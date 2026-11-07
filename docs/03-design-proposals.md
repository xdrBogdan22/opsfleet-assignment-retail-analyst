# Design proposals

These are proposals to review before the architecture is final. Each one states
the options, the constraints and a recommendation. Evidence was collected on
2026-11-07 and 2026-11-08. Vendor blogs and price trackers are marked as weaker
sources.

Status: P1 to P21 decided on 2026-11-08. The client answered on 2026-11-08, which
changed P4, P10, P12, P17 and P22. All changes were approved the same day. Each item names its decision on its first line.

The brief asks the prototype to support only safety and PII, the delete
confirmation, resilience and observability. The other requirements are design
only. When an item says "design only", it appears in the diagrams and the
technical explanation but not in the code.

## P1. Transaction data

Decision: no data generation. Init scripts create only our own tables and data.

The public dataset `bigquery-public-data.thelook_ecommerce` exists, and the
assignment names it. BigQuery metadata shows 125,266 orders, 181,446 order items,
29,120 products and 100,000 users. No generation or init scripts are needed for
this data.

We do need to create the Golden Trios, the demo users, their brand mapping and the
application tables. Those get a repeatable init script.

## P2. Application storage

Decision: a local Postgres with pgvector, without Docker. pgAdmin is optional for
browsing the data.

Constraints: the code must run on another machine, hybrid search must work, and
LangGraph needs persistence. Reports, preferences, personas and trios should not
need separate stores.

| Option | Plus | Minus |
|---|---|---|
| **Postgres with pgvector in Docker Compose** | Matches production. Has official LangGraph checkpointer [1] and store [2]. Hybrid search combines `tsvector` and vectors [3]. | Reviewers need Docker. |
| Embedded Postgres with `pgserver` | No Docker, includes pgvector [4] | Community project, and I have not checked its maintenance. |
| SQLite with `sqlite-vec` | Simple setup | Differs from production. I did not verify its maturity. |
| Dedicated vector database | Strong retrieval features | One more service for a very small set of trios. |

The assignment says Docker is not required and asks for clear setup instructions.
A local install keeps the setup to one package manager command per platform:
`brew install postgresql@18 pgvector` on macOS, or the PGDG packages
`postgresql-18` and `postgresql-18-pgvector` on Debian and Ubuntu [42]. One init
script then creates the database, the `vector` extension and the tables.
`DATABASE_URL` in `.env` points the app at any Postgres, including a cloud one.

Verified on the development machine: Postgres 18.3 with pgvector 0.8.7.

## P3. Golden Knowledge retrieval

Decision: hybrid search on masked questions, with a small recency weight. The
technical explanation cites the studies in the table below.

Your dynamic few-shot idea matches the literature.

| Source | Finding | What we take |
|---|---|---|
| DAIL-SQL [5] | Masks domain words, then selects examples by question and query similarity | Mask brands, states and dates before matching |
| OpenSearch-SQL [6] | Removing few-shot lowered Mini-Dev execution accuracy from 70.6% to 66.0% | Evidence that retrieved examples help |
| Text2SQL-Flow [7] | Selection based on a draft SQL can fail when the draft is wrong | Do not depend on a draft query |
| Generative Agents [8] | Combines normalized recency and relevance, with exponential recency decay | Use a simple decay for recency |

Those benchmark results come from academic datasets, not from this agent.

**Recommendation:**

1. Store trios in Postgres with their masked question, embedding and text index.
2. Run vector and full-text search on the masked question.
3. Merge the two rankings with reciprocal rank fusion [3].
4. Keep only approved trios.
5. Score each trio as `0.85 * relevance + 0.15 * recency`, with a 180-day half-life.
6. Add the top 3 to the prompt as examples.

The weights are initial values for tuning with the eval set. Recency stays small
because an old analysis can still be correct.

Updates work like this: analysts add trios or approve candidates, a job validates
the SQL against the current schema, then embeds and indexes it. A failed validation
keeps the trio out of retrieval.

