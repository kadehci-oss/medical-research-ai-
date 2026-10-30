import unittest
from report_generator import (
    generate_rule_based_turkish_report,
    extract_article_clinical_details,
    extract_outcome_metrics,
    classify_study_design,
    perform_red_team_audit
)

STATIN_MYOPATHY_ARTICLES = [
    {
        "pmid": "37884200",
        "doi": "10.1016/j.autrev.2023.103468",
        "title": "Anti-HMGCR immune-mediated necrotising myopathy: Addressing the remaining issues",
        "authors": ["Thomas Khoo", "Hector Chinoy"],
        "journal": "Autoimmunity reviews",
        "pub_year": "2023",
        "publication_types": ["Journal Article", "Review"],
        "abstract": "The discovery of autoantibodies directed against HMGCR enzyme has defined a sub-set of immune-mediated necrotising myopathy strongly associated with statins.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/37884200/",
        "doi_url": "https://doi.org/10.1016/j.autrev.2023.103468"
    },
    {
        "pmid": "31234567",
        "doi": "10.1001/jamaneurol.2019.1234",
        "title": "Risk Factors and Clinical Outcomes in Anti-HMGCR Myopathy",
        "authors": ["Lisa Christopher-Stine", "Andrew L Mammen"],
        "journal": "JAMA Neurology",
        "pub_year": "2020",
        "publication_types": ["Observational Study", "Cohort Studies"],
        "abstract": "In a cohort of 180 patients with statin-associated autoimmune myopathy (n=180), immunosuppressive therapy with corticosteroids and IVIG achieved clinical remission in 72% of cases (OR 3.20, 95% CI 1.80-5.60, p<0.001). However, causality cannot be proven due to the observational nature of the cohort.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31234567/",
        "doi_url": "https://doi.org/10.1001/jamaneurol.2019.1234"
    },
    {
        "pmid": "28765432",
        "doi": "10.1002/art.40123",
        "title": "Coenzyme Q10 Supplementation in Statin-Associated Muscle Symptoms: A Randomized Trial",
        "authors": ["Robert E Smith", "Karen L Davis"],
        "journal": "Arthritis & Rheumatology",
        "pub_year": "2018",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": "In a randomized trial with 120 patients (n=120) comparing CoQ10 vs placebo, CoQ10 failed to show statistically significant reduction in muscle pain scores (p=0.42) or CK elevation.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/28765432/",
        "doi_url": "https://doi.org/10.1002/art.40123"
    }
]


class TestStatinMyopathyRegression(unittest.TestCase):

    def test_statin_myopathy_article_extraction(self):
        art_rct = STATIN_MYOPATHY_ARTICLES[2]
        details = extract_article_clinical_details(art_rct, "CoQ10 in statin myopathy")

        self.assertEqual(details["sample_size"], "n = 120")
        self.assertIn("Rastgele Kontrollü", details["study_design"])
        self.assertEqual(details["evidence_level"], "Değerlendirilemedi")
        self.assertIn("Placebo", details["comparison"])

        om = details["outcome_metrics"]
        self.assertTrue(len(om) > 0)
        self.assertIn("p=0.42", om[0]["metrics"])

    def test_statin_myopathy_study_design_classification(self):
        rev = classify_study_design(STATIN_MYOPATHY_ARTICLES[0]["publication_types"], STATIN_MYOPATHY_ARTICLES[0]["title"], STATIN_MYOPATHY_ARTICLES[0]["abstract"])
        self.assertEqual(rev["level"], "Değerlendirilemedi")
        self.assertIn("Derleme", rev["design"])

        obs = classify_study_design(STATIN_MYOPATHY_ARTICLES[1]["publication_types"], STATIN_MYOPATHY_ARTICLES[1]["title"], STATIN_MYOPATHY_ARTICLES[1]["abstract"])
        self.assertEqual(obs["level"], "Değerlendirilemedi")
        self.assertIn("Gözlemsel", obs["design"])

        rct = classify_study_design(STATIN_MYOPATHY_ARTICLES[2]["publication_types"], STATIN_MYOPATHY_ARTICLES[2]["title"], STATIN_MYOPATHY_ARTICLES[2]["abstract"])
        self.assertEqual(rct["level"], "Değerlendirilemedi")
        self.assertIn("Rastgele Kontrollü", rct["design"])

    def test_statin_myopathy_report_section_12_synthesis(self):
        query = "Statin-associated autoimmune myopathy and anti-HMGCR antibodies"
        report = generate_rule_based_turkish_report(query, STATIN_MYOPATHY_ARTICLES)

        self.assertIn("## 12. Klinik Sonuç", report)
        sec_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # Verify 4 synthesis subsections exist
        self.assertIn("### 🎯 Ortak Klinik Bulgular ve Sentez", sec_12)
        self.assertIn("### ⚠️ Çelişkili Bulgular ve Heterojenlikler", sec_12)
        self.assertIn("### 🩺 Klinik Önem ve Uygulanabilirlik", sec_12)
        self.assertIn("### 🔬 Kanıt Sınırlılıkları ve Metodolojik Engeller", sec_12)

        # Verify PMID citations exist in Section 12
        self.assertIn("[PMID: 37884200]", sec_12)
        self.assertIn("[PMID: 31234567]", sec_12)
        self.assertIn("[PMID: 28765432]", sec_12)

        # Verify no ungrounded claims for review paper
        self.assertIn("kesin tedavi etkinliği çıkarılmamıştır", sec_12)

        # Verify extracted metrics are included
        self.assertIn("n = 180", sec_12)
        self.assertIn("OR 3.20", sec_12)
        self.assertIn("p=0.42", sec_12)

    def test_statin_myopathy_single_keyword_safeguard(self):
        review_art = STATIN_MYOPATHY_ARTICLES[0]
        details = extract_article_clinical_details(review_art, "statin myopathy")

        # Must not claim definitive efficacy from review without metrics
        self.assertNotIn("tedavinin klinik etkinlik sunduğu", details["real_findings"])
        self.assertIn("nicel istatistiksel parametre bildirilmemiştir", details["real_findings"])


if __name__ == "__main__":
    unittest.main()
