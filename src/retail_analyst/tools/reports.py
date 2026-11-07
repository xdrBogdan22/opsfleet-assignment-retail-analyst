"""The save_report tool."""

import json
from typing import Annotated

from langchain_core.tools import InjectedToolArg
from pydantic import Field

from retail_analyst.reports.model import Report, Section
from retail_analyst.reports.store import save_report as store_report
from retail_analyst.tools.context import ToolContext


def save_report(
    title: Annotated[str, Field(max_length=200)],
    summary: Annotated[str, Field(description="One paragraph with the main finding")],
    sections: Annotated[list[Section], Field(min_length=1, max_length=10)],
    action_items: Annotated[list[str], Field(max_length=10)],
    ctx: Annotated[ToolContext, InjectedToolArg],
) -> str:
    report = Report(title=title, summary=summary, sections=sections, action_items=action_items)
    report_id = store_report(ctx.db, ctx.scope.user_id, ctx.author, ctx.conversation_id, report)
    return json.dumps({"report_id": report_id, "message": f"Saved. The user can open it with /open {report_id}."})
