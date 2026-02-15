import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { DailyRecommendationResponse, DailyStockRecommendation, RecommendationLanguage } from "@/lib/recommendations/types";
import { LOGS_DIR } from "../runtimePaths";

type DailyRecommendationOptions = {
  language?: string;
  startDate?: string;
  endDate?: string;
  limitPerDay?: number;
  sourceFile?: string;
};

type DailyCsvRow = {
  date: string;
  rank: number;
  ticker: string;
  name: string;
  close: number;
  tradingValue: number;
  dayReturn1d: number;
  probability: number;
  finalScore: number;
  aiScore: number;
  turnoverRankPct: number;
  ret1dRankPct: number;
  modelRankPct: number;
  scoreTurnover: number;
  scoreRet1d: number;
  scoreModel: number;
  maxReturnSinceBuy: number;
  maxReturnPeakDate: string;
};

const DAILY_FILE_REGEX = /^daily_top5_recommendations_(\d{8})(?:_to_(\d{8}))?\.csv$/;

function normalizeLanguage(language?: string): RecommendationLanguage {
  return language === "en" ? "en" : "ko";
}

function toNumber(raw: string | undefined): number {
  if (!raw) return Number.NaN;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      cells.push(current);
      current = "";
      continue;
    }
    current += ch;
  }

  cells.push(current);
  return cells;
}

function parseCsv(text: string): Record<string, string>[] {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = splitCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const cols = splitCsvLine(line);
    const row: Record<string, string> = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = (cols[i] ?? "").trim();
    }
    return row;
  });
}

function normalizeDate(raw: string): string {
  const trimmed = String(raw ?? "").trim();
  const match = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : "";
}

