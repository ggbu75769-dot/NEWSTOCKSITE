import { readFile } from "node:fs/promises";
import path from "node:path";

const KRX_MASTER_PATH = path.join(process.cwd(), "data", "krx_symbol_master.csv");

let cachedMap: Map<string, string> | null = null;

function parseCsv(text: string): Array<Record<string, string>> {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const cols = line.split(",");
    const row: Record<string, string> = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = (cols[i] ?? "").trim();
    }
    return row;
  });
}

export async function loadKrxMasterNameMap(): Promise<Map<string, string>> {
  if (cachedMap) return cachedMap;

  try {
    const raw = await readFile(KRX_MASTER_PATH, "utf-8");
    const rows = parseCsv(raw);
    const map = new Map<string, string>();

    for (const row of rows) {
      const symbol = String(row.symbol ?? "").trim();
      const name = String(row.name_ko ?? "").trim();
      if (!symbol || !name) continue;
      map.set(symbol, name);
    }

    cachedMap = map;
    return map;
  } catch (err) {
    console.error("[recommendations] failed to load KRX master csv", err);
    return new Map();
  }
}
