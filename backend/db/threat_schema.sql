-- =========================================================
-- Pattern Factory — Threat Schema
-- RESET + RECREATE
-- Postgres ≥ 14
-- =========================================================

BEGIN;
CREATE SCHEMA IF NOT EXISTS threat;
SET search_path = threat, public;

-- =========================================================
-- 0. DROP TABLES (dependency order)
-- =========================================================

DROP TABLE IF EXISTS threat_documentation CASCADE;
DROP TABLE IF EXISTS additional_documentation CASCADE;

DROP TABLE IF EXISTS entrypoint_threat CASCADE;
DROP TABLE IF EXISTS attacker_threat CASCADE;
DROP TABLE IF EXISTS countermeasure_threat CASCADE;
DROP TABLE IF EXISTS vulnerability_threat CASCADE;
DROP TABLE IF EXISTS asset_threat CASCADE;
DROP TABLE IF EXISTS pattern_threat CASCADE;

DROP TABLE IF EXISTS area_countermeasure CASCADE;
DROP TABLE IF EXISTS area_vulnerability CASCADE;
DROP TABLE IF EXISTS area_threat CASCADE;
DROP TABLE IF EXISTS area_asset CASCADE;

DROP TABLE IF EXISTS entrypoints CASCADE;
DROP TABLE IF EXISTS countermeasures CASCADE;
DROP TABLE IF EXISTS vulnerabilities CASCADE;
DROP TABLE IF EXISTS threats CASCADE;
DROP TABLE IF EXISTS assets CASCADE;
DROP TABLE IF EXISTS areas CASCADE;

DROP TABLE IF EXISTS attacker_types CASCADE;
DROP TABLE IF EXISTS parameters CASCADE;
DROP TABLE IF EXISTS risk_history CASCADE;

DROP TABLE IF EXISTS projects CASCADE;

-- =========================================================
-- 1. Root aggregate
-- =========================================================

CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255),
    version     VARCHAR(50),
    author      VARCHAR(255),
    company     VARCHAR(255),
    category    VARCHAR(255),
    keywords    TEXT,
    description TEXT
);

-- =========================================================
-- 2. Core entities (project-scoped)
-- =========================================================

CREATE TABLE areas (
    id                          SERIAL PRIMARY KEY,
    project_id                  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                        VARCHAR(255) NOT NULL,
    description                 TEXT,
    use_for_threats             BOOLEAN NOT NULL,
    use_for_vulnerabilities     BOOLEAN NOT NULL,
    use_for_countermeasures     BOOLEAN NOT NULL,
    use_for_assets              BOOLEAN NOT NULL
);

CREATE INDEX idx_areas_project ON areas(project_id);

------------------------------------------------------------

CREATE TABLE assets (
    id                          SERIAL PRIMARY KEY,
    project_id                  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                        VARCHAR(255),
    description                 TEXT,
    fixed_value                 NUMERIC(15,2) NOT NULL,
    fixed_value_period          INTEGER NOT NULL,
    recurring_value             NUMERIC(15,2) NOT NULL,
    include_fixed_value         BOOLEAN NOT NULL,
    include_recurring_value     BOOLEAN NOT NULL,
    disabled                    BOOLEAN NOT NULL
);

CREATE INDEX idx_assets_project ON assets(project_id);

------------------------------------------------------------

CREATE TABLE threats (
    id                          SERIAL PRIMARY KEY,
    project_id                  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                        VARCHAR(255),
    description                 TEXT,
    probability                 INTEGER,
    damage_description          TEXT,
    spoofing                    BOOLEAN NOT NULL,
    tampering                   BOOLEAN NOT NULL,
    repudiation                 BOOLEAN NOT NULL,
    information_disclosure      BOOLEAN NOT NULL,
    denial_of_service           BOOLEAN NOT NULL,
    elevation_of_privilege      BOOLEAN NOT NULL,
    mitigation_level            INTEGER NOT NULL,
    disabled                    BOOLEAN NOT NULL
);

CREATE INDEX idx_threats_project ON threats(project_id);

------------------------------------------------------------

CREATE TABLE vulnerabilities (
    id                          SERIAL PRIMARY KEY,
    project_id                  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                        VARCHAR(255),
    description                 TEXT,
    disabled                    BOOLEAN NOT NULL
);

CREATE INDEX idx_vulnerabilities_project ON vulnerabilities(project_id);

------------------------------------------------------------

CREATE TABLE countermeasures (
    id                              SERIAL PRIMARY KEY,
    project_id                      INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                            VARCHAR(255),
    description                     TEXT,
    fixed_implementation_cost       INTEGER NOT NULL,
    fixed_cost_period               INTEGER NOT NULL,
    recurring_implementation_cost   INTEGER NOT NULL,
    detailed_design                 TEXT,
    implemented                     BOOLEAN NOT NULL,
    include_fixed_cost              BOOLEAN NOT NULL,
    include_recurring_cost          BOOLEAN NOT NULL,
    disabled                        BOOLEAN NOT NULL
);

