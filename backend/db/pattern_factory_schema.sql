-- ============================================
-- PATTERN FACTORY DATABASE SCHEMA (Postgres)
-- ============================================
-- Enable pgvector (requires Postgres ≥ 15, or extension installed via CREATE EXTENSION)
CREATE EXTENSION IF NOT EXISTS vector;
-- =====================
-- Life Science Categories
-- =====================
drop table  if exists categories cascade;
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    description TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Organizations
-- =====================

drop table if exists orgs cascade;
CREATE TABLE orgs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    stage TEXT,                   -- e.g., Seed, Series A, etc.
    funding NUMERIC,
    date_funded TIMESTAMP,
    date_founded TIMESTAMP,
    linkedin_company_url TEXT,
    keywords TEXT[],
    content_source TEXT,          -- e.g., 'linkedin', 'crunchbase', 'website'
    post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,          
    category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Guests
-- =====================

drop table if exists guests cascade;
CREATE TABLE guests (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    linkedin_url TEXT,
    job_description TEXT,
    keywords TEXT[],
    content_source TEXT,                -- e.g., 'linkedin', 'twitter', 'website', 'company_page', content post
    org_id BIGINT REFERENCES orgs(id) ON DELETE SET NULL,
    post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);
ALTER TABLE guests ADD CONSTRAINT guests_name_unique UNIQUE (name);

-- =====================
-- Episodes
-- =====================
-- Dec 5 refactor schema - removed episodes table
-- Episodes are now handled through the posts table
drop table if exists episodes cascade;

-- =====================
-- Substack Posts
-- =====================
-- Dec 5 refactor schema - posts table now handles all content, rename  substack_url to content_url
drop table if exists posts cascade;
CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT[],
    content_url TEXT,
    content_source TEXT,                        -- e.g., 'substack', 'website', 'blog', 'content_post'
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Patterns (Core entity)
-- =====================

drop table if exists patterns cascade;
CREATE TABLE patterns (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    content_source TEXT,                        -- e.g., 'substack', 'website', 'blog'
    kind TEXT CHECK (kind IN ('pattern','anti-pattern')) DEFAULT 'pattern',
    story_md TEXT,                              -- markdown-formatted story
    metadata JSONB DEFAULT '{}'::jsonb,         -- LLM summary, confidence, etc.
    highlights JSONB DEFAULT '[]'::jsonb,       -- quotes, snippets
    search_vector tsvector,                     -- for full-text search
    keywords TEXT[],
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Join Tables (Many-to-Many)
-- =====================

DROP TABLE if exists pattern_guest_link cascade;
CREATE TABLE pattern_guest_link (
    pattern_id BIGINT REFERENCES patterns(id) ON DELETE CASCADE,
    guest_id BIGINT REFERENCES guests(id) ON DELETE CASCADE,
    PRIMARY KEY (pattern_id, guest_id)
);

DROP TABLE if exists pattern_org_link cascade;
CREATE TABLE pattern_org_link (
    pattern_id BIGINT REFERENCES patterns(id) ON DELETE CASCADE,
    org_id BIGINT REFERENCES orgs(id) ON DELETE CASCADE,
    PRIMARY KEY (pattern_id, org_id)
);

DROP TABLE if exists pattern_post_link cascade;
CREATE TABLE pattern_post_link (
    pattern_id BIGINT REFERENCES patterns(id) ON DELETE CASCADE,
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    PRIMARY KEY (pattern_id, post_id)
);
--
-- Dec 5 refactor: removed episode-related tables
DROP TABLE if exists pattern_episode_link cascade;

-- =====================
-- System Log
-- =====================
DROP TABLE  if exists system_log cascade;
CREATE TABLE system_log (
    id BIGSERIAL PRIMARY KEY,
    event TEXT,
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT now()
);

-- =====================
-- Full-text search indexes
-- =====================
DROP INDEX if exists idx_orgs_vector cascade;
CREATE INDEX idx_orgs_vector
    ON orgs USING GIN (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,'')));

DROP INDEX if exists idx_guests_vector cascade;
CREATE INDEX idx_guests_vector
    ON guests USING GIN (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,'')));

-- Dec 5 refactor: removed episode-related indexes
DROP INDEX if exists idx_episodes_vector cascade;

DROP INDEX if exists idx_posts_vector cascade;
CREATE INDEX idx_posts_vector
    ON posts USING GIN (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,'')));

DROP INDEX if exists idx_patterns_vector cascade;
CREATE INDEX idx_patterns_vector
    ON patterns USING GIN (search_vector);

-- Optional triggers for automatic vector updates
CREATE OR REPLACE FUNCTION patterns_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    to_tsvector('english', coalesce(NEW.name,'') || ' ' || coalesce(NEW.description,''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_patterns_vector_update
BEFORE INSERT OR UPDATE ON patterns
FOR EACH ROW EXECUTE FUNCTION patterns_vector_update();
--
-- ============================================
-- INDEX TUNING FOR PATTERN FACTORY
-- ============================================
-- 
CREATE INDEX IF NOT EXISTS idx_pattern_guest_link_guest  ON pattern_guest_link(guest_id);
CREATE INDEX IF NOT EXISTS idx_pattern_org_link_org      ON pattern_org_link(org_id);
CREATE INDEX IF NOT EXISTS idx_pattern_post_link_post    ON pattern_post_link(post_id);

-- 
CREATE INDEX IF NOT EXISTS idx_orgs_active     ON orgs(id)     WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_guests_active   ON guests(id)   WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_posts_active    ON posts(id)    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_patterns_active ON patterns(id) WHERE deleted_at IS NULL;
--
-- =====================
-- Views Registry (consolidated rule and view metadata)
-- =====================
DROP TABLE IF EXISTS views_registry CASCADE;
CREATE TABLE IF NOT EXISTS views_registry (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR,                       -- YAML rule name e.g "Organizations who were on the podcast"
    table_name TEXT NOT NULL UNIQUE,    -- YAML rule rule_code e.g LIST_ORGS this will be the name of the view
    sql TEXT NOT NULL,                  -- generated SQL e.g. DROP VIEW IF EXISTS, create view 

    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
--
ALTER TABLE views_registry DROP CONSTRAINT views_registry_table_name_key;
ALTER TABLE views_registry ADD CONSTRAINT views_registry_table_name_key UNIQUE (table_name);

-- =====================
-- Unique Constraints for Upsert Operations
-- =====================
ALTER TABLE orgs ADD CONSTRAINT orgs_name_unique UNIQUE (name);
ALTER TABLE posts ADD CONSTRAINT posts_name_unique UNIQUE (name);
ALTER TABLE patterns ADD CONSTRAINT patterns_name_unique UNIQUE (name);
