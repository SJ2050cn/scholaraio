# ScholarAIO Third-Party Integration Quality Audit

This document records the quality, reachability, and output validation status of the third-party integrations, APIs, CLIs, and optional toolchains supported by ScholarAIO. 

Integrations are evaluated at the workflow boundary, checking CLI/skill entrypoints, provider implementations, setup diagnostics, output formatting, fallback behaviors, and failure handling. A config test or a broad unit-test filename is not enough evidence to mark an integration surface as Good.

---

## 1. Quality Matrix

| Integration / Surface | Category | Status | Verification Path / Test Evidence | Observed Result / Config & Version Boundaries |
| :--- | :--- | :--- | :--- | :--- |
| **qt-web-extractor (HTTP & MCP)** | Web / Agent | **needs-cleanup** | `extract_web` / `tests/test_webtools_source.py` | Sanitized output successfully resolves table-cell code fence corruption. Boundaries: `webextract.transport` (HTTP/MCP), `webextract.base_url`, `webextract.mcp_url`, `webextract.api_key`. |
| **GUILessBingSearch** | Web / Agent | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MinerU Local API** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MinerU Cloud CLI** | Parsing | **good** | `test_mineru.py` | Handles `mineru-open-api` subprocess calls; enforces filename constraints safely. Boundaries: `ingest.mineru_api_key` / `MINERU_TOKEN`, `mineru-open-api` CLI package. |
| **Paper2Any MCP Sidecar** | Parsing/MCP | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Docling Fallback** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **PyMuPDF Fallback** | Parsing | **good** | `test_pdf_fallback.py` | Robust extraction fallback when default parser fails. Boundaries: `pymupdf` / `fitz` dependency presence. |
| **arXiv Search (Atom API)** | Discovery | **good** | `test_arxiv_source.py` | Atom XML parser is stable; query filters match client expectations. Boundaries: HTTP requests to `export.arxiv.org`. |
| **arXiv PDF Download** | Discovery | **good** | `test_arxiv_source.py` | Enforces `RATE_LIMIT_DELAY = 3.0` spacing in `batch_download`. Boundaries: `https://arxiv.org/pdf/` endpoint. |
| **OpenAlex Explore** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Crossref / Semantic Scholar** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Zotero SQLite Import** | Import/Export | **good** | `test_workspace.py` | Parsed SQLite columns correctly map to `PaperMetadata`. Boundaries: Local `zotero.sqlite` database schema layout. |
| **Zotero Web API** | Import/Export | **usable-with-caveats** | `fetch_zotero_api` / `import-zotero` | pyzotero retrieves metadata; linked/external attachments are skipped by design. Boundaries: `zotero.api_key`, `zotero.library_id`, `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`. |
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
| **Setup Diagnostics** | System | **good** | `test_setup.py` | Reports dependency presence and credential state in bilingual strings. Boundaries: CLI `scholaraio setup check` / `run_check` path. |

---

## 2. Detailed Integration Audits (Workflow Boundary Analysis)

### 2.1 qt-web-extractor (HTTP & MCP)
* **CLI/Skill Entrypoint**:
  * CLI: `scholaraio webextract <url>` (implemented in `cmd_webextract` inside [web.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/interfaces/cli/web.py))
  * Skill: `.claude/skills/webextract`
