#!/usr/bin/env python3
"""Build the PO1 port-removed control config from N2R's SOLVED config, and prove the delta.

PO1 is N2R's discrete problem with the F1 lumped inductive port made inactive,
which is exactly K -> K - K_port: Palace assembles the port's 1/L_s boundary
mass term into the stiffness only for active ports
(``lumpedportoperator.cpp:571-591``, the guard at :577). Everything else -
mesh file, two-level refinement box, order, tolerances, eigenvalue target and
count, materials, PEC set, the port face's interface-dielectric probes - is
N2R's, byte for byte.

One postprocessing-only addition accompanies it: the three declared field
probes of ``numerical-plan.md`` section 2, which the solved N1R/N2R configs
omit and without which the declared readout classification cannot be run.
Probes add no operator term (``Domains.Postprocessing.Probe`` is read by the
domain postprocessor only), so they cannot move an eigenvalue.

This script writes the candidate only. It launches nothing, writes nothing
under ``results/`` and never touches ``.github/ladder-approval.json``, which
is the file whose commit starts a run.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

#: N2R's record and the config it actually SOLVED - not a candidate file.
N2R_RECORD = "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z"
N2R_SOLVED_CONFIG = REPO / "results" / N2R_RECORD / "L2" / "solver" / "config.json"
N2R_SOLVED_CONFIG_SHA256 = "79304b5f8bd7c67741e995ec7ae7880b41dfcee23d6c3c12984f5baba8c1f33f"
BASELINE_MESH_SHA256 = "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"

#: The three declared probe points of numerical-plan.md section 2, placed from the
#: registered geometry (solvers.palace.coupled_geometry) at a fixed 0.010 mm above
#: the chip surface, in the spec 7.3 frame. IMPORTED, not restated: they are
#: pinned in solvers/palace/coupled_config.py, which is also what the driver
#: reads, so the prepared candidate and any generated config cannot drift apart.
#:   1: over the F1 island (centre)
#:   2: over the R1 coupling pad, the resonator's open end (centre)
#:   3: over the R1 CPW at half its 6.983 mm centre-line length
sys.path.insert(0, str(REPO))
from solvers.palace.coupled_config import PO1_PROBES_MM as PROBES_MM  # noqa: E402
PROBE_ROLES = {1: "F1.island", 2: "R1.coupling_pad (resonator open end)", 3: "R1.cpw (mid-length)"}

#: The driver's own serialisation, so the delta below is a true file diff
#: (scripts/palace_order1_ladder.py:1406).
def _serialise(config: dict) -> str:
    return json.dumps(config, indent=2) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _paths_of(obj, prefix="") -> dict[str, object]:
    """Flatten to leaf paths, so the delta can be asserted exhaustively."""
    out: dict[str, object] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_paths_of(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_paths_of(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def build() -> tuple[dict, dict, str]:
    raw = N2R_SOLVED_CONFIG.read_text()
    if _sha256(raw) != N2R_SOLVED_CONFIG_SHA256:
        raise RuntimeError("N2R's solved config is not the one this preparation was written against")
    solved = json.loads(raw)
    if _serialise(solved) != raw:
        raise RuntimeError("N2R's solved config does not round-trip through the driver's serialisation")

    candidate = copy.deepcopy(solved)
    # (1) THE OPERATOR CHANGE: K -> K - K_port.
    ports = candidate["Boundaries"]["LumpedPort"]
    if len(ports) != 1 or ports[0]["Index"] != 1 or ports[0]["Attributes"] != [10]:
        raise RuntimeError("unexpected LumpedPort block; refusing to edit it blindly")
    if "Active" in ports[0]:
        raise RuntimeError("the solved config already carries an Active flag")
    ports[0]["Active"] = False
    # (2) POSTPROCESSING ONLY: the three declared probe points.
    if "Postprocessing" in candidate["Domains"]:
        raise RuntimeError("the solved config already carries Domains.Postprocessing")
    candidate["Domains"]["Postprocessing"] = {
        "Probe": [{"Index": i + 1, "Center": list(c)} for i, c in enumerate(PROBES_MM)]
    }

    # Assert the delta is EXACTLY those two things and nothing else.
    before, after = _paths_of(solved), _paths_of(candidate)
    changed = {k for k in before.keys() & after.keys() if before[k] != after[k]}
    removed = before.keys() - after.keys()
    added = after.keys() - before.keys()
    expected_added = {"Boundaries.LumpedPort[0].Active"} | {
        f"Domains.Postprocessing.Probe[{i}].{k}"
        for i in range(len(PROBES_MM)) for k in ("Index",)
    } | {
        f"Domains.Postprocessing.Probe[{i}].Center[{j}]"
        for i in range(len(PROBES_MM)) for j in range(3)
    }
    if changed or removed or added != expected_added:
        raise RuntimeError(f"unexpected delta: changed={sorted(changed)} removed={sorted(removed)} "
                           f"unexpected_added={sorted(added - expected_added)} "
                           f"missing={sorted(expected_added - added)}")
    diff = "".join(difflib.unified_diff(
        raw.splitlines(keepends=True), _serialise(candidate).splitlines(keepends=True),
        fromfile=f"results/{N2R_RECORD}/L2/solver/config.json",
        tofile="experiments/PO1-port-removed-control/config.candidate.json"))
    return solved, candidate, diff


def main() -> None:
    out = HERE
    if "results" in out.resolve().parts:
        raise SystemExit("refusing to write a candidate under results/")
    solved, candidate, diff = build()
    text = _serialise(candidate)
    (out / "config.candidate.json").write_text(text)
    (out / "config.delta.txt").write_text(diff)
    print(diff, end="")
    print(f"\nN2R solved config sha256 : {N2R_SOLVED_CONFIG_SHA256}")
    print(f"PO1 candidate config sha256: {_sha256(text)}")
    print(f"baseline mesh sha256       : {BASELINE_MESH_SHA256}")
    print("\nthe delta is exactly: Boundaries.LumpedPort[0].Active = false (the operator change),")
    print("plus Domains.Postprocessing.Probe with three declared points (postprocessing only).")
    return None


if __name__ == "__main__":
    sys.exit(main())
