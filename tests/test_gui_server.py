from __future__ import annotations

import io
import json
import shutil
import subprocess
import threading
from contextlib import contextmanager, suppress
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from scholaraio.core.config import _build_config


@contextmanager
def _running_library_server(cfg, *, host="127.0.0.1"):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    server = create_library_view_server(cfg, host=host, port=0)
    bound_host, port = server.server_address[:2]
    connect_host = "127.0.0.1" if bound_host in {"0.0.0.0", "::"} else bound_host
    if ":" in connect_host and not connect_host.startswith("["):
        connect_host = f"[{connect_host}]"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://{connect_host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def _json_response(url: str) -> tuple[dict, object]:
    with urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8")), response.headers


def _post_json(
    url: str,
    payload: object,
    *,
    token: str = "",
    origin: str = "",
    content_type: str = "application/json",
):
    headers = {"Content-Type": content_type}
    if token:
        headers["X-ScholarAIO-CSRF"] = token
    if origin:
        headers["Origin"] = origin
    return Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )


def _write_gui_action_fixtures(tmp_path: Path, *, main_pdf: bool = True):
    cfg = _build_config({}, tmp_path)
    main_dir = cfg.papers_dir / "Doe-2026-Action"
    main_dir.mkdir(parents=True)
    (main_dir / "meta.json").write_text(
        json.dumps(
            {
                "id": "action-paper",
                "title": "Action paper",
                "authors": ["Jane Doe"],
                "first_author_lastname": "Doe",
                "year": 2026,
                "journal": "Journal of Actions",
                "doi": "10.1000/action",
                "abstract": "Canonical abstract.",
                "paper_type": "journal-article",
            }
        ),
        encoding="utf-8",
    )
    if main_pdf:
        (main_dir / "Doe-2026-Action.pdf").write_bytes(b"%PDF-action")

    proceeding_dir = cfg.proceedings_dir / "Proc-2026-Actions"
    child_dir = proceeding_dir / "papers" / "Roe-2026-Proceeding"
    child_dir.mkdir(parents=True)
    (proceeding_dir / "meta.json").write_text(
        json.dumps({"id": "proc-actions", "title": "Proceedings of Actions", "year": 2026}),
        encoding="utf-8",
    )
    (child_dir / "meta.json").write_text(
        json.dumps(
            {
                "id": "proceeding-action-paper",
                "title": "Proceeding action paper",
                "authors": ["Pat Roe"],
                "first_author_lastname": "Roe",
                "year": 2026,
                "doi": "10.1000/proceeding-action",
                "paper_type": "conference-paper",
            }
        ),
        encoding="utf-8",
    )
    (child_dir / "Roe-2026-Proceeding.pdf").write_bytes(b"%PDF-proceeding")
    return cfg, main_dir, child_dir


