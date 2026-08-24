# openEMS FDTD solver container (spec §10.4).
#
# Build:
#   docker build -f docker/openems.Dockerfile -t qmhp-cem/openems:0.1.0 .
#
# Same provenance rules as Palace: record solver version, image digest where
# available, command line, input hash, output hashes and convergence.
#
# STATUS: skeleton. Default CI does not build or require this image (§12.8).

FROM ubuntu:24.04

ARG OPENEMS_VERSION=v0.0.36
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates \
        libhdf5-dev libvtk9-dev libboost-all-dev libcgal-dev \
        libtinyxml-dev qtbase5-dev libvtk9-qt-dev \
        python3 python3-pip python3-numpy \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --recursive --depth 1 --branch ${OPENEMS_VERSION} \
        https://github.com/thliebig/openEMS-Project.git /opt/openems-src \
    && cd /opt/openems-src \
    && ./update_openEMS.sh /opt/openems \
    && rm -rf /opt/openems-src

ENV PATH="/opt/openems/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/openems/lib:${LD_LIBRARY_PATH}"

LABEL org.qmhp.cem.solver="openems" \
      org.qmhp.cem.solver-version="${OPENEMS_VERSION}" \
      org.qmhp.cem.spec="QMHP-CEM v0.1 §10.4"

WORKDIR /work
ENTRYPOINT ["openEMS"]
