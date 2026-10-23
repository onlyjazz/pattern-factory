/*
 * PAT-406: create the Close smart view once per experiment, not once per run.
 *
 * POST /experiments/{id}/start created a Close saved search on every call, so
 * re-running an experiment piled up duplicate smart views. The view describes
 * the experiment rather than any one run, so its id is stored here and reused
 * by later activations.
 *
 * Note: existing experiments have no recorded id, so each creates one more
 * smart view on its next activation and reuses that one from then on. Views
 * already created by earlier runs stay in Close untouched.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20261021-pat-406-experiment-close-smart-view-id.sql
 */

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.experiment
    ADD COLUMN IF NOT EXISTS close_smart_view_id TEXT;

COMMENT ON COLUMN public.experiment.close_smart_view_id IS
    'Close saved-search (smart view) id created for this experiment on first activation; reused by later runs so re-running does not create duplicates.';

COMMIT;
