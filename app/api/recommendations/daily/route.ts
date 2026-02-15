import { NextResponse } from "next/server";
import { getDailyRecommendations } from "@/lib/recommendations/daily";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const lang = searchParams.get("lang") ?? "ko";
  const sourceFile = searchParams.get("file") ?? undefined;
  const startDate = searchParams.get("startDate") ?? undefined;
  const endDate = searchParams.get("endDate") ?? undefined;
  const limitRaw = searchParams.get("limit");
  let parsedLimit: number | undefined;

  if (limitRaw !== null) {
    const limitValue = Number(limitRaw);
    if (!Number.isFinite(limitValue) || limitValue <= 0) {
      return NextResponse.json({ error: "limit must be a positive number" }, { status: 400 });
    }
    parsedLimit = limitValue;
  }

  try {
    const payload = await getDailyRecommendations({
      language: lang,
      limitPerDay: parsedLimit,
      sourceFile,
      startDate,
      endDate,
    });
    return NextResponse.json(payload);
  } catch (err) {
    console.error("[api/recommendations/daily] failed", err);
    return NextResponse.json({ error: "failed to load daily recommendations" }, { status: 500 });
  }
}
