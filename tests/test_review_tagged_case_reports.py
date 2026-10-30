"""Offline regression: a generic PubMed Review tag must not hide a case report.

Metadata was recorded from PubMed EFetch MedlineCitation fields
(publication types, title, abstract, authors, journal, year, DOI).
This module does not call the network.
"""
import unittest

from report_generator import classify_study_design

# Recorded PubMed metadata. Publication types are the NLM labels as returned;
# PMID 33372889 and PMID 41458822 are both tagged Review, and the title or
# abstract has to decide between a case report and a systematic review.
RECORDED_ARTICLES = [
    {
        "pmid": "33372889",
        "title": "A case of statin-associated immune-mediated necrotizing myopathy with atypical biopsy features.",
        "authors": [
            "Mark M Zaki",
            "Zain M Virk",
            "Diego Lopez",
            "Jenna Klubnick",
            "Jared T Ahrendsen",
            "Hemant Varma",
            "Vasileios Kyttaris",
            "Ilana Abeles"
        ],
        "journal": "European journal of rheumatology",
        "pub_year": "2021",
        "publication_types": [
            "Journal Article",
            "Review"
        ],
        "doi": "10.5152/eurjrheum.2020.20064",
        "abstract": "Statin-associated immune-mediated necrotizing myopathy (IMNM) is a rare presentation of a statin-associated myopathy. Patients usually present with muscle weakness and pain in the setting of statin use with elevated creatine kinase (CK) levels and a positive anti-3-hydroxy-3-methylglutaryl-coenzyme A reductase (anti-HMGCR) antibody. Muscle biopsies typically show necrosis, CD68+ macrophages, and minimal lymphocytes. We present a case of a 67-year-old woman who had 2 months of progressive weakness and bilateral lower extremity pain after initiating atorvastatin therapy with symptoms persisting after statin cessation. She was found to have high anti-HMGCR antibody titers, and the biopsy of the rectus femoris muscle showed a prominent endomysial inflammatory cell infiltrate with necrotic and regenerative fibers and an atypical extensive inflammatory infiltrate composed of both CD4+ helper T cells and CD8+ cytotoxic T cells. She showed symptom resolution and normalization of CK levels and inflammatory markers with treatment involving a prolonged prednisone taper and a brief course of azathioprine, which was stopped because of the adverse effects."
    },
    {
        "pmid": "35955495",
        "title": "Statins Neuromuscular Adverse Effects.",
        "authors": [
            "Silvia Attardo",
            "Olimpia Musumeci",
            "Daniele Velardo",
            "Antonio Toscano"
        ],
        "journal": "International journal of molecular sciences",
        "pub_year": "2022",
        "publication_types": [
            "Journal Article",
            "Review"
        ],
        "doi": "10.3390/ijms23158364",
        "abstract": "Statins are drugs widely prescribed in high-risk patients for cerebrovascular or cardiovascular diseases and are, usually, safe and well tolerated. However, these drugs sometimes may cause neuromuscular side effects that represent about two-third of all adverse events. Muscle-related adverse events include cramps, myalgia, weakness, immune-mediated necrotizing myopathy and, more rarely, rhabdomyolysis. Moreover, they may lead to peripheral neuropathy and induce or unmask a preexisting neuromuscular junction dysfunction. A clinical follow up of patients assuming statins could reveal early side effects that may cause neuromuscular damage and suggest how to better modulate their use. In fact, statin dechallenge or cessation, or the alternative use of other lipid-lowering agents, can avoid adverse events. This review summarizes the current knowledge on statin-associated neuromuscular adverse effects, diagnosis, and management. It is conceivable that the incidence of neuromuscular complications will increase because, nowadays, use of statins is even more diffused than in the past. On this purpose, it is expected that pharmacogenomic and environmental studies will help to timely predict neuromuscular complications due to statin exposure, leading to a more personalized therapeutic approach."
    },
    {
        "pmid": "28207435",
        "title": "Statin-associated immune-mediated myopathy: biology and clinical implications.",
        "authors": [
            "Lisa Christopher-Stine",
            "Pari Basharat"
        ],
        "journal": "Current opinion in lipidology",
        "pub_year": "2017",
        "publication_types": [
            "Journal Article",
            "Review"
        ],
        "doi": "10.1097/MOL.0000000000000399",
        "abstract": "PURPOSE OF REVIEW: In the last 6 years, our understanding of statin-associated myopathy expanded to include not only a toxic myopathy with limited and reversible side-effects but also an autoimmune variety in which statins likely induce an autoimmune myopathy that is both associated with a specific autoantibody and responsive to immunosuppression and immune modulation. This review widens the reader's understanding of statin myopathy to include an autoimmune process.\n\nRECENT FINDINGS: Statin-associated immune-mediated myopathy provides an example of an environmental trigger (statins) directly implicated in an autoimmune disease associated with a genetic predisposition as well as potential risk factors including concomitant diseases and specific statins. Given a median exposure to statins of 38 months, providers should be aware that anti-3-hydroxy-3-methyl-glutaryl-coenzyme A reductase (HMGCR) myopathy may occur even after several years of statin exposure.\n\nSUMMARY: It is important for the reader to understand the clinical presentation of statin-associated immune-mediated myopathy and the difference in its clinical presentation to that of statins as direct myotoxins. Prompt recognition of such an entity allows the clinician to immediately stop the offending agent if it has not already been discontinued as well as to recognize that statin rechallenge is not a likely option, and that prompt treatment with immunosuppression and/or immunomodulation is usually of enormous benefit to the patient in restoring muscle strength and physical function. VIDEO ABSTRACT."
    },
    {
        "pmid": "32581543",
        "title": "Statin-Associated Autoimmune Myopathy: Current Perspectives.",
        "authors": [
            "Eleni Tiniakou"
        ],
        "journal": "Therapeutics and clinical risk management",
        "pub_year": "2020",
        "publication_types": [
            "Journal Article",
            "Review"
        ],
        "doi": "10.2147/TCRM.S197941",
        "abstract": "Although generally well tolerated, statin users frequently report muscle-related side effects, ranging from self-limiting myalgias to rhabdomyolysis or the rare clinical entity of statin-associated immune-mediated necrotizing myopathy (IMNM). Statin-associated IMNM is based on the development of autoantibodies against 3-hydroxy-3-methylglutaryl-CoA reductase (HMGCR), the rate-limiting enzyme in cholesterol synthesis and the pharmacologic target of statins, and leads to a necrotizing myopathy requiring immunosuppressive therapy. This review attempts to recapitulate the diverse aspects of anti-HMGCR IMNM, including clinical presentation, diagnostic modalities, genetic risk associations, therapeutic options and potential pathogenetic pathways."
    },
    {
        "pmid": "41458822",
        "title": "Immune-Mediated Necrotizing Myopathy: A Systematic Review of Antibody-Specific Mechanisms and Treatment Outcomes.",
        "authors": [
            "Zahra Vaezi",
            "Afshin Amini"
        ],
        "journal": "Cureus",
        "pub_year": "2025",
        "publication_types": [
            "Journal Article",
            "Review"
        ],
        "doi": "10.7759/cureus.97933",
        "abstract": "Immune-mediated necrotizing myopathy (IMNM) is a rare, antibody-defined subset of idiopathic inflammatory myopathies characterized by rapidly progressive proximal muscle weakness, markedly elevated creatine kinase (CK) levels, and myofiber necrosis with minimal lymphocytic infiltration. Two major autoantibody subtypes-anti-3-hydroxy-3-methylglutaryl-coenzyme A reductase (anti-HMGCR) and anti-signal recognition particle (anti-SRP)-define distinct clinical phenotypes, pathophysiologic mechanisms, and treatment responses. Despite growing recognition, optimal management strategies remain uncertain. Following PRISMA 2020 and MOOSE guidelines, PubMed, Scopus, Web of Science, and Embase were systematically searched for studies published between January 2011 and May 2025 using terms related to \"immune-mediated necrotizing myopathy,\" \"anti-HMGCR,\" and \"anti-SRP\". Eligible publications included biopsy-confirmed IMNM cases with antibody documentation and treatment or outcome data. Data extraction encompassed clinical features, immunopathology, therapeutic interventions, and relapse rates. Methodological quality was evaluated using the Joanna Briggs Institute (JBI) Checklist, NIH Quality Assessment Tool, Newcastle-Ottawa Scale (NOS), and ROBINS-I, depending on study design. Eighty-eight studies (n ≈ 230 patients) met the inclusion criteria. Anti-HMGCR IMNM typically affected middle-aged adults and was frequently associated with statin exposure, while anti-SRP IMNM presented at younger ages with more severe and treatment-refractory disease. Corticosteroids and IVIG were the most commonly used first-line agents, with additional benefit from steroid-sparing immunosuppressants (mycophenolate, azathioprine, methotrexate). Rituximab and other B-cell-targeted biologics achieved remission in approximately 60-70% of refractory cases, and emerging complement or FcRn-directed therapies showed early promise. Relapse occurred in 25-35% of cases, most often after tapering corticosteroids or immunosuppressants. Overall methodological quality was moderate to high, with 82% of studies meeting ≥75% of appraisal criteria across risk-of-bias domains. IMNM demonstrates antibody-specific differences in clinical course, therapeutic response, and prognosis. Early, aggressive, and combination immunotherapy improves outcomes, while novel biologic agents may benefit refractory disease. The overall certainty of evidence is moderate, supporting current management strategies yet underscoring the need for standardized diagnostic criteria and prospective multicenter studies to refine treatment algorithms and identify biomarkers of durable remission."
    }
]