## P4. Safety and PII

Decision: the four layers in the recommended order below.

Your layers are right, but the order of trust changes. OWASP says input screening
"is not a security boundary" and places permission checks in execution code outside
the model [9]. A guardrail library therefore cannot be the main protection.

| Option | Use | Decision |
|---|---|---|
| Deterministic SQL and scope layer | Blocks PII columns and enforces brands | Required, main protection |
| Structured Gemini classifier | Keeps the agent on analysis topics | Use as the first node |
| Presidio | Detects PII in text. It does not guarantee finding all PII [10]. | Use in the final output step |
| Exact value matching | Checks output for known emails or names returned by tools | Add if time allows |
| NeMo Guardrails | Dialogue and execution rails, but it needs Colang [11] | Skip, too much for 12 hours |
| Guardrails AI | Validator hub, strong for structured output [11] | Skip. Pydantic covers our structured output. |

The comparison sources for NeMo and Guardrails AI are weaker third-party articles.

**Recommended order:** input classifier, deterministic SQL layer, masked results,
then the Presidio output check. Each layer logs its decision.

Update after the client's answers: a separate classifier call would use one of
the 2 to 5 model calls. The proposal is to merge it into the agent's first call,
which returns a structured intent (analysis, report, schema question, delete,
refuse, or clarify) next to its first step. Cheap deterministic checks still run
before it. The main protection remains the SQL layer, so losing a separate
classifier does not weaken the security boundary [9]. Status: decided on
2026-11-08.

## P5. Delete flow

Decision: `interrupt()` on a stored list of report IDs.

A dedicated path with LangGraph `interrupt()` fits. OWASP also says approval should
cover the exact action, target and arguments [9], so the user approves a stored
list of report IDs. The confirmation stays one quick reply. Any other reply cancels.

## P6. Report format and storage

Decision: HTML and plain text in Postgres, opened in the browser with `/open <id>`.

| Option | Plus | Minus |
|---|---|---|
| Markdown in Postgres | Simple and easy to search | Weak charts |
| **HTML and plain text in Postgres** | Good charts, one store, simple delete | Rows are larger |
| HTML in object storage, metadata in Postgres | Best at production scale | A delete touches two systems |

**Recommendation:** the model returns structured sections, and code renders them
with a Jinja template and escaped text, because model output is untrusted [9]. Charts
are static SVG generated by code, so the file has no JavaScript. Postgres stores
the HTML, the plain text and a search index for "reports mentioning Client X".

In the demo, the CLI prints the summary and `/open <id>` opens the HTML in the
browser. Production can move the HTML to Cloud Storage.

## P7. User preferences

Decision: LangMem. User-level learning is design only in the brief, so the
prototype adds it only if time allows.

| Option | Plus | Minus |
|---|---|---|
| Scheduled extraction over conversations | No latency during chat, finds implicit habits | Delay before it helps, adds a job |
| **Capture explicit preferences during the turn** | Works at once and is simple | Misses implicit habits |

LangChain states that hot path memory is sufficient for most applications, and that
background consolidation helps with latency or quality across many conversations
[12]. LangMem recommends a concise profile for user settings [13].

LangMem covers both options with one library [13]:

- Hot path: the agent gets a memory tool and saves a preference as soon as the
  user states it.
- Background: a memory manager reads finished conversations, extracts
  preferences and updates the profile. A reflection executor can delay this
  until the conversation goes quiet.

LangMem writes to the LangGraph store, so the profile lives in Postgres next to
everything else [2]. A profile schema in Pydantic keeps it small and readable:
format (table, bullets, chart), depth, and the date of each field. The agent
reads the profile at the start of each turn and adds it to the prompt.

Risks to state in the design:

