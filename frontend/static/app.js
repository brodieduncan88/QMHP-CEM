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

// ---------------------------------------------------------------------- DOM
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
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}
const txt = (s) => document.createTextNode(s == null ? "" : String(s));
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function link(href, label, cls) { return el("a", { href, class: cls }, label); }
const fileHref = (path) => `#/file?path=${q(path)}`;
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

// ------------------------------------------------------------------- badges
function badge(label, tone, title) {
  return el("span", { class: `badge tone-${tone || "neutral"}`, title }, label);
}
function basisBadge(basis, lg) {
  const b = typeof basis === "string" ? basis : basis && basis.basis;
  const title = basis && basis.reason ? `${basis.rule}: ${basis.reason}` : undefined;
  return el("span", { class: `basis basis-${b}${lg ? " lg" : ""}`, title }, b || "?");
}
function statusBadges(items, max) {
  const out = [];
  for (const item of items || []) {
    item.tokens.forEach((tok, i) => {
      out.push(badge(tok, item.tones[i], `${item.path} = "${trunc(item.raw, 300)}"`));
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
    el("button", { type: "button", disabled: true, "aria-disabled": "true", title: "Unavailable in the read-only viewer" }, label),
    el("div", { class: "small muted" }, reason));
}

// ----------------------------------------------------------------- tables
function table(headers, rows, cls) {
  return el("div", { class: "table-wrap" },
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
    if (h) { const n = h[1].length; out.push(`<h${n}>${inline(h[2], baseDir)}</h${n}>`); i += 1; continue; }
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
  return el("div", { class: "page-head" },
    el("div", null,
      crumbs ? el("div", { class: "crumbs" }, crumbs) : null,
      el("h1", null, title),
      lead ? el("p", null, lead) : null),
    extra || null);
}

// ---------------------------------------------------------- editorial
// Decorative photography. Every image is labelled where it appears: it shows
// third-party cryogenic hardware, not QMHP hardware, and it is never evidence.
const CAPTION = "Illustrative photograph · third-party cryogenic hardware · not QMHP hardware · not evidence";
const IMG = {
  cryostat: { src: "/static/img/cryostat-interior.webp", alt: "Gold-plated interior of a dilution-refrigerator cryostat (illustrative)", ratio: "1 / 1" },
  assembly: { src: "/static/img/qcage-assembly.webp", alt: "Sample-holder assembly with coaxial wiring on a mixing-chamber mount (illustrative)", ratio: "1 / 1" },
  holder: { src: "/static/img/sample-holder.webp", alt: "Sample holder with four connector banks (illustrative)", ratio: "3 / 2" },
  wiring: { src: "/static/img/wiring-stage.webp", alt: "Coaxial wiring and attenuators between cryostat plates (illustrative)", ratio: "16 / 9" },
  panel: { src: "/static/img/connector-panel.webp", alt: "Gold-plated coaxial connector panel (illustrative)", ratio: "16 / 9" },
};
function plate(key, opts) {
  const im = IMG[key];
  const o = opts || {};
  const fig = el("figure", { class: `plate reveal${o.dark ? " dark" : ""}${o.cls ? " " + o.cls : ""}` },
    el("div", { class: "frame" }, el("img", { src: im.src, alt: im.alt, loading: o.eager ? "eager" : "lazy", decoding: "async" })),
    el("figcaption", null, el("span", null, o.label ? el("b", null, o.label) : null), el("span", null, CAPTION)));
  fig.style.setProperty("--ratio", o.ratio || im.ratio);
  return fig;
}
function lines(text, cls) {
  return el("h1", { class: cls }, String(text).split("\n").map((ln) => el("span", { class: "line" }, el("span", null, ln))));
}
function eyebrow(n, label) {
  return el("p", { class: "eyebrow" }, n ? el("span", { class: "num" }, n) : null, label);
}
function pageHero(n, title, lead, img, extra) {
  const copy = el("div", null, eyebrow(n, SECTION_NAMES[n] || ""), lines(title, "title"),
    lead ? el("p", { class: "lead" }, lead) : null, extra || null);
  return el("header", { class: `page-hero${img ? " has-media" : ""}` }, copy, img ? plate(img, { eager: true }) : null);
}
const SECTION_NAMES = {
  "02": "Experiments & contracts", "03": "Evidence records", "04": "Candidates & runs", "05": "Gate status",
  "06": "Provenance & hashes", "07": "Execution & audit trail", "08": "Corrections", "09": "Evidence classification",
  "10": "Documents", "11": "Unavailable actions",
};
function arrow() { return el("span", { class: "arr", "aria-hidden": "true" }, "→"); }

// Motion: reveal on scroll, count up, header state and a light parallax. All of it is
// presentation; it reads nothing and requests nothing.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function countUp(node) {
  const target = Number(node.dataset.count);
  if (!Number.isFinite(target) || reducedMotion || target === 0) { node.textContent = String(target); return; }
  const t0 = performance.now(), dur = 1400;
  const tick = (t) => {
    const k = Math.min(1, (t - t0) / dur);
    node.textContent = String(Math.round(target * (1 - Math.pow(1 - k, 4))));
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
let revealObserver = null;
function enhance(root) {
  const targets = root.querySelectorAll(".reveal, [data-count]");
  if (!("IntersectionObserver" in window) || reducedMotion) {
    targets.forEach((t) => { t.classList.add("in"); if (t.dataset.count) countUp(t); });
    return;
  }
  if (revealObserver) revealObserver.disconnect();
  revealObserver = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add("in");
      if (e.target.dataset.count) countUp(e.target);
      revealObserver.unobserve(e.target);
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  targets.forEach((t) => revealObserver.observe(t));
}
function onScroll() {
  let last = window.scrollY, ticking = false;
  const update = () => {
    const y = window.scrollY;
    document.body.classList.toggle("scrolled", y > 40);
    document.body.classList.toggle("head-hidden", y > 480 && y > last + 2);
    if (y < last - 2 || y < 480) document.body.classList.remove("head-hidden");
    last = y;
    const hero = document.querySelector(".hero");
    if (hero && !reducedMotion) {
      hero.style.setProperty("--hero-shift", `${Math.min(y, 1200) * 0.18}px`);
      hero.style.setProperty("--hero-scale", String(1.08 + Math.min(y, 1200) / 12000));
    }
    ticking = false;
  };
  window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  update();
}

// ================================================================== views
async function viewOverview() {
  const [d, cls] = await Promise.all([get("/api/overview"), get("/api/classification")]);
  const legend = Object.fromEntries(cls.families.map((f) => [f.family, f]));
  const measuredCount = d.by_basis.MEASURED || 0;
  const out = [];

  // 01 - hero
  out.push(el("section", { class: "hero bleed" },
    el("div", { class: "hero-media", "aria-hidden": "true" },
      el("img", { src: IMG.cryostat.src, alt: "", decoding: "async", fetchpriority: "high" })),
    el("div", { class: "wrap hero-inner" },
      eyebrow("(01)", "QMHP-CEM — Computational Engineering Model"),
      el("h1", { class: "display" },
        el("span", { class: "line" }, el("span", null, "Evidence,")),
        el("span", { class: "line" }, el("span", null, "not")),
        el("span", { class: "line" }, el("span", null, el("em", null, "assertion.")))),
      el("p", { class: "hero-lead" }, "A read-only window onto every record, gate and hash in this checkout: what was computed, what was only declared, and what still waits on hardware. Each label names the rule that put it there."),
      el("div", { class: "hero-ctas" },
        el("a", { class: "btn solid", href: "#/records" }, "Explore evidence records", arrow()),
        el("a", { class: "btn", href: "#/classification" }, "How labels are assigned", arrow())),
      el("div", { class: "hero-stats" },
        [[d.counts.records, "Result records", "#/records"], [d.counts.candidates, "Candidates evaluated", "#/candidates"],
          [d.hardware_gated_gates.length, "Hardware-gated gates", "#/gates"], [measuredCount, "Measured records", "#/classification"]]
          .map(([v, k, href]) => el("a", { href }, el("span", { class: "v", "data-count": String(v) }, String(v)), el("span", { class: "k" }, k)))),
      el("p", { class: "hero-caption" }, CAPTION))));

  // 02 - the boundary, stated
  const basisRows = Object.entries(d.by_basis).map(([b, n]) => el("a", { class: "spec-row", href: `#/records?basis=${b}` },
    el("span", { class: "k" }, basisBadge(b)), el("span", { class: "v" }, (cls.bases.find((x) => x.basis === b) || {}).explanation || ""),
    el("span", { class: "n", "data-count": String(n) }, String(n))));
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap split" },
    el("div", { class: "reveal" }, eyebrow("(02)", "The hardware boundary"),
      el("h2", { class: "statement" }, "A computational PASS is ", el("em", null, "not"), " hardware validation.")),
    el("div", { class: "reveal d1" },
      el("p", { class: "copy" }, d.measured_statement, " Every record carries an evidence basis assigned by an explicit, ordered rule, and every status badge quotes the record's own words."),
      ...d.notes.map((n) => el("div", { class: "notice warn" }, el("span", { class: "ico" }, "NOTE"), el("div", { class: "body" }, n))),
      el("div", { class: "spec mt" }, basisRows)))));

  // 03 - gates only hardware can close
  const hwRows = d.hardware_gated_gates.map((g) => el("div", { class: "spec-row" },
    el("span", { class: "k" }, g.gate_id), el("span", { class: "v" }, g.title),
    el("span", null, badge("HARDWARE-GATED", "gated", g.pass_permitted ? "PASS permitted" : "PASS is not in this gate's frozen allowed statuses"))));
  out.push(el("section", { class: "section band-dark bleed" }, el("div", { class: "wrap split media-left" },
    plate("assembly", { dark: true, label: "Fig. 01" }),
    el("div", { class: "reveal d1" }, eyebrow("(03)", "Gates only hardware can close"),
      el("h2", { class: "statement" }, "Some questions only a ", el("em", null, "cold"), " measurement answers."),
      el("p", { class: "copy mt" }, "From master/validation_gates.yaml. These gates omit PASS from their frozen allowed statuses, so no simulated or model-derived result in this repository can close them."),
      el("div", { class: "spec mt" }, hwRows.length ? hwRows : el("p", { class: "empty" }, "No frozen gate definitions in this checkout."))))));

  // 04 - latest evidence per family
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap" },
    el("div", { class: "sec-head reveal" }, el("div", null, eyebrow("(04)", "Latest evidence"), el("h2", null, "The newest record in each family")),
      el("p", null, "Status badges are quoted verbatim from each record's headline fields. Hover one for its JSON path.")),
    el("div", { class: "cards reveal d1" }, d.latest_by_family.map((r) => el("a", { class: "card", href: recordHref(r.id) },
      el("span", { class: "fam" }, r.family), el("span", { class: "rid" }, r.id), el("span", { class: "when" }, fmtTs(r.timestamp)),
      el("div", { class: "row" }, basisBadge(r.basis), statusBadges(r.headline, 5)),
      el("div", { class: "foot" }, el("span", { class: "small muted" }, trunc(r.statement || "", 110)), el("span", { class: "go", "aria-hidden": "true" }, "→"))))))));

  // 05 - status families as figures
  const figs = Object.entries(d.by_status_family).map(([f, n]) => el("a", { class: "figure", href: `#/records?status=${q(f)}` },
    el("div", { class: "v", "data-count": String(n) }, String(n)), el("div", { class: "k" }, badge(f, (legend[f] || {}).tone, (legend[f] || {}).meaning))));
  out.push(el("section", { class: "section tight band-plate bleed" }, el("div", { class: "wrap" },
    el("div", { class: "sec-head reveal" }, el("div", null, eyebrow("(05)", "Status at a glance"), el("h2", null, "Headline status families")),
      el("p", null, "Records whose own headline fields carry a token in that family. A family only picks the colour; the token is always the record's.")),
    el("div", { class: "figures reveal d1" }, figs))));

  // 06 - frozen master and checkout
  const m = d.master || {};
  const co = d.checkout;
  out.push(el("section", { class: "section bleed" }, el("div", { class: "wrap split" },
    el("div", { class: "reveal" }, eyebrow("(06)", "Frozen master"),
      el("div", { class: "spec" },
        [["Revision", m.revision], ["Status", m.status], ["Date", m.date]].map(([k, v]) => el("div", { class: "spec-row" }, el("span", { class: "k" }, k), el("span", { class: "v" }, v || "—"), el("span"))),
        (m.issues || []).map((iss) => el("div", { class: "spec-row" }, el("span", { class: "k" }, String(iss.field).replace(/_/g, " ")), el("span", { class: "v small" }, trunc(iss.statement, 220)), badge(iss.status || "?", "caution")))),
      el("p", { class: "mt" }, link("#/provenance", "Master digests, re-measured →", "link"))),
    el("div", { class: "reveal d1" }, eyebrow("(07)", "This checkout"),
      el("div", { class: "spec" },
        co.available ? [["Branch", co.branch || (co.detached ? "(detached HEAD)" : "?")], ["HEAD", el("span", { class: "hash" }, co.head_sha)],
          ["Read from", "git's own HEAD and ref files; no git command is run"]].map(([k, v]) => el("div", { class: "spec-row" }, el("span", { class: "k" }, k), el("span", { class: "v" }, v), el("span")))
          : el("p", { class: "muted" }, `Commit identity unavailable: ${co.reason || "no git metadata"}.`))))));

  // 08 - what the viewer will never do
  out.push(el("section", { class: "section band-dark bleed" }, el("div", { class: "wrap split" },
    el("div", { class: "reveal" }, eyebrow("(08)", "Unavailable by design"),
      el("h2", { class: "statement" }, "What this viewer will ", el("em", null, "never"), " do."),
      el("p", { class: "copy mt" }, "Not hidden, not behind a flag, not an admin mode. The code for these actions does not exist."),
      el("a", { class: "btn mt", href: "#/unavailable" }, "All unavailable actions", arrow())),
    el("div", { class: "locked reveal d1" }, d.capabilities.unavailable.map((u) => lockedAction(u.action, u.reason))))));
  return out;
}

