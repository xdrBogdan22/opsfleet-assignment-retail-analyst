# Technology decisions

This file records each technology choice, the alternatives and the evidence.
Evidence was collected on 2026-11-07.

## Decision 1: agent framework

**Status:** chosen.

**Choice:** LangGraph.

**Result:** LangGraph 4.30, Agno 4.15. That gap is too small to decide on
scores alone, so the decision rests on the two heaviest criteria. LangGraph is
stronger on safety control and human confirmation, and those are the areas where
a mistake could expose personal data or delete the wrong report. Agno needs less
orchestration code and has the highest personal experience score.

### What the framework must do

The brief asks for four things in the prototype: safety and PII masking,
confirmed deletion, resilience and observability. The review focuses on system
design, the technical explanation and an elegant prototype. Those points set
the criteria below.

Neither framework replaces the safety code. SQL validation, brand scoping, PII
masking and report ownership stay in application code, so the framework only
has to give that code a reliable place to run.

### Criteria

| Criterion | Weight | What a reviewer would ask |
|---|---:|---|
| Safety control | 20 | Can code inspect or block data between a tool result and the model? |
| Human confirmation | 15 | Can a delete pause, wait for a person and resume safely? |
| Resilience | 10 | Are retries and model fallback built in? |
| Observability | 10 | Can we inspect each model and tool step after a failure? |
| Gemini fit | 10 | Is Gemini supported directly and documented? |
| Delivery in 12 hours | 10 | How much orchestration code must be written? |
| Production path | 10 | Is there a clear route to persistence and multi-user operation? |
| Maturity | 5 | How large is the risk of relying on this project? |
| Personal experience | 10 | Can I defend the choice in the interview? |

### Scores

Scores run from 1 to 5, where 5 is the best fit. They are my judgement from the
evidence below, not measurements. The total is the weighted average.

| Criterion | Weight | Agno | LangGraph | Pydantic AI | Google ADK | Strands | CrewAI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Safety control | 20 | 4 | 5 | 4 | 3 | 4 | 2 |
| Human confirmation | 15 | 4 | 5 | 4 | 3 | 4 | 3 |
| Resilience | 10 | 4 | 4 | 4 | 3 | 3 | 2 |
| Observability | 10 | 5 | 4 | 4 | 5 | 4 | 3 |
| Gemini fit | 10 | 4 | 4 | 4 | 5 | 3 | 3 |
| Delivery in 12 hours | 10 | 4 | 3 | 4 | 4 | 4 | 3 |
| Production path | 10 | 4 | 5 | 4 | 4 | 3 | 3 |
| Maturity | 5 | 3 | 5 | 4 | 4 | 3 | 3 |
| Personal experience | 10 | 5 | 3 | 2 | 2 | 2 | 2 |
| **Total** | 100 | **4.15** | **4.30** | **3.80** | **3.55** | **3.45** | **2.60** |

Agno is 5 because it is my strongest framework. LangGraph is 3: I have medium
experience with it. The other four are at 2.

ADK and Strands have lower resilience scores partly because I did not find
model fallback documentation for them. That is a gap in the evidence, not proof
that the feature is missing.

### Sensitivity

| Scenario | First | Second | Third |
|---|---|---|---|
| Base weights | LangGraph 4.30 | Agno 4.15 | Pydantic AI 3.80 |
| Experience removed | LangGraph 4.44 | Agno 4.06 | Pydantic AI 4.00 |
| LangGraph experience is 1 | Agno 4.15 | LangGraph 4.10 | Pydantic AI 3.80 |
| Production weight moved to delivery | Agno 4.15 | LangGraph 4.10 | Pydantic AI 3.80 |

The last scenario treats production as an HLD topic and judges only the
12-hour prototype. Agno wins there. LangGraph wins when framework capability
matters most.

### Project health

Data comes from the GitHub API, PyPI and pypistats on 2026-11-07. Monthly
downloads include automated installs and dependencies, so they show reach, not
the number of teams using a framework.

