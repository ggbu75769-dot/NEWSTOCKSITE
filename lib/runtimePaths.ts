import path from "node:path";

function resolveRuntimeDir(envKey: string): string {
  const raw = process.env[envKey]?.trim();
  if (!raw) {
    throw new Error(`${envKey} is not set`);
  }

  return path.isAbsolute(raw) ? raw : path.resolve(raw);
}

export const DATA_DIR = resolveRuntimeDir("VS_DATA_DIR");
export const LOGS_DIR = resolveRuntimeDir("VS_LOGS_DIR");
