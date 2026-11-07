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
| 7 | BigQuery runner: dry run before every query, byte cap, job timeout, row cap, retry deadlines cut to the query timeout, errors mapped to repair, narrow or stop | 7 unit tests, 3 integration tests: row cap, byte cap, unknown column | next commit |

## Problems found and fixed

| Problem | Fix |
|---|---|
| `.gitignore` rule `data/` hid `config/data/` from git | Rule narrowed to `/data/` |
| `ruff --fix` edited the client's starter code | Restored from git, `docs/` excluded from lint |
| Appending to `.env` without a trailing newline merged two lines | Repaired the file, values never printed |
| Config temperature 0.2 contradicted Google's Gemini 3 guidance | Set to the default 1.0 with the source in a comment |
| The BigQuery client retries for up to 10 minutes by default, far beyond the 30-second budget | Both retry deadlines set to `query_timeout_seconds` |

## Next

1. Gemini model wrapper with the fallback chain from `config/agent/models.yaml`
2. Agent graph: context, input checks, agent loop with tools, output guard
3. Delete flow with `interrupt()` and stored report IDs
4. Reports: structured sections, Jinja HTML, `/open <id>`
5. Observability: Langfuse and Sentry, both optional through `.env`
6. CLI
7. Docs: technical explanation, requirement traceability, setup, example run

## Not tested yet

- Anything with Gemini calls in the agent loop
- Langfuse and Sentry, since no keys exist yet. Accounts: cloud.langfuse.com and sentry.io.
- Debian or Ubuntu install steps, written from the pgvector docs but not run
- Mermaid diagrams in `docs/02-architecture.md`, not rendered locally
