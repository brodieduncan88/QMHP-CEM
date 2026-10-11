// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// QMHP-CEM read-only evidence viewer.
//
// Every network call goes through get(), which issues HTTP GET only. The page
// has no forms, sends no request bodies and stores nothing. Repository text is
// inserted as text nodes; the only HTML this file builds is the markdown
// renderer's output, which escapes every character of the source first.

"use strict";

const view = document.getElementById("view");

// ------------------------------------------------------------------ network
async function get(path) {
  const res = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });
  let body = null;
  try { body = await res.json(); } catch (_) { body = { error: res.statusText }; }
  if (!res.ok) {
    const err = new Error((body && body.error) || res.statusText);
    err.status = res.status;
    err.detail = body && body.detail;
    throw err;
  }
  return body;
}
const q = encodeURIComponent;
// Idempotent reads used by several views are requested once per page load.
const readCache = new Map();
function getCached(path) {
  if (!readCache.has(path)) readCache.set(path, get(path).catch((e) => { readCache.delete(path); throw e; }));
  return readCache.get(path);
}

// ---------------------------------------------------------------------- DOM
// A long hex digest is broken into 8-character groups, so a wrap never leaves one orphan character.
const hashGroups = (s) => (/^[0-9a-f]{16,}$/i.test(s) ? (s.match(/.{1,8}/g) || [s]).flatMap((g, i) => (i ? [el("wbr"), document.createTextNode(g)] : [document.createTextNode(g)])) : null);
function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "on") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
      else node.setAttribute(k, v === true ? "" : String(v));
    }
  }
  const hashy = node.classList.contains("hash");
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    const grouped = hashy && typeof kid === "string" ? hashGroups(kid) : null;
    if (grouped) { node.append(...grouped); continue; }
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}
const txt = (s) => document.createTextNode(s == null ? "" : String(s));
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
// Marks each table that is wider than its box, so the scroll cues show only where columns are hidden.
function markScrollTables(root) {
  root.querySelectorAll(".table-wrap").forEach((w) => w.classList.toggle("is-scrollable", w.scrollWidth > w.clientWidth + 1));
}
function link(href, label, cls) { return el("a", { href, class: cls }, label); }
const fileHref = (path) => `#/file?path=${q(path)}`;
// A repository path as link text. A break opportunity follows each "_", "-", "." and "/",
// so a long name wraps at a separator instead of mid-word. The text itself is unchanged.
const pathLabel = (path) => el("span", null, String(path).split(/(?<=[_\-./])/).flatMap((seg, i) => (i ? [el("wbr"), seg] : [seg])));
// Prose that names identifiers or files ("base_v1_5_8e_provenance.pdf"): a break opportunity
// after "_" and before a letter that follows "." so the text wraps at a separator.
const softBreaks = (text) => String(text == null ? "" : text).split(/(?<=_)|(?<=\.)(?=[A-Za-z])/).flatMap((seg, i) => (i ? [el("wbr"), seg] : [seg]));
const recordHref = (id) => `#/records/${q(id)}`;
function fmtSize(n) {
  if (n == null) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}
function fmtTs(ts) { return ts ? ts.replace("T", " ").replace("Z", " UTC") : "undated"; }
function shortSha(s) { return s ? String(s).slice(0, 12) : ""; }
function trunc(s, n) { s = s == null ? "" : String(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
function plural(n, one, many = one + "s") { return n === 1 ? one : many; }
// Long repository text is shown in full. Past n characters it opens at a word boundary:
// the cut is the summary, and the complete text sits in the disclosure beneath it.
function excerpt(s, n) {
  s = s == null ? "" : String(s);
  if (s.length <= n) return softBreaks(s);
  const at = s.lastIndexOf(" ", n);
  return el("details", { class: "more" }, el("summary", null, softBreaks(s.slice(0, at > 0 ? at : n)), " … Show full text"), softBreaks(s));
}

// ------------------------------------------------------------------- badges
// A badge that carries detail is a button: hover, focus or tap shows the detail in
// the #tip popover. A badge inside a link stays plain (no nested controls).
function badge(label, tone, tip) {
  const cls = `badge tone-${tone || "neutral"}`;
  if (!tip) return el("span", { class: cls }, label);
  const t = typeof tip === "string" ? { k: label, v: tip } : tip;
  return el("button", { type: "button", class: cls, "data-tip": t.v, "data-tip-k": t.k, "aria-describedby": "tip", "aria-expanded": "false" }, label);
}
function basisBadge(basis, lg, plain) {
  const b = typeof basis === "string" ? basis : basis && basis.basis;
  const cls = `basis basis-${b}${lg ? " lg" : ""}`;
  if (plain || !basis || !basis.reason) return el("span", { class: cls }, b || "?");
  return el("button", { type: "button", class: cls, "data-tip": basis.reason, "data-tip-k": `Rule ${basis.rule} → ${b}`, "aria-describedby": "tip", "aria-expanded": "false" }, b);
}
function statusBadges(items, max, plain) {
  const out = [];
  for (const item of items || []) {
    item.tokens.forEach((tok, i) => {
      out.push(plain ? badge(tok, item.tones[i]) : badge(tok, item.tones[i], { k: item.path, v: `“${item.raw}”` }));
    });
  }
  return max && out.length > max ? [...out.slice(0, max), el("span", { class: "muted small" }, ` +${out.length - max}`)] : out;
}
function computationalNotice(basis) {
  const b = typeof basis === "string" ? basis : basis && basis.basis;
  const nodes = [];
  if (b === "SYNTHETIC") {
    nodes.push(el("div", { class: "notice synthetic", role: "note" },
      el("span", { class: "ico" }, "SYNTHETIC"),
      el("div", { class: "body" }, el("strong", null, "Synthetic data. "),
        "Known-answer inputs, fixtures or a software demonstration. It is not evidence about any candidate.")));
  }
  if (b !== "MEASURED") {
    nodes.push(el("div", { class: "notice comp", role: "note" },
      el("span", { class: "ico" }, "COMPUTATIONAL ONLY"),
      el("div", { class: "body" }, el("strong", null, "Not hardware validation. "),
        "Nothing here is measured on hardware. A computational PASS or QUALIFIED does not close any HARDWARE-GATED gate.")));
  }
  return nodes;
}
function lockedAction(label, reason) {
  return el("div", { class: "item" },
    el("div", { class: "action" }, label),
    reason ? el("div", { class: "small muted" }, reason) : null);
}
// A list of unavailable actions. A reason that two or more rows share is shown once above
// the list; a row shows its own reason only when it differs from that shared one.
function lockedList(items) {
  const counts = new Map();
  for (const [, reason] of items) counts.set(reason, (counts.get(reason) || 0) + 1);
  let shared = null, most = 1;
  for (const [reason, n] of counts) if (n > most) { most = n; shared = reason; }
  return [shared ? el("p", { class: "small muted" }, shared) : null,
    ...items.map(([label, reason]) => lockedAction(label, reason === shared ? null : reason))];
}

// ----------------------------------------------------------------- tables
function table(headers, rows, cls) {
  const labels = headers.map((h) => (typeof h === "string" ? h : ""));
  for (const tr of rows) {
    if (!tr || !tr.children) continue;
    [...tr.children].forEach((td, i) => { if (labels[i]) td.setAttribute("data-label", labels[i]); });
  }
  return el("div", { class: `table-wrap${cls === "matrix" ? " keep" : ""}` },
    el("table", { class: cls },
      el("thead", null, el("tr", null, headers.map((h) => el("th", null, h)))),
      el("tbody", null, rows.length ? rows : el("tr", null, el("td", { colspan: headers.length, class: "empty" }, "Nothing to show.")))));
}
function kv(pairs) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of pairs) {
    if (v === undefined || v === null || v === "") continue;
    dl.append(el("dt", null, k), el("dd", null, v));
  }
  return dl;
}

// -------------------------------------------------------------- JSON tree
function jsonTree(value, budget = { n: 6000 }) {
  const root = el("div", { class: "tree" });
  root.append(node(null, value, 0));
  if (budget.n <= 0) root.append(el("div", { class: "dim" }, "… truncated for display; the Raw tab shows every byte."));
  return root;

  function scalar(v) {
    if (v === null) return el("span", { class: "z" }, "null");
    if (typeof v === "string") return el("span", { class: "s" }, JSON.stringify(v));
    if (typeof v === "number") return el("span", { class: "n" }, String(v));
    if (typeof v === "boolean") return el("span", { class: "b" }, String(v));
    return el("span", null, String(v));
  }
  function node(key, v, depth) {
    budget.n -= 1;
    if (budget.n <= 0) return el("div");
    const label = key === null ? [] : [el("span", { class: "k" }, JSON.stringify(key)), ": "];
    if (v !== null && typeof v === "object") {
      const entries = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
      const summary = Array.isArray(v) ? `[${entries.length}]` : `{${entries.length}}`;
      const d = el("details", depth < 2 ? { open: true } : null,
        el("summary", null, ...label, el("span", { class: "dim" }, summary)));
      for (const [k, x] of entries) d.append(node(Array.isArray(v) ? k : k, x, depth + 1));
      return d;
    }
    return el("div", { class: "leaf" }, ...label, scalar(v));
  }
}

// --------------------------------------------------------------- markdown
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function resolveRel(base, target) {
  const parts = base ? base.split("/") : [];
  for (const seg of target.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") parts.pop(); else parts.push(seg);
  }
  return parts.join("/");
}
function safeHref(url, baseDir) {
  const raw = url.replace(/&amp;/g, "&");
  if (/^https?:\/\//i.test(raw)) return { href: raw, external: true };
  if (raw.startsWith("#")) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(raw)) return null; // javascript:, data:, mailto: ... not linked
  const path = resolveRel(raw.startsWith("/") ? "" : baseDir, raw.split("#")[0]);
  return path ? { href: fileHref(path), external: false } : null;
}
function inline(src, baseDir) {
  let s = esc(src);
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (m, label, url) => {
    const h = safeHref(url, baseDir);
    if (!h) return label;
    return `<a href="${esc(h.href)}"${h.external ? ' rel="noopener noreferrer" target="_blank"' : ""}>${label}</a>`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^\w*])\*([^*\s][^*]*)\*(?!\w)/g, "$1<em>$2</em>");
  s = s.replace(/(^|[^\w])_([^_\s][^_]*)_(?!\w)/g, "$1<em>$2</em>");
  s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
  return s;
}
function markdown(text, path) {
  const baseDir = path && path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
  const lines = String(text).replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let i = 0;
  const isTableSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
  const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      const buf = [];
      i += 1;
      while (i < lines.length && !/^\s*```/.test(lines[i])) { buf.push(lines[i]); i += 1; }
      i += 1;
      out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) { const n = Math.min(h[1].length + 1, 6); out.push(`<h${n}>${inline(h[2], baseDir)}</h${n}>`); i += 1; continue; }
    if (/^\s*(---+|\*\*\*+|___+)\s*$/.test(line)) { out.push("<hr class=\"soft\">"); i += 1; continue; }
    if (/^\s*\|/.test(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(cells(lines[i])); i += 1; }
      out.push("<div class=\"table-wrap\"><table><thead><tr>" + head.map((c) => `<th>${inline(c, baseDir)}</th>`).join("") +
        "</tr></thead><tbody>" + rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c, baseDir)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table></div>");
      continue;
    }
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, "")); i += 1; }
      out.push(`<blockquote>${inline(buf.join(" "), baseDir)}</blockquote>`);
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items = [];
      while (i < lines.length && (/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
        if (/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) items.push(lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, ""));
        else items[items.length - 1] += " " + lines[i].trim();
        i += 1;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>` + items.map((it) => `<li>${inline(it, baseDir)}</li>`).join("") + `</${tag}>`);
      continue;
    }
    if (!line.trim()) { i += 1; continue; }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*>|\s*\||\s*([-*+]|\d+[.)])\s+)/.test(lines[i])) {
      buf.push(lines[i]); i += 1;
    }
    if (!buf.length) { buf.push(lines[i]); i += 1; }
    out.push(`<p>${inline(buf.join(" "), baseDir)}</p>`);
  }
  const div = el("div", { class: "md" });
  div.innerHTML = out.join("\n"); // built only from esc()-escaped source, see inline()
  return div;
}

