# Task scripts

This directory contains operational commands that can be run manually or by a
host scheduler. Every scheduled command should have a small executable wrapper
in `scripts/tasks/`.

Run a task through the common runner:

```bash
./scripts/run-task.sh migrate-dev
./scripts/run-task.sh clone-prod-to-dev
```

The runner uses `flock` so two copies of the same task cannot run at once. It
does not contain credentials. Compose reads the repository's `.env` file, or a
different file can be selected with `DR_DB_ENV_FILE`. The task wrappers use
`scripts/compose-tools.sh` for this consistently.

Keep reusable application logic in `src/dr_db/`; keep these scripts thin and
focused on operational concerns such as selecting a database, creating an
output directory, or invoking Docker Compose.
