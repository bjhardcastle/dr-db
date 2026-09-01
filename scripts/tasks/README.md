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
The `export-prod-to-parquet` wrapper exports every non-system table using
`pg_parquet`; it defaults to `/var/lib/postgresql/parquet`, which is mounted at
`.data/parquet` by the Compose configuration. Set `PARQUET_OUTPUT_URI` to an
`s3://...` URI for an object-store export. Do not put cron syntax in this
directory.

The `test-postgres` wrapper starts or waits for `postgres-dev`, checks that
`pg_parquet` can write a Parquet file, and verifies that the export SQL emits
one file for every exportable dev table.
