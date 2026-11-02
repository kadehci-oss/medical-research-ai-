"""Regression coverage using explicitly synthetic mock article records."""

import pytest

from report_generator import (
    MISSING_ABSTRACT_LABEL,
    _has_real_abstract,
    format_klinik_bulgular_cell,
    format_methodological_limitation,
)


@pytest.mark.parametrize("abstract", [
    None, "", "   ", "Özet bulunamadı.", "Özet bilgisi bulunamadı.",
])
def test_missing_abstract_preserves_title_derived_limitation(abstract):
    article = {
        "title": "Synthetic mock clinical observation: a case report",
        "abstract": abstract,
        "publication_types": ["Journal Article"],
    }

    result = format_methodological_limitation(article)

    assert MISSING_ABSTRACT_LABEL in result
    assert "Kontrol grubu yok" in result
    assert "Kaynak başlık:" in result
    assert article["title"] in result
    assert "Özet bulunamadı." not in result
    assert "Özet bilgisi bulunamadı." not in result
    assert article["abstract"] == abstract


@pytest.mark.parametrize("article", [None, [], "mock", 42, False])
def test_has_real_abstract_rejects_non_dictionaries(article):
    assert _has_real_abstract(article) is False


def test_none_formatters_use_missing_abstract_behavior():
    assert format_klinik_bulgular_cell(None) == f"{MISSING_ABSTRACT_LABEL} (PMID: yok)."
    assert format_methodological_limitation(None) == MISSING_ABSTRACT_LABEL


def test_missing_abstract_without_title_limitation_returns_label_only():
    assert format_methodological_limitation({
        "title": "Synthetic mock record", "abstract": "Özet bulunamadı.",
    }) == MISSING_ABSTRACT_LABEL


def test_real_abstract_limitation_output_is_unchanged():
    article = {
        "title": "Synthetic mock case report",
        "abstract": "We report a case in this synthetic mock example.",
        "publication_types": ["Case Reports"],
    }
    assert _has_real_abstract(article) is True
    assert format_methodological_limitation(article) == (
        "Tasarımından türetilen sınırlılık (PMID: yok): Kontrol grubu yok."
    )
