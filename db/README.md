# Database

`schema.sql` creates the application tables in Postgres. It is safe to run more
than once. `scripts/init_db.py` runs it, loads the demo data from
`config/seed/demo.yaml` and lets LangGraph create its checkpoint tables.

| Table | Holds |
|---|---|
| `app_users`, `user_brands` | Demo users and the brands each one may analyze |
| `personas` | Versioned tone instructions, one active version |
| `reports` | Saved reports as HTML and plain text, with a full-text index |
| `delete_requests` | The exact report IDs a user confirmed for deletion |
| `checkpoint*` | Conversation state, created and owned by LangGraph |

The transaction data stays in BigQuery and is never copied here.
