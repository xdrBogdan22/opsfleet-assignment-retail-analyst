# Example run

Real sessions from 2026-11-08, copied from the terminal. They ran as separate
CLI sessions while the prototype was being built, so the sign-in line differs
between them. Every figure was checked afterwards with an independent BigQuery
query, and all matched to the cent.

## A brand manager asks about revenue

The denim manager sees only Diesel, True Religion, 7 For All Mankind and
Joe's Jeans.

```text
$ uv run --frozen retail-analyst --user denim_manager
Signed in as Alex (Denim). Commands: /new starts a new conversation, /quit exits.

you> What was revenue by brand last month?

analyst> True Religion led brand revenue last month with $7,365.91, followed closely by Diesel.

**Revenue by Brand (Last Month - October 2026):**
* **True Religion:** $7,365.91
* **Diesel:** $7,188.52
* **7 For All Mankind:** $6,933.14
* **Joe's Jeans:** $3,884.01

*Metric Definition:* Revenue is calculated as the sum of `sale_price` for order items, excluding items with a status of Cancelled or Returned.

you> Which of my brands grew the most compared with the month before?

analyst> 7 For All Mankind grew the most last month, increasing revenue by $2,384.29 (or 52.4%) compared to the month before.

**Revenue Growth by Brand (October 2026 vs. September 2026):**
* **7 For All Mankind:** +$2,384.29 (+52.4%) — from $4,548.85 to $6,933.14
* **Diesel:** +$270.47 (+3.9%) — from $6,918.05 to $7,188.52
* **True Religion:** +$226.66 (+3.2%) — from $7,139.25 to $7,365.91
* **Joe's Jeans:** +$87.89 (+2.3%) — from $3,796.12 to $3,884.01
```

Each answer took 2 model calls. The primary model was overloaded (HTTP 504),
so the fallback answered, and after the first failure the circuit breaker sent
the second question straight to the fallback.

## Personal data is not available

```text
you> List the emails of my top 3 customers

analyst> I can only answer questions about sales, customers and products, but please note that privacy rules and available data tables do not include customer names, emails, or addresses. Customer IDs are available as anonymous codes.
```

## A report, saved and opened

```text
you> Create a short report on October 2026 revenue by brand compared with September, with action items for November

analyst> October 2026 revenue across our brand portfolio reached $25,371.58, representing an increase over September 2026's $22,402.26, led by strong momentum in 7 For All Mankind.

Revenue is defined as the sum of order item sale prices, excluding items with Cancelled or Returned status.

I have saved the full report for you. You can open it using `/open 2`.
```

`/open 2` writes the HTML to a temporary file and opens it in the browser. The
report holds a summary, a bar chart, a table with September, October and
the change for each brand, and action items. The HTML is built by code from
the model's structured fields, with every string escaped.

## Deleting reports needs a confirmation

Two reports mentioning Acme Corp were saved first.

```text
you> Delete all reports mentioning Acme Corp

analyst> This will permanently delete 2 report(s):
  13: Acme Corp churn review
  14: Acme Corp Q3 pricing
Type yes to delete them. Anything else cancels: no

analyst> Cancelled. Nothing was deleted.

you> Delete all reports mentioning Acme Corp

analyst> This will permanently delete 2 report(s):
  13: Acme Corp churn review
  14: Acme Corp Q3 pricing
Type yes to delete them. Anything else cancels: yes

analyst> Deleted 2 reports.
```

Report 2, which does not mention Acme, was kept.

## The CEO sees every brand

```text
$ uv run --frozen retail-analyst --user ceo
Signed in as Dana (CEO). Commands: /open <id> opens a saved report, /new starts a new conversation, /quit exits.

you> What were the top 5 brands by revenue in 2025?

analyst> The top brand by revenue in 2025 was True Religion with $35,115.31.

Here are the top 5 brands by revenue for full-year 2025 (defined as the sum of `sale_price` for order items with status other than Cancelled or [removed]):

1. **True Religion**: $35,115.31
2. **Calvin Klein**: $33,671.59
3. **Diesel**: $29,084.17
4. **Carhartt**: $28,159.11
5. **7 For All Mankind**: $23,184.36
```

Brand names such as Calvin Klein pass the output guard because they came from
query results. This run also shows a bug the guard had: it removed the status
word "Returned" as a person's name, hence `[removed]`. A person finding now
needs at least two words, and a unit test pins the fix.

## Each turn leaves a log line

```text
$ uv run --frozen retail-analyst --user outdoor_manager
Signed in as Sam (Outdoor). Monitoring: local log only.
Commands: /open <id> opens a saved report, /good or /bad rates the last answer, /new starts a new conversation, /quit exits.

you> How many orders were returned in October 2026?

analyst> There were 39 orders returned in October 2026 (based on the order items created in October 2026 that have a status of Returned).

you> /good
Thanks, noted.
```

`retail_analyst.log`:

```json
{"event": "turn", "outcome": "answered", "trace_id": null, "model_calls": 2, "queries": 1, "sql_repairs": 0, "seconds": 6.0}
{"event": "feedback", "good": true, "trace_id": null}
```

With Langfuse keys in `.env`, `trace_id` links each line to the full trace.
