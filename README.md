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

```bash
docker compose --profile tools run --rm dbmate-dev up
```

For prod:

```bash
docker compose --profile tools run --rm dbmate-prod up
```
