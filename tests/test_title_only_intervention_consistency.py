"""Intervention source consistency with explicitly mock, offline articles."""

import pytest

from report_generator import (
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
    values = [details["intervention"], section6, cell]
    if in_abstract:
        assert [value.casefold() for value in values] == ["rituksimab"] * 3
    else:
        for value in values:
            assert "rituksimab" not in value.casefold()
            assert "rituximab" not in value.casefold()
