# Library WebUI EndNote-Style Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver all #114 acceptance criteria as a secure, transparent, product-grade extension of the existing local library WebUI.

**Architecture:** Keep the packaged browser UI presentation-oriented. Resolve canonical records in `library_view`, orchestrate ranked modes in a focused `library_search` service, isolate OS application launch in `system_open`, and expose narrow JSON routes from the standard-library HTTP adapter. All behavior-bearing changes use test-first evidence and stable paper IDs.

**Tech Stack:** Python 3.10+, stdlib `http.server`/`sqlite3`/`subprocess`, existing FTS5 + FAISS services, plain HTML/CSS/JavaScript, pytest, Node VM browser-behavior tests, Ruff, mypy, MkDocs.

**Specification:** `docs/superpowers/specs/2026-07-10-library-webui-endnote-workflows-design.md`

---

## File Map

### Create

- `scholaraio/services/library_search.py` — validates WebUI search inputs, constructs structured-filter candidate sets, calls keyword/semantic/unified services, and returns user-safe diagnostics.
- `scholaraio/services/system_open.py` — cross-platform, shell-free default-application launcher with a focused error type.
- `tests/test_library_search.py` — service-level filter, orchestration, ranking, and degradation contracts.
- `tests/test_system_open.py` — Windows/macOS/Linux and failure-path launcher contracts.
- `docs/guide/library-webui.md` — user guide for search modes, record actions, security, and recovery.

### Modify

- `scholaraio/services/index.py` — correct candidate filtering before result limiting and expose per-leg unified diagnostics.
- `scholaraio/services/vectors.py` — preserve correctness when semantic results are post-filtered.
- `scholaraio/services/export.py` — make the canonical single-record BibTeX formatter robust to supported author/value shapes.
- `scholaraio/services/library_view.py` — source-specific canonical BibTeX accessors.
- `scholaraio/interfaces/cli/gui.py` — capabilities, BibTeX, ranked search, secured native-open routes, request parsing, and response security headers.
- `scholaraio/interfaces/cli/library-view/index.html` — structured search controls, selected-record actions, diagnostics, and accessible feedback.
- `scholaraio/interfaces/cli/library-view/app.js` — filter/ranking state, API actions, clipboard fallback, diagnostics, and stale-request protection.
- `scholaraio/interfaces/cli/library-view/styles.css` — polished responsive controls, result diagnostics, action states, focus, toast, and reduced motion.
- `tests/test_index.py` — FTS candidate/diagnostics regressions.
- `tests/test_vectors.py` — semantic post-filter correctness regression.
- `tests/test_export.py` — canonical BibTeX robustness.
- `tests/test_library_view.py` — main/proceedings BibTeX accessors.
- `tests/test_gui_server.py` — HTTP security/contracts and Node-based WebUI behavior.
- `pyproject.toml` — package-data coverage only if the final static asset set grows beyond the existing wildcard.
- `mkdocs.yml`, `docs/guide/cli-reference.md`, `docs/index.md`, `CHANGELOG.md` — discoverability and release notes.

## U1: Make Canonical Ranked Retrieval Filter-Correct and Transparent

**Depends on:** none

**Files:**

- Modify: `tests/test_index.py`
- Modify: `tests/test_vectors.py`
- Modify: `scholaraio/services/index.py`
- Modify: `scholaraio/services/vectors.py`

**Execution note:** Proof-first. Use real SQLite FTS rows for keyword behavior. Keep FAISS/model seams mocked only at the optional dependency boundary.

- [ ] **Step 1: Add a failing FTS candidate-filter regression**

Add a test that indexes more than five times `top_k` matching papers, whitelists a paper that ranks below that old over-fetch window, and asserts `search(..., top_k=1, paper_ids={target_id})` returns that target. This proves candidate filtering occurs in SQL before `LIMIT`.

- [ ] **Step 2: Verify the FTS regression fails for the old post-filter behavior**

Run:

```bash
python -m pytest tests/test_index.py::TestBuildAndSearch::test_search_applies_paper_ids_before_limit -q -p no:cacheprovider
```

Expected: FAIL because the old implementation fetches only `top_k * 5` rows before applying `paper_ids`.

- [ ] **Step 3: Add a failing semantic post-filter regression**

