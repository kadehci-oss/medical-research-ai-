"""Disease-agnostic regressions from the live PubMed audit.

The sentences are copied from retrieved abstracts. The engine does not
special-case a PMID; the same wording has to behave in any specialty.
"""
import unittest

from limitations_generator import generate_limitations
from report_generator import (
    classify_study_design,
    extract_article_clinical_details,
    extract_clinical_profile,
    extract_grounded_clinical_findings,
    extract_outcome_metrics,
)
from universal_evidence_engine import UniversalEvidenceEngine, enrich_record


# Kokura Memorial Hospital retrospective SGLT2 cohort. The introduction mentions
# randomized trials the patients were not in; the methods name this study.
_RETROSPECTIVE_NOT_AN_RCT = (
    "However, the efficacy and safety of SGLT2 inhibitors in elderly patients with poor "
    "general status, such as very low bodyweight or low nutritional status, who are not "
    "included in randomized controlled trials, has not yet been examined. "
    "METHODS AND RESULTS: In Kokura Memorial Hospital, a retrospective study was conducted "
    "on 1559 patients over 80 years old hospitalized for HF between 2018 and 2023. "
    "The cumulative 1 year incidence of the composite outcome was significantly higher in "
    "the non-SGLT2i group (47.3% vs. 31.6%, P < 0.01). "
    "SGLT2 inhibitors independently reduced the risk of heart failure hospitalization "
    "(adjusted HR: 0.69, 95% CI: 0.52-0.91, P < 0.01)."
)

# Pooled dupilumab trial analysis. "Six cases of" is an adverse-event subset,
# and "followed by a decline" is a time course, not follow-up of a cohort.
_TRIAL_POOL_NOT_A_SERIES = (
    "OBJECTIVE: To assess eosinophil counts across 11 dupilumab clinical trials. "
    "RESULTS: Counts rose at week 4, followed by a decline starting by week 24. "
    "Clinical symptoms associated with increased eosinophils were rare "
    "(seven of 4,666 dupilumab-treated patients, including six cases of "
    "eosinophilic granulomatosis with polyangiitis)."
)

_DUPILUMAB_RATIO = (
    "METHODS: Skin biopsy specimens and blood were evaluated from 54 patients randomized "
    "1:1 to weekly subcutaneous doses of 200 mg of dupilumab or placebo for 16 weeks. "
    "The trial measured systemic type 2 biomarkers of patients with atopic dermatitis."
)

_HMGCR_CONTRAST = (
    "RESULTS: IMNM vs IIM patients were older [61.6 years (s.d. 9.8) vs 39.8 (14.3)], "
    "creatine kinase [CK; 11 780 IU (s.d. 7064) vs 1707 (1658)], "
    "anti-3-hydroxy-3-methylglutaryl coenzyme A reductase (HMGCR) antibodies "
    "(85.7% vs 11.1%) and necrotizing IM (81.8% vs 11.1%), but shorter disease duration "
    "[26.2 months (s.d. 395) vs 78.4 (47.9)], cutaneous manifestations (0% vs 55.6%), "
    "or any autoantibody (18.2% vs 88.9%) (all P < 0.05). "
    "IMNM vs IIM was treated more with IVIG (72.7% vs 11.1%; P = 0.009) and less with "
    "antimetabolites (45.5% vs 88.9%; P = 0.05) and rituximab (18.2% vs 55.6%; P = 0.09)."
)

# Lancet-style middle dot as the decimal mark.
_MIDDLE_DOT_EFFECT = (
    "Second-line immunotherapy resulted in a better outcome than those who did not "
    "(odds ratio [OR] 2·69, CI 1·24-5·80; p=0·012)."
)


def _article(title, abstract, pub_types=None):
    return {
        "pmid": "90009999",
        "title": title,
        "authors": ["Deneme Yazar"],
        "journal": "Test Journal",
        "pub_year": "2024",
        "publication_types": pub_types or ["Journal Article"],
        "abstract": abstract,
        "doi": "",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/90009999/",
    }


class TestDesignDoesNotBorrowACitedTrial(unittest.TestCase):
    def test_retrospective_study_is_not_an_rct_because_the_introduction_mentions_trials(self):
        design = classify_study_design(
            ["Journal Article"],
            "Efficacy and safety of SGLT2 inhibitors in patients aged over 80 years with heart failure",
            _RETROSPECTIVE_NOT_AN_RCT,
        )
        self.assertEqual(design["design_key"], "retrospective_comparative")
        self.assertEqual(design["level"], "Değerlendirilemedi")

    def test_an_explicit_randomized_trial_is_still_an_rct(self):
        design = classify_study_design(
            ["Journal Article"],
            "Drug A for migraine",
            "This randomized, double-blind trial assigned 400 adults. Patients were randomized to drug A or placebo.",
        )
        self.assertEqual(design["design_key"], "rct")

    def test_adverse_event_cases_and_followed_by_are_not_a_case_series_or_cohort(self):
        design = classify_study_design(
            ["Journal Article"],
            "Effect of dupilumab on blood eosinophil counts",
            _TRIAL_POOL_NOT_A_SERIES,
        )
        self.assertNotIn(design["design_key"], {"case_series", "case_report", "cohort", "rct"})

    def test_a_title_that_is_three_cases_stays_a_case_series(self):
        design = classify_study_design(
            ["Review"],
            "Three cases of statin myopathy",
            "The patients were treated with corticosteroids.",
        )
        self.assertEqual(design["design_key"], "case_series")


