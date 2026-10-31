import unittest

from clinical_evidence import (
    build_study_model,
    legacy_details_from_study,
    select_research_question_framework,
    validate_study_model,
)


def article(pmid="12345678", abstract=None, publication_types=None, **extra):
    result = {
        "pmid": pmid,
        "doi": "10.1000/example",
        "title": "Example clinical study",
        "pub_year": "2024",
        "publication_types": publication_types or ["Journal Article"],
        "abstract": abstract or "In 120 adults with disease (n=120), treatment A versus placebo reduced hospitalization (HR 0.72, 95% CI 0.61-0.85, p=0.01).",
        "verification_status": "verified",
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
    result.update(extra)
    return result


class TestQuestionFrameworkSelection(unittest.TestCase):
    def test_selects_non_pico_frameworks_for_different_research_questions(self):
        expected = {
            "sensitivity of a test for diagnosis": "PIRD",
            "screening strategy for colorectal cancer": "PICOTS-S",
            "prognostic factors for stroke survival": "PFO",
            "association between exposure and incidence": "PECO",
            "health services delivery model outcomes": "PICOT-HS",
            "safety adverse events of a drug": "PECO",
            "surgery versus usual care": "PICO",
            "description of rare disease context": "PCC",
        }
        for query, framework in expected.items():
            with self.subTest(query=query):
                self.assertEqual(select_research_question_framework(query)["framework"], framework)

    def test_design_can_select_diagnostic_frame_without_pico_words(self):
        self.assertEqual(select_research_question_framework("lung nodule imaging", "diagnostic_accuracy")["framework"], "PIRD")


class TestCanonicalEvidenceModel(unittest.TestCase):
    def test_model_binds_facts_metrics_sources_and_status(self):
        model = build_study_model(article(), query="treatment efficacy")
        self.assertEqual(model["model_version"], "1.0")
        self.assertEqual(model["pmid"], "12345678")
        self.assertEqual(model["doi"], "10.1000/example")
        self.assertEqual(model["research_question"]["framework"], "PICO")
        self.assertEqual(model["source"]["verification_status"], "pubmed_record_found_identity_only")
        population = model["population"]
        self.assertEqual(population["total_participants"]["value"], 120)
        self.assertEqual(population["description"]["source"]["pmid"], "12345678")
        self.assertTrue(population["description"]["source"]["source_sentence"])
        self.assertEqual(len(model["outcomes"]), 1)
        effect = model["outcomes"][0]["effect_estimates"][0]
        self.assertEqual(effect["metric_type"], "HR")
        self.assertEqual(effect["value"], "0.72")
        self.assertEqual(effect["ci_lower"], "0.61")
        self.assertEqual(effect["ci_upper"], "0.85")
        self.assertEqual(effect["p_value"], "p=0.01")
        self.assertEqual(effect["outcome_id"], model["outcomes"][0]["id"])
        self.assertEqual(effect["source"]["doi"], "10.1000/example")
        self.assertEqual(effect["source"]["verification_status"], "pubmed_record_found_identity_only")
        self.assertTrue(validate_study_model(model)["valid"])
        self.assertEqual(model["risk_of_bias"]["status"], "not_assessed")
        self.assertEqual(model["risk_of_bias"]["assessed"], False)

    def test_observational_drug_use_is_a_sourced_exposure_not_an_intervention(self):
        record = article(
            pmid="87650001",
            abstract=(
                "We reviewed patients with atopic dermatitis treated with dupilumab. "
                "Skin infections were less frequently observed compared to placebo."
            ),
            publication_types=["Journal Article", "Observational Study"],
        )
        model = build_study_model(record, query="dupilumab atopic dermatitis")
        self.assertIsNone(model["intervention"])
        self.assertIsNone(model["comparator"])
        self.assertEqual(model["exposure"]["value"], "Dupilumab")
        self.assertIn("treated with dupilumab", model["exposure"]["source"]["source_sentence"])
        self.assertTrue(validate_study_model(model)["valid"])

    def test_randomized_arms_ignore_earlier_or_in_a_clinical_classification(self):
        record = article(
            pmid="87650002",
            abstract=(
                "Patients with NYHA class II, III, or IV heart failure were randomly assigned "
                "to receive either dapagliflozin (10 mg daily) or placebo."
            ),
            publication_types=["Journal Article", "Randomized Controlled Trial"],
        )
        model = build_study_model(record, query="heart failure treatment")
        self.assertEqual(model["intervention"]["name"]["value"], "dapagliflozin 10 mg")
        self.assertEqual(model["comparator"]["name"]["value"], "plasebo")
        self.assertIn("dapagliflozin", model["intervention"]["name"]["source"]["source_sentence"].lower())
        self.assertIn("placebo", model["comparator"]["name"]["source"]["source_sentence"].lower())
        self.assertTrue(validate_study_model(model)["valid"])

    def test_unreported_comparator_placeholder_is_not_a_sourced_fact(self):
        record = article(
            pmid="87650003",
            abstract="This case series included 56 patients with Eagle syndrome.",
            publication_types=["Case Series"],
        )
        details = {
            "provenance": {
                "comparison": {"value": "bildirilmedi", "source_sentence": "", "source": "missing"},
            },
            "outcome_metrics": [],
        }
        model = build_study_model(
            record,
            clinical_details=details,
            study_design={"design_key": "case_series", "design": "Olgu serisi"},
        )
        self.assertIsNone(model["comparator"])
        self.assertFalse(any("missing_source_sentence:comparator" in x for x in model["extraction_validation"]["errors"]))

    def test_population_description_drops_numbers_not_in_its_source_sentence(self):
        record = article(
            pmid="87650004",
            abstract="This retrospective cohort included 400 patients with infection (n=400).",
            publication_types=["Cohort Study"],
        )
        details = {
            "provenance": {
                "population": {
                    "value": "400 patients; 22 events; 8.6%",
                    "source_sentence": "This retrospective cohort included 400 patients with infection (n=400).",
                    "source": "abstract",
                },
            },
            "outcome_metrics": [],
        }
        model = build_study_model(record, clinical_details=details)
        description = model["population"]["description"]
        self.assertEqual(description["value"], "400 hasta")
        self.assertEqual(description["source"]["source_sentence"], record["abstract"])
        self.assertNotIn("22", description["value"])
        self.assertNotIn("8.6", description["value"])
        self.assertEqual(model["population"]["total_participants"]["value"], 400)

    def test_subgroup_denominator_from_later_sentence_is_not_population_total(self):
        record = article(
            pmid="87650005",
            abstract=(
                "We followed 302 individuals with adult-onset epilepsy for 9 years. "
                "In the nondrug-resistant subgroup, infectious etiology occurred in 25.9% (n=66)."
            ),
            publication_types=["Cohort Study"],
        )
        model = build_study_model(record, query="epilepsy prognosis")
        description = model["population"]["description"]
        self.assertIn("302", description["value"])
        self.assertNotIn("66", description["value"])
        self.assertIn("302", description["source"]["source_sentence"])
        self.assertNotIn("66", description["source"]["source_sentence"])
        self.assertEqual(model["population"]["total_participants"]["value"], 302)

    def test_demographic_subgroup_count_keeps_its_own_source_sentence(self):
        import json
        from pathlib import Path
        records = json.loads((Path(__file__).parent / "fixtures" / "recorded_target_pmids.json").read_text(encoding="utf-8"))
        record = next(item for item in records if item["pmid"] == "40446701")
        model = build_study_model(record)
        characteristic = next(
            item for item in model["population"]["characteristics"]
            if "62" in item["value"] and "Hispanik" in item["value"]
        )
        self.assertEqual(characteristic["value"], "62 hasta Hispanik")
        self.assertIn("Sixty-two", characteristic["source"]["source_sentence"])
        from validation.run_pubmed_benchmark import number_tokens
        self.assertIn("62", number_tokens(characteristic["source"]["source_sentence"]))

    def test_implausible_ratio_interval_is_flagged_without_losing_source(self):
        record = article(abstract=(
            "In 100 adults, all-cause mortality was associated with exposure (RR 0.81, 95% CI -0.69 to 0.95)."
        ))
        model = build_study_model(record, query="epidemiology association")
        effect = next(
            effect
            for outcome in model["outcomes"]
            for effect in outcome["effect_estimates"]
            if effect["metric_type"] == "RR"
        )
        self.assertEqual(effect["value"], "0.81")
        self.assertTrue(effect["implausible_source_value"])
        self.assertEqual(effect["source"]["pmid"], record["pmid"])
        self.assertIn("RR 0.81", effect["source"]["source_sentence"])
        self.assertTrue(any(w.startswith("implausible_ratio_interval:") for w in model["extraction_validation"]["warnings"]))

    def test_events_are_not_sample_size_and_arm_n_is_not_copied_from_total(self):
        record = article(abstract=(
            "This retrospective cohort included 400 patients with infection (n=400). "
            "There were 24 events among 400 patients. Infection recurrence was associated with exposure (OR 1.8, 95% CI 1.1-2.9)."
        ))
        model = build_study_model(record, query="exposure infection risk")
        self.assertEqual(model["population"]["total_participants"]["value"], 400)
        self.assertEqual(model["causal_interpretation_status"], "association_only; no_causal_superiority_claim")
        # The abstract describes no intervention or comparator arm; the total N
        # must not be copied into fabricated per-arm values.
        self.assertEqual(model["arms"], [])
        outcomes = model["outcomes"]
        event_outcome = next((x for x in outcomes if x["event_count"]["value"] is not None), None)
        self.assertIsNotNone(event_outcome)
        self.assertEqual(event_outcome["event_count"]["value"], 24)
        self.assertEqual(event_outcome["denominator"]["value"], 400)
        self.assertNotEqual(model["population"]["total_participants"]["value"], 24)

    def test_diagnostic_metrics_and_confidence_intervals_bind_to_outcome(self):
        record = article(abstract=(
            "Among 200 children with fever, the index test had sensitivity 91%, specificity 84%, and AUC 0.88."
        ), publication_types=["Journal Article"])
        model = build_study_model(record, query="diagnostic accuracy in children")
        self.assertEqual(model["research_question"]["framework"], "PIRD")
        estimates = model["outcomes"][0]["effect_estimates"]
        self.assertEqual({x["metric_type"] for x in estimates}, {"sensitivity", "specificity", "AUC"})
        self.assertTrue(all(x["outcome_id"] == model["outcomes"][0]["id"] for x in estimates))

    def test_meta_analysis_and_follow_up_are_related_as_reviews_not_new_cohorts(self):
        record = article(
            pmid="87654321",
            publication_types=["Meta-Analysis", "Systematic Review"],
            title="Meta-analysis of the ABC-Heart trial",
            abstract="This meta-analysis included prior trial reports. A total of 5 studies were pooled.",
        )
        model = build_study_model(record, query="heart failure treatment")
        self.assertEqual(model["relationship"]["kind"], "meta_analysis")
        self.assertEqual(model["causal_interpretation_status"], "review_of_prior_studies; not_a_new_primary_cohort")
        self.assertEqual(model["evidence_family_basis"], "explicit_trial_name")
        self.assertEqual(model["risk_of_bias"]["assessed"], False)

    def test_overall_n_does_not_use_meta_analysis_stratum_or_diagnostic_agreement_n(self):
        review = article(
            pmid="11112222",
            publication_types=["Meta-Analysis", "Systematic Review"],
            title="Systematic review of diagnostic accuracy",
            abstract="We included 35 studies. In a subgroup, sensitivity was reported for n = 476 participants.",
        )
        review_model = build_study_model(review, query="diagnostic test", study_design={"design_key": "meta_analysis", "design": "Meta-analysis"})
        self.assertIsNone(review_model["population"]["total_participants"]["value"])

        diagnostic = article(
            pmid="33334444",
            title="Prospective diagnostic accuracy study",
            abstract="Among 126 children, 82% (n = 103) had matching index and reference results.",
        )
        diagnostic_model = build_study_model(
            diagnostic,
            query="diagnostic accuracy",
            study_design={"design_key": "diagnostic_accuracy", "design": "Diagnostic accuracy study"},
        )
        self.assertEqual(diagnostic_model["population"]["total_participants"]["value"], 126)

    def test_arm_sizes_and_outcome_event_denominators_are_distinct(self):
        record = article(
            pmid="44445555",
            publication_types=["Randomized Controlled Trial"],
            abstract=(
                "We randomly assigned 119 adult patients to active treatment (active group) or usual care (control group). "
                "A total of 60 participants were assigned to the active group and 59 to the control group. "
                "There were 12 events among 60 patients in the active group and 9 events among 59 patients in the control group."
            ),
        )
        model = build_study_model(record, query="treatment efficacy")
        self.assertEqual(model["population"]["total_participants"]["value"], 119)
        self.assertEqual([arm["participants_n"]["value"] for arm in model["arms"]], [60, 59])
        counts = [count for outcome in model["outcomes"] for count in outcome["arm_event_counts"]]
        self.assertEqual([(x["event_count"]["value"], x["denominator"]["value"]) for x in counts], [(12, 60), (9, 59)])
        self.assertTrue(all(x["event_count"]["source"]["source_sentence"] for x in counts))
        self.assertTrue(model["extraction_validation"]["valid"])

    def test_event_arm_label_does_not_inherit_dose_absent_from_result_sentence(self):
        record = article(
            pmid="55556666",
            publication_types=["Randomized Controlled Trial"],
            abstract=(
                "We randomly assigned 120 adults to receive empagliflozin (10 mg) or placebo. "
                "The primary outcome occurred in 12 of 60 patients in the empagliflozin group and 9 of 60 patients in the placebo group."
            ),
        )
        model = build_study_model(record, query="treatment efficacy")
        counts = [count for outcome in model["outcomes"] for count in outcome["arm_event_counts"]]
        self.assertEqual([count["arm_label"]["value"].casefold() for count in counts], ["empagliflozin", "placebo"])
        self.assertTrue(all(not any(ch.isdigit() for ch in count["arm_label"]["value"]) for count in counts))
        self.assertTrue(all(count["arm_label"]["value"].casefold() in count["arm_label"]["source"]["source_sentence"].casefold() for count in counts))

    def test_legacy_adapter_is_derived_from_same_canonical_model(self):
        model = build_study_model(article(), query="treatment efficacy")
        legacy = legacy_details_from_study(model)
        self.assertEqual(legacy["sample_size"], "n = 120")
        self.assertEqual(legacy["provenance"]["pmid"], model["pmid"])
        self.assertEqual(legacy["outcome_metrics"][0]["pmid"], model["pmid"])


if __name__ == "__main__":
    unittest.main()
