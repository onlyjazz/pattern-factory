--
-- Enable user to enter a threat scenario in MD format - for future use.  Will be parsed by agents to extract threat 
-- attacker, vulnerabilities, assets, and sercurity countermeasures 
alter table threat.threats
    add column if not exists created_at TIMESTAMP DEFAULT now(),
    add column if not exists updated_at TIMESTAMP DEFAULT now(),
    add column if not exists scenario text default null,
    add column if not exists scenario_format text default 'md',
    add column if not exists scenario_version int default 1;
-- MD text threat scenario 
-- UI like patterns.story 

--
-- Card belongsTo Pattern, Pattern hasMany Cards
DROP TABLE IF EXISTS public.cards CASCADE;
CREATE TABLE public.cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    description TEXT,
     -- MD text with common_contexts, typical_impact, early_signals, why_teams_miss_this, domain, audience, maturity
     -- UI like patterns.story
    markdown text   default '#Pattern card',
    order_index INT DEFAULT 0,   -- position in the patterns' collection of cards
    -- Operational metadata (NOT semantic)
    domain      TEXT,
    audience    TEXT,
    -- Front end will offer select box with options 'draft','validated','instrumented'
    maturity    TEXT DEFAULT 'draft',
    -- 
    pattern_id  bigint references patterns(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
--  Threat may have multiple cards — but cards never reference Threats.
DROP TABLE IF EXISTS threat.threat_cards CASCADE;
CREATE TABLE threat.threat_cards (
    id        bigserial                        PRIMARY KEY,
    threat_id bigint                           NOT NULL REFERENCES threat.threats(id),
    card_id   UUID                             NOT NULL REFERENCES public.cards(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--
-- Trigger to update updated_at column
--
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER update_cards_updated_at
BEFORE UPDATE ON public.cards
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();

CREATE OR REPLACE TRIGGER update_patterns_updated_at
BEFORE UPDATE ON public.patterns    
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();

CREATE OR REPLACE TRIGGER update_paths_updated_at
BEFORE UPDATE ON public.paths
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();

CREATE OR REPLACE TRIGGER update_threats_updated_at
BEFORE UPDATE ON threat.threats
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();
--
DROP TABLE IF EXISTS public.projects CASCADE;
DROP TABLE IF EXISTS threat.pattern_threat;
--
-- Threat analysis projects table.  patterns, paths, cards are public and available to all projects 
--
CREATE TABLE IF NOT EXISTS threat.projects (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255),
    version     VARCHAR(50),
    author      VARCHAR(255),
    company     VARCHAR(255),
    category    VARCHAR(255),
    keywords    TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS threat.project_threats (
    id          BIGSERIAL PRIMARY KEY,
    project_id  BIGINT NOT NULL REFERENCES threat.projects(id),
    threat_id   BIGINT NOT NULL REFERENCES threat.threats(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- correct path
threat.threats
→ threat.threat_cards
→ public.cards
→ public.patterns
--
ALTER TABLE threat.threats drop column pattern_id;