def test_library_view_api_serves_live_json_and_rejects_writes(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    paper_dir = tmp_path / "data" / "libraries" / "papers" / "Doe-2026-Live"
    paper_dir.mkdir(parents=True)
    (paper_dir / "meta.json").write_text(
        json.dumps(
            {
                "id": "live-paper",
                "title": "Live paper",
                "authors": ["Jane Doe"],
                "year": 2026,
                "journal": "Live Journal",
                "doi": "10.1000/live",
                "abstract": "Live abstract.",
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "paper.md").write_text("# Live paper\n", encoding="utf-8")

    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/api/main/papers", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["total"] == 1
        assert payload["papers"][0]["paper_id"] == "live-paper"

        new_dir = tmp_path / "data" / "libraries" / "papers" / "Roe-2026-New"
        new_dir.mkdir()
        (new_dir / "meta.json").write_text(
            json.dumps({"id": "new-paper", "title": "New paper", "authors": ["Pat Roe"], "year": 2026}),
            encoding="utf-8",
        )

        with urlopen(f"http://{host}:{port}/api/main/papers", timeout=3) as response:
            refreshed = json.loads(response.read().decode("utf-8"))
        assert {row["paper_id"] for row in refreshed["papers"]} == {"live-paper", "new-paper"}

        request = Request(f"http://{host}:{port}/api/main/papers", method="POST", data=b"{}")
        try:
            urlopen(request, timeout=3)
        except HTTPError as exc:
            assert exc.code == 405
            assert exc.headers["Allow"] == "GET, HEAD"
            assert "read-only" in exc.read().decode("utf-8")
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("POST unexpectedly succeeded")
    finally:
        server.shutdown()
        server.server_close()


def test_library_view_server_serves_static_console_shell(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/", timeout=3) as response:
            html = response.read().decode("utf-8")
        assert "ScholarAIO Library" in html
        assert "Main Papers" in html
        assert "Proceedings" in html
        assert "pdf-frame" in html
        assert "Back to records" in html
        assert ">CLI<" not in html
        assert "https://" not in html
        assert "http://" not in html
        assert "tex-chtml.js" not in html
        assert "MathJax" not in html
        assert "app.js" in html
    finally:
        server.shutdown()
        server.server_close()


def test_library_view_shell_uses_compact_records_and_pdf_controls(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/", timeout=3) as response:
            html = response.read().decode("utf-8")
        assert 'id="source-copy-button"' in html
        assert 'id="pdf-fullscreen-button"' in html
        assert 'id="detail-subtitle"' not in html
        assert html.index('id="toc-list"') < html.index('id="issue-list"')
    finally:
        server.shutdown()
        server.server_close()


def test_library_view_static_assets_live_inside_package() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    static_dir = _static_dir()

    assert static_dir.is_dir()
    assert static_dir.parent == Path(__file__).resolve().parents[1] / "scholaraio" / "interfaces" / "cli"
    assert (static_dir / "index.html").is_file()
    assert (static_dir / "app.js").is_file()
    assert (static_dir / "styles.css").is_file()


def test_library_view_css_preserves_hidden_attribute_for_pdf_toolbar() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    css = (_static_dir() / "styles.css").read_text(encoding="utf-8")

    assert "[hidden]" in css
    assert "display: none !important" in css


def test_library_view_app_source_copy_fullscreen_and_compact_rows() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  const classes = new Set();
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    disabled: false,
    hidden: false,
    textContent: "",
    className: "",
    children: [],
    classList: {{
      add(name) {{ classes.add(name); }},
      remove(name) {{ classes.delete(name); }},
      contains(name) {{ return classes.has(name); }},
      toggle(name, force) {{
        const enabled = force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name);
        else classes.delete(name);
        return enabled;
      }},
    }},
    appendChild(child) {{ this.children.push(child); return child; }},
    append(...items) {{ this.children.push(...items); }},
    removeAttribute(name) {{ delete this[name]; }},
    addEventListener() {{}},
  }};
}}

