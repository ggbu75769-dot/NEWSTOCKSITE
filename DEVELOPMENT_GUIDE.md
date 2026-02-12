# DEVELOPMENT_GUIDE

This document is the **source of truth** for development in this repository.
It is based on the current codebase state as of 2026-02-12.

## 0) Scope Notes
- Root and app code were reviewed.
- There is **no `/src` directory** in the active app; implementation lives in `app/`, `components/`, `lib/`, and root Python/SQL scripts.
- `_ui_ref/` is a separate UI reference sandbox and is not part of the runtime Next.js app.

## 1) Current Architecture

### 1.1 High-Level System
- Frontend/App: Next.js App Router + React + TypeScript + Tailwind.
- Auth/Data API: Supabase (SSR + browser client, RPC, RLS-backed tables/views).
- Batch/Data Pipeline: Python scripts for ingestion/ETL/analytics (PostgreSQL and R2/DuckDB paths).

### 1.2 Folder Responsibilities
- `app/`: route entrypoints, server components, route handlers, global providers/styles.
- `components/`: client UI and interaction logic.
- `lib/`: reusable service code (`supabase` client/server factories, domain helpers like `searchStock`).
- `tests/`: Vitest unit tests.
- Root `*.py`: data ingestion/ETL/analytics orchestrators.
- Root `*.sql`: schema definitions (Supabase and relational pipeline).
- Root docs (`*.md`): operational notes and analysis.

### 1.3 Routing and Rendering Pattern
- App Router routes:
- `app/page.tsx`: server component; fetches ranking data and session before rendering `HomeView`.
- `app/login/page.tsx`: server component; redirects authenticated users.
- `app/dashboard/page.tsx`: server component; auth gate + render `DashboardView`.
- `app/api/search/route.ts`: server route; validates query and returns JSON.
- `app/auth/callback/route.ts`: OAuth callback exchange + profile upsert + redirect.

### 1.4 State Management Pattern
- No global state library (no Redux/Zustand/Jotai currently).
- State is local/component-level via React hooks.
- Cross-app shared state is minimal and handled by:
- I18n context provider (`I18nextProvider`).
- Browser persistence (`localStorage`, `sessionStorage`) for language/theme/market override.
- Server session resolution in `lib/supabase/server.ts`.

### 1.5 Styling Pattern
- Tailwind utility-first classes + CSS variables in `app/globals.css`.
- Theme tokens use HSL CSS custom properties (`--background`, `--primary`, etc.).
- Reusable visual utilities/classes (`card-elevated`, animation classes) are defined in `globals.css`.

### 1.6 Data Flow (UI <-> Services)
- Home rankings:
- `app/page.tsx` -> Supabase view `daily_rankings_public` -> `HomeView` props.

- Search:
- `components/SearchBar.tsx` -> `GET /api/search?symbol=...` -> `lib/searchStock.ts` -> Supabase RPC `search_stock_public` -> JSON -> UI state render.

- Auth:
- `GoogleSignInButton` / `AuthPanel` -> Supabase OAuth -> `app/auth/callback/route.ts` exchange + `profiles` upsert -> redirect.

- Dashboard market data:
- `DashboardView` browser client -> `latest_prices` query + realtime channel subscription.

- Batch data update (backend operations):
- Root Python scripts -> external market data APIs -> PostgreSQL and/or R2 parquet datasets.

## 2) Coding Standards

### 2.1 TypeScript and Safety
- `tsconfig.json` uses `strict: true`. Keep strict mode clean.
- No `any` unless unavoidable and documented with reason.
- Create explicit types at domain boundaries:
- API response types.
- Supabase row/result types where practical.
- Component props.

### 2.2 Naming Conventions
- Components: `PascalCase` file and symbol names (`HomeView.tsx`).
- Functions/variables: `camelCase`.
- Constants: `UPPER_SNAKE_CASE` only for true constants.
- Route segment names: lowercase path folders in `app/`.

### 2.3 Component Patterns
- Keep route files thin: fetch/guard in route, render via components.
- Keep presentational components focused on UI.
- Move non-trivial side-effect/data logic into dedicated hooks/services.
- Prefer small composable components over very large page components.

### 2.4 Tailwind/CSS Usage
- Use design tokens (existing CSS variables) first; avoid arbitrary one-off colors.
- Prefer consistent spacing/typography scales over ad hoc utility drift.
- Reuse established utility classes in `globals.css` for repeated motion/elevation patterns.

### 2.5 API and Service Boundaries
- Validate and normalize all incoming API route inputs.
- Keep route handlers thin; move reusable business logic to `lib/`.
- Avoid duplicating Supabase query logic across UI components.

### 2.6 Testing Standards
- Minimum for behavior changes:
- Unit tests for pure logic helpers in `lib/`.
- Route-level tests for API handlers when behavior changes.
- For security-sensitive flows (auth/callback/redirect), add regression tests.

## 3) Operational Workflow (Required)

### 3.1 New Feature Workflow
1. Define route impact:
- Decide server vs client boundary first.
- Confirm data source (Supabase view/table/RPC or internal API route).

2. Define contracts:
- Add/adjust TypeScript types for request/response and component props.

3. Implement logic in the right layer:
- Reusable data/business logic -> `lib/`.
- Component interaction logic with side effects -> custom hook in `components/hooks` (create this folder when first needed).
- Route handler orchestration only in `app/api/*`.

4. Build UI:
- Compose existing components/utilities first.
- Keep i18n strings in locale resources and never hardcode visible copy directly in components.

5. Validate:
- Run `npm run typecheck` and `npm test`.
- Manually verify auth-gated and anonymous behavior when relevant.

### 3.2 Required Rules for Consistency
- Always reference this guide before code generation.
- Always follow current architecture boundaries (route -> component -> lib/service).
- Always prefer extraction to hooks/services when a component exceeds a single concern.
- Always keep i18n keys synchronized for `ko` and `en`.
- Never introduce a second competing state-management approach without explicit architectural approval.

### 3.3 Pipeline-Side Workflow (Python/SQL)
1. Update schema-first if data model changes.
2. Keep ETL scripts idempotent and retry-safe.
3. Validate env requirements explicitly before execution.
4. Add logging and summary output for operational visibility.

## 4) Current Known Architectural Constraints
- Monolithic UI components currently hold both presentation and orchestration logic.
- Translation resources are centralized in a single file and need modularization.
- App and data pipeline coexist in one repo; maintain clear boundaries to avoid cross-layer coupling.