async function viewUnavailable() {
  const c = await get("/api/capabilities");
  return [pageHero("11", "Unavailable\nby design.", "This viewer is a display surface only. Anything below would change scientific or repository state, or start an execution, so it is not implemented - not hidden, not behind a flag, not an admin mode."),
    el("div", { class: "panel" }, kv([["HTTP methods served", c.http_methods.join(", ")], ["Writes", c.writes]])),
    el("div", { class: "panel locked" }, c.unavailable.map((u) => lockedAction(u.action, u.reason)))];
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
        el("td", null, el("div", { class: "row" }, statusBadges(r.headline, 6)), r.statement ? el("div", { class: "small muted" }, trunc(r.statement, 160)) : null),
        el("td", { class: "small nowrap" }, `${r.candidate_count} / ${r.run_count}`),
        el("td", { class: "small" }, r.manifests.length ? `${r.manifests.length} manifest` : el("span", { class: "muted" }, "none"))))));
  }
  render();
  return [pageHero("03", "Evidence\nrecords.", "Every directory under results/, newest first. Status badges are tokens quoted from each record's own headline fields; hover for the JSON path and the full text."),
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
    el("td", { class: "reason" }, trunc(s.raw, 300)))));
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
    { label: "Provenance & hashes", render: provPane },
    (r.candidates.length || r.runs.length) && { label: `Candidates & runs (${r.candidates.length}/${r.runs.length})`, render: candPane },
    { label: "Links", render: linksPane },
    { label: `Files (${r.file_count})`, render: filesPane },
  ]));
  return out;
}

