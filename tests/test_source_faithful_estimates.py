"""Estimates stay faithful to the source sentence.

Each case is a sentence from a real PubMed abstract (PMID in the test name or
comment) where an earlier version bound a value to the wrong outcome, read a
non-estimate as an estimate, or described a p-value as something it is not.
"""
import unittest

import evidence_model as em
import report_generator as rg


def _study(abstract, types=("Randomized Controlled Trial",), title="Trial", pmid="1"):
    em.clear_cache()
    article = {"pmid": pmid, "title": title, "abstract": abstract, "publication_types": list(types)}
    return em.build_study(article), article


TWILIGHT_LIKE = (  # PMID 41631724
    "From July 24, 2020, to Sept 25, 2023, 4897 patients were enrolled (1598 in the HBR stratum and 3299 in the "
    "non-HBR stratum). In the HBR stratum, 1-month compared with 3-month DAPT did not reach non-inferiority for net "
    "adverse clinical events (144 [18.4%] of 798 vs 110 [14.0%] of 800 patients; hazard ratio [HR] 1.337 [95% CI "
    "1.043-1.713]; p=0.82 for non-inferiority). In the non-HBR stratum, 3-month was non-inferior to 12-month DAPT "
    "regarding net adverse clinical events (47 [2.9%] of 1649 vs 72 [4.4%] of 1650 patients; HR 0.657 [0.455-0.949]; "
    "p<0.0001 for non-inferiority) and major adverse cardiac or cerebral events (36 [2.2%] vs 37 [2.3%]; HR 0.984 "
    "[0.622-1.558]; p=0.0082 for non-inferiority), and superior for bleeding (120 [7.4%] vs 190 [11.7%]; HR 0.631 "
    "[0.502-0.793]; p<0.0001)."
)


class NonInferiorityPValues(unittest.TestCase):
    def test_p_value_is_labelled_as_a_non_inferiority_test(self):
        study, _ = _study(TWILIGHT_LIKE)
        by_value = {e.value: e for e in study.estimates}
        self.assertIn("non-inferiority", by_value[1.337].p_value)
        self.assertIn("non-inferiority", by_value[0.984].p_value)
        self.assertNotIn("non-inferiority", by_value[0.631].p_value)  # "superior for bleeding": an ordinary p

    def test_non_inferiority_p_is_not_read_as_a_difference(self):
        item = {"p": "p = 0.82 (non-inferiority testi)", "ci_low": "", "ci_high": "", "effect": "HR 1.337"}
        self.assertEqual(rg._finding_significance_flags(item)[0], "")
        legacy = {"p": "p = 0.82", "sentence": "HR 1.337 [95% CI 1.043-1.713]; p=0.82 for non-inferiority",
                  "effect": "HR 1.337"}
        self.assertEqual(rg._finding_significance_flags(legacy)[0], "")


class StrataAndConjunctOutcomes(unittest.TestCase):
    def test_stratum_is_kept_with_each_estimate(self):
        study, article = _study(TWILIGHT_LIKE)
        by_value = {e.value: e for e in study.estimates}
        self.assertEqual(by_value[1.337].stratum, "HBR stratum")
        self.assertEqual(by_value[0.657].stratum, "non-HBR stratum")
        lines = rg.extract_article_clinical_details(article)["outcomes_summary"]
        self.assertIn("analiz grubu: HBR stratum", lines)
        self.assertIn("analiz grubu: non-HBR stratum", lines)

    def test_value_after_a_numeric_parenthesis_belongs_to_the_last_conjunct(self):
        study, _ = _study(TWILIGHT_LIKE)
        by_value = {e.value: e for e in study.estimates}
        self.assertEqual(by_value[0.984].outcome_name, "major adverse cardiac or cerebral events")

    def test_one_noun_phrase_with_and_is_not_split(self):
        self.assertEqual(em._contiguous_outcome("respiratory and renal systems", "complications in respiratory and renal systems (OR 0.7)"),
                         "respiratory and renal systems")

    def test_raw_counts_do_not_take_the_hr_p_value(self):
        study, _ = _study(TWILIGHT_LIKE)
        unnamed = [e for e in study.estimates if e.measure == "unnamed"]
        self.assertTrue(all(not e.p_value for e in unnamed))


class SharedMeasureLists(unittest.TestCase):
    def test_measure_named_once_applies_to_later_groups(self):  # PMID 41020486
        sentence = ("Compared with the non-OAC group, the DOAC group showed lower risks of ischaemic stroke (hazard ratio, "
                    "95% confidence interval: 0.81, 0.68-0.96) and all-cause death (0.91, 0.86-0.96) and a higher risk "
                    "of major bleeding (1.44, 1.21-1.70).")
        study, _ = _study(sentence, types=("Journal Article",), title="A nationwide cohort study")
        found = {(e.value, e.ci_low, e.ci_high, e.outcome_name) for e in study.estimates}
        self.assertIn((0.91, 0.86, 0.96, "all-cause death"), found)
        self.assertIn((1.44, 1.21, 1.7, "major bleeding"), found)

    def test_exposure_window_is_not_an_outcome(self):  # PMID 17540675
        sentence = ("Risk of ampicillin-resistant E. coli infection was associated with amoxicillin prescriptions in the "
                    "previous 1 month [odds ratio (OR)=3.91, 95% CI 1.64-9.34] and previous 2-3 months (2.29, 1.12-4.70) "
                    "before illness onset.")
        study, _ = _study(sentence, types=("Journal Article",), title="A case-control study")
        later = [e for e in study.estimates if e.value == 2.29]
        self.assertEqual(len(later), 1)
        self.assertNotIn("previous", later[0].outcome_name)
        self.assertIn("zaman penceresi", later[0].outcome_basis)


