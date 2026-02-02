-- ============================================
-- PAT-116: Compute Countermeasures Cost
-- ============================================
-- Add yearly_cost field and set proper defaults
-- Add trigger to compute yearly_cost on update

BEGIN;

-- ============================================
-- 1. ADD yearly_cost COLUMN
-- ============================================

ALTER TABLE threat.countermeasures
    ADD COLUMN IF NOT EXISTS yearly_cost INTEGER DEFAULT 0;

-- ============================================
-- 2. SET DEFAULTS FOR EXISTING COLUMNS
-- ============================================

ALTER TABLE threat.countermeasures
    ALTER COLUMN fixed_cost_period SET DEFAULT 12,
    ALTER COLUMN fixed_implementation_cost SET DEFAULT 0,
    ALTER COLUMN recurring_implementation_cost SET DEFAULT 0,
    ALTER COLUMN include_fixed_cost SET DEFAULT true,
    ALTER COLUMN include_recurring_cost SET DEFAULT true,
    ALTER COLUMN disabled SET DEFAULT false,
    ALTER COLUMN implemented SET DEFAULT false;

-- ============================================
-- 3. CREATE TRIGGER TO COMPUTE yearly_cost
-- ============================================

CREATE OR REPLACE FUNCTION threat.compute_countermeasure_yearly_cost()
RETURNS TRIGGER AS $$
BEGIN
    -- Compute yearly cost based on formula:
    -- yearly_cost = fixed_implementation_cost * (12/fixed_cost_period) + recurring_implementation_cost
    -- Handle edge case where fixed_cost_period is 0 (should not happen due to defaults, but safe)
    IF NEW.fixed_cost_period IS NULL OR NEW.fixed_cost_period = 0 THEN
        NEW.yearly_cost := COALESCE(NEW.recurring_implementation_cost, 0);
    ELSE
        NEW.yearly_cost := (COALESCE(NEW.fixed_implementation_cost, 0) * 12 / NEW.fixed_cost_period) + COALESCE(NEW.recurring_implementation_cost, 0);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS countermeasure_compute_yearly_cost ON threat.countermeasures;

-- Create trigger that fires BEFORE INSERT or UPDATE
CREATE TRIGGER countermeasure_compute_yearly_cost
BEFORE INSERT OR UPDATE ON threat.countermeasures
FOR EACH ROW
EXECUTE FUNCTION threat.compute_countermeasure_yearly_cost();

-- ============================================
-- 4. COMPUTE yearly_cost FOR EXISTING ROWS
-- ============================================

UPDATE threat.countermeasures
SET 
    fixed_cost_period = COALESCE(fixed_cost_period, 12),
    fixed_implementation_cost = COALESCE(fixed_implementation_cost, 0),
    recurring_implementation_cost = COALESCE(recurring_implementation_cost, 0),
    include_fixed_cost = COALESCE(include_fixed_cost, true),
    include_recurring_cost = COALESCE(include_recurring_cost, true),
    disabled = COALESCE(disabled, false),
    implemented = COALESCE(implemented, false)
WHERE yearly_cost IS NULL OR yearly_cost = 0;

COMMIT;
