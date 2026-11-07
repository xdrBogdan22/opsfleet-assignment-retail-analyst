"""Langfuse traces, Sentry errors and a JSON line per turn.

Each service starts only when its keys are set. The turn summary is always
written to the local log, so failures can be read even without accounts.
"""

import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import sentry_sdk
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from sentry_sdk.integrations.langchain import LangchainIntegration
from sentry_sdk.integrations.langgraph import LanggraphIntegration

from retail_analyst.core.config import Settings

log = logging.getLogger("retail_analyst.turns")


@dataclass
class Turn:
    """One user question, from input to answer."""

    config: RunnableConfig
    handler: CallbackHandler | None
    started: float = field(default_factory=time.monotonic)


@dataclass
class Monitor:
    settings: Settings
    langfuse: Langfuse | None
    last_trace_id: str | None = None

    @property
    def services(self) -> list[str]:
        return [name for name, on in (("Langfuse", self.langfuse), ("Sentry", sentry_sdk.is_initialized())) if on]

    def start_turn(self, user_id: str, conversation_id: str) -> Turn:
        handler = CallbackHandler() if self.langfuse else None
        callbacks: list[BaseCallbackHandler] = [handler] if handler else []
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{user_id}:{conversation_id}"},
            "callbacks": callbacks,
            "metadata": {"langfuse_session_id": conversation_id, "langfuse_user_id": user_id},
        }
        return Turn(config=config, handler=handler)

    def end_turn(self, turn: Turn, outcome: str, state: Mapping[str, Any] | None) -> None:
        """Writes the turn summary and attaches the agent metrics to the trace."""
        limits = self.settings.limits
        state = state or {}
        metrics: dict[str, float] = {
            "model_calls": state.get("model_calls", 0),
            "queries": limits.queries - state.get("queries_left", limits.queries),
            "sql_repairs": limits.sql_repairs - state.get("repairs_left", limits.sql_repairs),
            "seconds": round(time.monotonic() - turn.started, 1),
        }
        self.last_trace_id = turn.handler.last_trace_id if turn.handler else None
        log.info(json.dumps({"event": "turn", "outcome": outcome, "trace_id": self.last_trace_id, **metrics}))
        trace_id = self.last_trace_id
        if self.langfuse and trace_id:
            for name, value in metrics.items():
                self.langfuse.create_score(name=name, value=value, trace_id=trace_id)
            self.langfuse.create_score(name="outcome", value=outcome, trace_id=trace_id, data_type="CATEGORICAL")

    def feedback(self, good: bool) -> str:
        log.info(json.dumps({"event": "feedback", "good": good, "trace_id": self.last_trace_id}))
        if not self.last_trace_id:
            return "Thanks, noted."
        if self.langfuse:
            self.langfuse.create_score(
                name="user_feedback", value=1.0 if good else 0.0, trace_id=self.last_trace_id, data_type="BOOLEAN"
            )
        return "Thanks, your rating is attached to that answer."

    def close(self) -> None:
        if self.langfuse:
            self.langfuse.flush()
        if sentry_sdk.is_initialized():
            sentry_sdk.flush()


def start_monitor(settings: Settings) -> Monitor:
    config = settings.observability
    logging.basicConfig(filename=config.log_file, level=logging.INFO)
    if os.environ.get("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            send_default_pii=False,
            traces_sample_rate=config.sentry_traces_sample_rate,
            integrations=[
                LangchainIntegration(include_prompts=config.sentry_include_prompts),
                LanggraphIntegration(include_prompts=config.sentry_include_prompts),
            ],
        )
    has_langfuse = os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    return Monitor(settings=settings, langfuse=Langfuse() if has_langfuse else None)
