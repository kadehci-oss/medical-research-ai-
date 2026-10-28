import unittest
from unittest.mock import patch
from report_generator import (
    generate_rule_based_turkish_report,
    generate_turkish_evidence_report,
    _classify_evidence_level,
    classify_study_design,
    generate_evidence_table_markdown,
    generate_evidence_table_html,
    perform_red_team_audit,
    generate_html_report
)

SAMPLE_ARTICLES = [
    {
        "pmid": "33264510",
        "doi": "10.1056/NEJMoa2022190",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker", "Javed Butler"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2020",
        "publication_types": ["Randomized Controlled Trial", "Journal Article"],
        "abstract": "SGLT2 inhibitors reduce the risk of hospitalization in heart failure patients.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/33264510/",
        "doi_url": "https://doi.org/10.1056/NEJMoa2022190"
    },
    {
        "pmid": "31535829",
        "doi": "10.1056/NEJMoa1911303",
        "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
        "authors": ["John J V McMurray", "Solomon D Solomon"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2019",
        "publication_types": ["Clinical Trial"],
        "abstract": "Dapagliflozin lowered risk of cardiovascular events in HFrEF.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31535829/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1911303"
    }
]


class TestReportGenerator(unittest.TestCase):

    def test_classify_study_design(self):
        rct = classify_study_design(["Randomized Controlled Trial"], "Title", "Abstract")
        self.assertEqual(rct["level"], "Seviye 2")
        self.assertIn("Rastgele Kontrollü", rct["design"])

        meta = classify_study_design(["Systematic Review"], "Meta-analysis title", "Abstract")
        self.assertEqual(meta["level"], "Seviye 1")
        self.assertIn("Sistematik Derleme", meta["design"])

        cohort = classify_study_design([], "Prospective Cohort Study", "A cohort of patients")
        self.assertEqual(cohort["level"], "Seviye 3")

    def test_classify_evidence_level(self):
        level_rct = _classify_evidence_level(["Randomized Controlled Trial"], "Title", "Abstract")
        self.assertIn("Seviye 2", level_rct)

    def test_evidence_table_markdown_generation(self):
        table_md = generate_evidence_table_markdown(SAMPLE_ARTICLES)
        self.assertIn("| # | Çalışma / Yazar (Yıl) |", table_md)
        self.assertIn("Stefan D Anker", table_md)
        self.assertIn("PMID: 33264510", table_md)

    def test_evidence_table_html_generation(self):
        table_html = generate_evidence_table_html(SAMPLE_ARTICLES)
        self.assertIn("<table", table_html)
        self.assertIn("Empagliflozin in Heart Failure", table_html)
        self.assertIn("PMID: 33264510", table_html)

    @patch("report_generator.verify_citation")
    def test_perform_red_team_audit(self, mock_verify_citation) -> None:
        mock_verify_citation.side_effect = [
            {"status": "verified", "verified": True, "pmid": "33264510", "reason": "match"},
            {"status": "verified", "verified": True, "pmid": "31535829", "reason": "match"}
        ]
        audit = perform_red_team_audit("Heart Failure SGLT2", SAMPLE_ARTICLES)
        self.assertIn("DENETLEME TAMAMLANDI", audit["status"])
        self.assertEqual(audit["citation_integrity"]["verified_citations"], 2)
        self.assertEqual(audit["citation_integrity"]["rejected_citations"], 0)
        self.assertEqual(audit["citation_integrity"]["mismatch_or_invalid_citations_detected"], 0)
        self.assertTrue(audit["grade_rating_policy"]["compliant"])
        self.assertEqual(audit["grade_rating_policy"]["grade_status"], "GRADE Değerlendirilmedi (Not Assessed)")
        self.assertIn("NCBI PubMed E-utilities API", audit["metadata_retrieval_source"])
        self.assertIn("Klinik Doğrulama Yapılmamıştır", audit["clinical_validation_status"])

        # Ensure no false claims in audit dictionary keys or string representations
        audit_str = str(audit)
        self.assertNotIn("100/100", audit_str)
        self.assertNotIn("100 / 100", audit_str)
        self.assertNotIn("0% (Sıfır)", audit_str)

    def test_generate_rule_based_turkish_report(self):
        query = "SGLT2 inhibitors in heart failure"
        report = generate_rule_based_turkish_report(query, SAMPLE_ARTICLES)

        # Check required sections
        self.assertIn("Türkçe Kanıt Raporu", report)
        self.assertIn("1. 🔍 PICO Yapısı ve Klinik Özet Sentezi", report)
        self.assertIn("2. 📊 Yapılandırılmış Kanıt Tablosu", report)
        self.assertIn("📋 Klinik PICO Çerçevesi", report)
        self.assertIn("Yanlılık Riski Değerlendirmesi", report)
        self.assertIn("3. ⚠️ Metodolojik Sınırlılıklar ve Klinik Uyarılar", report)
        self.assertIn("4. 🛡️ Red Team Denetimi ve Atıf Dürüstlüğü Analizi", report)
        self.assertIn("5. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi", report)

        # Check for mandatory disclaimers and limitations
        self.assertIn("Özet Metin Sınırlılığı Uyarısı", report)
        self.assertIn("Abstract-Only Limitation", report)
        self.assertIn("GRADE Değerlendirilmedi (Not Assessed)", report)
        self.assertIn("Klinik Doğrulama İddiası Yoktur", report)
        self.assertIn("No Clinical Validation Claimed", report)

        # Check citation distinction
        self.assertIn("PubMed Metadata Alımı", report)
        self.assertIn("Bağımsız Atıf Doğrulaması", report)

        # Ensure real PMIDs are present
        self.assertIn("PMID: [33264510]", report)
        self.assertIn("PMID: [31535829]", report)
        self.assertIn("Empagliflozin in Heart Failure", report)

        # Check absence of false claims
        self.assertNotIn("100/100", report)
        self.assertNotIn("100 / 100", report)
        self.assertNotIn("0% (Sıfır)", report)
        self.assertNotIn("SIFIR HALÜSİNASYON", report)

    def test_generate_report_empty_articles(self):
        query = "Unknown condition xyz"
        report = generate_rule_based_turkish_report(query, [])
        self.assertIn("Sonuç Bulunamadı", report)

    def test_generate_turkish_evidence_report_fallback(self):
        report = generate_turkish_evidence_report("SGLT2 inhibitors", SAMPLE_ARTICLES, api_key=None, use_llm=False)
        self.assertIn("Türkçe Kanıt Raporu", report)
        self.assertIn("33264510", report)

    def test_generate_html_report(self):
        markdown_rep = generate_rule_based_turkish_report("SGLT2 inhibitors", SAMPLE_ARTICLES)
        html_rep = generate_html_report("SGLT2 inhibitors", SAMPLE_ARTICLES, markdown_rep)
        self.assertIn("<!DOCTYPE html>", html_rep)
        self.assertIn("Türkçe Klinik Kanıt Raporu", html_rep)
        self.assertIn("GRADE Statüsü:", html_rep)
        self.assertIn("GRADE Değerlendirilmedi", html_rep)
        self.assertIn("Abstract-Only Limitation", html_rep)
        self.assertIn("No Clinical Validation claimed", html_rep)

        self.assertNotIn("100/100", html_rep)
        self.assertNotIn("100 / 100", html_rep)
        self.assertNotIn("0% (Sıfır)", html_rep)
        self.assertNotIn("SIFIR HALÜSİNASYON", html_rep)


if __name__ == "__main__":
    unittest.main()