const elements = new Map();
const tabs = ["main", "proceedings"].map((tab) => {{
  const el = element(`tab-${{tab}}`);
  el.dataset.tab = tab;
  return el;
}});
const document = {{
  body: element("body"),
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll(selector) {{
    if (selector === ".tab") return tabs;
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  navigator: {{ clipboard: {{ writeText: async (value) => {{ context.__copied = value; }} }} }},
  fetch: async () => ({{ ok: true, json: async () => ({{ papers: [], total: 0 }}) }}),
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
(async () => {{
  state.payload.main = {{ root: "/tmp/scholaraio/data/libraries/papers", total: 1, issue_totals: {{}} }};
  renderMetrics();
  await copySourceRoot();
  openPdf({{ pdf_url: "/api/main/pdf?id=paper-1", title: "Paper title" }});
  setPdfFullscreen(true);
  const fullscreenOn = els.tablePanel.classList.contains("is-pdf-fullscreen");
  showRecords();
  const row = {{ paper_id: "paper-1", dir_name: "Doe-2026-Paper", title: "Paper title", has_md: true }};
  state.rows.main = [row];
  renderTable();
  globalThis.__result = {{
    copied: globalThis.__copied,
    sourceCopyLabel: els.sourceCopyButton.textContent,
    fullscreenOn,
    fullscreenAfterBack: els.tablePanel.classList.contains("is-pdf-fullscreen"),
    firstTitleChildren: els.tableBody.children[0].children[0].children[0].children.length,
    metadataLabels: (() => {{
      renderMetadata({{ paper_id: "paper-1", dir_name: "Doe-2026-Paper", title: "Paper title" }});
      return els.metadataGrid.children.filter((child, index) => index % 2 === 0).map((child) => child.textContent);
    }})(),
  }};
}})();
`, context);
setImmediate(() => console.log(JSON.stringify(context.__result)));
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload["copied"] == "/tmp/scholaraio/data/libraries/papers"
    assert payload["sourceCopyLabel"] == "Copied"
    assert payload["fullscreenOn"] is True
    assert payload["fullscreenAfterBack"] is False
    assert payload["firstTitleChildren"] == 1
    assert "ID" not in payload["metadataLabels"]


def test_library_view_app_ignores_stale_refresh_and_detail_responses() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  const classes = new Set();
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    disabled: false,
    hidden: false,
    textContent: "",
    title: "",
    className: "",
    children: [],
    classList: {{
      add(name) {{ classes.add(name); }},
      remove(name) {{ classes.delete(name); }},
      contains(name) {{ return classes.has(name); }},
      toggle(name, force) {{
        const enabled = force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name);
        else classes.delete(name);
        return enabled;
      }},
    }},
    appendChild(child) {{ this.children.push(child); return child; }},
    append(...items) {{ this.children.push(...items); }},
    removeAttribute(name) {{ delete this[name]; }},
    addEventListener() {{}},
  }};
}}

const elements = new Map();
const tabs = ["main", "proceedings"].map((tab) => {{
  const el = element(`tab-${{tab}}`);
  el.dataset.tab = tab;
  return el;
}});
const document = {{
  body: element("body"),
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll(selector) {{
    if (selector === ".tab") return tabs;
    return [];
  }},
  addEventListener() {{}},
}};
const pending = [];
const context = {{
  document,
  pending,
  navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
  controlled: false,
  fetch: async (url) => {{
    if (!context.controlled) return {{ ok: true, json: async () => ({{ papers: [], total: 0, issue_totals: {{}} }}) }};
    return new Promise((resolve) => pending.push({{ url, resolve }}));
  }},
  setTimeout,
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
globalThis.__ready = (async () => {{
  controlled = true;
  state.tab = "main";
  state.rows = {{ main: [], proceedings: [] }};
  state.payload = {{ main: null, proceedings: null }};
  const staleRefresh = refreshActive({{ keepSelection: false }});
  state.tab = "proceedings";
  pending.shift().resolve({{ ok: true, json: async () => ({{
    root: "/main",
    total: 1,
    issue_totals: {{}},
    papers: [{{ paper_id: "main-paper", title: "Main paper", has_md: true }}],
  }}) }});
  await new Promise((resolve) => setTimeout(resolve, 0));
  if (pending.length) pending.shift().resolve({{ ok: true, json: async () => ({{ paper_id: "main-paper", title: "Wrong detail" }}) }});
  await staleRefresh;
  const refreshMainRows = state.rows.main.map((row) => row.paper_id);
  const refreshProceedingsRows = state.rows.proceedings.map((row) => row.paper_id);

  state.tab = "main";
  state.rows.main = [
    {{ paper_id: "first", title: "First", has_md: true }},
    {{ paper_id: "second", title: "Second", has_md: true }},
  ];
  state.selected.main = "";
  state.detail = null;
  const staleDetail = selectRow("first");
  await new Promise((resolve) => setTimeout(resolve, 0));
  state.selected.main = "second";
  pending.shift().resolve({{ ok: true, json: async () => ({{ paper_id: "first", title: "First detail" }}) }});
  await staleDetail;

  return {{
    refreshMainRows,
    refreshProceedingsRows,
    activeTab: state.tab,
    selected: state.selected.main,
    detailTitle: els.detailTitle.textContent,
    detail: state.detail,
  }};
}})();
`, context);
context.__ready.then((payload) => console.log(JSON.stringify(payload))).catch((err) => {{
  console.error(err);
  process.exit(1);
}});
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload["refreshMainRows"] == ["main-paper"]
    assert payload["refreshProceedingsRows"] == []
    assert payload["activeTab"] == "main"
    assert payload["selected"] == "second"
    assert payload["detailTitle"] != "First detail"
    assert payload["detail"] is None


def test_library_view_app_detail_failure_fallback_has_no_commands() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  const classes = new Set();
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    disabled: false,
    hidden: false,
    textContent: "",
    innerHTML: "",
    className: "",
    children: [],
    classList: {{
      add(name) {{ classes.add(name); }},
      remove(name) {{ classes.delete(name); }},
      contains(name) {{ return classes.has(name); }},
      toggle(name, force) {{
        const enabled = force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name);
        else classes.delete(name);
        return enabled;
      }},
    }},
    appendChild(child) {{ this.children.push(child); return child; }},
    append(...items) {{ this.children.push(...items); }},
    removeAttribute(name) {{ delete this[name]; }},
    addEventListener() {{}},
  }};
}}

