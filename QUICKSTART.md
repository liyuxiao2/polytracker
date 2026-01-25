# PolyEdge - Quick Start Guide

Get PolyEdge running in 5 minutes!

## Quick Start (Single Command)

After initial setup, run both servers at once:

```bash
./dev.sh
```

This starts both backend (port 8000) and frontend (port 3000) together. Press Ctrl+C to stop both.

**Note**: For first-time setup or if you prefer running them separately, see the manual setup steps below.

## First Time Setup (Manual Method)

### Step 1: Backend Setup

Open a terminal and run:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

You should see:
```
[App] Initializing database...
[App] Starting background worker...
[Worker] Starting data ingestion worker (poll interval: 30s)
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Keep this terminal open!

### Step 2: Frontend Setup

Open a **new terminal** and run:

```bash
cd frontend
npm install
npm run dev
```

You should see:
```
  ▲ Next.js 15.x.x
  - Local:        http://localhost:3000
```

### Step 3: Open Dashboard

Visit: **http://localhost:3000**

You'll see the PolyEdge dashboard with:
- Live trade feed with mock data
- Top insider traders ranked by confidence score
- Real-time statistics
- Interactive charts

## What's Happening?

In **Mock Mode** (enabled by default), the backend:
1. Generates 50 synthetic trades every 30 seconds
2. Creates 20 unique wallet addresses
3. Simulates 5 "whale" traders with occasional large bets
4. Calculates Z-scores and flags anomalous trades
5. Updates insider confidence scores in real-time

## Database Migration (Required for Market Watch)

If you're using the new Market Watch feature, run this migration first:

```bash
cd backend
python run_migration.py
```

This adds the necessary fields for market categorization, metrics, and suspicious activity tracking.

## Quick Tour

### Live Feed View
- See real-time trades as they come in
- Trades are color-coded by deviation
- Click any trader to see their profile

### Top Insiders View
- Traders sorted by insider confidence score
- Score ranges from 0-100 (higher = more suspicious)
- Sortable by trades, bet size, or flagged count

### Market Watch View (NEW!)
- Browse markets by category (NBA, Politics, Crypto, etc.)
- See suspicion scores based on flagged trades and timing
- Track volatility and price movements
- Sort by suspicious activity, volatility, volume, or flagged trades
- Filter by specific categories to focus on markets you care about

### Trader Detail Modal
- Click any wallet address
- View bet size chart over time
- Red dots = flagged trades above baseline
- Full trade history table

## Customization

Edit `backend/.env` to adjust:

```env
# How often to fetch new trades (seconds)
POLL_INTERVAL_SECONDS=30

# Minimum trade size to highlight (USD)
MIN_TRADE_SIZE_USD=5000

# Z-score threshold for flagging (standard deviations)
Z_SCORE_THRESHOLD=3.0
```

## API Endpoints

Test the API directly:

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **All Traders**: http://localhost:8000/api/traders
- **Trending Trades**: http://localhost:8000/api/trades/trending
- **Dashboard Stats**: http://localhost:8000/api/stats
- **Market Watch**: http://localhost:8000/api/markets/watch?sort_by=suspicion_score
- **Markets by Category**: http://localhost:8000/api/markets/watch?category=NBA

## Production Mode

To connect to real Polymarket data:

1. Edit `backend/.env`:
```env
MOCK_MODE=false
```

2. Restart the backend:
```bash
cd backend
python run.py
```

The system will now poll the real Polymarket CLOB API!

## Troubleshooting

### Backend won't start?
- Check Python version: `python --version` (need 3.10+)
- Activate venv: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

### Frontend won't start?
- Check Node version: `node --version` (need 18+)
- Delete node_modules: `rm -rf node_modules && npm install`

### No data showing?
- Check backend is running on port 8000
- Check browser console for errors
- Verify API is reachable: http://localhost:8000/health

### Database errors?
- Delete the database: `rm backend/polyedge.db`
- Restart backend (it will recreate)

## Next Steps

1. **Explore the code**: Check out the file structure in README.md
2. **Customize detection**: Modify the Z-score algorithm in `backend/app/services/insider_detector.py`
3. **Add features**: The codebase is modular and easy to extend
4. **Deploy**: Follow production deployment guide in README.md

## Support

Questions? Check the main README.md or open an issue!

---

Happy whale hunting! 🐋
