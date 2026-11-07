"""Runs rewritten queries on real BigQuery.

Skipped without GOOGLE_CLOUD_PROJECT. Each query scans a few MB of the public
dataset, well inside the free tier.
"""

import os

import pytest
from dotenv import load_dotenv
from google.cloud import bigquery

from retail_analyst.core.config import get_settings
from retail_analyst.safety.sql_guard import SafeQuery, Scope, make_safe

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("GOOGLE_CLOUD_PROJECT"), reason="needs GOOGLE_CLOUD_PROJECT"),
]

SETTINGS = get_settings()
DENIM = Scope(user_id="denim_manager", brands=("Diesel", "True Religion", "7 For All Mankind", "Joe's Jeans"))
CEO = Scope(user_id="ceo", brands=None)


def run(query: SafeQuery) -> list[dict[str, object]]:
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = []
    for name, value in query.params.items():
        if isinstance(value, list):
            params.append(bigquery.ArrayQueryParameter(name, "STRING", value))
        else:
            params.append(bigquery.ScalarQueryParameter(name, "STRING", value))
    client = bigquery.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
    config = bigquery.QueryJobConfig(
        query_parameters=params, maximum_bytes_billed=SETTINGS.bigquery.max_bytes_billed
    )
    return [dict(row) for row in client.query(query.sql, job_config=config).result()]


def test_manager_sees_only_own_brands() -> None:
    sql = (
        "SELECT p.brand, ROUND(SUM(oi.sale_price)) AS revenue FROM order_items oi "
        "JOIN products p ON p.id = oi.product_id GROUP BY 1"
    )
    rows = run(make_safe(sql, DENIM, SETTINGS, id_salt="s"))
    assert {row["brand"] for row in rows} == set(DENIM.brands or ())


def test_unjoined_order_items_are_scoped_too() -> None:
    sql = "SELECT COUNT(DISTINCT product_id) AS products FROM order_items"
    manager = run(make_safe(sql, DENIM, SETTINGS, id_salt="s"))[0]["products"]
    everyone = run(make_safe(sql, CEO, SETTINGS, id_salt="s"))[0]["products"]
    assert isinstance(manager, int)
    assert isinstance(everyone, int)
    assert 0 < manager < everyone


def test_customer_ids_are_hashed_consistently_across_tables() -> None:
    sql = (
        "SELECT oi.user_id, COUNT(*) AS items FROM order_items oi "
        "JOIN users u ON u.id = oi.user_id GROUP BY 1 ORDER BY 2 DESC LIMIT 3"
    )
    rows = run(make_safe(sql, DENIM, SETTINGS, id_salt="s"))
    assert len(rows) == 3
    assert all(isinstance(row["user_id"], str) and len(row["user_id"]) == 64 for row in rows)


def test_no_future_rows() -> None:
    sql = "SELECT COUNTIF(created_at > CURRENT_TIMESTAMP()) AS future FROM orders"
    assert run(make_safe(sql, CEO, SETTINGS, id_salt="s"))[0]["future"] == 0
