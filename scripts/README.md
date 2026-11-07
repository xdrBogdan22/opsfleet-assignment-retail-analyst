# Scripts

One-off commands for setup and checks. Run each from the repository root.

| Script | What it does |
|---|---|
| `doctor.py` | Checks the BigQuery and Gemini connections without scanning data or generating text |
| `init_db.py` | Creates the Postgres tables and demo data. Safe to run again. |
| `set_persona.py` | Publishes a new report tone, or lists every version with `--show`. Applies from the next question, no restart. |

```bash
uv run --frozen python scripts/doctor.py
uv run --frozen python scripts/init_db.py
```
