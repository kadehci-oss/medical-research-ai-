# Medical Research AI

A physician-oriented literature assistant built with Python, Streamlit, FastAPI, and NCBI PubMed E-utilities.

It searches live PubMed, checks citation identifiers and available title/DOI fields against PubMed and CrossRef, and drafts a Turkish evidence synthesis report (*Türkçe Kanıt Raporu*) from those records. Bibliographic fields come from APIs. Avoiding invented citations is a design goal, not a guarantee of factual or clinical correctness; generated claims still need human source review.

**Not for clinical use.** The independent expert physician review described in [`UZMAN_HEKIM_DEGERLENDIRME.md`](UZMAN_HEKIM_DEGERLENDIRME.md) has not been done. That file is an empty protocol (scoring form, reviewer slots, and acceptance criteria), not a completed evaluation. No specialist has signed off. Do not use this tool to diagnose, treat, or make clinical decisions.

**Klinik kullanım için değildir.** Bağımsız uzman hekim değerlendirmesi henüz yapılmamıştır.

---

## Key features

1. **PubMed E-utilities search** (`esearch` + `efetch`): publication-type and year filters, relevance or date sort, metadata (PMID, DOI, title, authors, journal, year, abstract), and offset pagination. `/api/search` accepts `max_results` (1–50) and zero-based `retstart`; responses expose `pagination.has_more`, `next_retstart`, and `truncated`. One ESearch request can retrieve at most 10,000 IDs; offsets beyond that window are not supported.
2. **PMID and DOI verification:** PMID lookup on PubMed; DOI lookup on CrossRef with a PubMed cross-check. Citation checks re-fetch the PMID and compare the normalized title and DOI.
3. **Turkish evidence report:** rule-based synthesis, with optional OpenAI synthesis only after explicit data-transfer confirmation. An API key alone does not enable external synthesis. Citations point at `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`.
4. **Two interfaces:** a Streamlit dashboard (`app.py`) and a FastAPI service (`api.py`) that also exposes the universal evidence engine (`universal_evidence_engine.py`).

Search is a PubMed-based preliminary search, not a systematic review or a claim of comprehensive coverage. The report does not screen every retrieved record against a registered inclusion/exclusion protocol. Cross-study matching is abstract-only; family deduplication requires a derived-report cue, an explicit source-text link to one named parent, and a shared trial identity. A common acronym or registry number, or title similarity, alone does not merge records. This is not evidence that studies or cohorts are clinically equivalent.

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
├── question_parser.py             # P/I/C/O spans from questions written as sentences (English and Turkish)
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
│   ├── ci.yml                     # pytest on push and pull request (Python 3.11 and 3.12)
│   └── live-ncbi-validation.yml   # Weekly and manual live NCBI check (Python 3.12)
└── tests/                         # pytest suite: unit and integration tests, saved real-PubMed regressions,
                                   # source-faithfulness checks and the validation-report consistency test
