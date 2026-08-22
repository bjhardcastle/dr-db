#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 COMPOSE_SERVICE [COMMAND_ARGUMENT ...]" >&2
    exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SERVICE=$1
shift

cd "$REPO_ROOT"
if [ -n "${DR_DB_ENV_FILE:-}" ]; then
    exec docker compose --env-file "$DR_DB_ENV_FILE" \
        --profile tools run --rm "$SERVICE" "$@"
fi

exec docker compose --profile tools run --rm "$SERVICE" "$@"
