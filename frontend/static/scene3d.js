// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// The stage stack: an original real-time 3-D illustration drawn from this checkout's
// data. One plate per frozen gate (dark with a violet rim when only hardware can close
// it), coax signal lines with bulkhead connectors and attenuators, one bead per record
// coloured by its headline status, and at the base a sample package holding an
// illustrative chip with one cell per record. It is not a model of QMHP, of its chip
// layout (the repository contains none), or of any real hardware.
//
// This module renders and animates; it requests nothing and stores nothing. The page
// hands it data already fetched through the viewer's single GET helper.

import {
  WebGLRenderer, Scene, PerspectiveCamera, Group, Mesh, InstancedMesh, Object3D,
  CylinderGeometry, BoxGeometry, TorusGeometry, SphereGeometry, TubeGeometry, PlaneGeometry,
  CatmullRomCurve3, Vector2, Vector3, Color, MeshPhysicalMaterial, MeshStandardMaterial,
  MeshBasicMaterial, DirectionalLight, HemisphereLight, PMREMGenerator, Raycaster,
  ACESFilmicToneMapping, SRGBColorSpace, BackSide, CanvasTexture, LineSegments,
  LineBasicMaterial, BufferGeometry, Float32BufferAttribute,
} from "/static/vendor/three.min.js";

const TONES = {
  positive: 0x3fd09a, negative: 0xff7486, caution: 0xf1b551,
  gated: 0xb8a2ff, neutral: 0xa9bdd4, muted: 0x9aa3b0,
};
const TONE_CSS = {
  positive: "#3fd09a", negative: "#ff7486", caution: "#f1b551",
  gated: "#b8a2ff", neutral: "#a9bdd4", muted: "#9aa3b0",
};

// Deterministic pseudo-random numbers from a string, so the same gate always gets
// the same components in the same places.
function seeded(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
  return () => { h ^= h << 13; h ^= h >>> 17; h ^= h << 5; return ((h >>> 0) % 100000) / 100000; };
}
const ease = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
const clamp01 = (t) => Math.min(1, Math.max(0, t));

// A small studio for reflections: dark room, soft boxes. Built here instead of using
// three's RoomEnvironment add-on, whose bare "three" import would need an import map,
// which the viewer's CSP (no inline script) does not allow.
function studio(renderer) {
  const room = new Scene();
  room.add(new Mesh(new BoxGeometry(20, 20, 20), new MeshBasicMaterial({ color: 0x0b0c10, side: BackSide })));
  const panel = (w, h, pos, rot, intensity, tint) => {
    const m = new MeshBasicMaterial({ color: new Color(tint).multiplyScalar(intensity) });
    const p = new Mesh(new PlaneGeometry(w, h), m);
    p.position.copy(pos); p.rotation.set(rot.x, rot.y, rot.z);
    room.add(p);
  };
  panel(12, 12, new Vector3(0, 9.8, 0), new Vector3(Math.PI / 2, 0, 0), 1.7, 0xffe2b4);
  panel(12, 3, new Vector3(0, 5, -9.8), new Vector3(0, 0, 0), 1.6, 0xffd9a0);
  panel(3, 12, new Vector3(-9.5, 1, 2), new Vector3(0, Math.PI / 2, 0), 3.2, 0xffd9a0);
  panel(2, 12, new Vector3(9.5, 0, -3), new Vector3(0, -Math.PI / 2, 0), 2.4, 0xbfe8ff);
  panel(10, 2, new Vector3(0, -3, 9.5), new Vector3(0, Math.PI, 0), 1.2, 0xffffff);
  const pmrem = new PMREMGenerator(renderer);
  const env = pmrem.fromScene(room, 0.035).texture;
  pmrem.dispose();
  room.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  return env;
}

