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

usage() {
  cat <<EOF
Usage: ./scripts/reset-docker-storage.sh --yes

Removes and recreates the disposable Docker storage directories for this repo.
The storage root is read from .env, unless DR_DB_STORAGE_ROOT is already set in
the shell environment.
EOF
}

if [[ "${1-}" != "--yes" ]]; then
  usage
  cat <<EOF

Refusing to remove anything without --yes.

Resolved storage root:
  $root
EOF
  exit 2
fi

if [[ "$root" == "~"* ]]; then
  echo "DR_DB_STORAGE_ROOT must not use '~', got: '$root'" >&2
  exit 1
fi

if [[ "$root" != /* ]]; then
  echo "DR_DB_STORAGE_ROOT must be an absolute path, got: '$root'" >&2
  exit 1
fi

case "$root" in
  /|/home|"$HOME")
    echo "Refusing unsafe DR_DB_STORAGE_ROOT: '$root'" >&2
    exit 1
    ;;
esac

targets=(
  "${root%/}/postgres"
  "${root%/}/mathesar"
)

for path in "${targets[@]}"; do
  case "$path" in
    "${root%/}/"*) ;;
    *)
      echo "Refusing to remove path outside storage root: '$path'" >&2
      exit 1
      ;;
  esac
done

printf "Removing Docker storage under: %s\n" "$root"
for path in "${targets[@]}"; do
  printf "Removing: %s\n" "$path"
done

if ! rm -rf -- "${targets[@]}"; then
  cat >&2 <<EOF

Failed to remove one or more storage directories.

If a previous container run created root-owned files, run:
  sudo rm -rf -- ${targets[0]@Q} ${targets[1]@Q}
  ./scripts/ensure-docker-storage.sh
EOF
  exit 1
fi

"$script_dir/ensure-docker-storage.sh"
