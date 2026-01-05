'use client';

import { TrendingTrade } from '@/lib/types';
import { formatCurrency, shortenAddress, formatRelativeTime } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface LiveFeedProps {
  trades: TrendingTrade[];
}

export default function LiveFeed({ trades }: LiveFeedProps) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-700 bg-slate-900">
        <h2 className="text-lg font-semibold text-white">Live Trade Feed</h2>
        <p className="text-sm text-slate-400 mt-1">Real-time high-value and anomalous trades</p>
      </div>

      <div className="divide-y divide-slate-700 max-h-[600px] overflow-y-auto">
        {trades.map((trade, idx) => (
          <div
            key={`${trade.wallet_address}-${trade.timestamp}-${idx}`}
            className="px-6 py-4 hover:bg-slate-700/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <code className="text-sm text-blue-400 font-mono">
                    {shortenAddress(trade.wallet_address)}
                  </code>
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
                <p className="text-lg font-bold text-white">
                  {formatCurrency(trade.trade_size_usd)}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Z-Score: {trade.z_score.toFixed(2)}
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
