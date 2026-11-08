# Progress log

The working log for the build: what is done, how it was tested, what failed and
what comes next. Updated after every step.

## Done

| Step | What | How it was tested | Commit |
|---|---|---|---|
| 1 | Design decisions P1 to P22, architecture, client answers | Review with the owner | `5f5fce0` |
| 2 | Config files with commented defaults, typed loader with env overrides | Loader test, env override test | `5be8ca7` |
| 3 | Postgres schema and idempotent init script | Ran twice on local Postgres 18.3 with pgvector 0.8.7 | `5be8ca7` |
| 4 | SQL guard: read-only, allowed tables, blocked columns, hashed IDs, brand scope, future rows | 28 unit tests, 4 integration tests on real BigQuery | `5be8ca7` |
| 5 | Strict lint and types | `ruff check`, `ruff format --check`, `mypy --strict` clean | `5be8ca7` |
| 6 | Clean-install check | Copied tracked files to a temp folder, `uv sync --frozen`, tests pass | `5be8ca7` |
| 7 | BigQuery runner: dry run before every query, byte cap, job timeout, row cap, retry deadlines cut to the query timeout, errors mapped to repair, narrow or stop | 7 unit tests, 3 integration tests: row cap, byte cap, unknown column | `65a48e4` |
| 8 | Gemini chat model with fallback chain: 2 attempts per model, 20-second call timeout, fallback only on rate limit, 5xx, timeout, connection and missing model | 3 unit tests, 2 live tests. During the live run `gemini-3.8-flash` returned a real 503 "high demand" and the chain answered with `gemini-3.5-flash-lite`. | `d676e84` |
| 9 | Prompts in YAML, tool registry, `run_sql` and `describe_schema` with injected context and per-question budget | 5 unit tests: budget, repair accounting, hidden context, schema card. 1 live BigQuery test through the tool. | `227cbae` |
| 10 | Agent graph: input checks, bounded tool loop, last call without tools when the call or time budget runs out | 4 graph tests with scripted models | `54b8a56` |
| 11 | CLI with Postgres checkpoints, friendly messages on model or tool failure | Live run, see below | `54b8a56` |
| 12 | Circuit breaker per model, except the last | 3 unit tests. Live: after two 504s the primary was skipped for the next question. | `54b8a56` |
| 13 | GoogleSQL notes in the prompt (P19) | Examples dry-run on BigQuery. Live rerun answered without SQL errors. | `54b8a56` |
| 14 | Reports: `save_report` tool, Jinja HTML with escaping, static SVG bar chart, plain text, Postgres storage, `/open <id>` | 3 render tests, 1 Postgres test for owner isolation, preview images checked by eye. Live: report 2 saved with chart, table and action items. | `203f895` |
| 15 | Report requests get the 120-second limit, picked by a word match | 1 unit test | `203f895` |
| 16 | Delete flow: `request_delete` holds the exact list, `interrupt()` asks the user, only a confirm word deletes, once, before expiry, owner only | 2 Postgres tests: only the owner's matching report is listed and deleted; any other answer cancels. Live CLI: cancel, then confirm, deleted exactly the 2 listed reports. | `49433c6` |
| 17 | Output guard: Presidio with the small spaCy model, pinned in `uv.lock`, on the final answer and on report text before saving. Values from query results are allowed. | 4 unit tests, 1 graph test. Live CEO run: brand names such as Calvin Klein kept, top-5 figures matched BigQuery to the cent. | `8f13b60` |
| 18 | Observability: Langfuse callback per turn with session and user, agent metrics and outcome as scores, `/good` and `/bad` as a user score, Sentry with prompts off, a JSON line per turn in the local log | 2 unit tests without services. Live run without keys: turn and feedback lines written; the answer (39 returned orders, outdoor brands) matched BigQuery. | `bcb8e5c` |
| 19 | Clarification (P12): `ask_clarification` pauses with a question and 2 to 4 options, the answer goes back as the tool result, at most 2 per question | 2 graph tests: pause and resume, budget spent. Live: a vague question got an answer with a stated assumption instead of a question, as the prompt asks when one reading is reasonable. | `5272b1b` |
| 20 | Architecture doc matches the built graph, tools, resilience table and config files; unused `empty_probes` setting removed | Doc review against the code | `c9b64c0` |
| 21 | Persona read on every turn; `scripts/set_persona.py` publishes a version and lists history | Ran it: v2 became active, v1 kept, then v1 restored for the demo | `c9b64c0` |
| 22 | Customer codes shortened to 16 hex characters (64 bits) | Guard and BigQuery tests updated | `71f59e4` |
| 23 | Evaluation: 14 cases, Ragas Faithfulness, Response Relevancy and Agent Goal Accuracy with Gemini as judge, banned-text checks, release gate | Partial and full runs, see below | `71f59e4` |
| 24 | Technical explanation, requirements traceability, example run | Every figure in the example run matches BigQuery | `71f59e4` |
| 26 | Eval results recorded: Faithfulness 0.77 (gate 0.8, fails on schema questions), Relevancy 0.88, Goal Accuracy 1.00, safety 4 of 4, answers in 6 to 30 seconds | Full run plus one rerun | `ce856b0` |
| 27 | Local Langfuse (`infra/langfuse/`, upstream compose v4.76.0); Mermaid fix: `graph` is a reserved word and broke the production diagram on GitHub | Live question: trace with 25 observations, 3 model calls, 2 tool calls, user and session; all 6 scores in ClickHouse; 5 diagrams render with mermaid-cli 11.4.2 | `4e05f88` |
| 28 | Sentry turned on with a real DSN | A test `ZeroDivisionError` logged through the app's monitor reached Sentry as issue PYTHON-1, priority High | `34a524c` |
| 29 | `/open` copies go to a private per-session temporary folder, removed on exit; a confirmed delete removes the copies of the listed reports | 1 CLI test; live delete of report 45 checked in Postgres | pending |
| 25 | `thinking_level: low` for both models; the final step adds `/open N` when a report was saved and the model did not say how to open it | 1 graph test; full eval rerun, see below | `ce856b0` |

