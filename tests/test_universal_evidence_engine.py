import unittest
from unittest.mock import patch, MagicMock

from universal_evidence_engine import (
    UniversalEvidenceEngine,
    run_universal_evidence_search,
    generate_universal_evidence_synthesis
)


# Mock articles across 5 distinct medical specialties:
# 1. Cardiology, 2. Neurology, 3. Oncology, 4. ENT (KBB), 5. Infectious Diseases

CARDIOLOGY_ARTICLES = [
    {
        "pmid": "34449189",
        "doi": "10.1056/NEJMoa2107038",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker", "Javed Butler", "Gerasimos Filippatos"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2021",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": "In a trial of 5988 patients with heart failure and ejection fraction > 40% (n=5988), Empagliflozin reduced cardiovascular death or hospitalization for heart failure (HR 0.79, 95% CI 0.69-0.90, p<0.001) compared to placebo.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/34449189/",
        "doi_url": "https://doi.org/10.1056/NEJMoa2107038"
    }
]

NEUROLOGY_ARTICLES = [
    {
        "pmid": "25671797",
        "doi": "10.1056/NEJMoa1411587",
        "title": "Endovascular Treatment for Acute Ischemic Stroke in the MR CLEAN Trial",
        "authors": ["Oloufeemi A Berkhemer", "Puck S S Fransen", "Debbie Beumer"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2015",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In 500 patients with acute ischemic stroke caused by anterior circulation occlusion (n=500), intraarterial treatment plus usual care significantly improved functional independence (OR 1.67, 95% CI 1.21-2.30, p=0.002) compared to usual care alone.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/25671797/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1411587"
    }
]

ONCOLOGY_ARTICLES = [
    {
        "pmid": "26516180",
        "doi": "10.1056/NEJMoa1508740",
        "title": "Pembrolizumab versus Chemotherapy for Advanced Non-Small-Cell Lung Cancer",
        "authors": ["Roy S Herbst", "Paul Baas", "D-W Kim"],
        "journal": "The Lancet",
        "pub_year": "2016",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In 1034 patients with previously treated PD-L1-positive advanced NSCLC (n=1034), Pembrolizumab prolonged overall survival (HR 0.71, 95% CI 0.58-0.88, p=0.0008) compared to docetaxel.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/26516180/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1508740"
    }
]

ENT_KBB_ARTICLES = [
    {
        "pmid": "31542298",
        "doi": "10.1016/S0140-6736(19)31881-1",
        "title": "Efficacy and safety of dupilumab in patients with severe chronic rhinosinusitis with nasal polyps (LIBERTY NP SINUS-24 and LIBERTY NP SINUS-52)",
        "authors": ["Claus Bachert", "Leda P Mannent", "Rhuen-Chi Naclerio"],
        "journal": "The Lancet",
        "pub_year": "2019",
        "publication_types": ["Randomized Controlled Trial", "Clinical Trial"],
        "abstract": "In two randomized trials of 724 adult patients with severe chronic rhinosinusitis with nasal polyps (n=724), add-on dupilumab reduced nasal polyp score (MD -1.89, 95% CI -2.23 to -1.55, p<0.0001) and improved nasal congestion compared to placebo.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31542298/",
        "doi_url": "https://doi.org/10.1016/S0140-6736(19)31881-1"
    }
]

INFECTIOUS_DISEASE_ARTICLES = [
    {
        "pmid": "35172054",
        "doi": "10.1056/NEJMoa2118542",
        "title": "Nirmatrelvir for Early Treatment of Covid-19 in High-Risk Patients",
        "authors": ["Jennifer Hammond", "Hana Leister-Tebbe", "Anette Gardner"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2022",
        "publication_types": ["Randomized Controlled Trial"],
        "abstract": "In a trial of 2246 symptomatic non-hospitalized adults with Covid-19 (n=2246), Nirmatrelvir plus ritonavir (Paxlovid) reduced Covid-19-related hospitalization or death by 89% (RR 0.11, 95% CI 0.04-0.27, p<0.001) compared to placebo without severe adverse events.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/35172054/",
        "doi_url": "https://doi.org/10.1056/NEJMoa2118542"
    }
]


class TestUniversalEvidenceEngine(unittest.TestCase):

    def setUp(self):
        self.engine = UniversalEvidenceEngine()

    # --- 1. Cardiology Tests ---
    def test_cardiology_parameter_extraction_and_synthesis(self):
        query = "SGLT2 inhibitors in heart failure with preserved ejection fraction"
        processed = self.engine.process_and_extract_parameters(CARDIOLOGY_ARTICLES, query)

        self.assertEqual(len(processed), 1)
        cardio = processed[0]
        self.assertEqual(cardio["sample_size_n"], "5988")
        self.assertIn("HR 0.79", cardio["effect_sizes"])
        self.assertIn("p<0.001", cardio["p_values"])
        self.assertIn("Rastgele Kontrollü Çalışma", cardio["study_design"]["design"])

        synth = self.engine.generate_synthesis_report(query, CARDIOLOGY_ARTICLES)
        self.assertEqual(synth["status"], "success")
        self.assertIn("## 12. Klinik Sonuç", synth["report_markdown"])
        self.assertIn("[PMID: 34449189]", synth["report_markdown"])

    # --- 2. Neurology Tests ---
    def test_neurology_parameter_extraction_and_synthesis(self):
        query = "Endovascular thrombectomy in acute ischemic stroke"
        processed = self.engine.process_and_extract_parameters(NEUROLOGY_ARTICLES, query)

        self.assertEqual(len(processed), 1)
        neuro = processed[0]
        self.assertEqual(neuro["sample_size_n"], "500")
        self.assertIn("OR 1.67", neuro["effect_sizes"])
        self.assertIn("p=0.002", neuro["p_values"])

        synth = self.engine.generate_synthesis_report(query, NEUROLOGY_ARTICLES)
        self.assertEqual(synth["status"], "success")
        self.assertIn("[PMID: 25671797]", synth["report_markdown"])
        self.assertIn("## 5. Bilimsel Kanıt Tablosu", synth["report_markdown"])

    # --- 3. Oncology Tests ---
    def test_oncology_parameter_extraction_and_synthesis(self):
        query = "Pembrolizumab in advanced non-small-cell lung cancer"
        processed = self.engine.process_and_extract_parameters(ONCOLOGY_ARTICLES, query)

        self.assertEqual(len(processed), 1)
        onco = processed[0]
        self.assertEqual(onco["sample_size_n"], "1034")
        self.assertIn("HR 0.71", onco["effect_sizes"])
        self.assertIn("p=0.0008", onco["p_values"])

        synth = self.engine.generate_synthesis_report(query, ONCOLOGY_ARTICLES)
        self.assertEqual(synth["status"], "success")
        self.assertIn("[PMID: 26516180]", synth["report_markdown"])

    # --- 4. ENT / KBB Tests ---
    def test_ent_kbb_parameter_extraction_and_synthesis(self):
        query = "Dupilumab in severe chronic rhinosinusitis with nasal polyps"
        processed = self.engine.process_and_extract_parameters(ENT_KBB_ARTICLES, query)

        self.assertEqual(len(processed), 1)
        ent = processed[0]
        self.assertEqual(ent["sample_size_n"], "724")
        self.assertIn("MD -1.89", ent["effect_sizes"])
        self.assertIn("p<0.0001", ent["p_values"])

        synth = self.engine.generate_synthesis_report(query, ENT_KBB_ARTICLES)
        self.assertEqual(synth["status"], "success")
        self.assertIn("[PMID: 31542298]", synth["report_markdown"])

    # --- 5. Infectious Diseases Tests ---
    def test_infectious_diseases_parameter_extraction_and_synthesis(self):
        query = "Nirmatrelvir ritonavir Paxlovid in Covid-19 treatment"
        processed = self.engine.process_and_extract_parameters(INFECTIOUS_DISEASE_ARTICLES, query)

        self.assertEqual(len(processed), 1)
        inf = processed[0]
        self.assertEqual(inf["sample_size_n"], "2246")
        self.assertIn("RR 0.11", inf["effect_sizes"])
        self.assertIn("p<0.001", inf["p_values"])

        synth = self.engine.generate_synthesis_report(query, INFECTIOUS_DISEASE_ARTICLES)
        self.assertEqual(synth["status"], "success")
        self.assertIn("[PMID: 35172054]", synth["report_markdown"])

    # --- 6. Cross-Article Comparative Analysis Test ---
    def test_cross_article_comparison_across_specialties(self):
        all_articles = CARDIOLOGY_ARTICLES + NEUROLOGY_ARTICLES + ONCOLOGY_ARTICLES
        comp = self.engine.compare_cross_article_findings(all_articles, "Multi-specialty trial review")

        self.assertEqual(comp["total_articles"], 3)
        self.assertEqual(comp["primary_study_count"], 3)
        self.assertEqual(comp["consistent_findings"], [])
        self.assertEqual(comp["conflicting_findings"], [])
        self.assertTrue(len(comp["non_comparable_studies"]) > 0)

    # --- 7. Source Contamination & Metric Mixing Prevention Test ---
    def test_source_contamination_and_metric_mixing_prevention(self):
        cardio_art = {
            "pmid": "10001",
            "doi": "10.1000/cardio1",
            "title": "Cardiology Trial for Heart Failure",
            "authors": ["Cardio Author"],
            "pub_year": "2023",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 1200 patients with heart failure (n=1200), Drug A reduced mortality (HR 0.65, 95% CI 0.50-0.85, p=0.001)."
        }
        psych_art = {
            "pmid": "20002",
            "doi": "10.2000/psych1",
            "title": "Psychiatry Trial for Major Depression",
            "authors": ["Psych Author"],
            "pub_year": "2024",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 450 patients with major depression (n=450), Drug B improved remission rate (OR 2.10, 95% CI 1.40-3.15, p<0.001)."
        }

        processed = self.engine.process_and_extract_parameters([cardio_art, psych_art])
        self.assertEqual(len(processed), 2)

        # Confirm PMID 10001 contains ONLY Cardio parameters
        c1 = processed[0] if processed[0]["pmid"] == "10001" else processed[1]
        c2 = processed[1] if processed[1]["pmid"] == "20002" else processed[0]

        self.assertEqual(c1["pmid"], "10001")
        self.assertEqual(c1["sample_size_n"], "1200")
        self.assertIn("HR 0.65", c1["effect_sizes"])
        self.assertNotIn("OR 2.10", c1["effect_sizes"])
        self.assertNotIn("450", c1["sample_size_n"])

        # Confirm PMID 20002 contains ONLY Psych parameters
        self.assertEqual(c2["pmid"], "20002")
        self.assertEqual(c2["sample_size_n"], "450")
        self.assertIn("OR 2.10", c2["effect_sizes"])
        self.assertNotIn("HR 0.65", c2["effect_sizes"])
        self.assertNotIn("1200", c2["sample_size_n"])

    # --- 8. Missing Data and Unstated Metric Handling Test ---
    def test_missing_data_and_unstated_metric_handling(self):
        missing_art = {
            "pmid": "30003",
            "title": "Observational Study on Rare Syndrome",
            "authors": ["No Data Author"],
            "pub_year": "2020",
            "publication_types": ["Journal Article"],
            "abstract": "This qualitative observational study describes clinical observations in rare syndrome patients without quantitative statistical tests."
        }

        processed = self.engine.process_and_extract_parameters([missing_art])
        p = processed[0]

        self.assertIsNone(p["sample_size_n"])
        self.assertEqual(p["effect_sizes"], [])
        self.assertEqual(p["confidence_intervals"], [])
        self.assertEqual(p["p_values"], [])

        comp = self.engine.compare_cross_article_findings([missing_art], "Rare syndrome")
        self.assertEqual(comp["consistent_findings"], [])
        self.assertEqual(comp["conflicting_findings"], [])

    # --- 9. Conflicting Findings Test with Matched PICO and Design ---
    def test_conflicting_findings_with_matched_pico_and_design(self):
        trial_positive = {
            "pmid": "40001",
            "doi": "10.4000/pos",
            "title": "Efficacy of Drug X in Major Depression",
            "authors": ["Positive Author"],
            "pub_year": "2022",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 300 patients with major depression (n=300), Drug X significantly reduced depression symptoms compared to placebo (OR 2.15, 95% CI 1.40-3.30, p<0.001)."
        }
        trial_negative = {
            "pmid": "40002",
            "doi": "10.4000/neg",
            "title": "Evaluation of Drug X in Major Depression",
            "authors": ["Negative Author"],
            "pub_year": "2023",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 320 patients with major depression (n=320), Drug X failed to show significant difference compared to placebo (OR 1.02, 95% CI 0.80-1.30, p=0.85)."
        }

        comp = self.engine.compare_cross_article_findings([trial_positive, trial_negative], "Drug X in major depression")
        self.assertEqual(comp["total_articles"], 2)
        self.assertEqual(comp["primary_study_count"], 2)
        self.assertEqual(len(comp["conflicting_findings"]), 1)
        self.assertIn("çelişkili veya farklı istatistiksel sonuçlar", comp["conflicting_findings"][0]["details"])
        self.assertIn("[PMID: 40001]", comp["conflicting_findings"][0]["details"])
        self.assertIn("[PMID: 40002]", comp["conflicting_findings"][0]["details"])

    # --- 10. Consistent Findings Test with Matched PICO and Design ---
    def test_consistent_findings_with_matched_pico_and_design(self):
        trial1 = {
            "pmid": "50001",
            "doi": "10.5000/trial1",
            "title": "Trial 1 of SGLT2i in Heart Failure",
            "authors": ["Trial1 Author"],
            "pub_year": "2021",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 4000 patients with heart failure (n=4000), SGLT2 inhibitor reduced heart failure hospitalization compared to placebo (HR 0.75, 95% CI 0.65-0.87, p<0.001)."
        }
        trial2 = {
            "pmid": "50002",
            "doi": "10.5000/trial2",
            "title": "Trial 2 of SGLT2i in Heart Failure",
            "authors": ["Trial2 Author"],
            "pub_year": "2022",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 4500 patients with heart failure (n=4500), SGLT2 inhibitor reduced heart failure hospitalization compared to placebo (HR 0.79, 95% CI 0.69-0.90, p<0.001)."
        }

        comp = self.engine.compare_cross_article_findings([trial1, trial2], "SGLT2 inhibitors in heart failure")
        self.assertEqual(len(comp["consistent_findings"]), 1)
        self.assertIn("tutarlı istatistiksel bulgular", comp["consistent_findings"][0]["details"])
        self.assertIn("[PMID: 50001]", comp["consistent_findings"][0]["details"])
        self.assertIn("[PMID: 50002]", comp["consistent_findings"][0]["details"])

    # --- 11. Multi-Specialty 88-Domain Compatibility Test ---
    def test_multi_specialty_88_domain_compatibility(self):
        dermatology_art = {
            "pmid": "60001",
            "doi": "10.6000/derm1",
            "title": "Biologic Therapy in Severe Psoriasis",
            "authors": ["Derm Author"],
            "pub_year": "2023",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 600 adult patients with severe plaque psoriasis (n=600), Biologic X achieved PASI 90 response compared to placebo (OR 4.50, 95% CI 3.10-6.50, p<0.0001)."
        }
        pmr_art = {
            "pmid": "60002",
            "doi": "10.6000/pmr1",
            "title": "Robot-Assisted Gait Training in Post-Stroke Rehabilitation",
            "authors": ["PMR Author"],
            "pub_year": "2024",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In 150 post-stroke rehabilitation patients (n=150), robot-assisted gait training improved walking speed compared to conventional physical therapy (MD 0.25, 95% CI 0.12-0.38, p=0.001)."
        }

        synth = self.engine.generate_synthesis_report("Multi specialty clinical research", [dermatology_art, pmr_art])
        self.assertEqual(synth["status"], "success")
        self.assertIn("## 12. Klinik Sonuç", synth["report_markdown"])
        self.assertIn("[PMID: 60001]", synth["report_markdown"])
        self.assertIn("[PMID: 60002]", synth["report_markdown"])
    # --- 7. Search and Verification with Mocks ---
    @patch("universal_evidence_engine.pubmed_client.search_pubmed")
    def test_search_and_verify_success(self, mock_search):
        mock_search.return_value = {
            "articles": CARDIOLOGY_ARTICLES,
            "total_count": 1,
            "query": "heart failure",
            "search_date": "2026-10-29"
        }

        res = run_universal_evidence_search("heart failure", max_results=5)
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["articles"]), 1)
        self.assertEqual(res["articles"][0]["verification_status"], "verified")
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(mock_search.call_args.kwargs["query"], "heart failure")

    @patch("universal_evidence_engine.pubmed_client.search_pubmed")
    def test_search_and_verify_specialty_expansion_preserves_terms(self, mock_search):
        mock_search.return_value = {
            "articles": CARDIOLOGY_ARTICLES,
            "total_count": 1,
            "query": "expanded",
            "search_date": "2026-10-30",
        }
        res = self.engine.search_and_verify("HFpEF SGLT2 inhibitors", max_results=3)
        self.assertEqual(res["status"], "success")
        executed = mock_search.call_args.kwargs["query"]
        for token in "HFpEF SGLT2 inhibitors".split():
            self.assertIn(token, executed)
        self.assertIn("heart failure with preserved ejection fraction", executed)
        self.assertNotIn(" AND ", f" {executed} ")
        self.assertEqual(res["query"], "HFpEF SGLT2 inhibitors")
        self.assertEqual(res["query_enhancement"]["specialty"]["id"], "kardiyoloji")
        self.assertFalse(res["query_enhancement"]["fallback_to_original"])
        self.assertEqual(mock_search.call_count, 1)

    @patch("universal_evidence_engine.pubmed_client.search_pubmed")
    def test_search_and_verify_can_disable_specialty_enhancement(self, mock_search):
        mock_search.return_value = {
            "articles": CARDIOLOGY_ARTICLES,
            "total_count": 1,
            "search_date": "2026-10-30",
        }
        res = self.engine.search_and_verify(
            "HFpEF SGLT2 inhibitors",
            enhance_with_specialty=False,
        )
        self.assertEqual(mock_search.call_args.kwargs["query"], "HFpEF SGLT2 inhibitors")
        self.assertEqual(res["query_enhancement"]["strategy"], "disabled")
        self.assertFalse(res["query_enhancement"]["applied"])
        self.assertEqual(res["query_enhancement"]["specialty"]["id"], "kardiyoloji")

    @patch("universal_evidence_engine.pubmed_client.search_pubmed")
    def test_search_and_verify_falls_back_when_enhanced_query_is_empty(self, mock_search):
        mock_search.side_effect = [
            {"articles": [], "total_count": 0, "search_date": "2026-10-30"},
            {
                "articles": CARDIOLOGY_ARTICLES,
                "total_count": 1,
                "search_date": "2026-10-30",
            },
        ]
        res = self.engine.search_and_verify("HFpEF SGLT2", max_results=2)
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["articles"]), 1)
        self.assertEqual(mock_search.call_count, 2)
        self.assertEqual(mock_search.call_args_list[1].kwargs["query"], "HFpEF SGLT2")
        self.assertIn("HFpEF", mock_search.call_args_list[0].kwargs["query"])
        self.assertTrue(res["query_enhancement"]["fallback_to_original"])
        self.assertEqual(res["executed_query"], "HFpEF SGLT2")

    # --- 8. Safe Fallback and Error Handling Tests ---
    @patch("universal_evidence_engine.pubmed_client.search_pubmed")
    def test_search_and_verify_api_failure_handling(self, mock_search):
        mock_search.side_effect = Exception("NCBI E-utilities connection timeout")

        res = run_universal_evidence_search("heart failure")
        self.assertEqual(res["status"], "error")
        self.assertIn("NCBI E-utilities connection timeout", res["error"])
        self.assertEqual(res["articles"], [])

    def test_empty_query_synthesis_handling(self):
        res = self.engine.generate_synthesis_report("", CARDIOLOGY_ARTICLES)
        self.assertEqual(res["status"], "error")
        self.assertIn("boş olamaz", res["error"])

    def test_synthesis_with_no_articles(self):
        synth = self.engine.generate_synthesis_report("Rare medical condition", [])
        self.assertEqual(synth["status"], "success")
        self.assertIn("Sonuç Bulunamadı", synth["report_markdown"])


if __name__ == "__main__":
    unittest.main()
