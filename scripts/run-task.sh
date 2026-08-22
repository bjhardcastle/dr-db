#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 TASK [ARGUMENT ...]" >&2
    echo "Available tasks:" >&2
    find "$(dirname "$0")/tasks" -maxdepth 1 -type f -perm -111 -exec basename {} \; | sort >&2
    exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
TASK=$1
shift
TASK_PATH="$SCRIPT_DIR/tasks/$TASK"

case "$TASK" in
    ''|*[!A-Za-z0-9_-]*)
        echo "Invalid task name: $TASK" >&2
        exit 2
        ;;
esac

if [ ! -x "$TASK_PATH" ]; then
    echo "Task is not executable or does not exist: $TASK_PATH" >&2
    exit 2
fi

: "${DR_DB_TASK_LOCK_DIR:=/tmp/dr-db-task-locks}"
mkdir -p "$DR_DB_TASK_LOCK_DIR"

if ! command -v flock >/dev/null 2>&1; then
    echo "flock is required to run scheduled tasks safely." >&2
    exit 1
fi

cd "$REPO_ROOT"
exec flock --exclusive --nonblock "$DR_DB_TASK_LOCK_DIR/$TASK.lock" \
    "$TASK_PATH" "$@"
