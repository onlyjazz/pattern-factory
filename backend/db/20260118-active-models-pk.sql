--
-- Fix active_models table: change primary key from (user_id, model_id) to user_id only
-- This allows one active model per user and enables simple UPDATE operations
set search_path to public;

-- Drop the old primary key constraint
ALTER TABLE active_models DROP CONSTRAINT active_models_pkey;

-- Add new primary key on user_id only
ALTER TABLE active_models ADD PRIMARY KEY (user_id);

-- Add unique constraint on model_id foreign key if needed for referential integrity
-- (model_id will no longer be part of the primary key)