| Risk | Evidence | Mitigation |
|---|---|---|
| Young package | Version 0.0.30, released 2025-10-27. The repo is active, with a push on 2026-11-03 [43]. | Pin the version. Keep LangMem behind one small interface, so a plain store write can replace it. |
| Extra dependencies | It requires `langchain-openai` and `langchain-anthropic`, even with Gemini [43] | Accept. Install size only. |
| Wrong memories | Extraction is a model call and can misread a joke as a preference | Store only format and depth fields, show the profile with `/profile`, let the user reset it |

## P8. System learning

Decision: design only, shown in the diagrams. The brief does not list it for the
prototype.

Keep this simple:

1. A user correction is saved as a note for that user only.
2. A rated answer or correction can become a candidate trio.
3. An analyst approves or rejects the candidate.
4. Approved trios enter the Golden Bucket, and the case joins the eval set.

The review step stops one user's mistake from teaching every user. OpenAI's guide
also turns failures into durable regression tests [14].

## P9. SQL self-correction

Decision: the checks and repair limits in the table below.

Your retry idea is the right base. The name of the library is `sqlglot`.

| Method | Cost | Decision |
|---|---|---|
| Local parse with `sqlglot` | No model or BigQuery call | First check |
| BigQuery dry run | Free validation before execution [15] | Second check |
| Retry with the failed SQL and error | One model call | Use, up to 2 repairs |
| Error-specific repair, as in ReFoRCE [16] | Small prompt additions | Use for missing columns, types and syntax |
| Exploration probes for empty results, as in SDE-SQL [17] | One extra query | Use one probe to check filter values |
| Trained critic model, as in SQLCritic [18] | High | Skip |

Execution feedback cannot fix a valid query with the wrong logic [19]. The eval set
must catch those errors.

## P10. Error handling and budget

Decision: the error table and budget below.

Rules below come from Google's documentation [20][21][22].

| Source | Error | Action |
|---|---|---|
| Gemini | 400, 401, 402, 403, 404 | No retry. Fail with a clear message. |
| Gemini | `model_not_found` | Use the fallback model. |
| Gemini | 408, 429 rate limit, 500, 503 | Exponential backoff with jitter, then fallback model. |
| Gemini | 429 `quota_exceeded` | No backoff. Use the fallback model, then stop. |
| Gemini | 504 | Retry once, then fallback model. |
| Gemini | Safety block | Stop and ask the user to rephrase. |
| Gemini | `malformed_function_call` | One repair, because Google gives no specific action. |
| BigQuery | 500, 502, 503, 504 `backendError` | Truncated exponential backoff. |
| BigQuery | `rateLimitExceeded`, `jobRateLimitExceeded` | Backoff, with a new job ID for the job error. |
| BigQuery | `invalidQuery`, `notFound` | No blind retry. Send to SQL repair. |
| BigQuery | `quotaExceeded`, `accessDenied` | No retry. Keep non-data commands working. |
| BigQuery | `timeout`, `responseTooLarge` | Ask the model for a narrower query. |

The Gemini Python SDK already retries transient errors up to four times [20], so we
must avoid stacking our own retry on top of it.

The client asked us to stay within free-tier rate limits, at roughly 2 to 5 model
calls for each question. The budget for each question is therefore:

| Limit | Value | Why |
|---|---|---|
| Model calls | 3 typical, 5 maximum | Client guidance |
| SQL repairs | 2 for the whole question, not for each query | Repairs share the 5 calls |
| Queries | 5. One model call may request several queries at once through parallel function calls. | A report needs several queries without extra calls |
| Time | 30 seconds for a question, 120 seconds for a report | Client targets of 10 to 30 seconds and 1 to 2 minutes |
| Cost | $1 for each question | Client budget. Design only. |
| Bytes | A cap on each query through `maximum_bytes_billed` | Cost control in BigQuery |

A typical question uses three calls: one to understand the question and write the
SQL, one optional repair or follow-up query, and one to write the answer. All
values live in the YAML config.

The $1 cap is far above the expected cost. As a rough estimate, five calls with
15,000 input and 1,000 output tokens each cost about $0.08 at the current
`gemini-3.8-flash` price, and about $0.16 after the 2027 price change [34]. The cap
protects against loops and huge queries. It does not set normal spending.

