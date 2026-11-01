"""Fixes made after the third held-out set was frozen.

Each case is a sentence from one of the 17 records in validation/pubmed_records_holdout3.json
(PMID in the test name). The frozen first run in validation/holdout3_first_run_results.json
records how the engine did before these fixes.
"""
import json
import os
import unittest

import evidence_model as em
import report_generator as rg

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(HERE, "validation", "pubmed_records_holdout3.json"), encoding="utf-8") as fh:
    RECORDS = {r["pmid"]: r for r in json.load(fh)}


def _study(pmid):
    em.clear_cache()
    return em.build_study(RECORDS[pmid])


def _by_value(study):
    return {e.value: e for e in study.estimates}


class NoCausalLanguageForNonRandomizedComparisons(unittest.TestCase):
    def test_trial_emulation_is_not_a_trial_42965030(self):
        study = _study("42965030")
        self.assertEqual(study.design_key, "cohort")
        self.assertFalse(study.causal_inference_allowed)

    def test_secondary_analysis_of_non_randomized_factors_42937536_42963818(self):
        for pmid in ("42937536", "42963818"):
            study = _study(pmid)
            self.assertEqual(study.report_role, "secondary_analysis", pmid)
            self.assertFalse(study.causal_inference_allowed, pmid)

    def test_secondary_analysis_comparing_randomized_arms_stays_causal(self):
        em.clear_cache()
        article = {"pmid": "1", "title": "Empagliflozin and albuminuria: a secondary analysis of a randomized trial",
                   "publication_types": ["Randomized Controlled Trial"],
                   "abstract": ("This secondary analysis of the EMPEROR trial included 9673 patients. Treatment with "
                                "empagliflozin was associated with lower incidence of new macroalbuminuria compared with "
                                "placebo (HR, 0.81; 95% CI, 0.70-0.94).")}
        self.assertTrue(em.build_study(article).causal_inference_allowed)


class ListsBindEachValueToItsOwnName(unittest.TestCase):
    def test_exposures_before_a_sentence_final_outcome_42921063(self):
        by_value = _by_value(_study("42921063"))
        for value in (3.01, 3.72, 2.14, 16.6):
            self.assertEqual(by_value[value].outcome_name, "GDM", value)
        self.assertIn("preconception body mass index", by_value[3.01].outcome_basis)
        self.assertEqual(by_value[2.92].outcome_name, "cesarean delivery")
        self.assertEqual(by_value[4.11].outcome_name, "need for induction of labor")
        self.assertIn("neonatal intensive care unit", by_value[5.68].outcome_name)

    def test_semicolon_list_with_for_after_each_value_42963493(self):
        by_value = _by_value(_study("42963493"))
        self.assertEqual(by_value[0.49].outcome_name, "NEC")
        self.assertEqual(by_value[0.87].outcome_name, "LOS")
        self.assertEqual(by_value[0.67].outcome_name, "all-cause mortality")

    def test_crude_and_adjusted_irr_42963818(self):
        study = _study("42963818")
        self.assertEqual(len([e for e in study.estimates if e.measure == "IRR"]), 5)
        self.assertTrue(all(e.outcome_name == "missed VDOT sessions" for e in study.estimates))

    def test_covariate_and_comparator_lists_are_not_outcomes(self):
        self.assertEqual(_by_value(_study("42959821"))[0.77].outcome_name.lower().count("body mass index"), 0)
        by_value = _by_value(_study("42961418"))
        self.assertNotIn("mammography", by_value[0.16].outcome_name)
        self.assertIn("mortality", by_value[0.16].outcome_name)

    def test_subject_outcome_with_exposure_after_associated_with_42937536(self):
        self.assertEqual(_by_value(_study("42937536"))[1.24].outcome_name.lower(), "mortality")

    def test_risk_phrases_after_the_bracket_42965030(self):
        by_value = _by_value(_study("42965030"))
        self.assertEqual(by_value[0.35].outcome_name, "SSE")
        self.assertEqual(by_value[0.43].outcome_name, "major bleeding")


class CountsAndMeasures(unittest.TestCase):
    def test_case_count_is_not_a_time_window_42959821(self):
        study = _study("42959821")
        self.assertEqual((study.population.n_cases, study.population.n_total), (17, 117))

    def test_analysed_population_of_a_secondary_report_42937536(self):
        self.assertEqual(_study("42937536").population.n_total, 21856)

    def test_participants_sentence_42965524(self):
        self.assertEqual(_study("42965524").population.n_total, 46)

    def test_slash_paired_ppv_npv_42945222(self):
        found = {(e.measure, e.value) for e in _study("42945222").estimates}
        self.assertIn(("PPV", 86.1), found)
        self.assertIn(("NPV", 46.2), found)
        self.assertNotIn(("NPV", 86.1), found)

    def test_degree_difference_is_a_mean_difference_42966369(self):
        est = _by_value(_study("42966369"))[-3.23]
        self.assertEqual((est.measure, est.ci_low, est.ci_high), ("MD", -3.51, -2.96))

    def test_p_value_is_not_imported_as_an_estimate_42963493(self):
        self.assertNotIn(0.001, {e.value for e in _study("42963493").estimates})


class TargetsAndArms(unittest.TestCase):
    def test_diagnostic_target_from_title_or_aim(self):
        self.assertIn("tuberculosis", _by_value(_study("42945222"))[0.675].outcome_name.lower())
        self.assertIn("stenosis", _by_value(_study("42965524"))[90.1].outcome_name.lower())
        self.assertIn("amyloid", _by_value(_study("42957617"))[0.73].outcome_name.lower())

    def test_title_order_keeps_laparoscopic_as_intervention_42944929(self):
        study = _study("42944929")
        self.assertIn("laparoscopic", study.interventions[0].name.lower())
        self.assertEqual(study.comparators[0].name.lower(), "open")

    def test_allocation_pair_and_background_bracing_42966369(self):
        study = _study("42966369")
        self.assertIn("PSSE", study.interventions[0].name)
        self.assertIn("self-directed", study.comparators[0].name)
        self.assertTrue(any("brac" in c.name for c in study.co_treatments))

    def test_study_level_names_carry_a_verified_source(self):
        for pmid in ("42965526", "42945222", "42963493", "42961418", "42965524"):
            study = _study(pmid)
            self.assertTrue(study.interventions, pmid)
            self.assertEqual(study.interventions[0].source.verification_status, em.SOURCE_VERIFIED, pmid)


if __name__ == "__main__":
    unittest.main()
