"""Tests for tools/report_quality_audit.py.

Verifies quality rules (positive and negative cases for all 7 rules),
source-sentence exclusion behavior, and live/mock engine integration test.
"""

import sys
import unittest
from pathlib import Path

# Ensure repo root is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.report_quality_audit import (
    audit_report_quality,
    check_consecutive_duplicate_words,
    check_duplicate_lines_in_block,
    check_expert_review_claim,
    check_raw_english_ci,
    check_raw_english_sentences,
    check_significance_contradictions,
    check_unlabeled_number_lists,
)
from universal_evidence_engine import UniversalEvidenceEngine


class TestRawEnglishSentencesRule(unittest.TestCase):
    def test_positive_raw_english_detected(self):
        text = (
            "## 2. Yönetici Özeti\n"
            "This randomized controlled clinical trial evaluated the efficacy and safety in patients with heart failure.\n"
        )
        findings = check_raw_english_sentences(text)
        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("randomized controlled clinical trial", findings[0]["text"])

    def test_negative_turkish_sentence_not_flagged(self):
        text = (
            "## 2. Yönetici Özeti\n"
            "Bu randomize kontrollü klinik çalışma kalp yetersizliği olan hastalarda etkinlik ve güvenliliği değerlendirmiştir.\n"
        )
        findings = check_raw_english_sentences(text)
        self.assertEqual(len(findings), 0)

    def test_source_sentence_and_quotes_not_flagged(self):
        text = (
            "## 6. Önemli Çalışmaların Karşılaştırılması\n"
            "- Hasta grubu: kalp yetersizliği. Kaynak cümle: \"This randomized trial included 400 patients with heart failure.\" (PMID: 12345678)\n"
            "> \"The efficacy and safety of the drug were evaluated in this cohort of patients.\"\n"
        )
        findings = check_raw_english_sentences(text)
        self.assertEqual(len(findings), 0)

    def test_bibliography_and_headers_not_flagged(self):
        text = (
            "## 13. Doğrulanmış Kaynakça\n"
            "1. Smith J. Efficacy and safety of statins in patients with muscle symptoms. N Engl J Med. PMID: 12345678.\n"
        )
        findings = check_raw_english_sentences(text)
        self.assertEqual(len(findings), 0)


class TestConsecutiveDuplicateWordsRule(unittest.TestCase):
    def test_positive_duplicate_words_detected(self):
        text = "Tedavi grubunda mortalite oranı oranı belirgin olarak azalmıştır."
        findings = check_consecutive_duplicate_words(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["repeated_word"].lower(), "oranı")

    def test_negative_normal_text(self):
        text = "Tedavi grubunda mortalite oranı belirgin olarak azalmıştır."
        findings = check_consecutive_duplicate_words(text)
        self.assertEqual(len(findings), 0)

    def test_negative_allowed_reduplication(self):
        text = "Doz yavaş yavaş artırılmıştır ve ayrı ayrı gruplar oluşturulmuştur."
        findings = check_consecutive_duplicate_words(text)
        self.assertEqual(len(findings), 0)


class TestDuplicateLinesInBlockRule(unittest.TestCase):
    def test_positive_duplicate_lines_in_same_block(self):
        text = (
            "## 7. Tedavi Etkinliği ve Güvenlilik\n"
            "- Primer sonlanım mortalitede azalma olarak saptanmıştır (PMID: 12345678).\n"
            "- Primer sonlanım mortalitede azalma olarak saptanmıştır (PMID: 12345678).\n"
        )
        findings = check_duplicate_lines_in_block(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["block"], "7. Tedavi Etkinliği ve Güvenlilik")

    def test_negative_distinct_lines_in_same_block(self):
        text = (
            "## 7. Tedavi Etkinliği ve Güvenlilik\n"
            "- Primer sonlanım mortalitede azalma olarak saptanmıştır (PMID: 12345678).\n"
            "- Sekonder sonlanım hastaneye yatışlarda düşüş olarak bildirilmiştir (PMID: 12345678).\n"
        )
        findings = check_duplicate_lines_in_block(text)
        self.assertEqual(len(findings), 0)


class TestUnlabeledNumberListsRule(unittest.TestCase):
    def test_positive_unlabeled_numbers_detected(self):
        text = "Örneklem dağılımı: 15 hasta; 15 hasta; 5 hasta şeklindedir."
        findings = check_unlabeled_number_lists(text)
        self.assertEqual(len(findings), 1)

    def test_negative_properly_labeled_metrics(self):
        text = "Grup 1: 15 hasta, Grup 2: 20 hasta, Kontrol: 5 hasta dahil edilmiştir."
        findings = check_unlabeled_number_lists(text)
        self.assertEqual(len(findings), 0)


