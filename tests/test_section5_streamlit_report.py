"""Streamlit AppTest: section 5 must not render a raw English abstract."""
import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from report_generator import INSUFFICIENT_CLINICAL_DATA_TR


_RAW_ABSTRACT = (
    "Statin-associated immune-mediated necrotizing myopathy is a rare presentation "
    "of a statin-associated myopathy with progressive weakness after atorvastatin."
)
_SOURCE_SENTENCE = (
    "Heart failure hospitalization was lower with empagliflozin than with placebo "
    "(HR 0.79, 95% CI 0.69-0.90)."
)


class TestSection5StreamlitReport(unittest.TestCase):
    @patch("pubmed_client.search_pubmed")
    @patch("report_generator.verify_citation")
    def test_section_5_shows_turkish_grounded_findings_not_the_english_abstract(
        self, mock_verify, mock_search
    ):
        os.environ.pop("OPENAI_API_KEY", None)
        mock_verify.return_value = {"status": "verified", "verified": True, "reason": "match"}
        articles = [
            {
                "pmid": "90000021",
                "title": "A case of statin-associated immune-mediated necrotizing myopathy",
                "authors": ["Deneme Yazar"],
                "journal": "Test Journal",
                "pub_year": "2021",
                "publication_types": ["Journal Article", "Review"],
                "abstract": _RAW_ABSTRACT,
                "doi": "10.1000/test-case",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/90000021/",
                "doi_url": "https://doi.org/10.1000/test-case",
            },
            {
                "pmid": "90000022",
                "title": "Empagliflozin in patients hospitalized for acute heart failure",
                "authors": ["Deneme Yazar"],
                "journal": "Test Journal",
                "pub_year": "2022",
                "publication_types": ["Journal Article", "Randomized Controlled Trial"],
                "abstract": _SOURCE_SENTENCE,
                "doi": "10.1000/test-rct",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/90000022/",
                "doi_url": "https://doi.org/10.1000/test-rct",
            },
            {
                "pmid": "90000023",
                "title": "Group differences in inflammatory myopathy",
                "authors": ["Deneme Yazar"],
                "journal": "Test Journal",
                "pub_year": "2025",
                "publication_types": ["Journal Article"],
                "abstract": (
                    "In this retrospective study 40 patients with myositis were compared. "
                    "Statistical comparisons were performed. "
                    "Anti-HMGCR myopathy was increased in one group "
                    "(OR: 4.81, CI: (1.03, 22.6), p=0.045) as was diabetes mellitus "
                    "(OR: 2.54, CI: (1.02, 6.29), p=0.05). "
                    "Cancer-associated myositis was lower (OR: 0.23CI: (0.08, 0.7), p=0.027)."
                ),
                "doi": "10.1000/test-retro",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/90000023/",
                "doi_url": "https://doi.org/10.1000/test-retro",
            },
        ]
        mock_search.return_value = {
            "status": "success",
            "articles": articles,
            "total_count": len(articles),
            "query": "statin-associated immune-mediated necrotizing myopathy",
            "search_date": "2026-10-30",
        }

        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
        at = AppTest.from_file(app_path, default_timeout=60)
        at.run()
        self.assertFalse(at.exception)

        at.text_input[0].input("statin-associated immune-mediated necrotizing myopathy").run()
        search_btn = [button for button in at.button if "Ara" in button.label][0]
        search_btn.click().run()
        self.assertFalse(at.exception)

        report_btn = [button for button in at.button if "Türkçe Kanıt Raporu" in button.label][0]
        report_btn.click().run()
        self.assertFalse(at.exception)

        report = at.session_state["generated_report"]
        self.assertIn("## 5. Bilimsel Kanıt Tablosu", report)
        section = report.split("## 5. Bilimsel Kanıt Tablosu")[1].split("## 6.")[0]

        self.assertIn(INSUFFICIENT_CLINICAL_DATA_TR, section)
        self.assertNotIn("is a rare presentation of a statin-associated myopathy", section)
        self.assertIn("**Olgu Sunumu**", section)
        self.assertNotIn("Niteliksel Derleme", section)

        self.assertIn("PMID: 90000022", section)
        self.assertIn("Etki ölçütü: HR 0.79", section)
        self.assertIn("Güven aralığı: 0.69 ile 0.90", section)
        self.assertIn(_SOURCE_SENTENCE, section)
        self.assertIn("Sonlanım:", section)

        grouped = section.split("PMID: 90000023", 1)[1].split("|  ", 1)[0]
        self.assertEqual(grouped.count("Anti-HMGCR myopathy was increased"), 1)
        self.assertIn("Sonlanım: anti-HMGCR miyopati", grouped)
        self.assertIn("Sonlanım: diyabet", grouped)
        self.assertIn("Sonlanım: kanserle ilişkili miyozit", grouped)
        self.assertIn("diabetes mellitus", grouped)
        self.assertNotIn("Sonlanım: diabetes mellitus", grouped)
        self.assertIn("Güven aralığı: 1.03 ile 22.6", grouped)
        self.assertIn("Güven aralığı: 0.08 ile 0.7", grouped)
        self.assertNotIn("Güven aralığı: özette bildirilmedi", grouped)
        self.assertIn("Retrospektif Karşılaştırmalı Gözlemsel Araştırma", section)
        heart_row = [line for line in section.splitlines() if "90000022" in line and line.startswith("|")][0]
        self.assertNotIn("4.81", heart_row)
        self.assertNotIn("22.6", heart_row)

        visible = "\n".join(getattr(block, "value", "") or "" for block in at.markdown)
        self.assertIn(INSUFFICIENT_CLINICAL_DATA_TR, visible)
        self.assertIn("## 5. Bilimsel Kanıt Tablosu", visible)
        self.assertIn("## 6. Önemli Çalışmaların Karşılaştırılması", visible)
        self.assertIn("Hasta grubu", visible)
        self.assertIn("Klinik sonucu doğrudan destekleyen PMID", visible)


if __name__ == "__main__":
    unittest.main()
