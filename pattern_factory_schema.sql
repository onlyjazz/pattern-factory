-- ============================================
-- PATTERN FACTORY DATABASE SCHEMA (Postgres)
-- ============================================
-- Enable pgvector (requires Postgres ≥ 15, or extension installed via CREATE EXTENSION)
CREATE EXTENSION IF NOT EXISTS vector;
-- =====================
-- Life Science Categories
-- =====================
drop table  if exists life_science_categories cascade;
CREATE TABLE life_science_categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    tech_keywords TEXT[],
    data_source TEXT,
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
    website TEXT,
    linkedin_company_url TEXT,
    tech_keywords TEXT[],
    data_source TEXT,
    life_science_category_id BIGINT REFERENCES life_science_categories(id) ON DELETE SET NULL,
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
    substack_url TEXT,
    tech_keywords TEXT[],
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
    tech_keywords TEXT[],
    data_source TEXT,
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
    tech_keywords TEXT[],
    data_source TEXT,
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
    episode_id BIGINT REFERENCES episodes(id) ON DELETE SET NULL,
    post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,
    org_id BIGINT REFERENCES orgs(id) ON DELETE SET NULL,
    guest_id BIGINT REFERENCES guests(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb,        -- LLM summary, confidence, etc.
    highlights JSONB DEFAULT '[]'::jsonb,      -- quotes, snippets
    vector tsvector,                           -- for full-text search
    tech_keywords TEXT[],
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
    ON patterns USING GIN (vector);

-- Optional triggers for automatic vector updates
CREATE OR REPLACE FUNCTION patterns_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.vector :=
    to_tsvector('english', coalesce(NEW.name,'') || ' ' || coalesce(NEW.description,''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_patterns_vector_update
BEFORE INSERT OR UPDATE ON patterns
FOR EACH ROW EXECUTE FUNCTION patterns_vector_update();
