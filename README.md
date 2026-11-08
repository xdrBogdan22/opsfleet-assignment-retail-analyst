# OpsFleet assignment: retail analyst

Technical assignment for OpsFleet. The goal is a data analysis chat agent for
retail executives, built on BigQuery's `thelook_ecommerce` dataset.


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
Acme", and confirm the listed reports with `yes`; any other answer cancels. Type `/new` for a new conversation and `/quit` to leave. 

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
| `docs/` | Design documents, listed below |

## Contents

- [Technology decisions](docs/01-technology-decisions.md)
- [Architecture](docs/02-architecture.md)
- [Design proposals](docs/03-design-proposals.md)
- [Technical explanation](docs/04-technical-explanation.md)
- [Requirements traceability](docs/05-requirements-traceability.md)
- [Example run](docs/example-run.md)
- [Evaluation](eval/README.md)
- [Progress log](docs/progress.md)
- [Known limitations](docs/known-limitations.md)
- [Client questions](docs/client-requirements/open-questions.md)
- [Client requirements](docs/client-requirements/initial-requirements.md)
- [BigQuery starter code](docs/client-requirements/big_query.py)
