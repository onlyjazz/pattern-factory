-- Migration: Add UNIQUE constraint on table_name in views_registry
-- This allows UPSERT operations to update existing view entries when re-running rules

ALTER TABLE views_registry
ADD CONSTRAINT views_registry_table_name_key UNIQUE (table_name);
