# Specs

This directory is the project's persistent context for **non-trivial** work — the substitute for team memory in a project worked on by one human developer plus multiple AI sessions/agents that don't share memory with each other. A spec exists so the next session (human or AI) can understand *why* something is built the way it is without re-deriving it from the code, or worse, from a stale assumption.

`.agents/AGENTS.md` is the **constitution** — durable principles, tech stack, and architectural rules that apply everywhere. It doesn't move here. `specs/` is for the *why* and *how* behind specific, scoped pieces of work.

## Layout

```
specs/<initiative-slug>/
  spec.md    # WHAT and WHY: requirements, constraints, decisions made and rejected
  plan.md    # HOW: technical approach, file-level changes, verification steps
  tasks.md   # optional: an actionable checklist, for anything large enough to benefit from one
```

## When to write one

Write a spec for anything that changes architecture, adds a new integration pattern, or makes a decision a future session would otherwise have to re-investigate (e.g. "why is this scraper a search-grid spider when every other store uses a static manifest?"). Don't write one for a bugfix, a config tweak, or anything that doesn't outlive the PR that made it.

## The one rule that matters

**A stale spec is worse than no spec** — it actively misleads instead of just failing to help. This project already paid that cost once: `README.md`, `.agents/AGENTS.md`, and `TESTING.md` all drifted out of sync with the SQLite→PostgreSQL migration and sat wrong for a while before getting fixed. The fix isn't a ritual (write spec → get approval → then code); it's discipline: **whatever change makes a spec inaccurate updates that spec in the same change**, not as a follow-up.

## Relationship to `.gemini/`

`.gemini/.artifacts/` and `.gemini/.promtps/` predate this convention and are **historical, not authoritative** — useful for archaeology ("why did we decide this originally"), but not maintained going forward. `specs/` is the current source of truth; where a `specs/` doc and a `.gemini/` doc disagree, `specs/` wins.

## Current specs

| Spec | Status |
|---|---|
| [`system/`](system/spec.md) | Living — overall architecture |
| [`data-contract/`](data-contract/spec.md) | Living — Pydantic contracts + DB schema |
| [`pichau-scraper/`](pichau-scraper/spec.md) | Verified against the live site — first store using search-grid discovery instead of a static manifest; disabled pending review |
| [`target-urls-table/`](target-urls-table/spec.md) | Done — replaced `data/target_urls.json` with a real DB table |
| [`kabum-scraper/`](kabum-scraper/spec.md) | Living — documents the existing, already-enabled scraper |
| [`terabyte-scraper/`](terabyte-scraper/spec.md) | Living — documents the existing, already-enabled scraper |
| [`amazon-scraper/`](amazon-scraper/spec.md) | Living — documents the active HTML scraper and the dormant SP-API path |
