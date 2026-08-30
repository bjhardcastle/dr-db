\if :{?output_uri}
\else
    \echo 'output_uri must be supplied with psql -v output_uri=...'
    \quit 2
\endif

SELECT set_config('dr_db.export_output_uri', :'output_uri', false);

DO $$
DECLARE
    table_to_export record;
    base_uri text := current_setting('dr_db.export_output_uri');
    table_uri text;
    exported_tables integer := 0;
BEGIN
    FOR table_to_export IN
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'p')
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            AND n.nspname NOT LIKE 'pg_%'
        ORDER BY n.nspname, c.relname
    LOOP
        table_uri := rtrim(base_uri, '/') || '/'
            || table_to_export.schema_name || '.'
            || table_to_export.table_name || '.parquet';

        RAISE NOTICE 'Exporting %.% to %',
            table_to_export.schema_name,
            table_to_export.table_name,
            table_uri;

        EXECUTE format(
            'COPY (SELECT * FROM %I.%I) TO %L WITH (format parquet)',
            table_to_export.schema_name,
            table_to_export.table_name,
            table_uri
        );
        exported_tables := exported_tables + 1;
    END LOOP;

    RAISE NOTICE 'Exported % tables.', exported_tables;
END
$$;