_EXPECTED = {
    "33372889": ("case_report", "Olgu Sunumu"),
    "35955495": ("narrative_review", "Niteliksel Derleme / Uzman Görüşü"),
    "28207435": ("narrative_review", "Niteliksel Derleme / Uzman Görüşü"),
    "32581543": ("narrative_review", "Niteliksel Derleme / Uzman Görüşü"),
    "41458822": ("systematic_review", "Sistematik Derleme"),
}


def _design(pub_types, title, abstract):
    return classify_study_design(pub_types, title, abstract)


class TestReviewTagDoesNotHideCaseReports(unittest.TestCase):
    def test_recorded_pmids_keep_case_report_narrative_review_and_systematic_review(self):
        self.assertEqual(
            [article["pmid"] for article in RECORDED_ARTICLES],
            ["33372889", "35955495", "28207435", "32581543", "41458822"],
        )
        for article in RECORDED_ARTICLES:
            pmid = article["pmid"]
            self.assertEqual(article["publication_types"], ["Journal Article", "Review"], pmid)
            design = _design(article["publication_types"], article["title"], article["abstract"])
            design_key, label = _EXPECTED[pmid]
            self.assertEqual(design["design_key"], design_key, pmid)
            self.assertEqual(design["design"], label, pmid)
            self.assertEqual(design["level"], "Değerlendirilemedi", pmid)
            self.assertIsNone(design["level_num"], pmid)
            self.assertNotIn("Seviye", design["level"])

    def test_zaki_case_report_is_not_a_narrative_review(self):
        article = next(item for item in RECORDED_ARTICLES if item["pmid"] == "33372889")
        self.assertEqual(article["authors"][0], "Mark M Zaki")
        self.assertEqual(article["pub_year"], "2021")
        self.assertIn("A case of", article["title"])
        self.assertIn("We present a case of a 67-year-old", article["abstract"])
        design = _design(article["publication_types"], article["title"], article["abstract"])
        self.assertEqual(design["design"], "Olgu Sunumu")
        self.assertNotEqual(design["design_key"], "narrative_review")

    def test_generic_review_yields_to_case_report_cues(self):
        cues = [
            ("A case of statin myopathy", "Muscle weakness developed after atorvastatin."),
            ("Statin myopathy: a case report", "The patient stopped the statin."),
            ("Statin myopathy", "We report a patient with progressive weakness."),
            ("Statin myopathy", "We present a 70-year-old patient with weakness after atorvastatin."),
            ("Statin myopathy", "A 67-year-old woman developed weakness after atorvastatin."),
            ("Statin myopathy", "An 8-year-old boy developed weakness after treatment."),
        ]
        for title, abstract in cues:
            design = _design(["Journal Article", "Review"], title, abstract)
            self.assertEqual(design["design"], "Olgu Sunumu", title + " " + abstract)
            self.assertEqual(design["design_key"], "case_report")
            self.assertEqual(design["level"], "Değerlendirilemedi")
            self.assertIsNone(design["level_num"])

    def test_several_patients_under_a_review_tag_are_a_case_series(self):
        design = _design(
            ["Review"],
            "Three cases of statin myopathy",
            "The patients were treated with corticosteroids.",
        )
        self.assertEqual(design["design"], "Olgu Serisi")
        self.assertEqual(design["design_key"], "case_series")

        described = _design(
            ["Journal Article", "Review"],
            "Statin-associated myopathy",
            "We present three patients with statin-associated myopathy. "
            "A 54-year-old man, a 61-year-old woman, and a 70-year-old man are described.",
        )
        self.assertEqual(described["design"], "Olgu Serisi")
        self.assertEqual(described["level"], "Değerlendirilemedi")
        self.assertIsNone(described["level_num"])

        series = _design(
            ["Review"],
            "Immune myopathy",
            "We report a series of 4 cases of immune-mediated myopathy.",
        )
        self.assertEqual(series["design"], "Olgu Serisi")

    def test_explicit_nlm_tags_outrank_case_report_wording(self):
        case_title = "A case of statin myopathy"
        case_abstract = "We present a case of a 67-year-old woman with progressive weakness."
        expected = [
            (["Systematic Review"], "systematic_review", "Sistematik Derleme"),
            (["Meta-Analysis"], "meta_analysis", "Meta-Analiz"),
            (["Randomized Controlled Trial"], "rct", "Rastgele Kontrollü Çalışma (RCT)"),
            (["Cohort Studies"], "cohort", "Kohort Çalışması (Gözlemsel)"),
            (["Case-Control Studies"], "case_control", "Vaka-Kontrol Çalışması"),
            (["Case Reports"], "case_report", "Olgu Sunumu"),
        ]
        for pub_types, design_key, label in expected:
            design = _design(pub_types, case_title, case_abstract)
            self.assertEqual(design["design_key"], design_key, pub_types)
            self.assertEqual(design["design"], label, pub_types)
            self.assertEqual(design["level"], "Değerlendirilemedi", pub_types)
            self.assertIsNone(design["level_num"], pub_types)

        series = _design(
            ["Case Reports", "Journal Article"],
            "Statin myopathy: a case series",
            "We present three patients with weakness.",
        )
        self.assertEqual(series["design"], "Olgu Serisi")
        self.assertEqual(series["level"], "Değerlendirilemedi")

    def test_cited_case_or_trial_does_not_reclassify_a_narrative_review(self):
        cited_case = _design(
            ["Journal Article", "Review"],
            "Statin myopathy",
            "A previous case report described muscle toxicity. This review summarizes management.",
        )
        self.assertEqual(cited_case["design"], "Niteliksel Derleme / Uzman Görüşü")

        cited_trial = _design(
            ["Review"],
            "Statin myopathy",
            "We present a review of patients treated with statins. "
            "A randomized trial previously showed a benefit.",
        )
        self.assertEqual(cited_trial["design"], "Niteliksel Derleme / Uzman Görüşü")
        self.assertEqual(cited_trial["level"], "Değerlendirilemedi")

    def test_case_report_wording_still_wins_when_the_abstract_cites_a_trial(self):
        design = _design(
            ["Review"],
            "Statin myopathy",
            "We present a case of a 67-year-old woman. A randomized trial previously showed a benefit.",
        )
        self.assertEqual(design["design"], "Olgu Sunumu")
        self.assertEqual(design["level"], "Değerlendirilemedi")
        self.assertIsNone(design["level_num"])

    def test_year_old_does_not_override_a_cohort_phrase_without_a_review_tag(self):
        design = _design(
            [],
            "Prospective cohort of statin users",
            "In this cohort of adults, a 67-year-old man was enrolled.",
        )
        self.assertEqual(design["design"], "Kohort Çalışması (Gözlemsel)")
        self.assertEqual(design["level"], "Değerlendirilemedi")


if __name__ == "__main__":
    unittest.main()
