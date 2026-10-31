"""B3 tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import grade_rules as gr  # noqa: E402


class RiskOfBias(unittest.TestCase):
    def test_double_blind_alone_is_not_reassurance(self):
        self.assertEqual(gr.risk_of_bias("A double-blind trial.")["status"], gr.NOT_ASSESSABLE)

    def test_open_label_is_serious(self):
        self.assertEqual(gr.risk_of_bias("An open-label trial.")["status"], gr.SERIOUS)

    def test_explicit_low_risk(self):
        self.assertEqual(gr.risk_of_bias("Low risk of bias was judged.")["status"], gr.NO_DOWNGRADE)

    def test_nothing_said(self):
        self.assertEqual(gr.risk_of_bias("We enrolled patients.")["status"], gr.NOT_ASSESSABLE)


class Imprecision(unittest.TestCase):
    def test_ci_crossing_one_is_serious(self):
        r = gr.imprecision("HR 0.85 (95% CI 0.62-1.15)")
        self.assertEqual(r["status"], gr.SERIOUS)
        self.assertIn("1", r["reason"])

    def test_old_rule_missed_this_case(self):
        low, high = 0.62, 1.15
        self.assertLess(high / low, 3)  # old spread rule: no downgrade

    def test_narrow_ci_excluding_one(self):
        self.assertEqual(gr.imprecision("HR 0.68 (95% CI 0.57-0.82)")["status"], gr.NO_DOWNGRADE)

    def test_wide_ci_excluding_one(self):
        self.assertEqual(gr.imprecision("OR 2.0 (95% CI 1.1-6.5)")["status"], gr.SERIOUS)

    def test_ci_without_ratio_measure_is_not_assessed(self):
        self.assertEqual(gr.imprecision("mean 12 (95% CI 0.5-2.5)")["status"], gr.NOT_ASSESSABLE)

    def test_no_ci(self):
        self.assertEqual(gr.imprecision("No interval reported.")["status"], gr.NOT_ASSESSABLE)

    def test_explicit_phrase(self):
        self.assertEqual(gr.imprecision("The trial was underpowered.")["status"], gr.SERIOUS)

    def test_ci_strings_argument(self):
        self.assertEqual(gr.imprecision("HR 0.85", ["0.62-1.15"])["status"], gr.SERIOUS)


class Ceiling(unittest.TestCase):
    def domains(self, rob, imp):
        return {"risk_of_bias": {"status": rob}, "imprecision": {"status": imp}}

    def test_rct_with_nothing_assessed_gets_no_level(self):
        r = gr.apply_ceiling(4, self.domains(gr.NOT_ASSESSABLE, gr.NOT_ASSESSABLE))
        self.assertEqual(r["preliminary_level"], gr.NOT_ASSESSABLE)
        self.assertEqual(r["upper_bound_level"], "Y\u00fcksek")
        self.assertIn("risk_of_bias", r["reason"])

    def test_one_critical_domain_missing_still_no_level(self):
        r = gr.apply_ceiling(4, self.domains(gr.NO_DOWNGRADE, gr.NOT_ASSESSABLE))
        self.assertEqual(r["preliminary_level"], gr.NOT_ASSESSABLE)

    def test_all_assessed_no_downgrade(self):
        r = gr.apply_ceiling(4, self.domains(gr.NO_DOWNGRADE, gr.NO_DOWNGRADE))
        self.assertEqual(r["preliminary_level"], "Y\u00fcksek")

    def test_downgrades_reduce_level(self):
        r = gr.apply_ceiling(4, self.domains(gr.SERIOUS, gr.SERIOUS))
        self.assertEqual(r["preliminary_level"], "D\u00fc\u015f\u00fck")

    def test_upper_bound_accounts_for_confirmed_downgrades(self):
        r = gr.apply_ceiling(4, self.domains(gr.SERIOUS, gr.NOT_ASSESSABLE))
        self.assertEqual(r["upper_bound_level"], "Orta")

    def test_floor_is_very_low(self):
        d = self.domains(gr.SERIOUS, gr.SERIOUS)
        d["inconsistency"] = {"status": gr.SERIOUS}
        self.assertEqual(gr.apply_ceiling(2, d)["preliminary_level"], "\u00c7ok d\u00fc\u015f\u00fck")

    def test_no_start_score(self):
        self.assertEqual(gr.apply_ceiling(None, {})["preliminary_level"], gr.NOT_ASSESSABLE)



class ImprecisionFromCi(unittest.TestCase):
    def test_ignores_phrases(self):
        # phrase handling stays in the patched module (with negation support)
        self.assertEqual(gr.imprecision_from_ci("underpowered")["status"], gr.NOT_ASSESSABLE)

    def test_crossing_one(self):
        self.assertEqual(gr.imprecision_from_ci("HR 0.85", ["95% CI 0.62-1.15"])["status"], gr.SERIOUS)


if __name__ == "__main__":
    unittest.main()
