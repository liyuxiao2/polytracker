# Trade Primary Key Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the synthetic auto-increment `id` on the Trade model with `transaction_hash` as the natural primary key, and add composite indexes for trader-centric and market-centric queries.

**Architecture:** Remove `id` column from Trade, promote `transaction_hash` to primary key (non-nullable), add two composite indexes via `__table_args__`. Update all code that references `Trade.id` or `trade.id` to use `transaction_hash` instead. Drop and recreate the database since SQLite doesn't support PK alteration.

**Tech Stack:** SQLAlchemy (async), Pydantic, TypeScript, React

---

### Task 1: Update the Trade model in database.py

**Files:**
- Modify: `backend/app/models/database.py:33-69`

**Step 1: Edit the Trade model**

Replace the `id` and `transaction_hash` column definitions, and add `__table_args__` with composite indexes.

Remove:
```python
    id = Column(Integer, primary_key=True, index=True)
```

Change:
```python
    transaction_hash = Column(String, unique=True, index=True, nullable=True)  # Unique trade identifier
```
To:
```python
    transaction_hash = Column(String, primary_key=True, nullable=False)
```

Add `__table_args__` at the end of the class (before the next class definition), also importing `Index` from sqlalchemy:

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index
```

Add at the end of the Trade class body:
```python
    __table_args__ = (
        Index("ix_trades_wallet_market_time", "wallet_address", "market_id", "timestamp"),
        Index("ix_trades_market_time_wallet", "market_id", "timestamp", "wallet_address"),
    )
```

**Step 2: Verify the model looks correct**

Read the file and confirm:
- No `id` column on Trade
- `transaction_hash` is `primary_key=True, nullable=False`
- Two composite indexes defined in `__table_args__`
- The `unique=True` and `index=True` kwargs are removed from `transaction_hash` (PK implies both)

**Step 3: Commit**

```bash
git add backend/app/models/database.py
git commit -m "refactor(Trade): use transaction_hash as primary key, add composite indexes"
```

---

### Task 2: Update Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/trader.py:21-41`

**Step 1: Edit TradeCreate — make transaction_hash required**

In `TradeCreate` (line 21-23), change:
```python
class TradeCreate(TradeBase):
    transaction_hash: Optional[str] = None
    asset_id: Optional[str] = None
```
To:
```python
class TradeCreate(TradeBase):
    transaction_hash: str
    asset_id: Optional[str] = None
```

**Step 2: Edit TradeResponse — remove id, make transaction_hash required**

In `TradeResponse` (line 26-41), remove `id: int` and change `transaction_hash` from Optional to required:
```python
class TradeResponse(TradeBase):
    transaction_hash: str
    is_flagged: bool
    flag_reason: Optional[str] = None
    z_score: Optional[float] = None
    is_win: Optional[bool] = None
    pnl_usd: Optional[float] = None
    # Unrealized P&L fields (for open positions)
    unrealized_pnl_usd: Optional[float] = None
    current_position_value_usd: Optional[float] = None
    shares_held: Optional[float] = None
    last_pnl_update: Optional[datetime] = None

    class Config:
        from_attributes = True
```

**Step 3: Commit**

```bash
git add backend/app/schemas/trader.py
git commit -m "refactor(schemas): remove id from TradeResponse, make transaction_hash required"
```

---

### Task 3: Update frontend TypeScript types

**Files:**
- Modify: `frontend/lib/types.ts:56-75`

**Step 1: Edit Trade interface**

Remove `id: number;` and make `transaction_hash` required:

```typescript
export interface Trade {
  transaction_hash: string;
  wallet_address: string;
  market_id: string;
  market_slug?: string;
  market_name: string;
  trade_size_usd: number;
  outcome?: string;
  price?: number;
  timestamp: string;
  is_flagged: boolean;
  flag_reason?: string;
  z_score?: number;
  is_win?: boolean | null;
  pnl_usd?: number;
  // Trade direction
  side?: string;
  trade_type?: string;
}
```

**Step 2: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "refactor(types): remove id from Trade interface, make transaction_hash required"
```

---

### Task 4: Update API routes — replace Trade.id references

**Files:**
- Modify: `backend/app/api/routes.py`

**Step 1: Replace all `func.count(Trade.id)` with `func.count(Trade.transaction_hash)`**

There are 6 occurrences at lines: 256, 266, 278, 286, 287, 319, 429.

Use find-and-replace: `Trade.id` → `Trade.transaction_hash` (only within `func.count()` calls in this file).

Specifically change every instance of:
```python
func.count(Trade.id)
```
to:
```python
func.count(Trade.transaction_hash)
```

**Step 2: Verify no remaining `Trade.id` references**

Search routes.py for `Trade.id` — should return zero results.

**Step 3: Commit**

```bash
git add backend/app/api/routes.py
git commit -m "refactor(routes): replace Trade.id with Trade.transaction_hash in count queries"
```

---

### Task 5: Update insider_detector.py — replace Trade.id reference

**Files:**
- Modify: `backend/app/services/insider_detector.py:704`

**Step 1: Edit coordinated trading detection**

At line 704, change:
```python
                if t.id != trade.id
```
to:
```python
                if t.transaction_hash != trade.transaction_hash
