"""Report storage on the local Postgres. Skipped without DATABASE_URL."""

import os

import pytest
from dotenv import load_dotenv

from retail_analyst.core.db import open_pool
from retail_analyst.reports.model import Report, Section
from retail_analyst.reports.store import load_report_html, save_report

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"),
]

REPORT = Report(title="Test report", summary="Summary.", sections=[Section(heading="One", paragraphs=["Text."])])


def test_report_is_stored_and_visible_only_to_its_owner() -> None:
    with open_pool(os.environ["DATABASE_URL"]) as pool:
        report_id = save_report(pool, "denim_manager", "Alex", "test-conversation", REPORT)
        try:
            html = load_report_html(pool, "denim_manager", report_id)
            assert html is not None
            assert "Test report" in html
            assert load_report_html(pool, "outdoor_manager", report_id) is None
        finally:
            with pool.connection() as conn:
                conn.execute("delete from reports where id = %s", (report_id,))
