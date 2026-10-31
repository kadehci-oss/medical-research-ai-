"""Outcome names and sample cells. Real abstract sentences, no network.

The engine does not special-case a PMID. Each fixture is a sentence pattern
that a live SGLT2 or statin abstract actually used.
"""
import re
import unittest

from display_turkish import localize_clinical_display
from report_generator import (
    UNTRANSLATED_OUTCOME_LABEL,
    _findings_cell,
    _format_cross_study_comparison,
    extract_clinical_profile,
    extract_grounded_clinical_findings,
    format_klinik_bulgular_cell,
)


def _article(pmid, abstract, title="Heart failure trial", pub_types=None):
    return {
        "pmid": pmid,
        "title": title,
        "authors": ["Deneme Yazar"],
        "journal": "Test Journal",
        "pub_year": "2024",
        "publication_types": pub_types or ["Journal Article", "Meta-Analysis"],
        "abstract": abstract,
        "doi": "10.1000/test-" + pmid,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": "https://doi.org/10.1000/test-" + pmid,
    }


def _row_cells(table, pmid):
    for line in table.splitlines():
        if line.startswith("|") and re.search(r"\b" + re.escape(pmid) + r"\b", line):
            return [part.strip() for part in line.strip().strip("|").split("|")]
    return []


def _outside_quotes(text):
    return re.sub(r'"[^"]*"', " ", text or "")


# Sentences copied from published abstracts (wording unchanged).
_ALL_CAUSE = (
    "In a meta-analysis of patients hospitalized for HF, SGLT2 inhibitors reduced "
    "the early risk of cardiovascular death or worsening HF (HR, 0.71 [95% CI, 0.54-0.93] "
    "P=0.012) and of all-cause death (HR, 0.57 [95% CI, 0.41-0.80]; P=0.001)."
)
_DRUG_LIST = (
    "A combination of ARNi, BB, MRA, and SGLT2i was most effective in reducing all-cause death "
    "(HR: 0.39; 95% CI: 0.31-0.49); followed by ARNi, BB, MRA, and vericiguat "
    "(HR: 0.41; 95% CI: 0.32-0.53); and ARNi, BB, and MRA (HR: 0.44; 95% CI: 0.36-0.54)."
)
_COMPOSITE_HF = (
    "Results were similar for the composite outcome of cardiovascular death or first "
    "hospitalization for HF (HR: 0.36; 95% CI: 0.29-0.46 for ARNi, BB, MRA, and SGLT2i)."
)
_EGFR_SUBGROUP = (
    "SGLT2 inhibitors reduced the risk of CKD progression (hazard ratio [HR], 0.62 "
    "[95% CI, 0.57-0.68]), irrespective of baseline eGFR (HR of 0.61 [95% CI, 0.52-0.71] "
    "for eGFR >=60) and baseline albuminuria (HR of 0.58 [95% CI, 0.44-0.76])."
)
_TIME_VARYING = (
    "Time-to-event individual patient data were reconstructed from published Kaplan-Meier "
    "plots; time-varying risk ratios (RRs) were calculated in half-, 1-, and 2-year time frames."
)
_RENAL_ENDPOINT = "The risk of the composite renal endpoint was also reduced (0.62, 0.43-0.90; p=0.013)."
_HBA1C_AND_MORTALITY = (
    "SGLT2Is did not significantly reduce HbA1c level (mean difference -0.13, 95%CI: -0.41 to 0.14). "
    "SGLT2Is were associated with a significant reduction in the risk of all-cause mortality "
    "(risk ratio (RR) 0.81, 95%CI: -0.69 to 0.95), cardiac death (RR 0.80, 95%CI: -0.94 to 0.69) "
    "and hospitalisation for heart failure (HHF) (RR 0.69, 95%CI: 0.59-0.81)."
)
_HOSPITALIZATIONS = (
    "The total number of hospitalizations for heart failure was lower in the empagliflozin group "
    "than in the placebo group (hazard ratio, 0.70; 95% CI, 0.58 to 0.85; P<0.001)."
)
_STATIN = (
    "Statin-induced anti-HMGCR antibody IMNM was increased (OR 4.81, 95% CI 1.03 to 22.6, p=0.045). "
    "Diabetes mellitus was increased (OR 2.54, 95% CI 1.02 to 6.29). "
    "Cancer-associated IIM was lower (OR 0.23, 95% CI 0.08 to 0.7)."
)
_PARTICIPANTS = (
    "STUDY SELECTION: Trials including at least 500 participants in each group were eligible. "
    "RESULTS: Among 70 361 participants (mean age 65 years) in 10 randomized trials, "
    "CKD progression was lower (HR 0.62, 95% CI 0.57-0.68)."
)
_LIFE_YEARS = (
    "We identified 75 relevant trials representing 95,444 participants. "
    "The estimated additional number of life-years gained for a 70-year-old patient on ARNi was 5.0 years."
)
_HFREF_SHOULD = (
    "Unless there are specific contraindications, patients with HFrEF should be treated with a beta-blocker."
)
_KIDNEY_BACKGROUND = (
    "Large trials have shown benefit in patients with heart failure or chronic kidney disease. "
    "We identified 13 trials involving 90 413 participants."
)
_WIN = "The stratified win ratio was 1.36 (95% CI 1.09 to 1.68)."


