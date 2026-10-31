from effect_size_extractor import extract_effect_sizes, summarize_effects
import pytest

SAMPLE = ("In this randomized trial of 452 patients, the hazard ratio for "
          "progression was 0.62 (95% CI 0.48-0.80; p=0.001). "
          "Mean difference in quality of life was 4.3 (95% CI 1.2-7.4).")

def test_extracts_hr_and_ci():
    effects = extract_effect_sizes(SAMPLE)
    assert any(e.type == "HR" for e in effects)
    hr = next(e for e in effects if e.type == "HR")
    assert hr.value == 0.62
    assert hr.ci_low == 0.48
    assert hr.ci_high == 0.80

def test_extracts_md():
    assert any(e.type == "MD" for e in extract_effect_sizes(SAMPLE))

def test_summary_primary():
    s = summarize_effects(extract_effect_sizes(SAMPLE))
    assert s["primary"] is not None

def test_empty_input():
    assert extract_effect_sizes("") == []
    assert summarize_effects([])["primary"] is None

def test_randomization_ratio_not_captured_as_n():
    sample_ratio = (
        "In this phase 3 trial, patients were randomly assigned 1:1 to receive drug or placebo. "
        "A total of 90 patients were evaluated, and the hazard ratio was 0.70 (95% CI 0.50-0.95; p=0.02)."
    )
    effects = extract_effect_sizes(sample_ratio)
    assert len(effects) >= 1
    hr = next(e for e in effects if e.type == "HR")
    assert hr.n == 90
    assert hr.n != 1

def test_n_equals_pattern():
    sample_n = "The hazard ratio was 0.55 (95% CI 0.35-0.85; p=0.005, n = 90)."
    effects = extract_effect_sizes(sample_n)
    hr = next(e for e in effects if e.type == "HR")
    assert hr.n == 90


@pytest.mark.parametrize("count_text, expected", [
    ("n = 100:1", None),
    ("2:90 patients", None),
    ("2 : 90 patients", None),
    ("n = 1234567", 1234567),
    ("total of 1,200 patients", 1200),
    ("n = 90.5", None),
    ("n = 0", None),
    ("enrolled 90, with treatment", 90),
    ("enrolled 90.", 90),
    ("assigned 2 : 90 patients, enrolled 120", 120),
])
def test_sample_size_requires_whole_participant_count(count_text, expected):
    effects = extract_effect_sizes(f"{count_text}; HR 0.7 (95% CI 0.5-0.9).")
    hr = next(effect for effect in effects if effect.type == "HR")
    assert hr.n == expected
