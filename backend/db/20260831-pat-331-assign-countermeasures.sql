CREATE SEQUENCE IF NOT exists countermeasure_tag_seq START 1;
ALTER TABLE threat.countermeasure_class add column if not exists short_tag text;

UPDATE threat.countermeasure_class c
SET short_tag = (
    SELECT string_agg(left(word, 1), '')
    FROM unnest(string_to_array(c.tag, '_')) AS word
);
-- Pass
ALTER sequence countermeasure_tag_seq RESTART with 0;
UPDATE threat.countermeasures cm
SET tag =
    c.short_tag || '-' ||
    lpad(nextval('countermeasure_tag_seq')::text, 5, '0')
FROM threat.countermeasure_class c
WHERE cm.class_id = c.id
  AND cm.tag IS NULL;

  -- edge generation query

SELECT
    thr.model_id,
    tc.threat_id,
    cm.id AS countermeasure_id
FROM threat.countermeasure_class c
JOIN threat.threat_countermeasure_classes tc
    ON tc.class_id = c.id
JOIN threat.countermeasures cm
    ON cm.class_id = c.id
JOIN threat.threats thr
    ON thr.id = tc.threat_id
ORDER BY
    thr.model_id,
    tc.threat_id,
    cm.id;

DROP INDEX   IF EXISTS threat.idx_threats_project;
DROP INDEX   IF EXISTS threat.threats_model_tag_unique;
ALTER TABLE threat.threats DROP CONSTRAINT threats_model_tag_unique;

DROP INDEX   IF EXISTS threat.idx_threats_normalization_version;
DROP TRIGGER IF EXISTS threats_increment_version     ON threat.threats;
DROP TRIGGER IF EXISTS trg_insert_threat_mitigation  ON threat.threats;
DROP TRIGGER IF EXISTS trg_update_threat_mitigation  ON threat.threats;
DROP TRIGGER IF EXISTS update_threats_updated_at     ON threat.threats;

-- INSERT 0 241125
-- 12s after dropping triggers and 

select count(*) from
(
 SELECT
    thr.model_id,
    cm.id AS countermeasure_id,
    tc.threat_id
FROM threat.countermeasure_class c
JOIN threat.threat_countermeasure_classes tc
    ON tc.class_id = c.id
JOIN threat.countermeasures cm
    ON cm.class_id = c.id
JOIN threat.threats thr
    ON thr.id = tc.threat_id
ORDER BY
    thr.model_id,
    tc.threat_id,
    cm.id
    );   