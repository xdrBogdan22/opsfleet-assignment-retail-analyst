# Technical explanation

This document explains how the system works in production and what the
prototype in this repository proves. The diagrams are in
[Architecture](02-architecture.md). The options behind each choice, with
sources, are in [Design proposals](03-design-proposals.md), cited as P1 to P22.
The build log, with every test and every problem found, is in
[Progress](progress.md).

## 1. Choices and reasons

### Cloud services

Google Cloud, because the data already sits in BigQuery and Gemini runs on
Vertex AI in the same cloud (P16).

| Need | Service | Why |
|---|---|---|
| Sign-in | Identity-Aware Proxy | Users are authenticated before a request reaches the app |
| Agent API | Cloud Run | Stateless containers that scale with load and to zero. At about 1,000 questions a day one small instance is enough. |
| Scheduled jobs | Cloud Run jobs with Cloud Scheduler | Golden Bucket ingestion, nightly preference extraction, quality checks |
| Warehouse | BigQuery, through authorized views | The agent never reads the raw tables |
| App data | Cloud SQL for PostgreSQL with pgvector | One store for conversation state, reports, delete requests, personas, preferences and Golden trios |
| Golden source | Cloud Storage | Versioned files of analyst trios |
| Tracing | Langfuse | Every model and tool call of a conversation, with scores |
| Errors | Sentry | Crash and error alerts |

Scaling for a sudden rise is a configuration change, not a redesign: more
Cloud Run instances, a connection pool, a report queue, reserved Gemini
capacity and partitioned BigQuery tables (P22).

### Models

`gemini-3.8-flash` first and `gemini-3.5-flash-lite` as fallback (P17). The
client asked for recent Gemini models, Gemini-only fallback and other
providers present but off; `config/agent/models.yaml` does exactly that.

No public text-to-SQL score exists for these models. On analyst-style agent
work, Google reports 61.4% for 3.8 Flash on Vals Finance Agent v2 against
58.6% for Claude Opus 5, and the independent Vals run puts it at 65.8%, rank 7
of 37, at about a sixth of Opus's price. It is much weaker on long, open agent
tasks, but this agent's loop is short and bounded.

Latency set one more choice. With its default reasoning, `gemini-3.8-flash`
took 8.7 seconds and 951 reasoning tokens for one SQL-writing call, and full
questions took about a minute, against the client's 10 to 30 seconds. With
`thinking_level: low` the same call took 2.2 seconds. The eval measures what
that costs in quality.

What development showed: on a free-tier key, `gemini-3.8-flash` allows 20
requests a day per project, and it also returned 503 and 504 under load. The
fallback answered every time. On the client's free key the fallback model will
carry most of the traffic, which is why the circuit breaker exists.

### Frameworks

| Framework | Role | Why |
|---|---|---|
| LangGraph | The agent graph | Explicit nodes for each safety step, and `interrupt()` with a Postgres checkpointer for the two user pauses. Full comparison in [Technology decisions](01-technology-decisions.md). |
| langchain-google-genai | Gemini client | Typed model errors (rate limit, timeout, server) that drive the fallback rules |
| sqlglot | SQL parsing and rewriting | Parses BigQuery SQL into a tree, so the guard rewrites tables instead of matching text |
| Presidio | Output check | Detects personal data in text, with a small pinned spaCy model |
| Jinja | Report HTML | Autoescaping, so model text cannot inject markup |
| Ragas 0.4.3 | Evaluation | Faithfulness, Response Relevancy, Agent Goal Accuracy |
| uv | Packaging | One lock file, so another machine gets the same versions |

## 2. Data flow

One question, in order. Steps 3, 5 and 7 are model calls; the client asked for
2 to 5 per question, and a typical question uses 2 or 3.

1. The CLI passes the message, the user and the conversation ID to the graph,
   with a fresh budget: 5 model calls, 5 queries, 2 SQL repairs, 2
   clarifications, and 30 seconds, or 120 for a report.
2. `input_checks` refuses very long messages and known injection phrases
   without calling a model.
3. The agent calls Gemini with the system prompt: the user's brand scope, the
   schema card without personal columns, GoogleSQL notes, business definitions
   and the current persona, read from Postgres on every turn. Gemini answers
   with tool calls. The chosen tool is the intent.
