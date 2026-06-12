# Repository Knowledge Design

Status: Current map

Last Updated: 2026-06-12

ScholarAIO is an agent-first research infrastructure. Its published repository
knowledge is organized for progressive disclosure: entry docs give agents a map,
and the public `docs/` tree carries user-facing and durable design material.

This layout is inspired by OpenAI's harness-engineering guidance that
`AGENTS.md` should behave like a table of contents rather than a monolithic
manual: https://openai.com/index/harness-engineering/

## Principles

- `AGENTS.md`, `CLAUDE.md`, and other wrappers stay short and point inward.
- Durable facts live in versioned Markdown near the code they govern.
- Multi-step procedures live in skills, not in entry docs.
- Plans, validation records, and audits are local maintenance artifacts, not
  published documentation.
- Generated references must say how they were generated and when to refresh them.
- Agent-facing docs should be easy to index, grep, validate, and garbage collect.

## Directory Roles

| Path | Role |
|------|------|
| `docs/index.md` | Public documentation home |
| `docs/getting-started/` | User setup and upgrade paths |
| `docs/guide/` | User-facing workflow references |
| `docs/writing-guide/` | Writing and diagram authoring guides |
| `docs/api/` | Python API documentation |
| `docs/design-docs/` | Long-lived architecture and runtime design decisions |
| `docs/product-specs/` | Product behavior and workflow specifications |
| `docs/generated/` | Generated facts such as schema or CLI snapshots |
| `docs/superpowers/` | Local planning artifacts created by superpowers workflows |
| `docs/archive/` and `docs/internal/` | Historical or local-only notes excluded from published docs |

## Reading Order

1. Start with `AGENTS.md` for hard constraints and navigation.
2. Use this file for the repository knowledge map.
3. Use `docs/guide/agent-reference.md` for agent runtime and skill details.
4. Use the relevant design doc, product spec, generated reference, or guide
   before changing a governed area.
5. Use source code and tests as the final authority for current behavior.

## Maintenance Rules

- When adding a durable design decision, put it under `docs/design-docs/` and
  link it from `docs/design-docs/index.md`.
- Keep plans, validation evidence, and audits under `docs/internal/`, which is
  excluded from the published MkDocs site.
- When internal work discovers reusable policy or product behavior, promote only
  the stable public fact into `docs/design-docs/`, `docs/product-specs/`, or a
  project skill.
- When a reference is generated, put it under `docs/generated/` and document the
  generating command in the file header.
- Do not use a single root wrapper as the long-term home for checklists,
  examples, or operational runbooks.
