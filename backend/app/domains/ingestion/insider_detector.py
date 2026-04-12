"""
Insider detection facade — delegates to focused modules.

This module preserves the original InsiderDetector API so existing callers
(data_ingestion_service, resolution_worker, traders/service, markets/service)
continue to work unchanged.
"""
from app.domains.ingestion.anomaly_detector import AnomalyDetector
from app.domains.ingestion.scoring_engine import ScoringEngine
from app.domains.ingestion.wallet_analyzer import WalletAnalyzer
from app.domains.ingestion.profile_updater import ProfileUpdater


class InsiderDetector:
    """Facade that composes anomaly detection, scoring, wallet analysis, and profile updates."""

    def __init__(self, z_score_threshold: float = None):
        self._anomaly = AnomalyDetector(z_score_threshold=z_score_threshold)
        self._scoring = ScoringEngine()
        self._wallet = WalletAnalyzer()
        self._profile = ProfileUpdater()

        # Expose settings and threshold for callers that read them
        self.z_score_threshold = self._anomaly.z_score_threshold
        self.settings = self._anomaly.settings

    # ── Anomaly detection ──
    async def calculate_z_score(self, wallet_address, trade_size, session, tracked_markets=None):
        return await self._anomaly.calculate_z_score(wallet_address, trade_size, session, tracked_markets=tracked_markets)

    async def get_trending_trades(self, session, min_size=10000, hours=24):
        return await self._anomaly.get_trending_trades(session, min_size, hours)

    async def detect_coordinated_trading(self, market_id, session, window_seconds=300):
        return await self._anomaly.detect_coordinated_trading(market_id, session, window_seconds)

    # ── Wallet analysis ──
    async def evaluate_trade_for_insider_activity(self, trade, session):
        return await self._wallet.evaluate_trade_for_insider_activity(trade, session)

    async def analyze_wallet_signals(self, wallet_address, session):
        return await self._wallet.analyze_wallet_signals(wallet_address, session)

    def is_new_wallet_large_bet(self, wallet_age_days, trade_size_usd, threshold_days=7, threshold_usd=10000):
        return self._wallet.is_new_wallet_large_bet(wallet_age_days, trade_size_usd, threshold_days, threshold_usd)

    def is_concentrated_trader(self, unique_markets, total_trades, market_concentration, min_trades=10):
        return self._wallet.is_concentrated_trader(unique_markets, total_trades, market_concentration, min_trades)

    def is_suspicious_timing(self, hours_before_resolution, threshold_hours=None):
        return self._wallet.is_suspicious_timing(hours_before_resolution, threshold_hours)

    def is_off_hours_trader(self, off_hours_pct, threshold=0.5):
        return self._wallet.is_off_hours_trader(off_hours_pct, threshold)

    def is_longshot_winner(self, longshot_win_rate, min_longshot_trades=5, threshold=None):
        return self._wallet.is_longshot_winner(longshot_win_rate, min_longshot_trades, threshold)

    # ── Profile updates ──
    async def update_trader_profile(self, wallet_address, session, tracked_markets=None):
        return await self._profile.update_trader_profile(wallet_address, session, tracked_markets=tracked_markets)

    # ── Scoring (exposed for direct access if needed) ──
    def _calculate_insider_score(self, all_trades, flagged_trades, flagged_wins, win_rate, outcome_bias):
        return self._scoring.calculate_insider_score(all_trades, flagged_trades, flagged_wins, win_rate, outcome_bias)

    def _calculate_insider_score_v3(self, **kwargs):
        return self._scoring.calculate_insider_score_v3(**kwargs)

    def _calculate_roi(self, total_pnl, total_volume):
        return self._scoring.calculate_roi(total_pnl, total_volume)

    def _calculate_profit_factor(self, trades):
        return self._scoring.calculate_profit_factor(trades)
