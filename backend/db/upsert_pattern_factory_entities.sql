CREATE OR REPLACE PROCEDURE upsert_pattern_factory_entities(
    v_payload JSONB,
    OUT v_result JSONB
)
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