# Configuration

Every limit, model choice and data rule lives here, not in code. Each value has
a comment that says why the default is what it is and where it comes from.
`src/retail_analyst/core/config.py` loads and validates all files at start-up,
so a typo stops the app with a clear error instead of a silent default.

| Folder | File | What it controls |
|---|---|---|
| `agent/` | `limits.yaml` | Budget for one question: model calls, repairs, queries, time, cost |
| `agent/` | `models.yaml` | Gemini models in fallback order, other providers switched off |
| `data/` | `bigquery.yaml` | Dataset, byte cap, timeout, row limit |
| `data/` | `schema.yaml` | Columns of the four tables, with descriptions |
| `data/` | `safety.yaml` | Blocked columns, hashed IDs, demographic rules |
| `seed/` | `demo.yaml` | Demo users, their brands and the first persona |

To change one value without editing a file, set an environment variable named
`RETAIL_ANALYST__<SECTION>__<KEY>`, for example:

```bash
export RETAIL_ANALYST__LIMITS__MODEL_CALLS=4
```

Section names are the keys of `SECTION_FILES` in `core/config.py`.
