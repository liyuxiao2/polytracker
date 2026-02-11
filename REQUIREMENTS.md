# PolyEdge — Data Ingestion Requirements

**Authors**: saixiao, louis xi
**Last Updated**: 2026-02-11
**Target Deadline**: End of March 2026
**Status**: Planning / Early Development

---

## 1. Goal

Build a robust data ingestion pipeline that continuously collects and stores Polymarket order book and trade data. This dataset will be used downstream for backtesting trading strategies.

---

## 2. What Already Exists

- **PolyEdge dashboard** — polls Polymarket for trades, computes Z-scores, stores in SQLite/PostgreSQL
- **Existing data worker** (`backend/app/services/data_worker.py`) — background poller for trade data
- **Polymarket client** (`backend/app/services/polymarket_client.py`) — HTTP client for CLOB + Data APIs
- **Louis's separate PostgreSQL DB** — ~2 weeks of trader data already collected via a JS-based scraper

---

## 3. What to Collect

| Data Point | Description | Granularity |
|---|---|---|
| **Spread** | Difference between best bid and best ask | Per snapshot |
| **Best Bid** | Highest buy order price | Per snapshot |
| **Best Ask** | Lowest sell order price | Per snapshot |
| **Bid Size** | Volume at best bid | Per snapshot |
| **Ask Size** | Volume at best ask | Per snapshot |
| **Last Trade Price** | Most recent trade execution price | Per snapshot |
| **Volume** | Total traded volume in the interval | Per interval |

### Market Categories

- **Politics** (elections, policy outcomes)
- **Sports** (NBA, NFL, soccer, etc.)
- **Crypto** (BTC/ETH price brackets — 5-minute and hourly markets)

---

## 4. Collection Parameters

- **Interval**: 1-minute or 5-minute snapshots
- **History depth**: As far back as possible (target: several months)
- **Sources**:
  - Polymarket CLOB API (`https://clob.polymarket.com`) — order book, trades
  - Polymarket Data API (`https://data-api.polymarket.com`) — market metadata, volume, categories
- **Access**: VPN required (Polymarket blocks US/Canadian IPs; use Luxembourg or similar)
- **Open question**: Does Polymarket expose historical data, or must we collect going forward only?

---

## 5. Storage

- **Database**: PostgreSQL (production-grade, supports concurrent reads/writes)
- **Retention**: Keep all raw snapshots; create aggregated views for faster queries
- **Existing data**: Integrate or migrate Louis's 2-week PostgreSQL dataset into the unified schema

### Proposed Schema (Draft)

```sql
-- Order book snapshots at regular intervals
CREATE TABLE order_book_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    market_id       TEXT NOT NULL,
    token_id        TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    best_bid        NUMERIC,
    best_ask        NUMERIC,
    bid_size        NUMERIC,
    ask_size        NUMERIC,
    spread          NUMERIC,
    mid_price       NUMERIC,
    last_trade_price NUMERIC,
    volume          NUMERIC,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_snapshots_market_ts ON order_book_snapshots (market_id, timestamp);
CREATE INDEX idx_snapshots_token_ts ON order_book_snapshots (token_id, timestamp);

-- Market metadata
CREATE TABLE markets (
    market_id       TEXT PRIMARY KEY,
    market_name     TEXT NOT NULL,
    category        TEXT,          -- Politics, Sports, Crypto, etc.
    description     TEXT,
    end_date        TIMESTAMPTZ,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Individual trades (already partially exists in current codebase)
CREATE TABLE trades (
    id              BIGSERIAL PRIMARY KEY,
    market_id       TEXT NOT NULL,
    token_id        TEXT NOT NULL,
    wallet_address  TEXT NOT NULL,
    side            TEXT,          -- BUY / SELL
    price           NUMERIC,
    size            NUMERIC,
    trade_size_usd  NUMERIC,
    timestamp       TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trades_market_ts ON trades (market_id, timestamp);
CREATE INDEX idx_trades_wallet ON trades (wallet_address, timestamp);
```

> This is a starting point. The design doc (Section 7) should evaluate this vs. alternatives.

---

## 6. Architecture

