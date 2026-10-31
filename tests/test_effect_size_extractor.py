from effect_size_extractor import extract_effect_sizes, summarize_effects

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
