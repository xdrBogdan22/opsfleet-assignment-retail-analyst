"""Fills the system prompt template from config/prompts/agent.yaml."""

import datetime as dt

from retail_analyst.agent.session import Session
from retail_analyst.tools.data import schema_card


def system_prompt(session: Session, today: dt.date | None = None) -> str:
    settings = session.settings
    brands = session.user.brands
    if brands is None:
        scope = "They can see data for every brand."
    else:
        scope = f"They can see data only for these brands: {', '.join(brands)}."
    return settings.prompts.system.format(
        today=(today or dt.datetime.now(dt.UTC).date()).isoformat(),
        user_name=session.user.name,
        scope_sentence=scope,
        model_calls=settings.limits.model_calls,
        queries=settings.limits.queries,
        dataset=settings.bigquery.dataset,
        schema_card=schema_card(settings),
        persona=session.persona,
        preferences="",
    )
