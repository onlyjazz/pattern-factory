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
    data_source TEXT,
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
    data_source TEXT,
    org_id BIGINT REFERENCES orgs(id) ON DELETE SET NULL,
    episode_id BIGINT REFERENCES episodes(id) ON DELETE SET NULL,
    post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Episodes
-- =====================

drop table if exists episodes cascade;
CREATE TABLE episodes (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT[],
    episode_url TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- =====================
-- Substack Posts
-- =====================

drop table if exists posts cascade;
CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT[],
    substack_url TEXT,
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
    data_source TEXT,
    kind TEXT CHECK (kind IN ('pattern','anti-pattern')) DEFAULT 'pattern',
    metadata JSONB DEFAULT '{}'::jsonb,        -- LLM summary, confidence, etc.
    highlights JSONB DEFAULT '[]'::jsonb,      -- quotes, snippets
    search_vector tsvector,                           -- for full-text search
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
DROP TABLE if exists pattern_episode_link cascade;
CREATE TABLE pattern_episode_link (
    pattern_id BIGINT REFERENCES patterns(id) ON DELETE CASCADE,
    episode_id BIGINT REFERENCES episodes(id) ON DELETE CASCADE,
    PRIMARY KEY (pattern_id, episode_id)
);
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

DROP INDEX if exists idx_episodes_vector cascade;
CREATE INDEX idx_episodes_vector
    ON episodes USING GIN (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,'')));

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
CREATE INDEX IF NOT EXISTS idx_pattern_episode_link_post ON pattern_episode_link(episode_id);

-- 
CREATE INDEX IF NOT EXISTS idx_orgs_active     ON orgs(id)     WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_guests_active   ON guests(id)   WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_episodes_active ON episodes(id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_posts_active    ON posts(id)    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_patterns_active ON patterns(id) WHERE deleted_at IS NULL;
--
-- Registry of materialized views for pattern factory queries (maps to results_registry§)
DROP TABLE IF EXISTS views_registry CASCADE;
CREATE TABLE IF NOT EXISTS views_registry (
    id BIGSERIAL PRIMARY KEY,
    rule_id int NOT NULL references rules(id),
    table_name TEXT NOT NULL,
    summary varchar,  -- how many rows were returned by executing the sql query (replaces query_results)
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
--
-- DSL rules for pattern factory views
DROP TABLE if EXISTS rules cascade;
CREATE TABLE IF NOT EXISTS rules (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    rule_code TEXT NOT NULL,  -- taken from DSL rule for example Logic: count total number of companies founded over 5 years ago
    sql TEXT NOT NULL,        -- generated SQL for materialized view
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
