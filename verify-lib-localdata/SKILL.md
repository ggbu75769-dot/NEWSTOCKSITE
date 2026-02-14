---
name: verify-lib-localdata
description: Verify local data adapters under lib for search, market, and recommendations flows. Use when lib local-data files or their data/log dependencies change.
---

# Verify Lib Local Data

## Purpose

Validate local data adapter contracts and data-loading paths.

1. Ensure key local-data library files exist.
2. Ensure required local-data exports are present.
3. Ensure search and recommendation adapters delegate correctly.
4. Ensure local filesystem/data usage remains intact without Supabase.

## Related Files

| File Pattern | Purpose |
|---|---|
| `lib/localDb.ts` | Local DB-like access for rankings/search/market rows. |
| `lib/searchStock.ts` | Search adapter wrapping local DB search. |
| `lib/recommendations/*.ts` | Recommendation loading and market metadata helpers. |
| `data/**` | Local source data used by local adapters. |
| `logs/**` | Local logs CSV sources used by recommendation/feature loaders. |

## Workflow

### Step 1: Check Key Local Data Files Exist

```bash
test -f lib/localDb.ts
test -f lib/searchStock.ts
test -f lib/recommendations/tier1.ts
test -f lib/recommendations/client.ts
test -d data
test -d logs
```

### Step 2: Verify Local Data Entry Exports

```bash
rg -n "export async function getLocalHomeRankings|export async function getLocalSearchResult|export async function getLocalMarketRows" lib/localDb.ts
```

### Step 3: Verify Adapter Delegation

```bash
rg -n "getLocalSearchResult" lib/searchStock.ts
rg -n "getTier1Recommendations|readFile|readdir|logs" lib/recommendations/tier1.ts
```

### Step 4: Verify Local Data Path Usage

```bash
rg -n "process\\.cwd\\(|DATA_DIR|LOGS_DIR|readFile|readdir" lib/localDb.ts lib/recommendations/tier1.ts
```

### Step 5: Check for Forbidden Supabase References

```bash
rg -n "supabase|@supabase" lib
```

## Pass/Fail Criteria

Pass:
- Key local-data files and source directories exist.
- `localDb.ts` exports required local entrypoints.
- `searchStock.ts` delegates to `getLocalSearchResult`.
- Recommendation/local adapters use local filesystem/data paths.
- No Supabase references in `lib`.

Fail:
- Any required file/directory is missing.
- Required local-data exports are missing or renamed without updates.
- Adapter delegation is broken.
- Local data path usage is missing.
- Any Supabase reference appears in `lib`.

If a command is unavailable in the environment, mark that check as `SKIP` with the reason and run the closest `rg`-based fallback.

## Output Format

```markdown
## verify-lib-localdata Report

| Check | Status | Evidence | Action |
|---|---|---|---|
| File/dir existence | PASS/FAIL | command output summary | restore missing files/dirs |
| Local exports | PASS/FAIL | file refs / rg matches | re-add expected exports |
| Adapter delegation | PASS/FAIL | file refs / rg matches | fix delegation path |
| Local path usage | PASS/FAIL | file refs / rg matches | restore local file loading |
| Supabase regression | PASS/FAIL | command output summary | remove forbidden references |
```
