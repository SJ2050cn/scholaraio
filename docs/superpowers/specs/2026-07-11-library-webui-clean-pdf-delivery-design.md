# Library WebUI Clean UI and Cross-Platform PDF Delivery Design

**Status:** Approved for implementation

## Goal

Remove low-value audit chrome from the library WebUI and make the selected-record PDF action truthful and useful across WSL, native desktop hosts, and remote deployments. The current inline preview remains available.

## Selected Approach

Use a capability-aware hybrid strategy:

- WSL copies the selected PDF into a managed Windows temporary directory and launches it through Windows PowerShell, so the Windows default PDF association (including Foxit) is honored.
- Native Windows, macOS, and Linux desktop hosts continue to use their default-application launcher.
- Non-loopback or launcher-less deployments download the PDF to the browser client instead of claiming that a server-side viewer opened.
- A native-launch failure automatically falls back to client download.

Always downloading was rejected because it degrades the local desktop workflow. A required client companion was rejected because it adds installation, protocol-handler, and security surface that is unnecessary for the current requirements.

## UI Simplification

Remove these sidebar controls and metrics:

- `Has audit issues`
- `Missing Markdown`
- `Errors`
- `Warnings`

Remove the gray uppercase kickers `Source`, `Discover`, `Records`, and `Inspector`. Keep the meaningful source title, record count, search title, selected-paper title, status pills, and detail quality information.

The selected-record action grid keeps `Copy BibTeX` full width. `Preview PDF` and the external PDF action share one row. Both buttons use non-wrapping labels and explicit minimum widths. The external action reads `Open in default viewer` when native launch is available and `Download PDF` otherwise.

## PDF Capability Contract

`GET /api/capabilities` exposes a PDF delivery object:

```json
{
  "pdf_delivery": {
    "mode": "native",
    "target": "windows",
    "label": "Open in default viewer",
    "reason": ""
  }
}
```

`mode` is `native` or `download`. `target` is `windows`, `host`, or `client`. The existing `native_pdf_open` field remains for compatibility and reflects whether the privileged POST action is enabled.

The server enables native mode only when it is bound to loopback and a supported launcher is discoverable. A non-loopback binding always advertises download mode because a server cannot safely start an application on an unrelated browser client.

## WSL Launch Adapter

WSL detection uses the WSL environment markers and the Microsoft kernel release marker. The adapter requires `powershell.exe` and `wslpath`.

For a WSL-native source path:

1. Resolve and verify the server-owned PDF path.
2. Resolve the Windows temporary directory through a constant PowerShell command.
3. Copy the PDF to a private `ScholarAIO` subdirectory with a unique, sanitized `.pdf` filename.
4. Convert that temporary path to Windows form with `wslpath -w`.
5. invoke a constant PowerShell `Start-Process` command without interpolating the path into executable code.
6. Remove stale ScholarAIO temporary PDFs older than 24 hours during later launches.

The HTTP request continues to carry only a stable paper ID. The browser cannot supply a filesystem path, command, or filename.

## Remote Download

The existing same-origin PDF endpoint accepts `download=1`. Inline preview keeps `Content-Disposition: inline`; download mode returns `Content-Disposition: attachment` with the canonical sanitized filename. The browser starts the transfer through a temporary anchor rather than buffering the PDF in JavaScript.

If native launch returns an error, the client immediately starts the same download and reports the fallback in a toast. This keeps the PDF accessible on headless Linux, SSH-forwarded sessions, and partially configured desktops.

## Security and Error Handling

- Native launch retains loopback, exact-origin, CSRF, JSON content, body-size, and stable-ID checks.
- WSL subprocesses use argument arrays and constant PowerShell programs; no client value becomes command text.
- Temporary copies are created only from an already-resolved library PDF.
- Download is a read-only GET of the existing stable-ID PDF resource.
- Capability reasons and runtime errors remain safe and actionable without exposing local paths.

## Tests

- DOM contract: removed controls, metrics, and kickers are absent.
- CSS contract: PDF action labels do not wrap and both actions remain in one row.
- WSL unit tests: detection, Windows temp copy, safe launcher arguments, missing tools, and stale-file cleanup.
- Native host unit tests: Windows, macOS, and Linux launch behavior remains intact.
- HTTP tests: capability mode, attachment disposition, inline preview compatibility, and security headers.
- JavaScript tests: native launch, remote download mode, and native-failure download fallback.
- Runtime smoke: restart the actual WSL service, verify capabilities, download headers, and launch one real PDF through the Windows default association.
