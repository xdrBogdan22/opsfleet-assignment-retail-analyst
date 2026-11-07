import pytest
from langchain_core.runnables import RunnableWithFallbacks

from retail_analyst.core.config import ModelEntry, get_settings
from retail_analyst.llm.models import FALLBACK_ERRORS, build_chat_model

SETTINGS = get_settings().models


def with_models(*entries: ModelEntry):  # type: ignore[no-untyped-def]
    return SETTINGS.model_copy(update={"models": list(entries)})


def test_enabled_gemini_models_form_a_fallback_chain() -> None:
    model = build_chat_model(SETTINGS, tools=[])
    assert isinstance(model, RunnableWithFallbacks)
    assert len(model.fallbacks) == len(SETTINGS.enabled) - 1
    assert model.exceptions_to_handle == FALLBACK_ERRORS


def test_enabled_provider_without_a_client_fails_fast() -> None:
    settings = with_models(ModelEntry(provider="anthropic", name="claude-sonnet-5-5", enabled=True))
    with pytest.raises(ValueError, match="anthropic"):
        build_chat_model(settings, tools=[])


def test_no_enabled_model_fails_fast() -> None:
    settings = with_models(ModelEntry(provider="google_genai", name="gemini-3.8-flash", enabled=False))
    with pytest.raises(ValueError, match="No model"):
        build_chat_model(settings, tools=[])
