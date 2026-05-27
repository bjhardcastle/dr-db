# dr-db

Docker Compose setup for a shared PostgreSQL database plus Mathesar, intended
to run on the Rocky Linux VM.

## Storage

Persistent container data lives outside the repo under:

```text
/home/ben.hardcastle/dr-db
```

Prepare the directory structure without overwriting anything:

```bash
./scripts/ensure-docker-storage.sh
```

To throw away the local Docker databases and recreate empty storage, use the
reset helper. It reads the same `.env` file as Compose; do not use a bare
`rm -rf "$DR_DB_STORAGE_ROOT/..."` unless you have explicitly sourced `.env`
in that shell.

```bash
docker compose down --remove-orphans
./scripts/reset-docker-storage.sh --yes
docker compose up -d
docker compose ps
```

## Start

The real `.env` file is intentionally ignored by git. Create it on the VM from
the template, set `DR_DB_POSTGRES_PASSWORD` to the shared password, and make
sure `DR_DB_STORAGE_ROOT` points at a directory owned by your VM user.
Set `DR_DB_CONTAINER_UID` and `DR_DB_CONTAINER_GID` from the VM user so
containers can write to home-directory bind mounts without trying to `chown`
them as root.

```bash
cp .env.example .env
id -u
id -g
$EDITOR .env
./scripts/ensure-docker-storage.sh
docker compose up -d
```

If Compose reports that it cannot create a bind mount under `/allen/...`, update
`DR_DB_STORAGE_ROOT` in `.env` to a user-owned path such as
`/home/ben.hardcastle/dr-db`, then rerun the storage helper before
starting Compose again.

If Compose reports `permission denied` while creating a bind mount under
`/home/ben.hardcastle/...`, the storage directories may exist but the Docker
daemon may not be able to traverse the home-directory path. Keep the storage
root under `/home/ben.hardcastle`, then make the parent directories executable
by the daemon:

```bash
namei -l "$DR_DB_STORAGE_ROOT/mathesar/pgdata"
chmod o+x /home/ben.hardcastle
chmod o+x /home/ben.hardcastle/dr-db
./scripts/ensure-docker-storage.sh
docker compose up -d
```

The `chmod o+x` commands allow traversal only; they do not make the directories
world-readable or writable.

On Rocky Linux with SELinux enforcing, home-directory bind mounts also need a
container label. The Compose file sets `bind.selinux: z` on each persisted bind
mount. If a reset leaves either Postgres container restarting, confirm the
diagnosis with:

```bash
getenforce
docker compose logs --tail=100 dr-db-postgres mathesar-metadata-postgres
```

If the logs show `chown`, `chmod`, or `mkdir` permission errors under
`/var/lib/postgresql/data`, confirm `.env` has the VM user's numeric IDs:

```bash
id -u
id -g
grep DR_DB_CONTAINER_ .env
./scripts/ensure-docker-storage.sh
```

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
