import unittest
from pubmed_client import verify_pmid
from report_generator import (
    extract_article_clinical_details,
    classify_study_design,
    assess_risk_of_bias,
    format_klinik_bulgular_cell,
    _format_cross_study_comparison,
    extract_clinical_profile,
    extract_pico,
)


class TestPmid35348616Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.article = verify_pmid("35348616")
        except Exception as exc:
            cls.article = None
            cls.skip_reason = f"PMID 35348616 network barrier: {exc}"

    def setUp(self):
        if not self.article or not self.article.get("valid"):
            self.skipTest(getattr(self, "skip_reason", "PMID 35348616 not available"))

    def test_sample_size_and_patient_group_and_study_design(self):
        details = extract_article_clinical_details(
            self.article, "statin-associated immune-mediated necrotizing myopathy"
        )
        self.assertEqual(details["sample_size"], "n = 21")
        self.assertIn("yerli amerikalı", details["patient_group"].lower())
        self.assertIn("inflamatuar miyopati", details["patient_group"].lower())
        self.assertEqual(details["study_design"], "Karşılaştırmalı Klinik Çalışma")
        self.assertEqual(details["evidence_level"], "Değerlendirilemedi")

        cd = classify_study_design(
            self.article.get("publication_types", []),
            self.article.get("title", ""),
            self.article.get("abstract", ""),
        )
        self.assertEqual(cd["design_key"], "comparative")
        self.assertEqual(cd["design"], "Karşılaştırmalı Klinik Çalışma")
        self.assertEqual(cd["level"], "Değerlendirilemedi")

        rob = assess_risk_of_bias(self.article)
        self.assertEqual(rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")

    def test_ck_biomarkers_treatments_mapped_to_sentences(self):
        profile = extract_clinical_profile(self.article.get("abstract", ""))
        categories = {item["category"] for item in profile}
        self.assertIn("biomarker", categories)
        self.assertIn("ck", categories)
        self.assertIn("treatment", categories)

        biomarkers = [item for item in profile if item["category"] == "biomarker"]
        self.assertTrue(any("anti-HMGCR" in item["line"] for item in biomarkers))
        self.assertTrue(any("ANA" in item["line"] for item in biomarkers))
        for item in biomarkers:
            self.assertTrue(item["sentence"])

        cks = [item for item in profile if item["category"] == "ck"]
        self.assertTrue(any("11 780" in item["line"] for item in cks))
        for item in cks:
            self.assertTrue(item["sentence"])

        treatments = [item for item in profile if item["category"] == "treatment"]
        self.assertTrue(any("IVIG" in item["line"] for item in treatments))
        self.assertTrue(any("antimetabolit" in item["line"] for item in treatments))
        self.assertTrue(any("rituksimab" in item["line"] for item in treatments))
        for item in treatments:
            self.assertTrue(item["sentence"])

    def test_section_5_and_6_synthesis_and_no_superiority(self):
        cell = format_klinik_bulgular_cell(self.article)
        self.assertIn("PMID: 35348616", cell)
        self.assertIn("Kaynak cümle:", cell)
        self.assertIn("anti-HMGCR antikoru", cell)
        self.assertIn("11 780 IU", cell)
        self.assertIn("IVIG, antimetabolit, rituksimab", cell)

        pico = extract_pico("statin-associated immune-mediated necrotizing myopathy")
        cross = _format_cross_study_comparison([self.article], pico)
        self.assertIn("35348616", cross)
        self.assertIn("Karşılaştırmalı Klinik Çalışma", cross)
        self.assertIn("21 hasta yerli Amerikalı", cross)
        self.assertNotIn("özette bildirilmedi", cross)
        self.assertIn("üstünlüğü (superiority) çıkarılamaz", cross)


if __name__ == "__main__":
    unittest.main()
