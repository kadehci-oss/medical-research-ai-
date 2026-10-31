"""Mock regression for design, grounded findings, and cross-article separation.

The recorded PMIDs are inputs to the general classifier. Their numbers are not
special cases in the engine. Real PubMed calls stay in
test_live_pubmed_design_regression.py. Streamlit stays in
test_section5_streamlit_report.py.
"""
import json
import os
import re
import unittest
from unittest.mock import patch

from report_generator import (
    INSUFFICIENT_CLINICAL_DATA_TR,
    classify_study_design,
    extract_clinical_profile,
    extract_grounded_clinical_findings,
    format_klinik_bulgular_cell,
    generate_rule_based_turkish_report,
)

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "recorded_target_pmids.json")
_ENGINE = os.path.join(os.path.dirname(__file__), "..", "report_generator.py")


def _load():
    with open(_FIXTURE, encoding="utf-8") as handle:
        return {article["pmid"]: article for article in json.load(handle)}


def _article(pmid, title, pub_types, abstract):
    return {
        "pmid": pmid,
        "title": title,
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "journal": "Test Journal",
        "pub_year": "2024",
        "publication_types": pub_types,
        "abstract": abstract,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _row(table, pmid):
    for line in table.splitlines():
        if line.startswith("|") and pmid in line and "PMID" not in line[:8]:
            return line
    for line in table.splitlines():
        if pmid in line and line.startswith("|"):
            return line
    return ""


class TestRecordedPmidsUseTheGeneralEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def test_classifier_source_does_not_hardcode_these_pmids(self):
        with open(_ENGINE, encoding="utf-8") as handle:
            source = handle.read()
        for pmid in ("40446701", "41010829", "36896367"):
            self.assertNotIn(pmid, source)

    def test_40446701_is_a_retrospective_comparative_observational_study(self):
        article = self.by_pmid["40446701"]
        self.assertEqual(article["publication_types"], ["Journal Article"])
        self.assertIn("In this retrospective study", article["abstract"])
        self.assertIn("Statistical comparisons were performed", article["abstract"])
        design = classify_study_design(article["publication_types"], article["title"], article["abstract"])
        self.assertEqual(design["design_key"], "retrospective_comparative")
        self.assertEqual(design["design"], "Retrospektif Karşılaştırmalı Gözlemsel Araştırma")
        self.assertEqual(design["level"], "Değerlendirilemedi")
        self.assertIsNone(design["level_num"])

    def test_41010829_is_a_retrospective_clinical_case_series(self):
        article = self.by_pmid["41010829"]
        self.assertIn("A retrospective review was conducted", article["abstract"])
        self.assertIn("Ten patients", article["abstract"])
        design = classify_study_design(article["publication_types"], article["title"], article["abstract"])
        self.assertEqual(design["design_key"], "retrospective_case_series")
        self.assertEqual(design["design"], "Retrospektif Klinik Olgu Serisi")
        self.assertEqual(design["level"], "Değerlendirilemedi")
        self.assertIsNone(design["level_num"])

    def test_36896367_case_reports_tag_stays_a_series_because_the_abstract_describes_two_patients(self):
        article = self.by_pmid["36896367"]
        self.assertIn("Case Reports", article["publication_types"])
        self.assertNotRegex(article["title"], r"\ba case of\b|\ba patient\b")
        self.assertIn("two cases", article["abstract"].lower())
        self.assertIn("Both patients", article["abstract"])
        design = classify_study_design(article["publication_types"], article["title"], article["abstract"])
        self.assertEqual(design["design_key"], "case_series")
        self.assertEqual(design["design"], "Olgu Serisi")
        self.assertEqual(design["level"], "Değerlendirilemedi")


class TestSameRulesAcrossSpecialties(unittest.TestCase):
    def test_eight_specialties_keep_distinct_designs_without_a_disease_table(self):
        cases = [
            ("Kardiyoloji", ["Journal Article"], "Group differences in heart-failure biomarkers",
             "In this retrospective study 210 patients with heart failure were compared. "
             "Statistical comparisons were performed between ischemic and non-ischemic groups "
             "(OR: 1.80, CI: (1.10, 2.90), p=0.02).",
             "retrospective_comparative"),
            ("Onkoloji", ["Journal Article"], "Clinical course of a rare sarcoma",
             "A retrospective review was conducted at one center. Twelve patients were included. "
             "Treatment included corticosteroids. Median follow-up was 14 months.",
             "retrospective_case_series"),
            ("Nöroloji", ["Case Reports"], "A case of new-onset seizure after a drug",
             "We report a 54-year-old man with a single seizure. Two cases of seizure have been "
             "described previously in the literature.",
             "case_report"),
            ("Dermatoloji", ["Case Reports", "Journal Article"], "Three patients with a new rash",
             "We present three patients with a persistent rash after a new drug.",
             "case_series"),
            ("Endokrinoloji", ["Journal Article"], "Cross-sectional study of HbA1c",
             "This cross-sectional study included 400 adults. HbA1c differed between groups "
             "(MD 0.4, 95% CI 0.1-0.7).",
             "cross_sectional"),
            ("Enfeksiyon hastalıkları", ["Case-Control Studies"], "Exposure and resistant infection",
             "In this case-control study, prior exposure was compared (OR 2.1, 95% CI 1.4-3.2).",
             "case_control"),
            ("Göğüs hastalıkları", ["Journal Article"], "Lung function in a community cohort",
             "In this prospective cohort of 500 adults, participants were followed for 3 years.",
             "cohort"),
            ("Psikiyatri", ["Randomized Controlled Trial"], "An antidepressant trial",
             "In this randomized trial, 80 patients received the drug or placebo "
             "(HR 0.70, 95% CI 0.50-0.90).",
             "rct"),
            ("Hematoloji", ["Practice Guideline"], "Clinical practice guideline for transfusion",
             "This clinical practice guideline addresses transfusion thresholds.",
             "guideline"),
        ]
        self.assertGreaterEqual(len({item[0] for item in cases}), 8)
        designs = set()
        for specialty, pub_types, title, abstract, expected in cases:
            design = classify_study_design(pub_types, title, abstract)
            self.assertEqual(design["design_key"], expected, specialty)
            self.assertEqual(design["level"], "Değerlendirilemedi", specialty)
            self.assertIsNone(design["level_num"], specialty)
            designs.add(expected)
        self.assertGreaterEqual(len(designs), 8)

    def test_false_positive_designs_stay_unclassified_or_keep_the_stronger_label(self):
        cited = classify_study_design(
            ["Journal Article", "Review"],
            "Heart failure management",
            "A previous retrospective study compared two drugs (OR 2.0, CI: (1.1, 3.4)). "
            "This review summarizes current management.",
        )
        self.assertEqual(cited["design_key"], "narrative_review")

        literature = classify_study_design(
            ["Journal Article"],
            "Mechanisms of cough",
            "A retrospective review of the literature was performed. No patients were enrolled.",
        )
        self.assertEqual(literature["design_key"], "unclassified")

        vague = classify_study_design(
            ["Journal Article"],
            "Observations in clinic",
            "Patients were discussed. The retrospective nature of medicine is well known.",
        )
        self.assertEqual(vague["design_key"], "unclassified")

        cohort = classify_study_design(
            ["Journal Article"],
            "Blood pressure in a retrospective cohort",
            "In this retrospective cohort of 200 adults, participants were followed for 5 years.",
        )
        self.assertEqual(cohort["design_key"], "cohort")

        single = classify_study_design(
            ["Case Reports"],
            "A case of stroke after surgery",
            "We describe a 70-year-old woman. Two cases of stroke have been reported previously.",
        )
        self.assertEqual(single["design_key"], "case_report")
        self.assertEqual(single["design"], "Olgu Sunumu")

    def test_the_same_comparative_wording_is_not_limited_to_one_disease(self):
        cardiology = classify_study_design(
            ["Journal Article"],
            "Statin exposure is not the topic",
            "In this retrospective study 80 patients with atrial fibrillation were compared. "
            "Statistical comparisons were performed.",
        )
        oncology = classify_study_design(
            ["Journal Article"],
            "Adjuvant therapy timing",
            "A retrospective review was conducted. Eight patients with sarcoma were included.",
        )
        self.assertEqual(cardiology["design_key"], "retrospective_comparative")
        self.assertEqual(oncology["design_key"], "retrospective_case_series")


class TestConfidenceIntervalsOutcomesAndGrouping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def test_parenthesis_bracket_and_unspaced_ci_formats_bind_to_their_outcomes(self):
        article = self.by_pmid["40446701"]
        findings = extract_grounded_clinical_findings(article["abstract"])
        by_outcome = {item["outcome"]: item for item in findings}
        self.assertIn("statin-induced anti-HMGCR antibody IMNM", by_outcome)
        self.assertIn("diabetes mellitus", by_outcome)
        self.assertIn("cancer-associated IIM", by_outcome)
        self.assertEqual(by_outcome["statin-induced anti-HMGCR antibody IMNM"]["effect"], "OR 4.81")
        self.assertEqual(by_outcome["statin-induced anti-HMGCR antibody IMNM"]["ci"], "1.03 ile 22.6")
        self.assertEqual(by_outcome["statin-induced anti-HMGCR antibody IMNM"]["p"], "p = 0.045")
        self.assertEqual(by_outcome["diabetes mellitus"]["ci"], "1.02 ile 6.29")
        self.assertEqual(by_outcome["cancer-associated IIM"]["effect"], "OR 0.23")
        self.assertEqual(by_outcome["cancer-associated IIM"]["ci"], "0.08 ile 0.7")
        for item in findings:
            self.assertNotEqual(item["ci"], "özette bildirilmedi")
            self.assertNotEqual(item["outcome"], "özette adlandırılmadı")

        bracket = extract_grounded_clinical_findings(
            "In patients with asthma the hazard ratio for exacerbation was 0.72 [0.61, 0.85]."
        )
        self.assertEqual(bracket[0]["ci"], "0.61 ile 0.85")
        dash = extract_grounded_clinical_findings(
            "Mortality was lower (HR 0.80, 95% CI 0.70–0.92)."
        )
        self.assertEqual(dash[0]["ci"], "0.70 ile 0.92")

    def test_one_source_sentence_is_shown_once_and_its_effects_are_grouped(self):
        cell = format_klinik_bulgular_cell(self.by_pmid["40446701"])
        sentence = (
            "statin-induced anti-HMGCR antibody IMNM was increased in Hispanics"
        )
        self.assertEqual(cell.count(sentence), 1)
        self.assertIn("Sonlanım: diyabet", cell)
        self.assertIn("diabetes mellitus", cell)
        self.assertNotIn("Sonlanım: diabetes mellitus", cell)
        self.assertIn("Güven aralığı: 1.03 ile 22.6", cell)
        self.assertIn("p değeri: p = 0.045", cell)
        self.assertLess(cell.find("(OR) 4.81"), cell.find("(OR) 2.54"))
        self.assertLess(cell.find(sentence), cell.find("(OR) 4.81"))

    def test_case_series_profile_keeps_ck_treatment_and_sample_on_their_sentences(self):
        article = self.by_pmid["41010829"]
        cell = format_klinik_bulgular_cell(article)
        self.assertIn("10 hasta", cell)
        self.assertIn("6 kadın, 4 erkek", cell)
        self.assertIn("ortanca yaş 58", cell)
        self.assertIn("European Neuromuscular Center", cell)
        self.assertIn("anti-HMGCR antikoru", cell)
        self.assertIn("1438 ile 13,000", cell)
        self.assertIn("kortikosteroid", cell)
        self.assertIn("Remisyon bildirildi", cell)
        self.assertIn("PMID: 41010829", cell)
        profile = extract_clinical_profile(article["abstract"])
        for item in profile:
            self.assertIn(item["sentence"], article["abstract"].replace("\xa0", " "))
            self.assertNotIn("4.81", item["line"])

    def test_two_patient_case_report_keeps_qualitative_findings(self):
        cell = format_klinik_bulgular_cell(self.by_pmid["36896367"])
        self.assertIn("Nitel klinik bulgu:", cell)
        self.assertIn("ilerleyici proksimal kas güçsüzlüğü", cell)
        self.assertIn("miyalji", cell)
        self.assertIn("PMID: 36896367", cell)
        self.assertNotIn(INSUFFICIENT_CLINICAL_DATA_TR, cell)

    def test_a_sentence_without_clinical_facts_states_insufficiency(self):
        article = _article(
            "90000111",
            "A note",
            ["Journal Article", "Review"],
            "This review summarizes laboratory methods. No patient outcome is stated.",
        )
        cell = format_klinik_bulgular_cell(article)
        self.assertTrue(cell.startswith(INSUFFICIENT_CLINICAL_DATA_TR))
        self.assertNotIn("laboratory methods", cell)


class TestFindingsDoNotCrossPmids(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "reason": "match"})
    def test_section_5_and_6_keep_each_number_on_its_own_pmid(self, _mock_verify):
        first = self.by_pmid["40446701"]
        second = self.by_pmid["41010829"]
        report = generate_rule_based_turkish_report(
            "statin-associated immune-mediated necrotizing myopathy",
            [first, second],
        )
        section_5 = report.split("## 5. Bilimsel Kanıt Tablosu")[1].split("## 6.")[0]
        section_6 = report.split("## 6. Önemli Çalışmaların Karşılaştırılması")[1].split("## 7.")[0]
        row_compare = _row(section_5, "40446701")
        row_series = _row(section_5, "41010829")
        self.assertIn("4.81", row_compare)
        self.assertIn("1.03 ile 22.6", row_compare)
        self.assertIn("diabetes mellitus", row_compare)
        self.assertNotIn("13,000", row_compare)
        self.assertNotIn("233", row_compare)
        self.assertIn("1438", row_series)
        self.assertIn("13,000", row_series)
        self.assertNotIn("4.81", row_series)
        self.assertNotIn("22.6", row_series)
        self.assertIn("**Retrospektif Karşılaştırmalı Gözlemsel Araştırma**", row_compare)
        self.assertIn("**Retrospektif Klinik Olgu Serisi**", row_series)

        self.assertIn("Hasta grubu", section_6)
        self.assertIn("Tasarım", section_6)
        self.assertIn("Müdahale", section_6)
        self.assertIn("Bulgular", section_6)
        self.assertIn("Metodolojik sınırlılık", section_6)
        self.assertIn("Çelişki", section_6)
        self.assertIn("Klinik sonucu doğrudan destekleyen PMID", section_6)
        self.assertIn("PMID: 40446701", section_6)
        self.assertIn("PMID: 41010829", section_6)
        compare_line = _row(section_6, "40446701")
        series_line = _row(section_6, "41010829")
        self.assertIn("4.81", compare_line)
        self.assertNotIn("13,000", compare_line)
        self.assertIn("1438", series_line)
        self.assertNotIn("4.81", series_line)
        self.assertNotIn("22.6", series_line)


if __name__ == "__main__":
    unittest.main()