function provenancePanel(r) {
  const res = el("div");
  const button = el("button", { type: "button", class: "chip", title: "Recomputes SHA-256 of the checked-out files. A read; nothing is written." },
    "Re-measure manifest hashes (read-only)");
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
      el("p", { class: "small muted" }, "Declared by the record. Not re-measured here: many name files outside this record or bytes that are not committed."),
      table(["JSON path", "SHA-256 (declared)"], digests.map((x) => el("tr", null, el("td", { class: "id" }, x.path), el("td", { class: "hash" }, x.sha256))))));
}

function verifyResult(v) {
  const box = el("div", { class: "mt-s" });
  for (const m of v.manifests) {
    const counts = Object.entries(m.counts || {}).map(([k, n]) => badge(`${k} ${n}`, k === "MATCH" ? "positive" : k === "MISMATCH" ? "negative" : "caution"));
    box.append(el("h4", null, m.manifest), el("div", { class: "row" }, counts), m.error ? el("p", { class: "error" }, m.error) : null);
    const bad = (m.entries || []).filter((e) => e.status !== "MATCH");
    if (bad.length) {
      box.append(table(["File", "Status", "Declared", "Measured now"], bad.map((e) => el("tr", null,
        el("td", { class: "id" }, e.path || `line ${e.line}`), el("td", { class: `st-${(e.status || "").split(" ")[0]}` }, e.status),
        el("td", { class: "hash" }, e.declared || ""), el("td", { class: "hash" }, e.measured || "")))));
    }
    const ok = (m.entries || []).filter((e) => e.status === "MATCH");
    if (ok.length) {
      box.append(el("details", null, el("summary", { class: "small" }, `${ok.length} matching files`),
        table(["File", "SHA-256 (declared = measured)"], ok.map((e) => el("tr", null, el("td", { class: "id" }, e.path), el("td", { class: "hash" }, e.declared))))));
    }
  }
  for (const f of v.declared_digest_files || []) {
    box.append(el("div", { class: "notice warn" }, el("span", { class: "ico" }, "DECLARED"),
      el("div", { class: "body" }, el("div", { class: "mono small" }, f.path), el("pre", { class: "code" }, f.content), el("div", { class: "small" }, f.note))));
  }
  if (v.unlisted_count) {
    box.append(el("details", null, el("summary", { class: "small" }, `${v.unlisted_count} file(s) in the record are not listed in any byte manifest`),
      el("ul", null, v.unlisted_files.map((p) => el("li", { class: "mono small" }, p)))));
  }
  box.append(el("p", { class: "small muted" }, `Measured ${fmtTs(v.measured_utc)}. ${v.note}`));
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
        el("td", null, c.classification ? badge(c.classification, "muted", "Candidate dimensions are ENGINEERING-SEED: never experimentally validated") : ""),
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
  return [pageHero("04", "Candidates\n& runs.", "Candidates evaluated against the frozen gates, and the named runs each record lists. Candidate geometry is ENGINEERING-SEED throughout.", "holder"),
    ...computationalNotice("SOLVED"),
    el("h2", null, `Candidates (${d.candidates.length})`), candidateTable(d.candidates),
    el("h2", null, `Runs (${d.runs.length})`), runTable(d.runs)];
}

