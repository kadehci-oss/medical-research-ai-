"""Narrative honesty regressions from live abstract shapes.

The sentences are copied from published abstracts. No PMID is special-cased.
Significance follows the numbers. PICO fields are structured Turkish values,
not a word-by-word translation of the English clause.
"""
import re
import unittest

from grade_assessment import format_preliminary_grade_markdown
from report_generator import (
    _format_cross_study_comparison,
    _translate_clinical_conclusion_to_turkish,
    extract_article_clinical_details,
    extract_study_metrics,
    format_methodological_limitation,
    generate_rule_based_turkish_report,
    study_effect_lines,
)


def _article(pmid, title, abstract, authors, year, pub_types):
    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": "Test Journal",
        "pub_year": year,
        "publication_types": pub_types,
        "abstract": abstract,
        "doi": "10.1000/honesty-" + pmid,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": "https://doi.org/10.1000/honesty-" + pmid,
    }


def _outside_quotes(text):
    return re.sub(r'"[^"]*"', " ", text or "")


# Significant OR and p-values, plus a subgroup phrase that used to force
# the default "fark saptanmamıştır" template.
_TITULAER_SHAPE = (
    "In this observational cohort study 577 patients were enrolled. "
    "No significant difference was observed in one laboratory subgroup. "
    "The odds ratio for a good outcome was 2.70 (95% CI 1.24-5.80, p<0.0001). "
    "A second comparison had p=0.012."
)
# Allocation arm, not an incidental results mention.
_DUPI_TRIAL = (
    "Patients with atopic dermatitis were randomized to receive dupilumab or placebo. "
    "The incidence rate ratio for IgE category shift was 0.46 "
    "(95% CI, 0.36-0.57)."
)
# "compared to placebo" here is a result sentence, not the study arm.
_DUPI_COHORT = (
    "We reviewed patients with atopic dermatitis treated with dupilumab. "
    "Skin infections were less frequently observed compared to placebo."
)
_KAWASAKI = (
    "OBJECTIVE: Intravenous immunoglobulin (IVIG) resistance in Kawasaki disease (KD) "
    "was studied. METHODS: Complete and incomplete KD patients diagnosed with KD at "
    "Hacettepe University between June 2007 and September 2019 were evaluated retrospectively. "
    "One hundred twenty-nine patients were included."
)
_MISCLASS = (
    "LIMITATIONS: There is potential for misclassification in the database. "
    "Association between dupilumab and the outcome does not prove causality."
)
_UNMAPPED_LIMIT = (
    "Traditional drug therapy has certain limitations for treating young children with atopic dermatitis."
)
_AUC = (
    "The area under the curve was 0.626 (95% confidence interval (CI): 0.553-0.698, p<0.001), "
    "0.571 (95% confidence interval [CI], 0.500-0.642, p<0.001), "
    "and 0.568 (95% CI: 0.495-0.641, p<0.001)."
)
_NAMED_CI = (
    "Hospitalization for heart failure was lower (hazard ratio 0.74; "
    "95% confidence interval 0.65-0.85; p<0.001)."
)
_DRUGS = (
    "Patients received methotrexate, rituximab, and intravenous immunoglobulin "
    "together with immunosuppressive therapy."
)
_MARCH = (
    "Including IgE category shift, the risk reduction in atopic march progression "
    "was lower in the DUPI-cohort than the CONV-cohort "
    "(hazard ratio 0.68, 95% CI 0.55-0.83, p<0.001)."
)


