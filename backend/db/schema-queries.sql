-- FAQ queries on the information schema
-- Views
SELECT
    '- ' || t.table_name || ' (' || string_agg(c.column_name::text, ', ' ORDER BY c.ordinal_position) || ')' AS view_with_columns
FROM
    information_schema.tables t
JOIN
    information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
WHERE
    t.table_schema = 'public' -- Replace 'public' with your desired schema name if different
    AND t.table_type = 'VIEW' -- Filter specifically for views
GROUP BY
    t.table_name
ORDER BY
    t.table_name;

-- Tables
SELECT
    '- ' || t.table_name || ' (' || string_agg(c.column_name::text, ', ' ORDER BY c.ordinal_position) || ')' AS table_with_columns
FROM
    information_schema.tables t
JOIN
    information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
WHERE
    t.table_schema = 'public' -- Replace 'public' with your desired schema name if different
    AND t.table_type = 'BASE TABLE' -- Filter specifically for tables
GROUP BY
    t.table_name
ORDER BY
    t.table_name;
