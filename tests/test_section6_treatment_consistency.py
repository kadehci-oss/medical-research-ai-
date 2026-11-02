"""Section 6 treatment consistency using explicitly synthetic, offline records."""

import pytest

from report_generator import _format_cross_study_comparison


@pytest.mark.parametrize(
    "title",
    ["Mock treatment study", "Mock treatment study of methotrexate"],
)
def test_both_cells_use_the_same_treatments_from_abstract(title):
    article = {
        "pmid": "MOCK-SECTION6",
        "title": title,
        "abstract": (
            "Patients were treated with intravenous immunoglobulin and rituximab. "
            "Other patients received cyclophosphamide and plasma exchange."
        ),
        "publication_types": [],
    }

    table = _format_cross_study_comparison([article])
    row = next(line for line in table.splitlines() if line.startswith("| MOCK-SECTION6 |"))
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    intervention, findings = cells[3:5]

    assert set(intervention.split(", ")) == {
        "IVIG", "rituksimab", "siklofosfamid", "plazma değişimi",
    }
    assert findings == "Tedavi: " + intervention + "."
    assert "metotreksat" not in intervention
