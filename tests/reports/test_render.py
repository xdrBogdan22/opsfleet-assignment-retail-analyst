import datetime as dt

from retail_analyst.reports.model import BarChart, Report, Section, Table
from retail_analyst.reports.render import bar_chart_svg, render_html, render_text

CHART = BarChart(title="Revenue by brand", labels=["Diesel", "Joe's <b>Jeans</b>"], values=[7188.52, 3884.01])
REPORT = Report(
    title="Q3 <script>alert(1)</script> review",
    summary="Diesel leads.",
    sections=[
        Section(
            heading="Revenue",
            paragraphs=["Diesel grew 4%."],
            chart=CHART,
            table=Table(columns=["Brand", "Revenue"], rows=[["Diesel", 7188.52]]),
        )
    ],
    action_items=["Restock Diesel jeans"],
)


def test_model_text_is_escaped() -> None:
    html = render_html(REPORT, author="Alex", created=dt.datetime(2026, 11, 8, tzinfo=dt.UTC))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_chart_has_one_bar_per_value_and_labels_only_the_largest() -> None:
    svg = str(bar_chart_svg(CHART))
    assert svg.count('class="bar"') == 2
    assert svg.count('class="value"') == 1
    assert "<b>" not in svg
    assert "<title>Diesel: 7,189</title>" in svg


def test_plain_text_keeps_the_content() -> None:
    text = render_text(REPORT)
    assert "Restock Diesel jeans" in text
    assert "Diesel | 7188.52" in text
