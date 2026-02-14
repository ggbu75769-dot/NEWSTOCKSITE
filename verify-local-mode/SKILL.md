---
name: verify-local-mode
description: Verify that the app operates in local-data mode without Supabase dependencies. Use when touching data access, search/market APIs, recommendations loading, dashboard/home UI wiring, local auth behavior, tests, or package dependencies related to backend data providers.
---

# Verify Local Mode

## Purpose

Prevent regressions after migration from Supabase to local CSV/log-based data.

1. Ensure Supabase dependencies and code references do not re-enter.
2. Ensure local data entrypoints are present and wired.
3. Ensure primary pages use local flow (no auth-gated server session).
4. Ensure typecheck and tests pass.

## Role with Other Verify Skills

This skill is the umbrella local-mode regression check.

- Use `verify-api-routes`, `verify-ui-pages`, `verify-lib-localdata`, `verify-tests`, and `verify-deps` for targeted selective checks.
- Use this skill when you need integrated end-to-end confidence across app/components/lib/tests/deps in one pass.

## Related Files

| File | Purpose |
|------|---------|
| `lib/localDb.ts` | Local data access layer for search, rankings, and market rows. |
| `lib/searchStock.ts` | Local stock search adapter. |
| `lib/recommendations/tier1.ts` | Recommendations loader from local logs CSV. |
| `app/api/search/route.ts` | Search API endpoint using local search. |
| `app/api/market/route.ts` | Market API endpoint using local market rows. |
| `app/page.tsx` | Home page server wiring to local rankings. |
| `app/dashboard/page.tsx` | Dashboard page without server session dependency. |
| `app/recommendations/page.tsx` | Recommendations page in local mode. |
| `app/login/page.tsx` | Local login behavior (redirect/deprecation path). |
| `components/HomeView.tsx` | Home UI flow and local navigation wiring. |
| `components/DashboardView.tsx` | Dashboard local market fetch and rendering. |
| `components/RecommendationsView.tsx` | Recommendations UI in local mode. |
| `components/SearchBar.tsx` | Local search UI behavior. |
| `components/SignOutButton.tsx` | Local mode reset/exit behavior. |
| `tests/api-search.test.ts` | Unit test coverage for local search adapter. |
| `package.json` | Dependency source of truth (must not contain `@supabase/*`). |

## Workflow

### Step 1: Check for Supabase Regression

Run:

```bash
rg -n "supabase|@supabase" app components lib tests package.json package-lock.json
```

Pass criteria:
- No matches.

Fail criteria:
- Any direct or transitive app-level Supabase reference appears in checked files.

### Step 2: Check Local Data Entry Points

Run:

```bash
rg -n "getLocalSearchResult|getLocalHomeRankings|getLocalMarketRows" lib app
```

Pass criteria:
- `getLocalSearchResult` is used by `lib/searchStock.ts`.
- `getLocalHomeRankings` is used by `app/page.tsx`.
- `getLocalMarketRows` is used by `app/api/market/route.ts`.

Fail criteria:
- Any local data function is missing, renamed without callers updated, or unused.

### Step 3: Check API Route Wiring

Run:

```bash
rg -n "searchStock\\(|/api/market|NextResponse\\.json" app/api
```

Pass criteria:
- `app/api/search/route.ts` calls `searchStock(symbol)`.
- `app/api/market/route.ts` exists and returns JSON payload.

Fail criteria:
- Search route depends on removed server client/session APIs.
- Market route is missing or does not return structured JSON.

### Step 4: Check Page and UI Local Flow

Run:

```bash
rg -n "isLoggedIn|DashboardView|RecommendationsView|redirect\\(\"/dashboard\"\\)|/api/market|searchStock|sessionStorage" app/page.tsx app/dashboard/page.tsx app/recommendations/page.tsx app/login/page.tsx components/HomeView.tsx components/DashboardView.tsx components/RecommendationsView.tsx components/SearchBar.tsx components/SignOutButton.tsx
```

Pass criteria:
- Home page renders with local ranking flow.
- Dashboard page renders without server session checks.
- Recommendations page renders in local mode.
- Login page performs local redirect behavior (or is explicitly deprecated).
- UI components use local API/data flow and do not depend on removed auth clients.

Fail criteria:
- Any page/UI component reintroduces server-session/Supabase-based gating.

### Step 5: Check Local Search Test Coverage

Run:

```bash
rg -n "getLocalSearchResult|searchStock" tests/api-search.test.ts lib/searchStock.ts
```

Pass criteria:
- `tests/api-search.test.ts` validates local search behavior.
- `lib/searchStock.ts` delegates to local DB search function.

Fail criteria:
- Local search path has no test coverage or test references outdated API shape.

### Step 6: Execute Health Checks

Run:

```bash
npm run typecheck
npm test
```

Optional (release-level verification):

```bash
npm run build
```

Pass criteria:
- Typecheck and tests pass.

Fail criteria:
- Any command returns non-zero exit code.

## Output Format

Report findings in this table:

```markdown
## verify-local-mode Report

| Check | Status | Evidence | Action |
|------|--------|----------|--------|
| Supabase regression | PASS/FAIL | command summary | remove offending references |
| Local entrypoints | PASS/FAIL | file refs | restore/rewire functions |
| API wiring | PASS/FAIL | file refs | fix route implementation |
| Page/UI flow | PASS/FAIL | file refs | remove auth/server-session coupling |
| Search test coverage | PASS/FAIL | file refs | update tests for local path |
| Health checks | PASS/FAIL | command results | fix compile/test errors |
```

## Exceptions

Treat these as non-fail by default:

1. Historical scripts under root Python files that still mention Supabase but are not part of active app/runtime flow.
2. External docs or archived notes outside the validated file set.
3. Build warnings about broad file globs, unless the task explicitly targets build-performance hardening.
