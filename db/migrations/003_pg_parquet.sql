-- migrate:up

CREATE EXTENSION IF NOT EXISTS pg_parquet;

-- migrate:down

DROP EXTENSION IF EXISTS pg_parquet;
