import unittest
from unittest.mock import patch
from report_generator import (
    generate_rule_based_turkish_report,
    generate_turkish_evidence_report,
    _classify_evidence_level,
    classify_study_design,
    assess_risk_of_bias,
    extract_pico,
    extract_study_metrics,
    generate_evidence_table_markdown,
    generate_evidence_table_html,
    perform_red_team_audit,
    generate_html_report
)

SAMPLE_ARTICLES = [
    {
        "pmid": "34449189",
        "doi": "10.1056/NEJMoa2107038",
        "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
        "authors": ["Stefan D Anker", "Javed Butler"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2021",
        "publication_types": ["Randomized Controlled Trial", "Journal Article"],
        "abstract": "SGLT2 inhibitors reduce the risk of hospitalization in heart failure patients.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/34449189/",
        "doi_url": "https://doi.org/10.1056/NEJMoa2107038"
    },
    {
        "pmid": "31535829",
        "doi": "10.1056/NEJMoa1911303",
        "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
        "authors": ["John J V McMurray", "Solomon D Solomon"],
        "journal": "The New England Journal of Medicine",
        "pub_year": "2019",
        "publication_types": ["Clinical Trial"],
        "abstract": "Dapagliflozin lowered risk of cardiovascular events in HFrEF.",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/31535829/",
        "doi_url": "https://doi.org/10.1056/NEJMoa1911303"
    }
]


class TestReportGenerator(unittest.TestCase):

    def test_classify_study_design(self):
        rct = classify_study_design(["Randomized Controlled Trial"], "Title", "Abstract")
        self.assertEqual(rct["level"], "Seviye 2")
        self.assertIn("Rastgele Kontrollü", rct["design"])

        meta = classify_study_design(["Systematic Review"], "Meta-analysis title", "Abstract")
        self.assertEqual(meta["level"], "Seviye 1")
        self.assertIn("Sistematik Derleme", meta["design"])

        cohort = classify_study_design([], "Prospective Cohort Study", "A cohort of patients")
        self.assertEqual(cohort["level"], "Seviye 3")

    def test_classify_study_design_nlm_preliminary_priority(self):
        # NLM publication type Cohort Studies should take priority over background mention of "Systematic Review"
        res = classify_study_design(
            ["Cohort Studies"],
            "Observational study on hypertension",
            "A systematic review was previously conducted on this topic. In our cohort of 500 patients..."
        )
        self.assertEqual(res["level"], "Seviye 3")
        self.assertEqual(res["design"], "Kohort Çalışması (Gözlemsel)")

    def test_assess_risk_of_bias_not_assessed(self):
        art = SAMPLE_ARTICLES[0]
        rob = assess_risk_of_bias(art)
        self.assertEqual(rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertIn("tam metin (full-text) incelemesi gereklidir", rob["note"])
        for domain_val in rob["domains"].values():
            self.assertIn("Değerlendirilmedi", domain_val)

    def test_assess_risk_of_bias_tool_assignment_by_article_type(self):
        # 1. Systematic Review / Meta-Analysis -> AMSTAR 2 / ROBIS
        meta_art = {
            "title": "Empagliflozin in Heart Failure: A Systematic Review and Meta-Analysis",
            "publication_types": ["Meta-Analysis", "Systematic Review"],
            "abstract": "We performed a systematic review and meta-analysis of RCTs."
        }
        rob_meta = assess_risk_of_bias(meta_art)
        self.assertEqual(rob_meta["overall_rating"], "Uygulanamaz (Not Applicable)")
        self.assertEqual(rob_meta["tool"], "AMSTAR 2 / ROBIS (Sistematik Derleme)")

        # 2. Narrative Review -> Uygulanamaz
        review_art = {
            "title": "Recent advances in heart failure therapy",
            "publication_types": ["Review"],
            "abstract": "In this review we summarize recent developments."
        }
        rob_rev = assess_risk_of_bias(review_art)
        self.assertEqual(rob_rev["overall_rating"], "Uygulanamaz (Not Applicable)")
        self.assertEqual(rob_rev["tool"], "Uygulanamaz (Not Applicable)")

        # 3. Case Report -> Uygulanamaz
        case_art = {
            "title": "SGLT2 inhibitor induced ketoacidosis: a case report",
            "publication_types": ["Case Reports"],
            "abstract": "We present a case of euglycemic ketoacidosis."
        }
        rob_case = assess_risk_of_bias(case_art)
        self.assertEqual(rob_case["overall_rating"], "Uygulanamaz (Not Applicable)")
        self.assertEqual(rob_case["tool"], "Uygulanamaz (Not Applicable)")

        # 4. RCT -> RoB 2
        rct_art = {
            "title": "Randomized trial of empagliflozin",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "Patients were randomly assigned..."
        }
        rob_rct = assess_risk_of_bias(rct_art)
        self.assertEqual(rob_rct["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(rob_rct["tool"], "RoB 2 (Cochrane Risk of Bias for RCTs)")

        # 5. Cohort Study -> ROBINS-I
        cohort_art = {
            "title": "A prospective cohort study of SGLT2 inhibitors",
            "publication_types": ["Observational Study"],
            "abstract": "We followed a prospective cohort..."
        }
        rob_cohort = assess_risk_of_bias(cohort_art)
        self.assertEqual(rob_cohort["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(rob_cohort["tool"], "ROBINS-I (Risk of Bias in Non-Randomized Studies)")

    def test_extract_study_metrics_concomitant_and_causality(self):
        abstract = "A total of 150 patients were treated with corticosteroids and immunosuppressive drugs. HR 0.45, 95% CI 0.30-0.65, p < 0.001. However, causality cannot be determined due to the observational nature of the cohort."
        metrics = extract_study_metrics(abstract)
        self.assertEqual(metrics["n"], "150")
        self.assertIn("HR 0.45", metrics["effect_sizes"])
        self.assertIn("Corticosteroids", metrics["concomitant_treatments"])
        self.assertIn("Immunosuppressive", metrics["concomitant_treatments"])
        self.assertTrue(any("causality" in lim.lower() for lim in metrics["causality_limitations"]))

    def test_extract_pico_multi_part_query(self):
        query = "SGLT2 inhibitors vs placebo in heart failure with preserved ejection fraction"

        pico = extract_pico(query)
        self.assertEqual(pico["intervention"], "SGLT2 inhibitors")
        self.assertEqual(pico["comparison"], "Placebo")
        self.assertEqual(pico["population"], "Heart failure with preserved ejection fraction")
        self.assertEqual(pico["outcome"], "Belirtilmemiş")

    def test_extract_pico_unstated_defaults_to_belirtilmemis(self):
        pico = extract_pico("")
        self.assertEqual(pico["population"], "Belirtilmemiş")
        self.assertEqual(pico["intervention"], "Belirtilmemiş")
        self.assertEqual(pico["comparison"], "Belirtilmemiş")
        self.assertEqual(pico["outcome"], "Belirtilmemiş")

    def test_classify_evidence_level(self):
        level_rct = _classify_evidence_level(["Randomized Controlled Trial"], "Title", "Abstract")
        self.assertIn("Seviye 2", level_rct)

    def test_evidence_table_markdown_generation(self):
        table_md = generate_evidence_table_markdown(SAMPLE_ARTICLES)
        self.assertIn("| # | Çalışma / Yazar (Yıl) |", table_md)
        self.assertIn("Stefan D Anker", table_md)
        self.assertIn("PMID: 34449189", table_md)

    def test_evidence_table_html_generation(self):
        table_html = generate_evidence_table_html(SAMPLE_ARTICLES)
        self.assertIn("<table", table_html)
        self.assertIn("Empagliflozin in Heart Failure", table_html)
        self.assertIn("PMID: 34449189", table_html)

    @patch("report_generator.verify_citation")
    def test_perform_red_team_audit(self, mock_verify_citation) -> None:
        mock_verify_citation.side_effect = [
            {"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"},
            {"status": "verified", "verified": True, "pmid": "31535829", "reason": "match"}
        ]
        audit = perform_red_team_audit("Heart Failure SGLT2", SAMPLE_ARTICLES)
        self.assertIn("DENETLEME TAMAMLANDI", audit["status"])
        self.assertEqual(audit["citation_integrity"]["verified_citations"], 2)
        self.assertEqual(audit["citation_integrity"]["rejected_citations"], 0)
        self.assertEqual(audit["citation_integrity"]["mismatch_or_invalid_citations_detected"], 0)
        self.assertTrue(audit["grade_rating_policy"]["compliant"])
        self.assertEqual(audit["grade_rating_policy"]["grade_status"], "GRADE Değerlendirilmedi (Not Assessed)")
        self.assertIn("NCBI PubMed E-utilities API", audit["metadata_retrieval_source"])
        self.assertIn("Klinik Doğrulama Yapılmamıştır", audit["clinical_validation_status"])

        # Ensure no false claims in audit dictionary keys or string representations
        audit_str = str(audit)
        self.assertNotIn("100/100", audit_str)
        self.assertNotIn("100 / 100", audit_str)
        self.assertNotIn("0% (Sıfır)", audit_str)

    @patch("report_generator.verify_citation")
    def test_perform_red_team_audit_six_citation_reasons(self, mock_verify_citation):
        six_articles = [
            {"pmid": "10001", "title": "Paper 1"},
            {"pmid": "10002", "title": "Paper 2"},
            {"pmid": "10003", "title": "Paper 3"},
            {"pmid": "abc", "title": "Paper 4"},
            {"pmid": "99999", "title": "Paper 5"},
            {"pmid": "10006", "title": "Paper 6"},
        ]
        mock_verify_citation.side_effect = [
            {"status": "verified", "verified": True, "pmid": "10001", "reason": "match"},
            {"status": "rejected", "verified": False, "pmid": "10002", "reason": "title_mismatch"},
            {"status": "rejected", "verified": False, "pmid": "10003", "reason": "doi_mismatch"},
            {"status": "rejected", "verified": False, "pmid": "abc", "reason": "missing_or_invalid_pmid"},
            {"status": "rejected", "verified": False, "pmid": "99999", "reason": "not_found"},
            {"status": "unverified", "verified": False, "pmid": "10006", "reason": "api_failure"}
        ]

        audit = perform_red_team_audit("Test Query", six_articles)
        self.assertEqual(audit["citation_integrity"]["verified_citations"], 1)
        self.assertEqual(audit["citation_integrity"]["rejected_citations"], 4)
        self.assertEqual(audit["citation_integrity"]["unverified_citations"], 1)

        breakdown = audit["citation_integrity"]["reason_breakdown"]
        self.assertEqual(breakdown["match"], 1)
        self.assertEqual(breakdown["title_mismatch"], 1)
        self.assertEqual(breakdown["doi_mismatch"], 1)
        self.assertEqual(breakdown["missing_or_invalid_pmid"], 1)
        self.assertEqual(breakdown["not_found"], 1)
        self.assertEqual(breakdown["api_failure"], 1)

    def test_generate_rule_based_turkish_report(self):
        query = "SGLT2 inhibitors in heart failure"
        report = generate_rule_based_turkish_report(query, SAMPLE_ARTICLES)

        # Check all 13 required sections
        self.assertIn("Türkçe Klinik Araştırma Raporu", report)
        self.assertIn("1. Klinik Araştırma Sorusu", report)
        self.assertIn("2. Yönetici Özeti", report)
        self.assertIn("3. Araştırma Yöntemi ve Tarama Tarihi", report)
        self.assertIn("4. Klinik Arka Plan ve Patofizyoloji", report)
        self.assertIn("5. Bilimsel Kanıt Tablosu", report)
        self.assertIn("6. Önemli Çalışmaların Karşılaştırılması", report)
        self.assertIn("7. Tedavi Etkinliği ve Güvenlilik", report)
        self.assertIn("8. Güncel Klinik Kılavuzlar", report)
        self.assertIn("9. Çelişkili Bilimsel Bulgular", report)
        self.assertIn("10. Red Team Eleştirisi", report)
        self.assertIn("11. Kanıt Gücü ve Belirsizlikler", report)
        self.assertIn("12. Klinik Sonuç", report)
        self.assertIn("13. Doğrulanmış Kaynakça", report)

        # Check for mandatory disclaimers and limitations
        self.assertIn("yayınlanmış özet (abstract) metinlerine dayanmaktadır", report)
        self.assertIn("GRADE Değerlendirilmedi (Not Assessed)", report)
        self.assertIn("Klinik Doğrulama Yapılmamıştır (No Clinical Validation Claimed)", report)

        # Ensure real PMIDs are present
        self.assertIn("PMID: [34449189]", report)
        self.assertIn("PMID: [31535829]", report)
        self.assertIn("Empagliflozin in Heart Failure", report)

        # Check absence of false claims
        self.assertNotIn("100/100", report)
        self.assertNotIn("100 / 100", report)
        self.assertNotIn("0% (Sıfır)", report)
        self.assertNotIn("SIFIR HALÜSİNASYON", report)

    def test_generate_report_empty_articles(self):
        query = "Unknown condition xyz"
        report = generate_rule_based_turkish_report(query, [])
        self.assertIn("Sonuç Bulunamadı", report)

    def test_generate_turkish_evidence_report_fallback(self):
        report = generate_turkish_evidence_report("SGLT2 inhibitors", SAMPLE_ARTICLES, api_key=None, use_llm=False)
        self.assertIn("Türkçe Klinik Araştırma Raporu", report)
        self.assertIn("34449189", report)

    def test_generate_html_report(self):
        markdown_rep = generate_rule_based_turkish_report("SGLT2 inhibitors", SAMPLE_ARTICLES)
        html_rep = generate_html_report("SGLT2 inhibitors", SAMPLE_ARTICLES, markdown_rep)
        self.assertIn("<!DOCTYPE html>", html_rep)
        self.assertIn("Türkçe Klinik Kanıt Raporu", html_rep)
        self.assertIn("GRADE Statüsü:", html_rep)
        self.assertIn("GRADE Değerlendirilmedi", html_rep)
        self.assertIn("Abstract-Only Limitation", html_rep)
        self.assertIn("No Clinical Validation claimed", html_rep)

        self.assertNotIn("100/100", html_rep)
        self.assertNotIn("100 / 100", html_rep)
        self.assertNotIn("0% (Sıfır)", html_rep)
        self.assertNotIn("SIFIR HALÜSİNASYON", html_rep)

    def test_regression_extract_pico_single_arg(self):
        pico = extract_pico("Statin-associated muscle symptoms AND anti-HMGCR")
        self.assertEqual(pico["population"], "Belirtilmemiş")
        self.assertEqual(pico["intervention"], "Belirtilmemiş")
        self.assertEqual(pico["comparison"], "Belirtilmemiş")

    def test_regression_section_12_no_generic_template_and_has_pmid_citations(self):
        query = "SGLT2 inhibitors in heart failure"
        report = generate_rule_based_turkish_report(query, SAMPLE_ARTICLES)

        # Ensure Section 12 header is present
        self.assertIn("## 12. Klinik Sonuç", report)

        # Isolate section 12 content
        section_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # Verify NO generic template fallback text
        self.assertNotIn("özet seviyesindeki bulgular sentezlenmiştir. Bu kanıt raporu, sorumlu hekimin hasta yönetimindeki klinik kararlarını desteklemek amacıyla hazırlanmıştır.", section_12)

        # Verify real article findings and explicit PMID citations
        self.assertIn("[PMID: 34449189]", section_12)
        self.assertIn("[PMID: 31535829]", section_12)
        self.assertIn("empagliflozin", section_12.lower())

    def test_regression_evidence_table_no_visible_br_tags_and_responsive_html(self):
        # 1. Markdown evidence table should NOT contain raw <br> tags
        table_md = generate_evidence_table_markdown(SAMPLE_ARTICLES)
        self.assertNotIn("<br>", table_md)
        self.assertIn("PMID: 34449189", table_md)

        # 2. HTML evidence table should be responsive and properly escaped
        table_html = generate_evidence_table_html(SAMPLE_ARTICLES)
        self.assertIn("overflow-x: auto", table_html)
        self.assertIn("word-break: break-word", table_html)
        self.assertIn("Empagliflozin in Heart Failure", table_html)


if __name__ == "__main__":
    unittest.main()
