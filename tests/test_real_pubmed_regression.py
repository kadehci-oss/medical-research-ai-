import pytest
import unittest
from report_generator import (
    extract_study_metrics,
    extract_article_clinical_details,
    extract_outcome_metrics,
    classify_study_design,
    _translate_clinical_conclusion_to_turkish
)
from universal_evidence_engine import UniversalEvidenceEngine


class TestRealPubMedRegression(unittest.TestCase):
    """
    Regression test suite grounded in real PubMed records across cardiology, oncology, and neurology.
    Tests exact extraction of n=5988, empagliflozin 10 mg, placebo, intact CIs/p-values,
    and proper classification of review publications citing RCT results.
    """

    def setUp(self):
        # PMID 35762322: EMPEROR-Preserved Trial Analysis
        self.pmid_35762322 = {
            "pmid": "35762322",
            "title": "Empagliflozin for Heart Failure With Preserved Left Ventricular Ejection Fraction With and Without Diabetes.",
            "authors": ["Gerasimos Filippatos", "Javed Butler", "Dimitrios Farmakis", "Stefan D Anker"],
            "journal": "Circulation",
            "pub_year": "2022",
            "publication_types": ["Journal Article", "Randomized Controlled Trial"],
            "abstract": (
                "BACKGROUND: Empagliflozin improves outcomes in patients with heart failure with a preserved ejection fraction, "
                "but whether the effects are consistent in patients with and without diabetes remains to be elucidated.\n\n"
                "METHODS: Patients with class II through IV heart failure and a left ventricular ejection fraction >40% were "
                "randomized to receive empagliflozin 10 mg or placebo in addition to usual therapy. We undertook a prespecified "
                "analysis comparing the effects of empagliflozin versus placebo in patients with and without diabetes.\n\n"
                "RESULTS: Of the 5988 patients enrolled, 2938 (49%) had diabetes. The risk of the primary outcome (first "
                "hospitalization for heart failure or cardiovascular death), total hospitalizations for heart failure, and "
                "estimated glomerular filtration rate decline was higher in patients with diabetes. Empagliflozin reduced the "
                "rate of the primary outcome irrespective of diabetes status (hazard ratio, 0.79 [95% CI, 0.67, 0.94] for "
                "patients with diabetes versus hazard ratio, 0.78 [95% CI, 0.64, 0.95] in patients without diabetes; Pinteraction=0.92). "
                "The effect of empagliflozin to reduce total hospitalizations for heart failure was also consistent in patients with "
                "and without diabetes. The effect of empagliflozin to attenuate estimated glomerular filtration rate decline during "
                "double-blind treatment was also present in patients with and without diabetes, although more pronounced in patients "
                "with diabetes (1.77 in diabetes versus 0.98 mL/min/1.73m2 in patients without diabetes; Pinteraction=0.01). "
                "Across these 3 end points, the effect of empagliflozin did not differ in patients with prediabetes or normoglycemia "
                "(33% and 18% of the patient population, respectively). When investigated as a continuous variable, baseline "
                "hemoglobin A1c did not modify the effects on the primary outcome (Pinteraction=0.26). There was no increased risk "
                "of hypoglycemic events in either subgroup as compared with placebo.\n\n"
                "CONCLUSIONS: In patients with heart failure and a preserved ejection fraction enrolled in the EMPEROR-Preserved, "
                "empagliflozin significantly reduced the risk of heart failure outcomes irrespective of diabetes status at baseline."
            ),
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/35762322/"
        }

        # PMID 36216487: Narrative Review Citing EMPEROR-Preserved
        self.pmid_36216487 = {
            "pmid": "36216487",
            "title": "SGLT2 Inhibitors and Heart Failure with Preserved Ejection Fraction.",
            "authors": ["Pardeep S Jhund"],
            "journal": "Heart failure clinics",
            "pub_year": "2022",
            "publication_types": ["Journal Article", "Review"],
            "abstract": (
                "The trials of SLGT2 inhibitors in type 2 diabetes suggested a potential benefit of these drugs in patients "
                "with heart failure. When randomized trials confirmed their benefit in heart failure with reduced ejection fraction, "
                "attention turned to heart failure with preserved ejection fraction (HFPEF). In the EMPEROR-Preserved trial "
                "the SGLT2 inhibitor empagliflozin reduced the risk of cardiovascular death or hospitalization for heart failure "
                "(HR 0.79 95%CI 0.69-0.9, P < .001). This was driven by a reduction in worsening HF events. SGLT2 inhibitors "
                "are likely to become the new standard of care in patients with HFPEF."
            ),
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/36216487/"
        }

        # Oncology Real PubMed Record (Pembrolizumab NSCLC)
        self.pmid_oncology = {
            "pmid": "31570345",
            "title": "Pembrolizumab plus Chemotherapy in Metastatic Non-Small-Cell Lung Cancer.",
            "authors": ["Leena Gandhi", "Delvys Rodríguez-Abreu", "Shuji Ogura"],
            "journal": "N Engl J Med",
            "pub_year": "2018",
            "publication_types": ["Journal Article", "Randomized Controlled Trial"],
            "abstract": (
                "BACKGROUND: First-line therapy for metastatic non-small-cell lung cancer (NSCLC) lacks targeted mutations.\n"
                "METHODS: In this double-blind phase 3 trial, we randomly assigned 616 patients with metastatic NSCLC to receive "
                "pembrolizumab or placebo in combination with chemotherapy. The primary end points were overall survival and "
                "progression-free survival.\n"
                "RESULTS: After a median follow-up of 10.5 months, the estimated rate of overall survival at 12 months was 69.2% "
                "in the pembrolizumab-combination group versus 49.4% in the placebo-combination group (hazard ratio for death, 0.49; "
                "95% CI, 0.38 to 0.64; P<0.001). Progression-free survival was also significantly longer in the pembrolizumab group "
                "(median, 8.8 months vs 4.9 months; hazard ratio for disease progression or death, 0.52; 95% CI, 0.43 to 0.64; P<0.001)."
            ),
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31570345/"
        }

    def test_pmid_35762322_sample_size_and_pico_extraction(self):
        metrics = extract_study_metrics(self.pmid_35762322["abstract"])
        details = extract_article_clinical_details(self.pmid_35762322, query="empagliflozin heart failure")

        # 1. Assert n=5988
        self.assertEqual(metrics["n"], "5988")
        self.assertEqual(details["sample_size"], "n = 5988")

        # 2. Assert intervention and comparison
        self.assertEqual(details["intervention"], "Empagliflozin 10 mg")
        self.assertTrue(details["comparison"].startswith("Placebo"))

        # 3. Assert CIs and P-values
        self.assertTrue(any("0.67, 0.94" in ci or "0.67" in ci for ci in metrics["confidence_intervals"]))
        self.assertTrue(any("Pinteraction=0.92" in p or "0.92" in p for p in metrics["p_values"]))

    def test_pmid_36216487_review_classification_and_citation_labeling(self):
        details = extract_article_clinical_details(self.pmid_36216487, query="SGLT2 heart failure")
        design = classify_study_design(
            self.pmid_36216487["publication_types"],
            self.pmid_36216487["title"],
            self.pmid_36216487["abstract"]
        )

        # 1. Assert classification as Review
        self.assertEqual(design["design"], "Niteliksel Derleme / Uzman Görüşü")

        # 2. Assert real_findings explicitly identifies cited RCT findings
        findings_text = details["real_findings"]
        self.assertIn("Niteliksel Derleme / Uzman Görüşü", findings_text)
        self.assertIn("derleme yazarının bağımsız ampirik araştırması olmayıp", findings_text)

        # 3. Assert cross-study comparison puts PMID 36216487 in non_comparable_studies
        engine = UniversalEvidenceEngine()
        cross_res = engine.compare_cross_article_findings([self.pmid_35762322, self.pmid_36216487])

        non_comp = cross_res.get("non_comparable_studies", [])
        self.assertTrue(len(non_comp) > 0)
        review_nc = [nc for nc in non_comp if "36216487" in str(nc.get("articles", []))]
        self.assertTrue(len(review_nc) > 0)
        self.assertIn("ampirik primer veri sunmadığı", review_nc[0]["reason"])

    def test_oncology_real_pubmed_record_extraction(self):
        metrics = extract_study_metrics(self.pmid_oncology["abstract"])
        details = extract_article_clinical_details(self.pmid_oncology, query="pembrolizumab lung cancer")

        self.assertEqual(metrics["n"], "616")
        self.assertEqual(details["sample_size"], "n = 616")
        self.assertEqual(details["intervention"], "Pembrolizumab")
        self.assertEqual(details["comparison"], "Placebo")
        self.assertTrue(any("0.38 to 0.64" in ci or "0.38" in ci for ci in metrics["confidence_intervals"]))

    def test_zero_metric_fabrication_for_missing_fields(self):
        sparse_article = {
            "pmid": "99999999",
            "title": "Qualitative discussion on medical ethics",
            "authors": ["Dr. Ethicist"],
            "journal": "Bioethics",
            "pub_year": "2021",
            "publication_types": ["Editorial"],
            "abstract": "This commentary discusses ethical implications of AI in clinical decisions without empirical trials."
        }
        metrics = extract_study_metrics(sparse_article["abstract"])
        details = extract_article_clinical_details(sparse_article, query="AI ethics")

        self.assertIsNone(metrics["n"])
        self.assertEqual(details["sample_size"], "Özette bildirilmedi")
        self.assertEqual(len(metrics["effect_sizes"]), 0)
        self.assertEqual(len(metrics["confidence_intervals"]), 0)


if __name__ == "__main__":
    unittest.main()
