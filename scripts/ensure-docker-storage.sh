#!/usr/bin/env bash
set -euo pipefail

root="${DR_DB_STORAGE_ROOT:-/allen/ai/homedirs/ben.hardcastle/dr-db}"

directories=(
  ""
  "postgres"
  "mathesar"
  "mathesar/static"
  "mathesar/media"
  "mathesar/secrets"
  "mathesar/caddy"
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
    echo "Exists:  $path"
    continue
  fi

  mkdir -p "$path"
  echo "Created: $path"
done