* **Provider/Service Implementation Path**:
  * [webtools.py:extract_web](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/providers/webtools.py#L613-L673)
* **Setup Diagnostics**:
  * Tested via `scholaraio setup check` (calls `_optional_webtool_detail` inside [setup.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/services/setup.py#L617-L665)), which executes `check_webextract_service` to verify that the HTTP/MCP endpoint responds.
* **Output Quality & Validation**:
  * Outputs parsed GFM Markdown. Output quality is protected by `_clean_table_code_fences` to sanitize malformed block code fences in Wikipedia/infobox table cells, resolving broken table rendering.
  * Verified via raw/cleaned fixtures: [wikipedia_infobox_bad.md](file:///c:/Users/hp/Desktop/Scholara_oss/tests/fixtures/wikipedia_infobox_bad.md) and [wikipedia_infobox_clean.md](file:///c:/Users/hp/Desktop/Scholara_oss/tests/fixtures/wikipedia_infobox_clean.md).
* **Fallback Behavior**:
  * Configured via `webextract.transport` (HTTP or MCP). When configured as HTTP, failure to connect triggers fallback hint to MCP or setup checks.
* **Failure Handling**:
  * Unreachable HTTP endpoints raise `WebExtractServiceUnavailableError`, returning a clean user-facing hint with exit code `1`.
  * API/Server errors raise `WebExtractError`, showing warnings/errors instead of generic crashes.

### 2.2 MinerU Cloud CLI (`mineru-open-api`)
* **CLI/Skill Entrypoint**:
  * CLI: `scholaraio ingest <pdf>` or `scholaraio/providers/mineru.py` main parser CLI.
  * Skill: `.claude/skills/ingest`
* **Provider/Service Implementation Path**:
  * [mineru.py:convert_pdf_cloud](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/providers/mineru.py#L702-L810)
* **Setup Diagnostics**:
  * Checked under `scholaraio setup check` via `_detect_mineru` which verifies presence of `mineru-open-api` in system path (`shutil.which`) and reads credential key values.
* **Output Quality & Validation**:
  * Translates PDF structures to Markdown with images/formulas.
  * Sanitizes cloud upload filenames via `_cloud_safe_pdf_name` to prevent platform-specific characters from crashing the extraction.
  * Handles chunk merging for multi-part large PDF parsing.
* **Fallback Behavior**:
  * When MinerU is missing or fails, it falls back to the list of alternatives defined in the configuration option `pdf_fallback_order` (e.g. `["docling", "pymupdf"]`).
* **Failure Handling**:
  * Subprocess timeouts (`subprocess.TimeoutExpired`) are caught.
  * Non-zero return codes from `mineru-open-api` raise descriptive errors containing stderr output.
  * Retries are handled with exponential backoff (`attempts` based on `mineru_upload_retries`).

### 2.3 PyMuPDF Fallback (`fitz`)
* **CLI/Skill Entrypoint**:
  * CLI: Invoked automatically as part of PDF ingestion when MinerU fails, or manually by setting `pdf_preferred_parser: pymupdf`.
* **Provider/Service Implementation Path**:
  * [pdf_fallback.py:run_pymupdf](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/providers/pdf_fallback.py#L142-L160)
* **Setup Diagnostics**:
  * Checked in `scholaraio setup check` via `_check_dep_group("fitz")`.
* **Output Quality & Validation**:
  * Extracts page-by-page flat plaintext with page headers (`## Page N\n\n`). Lacks complex block structure formatting but acts as a highly reliable baseline.
* **Fallback Behavior**:
  * Represents the last-resort fallback in the fallback parser chain (since it has no model/server dependencies).
* **Failure Handling**:
  * Catches general exception and formats error messages, skipping page crashes or file read errors gracefully without aborting the ingest execution pipeline.

### 2.4 arXiv Search & PDF Download
* **CLI/Skill Entrypoint**:
  * CLI: `scholaraio search --arxiv` (runs `cmd_search` inside [search.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/interfaces/cli/search.py)) and `scholaraio paper fetch` to retrieve PDFs.
  * Skill: `.claude/skills/search`, `.claude/skills/paper-guided-reading`
* **Provider/Service Implementation Path**:
  * [arxiv.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/providers/arxiv.py) (`_query_arxiv_api`, `download_arxiv_pdf`, and `batch_download`).
* **Setup Diagnostics**:
  * Setup checks verify internet connection and reachability of arXiv query export endpoints.
* **Output Quality & Validation**:
  * Parses response XML via `defusedxml.ElementTree` to prevent XML External Entity (XXE) vulnerabilities, mapping properties directly to `ArxivPaper` dataclasses.
  * Performs client-side field filtration (`_filter_search_results`) on author, title, and abstract fields to tighten results returned by arXiv's loose matching API.
* **Fallback Behavior**:
  * Gracefully fails with standard warning logs if the arXiv endpoint is offline, returning empty results rather than hard crashes.
* **Failure Handling**:
  * A requests session is mounted with a custom `urllib3` retry adapter to handle transient `429`, `502`, `503`, and `504` status codes automatically.
  * Enforces a polite rate limit delay `RATE_LIMIT_DELAY = 3.0` between successive paper downloads in batch modes.

### 2.5 Zotero Integration (Web API & Local SQLite Import)
* **CLI/Skill Entrypoint**:
  * CLI: `scholaraio import-zotero` command (`cmd_import_zotero` inside [import_zotero.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/interfaces/cli/import_zotero.py)).
  * Skill: `.claude/skills/import-zotero`
* **Provider/Service Implementation Path**:
  * [zotero.py](file:///c:/Users/hp/Desktop/Scholara_oss/scholaraio/providers/zotero.py) (`fetch_zotero_api` for cloud Web API, `parse_zotero_local` for local SQLite databases).
* **Setup Diagnostics**:
  * Checked in `setup.py` by verifying presence of Zotero API credentials.
* **Output Quality & Validation**:
  * Maps Zotero types (e.g. `journalArticle`, `preprint`) to standard `PaperMetadata` types.
  * Locates corresponding PDF attachments and copies them into the import directory.
* **Fallback Behavior**:
  * Supports local SQLite database import via `--local <path/to/sqlite>` if API keys are missing or the API is unreachable.
  * Skips unresolvable attachments/links instead of failing the import.
* **Failure Handling**:
  * Catches `ImportError` on `pyzotero` to prompt users to install optional dependencies.
  * Attachment download failures are caught per-item, logging warnings while continuing to parse the rest of the collection.
