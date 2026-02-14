import { NextResponse } from "next/server";
import { searchStock } from "@/lib/searchStock";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbol = searchParams.get("symbol")?.trim().toUpperCase();

  if (!symbol) {
    return NextResponse.json({ error: "Symbol is required." }, { status: 400 });
  }

  const result = await searchStock(symbol);

  if (!result) {
    return NextResponse.json({ error: "No results found." }, { status: 404 });
  }

  return NextResponse.json(result);
}
