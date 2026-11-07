"""Renders a Report to self-contained HTML and to plain text.

Jinja autoescaping covers every string from the model. Charts are static SVG
built here, with no JavaScript, so a report opens offline and prints cleanly.
Chart rules follow the dataviz guidance: one hue for one series, bars at most
24px thick with a 4px rounded end, only the largest value labeled, a tooltip
on every bar and the data available as a table.
"""

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from retail_analyst.reports.model import BarChart, Report, Table

TEMPLATES = Path(__file__).parent / "templates"
ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))

WIDTH, LABEL_WIDTH, ROW, BAR, RADIUS = 640, 170, 30, 18, 4


def render_html(report: Report, author: str, created: dt.datetime) -> str:
    return ENV.get_template("report.html.j2").render(
        report=report, author=author, created=created.strftime("%d %B %Y"), bar_chart=bar_chart_svg
    )


def render_text(report: Report) -> str:
    lines = [report.title, "", report.summary, ""]
    for section in report.sections:
        lines += [section.heading, *section.paragraphs]
        if section.table:
            lines.append(" | ".join(section.table.columns))
            lines += [" | ".join("" if cell is None else str(cell) for cell in row) for row in section.table.rows]
        lines.append("")
    if report.action_items:
        lines += ["Action items", *(f"- {item}" for item in report.action_items)]
    return "\n".join(lines).strip()


def bar_chart_svg(chart: BarChart) -> Markup:
    pairs = list(zip(chart.labels, chart.values, strict=False))
    peak = max((value for _, value in pairs), default=0) or 1
    plot = WIDTH - LABEL_WIDTH - 80
    height = ROW * len(pairs) + 8
    top = max(range(len(pairs)), key=lambda i: pairs[i][1])

    parts = [
        f'<svg class="chart" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(chart.title)}">',
        f'<line class="axis" x1="{LABEL_WIDTH}" y1="0" x2="{LABEL_WIDTH}" y2="{height}"/>',
    ]
    for i, (label, value) in enumerate(pairs):
        y = i * ROW + (ROW - BAR) / 2
        length = max(plot * max(value, 0) / peak, 0)
        parts.append(f'<text class="label" x="{LABEL_WIDTH - 8}" y="{y + BAR / 2}">{escape(label)}</text>')
        parts.append(f'<path class="bar" d="{_bar_path(LABEL_WIDTH, y, length)}">')
        parts.append(f"<title>{escape(label)}: {_number(value)}</title></path>")
        if i == top:
            x = LABEL_WIDTH + length + 6
            parts.append(f'<text class="value" x="{x}" y="{y + BAR / 2}">{_number(value)}</text>')
    parts.append("</svg>")
    return Markup("".join(parts))


def _cell(value: str | float | None) -> str:
    if value is None:
        return ""
    return _number(value) if isinstance(value, int | float) else value


def _numeric_column(index: int, table: Table) -> bool:
    return any(index < len(row) and isinstance(row[index], int | float) for row in table.rows)


ENV.filters["zip"] = zip
ENV.filters["cell"] = _cell
ENV.tests["numeric_column"] = _numeric_column


def _bar_path(x: float, y: float, length: float) -> str:
    """A bar square at the baseline with a rounded data end."""
    r = min(RADIUS, length / 2)
    return (
        f"M{x},{y} H{x + length - r} Q{x + length},{y} {x + length},{y + r} "
        f"V{y + BAR - r} Q{x + length},{y + BAR} {x + length - r},{y + BAR} H{x} Z"
    )


def _number(value: float) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.2f}"