Gemini rate limits apply per project and vary by model [23]. Free-tier values
appear only in AI Studio, so a client-side limiter reads them from config. Because
limits are per model, a 429 on the primary model can still succeed on the
fallback model. The eval run also uses the same project quota, so it runs slowly
and in sequence.

A simple circuit breaker stops calling a service after repeated failures. Schema
help and report commands keep working when Gemini or BigQuery is down.

## P11. Evaluation

Decision: the plan below, with a dataset of 10 questions, 2 for each flow, plus
safety cases. The prototype implements a minimal Ragas run only if time allows.
Otherwise the eval stays documented. The evaluation document will explain every
metric in plain words, as in the glossary at the end of this section.

Your three perspectives work, and I would add four things.

| Perspective | Prototype | Notes |
|---|---|---|
| LLM judge with Ragas | Yes | Faithfulness, Response Relevancy and Agent Goal Accuracy [24] |
| Consistency over 10 runs | Documented | Compare numbers and conclusions, not exact text |
| Deterministic correctness | Documented | Check that answer values appear in tool results |
| Safety and refusal cases | Add | Attacks, PII requests and out-of-scope brands |
| Regression and capability split | Add | Regression cases should stay near 100% [25] |
| Balanced cases | Add | Include cases where the agent should refuse or ask [25] |
| Tool and SQL checks | Documented | Ragas has Tool Call Accuracy and SQL metrics [24] |

Ragas must be pinned and tested, because its docs conflict: the metric page lists
Aspect Critic, while the v0.4 migration guide says it was removed [26].

The dataset has 2 to 4 questions for each flow: customer behavior, product
performance, time metrics, database structure and multi-step analysis, plus safety
cases. OpenAI suggests starting with 10 to 50 items [27]. The release gate starts at
0.8 for judge metrics, and 100% for safety cases. Those thresholds are initial
choices to calibrate.

Metrics in plain words. Each Ragas score runs from 0 to 1 [24].

| Metric | Question it answers | How it works |
|---|---|---|
| Faithfulness | Does the answer say only what the data says? | A judge model splits the answer into short claims and checks each claim against the query results. The score is the share of supported claims. |
| Response Relevancy | Does the answer address the question asked? | The judge writes questions that the answer would fit, then compares them with the real question. Off-topic answers score low. |
| Agent Goal Accuracy | Did the agent reach what the user wanted? | The judge compares the final result with a reference outcome we wrote for the case, and returns 1 or 0. |
| Consistency over repeated runs | Does the same question give the same answer? | Run each question several times, for example 10. Count how often the key numbers and the main conclusion match. |
| Deterministic correctness | Are the numbers real? | Code, not a model, checks that every number in the answer appears in the query results. |
| Safety pass rate | Did the agent refuse what it must refuse? | Attack and PII cases have an expected refusal. One miss fails the gate. |

## P12. Clarification and report intent

Decision: at most 2 questions, only when the meaning changes the result.

Your clarification node has research support. AmbiSQL detects ambiguity and asks
multiple-choice questions [28]. PRACTIQ defines a question as ambiguous when it has
several valid interpretations for the schema [29].

The decision to clarify comes from the same first call as the intent in P4, so it
adds no model call.

**Recommendation:** ask at most 2 questions, with short options and a custom answer,
only when the interpretation changes the result. Otherwise the agent states its
assumption in the answer. LangGraph can use the same interrupt as the delete flow.

## P13. UX evaluation

The sources here are mostly vendor blogs, so the targets are not reliable. The useful
idea is that a closed conversation is not proof of success [30].

Decision: document the metrics below and the session with executives. Design only.