class TestSampleSizeAndArms(unittest.TestCase):
    def test_allocation_ratio_and_type_2_biomarkers_are_not_the_sample_size(self):
        article = _article("Dupilumab in atopic dermatitis", _DUPILUMAB_RATIO, ["Randomized Controlled Trial"])
        details = extract_article_clinical_details(article, "dupilumab atopic dermatitis")
        self.assertEqual(details["sample_size"], "n = 54")
        self.assertIn("200 mg", details["intervention"])
        self.assertNotIn("1:1", details["intervention"])
        self.assertEqual(details["comparison"], "Plasebo")
        sample_lines = [
            item["line"] for item in extract_clinical_profile(article["abstract"])
            if item["category"] == "sample"
        ]
        self.assertTrue(any("54 hasta" in line for line in sample_lines))
        self.assertFalse(any(line.startswith("Örneklem ve hasta özellikleri: 2 hasta") for line in sample_lines))


class TestOutcomeNamesAndDecimals(unittest.TestCase):
    def test_parenthetical_antibody_name_keeps_anti_and_turkish_compounds(self):
        article = _article(
            "Statin-associated immune-mediated necrotizing myositis in Native Americans",
            _HMGCR_CONTRAST,
        )
        details = extract_article_clinical_details(article, "statin-associated myopathy")
        names = {item["outcome"] for item in details["outcome_metrics"]}
        self.assertIn("anti-HMGCR antikorlar", names)
        self.assertNotIn("(HMGCR) antikorlar", names)
        self.assertIn("daha kısa hastalık süresi", names)
        self.assertIn("deri bulguları", names)
        self.assertIn("nekrotizan IM", names)
        self.assertIn("herhangi bir otoantikor", names)
        self.assertIn("rituksimab", names)
        self.assertIn("antimetabolitler", names)
        self.assertNotIn("Sonlanım adı güvenle çevrilemedi", names)

    def test_middle_dot_decimals_stay_attached_to_the_effect(self):
        findings = extract_grounded_clinical_findings(_MIDDLE_DOT_EFFECT)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["effect"], "odds ratio 2.69")
        self.assertEqual(findings[0]["ci"], "1.24 ile 5.80")
        self.assertEqual(findings[0]["p"], "p = 0.012")
        self.assertNotEqual(findings[0]["outcome"], "değil")


class TestUngroundedLimitationsAndSharedOutcomes(unittest.TestCase):
    def test_limitations_do_not_invent_geography_rob_or_funnel_plots(self):
        text = generate_limitations(
            [{"study_design_info": {"design": "Kohort Çalışması (Gözlemsel)"}, "abstract": "A cohort of adults."}],
            "metformin cardiovascular outcomes",
            1404,
        )
        self.assertIn("1404", text)
        self.assertIn("Tam metin değerlendirmesi yapılmadı", text)
        self.assertIn("Uzman hekim değerlendirmesi yapılmamıştır", text)
        self.assertNotIn("Türkiye", text)
        self.assertNotIn("funnel", text.lower())
        self.assertNotIn("Egger", text)
        self.assertNotIn("RoB 2", text)
        self.assertNotIn("0/", text)

    def test_enrich_record_does_not_stamp_low_risk_or_a_design_grade(self):
        record = enrich_record({
            "abstract": _RETROSPECTIVE_NOT_AN_RCT,
            "publication_types": ["Journal Article"],
            "study_design_info": {"design_key": "retrospective_comparative", "design": "Retrospektif"},
        })
        self.assertIsNone(record["rob2"])
        self.assertEqual(record["grade"]["final"], "Değerlendirilemedi")

    def test_identical_unnamed_outcomes_are_not_called_the_same_result(self):
        engine = UniversalEvidenceEngine()
        first = _article(
            "Drug A in migraine",
            "In 80 patients with migraine, treatment lowered scores (p=0.03).",
            ["Journal Article"],
        )
        second = _article(
            "Drug A in migraine",
            "In 90 patients with migraine, treatment lowered scores (p=0.04).",
            ["Journal Article"],
        )
        first["pmid"] = "90010001"
        second["pmid"] = "90010002"
        compared = engine.compare_cross_article_findings([first, second], "migraine treatment")
        self.assertEqual(compared["consistent_findings"], [])
        self.assertEqual(compared["conflicting_findings"], [])


if __name__ == "__main__":
    unittest.main()
