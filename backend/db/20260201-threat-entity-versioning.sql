-- ============================================
-- Threat Entity Versioning & Card Parsing
-- ============================================
-- Add versioning and metadata fields to threat entities
-- Add version tracking to risk_history
-- Add version-increment triggers

BEGIN;

-- ============================================
-- 1. DROP THREAT OBSOLETE COLUMNS
-- ============================================

ALTER TABLE threat.threats
    DROP COLUMN IF EXISTS scenario CASCADE,
    DROP COLUMN IF EXISTS scenario_format CASCADE,
    DROP COLUMN IF EXISTS scenario_version CASCADE;

-- ============================================
-- 2. ADD VERSION & METADATA TO THREATS
-- ============================================

ALTER TABLE threat.threats
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS domain TEXT,
    ADD COLUMN IF NOT EXISTS tag TEXT;

-- ============================================
-- 3. ADD VERSION & TAG TO ASSETS
-- ============================================

ALTER TABLE threat.assets
    ADD COLUMN IF NOT EXISTS tag TEXT,
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- ============================================
-- 4. ADD VERSION TO VULNERABILITIES
-- ============================================

ALTER TABLE threat.vulnerabilities
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- ============================================
-- 5. ADD VERSION TO COUNTERMEASURES
-- ============================================

ALTER TABLE threat.countermeasures
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- ============================================
-- 6. UPDATE RISK_HISTORY TABLE
-- ============================================

ALTER TABLE threat.risk_history
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================
-- 7. CREATE VERSION-INCREMENT TRIGGERS
-- ============================================

-- Trigger function to increment version on update
CREATE OR REPLACE FUNCTION threat.increment_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version = COALESCE(OLD.version, 0) + 1;
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for threats table
DROP TRIGGER IF EXISTS threats_increment_version ON threat.threats;
CREATE TRIGGER threats_increment_version
BEFORE UPDATE ON threat.threats
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION threat.increment_version();

-- Trigger for assets table
DROP TRIGGER IF EXISTS assets_increment_version ON threat.assets;
CREATE TRIGGER assets_increment_version
BEFORE UPDATE ON threat.assets
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION threat.increment_version();

-- Trigger for vulnerabilities table
DROP TRIGGER IF EXISTS vulnerabilities_increment_version ON threat.vulnerabilities;
CREATE TRIGGER vulnerabilities_increment_version
BEFORE UPDATE ON threat.vulnerabilities
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION threat.increment_version();

-- Trigger for countermeasures table
DROP TRIGGER IF EXISTS countermeasures_increment_version ON threat.countermeasures;
CREATE TRIGGER countermeasures_increment_version
BEFORE UPDATE ON threat.countermeasures
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION threat.increment_version();

-- Create views that show threats, vulnerabilities, and countermeasures for the active model and the admin user
DROP view if exists threat.vthreats;
CREATE or REPLACE view threat.vthreats as
SELECT t.* from threat.threats t
    JOIN public.active_models am ON t.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP view if exists threat.vvulnerabilities;
CREATE or REPLACE view threat.vvulnerabilities as
SELECT v.* from threat.vulnerabilities v
    JOIN public.active_models am ON v.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP view if exists threat.vcountermeasures;
CREATE or REPLACE view threat.vcountermeasures as
SELECT c.* from threat.countermeasures c
    JOIN public.active_models am ON c.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));
--
DROP view if exists threat.vassets;
CREATE or REPLACE view threat.vassets as
SELECT a.* from threat.assets a
    JOIN public.active_models am ON a.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));


COMMIT;