// ------------------------------------------------------------------- tabs
function tabs(defs) {
  const bar = el("div", { class: "tabs", role: "tablist" });
  const body = el("div");
  const buttons = [];
  defs.filter(Boolean).forEach((d, idx) => {
    const b = el("button", { type: "button", role: "tab", class: idx === 0 ? "on" : "" }, d.label);
    b.addEventListener("click", () => {
      buttons.forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      clear(body);
      body.append(typeof d.render === "function" ? d.render() : d.render);
    });
    buttons.push(b);
    bar.append(b);
  });
  const first = defs.filter(Boolean)[0];
  if (first) body.append(typeof first.render === "function" ? first.render() : first.render);
  return el("div", null, bar, body);
}

function head(title, lead, crumbs, extra) {
  const mono = /^[A-Za-z0-9._\-]+$/.test(String(title)) && String(title).length > 14;
  return el("header", { class: "detail-hero" },
    el("div", { class: "dh-copy" },
      crumbs ? el("p", { class: "eyebrow bare" }, crumbs) : null,
      el("h1", { class: `dh-title${mono ? " mono" : ""}` }, title),
      lead ? el("p", { class: "lead" }, lead) : null),
    extra ? el("div", { class: "dh-extra" }, extra) : null);
}

// ---------------------------------------------------------- editorial
function eyebrow(n, label) {
  return el("p", { class: "eyebrow" }, n ? el("span", { class: "num" }, n) : null, label);
}
function pageHero(title, lead, art) {
  const copy = el("div", null, el("h1", { class: "title" }, title), lead ? el("p", { class: "lead" }, lead) : null);
  return el("header", { class: `page-hero${art ? " has-art" : ""}` }, copy, art || null);
}
function arrow() { return el("span", { class: "arr", "aria-hidden": "true" }, "→"); }
function skeleton() {
  return el("div", { class: "wrap skeleton", "aria-hidden": "true" },
    el("div", { class: "sk sk-eyebrow" }), el("div", { class: "sk sk-title" }),
    el("div", { class: "sk sk-line" }), el("div", { class: "sk sk-line" }), el("div", { class: "sk sk-block" }));
}

