import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { loadKrxMasterNameMap } from "@/lib/recommendations/krxMaster";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { RecommendationLanguage, RecommendationResponse, StockRecommendation } from "@/lib/recommendations/types";

type Tier1CandidateRow = {
  candidate_rank?: number;
  ticker: string;
  date: string;
  close: number;
  ret_1d: number;
  ret_5d: number;
  rvol20: number;
  breakout_dist_20: number;
  natr14: number;
  tier1_composite_score: number;
};

type Tier1RecommendationOptions = {
  language?: string;
  limit?: number;
  sourceFile?: string;
};

const LOGS_DIR = path.join(process.cwd(), "logs");
const TIER1_FILE_REGEX = /^tier1_buy_candidates_(\d{8}_\d{6})\.csv$/;

function normalizeLanguage(language?: string): RecommendationLanguage {
  return language === "en" ? "en" : "ko";
}

function toNumber(raw: string | undefined): number {
  if (!raw) return Number.NaN;
  const value = Number(raw);
  return Number.isFinite(value) ? value : Number.NaN;
}

function parseCsv(text: string): Record<string, string>[] {
  const rows = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (rows.length < 2) return [];

  const headers = rows[0].split(",").map((header) => header.trim().replace(/^\uFEFF/, ""));
  return rows.slice(1).map((line) => {
    const cols = line.split(",");
    const item: Record<string, string> = {};
    for (let i = 0; i < headers.length; i += 1) {
      item[headers[i]] = (cols[i] ?? "").trim();
    }
    return item;
  });
}

async function findLatestTier1Csv(): Promise<{ filePath: string; fileName: string } | null> {
  let files: string[] = [];
  try {
    files = await readdir(LOGS_DIR);
  } catch {
    return null;
  }

  const sorted = files
    .map((name) => {
      const match = name.match(TIER1_FILE_REGEX);
      return match ? { name, ts: match[1] } : null;
    })
    .filter((item): item is { name: string; ts: string } => Boolean(item))
    .sort((a, b) => b.ts.localeCompare(a.ts));

  if (sorted.length === 0) return null;

  const latest = sorted[0];
  return {
    filePath: path.join(LOGS_DIR, latest.name),
    fileName: latest.name,
  };
}

async function resolveTier1Csv(sourceFile?: string): Promise<{ filePath: string; fileName: string } | null> {
  if (!sourceFile) {
    return findLatestTier1Csv();
  }

  // Only allow known candidate filename under logs/
  if (!TIER1_FILE_REGEX.test(sourceFile)) {
    return null;
  }

  return {
    filePath: path.join(LOGS_DIR, sourceFile),
    fileName: sourceFile,
  };
}

function mapCsvRowsToCandidates(rawRows: Record<string, string>[]): Tier1CandidateRow[] {
  return rawRows
    .map((row) => ({
      candidate_rank: toNumber(row.candidate_rank),
      ticker: row.ticker ?? "",
      date: row.date ?? "",
      close: toNumber(row.close),
      ret_1d: toNumber(row.ret_1d),
      ret_5d: toNumber(row.ret_5d),
      rvol20: toNumber(row.rvol20),
      breakout_dist_20: toNumber(row.breakout_dist_20),
      natr14: toNumber(row.natr14),
      tier1_composite_score: toNumber(row.tier1_composite_score),
    }))
    .filter((row) => row.ticker && Number.isFinite(row.close) && Number.isFinite(row.tier1_composite_score))
    // Re-rank inside API from CSV metrics (do not trust precomputed candidate_rank).
    .sort((a, b) => {
      if (b.tier1_composite_score !== a.tier1_composite_score) {
        return b.tier1_composite_score - a.tier1_composite_score;
      }
      if (b.ret_5d !== a.ret_5d) {
        return b.ret_5d - a.ret_5d;
      }
      return b.breakout_dist_20 - a.breakout_dist_20;
    });
}

function toAiScore(rawScore: number, minScore: number, maxScore: number): number {
  if (!Number.isFinite(rawScore)) return 0;
  if (!Number.isFinite(minScore) || !Number.isFinite(maxScore) || maxScore <= minScore) return 85;
  const normalized = (rawScore - minScore) / (maxScore - minScore);
  const scaled = 70 + normalized * 29;
  return Math.max(0, Math.min(99, Math.round(scaled)));
}

