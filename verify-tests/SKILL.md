---
name: verify-tests
description: Verify test presence and runnable test workflow for this repository. Use when tests, test configuration, or tested adapters change.
---

# Verify Tests

## Purpose

Keep test coverage and test execution wiring healthy.

1. Ensure test directory and key test files exist.
2. Ensure key local search adapter behavior is asserted.
3. Ensure test scripts are present in `package.json`.
4. Execute tests when script support is available.

## Related Files

| File Pattern | Purpose |
|---|---|
| `tests/**/*.test.ts` | Test cases for runtime behavior. |
| `tests/api-search.test.ts` | Core local search adapter unit test coverage. |
| `vitest.config.ts` | Test runner configuration. |
| `package.json` | Script declarations for test/typecheck execution. |
| `lib/searchStock.ts` | Source module targeted by key tests. |
| `lib/localDb.ts` | Mocked local data dependency in tests. |

## Workflow

### Step 1: Check Test Files Exist

```bash
test -d tests
test -f tests/api-search.test.ts
test -f vitest.config.ts
```

### Step 2: Verify Key Test Assertions and Mocks

```bash
rg -n "describe\\(|it\\(|expect\\(|vi\\.spyOn|getLocalSearchResult|searchStock" tests/api-search.test.ts
```

### Step 3: Verify Required Scripts Exist

```bash
rg -n "\"test\"\\s*:|\"typecheck\"\\s*:" package.json
```

### Step 4: Execute Tests

Run only if `test` script exists:

```bash
npm test
```

Optional:

```bash
npm run typecheck
```

## Pass/Fail Criteria

Pass:
- `tests` directory, key test file, and vitest config exist.
- Key search test contains assertions/mocks for local search path.
- `test` script exists in `package.json`.
- `npm test` passes when executed.

Fail:
- Missing key test files/config.
- Test no longer validates local search path.
- Missing `test` script.
- Test execution returns non-zero status.

If a command is unavailable in the environment, mark that check as `SKIP` with the reason and run the closest `rg`-based fallback.

## Output Format

```markdown
## verify-tests Report

| Check | Status | Evidence | Action |
|---|---|---|---|
| Test file existence | PASS/FAIL | command output summary | add missing tests/config |
| Key test coverage | PASS/FAIL | file refs / rg matches | update tests for local path |
| Script availability | PASS/FAIL | package.json refs | add missing npm scripts |
| Test execution | PASS/FAIL/SKIP | command result | fix failing tests or skip rationale |
| Optional typecheck | PASS/FAIL/SKIP | command result | fix type errors or skip rationale |
```
