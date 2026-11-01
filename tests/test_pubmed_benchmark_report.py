import evidence_model as em
from validation.run_pubmed_benchmark import (
    compare_case,
    expected_outcome_match,
    number_tokens,
    summarize_field_gaps,
)


def _study_with_estimates():
    sentence = "Overall survival had an HR of 0.73 (95% CI 0.70 to 0.90; p=0.04) and an HR of 0.79 (95% CI 0.61 to 0.88; p=0.01)."
    source = em.EvidenceSource(
        pmid="12345678",
        sentence=sentence,
        location="abstract",
        verification_status=em.SOURCE_VERIFIED,
    )
    estimates = [
        em.EffectEstimate(
            measure="HR", measure_text="HR", family="ratio", value=0.73,
            value_text="0.73", ci_low=0.70, ci_high=0.90, ci_level=95,
            p_value="p=0.04", outcome_name="overall survival", source=source,
        ),
        em.EffectEstimate(
            measure="HR", measure_text="HR", family="ratio", value=0.79,
            value_text="0.79", ci_low=0.61, ci_high=0.88, ci_level=95,
            p_value="p=0.01", outcome_name="overall survival", source=source,
        ),
    ]
    outcome = em.Outcome(name="overall survival", estimates=estimates, source=source)
    return em.Study(
        pmid="12345678", doi="", title="Example", journal="", year="2024",
        design_key="rct", design_label="Randomized trial", evidence_level="",
        evidence_level_note="", claim_type="causal_effect", claim_type_tr="",
        causal_inference_allowed=True, results_reported=True, population=em.Population(),
        outcomes=[outcome],
    )


def test_confidence_interval_and_p_value_belong_to_the_matched_canonical_estimate():
    study = _study_with_estimates()
    result = expected_outcome_match(
        {
            "metric": "HR", "estimate": "0.73", "ci": ["0.61", "0.88"],
            "p": "<0.001", "source_sentence": study.estimates[0].source.sentence,
        },
        study,
    )

    assert result["source_sentence_matched"] is True
    assert result["estimate_matched"] is True
    assert result["metric_matched"] is True
    assert result["ci_matched"] is False
    assert result["p_matched"] is False
    assert result["matched_estimate"].value == 0.73


def test_non_arm_groups_are_not_scored_as_randomized_arms():
    study = _study_with_estimates()
    case = {
        "specialty": "Radiology", "pmid": study.pmid, "required_design": "rct",
        "total_n": None, "arms": [],
        "non_arm_groups": [{"label": "MRI subgroup", "participants_n": 29, "not_arm_reason": "Technical subgroup."}],
        "outcomes": [],
    }

    result = compare_case(case, {"pmid": study.pmid, "title": study.title, "abstract": study.estimates[0].source.sentence}, study)

    assert result["reference_fields_expected"] == 1
    assert result["reference_field_checks"][0]["category"] == "study_design"
    assert result["non_arm_groups_not_scored"] == case["non_arm_groups"]


def test_field_gap_summary_counts_canonical_benchmark_failures():
    gaps = summarize_field_gaps([
        {"reference_field_checks": [
            {"category": "arm_participant_n", "matched": True},
            {"category": "arm_participant_n", "matched": False},
            {"category": "outcome_metric", "matched": False},
        ]}
    ])
    by_category = {item["category"]: item for item in gaps}

    assert by_category["arm_participant_n"]["expected"] == 2
    assert by_category["arm_participant_n"]["matched"] == 1
    assert by_category["arm_participant_n"]["unmatched"] == 1
    assert by_category["outcome_metric"]["unmatched"] == 1
    assert by_category["outcome_metric"]["priority"].startswith("P1")


def test_number_tokens_keep_number_words_and_hyphenated_confidence_limits_positive():
    assert number_tokens("two times more likely") == ["2"]
    assert number_tokens("95% CI 1.64-9.34") == ["95%", "1.64", "9.34"]


def test_benchmark_matches_event_percent_from_canonical_event_count():
    study = _study_with_estimates()
    sentence = "Overall response was 47 (15.6%) among patients."
    source = em.EvidenceSource(
        pmid=study.pmid, sentence=sentence, location="abstract",
        verification_status=em.SOURCE_VERIFIED,
    )
    study.event_counts = [em.EventCount(events=47, total=None, percent=15.6, source=source)]

    result = expected_outcome_match(
        {"metric": "proportion", "estimate": "15.6%", "source_sentence": sentence},
        study,
    )

    assert result["source_sentence_matched"] is True
    assert result["estimate_matched"] is True
    assert result["metric_matched"] is True


def test_benchmark_matches_unstructured_source_bound_prevalence_without_calling_it_grade():
    study = _study_with_estimates()
    sentence = "Prevalence of thyroid disease among inpatients is approximately 1% to 2%."
    source = em.EvidenceSource(
        pmid=study.pmid, sentence=sentence, location="abstract",
        verification_status=em.SOURCE_VERIFIED,
    )
    study.other_numeric_findings = [{
        "outcome": "Prevalence of thyroid disease among inpatients",
        "metrics": ["approximately 1% to 2%"],
        "source": source,
    }]

    result = expected_outcome_match(
        {"metric": "prevalence", "estimate": "approximately 1% to 2%", "source_sentence": sentence},
        study,
    )

    assert result["source_sentence_matched"] is True
    assert result["estimate_matched"] is True
    assert result["metric_matched"] is True


def test_unrelated_event_count_is_not_matched_to_expected_source_sentence():
    study = _study_with_estimates()
    unrelated = em.EvidenceSource(
        pmid=study.pmid,
        sentence="There were 7 unrelated adverse events in the placebo arm.",
        location="abstract",
        verification_status=em.SOURCE_VERIFIED,
    )
    study.event_counts = [em.EventCount(events=7, total=None, percent=None, source=unrelated)]
    reference_sentence = "In the treatment group, 5 participants had a seizure."
    case = {
        "specialty": "Neurology", "pmid": study.pmid, "required_design": "rct",
        "total_n": None, "arms": [], "non_arm_groups": [],
        "outcomes": [{"outcome": "Seizures", "source_sentence": reference_sentence, "event_count": 5}],
    }

    result = compare_case(case, {"pmid": study.pmid, "title": study.title, "abstract": unrelated.sentence}, study)

    assert result["outcomes"][0]["event_counts_matched"] == [False]
    assert result["reference_fields_matched"] == 1
