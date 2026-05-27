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
Usage: ./scripts/reset-docker-storage.sh --yes [--all]

Removes and recreates the disposable Docker storage directories for this repo.
The storage root is read from .env, unless DR_DB_STORAGE_ROOT is already set in
the shell environment.

Options:
  --yes   Required confirmation flag.
  --all   Remove the entire storage root instead of just known service dirs.
EOF
}

confirmed=false
remove_all=false

for arg in "$@"; do
  case "$arg" in
    --yes)
      confirmed=true
      ;;
    --all)
      remove_all=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "$confirmed" != true ]]; then
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

if [[ "$root" == "$repo_root" ]]; then
  echo "Refusing to remove repo root as Docker storage: '$root'" >&2
  exit 1
fi

if [[ -d "${root%/}/.git" ]]; then
  echo "Refusing to remove a git checkout as Docker storage: '$root'" >&2
  exit 1
fi

if [[ "$remove_all" == true ]]; then
  targets=("$root")
else
  targets=(
    "${root%/}/postgres"
    "${root%/}/mathesar"
  )
fi

for path in "${targets[@]}"; do
  if [[ "$remove_all" == true && "$path" == "$root" ]]; then
    continue
  fi

  if [[ "$path" != "${root%/}/"* ]]; then
    echo "Refusing to remove path outside storage root: '$path'" >&2
    exit 1
  fi
done

printf "Removing Docker storage under: %s\n" "$root"
if [[ "$remove_all" == true ]]; then
  printf "Mode: remove entire storage root\n"
fi
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
