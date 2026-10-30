import os
import unittest
from unittest.mock import patch, MagicMock
from pubmed_client import (
    parse_pubmed_xml,
    search_pubmed,
    verify_pmid,
    verify_doi,
    normalize_title,
    normalize_doi,
    verify_citation,
    ncbi_request_headers,
    eutils_identity_params,
)

SAMPLE_PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">34449189</PMID>
      <Article PubModel="Print-Electronic">
        <Journal>
          <Title>The New England Journal of Medicine</Title>
          <JournalIssue>
            <PubDate>
              <Year>2021</Year>
            </PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Empagliflozin in Heart Failure with a Preserved Ejection Fraction</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">SGLT2 inhibitors reduce the risk of hospitalization in heart failure.</AbstractText>
          <AbstractText Label="CONCLUSIONS">Empagliflozin reduced the combined risk of cardiovascular death or hospitalization for heart failure.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Anker</LastName>
            <ForeName>Stefan D</ForeName>
          </Author>
          <Author ValidYN="Y">
            <LastName>Butler</LastName>
            <ForeName>Javed</ForeName>
          </Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType UI="D016428">Journal Article</PublicationType>
          <PublicationType UI="D016449">Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">34449189</ArticleId>
        <ArticleId IdType="doi">10.1056/NEJMoa2107038</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

