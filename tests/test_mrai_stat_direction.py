"""B1 tests. Runs under pytest and plain unittest."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import stat_direction as sd  # noqa: E402


def _legacy_is_significant(p_metrics):
    """Copy of the old substring check, kept only to document the bug."""
    return any(
        "< 0.0" in p or "= 0.0" in p or "=0.0" in p or "<0.0" in p for p in p_metrics
    )


def _legacy_direction(sentence):
    """Copy of the old verb order (positive list is checked first)."""
    s = sentence.lower()
    if any(t in s for t in ["reduced", "prolonged", "improved", "increase", "higher",
                            "lower", "decreased", "effective", "benefit"]):
        return "positive"
    if any(t in s for t in ["increased risk", "adverse", "mortality", "harmful", "worsened"]):
        return "negative"
    return "positive"


class LegacyBugDocumentation(unittest.TestCase):
    def test_old_logic_called_p_008_significant(self):
        self.assertTrue(_legacy_is_significant(["p = 0.08"]))

    def test_old_logic_called_increased_risk_positive(self):
        self.assertEqual(_legacy_direction("Treatment X increased the risk of death"), "positive")


class PValues(unittest.TestCase):
    def test_p_008_is_not_significant(self):
        self.assertEqual(sd.p_significance(sd.parse_p_values("p = 0.08")), (False, False))

    def test_boundary_049_and_05(self):
        self.assertEqual(sd.p_significance(sd.parse_p_values("p = 0.049"))[0], True)
        self.assertEqual(sd.p_significance(sd.parse_p_values("p = 0.05"))[0], False)

    def test_less_than_forms(self):
        for text in ("p < 0.001", "P<0.05", "p < .001", "p-value < 0.01", "p \u2264 0.05"):
            with self.subTest(text=text):
                self.assertTrue(sd.p_significance(sd.parse_p_values(text))[0])

    def test_unhelpful_bounds_are_unknown(self):
        self.assertIsNone(sd.p_significance(sd.parse_p_values("p < 0.1"))[0])
        self.assertIsNone(sd.p_significance(sd.parse_p_values("p > 0.01"))[0])

    def test_greater_than(self):
        self.assertEqual(sd.p_significance(sd.parse_p_values("p > 0.05"))[0], False)
        self.assertEqual(sd.p_significance(sd.parse_p_values("p \u2265 0.05"))[0], False)

    def test_mixed_p_values_flagged(self):
        sig, mixed = sd.p_significance(sd.parse_p_values("p < 0.001 and p = 0.4"))
        self.assertIsNone(sig)
        self.assertTrue(mixed)

    def test_no_false_p_in_words(self):
        self.assertEqual(sd.parse_p_values("group = 3, up = 5, PMID = 123"), [])


class Estimates(unittest.TestCase):
    def test_ci_forms(self):
        self.assertEqual(sd.parse_ci("(95% CI 0.62-1.15)"), (0.62, 1.15))
        self.assertEqual(sd.parse_ci("95% CI: 0.62 to 1.15"), (0.62, 1.15))
        self.assertEqual(sd.parse_ci("95% CI [0.62, 1.15]"), (0.62, 1.15))
        self.assertEqual(sd.parse_ci("95% CI -1.0 to -0.6"), (-1.0, -0.6))

    def test_bare_ci_strings(self):
        self.assertEqual(sd.parse_ci_strings(["0.62-1.15"]), (0.62, 1.15))
        self.assertIsNone(sd.parse_ci_strings(["n = 120"]))

    def test_ratio(self):
        self.assertEqual(sd.parse_ratio("HR 0.68 (95% CI 0.57-0.82)"), ("HR", 0.68))
        self.assertEqual(sd.parse_ratio("adjusted aOR = 2.1"), ("OR", 2.1))
        self.assertEqual(sd.parse_ratio("hazard ratio, 0.75"), ("HR", 0.75))
        self.assertEqual(sd.parse_ratio("relative risk of 1.4"), ("RR", 1.4))

    def test_lowercase_or_is_not_a_ratio(self):
        self.assertIsNone(sd.parse_ratio("tested in 2 or 3 patients"))

    def test_mean_difference(self):
        self.assertEqual(sd.parse_mean_difference("MD -0.8%, 95% CI"), -0.8)
        self.assertEqual(sd.parse_mean_difference("mean difference of 1.5"), 1.5)


class Direction(unittest.TestCase):
    def label(self, sentence, outcome="", metrics=None):
        return sd.assess_direction(sentence, metrics, outcome)["label"]

    def test_increased_risk_of_death_is_harm(self):
        self.assertEqual(
            self.label("Treatment X increased the risk of death (HR 1.4, 95% CI 1.1-1.8, p = 0.003)", "mortality"),
            sd.LABEL_HARM,
        )

    def test_reduced_mortality_is_benefit(self):
        self.assertEqual(
            self.label("Empagliflozin reduced all-cause mortality (HR 0.68; 95% CI 0.57-0.82; p<0.001)",
                       "all-cause mortality"),
            sd.LABEL_BENEFIT,
        )

    def test_no_significant_difference_is_neutral(self):
        self.assertEqual(self.label("No significant difference was observed (p = 0.08)", "mortality"),
                         sd.LABEL_NEUTRAL)

    def test_did_not_reduce_is_neutral(self):
        self.assertEqual(self.label("Treatment did not reduce mortality (p=0.4)", "mortality"),
                         sd.LABEL_NEUTRAL)

    def test_higher_remission_is_benefit(self):
        self.assertEqual(self.label("Higher remission rate (OR 2.1, 95% CI 1.2-3.6)", "remission"),
                         sd.LABEL_BENEFIT)

    def test_hazard_ratio_on_survival_is_benefit_when_below_one(self):
        self.assertEqual(self.label("Overall survival improved (HR 0.80, 95% CI 0.65-0.98)", "overall survival"),
                         sd.LABEL_BENEFIT)

    def test_median_survival_longer_is_benefit_without_hr(self):
        self.assertEqual(self.label("Treatment significantly increased survival (p = 0.01)", "survival"),
                         sd.LABEL_BENEFIT)

    def test_hba1c_mean_difference(self):
        self.assertEqual(
            self.label("Significant reduction in HbA1c (MD -0.8%, 95% CI -1.0 to -0.6, p<0.001)", "HbA1c"),
            sd.LABEL_BENEFIT,
        )

    def test_verb_only_reduction_in_mortality(self):
        self.assertEqual(self.label("Drug A significantly reduced mortality (p<0.001)", "mortality"),
                         sd.LABEL_BENEFIT)

    def test_verb_only_increased_bleeding(self):
        self.assertEqual(self.label("Increased risk of bleeding (p=0.01)", "bleeding"), sd.LABEL_HARM)

    def test_generic_outcome_uses_sentence_polarity(self):
        self.assertEqual(
            self.label("Reduced mortality (p<0.001)", "genel sonlan\u0131m / \u00f6zet istatisti\u011fi"),
            sd.LABEL_BENEFIT,
        )

    def test_unknown_polarity_is_significant_unclear(self):
        self.assertEqual(self.label("Increased the score (p < 0.001)", "composite index"),
                         sd.LABEL_SIG_UNCLEAR)

    def test_no_numbers_is_uncertain(self):
        self.assertEqual(self.label("Drug A improved outcomes", "mortality"), sd.LABEL_UNCERTAIN)

    def test_p_and_ci_conflict_is_uncertain(self):
        self.assertEqual(self.label("Mortality was lower (HR 0.9, 95% CI 0.7-1.2, p = 0.03)", "mortality"),
                         sd.LABEL_UNCERTAIN)

    def test_text_says_no_difference_but_numbers_significant_is_uncertain(self):
        self.assertEqual(self.label("No significant difference (HR 0.5, 95% CI 0.3-0.7, p < 0.001)", "mortality"),
                         sd.LABEL_UNCERTAIN)

    def test_both_directions_in_one_sentence_is_significant_unclear(self):
        self.assertEqual(self.label("Raised HDL but reduced adherence (p<0.01)", "adherence"),
                         sd.LABEL_SIG_UNCLEAR)

    def test_ratio_and_verb_disagree_is_significant_unclear(self):
        # OR 2.15 is probably the odds of response, but the text says symptoms were reduced.
        self.assertEqual(
            self.label("Drug X significantly reduced depression symptoms compared to placebo "
                       "(OR 2.15, 95% CI 1.40-3.30, p<0.001).", "depression symptoms"),
            sd.LABEL_SIG_UNCLEAR,
        )

    def test_hospitalization_reduction_with_hr(self):
        self.assertEqual(
            self.label("SGLT2 inhibitor reduced heart failure hospitalization compared to placebo "
                       "(HR 0.75, 95% CI 0.65-0.87, p<0.001).", "hospitalization"),
            sd.LABEL_BENEFIT,
        )

    def test_opposite_outcomes_do_not_look_consistent(self):
        a = sd.determine_direction({"outcome": "mortality", "metrics": ["HR 0.7", "p < 0.001"],
                                    "sentence": "Reduced mortality"})
        b = sd.determine_direction({"outcome": "mortality", "metrics": ["HR 1.4", "p < 0.001"],
                                    "sentence": "Increased mortality"})
        self.assertEqual((a, b), (sd.LABEL_BENEFIT, sd.LABEL_HARM))
        self.assertNotEqual(a, b)

    def test_empty_entry(self):
        self.assertEqual(sd.determine_direction({}), sd.LABEL_UNCERTAIN)
        self.assertEqual(sd.determine_direction(None), sd.LABEL_UNCERTAIN)


if __name__ == "__main__":
    unittest.main()
