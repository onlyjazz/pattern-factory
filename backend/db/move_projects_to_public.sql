-- =========================================================
-- Migration: Move projects from threat schema to public
-- Pattern Factory
-- Postgres ≥ 14
-- =========================================================

BEGIN;

-- =========================================================
-- 0. Safety checks (optional but recommended)
-- =========================================================
-- Ensure source table exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'threat'
          AND table_name = 'projects'
    ) THEN
        RAISE EXCEPTION 'threat.projects does not exist';
    END IF;
END $$;

-- =========================================================
-- 1. Create public.projects (id-preserving)
-- =========================================================

CREATE TABLE IF NOT EXISTS public.projects (
    id          INTEGER PRIMARY KEY,
    name        VARCHAR(255),
    version     VARCHAR(50),
    author      VARCHAR(255),
    company     VARCHAR(255),
    category    VARCHAR(255),
    keywords    TEXT,
    description TEXT
);

-- =========================================================
-- 2. Copy data (idempotent)
-- =========================================================

INSERT INTO public.projects (
    id, name, version, author, company, category, keywords, description
)
SELECT
    id, name, version, author, company, category, keywords, description
FROM threat.projects
ON CONFLICT (id) DO NOTHING;

-- =========================================================
-- 3. Drop all foreign keys pointing to threat.projects
-- =========================================================

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'threat.projects'::regclass
    )
    LOOP
        EXECUTE format(
            'ALTER TABLE %s DROP CONSTRAINT %I;',
            r.table_name,
            r.conname
        );
    END LOOP;
END $$;

-- =========================================================
-- 4. Recreate foreign keys → public.projects
-- =========================================================

-- Core entities
ALTER TABLE threat.threats
    ADD CONSTRAINT threats_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.assets
    ADD CONSTRAINT assets_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.vulnerabilities
    ADD CONSTRAINT vulnerabilities_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.countermeasures
    ADD CONSTRAINT countermeasures_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.entrypoints
    ADD CONSTRAINT entrypoints_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

-- Join tables
ALTER TABLE threat.pattern_threat
    ADD CONSTRAINT pattern_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.area_asset
    ADD CONSTRAINT area_asset_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.area_threat
    ADD CONSTRAINT area_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.area_vulnerability
    ADD CONSTRAINT area_vulnerability_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.area_countermeasure
    ADD CONSTRAINT area_countermeasure_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.asset_threat
    ADD CONSTRAINT asset_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.vulnerability_threat
    ADD CONSTRAINT vulnerability_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.countermeasure_threat
    ADD CONSTRAINT countermeasure_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.attacker_threat
    ADD CONSTRAINT attacker_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

ALTER TABLE threat.entrypoint_threat
    ADD CONSTRAINT entrypoint_threat_project_fk
    FOREIGN KEY (project_id)
    REFERENCES public.projects(id)
    ON DELETE CASCADE;

-- =========================================================
-- 5. Drop old table
-- =========================================================

DROP TABLE threat.projects;

-- =========================================================
-- 6. (Optional) Restore auto-increment behavior
-- =========================================================

CREATE SEQUENCE IF NOT EXISTS public.projects_id_seq;

SELECT setval(
    'public.projects_id_seq',
    COALESCE((SELECT MAX(id) FROM public.projects), 1)
);

ALTER TABLE public.projects
    ALTER COLUMN id
    SET DEFAULT nextval('public.projects_id_seq');

COMMIT;
