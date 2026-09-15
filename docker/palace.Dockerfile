# Palace EM solver container (spec §10.3) — QMHP-CEM v0.2 execution path.
#
# Build (from the repository root; the build context is not used, see
# .dockerignore, so the checkout size does not matter):
#   docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.13.0 .
#
# The build needs outbound HTTPS to archive.ubuntu.com, snapshot.ubuntu.com,
# github.com (Palace and most of its superbuild dependencies) and gitlab.com
# (PETSc/SLEPc). It has not been executed from this checkout: no Docker
# daemon is available where this file was written. The first build is the
# first test of it, and docs/palace-execution.md says so.
#
# Reproducibility levers, each pinned by default and overridable by build-arg:
#   BASE_IMAGE      ubuntu:24.04 pinned by content digest, not by tag
#   APT_SNAPSHOT    Ubuntu package archive snapshot (YYYYMMDDTHHMMSSZ, see
#                   https://snapshot.ubuntu.com), so the toolchain does not
#                   float with the archive. Set to "" to disable if the
#                   snapshot service is unreachable — that build is then not
#                   reproducible and the image label says so.
#   PALACE_VERSION  the Palace release tag that is cloned
#   PALACE_COMMIT   the commit that tag must resolve to; a moved tag fails the
#                   build instead of changing the solver silently. Set to ""
#                   to skip the assertion.
#   BUILD_JOBS      parallel build jobs (default: nproc)
#
# What this pins and what it does not: the base image, the Ubuntu packages,
# the Palace source and (through Palace's own superbuild) the revisions of
# MFEM, hypre, METIS, PETSc/SLEPc, SuperLU_DIST, libCEED and the rest are
# fixed. The resulting binaries are built from identical inputs on every
# build; they are not guaranteed bit-identical (timestamps, build paths and
# compiler nondeterminism are not controlled). The adapter therefore records
# the image ID and digest of the image it actually ran, not this file's hash.
#
# The image states what it contains: /opt/palace/PALACE_VERSION and
# /opt/palace/PALACE_COMMIT are written from the clone, and the adapter reads
# them into every run record.
#
# Default CI does not build or require this image (spec §12.8).

ARG BASE_IMAGE=ubuntu:24.04@sha256:224a1869083a311ef3f13648a154ba79832fbef6364d31493642ca03082da254

# ---------------------------------------------------------------------------
# Stage 1: build Palace from its pinned release tag.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS builder

ARG PALACE_VERSION=0.13.0
ARG PALACE_COMMIT=a61c8cbe0cacf496cde3c62e93085fae0d6299ac
ARG APT_SNAPSHOT=20260914T000000Z
ARG BUILD_JOBS=""
ENV DEBIAN_FRONTEND=noninteractive

