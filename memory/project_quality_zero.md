---
name: quality-zero remediation status
description: Progress on driving event-link to absolute-zero issues on all quality platforms (Codacy, SonarCloud, DeepSource, qlty, Semgrep, Codecov)
type: project
---

Active branch: `fix/quality-zero-true-green` (PR #113).

**Why:** 2026-04-16 /ralph-loop run. Goal is zero issues on every
platform (Codacy, SonarCloud, DeepSource, qlty, Semgrep) + 100% coverage
on Codecov for main and PRs. "No exclusions" means fix at the source,
not suppress.

**Architecture primer for future sessions:**
- Quality gates are delegated to `Prekzursil/quality-zero-platform`
  via four workflows in `.github/workflows/quality-zero-*.yml`.
- `shared-scanner-matrix` runs per-lane checks (Sonar Zero, Codacy Zero,
  DeepSource Visible Zero, QLTY Zero, Semgrep Zero, Coverage 100 Gate,
  DeepScan Zero, Sentry Zero, Dependency Alerts, Quality Secrets
  Preflight).
- `DeepSource Visible Zero` queries the DS dashboard and fails when
  count > 0 — it's the *real* zero-check vs the per-language
  "DeepSource: X" commit statuses, which only confirm analysis
  *completed* (not that issues == 0). Watch both — they can disagree.
- Auto-remediation workflow (`quality-zero-remediation.yml`) fires on
  Quality Zero Gate failures via `workflow_run` and uses Codex to
  attempt fixes. Uses `CODEX_AUTH_JSON` secret; skipped if absent.

**Starting counts on main b90e8da (2026-04-16):**
- Codacy: 1248 open issues (FAIL)
- DeepSource dashboard: 1100 visible issues (FAIL)
- Sonar: 0 (pass), QLTY: 0 (pass), DeepScan: 0 (pass), Sentry: 0
- Coverage 100 Gate: pass (only because codecov.yml ignored real source
  files like backend/main.py, seed_data.py, fixture_helpers.py — the
  false-green classic)
- 5 Dependabot alerts (2 critical axios, 1 medium follow-redirects,
  1 medium python-multipart, 1 medium pytest)

**How to apply:** When resuming, first check live status via
`gh pr checks 113` and the specific gate artifacts in
`backend/coverage.xml`, `ui/coverage/cobertura-coverage.xml`, and the
DS / Codacy dashboards. Do not assume earlier counts still hold —
re-query.

**Commits landed on this branch so far:**
1. `6e46872` fix(quality): 7 PTC-W0063 + 5 JS-0116
2. `afd406a` style: Black @ 120 across backend + scripts (93 files)
3. `9496a17` fix: 5 PY-D0002 test-helper class docs + auditor
4. `a352548` fix: 749 docstrings via scripts/add_docstrings.py
5. `816d816` fix: 195 JSDoc blocks via scripts/add_jsdoc.py
6. `5d46cc8` fix(coverage): widen pytest --cov, prune codecov ignore
7. `27ef8db` style: ruff format @ 100 (90 files)
8. `51da8b6` fix: hand-shorten 10 lines in api.py / email_templates.py /
   seed_data.py
9. `c01935c` fix: .flake8 max-line-length=100 + docstring wrapper
10. `28e99e4` fix: tooling line fixes (sync_codacy_repo_tools, etc.)
11. `3c1da5f` fix(deps): axios 1.15.0 / follow-redirects 1.16.0 /
    python-multipart 0.0.26 / pytest 9.0.3
12. `ce2a33f` fix: tighter docstring wrap (95 char)
13. `e7209cb` style: ruff format @ 95 (69 files)
14. `7c1ed3b` fix(security): 32 py/side-effect-in-assert rewrites,
    6 == None → .is_(None), unused imports, return-value fix
15. `eeca480` fix(sonarcloud): inline _safe_resolve_in_repo for S2083

**Reusable tooling left in scripts/:**
- `add_docstrings.py` - libcst-based; inserts meaningful docstrings
  derived from symbol names, places module docstring before
  `from __future__` imports.
- `add_jsdoc.py` - regex-based; inserts JSDoc above TS/TSX
  functions/classes/exported arrows that lack one.
- `wrap_long_docstrings.py` - splits overlong single-line docstrings
  into multi-line form; configurable LINE_LIMIT.
- `refactor_assert_side_effects.py` - libcst rewriter for
  py/side-effect-in-assert test patterns.
- `find_missing_docstrings.py` - ast auditor matching DS PY-D0002/0003.
- `count_long_lines.py` - quick long-line histogrammer.

**Remaining known work when this memory was written:**
- qlty check: 1 blocking issue (details not retrievable without login;
  check the `qlty check` PR check).
- Codacy: status unknown after latest push - re-query dashboard.
- 22 lines > 99 chars still exist, but all are either string literal
  URLs, single-token identifiers, or wrapped docstrings that cannot
  split naturally. Consider a SonarCloud-aligned threshold (100) on
  those; or accept if DS / qlty stop firing.
- DeepSource JavaScript analyzer crashing intermittently during CI —
  `DeepSource Visible Zero` gate fails with "JavaScript GitHub status
  is failure" even though dashboard shows 0 issues. May self-resolve
  on retry.
