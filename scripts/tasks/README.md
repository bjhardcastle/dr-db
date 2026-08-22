# Scheduled task wrappers

Files in this directory are executable, stable entry points for operations.
They should:

1. use `set -eu`;
2. resolve paths relative to the repository rather than the caller's directory;
3. accept explicit environment/configuration for machine-specific values; and
4. exit non-zero when the task fails.

Run one directly while developing:

```bash
./scripts/tasks/migrate-dev
```

Run one with locking, as cron does:

```bash
./scripts/run-task.sh migrate-dev
```

The existing wrappers cover migrations and production-to-development syncing.
Add future backup, parquet-export, or ingestion wrappers here. Do not put cron
syntax in this directory.
