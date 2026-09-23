# First-moment diagnostic image: build-environment qualification

Phase B of the adopted sequence (`docs/agent-contract-implementation.md`): resolve and
qualify the network/build environment. **No solver was executed, no image was built and
no scientific result changed.** Nothing here authorises an execution.

**Outcome: BLOCKED.** One host in the build's dependency set is refused by the
organisation's egress policy. Every other precondition that can be tested without that
host was tested and passes.

## The blocker

`docker/palace-first-moment.Dockerfile` pins its base image by content digest:

```
ARG BASE_IMAGE=ubuntu:24.04@sha256:224a1869083a311ef3f13648a154ba79832fbef6364d31493642ca03082da254
```

Resolution succeeds; the layer fetch does not:

```
registry-1.docker.io  manifest sha256:224a1869…              HTTP 200 (with token)
  → amd64 manifest    sha256:a61567bd31828687156d735ea8eb01ba4e37636e225dd6a48ba94136a70d9d61
  → first layer       sha256:e51aee9c82ec5dd5ba2add49c45c6d85d460512757e2615b69bcdf9469c7cb58
registry-1.docker.io  blobs/<layer>                          HTTP/2 307
  → location          https://production.cloudfront.docker.com/registry-v2/…
CONNECT production.cloudfront.docker.com:443                 403
```

The agent proxy's own record, verbatim:

```
kind:   connect_rejected
detail: gateway answered 403 to CONNECT (policy denial or upstream failure)
host:   production.cloudfront.docker.com:443
```

Re-confirmed 2026-09-21T09:35:29Z and 09:35:30Z. The denial has been left intact: no
mirror, alternate registry, `--network host` context change or TLS relaxation was used,
and the base image, Palace revision and diagnostic patch were not substituted.

**Who controls it.** The 403 originates at the upstream policy gateway; the local proxy
relays it. Outbound access is governed by the environment's network policy, chosen when
the environment is created, so it is controlled at environment/organisation level and
not from inside a session. This session exposes no authorised network-setting change:
the proxy endpoint is read-only status, reports `selective: false` and
`toolScoped: false`, and `/root/.ccr/` contains only the README and CA material.
`list_environments` returns exactly one environment, so no alternative build environment
is available either.

## Egress qualification (measured 2026-09-21T09:37:38Z)

| host | needed for | status |
|---|---|---|
| `registry-1.docker.io` | base image manifest | 200 with token (401 on unauthenticated `/v2/`, the expected auth challenge) |
| `auth.docker.io` | registry token | 200 |
| **`production.cloudfront.docker.com`** | **base image layer blobs** | **403 to CONNECT — BLOCKED** |
| `archive.ubuntu.com` | `ca-certificates` bootstrap | 200 |
| `snapshot.ubuntu.com` | pinned apt snapshot `20260914T000000Z` | 200 |
| `github.com` | Palace source | 200 |
| `gitlab.com` | PETSc/SLEPc superbuild | 200 |
| `proxy.golang.org` | secret-scanner module | 200 |
| `sum.golang.org` | scanner checksum database | 200 |

Build resources: 4 vCPU, 15 GB RAM, 22 GB free disk. The production image's first build
took 818 s of superbuild on a 4-vCPU runner, so the resources are adequate; the disk
margin is not generous.

## What IS qualified

The Dockerfile's three fail-closed build assertions were verified against real upstream,
without building anything:

1. **The pinned tag still resolves to the pinned commit.** `git clone --branch v0.13.0
   --depth 1 https://github.com/awslabs/palace` gives HEAD
   `a61c8cbe0cacf496cde3c62e93085fae0d6299ac`, matching `ARG PALACE_COMMIT`. A moved tag
   would fail the build; it has not moved.
2. **The patch applies cleanly to that commit.** `git apply --check` with
   `docker/patches/first-moment-diagnostic.patch` returns clean. The patch's measured
   sha256 is `e8a1ad51d4e355b0426e84c70cb9c796a4915b1216bb035d5fe60913de512fee`, equal
   to the pinned constant.
3. **The post-patch checks hold.** In a disposable copy,
   `palace/drivers/firstmomentsolver.cpp` exists and `FIRSTMOMENT` is present in
   `palace/utils/configfile.hpp`.

Additionally:

- **The patched-file set is exactly the pinned one** — 9 files, identical to
  `EXPECTED_PATCHED_FILES`: 7 modifications of existing upstream files and 2 new files.
- **Licence notices are correct.** The 2 authored files carry the proprietary notice;
  all 7 modified upstream files retain
  `Copyright Amazon.com, Inc. … SPDX-License-Identifier: Apache-2.0`.
- **The apt snapshot the Dockerfile pins is live**, so the build would not fall back to
  an unpinned toolchain (which it refuses to do anyway).

## What is NOT established

Nothing below can be tested until the blocked host is permitted. None of it should be
reported as done on the strength of the checks above.

- the image itself: image ID, repo digest and labels
- the in-image identity files `PALACE_VERSION`, `PALACE_COMMIT`, `PALACE_PATCH`,
  `PALACE_PATCH_SHA256`
- that the superbuild compiles (MFEM, hypre, METIS, PETSc/SLEPc, SuperLU_DIST, libCEED)
- the runtime-stage `ldd` and `palace --help` checks
- the four synthetic fixtures run **through the image** — the existing
  `experiments/first-moment-diagnostic/compiled_qualification.json` records a
  **natively built** binary and is native-only evidence; re-running it would not qualify
  the image
- the fault-injection arm, which needs a second deliberately broken build

## Remaining requirements for the image qualification

1. `production.cloudfront.docker.com:443` permitted for this environment's egress
   policy, by whoever administers it.
2. Build `qmhp-cem/palace-first-moment:0.13.0` from the pinned Dockerfile and patch.
3. Run all four synthetic fixtures through the built image and record the in-image
   identity files alongside the results.

The separately approved N2R execution remains gated behind its own requirements:
`EXECUTION-APPROVAL.json` (deliberately absent) carrying matching config, mesh and patch
digests; an N2R mesh and its sha256; and the DOF 250 000 / 2 700 s caps as hard caps.
