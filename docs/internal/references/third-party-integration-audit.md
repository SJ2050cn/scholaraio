# ScholarAIO Third-Party Integration Quality Audit

This document records the quality, reachability, and output validation status of the third-party integrations, APIs, CLIs, and optional toolchains supported by ScholarAIO.

Dependency admission and Codex-native overlap decisions are maintained in
`code-and-dependency-technical-debt-audit.md`. This document remains the
workflow-evidence matrix; an integration is not promoted here merely because it
is retained as an optional capability there.

Integrations are evaluated at the workflow boundary, checking CLI/skill entrypoints, provider implementations, setup diagnostics, output formatting, fallback behaviors, and failure handling. A config test or a broad unit-test filename is not enough evidence to mark an integration surface as Good.

This audit is not a declaration that the full third-party toolchain is adapted or verified. Each row claims only the evidence listed in that row; everything else remains inventory until a focused live or workflow-boundary pass verifies it.

Status is intentionally conservative:

- **good**: workflow-boundary evidence exists, including commands, representative output, and failure handling.
- **partially-reviewed**: code-level or fixture evidence exists, but live workflow evidence is still missing.
- **not-yet-reviewed**: inventory only; no quality claim is made.

---

## 1. Quality Matrix

| Integration / Surface | Category | Status | Verification Path / Test Evidence | Observed Result / Config & Version Boundaries |
| :--- | :--- | :--- | :--- | :--- |
| **qt-web-extractor (HTTP & MCP)** | Web / Agent | **partially-reviewed** | `extract_web`, `_clean_table_code_fences`, `tests/test_webtools_source.py`, fixture pair under `tests/fixtures/` | Sanitizer regression is covered for malformed table-cell code fences and adjacent standalone code blocks. Live daemon canary evidence is still required before this surface is promoted to `good`. Boundaries: `webextract.transport` (HTTP/MCP), `webextract.base_url`, `webextract.mcp_url`, `webextract.api_key`. |
| **GUILessBingSearch compatibility adapter** | Web / Agent | **not a default surface** | `tests/test_webtools_source.py` | Retained only for existing Python/config callers. ScholarAIO no longer registers a search skill, CLI command, setup check, generated config block, or default MCP server; agents use host-native web search. |
| **MinerU Local API** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MinerU Cloud CLI** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Paper2Any MCP Sidecar** | Parsing/MCP | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Docling Fallback** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **PyMuPDF Fallback** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **arXiv Search (Atom API)** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **arXiv PDF Download** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **OpenAlex Explore** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Crossref / Semantic Scholar** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Zotero SQLite Import** | Import/Export | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Zotero Web API** | Import/Export | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **EndNote / RIS** | Import/Export | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **USPTO ODP / PPubs** | Patents | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **OpenAI-compatible Chat API** | LLM Backend | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Anthropic Messages API** | LLM Backend | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Google Gemini API** | LLM Backend | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Zhipu API** | LLM Backend | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **vLLM / Ollama Local** | LLM Backend | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Sentence-transformers Embeddings** | Vector/Embed | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **FAISS Vector / BERTopic** | Vector/Embed | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MarkItDown Office Ingest** | Office/Output | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Office PPTX / DOCX Libraries** | Office/Output | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Mermaid / DOT Rendering** | Diagram | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Scientific Toolref (Quantum ESPRESSO, etc.)** | Toolref | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **AmberTools / PyMOL** | Scientific | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **rsync / SSH Backup** | System | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Setup Diagnostics** | System | **not-yet-reviewed** | N/A | Excluded from current triage phase. |

---

## 2. Current Reviewed Surface

### 2.1 qt-web-extractor (HTTP & MCP)
* **CLI/Skill Entrypoint**:
  * CLI: `scholaraio webextract <url>` (implemented in `cmd_webextract` inside `scholaraio/interfaces/cli/web.py`)
  * Skill: `.claude/skills/webextract`
* **Provider/Service Implementation Path**:
  * `scholaraio/providers/webtools.py:extract_web`
* **Setup Diagnostics**:
  * Diagnostic path exists through `scholaraio setup check` (calls `_optional_webtool_detail` inside `scholaraio/services/setup.py`), which executes `check_webextract_service` to verify that the HTTP/MCP endpoint responds. This PR does not include live daemon evidence from that path.
* **Output Quality & Validation**:
  * Outputs parsed GFM Markdown. Output quality is protected by `_clean_table_code_fences` to sanitize malformed block code fences in Wikipedia/infobox table cells, resolving broken table rendering.
  * Verified via unit and fixture coverage: `tests/fixtures/wikipedia_infobox_bad.md`, `tests/fixtures/wikipedia_infobox_clean.md`, and regression tests for standalone fenced code blocks near table or pipe-prefixed lines.
* **Fallback Behavior**:
  * Configured via `webextract.transport` (HTTP or MCP). When configured as HTTP, failure to connect triggers fallback hint to MCP or setup checks.
* **Failure Handling**:
  * Unreachable HTTP endpoints raise `WebExtractServiceUnavailableError`, returning a clean user-facing hint with exit code `1`.
  * API/Server errors raise `WebExtractError`, showing warnings/errors instead of generic crashes.

## 3. Not-Yet-Reviewed Inventory

Rows marked `not-yet-reviewed` in the matrix are intentionally inventory-only. Promoting any of them to `partially-reviewed` or `good` should happen in a focused follow-up that includes:

- exact CLI command or skill workflow exercised;
- relevant config/version boundaries;
- representative success output;
- failure-mode behavior;
- targeted tests or reproducible smoke evidence.
