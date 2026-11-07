"""The delete confirmation on the local Postgres, with a scripted model."""

import os
from collections.abc import Iterator
from typing import Any, cast

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from retail_analyst.agent.graph import CANCELLED, build_graph, new_question
from retail_analyst.agent.session import Session, User
from retail_analyst.core.config import get_settings
from retail_analyst.core.db import Pool, open_pool
from retail_analyst.reports.model import Report, Section
from retail_analyst.reports.store import save_report
from retail_analyst.tools.registry import build_tools

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"),
]

SETTINGS = get_settings()
DELETE_ACME = {"name": "request_delete", "args": {"matching_text": "Acme"}, "id": "1"}


@pytest.fixture
def pool() -> Iterator[Pool]:
    with open_pool(os.environ["DATABASE_URL"]) as pool:
        yield pool
        with pool.connection() as conn:
            conn.execute("delete from reports where conversation_id like 'delete-test-%'")


def report(title: str, text: str) -> Report:
    return Report(title=title, summary=text, sections=[Section(heading="Notes", paragraphs=[text])])


def session(pool: Pool, user_id: str) -> Session:
    def model() -> Any:
        replies = iter([AIMessage(content="", tool_calls=[DELETE_ACME])])
        return RunnableLambda(lambda _: next(replies))

    return Session(
        user=User(id=user_id, name=user_id, brands=("Diesel",)),
        persona=lambda: "",
        settings=SETTINGS,
        bigquery=cast(Any, None),
        db=pool,
        id_salt="s",
        tools={tool.name: tool for tool in build_tools(SETTINGS)},
        model_with_tools=model(),
        model_without_tools=model(),
    )


def run_delete(pool: Pool, user_id: str, answer: str) -> tuple[list[dict[str, Any]], str]:
    graph = build_graph(InMemorySaver())
    sess = session(pool, user_id)
    config: Any = {"configurable": {"thread_id": f"delete-test-{user_id}-{answer}"}}
    paused = graph.invoke(new_question("Delete reports about Acme", "delete-test-c", SETTINGS), config, context=sess)
    shown = paused["__interrupt__"][0].value["reports"]
    done = graph.invoke(Command(resume=answer), config, context=sess)
    return shown, done["messages"][-1].text


def remaining(pool: Pool, ids: list[int]) -> set[int]:
    with pool.connection() as conn:
        rows = conn.execute("select id from reports where id = any(%s)", (ids,)).fetchall()
    return {row["id"] for row in rows}


def test_confirmed_delete_removes_only_the_listed_reports_of_the_owner(pool: Pool) -> None:
    mine = save_report(pool, "denim_manager", "Alex", "delete-test-c", report("Acme review", "Acme churn"))
    other = save_report(pool, "denim_manager", "Alex", "delete-test-c", report("Q3 review", "Revenue"))
    theirs = save_report(pool, "outdoor_manager", "Sam", "delete-test-c", report("Acme for Sam", "Acme"))

    shown, message = run_delete(pool, "denim_manager", "yes")

    assert [r["id"] for r in shown] == [mine]
    assert message == "Deleted 1 report."
    assert remaining(pool, [mine, other, theirs]) == {other, theirs}


def test_any_other_answer_cancels(pool: Pool) -> None:
    mine = save_report(pool, "denim_manager", "Alex", "delete-test-c", report("Acme review", "Acme churn"))
    _, message = run_delete(pool, "denim_manager", "sure, why not")
    assert message == CANCELLED
    assert remaining(pool, [mine]) == {mine}
