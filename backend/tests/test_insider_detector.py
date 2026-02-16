import pytest
import numpy as np
from datetime import datetime, timedelta

from app.models.database import Trade, TraderProfile
from app.services.insider_detector import InsiderDetector


class TestZScoreCalculation:
    async def test_z_score_with_history(self, session):
        """Z-score should be calculated correctly from trade history."""
        detector = InsiderDetector(z_score_threshold=3.0)
        wallet = "0xzscore_test"

        # Create history of consistent $1000 trades (mean=1000, std~0)
        for i in range(10):
            session.add(Trade(
                wallet_address=wallet,
                market_id="m1",
                market_name="Test",
                trade_size_usd=1000.0,
                timestamp=datetime(2025, 1, 1, i),
            ))
        await session.commit()

        # A $1000 trade should have z_score ~0
        z_score, is_anomaly = await detector.calculate_z_score(wallet, 1000.0, session)
        assert abs(z_score) < 0.1
        assert is_anomaly is False

    async def test_z_score_anomaly_detection(self, session):
        """Trades far from the mean should be flagged as anomalies."""
        detector = InsiderDetector(z_score_threshold=3.0)
        wallet = "0xanomaly_test"

        # Create varied history
        sizes = [100, 150, 120, 130, 110, 140, 125, 135, 115, 145]
        for i, size in enumerate(sizes):
            session.add(Trade(
                wallet_address=wallet,
                market_id="m1",
                market_name="Test",
                trade_size_usd=float(size),
                timestamp=datetime(2025, 1, 1, i),
            ))
        await session.commit()

        mean = np.mean(sizes)
        std = np.std(sizes)

        # A massive trade should be flagged
        huge_trade = mean + (std * 5)  # 5 standard deviations
        z_score, is_anomaly = await detector.calculate_z_score(wallet, huge_trade, session)
        assert abs(z_score) > 3.0
        assert is_anomaly

    async def test_z_score_insufficient_history(self, session):
        """With <3 trades, should use simple threshold."""
        detector = InsiderDetector()
        wallet = "0xnewwallet"

        # Only 2 trades - not enough for z-score
        for i in range(2):
            session.add(Trade(
                wallet_address=wallet,
                market_id="m1",
                market_name="Test",
                trade_size_usd=500.0,
                timestamp=datetime(2025, 1, 1, i),
            ))
        await session.commit()

        z_score, is_anomaly = await detector.calculate_z_score(wallet, 500.0, session)
        assert z_score == 0.0
        # Small trade should not be flagged
        assert is_anomaly is False

        # Large trade should be flagged with fallback threshold
        z_score, is_anomaly = await detector.calculate_z_score(wallet, 15000.0, session)
        assert z_score == 0.0
        assert is_anomaly is True  # > $10k threshold

    async def test_z_score_zero_std(self, session):
        """All identical trades should return z=0, not divide by zero."""
        detector = InsiderDetector()
        wallet = "0xidentical"

        # All trades are exactly $500
        for i in range(5):
            session.add(Trade(
                wallet_address=wallet,
                market_id="m1",
                market_name="Test",
                trade_size_usd=500.0,
                timestamp=datetime(2025, 1, 1, i),
            ))
        await session.commit()

        z_score, is_anomaly = await detector.calculate_z_score(wallet, 500.0, session)
        assert z_score == 0.0
        assert is_anomaly is False


