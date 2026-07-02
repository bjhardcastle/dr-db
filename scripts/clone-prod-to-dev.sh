#!/usr/bin/env sh
set -eu

SOURCE_HOST="${DR_DB_CLONE_SOURCE_HOST:-postgres}"
SOURCE_PORT="${DR_DB_CLONE_SOURCE_PORT:-5432}"
SOURCE_DB="${DR_DB_CLONE_SOURCE_DB:-${DR_DB_POSTGRES_DB:-dr_db}}"
SOURCE_USER="${DR_DB_CLONE_SOURCE_USER:-${DR_DB_POSTGRES_USER:-svc_neuropix}}"
SOURCE_PASSWORD="${DR_DB_CLONE_SOURCE_PASSWORD:-${DR_DB_POSTGRES_PASSWORD:-}}"

TARGET_HOST="${DR_DB_CLONE_TARGET_HOST:-postgres-dev}"
TARGET_PORT="${DR_DB_CLONE_TARGET_PORT:-5432}"
TARGET_DB="${DR_DB_CLONE_TARGET_DB:-${DR_DB_DEV_POSTGRES_DB:-dr_db_dev}}"
TARGET_USER="${DR_DB_CLONE_TARGET_USER:-${DR_DB_DEV_POSTGRES_USER:-svc_neuropix}}"
TARGET_PASSWORD="${DR_DB_CLONE_TARGET_PASSWORD:-${DR_DB_DEV_POSTGRES_PASSWORD:-}}"
TARGET_MAINTENANCE_DB="${DR_DB_CLONE_TARGET_MAINTENANCE_DB:-postgres}"

if [ -z "$SOURCE_PASSWORD" ]; then
    echo "DR_DB_POSTGRES_PASSWORD or DR_DB_CLONE_SOURCE_PASSWORD must be set." >&2
    exit 1
fi

if [ -z "$TARGET_PASSWORD" ]; then
    echo "DR_DB_DEV_POSTGRES_PASSWORD or DR_DB_CLONE_TARGET_PASSWORD must be set." >&2
    exit 1
fi

if [ "$SOURCE_HOST:$SOURCE_PORT/$SOURCE_DB" = "$TARGET_HOST:$TARGET_PORT/$TARGET_DB" ]; then
    echo "Source and target database are identical; refusing to clone." >&2
    exit 1
fi

echo "Recreating dev database $TARGET_DB on $TARGET_HOST:$TARGET_PORT..."

PGPASSWORD="$TARGET_PASSWORD" psql \
    --host "$TARGET_HOST" \
    --port "$TARGET_PORT" \
    --username "$TARGET_USER" \
    --dbname "$TARGET_MAINTENANCE_DB" \
    --set=ON_ERROR_STOP=1 \
    --variable=target_db="$TARGET_DB" \
    --variable=target_user="$TARGET_USER" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'target_db'
    AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS :"target_db";
CREATE DATABASE :"target_db" OWNER :"target_user";
SQL

echo "Copying $SOURCE_DB from $SOURCE_HOST:$SOURCE_PORT into $TARGET_DB..."

PGPASSWORD="$SOURCE_PASSWORD" pg_dump \
    --host "$SOURCE_HOST" \
    --port "$SOURCE_PORT" \
    --username "$SOURCE_USER" \
    --format=custom \
    --no-owner \
    --no-acl \
    "$SOURCE_DB" \
| PGPASSWORD="$TARGET_PASSWORD" pg_restore \
    --host "$TARGET_HOST" \
    --port "$TARGET_PORT" \
    --username "$TARGET_USER" \
    --dbname "$TARGET_DB" \
    --exit-on-error \
    --single-transaction \
    --no-owner \
    --no-acl

echo "Dev database $TARGET_DB is now cloned from $SOURCE_DB."