// ----------------------------------------------------------------- gates
async function viewGates() {
  const d = await get("/api/gates");
  const defs = d.definitions.gates || [];
  const out = [pageHero("05", "Gates and\ntheir reasons.", "The frozen gate definitions, every gate result the records carry with its recorded reason, and each record's own headline verdicts.", "assembly"), ...computationalNotice("SOLVED")];
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
  const out = [pageHero("06", "Provenance\n& hashes.", d.note, "panel")];
  if (m.present) {
    out.push(el("h2", null, "Frozen master layer"),
      el("div", { class: "panel" }, kv([["Revision", m.revision], ["Status", m.status], ["Date", m.date], ["Provenance file", link(fileHref(m.path), m.path)]]),
        m.evidence_boundary ? el("div", { class: "notice comp mt-s" }, el("span", { class: "ico" }, "BOUNDARY"),
          el("div", { class: "body" }, `measured_evidence_objects_present = ${m.evidence_boundary.measured_evidence_objects_present}; hardware_gates_closable = ${m.evidence_boundary.hardware_gates_closable}. ${m.evidence_boundary.statement || ""}`)) : null),
      table(["File", "Declared SHA-256", "Measured now", "Result"], m.checks.map((c) => el("tr", null,
        el("td", { class: "id" }, link(fileHref(c.path), c.path)), el("td", { class: "hash" }, c.declared), el("td", { class: "hash" }, c.measured || ""),
        el("td", { class: `st-${c.status.split(" ")[0]}` }, c.status)))));
    if (m.issues.length) {
      out.push(el("h3", null, "Open provenance questions recorded in the master"),
        table(["Field", "Recorded status", "Statement"], m.issues.map((i) => el("tr", null, el("td", { class: "id" }, i.field),
          el("td", null, badge(i.status || "?", "caution")), el("td", { class: "reason" }, i.statement || "")))));
    }
  }
  const holder = new Map();
  out.push(el("h2", null, "Records"), table(["Record", "Basis", "Manifests", "Recorded environment and digests", ""], d.records.map((r) => {
    const res = el("div");
    holder.set(r.record_id, res);
    const btn = r.manifests.length ? el("button", { type: "button", class: "chip", title: "Read-only re-hash" }, "Re-measure") : null;
    if (btn) btn.addEventListener("click", async () => {
      btn.disabled = true; clear(res); res.append(el("span", { class: "loading small" }, "hashing…"));
      try { const v = await get(`/api/records/${q(r.record_id)}/verify`); clear(res); res.append(verifyResult(v)); }
      catch (e) { clear(res); res.append(el("span", { class: "error" }, e.message)); }
      btn.disabled = false;
    });
    const env = Object.entries(r.environment).map(([k, v]) => el("div", { class: "small" }, el("span", { class: "muted" }, `${k}: `), el("span", { class: "hash" }, String(v))));
    return el("tr", null, el("td", { class: "id" }, link(recordHref(r.record_id), r.record_id)), el("td", null, basisBadge(r.basis)),
      el("td", { class: "small" }, r.manifests.length ? r.manifests.map((x) => el("div", null, link(fileHref(x), x.split("/").pop()))) : el("span", { class: "muted" }, "none")),
      el("td", null, env.length ? env : el("span", { class: "muted small" }, "none recorded in the primary document"), res),
      el("td", null, btn));
  })));
  if (d.approvals.length) {
    out.push(el("h2", null, "Approval files (digests measured now)"),
      table(["Approval file", "State", "SHA-256"], d.approvals.map((a) => el("tr", null,
        el("td", { class: "id" }, link(fileHref(a.path), a.path)), el("td", null, badge(a.state, "muted")), el("td", { class: "hash" }, a.sha256)))));
  }
  return out;
}

