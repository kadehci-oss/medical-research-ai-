"""Structured effects for section 6 matrix lines and outcome names.

The sentences are copied from published abstracts. The engine does not
special-case a PMID. Ratio intervals that cannot be a real CI stay visible
and are kept out of synthesis and GRADE precision.
"""
import re
import unittest

from grade_assessment import assess_preliminary_grade
from report_generator import (
    INCONSISTENT_SOURCE_FLAG,
    _format_cross_study_comparison,
    _trial_arm_label,
    extract_grounded_clinical_findings,
    format_finding_brief,
    generate_rule_based_turkish_report,
    study_effect_lines,
)


def _article(pmid, abstract, title, pub_types=None):
    return {
        "pmid": pmid,
        "title": title,
        "authors": ["Deneme Yazar"],
        "journal": "Test Journal",
        "pub_year": "2021",
        "publication_types": pub_types or ["Journal Article", "Randomized Controlled Trial"],
        "abstract": abstract,
        "doi": "10.1000/effect-" + pmid,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": "https://doi.org/10.1000/effect-" + pmid,
    }


def _outside_quotes(text):
    return re.sub(r'"[^"]*"', " ", text or "")


def _matrix_outcome_lines(report):
    match = re.search(
        r"### 📊 Karşılaştırmalı Sentez Matrisi\n(.*?)(?=\n### )",
        report,
        re.S,
    )
    if not match:
        return []
    lines = []
    for chunk in re.split(r"\n- \*\*", match.group(1)):
        found = re.search(r"\*\*Klinik Sonlanımlar ve Etki Ölçütleri:\*\*\s*(.+)", chunk)
        if found:
            lines.append(re.sub(r"\s+", " ", found.group(1)).strip())
    return lines


# EMPEROR-Reduced, the eGFR slope sentence.
_SLOPE = (
    "The annual rate of decline in the estimated glomerular filtration rate was slower "
    "in the empagliflozin group than in the placebo group (-0.55 vs. -2.28 ml per minute "
    "per 1.73 m2 of body-surface area per year, P<0.001), and empagliflozin-treated "
    "patients had a lower risk of serious renal outcomes."
)
# DAPA-HF allocation and primary result.
_DAPA = (
    "In this phase 3, placebo-controlled trial, we randomly assigned 4744 patients with "
    "New York Heart Association class II, III, or IV heart failure and an ejection fraction "
    "of 40% or less to receive either dapagliflozin (at a dose of 10 mg once daily) or "
    "placebo, in addition to recommended therapy. The primary outcome was a composite of "
    "worsening heart failure or cardiovascular death. The primary outcome occurred in fewer "
    "patients in the dapagliflozin group (hazard ratio, 0.74; 95% confidence interval [CI], "
    "0.65 to 0.85; p<0.001)."
)
# SOLOIST-style arm names without using one study's numbers as a rule.
_SOTA = (
    "Patients were randomly assigned to receive sotagliflozin or placebo. "
    "Cardiovascular death was lower (HR 0.78, 95% CI 0.48-1.27, P=0.32)."
)
# Geba 2023, dupilumab atopic march meta-analysis.
_IGE = (
    "Allergy-associated events were grouped, and IgE changes from baseline were defined. "
    "Treatment effect was assessed by incidence rate ratios (IRRs), dupilumab versus placebo. "
    "Including IgE category shift, the IRR for combined new/worsening allergies was reduced "
    "by 54% (IRR 0.46; 95% CI, 0.36-0.57)."
)
# Lin 2024, pediatric atopic march cohort.
_MARCH = (
    "After matching, we analyzed atopic march progression, defined by the incident asthma "
    "or allergic rhinitis (AR). The 3-year cumulative incidence of atopic march progression "
    "was lower in the DUPI-cohort than the CONV-cohort (20.09% vs 27.22%; P < .001). "
    "The DUPI-cohort demonstrated significant risk reduction in atopic march progression "
    "(hazard ratio [HR] 0.68, 95% CI 0.55-0.83), individual asthma (HR 0.60, 0.45-0.81), "
    "and individual AR (HR 0.69, 0.54-0.88)."
)
# Frail/older SGLT2 meta-analysis. The negative bounds are what the abstract printed.
_BAD_RATIO = (
    "SGLT2Is did not significantly reduce HbA1c level (mean difference -0.13, 95%CI: -0.41 to 0.14). "
    "SGLT2Is were associated with a significant reduction in the risk of all-cause mortality "
    "(risk ratio (RR) 0.81, 95%CI: -0.69 to 0.95), cardiac death (RR 0.80, 95%CI: -0.94 to 0.69) "
    "and hospitalisation for heart failure (HHF) (RR 0.69, 95%CI: 0.59-0.81)."
)

_ENGLISH_PROSE = re.compile(
    r"\b(cardiovascular death|hospitali[sz]ation|confidence interval|including IgE|"
    r"per minute|individual asthma|individual AR|was lower in the|placebo group|"
    r"died from|worsening HF|DUPI-cohort)\b",
    re.IGNORECASE,
)


