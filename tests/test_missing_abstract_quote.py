"""Synthetic mock records only; no real publication identities or claims."""

import pytest

from report_generator import generate_rule_based_turkish_report
from tools.report_quality_audit import audit_report_quality


MISSING_LABEL = "Özet PubMed'de mevcut değil; bulgu çıkarılmadı"
NORMAL_ABSTRACT = "This mock observational study evaluated treatment outcomes in adults."


def mock_articles(abstract):
    return [
        {"title": "Mock record without abstract", "abstract": abstract,
         "authors": ["Mock Author"], "journal": "Mock Journal",
         "publication_types": ["Journal Article"]},
        {"title": "Mock record with abstract", "abstract": NORMAL_ABSTRACT,
         "authors": ["Mock Author"], "journal": "Mock Journal",
         "publication_types": ["Journal Article"]},
    ]


@pytest.mark.parametrize("abstract", [
    "Özet bulunamadı.", "Özet bilgisi bulunamadı.", "", "   ",
    "  Özet bulunamadı.\n",
])
def test_missing_abstract_is_not_quoted_in_full_report(abstract):
    report = generate_rule_based_turkish_report("mock treatment", mock_articles(abstract))

    assert 'Kaynak cümle: "Özet bulunamadı' not in report
    assert 'Kaynak cümle: "Özet bilgisi bulunamadı' not in report
    assert MISSING_LABEL in report
    assert f'Kaynak cümle: "{NORMAL_ABSTRACT}"' in report
    assert "Uzman Hekim Değerlendirmesi: Yapılmadı" in report
    assert audit_report_quality(report)["summary"]["passed_critical"]
