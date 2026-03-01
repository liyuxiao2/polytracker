# Trade Primary Key Redesign

## Problem

The `Trade` model uses an auto-increment `id` as primary key. This field is never queried directly — all real access patterns are by `wallet_address`, `market_id`, `timestamp`, or `transaction_hash`. The `id` adds no value and doesn't reflect the data's natural identity.

## Decision

- **Primary Key**: `transaction_hash` (String, not null) — the natural unique identifier from Polymarket
- **Remove**: `id` column entirely
- **Add composite indexes** for both trader-centric and market-centric query patterns

## Indexes

| Index | Columns | Purpose |
|---|---|---|
| PK | `transaction_hash` | Trade identity, dedup on ingest |
| Trader-centric | `(wallet_address, market_id, timestamp)` | "Trader X's activity on market Y over time" |
| Market-centric | `(market_id, timestamp, wallet_address)` | "All activity on market Y ordered by time" |

Existing individual indexes on `wallet_address`, `market_id`, `timestamp` may become redundant with the composites but can be evaluated later.

## Code Changes

| File | Change |
|---|---|
| `backend/app/models/database.py` | Change PK to `transaction_hash`, add composite indexes, drop `id` |
| `backend/app/schemas/trader.py` | Remove `id` from `TradeResponse` and `TradeCreate` |
| `frontend/lib/types.ts` | Remove `id` from `Trade` interface |
| `backend/app/api/routes.py` | Replace `func.count(Trade.id)` with `func.count(Trade.transaction_hash)` |
| `backend/app/services/insider_detector.py` | Replace `t.id != trade.id` with `t.transaction_hash != trade.transaction_hash` |
| `frontend/components/MarketWatch.tsx` | Change React key from `trade.id` to `trade.transaction_hash` |
| `frontend/components/TraderDetail.tsx` | Change React key from `trade.id` to `trade.transaction_hash` |
| `backend/tests/test_models.py` | Update test to use `transaction_hash` instead of `id` |

## Migration

SQLite does not support altering primary keys. Strategy: drop and recreate the database. This is acceptable because the system re-ingests data from Polymarket on startup.

## Date

2026-03-01
