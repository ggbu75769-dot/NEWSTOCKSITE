export type StockRecommendation = {
  id: string;
  symbol: string;
  name: string;
  currentPrice: number;
  aiScore: number;
  fluctuationRate: number;
  reasoning: string;
};

type Lang = "ko" | "en";

type LocalizedRecommendation = {
  id: string;
  symbol: string;
  name: {
    ko: string;
    en: string;
  };
  currentPrice: number;
  aiScore: number;
  fluctuationRate: number;
  reasoning: {
    ko: string;
    en: string;
  };
};

const recommendationSeeds: LocalizedRecommendation[] = [
  {
    id: "rec-001",
    symbol: "005930.KS",
    name: { ko: "삼성전자", en: "Samsung Electronics" },
    currentPrice: 118800,
    aiScore: 93,
    fluctuationRate: 4.21,
    reasoning: {
      ko: "가격이 20일 고점을 재돌파했고 상대거래량이 2.3배까지 확대됐습니다. 하방 변동성은 제한적이며, 3거래일 연속 변동폭 축소 뒤 돌파가 발생해 매도 물량 소화 후 추세 지속 가능성이 높습니다.",
      en: "Price reclaimed the 20-day high with a 2.3x relative volume burst while downside volatility stayed controlled. The breakout followed three sessions of narrowing range, which often indicates supply exhaustion before continuation.",
    },
  },
  {
    id: "rec-002",
    symbol: "NVDA",
    name: { ko: "엔비디아", en: "NVIDIA" },
    currentPrice: 953.42,
    aiScore: 91,
    fluctuationRate: 3.47,
    reasoning: {
      ko: "5일·20일 모멘텀이 동시에 상승 가속 중이며, 지수 대비 조정 폭이 얕습니다. 기관성 매수 흐름 지표도 높게 유지돼 단기 추세 연장 확률이 유리합니다.",
      en: "5-day and 20-day momentum are both positive and accelerating, while pullbacks have been shallow versus index beta. Institutional buy-flow proxy remains elevated, suggesting trend persistence over the next few sessions.",
    },
  },
  {
    id: "rec-003",
    symbol: "000660.KS",
    name: { ko: "SK하이닉스", en: "SK hynix" },
    currentPrice: 186200,
    aiScore: 89,
    fluctuationRate: 2.98,
    reasoning: {
      ko: "이전 저항 구간을 대량거래로 재돌파했고 동종 섹터 대비 상대강도가 높습니다. ATR 기준 변동성은 최근 급등 구간보다 낮아 추가 추세 진행 여력이 있습니다.",
      en: "A high-volume reclaim above the prior resistance zone occurred with strong relative strength versus sector peers. ATR normalized volatility is below recent expansion peaks, leaving room for directional follow-through.",
    },
  },
  {
    id: "rec-004",
    symbol: "035420.KS",
    name: { ko: "네이버", en: "NAVER" },
    currentPrice: 223500,
    aiScore: 86,
    fluctuationRate: 2.35,
    reasoning: {
      ko: "변동성 압축 구간 이후 2거래일 연속 볼린저 상단 부근에서 마감했습니다. 거래량 참여는 증가했지만 하루 과열은 크지 않아 추세 연속성 관점에서 구조가 양호합니다.",
      en: "After a volatility compression phase, price closed near the upper Bollinger region for two consecutive sessions. Volume participation improved without extreme one-day overheating, supporting a cleaner continuation setup.",
    },
  },
  {
    id: "rec-005",
    symbol: "TSLA",
    name: { ko: "테슬라", en: "Tesla" },
    currentPrice: 214.77,
    aiScore: 84,
    fluctuationRate: 1.82,
    reasoning: {
      ko: "크로스섹션 모멘텀 순위가 상위 10%대로 개선됐고 단기 추세 기울기가 양전환했습니다. 단발성 체결보다 광범위한 매수 압력 형태라 며칠 단위 움직임에 유리합니다.",
      en: "Cross-sectional momentum rank improved into the top decile and short-term trend slope turned positive. Buy pressure appears broad rather than single-print driven, which is generally more robust for multi-day moves.",
    },
  },
  {
    id: "rec-006",
    symbol: "251270.KQ",
    name: { ko: "넷마블", en: "Netmarble" },
    currentPrice: 61300,
    aiScore: 82,
    fluctuationRate: 1.44,
    reasoning: {
      ko: "가격이 20일 평균 위를 유지하고 상대거래량도 기준치 이상입니다. 폭발력은 상위 종목보다 낮지만 수급의 일관성과 시장 브레드스 개선이 확률을 지지합니다.",
      en: "Price is holding above the 20-day mean while relative volume remains above baseline. The setup is less explosive than top-ranked names, but consistency in demand and rising breadth context keep odds favorable.",
    },
  },
  {
    id: "rec-007",
    symbol: "AAPL",
    name: { ko: "애플", en: "Apple" },
    currentPrice: 201.16,
    aiScore: 79,
    fluctuationRate: 1.21,
    reasoning: {
      ko: "모멘텀은 양수지만 과열되지 않았고, 장중 종가 위치 지표와 유동성 안정성이 개선 중입니다. 급격한 변동보다 추세 정렬에 의한 완만한 상승 가능성이 큽니다.",
      en: "Momentum is positive but moderate, with improving intraday close-location values and stable liquidity. Signal quality comes from regime alignment rather than volatility shock, favoring steady drift over sharp spike.",
    },
  },
  {
    id: "rec-008",
    symbol: "207940.KS",
    name: { ko: "삼성바이오로직스", en: "Samsung Biologics" },
    currentPrice: 864000,
    aiScore: 77,
    fluctuationRate: 0.95,
    reasoning: {
      ko: "최근 조정에서도 구조적 고점·저점 패턴은 유지됐고 지지 구간에서 누적 매수 흔적이 확인됩니다. 돌파 거리는 작지만 양수라 초기 추세 연장 후보로 볼 수 있습니다.",
      en: "Recent pullback did not break structural higher lows, and volume profile shows accumulation near support. Breakout distance is small but positive, indicating an early-stage trend continuation candidate.",
    },
  },
  {
    id: "rec-009",
    symbol: "AMZN",
    name: { ko: "아마존", en: "Amazon" },
    currentPrice: 191.03,
    aiScore: 75,
    fluctuationRate: 0.78,
    reasoning: {
      ko: "가격이 단기 이동평균 위에 있고 브레드스 보정 상대강도가 개선 중입니다. 참여 강도는 다소 낮아 강도는 중간이지만 방향성은 상방 우위입니다.",
      en: "Price is above short-term moving averages with improving breadth-adjusted relative strength. Signal strength is medium due to lower participation intensity, but directional bias remains upward.",
    },
  },
  {
    id: "rec-010",
    symbol: "066570.KS",
    name: { ko: "LG전자", en: "LG Electronics" },
    currentPrice: 112400,
    aiScore: 73,
    fluctuationRate: 0.64,
    reasoning: {
      ko: "유동성과 변동성 조건이 균형적이고 추세 정렬도 양호합니다. 고확신 돌파 단계는 아니지만 리스크온 국면이 유지되면 점진적 상방 확률이 우세합니다.",
      en: "Liquidity and volatility conditions are balanced, and trend alignment remains constructive. Not a high-conviction breakout yet, but probability favors incremental upside while market regime stays risk-on.",
    },
  },
];

function normalizeLanguage(language?: string): Lang {
  return language === "en" ? "en" : "ko";
}

function resolveByLanguage(language?: string): StockRecommendation[] {
  const lang = normalizeLanguage(language);
  return recommendationSeeds.map((item) => ({
    id: item.id,
    symbol: item.symbol,
    name: item.name[lang],
    currentPrice: item.currentPrice,
    aiScore: item.aiScore,
    fluctuationRate: item.fluctuationRate,
    reasoning: item.reasoning[lang],
  }));
}

export function getSortedRecommendations(language?: string): StockRecommendation[] {
  return resolveByLanguage(language).sort((a, b) => b.aiScore - a.aiScore);
}

export function getTopRecommendations(language?: string, limit = 3): StockRecommendation[] {
  return getSortedRecommendations(language).slice(0, limit);
}
