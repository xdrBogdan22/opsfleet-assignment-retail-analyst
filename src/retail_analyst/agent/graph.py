"""The LangGraph agent: input checks, a bounded tool loop, two pauses for the
user (a clarifying question and the delete confirmation) and the final answer.

Each user question starts with a fresh budget in the state. The agent node
stops offering tools when the model-call budget or the time limit is about to
run out, so the last call always produces an answer instead of another query.
"""

import json
import logging
import re
import time
from typing import Any, Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ValidationError

from retail_analyst.agent.prompt import system_prompt
from retail_analyst.agent.session import Session
from retail_analyst.core.config import Settings
from retail_analyst.reports.deletion import cancel, confirm, load_preview
from retail_analyst.safety.output_guard import redact, result_strings
from retail_analyst.tools.context import Budget, ToolContext
from retail_analyst.tools.reports import DELETE_REQUEST

log = logging.getLogger(__name__)

REFUSAL = "I can only help with analysis of the company's sales, customers and products."
TOO_LONG = "That message is too long. Please ask a shorter question."
CANCELLED = "Cancelled. Nothing was deleted."
EXPIRED = "That delete request has expired or was already used. Nothing was deleted."
NO_MORE_QUESTIONS = "No more clarifying questions. State your assumption in the answer."


class AgentState(MessagesState):
    conversation_id: str
    model_calls: int
    queries_left: int
    repairs_left: int
    started_at: float
    time_limit: int
    pending_delete: str | None
    pending_question: dict[str, Any] | None
    clarifications_left: int


def new_question(text: str, conversation_id: str, settings: Settings) -> AgentState:
    """Graph input for one user question, with a fresh budget."""
    budget = Budget.for_question(settings)
    return AgentState(
        messages=[HumanMessage(text)],
        conversation_id=conversation_id,
        model_calls=0,
        queries_left=budget.queries_left,
        repairs_left=budget.repairs_left,
        started_at=time.monotonic(),
        time_limit=_time_limit(text, settings),
        pending_delete=None,
        pending_question=None,
        clarifications_left=settings.limits.clarifications,
    )


def _time_limit(text: str, settings: Settings) -> int:
    limits = settings.limits
    is_report = re.search(limits.report_pattern, text, re.IGNORECASE)
    return limits.report_seconds if is_report else limits.question_seconds


def input_checks(state: AgentState, runtime: Runtime[Session]) -> dict[str, list[AnyMessage]]:
    safety = runtime.context.settings.safety
    text = state["messages"][-1].text
    if len(text) > safety.max_input_chars:
        return {"messages": [AIMessage(TOO_LONG)]}
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in safety.injection_patterns):
        return {"messages": [AIMessage(REFUSAL)]}
    return {"messages": []}


def after_input_checks(state: AgentState) -> Literal["agent", "__end__"]:
    return "__end__" if isinstance(state["messages"][-1], AIMessage) else "agent"


def agent(state: AgentState, runtime: Runtime[Session]) -> dict[str, object]:
    session = runtime.context
    limits = session.settings.limits
    messages: list[AnyMessage] = [SystemMessage(system_prompt(session)), *state["messages"]]

    elapsed = time.monotonic() - state["started_at"]
    last_call = state["model_calls"] >= limits.model_calls - 1 or elapsed >= state["time_limit"]
    if last_call:
        messages.append(HumanMessage(session.settings.prompts.final_answer))
        reply = session.model_without_tools.invoke(messages)
    else:
        reply = session.model_with_tools.invoke(messages)
    return {"messages": [reply], "model_calls": state["model_calls"] + 1}


def after_agent(state: AgentState) -> Literal["tools", "output_guard"]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "output_guard"


def output_guard(state: AgentState, runtime: Runtime[Session]) -> dict[str, list[AnyMessage]]:
    """Removes personal data from the final answer. The message keeps its id, so it is replaced."""
    session = runtime.context
    last = state["messages"][-1]
    result = redact(str(last.text), session.settings.safety, _known_values(state) | {session.user.name})
    if not result.removed:
        return {"messages": []}
    log.warning("output guard removed %s", ", ".join(result.removed))
    return {"messages": [AIMessage(content=result.text, id=last.id)]}


def _known_values(state: AgentState) -> set[str]:
    return result_strings([str(m.text) for m in state["messages"] if isinstance(m, ToolMessage)])