| Metric | What it means | Why it matters |
|---|---|---|
| Task success | Share of conversations where the user got what they came for, judged by a rubric or the user's rating | The main UX outcome |
| Turns to answer | Messages the user sends before the first useful answer | More turns mean the agent misunderstood or asked too much |
| Clarification rate | Share of questions where the agent asked before answering | Too high is annoying. Too low may mean guessing. |
| Retry rate | Share of questions the user rephrases or asks again | A rephrase usually means the first answer missed |
| Thumbs up or down | The user's `/good` or `/bad` rating | Direct signal, but few users give it |
| Time to answer | Seconds from question to final answer | Executives leave slow tools |

Before release, watch 3 to 5 executives try scripted tasks and note where they get
stuck.

## P14. Observability

| Option | Plus | Minus |
|---|---|---|
| **Langfuse** | MIT core, LangGraph callback [31], sessions and scores | Self-hosting adds services |
| LangSmith | Best LangGraph fit [32] | Proprietary, self-hosting is Enterprise only [32] |
| Phoenix | OpenTelemetry-based | Elastic License 2.0, not OSI open source [32] |
| Sentry | Python LangGraph integration, PII capture is opt-in [33] | Better for errors than for analysis work |

The license and comparison details come from secondary sources.

Decision: Langfuse and Sentry, both in the prototype.

They overlap less than it seems. Langfuse shows the agent's work: each model call,
tool call, SQL query, token count and user score, grouped by conversation. Sentry
catches crashes and errors in the application and sends alerts. Langfuse's own
comparison recommends running both, with Sentry for the application and Langfuse
for the AI work [44]. That source is a vendor page, but it matches how the two
products describe themselves. Sentry's agent tracing would cover part of Langfuse,
but it has no scores, datasets or prompt review [44].

Both have free plans that fit this project. Langfuse Hobby gives 50,000 units a
month, 30 days of data and 2 users [45]. Sentry Developer gives 5,000 errors, 5M
spans, agent tracing and email alerts for 1 user [46].

Both stay optional through keys in `.env`. Without keys, the app runs and writes a
normal log file, so reviewers can run it without accounts. The `/good` and `/bad`
commands send the rating to Langfuse as a score.

Alerting: Sentry sends email on new errors and error spikes. Alerts on agent
quality, such as a falling success rate, are a production item. I did not confirm
an alerting feature in Langfuse, so the design uses a scheduled query over its
data.

Agent metrics are success rate, refusal rate, repairs per turn, empty results,
fallback use, latency, tokens, bytes scanned, cost per turn, and user rating. Traces
must contain only masked data. Detection of unhappy users stays documented only.

The CLI collects feedback with `/good` and `/bad`.

## P15. Persona management

Decision: a versioned persona table in Postgres.

Your approach is good. Postgres stores versioned persona records, and each turn loads
the active one. The prototype changes it through a CLI command or SQL. The product
would expose presets and short custom text in an admin screen. Safety rules stay
outside the persona.

## P16. Cloud services

Decision: Google Cloud.

We do not deploy, so this section explains what we would choose. Google Cloud is the
default because the data is already in BigQuery and Gemini runs on Vertex AI.
Sizing depends on traffic, which is a client question.

## P17. LLM models

Decision: `gemini-3.8-flash` as primary and `gemini-3.5-flash-lite` as fallback.

| Model | Input per 1M | Output per 1M | Source |
|---|---:|---:|---|
| `gemini-3.8-flash` | $0.75 until 2026-12-31, then $1.50 | $3.75, then $7.50 | Official [34] |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 | Official [34] |
| Claude Sonnet 5.5 | $2 | $10 | Official [35] |
| Claude Opus 5.5 | $4 | $20 | Official [35] |
| Kimi K3 | $3 | $15 | Third party [36] |
| Qwen3.8-Max | About $2 | About $6 | Third party [37] |

Fallback between providers. The client asked for fallback between Gemini models
only, with other providers present in config but switched off.

| Option | Plus | Minus |
|---|---|---|
| **Gemini to Gemini (default)** | One key, one data processor, the same tool-calling behavior, and separate rate limits for each model | Does not help when the whole Gemini API is down |
| Gemini to another provider | Survives a Google outage | Second key and contract, data goes to another company, prompts and tool calls behave differently and need their own eval |

