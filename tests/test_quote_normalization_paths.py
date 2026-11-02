"""Quote rendering regressions; all source content and identifiers are mock data."""

import re
from unittest.mock import patch

import pytest

import evidence_model as em
import grade_assessment as ga
import report_generator as rg


ENDINGS = [
    ("..", "."), ("...", "..."), ("…", "…"),
    ("..)", ".)"), ("..]", ".]"), ('.."', '."'),
    ("..'", ".'"), ("..’”", ".’”"), ("..)]”", ".)]”"),
    ("...)", "...)"), ('...]"', '...]"'), ("…)", "…)"),
]


def assert_quote(output, expected):
    assert f'Kaynak cümle: "{expected}"' in output
    assert not re.search(r'(?<!\.)\.\.(?=[)\]”’\"\']*(?:\"|\)|\]))', output)


@pytest.mark.parametrize("ending, normalized", ENDINGS)
def test_helper_and_all_rendering_paths(ending, normalized):
    sentence = "Mock internal.. marker" + ending
    expected = "Mock internal.. marker" + normalized
    assert rg._quote_sentence(sentence) == expected
    source = em.EvidenceSource(sentence=sentence)
    study = em.Study(
        pmid="MOCK-PMID", doi="", title="Mock record", journal="", year="",
        design_key="unknown", design_label="Mock design",
        evidence_level="Değerlendirilemedi", evidence_level_note="",
        claim_type="unknown", claim_type_tr="Mock claim", causal_inference_allowed=False,
        results_reported=True, population=em.Population(n_total=1, source=source),
        outcomes=[em.Outcome(name="Mock outcome", estimates=[em.EffectEstimate(
            measure="RR", measure_text="Mock measure", family="ratio",
            value=1.0, value_text="1.0", source=source,
        )])],
        other_numeric_findings=[{"outcome": "Mock outcome", "metrics": ["Mock metric"], "source": source}],
    )
    quotes = [line for line in em.render_study_card_lines(study) if "Kaynak cümle:" in line]
    assert len(quotes) == 3  # source note, estimate, and other numeric finding
    for quote in quotes:
        assert_quote(quote, expected)
    assert source.sentence == sentence  # Rendering must not mutate source evidence.

    note = {
        "pmid": "MOCK-PMID", "design": "Mock design", "ceiling_reason": "Mock reason",
        "outcomes": [{"outcome": "Mock outcome", "source_sentence": sentence,
                      "domains": {key: {"status": "değerlendirilemedi"} for key in (
                          "risk_of_bias", "inconsistency", "indirectness", "imprecision", "publication_bias",
                      )}}],
    }
    with patch.object(ga, "assess_preliminary_grade", return_value=note):
        output = ga.format_preliminary_grade_markdown("Mock query", [{}])
    assert_quote(output, expected)
    assert "GRADE Değerlendirilmedi (Not Assessed)" in output


def test_only_terminal_double_period_is_changed():
    assert rg._quote_sentence("  Mock\n internal.. marker..  ") == "Mock internal.. marker."
    for sentence in ("Mock..) internal", "Mock..] internal", "Mock....)", "Mock 1.25?!", ""):
        assert rg._quote_sentence(sentence) == sentence
