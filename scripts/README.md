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

To add missing Dynamic Routing subject and session IDs from S3 to Postgres:

```bash
uv run python scripts/update_db_from_s3.py --dry-run
uv run python scripts/update_db_from_s3.py
```

The script reads AWS credentials from the normal boto3 credential chain and
database settings from `.env` or `DR_DB_POSTGRES_*` environment variables. S3
session directories must be named `<subject_id>_<YYYYMMDD>` below a numeric
subject directory. Hyphenated `<YYYY-MM-DD>` dates are also accepted. Existing
subject/session rows are left unchanged.

To inventory each session's task-stim S3 path and rig ID in a temporary SQLite
database:

```bash
uv run --script scripts/export_session_rigs.py
```

The command reads the open S3 bucket anonymously and prints the output database
path. Its `session` table contains one row per `(subject_id, date)`; when
multiple task-data files exist for a day, the file with the latest filename
timestamp is used, and `task_filename` contains the selected task file name.
Rig-read failures are retained as rows with a null `rig_id`
and a `task_data_read_error`. An existing output database is reused, and
sessions already in its `session` table are skipped. Use `--limit` for a small
credential check or `--output` to choose the database path explicitly.
