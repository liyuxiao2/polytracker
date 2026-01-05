'use client';

import { Activity, TrendingUp, Users, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

const navigation = [
  { name: 'Live Feed', icon: Activity, id: 'live-feed' },
  { name: 'Top Insiders', icon: TrendingUp, id: 'top-insiders' },
  { name: 'Market Watch', icon: BarChart3, id: 'market-watch' },
  { name: 'All Traders', icon: Users, id: 'all-traders' },
];

export default function Sidebar({ activeView, onViewChange }: SidebarProps) {
  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart3 className="h-8 w-8 text-blue-500" />
          PolyEdge
        </h1>
        <p className="text-xs text-slate-400 mt-1">Insider Detection Dashboard</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className="bg-slate-800 rounded-lg p-4">
          <p className="text-xs text-slate-400">Status</p>
          <div className="flex items-center gap-2 mt-2">
            <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-white">Live Monitoring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