4. `run_sql` sends each query through the SQL guard, which rewrites every table
   into a scoped subquery with hashed customer IDs, then through the BigQuery
   runner: a free dry run, then the real query with byte, time and row caps.
   Rows go back to the model. Raw personal data never leaves BigQuery.
5. Gemini reads the rows and either asks for more data, fixes a failed query,
   pauses to ask the user a question, saves a report or answers.
6. `save_report` passes every text field through Presidio, renders HTML with
   Jinja and stores HTML and plain text in Postgres.
7. When one model call is left or time is up, the agent calls Gemini without
   tools, so the last call always answers.
8. `output_guard` runs Presidio on the answer. Text that came from query
   results, such as brand names, is allowed. If a report was saved, it adds
   the `/open` command when the model forgot it.
9. The CLI prints the answer. Langfuse gets the trace and the turn's metrics;
   the local log gets one JSON line.

Gemini receives the question, the allowed schema, masked rows, the persona and
the conversation. It never receives names, emails, addresses, coordinates,
raw customer IDs, the hashing salt or other managers' brands.

## 3. Error handling and fallback

| Failure | What happens | Seen in development |
|---|---|---|
| Syntax error in the model's SQL | The guard rejects it and the model gets the parser message as a repair, 2 per question | Yes: `TIMESTAMP_SUB(..., MONTH)` and a TIMESTAMP compared with a DATE. GoogleSQL notes in the prompt stopped it. |
| SQL that breaks a data rule | The guard rejects it and the model is told to explain the limit, not to retry | Yes: requests for emails |
| Unknown column | BigQuery's dry run fails and the model gets a repair | Yes, in tests |
| Query too large | The dry run measures bytes before anything is billed; over 1 GB is rejected | Yes, in tests |
| Slow query | A 20-second job timeout. The BigQuery client's own retries, 10 minutes by default, are cut to the same 20 seconds. | |
| Empty result | The model is told to check filter values once | |
| Gemini 429, 5xx or timeout | 2 attempts on the model, then the next Gemini model | Yes: 503, 504 and the 20-a-day limit on the primary |
| A model that keeps failing | Circuit breaker: after a failed call the model is skipped for 5 minutes | Yes: the second question went straight to the fallback |
| Gemini 400, 401 or 403 | No retry, no fallback, a plain message | |
| Invalid tool arguments | Validation error back to the model, which can retry | Yes: the fallback model sent `save_report` a wrong shape |
| BigQuery quota or outage | The model is told to stop and say so; `/open` and `describe_schema` still work | |
| Any other error in a turn | Logged, a short message printed, the chat goes on | |

Costs stay bounded because every retry has a limit: model calls, queries,
repairs, clarifications, bytes per query, rows per result and seconds per
question. All of them are in `config/` with the reason for each value.

## 4. Setup and example run

Setup is in the [README](../README.md): `uv sync --frozen`, Postgres with
pgvector, `scripts/init_db.py`, then `uv run --frozen retail-analyst --user
denim_manager`. A real session, with figures checked against BigQuery, is in
[Example run](example-run.md).

## 5. How each requirement is handled

### Hybrid intelligence

Design only in the prototype (P3). Analysts' trios land in Cloud Storage. A
job validates each trio's SQL on the current schema, masks brands, states and
dates in the question, embeds it and indexes it in pgvector with a full-text
index. At question time the agent masks the new question the same way, runs
vector and full-text search, merges the two lists with reciprocal rank fusion,
adds a small recency weight and puts the top 3 trios in the prompt as worked
examples. The method follows DAIL-SQL, OpenSearch-SQL and Generative Agents.
Retrieved SQL is only an example: anything based on it still passes the guard.

The bucket grows two ways: analysts add trios, and highly rated answers or
corrections become candidates that an analyst approves.

### Safety and PII masking

Implemented. Five layers, and the code layers are the boundary (P4):

1. Input checks refuse oversized input and known injection phrases.
2. The prompt keeps the agent on analysis topics. OWASP is clear that this is
   not a security boundary.
