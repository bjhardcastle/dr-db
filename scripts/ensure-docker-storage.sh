#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
env_storage_root="${DR_DB_STORAGE_ROOT-}"

if [[ -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

if [[ -n "$env_storage_root" ]]; then
  DR_DB_STORAGE_ROOT="$env_storage_root"
fi

root="${DR_DB_STORAGE_ROOT:-${HOME:?}/dr-db}"
current_uid="$(id -u)"
current_gid="$(id -g)"
container_uid="${DR_DB_CONTAINER_UID-}"
container_gid="${DR_DB_CONTAINER_GID-}"

if [[ "$root" == "~"* ]]; then
  cat >&2 <<EOF
DR_DB_STORAGE_ROOT must not use '~', got: '$root'

Use an absolute path owned by this VM user instead, for example:
  DR_DB_STORAGE_ROOT=$HOME/dr-db
EOF
  exit 1
fi

if [[ "$root" != /* ]]; then
  echo "DR_DB_STORAGE_ROOT must be an absolute path, got: '$root'" >&2
  exit 1
fi

if [[ -z "$container_uid" || -z "$container_gid" ]]; then
  cat >&2 <<EOF
DR_DB_CONTAINER_UID and DR_DB_CONTAINER_GID must be set in .env.

Set them from this VM user:
  DR_DB_CONTAINER_UID=$current_uid
  DR_DB_CONTAINER_GID=$current_gid
EOF
  exit 1
fi

if [[ "$container_uid" != "$current_uid" || "$container_gid" != "$current_gid" ]]; then
  cat >&2 <<EOF
DR_DB_CONTAINER_UID/GID do not match this VM user.

Current VM user:        $current_uid:$current_gid
Configured containers:  $container_uid:$container_gid

Update .env with:
  DR_DB_CONTAINER_UID=$current_uid
  DR_DB_CONTAINER_GID=$current_gid

Then rerun:
  ./scripts/ensure-docker-storage.sh
EOF
  exit 1
fi

describe_path() {
  if command -v stat >/dev/null 2>&1; then
    stat -c "%A %U:%G %n" "$1" 2>/dev/null || ls -ld "$1"
  else
    ls -ld "$1"
  fi
}

directories=(
  ""
  "postgres"
  "mathesar"
  "mathesar/pgdata"
  "mathesar/static"
  "mathesar/media"
  "mathesar/secrets"
)

for relative_path in "${directories[@]}"; do
  if [[ -n "$relative_path" ]]; then
    path="${root%/}/$relative_path"
  else
    path="$root"
  fi

  if [[ -f "$path" ]]; then
    echo "Refusing to continue because '$path' exists and is a file." >&2
    exit 1
  fi

  if [[ -d "$path" ]]; then
    if [[ ! -r "$path" || ! -w "$path" || ! -x "$path" ]]; then
      cat >&2 <<EOF
Exists but is not readable, writable, and traversable by this VM user:
  $(describe_path "$path")

This usually means the directory was created by an earlier container run as a
different user, or DR_DB_CONTAINER_UID/GID changed.

To reset disposable Docker storage, run:
  ./scripts/reset-docker-storage.sh --yes

If reset reports permission denied, remove the stale directories with sudo,
then rerun this script.
EOF
      exit 1
    fi
    echo "Exists:  $path"
    continue
  fi

  if ! mkdir -p "$path"; then
    cat >&2 <<EOF
Failed to create '$path'.

Set DR_DB_STORAGE_ROOT in .env to a directory owned by this VM user, then rerun:
  ./scripts/ensure-docker-storage.sh

For example:
  DR_DB_STORAGE_ROOT=$HOME/dr-db
EOF
    exit 1
  fi
  echo "Created: $path"
done

cat <<EOF

Storage root is ready: $root

If Docker Compose still reports permission denied for this path, check directory
traversal permissions with:
  namei -l "$root/mathesar/pgdata"

For storage under /home/ben.hardcastle, Docker may need execute permission on
the parent directories, for example:
  chmod o+x /home/ben.hardcastle
  chmod o+x /home/ben.hardcastle/dr-db
EOF
