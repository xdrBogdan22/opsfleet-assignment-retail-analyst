# OpsFleet assignment: retail analyst

Technical assignment for OpsFleet. The goal is a data analysis chat agent for
retail executives, built on BigQuery's `thelook_ecommerce` dataset.

Work in progress.

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

## Contents

- [Technology decisions](docs/01-technology-decisions.md)
- [Architecture](docs/02-architecture.md)
- [Design proposals](docs/03-design-proposals.md)
- [Open client questions](docs/client-requirements/open-questions.md)
- [Client requirements](docs/client-requirements/initial-requirements.md)
- [BigQuery starter code](docs/client-requirements/big_query.py)
