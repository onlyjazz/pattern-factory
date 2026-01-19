--
-- change back end to select directly from threats table
ALTER TABLE threats ADD column card_id UUID REFERENCES public.cards(id);
--
-- setup some test data after the migration
update threats set card_id = (select id from cards where order_index = 1) where id = 1;
update threats set card_id = (select id from cards where order_index = 5) where id = 46;
--
-- Remove foreign key constraints to drop model_threats and threat_cards table
-- after 
set search_path to threat;
ALTER TABLE threats DROP CONSTRAINT IF EXISTS project_threats_threat_id_fkey;
ALTER TABLE threats DROP CONSTRAINT IF EXISTS threat_cards_threat_id_fkey;
DROP TABLE model_threats;
DROP TABLE threat_cards CASCADE;
