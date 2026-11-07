"""What a tool receives besides the model's arguments.

The context is injected by the agent, never written by the model, so a tool
always knows the real user and the real budget.
"""

from dataclasses import dataclass

from google.cloud import bigquery

from retail_analyst.core.config import Settings
from retail_analyst.safety.sql_guard import Scope


@dataclass
class Budget:
    """What is left for the current question. Tools spend it; the agent resets it."""

    queries_left: int
    repairs_left: int

    @classmethod
    def for_question(cls, settings: Settings) -> "Budget":
        return cls(queries_left=settings.limits.queries, repairs_left=settings.limits.sql_repairs)


@dataclass
class ToolContext:
    scope: Scope
    settings: Settings
    bigquery: bigquery.Client
    id_salt: str
    budget: Budget
