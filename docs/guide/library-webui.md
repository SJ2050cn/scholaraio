# Library WebUI

The ScholarAIO Library WebUI is a local, library-read-only workspace for browsing records, copying citations, reading PDFs, checking metadata quality, and running ranked retrieval without leaving the browser.

## Start the WebUI

```bash
scholaraio gui
```

By default, ScholarAIO listens on `127.0.0.1:8765` and opens the page in your browser. To choose another local port or avoid opening a browser automatically:

```bash
scholaraio gui --port 9000 --no-open
```

The page loads only assets packaged with ScholarAIO. It does not load remote JavaScript, fonts, analytics, or CDNs.

## Search modes

The main library offers four explicit modes.

| Mode | What it searches | Index required |
| --- | --- | --- |
| **Metadata** | The currently loaded title, author, journal/source, DOI, IDs, and directory name | None |
| **Keyword** | FTS5 title, abstract, and conclusion text | Keyword index |
| **Semantic** | Vector similarity over embedded paper metadata/content | Embeddings and the configured embedding provider |
| **Unified** | Reciprocal-rank fusion of Keyword and Semantic results | Keyword index; embeddings recommended |

Metadata mode filters immediately. Keyword, Semantic, and Unified modes run ranked retrieval on the server when you choose **Search** or press Enter in the query field. Ranked rows show their rank, retrieval leg, and score. Click a column heading to sort the current result set by that field; run the search again to restore relevance order.

Proceedings child papers currently support Metadata mode only. The mode selector is disabled on the Proceedings tab and the limitation is shown directly in the search status area.

### Prepare search indexes

Build or refresh the keyword index after library metadata or full text changes:

```bash
scholaraio index --rebuild
```

Build semantic embeddings after the keyword index exists:

```bash
scholaraio embed
```

Unified search remains honest about degradation. If vectors are unavailable, it labels the result as keyword-only and shows `scholaraio embed`; if the keyword index is unavailable, it shows `scholaraio index --rebuild`. Semantic mode never substitutes keyword results while claiming semantic retrieval occurred.

## Structured filters

Filters combine with AND semantics. You can compose:

- query text;
- title;
- author;
- inclusive year-from and year-to bounds;
- journal or proceedings source;
- DOI;
- paper type;
- proceedings volume.

**Clear all** removes every filter, cancels stale ranked responses, returns to Metadata mode, and restores the default year-descending sort. The status at the bottom of the filter card reports the active-filter count.

## Record actions

Select a row to open its Inspector. The action row uses the selected record's stable paper ID and canonical metadata.

### Copy BibTeX

Choose **Copy BibTeX** to generate a complete entry on the server with ScholarAIO's canonical BibTeX formatter and copy it to the clipboard. The browser clipboard API is used first. If it is unavailable or denied, the WebUI uses a temporary local textarea fallback and removes it immediately afterward. A status toast reports success or failure.

Main-library and proceedings child records are both supported. Proceedings entries include their proceedings title as `booktitle` when available.

### Read a PDF inline

Choose **Preview PDF** or the table's **PDF** pill to keep reading inside the WebUI. The existing fullscreen and back-to-records controls remain available.

### Open a PDF in the default viewer

When ScholarAIO can reach a desktop safely, choose **Open in default viewer** to launch the same canonical PDF in the operating system's configured PDF application. This supports opening several papers in independent native windows while keeping the WebUI available for searching.

On WSL, ScholarAIO copies the PDF to a managed `ScholarAIO` folder under the Windows temporary directory and asks Windows to open that copy. The Windows default association is respected, including applications such as Foxit Reader. Temporary copies older than 24 hours are cleaned up opportunistically. The canonical library PDF is never modified.

When the WebUI is bound to a non-loopback host, or the server has no compatible desktop launcher, the action automatically becomes **Download PDF**. The browser receives an attachment and opens or saves it on the client machine according to its own settings. This is the correct behavior for a WebUI hosted on another computer: a server cannot directly launch an application on the browser's computer.

The action is intentionally restricted:

- the server must be bound to a loopback host;
- the browser request must have the same loopback origin and server port;
- every server process creates a new anti-CSRF token;
- the request body contains a stable paper ID, never a filesystem path; and
- ScholarAIO resolves that ID through the configured library before launching an application.

If an advertised native launch fails at runtime, the WebUI automatically starts the browser download and reports the fallback. The action is disabled only when the selected record has no PDF. The library remains metadata-read-only; opening or downloading a PDF does not edit a record.

## Live refresh and ranked results

The record list continues to refresh from the library. Expensive semantic or unified queries are not automatically rerun on every poll. If filters change, the search status asks you to run Search again. Stale detail, refresh, and ranked-search responses are ignored so an older request cannot overwrite the current source or query.

## Troubleshooting

| Message or state | What to do |
| --- | --- |
| `Keyword search index is unavailable` | Run `scholaraio index --rebuild`. |
| `Semantic search index or embedding provider is unavailable` | Configure an embedding provider if needed, then run `scholaraio embed`. |
| Unified search is `degraded` | Results are still valid for the available retrieval leg; follow the displayed rebuild command to restore both legs. |
| The action says **Download PDF** | This is expected for remote/non-loopback deployments or hosts without a desktop launcher; the file is delivered to the browser computer. |
| Native viewer launch fails on WSL | Confirm Windows interoperability provides `powershell.exe` and `wslpath`, and that Windows has a default PDF application. The WebUI falls back to a browser download if launch still fails. |
| Native viewer launch fails on Linux | Install/configure `xdg-open` and a default PDF application in the desktop session. The WebUI falls back to a browser download if launch still fails. |
| BibTeX copy fails | Allow clipboard access or use a browser that supports the local textarea copy fallback. |
| No rows remain after filtering | Choose **Clear all**, then add filters one at a time. |

For CLI-level search details, see [Search & Browse](search.md). For the full command surface, see the [CLI Reference](cli-reference.md).
