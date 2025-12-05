CREATE OR REPLACE FUNCTION upsert_pattern_factory_entities(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    org_rec      JSONB;
    guest_rec    JSONB;
    post_rec     JSONB;
    pattern_rec  JSONB;
    link_rec     JSONB;

    v_org_id     BIGINT;
    v_guest_id   BIGINT;
    v_post_id    BIGINT;
    v_pattern_id BIGINT;

    results JSONB := '{}'::jsonb;

BEGIN
    ---------------------------------------------------------------------
    -- 1. UPSERT ORGANIZATIONS
    ---------------------------------------------------------------------
    FOR org_rec IN SELECT * FROM jsonb_array_elements(payload->'orgs')
    LOOP
        INSERT INTO orgs (
            name,
            description,
            tech_keywords,
            content_url,
            content_source
        )
        VALUES (
            org_rec->>'name',
            org_rec->>'description',
            (org_rec->'tech_keywords')::text[],
            org_rec->>'content_url',
            org_rec->>'content_source'
        )
        ON CONFLICT (name)
        DO UPDATE SET
            description     = EXCLUDED.description,
            tech_keywords   = EXCLUDED.tech_keywords,
            content_url     = EXCLUDED.content_url,
            content_source  = EXCLUDED.content_source,
            updated_at      = NOW()
        RETURNING org_id INTO v_org_id;

        results := results || jsonb_build_object('last_org_id', v_org_id);
    END LOOP;


    ---------------------------------------------------------------------
    -- 2. UPSERT POSTS
    ---------------------------------------------------------------------
    FOR post_rec IN SELECT * FROM jsonb_array_elements(payload->'posts')
    LOOP
        INSERT INTO posts (
            name,
            description,
            keywords,
            content_url,
            content_source,
            published_at
        )
        VALUES (
            post_rec->>'name',
            post_rec->>'description',
            (post_rec->'keywords')::text[],
            post_rec->>'content_url',
            post_rec->>'content_source',
            NULLIF(post_rec->>'published_at','')::timestamp
        )
        ON CONFLICT (name)
        DO UPDATE SET
            description     = EXCLUDED.description,
            keywords        = EXCLUDED.keywords,
            content_url     = EXCLUDED.content_url,
            content_source  = EXCLUDED.content_source,
            updated_at      = NOW()
        RETURNING id INTO v_post_id;

        results := results || jsonb_build_object('last_post_id', v_post_id);
    END LOOP;


    ---------------------------------------------------------------------
    -- 3. UPSERT GUESTS
    ---------------------------------------------------------------------
    FOR guest_rec IN SELECT * FROM jsonb_array_elements(payload->'guests')
    LOOP
        INSERT INTO guests (
            name,
            description,
            job_description,
            org_id,
            content_url,
            content_source
        )
        VALUES (
            guest_rec->>'name',
            guest_rec->>'description',
            guest_rec->>'job_description',
            (SELECT org_id FROM orgs WHERE name = guest_rec->>'org_name' LIMIT 1),
            guest_rec->>'content_url',
            guest_rec->>'content_source'
        )
        ON CONFLICT (name)
        DO UPDATE SET
            description     = EXCLUDED.description,
            job_description = EXCLUDED.job_description,
            org_id          = EXCLUDED.org_id,
            content_url     = EXCLUDED.content_url,
            content_source  = EXCLUDED.content_source,
            updated_at      = NOW()
        RETURNING guest_id INTO v_guest_id;

        results := results || jsonb_build_object('last_guest_id', v_guest_id);
    END LOOP;


    ---------------------------------------------------------------------
    -- 4. UPSERT PATTERNS (Using name as natural key)
    ---------------------------------------------------------------------
    FOR pattern_rec IN SELECT * FROM jsonb_array_elements(payload->'patterns')
    LOOP
        INSERT INTO patterns (
            name,
            description,
            kind,
            keywords,
            metadata,
            highlights,
            content_source
        )
        VALUES (
            pattern_rec->>'name',
            pattern_rec->>'description',
            pattern_rec->>'kind',
            (pattern_rec->'keywords')::text[],
            COALESCE(pattern_rec->'metadata', '{}'::jsonb),
            COALESCE(pattern_rec->'highlights', '[]'::jsonb),
            pattern_rec->>'content_source'
        )
        ON CONFLICT (name)
        DO UPDATE SET
            description     = EXCLUDED.description,
            kind            = EXCLUDED.kind,
            keywords        = EXCLUDED.keywords,
            metadata        = EXCLUDED.metadata,
            highlights      = EXCLUDED.highlights,
            content_source  = EXCLUDED.content_source,
            updated_at      = NOW()
        RETURNING id INTO v_pattern_id;

        results := results || jsonb_build_object('last_pattern_id', v_pattern_id);
    END LOOP;


    ---------------------------------------------------------------------
    -- 5. PATTERN → POST LINKS
    ---------------------------------------------------------------------
    FOR link_rec IN SELECT * FROM jsonb_array_elements(payload->'pattern_post_link')
    LOOP
        INSERT INTO pattern_post_link(pattern_id, post_id)
        SELECT
            (SELECT id FROM patterns WHERE name = link_rec->>'pattern_name'),
            (SELECT id FROM posts    WHERE name = link_rec->>'post_name')
        ON CONFLICT DO NOTHING;
    END LOOP;


    ---------------------------------------------------------------------
    -- 6. PATTERN → ORG LINKS
    ---------------------------------------------------------------------
    FOR link_rec IN SELECT * FROM jsonb_array_elements(payload->'pattern_org_link')
    LOOP
        INSERT INTO pattern_org_link(pattern_id, org_id)
        SELECT
            (SELECT id FROM patterns WHERE name = link_rec->>'pattern_name'),
            (SELECT org_id FROM orgs WHERE name = link_rec->>'org_name')
        ON CONFLICT DO NOTHING;
    END LOOP;


    ---------------------------------------------------------------------
    -- 7. PATTERN → GUEST LINKS
    ---------------------------------------------------------------------
    FOR link_rec IN SELECT * FROM jsonb_array_elements(payload->'pattern_guest_link')
    LOOP
        INSERT INTO pattern_guest_link(pattern_id, guest_id)
        SELECT
            (SELECT id FROM patterns WHERE name = link_rec->>'pattern_name'),
            (SELECT guest_id FROM guests WHERE name = link_rec->>'guest_name')
        ON CONFLICT DO NOTHING;
    END LOOP;


    ---------------------------------------------------------------------
    -- RETURN SUMMARY
    ---------------------------------------------------------------------
    RETURN jsonb_build_object(
        'status', 'success',
        'details', results
    );

END;
$$;