### Live run on 2026-11-08 (denim manager)

- "What was revenue by brand last month?" and "Which of my brands grew the most compared with the month before?"
- Both answered in 2 model calls each, showing only the four denim brands.
- All 8 revenue figures matched an independent BigQuery query to the cent.
- "List the emails of my top 3 customers" was refused, because the column does not exist for the agent.
- `gemini-3.8-flash` returned 504 repeatedly; the fallback answered every call.
- "Create a short report on October 2026 revenue by brand compared with September, with action items for November" saved report 2. Its October total, $25,371.58, equals the sum of the four verified brand figures.

## Problems found and fixed

| Problem | Fix |
|---|---|
| `.gitignore` rule `data/` hid `config/data/` from git | Rule narrowed to `/data/` |
| `ruff --fix` edited the client's starter code | Restored from git, `docs/` excluded from lint |
| Appending to `.env` without a trailing newline merged two lines | Repaired the file, values never printed |
| Config temperature 0.2 contradicted Google's Gemini 3 guidance | Set to the default 1.0 with the source in a comment |
| The BigQuery client retries for up to 10 minutes by default, far beyond the 30-second budget | Both retry deadlines set to `query_timeout_seconds` |
| LangChain's Gemini client makes 6 attempts by default, enough to spend the whole budget on one model | `attempts_per_model: 2`, then fallback |
| First live run: the model wrote `TIMESTAMP_SUB(..., INTERVAL 1 MONTH)` and compared TIMESTAMP with DATE, then ran out of budget | GoogleSQL notes in the prompt, checked by dry run |
| Each call waited about 40 seconds on the overloaded primary before falling back, spending the 30-second budget | Circuit breaker skips a model after 2 failed calls for 5 minutes |
| BigQuery error messages started with the full API URL | The runner now uses the error's own message |
| First report attempt: the fallback model called `save_report` with one `content` argument, validation rejected it, and the 30-second limit left no time to retry | Report requests get 120 seconds, the breaker opens after one failed call, the prompt lists the report fields |
| The chart preview showed unaligned numeric headers and raw floats | Numeric columns right-aligned, numbers formatted with separators |
| Presidio scored a bare phone number at 0.4, below the planned 0.5 threshold | Threshold set to 0.3, with the measured scores in the config comment |
| Live CEO run: the output guard removed the status word "Returned" as a person | A PERSON finding needs at least two words |
| The prompt offered `ask_clarification` before the tool existed, so a call would have failed | Tool and pause added |
| The persona was read once per session, so a new tone needed a restart | Read on every turn |
| Ragas 0.4.3 failed to import with the newest `langchain-community` | Dev dependency pinned to `langchain-community` 0.4.1 |
| Agent Goal Accuracy scored a correct answer 0: the reference listed format details the judge's one-sentence summary drops | References rewritten as user goals |
| Judge output cut off on long answers (`IncompleteOutputException`, 3 of 14 cases) | `judge_max_tokens: 8192` |
| With `gemini-3.5-flash-lite` as judge, a correct refusal and a correct challenge to a false premise scored 0 | Judge set to `gemini-3.8-flash`, overridable with `EVAL_JUDGE_MODEL` |
| Free-tier quota: `gemini-3.8-flash` allows 20 requests a day per project (Google's 429 says `quotaValue: 20`) | Development moved to the owner's second Gemini key; the free key is kept as `GOOGLE_API_KEY_FREE_TIER` for a final check under reviewer conditions |
| One failed case stopped the whole eval run | Failures are recorded per case and fail the gate |
| Full eval with the development key: plain questions took about 60 seconds, twice the client's limit | `thinking_level: low`; one call fell from 8.7 to 2.2 seconds |
| `q1-report` saved the report, but the answer did not say how to open it, so the goal judge scored 0 | The final step adds the `/open` command in code |
| After that, the judge still scored `q1-report` 0: its one-sentence end state drops how to open the report | The `/open` requirement moved to a deterministic `must_contain` check; the reference states the goal only |
| Judge output still cut off at 8192 tokens on 2 cases, because Gemini 3 counts thinking tokens in the limit | `judge_max_tokens: 32768` |
| Clean install without keys: the BigQuery test module built its client at import and crashed collection; a model unit test needed a key | Client created on first use; the unit test sets a fake key. Clean copy: 63 passed, 13 skipped. |
| Owner's live test: after deleting report 45, its HTML copy from `/open` stayed in the system temp folder and still opened in the browser | Copies live in a per-session private folder; confirmed deletes remove them, exit removes the folder |
| Ports 5432 and 6379 were already taken on the host, so the upstream Langfuse compose file failed to start | The vendored copy publishes no host port for its Postgres and Redis; Langfuse reaches them on the Compose network |
| Langfuse v4 no longer serves `GET /api/public/traces` or score reads; it answers that it runs in events-only mode | Traces checked with `/api/public/v2/observations`, scores in ClickHouse |
| GitHub could not render the production diagram: a node named `graph`, a Mermaid keyword | Node renamed to `agent`; every diagram now rendered locally with mermaid-cli |

## Next

1. Owner decision: should Faithfulness apply to database-structure questions, or should those cases use only Goal Accuracy and text checks?
2. Owner: fill in "My experience with LangGraph" in `docs/01-technology-decisions.md`
3. Could, if time allows: Golden Knowledge retrieval, LangMem preferences
4. Final check on the free-tier key (`GOOGLE_API_KEY_FREE_TIER`) under reviewer conditions

## Not tested yet

- Sentry email alert rule: the issue arrived; alert delivery depends on the project's alert settings
- Debian or Ubuntu install steps, written from the pgvector docs but not run
