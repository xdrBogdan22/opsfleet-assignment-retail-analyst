"""Everything the graph needs for one signed-in user, built once per CLI session."""

from collections.abc import Callable
from dataclasses import dataclass

import psycopg
from google.cloud import bigquery
from langchain_core.tools import BaseTool
from psycopg.rows import DictRow

from retail_analyst.core.config import Settings
from retail_analyst.core.db import Pool
from retail_analyst.llm.models import ChatModel, build_breakers, build_chat_model
from retail_analyst.safety.sql_guard import Scope
from retail_analyst.tools.registry import build_tools


@dataclass(frozen=True)
class User:
    id: str
    name: str
    brands: tuple[str, ...] | None  # None means every brand

    @property
    def scope(self) -> Scope:
        return Scope(user_id=self.id, brands=self.brands)


@dataclass(frozen=True)
class Session:
    user: User
    persona: Callable[[], str]  # read on every turn, so a new tone applies at once
    settings: Settings
    bigquery: bigquery.Client
    db: Pool
    id_salt: str
    tools: dict[str, BaseTool]
    model_with_tools: ChatModel
    model_without_tools: ChatModel


class UnknownUserError(Exception):
    pass


def load_user(conn: psycopg.Connection[DictRow], user_id: str) -> User:
    row = conn.execute("select name, all_brands from app_users where id = %s", (user_id,)).fetchone()
    if row is None:
        raise UnknownUserError(user_id)
    if row["all_brands"]:
        return User(id=user_id, name=row["name"], brands=None)
    rows = conn.execute("select brand from user_brands where user_id = %s order by brand", (user_id,)).fetchall()
    return User(id=user_id, name=row["name"], brands=tuple(r["brand"] for r in rows))


def load_persona(conn: psycopg.Connection[DictRow]) -> str:
    row = conn.execute("select instructions from personas where active").fetchone()
    return str(row["instructions"]) if row else ""


def build_session(
    pool: Pool, user_id: str, settings: Settings, bigquery_client: bigquery.Client, id_salt: str
) -> Session:
    tools = build_tools(settings)
    breakers = build_breakers(settings.models)
    with pool.connection() as conn:
        user = load_user(conn, user_id)

    def persona() -> str:
        with pool.connection() as conn:
            return load_persona(conn)

    return Session(
        user=user,
        persona=persona,
        settings=settings,
        bigquery=bigquery_client,
        db=pool,
        id_salt=id_salt,
        tools={tool.name: tool for tool in tools},
        model_with_tools=build_chat_model(settings.models, tools, breakers),
        model_without_tools=build_chat_model(settings.models, [], breakers),
    )
