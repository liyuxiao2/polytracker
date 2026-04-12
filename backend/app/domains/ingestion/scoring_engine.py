"""Insider confidence score calculation algorithms."""
import numpy as np
from datetime import datetime
from app.core.config import get_settings


class ScoringEngine:
    def __init__(self):
        self.settings = get_settings()

    def calculate_roi(self, total_pnl: float, total_volume: float) -> float:
        """Calculate Return on Investment (ROI) percentage."""
        if total_volume == 0:
            return 0.0
        return (total_pnl / total_volume) * 100

    def calculate_profit_factor(self, trades: list) -> float:
        """Calculate Profit Factor (Gross Win / Gross Loss)."""
        gross_win = sum(t.pnl_usd for t in trades if t.pnl_usd and t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in trades if t.pnl_usd and t.pnl_usd < 0))

        if gross_loss == 0:
            return gross_win if gross_win > 0 else 0.0

        return gross_win / gross_loss

    def calculate_insider_score(
        self,
        all_trades: list,
        flagged_trades: list,
        flagged_wins: list,
        win_rate: float,
        outcome_bias: float
    ) -> float:
        """
        Calculate insider confidence score (0-100) using v1 algorithm.

        Components:
        1. Percentage of flagged trades (0-25 points)
        2. Average Z-score of flagged trades (0-20 points)
        3. Recency of flagged trades (0-20 points)
        4. Win rate on flagged trades (0-20 points)
        5. Extreme outcome bias (0-15 points)
        """
        if not all_trades:
            return 0.0

        score = 0.0

        # Component 1: Percentage of flagged trades (0-25 points)
        flagged_percentage = len(flagged_trades) / len(all_trades)
        score += flagged_percentage * 25

        # Component 2: Average Z-score of flagged trades (0-20 points)
        if flagged_trades:
            z_scores = [abs(t.z_score) for t in flagged_trades if t.z_score is not None]
            if z_scores:
                avg_z_score = np.mean(z_scores)
                score += min(avg_z_score / 9 * 20, 20)

        # Component 3: Recency of flagged trades (0-20 points)
        recent_trades = [t for t in all_trades if
                        (datetime.utcnow() - t.timestamp).days <= 7]
        if recent_trades:
            recent_flagged = [t for t in recent_trades if t.is_flagged]
            recent_percentage = len(recent_flagged) / len(recent_trades)
            score += recent_percentage * 20

        # Component 4: Win rate on flagged trades (0-20 points)
        if flagged_trades:
            resolved_flagged = [t for t in flagged_trades if t.is_win is not None]
            if len(resolved_flagged) >= 3:
                flagged_win_rate = len(flagged_wins) / len(resolved_flagged)
                if flagged_win_rate > 0.5:
                    score += (flagged_win_rate - 0.5) * 40

        # Component 5: Extreme outcome bias (0-15 points)
        bias_magnitude = abs(outcome_bias)
        if bias_magnitude > 0.7:
            score += (bias_magnitude - 0.7) * 50

        return min(score, 100.0)

    def calculate_insider_score_v3(
        self,
        trades: list,
        flagged_trades: list,
        win_rate: float,
        wallet_age_days: int,
        market_concentration: float,
        off_hours_trade_pct: float,
        longshot_win_rate: float,
        large_bet_win_rate: float,
        profit_factor: float,
    ) -> float:
        """
        PnL & win-rate-dominant insider score (0-100).

        Components (total 100 points):
        1. Win Rate (0-35 points)
        2. PnL Multiplier / ROI (0-35 points)
        3. Longshot Win Rate (0-15 points)
        4. Large Bet Win Rate (0-5 points)
        5. Market Concentration (0-5 points)
        6. Behavioral Signals (0-5 points)
        """
        if not trades:
            return 0.0

        score = 0.0
        total_trades = len(trades)
        resolved_trades = [t for t in trades if t.is_resolved]
        resolved_count = len(resolved_trades)

        # Calculate ROI
        total_pnl = sum(t.pnl_usd for t in trades if t.pnl_usd is not None)
        total_volume = sum(t.trade_size_usd for t in trades if t.trade_size_usd is not None)
        roi = (total_pnl / total_volume * 100) if total_volume > 0 else 0.0

        # Component 1: Win Rate (0-35 points)
        if resolved_count >= 5:
            if win_rate > 50:
                score += min((win_rate - 50) * 1.0, 35)

        # Component 2: PnL Multiplier / ROI (0-35 points)
        if roi > 50:
            roi_score = 5
            if roi > 200:
                roi_score = 10
            if roi > 500:
                roi_score = 15
            if roi > 1000:
                roi_score = 20
            score += roi_score

        if profit_factor > 2:
            pf_score = 5
            if profit_factor > 5:
                pf_score = 10
            if profit_factor > 10:
                pf_score = 15
            score += pf_score

        # Component 3: Longshot wins (0-15 points)
        longshot_trades = [t for t in trades if t.price and t.price < 0.1 and t.is_win is not None]
        if len(longshot_trades) >= 2:
            if longshot_win_rate > self.settings.longshot_win_rate_low:
                score += min((longshot_win_rate - self.settings.longshot_win_rate_low) * 20, 15)

        # Component 4: Large bet wins (0-5 points)
        avg_bet = np.mean([t.trade_size_usd for t in trades]) if trades else 0
        large_trades = [t for t in trades if t.trade_size_usd > avg_bet * self.settings.avg_bet_deviation_multiplier and t.is_win is not None]
        if len(large_trades) >= 2:
            if large_bet_win_rate > 0.5:
                score += min((large_bet_win_rate - 0.5) * 10, 5)

        # Component 5: Market Concentration (0-5 points)
        if total_trades >= 5 and market_concentration > self.settings.market_concentration_threshold:
            score += min((market_concentration - self.settings.market_concentration_threshold) * 16.6, 5)

        # Component 6: Behavioral Signals (0-5 points)
        behavioral = 0.0

        if wallet_age_days <= 7 and total_trades >= 3:
            behavioral += 2
        elif wallet_age_days <= 14:
            behavioral += 1

        if total_trades > 0:
            flagged_pct = len(flagged_trades) / total_trades
            behavioral += min(flagged_pct * 10, 2)

        if off_hours_trade_pct > 0.5:
            behavioral += 1

        score += min(behavioral, 5)

        return min(score, 100.0)
