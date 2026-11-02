"""Participant counts, event counts, arm sizes and time-point proportions.

Each case is a sentence (or a short abstract) taken from or modelled on a real
PubMed abstract. Patient counts must not be read as event counts, eligibility
thresholds must not be read as sample sizes, and a proportion is bound to an
endpoint only when the source names it.
"""
import unittest

import evidence_model as em


def _study(abstract, types=("Randomized Controlled Trial",), title="Trial"):
    em.clear_cache()
    article = {"pmid": "1", "title": title, "abstract": abstract, "publication_types": list(types)}
    return em.build_studies([article], "")[0][0]


EMPEROR = (
    "In this double-blind trial, we randomly assigned 5988 patients with class II-IV heart failure and an ejection "
    "fraction of more than 40% to receive empagliflozin (10 mg once daily) or placebo, in addition to usual therapy. "
    "Over a median of 26.2 months, a primary outcome event occurred in 415 of 2997 patients (13.8%) in the "
    "empagliflozin group and in 511 of 2991 patients (17.1%) in the placebo group (hazard ratio, 0.79; 95% "
    "confidence interval [CI], 0.69 to 0.90; P<0.001). The total number of hospitalizations for heart failure was "
    "lower in the empagliflozin group than in the placebo group (407 with empagliflozin and 541 with placebo; hazard "
    "ratio, 0.73; 95% CI, 0.61 to 0.88; P<0.001)."
)


class DenominatorIsNotAnEventCount(unittest.TestCase):
    def test_x_of_n_patients_percent(self):
        study = _study(EMPEROR)
        events = {(e.events, e.total, e.percent) for e in study.event_counts}
        self.assertIn((415, 2997, 13.8), events)
        self.assertIn((511, 2991, 17.1), events)
        self.assertNotIn(2997, {e.events for e in study.event_counts})
        self.assertNotIn(2991, {e.events for e in study.event_counts})

    def test_x_slash_n(self):
        study = _study("We included 48 patients. Thus, the false-negative rate was 14/48 (29%).",
                       types=("Journal Article",), title="MRI for diagnosis: a diagnostic accuracy study")
        events = {(e.events, e.total) for e in study.event_counts}
        self.assertIn((14, 48), events)
        self.assertNotIn(48, {e.events for e in study.event_counts})

    def test_total_of_is_a_count_not_a_denominator(self):
        abstract = ("Children born in Denmark were included (N = 2 103 232). Of the 2 103 232 children in the study "
                    "population, a total of 75 593 children (3.6%) were diagnosed with a first febrile seizure.")
        study = _study(abstract, types=("Journal Article",), title="Febrile seizures: a cohort study")
        self.assertIn(75593, {e.events for e in study.event_counts})
        self.assertEqual(study.population.n_total, 2103232)


class ArmSizesAndArmEvents(unittest.TestCase):
    def test_arm_size_from_results_denominator(self):
        study = _study(EMPEROR)
        sizes = {a.label.lower(): a.n for a in study.arms}
        self.assertEqual(sizes.get("empagliflozin"), 2997)
        self.assertEqual(sizes.get("placebo"), 2991)
        self.assertEqual(study.population.n_total, 5988)

    def test_events_written_with_arm_labels(self):
        study = _study(EMPEROR)
        self.assertTrue({407, 541} <= {e.events for e in study.event_counts})

    def test_with_phrase_without_effect_measure_is_not_an_event(self):
        abstract = ("We randomly assigned 200 patients to receive drug A or placebo. "
                    "At baseline, 40 with drug A and 38 with placebo had diabetes.")
        study = _study(abstract)
        self.assertFalse({40, 38} & {e.events for e in study.event_counts})


class EligibilityThresholdIsNotASampleSize(unittest.TestCase):
    ABSTRACT = (
        "PubMed and Embase were searched for all cohort and observational studies. Eligible studies included those "
        "with five or more participants with metastatic mucosal melanoma. From a total of 7402 studies, 35 eligible "
        "studies comprising a total of 2833 participants were included."
    )

    def test_pooled_total_found_and_threshold_ignored(self):
        study = _study(self.ABSTRACT, types=("Systematic Review", "Meta-Analysis"),
                       title="Immune checkpoint inhibitors in mucosal melanoma: a systematic review and meta-analysis")
        self.assertEqual(study.population.n_total, 2833)
        self.assertEqual(study.population.n_kind, "pooled")

    def test_at_least_is_ignored(self):
        study = _study("Trials enrolling at least 30 patients were eligible. Twelve trials including 1200 patients "
                       "were included.", types=("Systematic Review",), title="A systematic review")
        self.assertNotEqual(study.population.n_total, 30)


class FollowedCohort(unittest.TestCase):
    def test_followed_n_individuals(self):
        abstract = ("We followed 302 individuals with adult-onset epilepsy for 9.8 years. Overall 47 (15.6%) "
                    "individuals presented drug-resistant epilepsy.")
        study = _study(abstract, types=("Journal Article",), title="Adult-onset epilepsy: a cohort study")
        self.assertEqual(study.population.n_total, 302)
        self.assertIn((47, 15.6), {(e.events, e.percent) for e in study.event_counts})


