'use client';

import { TrendingUp, AlertTriangle, Activity, Target } from 'lucide-react';
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
      icon: Target,
      color: 'blue',
    },
    {
      title: 'High-Signal Alerts',
      value: stats.high_signal_alerts_today,
      subtitle: 'Today',
      icon: AlertTriangle,
      color: 'red',
    },
    {
      title: 'Total Trades',
      value: stats.total_trades_monitored,
      icon: Activity,
      color: 'green',
    },
    {
      title: 'Avg Insider Score',
      value: stats.avg_insider_score.toFixed(1),
      icon: TrendingUp,
      color: 'yellow',
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
                  {formatNumber(stat.value)}
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
