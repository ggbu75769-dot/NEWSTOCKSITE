import { constants } from "node:fs";
import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";

export type MarketCode = "KR" | "US";

type CsvRow = Record<string, string>;

type KrxMeta = {
  market: string;
  name: string;
};

type Tier1FeatureRow = {
  ticker: string;
  date: string;
  close: number;
  ret1d: number;
  volume: number;
  market: MarketCode;
};

type Tier1CandidateRow = {
  ticker: string;
  date: string;
  candidateRank: number;
  ret1d: number;
  ret5d: number;
  score: number;
};

type CandidateSummary = {
  ticker: string;
  date: string | null;
  rank: number;
  winRate: number | null;
  avgReturn: number | null;
  confluenceScore: number | null;
};

export type LocalHomeRanking = {
  rank: number;
  win_rate: number;
  avg_return: number;
  confluence_score: number;
  ticker: string;
  name: string;
};

export type LocalSearchResult = {
  ticker: string;
  name: string;
  sector: string | null;
  ranking_date: string | null;
  rank: number | null;
  win_rate: number | null;
  avg_return: number | null;
  confluence_score: number | null;
};

export type LocalMarketRow = {
  ticker: string;
  name: string;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
  trade_date: string;
  market: MarketCode;
  currency: string;
};

const DATA_DIR = path.join(process.cwd(), "data");
const LOGS_DIR = path.join(process.cwd(), "logs");
const KRX_MASTER_PATH = path.join(DATA_DIR, "krx_symbol_master.csv");
const FEATURES_FILE_REGEX = /^tier1_features_latest_(\d{8}_\d{6})\.csv$/;
const CANDIDATES_FILE_REGEX = /^tier1_buy_candidates_(\d{8}_\d{6})\.csv$/;

let cachedKrxMetaMap: Map<string, KrxMeta> | null = null;
let cachedFeatureRows: { fileName: string; rows: Tier1FeatureRow[] } | null = null;
let cachedCandidateRows: { fileName: string; rows: Tier1CandidateRow[] } | null = null;
const cachedLatestDateByTicker = new Map<string, string | null>();

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

function parseCsv(text: string): CsvRow[] {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = splitCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const cols = splitCsvLine(line);
    const row: CsvRow = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = (cols[i] ?? "").trim();
    }
    return row;
  });
}

