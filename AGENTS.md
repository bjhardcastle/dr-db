## Purpose
Config, setup, scripts, scheduled tasks for data ingestion and backup, for the dynamic routing database and associated dashboard. 

## Sources
- current sources of truth are an unstrict spreadsheet completed by RAs `Ephys Experiment Tracking.xlsx`, and spreadsheets maintained by Sam which are converted into `DynamicRoutingTraining*.sqlite` dbs.

## Components
- a dev db for testing and development.
- a production db.
- scheduled backups of the production db.
- dbmate services for applying the shared `db/migrations` history to either database. test them on dev after syncing prod -> dev, then apply to prod.
- scheduled table exports prod -> parquet in open bucket at s3://aind-scratch-data/dynamic_routing/db.
- scheduled (or one-off) scripts to ingest new data.
- a dashboard with a spreadsheet-like interface for viewing and editing the data.
- a dashboard for users to write no-code schema update requests, implemented and tested by an agent before being applied to the production db.
- python dashboards for common tasks like "add new subject" which can fetch metadata from other sources and insert into prod db. dashboards are an interface for underlying functions in the dr-db python package that can be called programatically elsewhere. 

## Implementation notes 
- `postgres` and `postgres-dev` are separate Postgres 17 services with separate storage.
- `tools` profile services are used for one-off tasks like migrations, backups, syncing, and ingestion scripts.
- `docker.mathesar.yaml` runs Mathesar as `mathesar` + `mathesar-proxy`; Mathesar stores its own metadata in `mathesar-metadata` and connects to the production `postgres` service via the `dr-db` network alias.

## Rules
- make atomic commits as you go along.
- ignore session_config.py for now.
- keep architecture and infrastructure simple, someone else may have to maintain this in the future. Always look for ways to reduce complexity.