// ------------------------------------------------------------ artwork
// Original figures drawn from this checkout's own records. Nothing here is a picture
// of hardware; each caption says exactly which data drew it.
const SVGNS = "http://www.w3.org/2000/svg";
function sv(tag, attrs, ...kids) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "text") node.textContent = v; else node.setAttribute(k, String(v));
  }
  for (const kid of kids.flat(Infinity)) if (kid) node.append(kid);
  return node;
}
function stagger(node, i) { node.style.setProperty("--i", String(i)); return node; }
let artSeq = 0;
const TONE_RANK = { negative: 5, caution: 4, gated: 3, positive: 2, neutral: 1, muted: 0 };
function worstTone(headline) {
  let best = "neutral", rank = -1;
  for (const h of headline || []) for (const t of h.tones) if ((TONE_RANK[t] ?? 1) > rank) { rank = TONE_RANK[t] ?? 1; best = t; }
  return best;
}
function artFigure(svgNode, caption, cls) {
  return el("figure", { class: `art reveal${cls ? " " + cls : ""}` }, svgNode, caption ? el("figcaption", null, caption) : null);
}
// Joins optional figure classes; figures with small labels pass "fig-scroll" so that on
// phones they scroll sideways inside their box instead of shrinking the text.
const figClass = (...parts) => parts.filter(Boolean).join(" ") || undefined;
function nodeShape(basis, cx, cy, tone) {
  const fill = `node tone-fill-${tone}`, ring = `node ring tone-stroke-${tone}`;
  const diamond = (r) => `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`;
  switch (basis) {
    case "SOLVED": return sv("circle", { cx, cy, r: 6.5, class: fill });
    case "SYNTHETIC": return sv("circle", { cx, cy, r: 6, class: `${ring} dashed` });
    case "ANALYSIS": return sv("rect", { x: cx - 5.5, y: cy - 5.5, width: 11, height: 11, rx: 1.5, class: fill });
    case "DECLARATION": return sv("polygon", { points: diamond(7), class: `${ring} dotted` });
    case "MEASURED": return sv("polygon", { points: diamond(7.5), class: fill });
    default: return sv("circle", { cx, cy, r: 6, class: `${ring} dotted` });
  }
}
// The evidence lattice: one row per record family, x = recorded time, shape = basis,
// colour = the record's most severe headline tone, curves = records naming records.
function artLattice(records, opts) {
  const o = opts || {};
  // The left gutter holds family names at the figure's label size, so it is wide enough
  // that a name never runs into the first mark of its row.
  const W = 640, rowH = o.rowH || 54, padL = 190, padR = 22, padT = 18;
  const fams = [...new Set(records.map((r) => r.family))].sort();
  const H = padT + Math.max(1, fams.length) * rowH + 34;
  const times = records.map((r) => Date.parse(r.timestamp || "")).filter(Number.isFinite);
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const span = W - padL - padR;
  const xOf = (r) => { const t = Date.parse(r.timestamp || ""); return (!Number.isFinite(t) || t1 === t0) ? padL + span / 2 : padL + ((t - t0) / (t1 - t0)) * span; };
  const pos = new Map();
  for (const f of fams) {
    const row = records.filter((r) => r.family === f).sort((a, b) => xOf(a) - xOf(b));
    let lastX = -1e9, flip = 0;
    for (const r of row) {
      const x = xOf(r); let dy = 0;
      if (x - lastX < 13) { flip += 1; dy = (flip % 2 ? -1 : 1) * 11; } else { flip = 0; lastX = x; }
      pos.set(r.id, [x, padT + fams.indexOf(f) * rowH + rowH / 2 + dy]);
    }
  }
  const grid = sv("g");
  fams.forEach((f, i) => {
    const y = padT + i * rowH + rowH / 2;
    grid.append(sv("line", { x1: padL - 10, x2: W - padR + 8, y1: y, y2: y, class: "rule-soft" }),
      sv("text", { x: 0, y: y + 5.5, class: "lbl", text: trunc(f, 16) }));
  });
  const axisY = padT + fams.length * rowH + 16;
  if (o.grid) {
    for (let k = 0; k <= 12; k += 1) {
      const gx = padL + (span * k) / 12;
      grid.append(sv("line", { x1: gx, x2: gx, y1: padT, y2: axisY - 8, class: "rule-soft" }));
    }
  }
  grid.append(sv("line", { x1: padL, x2: W - padR, y1: axisY - 8, y2: axisY - 8, class: "rule" }));
  if (times.length) {
    grid.append(sv("text", { x: padL, y: axisY + 8, class: "lbl", text: fmtTs(new Date(t0).toISOString().replace(/\.\d+Z$/, "Z")).slice(0, 16) }),
      sv("text", { x: W - padR, y: axisY + 8, class: "lbl", "text-anchor": "end", text: fmtTs(new Date(t1).toISOString().replace(/\.\d+Z$/, "Z")).slice(0, 16) }));
  }
  const linksG = sv("g"); let li = 0;
  for (const r of records) {
    for (const target of r.links || []) {
      if (!pos.has(target) || !pos.has(r.id)) continue;
      const [x1, y1] = pos.get(r.id), [x2, y2] = pos.get(target);
      const lift = Math.min(60, 18 + Math.abs(x2 - x1) / 6);
      linksG.append(stagger(sv("path", { d: `M${x1},${y1} C${x1},${Math.min(y1, y2) - lift} ${x2},${Math.min(y1, y2) - lift} ${x2},${y2}`, class: "link-path", pathLength: 1 }), li++));
    }
  }
  const nodesG = sv("g");
  records.forEach((r, i) => {
    const [cx, cy] = pos.get(r.id);
    const shape = stagger(nodeShape(r.basis.basis, cx, cy, worstTone(r.headline)), i);
    const toks = (r.headline || []).flatMap((h) => h.tokens).slice(0, 4).join(" · ");
    nodesG.append(sv("a", { href: recordHref(r.id), "data-tip-k": r.id, "data-tip": `${r.basis.basis}${toks ? " · " + toks : ""} · ${fmtTs(r.timestamp)}`, "aria-label": `${r.id}: ${r.basis.basis}${toks ? ", " + toks : ""}` },
      sv("circle", { cx, cy, r: 22, class: "node-hit" }), shape));
  });
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "fig-lattice", role: "group", "aria-label": `Evidence lattice of ${records.length} records` }, grid, linksG, nodesG);
  return artFigure(svg, o.caption === undefined
    ? `Drawn from ${records.length} records in this checkout · row = family · x = recorded time · shape = evidence basis · colour = most severe headline status · a curve joins two records, one naming the other · select a mark to open it`
    : o.caption, figClass("fig-scroll", o.cls));
}
// A stage stack: one plate per row, hatched and locked when only hardware can close it.
function artPlates(rows, opts) {
  const o = opts || {};
  const uid = `hatch-${++artSeq}`;
  // compact: a label-free stack for section headers; the table below carries the detail
  const W = 560, plateH = o.compact ? 20 : 38, gap = o.compact ? 9 : (o.gap || 18), top = 10;
  const n = Math.max(1, rows.length);
  const H = top + n * (plateH + gap) + 6;
  const wMax = 540, wMin = 330;
  const defs = sv("defs", null, sv("pattern", { id: uid, width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
    sv("line", { x1: 0, y1: 0, x2: 0, y2: 8, class: "hatch-line" })));
  const rodX = [W / 2 - wMin / 2 + 34, W / 2 + wMin / 2 - 34];
  // standoffs between consecutive plates, never across a plate's label
  const rods = sv("g");
  for (let i = 0; i < n - 1; i += 1) {
    const y1 = top + i * (plateH + gap) + plateH, y2 = y1 + gap;
    rodX.forEach((x) => rods.append(sv("line", { x1: x, x2: x, y1: y1 + 2, y2: y2 - 2, class: "rod" })));
  }
  const plates = sv("g");
  rows.forEach((row, i) => {
    const w = n === 1 ? wMax : wMax - ((wMax - wMin) * i) / (n - 1);
    const x = (W - w) / 2, y = top + i * (plateH + gap);
    const g = stagger(sv("g", { class: "plate-g" },
      sv("rect", { x, y, width: w, height: plateH, rx: 7, class: `plate-body${row.locked ? " locked" : ""} tone-stroke-${row.tone || "neutral"}`, fill: row.locked ? `url(#${uid})` : null }),
      o.compact ? null : sv("text", { x: x + 14, y: y + plateH / 2 + 3.5, class: "lbl lbl-strong", text: trunc(row.label, 22) }),
      o.compact ? null : sv("text", { x: x + w - 14, y: y + plateH / 2 + 3.5, class: "lbl", "text-anchor": "end", text: trunc(row.value || "", 30) })), i);
    plates.append(row.href && !o.compact ? sv("a", { href: row.href, "data-tip-k": row.label, "data-tip": row.tip || row.value || "", "aria-label": `${row.label}: ${row.value || ""}` }, g) : g);
  });
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": o.label || "Stage stack" }, defs, rods, plates);
  // labelled plates scroll sideways on phones; the compact stack has no text to protect
  return artFigure(svg, o.caption, figClass(o.compact ? null : "fig-scroll", o.cls));
}
// A digest drawn as a ring: 64 ticks, one per hex digit, length = the digit's value.
function artSigil(hex, label, sub, opts) {
  const o = opts || {};
  const W = 320, c = 160, R = 138;
  const digits = String(hex || "").toLowerCase().replace(/[^0-9a-f]/g, "").slice(0, 64).padEnd(64, "0");
  const ring = sv("g", { class: "sigil-rot" });
  [...digits].forEach((d, i) => {
    const v = parseInt(d, 16), a = (i / 64) * Math.PI * 2 - Math.PI / 2, len = 10 + v * 3;
    ring.append(sv("line", { x1: c + Math.cos(a) * R, y1: c + Math.sin(a) * R, x2: c + Math.cos(a) * (R - len), y2: c + Math.sin(a) * (R - len), class: `tick${i % 8 === 0 ? " alt" : ""}` }));
  });
  for (let i = 0; i < 32; i += 1) {
    const v = parseInt(digits.slice(i * 2, i * 2 + 2), 16), a = (i / 32) * Math.PI * 2 - Math.PI / 2, r = 70 + (v / 255) * 10;
    ring.append(sv("circle", { cx: c + Math.cos(a) * r, cy: c + Math.sin(a) * r, r: 1.6 + (v % 4) * 0.5, class: "tone-fill-neutral" }));
  }
  const svg = sv("svg", { viewBox: `0 0 ${W} ${W}`, role: "img", "aria-label": `${label}: SHA-256 ${hex}` },
    sv("circle", { cx: c, cy: c, r: R + 8, class: "rule-soft", fill: "none" }), ring,
    sv("circle", { cx: c, cy: c, r: 64, class: "core" }),
    sv("text", { x: c, y: c - 8, "text-anchor": "middle", class: "lbl", text: trunc(String(label).replace(/\.[a-z]+$/, ""), 15) }),
    sv("text", { x: c, y: c + 10, "text-anchor": "middle", class: "hexl", text: `${digits.slice(0, 8)}…${digits.slice(-4)}` }),
    sub ? sv("text", { x: c, y: c + 26, "text-anchor": "middle", class: "lbl", text: sub }) : null);
  return artFigure(svg, o.caption, o.cls);
}
// Candidates x gates: one mark per gate result, coloured by the recorded status.
function artMatrix(rows, cols, opts) {
  const o = opts || {};
  const cell = 24, padL = 30, padT = 70, W = padL + cols.length * cell + 10, H = padT + rows.length * cell + 6;
  const g = sv("g");
  cols.forEach((c, j) => g.append(sv("text", { x: padL + j * cell + cell / 2, y: padT - 10, class: "lbl", transform: `rotate(-55 ${padL + j * cell + cell / 2} ${padT - 10})`, text: trunc(c, 14) })));
  let k = 0;
  rows.forEach((row, i) => {
    g.append(sv("text", { x: 0, y: padT + i * cell + cell / 2 + 3.5, class: "lbl", text: String(i + 1).padStart(2, "0") }));
    cols.forEach((c, j) => {
      const res = row.cells[c];
      const cx = padL + j * cell + cell / 2, cy = padT + i * cell + cell / 2;
      const mark = res ? stagger(sv("circle", { cx, cy, r: 6.5, class: `node tone-fill-${res.tone}` }), k++) : sv("circle", { cx, cy, r: 1.5, class: "tone-fill-muted" });
      g.append(res ? sv("a", { href: recordHref(row.record), "data-tip-k": `${c} · ${row.label}`, "data-tip": `${res.status}${res.reason ? " — " + res.reason : ""}`, "aria-label": `${row.label}, ${c}: ${res.status}` }, sv("circle", { cx, cy, r: 12, class: "node-hit" }), mark) : mark);
    });
  });
  return artFigure(sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": o.label || "Gate matrix" }, g), o.caption, o.cls);
}

// ------------------------------------------------------------ 3-D stage
// The real-time stage stack (scene3d.js + vendored three.js) loads only when WebGL is
// available and motion is allowed; otherwise the SVG figure is shown instead.
let stageModule = null;
const activeStages = [];
function webglOK() {
  // Respect Data Saver and very weak devices: they get the SVG figure instead.
  const conn = navigator.connection;
  if ((conn && conn.saveData) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2)) return false;
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); }
  catch (_) { return false; }
}
function stageData(defs, records) {
  const times = records.map((r) => Date.parse(r.timestamp || "")).filter(Number.isFinite);
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const fams = new Map();
  for (const r of records) {
    if (!fams.has(r.family)) fams.set(r.family, []);
    const t = Date.parse(r.timestamp || "");
    fams.get(r.family).push({ id: r.id, tone: worstTone(r.headline),
      label: `${r.basis.basis}${(r.headline || []).length ? " · " + r.headline.flatMap((h) => h.tokens).slice(0, 3).join(" · ") : ""}`,
      t: Number.isFinite(t) && t1 > t0 ? (t - t0) / (t1 - t0) : 0.5 });
  }
  return { gates: defs.map((g) => ({ id: g.gate_id, hardware: !!g.hardware_required })),
    families: [...fams.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([name, recs]) => ({ name, records: recs })) };
}
// Returns a figure: the live stack when possible, else the fallback figure.
function stage(fallback, dataPromise, opts) {
  const o = opts || {};
  if (reducedMotion || !webglOK()) return fallback();
  const box = el("div", { class: `stage stage-${o.mode || "hero"} loading` });
  // an optional close-up label sits on top of the live canvas
  if (o.callout) box.append(o.callout);
  const fig = el("figure", { class: "art stage-fig reveal" }, box, el("figcaption", null, o.caption),
    // the records on the stage, for screen readers; the canvas itself is aria-hidden
    o.records ? el("ul", { class: "sr", "aria-label": "Records on this stage" }, o.records.map((r) => el("li", null, link(recordHref(r.id), r.id)))) : null);
  Promise.all([stageModule || (stageModule = import("/static/scene3d.js")), dataPromise]).then(([mod, data]) => {
    if (!box.isConnected) return;
    const ctl = mod.mountStack(box, data, {
      mode: o.mode,
      progress: o.progress,
      onHover: (rec, x, y) => (rec ? showTipPoint(x, y, rec.id, rec.label) : hideTip()),
      onSelect: (rec) => { location.hash = recordHref(rec.id); },
      onCloseUp: o.onCloseUp || null,
    });
    activeStages.push(ctl);
    box.classList.remove("loading");
    box.classList.add("live");
    if (o.onLive) o.onLive();
  }).catch(() => {
    if (fig.isConnected) { const fb = fallback(); fig.replaceWith(fb); fb.classList.add("in"); }
  });
  return fig;
}
function sectionProgress(node) {
  return () => {
    const h = window.innerHeight;
    // Pinned (wide screens): progress runs across the whole tall section while the stage stays put.
    const sec = node.closest(".pinned-scene");
    if (sec && window.matchMedia("(min-width: 901px)").matches) {
      const r = sec.getBoundingClientRect();
      return Math.min(1, Math.max(0, (h - r.top) / r.height));
    }
    // Unpinned (phones): finish by the time the stage reaches the top of the screen.
    const r = node.getBoundingClientRect();
    return Math.min(1, Math.max(0, (h - r.top) / (h + r.height) / 0.7));
  };
}
function sectionStage(hw, records) {
  const fallback = () => artPlates(hw.map((g) => ({ label: g.gate_id, value: "hardware only", locked: true, tone: "gated", href: "#/gates", tip: g.title })),
    { label: "Hardware-gated gates", caption: "Drawn from master/validation_gates.yaml · one plate per gate that omits PASS · hatched = closable only by measured hardware evidence" });
  const holder = el("div", { class: "stage-holder" });
  // The close-up label: it appears once the camera has reached the chip (amount above 0.8).
  const callout = el("p", { class: "stage-callout", "aria-hidden": "true" }, SECTION_CALLOUT);
  holder.append(stage(fallback, getCached("/api/gates").then((g) => stageData(g.definitions.gates || [], records)),
    { mode: "section", caption: SECTION_CAPTION, progress: sectionProgress(holder), records,
      callout,
      onCloseUp: (a) => callout.classList.toggle("show", a > 0.8),
      // the section pins its stage on wide screens once the live stack is running
      onLive: () => { const sec = holder.closest("section"); if (sec) sec.classList.add("pinned-scene"); } }));
  return holder;
}
const SECTION_CALLOUT = "Illustrative chip: procedural artwork, not a QMHP device design and not a measurement.";
const SECTION_CAPTION = "The same stack, separated, with the camera descending to the sample package. The chip, bond wires, coax and flex lines are illustrative artwork, not a QMHP device design and not a measurement. Each junction marker is tinted by one record's headline status. Violet-rimmed plates are gates that only measured hardware evidence can close. This is not a model of QMHP or any real hardware.";
const STAGE_CAPTION = "Original 3-D illustration, drawn live from this checkout. Plates are frozen gates; a violet rim marks a hardware-gated gate. One coax line per record family; the other lines are unlabelled wiring. Beads are records, coloured by headline status. The chip is illustrative artwork, not a QMHP device design and not a measurement. This is not a model of QMHP or any real hardware.";

// Reduced motion is read at load and kept current if the setting changes. The header
// gains its background once the page has scrolled; nothing else reacts to scrolling.
const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
let reducedMotion = motionQuery.matches;
motionQuery.addEventListener("change", (e) => { reducedMotion = e.matches; });
function onScroll() {
  let ticking = false;
  const update = () => {
    document.body.classList.toggle("scrolled", window.scrollY > 40);
    ticking = false;
  };
  window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  update();
}

