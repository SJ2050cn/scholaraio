# Rendered Web Extraction (Optional)

ScholarAIO is Codex-native first: ordinary web discovery, source verification,
and reading should use Codex's native web capabilities. ScholarAIO's optional
web integration is limited to producing rendered, ingestion-ready content from
a URL when native reading is insufficient.

## When to use this

Use the external `qt-web-extractor` integration only when:

- a user wants a webpage or online PDF persisted in the ScholarAIO library;
- JavaScript rendering is required to recover the meaningful page body;
- an online PDF needs an explicit extraction hint; or
- native URL reading failed and a rendered Markdown representation is required.

Do not use it for routine web discovery, current-information lookup, or normal
page reading. Those tasks belong to Codex's native web search and URL tools.

## Native ScholarAIO entrypoint

Use `ingest-link` when the selected URL should become a durable ScholarAIO
document:

```bash
scholaraio ingest-link https://example.com/page
```

This command:

1. Calls a configured `qt-web-extractor` service.
2. Pulls rendered page content instead of only raw HTML source.
3. Writes extracted Markdown into a temporary document inbox.
4. Reuses the normal ScholarAIO document-ingest pipeline.
5. Preserves source URL and extraction provenance in the resulting record.

In practice, the flow supports JavaScript-rendered pages, online PDFs, technical
documentation, manuals, standards, and web articles as normal `document`
records.

## Configuration

For agent workflows, prefer the MCP endpoint:

```yaml
webextract:
  transport: mcp
  mcp_url: http://127.0.0.1:8766/mcp
  api_key: your_key   # optional; sent as Bearer auth
  mcp_tool: fetch_url # optional; default
```

The legacy HTTP endpoint remains available for compatibility:

```yaml
webextract:
  transport: http
  base_url: http://127.0.0.1:8766
  api_key: your_key
```

Resolution order:

1. `config.yaml -> webextract.transport` / `mcp_url` / `mcp_tool`
2. `config.yaml -> webextract.base_url` / `api_key`
3. `WEBEXTRACT_MCP_URL` / `QT_WEB_EXTRACTOR_MCP_URL`
4. `WEBEXTRACT_URL` / `WEBEXTRACT_API_KEY` / `QT_WEB_EXTRACTOR_API_KEY`
5. `http://127.0.0.1:8766`

ScholarAIO's MCP client follows the Streamable HTTP lifecycle and sends Bearer
authentication when configured.

## Agent MCP registration

The repository-level `.mcp.json` advertises the optional extractor for hosts
that support project-scoped MCP configuration. Codex uses its own MCP registry;
register the extractor only on machines that need rendered URL ingestion:

```bash
codex mcp add web-extractor --url http://127.0.0.1:8766/mcp
```

For bearer authentication:

```bash
codex mcp add web-extractor --url http://127.0.0.1:8766/mcp \
  --bearer-token-env-var QT_WEB_EXTRACTOR_API_KEY
```

Claude Code can consume `.mcp.json` directly or register the endpoint with:

```bash
claude mcp add --transport http web-extractor http://127.0.0.1:8766/mcp
```

The known tool name is `fetch_url` with `{"url": "https://..."}`.

## Operational guidance

- Search and select sources with the host agent first; ingest only URLs the user
  wants to keep.
- Prefer local ScholarAIO evidence for stable academic claims.
- Record access dates for time-sensitive external sources.
- If the extractor is unavailable, ordinary web reading should continue through
  host-native tools; only rendered ingestion is blocked.
- Let automatic URL/PDF handling run first and use
  `scholaraio ingest-link --pdf <url>` only when the backend needs an explicit
  PDF hint.

`qt-web-extractor` is an external daemon, not a built-in ScholarAIO fetcher.
ScholarAIO delegates rendering to it, then resumes control for ingestion,
provenance, indexing, and local retrieval.
