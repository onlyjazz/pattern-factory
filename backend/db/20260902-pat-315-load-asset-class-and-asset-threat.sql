/*
 * Cycle 5: load asset-class taxonomy and materialize asset-threat relationships.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/load-asset-class-and-asset-threat.sql
 *
 * Requirements:
 *   - jq and base64 are available on the machine running psql.
 *   - taxonomy-assets-v3.json is at the path below.
 *   - threat.countermeasure_class contains the canonical class rows in
 *     columns (id, class).
 *   - model assets use A1..A8 in threat.assets.tag.
 *
 * If the countermeasure-class table has a different name, change only the
 * class_table variable below.
 */

\set ON_ERROR_STOP on
\set taxonomy_path '/Users/dl/code/pattern-factory/backend/db/taxonomy-assets-v3.json'
\set class_table threat.countermeasure_class

BEGIN;


/*
 * SLE is the explicit valuation basis for the new fixed asset taxonomy.
 * The SLE-view migration repeats this operation idempotently.
 */
ALTER TABLE threat.assets
    ADD COLUMN IF NOT EXISTS sle_value NUMERIC(15,2);

UPDATE threat.assets
SET sle_value = COALESCE(yearly_value, 0)
WHERE sle_value IS NULL;

ALTER TABLE threat.assets
    ALTER COLUMN sle_value SET DEFAULT 0,
    ALTER COLUMN sle_value SET NOT NULL;


/*
 * 1. Persistent asset-to-class mapping.
 */
CREATE TABLE IF NOT EXISTS threat.asset_class (
    asset_taxonomy_id TEXT NOT NULL,
    class_id INTEGER NOT NULL,
    damage INTEGER NOT NULL CHECK (damage BETWEEN 0 AND 100),
    PRIMARY KEY (asset_taxonomy_id, class_id)
);


/*
 * 2. Read the local JSON through psql.
 *
 * Base64 protects JSON backslashes and other characters from COPY text-mode
 * escaping. FROM PROGRAM runs on the psql client machine.
 */
CREATE TEMP TABLE _asset_taxonomy_source (
    payload_base64 TEXT NOT NULL
) ON COMMIT DROP;

\copy _asset_taxonomy_source(payload_base64) FROM PROGRAM 'jq -c . "/Users/dl/code/pattern-factory/backend/db/taxonomy-assets-v3.json" | base64 | tr -d "\n"'

CREATE TEMP TABLE _asset_class_stage
ON COMMIT DROP
AS
SELECT
    asset.value ->> 'id' AS asset_taxonomy_id,
    relationship.value ->> 'class_name' AS class_name,
    (relationship.value ->> 'damage')::INTEGER AS damage
FROM _asset_taxonomy_source source
CROSS JOIN LATERAL jsonb_array_elements(
    (
        convert_from(
            decode(source.payload_base64, 'base64'),
            'UTF8'
        )::JSONB
    ) -> 'assets'
) AS asset(value)
CROSS JOIN LATERAL jsonb_array_elements(
    asset.value -> 'countermeasure_classes'
) AS relationship(value);

CREATE TEMP TABLE _asset_taxonomy_stage
ON COMMIT DROP
AS
SELECT
    asset.value ->> 'id' AS asset_taxonomy_id,
    asset.value ->> 'name' AS asset_name,
    asset.value ->> 'description' AS asset_description,
    (asset.value ->> 'valuation_percentage')::NUMERIC
        AS valuation_percentage
FROM _asset_taxonomy_source source
CROSS JOIN LATERAL jsonb_array_elements(
    (
        convert_from(
            decode(source.payload_base64, 'base64'),
            'UTF8'
        )::JSONB
    ) -> 'assets'
) AS asset(value);


/*
 * Validation: malformed rows, duplicate relationships and unresolved class
 * names must stop the migration rather than silently producing partial data.
 */
SELECT *
FROM _asset_class_stage
WHERE asset_taxonomy_id IS NULL
   OR class_name IS NULL
   OR damage IS NULL
   OR damage NOT BETWEEN 0 AND 100;

CREATE TEMP TABLE _asset_class_validation (
    valid BOOLEAN NOT NULL CHECK (valid)
) ON COMMIT DROP;

INSERT INTO _asset_class_validation(valid)
SELECT NOT EXISTS (
    SELECT 1
    FROM _asset_class_stage
    WHERE asset_taxonomy_id IS NULL
       OR class_name IS NULL
       OR damage IS NULL
       OR damage NOT BETWEEN 0 AND 100
);

SELECT
    asset_taxonomy_id,
    class_name,
    COUNT(*) AS duplicate_count
FROM _asset_class_stage
GROUP BY asset_taxonomy_id, class_name
HAVING COUNT(*) > 1;

INSERT INTO _asset_class_validation(valid)
SELECT NOT EXISTS (
    SELECT 1
    FROM _asset_class_stage
    GROUP BY asset_taxonomy_id, class_name
    HAVING COUNT(*) > 1
);

SELECT
    stage.asset_taxonomy_id,
    stage.class_name
FROM _asset_class_stage stage
LEFT JOIN :class_table cc
    ON cc.class = stage.class_name
WHERE cc.id IS NULL
ORDER BY stage.asset_taxonomy_id, stage.class_name;

INSERT INTO _asset_class_validation(valid)
SELECT NOT EXISTS (
    SELECT 1
    FROM _asset_class_stage stage
    LEFT JOIN :class_table cc
        ON cc.class = stage.class_name
    WHERE cc.id IS NULL
);


/*
 * Resolve canonical names to database IDs and upsert all 84 relationships.
 */
INSERT INTO threat.asset_class (
    asset_taxonomy_id,
    class_id,
    damage
)
SELECT
    stage.asset_taxonomy_id,
    cc.id,
    stage.damage