def tools(state: AgentState, runtime: Runtime[Session]) -> dict[str, object]:
    session = runtime.context
    budget = Budget(queries_left=state["queries_left"], repairs_left=state["repairs_left"])
    ctx = ToolContext(
        scope=session.user.scope,
        author=session.user.name,
        conversation_id=state["conversation_id"],
        settings=session.settings,
        bigquery=session.bigquery,
        db=session.db,
        id_salt=session.id_salt,
        budget=budget,
        known_values=_known_values(state),
    )
    last = state["messages"][-1]
    assert isinstance(last, AIMessage)

    results: list[AnyMessage] = []
    pending_delete = pending_question = None
    clarifications_left = state["clarifications_left"]
    for call in last.tool_calls:
        call_id, name = call["id"] or "", call["name"]
        output = _run_tool(session, name, call["args"], ctx)
        if name == "ask_clarification" and clarifications_left > 0 and "error" not in json.loads(output):
            # Answered by the clarify node after the pause, as this call's tool result.
            pending_question = {"call_id": call_id, **json.loads(output)}
            clarifications_left -= 1
            continue
        if name == "ask_clarification" and clarifications_left <= 0:
            output = json.dumps({"error": NO_MORE_QUESTIONS})
        results.append(ToolMessage(content=output, tool_call_id=call_id, name=name))
        if name == "request_delete":
            pending_delete = json.loads(output).get(DELETE_REQUEST)
    return {
        "messages": results,
        "queries_left": budget.queries_left,
        "repairs_left": budget.repairs_left,
        "pending_delete": pending_delete,
        "pending_question": pending_question,
        "clarifications_left": clarifications_left,
    }


def after_tools(state: AgentState) -> Literal["confirm_delete", "clarify", "agent"]:
    if state["pending_delete"]:
        return "confirm_delete"
    return "clarify" if state["pending_question"] else "agent"


def clarify(state: AgentState) -> dict[str, object]:
    """Pauses with the agent's question and passes the user's answer back as the tool result."""
    pending = state["pending_question"]
    assert pending is not None
    answer = interrupt({"kind": "clarify", "question": pending["question"], "options": pending["options"]})
    reply = ToolMessage(
        content=json.dumps({"user_answer": str(answer)}), tool_call_id=pending["call_id"], name="ask_clarification"
    )
    return {"messages": [reply], "pending_question": None}


def confirm_delete(state: AgentState, runtime: Runtime[Session]) -> dict[str, object]:
    """Pauses for the user's answer, then deletes only the stored list or cancels."""
    session = runtime.context
    owner, request_id = session.user.id, state["pending_delete"]
    assert request_id is not None
    preview = load_preview(session.db, owner, request_id)
    reports = [{"id": report_id, "title": title} for report_id, title in preview.reports] if preview else []

    answer = interrupt({"kind": "confirm_delete", "reports": reports})

    if str(answer).strip().lower() in session.settings.safety.delete_confirm_words:
        deleted = confirm(session.db, owner, request_id)
        text = EXPIRED if deleted is None else f"Deleted {deleted} report{'s' if deleted != 1 else ''}."
    else:
        cancel(session.db, owner, request_id)
        text = CANCELLED
    return {"messages": [AIMessage(text)], "pending_delete": None}


def _run_tool(session: Session, name: str, args: dict[str, object], ctx: ToolContext) -> str:
    tool = session.tools.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown tool {name}."})
    try:
        return str(tool.invoke({**args, "ctx": ctx}))
    except ValidationError as error:
        return json.dumps({"error": f"Invalid arguments for {name}: {error.errors(include_url=False)}"})


def build_graph(checkpointer: BaseCheckpointSaver[str]) -> CompiledStateGraph[AgentState, Session]:
    graph = StateGraph(AgentState, context_schema=Session)
    graph.add_node("input_checks", input_checks)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_node("confirm_delete", confirm_delete)
    graph.add_node("clarify", clarify)
    graph.add_node("output_guard", output_guard)
    graph.add_edge(START, "input_checks")
    graph.add_conditional_edges("input_checks", after_input_checks)
    graph.add_conditional_edges("agent", after_agent)
    graph.add_conditional_edges("tools", after_tools)
    graph.add_edge("confirm_delete", END)
    graph.add_edge("clarify", "agent")
    graph.add_edge("output_guard", END)
    return graph.compile(checkpointer=checkpointer)
