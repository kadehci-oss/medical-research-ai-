"""Category 3 — independent clinical data validation against the reference tables.

Runs the same comparison as validation/run_multispecialty_validation.py. Thresholds
are regression guards; the honest accuracy estimate is the frozen first run on
the held-out set (validation/holdout_first_run_results.json), reported in
validation/MULTISPECIALTY_VALIDATION_REPORT.md.
"""
import json
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "validation"))

import run_multispecialty_validation as validation  # noqa: E402


class TestClinicalReferenceValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = validation.run_all()

    def _check(self, res, min_complete, max_false):
        overall = res["overall"]
        self.assertGreaterEqual(overall["complete_rate"], min_complete, res["study_details"])
        self.assertLessEqual(overall["false_rate"], max_false, res["study_details"])
        self.assertEqual(res["source_match"]["source_match_accuracy"], 1.0, res["source_match"]["failures"])
        self.assertEqual(res["source_match"]["value_match_accuracy"], 1.0, res["source_match"]["failures"])
        self.assertEqual(res["false_causal_claims"], 0, res["false_causal_language_hits"])
        self.assertEqual(res["sample_size_confused_with_event_or_arm_count"], [])
        self.assertEqual(res["background_therapy_reported_as_intervention"], 0)
        self.assertEqual(res["independence_errors"], [])
        for specialty, row in res["report_verification_by_specialty"].items():
            self.assertEqual(row["unknown_pmids"], [], specialty)
            self.assertEqual(row["quotes_failed"], 0, specialty)
            self.assertEqual(row["rob_rating_claims"] + row["grade_rating_claims"], 0, specialty)

    def test_development_set(self):
        self._check(self.results["development"], min_complete=0.95, max_false=0.02)

    def test_holdout_set_current_run(self):
        self._check(self.results["holdout_current"], min_complete=0.90, max_false=0.05)

    def test_frozen_holdout_first_run_is_recorded_unchanged(self):
        frozen = self.results["holdout_first_run"]
        self.assertIsNotNone(frozen)
        self.assertEqual(frozen["n_studies"], 16)
        self.assertEqual(frozen["overall"]["complete"], 53)
        self.assertEqual(frozen["overall"]["reference_items"], 68)
        self.assertEqual(frozen["overall"]["false"], 5)
        self.assertEqual(frozen["false_causal_claims"], 0)

    def test_every_specialty_is_reported(self):
        for key in ("development", "holdout_current"):
            self.assertEqual(len(self.results[key]["per_specialty"]), 8, key)

    def test_question_framework_selection(self):
        for key in ("development", "holdout_current"):
            fw = self.results[key]["question_framework"]
            self.assertEqual(fw["correct"], fw["total"], fw["rows"])

    def test_committed_report_matches_current_engine(self):
        """The committed Markdown report must be regenerated whenever the engine changes."""
        expected = validation.render_combined_markdown(self.results)
        with open(validation.REPORT_PATH, encoding="utf-8") as handle:
            committed = handle.read()
        strip = lambda text: "\n".join(l for l in text.splitlines() if not l.startswith("Oluşturulma:"))
        self.assertEqual(strip(committed), strip(expected),
                         "Run: python validation/run_multispecialty_validation.py")


if __name__ == "__main__":
    unittest.main()
