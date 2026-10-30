"""Offline regression: case reports are not reviews, and section 5 stays source-grounded.

Metadata was recorded from PubMed EFetch (publication type, title, abstract,
authors, journal, year, DOI). This module does not call the network.
The reference package medical_research_fix41.zip was not available; these
records were fetched directly from NCBI and then frozen.
"""
import json
import os
import re
import unittest
from unittest.mock import patch

from report_generator import (
    NO_NUMERIC_CLINICAL_FINDING_TR,
    classify_study_design,
    extract_grounded_clinical_findings,
    format_klinik_bulgular_cell,
    generate_evidence_table_html,
    generate_evidence_table_markdown,
    generate_rule_based_turkish_report,
)

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "recorded_pubmed_multidesign.json")

# design_key expected from the recorded publication type, title, and abstract.
# Case reports and case series must never land on narrative_review.
_EXPECTED_DESIGN = {
    "33372889": "case_report",       # Romatoloji, yayın türü Review
    "36896367": "case_series",       # Romatoloji, iki olgu, Case Reports
    "41458822": "systematic_review", # Romatoloji, yayın türü Review
    "35955495": "narrative_review",  # Nöromüsküler derleme
    "32581543": "narrative_review",  # Romatoloji derlemesi
    "35503884": "case_report",       # Dermatoloji, Case Reports + Review
    "38955192": "case_report",       # Nöroloji, Case Reports + Review
    "15271581": "narrative_review",  # Psikiyatri, mecazi "a case of"
    "33795149": "case_series",       # Kardiyoloji, olgu serisi
    "32345662": "cross_sectional",   # Endokrinoloji, "cross sectional"
    "12556958": "case_control",      # Hematoloji / enfeksiyon, vaka-kontrol
    "40532178": "rct",               # Onkoloji, RCT
    "35228754": "rct",               # Kardiyoloji, RCT
    "35241506": "systematic_review_and_meta_analysis",  # Onkoloji
    "23439909": "guideline",         # Kulak burun boğaz kılavuzu
    "38750479": "rct",               # Psikiyatri, RCT
    "33253970": "systematic_review", # Göğüs hastalıkları
    "40353578": "clinical_trial",    # Endokrinoloji, faz 3
}

_CASE_KEYS = {"case_report", "case_series"}
_NUMBER_RE = re.compile(r"[-−]?\d+(?:\.\d+)?")