const elements = new Map();
const tabs = ["main", "proceedings"].map((tab) => {{
  const el = element(`tab-${{tab}}`);
  el.dataset.tab = tab;
  return el;
}});
const document = {{
  body: element("body"),
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll(selector) {{
    if (selector === ".tab") return tabs;
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
  fetch: async () => ({{ ok: false, status: 500, statusText: "Boom" }}),
  setTimeout,
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
globalThis.__ready = (async () => {{
  renderDetail = (detail) => {{ globalThis.__captured = detail; }};
  state.tab = "main";
  state.rows.main = [{{ paper_id: "broken", title: "Broken", has_md: true }}];
  await selectRow("broken");
  return globalThis.__captured;
}})();
`, context);
context.__ready.then((payload) => console.log(JSON.stringify(payload))).catch((err) => {{
  console.error(err);
  process.exit(1);
}});
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload["title"] == "Detail unavailable"
    assert "commands" not in payload


def test_library_view_app_missing_markdown_status_is_not_clean() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    hidden: false,
    textContent: "",
    className: "",
    classList: {{ toggle() {{}}, add() {{}}, remove() {{}} }},
    appendChild() {{}},
    append() {{}},
    removeAttribute() {{}},
    addEventListener() {{}},
  }};
}}
const elements = new Map();
const document = {{
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll() {{
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
  fetch: async () => ({{ ok: true, json: async () => ({{ papers: [], total: 0, issue_totals: {{}} }}) }}),
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
globalThis.__result = statusPills({{ has_md: false, issue_counts: {{}} }}).map((pill) => pill[0]);
`, context);
console.log(JSON.stringify(context.__result));
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(result.stdout) == ["No MD"]


def test_library_view_app_renders_markdown_and_math_in_detail_text() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    abstract = json.dumps("Flow **energy** is $E_i = mc^2$. <script>alert(1)</script>")
    conclusion = json.dumps(r"Conclusion with $$\alpha + \beta$$.")
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    hidden: false,
    textContent: "",
    innerHTML: "",
    className: "",
    classList: {{ toggle() {{}}, add() {{}}, remove() {{}} }},
    children: [],
    appendChild(child) {{ this.children.push(child); return child; }},
    append(...items) {{ this.children.push(...items); }},
    removeAttribute() {{}},
    addEventListener() {{}},
  }};
}}
const elements = new Map();
const document = {{
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll() {{
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  __abstract: {abstract},
  __conclusion: {conclusion},
  navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
  fetch: async () => ({{ ok: true, json: async () => ({{ papers: [], total: 0, issue_totals: {{}} }}) }}),
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
renderDetail({{
  title: "Formula paper",
  abstract: globalThis.__abstract,
  l3_conclusion: globalThis.__conclusion
}});
globalThis.__result = {{
  abstractHtml: els.detailAbstract.innerHTML,
  conclusionHtml: els.detailConclusion.innerHTML,
}};
`, context);
setImmediate(() => console.log(JSON.stringify(context.__result)));
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert "<strong>energy</strong>" in payload["abstractHtml"]
    assert '<span class="math math-inline"' in payload["abstractHtml"]
    assert "E<sub>i</sub> = mc<sup>2</sup>" in payload["abstractHtml"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in payload["abstractHtml"]
    assert '<span class="math math-display"' in payload["conclusionHtml"]
    assert "α + β" in payload["conclusionHtml"]


def test_library_view_app_treats_single_newlines_as_soft_breaks_in_detail_text() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    abstract = json.dumps("We estimate\n$E_i = mc^2$\nfrom extracted features.")
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    hidden: false,
    textContent: "",
    innerHTML: "",
    className: "",
    classList: {{ toggle() {{}}, add() {{}}, remove() {{}} }},
    children: [],
    appendChild(child) {{ this.children.push(child); return child; }},
    append(...items) {{ this.children.push(...items); }},
    removeAttribute() {{}},
    addEventListener() {{}},
  }};
}}
const elements = new Map();
const document = {{
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll() {{
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  __abstract: {abstract},
  navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
  fetch: async () => ({{ ok: true, json: async () => ({{ papers: [], total: 0, issue_totals: {{}} }}) }}),
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
renderDetail({{
  title: "Wrapped formula paper",
  abstract: globalThis.__abstract,
  l3_conclusion: ""
}});
globalThis.__result = els.detailAbstract.innerHTML;
`, context);
console.log(JSON.stringify(context.__result));
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    html = json.loads(result.stdout)
    assert "<br>" not in html
    assert "We estimate " in html
    assert '<span class="math math-inline"' in html
    assert "E<sub>i</sub> = mc<sup>2</sup>" in html
    assert " from extracted features." in html


def test_library_view_css_only_scrolls_display_math() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    css = (_static_dir() / "styles.css").read_text(encoding="utf-8")

    assert ".math-display" in css
    assert "overflow-x: auto" in css
    assert ".math-inline {\n  display: inline;" in css
    assert "mjx-container" not in css


def test_library_view_tab_switch_resets_stale_type_filter() -> None:
    from scholaraio.interfaces.cli.gui import _static_dir

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for app.js behavior regression")
    app_js = (_static_dir() / "app.js").as_posix()
    script = f"""
const fs = require("fs");
const vm = require("vm");

function element(id) {{
  return {{
    id,
    dataset: {{}},
    value: "",
    checked: false,
    hidden: false,
    textContent: "",
    className: "",
    classList: {{ toggle() {{}} }},
    appendChild() {{}},
    append() {{}},
    removeAttribute() {{}},
    addEventListener() {{}},
  }};
}}

const elements = new Map();
const tabs = ["main", "proceedings"].map((tab) => {{
  const el = element(`tab-${{tab}}`);
  el.dataset.tab = tab;
  return el;
}});
const document = {{
  getElementById(id) {{
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  }},
  createElement(tag) {{
    return element(tag);
  }},
  querySelectorAll(selector) {{
    if (selector === ".tab") return tabs;
    return [];
  }},
  addEventListener() {{}},
}};
const context = {{
  document,
  fetch: async () => ({{ ok: true, json: async () => ({{ papers: [], total: 0 }}) }}),
  setInterval: () => 1,
  clearInterval: () => {{}},
  console,
}};
const code = fs.readFileSync({json.dumps(app_js)}, "utf8");
vm.runInNewContext(`${{code}}
state.filters.type = "journal-article";
els.typeFilter.value = "journal-article";
switchTab("proceedings");
globalThis.__result = {{ type: state.filters.type, select: els.typeFilter.value }};
`, context);
console.log(JSON.stringify(context.__result));
"""

    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(result.stdout) == {"type": "", "select": ""}


def test_library_view_capabilities_are_per_server_and_loopback_aware(tmp_path):
    cfg = _build_config({}, tmp_path)

    with _running_library_server(cfg) as (_server, base_url):
        payload, _headers = _json_response(f"{base_url}/api/capabilities")
    with _running_library_server(cfg) as (_server, second_base_url):
        second, _headers = _json_response(f"{second_base_url}/api/capabilities")

    assert payload["csrf_token"]
    assert payload["csrf_token"] != second["csrf_token"]
    assert payload["native_pdf_open"] == {"enabled": True, "reason": ""}
    assert payload["search_modes"] == {
        "main": ["metadata", "keyword", "semantic", "unified"],
        "proceedings": ["metadata"],
    }

    with _running_library_server(cfg, host="0.0.0.0") as (_server, wildcard_base_url):
        wildcard, _headers = _json_response(f"{wildcard_base_url}/api/capabilities")
    assert wildcard["native_pdf_open"]["enabled"] is False
    assert "loopback" in wildcard["native_pdf_open"]["reason"].lower()


def test_library_view_bibtex_endpoints_use_canonical_metadata(tmp_path):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with _running_library_server(cfg) as (_server, base_url):
        main, _headers = _json_response(f"{base_url}/api/main/bibtex?id=action-paper")
        proceedings, _headers = _json_response(f"{base_url}/api/proceedings/bibtex?id=proceeding-action-paper")

    assert main["paper_id"] == "action-paper"
    assert main["bibtex"].startswith("@article{")
    assert "author = {Jane Doe}" in main["bibtex"]
    assert "abstract = {{Canonical abstract.}}" in main["bibtex"]
    assert proceedings["paper_id"] == "proceeding-action-paper"
    assert proceedings["bibtex"].startswith("@inproceedings{")
    assert "booktitle = {Proceedings of Actions}" in proceedings["bibtex"]


def test_library_view_ranked_search_endpoint_parses_structured_filters(tmp_path, monkeypatch):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)
    captured: dict[str, object] = {}

    def fake_search(cfg_arg, *, query, mode, filters, limit):
        captured.update(cfg=cfg_arg, query=query, mode=mode, filters=filters, limit=limit)
        return {
            "mode": mode,
            "query": query,
            "total": 1,
            "results": [
                {
                    "paper_id": "action-paper",
                    "rank": 1,
                    "score": 0.03,
                    "match": "both",
                }
            ],
            "diagnostics": {
                "status": "ok",
                "message": "Both legs active.",
                "keyword": "available",
                "semantic": "available",
                "actions": [],
            },
        }

    monkeypatch.setattr("scholaraio.services.library_search.search_main_library", fake_search)
    query = urlencode(
        {
            "mode": "unified",
            "q": "reacting flow",
            "title": "Action",
            "author": "Doe",
            "year_from": "2020",
            "year_to": "2026",
            "journal": "Actions",
            "paper_type": "journal-article",
            "doi": "10.1000/action",
            "limit": "75",
        }
    )

    with _running_library_server(cfg) as (_server, base_url):
        payload, _headers = _json_response(f"{base_url}/api/main/search?{query}")

    assert payload["results"][0]["paper_id"] == "action-paper"
    assert captured["cfg"] is cfg
    assert captured["query"] == "reacting flow"
    assert captured["mode"] == "unified"
    assert captured["limit"] == 75
    filters = captured["filters"]
    assert filters.title == "Action"
    assert filters.author == "Doe"
    assert filters.year_from == 2020
    assert filters.year_to == 2026
    assert filters.journal == "Actions"
    assert filters.paper_type == "journal-article"
    assert filters.doi == "10.1000/action"


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ({"mode": "metadata", "q": "test"}, "invalid_search_mode"),
        ({"mode": "keyword", "q": "test", "year_from": "not-a-year"}, "invalid_year"),
        ({"mode": "keyword", "q": "test", "limit": "many"}, "invalid_search_limit"),
    ],
)
def test_library_view_ranked_search_rejects_invalid_requests(tmp_path, query, code):
    cfg = _build_config({}, tmp_path)

    with _running_library_server(cfg) as (_server, base_url):
        with pytest.raises(HTTPError) as caught:
            urlopen(f"{base_url}/api/main/search?{urlencode(query)}", timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == HTTPStatus.BAD_REQUEST
    assert payload["code"] == code


def test_library_view_responses_include_browser_security_headers(tmp_path):
    cfg = _build_config({}, tmp_path)
    required = {
        "Content-Security-Policy": "default-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
    }

    with _running_library_server(cfg) as (_server, base_url):
        for path in ("/", "/api/health"):
            with urlopen(f"{base_url}{path}", timeout=3) as response:
                response.read()
                for name, expected in required.items():
                    assert expected in response.headers[name]
            assert "Access-Control-Allow-Origin" not in response.headers


def test_library_view_native_open_uses_canonical_pdf_path(tmp_path):
    cfg, main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            {"id": "action-paper"},
            token=capabilities["csrf_token"],
            origin=base_url,
        )
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert payload == {"status": "opened", "paper_id": "action-paper"}
    open_default.assert_called_once_with((main_dir / "Doe-2026-Action.pdf").resolve())