```

**Step 2: Commit**

```bash
git add backend/app/services/insider_detector.py
git commit -m "refactor(detector): use transaction_hash for trade identity comparison"
```

---

### Task 6: Update frontend React components — replace trade.id keys

**Files:**
- Modify: `frontend/components/MarketWatch.tsx:313`
- Modify: `frontend/components/TraderDetail.tsx:297`

**Step 1: Edit MarketWatch.tsx**

Change:
```tsx
key={trade.id}
```
to:
```tsx
key={trade.transaction_hash}
```

**Step 2: Edit TraderDetail.tsx**

Change:
```tsx
key={trade.id}
```
to:
```tsx
key={trade.transaction_hash}
```

**Step 3: Commit**

```bash
git add frontend/components/MarketWatch.tsx frontend/components/TraderDetail.tsx
git commit -m "refactor(frontend): use transaction_hash as React key for trade lists"
```

---

### Task 7: Update tests

**Files:**
- Modify: `backend/tests/test_models.py:29-46`

**Step 1: Fix test_trade_defaults**

The test at line 39 queries by `Trade.id == trade.id`. Change this to query by `wallet_address` (consistent with the other test) or by `transaction_hash`. Since this test doesn't set `transaction_hash`, we need to add one:

Replace the entire `test_trade_defaults` method:
```python
    async def test_trade_defaults(self, session):
        trade = Trade(
            wallet_address="0xdef456",
            market_id="market_2",
            market_name="Election 2025",
            trade_size_usd=1000.0,
            transaction_hash="tx_defaults_test",
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(
            select(Trade).where(Trade.transaction_hash == "tx_defaults_test")
        )
        saved = result.scalar_one()

        assert saved.is_flagged is False
        assert saved.is_resolved is False
        assert saved.z_score is None
        assert saved.is_win is None
        assert saved.pnl_usd is None
```

Also update `test_create_trade` to include a `transaction_hash` since it's now required:
```python
    async def test_create_trade(self, session):
        trade = Trade(
            wallet_address="0xabc123",
            market_id="market_1",
            market_name="Will BTC hit 100k?",
            trade_size_usd=5000.0,
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            transaction_hash="tx_create_test",
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(select(Trade).where(Trade.wallet_address == "0xabc123"))
        saved = result.scalar_one()

        assert saved.wallet_address == "0xabc123"
        assert saved.market_id == "market_1"
        assert saved.trade_size_usd == 5000.0
        assert saved.is_flagged is False
```

Also update `test_trade_with_resolution` to include `transaction_hash`:
```python
    async def test_trade_with_resolution(self, session):
        trade = Trade(
            wallet_address="0xresolved",
            market_id="m1",
            market_name="Resolved market",
            trade_size_usd=10000.0,
            outcome="YES",
            is_resolved=True,
            resolved_outcome="YES",
            is_win=True,
            pnl_usd=5000.0,
            transaction_hash="tx_resolved_test",
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(select(Trade).where(Trade.wallet_address == "0xresolved"))
        saved = result.scalar_one()

        assert saved.is_win is True
        assert saved.pnl_usd == 5000.0
        assert saved.resolved_outcome == "YES"
```

**Step 2: Run tests**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

Expected: All tests pass.

**Step 3: Commit**

```bash
git add backend/tests/test_models.py
git commit -m "refactor(tests): update trade tests for transaction_hash primary key"
```

---

### Task 8: Update data_worker.py — ensure transaction_hash is always set

**Files:**
- Modify: `backend/app/services/data_worker.py`

**Step 1: Check that mock data generation and real data ingestion always provide transaction_hash**

Since `transaction_hash` is now non-nullable (it's the PK), we need to ensure every code path that creates a Trade sets it. Check `data_worker.py` for any Trade creation without `transaction_hash` and ensure mock mode generates one (e.g., using `uuid4`).

In mock data generation, if `transaction_hash` isn't already set, add:
```python
import uuid
# ... in mock trade generation:
transaction_hash=f"mock_{uuid.uuid4().hex[:16]}"
```

For real data ingestion, `transaction_hash` is already extracted from `trade_data.get("id", "")`. Add a fallback so it's never empty:
```python
transaction_hash = trade_data.get("id", "") or f"unknown_{uuid.uuid4().hex[:16]}"
```

**Step 2: Commit**

```bash
git add backend/app/services/data_worker.py
git commit -m "refactor(worker): ensure transaction_hash is always set for new trades"
```

---

### Task 9: Delete the database and verify startup

**Step 1: Delete existing database file**

```bash
rm -f backend/polyedge.db backend/*.db
```

**Step 2: Start the backend and verify it creates the schema**

```bash
cd backend && python -c "import asyncio; from app.models.database import init_db; asyncio.run(init_db())"
```

Expected: No errors. New database created with `transaction_hash` as PK and composite indexes.

**Step 3: Verify the schema**

```bash
sqlite3 backend/polyedge.db ".schema trades"
```

Expected: `transaction_hash` as PRIMARY KEY, no `id` column, two composite indexes.

**Step 4: Commit (if any remaining changes)**

```bash
git add -A
git commit -m "chore: remove old database, verified new schema"
```
