'use client';

import { useEffect, useState } from 'react';
import { X, TrendingUp, DollarSign, Activity, AlertCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { TraderProfile, Trade } from '@/lib/types';
import { api } from '@/lib/api';
import { formatCurrency, shortenAddress, getScoreColor, formatRelativeTime } from '@/lib/utils';

interface TraderDetailProps {
  address: string;
  onClose: () => void;
}

export default function TraderDetail({ address, onClose }: TraderDetailProps) {
  const [profile, setProfile] = useState<TraderProfile | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [profileData, tradesData] = await Promise.all([
          api.getTraderProfile(address),
          api.getTraderTrades(address, 100),
        ]);
        setProfile(profileData);
        setTrades(tradesData);
      } catch (error) {
        console.error('Error fetching trader data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [address]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-slate-800 rounded-lg p-8">
          <div className="animate-pulse text-white">Loading...</div>
        </div>
      </div>
    );
  }

  if (!profile) {
    return null;
  }

  const chartData = trades
    .slice()
    .reverse()
    .map((trade, idx) => ({
      index: idx,
      tradeSize: trade.trade_size_usd,
      timestamp: new Date(trade.timestamp).toLocaleDateString(),
      isFlagged: trade.is_flagged,
    }));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-900 border-b border-slate-700 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">Trader Profile</h2>
            <code className="text-sm text-blue-400 font-mono">{address}</code>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Stats Grid */}
        <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-blue-400" />
              <p className="text-xs text-slate-400 uppercase">Insider Score</p>
            </div>
            <p className={`text-2xl font-bold ${getScoreColor(profile.insider_score)}`}>
              {profile.insider_score.toFixed(1)}
            </p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-green-400" />
              <p className="text-xs text-slate-400 uppercase">Total Trades</p>
            </div>
            <p className="text-2xl font-bold text-white">{profile.total_trades}</p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="h-4 w-4 text-yellow-400" />
              <p className="text-xs text-slate-400 uppercase">Avg Bet Size</p>
            </div>
            <p className="text-2xl font-bold text-white">
              {formatCurrency(profile.avg_bet_size)}
            </p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="h-4 w-4 text-red-400" />
              <p className="text-xs text-slate-400 uppercase">Flagged Trades</p>
            </div>
            <p className="text-2xl font-bold text-white">{profile.flagged_trades_count}</p>
          </div>
        </div>

        {/* Chart */}
        <div className="px-6 pb-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Bet Size Over Time</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="timestamp"
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                  />
                  <YAxis
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                    tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#fff',
                    }}
                    formatter={(value: any) => [formatCurrency(value), 'Trade Size']}
                  />
                  <ReferenceLine
                    y={profile.avg_bet_size}
                    stroke="#22d3ee"
                    strokeDasharray="5 5"
                    label={{ value: 'Baseline', fill: '#22d3ee', fontSize: 12 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="tradeSize"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={(props: any) => {
                      const { cx, cy, payload } = props;
                      return (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={payload.isFlagged ? 6 : 4}
                          fill={payload.isFlagged ? '#ef4444' : '#3b82f6'}
                          stroke={payload.isFlagged ? '#dc2626' : '#2563eb'}
                          strokeWidth={2}
                        />
                      );
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 flex items-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-blue-500"></div>
                <span className="text-slate-400">Normal Trade</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500"></div>
                <span className="text-slate-400">Flagged Trade</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-0.5 w-8 bg-cyan-400"></div>
                <span className="text-slate-400">Baseline ({formatCurrency(profile.avg_bet_size)})</span>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Trades */}
        <div className="px-6 pb-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Recent Trades</h3>
            </div>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full">
                <thead className="bg-slate-900 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase">
                      Market
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase">
                      Trade Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase">
                      Z-Score
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase">
                      Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {trades.slice(0, 20).map((trade) => (
                    <tr key={trade.id} className="hover:bg-slate-700/50">
                      <td className="px-6 py-4 text-sm text-slate-300 max-w-xs truncate">
                        {trade.market_name}
                      </td>
                      <td className="px-6 py-4 text-sm font-semibold text-white">
                        {formatCurrency(trade.trade_size_usd)}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">
                        {trade.z_score?.toFixed(2) || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {formatRelativeTime(trade.timestamp)}
                      </td>
                      <td className="px-6 py-4">
                        {trade.is_flagged ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400">
                            Flagged
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-700 text-slate-400">
                            Normal
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
