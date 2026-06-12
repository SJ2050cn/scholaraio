# Repository Knowledge Quality

Status: Current scorecard

Last Updated: 2026-06-12

This scorecard tracks whether ScholarAIO's repository knowledge is legible to
agents and maintainers.

| Area | Current grade | Evidence | Next pressure point |
|------|---------------|----------|---------------------|
| Entry docs | A- | `AGENTS.md` and wrappers stay short and link inward | Keep wrapper line counts enforced |
| Knowledge map | B+ | `docs/DESIGN.md` and per-directory indexes exist | Add generated reference refresh checks |
| Runtime layout docs | A- | Design, migration, validation, and upgrade docs are separated | Keep tests aligned with new paths |
| Plans | B | Active and completed plans are separated | Move stale active plans after implementation |
| Validation evidence | B+ | Matrix and reports live under `docs/internal/validation/` | Add freshness metadata checks |
| Generated references | C | Directory exists with rules | Add first generated CLI/schema snapshots |

## Mechanical Checks

- `tests/test_agent_entry_docs.py` checks wrapper lightness and knowledge-map links.
- `tests/test_repository_layout.py` protects runtime-layout documentation
  invariants and canonical implementation pointers.
- `python -m mkdocs build --strict` checks the published documentation build.

## Garbage Collection Rules

- If an entry doc grows into a procedure, move that procedure into a skill.
- If a plan becomes the source of truth for a stable decision, promote the
  decision into a design doc or product spec.
- If a validation report is superseded, keep the report but update
  `docs/internal/validation/index.md` so agents can see which evidence is current.
- If a generated file cannot be refreshed, either fix the generation command or
  move it out of `docs/generated/`.
