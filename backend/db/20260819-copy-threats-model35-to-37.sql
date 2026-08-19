-- Migration: Copy threats from model_id=35 to model_id=37 (Canonical to Canonical V2)
-- Purpose: Bootstrap Canonical V2 threat set for normalization pass (Cycle-3)
-- Date: 2026-08-19

BEGIN;

-- Step 1: Verify baseline counts
SELECT COUNT(*) as threats_model_35 FROM threat.threats WHERE model_id = 35;
SELECT COUNT(*) as threats_model_37_before FROM threat.threats WHERE model_id = 37;

-- Step 2: Copy all threats from model_id=35 to model_id=37
INSERT INTO threat.threats (
    model_id,
    name,
    description,
    damage_description,
    probability,
    domain,
    tag,
    spoofing,
    tampering,
    repudiation,
    information_disclosure,
    denial_of_service,
    elevation_of_privilege,
    mitigation_level,
    disabled,
    card_id,
    version,
    created_at,
    updated_at
)
SELECT
    37 as model_id,
    name,
    description,
    damage_description,
    probability,
    domain,
    tag,
    spoofing,
    tampering,
    repudiation,
    information_disclosure,
    denial_of_service,
    elevation_of_privilege,
    mitigation_level,
    disabled,
    card_id,
    1 as version,
    NOW() as created_at,
    NOW() as updated_at
FROM threat.threats
WHERE model_id = 35
ORDER BY id;

-- Step 3: Verify copy success
SELECT COUNT(*) as threats_model_37_after FROM threat.threats WHERE model_id = 37;

-- Step 4: Verify data integrity (sample 5 threats)
SELECT 
    id,
    name,
    model_id,
    version,
    domain,
    created_at
FROM threat.threats
WHERE model_id = 37
ORDER BY RANDOM()
LIMIT 5;

COMMIT;
