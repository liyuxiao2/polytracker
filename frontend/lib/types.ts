export interface TraderListItem {
  wallet_address: string;
  insider_score: number;
  total_trades: number;
  avg_bet_size: number;
  flagged_trades_count: number;
  last_trade_time?: string;
}

export interface TrendingTrade {
  wallet_address: string;
  market_name: string;
  trade_size_usd: number;
  z_score: number;
  timestamp: string;
  deviation_percentage: number;
  is_win: boolean | null;
  flag_reason: string | null;
}

export interface TraderProfile {
  wallet_address: string;
  total_trades: number;
  avg_bet_size: number;
  std_bet_size: number;
  max_bet_size: number;
  total_volume: number;
  insider_score: number;
  last_updated: string;
  flagged_trades_count: number;
}

export interface Trade {
  id: number;
  wallet_address: string;
  market_id: string;
  market_name: string;
  trade_size_usd: number;
  outcome?: string;
  price?: number;
  timestamp: string;
  is_flagged: boolean;
  z_score?: number;
}

export interface DashboardStats {
  total_whales_tracked: number;
  high_signal_alerts_today: number;
  total_trades_monitored: number;
  avg_insider_score: number;
}
