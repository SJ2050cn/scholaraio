const POLL_MS = 2200;

const state = {
  tab: "main",
  rows: { main: [], proceedings: [] },
  payload: { main: null, proceedings: null },
  detail: null,
  selected: { main: "", proceedings: "" },
  sortKey: "year",
  sortDir: "desc",
  searchMode: "metadata",
  ranked: null,
  searchRequestSeq: 0,
  searchBusy: false,
  capabilities: {
    csrfToken: "",
    nativePdfOpen: false,
    nativePdfReason: "Checking local capabilities…",
  },
  pdf: null,
  pdfFullscreen: false,
  detailRequestSeq: 0,
  refreshRequestSeq: { main: 0, proceedings: 0 },
  filters: {
    search: "",
    title: "",
    author: "",
    yearFrom: "",
    yearTo: "",
    journal: "",
    doi: "",
    type: "",
    volume: "",
    issues: false,
    missingMd: false,
  },
  pollTimer: null,
};

const els = {
  connectionDot: document.getElementById("connection-dot"),
  connectionLabel: document.getElementById("connection-label"),
  updatedAt: document.getElementById("updated-at"),
  sourceTitle: document.getElementById("source-title"),
  sourceRoot: document.getElementById("source-root"),
  sourceCopyButton: document.getElementById("source-copy-button"),
  metricTotal: document.getElementById("metric-total"),
  metricErrors: document.getElementById("metric-errors"),
  metricWarnings: document.getElementById("metric-warnings"),
  tableCount: document.getElementById("table-count"),
  recordsToolbarTitle: document.getElementById("records-toolbar-title"),
  tablePanel: document.getElementById("table-panel"),
  recordsView: document.getElementById("records-view"),
  pdfToolbarTitle: document.getElementById("pdf-toolbar-title"),
  pdfBackButton: document.getElementById("pdf-back-button"),
  pdfFullscreenButton: document.getElementById("pdf-fullscreen-button"),
  pdfTitle: document.getElementById("pdf-title"),
  pdfViewer: document.getElementById("pdf-viewer"),
  pdfFrame: document.getElementById("pdf-frame"),
  tableBody: document.getElementById("paper-table-body"),
  emptyState: document.getElementById("empty-state"),
  searchInput: document.getElementById("search-input"),
  searchMode: document.getElementById("search-mode"),
  searchButton: document.getElementById("search-button"),
  searchDiagnostics: document.getElementById("search-diagnostics"),
  clearFiltersButton: document.getElementById("clear-filters-button"),
  activeFilterCount: document.getElementById("active-filter-count"),
  titleFilter: document.getElementById("title-filter"),
  authorFilter: document.getElementById("author-filter"),
  yearFromFilter: document.getElementById("year-from-filter"),
  yearToFilter: document.getElementById("year-to-filter"),
  journalFilter: document.getElementById("journal-filter"),
  doiFilter: document.getElementById("doi-filter"),
  typeFilter: document.getElementById("type-filter"),
  volumeFilter: document.getElementById("volume-filter"),
  volumeFilterLabel: document.getElementById("volume-filter-label"),
  filterIssues: document.getElementById("filter-issues"),
  filterMissingMd: document.getElementById("filter-missing-md"),
  refreshButton: document.getElementById("refresh-button"),
  detailTitle: document.getElementById("detail-title"),
  detailActions: document.getElementById("detail-actions"),
  copyBibtexButton: document.getElementById("copy-bibtex-button"),
  previewPdfButton: document.getElementById("preview-pdf-button"),
  nativePdfButton: document.getElementById("native-pdf-button"),
  metadataGrid: document.getElementById("metadata-grid"),
  issueList: document.getElementById("issue-list"),
  detailAbstract: document.getElementById("detail-abstract"),
  detailConclusion: document.getElementById("detail-conclusion"),
  tocList: document.getElementById("toc-list"),
  toast: document.getElementById("toast"),
};

