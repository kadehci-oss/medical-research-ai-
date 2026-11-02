"""Punctuation regressions using explicitly synthetic source sentences."""

import re
from unittest.mock import patch

import pytest

from report_generator import (
    _claim_source_phrase,
    _quote_sentence,
    format_klinik_bulgular_cell,
    format_methodological_limitation,
)


@pytest.mark.parametrize("ending, expected", [("..", "."), ("...", "..."), (".", "."), ("…", "…")])
def test_source_quote_punctuation(ending, expected):
    sentence = "Mock source contains an internal.. marker" + ending
    normalized = "Mock source contains an internal.. marker" + expected
    assert _quote_sentence(sentence) == normalized

    claim = _claim_source_phrase(
        {"source": "abstract", "source_sentence": sentence}, "MOCK-PMID", set()
    )
    with patch("report_generator.extract_methodological_limitations", return_value=[{
        "kind": "explicit", "source_sentence": sentence,
    }]):
        limitation = format_methodological_limitation({"pmid": "MOCK-PMID", "abstract": sentence})
    with patch("report_generator.structured_findings", return_value=[]), patch(
        "report_generator.extract_clinical_profile",
        return_value=[{"category": "mock", "sentence": sentence, "line": "Mock profile"}],
    ):
        findings = format_klinik_bulgular_cell({"pmid": "MOCK-PMID", "abstract": sentence})

    for output in (claim, limitation, findings):
        assert f'Kaynak cümle: "{normalized}"' in output
        assert not re.search(r'(?<!\.)\.\."|"\.\.(?!\.)', output)


def test_quote_preserves_other_content():
    assert _quote_sentence("Mock.. internal marker; 1.25?!") == "Mock.. internal marker; 1.25?!"


@pytest.mark.parametrize("ending, expected", [("..", "."), ("...", "..."), (".", "."), ("…", "…")])
def test_report_background_quote(ending, expected):
    from report_generator import generate_rule_based_turkish_report
    from tools.report_quality_audit import audit_report_quality

    article = {
        "pmid": "MOCK-PMID", "title": "Mock record",
        "abstract": "Mock source sentence" + ending,
        "authors": [], "publication_types": [], "pub_year": "",
    }
    # Isolate quote rendering from the independent sentence segmentation logic.
    with patch("report_generator._sentence_around", return_value=article["abstract"]):
        report = generate_rule_based_turkish_report("Mock query", [article])
    background = report.split("## 4.", 1)[1].split("## 5.", 1)[0]
    assert f'Kaynak cümle: "Mock source sentence{expected}"' in background
    assert not re.search(r'(?<!\.)\.\."|"\.\.(?!\.)', background)
    assert "Uzman Hekim Değerlendirmesi: Yapılmadı" in report
    assert "Kanıt düzeyi: Değerlendirilemedi" in background
    assert audit_report_quality(report)["summary"]["passed_critical"]
