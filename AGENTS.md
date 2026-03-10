# AGENTS.md

## Operating Model

This repository uses shared `quality-zero-platform` wrapper workflows for strict-zero quality automation.
Keep changes evidence-backed, small, and task-focused.

## Canonical Verification Command

Run this command before claiming completion:

```bash
bash scripts/verify
```

## Scope Guardrails

- Keep the aggregate gate PR-focused while legacy per-tool workflows remain active.
- Do not commit secrets or local runtime artifacts.
- Preserve existing public check names unless the platform rollout explicitly replaces them.
- Treat missing external statuses as policy drift before code changes.