"""Runs a guarded query on BigQuery within the byte, time and row limits.

Every query gets a free dry run first, so a query that is too large fails
before it costs anything. Failures come back as QueryFailedError with a kind
the agent can act on: repair the SQL, narrow the query, or stop.

The BigQuery client already retries rateLimitExceeded, backendError,
internalError and badGateway, but for up to 10 minutes by default. Both retry
deadlines are cut to the query timeout so one query cannot outlive the
question's time budget.
"""

import datetime as dt
import decimal
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from google.api_core import exceptions as gexc
from google.cloud import bigquery
from google.cloud.bigquery.retry import DEFAULT_JOB_RETRY, DEFAULT_RETRY

from retail_analyst.core.config import BigQuery as BigQuerySettings
from retail_analyst.safety.sql_guard import SafeQuery


class FailureKind(StrEnum):
    REPAIR = "repair"  # the SQL is wrong; the model may fix it
    NARROW = "narrow"  # too large or too slow; the model may ask for less
    STOP = "stop"  # quota, access or outage; retrying will not help


class QueryFailedError(Exception):
    def __init__(self, message: str, kind: FailureKind):
        super().__init__(message)
        self.message = message
        self.kind = kind


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, object]]
    total_rows: int
    bytes_processed: int

    @property
    def truncated(self) -> bool:
        return self.total_rows > len(self.rows)


def run_query(client: bigquery.Client, query: SafeQuery, settings: BigQuerySettings) -> QueryResult:
    params = _parameters(query.params)
    timeout = settings.query_timeout_seconds

    try:
        estimate = (
            client.query(
                query.sql,
                job_config=bigquery.QueryJobConfig(
                    query_parameters=params, dry_run=True, use_query_cache=False
                ),
                retry=DEFAULT_RETRY.with_timeout(timeout),
            ).total_bytes_processed
            or 0
        )
        if estimate > settings.max_bytes_billed:
            raise QueryFailedError(
                f"The query would scan {estimate:,} bytes, above the limit of "
                f"{settings.max_bytes_billed:,}. Filter by date or select fewer columns.",
                FailureKind.NARROW,
            )

        job = client.query(
            query.sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=params,
                maximum_bytes_billed=settings.max_bytes_billed,
                job_timeout_ms=timeout * 1000,
            ),
            retry=DEFAULT_RETRY.with_timeout(timeout),
            job_retry=DEFAULT_JOB_RETRY.with_timeout(timeout),
        )
        rows = job.result(max_results=settings.max_rows, timeout=timeout)
        return QueryResult(
            rows=[{key: _plain(value) for key, value in row.items()} for row in rows],
            total_rows=rows.total_rows or 0,
            bytes_processed=job.total_bytes_processed or 0,
        )
    except gexc.GoogleAPICallError as error:
        raise _classify(error) from error
    except (TimeoutError, gexc.RetryError) as error:
        raise QueryFailedError(
            f"The query did not finish within {timeout} seconds. Ask for less data.", FailureKind.NARROW
        ) from error


def _parameters(
    values: Mapping[str, str | list[str]],
) -> list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]:
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = []
    for name, value in values.items():
        if isinstance(value, list):
            params.append(bigquery.ArrayQueryParameter(name, "STRING", value))
        else:
            params.append(bigquery.ScalarQueryParameter(name, "STRING", value))
    return params


def _classify(error: gexc.GoogleAPICallError) -> QueryFailedError:
    """Maps BigQuery errors to an action, following the table in P10.

    https://docs.cloud.google.com/bigquery/docs/error-messages
    """
    reasons = {str(item.get("reason", "")) for item in error.errors or [] if isinstance(item, dict)}
    message = _first_line(error.message or str(error))

    if "bytesBilledLimitExceeded" in reasons or "responseTooLarge" in reasons:
        return QueryFailedError(f"The query is too large: {message}", FailureKind.NARROW)
    sql_error = isinstance(error, (gexc.BadRequest, gexc.NotFound))
    if sql_error or reasons & {"invalidQuery", "invalid", "notFound"}:
        return QueryFailedError(f"BigQuery rejected the SQL: {message}", FailureKind.REPAIR)
    if reasons & {"quotaExceeded", "accessDenied"} or isinstance(error, gexc.Forbidden):
        return QueryFailedError(f"BigQuery refused the request: {message}", FailureKind.STOP)
    return QueryFailedError(f"BigQuery is unavailable: {message}", FailureKind.STOP)


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0][:300] if text.strip() else "no details"


def _plain(value: object) -> object:
    """Makes a cell JSON-safe for the model and the traces."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value
