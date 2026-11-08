"""Runs guarded queries on real BigQuery through the runner.

Skipped without GOOGLE_CLOUD_PROJECT. Each query scans a few MB of the public
dataset, well inside the free tier.
"""

import json
import os
from typing import Any, cast

import pytest
from dotenv import load_dotenv
from google.cloud import bigquery

from retail_analyst.core.config import get_settings
from retail_analyst.safety.sql_guard import SafeQuery, Scope, make_safe
from retail_analyst.tools.context import Budget, ToolContext
from retail_analyst.tools.data import run_sql
from retail_analyst.warehouse.bigquery_runner import FailureKind, QueryFailedError, run_query

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("GOOGLE_CLOUD_PROJECT"), reason="needs GOOGLE_CLOUD_PROJECT"),
]

SETTINGS = get_settings()
DENIM = Scope(user_id="denim_manager", brands=("Diesel", "True Religion", "7 For All Mankind", "Joe's Jeans"))
CEO = Scope(user_id="ceo", brands=None)
CLIENT = bigquery.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))


def run(query: SafeQuery) -> list[dict[str, object]]:
    return run_query(CLIENT, query, SETTINGS.bigquery).rows


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
    length = SETTINGS.safety.hashed_id_length
    assert all(isinstance(row["user_id"], str) and len(row["user_id"]) == length for row in rows)


def test_no_future_rows() -> None:
    sql = "SELECT COUNTIF(created_at > CURRENT_TIMESTAMP()) AS future FROM orders"
    assert run(make_safe(sql, CEO, SETTINGS, id_salt="s"))[0]["future"] == 0


def test_runner_returns_capped_rows() -> None:
    query = make_safe("SELECT id, brand FROM products", CEO, SETTINGS, id_salt="s")
    result = run_query(CLIENT, query, SETTINGS.bigquery)
    assert len(result.rows) == SETTINGS.bigquery.max_rows
    assert result.truncated


def test_runner_rejects_queries_above_the_byte_cap() -> None:
    tiny = SETTINGS.bigquery.model_copy(update={"max_bytes_billed": 1000})
    query = make_safe("SELECT COUNT(*) FROM order_items", CEO, SETTINGS, id_salt="s")
    with pytest.raises(QueryFailedError) as error:
        run_query(CLIENT, query, tiny)
    assert error.value.kind is FailureKind.NARROW


def test_runner_flags_unknown_columns_for_repair() -> None:
    query = make_safe("SELECT revenue FROM order_items", CEO, SETTINGS, id_salt="s")
    with pytest.raises(QueryFailedError) as error:
        run_query(CLIENT, query, SETTINGS.bigquery)
    assert error.value.kind is FailureKind.REPAIR


def test_run_sql_tool_returns_scoped_rows() -> None:
    ctx = ToolContext(
        scope=DENIM,
        author="Alex",
        conversation_id="c1",
        settings=SETTINGS,
        bigquery=CLIENT,
        db=cast(Any, None),
        id_salt="s",
        budget=Budget.for_question(SETTINGS),
        known_values=set(),
    )
    sql = "SELECT DISTINCT p.brand FROM products p"
    [result] = json.loads(run_sql([sql], ctx))
    assert {row["brand"] for row in result["rows"]} == set(DENIM.brands or ())
