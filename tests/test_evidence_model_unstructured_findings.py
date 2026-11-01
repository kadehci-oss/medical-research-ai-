import evidence_model as em


ARTICLE = {
    "pmid": "98765432",
    "doi": "10.1000/unstructured",
    "title": "Example report of explicit abstract findings",
    "publication_types": ["Journal Article"],
    "abstract": (
        "Prevalence of thyroid disease among inpatients is approximately 1% to 2%. "
        "The positive likelihood ratio associated with an abnormal sTSH test result in ill inpatients is about 10 compared with about 100 in outpatients. "
        "Those with developmental delay were two times more likely to present seizures. "
        "All patients (100%) reached in a phone survey stated that their symptoms resolved or improved after surgery."
    ),
}


def test_explicit_abstract_findings_stay_source_bound_and_unstructured():
    findings = em.extract_explicit_unstructured_numeric_findings(ARTICLE)
    flattened = " | ".join(
        f"{item['outcome']} {' '.join(item['metrics'])}"
        for item in findings
    ).casefold()

    assert "approximately 1% to 2%" in flattened
    assert "positive likelihood ratio" in flattened
    assert "about 10 compared with about 100" in flattened
    assert "two times more likely to present seizures" in flattened
    assert "100%" in flattened
    assert all(item["source"].verification_status == em.SOURCE_VERIFIED for item in findings)


def test_study_validator_accepts_the_unstructured_source_linked_findings():
    em.clear_cache()
    study = em.build_study(ARTICLE)

    result = em.validate_study(study, ARTICLE)

    assert result["valid"] is True
    assert result["source_provenance_complete"] is True
    assert result["clinical_claim_validation"] == "not_independently_clinically_validated"
    assert study.other_numeric_findings


def test_case_control_total_accepts_explicit_in_n_patients_phrase():
    article = {
        "pmid": "17540675",
        "doi": "10.1093/jac/dkm141",
        "abstract": (
            "Risk of ampicillin-resistant E. coli infection in 903 patients was associated "
            "with amoxicillin prescriptions of 7 days duration."
        ),
    }

    population = em.extract_population(article, "case_control", [], [])

    assert population.n_total == 903
    assert population.n_kind == "enrolled"
    assert population.source.sentence in article["abstract"]