// Badge detail popover: hover (mouse), focus (keyboard) or tap (touch) shows it;
// Escape, a second tap or a tap elsewhere closes it.
const tip = el("div", { id: "tip", class: "tip", role: "tooltip" });
let tipFor = null, tipPinned = false;
function showTip(target, pinned) {
  const k = target.getAttribute("data-tip-k") || "", v = target.getAttribute("data-tip") || "";
  clear(tip);
  tip.append(k ? el("span", { class: "tip-k" }, k) : null, el("span", { class: "tip-v" }, v),
    pinned ? el("span", { class: "tip-hint" }, "Esc or tap elsewhere to close") : null);
  tip.classList.add("show");
  tip.classList.toggle("pinned", !!pinned);
  const r = target.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
  const left = Math.min(Math.max(12, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - 12);
  let top = r.bottom + 10;
  if (top + th > window.innerHeight - 12) top = Math.max(12, r.top - th - 10);
  tip.style.setProperty("left", `${left}px`);
  tip.style.setProperty("top", `${top}px`);
  if (tipFor && tipFor !== target && tipFor.tagName === "BUTTON") tipFor.setAttribute("aria-expanded", "false");
  tipFor = target;
  tipPinned = !!pinned;
  if (target.tagName === "BUTTON") target.setAttribute("aria-expanded", pinned ? "true" : "false");
}
function showTipPoint(x, y, k, v) {
  clear(tip);
  tip.append(el("span", { class: "tip-k" }, k), el("span", { class: "tip-v" }, v));
  tip.classList.add("show");
  tip.classList.remove("pinned");
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  const left = Math.min(Math.max(12, x + 16), window.innerWidth - tw - 12);
  const top = Math.min(Math.max(12, y + 18), window.innerHeight - th - 12);
  tip.style.setProperty("left", `${left}px`);
  tip.style.setProperty("top", `${top}px`);
  tipFor = null;
  tipPinned = false;
}
function hideTip() {
  tip.classList.remove("show", "pinned");
  if (tipFor && tipFor.tagName === "BUTTON") tipFor.setAttribute("aria-expanded", "false");
  tipFor = null;
  tipPinned = false;
}
function setupTips() {
  document.documentElement.append(tip);
  const at = (e) => (e.target && e.target.closest ? e.target.closest("[data-tip]") : null);
  document.addEventListener("pointerover", (e) => { const t = at(e); if (t && !tipPinned && e.pointerType === "mouse") showTip(t, false); });
  document.addEventListener("pointerout", (e) => { const t = at(e); if (t && !tipPinned && t === tipFor && !t.contains(e.relatedTarget)) hideTip(); });
  document.addEventListener("focusin", (e) => { const t = at(e); if (t) showTip(t, false); else if (!tipPinned) hideTip(); });
  document.addEventListener("click", (e) => {
    const t = e.target && e.target.closest ? e.target.closest("button[data-tip]") : null;
    if (t) { if (tipFor === t && tipPinned) hideTip(); else showTip(t, true); return; }
    if (tipPinned && !tip.contains(e.target)) hideTip();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  window.addEventListener("scroll", () => { if (tipFor) hideTip(); }, { passive: true });
}

function candidateArt(cands) {
  if (!cands.length) return null;
  const cols = [...new Set(cands.flatMap((c) => c.gates.map((g) => g.gate_id)))];
  const rows = cands.map((c) => ({ label: `${c.candidate_id} @ ${c.record_id}`, record: c.record_id,
    cells: Object.fromEntries(c.gates.map((g) => [g.gate_id, { tone: g.tone, status: g.status, reason: g.reason }])) }));
  return artMatrix(rows, cols, { label: "Candidate gate results", caption: `Drawn from ${rows.length} candidate gate reports · row = candidate · column = gate · colour = recorded status · select a mark for its reason` });
}
function provenanceArt(m) {
  const c = m && m.present ? (m.checks || []).find((x) => x.measured) || (m.checks || [])[0] : null;
  if (!c) return null;
  const name = c.path.split("/").pop();
  return artSigil(c.measured || c.declared, name, `recomputed: ${c.status}`,
    { caption: `Drawn from the SHA-256 of ${c.path}, recomputed when this page loaded · one tick per hex digit · tick length = digit value` });
}

// ================================================================== views
async function viewOverview() {
  const [d, cls, recs] = await Promise.all([get("/api/overview"), getCached("/api/classification"), get("/api/records")]);
  const legend = Object.fromEntries(cls.families.map((f) => [f.family, f]));
  const measuredCount = d.by_basis.MEASURED || 0;
  const out = [];

  // 01 - hero: the statement, and the evidence itself drawn as a lattice
  out.push(el("section", { class: "hero bleed" }, el("div", { class: "wrap" },
    el("div", { class: "hero-grid" },
      el("div", null,
        eyebrow(null, "QMHP-CEM — Computational Engineering Model"),
        el("h1", { class: "display" },
          el("span", { class: "line" }, "Evidence in"), " ",
          el("span", { class: "line" }, "this checkout")),
        el("p", { class: "hero-lead" }, "This page lists every evidence record, gate and recorded digest in this checkout. It separates what was computed from what was only declared, and what still requires hardware evidence. Each evidence basis states the rule that assigned it."),
        el("div", { class: "hero-ctas" },
          el("a", { class: "btn solid", href: "#/records" }, "Explore evidence records", arrow()),
          el("a", { class: "btn", href: "#/classification" }, "How labels are assigned", arrow()))),
      recs.records.length ? stage(
        () => artLattice(recs.records, { rowH: Math.max(40, Math.min(150, 380 / Math.max(1, new Set(recs.records.map((r) => r.family)).size))), grid: true }),
        getCached("/api/gates").then((g) => stageData(g.definitions.gates || [], recs.records)),
        { mode: "hero", caption: STAGE_CAPTION, progress: () => Math.min(1, window.scrollY / (window.innerHeight * 0.9)), records: recs.records }) : null),
    el("div", { class: "hero-stats" },
      [[d.counts.records, "Records", "#/records"], [d.counts.candidates, "Candidates evaluated", "#/candidates"],
        [d.hardware_gated_gates.length, "Hardware-gated gates", "#/gates"], [measuredCount, "Measured records", "#/classification"]]
        .map(([v, k, href]) => el("a", { href }, el("span", { class: "v" }, String(v)), el("span", { class: "k" }, k)))))));

  // 02 - now: the latest verdicts, before anything else
  out.push(el("section", { class: "now bleed", "aria-label": "Latest status" }, el("div", { class: "wrap now-inner" },
    el("div", null, el("h2", null, "Latest records"), el("p", { class: "small muted" }, "The newest record in each family, with its own headline status.")),
    el("div", { class: "now-rows" }, d.latest_by_family.map((r) => el("a", { class: "now-row", href: recordHref(r.id) },
      el("span", { class: "fam" }, r.family),
      el("span", { class: "rid" }, r.id, el("small", null, fmtTs(r.timestamp))),
      el("span", { class: "row" }, basisBadge(r.basis, false, true), statusBadges(r.headline, 4, true)),
      el("span", { class: "arr", "aria-hidden": "true" }, "→")))))));

  // 03 - the boundary, stated
  const basisRows = Object.entries(d.by_basis).map(([b, n]) => el("a", { class: "spec-row", href: `#/records?basis=${b}` },
    el("span", { class: "k" }, basisBadge(b, false, true)), el("span", { class: "v" }, (cls.bases.find((x) => x.basis === b) || {}).explanation || ""),
    el("span", { class: "n" }, String(n))));
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap split" },
    el("div", { class: "reveal" }, eyebrow(null, "The hardware boundary"),
      el("h2", { class: "statement" }, "A computational PASS is ", el("em", null, "not"), " hardware validation.")),
    el("div", { class: "reveal d1" },
      el("p", { class: "copy" }, d.measured_statement, " Every record carries an evidence basis assigned by an explicit, ordered rule, and every status badge quotes the record's own words."),
      ...d.notes.map((n) => el("div", { class: "notice warn" }, el("span", { class: "ico" }, "NOTE"), el("div", { class: "body" }, n))),
      el("div", { class: "spec mt" }, basisRows)))));

  // 04 - gates only hardware can close, drawn as a locked stage stack
  const hw = d.hardware_gated_gates;
  const hwRows = hw.map((g) => el("div", { class: "spec-row" },
    el("span", { class: "k" }, g.gate_id), el("span", { class: "v" }, g.title),
    el("span", null, badge("HARDWARE-GATED", "gated", { k: g.gate_id, v: g.pass_permitted ? "PASS permitted" : "PASS is not in this gate's frozen allowed statuses." }))));
  out.push(el("section", { class: "section band-dark bleed" }, el("div", { class: "wrap split media-left" },
    hw.length ? sectionStage(hw, recs.records) : el("div"),
    el("div", { class: "reveal d1" }, eyebrow(null, "Hardware-gated gates"),
      el("h2", { class: "statement" }, "Gates that only measured hardware evidence can close"),
      el("p", { class: "copy mt" }, "These gates do not allow PASS in their frozen allowed statuses. No simulated or model-derived result in this repository can close them."),
      el("div", { class: "spec mt" }, hwRows.length ? hwRows : el("p", { class: "empty" }, "No frozen gate definitions in this checkout."))))));

  // 05 - status families as figures
  const figs = Object.entries(d.by_status_family).map(([f, n]) => el("a", { class: "figure", href: `#/records?status=${q(f)}`, "aria-label": `${n} records: ${f}. ${(legend[f] || {}).meaning || ""}` },
    el("div", { class: "v" }, String(n)), el("div", { class: "k" }, badge(f, (legend[f] || {}).tone))));
  out.push(el("section", { class: "section tight bleed" }, el("div", { class: "wrap" },
    el("div", { class: "sec-head reveal" }, el("div", null, el("h2", null, "Headline status families")),
      el("p", null, "Records whose own headline fields carry a token in that family. A family only picks the colour; the token is always the record's.")),
    el("div", { class: "figures reveal d1" }, figs))));

  // 06/07 - frozen master and checkout
  const m = d.master || {};
  const co = d.checkout;
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap split" },
    el("div", { class: "reveal" }, eyebrow(null, "Frozen master"),
      el("div", { class: "spec" },
        [["Revision", m.revision], ["Status", m.status], ["Date", m.date]].map(([k, v]) => el("div", { class: "spec-row" }, el("span", { class: "k" }, k), el("span", { class: "v" }, v || "—"), el("span"))),
        (m.issues || []).map((iss) => el("div", { class: "spec-row" }, el("span", { class: "k" }, String(iss.field).replace(/_/g, " ")), el("span", { class: "v small" }, excerpt(iss.statement, 220)), badge(iss.status || "?", "caution")))),
      el("p", { class: "mt" }, link("#/provenance", "Master digests, recomputed →", "link"))),
    el("div", { class: "reveal d1" }, eyebrow(null, "This checkout"),
      el("div", { class: "spec" },
        co.available ? [["Branch", co.branch || (co.detached ? "(detached HEAD)" : "?")], ["HEAD", el("span", { class: "hash" }, co.head_sha)],
          ["Read from", "git's own HEAD and ref files; no git command is run"]].map(([k, v]) => el("div", { class: "spec-row" }, el("span", { class: "k" }, k), el("span", { class: "v" }, v), el("span")))
          : el("p", { class: "muted" }, `Commit identity unavailable: ${co.reason || "no git metadata"}.`))))));

  // 08 - what the viewer will never do
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap split" }, el("div", { class: "reveal" }, eyebrow(null, "Unavailable by design"),
      el("h2", null, "Actions this viewer does not provide."),
      el("p", { class: "copy mt" }, "These actions are not implemented, so there is no hidden mode, flag or admin path."),
      el("a", { class: "btn mt", href: "#/unavailable" }, "All unavailable actions", arrow())),
    el("div", { class: "locked reveal d1" }, lockedList(d.capabilities.unavailable.map((u) => [u.action, u.reason]))))));
  return out;
}

async function viewUnavailable() {
  const c = await get("/api/capabilities");
  return [pageHero("Unavailable", "This viewer only displays records. The actions below would change scientific or repository state, or start an execution, so they are not implemented. There is no hidden mode, flag or admin path."),
    el("div", { class: "panel" }, kv([["HTTP methods served", c.http_methods.join(", ")], ["Writes", c.writes]])),
    el("div", { class: "panel locked" }, lockedList(c.unavailable.map((u) => [u.action, u.reason])))];
}