Create deterministic fake FAISS scores/IDs where the only candidate matching a year or ID filter is below the first `top_k * 5` results. Assert `vsearch(..., top_k=1, paper_ids={target_id})` returns the target and does not load a real embedding model or native FAISS library.

- [ ] **Step 4: Verify the semantic regression fails for the old fetch window**

Run:

```bash
python -m pytest tests/test_vectors.py::test_vsearch_applies_filters_before_result_limit -q -p no:cacheprovider
```

Expected: FAIL with an empty result or the wrong paper ID.

- [ ] **Step 5: Add a failing per-leg diagnostics contract**

Strengthen the existing unified diagnostics test to require:

```python
assert diagnostics["keyword_degraded"] is False
assert diagnostics["vector_degraded"] is True
assert diagnostics["keyword_error"] == ""
assert diagnostics["vector_error"]
```

Add the inverse case for an unavailable keyword leg with a working vector leg, and a both-unavailable case.

- [ ] **Step 6: Verify diagnostics fail because only `vector_degraded` exists**

Run:

```bash
python -m pytest tests/test_index.py -q -p no:cacheprovider
```

Expected: FAIL on missing per-leg diagnostic keys.

- [ ] **Step 7: Implement pre-limit candidate filtering and per-leg diagnostics**

In `index.py`:

- extend `UnifiedSearchDiagnostics` with `keyword_degraded`, `keyword_error`, and `vector_error`;
- install a connection-local temporary allowed-ID table when `paper_ids` is supplied;
- constrain the FTS query with `EXISTS` against that table before `ORDER BY rank LIMIT ?`;
- remove the heuristic `top_k * 5` post-filter dependency while retaining the final defensive Python filter;
- catch expected missing-index/SQLite failures independently for each unified leg and record a safe message.

In `vectors.py`, request enough FAISS neighbors to apply structured/ID filters correctly before slicing to `top_k`. Do not change score ordering.

- [ ] **Step 8: Run focused retrieval tests green**

Run:

```bash
python -m pytest tests/test_index.py tests/test_vectors.py -q -p no:cacheprovider
```

Expected: PASS with all new and existing retrieval contracts.

- [ ] **Step 9: Commit the retrieval foundation**

```bash
git add scholaraio/services/index.py scholaraio/services/vectors.py tests/test_index.py tests/test_vectors.py
git commit -m "fix(search): preserve ranked filters and diagnostics"
```

## U2: Add WebUI Search Orchestration

**Depends on:** U1

**Files:**

- Create: `tests/test_library_search.py`
- Create: `scholaraio/services/library_search.py`

**Execution note:** Proof-first. Cover validation, filter composition, each mode, and dependency degradation before implementation.

- [ ] **Step 1: Write failing filter and validation tests**

Define the desired public API in tests:

```python
filters = LibrarySearchFilters(
    title="turbulence",
    author="doe",
    year_from=2020,
    year_to=2026,
    journal="fluid",
    paper_type="journal-article",
    doi="10.1000/",
)
response = search_main_library(cfg, query="closure", mode="keyword", filters=filters, limit=50)
```

Assert filters combine with AND semantics, comparisons are case-insensitive, both metadata IDs and directory names resolve consistently, invalid years/ranges/modes/blank ranked queries raise `LibrarySearchRequestError`, and limits are clamped to the documented maximum.

- [ ] **Step 2: Verify imports fail before the service exists**

Run:

```bash
python -m pytest tests/test_library_search.py -q -p no:cacheprovider
```

Expected: collection ERROR because `scholaraio.services.library_search` does not exist.

- [ ] **Step 3: Add failing mode and diagnostics tests**

Monkeypatch only `index.search`, `vectors.vsearch`, and `index.unified_search` to capture arguments. Assert:

- keyword, semantic, and unified call the correct service directly, never a CLI subprocess;
- the structured candidate-ID whitelist and year/journal/type values are passed through;
- results expose stable `paper_id`, one-based `rank`, numeric `score`, and `match`;
- semantic unavailability produces `status=unavailable` plus `scholaraio embed`;
- unified vector degradation keeps keyword results with `status=degraded` plus `scholaraio embed`;
- missing keyword and vectors produce both rebuild commands without a generic 500.

- [ ] **Step 4: Implement the focused search service**

Create:

