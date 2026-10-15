-- ============================================
-- PAT-380: Experiment hypothesis and target fields
-- ============================================
-- Promotes the Hypothesis and Target lines that were being written into
-- public.experiment.description into first-class columns, so they can be
-- authored and read as their own fields on the experiment add/edit pages.
--
-- Both columns are nullable with no default: existing rows keep their current
-- values and nothing needs backfilling.

-- ---------------------------------------------------------------------------
-- experiment: reusable cross-channel outreach template
-- ---------------------------------------------------------------------------
ALTER TABLE public.experiment
    ADD COLUMN IF NOT EXISTS hypothesis TEXT,
    ADD COLUMN IF NOT EXISTS target TEXT;