// -------------------------------------------------------------- records
async function viewRecords(params) {
  const d = await get("/api/records");
  const families = [...new Set(d.records.map((r) => r.family))].sort();
  const statusFams = d.families.map((f) => f.family);
  const state = { q: params.get("q") || "", basis: params.get("basis") || "", family: params.get("family") || "", status: params.get("status") || "" };
  const input = el("input", { type: "search", placeholder: "Filter by id or statement", value: state.q, "aria-label": "Filter records" });
  const sel = (name, opts, label) => {
    const s = el("select", { "aria-label": label }, el("option", { value: "" }, `All ${label}`),
      opts.map((o) => el("option", { value: o, selected: state[name] === o }, o)));
    s.addEventListener("change", () => { state[name] = s.value; render(); });
    return s;
  };
  input.addEventListener("input", () => { state.q = input.value; render(); });
  const count = el("span", { class: "count" });
  const holder = el("div");
  function render() {
    const needle = state.q.toLowerCase();
    const rows = d.records.filter((r) =>
      (!state.basis || r.basis.basis === state.basis) &&
      (!state.family || r.family === state.family) &&
      (!state.status || r.families.includes(state.status)) &&
      (!needle || r.id.toLowerCase().includes(needle) || (r.statement || "").toLowerCase().includes(needle)));
    count.textContent = `${rows.length} of ${d.records.length}`;
    const p = new URLSearchParams(Object.entries(state).filter(([, v]) => v));
    history.replaceState(null, "", `#/records${p.toString() ? "?" + p : ""}`);
    clear(holder);
    holder.append(table(["Record", "Recorded", "Basis", "Headline status (as recorded)", "Candidates / runs", "Manifest"],
      rows.map((r) => el("tr", null,
        el("td", { class: "id" }, link(recordHref(r.id), r.id)),
        el("td", { class: "nowrap small" }, fmtTs(r.timestamp)),
        el("td", null, basisBadge(r.basis)),
        el("td", null, el("div", { class: "row" }, statusBadges(r.headline, 6)), r.statement ? el("div", { class: "small muted" }, excerpt(r.statement, 160)) : null),
        el("td", { class: "small nowrap" }, `${r.candidate_count} / ${r.run_count}`),
        el("td", { class: "small nowrap" }, r.manifests.length ? `${r.manifests.length} ${plural(r.manifests.length, "manifest", "manifests")}` : el("span", { class: "muted" }, "none"))))));
    markScrollTables(holder);
  }
  render();
  return [pageHero("Records", "Every directory under results/, newest first. Status badges are tokens quoted from each record's own headline fields; hover, focus or tap one for its JSON path and full text.", d.records.length ? artLattice(d.records, { rowH: 40 }) : null),
    el("div", { class: "filters" }, input, sel("basis", ["SYNTHETIC", "SOLVED", "MEASURED", "ANALYSIS", "DECLARATION", "UNCLASSIFIED"], "bases"),
      sel("status", statusFams, "status families"), sel("family", families, "families"), count),
    holder];
}

async function viewRecord(id) {
  const r = await get(`/api/records/${q(id)}`);
  const out = [head(r.id, null, [link("#/records", "Evidence records"), " / ", r.family],
    el("div", { class: "row" }, basisBadge(r.basis, true)))];
  out.push(...computationalNotice(r.basis));
  out.push(el("div", { class: "panel mt" }, kv([
    ["Recorded", fmtTs(r.timestamp)],
    ["Evidence basis", el("span", null, basisBadge(r.basis), " ", el("span", { class: "small muted" }, `rule ${r.basis.rule}: ${r.basis.reason}`))],
    ["Primary document", r.primary ? link(fileHref(r.primary), r.primary) : "none"],
    ["Files", `${r.file_count}${r.files_truncated ? " (first 400 listed)" : ""}`],
    ["Statement", r.statement ? el("span", null, r.statement) : null],
  ])));
  if (r.headline.length) {
    out.push(el("h2", null, "Headline status, as recorded"),
      table(["JSON path", "Tokens", "Recorded text"], r.headline.map((h) => el("tr", null,
        el("td", { class: "id" }, h.path), el("td", null, el("div", { class: "row" }, statusBadges([h]))), el("td", { class: "reason" }, h.raw)))));
  }
  const reportPane = () => {
    const holder = el("div", { class: "panel" }, el("p", { class: "loading" }, "Loading report…"));
    get(`/api/file?path=${q(r.report)}`).then((f) => { clear(holder); holder.append(markdown(f.content || "", r.report)); })
      .catch((e) => { clear(holder); holder.append(el("p", { class: "error" }, e.message)); });
    return holder;
  };
  const primaryPane = () => {
    const holder = el("div", { class: "panel" }, el("p", { class: "loading" }, "Loading…"));
    get(`/api/file?path=${q(r.primary)}`).then((f) => { clear(holder); holder.append(fileBody(f)); })
      .catch((e) => { clear(holder); holder.append(el("p", { class: "error" }, e.message)); });
    return holder;
  };
  const statusesPane = () => table(["File", "JSON path", "Tokens", "Recorded text"], r.statuses.map((s) => el("tr", null,
    el("td", { class: "id" }, s.file), el("td", { class: "id" }, s.path), el("td", null, el("div", { class: "row" }, statusBadges([s]))),
    el("td", { class: "reason" }, excerpt(s.raw, 300)))));
  const filesPane = () => table(["Path"], r.files.map((p) => el("tr", null, el("td", { class: "id" }, link(fileHref(p), p)))));
  const provPane = () => provenancePanel(r);
  const candPane = () => el("div", null,
    r.candidates.length ? candidateTable(r.candidates.map((c) => ({ ...c, basis: r.basis }))) : el("p", { class: "empty" }, "No candidate directories in this record."),
    r.runs.length ? el("div", null, el("h3", null, "Runs listed in the record"), runTable(r.runs.map((x) => ({ ...x, record_id: r.id, basis: r.basis })))) : null);
  const linksPane = () => el("div", { class: "grid cols-2" },
    el("div", { class: "panel" }, el("h3", null, "Records this record names"),
      r.links.length ? el("ul", null, r.links.map((x) => el("li", null, link(recordHref(x), x, "mono")))) : el("p", { class: "empty" }, "None.")),
    el("div", { class: "panel" }, el("h3", null, "Named by"),
      r.referenced_by.length ? el("ul", null, r.referenced_by.map((x) => el("li", null,
        x.startsWith("results/") ? link(recordHref(x.slice(8)), x, "mono") : link(`#/experiments/${q(x.slice(12))}`, x, "mono"))))
        : el("p", { class: "empty" }, "No other record or experiment names this one.")));
  out.push(el("h2", null, "Contents"), tabs([
    r.report && { label: "Report", render: reportPane },
    r.primary && { label: "Primary JSON", render: primaryPane },
    { label: `All status statements (${r.statuses.length})`, render: statusesPane },
    { label: "Provenance and hashes", render: provPane },
    (r.candidates.length || r.runs.length) && { label: `Candidates (${r.candidates.length}) and runs (${r.runs.length})`, render: candPane },
    { label: "Related records", render: linksPane },
    { label: `Files (${r.file_count})`, render: filesPane },
  ]));
  return out;
}

function provenancePanel(r) {
  const res = el("div");
  const button = el("button", { type: "button", class: "chip", title: "Recomputes SHA-256 of the checked-out files. A read; nothing is written." },
    "Recompute manifest hashes (read-only)");
  button.addEventListener("click", async () => {
    button.disabled = true;
    clear(res);
    res.append(el("p", { class: "loading" }, "Hashing checked-out bytes…"));
    try {
      const v = await get(`/api/records/${q(r.id)}/verify`);
      clear(res);
      res.append(verifyResult(v));
    } catch (e) { clear(res); res.append(el("p", { class: "error" }, e.message)); }
    button.disabled = false;
  });
  const digests = r.declared_digests || [];
  return el("div", null,
    el("div", { class: "panel" },
      el("h3", null, "Byte manifests"),
      r.manifests.length ? el("ul", null, r.manifests.map((m) => el("li", null, link(fileHref(m), m, "mono")))) : el("p", { class: "empty" }, "This record has no manifest.sha256."),
      (r.digest_files || []).length ? el("p", { class: "small muted" }, `Other declared digest files (not byte-compared): ${r.digest_files.join(", ")}`) : null,
      r.manifests.length || (r.digest_files || []).length ? button : null, res),
    el("div", { class: "panel" }, el("h3", null, `Digests declared inside ${r.primary || "the record"} (${digests.length})`),
      el("p", { class: "small muted" }, "Declared by the record. Not recomputed here: many name files outside this record or bytes that are not committed."),
      table(["JSON path", "SHA-256 (declared)"], digests.map((x) => el("tr", null, el("td", { class: "id" }, x.path), el("td", { class: "hash" }, x.sha256))))));
}

function verifyResult(v) {
  const box = el("div", { class: "mt-s" });
  for (const m of v.manifests) {
    const counts = Object.entries(m.counts || {}).map(([k, n]) => badge(`${k} ${n}`, k === "MATCH" ? "positive" : k === "MISMATCH" ? "negative" : "caution"));
    box.append(el("h4", null, m.manifest), el("div", { class: "row" }, counts), m.error ? el("p", { class: "error" }, m.error) : null);
    const bad = (m.entries || []).filter((e) => e.status !== "MATCH");
    if (bad.length) {
      box.append(table(["File", "Status", "Declared", "Recomputed now"], bad.map((e) => el("tr", null,
        el("td", { class: "id" }, e.path || `line ${e.line}`), el("td", { class: `st-${(e.status || "").split(" ")[0]}` }, e.status),
        el("td", { class: "hash" }, e.declared || ""), el("td", { class: "hash" }, e.measured || "")))));
    }
    const ok = (m.entries || []).filter((e) => e.status === "MATCH");
    if (ok.length) {
      box.append(el("details", null, el("summary", { class: "small" }, `${ok.length} matching files`),
        table(["File", "SHA-256 (declared = recomputed)"], ok.map((e) => el("tr", null, el("td", { class: "id" }, e.path), el("td", { class: "hash" }, e.declared))))));
    }
  }
  for (const f of v.declared_digest_files || []) {
    box.append(el("div", { class: "notice warn" }, el("span", { class: "ico" }, "DECLARED"),
      el("div", { class: "body" }, el("div", { class: "mono small" }, f.path), el("pre", { class: "code" }, f.content), el("div", { class: "small" }, f.note))));
  }
  if (v.unlisted_count) {
    box.append(el("details", null, el("summary", { class: "small" }, `${v.unlisted_count} ${plural(v.unlisted_count, "file")} in the record ${v.unlisted_count === 1 ? "is" : "are"} not listed in any byte manifest`),
      el("ul", null, v.unlisted_files.map((p) => el("li", { class: "mono small" }, p)))));
  }
  box.append(el("p", { class: "small muted" }, `Recomputed ${fmtTs(v.measured_utc)}. ${v.note}`));
  return box;
}