class NotAnEstimate(unittest.TestCase):
    def test_twelve_lead_ecg_is_not_an_accuracy_value(self):  # PMID 41410574
        study, _ = _study("Purpose To assess the diagnostic accuracy of 12-lead electrocardiography (ECG). ECG detection "
                          "accuracy for pMI was 78.6% (88.4% specificity and 39.4% sensitivity).",
                          types=("Journal Article",), title="Diagnostic accuracy of ECG")
        self.assertNotIn(12.0, {e.value for e in study.estimates})
        self.assertIn(78.6, {e.value for e in study.estimates})

    def test_ci_label_is_not_a_mean_difference(self):  # PMID 41051743
        study, _ = _study("The nitroglycerin group showed higher perfusion index (mean [SD], 1.37 [1.09] vs 0.65 [0.49]; "
                          "95% CI for mean difference, 0.43-1.01; P < .001).")
        self.assertNotIn(0.43, {e.value for e in study.estimates if e.measure in ("MD", "unnamed")})


class DisplayKeepsTheSource(unittest.TestCase):
    def test_two_group_values_show_both_numbers(self):
        study, article = _study("Nonspecific conduction disturbances were more common in patients with pMIs "
                                "(5.3% vs 1.6%, P = .003).", types=("Journal Article",), title="A diagnostic study")
        text = rg.extract_article_clinical_details(article)["outcomes_summary"]
        self.assertNotIn("5.3% karşı 5.3%", text)

    def test_qualified_outcome_keeps_its_qualifier(self):
        self.assertEqual(rg._display_outcome_name("ischaemic stroke"), "iskemik inme")
        self.assertIn("fatal stroke", rg._display_outcome_name("fatal stroke"))
        self.assertNotEqual(rg._display_outcome_name("fatal stroke"), "inme")

    def test_composite_outcome_is_not_shown_as_one_component(self):  # PMID 31535829
        shown = rg._display_outcome_name("worsening heart failure or cardiovascular death")
        self.assertNotEqual(shown, "kardiyovasküler ölüm")
        self.assertIn("worsening heart failure or cardiovascular death", shown)
        self.assertEqual(rg._display_outcome_name("a composite of cardiovascular death or hospitalization for heart failure"),
                         "kardiyovasküler ölüm veya kalp yetersizliği nedeniyle hastaneye yatış")

    def test_named_but_untranslated_outcome_is_not_called_unnamed(self):
        study, article = _study("For benign biliary pathologies, MRCP achieved higher sensitivity (95.6% vs. 92.3%).",
                                types=("Journal Article",), title="Diagnostic accuracy of MRCP")
        text = rg.extract_article_clinical_details(article)["outcomes_summary"]
        self.assertIn("benign biliary pathologies", text)
        self.assertIn("Duyarlılık", text)

    def test_hazard_ratio_is_not_called_a_risk_ratio(self):
        self.assertEqual(em._MEASURE_TR["HR"], "HR (tehlike oranı)")
        self.assertEqual(em._MEASURE_TR["RR"], "RR (risk oranı)")

    def test_section_6_and_12_name_the_primary_outcome(self):  # PMID 34449189
        abstract = ("We randomly assigned 5988 patients with heart failure to empagliflozin or placebo. The primary outcome "
                    "was a composite of cardiovascular death or hospitalization for heart failure. Over a median of 26.2 "
                    "months, a primary outcome event occurred in 415 of 2997 patients (13.8%) in the empagliflozin group "
                    "and in 511 of 2991 patients (17.1%) in the placebo group (hazard ratio, 0.79; 95% confidence "
                    "interval [CI], 0.69 to 0.90; P<0.001).")
        _study_obj, article = _study(abstract)
        details = rg.extract_article_clinical_details(article)
        bound = rg._format_bound_claims(details)
        self.assertIn("kardiyovasküler ölüm veya kalp yetersizliği nedeniyle hastaneye yatış", bound)
        self.assertNotIn("Sonlanım: özette adlandırılmadı. İstatistik: tehlike oranı (HR) 0.79", bound)
        self.assertIn("kardiyovasküler ölüm veya kalp yetersizliği", details["real_findings"])
        self.assertEqual(details["sample_size"], "n = 5988")


if __name__ == "__main__":
    unittest.main()
