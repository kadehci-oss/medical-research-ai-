import pytest
from universal_evidence_engine import UniversalEvidenceEngine, run_universal_evidence_search
from report_generator import (
    extract_pico,
    extract_study_metrics,
    extract_outcome_metrics,
    extract_article_clinical_details,
    classify_study_design,
    assess_risk_of_bias,
    perform_red_team_audit
)


def test_cardiology_rct_and_cohort():
    """Cardiology: SGLT2 inhibitors in heart failure (RCT vs Cohort)."""
    query = "Empagliflozin in patients with heart failure with preserved ejection fraction"

    art_rct = {
        "pmid": "34449189",
        "doi": "10.1056/nejmoa2107038",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker", "Gerasimos Filippatos", "Avae Alikhan"],
        "journal": "N Engl J Med",
        "pub_year": "2021",
        "publication_types": ["Randomized Controlled Trial", "Journal Article"],
        "abstract": (
            "BACKGROUND: Empagliflozin reduced the risk of heart failure hospitalization in patients with HFpEF. "
            "METHODS: In a double-blind trial, 5988 patients with class II-IV heart failure and EF > 40% were randomized to empagliflozin (10 mg daily) or placebo. "
            "RESULTS: Over 26.2 months, primary outcome occurred in 415 of 2997 patients in empagliflozin vs 511 of 2991 in placebo (HR 0.79; 95% CI 0.69 to 0.90; p < 0.001). "
            "Heart failure hospitalizations were reduced (HR 0.71; 95% CI 0.60 to 0.83; p < 0.001). "
            "CONCLUSIONS: Empagliflozin reduced the combined risk of CV death or HF hospitalization."
        )
    }

    engine = UniversalEvidenceEngine()
    processed = engine.process_and_extract_parameters([art_rct], query)
    assert len(processed) == 1
    p = processed[0]

    assert p["study_design"]["design"] == "Rastgele Kontrollü Çalışma (RCT)"
    assert p["sample_size_n"] == "5988"
    assert len(p["effect_sizes"]) >= 1
    assert any("0.79" in es for es in p["effect_sizes"])
    assert any("0.69" in ci for ci in p["confidence_intervals"])

    cross_res = engine.compare_cross_article_findings([art_rct], query)
    assert cross_res["total_articles"] == 1
    assert cross_res["primary_study_count"] == 1


def test_neurology_anti_hmgcr_case_control():
    """Neurology: Anti-HMGCR myopathy and statin exposure."""
    query = "Anti-HMGCR myopathy in patients with statin exposure"

    art_cc = {
        "pmid": "29480216",
        "doi": "10.3233/jnd-170282",
        "title": "Anti-HMGCR Myopathy",
        "authors": ["Andrew L Mammen"],
        "journal": "J Neuromuscul Dis",
        "pub_year": "2018",
        "publication_types": ["Journal Article", "Case-Control Study"],
        "abstract": (
            "Anti-HMGCR myopathy is an autoimmune necrotizing myopathy strongly associated with statin use in adults. "
            "In a case-control study including n = 150 anti-HMGCR positive myopathy cases and 300 controls, "
            "prior statin exposure was strongly associated with disease onset (OR 5.4; 95% CI 3.1 to 9.2; p < 0.0001). "
            "Immunosuppressive therapy with corticosteroids and IVIG achieved remission in majority of patients."
        )
    }

    design = classify_study_design(art_cc["publication_types"], art_cc["title"], art_cc["abstract"])
    assert design["design"] == "Vaka-Kontrol Çalışması"

    metrics = extract_study_metrics(art_cc["abstract"])
    assert metrics["n"] == "150"
    assert any("OR 5.4" in es or "5.4" in es for es in metrics["effect_sizes"])
    assert any("p < 0.0001" in pv or "p<0.0001" in pv for pv in metrics["p_values"])


