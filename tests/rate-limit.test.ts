import { describe, expect, it } from "vitest";
import { checkRateLimit, readClientIdentifier } from "../lib/rateLimit";

describe("rate limit", () => {
  it("allows up to limit and blocks after limit in the same window", () => {
    const scope = `test-limit-${Date.now()}`;
    const identifier = "127.0.0.1";

    const first = checkRateLimit({ scope, identifier, limit: 2, windowMs: 60_000 });
    const second = checkRateLimit({ scope, identifier, limit: 2, windowMs: 60_000 });
    const third = checkRateLimit({ scope, identifier, limit: 2, windowMs: 60_000 });

    expect(first.ok).toBe(true);
    expect(second.ok).toBe(true);
    expect(third.ok).toBe(false);
    expect(third.retryAfterSeconds).toBeGreaterThan(0);
  });

  it("uses x-forwarded-for first when available", () => {
    const request = new Request("http://localhost", {
      headers: {
        "x-forwarded-for": "203.0.113.11, 10.0.0.5",
        "x-real-ip": "198.51.100.3",
      },
    });

    expect(readClientIdentifier(request)).toBe("203.0.113.11");
  });

  it("falls back to unknown when no IP headers are set", () => {
    const request = new Request("http://localhost");
    expect(readClientIdentifier(request)).toBe("unknown");
  });
});
