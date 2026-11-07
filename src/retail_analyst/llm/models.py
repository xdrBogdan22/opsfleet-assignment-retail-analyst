"""Builds the chat model with the fallback chain from config/agent/models.yaml.

The next model is tried only for errors another model could survive: rate
limits, server errors, timeouts, lost connections and a missing model. A bad
request or a permission error fails at once, because every model would fail
the same way (P10).
"""

from collections.abc import Sequence

from langchain_core.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelNotFoundError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from retail_analyst.core.config import Models

CONFIG_FILE = "config/agent/models.yaml"
FALLBACK_ERRORS = (
    ModelRateLimitError,
    ModelAPIError,
    ModelTimeoutError,
    ModelConnectionError,
    ModelNotFoundError,
)


def build_chat_model(settings: Models, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, AIMessage]:
    unsupported = [m.provider for m in settings.enabled if m.provider != "google_genai"]
    if unsupported:
        raise ValueError(f"No client for provider(s) {unsupported}. Disable them in {CONFIG_FILE}.")
    if not settings.enabled:
        raise ValueError(f"No model is enabled in {CONFIG_FILE}.")

    chain = [
        ChatGoogleGenerativeAI(
            model=entry.name,
            temperature=settings.temperature,
            max_retries=settings.attempts_per_model,
            timeout=settings.call_timeout_seconds,
        ).bind_tools(tools)
        for entry in settings.enabled
    ]
    primary, *fallbacks = chain
    if not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks, exceptions_to_handle=FALLBACK_ERRORS)