// ------------------------------------------------------- candidates/runs
function candidateTable(cands) {
  return table(["Record", "Candidate", "Basis", "Candidate class", "Solver", "Convergence", "Overall gate status", "Gate statuses"],
    cands.map((c) => {
      const counts = {};
      for (const g of c.gates) counts[g.status] = (counts[g.status] || 0) + 1;
      const tone = Object.fromEntries(c.gates.map((g) => [g.status, g.tone]));
      return el("tr", null,
        el("td", { class: "id" }, link(recordHref(c.record_id), c.record_id)),
        el("td", { class: "id" }, link(fileHref(c.path), c.candidate_id)),
        el("td", null, basisBadge(c.basis)),
        el("td", null, c.classification ? badge(c.classification, "muted", "ENGINEERING-SEED: a bootstrap assumption where the frozen master is silent, not a QMHP requirement; never experimentally validated.") : ""),
        el("td", { class: "small" }, c.solver ? `${c.solver.name || "?"} ${c.solver.version || ""}` : "", c.solver && c.solver.classification ? el("div", { class: "muted" }, c.solver.classification) : null),
        el("td", null, c.convergence ? badge(c.convergence, c.convergence === "CONVERGED" ? "positive" : "caution") : ""),
        el("td", null, c.overall_status ? badge(c.overall_status, c.overall_tone) : ""),
        el("td", null, el("div", { class: "row" }, Object.entries(counts).map(([s, n]) => badge(`${s} ×${n}`, tone[s])))));
    }));
}
function runTable(runs) {
  return table(["Record", "Run", "Basis", "Status (as recorded)", "Solver status"], runs.map((x) => el("tr", null,
    el("td", { class: "id" }, link(recordHref(x.record_id), x.record_id)), el("td", { class: "id" }, x.name),
    el("td", null, basisBadge(x.basis)), el("td", null, x.status ? badge(x.status, x.tone) : el("span", { class: "muted" }, "none")),
    el("td", { class: "small" }, x.palace_status || ""))));
}
async function viewCandidates() {
  const d = await get("/api/candidates");
  return [pageHero("Candidates", "Candidates evaluated against the frozen gates, and the named runs each record lists. Dimensions the frozen master does not define are labelled ENGINEERING-SEED: a bootstrap assumption set by this software, not a QMHP requirement.", candidateArt(d.candidates)),
    ...computationalNotice("SOLVED"),
    el("h2", null, `Candidates (${d.candidates.length})`), candidateTable(d.candidates),
    el("h2", null, `Runs (${d.runs.length})`), runTable(d.runs)];
}

// ----------------------------------------------------------------- gates
async function viewGates() {
  const d = await get("/api/gates");
  const defs = d.definitions.gates || [];
  const out = [pageHero("Gates", "The frozen gate definitions, every gate result the records carry with its recorded reason, and each record's own headline verdicts.", defs.length ? artPlates(defs.map((g) => ({ label: g.gate_id, value: g.hardware_required ? "hardware only" : (g.required_evidence || []).join(", "), locked: g.hardware_required, tone: g.hardware_required ? "gated" : "neutral", tip: g.title })), { compact: true, label: "Frozen gate definitions", caption: "Drawn from master/validation_gates.yaml \u00b7 one plate per gate, in file order \u00b7 hatched = hardware-gated, PASS not permitted" }) : null), ...computationalNotice("SOLVED")];
  out.push(el("h2", null, "Frozen gate definitions"),
    el("p", { class: "muted" }, d.definitions.path ? ["From ", link(fileHref(d.definitions.path), d.definitions.path), ". Allowed statuses are frozen data; hardware gates omit PASS."] : "master/validation_gates.yaml is not present in this checkout."),
    table(["Gate", "Title", "Kind", "Severity", "Required evidence", "Allowed statuses", "Hardware"], defs.map((g) => el("tr", null,
      el("td", { class: "id" }, g.gate_id), el("td", null, g.title), el("td", { class: "small" }, g.kind), el("td", null, badge(g.severity, g.severity === "HARD" ? "negative" : "caution")),
      el("td", { class: "small mono" }, (g.required_evidence || []).join(", ")),
      el("td", { class: "small mono" }, (g.allowed_statuses || []).join(", ")),
      el("td", null, g.hardware_required ? badge("HARDWARE-GATED", "gated", "PASS is not an allowed status for this gate") : el("span", { class: "muted small" }, "computational"))))));

  const gateIds = defs.map((g) => g.gate_id);
  for (const row of d.results) for (const g of row.gates) if (!gateIds.includes(g.gate_id)) gateIds.push(g.gate_id);
  out.push(el("h2", null, `Gate results (${d.results.length} candidate evaluations)`),
    table(["Record / candidate", ...gateIds, "Overall"], d.results.map((row) => {
      const byId = Object.fromEntries(row.gates.map((g) => [g.gate_id, g]));
      return el("tr", null,
        el("td", { class: "id" }, link(recordHref(row.record_id), row.record_id), el("div", { class: "muted small" }, row.candidate_id)),
        ...gateIds.map((id) => el("td", null, byId[id] ? badge(byId[id].status, byId[id].tone, `${id}: ${byId[id].reason || ""}`) : el("span", { class: "muted" }, "–"))),
        el("td", null, row.overall_status ? badge(row.overall_status, "neutral") : ""));
    }), "matrix"));

  const gateSel = el("select", { "aria-label": "Gate" }, el("option", { value: "" }, "All gates"), gateIds.map((g) => el("option", { value: g }, g)));
  const reasonHolder = el("div");
  const renderReasons = () => {
    clear(reasonHolder);
    const rows = [];
    const seen = new Set();
    for (const row of d.results) for (const g of row.gates) {
      if (gateSel.value && g.gate_id !== gateSel.value) continue;
      const key = `${g.gate_id}|${g.status}|${g.reason}`;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push(el("tr", null, el("td", { class: "id" }, g.gate_id), el("td", null, badge(g.status, g.tone)),
        el("td", { class: "small" }, g.evidence_class || el("span", { class: "muted" }, "none")),
        el("td", { class: "reason" }, g.reason || ""),
        el("td", { class: "small nowrap" }, g.measured != null ? `${g.measured} ${g.units || ""}` : "")));
    }
    reasonHolder.append(table(["Gate", "Status", "Evidence class", "Recorded reason", "Measured value"], rows));
  };
  gateSel.addEventListener("change", renderReasons);
  renderReasons();
  out.push(el("h2", null, "Distinct recorded reasons"), el("div", { class: "filters" }, gateSel), reasonHolder);

  out.push(el("h2", null, "Record verdicts"), el("p", { class: "muted" }, "Campaign and study verdicts are the records' own fields, quoted. Hover a badge for its JSON path."),
    table(["Record", "Recorded", "Basis", "Headline verdicts"], d.record_verdicts.map((v) => el("tr", null,
      el("td", { class: "id" }, link(recordHref(v.record_id), v.record_id)), el("td", { class: "small nowrap" }, fmtTs(v.timestamp)),
      el("td", null, basisBadge(v.basis)), el("td", null, el("div", { class: "row" }, statusBadges(v.headline)))))));
  return out;
}

// ------------------------------------------------------------ provenance
async function viewProvenance() {
  const d = await get("/api/provenance");
  const m = d.master;
  const out = [pageHero("Provenance", d.note, provenanceArt(d.master))];
  if (m.present) {
    out.push(el("h2", null, "Frozen master layer"),
      el("div", { class: "panel" }, kv([["Revision", m.revision], ["Status", m.status], ["Date", m.date], ["Provenance file", link(fileHref(m.path), pathLabel(m.path))]]),
        m.evidence_boundary ? el("div", { class: "notice comp mt-s" }, el("span", { class: "ico" }, "BOUNDARY"),
          el("div", { class: "body" }, `measured_evidence_objects_present = ${m.evidence_boundary.measured_evidence_objects_present}; hardware_gates_closable = ${m.evidence_boundary.hardware_gates_closable}. ${m.evidence_boundary.statement || ""}`)) : null),
      table(["File", "Declared SHA-256", "Recomputed now", "Result"], m.checks.map((c) => el("tr", null,
        el("td", { class: "id" }, link(fileHref(c.path), pathLabel(c.path))), el("td", { class: "hash" }, c.declared), el("td", { class: "hash" }, c.measured || ""),
        el("td", { class: `st-${c.status.split(" ")[0]}` }, c.status)))));
    if (m.issues.length) {
      out.push(el("h3", null, "Open provenance questions recorded in the master"),
        table(["Field", "Recorded status", "Statement"], m.issues.map((i) => el("tr", null, el("td", { class: "id" }, i.field),
          el("td", null, badge(i.status || "?", "caution")), el("td", { class: "reason" }, softBreaks(i.statement))))));
    }
  }
  const holder = new Map();
  out.push(el("h2", null, "Records"), table(["Record", "Basis", "Manifests", "Recorded environment and digests", ""], d.records.map((r) => {
    const res = el("div");
    holder.set(r.record_id, res);
    const btn = r.manifests.length ? el("button", { type: "button", class: "chip", title: "Read-only re-hash" }, "Recompute") : null;
    if (btn) btn.addEventListener("click", async () => {
      btn.disabled = true; clear(res); res.append(el("span", { class: "loading small" }, "hashing…"));
      try { const v = await get(`/api/records/${q(r.record_id)}/verify`); clear(res); res.append(verifyResult(v)); }
      catch (e) { clear(res); res.append(el("span", { class: "error" }, e.message)); }
      btn.disabled = false;
    });
    const env = Object.entries(r.environment).map(([k, v]) => el("div", { class: "small" }, el("span", { class: "muted" }, `${k}: `), el("span", { class: "hash" }, String(v))));
    return el("tr", null, el("td", { class: "id" }, link(recordHref(r.record_id), r.record_id)), el("td", null, basisBadge(r.basis)),
      el("td", { class: "small" }, r.manifests.length ? r.manifests.map((x) => el("div", null, link(fileHref(x), pathLabel(x.split("/").pop())))) : el("span", { class: "muted" }, "none")),
      el("td", null, env.length ? env : el("span", { class: "muted small" }, "none recorded in the primary document"), res),
      el("td", null, btn));
  })));
  if (d.approvals.length) {
    out.push(el("h2", null, "Approval files (digests recomputed now)"),
      table(["Approval file", "State", "SHA-256"], d.approvals.map((a) => el("tr", null,
        el("td", { class: "id" }, link(fileHref(a.path), pathLabel(a.path))), el("td", null, badge(a.state, "muted")), el("td", { class: "hash" }, a.sha256)))));
  }
  return out;
}