# apt (>= 2.7.3, so the noble base) selects the snapshot with APT::Snapshot;
# it has to be passed to *both* update and install, or install resolves
# against the live archive again. The snapshot host is HTTPS-only and the
# base image carries no CA bundle, so ca-certificates is installed from the
# live archive first: it is the one package that is not snapshot-pinned.
# After update the list directory must show snapshot entries, or the build
# stops: a silently un-pinned toolchain is exactly what this file exists to
# prevent.
RUN set -eux; \
    APT="apt-get"; \
    if [ -n "${APT_SNAPSHOT}" ]; then \
        apt-get update; \
        apt-get install -y --no-install-recommends ca-certificates; \
        APT="apt-get -o APT::Snapshot=${APT_SNAPSHOT}"; \
    fi; \
    ${APT} update; \
    if [ -n "${APT_SNAPSHOT}" ] && ! ls /var/lib/apt/lists/ | grep -q '^snapshot\.ubuntu\.com_'; then \
        echo "ERROR: apt did not resolve the ${APT_SNAPSHOT} snapshot; refusing an unpinned build" >&2; \
        exit 1; \
    fi; \
    ${APT} install -y --no-install-recommends \
        build-essential gfortran cmake git ca-certificates pkg-config \
        python3 zlib1g-dev \
        libopenmpi-dev openmpi-bin \
        libopenblas-dev liblapack-dev; \
    rm -rf /var/lib/apt/lists/*

# Clone the exact release tag and record the commit it resolves to. If the
# caller asserted a commit, a mismatch is a build failure, never a substitution.
RUN set -eux; \
    git clone --branch "v${PALACE_VERSION}" --depth 1 \
        https://github.com/awslabs/palace.git /opt/palace-src; \
    COMMIT="$(git -C /opt/palace-src rev-parse HEAD)"; \
    if [ -n "${PALACE_COMMIT}" ] && [ "${COMMIT}" != "${PALACE_COMMIT}" ]; then \
        echo "ERROR: tag v${PALACE_VERSION} resolves to ${COMMIT}, not the asserted ${PALACE_COMMIT}" >&2; \
        exit 1; \
    fi; \
    mkdir -p /opt/palace; \
    printf '%s\n' "${PALACE_VERSION}" > /opt/palace/PALACE_VERSION; \
    printf '%s\n' "${COMMIT}"         > /opt/palace/PALACE_COMMIT

# Palace's superbuild fetches and builds its dependencies and installs
# everything into CMAKE_INSTALL_PREFIX as part of `cmake --build`. Eigenmode
# solves need SLEPc (or ARPACK); SLEPc is the maintained default. Optional
# heavyweight packages are off to keep the build surface small. Headers,
# CMake package files and the sources are removed afterwards so the runtime
# stage copies only what the binary needs.
RUN set -eux; \
    JOBS="${BUILD_JOBS:-$(nproc)}"; \
    cmake -S /opt/palace-src -B /opt/palace-build \
        -DCMAKE_INSTALL_PREFIX=/opt/palace \
        -DCMAKE_BUILD_TYPE=Release \
        -DPALACE_WITH_SLEPC=ON \
        -DPALACE_WITH_ARPACK=OFF \
        -DPALACE_WITH_SUPERLU=ON \
        -DPALACE_WITH_STRUMPACK=OFF \
        -DPALACE_WITH_MUMPS=OFF \
        -DPALACE_WITH_GSLIB=OFF \
        -DPALACE_WITH_CUDA=OFF \
        -DPALACE_WITH_HIP=OFF; \
    cmake --build /opt/palace-build --parallel "${JOBS}"; \
    test -x /opt/palace/bin/palace; \
    ls /opt/palace/bin/palace-*.bin; \
    rm -rf /opt/palace-src /opt/palace-build \
           /opt/palace/include /opt/palace/share \
           /opt/palace/lib/cmake /opt/palace/lib/pkgconfig \
           /opt/palace/lib64/cmake /opt/palace/lib64/pkgconfig

# ---------------------------------------------------------------------------
# Stage 2: runtime image. Only what the linked binary needs.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE}

ARG PALACE_VERSION=0.13.0
ARG PALACE_COMMIT=a61c8cbe0cacf496cde3c62e93085fae0d6299ac
ARG APT_SNAPSHOT=20260914T000000Z
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    APT="apt-get"; \
    if [ -n "${APT_SNAPSHOT}" ]; then \
        apt-get update; \
        apt-get install -y --no-install-recommends ca-certificates; \
        APT="apt-get -o APT::Snapshot=${APT_SNAPSHOT}"; \
    fi; \
    ${APT} update; \
    if [ -n "${APT_SNAPSHOT}" ] && ! ls /var/lib/apt/lists/ | grep -q '^snapshot\.ubuntu\.com_'; then \
        echo "ERROR: apt did not resolve the ${APT_SNAPSHOT} snapshot; refusing an unpinned build" >&2; \
        exit 1; \
    fi; \
    ${APT} install -y --no-install-recommends \
        openmpi-bin libopenmpi3t64 \
        libopenblas0 libgfortran5 libgomp1 libstdc++6 zlib1g; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/palace /opt/palace

# Open MPI inside a `--network none` container sees only the loopback
# interface; tell it so, and keep transports to shared memory and self.
ENV PATH="/opt/palace/bin:${PATH}" \
    OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    OMPI_MCA_btl_vader_single_copy_mechanism=none \
    OMPI_MCA_btl=self,vader \
    OMPI_MCA_oob_tcp_if_include=lo

# Fail the build, not the first run, if the copied binary is missing a shared
# library or the launcher cannot start. `ldd` exits non-zero for a binary it
# cannot inspect, and any "not found" line is a missing dependency.
RUN set -eux; \
    test -x /opt/palace/bin/palace; \
    BIN="$(ls /opt/palace/bin/palace-*.bin | head -n1)"; \
    ldd "${BIN}" > /tmp/ldd.txt; \
    if grep -q "not found" /tmp/ldd.txt; then cat /tmp/ldd.txt; exit 1; fi; \
    rm -f /tmp/ldd.txt; \
    palace --help > /dev/null; \
    cat /opt/palace/PALACE_VERSION /opt/palace/PALACE_COMMIT

LABEL org.qmhp.cem.solver="palace" \
      org.qmhp.cem.palace-version="${PALACE_VERSION}" \
      org.qmhp.cem.palace-commit="${PALACE_COMMIT}" \
      org.qmhp.cem.apt-snapshot="${APT_SNAPSHOT}" \
      org.qmhp.cem.spec="QMHP-CEM v0.2 §10.3" \
      org.opencontainers.image.title="qmhp-cem/palace" \
      org.opencontainers.image.description="Palace EM solver for QMHP-CEM, built from the pinned release tag"

WORKDIR /work
ENTRYPOINT ["palace"]
