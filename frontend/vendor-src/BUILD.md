# Vendored three.js bundle

| Item | Value |
|---|---|
| Output | `frontend/static/vendor/three.min.js` |
| Library | three.js **0.186.1** (npm `three@0.186.1`), MIT licence — `frontend/static/vendor/LICENSE-three.txt` |
| Bundler | esbuild **0.25.10** (build tool only; not shipped) |
| Entry | `frontend/vendor-src/three-entry.js` — exactly the classes `frontend/static/scene3d.js` imports |
| SHA-256 | `1b6ac2963c0483b6eac25baac51db9172b1644bf6fc9d15e7467441b81ed3efd` |
| Size | 562714 bytes (about 140 KB gzipped) |

The bundle is tree-shaken to those classes, so it contains none of three's loaders
and no network code: no `fetch`, `XMLHttpRequest`, `WebSocket`, `sendBeacon` or
`EventSource`. `tests/test_readonly_frontend.py` pins the digest above and asserts
that absence.

## Rebuild

```bash
mkdir /tmp/tb && cd /tmp/tb && npm init -y
npm i three@0.186.1 esbuild@0.25.10
cp <repo>/frontend/vendor-src/three-entry.js .
npx esbuild three-entry.js --bundle --minify --format=esm --target=es2020 \
  --legal-comments=inline --outfile=three.min.js
sha256sum three.min.js   # must match the digest above
```

If `scene3d.js` imports a new class, add it to the entry, rebuild, and update the
digest here and in the test.