CREATE INDEX idx_countermeasures_project ON countermeasures(project_id);

------------------------------------------------------------

CREATE TABLE entrypoints (
    id                          SERIAL PRIMARY KEY,
    project_id                  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    name                        VARCHAR(255),
    description                 TEXT
);

CREATE INDEX idx_entrypoints_project ON entrypoints(project_id);

------------------------------------------------------------

CREATE TABLE attacker_types (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    tools_available TEXT
);

-- =========================================================
-- 3. Join tables (graph edges)
-- =========================================================

CREATE TABLE pattern_threat (
    project_id  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    pattern_id  BIGINT NOT NULL
        REFERENCES patterns(id),
    threat_id   INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, pattern_id, threat_id)
);

CREATE INDEX idx_pattern_threat_project_pattern
    ON pattern_threat(project_id, pattern_id);

CREATE INDEX idx_pattern_threat_project_threat
    ON pattern_threat(project_id, threat_id);

------------------------------------------------------------

CREATE TABLE area_asset (
    project_id  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL
        REFERENCES areas(id) ON DELETE CASCADE,
    asset_id    INTEGER NOT NULL
        REFERENCES assets(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, area_id, asset_id)
);

------------------------------------------------------------

CREATE TABLE area_threat (
    project_id  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL
        REFERENCES areas(id) ON DELETE CASCADE,
    threat_id   INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, area_id, threat_id)
);

------------------------------------------------------------

CREATE TABLE area_vulnerability (
    project_id          INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    area_id             INTEGER NOT NULL
        REFERENCES areas(id) ON DELETE CASCADE,
    vulnerability_id    INTEGER NOT NULL
        REFERENCES vulnerabilities(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, area_id, vulnerability_id)
);

------------------------------------------------------------

CREATE TABLE area_countermeasure (
    project_id          INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    area_id             INTEGER NOT NULL
        REFERENCES areas(id) ON DELETE CASCADE,
    countermeasure_id   INTEGER NOT NULL
        REFERENCES countermeasures(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, area_id, countermeasure_id)
);

------------------------------------------------------------

CREATE TABLE asset_threat (
    project_id  INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    asset_id    INTEGER NOT NULL
        REFERENCES assets(id) ON DELETE CASCADE,
    threat_id   INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    damage      INTEGER,
    PRIMARY KEY (project_id, asset_id, threat_id)
);

------------------------------------------------------------

CREATE TABLE vulnerability_threat (
    project_id          INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    vulnerability_id    INTEGER NOT NULL
        REFERENCES vulnerabilities(id) ON DELETE CASCADE,
    threat_id           INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, vulnerability_id, threat_id)
);

------------------------------------------------------------

CREATE TABLE countermeasure_threat (
    project_id              INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    countermeasure_id       INTEGER NOT NULL
        REFERENCES countermeasures(id) ON DELETE CASCADE,
    threat_id               INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    mitigation_level        INTEGER,
    included_in_mitigation  BOOLEAN NOT NULL,
    PRIMARY KEY (project_id, countermeasure_id, threat_id)
);

------------------------------------------------------------

CREATE TABLE attacker_threat (
    project_id          INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    attacker_type_id    INTEGER NOT NULL
        REFERENCES attacker_types(id),
    threat_id           INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, attacker_type_id, threat_id)
);

------------------------------------------------------------

CREATE TABLE entrypoint_threat (
    project_id      INTEGER NOT NULL
        REFERENCES projects(id) ON DELETE CASCADE,
    entrypoint_id   INTEGER NOT NULL
        REFERENCES entrypoints(id) ON DELETE CASCADE,
    threat_id       INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, entrypoint_id, threat_id)
);

-- =========================================================
-- 4. Documentation
-- =========================================================

CREATE TABLE additional_documentation (
    id              SERIAL PRIMARY KEY,
    document_file   VARCHAR(255),
    document_title  VARCHAR(255),
    description     TEXT
);

------------------------------------------------------------

CREATE TABLE threat_documentation (
    threat_id   INTEGER NOT NULL
        REFERENCES threats(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL
        REFERENCES additional_documentation(id) ON DELETE CASCADE,
    PRIMARY KEY (threat_id, document_id)
);

-- =========================================================
-- 5. Parameters & telemetry
-- =========================================================

CREATE TABLE parameters (
    id              SERIAL PRIMARY KEY,
    parameter_name  VARCHAR(50),
    display_name    VARCHAR(50),
    value           VARCHAR(255)
);

------------------------------------------------------------

CREATE TABLE risk_history (
    time    TIMESTAMP WITHOUT TIME ZONE,
    series  VARCHAR(50),
    value   DOUBLE PRECISION,
    PRIMARY KEY (time, series)
);

COMMIT;
