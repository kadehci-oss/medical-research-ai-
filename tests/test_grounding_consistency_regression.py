"""Grounding regressions from published abstracts. No network, no PMID special case.

The fixtures are the abstracts returned for the live queries. The engine is not
told which PMID is which; each check is about the text.
"""
import json
import os
import re
import unittest

from report_generator import (
    _format_bound_claims,
    _format_cross_study_comparison,
    assess_risk_of_bias,
    display_bias_rating,
    display_bias_tool,
    extract_article_clinical_details,
    generate_rule_based_turkish_report,
)


_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grounding_abstracts.json")


def _load():
    with open(_FIXTURE, encoding="utf-8") as handle:
        return {article["pmid"]: article for article in json.load(handle)}


def _row_cell(table, pmid, index):
    for line in table.splitlines():
        if line.startswith("|") and re.search(r"\b" + re.escape(pmid) + r"\b", line):
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            return cells[index] if len(cells) > index else ""
    return ""


def _unlabeled_counts(value):
    """Bare 'N hasta' segments, the defect the live reports showed."""
    parts = [part.strip() for part in (value or "").split(";")]
    return [
        part for part in parts
        if re.fullmatch(r"\d+\s+hasta(?:\s*\(%[\d.]+\))?", part)
    ]


class TestPatientGroupIsOneTotal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def _same_group(self, pmid, query):
        article = self.by_pmid[pmid]
        details = extract_article_clinical_details(article, query)
        table = _format_cross_study_comparison([article], {})
        cell = _row_cell(table, pmid, 1)
        self.assertEqual(cell, details["patient_group"])
        return details, cell

    def test_enrolled_total_is_not_an_unlabeled_list(self):
        details, cell = self._same_group("23290630", "anti-NMDA receptor encephalitis treatment")
        self.assertIn("577 hasta", cell)
        self.assertIn("anti-NMDA reseptör ensefaliti", cell)
        self.assertEqual(_unlabeled_counts(cell), ["577 hasta"])
        for stray in ("221 hasta", "501 hasta", "252 hasta", "45 hasta"):
            self.assertNotIn(stray, cell)
        self.assertEqual(cell.lower().count("577"), 1)

        liu, liu_cell = self._same_group("35340259", "anti-NMDA receptor encephalitis treatment")
        self.assertIn("15 hasta", liu_cell)
        self.assertEqual(_unlabeled_counts(liu_cell), ["15 hasta"])
        self.assertNotRegex(liu_cell, r"(?<!\d)5 hasta")
        self.assertNotRegex(liu_cell, r"(?<!\d)10 hasta")
        self.assertNotIn("açıkça bildirilmedi", liu["patient_group"])
        self.assertNotIn("açıkça bildirilmedi", liu_cell)

    def test_kawasaki_total_does_not_borrow_a_later_percent(self):
        details, cell = self._same_group("33753891", "Kawasaki disease IVIG resistance")
        self.assertIn("129 hasta", cell)
        self.assertIn("Kawasaki hastalığı (KH)", cell)
        self.assertNotIn("%61.2", cell)
        self.assertEqual(details["sample_size"], "n = 129")


