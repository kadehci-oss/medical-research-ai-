import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generate_review_packet import CSV_COLUMNS, build_review_packet
from grade_assessment import assess_preliminary_grade, format_preliminary_grade_markdown
from live_ncbi_validation import build_eutils_params
from pubmed_client import ncbi_request_headers
from report_generator import generate_rule_based_turkish_report
from specialty_matrix import detect_specialty, load_specialty_matrix
from specialty_terms import EXTRA_SPECIALTY_TERMS


SAMPLE_ARTICLES = [
    {
        "pmid": "34449189",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker"],
        "journal": "NEJM",
        "pub_year": "2021",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In this double-blind randomized trial, empagliflozin reduced heart failure hospitalization (HR 0.79, 95% CI 0.69-0.90, p<0.001).",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/34449189/",
    }
]


class TestPreliminaryGrade(unittest.TestCase):
    def test_rct_without_bias_language_does_not_invent_a_rob_downgrade(self):
        note = assess_preliminary_grade(SAMPLE_ARTICLES[0], "SGLT2 inhibitors in heart failure")
        self.assertEqual(note["starting_level"], "Yüksek")
        self.assertEqual(note["domains"]["risk_of_bias"]["status"], "düşürme yok")
        self.assertEqual(note["domains"]["inconsistency"]["status"], "değerlendirilemedi")
        self.assertEqual(note["domains"]["publication_bias"]["status"], "değerlendirilemedi")
        self.assertEqual(note["formal_grade_status"], "GRADE Değerlendirilmedi (Not Assessed)")
        self.assertIn("uzman hekim onayı", note["disclaimer"])

    def test_open_label_phrase_downgrades_only_risk_of_bias(self):
        article = {
            "pmid": "111",
            "title": "Open-label randomized trial of drug A",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "This open-label randomized trial enrolled adults. No confidence interval was reported.",
        }
        note = assess_preliminary_grade(article, "")
        self.assertEqual(note["domains"]["risk_of_bias"]["status"], "ciddi düşürme")
        self.assertEqual(note["domains"]["imprecision"]["status"], "değerlendirilemedi")
        self.assertEqual(note["preliminary_level"], "Orta")
        self.assertEqual(note["applied_downgrades"], 1)

    def test_meta_analysis_uses_reported_i2_only(self):
        article = {
            "pmid": "222",
            "title": "Meta-analysis of randomized trials",
            "publication_types": ["Meta-Analysis"],
            "abstract": "Randomized trials were pooled. I2 = 75%. Heterogeneity was high.",
        }
        note = assess_preliminary_grade(article, "treatment efficacy")
        self.assertEqual(note["starting_level"], "Yüksek")
        self.assertEqual(note["domains"]["inconsistency"]["status"], "ciddi düşürme")
        self.assertIn("75", note["domains"]["inconsistency"]["reason"])

    def test_empty_abstract_marks_domains_unassessed(self):
        article = {"pmid": "333", "title": "Untitled note", "publication_types": [], "abstract": ""}
        note = assess_preliminary_grade(article, "")
        self.assertEqual(note["starting_level"], "değerlendirilemedi")
        self.assertEqual(note["preliminary_level"], "değerlendirilemedi")
        self.assertTrue(all(item["status"] == "değerlendirilemedi" or item["status"] for item in note["domains"].values()))
        for key in ("inconsistency", "imprecision", "publication_bias"):
            self.assertEqual(note["domains"][key]["status"], "değerlendirilemedi")

    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"})
    def test_report_keeps_formal_grade_status_and_adds_preliminary_block(self, _mock_verify):
        report = generate_rule_based_turkish_report("SGLT2 inhibitors", SAMPLE_ARTICLES)
        self.assertIn("GRADE Değerlendirilmedi (Not Assessed)", report)
        self.assertIn("Ön GRADE-tarzı kesinlik tahmini", report)
        self.assertIn("34449189", format_preliminary_grade_markdown("SGLT2 inhibitors", SAMPLE_ARTICLES))


