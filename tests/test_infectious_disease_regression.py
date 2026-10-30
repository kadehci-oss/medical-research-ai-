import unittest
from report_generator import (
    generate_rule_based_turkish_report,
    extract_article_clinical_details,
    extract_outcome_metrics,
    classify_study_design
)

INFECTIOUS_DISEASE_ARTICLES = [
    {
        "pmid": "38123456",
        "doi": "10.1093/cid/ciad100",
        "title": "Early Antiviral Therapy in Hospitalized Severe Influenza: A Randomized Controlled Trial",
        "authors": ["G. Taylor", "H. Anderson", "M. White"],
        "journal": "Clinical Infectious Diseases",
        "pub_year": "2024",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": "In a randomized trial with 520 patients hospitalized with severe influenza (n=520), early antiviral therapy reduced ICU admission (OR 0.55, 95% CI 0.38-0.79, p=0.001) compared to standard care.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/38123456/",
        "doi_url": "https://doi.org/10.1093/cid/ciad100"
    },
    {
        "pmid": "37654321",
        "doi": "10.1016/S1473-3099(23)00200-1",
        "title": "Adjunctive Corticosteroids in Severe Community-Acquired Pneumonia: A Systematic Review and Meta-Analysis",
        "authors": ["L. Martin", "K. Thompson"],
        "journal": "The Lancet Infectious Diseases",
        "pub_year": "2023",
        "publication_types": ["Systematic Review", "Meta-Analysis"],
        "abstract": "We performed a systematic review and meta-analysis of 14 RCTs (n=3100). Adjunctive corticosteroid therapy reduced 28-day mortality in severe CAP (RR 0.67, 95% CI 0.52-0.86, p=0.002), but did not reduce length of stay in non-severe cases.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/37654321/",
        "doi_url": "https://doi.org/10.1016/S1473-3099(23)00200-1"
    },
    {
        "pmid": "36543210",
        "doi": "10.1007/s15010-022-01800-x",
        "title": "Impact of Antibiotic Stewardship Intervention on Multidrug-Resistant Bacterial Infections",
        "authors": ["J. Miller", "S. Garcia"],
        "journal": "Infection",
        "pub_year": "2022",
        "publication_types": ["Observational Study", "Comparative Study"],
        "abstract": "In an observational cohort of 650 patients (n=650), antimicrobial stewardship implementation did not show statistically significant reduction in 30-day mortality (p=0.28). However, broad-spectrum antibiotic duration was significantly shortened.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/36543210/",
        "doi_url": "https://doi.org/10.1007/s15010-022-01800-x"
    }
]


class TestInfectiousDiseaseRegression(unittest.TestCase):

    def test_infectious_disease_outcome_metric_binding(self):
        art_flu = INFECTIOUS_DISEASE_ARTICLES[0]
        outcome_metrics = extract_outcome_metrics(art_flu["abstract"])

        self.assertTrue(len(outcome_metrics) > 0)
        icu_om = outcome_metrics[0]
        self.assertIn("OR 0.55", icu_om["metrics"])
        self.assertIn("p=0.001", icu_om["metrics"])

    def test_infectious_disease_study_design_classification(self):
        rct = classify_study_design(INFECTIOUS_DISEASE_ARTICLES[0]["publication_types"], INFECTIOUS_DISEASE_ARTICLES[0]["title"], INFECTIOUS_DISEASE_ARTICLES[0]["abstract"])
        self.assertEqual(rct["level"], "Değerlendirilemedi")
        self.assertEqual(rct["design"], "Rastgele Kontrollü Çalışma (RCT)")

        meta = classify_study_design(INFECTIOUS_DISEASE_ARTICLES[1]["publication_types"], INFECTIOUS_DISEASE_ARTICLES[1]["title"], INFECTIOUS_DISEASE_ARTICLES[1]["abstract"])
        self.assertEqual(meta["level"], "Değerlendirilemedi")
        self.assertIn("Meta-Analiz", meta["design"])
        self.assertIn("Sistematik Derleme", meta["design"])

        obs = classify_study_design(INFECTIOUS_DISEASE_ARTICLES[2]["publication_types"], INFECTIOUS_DISEASE_ARTICLES[2]["title"], INFECTIOUS_DISEASE_ARTICLES[2]["abstract"])
        self.assertEqual(obs["level"], "Değerlendirilemedi")
        self.assertIn("Kohort", obs["design"])

    def test_infectious_disease_report_section_12_synthesis(self):
        query = "Antiviral and antibiotic stewardship in severe infections"
        report = generate_rule_based_turkish_report(query, INFECTIOUS_DISEASE_ARTICLES)

        self.assertIn("## 12. Klinik Sonuç", report)
        sec_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # Check 4 synthesis subsections
        self.assertIn("### 🎯 Ortak Klinik Bulgular ve Sentez", sec_12)
        self.assertIn("### ⚠️ Çelişkili Bulgular ve Heterojenlikler", sec_12)
        self.assertIn("### 🩺 Klinik Önem ve Uygulanabilirlik", sec_12)
        self.assertIn("### 🔬 Kanıt Sınırlılıkları ve Metodolojik Engeller", sec_12)

        # Check PMIDs
        self.assertIn("[PMID: 38123456]", sec_12)
        self.assertIn("[PMID: 37654321]", sec_12)
        self.assertIn("[PMID: 36543210]", sec_12)

        # Check extracted metrics present in synthesis
        self.assertIn("n = 520", sec_12)
        self.assertIn("OR 0.55", sec_12)
        self.assertIn("p=0.28", sec_12)


if __name__ == "__main__":
    unittest.main()
