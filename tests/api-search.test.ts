import { describe, expect, it } from "vitest";
import { searchStock } from "../lib/searchStock";

describe("searchStock", () => {
  it("returns the first result when rpc succeeds", async () => {
    const supabase = {
      rpc: async () => ({
        data: [
          {
            ticker: "AAPL",
            name: "Apple Inc.",
          },
        ],
        error: null,
      }),
    };

    const result = await searchStock(supabase, "AAPL");
    expect(result).toEqual({ ticker: "AAPL", name: "Apple Inc." });
  });

  it("returns null when rpc returns empty data", async () => {
    const supabase = {
      rpc: async () => ({ data: [], error: null }),
    };

    const result = await searchStock(supabase, "TSLA");
    expect(result).toBeNull();
  });

  it("returns null when rpc returns error", async () => {
    const supabase = {
      rpc: async () => ({ data: null, error: { message: "fail" } }),
    };

    const result = await searchStock(supabase, "MSFT");
    expect(result).toBeNull();
  });

  it("returns null when rpc returns non-array", async () => {
    const supabase = {
      rpc: async () => ({ data: { ticker: "NVDA" }, error: null }),
    };

    const result = await searchStock(supabase, "NVDA");
    expect(result).toBeNull();
  });
});
