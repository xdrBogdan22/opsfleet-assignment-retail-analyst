# Tests

The folders mirror `src/retail_analyst/`.

| Folder | What runs | Needs |
|---|---|---|
| `safety/` | Unit tests for the SQL guard | Nothing |
| `warehouse/` | Error classification and value conversion for the BigQuery runner | Nothing |
| `tools/` | Tool budget, repair accounting, hidden context, schema card | Nothing |
| `llm/` | Fallback chain wiring and config errors | Nothing |
| `integration/` | Guarded queries and runner limits on real BigQuery, model calls and fallback on real Gemini | `GOOGLE_CLOUD_PROJECT`, signed-in gcloud, `GOOGLE_API_KEY` |

```bash
uv run --frozen pytest                    # everything
uv run --frozen pytest -m "not integration"   # no network
```

Integration tests skip themselves when their key is not set. Each BigQuery
query scans a few MB of the public dataset, and the Gemini tests make two short
calls.
