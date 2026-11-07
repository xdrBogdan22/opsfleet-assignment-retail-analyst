"""The ask_clarification tool. The graph pauses on it and returns the user's answer."""

import json
from typing import Annotated

from langchain_core.tools import InjectedToolArg
from pydantic import Field

from retail_analyst.tools.context import ToolContext


def ask_clarification(
    question: Annotated[str, Field(max_length=300)],
    options: Annotated[list[str], Field(min_length=2, max_length=4, description="Short answer options")],
    ctx: Annotated[ToolContext, InjectedToolArg],
) -> str:
    return json.dumps({"question": question, "options": options})