class TestSignificanceContradictionsRule(unittest.TestCase):
    def test_positive_not_significant_with_low_p(self):
        text = "İki grup arasında anlamlı bir fark saptanmamıştır (p = 0.01)."
        findings = check_significance_contradictions(text)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["critical"])
        self.assertEqual(findings[0]["type"], "not_significant_with_low_p")

    def test_positive_unevaluated_with_low_p(self):
        text = "Sonlanım etkisi değerlendirilemedi (p < 0.05)."
        findings = check_significance_contradictions(text)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["critical"])
        self.assertEqual(findings[0]["type"], "unevaluated_with_low_p")

    def test_negative_consistent_significance(self):
        text1 = "İki grup arasında istatistiksel olarak anlamlı bir fark saptanmıştır (p < 0.01)."
        findings1 = check_significance_contradictions(text1)
        self.assertEqual(len(findings1), 0)

        text2 = "Anlamlı bir fark saptanmamıştır (p = 0.45)."
        findings2 = check_significance_contradictions(text2)
        self.assertEqual(len(findings2), 0)


class TestRawEnglishCIRule(unittest.TestCase):
    def test_positive_raw_confidence_interval_detected(self):
        text = "Rölatif risk 0.75, 95% confidence interval 0.60-0.92 olarak hesaplanmıştır."
        findings = check_raw_english_ci(text)
        self.assertEqual(len(findings), 1)

    def test_positive_raw_ci_prefix_detected(self):
        text = "Grup farkı saptandı (OR: 1.5, CI: 1.1-2.1)."
        findings = check_raw_english_ci(text)
        self.assertEqual(len(findings), 1)

    def test_negative_turkish_ga_format(self):
        text = "Rölatif risk 0.75, %95 GA: 0.60 ile 0.92 olarak hesaplanmıştır."
        findings = check_raw_english_ci(text)
        self.assertEqual(len(findings), 0)


class TestExpertReviewClaimRule(unittest.TestCase):
    def test_positive_expert_review_claimed_done(self):
        text = "Uzman hekim değerlendirmesi: Yapıldı"
        findings = check_expert_review_claim(text)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["critical"])

    def test_positive_expert_review_claimed_in_narrative(self):
        text = "Bu bulgular uzman hekim değerlendirmesi yapılmıştır."
        findings = check_expert_review_claim(text)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["critical"])

    def test_negative_expert_review_not_done(self):
        text = "Uzman Hekim Değerlendirmesi: Yapılmadı. Uzman hekim değerlendirmesi yapılmamıştır."
        findings = check_expert_review_claim(text)
        self.assertEqual(len(findings), 0)


class TestEngineReportQualityIntegration(unittest.TestCase):
    def test_mock_engine_report_passes_critical_checks(self):
        """Generates a report using UniversalEvidenceEngine with mock article,

        runs audit_report_quality, and asserts that zero CRITICAL violations exist.
        Non-critical counts are reported without failing the test.
        """
        engine = UniversalEvidenceEngine()
        mock_articles = [
            {
                "pmid": "88880001",
                "title": "SGLT2 inhibitors in heart failure: randomized trial",
                "authors": ["Ahmet Yılmaz", "Mehmet Kaya"],
                "journal": "Turk Kardiyol Dern Ars",
                "pub_year": "2023",
                "abstract": (
                    "BACKGROUND: Heart failure remains a major cause of hospitalization. "
                    "METHODS: We enrolled 200 patients randomized to SGLT2 inhibitor or placebo. "
                    "RESULTS: Cardiovascular death was significantly reduced (HR 0.70, 95% CI 0.50-0.90, p=0.01). "
                    "CONCLUSIONS: SGLT2 inhibitors improve clinical outcomes."
                ),
                "doi": "10.1000/mock1",
                "publication_types": ["Randomized Controlled Trial"],
            }
        ]

        result = engine.generate_synthesis_report("kalp yetersizliği SGLT2", mock_articles)
        markdown_report = result["report_markdown"]

        audit_result = audit_report_quality(markdown_report)

        # Log counts for transparency
        summary = audit_result["summary"]
        counts = audit_result["counts"]
        print(f"\n[Mock Engine Report Audit] Total Issues: {summary['total_issues']}, Critical: {summary['critical_issues']}")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        # Assert no critical violations
        self.assertEqual(
            summary["critical_issues"],
            0,
            f"Critical audit violations found in engine report: {audit_result['details']}",
        )
        self.assertTrue(summary["passed_critical"])
        self.assertEqual(counts["significance_contradictions"], 0)
        self.assertEqual(counts["expert_review_claimed"], 0)


if __name__ == "__main__":
    unittest.main()