function toNumber(raw: string | undefined): number {
  if (!raw) return Number.NaN;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function inferMarket(ticker: string): MarketCode {
  if (ticker.endsWith(".KS") || ticker.endsWith(".KQ")) return "KR";
  return "US";
}

function inferCurrency(market: MarketCode): string {
  return market === "KR" ? "KRW" : "USD";
}

function normalizeDate(raw: string): string {
  if (!raw) return "";
  const [date] = raw.split(" ");
  return date ?? raw;
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function findLatestLogFile(
  fileRegex: RegExp
): Promise<{ fileName: string; filePath: string } | null> {
  let files: string[] = [];
  try {
    files = await readdir(LOGS_DIR);
  } catch {
    return null;
  }

  const found = files
    .map((name) => {
      const match = name.match(fileRegex);
      return match ? { name, key: match[1] } : null;
    })
    .filter((item): item is { name: string; key: string } => Boolean(item))
    .sort((a, b) => b.key.localeCompare(a.key));

  if (found.length === 0) return null;
  return {
    fileName: found[0].name,
    filePath: path.join(LOGS_DIR, found[0].name),
  };
}

async function loadKrxMetaMap(): Promise<Map<string, KrxMeta>> {
  if (cachedKrxMetaMap) return cachedKrxMetaMap;

  try {
    const raw = await readFile(KRX_MASTER_PATH, "utf-8");
    const rows = parseCsv(raw);
    const map = new Map<string, KrxMeta>();

    for (const row of rows) {
      const symbol = String(row.symbol ?? "").trim().toUpperCase();
      const market = String(row.market ?? "").trim();
      const name = String(row.name_ko ?? "").trim();
      if (!symbol || !name) continue;
      map.set(symbol, { market, name });
    }

    cachedKrxMetaMap = map;
    return map;
  } catch (err) {
    console.error("[local-db] failed to load krx_symbol_master.csv", err);
    return new Map();
  }
}

async function loadLatestFeatureRows(): Promise<{ fileName: string; rows: Tier1FeatureRow[] }> {
  const latest = await findLatestLogFile(FEATURES_FILE_REGEX);
  if (!latest) {
    return { fileName: "", rows: [] };
  }

  if (cachedFeatureRows && cachedFeatureRows.fileName === latest.fileName) {
    return cachedFeatureRows;
  }

  const raw = await readFile(latest.filePath, "utf-8");
  const parsedRows = parseCsv(raw);
  const rows: Tier1FeatureRow[] = [];

  for (const row of parsedRows) {
    const ticker = String(row.ticker ?? "").trim().toUpperCase();
    if (!ticker) continue;

    rows.push({
      ticker,
      date: String(row.date ?? "").trim(),
      close: toNumber(row.close),
      ret1d: toNumber(row.ret_1d),
      volume: toNumber(row.volume),
      market: inferMarket(ticker),
    });
  }

  cachedFeatureRows = { fileName: latest.fileName, rows };
  return cachedFeatureRows;
}

async function loadLatestCandidateRows(): Promise<{ fileName: string; rows: Tier1CandidateRow[] }> {
  const latest = await findLatestLogFile(CANDIDATES_FILE_REGEX);
  if (!latest) {
    return { fileName: "", rows: [] };
  }

  if (cachedCandidateRows && cachedCandidateRows.fileName === latest.fileName) {
    return cachedCandidateRows;
  }

  const raw = await readFile(latest.filePath, "utf-8");
  const parsedRows = parseCsv(raw);
  const rows: Tier1CandidateRow[] = [];

  for (const row of parsedRows) {
    const ticker = String(row.ticker ?? "").trim().toUpperCase();
    if (!ticker) continue;

    rows.push({
      ticker,
      date: String(row.date ?? "").trim(),
      candidateRank: toNumber(row.candidate_rank),
      ret1d: toNumber(row.ret_1d),
      ret5d: toNumber(row.ret_5d),
      score: toNumber(row.tier1_composite_score),
    });
  }

  cachedCandidateRows = { fileName: latest.fileName, rows };
  return cachedCandidateRows;
}

function scoreToConfluence(rawScore: number, minScore: number, maxScore: number): number | null {
  if (!Number.isFinite(rawScore)) return null;
  if (!Number.isFinite(minScore) || !Number.isFinite(maxScore) || maxScore <= minScore) {
    return 85;
  }
  const normalized = (rawScore - minScore) / (maxScore - minScore);
  return Math.round(clamp(70 + normalized * 29, 0, 99));
}

function buildCandidateSummary(rows: Tier1CandidateRow[]): CandidateSummary[] {
  if (rows.length === 0) return [];

  const sorted = [...rows].sort((a, b) => {
    if (Number.isFinite(a.candidateRank) && Number.isFinite(b.candidateRank) && a.candidateRank !== b.candidateRank) {
      return a.candidateRank - b.candidateRank;
    }
    if (Number.isFinite(a.score) && Number.isFinite(b.score) && a.score !== b.score) {
      return b.score - a.score;
    }
    return a.ticker.localeCompare(b.ticker);
  });

  const finiteScores = sorted.map((row) => row.score).filter((score) => Number.isFinite(score));
  const minScore = finiteScores.length > 0 ? Math.min(...finiteScores) : Number.NaN;
  const maxScore = finiteScores.length > 0 ? Math.max(...finiteScores) : Number.NaN;

  return sorted.map((row, index) => {
    const confluenceScore = scoreToConfluence(row.score, minScore, maxScore);
    const winRate =
      confluenceScore === null
        ? null
        : Math.round(clamp(55 + ((confluenceScore - 70) / 29) * 40, 55, 95) * 10) / 10;

    const avgReturnSource = Number.isFinite(row.ret5d) ? row.ret5d : row.ret1d;
    const avgReturn =
      Number.isFinite(avgReturnSource) ? Math.round((avgReturnSource * 100) * 10) / 10 : null;

    return {
      ticker: row.ticker,
      date: normalizeDate(row.date) || null,
      rank: index + 1,
      winRate,
      avgReturn,
      confluenceScore,
    };
  });
}

async function resolveSymbol(symbolInput: string): Promise<string> {
  const symbol = symbolInput.trim().toUpperCase();
  if (!symbol) return symbol;

  const krxMetaMap = await loadKrxMetaMap();
  if (krxMetaMap.has(symbol)) return symbol;

  if (!symbol.includes(".")) {
    const withKs = `${symbol}.KS`;
    if (krxMetaMap.has(withKs)) return withKs;
    const withKq = `${symbol}.KQ`;
    if (krxMetaMap.has(withKq)) return withKq;

    if (await fileExists(path.join(DATA_DIR, `${withKs}.csv`))) return withKs;
    if (await fileExists(path.join(DATA_DIR, `${withKq}.csv`))) return withKq;
    if (await fileExists(path.join(DATA_DIR, `${symbol}.csv`))) return symbol;
  }

  return symbol;
}

async function readLatestDateForTicker(ticker: string): Promise<string | null> {
  const normalized = ticker.trim().toUpperCase();
  if (!normalized) return null;

  if (cachedLatestDateByTicker.has(normalized)) {
    return cachedLatestDateByTicker.get(normalized) ?? null;
  }

  const csvPath = path.join(DATA_DIR, `${normalized}.csv`);
  try {
    const raw = await readFile(csvPath, "utf-8");
    const lines = raw
      .replace(/^\uFEFF/, "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length < 2) {
      cachedLatestDateByTicker.set(normalized, null);
      return null;
    }

    const lastRow = splitCsvLine(lines[lines.length - 1]);
    const latestDate = normalizeDate(lastRow[0] ?? "");
    const value = latestDate || null;
    cachedLatestDateByTicker.set(normalized, value);
    return value;
  } catch {
    cachedLatestDateByTicker.set(normalized, null);
    return null;
  }
}

export async function getLocalHomeRankings(limit = 3): Promise<LocalHomeRanking[]> {
  const [{ rows: candidateRows }, krxMetaMap] = await Promise.all([loadLatestCandidateRows(), loadKrxMetaMap()]);
  const summaryRows = buildCandidateSummary(candidateRows).slice(0, Math.max(0, limit));

  return summaryRows.map((row) => ({
    rank: row.rank,
    win_rate: row.winRate ?? 0,
    avg_return: row.avgReturn ?? 0,
    confluence_score: row.confluenceScore ?? 0,
    ticker: row.ticker,
    name: krxMetaMap.get(row.ticker)?.name ?? row.ticker,
  }));
}

export async function getLocalSearchResult(symbolInput: string): Promise<LocalSearchResult | null> {
  const symbol = symbolInput.trim().toUpperCase();
  if (!symbol) return null;

  const [resolvedSymbol, krxMetaMap, { rows: candidateRows }] = await Promise.all([
    resolveSymbol(symbol),
    loadKrxMetaMap(),
    loadLatestCandidateRows(),
  ]);

  const candidateSummary = buildCandidateSummary(candidateRows);
  const candidateIndex = new Map(candidateSummary.map((row) => [row.ticker, row]));
  const summary = candidateIndex.get(resolvedSymbol);
  const latestDate = await readLatestDateForTicker(resolvedSymbol);
  const exists =
    Boolean(summary) ||
    krxMetaMap.has(resolvedSymbol) ||
    (await fileExists(path.join(DATA_DIR, `${resolvedSymbol}.csv`)));

  if (!exists) return null;

  const meta = krxMetaMap.get(resolvedSymbol);
  return {
    ticker: resolvedSymbol,
    name: meta?.name ?? resolvedSymbol,
    sector: meta?.market ?? null,
    ranking_date: summary?.date ?? latestDate,
    rank: summary?.rank ?? null,
    win_rate: summary?.winRate ?? null,
    avg_return: summary?.avgReturn ?? null,
    confluence_score: summary?.confluenceScore ?? null,
  };
}

export async function getLocalMarketRows(market: MarketCode, limit = 6): Promise<{
  items: LocalMarketRow[];
  sourceFile: string | null;
}> {
  const [{ fileName, rows }, krxMetaMap] = await Promise.all([loadLatestFeatureRows(), loadKrxMetaMap()]);

  const filtered = rows
    .filter((row) => row.market === market)
    .sort((a, b) => {
      const volumeA = Number.isFinite(a.volume) ? a.volume : -1;
      const volumeB = Number.isFinite(b.volume) ? b.volume : -1;
      return volumeB - volumeA;
    })
    .slice(0, Math.max(0, limit));

  const items = filtered.map((row) => ({
    ticker: row.ticker,
    name: krxMetaMap.get(row.ticker)?.name ?? row.ticker,
    close: Number.isFinite(row.close) ? row.close : null,
    change_pct: Number.isFinite(row.ret1d) ? row.ret1d * 100 : null,
    volume: Number.isFinite(row.volume) ? row.volume : null,
    trade_date: normalizeDate(row.date),
    market: row.market,
    currency: inferCurrency(row.market),
  }));

  return {
    items,
    sourceFile: fileName || null,
  };
}
