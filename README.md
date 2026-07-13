## Setting up db

From a fresh checkout:

1. Install Docker Desktop and start it.
2. Copy `.env.example` to `.env`.
3. In `.env`, replace every `replace-me` password and set `DR_DB_STORAGE_ROOT` to a real folder where Docker can keep database files. This folder is persistent data, not source code.
4. Start Postgres:

```powershell
docker compose up -d postgres postgres-dev
```

5. Run migrations against the database you want to initialize. For local dev:

```powershell
$env:DATABASE_URL = "postgres://svc_neuropix:<dev-password>@postgres-dev:5432/dr_db_dev?sslmode=disable"
docker compose --profile tools run --rm dbmate up
```

Use the non-dev username, password, host, and db name from `.env` when initializing prod. Keep `.env` local; do not commit it.
