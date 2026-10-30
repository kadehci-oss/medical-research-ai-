"""Section 5 and 6 polish. Recorded PubMed metadata, no network.

The checks are disease-agnostic: background wording is not a patient finding,
junk fragments are dropped, identical lines are not repeated, and section 6
uses the Turkish sample and treatment fields. A methods sentence is not a
limitation. Nothing is hardcoded to one PMID inside the engine.
"""
import json
import os
import re
import unittest
from unittest.mock import patch

from tests.test_review_tagged_case_reports import RECORDED_ARTICLES
from report_generator import (
    INSUFFICIENT_CLINICAL_DATA_TR,
    _format_cross_study_comparison,
    extract_clinical_profile,
    extract_methodological_limitations,
    extract_study_metrics,
    format_klinik_bulgular_cell,
    format_methodological_limitation,
    generate_rule_based_turkish_report,
)

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_BACKGROUND_PRESENTS = "It presents with severe proximal muscle weakness"
_SHOULD_CONSIDER = "should be considered in patients with"
_CASE_SENTENCE_33447390 = (
    "We report a rare case of statin-associated anti-HMGCR immune-mediated "
    "necrotizing myopathy with dermatomyositis-like cutaneous features."
)
_METHODS_40446701 = (
    "In this retrospective study 97 patients with IIM were self-identified as Hispanic versus non-Hispanic."
)
_METHODS_41010829 = "A retrospective review was conducted at a single institution"


