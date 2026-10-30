"""Offline regression: eight specialties and the nine requested study designs.

Real PubMed calls stay in test_live_pubmed_design_regression.py.
Streamlit behavior stays in test_streamlit_design_labels.py.
"""
import re
import unittest

from grade_assessment import assess_preliminary_grade
from report_generator import (
    assess_risk_of_bias,
    classify_study_design,
    extract_article_clinical_details,
    generate_rule_based_turkish_report,
)

_RISK_DEGREE = re.compile(
    r"\b(low risk|high risk|some concerns|moderate risk|düşük risk|yüksek risk|orta risk)\b",
    re.IGNORECASE,
)


def _article(pmid, title, pub_types, abstract, authors=None):
    return {
        "pmid": pmid,
        "title": title,
        "authors": authors or ["Ada Lovelace", "Grace Hopper", "Katherine Johnson"],
        "journal": "Test Journal",
        "pub_year": "2024",
        "publication_types": pub_types,
        "abstract": abstract,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


# Eight specialties. Case series is asserted separately so olgu sunumu and
# olgu serisi are not collapsed into one label.
SPECIALTIES = [
    {
        "specialty": "Kardiyoloji",
        "query": "Empagliflozin in heart failure",
        "design_key": "rct",
        "design": "Rastgele Kontrollü Çalışma (RCT)",
        "tool": "RoB 2 (Cochrane Risk of Bias for RCTs)",
        "article": _article(
            "90000001",
            "Empagliflozin in heart failure with preserved ejection fraction",
            ["Randomized Controlled Trial", "Journal Article"],
            "In this double-blind randomized trial, 5988 patients with heart failure were randomized "
            "to empagliflozin or placebo (n = 5988). Empagliflozin reduced heart failure hospitalization "
            "(HR 0.79, 95% CI 0.69-0.90, p<0.001).",
        ),
        "named_outcome": True,
    },
    {
        "specialty": "Nöroloji",
        "query": "Levetiracetam in epilepsy",
        "design_key": "cohort",
        "design": "Kohort Çalışması (Gözlemsel)",
        "tool": "ROBINS-I (Risk of Bias in Non-Randomized Studies)",
        "article": _article(
            "90000002",
            "Levetiracetam treatment in a prospective cohort of epilepsy",
            ["Observational Study", "Cohort Studies"],
            "We followed a prospective cohort of 640 patients with epilepsy treated with levetiracetam (n = 640). "
            "Seizure freedom was higher than with the prior regimen (OR 1.80, 95% CI 1.20-2.70, p=0.004).",
        ),
        "named_outcome": True,
    },
    {
        "specialty": "Onkoloji",
        "query": "Immunotherapy in melanoma",
        "design_key": "meta_analysis",
        "design": "Meta-Analiz",
        "tool": "ROBIS (Risk of Bias in Systematic Reviews)",
        "article": _article(
            "90000003",
            "Meta-analysis of immunotherapy for advanced melanoma",
            ["Meta-Analysis", "Journal Article"],
            "This meta-analysis pooled randomized trials. Overall survival favored immunotherapy "
            "(HR 0.72, 95% CI 0.61-0.85). I2 = 30%.",
        ),
        "named_outcome": True,
    },
    {
        "specialty": "Göğüs hastalıkları",
        "query": "Inhaled corticosteroid in COPD",
        "design_key": "systematic_review",
        "design": "Sistematik Derleme",
        "tool": "ROBIS (Risk of Bias in Systematic Reviews)",
        "article": _article(
            "90000004",
            "Inhaled corticosteroids for COPD: a systematic review",
            ["Systematic Review"],
            "We conducted a systematic review of randomized trials in COPD. Exacerbation results were narratively summarized.",
        ),
        "named_outcome": False,
    },
    {
        "specialty": "Endokrinoloji",
        "query": "Vitamin D in type 2 diabetes",
        "design_key": "cross_sectional",
        "design": "Kesitsel Çalışma",
        "tool": "AXIS (Kesitsel Çalışmalar)",
        "article": _article(
            "90000005",
            "Cross-sectional study of vitamin D and HbA1c",
            ["Journal Article"],
            "This cross-sectional study included 900 adults with type 2 diabetes (n = 900). "
            "HbA1c was higher in the low vitamin D group (MD 0.40, 95% CI 0.10-0.70, p=0.02).",
        ),
        "named_outcome": True,
    },
    {
        "specialty": "Enfeksiyon hastalıkları",
        "query": "Prior antibiotic exposure and resistant infection",
        "design_key": "case_control",
        "design": "Vaka-Kontrol Çalışması",
        "tool": "Newcastle-Ottawa Scale (NOS)",
        "article": _article(
            "90000006",
            "Prior antibiotic exposure and drug-resistant infection: a case-control study",
            ["Case-Control Studies"],
            "In this case-control study, exposure histories were compared (n = 220). "
            "Prior antibiotic exposure was associated with a higher infection rate (OR 2.4, 95% CI 1.5-3.8, p=0.001).",
        ),
        "named_outcome": True,
    },
    {
        "specialty": "Romatoloji",
        "query": "Tofacitinib and a rare adverse event",
        "design_key": "case_report",
        "design": "Olgu Sunumu",
        "tool": "JBI Olgu Sunumu Değerlendirme Listesi",
        "article": _article(
            "90000007",
            "Tofacitinib and opportunistic infection: a case report",
            ["Case Reports"],
            "We report a case of opportunistic infection after tofacitinib. No comparative statistic was calculated.",
        ),
        "named_outcome": False,
    },
    {
        "specialty": "Kulak burun boğaz",
        "query": "Chronic rhinosinusitis management",
        "design_key": "guideline",
        "design": "Klinik Kılavuz",
        "tool": "AGREE II (Klinik Kılavuz)",
        "article": _article(
            "90000008",
            "Clinical practice guideline for chronic rhinosinusitis",
            ["Practice Guideline"],
            "This clinical practice guideline summarizes management of chronic rhinosinusitis. No new trial statistic is reported.",
        ),
        "named_outcome": False,
    },
]


class TestEightSpecialtyDesignRegression(unittest.TestCase):
    def test_eight_specialties_keep_design_grade_and_bias_rules(self):
        self.assertEqual(len(SPECIALTIES), 8)
        specialties = [item["specialty"] for item in SPECIALTIES]
        self.assertEqual(len(set(specialties)), 8)

        for item in SPECIALTIES:
            article = item["article"]
            design = classify_study_design(
                article["publication_types"], article["title"], article["abstract"]
            )
            self.assertEqual(design["design_key"], item["design_key"], item["specialty"])
            self.assertEqual(design["design"], item["design"], item["specialty"])
            self.assertEqual(design["level"], "Değerlendirilemedi", item["specialty"])
            self.assertIsNone(design["level_num"], item["specialty"])
            self.assertNotIn("Seviye", design["level"])

            rob = assess_risk_of_bias(article)
            self.assertEqual(rob["tool"], item["tool"], item["specialty"])
            self.assertEqual(rob["overall_rating"], "Değerlendirilmedi (Not Assessed)", item["specialty"])
            self.assertFalse(rob["risk_assigned"], item["specialty"])
            self.assertIsNone(_RISK_DEGREE.search(rob["overall_rating"]))
            for domain_value in rob["domains"].values():
                self.assertIsNone(_RISK_DEGREE.search(domain_value), item["specialty"])

            details = extract_article_clinical_details(article, item["query"])
            self.assertEqual(details["evidence_level"], "Değerlendirilemedi", item["specialty"])
            provenance = details["provenance"]
            self.assertEqual(provenance["pmid"], article["pmid"])
            if "n = " in article["abstract"]:
                self.assertIn(article["pmid"], provenance["sample_size"]["pmid"] or article["pmid"])
                self.assertIn(details["sample_size"].replace(" ", ""), provenance["sample_size"]["source_sentence"].replace(" ", ""))
            for outcome in provenance["outcomes"]:
                self.assertEqual(outcome["pmid"], article["pmid"])
                self.assertTrue(outcome["source_sentence"])
                for metric in outcome["metrics"]:
                    token = metric.split()[-1]
                    self.assertIn(token, outcome["source_sentence"])

            grade = assess_preliminary_grade(article, item["query"])
            self.assertEqual(grade["formal_grade_status"], "GRADE Değerlendirilmedi (Not Assessed)")
            self.assertTrue(grade["outcomes"])
            if item["named_outcome"]:
                named = [row for row in grade["outcomes"] if row["identified"]]
                self.assertTrue(named, item["specialty"])
                for row in named:
                    self.assertTrue(row["source_sentence"], item["specialty"])
                    self.assertIn(article["pmid"], row["pmid"])
            else:
                self.assertEqual(grade["preliminary_level"], "değerlendirilemedi", item["specialty"])
                self.assertTrue(all(row["preliminary_level"] == "değerlendirilemedi" for row in grade["outcomes"]))

            report = generate_rule_based_turkish_report(item["query"], [article])
            self.assertIn(f"PMID: {article['pmid']}", report)
            self.assertIn("Kaynak cümle", report)
            self.assertIn("Değerlendirilemedi", report)
            self.assertNotIn("Seviye 1", report)
            self.assertNotIn("Seviye 2", report)
            self.assertNotIn("imprezisyon", report.lower())
            self.assertNotIn(" et al. et al.", report)
            self.assertIn(item["design"], report)

    def test_case_series_is_not_labeled_as_a_case_report(self):
        series = _article(
            "90000009",
            "Dupilumab for nasal polyps: a case series",
            ["Case Reports", "Journal Article"],
            "This case series describes 12 consecutive patients with nasal polyps (n = 12). Nasal polyp score fell in 9 patients.",
        )
        report_only = _article(
            "90000010",
            "Nasal polyp recurrence: a case report",
            ["Case Reports"],
            "We present a case report of nasal polyp recurrence after surgery.",
        )
        series_design = classify_study_design(series["publication_types"], series["title"], series["abstract"])
        report_design = classify_study_design(report_only["publication_types"], report_only["title"], report_only["abstract"])
        self.assertEqual(series_design["design_key"], "case_series")
        self.assertEqual(series_design["design"], "Olgu Serisi")
        self.assertEqual(report_design["design_key"], "case_report")
        self.assertEqual(report_design["design"], "Olgu Sunumu")
        self.assertEqual(series_design["level"], "Değerlendirilemedi")
        self.assertEqual(report_design["level"], "Değerlendirilemedi")

        series_rob = assess_risk_of_bias(series)
        report_rob = assess_risk_of_bias(report_only)
        self.assertEqual(series_rob["tool"], "JBI Olgu Serisi Değerlendirme Listesi")
        self.assertEqual(report_rob["tool"], "JBI Olgu Sunumu Değerlendirme Listesi")
        self.assertEqual(series_rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(report_rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")

        grade = assess_preliminary_grade(series, "nasal polyps")
        self.assertEqual(grade["preliminary_level"], "değerlendirilemedi")

    def test_nonrandomized_title_is_not_an_rct(self):
        design = classify_study_design(
            [],
            "Non-randomized study of an exercise program",
            "Participants were followed for 12 months.",
        )
        self.assertNotEqual(design["design_key"], "rct")
        self.assertEqual(design["level"], "Değerlendirilemedi")

    def test_background_systematic_review_does_not_override_cohort(self):
        design = classify_study_design(
            [],
            "Blood pressure trends in a community cohort",
            "A systematic review was previously conducted. In our cohort of 400 adults, blood pressure was recorded.",
        )
        self.assertEqual(design["design_key"], "cohort")


if __name__ == "__main__":
    unittest.main()
