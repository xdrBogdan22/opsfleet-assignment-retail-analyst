import pytest

from retail_analyst.core.config import get_settings
from retail_analyst.safety.sql_guard import QueryRejectedError, SafeQuery, Scope, make_safe

SETTINGS = get_settings()
DENIM = Scope(user_id="denim_manager", brands=("Diesel", "Joe's Jeans"))
CEO = Scope(user_id="ceo", brands=None)


def safe(sql: str, scope: Scope = DENIM) -> SafeQuery:
    return make_safe(sql, scope, SETTINGS, id_salt="test-salt")


def rejected(sql: str, scope: Scope = DENIM) -> QueryRejectedError:
    with pytest.raises(QueryRejectedError) as error:
        safe(sql, scope)
    return error.value


def test_scopes_every_table_to_the_managers_brands() -> None:
    query = safe(
        "SELECT p.brand, SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY 1"
    )
    assert query.sql.count("IN UNNEST(@allowed_brands)") == 2
    assert query.params["allowed_brands"] == ["Diesel", "Joe's Jeans"]
    assert "Joe" not in query.sql


def test_ceo_has_no_brand_filter_but_keeps_privacy_rules() -> None:
    query = safe("SELECT * FROM users", CEO)
    assert "allowed_brands" not in query.params
    assert "email" not in query.sql
    assert "TO_HEX(SHA256(CONCAT(@id_salt, CAST(id AS STRING)))) AS id" in query.sql


def test_star_exposes_only_allowed_columns() -> None:
    query = safe("SELECT * FROM users")
    for column in SETTINGS.safety.blocked_columns["users"]:
        assert column not in query.sql


def test_qualified_table_names_are_accepted() -> None:
    query = safe("SELECT COUNT(*) FROM `bigquery-public-data.thelook_ecommerce.orders`")
    assert "num_of_item" not in query.sql


def test_future_rows_are_excluded() -> None:
    assert "created_at <= CURRENT_TIMESTAMP()" in safe("SELECT COUNT(*) FROM orders").sql


def test_cte_names_are_not_treated_as_tables() -> None:
    query = safe("WITH recent AS (SELECT * FROM orders) SELECT status, COUNT(*) FROM recent GROUP BY 1")
    assert query.sql.count("thelook_ecommerce.orders") == 1


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT email FROM users",
        "SELECT u.first_name AS customer FROM users u",
        "SELECT COUNT(DISTINCT street_address) FROM users",
        "SELECT SUM(num_of_item) FROM orders",
    ],
)
def test_blocked_columns_are_rejected(sql: str) -> None:
    error = rejected(sql)
    assert not error.repairable


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders WHERE TRUE",
        "DROP TABLE users",
        "INSERT INTO orders (order_id) VALUES (1)",
        "UPDATE products SET brand = 'x' WHERE TRUE",
        "CREATE TABLE x AS SELECT 1",
    ],
)
def test_writes_are_rejected(sql: str) -> None:
    assert not rejected(sql).repairable


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM `other-project.dataset.secrets`",
        "SELECT * FROM thelook_ecommerce.events",
        "SELECT * FROM `region-us`.INFORMATION_SCHEMA.JOBS",
        "SELECT * FROM ML.PREDICT(MODEL m, (SELECT 1))",
        "SELECT * FROM EXTERNAL_QUERY('conn', 'select 1')",
    ],
)
def test_other_tables_and_table_functions_are_rejected(sql: str) -> None:
    assert not rejected(sql).repairable


def test_syntax_errors_are_repairable() -> None:
    assert rejected("SELEC brand FROM products").repairable


def test_multiple_statements_are_repairable() -> None:
    assert rejected("SELECT 1 FROM products; SELECT 2 FROM products").repairable


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT user_id, age FROM order_items oi JOIN users u ON u.id = oi.user_id",
        "SELECT u.id, u.city FROM users u",
        "SELECT id, gender FROM users",
    ],
)
def test_customer_id_with_raw_demographics_is_rejected(sql: str) -> None:
    assert not rejected(sql).repairable


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT user_id, SUM(sale_price) FROM order_items GROUP BY 1",
        "SELECT state, COUNT(DISTINCT user_id) FROM order_items oi JOIN users u ON u.id = oi.user_id GROUP BY 1",
        "SELECT u.id, AVG(u.age) FROM users u GROUP BY 1",
    ],
)
def test_aggregated_or_separate_demographics_are_allowed(sql: str) -> None:
    safe(sql)
