from validation.run_pubmed_benchmark import (
    compare_case,
    expected_outcome_match,
    summarize_field_gaps,
)
from clinical_evidence import build_study_model


def test_confidence_interval_and_p_value_must_belong_to_matched_estimate():
    sentence = "Outcome was reported with an effect estimate."
    model = {
        "outcomes": [
            {
                "source": {"source_sentence": sentence},
                "effect_estimates": [
                    {"metric_type": "HR", "value": "0.73", "ci_lower": "0.70", "ci_upper": "0.90", "p_value": "p=0.04"},
                    {"metric_type": "HR", "value": "0.79", "ci_lower": "0.61", "ci_upper": "0.88", "p_value": "p=0.01"},
                ],
            }
        ]
    }
    result = expected_outcome_match(
        {"metric": "HR", "estimate": "0.73", "ci": ["0.61", "0.88"], "p": "<0.001", "source_sentence": sentence},
        model,
    )
    assert result["estimate_matched"] is True
    assert result["metric_matched"] is True
    assert result["ci_matched"] is False
    assert result["p_matched"] is False


def test_paired_os_pfs_proportions_keep_their_own_confidence_intervals():
    sentence = (
        "Combined anti-PD1 and anti-CTLA4 therapy had the highest 12-month OS and 12-month PFS at "
        "71.8% (95% CI: 67.6%, 76.2%, n = 476) and 35.1% (95% CI: 30.5%, 40.4%, n = 401) respectively."
    )
    model = build_study_model({
        "pmid": "12345678",
        "doi": "10.1000/example",
        "title": "Meta-analysis example",
        "pub_year": "2024",
        "publication_types": ["Meta-Analysis", "Systematic Review"],
        "abstract": sentence,
        "verification_status": "verified",
    })
    expected = [
        {"metric": "proportion", "estimate": "71.8%", "ci": ["67.6%", "76.2%"], "source_sentence": sentence},
        {"metric": "proportion", "estimate": "35.1%", "ci": ["30.5%", "40.4%"], "source_sentence": sentence},
    ]
    results = [expected_outcome_match(item, model) for item in expected]
    assert all(result["source_sentence_matched"] for result in results)
    assert all(result["estimate_matched"] for result in results)
    assert all(result["metric_matched"] for result in results)
    assert [result["ci_matched"] for result in results] == [True, True]


def test_event_count_does_not_match_an_unrelated_outcome():
    source_sentence = "There were 5 events among 10 participants."
    case = {
        "specialty": "Test",
        "pmid": "12345678",
        "required_design": "rct",
        "total_n": None,
        "arms": [],
        "outcomes": [{"source_sentence": source_sentence, "event_count": [5]}],
    }
    model = {
        "design_key": "rct",
        "causal_interpretation_status": "randomized_design_reported",
        "population": {"total_participants": {"value": None}},
        "outcomes": [
            {
                "source": {"source_sentence": "Unrelated outcome had 5 events."},
                "event_count": {"value": 5},
                "arm_event_counts": [],
                "effect_estimates": [],
            }
        ],
    }
    result = compare_case(case, {"abstract": source_sentence, "title": "Test"}, model)
    assert result["outcomes"][0]["event_counts_matched"] == [False]
    assert result["reference_fields_matched"] == 1
    assert result["reference_fields_expected"] == 2


def test_field_gap_summary_reports_matched_and_unmatched_counts():
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
