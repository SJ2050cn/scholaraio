# Design Docs

Status: Current index

Last Updated: 2026-07-14

Design docs are long-lived architecture and runtime decisions. They answer what
must stay true, not just what one implementation plan happened to do.

## Current Authorities

| Document | Scope |
|----------|-------|
| `directory-structure-spec.md` | Current runtime directory layout and path ownership |
| `migration-mechanism-spec.md` | Migration control-plane contract, journal, locking, and cleanup gates |
| `directory-migration-sequence.md` | Historical compatibility-window execution order |
| `user-data-migration-strategy.md` | Historical user-data migration strategy and posture |
| `wsl-pdf-edit-mirror.md` | Stable Windows PDF edit mirrors, automatic reconciliation, and recovery contract |

## Rules

- Put durable architecture decisions here.
- Keep execution checklists and validation evidence in internal maintenance docs,
  not in the published design-doc surface.
- Link new design docs from this index before treating them as authority.
