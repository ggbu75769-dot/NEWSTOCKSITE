import { RecommendationResponse, StockRecommendation } from "@/lib/recommendations/types";

type FetchRecommendationsOptions = {
  language?: string;
  limit?: number;
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
