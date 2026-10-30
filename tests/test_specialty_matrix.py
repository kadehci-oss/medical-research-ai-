import json
import tempfile
import unittest
from pathlib import Path

from specialty_matrix import (
    detect_specialty,
    enhance_query_with_specialty,
    load_specialty_matrix,
)


class TestSpecialtyMatrix(unittest.TestCase):
    def test_real_matrix_loads_88_specialties(self):
        matrix = load_specialty_matrix()
        self.assertNotIn("error", matrix)
        self.assertEqual(len(matrix["specialties"]), 88)
        self.assertEqual(matrix["total_specialties"], 88)

    def test_missing_matrix_degrades_gracefully(self):
        missing = load_specialty_matrix("/tmp/does-not-exist-specialty-matrix.json")
        self.assertEqual(missing["specialties"], [])
        self.assertIn("error", missing)
        self.assertIsNone(detect_specialty("heart failure", path="/tmp/does-not-exist-specialty-matrix.json"))
        enhanced = enhance_query_with_specialty("heart failure", path="/tmp/does-not-exist-specialty-matrix.json")
        self.assertEqual(enhanced["enhanced_query"], "heart failure")
        self.assertFalse(enhanced["applied"])
        self.assertEqual(enhanced["strategy"], "matrix_unavailable")

    def test_malformed_matrix_degrades_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matrix.json"
            path.write_text("{ not json", encoding="utf-8")
            loaded = load_specialty_matrix(str(path))
            self.assertEqual(loaded["specialties"], [])
            self.assertIn("Malformed", loaded["error"])

            path.write_text("[]", encoding="utf-8")
            loaded = load_specialty_matrix(str(path))
            self.assertIn("specialties list", loaded["error"])

            path.write_text(json.dumps({
                "specialties": [
                    "not-a-record",
                    {
                        "id": "kardiyoloji",
                        "specialty_name": "Kardiyoloji",
                        "specialty_name_en": "Cardiology",
                        "search_keywords": ["heart failure", "clinical research"],
                    },
                ]
            }), encoding="utf-8")
            detected = detect_specialty("heart failure", path=str(path))
            self.assertEqual(detected["id"], "kardiyoloji")

    def test_generic_keywords_do_not_select_a_specialty(self):
        self.assertIsNone(detect_specialty("clinical research evidence synthesis pubmed"))

    def test_detects_expected_specialties_for_clinical_questions(self):
        cases = {
            "HFpEF + SGLT2 inhibitors": "kardiyoloji",
            "GLP-1 agonists in type 2 diabetes": "endokrinoloji_ve_metabolizma",
            "CRISPR in sickle cell disease": "hematoloji",
            "psilocybin for major depressive disorder": "ruh_sagligi_ve_psikiyatri",
            "febrile seizure in children": "cocuk_norolojisi",
            "seizure in children": "cocuk_norolojisi",
            "heart failure": "kardiyoloji",
        }
        for query, specialty_id in cases.items():
            detected = detect_specialty(query)
            self.assertIsNotNone(detected, query)
            self.assertEqual(detected["id"], specialty_id, query)

        sickle = detect_specialty("CRISPR in sickle cell disease")
        self.assertIn("tibbi_biyoteknoloji", [item["id"] for item in sickle["alternatives"]])

    def test_enhancement_preserves_original_terms_and_skips_boolean_queries(self):
        query = "HFpEF SGLT2 inhibitors"
        enhanced = enhance_query_with_specialty(query)
        self.assertTrue(enhanced["applied"])
        self.assertEqual(enhanced["strategy"], "synonym_or_expansion")
        for token in query.split():
            self.assertIn(token, enhanced["enhanced_query"])
        self.assertIn("heart failure with preserved ejection fraction", enhanced["enhanced_query"])
        self.assertIn("sodium-glucose cotransporter 2", enhanced["enhanced_query"])
        self.assertNotIn(" AND ", enhanced["enhanced_query"])
        self.assertNotIn("cardiology[mesh]", enhanced["enhanced_query"].lower())

        boolean = enhance_query_with_specialty("HFpEF AND SGLT2 inhibitors")
        self.assertEqual(boolean["enhanced_query"], "HFpEF AND SGLT2 inhibitors")
        self.assertFalse(boolean["applied"])
        self.assertEqual(boolean["strategy"], "preserved_boolean_query")
        self.assertEqual(boolean["specialty"]["id"], "kardiyoloji")

        disabled = enhance_query_with_specialty(query, apply=False)
        self.assertEqual(disabled["enhanced_query"], query)
        self.assertEqual(disabled["strategy"], "disabled")
        self.assertEqual(disabled["specialty"]["id"], "kardiyoloji")

    def test_queries_without_abbreviations_are_not_rewritten(self):
        for query in (
            "psilocybin for major depressive disorder",
            "febrile seizure in children",
            "CRISPR in sickle cell disease",
        ):
            enhanced = enhance_query_with_specialty(query)
            self.assertEqual(enhanced["enhanced_query"], query, query)
            self.assertFalse(enhanced["applied"], query)
            self.assertIsNotNone(enhanced["specialty"], query)


if __name__ == "__main__":
    unittest.main()
