import unittest
from unittest.mock import patch, MagicMock
from universal_evidence_engine import UniversalEvidenceEngine
from pubmed_client import search_pubmed
from report_generator import generate_rule_based_turkish_report, perform_red_team_audit

EMPAGLIFLOZIN_34449189_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">34449189</PMID>
      <Article>
        <Journal>
          <Title>The New England journal of medicine</Title>
          <JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Empagliflozin in Heart Failure with a Preserved Ejection Fraction.</ArticleTitle>
        <Abstract>
          <AbstractText>BACKGROUND: SGLT2 inhibitors reduce the risk of hospitalization for heart failure in patients with heart failure and a reduced ejection fraction, but their effects in patients with heart failure and a preserved ejection fraction are unclear.
METHODS: In this double-blind trial, we randomly assigned 5988 patients with class II-IV heart failure and an ejection fraction of more than 40% to receive empagliflozin (10 mg once daily) or placebo. The primary outcome was a composite of cardiovascular death or hospitalization for heart failure.
RESULTS: Over a median of 26.2 months, the primary outcome occurred in 415 of 2997 patients (13.8%) in the empagliflozin group and in 511 of 2991 patients (17.1%) in the placebo group (hazard ratio, 0.79; 95% confidence interval [CI], 0.69 to 0.90; p &lt; 0.001). This effect was mainly related to a lower risk of hospitalization for heart failure in the empagliflozin group.
CONCLUSIONS: Empagliflozin reduced the combined risk of cardiovascular death or hospitalization for heart failure in patients with heart failure and a preserved ejection fraction, regardless of the presence or absence of diabetes.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Anker</LastName><ForeName>Stefan D</ForeName></Author>
          <Author><LastName>Butler</LastName><ForeName>Javed</ForeName></Author>
          <Author><LastName>Filippatos</LastName><ForeName>Gerasimos</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">34449189</ArticleId>
        <ArticleId IdType="doi">10.1056/nejmoa2107038</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

DAPAGLIFLOZIN_31535829_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">31535829</PMID>
      <Article>
        <Journal>
          <Title>The New England journal of medicine</Title>
          <JournalIssue><PubDate><Year>2019</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction.</ArticleTitle>
        <Abstract>
          <AbstractText>BACKGROUND: In patients with type 2 diabetes, SGLT2 inhibitors reduce the risk of hospitalization for heart failure. However, data are needed regarding the efficacy and safety of SGLT2 inhibitors in patients with heart failure, regardless of the presence or absence of diabetes.
METHODS: In this phase 3, double-blind trial, we randomly assigned 4744 patients with New York Heart Association class II, III, or IV heart failure and an ejection fraction of 40% or less to receive either dapagliflozin (10 mg once daily) or placebo. The primary outcome was a composite of worsening heart failure or cardiovascular death.
RESULTS: Over a median of 18.2 months, the primary outcome occurred in 386 of 2373 patients (16.3%) in the dapagliflozin group and in 502 of 2371 patients (21.2%) in the placebo group (hazard ratio, 0.74; 95% confidence interval [CI], 0.65 to 0.85; p &lt; 0.001). A first worsening heart failure event occurred in 237 patients (10.0%) in the dapagliflozin group and in 326 patients (13.7%) in the placebo group (hazard ratio, 0.70; 95% CI, 0.59 to 0.83). Death from cardiovascular causes occurred in 227 patients (9.6%) in the dapagliflozin group and in 273 patients (11.5%) in the placebo group (hazard ratio, 0.82; 95% CI, 0.69 to 0.98).
CONCLUSIONS: Among patients with heart failure and a reduced ejection fraction, the risk of worsening heart failure or death from cardiovascular causes was lower among those who received dapagliflozin than among those who received placebo, regardless of the presence or absence of diabetes.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>McMurray</LastName><ForeName>John J V</ForeName></Author>
          <Author><LastName>Solomon</LastName><ForeName>Scott D</ForeName></Author>
          <Author><LastName>Inzucchi</LastName><ForeName>Silvio E</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">31535829</ArticleId>
        <ArticleId IdType="doi">10.1056/nejmoa1911303</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

COMBINED_SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">34449189</PMID>
      <Article>
        <Journal>
          <Title>The New England journal of medicine</Title>
          <JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Empagliflozin in Heart Failure with a Preserved Ejection Fraction.</ArticleTitle>
        <Abstract>
          <AbstractText>BACKGROUND: SGLT2 inhibitors reduce the risk of hospitalization for heart failure in patients with heart failure and a reduced ejection fraction, but their effects in patients with heart failure and a preserved ejection fraction are unclear.
METHODS: In this double-blind trial, we randomly assigned 5988 patients with class II-IV heart failure and an ejection fraction of more than 40% to receive empagliflozin (10 mg once daily) or placebo. The primary outcome was a composite of cardiovascular death or hospitalization for heart failure.
RESULTS: Over a median of 26.2 months, the primary outcome occurred in 415 of 2997 patients (13.8%) in the empagliflozin group and in 511 of 2991 patients (17.1%) in the placebo group (hazard ratio, 0.79; 95% confidence interval [CI], 0.69 to 0.90; p &lt; 0.001). This effect was mainly related to a lower risk of hospitalization for heart failure in the empagliflozin group.
CONCLUSIONS: Empagliflozin reduced the combined risk of cardiovascular death or hospitalization for heart failure in patients with heart failure and a preserved ejection fraction, regardless of the presence or absence of diabetes.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>Anker</LastName><ForeName>Stefan D</ForeName></Author>
          <Author><LastName>Butler</LastName><ForeName>Javed</ForeName></Author>
          <Author><LastName>Filippatos</LastName><ForeName>Gerasimos</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">34449189</ArticleId>
        <ArticleId IdType="doi">10.1056/nejmoa2107038</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">31535829</PMID>
      <Article>
        <Journal>
          <Title>The New England journal of medicine</Title>
          <JournalIssue><PubDate><Year>2019</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction.</ArticleTitle>
        <Abstract>
          <AbstractText>BACKGROUND: In patients with type 2 diabetes, SGLT2 inhibitors reduce the risk of hospitalization for heart failure. However, data are needed regarding the efficacy and safety of SGLT2 inhibitors in patients with heart failure, regardless of the presence or absence of diabetes.
