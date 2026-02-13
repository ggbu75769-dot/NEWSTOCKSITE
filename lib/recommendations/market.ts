export function inferCurrencyBySymbol(symbol: string): "KRW" | "USD" {
  return symbol.endsWith(".KS") || symbol.endsWith(".KQ") ? "KRW" : "USD";
}

export function getMarketLabelBySymbol(symbol: string, language: "ko" | "en"): string {
  if (symbol.endsWith(".KS")) {
    return language === "en" ? "KOSPI" : "코스피";
  }

  if (symbol.endsWith(".KQ")) {
    return language === "en" ? "KOSDAQ" : "코스닥";
  }

  return "";
}
