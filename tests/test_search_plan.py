import unittest
from unittest.mock import MagicMock, patch

import requests

import search_plan
from report_generator import generate_rule_based_turkish_report, validate_clinical_report_quality

THERAPY_QUERY = "metformin versus placebo in adults with type 2 diabetes on HbA1c"


def _tr_lower(text):
    """Lowercase with Turkish dotted/dotless I rules (str.lower/casefold get them wrong)."""
    return text.replace("I", "ı").replace("İ", "i").lower()


# Wordings that would promise the reader a verification switch the report does not offer.
_SWITCH_PROMISES = ("doğrulamayı aç", "doğrulamasını aç", "doğrulamayı etkinleştir",
                    "doğrulamasını etkinleştir", "doğrulamayı başlat",
                    "verify_mesh", "mesh_lookup")

ARTICLES = [
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
        "doi_url": "https://doi.org/10.1056/NEJMoa2107038",
    }
]


class TestBuildSearchPlan(unittest.TestCase):

    def test_search_uses_population_and_intervention_only(self):
        plan = search_plan.build_search_plan(THERAPY_QUERY)
        self.assertEqual(plan["question_type"], "therapy")
        self.assertEqual(plan["suggested_query"], '("type 2 diabetes"[tiab]) AND (Metformin[tiab])')
        in_search = {c["key"]: c["in_search"] for c in plan["concepts"]}
        self.assertEqual(in_search, {"P": True, "I": True, "C": False, "O": False})
        self.assertNotIn("placebo", plan["suggested_query"].lower())
        self.assertNotIn("hba1c", plan["suggested_query"].lower())

    def test_terms_come_only_from_the_query(self):
        plan = search_plan.build_search_plan(THERAPY_QUERY)
        query_words = set(THERAPY_QUERY.lower().split())
        for concept in plan["concepts"]:
            for term in concept["terms"]:
                self.assertTrue(set(term.lower().split()) <= query_words, term)

    def test_mesh_is_not_guessed_without_a_lookup(self):
        plan = search_plan.build_search_plan(THERAPY_QUERY)
        self.assertEqual(plan["mesh_status"], "doğrulanmadı")
        self.assertNotIn("[MeSH Terms]", plan["suggested_query"])
        self.assertTrue(all(not c["mesh_headings"] for c in plan["concepts"]))

    def test_unverified_mesh_note_does_not_promise_a_switch_the_report_lacks(self):
        # Without a lookup the plan is built offline, so the note may only ask the
        # reader to check MeSH themselves, never point to a switch to turn on.
        with patch.object(search_plan, "lookup_mesh_headings",
                          side_effect=AssertionError("default plan must not look up MeSH")):
            plan = search_plan.build_search_plan(THERAPY_QUERY)
        self.assertEqual(plan["mesh_status"], "doğrulanmadı")
        self.assertIn("doğrulayın", _tr_lower(plan["mesh_note"]))
        self.assertNoSwitchPromise(plan["mesh_note"])
        text = search_plan.render_search_plan_markdown(plan, include_executed=False, include_table_template=False)
        self.assertIn(plan["mesh_note"], text)

    def assertNoSwitchPromise(self, text):
        lowered = _tr_lower(text)
        for phrase in _SWITCH_PROMISES:
            self.assertNotIn(phrase, lowered)

    def test_mesh_headings_from_lookup_are_added(self):
        def fake_lookup(term):
            return ["Diabetes Mellitus, Type 2"] if "diabetes" in term.lower() else []

        plan = search_plan.build_search_plan(THERAPY_QUERY, mesh_lookup=fake_lookup)
        self.assertIn('"Diabetes Mellitus, Type 2"[MeSH Terms] OR "type 2 diabetes"[tiab]', plan["suggested_query"])
        self.assertEqual(plan["mesh_status"], "PubMed terim eşleştirmesinden alındı")
        self.assertNotIn("[MeSH Terms]", plan["free_text_query"])

    def test_lookup_without_any_heading_is_reported(self):
        plan = search_plan.build_search_plan(THERAPY_QUERY, mesh_lookup=lambda term: [])
        self.assertEqual(plan["mesh_status"], "eşleşme bulunamadı")
        self.assertNotIn("[MeSH Terms]", plan["suggested_query"])

    def test_english_query_has_no_turkish_warning(self):
        # Case-insensitive matching once let "i" match the Turkish letter "ı".
        plan = search_plan.build_search_plan(THERAPY_QUERY)
        self.assertFalse(any("Türkçe" in w for w in plan["warnings"]))

    def test_turkish_query_warns_and_is_not_translated(self):
        plan = search_plan.build_search_plan("tip 2 diyabette egzersizin HbA1c düzeyine etkisi")
        self.assertTrue(any("Türkçe" in w for w in plan["warnings"]))
        self.assertNotIn("diabetes", plan["suggested_query"].lower())

    def test_unparsed_query_falls_back_to_query_text_with_warning(self):
        plan = search_plan.build_search_plan("statin use and the risk of myopathy")
        self.assertTrue(plan["query_is_fallback"])
        self.assertEqual(plan["suggested_query"], "statin use and the risk of myopathy")
        self.assertTrue(any("ayrıştırılamadı" in w for w in plan["warnings"]))

    def test_empty_query_gives_empty_plan_without_error(self):
        plan = search_plan.build_search_plan("   ")
        self.assertEqual(plan["suggested_query"], "")
        self.assertFalse(plan["query_is_fallback"])

    def test_criteria_are_proposals_and_nothing_is_screened(self):
        plan = search_plan.build_search_plan(THERAPY_QUERY)
        self.assertTrue(plan["is_proposal"])
        self.assertFalse(plan["screened_against_criteria"])
        self.assertIn("uygulanmadı", plan["criteria_status"])
        self.assertTrue(plan["inclusion_criteria"])
        self.assertTrue(plan["exclusion_criteria"])

    def test_executed_search_reflects_metadata_only(self):
        meta = {"query": THERAPY_QUERY, "search_date": "2026-11-04", "total_count": 120,
                "search_params": {"publication_type": "Tümü", "start_year": 2015, "end_year": None}}
        plan = search_plan.build_search_plan(THERAPY_QUERY, search_metadata=meta, retrieved_count=10)
        executed = plan["executed"]
        self.assertEqual(executed["total_count"], 120)
        self.assertEqual(executed["retrieved_count"], 10)
        self.assertEqual(executed["filters"], "yıl: 2015–…")
        self.assertIsNone(search_plan.build_search_plan(THERAPY_QUERY)["executed"])

    def test_backticks_in_query_do_not_break_markdown(self):
        plan = search_plan.build_search_plan("metformin `versus` placebo in adults with type 2 diabetes")
        self.assertNotIn("`", plan["query"])


