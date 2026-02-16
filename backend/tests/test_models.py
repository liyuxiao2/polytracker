import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.database import Trade, TraderProfile, Market


class TestTradeModel:
    async def test_create_trade(self, session):
        trade = Trade(
            wallet_address="0xabc123",
            market_id="market_1",
            market_name="Will BTC hit 100k?",
            trade_size_usd=5000.0,
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(select(Trade).where(Trade.wallet_address == "0xabc123"))
        saved = result.scalar_one()

        assert saved.wallet_address == "0xabc123"
        assert saved.market_id == "market_1"
        assert saved.trade_size_usd == 5000.0
        assert saved.is_flagged is False

    async def test_trade_defaults(self, session):
        trade = Trade(
            wallet_address="0xdef456",
            market_id="market_2",
            market_name="Election 2025",
            trade_size_usd=1000.0,
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(select(Trade).where(Trade.id == trade.id))
        saved = result.scalar_one()

        assert saved.is_flagged is False
        assert saved.is_resolved is False
        assert saved.z_score is None
        assert saved.is_win is None
        assert saved.pnl_usd is None

    async def test_trade_unique_transaction_hash(self, session):
        trade1 = Trade(
            wallet_address="0xabc",
            market_id="m1",
            market_name="Test",
            trade_size_usd=100.0,
            transaction_hash="tx_unique_123",
        )
        trade2 = Trade(
            wallet_address="0xdef",
            market_id="m2",
            market_name="Test 2",
            trade_size_usd=200.0,
            transaction_hash="tx_unique_123",
        )
        session.add(trade1)
        await session.commit()

        session.add(trade2)
        with pytest.raises(IntegrityError):
            await session.commit()

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
        )
        session.add(trade)
        await session.commit()

        result = await session.execute(select(Trade).where(Trade.wallet_address == "0xresolved"))
        saved = result.scalar_one()

        assert saved.is_win is True
        assert saved.pnl_usd == 5000.0
        assert saved.resolved_outcome == "YES"


class TestTraderProfileModel:
    async def test_create_profile(self, session):
        profile = TraderProfile(
            wallet_address="0xtrader1",
            total_trades=50,
            avg_bet_size=1000.0,
            std_bet_size=500.0,
            max_bet_size=10000.0,
            total_volume=50000.0,
            insider_score=75.5,
            flagged_trades_count=5,
        )
        session.add(profile)
        await session.commit()

        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == "0xtrader1")
        )
        saved = result.scalar_one()

        assert saved.total_trades == 50
        assert saved.insider_score == 75.5
        assert saved.flagged_trades_count == 5

    async def test_profile_defaults(self, session):
        profile = TraderProfile(wallet_address="0xdefaults")
        session.add(profile)
        await session.commit()

        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == "0xdefaults")
        )
        saved = result.scalar_one()

        assert saved.total_trades == 0
        assert saved.win_rate == 0.0
        assert saved.insider_score == 0.0
        assert saved.total_pnl == 0.0
        assert saved.roi == 0.0

    async def test_profile_unique_wallet(self, session):
        p1 = TraderProfile(wallet_address="0xunique")
        p2 = TraderProfile(wallet_address="0xunique")
        session.add(p1)
        await session.commit()

        session.add(p2)
        with pytest.raises(IntegrityError):
            await session.commit()


class TestMarketModel:
    async def test_create_market(self, session):
        market = Market(
            market_id="cond_abc123",
            question="Will it rain tomorrow?",
            category="Weather",
            suspicion_score=42.0,
        )
        session.add(market)
        await session.commit()

        result = await session.execute(
            select(Market).where(Market.market_id == "cond_abc123")
        )
        saved = result.scalar_one()

        assert saved.question == "Will it rain tomorrow?"
        assert saved.category == "Weather"
        assert saved.suspicion_score == 42.0
        assert saved.is_resolved is False

    async def test_market_defaults(self, session):
        market = Market(market_id="cond_defaults")
        session.add(market)
        await session.commit()

        result = await session.execute(
            select(Market).where(Market.market_id == "cond_defaults")
        )
        saved = result.scalar_one()

        assert saved.is_resolved is False
        assert saved.suspicion_score == 0.0
        assert saved.total_volume == 0.0
        assert saved.suspicious_trades_count == 0