FROM _asset_class_stage stage
INNER JOIN :class_table cc
    ON cc.class = stage.class_name
ON CONFLICT (asset_taxonomy_id, class_id)
DO UPDATE
SET damage = EXCLUDED.damage;


/*
 * 3. Materialize the eight taxonomy assets for every model.
 *
 * orgs.size is the precomputed valuation basis. A model without a resolvable
 * product or organization still receives all eight assets with sle_value = 0;
 * those models are reported by the validation query below.
 */
INSERT INTO threat.assets (
    model_id,
    tag,
    name,
    description,
    sle_value,
    disabled
)
SELECT
    model.id::INTEGER,
    taxonomy.asset_taxonomy_id,
    taxonomy.asset_name,
    taxonomy.asset_description,
    ROUND(
        COALESCE(org.size, 0)::NUMERIC
        * taxonomy.valuation_percentage
        / 100.0,
        2
    ) AS sle_value,
    false
FROM threat.models model
LEFT JOIN public.products product
    ON product.id = model.product_id
LEFT JOIN public.orgs org
    ON org.id = product.org_id
CROSS JOIN _asset_taxonomy_stage taxonomy
ON CONFLICT (model_id, tag)
DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    sle_value = EXCLUDED.sle_value,
    disabled = false;


/*
 * ON CONFLICT for asset_threat requires a matching unique index.
 *
 * Index creation intentionally fails if duplicate relationships already exist;
 * the migration does not silently delete user data.
 */
CREATE UNIQUE INDEX IF NOT EXISTS asset_threat_model_asset_threat_uidx
    ON threat.asset_threat (model_id, asset_id, threat_id);


/*
 * 4. Inspect threat classification cardinality.
 *
 * class_id is stored in threat.threat_countermeasure_classes rather than on
 * threat.threats. A threat may have multiple applicable countermeasure classes.
 * This is informational and does not block the migration.
 */
SELECT
    COUNT(*) AS classified_threats,
    COUNT(*) FILTER (WHERE distinct_class_count > 1)
        AS threats_with_multiple_classes,
    MAX(distinct_class_count) AS maximum_classes_per_threat
FROM (
    SELECT
        tcc.threat_id,
        COUNT(DISTINCT tcc.class_id) AS distinct_class_count
    FROM threat.threat_countermeasure_classes tcc
    GROUP BY tcc.threat_id
) classification;


/*
 * 5. Materialize asset-threat relationships for every model.
 *
 * The model-specific asset is resolved through threat.assets.tag because the
 * current assets schema does not contain taxonomy_id.
 *
 * Several classes can map the same threat to the same asset. asset_threat has
 * one damage value for that relationship, so the strongest applicable
 * class-level damage is inherited with MAX().
 */
INSERT INTO threat.asset_threat (
    model_id,
    asset_id,
    threat_id,
    damage
)
SELECT
    threat_row.model_id,
    asset_row.id,
    threat_row.id,
    MAX(asset_class.damage) AS damage
FROM threat.threats threat_row
INNER JOIN (
    SELECT DISTINCT
        threat_id,
        class_id
    FROM threat.threat_countermeasure_classes
) threat_class
    ON threat_class.threat_id = threat_row.id
INNER JOIN threat.asset_class asset_class
    ON asset_class.class_id = threat_class.class_id
INNER JOIN threat.assets asset_row
    ON asset_row.model_id = threat_row.model_id
   AND asset_row.tag = asset_class.asset_taxonomy_id
WHERE threat_row.disabled = false
  AND asset_row.disabled = false
GROUP BY
    threat_row.model_id,
    asset_row.id,
    threat_row.id
ON CONFLICT (model_id, asset_id, threat_id)
DO UPDATE
SET damage = EXCLUDED.damage;


/*
 * Validation summaries.
 */
SELECT
    COUNT(*) AS asset_class_relationships,
    COUNT(DISTINCT asset_taxonomy_id) AS taxonomy_assets,
    COUNT(DISTINCT class_id) AS mapped_classes
FROM threat.asset_class;

SELECT
    COUNT(*) AS model_count,
    COUNT(*) FILTER (WHERE product.id IS NULL) AS models_without_product,
    COUNT(*) FILTER (WHERE org.id IS NULL) AS models_without_org,
    COUNT(*) FILTER (WHERE COALESCE(org.size, 0) = 0)
        AS models_with_zero_valuation
FROM threat.models model
LEFT JOIN public.products product
    ON product.id = model.product_id
LEFT JOIN public.orgs org
    ON org.id = product.org_id;

SELECT
    COUNT(*) AS taxonomy_asset_rows,
    COUNT(DISTINCT asset.model_id) AS models_with_taxonomy_assets,
    MIN(model_asset_count) AS minimum_assets_per_model,
    MAX(model_asset_count) AS maximum_assets_per_model
FROM threat.assets asset
INNER JOIN (
    SELECT asset_taxonomy_id
    FROM _asset_taxonomy_stage
) taxonomy
    ON taxonomy.asset_taxonomy_id = asset.tag
INNER JOIN (
    SELECT
        model_id,
        COUNT(*) AS model_asset_count
    FROM threat.assets
    WHERE tag IN (
        SELECT asset_taxonomy_id
        FROM _asset_taxonomy_stage
    )
      AND disabled = false
    GROUP BY model_id
) counts
    ON counts.model_id = asset.model_id
WHERE asset.disabled = false;

SELECT
    COUNT(*) AS asset_threat_rows,
    COUNT(DISTINCT model_id) AS populated_models,
    COUNT(DISTINCT threat_id) AS threats_with_assets
FROM threat.asset_threat;

COMMIT;
