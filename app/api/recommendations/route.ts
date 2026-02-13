import { NextResponse } from "next/server";
import { getTier1Recommendations } from "@/lib/recommendations/tier1";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const lang = searchParams.get("lang") ?? "ko";
  const sourceFile = searchParams.get("file") ?? undefined;
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
    const payload = await getTier1Recommendations({
      language: lang,
      limit: parsedLimit,
      sourceFile,
    });
    return NextResponse.json(payload);
  } catch (err) {
    console.error("[api/recommendations] failed", err);
    return NextResponse.json({ error: "failed to load recommendations" }, { status: 500 });
  }
}
