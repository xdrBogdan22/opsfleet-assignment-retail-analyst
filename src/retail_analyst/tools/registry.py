"""The tools the model can call.

Adding a capability means writing a function, adding its description to
config/prompts/tools.yaml and listing it here. The model sees each function's
arguments and the YAML description; the injected ToolContext stays hidden.
"""

from collections.abc import Callable

from langchain_core.tools import BaseTool, StructuredTool

from retail_analyst.core.config import Settings
from retail_analyst.tools.data import describe_schema, run_sql
from retail_analyst.tools.reports import request_delete, save_report

FUNCTIONS: dict[str, Callable[..., str]] = {
    "run_sql": run_sql,
    "describe_schema": describe_schema,
    "save_report": save_report,
    "request_delete": request_delete,
}


def build_tools(settings: Settings) -> list[BaseTool]:
    return [
        StructuredTool.from_function(func, name=name, description=settings.tool_descriptions[name])
        for name, func in FUNCTIONS.items()
    ]
