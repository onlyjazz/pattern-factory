-- Migration: Add normalization tracking columns to threat.threats
-- Purpose: Support Cycle-3 threat normalization with audit trail
-- Date: 2026-08-19

BEGIN;

-- Add columns for normalization tracking
ALTER TABLE threat.threats
ADD COLUMN IF NOT EXISTS normalization_version INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS normalized_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS normalization_confidence NUMERIC(3, 2),
ADD COLUMN IF NOT EXISTS original_threat_snapshot JSONB;

-- Create index on normalization_version for filtering
CREATE INDEX IF NOT EXISTS idx_threats_normalization_version 
ON threat.threats(model_id, normalization_version);

COMMIT;
