"""Intervention source consistency with explicitly mock, offline articles."""

import pytest

from report_generator import (
    _format_bound_claims,
    _format_cross_study_comparison,
    _intervention_comparison_cell,
    extract_article_clinical_details,
    extract_clinical_profile,
)


@pytest.mark.parametrize("in_abstract", [False, True])
def test_matrix_and_section6_share_abstract_only_interventions(in_abstract):
    article = {
        "pmid": "MOCK-TITLE-ONLY",
        "title": "Mock study of rituximab",
        "abstract": (
            "Patients were treated with rituximab."
            if in_abstract else "Patients were followed during the study."
        ),
        "publication_types": [],
    }
    details = extract_article_clinical_details(article)
    table = _format_cross_study_comparison([article])
    row = next(line for line in table.splitlines()
               if line.startswith("| MOCK-TITLE-ONLY |"))
    section6 = row.strip("|").split("|")[3].strip()
    # Also exercise the cell API when a caller explicitly supplies the title.
    cell = _intervention_comparison_cell(
        extract_clinical_profile(article["abstract"]),
        article["abstract"], article["title"],
    )
    claim = details["provenance"]["intervention"]
    assert claim["source"] == ("abstract" if in_abstract else "missing")
    assert "Kaynak: makale başlığı" not in _format_bound_claims(details)
    values = [details["intervention"], section6, cell]
    if in_abstract:
        assert [value.casefold() for value in values] == ["rituksimab"] * 3
    else:
        for value in values:
            assert "rituksimab" not in value.casefold()
            assert "rituximab" not in value.casefold()


@pytest.mark.parametrize("abstract", [
    "Treatment with rituximab is often necessary. We followed 40 patients.",
    "Patients previously exposed to rituximab were excluded.",
    "Patients treated with rituximab were excluded.",
    "Exclusion criteria included treatment with rituximab.",
    "Patients randomized to rituximab or placebo were excluded.",
])
def test_background_and_exclusion_are_not_intervention_sources(abstract):
    article = {
        "pmid": "MOCK-INCIDENTAL-DRUG",
        "title": "Mock study of rituximab",
        "abstract": abstract,
        "publication_types": [],
    }
    details = extract_article_clinical_details(article)
    claim = details["provenance"]["intervention"]
    cell = _intervention_comparison_cell(
        extract_clinical_profile(abstract), abstract, article["title"],
    )
    table = _format_cross_study_comparison([article])
    row = next(line for line in table.splitlines()
               if line.startswith("| MOCK-INCIDENTAL-DRUG |"))
    for value in (details["intervention"], cell, row):
        assert "rituksimab" not in value.casefold()
        assert "rituximab" not in value.casefold()
    assert claim["source"] == "missing"
    assert claim["source_sentence"] == ""


@pytest.mark.parametrize("sentence", [
    "Patients were treated with rituximab.",
    "We assessed the efficacy of rituximab.",
    "We assessed the safety of rituximab.",
    "Patients had rituximab resistance.",
    "We compared rituximab versus placebo.",
    "Patients were randomized to rituximab or placebo.",
])
def test_eligible_abstract_intervention_has_abstract_provenance(sentence):
    article = {
        "pmid": "MOCK-SUPPORTED-DRUG",
        "title": "Mock study of rituximab",
        "abstract": sentence,
        "publication_types": [],
    }
    details = extract_article_clinical_details(article)
    claim = details["provenance"]["intervention"]
    cell = _intervention_comparison_cell(
        extract_clinical_profile(sentence), sentence, article["title"],
    )
    assert "rituksimab" in details["intervention"].casefold()
    assert any(label in cell.casefold() for label in ("rituksimab", "rituximab"))
    assert claim["source"] == "abstract"
    assert claim["source_sentence"] == sentence
    assert "başlı" not in cell


def test_title_label_is_not_matched_inside_longer_abstract_label():
    # Both names are real recognized labels; the article itself is wholly mock.
    from report_generator import _recognized_study_interventions

    abstract = "Patients were treated with methylprednisolone."
    names = _recognized_study_interventions(abstract, "Mock study of prednisolone")
    assert names == _recognized_study_interventions(abstract, "")
    assert names == ["metilprednizolon"]
    article = {
        "pmid": "MOCK-LABEL-BOUNDARY",
        "title": "Mock study of prednisolone",
        "abstract": abstract,
        "publication_types": [],
    }
    details = extract_article_clinical_details(article)
    cell = _intervention_comparison_cell(
        extract_clinical_profile(abstract), abstract, article["title"],
    )
    assert details["intervention"].casefold() == "metilprednizolon"
    assert cell.casefold() == "metilprednizolon"
    assert details["provenance"]["intervention"]["source"] == "abstract"


def test_exclusion_mention_does_not_replace_valid_treatment_source():
    excluded = "Patients treated with rituximab were excluded."
    treatment = "Patients were treated with methylprednisolone."
    abstract = excluded + " " + treatment
    article = {
        "pmid": "MOCK-MIXED-SOURCES",
        "title": "Mock study of rituximab and methylprednisolone",
        "abstract": abstract,
        "publication_types": [],
    }
    details = extract_article_clinical_details(article)
    claim = details["provenance"]["intervention"]
    cell = _intervention_comparison_cell(
        extract_clinical_profile(abstract), abstract, article["title"],
    )
    assert details["intervention"].casefold() == "metilprednizolon"
    assert cell.casefold() == "metilprednizolon"
    assert claim["source"] == "abstract"
    assert claim["source_sentence"] == treatment
    assert "Kaynak: makale başlığı" not in _format_bound_claims(details)
