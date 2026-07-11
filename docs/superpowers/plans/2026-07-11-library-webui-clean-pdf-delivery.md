# Library WebUI Clean UI and Cross-Platform PDF Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the library WebUI chrome and deliver PDFs correctly through Windows from WSL, through native desktop launchers locally, or through browser download remotely.

**Architecture:** Keep stable paper IDs as the only browser-to-server file selector. Extend the default-application adapter with a capability probe and a WSL-to-Windows temporary-copy launcher, expose a truthful delivery strategy through `/api/capabilities`, and use the existing PDF GET route for attachment downloads and runtime fallback.

**Tech Stack:** Python 3.10+, standard-library HTTP server, subprocess/pathlib/shutil/tempfile-style filesystem operations, vanilla JavaScript, HTML/CSS, pytest, Node VM tests.

---

### Task 1: Remove low-value WebUI chrome and lock PDF actions to one line

**Files:**
- Modify: `scholaraio/interfaces/cli/library-view/index.html`
- Modify: `scholaraio/interfaces/cli/library-view/app.js`
- Modify: `scholaraio/interfaces/cli/library-view/workflows.css`
- Test: `tests/test_gui_server.py`

- [ ] **Step 1: Write failing HTML/CSS contract tests**

Assert that the packaged HTML no longer contains `Has audit issues`, `Missing Markdown`, metric error/warning IDs, or the four unwanted kicker elements. Assert that `Preview PDF` and the external action remain present, and that CSS applies `white-space: nowrap` plus a two-column detail-action grid.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py -k "shell or action or chrome"`

Expected: FAIL because the unwanted controls/metrics/kickers remain and the no-wrap contract is absent.

- [ ] **Step 3: Remove markup and dead JavaScript bindings**

Delete the two checkbox rows, error/warning metric rows, and only the `Source`, `Discover`, `Records`, and `Inspector` kicker nodes. Remove corresponding DOM references, metric writes, filter state, filtering predicates, active-count entries, and event listeners while retaining audit status rendering in rows/details.

- [ ] **Step 4: Make the action grid stable**

Keep `Copy BibTeX` across the full grid. Give the PDF actions explicit asymmetric minimum columns and `white-space: nowrap`; do not collapse the two PDF actions into separate rows at the current mobile breakpoint.

- [ ] **Step 5: Run focused GUI tests and commit**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py`

Commit: `fix(gui): simplify library chrome and stabilize PDF actions`

### Task 2: Add WSL-aware default-application capability and launch

**Files:**
- Modify: `scholaraio/services/system_open.py`
- Test: `tests/test_system_open.py`

- [ ] **Step 1: Write failing WSL capability tests**

Cover WSL detection by environment/kernel markers, missing `powershell.exe`/`wslpath`, and capability targets `windows`, `host`, or unavailable. Existing Windows/macOS/Linux behavior must remain covered.

- [ ] **Step 2: Write failing WSL launch tests**

Use a real temporary source PDF and mocked subprocess boundaries. Assert that the adapter resolves the Windows temp directory, copies into its managed `ScholarAIO` directory, converts the copied path with `wslpath -w`, and passes the path through a constant PowerShell command rather than interpolating it into command text.

- [ ] **Step 3: Verify RED**

Run: `python -m pytest -q -p no:cacheprovider tests/test_system_open.py`

Expected: FAIL because Linux currently dispatches only to `xdg-open` and has no capability probe or WSL temporary-copy path.

- [ ] **Step 4: Implement the minimal adapter**

Add focused helpers for WSL detection, launcher discovery, Windows temp resolution, filename sanitization, stale-copy cleanup, and detached PowerShell launch. Use argument arrays, constant PowerShell source, timeouts for synchronous probes, and `DefaultApplicationOpenError` for controlled failures.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest -q -p no:cacheprovider tests/test_system_open.py`

Commit: `fix(pdf): open WSL papers in the Windows default viewer`

### Task 3: Expose truthful native/download capability and attachment delivery

**Files:**
- Modify: `scholaraio/interfaces/cli/gui.py`
- Test: `tests/test_gui_server.py`

- [ ] **Step 1: Write failing API tests**

Assert that loopback plus a supported WSL/native launcher advertises `pdf_delivery.mode=native`, while non-loopback or missing launchers advertises `mode=download`. Preserve `native_pdf_open` for compatibility. Assert `download=1` returns `Content-Disposition: attachment` and normal preview remains `inline` with the same security headers.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py -k "capabilities or pdf"`

