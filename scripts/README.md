# Scripts

One-off commands for setup and checks. Run each from the repository root.

| Script | What it does |
|---|---|
| `doctor.py` | Checks the BigQuery and Gemini connections without scanning data or generating text |
| `init_db.py` | Creates the Postgres tables and demo data. Safe to run again. |

```bash
uv run --frozen python scripts/doctor.py
uv run --frozen python scripts/init_db.py
```
