# PolyEdge - System Architecture

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                             USER BROWSER                                │
│                          http://localhost:3000                          │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
                                │ HTTP/REST
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│                         NEXT.JS FRONTEND                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       App Router (page.tsx)                      │  │
│  │  - View Management (Live Feed, Top Insiders, All Traders)       │  │
│  │  - Auto-refresh (30s intervals)                                  │  │
│  │  - State management (traders, trades, stats, selected)          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   Sidebar    │  │  StatsBar    │  │ TradersTable │                 │
│  │  - Nav menu  │  │  - 4 metrics │  │  - Sortable  │                 │
│  │  - Status    │  │  - Icons     │  │  - Flagging  │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                          │
│  ┌──────────────┐  ┌──────────────────────────────────────────┐       │
│  │  LiveFeed    │  │        TraderDetail (Modal)              │       │
│  │  - Stream    │  │  - Profile stats                         │       │
│  │  - Deviation │  │  - Recharts line chart (bet size)        │       │
│  └──────────────┘  │  - Recent trades table                   │       │
│                    └──────────────────────────────────────────┘       │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     API Client (lib/api.ts)                      │  │
│  │  - getTraders(), getTrendingTrades(), getTraderProfile()        │  │
│  │  - getDashboardStats(), getTraderTrades()                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ HTTP REST API
                                    │ localhost:8000/api/*
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                          FASTAPI BACKEND                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      main.py (FastAPI App)                       │  │
│  │  - CORS middleware                                               │  │
│  │  - Lifespan management (startup/shutdown)                        │  │
│  │  - Router inclusion                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    API Routes (api/routes.py)                    │  │
│  │  GET /api/traders           - List flagged traders              │  │
│  │  GET /api/trades/trending   - Recent high-value trades          │  │
│  │  GET /api/trader/{address}  - Trader profile                    │  │
│  │  GET /api/trader/{address}/trades - Trade history               │  │
│  │  GET /api/stats             - Dashboard statistics              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   Services Layer                                 │  │
│  │  ┌─────────────────────────────────────────────────────────┐    │  │
│  │  │  insider_detector.py                                    │    │  │
│  │  │  - calculate_z_score(wallet, trade_size)                │    │  │
│  │  │  - update_trader_profile(wallet)                        │    │  │
│  │  │  - _calculate_insider_score(trades, flagged)            │    │  │
│  │  │  - get_trending_trades(min_size, hours)                 │    │  │
│  │  └─────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐    │  │
│  │  │  data_worker.py                                         │    │  │
│  │  │  - start() - Background asyncio loop                    │    │  │
│  │  │  - _process_trades() - Fetch & store trades             │    │  │
│  │  │  - _process_single_trade() - Z-score & flagging         │    │  │
│  │  └─────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐    │  │
│  │  │  polymarket_client.py                                   │    │  │
│  │  │  - get_recent_trades(limit)                             │    │  │
│  │  │  - get_market_activity(market_id)                       │    │  │
│  │  │  - _generate_mock_trades() [MOCK MODE]                  │    │  │
│  │  └─────────────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              Database Layer (models/database.py)                 │  │
│  │  ┌──────────────────┐         ┌──────────────────┐              │  │
│  │  │  Trade Model     │         │ TraderProfile    │              │  │
│  │  │  - wallet_address│         │ - wallet_address │              │  │
│  │  │  - market_id     │         │ - avg_bet_size   │              │  │
│  │  │  - trade_size_usd│         │ - std_bet_size   │              │  │
│  │  │  - z_score       │         │ - insider_score  │              │  │
│  │  │  - is_flagged    │         │ - flagged_count  │              │  │
│  │  │  - timestamp     │         │ - total_trades   │              │  │
│  │  └──────────────────┘         └──────────────────┘              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   SQLite Database (polyedge.db)                  │  │
│  │  - Async SQLAlchemy ORM                                          │  │
│  │  - Tables: trades, trader_profiles                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ HTTP Polling (30s)
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                         POLYMARKET APIs                                 │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐     │
│  │  CLOB API                   │  │  Data API                   │     │
│  │  clob.polymarket.com/trades │  │  data-api.polymarket.com    │     │
│  │  - Recent trades            │  │  - Market activity          │     │
│  │  - Market data              │  │  - Historical data          │     │
│  └─────────────────────────────┘  └─────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Data Ingestion Flow

```
┌──────────────┐
│ Timer (30s)  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ data_worker.py: _process_trades()                        │
│ - Fetch trades from Polymarket API or generate mock data │
└──────┬───────────────────────────────────────────────────┘
       │
       │ For each trade
       ▼
┌──────────────────────────────────────────────────────────┐
│ data_worker.py: _process_single_trade()                  │
│ 1. Check if trade already exists (deduplication)         │
│ 2. Call insider_detector.calculate_z_score()             │
│ 3. Create Trade record with z_score and is_flagged       │
│ 4. If flagged: call update_trader_profile()              │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ Database: SQLite                                          │
│ - Insert Trade                                            │
│ - Update/Insert TraderProfile                             │
└───────────────────────────────────────────────────────────┘
```

### 2. Z-Score Calculation Flow

```
Trade arrives
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ insider_detector.calculate_z_score()                │
│                                                     │
│ 1. Query last 100 trades for this wallet           │
│ 2. Calculate mean and std of trade sizes           │
│ 3. z = (current_trade - mean) / std                │
│ 4. is_anomaly = |z| > threshold (3.0)              │
│                                                     │
│ Return: (z_score, is_anomaly)                      │
└─────────────────────────────────────────────────────┘
```

### 3. Insider Score Calculation Flow

```
┌──────────────────────────────────────────────────────┐
│ insider_detector._calculate_insider_score()         │
│                                                      │
│ Score = Component1 + Component2 + Component3        │
│                                                      │
│ Component 1 (0-40 pts):                             │
│   flagged_percentage * 40                           │
│                                                      │
│ Component 2 (0-30 pts):                             │
│   min(avg_z_score / 9 * 30, 30)                     │
│                                                      │
│ Component 3 (0-30 pts):                             │
│   recent_flagged_percentage * 30                    │
│                                                      │
│ Final Score: min(total, 100)                        │
└──────────────────────────────────────────────────────┘
```

### 4. Frontend Data Flow

```
User opens dashboard
     │
     ▼
┌────────────────────────────────────────┐
│ page.tsx: useEffect() on mount         │
│ - fetchData()                          │
│   - api.getDashboardStats()            │
│   - api.getTraders(0, 100)             │
│   - api.getTrendingTrades(5000, 24)    │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Update React state                     │
│ - setStats(data)                       │
│ - setTraders(data)                     │
│ - setTrendingTrades(data)              │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Components re-render                   │
│ - StatsBar shows metrics               │
│ - TradersTable shows traders           │
│ - LiveFeed shows trades                │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Auto-refresh loop (every 30s)          │
│ - Calls fetchData() again              │
└────────────────────────────────────────┘
```

## Component Hierarchy

```
App (page.tsx)
├── Sidebar
│   └── Navigation items
├── Main Content
│   ├── Header
│   │   ├── Title
│   │   └── Controls (Auto-refresh, Refresh button)
│   ├── StatsBar
│   │   ├── Stat Card 1 (Whales Tracked)
│   │   ├── Stat Card 2 (High-Signal Alerts)
│   │   ├── Stat Card 3 (Total Trades)
│   │   └── Stat Card 4 (Avg Insider Score)
│   └── View Content (conditional)
│       ├── Live Feed View
│       │   ├── LiveFeed (left)
│       │   └── Top Suspicious Traders (right)
│       ├── Top Insiders View
│       │   └── TradersTable (filtered)
│       └── All Traders View
│           └── TradersTable (all)
└── TraderDetail (Modal, conditional)
    ├── Header
    ├── Stats Grid (4 cards)
    ├── Recharts Line Chart
    │   ├── XAxis (time)
    │   ├── YAxis (trade size)
    │   ├── Line (bet sizes)
    │   └── ReferenceLine (baseline)
    └── Recent Trades Table
```

## Database Schema

```sql
-- trades table
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address VARCHAR NOT NULL,
    market_id VARCHAR NOT NULL,
    market_name VARCHAR NOT NULL,
    trade_size_usd FLOAT NOT NULL,
    outcome VARCHAR,
    price FLOAT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_flagged BOOLEAN DEFAULT FALSE,
    z_score FLOAT,
    INDEX idx_wallet (wallet_address),
    INDEX idx_market (market_id),
    INDEX idx_timestamp (timestamp)
);

-- trader_profiles table
CREATE TABLE trader_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address VARCHAR UNIQUE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    avg_bet_size FLOAT DEFAULT 0.0,
    std_bet_size FLOAT DEFAULT 0.0,
    max_bet_size FLOAT DEFAULT 0.0,
    total_volume FLOAT DEFAULT 0.0,
    insider_score FLOAT DEFAULT 0.0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    flagged_trades_count INTEGER DEFAULT 0,
    INDEX idx_wallet_unique (wallet_address)
);
```

## API Request/Response Flow

### Example: GET /api/traders

```
Frontend                    Backend                     Database
   │                           │                           │
   │  GET /api/traders?       │                           │
   │  min_score=50&limit=20   │                           │
   ├──────────────────────────>│                           │
   │                           │                           │
   │                           │  SELECT * FROM           │
   │                           │  trader_profiles         │
   │                           │  WHERE insider_score>=50 │
   │                           │  ORDER BY insider_score  │
   │                           │  DESC LIMIT 20           │
   │                           ├──────────────────────────>│
   │                           │                           │
   │                           │<──────────────────────────┤
   │                           │  [profiles]               │
   │                           │                           │
   │                           │  For each profile:        │
   │                           │  SELECT timestamp FROM    │
   │                           │  trades WHERE wallet=...  │
   │                           │  ORDER BY timestamp DESC  │
   │                           │  LIMIT 1                  │
   │                           ├──────────────────────────>│
   │                           │<──────────────────────────┤
   │                           │                           │
   │                           │  Build TraderListItem[]   │
   │                           │                           │
   │<──────────────────────────┤                           │
   │  200 OK                   │                           │
   │  [TraderListItem]         │                           │
   │                           │                           │
```

## Deployment Architecture (Future)

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                        │
│                    (nginx/caddy)                         │
└────────────┬──────────────────────┬─────────────────────┘
             │                      │
             ▼                      ▼
┌────────────────────┐   ┌────────────────────┐
│  Frontend          │   │  Backend           │
│  Next.js           │   │  FastAPI           │
│  (Docker)          │   │  (Docker)          │
│  Port 3000         │   │  Port 8000         │
└────────────────────┘   └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │  PostgreSQL        │
                         │  (Docker)          │
                         │  Port 5432         │
                         └────────────────────┘
```

## Security Considerations

1. **CORS**: Configured for localhost:3000 (update for production)
2. **API Rate Limiting**: Should be added for production
3. **Input Validation**: Pydantic models validate all inputs
4. **SQL Injection**: Protected by SQLAlchemy ORM
5. **Environment Variables**: Sensitive config in .env (not committed)

## Performance Characteristics

- **Polling Interval**: 30 seconds (configurable)
- **Database Queries**: Indexed on wallet_address, timestamp
- **Frontend Refresh**: 30 seconds auto-refresh
- **API Response Time**: <100ms (with SQLite)
- **Concurrent Requests**: Handled by async FastAPI
- **Memory Usage**: Low (SQLite in-process)

---

This architecture provides a scalable, maintainable foundation for real-time insider detection on Polymarket.