class TestQuotesMatchTheExtractedToken(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def _bound(self, pmid, query):
        article = self.by_pmid[pmid]
        details = extract_article_clinical_details(article, query)
        return details, _format_bound_claims(details)

    def test_intervention_quote_names_the_drug_not_the_title(self):
        details, bound = self._bound("23290630", "anti-NMDA receptor encephalitis treatment")
        intervention = details["provenance"]["intervention"]
        sentence = intervention["source_sentence"]
        self.assertIn("intravenous immunoglobulin", sentence.lower())
        self.assertIn("rituximab", sentence.lower())
        self.assertNotIn("In 177 children", sentence)
        self.assertNotEqual(sentence.strip(), self.by_pmid["23290630"]["title"].strip())
        # Hasta grubu and Örneklem share one quote.
        self.assertEqual(bound.count("We enrolled 577 patients"), 1)
        self.assertIn("Kaynak cümle: yukarıdaki ile aynı", bound)

        for pmid in ("33753891", "39040113"):
            item_details, item_bound = self._bound(pmid, "Kawasaki disease IVIG resistance")
            item = item_details["provenance"]["intervention"]
            title = self.by_pmid[pmid]["title"]
            if item["source"] == "title":
                self.assertIn("Kaynak: makale başlığı", item_bound)
                self.assertNotIn(f'Kaynak cümle: "{title}"', item_bound)
            else:
                self.assertIn("ivig", (item["source_sentence"] or "").lower())
                self.assertNotEqual((item["source_sentence"] or "").strip(), title.strip())

    def test_field_token_is_cased_the_same_way(self):
        article = self.by_pmid["39040113"]
        report = generate_rule_based_turkish_report(
            "Kawasaki disease IVIG resistance",
            [article],
        )
        self.assertNotIn("Özette bildirilmedi", report)
        self.assertIn("özette bildirilmedi", report)


class TestOutcomesAreSplitAndNotDuplicated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def test_predictor_sentence_becomes_named_rows(self):
        article = self.by_pmid["23290630"]
        details = extract_article_clinical_details(article, "anti-NMDA receptor encephalitis treatment")
        outcomes = details["provenance"]["outcomes"]
        names = [item["outcome"] for item in outcomes]
        self.assertIn("öngördürücü: erken tedavi", names)
        self.assertIn("öngördürücü: yoğun bakım yatışı yok", names)
        keys = []
        for item in outcomes:
            key = (
                item["outcome"],
                tuple(item["metrics"]),
                item.get("p") or "",
                item.get("sentence") or "",
            )
            self.assertNotIn(key, keys)
            keys.append(key)
        bound = _format_bound_claims(details)
        self.assertIn("Sonlanım/öngördürücü: erken tedavi", bound)
        self.assertEqual(bound.count("İstatistik: p < 0.0001"), 0)
        self.assertLessEqual(bound.count("p < 0.0001"), 2)

    def test_two_odds_ratios_keep_their_own_names(self):
        article = self.by_pmid["33753891"]
        details = extract_article_clinical_details(article, "Kawasaki disease IVIG resistance")
        names = [item["outcome"] for item in details["provenance"]["outcomes"]]
        self.assertIn("öngördürücü: trombosit sayısı", names)
        self.assertIn("öngördürücü: GGT düzeyi", names)
        self.assertEqual(len(names), len(set(names)))
        text = details["real_findings"]
        self.assertIn("trombosit sayısı için anlamlı", text)
        self.assertNotIn("Anlamlılık değerlendirilemedi", text)


class TestBiasLabelIsTurkish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_pmid = _load()

    def test_section_matrix_uses_the_acronym_and_degerlendirilmedi(self):
        article = self.by_pmid["23290630"]
        rob = assess_risk_of_bias(article)
        # The stored tool name can keep the English gloss for callers that
        # compare the instrument. The report shows the acronym only.
        self.assertIn("ROBINS-I", rob["tool"])
        report = generate_rule_based_turkish_report(
            "anti-NMDA receptor encephalitis treatment",
            [article],
        )
        matrix = report.split("### 📊 Karşılaştırmalı Sentez Matrisi")[1].split("### ✅")[0]
        self.assertIn("Yanlılık aracı:** ROBINS-I |", matrix)
        self.assertIn("Risk derecesi:** Değerlendirilmedi", matrix)
        self.assertNotIn("Risk of Bias in Non-Randomized Studies", matrix)
        self.assertNotIn("(Not Assessed)", matrix)
        self.assertEqual(display_bias_tool(rob["tool"]), "ROBINS-I")
        self.assertEqual(display_bias_rating(rob["overall_rating"]), "Değerlendirilmedi")


if __name__ == "__main__":
    unittest.main()
