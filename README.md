# PolyEdge - Polymarket Insider Detection Dashboard

liyu

A real-time insider detection dashboard for Polymarket that identifies suspicious trading patterns using statistical analysis and Z-score calculations.

![PolyEdge Dashboard](https://img.shields.io/badge/Status-Production_Ready-green)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Next.js](https://img.shields.io/badge/Next.js-15-black)

## Features

- **Real-time Trade Monitoring**: Continuous polling of Polymarket CLOB API for live trade data
- **Insider Detection Algorithm**: Z-score based analysis to flag trades >3x the wallet's historical average
- **Insider Confidence Score**: 0-100 rating based on flagged trade percentage, Z-score, and recency
- **Bloomberg-Style UI**: Professional dark-mode dashboard with live updates
- **Trader Profiles**: Historical analysis showing baseline vs anomaly bet sizes
- **Mock Mode**: Development mode with synthetic data for immediate testing

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Async ORM with SQLite
- **Pydantic** - Data validation
- **NumPy/SciPy** - Statistical calculations
- **HTTPX** - Async HTTP client

### Frontend
- **Next.js 15** - React framework with App Router
- **Tailwind CSS** - Utility-first CSS
- **Recharts** - Data visualization
- **Lucide React** - Icon library
- **TypeScript** - Type safety

## Project Structure

```
polytracker/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # API endpoints
│   │   ├── models/
│   │   │   └── database.py        # SQLAlchemy models
│   │   ├── schemas/
│   │   │   └── trader.py          # Pydantic schemas
│   │   ├── services/
│   │   │   ├── data_worker.py     # Background data ingestion
│   │   │   ├── insider_detector.py # Z-score calculation
│   │   │   └── polymarket_client.py # API client
│   │   └── main.py                # FastAPI app
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Main dashboard
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── StatsBar.tsx
│   │   ├── TradersTable.tsx
│   │   ├── LiveFeed.tsx
│   │   └── TraderDetail.tsx
│   ├── lib/
│   │   ├── api.ts                 # API client
│   │   ├── types.ts               # TypeScript types
│   │   └── utils.ts               # Utility functions
│   └── package.json
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment file:
```bash
cp .env.example .env
```

5. Configure `.env` (optional - defaults work for development):
```env
DATABASE_URL=sqlite+aiosqlite:///./polyedge.db
MOCK_MODE=true
API_HOST=0.0.0.0
API_PORT=8000
POLYMARKET_CLOB_API=https://clob.polymarket.com
POLYMARKET_DATA_API=https://data-api.polymarket.com
POLL_INTERVAL_SECONDS=30
MIN_TRADE_SIZE_USD=5000
Z_SCORE_THRESHOLD=3.0
```

6. Run the backend:
```bash
python run.py
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
# or
yarn install
```

3. Run the development server:
```bash
npm run dev
# or
yarn dev
```

4. Open your browser:
```
http://localhost:3000
```

## API Endpoints

### GET `/api/traders`
List of flagged wallets with insider confidence scores.

**Query Parameters:**
- `min_score` (float, default: 0) - Minimum insider score filter
- `limit` (int, default: 50) - Maximum results to return

**Response:**
```json
[
  {
    "wallet_address": "0x1234...",
    "insider_score": 87.5,
    "total_trades": 45,
    "avg_bet_size": 2500.0,
    "flagged_trades_count": 12,
    "last_trade_time": "2026-01-05T10:30:00"
  }
]
```

### GET `/api/trades/trending`
Real-time stream of trades filtered by size or high deviation.

**Query Parameters:**
- `min_size` (float, default: 5000) - Minimum trade size in USD
- `hours` (int, default: 24) - Time window in hours
- `limit` (int, default: 100) - Maximum results

**Response:**
```json
[
  {
    "wallet_address": "0x1234...",
    "market_name": "Will Bitcoin reach $100k in 2026?",
    "trade_size_usd": 25000.0,
    "z_score": 4.2,
    "timestamp": "2026-01-05T10:30:00",
    "deviation_percentage": 320.5
  }
]
```

### GET `/api/trader/{address}`
Historical profile for a specific trader.

**Response:**
```json
{
  "wallet_address": "0x1234...",
  "total_trades": 45,
  "avg_bet_size": 2500.0,
  "std_bet_size": 1200.0,
  "max_bet_size": 25000.0,
  "total_volume": 112500.0,
  "insider_score": 87.5,
  "last_updated": "2026-01-05T10:30:00",
  "flagged_trades_count": 12
}
```

### GET `/api/trader/{address}/trades`
Trade history for a specific trader.

**Query Parameters:**
- `limit` (int, default: 100) - Maximum trades to return

### GET `/api/stats`
Dashboard-level statistics.

**Response:**
```json
{
  "total_whales_tracked": 15,
  "high_signal_alerts_today": 8,
  "total_trades_monitored": 342,
  "avg_insider_score": 45.2
}
```

## Insider Detection Algorithm

### Z-Score Calculation

For each trade, we calculate:

```python
z_score = (trade_size - historical_mean) / historical_std
```

A trade is flagged if `|z_score| > 3.0` (configurable)

### Insider Confidence Score (0-100)

The score combines three factors:

1. **Flagged Trade Percentage** (40 points max)
   - Proportion of total trades that are flagged

2. **Average Z-Score** (30 points max)
   - Mean z-score of flagged trades
   - Normalized: z=3 → 10pts, z=6 → 20pts, z≥9 → 30pts

3. **Recency Weight** (30 points max)
   - Percentage of recent (7 days) trades that are flagged

## Mock Mode

Mock mode generates realistic synthetic data for development:

- 20 unique wallet addresses
- 5 different markets
- 5 "whale" wallets with occasional large bets (30% chance)
- Random trade sizes: $100-$2,000 (normal), $10,000-$50,000 (whales)
- Realistic timestamps within last 24 hours

Enable in `.env`:
```env
MOCK_MODE=true
```

## Production Deployment

### Backend

1. Set `MOCK_MODE=false` in `.env`
2. Configure production database (PostgreSQL recommended)
3. Use a production ASGI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

1. Build the production bundle:
```bash
npm run build
```

2. Start the production server:
```bash
npm start
```

### Docker (Coming Soon)

```bash
docker-compose up -d
```

## Development

### Adding New Features

1. Backend: Add routes in [app/api/routes.py](backend/app/api/routes.py)
2. Frontend: Create components in [components/](frontend/components/)
3. Update types in [lib/types.ts](frontend/lib/types.ts)

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Polymarket for the CLOB and Data APIs
- FastAPI and Next.js communities
- Statistical analysis inspired by financial fraud detection systems

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: [your-email@example.com]

---

Built with ❤️ for transparent prediction markets
