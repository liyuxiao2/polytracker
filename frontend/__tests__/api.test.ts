import { PolyEdgeAPI } from "@/lib/api";

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("PolyEdgeAPI", () => {
  let api: PolyEdgeAPI;

  beforeEach(() => {
    api = new PolyEdgeAPI("http://test-api:8000");
    mockFetch.mockClear();
  });

  describe("getTraders", () => {
    it("fetches traders with default params", async () => {
      const mockTraders = [
        {
          wallet_address: "0xabc",
          insider_score: 85,
          total_trades: 50,
          avg_bet_size: 1000,
          flagged_trades_count: 5,
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTraders,
      });

      const result = await api.getTraders();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/traders?min_score=0&limit=50"
      );
      expect(result).toEqual(mockTraders);
    });

    it("passes custom min_score and limit", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getTraders(50, 10);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/traders?min_score=50&limit=10"
      );
    });

    it("throws on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      });

      await expect(api.getTraders()).rejects.toThrow("Failed to fetch traders");
    });
  });

  describe("getTrendingTrades", () => {
    it("builds correct query params", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getTrendingTrades(10000, 12, 25, 2, "size", "asc");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/trades/trending?min_size=10000&hours=12&limit=25&page=2&sort_by=size&sort_order=asc"
      );
    });
  });

  describe("getTraderProfile", () => {
    it("fetches profile by address", async () => {
      const mockProfile = {
        wallet_address: "0xtest",
        insider_score: 75,
        total_trades: 100,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockProfile,
      });

      const result = await api.getTraderProfile("0xtest");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/trader/0xtest"
      );
      expect(result.wallet_address).toBe("0xtest");
    });

    it("throws on 404", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(api.getTraderProfile("0xnone")).rejects.toThrow();
    });
  });

  describe("getTraderTrades", () => {
    it("fetches trades with limit", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getTraderTrades("0xaddr", 50);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/trader/0xaddr/trades?limit=50"
      );
    });
  });

  describe("getDashboardStats", () => {
    it("fetches dashboard stats", async () => {
      const mockStats = {
        total_whales_tracked: 10,
        high_signal_alerts_today: 5,
        total_trades_monitored: 1000,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      });

      const result = await api.getDashboardStats();
      expect(result.total_whales_tracked).toBe(10);
    });
  });

  describe("getMarketWatch", () => {
    it("builds params without category when All", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getMarketWatch("All");

      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).not.toContain("category=");
    });

    it("includes category param when specified", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getMarketWatch("NBA");

      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).toContain("category=NBA");
    });

    it("uses correct sort params", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getMarketWatch(undefined, "volatility_score", "asc", 25);

      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).toContain("sort_by=volatility_score");
      expect(calledUrl).toContain("sort_order=asc");
      expect(calledUrl).toContain("limit=25");
    });
  });

  describe("getMarketTrades", () => {
    it("fetches trades for a market", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getMarketTrades("market_123", 20);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api:8000/api/markets/market_123/trades?limit=20"
      );
    });
  });

  describe("constructor", () => {
    it("uses custom base URL", () => {
      const customApi = new PolyEdgeAPI("http://custom:9000");
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      customApi.getTraders();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("http://custom:9000")
      );
    });
  });
});
