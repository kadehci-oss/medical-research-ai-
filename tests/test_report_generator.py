import unittest
from report_generator import (
    generate_rule_based_turkish_report,
    generate_turkish_evidence_report,
    _classify_evidence_level
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

    def test_classify_evidence_level(self):
        level_rct = _classify_evidence_level(["Randomized Controlled Trial"], "Title", "Abstract")
        self.assertIn("Seviye 2", level_rct)

        level_sr = _classify_evidence_level(["Systematic Review"], "Meta-analysis of trial data", "Abstract")
        self.assertIn("Seviye 1", level_sr)

    def test_generate_rule_based_turkish_report(self):
        query = "SGLT2 inhibitors in heart failure"
        report = generate_rule_based_turkish_report(query, SAMPLE_ARTICLES)

        # Check required sections
        self.assertIn("Türkçe Kanıt Raporu", report)
        self.assertIn("1. 🔍 Klinik Özet ve Sentez", report)
        self.assertIn("2. 📊 Kanıt Seviyeleri ve Metodolojik Dağılım", report)
        self.assertIn("3. ⚠️ Klinik Uyarılar ve Sınırlılıklar", report)
        self.assertIn("4. 📚 Doğrulanmış Kaynaklar ve Literatür Listesi", report)

        # Anti-hallucination check: ensure real PMIDs are present in the references
        self.assertIn("PMID: [33264510]", report)
        self.assertIn("PMID: [31535829]", report)
        self.assertIn("Empagliflozin in Heart Failure", report)

    def test_generate_report_empty_articles(self):
        query = "Unknown condition xyz"
        report = generate_rule_based_turkish_report(query, [])
        self.assertIn("Sonuç Bulunamadı", report)

    def test_generate_turkish_evidence_report_fallback(self):
        # Even without LLM key, default generator should return valid Turkish report
        report = generate_turkish_evidence_report("SGLT2 inhibitors", SAMPLE_ARTICLES, api_key=None, use_llm=False)
        self.assertIn("Türkçe Kanıt Raporu", report)
        self.assertIn("33264510", report)


if __name__ == "__main__":
    unittest.main()
