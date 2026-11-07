"""Saves and reads reports in Postgres. Every read is limited to the owner."""

import datetime as dt

from psycopg.rows import scalar_row

from retail_analyst.core.db import Pool
from retail_analyst.reports.model import Report
from retail_analyst.reports.render import render_html, render_text


def save_report(pool: Pool, owner_id: str, author: str, conversation_id: str, report: Report) -> int:
    html = render_html(report, author=author, created=dt.datetime.now(dt.UTC))
    with pool.connection() as conn, conn.cursor(row_factory=scalar_row) as cur:
        report_id = cur.execute(
            "insert into reports (owner_id, conversation_id, title, body_text, body_html) "
            "values (%s, %s, %s, %s, %s) returning id",
            (owner_id, conversation_id, report.title, render_text(report), html),
        ).fetchone()
    assert report_id is not None
    return int(report_id)


def load_report_html(pool: Pool, owner_id: str, report_id: int) -> str | None:
    with pool.connection() as conn, conn.cursor(row_factory=scalar_row) as cur:
        html = cur.execute(
            "select body_html from reports where id = %s and owner_id = %s", (report_id, owner_id)
        ).fetchone()
    return None if html is None else str(html)
