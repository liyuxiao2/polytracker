import {
  formatCurrency,
  formatNumber,
  shortenAddress,
  getScoreColor,
  getScoreBgColor,
  formatRelativeTime,
} from "@/lib/utils";

describe("formatCurrency", () => {
  it("formats positive numbers as USD", () => {
    expect(formatCurrency(1234)).toBe("$1,234");
  });

  it("formats large numbers with commas", () => {
    expect(formatCurrency(1000000)).toBe("$1,000,000");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0");
  });

  it("formats negative numbers", () => {
    expect(formatCurrency(-5000)).toBe("-$5,000");
  });
});

describe("formatNumber", () => {
  it("formats with default 0 decimals", () => {
    expect(formatNumber(1234.567)).toBe("1,235");
  });

  it("formats with specified decimals", () => {
    expect(formatNumber(1234.567, 2)).toBe("1,234.57");
  });

  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });
});

describe("shortenAddress", () => {
  it("shortens a full address", () => {
    const addr = "0x1234567890abcdef1234567890abcdef12345678";
    expect(shortenAddress(addr)).toBe("0x1234...5678");
  });

  it("supports custom char count", () => {
    const addr = "0xabcdefghijklmnop";
    expect(shortenAddress(addr, 4)).toBe("0xab...mnop");
  });

  it("handles empty string", () => {
    expect(shortenAddress("")).toBe("");
  });

  it("handles undefined-like falsy input", () => {
    expect(shortenAddress("")).toBe("");
  });
});

describe("getScoreColor", () => {
  it("returns red for scores >= 80", () => {
    expect(getScoreColor(80)).toBe("text-red-500");
    expect(getScoreColor(100)).toBe("text-red-500");
  });

  it("returns orange for scores >= 60", () => {
    expect(getScoreColor(60)).toBe("text-orange-500");
    expect(getScoreColor(79)).toBe("text-orange-500");
  });

  it("returns yellow for scores >= 40", () => {
    expect(getScoreColor(40)).toBe("text-yellow-500");
    expect(getScoreColor(59)).toBe("text-yellow-500");
  });

  it("returns green for scores < 40", () => {
    expect(getScoreColor(0)).toBe("text-green-500");
    expect(getScoreColor(39)).toBe("text-green-500");
  });
});

describe("getScoreBgColor", () => {
  it("returns red bg for scores >= 80", () => {
    expect(getScoreBgColor(80)).toContain("bg-red-500");
  });

  it("returns orange bg for scores >= 60", () => {
    expect(getScoreBgColor(60)).toContain("bg-orange-500");
  });

  it("returns yellow bg for scores >= 40", () => {
    expect(getScoreBgColor(40)).toContain("bg-yellow-500");
  });

  it("returns green bg for scores < 40", () => {
    expect(getScoreBgColor(20)).toContain("bg-green-500");
  });
});

describe("formatRelativeTime", () => {
  it('returns "Just now" for very recent times', () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe("Just now");
  });

  it("returns minutes ago", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatRelativeTime(fiveMinAgo)).toBe("5m ago");
  });

  it("returns hours ago", () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(twoHoursAgo)).toBe("2h ago");
  });

  it("returns days ago", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(threeDaysAgo)).toBe("3d ago");
  });

  it("returns date for old times", () => {
    const twoWeeksAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString();
    const result = formatRelativeTime(twoWeeksAgo);
    // Should be a locale date string, not relative
    expect(result).not.toContain("ago");
  });
});
