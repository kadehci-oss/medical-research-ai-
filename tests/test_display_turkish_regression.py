"""Section 6 Turkish cells and study-card extraction. No network.

The checks are disease-agnostic. A PMID is only the fixture that showed the
failure; the engine does not special-case that PMID.
"""
import json
import os
import re
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from report_generator import (
    UNTRANSLATED_OUTCOME_LABEL,
    _format_cross_study_comparison,
    extract_article_clinical_details,
    format_klinik_bulgular_cell,
    generate_rule_based_turkish_report,
)

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Same shapes as a results sentence that used to be cut at a decimal and at "s.d.".
_CARD_ABSTRACT = (
    "METHOD: Twenty patients with inflammatory myopathy (IM) were characterized. "
    "RESULTS: IMNM vs IIM patients were older [61.6 years (s.d. 9.8) vs 39.8 (14.3)]. "
    "RP (9.1% vs 55.6%) was less common (P < 0.05)."
)
_UNTRANSLATABLE_ABSTRACT = (
    "In this cohort quixotic flibbertigibbet was increased "
    "(OR 3.20, 95% CI 1.10 to 4.40, p=0.02)."
)


def _load(name):
    with open(os.path.join(_FIXTURE_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def _article(pmid, title, pub_types, abstract):
    return {
        "pmid": pmid,
        "title": title,
        "authors": ["Deneme Yazar"],
        "journal": "Test Journal",
        "pub_year": "2024",
        "publication_types": pub_types,
        "abstract": abstract,
        "doi": "10.1000/display-" + pmid,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": "https://doi.org/10.1000/display-" + pmid,
    }


def _row_cells(table, pmid):
    for line in table.splitlines():
        if line.startswith("|") and re.search(r"\b" + re.escape(pmid) + r"\b", line):
            return [part.strip() for part in line.strip().strip("|").split("|")]
    return []


class TestSection6TurkishFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        articles = _load("recorded_target_pmids.json") + _load("recorded_pmid_33447390.json")
        cls.by_pmid = {article["pmid"]: article for article in articles}

    def test_bulgular_use_the_terminology_map_and_hide_unsafe_english(self):
        table = _format_cross_study_comparison(
            [self.by_pmid["40446701"], self.by_pmid["41010829"], self.by_pmid["33447390"]],
            {},
        )
        statin = _row_cells(table, "40446701")[4]
        self.assertIn("statin ilişkili anti-HMGCR antikor pozitif İMNM", statin)
        self.assertIn("diyabet", statin)
        self.assertIn("kanserle ilişkili İİM", statin)
        self.assertIn("OR 4.81", statin)
        self.assertIn("1.03 ile 22.6", statin)
        for english in (
            "statin-induced",
            "diabetes mellitus",
            "cancer-associated",
            "antibody IMNM",
        ):
            self.assertNotIn(english, statin.lower())

        criteria = _row_cells(table, "41010829")[4]
        self.assertIn("Avrupa Nöromusküler Merkezi", criteria)
        self.assertIn("İMNM", criteria)
        self.assertIn("kortikosteroid", criteria)
        self.assertIn("takrolimus", criteria)
        self.assertNotIn("European", criteria)
        self.assertNotIn("Neuromuscular", criteria)

        skin = _row_cells(table, "33447390")[4]
        self.assertIn("dermatomiyozit benzeri deri bulguları", skin)

        # Section 5 still quotes the English source sentence.
        cell = format_klinik_bulgular_cell(self.by_pmid["40446701"])
        self.assertIn("Kaynak cümle:", cell)
        self.assertIn("diabetes mellitus", cell)

    def test_untranslatable_outcome_is_not_shown_as_raw_english(self):
        article = _article(
            "90007001",
            "An unnamed laboratory signal",
            ["Journal Article"],
            _UNTRANSLATABLE_ABSTRACT,
        )
        table = _format_cross_study_comparison([article], {})
        findings = _row_cells(table, "90007001")[4]
        self.assertIn(UNTRANSLATED_OUTCOME_LABEL, findings)
        self.assertIn("3.20", findings)
        self.assertNotIn("quixotic", findings.lower())
        self.assertNotIn("flibbertigibbet", findings.lower())

    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "reason": "match"})
    def test_hasta_grubu_does_not_repeat_the_column_label(self, _verify):
        articles = [
            self.by_pmid["40446701"],
            self.by_pmid["41010829"],
            self.by_pmid["33447390"],
        ]
        table = _format_cross_study_comparison(articles, {})
        self.assertNotIn("Örneklem ve hasta özellikleri", table)
        populated = _row_cells(table, "40446701")[1]
        self.assertIn("62 hasta Hispanik", populated)
        self.assertIn("35 hasta Hispanik olmayan", populated)
        self.assertEqual(_row_cells(table, "33447390")[1], "özette bildirilmedi")

        report = generate_rule_based_turkish_report("inflamatuar miyopati", articles)
        section_6 = report.split("## 6. Önemli Çalışmaların Karşılaştırılması")[1].split("## 7.")[0]
        table_lines = "\n".join(line for line in section_6.splitlines() if line.startswith("|"))
        self.assertNotIn("Örneklem ve hasta özellikleri", table_lines)
        self.assertIn("özette bildirilmedi", table_lines)
        self.assertIn("diyabet", table_lines)
        self.assertNotIn("diabetes mellitus", table_lines.lower())


