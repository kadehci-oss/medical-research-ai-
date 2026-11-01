import unittest
from report_generator import generate_rule_based_turkish_report


class TestSection12StudyTypeWording(unittest.TestCase):
    def test_mostly_case_reports_and_reviews_avoids_empirical_primary_wording(self):
        """
        Regresyon testi (1): Çoğunluğu olgu sunumu/derleme olan mock makale listesiyle
        rapor üret ve 'ampirik primer araştırmalar' ifadesinin geçmediğini,
        tür sayılarının doğru olduğunu doğrula.
        """
        articles = [
            # 1. Olgu sunumu (Review/Case report pool)
            {
                "pmid": "90001",
                "title": "A 45-year-old female with anti-NMDA receptor encephalitis: a case report",
                "abstract": "We present a case of a 45-year-old female with anti-NMDA receptor encephalitis treated with rituximab.",
                "publication_types": ["Case Reports"],
                "pub_year": "2023",
                "authors": ["Demir A", "Yilmaz B"],
                "journal": "J Neuroimmunol",
            },
            # 2. Derleme (Review pool)
            {
                "pmid": "90002",
                "title": "Treatment strategies in anti-NMDA receptor encephalitis: a literature review",
                "abstract": "This review summarizes treatment strategies and immunotherapy outcomes in autoimmune encephalitis.",
                "publication_types": ["Review"],
                "pub_year": "2022",
                "authors": ["Kaya C"],
                "journal": "Neurol Sci",
            },
            # 3. Kohort çalışması (Primary pool)
            {
                "pmid": "90003",
                "title": "Long-term outcomes of immunotherapy in anti-NMDA encephalitis cohort",
                "abstract": "A prospective cohort study of 60 patients with anti-NMDA receptor encephalitis followed for 2 years (n = 60). Rituximab improved outcomes (HR 0.65, 95% CI 0.45-0.90, p = 0.01).",
                "publication_types": ["Observational Study", "Cohort Studies"],
                "pub_year": "2021",
                "authors": ["Ozturk D", "Ak E"],
                "journal": "Brain",
            },
            # 4. Olgu serisi (Primary pool - case series not excluded by _excluded_from_primary_pool)
            {
                "pmid": "90004",
                "title": "Clinical characteristics of 5 patients with anti-NMDA receptor encephalitis: a case series",
                "abstract": "We describe a case series of 5 patients diagnosed with anti-NMDA receptor encephalitis (n = 5).",
                "publication_types": ["Journal Article"],
                "pub_year": "2020",
                "authors": ["Celik S"],
                "journal": "Eur J Neurol",
            },
        ]

        query = "anti-NMDA receptor encephalitis treatment"
        report = generate_rule_based_turkish_report(query, articles)

        self.assertIn("## 12. Klinik Sonuç", report)
        section_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # "ampirik primer araştırmalar" ifadesi geçmemeli
        self.assertNotIn("ampirik primer araştırmalar", section_12)

        # Tür sayıları ve format doğrulanmalı
        # Primary pool'da 2 çalışma olmalı (1 kohort, 1 olgu serisi)
        self.assertIn("bu bölümde 2 kayıt yer alıyor:", section_12)
        self.assertIn("1 Kohort Çalışması (Gözlemsel)", section_12)
        self.assertIn("1 Olgu Serisi", section_12)

        # Review pool'daki çalışmalar için ilgili derleme/olgu sunumu bloğu bulunmalı
        self.assertIn("kesin tedavi etkinliği çıkarılmamıştır", section_12)
        self.assertIn("[PMID: 90001]", section_12)
        self.assertIn("[PMID: 90002]", section_12)

    def test_only_rct_and_cohort_reflects_exact_study_types_and_counts(self):
        """
        Regresyon testi (2): Yalnızca RCT/kohort içeren listede ifadenin
        yine doğru sayılarla yazıldığını doğrula.
        """
        articles = [
            {
                "pmid": "91001",
                "title": "Rituximab versus placebo in autoimmune encephalitis: a randomized controlled trial",
                "abstract": "A randomized controlled trial evaluating rituximab in 120 patients (n = 120). Primary outcome was mRS improvement (RR 1.45, 95% CI 1.10-1.90, p = 0.008).",
                "publication_types": ["Randomized Controlled Trial"],
                "pub_year": "2023",
                "authors": ["Smith J", "Doe A"],
                "journal": "Lancet Neurol",
            },
            {
                "pmid": "91002",
                "title": "Second-line immunotherapy in autoimmune encephalitis: randomized trial",
                "abstract": "In this randomized controlled trial of 80 patients (n = 80), cyclophosphamide was compared with rituximab (p = 0.04).",
                "publication_types": ["Randomized Controlled Trial"],
                "pub_year": "2022",
                "authors": ["Brown K"],
                "journal": "Neurology",
            },
            {
                "pmid": "91003",
                "title": "Observational cohort study of long-term prognosis in autoimmune encephalitis",
                "abstract": "A multicenter cohort study followed 250 patients for 5 years (n = 250, HR 0.70, p = 0.02).",
                "publication_types": ["Cohort Studies"],
                "pub_year": "2021",
                "authors": ["Taylor R", "White G"],
                "journal": "Ann Neurol",
            },
        ]

        query = "autoimmune encephalitis immunotherapy"
        report = generate_rule_based_turkish_report(query, articles)

        self.assertIn("## 12. Klinik Sonuç", report)
        section_12 = report.split("## 12. Klinik Sonuç")[1].split("## 13. Doğrulanmış Kaynakça")[0]

        # "ampirik primer araştırmalar" ifadesi geçmemeli
        self.assertNotIn("ampirik primer araştırmalar", section_12)

        # Primary pool'da 3 kayıt var: 2 RCT, 1 Kohort
        self.assertIn("bu bölümde 3 kayıt yer alıyor:", section_12)
        self.assertIn("2 Rastgele Kontrollü Çalışma (RCT)", section_12)
        self.assertIn("1 Kohort Çalışması (Gözlemsel)", section_12)
        self.assertIn("Klinik verileri ve nicel etki ölçütlerini ortaya koymaktadır:", section_12)


if __name__ == "__main__":
    unittest.main()
