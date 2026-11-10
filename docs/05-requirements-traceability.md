# Requirements traceability

Every sentence of the [brief](client-requirements/initial-requirements.md), in
order, with a short answer and where to find the detail. "Prototype" means it
runs in this repository; "design" means it is in the documents only, as the
brief allows.

## The challenge

| Brief | Answer | Where |
|---|---|---|
| A data analysis agent for non-technical executives | A CLI chat agent that answers in plain business language, with a persona the company sets | [Technical explanation §5](04-technical-explanation.md#agility-persona-management) |
| Executives ask complex questions about sales and performance, such as underspending by state, a churn spike, or a Q1 report with Q2 actions | Each example is an eval case; the agent chains queries for multi-step questions and saves reports | [eval/dataset.yaml](../eval/dataset.yaml) |
| A read-only SQL connection to raw transaction logs | BigQuery `thelook_ecommerce`. The SQL guard allows one SELECT on four tables and rewrites them into scoped views. | [Technical explanation: SQL guard](04-technical-explanation.md#the-sql-guard-step-by-step) |
| A Golden Knowledge bucket of Question, SQL, Report trios | Design: Cloud Storage source, pgvector index, hybrid retrieval | [Technical explanation: hybrid intelligence](04-technical-explanation.md#hybrid-intelligence) |

## The task

| Brief | Answer | Where |
|---|---|---|
| A production-ready HLD | Production diagram, components and services | [Architecture](02-architecture.md#production-architecture) |
| A detailed technical explanation | Choices, data flow, errors, setup and one section for each requirement | [Technical explanation](04-technical-explanation.md) |
| A chat agent prototype to ask questions naturally and discuss them | CLI with conversation memory in Postgres | [README: Run the chat](../README.md#run-the-chat) |
| Easily extendable: graphs, mail, web search | A tool is a function, a YAML description and a registry line. Charts already exist in reports. A worked `send_report` example shows mail reusing the delete confirmation. | [Technical explanation: extensibility](04-technical-explanation.md#extensibility), P20 |
| Which services, how components communicate, where data is stored | Service table, request flow diagram, storage table | [Architecture](02-architecture.md#request-flow), [Storage](02-architecture.md#storage) |
| Detailed enough to understand production behavior | Data flow step by step, error table, scaling path | [Technical explanation §2 and §3](04-technical-explanation.md#2-data-flow), P22 |
| Ask about assumptions | Questions sent to the client, answers recorded with their effect on the design | [Client questions](client-requirements/open-questions.md) |

## Requirements

| Brief | Answer | Where |
|---|---|---|
| 1. Use the Golden Bucket to understand how analysts interpreted questions | Design: retrieve the 3 most similar approved trios as worked examples | [Technical explanation: hybrid intelligence](04-technical-explanation.md#hybrid-intelligence) |
| 1. How the bucket is updated over time | Analysts add trios; rated answers and corrections become candidates an analyst approves; a nightly job validates SQL against the current schema | [Technical explanation: hybrid intelligence](04-technical-explanation.md#hybrid-intelligence) |
| 1. How relevant data is provided at query time | Masked question, vector and full-text search, rank fusion, recency weight, top 3 in the prompt | [Technical explanation: hybrid intelligence](04-technical-explanation.md#hybrid-intelligence) |
| 2. Only analysis questions, safe against malicious users | Prototype: input checks, prompt scope, refusals; safety eval cases | [Technical explanation §5](04-technical-explanation.md#safety-and-pii-masking) |
| 2. PII must never appear in the output | Prototype: blocked columns, hashed IDs, Presidio on answers and reports | `src/retail_analyst/safety/` |
| 2. Each user analyzes only products related to them | Prototype: brand scope applied inside every table before aggregation | `config/seed/demo.yaml`, SQL guard tests |
| 3. "Delete all reports mentioning Client X" or "from this conversation" | Prototype: both supported through `request_delete`, plus deleting by report number | [Example run](example-run.md#6-brand-scope-personal-data-injection-and-delete) |
| 3. A strict confirmation without breaking UX | Prototype: one pause with the exact list; one word confirms, anything else cancels | [Technical explanation: high-stakes oversight](04-technical-explanation.md#high-stakes-oversight) |
| 3. Users delete only their own reports | Prototype: owner filter on search, on the stored request and on the delete | Delete flow tests |
| 4.1 Remember format preferences per user | Design: LangMem profile in the LangGraph store | [Technical explanation](04-technical-explanation.md#continuous-improvement), P7 |
| 4.1 Learn preferences over time | Design: nightly extraction from finished conversations | [Technical explanation](04-technical-explanation.md#continuous-improvement), P7 |
| 4.2 Learn from past interactions and improve | Design: reviewed corrections feed the Golden Bucket and the eval set | [Technical explanation](04-technical-explanation.md#continuous-improvement), P8 |
| 5. Detect syntax errors or empty results and self-correct | Prototype: parser and dry run errors go back as repairs; empty results trigger one filter check | [Technical explanation §3](04-technical-explanation.md#3-error-handling-and-fallback) |
| 5. Without crashing the UI | Prototype: every turn ends in an answer or a short message | `src/retail_analyst/cli/app.py` |
| 5. Without inflating costs | Prototype: limits on model calls, queries, repairs, bytes, rows and seconds | `config/agent/limits.yaml` |
| 5. Resilient to API and third-party failures | Prototype: Gemini fallback chain, circuit breaker, BigQuery retry deadlines, stop on outage | [Technical explanation §3](04-technical-explanation.md#3-error-handling-and-fallback), P10 |
| 6. How to evaluate before deployment | Prototype: 14-case eval with a release gate | [eval/README](../eval/README.md) |
| 6. Verify reports answer the user's intent | Prototype: Agent Goal Accuracy against a reference outcome; clarifying question when intent is ambiguous | [Technical explanation](04-technical-explanation.md#quality-assurance), P11, P12 |
| 6. How to evaluate UX | Design: per-turn outcome, calls, seconds and ratings, plus watched sessions with executives | [Technical explanation](04-technical-explanation.md#quality-assurance), P13 |
| 7. Know when the agent fails and why | Prototype: Sentry alerts, Langfuse outcome scores, JSON turn log | [Technical explanation §5](04-technical-explanation.md#observability) |
| 7. Agent-level metrics | Prototype: outcome, model calls, queries, SQL repairs, seconds, rating; production adds rates, bytes and cost | [Technical explanation](04-technical-explanation.md#observability), P14 |
| 7. Deep-dive debugging of the message exchange | Prototype: the Langfuse trace holds every message and tool call in order; five debugging steps | [Technical explanation](04-technical-explanation.md#observability), P14 |
| 8. The CEO changes the tone weekly | Prototype: versioned persona read on every turn | `scripts/set_persona.py` |
| 8. Non-developers update instructions without redeployment | Prototype: a table edit or one command; production: an admin screen on the same table | [Technical explanation §5](04-technical-explanation.md#agility-persona-management) |

## Deliverables

| Brief | Answer | Where |
|---|---|---|
| 1. Architecture diagram with building blocks, services, compute and flow | Production, request flow and agent graph; delete flow and Golden Knowledge sit with their requirements | [Architecture](02-architecture.md), [Technical explanation §5](04-technical-explanation.md#5-how-each-requirement-is-handled) |
| 1. Explain each infrastructure, framework or data store choice | Component table and design decisions | [Architecture](02-architecture.md#production-architecture), [Design decisions](03-design-decisions.md), [Technology decisions](01-technology-decisions.md) |
| 2.1 Reasoning for cloud services, models and frameworks | Choices with benchmarks and sources | [Technical explanation §1](04-technical-explanation.md#1-choices-and-reasons) |
| 2.2 Data flow between components | Nine steps with what the model sees | [Technical explanation §2](04-technical-explanation.md#2-data-flow) |
| 2.3 Error handling and fallback | Table of failures, responses and what development showed | [Technical explanation §3](04-technical-explanation.md#3-error-handling-and-fallback) |
| 2.4 Setup instructions and example run | README setup, tested on a clean clone; verified CLI sessions | [README](../README.md#setup), [Example run](example-run.md) |
| 2.5 How each requirement is handled | One section per requirement | [Technical explanation §5](04-technical-explanation.md#5-how-each-requirement-is-handled) |
| 3. Chat about data naturally, discuss it, create a report with action items | Prototype | [Example run](example-run.md) |
| 3.1 to 3.4 The prototype supports safety, oversight, resilience and observability | All four implemented and tested | [Progress](progress.md) |
| 4. CLI interface | `retail-analyst` command | `src/retail_analyst/cli/` |
| 5. Runnable on another machine | `uv sync --frozen` from a lock file, local Postgres, tested on a clean copy | [README](../README.md#setup) |
| 6. Framework choice, reasons and experience | LangGraph | [Technology decisions](01-technology-decisions.md) |

## Expected capabilities

| Brief | Eval cases | Verified CLI run |
|---|---|---|
| Customer behavior | `top-customers`, `aov-by-traffic-source` | [Example run §2](example-run.md#2-customer-behavior) |
| Product performance, and why products differ | `compare-two-brands`, `return-rate-by-category` | [Example run §4](example-run.md#4-product-performance-compare-two-brands-and-explain-why) |
| Time-based metrics | `monthly-revenue`, `ytd-by-department` | [Example run §3](example-run.md#3-time-based-metrics) |
| Questions about the database structure | `what-data`, `customer-fields` | [Example run §1](example-run.md#1-general-structure-of-the-database) |
| Multi-step queries | `state-underspending`, `q1-report` | [Example run §5](example-run.md#5-multi-step-question-with-a-report) |
| Construct and run SQL dynamically on BigQuery | The model writes the SQL; the guard checks and scopes it | All of the above |
| A newer Gemini model, mindful of rate limits | `gemini-3.8-flash` with fallback; 2 to 5 calls per question; breaker on repeated failures | 2 or 3 model calls per question in the run |