class TestSignificanceFollowsTheNumbers(unittest.TestCase):
    def test_significant_values_are_not_called_nonsignificant(self):
        article = _article(
            "90018001",
            "Treatment and prognostic factors for long-term outcome in patients with anti-NMDA receptor encephalitis",
            _TITULAER_SHAPE,
            ["Maarten J Titulaer"],
            "2013",
            ["Journal Article", "Observational Study"],
        )
        report = generate_rule_based_turkish_report(
            "anti-NMDA receptor encephalitis treatment",
            [article],
        )
        visible = _outside_quotes(report)
        self.assertIn("istatistiksel olarak anlamlı bir fark saptanmıştır", visible)
        self.assertNotIn("istatistiksel olarak anlamlı bir fark saptanmamıştır", visible)
        self.assertNotIn("confidence interval", visible.lower())
        self.assertNotIn("95% CI", visible)
        self.assertIn("1.24 ile 5.80", visible)
        self.assertNotRegex(visible, r"\*[^*]+\*\s+çalışması")
        self.assertIn("Maarten J Titulaer (2013), PMID: 90018001", visible)
        section_4 = report.split("## 4.")[1].split("## 5.")[0]
        self.assertNotIn("*Treatment and prognostic factors", section_4)

    def test_unknown_significance_is_not_a_default_negative(self):
        text = _translate_clinical_conclusion_to_turkish(
            "",
            "This review summarizes recent developments in the field.",
            {},
            "Niteliksel Derleme / Uzman Görüşü",
            "Kawasaki disease.",
            authors=["Jane W Newburger"],
            year="2004",
            pmid="90018002",
        )
        self.assertIn("Anlamlılık değerlendirilemedi", text)
        self.assertNotIn("fark saptanmamıştır", text)
        self.assertNotIn("Kawasaki disease.", text)
        self.assertIn("Jane W Newburger (2004), PMID: 90018002", text)


class TestStructuredPicoFields(unittest.TestCase):
    def test_word_by_word_population_and_incidental_placebo_are_not_used(self):
        cohort = _article(
            "90018003",
            "Dupilumab use in atopic dermatitis",
            _DUPI_COHORT,
            ["Iraj Hasan"],
            "2024",
            ["Journal Article", "Observational Study"],
        )
        trial = _article(
            "90018004",
            "Effect of dupilumab in atopic dermatitis",
            _DUPI_TRIAL,
            ["Emma Guttman-Yassky"],
            "2019",
            ["Journal Article", "Randomized Controlled Trial"],
        )
        kawasaki = _article(
            "90018005",
            "Comparison of IVIG resistance predictive models in Kawasaki disease",
            _KAWASAKI,
            ["Ummusen Kaya Akca"],
            "2022",
            ["Journal Article"],
        )
        for article in (cohort, trial, kawasaki):
            details = extract_article_clinical_details(article, "query")
            blob = " ".join((
                details["patient_group"],
                details["intervention"],
                details["comparison"],
            ))
            for garbage in (
                "Hacettepe", "June", "September", "samples", "Recognise",
                "cognitive", "incomplete KD", "hastalık ve", "(veya)", "(NMDA)",
                "efficacy atopik", "strategies",
            ):
                self.assertNotIn(garbage, blob)
        cohort_details = extract_article_clinical_details(cohort, "dupilumab atopic dermatitis")
        self.assertIn("dupilumab", cohort_details["intervention"].lower())
        self.assertEqual(cohort_details["comparison"], "bildirilmedi")
        self.assertIn("atopik dermatit", cohort_details["patient_group"])
        trial_details = extract_article_clinical_details(trial, "dupilumab atopic dermatitis")
        self.assertIn("dupilumab", trial_details["intervention"].lower())
        self.assertEqual(trial_details["comparison"], "Plasebo")
        kawa = extract_article_clinical_details(kawasaki, "Kawasaki disease IVIG resistance")
        self.assertIn("Kawasaki hastalığı (KH)", kawa["patient_group"])
        self.assertNotIn(" KD", " " + kawa["patient_group"])
        self.assertNotRegex(kawa["patient_group"], r"\bKD\b")

        table = _format_cross_study_comparison([cohort, trial], {})
        cohort_row = [line for line in table.splitlines() if line.startswith("|") and "90018003" in line][0]
        trial_row = [line for line in table.splitlines() if line.startswith("|") and "90018004" in line][0]
        self.assertIn("dupilumab", cohort_row.lower())
        self.assertNotIn("| Belirtilmedi |", cohort_row)
        self.assertIn("dupilumab", trial_row.lower())
        self.assertIn("plasebo", trial_row.lower())

        report = generate_rule_based_turkish_report("dupilumab atopic dermatitis", [cohort, trial, kawasaki])
        gerekce = report.split("### 🚫 Karşılaştırılamama")[1].split("### 📑")[0]
        for garbage in ("Hacettepe", "June 2007", "CSF samples", "Recognise", "(veya)"):
            self.assertNotIn(garbage, _outside_quotes(gerekce))


