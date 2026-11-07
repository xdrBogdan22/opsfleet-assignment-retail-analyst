# Tests

The folders mirror `src/retail_analyst/`.

| Folder | What runs | Needs |
|---|---|---|
| `safety/` | Unit tests for the SQL guard | Nothing |
| `integration/` | Rewritten queries on real BigQuery | `GOOGLE_CLOUD_PROJECT` and signed-in gcloud |

```bash
uv run --frozen pytest                    # everything
uv run --frozen pytest -m "not integration"   # no network
```

Integration tests skip themselves when `GOOGLE_CLOUD_PROJECT` is not set. Each
query scans a few MB of the public dataset.
