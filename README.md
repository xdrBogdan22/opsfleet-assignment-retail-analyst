# OpsFleet assignment: retail analyst

Technical assignment for OpsFleet. The goal is a data analysis chat agent for
retail executives, built on BigQuery's `thelook_ecommerce` dataset.

## For reviewers

Each deliverable of the [brief](docs/client-requirements/initial-requirements.md)
and where it is:

| Deliverable | Where |
|---|---|
| 1. Architecture diagram, services, compute and data stores | [Architecture](docs/02-architecture.md) |
| 2.1 Reasoning for cloud services, models and frameworks | [Technical explanation §1](docs/04-technical-explanation.md#1-choices-and-reasons) |
| 2.2 Data flow between components | [Technical explanation §2](docs/04-technical-explanation.md#2-data-flow) |
| 2.3 Error handling and fallback | [Technical explanation §3](docs/04-technical-explanation.md#3-error-handling-and-fallback) |
| 2.4 Setup instructions and example run | [Setup](#setup) below, [Example run](docs/example-run.md) |
| 2.5 How each requirement is handled | [Technical explanation §5](docs/04-technical-explanation.md#5-how-each-requirement-is-handled) |
| Working prototype: CLI chat with safety, delete confirmation, resilience and observability | This repository; [Run the chat](#run-the-chat) |
| Framework choice, reasons and experience | [Technology decisions](docs/01-technology-decisions.md) |

[Requirements traceability](docs/05-requirements-traceability.md) maps every
sentence of the brief to where it is handled.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), the
[Google Cloud CLI](https://cloud.google.com/sdk/docs/install), a Google Cloud
project with BigQuery access and a
[Gemini API key](https://aistudio.google.com/apikey). The
[BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox) works and
needs no billing account. Enable the
[BigQuery API](https://console.cloud.google.com/apis/library/bigquery.googleapis.com)
on that project.

```bash
git clone https://github.com/xdrBogdan22/opsfleet-assignment-retail-analyst.git
cd opsfleet-assignment-retail-analyst
uv sync --frozen
cp .env.example .env
```

Set `GOOGLE_API_KEY` and `GOOGLE_CLOUD_PROJECT` in `.env`, then sign in and
check both connections. `uv` installs Python 3.12 and the exact locked
dependencies. The check uses a BigQuery dry run and lists Gemini models, so it
scans no data and generates no text.

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
uv run --frozen python scripts/doctor.py
```

### Postgres

The app stores reports, confirmations and conversation state in Postgres with
the pgvector extension. Docker is not needed.

```bash
# macOS
brew install postgresql@18 pgvector
brew services start postgresql@18

# Debian or Ubuntu, after adding the PGDG apt repository
sudo apt install postgresql-18 postgresql-18-pgvector
```

Create the database, point `DATABASE_URL` in `.env` at it, then create the
tables and demo data:

```bash
createdb retail_analyst
uv run --frozen python scripts/init_db.py
```

### Run the chat

```bash
uv run --frozen retail-analyst --user denim_manager
```

Demo users: `ceo` sees every brand, `denim_manager` and `outdoor_manager` see
only their brands (`config/seed/demo.yaml`). Ask for a report and open it with
`/open <id>`. Ask to delete reports, for example "Delete all reports mentioning
Acme", and confirm the listed reports with `yes`; any other answer cancels.
Type `/new` for a new conversation and `/quit` to leave.

### Example questions

[Example run](docs/example-run.md) has one question for each kind
the brief lists, run end to end through the CLI on 2026-11-10, with the full
answers and every figure checked against an independent BigQuery query:

| Kind | Question |
|---|---|
| Database structure | What data is available, and what kinds of analysis can I do with it? |
| Customer behavior | Who were our top 5 customers by total spend in 2025, with their number of orders? |
| Time-based metrics | Show monthly revenue for each month from January to June 2026. / Year-to-date revenue in 2026 by brand, highest first. |
| Product performance | Compare Diesel and True Religion in 2025: revenue, items sold, average sale price and return rate. Why do they perform differently? |
| Multi-step with a report | Why did our revenue change in May 2026 compared with April 2026? Break it down by product category, then save a report with action items. |

It also shows a manager asking about a brand outside their scope, asking for
customer emails, trying a prompt injection and deleting a report, then the CEO
asking across all brands, with that turn's Langfuse scores. Try them as
`denim_manager`, `outdoor_manager` and `ceo`.

### Monitoring (optional)

Without keys the app writes one JSON line per turn to `retail_analyst.log`.

For full traces, run Langfuse locally with Docker. One command writes its
secrets, starts it and adds the keys to `.env`:

```bash
infra/langfuse/setup.sh     # then open http://localhost:3000
```

[Langfuse Cloud](https://cloud.langfuse.com) works too: put its
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST` in `.env`.
For error alerts, create a Python project on [Sentry](https://sentry.io) and
put its `SENTRY_DSN` in `.env`.

The CLI prints which services are on when it starts. `/good` and `/bad` attach
a rating to the last answer's trace.

### Tests and evaluation

```bash
uv run --frozen pytest                     # unit tests, plus live tests when keys are set
uv run --frozen python eval/run_eval.py    # 14 cases scored with Ragas, with a release gate
```

The evaluation makes real Gemini calls; see [eval/README](eval/README.md) for
the metrics and for running it on a free-tier key.

## Repository layout

| Folder | Contents |
|---|---|
| [`config/`](config/README.md) | Every limit, model and data rule, with the reason for each default |
| [`db/`](db/README.md) | Postgres schema |
| [`scripts/`](scripts/README.md) | Setup and connection checks |
| [`src/retail_analyst/`](src/retail_analyst/README.md) | Application code |
| [`tests/`](tests/README.md) | Unit and integration tests |
| [`eval/`](eval/README.md) | Evaluation dataset, runner and release gate |
| [`infra/`](infra/langfuse/README.md) | Local Langfuse with Docker |
| `.claude/`, [`CLAUDE.md`](CLAUDE.md) | Project rules and the `/add-tool` skill for coding agents |
| `docs/` | Design documents, listed below |

## Contents

The design, in reading order:

- [Technology decisions](docs/01-technology-decisions.md): the framework choice
- [Architecture](docs/02-architecture.md): the high-level design and its diagrams
- [Design decisions](docs/03-design-decisions.md): options and sources behind each choice, P1 to P22
- [Technical explanation](docs/04-technical-explanation.md): how it works and how each requirement is solved
- [Requirements traceability](docs/05-requirements-traceability.md): the brief, sentence by sentence
- [Example run](docs/example-run.md): verified CLI sessions

Project notes:

- [Evaluation](eval/README.md)
- [Progress log](docs/progress.md)
- [Known limitations](docs/known-limitations.md)

From the client:

- [Client requirements](docs/client-requirements/initial-requirements.md)
- [Client questions](docs/client-requirements/open-questions.md)
- [BigQuery starter code](docs/client-requirements/big_query.py)