class TestSpecialtyCoverage(unittest.TestCase):
    def test_every_matrix_row_has_specific_terms(self):
        matrix = load_specialty_matrix()
        ids = [entry["id"] for entry in matrix["specialties"]]
        self.assertEqual(len(ids), 88)
        for sid in ids:
            terms = EXTRA_SPECIALTY_TERMS.get(sid) or []
            specific = [term for term in terms if len(term) >= 4]
            self.assertGreaterEqual(len(specific), 3, sid)
            keywords = next(entry["search_keywords"] for entry in matrix["specialties"] if entry["id"] == sid)
            lowered = {item.casefold() for item in keywords}
            self.assertIn(terms[0].casefold(), lowered)

    def test_representative_queries_map_to_expected_specialties(self):
        cases = {
            "psoriasis biologic therapy": "dermatoloji",
            "rheumatoid arthritis methotrexate": "romatoloji",
            "chronic kidney disease dialysis": "nefroloji",
            "COPD exacerbation inhaled corticosteroid": "gogus_hastaliklari",
            "preeclampsia aspirin": "kadin_hastaliklari_ve_dogum",
            "glaucoma intraocular pressure": "goz_hastaliklari",
            "otitis media antibiotics": "kulak_burun_bogaz",
            "hip fracture arthroplasty": "ortopedi_ve_travmatoloji",
            "preterm infant respiratory distress": "neonatoloji",
            "crispr gene editing": "tibbi_biyoteknoloji",
            "forensic autopsy toxicology": "adli_tip",
            "periodontitis scaling": "periodontoloji",
        }
        for query, expected in cases.items():
            detected = detect_specialty(query)
            self.assertIsNotNone(detected, query)
            self.assertEqual(detected["id"], expected, query)


class TestLiveValidationIdentity(unittest.TestCase):
    def test_build_eutils_params_reads_ncbi_env(self):
        with patch.dict(
            os.environ,
            {"NCBI_TOOL": "LabTool", "NCBI_EMAIL": "lab@example.com", "NCBI_API_KEY": "secret-key"},
            clear=False,
        ):
            params = build_eutils_params({"db": "pubmed", "term": "hfpef"})
            self.assertEqual(params["db"], "pubmed")
            self.assertEqual(params["tool"], "LabTool")
            self.assertEqual(params["email"], "lab@example.com")
            self.assertEqual(params["api_key"], "secret-key")
            self.assertIn("mailto:lab@example.com", ncbi_request_headers()["User-Agent"])

    def test_empty_api_key_is_omitted(self):
        with patch.dict(os.environ, {"NCBI_TOOL": "", "NCBI_EMAIL": "", "NCBI_API_KEY": ""}, clear=False):
            params = build_eutils_params({"db": "pubmed"})
            self.assertNotIn("api_key", params)
            self.assertEqual(params["tool"], "MedicalResearchAI")


class TestReviewPacket(unittest.TestCase):
    def test_packet_writes_reports_and_blank_scores(self):
        article = dict(SAMPLE_ARTICLES[0])

        def fake_search(query, max_results):
            return {"status": "success", "articles": [article], "total_count": 1}

        def fake_report(query, articles):
            return f"# Taslak\n\n{query}\n\nPMID: {articles[0]['pmid']}\n"

        with tempfile.TemporaryDirectory() as tmp, patch(
            "report_generator.verify_citation",
            return_value={"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"},
        ):
            out = build_review_packet(
                Path(tmp),
                [{"case_id": "TEST-01", "specialty": "Kardiyoloji", "query": "SGLT2 inhibitors vs placebo"}],
                pause_seconds=0,
                search_fn=fake_search,
                report_fn=fake_report,
            )
            markdown = (out / "TEST-01.md").read_text(encoding="utf-8")
            html = (out / "TEST-01.html").read_text(encoding="utf-8")
            self.assertIn("34449189", markdown)
            self.assertIn("Uzman değerlendirmesi yapılmış değildir", markdown)
            self.assertIn("34449189", html)
            with (out / "puanlama.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0].keys()), CSV_COLUMNS)
            self.assertEqual(rows[0]["vaka_id"], "TEST-01")
            self.assertEqual(rows[0]["klinik_soru_ve_pico_0_2"], "")
            self.assertEqual(rows[0]["uzman_degerlendirmesi"], "")
            self.assertIn("34449189", rows[0]["pmid_listesi"])
            self.assertIn("yapılmış değildir", (out / "OKU.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
