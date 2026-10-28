import unittest
from unittest.mock import patch, MagicMock
from pubmed_client import parse_pubmed_xml, search_pubmed, verify_pmid, verify_doi

SAMPLE_PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">33264510</PMID>
      <Article PubModel="Print-Electronic">
        <Journal>
          <Title>The New England Journal of Medicine</Title>
          <JournalIssue>
            <PubDate>
              <Year>2020</Year>
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
        <ArticleId IdType="pubmed">33264510</ArticleId>
        <ArticleId IdType="doi">10.1056/NEJMoa2022190</ArticleId>
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
        self.assertEqual(art["pmid"], "33264510")
        self.assertEqual(art["title"], "Empagliflozin in Heart Failure with a Preserved Ejection Fraction")
        self.assertEqual(art["pub_year"], "2020")
        self.assertEqual(art["doi"], "10.1056/NEJMoa2022190")
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
                "idlist": ["33264510"]
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
        self.assertEqual(res["articles"][0]["pmid"], "33264510")

    @patch("requests.get")
    def test_verify_pmid_valid(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_PUBMED_XML
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = verify_pmid("33264510")
        self.assertTrue(res["valid"])
        self.assertEqual(res["pmid"], "33264510")
        self.assertEqual(res["doi"], "10.1056/NEJMoa2022190")

    def test_verify_pmid_invalid_format(self):
        res = verify_pmid("invalid_pmid_123abc")
        self.assertFalse(res["valid"])
        self.assertIn("yalnızca rakamlardan oluşmalıdır", res["error"])

    @patch("requests.get")
    def test_verify_doi_crossref_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "title": ["Empagliflozin Test Article"],
                "author": [{"given": "Stefan", "family": "Anker"}],
                "container-title": ["NEJM"],
                "published-print": {"date-parts": [[2020, 8, 27]]}
            }
        }
        mock_resp.raise_for_status.return_value = None

        # Also mock internal search_pubmed call inside verify_doi
        with patch("pubmed_client.search_pubmed") as mock_search:
            mock_search.return_value = {"articles": []}
            mock_get.return_value = mock_resp

            res = verify_doi("10.1056/NEJMoa2022190")
            self.assertTrue(res["valid"])
            self.assertEqual(res["doi"], "10.1056/NEJMoa2022190")
            self.assertEqual(res["title"], "Empagliflozin Test Article")


if __name__ == "__main__":
    unittest.main()