// ------------------------------------------------------------------ the chip
// An illustrative superconducting-circuit die, drawn procedurally: a coplanar
// feedline, one cell per record (capacitor pads, a meandered superinductor and a
// junction marker tinted by the record's status), couplers, meandered readout
// resonators, flux lines and a bond-pad ring. Etched "ILLUSTRATIVE LAYOUT": the
// repository contains no chip design.
function chipTexture(tones, anisotropy, small) {
  const S = small ? 1024 : 2048;
  const k = S / 1024;
  const cv = document.createElement("canvas");
  cv.width = cv.height = S;
  const g = cv.getContext("2d");
  const metal = "#cfd4dc", gap = "#1d222c", sub = "#262c38";
  g.fillStyle = sub; g.fillRect(0, 0, S, S);
  g.fillStyle = metal; g.fillRect(26 * k, 26 * k, S - 52 * k, S - 52 * k);
  const path = (pts) => { g.beginPath(); g.moveTo(pts[0][0] * k, pts[0][1] * k); for (const p of pts.slice(1)) g.lineTo(p[0] * k, p[1] * k); };
  // coplanar waveguide: a metal trace with a gap on each side
  const cpw = (pts, w, gw) => {
    g.lineJoin = "round"; g.lineCap = "round";
    g.strokeStyle = gap; g.lineWidth = (w + 2 * gw) * k; path(pts); g.stroke();
    g.strokeStyle = metal; g.lineWidth = w * k; path(pts); g.stroke();
  };
  const rect = (x, y, w, h, c) => { g.fillStyle = c; g.fillRect(x * k, y * k, w * k, h * k); };
  // bond pads on all four edges
  for (let side = 0; side < 4; side += 1) {
    for (let i = 0; i < 9; i += 1) {
      const t = 120 + i * 98;
      const [x, y] = side === 0 ? [t, 50] : side === 1 ? [974, t] : side === 2 ? [t, 974] : [50, t];
      rect(x - 22, y - 22, 44, 44, gap); rect(x - 15, y - 15, 30, 30, metal);
    }
  }
  // feedline across the top, launched from the left and right pads
  const feedY = 170;
  cpw([[50, 316], [110, 316], [140, feedY], [884, feedY], [914, 316], [974, 316]], 12, 8);
  // cells: one per record, at least four
  const n = Math.max(4, Math.min(16, tones.length || 4));
  const cols = n <= 4 ? 2 : n <= 9 ? 3 : 4, rows = Math.ceil(n / cols);
  const x0 = 170, x1 = 854, y0 = 330, y1 = 900;
  const cw = (x1 - x0) / cols, ch = (y1 - y0) / rows;
  const cells = [];
  for (let i = 0; i < n; i += 1) {
    const c = i % cols, r = Math.floor(i / cols);
    cells.push({ cx: x0 + cw * (c + 0.5), cy: y0 + ch * (r + 0.5), c, r, tone: tones[i] || "neutral" });
  }
  const P = Math.min(cw, ch) * 0.52;
  // couplers between horizontal neighbours
  for (const a of cells) {
    const b = cells.find((x) => x.r === a.r && x.c === a.c + 1);
    if (!b) continue;
    rect(a.cx + P / 2 - 4, a.cy - 9, b.cx - a.cx - P + 8, 18, gap);
    rect(a.cx + P / 2 - 2, a.cy - 4, b.cx - a.cx - P + 4, 8, metal);
    rect((a.cx + b.cx) / 2 - 7, a.cy - 7, 14, 14, "#8a93a3");
  }
  for (const cell of cells) {
    const { cx, cy } = cell;
    rect(cx - P / 2, cy - P / 2, P, P, gap);
    const pw = P * 0.28, ph = P * 0.56;
    rect(cx - P / 2 + P * 0.1, cy - ph / 2, pw, ph, metal);
    rect(cx + P / 2 - P * 0.1 - pw, cy - ph / 2, pw, ph, metal);
    // meandered superinductor between the pads
    const L = cx - P / 2 + P * 0.1 + pw, R = cx + P / 2 - P * 0.1 - pw;
    const zz = [[L, cy - ph * 0.36]];
    const turns = 9;
    for (let t = 0; t <= turns; t += 1) {
      const y = cy - ph * 0.36 + (ph * 0.72 * t) / turns;
      zz.push([t % 2 ? R - 3 : L + 3, y]);
    }
    zz.push([R, cy + ph * 0.36]);
    g.strokeStyle = metal; g.lineWidth = 2.2 * k; g.lineJoin = "miter"; path(zz); g.stroke();
    // junction marker, tinted by the record's headline status
    g.fillStyle = TONE_CSS[cell.tone] || TONE_CSS.neutral;
    g.fillRect((cx - 6) * k, (cy - 6) * k, 12 * k, 12 * k);
    // readout resonator: a meander from the cell up toward the feedline
    const topY = cell.r === 0 ? feedY + 14 : cy - ch + P / 2 + 10;
    const mx = cx + P * 0.34;
    const pts = [[mx, cy - P / 2]];
    const steps = 6, span = (cy - P / 2) - topY;
    for (let s = 1; s <= steps; s += 1) {
      const y = cy - P / 2 - (span * s) / (steps + 1);
      pts.push([s % 2 ? mx + 26 : mx - 26, y]);
    }
    pts.push([mx, topY]);
    cpw(pts, 4, 3);
    // flux line from the side pad channel
    const side = cell.c < cols / 2 ? -1 : 1;
    const edgeX = side < 0 ? 60 : 964;
    cpw([[edgeX, cy + P * 0.28], [cx + side * (P / 2 + 8), cy + P * 0.28]], 4, 3);
  }
  // etched label
  g.fillStyle = gap;
  g.font = `${18 * k}px monospace`;
  g.fillText("QMHP-CEM · ILLUSTRATIVE LAYOUT · NOT A DEVICE DESIGN", 90 * k, 1000 * k);
  const tex = new CanvasTexture(cv);
  tex.colorSpace = SRGBColorSpace;
  tex.anisotropy = anisotropy;
  return tex;
}

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch (_) { return false; }
}