```python
@dataclass(frozen=True)
class LibrarySearchFilters:
    title: str = ""
    author: str = ""
    year_from: int | None = None
    year_to: int | None = None
    journal: str = ""
    paper_type: str = ""
    doi: str = ""

class LibrarySearchRequestError(ValueError):
    code: str

def search_main_library(
    cfg: Config,
    *,
    query: str,
    mode: str,
    filters: LibrarySearchFilters | None = None,
    limit: int = 100,
) -> dict: ...
```

Scan canonical metadata without invoking the audit cache, build the allowed ID set, call the canonical retrieval service, normalize results, and construct safe diagnostics/actions. Return no raw traceback or local secret.

- [ ] **Step 5: Add a real build-index integration test**

Build a real FTS index from fixture papers, then call `search_main_library` with a title/author/year filter and assert the service returns the same stable ID that `library_view` exposes. This proves the service boundary, SQLite index, and metadata whitelist work together without mocks.

- [ ] **Step 6: Run the service tests green**

```bash
python -m pytest tests/test_library_search.py tests/test_index.py tests/test_vectors.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Commit search orchestration**

```bash
git add scholaraio/services/library_search.py tests/test_library_search.py
git commit -m "feat(gui): add ranked library search orchestration"
```

## U3: Add Canonical Per-Record BibTeX

**Depends on:** none

**Files:**

- Modify: `tests/test_export.py`
- Modify: `tests/test_library_view.py`
- Modify: `scholaraio/services/export.py`
- Modify: `scholaraio/services/library_view.py`

**Execution note:** Proof-first. Strengthen the canonical formatter only where real supported metadata shapes require it.

- [ ] **Step 1: Write failing formatter robustness tests**

Add focused cases for author lists and an already-normalized author string, numeric volume/issue/pages, BibTeX-sensitive title characters, and a record with only the minimum title/year fields. Assert complete entries, stable cite keys, and no character-by-character author joining.

- [ ] **Step 2: Verify the string-author/numeric-value cases fail**

```bash
python -m pytest tests/test_export.py -q -p no:cacheprovider
```

Expected: FAIL on current `" and ".join(str)` and/or non-string field handling.

- [ ] **Step 3: Add failing main/proceedings accessor tests**

Use real fixture directories and assert:

```python
bibtex = get_main_paper_bibtex(cfg, "paper-id")
assert "@article{" in bibtex
assert "doi = {10.1000/example}" in bibtex
```

Repeat for a proceedings child, requiring `@inproceedings` and canonical child metadata. Unknown IDs must raise `KeyError`.

- [ ] **Step 4: Verify the accessors do not exist**

```bash
python -m pytest tests/test_library_view.py -q -p no:cacheprovider
```

Expected: collection/import failure or missing-attribute failure for the new functions.

- [ ] **Step 5: Implement robust canonical formatting and accessors**

Normalize supported author shapes and stringify scalar BibTeX values in `meta_to_bibtex` without changing the emitted field set. In `library_view`, resolve the canonical metadata with `_find_main_paper` / `_find_proceedings_row`, enrich missing proceedings type/context conservatively, and delegate to `meta_to_bibtex`.

- [ ] **Step 6: Run export and view tests green**

```bash
python -m pytest tests/test_export.py tests/test_export_extended.py tests/test_library_view.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Commit BibTeX support**

```bash
git add scholaraio/services/export.py scholaraio/services/library_view.py tests/test_export.py tests/test_library_view.py
git commit -m "feat(gui): expose canonical per-record BibTeX"
```

## U4: Add the Cross-Platform Native Viewer Adapter

**Depends on:** none

**Files:**

- Create: `tests/test_system_open.py`
- Create: `scholaraio/services/system_open.py`

**Execution note:** Proof-first. No test may spawn a real application.

- [ ] **Step 1: Write failing platform contract tests**

Use injected/mocked `platform.system`, `os.startfile`, `shutil.which`, and `subprocess.Popen`. Assert:

- Windows passes the exact resolved file to `os.startfile`;
- macOS invokes `["open", str(path)]`;
- Linux invokes `["xdg-open", str(path)]`;
- subprocess launch uses no shell and detaches stdio/session;
- a missing file, missing executable, or launch `OSError` raises `DefaultApplicationOpenError` with a safe message.

- [ ] **Step 2: Verify the module is missing**