function formatSignedPct(value: number): string {
  if (!Number.isFinite(value)) return "-";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function formatX(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return `${value.toFixed(1)}x`;
}

function buildReasoning(row: Tier1CandidateRow, language: RecommendationLanguage): string {
  const ret1d = row.ret_1d;
  const ret5d = row.ret_5d;
  const rvol = row.rvol20;
  const breakout = row.breakout_dist_20;
  const natr = row.natr14;

  const momentumTag =
    Number.isFinite(ret5d) && ret5d >= 0.25
      ? language === "en"
        ? "Strong short-term momentum"
        : "단기 강한 모멘텀"
      : Number.isFinite(ret5d) && ret5d >= 0.12
        ? language === "en"
          ? "Uptrend continuation"
          : "상승 추세 지속"
        : Number.isFinite(ret5d) && ret5d >= 0.06
          ? language === "en"
            ? "Steady upward move"
            : "완만한 상승 흐름"
          : language === "en"
            ? "Early rebound phase"
            : "초기 반등 구간";

  const volumeTag =
    Number.isFinite(rvol) && rvol >= 10
      ? language === "en"
        ? "explosive volume"
        : "거래량 급증"
      : Number.isFinite(rvol) && rvol >= 5
        ? language === "en"
          ? "strong participation"
          : "강한 수급 유입"
        : Number.isFinite(rvol) && rvol >= 2
          ? language === "en"
            ? "above-average participation"
            : "평균 이상 수급"
          : language === "en"
            ? "normal participation"
            : "보통 수급";

  const breakoutTag =
    Number.isFinite(breakout) && breakout >= 0.15
      ? language === "en"
        ? "clear breakout zone"
        : "강한 돌파 구간"
      : Number.isFinite(breakout) && breakout >= 0.05
        ? language === "en"
          ? "above resistance"
          : "저항 돌파 후 안착"
        : Number.isFinite(breakout) && breakout >= 0
          ? language === "en"
            ? "near breakout level"
            : "돌파 시도 구간"
          : language === "en"
            ? "below resistance"
            : "저항선 아래 대기";

  const riskTag =
    Number.isFinite(natr) && natr <= 0.035
      ? language === "en"
        ? "low volatility risk"
        : "변동성 낮음"
      : Number.isFinite(natr) && natr <= 0.05
        ? language === "en"
          ? "manageable volatility"
          : "변동성 보통"
        : Number.isFinite(natr) && natr <= 0.08
          ? language === "en"
            ? "elevated volatility"
            : "변동성 다소 큼"
          : language === "en"
            ? "high volatility"
            : "변동성 큼";

  if (language === "en") {
    return `${momentumTag}: 5D ${formatSignedPct(ret5d)}, 1D ${formatSignedPct(ret1d)}. ${volumeTag} (${formatX(rvol)} vs average). ${breakoutTag} (20D high distance ${formatSignedPct(breakout)}). Volatility ${riskTag} (NATR14 ${formatSignedPct(natr)}).`;
  }

  return `${momentumTag}: 5일 ${formatSignedPct(ret5d)}, 1일 ${formatSignedPct(ret1d)}. ${volumeTag} (평균 대비 ${formatX(rvol)}). ${breakoutTag} (20일 고점 대비 ${formatSignedPct(breakout)}). 리스크는 ${riskTag} (NATR14 ${formatSignedPct(natr)}).`;
}

async function loadTickerNameMap(tickers: string[]): Promise<Map<string, string>> {
  if (tickers.length === 0) return new Map();

  try {
    const supabase = await createServerSupabaseClient();
    const uniqueTickers = Array.from(new Set(tickers));
    const tickerNameMap = new Map<string, string>();
    const chunkSize = 80;

    for (let i = 0; i < uniqueTickers.length; i += chunkSize) {
      const batch = uniqueTickers.slice(i, i + chunkSize);
      const { data, error } = await supabase.from("latest_prices").select("ticker, name").in("ticker", batch);

      if (error) {
        throw new Error(error.message);
      }

      for (const row of data ?? []) {
        const ticker = String(row.ticker ?? "");
        const name = String(row.name ?? "").trim();
        if (ticker && name) {
          tickerNameMap.set(ticker, name);
        }
      }
    }

    return tickerNameMap;
  } catch (err) {
    console.error("[recommendations] failed to enrich ticker names from DB", err);
    return new Map();
  }
}

export async function getTier1Recommendations(options: Tier1RecommendationOptions = {}): Promise<RecommendationResponse> {
  const language = normalizeLanguage(options.language);
  const resolved = await resolveTier1Csv(options.sourceFile);

  if (!resolved) {
    return {
      source: { file: null, generatedAt: new Date().toISOString() },
      items: [],
    };
  }

  const rawCsv = await readFile(resolved.filePath, "utf-8");
  const rows = mapCsvRowsToCandidates(parseCsv(rawCsv));

  if (rows.length === 0) {
    return {
      source: { file: resolved.fileName, generatedAt: new Date().toISOString() },
      items: [],
    };
  }

  const minScore = Math.min(...rows.map((row) => row.tier1_composite_score));
  const maxScore = Math.max(...rows.map((row) => row.tier1_composite_score));
  const krxMasterNameMap = await loadKrxMasterNameMap();
  const tickerNameMap = await loadTickerNameMap(rows.map((row) => row.ticker));

  const mapped: StockRecommendation[] = rows.map((row, index) => ({
    id: `${row.ticker}-${row.date || index}`,
    symbol: row.ticker,
    name:
      krxMasterNameMap.get(row.ticker) ??
      tickerNameMap.get(row.ticker) ??
      (language === "en" ? "Unknown Stock" : "이름 미확인 종목"),
    currentPrice: row.close,
    aiScore: toAiScore(row.tier1_composite_score, minScore, maxScore),
    fluctuationRate: Number.isFinite(row.ret_1d) ? row.ret_1d * 100 : 0,
    reasoning: buildReasoning(row, language),
  }));

  const limited =
    typeof options.limit === "number" && options.limit > 0 ? mapped.slice(0, Math.floor(options.limit)) : mapped;

  return {
    source: {
      file: resolved.fileName,
      generatedAt: new Date().toISOString(),
    },
    items: limited,
  };
}
