export type StockRecommendation = {
  id: string;
  symbol: string;
  name: string;
  currentPrice: number;
  aiScore: number;
  fluctuationRate: number;
  reasoning: string;
};

export type RecommendationLanguage = "ko" | "en";

export type RecommendationResponse = {
  source: {
    file: string | null;
    generatedAt: string;
  };
  items: StockRecommendation[];
};
