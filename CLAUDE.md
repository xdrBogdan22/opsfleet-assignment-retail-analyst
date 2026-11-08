# CLAUDE.md

A CLI data analyst agent: LangGraph, Gemini, BigQuery `thelook_ecommerce`,
Postgres. Design in `docs/02-architecture.md`, build log in `docs/progress.md`.

## Commands

```bash
uv sync --frozen
uv run --frozen pytest -m "not integration"   # unit tests, no keys needed
uv run --frozen pytest                        # plus live BigQuery, Gemini, Postgres
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen mypy src
uv run --frozen retail-analyst --user denim_manager
```

## Rules that protect the design

1. **Code enforces safety, the prompt does not.** Brand scope, blocked columns
   and hashed IDs live in `safety/sql_guard.py`. Every query, from any tool,
   goes through `make_safe` and then `warehouse/bigquery_runner.run_query`.
   Never run SQL on BigQuery another way.
2. **The model proposes, code disposes.** Anything that changes data or leaves
   the system (delete, and later mail) returns a pending request from the
   tool, and a graph node pauses with `interrupt()` for the user's
   confirmation. See `confirm_delete` in `agent/graph.py`.
3. **Every limit and rule lives in `config/`,** with a comment saying why the
   default is what it is. Settings models in `core/config.py` are strict
   (`extra="forbid"`), so a new YAML key needs its field there.
4. **The model never sees who the user is in a form it can change.** Tools get
   a `ToolContext` argument marked `InjectedToolArg`; the model fills only the
   other arguments.
5. **Text that reaches the user passes the output guard** (`safety/output_guard.py`),
   and stored text passes `redact_strings`.
6. **Every retry is bounded:** model calls, queries, repairs, seconds, bytes.
   A new loop gets a limit in `config/agent/limits.yaml`.

## Code style

- Small modules, each opening with a docstring that states what it guarantees.
  Comments explain constraints, not what the next line does.
- Tool results are JSON strings; errors go back to the model as
  `{"error": "..."}`, never as exceptions.
- Tests sit in `tests/<package>/`. Unit tests use no network: graph tests use
  `ScriptedModel` in `tests/agent/test_graph.py`, tool tests build a
  `ToolContext` as in `tests/tools/test_data_tools.py`. Live tests carry
  `@pytest.mark.integration`.
- Secrets live in `.env` only and are never printed.

## Docs

English, plain sentences, sentence-case headings, no em dashes. Each finished
step adds a row to `docs/progress.md`; open problems go to
`docs/known-limitations.md`.

## Skills

- `/add-tool` adds a capability to the agent, from function to eval case.
