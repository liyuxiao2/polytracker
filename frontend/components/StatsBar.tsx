'use client';

import { AlertTriangle, Activity, Target, Trophy } from 'lucide-react';
import { DashboardStats } from '@/lib/types';
import { formatNumber } from '@/lib/utils';

interface StatsBarProps {
  stats: DashboardStats;
}

export default function StatsBar({ stats }: StatsBarProps) {
  const statCards = [
    {
      title: 'Whales Tracked',
      value: stats.total_whales_tracked,
      decimals: 0,
      icon: Target,
      color: 'blue',
    },
    {
      title: 'Resolved Trades',
      value: stats.total_resolved_trades,
      decimals: 0,
      subtitle: 'Won/Lost Known',
      icon: Activity,
      color: 'green',
    },
    {
      title: 'Flagged Win Rate',
      value: stats.avg_win_rate,
      decimals: 1,
      subtitle: 'Flagged Trades',
      icon: Trophy,
      color: 'yellow',
      suffix: '%',
    },
    {
      title: 'Alerts Today',
      value: stats.high_signal_alerts_today,
      decimals: 0,
      icon: AlertTriangle,
      color: 'red',
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
                  {formatNumber(stat.value, stat.decimals)}{('suffix' in stat) ? stat.suffix : ''}
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