```

---

## Getting started

### Prerequisites

- Python 3.11 and 3.12 are tested in CI from the pinned dependency set. The weekly live NCBI validation workflow currently runs on Python 3.12. Streamlit 1.66 and pandas 3.1 require Python 3.11+.
- Network access to NCBI E-utilities and the CrossRef API.

### Install

```bash
git clone https://github.com/kadehci-oss/medical-research-ai-.git
cd medical-research-ai-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` lists the direct dependencies. `requirements.lock` is a full `pip freeze` from a clean Python 3.11 virtual environment created after `pip install -r requirements.txt`; Python 3.11 is the lowest supported interpreter, and CI verifies the same lock on 3.11 and 3.12. Use the lock file when the install must be reproducible:

```bash
pip install -r requirements.lock
```

Regenerate the lock file from a clean Python 3.11 virtual environment whenever `requirements.txt` changes. Do not edit `requirements.lock` by hand.

CI (`.github/workflows/ci.yml`) installs from `requirements.lock`, runs `pip check` and the full pytest suite on Python 3.11 and 3.12. The live NCBI workflow remains on Python 3.12. If a locked install fails, the job stops rather than silently testing with the looser `requirements.txt`; regenerate and review the lock file when dependencies change.

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

---

## Rapor Kalite Denetçisi (Report Quality Audit)

Üretilen Türkçe kanıt sentezi Markdown raporlarını otomatik olarak denetlemek için `tools/report_quality_audit.py` aracı kullanılır. Bu araç canlı raporları manuel kontrol etmek yerine sayımlar ve kritik ihlal kontrolleri yapar:

- Kaynak cümle / alıntı / kaynakça dışındaki ham İngilizce cümleler
- Ardışık yinelenen sözcükler (ör. "oranı oranı")
- Aynı blok içinde birebir yinelenen satırlar veya sonlanım maddeleri
- Etiketsiz sayı listeleri (ör. "15 hasta; 15 hasta; 5 hasta")
- Anlamlılık çelişkileri (aynı cümlede "anlamlı bir fark saptanmamıştır" veya "değerlendirilemedi" ile p < 0.05 çelişkisi — **kritik**)
- GA alanında ham İngilizce metin ("confidence interval", "CI")
- Uzman hekim değerlendirmesi için yapıldı iddiası (**kritik**)

### Kullanım:

```bash
# Markdown dosyasını denetle (özet çıktı)
python tools/report_quality_audit.py statin_myopathy_report.md

# JSON formatında çıktı al
python tools/report_quality_audit.py statin_myopathy_report.md --json

# Standart girdiden (stdin) boru hattıyla çalıştır
cat statin_myopathy_report.md | python tools/report_quality_audit.py

