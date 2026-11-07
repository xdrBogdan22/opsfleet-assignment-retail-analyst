import json
from typing import Any, cast

from retail_analyst.core.config import get_settings
from retail_analyst.safety.sql_guard import Scope
from retail_analyst.tools.context import Budget, ToolContext
from retail_analyst.tools.data import run_sql, schema_card
from retail_analyst.tools.registry import build_tools

SETTINGS = get_settings()


def context(queries: int = 5, repairs: int = 2) -> ToolContext:
    # The guard rejects these queries before BigQuery is reached, so no client is needed.
    return ToolContext(
        scope=Scope(user_id="denim_manager", brands=("Diesel",)),
        settings=SETTINGS,
        bigquery=cast(Any, None),
        id_salt="s",
        budget=Budget(queries_left=queries, repairs_left=repairs),
    )


def call(queries: list[str], ctx: ToolContext) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads(run_sql(queries, ctx)))


def test_schema_card_hides_blocked_columns() -> None:
    card = schema_card(SETTINGS)
    assert "sale_price" in card
    for columns in SETTINGS.safety.blocked_columns.values():
        for column in columns:
            assert f"- {column} " not in card


def test_rule_violations_do_not_spend_repairs() -> None:
    ctx = context()
    [result] = call(["SELECT email FROM users"], ctx)
    assert "Do not retry" in result["next_step"]
    assert ctx.budget.repairs_left == 2
    assert ctx.budget.queries_left == 4


def test_syntax_errors_spend_a_repair_until_none_are_left() -> None:
    ctx = context(repairs=1)
    first, second = call(["SELEC 1", "SELEC 2"], ctx)
    assert first["next_step"] == "Fix the SQL and try again."
    assert "No repairs left" in second["next_step"]


def test_query_budget_is_enforced() -> None:
    ctx = context(queries=1)
    _, second = call(["SELECT email FROM users", "SELECT email FROM users"], ctx)
    assert "budget" in second["error"]


def test_model_never_sees_the_injected_context() -> None:
    for tool in build_tools(SETTINGS):
        assert "ctx" not in tool.tool_call_schema.model_json_schema().get("properties", {})  # type: ignore[union-attr]
