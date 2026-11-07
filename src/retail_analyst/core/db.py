"""The Postgres connection pool shared by the app and the LangGraph checkpointer."""

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

Pool = ConnectionPool[psycopg.Connection[DictRow]]


def open_pool(url: str) -> Pool:
    # The checkpointer needs autocommit and dict rows; prepare_threshold=0 avoids
    # prepared statements that break behind connection poolers such as PgBouncer.
    return ConnectionPool(
        url,
        connection_class=psycopg.Connection[DictRow],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
