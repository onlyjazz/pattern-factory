-- FAQ queries on the information schema
-- Views
DROP VIEW IF EXISTS public.information_schema_view;
CREATE OR REPLACE VIEW public.information_schema_view AS
SELECT
    t.table_name,t.table_type,t.table_schema,
    t.table_name || ' (' || string_agg(c.column_name::text, ', ' ORDER BY c.ordinal_position) || ')' AS view_with_columns
FROM
    information_schema.tables t
JOIN
    information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema

GROUP BY
    t.table_name, t.table_type
ORDER BY
    t.table_name;

-- Tables
SELECT
    t.table_name,t.table_type,t.table_schema,
    t.table_name || ' (' || string_agg(c.column_name::text, ', ' ORDER BY c.ordinal_position) || ')' AS table_with_columns
FROM
    information_schema.tables t
JOIN
    information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
GROUP BY
    t.table_name, t.table_type
ORDER BY
    t.table_name;
