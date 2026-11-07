"""Tools that read the warehouse: run_sql and describe_schema."""

import json
from typing import Annotated

from langchain_core.tools import InjectedToolArg
from pydantic import Field

from retail_analyst.core.config import Settings
from retail_analyst.safety.sql_guard import QueryRejectedError, make_safe
from retail_analyst.tools.context import ToolContext
from retail_analyst.warehouse.bigquery_runner import FailureKind, QueryFailedError, run_query

NEXT_STEP = {
    FailureKind.REPAIR: "Fix the SQL and try again.",
    FailureKind.NARROW: "Ask for less data: filter by date, aggregate, or select fewer columns.",
    FailureKind.STOP: "Tell the user the data service is unavailable right now. Do not retry.",
}
BUDGET_SPENT = "The query budget for this question is spent. Answer with what you have."
RULE_LIMIT = "Explain this limit to the user. Do not retry."
NO_REPAIRS = "No repairs left. Explain what failed to the user."
NO_ROWS = "No rows matched. Check the filter values once before concluding there is no data."
QUERIES_HELP = "GoogleSQL SELECT statements, one per item"


def run_sql(
    queries: Annotated[list[str], Field(min_length=1, description=QUERIES_HELP)],
    ctx: Annotated[ToolContext, InjectedToolArg],
) -> str:
    return json.dumps([_run_one(sql, ctx) for sql in queries], default=str)


def describe_schema(ctx: Annotated[ToolContext, InjectedToolArg]) -> str:
    return schema_card(ctx.settings)


def schema_card(settings: Settings) -> str:
    """The tables and columns the agent may use. Blocked columns never appear."""
    lines = []
    for table, spec in settings.dataset_schema.tables.items():
        blocked = set(settings.safety.blocked_columns.get(table, []))
        hashed = set(settings.safety.hashed_id_columns.get(table, []))
        lines.append(f"{table}: {spec.description}")
        for name, column in spec.columns.items():
            if name in blocked:
                continue
            note = " (anonymous customer code, STRING)" if name in hashed else ""
            lines.append(f"  - {name} {column.type}: {column.description}{note}")
    return "\n".join(lines)


def _run_one(sql: str, ctx: ToolContext) -> dict[str, object]:
    budget = ctx.budget
    if budget.queries_left <= 0:
        return {"sql": sql, "error": BUDGET_SPENT}
    budget.queries_left -= 1

    try:
        safe = make_safe(sql, ctx.scope, ctx.settings, ctx.id_salt)
        result = run_query(ctx.bigquery, safe, ctx.settings.bigquery)
    except QueryRejectedError as error:
        if not error.repairable:
            return {"sql": sql, "error": error.reason, "next_step": RULE_LIMIT}
        return _failure(sql, error.reason, FailureKind.REPAIR, ctx)
    except QueryFailedError as error:
        return _failure(sql, error.message, error.kind, ctx)

    entry: dict[str, object] = {"sql": sql, "row_count": result.total_rows, "rows": result.rows}
    if result.total_rows == 0:
        entry["note"] = NO_ROWS
    elif result.truncated:
        entry["note"] = f"Only the first {len(result.rows)} of {result.total_rows} rows are shown."
    return entry


def _failure(sql: str, message: str, kind: FailureKind, ctx: ToolContext) -> dict[str, object]:
    if kind is not FailureKind.STOP:
        if ctx.budget.repairs_left <= 0:
            return {"sql": sql, "error": message, "next_step": NO_REPAIRS}
        ctx.budget.repairs_left -= 1
    return {"sql": sql, "error": message, "next_step": NEXT_STEP[kind]}
