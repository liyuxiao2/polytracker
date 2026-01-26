"use client";

import { useState, useEffect } from "react";
import { MarketWatchItem, Trade } from "@/lib/types";
import { api } from "@/lib/api";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

const CATEGORIES = [
  "All",
  "NBA",
  "NFL",
  "Politics",
  "Crypto",
  "Business",
  "Entertainment",
  "Science",
  "Sports",
  "Other",
];

type SortBy =
  | "suspicion_score"
  | "volatility_score"
  | "total_volume"
  | "suspicious_trades_count";

export default function MarketWatch() {
  const [markets, setMarkets] = useState<MarketWatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [sortBy, setSortBy] = useState<SortBy>("suspicion_score");

  // Expansion state
  const [expandedMarketId, setExpandedMarketId] = useState<string | null>(null);
  const [marketTrades, setMarketTrades] = useState<Trade[]>([]);
  const [loadingTrades, setLoadingTrades] = useState(false);

  useEffect(() => {
    fetchMarkets();
    const interval = setInterval(fetchMarkets, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [selectedCategory, sortBy]);

  const fetchMarkets = async () => {
    try {
      const data = await api.getMarketWatch(
        selectedCategory,
        sortBy,
        "desc",
        50,
      );
      setMarkets(data);
    } catch (error) {
      console.error("Error fetching markets:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleExpand = async (marketId: string) => {
    if (expandedMarketId === marketId) {
      setExpandedMarketId(null);
      setMarketTrades([]);
      return;
    }

    setExpandedMarketId(marketId);
    setLoadingTrades(true);
    try {
      const trades = await api.getMarketTrades(marketId, 20);
      setMarketTrades(trades);
    } catch (error) {
      console.error("Error fetching market trades:", error);
    } finally {
      setLoadingTrades(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value: number | undefined) => {
    if (value === undefined || value === null) return "N/A";
    return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-red-400";
    if (score >= 40) return "text-orange-400";
    return "text-yellow-400";
  };

  const getCategoryColor = (category: string | undefined) => {
    const colors: { [key: string]: string } = {
      NBA: "bg-orange-500/20 text-orange-300",
      NFL: "bg-green-500/20 text-green-300",
      Politics: "bg-blue-500/20 text-blue-300",
      Crypto: "bg-purple-500/20 text-purple-300",
      Business: "bg-cyan-500/20 text-cyan-300",
      Entertainment: "bg-pink-500/20 text-pink-300",
      Science: "bg-teal-500/20 text-teal-300",
      Sports: "bg-yellow-500/20 text-yellow-300",
      Other: "bg-slate-500/20 text-slate-300",
    };
    return colors[category || "Other"] || colors["Other"];
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading markets...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-center justify-between">
        {/* Category Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-400">Category:</span>
          <div className="flex gap-2 flex-wrap">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1 rounded-md text-sm transition-colors ${
                  selectedCategory === cat
                    ? "bg-blue-500 text-white"
                    : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Sort By */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-400">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
            className="bg-slate-700 text-slate-200 rounded-md px-3 py-1 text-sm border border-slate-600"
          >
            <option value="suspicion_score">Suspicion Score</option>
            <option value="volatility_score">Volatility</option>
            <option value="total_volume">Volume</option>
            <option value="suspicious_trades_count">Suspicious Trades</option>
          </select>
        </div>
      </div>

      {/* Markets List */}
      {markets.length === 0 ? (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 text-center">
          <p className="text-slate-400">
            No markets found. The market watch worker may need to run first.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {markets.map((market) => (
            <div
              key={market.market_id}
              className={`bg-slate-800 border ${
                expandedMarketId === market.market_id
                  ? "border-blue-500/50"
                  : "border-slate-700 hover:border-slate-600"
              } rounded-lg transition-all duration-200 overflow-hidden`}
            >
              <div
                className="p-4 cursor-pointer"
                onClick={() => handleExpand(market.market_id)}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* Left: Market Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      {market.category && (
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${getCategoryColor(market.category)}`}
                        >
                          {market.category}
                        </span>
                      )}
                    </div>
                    <div className="flex items-start gap-2">
                      {expandedMarketId === market.market_id ? (
                        <ChevronUp className="w-5 h-5 text-slate-400 mt-1 flex-shrink-0" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-slate-400 mt-1 flex-shrink-0" />
                      )}
                      <h3 className="text-slate-100 font-medium mb-2 line-clamp-2">
                        {market.question}
                      </h3>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-400 ml-7">
                      <span>{market.total_trades_count} trades</span>
                      <span>{market.unique_traders_count} traders</span>
                      <span>{formatCurrency(market.total_volume)} volume</span>
                    </div>
                  </div>

                  {/* Right: Metrics */}
                  <div className="flex flex-col items-end gap-2">
                    {/* Suspicion Score */}
                    <div className="text-right">
                      <div className="text-xs text-slate-400 mb-1">
                        Suspicion
                      </div>
                      <div
                        className={`text-2xl font-bold ${getScoreColor(market.suspicion_score)}`}
                      >
                        {market.suspicion_score.toFixed(0)}
                      </div>
                    </div>

                    {/* Additional Metrics */}
                    <div className="flex gap-4 text-sm">
                      {/* Volatility */}
                      <div className="text-right">
                        <div className="text-xs text-slate-400">Volatility</div>
                        <div className="text-slate-200 font-medium">
                          {market.volatility_score.toFixed(1)}%
                        </div>
                      </div>

                      {/* Price Change */}
                      {market.price_change_24h !== undefined &&
                        market.price_change_24h !== null && (
                          <div className="text-right">
                            <div className="text-xs text-slate-400">
                              24h Change
                            </div>
                            <div
                              className={`font-medium ${
                                market.price_change_24h > 0
                                  ? "text-green-400"
                                  : market.price_change_24h < 0
                                    ? "text-red-400"
                                    : "text-slate-400"
                              }`}
                            >
                              {formatPercent(market.price_change_24h)}
                            </div>
                          </div>
                        )}
                    </div>

                    {/* Suspicious Trades Badge */}
                    {market.suspicious_trades_count > 0 && (
                      <div className="bg-red-500/20 text-red-400 px-2 py-1 rounded text-xs font-medium">
                        {market.suspicious_trades_count} suspicious trade
                        {market.suspicious_trades_count !== 1 ? "s" : ""}
                      </div>
                    )}

                    {/* Current Prices */}
                    {market.current_yes_price !== undefined &&
                      market.current_yes_price !== null && (
                        <div className="text-xs text-slate-400">
                          YES: {(market.current_yes_price * 100).toFixed(1)}¢
                          {market.current_no_price !== undefined &&
                            market.current_no_price !== null &&
                            ` | NO: ${(market.current_no_price * 100).toFixed(1)}¢`}
                        </div>
                      )}
                  </div>
                </div>
              </div>

              {/* Expanded Trade View */}
              {expandedMarketId === market.market_id && (
                <div className="border-t border-slate-700 bg-slate-900/50 p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-sm font-semibold text-slate-300">
                      Recent Trades
                    </h4>
                    <a
                      href={`https://polymarket.com/event/${market.market_id}`} // Note: market_id might not be the slug, but it's a best effort link
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                    >
                      View on Polymarket <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>

                  {loadingTrades ? (
                    <div className="flex justify-center py-8">
                      <div className="animate-spin h-6 w-6 border-2 border-blue-500 rounded-full border-t-transparent"></div>
                    </div>
                  ) : marketTrades.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-xs text-slate-400 uppercase bg-slate-800/50">
                          <tr>
                            <th className="px-4 py-3">Time</th>
                            <th className="px-4 py-3">Trader</th>
                            <th className="px-4 py-3 text-right">Size</th>
                            <th className="px-4 py-3">Outcome</th>
                            <th className="px-4 py-3 text-right">Price</th>
                            <th className="px-4 py-3 text-center">Score</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {marketTrades.map((trade) => (
                            <tr
                              key={trade.id}
                              className="hover:bg-slate-800/30"
                            >
                              <td className="px-4 py-3 text-slate-300">
                                {new Date(
                                  trade.timestamp + "Z",
                                ).toLocaleTimeString()}
                              </td>
                              <td className="px-4 py-3">
                                <span className="font-mono text-blue-400">
                                  {trade.wallet_address.slice(0, 6)}...
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right font-medium text-slate-200">
                                {formatCurrency(trade.trade_size_usd)}
                              </td>
                              <td className="px-4 py-3">
                                <span
                                  className={
                                    trade.outcome === "YES"
                                      ? "text-green-400"
                                      : trade.outcome === "NO"
                                        ? "text-red-400"
                                        : "text-slate-400"
                                  }
                                >
                                  {trade.outcome || "-"}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right text-slate-300">
                                {trade.price
                                  ? `${(trade.price * 100).toFixed(1)}¢`
                                  : "-"}
                              </td>
                              <td className="px-4 py-3 text-center">
                                {trade.z_score ? (
                                  <span
                                    className={`px-2 py-0.5 rounded text-xs font-bold ${
                                      Math.abs(trade.z_score) > 3
                                        ? "bg-red-500/20 text-red-400"
                                        : "bg-slate-700 text-slate-400"
                                    }`}
                                  >
                                    {trade.z_score.toFixed(1)}
                                  </span>
                                ) : (
                                  "-"
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-slate-500">
                      No recent trades found for this market.
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