def test_library_view_native_open_supports_proceedings_child_pdf(tmp_path):
    cfg, _main_dir, child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/proceedings/open-pdf",
            {"id": "proceeding-action-paper"},
            token=capabilities["csrf_token"],
            origin=base_url,
        )
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert payload == {"status": "opened", "paper_id": "proceeding-action-paper"}
    open_default.assert_called_once_with((child_dir / "Roe-2026-Proceeding.pdf").resolve())


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_library_view_native_open_rejects_non_post_methods(tmp_path, method):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with _running_library_server(cfg) as (_server, base_url):
        request = Request(
            f"{base_url}/api/main/open-pdf",
            method=method,
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)

    assert caught.value.code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.parametrize(
    ("token_kind", "origin_kind"),
    [
        ("missing", "valid"),
        ("wrong", "valid"),
        ("valid", "missing"),
        ("valid", "cross-origin"),
    ],
)
def test_library_view_native_open_rejects_csrf_and_cross_origin(
    tmp_path,
    token_kind,
    origin_kind,
):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        token = capabilities["csrf_token"] if token_kind == "valid" else ""
        if token_kind == "wrong":
            token = "wrong-token"
        origin = base_url if origin_kind == "valid" else ""
        if origin_kind == "cross-origin":
            origin = "https://attacker.example"
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            {"id": "action-paper"},
            token=token,
            origin=origin,
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == HTTPStatus.FORBIDDEN
    assert payload["code"] in {"csrf_rejected", "origin_rejected"}
    open_default.assert_not_called()


