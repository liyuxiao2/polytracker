'use client';

import { TrendingTrade } from '@/lib/types';
import { formatCurrency, shortenAddress, formatRelativeTime } from '@/lib/utils';
import { TrendingUp, TrendingDown, Trophy, XCircle, Clock, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

interface LiveFeedProps {
  trades: TrendingTrade[];
  page: number;
  setPage: (page: number) => void;
  sortBy: string;
  setSortBy: (sort: string) => void;
  sortOrder: string;
  setSortOrder: (order: string) => void;
}

export default function LiveFeed({ 
  trades, 
  page, 
  setPage, 
  sortBy, 
  setSortBy, 
  sortOrder, 
  setSortOrder 
}: LiveFeedProps) {
  const getWinLossBadge = (isWin: boolean | null | undefined) => {
    if (isWin === null || isWin === undefined) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-slate-600/50 text-slate-300">
          <Clock className="h-3 w-3" />
          Pending
        </span>
      );
    }
    if (isWin) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          <Trophy className="h-3 w-3" />
          Won
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
        <XCircle className="h-3 w-3" />
        Lost
      </span>
    );
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-700 bg-slate-900">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Live Trade Feed</h2>
            <p className="text-sm text-slate-400 mt-1">Real-time high-value and anomalous trades</p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <select 
                value={sortBy}
                onChange={(e) => {
                    setSortBy(e.target.value);
                    setPage(1);
                }}
                className="bg-slate-800 text-slate-200 text-xs rounded px-2 py-1.5 border border-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="timestamp">Time</option>
                <option value="size">Size</option>
                <option value="z_score">Z-Score</option>
                <option value="win_loss">Win/Loss</option>
                <option value="deviation">Deviation</option>
              </select>
              <button 
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors border border-slate-600"
                title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
              >
                <ArrowUpDown className="h-3 w-3" />
              </button>
            </div>

            <div className="flex items-center gap-1 bg-slate-800 rounded border border-slate-600 p-0.5">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="p-1 hover:bg-slate-700 rounded text-slate-400 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="h-3 w-3" />
              </button>
              <span className="text-xs text-slate-400 font-mono px-2">{page}</span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={trades.length < 50}
                className="p-1 hover:bg-slate-700 rounded text-slate-400 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="divide-y divide-slate-700 max-h-[600px] overflow-y-auto">
        {trades.map((trade, idx) => (
          <div
            key={`${trade.wallet_address}-${trade.timestamp}-${idx}`}
            className={`px-6 py-4 hover:bg-slate-700/50 transition-colors ${
              trade.is_win === true ? 'border-l-2 border-l-emerald-500' : 
              trade.is_win === false ? 'border-l-2 border-l-red-500' : ''
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <code className="text-sm text-blue-400 font-mono">
                    {shortenAddress(trade.wallet_address)}
                  </code>
                  {/* BUY/SELL Badge */}
                  {trade.side && (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      trade.side === 'BUY'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                    }`}>
                      {trade.side === 'BUY' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                      {trade.side}
                    </span>
                  )}
                  {/* YES/NO Outcome Badge */}
                  {trade.outcome && (
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      trade.outcome === 'YES'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    }`}>
                      {trade.outcome}
                    </span>
                  )}
                  {getWinLossBadge(trade.is_win)}
                  {trade.deviation_percentage > 0 ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/10 text-red-400">
                      <TrendingUp className="h-3 w-3" />
                      +{trade.deviation_percentage.toFixed(0)}%
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-500/10 text-green-400">
                      <TrendingDown className="h-3 w-3" />
                      {trade.deviation_percentage.toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-300 mb-1">{trade.market_name}</p>
                <p className="text-xs text-slate-500">{formatRelativeTime(trade.timestamp)}</p>
              </div>
              <div className="text-right">
                <p className={`text-lg font-bold ${
                  trade.is_win === true ? 'text-emerald-400' :
                  trade.is_win === false ? 'text-red-400' : 'text-white'
                }`}>
                  {formatCurrency(trade.trade_size_usd)}
                </p>
                {trade.pnl_usd !== null && trade.pnl_usd !== undefined && (
                  <p className={`text-sm font-medium ${
                    trade.pnl_usd >= 0 ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {trade.pnl_usd >= 0 ? '+' : ''}{formatCurrency(trade.pnl_usd)}
                  </p>
                )}
                <p className="text-xs text-slate-400 mt-1">
                  Z-Score: {trade.z_score.toFixed(2)}
                  {trade.price && ` @ ${(trade.price * 100).toFixed(0)}%`}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {trades.length === 0 && (
        <div className="text-center py-12">
          <p className="text-slate-400">No recent trades</p>
        </div>
      )}
    </div>
  );
}