3. The SQL guard (`safety/sql_guard.py`) parses the SQL, allows one SELECT on
   the four tables, rejects table functions, and replaces every table with a
   subquery that exposes only allowed columns and only the user's brands.
   Brands travel as query parameters. A blocked column does not exist for the
   query, whatever aliases or CTEs the model writes.
4. Customer IDs leave BigQuery as salted 16-character hashes, consistent across
   tables so joins still work. A query that returns a customer ID next to a
   raw age, gender or location is rejected.
5. Presidio checks the final answer and every report, removing emails, phone
   numbers and person names that did not come from the data.

Brand scope is enforced before aggregation, so a manager's spend and churn
cannot include other brands. `orders.num_of_item` is hidden because it counts
items of every brand.

Evidence: 28 guard unit tests, real BigQuery tests that show a manager sees
only their brands, and safety cases in the eval.

### High-stakes oversight

Implemented (P5). The model can start a delete but never finish one.
`request_delete` finds the user's matching reports by full-text search and
stores the exact list with an owner and an expiry. The graph pauses with
`interrupt()` and the CLI shows the list. Only `yes`, `y`, `delete` or
`confirm` deletes, and only the stored IDs, once, for the same owner, before
expiry. Any other answer cancels. "Reports from this conversation" works the
same way with a conversation filter. LangGraph may re-run a node after a
resume; the single-use check makes that harmless.

Evidence: Postgres tests show another user's matching report is never listed,
and a live run cancelled and then deleted exactly the two listed reports.

### Continuous improvement

Design only in the prototype (P7, P8).

- User level: LangMem saves a preference the moment the user states it ("use
  tables"), and a nightly job extracts implicit habits from finished
  conversations. The profile lives in the LangGraph store on Postgres, holds
  only format and depth fields with dates, and fills the `{preferences}` slot
  that already exists in the prompt.
- System level: a correction becomes a note for that user and a candidate
  trio. An analyst approves or rejects it; approved trios join the Golden
  Bucket and the case joins the eval set, so the fix is tested on every
  release.

### Resilience and graceful error handling

Implemented. See section 3. Every failure ends in an answer or a short
message, never a crash, and every retry is bounded.

### Quality assurance

Partly implemented (P11, P12, P13).

- Before deployment: `eval/run_eval.py` runs 14 cases and applies a gate of
  0.8 on Faithfulness, Response Relevancy and Agent Goal Accuracy, and 100% on
  safety. The metrics are explained in plain words in
  [eval/README](../eval/README.md). The latest run: Goal Accuracy 1.00,
  Relevancy 0.88, safety 4 of 4, Faithfulness 0.77. Faithfulness fails the
  gate because answers about the database suggest analyses the schema does not
  state; the eval README explains it.
- Report intent: Agent Goal Accuracy checks that the user got the outcome they
  asked for. When a request has several readings that change the numbers, the
  agent asks one short question with options before answering.
- UX: tracked through outcome, model calls, seconds and `/good` or `/bad` on
  each turn; before release, 3 to 5 executives try scripted tasks while we
  watch. The metric list is in P13.

### Observability

Implemented (P14). With keys in `.env`, each turn becomes a Langfuse trace
grouped by conversation and user, holding every model call, tool call, SQL
query and result. The turn's outcome, model calls, queries, SQL repairs and
seconds are attached as scores, and `/good` or `/bad` adds a user rating. To
debug a bad answer, open its trace and read the messages in order. For the
prototype, `infra/langfuse/setup.sh` runs Langfuse locally with Docker; a live
question produced a trace of 25 steps with all six scores. Sentry
records errors without prompts and alerts by email; a test error reached it as
an issue. Without keys, the same
turn summary goes to `retail_analyst.log` as one JSON line.

Production adds dashboards on success rate, refusals, fallback use, bytes and
cost, and a scheduled job that flags unhappy conversations.

### Agility: persona management

Implemented. Tone lives in the versioned `personas` table and is read on every
turn, so a change applies from the next question with no restart.
`scripts/set_persona.py "..."` publishes a new version and `--show` lists the
history. In production an admin screen edits the same table. Safety rules live
in code and config, outside the persona, so a tone change cannot weaken them.
