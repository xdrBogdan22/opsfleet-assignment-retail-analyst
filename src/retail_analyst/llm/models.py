"""Builds the chat model with the fallback chain from config/agent/models.yaml.

The next model is tried only for errors another model could survive: rate
limits, server errors, timeouts, lost connections and a missing model. A bad
request or a permission error fails at once, because every model would fail
the same way (P10).

Every model except the last sits behind a circuit breaker, so a model that
keeps failing is skipped for a while instead of costing time on each call.
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
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from retail_analyst.core.config import Models
from retail_analyst.llm.breaker import CircuitBreaker, CircuitOpenError

ChatModel = Runnable[LanguageModelInput, AIMessage]

CONFIG_FILE = "config/agent/models.yaml"
FALLBACK_ERRORS = (
    ModelRateLimitError,
    ModelAPIError,
    ModelTimeoutError,
    ModelConnectionError,
    ModelNotFoundError,
    CircuitOpenError,
)


def build_breakers(settings: Models) -> dict[str, CircuitBreaker]:
    """One breaker per model, shared by every chain built in the process."""
    failures, cooldown = settings.breaker_failures, settings.breaker_cooldown_seconds
    return {m.name: CircuitBreaker(failures, cooldown) for m in settings.enabled}


def build_chat_model(
    settings: Models, tools: Sequence[BaseTool], breakers: dict[str, CircuitBreaker] | None = None
) -> ChatModel:
    unsupported = [m.provider for m in settings.enabled if m.provider != "google_genai"]
    if unsupported:
        raise ValueError(f"No client for provider(s) {unsupported}. Disable them in {CONFIG_FILE}.")
    if not settings.enabled:
        raise ValueError(f"No model is enabled in {CONFIG_FILE}.")

    breakers = breakers or build_breakers(settings)
    chain: list[ChatModel] = []
    for position, entry in enumerate(settings.enabled, start=1):
        model = ChatGoogleGenerativeAI(
            model=entry.name,
            temperature=settings.temperature,
            max_retries=settings.attempts_per_model,
            timeout=settings.call_timeout_seconds,
        ).bind_tools(tools)
        is_last = position == len(settings.enabled)
        chain.append(model if is_last else _guarded(model, breakers[entry.name]))

    primary, *fallbacks = chain
    if not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks, exceptions_to_handle=FALLBACK_ERRORS)


def _guarded(model: ChatModel, breaker: CircuitBreaker) -> ChatModel:
    def call(messages: LanguageModelInput, config: RunnableConfig) -> AIMessage:
        if not breaker.allows_call():
            raise CircuitOpenError
        try:
            reply = model.invoke(messages, config)
        except FALLBACK_ERRORS:
            breaker.record_failure()
            raise
        breaker.record_success()
        return reply

    return RunnableLambda(call)
