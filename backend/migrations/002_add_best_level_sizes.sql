-- Migration: Add best bid/ask SIZE columns to market_snapshots table
-- These store the individual top-of-book sizes (not aggregated liquidity)

ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS yes_best_bid_size FLOAT;
ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS yes_best_ask_size FLOAT;
ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS no_best_bid_size FLOAT;
ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS no_best_ask_size FLOAT;
