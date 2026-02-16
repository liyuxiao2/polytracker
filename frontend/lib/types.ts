export interface TraderListItem {
  wallet_address: string;
  insider_score: number;
  total_trades: number;
  avg_bet_size: number;
  win_rate: number;
  total_pnl: number;
  flagged_trades_count: number;
  flagged_wins_count: number;
  last_trade_time?: string;
}

export interface TrendingTrade {
  wallet_address: string;
  market_name: string;
  market_slug?: string;
  trade_size_usd: number;
  z_score: number;
  timestamp: string;
  deviation_percentage: number;
  is_win: boolean | null;
  flag_reason?: string;
  // Trade direction and outcome
  outcome?: string; // YES or NO
  side?: string; // BUY or SELL
  price?: number;
  pnl_usd?: number;
}

export interface TraderProfile {
  wallet_address: string;
  total_trades: number;
  resolved_trades: number;
  winning_trades: number;
  avg_bet_size: number;
  std_bet_size: number;
  max_bet_size: number;
  total_volume: number;
  total_pnl: number;
  insider_score: number;
  last_updated: string;
  flagged_trades_count: number;
  win_rate: number;
  flagged_wins_count: number;
  // Outcome bias tracking
  total_yes_bets: number;
  total_no_bets: number;
  outcome_bias: number;
  roi?: number;
  profit_factor?: number;
  // Buy/Sell tracking
  total_buys: number;
  total_sells: number;
}

export interface Trade {
  id: number;
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
  transaction_hash?: string;
}

export interface DashboardStats {
  total_whales_tracked: number;
  high_signal_alerts_today: number;
  total_trades_monitored: number;
  avg_insider_score: number;
  total_resolved_trades: number;
  avg_win_rate: number;
  // Volume and PnL stats
  total_volume_24h: number;
  total_pnl_flagged: number;
}

export interface MarketWatchItem {
  market_slug: string;
  market_id: string;
  question: string;
  category?: string;
  suspicious_trades_count: number;
  total_trades_count: number;
  total_volume: number;
  unique_traders_count: number;
  current_yes_price?: number;
  current_no_price?: number;
  price_change_24h?: number;
  volatility_score: number;
  suspicion_score: number;
  is_resolved: boolean;
  end_date?: string;
  metrics_updated_at?: string;
}
