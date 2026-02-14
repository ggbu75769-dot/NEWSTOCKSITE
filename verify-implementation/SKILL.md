---
name: verify-implementation
description: Run all registered verify skills and produce a consolidated implementation verification report. Use before review/merge, after major refactors, or when validating behavior after broad code changes.
---

# Verify Implementation

## Purpose

Execute registered `verify-*` skills in sequence and summarize project health.

1. Load and run each listed verification skill.
2. Aggregate pass/fail results with concrete evidence.
3. Highlight actionable fixes for failing checks.

## Execution Skills

| # | Skill | Scope |
|---|------|-------|
| 1 | `verify-deps` | Validate dependency/script hygiene and no Supabase deps. |
| 2 | `verify-lib-localdata` | Validate local data adapters and file-based loaders. |
| 3 | `verify-api-routes` | Validate API route wiring and JSON/error responses. |
| 4 | `verify-ui-pages` | Validate page/component local flow wiring. |
| 5 | `verify-tests` | Validate test presence and test execution health. |
| 6 | `verify-local-mode` | Validate integrated local-mode runtime and no Supabase regressions. |

## Policy Flags

- `full`: run all registered verify skills regardless of changed files.
- `strict`: fail verification if any changed files remain `UNCOVERED` after mapping.

## Workflow

### Step 1: Resolve Execution Mode

If a specific verify skill name is provided, run only that skill.
Otherwise choose mode:

1. `full` flag enabled: run the full list from `Execution Skills`.
2. Default selective mode: run only skills mapped from changed files.

### Step 2: Build Changed File Set (Selective Mode)

Collect candidate changed files:

```bash
git diff --name-only
git diff --cached --name-only
git diff main...HEAD --name-only 2>/dev/null
```

Normalize path separators, trim blanks, deduplicate, then sort for deterministic processing.

### Step 3: Load Registered Verify Skills

Read the `Registered Verify Skills` table from `manage-skills/SKILL.md`.

For each listed skill:

1. Parse skill name and file patterns.
2. Keep table order as the deterministic run order.
3. Use this list as the source of truth for selective execution.

### Step 4: Map Changed Files to Skills

Map each changed file against each registered skill pattern using:

1. Exact path match (literal file path).
2. Prefix match (pattern prefix matches file path).
3. Recursive `**` match (e.g. `app/**` matches nested files under `app/`).

Classify each changed file:

- `COVERED`: matched by one or more verify skills.
- `UNCOVERED`: matched by none.

### Step 5: Resolve Final Execution Set

Rules:

1. Explicit skill input: run only that skill.
2. `full` flag: run all registered skills.
3. Selective mode: run only skills that matched at least one changed file, in deterministic table order.

If `strict` flag is enabled and any `UNCOVERED` files exist, mark verification as failed.

### Step 6: Execute Each Verify Skill

For each skill:

1. Read `<skill-name>/SKILL.md`.
2. Execute checks defined in its workflow.
3. Capture command output, file references, and pass/fail status.

### Step 7: Aggregate Findings

Group results by severity:

1. Blocking failures (must fix before merge).
2. Non-blocking warnings.
3. Passed checks.
4. Coverage summary (`COVERED` vs `UNCOVERED` files).

### Step 8: Provide Fix Plan

For each failed check, include:

1. Exact failing evidence (file/command).
2. Minimal remediation steps.
3. Recommended re-check command.

## Output Format

```markdown
## Implementation Verification Report

### Summary
- Skills run: <n>
- Passed: <n>
- Failed: <n>
- Mode: <explicit-skill/full/selective>
- Policy flags: full=<on/off>, strict=<on/off>
- Coverage: COVERED=<n>, UNCOVERED=<n>

### Results
| Skill | Status | Failures | Notes |
|------|--------|----------|-------|
| verify-<name> | PASS/FAIL | <count> | <short note> |

### Coverage
| File | Status | Matched Skills |
|------|--------|----------------|
| <path> | COVERED/UNCOVERED | <skill list or -> |

### Findings
1. <severity> <issue with file refs>

### Next Checks
1. <command>
2. <command>
```

## Exceptions

1. If no execution skills are registered, return a clear "no verify skills registered" result instead of failing.
2. If a skill file is missing, mark that skill as failed with remediation to restore it.
3. If a command is unavailable in the environment, mark as blocked and provide an alternative command where possible.
4. In selective mode, if no changed files are found, return a no-op result unless `full` is enabled.
