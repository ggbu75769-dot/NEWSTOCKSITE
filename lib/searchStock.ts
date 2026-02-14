import { getLocalSearchResult, LocalSearchResult } from "./localDb";

export async function searchStock(symbol: string): Promise<LocalSearchResult | null> {
  return getLocalSearchResult(symbol);
}
