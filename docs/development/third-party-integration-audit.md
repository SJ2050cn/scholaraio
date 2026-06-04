# ScholarAIO Third-Party Integration Quality Audit

This document records the quality, reachability, and output validation status of the third-party integrations, APIs, CLIs, and optional toolchains supported by ScholarAIO. 

Integrations are evaluated at the workflow boundary, checking CLI/skill entrypoints, provider implementations, setup diagnostics, output formatting, fallback behaviors, and failure handling.

---

## 1. Quality Matrix

| Integration / Surface | Category | Status | Verification Path / Test Evidence | Observed Result / Boundaries |
| :--- | :--- | :--- | :--- | :--- |
| **qt-web-extractor (HTTP & MCP)** | Web / Agent | **needs-cleanup** | `extract_web` / `tests/test_webtools_source.py` | Sanitized output successfully resolves table-cell code fence corruption on Wikipedia. |
| **GUILessBingSearch** | Web / Agent | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MinerU Local API** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **MinerU Cloud CLI** | Parsing | **good** | `test_mineru.py` | Handles `mineru-open-api` subprocess calls; enforces filename constraints safely. |
| **Docling Fallback** | Parsing | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **PyMuPDF Fallback** | Parsing | **good** | `test_pdf_fallback.py` | Robust extraction fallback when default parser fails. |
| **arXiv Search (Atom API)** | Discovery | **good** | `test_arxiv_source.py` | Atom XML parser is stable; query filters match client expectations. |
| **arXiv PDF Download** | Discovery | **good** | `test_arxiv_source.py` | Enforces `RATE_LIMIT_DELAY = 3.0` between successive paper downloads. |
| **OpenAlex Explore** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Crossref / Semantic Scholar** | Discovery | **not-yet-reviewed** | N/A | Excluded from current triage phase. |
| **Zotero SQLite Import** | Import/Export | **good** | `test_workspace.py` | Parsed SQLite columns correctly map to `PaperMetadata`. |
| **Zotero Web API** | Import/Export | **usable-with-caveats** | `fetch_zotero_api` / `import-zotero` | pyzotero retrieves metadata; linked/external attachments are skipped by design. |
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
| **Setup Diagnostics** | System | **good** | `test_setup.py` | Reports dependency presence and credential state in bilingual strings. |

---

## 2. Seed Issue: qt-web-extractor Table Cell Corruption
- **Symptom**: Unescaped block elements (e.g. ` ``` ` or `\n\n`) inside Wikipedia tables break Markdown parsing and cause garbled readback.
- **Verification Fixtures**:
  - Raw Input: [wikipedia_infobox_bad.md](file:///c:/Users/hp/Desktop/Scholara_oss/tests/fixtures/wikipedia_infobox_bad.md)
  - Expected Output: [wikipedia_infobox_clean.md](file:///c:/Users/hp/Desktop/Scholara_oss/tests/fixtures/wikipedia_infobox_clean.md)
- **Fix**: Added a regex sanitization helper in `scholaraio/providers/webtools.py` called `_clean_table_code_fences`. It scans the output Markdown for block elements bounded by table column pipes (`|`) and collapses them to inline code blocks:
  ```python
  res["text"] = _clean_table_code_fences(res["text"])
  ```
- **Scope**: Executed at the end of the `extract_web` function to clean both HTTP and MCP outputs prior to consumption by RAG and CLI workflows.
