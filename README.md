# dr-db

Docker Compose setup for a shared PostgreSQL database plus Mathesar.

## Storage

Persistent container data lives outside the repo under:

```text
//allen/ai/homedirs/ben.hardcastle/dr-db
```

Prepare the directory structure without overwriting anything:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ensure-docker-storage.ps1
```

## Start

The real `.env` file is intentionally ignored by git. This checkout has one with
the requested local password; use `.env.example` as the template for new
checkouts.

```powershell
docker compose up -d
```

## Connections

PostgreSQL:

```text
Host: dr-db
Port: 7500
Database: dr_db
User: dr_db_admin
Password: see local .env
```

If `dr-db` is not resolvable from a client machine, use the Docker host name or
IP address with port `7500`.

Mathesar:

```text
http://dr-db:7000
```

If opening Mathesar on the Docker host itself, `http://localhost:7000` should
also work. When connecting Mathesar to the user database from the UI, use host
`dr-db`, port `5432`, database `dr_db`, user `dr_db_admin`, and the same
password from `.env`.