The YAML model config lists providers in order, each with `enabled: true` or
`false`. Only Gemini entries are enabled.

**Recommendation:** use `gemini-3.8-flash` as primary and `gemini-3.5-flash-lite` as
fallback. Both show a free tier, but actual limits appear only in AI Studio [23].

Benchmarks. Google publishes no text-to-SQL score for these models, and I found
none on the BIRD or Spider leaderboards. Those leaderboards also have label
problems: one study found annotation errors in 52.8% of BIRD Mini-Dev and 62.8% of
Spider 2.0-Snow examples [47]. The closest public evidence is agent work on
financial data:

| Benchmark | What it tests | 3.8 Flash | Comparison | Source |
|---|---|---:|---|---|
| Vals Finance Agent v2 | Financial analyst tasks with tools | 61.4% | Opus 5 58.6%, Sonnet 5 53.9%, GPT-5.6 Sol 53.8% | Google [48] |
| Vals Finance Agent v2.1 | Same, run independently by Vals | 65.8% | Rank 7 of 37 models | Vals AI [49] |
| CharXiv Reasoning | Reading charts | 86.2% | Opus 5 83.7% | Google [48] |
| GDPVal-AA v2 | Knowledge work, Elo | 1545 | Opus 5 1824, Sonnet 5 1584 | Google [48] |
| Terminal-bench 4.0 | General agent tasks | 19.1% | Opus 5 51.8% | Google [48] |

For the fallback, `gemini-3.5-flash-lite` scores 1140 on GDPVal-AA v2, against 907
for Claude Haiku 4.5 [50].

What this supports: 3.8 Flash matches or beats far more expensive models on
analyst-style tasks, at about a sixth of Opus 5's price. What it does not support:
long, open-ended agent work, where Opus 5 leads clearly. Our loop is short and
bounded, so Flash fits. Google's table mixes its own runs with figures other
vendors published [48], so the Vals run is the stronger evidence. Our eval set
remains the real test.

Kimi K3 costs more than Gemini Flash at these prices, so it is not the budget option.
Its license also differs across sources [36]. Qwen3.8-27B is Apache 2.0 [37] and
fits a self-hosted option. Client questions decide this.

## P18. Agent paradigm

Decision: bounded ReAct with typed tools.

| Option | Plus | Minus |
|---|---|---|
| **Bounded ReAct with typed tools** | Every query passes the safety layer | More steps for heavy calculations |
| Code agent | Strong for data processing | Needs a sandbox [38] and adds a second execution path |

**Recommendation:** a ReAct loop. BigQuery does the calculations, and the agent stops
when it has enough evidence or reaches its budget.

## P19. BigQuery knowledge

Decision: a GoogleSQL note, a schema card and business definitions as editable
files.

I found no official Google skill for BigQuery SQL. MCP Toolbox is an official open
source server [39], but it does not replace our safety layer, so the agent calls an
in-process tool. Context7 is not connected to this session.

**Recommendation:** add a short GoogleSQL note, a schema card from real metadata and
business definitions to the prompt, stored as editable files.

## P20. Extensibility

Decision: YAML for prompts, tool descriptions, limits and models. Python for the
graph and tool code.

CrewAI recommends YAML for agents [40], and ADK has YAML Agent Config [41]. I found no
official LangGraph pattern for this.

**Recommendation:** use YAML for prompts, tool descriptions, limits and model
settings, validated with Pydantic.

Every limit, threshold and weight in these proposals lives in the YAML config, not
in code. Each value carries a comment that states why the default is what it is
and where that comes from, for example "5 model calls: client guidance of 2 to 5
calls per question" or "180-day half-life: initial value, tuned with the eval
set". Environment variables can override a value without editing the file. Tool code and the graph stay in Python, with a tool
registry. A graph written in YAML would be harder to test and explain.

