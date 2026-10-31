"""Regression checks for the combined appraisal and structured evidence paths."""
from report_generator import build_evidence_table
from report_generator import _number_after, _quote_sentence


def article(abstract):
    return {
        "pmid": "12345678", "title": "Randomized trial", "abstract": abstract,
        "publication_types": ["Randomized Controlled Trial"],
        "authors": ["Test Author"], "pub_year": "2024", "journal": "Test Journal",
        # Legacy input cannot turn extraction into a completed appraisal.
        "grade": {"final": "High"}, "rob2": {"overall": "Low"},
        "effect_summary": {"primary": {"type": "HR", "value": 999}},
    }


def test_appraisal_table_uses_source_model_instead_of_legacy_input():
    table = build_evidence_table([article(
        "We randomly assigned 120 patients to drug or placebo. "
        "Mortality: HR 0.70 (95% CI 0.50 to 0.90)."
    )])
    assert "999" not in table
    assert "High" not in table and "Low" not in table
    assert "0,70" in table or "0,7" in table
    assert "Değerlendirilemedi" in table
    assert "120" in table


def test_appraisal_table_does_not_present_invalid_estimate_as_finding():
    table = build_evidence_table([article("Mortality: HR 0.70 (95% CI 1.20 to 1.80).")])
    assert "Özette kullanılabilir etki tahmini yok" in table
    assert "HR" not in table


def test_appraisal_table_escapes_markdown_cell_content():
    record = article("No numerical result was reported.")
    record["pmid"] = "12345678|injected\nrow"
    table = build_evidence_table([record])
    assert len(table.splitlines()) == 3
    assert all(line.count("|") == 7 for line in table.splitlines())


def test_confidence_level_is_not_an_estimate_at_search_window_boundary():
    text = "Odds Ratio (OR) and 95% confidence interval were calculated."
    assert _number_after(text, len("Odds Ratio"), max_gap=24) is None


def test_attributed_long_source_sentence_is_never_abbreviated_or_rewritten():
    sentence = 'The authors reported "uncertain results" ' + "from the recorded source " * 20 + "."
    assert _quote_sentence(sentence) == sentence
