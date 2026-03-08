-- Migration: Change trades table primary key from auto-increment id
-- to composite key (wallet_address, market_id, timestamp)

-- Step 1: Drop the old primary key constraint (if it's on id)
ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_pkey;

-- Step 2: Drop the id column (if it exists)
ALTER TABLE trades DROP COLUMN IF EXISTS id;

-- Step 3: Add composite primary key on (wallet_address, market_id, timestamp)
ALTER TABLE trades ADD PRIMARY KEY (wallet_address, market_id, timestamp);
