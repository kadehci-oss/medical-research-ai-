"""PICO from questions written as sentences (English and Turkish).

Every value must be a span of the query; nothing is translated or invented.
"""
import unittest

import pico_compat
import question_parser as qp
import report_generator as rg

NOT_STATED = "Belirtilmemiş"


class EnglishQuestions(unittest.TestCase):
    CASES = {
        "Does empagliflozin reduce mortality in heart failure with preserved ejection fraction?":
            ("Heart failure with preserved ejection fraction", "Empagliflozin", NOT_STATED, "Mortality"),
        "Is antibiotic therapy as effective as appendectomy for acute appendicitis?":
            ("Acute appendicitis", "Antibiotic therapy", "Appendectomy", NOT_STATED),
        "Effect of GLP-1 receptor agonists on weight loss in type 2 diabetes":
            ("Type 2 diabetes", "GLP-1 receptor agonists", NOT_STATED, "Weight loss"),
        "Can mechanical thrombectomy improve functional outcome in acute ischemic stroke compared with medical therapy?":
            ("Acute ischemic stroke", "Mechanical thrombectomy", "Medical therapy", "Functional outcome"),
        "What is the risk of epilepsy after febrile seizures in children?":
            ("Children", "Febrile seizures", NOT_STATED, "Epilepsy"),
    }

    def test_sentence_questions(self):
        for query, (p, i, c, o) in self.CASES.items():
            with self.subTest(query=query):
                pico = rg.extract_pico(query)
                self.assertEqual((pico["population"], pico["intervention"], pico["comparison"], pico["outcome"]),
                                 (p, i, c, o))

    def test_question_mark_never_leaks_into_a_field(self):
        pico = rg.extract_pico("What is the sensitivity of mammography screening for breast cancer?")
        self.assertFalse(any("?" in value for value in pico.values()))
        self.assertNotIn("What is", pico["intervention"])

    def test_keyword_strings_keep_the_old_extractor(self):
        self.assertIsNone(qp.parse_question("SGLT2 inhibitors in heart failure with preserved ejection fraction"))
        pico = rg.extract_pico("Empagliflozin versus placebo in patients with heart failure on cardiovascular death")
        self.assertEqual(pico["comparison"], "Placebo")
        self.assertEqual(pico["outcome"], "Cardiovascular death")


class TurkishQuestions(unittest.TestCase):
    CASES = {
        "Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi azaltır mı?":
            ("Kalp yetersizliği", "SGLT2 inhibitörleri", NOT_STATED, "Mortalite"),
        "Kalp yetersizliği hastalarında SGLT2 inhibitörleri plaseboya kıyasla mortaliteyi azaltır mı?":
            ("Kalp yetersizliği hastaları", "SGLT2 inhibitörleri", "Plasebo", "Mortalite"),
        "Akut apandisitte antibiyotik tedavisi apendektomi kadar etkili midir?":
            ("Akut apandisit", "Antibiyotik tedavisi", "Apendektomi", NOT_STATED),
        "Tip 2 diyabette GLP-1 agonistleri kilo kaybı sağlar mı?":
            ("Tip 2 diyabet", "GLP-1 agonistleri", NOT_STATED, "Kilo kaybı"),
        "Hipertansiyonda ACE inhibitörleri kalsiyum kanal blokerlerine göre inme riskini azaltır mı?":
            ("Hipertansiyon", "ACE inhibitörleri", "Kalsiyum kanal blokerleri", "İnme riski"),
        "Atriyal fibrilasyonlu yaşlı hastalarda düşük doz edoksaban kanamayı artırır mı?":
            ("Atriyal fibrilasyonlu yaşlı hastalar", "Düşük doz edoksaban", NOT_STATED, "Kanama"),
        "Çocuklarda febril nöbet sonrası epilepsi riski nedir?":
            ("Çocuklar", "Febril nöbet", NOT_STATED, "Epilepsi"),
        "İnmede trombektomi ile en iyi tıbbi tedavinin karşılaştırılması":
            ("İnme", "Trombektomi", "En iyi tıbbi tedavi", NOT_STATED),
    }

    def test_sentence_questions(self):
        for query, (p, i, c, o) in self.CASES.items():
            with self.subTest(query=query):
                pico = rg.extract_pico(query)
                self.assertEqual((pico["population"], pico["intervention"], pico["comparison"], pico["outcome"]),
                                 (p, i, c, o))

    def test_values_are_spans_of_the_query(self):
        for query in self.CASES:
            parsed = qp.parse_question(query)
            for value in parsed.values():
                for word in value.split():
                    with self.subTest(query=query, word=word):
                        stem = word[:max(3, len(word) - 3)].lower()
                        self.assertIn(stem, query.lower())

    def test_framework_shows_the_parsed_values(self):
        import question_framework as qf
        selection = qf.select_question_framework("Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi azaltır mı?")
        values = {e["key"]: e["value"] for e in selection["elements"]}
        self.assertEqual(values["P"], "Kalp yetersizliği")
        self.assertEqual(values["I"], "SGLT2 inhibitörleri")
        self.assertEqual(values["O"], "Mortalite")


class TurkishQueryTermsDoNotExcludeEnglishStudies(unittest.TestCase):
    def _study(self, title):
        return {"population": None, "intervention": None, "comparison": None, "title": title,
                "outcome_metrics": [], "study_design": {"design": "Rastgele Kontrollü Çalışma (RCT)"}}

    def test_missing_turkish_term_is_unknown_not_mismatch(self):
        query_pico = dict(rg.extract_pico("Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi azaltır mı?"),
                          _query_language="tr")
        a = self._study("Empagliflozin in heart failure with a preserved ejection fraction")
        b = self._study("Dapagliflozin in patients with heart failure and reduced ejection fraction")
        result = pico_compat.evaluate_pico_compatibility(a, b, query_pico)
        self.assertIsNone(result["pop_match"])
        self.assertFalse(any("uyuşmazlığı" in reason for reason in result["unmatched_reasons"]))

    def test_english_query_term_can_still_mismatch(self):
        query_pico = rg.extract_pico("Does empagliflozin reduce mortality in heart failure?")
        a = self._study("Empagliflozin in heart failure with a preserved ejection fraction")
        b = self._study("Statins in chronic kidney disease")
        result = pico_compat.evaluate_pico_compatibility(a, b, query_pico)
        self.assertFalse(result["pop_match"])


if __name__ == "__main__":
    unittest.main()


class SearchBoxHints(unittest.TestCase):
    def test_turkish_search_terms_are_detected(self):
        self.assertTrue(rg._is_turkish_query("Kalp yetersizliğinde SGLT2 inhibitörleri mortaliteyi azaltır mı?"))
        self.assertFalse(rg._is_turkish_query("SGLT2 inhibitors in heart failure with preserved ejection fraction"))

    def test_year_filter_is_not_capped_at_a_fixed_year(self):
        import os
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotRegex(source, r"max_value=20\d\d")
