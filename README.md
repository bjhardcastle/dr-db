# dr-db

Docker Compose setup for a shared PostgreSQL database plus Mathesar, intended
to run on the Rocky Linux VM.

## Storage

Persistent container data lives outside the repo under:

```text
/home/ben.hardcastle/.local/share/dr-db
```

Prepare the directory structure without overwriting anything:

```bash
./scripts/ensure-docker-storage.sh
```

## Start

The real `.env` file is intentionally ignored by git. Create it on the VM from
the template, set `DR_DB_POSTGRES_PASSWORD` to the shared password, and make
sure `DR_DB_STORAGE_ROOT` points at a directory owned by your VM user.

```bash
cp .env.example .env
$EDITOR .env
./scripts/ensure-docker-storage.sh
docker compose up -d
```

If Compose reports that it cannot create a bind mount under `/allen/...`, update
`DR_DB_STORAGE_ROOT` in `.env` to a user-owned path such as
`/home/ben.hardcastle/.local/share/dr-db`, then rerun the storage helper before
starting Compose again.

If Docker reports `permission denied while trying to connect to the docker API
at unix:///var/run/docker.sock`, make sure your VM user is in the `docker`
group:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker version
```

After `newgrp docker`, `id` should include `docker` and `docker version` should
show both client and server details. Avoid running Compose with `sudo` from this
repo; on the VM, root may not be able to read `.env` from the protected home
directory.

## Connections

PostgreSQL:

```text
Host: dr-db
Port: 7500
Database: dr_db
User: svc_neuropix
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
`dr-db`, port `5432`, database `dr_db`, user `svc_neuropix`, and the same
password from `.env`.
