-- PAT-330 Integration Test: Threat Classification E2E Query Chain
-- Verifies threat -> class -> countermeasures relationship works correctly

-- Test 1: Verify countermeasure_class table is populated
SELECT 'Test 1: Count countermeasure classes' AS test_name;
SELECT COUNT(*) as class_count FROM threat.countermeasure_class;
SELECT * FROM threat.countermeasure_class LIMIT 3;

-- Test 2: Verify all countermeasures have class_id assigned
SELECT 'Test 2: Countermeasure class assignments' AS test_name;
SELECT 
    COUNT(*) as total_countermeasures,
    COUNT(CASE WHEN class_id IS NOT NULL THEN 1 END) as with_class_id,
    COUNT(CASE WHEN class_id IS NULL THEN 1 END) as without_class_id
FROM threat.countermeasures;

-- Test 3: Count threats per class (should initially be empty since no classifications yet)
SELECT 'Test 3: Threats per class (before classification)' AS test_name;
SELECT 
    cc.tag,
    COUNT(DISTINCT tcc.threat_id) as threat_count
FROM threat.countermeasure_class cc
LEFT JOIN threat.threat_countermeasure_classes tcc ON cc.id = tcc.class_id
GROUP BY cc.id, cc.tag
ORDER BY threat_count DESC;

-- Test 4: Verify the join query works (threat -> class -> countermeasures)
SELECT 'Test 4: Threat to countermeasures query chain' AS test_name;
-- After classification, this should return countermeasures for a threat
-- Example: SELECT cm.* FROM threat.countermeasures cm
-- JOIN threat.countermeasure_class cc ON cm.class_id = cc.id
-- JOIN threat.threat_countermeasure_classes tcc ON tcc.class_id = cc.id
-- WHERE tcc.threat_id = 1;

-- For now, just verify the FK relationships exist
SELECT 
    t.name 'table_name',
    c.constraint_name,
    c.constraint_type
FROM information_schema.tables t
LEFT JOIN information_schema.constraint_column_usage ccu ON t.table_name = ccu.table_name
LEFT JOIN information_schema.table_constraints c ON c.table_name = t.table_name AND c.constraint_name = ccu.constraint_name
WHERE t.table_schema = 'threat' AND t.table_name IN ('threat_countermeasure_classes', 'countermeasure_class', 'countermeasures')
ORDER BY t.table_name, c.constraint_name;

-- Test 5: Sample countermeasures with their classes
SELECT 'Test 5: Sample countermeasures with classes' AS test_name;
SELECT 
    cm.id,
    cm.name,
    cc.tag,
    cc.class
FROM threat.countermeasures cm
LEFT JOIN threat.countermeasure_class cc ON cm.class_id = cc.id
LIMIT 10;

-- Summary
SELECT 'Summary: PAT-330 Integration Test' AS test_name;
SELECT 
    'Total countermeasure classes' AS metric,
    COUNT(*) AS value
FROM threat.countermeasure_class
UNION ALL
SELECT 
    'Countermeasures with class_id',
    COUNT(*)
FROM threat.countermeasures
WHERE class_id IS NOT NULL
UNION ALL
SELECT 
    'Threat classifications (pre-classification)',
    COUNT(*)
FROM threat.threat_countermeasure_classes
ORDER BY value DESC;
