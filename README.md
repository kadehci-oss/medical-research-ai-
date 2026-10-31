# Medical Research AI

A physician-oriented literature assistant built with Python, Streamlit, FastAPI, and NCBI PubMed E-utilities.

It searches live PubMed, checks citation identifiers and available title/DOI fields against PubMed and CrossRef, and drafts a Turkish evidence synthesis report (*Türkçe Kanıt Raporu*) from those records. Bibliographic fields come from APIs. Avoiding invented citations is a design goal, not a guarantee of factual or clinical correctness; generated claims still need human source review.

**Not for clinical use.** The independent expert physician review described in [`UZMAN_HEKIM_DEGERLENDIRME.md`](UZMAN_HEKIM_DEGERLENDIRME.md) has not been done. That file is an empty protocol (scoring form, reviewer slots, and acceptance criteria), not a completed evaluation. No specialist has signed off. Do not use this tool to diagnose, treat, or make clinical decisions.

**Klinik kullanım için değildir.** Bağımsız uzman hekim değerlendirmesi henüz yapılmamıştır.

---

## Key features

1. **PubMed E-utilities search** (`esearch` + `efetch`): publication-type and year filters, relevance or date sort, and metadata (PMID, DOI, title, authors, journal, year, abstract).
2. **PMID and DOI verification:** PMID lookup on PubMed; DOI lookup on CrossRef with a PubMed cross-check. Citation checks re-fetch the PMID and compare the normalized title and DOI.
3. **Turkish evidence report:** rule-based synthesis, with optional OpenAI synthesis only after explicit data-transfer confirmation. An API key alone does not enable external synthesis. Citations point at `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`.
4. **Two interfaces:** a Streamlit dashboard (`app.py`) and a FastAPI service (`api.py`) that also exposes the universal evidence engine (`universal_evidence_engine.py`).

Search is a PubMed-based preliminary search, not a systematic review or a claim of comprehensive coverage. The report does not screen every retrieved record against a registered inclusion/exclusion protocol. Cross-study matching is heuristic and abstract-only; it is not evidence that studies are clinically equivalent.

## Product goal and current gap

The intended goal is a Turkish, expert-level report for clinical research questions across medical specialties, grounded in verified real publications. **This version does not yet meet that goal.** It searches PubMed only, retrieves bibliographic records and available abstracts rather than full text, and uses keyword-based matching across 88 configured specialty labels. Search, outcome extraction, cross-study comparison, and GRADE-style notes are not an exhaustive or independently validated clinical review. PMID/title/DOI matching verifies record identity; it does not prove that every report claim is supported by that source. Independent specialist review has not been performed.

---

## Project structure

