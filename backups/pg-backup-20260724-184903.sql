--
-- PostgreSQL database dump
--

\restrict QVPP7e5qHN8Wgzl9TtHtVB8XeztYOcNfVVqZ4L6WY586viyye0sENctCfNqBoRS

-- Dumped from database version 17.6 (Homebrew)
-- Dumped by pg_dump version 17.6 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: threat; Type: SCHEMA; Schema: -; Owner: pattern_factory
--

CREATE SCHEMA threat;


ALTER SCHEMA threat OWNER TO pattern_factory;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: patterns_vector_update(); Type: FUNCTION; Schema: public; Owner: pattern_factory
--

CREATE FUNCTION public.patterns_vector_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.search_vector :=
    to_tsvector('english', coalesce(NEW.name,'') || ' ' || coalesce(NEW.description,''));
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.patterns_vector_update() OWNER TO pattern_factory;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: pattern_factory
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO pattern_factory;

--
-- Name: upsert_pattern_factory_entities(jsonb); Type: PROCEDURE; Schema: public; Owner: pattern_factory
--

CREATE PROCEDURE public.upsert_pattern_factory_entities(IN v_payload jsonb, OUT v_result jsonb)
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_org_count     INTEGER := 0;
    v_guest_count   INTEGER := 0;
    v_post_count    INTEGER := 0;
    v_pattern_count INTEGER := 0;
    v_link_count    INTEGER := 0;
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

    ---------------------------------------------------------------------
    -- 1. BULK UPSERT ORGANIZATIONS
    ---------------------------------------------------------------------
    WITH upserted_orgs AS (
        INSERT INTO orgs (
            name,
            description,
            content_url,
            content_source
        )
        SELECT 
            value->>'name',
            value->>'description',
            value->>'content_url',
            value->>'content_source'
        FROM jsonb_array_elements(COALESCE(v_payload->'orgs', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL  -- Skip nulls
        ON CONFLICT (name)
        DO UPDATE SET
            description    = EXCLUDED.description,
            content_url    = EXCLUDED.content_url,
            content_source = EXCLUDED.content_source,
            updated_at     = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_org_count FROM upserted_orgs;


    ---------------------------------------------------------------------
    -- 2. BULK UPSERT POSTS
    ---------------------------------------------------------------------
    WITH upserted_posts AS (
        INSERT INTO posts (
            name,
            description,
            content_url,
            content_source,
            published_at
        )
        SELECT 
            value->>'name',
            value->>'description',
            value->>'content_url',
            value->>'content_source',
            NULLIF(value->>'published_at', '')::timestamp
        FROM jsonb_array_elements(COALESCE(v_payload->'posts', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
        ON CONFLICT (name)
        DO UPDATE SET
            description    = EXCLUDED.description,
            content_url    = EXCLUDED.content_url,
            content_source = EXCLUDED.content_source,
            published_at   = EXCLUDED.published_at,
            updated_at     = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_post_count FROM upserted_posts;


    ---------------------------------------------------------------------
    -- 3. BULK UPSERT GUESTS
    ---------------------------------------------------------------------
    WITH upserted_guests AS (
        INSERT INTO guests (
            name,
            description,
            job_description,
            org_id,
            post_id,
            content_url,
            content_source
        )
        SELECT 
            value->>'name',
            value->>'description',
            value->>'job_description',
            o.id,
            p.id,
            value->>'content_url',
            value->>'content_source'
        FROM jsonb_array_elements(COALESCE(v_payload->'guests', '[]'::jsonb))
        LEFT JOIN orgs o ON o.name = value->>'org_name'
        LEFT JOIN posts p ON p.name = value->>'post_name'
        WHERE value->>'name' IS NOT NULL
        ON CONFLICT (name)
        DO UPDATE SET
            description     = EXCLUDED.description,
            job_description = EXCLUDED.job_description,
            org_id          = EXCLUDED.org_id,
            post_id         = EXCLUDED.post_id,
            content_url     = EXCLUDED.content_url,
            content_source  = EXCLUDED.content_source,
            updated_at      = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_guest_count FROM upserted_guests;


    ---------------------------------------------------------------------
    -- 4. BULK UPSERT PATTERNS
    ---------------------------------------------------------------------
    WITH upserted_patterns AS (
        INSERT INTO patterns (
            name,
            description,
            kind,
            content_source
        )
        SELECT 
            value->>'name',
            value->>'description',
            value->>'kind',
            value->>'content_source'
        FROM jsonb_array_elements(COALESCE(v_payload->'patterns', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
        ON CONFLICT (name)
        DO UPDATE SET
            description    = EXCLUDED.description,
            kind           = EXCLUDED.kind,
            content_source = EXCLUDED.content_source,
            updated_at     = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_pattern_count FROM upserted_patterns;


    ---------------------------------------------------------------------
    -- 5. BULK INSERT PATTERN → POST LINKS
    ---------------------------------------------------------------------
    WITH inserted_links AS (
        INSERT INTO pattern_post_link(pattern_id, post_id)
        SELECT DISTINCT
            pat.id,
            pos.id
        FROM jsonb_array_elements(COALESCE(v_payload->'pattern_post_link', '[]'::jsonb))
        INNER JOIN patterns pat ON pat.name = value->>'pattern_name'
        INNER JOIN posts pos ON pos.name = value->>'post_name'
        WHERE value->>'pattern_name' IS NOT NULL 
          AND value->>'post_name' IS NOT NULL
        ON CONFLICT DO NOTHING
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_link_count FROM inserted_links;


    ---------------------------------------------------------------------
    -- 6. BULK INSERT PATTERN → ORG LINKS
    ---------------------------------------------------------------------
    WITH inserted_links AS (
        INSERT INTO pattern_org_link(pattern_id, org_id)
        SELECT DISTINCT
            pat.id,
            org.id
        FROM jsonb_array_elements(COALESCE(v_payload->'pattern_org_link', '[]'::jsonb))
        INNER JOIN patterns pat ON pat.name = value->>'pattern_name'
        INNER JOIN orgs org ON org.name = value->>'org_name'
        WHERE value->>'pattern_name' IS NOT NULL 
          AND value->>'org_name' IS NOT NULL
        ON CONFLICT DO NOTHING
        RETURNING 1
    )
    SELECT v_link_count + COUNT(*) INTO v_link_count FROM inserted_links;


    ---------------------------------------------------------------------
    -- 7. BULK INSERT PATTERN → GUEST LINKS
    ---------------------------------------------------------------------
    WITH inserted_links AS (
        INSERT INTO pattern_guest_link(pattern_id, guest_id)
        SELECT DISTINCT
            pat.id,
            guest.id
        FROM jsonb_array_elements(COALESCE(v_payload->'pattern_guest_link', '[]'::jsonb))
        INNER JOIN patterns pat ON pat.name = value->>'pattern_name'
        INNER JOIN guests guest ON guest.name = value->>'guest_name'
        WHERE value->>'pattern_name' IS NOT NULL 
          AND value->>'guest_name' IS NOT NULL
        ON CONFLICT DO NOTHING
        RETURNING 1
    )
    SELECT v_link_count + COUNT(*) INTO v_link_count FROM inserted_links;


    ---------------------------------------------------------------------
    -- RETURN SUMMARY
    ---------------------------------------------------------------------
    v_result := jsonb_build_object(
        'status', 'success',
        'summary', jsonb_build_object(
            'orgs_upserted', v_org_count,
            'posts_upserted', v_post_count,
            'guests_upserted', v_guest_count,
            'patterns_upserted', v_pattern_count,
            'links_created', v_link_count
        )
    );

EXCEPTION
    WHEN OTHERS THEN
        v_result := jsonb_build_object(
            'status', 'error',
            'message', SQLERRM,
            'detail', SQLSTATE
        );
        RAISE;  -- Re-raise to rollback transaction
END;
$$;


ALTER PROCEDURE public.upsert_pattern_factory_entities(IN v_payload jsonb, OUT v_result jsonb) OWNER TO pattern_factory;

--
-- Name: compute_asset_yearly_value(); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.compute_asset_yearly_value() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION threat.compute_asset_yearly_value() OWNER TO pattern_factory;

--
-- Name: compute_countermeasure_yearly_cost(); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.compute_countermeasure_yearly_cost() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION threat.compute_countermeasure_yearly_cost() OWNER TO pattern_factory;

--
-- Name: compute_mitigation_level(integer); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.compute_mitigation_level(p_threat_id integer) RETURNS integer
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    -- Mitigation level = 100 - residual_risk_pct (as an integer).
    --
    -- IMPORTANT: use a scalar subquery wrapped in COALESCE so this function
    -- NEVER returns NULL. The threat_impact view returns NO rows for a threat
    -- that has no asset_threat links, is disabled, or whose model is not the
    -- active model. A plain SELECT ... INTO leaves the target variable NULL in
    -- that zero-rows case, and the inner COALESCE only handles a NULL column
    -- value from a matching row — it does NOT handle "no rows". Writing that
    -- NULL back via the trigger then violates the NOT NULL constraint on
    -- threats.mitigation_level. Wrapping the scalar subquery in COALESCE(..., 0)
    -- yields the fallback when the subquery returns no rows.
    RETURN COALESCE(
        (
            SELECT 100 - ROUND(ti.residual_risk_pct)::INTEGER
            FROM threat.threat_impact ti
            WHERE ti.threat_tag <> 'TOTAL'
              AND ti.threat_tag = (
                SELECT t.tag FROM threat.threats t WHERE t.id = p_threat_id LIMIT 1
              )
            LIMIT 1
        ),
        0
    );
END;
$$;


ALTER FUNCTION threat.compute_mitigation_level(p_threat_id integer) OWNER TO pattern_factory;

--
-- Name: increment_version(); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.increment_version() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.version = COALESCE(OLD.version, 0) + 1;
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION threat.increment_version() OWNER TO pattern_factory;

--
-- Name: update_threat_mitigation_level(); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.update_threat_mitigation_level() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_new_level INTEGER;
BEGIN
    -- Recursion guard: this function issues a nested UPDATE on threat.threats,
    -- which would re-fire the AFTER UPDATE trigger. Skip when re-entered so we
    -- don't loop infinitely. pg_trigger_depth() is 1 for the original fire and
    -- 2+ for the nested UPDATE we issue below.
    IF pg_trigger_depth() > 1 THEN
        RETURN NEW;
    END IF;

    -- compute_mitigation_level is NULL-safe (returns 0 when the threat is
    -- absent from the threat_impact view), but guard defensively so a NULL can
    -- never reach the NOT NULL column.
    v_new_level := threat.compute_mitigation_level(NEW.id);
    IF v_new_level IS NOT NULL THEN
        UPDATE threat.threats
        SET mitigation_level = v_new_level
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$;


ALTER FUNCTION threat.update_threat_mitigation_level() OWNER TO pattern_factory;

--
-- Name: update_threat_mitigation_on_countermeasure_change(); Type: FUNCTION; Schema: threat; Owner: pattern_factory
--

CREATE FUNCTION threat.update_threat_mitigation_on_countermeasure_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_threat_id INTEGER;
BEGIN
    -- Handle both INSERT/UPDATE/DELETE from countermeasure_threat
    -- and UPDATE from countermeasures table
    IF TG_TABLE_NAME = 'countermeasure_threat' THEN
        v_threat_id := COALESCE(NEW.threat_id, OLD.threat_id);
    ELSIF TG_TABLE_NAME = 'countermeasures' THEN
        -- Update all threats that reference this countermeasure
        FOR v_threat_id IN
            SELECT DISTINCT threat_id FROM threat.countermeasure_threat
            WHERE countermeasure_id = COALESCE(NEW.id, OLD.id)
        LOOP
            UPDATE threat.threats
            SET mitigation_level = COALESCE(threat.compute_mitigation_level(v_threat_id), 0)
            WHERE id = v_threat_id;
        END LOOP;
        RETURN COALESCE(NEW, OLD);
    END IF;
    
    -- Update the threat's mitigation level (defensive: never write NULL)
    IF v_threat_id IS NOT NULL THEN
        UPDATE threat.threats
        SET mitigation_level = COALESCE(threat.compute_mitigation_level(v_threat_id), 0)
        WHERE id = v_threat_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION threat.update_threat_mitigation_on_countermeasure_change() OWNER TO pattern_factory;

--
-- Name: upsert_risk_model(jsonb); Type: PROCEDURE; Schema: threat; Owner: pattern_factory
--

CREATE PROCEDURE threat.upsert_risk_model(IN v_payload jsonb, OUT v_result jsonb)
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_model_id          INTEGER;
    v_card_id           UUID;
    v_asset_count       INTEGER := 0;
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
    -- 0. BULK UPSERT ASSETS
    ---------------------------------------------------------------------
    -- Assets have: tag, name, fixed_value, recurring_value, description, card_id, model_id
    -- tag is the unique identifier within a model
    -- recurring_value is yearly
    WITH upserted_assets AS (
        INSERT INTO threat.assets (
            model_id,
            tag,
            name,
            description,
            fixed_value,
            recurring_value,
            card_id,
            disabled,
            created_at,
            updated_at
        )
        SELECT 
            v_model_id,
            value->>'tag',
            value->>'name',
            value->>'description',
            COALESCE((value->>'fixed_value')::INTEGER, 0),
            COALESCE((value->>'recurring_value')::INTEGER, 0),
            v_card_id,
            false,
            NOW(),
            NOW()
        FROM jsonb_array_elements(COALESCE(v_payload->'assets', '[]'::jsonb))
        WHERE value->>'name' IS NOT NULL
          AND value->>'tag' IS NOT NULL
        ON CONFLICT (model_id, tag) DO UPDATE SET
            name            = EXCLUDED.name,
            description     = EXCLUDED.description,
            fixed_value     = EXCLUDED.fixed_value,
            recurring_value = EXCLUDED.recurring_value,
            card_id         = EXCLUDED.card_id,
            updated_at      = NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO v_asset_count FROM upserted_assets;


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
            value->>'description',
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
        SELECT DISTINCT ON (value->>'name')
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
            'assets_upserted', v_asset_count,
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


ALTER PROCEDURE threat.upsert_risk_model(IN v_payload jsonb, OUT v_result jsonb) OWNER TO pattern_factory;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: active_models; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.active_models (
    user_id uuid NOT NULL,
    model_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.active_models OWNER TO pattern_factory;

--
-- Name: assets; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.assets (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255),
    description text,
    fixed_value numeric(15,2) DEFAULT 0 NOT NULL,
    fixed_value_period integer DEFAULT 12 NOT NULL,
    recurring_value numeric(15,2) DEFAULT 0 NOT NULL,
    include_fixed_value boolean DEFAULT true NOT NULL,
    include_recurring_value boolean DEFAULT true NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tag text,
    version integer DEFAULT 1,
    yearly_value integer DEFAULT 0,
    card_id uuid
);


ALTER TABLE threat.assets OWNER TO pattern_factory;

--
-- Name: ALIST; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."ALIST" AS
 SELECT tag,
    name,
    yearly_value
   FROM threat.assets a
  WHERE (model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1));


ALTER VIEW public."ALIST" OWNER TO pattern_factory;

--
-- Name: asset_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.asset_threat (
    model_id integer NOT NULL,
    asset_id integer NOT NULL,
    threat_id integer NOT NULL,
    damage integer
);


ALTER TABLE threat.asset_threat OWNER TO pattern_factory;

--
-- Name: countermeasure_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.countermeasure_threat (
    model_id integer NOT NULL,
    countermeasure_id integer NOT NULL,
    threat_id integer NOT NULL,
    mitigation_level integer DEFAULT 50,
    included_in_mitigation boolean DEFAULT true NOT NULL
);


ALTER TABLE threat.countermeasure_threat OWNER TO pattern_factory;

--
-- Name: countermeasures; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.countermeasures (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255),
    description text,
    fixed_implementation_cost integer DEFAULT 0 NOT NULL,
    fixed_cost_period integer DEFAULT 12 NOT NULL,
    recurring_implementation_cost integer DEFAULT 0 NOT NULL,
    detailed_design text,
    implemented boolean DEFAULT true NOT NULL,
    include_fixed_cost boolean DEFAULT true NOT NULL,
    include_recurring_cost boolean DEFAULT true NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    version integer DEFAULT 1,
    yearly_cost integer DEFAULT 0,
    tag text
);


ALTER TABLE threat.countermeasures OWNER TO pattern_factory;

--
-- Name: threats; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.threats (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255),
    description text,
    probability integer,
    damage_description text,
    spoofing boolean NOT NULL,
    tampering boolean NOT NULL,
    repudiation boolean NOT NULL,
    information_disclosure boolean NOT NULL,
    denial_of_service boolean NOT NULL,
    elevation_of_privilege boolean NOT NULL,
    mitigation_level integer NOT NULL,
    disabled boolean NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    card_id uuid,
    version integer DEFAULT 1,
    domain text,
    tag text
);


ALTER TABLE threat.threats OWNER TO pattern_factory;

--
-- Name: vulnerabilities; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.vulnerabilities (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255),
    description text,
    disabled boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    version integer DEFAULT 1,
    tag character varying(50) NOT NULL
);


ALTER TABLE threat.vulnerabilities OWNER TO pattern_factory;

--
-- Name: vulnerability_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.vulnerability_threat (
    model_id integer NOT NULL,
    vulnerability_id integer NOT NULL,
    threat_id integer NOT NULL
);


ALTER TABLE threat.vulnerability_threat OWNER TO pattern_factory;

--
-- Name: ASSET-EXPLOITS; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."ASSET-EXPLOITS" AS
 SELECT a.tag AS asset_tag,
    a.name AS asset_name,
    a.yearly_value AS asset_value,
    t.tag AS threat_tag,
    t.name AS threat_name,
    at.damage AS threat_damage_to_asset,
    v.id AS vulnerability_tag,
    v.name AS vulnerability_name,
    c.name AS countermeasure_name,
    c.yearly_cost AS countermeasure_yearly_cost,
    ct.mitigation_level
   FROM ((((((threat.assets a
     JOIN threat.asset_threat at ON (((a.id = at.asset_id) AND (a.model_id = at.model_id))))
     JOIN threat.threats t ON (((at.threat_id = t.id) AND (at.model_id = t.model_id))))
     LEFT JOIN threat.vulnerability_threat vt ON (((t.id = vt.threat_id) AND (t.model_id = vt.model_id))))
     LEFT JOIN threat.vulnerabilities v ON (((vt.vulnerability_id = v.id) AND (vt.model_id = v.model_id))))
     LEFT JOIN threat.countermeasure_threat ct ON (((t.id = ct.threat_id) AND (t.model_id = ct.model_id))))
     LEFT JOIN threat.countermeasures c ON (((ct.countermeasure_id = c.id) AND (ct.model_id = c.model_id))))
  WHERE (a.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1))
  ORDER BY a.name, v.name;


ALTER VIEW public."ASSET-EXPLOITS" OWNER TO pattern_factory;

--
-- Name: CLIST; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."CLIST" AS
 SELECT name
   FROM threat.countermeasures c
  WHERE (model_id = ( SELECT am.model_id
           FROM public.active_models am
         LIMIT 1));


ALTER VIEW public."CLIST" OWNER TO pattern_factory;

--
-- Name: orgs; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.orgs (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    stage text,
    funding numeric,
    date_funded timestamp without time zone,
    date_founded timestamp without time zone,
    linkedin_company_url text,
    content_source text,
    category_id bigint,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    content_url text
);


ALTER TABLE public.orgs OWNER TO pattern_factory;

--
-- Name: LIST_ORGS; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."LIST_ORGS" AS
 SELECT name,
    description,
    date_founded,
    date_funded,
    stage AS funding_stage
   FROM public.orgs o;


ALTER VIEW public."LIST_ORGS" OWNER TO pattern_factory;

--
-- Name: guests; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.guests (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    linkedin_url text,
    job_description text,
    content_source text,
    org_id bigint,
    post_id bigint,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    content_url text
);


ALTER TABLE public.guests OWNER TO pattern_factory;

--
-- Name: pattern_guest_link; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.pattern_guest_link (
    pattern_id bigint NOT NULL,
    guest_id bigint NOT NULL
);


ALTER TABLE public.pattern_guest_link OWNER TO pattern_factory;

--
-- Name: patterns; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.patterns (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    content_source text,
    kind text DEFAULT 'pattern'::text,
    search_vector tsvector,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    story text,
    taxonomy text,
    CONSTRAINT patterns_kind_check CHECK ((kind = ANY (ARRAY['pattern'::text, 'anti-pattern'::text])))
);


ALTER TABLE public.patterns OWNER TO pattern_factory;

--
-- Name: posts; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.posts (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    content_url text,
    content_source text,
    published_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.posts OWNER TO pattern_factory;

--
-- Name: PATTERNS_BY_GUEST; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."PATTERNS_BY_GUEST" AS
 SELECT g.name AS guest_name,
    g.job_description,
    p.kind AS pattern_kind,
        CASE
            WHEN (p.content_source = 'episode'::text) THEN 'Episode'::text
            WHEN (p.content_source = 'post'::text) THEN po.name
            ELSE NULL::text
        END AS relevant_episode_or_post
   FROM (((public.patterns p
     JOIN public.pattern_guest_link pgl ON ((p.id = pgl.pattern_id)))
     JOIN public.guests g ON ((pgl.guest_id = g.id)))
     LEFT JOIN public.posts po ON ((po.id = g.post_id)));


ALTER VIEW public."PATTERNS_BY_GUEST" OWNER TO pattern_factory;

--
-- Name: pattern_post_link; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.pattern_post_link (
    pattern_id bigint NOT NULL,
    post_id bigint NOT NULL
);


ALTER TABLE public.pattern_post_link OWNER TO pattern_factory;

--
-- Name: PIP; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."PIP" AS
 SELECT p.id,
    p.name,
    p.description,
    p.content_url,
    p.content_source,
    p.published_at,
    p.created_at,
    p.updated_at,
    p.deleted_at
   FROM ((public.posts p
     JOIN public.pattern_post_link ppl ON ((ppl.post_id = p.id)))
     JOIN public.patterns pat ON ((pat.id = ppl.pattern_id)));


ALTER VIEW public."PIP" OWNER TO pattern_factory;

--
-- Name: POSTS; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."POSTS" AS
 SELECT name,
    description,
    content_url,
    content_source,
    published_at
   FROM public.posts p;


ALTER VIEW public."POSTS" OWNER TO pattern_factory;

--
-- Name: models; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.models (
    id bigint NOT NULL,
    name character varying(255),
    version character varying(50),
    author character varying(255),
    company character varying(255),
    category character varying(255),
    keywords text,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE threat.models OWNER TO pattern_factory;

--
-- Name: PROJECTS; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."PROJECTS" AS
 SELECT name,
    description
   FROM threat.models;


ALTER VIEW public."PROJECTS" OWNER TO pattern_factory;

--
-- Name: threat_countermeasures; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.threat_countermeasures AS
 SELECT t.model_id,
    t.tag AS threat_tag,
    t.name AS threat_name,
    (t.probability)::text AS probability,
    c.tag AS countermeasure_tag,
    c.name AS countermeasure_name,
    ct.mitigation_level,
    c.implemented,
    c.disabled
   FROM ((threat.threats t
     JOIN threat.countermeasure_threat ct ON (((t.id = ct.threat_id) AND (t.model_id = ct.model_id))))
     JOIN threat.countermeasures c ON (((ct.countermeasure_id = c.id) AND (ct.model_id = c.model_id))))
  WHERE ((t.disabled = false) AND (ct.included_in_mitigation = true) AND (t.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1)))
  ORDER BY t.tag, c.name;


ALTER VIEW threat.threat_countermeasures OWNER TO pattern_factory;

--
-- Name: THRCM; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."THRCM" AS
 SELECT threat_tag,
    threat_name,
    probability,
    countermeasure_tag,
    countermeasure_name,
    mitigation_level,
    implemented,
    disabled
   FROM threat.threat_countermeasures;


ALTER VIEW public."THRCM" OWNER TO pattern_factory;

--
-- Name: THREAT-CM; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."THREAT-CM" AS
 SELECT t.tag AS threat_tag,
    t.name AS threat_name,
    ct.mitigation_level,
    c.name AS countermeasure_name,
    c.yearly_cost AS countermeasure_yearly_cost
   FROM ((threat.threats t
     JOIN threat.countermeasure_threat ct ON ((t.id = ct.threat_id)))
     JOIN threat.countermeasures c ON ((ct.countermeasure_id = c.id)))
  WHERE (t.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1))
  ORDER BY t.name, c.name;


ALTER VIEW public."THREAT-CM" OWNER TO pattern_factory;

--
-- Name: THREAT-VULN; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."THREAT-VULN" AS
 SELECT t.tag AS threat_tag,
    t.name AS threat_name,
    v.name AS vulnerability_name
   FROM ((threat.threats t
     JOIN threat.vulnerability_threat vt ON (((t.id = vt.threat_id) AND (t.model_id = vt.model_id))))
     JOIN threat.vulnerabilities v ON (((vt.vulnerability_id = v.id) AND (vt.model_id = v.model_id))))
  WHERE (t.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1));


ALTER VIEW public."THREAT-VULN" OWNER TO pattern_factory;

--
-- Name: threat_impact; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.threat_impact AS
 WITH threat_mitigation AS (
         SELECT ct.threat_id,
                CASE
                    WHEN (count(ct.countermeasure_id) > 0) THEN exp(sum(ln(((1)::numeric - ((ct.mitigation_level)::numeric / 100.0)))))
                    ELSE 1.0
                END AS residual_risk_multiplier,
            sum(COALESCE(c.yearly_cost, 0)) AS total_yearly_cost
           FROM (threat.countermeasure_threat ct
             JOIN threat.countermeasures c ON ((ct.countermeasure_id = c.id)))
          WHERE ((ct.included_in_mitigation = true) AND (c.implemented = true) AND (c.disabled = false) AND (ct.mitigation_level < 100))
          GROUP BY ct.threat_id
        ), threat_details AS (
         SELECT t.model_id,
            t.tag AS threat_tag,
            t.name AS threat_name,
            t.probability,
            (round(sum((((COALESCE(a.yearly_value, 0))::numeric * ((t.probability)::numeric / 100.0)) * ((at.damage)::numeric / 100.0)))))::integer AS var_before_mitigation,
            (round(sum(((((COALESCE(a.yearly_value, 0))::numeric * ((t.probability)::numeric / 100.0)) * ((at.damage)::numeric / 100.0)) * COALESCE(tm.residual_risk_multiplier, 1.0)))))::integer AS var_after_mitigation,
            ((round((((1)::numeric - COALESCE(tm.residual_risk_multiplier, 1.0)) * (100)::numeric), 1))::text || '%'::text) AS mitigation_level,
            round((COALESCE(tm.residual_risk_multiplier, 1.0) * (100)::numeric), 1) AS residual_risk_pct,
                CASE
                    WHEN ((COALESCE(tm.residual_risk_multiplier, 1.0) * (100)::numeric) <= (10)::numeric) THEN 'Very Low'::text
                    WHEN ((COALESCE(tm.residual_risk_multiplier, 1.0) * (100)::numeric) <= (20)::numeric) THEN 'Low'::text
                    WHEN ((COALESCE(tm.residual_risk_multiplier, 1.0) * (100)::numeric) <= (50)::numeric) THEN 'Medium'::text
                    ELSE 'High'::text
                END AS residual_risk_level,
            (COALESCE(tm.total_yearly_cost, (0)::bigint))::integer AS yearly_cost
           FROM (((threat.threats t
             JOIN threat.asset_threat at ON (((t.id = at.threat_id) AND (t.model_id = at.model_id))))
             JOIN threat.assets a ON (((at.asset_id = a.id) AND (at.model_id = a.model_id))))
             LEFT JOIN threat_mitigation tm ON ((t.id = tm.threat_id)))
          WHERE ((t.disabled = false) AND (a.disabled = false) AND (t.model_id = ( SELECT active_models.model_id
                   FROM public.active_models
                 LIMIT 1)))
          GROUP BY t.id, t.model_id, t.tag, t.name, t.probability, tm.residual_risk_multiplier, tm.total_yearly_cost
          ORDER BY (round((COALESCE(tm.residual_risk_multiplier, 1.0) * (100)::numeric), 1)) DESC
        )
 SELECT threat_details.model_id,
    threat_details.threat_tag,
    threat_details.threat_name,
    threat_details.probability,
    threat_details.var_before_mitigation,
    threat_details.var_after_mitigation,
    threat_details.mitigation_level,
    threat_details.residual_risk_pct,
    threat_details.residual_risk_level,
    threat_details.yearly_cost
   FROM threat_details
UNION ALL
 SELECT ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1) AS model_id,
    'TOTAL'::text AS threat_tag,
    'Total Portfolio Risk'::character varying AS threat_name,
    NULL::integer AS probability,
    sum(threat_details.var_before_mitigation) AS var_before_mitigation,
    sum(threat_details.var_after_mitigation) AS var_after_mitigation,
    ((round((((1)::numeric - ((sum(threat_details.var_after_mitigation))::numeric / (NULLIF(sum(threat_details.var_before_mitigation), 0))::numeric)) * (100)::numeric), 1))::text || '%'::text) AS mitigation_level,
    round((((sum(threat_details.var_after_mitigation))::numeric / (NULLIF(sum(threat_details.var_before_mitigation), 0))::numeric) * (100)::numeric), 1) AS residual_risk_pct,
        CASE
            WHEN ((((sum(threat_details.var_after_mitigation))::numeric / (NULLIF(sum(threat_details.var_before_mitigation), 0))::numeric) * (100)::numeric) <= (10)::numeric) THEN 'Very Low'::text
            WHEN ((((sum(threat_details.var_after_mitigation))::numeric / (NULLIF(sum(threat_details.var_before_mitigation), 0))::numeric) * (100)::numeric) <= (20)::numeric) THEN 'Low'::text
            WHEN ((((sum(threat_details.var_after_mitigation))::numeric / (NULLIF(sum(threat_details.var_before_mitigation), 0))::numeric) * (100)::numeric) <= (50)::numeric) THEN 'Medium'::text
            ELSE 'High'::text
        END AS residual_risk_level,
    (sum(threat_details.yearly_cost))::integer AS yearly_cost
   FROM threat_details;


ALTER VIEW threat.threat_impact OWNER TO pattern_factory;

--
-- Name: THRIM; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."THRIM" AS
 SELECT threat_tag,
    threat_name,
    probability,
    mitigation_level,
    yearly_cost AS "Cost of mitigation",
    var_before_mitigation,
    var_after_mitigation,
    residual_risk_pct,
    residual_risk_level
   FROM threat.threat_impact;


ALTER VIEW public."THRIM" OWNER TO pattern_factory;

--
-- Name: TIME_TO_FUNDING; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."TIME_TO_FUNDING" AS
 SELECT name,
    stage,
    EXTRACT(year FROM age(date_funded, date_founded)) AS years_from_founding_to_funding
   FROM public.orgs o;


ALTER VIEW public."TIME_TO_FUNDING" OWNER TO pattern_factory;

--
-- Name: TLIKE; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."TLIKE" AS
 SELECT tag,
    name,
        CASE
            WHEN (probability > 50) THEN 'High'::text
            WHEN (probability > 20) THEN 'Medium'::text
            WHEN (probability > 10) THEN 'Low'::text
            ELSE 'Very low'::text
        END AS likelihood
   FROM threat.threats t
  WHERE (model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1))
  ORDER BY probability DESC;


ALTER VIEW public."TLIKE" OWNER TO pattern_factory;

--
-- Name: vulnerability_exploitability; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.vulnerability_exploitability AS
 SELECT vt.vulnerability_id,
    v.name AS vulnerability_name,
    vt.threat_id,
    t.name AS threat_name,
    COALESCE(m.total_mitigation, (0)::bigint) AS cumulative_mitigation,
        CASE
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) > 100) THEN ((COALESCE(m.total_mitigation, (0)::bigint) / 100))::numeric(10,1)
            ELSE (0)::numeric
        END AS redundancy_factor,
        CASE
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 100) THEN (0)::bigint
            ELSE (100 - COALESCE(m.total_mitigation, (0)::bigint))
        END AS residual_exploitability,
        CASE
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 400) THEN 'Fail-Safe'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 200) THEN 'Negligible'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 100) THEN 'Very Low'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 30) THEN 'Low'::text
            ELSE 'High'::text
        END AS exploitability,
        CASE
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 400) THEN 'Inherent Safety: Physically/Logically impossible to exploit.'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 200) THEN 'Resilient: Multiple redundant safety layers.'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 100) THEN 'Fully mitigated with standard controls.'::text
            WHEN (COALESCE(m.total_mitigation, (0)::bigint) >= 30) THEN 'Mitigated but with some residual risk.'::text
            ELSE 'Unmitigated or minimal controls in place.'::text
        END AS qualitative_justification
   FROM (((threat.vulnerability_threat vt
     JOIN threat.vulnerabilities v ON (((vt.vulnerability_id = v.id) AND (vt.model_id = v.model_id))))
     JOIN threat.threats t ON (((vt.threat_id = t.id) AND (vt.model_id = t.model_id))))
     LEFT JOIN ( SELECT tcm.threat_id,
            sum(tcm.mitigation_level) AS total_mitigation
           FROM threat.countermeasure_threat tcm
          WHERE ((tcm.included_in_mitigation = true) AND (tcm.model_id = ( SELECT active_models.model_id
                   FROM public.active_models
                 LIMIT 1)))
          GROUP BY tcm.threat_id) m ON ((vt.threat_id = m.threat_id)))
  WHERE (vt.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1));


ALTER VIEW threat.vulnerability_exploitability OWNER TO pattern_factory;

--
-- Name: VULNEXPLOIT; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."VULNEXPLOIT" AS
 SELECT vulnerability_name,
    exploitability
   FROM threat.vulnerability_exploitability;


ALTER VIEW public."VULNEXPLOIT" OWNER TO pattern_factory;

--
-- Name: WCRT; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public."WCRT" AS
 SELECT t.name,
    t.probability
   FROM (threat.threats t
     JOIN threat.models m ON ((t.model_id = m.id)))
  WHERE ((m.name)::text = 'Baseline'::text);


ALTER VIEW public."WCRT" OWNER TO pattern_factory;

--
-- Name: cards; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.cards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255),
    description text,
    story text DEFAULT '#Pattern card'::text,
    order_index integer DEFAULT 0,
    domain text,
    audience text,
    maturity text DEFAULT 'draft'::text,
    pattern_id bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.cards OWNER TO pattern_factory;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.categories (
    id bigint NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.categories OWNER TO pattern_factory;

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO pattern_factory;

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: guests_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.guests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.guests_id_seq OWNER TO pattern_factory;

--
-- Name: guests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.guests_id_seq OWNED BY public.guests.id;


--
-- Name: information_schema_view; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public.information_schema_view AS
 SELECT t.table_name,
    t.table_type,
    (((('- '::text || (t.table_name)::text) || ' ('::text) || string_agg((c.column_name)::text, ', '::text ORDER BY c.ordinal_position)) || ')'::text) AS view_with_columns
   FROM (information_schema.tables t
     JOIN information_schema.columns c ON ((((t.table_name)::name = (c.table_name)::name) AND ((t.table_schema)::name = (c.table_schema)::name))))
  GROUP BY t.table_name, t.table_type
  ORDER BY t.table_name;


ALTER VIEW public.information_schema_view OWNER TO pattern_factory;

--
-- Name: orgs_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.orgs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orgs_id_seq OWNER TO pattern_factory;

--
-- Name: orgs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.orgs_id_seq OWNED BY public.orgs.id;


--
-- Name: paths; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.paths (
    id integer NOT NULL,
    name text NOT NULL,
    yaml text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.paths OWNER TO pattern_factory;

--
-- Name: paths_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.paths_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.paths_id_seq OWNER TO pattern_factory;

--
-- Name: paths_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.paths_id_seq OWNED BY public.paths.id;


--
-- Name: pattern_guests; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public.pattern_guests AS
 SELECT p.name AS pattern_name,
    p.kind,
    p.content_source,
    g.name AS guest_name,
    g.job_description
   FROM ((public.patterns p
     JOIN public.pattern_guest_link pgl ON ((p.id = pgl.pattern_id)))
     JOIN public.guests g ON ((pgl.guest_id = g.id)))
  WHERE ((p.deleted_at IS NULL) AND (g.deleted_at IS NULL));


ALTER VIEW public.pattern_guests OWNER TO pattern_factory;

--
-- Name: pattern_org_link; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.pattern_org_link (
    pattern_id bigint NOT NULL,
    org_id bigint NOT NULL
);


ALTER TABLE public.pattern_org_link OWNER TO pattern_factory;

--
-- Name: pattern_orgs; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public.pattern_orgs AS
 SELECT p.name AS pattern_name,
    p.kind,
    p.content_source,
    o.name AS org_name,
    o.stage
   FROM ((public.patterns p
     JOIN public.pattern_org_link pol ON ((p.id = pol.pattern_id)))
     JOIN public.orgs o ON ((pol.org_id = o.id)))
  WHERE ((p.deleted_at IS NULL) AND (o.deleted_at IS NULL));


ALTER VIEW public.pattern_orgs OWNER TO pattern_factory;

--
-- Name: pattern_posts; Type: VIEW; Schema: public; Owner: pattern_factory
--

CREATE VIEW public.pattern_posts AS
 SELECT p.name AS pattern_name,
    p.kind,
    p.content_source,
    po.name AS post_name,
    po.content_url
   FROM ((public.patterns p
     JOIN public.pattern_post_link ppl ON ((p.id = ppl.pattern_id)))
     JOIN public.posts po ON ((ppl.post_id = po.id)))
  WHERE ((p.deleted_at IS NULL) AND (po.deleted_at IS NULL));


ALTER VIEW public.pattern_posts OWNER TO pattern_factory;

--
-- Name: patterns_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.patterns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.patterns_id_seq OWNER TO pattern_factory;

--
-- Name: patterns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.patterns_id_seq OWNED BY public.patterns.id;


--
-- Name: posts_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.posts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.posts_id_seq OWNER TO pattern_factory;

--
-- Name: posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.posts_id_seq OWNED BY public.posts.id;


--
-- Name: rbac; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.rbac (
    user_id uuid NOT NULL,
    role_id integer NOT NULL,
    permission character varying(255) NOT NULL
);


ALTER TABLE public.rbac OWNER TO pattern_factory;

--
-- Name: roles; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(255) NOT NULL
);


ALTER TABLE public.roles OWNER TO pattern_factory;

--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.roles_id_seq OWNER TO pattern_factory;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: system_log; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.system_log (
    id bigint NOT NULL,
    event text,
    context jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.system_log OWNER TO pattern_factory;

--
-- Name: system_log_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.system_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_log_id_seq OWNER TO pattern_factory;

--
-- Name: system_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.system_log_id_seq OWNED BY public.system_log.id;


--
-- Name: user_role; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.user_role (
    user_id uuid NOT NULL,
    role_id integer NOT NULL
);


ALTER TABLE public.user_role OWNER TO pattern_factory;

--
-- Name: users; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    role_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.users OWNER TO pattern_factory;

--
-- Name: views_registry; Type: TABLE; Schema: public; Owner: pattern_factory
--

CREATE TABLE public.views_registry (
    id bigint NOT NULL,
    name character varying,
    table_name text NOT NULL,
    sql text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    mode text DEFAULT 'model'::text
);


ALTER TABLE public.views_registry OWNER TO pattern_factory;

--
-- Name: views_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: pattern_factory
--

CREATE SEQUENCE public.views_registry_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.views_registry_id_seq OWNER TO pattern_factory;

--
-- Name: views_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pattern_factory
--

ALTER SEQUENCE public.views_registry_id_seq OWNED BY public.views_registry.id;


--
-- Name: area_asset; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.area_asset (
    model_id integer NOT NULL,
    area_id integer NOT NULL,
    asset_id integer NOT NULL
);


ALTER TABLE threat.area_asset OWNER TO pattern_factory;

--
-- Name: area_countermeasure; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.area_countermeasure (
    model_id integer NOT NULL,
    area_id integer NOT NULL,
    countermeasure_id integer NOT NULL
);


ALTER TABLE threat.area_countermeasure OWNER TO pattern_factory;

--
-- Name: area_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.area_threat (
    model_id integer NOT NULL,
    area_id integer NOT NULL,
    threat_id integer NOT NULL
);


ALTER TABLE threat.area_threat OWNER TO pattern_factory;

--
-- Name: area_vulnerability; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.area_vulnerability (
    model_id integer NOT NULL,
    area_id integer NOT NULL,
    vulnerability_id integer NOT NULL
);


ALTER TABLE threat.area_vulnerability OWNER TO pattern_factory;

--
-- Name: areas; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.areas (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    use_for_threats boolean NOT NULL,
    use_for_vulnerabilities boolean NOT NULL,
    use_for_countermeasures boolean NOT NULL,
    use_for_assets boolean NOT NULL
);


ALTER TABLE threat.areas OWNER TO pattern_factory;

--
-- Name: areas_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.areas_id_seq OWNER TO pattern_factory;

--
-- Name: areas_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.areas_id_seq OWNED BY threat.areas.id;


--
-- Name: asset_threat_exploitability; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.asset_threat_exploitability AS
 SELECT a.name AS asset_name,
    t.name AS threat_name,
    t.probability AS threat_probability,
    at.damage AS threat_damage_to_asset,
    round(((((t.probability)::numeric / 100.0) * ((at.damage)::numeric / 100.0)) * (100)::numeric), 1) AS exploitability
   FROM ((threat.assets a
     JOIN threat.asset_threat at ON (((a.id = at.asset_id) AND (a.model_id = at.model_id))))
     JOIN threat.threats t ON (((at.threat_id = t.id) AND (at.model_id = t.model_id))))
  WHERE ((a.disabled = false) AND (t.disabled = false) AND (a.model_id = ( SELECT active_models.model_id
           FROM public.active_models
         LIMIT 1)))
  ORDER BY a.name, t.name;


ALTER VIEW threat.asset_threat_exploitability OWNER TO pattern_factory;

--
-- Name: assets_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.assets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.assets_id_seq OWNER TO pattern_factory;

--
-- Name: assets_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.assets_id_seq OWNED BY threat.assets.id;


--
-- Name: attacker_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.attacker_threat (
    model_id integer NOT NULL,
    attacker_type_id integer NOT NULL,
    threat_id integer NOT NULL
);


ALTER TABLE threat.attacker_threat OWNER TO pattern_factory;

--
-- Name: attacker_types; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.attacker_types (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    tools_available text
);


ALTER TABLE threat.attacker_types OWNER TO pattern_factory;

--
-- Name: attacker_types_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.attacker_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.attacker_types_id_seq OWNER TO pattern_factory;

--
-- Name: attacker_types_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.attacker_types_id_seq OWNED BY threat.attacker_types.id;


--
-- Name: countermeasures_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.countermeasures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.countermeasures_id_seq OWNER TO pattern_factory;

--
-- Name: countermeasures_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.countermeasures_id_seq OWNED BY threat.countermeasures.id;


--
-- Name: entrypoint_threat; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.entrypoint_threat (
    model_id integer NOT NULL,
    entrypoint_id integer NOT NULL,
    threat_id integer NOT NULL
);


ALTER TABLE threat.entrypoint_threat OWNER TO pattern_factory;

--
-- Name: entrypoints; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.entrypoints (
    id integer NOT NULL,
    model_id integer NOT NULL,
    name character varying(255),
    description text
);


ALTER TABLE threat.entrypoints OWNER TO pattern_factory;

--
-- Name: entrypoints_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.entrypoints_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.entrypoints_id_seq OWNER TO pattern_factory;

--
-- Name: entrypoints_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.entrypoints_id_seq OWNED BY threat.entrypoints.id;


--
-- Name: parameters; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.parameters (
    id integer NOT NULL,
    parameter_name character varying(50),
    display_name character varying(50),
    value character varying(255)
);


ALTER TABLE threat.parameters OWNER TO pattern_factory;

--
-- Name: parameters_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.parameters_id_seq OWNER TO pattern_factory;

--
-- Name: parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.parameters_id_seq OWNED BY threat.parameters.id;


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.projects_id_seq OWNER TO pattern_factory;

--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.projects_id_seq OWNED BY threat.models.id;


--
-- Name: risk_history; Type: TABLE; Schema: threat; Owner: pattern_factory
--

CREATE TABLE threat.risk_history (
    "time" timestamp without time zone NOT NULL,
    series character varying(50) NOT NULL,
    value double precision,
    model_id integer,
    version integer DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE threat.risk_history OWNER TO pattern_factory;

--
-- Name: threats_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.threats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.threats_id_seq OWNER TO pattern_factory;

--
-- Name: threats_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.threats_id_seq OWNED BY threat.threats.id;


--
-- Name: vassets; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.vassets AS
 SELECT a.id,
    a.model_id,
    a.name,
    a.description,
    a.fixed_value,
    a.fixed_value_period,
    a.recurring_value,
    a.include_fixed_value,
    a.include_recurring_value,
    a.disabled,
    a.created_at,
    a.updated_at,
    a.tag,
    a.version,
    a.yearly_value
   FROM (threat.assets a
     JOIN public.active_models am ON ((a.model_id = am.model_id)))
  WHERE (am.user_id = ( SELECT users.id
           FROM public.users
          WHERE ((users.email)::text = 'admin@opencro.com'::text)));


ALTER VIEW threat.vassets OWNER TO pattern_factory;

--
-- Name: vcountermeasures; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.vcountermeasures AS
 SELECT c.id,
    c.model_id,
    c.name,
    c.description,
    c.fixed_implementation_cost,
    c.fixed_cost_period,
    c.recurring_implementation_cost,
    c.detailed_design,
    c.implemented,
    c.include_fixed_cost,
    c.include_recurring_cost,
    c.disabled,
    c.created_at,
    c.updated_at,
    c.version,
    c.yearly_cost
   FROM (threat.countermeasures c
     JOIN public.active_models am ON ((c.model_id = am.model_id)))
  WHERE (am.user_id = ( SELECT users.id
           FROM public.users
          WHERE ((users.email)::text = 'admin@opencro.com'::text)));


ALTER VIEW threat.vcountermeasures OWNER TO pattern_factory;

--
-- Name: vthreats; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.vthreats AS
 SELECT t.id,
    t.model_id,
    t.name,
    t.description,
    t.probability,
    t.damage_description,
    t.spoofing,
    t.tampering,
    t.repudiation,
    t.information_disclosure,
    t.denial_of_service,
    t.elevation_of_privilege,
    t.mitigation_level,
    t.disabled,
    t.created_at,
    t.updated_at,
    t.card_id,
    t.version,
    t.domain,
    t.tag
   FROM (threat.threats t
     JOIN public.active_models am ON ((t.model_id = am.model_id)))
  WHERE (am.user_id = ( SELECT users.id
           FROM public.users
          WHERE ((users.email)::text = 'admin@opencro.com'::text)));


ALTER VIEW threat.vthreats OWNER TO pattern_factory;

--
-- Name: vulnerabilities_id_seq; Type: SEQUENCE; Schema: threat; Owner: pattern_factory
--

CREATE SEQUENCE threat.vulnerabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE threat.vulnerabilities_id_seq OWNER TO pattern_factory;

--
-- Name: vulnerabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: threat; Owner: pattern_factory
--

ALTER SEQUENCE threat.vulnerabilities_id_seq OWNED BY threat.vulnerabilities.id;


--
-- Name: vvulnerabilities; Type: VIEW; Schema: threat; Owner: pattern_factory
--

CREATE VIEW threat.vvulnerabilities AS
 SELECT v.id,
    v.model_id,
    v.name,
    v.description,
    v.disabled,
    v.created_at,
    v.updated_at,
    v.version
   FROM (threat.vulnerabilities v
     JOIN public.active_models am ON ((v.model_id = am.model_id)))
  WHERE (am.user_id = ( SELECT users.id
           FROM public.users
          WHERE ((users.email)::text = 'admin@opencro.com'::text)));


ALTER VIEW threat.vvulnerabilities OWNER TO pattern_factory;

--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: guests id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.guests ALTER COLUMN id SET DEFAULT nextval('public.guests_id_seq'::regclass);


--
-- Name: orgs id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.orgs ALTER COLUMN id SET DEFAULT nextval('public.orgs_id_seq'::regclass);


--
-- Name: paths id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.paths ALTER COLUMN id SET DEFAULT nextval('public.paths_id_seq'::regclass);


--
-- Name: patterns id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.patterns ALTER COLUMN id SET DEFAULT nextval('public.patterns_id_seq'::regclass);


--
-- Name: posts id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.posts ALTER COLUMN id SET DEFAULT nextval('public.posts_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: system_log id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.system_log ALTER COLUMN id SET DEFAULT nextval('public.system_log_id_seq'::regclass);


--
-- Name: views_registry id; Type: DEFAULT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.views_registry ALTER COLUMN id SET DEFAULT nextval('public.views_registry_id_seq'::regclass);


--
-- Name: areas id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.areas ALTER COLUMN id SET DEFAULT nextval('threat.areas_id_seq'::regclass);


--
-- Name: assets id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.assets ALTER COLUMN id SET DEFAULT nextval('threat.assets_id_seq'::regclass);


--
-- Name: attacker_types id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.attacker_types ALTER COLUMN id SET DEFAULT nextval('threat.attacker_types_id_seq'::regclass);


--
-- Name: countermeasures id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasures ALTER COLUMN id SET DEFAULT nextval('threat.countermeasures_id_seq'::regclass);


--
-- Name: entrypoints id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.entrypoints ALTER COLUMN id SET DEFAULT nextval('threat.entrypoints_id_seq'::regclass);


--
-- Name: models id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.models ALTER COLUMN id SET DEFAULT nextval('threat.projects_id_seq'::regclass);


--
-- Name: parameters id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.parameters ALTER COLUMN id SET DEFAULT nextval('threat.parameters_id_seq'::regclass);


--
-- Name: threats id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.threats ALTER COLUMN id SET DEFAULT nextval('threat.threats_id_seq'::regclass);


--
-- Name: vulnerabilities id; Type: DEFAULT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerabilities ALTER COLUMN id SET DEFAULT nextval('threat.vulnerabilities_id_seq'::regclass);


--
-- Data for Name: active_models; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.active_models (user_id, model_id, created_at, updated_at) FROM stdin;
4da53331-d976-4512-a215-ed756612a8e0	34	2026-06-25 11:01:52.960978+03	2026-07-24 15:27:31.463074+03
\.


--
-- Data for Name: cards; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.cards (id, name, description, story, order_index, domain, audience, maturity, pattern_id, created_at, updated_at) FROM stdin;
9e4d617f-e697-4737-8ccb-ae8e920b7ea9	Assuming that testing is sufficient in pre-production environments	Security testing (penetration testing, vulnerability scanning, fuzzing) occurs exclusively in pre-production environments that differ significantly from production configurations	# Testing Cybersecurity Requirements in pre-production\n\n## Description\n\nSecurity testing (penetration testing, vulnerability scanning, fuzzing) occurs exclusively in pre-production environments that differ significantly from production configurations. Production-specific attack surfaces (third-party integrations, enterprise network configurations, multi-tenancy boundaries) remain untested until post-market deployment. The assumption is that staging environment security testing is representative of production security posture.\n\n## Common Contexts\n\n* Hospital network deployments with site-specific firewall rules and VLANs\n* Cloud-based platforms with customer-specific SSO integrations\n* Devices with field-configurable network interfaces and protocols\n* Systems integrating with EHR/PACS/laboratory information systems via HL7/FHIR\n\n## Typical Impact\n\n**HIGH:** Post-market security vulnerabilities discovered by hospitals during deployment, installation delays, emergency security patches in production, customer security audit failures. Production-specific attack vectors (misconfigured integration points, unanticipated network exposure) create exploitable vulnerabilities that staging testing never revealed.\n\n## Early Signals\n\n* Security test plans explicitly exclude production systems due to patient safety concerns\n* Staging environment uses simplified network topology without customer integration points\n* No security validation process during installation qualification (IQ/OQ/PQ)\n* Customer-reported security issues consistently involve features not present in staging\n\n## Why Teams Miss This\n\nPatient safety concerns legitimately constrain testing in production medical device environments. Staging environments are intentionally simplified to enable controlled testing - this simplification removes attack surfaces. The configuration space of production deployments (hospital networks, customer-specific integrations) is too large to fully replicate in staging. Security testing is time-boxed and scoped to core functionality, not edge cases. Regulatory validation focuses on intended use, not adversarial scenarios.	5	MedTech	RA/QA, Cyber	Draft	23	2026-01-13 10:55:05.4304	2026-01-22 12:25:04.508128
07795510-3822-4bfb-953f-473f368388b9	SBOM compliance	Treating SBOM Generation as a Compliance Checkbox	# Treating SBOM Generation as a Compliance Checkbox\n\n## Description\n\nOrganizations generate Software Bill of Materials (SBOM) documents to satisfy regulatory requirements without integrating SBOM data into vulnerability management, procurement decisions, or incident response workflows. The SBOM exists as a static artifact that is never queried, updated, or actionable.\n\n## Common Contexts\n\n* FDA premarket submissions requires SBOM attachments\n* Post-market surveillance programs with SBOM requirements\n* Procurement contracts mandating SBOM delivery\n* EU MDR technical documentation including software composition\n\n## Typical Impact\n\n**HIGH:** Delayed response to zero-day vulnerabilities (Log4Shell, Heartbleed), inability to identify affected products during security incidents, missed vulnerability disclosures from component vendors. Organizations discover critical vulnerabilities in deployed devices weeks or months after public disclosure.\n\n## Early Signals\n\n* SBOM is generated once during regulatory submission and never updated\n* No automated tooling to query SBOM against vulnerability databases\n* Security team cannot answer "which products use OpenSSL 1.1.1?" within 24 hours\n* SBOM generation is owned by regulatory affairs, not engineering or security\n\n## Why Teams Miss This\n\nSBOM requirements are framed as regulatory documentation rather than operational security tools. Organizations lack mature vulnerability management processes that could consume SBOM data. The gap between "compliance artifact" and "security tool" isn't obvious until a major incident occurs. Tooling investments focus on SBOM generation, not SBOM operationalization.\n	2	MedTech	RA/QA, Cyber	Draft	23	2026-01-13 10:42:19.36165	2026-01-13 10:46:18.607183
1846eb05-89e6-4845-b183-8ce9a1a47772	Deferring cryptographic agility	Deferring Cryptographic Agility Until Post-Market	# Deferring Cryptographic Agility Until Post-Market\n\n## Description\n\nTeams hardcode cryptographic algorithms, key lengths, and protocols into firmware/software without abstraction layers or update mechanisms, assuming cryptographic standards will remain secure throughout the 10-15 year device lifecycle. When quantum computing or cryptanalytic breakthroughs invalidate current algorithms, devices cannot be upgraded.\n\n## Common Contexts\n\n* Implantable devices with 10+ year operational lifespans\n* Resource-constrained embedded systems optimizing for performance\n* Legacy products undergoing line extensions without architecture refresh\n* Devices using proprietary communication protocols with baked-in crypto\n\n## Typical Impact\n\n**CRITICAL:** Cryptographic obsolescence creates unfixable vulnerabilities in deployed device fleets. NIST transitions (SHA-1 deprecation, post-quantum migration) render devices unable to communicate with updated infrastructure. Surgical removal of implantables becomes the only remediation option. Regulatory submissions frozen due to cryptographic non-compliance.\n\n## Early Signals\n\n* Cryptographic primitives called directly in application code without abstraction\n* Firmware update mechanism cannot modify cryptographic libraries\n* Security architecture review doesn't address crypto agility or algorithm transitions\n* Hardware crypto accelerators lock device into specific algorithms\n\n## Why Teams Miss This\n\nCryptographic transitions happen on decade timescales that exceed product planning horizons. Embedded teams optimize for current performance/memory constraints rather than future flexibility. NIST guidance on crypto agility is abstract and doesn't map to embedded development practices. Security architects focus on current threat landscape, not 15-year forward projections. Regulatory submissions lock down algorithms, discouraging post-market changes.\n	3	MedTech	RA/QA, Cyber	Draft	23	2026-01-13 10:47:22.207142	2026-01-13 10:47:37.906103
742c2847-4d40-41b2-a184-f76b15048e6a	Relying on cloud provider for privacy	Assuming Cloud Provider Security Controls Are Sufficient for PHI	# Assuming Cloud Provider Security Controls Are Sufficient for PHI\n\n## Description\n\nTeams rely exclusively on AWS/Azure/GCP platform-level security controls (IAM, encryption at rest, compliance certifications) without implementing application-layer protections specific to protected health information. The shared responsibility model is misunderstood - organizations assume HIPAA compliance is inherited from cloud provider rather than constructed at the application layer.\n\n## Common Contexts\n\n* SaMD (Software as Medical Device) platforms migrating from on-premise to cloud\n* Clinical trial data management systems built on cloud infrastructure\n* Remote patient monitoring applications with consumer-facing portals\n* AI/ML model training pipelines processing de-identified datasets\n\n## Typical Impact\n\n**HIGH:** HIPAA breach notifications, OCR enforcement actions, patient data exposure. Misconfigured S3 buckets expose PHI. Inadequate access controls allow unauthorized cross-tenant data access. Logging/monitoring gaps prevent breach detection. Application-layer vulnerabilities (SQL injection, broken authentication) bypass platform security.\n\n## Early Signals\n\n* Security architecture diagram shows only AWS/Azure security services, no application controls\n* BAA (Business Associate Agreement) with cloud provider treated as completion of HIPAA compliance\n* No application-layer encryption for PHI beyond platform default encryption\n* Security team cannot articulate which controls are organization's responsibility vs. provider's\n\n## Why Teams Miss This\n\nCloud provider marketing emphasizes compliance certifications, creating perception of inherited security. Development teams lack healthcare-specific security expertise - they know cloud infrastructure but not HIPAA requirements. Shared responsibility model is conceptually simple but operationally complex to implement. Application security feels redundant when platform security is "enterprise-grade". Security-by-default cloud configurations create false confidence.\n	4	MedTech	RA/QA, Cyber	Draft	23	2026-01-13 10:50:52.365037	2026-01-13 10:51:13.515545
0df7bb6b-ae68-4b9d-84b7-1f6dc24a1522	Assuming Non-Networked Devices Do not Have Security Vulnerabilities	Unconnected devices can still be at risk with physical, USB and software defect attack vectors	# Air-Gap Fallacy: Network Isolation as Complete Security\n\n## Description\n\nTeams treat devices without network connectivity as inherently secure, ignoring physical access vectors, local interfaces (USB, Bluetooth), supply chain attacks, and firmware vulnerabilities. The absence of network connectivity creates a false sense of security that exempts the device from security review processes.\n\n## Common Contexts\n\n* Implantable devices with local wireless interfaces (programmer communication)\n* Standalone diagnostic equipment in clinical labs\n* Legacy devices being "air-gapped" as a security control\n* Battery-powered wearables with Bluetooth-only connectivity\n\n## Typical Impact\n\n**CRITICAL:** Device recalls, FDA enforcement actions, patient safety incidents. Physical access exploits can result in device manipulation, unauthorized firmware modification, or data exfiltration through side channels. Supply chain compromises remain undetected until deployment.\n\n## Early Signals\n\n* Security requirements document excludes "standalone" devices from threat modeling\n* USB ports and diagnostic interfaces have no authentication or encryption\n* Firmware update process relies solely on physical possession as security control\n* No security testing budget allocated for non-networked product lines\n\n## Why Teams Miss This\n\nNetwork security dominates the mental model of "cybersecurity" - teams trained on IT security naturally focus on network perimeter defenses. Non-networked devices don't trigger standard security review workflows. Physical security feels like a facilities problem, not an engineering problem. FDA guidance historically focused on networked medical devices, creating regulatory blind spots.\n	1	MedTech	RA/QA, Cyber	draft	23	2026-01-12 16:50:08.831386	2026-01-22 15:24:23.214833
428fa5a3-026c-4aeb-a428-fe6f0ab2bf04	Radiation protection business threat analysis	Technologies for radiation protection for hospital staff	# Anti-Pattern: Source-Based Radiation Protection in Interventional Radiology\n\n**Category:** MedTech Business Model Failure  \n**Confidence Level:** High (validated by market exit)  \n**Capital Destroyed:** $90M+ (ControlRad + Radiaction combined)  \n**Pattern Observed:** 2011-2025  \n**Document Version:** 1.0  \n**Last Updated:** January 27, 2026  \n**Author:** Danny Lieberman (OpenCRO / Pattern Factory)\n\n---\n\n## Executive Summary\n\nSource-based radiation protection represents a **technical solution to a real problem that fails due to systemic market structure issues**. Two well-funded companies (ControlRad: $43.6M, Radiaction: $46.3M) with FDA clearance, clinical validation, and strategic partnerships both failed to achieve commercial viability. ControlRad closed permanently despite exclusive Boston Scientific distribution. Radiaction faces identical structural barriers 2-3 years post-FDA clearance.\n\n**Core Insight:** Innovation in device safety accessories fails when it competes with hospital capital budgets, lacks reimbursement pathways, and cannibalizes incumbent recurring revenue models—regardless of clinical superiority.\n\n---\n\n## Pattern Recognition\n\n### What Looks Promising\n\n✅ **Real Clinical Problem**\n- 4 million interventional procedures annually (US)\n- Documented occupational hazards: cataracts, thyroid disease, brain tumors, atherosclerosis\n- Cumulative radiation exposure over 20-30 year careers\n- Established regulatory concern (FDA, OSHA guidelines)\n\n✅ **Technical Differentiation**\n- Novel approach: Block radiation at source vs. personal protective equipment\n- 85-90% dose reduction (vs. 70-80% with traditional PPE)\n- Validated through clinical trials at major institutions\n- Does not compromise image quality or workflow\n\n✅ **Regulatory Success**\n- Multiple FDA 510(k) clearances\n- CE Mark (international market access)\n- Class II device designation\n- Clinical evidence package accepted by regulators\n\n✅ **Early Validation Signals**\n- Strategic partnerships (ControlRad + Boston Scientific exclusive deal)\n- Professional society engagement (medical advisory boards)\n- Experienced management teams\n- Institutional investor backing ($40M+ rounds)\n\n---\n\n## Why It Fails: Systemic Barriers\n\n### 1. Equipment Lock-In Trap\n\n**The Problem:**\n- Source-based protection requires integration with specific C-arm manufacturers\n- ControlRad Select: Only Siemens Artis zee systems (~20-33% of market)\n- ControlRad Trace: Specific mobile C-arm models only\n- Radiaction: Limited C-arm compatibility (unspecified but similar constraints)\n\n**Market Math:**\n```\nTotal US cath/EP/IR labs: ~15,000\nCompatible installed base: ~3,000-5,000 (20-33%)\nMaximum addressable market: 33% of total TAM\n```\n\n**Why This Matters:**\n- Cannot serve 67-80% of potential customers regardless of sales execution\n- Hospital systems with mixed C-arm fleets cannot standardize on one vendor\n- New C-arm purchases take 7-10 years to refresh installed base\n- Trapped in vendor-specific niche while competitors sell to 100% of market\n\n### 2. Strategic Acquirer Mismatch\n\n**Boston Scientific Case Study:**\n\nControlRad secured exclusive distribution deal (March 2021). Company still closed within 3-4 years.\n\n**Why Strategic Failed:**\n\n**BSX Portfolio Priorities (2021-2025):**\n- Farapulse (PFA): Differentiated AF ablation outcomes → **drives procedure volume**\n- Axonics ($3.7B): Recurring revenue from neuromodulation → **$300M+ annual revenue**\n- Silk Road Medical ($1.18B): TCAR procedure growth → **reimbursement tied to device**\n- Penumbra ($14.5B): Neurovascular/peripheral → **consumables + capital equipment**\n\n**ControlRad Positioning:**\n- Radiation safety accessory (nice-to-have)\n- No impact on procedure volume or patient outcomes\n- One-time capital sale with zero recurring revenue\n- Competes with Siemens/Philips for capex budget, not with BSX products\n\n**Sales Force Incentives:**\n- BSX reps compensated on high-margin consumables and procedure-driving capital equipment\n- Radiation protection generates no follow-on consumable sales\n- Selling ControlRad requires separate conversations with hospital safety committees, not physicians\n- No credit toward quota for "saving OR staff from radiation exposure"\n\n**Lesson:** Even with 1,800-person global sales force, distribution deal failed because product doesn't align with strategic buyer's business model.\n\n### 3. Capital Budget Competition\n\n**The Hidden Competitor Analysis:**\n\nHospitals allocate radiation safety budgets across:\n\n**Option A: Traditional PPE (Burlington Medical, Barrier Technologies)**\n```\nInitial purchase: $40,000 (20 aprons × $2,000)\nReplacement cycle: 3-5 years\nAnnual maintenance: $8,000-13,000/year\n10-year TCO: $120,000-170,000\nVendor revenue model: Recurring, subscription-like\n```\n\n**Option B: Source-Based Protection (ControlRad/Radiaction)**\n```\nInitial purchase: $75,000-100,000 (estimated)\nReplacement cycle: 10+ years (capital equipment)\nAnnual maintenance: $5,000-10,000 (service contract)\n10-year TCO: $125,000-200,000\nVendor revenue model: One-time capital, minimal recurring\n```\n\n**Why PPE Incumbents Win:**\n\n1. **Budget Fungibility:** Aprons purchased from consumables/supply budget; source-based from capital equipment budget (different approval process)\n2. **Distributed Spending:** $13K/year doesn't trigger capital committee review; $100K purchase requires CFO/board approval\n3. **Vendor Lock-In:** Apron replacement = recurring revenue every 3-5 years; source-based = one-time sale\n4. **Risk Mitigation:** If aprons fail (tears, contamination), replace one unit for $2K; if source-based fails, lose $100K investment\n\n**Procurement Reality:**\n- Hospital value analysis committees prefer opex over capex\n- PPE vendors actively lobby against source-based solutions (cannibalization threat)\n- Group purchasing organizations (GPOs) negotiate multi-year PPE contracts with price protection\n- Burlington Medical won Premier GPO contract (November 2025) = preferred pricing for thousands of hospitals\n\n**Source-based protection optimizes for hospital safety but destroys vendor economics.**\n\n### 4. The "Good Enough" Threshold\n\n**Clinical Benefit Analysis:**\n\n| Solution | Dose Reduction | Staff Compliance | Cost per Lab |\n|----------|----------------|------------------|--------------|\n| No Protection | 0% | N/A | $0 |\n| Lead Apron Only | 70-75% | 80-90% | $2,000 |\n| Apron + Thyroid Shield + Glasses | 85-90% | 60-75% | $3,500 |\n| Source-Based Protection | 90-95% | 95%+ (passive) | $100,000 |\n\n**Marginal Improvement: 5-10% dose reduction for 25-30× cost increase**\n\n**Physician Behavior Patterns:**\n- Interventional cardiologists/radiologists already wear protection (regulatory requirement)\n- Scatter radiation health risks manifest over 20-30 year careers (not acute)\n- No immediate procedural benefit (unlike faster ablation or better imaging)\n- Safety culture emphasizes "wear your PPE" not "upgrade your C-arm"\n\n**Comparable Innovation Success (for contrast):**\n\n**Farapulse (Boston Scientific's star acquisition):**\n- Pulsed field ablation vs. radiofrequency ablation\n- **Differentiated outcome:** 80% reduction in esophageal injury (life-threatening complication)\n- **Procedural benefit:** 30-40% faster procedure times\n- **Reimbursement:** Same DRG as RF ablation, better outcomes = lower complications\n- **Physician incentive:** Better patient outcomes + faster turnover = more cases per day\n\n**ControlRad/Radiaction:**\n- Radiation protection vs. lead aprons\n- **Differentiated outcome:** 5-10% additional dose reduction (no acute clinical impact)\n- **Procedural benefit:** None (may even slow workflow during setup)\n- **Reimbursement:** Zero (hospital cost center)\n- **Physician incentive:** None (patients don't see/feel radiation exposure)\n\n### 5. Reimbursement Desert\n\n**Critical Failure: No Payment Mechanism**\n\n**CPT/DRG Analysis:**\n- No separate CPT code for "enhanced radiation protection"\n- Medicare/private payers reimburse procedure (e.g., PCI, EP ablation), not safety equipment\n- Hospitals cannot bill extra for "radiation-safe facility"\n- Pure cost absorption by hospital\n\n**Comparison to Successful MedTech:**\n\n| Device | Reimbursement Pathway | Hospital ROI |\n|--------|----------------------|--------------|\n| Watchman (BSX) | Separate DRG add-on payment | Positive (revenue > cost) |\n| Spinal cord stimulator | Covered by insurance, ~$30K reimbursement | Positive |\n| da Vinci robot | Higher DRG for robotic procedures | Neutral to positive |\n| ECMO | High-acuity billing codes | Positive |\n| **Source-Based Radiation Protection** | **None** | **Negative (pure cost)** |\n\n**Business Model Requires:**\n- Hospital choosing staff safety over margin optimization\n- No ROI from patient throughput improvement\n- No ability to market as "premium radiation-safe facility"\n- Competing with revenue-generating capital equipment (new MRI, robotic surgery)\n\n**Financial Reality Check:**\n```\nAverage hospital operating margin: 3-4%\nCapital committee ROI threshold: 18-24 months payback\nSource-based radiation protection payback: Never (no incremental revenue)\n```\n\n### 6. Market Structure Alignment Failure\n\n**The Ecosystem Doesn't Want This Innovation:**\n\n**C-Arm Manufacturers (Siemens, Philips, GE):**\n- **Why not integrate?** Could offer as bundled feature on new C-arm sales\n- **Why don't they?** No customer demand (hospitals satisfied with PPE status quo)\n- **Conflict:** If Siemens bundles radiation protection, Philips/GE gain competitive advantage by offering lower-priced systems without it\n- **Strategic risk:** Acquiring Radiaction highlights radiation exposure liability (opens lawsuit exposure)\n\n**PPE Manufacturers (Burlington, Barrier Technologies):**\n- **Economic threat:** Source-based protection eliminates recurring apron revenue\n- **Market defense:** Lobby hospital safety committees, emphasize "proven solution" vs. "unproven technology"\n- **Distribution advantage:** Existing relationships with hospital supply chains (PPE ordered by nurses/safety officers, not physicians)\n\n**Strategic Acquirers (BSX, Medtronic, Abbott):**\n- **No strategic fit:** Don't own C-arm businesses (Siemens/Philips domain)\n- **Revenue model mismatch:** Major medtech acquires recurring revenue businesses ($50M+ annual), not one-time capital sales\n- **Valuation ceiling:** Pre-revenue or low-revenue safety accessories don't command strategic premiums\n\n**Hospitals:**\n- **Budget pressure:** 60% of US hospitals operate on negative margins (2023)\n- **Priority spending:** AI diagnostics, robotics, capacity expansion (revenue generators)\n- **Staff safety reality:** OSHA fines for radiation exposure are rare and small ($5K-20K penalties)\n- **Risk assessment:** Cumulative staff injury over 20-30 years vs. immediate financial pressure = long-term risk gets deprioritized\n\n**Regulatory Bodies:**\n- **FDA:** Cleared for safety/efficacy, not required for market adoption\n- **OSHA:** Recommends ALARA (As Low As Reasonably Achievable) but doesn't mandate source-based protection\n- **Joint Commission:** Requires radiation safety programs but accepts PPE as compliant\n\n**No stakeholder in the ecosystem has strong incentive to champion adoption.**\n\n---\n\n## ControlRad Precedent: The Cautionary Data\n\n### Timeline of Failure Despite Advantages\n\n**2011:** Founded (Allon Guez, serial entrepreneur)  \n**2012:** $5.32M Series A  \n**2017-2019:** FDA clearances (Trace for mobile C-arms)  \n**2019:** $15M Series B (Questa Capital)  \n**2020:** Series C (undisclosed), additional FDA clearance  \n**2021:** FDA clearance for Select (Siemens Artis zee) + **Exclusive Boston Scientific distribution deal**  \n**2022:** Last funding activity (~$43.6M total raised)  \n**2024-2025:** Crunchbase status: **"Permanently Closed"**\n\n### What Went Wrong (Despite Having Everything "Right")\n\n✅ **Strong IP:** Eye-tracking + tablet-driven beam collimation (defensible tech)  \n✅ **FDA Validation:** Multiple 510(k) clearances across device types  \n✅ **Clinical Evidence:** Published trials from Beaumont Hospital, Hospital for Special Surgery  \n✅ **Strategic Partnership:** Exclusive distribution through Boston Scientific (1,800+ person sales force)  \n✅ **Experienced Management:** Guillaume Bailliard (CEO), Chris Fair (President), industry veterans  \n✅ **Well-Capitalized:** $43.6M raised across 7 rounds from institutional investors  \n\n**Result:** Company closed within 3-4 years of Boston Scientific partnership\n\n### Key Failure Points\n\n1. **Distribution Deal Didn't Execute**\n   - BSX sales force didn't prioritize (wrong incentive structure)\n   - Product required selling to hospital safety committees, not physicians (outside BSX core competency)\n   - No evidence of significant installation volume despite 4+ years of partnership\n\n2. **Equipment Lock-In Limited TAM**\n   - Select only worked with Siemens Artis zee (20-33% of market)\n   - Hospitals with mixed C-arm fleets couldn't standardize\n   - Expansion to other manufacturers required separate FDA clearances + engineering (capital intensive)\n\n3. **Revenue Model Unsustainable**\n   - One-time capital sales with minimal recurring revenue\n   - Estimated ASP: $50-75K per system\n   - To reach $20M revenue needed 270-400 installations\n   - Hospital sales cycles: 12-18 months (burn rate exceeded sales velocity)\n\n4. **Competitive Response**\n   - PPE incumbents (Burlington, Barrier) strengthened GPO relationships\n   - Burlington won Premier GPO contract (November 2025) = preferred pricing for 4,400+ hospitals\n   - Lightweight, lead-free apron innovations (XENOLITE 800 NL, 2022) reduced "burden" complaint\n\n5. **Market Timing Miss**\n   - COVID-19 (2020-2022) disrupted capital equipment budgets\n   - Hospital financial pressure intensified (margins compressed)\n   - Clinical staff safety took backseat to capacity/revenue priorities\n\n### Financial Analysis: Why ControlRad Failed\n\n**Estimated Burn Rate:**\n- 29 employees (per PitchBook)\n- Typical loaded cost: $150K-200K per employee = $4.35M-5.8M annual payroll\n- R&D, manufacturing, regulatory, commercial infrastructure: +$2-3M\n- **Total burn: ~$6-9M annually**\n\n**Required Commercialization Trajectory:**\n```\nYear 1 post-clearance: 10-20 installations × $60K ASP = $600K-1.2M revenue\nYear 2: 40-60 installations = $2.4M-3.6M revenue  \nYear 3: 80-120 installations = $4.8M-7.2M revenue\nYear 4: 150-200 installations = $9M-12M revenue\n```\n\n**What Actually Happened (estimated):**\n- Years 1-2 (2021-2022): <20 total installations = <$1.2M cumulative revenue\n- Year 3-4 (2023-2024): Stalled growth, no Series D financing\n- Burn through $43.6M over 13 years = ~$3.4M/year (insufficient commercialization investment)\n- **Cash out → wind down decision**\n\n### The Strategic Buyer Analysis That Never Materialized\n\n**Why Boston Scientific Didn't Acquire:**\n\n1. **No Revenue Threshold Met**\n   - BSX targets acquisitions with $50M-100M+ annual revenue (Farapulse, Axonics, Silk Road)\n   - ControlRad likely <$5M revenue after 3-4 years of partnership\n   - Pre-revenue/low-revenue acquisitions only for strategic tech (AI, platform capabilities)\n\n2. **No Strategic Fit with Portfolio**\n   - BSX cardiovascular portfolio: Stents, balloons, ablation catheters, Watchman\n   - BSX electrophysiology: Mapping systems, ablation technologies\n   - **ControlRad:** Radiation safety accessory (orthogonal to core business)\n\n3. **Technology Not Defensible**\n   - Semi-transparent filter + beam collimation = replicable by Siemens/Philips\n   - Eye-tracking interface = interesting but not proprietary\n   - BSX could build internally if demand existed (it didn't)\n\n4. **Market Size Reality**\n   - Even with 100% market penetration of compatible C-arms = ~5,000 US labs\n   - $60K ASP × 5,000 labs = $300M total US TAM (one-time)\n   - Replacement cycle: 10+ years (minimal recurring revenue)\n   - **Too small for strategic acquisition by $20B revenue company**\n\n**Why Siemens/Philips Didn't Acquire:**\n- Could integrate radiation protection into C-arm software (free feature to drive hardware sales)\n- Acquiring ControlRad would highlight radiation liability (legal exposure)\n- Better to let market demand pull innovation (demand never materialized)\n\n**Why Private Equity Didn't Acquire:**\n- No recurring revenue model (PE prefers SaaS, consumables, service contracts)\n- High customer acquisition cost + long sales cycles = low IRR potential\n- Better opportunities in traditional PPE (Burlington Medical model: recurring apron sales)\n\n---\n\n## Radiaction's Current Position (2025)\n\n### Company Profile\n\n**Founded:** 2014 (Tel Aviv, Israel)  \n**Total Funding:** $46.3M across 4 rounds  \n**Latest Round:** $12.6M Series C2 (August 2023)  \n**Technology:** Robotic radiation shielding system that attaches to C-arm  \n**Key Milestones:**\n- CE Mark: Achieved (European market)\n- FDA 510(k) Clearance: April 2022\n- US President/CCO: Christopher Barys appointed (October 2023)\n- US Medical Advisory Board: Formed (August 2024)\n- Distribution: Cassling partnership (US strategic sales agent)\n\n### Revenue Estimate (2024)\n\n**Analysis Based on Public Indicators:**\n\n**Conservative ($3-5M):**\n- 30-50 installations post-FDA clearance (April 2022-Dec 2024)\n- ASP: $75-100K per system\n- Implies 1-2 installations per month (early commercial traction)\n\n**Moderate ($5-7M):**\n- 50-70 installations over 2.5 years\n- Some recurring service revenue ($5-10K/year per installation)\n- Implies scaling to 2-3 installations per month\n\n**Red Flags Against Higher Revenue:**\n- No Series D announcement (suggests revenue below strategic acquisition threshold)\n- Appointed US leadership only in 2023 (late-stage commercial push)\n- 29 employees per PitchBook (similar to ControlRad at close)\n- No public case studies or major hospital system announcements\n- Crunchbase activity: Minimal media coverage beyond press releases\n\n**Most Likely: $4-6M annual revenue (2024)**\n\n### Cash Runway Analysis\n\n**Assumptions:**\n- $12.6M Series C2 (August 2023)\n- Burn rate: $4-6M annually (29 employees + commercial infrastructure)\n- Revenue: $4-6M (2024)\n- **Net burn: $0-2M annually**\n\n**Implied Runway:**\n- Best case: Self-sustaining at current revenue (unlikely, requires breakeven operations)\n- Base case: 12-18 months from Series C2 = **cash out Q4 2024 to Q2 2025**\n- **Next financing decision: Imminent (Q1-Q2 2025)**\n\n### Optionality Assessment (2-3 Year Horizon)\n\n**Option 1: Strategic Acquisition**\n\n**Probability: 10-15%**\n\n**Potential Acquirers:**\n1. **Boston Scientific** ❌\n   - Already attempted with ControlRad (failed)\n   - No appetite for radiation safety category\n   \n2. **Siemens/Philips/GE Healthineers** ❌\n   - Can build internally if market demands (hasn't)\n   - Legal liability exposure\n   - Better economics to bundle free vs. acquire for $46M\n   \n3. **Burlington Medical / Barrier Technologies** ❌\n   - Source-based protection cannibalizes recurring PPE revenue\n   - Economically irrational to acquire competitor to own business model\n\n**Valuation Ceiling:**\n- Pre-profitability MedTech multiples: 3-5× revenue\n- $6M revenue × 4× = **$24M valuation**\n- Investor returns: **-48% loss** on $46.3M invested\n- More likely valuation: $10-15M (technology fire sale)\n\n**Option 2: Continue Operating (Bootstrap/Venture Sustain)**\n\n**Probability: 30-40%**\n\n**Requirements:**\n- Achieve $15-20M revenue by 2026-2027\n- Requires 150-200 installations at $75-100K ASP\n- Penetration: 1-1.5% of US cath/EP/IR labs (15,000 total)\n- **Challenge:** ControlRad couldn't achieve this with BSX distribution\n\n**Path to Sustainability:**\n- Reduce burn to $3-4M annually\n- Focus on profitable geographies (Europe via CE Mark)\n- Add recurring revenue (service contracts, software subscriptions)\n- **Risk:** Zombie company scenario (low growth, low margin, no exit)\n\n**Option 3: Wind Down / Acqui-hire**\n\n**Probability: 50-60%**\n\n**Trigger Events:**\n- Series D fails (Q2-Q3 2025)\n- Revenue growth stalls (<$10M by end of 2025)\n- Key customer loss or manufacturing issue\n- Management team exits\n\n**Residual Value:**\n- IP portfolio (16 patents): $2-5M\n- Customer contracts: $1-2M\n- Manufacturing equipment: $500K-1M\n- **Total liquidation: $5-10M**\n- **Investor recovery: 10-20% of capital**\n\n**Most Likely Scenario:** \nRadiaction attempts Series D (Q2 2025), fails to raise at acceptable valuation, enters controlled wind-down or fire-sale M&A by Q4 2025 - Q1 2026.\n\n---\n\n## Why This Pattern Matters\n\n### Capital Efficiency Anti-Pattern\n\n**ControlRad + Radiaction Combined:**\n- Total capital raised: ~$90M\n- Combined revenue (estimated): <$10M annually\n- Capital efficiency: **<0.11× (11% of invested capital)**\n- Compare to successful MedTech: 2-5× capital efficiency at Series C\n\n**Comparable MedTech Failures:**\n- Theranos: $700M raised → $0 revenue (fraud)\n- uBiome: $105M raised → bankruptcy (business model failure)\n- **Source-based radiation protection: $90M raised → <$10M revenue (market structure failure)**\n\n### Pattern: "Technically Correct, Commercially Wrong"\n\n**Common Characteristics:**\n1. ✅ Solves real clinical problem with measurable impact\n2. ✅ FDA/regulatory approval validates safety and efficacy\n3. ✅ Clinical evidence from respected institutions\n4. ✅ Experienced team with prior exits\n5. ❌ No reimbursement pathway\n6. ❌ Competes with hospital capital budgets\n7. ❌ Cannibalizes incumbent recurring revenue models\n8. ❌ Marginal improvement over "good enough" status quo\n9. ❌ No physician/patient incentive for adoption\n10. ❌ Market structure aligned against disruption\n\n**Other Examples:**\n- **Digital health apps** (behavior change without reimbursement)\n- **Remote monitoring devices** (competes with in-person visits, no CPT codes)\n- **AI diagnostics** (radiologists threatened, hospitals lack budget for "second opinion" software)\n- **Preventative care devices** (payers don't reimburse for disease prevention, only treatment)\n\n### The "Good Idea, Bad Business" Matrix\n\n|  | Strong Business Model | Weak Business Model |\n|--|----------------------|---------------------|\n| **Strong Clinical Value** | ✅ Watchman (BSX): Reduces stroke + reimbursed | ⚠️ Source-Based Radiation Protection: Reduces exposure, no payment |\n| **Weak Clinical Value** | ✅ Cosmetic Devices: Elective, cash pay | ❌ Vitamin Supplements: OTC, low margin, commoditized |\n\n**Source-based radiation protection lives in the worst quadrant:** Strong clinical value meets weak business model.\n\n---\n\n## Lessons for Founders, Investors, Regulators\n\n### For Founders\n\n**Pre-Commercialization Diligence:**\n\n1. **Reimbursement Before Technology Development**\n   - If no CPT code exists, create reimbursement strategy before Series A\n   - Engage with CMS (Medicare) and private payers during R&D phase\n   - Budget $1-2M for health economics studies (cost-effectiveness analysis)\n\n2. **Hospital Budget Workflow Mapping**\n   - Identify budget source (capital equipment vs. supplies vs. IT)\n   - Map approval process (value analysis committee, CFO, board)\n   - Understand competing priorities (revenue-generating equipment gets preference)\n\n3. **Stakeholder Incentive Analysis**\n   - Physicians: Does device improve outcomes or workflow?\n   - Hospitals: Does device increase revenue or reduce costs?\n   - Payers: Does device reduce total cost of care?\n   - **If all three answers are "no," don't build the company**\n\n4. **Incumbent Response Prediction**\n   - Will your innovation cannibalize existing revenue streams?\n   - Can incumbents lobby against adoption?\n   - Do incumbents have distribution advantages? (GPO contracts, existing relationships)\n\n**Red Flags to Abort Early:**\n- "Hospitals should buy this because it's the right thing to do" (they won't)\n- "Once we have FDA clearance, adoption will follow" (it won't without reimbursement)\n- "We'll partner with a strategic for distribution" (ControlRad tried, failed)\n- "Safety innovations always get adopted eventually" (not without payment mechanism)\n\n### For Investors\n\n**Due Diligence Kill Criteria:**\n\n1. **No Reimbursement Pathway = No Investment**\n   - Exceptions: Elective/cosmetic procedures (cash pay), consumer devices (direct-to-consumer)\n   - MedTech without CPT codes requires 3-5× longer sales cycles and lower ASP\n\n2. **Market Structure Trumps Technology**\n   - Map stakeholder incentives before evaluating clinical data\n   - If incumbents have structural advantages (GPO contracts, recurring revenue models), assume high risk\n\n3. **Capital Efficiency Benchmarks**\n   - Series A: Prototype + pilot customers (2-5)\n   - Series B: Revenue $2-5M, path to $10M\n   - Series C: Revenue $10-20M, path to profitability\n   - **Below these thresholds = bridge rounds, not growth equity**\n\n4. **Strategic Exit Viability Test**\n   - Who are the 5 potential acquirers?\n   - Do they have economic incentive to acquire vs. build internally?\n   - Is the TAM large enough for strategic premium? ($500M+ TAM minimum)\n   - **If no clear strategic buyer, assume venture-scale returns unlikely**\n\n**Portfolio Management:**\n- Source-based radiation protection represents **70-90% loss** scenario\n- Similar to digital health pattern: $1.5B invested → $425M returned (aMoon portfolio)\n- Avoid "technical innovation without business model" trap\n\n### For Regulatory Bodies (FDA, CMS)\n\n**Policy Implications:**\n\n1. **FDA Clearance ≠ Market Adoption**\n   - Safety and efficacy validation insufficient for commercial success\n   - Consider pre-market reimbursement pathway guidance (parallel track with FDA review)\n\n2. **Post-Market Surveillance Bias**\n   - FDA tracks adverse events, not adoption failures\n   - Devices can be "safe and effective" but commercially unviable\n   - Regulatory success rate ≠ market success rate\n\n3. **Reimbursement Coordination**\n   - FDA and CMS operate independently (technology approval vs. payment decisions)\n   - Creates "valley of death" for devices cleared but not reimbursed\n   - Recommendation: Joint FDA-CMS pathway for novel device categories\n\n---\n\n## The Radiaction-Specific Diagnosis\n\n### Immediate Challenges (2025)\n\n**Fundraising Environment:**\n- Series C2 closed August 2023 ($12.6M)\n- 18-month runway implies Q1-Q2 2025 financing decision\n- Macro headwinds: MedTech venture funding down 30% YoY (2024 vs. 2023)\n- ControlRad closure signals category risk to investors\n\n**Commercial Traction Metrics:**\n- Estimated 30-70 installations over 2.5 years post-FDA clearance\n- Implies 1-2 installations per month (insufficient for venture-scale returns)\n- Requires 10× acceleration to reach $50M revenue (strategic acquisition threshold)\n- **Probability of 10× acceleration: <5%** (no comparable precedent)\n\n**Team/Operational Red Flags:**\n- US President/CCO appointed October 2023 (indicates slow US commercialization pre-2023)\n- Medical Advisory Board formed August 2024 (late-stage clinical validation efforts)\n- Cassling distribution partnership (non-exclusive, limited to "various territories")\n- No announcements of major hospital system deployments or multi-site contracts\n\n### The Uncomfortable Questions for Leadership\n\n**For CEO (Jonathan Yifat):**\n\n1. **"Since FDA clearance (April 2022), where has reality pushed back harder than you expected?"**\n   - Listen for: Budget committees, procurement timelines, competitor response, physician adoption\n   - Red flag answers: "We just need more time" / "Hospitals love the technology"\n\n2. **"What's the path to $50M revenue, and which variables are within your control vs. external?"**\n   - Forces distinction between execution risk (can fix) vs. market structure risk (can't fix)\n   - ControlRad had execution excellence + BSX partnership, still failed\n\n3. **"If you were a hospital CFO with a $5M capital budget, why would you choose Radiaction over new imaging equipment or robotic surgery?"**\n   - Tests understanding of customer ROI calculus\n   - Radiation protection competes with revenue-generating equipment\n\n4. **"What's different about Radiaction's approach that explains why you'll succeed where ControlRad failed?"**\n   - ControlRad had: FDA clearance, Boston Scientific exclusive distribution, clinical trials, $43.6M funding\n   - If answer is "better technology," that's insufficient\n\n5. **"Walk me through your last three lost deals—why did hospitals decide not to purchase?"**\n   - Reveals pattern: Price objection vs. competitor vs. "not now" vs. "not convinced"\n   - If pattern is consistent, indicates market structure issue, not execution\n\n### The Hard Truths\n\n**What Radiaction Leadership Likely Believes:**\n- "We have better technology than ControlRad" (may be true)\n- "ControlRad failed due to execution issues" (partially true, but insufficient explanation)\n- "If we can get to 100 installations, hockey stick growth will follow" (unlikely, violates ControlRad precedent)\n- "Strategic acquisition is realistic in 2-3 years" (incompatible with market structure)\n\n**What Evidence Suggests:**\n- FDA clearance (April 2022) to present = 2.5 years, estimated 30-70 installations\n- Requires 4-6× acceleration to reach strategic acquisition threshold\n- ControlRad had 3-4 years with Boston Scientific partnership, closed anyway\n- No strategic buyer has demonstrated willingness to acquire in this category\n- PPE incumbents strengthened position (Burlington won Premier GPO contract Nov 2025)\n\n**Base Rate Analysis:**\n- Source-based radiation protection companies founded: 2 (ControlRad, Radiaction)\n- Successful exits: 0\n- Ongoing viability: 1 (Radiaction, cash runway 12-18 months)\n- **Base rate of success: 0%** (as of January 2025)\n\n---\n\n## Recommendations\n\n### For Radiaction Leadership\n\n**If Committed to Continuing (Against Evidence):**\n\n1. **Pivot to OEM Model**\n   - Stop direct hospital sales (too slow, too expensive)\n   - License technology to Siemens/Philips as bundled C-arm feature\n   - Accept lower margins ($5-10M total deal) but faster path to exit\n   - **Challenge:** Why would Siemens pay for technology they can build internally?\n\n2. **Focus on Reimbursement Advocacy**\n   - Lobby for CPT code creation (Category III code for novel services)\n   - Fund health economics study demonstrating cost savings from reduced staff injury\n   - Engage professional societies (SCAI, SIR, HRS) to petition CMS\n   - **Timeline:** 3-5 years minimum for CPT code approval (burns more cash than available)\n\n3. **Geographic Arbitrage**\n   - Exit US market (too competitive, no reimbursement)\n   - Focus on Europe/Asia where radiation safety regulations stricter\n   - Target countries with national health systems (single payer = easier adoption)\n   - **Challenge:** International expansion requires additional regulatory approvals + capital\n\n**If Considering Wind Down (Recommended):**\n\n1. **Maximize Residual Value**\n   - Approach Siemens/Philips for IP acquisition ($5-10M range)\n   - Sell customer contracts to service provider\n   - Return remaining capital to investors (40-60% recovery possible)\n\n2. **Transparent Communication**\n   - Avoid "bridge round" that delays inevitable (burns remaining capital)\n   - Board should assess: Is path to profitability realistic within 24 months?\n   - If answer is "no," controlled wind-down preserves reputation + investor relationships\n\n3. **Team Transition**\n   - Radiaction has strong engineering/regulatory talent (valuable to other MedTech)\n   - Acqui-hire scenario: Larger MedTech acquires team for different product line\n   - Better outcome than insolvency/bankruptcy\n\n---\n\n## Consultant's Meeting Script (Tomorrow's 1:1)\n\n**Your Opening (Revised):**\n\n"Jonathan, I appreciate you carving out time before the working session. I wanted to share some context on where I'm coming from.\n\nI'm an ex-physicist, and over the years I've worked on 70+ clinical trials and was involved in five FDA clearances across MedTech and AI. We sold that company about two years ago.\n\nOne thing that's stood out across those teams is a recurring pattern post-clearance. It's not about any single function—engineering, regulatory, clinical. What changes after clearance is that reality starts pushing back at the weakest interface. Sometimes it's workflow, sometimes procurement, sometimes hospital risk committees, sometimes internal coordination between your commercial team and the actual decision-makers in hospitals.\n\nMost teams expect technical validation to be the hard part. The surprise is that once that's done, a different set of constraints suddenly dominates—and often those constraints are external to the company, embedded in how hospitals make capital allocation decisions.\n\n**Since your clearance in April 2022, where has reality pushed back harder than you expected?**\n\nI'm asking because I did some research on the category after you reached out, and I saw ControlRad's trajectory. I know they had FDA clearance, clinical trials, and an exclusive distribution deal with Boston Scientific. From the outside, it looked like they had all the pieces in place. Yet Crunchbase shows them as permanently closed.\n\nI don't know the inside story, but it made me curious: **what do you think happened there, and what's different about Radiaction's path?**\n\nThe reason I'm asking is not to be difficult—it's because I've seen this pattern before in other categories where the technology works, the regulatory path is clear, but adoption doesn't follow the expected curve. And when that happens, it's usually not an execution problem—it's a structural problem with how the market assigns budget priority, how procurement works, or how reimbursement flows.\n\nIf we're going to build an effective threat model together this afternoon, I want to make sure I'm calibrating risk in the right places. Sometimes the highest risk isn't in the device itself—it's in the gap between what the technology enables and what the market is actually structured to pay for.\n\n**So: since clearance, where has reality pushed back harder than you expected?** And **what gives you confidence that the path forward looks different than what ControlRad experienced?**"\n\n### What to Listen For\n\n**Strong Answers (Suggests Leadership Awareness):**\n- "Hospital capital committees are the real bottleneck, not physicians"\n- "We've shifted strategy from direct sales to OEM partnerships"\n- "Reimbursement is the missing piece; we're funding a health economics study"\n- "We're seeing 12-18 month sales cycles, which is burning cash faster than projected"\n\n**Weak Answers (Red Flags):**\n- "ControlRad failed because they didn't have our technology"\n- "We just need more time for hospitals to see the value"\n- "Our strategic partnership with Cassling will change things"\n- "The market is starting to shift in our direction"\n\n**Danger Answers (Abort Mission):**\n- "ControlRad's closure doesn't concern us—we're different"\n- "Hospitals love our technology, it's just a matter of scaling sales"\n- "We're confident we'll get acquired in the next 2-3 years"\n- Avoids answering or deflects to technical superiority\n\n### Your Decision Tree Post-Conversation\n\n1. **If Strong Answers → Proceed with threat model work**\n   - They're self-aware about market structure challenges\n   - Your FDA cyber work helps them survive longer to attempt pivot\n   - You're helping a team that might find an exit path\n\n2. **If Weak Answers → Proceed with Caution**\n   - Deliver excellent FDA cyber work (professional reputation)\n   - Do not accept equity in lieu of cash payment\n   - Treat as consulting engagement, not partnership opportunity\n\n3. **If Danger Answers → Deliver Contract, Exit Cleanly**\n   - Complete the statement of work as agreed\n   - Do not engage on strategic advice (they won't listen)\n   - Preserve relationship with Shlomit (RA/QA lead) for future opportunities\n\n### Optional Follow-Up (If Conversation Goes Well)\n\n"Would it be useful if I documented some of what I've learned about market structure challenges in this category? Not as a formal report, but as a pattern analysis—here's what I've observed in similar situations, here are the variables that matter most, here are the questions to ask when deciding on next steps.\n\nI'm not saying you should do X or Y—that's your decision as CEO. But sometimes having an outside perspective that's seen adjacent patterns can help clarify strategic options. No charge—I'm documenting this for my own pattern library anyway, and Radiaction would be a useful case study."\n\n**If he says yes:** You've opened the door to influence strategic thinking without being prescriptive.  \n**If he says no:** You've signaled awareness without overstepping, and you can deliver excellent FDA cyber work.\n\n---\n\n## Conclusion: Pattern Complete\n\nSource-based radiation protection in interventional radiology is a **validated anti-pattern**:\n\n- **Clinical value:** ✅ Real, measurable, scientifically validated\n- **Technical feasibility:** ✅ FDA-cleared, proven in clinical trials\n- **Market demand:** ❌ Misaligned with hospital economics, reimbursement, and stakeholder incentives\n- **Business model:** ❌ One-time capital sale with no recurring revenue\n- **Exit viability:** ❌ No strategic buyer, no venture-scale returns\n\n**Capital efficiency:** 0.11× (ControlRad + Radiaction combined)  \n**Base rate of success:** 0% (no successful exits as of January 2025)  \n**Estimated investor recovery:** 10-25% of invested capital\n\n**For founders:** Avoid categories where incumbents have structural advantages (GPO contracts, recurring revenue models) and no reimbursement pathway exists.\n\n**For investors:** "Good technology" ≠ "Good business." Market structure trumps innovation in MedTech without payment mechanisms.\n\n**For Radiaction specifically:** Without dramatic pivot (OEM licensing, reimbursement breakthrough, geographic shift), path to positive exit is <10% probable within 2-3 year horizon.\n\n---\n\n## Related Patterns\n\n- **Digital Health Investment Destruction** (aMoon: $1.5B → $425M, 72% loss)\n- **AI Diagnostics Without Reimbursement**\n- **Remote Patient Monitoring Pre-CPT Code**\n- **Preventative Care Device Market Structure Failure**\n- **Safety Innovation vs. Revenue Generation Capital Competition**\n\n---\n\n## Pattern Factory Metadata\n\n**Document Type:** Anti-Pattern Analysis  \n**Industry:** MedTech / Interventional Radiology  \n**Stage:** Post-FDA Clearance Commercialization  \n**Capital Destroyed:** $90M+  \n**Companies Analyzed:** ControlRad (closed), Radiaction (active, at risk)  \n**Time Period:** 2011-2025 (14 years)  \n**Validation Status:** High confidence (market exit validates thesis)  \n**Related Anti-Patterns:** Reimbursement desert, incumbent cannibalization risk, capital budget competition  \n**Strategic Implication:** Technical innovation insufficient without market structure alignment  \n\n**Tags:** #MedTech #BusinessModelFailure #ReimbursementRisk #MarketStructure #CapitalEfficiency #StrategicAcquisition #VentureReturns #RadiationProtection #InterventionalRadiology #AntiPattern\n\n---\n\n**Next Steps for Pattern Factory Integration:**\n1. Cross-reference with digital health investment destruction pattern (aMoon portfolio)\n2. Create decision tree: "When to abort MedTech opportunity pre-Series A"\n3. Build stakeholder incentive mapping framework (physicians, hospitals, payers, incumbents)\n4. Develop "Good Idea, Bad Business" matrix for rapid triage\n5. Interview ControlRad investors/team (if accessible) for insider perspective\n6. Track Radiaction over next 12-18 months to validate predictions\n7. Generalize pattern to "Safety Innovation Without Reimbursement" category\n\n**Document Status:** Draft from Radiaction prep session\n**Last Updated:** January 27, 2026  \n**Author:** Danny Lieberman\n**Review Status:** Self-reviewed (recommend peer review from MedTech investors/operators)\n	1	MedTech	Investors	Draft	52	2026-01-27 16:03:54.439463	2026-02-03 12:32:30.789853
124cd230-f665-4926-b037-8388d842fafb	Vectorious	TM workflow	Company Vectorious Medical Technologies\nFounded: 2011\n\nStage: Clinical\n\nFunding: 35M\n\nRevenue: Not publicly disclosed\n\nEnterprise valuation: $497M\n\nFixed asset pool: $397M\n\nRecurring asset pool: $100M\n\nProduct\nFDA IDE G220071 / NCT06147336: V-LAP System\n\nPanel: Cardiovascular\n\nClassification Product code: Investigational device – not yet assigned\n\nAssets\nA1 Clinical Safety and Treatment Integrity Tier 1 fixed_value 90000000 recurring_value 0\n\nA2 V-LAP Implant and Sensor Intellectual Property Tier 1 fixed_value 80000000 recurring_value 0\n\nA3 Measurement Accuracy and Calibration Tier 1 fixed_value 65000000 recurring_value 0\n\nA4 Regulatory Pathway and Clinical Evidence Tier 1 fixed_value 65000000 recurring_value 0\n\nA5 Longitudinal LAP Dataset and Algorithms Tier 2 fixed_value 35000000 recurring_value 10000000\n\nA6 Wireless Power and Communication Integrity Tier 2 fixed_value 35000000 recurring_value 0\n\nA7 Patient Self-Management Platform Tier 2 fixed_value 10000000 recurring_value 20000000\n\nA8 Physician Monitoring and Clinical Workflow Tier 2 fixed_value 5000000 recurring_value 20000000\n\nA9 Cloud and Software Platform Availability Tier 3 fixed_value 0 recurring_value 20000000\n\nA10 Patient Data Confidentiality Tier 2 fixed_value 5000000 recurring_value 10000000\n\nA11 Manufacturing and Supply-Chain Quality Tier 2 fixed_value 7000000 recurring_value 8000000\n\nA12 Reputation and Strategic Value Tier 2 fixed_value 0 recurring_value 12000000\n\nThreat R1\n\nTag: R1\n\nName: Inaccurate LAP measurement due to drift or algorithm error\n\nDescription: Inaccurate LAP measurement due to drift or algorithm error\n\nDomain: CLINICAL\n\nProbability: 12\n\nAffects Assets: A1, A3, A4, A5, A12\n\nDamage: 100\n\nVulnerability\n\nSensor drift, calibration bias, signal-processing defects, environmental variation, or algorithm errors produce a left atrial pressure value that appears technically valid but does not represent the patient’s true physiological state.\n\nCountermeasures\n\nCM1 - End-to-end calibration and drift monitoring mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 120000\n\nCM2 - Measurement confidence and physiological plausibility scoring mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nCM3 - Longitudinal clinical performance monitoring by device and cohort mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 100000\n\nThreat R2\n\nTag: R2\n\nName: Wireless power or communication failure prevents a reading\n\nDescription: Wireless power or communication failure prevents a reading\n\nDomain: OPERATIONAL\n\nProbability: 15\n\nAffects Assets: A1, A3, A6, A8, A9\n\nDamage: 85\n\nVulnerability\n\nImplant-reader misalignment, insufficient wireless power transfer, interference, external reader failure, network loss, or communication protocol errors prevent the system from obtaining or transmitting a reliable LAP measurement.\n\nCountermeasures\n\nCM4 - Real-time link quality and power-transfer validation mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 100000\n\nCM5 - Store-and-forward delivery with retry and integrity verification mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 80000\n\nCM6 - Patient guidance and automated troubleshooting for reader alignment mitigation_level 85 recurring_implementation_cost 25000 fixed_implementation_cost 60000\n\nThreat R3\n\nTag: R3\n\nName: Patient guidance uses corrupted or stale pressure data\n\nDescription: Patient guidance uses corrupted or stale pressure data\n\nDomain: CLINICAL\n\nProbability: 8\n\nAffects Assets: A1, A3, A7, A8, A12\n\nDamage: 100\n\nVulnerability\n\nThe patient self-management application generates guidance using delayed, duplicated, incomplete, corrupted, or clinically invalid LAP measurements, potentially causing inappropriate medication adjustment or delayed escalation.\n\nCountermeasures\n\nCM7 - Measurement freshness, completeness, and sequence validation mitigation_level 90 recurring_implementation_cost 25000 fixed_implementation_cost 75000\n\nCM8 - Physician-approved treatment guardrails and dose-change limits mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 100000\n\nCM9 - Fail-safe workflow that withholds guidance when data confidence is insufficient mitigation_level 95 recurring_implementation_cost 25000 fixed_implementation_cost 80000\n\nThreat R4\n\nTag: R4\n\nName: Unauthorized firmware or software modification\n\nDescription: Unauthorized firmware or software modification\n\nDomain: CYBER\n\nProbability: 5\n\nAffects Assets: A1, A2, A3, A4, A6, A12\n\nDamage: 100\n\nVulnerability\n\nUnauthorized or unintended changes to implant firmware, embedded software, reader software, mobile applications, cloud services, or clinical web clients alter how the implant is powered, interrogated, interpreted, or presented.\n\nCountermeasures\n\nCM10 - Secure boot and hardware-backed root of trust mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 180000\n\nCM11 - Cryptographically signed software and firmware with anti-rollback mitigation_level 90 recurring_implementation_cost 35000 fixed_implementation_cost 150000\n\nCM12 - Reproducible builds, provenance attestation, and protected release pipeline mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 140000\n\nThreat R5\n\nTag: R5\n\nName: Patient, implant, or monitoring session associated incorrectly\n\nDescription: Patient, implant, or monitoring session associated incorrectly\n\nDomain: OPERATIONAL\n\nProbability: 7\n\nAffects Assets: A1, A3, A7, A8, A10\n\nDamage: 95\n\nVulnerability\n\nEnrollment, pairing, account provisioning, device replacement, clinical-site workflow, or data-integration errors associate measurements or guidance with the wrong patient, implant, reader, or monitoring session.\n\nCountermeasures\n\nCM13 - Cryptographic patient-implant-reader binding mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 100000\n\nCM14 - Positive patient identification and two-person enrollment verification mitigation_level 90 recurring_implementation_cost 25000 fixed_implementation_cost 70000\n\nCM15 - Automated reconciliation with clinical study and healthcare records mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nThreat R6\n\nTag: R6\n\nName: Unauthorized access to clinical monitoring APIs\n\nDescription: Unauthorized access to clinical monitoring APIs\n\nDomain: PRIVACY\n\nProbability: 10\n\nAffects Assets: A7, A8, A9, A10, A12\n\nDamage: 75\n\nVulnerability\n\nWeak authentication, authorization, tenant isolation, token handling, or API design allows unauthorized parties to access patient measurements, clinical functions, treatment guidance, or administrative capabilities.\n\nCountermeasures\n\nCM16 - OAuth2 or OIDC with phishing-resistant multi-factor authentication mitigation_level 90 recurring_implementation_cost 35000 fixed_implementation_cost 100000\n\nCM17 - Fine-grained role-based and attribute-based authorization mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nCM18 - API gateway monitoring, rate limiting, and anomaly detection mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 90000\n\nThreat R7\n\nTag: R7\n\nName: Monitoring platform unavailable during clinical use\n\nDescription: Monitoring platform unavailable during clinical use\n\nDomain: OPERATIONAL\n\nProbability: 12\n\nAffects Assets: A1, A7, A8, A9\n\nDamage: 70\n\nVulnerability\n\nCloud, identity, database, messaging, mobile, web, or network failures interrupt access to measurements, patient guidance, physician monitoring, or study operations.\n\nCountermeasures\n\nCM19 - Multi-zone high-availability architecture and dependency isolation mitigation_level 90 recurring_implementation_cost 70000 fixed_implementation_cost 150000\n\nCM20 - Disaster recovery with tested recovery-time and recovery-point objectives mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 120000\n\nCM21 - Graceful degradation and offline continuity for critical workflows mitigation_level 85 recurring_implementation_cost 40000 fixed_implementation_cost 120000\n\nThreat R8\n\nTag: R8\n\nName: CI/CD or software supply-chain compromise\n\nDescription: CI/CD or software supply-chain compromise\n\nDomain: SUPPLYCHAIN\n\nProbability: 4\n\nAffects Assets: A1, A2, A3, A4, A5, A7, A9\n\nDamage: 95\n\nVulnerability\n\nCompromised source repositories, developer credentials, build systems, third-party packages, artifact repositories, or release infrastructure introduce malicious or vulnerable software into the V-LAP system.\n\nCountermeasures\n\nCM22 - SBOM, dependency scanning, and continuous vulnerability monitoring mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 100000\n\nCM23 - Protected branches, privileged-access controls, and developer MFA mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 80000\n\nCM24 - Signed build artifacts and independently verified build provenance mitigation_level 90 recurring_implementation_cost 45000 fixed_implementation_cost 130000\n\nThreat R9\n\nTag: R9\n\nName: Cybersecurity evidence is insufficient for regulatory review\n\nDescription: Cybersecurity evidence is insufficient for regulatory review\n\nDomain: REGULATORY\n\nProbability: 9\n\nAffects Assets: A4, A9, A11, A12\n\nDamage: 80\n\nVulnerability\n\nThe security risk-management file does not demonstrate traceability from architecture and threats to vulnerabilities, controls, verification evidence, residual risk, and post-market processes.\n\nCountermeasures\n\nCM25 - Cybersecurity traceability matrix linked to system and clinical risk mitigation_level 90 recurring_implementation_cost 25000 fixed_implementation_cost 100000\n\nCM26 - Independent penetration testing and control-effectiveness verification mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 120000\n\nCM27 - Regulatory readiness reviews and evidence-completeness gates mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 80000\n\nThreat R10\n\nTag: R10\n\nName: Implant identity spoofing or replay of measurements\n\nDescription: Implant identity spoofing or replay of measurements\n\nDomain: CYBER\n\nProbability: 5\n\nAffects Assets: A1, A3, A6, A7, A8\n\nDamage: 90\n\nVulnerability\n\nWeak device identity, key protection, freshness validation, or mutual authentication allows fabricated, substituted, or previously captured measurements to be accepted as current data from a legitimate implant.\n\nCountermeasures\n\nCM28 - Hardware-backed implant and reader identity mitigation_level 90 recurring_implementation_cost 35000 fixed_implementation_cost 140000\n\nCM29 - Mutual authentication with device-specific certificates and managed key lifecycle mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 130000\n\nCM30 - Nonces, sequence numbers, timestamps, and replay detection mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nThreat R11\n\nTag: R11\n\nName: Long-term implant or sensor degradation is not detected\n\nDescription: Long-term implant or sensor degradation is not detected\n\nDomain: CLINICAL\n\nProbability: 8\n\nAffects Assets: A1, A2, A3, A4, A5\n\nDamage: 95\n\nVulnerability\n\nMaterial aging, encapsulation, mechanical stress, biological environment, electronic drift, or long-term changes in wireless coupling degrade implant performance without timely detection.\n\nCountermeasures\n\nCM31 - Accelerated aging and lifetime performance characterization mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 180000\n\nCM32 - Longitudinal drift detection using patient and population baselines mitigation_level 90 recurring_implementation_cost 45000 fixed_implementation_cost 110000\n\nCM33 - Post-market performance surveillance with predefined escalation thresholds mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 100000\n\nThreat R12\n\nTag: R12\n\nName: Third-party cloud or mobile dependency is compromised\n\nDescription: Third-party cloud or mobile dependency is compromised\n\nDomain: SUPPLYCHAIN\n\nProbability: 7\n\nAffects Assets: A7, A8, A9, A10, A12\n\nDamage: 85\n\nVulnerability\n\nA compromise or material outage affecting a cloud, mobile operating system, notification, identity, analytics, hosting, or software supplier exposes data or interrupts critical V-LAP services.\n\nCountermeasures\n\nCM34 - Supplier security requirements, evidence review, and contractual notification mitigation_level 85 recurring_implementation_cost 30000 fixed_implementation_cost 70000\n\nCM35 - Architectural isolation and least-privilege access for third-party services mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 110000\n\nCM36 - Dependency health monitoring, substitution plans, and tested failover mitigation_level 85 recurring_implementation_cost 45000 fixed_implementation_cost 120000\n\nThreat R13\n\nTag: R13\n\nName: Longitudinal patient data is exposed\n\nDescription: Longitudinal patient data is exposed\n\nDomain: PRIVACY\n\nProbability: 8\n\nAffects Assets: A5, A7, A8, A10, A12\n\nDamage: 70\n\nVulnerability\n\nWeak access control, encryption, key management, data minimization, cloud configuration, logging, or endpoint protection exposes longitudinal LAP measurements, patient activity, treatment guidance, or study information.\n\nCountermeasures\n\nCM37 - Encryption in transit and at rest with managed key rotation mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 80000\n\nCM38 - Pseudonymization, data minimization, and environment segregation mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nCM39 - Continuous access monitoring and data-loss detection mitigation_level 85 recurring_implementation_cost 40000 fixed_implementation_cost 90000\n\nThreat R14\n\nTag: R14\n\nName: Manufacturing or calibration variation changes measurement accuracy\n\nDescription: Manufacturing or calibration variation changes measurement accuracy\n\nDomain: OPERATIONAL\n\nProbability: 10\n\nAffects Assets: A1, A2, A3, A4, A11\n\nDamage: 85\n\nVulnerability\n\nMaterial, component, assembly, packaging, calibration, test, sterilization, or supplier variation shifts device performance outside the validated measurement envelope.\n\nCountermeasures\n\nCM40 - Unit-level calibration with traceable reference standards mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 160000\n\nCM41 - Statistical process control and automated manufacturing test limits mitigation_level 90 recurring_implementation_cost 45000 fixed_implementation_cost 140000\n\nCM42 - Supplier change control and incoming component verification mitigation_level 90 recurring_implementation_cost 40000 fixed_implementation_cost 110000\n\nThreat R15\n\nTag: R15\n\nName: Audit trail cannot reconstruct measurements and treatment decisions\n\nDescription: Audit trail cannot reconstruct measurements and treatment decisions\n\nDomain: REGULATORY\n\nProbability: 6\n\nAffects Assets: A1, A4, A7, A8, A9\n\nDamage: 80\n\nVulnerability\n\nLogs lack synchronized time, device and software version, measurement provenance, user activity, guidance rationale, acknowledgement, or tamper resistance required to reconstruct a clinical or security event.\n\nCountermeasures\n\nCM43 - Tamper-evident audit logging with trusted time synchronization mitigation_level 90 recurring_implementation_cost 35000 fixed_implementation_cost 100000\n\nCM44 - End-to-end measurement and decision provenance mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nCM45 - Retention, review, and regulatory reconstruction exercises mitigation_level 85 recurring_implementation_cost 30000 fixed_implementation_cost 70000\n\nThreat R16\n\nTag: R16\n\nName: Security vulnerabilities remain unremediated after implantation\n\nDescription: Security vulnerabilities remain unremediated after implantation\n\nDomain: CYBER\n\nProbability: 6\n\nAffects Assets: A1, A2, A4, A6, A7, A9, A12\n\nDamage: 90\n\nVulnerability\n\nThe product cannot identify, assess, communicate, mitigate, or safely remediate newly disclosed vulnerabilities across implanted, external, mobile, cloud, web, and third-party components over the supported lifetime.\n\nCountermeasures\n\nCM46 - Coordinated vulnerability disclosure and product-security response process mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 90000\n\nCM47 - Continuous SBOM and exploitability monitoring across supported versions mitigation_level 90 recurring_implementation_cost 55000 fixed_implementation_cost 110000\n\nCM48 - Secure update capability with risk-based patching and compensating controls mitigation_level 90 recurring_implementation_cost 60000 fixed_implementation_cost 180000\n\nThreat R17\n\nTag: R17\n\nName: False elevated pressure results in unnecessary treatment\n\nDescription: False elevated pressure results in unnecessary treatment\n\nDomain: CLINICAL\n\nProbability: 11\n\nAffects Assets: A1, A3, A7, A8, A12\n\nDamage: 90\n\nVulnerability\n\nNoise, drift, calibration error, transient physiology, data-processing defects, or incorrect interpretation produces an elevated LAP value that triggers unnecessary medication change, patient anxiety, or clinical intervention.\n\nCountermeasures\n\nCM49 - Repeated-measurement confirmation and trend-based decision rules mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 90000\n\nCM50 - Physician-configured treatment limits and exception handling mitigation_level 90 recurring_implementation_cost 30000 fixed_implementation_cost 80000\n\nCM51 - Patient application warnings and escalation for unexpected readings mitigation_level 85 recurring_implementation_cost 25000 fixed_implementation_cost 70000\n\nThreat R18\n\nTag: R18\n\nName: Cyber incident disrupts an active clinical study\n\nDescription: Cyber incident disrupts an active clinical study\n\nDomain: REGULATORY\n\nProbability: 5\n\nAffects Assets: A4, A5, A7, A8, A9, A10, A12\n\nDamage: 85\n\nVulnerability\n\nRansomware, account compromise, data corruption, service outage, or loss of study evidence interrupts enrollment, monitoring, patient guidance, safety reporting, data integrity, or regulatory timelines.\n\nCountermeasures\n\nCM52 - Clinical-study-specific cyber incident response and communication plan mitigation_level 90 recurring_implementation_cost 35000 fixed_implementation_cost 80000\n\nCM53 - Immutable backups and validated recovery of study and audit evidence mitigation_level 90 recurring_implementation_cost 50000 fixed_implementation_cost 120000\n\nCM54 - Site continuity exercises and alternate clinical workflows mitigation_level 85 recurring_implementation_cost 40000 fixed_implementation_cost 100000	1	RISK-MODELING	Analysts	Evolving	23	2026-02-03 12:52:36.81378	2026-07-20 21:02:29.132119
497b2dba-d545-4de2-97cb-7833f07f342e	Radiaction risk scenarios 0.5	Radiaction FDA Cyber	# Risks\n\n## Controlled Domains are:\n- PHYSICAL_SECURITY\n- SUPPLY_CHAIN\n- INSIDER_THREAT\n- CYBER_PHYSICAL\n- OPERATIONAL_PROCESS\n\n## Database conventions **\n- All tables are in the threat. Schema\n- Damage is in asset_threat.damage column \n- Probability is in threats.probability column\n- Model name is in models.name\n---\n\n## Model name: Radiaction\n\n## Threat R1\n- Tag: R1\n- Name: Change Preset Configuration\n- Domain:CYBER_PHYSICAL\n- Probability 0.4\n- Affects Assets: A2, A6\n- Damage:30\n\n**Vulnerability:** No password required \n\n**Countermeasures:**\n- CM1 – Employee training mitigation level 80\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R2 \n- Tag: R2\n- Name: Supply chain attack\n- Domain:SUPPLY_CHAIN\n- Probability: 0.2\n- Affects Assets: A3, A6, A2\n- Damage:100\n\n**Vulnerability:** PLC and sensor firmware integrity\n\n**Countermeasures:**\n- CM2 – Multiple ATP tests mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM3 – Test on jig before shipment mitigation level 95\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM4 – Site inspection mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R3 \n- Tag: R3\n- Name: Remove System Plug\n- Domain: PHYSICAL_SECURITY\n- Probability: 0.3\n- Affects Assets: A6, A2\n- Damage:30\n\n**Vulnerability:** Unrestricted physical access\n\n**Countermeasures:**\n- CM5 – Power-loss indicator mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM6 – Physical locking mechanism on system cable mitigation level 95\n- recurring_implementation_cost 100 fixed_implementation_cost 0\n\n---\n\n## Threat R4\n- Tag: R4\n- Name: Field Service Rep Unauthorized Change\n- Domain: INSIDER_THREAT\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Shared credentials / technician mode persistence\n\n**Countermeasures:**\n- CM7 – Vetting process mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM8 – Training mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM9 – Service reports mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM10 – ATP mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM11 – Periodic clinical team checks mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R5 \n- Tag: R5\n– Name: Sabotage \n- Domain: PHYSICAL_SECURITY\n- Probability: 0.1\n- Affects Assets: A6, A2, A4\n- Damage: 100\n\n**Vulnerability:** Physical access to system in hospital Cath lab\n\n**Countermeasures:**\n- CM12 – Sealed system mitigation level 90\n- recurring_implementation_cost 0  fixed_implementation_cost 0\n- CM13 – Hospital physical security mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R6 \n- Tag: R6\n- Name: Change Sensor Parameters\n- Domain:CYBER_PHYSICAL\n\n- Probability: 0.2\n- Affects Assets:A6, A2\n- Damage: 60\n\n**Vulnerability:** USB access without authentication\n\n**Countermeasures:**\n- CM14 – Controlled room access mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM15 – Tool access control mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM16 – Dedicated interface software mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM17 – Proprietary protocol mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R7\n- Tag: R7\n- Name: Software Hack or Attack\n- Domain:CYBER_PHYSICAL\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Hard-coded and shared passwords in CODESYS\n\n**Countermeasures:**\n- CM18 – Strong password policy mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 1000\n- CM19 – Physical barriers mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM20 – Equipment locked away mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n	1	MedTech	RA/QA, Cyber	Draft	23	2026-02-03 12:11:36.957942	2026-02-15 11:45:13.694862
c89552dc-420a-4459-9004-216cf107f7ac	Radiaction risk scenarios 1.0	Radiaction FDA Cyber	# Assets\n\nA1\tCustomer satisfaction\trecurring_value 1000000 fixed_value 0\n\nA2\tPatient safety\trecurring_value 3000000 fixed_value 0\n\nA3\tSupply chain\trecurring_value 0 fixed_value 500000\n\nA4\tReputation\trecurring_value 0 fixed_value 1000000\n\nA5\tComponents recurring_value 0 fixed_value 25000\n\nA6\tSystem\trecurring_value 200000 fixed_value 0\n\nA7\tSoftware development and runtime recurring_value 0 fixed_value 100000\n\n\n# Risks\n\n## Controlled Domains are:\n- PHYSICAL_SECURITY\n- SUPPLY_CHAIN\n- INSIDER_THREAT\n- CYBER_PHYSICAL\n- OPERATIONAL_PROCESS\n- PATIENT_SAFETY\n- MEDICAL_STAFF_SAFETY\n\n## Database conventions **\n- All tables are in the threat. Schema\n- Damage is in asset_threat.damage column \n- Probability is in threats.probability column\n- Model name is in models.name\n---\n\n## Model name: Radiaction\n\n## Threat R1\n- Tag: R1\n- Name: Preset configuration may be changed in the support station UI\n- Domain:CYBER_PHYSICAL\n- Probability 0.4\n- Affects Assets: A2, A6\n- Damage:30\n\n**Vulnerability:** No password required to change the preset by the operator\n\n**Countermeasures:**\n- CM1 – Hospital employee training mitigation level 80\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R2 \n- Tag: R2\n- Name: Supply chain attack\n- Domain:SUPPLY_CHAIN\n- Probability: 0.2\n- Affects Assets: A3, A6, A2\n- Damage:100\n\n**Vulnerability:** PLC, sensors integrity may be compromised between manufacturing and hospital\n\n**Countermeasures:**\n- CM2 – Multiple ATP tests mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM3 – Test on jig before sending to customer mitigation level 95\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM4 – Site inspection mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R3 \n- Tag: R3\n- Name: System power is disconnected by mistake\n- Domain: PHYSICAL_SECURITY\n- Probability: 0.3\n- Affects Assets: A6, A2\n- Damage:30\n\n**Vulnerability:**The power cable may be disconnected by mistake\n\n**Countermeasures:**\n- CM5 – System power light will turn off to indicate issue mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM6 – Physical locking mechanism on system side of the cable, segment locking mechanism mitigation level 95\n- recurring_implementation_cost 100 fixed_implementation_cost 0\n\n---\n\n## Threat R4\n- Tag: R4\n- Name: Field Service Rep makes an unauthorized change to system\n- Domain: INSIDER_THREAT\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Field service may share maintenance password with an attacker or didn't log out of technician mode\n\n**Countermeasures:**\n- CM7 – Vetting process mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM8 – Training mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM9 – Service reports mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM10 – ATP mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM11 – Clinical team  periodically verifies that system is online and not in technician mode mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R5 \n- Tag: R5\n– Name: System is sabotaged \n- Domain: PHYSICAL_SECURITY\n- Probability: 0.1\n- Affects Assets: A6, A2, A4\n- Damage: 100\n\n**Vulnerability:** People have physical access to electrophysiology lab \n\n**Countermeasures:**\n- CM12 – Support station is sealed mitigation level 90\n- recurring_implementation_cost 0  fixed_implementation_cost 0\n- CM13 – Controlled access to electrophysiology lab mitigation level 90\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R6 \n- Tag: R6\n- Name: An unauthorized change is made to sensor parameters\n- Domain:CYBER_PHYSICAL\n\n- Probability: 0.2\n- Affects Assets:A6, A2\n- Damage: 60\n\n**Vulnerability:** After physical access is obtained to the USB maintenance port, additional user authentication is not performed\n\n**Countermeasures:**\n- CM13 – Controlled access to electrophysiology lab 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM16 – Dedicated interface software mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM17 – An attacker would need to reverse-engineer the proprietary protocol used by the sensors mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R7\n- Tag: R7\n- Name: Software Hack or local attack on support station\n- Domain:CYBER_PHYSICAL\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Attacker may gain access to maintenance password\n\n**Countermeasures:**\n- CM18 – Strong password policy mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 1000\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM20 – Equipment locked away mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R8\n- Tag: R8\n- Name: CODESys runtime issues impact correct system operation\n- Domain:SUPPLY_CHAIN\n- Probability: 0.1\n- Affects Assets: A7\n- Damage: 80\n\n**Vulnerability:** CODESYS runtime in deployed system may have unpatched issues\n\n**Countermeasures:**\n- CM21 - CODESys implements an ongoing software security program mitigation level 90\n- CM22 - Radiaction implements an ongoing patch policy for CODESys mitigation level 90\n- CM2 – Multiple ATP tests mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM3 – Test on jig before shipment mitigation level 95\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM4 – Site inspection mitigation level 90\n- recurring_implementation_cost 10000 fixed_implementation_cost 0\n\n---\n	1	MedTech	RA/QA, Cyber	Draft	23	2026-02-15 11:42:33.881756	2026-06-29 08:22:15.764654
fbe56779-c539-4b9d-9593-1a8e27bec752	Diagnostic AI system risk story	Test  pat-169 Gen model with assets	# Risk Model: Diagnostic AI System\n\n\n## Database conventions \n\n- All tables are in the threat. Schema\n\n- Damage is in asset_threat.damage column\n\n- Probability is in threats.probability column\n- Model name is in models.name\n\n## Model name: Diagnostic AI System\n\n## Assets\n\nA1 Patient Safety fixed_value 100 recurring value 100\n\nA2 Clinical Decision Accuracy fixed_value 100 recurring value 100\n\nA3 Patient Confidentiality fixed_value 100 recurring value 100\n\nA4 Patient Consent Integrity fixed_value 100 recurring value 100\n\nA5 AI Model Integrity fixed_value 100 recurring value 100\n\nA6 Imaging Data Integrity fixed_value 100 recurring value 100\n\nA7 Platform Availability fixed_value 100 recurring value 100\n\nA8 Cloud Infrastructure Security fixed_value 100 recurring value 100\n\nA9 Regulatory Compliance fixed_value 100 recurring value 100\n\nA10 Reputation fixed_value 100 recurring value 100\n\nA11 Clinical Workflow Continuity fixed_value 0 recurring value 0\n\nA12 Auditability fixed_value 10 recurring value 10\n\n## Threat R1\n\nTag: R1\n\nName: Missed aortic aneurysm due to image quality degradation\n\nDescription: Poor image quality may result in a misdiagnosis\n\nDomain: CLINICAL\n\nProbability: 15\n\nAffects Assets: A1, A2, A10\n\nDamage: 90\n\nVulnerability: Low-quality CTA images may reduce segmentation and detection accuracy.\n\nCountermeasures:\nCM1 – Image quality validation mitigation level 85 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM2 – Radiologist review of low-confidence cases mitigation level 95 recurring_implementation_cost 120000 fixed_implementation_cost 0\n\nCM3 – Clinical performance monitoring mitigation level 75 recurring_implementation_cost 25000 fixed_implementation_cost 30000\n\n## Threat R2\n\nTag: R2\n\nName: Adversarial attack on medical imaging AI\n\nDescription: Exploit the fact that AI models are vulnerable to adversarial perturbations in input images.  \n\nDomain: CYBER_PHYSICAL\n\nProbability: 8\n\nAffects Assets: A5, A6, A2\n\nDamage: 100\n\nVulnerability: AI models vulnerable to adversarial perturbations in input images.\n\nCountermeasures:\nCM4 – Input validation and anomaly detection mitigation level 80 recurring_implementation_cost 50000 fixed_implementation_cost 75000\n\nCM5 – Regular model retraining with adversarial examples mitigation level 70 recurring_implementation_cost 100000 fixed_implementation_cost 10000\n	0	AI-enabled medical devices	Engineering	Validation	50	2026-06-25 10:26:45.29245	2026-06-29 08:31:33.659835
698fb6b6-c1e3-4340-b599-cfb058347bc3	AIOrta risk story	AIOrta threat model	# Assets\n\n* A1 Patient Safety Tier 2 \nRationale:\nFailure to detect physiological deterioration may result in patient injury, regulatory action, product recall, and loss of hospital trust.\n\n* A2 Clinical Decision Accuracy Tier 2\nRationale: Errors may impact patient safety and hospital trust\n\n* A3 Patient Confidentiality Tier 2\nRationale: Breach of confidentiality may result in HIPAA or GDPR exposure\n\n* A4 Patient Consent Integrity Tier 2\nRationale:Informed consent violations may result in hospital exposure\n\n* A5 AI Model Integrity Tier 1\nRationale: Damage to model integrity affects core functionality\n\n* A6 Imaging Data Integrity Tier 1\nRationale: Damage to data integrity affects core functionality\n\n* A7 Platform Availability Tier 3\nRationale: May impact revenue\n\n* A8 Cloud Infrastructure Tier 3\nRationale: May impact revenue\n\n* A9 Regulatory Compliance Tier 1\nRationale: Device cannot be sold in US unless cleared by FDA\n\n\n* A10 Reputation Tier 2\nRationale:  Attacks/failures in functionality may impact reputation\n\n* A11 Clinical Workflow Continuity Tier 3\nRationale: May impact revenue\n\n* A12 Auditability Tier 3\nRationale: May impact ability to sell system to hospitals\n\n# Threat R1\n\nTag: R1\n\nName: Missed aortic aneurysm due to image quality degradation\n\nDomain: CLINICAL\n\nProbability: 0.15\n\nAffects Assets: A1, A2, A10\n\nDamage: 90\n\nVulnerability:\nLow-quality CTA images may reduce segmentation and detection accuracy.\n\nCountermeasures:\n\nCM1 – Image quality validation mitigation level 85\nrecurring_implementation_cost 20000\nfixed_implementation_cost 50000\n\nCM2 – Radiologist review of low-confidence cases mitigation level 95\nrecurring_implementation_cost 120000\nfixed_implementation_cost 0\n\nCM3 – Clinical performance monitoring mitigation level 75\nrecurring_implementation_cost 25000\nfixed_implementation_cost 30000\n\n# Threat R2\n\nTag: R2\n\nName: Acute aortic dissection not detected by AI\n\nDomain: CLINICAL\n\nProbability: 0.05\n\nAffects Assets: A1, A2, A10, A11\n\nDamage: 100\n\nVulnerability:\nModel fails to identify dissection flap in atypical anatomy.\n\nCountermeasures:\n\nCM4 – High-sensitivity validation testing mitigation level 90\nrecurring_implementation_cost 15000\nfixed_implementation_cost 80000\n\nCM5 – Mandatory clinician review mitigation level 95\nrecurring_implementation_cost 100000\nfixed_implementation_cost 0\n\nCM6 – Post-market surveillance mitigation level 70\nrecurring_implementation_cost 25000\nfixed_implementation_cost 25000\n\n# Threat R3\n\nTag: R3\n\nName: Unauthorized modification of production AI model\n\nDomain: CYBER\n\nProbability: 0.08\n\nAffects Assets: A1, A5, A8, A10\n\nDamage: 95\n\nVulnerability:\nAdministrative access permits deployment of altered model versions.\n\nCountermeasures:\n\nCM7 – Multi-factor authentication mitigation level 95\nrecurring_implementation_cost 5000\nfixed_implementation_cost 10000\n\nCM8 – Signed model deployment pipeline mitigation level 95\nrecurring_implementation_cost 10000\nfixed_implementation_cost 40000\n\nCM9 – Separation of duties mitigation level 80\nrecurring_implementation_cost 25000\nfixed_implementation_cost 5000\n\n# Threat R4\n\nTag: R4\n\nName: Ransomware attack disrupts clinical processing\n\nDomain: CYBER\n\nProbability: 0.12\n\nAffects Assets: A7, A8, A10, A11\n\nDamage: 80\n\nVulnerability:\nCompromised endpoint enables ransomware propagation into cloud operations.\n\nCountermeasures:\n\nCM10 – Immutable backups mitigation level 95\nrecurring_implementation_cost 15000\nfixed_implementation_cost 20000\n\nCM11 – Endpoint detection and response mitigation level 85\nrecurring_implementation_cost 30000\nfixed_implementation_cost 10000\n\nCM12 – Disaster recovery testing mitigation level 75\nrecurring_implementation_cost 20000\nfixed_implementation_cost 5000\n\n# Threat R5\n\nTag: R5\n\nName: Exposure of patient CTA studies from cloud storage\n\nDomain: PRIVACY\n\nProbability: 0.10\n\nAffects Assets: A3, A9, A10\n\nDamage: 85\n\nVulnerability:\nCloud storage bucket may be misconfigured and publicly accessible.\n\nCountermeasures:\n\nCM13 – Encryption at rest mitigation level 90\nrecurring_implementation_cost 5000\nfixed_implementation_cost 10000\n\nCM14 – Continuous cloud posture monitoring mitigation level 85\nrecurring_implementation_cost 25000\nfixed_implementation_cost 15000\n\nCM15 – Quarterly access reviews mitigation level 75\nrecurring_implementation_cost 12000\nfixed_implementation_cost 0\n\n# Threat R6\n\nTag: R6\n\nName: Patient data used beyond original consent\n\nDomain: PRIVACY\n\nProbability: 0.07\n\nAffects Assets: A3, A4, A9, A10\n\nDamage: 70\n\nVulnerability:\nResearch or model-training activities may exceed authorized consent scope.\n\nCountermeasures:\n\nCM16 – Consent management platform mitigation level 90\nrecurring_implementation_cost 10000\nfixed_implementation_cost 30000\n\nCM17 – Data governance review board mitigation level 80\nrecurring_implementation_cost 40000\nfixed_implementation_cost 10000\n\nCM18 – Dataset release approval workflow mitigation level 85\nrecurring_implementation_cost 15000\nfixed_implementation_cost 5000\n\n# Threat R7\n\nTag: R7\n\nName: Wrong patient associated with AI analysis\n\nDomain: CLINICAL_PRIVACY\n\nProbability: 0.03\n\nAffects Assets: A1, A2, A3, A12\n\nDamage: 95\n\nVulnerability:\nDICOM metadata mismatch during ingestion or processing.\n\nCountermeasures:\n\nCM19 – DICOM identity validation mitigation level 90\nrecurring_implementation_cost 10000\nfixed_implementation_cost 20000\n\nCM20 – Workflow verification checkpoint mitigation level 85\nrecurring_implementation_cost 25000\nfixed_implementation_cost 10000\n\nCM21 – Audit trail monitoring mitigation level 75\nrecurring_implementation_cost 10000\nfixed_implementation_cost 10000\n	1	AI-enabled medical devices	Engineering	Draft	50	2026-06-21 13:53:18.558292	2026-06-25 16:21:03.235465
8d17a4c4-2c8c-40b8-8212-5b7d2abf2aab	Electrophysiology lab	Electrophysiology lab	# Risks\n\n## Controlled Domains are:\n- PHYSICAL_SECURITY\n- SUPPLY_CHAIN\n- INSIDER_THREAT\n- CYBER_PHYSICAL\n- OPERATIONAL_PROCESS\n- PATIENT_SAFETY\n- MEDICAL_STAFF_SAFETY\n\n## Database conventions **\n- All tables are in the threat. Schema\n- Damage is in asset_threat.damage column \n- Probability is in threats.probability column\n- Model name is in models.name\n---\n\n## Model name: Electrophysiology lab\n\n## Threat R1\n- Tag: R1\n- Name: Preset configuration may be changed\n- Domain:CYBER_PHYSICAL\n- Probability 0.4\n- Affects Assets: A2, A6\n- Damage:30\n\n**Vulnerability:** No password required to change the preset by the operator\n\n**Countermeasures:**\n- CM1 – Hospital employee training mitigation level 80\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R2 \n- Tag: R2\n- Name: Supply chain attack\n- Domain:SUPPLY_CHAIN\n- Probability: 0.2\n- Affects Assets: A3, A6, A2\n- Damage:100\n\n**Vulnerability:** PLC, sensors integrity may be compromised between manufacturing and hospital\n\n**Countermeasures:**\n- CM2 – Multiple ATP tests mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM3 – Test on jig before sending to customer mitigation level 95\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM4 – Site inspection mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R3 \n- Tag: R3\n- Name: System power is disconnected by mistake\n- Domain: PHYSICAL_SECURITY\n- Probability: 0.3\n- Affects Assets: A6, A2\n- Damage:30\n\n**Vulnerability:**The power cable may be disconnected by mistake\n\n**Countermeasures:**\n- CM5 – System power light will turn off to indicate issue mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM6 – Physical locking mechanism on system side of the cable, segment locking mechanism mitigation level 95\n- recurring_implementation_cost 100 fixed_implementation_cost 0\n\n---\n\n## Threat R4\n- Tag: R4\n- Name: Field Service Rep makes an unauthorized change to system\n- Domain: INSIDER_THREAT\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Field service may share maintenance password with an attacker or didn't log out of technician mode\n\n**Countermeasures:**\n- CM7 – Vetting process mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM8 – Training mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM9 – Service reports mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM10 – ATP mitigation level 90\n- recurring_implementation_cost 1000 fixed_implementation_cost 0\n- CM11 – Clinical team  periodically verifies that system is online and not in technician mode mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n\n---\n\n## Threat R5 \n- Tag: R5\n– Name: System is sabotaged \n- Domain: PHYSICAL_SECURITY\n- Probability: 0.1\n- Affects Assets: A6, A2, A4\n- Damage: 100\n\n**Vulnerability:** People have physical access to electrophysiology lab \n\n**Countermeasures:**\n- CM12 – Support station is sealed mitigation level 90\n- recurring_implementation_cost 0  fixed_implementation_cost 0\n- CM13 – Controlled access to electrophysiology lab mitigation level 90\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R6 \n- Tag: R6\n- Name: An unauthorized change is made to sensor parameters\n- Domain:CYBER_PHYSICAL\n\n- Probability: 0.2\n- Affects Assets:A6, A2\n- Damage: 60\n\n**Vulnerability:** After physical access is obtained to the USB maintenance port, additional user authentication is not performed\n\n**Countermeasures:**\n- CM13 – Controlled access to electrophysiology lab 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM16 – Dedicated interface software mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM17 – An attacker would need to reverse-engineer the proprietary protocol used by the sensors mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R7\n- Tag: R7\n- Name: Software Hack or local attack on support station\n- Domain:CYBER_PHYSICAL\n- Probability: 0.2\n- Affects Assets: A6, A2, A4\n- Damage: 80\n\n**Vulnerability:** Attacker may gain access to maintenance password\n\n**Countermeasures:**\n- CM18 – Strong password policy mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 1000\n- CM15 – Special tools are needed in order to gain access to support station USB port mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n- CM20 – Equipment locked away mitigation level 90\n- recurring_implementation_cost 0 fixed_implementation_cost 0\n\n---\n\n## Threat R8\n- Tag: R8\n- Name: CODESys runtime issues impact correct system operation\n- Domain:SUPPLY_CHAIN\n- Probability: 0.1\n- Affects Assets: A7\n- Damage: 80\n\n**Vulnerability:** CODESYS runtime in deployed system may have unpatched issues\n\n**Countermeasures:**\n- CM21 - CODESys implements an ongoing software security program mitigation level 90\n- CM22 - Radiaction implements an ongoing patch policy for CODESys mitigation level 90\n- CM2 – Multiple ATP tests mitigation level 90\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM3 – Test on jig before shipment mitigation level 95\n- recurring_implementation_cost 5000 fixed_implementation_cost 0\n- CM4 – Site inspection mitigation level 90\n- recurring_implementation_cost 10000 fixed_implementation_cost 0\n\n---\n	1	MedTech	RA/QA, Cyber	Draft	23	2026-02-26 11:03:26.753552	2026-02-26 11:06:16.6454
5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	Neteera risk story	Neteera risk story	# Company Neteera\n\nFounded: 2015\n\nStage: Growth\n\nFunding: 36M\n\nRevenue: 16M\n\nEnterprise valuation: $180M\n\nFixed asset pool: $120M\n\nRecurring asset pool: $60M\n\n# Product\n\nK231733: Neteera 130H-Plus Vital Sign Monitoring Sensor\n\nPanel: Cardiovascular\n\nClassification Product code: DRT \n\n# Assets\n\nA1 Patient Safety Tier 2\nfixed_value 16000000\nrecurring_value 0\n\nA2 Clinical Decision Accuracy Tier 2\nfixed_value 13333333\nrecurring_value 0\n\nA3 Patient Confidentiality Tier 2\nfixed_value 3333333\nrecurring_value 6666667\n\nA4 Patient Consent Integrity Tier 2\nfixed_value 13333333\nrecurring_value 0\n\nA5 AI Model Integrity Tier 1\nfixed_value 30000000\nrecurring_value 0\n\nA6 Physiological Signal Integrity Tier 1\nfixed_value 30000000\nrecurring_value 0\n\nA7 Platform Availability Tier 3\nfixed_value 0\nrecurring_value 6666667\n\nA8 Cloud Infrastructure Tier 3\nfixed_value 0\nrecurring_value 6666667\n\nA9 Regulatory Compliance Tier 1\nfixed_value 30000000\nrecurring_value 0\n\nA10 Reputation Tier 2\nfixed_value 6666667\nrecurring_value 6666666\n\nA11 Clinical Workflow Continuity Tier 3\nfixed_value 0\nrecurring_value 6666667\n\nA12 Auditability Tier 3\nfixed_value 3333334\nrecurring_value 0\n\nA13 Upstream Device Management Pipeline, BioT (Cloud) – The infrastructure used to push firmware, security patches, and algorithm updates to Neteera edge devices. Tier 3\nfixed_value 0\nrecurring_value 6666667\n\nA14 Device Authorization Registry, BioT (Cloud) – The database hosting unique cryptographic keys and tokens that authenticate physical Neteera devices to the cloud. Tier 3\nfixed_value 3333333\nrecurring_value 0\n\nA15 Live Telemetry Ingestion Endpoint, BioT (Cloud) – The cloud gateway (MQTT broker) receiving real-time patient vital signs and bed-exit metrics. Tier 3\nfixed_value 0\nrecurring_value 6666666\n\nThreat R1\n\nTag: R1\n\nName: Early physiological deterioration not detected\n\nDescription: Early physiological deterioration not detected\n\nDomain: CLINICAL\n\nProbability: 14\n\nAffects Assets: A1, A2, A6, A10\n\nDamage: 15\n\nVulnerability\n\nReduced signal quality caused by patient movement, body position, blankets, distance from the sensor, or environmental interference degrades continuous physiological measurements and delays recognition of deterioration.\n\nCountermeasures\n\nCM1 - Continuous signal quality assessment mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM2 - Measurement confidence scoring mitigation_level 90 recurring_implementation_cost 0 fixed_implementation_cost 50000\n\nCM3 - Clinical performance monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R2\n\nTag: R2\n\nName: False deterioration indication\n\nDescription: False deterioration indication\n\nDomain: CLINICAL\n\nProbability: 16\n\nAffects Assets: A1, A2, A10, A11\n\nDamage: 35\n\nVulnerability\n\nMotion artifacts or environmental interference produce measurements suggesting deterioration where none exists, increasing unnecessary clinical intervention and alarm fatigue.\n\nCountermeasures\n\nCM4 - Multi-parameter validation mitigation_level 90 recurring_implementation_cost 0 fixed_implementation_cost 50000\n\nCM5 - Artifact rejection algorithms mitigation_level 90 recurring_implementation_cost 0 fixed_implementation_cost 50000\n\n\nThreat R3\n\nTag: R3\n\nName: Contactless physiological measurements become inaccurate\n\nDescription: Contactless physiological measurements become inaccurate\n\nDomain: CLINICAL\n\nProbability: 10\n\nAffects Assets: A1, A2, A6\n\nDamage: 35\n\nVulnerability\n\nPerformance may drift outside of validated operating ranges and reduce measurement accuracy.\n\nCountermeasures\n\nCM7 - Test both the physical micro-radar sensors and the algorithm's interpretation (software) for drift. Implement automated power-on self-tests (POST) and periodic background calibration checks.Use internal reference loops where the transmitter sends a known signal directly back to the receiver to test for hardware-only drift. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM2 - Measurement confidence scoring. Tie the confidence score directly to Signal-to-Noise Ratio (SNR) and phase stability.Ensure the software withholds the measurement entirely (or marks it visually) if the score drops below a validated clinical threshold, rather than displaying a guessed value. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM8: Environmental Noise Filtering: Implement algorithms specifically designed to detect and filter out periodic motion from non-human sources (like a spinning room fan or vibrating HVAC vent) that can mimic or distort heart and respiratory rates. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM9: Out-of-Range Alerts: Create a system alert that triggers if the sensor outputs data that is physiologically impossible for a human (e.g., a respiratory rate of 150 breaths per minute), signaling immediate sensor malfunction. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R4\n\nTag: R4\n\nName: Bed-exit event not detected\n\nDescription: Bed-exit event not detected\n\nDomain: CLINICAL\n\nProbability: 8\n\nAffects Assets: A1, A10, A11\n\nDamage: 5\n\nVulnerability\n\nMovement classification fails to recognize bed exit because of occlusion, unusual movement patterns, or degraded sensor observations.\n\nCountermeasures\n\nCM10: Movement Classifier Validation - do not overfit to standard movement profiles.How to strengthen it :Validate specifically against "edge-case" cohorts (e.g., extremely frail patients who move slowly, or patients with chorea/parkinsonian tremors).Test with common physical occlusions included in the training data, such as heavy weighted blankets or over-bed tables. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM11: Multi-Feature Movement Analysis - Incorporate spatial tracking thresholds (e.g., tracking the center of mass shifting toward the perimeter of the sensor's fields of view).Use temporal sequencing (e.g., a sudden increase in respiratory rate often precedes the physical act of sitting up). mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM12: Clinical Notification Testing:Implement end-to-end latency testing to ensure the alert arrives within seconds of the event.Establish a heartbeat check between the sensor and the facility's Nurse Call system to log communication failures immediately. mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM13: Pre-Exit Intent Detection (Early Warning): Train the classifier to detect the sequence leading to a bed exit (e.g., rolling over, then sitting up) to issue a "pre-exit" warning before the patient's feet actually hit the floor. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM14: Fall-Back "Empty Bed" State Validation: If movement tracking becomes fully occluded or lost, the system should default to cross-referencing physiological data. If no heart rate or respiration is detected anywhere in the zone, it should trigger an immediate "Presence Lost" alert rather than failing silently. \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\n\nThreat R5\n\nTag: R5\n\nName: False bed-exit notification\n\nDescription: False bed-exit notification\n\nDomain: CLINICAL\n\nProbability: 2\n\nAffects Assets: A10, A11\n\nDamage: 70\n\nVulnerability\n\nNormal patient movement is incorrectly classified as bed exit, creating unnecessary caregiver workload.\n\nCountermeasures\n\nCM2 - Measurement confidence scoring. Tie the confidence score directly to Signal-to-Noise Ratio (SNR) and phase stability.Ensure the software withholds the measurement entirely (or marks it visually) if the score drops below a validated clinical threshold, rather than displaying a guessed value. \nmitigation_level 90 recurring_implementation_cost 0 fixed_implementation_cost 50000\n\nThreat R6\n\nTag: R6\n\nName: Sleep and movement classification inaccurate\n\nDescription: Sleep and movement classification inaccurate\n\nDomain: CLINICAL\n\nProbability: 10\n\nAffects Assets: A2, A10\n\nDamage: 65\n\nVulnerability: Movement classification algorithms misclassify sleep state or patient positioning.\n\nCountermeasures\n\nCM4 - Multi-parameter validation \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM5 - Artifact rejection algorithms \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R7\n\nTag: R7\n\nName: Patient associated with incorrect monitoring session\n\nDescription: Patient associated with incorrect monitoring session\n\nDomain: OPERATIONAL\n\nProbability: 5\n\nAffects Assets: A1, A2, A3, A11\n\nDamage: 95\n\nVulnerability\n\nIncorrect patient association attributes physiological measurements to the wrong patient.\n\nCountermeasures\n\nCM15 - Positive patient identification \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM16 - EMR reconciliation \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM17 - Clinical verification workflow \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R8\n\nTag: R8\n\nName: Physiological monitoring unavailable\n\nDescription: Physiological monitoring unavailable\n\nDomain: OPERATIONAL\n\nProbability: 7\n\nAffects Assets: A7, A8, A11\n\nDamage: 85\n\nVulnerability: Infrastructure failure, software failure, or network disruption interrupts continuous monitoring.\n\nCountermeasures\n\nCM21 - High-availability architecture \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM22 - Disaster recovery testing \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\n\nThreat R9\n\nTag: R9\n\nName: Unauthorized modification of physiological processing software\n\nDescription: Unauthorized modification of physiological processing software\n\nDomain: CYBER\n\nProbability: 4\n\nAffects Assets: A1, A2, A5, A9\n\nDamage: 100\n\nVulnerability: Compromised software deployment alters physiological calculations or movement classification.\n\nCountermeasures\n\nCM23 - Secure software signing \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM24 - Runtime integrity verification \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM25 - Secure software lifecycle \nmitigation_level 90 recurring_implementation_cost 200000 fixed_implementation_cost 40000\n\nThreat R10\n\nTag: R10\n\nName: Physiological measurements exposed to unauthorized parties\n\nDescription: Physiological measurements exposed to unauthorized parties\n\nDomain: PRIVACY\n\nProbability: 10\n\nAffects Assets: A3, A9, A10\n\nDamage: 90\n\nVulnerability: Weak authentication, authorization, or encryption exposes patient monitoring information.\n\nCountermeasures\n\nCM26 - Multi-factor authentication \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM27 - Role-based access control \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM28 - Encryption at rest and in transit \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R11\n\nTag: R11\n\nName: Sensor measurements intentionally manipulated\n\nDescription: Sensor measurements intentionally manipulated\n\nDomain: CYBER\n\nProbability: 3\n\nAffects Assets: A1, A2, A5, A6\n\nDamage: 95\n\nVulnerability: Malicious manipulation or spoofing of physiological signals results in incorrect measurements presented to clinicians.\n\nCountermeasures\n\nCM30 - Signal anomaly detection \nmitigation_level 80 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM31 - Sensor integrity verification \nmitigation_level 80 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM32 - Physiological consistency validation \nmitigation_level 80 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R12\n\nTag: R12\n\nName: Clinical workflow disrupted by system integration failure\n\nDescription: Clinical workflow disrupted by system integration failure\n\nDomain: OPERATIONAL\n\nProbability: 8\n\nAffects Assets: A7, A10, A11\n\nDamage: 75\n\nVulnerability: Failure to exchange monitoring information reliably with hospital systems delays clinical workflows.\n\nCountermeasures\n\nCM41- Interface conformance testing \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\n\nCM42 - Automated interface monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\n\nThreat R14\n\nTag: R14\n\nName: Security vulnerabilities remain unremediated after deployment\n\nDescription: Security vulnerabilities remain unremediated after deployment\n\nDomain: REGULATORY\n\nProbability: 6\n\nAffects Assets: A9, A10, A12\n\nDamage: 90\n\nVulnerability: Failure to identify, assess, prioritize, and remediate cybersecurity vulnerabilities throughout the product lifecycle.\n\nCountermeasures\n\nCM51 - Vulnerability disclosure mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM52 - Secure patch management mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM53 - Vulnerability monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R15\n\nTag: R15\n\nName: Audit evidence insufficient for regulatory investigation\n\nDomain: REGULATORY\n\nProbability: 0.05\n\nAffects Assets: A9, A12, A10\n\nDamage: 85\n\nVulnerability: Audit logs do not provide sufficient evidence to reconstruct system behavior, software versions, user activity, or clinical events.\n\nCountermeasures\n\nCM61 - Tamper-resistant audit logging \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM62 - Periodic audit review \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM63 - Regulatory readiness exercises \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R16\n\nTag: R16\n\nName: Malicious firmware installed on patient monitoring sensor\n\nDescription: Malicious firmware installed on patient monitoring sensor\n\nDomain: CYBER\n\nProbability: 4\n\nAffects Assets: A1, A2, A5, A6, A9\n\nDamage: 100\n\nVulnerability: The device accepts unauthorized firmware because of weak code-signing verification, insecure boot, or firmware rollback vulnerabilities, allowing physiological measurements or movement classifications to be manipulated.\n\nCountermeasures\n\nCM71 - Secure Boot mitigation_level 90 \nrecurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM72 - Hardware Root of Trust \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM73 - Cryptographically signed \nfirmware mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM74 - Anti-rollback protection \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R17\n\nTag: R17\n\nName: Device identity spoofed\n\nDomain: CYBER\n\nProbability: 0.05\n\nAffects Assets: A1, A2, A3, A6\n\nDamage: 90\n\nVulnerability: Weak device authentication allows an attacker to impersonate a legitimate monitoring device and inject fabricated physiological measurements into the monitoring platform.\n\nCountermeasures\n\nCM81 - Mutual TLS \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM82 - Device certificates \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM83 - Certificate lifecycle management \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM84 - Hardware-backed device identity \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R18\n\nTag: R18\n\nName: Replay of physiological measurements\n\nDescription: Replay of physiological measurements\n\nDomain: CYBER\n\nProbability: 4\n\nAffects Assets: A1, A2, A6\n\nDamage: 95\n\nVulnerability: Captured physiological data are replayed because communication protocols lack freshness validation or replay protection.\n\nCountermeasures\n\nCM91 - Nonces \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM92 - Sequence numbers \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM93 - Message timestamps \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM94 - Replay detection \nmitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R19\n\nTag: R19\n\nName: Unauthorized access to patient monitoring APIs\n\nDescription: Unauthorized access to patient monitoring APIs\n\nDomain: CYBER\n\nProbability: 8\n\nAffects Assets: A3, A7, A9\n\nDamage: 90\n\nVulnerability: Weak API authentication or authorization permits unauthorized access to patient monitoring data or monitoring functions.\n\nCountermeasures\n\nCM101 - OAuth2/OIDC mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM102 - API authorization mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM103 - Rate limiting mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM104 - API gateway monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R20\n\nTag: R20\n\nName: Clinician portal privilege escalation\n\nDescription: Clinician portal privilege escalation\n\nDomain: CYBER\n\nProbability: 5\n\nAffects Assets: A3, A9, A10\n\nDamage: 90\n\nVulnerability: Authorization weaknesses allow users to obtain privileges beyond their intended clinical role.\n\nCountermeasures\n\nCM111 - RBAC mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM112 - Least privilege mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM113 - Privilege auditing mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM114 - Segregation of duties mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R21\n\nTag: R21\n\nName: Session hijacking of clinical users\n\nDomain: CYBER\n\nProbability: 0.06\n\nAffects Assets: A3, A9\n\nDamage: 85\n\nVulnerability: Weak session management permits attackers to reuse authenticated clinician sessions.\n\nCountermeasures\n\nCM121 - Secure session tokens mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM122 - MFA mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM123 - Session expiration mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM124 - Device binding mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R22\n\nTag: R22\n\nName: Supply chain compromise introduces vulnerable software\n\nDescription: Supply chain compromise introduces vulnerable software\n\nDomain: SUPPLYCHAIN\n\nProbability: 5\n\nAffects Assets: A5, A9, A12\n\nDamage: 95\n\nVulnerability: Compromised third-party software components or build dependencies introduce exploitable vulnerabilities into production systems.\n\nCountermeasures\n\nCM131 - SBOM management mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM132 - Dependency scanning mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM133 - Build provenance mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM134 - Trusted artifact repositories mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R23\n\nTag: R23\n\nName: CI/CD pipeline compromise deploys malicious software\n\nDescription: CI/CD pipeline compromise deploys malicious software\n\nDomain: CYBER\n\nProbability: 3\n\nAffects Assets: A5, A9, A12\n\nDamage: 100\n\nVulnerability: Compromise of development infrastructure enables unauthorized software deployment into production environments.\n\nCountermeasures\n\nCM141 - Build signing mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM142 - Protected branches mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM143 - MFA for developers mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM144 - Build attestation mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R24\n\nTag: R24\n\nName: Cloud denial-of-service interrupts continuous monitoring\n\nDomain: CYBER\n\nProbability: 3\n\nAffects Assets: A7, A8, A11\n\nDamage: 35\n\nVulnerability: Network or application-layer denial-of-service attacks exhaust cloud resources and interrupt monitoring services.\n\nCountermeasures\n\nCM151 - DDoS protection mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM152 - Auto-scaling mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM153 - Rate limiting mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM154 - Traffic filtering mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R24A\n\nTag: R24A\n\nName: Cloud service dependency failure interrupts monitoring\n\nDescription: Cloud service dependency failure interrupts monitoring\n\nDomain: OPERATIONAL\n\nProbability: 3\n\nAffects Assets: A7, A8, A11\n\nDamage: 35\n\nVulnerability: Failure of cloud identity, messaging, storage, notification, or monitoring services interrupts delivery of patient monitoring information.\n\nCountermeasures\n\nCM161 - Multi-zone deployment mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM162 - Dependency health monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM163 - Graceful degradation mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM164 - Offline operation mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R25\n\nTag: R25\n\nName: Message queue saturation delays clinical events\n\nDescription: Message queue saturation delays clinical events\n\nDomain: OPERATIONAL\n\nProbability: 3\n\nAffects Assets: A7, A11\n\nDamage: 10\n\nVulnerability: Backlog within event-processing infrastructure delays delivery of physiological measurements and clinical notifications.\n\nCountermeasures\n\nCM171 - Queue monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM172 - Autoscaling mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM173 - Backpressure controls mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM174 - Capacity testing mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R26\n\nTag: R26\n\nName: Storage exhaustion prevents physiological data recording\n\nDescription: Storage exhaustion prevents physiological data recording\n\nDomain: OPERATIONAL\n\nProbability: 3\n\nAffects Assets: A7, A12\n\nDamage: 75\n\nVulnerability: Insufficient storage capacity or storage failures prevent recording of physiological measurements and audit evidence.\n\nCountermeasures\n\nCM181 - Capacity monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM182 - Storage quotas mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM183 - Automatic archival mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM184 - Storage redundancy mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat R27\n\nTag: R27\n\nName: Sensor configuration modified without authorization\n\nDescription: Sensor configuration modified without authorization\n\nDomain: CYBER\n\nProbability: 3\n\nAffects Assets: A1, A2, A5, A6\n\nDamage: 35\n\nVulnerability: Unauthorized modification of sensor calibration, operating parameters, or detection thresholds alters physiological measurements and behavioral monitoring.\n\nCountermeasures\n\nCM191 - Configuration integrity monitoring mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM192 - Digitally signed configuration mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM193 - Role-based configuration management mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM194 - Configuration audit logging mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nThreat: R28\n\nTag: R28\n\nName:BioT system -Infrastructure Supply Chain Failure / Compromise.\n\nDescription: A malicious compromise or sudden operational outage of the upstream IoT platform provider (BioT Medical / AWS) corrupts the device management pipeline or completely halts clinical data delivery.\n\nDomain: SUPPLYCHAIN \n\nProbability: 3\n\nDamage: 35\n\nAffects Assets: A13, A14, A15\n\nVulnerabilities\n\nVULN-S1: Single Point of Failure (SPOF) Dependency – The system architecture relies entirely on a single platform vendor (BioT) without a dynamic failover cloud or local on-premise fallback mesh.\n\nVULN-S2: Implicit Trust in Upstream Code Signing – The edge device accepts and executes firmware updates or configuration files pushed from the cloud registry without an independent, secondary validation layer.\n\nVULN-S3: Shared Infrastructure Risk (Multi-tenancy) – Weak logical isolation at the PaaS layer could allow a compromise of another BioT customer to cascade into Neteera's data silos.\n\nCountermeasures\n\nCM281: Edge Autonomous Fallback Mode (Local Survivability). mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nDescription: If the connection to the BioT cloud ingest endpoint drops, the physical Neteera hardware switches to a "Local Alert" state. The device continues to run its micro-radar classification algorithms locally at the edge. It routes critical bed-exit and respiratory distress notifications over the local facility Wi-Fi directly to an on-premise pager or nurse call system, bypasssing the cloud entirely during an outage.\n\nCM282: Multi-Party / Independent Code Signing Validation mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nDescription: Prevents a compromised upstream provider from pushing malicious firmware updates to the physical sensors. The Neteera edge device requires a dual-signature for any firmware update. Even if the BioT pipeline initiates the update, the device will reject the package unless it is also cryptographically signed by an independent Neteera corporate private key kept in an offline Hardware Security Module (HSM).\n\nCM283: Continuous Security Posture Drift Monitoring. mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nDescription: Mitigates shared infrastructure risk by monitoring the boundary between Neteera and the platform provider. Automate real-time IAM (Identity and Access Management) auditing. If the upstream provider modifies access permissions, introduces an unvetted third-party API, or alters data-at-rest encryption settings on the AWS bucket, an automated alert triggers to isolate the Neteera environment.\n\nThreat: R29\n\nTag: R29\n\nName: Upstream Supply Chain Phishing\n\nDescription: As seen in recent trends hitting other medical device software and robotics companies, the highest-probability entry point is rarely a zero-day exploit in the platform's code. Instead, it is an attacker phishing a BioT engineer or cloud administrator to steal credentials, gaining access to the AWS console to manipulate database configurations or software update hooks.\n\nDomain: SUPPLYCHAIN\n\nProbability: 3\n\nAffects Assets: A7, A9, A10, A11, A12 \n\nDamage: 35\n\nVulnerability: Compromised credentials from a BioT engineer or cloud administrator allow attackers to manipulate database configurations or software update hooks in the AWS console.\n\nCountermeasures\n\nCM294: Multi-Factor Authentication (MFA) Enforcement mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM295: Just-In-Time (JIT) Access mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM296: Principle of Least Privilege (PoLP) mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\nCM297: Credential Rotation and Audit Logging mitigation_level 90 recurring_implementation_cost 20000 fixed_implementation_cost 50000\n\n	0	MedTech	Analysts	Draft	23	2026-06-25 16:25:33.315335	2026-07-24 15:26:12.335603
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.categories (id, description, created_at, updated_at, deleted_at) FROM stdin;
1	TechBio	2025-12-05 09:37:27.849885	2025-12-05 09:37:27.849885	\N
2	Biotech	2025-12-05 09:37:27.851977	2025-12-05 09:37:27.851977	\N
3	AI	2025-12-05 09:37:27.852617	2025-12-05 09:37:27.852617	\N
\.


--
-- Data for Name: guests; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.guests (id, name, description, linkedin_url, job_description, content_source, org_id, post_id, created_at, updated_at, deleted_at, content_url) FROM stdin;
1	Yann Gaston-Mathé	\N	\N	Co-Founder and CEO at Iktos	\N	\N	\N	2025-12-05 09:37:27.885984	2025-12-05 09:37:27.885984	\N	\N
2	James Hamrick	\N	\N	Chairman of the Caris Precision Oncology Alliance at Caris Life Sciences	\N	\N	\N	2025-12-05 09:37:27.886765	2025-12-05 09:37:27.886765	\N	\N
3	Aaron Brouser	\N	\N	General Manager Life Sciences at Carta Healthcare	\N	\N	\N	2025-12-05 09:37:27.887095	2025-12-05 09:37:27.887095	\N	\N
4	Tim O'Connell	\N	\N	Founder and CEO at emtelligent	\N	\N	\N	2025-12-05 09:37:27.887392	2025-12-05 09:37:27.887392	\N	\N
8	Alice Smith	Founder and CEO of HelixBio	\N	CEO	substack	14	\N	2025-12-05 13:52:56.673713	2025-12-05 13:52:56.673713	\N	https://example.com/post
9	Enrique Diloné	Chief technology officer	\N	CTO	substack	15	\N	2025-12-08 16:12:48.705166	2025-12-08 16:34:04.819286	\N	https://example.com/post
11	Tigran Arzumanov	Founder and CEO of BDaaS.	\N	Founder and CEO	substack	17	\N	2025-12-08 16:35:35.373609	2025-12-08 16:38:15.625567	\N	https://newsletter.dannylieberman.com/p/a-better-version-of-you
15	Aaron Brauser	GM Life Sciences at Carta Healthcare.	\N	Aaron and I talked about how they create a competitive moat using switching costs.	substack	3	\N	2025-12-08 16:45:00.066986	2025-12-08 16:46:58.565344	\N	https://newsletter.dannylieberman.com/p/switching-costs
13	Bar Rafaeli	Israeli supermodel and co-founder of Carolina Lemke Berlin.	\N	Co-founder	substack	\N	\N	2025-12-08 16:39:48.538832	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
14	Martin Rapaport	Founder of the Rapaport Diamond Report.	\N	Founder	substack	\N	\N	2025-12-08 16:39:48.538832	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
19	Pamela Tenaerts	Chief Medical Officer at Medable, former practicing physician who transitioned to clinical trials and became a leader in public policy.	\N	Chief Medical Officer	substack	31	\N	2025-12-09 16:50:22.136134	2025-12-09 16:50:22.136134	\N	https://newsletter.dannylieberman.com/p/dissent-is-an-act-of-faith
20	Viraj Narayanan	CEO of Cornerstone AI.	\N	CEO	substack	32	\N	2025-12-09 17:20:04.395605	2025-12-09 17:20:04.395605	\N	https://newsletter.dannylieberman.com/p/real-world-people
22	Ronel Wexler	Co-founder and CEO of Promise Bio.	\N	Co-founder and CEO	substack	33	\N	2025-12-09 18:14:16.595295	2025-12-09 18:14:16.595295	\N	https://newsletter.dannylieberman.com/p/israel-is-the-best-place-in-the-world
24	Security Analyst		\N	Security Analyst	substack	34	\N	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	https://pattern-cards.netlify.app/
26	David Bates	CEO of Linus Health.	\N	CEO/founder	substack	37	\N	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N	https://newsletter.dannylieberman.com/p/what-happened-yesterday-is-easy
21	Danny Lieberman	I help TechBio and digital health CEOs grow revenue—by solving the tech, team, and go-to-market problems that stall progress. | Host, Life Sciences Today.	\N	Author	substack	19	\N	2025-12-09 17:20:04.395605	2026-06-29 09:54:19.95046	\N	https://newsletter.dannylieberman.com/p/what-threats-really-count
28	Philip Poulidis	CEO of Odaia AI in Toronto.	\N	CEO	substack	39	\N	2026-01-07 12:33:34.105393	2026-01-07 12:33:34.105393	\N	https://newsletter.dannylieberman.com/p/paying-customers-is-proof
30	Walt Pebley	Chief Scientific Officer of Oregon Freeze Dry Life Sciences.	\N	Veteran freeze-drying innovator with 43 years of experience.	substack	40	\N	2026-01-07 12:46:31.747775	2026-01-07 12:51:12.590419	\N	https://newsletter.dannylieberman.com/p/customers-dont-want-to-hear-your
5	Wessam Sonbol	Wessam is a great example of a founder-market misfit.	\N	Founder of Delve Health	substack	5	\N	2025-12-05 09:37:27.887696	2026-01-07 14:24:14.003969	\N	https://newsletter.dannylieberman.com/p/foundermarket-misfit
\.


--
-- Data for Name: orgs; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.orgs (id, name, description, stage, funding, date_funded, date_founded, linkedin_company_url, content_source, category_id, created_at, updated_at, deleted_at, content_url) FROM stdin;
1	Iktos	AI for new drug discovery and design	Series A	21000000.00	2025-02-20 00:00:00	2016-01-01 00:00:00	\N	\N	\N	2025-12-05 09:37:27.898626	2025-12-05 09:37:27.898626	\N	\N
2	Caris Life Sciences	AI TechBio company specializing in molecular profiling for oncology	Public (previously Series D)	1230000000.00	2025-06-18 00:00:00	2008-01-01 00:00:00	\N	\N	\N	2025-12-05 09:37:27.898626	2025-12-05 09:37:27.898626	\N	\N
4	Emtelligent	NLP engine and apps primarily for healthcare	Unfunded (Revenue Generating)	0.00	\N	2016-01-01 00:00:00	\N	\N	\N	2025-12-05 09:37:27.898626	2025-12-05 09:37:27.898626	\N	\N
14	HelixBio	AI-first biotech CRO	\N	\N	\N	\N	\N	substack	\N	2025-12-05 13:52:56.673713	2025-12-05 13:52:56.673713	\N	https://example.com/post
15	ImmunityBio	AI-first biotech CRO	\N	\N	\N	\N	\N	substack	\N	2025-12-08 16:12:48.705166	2025-12-08 16:34:04.819286	\N	https://example.com/post
17	BDaaS	A business development service for US life science companies trying to expand into Europe.	\N	\N	\N	\N	\N	substack	\N	2025-12-08 16:35:35.373609	2025-12-08 16:38:15.625567	\N	https://newsletter.dannylieberman.com/p/a-better-version-of-you
20	SAP	SAP exemplifies extreme switching costs through deep enterprise integration. Their ERP software becomes the central nervous system of organizations, handling everything from finance to supply chain management.	\N	\N	\N	\N	\N	substack	\N	2025-12-08 16:45:00.066986	2025-12-08 16:46:58.565344	\N	https://newsletter.dannylieberman.com/p/switching-costs
34	Pattern Factory		\N	\N	\N	\N	\N	substack	\N	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	https://pattern-cards.netlify.app/
3	Carta Healthcare	Carta Healthcare is tackling healthcare’s massive inefficiency problem with LLM technology that extracts clinical insights from unstructured medical notes.	Series B	80500000.00	2025-05-08 00:00:00	2017-01-01 00:00:00	\N	substack	\N	2025-12-05 09:37:27.898626	2025-12-08 16:46:58.565344	\N	https://newsletter.dannylieberman.com/p/switching-costs
26	Merck		\N	\N	\N	\N	\N	substack	\N	2025-12-08 17:37:39.582085	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
27	IQVIA		\N	\N	\N	\N	\N	substack	\N	2025-12-08 17:37:39.582085	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
28	Medtronic		\N	\N	\N	\N	\N	substack	\N	2025-12-08 17:37:39.582085	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
21	Flatiron Health		\N	\N	\N	\N	\N	substack	\N	2025-12-08 16:45:00.066986	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
30	Debiopharm		\N	\N	\N	\N	\N	substack	\N	2025-12-08 17:37:39.582085	2025-12-08 17:37:39.582085	\N	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling
31	Medable	Decentralized clinical trials (DCT) pioneer founded in 2015.	\N	\N	\N	\N	\N	substack	\N	2025-12-09 16:50:22.136134	2025-12-09 16:50:22.136134	\N	https://newsletter.dannylieberman.com/p/dissent-is-an-act-of-faith
32	Cornerstone AI	Cornerstone AI uses AI to clean and standardize healthcare data.	\N	\N	\N	\N	\N	substack	\N	2025-12-09 17:20:04.395605	2025-12-09 17:20:04.395605	\N	https://newsletter.dannylieberman.com/p/real-world-people
33	Promise Bio	Promise Bio is an early-stage tech-bio company coming out of AION Labs in Israel with strategic investors – AstraZeneca and Pfizer. They’ve built a cloud-based AI platform that uses advanced mass spectrometry-based proteomics and provides value for pharmaceutical companies in 4 ways: identifies new drug targets, predicts treatment response, analyzes the mechanism of action, and supports pathway engagement analysis.	\N	\N	\N	\N	\N	substack	\N	2025-12-09 18:14:16.595295	2025-12-09 18:14:16.595295	\N	https://newsletter.dannylieberman.com/p/israel-is-the-best-place-in-the-world
37	Linus Health	AI-driven brain health platform helps payers detect cognitive impairment early and monitor members over time.	\N	\N	\N	\N	\N	substack	\N	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N	https://newsletter.dannylieberman.com/p/what-happened-yesterday-is-easy
39	Odaia AI	A real-time AI platform for pharma commercial teams (sales reps, MSLs, marketers).	\N	\N	\N	\N	\N	substack	\N	2026-01-07 12:33:34.105393	2026-01-07 12:33:34.105393	\N	https://newsletter.dannylieberman.com/p/paying-customers-is-proof
40	Oregon Freeze Dry Life Sciences	North America’s leading stabilizer of probiotics and other sensitive biological materials—serving pharma, nutraceutical, and veterinary customers.	\N	\N	\N	\N	\N	substack	\N	2026-01-07 12:46:31.747775	2026-01-07 12:51:12.590419	\N	https://newsletter.dannylieberman.com/p/customers-dont-want-to-hear-your
42	Giganet	SaaS for companies who employ gig workers in California.	\N	\N	\N	\N	\N	substack	\N	2026-01-07 14:19:29.342309	2026-01-07 14:19:29.342309	\N	https://newsletter.dannylieberman.com/p/from-hero-to-zero
5	Delve Health	Delve’s mission is simple but radical: deliver clinical trials at scale in patients’ homes.	Seed/Early Stage	1250000.00	2022-07-07 00:00:00	2016-01-01 00:00:00	\N	substack	\N	2025-12-05 09:37:27.898626	2026-01-07 14:24:14.003969	\N	https://newsletter.dannylieberman.com/p/foundermarket-misfit
19	Clear Thinking with Danny Lieberman	Strategic patterns, anti-patterns, and risk in life science AI.	\N	\N	\N	\N	\N	substack	\N	2025-12-08 16:39:48.538832	2026-06-29 09:54:19.95046	\N	https://newsletter.dannylieberman.com
\.


--
-- Data for Name: paths; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.paths (id, name, yaml, created_at, updated_at) FROM stdin;
3	Study and find a job in Biomedical engineering 	{"nodes": [{"id": "2020", "type": "decision", "label": "Decide to study bioengineering", "serial": 1, "optionality": {"collapses": false, "reason": "Bioengineering specialty doesn't guarantee employability", "irreversible": false}}, {"id": "2022-02", "type": "state", "label": "Russia invades Ukraine", "serial": 2, "optionality": null}, {"id": "2022-10", "type": "state", "label": "Hamas attack on Oct 7", "serial": 3, "optionality": null}, {"id": "2022-11", "type": "state", "label": "ChatGPT released", "serial": 4, "optionality": {"collapses": true, "reason": "Bioengineering specialty doesn't guarantee employability", "irreversible": true}}, {"id": "2022-2025", "type": "state", "label": "250 days of reserve duty", "serial": 5, "optionality": null}, {"id": "2025-1", "type": "state", "label": "Israeli Cyber/Defense sales: $80BN", "serial": 6, "optionality": null}, {"id": "2025-2", "type": "state", "label": "Israeli MedTech Sales: $3BN", "serial": 7, "optionality": null}, {"id": "2025-3", "type": "state", "label": "Israeli Digital Health sales: $850M", "serial": 8, "optionality": null}, {"id": "2026", "type": "state", "label": "No bioengineering jobs", "serial": 9, "optionality": null}], "edges": [{"from_node": "2020", "to_node": "2022-02", "reason": "Unreleated to studies"}, {"from_node": "2022-10", "to_node": "2022-2025", "reason": "Israeli mobilizes reservists for extended periods of time"}, {"from_node": "2022-10", "to_node": "2025-1", "reason": "War is good for cyber/defense sales"}, {"from_node": "2022-11", "to_node": "2025-1", "reason": "AI stimulates cyber and defense solutions"}, {"from_node": "2025-1", "to_node": "2026", "reason": "Job demand shifts to cyber/defense away from bio"}], "youAreHere": 9}	2026-01-09 13:33:45.266697+02	2026-01-11 11:18:04.190071+02
1	Medical device without connectivity	{"nodes": [{"id": "n1", "type": "decision", "label": "Update device with USB", "serial": 1, "optionality": null}, {"id": "n2", "type": "decision", "label": "Submit FDA Cyber", "serial": 2, "optionality": {"collapses": true, "reason": "FDA Cyber reviewer will fail the submission", "irreversible": true}}], "edges": [{"from_node": "n1", "to_node": "n2", "reason": "Engineering upgrade"}], "youAreHere": 1}	2026-01-07 19:21:51.714261+02	2026-01-18 11:10:49.051617+02
4	Medtech - Reimbursement is addressed late or last	{"nodes": [{"id": "2007", "type": "decision", "label": "Gastro medical device company started with academic IP", "serial": 1, "optionality": null}, {"id": "2014", "type": "decision", "label": "Start clinical trials to generate clinical evidence", "serial": 2, "optionality": null}, {"id": "2015-2019", "type": "state", "label": "First 5 clinical trials didn't show benefit", "serial": 3, "optionality": {"collapses": true, "reason": "Trials didn't show benefit", "irreversible": false}}, {"id": "2019", "type": "decision", "label": "Decided to tune device configuration and do pivotal trial for De Novo submission", "serial": 4, "optionality": null}, {"id": "Dec 1, 2021", "type": "state", "label": "Obtained statistically significant and clinically meaningful benefit vs the control, De Novo submission to FDA", "serial": 5, "optionality": null}, {"id": "Aug 20, 2022", "type": "state", "label": "De Novo clearance from FDA", "serial": 6, "optionality": null}, {"id": "Oct 1, 2023", "type": "decision", "label": "CMS declined HCPCS code :  \\"not suitable for inclusion in the HCPCS Level II code set", "serial": 7, "optionality": {"collapses": true, "reason": "CMS declined", "irreversible": false}}, {"id": "Jan 1, 2025", "type": "state", "label": "FEHB reimbursement with BC/BS", "serial": 8, "optionality": null}], "edges": [{"from_node": "2007", "to_node": "2014", "reason": "Fund-raising and R&D"}, {"from_node": "2014", "to_node": "2015-2019", "reason": "5 studies, failed in succession"}, {"from_node": "2019", "to_node": "Aug 20, 2022", "reason": "Pivotal trial received De Novo"}, {"from_node": "Aug 20, 2022", "to_node": "Oct 1, 2023", "reason": "Reimbursement code declined"}, {"from_node": "Oct 1, 2023", "to_node": "Jan 1, 2025", "reason": "Took Federal pathway "}], "youAreHere": 8}	2026-01-11 11:18:33.659813+02	2026-07-19 11:51:15.306051+03
\.


--
-- Data for Name: pattern_guest_link; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.pattern_guest_link (pattern_id, guest_id) FROM stdin;
7	1
2	2
5	2
6	2
4	3
7	4
6	4
3	5
7	5
1	5
7	8
7	9
13	11
3	14
5	13
4	15
21	19
22	20
24	24
25	24
26	24
27	24
28	24
39	26
40	26
41	26
42	21
43	5
53	21
54	21
\.


--
-- Data for Name: pattern_org_link; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.pattern_org_link (pattern_id, org_id) FROM stdin;
7	1
5	2
6	2
2	2
4	3
7	4
3	5
7	5
1	5
7	14
7	15
13	17
3	19
5	19
4	20
4	21
5	21
5	26
5	27
5	28
5	30
21	31
22	32
24	34
25	34
26	34
27	34
28	34
39	37
40	37
41	37
42	42
53	19
54	19
\.


--
-- Data for Name: pattern_post_link; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.pattern_post_link (pattern_id, post_id) FROM stdin;
7	1
5	2
4	3
2	3
6	4
3	4
3	5
7	5
1	5
13	17
13	18
3	21
5	21
4	22
21	25
22	26
24	28
25	28
26	28
27	28
28	28
39	30
40	30
41	30
42	35
3	1
43	1
53	37
54	37
\.


--
-- Data for Name: patterns; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.patterns (id, name, description, content_source, kind, search_vector, created_at, updated_at, deleted_at, story, taxonomy) FROM stdin;
1	Scale Economies	Unit costs decline as production volume increases due to fixed cost spreading and operational efficiencies. Barriers rise when competitors can't match your volume economics.	\N	pattern	'barrier':18 'competitor':21 'cost':4,13 'declin':5 'due':10 'econom':27 'economi':2 'effici':17 'fix':12 'increas':9 'match':24 'oper':16 'product':7 'rise':19 'scale':1 'spread':14 'unit':3 'volum':8,26	2025-12-05 09:37:27.889063	2025-12-05 09:37:27.889063	\N	\N	\N
2	Network Economies	Product value increases as more users join the network. Each additional user makes the product more valuable for everyone. See The Network Effects Bible for a detailed treatment of the different kinds of network effects.	\N	pattern	'addit':13 'bibl':26 'detail':29 'differ':33 'economi':2 'effect':25,37 'everyon':21 'increas':5 'join':9 'kind':34 'make':15 'network':1,11,24,36 'product':3,17 'see':22 'treatment':30 'user':8,14 'valu':4 'valuabl':19	2025-12-05 09:37:27.889063	2025-12-05 09:37:27.889063	\N	\N	\N
6	Cornered Resource	Exclusive access to a critical asset (data, talent, IP, relationships, raw materials) that others can't easily obtain.	\N	pattern	'access':4 'asset':8 'corner':1 'critic':7 'data':9 'easili':19 'exclus':3 'ip':11 'materi':14 'obtain':20 'other':16 'raw':13 'relationship':12 'resourc':2 'talent':10	2025-12-05 09:37:27.889063	2025-12-05 09:37:27.889063	\N	\N	\N
4	Switching Costs	Customers face high financial, time, or risk costs when changing suppliers, keeping them loyal even when alternatives exist.	substack	pattern	'altern':19 'chang':12 'cost':2,10 'custom':3 'even':17 'exist':20 'face':4 'financi':6 'high':5 'keep':14 'loyal':16 'risk':9 'supplier':13 'switch':1 'time':7	2025-12-05 09:37:27.889063	2025-12-08 16:46:58.565344	\N	\N	\N
7	Process Power	Efficiency grows when workflows become structured and repeatable.	substack	pattern	'becom':7 'effici':3 'grow':4 'power':2 'process':1 'repeat':10 'structur':8 'workflow':6	2025-12-05 09:37:27.889063	2025-12-08 16:34:04.819286	\N	\N	\N
13	Practice as Freedom	The concept that practice is essential for mastery and personal growth.	substack	pattern	'concept':5 'essenti':9 'freedom':3 'growth':14 'masteri':11 'person':13 'practic':1,7	2025-12-08 16:35:35.373609	2025-12-08 16:38:15.625567	\N	\N	\N
24	Assuming Non-Networked Devices Don't Have Security Vulnerabilities	Teams treat devices without network connectivity as inherently secure, ignoring physical access vectors, local interfaces (USB, Bluetooth), supply chain attacks, and firmware vulnerabilities. The absence of network connectivity creates a false sense of security that exempts the device from security review processes.	substack	anti-pattern	'absenc':35 'access':22 'assum':1 'attack':30 'bluetooth':27 'chain':29 'connect':16,38 'creat':39 'devic':5,13,48 'exempt':46 'fals':41 'firmwar':32 'ignor':20 'inher':18 'interfac':25 'local':24 'network':4,15,37 'non':3 'non-network':2 'physic':21 'process':52 'review':51 'secur':9,19,44,50 'sens':42 'suppli':28 'team':11 'treat':12 'usb':26 'vector':23 'vulner':10,33 'without':14	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	\N	\N
5	Branding	Customers attribute higher value based on reputation and trust, not just product features.	substack	pattern	'attribut':3 'base':6 'brand':1 'custom':2 'featur':14 'higher':4 'product':13 'reput':8 'trust':10 'valu':5	2025-12-05 09:37:27.889063	2025-12-08 17:37:39.582085	\N	\N	\N
22	Internet of Bodies (IoB)	Data from wearable medical devices and genomic sequencing creates a new reality. The IoB is exploding, and its data is fresh, rich, and personally relevant to our health.	substack	pattern	'bodi':3 'creat':13 'data':5,23 'devic':9 'explod':20 'fresh':25 'genom':11 'health':32 'internet':1 'iob':4,18 'medic':8 'new':15 'person':28 'realiti':16 'relev':29 'rich':26 'sequenc':12 'wearabl':7	2025-12-09 17:20:04.395605	2025-12-09 17:20:04.395605	\N	\N	\N
23	FDA Cyber compliance	Cybersecurity controls and risk management expectations for FDA-regulated laboratory and medical systems.	seed	pattern	'complianc':3 'control':5 'cyber':2 'cybersecur':4 'expect':9 'fda':1,12 'fda-regul':11 'laboratori':14 'manag':8 'medic':16 'regul':13 'risk':7 'system':17	2026-01-05 16:34:13.253693	2026-01-05 16:34:13.253693	\N	\N	\N
3	Counter-Positioning	A newcomer adopts a superior business model that established players can’t copy without damaging their existing business.	substack	pattern	'adopt':6 'busi':9,21 'copi':16 'counter':2 'counter-posit':1 'damag':18 'establish':12 'exist':20 'model':10 'newcom':5 'player':13 'posit':3 'superior':8 'without':17	2025-12-05 09:37:27.889063	2026-01-07 14:24:14.003969	\N	\N	\N
21	Boss is Stuck	A common issue where decision-makers fail to make decisions due to various reasons, leading to organizational paralysis.	substack	anti-pattern	'boss':1 'common':5 'decis':9,14 'decision-mak':8 'due':15 'fail':11 'issu':6 'lead':19 'make':13 'maker':10 'organiz':21 'paralysi':22 'reason':18 'stuck':3 'various':17	2025-12-09 16:50:22.136134	2026-01-12 11:44:17.863472	\N	\N	Decision & Cognitive Accelerator
25	Treating SBOM Generation as a Compliance Checkbox	Organizations generate Software Bill of Materials (SBOM) documents to satisfy regulatory requirements without integrating SBOM data into vulnerability management, procurement decisions, or incident response workflows. The SBOM exists as a static artifact that is never queried, updated, or actionable.	substack	anti-pattern	'action':46 'artifact':39 'bill':11 'checkbox':7 'complianc':6 'data':23 'decis':28 'document':15 'exist':35 'generat':3,9 'incid':30 'integr':21 'manag':26 'materi':13 'never':42 'organ':8 'procur':27 'queri':43 'regulatori':18 'requir':19 'respons':31 'satisfi':17 'sbom':2,14,22,34 'softwar':10 'static':38 'treat':1 'updat':44 'vulner':25 'without':20 'workflow':32	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	\N	\N
26	Deferring Cryptographic Agility Until Post-Market	Teams hardcode cryptographic algorithms, key lengths, and protocols into firmware/software without abstraction layers or update mechanisms, assuming cryptographic standards will remain secure throughout the 10-15 year device lifecycle. When quantum computing or cryptanalytic breakthroughs invalidate current algorithms, devices cannot be upgraded.	substack	anti-pattern	'-15':33 '10':32 'abstract':19 'agil':3 'algorithm':11,45 'assum':24 'breakthrough':42 'cannot':47 'comput':39 'cryptanalyt':41 'cryptograph':2,10,25 'current':44 'defer':1 'devic':35,46 'firmware/software':17 'hardcod':9 'invalid':43 'key':12 'layer':20 'length':13 'lifecycl':36 'market':7 'mechan':23 'post':6 'post-market':5 'protocol':15 'quantum':38 'remain':28 'secur':29 'standard':26 'team':8 'throughout':30 'updat':22 'upgrad':49 'without':18 'year':34	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	\N	\N
27	Assuming Cloud Provider Security Controls Are Sufficient for PHI	Teams rely exclusively on AWS/Azure/GCP platform-level security controls (IAM, encryption at rest, compliance certifications) without implementing application-layer protections specific to protected health information. The shared responsibility model is misunderstood - organizations assume HIPAA compliance is inherited from cloud provider rather than constructed at the application layer.	substack	anti-pattern	'applic':29,57 'application-lay':28 'assum':1,44 'aws/azure/gcp':14 'certif':25 'cloud':2,50 'complianc':24,46 'construct':54 'control':5,19 'encrypt':21 'exclus':12 'health':35 'hipaa':45 'iam':20 'implement':27 'inform':36 'inherit':48 'layer':30,58 'level':17 'misunderstood':42 'model':40 'organ':43 'phi':9 'platform':16 'platform-level':15 'protect':31,34 'provid':3,51 'rather':52 'reli':11 'respons':39 'rest':23 'secur':4,18 'share':38 'specif':32 'suffici':7 'team':10 'without':26	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	\N	\N
28	Testing Cybersecurity Requirements Only in Staging Environments	Security testing (penetration testing, vulnerability scanning, fuzzing) occurs exclusively in pre-production environments that differ significantly from production configurations. Production-specific attack surfaces (third-party integrations, enterprise network configurations, multi-tenancy boundaries) remain untested until post-market deployment. The assumption is that staging environment security testing is representative of production security posture.	substack	anti-pattern	'assumpt':52 'attack':31 'boundari':43 'configur':27,39 'cybersecur':2 'deploy':50 'differ':23 'enterpris':37 'environ':7,21,56 'exclus':16 'fuzz':14 'integr':36 'market':49 'multi':41 'multi-ten':40 'network':38 'occur':15 'parti':35 'penetr':10 'post':48 'post-market':47 'postur':64 'pre':19 'pre-product':18 'product':20,26,29,62 'production-specif':28 'remain':44 'repres':60 'requir':3 'scan':13 'secur':8,57,63 'signific':24 'specif':30 'stage':6,55 'surfac':32 'tenanc':42 'test':1,9,11,58 'third':34 'third-parti':33 'untest':45 'vulner':12	2026-01-07 12:16:57.511552	2026-01-07 12:31:56.559381	\N	\N	\N
39	Factual Reasoning	Analyzing present data, and observable conditions to draw conclusions.	substack	pattern	'analyz':3 'conclus':11 'condit':8 'data':5 'draw':10 'factual':1 'observ':7 'present':4 'reason':2	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N	\N	\N
40	Counterfactual Reasoning	Explores what could be under different conditions - imagining alternative scenarios to understand causal relationships and hidden risks.	substack	pattern	'altern':11 'causal':15 'condit':9 'could':5 'counterfactu':1 'differ':8 'explor':3 'hidden':18 'imagin':10 'reason':2 'relationship':16 'risk':19 'scenario':12 'understand':14	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N	\N	\N
41	Path Dependency	Once a path is chosen, you might reduce your risk today at the expense of missing a $100M exit in 7 years.	substack	anti-pattern	'100m':20 '7':23 'chosen':7 'depend':2 'exit':21 'expens':16 'might':9 'miss':18 'path':1,5 'reduc':10 'risk':12 'today':13 'year':24	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N	\N	\N
43	Founder–Market Misfit	Founder-market fit alone doesn't build a moat. It aligns motivation and market need — but not defensibility and competitive advantage.	substack	pattern	'advantag':25 'align':15 'alon':8 'build':11 'competit':24 'defens':22 'doesn':9 'fit':7 'founder':1,5 'founder-market':4 'market':2,6,18 'misfit':3 'moat':13 'motiv':16 'need':19	2026-01-07 14:24:14.003969	2026-01-11 17:58:02.839546	\N	\N	Founder / Financing Anti-Pattern
42	Recoil	An anti-design pattern where high performers feel depressed after a big win. Happens to star athletes, engineers and operators.	substack	anti-pattern	'anti':4 'anti-design':3 'athlet':19 'big':14 'depress':11 'design':5 'engin':20 'feel':10 'happen':16 'high':8 'oper':22 'pattern':6 'perform':9 'recoil':1 'star':18 'win':15	2026-01-07 14:19:29.342309	2026-01-11 18:12:35.54517	\N	\N	Decision & Cognitive Accelerator
48	Capital Structure Trap	Late stage capital can keep a company alive long enough to bring the tech to an acquirer and destroy equity outcomes.	\N	anti-pattern	'acquir':20 'aliv':11 'bring':15 'capit':1,6 'compani':10 'destroy':22 'enough':13 'equiti':23 'keep':8 'late':4 'long':12 'outcom':24 'stage':5 'structur':2 'tech':17 'trap':3	2026-01-11 16:59:46.314424	2026-01-11 17:31:05.65892	\N	# Pattern: "The Capital Structure Trap"\n**Category:** Anti-Pattern (Financing/Exit Strategy)\n\n---\n\n## Pattern Statement\n\n- What happens when a good team tries to survive inside a broken market?\n\n- Liquidation preferences destroy equity outcomes\n\n- Successful exits” become personal failures\n\n- When breakthrough science hits difficult commercialization, raising large late-stage capital through structured instruments (convertible notes, debt with preferences) can keep the company alive short term until an acquisition\n\n\n\n\n---\n\n## Recognition Signals\n\n### Early Warning Signs:\n- Raising follow-on round 10x larger than previous (e.g., $12M Series A → $100M Series B)\n- Choosing convertible debt over equity "for flexibility"\n- Justification: "We're growing so fast, equity would be too dilutive"\n- Capital structure becomes: Small equity base + Massive debt sitting on top\n- Burn rate accelerates dramatically post-funding\n- Commercialization milestones keep slipping despite capital infusion\n\n### The Setup:\n1. **Strong science** (Nature/Science publication, validated technology)\n2. **Clear clinical need** (large patient population, unmet need)\n3. **Capital-intensive business model** (whole-genome sequencing, CLIA labs, global ops)\n4. **Difficult path to revenue** (long sales cycles, reimbursement uncertainty, conservative buyers)\n5. **Investor enthusiasm** based on technology, not traction\n\n### The Trap Triggers:\n- Company raises large structured financing when:\n  - Revenue traction insufficient to justify equity valuation\n  - Next equity round would be "too dilutive" \n  - Investors want downside protection (hence debt/notes)\n  - Alternative is shutting down\n\n---\n\n## The Mechanism\n\n### Act 1: The Science Win (Years 0-2)\n- Founders: 80-90% ownership\n- Technology validated in academic setting\n- Seed round: $1-2M on $5-6M valuation\n- Still founder-controlled, mission intact\n\n### Act 2: The Growth Acceleration (Years 2-3)\n- Series A: $10-15M on $40-50M valuation\n- Founders: 55-60% ownership\n- Hiring accelerates, infrastructure builds\n- Early commercial traction, but not enough\n\n### Act 3: The Trap Springs (Years 3-4)\n- **Decision point:** Need $50-100M to scale\n- **Option A:** Equity raise at lower valuation (down round, massive dilution)\n- **Option B:** Structured financing (convertible note/debt with liquidation preference)\n- **Choice:** Option B - "preserves optionality"\n\n**The Fatal Math:**\n- $100M note sits ON TOP of equity in liquidation waterfall\n- Founders: diluted to 30-35% of equity\n- BUT: Equity only gets paid AFTER note holders\n- Liquidation preference means: First $100M goes to note holders\n\n### Act 4: The Exit Reality (Years 4-5)\n- Strategic acquisition: $70-95M\n- Note holders: Recover 70-95% of capital\n- Equity holders (founders + early investors): $0 - $10M split among everyone\n- Per founder: $1-2M for 5 years work\n- Opportunity cost: Negative\n\n---\n\n## Why It Happens\n\n### Founder Psychology:\n1. **Mission-driven persistence** - "We're so close to helping patients"\n2. **Sunk cost fallacy** - "We've come too far to quit"\n3. **Technology confidence** - "Our science is better, we just need more time"\n4. **Shutdown avoidance** - "Taking $100M debt is better than shutting down"\n5. **Optimism bias** - "We'll grow into the valuation, this protects us"\n\n### Investor Behavior:\n1. **Downside protection** - Late-stage investors demand liquidation preferences\n2. **Portfolio math** - VCs need some investments to "not lose money"\n3. **Time value** - 5 years in, investors want liquidity/conclusion\n4. **Reputation management** - "Strategic exit" sounds better than "shutdown"\n\n### Market Dynamics:\n1. **IPO window closed** - Can't go public on promise\n2. **M&A market weak** - Strategic acquirers not paying premiums\n3. **Revenue traction insufficient** - Can't command growth equity valuations\n4. **Competitive pressure** - Better-capitalized competitors exist\n\n---\n\n## The Outcome Pattern\n\n**Typical Exit Economics:**\n\n| Stakeholder | Investment | Exit Return | Outcome |\n|-------------|-----------|-------------|---------|\n| Seed Investors | $1M | $0-100K | -90% loss |\n| Series A Investors | $12M | $0-2M | -83% loss |\n| Note Holders | $100M | $70-85M | -15-30% loss |\n| Founders (4 people) | 5 years work | $1-2M each | Opportunity cost negative |\n| Technology | - | Lives on | Mission partially succeeded |\n\n**The Paradox:**\n- ✅ Technology validated and acquired\n- ✅ Team stays employed\n- ✅ Patients will eventually benefit\n- ❌ Founders made less than senior engineers\n- ❌ Early believers lost money\n- ❌ Late investors lost some money\n\n---\n\n## Case Studies\n\n### Primary Example: C2i Genomics\n- **Raised:** $112M (seed $1.2M → Series A $12M → Note $100M)\n- **Exit:** $70M cash + $25M earnout to Veracyte\n- **Founder outcome:** ~$1-2M each for 5 years\n- **Technology:** Whole-genome MRD, 100x sensitivity, Nature Medicine validated\n- **What killed it:** Capital structure + slow commercialization + burn rate\n\n### Related Examples:\n\n**Pear Therapeutics:** \n- Raised $400M+ → Bankruptcy → Assets sold for $6M\n- Difference: C2i got strategic exit, Pear got liquidation\n- Similarity: Great science, difficult commercialization, capital structure doom\n\n**Theranos** (extreme version): \n- Capital structure concealed fundamental science failure\n- C2i's science actually worked - this is important distinction\n\n---\n\n## Application to TechBio Pattern Recognition\n\n**When advising founders, ask:**\n\n1. **"What's the capital efficiency path to meaningful revenue?"**\n   - If answer requires >$50M before first dollar, danger zone\n   - Whole-genome approaches are inherently capital-intensive\n\n2. **"Can you prove commercial traction before raising huge rounds?"**\n   - If no, you're raising on promise, which leads to structured deals\n   - Structured deals destroy exit economics\n\n3. **"What's your burn rate doing to your runway?"**\n   - C2i: 64 employees, CLIA lab, R&D center in Israel\n   - This forces you to raise large rounds on investor timeline, not traction timeline\n\n4. **"Who are you competing against for the same use case?"**\n   - If competitor raised $1B and you raised $100M, you're playing catch-up\n   - MRD space: Guardant ($1B+), Natera, Grail all competing\n\n5. **"Will a $70M exit feel like success or failure to you?"**\n   - If you've raised $112M, $70M is failure for most stakeholders\n   - This should inform capital raising strategy upfront\n\n---\n\n## The Counter-Pattern: "Veracyte's Playbook"\n\n**How to avoid the trap:**\n\n1. **Start with one validated, reimbursed test** (Afirma thyroid)\n2. **Achieve profitability at small scale** (prove unit economics)\n3. **Go public on traction, not promise** (IPO 2013 on real revenue)\n4. **Use public market currency for M&A** (stock acquisitions, not cash burn)\n5. **Acquire proven assets, don't build from scratch** (Decipher, HalioDx, C2i)\n\n**Veracyte's M&A strategy:**\n- They paid $600M for Decipher (which had $40M revenue, NCCN guidelines)\n- They paid $318M for HalioDx (European manufacturing, Immunoscore)\n- They paid $70M for C2i (validated tech, but no revenue)\n\n**The lesson:** Veracyte only took big M&A risk AFTER they had:\n- Public market access\n- Strong balance sheet  \n- Existing commercial infrastructure\n- Reimbursement expertise\n\n---\n\n## The Pattern Factory Distillation\n\n**Pattern Name:** "Capital Structure Trap" or "The Structured Financing Death Spiral"\n\n**One-Liner:** When great science meets slow commercialization, structured financing (notes/debt with liquidation preferences) saves the company but kills founder economics.\n\n**Frequency:** Increasingly common in capital-intensive life sciences (genomics, diagnostics, digital therapeutics)\n\n**Severity:** High - Founders work 5+ years for $1-2M while technology succeeds\n\n**Prevention:** \n1. Raise less capital more slowly\n2. Achieve commercial traction before scale\n3. Avoid structured instruments unless exit valuation will be 3x+ the note amount\n4. If you must raise structured financing, negotiate earnouts that benefit founders\n5. Consider strategic partnership over large late-stage VC rounds\n\n**The Brutal Truth:**\n> "Better to build a $50M company on $10M raised than a $70M exit on $112M raised. The first makes founders wealthy. The second makes founders employees who worked for free."\n\n---\n\n## For the Newsletter\n\n**Subject:** "When $112M Raised Means $1M Take-Home: The Capital Structure Trap"\n\n**Hook:** "C2i Genomics had everything: Nature Medicine publication, cancer survivor CEO, 100x better technology than competitors, and $112M in funding. So why did the founders make less than senior engineers when they sold for $70M?"\n\n**The Pattern:** Capital structure matters more than total capital raised. When late-stage structured financing (convertible notes with liquidation preferences) sits on top of your equity, even successful exits become financial failures for founders and early investors.\n\n**Key Insight:** Veracyte paid $600M for Decipher (which had revenue and guidelines) but only $70M for C2i (which had better science). The difference? Commercial validation >> Scientific validation in strategic M&A.	Founder / Financing Anti-Pattern
47	Answers don't bring buyers	Don't educate	\N	anti-pattern	'answer':1 'bring':4 'buyer':5 'educ':8	2026-01-11 16:12:39.209728	2026-01-11 17:31:43.508829	\N	## Pattern: **Answers Don’t Bring Buyers**\n\n**Category:** Anti-Pattern (Content Strategy, Consulting, Sales)\n\n---\n\n## Context\n\nExpert-led businesses that use content to attract clients, including:\n- consultants\n- advisors\n- fractional executives\n- technical founders selling services\n\n---\n\n## Observed Behavior\n\nContent that **fully explains how to solve a problem** attracts:\n- information-seekers\n- free-resource collectors\n- non-buyers\n\nContent that **reveals a flawed mental model** attracts:\n- decision-makers\n- budget holders\n- buyers\n\n---\n\n## Assumed Causal Model\n\n- High-quality explanations build trust  \n- Solving the problem in public demonstrates value  \n- Engagement correlates with commercial intent  \n\n---\n\n## Actual System Behavior\n\n- Complete solutions eliminate the need to hire the expert  \n- Engagement optimizes for consumption, not commitment  \n- Requests skew toward “more information,” not paid work  \n\n---\n\n## The Hidden Failure Mode\n\nWhen expertise is delivered as **complete answers**, it substitutes for economic value.\n\nHelpfulness removes the incentive to buy.\n\n---\n\n## Why This Becomes a Pattern\n\nThis structure repeats when:\n- creators optimize for clarity over judgment\n	Demand Formation Anti-Pattern
45	The PDT Graveyard	Prescription digital therapeutics fail payers, physicians and patients.	\N	anti-pattern	'digit':5 'fail':7 'graveyard':3 'patient':11 'payer':8 'pdt':2 'physician':9 'prescript':4 'therapeut':6	2026-01-11 14:26:28.87101	2026-01-11 17:31:28.658773	\N	## Pattern: **The PDT Graveyard**\n\n**Category:** Anti-Pattern (Digital Therapeutics, Commercialization, Financing)\n\n---\n\n## Context\n\nPrescription Digital Therapeutics (PDTs) positioned as “digital pharma”:\n- software prescribed by clinicians\n- reimbursed by payers\n- regulated like medical products\n\n---\n\n## Observed Category Behavior\n\nAcross PDT companies:\n- Regulatory clearance is achievable\n- Reimbursement is rare or delayed\n- Commercial adoption remains fragmented\n- Capital requirements escalate post-clearance\n\nCategory leaders and followers exhibit similar outcomes.\n\n---\n\n## Assumed Causal Model\n\n- Regulatory clearance creates payer legitimacy  \n- Clinical evidence drives reimbursement  \n- Digital delivery lowers distribution friction  \n- Capital enables scale once approval is achieved  \n\n---\n\n## Actual System Behavior\n\n- Payers refuse coverage despite clinical evidence  \n- Clinicians lack incentive and workflow integration  \n- Patients face prescription and fulfillment friction  \n- Revenue lags persist for years post-clearance  \n\nRegulatory approval does not resolve distribution or payment.\n\n---\n\n## The Hidden Failure Mode\n\nPDTs face a **three-way coordination failure**:\n\n- **Payers** do not reimburse novel software treatments  \n- **Clinicians** do not adopt prescription software workflows  \n- **Patients** do not experience pharmacy-like fulfillment  \n\nNo actor can move without the others.\n\n---\n\n## Capital Response Pattern\n\nWhen commercialization stalls post-clearance:\n- Companies raise large late-stage capital to survive\n- Financing shifts from equity to structured instruments\n- Capital preserves operations but distorts exit economics\n\nThis frequently leads to the **Capital Structure Trap**.\n\n---\n\n## Outcome Pattern\n\nTypical outcomes include:\n- Partial asset sales\n- Strategic acquisitions below capital raised\n- Founder and early investor economic loss\n- Technology survives; companies do not\n\n---\n\n## Why This Becomes a Pattern\n\nThis structure repeats across:\n- behavioral health PDTs\n- metabolic disease PDTs\n- neurological and psychiatric software therapies\n\nThe failure is not executional.\nIt is **structural**.\n\n---\n\n## Pattern Test (Investor)\n\n**If a PDT requires payer reimbursement to exist and lacks a working distribution path today, this pattern likely applies.**\n	Category Anti-Pattern
46	Clinical is not commercial	Building for regulatory approval doesn't guarantee commercial success	\N	anti-pattern	'approv':8 'build':5 'clinic':1 'commerci':4,12 'doesn':9 'guarante':11 'regulatori':7 'success':13	2026-01-11 15:24:05.962319	2026-01-11 17:32:25.851222	\N	## Pattern: Clinical Is Not Commercial\n\n**Category:** Anti-Pattern (Clinical R&D, GTM Strategy)\n\n**Context:** Medical device company commercializing academic IP via the FDA De Novo pathway.\n\n**Observed Outcome:** FDA clearance achieved. Commercial adoption stalled due to reimbursement dynamics.\n\n\n---\n\n## Timeline\n\n- **2007** — Company founded with academic IP  \n- **2014** — Clinical trials initiated  \n- **2015–2019** — Studies fail to demonstrate benefit  \n- **2019** — Device configuration tuned; pivotal trial initiated  \n- **2022** — FDA De Novo clearance obtained  \n- **2023** — CMS declines HCPCS code  \n- **2025** — FEHB / BCBS reimbursement achieved via federal pathway  \n\n---\n\n## What Founders and Investors Believed\n\n- FDA clearance would unlock reimbursement.\n- Clinical significance would translate into payer acceptance\n- Regulatory approval would drive reimbursement.\n\n---\n\n## What the Market Did\n\n- CMS evaluated value using a different logic than FDA\n- No new HCPCS code meant no payer category\n- Revenue stalled for multiple years post-clearance\n- Only limited federal coverage was achieved\n\n---\n\n## The Hidden Failure Mode\n\nRegulatory success created a false sense of completion. Economic access for patients was never secured.\n\nThe core economic question was not answered during product development and validation: *Who pays, from which budget, and why?*\n\n---\n\n## Why This Becomes a Pattern\n\nThis structure repeats across:\n\n- De Novo medical devices  \n- Digital therapeutics \n- Diagnostic adjuncts  \n- Workflow-neutral clinical tools\n\nThe delay between regulatory approval and reimbursement is **not accidental**.  \nIt is **structural**.\n\n---\n\n## Pattern Test (Investor)\n\n*If FDA approval is your primary commercial milestone, this pattern likely applies.*\n	Regulatory / GTM Anti-Pattern
52	PF Design patterns	Pattern factory design patterns	\N	pattern	'design':2,6 'factori':5 'pattern':3,4,7 'pf':1	2026-01-21 10:46:21.473814	2026-01-22 14:27:48.634045	\N	Component: /src/lib/CheckboxField.svelte\n\nProps:\n1.  id (required) - HTML id for the checkbox\n2.  checked (optional, default: false) - Binding for checkbox state\n-  label (required) \n- Main label text\n-  description (optional) - Secondary description text below label\n•  disabled (optional, default: false) - Disabled state\n\nUsage example:\n\n```\n<CheckboxField\n  id="my-checkbox"\n  bind:checked={myValue}\n  label="Enable feature"\n  description="This will activate the feature"\n/>\n```	Decision & Cognitive Accelerator
51	Capitalized optionality without closure	Create healthcare value without committing to irreversible constraints	\N	pattern	'capit':1 'closur':4 'commit':9 'constraint':12 'creat':5 'healthcar':6 'irrevers':11 'option':2 'valu':7 'without':3,8	2026-01-12 11:24:13.717305	2026-01-21 10:38:51.48146	\N	# Pattern Story  \n## Capitalized Optionality Without Closure\n\n---\n\n## Context\n\nThis pattern emerged while exploring **Byte51** data on digital health investors.  \nThe initial goal was not to validate a thesis, but to explore whether Byte51 was more useful for *path analysis* or *macro-pattern detection*.\n\nWhat surfaced was neither subtle nor isolated.\n\nAcross multiple digital health–focused funds, the same structural shape appeared:\n- Large capital deployment\n- Limited liquidity\n- Minimal regulatory conversion\n- No durable value floor\n\nThis is a **macro anti-pattern**, not a company-level failure.\n\n---\n\n## The Observation\n\nUsing aMoon as a representative example:\n\n- ~$1.5B invested in digital health\n- ~$425M returned (IPO + M&A combined)\n\nIgnoring:\n- liquidation preferences\n- ratchets\n- DPI vs TVPI nuances\n- time value of money\n\n**Capital was not recycled.**\n\nMore importantly:\n> Almost none of the portfolio companies achieved regulatory approval of any kind.\n\nThis was not unique to one fund.  \nDifferent funds, similar vintages, same shape.\n\n---\n\n## What This Is *Not*\n\nThis pattern is not explained by:\n- poor founder quality\n- isolated diligence failures\n- bad timing\n- COVID-era distortions\n- market cyclicality\n\nThose explanations fail once the same structure repeats across funds and taxonomies.\n\nThis is not a portfolio problem.  \nIt is a **belief system problem that was capitalized at scale**.\n\n---\n\n## The Capitalized Belief\n\nThe implicit belief underlying these investments:\n\n> “We can create healthcare value without committing to irreversible constraints.”\n\nIn practice, this meant systematically avoiding:\n- FDA approval\n- reimbursement pathways\n- regulated claims\n- clinical endpoints\n- security accountability\n- downstream liability ownership\n\nThis was often described as:\n- “regulatory arbitrage”\n- “enterprise software”\n- “workflow enablement”\n- “platform-first, regulation later”\n\nBut functionally, it was **constraint avoidance disguised as speed**.\n\n---\n\n## Why It Looked Rational\n\nThe logic felt coherent:\n\n- Regulation is slow\n- Healthcare buyers are conservative\n- Software scales\n- SaaS multiples are attractive\n\nSo companies positioned themselves *adjacent* to healthcare value creation, but outside its irreversible commitments.\n\nThe problem:\n> In healthcare, **constraints are the moat**.\n\nBy avoiding them, companies removed the very mechanisms that produce durable value.\n\n---\n\n## The Missing Mechanism: Closure\n\nHealthcare value is created through **closure**, not momentum.\n\nClosure looks like:\n- regulatory clearance\n- reimbursement eligibility\n- liability ownership\n- budget line-items\n- procurement inevitability\n\nMost digital health companies postponed closure indefinitely.\n\nThey did not fail regulatory paths.  \nThey **never entered them**.\n\nWhat they accumulated instead:\n- pilots instead of contracts\n- design partners instead of customers\n- narratives instead of pricing power\n- optionality instead of inevitability\n\nOptionality feels safe.  \nLPs do not get paid in optionality.\n\n---\n\n## The Byte51 Insight\n\nByte51 did not “predict failure.”\n\nIt surfaced something more important:\n\n> Capital flowed repeatedly into entities that never crossed known value thresholds.\n\nThose thresholds were visible *ex ante*:\n- FDA clearance\n- CMS reimbursement\n- hospital procurement gates\n- enterprise security standards\n\nByte51 functions best as a **wreckage map**, not a compass.\n\nWreckage maps reveal **broken navigation rules**.\n\n---\n\n## The Anti-Pattern\n\n### Capitalized Optionality Without Closure\n\n**Signals**\n- Regulatory engagement explicitly postponed\n- Value framed as “platform” or “workflow” without claims\n- Speed prioritized over irreversible commitments\n\n**Belief**\n- “We’ll figure out regulation, reimbursement, and risk later”\n\n**Outcome**\n- Liquidity without intrinsic value\n- Weak pricing power\n- Acquirer disengagement\n- IPO market rejection\n- Category-wide underperformance\n\nNo villains required.  \nJust physics.\n\n---\n\n## The Non-Obvious Failure Mode\n\nLiquidity events occurred **without value creation**.\n\nWhen exit markets closed:\n- there was no regulatory asset\n- no reimbursable claim\n- no unavoidable buyer\n\nJust companies requiring a *next* buyer.\n\nThat is why the category froze simultaneously.\n\n---\n\n## Why This Pattern Persists\n\nBecause:\n- optionality masquerades as risk management\n- constraint looks like friction\n- early exits mask missing fundamentals\n- no one is rewarded for stopping a deal early\n\nUntil the cycle ends.\n\n---\n\n## Implications\n\nThis pattern is not a critique of digital health.\n\nIt is a critique of:\n> **Capitalization strategies that avoid irreversible commitment in regulated markets.**\n\nThere are winners.\nThey look slower early.\nThey accept constraint.\nThey build real moats.\n\nThey were drowned out by louder stories.\n\n---\n\n## Appendix A: Byte51 Agent Taxonomy (Draft)\n\n**Goal:**  \nUse agents to surface *macro anti-patterns*, not predict winners.\n\n### Agent Dimensions\n\n**1. Sector Taxonomy**\n- Digital health\n- Diagnostics\n- Medical devices\n- Digital therapeutics\n- Workflow / analytics / engagement\n\n**2. Regulatory Posture**\n- FDA-cleared\n- FDA-pending\n- FDA-avoided\n- Explicitly non-regulated claims\n\n**3. Reimbursement Exposure**\n- CMS code present\n- Reimbursement-dependent\n- Buyer-funded only\n- Pilot-funded\n\n**4. Capital Efficiency**\n- Capital in\n- Capital out\n- Time to liquidity\n- DPI proxy\n\n**5. Exit Type**\n- Strategic acquisition\n- Financial acquisition\n- IPO\n- Acqui-hire / asset sale\n\n**6. Value Closure Signals**\n- Regulatory clearance achieved\n- Procurement contracts signed\n- Pricing power demonstrated\n\n### Agent Output\n\n- Identify repeated structures where:\n  - capital deployed >> value realized\n  - regulatory posture = avoidance\n  - exits decouple from intrinsic value\n\nNot prediction.  \n**Pattern detection.**\n\n---\n\n## Appendix B: The One Question\n\n> **“What irreversible constraint must this company cross for value to exist — and when?”**\n\nIf the answer is:\n- vague\n- deferred\n- dependent on future buyers\n- framed as “optional”\n\nThen:\n- value is not inevitable\n- risk is externalized\n- capital is underwriting belief, not closure\n\nThis question would have killed ~70% of these deals early.\n\nThat is its job.\n\n---\n\n## Status\n\nThis is a **Pattern Story**, not a Pattern Card.\n\nIt captures a thought that would not go away.\n\nLater, this can become:\n- a Pattern Factory card\n- an OpenCRO diagnostic\n- an LP diligence filter\n\nFor now, it is written so it cannot be forgotten.\n	Category Anti-Pattern
50	Patterns	Patterns, stories, threats and cards	\N	pattern	'card':6 'pattern':1,2 'stori':3 'threat':4	2026-01-11 18:04:14.902078	2026-01-22 14:23:04.415877	\N	## Pattern: **Taxonomy Drift**\n\n**Category:** Meta-Pattern (Pattern Authoring, System Design)\n\n---\n\n## Context\n\n**Pattern Cards**\n\n- Patterns are general Design | Anti-Design patterns that belong to a taxonomy like Demand Formation\n- Threat scenarios hasMany pattern cards\n- PatternCard belongsTo Pattern\n- Pattern hasMany PatternCards\n\n\n**Pattern libraries** \n- tend to degrade over time when:\n- taxonomy boundaries blur\n- team behavior is mistaken for root cause\n- narrative intuition overrides structural causality\n\nThis pattern exists to prevent misclassification.\n\n---\n\n## Core Principle\n\n**Patterns explain systems.  \nTeams explain interactions.**\n\n---\n\n## Decision Rubric\n\nUse this rubric **after extracting a pattern**, before assigning taxonomy.\n\nDo not ask *what the story is about*.  \nAsk **where the failure originates**.\n\n---\n\n## Step 1 — Identify the First Broken Assumption\n\nWrite the belief that had to be wrong for the failure to occur.\n\nExamples:\n- “Regulatory approval unlocks revenue”\n- “Customers want better features”\n- “More effort fixes systemic problems”\n- “More capital preserves optionality”\n\nIf you cannot state the assumption clearly, the pattern is not ready.\n\n---\n\n## Step 2 — Origin Test\n\nAnswer **Yes / No** to each question, in order.\n\n---\n\n### A. Category / Market Structure\n\n**Would this failure still occur with an excellent team, strong execution, and ample capital?**\n\n- Yes → **Category Anti-Pattern**\n- No → Continue\n\n---\n\n### B. Regulatory / Capital / GTM Systems\n\n**Is value blocked by external systems (regulators, payers, financing mechanics, buyer incentives)?**\n\n- Yes → **Regulatory / Capital / GTM Anti-Pattern**\n- No → Continue\n\n---\n\n### C. Demand Formation / Market Interpretation\n\n**Is the core failure a misunderstanding of what customers are actually buying or valuing?**\n\n- Yes → **Demand Formation Anti-Pattern**\n- No → Continue\n\n---\n\n### D. Founder / Company Structure\n\n**Did ownership, incentives, governance, or capital structure distort outcomes despite real demand?**\n\n- Yes → **Founder / Company Anti-Pattern**\n- No → Continue\n\n---\n\n### E. Decision & Cognitive Accelerator (Team)\n\n**Is this a predictable human response to ambiguity, pressure, or constraint rather than the root cause?**\n\n- Yes → **Decision & Cognitive Accelerator**\n- No → Re-express the pattern (layers are mixed)\n\n---\n\n## Step 3 — Replacement Test\n\nAsk:\n\n**If the entire team were replaced tomorrow, would this failure still occur?**\n\n- Yes → Not a Team pattern\n- No → Team pattern\n\nThis test overrides intuition.\n\n---\n\n## Step 4 — Counterfactual Test\n\nAsk:\n\n**What would have needed to change *first* to prevent this failure?**\n\n- Market structure → Category\n- External permission or capital mechanics → Regulatory / Capital\n- Interpretation of customer value → Demand Formation\n- Incentives or ownership → Founder / Company\n- Cognitive load or decision dynamics → Team\n\nChoose the **earliest causal intervention**.\n\n---\n\n## Step 5 — One-Taxonomy Rule\n\nEach pattern must have:\n- One primary taxonomy\n- No blended root causes\n\nDownstream links may exist, but origin must be singular.\n\n---\n\n## Red Flags (Stop and Rewrite)\n\nRework the pattern if it:\n- sounds like advice\n- diagnoses personality or culture\n- praises or blames individuals\n- could be fixed by “better leadership”\n\nThese indicate interaction-level thinking, not system-level diagnosis.\n\n---\n\n## Final Test\n\n**Could this pattern be true even if everyone involved was competent, well-intentioned, and working hard?**\n\nIf yes, the pattern is at the correct abstraction level.\n\n---\n\n## Outcome\n\nThis rubric prevents:\n- taxonomy inflation\n- moralized failure analysis\n- pattern libraries turning into essays\n\nIt preserves:\n- structural clarity\n- founder dignity\n- system-level truth\n	Decision & Cognitive Accelerator
49	You're not in Kansas anymore	Market or your understanding of market needs changes	\N	anti-pattern	'anymor':6 'chang':14 'kansa':5 'market':7,12 'need':13 're':2 'understand':10	2026-01-11 17:45:33.569297	2026-01-28 08:15:43.952554	\N	## Pattern: **You’re Not in Kansas Anymore**\n\n**Category:** Anti-Pattern (Demand Formation, Market Interpretation)\n\n---\n\n## Context\n\nFounder-led companies operating in evolving or complex markets where:\n- customer understanding deepens over time\n- sales motion reveals hidden constraints\n- market structure shifts due to regulation, scale, or buyer maturity\n\n---\n\n## Assumed Causal Model\n\n- The original business model defines the company\n- Improving execution will unlock growth\n- Customer feedback refines the product, not the business\n\n---\n\n## Actual System Behavior\n\n- Demand evolves faster than the company’s mental model\n- Customers buy outcomes adjacent to, not identical with, the original offering\n- Revenue exists, but under a different framing than expected\n\n---\n\n## The Hidden Failure Mode\n\nThe company continues to design, build, and sell for a **demand model that no longer exists**.\n\nExecution improves, but leverage does not.\n\n---\n\n## Recognition Signals\n\n- Customers pay for work that is described as “non-core”\n- Sales close for reasons not reflected in product positioning\n- Revenue grows through exceptions, services, or workarounds\n- The business feels “close” but structurally constrained\n\n---\n\n## Why This Becomes a Pattern\n\nFounders anchor on their first correct insight and fail to update it as conditions change.\n\nMarkets move.\nDemand re-forms.\nThe business does not.\n\n---\n\n## Outcome Pattern\n\n- Growth stalls despite strong customer relationships\n- Value is created, but not captured at scale\n- Competitors or acquirers monetize the reframed demand\n\n---\n\n## Pattern Test\n\n**If customers reliably pay you for something you don’t believe is your real business, this pattern applies.**\n	Demand Formation Anti-Pattern
54	Defective systems are insecure systems	A common mistake organizations make is assuming that reactive network defense tools can protect against exploitation of software defects.	substack	anti-pattern	'assum':12 'common':7 'defect':1,24 'defens':16 'exploit':21 'insecur':4 'make':10 'mistak':8 'network':15 'organ':9 'protect':19 'reactiv':14 'softwar':23 'system':2,5 'tool':17	2026-06-29 09:54:19.95046	2026-06-29 09:55:57.002339	\N	\N	Category Anti-Pattern
53	Business Threat Modeling	A continuous threat assessment process for software development organisations that employs a systematic risk analysis of complex software systems along with quantitative evaluation of how well removing software defects reduces risk.	substack	pattern	'along':23 'analysi':18 'assess':7 'busi':1 'complex':20 'continu':5 'defect':32 'develop':11 'employ':14 'evalu':26 'model':3 'organis':12 'process':8 'quantit':25 'reduc':33 'remov':30 'risk':17,34 'softwar':10,21,31 'system':22 'systemat':16 'threat':2,6 'well':29	2026-06-29 09:54:19.95046	2026-07-19 12:20:09.751136	\N	\N	Decision & Cognitive Accelerator
\.


--
-- Data for Name: posts; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.posts (id, name, description, content_url, content_source, published_at, created_at, updated_at, deleted_at) FROM stdin;
2	The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma	Early-stage TechBio companies build moats through Cornered Resources or Counter-Positioning. Itay and Beyond uses human-derived brain organoids to replace failing animal models.	https://newsletter.dannylieberman.com/p/the-great-brain-bet-how-human-derived	substack	\N	2025-12-05 09:37:27.878456	2025-12-05 09:37:27.878456	\N
3	Switching Costs	Switching Costs create customer lock-in through integration complexity and workflow dependencies. SAP and Flatiron Health demonstrate how captive customers become defensible moats.	https://newsletter.dannylieberman.com/p/switching-costs	substack	\N	2025-12-05 09:37:27.879595	2025-12-05 09:37:27.879595	\N
4	Why do we buy Brands: For good feeling or good value?	Brand Power commands premium pricing through emotional connection and trust. Analysis of Tiffany, Carolina Lemke Berlin, and Selmer reveals leverage metrics from heritage cultivation.	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling	substack	\N	2025-12-05 09:37:27.880717	2025-12-05 09:37:27.880717	\N
5	AI and Robotics Rewrite Drug Discovery	Process Power builds competitive moats through years of pattern accumulation. Iktos integrates AI with robotics for drug discovery orchestration competitors can't easily replicate.	https://newsletter.dannylieberman.com/p/ai-and-robotics-rewrite-drug-discovery	substack	\N	2025-12-05 09:37:27.88151	2025-12-05 09:37:27.88151	\N
6	From Personal Struggle to Global Solution: Wessam Sonbol's Mission to Bring Trials Home	Wessam Sonbol founded Delve Health after his mother's trial access struggle, bringing clinical trials home with wearables, AI agents, and multilingual support.	https://www.healthcareittoday.com/2025/10/17/from-personal-struggle-to-global-solution-wessam-sonbols-mission-to-bring-trials-home-life-sciences-today-podcast-episode-31/	podcast	\N	2025-12-05 09:37:27.88399	2025-12-05 09:37:27.88399	\N
21	The 5 step hack to Brand Power if you’re a super model	Why do we buy Brands: For good feeling or good value?	https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling	substack	2025-11-07 00:00:00	2025-12-08 16:39:48.538832	2025-12-08 17:37:39.582085	\N
17	A Better Version of You	Practice is the Enemy and the Gift	https://newsletter.dannylieberman.com/p/a-better-version-of-you	substack	2025-10-03 00:00:00	2025-12-08 16:35:35.373609	2025-12-08 16:38:15.625567	\N
18	Business Development for Life Sciences companies with BDaaS	Podcast episode discussing business development strategies for life sciences companies.	https://www.healthcareittoday.com/2025/10/03/business-development-with-bdaas-life-sciences-today-podcast-episode-29/	podcast	2025-10-03 00:00:00	2025-12-08 16:35:35.373609	2025-12-08 16:38:15.625567	\N
22	Make captive customers your moat	The power of Switching Costs	https://newsletter.dannylieberman.com/p/switching-costs	substack	2025-10-31 00:00:00	2025-12-08 16:45:00.066986	2025-12-08 16:46:58.565344	\N
25	Dissent is an act of faith	Like medicine, the value of dissent is not in the taste.	https://newsletter.dannylieberman.com/p/dissent-is-an-act-of-faith	substack	2025-09-26 00:00:00	2025-12-09 16:50:22.136134	2025-12-09 16:50:22.136134	\N
26	Real world people	What would you do if you could find the right patients instantly?	https://newsletter.dannylieberman.com/p/real-world-people	substack	2025-09-19 00:00:00	2025-12-09 17:20:04.395605	2025-12-09 17:20:04.395605	\N
27	Israel is the best place in the world to innovate	The road not taken	https://newsletter.dannylieberman.com/p/israel-is-the-best-place-in-the-world	substack	2025-09-05 00:00:00	2025-12-09 18:14:16.595295	2025-12-09 18:14:16.595295	\N
28	MedTech Security Anti-Patterns	Pattern Factory Test Data | Medical Device Cybersecurity	https://pattern-cards.netlify.app/	substack	2026-01-06 00:00:00	2026-01-07 12:25:26.204056	2026-01-07 12:31:56.559381	\N
30	What happened yesterday is easy	Can we prevent bad things from happening tomorrow?	https://newsletter.dannylieberman.com/p/what-happened-yesterday-is-easy	substack	2026-01-02 16:05:12	2026-01-07 12:32:38.906094	2026-01-07 12:32:38.906094	\N
31	Why Deals Die	Most life science revenue problems aren’t sales problems.	https://newsletter.dannylieberman.com/p/paying-customers-is-proof-6e1	substack	2025-12-26 00:00:00	2026-01-07 12:33:09.928835	2026-01-07 12:33:09.928835	\N
32	Paying customers is proof	It’s the only proof you created wealth	https://newsletter.dannylieberman.com/p/paying-customers-is-proof	substack	2025-12-26 16:05:25	2026-01-07 12:33:34.105393	2026-01-07 12:33:34.105393	\N
33	Customers don’t want to hear your vision	They want to believe your logic	https://newsletter.dannylieberman.com/p/customers-dont-want-to-hear-your	substack	2025-12-19 00:00:00	2026-01-07 12:46:31.747775	2026-01-07 12:51:12.590419	\N
35	From Hero to Zero	Recoil	https://newsletter.dannylieberman.com/p/from-hero-to-zero	substack	2024-03-20 20:37:47	2026-01-07 14:19:29.342309	2026-01-07 14:19:29.342309	\N
1	Founder–Market Misfit	How do you build a TechBio company with an unbeatable competitive advantage?	https://newsletter.dannylieberman.com/p/foundermarket-misfit	substack	2025-10-17 00:00:00	2025-12-05 09:37:27.855305	2026-01-07 14:24:14.003969	\N
37	What threats really count 	It's not about cyber tech stupid. It's about your business leadership man.	https://newsletter.dannylieberman.com/p/what-threats-really-count	substack	2023-10-31 18:45:53	2026-06-29 09:54:19.95046	2026-06-29 09:54:19.95046	\N
\.


--
-- Data for Name: rbac; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.rbac (user_id, role_id, permission) FROM stdin;
4da53331-d976-4512-a215-ed756612a8e0	1	RWDE
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.roles (id, name) FROM stdin;
1	admin
2	user
\.


--
-- Data for Name: system_log; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.system_log (id, event, context, created_at) FROM stdin;
\.


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.user_role (user_id, role_id) FROM stdin;
4da53331-d976-4512-a215-ed756612a8e0	1
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.users (id, role_id, email, password_hash, created_at, updated_at) FROM stdin;
4da53331-d976-4512-a215-ed756612a8e0	1	admin@opencro.com	password	2026-01-15 18:03:09.954843	2026-01-15 18:03:09.954843
\.


--
-- Data for Name: views_registry; Type: TABLE DATA; Schema: public; Owner: pattern_factory
--

COPY public.views_registry (id, name, table_name, sql, created_at, updated_at, mode) FROM stdin;
32	Security countermeasures	THRCM	SELECT threat_tag, threat_name, probability, countermeasure_tag, countermeasure_name, mitigation_level, implemented, disabled FROM threat.threat_countermeasures;	2026-02-04 02:44:28.151793	2026-07-06 20:06:41.686788	model
25	Cards in Baseline	WCRT	SELECT t.name, t.probability\nFROM threat.threats t\nJOIN threat.models m ON t.model_id = m.id\nWHERE m.name = 'Baseline';	2026-01-12 17:59:54.43844	2026-01-19 15:00:08.138656	model
10	Founding to funding	TIME_TO_FUNDING	SELECT \n    o.name, \n    o.stage, \n    EXTRACT(YEAR FROM AGE(o.date_funded, o.date_founded)) AS years_from_founding_to_funding\nFROM \n    orgs o;	2025-12-09 18:14:53.387708	2025-12-09 18:14:53.387708	explore
2	Organizations	LIST_ORGS	SELECT \n    o.name, \n    o.description, \n    o.date_founded, \n    o.date_funded, \n    o.stage AS funding_stage\nFROM \n    orgs AS o;	2025-12-05 10:23:36.922438	2025-12-05 10:23:36.922438	explore
7	Patterns/guests	pattern_guests	select * from pattern_guests	2025-12-08 17:56:36.645221	2025-12-08 17:56:36.645221	explore
8	Patterns/orgs	pattern_orgs	select * from pattern_orgs	2025-12-08 17:56:36.648442	2025-12-08 17:56:36.648442	explore
80	Threats and Vulnerabilities	THREAT-VULN	SELECT \n    t.tag AS threat_tag, \n    t.name AS threat_name, \n    v.name AS vulnerability_name\nFROM \n    threat.threats t\nJOIN \n    threat.vulnerability_threat vt ON t.id = vt.threat_id AND t.model_id = vt.model_id\nJOIN \n    threat.vulnerabilities v ON vt.vulnerability_id = v.id AND vt.model_id = v.model_id\nWHERE \n    t.model_id = (SELECT model_id FROM public.active_models LIMIT 1)	2026-07-24 10:57:47.196107	2026-07-24 15:10:18.690748	model
44	Vulnerability exploitability after mitigation	VULNEXPLOIT	SELECT vulnerability_name, exploitability\nFROM threat.vulnerability_exploitability	2026-02-15 18:00:06.284191	2026-02-17 20:00:32.875016	model
83	Threats and Countermeasures	THREAT-CM	SELECT \n    t.tag AS threat_tag, \n    t.name AS threat_name, \n    ct.mitigation_level, \n    c.name AS countermeasure_name, \n    c.yearly_cost AS countermeasure_yearly_cost\nFROM \n    threat.threats t\nJOIN \n    threat.countermeasure_threat ct ON t.id = ct.threat_id\nJOIN \n    threat.countermeasures c ON ct.countermeasure_id = c.id\nWHERE \n    t.model_id = (SELECT model_id FROM public.active_models LIMIT 1)\nORDER BY \n    t.name, c.name;	2026-07-24 11:12:44.789555	2026-07-24 15:11:49.072933	model
93	Assets and Exploits	ASSET-EXPLOITS	SELECT \n    a.tag AS asset_tag, \n    a.name AS asset_name, \n    a.yearly_value AS asset_value,\n    t.tag AS threat_tag, \n    t.name AS threat_name, \n    at.damage AS threat_damage_to_asset,\n    v.id AS vulnerability_tag, \n    v.name AS vulnerability_name,\n    c.name AS countermeasure_name, \n    c.yearly_cost AS countermeasure_yearly_cost,\n    ct.mitigation_level\nFROM \n    threat.assets a\nJOIN \n    threat.asset_threat at ON a.id = at.asset_id AND a.model_id = at.model_id\nJOIN \n    threat.threats t ON at.threat_id = t.id AND at.model_id = t.model_id\nLEFT JOIN \n    threat.vulnerability_threat vt ON t.id = vt.threat_id AND t.model_id = vt.model_id\nLEFT JOIN \n    threat.vulnerabilities v ON vt.vulnerability_id = v.id AND vt.model_id = v.model_id\nLEFT JOIN \n    threat.countermeasure_threat ct ON t.id = ct.threat_id AND t.model_id = ct.model_id\nLEFT JOIN \n    threat.countermeasures c ON ct.countermeasure_id = c.id AND ct.model_id = c.model_id\nWHERE \n    a.model_id = (SELECT model_id FROM public.active_models LIMIT 1)\nORDER BY \n    asset_name, vulnerability_name;	2026-07-24 16:57:15.686601	2026-07-24 16:57:15.686601	model
36	List assets	ALIST	SELECT a.tag, a.name, a.yearly_value\nFROM threat.assets AS a\nWHERE a.model_id = (SELECT model_id FROM public.active_models LIMIT 1)	2026-02-04 10:09:54.404823	2026-07-24 17:33:04.04905	model
15	Posts	POSTS	SELECT p.name, p.description, p.content_url, p.content_source, p.published_at\nFROM public.posts AS p;	2026-01-07 12:43:42.433055	2026-01-07 12:43:42.433055	explore
31	Residual Risk	THRIM	SELECT threat_tag, \n       threat_name, \n       probability, \n       mitigation_level, \n       yearly_cost AS "Cost of mitigation", \n       var_before_mitigation, \n       var_after_mitigation,\n       residual_risk_level AS "Residual Risk"\nFROM threat.threat_impact\nORDER BY residual_risk_pct DESC	2026-02-04 02:43:19.703675	2026-07-24 11:45:47.615601	model
52	Threat likelihood before mitigation	TLIKE	SELECT \n    t.tag, \n    t.name, \n    CASE \n        WHEN t.probability > 50 THEN 'High'\n        WHEN t.probability > 20 THEN 'Medium'\n        WHEN t.probability > 10 THEN 'Low'\n        ELSE 'Very low'\n    END AS likelihood\nFROM \n    threat.threats AS t\nWHERE \n    t.model_id = (SELECT model_id FROM public.active_models LIMIT 1)\nORDER BY \n    t.probability DESC;	2026-02-17 18:48:34.430948	2026-02-17 21:01:54.42174	model
3	All patterns all posts	PIP	SELECT p.id, p.name, p.description, p.content_url, p.content_source, p.published_at, p.created_at, p.updated_at, p.deleted_at\nFROM public.posts AS p\nJOIN public.pattern_post_link AS ppl ON ppl.post_id = p.id\nJOIN public.patterns AS pat ON pat.id = ppl.pattern_id;	2025-12-05 10:45:34.811685	2026-06-21 12:08:25.35002	explore
\.


--
-- Data for Name: area_asset; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.area_asset (model_id, area_id, asset_id) FROM stdin;
\.


--
-- Data for Name: area_countermeasure; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.area_countermeasure (model_id, area_id, countermeasure_id) FROM stdin;
\.


--
-- Data for Name: area_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.area_threat (model_id, area_id, threat_id) FROM stdin;
\.


--
-- Data for Name: area_vulnerability; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.area_vulnerability (model_id, area_id, vulnerability_id) FROM stdin;
\.


--
-- Data for Name: areas; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.areas (id, model_id, name, description, use_for_threats, use_for_vulnerabilities, use_for_countermeasures, use_for_assets) FROM stdin;
\.


--
-- Data for Name: asset_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.asset_threat (model_id, asset_id, threat_id, damage) FROM stdin;
6	6	34	30
6	6	35	100
6	6	36	30
6	6	37	80
6	6	38	100
6	6	39	60
6	6	40	80
6	7	35	100
6	8	37	80
6	8	38	100
6	8	40	80
6	10	34	30
6	10	35	100
6	10	36	30
6	10	37	80
6	10	38	100
6	10	39	60
6	10	40	80
6	65	48	80
27	69	73	90
27	70	73	90
27	70	74	100
27	71	74	100
27	72	73	90
29	73	75	90
29	74	75	90
29	74	76	100
29	77	76	100
29	78	76	100
29	82	75	90
30	85	77	90
30	85	78	100
30	85	79	95
30	85	83	95
30	86	77	90
30	86	78	100
30	86	83	95
30	87	81	85
30	87	82	70
30	87	83	95
30	88	82	70
30	89	79	95
30	91	80	80
30	92	79	95
30	92	80	80
30	93	81	85
30	93	82	70
30	94	77	90
30	94	78	100
30	94	79	95
30	94	80	80
30	94	81	85
30	94	82	70
30	95	78	100
30	95	80	80
30	96	83	95
26	129	146	90
26	130	146	90
26	130	147	100
26	133	147	100
26	134	147	100
26	138	146	90
32	227	224	15
32	227	225	35
32	227	226	35
32	227	227	5
32	227	230	95
32	227	232	100
32	227	234	95
32	227	238	100
32	227	239	90
25	59	65	90
32	227	240	95
32	227	250	35
25	63	66	100
32	228	224	15
32	228	225	35
25	60	65	30
25	60	66	100
25	60	67	30
25	60	68	80
25	60	69	100
25	60	70	60
25	60	71	80
25	61	66	100
25	62	68	80
25	62	69	100
25	62	71	80
25	64	65	30
25	64	66	100
25	64	67	30
25	64	68	80
25	64	69	100
25	64	70	60
25	64	71	80
25	66	72	80
31	185	164	90
31	186	164	90
31	186	165	100
31	189	165	100
31	190	165	100
31	194	164	90
32	228	226	35
32	228	229	65
32	228	230	95
32	228	232	100
32	228	234	95
32	228	238	100
32	228	239	90
32	228	240	95
32	228	250	35
32	229	230	95
32	229	233	90
32	229	239	90
32	229	241	90
32	229	242	90
32	229	243	85
32	231	232	100
32	231	234	95
32	231	238	100
32	231	244	95
32	231	245	100
33	242	253	100
33	242	254	85
33	242	255	100
33	242	256	100
33	242	257	95
33	242	259	70
33	242	260	95
33	242	262	90
33	242	263	95
33	242	266	85
33	242	267	80
33	242	268	90
33	242	269	90
33	243	256	100
33	243	260	95
33	243	263	95
33	243	266	85
33	243	268	90
33	244	253	100
33	244	254	85
33	244	255	100
33	244	256	100
33	244	257	95
33	244	260	95
33	244	262	90
33	244	263	95
33	244	266	85
33	244	269	90
33	245	253	100
33	245	256	100
33	245	260	95
33	245	261	80
33	245	263	95
33	245	266	85
33	245	267	80
33	245	268	90
33	245	270	85
33	246	253	100
33	246	260	95
33	246	263	95
33	246	265	70
33	246	270	85
33	247	254	85
33	247	256	100
33	247	262	90
33	247	268	90
33	248	255	100
33	248	257	95
33	248	258	75
33	248	259	70
33	248	260	95
33	248	262	90
33	248	264	85
33	248	265	70
33	248	267	80
33	248	268	90
33	248	269	90
33	248	270	85
33	249	254	85
33	249	255	100
33	249	257	95
33	249	258	75
33	249	259	70
33	249	262	90
33	249	264	85
33	249	265	70
33	249	267	80
33	249	269	90
33	249	270	85
33	250	254	85
33	250	258	75
33	250	259	70
33	250	260	95
33	250	261	80
33	250	264	85
33	250	267	80
33	250	268	90
33	250	270	85
33	251	257	95
33	251	258	75
33	251	264	85
33	251	265	70
33	251	270	85
33	252	261	80
33	252	266	85
33	253	253	100
33	253	255	100
33	253	256	100
33	253	258	75
33	253	261	80
33	253	264	85
33	253	265	70
33	253	268	90
33	253	269	90
33	253	270	85
32	231	250	35
32	232	224	15
32	232	226	35
32	232	234	95
32	232	238	100
32	232	239	90
32	232	240	95
32	232	250	35
32	233	231	85
32	233	235	75
32	233	241	90
32	233	246	35
32	233	247	85
32	233	248	10
32	233	249	75
32	233	252	35
32	234	231	85
32	234	246	35
32	234	247	85
32	235	232	100
32	235	233	90
32	235	236	90
32	235	237	85
32	235	238	100
32	235	241	90
32	235	242	90
32	235	243	85
32	235	244	95
32	235	245	100
32	235	252	35
32	236	224	15
32	236	225	35
32	236	227	5
32	236	228	70
32	236	229	65
32	236	233	90
32	236	235	75
32	236	236	90
32	236	237	85
32	236	242	90
32	236	252	35
32	237	225	35
32	237	227	5
32	237	228	70
32	237	230	95
32	237	231	85
32	237	235	75
32	237	246	35
32	237	247	85
32	237	248	10
32	237	252	35
32	238	236	90
32	238	237	85
32	238	244	95
32	238	245	100
32	238	249	75
32	238	252	35
32	239	251	35
32	240	251	35
32	241	251	35
34	269	300	15
34	269	301	35
34	269	302	35
34	269	303	5
34	269	306	95
34	269	308	100
34	269	310	95
34	269	314	100
34	269	315	90
34	269	316	95
34	269	326	35
34	270	300	15
34	270	301	35
34	270	302	35
34	270	305	65
34	270	306	95
34	270	308	100
34	270	310	95
34	270	314	100
34	270	315	90
34	270	316	95
34	270	326	35
34	271	306	95
34	271	309	90
34	271	315	90
34	271	317	90
34	271	318	90
34	273	308	100
34	273	310	95
34	273	314	100
34	273	320	95
34	273	321	100
34	273	326	35
34	274	300	15
34	274	302	35
34	274	310	95
34	274	314	100
34	274	315	90
34	274	316	95
34	274	326	35
34	275	311	75
34	275	317	90
34	275	322	35
34	275	324	10
34	275	325	75
34	275	328	35
34	276	322	35
34	277	308	100
34	277	309	90
34	277	312	90
34	277	314	100
34	277	317	90
34	277	318	90
34	277	320	95
34	277	321	100
34	277	328	35
34	278	300	15
34	278	301	35
34	278	303	5
34	278	304	70
34	278	305	65
34	278	309	90
34	278	311	75
34	278	312	90
34	278	318	90
34	278	328	35
34	279	301	35
34	279	303	5
34	279	304	70
34	279	306	95
34	279	311	75
34	279	322	35
34	279	324	10
34	279	328	35
34	280	312	90
34	280	320	95
34	280	321	100
34	280	325	75
34	280	328	35
34	281	327	35
34	282	327	35
34	283	327	35
34	271	319	95
34	275	307	95
34	275	323	95
34	276	307	95
34	276	323	95
34	277	313	95
34	277	319	95
34	278	313	95
34	279	307	95
34	279	323	95
34	280	313	95
\.


--
-- Data for Name: assets; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.assets (id, model_id, name, description, fixed_value, fixed_value_period, recurring_value, include_fixed_value, include_recurring_value, disabled, created_at, updated_at, tag, version, yearly_value, card_id) FROM stdin;
1	1	Test Asset	\N	100.00	12	50.00	t	t	f	2026-01-18 12:13:57.416083+02	2026-06-25 10:16:47.114933+03	A1	5	150	550e8400-e29b-41d4-a716-446655440000
3	1	Another Asset	\N	75.00	12	25.00	t	t	f	2026-01-18 12:13:57.416083+02	2026-06-25 10:16:47.114933+03	A2	4	100	550e8400-e29b-41d4-a716-446655440000
2	1	Remote Control & Automation System	Software and control logic enabling remote execution and monitoring.	500000.00	12	0.00	t	t	f	2026-01-18 12:13:57.416083+02	2026-02-02 12:52:44.459694+02	A3	4	500000	\N
5	6	Customer satisfaction	Customer satisfaction is key to building trust and successful commercialization	0.00	12	1000000.00	t	t	f	2026-02-03 11:33:22.517744+02	2026-02-03 11:41:59.339195+02	A1	2	1000000	\N
10	6	System	Radiaction system operating efficacy and safety	0.00	12	200000.00	t	t	f	2026-02-03 12:04:42.472487+02	2026-02-03 12:05:07.407433+02	A6	1	200000	\N
6	6	Patient safety	Malfunction of the device may impact patient safety	0.00	12	3000000.00	t	t	f	2026-02-03 11:56:24.476434+02	2026-02-03 14:47:39.0092+02	A2	2	3000000	\N
7	6	Supply chain	Integrity of the vendor supply chain	0.00	12	500000.00	t	t	f	2026-02-03 12:02:32.112073+02	2026-02-03 14:48:05.166937+02	A3	2	500000	\N
8	6	Reputation	Brand trust, regulatory credibility, long-term market position	0.00	12	1000000.00	t	t	f	2026-02-03 12:03:03.751489+02	2026-02-03 14:48:19.838889+02	A4	2	1000000	\N
9	6	Components	System components	0.00	12	25000.00	t	t	f	2026-02-03 12:03:22.329761+02	2026-02-03 14:48:35.666009+02	A5	2	25000	\N
11	8	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:42:28.784093+02	2026-02-03 21:42:28.784093+02	A1	1	0	\N
12	8	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:42:28.790567+02	2026-02-03 21:42:28.790567+02	A2	1	0	\N
13	8	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:42:28.790841+02	2026-02-03 21:42:28.790841+02	A3	1	0	\N
14	9	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:45:15.507771+02	2026-02-03 21:45:15.507771+02	A1	1	0	\N
15	9	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:45:15.511853+02	2026-02-03 21:45:15.511853+02	A2	1	0	\N
16	9	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:45:15.51224+02	2026-02-03 21:45:15.51224+02	A3	1	0	\N
17	10	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:46:05.720922+02	2026-02-03 21:46:05.720922+02	A1	1	0	\N
18	10	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:46:05.72678+02	2026-02-03 21:46:05.72678+02	A2	1	0	\N
19	10	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:46:05.727105+02	2026-02-03 21:46:05.727105+02	A3	1	0	\N
20	11	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.0941+02	2026-02-03 21:49:06.0941+02	A1	1	0	\N
21	11	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.099895+02	2026-02-03 21:49:06.099895+02	A2	1	0	\N
22	11	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.100658+02	2026-02-03 21:49:06.100658+02	A3	1	0	\N
23	12	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.133883+02	2026-02-03 21:49:06.133883+02	A1	1	0	\N
24	12	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.137513+02	2026-02-03 21:49:06.137513+02	A2	1	0	\N
25	12	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.13782+02	2026-02-03 21:49:06.13782+02	A3	1	0	\N
26	13	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.154276+02	2026-02-03 21:49:06.154276+02	A1	1	0	\N
27	13	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.157446+02	2026-02-03 21:49:06.157446+02	A2	1	0	\N
28	13	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:06.157692+02	2026-02-03 21:49:06.157692+02	A3	1	0	\N
29	14	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.238258+02	2026-02-03 21:49:31.238258+02	A1	1	0	\N
30	14	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.242489+02	2026-02-03 21:49:31.242489+02	A2	1	0	\N
31	14	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.242879+02	2026-02-03 21:49:31.242879+02	A3	1	0	\N
32	15	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.2686+02	2026-02-03 21:49:31.2686+02	A1	1	0	\N
33	15	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.271909+02	2026-02-03 21:49:31.271909+02	A2	1	0	\N
34	15	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.272157+02	2026-02-03 21:49:31.272157+02	A3	1	0	\N
35	16	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.282731+02	2026-02-03 21:49:31.282731+02	A1	1	0	\N
36	16	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.284007+02	2026-02-03 21:49:31.284007+02	A2	1	0	\N
37	16	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.284216+02	2026-02-03 21:49:31.284216+02	A3	1	0	\N
38	17	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.292402+02	2026-02-03 21:49:31.292402+02	A1	1	0	\N
39	17	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.293516+02	2026-02-03 21:49:31.293516+02	A2	1	0	\N
40	17	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 21:49:31.293706+02	2026-02-03 21:49:31.293706+02	A3	1	0	\N
41	18	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:18:35.597535+02	2026-02-03 22:18:35.597535+02	A1	1	0	\N
42	18	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:18:35.603117+02	2026-02-03 22:18:35.603117+02	A2	1	0	\N
43	18	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:18:35.603488+02	2026-02-03 22:18:35.603488+02	A3	1	0	\N
44	19	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:19:21.567722+02	2026-02-03 22:19:21.567722+02	A1	1	0	\N
45	19	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:19:21.572532+02	2026-02-03 22:19:21.572532+02	A2	1	0	\N
46	19	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:19:21.572915+02	2026-02-03 22:19:21.572915+02	A3	1	0	\N
47	20	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:19:43.262795+02	2026-02-03 22:19:43.262795+02	A1	1	0	\N
48	20	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:19:43.267368+02	2026-02-03 22:19:43.267368+02	A2	1	0	\N
49	20	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:19:43.267831+02	2026-02-03 22:19:43.267831+02	A3	1	0	\N
50	21	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:19:59.910089+02	2026-02-03 22:19:59.910089+02	A1	1	0	\N
51	21	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:19:59.914253+02	2026-02-03 22:19:59.914253+02	A2	1	0	\N
52	21	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:19:59.91454+02	2026-02-03 22:19:59.91454+02	A3	1	0	\N
53	22	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:20:42.655921+02	2026-02-03 22:20:42.655921+02	A1	1	0	\N
54	22	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:20:42.663379+02	2026-02-03 22:20:42.663379+02	A2	1	0	\N
55	22	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:20:42.66412+02	2026-02-03 22:20:42.66412+02	A3	1	0	\N
56	23	Asset 1	Test asset 1	0.00	12	0.00	t	t	f	2026-02-03 22:21:08.139383+02	2026-02-03 22:21:08.139383+02	A1	1	0	\N
57	23	Asset 2	Test asset 2	0.00	12	0.00	t	t	f	2026-02-03 22:21:08.144349+02	2026-02-03 22:21:08.144349+02	A2	1	0	\N
58	23	Asset 3	Test asset 3	0.00	12	0.00	t	t	f	2026-02-03 22:21:08.144743+02	2026-02-03 22:21:08.144743+02	A3	1	0	\N
60	25	Patient safety	\N	0.00	12	3000000.00	t	t	f	2026-02-15 11:59:33.171995+02	2026-06-29 08:23:40.678248+03	A2	5	3000000	c89552dc-420a-4459-9004-216cf107f7ac
59	25	Customer satisfaction	\N	0.00	12	1000000.00	t	t	f	2026-02-15 11:57:33.309192+02	2026-06-29 08:23:40.678248+03	A1	6	1000000	c89552dc-420a-4459-9004-216cf107f7ac
61	25	Supply chain	\N	500000.00	12	0.00	t	t	f	2026-02-15 12:00:13.660476+02	2026-06-29 08:23:40.678248+03	A3	5	500000	c89552dc-420a-4459-9004-216cf107f7ac
62	25	Reputation	\N	1000000.00	12	0.00	t	t	f	2026-02-15 12:00:51.883535+02	2026-06-29 08:23:40.678248+03	A4	5	1000000	c89552dc-420a-4459-9004-216cf107f7ac
63	25	Components	\N	25000.00	12	0.00	t	t	f	2026-02-15 12:01:44.971169+02	2026-06-29 08:23:40.678248+03	A5	5	25000	c89552dc-420a-4459-9004-216cf107f7ac
65	6	Software development and runtime	CODESys development and runtime environments	0.00	12	100000.00	t	t	f	2026-02-15 12:20:46.250849+02	2026-02-15 12:21:10.697466+02	A7	1	100000	\N
64	25	System	\N	0.00	12	200000.00	t	t	f	2026-02-15 12:02:28.964265+02	2026-06-29 08:23:40.678248+03	A6	5	200000	c89552dc-420a-4459-9004-216cf107f7ac
66	25	Software development and runtime	\N	100000.00	12	0.00	t	t	f	2026-02-15 12:21:34.15812+02	2026-06-29 08:23:40.678248+03	A7	6	100000	c89552dc-420a-4459-9004-216cf107f7ac
69	27	Patient Safety	\N	100.00	12	100.00	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	A1	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
70	27	Clinical Decision Accuracy	\N	100.00	12	100.00	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	A2	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
71	27	Patient Confidentiality	\N	100.00	12	100.00	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	A3	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
72	27	Reputation	\N	100.00	12	100.00	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	A10	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
73	29	Patient Safety	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A1	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
74	29	Clinical Decision Accuracy	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A2	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
75	29	Patient Confidentiality	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A3	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
76	29	Patient Consent Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A4	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
77	29	AI Model Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A5	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
78	29	Imaging Data Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A6	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
79	29	Platform Availability	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A7	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
80	29	Cloud Infrastructure Security	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A8	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
81	29	Regulatory Compliance	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A9	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
82	29	Reputation	\N	100.00	12	100.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A10	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
83	29	Clinical Workflow Continuity	\N	0.00	12	0.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A11	1	0	fbe56779-c539-4b9d-9593-1a8e27bec752
84	29	Auditability	\N	10.00	12	10.00	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	A12	1	20	fbe56779-c539-4b9d-9593-1a8e27bec752
85	30	Patient Safety	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A1	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
86	30	Clinical Decision Accuracy	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A2	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
87	30	Patient Confidentiality	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A3	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
88	30	Patient Consent Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A4	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
89	30	AI Model Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A5	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
90	30	Imaging Data Integrity	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A6	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
91	30	Platform Availability	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A7	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
92	30	Cloud Infrastructure Security	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A8	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
93	30	Regulatory Compliance	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A9	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
94	30	Reputation	\N	100.00	12	100.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A10	1	200	698fb6b6-c1e3-4340-b599-cfb058347bc3
95	30	Clinical Workflow Continuity	\N	0.00	12	0.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A11	1	0	698fb6b6-c1e3-4340-b599-cfb058347bc3
96	30	Auditability	\N	10.00	12	10.00	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	A12	1	20	698fb6b6-c1e3-4340-b599-cfb058347bc3
129	26	Patient Safety	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A1	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
130	26	Clinical Decision Accuracy	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A2	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
131	26	Patient Confidentiality	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A3	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
132	26	Patient Consent Integrity	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A4	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
133	26	AI Model Integrity	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A5	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
134	26	Imaging Data Integrity	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A6	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
135	26	Platform Availability	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A7	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
136	26	Cloud Infrastructure Security	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A8	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
137	26	Regulatory Compliance	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A9	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
138	26	Reputation	\N	100.00	12	100.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A10	1	200	fbe56779-c539-4b9d-9593-1a8e27bec752
139	26	Clinical Workflow Continuity	\N	0.00	12	0.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A11	1	0	fbe56779-c539-4b9d-9593-1a8e27bec752
140	26	Auditability	\N	10.00	12	10.00	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	A12	1	20	fbe56779-c539-4b9d-9593-1a8e27bec752
185	31	Patient Safety	\N	0.00	12	5000000.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:22:55.448434+03	A1	2	5000000	fbe56779-c539-4b9d-9593-1a8e27bec752
186	31	Clinical Decision Accuracy	\N	10000000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:23:19.033268+03	A2	2	10000000	fbe56779-c539-4b9d-9593-1a8e27bec752
187	31	Patient Confidentiality	\N	0.00	12	2500000.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:23:54.181424+03	A3	2	2500000	fbe56779-c539-4b9d-9593-1a8e27bec752
188	31	Patient Consent Integrity	\N	0.00	12	500000.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:24:20.940741+03	A4	2	500000	fbe56779-c539-4b9d-9593-1a8e27bec752
189	31	AI Model Integrity	\N	3000000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:24:38.867768+03	A5	2	3000000	fbe56779-c539-4b9d-9593-1a8e27bec752
190	31	Imaging Data Integrity	\N	1000000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:24:58.234089+03	A6	2	1000000	fbe56779-c539-4b9d-9593-1a8e27bec752
191	31	Platform Availability	\N	0.00	12	500000.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:25:17.687901+03	A7	2	500000	fbe56779-c539-4b9d-9593-1a8e27bec752
192	31	Cloud Infrastructure Security	\N	50000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:25:41.399728+03	A8	2	50000	fbe56779-c539-4b9d-9593-1a8e27bec752
193	31	Regulatory Compliance	\N	100000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:25:57.153207+03	A9	2	100000	fbe56779-c539-4b9d-9593-1a8e27bec752
194	31	Reputation	\N	8000000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:26:18.976515+03	A10	2	8000000	fbe56779-c539-4b9d-9593-1a8e27bec752
195	31	Clinical Workflow Continuity	\N	0.00	12	50000.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:26:34.215244+03	A11	2	50000	fbe56779-c539-4b9d-9593-1a8e27bec752
196	31	Auditability	\N	25000.00	12	0.00	t	t	f	2026-06-29 08:32:25.672864+03	2026-07-09 16:26:53.312538+03	A12	2	25000	fbe56779-c539-4b9d-9593-1a8e27bec752
280	34	Auditability	\N	3333334.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A12	1	3333334	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
281	34	Upstream Device Management Pipeline, BioT (Cloud)	The infrastructure used to push firmware, security patches, and algorithm updates to Neteera edge devices.	0.00	12	4000000.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 17:06:37.444525+03	A13	2	4000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
282	34	Device Authorization Registry, BioT (Cloud)	The database hosting unique cryptographic keys and tokens that authenticate physical Neteera devices to the cloud.	3000000.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 17:07:05.194037+03	A14	2	3000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
283	34	Live Telemetry Ingestion Endpoint, BioT (Cloud)	The cloud gateway (MQTT broker) receiving real-time patient vital signs and bed-exit metrics.	0.00	12	3000000.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 17:07:20.783374+03	A15	2	3000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
269	34	Patient Safety	\N	16000000.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A1	1	16000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
270	34	Clinical Decision Accuracy	\N	13333333.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A2	1	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
279	34	Clinical Workflow Continuity	\N	0.00	12	4000000.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 17:00:44.926044+03	A11	2	4000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
242	33	Clinical Safety and Treatment Integrity	\N	90000000.00	12	0.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A1	1	90000000	124cd230-f665-4926-b037-8388d842fafb
243	33	V-LAP Implant and Sensor Intellectual Property	\N	80000000.00	12	0.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A2	1	80000000	124cd230-f665-4926-b037-8388d842fafb
244	33	Measurement Accuracy and Calibration	\N	65000000.00	12	0.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A3	1	65000000	124cd230-f665-4926-b037-8388d842fafb
245	33	Regulatory Pathway and Clinical Evidence	\N	65000000.00	12	0.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A4	1	65000000	124cd230-f665-4926-b037-8388d842fafb
246	33	Longitudinal LAP Dataset and Algorithms	\N	35000000.00	12	10000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A5	1	45000000	124cd230-f665-4926-b037-8388d842fafb
247	33	Wireless Power and Communication Integrity	\N	35000000.00	12	0.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A6	1	35000000	124cd230-f665-4926-b037-8388d842fafb
248	33	Patient Self-Management Platform	\N	10000000.00	12	20000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A7	1	30000000	124cd230-f665-4926-b037-8388d842fafb
249	33	Physician Monitoring and Clinical Workflow	\N	5000000.00	12	20000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A8	1	25000000	124cd230-f665-4926-b037-8388d842fafb
250	33	Cloud and Software Platform Availability	\N	0.00	12	20000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A9	1	20000000	124cd230-f665-4926-b037-8388d842fafb
251	33	Patient Data Confidentiality	\N	5000000.00	12	10000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A10	1	15000000	124cd230-f665-4926-b037-8388d842fafb
252	33	Manufacturing and Supply-Chain Quality	\N	7000000.00	12	8000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A11	1	15000000	124cd230-f665-4926-b037-8388d842fafb
253	33	Reputation and Strategic Value	\N	0.00	12	12000000.00	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	A12	1	12000000	124cd230-f665-4926-b037-8388d842fafb
227	32	Patient Safety	\N	16000000.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A1	4	16000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
228	32	Clinical Decision Accuracy	\N	13333333.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A2	2	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
229	32	Patient Confidentiality	\N	3333333.00	12	6666667.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A3	2	10000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
230	32	Patient Consent Integrity	\N	13333333.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A4	2	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
231	32	AI Model Integrity	\N	30000000.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A5	2	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
232	32	Physiological Signal Integrity	\N	30000000.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A6	2	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
233	32	Platform Availability	\N	0.00	12	6666667.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A7	2	6666667	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
234	32	Cloud Infrastructure	\N	0.00	12	6666667.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A8	2	6666667	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
235	32	Regulatory Compliance	\N	30000000.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A9	2	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
236	32	Reputation	\N	6666667.00	12	6666666.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A10	2	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
237	32	Clinical Workflow Continuity	\N	0.00	12	6666667.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A11	2	6666667	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
238	32	Auditability	\N	3333334.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A12	2	3333334	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
239	32	Upstream Device Management Pipeline, BioT (Cloud)	The infrastructure used to push firmware, security patches, and algorithm updates to Neteera edge devices.	0.00	12	6666667.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A13	2	6666667	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
240	32	Device Authorization Registry, BioT (Cloud)	The database hosting unique cryptographic keys and tokens that authenticate physical Neteera devices to the cloud.	3333333.00	12	0.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A14	2	3333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
241	32	Live Telemetry Ingestion Endpoint, BioT (Cloud)	The cloud gateway (MQTT broker) receiving real-time patient vital signs and bed-exit metrics.	0.00	12	6666666.00	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	A15	2	6666666	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
271	34	Patient Confidentiality	\N	3333333.00	12	6666667.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A3	1	10000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
272	34	Patient Consent Integrity	\N	13333333.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A4	1	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
273	34	AI Model Integrity	\N	30000000.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A5	1	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
274	34	Physiological Signal Integrity	\N	30000000.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A6	1	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
275	34	Platform Availability	\N	0.00	12	6666667.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A7	1	6666667	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
277	34	Regulatory Compliance	\N	30000000.00	12	0.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A9	1	30000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
278	34	Reputation	\N	6666667.00	12	6666666.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	A10	1	13333333	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
276	34	Cloud Infrastructure	\N	0.00	12	8000000.00	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 17:06:04.759549+03	A8	2	8000000	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160
\.


--
-- Data for Name: attacker_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.attacker_threat (model_id, attacker_type_id, threat_id) FROM stdin;
\.


--
-- Data for Name: attacker_types; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.attacker_types (id, name, description, tools_available) FROM stdin;
\.


--
-- Data for Name: countermeasure_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.countermeasure_threat (model_id, countermeasure_id, threat_id, mitigation_level, included_in_mitigation) FROM stdin;
6	94	39	90	t
6	99	40	90	t
6	81	34	80	t
6	82	35	90	t
6	82	48	90	t
6	83	35	95	t
6	83	48	95	t
6	84	35	90	t
6	84	48	90	t
6	85	36	90	t
6	86	36	95	t
6	87	37	90	t
6	88	37	90	t
6	89	37	90	t
6	90	37	90	t
6	91	37	90	t
6	92	38	90	t
6	93	38	90	t
6	93	39	90	t
6	95	38	90	t
6	95	39	90	t
6	95	40	90	t
6	96	39	90	t
6	97	39	90	t
6	98	40	90	t
6	100	40	90	t
6	101	34	80	t
6	105	36	90	t
6	106	36	95	t
6	111	37	90	t
6	112	38	90	t
6	113	38	90	t
6	113	39	90	t
6	114	38	90	t
6	114	39	90	t
6	114	40	90	t
6	119	48	90	t
6	120	48	90	t
25	181	71	95	t
27	182	73	85	t
27	183	73	95	t
27	184	74	80	t
29	185	75	85	t
29	186	75	95	t
29	187	75	75	t
29	188	76	80	t
29	189	76	70	t
30	190	77	85	t
30	191	77	95	t
30	192	77	75	t
30	193	78	90	t
30	194	78	95	t
30	195	78	70	t
30	196	79	95	t
30	197	79	95	t
30	198	79	80	t
30	199	80	95	t
30	200	80	85	t
30	201	80	75	t
30	202	81	90	t
30	203	81	85	t
30	204	81	75	t
30	205	82	90	t
30	206	82	80	t
30	207	82	85	t
30	208	83	90	t
30	209	83	85	t
30	210	83	75	t
26	211	146	85	t
26	212	146	95	t
26	213	146	75	t
26	214	147	80	t
26	215	147	70	t
25	162	65	95	t
25	163	65	75	t
25	165	66	70	t
25	217	65	95	t
25	218	65	75	t
25	220	66	70	t
25	161	65	80	t
25	162	66	90	t
25	162	72	90	t
25	163	66	95	t
25	163	72	95	t
25	164	66	90	t
25	164	72	90	t
25	165	67	90	t
25	166	67	95	t
25	167	68	90	t
25	168	68	90	t
25	169	68	90	t
25	170	68	90	t
25	171	68	90	t
25	172	69	90	t
25	173	69	90	t
25	173	70	90	t
25	174	69	90	t
25	174	70	90	t
25	174	71	90	t
25	175	70	90	t
25	176	70	90	t
25	177	71	90	t
25	178	71	90	t
25	179	72	90	t
25	180	72	90	t
25	216	65	80	t
25	217	66	90	t
25	217	72	90	t
25	218	66	95	t
25	218	72	95	t
25	219	66	90	t
25	219	72	90	t
25	220	67	90	t
25	232	66	90	t
25	232	72	90	t
25	243	69	90	t
25	243	70	90	t
25	246	70	90	t
25	250	72	90	t
31	251	164	85	t
31	253	164	75	t
31	254	165	80	t
31	255	165	70	t
31	252	164	10	t
33	489	263	90	t
33	490	258	90	t
33	491	264	90	t
33	492	257	90	t
33	493	270	90	t
33	494	265	85	t
33	495	268	90	t
33	496	268	90	t
33	497	257	90	t
33	498	256	90	t
33	499	261	90	t
33	500	264	85	t
33	501	259	90	t
33	502	265	90	t
33	503	253	90	t
33	504	267	90	t
33	505	255	95	t
33	506	258	90	t
33	507	259	85	t
33	508	262	90	t
33	509	270	90	t
33	510	261	90	t
33	511	253	90	t
33	512	263	90	t
33	513	253	90	t
33	514	255	90	t
33	515	259	90	t
33	516	262	90	t
33	517	262	90	t
33	518	258	90	t
33	519	269	85	t
33	520	254	85	t
33	521	255	90	t
33	522	269	90	t
32	396	238	90	t
32	397	241	90	t
32	398	241	90	t
33	523	257	90	t
33	524	263	90	t
33	525	260	90	t
33	526	265	90	t
33	527	254	90	t
33	528	261	90	t
33	529	269	90	t
33	530	256	90	t
33	531	267	85	t
33	532	260	90	t
33	533	256	90	t
33	534	268	90	t
33	535	260	90	t
33	536	270	85	t
33	537	266	90	t
33	538	254	90	t
33	539	266	90	t
33	540	264	85	t
33	541	267	90	t
33	542	266	90	t
32	399	225	90	t
32	399	229	90	t
32	400	246	90	t
32	401	235	90	t
32	402	249	90	t
32	403	248	90	t
32	404	248	90	t
32	405	245	90	t
32	406	244	90	t
32	407	245	90	t
32	408	249	90	t
32	409	248	90	t
32	410	239	90	t
32	411	227	90	t
32	412	224	90	t
32	413	230	90	t
32	414	250	90	t
32	415	250	90	t
32	416	251	90	t
32	417	224	90	t
32	418	252	90	t
32	419	238	90	t
32	420	246	90	t
32	421	247	90	t
32	422	244	90	t
32	423	243	90	t
32	424	239	90	t
32	425	250	90	t
32	426	231	90	t
32	427	251	90	t
32	428	230	90	t
32	429	233	90	t
32	430	226	90	t
32	431	227	90	t
32	432	247	90	t
32	433	238	90	t
32	434	239	90	t
32	435	231	90	t
32	436	235	90	t
32	437	252	90	t
32	438	242	90	t
32	439	224	90	t
32	439	226	90	t
32	439	228	90	t
32	440	240	90	t
32	441	243	90	t
32	442	245	90	t
32	443	227	90	t
32	444	233	90	t
32	445	252	90	t
32	446	227	90	t
32	447	225	90	t
32	447	229	90	t
32	448	251	90	t
32	449	247	90	t
32	450	239	90	t
32	451	240	90	t
32	452	241	90	t
32	453	247	90	t
32	454	226	90	t
32	455	237	90	t
32	456	234	80	t
32	457	230	90	t
32	458	227	90	t
32	459	252	90	t
32	460	242	90	t
32	461	245	90	t
32	462	248	90	t
32	463	241	90	t
32	464	242	90	t
32	465	237	90	t
32	466	240	90	t
32	467	233	90	t
32	468	250	90	t
32	469	232	90	t
32	470	244	90	t
32	471	238	90	t
32	472	236	90	t
32	473	243	90	t
32	474	232	90	t
32	475	232	90	t
32	476	242	90	t
32	477	234	80	t
32	478	240	90	t
32	479	243	90	t
32	480	234	80	t
32	481	249	90	t
32	482	249	90	t
32	483	237	90	t
32	484	226	90	t
32	485	246	90	t
32	486	244	90	t
32	487	236	90	t
32	488	236	90	t
32	563	251	90	t
32	574	251	90	t
32	631	226	90	t
34	636	314	90	t
34	637	317	90	t
34	638	317	90	t
34	639	301	90	t
34	639	305	90	t
34	640	322	90	t
34	641	311	90	t
34	642	325	90	t
34	643	324	90	t
34	644	324	90	t
34	645	321	90	t
34	646	320	90	t
34	647	321	90	t
34	648	325	90	t
34	649	324	90	t
34	650	315	90	t
34	651	303	90	t
34	652	300	90	t
34	653	306	90	t
34	654	326	90	t
34	655	326	90	t
34	656	327	90	t
34	657	300	90	t
34	658	328	90	t
34	659	314	90	t
34	660	322	90	t
34	661	323	90	t
34	662	320	90	t
34	663	319	90	t
34	664	315	90	t
34	665	326	90	t
34	666	307	90	t
34	667	327	90	t
34	668	306	90	t
34	669	309	90	t
34	670	302	90	t
34	671	303	90	t
34	672	323	90	t
34	673	314	90	t
34	674	315	90	t
34	675	307	90	t
34	676	311	90	t
34	677	328	90	t
34	678	318	90	t
34	679	300	90	t
34	679	302	90	t
34	679	304	90	t
34	680	316	90	t
34	681	319	90	t
34	682	321	90	t
34	683	303	90	t
34	684	309	90	t
34	685	328	90	t
34	686	303	90	t
34	687	301	90	t
34	687	305	90	t
34	688	327	90	t
34	689	323	90	t
34	690	315	90	t
34	691	316	90	t
34	692	317	90	t
34	693	323	90	t
34	694	302	90	t
34	695	313	90	t
34	696	310	80	t
34	697	306	90	t
34	698	303	90	t
34	699	328	90	t
34	700	318	90	t
34	701	321	90	t
34	702	324	90	t
34	703	317	90	t
34	704	318	90	t
34	705	313	90	t
34	706	316	90	t
34	707	309	90	t
34	708	326	90	t
34	709	308	90	t
34	710	320	90	t
34	711	314	90	t
34	712	312	90	t
34	713	319	90	t
34	714	308	90	t
34	715	308	90	t
34	716	318	90	t
34	717	310	80	t
34	718	316	90	t
34	719	319	90	t
34	720	310	80	t
34	721	325	90	t
34	722	325	90	t
34	723	313	90	t
34	724	302	90	t
34	725	322	90	t
34	726	320	90	t
34	727	312	90	t
34	728	312	90	t
\.


--
-- Data for Name: countermeasures; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.countermeasures (id, model_id, name, description, fixed_implementation_cost, fixed_cost_period, recurring_implementation_cost, detailed_design, implemented, include_fixed_cost, include_recurring_cost, disabled, created_at, updated_at, version, yearly_cost, tag) FROM stdin;
636	34	Anti-rollback protection	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM74
82	6	Multiple ATP tests	\N	0	12	5000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	5000	CM2
83	6	Test on jig before shipment	\N	0	12	5000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	5000	CM3
637	34	API authorization	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM102
638	34	API gateway monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM104
639	34	Artifact rejection algorithms	\N	50000	12	0	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	50000	CM5
640	34	Auto-scaling	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM152
641	34	Automated interface monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM42
642	34	Automatic archival	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM183
643	34	Autoscaling	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM172
644	34	Backpressure controls	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM173
645	34	Build attestation	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM144
646	34	Build provenance	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM133
647	34	Build signing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM141
648	34	Capacity monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM181
173	25	Controlled access to IR room	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-02-17 19:15:06.13059+02	2	0	CM13
649	34	Capacity testing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM174
180	25	Radiaction implements an ongoing patch policy for implementing CODESys software software advisories to the runtime (see SBOM, Patch SOP)	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-02-17 21:24:33.482829+02	3	0	CM22
162	25	Multiple ATP tests are performed from the manufacturing to customer delivery	\N	0	12	5000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-02-17 21:25:29.0462+02	2	5000	CM2
176	25	An attacker would need to reverse-engineer the proprietary protocol used by the sensors in order to develop an exploit in fabricated update package	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-02-17 21:26:40.220434+02	2	0	CM17
182	27	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	1	70000	CM1
183	27	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	1	120000	CM2
184	27	Input validation and anomaly detection	\N	75000	12	50000	\N	t	t	t	f	2026-06-25 10:42:18.19003+03	2026-06-25 10:42:18.19003+03	1	125000	CM4
211	26	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	1	70000	CM1
212	26	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	1	120000	CM2
213	26	Clinical performance monitoring	\N	30000	12	25000	\N	t	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	1	55000	CM3
214	26	Input validation and anomaly detection	\N	75000	12	50000	\N	t	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	1	125000	CM4
215	26	Regular model retraining with adversarial examples	\N	10000	12	100000	\N	t	t	t	f	2026-06-29 07:38:14.934245+03	2026-06-29 07:38:14.934245+03	1	110000	CM5
161	25	Hospital employee training	\N	0	12	5000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	5000	CM1
163	25	Test on jig before sending to customer	\N	0	12	5000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	5000	CM3
164	25	Site inspection	\N	0	12	5000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	5000	CM4
165	25	System power light will turn off to indicate issue	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM5
166	25	Physical locking mechanism on system side of the cable, segment locking mechanism	\N	0	12	100	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	100	CM6
167	25	Vetting process	\N	0	12	1000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	1000	CM7
168	25	Training	\N	0	12	1000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	1000	CM8
650	34	Certificate lifecycle management	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM83
651	34	Clinical Notification Testing	Implement end-to-end latency testing to ensure the alert arrives within seconds of the event. Establish a heartbeat check between the sensor and the facility's Nurse Call system to log communication failures immediately.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM12
84	6	Site inspection	\N	0	12	10000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	10000	CM4
87	6	Vetting process	\N	0	12	1000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	1000	CM7
88	6	Training	\N	0	12	1000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	1000	CM8
81	6	Employee training	\N	0	12	5000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	5000	CM1
2	1	Command Validation Guardrails	Hard safety limits and validation of control commands.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
3	1	Immutable Audit Logging	Append-only logs for control actions and configuration changes.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
4	1	Control/Data Plane Separation	Isolation of control APIs from data ingestion and analytics.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
5	1	Local Fail-Safe Mode	Autonomous safe operation during network outages.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
6	1	Sensor Data Integrity Checks	Consistency and anomaly detection for sensor data.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
7	1	Continuous Monitoring & Alerting	Detection of abnormal access patterns and system behavior.	25000	12	5000	\N	t	t	t	f	2026-01-18 12:13:57.419142+02	2026-02-04 01:51:35.641192+02	3	30000	\N
85	6	Power-loss indicator	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM5
86	6	Physical locking mechanism on system cable	\N	0	12	100	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	100	CM6
1	1	Strong Authentication & RBAC	Multi-factor authentication and role-based access control.	25000	12	150	\N	t	t	t	t	2026-01-18 12:13:57.419142+02	2026-02-02 12:02:37.650844+02	6	25150	\N
8	11	Multi-factor authentication	Implement MFA for all users	5000	12	500	\N	t	t	t	f	2026-02-03 21:49:06.104273+02	2026-02-04 01:51:35.641192+02	2	5500	CM1
9	11	Security audit	Conduct quarterly security audits	2000	12	1500	\N	t	t	t	f	2026-02-03 21:49:06.104273+02	2026-02-04 01:51:35.641192+02	2	3500	CM2
10	11	Network segmentation	Isolate critical systems	8000	12	0	\N	t	t	t	f	2026-02-03 21:49:06.104273+02	2026-02-04 01:51:35.641192+02	2	8000	CM3
13	14	Multi-factor authentication	Implement MFA for all users	5000	12	500	\N	t	t	t	f	2026-02-03 21:49:31.246303+02	2026-02-04 01:51:35.641192+02	2	5500	CM1
14	14	Security audit	Conduct quarterly security audits	2000	12	1500	\N	t	t	t	f	2026-02-03 21:49:31.246303+02	2026-02-04 01:51:35.641192+02	2	3500	CM2
15	14	Network segmentation	Isolate critical systems	8000	12	0	\N	t	t	t	f	2026-02-03 21:49:31.246303+02	2026-02-04 01:51:35.641192+02	2	8000	CM3
16	16	Integer costs	\N	1500	12	100	\N	t	t	t	f	2026-02-03 21:49:31.285327+02	2026-02-04 01:51:35.641192+02	2	1600	CM_INT
181	25	The update package creation process signs and encrypts the application code using X.509 certificates.	The update package creation process signs and encrypts the application code using X.509 certificates.	0	12	0	\N	t	t	t	f	2026-02-17 21:29:04.109142+02	2026-02-17 21:34:53.1107+02	2	0	\N
185	29	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	1	70000	CM1
186	29	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	1	120000	CM2
187	29	Clinical performance monitoring	\N	30000	12	25000	\N	t	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	1	55000	CM3
188	29	Input validation and anomaly detection	\N	75000	12	50000	\N	t	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	1	125000	CM4
189	29	Regular model retraining with adversarial examples	\N	10000	12	100000	\N	t	t	t	f	2026-06-25 11:05:26.979986+03	2026-06-25 11:05:26.979986+03	1	110000	CM5
652	34	Clinical performance monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM3
653	34	Clinical verification workflow	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM17
654	34	Configuration audit logging	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM194
655	34	Configuration integrity monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM191
656	34	Continuous Security Posture Drift Monitoring	Mitigates shared infrastructure risk by monitoring the boundary between Neteera and the platform provider. Automate real-time IAM (Identity and Access Management) auditing. If the upstream provider modifies access permissions, introduces an unvetted third-party API, or alters data-at-rest encryption settings on the AWS bucket, an automated alert triggers to isolate the Neteera environment.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM283
216	25	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 07:59:04.993739+03	2026-06-29 08:07:19.491508+03	3	70000	CM1
217	25	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-29 07:59:04.993739+03	2026-06-29 08:07:19.491508+03	3	120000	CM2
218	25	Clinical performance monitoring	\N	30000	12	25000	\N	t	t	t	f	2026-06-29 07:59:04.993739+03	2026-06-29 08:07:19.491508+03	3	55000	CM3
219	25	Input validation and anomaly detection	\N	75000	12	50000	\N	t	t	t	f	2026-06-29 07:59:04.993739+03	2026-06-29 08:07:19.491508+03	3	125000	CM4
220	25	Regular model retraining with adversarial examples	\N	10000	12	100000	\N	t	t	t	f	2026-06-29 07:59:04.993739+03	2026-06-29 08:07:19.491508+03	3	110000	CM5
251	31	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 08:32:25.672864+03	2026-06-29 08:32:25.672864+03	1	70000	CM1
252	31	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-29 08:32:25.672864+03	2026-06-29 08:32:25.672864+03	1	120000	CM2
253	31	Clinical performance monitoring	\N	30000	12	25000	\N	t	t	t	f	2026-06-29 08:32:25.672864+03	2026-06-29 08:32:25.672864+03	1	55000	CM3
254	31	Input validation and anomaly detection	\N	75000	12	50000	\N	t	t	t	f	2026-06-29 08:32:25.672864+03	2026-06-29 08:32:25.672864+03	1	125000	CM4
255	31	Regular model retraining with adversarial examples	\N	10000	12	100000	\N	t	t	t	f	2026-06-29 08:32:25.672864+03	2026-06-29 08:32:25.672864+03	1	110000	CM5
657	34	Continuous signal quality assessment	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM1
658	34	Credential Rotation and Audit Logging	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM297
659	34	Cryptographically signed firmware	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM73
660	34	DDoS protection	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM151
661	34	Dependency health monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM162
662	34	Dependency scanning	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM132
663	34	Device binding	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM124
664	34	Device certificates	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM82
665	34	Digitally signed configuration	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM192
666	34	Disaster recovery testing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM22
667	34	Edge Autonomous Fallback Mode (Local Survivability)	If the connection to the BioT cloud ingest endpoint drops, the physical Neteera hardware switches to a "Local Alert" state. The device continues to run its micro-radar classification algorithms locally at the edge. It routes critical bed-exit and respiratory distress notifications over the local facility Wi-Fi directly to an on-premise pager or nurse call system, bypasssing the cloud entirely during an outage.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM281
668	34	EMR reconciliation	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM16
669	34	Encryption at rest and in transit	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM28
670	34	Environmental Noise Filtering	Implement algorithms specifically designed to detect and filter out periodic motion from non-human sources (like a spinning room fan or vibrating HVAC vent) that can mimic or distort heart and respiratory rates.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM8
17	16	High costs	\N	2500	12	250	\N	t	t	t	f	2026-02-03 21:49:31.285327+02	2026-02-04 01:51:35.641192+02	2	2750	CM_DECIMAL
18	16	Zero recurring cost	\N	5000	12	0	\N	t	t	t	f	2026-02-03 21:49:31.285327+02	2026-02-04 01:51:35.641192+02	2	5000	CM_ZERO
19	17	Original name	\N	1000	12	100	\N	t	t	t	f	2026-02-03 21:49:31.294947+02	2026-02-04 01:51:35.641192+02	2	1100	CM_UPDATE
20	17	Updated name	\N	2000	12	200	\N	t	t	t	f	2026-02-03 21:49:31.298798+02	2026-02-04 01:51:35.641192+02	2	2200	CM_UPDATE
91	6	Periodic clinical team checks	\N	0	12	5000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	5000	CM11
92	6	Sealed system	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM12
93	6	Hospital physical security	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM13
94	6	Controlled room access	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM14
95	6	Tool access control	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM15
99	6	Physical barriers	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-04 01:51:35.641192+02	2	0	CM19
101	6	Hospital employee training	\N	0	12	5000	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	5000	CM1
105	6	Support station has a power-loss indicator	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM5
106	6	Physical locking mechanism on system power cable	\N	0	12	100	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	100	CM6
89	6	Service reports	\N	0	12	1000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	1000	CM9
90	6	ATP	\N	0	12	1000	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	1000	CM10
111	6	Clinical team periodically verifies that system is online and not in technician mode	\N	0	12	5000	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	5000	CM11
112	6	Support station is sealed	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM12
113	6	Controlled access to electrophysiology lab	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM13
114	6	Special tools are needed in order to gain access to support station USB port	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM15
96	6	Dedicated interface software	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	0	CM16
97	6	Proprietary protocol	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	0	CM17
98	6	Strong password policy	\N	1000	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	1000	CM18
100	6	Equipment locked away	\N	0	12	0	\N	t	t	t	f	2026-02-04 00:08:18.861712+02	2026-02-15 14:54:51.345536+02	3	0	CM20
119	6	CODESys implements an ongoing software security program	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM21
120	6	Radiaction implements an ongoing patch policy for CODESys	\N	0	12	0	\N	t	t	t	f	2026-02-15 14:54:51.345536+02	2026-02-15 16:01:27.97048+02	2	0	CM22
671	34	Fall-Back "Empty Bed" State Validation	If movement tracking becomes fully occluded or lost, the system should default to cross-referencing physiological data. If no heart rate or respiration is detected anywhere in the zone, it should trigger an immediate Presence Lost alert rather than failing silently.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM14
672	34	Graceful degradation	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM163
673	34	Hardware Root of Trust	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM72
674	34	Hardware-backed device identity	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM84
675	34	High-availability architecture	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM21
676	34	Interface conformance testing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM41
677	34	Just-In-Time (JIT) Access	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM295
678	34	Least privilege	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM112
679	34	Measurement confidence scoring	Tie the confidence score directly to Signal-to-Noise Ratio (SNR) and phase stability. Ensure the software withholds the measurement entirely (or marks it visually) if the score drops below a validated clinical threshold, rather than displaying a guessed value.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM2
680	34	Message timestamps	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM93
681	34	MFA	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM122
682	34	MFA for developers	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM143
683	34	Movement Classifier Validation	Do not overfit to standard movement profiles. Validate specifically against edge-case cohorts (e.g., extremely frail patients who move slowly, or patients with chorea/parkinsonian tremors). Test with common physical occlusions included in the training data, such as heavy weighted blankets or over-bed tables.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM10
684	34	Multi-factor authentication	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM26
685	34	Multi-Factor Authentication (MFA) Enforcement	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM294
190	30	Image quality validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	70000	CM1
191	30	Radiologist review of low-confidence cases	\N	0	12	120000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	120000	CM2
192	30	Clinical performance monitoring	\N	30000	12	25000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	55000	CM3
193	30	High-sensitivity validation testing	\N	80000	12	15000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	95000	CM4
194	30	Mandatory clinician review	\N	0	12	100000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	100000	CM5
195	30	Post-market surveillance	\N	25000	12	25000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	50000	CM6
196	30	Multi-factor authentication	\N	10000	12	5000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	15000	CM7
197	30	Signed model deployment pipeline	\N	40000	12	10000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	50000	CM8
198	30	Separation of duties	\N	5000	12	25000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	30000	CM9
199	30	Immutable backups	\N	20000	12	15000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	35000	CM10
200	30	Endpoint detection and response	\N	10000	12	30000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	40000	CM11
201	30	Disaster recovery testing	\N	5000	12	20000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	25000	CM12
202	30	Encryption at rest	\N	10000	12	5000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	15000	CM13
203	30	Continuous cloud posture monitoring	\N	15000	12	25000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	40000	CM14
204	30	Quarterly access reviews	\N	0	12	12000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	12000	CM15
205	30	Consent management platform	\N	30000	12	10000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	40000	CM16
206	30	Data governance review board	\N	10000	12	40000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	50000	CM17
207	30	Dataset release approval workflow	\N	5000	12	15000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	20000	CM18
208	30	DICOM identity validation	\N	20000	12	10000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	30000	CM19
209	30	Workflow verification checkpoint	\N	10000	12	25000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	35000	CM20
210	30	Audit trail monitoring	\N	10000	12	10000	\N	t	t	t	f	2026-06-25 11:26:09.752451+03	2026-06-25 11:26:09.752451+03	1	20000	CM21
232	25	Multiple ATP tests	\N	0	12	5000	\N	t	t	t	f	2026-06-29 08:23:40.678248+03	2026-06-29 08:23:40.678248+03	1	5000	CM2
169	25	Service reports	\N	0	12	1000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	1000	CM9
170	25	ATP	\N	0	12	1000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	1000	CM10
171	25	Clinical team periodically verifies that system is online and not in technician mode	\N	0	12	5000	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	5000	CM11
172	25	Support station is sealed	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM12
243	25	Controlled access to electrophysiology lab	\N	0	12	0	\N	t	t	t	f	2026-06-29 08:23:40.678248+03	2026-06-29 08:23:40.678248+03	1	0	CM13
174	25	Special tools are needed in order to gain access to support station USB port	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM15
175	25	Dedicated interface software	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM16
246	25	An attacker would need to reverse-engineer the proprietary protocol used by the sensors	\N	0	12	0	\N	t	t	t	f	2026-06-29 08:23:40.678248+03	2026-06-29 08:23:40.678248+03	1	0	CM17
177	25	Strong password policy	\N	1000	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	1000	CM18
178	25	Equipment locked away	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM20
179	25	CODESys implements an ongoing software security program	\N	0	12	0	\N	t	t	t	f	2026-02-15 17:12:40.11863+02	2026-06-29 08:23:40.678248+03	2	0	CM21
250	25	Radiaction implements an ongoing patch policy for CODESys	\N	0	12	0	\N	t	t	t	f	2026-06-29 08:23:40.678248+03	2026-06-29 08:23:40.678248+03	1	0	CM22
686	34	Multi-Feature Movement Analysis	Incorporate spatial tracking thresholds (e.g., tracking the center of mass shifting toward the perimeter of the sensor's fields of view). Use temporal sequencing (e.g., a sudden increase in respiratory rate often precedes the physical act of sitting up).	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM11
687	34	Multi-parameter validation	\N	50000	12	0	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	50000	CM4
688	34	Multi-Party / Independent Code Signing Validation	Prevents a compromised upstream provider from pushing malicious firmware updates to the physical sensors. The Neteera edge device requires a dual-signature for any firmware update. Even if the BioT pipeline initiates the update, the device will reject the package unless it is also cryptographically signed by an independent Neteera corporate private key kept in an offline Hardware Security Module (HSM).	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM282
689	34	Multi-zone deployment	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM161
690	34	Mutual TLS	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM81
691	34	Nonces	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM91
692	34	OAuth2/OIDC	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM101
693	34	Offline operation	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM164
694	34	Out-of-Range Alerts	Create a system alert that triggers if the sensor outputs data that is physiologically impossible for a human (e.g., a respiratory rate of 150 breaths per minute), signaling immediate sensor malfunction.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM9
695	34	Periodic audit review	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM62
696	34	Physiological consistency validation	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM32
697	34	Positive patient identification	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM15
698	34	Pre-Exit Intent Detection (Early Warning)	Train the classifier to detect the sequence leading to a bed exit (e.g., rolling over, then sitting up) to issue a pre-exit warning before the patient's feet actually hit the floor.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM13
699	34	Principle of Least Privilege (PoLP)	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM296
700	34	Privilege auditing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM113
701	34	Protected branches	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM142
702	34	Queue monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM171
703	34	Rate limiting	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM103
704	34	RBAC	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM111
705	34	Regulatory readiness exercises	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM63
706	34	Replay detection	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM94
707	34	Role-based access control	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM27
708	34	Role-based configuration management	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM193
709	34	Runtime integrity verification	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM24
710	34	SBOM management	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM131
711	34	Secure Boot	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM71
712	34	Secure patch management	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM52
713	34	Secure session tokens	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM121
714	34	Secure software lifecycle	\N	40000	12	200000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	240000	CM25
715	34	Secure software signing	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM23
716	34	Segregation of duties	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM114
717	34	Sensor integrity verification	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM31
718	34	Sequence numbers	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM92
719	34	Session expiration	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM123
720	34	Signal anomaly detection	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM30
721	34	Storage quotas	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM182
722	34	Storage redundancy	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM184
723	34	Tamper-resistant audit logging	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM61
724	34	Test both the physical micro-radar sensors and the algorithm's interpretation (software) for drift	Implement automated power-on self-tests (POST) and periodic background calibration checks. Use internal reference loops where the transmitter sends a known signal directly back to the receiver to test for hardware-only drift.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM7
725	34	Traffic filtering	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM154
416	32	Continuous Security Posture Drift Monitoring	Mitigates shared infrastructure risk by monitoring the boundary between Neteera and the platform provider. Automate real-time IAM (Identity and Access Management) auditing. If the upstream provider modifies access permissions, introduces an unvetted third-party API, or alters data-at-rest encryption settings on the AWS bucket, an automated alert triggers to isolate the Neteera environment.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-06-29 09:16:34.368546+03	1	70000	CM283
726	34	Trusted artifact repositories	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM134
727	34	Vulnerability disclosure	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM51
728	34	Vulnerability monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-07-24 12:34:23.237325+03	2026-07-24 12:34:23.237325+03	1	70000	CM53
427	32	Edge Autonomous Fallback Mode (Local Survivability)	If the connection to the BioT cloud ingest endpoint drops, the physical Neteera hardware switches to a "Local Alert" state. The device continues to run its micro-radar classification algorithms locally at the edge. It routes critical bed-exit and respiratory distress notifications over the local facility Wi-Fi directly to an on-premise pager or nurse call system, bypasssing the cloud entirely during an outage.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-06-29 09:16:34.368546+03	1	70000	CM281
534	33	Secure update capability with risk-based patching and compensating controls	\N	180000	12	60000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	240000	CM48
432	32	Graceful degradation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM163
484	32	Test both the physical micro-radar sensors and the algorithm's interpretation (software) for drift	Implement automated power-on self-tests (POST) and periodic background calibration checks. Use internal reference loops where the transmitter sends a known signal directly back to the receiver to test for hardware-only drift.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-06-29 09:16:34.368546+03	1	70000	CM7
489	33	Accelerated aging and lifetime performance characterization	\N	180000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	230000	CM31
490	33	API gateway monitoring, rate limiting, and anomaly detection	\N	90000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	130000	CM18
491	33	Architectural isolation and least-privilege access for third-party services	\N	110000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	150000	CM35
492	33	Automated reconciliation with clinical study and healthcare records	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM15
493	33	Clinical-study-specific cyber incident response and communication plan	\N	80000	12	35000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	115000	CM52
494	33	Continuous access monitoring and data-loss detection	\N	90000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	130000	CM39
495	33	Continuous SBOM and exploitability monitoring across supported versions	\N	110000	12	55000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	165000	CM47
496	33	Coordinated vulnerability disclosure and product-security response process	\N	90000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	140000	CM46
497	33	Cryptographic patient-implant-reader binding	\N	100000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	130000	CM13
498	33	Cryptographically signed software and firmware with anti-rollback	\N	150000	12	35000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	185000	CM11
499	33	Cybersecurity traceability matrix linked to system and clinical risk	\N	100000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	125000	CM25
500	33	Dependency health monitoring, substitution plans, and tested failover	\N	120000	12	45000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	165000	CM36
501	33	Disaster recovery with tested recovery-time and recovery-point objectives	\N	120000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	170000	CM20
502	33	Encryption in transit and at rest with managed key rotation	\N	80000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	110000	CM37
503	33	End-to-end calibration and drift monitoring	\N	120000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	160000	CM1
504	33	End-to-end measurement and decision provenance	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM44
505	33	Fail-safe workflow that withholds guidance when data confidence is insufficient	\N	80000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	105000	CM9
506	33	Fine-grained role-based and attribute-based authorization	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM17
507	33	Graceful degradation and offline continuity for critical workflows	\N	120000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	160000	CM21
508	33	Hardware-backed implant and reader identity	\N	140000	12	35000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	175000	CM28
509	33	Immutable backups and validated recovery of study and audit evidence	\N	120000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	170000	CM53
510	33	Independent penetration testing and control-effectiveness verification	\N	120000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	160000	CM26
511	33	Longitudinal clinical performance monitoring by device and cohort	\N	100000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	150000	CM3
512	33	Longitudinal drift detection using patient and population baselines	\N	110000	12	45000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	155000	CM32
513	33	Measurement confidence and physiological plausibility scoring	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM2
514	33	Measurement freshness, completeness, and sequence validation	\N	75000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	100000	CM7
515	33	Multi-zone high-availability architecture and dependency isolation	\N	150000	12	70000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	220000	CM19
516	33	Mutual authentication with device-specific certificates and managed key lifecycle	\N	130000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	170000	CM29
517	33	Nonces, sequence numbers, timestamps, and replay detection	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM30
518	33	OAuth2 or OIDC with phishing-resistant multi-factor authentication	\N	100000	12	35000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	135000	CM16
519	33	Patient application warnings and escalation for unexpected readings	\N	70000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	95000	CM51
520	33	Patient guidance and automated troubleshooting for reader alignment	\N	60000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	85000	CM6
521	33	Physician-approved treatment guardrails and dose-change limits	\N	100000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	130000	CM8
522	33	Physician-configured treatment limits and exception handling	\N	80000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	110000	CM50
523	33	Positive patient identification and two-person enrollment verification	\N	70000	12	25000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	95000	CM14
524	33	Post-market performance surveillance with predefined escalation thresholds	\N	100000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	150000	CM33
525	33	Protected branches, privileged-access controls, and developer MFA	\N	80000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	110000	CM23
526	33	Pseudonymization, data minimization, and environment segregation	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM38
527	33	Real-time link quality and power-transfer validation	\N	100000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	130000	CM4
528	33	Regulatory readiness reviews and evidence-completeness gates	\N	80000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	110000	CM27
529	33	Repeated-measurement confirmation and trend-based decision rules	\N	90000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	120000	CM49
530	33	Reproducible builds, provenance attestation, and protected release pipeline	\N	140000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	190000	CM12
531	33	Retention, review, and regulatory reconstruction exercises	\N	70000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	100000	CM45
532	33	SBOM, dependency scanning, and continuous vulnerability monitoring	\N	100000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	150000	CM22
533	33	Secure boot and hardware-backed root of trust	\N	180000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	220000	CM10
535	33	Signed build artifacts and independently verified build provenance	\N	130000	12	45000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	175000	CM24
536	33	Site continuity exercises and alternate clinical workflows	\N	100000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	140000	CM54
537	33	Statistical process control and automated manufacturing test limits	\N	140000	12	45000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	185000	CM41
538	33	Store-and-forward delivery with retry and integrity verification	\N	80000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	110000	CM5
539	33	Supplier change control and incoming component verification	\N	110000	12	40000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	150000	CM42
540	33	Supplier security requirements, evidence review, and contractual notification	\N	70000	12	30000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	100000	CM34
541	33	Tamper-evident audit logging with trusted time synchronization	\N	100000	12	35000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	135000	CM43
542	33	Unit-level calibration with traceable reference standards	\N	160000	12	50000	\N	t	t	t	f	2026-07-20 21:18:43.837738+03	2026-07-20 21:18:43.837738+03	1	210000	CM40
396	32	Anti-rollback protection	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM74
397	32	API authorization	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM102
398	32	API gateway monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM104
399	32	Artifact rejection algorithms	\N	50000	12	0	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	50000	CM5
400	32	Auto-scaling	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM152
401	32	Automated interface monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM42
402	32	Automatic archival	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM183
403	32	Autoscaling	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM172
404	32	Backpressure controls	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM173
405	32	Build attestation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM144
406	32	Build provenance	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM133
407	32	Build signing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM141
408	32	Capacity monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM181
409	32	Capacity testing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM174
410	32	Certificate lifecycle management	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM83
411	32	Clinical Notification Testing	Implement end-to-end latency testing to ensure the alert arrives within seconds of the event. Establish a heartbeat check between the sensor and the facility's Nurse Call system to log communication failures immediately.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM12
412	32	Clinical performance monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM3
413	32	Clinical verification workflow	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM17
414	32	Configuration audit logging	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM194
415	32	Configuration integrity monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM191
563	32	Continuous Security Posture Drift Monitoring.	Mitigates shared infrastructure risk by monitoring the boundary between Neteera and the platform provider. Automate real-time IAM (Identity and Access Management) auditing. If the upstream provider modifies access permissions, introduces an unvetted third-party API, or alters data-at-rest encryption settings on the AWS bucket, an automated alert triggers to isolate the Neteera environment.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:32:04.656549+03	2026-07-24 12:32:04.656549+03	1	70000	CM283
417	32	Continuous signal quality assessment	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM1
418	32	Credential Rotation and Audit Logging	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM297
419	32	Cryptographically signed firmware	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM73
420	32	DDoS protection	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM151
421	32	Dependency health monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM162
422	32	Dependency scanning	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM132
423	32	Device binding	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM124
424	32	Device certificates	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM82
425	32	Digitally signed configuration	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM192
426	32	Disaster recovery testing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM22
574	32	Edge Autonomous Fallback Mode (Local Survivability).	If the connection to the BioT cloud ingest endpoint drops, the physical Neteera hardware switches to a "Local Alert" state. The device continues to run its micro-radar classification algorithms locally at the edge. It routes critical bed-exit and respiratory distress notifications over the local facility Wi-Fi directly to an on-premise pager or nurse call system, bypasssing the cloud entirely during an outage.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:32:04.656549+03	2026-07-24 12:32:04.656549+03	1	70000	CM281
428	32	EMR reconciliation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM16
429	32	Encryption at rest and in transit	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM28
430	32	Environmental Noise Filtering	Implement algorithms specifically designed to detect and filter out periodic motion from non-human sources (like a spinning room fan or vibrating HVAC vent) that can mimic or distort heart and respiratory rates.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM8
431	32	Fall-Back "Empty Bed" State Validation	If movement tracking becomes fully occluded or lost, the system should default to cross-referencing physiological data. If no heart rate or respiration is detected anywhere in the zone, it should trigger an immediate "Presence Lost" alert rather than failing silently.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM14
433	32	Hardware Root of Trust	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM72
434	32	Hardware-backed device identity	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM84
435	32	High-availability architecture	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM21
436	32	Interface conformance testing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM41
437	32	Just-In-Time (JIT) Access	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM295
438	32	Least privilege	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM112
439	32	Measurement confidence scoring	Tie the confidence score directly to Signal-to-Noise Ratio (SNR) and phase stability. Ensure the software withholds the measurement entirely (or marks it visually) if the score drops below a validated clinical threshold, rather than displaying a guessed value.	50000	12	0	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	50000	CM2
440	32	Message timestamps	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM93
441	32	MFA	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM122
442	32	MFA for developers	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM143
443	32	Movement Classifier Validation	Do not overfit to standard movement profiles. Validate specifically against edge-case cohorts (e.g., extremely frail patients who move slowly, or patients with chorea/parkinsonian tremors). Test with common physical occlusions included in the training data, such as heavy weighted blankets or over-bed tables.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM10
444	32	Multi-factor authentication	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM26
445	32	Multi-Factor Authentication (MFA) Enforcement	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM294
446	32	Multi-Feature Movement Analysis	Incorporate spatial tracking thresholds (e.g., tracking the center of mass shifting toward the perimeter of the sensor's fields of view). Use temporal sequencing (e.g., a sudden increase in respiratory rate often precedes the physical act of sitting up).	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM11
447	32	Multi-parameter validation	\N	50000	12	0	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	50000	CM4
448	32	Multi-Party / Independent Code Signing Validation	Prevents a compromised upstream provider from pushing malicious firmware updates to the physical sensors. The Neteera edge device requires a dual-signature for any firmware update. Even if the BioT pipeline initiates the update, the device will reject the package unless it is also cryptographically signed by an independent Neteera corporate private key kept in an offline Hardware Security Module (HSM).	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM282
449	32	Multi-zone deployment	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM161
450	32	Mutual TLS	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM81
451	32	Nonces	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM91
452	32	OAuth2/OIDC	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM101
453	32	Offline operation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM164
454	32	Out-of-Range Alerts	Create a system alert that triggers if the sensor outputs data that is physiologically impossible for a human (e.g., a respiratory rate of 150 breaths per minute), signaling immediate sensor malfunction.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM9
455	32	Periodic audit review	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM62
456	32	Physiological consistency validation	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM32
457	32	Positive patient identification	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM15
458	32	Pre-Exit Intent Detection (Early Warning)	Train the classifier to detect the sequence leading to a bed exit (e.g., rolling over, then sitting up) to issue a pre-exit warning before the patient's feet actually hit the floor.	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM13
459	32	Principle of Least Privilege (PoLP)	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM296
460	32	Privilege auditing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM113
461	32	Protected branches	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM142
462	32	Queue monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM171
463	32	Rate limiting	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM103
464	32	RBAC	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM111
465	32	Regulatory readiness exercises	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM63
466	32	Replay detection	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM94
467	32	Role-based access control	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM27
468	32	Role-based configuration management	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM193
469	32	Runtime integrity verification	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM24
470	32	SBOM management	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM131
471	32	Secure Boot	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM71
472	32	Secure patch management	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM52
473	32	Secure session tokens	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM121
474	32	Secure software lifecycle	\N	40000	12	200000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	240000	CM25
475	32	Secure software signing	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM23
476	32	Segregation of duties	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM114
477	32	Sensor integrity verification	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM31
478	32	Sequence numbers	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM92
479	32	Session expiration	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM123
480	32	Signal anomaly detection	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM30
481	32	Storage quotas	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM182
482	32	Storage redundancy	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM184
483	32	Tamper-resistant audit logging	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM61
631	32	Test both the physical micro-radar sensors and the algorithm's interpretation (software) for drift.	Implement automated power-on self-tests (POST) and periodic background calibration checks. Use internal reference loops where the transmitter sends a known signal directly back to the receiver to test for hardware-only drift.	50000	12	20000	\N	t	t	t	f	2026-07-24 12:32:04.656549+03	2026-07-24 12:32:04.656549+03	1	70000	CM7
485	32	Traffic filtering	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM154
486	32	Trusted artifact repositories	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM134
487	32	Vulnerability disclosure	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM51
488	32	Vulnerability monitoring	\N	50000	12	20000	\N	t	t	t	f	2026-06-29 09:16:34.368546+03	2026-07-24 12:32:04.656549+03	2	70000	CM53
\.


--
-- Data for Name: entrypoint_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.entrypoint_threat (model_id, entrypoint_id, threat_id) FROM stdin;
\.


--
-- Data for Name: entrypoints; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.entrypoints (id, model_id, name, description) FROM stdin;
\.


--
-- Data for Name: models; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.models (id, name, version, author, company, category, keywords, description, created_at, updated_at) FROM stdin;
6	Radiaction 0.5	0.5	DL	Radiaction Medical	Medical device	\N	Comprehensive Scatter Radiation Protection\nThe Radiaction Smart Shield creates a dynamic barrier at the touch of a button without compromising image quality. Physicians can maintain workflow efficiency with a setup that takes just seconds and one-button operation, retraction, and deployment. Because Radiaction blocks radiation at the source, the team maintains immediate access to their patients in everyday cases or emergencies while benefiting from advanced radiation protection.	2026-02-01 11:36:17.181657+02	2026-02-01 11:36:17.181657+02
3	MedTech hospital device without connectivity	1.0	DL	OpenCRO	\N	\N	MedTech hospital device without connectivity	2026-01-18 13:47:22.246564+02	2026-01-18 13:47:22.246564+02
31	Diagnostic AI system	1.0	DL	Diagnostic AI Systems Inc.	Radiology	\N	AI-assisted diagnosis of aortic aneurysms	2026-06-29 08:28:44.853681+03	2026-06-29 08:28:44.853681+03
25	Radiaction 1.0	1.0	DL	Radiaction Medical	FDA Cyber	\N	Comprehensive Scatter Radiation Protection\nThe Radiaction Smart Shield creates a dynamic barrier at the touch of a button without compromising image quality. Physicians can maintain workflow efficiency with a setup that takes just seconds and one-button operation, retraction, and deployment. Because Radiaction blocks radiation at the source, the team maintains immediate access to their patients in everyday cases or emergencies while benefiting from advanced radiation protection.	2026-02-15 11:43:16.449956+02	2026-02-15 11:43:16.449956+02
4	LaaS	1.0	DL	OpenCRO	\N	\N	Connected LaaS system	2026-01-18 14:36:50.358217+02	2026-01-18 14:36:50.358217+02
1	Baseline	1.0	DL	OpenCRO	\N	\N	Baseline medical device model - example	2026-01-18 13:43:19.172148+02	2026-01-18 13:43:19.174742+02
33	Vectorious	1	Danny	OpenCRO	\N	\N	Threat story	2026-07-20 21:08:38.214662+03	2026-07-20 21:08:38.214662+03
32	Neteera 0.1	0.1	OpenCRO	Neteera	\N	\N	The Neteera device is a contact-free, continuous patient monitoring system. Its primary intended use is to measure an adult patient's heart rate, respiration rate, and bed exit status in healthcare facilities and home settings.	2026-06-29 08:59:21.860494+03	2026-06-29 08:59:21.860494+03
34	Neteera 0.2	0.2	OpenCRO	Neteera	\N	\N	The Neteera device is a contact-free, continuous patient monitoring system. Its primary intended use is to measure an adult patient's heart rate, respiration rate, and bed exit status in healthcare facilities and home settings.	2026-07-24 11:15:01.059921+03	2026-07-24 11:15:01.059921+03
\.


--
-- Data for Name: parameters; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.parameters (id, parameter_name, display_name, value) FROM stdin;
\.


--
-- Data for Name: risk_history; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.risk_history ("time", series, value, model_id, version, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: threats; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.threats (id, model_id, name, description, probability, damage_description, spoofing, tampering, repudiation, information_disclosure, denial_of_service, elevation_of_privilege, mitigation_level, disabled, created_at, updated_at, card_id, version, domain, tag) FROM stdin;
80	30	Ransomware attack disrupts clinical processing	Ransomware attack disrupts clinical processing	12	\N	f	f	f	f	f	f	0	f	2026-06-25 11:26:09.752451	2026-07-05 12:15:34.699721	698fb6b6-c1e3-4340-b599-cfb058347bc3	1	CYBER	R4
146	26	Missed aortic aneurysm due to image quality degradation	Poor image quality may result in a misdiagnosis	0	\N	f	f	f	f	f	f	97	f	2026-06-29 07:38:14.934245	2026-07-05 12:00:40.034632	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CLINICAL	R1
34	6	Preset configuration may be changed in the support station UI	Preset configuration may be changed in the support station UI	40	\N	f	f	f	f	f	f	97	f	2026-02-04 00:08:18.861712	2026-07-05 12:00:40.034632	c89552dc-420a-4459-9004-216cf107f7ac	3	CYBER_PHYSICAL	R1
3	1	Service Disruption During Active Experiments	Loss of availability during active lab processing runs.	3	Experiment failure and loss of biological materials.	f	f	t	t	t	f	0	t	2026-01-12 12:41:32.484388	2026-07-05 12:15:47.249665	9e4d617f-e697-4737-8ccb-ae8e920b7ea9	5	X	T1
225	32	False deterioration indication	False deterioration indication	16	\N	f	f	f	f	f	f	99	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	6	CLINICAL	R2
227	32	Bed-exit event not detected	Bed-exit event not detected	8	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	5	CLINICAL	R4
65	25	Preset configuration may be changed in the support station UI	Preset configuration may be changed in the support station UI	40	\N	f	f	f	f	f	f	100	f	2026-02-15 17:12:40.11863	2026-07-19 11:43:06.302208	c89552dc-420a-4459-9004-216cf107f7ac	14	CYBER_PHYSICAL	R1
73	27	Missed diagnosis due to image quality	Low-quality imaging reduces AI accuracy	0	\N	f	f	f	f	f	f	97	f	2026-06-25 10:42:18.19003	2026-07-05 12:00:40.034632	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CLINICAL	R1
75	29	Missed aortic aneurysm due to image quality degradation	Missed aortic aneurysm due to image quality degradation	15	\N	f	f	f	f	f	f	97	f	2026-06-25 11:05:26.979986	2026-07-05 12:00:40.034632	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CLINICAL	R1
81	30	Exposure of patient CTA studies from cloud storage	Exposure of patient CTA studies from cloud storage	10	\N	f	f	f	f	f	f	0	f	2026-06-25 11:26:09.752451	2026-07-05 12:15:34.699721	698fb6b6-c1e3-4340-b599-cfb058347bc3	1	PRIVACY	R5
82	30	Patient data used beyond original consent	Patient data used beyond original consent	7	\N	f	f	f	f	f	f	0	f	2026-06-25 11:26:09.752451	2026-07-05 12:15:34.699721	698fb6b6-c1e3-4340-b599-cfb058347bc3	1	PRIVACY	R6
83	30	Wrong patient associated with AI analysis	Wrong patient associated with AI analysis	3	\N	f	f	f	f	f	f	0	f	2026-06-25 11:26:09.752451	2026-07-05 12:15:34.699721	698fb6b6-c1e3-4340-b599-cfb058347bc3	1	CLINICAL_PRIVACY	R7
67	25	System power is disconnected by mistake	System power is disconnected by mistake	30	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	7	PHYSICAL_SECURITY	R3
68	25	Field Service Rep makes an unauthorized change to system	Field Service Rep makes an unauthorized change to system	20	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	3	INSIDER_THREAT	R4
69	25	System is sabotaged	System is sabotaged	10	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	4	PHYSICAL_SECURITY	R5
36	6	System power is disconnected by mistake	System power is disconnected by mistake	30	\N	f	f	f	f	f	f	0	f	2026-02-04 00:08:18.861712	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	2	PHYSICAL_SECURITY	R3
37	6	Field Service Rep makes an unauthorized change	Field Service Rep makes an unauthorized change	20	\N	f	f	f	f	f	f	0	f	2026-02-04 00:08:18.861712	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	2	INSIDER_THREAT	R4
38	6	System is sabotaged	System is sabotaged	10	\N	f	f	f	f	f	f	0	f	2026-02-04 00:08:18.861712	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	2	PHYSICAL_SECURITY	R5
39	6	An unauthorized change is made to sensor parameters	An unauthorized change is made to sensor parameters	20	\N	f	f	f	f	f	f	0	f	2026-02-04 00:08:18.861712	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	2	CYBER_PHYSICAL	R6
40	6	Software Hack or local attack on support station	Software Hack or local attack on support station	20	\N	f	f	f	f	f	f	0	f	2026-02-04 00:08:18.861712	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	2	CYBER_PHYSICAL	R7
48	6	CODESys runtime issues impact correct system operation	CODESys runtime issues impact correct system operation	10	\N	f	f	f	f	f	f	0	f	2026-02-15 14:54:51.345536	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	1	SUPPLY_CHAIN	R8
70	25	An unauthorized change is made to sensor parameters	An unauthorized change is made to sensor parameters	20	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	3	CYBER_PHYSICAL	R6
74	27	Adversarial attack on AI model	AI vulnerable to adversarial perturbations	0	\N	f	f	f	f	f	f	6	f	2026-06-25 10:42:18.19003	2026-07-01 18:26:02.497321	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CYBER_PHYSICAL	R2
76	29	Adversarial attack on medical imaging AI	Adversarial attack on medical imaging AI	8	\N	f	f	f	f	f	f	6	f	2026-06-25 11:05:26.979986	2026-07-01 18:26:02.497321	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CYBER_PHYSICAL	R2
71	25	Software Hack or local attack on support station	Software Hack or local attack on support station	20	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	9	CYBER_PHYSICAL	R7
72	25	CODESys runtime issues impact correct system operation	CODESys runtime issues impact correct system operation	10	\N	f	f	f	f	f	f	0	f	2026-02-15 17:12:40.11863	2026-07-05 12:15:34.699721	c89552dc-420a-4459-9004-216cf107f7ac	3	SUPPLY_CHAIN	R8
228	32	False bed-exit notification	False bed-exit notification	11	\N	f	f	f	f	f	f	90	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CLINICAL	R5
226	32	Contactless physiological measurements become inaccurate	Contactless physiological measurements become inaccurate	10	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CLINICAL	R3
66	25	Supply chain attack	Supply chain attack	20	\N	f	f	f	f	f	f	6	f	2026-02-15 17:12:40.11863	2026-07-01 18:26:02.497321	c89552dc-420a-4459-9004-216cf107f7ac	7	SUPPLY_CHAIN	R2
78	30	Acute aortic dissection not detected by AI	Acute aortic dissection not detected by AI	5	\N	f	f	f	f	f	f	6	f	2026-06-25 11:26:09.752451	2026-07-01 18:26:02.497321	698fb6b6-c1e3-4340-b599-cfb058347bc3	2	CLINICAL	R2
301	34	False deterioration indication	False deterioration indication	5	\N	f	f	f	f	f	f	99	f	2026-07-24 12:34:23.237325	2026-07-24 15:21:14.311686	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	3	CLINICAL	R2
265	33	Longitudinal patient data is exposed	Longitudinal patient data is exposed	8	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	PRIVACY	R13
35	6	Supply chain attack	Supply chain attack	20	\N	f	f	f	f	f	f	6	f	2026-02-04 00:08:18.861712	2026-07-01 18:26:02.497321	c89552dc-420a-4459-9004-216cf107f7ac	3	SUPPLY_CHAIN	R2
147	26	Adversarial attack on medical imaging AI	Exploit the fact that AI models are vulnerable to adversarial perturbations in input images.	0	\N	f	f	f	f	f	f	6	f	2026-06-29 07:38:14.934245	2026-07-01 18:26:02.497321	fbe56779-c539-4b9d-9593-1a8e27bec752	2	CYBER_PHYSICAL	R2
77	30	Missed aortic aneurysm due to image quality degradation	Missed aortic aneurysm due to image quality degradation	15	\N	f	f	f	f	f	f	97	f	2026-06-25 11:26:09.752451	2026-07-05 12:00:40.034632	698fb6b6-c1e3-4340-b599-cfb058347bc3	2	CLINICAL	R1
164	31	Missed aortic aneurysm due to image quality degradation	Poor image quality may result in a misdiagnosis of patient	15	\N	f	f	f	f	f	f	97	f	2026-06-29 08:32:25.672864	2026-07-05 12:16:45.010982	fbe56779-c539-4b9d-9593-1a8e27bec752	6	CLINICAL	R1
165	31	Adversarial attack on medical imaging AI	Exploit the fact that AI models are vulnerable to adversarial perturbations in input images.	8	\N	f	t	f	f	f	f	94	f	2026-06-29 08:32:25.672864	2026-07-05 12:16:58.269295	fbe56779-c539-4b9d-9593-1a8e27bec752	5	MODEL	R2
1	1	Unauthorized Remote Control	An attacker gains unauthorized access to the system control interface.	3	Silent experiment corruption and large-scale experiment loss.	t	f	t	f	t	t	0	f	2026-01-12 12:41:32.484388	2026-07-05 12:15:34.699721	0df7bb6b-ae68-4b9d-84b7-1f6dc24a1522	2	\N	T2
2	1	Data Manipulation or Integrity Loss	Sensor readings or experiment data are altered or falsified.	3	Invalid scientific conclusions and regulatory exposure.	f	t	t	t	f	f	0	f	2026-01-12 12:41:32.484388	2026-07-05 12:15:34.699721	9e4d617f-e697-4737-8ccb-ae8e920b7ea9	2	\N	T3
79	30	Unauthorized modification of production AI model	Unauthorized modification of production AI model	8	\N	f	f	f	f	f	f	0	f	2026-06-25 11:26:09.752451	2026-07-05 12:15:34.699721	698fb6b6-c1e3-4340-b599-cfb058347bc3	1	CYBER	R3
253	33	Inaccurate LAP measurement due to drift or algorithm error	Inaccurate LAP measurement due to drift or algorithm error	12	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CLINICAL	R1
259	33	Monitoring platform unavailable during clinical use	Monitoring platform unavailable during clinical use	12	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	OPERATIONAL	R7
262	33	Implant identity spoofing or replay of measurements	Implant identity spoofing or replay of measurements	5	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CYBER	R10
258	33	Unauthorized access to clinical monitoring APIs	Unauthorized access to clinical monitoring APIs	10	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	PRIVACY	R6
255	33	Patient guidance uses corrupted or stale pressure data	Patient guidance uses corrupted or stale pressure data	8	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CLINICAL	R3
257	33	Patient, implant, or monitoring session associated incorrectly	Patient, implant, or monitoring session associated incorrectly	7	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	OPERATIONAL	R5
263	33	Long-term implant or sensor degradation is not detected	Long-term implant or sensor degradation is not detected	8	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CLINICAL	R11
261	33	Cybersecurity evidence is insufficient for regulatory review	Cybersecurity evidence is insufficient for regulatory review	9	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	REGULATORY	R9
269	33	False elevated pressure results in unnecessary treatment	False elevated pressure results in unnecessary treatment	11	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CLINICAL	R17
256	33	Unauthorized firmware or software modification	Unauthorized firmware or software modification	5	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CYBER	R4
268	33	Security vulnerabilities remain unremediated after implantation	Security vulnerabilities remain unremediated after implantation	6	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	CYBER	R16
260	33	CI/CD or software supply-chain compromise	CI/CD or software supply-chain compromise	4	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	SUPPLYCHAIN	R8
231	32	Physiological monitoring unavailable	Physiological monitoring unavailable	7	\N	f	f	f	f	f	f	99	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R8
229	32	Sleep and movement classification inaccurate	Sleep and movement classification inaccurate	10	\N	f	f	f	f	f	f	99	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CLINICAL	R6
230	32	Patient associated with incorrect monitoring session	Patient associated with incorrect monitoring session	5	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R7
270	33	Cyber incident disrupts an active clinical study	Cyber incident disrupts an active clinical study	5	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	REGULATORY	R18
303	34	Bed-exit event not detected	Bed-exit event not detected	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 15:20:46.033486	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CLINICAL	R4
254	33	Wireless power or communication failure prevents a reading	Wireless power or communication failure prevents a reading	15	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	OPERATIONAL	R2
304	34	False bed-exit notification	False bed-exit notification	3	\N	f	f	f	f	f	f	90	f	2026-07-24 12:34:23.237325	2026-07-24 15:21:28.782737	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	3	CLINICAL	R5
264	33	Third-party cloud or mobile dependency is compromised	Third-party cloud or mobile dependency is compromised	7	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	SUPPLYCHAIN	R12
267	33	Audit trail cannot reconstruct measurements and treatment decisions	Audit trail cannot reconstruct measurements and treatment decisions	6	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	REGULATORY	R15
266	33	Manufacturing or calibration variation changes measurement accuracy	Manufacturing or calibration variation changes measurement accuracy	10	\N	f	f	f	f	f	f	100	f	2026-07-20 21:18:43.837738	2026-07-20 21:18:43.837738	124cd230-f665-4926-b037-8388d842fafb	2	OPERATIONAL	R14
307	34	Physiological monitoring unavailable	Physiological monitoring unavailable	7	\N	f	f	f	f	f	f	99	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R8
311	34	Clinical workflow disrupted by system integration failure	Clinical workflow disrupted by system integration failure	8	\N	f	f	f	f	f	f	99	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R12
300	34	Early physiological deterioration not detected	Early physiological deterioration not detected	14	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CLINICAL	R1
305	34	Sleep and movement classification inaccurate	Sleep and movement classification inaccurate	10	\N	f	f	f	f	f	f	99	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CLINICAL	R6
327	34	BioT system -Infrastructure Supply Chain Failure / Compromise	A malicious compromise or sudden operational outage of the upstream IoT platform provider (BioT Medical / AWS) corrupts the device management pipeline or completely halts clinical data delivery.	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	SUPPLYCHAIN	R28
315	34	Device identity spoofed	Device identity spoofed	5	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R17
323	34	Cloud service dependency failure interrupts monitoring	Cloud service dependency failure interrupts monitoring	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R24A
306	34	Patient associated with incorrect monitoring session	Patient associated with incorrect monitoring session	5	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R7
328	34	Upstream Supply Chain Phishing	As seen in recent trends hitting other medical device software and robotics companies, the highest-probability entry point is rarely a zero-day exploit in the platform's code. Instead, it is an attacker phishing a BioT engineer or cloud administrator to steal credentials, gaining access to the AWS console to manipulate database configurations or software update hooks.	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	SUPPLYCHAIN	R29
321	34	CI/CD pipeline compromise deploys malicious software	CI/CD pipeline compromise deploys malicious software	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R23
324	34	Message queue saturation delays clinical events	Message queue saturation delays clinical events	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R25
317	34	Unauthorized access to patient monitoring APIs	Unauthorized access to patient monitoring APIs	8	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R19
309	34	Physiological measurements exposed to unauthorized parties	Physiological measurements exposed to unauthorized parties	10	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	PRIVACY	R10
326	34	Sensor configuration modified without authorization	Sensor configuration modified without authorization	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R27
314	34	Malicious firmware installed on patient monitoring sensor	Malicious firmware installed on patient monitoring sensor	4	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R16
308	34	Unauthorized modification of physiological processing software	Unauthorized modification of physiological processing software	4	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R9
318	34	Clinician portal privilege escalation	Clinician portal privilege escalation	5	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R20
316	34	Replay of physiological measurements	Replay of physiological measurements	4	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R18
319	34	Session hijacking of clinical users	Session hijacking of clinical users	6	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R21
310	34	Sensor measurements intentionally manipulated	Sensor measurements intentionally manipulated	3	\N	f	f	f	f	f	f	99	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R11
325	34	Storage exhaustion prevents physiological data recording	Storage exhaustion prevents physiological data recording	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	OPERATIONAL	R26
313	34	Audit evidence insufficient for regulatory investigation	Audit evidence insufficient for regulatory investigation	5	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	REGULATORY	R15
302	34	Contactless physiological measurements become inaccurate	Contactless physiological measurements become inaccurate	10	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CLINICAL	R3
322	34	Cloud denial-of-service interrupts continuous monitoring	Cloud denial-of-service interrupts continuous monitoring	3	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	CYBER	R24
320	34	Supply chain compromise introduces vulnerable software	Supply chain compromise introduces vulnerable software	5	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	SUPPLYCHAIN	R22
312	34	Security vulnerabilities remain unremediated after deployment	Security vulnerabilities remain unremediated after deployment	6	\N	f	f	f	f	f	f	100	f	2026-07-24 12:34:23.237325	2026-07-24 12:34:23.237325	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	2	REGULATORY	R14
235	32	Clinical workflow disrupted by system integration failure	Clinical workflow disrupted by system integration failure	8	\N	f	f	f	f	f	f	99	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R12
224	32	Early physiological deterioration not detected	Early physiological deterioration not detected	14	\N	t	f	t	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	9	CLINICAL	R1
239	32	Device identity spoofed	Device identity spoofed	5	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R17
247	32	Cloud service dependency failure interrupts monitoring	Cloud service dependency failure interrupts monitoring	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R24A
252	32	Upstream Supply Chain Phishing	As seen in recent trends hitting other medical device software and robotics companies, the highest-probability entry point is rarely a zero-day exploit in the platform's code. Instead, it is an attacker phishing a BioT engineer or cloud administrator to steal credentials, gaining access to the AWS console to manipulate database configurations or software update hooks.	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	SUPPLYCHAIN	R29
245	32	CI/CD pipeline compromise deploys malicious software	CI/CD pipeline compromise deploys malicious software	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R23
248	32	Message queue saturation delays clinical events	Message queue saturation delays clinical events	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R25
241	32	Unauthorized access to patient monitoring APIs	Unauthorized access to patient monitoring APIs	8	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R19
233	32	Physiological measurements exposed to unauthorized parties	Physiological measurements exposed to unauthorized parties	10	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	5	PRIVACY	R10
250	32	Sensor configuration modified without authorization	Sensor configuration modified without authorization	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R27
238	32	Malicious firmware installed on patient monitoring sensor	Malicious firmware installed on patient monitoring sensor	4	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R16
232	32	Unauthorized modification of physiological processing software	Unauthorized modification of physiological processing software	4	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R9
242	32	Clinician portal privilege escalation	Clinician portal privilege escalation	5	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R20
240	32	Replay of physiological measurements	Replay of physiological measurements	4	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R18
243	32	Session hijacking of clinical users	Session hijacking of clinical users	6	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R21
234	32	Sensor measurements intentionally manipulated	Sensor measurements intentionally manipulated	3	\N	f	f	f	f	f	f	99	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	5	CYBER	R11
249	32	Storage exhaustion prevents physiological data recording	Storage exhaustion prevents physiological data recording	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	OPERATIONAL	R26
237	32	Audit evidence insufficient for regulatory investigation	Audit evidence insufficient for regulatory investigation	5	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	5	REGULATORY	R15
246	32	Cloud denial-of-service interrupts continuous monitoring	Cloud denial-of-service interrupts continuous monitoring	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	CYBER	R24
244	32	Supply chain compromise introduces vulnerable software	Supply chain compromise introduces vulnerable software	5	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	SUPPLYCHAIN	R22
236	32	Security vulnerabilities remain unremediated after deployment	Security vulnerabilities remain unremediated after deployment	6	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	REGULATORY	R14
251	32	BioT system -Infrastructure Supply Chain Failure / Compromise.	A malicious compromise or sudden operational outage of the upstream IoT platform provider (BioT Medical / AWS) corrupts the device management pipeline or completely halts clinical data delivery.	3	\N	f	f	f	f	f	f	100	f	2026-06-29 09:16:34.368546	2026-07-24 12:32:04.656549	5fd73f86-1179-4fcb-a1c7-fd9b81a0e160	4	SUPPLYCHAIN	R28
\.


--
-- Data for Name: vulnerabilities; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.vulnerabilities (id, model_id, name, description, disabled, created_at, updated_at, version, tag) FROM stdin;
1	1	Weak Authentication	Single-factor or poorly enforced authentication for remote access.	f	2026-01-18 12:13:57.418647+02	2026-07-24 15:02:52.662461+03	2	V1
2	1	No Control/Data Plane Segmentation	Control logic and data systems share the same trust boundary.	f	2026-01-18 12:13:57.418647+02	2026-07-24 15:02:52.662461+03	2	V2
3	1	Unvalidated Control Commands	Control commands are accepted without bounds or sanity checks.	f	2026-01-18 12:13:57.418647+02	2026-07-24 15:02:52.662461+03	2	V3
4	1	Insufficient Audit Logging	Actions are not fully logged with actor and timestamp.	f	2026-01-18 12:13:57.418647+02	2026-07-24 15:02:52.662461+03	2	V4
5	1	Network Dependency	System behavior degrades or fails on network loss.	f	2026-01-18 12:13:57.418647+02	2026-07-24 15:02:52.662461+03	2	V5
6	1	V1	V1	f	2026-02-03 11:05:37.745202+02	2026-07-24 15:02:52.662461+03	2	V6
7	11	No authentication required	System accepts connections without authentication	f	2026-02-03 21:49:06.104273+02	2026-07-24 15:02:52.662461+03	2	V7
8	11	Weak password policy	Default passwords not enforced to change	f	2026-02-03 21:49:06.104273+02	2026-07-24 15:02:52.662461+03	2	V8
9	14	No authentication required	System accepts connections without authentication	f	2026-02-03 21:49:31.246303+02	2026-07-24 15:02:52.662461+03	2	V9
10	14	Weak password policy	Default passwords not enforced to change	f	2026-02-03 21:49:31.246303+02	2026-07-24 15:02:52.662461+03	2	V10
32	6	No password required	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V32
33	6	PLC and sensor firmware integrity	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V33
189	32	Single Point of Failure (SPOF) Dependency	The system architecture relies entirely on a single platform vendor (BioT) without a dynamic failover cloud or local on-premise fallback mesh.	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	2	V189
190	32	Implicit Trust in Upstream Code Signing	The edge device accepts and executes firmware updates or configuration files pushed from the cloud registry without an independent, secondary validation layer.	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	2	V190
191	32	Shared Infrastructure Risk (Multi-tenancy)	Weak logical isolation at the PaaS layer could allow a compromise of another BioT customer to cascade into Neteera's data silos.	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	2	V191
193	33	Sensor drift, calibration bias, signal-processing defects, environmental variation, or algorithm errors produce a left atrial pressure value that appears technically valid but does not represent the patient’s true physiological state.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V193
194	33	Implant-reader misalignment, insufficient wireless power transfer, interference, external reader failure, network loss, or communication protocol errors prevent the system from obtaining or transmitting a reliable LAP measurement.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V194
195	33	The patient self-management application generates guidance using delayed, duplicated, incomplete, corrupted, or clinically invalid LAP measurements, potentially causing inappropriate medication adjustment or delayed escalation.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V195
196	33	Unauthorized or unintended changes to implant firmware, embedded software, reader software, mobile applications, cloud services, or clinical web clients alter how the implant is powered, interrogated, interpreted, or presented.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V196
197	33	Enrollment, pairing, account provisioning, device replacement, clinical-site workflow, or data-integration errors associate measurements or guidance with the wrong patient, implant, reader, or monitoring session.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V197
198	33	Weak authentication, authorization, tenant isolation, token handling, or API design allows unauthorized parties to access patient measurements, clinical functions, treatment guidance, or administrative capabilities.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V198
199	33	Cloud, identity, database, messaging, mobile, web, or network failures interrupt access to measurements, patient guidance, physician monitoring, or study operations.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V199
200	33	Compromised source repositories, developer credentials, build systems, third-party packages, artifact repositories, or release infrastructure introduce malicious or vulnerable software into the V-LAP system.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V200
201	33	The security risk-management file does not demonstrate traceability from architecture and threats to vulnerabilities, controls, verification evidence, residual risk, and post-market processes.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V201
202	33	Weak device identity, key protection, freshness validation, or mutual authentication allows fabricated, substituted, or previously captured measurements to be accepted as current data from a legitimate implant.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V202
34	6	Unrestricted physical access	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V34
35	6	Shared credentials / technician mode persistence	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V35
36	6	Physical access to system in hospital Cath lab	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V36
37	6	USB access without authentication	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V37
38	6	Hard-coded and shared passwords in CODESYS	\N	f	2026-02-04 00:08:18.861712+02	2026-07-24 15:02:52.662461+03	2	V38
39	6	No password required to change the preset by the operator	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V39
40	6	Asset operational integrity may be compromised between manufacturing and hospital	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V40
41	6	The power cable may be disconnected by mistake	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V41
42	6	Field service share maintenance credentials	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V42
43	6	People have physical access to electrophysiology lab	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V43
44	6	After physical access is obtained to the USB maintenance port, additional user authentication is not performed	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V44
45	6	Support station field service access uses hard-coded and shared passwords	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V45
46	6	CODESYS runtime in deployed system may have unpatched issues	\N	f	2026-02-15 14:54:51.345536+02	2026-07-24 15:02:52.662461+03	2	V46
67	25	People have physical access to IR lab	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V67
71	27	Low-quality CTA images	May reduce segmentation accuracy	f	2026-06-25 10:42:18.19003+03	2026-07-24 15:02:52.662461+03	2	V71
72	27	Model not robust to perturbations	AI vulnerable to adversarial inputs	f	2026-06-25 10:42:18.19003+03	2026-07-24 15:02:52.662461+03	2	V72
73	29	Low-quality CTA images may reduce segmentation and detection accuracy.	\N	f	2026-06-25 11:05:26.979986+03	2026-07-24 15:02:52.662461+03	2	V73
74	29	AI models vulnerable to adversarial perturbations in input images.	\N	f	2026-06-25 11:05:26.979986+03	2026-07-24 15:02:52.662461+03	2	V74
75	30	Low-quality CTA images may reduce segmentation and detection accuracy.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V75
76	30	Model fails to identify dissection flap in atypical anatomy.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V76
77	30	Administrative access permits deployment of altered model versions.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V77
78	30	Compromised endpoint enables ransomware propagation into cloud operations.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V78
79	30	Cloud storage bucket may be misconfigured and publicly accessible.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V79
80	30	Research or model-training activities may exceed authorized consent scope.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V80
81	30	DICOM metadata mismatch during ingestion or processing.	\N	f	2026-06-25 11:26:09.752451+03	2026-07-24 15:02:52.662461+03	2	V81
82	26	Low-quality CTA images may reduce segmentation and detection accuracy.	\N	f	2026-06-29 07:38:14.934245+03	2026-07-24 15:02:52.662461+03	2	V82
83	26	AI models vulnerable to adversarial perturbations in input images.	\N	f	2026-06-29 07:38:14.934245+03	2026-07-24 15:02:52.662461+03	2	V83
98	31	Low-quality CTA images may reduce segmentation and detection accuracy.	\N	f	2026-06-29 08:32:25.672864+03	2026-07-24 15:02:52.662461+03	2	V98
99	31	AI models vulnerable to adversarial perturbations in input images.	\N	f	2026-06-29 08:32:25.672864+03	2026-07-24 15:02:52.662461+03	2	V99
84	25	Low-quality CTA images may reduce segmentation and detection accuracy.	\N	f	2026-06-29 07:59:04.993739+03	2026-07-24 15:02:52.662461+03	4	V84
85	25	AI models vulnerable to adversarial perturbations in input images.	\N	f	2026-06-29 07:59:04.993739+03	2026-07-24 15:02:52.662461+03	4	V85
63	25	No password required to change the preset by the operator	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V63
64	25	PLC, sensors integrity may be compromised between manufacturing and hospital	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V64
65	25	The power cable may be disconnected by mistake	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V65
66	25	Field service may share maintenance password with an attacker or didn't log out of technician mode	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V66
94	25	People have physical access to electrophysiology lab	\N	f	2026-06-29 08:23:40.678248+03	2026-07-24 15:02:52.662461+03	2	V94
68	25	After physical access is obtained to the USB maintenance port, additional user authentication is not performed	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V68
69	25	Attacker may gain access to maintenance password	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V69
70	25	CODESYS runtime in deployed system may have unpatched issues	\N	f	2026-02-15 17:12:40.11863+02	2026-07-24 15:02:52.662461+03	3	V70
203	33	Material aging, encapsulation, mechanical stress, biological environment, electronic drift, or long-term changes in wireless coupling degrade implant performance without timely detection.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V203
204	33	A compromise or material outage affecting a cloud, mobile operating system, notification, identity, analytics, hosting, or software supplier exposes data or interrupts critical V-LAP services.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V204
170	32	Compromised software deployment alters physiological calculations or movement classification.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V170
205	33	Weak access control, encryption, key management, data minimization, cloud configuration, logging, or endpoint protection exposes longitudinal LAP measurements, patient activity, treatment guidance, or study information.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V205
206	33	Material, component, assembly, packaging, calibration, test, sterilization, or supplier variation shifts device performance outside the validated measurement envelope.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V206
207	33	Logs lack synchronized time, device and software version, measurement provenance, user activity, guidance rationale, acknowledgement, or tamper resistance required to reconstruct a clinical or security event.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V207
208	33	The product cannot identify, assess, communicate, mitigate, or safely remediate newly disclosed vulnerabilities across implanted, external, mobile, cloud, web, and third-party components over the supported lifetime.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V208
209	33	Noise, drift, calibration error, transient physiology, data-processing defects, or incorrect interpretation produces an elevated LAP value that triggers unnecessary medication change, patient anxiety, or clinical intervention.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V209
210	33	Ransomware, account compromise, data corruption, service outage, or loss of study evidence interrupts enrollment, monitoring, patient guidance, safety reporting, data integrity, or regulatory timelines.	\N	f	2026-07-20 21:18:43.837738+03	2026-07-24 15:02:52.662461+03	2	V210
162	32	Reduced signal quality caused by patient movement, body position, blankets, distance from the sensor, or environmental interference degrades continuous physiological measurements and delays recognition of deterioration.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V162
163	32	Motion artifacts or environmental interference produce measurements suggesting deterioration where none exists, increasing unnecessary clinical intervention and alarm fatigue.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V163
164	32	Performance may drift outside of validated operating ranges and reduce measurement accuracy.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V164
165	32	Movement classification fails to recognize bed exit because of occlusion, unusual movement patterns, or degraded sensor observations.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V165
166	32	Normal patient movement is incorrectly classified as bed exit, creating unnecessary caregiver workload.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V166
167	32	Movement classification algorithms misclassify sleep state or patient positioning.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V167
168	32	Incorrect patient association attributes physiological measurements to the wrong patient.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V168
169	32	Infrastructure failure, software failure, or network disruption interrupts continuous monitoring.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V169
171	32	Weak authentication, authorization, or encryption exposes patient monitoring information.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V171
172	32	Malicious manipulation or spoofing of physiological signals results in incorrect measurements presented to clinicians.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V172
173	32	Failure to exchange monitoring information reliably with hospital systems delays clinical workflows.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V173
174	32	Failure to identify, assess, prioritize, and remediate cybersecurity vulnerabilities throughout the product lifecycle.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V174
175	32	Audit logs do not provide sufficient evidence to reconstruct system behavior, software versions, user activity, or clinical events.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V175
176	32	The device accepts unauthorized firmware because of weak code-signing verification, insecure boot, or firmware rollback vulnerabilities, allowing physiological measurements or movement classifications to be manipulated.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V176
177	32	Weak device authentication allows an attacker to impersonate a legitimate monitoring device and inject fabricated physiological measurements into the monitoring platform.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V177
178	32	Captured physiological data are replayed because communication protocols lack freshness validation or replay protection.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V178
179	32	Weak API authentication or authorization permits unauthorized access to patient monitoring data or monitoring functions.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V179
180	32	Authorization weaknesses allow users to obtain privileges beyond their intended clinical role.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V180
181	32	Weak session management permits attackers to reuse authenticated clinician sessions.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V181
182	32	Compromised third-party software components or build dependencies introduce exploitable vulnerabilities into production systems.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V182
183	32	Compromise of development infrastructure enables unauthorized software deployment into production environments.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V183
184	32	Network or application-layer denial-of-service attacks exhaust cloud resources and interrupt monitoring services.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V184
185	32	Failure of cloud identity, messaging, storage, notification, or monitoring services interrupts delivery of patient monitoring information.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V185
186	32	Backlog within event-processing infrastructure delays delivery of physiological measurements and clinical notifications.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V186
187	32	Insufficient storage capacity or storage failures prevent recording of physiological measurements and audit evidence.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V187
188	32	Unauthorized modification of sensor calibration, operating parameters, or detection thresholds alters physiological measurements and behavioral monitoring.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V188
238	32	VULN-S1: Single Point of Failure (SPOF) Dependency	The system architecture relies entirely on a single platform vendor (BioT) without a dynamic failover cloud or local on-premise fallback mesh.	f	2026-07-24 12:32:04.656549+03	2026-07-24 15:02:52.662461+03	2	V238
239	32	VULN-S2: Implicit Trust in Upstream Code Signing	The edge device accepts and executes firmware updates or configuration files pushed from the cloud registry without an independent, secondary validation layer.	f	2026-07-24 12:32:04.656549+03	2026-07-24 15:02:52.662461+03	2	V239
240	32	VULN-S3: Shared Infrastructure Risk (Multi-tenancy)	Weak logical isolation at the PaaS layer could allow a compromise of another BioT customer to cascade into Neteera's data silos.	f	2026-07-24 12:32:04.656549+03	2026-07-24 15:02:52.662461+03	2	V240
192	32	Compromised credentials from a BioT engineer or cloud administrator allow attackers to manipulate database configurations or software update hooks in the AWS console.	\N	f	2026-06-29 09:16:34.368546+03	2026-07-24 15:02:52.662461+03	3	V192
242	34	Reduced signal quality caused by patient movement, body position, blankets, distance from the sensor, or environmental interference degrades continuous physiological measurements and delays recognition of deterioration.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V242
243	34	Motion artifacts or environmental interference produce measurements suggesting deterioration where none exists, increasing unnecessary clinical intervention and alarm fatigue.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V243
244	34	Performance may drift outside of validated operating ranges and reduce measurement accuracy.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V244
245	34	Movement classification fails to recognize bed exit because of occlusion, unusual movement patterns, or degraded sensor observations.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V245
246	34	Normal patient movement is incorrectly classified as bed exit, creating unnecessary caregiver workload.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V246
247	34	Movement classification algorithms misclassify sleep state or patient positioning.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V247
248	34	Incorrect patient association attributes physiological measurements to the wrong patient.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V248
249	34	Infrastructure failure, software failure, or network disruption interrupts continuous monitoring.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V249
250	34	Compromised software deployment alters physiological calculations or movement classification.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V250
251	34	Weak authentication, authorization, or encryption exposes patient monitoring information.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V251
252	34	Malicious manipulation or spoofing of physiological signals results in incorrect measurements presented to clinicians.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V252
253	34	Failure to exchange monitoring information reliably with hospital systems delays clinical workflows.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V253
254	34	Failure to identify, assess, prioritize, and remediate cybersecurity vulnerabilities throughout the product lifecycle.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V254
255	34	Audit logs do not provide sufficient evidence to reconstruct system behavior, software versions, user activity, or clinical events.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V255
256	34	The device accepts unauthorized firmware because of weak code-signing verification, insecure boot, or firmware rollback vulnerabilities, allowing physiological measurements or movement classifications to be manipulated.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V256
257	34	Weak device authentication allows an attacker to impersonate a legitimate monitoring device and inject fabricated physiological measurements into the monitoring platform.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V257
258	34	Captured physiological data are replayed because communication protocols lack freshness validation or replay protection.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V258
259	34	Weak API authentication or authorization permits unauthorized access to patient monitoring data or monitoring functions.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V259
260	34	Authorization weaknesses allow users to obtain privileges beyond their intended clinical role.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V260
261	34	Weak session management permits attackers to reuse authenticated clinician sessions.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V261
262	34	Compromised third-party software components or build dependencies introduce exploitable vulnerabilities into production systems.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V262
263	34	Compromise of development infrastructure enables unauthorized software deployment into production environments.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V263
264	34	Network or application-layer denial-of-service attacks exhaust cloud resources and interrupt monitoring services.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V264
265	34	Failure of cloud identity, messaging, storage, notification, or monitoring services interrupts delivery of patient monitoring information.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V265
266	34	Backlog within event-processing infrastructure delays delivery of physiological measurements and clinical notifications.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V266
267	34	Insufficient storage capacity or storage failures prevent recording of physiological measurements and audit evidence.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V267
268	34	Unauthorized modification of sensor calibration, operating parameters, or detection thresholds alters physiological measurements and behavioral monitoring.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V268
269	34	Single Point of Failure (SPOF) Dependency	The system architecture relies entirely on a single platform vendor (BioT) without a dynamic failover cloud or local on-premise fallback mesh.	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V269
270	34	Implicit Trust in Upstream Code Signing	The edge device accepts and executes firmware updates or configuration files pushed from the cloud registry without an independent, secondary validation layer.	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V270
271	34	Shared Infrastructure Risk (Multi-tenancy)	Weak logical isolation at the PaaS layer could allow a compromise of another BioT customer to cascade into Neteera's data silos.	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V271
272	34	Compromised credentials from a BioT engineer or cloud administrator allow attackers to manipulate database configurations or software update hooks in the AWS console.	\N	f	2026-07-24 12:34:23.237325+03	2026-07-24 15:02:52.662461+03	2	V272
\.


--
-- Data for Name: vulnerability_threat; Type: TABLE DATA; Schema: threat; Owner: pattern_factory
--

COPY threat.vulnerability_threat (model_id, vulnerability_id, threat_id) FROM stdin;
6	32	34
6	33	35
6	34	36
6	35	37
6	36	38
6	37	39
6	38	40
6	39	34
6	40	35
6	41	36
6	42	37
6	43	38
6	44	39
6	45	40
6	46	48
25	63	65
25	64	66
25	65	67
25	66	68
25	67	69
25	68	70
25	69	71
25	70	72
27	71	73
27	72	74
29	73	75
29	74	76
30	75	77
30	76	78
30	77	79
30	78	80
30	79	81
30	80	82
30	81	83
26	82	146
26	83	147
25	84	65
25	85	66
25	94	69
31	98	164
31	99	165
32	162	224
32	163	225
32	164	226
32	165	227
32	166	228
32	167	229
32	168	230
32	169	231
32	170	232
32	171	233
32	172	234
32	173	235
32	174	236
32	175	237
32	176	238
32	177	239
32	178	240
32	179	241
32	180	242
32	181	243
32	182	244
32	183	245
32	184	246
32	185	247
32	186	248
32	187	249
32	188	250
32	189	251
32	190	251
32	191	251
32	192	252
33	193	253
33	194	254
33	195	255
33	196	256
33	197	257
33	198	258
33	199	259
33	200	260
33	201	261
33	202	262
33	203	263
33	204	264
33	205	265
33	206	266
33	207	267
33	208	268
33	209	269
33	210	270
32	239	251
32	240	251
32	238	251
34	242	300
34	243	301
34	244	302
34	245	303
34	246	304
34	247	305
34	248	306
34	249	307
34	250	308
34	251	309
34	252	310
34	253	311
34	254	312
34	255	313
34	256	314
34	257	315
34	258	316
34	259	317
34	260	318
34	261	319
34	262	320
34	263	321
34	264	322
34	265	323
34	266	324
34	267	325
34	268	326
34	269	327
34	270	327
34	271	327
34	272	328
\.


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.categories_id_seq', 3, true);


--
-- Name: guests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.guests_id_seq', 36, true);


--
-- Name: orgs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.orgs_id_seq', 44, true);


--
-- Name: paths_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.paths_id_seq', 4, true);


--
-- Name: patterns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.patterns_id_seq', 54, true);


--
-- Name: posts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.posts_id_seq', 37, true);


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.roles_id_seq', 3, true);


--
-- Name: system_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.system_log_id_seq', 1, false);


--
-- Name: views_registry_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pattern_factory
--

SELECT pg_catalog.setval('public.views_registry_id_seq', 94, true);


--
-- Name: areas_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.areas_id_seq', 1, false);


--
-- Name: assets_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.assets_id_seq', 283, true);


--
-- Name: attacker_types_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.attacker_types_id_seq', 1, false);


--
-- Name: countermeasures_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.countermeasures_id_seq', 728, true);


--
-- Name: entrypoints_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.entrypoints_id_seq', 1, false);


--
-- Name: parameters_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.parameters_id_seq', 1, false);


--
-- Name: projects_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.projects_id_seq', 34, true);


--
-- Name: threats_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.threats_id_seq', 328, true);


--
-- Name: vulnerabilities_id_seq; Type: SEQUENCE SET; Schema: threat; Owner: pattern_factory
--

SELECT pg_catalog.setval('threat.vulnerabilities_id_seq', 272, true);


--
-- Name: active_models active_models_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.active_models
    ADD CONSTRAINT active_models_pkey PRIMARY KEY (user_id);


--
-- Name: cards cards_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT cards_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: guests guests_name_unique; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.guests
    ADD CONSTRAINT guests_name_unique UNIQUE (name);


--
-- Name: guests guests_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.guests
    ADD CONSTRAINT guests_pkey PRIMARY KEY (id);


--
-- Name: orgs orgs_name_unique; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.orgs
    ADD CONSTRAINT orgs_name_unique UNIQUE (name);


--
-- Name: orgs orgs_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.orgs
    ADD CONSTRAINT orgs_pkey PRIMARY KEY (id);


--
-- Name: paths paths_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.paths
    ADD CONSTRAINT paths_pkey PRIMARY KEY (id);


--
-- Name: pattern_guest_link pattern_guest_link_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_guest_link
    ADD CONSTRAINT pattern_guest_link_pkey PRIMARY KEY (pattern_id, guest_id);


--
-- Name: pattern_org_link pattern_org_link_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_org_link
    ADD CONSTRAINT pattern_org_link_pkey PRIMARY KEY (pattern_id, org_id);


--
-- Name: pattern_post_link pattern_post_link_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_post_link
    ADD CONSTRAINT pattern_post_link_pkey PRIMARY KEY (pattern_id, post_id);


--
-- Name: patterns patterns_name_unique; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.patterns
    ADD CONSTRAINT patterns_name_unique UNIQUE (name);


--
-- Name: patterns patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.patterns
    ADD CONSTRAINT patterns_pkey PRIMARY KEY (id);


--
-- Name: posts posts_name_unique; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_name_unique UNIQUE (name);


--
-- Name: posts posts_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (id);


--
-- Name: rbac rbac_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.rbac
    ADD CONSTRAINT rbac_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: system_log system_log_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.system_log
    ADD CONSTRAINT system_log_pkey PRIMARY KEY (id);


--
-- Name: user_role user_role_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT user_role_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: views_registry views_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.views_registry
    ADD CONSTRAINT views_registry_pkey PRIMARY KEY (id);


--
-- Name: views_registry views_registry_table_name_key; Type: CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.views_registry
    ADD CONSTRAINT views_registry_table_name_key UNIQUE (table_name);


--
-- Name: area_asset area_asset_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_asset
    ADD CONSTRAINT area_asset_pkey PRIMARY KEY (model_id, area_id, asset_id);


--
-- Name: area_countermeasure area_countermeasure_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_countermeasure
    ADD CONSTRAINT area_countermeasure_pkey PRIMARY KEY (model_id, area_id, countermeasure_id);


--
-- Name: area_threat area_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_threat
    ADD CONSTRAINT area_threat_pkey PRIMARY KEY (model_id, area_id, threat_id);


--
-- Name: area_vulnerability area_vulnerability_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_vulnerability
    ADD CONSTRAINT area_vulnerability_pkey PRIMARY KEY (model_id, area_id, vulnerability_id);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);


--
-- Name: asset_threat asset_threat_model_ids_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.asset_threat
    ADD CONSTRAINT asset_threat_model_ids_unique UNIQUE (model_id, asset_id, threat_id);


--
-- Name: asset_threat asset_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.asset_threat
    ADD CONSTRAINT asset_threat_pkey PRIMARY KEY (model_id, asset_id, threat_id);


--
-- Name: assets assets_model_id_tag_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.assets
    ADD CONSTRAINT assets_model_id_tag_unique UNIQUE (model_id, tag);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: attacker_threat attacker_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.attacker_threat
    ADD CONSTRAINT attacker_threat_pkey PRIMARY KEY (model_id, attacker_type_id, threat_id);


--
-- Name: attacker_types attacker_types_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.attacker_types
    ADD CONSTRAINT attacker_types_pkey PRIMARY KEY (id);


--
-- Name: countermeasure_threat countermeasure_threat_model_ids_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasure_threat
    ADD CONSTRAINT countermeasure_threat_model_ids_unique UNIQUE (model_id, countermeasure_id, threat_id);


--
-- Name: countermeasure_threat countermeasure_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasure_threat
    ADD CONSTRAINT countermeasure_threat_pkey PRIMARY KEY (model_id, countermeasure_id, threat_id);


--
-- Name: countermeasures countermeasures_model_name_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasures
    ADD CONSTRAINT countermeasures_model_name_unique UNIQUE (model_id, name);


--
-- Name: countermeasures countermeasures_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasures
    ADD CONSTRAINT countermeasures_pkey PRIMARY KEY (id);


--
-- Name: entrypoint_threat entrypoint_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.entrypoint_threat
    ADD CONSTRAINT entrypoint_threat_pkey PRIMARY KEY (model_id, entrypoint_id, threat_id);


--
-- Name: entrypoints entrypoints_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.entrypoints
    ADD CONSTRAINT entrypoints_pkey PRIMARY KEY (id);


--
-- Name: parameters parameters_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.parameters
    ADD CONSTRAINT parameters_pkey PRIMARY KEY (id);


--
-- Name: models projects_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.models
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: risk_history risk_history_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.risk_history
    ADD CONSTRAINT risk_history_pkey PRIMARY KEY ("time", series);


--
-- Name: threats threats_model_tag_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.threats
    ADD CONSTRAINT threats_model_tag_unique UNIQUE (model_id, tag);


--
-- Name: threats threats_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.threats
    ADD CONSTRAINT threats_pkey PRIMARY KEY (id);


--
-- Name: vulnerabilities vulnerabilities_model_name_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerabilities
    ADD CONSTRAINT vulnerabilities_model_name_unique UNIQUE (model_id, name);


--
-- Name: vulnerabilities vulnerabilities_model_tag_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerabilities
    ADD CONSTRAINT vulnerabilities_model_tag_unique UNIQUE (model_id, tag);


--
-- Name: vulnerabilities vulnerabilities_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerabilities
    ADD CONSTRAINT vulnerabilities_pkey PRIMARY KEY (id);


--
-- Name: vulnerability_threat vulnerability_threat_model_ids_unique; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerability_threat
    ADD CONSTRAINT vulnerability_threat_model_ids_unique UNIQUE (model_id, vulnerability_id, threat_id);


--
-- Name: vulnerability_threat vulnerability_threat_pkey; Type: CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerability_threat
    ADD CONSTRAINT vulnerability_threat_pkey PRIMARY KEY (model_id, vulnerability_id, threat_id);


--
-- Name: idx_guests_active; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_guests_active ON public.guests USING btree (id) WHERE (deleted_at IS NULL);


--
-- Name: idx_guests_vector; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_guests_vector ON public.guests USING gin (to_tsvector('english'::regconfig, ((COALESCE(name, ''::text) || ' '::text) || COALESCE(description, ''::text))));


--
-- Name: idx_orgs_active; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_orgs_active ON public.orgs USING btree (id) WHERE (deleted_at IS NULL);


--
-- Name: idx_orgs_vector; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_orgs_vector ON public.orgs USING gin (to_tsvector('english'::regconfig, ((COALESCE(name, ''::text) || ' '::text) || COALESCE(description, ''::text))));


--
-- Name: idx_pattern_guest_link_guest; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_pattern_guest_link_guest ON public.pattern_guest_link USING btree (guest_id);


--
-- Name: idx_pattern_org_link_org; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_pattern_org_link_org ON public.pattern_org_link USING btree (org_id);


--
-- Name: idx_pattern_post_link_post; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_pattern_post_link_post ON public.pattern_post_link USING btree (post_id);


--
-- Name: idx_patterns_active; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_patterns_active ON public.patterns USING btree (id) WHERE (deleted_at IS NULL);


--
-- Name: idx_patterns_vector; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_patterns_vector ON public.patterns USING gin (search_vector);


--
-- Name: idx_posts_active; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_posts_active ON public.posts USING btree (id) WHERE (deleted_at IS NULL);


--
-- Name: idx_posts_vector; Type: INDEX; Schema: public; Owner: pattern_factory
--

CREATE INDEX idx_posts_vector ON public.posts USING gin (to_tsvector('english'::regconfig, ((COALESCE(name, ''::text) || ' '::text) || COALESCE(description, ''::text))));


--
-- Name: idx_areas_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_areas_project ON threat.areas USING btree (model_id);


--
-- Name: idx_assets_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_assets_project ON threat.assets USING btree (model_id);


--
-- Name: idx_countermeasures_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_countermeasures_project ON threat.countermeasures USING btree (model_id);


--
-- Name: idx_entrypoints_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_entrypoints_project ON threat.entrypoints USING btree (model_id);


--
-- Name: idx_threats_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_threats_project ON threat.threats USING btree (model_id);


--
-- Name: idx_vulnerabilities_project; Type: INDEX; Schema: threat; Owner: pattern_factory
--

CREATE INDEX idx_vulnerabilities_project ON threat.vulnerabilities USING btree (model_id);


--
-- Name: patterns trg_patterns_vector_update; Type: TRIGGER; Schema: public; Owner: pattern_factory
--

CREATE TRIGGER trg_patterns_vector_update BEFORE INSERT OR UPDATE ON public.patterns FOR EACH ROW EXECUTE FUNCTION public.patterns_vector_update();


--
-- Name: active_models update_active_models_updated_at; Type: TRIGGER; Schema: public; Owner: pattern_factory
--

CREATE TRIGGER update_active_models_updated_at BEFORE UPDATE ON public.active_models FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: cards update_cards_updated_at; Type: TRIGGER; Schema: public; Owner: pattern_factory
--

CREATE TRIGGER update_cards_updated_at BEFORE UPDATE ON public.cards FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: paths update_paths_updated_at; Type: TRIGGER; Schema: public; Owner: pattern_factory
--

CREATE TRIGGER update_paths_updated_at BEFORE UPDATE ON public.paths FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: patterns update_patterns_updated_at; Type: TRIGGER; Schema: public; Owner: pattern_factory
--

CREATE TRIGGER update_patterns_updated_at BEFORE UPDATE ON public.patterns FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: assets asset_compute_yearly_value; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER asset_compute_yearly_value BEFORE INSERT OR UPDATE ON threat.assets FOR EACH ROW EXECUTE FUNCTION threat.compute_asset_yearly_value();


--
-- Name: assets assets_increment_version; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER assets_increment_version BEFORE UPDATE ON threat.assets FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION threat.increment_version();


--
-- Name: countermeasures countermeasure_compute_yearly_cost; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER countermeasure_compute_yearly_cost BEFORE INSERT OR UPDATE ON threat.countermeasures FOR EACH ROW EXECUTE FUNCTION threat.compute_countermeasure_yearly_cost();


--
-- Name: countermeasures countermeasures_increment_version; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER countermeasures_increment_version BEFORE UPDATE ON threat.countermeasures FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION threat.increment_version();


--
-- Name: threats threats_increment_version; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER threats_increment_version BEFORE UPDATE ON threat.threats FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION threat.increment_version();


--
-- Name: countermeasures trg_countermeasure_impl_mitigation; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER trg_countermeasure_impl_mitigation AFTER UPDATE ON threat.countermeasures FOR EACH ROW WHEN (((old.implemented IS DISTINCT FROM new.implemented) OR (old.disabled IS DISTINCT FROM new.disabled))) EXECUTE FUNCTION threat.update_threat_mitigation_on_countermeasure_change();


--
-- Name: countermeasure_threat trg_countermeasure_threat_mitigation; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER trg_countermeasure_threat_mitigation AFTER INSERT OR DELETE OR UPDATE ON threat.countermeasure_threat FOR EACH ROW EXECUTE FUNCTION threat.update_threat_mitigation_on_countermeasure_change();


--
-- Name: threats trg_insert_threat_mitigation; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER trg_insert_threat_mitigation AFTER INSERT ON threat.threats FOR EACH ROW EXECUTE FUNCTION threat.update_threat_mitigation_level();


--
-- Name: threats trg_update_threat_mitigation; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER trg_update_threat_mitigation AFTER UPDATE ON threat.threats FOR EACH ROW EXECUTE FUNCTION threat.update_threat_mitigation_level();


--
-- Name: threats update_threats_updated_at; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER update_threats_updated_at BEFORE UPDATE ON threat.threats FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: vulnerabilities vulnerabilities_increment_version; Type: TRIGGER; Schema: threat; Owner: pattern_factory
--

CREATE TRIGGER vulnerabilities_increment_version BEFORE UPDATE ON threat.vulnerabilities FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION threat.increment_version();


--
-- Name: active_models active_models_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.active_models
    ADD CONSTRAINT active_models_model_id_fkey FOREIGN KEY (model_id) REFERENCES threat.models(id);


--
-- Name: active_models active_models_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.active_models
    ADD CONSTRAINT active_models_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: cards cards_pattern_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT cards_pattern_id_fkey FOREIGN KEY (pattern_id) REFERENCES public.patterns(id);


--
-- Name: guests guests_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.guests
    ADD CONSTRAINT guests_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id) ON DELETE SET NULL;


--
-- Name: orgs orgs_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.orgs
    ADD CONSTRAINT orgs_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE SET NULL;


--
-- Name: pattern_guest_link pattern_guest_link_guest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_guest_link
    ADD CONSTRAINT pattern_guest_link_guest_id_fkey FOREIGN KEY (guest_id) REFERENCES public.guests(id) ON DELETE CASCADE;


--
-- Name: pattern_guest_link pattern_guest_link_pattern_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_guest_link
    ADD CONSTRAINT pattern_guest_link_pattern_id_fkey FOREIGN KEY (pattern_id) REFERENCES public.patterns(id) ON DELETE CASCADE;


--
-- Name: pattern_org_link pattern_org_link_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_org_link
    ADD CONSTRAINT pattern_org_link_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id) ON DELETE CASCADE;


--
-- Name: pattern_org_link pattern_org_link_pattern_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_org_link
    ADD CONSTRAINT pattern_org_link_pattern_id_fkey FOREIGN KEY (pattern_id) REFERENCES public.patterns(id) ON DELETE CASCADE;


--
-- Name: pattern_post_link pattern_post_link_pattern_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_post_link
    ADD CONSTRAINT pattern_post_link_pattern_id_fkey FOREIGN KEY (pattern_id) REFERENCES public.patterns(id) ON DELETE CASCADE;


--
-- Name: pattern_post_link pattern_post_link_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.pattern_post_link
    ADD CONSTRAINT pattern_post_link_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE;


--
-- Name: rbac rbac_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.rbac
    ADD CONSTRAINT rbac_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: rbac rbac_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.rbac
    ADD CONSTRAINT rbac_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_role user_role_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT user_role_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: user_role user_role_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pattern_factory
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT user_role_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: area_asset area_asset_area_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_asset
    ADD CONSTRAINT area_asset_area_id_fkey FOREIGN KEY (area_id) REFERENCES threat.areas(id) ON DELETE CASCADE;


--
-- Name: area_asset area_asset_asset_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_asset
    ADD CONSTRAINT area_asset_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES threat.assets(id) ON DELETE CASCADE;


--
-- Name: area_countermeasure area_countermeasure_area_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_countermeasure
    ADD CONSTRAINT area_countermeasure_area_id_fkey FOREIGN KEY (area_id) REFERENCES threat.areas(id) ON DELETE CASCADE;


--
-- Name: area_countermeasure area_countermeasure_countermeasure_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_countermeasure
    ADD CONSTRAINT area_countermeasure_countermeasure_id_fkey FOREIGN KEY (countermeasure_id) REFERENCES threat.countermeasures(id) ON DELETE CASCADE;


--
-- Name: area_threat area_threat_area_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_threat
    ADD CONSTRAINT area_threat_area_id_fkey FOREIGN KEY (area_id) REFERENCES threat.areas(id) ON DELETE CASCADE;


--
-- Name: area_threat area_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_threat
    ADD CONSTRAINT area_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: area_vulnerability area_vulnerability_area_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_vulnerability
    ADD CONSTRAINT area_vulnerability_area_id_fkey FOREIGN KEY (area_id) REFERENCES threat.areas(id) ON DELETE CASCADE;


--
-- Name: area_vulnerability area_vulnerability_vulnerability_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.area_vulnerability
    ADD CONSTRAINT area_vulnerability_vulnerability_id_fkey FOREIGN KEY (vulnerability_id) REFERENCES threat.vulnerabilities(id) ON DELETE CASCADE;


--
-- Name: asset_threat asset_threat_asset_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.asset_threat
    ADD CONSTRAINT asset_threat_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES threat.assets(id) ON DELETE CASCADE;


--
-- Name: asset_threat asset_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.asset_threat
    ADD CONSTRAINT asset_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: attacker_threat attacker_threat_attacker_type_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.attacker_threat
    ADD CONSTRAINT attacker_threat_attacker_type_id_fkey FOREIGN KEY (attacker_type_id) REFERENCES threat.attacker_types(id);


--
-- Name: attacker_threat attacker_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.attacker_threat
    ADD CONSTRAINT attacker_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: countermeasure_threat countermeasure_threat_countermeasure_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasure_threat
    ADD CONSTRAINT countermeasure_threat_countermeasure_id_fkey FOREIGN KEY (countermeasure_id) REFERENCES threat.countermeasures(id) ON DELETE CASCADE;


--
-- Name: countermeasure_threat countermeasure_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.countermeasure_threat
    ADD CONSTRAINT countermeasure_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: entrypoint_threat entrypoint_threat_entrypoint_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.entrypoint_threat
    ADD CONSTRAINT entrypoint_threat_entrypoint_id_fkey FOREIGN KEY (entrypoint_id) REFERENCES threat.entrypoints(id) ON DELETE CASCADE;


--
-- Name: entrypoint_threat entrypoint_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.entrypoint_threat
    ADD CONSTRAINT entrypoint_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: risk_history risk_history_model_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.risk_history
    ADD CONSTRAINT risk_history_model_id_fkey FOREIGN KEY (model_id) REFERENCES threat.models(id);


--
-- Name: threats threats_card_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.threats
    ADD CONSTRAINT threats_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.cards(id);


--
-- Name: vulnerability_threat vulnerability_threat_threat_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerability_threat
    ADD CONSTRAINT vulnerability_threat_threat_id_fkey FOREIGN KEY (threat_id) REFERENCES threat.threats(id) ON DELETE CASCADE;


--
-- Name: vulnerability_threat vulnerability_threat_vulnerability_id_fkey; Type: FK CONSTRAINT; Schema: threat; Owner: pattern_factory
--

ALTER TABLE ONLY threat.vulnerability_threat
    ADD CONSTRAINT vulnerability_threat_vulnerability_id_fkey FOREIGN KEY (vulnerability_id) REFERENCES threat.vulnerabilities(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict QVPP7e5qHN8Wgzl9TtHtVB8XeztYOcNfVVqZ4L6WY586viyye0sENctCfNqBoRS