# Python modülü olarak çağır
from tools.report_quality_audit import audit_report_quality
result = audit_report_quality(report_markdown)
```

`pytest` mocks network calls. `live_ncbi_validation.py` calls production E-utilities with no mocks and overwrites `ncbi_live_results.json` in the current working directory. The copy committed in this repository is only a saved local run and may be stale; the latest scheduled or manual GitHub Actions result is available as that run's uploaded artifact and does not update the repository file. The script runs from `.github/workflows/live-ncbi-validation.yml` on Python 3.12, every Monday at 08:17 UTC and on manual dispatch. That job installs from `requirements.lock` and passes `NCBI_EMAIL` from the Actions secret described above. A passing smoke test is not a clinical or security validation.

---

## Structured evidence engine (v1.5.0)

Every PubMed record is turned into one `Study` object (`evidence_model.py`). Search cards in Streamlit, report sections 5, 6, 7 and 12, the API detail endpoint and the downloadable Markdown/HTML/JSON exports all read the sample size and effect estimates from that same object, so a value cannot differ between views.

- **Data model:** `Study`, `Population`, `StudyArm`, `Intervention`, `Comparator`, `CoTreatment`, `Outcome`, `EffectEstimate`, `FollowUpTimepoint`, `EventCount`, `EvidenceSource`, `RiskOfBiasAssessment`, `CertaintyAssessment`, `StudyRelation`. A structured follow-up timepoint is attached to an effect estimate only when it is explicit, unambiguous, and copied from that estimate’s verified source sentence; absent or competing timepoints remain `null`.
- **Counts kept apart:** total participants, arm sizes and event numerators are separate fields. An arm total that the abstract does not state is shown as "kol sayılarının toplamı".
- **Effect estimates:** HR, OR, RR, IRR, RD, MD, SMD, WMD, DOR, sensitivity, specificity, AUC, PPV, NPV, LR and accuracy are parsed with their own CI (and CI level, e.g. 90%) and bound to the outcome named in the sentence. A missing point estimate stays missing. A CI that does not contain its estimate is rejected and left out of synthesis.
- **Claim types:** causal wording only for randomized comparisons and pooled randomized evidence; observational results are shown as associations, diagnostic results as accuracy, case series as descriptive.
- **RoB / GRADE:** the tool is chosen, but the status stays `not_assessed`; no rating is generated.
- **Study relations:** a derived report is linked only when its role is explicit, its source text names one parent through a relation phrase, and the identity matches. A shared registry number or acronym alone, or similar titles, never merges cohorts. Ambiguous pooled analyses and derived reports without a verified parent are not promoted to independent primary units; this can undercount evidence and should be read as a conservative software rule, not a cohort adjudication.
- **Question framework:** `question_framework.py` picks PICO, PIRD (diagnosis), PFO (prognosis), PEO/PECO (aetiology, harm), CoCoPop (epidemiology), screening-PICO or SPICE (health services). Values come only from the query. `question_parser.py` reads questions written as sentences ("Does X reduce Y in Z?", "Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi azaltır mı?"); every value is a span of the query, nothing is translated. Abstracts are English, so a Turkish query term that does not appear in an abstract leaves that field "unknown" in cross-study matching instead of marking the studies as mismatched. PubMed itself is searched in English: write the search terms in English.
- **Faithful estimates:** a non-inferiority or equivalence p-value is labelled as such and never read as a test for a difference; an analysis stratum named at the start of a sentence ("In the HBR stratum, …") is shown with each estimate; a number that is part of a compound word ("12-lead ECG") or the lower bound of a labelled interval ("95% CI for mean difference, 0.43-1.01") is not an estimate; a measure named once in a list ("ischaemic stroke (HR, 95% CI: 0.81, 0.68-0.96) and all-cause death (0.91, 0.86-0.96)") applies to each later group whose interval contains its value; an outcome qualifier ("ischaemic", "fatal", "major") is never dropped in translation, and an untranslated outcome is shown as the source term rather than as "not named".
- **Report verification:** `report_verification.py` checks that every cited PMID is in the article set, every quoted source sentence is verbatim in that PMID's abstract, no RoB/GRADE rating is asserted and no causal wording is attached to a non-randomized study. Streamlit shows the status and version; exports carry it in a footer.

### Validation

Three test categories:

1. **Software unit and integration tests:** `tests/test_evidence_model.py`, `tests/test_pubmed_client.py`, `tests/test_api.py` (including two-page search endpoint coverage), `tests/test_question_framework.py` (including report-verification tests), plus the existing suite. CI runs the complete suite on Python 3.11 and 3.12.
2. **Real PubMed source verification:** `tests/test_pubmed_source_verification.py`. The recorded PubMed records in `validation/` are checked offline; `RUN_LIVE_PUBMED=1 pytest tests/test_pubmed_source_verification.py` re-fetches every PMID from NCBI and compares title and DOI.
3. **Independent clinical data validation:** `tests/test_clinical_reference_validation.py` compares engine output with pre-specified reference tables (68 real PubMed publications, 8 required specialties plus obstetrics: cardiology, oncology, neurology, infectious diseases, endocrinology, paediatrics, surgery, radiology; RCT, cohort, case-control, diagnostic accuracy, case series, systematic review, meta-analysis).

`python validation/run_multispecialty_validation.py` regenerates [`validation/MULTISPECIALTY_VALIDATION_REPORT.md`](validation/MULTISPECIALTY_VALIDATION_REPORT.md). The development set was used while tuning, so its numbers are optimistic. The honest estimates are the **frozen first runs on two held-out sets** (reference written before the engine saw them; set 2 was built after fixing set 1's errors, to test whether the fixes generalize): complete extraction 77.9% and 78.8%, false extraction 8.6% and 11.9%, source-sentence match 100%, 0 false causal claims. The rule-based extractor plateaus around 78% completeness on unseen abstracts; fixes made on one set did not raise the first-run score on the next. All reference tables were prepared by an AI assistant from abstracts only; no independent physician has checked them.

The fixed eight-record live PubMed benchmark is separate from offline pull-request CI and can be rerun with `python validation/run_pubmed_benchmark.py`. It re-fetches the records, checks the reference quote text against each current abstract/title, and writes JSON/Markdown reports with runner/reference hashes and a hash for each fetched abstract. Its source-text and rendered-claim phrase checks are software checks only; they are not independent clinical adjudication, GRADE, or proof of clinical accuracy. A fetch failure is reported as not evaluated rather than as a zero-violation result.

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