def _load(name):
    with open(os.path.join(_FIXTURE_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def _by_pmid(articles):
    return {article["pmid"]: article for article in articles}


def _flat(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_quotes(text):
    return re.sub(r'"[^"]*"', "", text or "")


def _row(table, pmid):
    for line in table.splitlines():
        if line.startswith("|") and re.search(r"\b" + re.escape(pmid) + r"\b", line):
            return line
    return ""


def _row_cells(line):
    return [part.strip() for part in line.strip().strip("|").split("|")]


def _english_four_grams(abstract):
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", abstract or "")
    grams = []
    for index in range(len(words) - 3):
        grams.append(" ".join(words[index:index + 4]).lower())
    return grams


def _assert_no_english_prose(test, cell, abstract):
    visible = _strip_quotes(cell).lower()
    for gram in _english_four_grams(abstract):
        test.assertNotIn(gram, visible, gram)


class TestSection5QualitativeFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        articles = []
        articles.extend(_load("recorded_pmid_33447390.json"))
        articles.extend(_load("recorded_target_pmids.json"))
        articles.extend(_load("recorded_pubmed_multidesign.json"))
        articles.extend(RECORDED_ARTICLES)
        cls.by_pmid = _by_pmid(articles)

    def test_33447390_case_sentence_is_not_replaced_by_background(self):
        article = self.by_pmid["33447390"]
        self.assertIn("Case Reports", article["publication_types"])
        self.assertIn(_BACKGROUND_PRESENTS, article["abstract"])
        self.assertIn(_SHOULD_CONSIDER, article["abstract"])
        cell = format_klinik_bulgular_cell(article)
        self.assertIn("dermatomiyozit benzeri deri bulguları", cell)
        self.assertIn(_CASE_SENTENCE_33447390, cell)
        self.assertIn("Kaynak cümle:", cell)
        self.assertNotIn(INSUFFICIENT_CLINICAL_DATA_TR, cell)
        self.assertNotIn(_BACKGROUND_PRESENTS, cell)
        self.assertNotIn(_SHOULD_CONSIDER, cell)
        self.assertNotIn("şiddetli proksimal kas güçsüzlüğü", cell)
        self.assertNotIn("belirgin yüksek kreatin kinaz", cell)
        profile = extract_clinical_profile(article["abstract"])
        qualitative = [item for item in profile if item["category"] == "qualitative"]
        self.assertTrue(qualitative)
        for item in qualitative:
            self.assertIn(_CASE_SENTENCE_33447390, item["sentence"])
            self.assertNotIn("It presents with", item["sentence"])
            self.assertNotIn("should be considered", item["sentence"])

    def test_case_sentence_keeps_weakness_and_kinase_when_they_belong_to_the_patient(self):
        # Same phrases as the background of 33447390, but here the case sentence states them.
        article = {
            "pmid": "90005611",
            "title": "A case of immune myopathy",
            "publication_types": ["Case Reports"],
            "abstract": (
                "Immune myopathy is a rare entity. It presents with fatigue in general. "
                "The diagnosis should be considered in patients with mild pain. "
                "We report a rare case of immune myopathy with severe proximal muscle weakness "
                "and highly elevated creatine kinase."
            ),
        }
        cell = format_klinik_bulgular_cell(article)
        self.assertIn("şiddetli proksimal kas güçsüzlüğü", cell)
        self.assertIn("belirgin yüksek kreatin kinaz", cell)
        self.assertIn("We report a rare case of immune myopathy", cell)
        self.assertNotIn("It presents with fatigue", cell)
        self.assertNotIn("should be considered", cell)

    def test_background_and_unattributed_sentences_are_not_patient_findings(self):
        background = {
            "pmid": "90005612",
            "title": "Immune myopathy",
            "publication_types": ["Review"],
            "abstract": (
                "It presents with severe proximal muscle weakness, high creatine kinase levels "
                "and muscle fiber necrosis. The diagnosis should be considered in patients with "
                "severe proximal muscle weakness and highly elevated creatine kinase."
            ),
        }
        cell = format_klinik_bulgular_cell(background)
        self.assertTrue(cell.startswith(INSUFFICIENT_CLINICAL_DATA_TR))
        self.assertNotIn("şiddetli proksimal kas güçsüzlüğü", cell)
        self.assertNotIn("Nitel klinik bulgu:", cell)

        unclear = {
            "pmid": "90005613",
            "title": "Muscle disease",
            "publication_types": ["Journal Article"],
            "abstract": "Presented with severe proximal muscle weakness and highly elevated creatine kinase.",
        }
        unclear_cell = format_klinik_bulgular_cell(unclear)
        self.assertIn("bildirilen olguya ait olup olmadığı belirlenemedi", unclear_cell)
        self.assertNotIn("şiddetli proksimal kas güçsüzlüğü", unclear_cell)
        self.assertNotIn("CK yüksekliği bildirildi", unclear_cell)

    def test_28207435_rejects_the_patient_only_fragment(self):
        article = self.by_pmid["28207435"]
        cell = format_klinik_bulgular_cell(article)
        self.assertNotRegex(cell, r"Nitel klinik bulgu:\s*hasta\b")
        self.assertNotIn("immünosupresif tedavi", cell)
        self.assertTrue(cell.startswith(INSUFFICIENT_CLINICAL_DATA_TR))
        for item in extract_clinical_profile(article["abstract"]):
            if item["category"] == "qualitative":
                self.fail(item["line"])

    def test_41458822_does_not_repeat_remission(self):
        article = self.by_pmid["41458822"]
        cell = format_klinik_bulgular_cell(article)
        self.assertEqual(cell.count("Remisyon bildirildi"), 1)
        self.assertIn("Nüks: 25-35%", cell)
        self.assertNotIn("Nüks bildirildi.", cell)
        self.assertNotIn("biomarkers of durable remission", _strip_quotes(cell).lower())

    def test_duplicate_course_lines_collapse_inside_one_row(self):
        article = {
            "pmid": "90005614",
            "title": "Endocrine case",
            "publication_types": ["Case Reports"],
            "abstract": (
                "We report a case of thyroid storm with fever and vomiting. "
                "She achieved remission. Later she achieved remission again. "
                "Biomarkers of durable remission remain undefined."
            ),
        }
        cell = format_klinik_bulgular_cell(article)
        self.assertEqual(cell.count("Remisyon bildirildi"), 1)
        self.assertIn("ateş", cell)
        self.assertIn("kusma", cell)
        self.assertNotIn("Biomarkers of durable remission", cell)

    def test_other_specialties_keep_case_features_and_drop_background(self):
        derm = self.by_pmid["35503884"]
        derm_cell = format_klinik_bulgular_cell(derm)
        self.assertIn("sert viyolese papüller", derm_cell)
        self.assertIn("konjonktival kızarıklık", derm_cell)
        self.assertNotRegex(derm_cell, r"Nitel klinik bulgu:\s*hasta\b")
        self.assertNotIn("Janus kinase (JAK) inhibitors are being prescribed", derm_cell)

        neuro = self.by_pmid["38955192"]
        neuro_cell = format_klinik_bulgular_cell(neuro)
        self.assertIn("miyalji", neuro_cell)
        self.assertIn("ateş", neuro_cell)
        self.assertIn("27 yaşında kadın", neuro_cell)
        self.assertNotIn("Dengue continues to pose a global health challenge", neuro_cell)
        self.assertNotIn("stroke is an uncommon complication", neuro_cell)

        lung = {
            "pmid": "90005615",
            "title": "A case of pulmonary embolism",
            "publication_types": ["Case Reports"],
            "abstract": (
                "Pulmonary embolism is a common emergency. It presents with sudden dyspnea and chest pain. "
                "The diagnosis should be considered in patients with sudden dyspnea. "
                "We report a case of pulmonary embolism with sudden dyspnea and pleuritic chest pain."
            ),
        }
        lung_cell = format_klinik_bulgular_cell(lung)
        self.assertIn("ani dispne", lung_cell)
        self.assertIn("plöritik göğüs ağrısı", lung_cell)
        self.assertIn("We report a case of pulmonary embolism", lung_cell)
        self.assertNotIn("It presents with sudden dyspnea", lung_cell)
        self.assertNotIn("should be considered", lung_cell)

        oncology = {
            "pmid": "90005616",
            "title": "Melanoma",
            "publication_types": ["Case Reports"],
            "abstract": (
                "Metastatic melanoma may cause many symptoms. "
                "Prompt treatment is of enormous benefit to the patient. "
                "We report a case of metastatic melanoma with severe headache and vomiting."
            ),
        }
        oncology_cell = format_klinik_bulgular_cell(oncology)
        self.assertIn("şiddetli baş ağrısı", oncology_cell)
        self.assertIn("kusma", oncology_cell)
        self.assertNotRegex(oncology_cell, r"Nitel klinik bulgu:\s*hasta\b")


class TestSection6ComparisonCells(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        articles = []
        articles.extend(_load("recorded_pmid_33447390.json"))
        articles.extend(_load("recorded_target_pmids.json"))
        articles.extend(_load("recorded_pubmed_multidesign.json"))
        articles.extend(RECORDED_ARTICLES)
        cls.by_pmid = _by_pmid(articles)
        cls.order = [
            "33447390", "28207435", "41458822", "40446701", "41010829",
            "33372889", "36896367", "35503884", "38955192", "33795149",
        ]
        cls.table = _format_cross_study_comparison(
            [cls.by_pmid[pmid] for pmid in cls.order], {}
        )

    def _cells(self, pmid):
        cells = _row_cells(_row(self.table, pmid))
        self.assertGreaterEqual(len(cells), 6, self.table)
        return cells

    def test_patient_and_intervention_are_turkish_structured_fields(self):
        patient, _design, intervention = self._cells("40446701")[1:4]
        self.assertIn("62 hasta Hispanik", patient)
        self.assertIn("35 hasta Hispanik olmayan", patient)
        self.assertNotIn("self-identified", patient.lower())
        self.assertNotIn("hispanic versus", patient.lower())
        self.assertEqual(intervention, "Belirtilmedi")

        series_patient, _series_design, series_intervention = self._cells("41010829")[1:4]
        self.assertIn("10 hasta", series_patient)
        self.assertIn("6 kadın, 4 erkek", series_patient)
        self.assertNotIn("anti-hmgcr-positive", series_patient.lower())
        for drug in ("kortikosteroid", "metotreksat", "IVIG", "rituksimab", "azatioprin"):
            self.assertIn(drug, series_intervention)

        case_patient, _case_design, case_intervention = self._cells("33372889")[1:4]
        self.assertIn("67 yaşında kadın", case_patient)
        self.assertIn("prednizon", case_intervention)
        self.assertIn("azatioprin", case_intervention)
        self.assertNotIn("necrotizing", case_intervention.lower())

        _title_patient, _title_design, title_intervention = self._cells("36896367")[1:4]
        self.assertNotIn("resulting", title_intervention.lower())
        self.assertNotIn("Statin-induced", title_intervention)
        self.assertIn("immünosupresif tedavi", title_intervention)

        missing_patient, _missing_design, missing_intervention = self._cells("33447390")[1:4]
        self.assertEqual(missing_patient, "özette bildirilmedi")
        self.assertEqual(missing_intervention, "Belirtilmedi")
        self.assertIn("dermatomiyozit benzeri deri bulguları", self._cells("33447390")[4])

        heart_intervention = self._cells("33795149")[3]
        self.assertIn("deksametazon", heart_intervention)
        self.assertIn("remdesivir", heart_intervention)
        self.assertNotIn("treated with", heart_intervention.lower())

    def test_limitations_are_not_methods_sentences(self):
        compare_limit = self._cells("40446701")[5]
        self.assertIn("Tasarımından türetilen sınırlılık", compare_limit)
        self.assertIn("Retrospektif tasarım", compare_limit)
        self.assertIn("PMID: 40446701", compare_limit)
        self.assertNotIn("METHODS", compare_limit)
        self.assertNotIn("self-identified", compare_limit.lower())
        self.assertNotIn(_METHODS_40446701, compare_limit)
        self.assertNotIn("Küçük örneklem", compare_limit)
        self.assertNotIn("Kontrol grubu yok", compare_limit)

        series_limit = self._cells("41010829")[5]
        self.assertIn("Tasarımından türetilen sınırlılık (PMID: 41010829)", series_limit)
        self.assertIn("Retrospektif tasarım", series_limit)
        self.assertIn("Tek merkez", series_limit)
        self.assertIn("Küçük örneklem (n=10)", series_limit)
        self.assertIn("Kontrol grubu yok", series_limit)
        self.assertNotIn(_METHODS_41010829, series_limit)
        self.assertNotIn("single institution", series_limit.lower())

        items = extract_methodological_limitations(self.by_pmid["41010829"])
        labels = {item["label"] for item in items}
        self.assertIn("Retrospektif tasarım", labels)
        self.assertIn("Tek merkez", labels)
        self.assertIn("Küçük örneklem (n=10)", labels)
        abstract = _flat(self.by_pmid["41010829"]["abstract"])
        for item in items:
            self.assertEqual(item["kind"], "derived")
            self.assertEqual(item["pmid"], "41010829")
            self.assertIn(_flat(item["source_sentence"]), abstract)

        review_limit = self._cells("28207435")[5]
        self.assertEqual(review_limit, "Özette spesifik metodolojik sınırlılık bildirilmedi")

    def test_explicit_limitation_stays_a_quoted_source_not_a_methods_line(self):
        article = {
            "pmid": "90005617",
            "title": "Cohort",
            "publication_types": ["Journal Article", "Observational Study"],
            "abstract": (
                "METHODS: In this retrospective study 40 patients were enrolled. "
                "However, causality cannot be determined due to the observational nature of the cohort."
            ),
        }
        metrics = extract_study_metrics(article["abstract"])
        self.assertTrue(any("causality cannot" in item.lower() for item in metrics["causality_limitations"]))
        self.assertFalse(any(item.startswith("METHODS:") for item in metrics["causality_limitations"]))
        cell = format_methodological_limitation(article)
        self.assertIn("nedensellik kurulamadığı bildirildi", cell)
        self.assertIn('Kaynak cümle:', cell)
        self.assertIn("causality cannot be determined", cell)
        self.assertNotIn("40 patients were enrolled", _strip_quotes(cell))

    def test_a_cited_retrospective_study_is_not_this_papers_limitation(self):
        article = {
            "pmid": "90005618",
            "title": "Myopathy review",
            "publication_types": ["Journal Article", "Review"],
            "abstract": (
                "A previous retrospective study compared two drugs. "
                "This review summarizes laboratory methods."
            ),
        }
        self.assertNotIn("Retrospektif tasarım", format_methodological_limitation(article))

    def test_turkish_cells_do_not_repeat_english_abstract_prose(self):
        for pmid in self.order:
            article = self.by_pmid[pmid]
            cells = self._cells(pmid)
            patient, intervention, findings, limit = cells[1], cells[3], cells[4], cells[5]
            _assert_no_english_prose(self, patient, article["abstract"])
            _assert_no_english_prose(self, intervention, article["abstract"])
            _assert_no_english_prose(self, limit, article["abstract"])
            for match in re.finditer(r"Nitel klinik bulgu:\s*([^.]*)", findings):
                _assert_no_english_prose(self, match.group(1), article["abstract"])
            self.assertNotRegex(patient + " " + intervention, r"Nitel klinik bulgu:\s*hasta\b")

    def test_identical_findings_are_not_repeated_in_section_6(self):
        findings = self._cells("41458822")[4]
        self.assertEqual(findings.count("Remisyon bildirildi"), 1)

    @patch("report_generator.verify_citation", return_value={"status": "verified", "verified": True, "reason": "match"})
    def test_section_5_and_6_do_not_mix_pmid_data(self, _mock_verify):
        selected = [
            self.by_pmid[pmid]
            for pmid in ("33447390", "40446701", "41010829", "33372889", "38955192", "35503884")
        ]
        report = generate_rule_based_turkish_report(
            "statin-associated immune-mediated necrotizing myopathy",
            selected,
        )
        section_5 = report.split("## 5. Bilimsel Kanıt Tablosu")[1].split("## 6.")[0]
        section_6 = report.split("## 6. Önemli Çalışmaların Karşılaştırılması")[1].split("## 7.")[0]
        expectations = {
            "33447390": ("dermatomiyozit benzeri deri bulguları", ("4.81", "13,000", "prednizon", "papüller")),
            "40446701": ("4.81", ("13,000", "233", "dermatomiyozit", "prednizon")),
            "41010829": ("13,000", ("4.81", "dermatomiyozit", "67 yaşında")),
            "33372889": ("prednizon", ("4.81", "13,000", "dermatomiyozit")),
            "38955192": ("miyalji", ("4.81", "13,000", "rituksimab", "papüller")),
            "35503884": ("papüller", ("4.81", "13,000", "rituksimab", "Hispanik")),
        }
        for pmid, (needed, banned) in expectations.items():
            for section in (section_5, section_6):
                row = _row(section, pmid)
                self.assertIn(needed, row, pmid)
                for token in banned:
                    self.assertNotIn(token, row, f"{pmid} {token}")


if __name__ == "__main__":
    unittest.main()
