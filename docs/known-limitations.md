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

## 4. Whole-row selects and grouped aggregates pass the demographics rule

**Found in a code review on 2026-11-10.** Reproduced with sqlglot's parser,
not yet run on BigQuery. `_check_demographics_with_customer_id` in
`safety/sql_guard.py` misses two shapes:

- `SELECT u FROM users u` returns the whole row as a struct: the hashed ID
  next to age, gender, city, state and country. sqlglot sees one column named
  `u`, so neither a customer ID nor a demographic column is found.
- `SELECT id, ANY_VALUE(city), MAX(age) FROM users GROUP BY id` passes,
  because columns inside aggregates are skipped. Grouped by customer ID, the
  aggregate is the raw value.

Names, emails and addresses are still never exposed: the scoped subquery has
no such columns. What leaks is a hashed ID with the demographics that can
single out a person. `min_group_size` in `config/data/safety.yaml` is not
enforced either.

**Options.**

| Option | Effect | Cost or risk |
|---|---|---|
| Reject a column whose name is a table alias of its SELECT | Closes the whole-row struct | One more AST rule; `TO_JSON_STRING(u)` and similar need the same check |
| When a customer ID is selected or grouped on, reject demographic columns even inside aggregates | Closes `ANY_VALUE` and `MAX` | Blocks "top customers with their average age"; such questions need a breakdown without IDs |
| Enforce `min_group_size` by wrapping demographic breakdowns in `HAVING COUNT(DISTINCT user_id) >= 10` | Small groups disappear from results | Changes totals; the answer must say rows were hidden |
| Authorized views that expose demographics only in pre-aggregated form | Removes the class of problem in production | Design change; fewer free-form questions |

## 5. The ID hash salt can be read by a query

**Found in a code review on 2026-11-10.** Reproduced with sqlglot's parser,
not yet run on BigQuery. The salt is passed as the query parameter
`@id_salt` to every query, and the SQL guard does not reject parameters in
the model's SQL, so `SELECT @id_salt` returns it. With the salt and about
100,000 integer customer IDs, every hashed code can be reversed in seconds.

**Options.** Reject any `exp.Parameter` in the model's SQL before rewriting,
since the model never needs one; that is a one-line rule with a test. In
production, compute the hash inside the authorized view or a persistent UDF,
so the salt never travels with a query.

## 6. Answering a clarifying question uses up the time limit

**Found in a code review on 2026-11-10.** `started_at` is set when the
question arrives, and `agent` in `agent/graph.py` compares the elapsed time
with the limit. The time the user spends reading and answering a clarifying
question counts too. A user who answers after 30 seconds gets the forced
final answer, without tools and so without data.

**Options.** Let the `clarify` node move `started_at` forward by the time
spent in the pause, or give the question a fresh time limit after the
answer. Either needs a graph test with a slow answer.

## 7. Conversation history is never trimmed

**Found in a code review on 2026-11-10.** Every turn sends the whole
conversation, including every earlier query result, to the model. Cost and
latency grow with the length of the conversation, and a long one can reach
the time limit before any new query runs.

**Options.** Keep earlier answers but replace earlier tool results with a
short note, using LangChain's `trim_messages` or a summary step; or keep the
last few turns in full. The eval should include a long conversation before
and after.

## 8. The time limit is checked only before a model call

**Found in a code review on 2026-11-10.** The 30 and 120 second limits in
`config/agent/limits.yaml` are described as hard stops, but `agent` checks
them only on entry. A model call (up to 20 seconds) and queries (up to the
BigQuery timeout each) that start just before the limit run to the end.

**Options.** Pass the remaining time as the timeout of the model call and of
each query, or describe the limits as soft in the config comments.

## 9. The clarifying question skips the output guard

**Found in a code review on 2026-11-10.** The question and options of
`ask_clarification` reach the user through the `clarify` interrupt without
passing `safety/output_guard.py`. The model never sees personal columns, so
the risk is low, but it breaks the rule that all text reaching the user
passes the guard.

**Options.** Run the question and each option through `redact` in the tool
or in the `clarify` node.
