# Known limitations

Problems found in live runs that are not fixed yet, each with what we saw and
the options to fix it. When one is fixed, move it to the progress log.

## 1. The output guard removes harmless table headers

**Seen on 2026-11-08.** In a run of the brief's example questions, the output
guard replaced 7 table headers and section titles with `[removed]`, among them
"Core Metric Comparison", "Oct Active Base", "Gross Profit" and "Items Sold".
The answers were otherwise correct.

**Cause.** Presidio finds person names with the small spaCy model. A short
phrase of capitalized words with no sentence around it, which is what a header
is, looks like a name to that model. The guard is set to prefer a false alarm
over a miss: the score threshold is 0.3, and the only filter is that a name
needs at least two words (`config/data/safety.yaml`).

**Why it is not urgent.** Names cannot reach the model from the data, because
the SQL guard never exposes name, email or address columns. A name can only
come from the user's own message or from the model inventing one. The output
guard is the last check, not the main one.

**Options.**

| Option | Effect | Cost or risk |
|---|---|---|
| Remove a PERSON finding only if one of its words is a known first name, from a public list such as the US Social Security baby-name data | "Gross Profit" stays; "John Smith" is removed wherever it appears | A name missing from the list would pass; the list adds a data file |
| Use a larger spaCy model, `en_core_web_lg` or a transformer model | Fewer false alarms everywhere, with no rule changes | About 400 MB more to install and a slower start; measure it on 20 to 30 test phrases before switching |
| Skip headings and table headers | Fixes the symptom | Rejected: a heading such as "Top customer: John Smith" would pass unchecked |
| Keep it as it is | No new risk | Executives see `[removed]` in some tables |

The first two can be combined. Either way, a test set of harmless headers and
real names in headings, tables and sentences should decide, and no option may
let a real name through that passes today.

## 2. The churn rate has no fixed formula

**Seen on 2026-11-08.** Asked about churn twice, the agent divided churned
customers by all customers ever in one run (82%) and by customers active at the
start of the month in another (27%). Each answer stated its formula, but the
numbers are not comparable between conversations.

**Options.** Write the formula next to the 90-day definition in the prompt's
business definitions, or add a Golden Knowledge trio with the approved churn
query, so every answer uses it.

## 3. Five queries are tight for "why" questions with breakdowns

**Seen on 2026-11-08.** "Why did churn rise, by traffic source and category"
spent all 5 queries before the breakdown and said so. The follow-up question
answered it.

**Options.** Raise `limits.queries` in `config/agent/limits.yaml` for questions
that ask for breakdowns, as report requests already get more time; or let the
model combine breakdowns into one query with `GROUP BY ROLLUP`. Either needs a
check that the 30-second limit still holds.