// ------------------------------------------------------------ experiments
async function viewExperiments() {
  const d = await get("/api/experiments");
  const out = [pageHero("Experiments", "Frozen requirements and data contracts, then each experiment directory with the execution state its own files report.", d.frozen_contracts.length ? artPlates([...d.frozen_contracts.map((g) => ({ label: g.group, value: `${g.files.length} file${g.files.length === 1 ? "" : "s"}`, tone: "neutral", tip: g.label })), ...d.experiments.map((e) => ({ label: e.id, value: e.state.label, tone: e.state.tone, href: `#/experiments/${q(e.id)}`, tip: e.state.reason }))].slice(0, 12), { compact: true, label: "Frozen contracts and experiments", caption: `Drawn from this checkout \u00b7 one plate per frozen-contract group${d.experiments.length ? " and experiment" : ""} \u00b7 value = file count or stated execution state` }) : null)];
  out.push(el("h2", null, "Frozen contracts"), el("div", { class: "grid cols-2" }, d.frozen_contracts.map((g) => el("div", { class: "panel" },
    el("h3", null, g.label), el("ul", null, g.files.map((f) => el("li", null, link(fileHref(f.path), f.path, "mono"), el("span", { class: "muted small" }, `  ${fmtSize(f.size)}`))))))));
  out.push(el("h2", null, `Experiments (${d.experiments.length})`));
  if (!d.present) {
    out.push(el("div", { class: "notice warn" }, el("span", { class: "ico" }, "ABSENT"),
      el("div", { class: "body" }, "There is no experiments/ directory in this checkout. Experiments, predeclarations, approvals and execution logs held on other branches appear here only once they are part of the checked-out commit.")));
    return out;
  }
  out.push(table(["Experiment", "Basis", "Execution state (as stated)", "Question / linked records", "Files"], d.experiments.map((e) => el("tr", null,
    el("td", { class: "id" }, link(`#/experiments/${q(e.id)}`, e.id)), el("td", null, basisBadge(e.basis)),
    el("td", null, badge(e.state.label, e.state.tone, e.state.reason), e.state.source ? el("div", { class: "small muted" }, e.state.source.split("/").pop()) : null),
    el("td", { class: "reason" }, e.question ? excerpt(e.question, 220) : null,
      e.linked_records.length ? el("div", { class: "small" }, `${e.linked_records.length} linked ${plural(e.linked_records.length, "record")}`) : null),
    el("td", { class: "small" }, `${e.file_count}`, el("div", { class: "muted" }, e.roles.join(", ")))))));
  return out;
}

async function viewExperiment(id) {
  const [e, recs] = await Promise.all([get(`/api/experiments/${q(id)}`), get("/api/records")]);
  const recById = Object.fromEntries(recs.records.map((r) => [r.id, r]));
  const out = [head(e.id, e.question, [link("#/experiments", "Experiments"), " / ", e.id], el("div", { class: "row" }, basisBadge(e.basis, true)))];
  out.push(el("div", { class: "panel" }, kv([
    ["Execution state", el("span", null, badge(e.state.label, e.state.tone), " ", el("span", { class: "small muted" }, e.state.reason))],
    ["Stated in", e.state.source ? link(fileHref(e.state.source), e.state.source) : "no state file"],
    ["Basis", el("span", { class: "small muted" }, `rule ${e.basis.rule}: ${e.basis.reason}`)],
  ])));
  if (e.synthetic_files.length) {
    out.push(el("div", { class: "notice synthetic" }, el("span", { class: "ico" }, "SYNTHETIC FILES"),
      el("div", { class: "body" }, "These files declare synthetic or fixture content; they are not evidence about the QMHP candidate: ",
        e.synthetic_files.map((s) => el("span", { class: "mono small" }, ` ${s.file} (${s.path})`)))));
  }
  out.push(el("div", { class: "panel locked" }, lockedList([[`Execute ${e.id}`, "Unavailable. Execution needs the repository's approved launcher and a scoped human approval, outside this viewer."],
    ["Create or edit an approval", "Unavailable. Approval files are displayed, never written."]])));
  out.push(el("h2", null, "Linked results records"), e.linked_records.length ? table(["Record", "Basis", "Headline status"], e.linked_records.map((rid) => {
    const r = recById[rid] || {};
    return el("tr", null, el("td", { class: "id" }, link(recordHref(rid), rid)), el("td", null, r.basis ? basisBadge(r.basis) : ""), el("td", null, el("div", { class: "row" }, statusBadges(r.headline, 6))));
  })) : el("p", { class: "empty" }, "No results record is named by this experiment's JSON."));
  if (e.approvals.length) {
    out.push(el("h2", null, "Approval files"), el("p", { class: "muted" }, "Displayed only. The viewer cannot validate whether an approval authorises anything."),
      ...e.approvals.map((a) => el("div", { class: "panel" }, el("div", { class: "row" }, badge(a.state, a.tone), link(fileHref(a.path), a.path, "mono")),
        kv([["Authorises", a.authorises != null ? excerpt(typeof a.authorises === "string" ? a.authorises : JSON.stringify(a.authorises), 600) : null],
          ["Scope", a.scope != null ? excerpt(typeof a.scope === "string" ? a.scope : JSON.stringify(a.scope), 600) : null],
          ["Run label", a.run_label], ["Does not authorise", a.does_not_authorise != null ? excerpt(JSON.stringify(a.does_not_authorise), 600) : null],
          ["SHA-256 (recomputed now)", el("span", { class: "hash" }, a.sha256)]]))));
  }
  const groups = {};
  for (const f of e.files) (groups[f.role] = groups[f.role] || []).push(f);
  const order = ["predeclaration", "frozen-configuration", "approval", "execution-log", "attempt-spent", "withdrawal", "review", "documentation", "data", "manifest", "code"];
  out.push(el("h2", null, "Files by role"), table(["Role", "File", "Size", "Status statements"],
    order.filter((r) => groups[r]).flatMap((role) => groups[role].map((f) => el("tr", null,
      el("td", { class: "small nowrap" }, role), el("td", { class: "id" }, link(fileHref(f.path), f.name)), el("td", { class: "small nowrap" }, fmtSize(f.size)),
      el("td", null, el("div", { class: "row" }, statusBadges(f.statuses, 5)), f.parse_error ? el("span", { class: "error small" }, f.parse_error) : null))))));
  if (e.readme) {
    const holder = el("div", { class: "panel" }, el("p", { class: "loading" }, "Loading README…"));
    get(`/api/file?path=${q(e.readme)}`).then((f) => { clear(holder); holder.append(markdown(f.content || "", e.readme)); })
      .catch((err) => { clear(holder); holder.append(el("p", { class: "error" }, err.message)); });
    out.push(el("h2", null, "README"), holder);
  }
  return out;
}

// ------------------------------------------------------------------ audit
async function viewAudit() {
  const [d, ap] = await Promise.all([get("/api/audit"), get("/api/approvals")]);
  const out = [pageHero("Audit trail", d.note)];
  if (d.experiment_states.length) {
    out.push(el("h2", null, "Execution state by experiment"), table(["Experiment", "State (as stated)", "Why", "Source"], d.experiment_states.map((s) => el("tr", null,
      el("td", { class: "id" }, link(`#/experiments/${q(s.experiment)}`, s.experiment)), el("td", null, badge(s.label, s.tone)),
      el("td", { class: "reason" }, s.reason), el("td", { class: "small" }, s.source ? link(fileHref(s.source), s.source.split("/").pop()) : "")))));
  }
  out.push(el("h2", null, `Approval files (${ap.approvals.length})`), el("div", { class: "notice info" }, el("span", { class: "ico" }, "DISPLAY ONLY"), el("div", { class: "body" }, ap.statement)),
    table(["File", "State", "Approved by / when", "What it names", "SHA-256 (recomputed now)"], ap.approvals.map((a) => el("tr", null,
      el("td", { class: "id" }, link(fileHref(a.path), a.path)), el("td", null, badge(a.state, a.tone)),
      el("td", { class: "small" }, a.approved_by ? excerpt(a.approved_by, 140) : "", a.approved_utc ? el("div", { class: "muted" }, a.approved_utc) : null),
      el("td", { class: "reason" }, excerpt(typeof a.authorises === "string" ? a.authorises : (a.what || a.run_label || JSON.stringify(a.authorises || a.scope || "")), 260),
        a.one_attempt ? el("div", { class: "small muted" }, `one attempt: run ${a.one_attempt.run_number}, attempt ${a.one_attempt.run_attempt}`) : null),
      el("td", { class: "hash" }, shortSha(a.sha256))))));

  const kinds = [...new Set(d.events.map((e) => e.kind))].sort();
  const sel = el("select", { "aria-label": "Event kind" }, el("option", { value: "" }, "All events"), kinds.map((k) => el("option", { value: k }, k)));
  const tl = el("div", { class: "timeline" });
  const render = () => {
    clear(tl);
    for (const ev of d.events.filter((x) => !sel.value || x.kind === sel.value)) {
      tl.append(el("div", { class: `ev k-${ev.kind.split(" ")[0]}` },
        el("div", { class: "when" }, fmtTs(ev.ts)),
        el("div", { class: "what" }, ev.kind, "  ", ev.basis ? basisBadge(ev.basis) : null, " ",
          ev.record_id ? link(recordHref(ev.record_id), ev.ref, "mono") : link(fileHref(ev.ref), ev.ref, "mono")),
        ev.headline ? el("div", { class: "row" }, statusBadges(ev.headline, 6)) : null,
        ev.summary ? el("div", { class: "small muted" }, excerpt(ev.summary, 300)) : null));
    }
  };
  sel.addEventListener("change", render);
  render();
  out.push(el("h2", null, `Timeline (${d.events.length} events)`), el("div", { class: "filters" }, sel), tl);
  return out;
}

// ------------------------------------------------------------ corrections
async function viewCorrections() {
  const d = await get("/api/corrections");
  const types = [...new Set(d.items.map((i) => i.type))].sort();
  const sel = el("select", { "aria-label": "Type" }, el("option", { value: "" }, "All types"), types.map((t) => el("option", { value: t }, t)));
  const holder = el("div");
  const render = () => {
    clear(holder);
    const items = d.items.filter((i) => !sel.value || i.type === sel.value);
    if (!items.length) holder.append(el("p", { class: "empty" }, "No correction, supersession, withdrawal or retraction statements were found."));
    for (const i of items) {
      holder.append(el("div", { class: "panel" },
        el("div", { class: "row" }, badge(i.type, i.type === "WITHDRAWAL" || i.type === "RETRACTION" ? "muted" : "caution"),
          i.ref.startsWith("results/") ? link(recordHref(i.ref.slice(8)), i.ref, "mono") : i.ref.startsWith("experiments/") ? link(`#/experiments/${q(i.ref.slice(12))}`, i.ref, "mono") : link(fileHref(i.ref), i.ref, "mono")),
        el("div", { class: "small muted my-xs" }, i.path ? link(fileHref(i.path), i.path) : "", i.json_path ? `  ›  ${i.json_path}` : ""),
        el("pre", { class: "code wrap-pre" }, i.excerpt),
        i.links.length ? el("div", { class: "row small" }, "Names: ", i.links.map((x) => link(recordHref(x), x, "mono"))) : null));
    }
  };
  sel.addEventListener("change", render);
  render();
  return [pageHero("Corrections", "Corrections in this repository are made as new linked records; the originals are preserved."),
    el("div", { class: "notice info" }, el("span", { class: "ico" }, "SCOPE"), el("div", { class: "body" }, d.statement)),
    el("div", { class: "filters mt" }, sel, el("span", { class: "count" }, `${d.items.length} entries`)), holder];
}

