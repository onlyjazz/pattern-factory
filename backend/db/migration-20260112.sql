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
-- PatternCard belongsTo Pattern
DROP TABLE IF EXISTS public.pattern_cards;
CREATE TABLE public.pattern_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
     -- MD text with common_contexts, typical_impact, early_signals, why_teams_miss_this, domain, audience, maturity
     -- UI like patterns.story
    card text not null,
    order_index INT DEFAULT 0,   -- position in the patterns' collection of cards
    -- Operational metadata (NOT semantic)
    domain TEXT,
    audience TEXT,
    maturity TEXT CHECK (maturity IN ('draft','validated','instrumented')) DEFAULT 'draft',
    -- 
    pattern_id bigint NOT NULL references patterns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
--  ThreatScenarios may reference many PatternCards — but PatternCards never reference ThreatScenarios.
CREATE TABLE public.threat_scenario_pattern_card_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threat_scenario_id bigint NOT NULL references threat.threats(id),
    pattern_card_id UUID NOT NULL references pattern_cards(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX uniq_threat_pattern_card
ON public.threat_scenario_pattern_card_refs (threat_scenario_id, pattern_card_id);
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

CREATE OR REPLACE TRIGGER update_pattern_cards_updated_at
BEFORE UPDATE ON public.pattern_cards
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE OR REPLACE TRIGGER update_patterns_updated_at
BEFORE UPDATE ON public.patterns    
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE OR REPLACE TRIGGER update_paths_updated_at
BEFORE UPDATE ON public.paths
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE OR REPLACE TRIGGER update_threats_updated_at
BEFORE UPDATE ON threat.threats
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();