'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import StatsBar from '@/components/StatsBar';
import TradersTable from '@/components/TradersTable';
import LiveFeed from '@/components/LiveFeed';
import TraderDetail from '@/components/TraderDetail';
import { api } from '@/lib/api';
import { TraderListItem, TrendingTrade, DashboardStats } from '@/lib/types';
import { RefreshCw } from 'lucide-react';

export default function Dashboard() {
  const [activeView, setActiveView] = useState('live-feed');
  const [stats, setStats] = useState<DashboardStats>({
    total_whales_tracked: 0,
    high_signal_alerts_today: 0,
    total_trades_monitored: 0,
    avg_insider_score: 0,
  });
  const [traders, setTraders] = useState<TraderListItem[]>([]);
  const [trendingTrades, setTrendingTrades] = useState<TrendingTrade[]>([]);
  const [selectedTrader, setSelectedTrader] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = async () => {
    try {
      const [statsData, tradersData, tradesData] = await Promise.all([
        api.getDashboardStats(),
        api.getTraders(0, 100),
        api.getTrendingTrades(5000, 24, 100),
      ]);

      setStats(statsData);
      setTraders(tradersData);
      setTrendingTrades(tradesData);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchData();
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleRefresh = () => {
    setLoading(true);
    fetchData();
  };

  if (loading && traders.length === 0) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-950">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex bg-slate-950">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

      <main className="flex-1 overflow-y-auto">
        <div className="p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">
                {activeView === 'live-feed' && 'Live Trade Feed'}
                {activeView === 'top-insiders' && 'Top Insider Traders'}
                {activeView === 'market-watch' && 'Market Overview'}
                {activeView === 'all-traders' && 'All Tracked Traders'}
              </h1>
              <p className="text-slate-400">
                Real-time monitoring of Polymarket trading activity
              </p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-400">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded bg-slate-700 border-slate-600"
                />
                Auto-refresh
              </label>
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-lg transition-colors"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="mb-8">
            <StatsBar stats={stats} />
          </div>

          {/* Content */}
          {activeView === 'live-feed' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <LiveFeed trades={trendingTrades} />
              <div>
                <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
                  <h2 className="text-lg font-semibold text-white mb-4">
                    Top Suspicious Traders
                  </h2>
                  <div className="space-y-3">
                    {traders.slice(0, 10).map((trader) => (
                      <button
                        key={trader.wallet_address}
                        onClick={() => setSelectedTrader(trader.wallet_address)}
                        className="w-full text-left p-4 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <code className="text-sm text-blue-400 font-mono">
                            {trader.wallet_address.slice(0, 10)}...{trader.wallet_address.slice(-8)}
                          </code>
                          <span className="text-lg font-bold text-red-400">
                            {trader.insider_score.toFixed(1)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between mt-2 text-xs text-slate-400">
                          <span>{trader.total_trades} trades</span>
                          <span>{trader.flagged_trades_count} flagged</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {(activeView === 'top-insiders' || activeView === 'all-traders') && (
            <TradersTable
              traders={
                activeView === 'top-insiders'
                  ? traders.filter((t) => t.insider_score >= 50)
                  : traders
              }
              onTraderClick={setSelectedTrader}
            />
          )}

          {activeView === 'market-watch' && (
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 text-center">
              <p className="text-slate-400">Market analytics coming soon...</p>
            </div>
          )}
        </div>
      </main>

      {selectedTrader && (
        <TraderDetail
          address={selectedTrader}
          onClose={() => setSelectedTrader(null)}
        />
      )}
    </div>
  );
}
