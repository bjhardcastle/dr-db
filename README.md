## Setting up db

From a fresh checkout:

1. Install Docker Engine with the Compose plugin and start Docker.
2. Copy `.env.example` to `.env`.
3. In `.env`, replace every `replace-me` with a password. Keep `.env` local; do not commit it.
4. Start prod and dev Postgres dbs:

```bash
docker compose up -d postgres postgres-dev
```

## Starting Mathesar

```bash
docker compose -f compose.yml -f docker.mathesar.yaml up -d postgres mathesar-proxy
```

Open `http://localhost` (or one of the `MATHESAR_DOMAIN_NAME` domains), followed by `:<MATHESAR_HOST_PORT>` if not using the default port `:80`.



5. (optional) Run all existing migrations against the database you want to initialize. For local dev:
The Postgres image builds `pg_parquet` 0.5.1 for PostgreSQL 17 and preloads it
in both database services. Rebuild after changing the extension version:

```bash
docker compose build postgres postgres-dev
docker compose up -d postgres postgres-dev
```

5. Run migrations against the database you want to initialize. For local dev:

```bash
docker compose --profile tools run --rm dbmate-dev up
```

For prod:

```bash
docker compose --profile tools run --rm dbmate-prod up
```

Both commands construct their database connection from `.env`. Keep `.env` local; do not commit it.

## Scheduled tasks

Operational task wrappers live in [`scripts/tasks/`](scripts/tasks/README.md),
and the production schedule is in
[`ops/cron/dr-db.crontab`](ops/cron/dr-db.crontab). Run tasks manually through
the locking wrapper:

```bash
./scripts/run-task.sh migrate-dev
./scripts/run-task.sh clone-prod-to-dev
```

See [`ops/README.md`](ops/README.md) before installing the cron schedule. The
schedule contains no credentials; production secrets belong in a host-only env
file.

To export every non-system table in the production database to local Parquet
files under `.data/parquet`:

```bash
./scripts/tasks/export-prod-to-parquet
```

Set `PARQUET_OUTPUT_URI` to an `s3://...` URI for an object-store export. The
Postgres service needs AWS credentials and the `parquet_object_store_write`
role for that destination.
