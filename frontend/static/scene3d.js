// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// The stage stack: an original real-time 3-D illustration drawn from this checkout's
// data. One plate per frozen gate (dark with a violet rim when only hardware can close
// it), one coax line per record family, one bead per record coloured by its headline
// status. It is not a model of QMHP or of any real hardware.
//
// This module renders and animates; it requests nothing and stores nothing. The page
// hands it data already fetched through the viewer's single GET helper.

import {
  WebGLRenderer, Scene, PerspectiveCamera, Group, Mesh, InstancedMesh, Object3D,
  CylinderGeometry, BoxGeometry, TorusGeometry, SphereGeometry, TubeGeometry, PlaneGeometry,
  CatmullRomCurve3, Vector2, Vector3, Color, MeshPhysicalMaterial, MeshStandardMaterial,
  MeshBasicMaterial, DirectionalLight, HemisphereLight, PMREMGenerator, Raycaster,
  ACESFilmicToneMapping, SRGBColorSpace, BackSide,
} from "/static/vendor/three.min.js";

const TONES = {
  positive: 0x3fd09a, negative: 0xff7486, caution: 0xf1b551,
  gated: 0xb8a2ff, neutral: 0xa9bdd4, muted: 0x9aa3b0,
};

// Deterministic pseudo-random numbers from a string, so the same gate always gets
// the same components in the same places.
function seeded(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
  return () => { h ^= h << 13; h ^= h >>> 17; h ^= h << 5; return ((h >>> 0) % 100000) / 100000; };
}
const ease = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

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
 *   options.mode:  "hero" | "section"
 *   options.progress(): scroll progress in [0, 1]
 *   options.onHover(record | null, clientX, clientY), options.onSelect(record)
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

  const camera = new PerspectiveCamera(30, 1, 0.1, 100);
  const disposables = [];
  const keep = (x) => { disposables.push(x); return x; };

  // materials
  const gold = keep(new MeshPhysicalMaterial({ color: 0xd69634, metalness: 1, roughness: 0.28, clearcoat: 0.25, clearcoatRoughness: 0.25 }));
  const goldSatin = keep(new MeshPhysicalMaterial({ color: 0xc99a45, metalness: 1, roughness: 0.42 }));
  const gunmetal = keep(new MeshPhysicalMaterial({ color: 0x15171d, metalness: 0.7, roughness: 0.52, clearcoat: 0.12 }));
  const steel = keep(new MeshStandardMaterial({ color: 0xc5cad3, metalness: 0.95, roughness: 0.3 }));
  const copper = keep(new MeshStandardMaterial({ color: 0xc8734a, metalness: 1, roughness: 0.32 }));
  const hole = keep(new MeshStandardMaterial({ color: 0x14161b, metalness: 0.4, roughness: 0.8 }));
  const violet = keep(new MeshBasicMaterial({ color: new Color(TONES.gated).multiplyScalar(1.4) }));

  const gates = data.gates && data.gates.length ? data.gates : [{ id: "stage", hardware: false }];
  const n = gates.length;
  const rTop = 2.25, rBottom = Math.max(1.05, rTop - n * 0.12);
  const baseGap = n > 8 ? 0.5 : 0.72;
  const thick = 0.085;
  const radius = (i) => (n === 1 ? rTop : rTop - ((rTop - rBottom) * i) / (n - 1));

  const stack = new Group();
  scene.add(stack);
  const plates = [];
  const plateGeo = new Map();
  const cylinder = (r, h, seg) => {
    const k = `${r.toFixed(3)}:${h}:${seg}`;
    if (!plateGeo.has(k)) plateGeo.set(k, keep(new CylinderGeometry(r, r, h, seg)));
    return plateGeo.get(k);
  };
  const componentGeo = keep(new BoxGeometry(0.22, 0.14, 0.34));
  const holeGeo = keep(new CylinderGeometry(0.035, 0.035, thick * 1.1, 10));
  const dummy = new Object3D();

  gates.forEach((g, i) => {
    const r = radius(i);
    const plate = new Group();
    const body = new Mesh(cylinder(r, thick, coarse ? 64 : 112), g.hardware ? gunmetal : gold);
    plate.add(body);
    // bolt circle
    const bolts = new InstancedMesh(holeGeo, hole, 28);
    for (let k = 0; k < 28; k += 1) {
      const a = (k / 28) * Math.PI * 2;
      dummy.position.set(Math.cos(a) * (r - 0.13), 0.004, Math.sin(a) * (r - 0.13));
      dummy.updateMatrix();
      bolts.setMatrixAt(k, dummy.matrix);
    }
    plate.add(bolts);
    // components mounted on the plate, placed deterministically from the gate id
    const rnd = seeded(g.id);
    const count = 3 + Math.floor(rnd() * 4);
    for (let k = 0; k < count; k += 1) {
      const a = rnd() * Math.PI * 2, d = 0.55 + rnd() * (r - 0.9);
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

  // support rods and coax lines live in a group that is stretched vertically as
  // the stack separates; beads are positioned separately so they stay round.
  const stretch = new Group();
  stack.add(stretch);
  const span = (n - 1) * baseGap;
  const rodR = rBottom - 0.28;
  for (let k = 0; k < 4; k += 1) {
    const a = Math.PI / 4 + (k * Math.PI) / 2;
    const rod = new Mesh(cylinder(0.045, span, 18), gold);
    rod.position.set(Math.cos(a) * rodR, -span / 2, Math.sin(a) * rodR);
    stretch.add(rod);
  }
  const families = (data.families || []).slice(0, 10);
  const lines = [];
  const lineCount = Math.max(families.length, 6);
  for (let k = 0; k < lineCount; k += 1) {
    const rnd = seeded(`line-${k}`);
    const a = (k / lineCount) * Math.PI * 2 + 0.3;
    const rad = 0.42 + (k % 3) * 0.16;
    const pts = [];
    const steps = 8;
    for (let s = 0; s <= steps; s += 1) {
      const y = -(s / steps) * span;
      const wob = s === 0 || s === steps ? 0 : (rnd() - 0.5) * 0.18;
      pts.push(new Vector3(Math.cos(a) * (rad + wob), y, Math.sin(a) * (rad + wob)));
    }
    const curve = new CatmullRomCurve3(pts);
    const tube = new Mesh(keep(new TubeGeometry(curve, coarse ? 48 : 96, 0.02, 8, false)), k % 4 === 1 ? copper : steel);
    stretch.add(tube);
    lines.push({ curve, family: families[k] || null });
    // a thermalisation coil on some lines
    if (k % 3 === 0 && n > 2) {
      const coil = new Mesh(keep(new TorusGeometry(0.16, 0.012, 6, 40)), steel);
      const p = curve.getPoint(0.42);
      coil.position.copy(p); coil.rotation.y = a; coil.scale.y = 1;
      stretch.add(coil);
    }
  }

  // beads: one per record, on its family's line, height by recorded time
  const beadGeo = keep(new SphereGeometry(0.062, 20, 14));
  const beadMats = new Map();
  const beads = [];
  lines.forEach((line) => {
    if (!line.family) return;
    line.family.records.forEach((rec) => {
      if (!beadMats.has(rec.tone)) {
        beadMats.set(rec.tone, keep(new MeshStandardMaterial({ color: TONES[rec.tone] || TONES.neutral, emissive: TONES[rec.tone] || TONES.neutral, emissiveIntensity: 0.85, roughness: 0.3, metalness: 0.1 })));
      }
      const bead = new Mesh(beadGeo, beadMats.get(rec.tone));
      bead.userData.record = rec;
      bead.userData.u = 0.06 + rec.t * 0.88;
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
    const top = ((n - 1) * gap) / 2;
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
    const v = toNdc(e);
    pointer.copy(v);
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
  let raf = 0, visible = true, running = false, spin = 0, last = performance.now();
  const io = new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; if (visible) start(); }, { threshold: 0 });
  io.observe(container);
  const onVis = () => { if (!document.hidden) start(); };
  document.addEventListener("visibilitychange", onVis);

  function frame(now) {
    if (minFrameMs && now - last < minFrameMs) {
      if (visible && !document.hidden) raf = requestAnimationFrame(frame); else running = false;
      return;
    }
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const p = ease(o.progress ? o.progress() : 0);
    spin += dt * (mode === "hero" ? 0.12 : 0.08);
    aim.lerp(pointer, 0.06);
    const sep = mode === "hero" ? p * 0.75 : 0.35 + p * 0.65;
    layout(sep);
    stack.rotation.y = spin + p * (mode === "hero" ? 1.1 : 1.6) + aim.x * 0.35;
    stack.rotation.x = 0.16 + aim.y * -0.08;
    const height = (n - 1) * baseGap * (1 + sep);
    const tanHalf = Math.tan((camera.fov * Math.PI) / 360);
    const fitV = (height / 2 + 1.35) / tanHalf;
    const fitH = (rTop + 0.7) / (tanHalf * camera.aspect);
    const dist = Math.max(fitV, fitH) * (mode === "hero" ? 1.02 - p * 0.08 : 1.04);
    camera.position.set(0, 1.0 + height * 0.06, dist);
    camera.lookAt(0, -0.05, 0);
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
