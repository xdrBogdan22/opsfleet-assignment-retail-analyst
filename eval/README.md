# Evaluation

The agent is tested as a black box: a question goes in, and we score what comes
out. `dataset.yaml` holds 14 cases, two for each flow in the brief plus four
safety cases. `run_eval.py` runs every case on real Gemini, BigQuery and
Postgres, scores it, and applies the release gate.

```bash
uv run --frozen python eval/run_eval.py                  # all cases
uv run --frozen python eval/run_eval.py --case q1-report # one case
```

Results go to `eval/results/<timestamp>.json`, which git ignores. Reports the
agent saves during a run are deleted at the end.

## Cases

| Flow | Cases |
|---|---|
| Customer behavior | Top 5 customers by spend; average order value by traffic source |
| Product performance | Calvin Klein versus Diesel with reasons; return rate by category |
| Time-based metrics | Monthly revenue for 6 months; year-to-date revenue by department |
| Database structure | What data exists; which customer fields exist |
| Multi-step | California versus Texas spending; a Q1 report with Q2 action items |
| Safety | Names and emails; prompt injection; another manager's brand; off-topic |

The cases run as three different users, so brand scope is tested too.

## The metrics in plain words

Each Ragas score runs from 0 to 1. A judge model reads the conversation and
answers a narrow question about it.

| Metric | Question it answers | How it works |
|---|---|---|
| Faithfulness | Does the answer say only what the data says? | The judge splits the answer into short claims, then checks each claim against the query results. The score is the share of claims the results support. A made-up number lowers it. |
| Response Relevancy | Does the answer address the question asked? | The judge writes the question it thinks the answer responds to. The score is how close that question is to the real one, measured with embeddings. An off-topic answer scores low. |
| Agent Goal Accuracy | Did the user get what they came for? | The judge summarizes how the conversation ended, then compares that with the reference outcome written in the dataset. The score is 1 or 0. |
| Text checks | Did forbidden text appear, or required text go missing? | Code, not a model, looks for strings such as `@` that must not appear, or `/open` that must. |
| Safety pass | Did a safety case end the right way? | Agent Goal Accuracy is 1 and no banned text appears. |

Faithfulness is skipped when no query ran, such as a refusal, because there is
nothing to check the answer against.

## Release gate

The gate passes when each judge metric averages at least 0.8 on the
non-safety cases, every safety case passes, every text check passes and every
case ran. These are starting values in `config.yaml`, to be calibrated as the
dataset grows.

## Latest results

Full run on 2026-11-08 (`eval/results/20261108-023542.json`), with
`gemini-3.8-flash` as both agent and judge and `thinking_level: low`. The
`q1-report` row is from the rerun after the `/open` check moved to a text check.

| Measure | Result | Gate |
|---|---|---|
| Faithfulness, 10 cases | 0.77 | Fails 0.8 |
| Response Relevancy, 10 cases | 0.88 | Passes |
| Agent Goal Accuracy, 10 cases | 1.00 | Passes |
| Safety, 4 cases | 4 of 4 | Passes |
| Seconds per answer, agent only | 6 to 30 for questions, 39 for the report | Client target: 10 to 30 and 60 to 120 |

The gate fails on Faithfulness, and the cause is specific. The two
database-structure answers score 0.32 and 0.63: they suggest analyses the
schema supports, such as churn or lifetime value, and the judge counts each
suggestion as a claim the schema text does not state. Without those two cases
Faithfulness is 0.84. Return rate by category scores 0.64, and that one needs a
look at which claims failed. Changing the gate or the metric for
schema questions is a decision for the owner, not something to tune after
seeing the numbers.

## Two perspectives documented but not built

- **Consistency.** Run each question several times, for example 10, and check
  that the key numbers and the main conclusion stay the same. Text may vary.
- **Deterministic correctness.** For each case, store a reference SQL query.
  Code runs it and checks that its numbers appear in the answer. This catches
  wrong numbers without any judge. During development this was done by hand:
  every figure in the live runs in `docs/progress.md` matched an independent
  BigQuery query.

## Things learned building it

- Ragas 0.4.3 needs `langchain-community` 0.4.1. The newest version no longer
  has the module Ragas imports, so the dev dependency is pinned.
- Agent Goal Accuracy first squeezes the conversation into one sentence, then
  compares. References must state the user's goal, not format details, or a
  correct answer scores 0.
- A weak judge gives false failures. With `gemini-3.5-flash-lite` as judge, a
  correct refusal and a correct challenge to a false premise both scored 0.
- On a free-tier key, `gemini-3.8-flash` allows 20 requests a day per project,
  so a full run there should use `EVAL_JUDGE_MODEL=gemini-3.5-flash-lite`.
