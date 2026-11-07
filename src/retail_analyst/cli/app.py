"""Command-line chat. Run with: uv run --frozen retail-analyst --user ceo"""

import argparse
import logging
import os
import secrets
import sys
import tempfile
import uuid
import webbrowser
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery
from langchain_core.exceptions import ModelError
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from retail_analyst.agent.graph import AgentState, build_graph, new_question
from retail_analyst.agent.session import Session, UnknownUserError, build_session
from retail_analyst.core.config import get_settings
from retail_analyst.core.db import Pool, open_pool
from retail_analyst.observability.monitor import Monitor, start_monitor
from retail_analyst.reports.store import load_report_html

log = logging.getLogger("retail_analyst")

HELP = (
    "Commands: /open <id> opens a saved report, /good or /bad rates the last answer, "
    "/new starts a new conversation, /quit exits."
)
MODEL_DOWN = "The AI service is not responding right now. Please try again in a minute."
FAILED = "Something went wrong with that request. Please try again."

Graph = CompiledStateGraph[AgentState, Session]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retail-analyst", description="Chat with the retail data analyst.")
    parser.add_argument("--user", required=True, help="demo user id, for example ceo or denim_manager")
    args = parser.parse_args(argv)

    load_dotenv()
    settings = get_settings()
    monitor = start_monitor(settings)
    salt = os.environ.get("ID_HASH_SALT") or _temporary_salt()

    with open_pool(os.environ["DATABASE_URL"]) as pool:
        try:
            session = build_session(pool, args.user, settings, bigquery.Client(), salt)
        except UnknownUserError:
            print(f"Unknown user {args.user!r}. Run scripts/init_db.py to create the demo users.")
            return 1
        graph = build_graph(PostgresSaver(pool))
        services = ", ".join(monitor.services) or "local log only"
        print(f"Signed in as {session.user.name}. Monitoring: {services}.\n{HELP}")
        try:
            _chat(graph, session, monitor, pool)
        finally:
            monitor.close()
    return 0


def _chat(graph: Graph, session: Session, monitor: Monitor, pool: Pool) -> None:
    conversation = uuid.uuid4().hex
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text == "/quit":
            return
        if text == "/new":
            conversation = uuid.uuid4().hex
            print("Started a new conversation.")
        elif text in ("/good", "/bad"):
            print(monitor.feedback(good=text == "/good"))
        elif text.startswith("/open"):
            print(_open_report(pool, session.user.id, text.removeprefix("/open").strip()))
        elif text:
            print(f"\nanalyst> {_ask(graph, session, monitor, text, conversation)}")


def _ask(graph: Graph, session: Session, monitor: Monitor, text: str, conversation: str) -> str:
    """Runs one question, including any confirmation pause, and never raises."""
    turn = monitor.start_turn(session.user.id, conversation)
    state: dict[str, Any] | None = None
    try:
        state = graph.invoke(new_question(text, conversation, session.settings), turn.config, context=session)
        while "__interrupt__" in state:
            answer = _ask_confirmation(state["__interrupt__"][0].value)
            state = graph.invoke(Command(resume=answer), turn.config, context=session)
    except ModelError:
        log.exception("model failure")
        monitor.end_turn(turn, "model_down", state)
        return MODEL_DOWN
    except Exception:
        log.exception("turn failed")
        monitor.end_turn(turn, "error", state)
        return FAILED
    monitor.end_turn(turn, "answered", state)
    return str(state["messages"][-1].text)


def _ask_confirmation(request: dict[str, Any]) -> str:
    reports = request["reports"]
    print(f"\nanalyst> This will permanently delete {len(reports)} report(s):")
    for report in reports:
        print(f"  {report['id']}: {report['title']}")
    try:
        return input("Type yes to delete them. Anything else cancels: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _open_report(pool: Pool, user_id: str, report_id: str) -> str:
    if not report_id.isdigit():
        return "Usage: /open <report id>"
    html = load_report_html(pool, user_id, int(report_id))
    if html is None:
        return f"You have no report {report_id}."
    path = Path(tempfile.gettempdir()) / f"retail-report-{report_id}.html"
    path.write_text(html, encoding="utf-8")
    webbrowser.open(path.as_uri())
    return f"Opened report {report_id} in your browser ({path})."


def _temporary_salt() -> str:
    print("ID_HASH_SALT is not set, so customer codes will change on every run.", file=sys.stderr)
    return secrets.token_hex(16)
