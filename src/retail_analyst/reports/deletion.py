"""Two-step deletion: store the exact list, then delete only that list once.

The model can start a deletion but never finish one. The delete runs from the
report IDs stored with the request, owned by the same user, before expiry and
only once. LangGraph may re-run a node after resume, so the used_at check makes
a repeated confirmation harmless.
"""

import datetime as dt
from dataclasses import dataclass

from psycopg import sql
from psycopg.rows import scalar_row

from retail_analyst.core.db import Pool


@dataclass(frozen=True)
class DeletePreview:
    request_id: str
    reports: list[tuple[int, str]]  # (id, title)


def find_and_hold(
    pool: Pool,
    owner_id: str,
    matching_text: str | None,
    conversation_id: str | None,
    report_ids: list[int] | None,
    minutes: int,
) -> DeletePreview | None:
    """Finds the owner's reports that meet every given filter and stores them as a pending request."""
    conditions: list[sql.Composable] = [sql.SQL("owner_id = %s")]
    params: list[object] = [owner_id]
    if report_ids:
        conditions.append(sql.SQL("id = any(%s)"))
        params.append(report_ids)
    if matching_text:
        conditions.append(sql.SQL("(search @@ websearch_to_tsquery('english', %s) or body_text ilike %s)"))
        params += [matching_text, f"%{matching_text}%"]
    if conversation_id:
        conditions.append(sql.SQL("conversation_id = %s"))
        params.append(conversation_id)
    query = sql.SQL("select id, title from reports where {} order by id").format(sql.SQL(" and ").join(conditions))

    with pool.connection() as conn:
        rows = conn.execute(query, params).fetchall()
        if not rows:
            return None
        reports = [(int(row["id"]), str(row["title"])) for row in rows]
        description = matching_text or ("reports from this conversation" if conversation_id else "reports by number")
        expires = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=minutes)
        with conn.cursor(row_factory=scalar_row) as cur:
            request_id = cur.execute(
                "insert into delete_requests (owner_id, report_ids, description, expires_at) "
                "values (%s, %s, %s, %s) returning id",
                (owner_id, [report_id for report_id, _ in reports], description, expires),
            ).fetchone()
    return DeletePreview(request_id=str(request_id), reports=reports)


def load_preview(pool: Pool, owner_id: str, request_id: str) -> DeletePreview | None:
    with pool.connection() as conn:
        row = conn.execute(
            "select report_ids from delete_requests where id = %s and owner_id = %s", (request_id, owner_id)
        ).fetchone()
        if row is None:
            return None
        titles = conn.execute(
            "select id, title from reports where id = any(%s) and owner_id = %s order by id",
            (row["report_ids"], owner_id),
        ).fetchall()
    return DeletePreview(request_id=request_id, reports=[(int(r["id"]), str(r["title"])) for r in titles])


def confirm(pool: Pool, owner_id: str, request_id: str) -> int | None:
    """Deletes the held reports. Returns the count, or None if the request is used, expired or not the owner's."""
    with pool.connection() as conn, conn.transaction():
        held = conn.execute(
            "update delete_requests set used_at = now() "
            "where id = %s and owner_id = %s and used_at is null and expires_at > now() returning report_ids",
            (request_id, owner_id),
        ).fetchone()
        if held is None:
            return None
        deleted = conn.execute(
            "delete from reports where id = any(%s) and owner_id = %s", (held["report_ids"], owner_id)
        ).rowcount
        conn.execute("update delete_requests set deleted_count = %s where id = %s", (deleted, request_id))
    return deleted


def cancel(pool: Pool, owner_id: str, request_id: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "update delete_requests set used_at = now(), deleted_count = 0 "
            "where id = %s and owner_id = %s and used_at is null",
            (request_id, owner_id),
        )
