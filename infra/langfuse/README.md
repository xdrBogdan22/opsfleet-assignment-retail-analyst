# Local Langfuse

Langfuse shows each conversation turn as a trace: every model call, tool call,
SQL query and result in order, with the turn's scores. This folder runs it on
your machine with Docker, so no account is needed.

```bash
infra/langfuse/setup.sh
```

The script does three things, and is safe to run again:

1. Writes `infra/langfuse/.env` with random secrets, plus a first user,
   project and API keys that Langfuse creates at its first start. Git ignores
   the file.
2. Adds `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST` to the
   app's `.env`, unless a secret key is already there.
3. Starts the stack and waits until `http://localhost:3000` answers.

Sign in as `admin@retail-analyst.local`. The password is
`LANGFUSE_INIT_USER_PASSWORD` in `infra/langfuse/.env`.

## What runs

`docker-compose.yml` is the upstream Langfuse v4.76.0 file. The only change is
that its Postgres and Redis publish no host port, because the app's Postgres or
a local Redis often holds 5432 and 6379. The stack is Langfuse web and worker,
Postgres, ClickHouse, Redis and MinIO. Upstream recommends 4 cores and 16 GB
for a server; a laptop runs it for development.

## Stop or reset

```bash
docker compose -f infra/langfuse/docker-compose.yml --env-file infra/langfuse/.env down      # stop, keep data
docker compose -f infra/langfuse/docker-compose.yml --env-file infra/langfuse/.env down -v   # stop and delete data
```

After `down -v`, delete `infra/langfuse/.env` and the three `LANGFUSE_` lines
in `.env` too, then run the script again.

## Reading traces from code

Langfuse v4 stores traces as events and no longer serves
`GET /api/public/traces`. Use `GET /api/public/v2/observations?traceId=<id>`
instead. The `trace_id` of each turn is in `retail_analyst.log`.
