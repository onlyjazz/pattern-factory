-- ============================================
-- PAT-138: Compute Assets Yearly Value
-- ============================================
-- Add yearly_value field and set proper defaults
-- Add trigger to compute yearly_value on update

BEGIN;

-- ============================================
-- 1. ADD yearly_value COLUMN
-- ============================================

ALTER TABLE threat.assets
    ADD COLUMN IF NOT EXISTS yearly_value INTEGER DEFAULT 0;

-- ============================================
-- 2. SET DEFAULTS FOR EXISTING COLUMNS
-- ============================================

ALTER TABLE threat.assets
    ALTER COLUMN fixed_value_period SET DEFAULT 12,
    ALTER COLUMN fixed_value SET DEFAULT 0,
    ALTER COLUMN recurring_value SET DEFAULT 0,
    ALTER COLUMN include_fixed_value SET DEFAULT true,
    ALTER COLUMN include_recurring_value SET DEFAULT true,
    ALTER COLUMN disabled SET DEFAULT false;

-- ============================================
-- 3. ADD tag AND version COLUMNS TO assets
-- ============================================

ALTER TABLE threat.assets
    ADD COLUMN IF NOT EXISTS tag TEXT,
    ADD COLUMN IF NOT EXISTS version TEXT;

-- ============================================
-- 4. ADD tag AND version COLUMNS TO countermeasures
-- ============================================

ALTER TABLE threat.countermeasures
    ADD COLUMN IF NOT EXISTS tag TEXT,
    ADD COLUMN IF NOT EXISTS version TEXT;

-- ============================================
-- 5. CREATE TRIGGER TO COMPUTE yearly_value
-- ============================================

CREATE OR REPLACE FUNCTION threat.compute_asset_yearly_value()
RETURNS TRIGGER AS $$
BEGIN
    -- Compute yearly value based on formula:
    -- yearly_value = fixed_value * (12/fixed_value_period) + recurring_value
    -- Handle edge case where fixed_value_period is 0 (should not happen due to defaults, but safe)
    IF NEW.fixed_value_period IS NULL OR NEW.fixed_value_period = 0 THEN
        NEW.yearly_value := COALESCE(NEW.recurring_value, 0);
    ELSE
        NEW.yearly_value := (COALESCE(NEW.fixed_value, 0) * 12 / NEW.fixed_value_period) + COALESCE(NEW.recurring_value, 0);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS asset_compute_yearly_value ON threat.assets;

-- Create trigger that fires BEFORE INSERT or UPDATE
CREATE TRIGGER asset_compute_yearly_value
BEFORE INSERT OR UPDATE ON threat.assets
FOR EACH ROW
EXECUTE FUNCTION threat.compute_asset_yearly_value();

-- ============================================
-- 6. COMPUTE yearly_value FOR EXISTING ROWS
-- ============================================

UPDATE threat.assets
SET 
    fixed_value_period = COALESCE(fixed_value_period, 12),
    fixed_value = COALESCE(fixed_value, 0),
    recurring_value = COALESCE(recurring_value, 0),
    include_fixed_value = COALESCE(include_fixed_value, true),
    include_recurring_value = COALESCE(include_recurring_value, true),
    disabled = COALESCE(disabled, false)
WHERE yearly_value IS NULL OR yearly_value = 0;

-- ============================================
-- 7. RECREATE vassets VIEW WITH NEW COLUMNS
-- ============================================

DROP VIEW IF EXISTS threat.vassets;
CREATE OR REPLACE VIEW threat.vassets AS
SELECT a.* FROM threat.assets a
    JOIN public.active_models am ON a.model_id = am.model_id
    WHERE am.user_id = ((SELECT id FROM public.users WHERE email = 'admin@opencro.com'));

COMMIT;
