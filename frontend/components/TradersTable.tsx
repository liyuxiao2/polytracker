'use client';

import { useState } from 'react';
import { ArrowUpDown, ExternalLink } from 'lucide-react';
import { TraderListItem } from '@/lib/types';
import { formatCurrency, shortenAddress, getScoreColor, getScoreBgColor, formatRelativeTime } from '@/lib/utils';
import { cn } from '@/lib/utils';

interface TradersTableProps {
  traders: TraderListItem[];
  onTraderClick: (address: string) => void;
}

type SortField = 'insider_score' | 'total_trades' | 'avg_bet_size' | 'flagged_trades_count' | 'win_rate' | 'total_pnl';
type SortDirection = 'asc' | 'desc';

export default function TradersTable({ traders, onTraderClick }: TradersTableProps) {
  const [sortField, setSortField] = useState<SortField>('insider_score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const sortedTraders = [...traders].sort((a, b) => {
    const multiplier = sortDirection === 'asc' ? 1 : -1;
    return (a[sortField] - b[sortField]) * multiplier;
  });

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-900">
            <tr>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('insider_score')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Insider Score
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Wallet Address
              </th>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('total_trades')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Total Trades
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('avg_bet_size')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Avg Bet Size
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('flagged_trades_count')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Flagged Trades
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('win_rate')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Win Rate
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left">
                <button
                  onClick={() => handleSort('total_pnl')}
                  className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider hover:text-white"
                >
                  Total PnL
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Last Trade
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {sortedTraders.map((trader) => (
              <tr
                key={trader.wallet_address}
                className="hover:bg-slate-700/50 cursor-pointer transition-colors"
                onClick={() => onTraderClick(trader.wallet_address)}
              >
                <td className="px-6 py-4">
                  <div className={cn(
                    'inline-flex items-center px-3 py-1 rounded-full border text-sm font-bold',
                    getScoreBgColor(trader.insider_score)
                  )}>
                    <span className={getScoreColor(trader.insider_score)}>
                      {trader.insider_score.toFixed(1)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <code className="text-sm text-blue-400 font-mono">
                    {shortenAddress(trader.wallet_address)}
                  </code>
                </td>
                <td className="px-6 py-4 text-sm text-slate-300">
                  {trader.total_trades}
                </td>
                <td className="px-6 py-4 text-sm font-semibold text-white">
                  {formatCurrency(trader.avg_bet_size)}
                </td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400">
                    {trader.flagged_trades_count}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className={cn(
                    "text-sm font-medium",
                    trader.win_rate >= 60 ? "text-emerald-400" :
                    trader.win_rate >= 40 ? "text-slate-300" : "text-red-400"
                  )}>
                    {trader.win_rate.toFixed(1)}%
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className={cn(
                    "text-sm font-semibold",
                    trader.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"
                  )}>
                    {trader.total_pnl >= 0 ? '+' : ''}{formatCurrency(trader.total_pnl)}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-slate-400">
                  {trader.last_trade_time ? formatRelativeTime(trader.last_trade_time) : 'N/A'}
                </td>
                <td className="px-6 py-4">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onTraderClick(trader.wallet_address);
                    }}
                    className="text-blue-400 hover:text-blue-300"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sortedTraders.length === 0 && (
        <div className="text-center py-12">
          <p className="text-slate-400">No traders found</p>
        </div>
      )}
    </div>
  );
}
