-- ============================================
-- Data Cleanup: People and Organizations
-- ============================================

-- First, create missing organizations
INSERT INTO public.orgs (name, created_at, updated_at)
VALUES 
    ('Precision Oncology Alliance at Caris Life Sciences', now(), now()),
    ('Natera', now(), now()),
    ('Carolina Lemke Berlin', now(), now()),
    ('Rapaport Group', now(), now())
ON CONFLICT (name) DO NOTHING;

-- Update people table with correct org assignments
-- Yann Gaston-Mathé → Iktos (id 1)
UPDATE public.people
SET org_id = 1
WHERE name = 'Yann Gaston-Mathé';

-- James Hamrick → Precision Oncology Alliance at Caris Life Sciences
UPDATE public.people
SET org_id = (SELECT id FROM public.orgs WHERE name = 'Precision Oncology Alliance at Caris Life Sciences' LIMIT 1)
WHERE name = 'James Hamrick';

-- Aaron Brouser → Natera
UPDATE public.people
SET org_id = (SELECT id FROM public.orgs WHERE name = 'Natera' LIMIT 1)
WHERE name = 'Aaron Brouser';

-- Tim O'Connell → Emtelligent (id 4)
UPDATE public.people
SET org_id = 4
WHERE name = 'Tim O''Connell';

-- Bar Rafaelli → Carolina Lemke Berlin
UPDATE public.people
SET org_id = (SELECT id FROM public.orgs WHERE name = 'Carolina Lemke Berlin' LIMIT 1)
WHERE name = 'Bar Rafaeli';

-- Martin Rapaport → Rapaport Group
UPDATE public.people
SET org_id = (SELECT id FROM public.orgs WHERE name = 'Rapaport Group' LIMIT 1)
WHERE name = 'Martin Rapaport';

-- Fix Aaron Brauser (note the spelling) - remove incorrect org_id 3
UPDATE public.people
SET org_id = NULL
WHERE name = 'Aaron Brauser';

-- Log the cleanup operation
INSERT INTO public.system_log (event, context, created_at)
VALUES (
    'people_data_cleanup_completed',
    jsonb_build_object(
        'action', 'cleaned up people-org relationships and created missing organizations',
        'organizations_created', 4,
        'people_updated', 7,
        'timestamp', now()
    ),
    now()
);
