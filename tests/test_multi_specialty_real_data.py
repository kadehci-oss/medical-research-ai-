"""Multi-specialty fixtures ported from PR #33.

Sample size is read with the strict extractor. Abstracts that would only match
the loosened "N patients" pattern state n explicitly instead.
"""
import unittest
from unittest.mock import patch

from report_generator import (
    assess_risk_of_bias,
    classify_study_design,
    extract_article_clinical_details,
    extract_pico,
    extract_study_metrics,
)
from universal_evidence_engine import UniversalEvidenceEngine


class TestMultiSpecialtyFixtures(unittest.TestCase):
    def test_cardiology_rct_sample_size_and_effect(self):
        query = "Empagliflozin in patients with heart failure with preserved ejection fraction"
        art_rct = {
            "pmid": "34449189",
            "doi": "10.1056/nejmoa2107038",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "authors": ["Stefan D Anker", "Gerasimos Filippatos"],
            "journal": "N Engl J Med",
            "pub_year": "2021",
            "publication_types": ["Randomized Controlled Trial", "Journal Article"],
            "abstract": (
                "BACKGROUND: Empagliflozin reduced the risk of heart failure hospitalization in patients with HFpEF. "
                "METHODS: In a double-blind trial, patients with class II-IV heart failure and EF > 40% were randomized "
                "to empagliflozin (10 mg daily) or placebo (n = 5988). "
                "RESULTS: Over 26.2 months, a primary outcome was reported "
                "(HR 0.79; 95% CI 0.69 to 0.90; p < 0.001)."
            ),
        }
        engine = UniversalEvidenceEngine()
        processed = engine.process_and_extract_parameters([art_rct], query)
        self.assertEqual(len(processed), 1)
        row = processed[0]
        self.assertEqual(row["study_design"]["design"], "Rastgele Kontrollü Çalışma (RCT)")
        self.assertEqual(row["sample_size_n"], "5988")
        self.assertTrue(any("0.79" in es for es in row["effect_sizes"]))
        self.assertTrue(any("0.69" in ci for ci in row["confidence_intervals"]))

        cross_res = engine.compare_cross_article_findings([art_rct], query)
        self.assertEqual(cross_res["total_articles"], 1)
        self.assertEqual(cross_res["primary_study_count"], 1)

    def test_neurology_case_control_from_publication_type(self):
        art_cc = {
            "pmid": "29480216",
            "doi": "10.3233/jnd-170282",
            "title": "Anti-HMGCR Myopathy",
            "authors": ["Andrew L Mammen"],
            "journal": "J Neuromuscul Dis",
            "pub_year": "2018",
            "publication_types": ["Journal Article", "Case-Control Studies"],
            "abstract": (
                "Exposure histories were compared in anti-HMGCR positive myopathy (n = 150). "
                "Prior statin exposure was associated with disease onset "
                "(OR 5.4; 95% CI 3.1 to 9.2; p < 0.0001)."
            ),
        }
        design = classify_study_design(art_cc["publication_types"], art_cc["title"], art_cc["abstract"])
        self.assertEqual(design["design"], "Vaka-Kontrol Çalışması")

        metrics = extract_study_metrics(art_cc["abstract"])
        self.assertEqual(metrics["n"], "150")
        self.assertTrue(any("5.4" in es for es in metrics["effect_sizes"]))
        self.assertTrue(any("p < 0.0001" in pv or "p<0.0001" in pv for pv in metrics["p_values"]))

    def test_oncology_phase3_pico_and_sample_size(self):
        query = "Pembrolizumab versus chemotherapy in advanced non-small cell lung cancer"
        art_onc = {
            "pmid": "30345905",
            "doi": "10.1056/nejmoa1801005",
            "title": "Pembrolizumab plus Chemotherapy in Metastatic Non-Small-Cell Lung Cancer",
            "authors": ["Leena Gandhi", "Delvys Rodriguez-Abreu"],
            "journal": "N Engl J Med",
            "pub_year": "2018",
            "publication_types": ["Clinical Trial, Phase III", "Randomized Controlled Trial"],
            "abstract": (
                "METHODS: A total of 616 patients with metastatic non-squamous NSCLC were randomized "
                "to pembrolizumab or placebo with chemotherapy. "
                "RESULTS: Overall survival differed between groups (HR 0.49; 95% CI 0.38 to 0.64; p < 0.001)."
            ),
        }
        pico = extract_pico(query)
        self.assertIn("pembrolizumab", pico["intervention"].lower())
        self.assertIn("chemotherapy", pico["comparison"].lower())

        details = extract_article_clinical_details(art_onc, query)
        self.assertEqual(details["sample_size"], "n = 616")
        self.assertTrue("HR 0.49" in details["outcomes_summary"] or "Overall Survival" in details["outcomes_summary"])

    def test_ent_guideline_is_not_pooled_with_rct(self):
        query = "Dupilumab in patients with chronic rhinosinusitis with nasal polyps"
        art_guideline = {
            "pmid": "31960990",
            "doi": "10.1111/rhin.20.001",
            "title": "European Position Paper on Rhinosinusitis and Nasal Polyps 2020",
            "authors": ["W J Fokkens", "V J Lund"],
            "journal": "Rhinology",
            "pub_year": "2020",
            "publication_types": ["Practice Guideline", "Consensus Development Conference"],
            "abstract": "This EPOS 2020 guideline summarizes evidence-based management of rhinosinusitis.",
        }
        art_rct = {
            "pmid": "31543078",
            "doi": "10.1016/s0140-6736(19)31881-1",
            "title": "Efficacy and safety of dupilumab in patients with severe chronic rhinosinusitis with nasal polyps",
            "authors": ["Claus Bachert", "Leda P Mannent"],
            "journal": "Lancet",
            "pub_year": "2019",
            "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
            "abstract": (
                "Two trials enrolled 724 adult patients with severe CRSwNP. "
                "Dupilumab reduced nasal polyp score (MD -1.89; 95% CI -2.19 to -1.59; p < 0.0001)."
            ),
        }
        comp = UniversalEvidenceEngine().compare_cross_article_findings([art_guideline, art_rct], query)
        self.assertEqual(comp["total_articles"], 2)
        self.assertEqual(comp["primary_study_count"], 1)
        self.assertEqual(comp["review_study_count"], 1)
        self.assertGreaterEqual(len(comp["non_comparable_studies"]), 1)

    def test_rheumatology_rct_bias_tool_not_assessed(self):
        art_rheum = {
            "pmid": "23746811",
            "doi": "10.1016/s0140-6736(13)60833-3",
            "title": "Tocilizumab monotherapy versus methotrexate monotherapy in rheumatoid arthritis",
            "authors": ["Josef S Smolen"],
            "journal": "Lancet",
            "pub_year": "2013",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": (
                "In a double-blind trial, 321 patients with active rheumatoid arthritis were randomized. "
                "ACR20 response differed (OR 2.3; 95% CI 1.4 to 3.8; p = 0.001)."
            ),
        }
        rob = assess_risk_of_bias(art_rheum)
        self.assertEqual(rob["tool"], "RoB 2 (Cochrane Risk of Bias for RCTs)")
        self.assertEqual(rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")

    def test_endocrinology_semaglutide_mean_difference(self):
        art_endo = {
            "pmid": "28818818",
            "doi": "10.1016/s2213-8587(17)30217-9",
            "title": "Efficacy and safety of once-weekly semaglutide in type 2 diabetes",
            "authors": ["Richard M Bergenstal"],
            "journal": "Lancet Diabetes Endocrinol",
            "pub_year": "2017",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": (
                "A total of 813 patients with type 2 diabetes were randomized to once-weekly semaglutide or sitagliptin. "
                "Semaglutide reduced HbA1c (MD -1.4%; 95% CI -1.6 to -1.2; p < 0.0001)."
            ),
        }
        metrics = extract_study_metrics(art_endo["abstract"])
        self.assertEqual(metrics["n"], "813")
        self.assertTrue(any("MD" in es and "-1.4" in es for es in metrics["effect_sizes"]))

    @patch("report_generator.verify_citation")
    def test_infectious_disease_report_states_physician_review_not_done(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        query = "Nirmatrelvir plus ritonavir in patients with non-hospitalized COVID-19"
        art_id = {
            "pmid": "35172054",
            "doi": "10.1056/nejmoa2118542",
            "title": "Oral Nirmatrelvir for Unvaccinated Outpatients with Covid-19",
            "authors": ["Jennifer Hammond", "Hanna Leister-Tebbe"],
            "journal": "N Engl J Med",
            "pub_year": "2022",
            "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
            "abstract": (
                "Unvaccinated, non-hospitalized adults with symptomatic Covid-19 (n = 2246) were assigned "
                "to nirmatrelvir plus ritonavir or placebo. "
                "Hospitalization or death by day 28 differed (HR 0.12; 95% CI 0.06 to 0.24; p < 0.001)."
            ),
        }
        report = UniversalEvidenceEngine().generate_synthesis_report(query, [art_id])
        self.assertEqual(report["status"], "success")
        markdown = report["report_markdown"]
        self.assertIn("# 📑 Türkçe Klinik Araştırma Raporu", markdown)
        self.assertIn("## 1. Klinik Araştırma Sorusu", markdown)
        self.assertIn("## 12. Klinik Sonuç", markdown)
        self.assertIn("## 13. Doğrulanmış Kaynakça", markdown)
        self.assertIn("Uzman Hekim Değerlendirmesi: Yapılmadı", markdown)
        self.assertEqual(
            report["audit"]["clinical_validation_status"],
            "Klinik Doğrulama Yapılmamıştır (No Clinical Validation Claimed)",
        )
        self.assertEqual(report["audit"]["expert_physician_review"], "Yapılmadı")
        self.assertTrue(report["quality_control"]["valid"], report["quality_control"])


if __name__ == "__main__":
    unittest.main()