## P21. Scope for 12 hours

Decision: the priorities in the table below.

The full list will not fit in 12 hours. This order protects the review criteria:

| Priority | Work |
|---|---|
| Must | CLI, ReAct agent, SQL layer, PII, confirmed delete, resilience, Langfuse and Sentry |
| Must | Postgres setup and init script, because reports and the delete flow need it |
| Must | HLD, technical explanation, setup, example run, sentence-by-sentence traceability |
| Should | HTML report |
| Could | Minimal Ragas run on the 10-question dataset |
| Could | Golden retrieval, clarification node, Presidio, persona table, LangMem preferences |
| Documented only | System learning, consistency eval, deterministic eval, UX study, quality alerts |

Golden retrieval is optional in the brief's prototype list, but it is a strong demo.
I suggest including it only after the Must and Should items pass.

## P22. Scaling under a traffic spike

Decision: the plan below. Design only.

Client load: about 100 active managers a day, 10 questions and 1 saved report each.
That is about 1,000 questions and 100 reports a day, with only a few users active
at the same time. The data grows by about 1M rows a day.

At this load one small Cloud Run instance and a small Cloud SQL instance are
enough, and a queue or Provisioned Throughput is not needed on day one. At 3 to 5
model calls a question, the day needs 3,000 to 5,000 Gemini requests, which a paid
tier handles. The free tier is for the client's testing only.

The table below is the growth path, so a sudden rise to thousands of questions
needs configuration changes, not a redesign. The agent servers are the easy part.
The limits sit in the services they call.

| Part | Limit | Plan |
|---|---|---|
| Agent servers | CPU and memory per instance | Run the agent as a stateless container on Cloud Run. It adds instances when CPU or concurrency passes a target, 60% by default, and can scale to zero [51]. |
| Conversation state | One instance cannot hold another's memory | Keep all state in Postgres through the LangGraph checkpointer [1]. Any instance can continue any conversation, including a paused delete confirmation. |
| Postgres | Connection count | Cloud SQL with a connection pool, so new instances do not exhaust connections |
| Gemini | Shared capacity. A 429 can mean temporary contention, not a fixed quota [52]. | Backoff and the fallback model from P10. A per-user rate limit. Provisioned Throughput for steady high volume, which reserves capacity and spills extra traffic to pay-as-you-go [53]. |
| BigQuery | On demand: up to 2,000 concurrent slots per project, and 1,000 queued interactive queries [54] | The byte cap per query from P10. A cache for repeated questions. Reserved slots if volume stays high. |
| Long reports | A report can take 1 to 2 minutes | At high volume, run report jobs through a queue, Cloud Tasks or Pub/Sub, so a spike waits in line instead of failing |
| Data growth | About 1M new rows a day | Partition the fact tables by `created_at` and cluster them by product and user, so a query for one quarter and one brand scans only that part. The public tables are about 45 MB and have no partitions. |

Pods on GKE would also work, but Cloud Run gives the same scaling without running a
cluster. GKE fits only if the client already runs Kubernetes.

The cost grows with traffic too. P10's per-turn budget and a per-user daily limit
keep a spike from turning into a surprise bill.

## References

