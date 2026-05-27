# dr-db

Docker Compose setup for a shared PostgreSQL database plus Mathesar, intended
to run on the Rocky Linux VM.

## Storage

Persistent container data lives outside the repo under:

```text
/allen/ai/homedirs/ben.hardcastle/dr-db
```

Prepare the directory structure without overwriting anything:

```bash
./scripts/ensure-docker-storage.sh
```

## Start

The real `.env` file is intentionally ignored by git. Create it on the VM from
the template and set `DR_DB_POSTGRES_PASSWORD` to the shared password.

```bash
cp .env.example .env
$EDITOR .env
./scripts/ensure-docker-storage.sh
docker compose up -d
```

## Connections

PostgreSQL:

```text
Host: dr-db
Port: 7500
Database: main
User: dr_db_admin
Password: see local .env
```

If `dr-db` is not resolvable from a client machine, use the Docker host name or
IP address with port `7500`, or add `dr-db` to DNS or `/etc/hosts` pointing at
the VM.

Mathesar has a separate internal Postgres container for its own metadata. That
internal database uses Mathesar's default database name, `mathesar_django`.
The `.env` variables for that container are prefixed with
`MATHESAR_METADATA_POSTGRES_`.

Mathesar:

```text
http://dr-db:7000
```

If opening Mathesar on the Docker host itself, `http://localhost:7000` should
also work. When connecting Mathesar to the user database from the UI, use host
`dr-db`, port `5432`, database `main`, user `dr_db_admin`, and the same
password from `.env`.