METHODS: In this phase 3, double-blind trial, we randomly assigned 4744 patients with New York Heart Association class II, III, or IV heart failure and an ejection fraction of 40% or less to receive either dapagliflozin (10 mg once daily) or placebo. The primary outcome was a composite of worsening heart failure or cardiovascular death.
RESULTS: Over a median of 18.2 months, the primary outcome occurred in 386 of 2373 patients (16.3%) in the dapagliflozin group and in 502 of 2371 patients (21.2%) in the placebo group (hazard ratio, 0.74; 95% confidence interval [CI], 0.65 to 0.85; p &lt; 0.001). A first worsening heart failure event occurred in 237 patients (10.0%) in the dapagliflozin group and in 326 patients (13.7%) in the placebo group (hazard ratio, 0.70; 95% CI, 0.59 to 0.83). Death from cardiovascular causes occurred in 227 patients (9.6%) in the dapagliflozin group and in 273 patients (11.5%) in the placebo group (hazard ratio, 0.82; 95% CI, 0.69 to 0.98).
CONCLUSIONS: Among patients with heart failure and a reduced ejection fraction, the risk of worsening heart failure or death from cardiovascular causes was lower among those who received dapagliflozin than among those who received placebo, regardless of the presence or absence of diabetes.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author><LastName>McMurray</LastName><ForeName>John J V</ForeName></Author>
          <Author><LastName>Solomon</LastName><ForeName>Scott D</ForeName></Author>
          <Author><LastName>Inzucchi</LastName><ForeName>Silvio E</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">31535829</ArticleId>
        <ArticleId IdType="doi">10.1056/nejmoa1911303</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class TestRealPubMedE2E(unittest.TestCase):

    @patch("requests.get")
    def test_real_pubmed_articles_e2e_synthesis(self, mock_get):
        mock_esearch = MagicMock()
        mock_esearch.json.return_value = {
            "esearchresult": {
                "count": "2",
                "idlist": ["34449189", "31535829"]
            }
        }
        mock_esearch.raise_for_status.return_value = None

        mock_efetch_set = MagicMock()
        mock_efetch_set.text = COMBINED_SEARCH_XML
        mock_efetch_set.raise_for_status.return_value = None

        mock_efetch_34449189 = MagicMock()
        mock_efetch_34449189.text = EMPAGLIFLOZIN_34449189_XML
        mock_efetch_34449189.raise_for_status.return_value = None

        mock_efetch_31535829 = MagicMock()
        mock_efetch_31535829.text = DAPAGLIFLOZIN_31535829_XML
        mock_efetch_31535829.raise_for_status.return_value = None

        mock_get.side_effect = [
            mock_esearch,
            mock_efetch_set,
            mock_efetch_34449189,
            mock_efetch_31535829
        ]

        query = "SGLT2 inhibitors in heart failure"

        engine = UniversalEvidenceEngine()
        search_res = engine.search_and_verify(
            query=query,
            max_results=5,
            prefer_high_level_evidence=False,
        )
        articles = search_res.get("articles", [])

        self.assertEqual(len(articles), 2)
        pmids = [a.get("pmid") for a in articles]
        self.assertIn("34449189", pmids)
        self.assertIn("31535829", pmids)

        synthesis_res = engine.generate_synthesis_report(query=query, articles=articles)
        self.assertEqual(synthesis_res.get("status"), "success")

        report_md = synthesis_res.get("report_markdown", "")
        cross_comp = synthesis_res.get("cross_comparison", {})

        # Assert correct PMID links in report
        self.assertIn("[PMID: 34449189]", report_md)
        self.assertIn("[PMID: 31535829]", report_md)
        self.assertIn("https://pubmed.ncbi.nlm.nih.gov/34449189/", report_md)
        self.assertIn("https://pubmed.ncbi.nlm.nih.gov/31535829/", report_md)

        # Assert cross-comparison structure
        ind_summaries = cross_comp.get("individual_article_summaries", [])
        self.assertEqual(len(ind_summaries), 2)

        summary_34449189 = next((s for s in ind_summaries if s.get("pmid") == "34449189"), None)
        summary_31535829 = next((s for s in ind_summaries if s.get("pmid") == "31535829"), None)

        self.assertIsNotNone(summary_34449189)
        self.assertIsNotNone(summary_31535829)

        # Validate extracted sample sizes n
        self.assertEqual(summary_34449189.get("sample_size_n"), "5988")
        self.assertEqual(summary_31535829.get("sample_size_n"), "4744")

        # Validate extracted metrics (HR 0.79 and HR 0.74)
        om_34449189 = summary_34449189.get("outcome_metrics", [])
        om_31535829 = summary_31535829.get("outcome_metrics", [])

        self.assertTrue(any("0.79" in str(m.get("metrics")) for m in om_34449189))
        self.assertTrue(any("0.74" in str(m.get("metrics")) for m in om_31535829))

        # Check all 13 sections in generated report
        for sec_num in range(1, 14):
            self.assertIn(f"{sec_num}.", report_md)

        # Ensure no hallucination or exaggerated guarantees
        self.assertNotIn("100/100", report_md)
        self.assertNotIn("0% (Sıfır)", report_md)


if __name__ == "__main__":
    unittest.main()
