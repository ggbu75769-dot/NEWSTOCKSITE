---
name: verify-ui-pages
description: Verify page/component wiring for local UI flow. Use when app page files or components are changed.
---

# Verify UI Pages

## Purpose

Validate page-to-component wiring and local client flow in UI layers.

1. Ensure key page files and core components exist.
2. Ensure pages import and render expected view components.
3. Ensure local API usage and navigation flow are intact.
4. Ensure Supabase/session-client coupling is not reintroduced.

## Related Files

| File Pattern | Purpose |
|---|---|
| `app/**/page.tsx` | Next.js page entrypoints. |
| `app/page.tsx` | Home page wiring to `HomeView`. |
| `app/dashboard/page.tsx` | Dashboard page wiring to `DashboardView`. |
| `app/recommendations/page.tsx` | Recommendations page wiring to `RecommendationsView`. |
| `app/login/page.tsx` | Local redirect/deprecation login behavior. |
| `components/**/*.tsx` | UI component layer including search/dashboard/recommendations views. |
| `components/**/*.jsx` | JSX UI components used by pages. |

## Workflow

### Step 1: Check Key Pages and Components Exist

```bash
test -f app/page.tsx
test -f app/dashboard/page.tsx
test -f app/recommendations/page.tsx
test -f app/login/page.tsx
test -f components/HomeView.tsx
test -f components/DashboardView.tsx
test -f components/RecommendationsView.tsx
test -f components/SearchBar.tsx
test -f components/SignOutButton.tsx
```

### Step 2: Verify Page-to-View Wiring

```bash
rg -n "HomeView|DashboardView|RecommendationsView|redirect\\(\"/dashboard\"\\)" app/page.tsx app/dashboard/page.tsx app/recommendations/page.tsx app/login/page.tsx
```

### Step 3: Verify Local UI Data Flow and API Usage

```bash
rg -n "/api/search|/api/market|fetchRecommendations|sessionStorage|window\\.location\\.href" components/HomeView.tsx components/DashboardView.tsx components/RecommendationsView.tsx components/SearchBar.tsx components/SignOutButton.tsx
```

### Step 4: Check for Forbidden Supabase References

```bash
rg -n "supabase|@supabase" app components
```

### Step 5: Optional Type Validation

Run only if `typecheck` script exists:

```bash
rg -n "\"typecheck\"\\s*:" package.json
npm run typecheck
```

## Pass/Fail Criteria

Pass:
- Required page/component files exist.
- Pages reference expected view components and login redirect behavior.
- UI layer shows local API/data flow paths.
- No Supabase references in `app` or `components`.
- Optional typecheck passes when executed.

Fail:
- Missing key page/component files.
- Broken or missing page-to-view wiring.
- Missing local API/data flow hooks in affected components.
- Any Supabase reference appears in UI/page layers.
- Typecheck fails when run.

If a command is unavailable in the environment, mark that check as `SKIP` with the reason and run the closest `rg`-based fallback.

## Output Format

```markdown
## verify-ui-pages Report

| Check | Status | Evidence | Action |
|---|---|---|---|
| Key files exist | PASS/FAIL | command output summary | restore missing files |
| Page wiring | PASS/FAIL | file refs / rg matches | fix page imports/rendering |
| Local UI data flow | PASS/FAIL | file refs / rg matches | restore API/local flow hooks |
| Supabase regression | PASS/FAIL | command output summary | remove forbidden references |
| Optional typecheck | PASS/FAIL/SKIP | command result | fix type errors or skip rationale |
```