class TestEvaluateTradeForInsiderActivity:
    async def test_already_flagged_skipped(self, session):
        """Already flagged trades should not be re-evaluated."""
        detector = InsiderDetector()
        trade = Trade(
            wallet_address="0xflagged",
            market_id="m1",
            market_name="Test",
            trade_size_usd=50000.0,
            is_flagged=True,
            is_win=True,
            pnl_usd=100000.0,
        )
        session.add(trade)
        await session.commit()

        should_flag, reason = await detector.evaluate_trade_for_insider_activity(trade, session)
        assert should_flag is False
        assert reason is None

    async def test_losing_trade_skipped(self, session):
        """Losing trades should not be flagged post-resolution."""
        detector = InsiderDetector()
        trade = Trade(
            wallet_address="0xloser",
            market_id="m1",
            market_name="Test",
            trade_size_usd=50000.0,
            is_win=False,
            pnl_usd=-50000.0,
        )
        session.add(trade)
        await session.commit()

        should_flag, reason = await detector.evaluate_trade_for_insider_activity(trade, session)
        assert should_flag is False

    async def test_large_winning_bet_flagged(self, session):
        """Large winning bets (>$25k profit) should be flagged."""
        detector = InsiderDetector()
        trade = Trade(
            wallet_address="0xbigwin",
            market_id="m1",
            market_name="Test",
            trade_size_usd=50000.0,
            is_win=True,
            pnl_usd=30000.0,
        )
        session.add(trade)
        await session.commit()

        should_flag, reason = await detector.evaluate_trade_for_insider_activity(trade, session)
        assert should_flag is True
        assert "Large winning bet" in reason

    async def test_high_conviction_bet_flagged(self, session):
        """Winning bets at very low odds (<10%) should be flagged."""
        detector = InsiderDetector()
        trade = Trade(
            wallet_address="0xlongshot",
            market_id="m1",
            market_name="Test",
            trade_size_usd=5000.0,
            price=0.05,  # 5% odds
            is_win=True,
            pnl_usd=10000.0,
        )
        session.add(trade)
        await session.commit()

        should_flag, reason = await detector.evaluate_trade_for_insider_activity(trade, session)
        assert should_flag is True
        assert "High conviction" in reason


class TestUpdateTraderProfile:
    async def test_create_profile_from_trades(self, session):
        """update_trader_profile should create a profile from existing trades."""
        detector = InsiderDetector()
        wallet = "0xnewprofile"

        # Create some trades
        for i in range(5):
            session.add(Trade(
                wallet_address=wallet,
                market_id=f"m{i}",
                market_name=f"Market {i}",
                trade_size_usd=1000.0 * (i + 1),
                timestamp=datetime(2025, 1, 1, i),
                outcome="YES" if i % 2 == 0 else "NO",
                side="BUY",
            ))
        await session.commit()

        profile = await detector.update_trader_profile(wallet, session)

        assert profile is not None
        assert profile.wallet_address == wallet
        assert profile.total_trades == 5
        assert profile.avg_bet_size > 0
        assert profile.total_volume == sum(1000.0 * (i + 1) for i in range(5))

    async def test_update_existing_profile(self, session):
        """Should update an existing profile with new data."""
        detector = InsiderDetector()
        wallet = "0xupdateprofile"

        # Create initial profile
        profile = TraderProfile(
            wallet_address=wallet,
            total_trades=2,
            avg_bet_size=500.0,
            std_bet_size=0.0,
            max_bet_size=500.0,
            total_volume=1000.0,
            insider_score=0.0,
            flagged_trades_count=0,
        )
        session.add(profile)

        # Create trades
        for i in range(5):
            session.add(Trade(
                wallet_address=wallet,
                market_id=f"m{i}",
                market_name=f"Market {i}",
                trade_size_usd=1000.0,
                timestamp=datetime(2025, 1, 1, i),
                side="BUY",
            ))
        await session.commit()

        updated = await detector.update_trader_profile(wallet, session)
        assert updated is not None
        assert updated.total_trades == 5

    async def test_no_trades_returns_none(self, session):
        """If wallet has no trades, should return None."""
        detector = InsiderDetector()
        profile = await detector.update_trader_profile("0xghostwallet", session)
        assert profile is None


class TestInsiderDetectorHelpers:
    def test_calculate_roi(self):
        detector = InsiderDetector()
        assert detector._calculate_roi(1000.0, 10000.0) == 10.0
        assert detector._calculate_roi(-500.0, 10000.0) == -5.0
        assert detector._calculate_roi(0.0, 0.0) == 0.0

    def test_calculate_profit_factor(self):
        detector = InsiderDetector()
        # No trades = 0
        assert detector._calculate_profit_factor([]) == 0.0
