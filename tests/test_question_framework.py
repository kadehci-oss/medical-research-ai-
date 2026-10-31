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


if __name__ == "__main__":
    unittest.main()
