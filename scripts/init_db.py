"""Creates the application tables and demo data in the database at DATABASE_URL.

Safe to run more than once. Run with:

    uv run --frozen python scripts/init_db.py
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from retail_analyst.core.config import get_settings

SCHEMA = Path(__file__).parents[1] / "db" / "schema.sql"


def seed(conn: psycopg.Connection) -> None:
    settings = get_settings().seed
    for user in settings.users:
        conn.execute(
            "insert into app_users (id, name, all_brands) values (%s, %s, %s) "
            "on conflict (id) do update set name = excluded.name, all_brands = excluded.all_brands",
            (user.id, user.name, user.all_brands),
        )
        conn.execute("delete from user_brands where user_id = %s", (user.id,))
        for brand in user.brands:
            conn.execute("insert into user_brands (user_id, brand) values (%s, %s)", (user.id, brand))

    persona = settings.persona
    has_persona = conn.execute("select 1 from personas where name = %s", (persona.name,)).fetchone()
    if not has_persona:
        conn.execute(
            "insert into personas (name, version, instructions, active) values (%s, 1, %s, true)",
            (persona.name, persona.instructions),
        )


def main() -> int:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    with psycopg.connect(url) as conn:
        conn.execute(SCHEMA.read_bytes())
        seed(conn)
    # setup() runs its own migrations and needs autocommit.
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as conn:
        PostgresSaver(conn).setup()

    with psycopg.connect(url) as conn:
        (users,) = conn.execute("select count(*) from app_users").fetchone() or (0,)
        (brands,) = conn.execute("select count(*) from user_brands").fetchone() or (0,)
    print(f"Database ready: {users} users, {brands} brand assignments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
