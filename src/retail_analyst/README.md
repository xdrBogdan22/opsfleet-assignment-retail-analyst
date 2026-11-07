# retail_analyst package

| Package | Responsibility |
|---|---|
| `core/` | Settings loaded from `config/` |
| `safety/` | The SQL guard: turns model-written SQL into scoped, read-only SQL |
| `tools/` | Tools the model can call, their injected context and the per-question budget |
| `llm/` | Chat model with the Gemini fallback chain |
| `warehouse/` | Runs guarded SQL on BigQuery within byte, time and row limits, and classifies errors |

Rules for code in this package:

- Data rules and limits come from settings, never from literals in code.
- Safety checks are plain functions with no model calls, so tests can prove them.
- Each module starts with a docstring that says what it guarantees.
