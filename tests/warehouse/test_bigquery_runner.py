import datetime as dt
import decimal

import pytest
from google.api_core import exceptions as gexc

from retail_analyst.warehouse.bigquery_runner import FailureKind, _classify, _plain


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (gexc.BadRequest("Unrecognized name: foo", errors=[{"reason": "invalidQuery"}]), FailureKind.REPAIR),
        (gexc.NotFound("Table not found", errors=[{"reason": "notFound"}]), FailureKind.REPAIR),
        (gexc.BadRequest("limit", errors=[{"reason": "bytesBilledLimitExceeded"}]), FailureKind.NARROW),
        (gexc.Forbidden("quota", errors=[{"reason": "quotaExceeded"}]), FailureKind.STOP),
        (gexc.Forbidden("denied", errors=[{"reason": "accessDenied"}]), FailureKind.STOP),
        (gexc.ServiceUnavailable("down", errors=[{"reason": "backendError"}]), FailureKind.STOP),
    ],
)
def test_errors_map_to_actions(error: gexc.GoogleAPICallError, kind: FailureKind) -> None:
    assert _classify(error).kind is kind


def test_cells_become_json_safe() -> None:
    assert _plain(decimal.Decimal("1.5")) == 1.5
    assert _plain(dt.datetime(2026, 1, 2, tzinfo=dt.UTC)) == "2026-01-02T00:00:00+00:00"
    assert _plain("x") == "x"
