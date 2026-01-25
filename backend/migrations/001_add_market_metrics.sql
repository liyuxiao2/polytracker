-- Migration: Add market metrics and categorization fields
-- Date: 2026-01-24
-- Description: Adds fields for market categorization, metrics, and suspicious activity tracking

-- Add categorization fields
ALTER TABLE markets ADD COLUMN IF NOT EXISTS category VARCHAR(255);
ALTER TABLE markets ADD COLUMN IF NOT EXISTS tags VARCHAR(500);

-- Add market metrics
ALTER TABLE markets ADD COLUMN IF NOT EXISTS suspicious_trades_count INTEGER DEFAULT 0;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS total_trades_count INTEGER DEFAULT 0;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS total_volume FLOAT DEFAULT 0.0;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS unique_traders_count INTEGER DEFAULT 0;

-- Add volatility metrics
ALTER TABLE markets ADD COLUMN IF NOT EXISTS current_yes_price FLOAT;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS current_no_price FLOAT;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS price_change_24h FLOAT;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS volatility_score FLOAT DEFAULT 0.0;

-- Add suspicious activity score
ALTER TABLE markets ADD COLUMN IF NOT EXISTS suspicion_score FLOAT DEFAULT 0.0;

-- Add liquidity
ALTER TABLE markets ADD COLUMN IF NOT EXISTS liquidity_usd FLOAT;

-- Add metrics update timestamp
ALTER TABLE markets ADD COLUMN IF NOT EXISTS metrics_updated_at TIMESTAMP;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_markets_category ON markets(category);
CREATE INDEX IF NOT EXISTS idx_markets_suspicion_score ON markets(suspicion_score DESC);
CREATE INDEX IF NOT EXISTS idx_markets_volatility_score ON markets(volatility_score DESC);
CREATE INDEX IF NOT EXISTS idx_markets_is_resolved ON markets(is_resolved);
