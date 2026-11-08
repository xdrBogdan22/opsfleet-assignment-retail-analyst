"""Runs the agent on eval/dataset.yaml and scores it with Ragas and simple checks.

Uses real Gemini, BigQuery and Postgres, so it needs the same .env as the CLI.
Reports saved during the run are deleted at the end.

    uv run --frozen python eval/run_eval.py              # every case
    uv run --frozen python eval/run_eval.py --case injection --case q1-report
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from google.cloud import bigquery
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from openai import AsyncOpenAI
from ragas import messages as rm
from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import AgentGoalAccuracyWithReference, AnswerRelevancy, Faithfulness

from retail_analyst.agent.graph import build_graph, new_question
from retail_analyst.agent.session import build_session
from retail_analyst.core.config import get_settings
from retail_analyst.core.db import Pool, open_pool

HERE = Path(__file__).parent
RUN_PREFIX = "eval-"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the agent.")
    parser.add_argument("--case", action="append", help="run only these case ids")
    args = parser.parse_args()
    load_dotenv()

    config = yaml.safe_load((HERE / "config.yaml").read_text())
    cases = yaml.safe_load((HERE / "dataset.yaml").read_text())["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] in args.case]

    with open_pool(os.environ["DATABASE_URL"]) as pool:
        try:
            results = [_run_safely(case, pool, config) for case in _paced(cases, config["pause_seconds"])]
        finally:
            with pool.connection() as conn:
                conn.execute("delete from reports where conversation_id like %s", (f"{RUN_PREFIX}%",))

    passed = _report(results, config)
    out = HERE / "results" / f"{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nDetails: {out}")
    return 0 if passed else 1


def _paced(cases: list[dict[str, Any]], pause: float) -> Any:
    for index, case in enumerate(cases):
        if index:
            time.sleep(pause)
        yield case


def _run_safely(case: dict[str, Any], pool: Pool, config: dict[str, Any]) -> dict[str, Any]:
    """One failed case, such as a judge rate limit, is recorded and the run goes on."""
    try:
        return _run_case(case, pool, config)
    except Exception as error:
        print(f"{case['id']}: ERROR {type(error).__name__}: {str(error)[:300]}")
        return {"id": case["id"], "flow": case["flow"], "error": f"{type(error).__name__}: {error}"}


def _run_case(case: dict[str, Any], pool: Pool, config: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    session = build_session(pool, case["user"], settings, bigquery.Client(), os.environ.get("ID_HASH_SALT", "eval"))
    graph = build_graph(InMemorySaver())
    conversation = f"{RUN_PREFIX}{uuid.uuid4().hex}"
    started = time.monotonic()
    state = graph.invoke(
        new_question(case["question"], conversation, settings),
        {"configurable": {"thread_id": conversation}},
        context=session,
    )
    messages = state["messages"]
    answer = str(messages[-1].text)
    contexts = [str(m.text) for m in messages if isinstance(m, ToolMessage)]

    banned = [text for text in case.get("must_not_contain", []) if text.lower() in answer.lower()]
    scores = asyncio.run(_judge(case, answer, contexts, messages, config))
    result = {
        "id": case["id"],
        "flow": case["flow"],
        "answer": answer,
        "seconds": round(time.monotonic() - started, 1),
        "model_calls": state.get("model_calls", 0),
        "banned_text_found": banned,
        **scores,
    }
    if case["flow"] == "safety":
        result["safety_pass"] = not banned and scores.get("agent_goal_accuracy") == 1.0
    print(f"{case['id']}: {json.dumps({k: v for k, v in result.items() if k != 'answer'})}")
    return result


async def _judge(
    case: dict[str, Any], answer: str, contexts: list[str], messages: list[Any], config: dict[str, Any]
) -> dict[str, float | None]:
    async with AsyncOpenAI(api_key=os.environ["GOOGLE_API_KEY"], base_url=config["judge_base_url"]) as client:
        return await _scores(case, answer, contexts, messages, config, client)


async def _scores(
    case: dict[str, Any], answer: str, contexts: list[str], messages: list[Any], config: dict[str, Any], client: Any
) -> dict[str, float | None]:
    judge = os.environ.get("EVAL_JUDGE_MODEL", config["judge_model"])
    llm = llm_factory(judge, client=client, max_tokens=config["judge_max_tokens"])
    embeddings = embedding_factory("openai", model=config["embedding_model"], client=client)

    scores: dict[str, float | None] = {"faithfulness": None}
    if contexts:  # nothing to be faithful to when no tool ran, for example a refusal
        faithfulness = await Faithfulness(llm=llm).ascore(
            user_input=case["question"], response=answer, retrieved_contexts=contexts
        )
        scores["faithfulness"] = faithfulness.value
    relevancy = await AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=config["relevancy_strictness"]).ascore(
        user_input=case["question"], response=answer
    )
    scores["response_relevancy"] = relevancy.value
    goal = await AgentGoalAccuracyWithReference(llm=llm).ascore(
        user_input=_ragas_messages(messages), reference=case["reference"]
    )
    scores["agent_goal_accuracy"] = goal.value
    return scores


def _ragas_messages(messages: list[Any]) -> list[rm.HumanMessage | rm.AIMessage | rm.ToolMessage]:
    converted: list[rm.HumanMessage | rm.AIMessage | rm.ToolMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            converted.append(rm.HumanMessage(content=str(message.text)))
        elif isinstance(message, AIMessage):
            calls = [rm.ToolCall(name=call["name"], args=call["args"]) for call in message.tool_calls]
            converted.append(rm.AIMessage(content=str(message.text), tool_calls=calls or None))
        elif isinstance(message, ToolMessage):
            converted.append(rm.ToolMessage(content=str(message.text)))
    return converted


def _report(results: list[dict[str, Any]], config: dict[str, Any]) -> bool:
    print("\nMetric means (0 to 1):")
    passed = True
    for metric in ("faithfulness", "response_relevancy", "agent_goal_accuracy"):
        values = [r[metric] for r in results if r.get(metric) is not None and r["flow"] != "safety"]
        if not values:
            continue
        mean = statistics.mean(values)
        ok = mean >= config["gate_judge_mean"]
        passed &= ok
        print(f"  {metric}: {mean:.2f} over {len(values)} cases {'PASS' if ok else 'FAIL'}")
    safety = [r for r in results if r["flow"] == "safety"]
    if safety:
        rate = sum(bool(r.get("safety_pass")) for r in safety) / len(safety)
        ok = rate >= config["gate_safety_pass_rate"]
        passed &= ok
        print(f"  safety pass rate: {rate:.0%} over {len(safety)} cases {'PASS' if ok else 'FAIL'}")
    errors = [r["id"] for r in results if "error" in r]
    if errors:
        passed = False
        print(f"  cases that did not run: {', '.join(errors)}")
    print(f"\nRelease gate: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    sys.exit(main())
