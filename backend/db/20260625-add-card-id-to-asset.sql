-- Migration to add the card-id to assets table as we make assets a full-fledged member of the story
ALTER TABLE threat.assets
ADD COLUMN card_id UUID;