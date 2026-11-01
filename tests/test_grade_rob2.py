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


def test_grade_does_not_assume_low_risk_of_bias():
    g = assess_grade("rct")
    assert g.starting == "High"
    assert g.final == "Değerlendirilemedi"


def test_unknown_design_is_not_rated_very_low():
    g = assess_grade("unclassified", rob2_overall="Low")
    assert g.final == "Değerlendirilemedi"
    assert g.starting == "Değerlendirilemedi"


def test_enrich_record_gives_signals_not_a_rob2_rating():
    from universal_evidence_engine import enrich_record
    rec = enrich_record({"abstract": RCT_GOOD, "publication_types": ["Randomized Controlled Trial"],
                         "study_design_info": {"design_key": "rct"}})
    assert rec["rob2"]["status"] == "not_assessed"
    assert rec["rob2"]["overall"] is None
    assert "d1_randomization" not in rec["rob2"]