def test_oncology_immunotherapy_phase3_trial():
    """Oncology: Pembrolizumab in non-small cell lung cancer (NSCLC)."""
    query = "Pembrolizumab versus chemotherapy in advanced non-small cell lung cancer"

    art_onc = {
        "pmid": "30345905",
        "doi": "10.1056/nejmoa1801005",
        "title": "Pembrolizumab plus Chemotherapy in Metastatic Non-Small-Cell Lung Cancer",
        "authors": ["Leena Gandhi", "Delvys Rodriguez-Abreu", "Suresh Senan"],
        "journal": "N Engl J Med",
        "pub_year": "2018",
        "publication_types": ["Clinical Trial, Phase III", "Randomized Controlled Trial"],
        "abstract": (
            "BACKGROUND: First-line pembrolizumab plus chemotherapy in metastatic NSCLC. "
            "METHODS: A total of 616 patients with metastatic non-squamous NSCLC were randomized to receive pembrolizumab or placebo with chemotherapy. "
            "RESULTS: Overall survival at 12 months was 69.2% in pembrolizumab group vs 49.4% in placebo group (HR 0.49; 95% CI 0.38 to 0.64; p < 0.001). "
            "Progression-free survival was longer with pembrolizumab (median 8.8 months vs 4.9 months; HR 0.52; 95% CI 0.43 to 0.64; p < 0.001). "
            "Adverse events occurred in 99.8% of patients."
        )
    }

    pico = extract_pico(query)
    assert "pembrolizumab" in pico["intervention"].lower()
    assert "chemotherapy" in pico["comparison"].lower()

    details = extract_article_clinical_details(art_onc, query)
    assert details["sample_size"] == "n = 616"
    assert "HR 0.49" in details["outcomes_summary"] or "Overall Survival" in details["outcomes_summary"]


def test_ent_kbb_guideline_and_biologic():
    """ENT / KBB: Dupilumab in chronic rhinosinusitis with nasal polyps."""
    query = "Dupilumab in patients with chronic rhinosinusitis with nasal polyps"

    art_guideline = {
        "pmid": "31960990",
        "doi": "10.1111/rhin.20.001",
        "title": "European Position Paper on Rhinosinusitis and Nasal Polyps 2020",
        "authors": ["W J Fokkens", "V J Lund", "C Hopkins"],
        "journal": "Rhinology",
        "pub_year": "2020",
        "publication_types": ["Practice Guideline", "Consensus Development Conference"],
        "abstract": (
            "This EPOS 2020 guidelines paper summarizes evidence-based management of rhinosinusitis. "
            "Biologics targeting Type 2 inflammation including dupilumab are recommended for severe CRSwNP."
        )
    }

    art_rct_ent = {
        "pmid": "31543078",
        "doi": "10.1016/s0140-6736(19)31881-1",
        "title": "Efficacy and safety of dupilumab in patients with severe chronic rhinosinusitis with nasal polyps",
        "authors": ["Claus Bachert", "Leda P Mannent", "M Asif Khan"],
        "journal": "Lancet",
        "pub_year": "2019",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": (
            "LIBERTY NP SINUS-24 and SINUS-52 enrolled 724 adult patients with severe CRSwNP. "
            "Dupilumab significantly reduced nasal polyp score (MD -1.89; 95% CI -2.19 to -1.59; p < 0.0001) "
            "and improved nasal congestion score."
        )
    }

    engine = UniversalEvidenceEngine()
    comp = engine.compare_cross_article_findings([art_guideline, art_rct_ent], query)

    assert comp["total_articles"] == 2
    assert comp["primary_study_count"] == 1
    assert comp["review_study_count"] == 1
    assert len(comp["non_comparable_studies"]) >= 1


