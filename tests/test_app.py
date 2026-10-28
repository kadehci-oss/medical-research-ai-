import unittest
import app


class TestAppImports(unittest.TestCase):

    def test_app_imports_and_functions(self):
        """Verify app module imports correctly and exported functions exist."""
        self.assertTrue(hasattr(app, "search_pubmed"))
        self.assertTrue(callable(app.search_pubmed))

        self.assertTrue(hasattr(app, "verify_pmid"))
        self.assertTrue(callable(app.verify_pmid))

        self.assertTrue(hasattr(app, "verify_doi"))
        self.assertTrue(callable(app.verify_doi))

        self.assertTrue(hasattr(app, "generate_turkish_evidence_report"))
        self.assertTrue(callable(app.generate_turkish_evidence_report))

        self.assertTrue(hasattr(app, "generate_evidence_table_html"))
        self.assertTrue(callable(app.generate_evidence_table_html))

        self.assertTrue(hasattr(app, "generate_html_report"))
        self.assertTrue(callable(app.generate_html_report))

        self.assertTrue(hasattr(app, "perform_red_team_audit"))
        self.assertTrue(callable(app.perform_red_team_audit))

        self.assertTrue(hasattr(app, "classify_study_design"))
        self.assertTrue(callable(app.classify_study_design))

    def test_app_main_callable(self):
        """Verify main entrypoint function in app.py exists."""
        self.assertTrue(hasattr(app, "main"))
        self.assertTrue(callable(app.main))


if __name__ == "__main__":
    unittest.main()
