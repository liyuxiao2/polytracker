'use client';

import { Target, Trophy, DollarSign, TrendingUp } from 'lucide-react';
import { DashboardStats } from '@/lib/types';
import { formatNumber, formatCurrency } from '@/lib/utils';

interface StatsBarProps {
  stats: DashboardStats;
}

export default function StatsBar({ stats }: StatsBarProps) {
  // Format volume for display (e.g., $1.2M, $500K)
  const formatVolume = (value: number) => {
    if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`;
    } else if (value >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`;
    }
    return formatCurrency(value);
  };

  const statCards = [
    {
      title: 'Whales Tracked',
      value: stats.total_whales_tracked,
      decimals: 0,
      icon: Target,
      color: 'blue',
    },
    {
      title: '24h Volume',
      value: stats.total_volume_24h,
      decimals: 0,
      displayValue: formatVolume(stats.total_volume_24h),
      icon: TrendingUp,
      color: 'green',
    },
    {
      title: 'Flagged Win Rate',
      value: stats.avg_win_rate,
      decimals: 1,
      subtitle: `${stats.total_resolved_trades} resolved`,
      icon: Trophy,
      color: 'yellow',
      suffix: '%',
    },
    {
      title: 'Flagged PnL',
      value: stats.total_pnl_flagged,
      decimals: 0,
      displayValue: formatVolume(stats.total_pnl_flagged),
      subtitle: `${stats.high_signal_alerts_today} alerts today`,
      icon: DollarSign,
      color: stats.total_pnl_flagged >= 0 ? 'green' : 'red',
    },
  ];

  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-500',
    red: 'bg-red-500/10 text-red-500',
    green: 'bg-green-500/10 text-green-500',
    yellow: 'bg-yellow-500/10 text-yellow-500',
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {statCards.map((stat) => {
        const Icon = stat.icon;
        return (
          <div
            key={stat.title}
            className="bg-slate-800 border border-slate-700 rounded-lg p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider">
                  {stat.title}
                </p>
                <p className="text-3xl font-bold text-white mt-2">
                  {('displayValue' in stat) ? stat.displayValue : formatNumber(stat.value, stat.decimals)}{('suffix' in stat) ? stat.suffix : ''}
                </p>
                {stat.subtitle && (
                  <p className="text-xs text-slate-500 mt-1">{stat.subtitle}</p>
                )}
              </div>
              <div
                className={`h-12 w-12 rounded-lg flex items-center justify-center ${
                  colorClasses[stat.color as keyof typeof colorClasses]
                }`}
              >
                <Icon className="h-6 w-6" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
