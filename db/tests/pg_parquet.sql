\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_extension
        WHERE extname = 'pg_parquet'
    ) THEN
        RAISE EXCEPTION 'pg_parquet extension is not installed';
    END IF;

    IF position('pg_parquet' IN current_setting('shared_preload_libraries')) = 0 THEN
        RAISE EXCEPTION 'pg_parquet is not in shared_preload_libraries';
    END IF;
END
$$;

BEGIN;

CREATE TEMP TABLE pg_parquet_test (
    id integer,
    label text,
    amount double precision
);

INSERT INTO pg_parquet_test (id, label, amount)
VALUES
    (1, 'one', 1.5),
    (2, 'two', 2.5);

COPY (
    SELECT id, label, amount
    FROM pg_parquet_test
    ORDER BY id
) TO '/tmp/dr-db-pg-parquet-test.parquet' WITH (format parquet);

DO $$
DECLARE
    field_count integer;
BEGIN
    SELECT count(*)
    INTO field_count
    FROM parquet.schema('/tmp/dr-db-pg-parquet-test.parquet')
    WHERE name <> 'arrow_schema';

    IF field_count <> 3 THEN
        RAISE EXCEPTION 'expected 3 exported fields, found %', field_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM parquet.schema('/tmp/dr-db-pg-parquet-test.parquet')
        WHERE name = 'label' AND converted_type = 'UTF8'
    ) THEN
        RAISE EXCEPTION 'exported Parquet schema is missing the text field';
    END IF;
END
$$;

ROLLBACK;