| Framework | Version | License | Stars | Open issues | Downloads, last month |
|---|---|---|---:|---:|---:|
| Agno | 3.1.12 | Apache-2.0 | 43,092 | 1,977 | 1,779,568 |
| LangGraph | 1.2.20 | MIT | 44,615 | 461 | 44,769,952 |
| Pydantic AI | 2.66.0 | MIT | 21,073 | 1,825 | 5,383,780 |
| Google ADK | 2.14.0 | Apache-2.0 | 22,133 | 408 | 10,109,331 |
| Strands | 1.64.0 | Apache-2.0 | 9,069 | 1,148 | 37,112,498 |
| CrewAI | 1.15.37 | MIT | 60,607 | 1,184 | 2,442,764 |

### Mini-studies

#### Agno

Agno fits a single agent with a small number of tools. A tool can require
confirmation, the run pauses, and `continue_run` resumes it [A1]. Resuming by
run ID needs the same database and session identity [A1], so the prototype must
persist that state.

`fallback_models` handles eligible provider errors. Rate limits and server
errors can trigger it, while most other 4xx errors do not [A2]. Gemini retries
default to 0, so they must be configured [A3].

Tracing writes traces and spans to SQLite or Postgres through `setup_tracing`,
and `get_traces` and `get_spans` read them back [A4]. That suits a CLI, because
no external service is required.

Pre-hooks and post-hooks run around the model flow [A5], but the built-in
injection guardrail matches configured patterns and does not catch every attack
[A6]. PII masking of query results must therefore happen in the tool, before
the model sees them. AgentOS offers a production route with roles, approvals
and durable execution [A7]. That page is vendor material, and I have not tested
it.

Main risk: the docs do not show how a paused run behaves across a process
restart.

#### LangGraph

LangGraph has the strongest control model here. `interrupt()` saves state and
waits for a person, and a `Command` resumes the graph [L1]. A separate node can
sit between SQL execution and the model, which matches the PII boundary
directly.

It has costs. A node restarts from the top after an interrupt, so code before
the interrupt runs again [L1], and writes need idempotency keys or a check for
existing results [L2]. Crash protection depends on the durability mode, and
each mode has limits [L8]. In memory checkpointers lose state on restart, so
production needs a persistent one [L3].

Model fallback is available through `ModelFallbackMiddleware` with
`create_agent` [L4]. Gemini is supported through `ChatGoogleGenerativeAI` [L5],
and stores handle long-term user memory [L6]. Comparison articles agree that
the explicit graph adds code compared with lighter frameworks [L7]. Those
articles are secondary sources.

#### Pydantic AI

Pydantic AI is the strongest alternative that I did not expect to rank this
high. `requires_approval=True` ends the run with `DeferredToolRequests`, and
`DeferredToolResults` resumes it [P1]. A long wait can store the conversation
so nothing stays in memory [P2]. Validators run before approval, so a person
does not review invalid arguments [P3].

`ModelFallback` is the documented fallback for agents [P4], and `GoogleModel`
supports Gemini [P5]. Logfire provides instrumentation [P6], and durable
execution integrates with Temporal or DBOS [P7]. It lacks the personal
experience score, which keeps it third.

#### Google ADK

ADK is the natural Gemini and Google Cloud option. It has built-in OpenTelemetry
support [G1] and a plugin that records agent events in BigQuery [G2]. Tools can
require confirmation with a boolean or a function [G3].

The blocker for this project is the documented limit on tool confirmation:
`DatabaseSessionService` and `VertexAiSessionService` are not supported [G3].
A delete flow with persisted sessions would need extra work, so the score is 3.
I did not verify `before_tool` callbacks or model fallback, which affects the
safety and resilience scores.

#### Strands

Strands has a clean approval model. Hooks and tools can raise an interrupt, and
the project's own lesson uses delete approval as its example [S1][S2]. It emits
standard OpenTelemetry spans [S3].

The evidence for Gemini is weaker. A Python `GeminiModel` appears on an older
page [S4], and I did not find a model fallback guide. Nothing here makes it a
better choice than Agno or LangGraph for this project.

#### CrewAI

CrewAI is built around crews and flows, which is more structure than this
single-agent CLI needs. `@human_feedback` pauses a flow but blocks on console
input by default, and a custom provider is required for persisted async review
[C1]. Task guardrails validate task output [C2], which is a different boundary
from filtering a query result before the model reads it.

