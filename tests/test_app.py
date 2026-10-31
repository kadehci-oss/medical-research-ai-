import os
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class TestAppRegression(unittest.TestCase):

    @patch("pubmed_client.search_pubmed")
    @patch("report_generator.generate_turkish_evidence_report")
    @patch("report_generator.generate_html_report")
    @patch("report_generator.verify_citation")
    def test_new_search_clears_old_generated_report(
        self, mock_verify_cit, mock_gen_html, mock_gen_report, mock_search
    ):
        mock_verify_cit.return_value = {"status": "verified", "verified": True, "reason": "match"}
        mock_search.return_value = {
            "articles": [
                {
                    "pmid": "11111",
                    "title": "Study 1",
                    "authors": ["Author 1"],
                    "journal": "Journal 1",
                    "pub_year": "2023",
                    "publication_types": ["Journal Article"],
                    "abstract": "Abstract 1",
                    "doi": "10.1000/1",
                    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/11111/",
                    "doi_url": "https://doi.org/10.1000/1"
                }
            ],
            "total_count": 1,
            "query": "query 1",
            "search_date": "2023-10-01"
        }
        mock_gen_report.return_value = "# Report for Query 1"
        mock_gen_html.return_value = "<html>Report 1</html>"

        app_path = os.path.abspath("app.py")
        at = AppTest.from_file(app_path, default_timeout=10)
        at.run()

        # Input query 1 and click search button ("🔍 Ara")
        search_btn = [b for b in at.button if "Ara" in b.label][0]
        at.text_input[0].input("query 1")
        search_btn.click().run()

        # Click report generation button ("📑 Türkçe Kanıt Raporunu ve Tabloları Oluştur")
        report_btn = [b for b in at.button if "Türkçe Kanıt Raporu" in b.label][0]
        report_btn.click().run()

        self.assertIn("generated_report", at.session_state)
        self.assertEqual(at.session_state["generated_report"], "# Report for Query 1")
        metric_labels = [metric.label for metric in at.metric]
        metric_values = [str(metric.value) for metric in at.metric]
        self.assertIn("Uzman Hekim Değerlendirmesi", metric_labels)
        self.assertIn("Yapılmadı", metric_values)
        self.assertTrue(at.error or at.warning)

        # Now perform a NEW search
        mock_search.return_value = {
            "articles": [
                {
                    "pmid": "22222",
                    "title": "Study 2",
                    "authors": ["Author 2"],
                    "journal": "Journal 2",
                    "pub_year": "2024",
                    "publication_types": ["Journal Article"],
                    "abstract": "Abstract 2",
                    "doi": "10.1000/2",
                    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/22222/",
                    "doi_url": "https://doi.org/10.1000/2"
                }
            ],
            "total_count": 1,
            "query": "query 2",
            "search_date": "2023-10-02"
        }

        at.text_input[0].input("query 2")
        search_btn = [b for b in at.button if "Ara" in b.label][0]
        search_btn.click().run()

        # Verify old generated_report and generated_html_report are removed from session_state
        self.assertNotIn("generated_report", at.session_state)
        self.assertNotIn("generated_html_report", at.session_state)

    def test_streamlit_displays_version_and_commit_info(self):
        app_path = os.path.abspath("app.py")
        at = AppTest.from_file(app_path, default_timeout=10)
        at.run()
        sidebar_captions = [c.value for c in at.sidebar.caption]
        has_version_caption = any("Sürüm:" in cap and "Commit:" in cap for cap in sidebar_captions)
        self.assertTrue(has_version_caption, f"Expected version/commit caption in sidebar, got: {sidebar_captions}")

    def test_openai_data_transfer_is_disabled_by_default(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=10)
            at.run()

        llm_toggle = next(item for item in at.sidebar.checkbox if item.label == "OpenAI Sentez Motorunu Kullan")
        self.assertFalse(llm_toggle.value)

    @patch("app.UniversalEvidenceEngine.search_and_verify")
    def test_article_identifiers_are_rendered_as_plain_text(self, mock_search):
        malicious_doi = '<img src=x onerror="alert(1)">'
        mock_search.return_value = {
            "query": "test query",
            "total_count": 1,
            "articles": [{
                "pmid": "12345",
                "title": "Test article",
                "authors": [],
                "journal": "Test journal",
                "pub_year": "2024",
                "publication_types": ["Journal Article"],
                "abstract": "Test abstract",
                "doi": malicious_doi,
                "pubmed_url": "",
                "doi_url": "",
            }],
        }
        at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=10)
        at.run()
        at.text_input[0].input("test query")
        [button for button in at.button if "Ara" in button.label][0].click().run()

        displayed_text = [element.value for element in at.text]
        rendered_markdown = [element.value for element in at.markdown]
        self.assertIn(f"PMID: 12345 | DOI: {malicious_doi}", displayed_text)
        self.assertFalse(any(malicious_doi in value for value in rendered_markdown))


if __name__ == "__main__":
    unittest.main()
