"""Calls real Gemini. Two short calls per run, skipped without GOOGLE_API_KEY."""

import os

import pytest
from dotenv import load_dotenv

from retail_analyst.core.config import ModelEntry, get_settings
from retail_analyst.llm.models import build_chat_model

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="needs GOOGLE_API_KEY"),
]

SETTINGS = get_settings().models
PROMPT = "Reply with the single word: ok"


def test_configured_chain_answers() -> None:
    reply = build_chat_model(SETTINGS, tools=[]).invoke(PROMPT)
    assert "ok" in reply.text.lower()


def test_missing_primary_model_falls_back() -> None:
    missing = ModelEntry(provider="google_genai", name="gemini-does-not-exist", enabled=True)
    fallback = SETTINGS.enabled[-1]
    settings = SETTINGS.model_copy(update={"models": [missing, fallback]})
    reply = build_chat_model(settings, tools=[]).invoke(PROMPT)
    assert "ok" in reply.text.lower()
