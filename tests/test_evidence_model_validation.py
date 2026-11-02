import copy

import evidence_model as em


ARTICLE = {
    "pmid": "12345678",
    "doi": "10.1000/example",
    "title": "Randomized trial of an example treatment",
    "publication_types": ["Randomized Controlled Trial"],
    "abstract": (
        "A total of 100 patients were randomly assigned to drug A or placebo. "
        "Death occurred in 10 of 50 patients in the drug A group and 20 of 50 in the placebo group "
        "(hazard ratio, 0.45; 95% CI, 0.20 to 0.98; P=0.04)."
    ),
}


def _study():
    em.clear_cache()
    return em.build_study(copy.deepcopy(ARTICLE))


def test_validator_accepts_canonical_study_with_article_bound_sources():
    study = _study()

    result = em.validate_study(study, ARTICLE)

    assert result["valid"] is True
    assert result["status"] == "structurally_valid"
    assert result["source_provenance_complete"] is True
    assert list(em.iter_sourced_claims(study))
    assert result["clinical_claim_validation"] == "not_independently_clinically_validated"
    assert result["formal_grade_status"] == "not_assessed"


def test_validator_flags_source_sentence_not_in_supplied_article():
    study = _study()
    assert study.estimates
    study.estimates[0].source.sentence = "This sentence is not in the fetched record."

    result = em.validate_study(study, ARTICLE)

    assert result["valid"] is False
    assert any(error.startswith("source_sentence_not_in_article:") for error in result["errors"])


def test_validator_flags_population_description_number_not_in_its_source_sentence():
    study = _study()
    study.population.description = "100 patients; n = 9"

    result = em.validate_study(study, ARTICLE)

    assert result["valid"] is False
    assert "unsupported_numeric_text:population.description" in result["errors"]


def test_validator_flags_outcome_value_not_in_its_source_sentence():
    study = _study()
    estimate = study.outcomes[0].estimates[0]
    estimate.value = 0.99

    result = em.validate_study(study, ARTICLE)

    assert result["valid"] is False
    assert "unsupported_numeric_value:outcomes[0].estimates[0].value" in result["errors"]


def test_validator_flags_article_identity_mismatch():
    study = _study()
    changed_article = copy.deepcopy(ARTICLE)
    changed_article["pmid"] = "87654321"

    result = em.validate_study(study, changed_article)

    assert result["valid"] is False
    assert "study_article_pmid_mismatch" in result["errors"]


def test_validator_rejects_noncanonical_parallel_dict_model():
    result = em.validate_study({"pmid": ARTICLE["pmid"], "outcomes": []})

    assert result["valid"] is False
    assert result["errors"] == ["unsupported_model_type"]
