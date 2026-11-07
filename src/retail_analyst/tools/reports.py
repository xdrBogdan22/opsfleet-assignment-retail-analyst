"""The report tools: save_report and request_delete."""

import json
from typing import Annotated

from langchain_core.tools import InjectedToolArg
from pydantic import Field

from retail_analyst.reports.deletion import find_and_hold
from retail_analyst.reports.model import Report, Section
from retail_analyst.reports.store import save_report as store_report
from retail_analyst.tools.context import ToolContext

DELETE_REQUEST = "delete_request_id"


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


def request_delete(
    ctx: Annotated[ToolContext, InjectedToolArg],
    matching_text: Annotated[str | None, Field(description="Text the reports must mention, such as a client")] = None,
    this_conversation: Annotated[bool, Field(description="Only reports made in this conversation")] = False,
) -> str:
    if not matching_text and not this_conversation:
        return json.dumps({"error": "Give matching_text, or set this_conversation to true."})
    conversation = ctx.conversation_id if this_conversation else None
    minutes = ctx.settings.safety.delete_confirmation_minutes
    preview = find_and_hold(ctx.db, ctx.scope.user_id, matching_text, conversation, minutes)
    if preview is None:
        return json.dumps({"matches": 0, "message": "No saved reports match. Tell the user nothing was deleted."})
    return json.dumps({DELETE_REQUEST: preview.request_id, "matches": len(preview.reports)})
