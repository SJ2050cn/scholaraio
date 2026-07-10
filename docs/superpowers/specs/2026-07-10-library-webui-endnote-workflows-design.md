# Library WebUI EndNote-Style Workflows Design

**Issue:** [#114](https://github.com/ZimoLiao/scholaraio/issues/114)

**Status:** Approved requirements baseline

## Goal

Turn the existing local library inspector into a dependable daily reference-management surface without changing library metadata. Users must be able to copy canonical BibTeX, open several PDFs in native viewers, combine precise metadata filters, and run transparent keyword, semantic, or unified retrieval from the WebUI.

## Product Principles

- Keep the current fast, local, dependency-light WebUI and its inline PDF reader.
- Reuse canonical Python services; JavaScript must not recreate BibTeX or retrieval behavior.
- Make expensive or degraded search behavior explicit. The UI must never label keyword-only results as semantic results.
- Treat opening a desktop application as privileged even though the library itself remains read-only.
- Preserve stable paper IDs from list to search result, detail, BibTeX, PDF preview, and native PDF launch.
- Keep the packaged UI self-contained: no remote scripts, fonts, analytics, or CDNs.

## Approaches Considered

### 1. Service-backed local WebUI (selected)

Add small HTTP adapters over canonical service functions and keep the browser responsible only for interaction state, display, clipboard access, and local metadata filtering. This fits the existing architecture, enables direct unit and integration tests, and gives native launch a narrow security boundary.

### 2. Browser-only enhancement

Generating BibTeX and emulating unified search in JavaScript would be initially quick, but it would duplicate canonical behavior, drift from the CLI, and cannot securely launch the OS viewer. This approach is rejected.

### 3. Replace the server with a full web framework

A framework could provide routing and request helpers, but it would add a new runtime dependency and force an unrelated rewrite of the intentionally small local server. The required surface is small enough to keep the standard-library server while extracting focused services. This approach is rejected.

## Architecture

```text
Packaged HTML/CSS/JS
        |
        | stable paper ID + structured request
        v
interfaces/cli/gui.py
  - HTTP parsing and response contracts
  - security headers, CSRF, same-origin, loopback policy
        |
        +--> services/library_view.py
        |      canonical metadata/PDF lookup + BibTeX adapter
        |
        +--> services/library_search.py
        |      filter validation + ranked retrieval orchestration
        |             |--> services/index.py (keyword/unified)
        |             `--> services/vectors.py (semantic)
        |
        `--> services/system_open.py
               Windows/macOS/Linux default-application adapter
```

The UI never sends a filesystem path. Every paper action starts with a source (`main` or `proceedings`) and a stable paper ID. `library_view` resolves that ID against configured library roots before another service can act.

## Service Boundaries

### Canonical record actions

`scholaraio.services.library_view` gains source-specific BibTeX functions alongside its existing detail/PDF functions:

- `get_main_paper_bibtex(cfg, paper_id)`
- `get_proceedings_paper_bibtex(cfg, paper_id)`

They resolve the full canonical metadata and delegate formatting to `scholaraio.services.export.meta_to_bibtex`. Proceedings metadata may be enriched with non-destructive volume context only when the child record lacks that field. Malformed or missing records preserve the existing `KeyError`/controlled-error behavior.

### Native viewer adapter

`scholaraio.services.system_open.open_with_default_application(path)` accepts an already resolved `Path` and dispatches without a shell:

- Windows: `os.startfile`
- macOS: `open <path>`
- Linux/other desktop Unix: `xdg-open <path>`

The adapter checks that the path is an existing file, uses argument arrays instead of shell strings, detaches subprocess-based launchers, and turns missing launchers or OS failures into a focused `DefaultApplicationOpenError`. Tests inject or mock launch primitives and never start a real application.

### Search orchestration

`scholaraio.services.library_search` owns WebUI search contracts. It validates mode, query, limit, and years; constructs a canonical candidate-ID set from field filters; then calls existing services directly:

- `keyword` -> `services.index.search`
- `semantic` -> `services.vectors.vsearch`
- `unified` -> `services.index.unified_search`

Accepted structured filters are title, author, start/end year, journal/source, paper type, and DOI. Title, author, and DOI narrow the candidate-ID set before ranked retrieval. Year, journal, and paper type are also passed through to the canonical retrieval service. Retrieval must return enough candidates to remain correct after filtering rather than silently dropping qualifying lower-ranked results.

Every result contains `paper_id`, `rank`, `score`, and `match`, plus display metadata when available. Every response contains diagnostics:

```json
{
  "mode": "unified",
  "query": "turbulent combustion",
  "total": 12,
  "results": [
    {"paper_id": "...", "rank": 1, "score": 0.0328, "match": "both"}
  ],
  "diagnostics": {
    "status": "ok",
    "message": "Keyword and semantic retrieval are active.",
    "keyword": "available",
    "semantic": "available",
    "actions": []
  }
}
```

Diagnostic status is `ok`, `degraded`, or `unavailable`. Degradation includes a safe summary and actionable commands such as `scholaraio index --rebuild` or `scholaraio embed`; raw tracebacks are not exposed. Unified search may return keyword-only results with `degraded`, but semantic mode never substitutes keyword results. If both unified legs are unavailable, the response is explicitly unavailable.

Main-library ranked retrieval is required. Proceedings keeps full metadata filtering but exposes ranked modes as unavailable with an explanatory message until a compatible proceedings vector index exists.

## HTTP API

### Capabilities

`GET /api/capabilities` returns:

- whether native PDF launch is enabled;
- the reason when it is disabled;
- a per-server CSRF token for same-origin action requests; and
- supported search modes by source.

The token is random for every server process and is not persisted.

### BibTeX

- `GET /api/main/bibtex?id=<paper-id>`
- `GET /api/proceedings/bibtex?id=<paper-id>`

Success returns `{ "paper_id": "...", "bibtex": "..." }`. Unknown IDs return 404 and malformed requests return 400.

### Ranked search

`GET /api/main/search` accepts `mode`, `q`, `title`, `author`, `year_from`, `year_to`, `journal`, `paper_type`, `doi`, and `limit`. Modes are restricted to `keyword`, `semantic`, and `unified`; the local `metadata` mode does not require a server round trip. Limits are bounded server-side. Invalid ranges or modes return 400 with a stable error code. Missing derived indexes return a successful structured search envelope with `unavailable` diagnostics so the UI can present recovery actions without losing state.

### Native PDF launch

- `POST /api/main/open-pdf`
- `POST /api/proceedings/open-pdf`

The JSON body contains only `{ "id": "<paper-id>" }`. A valid request must:

1. target a server bound to a loopback address;
2. have an HTTP `Origin` whose hostname is loopback and whose port matches the server;
3. include `X-ScholarAIO-CSRF` matching the per-process token;
4. use `application/json` within a small body-size limit; and
5. resolve the ID through `library_view` before launching.

Failures use 400 for malformed input, 403 for policy/CSRF/origin rejection, 404 for missing paper/PDF, and 500 for a controlled desktop-launch failure. The endpoint never accepts a path.

All responses add a restrictive Content Security Policy, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and frame protections. No CORS headers are emitted.

## WebUI Experience

### Search and filters

The filter card becomes a compact search workspace:

- mode selector: Metadata, Keyword, Semantic, Unified;
- primary query input and explicit Search action for ranked modes;
- field inputs for title, author, year from/to, journal/source, DOI, type, and proceedings volume;
- existing audit-issue and missing-Markdown toggles;
- one `Clear all` action;
- active-filter/result count and a debounced metadata-mode update;
- a diagnostic region with `aria-live` that shows loading, result, degraded, and recovery states.

Metadata mode filters the already loaded list immediately. Ranked modes call the server, filter the visible rows by returned stable IDs, and default to relevance order. Rank, retrieval leg (`keyword`, `semantic`, or `both`), and score are visible without replacing existing status information. Users can still choose a column sort; clearing or changing mode restores the normal sort.

Switching to Proceedings automatically uses Metadata mode and explains why ranked search is not available. Switching sources keeps meaningful common filters but clears source-specific volume and stale ranking state.

### Selected-record actions

The inspector gains a persistent action row for the selected record:

- `Copy BibTeX`
- `Preview PDF`
- `Open in default viewer`

PDF actions are disabled with a useful tooltip when no PDF exists. Native open is disabled when capabilities report a non-loopback binding. Actions show busy state, prevent duplicate clicks, and report success/failure in an accessible toast/live region.

Clipboard behavior first uses `navigator.clipboard.writeText`. If unavailable or rejected, it uses a temporary off-screen textarea plus `document.execCommand("copy")`, restores focus, and removes the temporary element. A failed fallback is reported honestly.

The existing table PDF pill and fullscreen inline preview remain available.

### Responsive and accessible behavior

- Every input has a visible label and every icon-free button has explicit text.
- Buttons and fields receive keyboard-visible focus styling.
- Status is not communicated by color alone.
- Busy buttons expose `aria-busy`; dynamic feedback uses `role="status"` or `role="alert"`.
- At narrow widths the filter, records, and inspector stack without horizontal page overflow; the table retains its own scroll region.
- Reduced-motion preferences disable nonessential transitions.

## State and Concurrency

Ranked search uses a monotonically increasing request sequence, matching existing refresh/detail stale-response protection. Only the latest response for the current source/mode may update the table. A library poll can refresh record metadata without automatically rerunning an expensive vector query every 2.2 seconds; the UI marks ranked results as ready to rerun if the underlying list changes.

Selecting a row remains stable while filters change when the selected ID is still visible. Otherwise the first visible row becomes selected. Clearing all filters cancels stale ranked responses and returns to Metadata mode.

## Error Handling

- API responses use JSON with `error`, `code`, and HTTP status for request failures.
- Search dependency/index problems use the diagnostic envelope rather than a generic 500.
- The UI preserves current rows when a ranked search fails and displays the recovery message.
- Clipboard and native-launch failures never claim success.
- Missing metadata or PDFs use the existing controlled 404 behavior.
- Server logs do not print CSRF tokens or full BibTeX payloads.

## Testing Strategy

### Unit tests

- Canonical BibTeX for main and proceedings records, including special characters and canonical metadata usage.
- Field-filter combinations, year validation, result limit bounds, stable IDs, ranking order, and all search modes.
- Keyword/vector/unified readiness and honest degradation diagnostics.
- Correct filtered retrieval when qualifying records are below an initial top-N window.
- Windows, macOS, Linux, missing-launcher, and missing-file native-open behavior with mocked launchers.

### HTTP integration tests

- BibTeX, search, capabilities, and native-open success contracts.
- Native open rejects arbitrary paths by schema, missing/wrong CSRF, missing/cross-origin Origin, non-loopback binding, oversized bodies, bad content type, missing records, and missing PDFs.
- Native-open tests assert the canonical resolved `Path` and never spawn a process.
- Existing list/detail/PDF routes and rejected unrelated write methods remain compatible.
- Security headers appear on static and API responses.

### Frontend behavior tests

Node-based DOM tests cover composable filters, clear-all, year validation, clipboard fallback, selected-record actions, capabilities, ranked result ordering/diagnostics, source limitations, and stale response rejection. Existing Markdown, math, polling, detail, and fullscreen tests remain green.

### Product verification

- Run focused service/server/frontend tests during TDD.
- Run Ruff check/format, mypy, the full pytest suite, and strict MkDocs build.
- Exercise a real local server with representative main/proceedings fixtures.
- Inspect desktop and narrow-width screenshots in a real headless browser when available.

## Documentation and Release

Create a focused `docs/guide/library-webui.md`, add it to the MkDocs navigation, update the CLI reference, and add an Unreleased changelog entry linked to #114. The guide documents search-mode semantics, index preparation, native-open security limits, keyboard/accessibility behavior, and troubleshooting commands.

## Non-Goals

- Editing, deleting, tagging, or mutating paper metadata.
- Remote/native application launch from a non-loopback server.
- Proceedings semantic retrieval before a compatible vector index exists.
- Replacing the current HTTP server or introducing a frontend build system.
- Synchronization with EndNote or a complete EndNote feature clone.

## Acceptance Mapping

| #114 criterion | Design coverage |
| --- | --- |
| Canonical one-click BibTeX | Source-specific service + GET API + inspector action + clipboard fallback |
| Inline and OS-native PDF | Existing preview retained + secured POST launch adapter |
| Safe launch | Stable-ID resolution, loopback, Origin, CSRF, JSON/size limits, mocked tests |
| Composable filters | Seven structured fields plus retained status/volume filters and clear-all |
| Vector-enhanced WebUI | Explicit four-mode selector and service-backed ranked retrieval |
| Honest diagnostics | Per-leg availability, degraded/unavailable states, recovery commands |
| Main/proceedings coverage | Shared record actions and metadata filters; explicit proceedings ranking limit |
| Docs/changelog | Dedicated guide, navigation, CLI reference, and Unreleased entry |
