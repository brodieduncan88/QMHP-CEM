# Palace EM solver container (spec §10.3).
#
# Build:
#   docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.1.0 .
#
# The image digest is recorded in the batch manifest wherever available, along
# with the solver version, command line, input hash and output hashes.
#
# STATUS: skeleton. The Palace build below pins a released tag; verify the
# revision and record it in master/provenance.json before treating any Palace
# output as SOLVED evidence. Default CI does not build or require this image
# (spec §12.8).

FROM ubuntu:24.04

ARG PALACE_VERSION=0.13.0
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates \
        libopenmpi-dev openmpi-bin \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Palace is built from source; pin the tag so the image is reproducible.
RUN git clone --depth 1 --branch v${PALACE_VERSION} \
        https://github.com/awslabs/palace.git /opt/palace-src \
    && cmake -S /opt/palace-src -B /opt/palace-build \
        -DCMAKE_INSTALL_PREFIX=/opt/palace \
        -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/palace-build --parallel \
    && cmake --install /opt/palace-build \
    && rm -rf /opt/palace-src /opt/palace-build

ENV PATH="/opt/palace/bin:${PATH}"

LABEL org.qmhp.cem.solver="palace" \
      org.qmhp.cem.solver-version="${PALACE_VERSION}" \
      org.qmhp.cem.spec="QMHP-CEM v0.1 §10.3"

WORKDIR /work
ENTRYPOINT ["palace"]
