import { TraderListItem, TrendingTrade, TraderProfile, Trade, DashboardStats, MarketWatchItem } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class PolyEdgeAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async getTraders(minScore: number = 0, limit: number = 50): Promise<TraderListItem[]> {
    const response = await fetch(
      `${this.baseUrl}/api/traders?min_score=${minScore}&limit=${limit}`
    );
    if (!response.ok) throw new Error('Failed to fetch traders');
    return response.json();
  }

  async getTrendingTrades(
    minSize: number = 5000, 
    hours: number = 24, 
    limit: number = 50,
    page: number = 1,
    sortBy: string = 'timestamp',
    sortOrder: string = 'desc'
  ): Promise<TrendingTrade[]> {
    const response = await fetch(
      `${this.baseUrl}/api/trades/trending?min_size=${minSize}&hours=${hours}&limit=${limit}&page=${page}&sort_by=${sortBy}&sort_order=${sortOrder}`
    );
    if (!response.ok) throw new Error('Failed to fetch trending trades');
    return response.json();
  }

  async getTraderProfile(address: string): Promise<TraderProfile> {
    const response = await fetch(`${this.baseUrl}/api/trader/${address}`);
    if (!response.ok) throw new Error('Failed to fetch trader profile');
    return response.json();
  }

  async getTraderTrades(address: string, limit: number = 100): Promise<Trade[]> {
    const response = await fetch(
      `${this.baseUrl}/api/trader/${address}/trades?limit=${limit}`
    );
    if (!response.ok) throw new Error('Failed to fetch trader trades');
    return response.json();
  }

  async getDashboardStats(): Promise<DashboardStats> {
    const response = await fetch(`${this.baseUrl}/api/stats`);
    if (!response.ok) throw new Error('Failed to fetch dashboard stats');
    return response.json();
  }

  async getMarketWatch(
    category?: string,
    sortBy: string = 'suspicion_score',
    sortOrder: string = 'desc',
    limit: number = 50
  ): Promise<MarketWatchItem[]> {
    const params = new URLSearchParams({
      sort_by: sortBy,
      sort_order: sortOrder,
      limit: limit.toString()
    });

    if (category && category !== 'All') {
      params.append('category', category);
    }

    const response = await fetch(`${this.baseUrl}/api/markets/watch?${params}`);
    if (!response.ok) throw new Error('Failed to fetch market watch data');
    return response.json();
  }
}

export const api = new PolyEdgeAPI();
