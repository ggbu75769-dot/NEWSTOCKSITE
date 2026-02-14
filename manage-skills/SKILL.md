---
name: manage-skills
description: Maintain and evolve local verify skills when the codebase changes. Use when adding, updating, or auditing verify workflows; when changed files are not covered by existing verify skills; or when verify skill references become stale.
---

# Manage Skills

## Purpose

Keep project verification skills accurate as the codebase evolves.

1. Detect changed files in the current branch or working tree.
2. Map changes to existing `verify-*` skills.
3. Update affected skills to prevent stale checks.
4. Create new `verify-*` skills when uncovered patterns are repeated.
5. Keep skill registries synchronized.

## Related Files

| File | Purpose |
|------|---------|
| `manage-skills/SKILL.md` | Source of truth for registered verify skills and this maintenance workflow. |
| `verify-implementation/SKILL.md` | Execution order and list of verify skills to run. |
| `CLAUDE.md` | Top-level project skill index for this repository. |
| `verify-api-routes/SKILL.md` | API route verification skill definition. |
| `verify-ui-pages/SKILL.md` | UI page/component wiring verification skill definition. |
| `verify-lib-localdata/SKILL.md` | Local data adapter verification skill definition. |
| `verify-tests/SKILL.md` | Test coverage and test execution verification skill definition. |
| `verify-deps/SKILL.md` | Dependency/script hygiene verification skill definition. |
| `verify-local-mode/SKILL.md` | Local-data mode verification workflow and regression checks. |
| `verify-*/SKILL.md` | Individual verification skills maintained by this workflow. |

## Registered Verify Skills

| Skill | Scope | File Patterns |
|------|------|---------------|
| `verify-deps` | Verify dependency hygiene, required scripts, and no Supabase deps | `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.js` |
| `verify-lib-localdata` | Verify local data adapters and file-based loaders | `lib/localDb.ts`, `lib/searchStock.ts`, `lib/recommendations/**`, `data/**`, `logs/**` |
| `verify-api-routes` | Verify app API route handlers and local adapter wiring | `app/api/**/route.ts`, `app/api/search/route.ts`, `app/api/market/route.ts`, `app/api/recommendations/route.ts` |
| `verify-ui-pages` | Verify page/component wiring and local UI flow | `app/**/page.tsx`, `components/**/*.tsx`, `components/**/*.jsx` |
| `verify-tests` | Verify test files, key assertions, and runnable test scripts | `tests/**`, `vitest.config.ts`, `package.json` |
| `verify-local-mode` | Verify local-data operation after Supabase removal | `app/page.tsx`, `app/dashboard/page.tsx`, `app/recommendations/page.tsx`, `app/login/page.tsx`, `app/api/search/route.ts`, `app/api/market/route.ts`, `components/HomeView.tsx`, `components/DashboardView.tsx`, `components/RecommendationsView.tsx`, `components/SearchBar.tsx`, `components/SignOutButton.tsx`, `lib/localDb.ts`, `lib/searchStock.ts`, `lib/recommendations/tier1.ts`, `tests/api-search.test.ts`, `package.json` |

## Workflow

### Step 1: Collect Changed Files

Gather changed files from both uncommitted and committed work:

```bash
git diff --name-only
git diff --cached --name-only
git diff main...HEAD --name-only 2>/dev/null
```

Normalize, deduplicate, and group by top-level directory.

### Step 2: Build Skill Coverage Map

For each registered `verify-*` skill:

1. Read `verify-<name>/SKILL.md`.
2. Extract declared file paths and patterns from `Related Files` and workflow commands.
3. Map changed files to matching skills.

Classify each changed file as:

- `COVERED`: matched by at least one skill.
- `UNCOVERED`: not matched by any skill.

### Step 3: Audit Affected Skills

For each affected skill, check for maintenance issues:

1. Missing references: changed files are relevant but absent from the skill.
2. Stale references: skill points to removed or moved files.
3. Broken commands: grep/glob patterns no longer match current structure.
4. Drifted rules: validation logic no longer reflects current implementation.

Record concrete evidence (file path, command output, and impact).

### Step 4: Decide Update vs Create

Use this policy:

1. Update an existing skill when uncovered files clearly belong to its domain.
2. Create a new `verify-*` skill when uncovered files form a repeated, coherent pattern.
3. Leave as out-of-scope when changes are docs, generated files, lockfiles, or unrelated infra.

Ask the user before creating a new skill name or making broad restructuring changes.

### Step 5: Update Existing Skills

When updating a skill:

1. Add missing `Related Files` entries.
2. Update workflow checks with concrete file patterns.
3. Keep pass/fail criteria explicit and testable.
4. Preserve valid existing checks; do not remove useful coverage without cause.

### Step 6: Create New Verify Skill

When creating a new skill:

1. Use folder name format: `verify-<scope>` (kebab-case).
2. Create `verify-<scope>/SKILL.md` with minimal frontmatter:

```yaml
---
name: verify-<scope>
description: Verify <scope> changes and detect regressions. Use when files under <patterns> are modified.
---
```

3. Include sections for `Purpose`, `Related Files`, `Workflow`, and `Output Format`.
4. Add concrete validation commands tied to real repository paths.

### Step 7: Sync Registries

After any create/update:

1. Update the `Registered Verify Skills` table in `manage-skills/SKILL.md`.
2. Update the execution list in `verify-implementation/SKILL.md`.
3. Update the skill index in `CLAUDE.md` if it exists.

Ensure names and descriptions are consistent across all three files.

### Step 8: Validate

Before finishing:

1. Re-read edited skill files.
2. Confirm every referenced path exists.
3. Run representative commands from updated workflows.
4. Confirm markdown tables and code blocks render correctly.

## Output Format

Return a short maintenance report:

```markdown
## Skill Maintenance Report

### Changed Files
- <count> files analyzed

### Updated Skills
- verify-<name>: <what changed>

### New Skills
- verify-<name>: <scope>

### Uncovered / Deferred
- <file or pattern>: <reason>
```

## Exceptions

Do not force skill updates for:

1. Lockfiles and generated artifacts.
2. Pure documentation-only changes.
3. Third-party vendored code.
4. Build system changes that are unrelated to verification scope.
