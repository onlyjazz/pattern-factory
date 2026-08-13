-- =========================================================
-- Pattern Factory: Randomization Verification Queries
-- =========================================================
-- Run these queries to verify the stratified randomization
-- results after executing the randomize_orgs function or
-- running the Python randomization script.
--
-- Expected Results:
-- 1. All non-deleted orgs assigned to exactly one arm
-- 2. Within each tier, arms balanced to within ±1 org
-- 3. Overall distribution roughly 1/3 per arm
-- 4. All orgs have matching randomization_seed
-- 5. All orgs have randomized_at timestamp

-- =========================================================
-- QUERY 1: Overall Arm Distribution
-- =========================================================
-- Shows the count and percentage of orgs in each study arm.
-- Expected: ~33% each arm (some variation due to rounding)
--
SELECT
    study_arm,
    COUNT(*) AS org_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM public.orgs WHERE deleted_at IS NULL), 1) AS percentage,
    COUNT(*) FILTER (WHERE tier = 1) AS tier_1_count,
    COUNT(*) FILTER (WHERE tier = 2) AS tier_2_count,
    COUNT(*) FILTER (WHERE tier = 3) AS tier_3_count
FROM public.orgs
WHERE deleted_at IS NULL
GROUP BY study_arm
ORDER BY study_arm;

-- =========================================================
-- QUERY 2: Distribution by Tier and Arm
-- =========================================================
-- Shows how balanced the arms are within each tier.
-- Expected: Within each tier, all three arms have similar counts (±1 org)
--
SELECT
    tier,
    study_arm,
    COUNT(*) AS org_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM public.orgs WHERE deleted_at IS NULL AND tier = o.tier), 1) AS pct_of_tier
FROM public.orgs o
WHERE deleted_at IS NULL
GROUP BY tier, study_arm
ORDER BY tier, study_arm;

-- =========================================================
-- QUERY 3: Check for Unassigned Organizations
-- =========================================================
-- Should return 0 rows. If > 0, some orgs weren't assigned.
--
SELECT COUNT(*) AS unassigned_orgs
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NULL;

-- =========================================================
-- QUERY 4: Check for Duplicate Assignments
-- =========================================================
-- Should return 0 rows. If > 0, something went wrong with updates.
--
SELECT
    id,
    name,
    COUNT(*) AS assignment_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY id, name
HAVING COUNT(*) > 1;

-- =========================================================
-- QUERY 5: Verify Randomization Seed Consistency
-- =========================================================
-- All orgs should have the same randomization_seed.
-- Should return 1 row with seed value.
--
SELECT
    randomization_seed,
    COUNT(*) AS org_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY randomization_seed;

-- =========================================================
-- QUERY 6: Verify Randomized Timestamp
-- =========================================================
-- All orgs should have randomized_at timestamp.
-- Should return 1 row with recent timestamp.
--
SELECT
    randomized_at,
    COUNT(*) AS org_count
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY randomized_at
ORDER BY randomized_at DESC;

-- =========================================================
-- QUERY 7: Balance Check (Tier-Wise)
-- =========================================================
-- For each tier, shows max-min difference in arm sizes.
-- Expected: Difference should be ≤ 1 for all tiers.
--
WITH tier_arm_counts AS (
    SELECT
        tier,
        study_arm,
        COUNT(*) AS arm_count
    FROM public.orgs
    WHERE deleted_at IS NULL AND study_arm IS NOT NULL
    GROUP BY tier, study_arm
)
SELECT
    tier,
    MAX(arm_count) - MIN(arm_count) AS balance_difference,
    CASE
        WHEN MAX(arm_count) - MIN(arm_count) <= 1 THEN 'BALANCED ✓'
        ELSE 'IMBALANCED ✗'
    END AS status
FROM tier_arm_counts
GROUP BY tier
ORDER BY tier;

-- =========================================================
-- QUERY 8: Randomization Event Log
-- =========================================================
-- Shows the last randomization event logged in system_log.
--
SELECT
    id,
    event,
    context,
    created_at
FROM public.system_log
WHERE event = 'stratified_randomization_completed'
ORDER BY created_at DESC
LIMIT 1;

-- =========================================================
-- QUERY 9: Sample Organizations from Each Arm
-- =========================================================
-- Shows 5 sample orgs from each arm for manual inspection.
--
SELECT
    study_arm,
    name,
    tier,
    size,
    randomization_seed,
    randomized_at
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
ORDER BY study_arm, RANDOM()
LIMIT 15;

-- =========================================================
-- QUERY 10: Tier-wise Summary
-- =========================================================
-- Comprehensive summary showing counts and percentages by tier.
--
SELECT
    tier,
    COUNT(*) AS total_in_tier,
    COUNT(*) FILTER (WHERE study_arm = 'control') AS control,
    COUNT(*) FILTER (WHERE study_arm = 'treatment_1') AS treatment_1,
    COUNT(*) FILTER (WHERE study_arm = 'treatment_2') AS treatment_2,
    ROUND(100.0 * COUNT(*) FILTER (WHERE study_arm = 'control') / COUNT(*), 1) AS control_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE study_arm = 'treatment_1') / COUNT(*), 1) AS treatment_1_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE study_arm = 'treatment_2') / COUNT(*), 1) AS treatment_2_pct
FROM public.orgs
WHERE deleted_at IS NULL AND study_arm IS NOT NULL
GROUP BY tier
ORDER BY tier;

-- =========================================================
-- QUERY 11: Check for Null Values (Data Integrity)
-- =========================================================
-- Returns rows with NULL values in critical fields.
-- Should return 0 rows after successful randomization.
--
SELECT
    id,
    name,
    study_arm,
    randomization_seed,
    randomized_at
FROM public.orgs
WHERE deleted_at IS NULL
  AND (study_arm IS NULL OR randomization_seed IS NULL OR randomized_at IS NULL)
LIMIT 10;

-- =========================================================
-- QUERY 12: Final Verification Summary
-- =========================================================
-- One-line summary: Pass/Fail on all critical checks.
--
WITH checks AS (
    SELECT
        CASE WHEN COUNT(DISTINCT study_arm) = 3 THEN 'PASS' ELSE 'FAIL' END AS three_arms,
        CASE WHEN COUNT(*) FILTER (WHERE study_arm IS NULL) = 0 THEN 'PASS' ELSE 'FAIL' END AS all_assigned,
        CASE WHEN (MAX(CASE WHEN study_arm IN ('control', 'treatment_1', 'treatment_2') THEN 1 ELSE 0 END) = 1 AND COUNT(*) FILTER (WHERE study_arm NOT IN ('control', 'treatment_1', 'treatment_2')) = 0) THEN 'PASS' ELSE 'FAIL' END AS valid_arm_values,
        CASE WHEN COUNT(DISTINCT randomization_seed) = 1 THEN 'PASS' ELSE 'FAIL' END AS consistent_seed,
        CASE WHEN COUNT(DISTINCT randomized_at) = 1 THEN 'PASS' ELSE 'FAIL' END AS consistent_timestamp
    FROM public.orgs
    WHERE deleted_at IS NULL
)
SELECT
    three_arms,
    all_assigned,
    valid_arm_values,
    consistent_seed,
    consistent_timestamp,
    CASE WHEN three_arms = 'PASS' AND all_assigned = 'PASS' AND valid_arm_values = 'PASS' AND consistent_seed = 'PASS' AND consistent_timestamp = 'PASS' THEN 'ALL CHECKS PASSED ✓' ELSE 'SOME CHECKS FAILED ✗' END AS overall_status
FROM checks;
