from rob2_assessor import assess_rob2
from grade_assessor import assess_grade

RCT_GOOD = ("Randomized, double-blind, intention-to-treat trial. Registered at "
            "ClinicalTrials.gov. 320 patients. HR 0.70 (95% CI 0.55-0.89).")
OBS_BAD = "Observational cohort study. No blinding, no registration mentioned."

def test_rob2_rct():
    r = assess_rob2(RCT_GOOD)
    assert r.overall in ("Low", "Some concerns")

def test_rob2_observational():
    r = assess_rob2(OBS_BAD)
    assert r.overall in ("Some concerns", "High")

def test_grade_rct():
    g = assess_grade("rct", rob2_overall="Low")
    assert g.starting == "High"
    assert g.final in ("High", "Moderate")

def test_grade_cohort_downgrades():
    g = assess_grade("cohort", rob2_overall="High",
                     heterogeneity_i2=80, imprecision=True)
    assert g.final in ("Low", "Very low")
    assert len(g.downgrades) >= 2