def test_rheumatology_biologics_ra():
    """Rheumatology: Tocilizumab in rheumatoid arthritis."""
    query = "Tocilizumab versus methotrexate in rheumatoid arthritis"

    art_rheum = {
        "pmid": "23746811",
        "doi": "10.1016/s0140-6736(13)60833-3",
        "title": "Tocilizumab monotherapy versus methotrexate monotherapy in rheumatoid arthritis",
        "authors": ["Josef S Smolen", "E W St Clair", "L B Fleischmann"],
        "journal": "Lancet",
        "pub_year": "2013",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": (
            "In a double-blind RCT involving 321 patients with active rheumatoid arthritis, "
            "tocilizumab monotherapy resulted in higher ACR20 response rate compared to methotrexate "
            "(OR 2.3; 95% CI 1.4 to 3.8; p = 0.001). DAS28 remission was achieved in 39% vs 15%."
        )
    }

    rob = assess_risk_of_bias(art_rheum)
    assert rob["tool"] == "RoB 2 (Cochrane Risk of Bias for RCTs)"
    assert rob["overall_rating"] == "Değerlendirilmedi (Not Assessed)"


def test_endocrinology_semaglutide_diabetes():
    """Endocrinology: Semaglutide in type 2 diabetes."""
    query = "Semaglutide in patients with type 2 diabetes"

    art_endo = {
        "pmid": "28818818",
        "doi": "10.1016/s2213-8587(17)30217-9",
        "title": "Efficacy and safety of once-weekly semaglutide in type 2 diabetes",
        "authors": ["Richard M Bergenstal"],
        "journal": "Lancet Diabetes Endocrinol",
        "pub_year": "2017",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": (
            "A total of 813 patients with type 2 diabetes were randomized to once-weekly semaglutide (0.5 mg or 1.0 mg) or sitagliptin. "
            "Semaglutide reduced HbA1c significantly (MD -1.4%; 95% CI -1.6 to -1.2; p < 0.0001) "
            "and body weight (MD -4.3 kg; 95% CI -5.1 to -3.5; p < 0.0001)."
        )
    }

    metrics = extract_study_metrics(art_endo["abstract"])
    assert metrics["n"] == "813"
    assert any("MD -1.4%" in es or "-1.4%" in es or "MD" in es for es in metrics["effect_sizes"])


def test_infectious_diseases_paxlovid_covid19():
    """Infectious Diseases: Paxlovid (Nirmatrelvir/ritonavir) in COVID-19."""
    query = "Nirmatrelvir plus ritonavir in patients with non-hospitalized COVID-19"

    art_id = {
        "pmid": "35172054",
        "doi": "10.1056/nejmoa2118542",
        "title": "Oral Nirmatrelvir for Unvaccinated Outpatients with Covid-19",
        "authors": ["Jennifer Hammond", "Hanna Leister-Tebbe", "Anya Gardner"],
        "journal": "N Engl J Med",
        "pub_year": "2022",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": (
            "BACKGROUND: Nirmatrelvir is an oral protease inhibitor for SARS-CoV-2. "
            "METHODS: Unvaccinated, non-hospitalized adults with symptomatic Covid-19 (n = 2246) were assigned to nirmatrelvir plus ritonavir or placebo every 12 hours for 5 days. "
            "RESULTS: Covid-19-related hospitalization or death by day 28 was 0.72% in nirmatrelvir group vs 6.53% in placebo (relative risk reduction 89%; HR 0.12; 95% CI 0.06 to 0.24; p < 0.001). "
            "No deaths were reported in the treatment group."
        )
    }

    engine = UniversalEvidenceEngine()
    report = engine.generate_synthesis_report(query, [art_id])
    assert report["status"] == "success"
    md = report["report_markdown"]

    assert "# 📑 Türkçe Klinik Araştırma Raporu" in md
    assert "## 1. Klinik Araştırma Sorusu" in md
    assert "## 12. Klinik Sonuç" in md
    assert "## 13. Doğrulanmış Kaynakça" in md
    assert audit_check(report["audit"])


def audit_check(audit_dict):
    return (
        audit_dict.get("clinical_validation_status") == "Klinik Doğrulama Yapılmamıştır (No Clinical Validation Claimed)" and
        audit_dict.get("expert_physician_review") == "Yapılmadı / Tamamlanmadı (Incomplete / Not Performed)"
    )
