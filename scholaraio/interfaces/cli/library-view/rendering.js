(() => {
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

  globalThis.ScholarAIORendering = Object.freeze({ formatDate, renderMarkdown, text });
})();
