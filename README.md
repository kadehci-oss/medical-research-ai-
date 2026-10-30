# Medical Research AI

A physician-oriented literature assistant built with Python, Streamlit, FastAPI, and NCBI PubMed E-utilities.

It searches live PubMed, verifies PMIDs and DOIs against PubMed and CrossRef, and drafts a Turkish evidence synthesis report (*Türkçe Kanıt Raporu*) from those records. Bibliographic fields come from the APIs. The project rule is zero citation fabrication: do not invent PMIDs, DOIs, titles, authors, or journal names.

**Not for clinical use.** The independent expert physician review described in [`UZMAN_HEKIM_DEGERLENDIRME.md`](UZMAN_HEKIM_DEGERLENDIRME.md) has not been done. That file is an empty protocol (scoring form, reviewer slots, and acceptance criteria), not a completed evaluation. No specialist has signed off. Do not use this tool to diagnose, treat, or make clinical decisions.

**Klinik kullanım için değildir.** Bağımsız uzman hekim değerlendirmesi henüz yapılmamıştır.

---

## Key features

1. **PubMed E-utilities search** (`esearch` + `efetch`): publication-type and year filters, relevance or date sort, and metadata (PMID, DOI, title, authors, journal, year, abstract).
2. **PMID and DOI verification:** PMID lookup on PubMed; DOI lookup on CrossRef with a PubMed cross-check. Citation checks re-fetch the PMID and compare the normalized title and DOI.
3. **Turkish evidence report:** rule-based synthesis, with optional OpenAI synthesis when `OPENAI_API_KEY` is set. Citations point at `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`.
4. **Two interfaces:** a Streamlit dashboard (`app.py`) and a FastAPI service (`api.py`) that also exposes the universal evidence engine (`universal_evidence_engine.py`).

---

## Project structure

```
.
├── api.py                         # FastAPI app (search, verify, report, universal engine)
├── app.py                         # Streamlit dashboard
├── pubmed_client.py               # NCBI E-utilities and CrossRef client
├── report_generator.py            # Turkish evidence-report synthesis
├── universal_evidence_engine.py   # Disease-agnostic evidence search and synthesis
├── all_specialty_matrix.json      # Specialty matrix used by the evidence engine
├── live_ncbi_validation.py        # Live esearch/efetch smoke script (no mocks)
├── ncbi_live_results.json         # Last recorded live-validation output
├── requirements.txt               # Pinned direct dependencies
├── UZMAN_HEKIM_DEGERLENDIRME.md   # Expert-review protocol (not yet performed)
├── IMPLEMENTATION.md              # Architecture notes
├── AGENTS.md                      # Contributor and agent conventions
├── statin_myopathy_report.md      # Example generated report
├── .github/workflows/
│   ├── ci.yml                     # pytest on push and pull request
│   └── live-ncbi-validation.yml   # Scheduled and manual live NCBI check
└── tests/
    ├── test_api.py
    ├── test_app.py
    ├── test_heart_failure_regression.py
    ├── test_infectious_disease_regression.py
    ├── test_pubmed_client.py
    ├── test_real_pubmed_e2e.py
    ├── test_real_pubmed_regression.py
    ├── test_report_generator.py
    ├── test_statin_myopathy_e2e.py
    ├── test_statin_myopathy_regression.py
    └── test_universal_evidence_engine.py
```

---

## Getting started

### Prerequisites

- Python 3.11 or newer (3.12 is what CI and the pinned dependency set were checked with). Streamlit 1.66 and pandas 3.1 require 3.11+.
- Network access to NCBI E-utilities and the CrossRef API.

### Install

```bash
git clone https://github.com/kadehci-oss/medical-research-ai-.git
cd medical-research-ai-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `NCBI_TOOL` | No | Tool name sent as `tool` on every E-utilities request and used in the User-Agent. Default: `MedicalResearchAI`. |
| `NCBI_EMAIL` | No | Contact email sent as `email` on every E-utilities request and in the User-Agent. Default: `medical-research-ai@example.com` (not a personal address). Set this to a monitored mailbox before sustained use so NCBI can reach you. |
| `NCBI_API_KEY` | No | When set, sent as `api_key` on E-utilities requests only (not to CrossRef). Raises the NCBI rate limit. Omit it to leave the parameter off the request. |
| `OPENAI_API_KEY` | No | Enables optional LLM report synthesis. Without it, synthesis stays rule-based. The Streamlit sidebar can also take this key. |

```bash
export NCBI_TOOL="MedicalResearchAI"
export NCBI_EMAIL="you@example.com"
export NCBI_API_KEY="your-ncbi-api-key"
export OPENAI_API_KEY="your-openai-api-key"
```

No personal email is hardcoded. `live_ncbi_validation.py` is a separate smoke script and does not read these variables.

---

## Run the applications

Streamlit dashboard (default URL `http://localhost:8501`):

```bash
streamlit run app.py
```

FastAPI server. The ASGI app object is `app` in `api.py`. This command was checked locally: `GET /health` returns `{"status":"ok","service":"Medical Research AI API"}`.

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

- Health: `http://127.0.0.1:8000/health`
- Interactive docs: `http://127.0.0.1:8000/docs`
- `GET /api/search`
- `GET /api/verify/pmid/{pmid}`
- `GET /api/verify/doi/{doi}`
- `POST /api/verify/citation`
- `POST /api/report`
- `POST /api/universal_engine/synthesize`

---

## Tests and live NCBI check

```bash
pytest
python live_ncbi_validation.py
```

`pytest` mocks network calls. `live_ncbi_validation.py` calls production E-utilities with no mocks and writes `ncbi_live_results.json`. The same script runs from `.github/workflows/live-ncbi-validation.yml` (weekly and on manual dispatch). A passing smoke test is not a clinical validation.

---

## Citation integrity

Records are parsed from PubMed XML or CrossRef JSON. The report generator is only supposed to cite articles present in that payload. A green test run does not mean a physician has reviewed the wording, evidence grades, or clinical applicability.

---

## Expert review status

[`UZMAN_HEKIM_DEGERLENDIRME.md`](UZMAN_HEKIM_DEGERLENDIRME.md) is the protocol for a future double-blind review by at least two independent specialists. **That review has not been done.** The form is blank. This software is a research prototype, not a medical device, and it is not for clinical use.
