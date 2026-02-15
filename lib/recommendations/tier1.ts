import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { loadKrxMasterNameMap } from "@/lib/recommendations/krxMaster";
import { RecommendationLanguage, RecommendationResponse, StockRecommendation } from "@/lib/recommendations/types";
import { LOGS_DIR } from "../runtimePaths";

type Tier1CandidateRow = {
  ticker: string;
  date: string;
  close: number;
  ret1d: number;
  ret5d: number;
  rvol20: number;
  breakoutDist20: number;
  natr14: number;
  score: number;
};

type Tier1RecommendationOptions = {
  language?: string;
  limit?: number;
  sourceFile?: string;
};

const TIER1_FILE_REGEX = /^tier1_buy_candidates_(\d{8}_\d{6})\.csv$/;

function normalizeLanguage(language?: string): RecommendationLanguage {
  return language === "en" ? "en" : "ko";
}

function toNumber(raw: string | undefined): number {
  if (!raw) return Number.NaN;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function parseCsv(text: string): Record<string, string>[] {
  const rows = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (rows.length < 2) return [];

  const headers = rows[0].split(",").map((header) => header.trim());
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
  if (!sourceFile) return findLatestTier1Csv();
  if (!TIER1_FILE_REGEX.test(sourceFile)) return null;

  return {
    filePath: path.join(LOGS_DIR, sourceFile),
    fileName: sourceFile,
  };
}

function mapCsvRowsToCandidates(rawRows: Record<string, string>[]): Tier1CandidateRow[] {
  return rawRows
    .map((row) => ({
      ticker: String(row.ticker ?? "").trim().toUpperCase(),
      date: String(row.date ?? "").trim(),
      close: toNumber(row.close),
      ret1d: toNumber(row.ret_1d),
      ret5d: toNumber(row.ret_5d),
      rvol20: toNumber(row.rvol20),
      breakoutDist20: toNumber(row.breakout_dist_20),
      natr14: toNumber(row.natr14),
      score: toNumber(row.tier1_composite_score),
    }))
    .filter((row) => row.ticker && Number.isFinite(row.close) && Number.isFinite(row.score))
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      if (b.ret5d !== a.ret5d) return b.ret5d - a.ret5d;
      return b.breakoutDist20 - a.breakoutDist20;
    });
}

function toAiScore(rawScore: number, minScore: number, maxScore: number): number {
  if (!Number.isFinite(rawScore)) return 0;
  if (!Number.isFinite(minScore) || !Number.isFinite(maxScore) || maxScore <= minScore) return 85;
  const normalized = (rawScore - minScore) / (maxScore - minScore);
  const scaled = 70 + normalized * 29;
  return Math.round(Math.max(0, Math.min(99, scaled)));
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
  if (language === "en") {
    return `5D momentum ${formatSignedPct(row.ret5d)}, 1D move ${formatSignedPct(row.ret1d)}, volume ${formatX(
      row.rvol20
    )}, breakout distance ${formatSignedPct(row.breakoutDist20)}, NATR14 ${formatSignedPct(row.natr14)}.`;
  }

  return `5일 수익률 ${formatSignedPct(row.ret5d)}, 1일 수익률 ${formatSignedPct(
    row.ret1d
  )}, 거래량 배수 ${formatX(row.rvol20)}, 돌파 강도 ${formatSignedPct(row.breakoutDist20)}, 변동성(NATR14) ${formatSignedPct(
    row.natr14
  )} 기반 신호입니다.`;
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

  const minScore = Math.min(...rows.map((row) => row.score));
  const maxScore = Math.max(...rows.map((row) => row.score));
  const krxMasterNameMap = await loadKrxMasterNameMap();

  const mapped: StockRecommendation[] = rows.map((row, index) => ({
    id: `${row.ticker}-${row.date || index}`,
    symbol: row.ticker,
    name: krxMasterNameMap.get(row.ticker) ?? row.ticker,
    currentPrice: row.close,
    aiScore: toAiScore(row.score, minScore, maxScore),
    fluctuationRate: Number.isFinite(row.ret1d) ? row.ret1d * 100 : 0,
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
