from typing import Any

import pytest
from langchain_core.exceptions import ModelAPIError, ModelInvalidRequestError
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from retail_analyst.llm.breaker import CircuitBreaker, CircuitOpenError
from retail_analyst.llm.models import _guarded


class FlakyModel:
    def __init__(self, error: Exception | None):
        self.error = error
        self.calls = 0

    def runnable(self) -> Any:
        def call(_: object) -> AIMessage:
            self.calls += 1
            if self.error:
                raise self.error
            return AIMessage("ok")

        return RunnableLambda(call)


def test_breaker_opens_after_repeated_failures_and_skips_the_model() -> None:
    model = FlakyModel(ModelAPIError("503"))
    guarded = _guarded(model.runnable(), CircuitBreaker(failures_to_open=2, cooldown_seconds=60))
    for _ in range(2):
        with pytest.raises(ModelAPIError):
            guarded.invoke("hi")
    with pytest.raises(CircuitOpenError):
        guarded.invoke("hi")
    assert model.calls == 2


def test_breaker_lets_one_call_through_after_the_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("retail_analyst.llm.breaker.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failures_to_open=1, cooldown_seconds=60)
    breaker.record_failure()
    assert not breaker.allows_call()
    clock[0] += 61
    assert breaker.allows_call()


def test_errors_another_model_cannot_fix_do_not_open_the_breaker() -> None:
    model = FlakyModel(ModelInvalidRequestError("400"))
    breaker = CircuitBreaker(failures_to_open=1, cooldown_seconds=60)
    with pytest.raises(ModelInvalidRequestError):
        _guarded(model.runnable(), breaker).invoke("hi")
    assert breaker.allows_call()
