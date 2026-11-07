"""The LangGraph agent: input checks, a bounded tool loop and the final answer.

Each user question starts with a fresh budget in the state. The agent node
stops offering tools when the model-call budget or the time limit is about to
run out, so the last call always produces an answer instead of another query.
"""

import json
import re
import time
from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import ValidationError

from retail_analyst.agent.prompt import system_prompt
from retail_analyst.agent.session import Session
from retail_analyst.core.config import Settings
from retail_analyst.tools.context import Budget, ToolContext

REFUSAL = "I can only help with analysis of the company's sales, customers and products."
TOO_LONG = "That message is too long. Please ask a shorter question."


class AgentState(MessagesState):
    model_calls: int
    queries_left: int
    repairs_left: int
    started_at: float


def new_question(text: str, settings: Settings) -> dict[str, object]:
    """Graph input for one user question, with a fresh budget."""
    budget = Budget.for_question(settings)
    return {
        "messages": [HumanMessage(text)],
        "model_calls": 0,
        "queries_left": budget.queries_left,
        "repairs_left": budget.repairs_left,
        "started_at": time.monotonic(),
    }


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
    last_call = state["model_calls"] >= limits.model_calls - 1 or elapsed >= limits.question_seconds
    if last_call:
        messages.append(HumanMessage(session.settings.prompts.final_answer))
        reply = session.model_without_tools.invoke(messages)
    else:
        reply = session.model_with_tools.invoke(messages)
    return {"messages": [reply], "model_calls": state["model_calls"] + 1}


def after_agent(state: AgentState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "__end__"


def tools(state: AgentState, runtime: Runtime[Session]) -> dict[str, object]:
    session = runtime.context
    budget = Budget(queries_left=state["queries_left"], repairs_left=state["repairs_left"])
    ctx = ToolContext(
        scope=session.user.scope,
        settings=session.settings,
        bigquery=session.bigquery,
        id_salt=session.id_salt,
        budget=budget,
    )
    last = state["messages"][-1]
    assert isinstance(last, AIMessage)

    results: list[AnyMessage] = []
    for call in last.tool_calls:
        output = _run_tool(session, call["name"], call["args"], ctx)
        results.append(ToolMessage(content=output, tool_call_id=call["id"] or "", name=call["name"]))
    return {"messages": results, "queries_left": budget.queries_left, "repairs_left": budget.repairs_left}


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
    graph.add_edge(START, "input_checks")
    graph.add_conditional_edges("input_checks", after_input_checks)
    graph.add_conditional_edges("agent", after_agent)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
