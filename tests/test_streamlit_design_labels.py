"""Streamlit UI regression for design, unassigned evidence level, and RoB labels."""
import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class TestStreamlitDesignLabels(unittest.TestCase):
    @patch("pubmed_client.search_pubmed")
    @patch("report_generator.verify_citation")
    def test_search_result_does_not_show_a_design_based_evidence_grade(self, mock_verify, mock_search):
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match", "pmid": "90000001"}
        mock_search.return_value = {
            "status": "success",
            "articles": [
                {
                    "pmid": "90000001",
                    "title": "Empagliflozin in heart failure with preserved ejection fraction",
                    "authors": ["Ada Lovelace"],
                    "journal": "Test Journal",
                    "pub_year": "2024",
                    "publication_types": ["Randomized Controlled Trial"],
                    "abstract": (
                        "In this double-blind randomized trial, 120 patients with heart failure were randomized "
                        "to empagliflozin or placebo (n = 120). Heart failure hospitalization fell "
                        "(HR 0.79, 95% CI 0.69-0.90, p<0.001)."
                    ),
                    "doi": "10.1000/streamlit-rct",
                    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/90000001/",
                    "doi_url": "https://doi.org/10.1000/streamlit-rct",
                }
            ],
            "total_count": 1,
            "query": "empagliflozin in heart failure",
            "executed_query": "empagliflozin in heart failure",
            "search_date": "2026-10-30",
            "query_enhancement": {},
            "evidence_ranking": {},
        }

        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
        at = AppTest.from_file(app_path, default_timeout=20)
        at.run()
        at.text_input[0].input("empagliflozin in heart failure")
        search_btn = [button for button in at.button if "Ara" in button.label][0]
        search_btn.click().run()

        self.assertTrue(at.expander)
        labels = " ".join(expander.label for expander in at.expander)
        self.assertIn("Rastgele Kontrollü", labels)
        self.assertNotIn("Seviye 2", labels)
        self.assertNotIn("Seviye 1", labels)

        visible = " ".join(getattr(block, "value", "") for block in at.markdown)
        visible += " " + " ".join(getattr(block, "value", "") for block in getattr(at, "caption", []))
        self.assertIn("Değerlendirilemedi", visible)
        self.assertIn("RoB 2", visible)
        self.assertIn("90000001", visible)
        self.assertNotIn("Seviye 2", visible)


if __name__ == "__main__":
    unittest.main()
