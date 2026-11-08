from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from retail_analyst.cli import app


class FakeGraph:
    """Pauses once for a delete confirmation, then answers."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *_: Any, **__: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            request = {"kind": "confirm_delete", "reports": [{"id": 45, "title": "Churn"}]}
            return {"__interrupt__": [SimpleNamespace(value=request)]}
        return {"messages": [AIMessage("Deleted 1 report.")]}


class FakeMonitor:
    def start_turn(self, *_: Any) -> SimpleNamespace:
        return SimpleNamespace(config={})

    def end_turn(self, *_: Any) -> None:
        pass


def test_confirmed_delete_removes_the_browser_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kept, deleted = tmp_path / "report-7.html", tmp_path / "report-45.html"
    kept.write_text("kept")
    deleted.write_text("deleted")
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    session = SimpleNamespace(user=SimpleNamespace(id="denim_manager"), settings=None)
    monkeypatch.setattr(app, "new_question", lambda *_: {})

    answer = app._ask(FakeGraph(), session, FakeMonitor(), "delete it", "c1", tmp_path)  # type: ignore[arg-type]

    assert answer == "Deleted 1 report."
    assert kept.exists()
    assert not deleted.exists()
