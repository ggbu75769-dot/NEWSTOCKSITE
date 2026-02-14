import { afterEach, describe, expect, it, vi } from "vitest";
import { searchStock } from "../lib/searchStock";
import * as localDb from "../lib/localDb";

describe("searchStock", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns local search result", async () => {
    vi.spyOn(localDb, "getLocalSearchResult").mockResolvedValue({
      ticker: "005930.KS",
      name: "Samsung Electronics",
      sector: "KOSPI",
      ranking_date: "2026-02-11",
      rank: 1,
      win_rate: 92.3,
      avg_return: 5.2,
      confluence_score: 97.1,
    });

    const result = await searchStock("005930");
    expect(result?.ticker).toBe("005930.KS");
    expect(result?.name).toBe("Samsung Electronics");
  });

  it("returns null when local search has no result", async () => {
    vi.spyOn(localDb, "getLocalSearchResult").mockResolvedValue(null);

    const result = await searchStock("UNKNOWN");
    expect(result).toBeNull();
  });
});