- [ ] **Step 3: Implement capability wiring and download disposition**

Probe the server host and default-application adapter when creating the handler. Store the immutable delivery capability on the configured handler. Extend `_send_pdf` with an attachment flag derived from the query string without adding a new filesystem route.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py -k "capabilities or pdf"`

Commit: `feat(gui): expose native and download PDF delivery modes`

### Task 4: Implement client download mode and native-failure fallback

**Files:**
- Modify: `scholaraio/interfaces/cli/library-view/app.js`
- Modify: `scholaraio/interfaces/cli/library-view/index.html`
- Test: `tests/test_gui_server.py`

- [ ] **Step 1: Write failing JavaScript behavior tests**

Test three paths in the existing Node VM harness:

1. native capability posts the stable paper ID and reports success;
2. download capability creates/clicks/removes a same-origin attachment anchor without POSTing;
3. native POST failure triggers exactly one download and reports the fallback.

Also assert the action label is `Open in default viewer` for native and `Download PDF` for remote mode.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py -k "native_pdf or download"`

- [ ] **Step 3: Implement strategy-aware action state**

Normalize `pdf_delivery` from capabilities with backward-compatible defaults. Add a URL helper that appends `download=1`, a temporary-anchor download primitive, and fallback handling around the privileged POST. Keep busy state and toast messages truthful.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q -p no:cacheprovider tests/test_gui_server.py`

Commit: `feat(gui): download PDFs when native launch is unavailable`

### Task 5: Document deployment behavior and validate the complete change

**Files:**
- Modify: `docs/guide/library-webui.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_gui_server.py`
- Test: `tests/test_system_open.py`

- [ ] **Step 1: Document the behavior matrix**

Describe WSL-to-Windows temporary copies, native desktop launch, remote attachment download, automatic fallback, 24-hour cleanup, and the browser security limitation that prevents a remote server from directly starting a client application.

- [ ] **Step 2: Run targeted and static checks**

Run:

- `python -m pytest -q -p no:cacheprovider tests/test_system_open.py tests/test_gui_server.py`
- `/home/lzmo/miniconda3/envs/scholaraio/bin/ruff check scholaraio tests`
- `/home/lzmo/miniconda3/envs/scholaraio/bin/ruff format --check scholaraio tests`
- `/home/lzmo/miniconda3/envs/scholaraio/bin/mypy scholaraio`
- `node --check scholaraio/interfaces/cli/library-view/app.js`
- `git diff --check`

- [ ] **Step 3: Run full regression**

Run: `python -m pytest -q -p no:cacheprovider`

Expected: all tests pass with the new WSL, download, DOM, CSS, and fallback cases.

- [ ] **Step 4: Run real WSL runtime smoke**

Launch the feature checkout on an alternate loopback port without touching the production systemd service. Check health/capabilities, inline headers, attachment headers, and launch one known PDF through the Windows default association. Confirm no metadata files change. Restart the managed service only after the branch merges and the primary checkout is aligned.

- [ ] **Step 5: Commit docs and final verification evidence**

Commit: `docs(gui): explain cross-platform PDF delivery`

### Task 6: Review, ship, align, and restart

**Files:**
- Review all branch changes against `origin/main`

- [ ] **Step 1: Run structured code review and address findings with TDD**

- [ ] **Step 2: Push and create a PR describing user-visible behavior, security boundaries, validation, and remote limitations**

- [ ] **Step 3: Wait for CI and delayed automated review feedback; fix all valid findings before merge**

- [ ] **Step 4: Merge the PR, fast-forward `/home/lzmo/repos/personal/scholaraio` to `origin/main`, and restart `scholaraio-webui.service`**

- [ ] **Step 5: Verify `HEAD == origin/main`, service active, new assets loaded, capabilities truthful, and all review threads resolved**
