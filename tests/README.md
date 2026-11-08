# Tests

The folders mirror `src/retail_analyst/`.

| Folder | What runs | Needs |
|---|---|---|
| `safety/` | SQL guard rules and output guard redaction | Nothing; the spaCy model is a locked dependency |
| `warehouse/` | Error classification and value conversion for the BigQuery runner | Nothing |
| `agent/` | Graph routing, budgets, refusals, clarification pause, output guard, with scripted models | Nothing |
| `cli/` | A confirmed delete removes the report's browser copy | Nothing |
| `observability/` | Turn summary and feedback logging without services | Nothing |
| `reports/` | Escaping, chart marks, plain text | Nothing |
| `tools/` | Tool budget, repair accounting, hidden context, schema card | Nothing |
| `llm/` | Fallback chain wiring, config errors, circuit breaker | Nothing |
| `integration/` | Guarded queries and runner limits on real BigQuery, model calls and fallback on real Gemini, report storage and the delete confirmation on local Postgres | `GOOGLE_CLOUD_PROJECT`, signed-in gcloud, `GOOGLE_API_KEY`, `DATABASE_URL` |

```bash
uv run --frozen pytest                    # everything
uv run --frozen pytest -m "not integration"   # no network
```

Integration tests skip themselves when their key is not set. Each BigQuery
query scans a few MB of the public dataset, and the Gemini tests make two short
calls.
