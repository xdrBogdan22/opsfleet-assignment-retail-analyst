"""Check that local credentials reach BigQuery and Gemini without spending quota."""

import os
import sys

from dotenv import load_dotenv
from google import genai
from google.cloud import bigquery

DATASET = "bigquery-public-data.thelook_ecommerce"
REQUIRED_TABLES = ("orders", "order_items", "products", "users")


def check_bigquery(project: str) -> str:
    client = bigquery.Client(project=project)
    tables = " UNION ALL ".join(f"SELECT COUNT(*) AS n FROM `{DATASET}.{name}`" for name in REQUIRED_TABLES)
    job = client.query(
        tables,
        job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False),
    )
    return f"BigQuery ok: dry run would scan {job.total_bytes_processed:,} bytes"


def check_gemini() -> str:
    client = genai.Client()
    names = [model.name for model in client.models.list() if "gemini" in (model.name or "")]
    if not names:
        raise RuntimeError("the API key works, but no Gemini model is available")
    return f"Gemini ok: {len(names)} models available"


def main() -> None:
    load_dotenv()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", project),
            ("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY")),
        )
        if not value
    ]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")

    failed = False
    for check, args in ((check_bigquery, (project,)), (check_gemini, ())):
        try:
            print(check(*args))
        except Exception as error:
            failed = True
            print(f"{check.__name__} failed: {error}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