Gemini has a native integration [C3]. I found no native fallback setting, only
a gateway example through Portkey [C4]. Tracing goes to the CrewAI platform by
default, with OpenLIT as an OpenTelemetry option [C5].

### Consequences for the build

LangGraph restarts a node after an interrupt, so the design follows these rules:

1. The delete node does nothing before `interrupt()` except read the preview.
2. The confirmation is bound to the exact previewed report IDs and works once.
3. A repeated or stale confirmation deletes nothing.
4. The prototype uses a persistent checkpointer, so a pending delete survives a
   restart.
5. A dedicated node masks query results before the model reads them.

### Justification

> I chose LangGraph because the highest risks in this agent are exposing personal
> data and deleting the wrong reports. An explicit graph gives each safety step
> its own node, so PII masking sits between SQL execution and the model and can
> be tested alone. `interrupt()` with a checkpointer stops a delete, waits for a
> person and resumes from saved state. The graph costs more code than a lighter
> framework. I accept that cost, and I keep SQL validation, brand scoping and
> report ownership in plain application code. My experience with LangGraph is
> medium.

### References

**Agno**

- [A1] [Human-in-the-loop overview](https://docs.agno.com/hitl/overview)
- [A2] [Fallback models](https://docs.agno.com/models/fallback-models)
- [A3] [Gemini reference](https://docs.agno.com/reference/models/gemini)
- [A4] [Tracing overview](https://docs.agno.com/tracing/overview)
- [A5] [Pre-hooks and post-hooks](https://docs.agno.com/hooks/overview)
- [A6] [Prompt injection guardrail](https://docs.agno.com/examples/agents/guardrails/prompt-injection)
- [A7] [Agno introduction](https://docs.agno.com/introduction)

**LangGraph**

- [L1] [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [L2] [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [L3] [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [L4] [Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [L5] [ChatGoogleGenerativeAI](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai)
- [L6] [Stores](https://docs.langchain.com/oss/python/langgraph/stores)
- [L7] [Agno vs LangGraph, aicoolies](https://aicoolies.com/comparisons/agno-vs-langgraph)
- [L8] [Checkpointers](https://docs.langchain.com/oss/javascript/langgraph/checkpointers)

**Pydantic AI**

- [P1] [Deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [P2] [Going to production](https://pydantic.dev/docs/ai/production/)
- [P3] [Advanced tool features](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)
- [P4] [Model fallback](https://pydantic.dev/docs/ai/capabilities/model-fallback/)
- [P5] [Google models](https://pydantic.dev/docs/ai/models/google/)
- [P6] [Logfire integration](https://pydantic.dev/docs/ai/integrations/logfire/)
- [P7] [Durable execution with DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)

**Google ADK**

- [G1] [Instrument ADK applications with OpenTelemetry](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk)
- [G2] [BigQuery Agent Analytics plugin](https://adk.dev/integrations/bigquery-agent-analytics/)
- [G3] [Action confirmations](https://adk.dev/tools-custom/confirmation/)

**Strands**

- [S1] [Interrupts](https://strandsagents.com/docs/user-guide/concepts/interrupts/)
- [S2] [Control your agent with hooks](https://strandsagents.com/docs/learning/control-your-agent-with-hooks/)
- [S3] [Traces](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/)
- [S4] [Get started](https://strandsagents.com/latest/documentation/docs/)

**CrewAI**

- [C1] [Human feedback in flows](https://docs.crewai.com/en/learn/human-feedback-in-flows)
- [C2] [Tasks](https://docs.crewai.com/en/concepts/tasks)
- [C3] [LLMs](https://docs.crewai.com/en/concepts/llms)
- [C4] [Portkey integration](https://docs.crewai.com/en/observability/portkey)
- [C5] [CrewAI tracing](https://docs.crewai.com/edge/en/observability/tracing)

**Project health**

- [H1] [GitHub REST API](https://docs.github.com/en/rest)
- [H2] [PyPI](https://pypi.org/)
- [H3] [pypistats](https://pypistats.org/)

## Decision 2: development harness

**Status:** chosen.

I build this project with [Claude Code](https://claude.com/claude-code), using
spec-driven development. Each feature starts as a written spec with acceptance
criteria. Claude Code implements it, and I review the diff and the tests before
accepting the change.