class TestStructuredMatrixLines(unittest.TestCase):
    def test_slope_uses_a_turkish_unit_without_doubled_words_or_parentheses(self):
        findings = extract_grounded_clinical_findings(_SLOPE)
        slope = [item for item in findings if "0.55" in item["effect"]]
        self.assertEqual(len(slope), 1)
        brief = format_finding_brief(slope[0])
        self.assertIn("yıllık eGFR azalma hızı", brief)
        self.assertIn("-0.55 karşı -2.28", brief)
        self.assertIn("mL/dk/1,73 m²/yıl", brief)
        self.assertIn("p < 0.001", brief)
        self.assertNotIn("((", brief)
        self.assertNotIn("başına başına", brief)
        self.assertNotIn("empagliflozin", brief.lower())
        self.assertNotIn("placebo", brief.lower())
        self.assertNotIn("ml per", brief.lower())

    def test_allocation_names_are_the_intervention_not_a_stated_flag(self):
        self.assertEqual(_trial_arm_label(_DAPA), "dapagliflozin vs plasebo")
        self.assertEqual(_trial_arm_label(_SOTA), "sotagliflozin vs plasebo")
        self.assertEqual(_trial_arm_label("We reviewed heart failure guidelines."), "")
        article = _article("90009101", _DAPA, "Dapagliflozin in heart failure")
        table = _format_cross_study_comparison([article], {})
        self.assertIn("dapagliflozin vs plasebo", table)
        self.assertNotIn("| Belirtilmedi |", table)
        line = _matrix_outcome_lines(
            generate_rule_based_turkish_report("SGLT2 inhibitors heart failure", [article])
        )[0]
        visible = _outside_quotes(line)
        self.assertIn("tehlike oranı (HR) 0.74", visible)
        self.assertIn("GA 0.65 ile 0.85", visible)
        self.assertNotRegex(visible, _ENGLISH_PROSE)
        self.assertNotIn("((", visible)

    def test_dermatology_outcomes_are_controlled_terms_not_partial_words(self):
        report = generate_rule_based_turkish_report(
            "dupilumab atopic dermatitis",
            [
                _article("90009102", _IGE, "Attenuating the atopic march", ["Meta-Analysis"]),
                _article(
                    "90009103",
                    _MARCH,
                    "Reduced atopic march risk",
                    ["Journal Article", "Observational Study"],
                ),
            ],
        )
        visible = _outside_quotes(report.split("## 5.")[1].split("## 7.")[0])
        self.assertIn("IgE kategori değişimi", visible)
        self.assertIn("insidans hızı oranı (IRR) 0.46", visible)
        self.assertNotIn("insidans oranı oranı", visible)
        self.assertIn("atopik yürüyüş ilerlemesi", visible)
        self.assertIn("tehlike oranı (HR) 0.68", visible)
        self.assertIn("astım", visible)
        self.assertIn("alerjik rinit", visible)
        self.assertIn("20.09% karşı 27.22%", visible)
        for garbled in (
            "Sonlanım: dahil",
            "anlamlı risk progresyon",
            "birey AR",
            "Sonlanım: birey",
            "((",
            "başına başına",
        ):
            self.assertNotIn(garbled, visible)
        self.assertNotRegex(visible, _ENGLISH_PROSE)
    def test_inconsistent_ratio_is_flagged_and_kept_out_of_synthesis_and_grade(self):
        findings = extract_grounded_clinical_findings(_BAD_RATIO)
        by_value = {item["estimate"]: item for item in findings if item.get("estimate")}
        self.assertTrue(by_value["0.81"]["implausible"])
        self.assertTrue(by_value["0.80"]["implausible"])
        self.assertFalse(by_value["0.69"]["implausible"])
        self.assertFalse(by_value["-0.13"]["implausible"])
        self.assertEqual(by_value["0.81"]["ci"], "-0.69 ile 0.95")
        brief = " ".join(study_effect_lines(_BAD_RATIO))
        self.assertIn(INCONSISTENT_SOURCE_FLAG, brief)
        self.assertIn("risk oranı (RR) 0.81", brief)
        self.assertIn("-0.69 ile 0.95", brief)

        article = _article(
            "90009104",
            _BAD_RATIO,
            "SGLT2 inhibitors in older people",
            ["Meta-Analysis"],
        )
        report = generate_rule_based_turkish_report("SGLT2 inhibitors heart failure", [article])
        section_12 = report.split("## 12.")[1].split("## 13.")[0]
        visible_12 = _outside_quotes(section_12)
        self.assertNotIn("risk oranı (RR) 0.81", visible_12)
        self.assertNotIn("-0.69", visible_12)
        self.assertNotIn(INCONSISTENT_SOURCE_FLAG, visible_12)
        self.assertIn("risk oranı (RR) 0.69", visible_12)

        note = assess_preliminary_grade(article, "SGLT2 inhibitors heart failure")
        reason = note["domains"]["imprecision"]["reason"]
        self.assertNotIn("-0.69", reason)
        self.assertNotIn("-0.94", reason)
        self.assertIn("0.59", reason)
        self.assertIn("0.81", reason)


if __name__ == "__main__":
    unittest.main()
