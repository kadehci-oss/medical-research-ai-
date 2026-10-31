import unittest
from unittest.mock import patch
from report_generator import (
    generate_rule_based_turkish_report,
    generate_turkish_evidence_report,
    _classify_evidence_level,
    classify_study_design,
    assess_risk_of_bias,
    extract_pico,
    extract_pico_improved,
    extract_study_metrics,
    extract_outcome_metrics,
    generate_evidence_table_markdown,
    generate_evidence_table_html,
    perform_red_team_audit,
    generate_html_report,
    validate_clinical_report_quality,
    _synthesize_article_conclusion_tr
)

PHYSICIAN_REVIEW_LINE = "Uzman Hekim Değerlendirmesi: Yapılmadı"

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
        self.assertEqual(rct["level"], "Değerlendirilemedi")
        self.assertIsNone(rct["level_num"])
        self.assertIn("Rastgele Kontrollü", rct["design"])

        meta = classify_study_design(["Systematic Review"], "Meta-analysis title", "Abstract")
        self.assertEqual(meta["level"], "Değerlendirilemedi")
        self.assertIn("Sistematik Derleme", meta["design"])
        self.assertIn("Meta-Analiz", meta["design"])

        cohort = classify_study_design([], "Prospective Cohort Study", "A cohort of patients")
        self.assertEqual(cohort["level"], "Değerlendirilemedi")
        self.assertEqual(cohort["design"], "Kohort Çalışması (Gözlemsel)")

    def test_classify_study_design_nlm_preliminary_priority(self):
        # NLM publication type Cohort Studies should take priority over background mention of "Systematic Review"
        res = classify_study_design(
            ["Cohort Studies"],
            "Observational study on hypertension",
            "A systematic review was previously conducted on this topic. In our cohort of 500 patients..."
        )
        self.assertEqual(res["level"], "Değerlendirilemedi")
        self.assertEqual(res["design"], "Kohort Çalışması (Gözlemsel)")

    def test_assess_risk_of_bias_not_assessed(self):
        art = SAMPLE_ARTICLES[0]
        rob = assess_risk_of_bias(art)
        self.assertEqual(rob["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertIn("tam metin (full-text) incelemesi gereklidir", rob["note"])
        for domain_val in rob["domains"].values():
            self.assertIn("Değerlendirilmedi", domain_val)

    def test_assess_risk_of_bias_tool_assignment_by_article_type(self):
        # 1. Systematic Review / Meta-Analysis -> ROBIS, no risk degree
        meta_art = {
            "title": "Empagliflozin in Heart Failure: A Systematic Review and Meta-Analysis",
            "publication_types": ["Meta-Analysis", "Systematic Review"],
            "abstract": "We performed a systematic review and meta-analysis of RCTs."
        }
        rob_meta = assess_risk_of_bias(meta_art)
        self.assertEqual(rob_meta["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(rob_meta["tool"], "ROBIS (Risk of Bias in Systematic Reviews)")
        self.assertFalse(rob_meta["risk_assigned"])

        # 2. Narrative Review -> no RoB tool and no risk degree
        review_art = {
            "title": "Recent advances in heart failure therapy",
            "publication_types": ["Review"],
            "abstract": "In this review we summarize recent developments."
        }
        rob_rev = assess_risk_of_bias(review_art)
        self.assertEqual(rob_rev["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(rob_rev["tool"], "Uygulanamaz (Not Applicable)")
        self.assertFalse(rob_rev["risk_assigned"])

        # 3. Case Report -> JBI, still unrated
        case_art = {
            "title": "SGLT2 inhibitor induced ketoacidosis: a case report",
            "publication_types": ["Case Reports"],
            "abstract": "We present a case of euglycemic ketoacidosis."
        }
        rob_case = assess_risk_of_bias(case_art)
        self.assertEqual(rob_case["overall_rating"], "Değerlendirilmedi (Not Assessed)")
        self.assertEqual(rob_case["tool"], "JBI Olgu Sunumu Değerlendirme Listesi")
        self.assertFalse(rob_case["risk_assigned"])

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
        self.assertIn("Değerlendirilemedi", level_rct)
        self.assertNotIn("Seviye", level_rct)

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

    def test_evidence_table_html_blocks_unsafe_url_schemes(self):
        article = dict(SAMPLE_ARTICLES[0])
        article["pubmed_url"] = "javascript:alert(1)"
        article["doi_url"] = "data:text/html,<script>alert(2)</script>"

        table_html = generate_evidence_table_html([article])

        self.assertNotIn('href="javascript:', table_html)
        self.assertNotIn('href="data:', table_html)
        self.assertIn('href="#"', table_html)
        self.assertIn('rel="noopener noreferrer"', table_html)

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

    def test_llm_is_not_called_without_explicit_data_transfer_consent(self):
        with patch(
            "report_generator.verify_citation",
            return_value={"status": "verified", "verified": True, "reason": "match"},
        ), patch("report_generator.OpenAI") as mock_openai:
            report = generate_turkish_evidence_report(
                "SGLT2 inhibitors", SAMPLE_ARTICLES, api_key="test-key", use_llm=True
            )

        mock_openai.assert_not_called()
        self.assertIn("açık onay verilmedi", report)
        self.assertIn("Türkçe Klinik Araştırma Raporu", report)

    def test_llm_exception_uses_safe_fallback_without_exposing_error(self):
        with patch(
            "report_generator.verify_citation",
            return_value={"status": "verified", "verified": True, "reason": "match"},
        ), patch("report_generator.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.side_effect = Exception(
                "Authorization failed for api_key=sk-test-secret"
            )
            report = generate_turkish_evidence_report(
                "SGLT2 inhibitors",
                SAMPLE_ARTICLES,
                api_key="sk-test-secret",
                use_llm=True,
                allow_external_data_transfer=True,
            )

        self.assertIn("OpenAI sentezi üretilemedi", report)
        self.assertNotIn("sk-test-secret", report)
        self.assertNotIn("Authorization failed", report)
        self.assertIn("aktarılıp aktarılmadığı", report)

    def test_openai_client_initialization_error_uses_safe_fallback(self):
        with patch(
            "report_generator.verify_citation",
            return_value={"status": "verified", "verified": True, "reason": "match"},
        ), patch("report_generator.OpenAI", side_effect=Exception("api_key=test-secret")):
            report = generate_turkish_evidence_report(
                "SGLT2 inhibitors",
                SAMPLE_ARTICLES,
                api_key="test-secret",
                use_llm=True,
                allow_external_data_transfer=True,
            )

        self.assertIn("OpenAI sentezi üretilemedi", report)
        self.assertNotIn("test-secret", report)
        self.assertNotIn("api_key", report)

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

    def test_generate_html_report_escapes_untrusted_content_and_blocks_unsafe_links(self):
        audit = {
            "status": "DENETLEME TAMAMLANDI",
            "grade_rating_policy": {"grade_status": "GRADE Değerlendirilmedi"},
        }
        malicious_query = 'test\"><script>alert("query")</script>'
        markdown = (
            '<script>alert("body")</script>\n\n'
            '[bad](javascript:alert(1))\n\n'
            '[good](https://example.org/path?a=1&b=2)'
        )

        html_rep = generate_html_report(malicious_query, [], markdown, audit=audit)

        self.assertNotIn("<script>", html_rep)
        self.assertIn("&lt;script&gt;", html_rep)
        self.assertNotIn('href="javascript:', html_rep)
        self.assertIn('href="https://example.org/path?a=1&amp;b=2"', html_rep)
        self.assertIn('rel="noopener noreferrer"', html_rep)

    def test_regression_extract_pico_single_arg(self):
        pico = extract_pico("Statin-associated muscle symptoms AND anti-HMGCR")
        self.assertEqual(pico["population"], "Belirtilmemiş")
        self.assertEqual(pico["intervention"], "Belirtilmemiş")
        self.assertEqual(pico["comparison"], "Belirtilmemiş")

    def test_extract_pico_improved_is_public_alias(self):
        query = "Empagliflozin compared with placebo for cardiovascular mortality in patients with HFrEF"
        self.assertEqual(extract_pico(query), extract_pico_improved(query))

    def test_extract_pico_english_comparison_population_and_outcome(self):
        glp = extract_pico("GLP-1 agonists versus insulin on HbA1c in adults with type 2 diabetes")
        self.assertEqual(glp["intervention"], "GLP-1 agonists")
        self.assertEqual(glp["comparison"], "Insulin")
        self.assertEqual(glp["population"], "Adults with type 2 diabetes")
        self.assertEqual(glp["outcome"], "HbA1c")

        mortality = extract_pico(
            "Empagliflozin compared with placebo for cardiovascular mortality in patients with HFrEF"
        )
        self.assertEqual(mortality["intervention"], "Empagliflozin")
        self.assertEqual(mortality["comparison"], "Placebo")
        self.assertEqual(mortality["population"], "Patients with HFrEF")
        self.assertEqual(mortality["outcome"], "Cardiovascular mortality")

        kidney = extract_pico(
            "dapagliflozin versus placebo among adults with chronic kidney disease on kidney failure"
        )
        self.assertEqual(kidney["intervention"], "Dapagliflozin")
        self.assertEqual(kidney["comparison"], "Placebo")
        self.assertEqual(kidney["population"], "Adults with chronic kidney disease")
        self.assertEqual(kidney["outcome"], "Kidney failure")

        head_to_head = extract_pico("Empagliflozin in comparison with placebo in patients with HFpEF")
        self.assertEqual(head_to_head["intervention"], "Empagliflozin")
        self.assertEqual(head_to_head["comparison"], "Placebo")
        self.assertEqual(head_to_head["population"], "Patients with HFpEF")
        self.assertEqual(head_to_head["outcome"], "Belirtilmemiş")

    def test_extract_pico_turkish_comparison_population_and_outcome(self):
        diabetes = extract_pico(
            "Tip 2 diyabet hastalarında GLP-1 agonistlerinin insülin ile karşılaştırıldığında HbA1c üzerine etkisi"
        )
        self.assertEqual(diabetes["population"], "Tip 2 diyabet hastalarında")
        self.assertEqual(diabetes["intervention"], "GLP-1 agonistleri")
        self.assertEqual(diabetes["comparison"], "İnsülin")
        self.assertEqual(diabetes["outcome"], "HbA1c")

        hf = extract_pico(
            "SGLT2 inhibitörleri plaseboya karşı kalp yetersizliği hastalarında mortalite"
        )
        self.assertEqual(hf["intervention"], "SGLT2 inhibitörleri")
        self.assertEqual(hf["comparison"], "Plasebo")
        self.assertEqual(hf["population"], "Kalp yetersizliği hastalarında")
        self.assertEqual(hf["outcome"], "Mortalite")

        plain = extract_pico(
            "SGLT2 inhibitörleri plasebo ile karşılaştırıldığında kalp yetersizliği hastalarında mortalite"
        )
        self.assertEqual(plain["intervention"], "SGLT2 inhibitörleri")
        self.assertEqual(plain["comparison"], "Plasebo")
        self.assertEqual(plain["population"], "Kalp yetersizliği hastalarında")
        self.assertEqual(plain["outcome"], "Mortalite")

        children = extract_pico("çocuklarda febril nöbet")
        self.assertEqual(children["population"], "Çocuklarda")
        self.assertEqual(children["intervention"], "Febril nöbet")
        self.assertEqual(children["comparison"], "Belirtilmemiş")
        self.assertEqual(children["outcome"], "Belirtilmemiş")

    def test_extract_pico_short_clinical_questions_keep_outcome_unstated(self):
        crispr = extract_pico("CRISPR in sickle cell disease")
        self.assertEqual(crispr["intervention"], "CRISPR")
        self.assertEqual(crispr["population"], "Sickle cell disease")
        self.assertEqual(crispr["comparison"], "Belirtilmemiş")
        self.assertEqual(crispr["outcome"], "Belirtilmemiş")

        seizure = extract_pico("Febrile seizure in children")
        self.assertEqual(seizure["intervention"], "Febrile seizure")
        self.assertEqual(seizure["population"], "Children")
        self.assertEqual(seizure["outcome"], "Belirtilmemiş")

        depression = extract_pico("Psilocybin for major depressive disorder")
        self.assertEqual(depression["intervention"], "Psilocybin")
        self.assertEqual(depression["population"], "Major depressive disorder")
        self.assertEqual(depression["comparison"], "Belirtilmemiş")
        self.assertEqual(depression["outcome"], "Belirtilmemiş")

    def test_synthesize_article_conclusion_tr_diverse_medical_conditions(self):
        # 1. Oncology with explicit quantitative metrics
        onco_article = {
            "pmid": "12345678",
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "authors": ["John Smith", "Jane Doe"],
            "pub_year": "2023",
            "title": "Pembrolizumab in Non-Small Cell Lung Cancer",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In this trial with 450 patients (n=450), Pembrolizumab reduced recurrence (HR 0.62, p=0.002) and improved overall survival."
        }
        res_onco = _synthesize_article_conclusion_tr(onco_article, "lung cancer immunotherapy")
        self.assertIn("[PMID: 12345678]", res_onco)
        self.assertIn("John Smith ve Jane Doe (2023)", res_onco)
        self.assertIn("n = 450", res_onco)
        self.assertIn("HR 0.62", res_onco)

        # 2. Non-significant trial
        rheum_article = {
            "pmid": "45678901",
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/45678901/",
            "authors": ["Hana Tanaka"],
            "pub_year": "2020",
            "title": "JAK Inhibitors vs TNF Inhibitors in Rheumatoid Arthritis",
            "publication_types": ["Systematic Review"],
            "abstract": "No statistically significant difference was observed between JAK inhibitors and TNF inhibitors regarding overall remission rates."
        }
        res_rheum = _synthesize_article_conclusion_tr(rheum_article, "Rheumatoid Arthritis")
        self.assertIn("[PMID: 45678901]", res_rheum)
        self.assertIn("istatistiksel olarak anlamlı bir fark saptanmamıştır", res_rheum)

    def test_synthesize_article_conclusion_tr_insufficient_data(self):
        # 1. Missing / Empty abstract
        empty_art = {
            "pmid": "99990000",
            "authors": ["Test Author"],
            "pub_year": "2023",
            "title": "Incomplete Record",
            "abstract": "Özet bulunamadı."
        }
        res_empty = _synthesize_article_conclusion_tr(empty_art, "Test Query")
        self.assertIn("[PMID: 99990000]", res_empty)
        self.assertIn("Makale özetinde klinik kanıt veya sonuç verisi yetersizdir / bildirilmemiştir.", res_empty)

        # 2. Abstract without quantitative metrics reports limitations rather than fabricating claims
        vague_art = {
            "pmid": "99990001",
            "authors": ["Test Author"],
            "pub_year": "2023",
            "title": "Study Protocol for Rare Condition",
            "abstract": "This article describes the preliminary background design for an ongoing trial."
        }
        res_vague = _synthesize_article_conclusion_tr(vague_art, "Rare Condition")
        self.assertIn("[PMID: 99990001]", res_vague)
        self.assertIn("doğrulanabilir nicel klinik sonuç veya istatistiksel parametre verisi yetersizdir", res_vague)

    def test_regression_statin_myopathy_heart_failure_infection_outcomes(self):
        """
        Regression tests for Statin Myopathy, Heart Failure, and Infectious Diseases across:
        1) Positive (quantitative) results
        2) Negative results
        3) Nonsignificant results
        4) Conflicting/heterogeneous results
        Verifies no ungrounded claims are produced from single trigger words ("effective", "safe", etc.).
        """
        # --- 1. Statin Myopathy ---
        # Positive quantitative
        statin_pos = {
            "pmid": "50001",
            "title": "Statin Myopathy Trial",
            "authors": ["A. Smith"],
            "pub_year": "2022",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In a study of n=200 patients with statin myopathy, anti-HMGCR titers correlated with CK levels (OR 2.50, 95% CI 1.40-4.20, p=0.001)."
        }
        res_statin_pos = _synthesize_article_conclusion_tr(statin_pos, "Statin myopathy in adults")
        self.assertIn("[PMID: 50001]", res_statin_pos)
        self.assertIn("n = 200", res_statin_pos)
        self.assertIn("OR 2.50", res_statin_pos)
        self.assertIn("Popülasyon (P): **Adults**", res_statin_pos)

        # Nonsignificant
        statin_nonsig = {
            "pmid": "50002",
            "title": "Statin Myopathy Supplement Trial",
            "authors": ["B. Jones"],
            "pub_year": "2021",
            "publication_types": ["Clinical Trial"],
            "abstract": "Coenzyme Q10 failed to show statistically significant reduction in statin-associated muscle symptoms compared to placebo (p=0.45)."
        }
        res_statin_nonsig = _synthesize_article_conclusion_tr(statin_nonsig, "CoQ10 in statin myopathy")
        self.assertIn("[PMID: 50002]", res_statin_nonsig)
        self.assertIn("istatistiksel olarak anlamlı bir fark saptanmamıştır", res_statin_nonsig)

        # Conflicting
        statin_conflict = {
            "pmid": "50003",
            "title": "Vitamin D in Statin Intolerance",
            "authors": ["C. Lee"],
            "pub_year": "2023",
            "publication_types": ["Observational Study"],
            "abstract": "Literature shows conflicting and inconsistent results regarding vitamin D supplementation for statin myopathy."
        }
        res_statin_conflict = _synthesize_article_conclusion_tr(statin_conflict, "Vitamin D statin myopathy")
        self.assertIn("[PMID: 50003]", res_statin_conflict)
        self.assertIn("çelişkili veya heterojen sonuçlar bildirilmiştir", res_statin_conflict)

        # Single trigger word ("effective", "safe") without metrics -> MUST report evidence limitation, NOT auto-claim efficacy!
        statin_trigger = {
            "pmid": "50004",
            "title": "Statin Myopathy Narrative Review",
            "authors": ["D. Miller"],
            "pub_year": "2020",
            "publication_types": ["Journal Article"],
            "abstract": "Statins are generally effective and safe in reducing cardiovascular events, but myopathy remains a concern."
        }
        res_statin_trigger = _synthesize_article_conclusion_tr(statin_trigger, "Statin myopathy")
        self.assertNotIn("tedavinin klinik etkinlik sunduğu", res_statin_trigger)
        self.assertNotIn("güvenilirlik profilinin kabul edilebilir olduğu", res_statin_trigger)
        self.assertIn("nicel istatistiksel parametre bildirilmemiştir", res_statin_trigger)

        # --- 2. Heart Failure ---
        hf_pos = {
            "pmid": "60001",
            "title": "SGLT2 Inhibitor in Heart Failure",
            "authors": ["E. Davis"],
            "pub_year": "2023",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In HFrEF patients (n=300), SGLT2 inhibition lowered CV death (HR 0.74, 95% CI 0.60-0.90, p=0.003)."
        }
        res_hf_pos = _synthesize_article_conclusion_tr(hf_pos, "SGLT2 in heart failure")
        self.assertIn("[PMID: 60001]", res_hf_pos)
        self.assertIn("HR 0.74", res_hf_pos)

        hf_nonsig = {
            "pmid": "60002",
            "title": "Novel Inotrope in Acute Heart Failure",
            "authors": ["F. Wilson"],
            "pub_year": "2022",
            "publication_types": ["Clinical Trial"],
            "abstract": "The novel inotrope did not reduce 30-day mortality in acute decompensated heart failure compared to placebo (p=0.82)."
        }
        res_hf_nonsig = _synthesize_article_conclusion_tr(hf_nonsig, "Inotropes in acute heart failure")
        self.assertIn("[PMID: 60002]", res_hf_nonsig)
        self.assertIn("istatistiksel olarak anlamlı bir fark saptanmamıştır", res_hf_nonsig)

        # --- 3. Infectious Diseases ---
        inf_pos = {
            "pmid": "70001",
            "title": "Antiviral Therapy in Severe Influenza",
            "authors": ["G. Taylor"],
            "pub_year": "2024",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "In hospitalized influenza patients (n=500), early antiviral therapy reduced ICU admission (OR 0.55, 95% CI 0.38-0.79, p=0.001)."
        }
        res_inf_pos = _synthesize_article_conclusion_tr(inf_pos, "Antiviral in severe influenza")
        self.assertIn("[PMID: 70001]", res_inf_pos)
        self.assertIn("OR 0.55", res_inf_pos)

        inf_nonsig = {
            "pmid": "70002",
            "title": "Adjunctive Steroids in Bacterial Pneumonia",
            "authors": ["H. Anderson"],
            "pub_year": "2023",
            "publication_types": ["Randomized Controlled Trial"],
            "abstract": "Adjunctive corticosteroids showed no statistically significant difference in 28-day mortality in non-severe CAP (p=0.34)."
        }
        res_inf_nonsig = _synthesize_article_conclusion_tr(inf_nonsig, "Steroids in bacterial pneumonia")
        self.assertIn("[PMID: 70002]", res_inf_nonsig)
        self.assertIn("istatistiksel olarak anlamlı bir fark saptanmamıştır", res_inf_nonsig)

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

    def test_section_12_comparative_evaluation_and_review_exclusion(self):
        """
        Verifies that Section 12 produces a source-based, Turkish comparative evaluation,
        does not claim definitive treatment efficacy from reviews, and displays patient count (n),
        effect metrics, and uncertainties with PMID sources.
        """
        test_articles = [
            {
                "pmid": "80001",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/80001/",
                "authors": ["Alice Brown"],
                "pub_year": "2023",
                "title": "Randomized Trial of Drug X in Hypertension",
                "publication_types": ["Randomized Controlled Trial"],
                "abstract": "In a study with n=500 hypertensive patients, Drug X lowered blood pressure (HR 0.65, 95% CI 0.50-0.85, p=0.001)."
            },
            {
                "pmid": "80002",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/80002/",
                "authors": ["Bob Green"],
                "pub_year": "2022",
                "title": "Comprehensive Review of Hypertension Therapies",
                "publication_types": ["Review", "Journal Article"],
                "abstract": "This narrative review summarizes current antihypertensive drugs and mechanisms."
            }
        ]

        query = "Drug X in hypertension management"
        report = generate_rule_based_turkish_report(query, test_articles)

        # Isolate section 12
        self.assertIn("## 12. Klinik Sonuç", report)
        section_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # 1. Check comparative synthesis header and subsection
        self.assertIn("karşılaştırmalı değerlendirmesi", section_12.lower())
        self.assertIn("### 🎯 Ortak Klinik Bulgular ve Sentez", section_12)

        # 2. Check PMIDs present in Section 12
        self.assertIn("[PMID: 80001]", section_12)
        self.assertIn("[PMID: 80002]", section_12)

        # 3. Check review exclusion disclaimer: no definitive efficacy from review
        self.assertIn("kesin tedavi etkinliği çıkarılmamıştır", section_12)

        # 4. Check display of patient count (n), effect metrics, and uncertainties
        self.assertIn("n = 500", section_12)
        self.assertIn("HR 0.65", section_12)
        self.assertIn("Sonlanım Ölçütleri:", section_12)

    def test_case_control_publication_type_without_title_or_abstract_cues(self):
        design = classify_study_design(
            ["Journal Article", "Case-Control Studies"],
            "Statin exposure and autoimmune myopathy",
            "Exposure histories were compared between groups.",
        )
        self.assertEqual(design["design"], "Vaka-Kontrol Çalışması")
        self.assertEqual(design["level"], "Değerlendirilemedi")
        self.assertIsNone(design["level_num"])

        singular = classify_study_design(
            ["Case-Control Study"],
            "Exposure study",
            "Groups were compared.",
        )
        self.assertEqual(singular["design"], "Vaka-Kontrol Çalışması")

    def test_case_control_publication_type_outranks_generic_observational_tag(self):
        design = classify_study_design(
            ["Observational Study", "Case-Control Studies", "Journal Article"],
            "Statin exposure and myopathy",
            "We compared exposure histories.",
        )
        self.assertEqual(design["design"], "Vaka-Kontrol Çalışması")

        cohort = classify_study_design(
            ["Observational Study", "Journal Article"],
            "A registry analysis",
            "Participants were followed over time.",
        )
        self.assertEqual(cohort["design"], "Kohort Çalışması (Gözlemsel)")

    def test_case_control_does_not_override_rct_publication_type(self):
        design = classify_study_design(
            ["Randomized Controlled Trial", "Case-Control Studies"],
            "Treatment comparison",
            "Participants were allocated to two groups.",
        )
        self.assertEqual(design["design"], "Rastgele Kontrollü Çalışma (RCT)")

    def test_extract_irr_and_smd_effect_measures(self):
        abstract = (
            "Depression symptoms improved after treatment "
            "(standardized mean difference -0.42; 95% CI -0.61 to -0.23; p < 0.001). "
            "Pain scores also changed (SMD -0.55). "
            "The infection rate was lower with prophylaxis "
            "(incidence rate ratio 0.74; 95% CI 0.61 to 0.90; p = 0.003). "
            "A second analysis reported IRR 1.20."
        )
        metrics = extract_study_metrics(abstract)
        self.assertCountEqual(
            metrics["effect_sizes"],
            [
                "standardized mean difference -0.42",
                "SMD -0.55",
                "incidence rate ratio 0.74",
                "IRR 1.20",
            ],
        )
        self.assertTrue(any("-0.61" in ci for ci in metrics["confidence_intervals"]))

        outcomes = extract_outcome_metrics(abstract)
        symptom_metrics = " ".join(
            " ".join(item["metrics"]) for item in outcomes if "depression" in item["outcome"].lower()
        )
        self.assertIn("standardized mean difference -0.42", symptom_metrics)
        infection_metrics = " ".join(
            " ".join(item["metrics"]) for item in outcomes if "infection" in item["outcome"].lower()
        )
        self.assertIn("incidence rate ratio 0.74", infection_metrics)

    def test_sample_size_regex_does_not_capture_bare_patient_counts(self):
        """Bare 'N patients' spans stay unmatched. PR #33's looser pattern is not used."""
        group_counts = (
            "Primary outcome occurred in 415 of 2997 patients in the empagliflozin group "
            "and 511 of 2991 patients in the placebo group."
        )
        self.assertIsNone(extract_study_metrics(group_counts)["n"])

        enrolled = (
            "In the registry, 450 patients with diabetes received metformin. "
            "A separate cohort of 120 patients were enrolled."
        )
        self.assertEqual(extract_study_metrics(enrolled)["n"], "120")

    @patch("report_generator.verify_citation")
    def test_expert_physician_review_line_in_report_html_and_audit(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        audit = perform_red_team_audit("SGLT2 inhibitors", SAMPLE_ARTICLES)
        self.assertEqual(audit["expert_physician_review"], "Yapılmadı")
        self.assertEqual(audit["physician_review_status"], "Yapılmadı")

        report = generate_rule_based_turkish_report("SGLT2 inhibitors", SAMPLE_ARTICLES)
        self.assertIn(PHYSICIAN_REVIEW_LINE, report)
        red_team = report.split("## 10. Red Team Eleştirisi")[1].split("## 11.")[0]
        self.assertIn(PHYSICIAN_REVIEW_LINE, red_team)

        html_rep = generate_html_report("SGLT2 inhibitors", SAMPLE_ARTICLES, report)
        self.assertIn(PHYSICIAN_REVIEW_LINE, html_rep)

        empty = generate_rule_based_turkish_report("Unknown condition xyz", [])
        self.assertIn(PHYSICIAN_REVIEW_LINE, empty)

    @patch("report_generator.verify_citation")
    def test_validate_clinical_report_quality_success(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", SAMPLE_ARTICLES)
        qc = validate_clinical_report_quality(report)
        self.assertTrue(qc["valid"], qc)
        self.assertEqual(qc["missing_sections"], [])
        self.assertEqual(qc["detected_false_claims"], [])
        self.assertEqual(qc["warnings"], [])

    @patch("report_generator.verify_citation")
    def test_validate_clinical_report_quality_missing_sections(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", SAMPLE_ARTICLES)
        truncated = report.split("## 13. Doğrulanmış Kaynakça")[0]
        qc = validate_clinical_report_quality(truncated)
        self.assertFalse(qc["valid"])
        self.assertIn("## 13. Doğrulanmış Kaynakça", qc["missing_sections"])

    @patch("report_generator.verify_citation")
    def test_validate_clinical_report_quality_false_claims(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", SAMPLE_ARTICLES)
        bad = report + "\n\nBu rapor 100/100 tam puan almış olup %0 halüsinasyon riski taşır ve uzman hekim değerlendirmesi tamamlanmıştır."
        qc = validate_clinical_report_quality(bad)
        self.assertFalse(qc["valid"])
        self.assertGreaterEqual(len(qc["detected_false_claims"]), 2)
        self.assertTrue(any("100/100" in claim for claim in qc["detected_false_claims"]))
        self.assertTrue(any("tamamland" in claim for claim in qc["detected_false_claims"]))

    @patch("report_generator.verify_citation")
    def test_validate_clinical_report_quality_warns_when_physician_line_removed(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        report = generate_rule_based_turkish_report("SGLT2 inhibitors", SAMPLE_ARTICLES)
        stripped = report.replace(PHYSICIAN_REVIEW_LINE, "Uzman inceleme notu yok")
        qc = validate_clinical_report_quality(stripped)
        self.assertTrue(qc["valid"])
        self.assertTrue(any(PHYSICIAN_REVIEW_LINE in warning for warning in qc["warnings"]))

    def test_validate_clinical_report_quality_rejects_empty_text(self):
        qc = validate_clinical_report_quality("")
        self.assertFalse(qc["valid"])
        self.assertEqual(len(qc["missing_sections"]), 13)
        self.assertIn("error", qc)


if __name__ == "__main__":
    unittest.main()