class TestOutcomeSpanAndTurkishLabel(unittest.TestCase):
    def test_leading_preposition_and_subgroup_are_not_the_outcome_name(self):
        findings = extract_grounded_clinical_findings(_ALL_CAUSE)
        by_effect = {item["effect"]: item for item in findings}
        self.assertEqual(by_effect["HR 0.57"]["outcome"].lower(), "all-cause death")
        self.assertNotIn("of all-cause", by_effect["HR 0.57"]["outcome"].lower())
        cell = format_klinik_bulgular_cell(_article("90008101", _ALL_CAUSE))
        visible = _outside_quotes(cell)
        self.assertIn("Sonlanım: tüm nedenlere bağlı ölüm", visible)
        self.assertIn("of all-cause death", cell)
        self.assertNotIn("Sonlanım: of all-cause death", visible)

    def test_treatment_list_and_followed_by_are_rejected(self):
        findings = extract_grounded_clinical_findings(_DRUG_LIST)
        self.assertEqual(len(findings), 3)
        for item in findings:
            self.assertEqual(item["outcome"].lower(), "all-cause death")
            self.assertNotIn("ARNi", item["outcome"])
            self.assertNotIn("followed", item["outcome"].lower())
        table = _format_cross_study_comparison([_article("90008102", _DRUG_LIST)], {})
        findings_cell = _row_cells(table, "90008102")[4]
        self.assertIn("tüm nedenlere bağlı ölüm", findings_cell)
        self.assertNotIn("BB, MRA, ve", findings_cell)
        self.assertNotIn("BB, ve MRA", findings_cell)
        self.assertNotIn(UNTRANSLATED_OUTCOME_LABEL, findings_cell)

    def test_composite_hospitalization_for_hf_is_translated(self):
        findings = extract_grounded_clinical_findings(_COMPOSITE_HF)
        self.assertTrue(findings)
        self.assertIn("hospitalization for HF", findings[0]["outcome"])
        self.assertNotEqual(findings[0]["outcome"], "Results")
        cell = _outside_quotes(format_klinik_bulgular_cell(_article("90008103", _COMPOSITE_HF)))
        self.assertIn("Sonlanım: kardiyovasküler ölüm veya kalp yetersizliği nedeniyle ilk hastaneye yatış", cell)
        self.assertNotIn(UNTRANSLATED_OUTCOME_LABEL, cell)

    def test_egfr_and_albuminuria_modifiers_keep_the_endpoint(self):
        findings = extract_grounded_clinical_findings(_EGFR_SUBGROUP)
        self.assertGreaterEqual(len(findings), 2)
        for item in findings:
            lowered = item["outcome"].lower()
            self.assertNotIn("irrespective", lowered)
            self.assertNotIn("baseline", lowered)
            self.assertIn("ckd progression", lowered)
        visible = _outside_quotes(format_klinik_bulgular_cell(_article("90008104", _EGFR_SUBGROUP)))
        self.assertIn("Sonlanım: kronik böbrek hastalığı progresyonu", visible)
        self.assertNotIn("Sonlanım: irrespective", visible)
        self.assertNotIn("Sonlanım: baseline", visible)

    def test_time_frame_is_not_an_effect_or_an_outcome(self):
        self.assertEqual(extract_grounded_clinical_findings(_TIME_VARYING), [])
        cell = format_klinik_bulgular_cell(_article("90008105", _TIME_VARYING))
        self.assertNotIn("Sonlanım: time-varying", cell)
        self.assertNotIn("risk ratios 1", cell.lower())

    def test_composite_renal_endpoint_and_heart_failure_hospitalizations(self):
        renal = extract_grounded_clinical_findings(_RENAL_ENDPOINT)
        self.assertEqual(renal[0]["outcome"].lower(), "composite renal endpoint")
        self.assertIn("p = 0.013", renal[0]["effect"])
        renal_cell = _outside_quotes(format_klinik_bulgular_cell(_article("90008106", _RENAL_ENDPOINT)))
        self.assertIn("Sonlanım: bileşik böbrek sonlanımı", renal_cell)

        hosp = extract_grounded_clinical_findings(_HOSPITALIZATIONS)[0]
        self.assertIn("hospitalization", hosp["outcome"].lower())
        self.assertNotIn("total number", hosp["outcome"].lower())
        hosp_cell = _outside_quotes(format_klinik_bulgular_cell(_article("90008107", _HOSPITALIZATIONS)))
        self.assertIn("Sonlanım: kalp yetersizliği nedeniyle hastaneye yatış", hosp_cell)

    def test_hba1c_mean_difference_and_signed_ratio_intervals_keep_their_labels(self):
        findings = extract_grounded_clinical_findings(_HBA1C_AND_MORTALITY)
        by_effect = {item["effect"]: item for item in findings}
        self.assertEqual(by_effect["mean difference -0.13"]["outcome"], "HbA1c")
        self.assertEqual(by_effect["mean difference -0.13"]["ci"], "-0.41 ile 0.14")
        self.assertEqual(by_effect["risk ratio 0.81"]["outcome"].lower(), "all-cause mortality")
        self.assertEqual(by_effect["risk ratio 0.81"]["ci"], "-0.69 ile 0.95")
        self.assertEqual(by_effect["RR 0.80"]["outcome"].lower(), "cardiac death")
        self.assertEqual(by_effect["RR 0.80"]["ci"], "-0.94 ile 0.69")
        self.assertIn("heart failure", by_effect["RR 0.69"]["outcome"].lower())
        self.assertEqual(by_effect["RR 0.69"]["ci"], "0.59 ile 0.81")

        cell = format_klinik_bulgular_cell(_article("90008108", _HBA1C_AND_MORTALITY))
        visible = _outside_quotes(cell)
        self.assertIn("Sonlanım: HbA1c", visible)
        self.assertIn("Etki ölçütü: mean difference -0.13", visible)
        self.assertIn("Güven aralığı: -0.41 ile 0.14", visible)
        self.assertIn("Sonlanım: tüm nedenlere bağlı ölüm", visible)
        self.assertIn("Etki ölçütü: risk ratio 0.81", visible)
        self.assertIn("Güven aralığı: -0.69 ile 0.95", visible)
        self.assertIn("Sonlanım: kardiyak ölüm", visible)
        self.assertIn("Etki ölçütü: RR 0.80", visible)
        self.assertIn("Güven aralığı: -0.94 ile 0.69", visible)
        self.assertIn("Sonlanım: kalp yetersizliği nedeniyle hastaneye yatış", visible)
        self.assertNotIn(UNTRANSLATED_OUTCOME_LABEL, visible)
        self.assertLess(visible.find("Etki ölçütü: mean difference -0.13"), visible.find("Güven aralığı: -0.41 ile 0.14"))
        self.assertLess(visible.find("Güven aralığı: -0.41 ile 0.14"), visible.find("Etki ölçütü: risk ratio 0.81"))
        self.assertLess(visible.find("Etki ölçütü: risk ratio 0.81"), visible.find("Güven aralığı: -0.69 ile 0.95"))
        self.assertLess(visible.find("Güven aralığı: -0.69 ile 0.95"), visible.find("Etki ölçütü: RR 0.80"))

    def test_statin_section_5_uses_the_same_map_as_section_6(self):
        article = _article("90008109", _STATIN, title="Immune myopathy", pub_types=["Journal Article"])
        cell = _outside_quotes(format_klinik_bulgular_cell(article))
        table = _row_cells(_format_cross_study_comparison([article], {}), "90008109")[4]
        for label in (
            "statin ilişkili anti-HMGCR antikor pozitif İMNM",
            "diyabet",
            "kanserle ilişkili İİM",
        ):
            self.assertIn(label, cell)
            self.assertIn(label, table)
        self.assertNotIn("Sonlanım: statin-induced", cell)
        self.assertNotIn("Sonlanım: diabetes mellitus", cell)
        self.assertNotIn("Sonlanım: cancer-associated", cell.lower())
        self.assertIn("Diabetes mellitus", format_klinik_bulgular_cell(article))

    def test_win_ratio_display_name(self):
        shown = localize_clinical_display("win ratio 1.36")
        self.assertIn("kazanma oranı (win ratio)", shown)
        self.assertNotIn("win oranı", shown)
        table = _format_cross_study_comparison([_article("90008110", _WIN)], {})
        self.assertIn("kazanma oranı (win ratio)", _row_cells(table, "90008110")[4])


