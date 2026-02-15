# Skill Index

This repository uses local verification skills to keep implementation checks consistent.

## Skills

- `manage-skills`: Use for skill maintenance, coverage mapping for changed files, and registry synchronization.
- `verify-implementation`: Use to run all registered `verify-*` skills and consolidate one verification report.
- `verify-deps`: Use for dependency/script hygiene checks and forbidden package regression checks.
- `verify-lib-localdata`: Use for local data adapter and file-based loader verification.
- `verify-api-routes`: Use for `app/api` route wiring (including auth endpoints) and JSON/error response checks.
- `verify-ui-pages`: Use for page/component wiring and local/auth UI flow checks.
- `verify-tests`: Use for test presence and test execution checks.
- `verify-local-mode`: Use to prevent local-data mode regressions (with auth flow intact) and ensure Supabase is not reintroduced.

## Typical Workflow

1. After code changes: run `manage-skills` to verify changed files are covered by verify skills.
2. Before review/merge: run `verify-implementation` to execute registered verify skills and review the consolidated result.
3. For scoped changes: run a specific `verify-*` skill directly.

## Execution Model

- `verify-implementation` determines execution order.
- Individual `verify-*` skills must remain independent and deterministic.

## Skill Governance

- All new verification logic must be implemented as a `verify-*` skill.
- `manage-skills` must update registries when code structure changes.
- Skill names must remain kebab-case and folder-aligned.

## Locations

- `manage-skills/SKILL.md`
- `verify-implementation/SKILL.md`
- `verify-deps/SKILL.md`
- `verify-lib-localdata/SKILL.md`
- `verify-api-routes/SKILL.md`
- `verify-ui-pages/SKILL.md`
- `verify-tests/SKILL.md`
- `verify-local-mode/SKILL.md`
