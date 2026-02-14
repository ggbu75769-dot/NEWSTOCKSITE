import { NextResponse } from "next/server";
import { getLocalMarketRows, MarketCode } from "@/lib/localDb";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const marketRaw = (searchParams.get("market") ?? "KR").toUpperCase();
  const market: MarketCode = marketRaw === "US" ? "US" : "KR";

  const limitRaw = searchParams.get("limit");
  let limit = 6;
  if (limitRaw !== null) {
    const parsed = Number(limitRaw);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return NextResponse.json({ error: "limit must be a positive number" }, { status: 400 });
    }
    limit = Math.floor(parsed);
  }

  try {
    const { items, sourceFile } = await getLocalMarketRows(market, limit);
    return NextResponse.json({
      market,
      sourceFile,
      updatedAt: new Date().toISOString(),
      items,
    });
  } catch (err) {
    console.error("[api/market] failed", err);
    return NextResponse.json({ error: "failed to load market data" }, { status: 500 });
  }
}
