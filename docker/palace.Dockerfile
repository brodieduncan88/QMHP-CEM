# syntax=docker/dockerfile:1.7
# Palace EM solver container (spec §10.3) — QMHP-CEM v0.2 execution path.
#
# Build (from the repository root):
#   docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.13.0 .
#
# Reproducibility levers, each pinned by default and overridable by build-arg:
#   BASE_IMAGE      ubuntu:24.04 pinned by content digest, not by tag
#   APT_SNAPSHOT    Ubuntu package archive snapshot (YYYYMMDDTHHMMSSZ), so the
#                   toolchain does not float with the archive; set to "" to
#                   disable if the snapshot service is unreachable
#   PALACE_VERSION  the Palace release tag that is cloned
#   PALACE_COMMIT   optional: assert the tag resolves to this commit, so a moved
#                   tag fails the build instead of changing the solver silently
#
# The image states what it contains: /opt/palace/PALACE_VERSION and
# /opt/palace/PALACE_COMMIT are written from the clone, and the adapter reads
# them into every run record. Palace's own dependencies (MFEM, hypre, METIS,
# PETSc/SLEPc, SuperLU_DIST, libCEED, ...) are fetched by its CMake superbuild
# at the revisions pinned inside the Palace source tree for that tag.
#
# Default CI does not build or require this image (spec §12.8).

ARG BASE_IMAGE=ubuntu:24.04@sha256:224a1869083a311ef3f13648a154ba79832fbef6364d31493642ca03082da254

# ---------------------------------------------------------------------------
# Stage 1: build Palace from its pinned release tag.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS builder

ARG PALACE_VERSION=0.13.0
ARG PALACE_COMMIT=""
ARG APT_SNAPSHOT=20260914T000000Z
ARG BUILD_JOBS=4
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    APT="apt-get"; \
    if [ -n "${APT_SNAPSHOT}" ]; then APT="apt-get -o Acquire::Snapshot=${APT_SNAPSHOT}"; fi; \
    ${APT} update; \
    ${APT} install -y --no-install-recommends \
        build-essential gfortran cmake git ca-certificates curl pkg-config \
        python3 bison flex zlib1g-dev \
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

# Palace's superbuild installs into CMAKE_INSTALL_PREFIX as part of the build.
# Eigenmode solves need SLEPc (or ARPACK); SLEPc is the maintained default.
# Optional heavyweight packages are off to keep the build surface small.
RUN set -eux; \
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
    cmake --build /opt/palace-build --parallel "${BUILD_JOBS}"; \
    test -x /opt/palace/bin/palace; \
    ls /opt/palace/bin/palace-*.bin; \
    rm -rf /opt/palace-src /opt/palace-build

# ---------------------------------------------------------------------------
# Stage 2: runtime image. Only what the linked binary needs.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE}

ARG PALACE_VERSION=0.13.0
ARG APT_SNAPSHOT=20260914T000000Z
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    APT="apt-get"; \
    if [ -n "${APT_SNAPSHOT}" ]; then APT="apt-get -o Acquire::Snapshot=${APT_SNAPSHOT}"; fi; \
    ${APT} update; \
    ${APT} install -y --no-install-recommends \
        openmpi-bin libopenmpi3t64 \
        libopenblas0 libgfortran5 libgomp1 libstdc++6 zlib1g \
        ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/palace /opt/palace

ENV PATH="/opt/palace/bin:${PATH}" \
    OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    OMPI_MCA_btl_vader_single_copy_mechanism=none

# Fail the build, not the first run, if the copied binary is missing a shared
# library. The launcher script and the binary must both be present.
RUN set -eux; \
    test -x /opt/palace/bin/palace; \
    BIN="$(ls /opt/palace/bin/palace-*.bin | head -n1)"; \
    if ldd "${BIN}" | grep -q "not found"; then ldd "${BIN}"; exit 1; fi; \
    cat /opt/palace/PALACE_VERSION /opt/palace/PALACE_COMMIT

LABEL org.qmhp.cem.solver="palace" \
      org.qmhp.cem.palace-version="${PALACE_VERSION}" \
      org.qmhp.cem.spec="QMHP-CEM v0.2 §10.3" \
      org.opencontainers.image.title="qmhp-cem/palace" \
      org.opencontainers.image.description="Palace EM solver for QMHP-CEM, built from the pinned release tag"

WORKDIR /work
ENTRYPOINT ["palace"]
