-- ============================================
-- Recreate vcountermeasures view to include yearly_cost
-- ============================================

BEGIN;

-- Drop and recreate the vcountermeasures view
-- to include the new yearly_cost column
DROP VIEW IF EXISTS threat.vcountermeasures;

CREATE VIEW threat.vcountermeasures AS
SELECT c.* 
FROM threat.countermeasures c
JOIN public.active_models am ON c.model_id = am.model_id
WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));

COMMIT;
