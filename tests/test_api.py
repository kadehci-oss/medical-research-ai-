import unittest
from unittest.mock import patch
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
    def test_api_search_rejects_invalid_sort_and_year_range(self, mock_search):
        bad_sort = client.get("/api/search?query=diabetes&sort=arbitrary")
        reversed_years = client.get("/api/search?query=diabetes&start_year=2024&end_year=2020")
        too_long_query = client.get(f"/api/search?query={'x' * 2001}")
        self.assertEqual(bad_sort.status_code, 422)
        self.assertEqual(reversed_years.status_code, 422)
        self.assertEqual(too_long_query.status_code, 422)
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


if __name__ == "__main__":
    unittest.main()