class TestPubMedClient(unittest.TestCase):

    def test_parse_pubmed_xml(self):
        articles = parse_pubmed_xml(SAMPLE_PUBMED_XML)
        self.assertEqual(len(articles), 1)
        art = articles[0]
        self.assertEqual(art["pmid"], "34449189")
        self.assertEqual(art["title"], "Empagliflozin in Heart Failure with a Preserved Ejection Fraction")
        self.assertEqual(art["pub_year"], "2021")
        self.assertEqual(art["doi"], "10.1056/NEJMoa2107038")
        self.assertIn("Stefan D Anker", art["authors"])
        self.assertIn("Javed Butler", art["authors"])
        self.assertIn("BACKGROUND: SGLT2 inhibitors", art["abstract"])

    @patch("requests.get")
    def test_search_pubmed_success(self, mock_get):
        # Mock esearch response then efetch response
        mock_esearch_resp = MagicMock()
        mock_esearch_resp.json.return_value = {
            "esearchresult": {
                "count": "1",
                "idlist": ["34449189"]
            }
        }
        mock_esearch_resp.raise_for_status.return_value = None

        mock_efetch_resp = MagicMock()
        mock_efetch_resp.text = SAMPLE_PUBMED_XML
        mock_efetch_resp.raise_for_status.return_value = None

        mock_get.side_effect = [mock_esearch_resp, mock_efetch_resp]

        res = search_pubmed("empagliflozin", max_results=5)
        self.assertEqual(res["total_count"], 1)
        self.assertEqual(len(res["articles"]), 1)
        self.assertEqual(res["articles"][0]["pmid"], "34449189")
        self.assertIn("search_date", res)
        self.assertIn("search_params", res)

    @patch("requests.get")
    def test_search_pubmed_deduplication(self, mock_get):
        # XML containing 2 identical articles with same PMID
        DUPLICATE_PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation Status="MEDLINE"><PMID Version="1">10001</PMID>
              <Article><ArticleTitle>Dup Paper</ArticleTitle></Article>
            </MedlineCitation>
          </PubmedArticle>
          <PubmedArticle>
            <MedlineCitation Status="MEDLINE"><PMID Version="1">10001</PMID>
              <Article><ArticleTitle>Dup Paper</ArticleTitle></Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""

        mock_esearch = MagicMock()
        mock_esearch.json.return_value = {"esearchresult": {"count": "2", "idlist": ["10001", "10001"]}}
        mock_efetch = MagicMock()
        mock_efetch.text = DUPLICATE_PUBMED_XML

        mock_get.side_effect = [mock_esearch, mock_efetch]

        res = search_pubmed("duplicate query")
        self.assertEqual(len(res["articles"]), 1)
        self.assertEqual(res["articles"][0]["pmid"], "10001")

    @patch("requests.get")
    def test_search_pubmed_api_error(self, mock_get):
        mock_esearch_resp = MagicMock()
        mock_esearch_resp.json.return_value = {
            "esearchresult": {
                "ERROR": "Invalid search term"
            }
        }
        mock_esearch_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_esearch_resp

        res = search_pubmed("invalid_term")
        self.assertIn("error", res)
        self.assertEqual(res["error"], "Invalid search term")

    @patch("requests.get")
    def test_search_pubmed_network_exception(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")

        res = search_pubmed("diabetes")
        self.assertIn("error", res)
        self.assertEqual(res["error"], "Connection timeout")

    @patch("requests.get")
    def test_verify_pmid_valid(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_PUBMED_XML
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = verify_pmid("34449189")
        self.assertTrue(res["valid"])
        self.assertEqual(res["pmid"], "34449189")
        self.assertEqual(res["doi"], "10.1056/NEJMoa2107038")

    def test_verify_pmid_invalid_format(self):
        res = verify_pmid("invalid_pmid_123abc")
        self.assertFalse(res["valid"])
        self.assertIn("yalnızca rakamlardan oluşmalıdır", res["error"])

    def test_normalize_title(self):
        self.assertEqual(normalize_title(" <b>Empagliflozin</b> in Heart Failure! "), "empagliflozin in heart failure")
        self.assertEqual(normalize_title(None), "")

    def test_normalize_doi(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1056/NEJMoa2107038 "), "10.1056/nejmoa2107038")
        self.assertEqual(normalize_doi("doi: 10.1056/NEJMoa2107038"), "10.1056/nejmoa2107038")
        self.assertEqual(normalize_doi(None), "")

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_valid_match(self, mock_verify_pmid):
        mock_verify_pmid.return_value = {
            "valid": True,
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "doi": "10.1056/NEJMoa2107038"
        }

        citation = {
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "doi": "10.1056/NEJMoa2107038"
        }

        res = verify_citation(citation)
        self.assertEqual(res["status"], "verified")
        self.assertTrue(res["verified"])
        self.assertEqual(res["reason"], "match")

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_title_mismatch_rejection(self, mock_verify_pmid):
        mock_verify_pmid.return_value = {
            "valid": True,
            "pmid": "34449189",
            "title": "Real PubMed Title Here",
            "doi": "10.1056/NEJMoa2107038"
        }

        citation = {
            "pmid": "34449189",
            "title": "Fabricated Title Mismatch",
            "doi": "10.1056/NEJMoa2107038"
        }

        res = verify_citation(citation)
        self.assertEqual(res["status"], "rejected")
        self.assertFalse(res["verified"])
        self.assertEqual(res["reason"], "title_mismatch")
        self.assertIn("Başlık uyuşmazlığı nedeniyle reddedildi", res["error"])

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_doi_mismatch_rejection(self, mock_verify_pmid):
        mock_verify_pmid.return_value = {
            "valid": True,
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure",
            "doi": "10.1056/NEJMoa2107038"
        }

        citation = {
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure",
            "doi": "10.9999/wrong-doi"
        }

        res = verify_citation(citation)
        self.assertEqual(res["status"], "rejected")
        self.assertFalse(res["verified"])
        self.assertEqual(res["reason"], "doi_mismatch")
        self.assertIn("DOI uyuşmazlığı nedeniyle reddedildi", res["error"])

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_api_failure_unverified(self, mock_verify_pmid):
        mock_verify_pmid.return_value = {
            "valid": False,
            "pmid": "34449189",
            "error": "Doğrulama sırasında hata oluştu: Connection timeout"
        }

        citation = {
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure"
        }

        res = verify_citation(citation)
        self.assertEqual(res["status"], "unverified")
        self.assertFalse(res["verified"])
        self.assertEqual(res["reason"], "api_failure")

    def test_verify_citation_invalid_pmid_rejection(self):
        res = verify_citation({"pmid": "abc"})
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["reason"], "missing_or_invalid_pmid")

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_not_found_rejection(self, mock_verify_pmid):
        mock_verify_pmid.return_value = {
            "valid": False,
            "pmid": "999999999",
            "error": "PMID 999999999 PubMed veritabanında bulunamadı."
        }

        citation = {
            "pmid": "999999999",
            "title": "Non-existent Paper Title"
        }

        res = verify_citation(citation)
        self.assertEqual(res["status"], "rejected")
        self.assertFalse(res["verified"])
        self.assertEqual(res["reason"], "not_found")

    def test_verify_citation_auto_rejection_regression(self):
        """Regression test ensuring mismatched titles, DOIs, and non-existent PMIDs are strictly auto-rejected."""
        # 1. Invalid PMID non-numeric
        res_invalid_pmid = verify_citation({"pmid": "PMID12345XYZ", "title": "Some Title"})
        self.assertEqual(res_invalid_pmid["status"], "rejected")
        self.assertFalse(res_invalid_pmid["verified"])
        self.assertEqual(res_invalid_pmid["reason"], "missing_or_invalid_pmid")

        # 2. Empty or non-dict input
        res_empty = verify_citation(None)
        self.assertEqual(res_empty["status"], "rejected")
        self.assertFalse(res_empty["verified"])
        self.assertEqual(res_empty["reason"], "invalid_input")

    @patch("pubmed_client.verify_pmid")
    def test_verify_citation_mismatch_auto_rejection_regression(self, mock_verify_pmid):
        # Mock PMID lookup returns real article data
        mock_verify_pmid.return_value = {
            "valid": True,
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "doi": "10.1056/NEJMoa2107038"
        }

        # Case A: Title mismatch
        bad_title = verify_citation({
            "pmid": "34449189",
            "title": "Fabricated Title About Diabetes Insipidus",
            "doi": "10.1056/NEJMoa2107038"
        })
        self.assertEqual(bad_title["status"], "rejected")
        self.assertFalse(bad_title["verified"])
        self.assertEqual(bad_title["reason"], "title_mismatch")

        # Case B: DOI mismatch
        bad_doi = verify_citation({
            "pmid": "34449189",
            "title": "Empagliflozin in Heart Failure with a Preserved Ejection Fraction",
            "doi": "10.1000/fabricated-doi"
        })
        self.assertEqual(bad_doi["status"], "rejected")
        self.assertFalse(bad_doi["verified"])
        self.assertEqual(bad_doi["reason"], "doi_mismatch")

    @patch("requests.get")
    def test_verify_doi_crossref_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "title": ["Empagliflozin Test Article"],
                "author": [{"given": "Stefan", "family": "Anker"}],
                "container-title": ["NEJM"],
                "published-print": {"date-parts": [[2021, 8, 27]]}
            }
        }
        mock_resp.raise_for_status.return_value = None

        # Also mock internal search_pubmed call inside verify_doi
        with patch("pubmed_client.search_pubmed") as mock_search:
            mock_search.return_value = {"articles": []}
            mock_get.return_value = mock_resp

            res = verify_doi("10.1056/NEJMoa2107038")
            self.assertTrue(res["valid"])
            self.assertEqual(res["doi"], "10.1056/NEJMoa2107038")
            self.assertEqual(res["title"], "Empagliflozin Test Article")
            sent_headers = mock_get.call_args.kwargs["headers"]
            self.assertNotIn("api_key", sent_headers)
            self.assertIn("mailto:", sent_headers["User-Agent"])

    def test_eutils_identity_uses_env_and_omits_empty_api_key(self):
        """NCBI tool, email, and api_key come from the environment."""
        with patch.dict(
            os.environ,
            {
                "NCBI_TOOL": "LabTool",
                "NCBI_EMAIL": "lab-contact@example.com",
                "NCBI_API_KEY": "  ",
            },
            clear=False,
        ):
            params = eutils_identity_params()
            self.assertEqual(params["tool"], "LabTool")
            self.assertEqual(params["email"], "lab-contact@example.com")
            self.assertNotIn("api_key", params)
            self.assertEqual(
                ncbi_request_headers()["User-Agent"],
                "LabTool/1.0 (mailto:lab-contact@example.com)",
            )

        with patch.dict(os.environ, {"NCBI_TOOL": "", "NCBI_EMAIL": "", "NCBI_API_KEY": ""}, clear=False):
            params = eutils_identity_params()
            self.assertEqual(params["tool"], "MedicalResearchAI")
            self.assertEqual(params["email"], "medical-research-ai@example.com")
            self.assertNotIn("api_key", params)
            self.assertNotIn("medical_ai_app@example.com", ncbi_request_headers()["User-Agent"])

    @patch("requests.get")
    def test_search_pubmed_sends_tool_email_and_api_key(self, mock_get):
        """esearch and efetch both receive tool, email, and api_key."""
        mock_esearch_resp = MagicMock()
        mock_esearch_resp.json.return_value = {
            "esearchresult": {"count": "1", "idlist": ["34449189"]}
        }
        mock_esearch_resp.raise_for_status.return_value = None
        mock_efetch_resp = MagicMock()
        mock_efetch_resp.text = SAMPLE_PUBMED_XML
        mock_efetch_resp.raise_for_status.return_value = None
        mock_get.side_effect = [mock_esearch_resp, mock_efetch_resp]

        with patch.dict(
            os.environ,
            {
                "NCBI_TOOL": "LabTool",
                "NCBI_EMAIL": "lab-contact@example.com",
                "NCBI_API_KEY": "test-ncbi-key",
            },
            clear=False,
        ):
            res = search_pubmed("empagliflozin", max_results=1)

        self.assertEqual(res["articles"][0]["pmid"], "34449189")
        self.assertEqual(mock_get.call_count, 2)
        for call in mock_get.call_args_list:
            params = call.kwargs["params"]
            headers = call.kwargs["headers"]
            self.assertEqual(params["tool"], "LabTool")
            self.assertEqual(params["email"], "lab-contact@example.com")
            self.assertEqual(params["api_key"], "test-ncbi-key")
            self.assertEqual(headers["User-Agent"], "LabTool/1.0 (mailto:lab-contact@example.com)")


if __name__ == "__main__":
    unittest.main()
