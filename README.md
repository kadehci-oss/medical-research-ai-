# 🩺 Medical Research AI MVP

A physician-oriented Medical Research AI assistant built with **Python**, **Streamlit**, and **NCBI PubMed E-utilities**.

This application enables clinicians and medical researchers to perform real-time literature searches, verify PMIDs and DOIs against official databases, and generate structured Turkish Evidence Synthesis Reports (*Türkçe Kanıt Raporu*) backed strictly by real, non-fabricated NCBI PubMed citations.

---

## 🌟 Key Features

1. **🔎 Real PubMed E-utilities Search:**
   - Real-time integration with NCBI PubMed (`esearch` and `efetch` APIs).
   - Filter by publication type (*Randomized Controlled Trial*, *Systematic Review*, *Meta-Analysis*, *Clinical Trial*, *Review*).
   - Filter by publication date range and sort by relevance or date.
   - Complete metadata retrieval: PMIDs, DOIs, article titles, authors, journals, publication year, and full abstracts.

2. **✅ PMID & DOI Verification Engine:**
   - Instantly verify PMIDs against PubMed NCBI database.
   - Verify DOIs using CrossRef REST API and PubMed cross-referencing.
   - View publication status and full verified bibliographic details.

3. **📑 Turkish Evidence Synthesis Reports (*Türkçe Kanıt Raporu*):**
   - Automatically synthesizes evidence from verified PubMed search results into structured Turkish reports tailored for physicians.
   - **Structured Sections:**
     1. **Klinik Özet ve Sentez** (Clinical Summary & Key Findings)
     2. **Kanıt Seviyeleri ve Metodolojik Dağılım** (Levels of Evidence & Methodological Quality)
     3. **Klinik Uyarılar ve Sınırlılıklar** (Clinical Disclaimers & Methodological Limitations)
     4. **Doğrulanmış Kaynaklar ve Literatür Listesi** (Verified Bibliography)
   - **Zero Citation Fabrication:** Built with strict grounding constraints. Every citation links directly to its verified PubMed page (`https://pubmed.ncbi.nlm.nih.gov/<PMID>/`).
   - Supports both deterministic rule-based generation and optional LLM synthesis via OpenAI GPT models.

4. **💻 Interactive Physician Dashboard:**
   - Sleek multi-tab Streamlit dashboard designed for fast clinical workflow.
   - Export reports as Markdown (`.md`) files with one click.

---

## 🏗 Architecture & Project Structure

```
.
├── app.py                   # Streamlit web application dashboard
├── pubmed_client.py         # PubMed E-utilities client & PMID/DOI verifiers
├── report_generator.py      # Turkish Evidence Report synthesis engine
├── live_ncbi_validation.py  # Live NCBI PubMed API smoke validation script
├── ncbi_live_results.json   # Output results of live NCBI validation check
├── UZMAN_HEKIM_DEGERLENDIRME.md # Independent Expert Physician Evaluation Protocol
├── .github/workflows/
│   └── live-ncbi-validation.yml # GitHub Actions workflow for live NCBI validation
├── tests/
│   ├── test_pubmed_client.py   # Unit tests for PubMed client & verifiers
│   └── test_report_generator.py # Unit tests for report synthesis & anti-hallucination
├── AGENTS.md                # AI agent instructions & codebase conventions
└── README.md                # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Internet connection (for NCBI PubMed E-utilities and CrossRef API)

### Installation

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-org/medical-research-ai.git
   cd medical-research-ai
   ```

2. **Install dependencies:**
   ```bash
   pip install streamlit requests pytest openai python-dotenv
   ```

3. **(Optional) Set OpenAI API Key:**
   If you wish to use OpenAI LLM synthesis for report generation, set your API key as an environment variable or enter it directly in the Streamlit sidebar:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

---

## 🧪 Running Tests & Live NCBI Validation

### Unit & Integration Test Suite
Run the full automated test suite using `pytest`:

```bash
pytest
```

### Live NCBI PubMed API Validation
To verify real ESearch and EFetch calls directly against live NCBI production servers without mocks:

```bash
python live_ncbi_validation.py
```

This generates `ncbi_live_results.json` detailing the pass/fail status of ESearch queries and EFetch paper identities (PMID, DOI, Title).

This test is also executed automatically via GitHub Actions workflow (`.github/workflows/live-ncbi-validation.yml`).

---

## 🏃 Running the Application

Start the Streamlit dashboard locally:

```bash
streamlit run app.py
```

Then open your browser at `http://localhost:8501`.

---

## 🛡 Citation Integrity & Anti-Hallucination Policy

Medical safety requires absolute accuracy. Hallucinating paper citations or inventing PMIDs/DOIs is unacceptable in clinical research.

- **Direct API Sourcing:** All bibliographic records are fetched directly from NCBI PubMed XML outputs.
- **Verification First:** Verification tools query live CrossRef and PubMed servers.
- **Strict Grounding:** The report generator operates on verified PubMed payload objects only, ensuring zero fabricated PMIDs or paper titles.

---

## ⚕️ Independent Expert Physician Review Disclosure

- **Evaluation Protocol:** See `UZMAN_HEKIM_DEGERLENDIRME.md` for the evaluation framework, scoring criteria, and clinical safety thresholds for independent specialist physicians.
- **Status Notice:** **Uzman Hekim Değerlendirmesi / Onayı Henüz Tamamlanmamıştır (Yapılmadı / Tamamlanmadı).** The protocol form in `UZMAN_HEKIM_DEGERLENDIRME.md` is a baseline proposal for future double-blind expert review. No completed physician review or clinical validation approval is claimed.