```
┌─────────────────────────────────────────────────┐
│              INGESTION PIPELINE                  │
│                                                  │
│  ┌───────────────┐      ┌───────────────────┐   │
│  │ Market        │      │ Order Book        │   │
│  │ Discovery     │─────→│ Snapshot Poller   │   │
│  │ Worker        │      │ (1-min interval)  │   │
│  └───────────────┘      └────────┬──────────┘   │
│         │                        │               │
│         │               ┌────────▼──────────┐   │
│         │               │ Trade             │   │
│         │               │ Collector         │   │
│         │               │ (per-market)      │   │
│         │               └────────┬──────────┘   │
│         │                        │               │
└─────────┼────────────────────────┼───────────────┘
          │                        │
          ▼                        ▼
┌─────────────────────────────────────────────────┐
│                 PostgreSQL                        │
│                                                  │
│  markets │ order_book_snapshots │ trades          │
└─────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│           EXISTING DASHBOARD (v1)                │
│                                                  │
│  FastAPI API  →  Next.js Frontend                │
│  Insider Detector (Z-scores)                     │
└─────────────────────────────────────────────────┘
```

### Workers

1. **Market Discovery Worker** — periodically fetches active markets from the Data API, filters by category (politics/sports/crypto), and maintains the `markets` table.
2. **Order Book Snapshot Poller** — for each tracked market, hits the CLOB API every 1–5 minutes, records best bid/ask/size/spread/volume into `order_book_snapshots`.
3. **Trade Collector** — fetches recent trades per market, deduplicates, and stores in `trades`.

---

## 7. Design Doc Required

**Author**: louis xi | **Reviewer**: saixiao

A 2-page design doc covering:

- **Problem statement**: What data do we need and why
- **Option A vs Option B**: Two approaches for the ingestion pipeline (e.g., REST polling vs WebSocket streaming, per-market workers vs batch collection, etc.)
- **Pros/cons** of each
- **Recommended approach** with justification
- **Final schema design** (refine the draft above)
- **Open questions**

---

## 8. Tasks

- [ ] Research Polymarket CLOB API for order book endpoints and historical data availability
- [ ] Research Polymarket Data API for market discovery and metadata
- [ ] Determine API rate limits and plan polling intervals accordingly
- [ ] Write data ingestion design doc (2-pager with 2 options)
- [ ] Design and finalize PostgreSQL schema
- [ ] Build market discovery worker (fetch + filter active markets)
- [ ] Build order book snapshot poller (1-min or 5-min interval per market)
- [ ] Build trade collector (fetch + deduplicate trades)
- [ ] Integrate or migrate Louis's existing 2-week dataset
- [ ] Add data validation and gap detection (alert if collection drops)
- [ ] Set up VPN access and verify API connectivity
- [ ] Deploy pipeline and let it run continuously to accumulate data

---

## 9. Timeline

| Week | Target Date | Milestone |
|------|-------------|-----------|
| **Week 1–2** | Feb 14 | API research complete. Design doc written and reviewed. |
| **Week 3–4** | Feb 28 | Ingestion pipeline running. Data accumulating in PostgreSQL. |
| **Week 5–6** | Mar 14 | 2+ weeks of clean data. Gap detection and validation in place. |
| **Week 7–8** | Mar 28 | **1+ month of historical data collected.** Existing dataset migrated. |

**Time commitment**: ~1–2 hours per weekend per person.

---

## 10. Open Questions

1. **Does Polymarket expose historical order book data?** Or must we collect going forward only?
2. **What are the CLOB API rate limits?** Determines how many markets we can poll and at what frequency.
3. **Can we access the API from behind a VPN?** Need to test Luxembourg endpoint.
4. **REST polling vs WebSocket?** WebSocket gives real-time data but is more complex to manage. Design doc should evaluate.
5. **How do we handle market expiry?** Markets resolve and become inactive — need to stop polling and archive.
6. **What's the minimum dataset size for useful backtesting?** Drives urgency of getting the pipeline running.

---

## 11. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Polymarket blocks our IP | Can't collect data | Use VPN; rotate IPs if needed |
| API rate limiting | Data gaps, incomplete snapshots | Implement exponential backoff; prioritize high-value markets |
| API schema changes | Ingestion breaks | Version the client; add schema validation |
| Data gaps from downtime | Incomplete history | Gap detection alerts; backfill if API supports it |
| PostgreSQL storage growth | Disk fills up | Monitor disk usage; partition tables by month; compress old data |

---

*This document is a living spec. Update it as requirements evolve.*
