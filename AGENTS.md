# AGENTS.md

## Overview & Scope
This repository contains a physician-oriented Medical Research AI MVP built with Python, Streamlit, and NCBI PubMed E-utilities.
The instructions in this file apply to the entire repository.

---

## Code Base Conventions & Architecture

1. **`pubmed_client.py`**:
   - Handles all interactions with NCBI PubMed E-utilities (`esearch.fcgi`, `efetch.fcgi`) and CrossRef REST API.
   - Parses XML responses safely using `xml.etree.ElementTree`.
   - Implements PMID and DOI verification logic.

2. **`report_generator.py`**:
   - Generates structured Turkish Evidence Synthesis Reports ("Türkçe Kanıt Raporu").
   - Classifies study design (RCT, cohort, case-control, cross-sectional, case report, case series, systematic review, meta-analysis, guideline) without assigning an evidence grade from the design alone.
   - Contains both a rule-based deterministic synthesizer and an optional OpenAI LLM synthesizer with strict anti-hallucination grounding prompt constraints.

3. **`app.py`**:
   - The user-facing Streamlit application.
   - Organized in clean tabs for PubMed Search, PMID/DOI Verification, and Turkish Evidence Report Generation.

4. **`tests/`**:
   - Contains unit and integration tests using `pytest` and `unittest.mock`.
   - All external network calls in unit tests must be mocked where appropriate.

---

## Coding Guidelines

- **Zero Citation Fabrication:** Never invent, fabricate, or hallucinate PMIDs, DOIs, paper titles, authors, or journal names.
- **Error Handling:** Gracefully handle network timeouts and API errors without crashing the UI.
- **Language Requirements:** User interfaces and report synthesis outputs meant for physicians should be in Turkish ("Türkçe Kanıt Raporu"), while source code comments and docstrings should be in clear English or Turkish.
- **Testing:** Always run `pytest` after modifying core client or report synthesis logic.

---

## Development Workflow Commands

- **Run Tests:** `pytest`
- **Run Application:** `streamlit run app.py`
- **Check Syntax:** `python3 -m py_compile pubmed_client.py report_generator.py app.py`
