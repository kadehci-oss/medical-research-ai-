"""LLM provider selection for the optional report synthesis step.

Two OpenAI-compatible backends are supported:

* ``openai``    – the OpenAI API (default, previous behaviour).
* ``omniroute`` – a self-hosted OmniRoute AI gateway, which exposes an
  OpenAI-compatible ``/v1`` endpoint and routes requests to the upstream
  providers configured in its dashboard (with fallback).

The gateway URL is read only from the server environment
(``OMNIROUTE_BASE_URL``); API clients can choose the provider but never the
URL, so the endpoint cannot be used to make the server call arbitrary hosts.
"""

import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_PROVIDER = "openai"
OMNIROUTE_DEFAULT_BASE_URL = "http://localhost:20128/v1"
SUPPORTED_PROVIDERS = ("openai", "omniroute")


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    label: str
    # Turkish dative form used in data-transfer disclosures ("...'ye gönderildi").
    destination_dative: str
    base_url: Optional[str]
    api_key_env: str
    default_model: Optional[str]


def normalize_provider(provider: Optional[str]) -> str:
    """Return a supported provider id; falls back to ``LLM_PROVIDER`` then ``openai``."""
    value = (provider or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {value!r}")
    return value


def get_provider_config(provider: Optional[str] = None) -> LLMProviderConfig:
    name = normalize_provider(provider)
    if name == "omniroute":
        base_url = (os.environ.get("OMNIROUTE_BASE_URL") or OMNIROUTE_DEFAULT_BASE_URL).strip().rstrip("/")
        return LLMProviderConfig(
            provider="omniroute",
            label="OmniRoute",
            destination_dative=(
                "OmniRoute ağ geçidine (ve ağ geçidinin yönlendirdiği yapay zekâ sağlayıcısına)"
            ),
            base_url=base_url,
            api_key_env="OMNIROUTE_API_KEY",
            default_model=(os.environ.get("OMNIROUTE_MODEL") or "").strip() or None,
        )
    return LLMProviderConfig(
        provider="openai",
        label="OpenAI",
        destination_dative="OpenAI'ye",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        default_model=None,
    )


def resolve_api_key(config: LLMProviderConfig, api_key: Optional[str]) -> Optional[str]:
    """Explicit key wins; for OmniRoute fall back to ``OMNIROUTE_API_KEY``.

    The OpenAI path keeps its previous behaviour: the caller must pass the key.
    """
    if api_key and api_key.strip():
        return api_key.strip()
    if config.provider == "omniroute":
        env_key = (os.environ.get(config.api_key_env) or "").strip()
        return env_key or None
    return None


def resolve_model(config: LLMProviderConfig, model: Optional[str], fallback: str = "gpt-4o-mini") -> str:
    if model and model.strip():
        return model.strip()
    return config.default_model or fallback
