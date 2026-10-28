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

    @patch("api.generate_turkish_evidence_report")
    def test_api_generate_report(self, mock_generate):
        mock_generate.return_value = "# 📑 Türkçe Kanıt Raporu\n\nTest report content."

        payload = {
            "query": "diabetes",
            "articles": [
                {
                    "pmid": "35771962",
                    "title": "Test Title",
                    "authors": ["Author One"],
                    "journal": "Test Journal",
                    "pub_year": "2022",
                    "abstract": "Test abstract"
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
        self.assertEqual(data["audit"]["status"], "GEÇTİ (PASSED)")


if __name__ == "__main__":
    unittest.main()
