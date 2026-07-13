## Setting up db

From a fresh checkout:

1. Install Docker Engine with the Compose plugin and start Docker.
2. Copy `.env.example` to `.env`.
3. In `.env`, replace every `replace-me` password and set `DR_DB_STORAGE_ROOT` to a real folder where Docker can keep database files. This folder is persistent data, not source code.
4. Start Postgres:

```bash
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
