import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from llm_provider import (
    OMNIROUTE_DEFAULT_BASE_URL,
    get_provider_config,
    normalize_provider,
    resolve_api_key,
    resolve_model,
)
from report_generator import generate_turkish_evidence_report
from tests.test_report_generator import SAMPLE_ARTICLES

client = TestClient(app)
_VERIFIED = {"status": "verified", "verified": True, "reason": "match"}


class TestProviderConfig(unittest.TestCase):
    def test_default_provider_is_openai(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = get_provider_config(None)
        self.assertEqual(cfg.provider, "openai")
        self.assertIsNone(cfg.base_url)

    def test_env_selects_omniroute_with_default_url(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "OmniRoute"}, clear=True):
            cfg = get_provider_config(None)
        self.assertEqual(cfg.provider, "omniroute")
        self.assertEqual(cfg.base_url, OMNIROUTE_DEFAULT_BASE_URL)

    def test_base_url_and_model_come_from_env(self):
        env = {"OMNIROUTE_BASE_URL": "http://gateway:20128/v1/", "OMNIROUTE_MODEL": "medical-combo"}
        with patch.dict(os.environ, env, clear=True):
            cfg = get_provider_config("omniroute")
        self.assertEqual(cfg.base_url, "http://gateway:20128/v1")
        self.assertEqual(resolve_model(cfg, None), "medical-combo")
        self.assertEqual(resolve_model(cfg, "gpt-4o"), "gpt-4o")

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            normalize_provider("other")

    def test_api_key_env_fallback_only_for_omniroute(self):
        with patch.dict(os.environ, {"OMNIROUTE_API_KEY": "omni-key", "OPENAI_API_KEY": "sk-env"}, clear=True):
            self.assertEqual(resolve_api_key(get_provider_config("omniroute"), None), "omni-key")
            self.assertEqual(resolve_api_key(get_provider_config("omniroute"), " explicit "), "explicit")
            self.assertIsNone(resolve_api_key(get_provider_config("openai"), None))


class TestOmniRouteReportPath(unittest.TestCase):
    def _run(self, provider, env, api_key="omni-key"):
        with patch.dict(os.environ, env, clear=True), patch(
            "report_generator.verify_citation", return_value=_VERIFIED
        ), patch("report_generator.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.side_effect = Exception("boom")
            report = generate_turkish_evidence_report(
                "SGLT2 inhibitors",
                SAMPLE_ARTICLES,
                api_key=api_key,
                use_llm=True,
                model="medical-combo",
                allow_external_data_transfer=True,
                llm_provider=provider,
            )
        return mock_openai, report

    def test_omniroute_client_uses_gateway_base_url(self):
        mock_openai, report = self._run("omniroute", {"OMNIROUTE_BASE_URL": "http://gw:20128/v1"})
        mock_openai.assert_called_once_with(api_key="omni-key", base_url="http://gw:20128/v1")
        self.assertEqual(
            mock_openai.return_value.chat.completions.create.call_args.kwargs["model"], "medical-combo"
        )
        self.assertIn("OmniRoute sentezi üretilemedi", report)
        self.assertIn("OmniRoute ağ geçidine", report)
        self.assertNotIn("boom", report)

    def test_omniroute_uses_server_key_when_none_given(self):
        mock_openai, _ = self._run("omniroute", {"OMNIROUTE_API_KEY": "server-key"}, api_key=None)
        self.assertEqual(mock_openai.call_args.kwargs["api_key"], "server-key")

    def test_openai_client_has_no_base_url_override(self):
        mock_openai, report = self._run("openai", {}, api_key="sk-test")
        mock_openai.assert_called_once_with(api_key="sk-test")
        self.assertIn("OpenAI sentezi üretilemedi", report)

    def test_omniroute_not_called_without_consent(self):
        with patch.dict(os.environ, {"OMNIROUTE_API_KEY": "server-key"}, clear=True), patch(
            "report_generator.verify_citation", return_value=_VERIFIED
        ), patch("report_generator.OpenAI") as mock_openai:
            report = generate_turkish_evidence_report(
                "SGLT2 inhibitors", SAMPLE_ARTICLES, use_llm=True, llm_provider="omniroute"
            )
        mock_openai.assert_not_called()
        self.assertIn("OmniRoute ağ geçidine", report)
        self.assertIn("açık onay verilmedi", report)


class TestOmniRouteApi(unittest.TestCase):
    @patch("api.verify_citation")
    def test_server_key_still_requires_consent(self, mock_verify):
        payload = {"query": "diabetes", "articles": [{"pmid": "12345"}], "use_llm": True, "llm_provider": "omniroute"}
        with patch.dict(os.environ, {"OMNIROUTE_API_KEY": "server-key"}):
            response = client.post("/api/report", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("OmniRoute", response.json()["detail"])
        mock_verify.assert_not_called()

    def test_unknown_provider_is_rejected(self):
        payload = {"query": "diabetes", "articles": [{"pmid": "12345"}], "llm_provider": "evil"}
        self.assertEqual(client.post("/api/report", json=payload).status_code, 422)

    def test_base_url_cannot_be_set_by_client(self):
        from api import ReportRequest

        self.assertNotIn("base_url", ReportRequest.model_fields)


if __name__ == "__main__":
    unittest.main()
