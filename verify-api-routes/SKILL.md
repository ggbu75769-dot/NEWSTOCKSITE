---
name: verify-api-routes
description: Verify Next.js API route wiring, handler shape, and JSON/error responses. Use when files under app/api or their direct lib adapters are changed.
---

# Verify API Routes

## Purpose

Validate local API route behavior and prevent route wiring regressions.

1. Ensure required API route files exist.
2. Ensure route handlers expose HTTP methods (`GET`/`POST`) and return `NextResponse.json`.
3. Ensure routes call expected local adapters.
4. Ensure error responses include explicit status codes.

## Related Files

| File Pattern | Purpose |
|---|---|
| `app/api/**/route.ts` | API route handlers for search/market/recommendations/auth endpoints. |
| `app/api/search/route.ts` | Search route should delegate to `searchStock`. |
| `app/api/market/route.ts` | Market route should delegate to `getLocalMarketRows`. |
| `app/api/recommendations/route.ts` | Recommendations route should delegate to `getTier1Recommendations`. |
| `app/api/auth/register/route.ts` | Register route should validate payload and return structured errors. |
| `app/api/auth/forgot-password/route.ts` | Forgot-password route should issue reset flow response. |
| `app/api/auth/reset-password/route.ts` | Reset-password route should validate token/password and update password. |
| `lib/searchStock.ts` | Search adapter consumed by search API route. |
| `lib/localDb.ts` | Local market data adapter consumed by market API route. |
| `lib/recommendations/tier1.ts` | Recommendations adapter consumed by recommendations API route. |
| `lib/passwordReset.ts` | Password reset token issuance/reset helper used by auth routes. |
| `lib/rateLimit.ts` | Common auth route rate limiting helper. |

## Workflow

### Step 1: Check Required Route Files Exist

```bash
test -d app/api
test -f app/api/search/route.ts
test -f app/api/market/route.ts
test -f app/api/recommendations/route.ts
```

If `test` is unavailable, use:

```bash
rg --files app/api
```

### Step 2: Verify Handler and JSON Response Shape

```bash
rg -n "export async function (GET|POST)|NextResponse\\.json" app/api
```

### Step 3: Verify Adapter Wiring

```bash
rg -n "searchStock\\(|getLocalMarketRows\\(|getTier1Recommendations\\(|issuePasswordReset\\(|resetPasswordByToken\\(|checkRateLimit\\(" app/api
```

### Step 4: Verify Error Status Handling

```bash
rg -n "status:\\s*400|status:\\s*404|status:\\s*500" app/api
```

### Step 5: Check for Forbidden Supabase References

```bash
rg -n "supabase|@supabase" app/api lib/searchStock.ts lib/localDb.ts lib/recommendations/tier1.ts
```

## Pass/Fail Criteria

Pass:
- All required API route files exist.
- Route files expose expected HTTP handlers (`GET`/`POST`) and return JSON responses.
- Search/market/recommendations/auth routes call expected adapters/helpers.
- Error status handling is present where invalid input or runtime errors are handled.
- No Supabase references in API route path and direct adapters.

Fail:
- Any required route file is missing.
- Any route omits expected HTTP handler or JSON response.
- Route wiring to expected adapter is missing.
- Error handling/status responses are absent in relevant branches.
- Any Supabase reference appears in the checked scope.

If a command is unavailable in the environment, mark that check as `SKIP` with the reason and run the closest `rg`-based fallback.

## Output Format

```markdown
## verify-api-routes Report

| Check | Status | Evidence | Action |
|---|---|---|---|
| Required route files | PASS/FAIL | command output summary | add missing route files |
| Handler/JSON shape | PASS/FAIL | file refs / rg matches | fix route response structure |
| Adapter wiring | PASS/FAIL | file refs / rg matches | restore local adapter calls |
| Error status handling | PASS/FAIL | file refs / rg matches | add explicit status responses |
| Supabase regression | PASS/FAIL | command output summary | remove forbidden references |
```
