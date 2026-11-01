import unittest
import re
from report_generator import (
    extract_article_clinical_details,
    _raise_initial,
    _significance_from_findings,
    _format_bound_claims,
    _intervention_comparison_cell,
    PICO_UNSTATED_TR,
    generate_rule_based_turkish_report,
)
from tools.report_quality_audit import audit_report_quality


class TestConsistencyFixesRegression(unittest.TestCase):
    """Regresyon testleri: Örneklem tutarlılığı, etiket birliği, İ yazımı, sınırda p, kaynak cümleler."""

    def test_sample_size_populated_from_patient_group(self):
        # PMID 36797460 (Lam): Hasta grubunda kayıtlı n varsa Örneklem aynı kaynaktan doldurulmalı
        article = {
            "pmid": "36797460",
            "title": "Intravenous immunoglobulin resistance in Kawasaki disease patients: prediction using clinical data.",
            "publication_types": ["Cohort Studies"],
            "abstract": (
                "BACKGROUND: About 10-20% of Kawasaki disease (KD) patients are resistant to the initial infusion of intravenous immunoglobin (IVIG).\n"
                "METHODS: Data were from two cohorts: a Korean cohort of 7101 KD patients from 2015 to 2017 and a cohort of 649 KD patients from San Diego enrolled from 1998 to 2021.\n"
                "RESULTS: Five machine learning models achieved a maximum median AUC of 0.711 [IQR: 0.706-0.72] in the Korean cohort.\n"
                "CONCLUSIONS: Clinical laboratory data alone is not sufficient to predict IVIG resistance."
            ),
        }
        details = extract_article_clinical_details(article, "Kawasaki disease IVIG resistance")
        self.assertIn("7101 hasta", details["patient_group"])
        self.assertEqual(details["sample_size"], "n = 7101")
        self.assertNotEqual(details["sample_size"], "özette bildirilmedi")
        self.assertEqual(details["provenance"]["sample_size"]["value"], "n = 7101")
        self.assertIn("7101 KD patients", details["provenance"]["sample_size"]["source_sentence"])

    def test_label_uniformity_ozette_bildirilmedi(self):
        # Etiket birliği: PICO_UNSTATED_TR 'özette bildirilmedi' olmalı ve Müdahale sütununda 'Belirtilmedi' veya 'açıkça' yerine 'özette bildirilmedi' kullanılmalı
        self.assertEqual(PICO_UNSTATED_TR, "özette bildirilmedi")

        cell = _intervention_comparison_cell([], abstract="", title="")
        self.assertEqual(cell, "özette bildirilmedi")
        self.assertNotEqual(cell, "Belirtilmedi")
        self.assertNotEqual(cell, "özette açıkça bildirilmedi")

    def test_turkish_capitalization_i_dotted(self):
        # Yazım: 'intravenöz immünoglobulin' cümle başında 'İntravenöz immünoglobulin' olmalı
        raised = _raise_initial("intravenöz immünoglobulin (IVIG)")
        self.assertTrue(raised.startswith("İntravenöz"))
        self.assertFalse(raised.startswith("Intravenöz"))

        raised_i = _raise_initial("immünosupresif")
        self.assertEqual(raised_i, "İmmünosupresif")

        raised_dotless = _raise_initial("ılık su")
        self.assertEqual(raised_dotless, "Ilık su")

    def test_borderline_p_value_wording(self):
        # Sınırda p: Akca (PMID 33753891) p = 0.050 satırı 'sınırda (p = 0.050); anlamlılık eşiğini aşmadı' demeli
        finding = {
            "outcome": "öngördürücü: GGT düzeyi",
            "effect": "OR 1.008",
            "ci": "1.001 ile 1.015",
            "p": "p = 0.050",
            "ci_low": "1.001",
            "ci_high": "1.015",
            "measure": "OR",
        }
        res = _significance_from_findings([finding])
        self.assertIn("sınırda (p = 0.050); anlamlılık eşiğini aşmadı", res)
        self.assertNotIn("farklı yön", res)

        # Gerçek bir GA yoksa GA'dan bahsedilmemeli
        finding_no_ci = {
            "outcome": "test sonlanım",
            "effect": "HR 1.20",
            "ci": "özette bildirilmedi",
            "p": "p = 0.050",
            "measure": "HR",
        }
        res_no_ci = _significance_from_findings([finding_no_ci])
        self.assertIn("sınırda (p = 0.050); anlamlılık eşiğini aşmadı", res_no_ci)
        self.assertNotIn("güven aralığı", res_no_ci.lower())

    def test_cross_block_source_sentence_quoting(self):
        # Farklı bloklarda bağımsız çağrıldığında alıntının kendisi tam olarak gösterilmeli
        details = {
            "provenance": {
                "pmid": "12345678",
                "population": {
                    "value": "100 hasta",
                    "source_sentence": "We evaluated 100 patients with the disease.",
                    "source": "abstract",
                },
                "sample_size": {
                    "value": "n = 100",
                    "source_sentence": "We evaluated 100 patients with the disease.",
                    "source": "abstract",
                },
                "intervention": {
                    "value": "İlaç A",
                    "source_sentence": "Patients received Drug A.",
                    "source": "abstract",
                },
                "comparison": {
                    "value": "özette bildirilmedi",
                    "source_sentence": "",
                    "source": "missing",
                },
                "outcomes": [],
            }
        }
        # Blok 1
        block1 = _format_bound_claims(details)
        self.assertIn('Kaynak cümle: "We evaluated 100 patients with the disease."', block1)
        self.assertIn("Kaynak cümle: yukarıdaki ile aynı", block1)

        # Blok 2 (başka bir blokta formatlandığında)
        block2 = _format_bound_claims(details)
        self.assertIn('Kaynak cümle: "We evaluated 100 patients with the disease."', block2)
        # Blok 2 de kendi içinde ilk geçen için cümleyi vermeli, sıfırlanmış olmalı
        self.assertTrue(block2.startswith("*Kaynağa bağlı öğeler (PMID: 12345678):* Hasta grubu: 100 hasta. Kaynak cümle: \"We evaluated 100 patients with the disease.\""))

    def test_report_quality_audit_on_mock_report(self):
        # tools/report_quality_audit.py denetimi
        article = {
            "pmid": "36797460",
            "title": "Intravenous immunoglobulin resistance in Kawasaki disease patients: prediction using clinical data.",
            "publication_types": ["Cohort Studies"],
            "abstract": (
                "BACKGROUND: About 10-20% of Kawasaki disease (KD) patients are resistant to the initial infusion of intravenous immunoglobin (IVIG).\n"
                "METHODS: Data were from two cohorts: a Korean cohort of 7101 KD patients from 2015 to 2017 and a cohort of 649 KD patients from San Diego enrolled from 1998 to 2021.\n"
                "RESULTS: Five machine learning models achieved a maximum median AUC of 0.711 [IQR: 0.706-0.72] in the Korean cohort.\n"
                "CONCLUSIONS: Clinical laboratory data alone is not sufficient to predict IVIG resistance."
            ),
        }
        report = generate_rule_based_turkish_report("Kawasaki disease IVIG resistance", [article])
        audit_res = audit_report_quality(report)
        self.assertEqual(audit_res["summary"]["critical_issues"], 0)
        self.assertTrue(audit_res["summary"]["passed_critical"])
        self.assertIn("Uzman Hekim Değerlendirmesi: Yapılmadı", report)
        self.assertNotIn("Intravenöz immünoglobulin (IVIG)", report)
        self.assertIn("İntravenöz immünoglobulin (IVIG)", report)


if __name__ == "__main__":
    unittest.main()