function normalizeIsoDate(raw?: string): string | null {
  if (!raw) return null;
  const value = raw.trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

function toTopBandText(pct: number): string {
  if (!Number.isFinite(pct)) return "-";
  const topPct = Math.max(0, (1 - pct) * 100);
  return `${topPct.toFixed(1)}%`;
}

function toSignedPctText(value: number): string {
  if (!Number.isFinite(value)) return "-";
  const pct = value * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function toEokText(value: number, language: RecommendationLanguage): string {
  if (!Number.isFinite(value)) return "-";
  const eok = Math.round(value / 100_000_000);
  const grouped = new Intl.NumberFormat(language === "en" ? "en-US" : "ko-KR").format(eok);
  if (language === "en") return `${grouped}eok KRW`;
  return `${grouped}억`;
}

function buildReasoning(row: DailyCsvRow, language: RecommendationLanguage): string {
  const turnoverText = toEokText(row.tradingValue, language);
  const ret1dText = toSignedPctText(row.dayReturn1d);
  const turnoverTopText = toTopBandText(row.turnoverRankPct);
  const retTopText = toTopBandText(row.ret1dRankPct);
  const modelTopText = toTopBandText(row.modelRankPct);
  const scoreText = Number.isFinite(row.finalScore) ? row.finalScore.toFixed(3) : "-";
  const scoreTurnoverText = Number.isFinite(row.scoreTurnover) ? row.scoreTurnover.toFixed(3) : "-";
  const scoreRet1dText = Number.isFinite(row.scoreRet1d) ? row.scoreRet1d.toFixed(3) : "-";
  const scoreModelText = Number.isFinite(row.scoreModel) ? row.scoreModel.toFixed(3) : "-";
  const maxReturnText = toSignedPctText(row.maxReturnSinceBuy);
  const peakDateText = row.maxReturnPeakDate || "-";

  if (language === "en") {
    return `Turnover ${turnoverText} (top ${turnoverTopText}), 1D return ${ret1dText} (top ${retTopText}), base-model signal top ${modelTopText}; final score ${scoreText} [turnover ${scoreTurnoverText}, return ${scoreRet1dText}, model ${scoreModelText}], max return after buy ${maxReturnText} (peak ${peakDateText}).`;
  }
  return `거래대금 ${turnoverText}(상위 ${turnoverTopText}), 1일 상승률 ${ret1dText}(상위 ${retTopText}), 기존 모델 신호 상위 ${modelTopText}; 최종 점수 ${scoreText}(거래대금 ${scoreTurnoverText} + 상승률 ${scoreRet1dText} + 기존모델 ${scoreModelText}), 매수 후 최고수익률 ${maxReturnText}(고점일 ${peakDateText}).`;
}

async function findLatestDailyCsv(): Promise<{ filePath: string; fileName: string } | null> {
  let files: string[] = [];
  try {
    files = await readdir(LOGS_DIR);
  } catch {
    return null;
  }

  const sorted = files
    .map((name) => {
      const match = name.match(DAILY_FILE_REGEX);
      if (!match) return null;
      const start = match[1];
      const end = match[2] ?? start;
      return { name, key: `${end}_${start}` };
    })
    .filter((item): item is { name: string; key: string } => Boolean(item))
    .sort((a, b) => b.key.localeCompare(a.key));

  if (sorted.length === 0) return null;
  return {
    filePath: path.join(LOGS_DIR, sorted[0].name),
    fileName: sorted[0].name,
  };
}

async function resolveDailyCsv(sourceFile?: string): Promise<{ filePath: string; fileName: string } | null> {
  if (!sourceFile) return findLatestDailyCsv();
  if (!DAILY_FILE_REGEX.test(sourceFile)) return null;

  return {
    filePath: path.join(LOGS_DIR, sourceFile),
    fileName: sourceFile,
  };
}

function mapCsvRows(rawRows: Record<string, string>[]): DailyCsvRow[] {
  return rawRows
    .map((row) => ({
      date: normalizeDate(row.Date ?? row.date ?? ""),
      rank: toNumber(row.rank),
      ticker: String(row.Ticker ?? row.ticker ?? "").trim().toUpperCase(),
      name: String(row.name ?? row.Name ?? "").trim(),
      close: toNumber(row.Close ?? row.close),
      tradingValue: toNumber(row.trading_value ?? row.tradingValue),
      dayReturn1d: toNumber(row.ret_1d ?? row.ret1d),
      probability: toNumber(row.prob_up_next_day ?? row.probability),
      finalScore: toNumber(row.final_score ?? row.finalScore),
      aiScore: toNumber(row.ai_score ?? row.aiScore),
      turnoverRankPct: toNumber(row.turnover_rank_pct ?? row.turnoverRankPct),
      ret1dRankPct: toNumber(row.ret1d_rank_pct ?? row.ret1dRankPct),
      modelRankPct: toNumber(row.model_rank_pct ?? row.modelRankPct),
      scoreTurnover: toNumber(row.score_turnover ?? row.scoreTurnover),
      scoreRet1d: toNumber(row.score_ret1d ?? row.scoreRet1d),
      scoreModel: toNumber(row.score_model ?? row.scoreModel),
      maxReturnSinceBuy: toNumber(row.max_return_since_buy ?? row.maxReturnSinceBuy),
      maxReturnPeakDate: normalizeDate(row.max_return_peak_date ?? row.maxReturnPeakDate ?? ""),
    }))
    .filter(
      (row) =>
        Boolean(row.date) &&
        Boolean(row.ticker) &&
        Number.isFinite(row.rank) &&
        Number.isFinite(row.close) &&
        Number.isFinite(row.probability)
    )
    .sort((a, b) => {
      if (a.date !== b.date) return b.date.localeCompare(a.date);
      if (a.rank !== b.rank) return a.rank - b.rank;
      if (b.probability !== a.probability) return b.probability - a.probability;
      return a.ticker.localeCompare(b.ticker);
    });
}

export async function getDailyRecommendations(options: DailyRecommendationOptions = {}): Promise<DailyRecommendationResponse> {
  const language = normalizeLanguage(options.language);
  const startDate = normalizeIsoDate(options.startDate);
  const endDate = normalizeIsoDate(options.endDate);
  const limitPerDay = typeof options.limitPerDay === "number" && options.limitPerDay > 0 ? Math.floor(options.limitPerDay) : 5;
  const resolved = await resolveDailyCsv(options.sourceFile);

  if (!resolved) {
    return {
      source: {
        file: null,
        generatedAt: new Date().toISOString(),
        startDate,
        endDate,
      },
      days: [],
    };
  }

  const rawCsv = await readFile(resolved.filePath, "utf-8");
  const rows = mapCsvRows(parseCsv(rawCsv)).filter((row) => {
    if (startDate && row.date < startDate) return false;
    if (endDate && row.date > endDate) return false;
    return true;
  });

  const grouped = new Map<string, DailyStockRecommendation[]>();
  for (const row of rows) {
    const arr = grouped.get(row.date) ?? [];
    if (arr.length >= limitPerDay) continue;

    const aiScore = Number.isFinite(row.aiScore) ? Math.round(row.aiScore) : 85;
    arr.push({
      id: `${row.date}-${row.ticker}-${row.rank}`,
      date: row.date,
      rank: row.rank,
      probability: row.probability,
      tradingValue: Number.isFinite(row.tradingValue) ? row.tradingValue : null,
      dayReturn1d: Number.isFinite(row.dayReturn1d) ? row.dayReturn1d : null,
      finalScore: Number.isFinite(row.finalScore) ? row.finalScore : null,
      turnoverRankPct: Number.isFinite(row.turnoverRankPct) ? row.turnoverRankPct : null,
      ret1dRankPct: Number.isFinite(row.ret1dRankPct) ? row.ret1dRankPct : null,
      modelRankPct: Number.isFinite(row.modelRankPct) ? row.modelRankPct : null,
      scoreTurnover: Number.isFinite(row.scoreTurnover) ? row.scoreTurnover : null,
      scoreRet1d: Number.isFinite(row.scoreRet1d) ? row.scoreRet1d : null,
      scoreModel: Number.isFinite(row.scoreModel) ? row.scoreModel : null,
      maxReturnSinceBuy: Number.isFinite(row.maxReturnSinceBuy) ? row.maxReturnSinceBuy : null,
      maxReturnPeakDate: row.maxReturnPeakDate || null,
      symbol: row.ticker,
      name: row.name || row.ticker,
      currentPrice: row.close,
      aiScore,
      fluctuationRate: Number.isFinite(row.dayReturn1d) ? row.dayReturn1d * 100 : 0,
      reasoning: buildReasoning(row, language),
    });
    grouped.set(row.date, arr);
  }

  const days = [...grouped.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, items]) => ({
      date,
      items: items.sort((a, b) => a.rank - b.rank),
    }));

  const responseStartDate = startDate ?? (days.length > 0 ? days[days.length - 1].date : null);
  const responseEndDate = endDate ?? (days.length > 0 ? days[0].date : null);

  return {
    source: {
      file: resolved.fileName,
      generatedAt: new Date().toISOString(),
      startDate: responseStartDate,
      endDate: responseEndDate,
    },
    days,
  };
}