// --------------------------------------------------------- classification
async function viewClassification() {
  const d = await get("/api/classification");
  const out = [pageHero("Classification", "Two questions are kept apart: what kind of evidence a record is (its basis), and what the record says about itself (its status tokens). Neither is invented by the viewer.")];
  out.push(...computationalNotice("SOLVED"));
  out.push(el("div", { class: "notice info" }, el("span", { class: "ico" }, "MEASURED"), el("div", { class: "body" }, d.measured_statement)));
  out.push(el("div", { class: "grid cols-3 mt" }, d.bases.map((b) => el("div", { class: "panel" },
    el("div", { class: "row" }, basisBadge(b.basis, true), el("span", { class: "count" }, `${b.count} ${plural(b.count, "record")}`)),
    el("p", { class: "small mt-s" }, b.explanation)))));
  out.push(el("h2", null, "How a results record's basis is assigned"), el("p", { class: "muted" }, "Rules are tried in order; the first match wins. Each record page shows which rule fired and why."),
    table(["Rule", "Basis", "Condition"], d.record_rules.map((r) => el("tr", null, el("td", { class: "id" }, r.id), el("td", null, basisBadge(r.basis)), el("td", { class: "reason" }, r.rule)))),
    el("h3", null, "Experiments"),
    table(["Rule", "Basis", "Condition"], d.experiment_rules.map((r) => el("tr", null, el("td", { class: "id" }, r.id), el("td", null, basisBadge(r.basis)), el("td", { class: "reason" }, r.rule)))));
  out.push(el("h2", null, "Status families"), el("p", { class: "muted" }, "A family only chooses a colour and a filter. The badge text is always the token the record wrote."),
    table(["Family", "Meaning"], d.families.map((f) => el("tr", null, el("td", null, badge(f.family, f.tone)), el("td", { class: "reason" }, f.meaning)))));
  out.push(el("h2", null, "Terms used"), kv([
    ["Frozen", "Fixed by a released master file, such as master/validation_gates.yaml. This viewer never changes it."],
    ["Headline status", "The record's own status tokens, quoted as written in its JSON. The viewer does not assign them."],
    ["ENGINEERING-SEED", "A bootstrap assumption where the frozen master is silent, per the specification. Not a QMHP requirement; never experimentally validated."],
    ["HARDWARE-GATED", "A gate whose frozen definition does not allow PASS. Computational and synthetic evidence never closes it."],
  ]));
  out.push(el("h2", null, "Records by basis"));
  for (const b of d.bases) {
    const recs = d.records_by_basis[b.basis] || [];
    out.push(el("details", { class: "panel", open: recs.length && recs.length < 12 ? true : null },
      el("summary", null, basisBadge(b.basis), `  ${recs.length} ${plural(recs.length, "record")}`),
      recs.length ? el("ul", null, recs.map((r) => el("li", null, link(recordHref(r.id), r.id, "mono"), "  ",
        el("span", { class: "small muted" }, `${r.basis.rule}: ${r.basis.reason}`)))) : el("p", { class: "empty" }, "None.")));
  }
  return out;
}

// ------------------------------------------------------------- documents
async function viewDocuments() {
  const d = await get("/api/documents");
  const input = el("input", { type: "search", placeholder: "Filter documents", "aria-label": "Filter documents" });
  const holder = el("div");
  const render = () => {
    const n = input.value.toLowerCase();
    clear(holder);
    holder.append(table(["Document", "Path", "Size"], d.documents.filter((x) => !n || x.path.toLowerCase().includes(n) || (x.title || "").toLowerCase().includes(n))
      .map((x) => el("tr", null, el("td", null, link(fileHref(x.path), x.title || x.path)), el("td", { class: "id small" }, x.path), el("td", { class: "small nowrap" }, fmtSize(x.size))))));
  };
  input.addEventListener("input", render);
  render();
  return [pageHero("Documents", "Markdown documents and record reports in this checkout. Each opens formatted, with the raw source one tab away."), el("div", { class: "filters" }, input), holder];
}

// ------------------------------------------------------------------ files
function fileBody(f) {
  if (f.kind === "directory") {
    return table(["Entry"], f.entries.map((x) => el("tr", null, el("td", { class: "id" }, link(fileHref(x.path), x.name + (x.is_dir ? "/" : ""))))));
  }
  if (f.content == null) return el("p", { class: "muted" }, f.note || "Not displayable.");
  const raw = () => el("pre", { class: "code" }, f.content);
  if (f.kind === "markdown") return tabs([{ label: "Rendered", render: () => markdown(f.content, f.path) }, { label: "Raw", render: raw }]);
  if ((f.kind === "json" || f.kind === "yaml") && f.parsed !== null && f.parsed !== undefined) {
    return tabs([{ label: "Tree", render: () => jsonTree(f.parsed) }, { label: "Raw", render: raw }]);
  }
  return raw();
}
async function viewFile(params) {
  const path = params.get("path") || "";
  const f = await get(`/api/file?path=${q(path)}`);
  const parts = path.split("/");
  const crumbs = parts.map((p, i) => i < parts.length - 1 ? [link(fileHref(parts.slice(0, i + 1).join("/")), p), " / "] : p);
  return [head(parts[parts.length - 1] || path, null, crumbs),
    el("div", { class: "panel" }, kv([["Path", el("span", { class: "mono" }, f.path)], ["Kind", f.kind], ["Size", f.size != null ? fmtSize(f.size) : null],
      ["SHA-256 (recomputed now)", f.sha256_measured ? el("span", { class: "hash" }, f.sha256_measured) : null],
      ["Part of record", f.in_record ? link(recordHref(f.in_record.slice(8)), f.in_record) : null],
      ["Access", "Read-only. Displayed as text; it cannot be edited here."]]),
      f.parse_error ? el("p", { class: "error small" }, `Parse error: ${f.parse_error}`) : null),
    el("div", { class: "panel" }, fileBody(f))];
}

// ----------------------------------------------------------------- search
function highlight(text, needle) {
  const out = el("span");
  const low = text.toLowerCase();
  let i = 0;
  while (needle) {
    const j = low.indexOf(needle, i);
    if (j < 0) break;
    out.append(txt(text.slice(i, j)), el("mark", null, text.slice(j, j + needle.length)));
    i = j + needle.length;
  }
  out.append(txt(text.slice(i)));
  return out;
}
async function viewSearch(params) {
  const query = params.get("q") || "";
  document.getElementById("global-search").value = query;
  const d = await get(`/api/search?q=${q(query)}`);
  const needle = query.toLowerCase();
  const n = d.files_matched || 0;
  const found = n ? `${n} ${plural(n, "file")} matched${d.truncated ? " (first 200 shown)" : ""}.` : `No files match “${query}”.`;
  const out = [head(`Search: “${query}”`, d.note || `${found} Solver output directories and files over 1 MB are not searched.`)];
  if (d.records && d.records.length) {
    out.push(el("h2", null, "Records"), table(["Record", "Basis", "Headline"], d.records.map((r) => el("tr", null,
      el("td", { class: "id" }, link(recordHref(r.id), r.id)), el("td", null, basisBadge(r.basis)), el("td", null, el("div", { class: "row" }, statusBadges(r.headline, 5)))))));
  }
  out.push(el("h2", null, "Files"), table(["File", "Matches"], (d.hits || []).map((h) => el("tr", null,
    el("td", { class: "id" }, link(fileHref(h.path), h.path)),
    el("td", null, h.snippets.map((s) => el("div", { class: "small" }, el("span", { class: "muted mono" }, `${s.line}: `), highlight(s.text, needle))))))));
  return out;
}

// ----------------------------------------------------------------- router
const ROUTES = [
  [/^overview$/, () => viewOverview()],
  [/^experiments$/, () => viewExperiments()],
  [/^experiments\/(.+)$/, (m) => viewExperiment(m[1])],
  [/^records$/, (m, p) => viewRecords(p)],
  [/^records\/(.+)$/, (m) => viewRecord(m[1])],
  [/^candidates$/, () => viewCandidates()],
  [/^gates$/, () => viewGates()],
  [/^provenance$/, () => viewProvenance()],
  [/^audit$/, () => viewAudit()],
  [/^corrections$/, () => viewCorrections()],
  [/^classification$/, () => viewClassification()],
  [/^documents$/, () => viewDocuments()],
  [/^unavailable$/, () => viewUnavailable()],
  [/^file$/, (m, p) => viewFile(p)],
  [/^search$/, (m, p) => viewSearch(p)],
];
let routeSeq = 0;
async function route() {
  const hash = location.hash.replace(/^#\/?/, "") || "overview";
  const [rawPath, rawQuery] = hash.split("?");
  const path = decodeURIComponent(rawPath || "overview");
  const params = new URLSearchParams(rawQuery || "");
  const section = path.split("/")[0];
  for (const a of document.querySelectorAll("#nav a")) a.classList.toggle("active", a.dataset.r === section);
  const navItem = document.querySelector(`#nav a[data-r="${section}"]`);
  document.title = navItem ? `${navItem.textContent} · QMHP-CEM Evidence Viewer` : "QMHP-CEM Evidence Viewer";
  const seq = ++routeSeq;
  for (const [re, fn] of ROUTES) {
    const m = re.exec(path);
    if (!m) continue;
    clear(view);
    view.append(skeleton());
    try {
      const nodes = await fn(m, params);
      if (seq !== routeSeq) return;
      render([nodes].flat(Infinity).filter(Boolean), section === "overview");
    } catch (e) {
      if (seq !== routeSeq) return;
      render([el("div", { class: "page-head" }, el("div", null,
        el("h1", null, e.status === 404 ? "Not found" : e.status === 403 ? "Refused" : "Could not load"),
        el("p", { class: "error" }, e.message), e.detail ? el("p", { class: "muted" }, e.detail) : null,
        el("p", null, link("#/overview", "Back to the overview", "link"))))], false);
    }
    return;
  }
  render([el("div", { class: "page-head" }, el("div", null, el("h1", null, "No such page"),
    el("p", null, link("#/overview", "Back to the overview", "link"))))], false);
}

// Full-bleed sections go straight into <main>; everything else is grouped into the
// centred page column. With View Transitions available, pages cross-fade.
let rendered = false;
function render(nodes, onHero) {
  const apply = () => {
    while (activeStages.length) { try { activeStages.pop().dispose(); } catch (_) { /* already gone */ } }
    clear(view);
    window.scrollTo(0, 0);
    document.body.classList.toggle("on-hero", onHero);
    hideTip();
    let column = null;
    for (const node of nodes) {
      if (node.classList && node.classList.contains("bleed")) {
        column = null;
        view.append(node);
      } else {
        if (!column) { column = el("div", { class: "wrap page-body" }); view.append(column); }
        column.append(node);
      }
    }
    markScrollTables(view);
    const h1 = view.querySelector("h1");
    if (h1) { h1.setAttribute("tabindex", "-1"); h1.focus({ preventScroll: true }); } else view.focus({ preventScroll: true });
  };
  if (rendered && document.startViewTransition && !reducedMotion) document.startViewTransition(apply);
  else apply();
  rendered = true;
}

async function boot() {
  setupTips();
  window.addEventListener("resize", () => markScrollTables(view), { passive: true });
  const search = document.getElementById("global-search");
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); location.hash = `#/search?q=${q(search.value.trim())}`; }
  });
  try {
    const co = await getCached("/api/checkout");
    const where = co.available ? `Checkout ${co.branch || "detached"} @ ${shortSha(co.head_sha)}` : "Checkout: no git metadata";
    document.querySelectorAll(".checkout-text").forEach((n) => { n.textContent = where; });
    const cls = await getCached("/api/classification");
    document.querySelectorAll(".measured-text").forEach((n) => { n.textContent = cls.measured_statement; });
  } catch (_) { /* the page still works without the ticker text */ }
  window.addEventListener("hashchange", route);
  onScroll();
  route();
}
boot();