function text(value, fallback = "--") {
  const string = String(value ?? "").trim();
  return string || fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function findUnescaped(input, token, start) {
  let index = start;
  while (index < input.length) {
    index = input.indexOf(token, index);
    if (index === -1) return -1;
    let backslashes = 0;
    for (let i = index - 1; i >= 0 && input[i] === "\\"; i -= 1) backslashes += 1;
    if (backslashes % 2 === 0) return index;
    index += token.length;
  }
  return -1;
}

const LATEX_SYMBOLS = {
  alpha: "α",
  beta: "β",
  gamma: "γ",
  delta: "δ",
  epsilon: "ε",
  varepsilon: "ε",
  zeta: "ζ",
  eta: "η",
  theta: "θ",
  vartheta: "ϑ",
  iota: "ι",
  kappa: "κ",
  lambda: "λ",
  mu: "μ",
  nu: "ν",
  xi: "ξ",
  pi: "π",
  rho: "ρ",
  sigma: "σ",
  tau: "τ",
  upsilon: "υ",
  phi: "φ",
  varphi: "φ",
  chi: "χ",
  psi: "ψ",
  omega: "ω",
  Gamma: "Γ",
  Delta: "Δ",
  Theta: "Θ",
  Lambda: "Λ",
  Xi: "Ξ",
  Pi: "Π",
  Sigma: "Σ",
  Phi: "Φ",
  Psi: "Ψ",
  Omega: "Ω",
  partial: "∂",
  nabla: "∇",
  infty: "∞",
  sum: "∑",
  prod: "∏",
  int: "∫",
  times: "×",
  cdot: "·",
  pm: "±",
  mp: "∓",
  le: "≤",
  leq: "≤",
  ge: "≥",
  geq: "≥",
  neq: "≠",
  approx: "≈",
  sim: "∼",
  propto: "∝",
  to: "→",
  rightarrow: "→",
  leftarrow: "←",
  leftrightarrow: "↔",
  degree: "°",
};

function splitMathSegments(input) {
  const segments = [];
  let start = 0;
  let i = 0;
  while (i < input.length) {
    let end = -1;
    let tokenLength = 0;
    if (input.startsWith("$$", i)) {
      end = findUnescaped(input, "$$", i + 2);
      tokenLength = 2;
    } else if (input.startsWith("\\[", i)) {
      end = findUnescaped(input, "\\]", i + 2);
      tokenLength = 2;
    } else if (input.startsWith("\\(", i)) {
      end = findUnescaped(input, "\\)", i + 2);
      tokenLength = 2;
    } else if (input[i] === "$" && input[i + 1] !== "$") {
      end = findUnescaped(input, "$", i + 1);
      tokenLength = 1;
    }
    if (end === -1) {
      i += 1;
      continue;
    }
    const close = end + tokenLength;
    if (i > start) segments.push({ kind: "text", value: input.slice(start, i) });
    segments.push({ kind: "math", value: input.slice(i, close) });
    i = close;
    start = close;
  }
  if (start < input.length) segments.push({ kind: "text", value: input.slice(start) });
  return segments;
}

function stripMathDelimiters(value) {
  if (value.startsWith("$$") && value.endsWith("$$")) {
    return { body: value.slice(2, -2), display: true };
  }
  if (value.startsWith("\\[") && value.endsWith("\\]")) {
    return { body: value.slice(2, -2), display: true };
  }
  if (value.startsWith("\\(") && value.endsWith("\\)")) {
    return { body: value.slice(2, -2), display: false };
  }
  if (value.startsWith("$") && value.endsWith("$")) {
    return { body: value.slice(1, -1), display: false };
  }
  return { body: value, display: false };
}

function skipSpaces(input, index) {
  let i = index;
  while (i < input.length && /\s/.test(input[i])) i += 1;
  return i;
}

function readGroup(input, index) {
  const start = skipSpaces(input, index);
  if (input[start] !== "{") return null;
  let depth = 1;
  let i = start + 1;
  while (i < input.length) {
    if (input[i] === "\\" && i + 1 < input.length) {
      i += 2;
      continue;
    }
    if (input[i] === "{") depth += 1;
    else if (input[i] === "}") {
      depth -= 1;
      if (depth === 0) return { value: input.slice(start + 1, i), end: i + 1 };
    }
    i += 1;
  }
  return null;
}

function readScriptValue(input, index) {
  const group = readGroup(input, index);
  if (group) return group;
  const start = skipSpaces(input, index);
  if (start >= input.length) return { value: "", end: start };
  if (input[start] === "\\") {
    let end = start + 1;
    while (end < input.length && /[A-Za-z]/.test(input[end])) end += 1;
    return { value: input.slice(start, end), end };
  }
  return { value: input[start], end: start + 1 };
}

function appendScripts(baseHtml, input, index) {
  let html = baseHtml;
  let i = index;
  while (i < input.length && (input[i] === "_" || input[i] === "^")) {
    const tag = input[i] === "_" ? "sub" : "sup";
    const value = readScriptValue(input, i + 1);
    html += `<${tag}>${renderMathExpression(value.value)}</${tag}>`;
    i = value.end;
  }
  return { html, end: i };
}

function renderMathExpression(raw) {
  const input = String(raw ?? "").replace(/\s+/g, " ").trim();
  let html = "";
  let i = 0;
  while (i < input.length) {
    if (/\s/.test(input[i])) {
      html += " ";
      i += 1;
      continue;
    }
    if (input[i] === "\\" && /[A-Za-z]/.test(input[i + 1] || "")) {
      let end = i + 1;
      while (end < input.length && /[A-Za-z]/.test(input[end])) end += 1;
      const command = input.slice(i + 1, end);
      if (command === "frac") {
        const numerator = readGroup(input, end);
        const denominator = numerator ? readGroup(input, numerator.end) : null;
        if (numerator && denominator) {
          html += `<span class="math-frac"><span>${renderMathExpression(numerator.value)}</span><span>${renderMathExpression(denominator.value)}</span></span>`;
          i = denominator.end;
          continue;
        }
      }
      if (command === "sqrt") {
        const radicand = readGroup(input, end);
        if (radicand) {
          const scripted = appendScripts(
            `<span class="math-root"><span class="math-root-symbol">√</span><span>${renderMathExpression(radicand.value)}</span></span>`,
            input,
            radicand.end,
          );
          html += scripted.html;
          i = scripted.end;
          continue;
        }
      }
      if (["mathrm", "mathit", "mathbf", "text", "operatorname"].includes(command)) {
        const group = readGroup(input, end);
        if (group) {
          const rendered = command === "mathbf" ? `<strong>${renderMathExpression(group.value)}</strong>` : renderMathExpression(group.value);
          const scripted = appendScripts(rendered, input, group.end);
          html += scripted.html;
          i = scripted.end;
          continue;
        }
      }
      if (["left", "right"].includes(command)) {
        i = end;
        continue;
      }
      const symbol = LATEX_SYMBOLS[command] || command;
      const scripted = appendScripts(escapeHtml(symbol), input, end);
      html += scripted.html;
      i = scripted.end;
      continue;
    }
    if (input[i] === "\\" && [",", ";", ":", "!"].includes(input[i + 1])) {
      html += input[i + 1] === "!" ? "" : " ";
      i += 2;
      continue;
    }
    if (input[i] === "{" || input[i] === "}") {
      i += 1;
      continue;
    }
    const word = input.slice(i).match(/^[\p{L}\p{N}]+/u);
    if (word) {
      const scripted = appendScripts(escapeHtml(word[0]), input, i + word[0].length);
      html += scripted.html;
      i = scripted.end;
      continue;
    }
    const scripted = appendScripts(escapeHtml(input[i]), input, i + 1);
    html += scripted.html;
    i = scripted.end;
  }
  return html.trim();
}

function renderMathSegment(value) {
  const { body, display } = stripMathDelimiters(value);
  const className = display ? "math math-display" : "math math-inline";
  return `<span class="${className}" aria-label="${escapeHtml(body)}">${renderMathExpression(body)}</span>`;
}

function renderInlineText(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\b_([^_\n]+)_\b/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
}

function renderInlineMarkdown(value) {
  return splitMathSegments(value)
    .map((segment) => {
      if (segment.kind === "math") return renderMathSegment(segment.value);
      return renderInlineText(segment.value);
    })
    .join("");
}

function markdownToHtml(value) {
  const lines = String(value ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let paragraph = [];
  let list = [];
  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(`<p>${renderInlineMarkdown(paragraph.map((line) => line.trim()).join(" "))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    blocks.push(`<ul>${list.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }
    const bullet = trimmed.match(/^[-*+]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      list.push(bullet[1]);
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}

function renderMarkdown(container, value) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    container.textContent = "--";
    return;
  }
  container.innerHTML = markdownToHtml(raw);
}

function formatDate(iso) {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function setConnection(kind, label) {
  els.connectionDot.classList.toggle("live", kind === "live");
  els.connectionDot.classList.toggle("error", kind === "error");
  els.connectionLabel.textContent = label;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  if (!response.ok) {
    let message = `${response.status || ""} ${response.statusText || "Request failed"}`.trim();
    try {
      const payload = await response.json();
      if (payload?.error) message = payload.error;
    } catch (_err) {
      // Keep the HTTP fallback when an error body is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

async function loadCapabilities() {
  try {
    const payload = await fetchJson("/api/capabilities");
    state.capabilities = {
      csrfToken: String(payload?.csrf_token || ""),
      nativePdfOpen: Boolean(payload?.native_pdf_open?.enabled),
      nativePdfReason: String(payload?.native_pdf_open?.reason || ""),
    };
  } catch (_err) {
    state.capabilities = {
      csrfToken: "",
      nativePdfOpen: false,
      nativePdfReason: "Native PDF launch capability could not be verified.",
    };
  }
  if (state.detail) renderDetailActions(state.detail);
}

function activePayload() {
  return state.payload[state.tab];
}

function activeRows() {
  return state.rows[state.tab] || [];
}

function issueTotal(row) {
  const counts = row.issue_counts || {};
  return Number(counts.error || 0) + Number(counts.warning || 0) + Number(counts.info || 0);
}

function includesFold(value, query) {
  return String(value ?? "").toLocaleLowerCase().includes(String(query ?? "").toLocaleLowerCase());
}

function rowMatches(row) {
  const q = state.filters.search.trim();
  if (q && state.searchMode === "metadata") {
    const haystack = [
      row.title,
      row.authors_text,
      row.journal,
      row.doi,
      row.paper_id,
      row.dir_name,
      row.proceeding_title,
    ].join(" ");
    if (!includesFold(haystack, q)) return false;
  }
  if (state.filters.title && !includesFold(row.title, state.filters.title)) return false;
  if (state.filters.author && !includesFold(row.authors_text, state.filters.author)) return false;
  if (state.filters.journal) {
    const source = [row.journal, row.proceeding_title].filter(Boolean).join(" ");
    if (!includesFold(source, state.filters.journal)) return false;
  }
  if (state.filters.doi && !includesFold(row.doi, state.filters.doi)) return false;
  const year = Number(row.year);
  const yearFrom = Number(state.filters.yearFrom);
  const yearTo = Number(state.filters.yearTo);
  if (state.filters.yearFrom && (!Number.isFinite(year) || year < yearFrom)) return false;
  if (state.filters.yearTo && (!Number.isFinite(year) || year > yearTo)) return false;
  if (state.filters.type && row.paper_type !== state.filters.type) return false;
  if (state.filters.volume && row.proceeding_title !== state.filters.volume) return false;
  if (state.filters.issues && issueTotal(row) === 0) return false;
  if (state.filters.missingMd && row.has_md) return false;
  return true;
}

function compareRows(a, b) {
  if (state.sortKey === "relevance") {
    const aRank = rankingFor(a.paper_id)?.rank ?? Number.MAX_SAFE_INTEGER;
    const bRank = rankingFor(b.paper_id)?.rank ?? Number.MAX_SAFE_INTEGER;
    return aRank - bRank;
  }
  const av = a[state.sortKey] ?? "";
  const bv = b[state.sortKey] ?? "";
  const an = Number(av);
  const bn = Number(bv);
  let result;
  if (Number.isFinite(an) && Number.isFinite(bn)) result = an - bn;
  else result = String(av).localeCompare(String(bv));
  return state.sortDir === "asc" ? result : -result;
}

function filteredRows() {
  let rows = activeRows().filter(rowMatches);
  if (state.ranked) {
    rows = rows.filter((row) => state.ranked.byId.has(row.paper_id));
  }
  return rows.sort(compareRows);
}

function rankingFor(paperId) {
  return state.ranked?.byId?.get(paperId) || null;
}

function syncFiltersFromControls() {
  state.filters.search = els.searchInput.value.trim();
  state.filters.title = els.titleFilter.value.trim();
  state.filters.author = els.authorFilter.value.trim();
  state.filters.yearFrom = els.yearFromFilter.value.trim();
  state.filters.yearTo = els.yearToFilter.value.trim();
  state.filters.journal = els.journalFilter.value.trim();
  state.filters.doi = els.doiFilter.value.trim();
  state.filters.type = els.typeFilter.value;
  state.filters.volume = els.volumeFilter.value;
  state.filters.issues = els.filterIssues.checked;
  state.filters.missingMd = els.filterMissingMd.checked;
}

function activeFilterTotal() {
  return [
    state.filters.search,
    state.filters.title,
    state.filters.author,
    state.filters.yearFrom,
    state.filters.yearTo,
    state.filters.journal,
    state.filters.doi,
    state.filters.type,
    state.filters.volume,
    state.filters.issues,
    state.filters.missingMd,
  ].filter(Boolean).length;
}

function renderActiveFilterCount() {
  const total = activeFilterTotal();
  els.activeFilterCount.textContent = total ? `${total} active filter${total === 1 ? "" : "s"}` : "No active filters";
}

function validateYearRange() {
  const fields = [
    ["Year from", state.filters.yearFrom],
    ["Year to", state.filters.yearTo],
  ];
  for (const [label, value] of fields) {
    if (value && (!/^\d{4}$/.test(value) || Number(value) < 1000)) return `${label} must be a four-digit year.`;
  }
  if (state.filters.yearFrom && state.filters.yearTo && Number(state.filters.yearFrom) > Number(state.filters.yearTo)) {
    return "Year to must not be before year from.";
  }
  return "";
}

function buildOptions(select, values, emptyLabel) {
  const current = select.value;
  select.textContent = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = emptyLabel;
  select.appendChild(empty);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  select.value = values.includes(current) ? current : "";
  return select.value;
}

function setSearchDiagnostics(kind, message, actions = []) {
  const commands = (actions || []).map((action) => action.command).filter(Boolean);
  els.searchDiagnostics.dataset.kind = kind;
  els.searchDiagnostics.textContent = [message, ...commands].filter(Boolean).join(" • ");
}

function updateSearchModeUi() {
  const proceedings = state.tab === "proceedings";
  if (proceedings && state.searchMode !== "metadata") {
    state.searchMode = "metadata";
    state.ranked = null;
  }
  els.searchMode.value = state.searchMode;
  els.searchMode.disabled = proceedings;
  els.searchMode.title = proceedings ? "Ranked search is not available for proceedings yet." : "";
  els.searchButton.disabled = state.searchBusy || state.searchMode === "metadata" || proceedings;
  els.searchButton.hidden = state.searchMode === "metadata";
  els.searchButton.setAttribute?.("aria-busy", state.searchBusy ? "true" : "false");
  els.searchButton.textContent = state.searchBusy ? "Searching…" : "Search";
  els.searchInput.placeholder =
    state.searchMode === "metadata" ? "Filter loaded metadata" : `Enter a ${state.searchMode} search query`;
  if (proceedings) {
    setSearchDiagnostics("info", "Proceedings currently supports Metadata search and structured filters.");
  } else if (state.searchMode === "metadata") {
    setSearchDiagnostics("info", "Metadata mode filters the loaded records instantly.");
  }
}

function renderFilters() {
  const rows = activeRows();
  const types = [...new Set(rows.map((row) => row.paper_type).filter(Boolean))].sort();
  const volumes = [...new Set(rows.map((row) => row.proceeding_title).filter(Boolean))].sort();
  state.filters.type = buildOptions(els.typeFilter, types, "All types");
  state.filters.volume = buildOptions(els.volumeFilter, volumes, "All volumes");
  const isProceedings = state.tab === "proceedings";
  els.volumeFilter.hidden = !isProceedings;
  els.volumeFilterLabel.hidden = !isProceedings;
  updateSearchModeUi();
  renderActiveFilterCount();
}

function renderMetrics() {
  const payload = activePayload();
  const root = payload?.root || "";
  els.sourceTitle.textContent = state.tab === "main" ? "Main Papers" : "Proceedings";
  els.sourceRoot.textContent = root || "--";
  els.sourceRoot.title = root;
  els.sourceCopyButton.disabled = !root;
  if (els.sourceCopyButton.textContent !== "Copied") els.sourceCopyButton.textContent = "Copy";
  els.metricTotal.textContent = String(payload?.total ?? "--");
  const totals = payload?.issue_totals || {};
  els.metricErrors.textContent = String(totals.error ?? 0);
  els.metricWarnings.textContent = String(totals.warning ?? 0);
  els.updatedAt.textContent = formatDate(payload?.generated_at);
}

function rankedSearchUrl() {
  const params = new URLSearchParams({
    mode: state.searchMode,
    q: state.filters.search,
  });
  const fields = [
    ["title", state.filters.title],
    ["author", state.filters.author],
    ["year_from", state.filters.yearFrom],
    ["year_to", state.filters.yearTo],
    ["journal", state.filters.journal],
    ["paper_type", state.filters.type],
    ["doi", state.filters.doi],
  ];
  for (const [name, value] of fields) {
    if (value) params.set(name, value);
  }
  params.set("limit", "200");
  return `/api/main/search?${params.toString()}`;
}

function setSearchButtonBusy(busy) {
  state.searchBusy = Boolean(busy);
  els.searchButton.disabled = Boolean(busy) || state.searchMode === "metadata" || state.tab === "proceedings";
  els.searchButton.setAttribute?.("aria-busy", busy ? "true" : "false");
  els.searchButton.textContent = busy ? "Searching…" : "Search";
}

async function runRankedSearch() {
  syncFiltersFromControls();
  renderActiveFilterCount();
  if (state.tab !== "main") {
    state.searchMode = "metadata";
    state.ranked = null;
    updateSearchModeUi();
    renderTable();
    return;
  }
  if (state.searchMode === "metadata") {
    state.ranked = null;
    setSearchDiagnostics("info", "Metadata mode filters the loaded records instantly.");
    renderTable();
    return;
  }
  if (!state.filters.search) {
    setSearchDiagnostics("error", "Enter a query before running ranked search.");
    els.searchInput.focus();
    return;
  }
  const yearError = validateYearRange();
  if (yearError) {
    setSearchDiagnostics("error", yearError);
    return;
  }

  const requestTab = state.tab;
  const requestMode = state.searchMode;
  const requestSeq = ++state.searchRequestSeq;
  setSearchButtonBusy(true);
  setSearchDiagnostics("loading", `Running ${requestMode} search…`);
  try {
    const payload = await fetchJson(rankedSearchUrl());
    if (state.tab !== requestTab || state.searchMode !== requestMode || state.searchRequestSeq !== requestSeq) return;
    const results = Array.isArray(payload.results) ? payload.results : [];
    const diagnostics = payload.diagnostics || {};
    if (diagnostics.status === "unavailable" && results.length === 0) {
      state.ranked = null;
    } else {
      state.ranked = {
        order: results.map((result) => result.paper_id),
        byId: new Map(
          results.map((result, index) => [
            result.paper_id,
            {
              rank: Number(result.rank || index + 1),
              score: Number(result.score || 0),
              match: String(result.match || requestMode),
            },
          ]),
        ),
        diagnostics,
      };
      state.sortKey = "relevance";
      state.sortDir = "asc";
    }
    const message = diagnostics.message || `${results.length} ranked result${results.length === 1 ? "" : "s"}.`;
    setSearchDiagnostics(diagnostics.status || "ok", message, diagnostics.actions || []);
    renderTable();
  } catch (err) {
    if (state.tab !== requestTab || state.searchMode !== requestMode || state.searchRequestSeq !== requestSeq) return;
    setSearchDiagnostics("error", `Search failed: ${String(err)}`);
  } finally {
    if (state.tab === requestTab && state.searchMode === requestMode && state.searchRequestSeq === requestSeq) {
      setSearchButtonBusy(false);
    }
  }
}

function markRankedSearchDirty() {
  if (state.searchMode === "metadata") {
    state.ranked = null;
    renderTable();
  } else {
    setSearchDiagnostics("info", "Filters changed. Run Search to refresh ranked results.");
  }
  renderActiveFilterCount();
}

function clearAllFilters() {
  state.searchRequestSeq += 1;
  state.searchMode = "metadata";
  state.ranked = null;
  state.searchBusy = false;
  state.sortKey = "year";
  state.sortDir = "desc";
  Object.assign(state.filters, {
    search: "",
    title: "",
    author: "",
    yearFrom: "",
    yearTo: "",
    journal: "",
    doi: "",
    type: "",
    volume: "",
    issues: false,
    missingMd: false,
  });
  for (const input of [
    els.searchInput,
    els.titleFilter,
    els.authorFilter,
    els.yearFromFilter,
    els.yearToFilter,
    els.journalFilter,
    els.doiFilter,
    els.typeFilter,
    els.volumeFilter,
  ]) {
    input.value = "";
  }
  els.filterIssues.checked = false;
  els.filterMissingMd.checked = false;
  updateSearchModeUi();
  renderActiveFilterCount();
  renderTable();
}

function statusPills(row) {
  const pills = [];
  if (row.has_md) pills.push(["MD", "ok"]);
  else pills.push(["No MD", "severe"]);
  if (issueTotal(row) > 0) {
    const counts = row.issue_counts || {};
    if (counts.error) pills.push([`${counts.error} error`, "severe"]);
    if (counts.warning) pills.push([`${counts.warning} warn`, "warn"]);
  } else if (row.has_md) {
    pills.push(["clean", "ok"]);
  }
  if (row.has_l3) pills.push(["L3", ""]);
  if (row.toc_count) pills.push([`TOC ${row.toc_count}`, ""]);
  return pills;
}

function renderTable() {
  const rows = filteredRows();
  els.tableBody.textContent = "";
  els.emptyState.hidden = rows.length > 0;
  els.tableCount.textContent = state.ranked ? `${rows.length} ranked result${rows.length === 1 ? "" : "s"}` : `${rows.length} shown`;
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.className = state.selected[state.tab] === row.paper_id ? "is-selected" : "";
    tr.addEventListener("click", () => selectRow(row.paper_id));

    const titleCell = document.createElement("td");
    const titleWrap = document.createElement("div");
    titleWrap.className = "title-cell";
    const title = document.createElement("div");
    title.className = "paper-title";
    title.textContent = text(row.title);
    titleWrap.appendChild(title);
    const ranking = rankingFor(row.paper_id);
    if (ranking) {
      const relevance = document.createElement("div");
      relevance.className = "relevance-line";
      const score = Number.isFinite(ranking.score) ? ranking.score.toFixed(4) : "--";
      relevance.textContent = `#${ranking.rank} · ${ranking.match} · ${score}`;
      titleWrap.appendChild(relevance);
    }
    titleCell.appendChild(titleWrap);
    tr.appendChild(titleCell);

    for (const value of [row.authors_text, row.year, row.paper_type]) {
      const td = document.createElement("td");
      td.textContent = text(value);
      tr.appendChild(td);
    }

    const status = document.createElement("td");
    const pillRow = document.createElement("div");
    pillRow.className = "pill-row";
    for (const [label, kind] of statusPills(row)) {
      const pill = document.createElement("span");
      pill.className = `pill ${kind}`;
      pill.textContent = label;
      pillRow.appendChild(pill);
    }
    if (row.has_pdf && row.pdf_url) {
      const pdfButton = document.createElement("button");
      pdfButton.className = "pill pdf-pill";
      pdfButton.type = "button";
      pdfButton.textContent = "PDF";
      pdfButton.addEventListener("click", (event) => {
        event.stopPropagation();
        openPdf(row);
      });
      pillRow.appendChild(pdfButton);
    }
    status.appendChild(pillRow);
    tr.appendChild(status);
    els.tableBody.appendChild(tr);
  }
}

function renderMetadata(detail) {
  els.metadataGrid.textContent = "";
  const pairs = [
    ["Directory", detail.dir_name],
    ["Authors", detail.authors_text],
    ["Year", detail.year],
    ["Type", detail.paper_type],
    ["Journal", detail.journal],
    ["DOI", detail.doi],
  ];
  if (state.tab === "proceedings") pairs.splice(2, 0, ["Volume", detail.proceeding_title]);
  for (const [label, value] of pairs) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    els.metadataGrid.append(dt, dd);
  }
}

function renderIssues(detail) {
  els.issueList.textContent = "";
  const issues = detail.issues || [];
  if (!issues.length) {
    const empty = document.createElement("div");
    empty.className = "pill ok";
    empty.textContent = "No audit issues";
    els.issueList.appendChild(empty);
    return;
  }
  for (const issue of issues) {
    const item = document.createElement("div");
    item.className = `issue-item ${issue.severity}`;
    const rule = document.createElement("div");
    rule.className = "issue-rule";
    rule.textContent = `${issue.severity}: ${issue.rule}`;
    const message = document.createElement("div");
    message.className = "issue-message";
    message.textContent = issue.message;
    item.append(rule, message);
    els.issueList.appendChild(item);
  }
}

function renderToc(detail) {
  els.tocList.textContent = "";
  const toc = detail.toc || [];
  if (!toc.length) {
    const empty = document.createElement("div");
    empty.className = "pill";
    empty.textContent = "No TOC";
    els.tocList.appendChild(empty);
    return;
  }
  for (const entry of toc) {
    const item = document.createElement("div");
    item.className = "toc-item";
    const title = document.createElement("span");
    title.textContent = `${"#".repeat(Number(entry.level || 1))} ${entry.title || ""}`;
    const line = document.createElement("span");
    line.textContent = entry.line ? `L${entry.line}` : "";
    item.append(title, line);
    els.tocList.appendChild(item);
  }
}

function renderDetailActions(detail) {
  const hasRecord = Boolean(detail?.paper_id);
  const hasPdf = Boolean(detail?.has_pdf && detail?.pdf_url);
  els.detailActions.hidden = !hasRecord;
  els.copyBibtexButton.disabled = !hasRecord;
  els.previewPdfButton.disabled = !hasPdf;
  els.previewPdfButton.title = hasPdf ? "Preview this PDF inside ScholarAIO" : "No local PDF is available";
  const nativeEnabled = hasPdf && state.capabilities.nativePdfOpen;
  els.nativePdfButton.disabled = !nativeEnabled;
  if (!hasPdf) els.nativePdfButton.title = "No local PDF is available";
  else if (!state.capabilities.nativePdfOpen) {
    els.nativePdfButton.title = state.capabilities.nativePdfReason || "Native PDF launch is unavailable";
  } else els.nativePdfButton.title = "Open this PDF with the operating system's default viewer";
}

function renderDetail(detail) {
  if (!detail) {
    state.detail = null;
    els.detailTitle.textContent = "Select a record";
    els.metadataGrid.textContent = "";
    els.issueList.textContent = "";
    els.detailAbstract.textContent = "--";
    els.detailConclusion.textContent = "--";
    els.tocList.textContent = "";
    renderDetailActions(null);
    return;
  }
  state.detail = detail;
  els.detailTitle.textContent = text(detail.title);
  renderMetadata(detail);
  renderIssues(detail);
  renderMarkdown(els.detailAbstract, detail.abstract);
  renderMarkdown(els.detailConclusion, detail.l3_conclusion);
  renderToc(detail);
  renderDetailActions(detail);
}

async function copyText(value) {
  const content = String(value ?? "");
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(content);
    return;
  } catch (_clipboardError) {
    const textarea = document.createElement("textarea");
    const previousFocus = document.activeElement;
    textarea.value = content;
    textarea.className = "clipboard-fallback";
    textarea.setAttribute("readonly", "");
    document.body.appendChild(textarea);
    try {
      textarea.focus();
      textarea.select();
      if (!document.execCommand("copy")) throw new Error("Clipboard fallback was rejected");
    } finally {
      textarea.remove();
      if (previousFocus?.focus) previousFocus.focus();
    }
  }
}

let toastTimer = null;
function showToast(message, kind = "success") {
  clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.dataset.kind = kind;
  els.toast.hidden = false;
  toastTimer = setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
  if (toastTimer?.unref) toastTimer.unref();
}

function setActionBusy(button, busy, busyLabel) {
  if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent;
  button.disabled = Boolean(busy);
  button.setAttribute?.("aria-busy", busy ? "true" : "false");
  button.textContent = busy ? busyLabel : button.dataset.idleLabel;
}

async function copySourceRoot() {
  const root = activePayload()?.root || "";
  if (!root) return;
  try {
    await copyText(root);
    els.sourceCopyButton.textContent = "Copied";
  } catch (_err) {
    els.sourceCopyButton.textContent = "Copy failed";
  }
}

async function copySelectedBibtex() {
  const detail = state.detail;
  if (!detail?.paper_id || els.copyBibtexButton.disabled) return;
  const source = state.tab === "main" ? "main" : "proceedings";
  setActionBusy(els.copyBibtexButton, true, "Copying…");
  try {
    const payload = await fetchJson(`/api/${source}/bibtex?id=${encodeURIComponent(detail.paper_id)}`);
    await copyText(payload.bibtex || "");
    showToast("BibTeX copied to clipboard.");
  } catch (err) {
    showToast(`Could not copy BibTeX: ${String(err)}`, "error");
  } finally {
    setActionBusy(els.copyBibtexButton, false, "Copying…");
    renderDetailActions(state.detail);
  }
}

function previewSelectedPdf() {
  if (!state.detail?.has_pdf || !state.detail?.pdf_url) return;
  openPdf(state.detail);
}

async function openSelectedPdfNative() {
  const detail = state.detail;
  if (!detail?.paper_id || !detail.has_pdf || !state.capabilities.nativePdfOpen || els.nativePdfButton.disabled) {
    return;
  }
  const source = state.tab === "main" ? "main" : "proceedings";
  setActionBusy(els.nativePdfButton, true, "Opening…");
  try {
    await fetchJson(`/api/${source}/open-pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-ScholarAIO-CSRF": state.capabilities.csrfToken,
      },
      body: JSON.stringify({ id: detail.paper_id }),
    });
    showToast("PDF opened in the default viewer.");
  } catch (err) {
    showToast(`Could not open the default viewer: ${String(err)}`, "error");
  } finally {
    setActionBusy(els.nativePdfButton, false, "Opening…");
    renderDetailActions(state.detail);
  }
}

function setPdfFullscreen(enabled) {
  state.pdfFullscreen = Boolean(enabled);
  els.tablePanel.classList.toggle("is-pdf-fullscreen", state.pdfFullscreen);
  els.pdfFullscreenButton.textContent = state.pdfFullscreen ? "Exit fullscreen" : "Fullscreen";
}

function showRecords() {
  setPdfFullscreen(false);
  state.pdf = null;
  els.pdfFrame.removeAttribute("src");
  els.recordsToolbarTitle.hidden = false;
  els.refreshButton.hidden = false;
  els.recordsView.hidden = false;
  els.pdfToolbarTitle.hidden = true;
  els.pdfViewer.hidden = true;
}

function openPdf(row) {
  setPdfFullscreen(false);
  state.pdf = { url: row.pdf_url, title: row.title || row.dir_name || row.paper_id };
  els.pdfTitle.textContent = text(state.pdf.title);
  els.pdfFrame.src = row.pdf_url;
  els.recordsToolbarTitle.hidden = true;
  els.refreshButton.hidden = true;
  els.recordsView.hidden = true;
  els.pdfToolbarTitle.hidden = false;
  els.pdfViewer.hidden = false;
}

async function selectRow(paperId) {
  const requestTab = state.tab;
  const requestSeq = ++state.detailRequestSeq;
  state.selected[requestTab] = paperId;
  if (state.tab === requestTab) renderTable();
  try {
    const endpoint = requestTab === "main" ? "/api/main/detail" : "/api/proceedings/detail";
    const detail = await fetchJson(`${endpoint}?id=${encodeURIComponent(paperId)}`);
    if (state.tab !== requestTab || state.selected[requestTab] !== paperId || state.detailRequestSeq !== requestSeq) {
      return;
    }
    state.detail = detail;
    renderDetail(detail);
    setConnection("live", "Live");
  } catch (err) {
    if (state.tab !== requestTab || state.selected[requestTab] !== paperId || state.detailRequestSeq !== requestSeq) {
      return;
    }
    setConnection("error", "Detail failed");
    renderDetail({ title: "Detail unavailable", abstract: String(err) });
  }
}

function chooseDefaultSelection() {
  const selected = state.selected[state.tab];
  const rows = filteredRows();
  if (selected && rows.some((row) => row.paper_id === selected)) return selected;
  return rows[0]?.paper_id || "";
}

async function refreshActive({ keepSelection = true } = {}) {
  const requestTab = state.tab;
  const requestSeq = ++state.refreshRequestSeq[requestTab];
  const endpoint = requestTab === "main" ? "/api/main/papers" : "/api/proceedings/papers";
  try {
    const payload = await fetchJson(endpoint);
    if (state.refreshRequestSeq[requestTab] !== requestSeq) {
      return;
    }
    state.payload[requestTab] = payload;
    state.rows[requestTab] = payload.papers || [];
    if (state.tab !== requestTab) {
      return;
    }
    if (state.pdf && !state.rows[requestTab].some((row) => row.pdf_url === state.pdf.url)) {
      showRecords();
    }
    renderFilters();
    renderMetrics();
    renderTable();
    setConnection("live", "Live");
    const nextSelection = keepSelection ? chooseDefaultSelection() : filteredRows()[0]?.paper_id || "";
    if (nextSelection) await selectRow(nextSelection);
    else renderDetail(null);
  } catch (err) {
    if (state.tab !== requestTab) {
      return;
    }
    setConnection("error", "Refresh failed");
    els.tableCount.textContent = String(err);
  }
}

function schedulePoll() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => refreshActive({ keepSelection: true }), POLL_MS);
}

function switchTab(tab) {
  if (state.tab === tab) return;
  state.tab = tab;
  state.searchRequestSeq += 1;
  state.searchMode = "metadata";
  state.ranked = null;
  state.searchBusy = false;
  state.sortKey = "year";
  state.sortDir = "desc";
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tab);
  });
  state.filters.type = "";
  state.filters.volume = "";
  els.typeFilter.value = "";
  els.volumeFilter.value = "";
  els.searchMode.value = "metadata";
  showRecords();
  state.detailRequestSeq += 1;
  renderDetail(null);
  updateSearchModeUi();
  refreshActive({ keepSelection: true });
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
  for (const input of [
    els.searchInput,
    els.titleFilter,
    els.authorFilter,
    els.yearFromFilter,
    els.yearToFilter,
    els.journalFilter,
    els.doiFilter,
  ]) {
    input.addEventListener("input", () => {
      syncFiltersFromControls();
      const yearError = validateYearRange();
      if (yearError) setSearchDiagnostics("error", yearError);
      else markRankedSearchDirty();
    });
  }
  els.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && state.searchMode !== "metadata") {
      event.preventDefault();
      runRankedSearch();
    }
  });
  els.searchMode.addEventListener("change", () => {
    state.searchRequestSeq += 1;
    state.searchMode = els.searchMode.value;
    state.ranked = null;
    state.searchBusy = false;
    state.sortKey = "year";
    state.sortDir = "desc";
    updateSearchModeUi();
    if (state.searchMode !== "metadata") {
      setSearchDiagnostics("info", `Enter a query, then run ${state.searchMode} search.`);
    }
    renderTable();
  });
  els.searchButton.addEventListener("click", runRankedSearch);
  els.clearFiltersButton.addEventListener("click", clearAllFilters);
  els.typeFilter.addEventListener("change", () => {
    syncFiltersFromControls();
    markRankedSearchDirty();
  });
  els.volumeFilter.addEventListener("change", () => {
    syncFiltersFromControls();
    markRankedSearchDirty();
  });
  els.filterIssues.addEventListener("change", () => {
    syncFiltersFromControls();
    markRankedSearchDirty();
  });
  els.filterMissingMd.addEventListener("change", () => {
    syncFiltersFromControls();
    markRankedSearchDirty();
  });
  els.sourceCopyButton.addEventListener("click", copySourceRoot);
  els.copyBibtexButton.addEventListener("click", copySelectedBibtex);
  els.previewPdfButton.addEventListener("click", previewSelectedPdf);
  els.nativePdfButton.addEventListener("click", openSelectedPdfNative);
  els.refreshButton.addEventListener("click", () => refreshActive({ keepSelection: true }));
  els.pdfBackButton.addEventListener("click", showRecords);
  els.pdfFullscreenButton.addEventListener("click", () => setPdfFullscreen(!state.pdfFullscreen));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.pdfFullscreen) setPdfFullscreen(false);
  });
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else {
        state.sortKey = key;
        state.sortDir = key === "year" ? "desc" : "asc";
      }
      renderTable();
    });
  });
}

bindEvents();
loadCapabilities();
refreshActive({ keepSelection: false });
schedulePoll();