```
.
├── api.py                         # FastAPI app (search, verify, report, universal engine)
├── app.py                         # Streamlit dashboard
├── pubmed_client.py               # NCBI E-utilities and CrossRef client
├── report_generator.py            # Turkish evidence-report synthesis
├── universal_evidence_engine.py   # PubMed/abstract-based preliminary search and synthesis
├── evidence_model.py              # Structured Study model shared by cards, sections 5/6 and exports
├── question_framework.py          # Question type -> PICO / PIRD / PFO / PECO / CoCoPop / SPICE
├── report_verification.py         # Report audit: PMIDs, verbatim quotes, RoB/GRADE, causal wording
├── version.py                     # User-visible software version
├── validation/                    # Real PubMed records, reference tables, validation runner and report
├── all_specialty_matrix.json      # Specialty matrix used by the evidence engine
├── live_ncbi_validation.py        # Live esearch/efetch smoke script (no mocks)
├── ncbi_live_results.json         # Saved local smoke-test output; may be stale
├── requirements.txt               # Pinned direct dependencies
├── UZMAN_HEKIM_DEGERLENDIRME.md   # Expert-review protocol (not yet performed)
├── IMPLEMENTATION.md              # Architecture notes
├── AGENTS.md                      # Contributor and agent conventions
├── statin_myopathy_report.md      # Example generated report
├── .github/workflows/
│   ├── ci.yml                     # pytest on push and pull request (Python 3.12)
│   └── live-ncbi-validation.yml   # Weekly and manual live NCBI check (Python 3.12)
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

- Python 3.12 is what CI, the weekly NCBI workflow, and the pinned dependency set are checked with. Python 3.11+ is the declared dependency baseline, but 3.11 is not currently verified by CI. Streamlit 1.66 and pandas 3.1 require 3.11+.
- Network access to NCBI E-utilities and the CrossRef API.

### Install

```bash
git clone https://github.com/kadehci-oss/medical-research-ai-.git
cd medical-research-ai-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` lists the direct dependencies. `requirements.lock` is a full `pip freeze` from a clean Python 3.12 virtual environment created after `pip install -r requirements.txt`. Use the lock file when the install must be reproducible:

```bash
pip install -r requirements.lock
```

Regenerate the lock file from a clean virtual environment whenever `requirements.txt` changes. Do not edit `requirements.lock` by hand.

CI (`.github/workflows/ci.yml`) and the live NCBI workflow install from `requirements.lock` on Python 3.12 and run `pip check`. If the locked install fails, the job stops rather than silently testing with the looser `requirements.txt`; regenerate and review the lock file when dependencies change.

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `NCBI_TOOL` | No | Tool name sent as `tool` on every E-utilities request and used in the User-Agent. Default: `MedicalResearchAI`. |
| `NCBI_EMAIL` | No | Contact email sent as `email` on every E-utilities request and in the User-Agent. Default: `medical-research-ai@example.com` (not a personal address). Set this to a monitored mailbox before sustained use so NCBI can reach you. |
| `NCBI_API_KEY` | No | When set, sent as `api_key` on E-utilities requests only (not to CrossRef). Raises the NCBI rate limit. Omit it to leave the parameter off the request. |
| `OPENAI_API_KEY` | No | Credential for optional LLM report synthesis. Synthesis remains off until the user explicitly confirms data transfer. Once confirmed, the query, article metadata, and PubMed abstracts are sent to OpenAI. Do not include patient-identifying or confidential health information. |

```bash
export NCBI_TOOL="MedicalResearchAI"
export NCBI_EMAIL="you@example.com"
export NCBI_API_KEY="your-ncbi-api-key"
export OPENAI_API_KEY="your-openai-api-key"
```

No personal email is hardcoded. `live_ncbi_validation.py` sends the same `tool`, `email`, and optional `api_key` values as `pubmed_client.py`.

The weekly workflow reads `NCBI_EMAIL`, `NCBI_API_KEY`, and `NCBI_TOOL` from GitHub Actions secrets. **Set the repository secret `NCBI_EMAIL` under Settings > Secrets and variables > Actions.** `NCBI_API_KEY` and `NCBI_TOOL` are optional; an empty `NCBI_API_KEY` is left off the request. If `NCBI_EMAIL` is missing, the job prints a `::warning::` and continues with the non-personal default above. This repository is public, so the monitored contact address belongs in that secret.

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

The report endpoints accept citation identifiers (PMID, with optional title/DOI for matching), fetch the authoritative article record from PubMed, and synthesize from that fetched record rather than trusting client-supplied abstracts or authors. At most 50 citations are accepted per report request.

LLM synthesis is off by default. For API requests, setting `use_llm: true` with an OpenAI key also requires `llm_data_transfer_confirmed: true`; this confirms that the query and PubMed metadata/abstracts may be sent to OpenAI and contain no patient-identifying or confidential health data. Without that confirmation, the API rejects the request before fetching citations. In Streamlit, OpenAI also starts disabled and the user must explicitly confirm the data transfer; otherwise the report stays local and rule-based.

The API does not provide user authentication or request-rate limiting. The documented Uvicorn command binds to `127.0.0.1`; do not expose the service directly to the public internet. A public deployment must add authentication, rate/body limits, TLS, and appropriate proxy configuration.

---

## Tests and live NCBI check

```bash
pytest
python live_ncbi_validation.py
```

`pytest` mocks network calls. `live_ncbi_validation.py` calls production E-utilities with no mocks and overwrites `ncbi_live_results.json` in the current working directory. The copy committed in this repository is only a saved local run and may be stale; the latest scheduled or manual GitHub Actions result is available as that run's uploaded artifact and does not update the repository file. The script runs from `.github/workflows/live-ncbi-validation.yml` on Python 3.12, every Monday at 08:17 UTC and on manual dispatch. That job installs from `requirements.lock` and passes `NCBI_EMAIL` from the Actions secret described above. A passing smoke test is not a clinical or security validation.

---

## Structured evidence engine (v1.5.0)

Every PubMed record is turned into one `Study` object (`evidence_model.py`). Search cards in Streamlit, report sections 5 and 6, and the downloadable Markdown/HTML/JSON exports all read that same object, so a value cannot differ between views.

- **Data model:** `Study`, `Population`, `StudyArm`, `Intervention`, `Comparator`, `CoTreatment`, `Outcome`, `EffectEstimate`, `EventCount`, `EvidenceSource`, `RiskOfBiasAssessment`, `CertaintyAssessment`, `StudyRelation`. Each extracted value carries PMID, DOI, the verbatim source sentence and a verification status (`kaynakta_dogrulandi`, `kaynaktan_hesaplandi`, `kaynakta_bulunamadi`).
- **Counts kept apart:** total participants, arm sizes and event numerators are separate fields. An arm total that the abstract does not state is shown as "kol sayılarının toplamı".
- **Effect estimates:** HR, OR, RR, IRR, RD, MD, SMD, WMD, DOR, sensitivity, specificity, AUC, PPV, NPV, LR and accuracy are parsed with their own CI (and CI level, e.g. 90%) and bound to the outcome named in the sentence. A missing point estimate stays missing. A CI that does not contain its estimate is rejected and left out of synthesis.
- **Claim types:** causal wording only for randomized comparisons and pooled randomized evidence; observational results are shown as associations, diagnostic results as accuracy, case series as descriptive.
- **RoB / GRADE:** the tool is chosen, but the status stays `not_assessed`; no rating is generated.
- **Study relations:** secondary/post hoc analyses, later interim analyses, extended follow-up and meta-analyses are linked to the parent trial by shared registry number (NCT, ISRCTN, NTR, DRKS, …) or trial acronym. Derived reports and meta-analyses are not counted as independent evidence, so the same participants are not counted twice.
- **Question framework:** `question_framework.py` picks PICO, PIRD (diagnosis), PFO (prognosis), PEO/PECO (aetiology, harm), CoCoPop (epidemiology), screening-PICO or SPICE (health services). Values come only from the query.
- **Report verification:** `report_verification.py` checks that every cited PMID is in the article set, every quoted source sentence is verbatim in that PMID's abstract, no RoB/GRADE rating is asserted and no causal wording is attached to a non-randomized study. Streamlit shows the status and version; exports carry it in a footer.

### Validation

Three test categories:

1. **Software unit and integration tests:** `tests/test_evidence_model.py`, `tests/test_question_framework.py` (including report-verification tests), plus the existing suite.
2. **Real PubMed source verification:** `tests/test_pubmed_source_verification.py`. The recorded PubMed records in `validation/` are checked offline; `RUN_LIVE_PUBMED=1 pytest tests/test_pubmed_source_verification.py` re-fetches every PMID from NCBI and compares title and DOI.
3. **Independent clinical data validation:** `tests/test_clinical_reference_validation.py` compares engine output with pre-specified reference tables (51 real PubMed publications, 8 specialties: cardiology, oncology, neurology, infectious diseases, endocrinology, paediatrics, surgery, radiology; RCT, cohort, case-control, diagnostic accuracy, case series, systematic review, meta-analysis).

`python validation/run_multispecialty_validation.py` regenerates [`validation/MULTISPECIALTY_VALIDATION_REPORT.md`](validation/MULTISPECIALTY_VALIDATION_REPORT.md). The development set was used while tuning, so its numbers are optimistic. The honest estimate is the **frozen first run on the held-out set** (16 publications, reference written before the engine saw them): complete extraction 77.9%, false extraction 8.6%, source-sentence match 100%, 0 false causal claims. Both reference tables were prepared by an AI assistant from abstracts only; no independent physician has checked them.

---

## Citation integrity

Records are parsed from PubMed XML or CrossRef JSON. Report endpoints fetch canonical PubMed records by PMID and compare submitted title/DOI only when those fields are provided; absent fields are not considered matched. This check confirms record identity, not that every generated statement is supported by its citation. A green test run does not mean a physician has reviewed the wording, evidence grades, or clinical applicability.

---

## Expert review status

[`UZMAN_HEKIM_DEGERLENDIRME.md`](UZMAN_HEKIM_DEGERLENDIRME.md) is the protocol for a future double-blind review by at least two independent specialists. **That review has not been done.** The form is blank. This software is a research prototype, not a medical device, and it is not for clinical use.

To prepare materials for that review, without claiming it has happened:

```bash
python generate_review_packet.py --output review_packet --limit 8 --max-results 5 --pause 2
```

The command calls live PubMed, writes one Markdown file and one HTML file per question, and writes `puanlama.csv` with empty score columns that match the protocol (PICO, source identity, claim-source match, study design, safety, uncertainty, critical error, reviewer decision and signature). Pause between questions so NCBI is not called back-to-back. Filling the CSV and signing it is a human physician's job. The script does not fill scores and does not record an approval.

The current protocol's 30 questions cover only statin myopathy, heart failure, and infectious diseases; it is a limited pilot sample and cannot validate performance across all 88 configured specialty labels or all clinical question types.
