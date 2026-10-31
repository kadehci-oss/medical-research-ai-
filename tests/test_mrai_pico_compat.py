"""B2 tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pico_compat as pc  # noqa: E402


def study(pop="adults with type 2 diabetes", intervention="empagliflozin", comparison="placebo",
          design_key="rct", design="Rastgele Kontroll\u00fc \u00c7al\u0131\u015fma (RCT)", outcomes=None):
    return {
        "patient_population": pop,
        "intervention": intervention,
        "comparison": comparison,
        "study_design": {"design_key": design_key, "design": design},
        "outcome_metrics": outcomes if outcomes is not None else [
            {"outcome": "all-cause mortality", "metrics": ["HR 0.7"], "sentence": "x"}
        ],
    }


class TermComparison(unittest.TestCase):
    def test_type1_vs_type2_diabetes_not_compatible(self):
        match, why = pc.compare_terms("patients with type 1 diabetes", "patients with type 2 diabetes")
        self.assertFalse(match)
        self.assertEqual(why, "numeric_conflict")

    def test_single_shared_word_is_not_enough(self):
        match, _ = pc.compare_terms("heart failure patients", "kidney failure patients")
        self.assertFalse(match)

    def test_same_population_matches(self):
        match, _ = pc.compare_terms("adults with type 2 diabetes", "patients with type 2 diabetes")
        self.assertTrue(match)

    def test_adult_vs_pediatric_conflict(self):
        match, why = pc.compare_terms("adult asthma", "pediatric asthma")
        self.assertFalse(match)
        self.assertEqual(why, "qualifier_conflict")

    def test_acute_vs_chronic_conflict(self):
        self.assertFalse(pc.compare_terms("acute pancreatitis", "chronic pancreatitis")[0])

    def test_unknown_is_none_not_true(self):
        for missing in ("", None, "Belirtilmedi", "Belirtilmemi\u015f"):
            with self.subTest(missing=missing):
                self.assertIsNone(pc.compare_terms(missing, "placebo")[0])
                self.assertIsNone(pc.compare_terms("placebo", missing)[0])

    def test_turkish_dotted_capital_i(self):
        self.assertTrue(pc.compare_terms("\u0130nme hastalar", "inme hastalar")[0])


    def test_sample_size_is_not_a_subtype(self):
        self.assertTrue(pc.compare_terms("hastalar kalp yetersizli\u011fi (n=4000)",
                                         "hastalar kalp yetersizli\u011fi (n=4500)")[0])
        self.assertTrue(pc.compare_terms("4000 patients with heart failure", "4500 patients with heart failure")[0])

    def test_t1dm_vs_type_2(self):
        self.assertFalse(pc.compare_terms("adults with T1DM", "adults with type 2 diabetes")[0])

    def test_nyha_class_conflict(self):
        self.assertFalse(pc.compare_terms("heart failure NYHA class II", "heart failure NYHA class IV")[0])

    def test_plural_stemming(self):
        self.assertTrue(pc.compare_terms("SGLT2 inhibitors", "SGLT2 inhibitor")[0])


class DesignClass(unittest.TestCase):
    def test_key_preferred_over_label(self):
        self.assertEqual(pc.design_class({"design_key": "cohort", "design": "RCT"}), "cohort")

    def test_label_fallback(self):
        self.assertEqual(pc.design_class("Vaka-Kontrol \u00c7al\u0131\u015fmas\u0131"), "case_control")

    def test_unknown(self):
        self.assertIsNone(pc.design_class({"design": "\u00c7al\u0131\u015fma tasar\u0131m\u0131 belirlenemedi"}))
        self.assertIsNone(pc.design_class(None))


class OutcomeMatching(unittest.TestCase):
    def test_matches_by_name_and_returns_entries(self):
        a = [{"outcome": "all-cause mortality"}, {"outcome": "stroke"}]
        b = [{"outcome": "stroke"}, {"outcome": "all-cause mortality"}]
        pairs = pc.match_outcomes(a, b)
        self.assertEqual(len(pairs), 2)
        for e1, e2 in pairs:
            self.assertEqual(e1["outcome"], e2["outcome"])

    def test_cardiovascular_vs_all_cause_not_matched(self):
        self.assertEqual(pc.match_outcomes([{"outcome": "cardiovascular mortality"}],
                                           [{"outcome": "all-cause mortality"}]), [])

    def test_generic_labels_never_match(self):
        generic = "Genel sonlan\u0131m / \u00d6zet istatisti\u011fi"
        self.assertEqual(pc.match_outcomes([{"outcome": generic}], [{"outcome": generic}]), [])
        self.assertEqual(pc.match_outcomes([{"outcome": "Primer Klinik Sonlan\u0131m \u00d6l\u00e7\u00fct\u00fc"}],
                                           [{"outcome": "mortality"}]), [])

    def test_no_first_outcome_fallback(self):
        self.assertEqual(pc.match_outcomes([{"outcome": "mortality"}], [{"outcome": "pain score"}]), [])


class Compatibility(unittest.TestCase):
    def test_identical_setup_is_compatible(self):
        r = pc.evaluate_pico_compatibility(study(), study())
        self.assertTrue(r["compatible"], r["unmatched_reasons"])
        self.assertEqual(r["matching_outcomes"], ["all-cause mortality"])
        self.assertEqual(len(r["outcome_pairs"]), 1)

    def test_type1_vs_type2_incompatible(self):
        r = pc.evaluate_pico_compatibility(study(pop="adults with type 1 diabetes"), study())
        self.assertFalse(r["compatible"])
        self.assertIs(r["pop_match"], False)

    def test_missing_comparator_is_not_compatible(self):
        r = pc.evaluate_pico_compatibility(study(comparison="Belirtilmedi"), study())
        self.assertFalse(r["compatible"])
        self.assertIsNone(r["comp_match"])
        self.assertIn("Kar\u015f\u0131la\u015ft\u0131r\u0131c\u0131", r["unknown_fields"])

    def test_rct_vs_case_control_incompatible(self):
        r = pc.evaluate_pico_compatibility(
            study(), study(design_key="case_control", design="Vaka-Kontrol \u00c7al\u0131\u015fmas\u0131"))
        self.assertFalse(r["compatible"])
        self.assertFalse(r["design_compatible"])

    def test_no_shared_outcome_is_incompatible(self):
        r = pc.evaluate_pico_compatibility(
            study(), study(outcomes=[{"outcome": "pain score", "metrics": [], "sentence": ""}]))
        self.assertFalse(r["compatible"])
        self.assertEqual(r["outcome_pairs"], [])

    def test_unknown_intervention_resolved_from_query_term(self):
        a = study(intervention="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "SGLT2 inhibitor reduced all-cause mortality"}])
        b = study(intervention="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "SGLT2 inhibitors lowered all-cause mortality"}])
        no_query = pc.evaluate_pico_compatibility(a, b)
        self.assertFalse(no_query["compatible"])
        r = pc.evaluate_pico_compatibility(a, b, {"intervention": "SGLT2 inhibitors"})
        self.assertTrue(r["compatible"], r["unmatched_reasons"])
        self.assertTrue(r["notes"])

    def test_query_term_must_appear_in_both_studies(self):
        a = study(intervention="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "SGLT2 inhibitor reduced all-cause mortality"}])
        b = study(intervention="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "Metformin reduced all-cause mortality"}])
        r = pc.evaluate_pico_compatibility(a, b, {"intervention": "SGLT2 inhibitors"})
        self.assertFalse(r["compatible"])

    def test_known_value_checked_against_query(self):
        a = study(intervention="metformin")
        b = study(intervention="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "SGLT2 inhibitor reduced all-cause mortality"}])
        r = pc.evaluate_pico_compatibility(a, b, {"intervention": "SGLT2 inhibitors"})
        self.assertFalse(r["compatible"])
        self.assertIs(r["int_match"], False)

    def test_translated_value_matches_query_through_the_abstract(self):
        a = study(intervention="Belirtilmedi", outcomes=[{"outcome": "depression",
                  "sentence": "Drug X significantly reduced depression symptoms"}])
        b = study(intervention="ila\u00e7 X", outcomes=[{"outcome": "depression",
                  "sentence": "Drug X failed to show significant difference"}])
        r = pc.evaluate_pico_compatibility(a, b, {"intervention": "Drug X"})
        self.assertIs(r["int_match"], True, r["unmatched_reasons"])

    def test_query_fallback_does_not_hide_a_subtype_clash(self):
        a = study(pop="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "In patients with type 1 diabetes, drug reduced all-cause mortality"}])
        b = study(pop="hastalar tip 2 diyabet (n=600)", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "In patients with type 2 diabetes, drug reduced all-cause mortality"}])
        r = pc.evaluate_pico_compatibility(a, b, {"population": "diabetes"})
        self.assertIs(r["pop_match"], False)
        self.assertFalse(r["compatible"])

    def test_query_fallback_does_not_hide_adult_vs_child(self):
        a = study(pop="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "In children with asthma, drug reduced all-cause mortality"}])
        b = study(pop="Belirtilmedi", outcomes=[{"outcome": "all-cause mortality",
                  "sentence": "In adults with asthma, drug reduced all-cause mortality"}])
        r = pc.evaluate_pico_compatibility(a, b, {"population": "asthma"})
        self.assertIs(r["pop_match"], False)

    def test_old_keys_still_present(self):
        r = pc.evaluate_pico_compatibility(study(), study())
        for key in ("compatible", "matching_outcomes", "unmatched_reasons",
                    "pop_match", "int_match", "comp_match"):
            self.assertIn(key, r)


if __name__ == "__main__":
    unittest.main()
