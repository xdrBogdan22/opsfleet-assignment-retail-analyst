import json
import logging

import pytest

from retail_analyst.core.config import get_settings
from retail_analyst.observability.monitor import Monitor

SETTINGS = get_settings()


def test_turn_summary_is_logged_without_any_service(caplog: pytest.LogCaptureFixture) -> None:
    monitor = Monitor(settings=SETTINGS, langfuse=None)
    turn = monitor.start_turn("ceo", "c1")
    assert turn.config["callbacks"] == []
    state = {"model_calls": 3, "queries_left": SETTINGS.limits.queries - 2, "repairs_left": SETTINGS.limits.sql_repairs}

    with caplog.at_level(logging.INFO, logger="retail_analyst.turns"):
        monitor.end_turn(turn, "answered", state)

    summary = json.loads(caplog.records[-1].getMessage())
    assert summary["outcome"] == "answered"
    assert summary["model_calls"] == 3
    assert summary["queries"] == 2
    assert summary["sql_repairs"] == 0


def test_feedback_without_a_trace_is_still_recorded(caplog: pytest.LogCaptureFixture) -> None:
    monitor = Monitor(settings=SETTINGS, langfuse=None)
    with caplog.at_level(logging.INFO, logger="retail_analyst.turns"):
        assert monitor.feedback(good=False) == "Thanks, noted."
    assert json.loads(caplog.records[-1].getMessage()) == {"event": "feedback", "good": False, "trace_id": None}
