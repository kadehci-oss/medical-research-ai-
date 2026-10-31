import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import requests

from live_ncbi_validation import run


class TestLiveNcbiValidation(unittest.TestCase):
    def test_error_artifact_does_not_include_request_credentials(self):
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                with patch.dict(os.environ, {"NCBI_API_KEY": "test-secret"}), patch(
                    "live_ncbi_validation.get",
                    side_effect=requests.ConnectionError(
                        "Connection failed: https://eutils.ncbi.nlm.nih.gov/?api_key=test-secret"
                    ),
                ), redirect_stdout(io.StringIO()):
                    exit_code = run()

                artifact = Path("ncbi_live_results.json").read_text(encoding="utf-8")
            finally:
                os.chdir(previous_cwd)

        report = json.loads(artifact)
        self.assertEqual(exit_code, 1)
        self.assertNotIn("test-secret", artifact)
        self.assertNotIn("api_key=", artifact)
        self.assertEqual(report["checks"][0]["error_type"], "ConnectionError")


if __name__ == "__main__":
    unittest.main()
