--
-- Add created_at and updated_at columns to threat tables
alter table threat.vulnerabilities add column if not exists created_at timestamp with time zone default now();
alter table threat.vulnerabilities add column if not exists updated_at timestamp with time zone default now();

alter table threat.countermeasures add column if not exists created_at timestamp with time zone default now();
alter table threat.countermeasures add column if not exists updated_at timestamp with time zone default now();

alter table threat.models add column if not exists created_at timestamp with time zone default now();
alter table threat.models add column if not exists updated_at timestamp with time zone default now();

alter table public.active_models add column if not exists created_at timestamp with time zone default now();
alter table public.active_models add column if not exists updated_at timestamp with time zone default now();

--
-- Create views that show threats, vulnerabilities, and countermeasures for the active model and the admin user
DROP VIEW IF EXISTS threat.vthreats;
CREATE or REPLACE view threat.vthreats as
SELECT t.* from threat.threats t
    JOIN public.active_models am ON t.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP VIEW IF EXISTS threat.vvulnerabilities;
CREATE or REPLACE view threat.vvulnerabilities as
SELECT v.* from threat.vulnerabilities v
    JOIN public.active_models am ON v.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP VIEW IF EXISTS threat.vcountermeasures;
CREATE or REPLACE view threat.vcountermeasures as
SELECT c.* from threat.countermeasures c
    JOIN public.active_models am ON c.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP VIEW IF EXISTS threat.vassets;
CREATE or REPLACE view threat.vassets as
SELECT a.* from threat.assets a
    JOIN public.active_models am ON a.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));

--
CREATE OR REPLACE TRIGGER update_active_models_updated_at
BEFORE UPDATE ON public.active_models
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();

    