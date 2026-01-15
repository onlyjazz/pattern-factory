set search_path to threat;
ALTER TABLE projects RENAME TO models;
ALTER TABLE project_threats RENAME TO model_threats;
-- rename project_id to model_id in all tables
ALTER TABLE area_asset RENAME COLUMN project_id TO model_id;
ALTER TABLE area_countermeasure RENAME COLUMN project_id TO model_id;
ALTER TABLE area_threat RENAME COLUMN project_id TO model_id;
ALTER TABLE area_vulnerability RENAME COLUMN project_id TO model_id;
ALTER TABLE areas RENAME COLUMN project_id TO model_id;
ALTER TABLE asset_threat RENAME COLUMN project_id TO model_id;
ALTER TABLE assets RENAME COLUMN project_id TO model_id;
ALTER TABLE attacker_threat RENAME COLUMN project_id TO model_id;
ALTER TABLE attacker_types RENAME COLUMN project_id TO model_id;
ALTER TABLE countermeasure_threat RENAME COLUMN project_id TO model_id;
ALTER TABLE countermeasures RENAME COLUMN project_id TO model_id;
ALTER TABLE entrypoint_threat RENAME COLUMN project_id TO model_id;
ALTER TABLE entrypoints RENAME COLUMN project_id TO model_id;
ALTER TABLE parameters RENAME COLUMN project_id TO model_id;
ALTER TABLE model_threats RENAME COLUMN project_id TO model_id;
ALTER TABLE risk_history RENAME COLUMN project_id TO model_id;
ALTER TABLE threat_cards RENAME COLUMN project_id TO model_id;
ALTER TABLE threats RENAME COLUMN project_id TO model_id;
ALTER TABLE vulnerabilities RENAME COLUMN project_id TO model_id;
ALTER TABLE vulnerability_threat RENAME COLUMN project_id TO model_id;
--
-- remove documentation and additional_documentation tables, functionality in cards in a more structured way
-- for example can link to FDA guidance documents inside the markdown content of a card
DROP TABLE documentation CASCADE;
DROP TABLE additional_documentation CASCADE;
DROP TABLE threat_documentation CASCADE;
-- post-migrations
ALTER TABLE risk_history add column model_id integer references models(id);
ALTER TABLE threat_cards add constraint "threat_cards_card_id_fkey" FOREIGN KEY (card_id) REFERENCES public.cards(id);