ONCOLOGY = (
    "From a total of 7402 studies, 35 eligible studies comprising a total of 2833 participants were included. "
    "Combined anti-PD1 and anti-CTLA4 therapy had the highest 12-month OS and 12-month PFS at 71.8% (95% CI: 67.6%, "
    "76.2%, n = 476) and 35.1% (95% CI: 30.5%, 40.4%, n = 401) respectively, followed by anti-PD1 therapy alone "
    "(OS: 64.0% (95% CI: 61.4%, 66.7%, n = 1399); PFS: 9.8% (95% CI: 5.9%, 16.5%, n = 200))."
)


class TimePointProportions(unittest.TestCase):
    def _props(self, abstract=ONCOLOGY):
        study = _study(abstract, types=("Systematic Review", "Meta-Analysis"),
                       title="Mucosal melanoma: a systematic review and meta-analysis")
        return study, [e for e in study.estimates if e.family == "proportion"]

    def test_respectively_maps_in_order(self):
        _study_obj, props = self._props()
        by_value = {e.value: e for e in props}
        self.assertEqual(by_value[71.8].outcome_name, "12-month overall survival")
        self.assertEqual((by_value[71.8].ci_low, by_value[71.8].ci_high), (67.6, 76.2))
        self.assertEqual(by_value[35.1].outcome_name, "12-month progression-free survival")
        self.assertIn("respectively", by_value[35.1].outcome_basis)

    def test_labelled_value_keeps_its_group(self):
        _study_obj, props = self._props()
        by_value = {e.value: e for e in props}
        self.assertEqual(by_value[64.0].outcome_name, "overall survival")
        self.assertIn("anti-PD1 therapy alone", by_value[64.0].outcome_basis)
        self.assertNotIn("followed by", by_value[64.0].outcome_basis)

    def test_unlabelled_percent_is_not_bound(self):
        _study_obj, props = self._props("Survival was 50.0% (95% CI: 40.0%, 60.0%) overall in 300 patients.")
        self.assertEqual(props, [])

    def test_unequal_counts_with_respectively_are_not_mapped(self):
        abstract = ("12-month OS was 70.0% (95% CI: 60.0%, 80.0%) and 50.0% (95% CI: 40.0%, 60.0%) in the two "
                    "groups, respectively.")
        _study_obj, props = self._props(abstract)
        self.assertEqual([p for p in props if "respectively" in p.outcome_basis], [])

    def test_wording_is_not_causal(self):
        study, props = self._props()
        sentence = em.claim_sentence_tr(study, props[0])
        self.assertIn("Grup içi oran", sentence)
        self.assertIn("nedensellik değildir", sentence)
        self.assertNotIn("Randomize", sentence)

    def test_named_outcome_is_never_shown_as_unnamed(self):
        self.assertNotIn("adlandırılmadı", em.outcome_label_tr("OS"))
        self.assertIn("OS", em.outcome_label_tr("OS"))
        self.assertEqual(em.outcome_label_tr(""), "sonlanım özette adlandırılmadı")


class ConfidenceLevelIsNotAnEstimate(unittest.TestCase):
    def test_methods_sentence_does_not_yield_or_95(self):
        abstract = ("We performed conditional logistic regression to estimate Odds Ratio (OR) and 95% confidence "
                    "interval (95% CI). Use was associated with higher risk (OR 1.8, 95% CI 1.2-2.7).")
        study = _study(abstract, types=("Journal Article",), title="A case-control study")
        values = {e.value for e in study.estimates}
        self.assertNotIn(95.0, values)
        self.assertIn(1.8, values)

    def test_wmd_with_95_ci_in_methods(self):
        abstract = ("Effect sizes were summarized as risk ratios (RR) or weighted mean differences (WMD) with 95% "
                    "confidence intervals (CI).")
        study = _study(abstract, types=("Meta-Analysis",), title="A meta-analysis")
        self.assertNotIn(95.0, {e.value for e in study.estimates})


class NumbersAsWrittenInTheSource(unittest.TestCase):
    def test_hyphenated_ci_keeps_trailing_zero(self):
        import report_generator as rg
        em.clear_cache()
        article = {"pmid": "2", "title": "Empagliflozin in acute heart failure", "publication_types": ["Randomized Controlled Trial"],
                   "abstract": ("We randomly assigned 530 patients to empagliflozin or placebo. Heart failure hospitalization was "
                                "lower with empagliflozin than with placebo (HR 0.79, 95% CI 0.69-0.90).")}
        finding = [f for f in rg.structured_findings(article) if "0.79" in f["effect"]][0]
        self.assertEqual(finding["ci"], "0.69 ile 0.90")

    def test_negative_bounds_are_kept(self):
        import report_generator as rg
        sentence = "MD -1.20 (95% CI -2.40 to -0.10)"
        self.assertEqual([rg._source_number_text(v, sentence) for v in (-1.2, -2.4, -0.1)], ["-1.20", "-2.40", "-0.10"])


if __name__ == "__main__":
    unittest.main()
