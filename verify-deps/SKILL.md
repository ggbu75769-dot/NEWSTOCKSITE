---
name: verify-deps
description: Verify dependency and script hygiene for local-mode runtime. Use when package manifests, lockfiles, or build/test script definitions change.
---

# Verify Dependencies

## Purpose

Protect dependency hygiene and required script availability.

1. Ensure package manifest/lockfile exist.
2. Ensure forbidden Supabase packages are absent.
3. Ensure required scripts for validation are present.
4. Optionally run script smoke checks when available.

## Related Files

| File Pattern | Purpose |
|---|---|
| `package.json` | Dependency and script source of truth. |
| `package-lock.json` | Locked dependency graph consistency. |
| `tsconfig.json` | Typecheck configuration dependency. |
| `next.config.js` | Build/runtime framework config. |

## Workflow

### Step 1: Check Required Manifest Files Exist

```bash
test -f package.json
test -f package-lock.json
test -f tsconfig.json
test -f next.config.js
```

### Step 2: Check for Forbidden Supabase Dependencies

```bash
rg -n "@supabase|supabase" package.json package-lock.json
```

### Step 3: Verify Required NPM Scripts

```bash
rg -n "\"dev\"\\s*:|\"build\"\\s*:|\"test\"\\s*:|\"typecheck\"\\s*:" package.json
```

### Step 4: Optional Script Smoke Checks

Run only if corresponding script exists:

```bash
npm run typecheck
npm test
npm run build
```

## Pass/Fail Criteria

Pass:
- Required manifest/config files exist.
- No forbidden Supabase dependencies in manifest/lockfile.
- Required scripts (`dev`, `build`, `test`, `typecheck`) exist.
- Optional smoke checks pass when executed.

Fail:
- Missing manifest/config files.
- Forbidden Supabase dependency reference found.
- Missing required scripts.
- Any executed smoke check fails.

If a command is unavailable in the environment, mark that check as `SKIP` with the reason and run the closest available script or `rg` check.

## Output Format

```markdown
## verify-deps Report

| Check | Status | Evidence | Action |
|---|---|---|---|
| Manifest/config existence | PASS/FAIL | command output summary | restore missing files |
| Forbidden deps | PASS/FAIL | command output summary | remove banned dependencies |
| Required scripts | PASS/FAIL | package.json refs | add missing scripts |
| Typecheck smoke | PASS/FAIL/SKIP | command result | fix type issues or skip rationale |
| Test smoke | PASS/FAIL/SKIP | command result | fix test issues or skip rationale |
| Build smoke | PASS/FAIL/SKIP | command result | fix build issues or skip rationale |
```
