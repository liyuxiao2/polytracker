import pytest
from datetime import datetime, timedelta

from app.models.database import Trade, TraderProfile, Market


class TestHealthEndpoint:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "PolyEdge API"
        assert "version" in data


class TestTradersEndpoint:
    async def test_get_traders_empty(self, client):
        resp = await client.get("/api/traders")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_traders_with_data(self, client, session):
        # Create test profiles
        for i, score in enumerate([90.0, 70.0, 50.0]):
            profile = TraderProfile(
                wallet_address=f"0xtrader{i}",
                total_trades=10 + i,
                avg_bet_size=1000.0,
                std_bet_size=200.0,
                max_bet_size=5000.0,
                total_volume=10000.0,
                insider_score=score,
                flagged_trades_count=i + 1,
            )
            session.add(profile)
        await session.commit()

        resp = await client.get("/api/traders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be sorted by insider_score desc
        assert data[0]["insider_score"] == 90.0
        assert data[1]["insider_score"] == 70.0
        assert data[2]["insider_score"] == 50.0

    async def test_get_traders_min_score_filter(self, client, session):
        for i, score in enumerate([90.0, 40.0, 10.0]):
            profile = TraderProfile(
                wallet_address=f"0xfilter{i}",
                total_trades=5,
                avg_bet_size=500.0,
                std_bet_size=100.0,
                max_bet_size=2000.0,
                total_volume=2500.0,
                insider_score=score,
                flagged_trades_count=1,
            )
            session.add(profile)
        await session.commit()

        resp = await client.get("/api/traders?min_score=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["insider_score"] == 90.0

    async def test_get_traders_limit(self, client, session):
        for i in range(5):
            profile = TraderProfile(
                wallet_address=f"0xlimit{i}",
                total_trades=5,
                avg_bet_size=500.0,
                std_bet_size=100.0,
                max_bet_size=2000.0,
                total_volume=2500.0,
                insider_score=50.0 + i,
                flagged_trades_count=1,
            )
            session.add(profile)
        await session.commit()

        resp = await client.get("/api/traders?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_get_traders_with_last_trade_time(self, client, session):
        profile = TraderProfile(
            wallet_address="0xwithtrades",
            total_trades=1,
            avg_bet_size=1000.0,
            std_bet_size=0.0,
            max_bet_size=1000.0,
            total_volume=1000.0,
            insider_score=60.0,
            flagged_trades_count=0,
        )
        trade = Trade(
            wallet_address="0xwithtrades",
            market_id="m1",
            market_name="Test",
            trade_size_usd=1000.0,
            timestamp=datetime(2025, 6, 15, 10, 0, 0),
        )
        session.add(profile)
        session.add(trade)
        await session.commit()

        resp = await client.get("/api/traders")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["last_trade_time"] is not None


class TestTraderProfileEndpoint:
    async def test_trader_not_found(self, client):
        resp = await client.get("/api/trader/0xnonexistent")
        assert resp.status_code == 404

    async def test_get_trader_profile(self, client, session):
        profile = TraderProfile(
            wallet_address="0xexists",
            total_trades=20,
            avg_bet_size=2000.0,
            std_bet_size=500.0,
            max_bet_size=15000.0,
            total_volume=40000.0,
            insider_score=85.0,
            flagged_trades_count=3,
            last_updated=datetime.utcnow(),
        )
        session.add(profile)
        await session.commit()

        resp = await client.get("/api/trader/0xexists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wallet_address"] == "0xexists"
        assert data["insider_score"] == 85.0
        assert data["total_trades"] == 20


class TestTraderTradesEndpoint:
    async def test_get_trader_trades(self, client, session):
        for i in range(3):
            trade = Trade(
                wallet_address="0xtradehistory",
                market_id=f"m{i}",
                market_name=f"Market {i}",
                trade_size_usd=1000.0 * (i + 1),
                timestamp=datetime(2025, 6, 15, 10 + i, 0, 0),
            )
            session.add(trade)
        await session.commit()

        resp = await client.get("/api/trader/0xtradehistory/trades")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be sorted by timestamp desc
        assert data[0]["trade_size_usd"] == 3000.0

    async def test_get_trader_trades_empty(self, client):
        resp = await client.get("/api/trader/0xnotrades/trades")
        assert resp.status_code == 200
        assert resp.json() == []


class TestDashboardStats:
    async def test_stats_empty_db(self, client):
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_whales_tracked"] == 0
        assert data["total_trades_monitored"] == 0
        assert data["avg_insider_score"] == 0.0

    async def test_stats_with_data(self, client, session):
        profile = TraderProfile(
            wallet_address="0xwhale",
            total_trades=100,
            avg_bet_size=5000.0,
            std_bet_size=1000.0,
            max_bet_size=50000.0,
            total_volume=500000.0,
            insider_score=80.0,
            flagged_trades_count=10,
        )
        session.add(profile)

        now = datetime.utcnow()
        trade = Trade(
            wallet_address="0xwhale",
            market_id="m1",
            market_name="Test",
            trade_size_usd=10000.0,
            timestamp=now,
            is_flagged=True,
        )
        session.add(trade)
        await session.commit()

        resp = await client.get("/api/stats")
        data = resp.json()
        assert data["total_whales_tracked"] == 1
        assert data["total_trades_monitored"] == 1
        assert data["high_signal_alerts_today"] == 1


class TestMarketWatch:
    async def test_market_watch_empty(self, client):
        resp = await client.get("/api/markets/watch")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_market_watch_with_data(self, client, session):
        m1 = Market(
            market_id="m1",
            question="Will it rain?",
            category="Weather",
            suspicion_score=80.0,
            is_resolved=False,
        )
        m2 = Market(
            market_id="m2",
            question="Will BTC go up?",
            category="Crypto",
            suspicion_score=40.0,
            is_resolved=False,
        )
        session.add(m1)
        session.add(m2)
        await session.commit()

        resp = await client.get("/api/markets/watch")
        data = resp.json()
        assert len(data) == 2
        # Default sort by suspicion_score desc
        assert data[0]["suspicion_score"] == 80.0

    async def test_market_watch_excludes_resolved(self, client, session):
        m1 = Market(market_id="active", question="Active?", is_resolved=False, suspicion_score=50.0)
        m2 = Market(market_id="resolved", question="Resolved?", is_resolved=True, suspicion_score=90.0)
        session.add(m1)
        session.add(m2)
        await session.commit()

        resp = await client.get("/api/markets/watch")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["market_id"] == "active"

    async def test_market_watch_category_filter(self, client, session):
        m1 = Market(market_id="nba1", question="NBA game?", category="NBA", is_resolved=False)
        m2 = Market(market_id="pol1", question="Election?", category="Politics", is_resolved=False)
        session.add(m1)
        session.add(m2)
        await session.commit()

        resp = await client.get("/api/markets/watch?category=NBA")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "NBA"


class TestTrendingTrades:
    async def test_trending_empty(self, client):
        resp = await client.get("/api/trades/trending")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_trending_filters_by_size_or_flagged(self, client, session):
        now = datetime.utcnow()
        # Large trade (should appear)
        t1 = Trade(
            wallet_address="0xbig",
            market_id="m1",
            market_name="Big trade",
            trade_size_usd=50000.0,
            timestamp=now,
        )
        # Small flagged trade (should appear)
        t2 = Trade(
            wallet_address="0xflag",
            market_id="m2",
            market_name="Flagged",
            trade_size_usd=100.0,
            timestamp=now,
            is_flagged=True,
        )
        # Small unflagged trade (should NOT appear with default min_size=5000)
        t3 = Trade(
            wallet_address="0xsmall",
            market_id="m3",
            market_name="Small",
            trade_size_usd=100.0,
            timestamp=now,
        )
        session.add_all([t1, t2, t3])
        await session.commit()

        resp = await client.get("/api/trades/trending?min_size=5000&hours=24")
        data = resp.json()
        addresses = [t["wallet_address"] for t in data]
        assert "0xbig" in addresses
        assert "0xflag" in addresses
        assert "0xsmall" not in addresses


class TestMarketTrades:
    async def test_market_trades(self, client, session):
        for i in range(3):
            t = Trade(
                wallet_address=f"0xt{i}",
                market_id="target_market",
                market_name="Target",
                trade_size_usd=1000.0,
                timestamp=datetime(2025, 6, 15, 10 + i, 0, 0),
            )
            session.add(t)
        # Trade in different market
        t_other = Trade(
            wallet_address="0xother",
            market_id="other_market",
            market_name="Other",
            trade_size_usd=500.0,
        )
        session.add(t_other)
        await session.commit()

        resp = await client.get("/api/markets/target_market/trades")
        data = resp.json()
        assert len(data) == 3

    async def test_market_trades_count(self, client, session):
        for i in range(5):
            session.add(Trade(
                wallet_address=f"0x{i}",
                market_id="counted_market",
                market_name="Count",
                trade_size_usd=100.0,
            ))
        await session.commit()

        resp = await client.get("/api/markets/counted_market/trades/count")
        assert resp.status_code == 200
        assert resp.json()["total_trades"] == 5
