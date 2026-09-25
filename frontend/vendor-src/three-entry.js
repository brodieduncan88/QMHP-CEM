// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Build entry for frontend/static/vendor/three.min.js: exactly the three.js classes
// frontend/static/scene3d.js imports, so the vendored bundle is tree-shaken to them.
// Rebuild with the command in frontend/vendor-src/BUILD.md.

export {
  WebGLRenderer,
  Scene,
  PerspectiveCamera,
  Group,
  Mesh,
  InstancedMesh,
  Object3D,
  CylinderGeometry,
  BoxGeometry,
  TorusGeometry,
  SphereGeometry,
  TubeGeometry,
  PlaneGeometry,
  CatmullRomCurve3,
  Vector2,
  Vector3,
  Color,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  MeshBasicMaterial,
  DirectionalLight,
  HemisphereLight,
  PMREMGenerator,
  Raycaster,
  ACESFilmicToneMapping,
  SRGBColorSpace,
  BackSide,
} from "three";