1. [LangGraph memory and Postgres checkpointer](https://docs.langchain.com/oss/python/langgraph/add-memory)
2. [AsyncPostgresStore](https://reference.langchain.com/python/langgraph.store.postgres/aio/AsyncPostgresStore)
3. [Hybrid search with Postgres](https://supabase.com/docs/guides/ai/hybrid-search)
4. [pgserver](https://pypi.org/project/pgserver)
5. [DAIL-SQL paper](https://arxiv.org/pdf/2308.15363)
6. [OpenSearch-SQL paper](https://arxiv.org/html/2502.14913v1)
7. [Text2SQL-Flow paper](https://arxiv.org/pdf/2511.10192)
8. [Generative Agents paper](https://arxiv.org/pdf/2304.03442)
9. [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
10. [Presidio FAQ](https://github.com/microsoft/presidio/blob/main/docs/faq.md)
11. [NeMo Guardrails vs Guardrails AI](https://aisecurityandsafety.org/en/compare/nemo-guardrails-vs-guardrails-ai/)
12. [LangChain Deep Agents memory](https://docs.langchain.com/oss/python/deepagents/memory)
13. [LangMem conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
14. [OpenAI agent improvement loop](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)
15. [Estimate and control BigQuery costs](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)
16. [SQL generation survey citing ReFoRCE](https://arxiv.org/html/2601.17942v1)
17. [SDE-SQL paper](https://arxiv.org/abs/2506.07245)
18. [SQLCritic paper](https://arxiv.org/html/2503.07996v1)
19. [SQL-of-Thought paper](https://arxiv.org/pdf/2509.00581)
20. [Gemini troubleshooting](https://aistudio.google.com/docs/troubleshooting)
21. [Gemini API errors](https://aistudio.google.com/docs/api-errors)
22. [BigQuery error messages](https://docs.cloud.google.com/bigquery/docs/error-messages)
23. [Gemini rate limits](https://aistudio.google.com/docs/rate-limits)
24. [Ragas available metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
25. [Anthropic: demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
26. [Ragas v0.3 to v0.4 migration](https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/)
27. [OpenAI Realtime Eval Guide](https://developers.openai.com/cookbook/examples/realtime_eval_guide)
28. [AmbiSQL paper](https://arxiv.org/abs/2508.15276)
29. [PRACTIQ paper](https://arxiv.org/abs/2410.11076)
30. [Rasa: measuring AI agent performance](https://rasa.com/blog/measure-ai-agent-performance-in-the-contact-center)
31. [Langfuse LangChain and LangGraph integration](https://langfuse.com/integrations/frameworks/langchain)
32. [Top LLM observability platforms 2026](https://guptadeepak.com/tools/top-5-llm-observability-platforms-2026/)
33. [Sentry LangGraph integration](https://docs.sentry.io/platforms/python/integrations/langgraph/)
34. [Gemini pricing](https://aistudio.google.com/docs/pricing)
35. [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing)
36. [Kimi K3 summary](https://llmgateway.io/blog/kimi-k3)
37. [Qwen3.8 licensing report](https://www.eweek.com/news/alibaba-qwen3-8-27b-license-apac-china/)
38. [smolagents](https://pypi.org/project/smolagents/1.23.0/)
39. [MCP Toolbox for BigQuery codelab](https://codelabs.developers.google.com/mcp-toolbox-bigquery-dataset)
40. [CrewAI concepts](https://docs.crewai.com/concepts)
41. [ADK Agent Config overview](https://hackernoon.com/the-fastest-way-to-prototype-agents-declare-the-what-let-adk-run-the-how)
42. [pgvector installation](https://github.com/pgvector/pgvector#installation)
43. [LangMem on PyPI](https://pypi.org/project/langmem/) and [repository](https://github.com/langchain-ai/langmem)
44. [Langfuse vs Sentry for AI agents](https://langfuse.com/compare/sentry)
45. [Langfuse pricing](https://langfuse.com/pricing)
46. [Sentry pricing](https://sentry.io/pricing/)
47. [Annotation errors in text-to-SQL benchmarks](https://arxiv.org/abs/2601.08778)
48. [Gemini 3.8 Flash model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/)
49. [Vals AI results for Gemini 3.8 Flash](https://www.vals.ai/models/google_gemini-3.8-flash)
50. [Gemini 3.5 Flash-Lite model card](https://deepmind.google/models/model-cards/gemini-3-5-flash-lite/)
51. [Cloud Run instance autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)
52. [Vertex AI Dynamic Shared Quota](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/dsq)
53. [Use Provisioned Throughput](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/use-provisioned-throughput)
54. [BigQuery quotas and limits](https://docs.cloud.google.com/bigquery/quotas)
