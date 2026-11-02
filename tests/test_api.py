import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


class TestFastAPIApp(unittest.TestCase):

    def test_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "Medical Research AI API"})

    @patch("api.search_pubmed")
    def test_api_search_pubmed(self, mock_search):
        mock_search.return_value = {
            "articles": [
                {
                    "pmid": "12345",
                    "title": "Test Title",
                    "authors": ["Author One"],
                    "journal": "Test Journal",
                    "pub_year": "2023",
                    "publication_types": ["Journal Article"],
                    "abstract": "Test abstract",
                    "doi": "10.1000/test",
                    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
                    "doi_url": "https://doi.org/10.1000/test"
                }
            ],
            "total_count": 1,
            "query": "diabetes"
        }

        response = client.get("/api/search?query=diabetes&max_results=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(data["articles"][0]["pmid"], "12345")

    @patch("api.search_pubmed")
    def test_api_search_author_uses_pubmed_full_author_name_field(self, mock_search):
        mock_search.return_value = {
            "articles": [],
            "total_count": 0,
            "query": "Jane Doe[FAU]",
        }

        response = client.get(
            "/api/search/author?first_name=Jane&last_name=Doe&max_results=3&start_year=2000"
        )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once_with(
            query="Jane Doe[FAU]",
            max_results=3,
            retstart=0,
            sort="relevance",
            publication_type="Tümü",
            start_year=2000,
            end_year=None,
        )

    @patch("api.search_pubmed")
    def test_api_search_author_rejects_query_syntax_in_names(self, mock_search):
        response = client.get("/api/search/author?first_name=Jane%5BAU%5D&last_name=Doe")
        self.assertEqual(response.status_code, 422)
        mock_search.assert_not_called()

    @patch("requests.get")
    def test_api_search_pagination_end_to_end(self, mock_get):
        def response():
            item = MagicMock()
            item.status_code = 200
            item.headers = {}
            item.raise_for_status.return_value = None
            return item

        def xml_for(pmids):
            records = "".join(
                f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>Study {pmid}</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
                for pmid in pmids
            )
            return f"<PubmedArticleSet>{records}</PubmedArticleSet>"

        search_first, fetch_first = response(), response()
        search_first.json.return_value = {"esearchresult": {"count": "4", "idlist": ["20001", "20002"]}}
        fetch_first.text = xml_for(["20001", "20002"])
        search_second, fetch_second = response(), response()
        search_second.json.return_value = {"esearchresult": {"count": "4", "idlist": ["20003", "20004"]}}
        fetch_second.text = xml_for(["20003", "20004"])
        mock_get.side_effect = [search_first, fetch_first, search_second, fetch_second]

        first = client.get("/api/search?query=diabetes&max_results=2&retstart=0")
        second = client.get("/api/search?query=diabetes&max_results=2&retstart=2")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual([item["pmid"] for item in first.json()["articles"]], ["20001", "20002"])
        self.assertEqual([item["pmid"] for item in second.json()["articles"]], ["20003", "20004"])
        self.assertEqual(first.json()["pagination"]["retstart"], 0)
        self.assertEqual(first.json()["pagination"]["next_retstart"], 2)
        self.assertTrue(first.json()["pagination"]["truncated"])
        self.assertFalse(second.json()["pagination"]["has_more"])
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["retstart"], 0)
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["retmax"], 2)
        self.assertEqual(mock_get.call_args_list[2].kwargs["params"]["retstart"], 2)

    @patch("requests.get")
    def test_api_search_last_offset_clamps_page_and_reports_unreachable_more(self, mock_get):
        esearch = MagicMock()
        esearch.status_code = 200
        esearch.headers = {}
        esearch.raise_for_status.return_value = None
        esearch.json.return_value = {"esearchresult": {"count": "20000", "idlist": ["30001"]}}
        efetch = MagicMock()
        efetch.status_code = 200
        efetch.headers = {}
        efetch.raise_for_status.return_value = None
        efetch.text = (
            "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>30001</PMID>"
            "<Article><ArticleTitle>Study 30001</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        )
        mock_get.side_effect = [esearch, efetch]

        response = client.get("/api/search?query=diabetes&max_results=50&retstart=9999")

        self.assertEqual(response.status_code, 200)
        pagination = response.json()["pagination"]
        self.assertEqual(pagination["retstart"], 9999)
        self.assertEqual(pagination["page_size"], 1)
        self.assertTrue(pagination["limit_applied"])
        self.assertTrue(pagination["has_more"])
        self.assertTrue(pagination["retrieval_window_exhausted"])
        self.assertIsNone(pagination["next_retstart"])
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["retstart"], 9999)
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["retmax"], 1)

    @patch("api.search_pubmed")
    def test_api_search_masks_upstream_error_details(self, mock_search):
        mock_search.return_value = {
            "articles": [],
            "total_count": 0,
            "error": "authorization=hidden-sensitive-value",
        }
        response = client.get("/api/search?query=diabetes")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("hidden-sensitive-value", response.text)
        self.assertIn("daha sonra tekrar deneyin", response.json()["detail"])

    @patch("api.search_pubmed")
    def test_api_search_rejects_invalid_sort_and_year_range(self, mock_search):
        bad_sort = client.get("/api/search?query=diabetes&sort=arbitrary")
        reversed_years = client.get("/api/search?query=diabetes&start_year=2024&end_year=2020")
        too_long_query = client.get(f"/api/search?query={'x' * 2001}")
        invalid_offset = client.get("/api/search?query=diabetes&retstart=10000")
        self.assertEqual(bad_sort.status_code, 422)
        self.assertEqual(reversed_years.status_code, 422)
        self.assertEqual(too_long_query.status_code, 422)
        self.assertEqual(invalid_offset.status_code, 422)
        mock_search.assert_not_called()

    @patch("api.verify_pmid")
    def test_api_verify_pmid_success(self, mock_verify):
        mock_verify.return_value = {
            "valid": True,
            "pmid": "35771962",
            "title": "Diagnosis and Management of Central Diabetes Insipidus in Adults.",
            "authors": ["Maria Tomkins"],
            "journal": "The Journal of clinical endocrinology and metabolism",
            "pub_year": "2022"
        }

        response = client.get("/api/verify/pmid/35771962")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    @patch("api.verify_pmid")
    def test_api_verify_pmid_not_found(self, mock_verify):
        mock_verify.return_value = {
            "valid": False,
            "pmid": "999999999",
            "error": "PMID not found"
        }

        response = client.get("/api/verify/pmid/999999999")
        self.assertEqual(response.status_code, 404)

    @patch("api.verify_pmid")
    def test_api_verify_pmid_upstream_error_is_502(self, mock_verify):
        mock_verify.return_value = {
            "valid": False,
            "pmid": "35771962",
            "reason": "upstream_error",
            "error": "PubMed kaydı doğrulanırken geçici bir hata oluştu.",
        }
        response = client.get("/api/verify/pmid/35771962")
        self.assertEqual(response.status_code, 502)

    @patch("api.verify_doi")
    def test_api_verify_doi_success(self, mock_verify):
        mock_verify.return_value = {
            "valid": True,
            "doi": "10.1210/clinem/dgac381",
            "title": "Diagnosis and Management of Central Diabetes Insipidus in Adults"
        }

        response = client.get("/api/verify/doi/10.1210/clinem/dgac381")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    @patch("api.verify_citation")
    def test_api_verify_citation(self, mock_verify_citation):
        mock_verify_citation.return_value = {
            "status": "verified",
            "verified": True,
            "pmid": "35771962",
            "reason": "match"
        }

        response = client.post("/api/verify/citation", json={"pmid": "35771962", "title": "Test Title"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "verified")

    @patch("api.verify_citation")
    @patch("api.generate_turkish_evidence_report")
    def test_api_generate_report(self, mock_generate, mock_verify_citation):
        mock_generate.return_value = "# 📑 Türkçe Kanıt Raporu\n\nTest report content."
        mock_verify_citation.return_value = {
            "status": "verified",
            "verified": True,
            "pmid": "35771962",
            "reason": "match",
            "fetched_article": {
                "valid": True,
                "pmid": "35771962",
                "title": "Canonical PubMed title",
                "authors": ["PubMed Author"],
                "journal": "PubMed Journal",
                "pub_year": "2022",
                "publication_types": ["Journal Article"],
                "abstract": "Canonical abstract from PubMed",
                "doi": "10.1000/pubmed",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/35771962/",
            },
        }

        payload = {
            "query": "diabetes",
            "articles": [
                {
                    "pmid": "35771962",
                    "title": "Canonical PubMed title",
                    "authors": ["Attacker-supplied author"],
                    "journal": "Untrusted journal",
                    "pub_year": "2022",
                    "abstract": "Untrusted abstract"
                }
            ],
            "use_llm": False
        }

        response = client.post("/api/report", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "diabetes")
        self.assertIn("Türkçe Kanıt Raporu", data["report"])
        self.assertIn("html_report", data)
        self.assertIn("audit", data)
        self.assertIn("DENETLEME TAMAMLANDI", data["audit"]["status"])
        self.assertIn("quality_control", data)
        self.assertFalse(data["quality_control"]["valid"])
        self.assertTrue(data["quality_control"]["missing_sections"])
        self.assertEqual(mock_generate.call_args.kwargs["articles"][0]["title"], "Canonical PubMed title")
        self.assertEqual(mock_generate.call_args.kwargs["articles"][0]["abstract"], "Canonical abstract from PubMed")

    @patch("api.perform_red_team_audit", return_value={})
    @patch("api._load_verified_articles", return_value=([], []))
    @patch("api.generate_turkish_evidence_report", side_effect=RuntimeError("internal-sensitive-error"))
    def test_api_generate_report_masks_generator_failure(self, _mock_generate, _mock_load, _mock_audit):
        response = client.post(
            "/api/report",
            json={"query": "diabetes", "articles": [{"pmid": "12345"}]},
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Rapor oluşturulamadı", response.json()["detail"])
        self.assertNotIn("internal-sensitive-error", response.text)

    @patch("api.verify_citation")
    @patch("api.generate_turkish_evidence_report")
    def test_api_report_rejects_mismatched_citation_before_synthesis(self, mock_generate, mock_verify_citation):
        mock_verify_citation.return_value = {
            "status": "rejected",
            "verified": False,
            "pmid": "35771962",
            "reason": "title_mismatch",
            "error": "Title mismatch",
        }
        response = client.post(
            "/api/report",
            json={"query": "diabetes", "articles": [{"pmid": "35771962", "title": "Fake title"}]},
        )
        self.assertEqual(response.status_code, 422)
        mock_generate.assert_not_called()

    def test_api_report_limits_citations_to_50(self):
        response = client.post(
            "/api/report",
            json={"query": "diabetes", "articles": [{"pmid": str(10000 + index)} for index in range(51)]},
        )
        self.assertEqual(response.status_code, 422)

    @patch("api.verify_citation")
    def test_llm_endpoints_require_explicit_data_transfer_confirmation(self, mock_verify_citation):
        payload = {
            "query": "diabetes",
            "articles": [{"pmid": "12345"}],
            "api_key": "test-key",
            "use_llm": True,
        }
        report_response = client.post("/api/report", json=payload)
        synthesis_response = client.post("/api/universal_engine/synthesize", json=payload)

        self.assertEqual(report_response.status_code, 422)
        self.assertEqual(synthesis_response.status_code, 422)
        self.assertIn("açıkça onaylayın", report_response.json()["detail"])
        mock_verify_citation.assert_not_called()

    @patch("api.verify_citation")
    @patch("api.generate_turkish_evidence_report")
    @patch("api.generate_universal_evidence_synthesis")
    def test_confirmed_llm_transfer_permission_reaches_both_generators(
        self, mock_synthesize, mock_generate_report, mock_verify_citation
    ):
        mock_synthesize.return_value = {"status": "success"}
        mock_generate_report.return_value = "# Test report"
        mock_verify_citation.return_value = {
            "status": "verified",
            "verified": True,
            "pmid": "12345",
            "reason": "match",
            "fetched_article": {
                "valid": True,
                "pmid": "12345",
                "title": "Canonical PubMed title",
                "authors": ["PubMed Author"],
                "journal": "PubMed Journal",
                "pub_year": "2024",
                "publication_types": ["Randomized Controlled Trial"],
                "abstract": "Canonical PubMed abstract",
                "doi": "10.1000/pubmed",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
            },
        }
        payload = {
            "query": "diabetes",
            "articles": [{"pmid": "12345"}],
            "api_key": "test-key",
            "use_llm": True,
            "llm_data_transfer_confirmed": True,
        }

        report_response = client.post("/api/report", json=payload)
        synthesis_response = client.post("/api/universal_engine/synthesize", json=payload)

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(synthesis_response.status_code, 200)
        self.assertTrue(mock_generate_report.call_args.kwargs["allow_external_data_transfer"])
        self.assertTrue(mock_synthesize.call_args.kwargs["allow_external_data_transfer"])

    @patch("api.verify_citation")
    def test_api_report_rejects_invalid_or_duplicate_pmids(self, mock_verify_citation):
        mock_verify_citation.return_value = {
            "status": "verified",
            "verified": True,
            "pmid": "12345",
            "fetched_article": {"valid": True, "pmid": "12345", "title": "Canonical title"},
        }
        invalid = client.post("/api/report", json={"query": "diabetes", "articles": [{"pmid": "abc"}]})
        empty = client.post("/api/report", json={"query": "diabetes", "articles": []})
        duplicate = client.post(
            "/api/report",
            json={"query": "diabetes", "articles": [{"pmid": "12345"}, {"pmid": "12345"}]},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(duplicate.status_code, 422)
        mock_verify_citation.assert_called_once()

    @patch("api.verify_citation")
    @patch("api.generate_universal_evidence_synthesis")
    def test_universal_synthesis_uses_canonical_pubmed_record(self, mock_synthesize, mock_verify_citation):
        mock_synthesize.return_value = {"status": "success"}
        mock_verify_citation.return_value = {
            "status": "verified",
            "verified": True,
            "pmid": "12345",
            "reason": "match",
            "fetched_article": {
                "valid": True,
                "pmid": "12345",
                "title": "Canonical title",
                "abstract": "Canonical PubMed abstract",
                "authors": ["Canonical author"],
            },
        }
        response = client.post(
            "/api/universal_engine/synthesize",
            json={"query": "diabetes", "articles": [{"pmid": "12345", "abstract": "untrusted"}]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_synthesize.call_args.kwargs["articles"][0]["abstract"], "Canonical PubMed abstract")
        self.assertEqual(mock_synthesize.call_args.kwargs["verification_results"][0]["status"], "verified")

    @patch("api._load_verified_articles", return_value=([], []))
    @patch("api.generate_universal_evidence_synthesis")
    def test_universal_synthesis_engine_error_is_not_returned_as_success(self, mock_synthesize, _mock_load):
        mock_synthesize.return_value = {
            "status": "error",
            "error": "Sentez sırasında beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
            "report_markdown": "# Hata Oluştu",
        }

        response = client.post(
            "/api/universal_engine/synthesize",
            json={"query": "diabetes", "articles": [{"pmid": "12345"}]},
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Sentez sırasında beklenmeyen", response.json()["detail"])
        self.assertNotIn("report_markdown", response.json())


if __name__ == "__main__":
    unittest.main()
