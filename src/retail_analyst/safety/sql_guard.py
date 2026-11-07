"""Turns model-written SQL into SQL that is safe to send to BigQuery.

The model never queries the raw tables. Every table reference is replaced by a
subquery that exposes only allowed columns, hashes customer IDs and keeps only
rows inside the user's brand scope. A blocked column therefore does not exist
from the query's point of view, whatever aliases or CTEs the model uses.

Brand names and the hashing salt travel as query parameters, never as text in
the SQL.
"""

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from retail_analyst.core.config import Settings

CUSTOMER_ID = "user_id"


@dataclass(frozen=True)
class Scope:
    """Who is asking. brands=None means every brand (the CEO)."""

    user_id: str
    brands: tuple[str, ...] | None


@dataclass(frozen=True)
class SafeQuery:
    sql: str
    params: dict[str, str | list[str]] = field(default_factory=dict)


class QueryRejectedError(Exception):
    """The query will not run.

    repairable=True means the model made a mistake it can fix, such as a syntax
    error. repairable=False means the request breaks a data rule; the agent
    must explain that to the user instead of trying again.
    """

    def __init__(self, reason: str, repairable: bool):
        super().__init__(reason)
        self.reason = reason
        self.repairable = repairable


def make_safe(sql: str, scope: Scope, settings: Settings, id_salt: str) -> SafeQuery:
    statement = _parse_single(sql)
    _check_read_only(statement)
    tables = _base_tables(statement, settings)
    _check_blocked_columns(statement, settings)
    _check_demographics_with_customer_id(statement, settings)

    for table in tables:
        table.replace(_scoped_view(table, scope, settings))

    params: dict[str, str | list[str]] = {"id_salt": id_salt}
    if scope.brands is not None:
        params["allowed_brands"] = list(scope.brands)
    return SafeQuery(sql=statement.sql(dialect="bigquery"), params=params)


def _parse_single(sql: str) -> exp.Expr:
    try:
        statements = [s for s in sqlglot.parse(sql, read="bigquery") if s is not None]
    except ParseError as error:
        raise QueryRejectedError(f"SQL syntax error: {error}", repairable=True) from error
    if len(statements) != 1:
        raise QueryRejectedError("Send exactly one SQL statement.", repairable=True)
    return statements[0]


def _check_read_only(statement: exp.Expr) -> None:
    if not isinstance(statement, exp.Query):
        raise QueryRejectedError("Only SELECT queries are allowed.", repairable=False)
    for node in statement.walk():
        if isinstance(node, (exp.DML, exp.DDL, exp.Command)):
            raise QueryRejectedError("Only SELECT queries are allowed.", repairable=False)


def _base_tables(statement: exp.Expr, settings: Settings) -> list[exp.Table]:
    """Returns references to the dataset's tables, skipping CTE names."""
    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    project, dataset = settings.bigquery.dataset.split(".")
    allowed = set(settings.bigquery.tables)

    tables = []
    for table in statement.find_all(exp.Table):
        # Table functions such as ML.PREDICT or EXTERNAL_QUERY reach outside the dataset.
        if not isinstance(table.this, exp.Identifier):
            raise QueryRejectedError("Table functions are not allowed.", repairable=False)
        name = table.name.lower()
        if not table.db and name in cte_names:
            continue
        if name not in allowed or table.db not in ("", dataset) or table.catalog not in ("", project):
            available = ", ".join(sorted(allowed))
            raise QueryRejectedError(
                f"Table {table.sql(dialect='bigquery')} is not available. Use only: {available}.",
                repairable=False,
            )
        tables.append(table)
    return tables


def _check_blocked_columns(statement: exp.Expr, settings: Settings) -> None:
    blocked = {col for cols in settings.safety.blocked_columns.values() for col in cols}
    for column in statement.find_all(exp.Column):
        if column.name.lower() in blocked:
            raise QueryRejectedError(
                f"Column {column.name} holds personal or out-of-scope data and is not available.",
                repairable=False,
            )


def _check_demographics_with_customer_id(statement: exp.Expr, settings: Settings) -> None:
    """Rejects a SELECT that returns a customer ID next to a raw demographic value.

    A hashed ID next to age, city and gender could still single out a person,
    so demographics must be aggregated when customer IDs are selected.
    """
    demographics = set(settings.safety.demographic_columns)
    for select in statement.find_all(exp.Select):
        aliases = _source_tables(select)
        has_id = has_demographic = False
        for projection in select.expressions:
            for column in projection.find_all(exp.Column):
                if isinstance(column.find_ancestor(exp.AggFunc, exp.Select), exp.AggFunc):
                    continue
                name = column.name.lower()
                source = aliases.get(column.table.lower()) if column.table else _single(aliases)
                if name == CUSTOMER_ID or (name == "id" and source == "users"):
                    has_id = True
                if name in demographics:
                    has_demographic = True
        if has_id and has_demographic:
            raise QueryRejectedError(
                "Customer IDs cannot appear next to raw age, gender or location. "
                "Aggregate the demographic columns or drop the customer ID.",
                repairable=False,
            )


def _source_tables(select: exp.Select) -> dict[str, str]:
    """Maps each alias in this SELECT's FROM and JOIN clauses to its table name."""
    sources: dict[str, str] = {}
    from_ = select.args.get("from_")
    nodes = [from_.this] if from_ else []
    nodes += [join.this for join in select.args.get("joins") or []]
    for node in nodes:
        if isinstance(node, exp.Table):
            sources[node.alias_or_name.lower()] = node.name.lower()
    return sources


def _single(aliases: dict[str, str]) -> str | None:
    return next(iter(aliases.values())) if len(aliases) == 1 else None


def _scoped_view(table: exp.Table, scope: Scope, settings: Settings) -> exp.Subquery:
    name = table.name.lower()
    source = f"`{settings.bigquery.dataset}.{name}`"
    blocked = set(settings.safety.blocked_columns.get(name, []))
    hashed = set(settings.safety.hashed_id_columns.get(name, []))

    columns = []
    for column in settings.dataset_schema.tables[name].columns:
        if column in blocked:
            continue
        if column in hashed:
            columns.append(f"TO_HEX(SHA256(CONCAT(@id_salt, CAST({column} AS STRING)))) AS {column}")
        else:
            columns.append(column)

    filters = _scope_filters(name, scope, settings)
    where = f" WHERE {' AND '.join(filters)}" if filters else ""
    inner = sqlglot.parse_one(f"SELECT {', '.join(columns)} FROM {source}{where}", read="bigquery")
    return exp.Subquery(this=inner, alias=exp.TableAlias(this=exp.to_identifier(table.alias_or_name)))


def _scope_filters(name: str, scope: Scope, settings: Settings) -> list[str]:
    dataset = settings.bigquery.dataset
    filters = []
    if scope.brands is not None:
        products = f"SELECT id FROM `{dataset}.products` WHERE brand IN UNNEST(@allowed_brands)"
        items = f"SELECT {{col}} FROM `{dataset}.order_items` WHERE product_id IN ({products})"
        filters.append(
            {
                "products": "brand IN UNNEST(@allowed_brands)",
                "order_items": f"product_id IN ({products})",
                "orders": f"order_id IN ({items.format(col='order_id')})",
                "users": f"id IN ({items.format(col='user_id')})",
            }[name]
        )
    if settings.bigquery.exclude_future_rows and "created_at" in settings.dataset_schema.tables[name].columns:
        filters.append("created_at <= CURRENT_TIMESTAMP()")
    return filters
