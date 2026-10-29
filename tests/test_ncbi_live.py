import time
import unittest
from pubmed_client import search_pubmed, verify_pmid, verify_citation
from report_generator import (
    generate_rule_based_turkish_report,
    perform_red_team_audit,
    validate_clinical_report_quality
)


class TestNCBILiveAPI(unittest.TestCase):

    def setUp(self):
        time.sleep(0.5)
    """
    Live Integration Test Suite for NCBI PubMed ESearch & EFetch APIs.
    Performs real network HTTP requests against NCBI servers.
    """

    def test_live_ncbi_esearch_and_efetch(self):
        query = "statin myopathy anti-HMGCR"
        res = search_pubmed(query, max_results=5)

        self.assertNotIn("error", res, f"Live NCBI PubMed search failed with error: {res.get('error')}")
        self.assertGreater(res.get("total_count", 0), 0, "Live ESearch returned 0 total count.")
        articles = res.get("articles", [])
        self.assertGreater(len(articles), 0, "Live EFetch returned 0 articles.")

        first_art = articles[0]
        self.assertTrue(first_art.get("pmid").isdigit(), f"Invalid PMID: {first_art.get('pmid')}")
        self.assertTrue(len(first_art.get("title", "")) > 5, "Article title is too short or missing.")
        self.assertTrue(len(first_art.get("authors", [])) > 0, "Authors list is empty.")
        self.assertTrue(first_art.get("pubmed_url").startswith("https://pubmed.ncbi.nlm.nih.gov/"))

    def test_live_ncbi_verify_pmid(self):
        pmid = "34449189"
        res = verify_pmid(pmid)

        self.assertTrue(res.get("valid"), f"Live verify_pmid failed for PMID {pmid}: {res.get('error')}")
        self.assertEqual(res.get("pmid"), "34449189")
        self.assertIn("Empagliflozin", res.get("title", ""))
        self.assertEqual(res.get("doi"), "10.1056/NEJMoa2107038")

    def test_live_ncbi_verify_citation_match(self):
        citation = {
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "doi": "10.1056/NEJMoa2107038"
        }
        res = verify_citation(citation)

        self.assertEqual(res.get("status"), "verified")
        self.assertTrue(res.get("verified"))
        self.assertEqual(res.get("reason"), "match")

    def test_live_ncbi_end_to_end_report_quality_control(self):
        query = "empagliflozin heart failure"
        search_res = search_pubmed(query, max_results=3)
        articles = search_res.get("articles", [])
        self.assertGreater(len(articles), 0, "No articles returned for e2e live report test.")

        report = generate_rule_based_turkish_report(query, articles, search_metadata=search_res)
        qc = validate_clinical_report_quality(report)

        self.assertTrue(qc.get("valid"), f"Live clinical report quality control failed: missing={qc.get('missing_sections')}, false_claims={qc.get('detected_false_claims')}")
        self.assertEqual(len(qc.get("missing_sections", [])), 0)
        self.assertEqual(len(qc.get("detected_false_claims", [])), 0)

        audit = perform_red_team_audit(query, articles)
        self.assertEqual(audit.get("status"), "DENETLEME TAMAMLANDI (AUDIT COMPLETE)")
        self.assertIn("Yapılmadı", audit.get("expert_physician_evaluation", ""))
        self.assertEqual(audit.get("physician_review_status"), "Tamamlanmadı (Not Completed)")


if __name__ == "__main__":
    unittest.main()
