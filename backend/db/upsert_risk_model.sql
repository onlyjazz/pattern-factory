CREATE OR REPLACE PROCEDURE threat.upsert_risk_model(
    v_payload JSONB,
    OUT v_result JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_model_id          INTEGER;
    v_card_id           UUID;
    v_threat_count      INTEGER := 0;
    v_vuln_count        INTEGER := 0;
    v_cm_count          INTEGER := 0;
    v_asset_threat_count INTEGER := 0;
    v_vuln_threat_count  INTEGER := 0;
    v_cm_threat_count    INTEGER := 0;
BEGIN
    ---------------------------------------------------------------------
    -- VALIDATE PAYLOAD STRUCTURE
    ---------------------------------------------------------------------
    IF v_payload IS NULL THEN
        v_result := jsonb_build_object(
            'status', 'error',
            'message', 'Payload cannot be NULL'
        );
        RETURN;
    END IF;

    -- Extract model_id and card_id from payload
    v_model_id := (v_payload->>'model_id')::INTEGER;
    v_card_id := (v_payload->>'card_id')::UUID;

    IF v_model_id IS NULL THEN
        v_result := jsonb_build_object(
            'status', 'error',
            'message', 'model_id is required in payload'
        );
        RETURN;
    END IF;

    IF v_card_id IS NULL THEN
        v_result := jsonb_build_object(
            'status', 'error',
            'message', 'card_id is required in payload'
        );
        RETURN;
    END IF;

    ---------------------------------------------------------------------
    -- 1. BULK UPSERT THREATS
    ---------------------------------------------------------------------
    -- Threats have: tag, name, domain, probability, description, card_id, model_id
    -- tag is the unique identifier within a model
    WITH upserted_threats AS (
        INSERT INTO threat.threats (
            model_id,
            tag,
            name,
            description,
            domain,
            probability,
            card_id,
            spoofing,
            tampering,
            repudiation,
            information_disclosure,
            denial_of_service,
            elevation_of_privilege,
            mitigation_level,
            disabled,
            created_at,
            updated_at
        )
        SELECT 
            v_model_id,
            value->>'tag',
            value->>'name',
            COALESCE(value->>'description', value->>'name'),
            value->>'domain',
            NULLIF(value->>'probability', '')::NUMERIC,
            v_card_id,
            false,
            false,
            false,
            false,
            false,
            false,
            0,
            false,
            NOW(),
            NOW()
        FROM jsonb_array_elements(COALESCE(v_payload->'threats', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
          AND value->>'tag' IS NOT NULL
        ON CONFLICT (model_id, tag) DO UPDATE SET
            name            = EXCLUDED.name,
            description     = EXCLUDED.description,
            domain          = EXCLUDED.domain,
            probability     = EXCLUDED.probability,
            card_id         = EXCLUDED.card_id,
            updated_at      = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_threat_count FROM upserted_threats;


    ---------------------------------------------------------------------
    -- 2. BULK UPSERT VULNERABILITIES
    ---------------------------------------------------------------------
    -- Vulnerabilities have: name, description, model_id
    WITH upserted_vulns AS (
        INSERT INTO threat.vulnerabilities (
            model_id,
            name,
            description,
            disabled,
            created_at,
            updated_at
        )
        SELECT 
            v_model_id,
            value->>'name',
            value->>'description',
            false,
            NOW(),
            NOW()
        FROM jsonb_array_elements(COALESCE(v_payload->'vulnerabilities', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
        ON CONFLICT (model_id, name) DO UPDATE SET
            description     = EXCLUDED.description,
            updated_at      = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_vuln_count FROM upserted_vulns;


    ---------------------------------------------------------------------
    -- 3. BULK UPSERT COUNTERMEASURES
    -- Countermeasures have: name (required), fixed_implementation_cost (required),
    -- recurring_implementation_cost (required), tag (optional), description (optional)
    WITH upserted_cms AS (
        INSERT INTO threat.countermeasures (
            model_id,
            tag,
            name,
            description,
            fixed_implementation_cost,
            fixed_cost_period,
            recurring_implementation_cost,
            include_fixed_cost,
            include_recurring_cost,
            created_at,
            updated_at
        )
        SELECT 
            v_model_id,
            value->>'tag',
            value->>'name',
            value->>'description',
            (value->>'fixed_implementation_cost')::INTEGER,
            COALESCE(NULLIF(value->>'fixed_cost_period', '')::INTEGER, 12),
            (value->>'recurring_implementation_cost')::INTEGER,
            COALESCE((value->>'include_fixed_cost')::BOOLEAN, true),
            COALESCE((value->>'include_recurring_cost')::BOOLEAN, true),
            NOW(),
            NOW()
        FROM jsonb_array_elements(COALESCE(v_payload->'countermeasures', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
          AND value->>'fixed_implementation_cost' IS NOT NULL
          AND value->>'recurring_implementation_cost' IS NOT NULL
        ON CONFLICT (model_id, name) DO UPDATE SET
            tag                          = EXCLUDED.tag,
            description                  = EXCLUDED.description,
            fixed_implementation_cost    = EXCLUDED.fixed_implementation_cost,
            fixed_cost_period            = EXCLUDED.fixed_cost_period,
            recurring_implementation_cost = EXCLUDED.recurring_implementation_cost,
            include_fixed_cost           = EXCLUDED.include_fixed_cost,
            include_recurring_cost       = EXCLUDED.include_recurring_cost,
            updated_at                   = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_cm_count FROM upserted_cms;


    ---------------------------------------------------------------------
    -- 4. BULK INSERT ASSET → THREAT LINKS
    ---------------------------------------------------------------------
    -- Link format: { asset_tag, threat_tag, damage }
    -- Must resolve asset_tag → asset_id and threat_tag → threat_id
    WITH inserted_asset_threats AS (
        INSERT INTO threat.asset_threat (
            model_id,
            asset_id,
            threat_id,
            damage
        )
        SELECT DISTINCT
            v_model_id,
            a.id,
            t.id,
            NULLIF(value->>'damage', '')::INTEGER
        FROM jsonb_array_elements(COALESCE(v_payload->'asset_threat', '[]'::jsonb))
        LEFT JOIN threat.assets a ON a.model_id = v_model_id AND a.tag = value->>'asset_tag'
        LEFT JOIN threat.threats t ON t.model_id = v_model_id AND t.tag = value->>'threat_tag'
        WHERE value->>'asset_tag' IS NOT NULL 
          AND value->>'threat_tag' IS NOT NULL
          AND a.id IS NOT NULL
          AND t.id IS NOT NULL
        ON CONFLICT (model_id, asset_id, threat_id) DO UPDATE SET
            damage = EXCLUDED.damage
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_asset_threat_count FROM inserted_asset_threats;


    ---------------------------------------------------------------------
    -- 5. BULK INSERT VULNERABILITY → THREAT LINKS
    ---------------------------------------------------------------------
    -- Link format: { vulnerability_name, threat_tag }
    -- Must resolve vulnerability_name → vulnerability_id and threat_tag → threat_id
    WITH inserted_vuln_threats AS (
        INSERT INTO threat.vulnerability_threat (
            model_id,
            vulnerability_id,
            threat_id
        )
        SELECT DISTINCT
            v_model_id,
            v.id,
            t.id
        FROM jsonb_array_elements(COALESCE(v_payload->'vulnerability_threat', '[]'::jsonb))
        LEFT JOIN threat.vulnerabilities v ON v.model_id = v_model_id AND v.name = value->>'vulnerability_name'
        LEFT JOIN threat.threats t ON t.model_id = v_model_id AND t.tag = value->>'threat_tag'
        WHERE value->>'vulnerability_name' IS NOT NULL 
          AND value->>'threat_tag' IS NOT NULL
          AND v.id IS NOT NULL
          AND t.id IS NOT NULL
        ON CONFLICT (model_id, vulnerability_id, threat_id) DO NOTHING
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_vuln_threat_count FROM inserted_vuln_threats;


    ---------------------------------------------------------------------
    -- 6. BULK INSERT COUNTERMEASURE → THREAT LINKS
    ---------------------------------------------------------------------
    -- Link format: { countermeasure_tag, threat_tag, mitigation_level }
    -- Must resolve countermeasure_tag → countermeasure_id and threat_tag → threat_id
    -- Countermeasure lookup by tag, or fall back to name if tag is null
    WITH inserted_cm_threats AS (
        INSERT INTO threat.countermeasure_threat (
            model_id,
            countermeasure_id,
            threat_id,
            mitigation_level,
            included_in_mitigation
        )
        SELECT DISTINCT
            v_model_id,
            c.id,
            t.id,
            NULLIF(value->>'mitigation_level', '')::INTEGER,
            true
        FROM jsonb_array_elements(COALESCE(v_payload->'countermeasure_threat', '[]'::jsonb))
        LEFT JOIN threat.countermeasures c ON 
            c.model_id = v_model_id AND (
                (value->>'countermeasure_tag' IS NOT NULL AND c.tag = value->>'countermeasure_tag')
                OR 
                (value->>'countermeasure_name' IS NOT NULL AND c.name = value->>'countermeasure_name')
            )
        LEFT JOIN threat.threats t ON t.model_id = v_model_id AND t.tag = value->>'threat_tag'
        WHERE value->>'threat_tag' IS NOT NULL
          AND (value->>'countermeasure_tag' IS NOT NULL OR value->>'countermeasure_name' IS NOT NULL)
          AND c.id IS NOT NULL
          AND t.id IS NOT NULL
        ON CONFLICT (model_id, countermeasure_id, threat_id) DO UPDATE SET
            mitigation_level = EXCLUDED.mitigation_level,
            included_in_mitigation = EXCLUDED.included_in_mitigation
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_cm_threat_count FROM inserted_cm_threats;


    ---------------------------------------------------------------------
    -- RETURN SUMMARY
    ---------------------------------------------------------------------
    v_result := jsonb_build_object(
        'status', 'success',
        'summary', jsonb_build_object(
            'model_id', v_model_id,
            'card_id', v_card_id,
            'threats_upserted', v_threat_count,
            'vulnerabilities_upserted', v_vuln_count,
            'countermeasures_upserted', v_cm_count,
            'asset_threat_links_created', v_asset_threat_count,
            'vulnerability_threat_links_created', v_vuln_threat_count,
            'countermeasure_threat_links_created', v_cm_threat_count
        )
    );

EXCEPTION
    WHEN OTHERS THEN
        v_result := jsonb_build_object(
            'status', 'error',
            'message', SQLERRM,
            'detail', SQLSTATE,
            'model_id', v_model_id,
            'card_id', v_card_id
        );
        RAISE;  -- Re-raise to rollback transaction
END;
$$;