// ------------------------------------------------------------ experiments
async function viewExperiments() {
  const d = await get("/api/experiments");
  const out = [pageHero("02", "Experiments &\nfrozen contracts.", "The frozen requirements layer and data contracts, then each experiment directory with its execution state as its own files state it.", "wiring")];
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
    el("td", { class: "reason" }, e.question ? trunc(e.question, 220) : null,
      e.linked_records.length ? el("div", { class: "small" }, `${e.linked_records.length} linked record(s)`) : null),
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
  out.push(el("div", { class: "panel locked" }, lockedAction(`Execute ${e.id}`, "Unavailable. Execution needs the repository's approved launcher and a scoped human approval, outside this viewer."),
    lockedAction("Create or edit an approval", "Unavailable. Approval files are displayed, never written.")));
  out.push(el("h2", null, "Linked results records"), e.linked_records.length ? table(["Record", "Basis", "Headline status"], e.linked_records.map((rid) => {
    const r = recById[rid] || {};
    return el("tr", null, el("td", { class: "id" }, link(recordHref(rid), rid)), el("td", null, r.basis ? basisBadge(r.basis) : ""), el("td", null, el("div", { class: "row" }, statusBadges(r.headline, 6))));
  })) : el("p", { class: "empty" }, "No results record is named by this experiment's JSON."));
  if (e.approvals.length) {
    out.push(el("h2", null, "Approval files"), el("p", { class: "muted" }, "Displayed only. The viewer cannot validate whether an approval authorises anything."),
      ...e.approvals.map((a) => el("div", { class: "panel" }, el("div", { class: "row" }, badge(a.state, a.tone), link(fileHref(a.path), a.path, "mono")),
        kv([["Authorises", a.authorises != null ? trunc(typeof a.authorises === "string" ? a.authorises : JSON.stringify(a.authorises), 600) : null],
          ["Scope", a.scope != null ? trunc(typeof a.scope === "string" ? a.scope : JSON.stringify(a.scope), 600) : null],
          ["Run label", a.run_label], ["Does not authorise", a.does_not_authorise != null ? trunc(JSON.stringify(a.does_not_authorise), 600) : null],
          ["SHA-256 (measured now)", el("span", { class: "hash" }, a.sha256)]]))));
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
  const out = [pageHero("07", "Execution &\naudit trail.", d.note)];
  if (d.experiment_states.length) {
    out.push(el("h2", null, "Execution state by experiment"), table(["Experiment", "State (as stated)", "Why", "Source"], d.experiment_states.map((s) => el("tr", null,
      el("td", { class: "id" }, link(`#/experiments/${q(s.experiment)}`, s.experiment)), el("td", null, badge(s.label, s.tone)),
      el("td", { class: "reason" }, s.reason), el("td", { class: "small" }, s.source ? link(fileHref(s.source), s.source.split("/").pop()) : "")))));
  }
  out.push(el("h2", null, `Approval files (${ap.approvals.length})`), el("div", { class: "notice info" }, el("span", { class: "ico" }, "DISPLAY ONLY"), el("div", { class: "body" }, ap.statement)),
    table(["File", "State", "Approved by / when", "What it names", "SHA-256 now"], ap.approvals.map((a) => el("tr", null,
      el("td", { class: "id" }, link(fileHref(a.path), a.path)), el("td", null, badge(a.state, a.tone)),
      el("td", { class: "small" }, a.approved_by ? trunc(a.approved_by, 140) : "", a.approved_utc ? el("div", { class: "muted" }, a.approved_utc) : null),
      el("td", { class: "reason" }, trunc(typeof a.authorises === "string" ? a.authorises : (a.what || a.run_label || JSON.stringify(a.authorises || a.scope || "")), 260),
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
        ev.summary ? el("div", { class: "small muted" }, trunc(ev.summary, 300)) : null));
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
  return [pageHero("08", "Corrections,\non the record.", "Corrections in this repository are made as new linked records; the originals are preserved."),
    el("div", { class: "notice info" }, el("span", { class: "ico" }, "SCOPE"), el("div", { class: "body" }, d.statement)),
    el("div", { class: "filters mt" }, sel, el("span", { class: "count" }, `${d.items.length} entries`)), holder];
}

// --------------------------------------------------------- classification
async function viewClassification() {
  const d = await get("/api/classification");
  const out = [pageHero("09", "Synthetic, solved,\nmeasured.", "Two questions are kept apart: what kind of evidence a record is (its basis), and what the record says about itself (its status tokens). Neither is invented by the viewer.")];
  out.push(...computationalNotice("SOLVED"));
  out.push(el("div", { class: "notice info" }, el("span", { class: "ico" }, "MEASURED"), el("div", { class: "body" }, d.measured_statement)));
  out.push(el("div", { class: "grid cols-3 mt" }, d.bases.map((b) => el("div", { class: "panel" },
    el("div", { class: "row" }, basisBadge(b.basis, true), el("span", { class: "count" }, `${b.count} record(s)`)),
    el("p", { class: "small mt-s" }, b.explanation)))));
  out.push(el("h2", null, "How a results record's basis is assigned"), el("p", { class: "muted" }, "Rules are tried in order; the first match wins. Each record page shows which rule fired and why."),
    table(["Rule", "Basis", "Condition"], d.record_rules.map((r) => el("tr", null, el("td", { class: "id" }, r.id), el("td", null, basisBadge(r.basis)), el("td", { class: "reason" }, r.rule)))),
    el("h3", null, "Experiments"),
    table(["Rule", "Basis", "Condition"], d.experiment_rules.map((r) => el("tr", null, el("td", { class: "id" }, r.id), el("td", null, basisBadge(r.basis)), el("td", { class: "reason" }, r.rule)))));
  out.push(el("h2", null, "Status families"), el("p", { class: "muted" }, "A family only chooses a colour and a filter. The badge text is always the token the record wrote."),
    table(["Family", "Tone", "Meaning"], d.families.map((f) => el("tr", null, el("td", null, badge(f.family, f.tone)), el("td", { class: "small" }, f.tone), el("td", { class: "reason" }, f.meaning)))));
  out.push(el("h2", null, "Records by basis"));
  for (const b of d.bases) {
    const recs = d.records_by_basis[b.basis] || [];
    out.push(el("details", { class: "panel", open: recs.length && recs.length < 12 ? true : null },
      el("summary", null, basisBadge(b.basis), `  ${recs.length} record(s)`),
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
  return [pageHero("10", "Documents.", "Markdown documents and record reports in this checkout, rendered as text."), el("div", { class: "filters" }, input), holder];
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
      ["SHA-256 (measured now)", f.sha256_measured ? el("span", { class: "hash" }, f.sha256_measured) : null],
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
  const out = [head(`Search: “${query}”`, d.note || `${d.files_matched || 0} file(s) matched${d.truncated ? " (first 200 shown)" : ""}. Solver output directories and files over 1 MB are not searched.`)];
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
  const seq = ++routeSeq;
  for (const [re, fn] of ROUTES) {
    const m = re.exec(path);
    if (!m) continue;
    clear(view);
    view.append(el("p", { class: "loading wrap" }, "Loading…"));
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
    view.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    return;
  }
  render([el("div", { class: "page-head" }, el("div", null, el("h1", null, "No such page"),
    el("p", null, link("#/overview", "Back to the overview", "link"))))], false);
}

// Full-bleed sections go straight into <main>; everything else is grouped into the
// centred page column.
function render(nodes, onHero) {
  clear(view);
  document.body.classList.toggle("on-hero", onHero);
  document.body.classList.remove("head-hidden");
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
  enhance(view);
}

async function boot() {
  const search = document.getElementById("global-search");
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); location.hash = `#/search?q=${q(search.value.trim())}`; }
  });
  try {
    const co = await get("/api/checkout");
    const where = co.available ? `Checkout ${co.branch || "detached"} @ ${shortSha(co.head_sha)}` : "Checkout: no git metadata";
    document.querySelectorAll(".checkout-text").forEach((n) => { n.textContent = where; });
    const cls = await get("/api/classification");
    document.querySelectorAll(".measured-text").forEach((n) => { n.textContent = cls.measured_statement; });
  } catch (_) { /* the page still works without the ticker text */ }
  window.addEventListener("hashchange", route);
  onScroll();
  route();
}
boot();
