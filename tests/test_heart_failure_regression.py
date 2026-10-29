import unittest
from report_generator import (
    generate_rule_based_turkish_report,
    extract_article_clinical_details,
    extract_outcome_metrics,
    classify_study_design,
    extract_study_metrics
)

HEART_FAILURE_ARTICLES = [
    {
        "pmid": "34449189",
        "doi": "10.1056/NEJMoa2107038",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker", "Javed Butler", "Gerasimos Filippatos"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2021",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": "In a trial of 5988 patients with heart failure and ejection fraction > 40% (n=5988), Empagliflozin reduced cardiovascular death or hospitalization for heart failure (HR 0.79, 95% CI 0.69-0.90, p<0.001) compared to placebo. All-cause mortality was not significantly lower (HR 1.00, 95% CI 0.87-1.15).",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/34449189/",
        "doi_url": "https://doi.org/10.1056/NEJMoa2107038"
    },
    {
        "pmid": "31535829",
        "doi": "10.1056/NEJMoa1911303",
        "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
        "authors": ["John J V McMurray", "Solomon D Solomon", "Inbar Nativi"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2019",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In 4744 patients with HFrEF (n=4744), Dapagliflozin reduced cardiovascular death (HR 0.82, 95% CI 0.69-0.98, p=0.03) and heart failure hospitalization (RR 0.70, 95% CI 0.59-0.83, p<0.001) compared to placebo.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31535829/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1911303"
    },
    {
        "pmid": "31475794",
        "doi": "10.1056/NEJMoa1908655",
        "title": "Angiotensin-Neprilysin Inhibition in Heart Failure with Preserved Ejection Fraction",
        "authors": ["Solomon D Solomon", "John J V McMurray", "Biykem Bozkurt"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2019",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In 4822 patients with HFpEF (n=4822), Sacubitril-valsartan did not significantly reduce heart failure hospitalization or CV death compared to valsartan alone (RR 0.87, 95% CI 0.75-1.01, p=0.06). Results showed heterogeneous treatment effects in subgroups by ejection fraction.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31475794/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1908655"
    }
]


class TestHeartFailureRegression(unittest.TestCase):

    def test_outcome_metric_binding_in_heart_failure(self):
        art = HEART_FAILURE_ARTICLES[1] # Dapagliflozin
        outcome_metrics = extract_outcome_metrics(art["abstract"])

        self.assertTrue(len(outcome_metrics) >= 2)

        # Check CV death outcome binding
        cv_death = next((om for om in outcome_metrics if "death" in om["outcome"].lower() or "cardiovascular" in om["outcome"].lower()), None)
        self.assertIsNotNone(cv_death)
        self.assertTrue(any("HR 0.82" in m for m in cv_death["metrics"]))
        self.assertTrue(any("p=0.03" in m for m in cv_death["metrics"]))

        # Check HF hospitalization outcome binding
        hf_hosp = next((om for om in outcome_metrics if "hospitalization" in om["outcome"].lower()), None)
        self.assertIsNotNone(hf_hosp)
        self.assertTrue(any("RR 0.70" in m for m in hf_hosp["metrics"]))

    def test_heart_failure_article_clinical_details(self):
        art = HEART_FAILURE_ARTICLES[0] # Empagliflozin
        details = extract_article_clinical_details(art, "Empagliflozin in heart failure with preserved ejection fraction")

        self.assertEqual(details["sample_size"], "n = 5988")
        self.assertIn("Seviye 2", details["study_design"])
        self.assertEqual(details["comparison"], "Placebo")
        self.assertIn("HR 0.79", details["outcomes_summary"])

    def test_heart_failure_report_section_12_synthesis(self):
        query = "SGLT2 inhibitors and ARNI in heart failure"
        report = generate_rule_based_turkish_report(query, HEART_FAILURE_ARTICLES)

        self.assertIn("## 12. Klinik Sonuç", report)
        sec_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # Check 4 synthesis subsections
        self.assertIn("### 🎯 Ortak Klinik Bulgular ve Sentez", sec_12)
        self.assertIn("### ⚠️ Çelişkili Bulgular ve Heterojenlikler", sec_12)
        self.assertIn("### 🩺 Klinik Önem ve Uygulanabilirlik", sec_12)
        self.assertIn("### 🔬 Kanıt Sınırlılıkları ve Metodolojik Engeller", sec_12)

        # Check all PMIDs cited
        self.assertIn("[PMID: 34449189]", sec_12)
        self.assertIn("[PMID: 31535829]", sec_12)
        self.assertIn("[PMID: 31475794]", sec_12)

        # Check sample sizes and metrics in narrative
        self.assertIn("n = 5988", sec_12)
        self.assertIn("HR 0.79", sec_12)
        self.assertIn("n = 4744", sec_12)


if __name__ == "__main__":
    unittest.main()
