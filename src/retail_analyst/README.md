# retail_analyst package

| Package | Responsibility |
|---|---|
| `cli/` | The command-line chat |
| `agent/` | The LangGraph graph, the per-user session and the system prompt |
| `core/` | Settings loaded from `config/`, the shared Postgres pool |
| `safety/` | The SQL guard: turns model-written SQL into scoped, read-only SQL |
| `reports/` | Report structure, HTML and text rendering with static SVG charts, storage in Postgres |
| `tools/` | Tools the model can call, their injected context and the per-question budget |
| `llm/` | Chat model with the Gemini fallback chain and a circuit breaker per model |
| `warehouse/` | Runs guarded SQL on BigQuery within byte, time and row limits, and classifies errors |

Rules for code in this package:

- Data rules and limits come from settings, never from literals in code.
- Safety checks are plain functions with no model calls, so tests can prove them.
- Each module starts with a docstring that says what it guarantees.