```bash
python -m pytest tests/test_system_open.py -q -p no:cacheprovider
```

Expected: collection ERROR because the module does not exist.

- [ ] **Step 3: Implement the adapter**

Create:

```python
class DefaultApplicationOpenError(RuntimeError):
    pass

def open_with_default_application(path: Path) -> None: ...
```

Reject non-files before platform dispatch, never use `shell=True`, locate Unix launchers explicitly, and wrap only expected OS/launcher failures.

- [ ] **Step 4: Run adapter tests green**

```bash
python -m pytest tests/test_system_open.py -q -p no:cacheprovider
```

Expected: PASS with zero real process launches.

- [ ] **Step 5: Commit the adapter**

```bash
git add scholaraio/services/system_open.py tests/test_system_open.py
git commit -m "feat(gui): add native PDF viewer adapter"
```

## U5: Expose Secure Product APIs

**Depends on:** U2, U3, U4

**Files:**

- Modify: `tests/test_gui_server.py`
- Modify: `scholaraio/interfaces/cli/gui.py`

**Execution note:** Proof-first HTTP integration. Exercise a real `ThreadingHTTPServer`; mock only the final OS launch function.

- [ ] **Step 1: Add failing capabilities/BibTeX/search endpoint tests**

Start a real loopback server and assert:

- `/api/capabilities` returns a nonempty CSRF token, native launch enabled, main modes, and proceedings limitation;
- `/api/main/bibtex` and `/api/proceedings/bibtex` return canonical complete entries;
- `/api/main/search` passes structured fields and returns ranks/diagnostics;
- missing IDs, invalid modes, invalid years, and excessive limits use stable JSON error codes or bounded values;
- static and API responses include CSP, `nosniff`, no-referrer, and frame protection.

- [ ] **Step 2: Verify the new GET routes fail with 404**

```bash
python -m pytest tests/test_gui_server.py -k "capabilities or bibtex or ranked_search or security_headers" -q -p no:cacheprovider
```

Expected: FAIL because routes and headers do not exist.

- [ ] **Step 3: Add failing native-open security matrix**

For `POST /api/main/open-pdf` and proceedings, cover:

- valid loopback Origin + correct token + canonical ID calls the mocked launcher with the resolved PDF path;
- missing/wrong token, missing/cross-origin Origin, and a non-loopback-bound handler return 403;
- `path` or extra JSON keys, malformed JSON, wrong content type, and oversized bodies return 400/413;
- unknown paper/PDF returns 404;
- launcher failure returns a controlled 500;
- PUT/PATCH/DELETE and unknown POST routes remain 405 and close the connection.

- [ ] **Step 4: Verify valid POST is still rejected and security cases fail**

```bash
python -m pytest tests/test_gui_server.py -k "open_pdf or rejected_write" -q -p no:cacheprovider
```

Expected: FAIL because all POST requests currently return 405.

- [ ] **Step 5: Implement HTTP parsing, routes, and security policy**

Add focused helpers for:

- loopback host/origin validation using `ipaddress` and parsed ports;
- constant-time token comparison using `secrets.compare_digest`;
- bounded JSON-body parsing with exact-key validation;
- stable JSON errors containing `error`, `code`, and `status`;
- shared response security headers;
- capabilities, BibTeX, ranked search, and source-specific native-open routing.

Generate one `secrets.token_urlsafe` token per server. Set native launch capability from the configured bind host, not the browser-provided request. Resolve IDs via `library_view` before calling `system_open`.

- [ ] **Step 6: Run the complete server/view/action test set**

