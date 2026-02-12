# IMPROVEMENT_PLAN

This plan prioritizes technical debt and risk reduction based on the current codebase.

## 1) Refactoring Needs

### P0 (Immediate)
1. Split oversized UI components
- Files: `components/HomeView.tsx`, `components/DashboardView.tsx`, `components/StockCard.tsx`.
- Issue: page-level composition, business/UI state, formatting, and side effects are mixed in large client components.
- Risk: harder regression control, slower onboarding, brittle edits.
- Solution:
- Extract data/behavior hooks (`useDashboardMarketData`, `useSearch`, `useAuthActions`).
- Split sections into focused components (`HeroSection`, `PricingSection`, `MarketPanel`, etc.).

2. Centralize Supabase browser client usage
- Files: `components/AuthPanel.tsx`, `components/GoogleSignInButton.tsx`, `components/SignOutButton.tsx`, `components/DashboardView.tsx`.
- Issue: repeated direct `createClientSupabaseClient()` usage inside multiple components.
- Risk: inconsistent auth behavior and duplicated implementation details.
- Solution:
- Introduce a shared client hook/provider (`useSupabaseClient`) with singleton-safe initialization.

### P1 (Near-Term)
3. Modularize i18n resources
- File: `app/i18n/client.ts`.
- Issue: all locale resources in one large file.
- Risk: high merge conflict probability, poor scalability.
- Solution:
- Move to `app/i18n/locales/{ko,en}/...json` per domain (`home`, `dashboard`, `auth`, etc.).
- Add lightweight key coverage check in tests.

4. Separate dashboard data logic from rendering
- File: `components/DashboardView.tsx`.
- Issue: market time computation, fetch orchestration, realtime subscription, formatting and rendering live together.
- Solution:
- Extract hooks:
- `useMarketClock`.
- `useMarketOverride`.
- `useLatestPrices` with fetch + realtime updates + retry policy.

## 2) Performance and Security Risks

### P0 (Immediate)
1. Open redirect risk in OAuth callback
- File: `app/auth/callback/route.ts`.
- Issue: `next` query parameter is redirected without strict allowlist validation.
- Impact: potential redirect abuse/phishing vector.
- Solution:
- Allow only internal relative paths and reject absolute URLs.
- Add helper `sanitizeNextPath(next, fallback='/dashboard')`.

2. Session trust model should be hardened server-side
- Files: `lib/supabase/server.ts`, server route/page auth gates.
- Issue: session retrieval via `getSession()` only can be stale/unverified depending on token state.
- Impact: auth edge-case inconsistency.
- Solution:
- Prefer `supabase.auth.getUser()` in critical auth checks, or use both with clear trust policy.

### P1 (Near-Term)
3. Search API input constraints are minimal
- File: `app/api/search/route.ts`.
- Issue: only non-empty validation; no symbol pattern/length constraints.
- Impact: avoidable bad requests and noisy backend load.
- Solution:
- Enforce regex allowlist (`^[A-Z0-9.\-]{1,10}$`) and return 400 for invalid format.

4. Dashboard realtime refresh can over-fetch
- File: `components/DashboardView.tsx`.
- Issue: refreshes on every `historical_prices` change event.
- Impact: excessive reads under heavy write periods.
- Solution:
- Debounce/throttle realtime-triggered fetches.
- Filter change events by `market` where possible.

### P2 (Planned)
5. Pipeline scripts need stronger shared utility layer
- Files: root Python ETL scripts.
- Issue: repeated env-loading, retry, and data transformation patterns across scripts.
- Impact: maintenance overhead and inconsistent behavior.
- Solution:
- Add shared Python module (`pipeline_common/`) for env validation, retry, logging, and fetch adapters.

6. Destructive command safety hardening
- File: `purge_r2_dataset.py`.
- Issue: `--yes` exists but no explicit typed confirmation of bucket/prefix target.
- Impact: accidental data deletion risk.
- Solution:
- Require `--confirm "<bucket>/<prefix>"` exact match.
- Add `--dry-run` mode.

## 3) Proposed Execution Roadmap

### Phase A (Security and reliability first)
1. Implement redirect sanitization in callback route.
2. Harden server-side auth verification policy.
3. Add tests for callback redirect and search input validation.

### Phase B (Maintainability and consistency)
1. Introduce shared Supabase client hook/provider.
2. Refactor `DashboardView` into hooks + presentational sections.
3. Refactor `HomeView` into section components.

### Phase C (Scalability)
1. Split i18n resources into modular locale files.
2. Add realtime fetch throttling strategy.
3. Build `pipeline_common` for Python scripts.

## 4) Definition of Done for Improvement Work
- Typecheck and tests pass (`npm run typecheck`, `npm test`).
- No auth behavior regression for anonymous vs authenticated users.
- Redirects remain internal-only after OAuth callback handling.
- Large components reduced with clear separation of concerns.
- i18n key organization allows domain-level changes without single-file conflict.
