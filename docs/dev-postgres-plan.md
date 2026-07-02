# Dev Postgres With Prod Clone Workflow

## Summary

Add a simple isolated dev Postgres service and an explicit one-command prod-to-dev clone workflow. Use logical `pg_dump`/`pg_restore`, so prod can stay running and dev can be safely overwritten without copying raw Postgres files.

## Key Changes

- Add `postgres-dev` to `compose.yml` with no Compose profile: same Postgres image as prod, host port `7501`, storage at `${DR_DB_STORAGE_ROOT}/postgres-dev`, database `dr_db_dev`, network alias `dr-db-dev`.
- Add `clone-prod-to-dev` as a short-lived tool service under the existing `tools` profile. Run it manually with `docker compose --profile tools run --rm clone-prod-to-dev`; it connects to `postgres`, overwrites only the dev database, and restores prod schema/data into dev.
- Update `.env.example` with dev DB variables: `DR_DB_DEV_POSTGRES_DB`, `DR_DB_DEV_POSTGRES_USER`, `DR_DB_DEV_POSTGRES_PASSWORD`, and `DR_DB_DEV_POSTGRES_HOST_PORT`.
- Update README with the dev start, clone, and connection commands.

## Public Interfaces

- New long-running service: `postgres-dev`.
- New manual tool service: `clone-prod-to-dev`.
- Dev connection:
  - from host: `localhost:${DR_DB_DEV_POSTGRES_HOST_PORT:-7501}`
  - from containers: `dr-db-dev:5432`
  - default db: `${DR_DB_DEV_POSTGRES_DB:-dr_db_dev}`

## Test Plan

- Run `docker compose config` on a Docker-enabled machine.
- Start dev with `docker compose up -d postgres-dev` and confirm healthcheck.
- Run `docker compose --profile tools run --rm clone-prod-to-dev`.
- Verify dev has expected schemas/tables and representative row counts match prod.
- Run `uv run pytest`.

## Assumptions

- Normal `docker compose up -d` may start both `postgres` and `postgres-dev`; use explicit service names when only one DB should run.
- Dev data is disposable and may be overwritten by the clone command.
- "Prod" means the existing `postgres` service unless overridden later.
- Runtime Docker validation must happen on a machine with Docker installed.