class TestSamplePopulationCell(unittest.TestCase):
    def test_counted_participants_are_kept_and_fragments_are_not(self):
        counted = _article("90008111", _PARTICIPANTS)
        profile = " ".join(
            item["line"] for item in extract_clinical_profile(counted["abstract"]) if item["category"] == "sample"
        )
        self.assertIn("70361 katılımcı", profile)
        self.assertNotIn("500 katılımcı", profile)
        table = _format_cross_study_comparison([counted], {})
        self.assertIn("70361 katılımcı", _row_cells(table, "90008111")[1])
        self.assertNotIn("type 2", _row_cells(table, "90008111")[1].lower())
        self.assertNotIn("diyabet", _row_cells(table, "90008111")[1].lower())

        life = _article("90008112", _LIFE_YEARS)
        life_cell = _row_cells(_format_cross_study_comparison([life], {}), "90008112")[1]
        self.assertIn("95444 katılımcı", life_cell)
        self.assertNotIn("70 yaşında", life_cell)

        should = _article("90008113", _HFREF_SHOULD, pub_types=["Review"])
        should_cell = _row_cells(_format_cross_study_comparison([should], {}), "90008113")[1]
        self.assertEqual(should_cell, "özette bildirilmedi")
        self.assertNotIn("should", should_cell.lower())

        kidney = _article("90008114", _KIDNEY_BACKGROUND)
        kidney_cell = _row_cells(_format_cross_study_comparison([kidney], {}), "90008114")[1]
        self.assertIn("90413 katılımcı", kidney_cell)
        self.assertNotIn("chronic", kidney_cell.lower())
        self.assertNotIn("kidney", kidney_cell.lower())
        self.assertNotRegex(kidney_cell, r"[A-Za-z]{4,}")

    def test_findings_cell_does_not_cut_inside_a_value(self):
        text = (
            "kronik böbrek hastalığı progresyonu: HR 0.61 (GA 0.52 ile 0.71); "
            "kronik böbrek hastalığı progresyonu: HR 0.58 (GA 0.44 ile 0.76)"
        )
        clipped = _findings_cell(text, limit=70)
        self.assertIn("0.61", clipped)
        self.assertIn("0.52 ile 0.71", clipped)
        self.assertNotRegex(clipped, r"\d…")
        self.assertNotIn("0.58", clipped)
        self.assertTrue(clipped.endswith("…"))


if __name__ == "__main__":
    unittest.main()
