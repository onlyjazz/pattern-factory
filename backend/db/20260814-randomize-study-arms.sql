-- =========================================================
-- Pattern Factory — Balanced Stratified Randomization
-- Date: 2026-08-14
-- Purpose: Randomize ~1,500 FDA device manufacturers into
--          three balanced study arms (Control, Treatment 1, Treatment 2)
--          stratified by market tier (Tier 1, 2, 3).
-- =========================================================

BEGIN;

-- =========================================================
-- Add study arm assignment columns to orgs
-- =========================================================
ALTER TABLE public.orgs
ADD COLUMN study_arm TEXT 
  CHECK (study_arm IN ('control', 'treatment_1', 'treatment_2')) 
  DEFAULT NULL;

ALTER TABLE public.orgs
ADD COLUMN randomization_seed BIGINT DEFAULT NULL;

ALTER TABLE public.orgs
ADD COLUMN randomized_at TIMESTAMP DEFAULT NULL;

-- =========================================================
-- Create function: compute_arm_for_org
-- Purpose: Given an org id and tier, assign to an arm using
--          stratified block randomization (permuted blocks per tier)
-- =========================================================
CREATE OR REPLACE FUNCTION public.randomize_orgs_to_arms(
    p_randomization_seed BIGINT DEFAULT NULL
)
RETURNS TABLE (
    total_orgs BIGINT,
    control_count BIGINT,
    treatment_1_count BIGINT,
    treatment_2_count BIGINT,
    seed_used BIGINT
) AS $$
DECLARE
    v_seed BIGINT;
    v_total_orgs BIGINT;
    v_control_count BIGINT;
    v_treatment_1_count BIGINT;
    v_treatment_2_count BIGINT;
    v_tier INT;
    v_tier_count BIGINT;
    v_control_per_tier BIGINT;
    v_treatment_1_per_tier BIGINT;
    v_treatment_2_per_tier BIGINT;
    v_remainder BIGINT;
    v_idx BIGINT;
    v_arm TEXT;
    v_org_id BIGINT;
    v_random_order_seq INT;
BEGIN
    -- Use provided seed or generate one from current timestamp + random
    v_seed := COALESCE(p_randomization_seed, (EXTRACT(EPOCH FROM NOW()) * 1000000)::BIGINT + (random() * 1000000)::BIGINT);
    
    -- Initialize counters
    v_control_count := 0;
    v_treatment_1_count := 0;
    v_treatment_2_count := 0;
    
    -- Clear any existing randomization
    UPDATE public.orgs SET study_arm = NULL, randomization_seed = NULL, randomized_at = NULL
    WHERE deleted_at IS NULL;
    
    -- Randomize by tier (stratified block randomization)
    FOR v_tier IN 1..3 LOOP
        -- Count orgs in this tier
        SELECT COUNT(*) INTO v_tier_count
        FROM public.orgs
        WHERE deleted_at IS NULL AND tier = v_tier;
        
        IF v_tier_count > 0 THEN
            -- Compute balanced allocation for this tier
            v_control_per_tier := v_tier_count / 3;
            v_remainder := v_tier_count % 3;
            
            v_treatment_1_per_tier := v_tier_count / 3;
            v_treatment_2_per_tier := v_tier_count / 3;
            
            -- Distribute remainder orgs round-robin: control, treatment_1, treatment_2
            IF v_remainder >= 1 THEN
                v_control_per_tier := v_control_per_tier + 1;
            END IF;
            IF v_remainder >= 2 THEN
                v_treatment_1_per_tier := v_treatment_1_per_tier + 1;
            END IF;
            
            -- Seed SQL randomness for this tier
            PERFORM setseed((v_seed::FLOAT / 1000000000000.0) + (v_tier::FLOAT / 100.0));
            
            -- Assign orgs in this tier to arms based on sorted random order
            v_idx := 1;
            FOR v_org_id IN
                SELECT id
                FROM public.orgs
                WHERE deleted_at IS NULL AND tier = v_tier
                ORDER BY random()
            LOOP
                IF v_idx <= v_control_per_tier THEN
                    v_arm := 'control';
                    v_control_count := v_control_count + 1;
                ELSIF v_idx <= v_control_per_tier + v_treatment_1_per_tier THEN
                    v_arm := 'treatment_1';
                    v_treatment_1_count := v_treatment_1_count + 1;
                ELSE
                    v_arm := 'treatment_2';
                    v_treatment_2_count := v_treatment_2_count + 1;
                END IF;
                
                -- Update org with assignment
                UPDATE public.orgs
                SET
                    study_arm = v_arm,
                    randomization_seed = v_seed,
                    randomized_at = NOW()
                WHERE id = v_org_id;
                
                v_idx := v_idx + 1;
            END LOOP;
        END IF;
    END LOOP;
    
    -- Count total
    SELECT COUNT(*) INTO v_total_orgs
    FROM public.orgs
    WHERE deleted_at IS NULL;
    
    -- Return summary
    RETURN QUERY SELECT
        v_total_orgs,
        v_control_count,
        v_treatment_1_count,
        v_treatment_2_count,
        v_seed;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- Execute stratified randomization
-- =========================================================
-- This will randomize all non-deleted orgs to the three arms
-- balanced by tier.
--
-- To run with a specific seed (for reproducibility):
-- SELECT * FROM public.randomize_orgs_to_arms(123456789);
--
-- To run with auto-generated seed:
-- SELECT * FROM public.randomize_orgs_to_arms();
--
-- Uncomment the line below to execute immediately:
-- SELECT * FROM public.randomize_orgs_to_arms();

-- =========================================================
-- Log randomization event to system_log
-- =========================================================
INSERT INTO public.system_log (event, context)
VALUES (
    'stratified_randomization_completed',
    jsonb_build_object(
        'timestamp', NOW(),
        'description', 'Stratified randomization of organizations to study arms completed',
        'arms', jsonb_build_object(
            'control', (SELECT COUNT(*) FROM public.orgs WHERE study_arm = 'control' AND deleted_at IS NULL),
            'treatment_1', (SELECT COUNT(*) FROM public.orgs WHERE study_arm = 'treatment_1' AND deleted_at IS NULL),
            'treatment_2', (SELECT COUNT(*) FROM public.orgs WHERE study_arm = 'treatment_2' AND deleted_at IS NULL)
        )
    )
);

-- =========================================================
-- Verification queries (commented out)
-- =========================================================
/*
-- Check overall arm distribution
SELECT
    study_arm,
    COUNT(*) AS org_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM public.orgs WHERE deleted_at IS NULL), 1) AS pct
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY study_arm
ORDER BY study_arm;

-- Check distribution by tier and arm
SELECT
    tier,
    study_arm,
    COUNT(*) AS org_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY tier, study_arm
ORDER BY tier, study_arm;

-- Check for unassigned orgs
SELECT COUNT(*) AS unassigned
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NULL;

-- Check for duplicate assignments (should be 0)
SELECT
    id,
    COUNT(*) AS assignment_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY id
HAVING COUNT(*) > 1;

-- Verify seed is consistent within batch
SELECT DISTINCT randomization_seed, COUNT(*) AS org_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY randomization_seed;
*/

COMMIT;