def _load_articles():
    with open(_FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def _by_pmid(articles):
    return {article["pmid"]: article for article in articles}


def _normalized(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ").replace("\u2009", " ")).strip()


def _section_5(report):
    return report.split("## 5. Bilimsel Kanıt Tablosu")[1].split("## 6.")[0]


def _table_row(table, pmid):
    for line in table.splitlines():
        if line.startswith("|") and pmid in line:
            return line
    return ""


class TestRecordedDesignsStayDiseaseAgnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles = _load_articles()
        cls.by_pmid = _by_pmid(cls.articles)

    def test_fixture_covers_the_requested_imnm_pmids_and_several_specialties(self):
        pmids = [article["pmid"] for article in self.articles]
        for pmid in ("33372889", "41458822", "36896367", "35955495", "32581543"):
            self.assertIn(pmid, pmids)
        self.assertEqual(len(self.articles), len(_EXPECTED_DESIGN))
        self.assertEqual(set(pmids), set(_EXPECTED_DESIGN))

    def test_recorded_designs_match_and_case_reports_are_not_reviews(self):
        for article in self.articles:
            pmid = article["pmid"]
            design = classify_study_design(
                article["publication_types"], article["title"], article["abstract"]
            )
            self.assertEqual(design["design_key"], _EXPECTED_DESIGN[pmid], pmid)
            self.assertEqual(design["level"], "Değerlendirilemedi", pmid)
            self.assertIsNone(design["level_num"], pmid)
            self.assertNotIn("Seviye", design["level"])
            if _EXPECTED_DESIGN[pmid] in _CASE_KEYS:
                self.assertNotIn("Derleme", design["design"], pmid)
                self.assertNotIn("Uzman Görüşü", design["design"], pmid)
                self.assertNotEqual(design["design_key"], "narrative_review", pmid)

    def test_review_tagged_case_language_is_a_case_across_specialties(self):
        cases = [
            ("Kardiyoloji", "A case of aortic dissection after lifting", "The patient underwent repair."),
            ("Onkoloji", "Metastatic melanoma", "We present a patient with a new pigmented lesion."),
            ("Enfeksiyon", "Tuberculous meningitis", "We describe a man with fever and neck stiffness."),
            ("Endokrinoloji", "Thyroid storm", "A 34-year-old woman developed fever after delivery."),
            ("Kulak burun boğaz", "Sudden hearing loss: a case report", "The patient received corticosteroids."),
            ("Psikiyatri", "Catatonia after antipsychotic withdrawal", "An 8-year-old boy developed mutism."),
        ]
        for specialty, title, abstract in cases:
            design = classify_study_design(["Journal Article", "Review"], title, abstract)
            self.assertEqual(design["design_key"], "case_report", specialty)
            self.assertEqual(design["design"], "Olgu Sunumu", specialty)
            self.assertNotIn("Derleme", design["design"], specialty)

        series = classify_study_design(
            ["Review"],
            "Thyroid storm",
            "We present three patients with thyroid storm.",
        )
        self.assertEqual(series["design_key"], "case_series")
        self.assertEqual(series["design"], "Olgu Serisi")

    def test_metaphorical_case_of_inside_a_self_described_review_stays_a_review(self):
        article = self.by_pmid["15271581"]
        self.assertIn("a case of", article["title"].lower())
        self.assertIn("Review", article["publication_types"])
        design = classify_study_design(
            article["publication_types"], article["title"], article["abstract"]
        )
        self.assertEqual(design["design_key"], "narrative_review")
        self.assertEqual(design["design"], "Niteliksel Derleme / Uzman Görüşü")


class TestKlinikBulgularCellIsSourceGrounded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles = _load_articles()
        cls.by_pmid = _by_pmid(cls.articles)

    def test_every_number_in_a_finding_is_in_its_source_sentence(self):
        for article in self.articles:
            abstract = _normalized(article["abstract"])
            findings = extract_grounded_clinical_findings(article["abstract"])
            for finding in findings:
                self.assertIn(finding["sentence"], abstract, article["pmid"])
                blob = f"{finding['effect']} {finding['ci']}"
                for number in _NUMBER_RE.findall(blob):
                    self.assertIn(number, finding["sentence"], f"{article['pmid']} {number} {blob}")

    def test_missing_effect_measure_is_stated_in_turkish_without_the_english_abstract(self):
        for pmid in ("33372889", "35955495", "32581543", "36896367", "35503884", "38750479"):
            article = self.by_pmid[pmid]
            cell = format_klinik_bulgular_cell(article)
            self.assertTrue(cell.startswith(NO_NUMERIC_CLINICAL_FINDING_TR), cell)
            self.assertIn(f"PMID: {pmid}", cell)
            opening = _normalized(article["abstract"])[:80]
            self.assertNotIn(opening, cell, pmid)
            self.assertNotIn("HR ", cell)
            self.assertNotIn("odds ratio", cell.lower())

    def test_named_effects_keep_pmid_outcome_value_ci_and_source_sentence(self):
        leukaemia = format_klinik_bulgular_cell(self.by_pmid["12556958"])
        self.assertIn("PMID: 12556958", leukaemia)
        self.assertIn("Sonlanım: leukaemia", leukaemia)
        self.assertIn("Etki ölçütü: odds ratio 4.2", leukaemia)
        self.assertIn("Güven aralığı: 1.1 ile 16.2", leukaemia)
        self.assertIn("Kaynak cümle:", leukaemia)
        self.assertIn("odds ratio 4.2, 95% confidence interval 1.1-16.2", leukaemia)
        self.assertNotIn("0.66", leukaemia)

        cardio = format_klinik_bulgular_cell(self.by_pmid["35228754"])
        self.assertIn("PMID: 35228754", cardio)
        self.assertIn("Etki ölçütü: win ratio 1.36", cardio)
        self.assertIn("Güven aralığı: 1.09 ile 1.68", cardio)
        self.assertIn("stratified win ratio, 1.36", cardio)
        self.assertNotIn("4.2", cardio)

        oncology = format_klinik_bulgular_cell(self.by_pmid["40532178"])
        self.assertIn("PMID: 40532178", oncology)
        self.assertIn("Etki ölçütü: hazard ratio 0.66", oncology)
        self.assertIn("Güven aralığı: 0.49 ile 0.88", oncology)
        self.assertIn("Etki ölçütü: hazard ratio 0.70", oncology)
        self.assertIn("Güven aralığı: 0.55 ile 0.89", oncology)
        self.assertIn("progression, recurrence, or death", oncology)

    def test_unnamed_effect_with_ci_does_not_invent_a_measure_name(self):
        cell = format_klinik_bulgular_cell(self.by_pmid["40353578"])
        self.assertIn("PMID: 40353578", cell)
        self.assertIn("Etki ölçütü: özette adlandırılmadı; kaynak değer: -20.2%", cell)
        self.assertIn("Güven aralığı: -21.4 ile -19.1", cell)
        self.assertIn("Sonlanım: weight", cell)
        self.assertNotIn("HR ", cell)
        self.assertNotIn("odds ratio", cell.lower())
        self.assertNotRegex(cell, r"\bMD\s+-20\.2")

    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "reason": "match"})
    def test_section_5_table_has_no_raw_english_abstract_and_keeps_links(self, _mock_verify):
        selected = [
            self.by_pmid[pmid]
            for pmid in ("33372889", "35503884", "38955192", "36896367", "12556958", "40532178", "35228754")
        ]
        report = generate_rule_based_turkish_report(
            "statin-associated immune-mediated necrotizing myopathy",
            selected,
        )
        section = _section_5(report)
        self.assertIn("Klinik Bulgular hücresi ham özet metni değildir", section)

        for pmid in ("33372889", "35503884", "36896367"):
            row = _table_row(section, pmid)
            self.assertIn(NO_NUMERIC_CLINICAL_FINDING_TR, row, pmid)
            opening = _normalized(self.by_pmid[pmid]["abstract"])[:80]
            self.assertNotIn(opening, row, pmid)

        case_row = _table_row(section, "33372889")
        self.assertIn("**Olgu Sunumu**", case_row)
        self.assertNotIn("Niteliksel Derleme", case_row)

        neuro_row = _table_row(section, "38955192")
        self.assertIn("**Olgu Sunumu**", neuro_row)
        self.assertNotIn("**Niteliksel Derleme", neuro_row)

        series_row = _table_row(section, "36896367")
        self.assertIn("**Olgu Serisi**", series_row)
        self.assertNotIn("Niteliksel Derleme", series_row)

        leukaemia_row = _table_row(section, "12556958")
        self.assertIn("odds ratio 4.2", leukaemia_row)
        self.assertIn("1.1 ile 16.2", leukaemia_row)
        self.assertIn("PMID: 12556958", leukaemia_row)
        self.assertNotIn("hazard ratio 0.66", leukaemia_row)
        self.assertNotIn("win ratio 1.36", leukaemia_row)

        oncology_row = _table_row(section, "40532178")
        self.assertIn("hazard ratio 0.66", oncology_row)
        self.assertIn("0.49 ile 0.88", oncology_row)
        self.assertNotIn("odds ratio 4.2", oncology_row)

        html_table = generate_evidence_table_html(selected)
        self.assertIn(NO_NUMERIC_CLINICAL_FINDING_TR, html_table)
        self.assertIn("odds ratio 4.2", html_table)
        self.assertNotIn(_normalized(self.by_pmid["33372889"]["abstract"])[:80], html_table)
        markdown = generate_evidence_table_markdown(selected)
        self.assertNotIn("<br>", markdown)


if __name__ == "__main__":
    unittest.main()