def test_library_view_native_open_is_disabled_for_non_loopback_bind(tmp_path):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg, host="0.0.0.0") as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            {"id": "action-paper"},
            token=capabilities["csrf_token"],
            origin=base_url,
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == HTTPStatus.FORBIDDEN
    assert payload["code"] == "native_open_disabled"
    open_default.assert_not_called()


@pytest.mark.parametrize(
    ("payload", "content_type", "expected_status", "expected_code"),
    [
        (
            {"id": "action-paper", "path": "/etc/passwd"},
            "application/json",
            HTTPStatus.BAD_REQUEST,
            "invalid_request_body",
        ),
        (
            {"id": "action-paper"},
            "text/plain",
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "unsupported_media_type",
        ),
    ],
)
def test_library_view_native_open_validates_request_schema(
    tmp_path,
    payload,
    content_type,
    expected_status,
    expected_code,
):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            payload,
            token=capabilities["csrf_token"],
            origin=base_url,
            content_type=content_type,
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        response_payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == expected_status
    assert response_payload["code"] == expected_code
    open_default.assert_not_called()


def test_library_view_native_open_rejects_oversized_json(tmp_path):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with _running_library_server(cfg) as (_server, base_url):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = Request(
            f"{base_url}/api/main/open-pdf",
            method="POST",
            data=b"{" + b"x" * (70 * 1024) + b"}",
            headers={
                "Content-Type": "application/json",
                "X-ScholarAIO-CSRF": capabilities["csrf_token"],
                "Origin": base_url,
            },
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert payload["code"] == "request_too_large"


@pytest.mark.parametrize(
    ("paper_id", "with_pdf", "expected_status", "expected_code"),
    [
        ("missing-paper", True, HTTPStatus.NOT_FOUND, "paper_not_found"),
        ("action-paper", False, HTTPStatus.NOT_FOUND, "pdf_not_found"),
    ],
)
def test_library_view_native_open_reports_missing_records_and_pdfs(
    tmp_path,
    paper_id,
    with_pdf,
    expected_status,
    expected_code,
):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path, main_pdf=with_pdf)

    with (
        patch("scholaraio.services.system_open.open_with_default_application") as open_default,
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            {"id": paper_id},
            token=capabilities["csrf_token"],
            origin=base_url,
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == expected_status
    assert payload["code"] == expected_code
    open_default.assert_not_called()


def test_library_view_native_open_reports_controlled_launcher_failure(tmp_path):
    from scholaraio.services.system_open import DefaultApplicationOpenError

    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        patch(
            "scholaraio.services.system_open.open_with_default_application",
            side_effect=DefaultApplicationOpenError("desktop unavailable"),
        ),
        _running_library_server(cfg) as (_server, base_url),
    ):
        capabilities, _headers = _json_response(f"{base_url}/api/capabilities")
        request = _post_json(
            f"{base_url}/api/main/open-pdf",
            {"id": "action-paper"},
            token=capabilities["csrf_token"],
            origin=base_url,
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
        payload = json.loads(caught.value.read().decode("utf-8"))

    assert caught.value.code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert payload["code"] == "native_open_failed"
    assert "desktop unavailable" in payload["error"]


def test_library_view_server_serves_main_pdf_inline(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    paper_dir = tmp_path / "data" / "libraries" / "papers" / "Doe-2026-PDF"
    paper_dir.mkdir(parents=True)
    (paper_dir / "meta.json").write_text(
        json.dumps({"id": "pdf-paper", "title": "PDF paper", "authors": ["Jane Doe"], "year": 2026}),
        encoding="utf-8",
    )
    (paper_dir / "Doe-2026-PDF.pdf").write_bytes(b"%PDF-inline")

    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/api/main/pdf?id=pdf-paper", timeout=3) as response:
            body = response.read()
            content_type = response.headers["Content-Type"]
            disposition = response.headers["Content-Disposition"]
        assert body == b"%PDF-inline"
        assert content_type == "application/pdf"
        assert "inline" in disposition
        assert "Doe-2026-PDF.pdf" in disposition
    finally:
        server.shutdown()
        server.server_close()


def test_library_view_inline_pdf_security_headers_allow_same_origin_frame(tmp_path):
    cfg, _main_dir, _child_dir = _write_gui_action_fixtures(tmp_path)

    with (
        _running_library_server(cfg) as (_server, base_url),
        urlopen(f"{base_url}/api/main/pdf?id=action-paper", timeout=3) as response,
    ):
        response.read()
        headers = response.headers

    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]


def test_library_view_server_serves_non_ascii_pdf_filename(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    paper_dir = tmp_path / "data" / "libraries" / "papers" / "王-2026-中文论文"
    paper_dir.mkdir(parents=True)
    (paper_dir / "meta.json").write_text(
        json.dumps({"id": "cn-pdf", "title": "中文论文", "authors": ["王"], "year": 2026}, ensure_ascii=False),
        encoding="utf-8",
    )
    (paper_dir / "王-2026-中文论文.pdf").write_bytes(b"%PDF-cn")

    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/api/main/pdf?id=cn-pdf", timeout=3) as response:
            body = response.read()
            disposition = response.headers["Content-Disposition"]
        assert body == b"%PDF-cn"
        assert 'filename="paper.pdf"' in disposition
        assert "filename*=UTF-8''%E7%8E%8B-2026-%E4%B8%AD%E6%96%87%E8%AE%BA%E6%96%87.pdf" in disposition
    finally:
        server.shutdown()
        server.server_close()


def test_library_view_pdf_errors_do_not_send_ok_before_file_check():
    from scholaraio.interfaces.cli.gui import LibraryViewRequestHandler

    class MissingPdf:
        name = "missing.pdf"

        def stat(self):
            raise FileNotFoundError("missing")

        def open(self, _mode):
            raise AssertionError("open should not run after failed stat")

    class UnreadablePdf:
        name = "locked.pdf"

        def stat(self):
            return SimpleNamespace(st_size=1)

        def open(self, _mode):
            raise PermissionError("locked")

    for pdf_path, expected_status in [
        (MissingPdf(), HTTPStatus.NOT_FOUND),
        (UnreadablePdf(), HTTPStatus.INTERNAL_SERVER_ERROR),
    ]:
        handler = LibraryViewRequestHandler.__new__(LibraryViewRequestHandler)
        statuses: list[HTTPStatus] = []
        handler.command = "GET"
        handler.wfile = io.BytesIO()
        handler.send_response = statuses.append
        handler.send_header = lambda *_args, **_kwargs: None
        handler.end_headers = lambda: None

        def record_error(status, _message, headers=None, *, statuses=statuses):
            statuses.append(status)

        handler._send_error_json = record_error

        with suppress(FileNotFoundError, PermissionError):
            handler._send_pdf(pdf_path)  # type: ignore[arg-type]

        assert HTTPStatus.OK not in statuses
        assert statuses == [expected_status]


def test_pdf_content_disposition_uses_ascii_fallback_and_strips_line_breaks():
    from scholaraio.interfaces.cli.gui import _pdf_content_disposition

    disposition = _pdf_content_disposition('坏\r\nName".pdf')

    assert "\r" not in disposition
    assert "\n" not in disposition
    assert 'filename="paper.pdf"' in disposition
    assert "filename*=UTF-8''%E5%9D%8F__Name_.pdf" in disposition


def test_library_view_rejected_write_methods_close_connection():
    from scholaraio.interfaces.cli.gui import LibraryViewRequestHandler

    handler = LibraryViewRequestHandler.__new__(LibraryViewRequestHandler)
    captured: dict[str, object] = {}
    handler.close_connection = False
    handler.headers = {"Content-Length": "7"}
    handler.rfile = io.BytesIO(b"payload")
    handler._send_error_json = lambda status, message, headers=None: captured.update(
        {"status": status, "message": message, "headers": headers or {}}
    )

    handler.do_POST()

    assert handler.close_connection is True
    assert captured["status"] == HTTPStatus.METHOD_NOT_ALLOWED
    assert captured["headers"] == {"Allow": "GET, HEAD", "Connection": "close"}


def test_browser_url_uses_loopback_for_wildcard_bind_hosts():
    from scholaraio.interfaces.cli.gui import _browser_url

    assert _browser_url("0.0.0.0", 8765) == "http://127.0.0.1:8765"
    assert _browser_url("::", 8765) == "http://127.0.0.1:8765"
    assert _browser_url("", 8765) == "http://127.0.0.1:8765"
    assert _browser_url("127.0.0.1", 8765) == "http://127.0.0.1:8765"
    assert _browser_url("::1", 8765) == "http://[::1]:8765"


def test_library_view_server_head_pdf_does_not_read_body(tmp_path):
    from scholaraio.interfaces.cli.gui import create_library_view_server

    cfg = _build_config({}, tmp_path)
    paper_dir = tmp_path / "data" / "libraries" / "papers" / "Doe-2026-Head-PDF"
    paper_dir.mkdir(parents=True)
    (paper_dir / "meta.json").write_text(
        json.dumps({"id": "head-pdf", "title": "Head PDF", "authors": ["Jane Doe"], "year": 2026}),
        encoding="utf-8",
    )
    (paper_dir / "Doe-2026-Head-PDF.pdf").write_bytes(b"%PDF-head")

    server = create_library_view_server(cfg, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.object(Path, "read_bytes", side_effect=AssertionError("PDF body should not be buffered")):
            request = Request(f"http://{host}:{port}/api/main/pdf?id=head-pdf", method="HEAD")
            with urlopen(request, timeout=3) as response:
                body = response.read()
                content_type = response.headers["Content-Type"]
                length = response.headers["Content-Length"]
        assert body == b""
        assert content_type == "application/pdf"
        assert length == str(len(b"%PDF-head"))
    finally:
        server.shutdown()
        server.server_close()


def test_cmd_gui_delegates_to_read_only_server(monkeypatch, tmp_path):
    from scholaraio.interfaces.cli.gui import cmd_gui

    seen = {}

    def fake_serve(cfg, *, host, port, open_browser):
        seen["cfg"] = cfg
        seen["host"] = host
        seen["port"] = port
        seen["open_browser"] = open_browser

    monkeypatch.setattr("scholaraio.interfaces.cli.gui.serve_library_view", fake_serve)
    cfg = _build_config({}, tmp_path)

    cmd_gui(SimpleNamespace(host="127.0.0.1", port=18888, no_open=True), cfg)

    assert seen == {"cfg": cfg, "host": "127.0.0.1", "port": 18888, "open_browser": False}
