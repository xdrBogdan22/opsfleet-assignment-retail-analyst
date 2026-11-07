"""Loads the YAML files under config/ into typed, validated settings.

Each file becomes one section, listed in SECTION_FILES. An environment variable
named RETAIL_ANALYST__<SECTION>__<KEY> overrides a single top-level value, so an
operator can change a limit without editing files. Its value is parsed as YAML,
so numbers and lists keep their types.
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

CONFIG_DIR = Path(os.environ.get("RETAIL_ANALYST_CONFIG_DIR", Path(__file__).parents[3] / "config"))
ENV_PREFIX = "RETAIL_ANALYST__"

SECTION_FILES = {
    "limits": "agent/limits.yaml",
    "models": "agent/models.yaml",
    "bigquery": "data/bigquery.yaml",
    "dataset_schema": "data/schema.yaml",
    "safety": "data/safety.yaml",
    "seed": "seed/demo.yaml",
    "prompts": "prompts/agent.yaml",
    "tool_descriptions": "prompts/tools.yaml",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Limits(Strict):
    model_calls: int = Field(ge=1)
    sql_repairs: int = Field(ge=0)
    queries: int = Field(ge=1)
    empty_probes: int = Field(ge=0)
    question_seconds: int = Field(gt=0)
    report_seconds: int = Field(gt=0)
    cost_usd: float = Field(gt=0)


class ModelEntry(Strict):
    provider: str
    name: str
    enabled: bool


class Models(Strict):
    models: list[ModelEntry]
    temperature: float = Field(ge=0, le=2)
    attempts_per_model: int = Field(ge=1)
    call_timeout_seconds: int = Field(gt=0)

    @property
    def enabled(self) -> list[ModelEntry]:
        return [m for m in self.models if m.enabled]


class BigQuery(Strict):
    dataset: str
    tables: list[str]
    max_bytes_billed: int = Field(gt=0)
    query_timeout_seconds: int = Field(gt=0)
    max_rows: int = Field(gt=0)
    exclude_future_rows: bool


class Safety(Strict):
    blocked_columns: dict[str, list[str]]
    hashed_id_columns: dict[str, list[str]]
    demographic_columns: list[str]
    min_group_size: int = Field(ge=1)
    max_input_chars: int = Field(gt=0)


class Column(Strict):
    type: str
    description: str


class Table(Strict):
    description: str
    columns: dict[str, Column]


class DatasetSchema(Strict):
    tables: dict[str, Table]


class SeedUser(Strict):
    id: str
    name: str
    all_brands: bool = False
    brands: list[str] = []


class Persona(Strict):
    name: str
    instructions: str


class Seed(Strict):
    users: list[SeedUser]
    persona: Persona


class Prompts(Strict):
    system: str
    final_answer: str


class Settings(Strict):
    limits: Limits
    models: Models
    bigquery: BigQuery
    safety: Safety
    dataset_schema: DatasetSchema
    seed: Seed
    prompts: Prompts
    tool_descriptions: dict[str, str]


def _load_section(name: str) -> dict[str, object]:
    data = yaml.safe_load((CONFIG_DIR / SECTION_FILES[name]).read_text()) or {}
    prefix = f"{ENV_PREFIX}{name.upper()}__"
    for var, raw in os.environ.items():
        if var.startswith(prefix):
            data[var.removeprefix(prefix).lower()] = yaml.safe_load(raw)
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate({name: _load_section(name) for name in SECTION_FILES})