class TestLookupMeshHeadings(unittest.TestCase):

    @patch("pubmed_client._get_with_retry")
    def test_headings_are_read_from_query_translation(self, mock_get):
        response = MagicMock()
        response.json.return_value = {"esearchresult": {
            "querytranslation": '"diabetes mellitus, type 2"[MeSH Terms] OR ("diabetes"[All Fields] AND "type 2"[All Fields])'}}
        mock_get.return_value = response
        self.assertEqual(search_plan.lookup_mesh_headings("type 2 diabetes"), ["diabetes mellitus, type 2"])
        sent = mock_get.call_args.kwargs["params"]
        self.assertEqual(sent["term"], "type 2 diabetes")
        self.assertEqual(sent["tool"], "MedicalResearchAI")

    @patch("pubmed_client._get_with_retry", side_effect=requests.exceptions.ConnectionError("down"))
    def test_network_failure_returns_empty_list(self, _mock_get):
        self.assertEqual(search_plan.lookup_mesh_headings("type 2 diabetes"), [])

    @patch("pubmed_client._get_with_retry")
    def test_bad_json_returns_empty_list(self, mock_get):
        response = MagicMock()
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response
        self.assertEqual(search_plan.lookup_mesh_headings("type 2 diabetes"), [])


class TestRenderSearchPlan(unittest.TestCase):

    def setUp(self):
        meta = {"query": THERAPY_QUERY, "search_date": "2026-11-04", "total_count": 120, "search_params": {}}
        self.plan = search_plan.build_search_plan(THERAPY_QUERY, search_metadata=meta, retrieved_count=10)

    def test_full_render_has_all_blocks(self):
        text = search_plan.render_search_plan_markdown(self.plan)
        for expected in ("### 🔎 Arama Planı", "#### Uygulanan arama", "#### Önerilen arama stratejisi (çalıştırılmadı)",
                         "#### Önerilen dahil etme ölçütleri", "#### Önerilen dışlama ölçütleri",
                         "#### Bakılabilecek veri tabanları", "#### Çalışma tablosu şablonu", "taranmamıştır"):
            self.assertIn(expected, text)
        self.assertIn("| Yazar-Yıl | PMID |", text)

    def test_report_mode_omits_executed_and_table(self):
        text = search_plan.render_search_plan_markdown(self.plan, include_executed=False, include_table_template=False)
        self.assertNotIn("#### Uygulanan arama", text)
        self.assertNotIn("Çalışma tablosu şablonu", text)
        self.assertIn("yukarıda belirtilen arama ifadesidir", text)

    def test_other_databases_are_not_claimed_as_searched(self):
        text = search_plan.render_search_plan_markdown(self.plan)
        self.assertIn("Bu uygulamanın taradığı tek kaynak", text)
        self.assertEqual(self.plan["executed"]["databases"], ["PubMed (NCBI E-utilities)"])


