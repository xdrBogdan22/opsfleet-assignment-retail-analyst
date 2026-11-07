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
| 17 | Output guard: Presidio with the small spaCy model, pinned in `uv.lock`, on the final answer and on report text before saving. Values from query results are allowed. | 4 unit tests, 1 graph test. Live CEO run: brand names such as Calvin Klein kept, top-5 figures matched BigQuery to the cent. | next commit |

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

## Next

1. Observability: Langfuse and Sentry, both optional through `.env`
2. Docs: technical explanation, requirement traceability, setup, example run

## Not tested yet

- Langfuse and Sentry, since no keys exist yet. Accounts: cloud.langfuse.com and sentry.io.
- Debian or Ubuntu install steps, written from the pgvector docs but not run
- Mermaid diagrams in `docs/02-architecture.md`, not rendered locally