/**
 * mountStack(container, data, options) -> { dispose() }
 *   data.gates:    [{ id, hardware }]              top to bottom
 *   data.families: [{ name, records: [{ id, tone, t, label }] }]   t in [0, 1]
 *   options.mode:  "hero" | "section"   ("section" ends in a close-up of the chip)
 *   options.progress(): scroll progress in [0, 1]
 *   options.onHover(record | null, clientX, clientY), options.onSelect(record)
 *   options.onCloseUp(amount in [0, 1])
 */
export function mountStack(container, data, options) {
  const o = options || {};
  const mode = o.mode || "hero";
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.25 : 2));
  const minFrameMs = coarse ? 33 : 0;
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0x000000, 0);
  const canvas = renderer.domElement;
  canvas.setAttribute("aria-hidden", "true");
  canvas.className = "stage-canvas";
  container.append(canvas);

  const scene = new Scene();
  scene.environment = studio(renderer);
  scene.add(new HemisphereLight(0xfff1dc, 0x10121a, 0.5));
  const key = new DirectionalLight(0xffe2b0, 1.6); key.position.set(4, 7, 5); scene.add(key);
  const rim = new DirectionalLight(0x9fdcff, 1.1); rim.position.set(-6, 2, -5); scene.add(rim);

  const camera = new PerspectiveCamera(30, 1, 0.02, 100);
  const disposables = [];
  const keep = (x) => { disposables.push(x); return x; };

  // materials
  const gold = keep(new MeshPhysicalMaterial({ color: 0xd69634, metalness: 1, roughness: 0.28, clearcoat: 0.25, clearcoatRoughness: 0.25 }));
  const goldSatin = keep(new MeshPhysicalMaterial({ color: 0xc99a45, metalness: 1, roughness: 0.42 }));
  const gunmetal = keep(new MeshPhysicalMaterial({ color: 0x15171d, metalness: 0.7, roughness: 0.52, clearcoat: 0.12 }));
  const steel = keep(new MeshStandardMaterial({ color: 0xc5cad3, metalness: 0.95, roughness: 0.3 }));
  const braid = keep(new MeshStandardMaterial({ color: 0xaeb3bb, metalness: 0.8, roughness: 0.55 }));
  const copper = keep(new MeshStandardMaterial({ color: 0xc8734a, metalness: 1, roughness: 0.32 }));
  const hole = keep(new MeshStandardMaterial({ color: 0x14161b, metalness: 0.4, roughness: 0.8 }));
  const violet = keep(new MeshBasicMaterial({ color: new Color(TONES.gated).multiplyScalar(1.4) }));

  const gates = data.gates && data.gates.length ? data.gates : [{ id: "stage", hardware: false }];
  const n = gates.length;
  const rTop = 2.25, rBottom = Math.max(1.05, rTop - n * 0.12);
  const baseGap = n > 8 ? 0.5 : 0.72;
  const thick = 0.085;
  const radius = (i) => (n === 1 ? rTop : rTop - ((rTop - rBottom) * i) / (n - 1));
  const dummy = new Object3D();
  const geoCache = new Map();
  const cyl = (r, h, seg) => {
    const key2 = `c${r.toFixed(3)}:${h.toFixed(3)}:${seg}`;
    if (!geoCache.has(key2)) geoCache.set(key2, keep(new CylinderGeometry(r, r, h, seg)));
    return geoCache.get(key2);
  };

  // -------------------------------------------------------- signal lines
  // Semi-rigid coax: straight runs that jog slightly at each stage, a bulkhead
  // connector where each line crosses a plate, attenuators under some stages.
  const families = (data.families || []).slice(0, 16);
  const lineCount = Math.max(families.length, coarse ? 10 : 16);
  const lineDefs = [];
  for (let k = 0; k < lineCount; k += 1) {
    const rnd = seeded(`line-${k}`);
    const a = (k / lineCount) * Math.PI * 2 + 0.2;
    const rad = 0.36 + (k % 3) * 0.2;
    const at = [];
    for (let i = 0; i < n; i += 1) {
      const j = (rnd() - 0.5) * 0.05;
      at.push([Math.cos(a) * (rad + j), Math.sin(a) * (rad + j)]);
    }
    lineDefs.push({ a, rad, at, family: families[k] || null, copper: k % 5 === 2 });
  }

  // -------------------------------------------------------------- plates
  const stack = new Group();
  scene.add(stack);
  const plates = [];
  const componentGeo = keep(new BoxGeometry(0.22, 0.14, 0.34));
  const holeGeo = keep(new CylinderGeometry(0.035, 0.035, thick * 1.1, 10));
  const bulkGeo = keep(new CylinderGeometry(0.034, 0.034, 0.12, 12));
  const nutGeo = keep(new CylinderGeometry(0.05, 0.05, 0.03, 6));
  const attGeo = keep(new BoxGeometry(0.075, 0.15, 0.075));

  gates.forEach((g, i) => {
    const r = radius(i);
    const plate = new Group();
    plate.add(new Mesh(cyl(r, thick, coarse ? 64 : 112), g.hardware ? gunmetal : gold));
    // bolt circle
    const bolts = new InstancedMesh(holeGeo, hole, 28);
    for (let k = 0; k < 28; k += 1) {
      const a = (k / 28) * Math.PI * 2;
      dummy.position.set(Math.cos(a) * (r - 0.13), 0.004, Math.sin(a) * (r - 0.13));
      dummy.rotation.set(0, 0, 0); dummy.scale.set(1, 1, 1); dummy.updateMatrix();
      bolts.setMatrixAt(k, dummy.matrix);
    }
    plate.add(bolts);
    // bulkhead connectors and hex nuts where every line crosses this plate
    const bulk = new InstancedMesh(bulkGeo, goldSatin, lineCount);
    const nuts = new InstancedMesh(nutGeo, gold, lineCount * 2);
    lineDefs.forEach((ln, k) => {
      const [x, z] = ln.at[i];
      dummy.rotation.set(0, 0, 0); dummy.scale.set(1, 1, 1);
      dummy.position.set(x, 0, z); dummy.updateMatrix(); bulk.setMatrixAt(k, dummy.matrix);
      dummy.position.set(x, thick / 2 + 0.018, z); dummy.updateMatrix(); nuts.setMatrixAt(2 * k, dummy.matrix);
      dummy.position.set(x, -thick / 2 - 0.018, z); dummy.updateMatrix(); nuts.setMatrixAt(2 * k + 1, dummy.matrix);
    });
    plate.add(bulk, nuts);
    // attenuators hanging under every third stage, on alternate lines
    if (i < n - 1 && i % 3 === 1) {
      const lines = lineDefs.filter((_, k) => k % 2 === 0);
      const att = new InstancedMesh(attGeo, goldSatin, lines.length);
      lines.forEach((ln, k) => {
        const [x, z] = ln.at[i];
        dummy.rotation.set(0, -ln.a, 0); dummy.scale.set(1, 1, 1);
        dummy.position.set(x, -thick / 2 - 0.11, z); dummy.updateMatrix(); att.setMatrixAt(k, dummy.matrix);
      });
      plate.add(att);
    }
    // components mounted on the plate, placed deterministically from the gate id
    const rnd = seeded(g.id);
    const count = 3 + Math.floor(rnd() * 4);
    for (let k = 0; k < count; k += 1) {
      const a = rnd() * Math.PI * 2, d = 1.15 + rnd() * Math.max(0.05, r - 1.45);
      const box = new Mesh(componentGeo, rnd() > 0.35 ? goldSatin : steel);
      box.position.set(Math.cos(a) * d, thick / 2 + 0.07, Math.sin(a) * d);
      box.rotation.y = -a;
      plate.add(box);
    }
    let ring = null;
    if (g.hardware) {
      ring = new Mesh(keep(new TorusGeometry(r + 0.012, 0.018, 8, coarse ? 96 : 160)), violet);
      ring.rotation.x = Math.PI / 2;
      plate.add(ring);
    }
    stack.add(plate);
    plates.push({ group: plate, ring, index: i });
  });

  // Rods and coax runs live in a group stretched vertically as the stack separates;
  // beads are positioned separately so they stay round.
  const stretch = new Group();
  stack.add(stretch);
  const span = (n - 1) * baseGap;
  const rodR = rBottom - 0.2;
  for (let k = 0; k < 4; k += 1) {
    const a = Math.PI / 4 + (k * Math.PI) / 2;
    const rod = new Mesh(cyl(0.045, Math.max(0.01, span), 18), gold);
    rod.position.set(Math.cos(a) * rodR, -span / 2, Math.sin(a) * rodR);
    stretch.add(rod);
  }
  lineDefs.forEach((ln, k) => {
    const pts = [];
    for (let i = 0; i < n; i += 1) {
      const [x, z] = ln.at[i];
      pts.push(new Vector3(x, -i * baseGap, z));
      if (i < n - 1) {
        const [x2, z2] = ln.at[i + 1];
        const jog = 0.035 * (k % 2 ? 1 : -1);
        pts.push(new Vector3((x + x2) / 2 + Math.cos(ln.a + Math.PI / 2) * jog, -(i + 0.5) * baseGap, (z + z2) / 2 + Math.sin(ln.a + Math.PI / 2) * jog));
      }
    }
    if (pts.length < 2) pts.push(new Vector3(pts[0].x, -0.4, pts[0].z));
    ln.curve = new CatmullRomCurve3(pts, false, "centripetal");
    stretch.add(new Mesh(keep(new TubeGeometry(ln.curve, Math.max(24, (n - 1) * (coarse ? 6 : 10)), 0.016, coarse ? 6 : 8, false)), ln.copper ? copper : steel));
    // a thermalisation coil on some lines
    if (k % 4 === 0 && n > 2) {
      const coilPts = [];
      const c = ln.curve.getPoint(0.36);
      for (let s = 0; s <= 48; s += 1) {
        const t = (s / 48) * Math.PI * 2 * 3;
        coilPts.push(new Vector3(c.x + Math.cos(t) * 0.09, c.y + 0.12 - (s / 48) * 0.24, c.z + Math.sin(t) * 0.09));
      }
      stretch.add(new Mesh(keep(new TubeGeometry(new CatmullRomCurve3(coilPts), 120, 0.011, 6, false)), copper));
    }
  });

  // ------------------------------------------------------- sample package
  const bottom = plates[n - 1].group;
  const pkg = new Group();
  pkg.position.y = -1.0;
  bottom.add(pkg);
  // four corner posts hang the package from the stage, leaving the chip open to view
  const postGeo = cyl(0.032, 0.9, 16);
  const footGeo = cyl(0.07, 0.04, 24);
  for (const [px, pz] of [[-0.54, -0.54], [0.54, -0.54], [-0.54, 0.54], [0.54, 0.54]]) {
    const post = new Mesh(postGeo, gold);
    post.position.set(px, 0.58, pz);
    const foot = new Mesh(footGeo, goldSatin);
    foot.position.set(px, 0.15, pz);
    pkg.add(post, foot);
  }
  pkg.add(new Mesh(keep(new BoxGeometry(1.2, 0.26, 1.2)), goldSatin));
  const pocket = new Mesh(keep(new BoxGeometry(0.66, 0.02, 0.66)), hole);
  pocket.position.y = 0.125;
  pkg.add(pocket);
  const records = families.flatMap((f) => f.records);
  const chipTex = keep(chipTexture(records.map((r) => r.tone), renderer.capabilities.getMaxAnisotropy(), coarse));
  const chipTop = keep(new MeshStandardMaterial({ map: chipTex, metalness: 0.35, roughness: 0.38 }));
  const chipSide = keep(new MeshStandardMaterial({ color: 0x3a404c, metalness: 0.2, roughness: 0.6 }));
  const chip = new Mesh(keep(new BoxGeometry(0.5, 0.02, 0.5)), [chipSide, chipSide, chipTop, chipSide, chipSide, chipSide]);
  chip.position.y = 0.14;
  pkg.add(chip);
  // SMA launches on all four sides, launch traces to the chip, bond wires
  const smaGeo = keep(new CylinderGeometry(0.045, 0.045, 0.24, 16));
  const hexGeo = keep(new CylinderGeometry(0.072, 0.072, 0.06, 6));
  const traceGeo = keep(new BoxGeometry(0.34, 0.006, 0.022));
  const smas = new InstancedMesh(smaGeo, gold, 16);
  const hexes = new InstancedMesh(hexGeo, goldSatin, 16);
  const traces = new InstancedMesh(traceGeo, steel, 16);
  const smaTips = [];
  const wire = [];
  const up = new Vector3(0, 1, 0);
  let si = 0;
  for (let side = 0; side < 4; side += 1) {
    const ang = (side * Math.PI) / 2;
    const out = new Vector3(Math.cos(ang), 0, Math.sin(ang));
    const tan = new Vector3(-Math.sin(ang), 0, Math.cos(ang));
    for (const off of [-0.36, -0.12, 0.12, 0.36]) {
      const base = out.clone().multiplyScalar(0.6).add(tan.clone().multiplyScalar(off));
      dummy.scale.set(1, 1, 1);
      dummy.quaternion.setFromUnitVectors(up, out);
      dummy.position.copy(base.clone().add(out.clone().multiplyScalar(0.12)));
      dummy.updateMatrix(); smas.setMatrixAt(si, dummy.matrix);
      dummy.position.copy(base.clone().add(out.clone().multiplyScalar(0.03)));
      dummy.updateMatrix(); hexes.setMatrixAt(si, dummy.matrix);
      // trace on the package lid from the launch toward the chip
      const inner = out.clone().multiplyScalar(0.27).add(tan.clone().multiplyScalar(off * 0.55));
      const mid = base.clone().add(inner).multiplyScalar(0.5);
      dummy.quaternion.identity();
      dummy.rotation.set(0, -Math.atan2(base.z - inner.z, base.x - inner.x), 0);
      dummy.position.set(mid.x, 0.133, mid.z);
      dummy.scale.set(base.distanceTo(inner) / 0.34, 1, 1);
      dummy.updateMatrix(); traces.setMatrixAt(si, dummy.matrix);
      // three bond wires from the trace end to the chip's edge pads
      for (const w of [-0.012, 0, 0.012]) {
        const a0 = inner.clone().add(tan.clone().multiplyScalar(w));
        const b0 = out.clone().multiplyScalar(0.225).add(tan.clone().multiplyScalar(off * 0.5 + w));
        let prev = null;
        for (let s = 0; s <= 8; s += 1) {
          const t = s / 8;
          const p = a0.clone().lerp(b0, t);
          p.y = 0.137 + Math.sin(Math.PI * t) * 0.03 + 0.015 * t;
          if (prev) wire.push(prev.x, prev.y, prev.z, p.x, p.y, p.z);
          prev = p;
        }
      }
      smaTips.push(base.clone().add(out.clone().multiplyScalar(0.25)));
      si += 1;
    }
  }
  dummy.scale.set(1, 1, 1);
  pkg.add(smas, hexes, traces);
  const wireGeo = keep(new BufferGeometry());
  wireGeo.setAttribute("position", new Float32BufferAttribute(wire, 3));
  pkg.add(new LineSegments(wireGeo, keep(new LineBasicMaterial({ color: 0xe8c47a }))));
  // braided flex cables from the bottom stage's connectors down into the launches
  lineDefs.forEach((ln, k) => {
    const [x, z] = ln.at[n - 1];
    const tip = smaTips[k % smaTips.length].clone().add(pkg.position);
    const dir = tip.clone().setY(0).normalize();
    const pts = [
      new Vector3(x, -thick / 2 - 0.03, z),
      new Vector3(x * 1.05, -0.35, z * 1.05),
      tip.clone().add(dir.clone().multiplyScalar(0.3)).setY(tip.y + 0.2),
      tip.clone().add(dir.clone().multiplyScalar(0.08)),
    ];
    bottom.add(new Mesh(keep(new TubeGeometry(new CatmullRomCurve3(pts), 40, 0.013, 6, false)), braid));
  });

  // ---------------------------------------------------------------- beads
  const beadGeo = keep(new SphereGeometry(0.062, 20, 14));
  const beadMats = new Map();
  const beads = [];
  lineDefs.forEach((line) => {
    if (!line.family) return;
    line.family.records.forEach((rec) => {
      if (!beadMats.has(rec.tone)) {
        beadMats.set(rec.tone, keep(new MeshStandardMaterial({ color: TONES[rec.tone] || TONES.neutral, emissive: TONES[rec.tone] || TONES.neutral, emissiveIntensity: 0.85, roughness: 0.3, metalness: 0.1 })));
      }
      const bead = new Mesh(beadGeo, beadMats.get(rec.tone));
      bead.userData.record = rec;
      bead.userData.u = 0.04 + rec.t * 0.92;
      bead.userData.curve = line.curve;
      stack.add(bead);
      beads.push(bead);
    });
  });

  // layout for a given separation (0 = compact)
  let lastSep = -1;
  function layout(sep) {
    if (Math.abs(sep - lastSep) < 1e-4) return;
    lastSep = sep;
    const gap = baseGap * (1 + sep);
    const top = ((n - 1) * gap) / 2 + 0.5;
    plates.forEach((p) => { p.group.position.y = top - p.index * gap; });
    stretch.position.y = top;
    stretch.scale.y = 1 + sep;
    for (const b of beads) {
      const p = b.userData.curve.getPoint(b.userData.u);
      b.position.set(p.x, top + p.y * (1 + sep), p.z);
    }
  }

  // sizing
  function resize() {
    const w = Math.max(1, container.clientWidth), h = Math.max(1, container.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // interaction
  const pointer = new Vector2(0, 0), aim = new Vector2(0, 0);
  const ray = new Raycaster();
  let hovered = null;
  const toNdc = (e) => {
    const r = canvas.getBoundingClientRect();
    return new Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  };
  const pick = (e) => {
    ray.setFromCamera(toNdc(e), camera);
    const hit = ray.intersectObjects(beads, false)[0];
    return hit ? hit.object : null;
  };
  const onMove = (e) => {
    pointer.copy(toNdc(e));
    if (e.pointerType !== "mouse") return;
    const b = pick(e);
    if (b !== hovered) {
      hovered = b;
      canvas.style.cursor = b ? "pointer" : "";
      if (o.onHover) o.onHover(b ? b.userData.record : null, e.clientX, e.clientY);
    } else if (b && o.onHover) {
      o.onHover(b.userData.record, e.clientX, e.clientY);
    }
  };
  const onLeave = () => { pointer.set(0, 0); if (hovered && o.onHover) o.onHover(null); hovered = null; canvas.style.cursor = ""; };
  const onClick = (e) => { const b = pick(e); if (b && o.onSelect) o.onSelect(b.userData.record); };
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("click", onClick);

  // render loop, only while on screen and the tab is visible
  let raf = 0, visible = true, running = false, spin = 0, last = performance.now(), lastClose = -1;
  const io = new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; if (visible) start(); }, { threshold: 0 });
  io.observe(container);
  const onVis = () => { if (!document.hidden) start(); };
  document.addEventListener("visibilitychange", onVis);
  const far = new Vector3(), near = new Vector3(), look = new Vector3(), pkgWorld = new Vector3(), center = new Vector3(0, 0.45, 0);

  function frame(now) {
    if (minFrameMs && now - last < minFrameMs) {
      if (visible && !document.hidden) raf = requestAnimationFrame(frame); else running = false;
      return;
    }
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const raw = clamp01(o.progress ? o.progress() : 0);
    const p = ease(mode === "hero" ? raw : raw / 0.55);
    const close = mode === "section" ? ease((raw - 0.55) / 0.4) : 0;
    spin += dt * (mode === "hero" ? 0.12 : 0.08) * (1 - close);
    aim.lerp(pointer, 0.06);
    const sep = mode === "hero" ? p * 0.75 : 0.35 + p * 0.65;
    layout(sep);
    stack.rotation.y = (spin + p * (mode === "hero" ? 1.1 : 1.6) + aim.x * 0.35) * (1 - close) + close * 0.04;
    stack.rotation.x = (0.16 + aim.y * -0.08) * (1 - close);
    stack.updateMatrixWorld(true);
    const height = (n - 1) * baseGap * (1 + sep) + 1.6;
    const tanHalf = Math.tan((camera.fov * Math.PI) / 360);
    const fitV = (height / 2 + 1.2) / tanHalf;
    const fitH = (rTop + 0.7) / (tanHalf * camera.aspect);
    const dist = Math.max(fitV, fitH) * (mode === "hero" ? 1.0 - p * 0.08 : 1.04);
    far.set(0, 0.9 + height * 0.05, dist);
    // During the close-up the near plane moves out, so cables passing the lens do not block the chip.
    const nearPlane = 0.02 + close * 0.42;
    if (Math.abs(camera.near - nearPlane) > 1e-3) { camera.near = nearPlane; camera.updateProjectionMatrix(); }
    if (close > 0.001) {
      pkg.getWorldPosition(pkgWorld);
      near.set(pkgWorld.x + 0.02, pkgWorld.y + 0.66, pkgWorld.z + 0.86);
      camera.position.lerpVectors(far, near, close);
      look.lerpVectors(center, pkgWorld.setY(pkgWorld.y + 0.14), close);
      camera.lookAt(look);
    } else {
      camera.position.copy(far);
      camera.lookAt(center);
    }
    if (o.onCloseUp && Math.abs(close - lastClose) > 0.01) { lastClose = close; o.onCloseUp(close); }
    const pulse = 0.75 + Math.sin(now / 600) * 0.25;
    violet.color.setHex(TONES.gated).multiplyScalar(1.1 + pulse * 0.6);
    for (const b of beads) b.scale.setScalar(b === hovered ? 1.8 : 1);
    renderer.render(scene, camera);
    if (visible && !document.hidden) raf = requestAnimationFrame(frame);
    else running = false;
  }
  function start() {
    if (running) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }
  start();

  return {
    dispose() {
      cancelAnimationFrame(raf);
      running = false;
      io.disconnect();
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("click", onClick);
      for (const d of disposables) d.dispose();
      if (scene.environment) scene.environment.dispose();
      renderer.dispose();
      canvas.remove();
    },
  };
}
