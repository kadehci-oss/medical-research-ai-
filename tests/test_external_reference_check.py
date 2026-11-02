"""External reference check (PR #64's eight PubMed cases) must not regress.

The first run is frozen in validation/external_pr64_first_run_results.json and is
the independent estimate. This test only guards the current engine against new
false extractions on the same records.
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "validation", "run_external_reference_check.py")


class ExternalReferenceCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run([sys.executable, RUNNER, "--no-write"], capture_output=True, text=True, timeout=600,
                             cwd=ROOT, check=True).stdout
        summaries = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
        cls.current = summaries[-1]

    def test_no_false_extraction(self):
        self.assertEqual(self.current["wrong"], 0, self.current)

    def test_complete_cases_do_not_drop(self):
        self.assertGreaterEqual(self.current["complete_cases"], 7, self.current)

    def test_frozen_first_run_is_kept(self):
        with open(os.path.join(ROOT, "validation", "external_pr64_first_run_results.json"), encoding="utf-8") as fh:
            frozen = json.load(fh)
        self.assertEqual(frozen["engine_commit"], "0e58b02")
        self.assertEqual(frozen["summary"]["cases"], 8)


if __name__ == "__main__":
    unittest.main()
