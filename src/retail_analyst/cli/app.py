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

from dotenv import load_dotenv
from google.cloud import bigquery
from langchain_core.exceptions import ModelError
from langgraph.checkpoint.postgres import PostgresSaver

from retail_analyst.agent.graph import build_graph, new_question
from retail_analyst.agent.session import UnknownUserError, build_session
from retail_analyst.core.config import get_settings
from retail_analyst.core.db import Pool, open_pool
from retail_analyst.reports.store import load_report_html

log = logging.getLogger("retail_analyst")

HELP = "Commands: /open <id> opens a saved report, /new starts a new conversation, /quit exits."
MODEL_DOWN = "The AI service is not responding right now. Please try again in a minute."
FAILED = "Something went wrong with that request. Please try again."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retail-analyst", description="Chat with the retail data analyst.")
    parser.add_argument("--user", required=True, help="demo user id, for example ceo or denim_manager")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(filename="retail_analyst.log", level=logging.INFO)
    settings = get_settings()
    url = os.environ["DATABASE_URL"]
    salt = os.environ.get("ID_HASH_SALT") or _temporary_salt()

    with open_pool(url) as pool:
        try:
            session = build_session(pool, args.user, settings, bigquery.Client(), salt)
        except UnknownUserError:
            print(f"Unknown user {args.user!r}. Run scripts/init_db.py to create the demo users.")
            return 1
        graph = build_graph(PostgresSaver(pool))

        print(f"Signed in as {session.user.name}. {HELP}")
        conversation = uuid.uuid4().hex
        while True:
            try:
                text = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not text:
                continue
            if text == "/quit":
                return 0
            if text == "/new":
                conversation = uuid.uuid4().hex
                print("Started a new conversation.")
                continue
            if text.startswith("/open"):
                print(_open_report(pool, session.user.id, text.removeprefix("/open").strip()))
                continue

            config = {"configurable": {"thread_id": f"{session.user.id}:{conversation}"}}
            try:
                result = graph.invoke(new_question(text, conversation, settings), config, context=session)  # type: ignore[call-overload]
                print(f"\nanalyst> {result['messages'][-1].text}")
            except ModelError:
                log.exception("model failure")
                print(f"\nanalyst> {MODEL_DOWN}")
            except Exception:
                log.exception("turn failed")
                print(f"\nanalyst> {FAILED}")


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