class TestIntervalsDrugsAndLimitations(unittest.TestCase):
    def test_intervals_are_bounds_and_unlabeled_numbers_are_omitted(self):
        lines = " ".join(study_effect_lines(_NAMED_CI))
        self.assertIn("0.65 ile 0.85", lines)
        self.assertIn("kalp yetersizliği nedeniyle hastaneye yatış", lines)
        self.assertNotIn("confidence interval", lines.lower())
        self.assertNotIn("95% CI", lines)
        auc_lines = " ".join(study_effect_lines(_AUC))
        self.assertNotIn("kaynak değer: 0.571", auc_lines)
        self.assertNotIn("confidence interval", auc_lines.lower())
        self.assertLessEqual(auc_lines.count("p < 0.001"), 1)
        repeated = study_effect_lines(
            "The primary score was lower (p<0.0001). The primary score was lower (p<0.0001)."
        )
        self.assertEqual(sum("p < 0.0001" in line for line in repeated), 1)
        visible = _outside_quotes(
            generate_rule_based_turkish_report(
                "heart failure",
                [_article(
                    "90018006",
                    "A heart failure trial",
                    _NAMED_CI + " " + _AUC,
                    ["E. Davis"],
                    "2023",
                    ["Journal Article", "Randomized Controlled Trial"],
                )],
            )
        )
        self.assertNotIn("confidence interval", visible.lower())
        self.assertNotIn("özette adlandırılmadı: özette adlandırılmadı", visible)
        dupi_visible = _outside_quotes(
            generate_rule_based_turkish_report(
                "dupilumab atopic dermatitis",
                [_article(
                    "90018007",
                    "Attenuating the atopic march",
                    _DUPI_TRIAL,
                    ["T. Geba"],
                    "2023",
                    ["Meta-Analysis"],
                )],
            )
        )
        self.assertIn("insidans hızı oranı (IRR)", dupi_visible)
        self.assertNotIn("insidans oranı oranı", dupi_visible)
        self.assertNotIn("insidans oranı oranı", visible)

    def test_concomitant_drugs_and_section_11_use_turkish_labels(self):
        metrics = extract_study_metrics(_DRUGS)
        joined = ", ".join(metrics["concomitant_treatments"])
        self.assertIn("metotreksat", joined)
        self.assertIn("rituksimab", joined)
        self.assertIn("immünosupresif", joined)
        self.assertIn("intravenöz immünoglobulin (IVIG)", joined)
        for english in ("Methotrexate", "Rituximab", "Immunosuppressive", "Intravenous"):
            self.assertNotIn(english, joined)

        article = _article(
            "90018008",
            "Reduced atopic march risk",
            _MARCH,
            ["Teng-Li Lin"],
            "2024",
            ["Journal Article", "Observational Study"],
        )
        section_11 = format_preliminary_grade_markdown("dupilumab atopic dermatitis", [article])
        visible = _outside_quotes(section_11)
        self.assertNotIn("Including IgE", visible)
        self.assertNotIn("was lower in the", visible)
        self.assertNotIn("risk reduction in atopic march", visible)
        self.assertNotIn("DUPI-cohort", visible)
        self.assertTrue(
            "atopik yürüyüş" in visible or "IgE kategori" in visible or "özette adlandırılmadı" in visible
        )

    def test_author_limitations_use_the_phrase_map_or_a_generic_label(self):
        mapped = format_methodological_limitation(_article(
            "90018009",
            "Dupilumab therapy and lymphoma",
            _MISCLASS,
            ["Iraj Hasan"],
            "2024",
            ["Journal Article"],
        ))
        self.assertIn("Yazarların belirttiği sınırlılık: veri tabanında yanlış sınıflama olasılığı", mapped)
        self.assertIn("Yazarların belirttiği sınırlılık: nedensellik kurulamadığı bildirildi", mapped)
        self.assertIn('Kaynak cümle:', mapped)
        self.assertNotIn("LIMITATIONS:", _outside_quotes(mapped))

        plain = format_methodological_limitation(_article(
            "90018010",
            "Traditional therapy",
            _UNMAPPED_LIMIT,
            ["A. Yazar"],
            "2022",
            ["Journal Article"],
        ))
        self.assertIn("Yazarlar sınırlılık bildirmiş (kaynak cümleye bakın)", plain)
        self.assertIn("Traditional drug therapy has certain limitations", plain)
        self.assertTrue(plain.index("Yazarlar sınırlılık") < plain.index("Traditional drug therapy"))


if __name__ == "__main__":
    unittest.main()
