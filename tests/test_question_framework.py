"""Category 1 — question-type and framework selection (no forced PICO)."""
import unittest

import question_framework as qf


class TestQuestionFramework(unittest.TestCase):
    CASES = {
        "Empagliflozin versus placebo in heart failure": ("therapy", "PICO"),
        "Diagnostic accuracy of MRCP versus ultrasonography in obstructive jaundice": ("diagnosis", "PIRD"),
        "Prognosis of post-stroke epilepsy and seizure recurrence": ("prognosis", "PFO"),
        "Oral contraceptive use and risk of colorectal cancer": ("etiology", "PEO / PECO"),
        "Prevalence of Toscana virus meningitis in Austria": ("epidemiology", "CoCoPop"),
        "Low-dose CT screening for lung cancer mortality": ("screening", "PICO (tarama programı)"),
        "Tirzepatide adverse events and safety in obesity": ("safety", "PECO"),
        "Laparoscopic versus open cholecystectomy postoperative complications": ("surgery", "PICO (girişim = cerrahi işlem)"),
        "Cost-effectiveness of teleradiology services in rural hospitals": ("health_services", "SPICE"),
        "Beyin kanamasında konik ışınlı BT tanısal doğruluğu": ("diagnosis", "PIRD"),
    }

    def test_question_types(self):
        for query, (qtype, framework) in self.CASES.items():
            selection = qf.select_question_framework(query)
            self.assertEqual(selection["question_type"], qtype, query)
            self.assertTrue(selection["framework"].startswith(framework.split(" ")[0]), query)

    def test_spice_preserves_explicit_cost_evaluation_measure(self):
        english = qf.select_question_framework(
            "Cost-effectiveness of teleradiology services in rural hospitals"
        )
        english_elements = {element["key"]: element["value"] for element in english["elements"]}
        self.assertEqual(english_elements["E"], "Cost-effectiveness")
        self.assertEqual(english_elements["I"], "teleradiology services")

        turkish = qf.select_question_framework("Teleradyoloji hizmetlerinde maliyet-etkililik")
        turkish_elements = {element["key"]: element["value"] for element in turkish["elements"]}
        self.assertEqual(turkish_elements["E"], "maliyet-etkililik")
        self.assertEqual(turkish_elements["I"], "Teleradyoloji hizmetlerinde")

    def test_unstated_elements_are_not_filled(self):
        selection = qf.select_question_framework("Diagnostic accuracy of MRCP versus ultrasonography in obstructive jaundice")
        elements = {e["key"]: e for e in selection["elements"]}
        self.assertEqual(elements["I"]["value"], "MRCP")
        self.assertEqual(elements["R"]["value"], qf.NOT_STATED_TR)
        self.assertEqual(elements["R"]["source"], "yok")

    def test_markdown_states_framework_is_not_forced(self):
        text = qf.render_framework_markdown(qf.select_question_framework("Prognosis of febrile seizures"))
        self.assertIn("PICO zorlanmadı", text)
        self.assertIn("PFO", text)



class QuestionTypeCoverage(unittest.TestCase):
    """Eight research types, Turkish and English queries; PICO is not forced."""

    CASES = {
        "therapy": ["SGLT2 inhibitors vs placebo in heart failure", "kalp yetersizliğinde empagliflozin etkinliği",
                    "metformin tedavisi tip 2 diyabette HbA1c"],
        "diagnosis": ["diagnostic accuracy of MRI for cervical rib", "troponin duyarlılık özgüllük miyokard enfarktüsü tanısı",
                      "ultrasonografi apandisit tanısında doğruluk"],
        "prognosis": ["prognostic factors for survival in glioblastoma", "anti-NMDA ensefalitinde uzun dönem prognoz",
                      "sepsiste mortaliteyi öngören faktörler"],
        "screening": ["lung cancer screening with low-dose CT", "meme kanseri taramasında mamografi",
                      "kolorektal kanser taraması kolonoskopi"],
        "epidemiology": ["prevalence of hypothyroidism in adults", "Türkiye'de diyabet prevalansı",
                         "çocuklarda astım insidansı"],
        "surgery": ["laparoscopic versus open appendectomy outcomes", "torasik çıkış sendromunda cerrahi dekompresyon",
                    "bariatrik cerrahi sonrası kilo kaybı"],
        "safety": ["statin induced myopathy risk", "amoksisilin yan etkileri çocuklarda",
                   "isotretinoin adverse events depression"],
        "health_services": ["telemedicine follow-up cost-effectiveness", "acil serviste bekleme süresi ve hasta memnuniyeti",
                            "hospital readmission quality improvement program"],
    }

    def test_each_type_selects_its_framework(self):
        for expected, queries in self.CASES.items():
            for query in queries:
                with self.subTest(query=query):
                    self.assertEqual(qf.classify_question_type(query), expected)

    def test_non_therapy_questions_do_not_get_plain_pico(self):
        for expected, queries in self.CASES.items():
            if expected in ("therapy", "surgery", "screening"):
                continue
            for query in queries:
                with self.subTest(query=query):
                    self.assertNotEqual(qf.select_question_framework(query)["framework"], "PICO")


if __name__ == "__main__":
    unittest.main()
