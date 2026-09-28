-- PAT-378: track an organization's name before it was acquired/renamed.
--
-- The ORG_STATUS flow (backend/pitboss/org_status.py) renames an org to the
-- latest operating company name reported by the Exa agent when its status is
-- 'acquired' or 'renamed', and preserves the prior name here. Across successive
-- acquisitions the earliest name is retained (COALESCE keeps the first value).

ALTER TABLE public.orgs
    ADD COLUMN IF NOT EXISTS name_before_acquisition text;
