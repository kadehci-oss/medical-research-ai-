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