```bash
python -m pytest tests/test_gui_server.py tests/test_library_view.py tests/test_library_search.py tests/test_system_open.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Commit the API surface**

```bash
git add scholaraio/interfaces/cli/gui.py tests/test_gui_server.py
git commit -m "feat(gui): add secure library action and search APIs"
```

## U6: Build the Product-Grade WebUI Experience

**Depends on:** U5

**Files:**

- Modify: `tests/test_gui_server.py`
- Modify: `scholaraio/interfaces/cli/library-view/index.html`
- Modify: `scholaraio/interfaces/cli/library-view/app.js`
- Modify: `scholaraio/interfaces/cli/library-view/styles.css`

**Execution note:** Test behavior first with the existing Node VM seam. Pure styling follows behavior and is verified through static assertions plus real-browser inspection.

- [ ] **Step 1: Add failing shell/accessibility assertions**

Assert the served HTML contains labeled mode/query/title/author/year/journal/DOI/type controls, Clear all, selected-record actions, an `aria-live` diagnostic region, and a toast/status region, while still containing the existing PDF frame/fullscreen controls and no remote URLs/scripts.

- [ ] **Step 2: Verify markup assertions fail**

```bash
python -m pytest tests/test_gui_server.py -k "shell or accessibility" -q -p no:cacheprovider
```

Expected: FAIL on missing controls/actions/status regions.

- [ ] **Step 3: Add failing composable-filter and clear-all Node tests**

Exercise `rowMatches` with simultaneous title, author, year-from/to, journal/source, DOI, type, volume, issues, and missing-Markdown state. Assert every filter is AND-composed, year bounds are inclusive, proceedings source matches volume/source metadata, and `clearAllFilters()` restores empty controls, Metadata mode, relevance state, and the normal sort.

- [ ] **Step 4: Verify filter behavior fails before implementation**

```bash
python -m pytest tests/test_gui_server.py -k "structured_filters or clear_all" -q -p no:cacheprovider
```

Expected: FAIL on missing filter state/functions.

- [ ] **Step 5: Add failing ranked-search state tests**

With controlled fetch promises, assert:

- ranked modes issue encoded server requests with all structured filters;
- only returned stable IDs are visible, in server rank order by default;
- match/score/rank are rendered;
- switching to a column sort is deterministic;
- stale search responses cannot overwrite a newer mode/query/tab;
- degraded/unavailable messages and recovery commands are visible;
- Proceedings forces Metadata mode with an honest limitation;
- polling metadata does not automatically rerun semantic/unified search.

- [ ] **Step 6: Verify ranked behavior fails before implementation**

```bash
python -m pytest tests/test_gui_server.py -k "ranked_search or stale_search or proceedings_search" -q -p no:cacheprovider
```

Expected: FAIL on missing ranked-search state/actions.

- [ ] **Step 7: Add failing BibTeX/clipboard/native-open Node tests**

Cover:

- clipboard API success;
- missing/rejected clipboard API falls back to a temporary textarea and `execCommand("copy")`;
- fallback failure reports failure and cleans up the textarea;
- BibTeX is fetched server-side for the selected source/ID;
- native open sends JSON, Origin-managed same-origin fetch, and `X-ScholarAIO-CSRF`;
- missing PDF and non-loopback capability disable actions with explanations;
- busy state blocks duplicate actions and success/failure reaches the live region.

- [ ] **Step 8: Verify action tests fail before implementation**

```bash
python -m pytest tests/test_gui_server.py -k "bibtex_copy or clipboard_fallback or native_open_action" -q -p no:cacheprovider
```

Expected: FAIL on missing actions/fallback/capability state.

- [ ] **Step 9: Implement semantic markup and state-driven behavior**

Update HTML with a compact search/filter card, diagnostics, selected-record action row, and toast. Update JavaScript to:

- extend filter state and element bindings;
- validate year ranges and derive query parameters;
- fetch capabilities once per server session;
- maintain ranked result maps/order and search request sequence;
- preserve explicit user sort and existing list/detail stale guards;
- implement `copyText`, `copySelectedBibtex`, `previewSelectedPdf`, and `openSelectedPdfNative`;
- provide reusable busy/feedback helpers;
- keep existing inline PDF and Markdown/math behavior unchanged.

- [ ] **Step 10: Implement responsive, accessible visual polish**

Add grouped field grids, mode segmented controls/select styling, primary/secondary action hierarchy, result badges, diagnostic states, toast, disabled/busy states, `:focus-visible`, narrow-width stacking, table overflow containment, and `prefers-reduced-motion`. Preserve `[hidden] { display: none !important; }`.

- [ ] **Step 11: Run every frontend/server regression green**

```bash
python -m pytest tests/test_gui_server.py -q -p no:cacheprovider
```

Expected: PASS, including all pre-existing Markdown/math/polling/PDF tests.

- [ ] **Step 12: Commit the WebUI**

```bash
git add scholaraio/interfaces/cli/library-view/index.html scholaraio/interfaces/cli/library-view/app.js scholaraio/interfaces/cli/library-view/styles.css tests/test_gui_server.py
git commit -m "feat(gui): deliver EndNote-style library workflows"
```

## U7: Document and Announce the Product Surface

**Depends on:** U6

**Files:**

- Create: `docs/guide/library-webui.md`
- Modify: `mkdocs.yml`
- Modify: `docs/guide/cli-reference.md`
- Modify: `docs/index.md`
- Modify: `CHANGELOG.md`

**Execution note:** Documentation-only; replacement verification is strict MkDocs build plus command smoke output.

- [ ] **Step 1: Write the focused user guide**

Document:

- launching `scholaraio gui` and the loopback security model;
- Metadata/Keyword/Semantic/Unified semantics;
- preparation/recovery commands (`scholaraio index --rebuild`, `scholaraio embed`);
- structured filters and relevance/column sorting;
- BibTeX clipboard fallback and native/inline PDF behavior;
- proceedings ranked-search limitation;
- troubleshooting and privacy guarantees.

- [ ] **Step 2: Link the guide and update current behavior summaries**

Add Library WebUI to MkDocs User Guide navigation, link it from `docs/index.md`, replace the old one-sentence GUI description in CLI reference, and add an Unreleased Added entry linked to #114.

- [ ] **Step 3: Build docs strictly**

```bash
python -m mkdocs build --strict
```

Expected: success with no missing links or nav warnings.

- [ ] **Step 4: Smoke the CLI help**

```bash
python -m scholaraio.cli gui --help
```

Expected: exit 0 and current host/port/no-open options.

- [ ] **Step 5: Commit docs**

```bash
git add docs/guide/library-webui.md mkdocs.yml docs/guide/cli-reference.md docs/index.md CHANGELOG.md
git commit -m "docs(gui): document advanced library workflows"
```

## U8: Product Verification, Review, and Shipping

**Depends on:** U1-U7

**Files:** all changed files

**Execution note:** Do not claim completion from partial tests. Capture fresh full-suite and real-runtime evidence.

- [ ] **Step 1: Review and simplify the complete diff**

Run a focused simplification pass over files changed since `origin/main`: remove duplicated filter/feedback code, confirm module boundaries, check error messages, and preserve behavior. Re-run focused tests after any edit.

- [ ] **Step 2: Run static quality gates**

```bash
python -m ruff check scholaraio tests
python -m ruff format --check scholaraio tests
python -m mypy scholaraio
git diff --check origin/main...HEAD
```

Expected: all exit 0.

- [ ] **Step 3: Run full automated verification**

```bash
python -m pytest -q -p no:cacheprovider
python -m mkdocs build --strict
```

Expected: all tests pass; docs build succeeds.

- [ ] **Step 4: Run a real local-server smoke fixture**

Create temporary configured main/proceedings fixtures outside tracked runtime data, build a real keyword index, start the server on an ephemeral loopback port, and verify with HTTP requests:

- capabilities;
- list/detail;
- canonical BibTeX;
- structured keyword and degraded unified search;
- inline PDF bytes;
- native-open policy using a patched launcher only.

Expected: every route returns its documented contract and no library file changes.

- [ ] **Step 5: Perform real-browser desktop/mobile QA**

If Chromium/Chrome is installed, drive the local fixture in headless mode at desktop and mobile widths, capture screenshots, inspect them, and exercise filters, mode diagnostics, selected-record actions, inline PDF navigation, keyboard focus, and clear-all. If no browser exists, record the unavailable tool and perform the specified code-level responsive/accessibility review.

- [ ] **Step 6: Run full code review and resolve findings**

Use `compound-engineering:ce-code-review` with `base:origin/main`, `plan:docs/superpowers/plans/2026-07-10-library-webui-endnote-workflows.md`, and full depth. Apply every valid P1/P2/P3 finding with regression tests, then rerun relevant and full gates.

- [ ] **Step 7: Confirm clean branch state and acceptance mapping**

```bash
git status --short --branch
git log --oneline --decorate origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: clean feature branch; every #114 checkbox maps to code, tests, docs, and fresh verification evidence.

- [ ] **Step 8: Push and open the PR**

Push `feat/issue-114-endnote-webui`, open a PR whose body includes `Closes #114`, design/architecture notes, security decisions, screenshots, and exact verification results, then wait for required CI and address any failure before handoff.
