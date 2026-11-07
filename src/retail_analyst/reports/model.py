"""The structure the model fills when it saves a report.

The model writes data and text only. Code renders the HTML, so model output
can never inject markup or scripts into a report.
"""

from pydantic import BaseModel, Field


class Table(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=8)
    rows: list[list[str | float | int | None]] = Field(max_length=50)


class BarChart(BaseModel):
    """One series: one value per label. Compare periods in a table instead."""

    title: str = Field(description="What the bars measure, for example 'Revenue by brand, October 2026 (USD)'")
    labels: list[str] = Field(min_length=1, max_length=15)
    values: list[float] = Field(min_length=1, max_length=15)


class Section(BaseModel):
    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    table: Table | None = None
    chart: BarChart | None = None


class Report(BaseModel):
    title: str = Field(max_length=200)
    summary: str = Field(description="One paragraph with the main finding")
    sections: list[Section] = Field(min_length=1, max_length=10)
    action_items: list[str] = Field(default_factory=list, max_length=10)