class TestStudyCardExtraction(unittest.TestCase):
    def test_comparison_and_outcomes_are_not_cut_inside_numbers_or_brackets(self):
        article = _article(
            "90007002",
            "Immune myopathy in two groups",
            ["Journal Article"],
            _CARD_ABSTRACT,
        )
        details = extract_article_clinical_details(article, "immune myopathy")
        comparison = details["comparison"]
        outcomes = details["outcomes_summary"]
        visible = " ".join((details["patient_group"], comparison, details["intervention"], outcomes))

        self.assertNotIn("Iim", visible)
        self.assertIn("61.6", comparison)
        self.assertIn("9.8", comparison)
        self.assertIn("39.8", comparison)
        self.assertEqual(comparison.count("["), comparison.count("]"))
        self.assertEqual(comparison.count("("), comparison.count(")"))
        self.assertIn("İİM", comparison)
        self.assertIn("karşı", comparison)
        self.assertNotRegex(comparison, r"\[61(?!\.6)")

        self.assertRegex(outcomes, r"9\.1%\s+karşı\s+55\.6%\)")
        self.assertNotRegex(outcomes, r"55\.6(?!%)")
        self.assertIn("inflamatuar miyopati", details["patient_group"])
        self.assertNotIn("were characterized", details["patient_group"].lower())

    def test_placebo_and_drug_names_stay_traceable(self):
        article = _article(
            "90007003",
            "Empagliflozin in heart failure",
            ["Randomized Controlled Trial"],
            "Patients were randomized to receive empagliflozin 10 mg or placebo. "
            "Heart failure hospitalization fell (HR 0.79, 95% CI 0.69-0.90, p<0.001).",
        )
        details = extract_article_clinical_details(article, "heart failure")
        self.assertEqual(details["intervention"], "Empagliflozin 10 mg")
        self.assertEqual(details["comparison"], "Plasebo")
        self.assertIn("HR 0.79", details["outcomes_summary"])


class TestStreamlitStudyCardAndSection6(unittest.TestCase):
    @patch("pubmed_client.search_pubmed")
    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "reason": "match"})
    def test_search_card_and_report_table_do_not_cut_or_leave_english(self, _verify, mock_search):
        recorded = {article["pmid"]: article for article in _load("recorded_target_pmids.json")}
        card = _article(
            "90007002",
            "Immune myopathy in two groups",
            ["Journal Article"],
            _CARD_ABSTRACT,
        )
        mock_search.return_value = {
            "status": "success",
            "articles": [card, recorded["40446701"]],
            "total_count": 2,
            "query": "immune myopathy",
            "search_date": "2026-10-30",
        }
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
        at = AppTest.from_file(app_path, default_timeout=60)
        at.run()
        at.text_input[0].input("immune myopathy").run()
        search_btn = [button for button in at.button if "Ara" in button.label][0]
        search_btn.click().run()
        self.assertFalse(at.exception)

        visible = " ".join(getattr(block, "value", "") or "" for block in at.markdown)
        visible += " " + " ".join(getattr(block, "value", "") or "" for block in at.caption)
        self.assertIn("61.6", visible)
        self.assertIn("55.6%", visible)
        self.assertNotIn("Iim", visible)
        self.assertNotRegex(visible, r"\[61(?!\.6)")
        self.assertRegex(visible, r"55\.6%\)")

        report_btn = [button for button in at.button if "Türkçe Kanıt Raporu" in button.label][0]
        report_btn.click().run()
        self.assertFalse(at.exception)
        report = at.session_state["generated_report"]
        section_6 = report.split("## 6. Önemli Çalışmaların Karşılaştırılması")[1].split("## 7.")[0]
        table_lines = "\n".join(line for line in section_6.splitlines() if line.startswith("|"))
        self.assertNotIn("Örneklem ve hasta özellikleri", table_lines)
        self.assertIn("diyabet", table_lines)
        self.assertIn("kanserle ilişkili İİM", table_lines)
        self.assertNotIn("diabetes mellitus", table_lines.lower())
        self.assertNotIn("statin-induced", table_lines.lower())


if __name__ == "__main__":
    unittest.main()
