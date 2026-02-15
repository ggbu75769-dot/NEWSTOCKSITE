import {
  DailyRecommendationResponse,
  RecommendationResponse,
  StockRecommendation,
} from "@/lib/recommendations/types";

type FetchRecommendationsOptions = {
  language?: string;
  limit?: number;
  sourceFile?: string;
};

type FetchDailyRecommendationsOptions = {
  language?: string;
  startDate?: string;
  endDate?: string;
  limitPerDay?: number;
  sourceFile?: string;
};

type FetchLatestDailyTopOptions = {
  language?: string;
  limit?: number;
  startDate?: string;
  sourceFile?: string;
};

export async function fetchRecommendations(options: FetchRecommendationsOptions = {}): Promise<StockRecommendation[]> {
  const params = new URLSearchParams();
  if (options.language) params.set("lang", options.language === "en" ? "en" : "ko");
  if (typeof options.limit === "number" && options.limit > 0) params.set("limit", String(Math.floor(options.limit)));
  if (options.sourceFile) params.set("file", options.sourceFile);

  const query = params.toString();
  const url = query ? `/api/recommendations?${query}` : "/api/recommendations";

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch recommendations: ${res.status}`);
  }

  const data = (await res.json()) as RecommendationResponse;
  return Array.isArray(data.items) ? data.items : [];
}

export async function fetchDailyRecommendations(
  options: FetchDailyRecommendationsOptions = {}
): Promise<DailyRecommendationResponse> {
  const params = new URLSearchParams();
  if (options.language) params.set("lang", options.language === "en" ? "en" : "ko");
  if (options.startDate) params.set("startDate", options.startDate);
  if (options.endDate) params.set("endDate", options.endDate);
  if (typeof options.limitPerDay === "number" && options.limitPerDay > 0) {
    params.set("limit", String(Math.floor(options.limitPerDay)));
  }
  if (options.sourceFile) params.set("file", options.sourceFile);

  const query = params.toString();
  const url = query ? `/api/recommendations/daily?${query}` : "/api/recommendations/daily";

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch daily recommendations: ${res.status}`);
  }

  const data = (await res.json()) as DailyRecommendationResponse;
  return {
    source: data.source ?? {
      file: null,
      generatedAt: new Date().toISOString(),
      startDate: null,
      endDate: null,
    },
    days: Array.isArray(data.days) ? data.days : [],
  };
}

export async function fetchLatestDailyTopRecommendations(
  options: FetchLatestDailyTopOptions = {}
): Promise<StockRecommendation[]> {
  const limit =
    typeof options.limit === "number" && options.limit > 0
      ? Math.floor(options.limit)
      : 3;

  const payload = await fetchDailyRecommendations({
    language: options.language,
    startDate: options.startDate ?? "2026-01-01",
    limitPerDay: Math.max(limit, 5),
    sourceFile: options.sourceFile,
  });

  const latestDay = payload.days[0];
  if (!latestDay || !Array.isArray(latestDay.items)) return [];
  return latestDay.items.slice(0, limit);
}