class TestReportIntegration(unittest.TestCase):

    @patch("report_generator.verify_citation")
    def test_plan_sits_inside_section_3_and_report_stays_valid(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"}
        report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", ARTICLES)
        section3 = report.index("## 3. Araştırma Yöntemi ve Tarama Tarihi")
        plan_at = report.index("### 🔎 Arama Planı")
        section4 = report.index("## 4. Klinik Arka Plan ve Patofizyoloji")
        self.assertTrue(section3 < plan_at < section4)
        # The plan is a sub-heading, never a new numbered or top-level section.
        self.assertFalse(any(line.startswith("## 🔎") for line in report.splitlines()))
        self.assertEqual(report.count("### 🔎 Arama Planı"), 1)
        quality = validate_clinical_report_quality(report)
        self.assertEqual(quality["missing_sections"], [])
        self.assertEqual(quality["detected_false_claims"], [])
        self.assertTrue(quality["valid"])

    @patch("report_generator.verify_citation")
    def test_report_builds_plan_offline_with_unverified_mesh_note(self, mock_verify):
        # The report must not look MeSH up (no network for the plan) and must tell the
        # reader the headings are unverified, without promising a switch it lacks.
        mock_verify.return_value = {"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"}
        with patch("search_plan.lookup_mesh_headings") as mock_lookup, \
                patch("pubmed_client._get_with_retry") as mock_http:
            report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", ARTICLES)
        mock_lookup.assert_not_called()
        mock_http.assert_not_called()
        plan_block = report[report.index("### 🔎 Arama Planı"):report.index("## 4. Klinik Arka Plan ve Patofizyoloji")]
        self.assertIn("**MeSH durumu:** doğrulanmadı.", plan_block)
        self.assertIn("kendiniz doğrulayın", plan_block)
        self.assertNotIn("[MeSH Terms]", plan_block)
        lowered = _tr_lower(plan_block)
        for phrase in _SWITCH_PROMISES:
            self.assertNotIn(phrase, lowered)

    @patch("report_generator.verify_citation")
    def test_report_survives_plan_failure(self, mock_verify):
        mock_verify.return_value = {"status": "verified", "verified": True, "pmid": "34449189", "reason": "match"}
        with patch("search_plan.build_search_plan", side_effect=RuntimeError("boom")):
            report = generate_rule_based_turkish_report("SGLT2 inhibitors in heart failure", ARTICLES)
        self.assertNotIn("Arama Planı", report)
        self.assertIn("## 4. Klinik Arka Plan ve Patofizyoloji", report)


if __name__ == "__main__":
    unittest.main()
