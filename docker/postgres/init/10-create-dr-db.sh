#!/usr/bin/env bash
set -euo pipefail

app_db="${DR_DB_APP_DB:-main}"

case "$app_db" in
  ""|*[!A-Za-z0-9_]*)
    echo "Invalid DR_DB_APP_DB '$app_db'; use letters, numbers, and underscores only." >&2
    exit 1
    ;;
esac

if psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align \
  --command "SELECT 1 FROM pg_database WHERE datname = '$app_db';" | grep -q '^1$'; then
  echo "Database '$app_db' already exists; leaving it unchanged."
else
  createdb --username "$POSTGRES_USER" --owner "$POSTGRES_USER" "$app_db"
  echo "Created database '$app_db' owned by '$POSTGRES_USER'."
fi
