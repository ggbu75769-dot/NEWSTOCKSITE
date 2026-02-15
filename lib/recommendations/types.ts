export type StockRecommendation = {
  id: string;
  symbol: string;
  name: string;
  currentPrice: number;
  aiScore: number;
  fluctuationRate: number;
  reasoning: string;
};

export type DailyStockRecommendation = StockRecommendation & {
  date: string;
  rank: number;
  probability: number;
  tradingValue: number | null;
  dayReturn1d: number | null;
  finalScore: number | null;
  turnoverRankPct: number | null;
  ret1dRankPct: number | null;
  modelRankPct: number | null;
  scoreTurnover: number | null;
  scoreRet1d: number | null;
  scoreModel: number | null;
  maxReturnSinceBuy: number | null;
  maxReturnPeakDate: string | null;
};

export type RecommendationLanguage = "ko" | "en";

export type RecommendationResponse = {
  source: {
    file: string | null;
    generatedAt: string;
  };
  items: StockRecommendation[];
};

export type DailyRecommendationResponse = {
  source: {
    file: string | null;
    generatedAt: string;
    startDate: string | null;
    endDate: string | null;
  };
  days: Array<{
    date: string;
    items: DailyStockRecommendation[];
  }>;
};
