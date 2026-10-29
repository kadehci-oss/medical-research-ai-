import unittest
from unittest.mock import patch, MagicMock
from pubmed_client import search_pubmed
from report_generator import generate_rule_based_turkish_report, perform_red_team_audit

SAMPLE_STATIN_PUBMED_XML_1 = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">37884200</PMID>
      <Article>
        <Journal>
          <Title>Autoimmunity reviews</Title>
          <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Anti-HMGCR immune-mediated necrotising myopathy: Addressing the remaining issues.</ArticleTitle>
        <Abstract>
          <AbstractText>The discovery of autoantibodies directed against HMGCR enzyme has defined a sub-set of immune-mediated necrotising myopathy strongly associated with statins.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Khoo</LastName><ForeName>Thomas</ForeName></Author>
          <Author><LastName>Chinoy</LastName><ForeName>Hector</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Review</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">37884200</ArticleId>
        <ArticleId IdType="doi">10.1016/j.autrev.2023.103468</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">23519993</PMID>
      <Article>
        <Journal>
          <Title>Muscle &amp; nerve</Title>
          <JournalIssue><PubDate><Year>2013</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Statin-associated autoimmune myopathy and anti-HMGCR autoantibodies.</ArticleTitle>
        <Abstract>
          <AbstractText>Anti-HMGCR antibodies differentiate self-limited statin myopathy from progressive statin-associated autoimmune myopathy requiring immunosuppressive therapy.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Mohassel</LastName><ForeName>Payam</ForeName></Author>
          <Author><LastName>Mammen</LastName><ForeName>Andrew L</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Review</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">23519993</ArticleId>
        <ArticleId IdType="doi">10.1002/mus.23854</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

SAMPLE_PMID_37884200_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">37884200</PMID>
      <Article>
        <Journal>
          <Title>Autoimmunity reviews</Title>
          <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Anti-HMGCR immune-mediated necrotising myopathy: Addressing the remaining issues.</ArticleTitle>
        <Abstract>
          <AbstractText>The discovery of autoantibodies directed against HMGCR enzyme has defined a sub-set of immune-mediated necrotising myopathy strongly associated with statins.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Khoo</LastName><ForeName>Thomas</ForeName></Author>
          <Author><LastName>Chinoy</LastName><ForeName>Hector</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Review</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">37884200</ArticleId>
        <ArticleId IdType="doi">10.1016/j.autrev.2023.103468</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

SAMPLE_PMID_23519993_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">23519993</PMID>
      <Article>
        <Journal>
          <Title>Muscle &amp; nerve</Title>
          <JournalIssue><PubDate><Year>2013</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Statin-associated autoimmune myopathy and anti-HMGCR autoantibodies.</ArticleTitle>
        <Abstract>
          <AbstractText>Anti-HMGCR antibodies differentiate self-limited statin myopathy from progressive statin-associated autoimmune myopathy requiring immunosuppressive therapy.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Mohassel</LastName><ForeName>Payam</ForeName></Author>
          <Author><LastName>Mammen</LastName><ForeName>Andrew L</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Review</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">23519993</ArticleId>
        <ArticleId IdType="doi">10.1002/mus.23854</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

class TestStatinMyopathyEndToEnd(unittest.TestCase):

    @patch("requests.get")
    def test_statin_myopathy_anti_hmgcr_e2e(self, mock_get):
        mock_esearch = MagicMock()
        mock_esearch.json.return_value = {
            "esearchresult": {
                "count": "2",
                "idlist": ["37884200", "23519993"]
            }
        }
        mock_esearch.raise_for_status.return_value = None

        mock_efetch_set = MagicMock()
        mock_efetch_set.text = SAMPLE_STATIN_PUBMED_XML_1
        mock_efetch_set.raise_for_status.return_value = None

        mock_efetch_37884200 = MagicMock()
        mock_efetch_37884200.text = SAMPLE_PMID_37884200_XML
        mock_efetch_37884200.raise_for_status.return_value = None

        mock_efetch_23519993 = MagicMock()
        mock_efetch_23519993.text = SAMPLE_PMID_23519993_XML
        mock_efetch_23519993.raise_for_status.return_value = None

        # 1. search_pubmed: esearch -> efetch_set
        # 2. perform_red_team_audit: verify_pmid(37884200) -> efetch_37884200, verify_pmid(23519993) -> efetch_23519993
        mock_get.side_effect = [
            mock_esearch,
            mock_efetch_set,
            mock_efetch_37884200,
            mock_efetch_23519993
        ]

        query = "Statin-associated muscle symptoms AND anti-HMGCR"

        # Perform PubMed search for statin myopathy and anti-HMGCR
        search_res = search_pubmed(query, max_results=5)
        articles = search_res.get("articles", [])

        self.assertEqual(len(articles), 2)

        audit = perform_red_team_audit(query, articles)
        self.assertEqual(audit["status"], "DENETLEME TAMAMLANDI (AUDIT COMPLETE)")
        self.assertEqual(audit["citation_integrity"]["rejected_citations"], 0)
        self.assertEqual(audit["citation_integrity"]["verified_citations"], 2)

        # Generate Turkish evidence synthesis report
        report = generate_rule_based_turkish_report(query, articles, search_metadata=search_res)

        # Validate all 13 mandatory clinical sections exist
        self.assertIn("1. Klinik Araştırma Sorusu", report)
        self.assertIn("2. Yönetici Özeti", report)
        self.assertIn("3. Araştırma Yöntemi ve Tarama Tarihi", report)
        self.assertIn("4. Klinik Arka Plan ve Patofizyoloji", report)
        self.assertIn("5. Bilimsel Kanıt Tablosu", report)
        self.assertIn("6. Önemli Çalışmaların Karşılaştırılması", report)
        self.assertIn("7. Tedavi Etkinliği ve Güvenlilik", report)
        self.assertIn("8. Güncel Klinik Kılavuzlar", report)
        self.assertIn("9. Çelişkili Bilimsel Bulgular", report)
        self.assertIn("10. Red Team Eleştirisi", report)
        self.assertIn("11. Kanıt Gücü ve Belirsizlikler", report)
        self.assertIn("12. Klinik Sonuç", report)
        self.assertIn("13. Doğrulanmış Kaynakça", report)

        # Verify key clinical concepts from real source PubMed data
        self.assertIn("anti-HMGCR", report, "Anti-HMGCR antibody term missing in report")
        self.assertIn("GRADE Değerlendirilmedi (Not Assessed)", report)
        self.assertIn("Klinik Doğrulama Yapılmamıştır", report)

        # Verify Section 12 contains specific PMID citations and Turkish clinical synthesis
        self.assertIn("[PMID: 37884200]", report)
        self.assertIn("[PMID: 23519993]", report)
        self.assertIn("nekrotizan miyopati", report.lower())

        # Ensure no false claims
        self.assertNotIn("100/100", report)
        self.assertNotIn("100 / 100", report)
        self.assertNotIn("0% (Sıfır)", report)

if __name__ == "__main__":
    unittest.main()
