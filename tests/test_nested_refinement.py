"""Checks for the prepared nested-refinement candidate (N1).

These verify facts a reader would otherwise have to take on trust: that the
baseline is untouched, that the marking reproduces, that the budget claim is a
bound and not a measurement, and that refining the port face cannot move the
lumped-port geometry. They assert measurements and source-derived invariants;
they do not assert any interpretation of R1.

Nothing here launches Palace or writes inside a record.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-20260916T080802Z"
SOLVER = BASELINE / "L2" / "solver"
MSH = SOLVER / "coupled_chip_cell_L2.msh"
CANDIDATE = REPO_ROOT / "experiments" / "N1-nested-port-refinement"

PORT_ATTR = 10
BUDGET = 250_000


def _load():
    txt = MSH.read_text().splitlines()
    i = txt.index("$Nodes")
    n = int(txt[i + 1])
    nodes = {
        int(p[0]): (float(p[1]), float(p[2]), float(p[3]))
        for p in (txt[i + 2 + k].split() for k in range(n))
    }
    j = txt.index("$Elements")
    m = int(txt[j + 1])
    tets, tris = [], []
    for k in range(m):
        p = txt[j + 2 + k].split()
        etype, ntags, phys = int(p[1]), int(p[2]), int(p[3])
        conn = tuple(int(x) for x in p[3 + ntags:])
        if etype == 4:
            tets.append((phys, conn))
        elif etype == 2:
            tris.append((phys, conn))
    return nodes, tets, tris


@pytest.fixture(scope="module")
def mesh():
    return _load()


@pytest.fixture(scope="module")
def candidate():
    return json.loads((CANDIDATE / "candidate.json").read_text())


def test_the_preserved_baseline_is_the_mesh_the_candidate_names(candidate):
    """The candidate is derived from the preserved record, not a copy of it."""
    assert MSH.exists(), "the preserved baseline mesh must be present"
    assert hashlib.sha256(MSH.read_bytes()).hexdigest() == candidate["baseline_mesh_sha256"]
    # And the record still verifies against its own manifest entry.
    manifest = (BASELINE / "manifest.sha256").read_text()
    rel = str(MSH.relative_to(BASELINE))
    assert candidate["baseline_mesh_sha256"] in manifest and rel in manifest


def test_order_one_dof_is_the_edge_count_the_record_published(mesh):
    """Anchors the whole budget argument to a number the solver already agreed."""
    _, tets, _ = mesh
    edges = set()
    for _, (a, b, c, d) in tets:
        for e in ((a, b), (a, c), (a, d), (b, c), (b, d), (c, d)):
            edges.add(tuple(sorted(e)))
    published = json.loads((BASELINE / "summary.json").read_text())["rung"]["dof_measured"]
    assert len(edges) == published == 79_944


def test_the_box_marking_reproduces_palace_s_criterion(mesh, candidate):
    """Marking is 'any vertex inside the closed box' (geodata.cpp:282-306).

    Pinned so the declared box cannot drift from the count it was justified by.
    """
    nodes, tets, _ = mesh
    region = candidate["refinement_region"]
    lo, hi = region["BoundingBoxMin"], region["BoundingBoxMax"]
    marked = [
        i
        for i, (_, t) in enumerate(tets)
        if any(all(lo[d] <= nodes[v][d] <= hi[d] for d in range(3)) for v in t)
    ]
    assert len(marked) == candidate["marking"]["marked_tets"]
    assert len(marked) / len(tets) < 0.01, "the region must stay local"


def test_the_budget_claim_is_a_bound_and_is_not_presented_as_a_measurement(candidate):
    """The 250k rule needs a MEASURED DOF. This candidate cannot supply one."""
    dof = candidate["dof"]
    assert dof["measured"] is None, "no offline measurement exists; it must not be invented"
    assert dof["why_not_measured"]
    assert dof["rigorous_lower_bound"] < BUDGET
    # The bound is only a bound: green closure can only add.
    assert dof["rigorous_lower_bound"] > 79_944
    assert dof["uniform_refinement_for_scale"] > BUDGET, (
        "uniform refinement is out of budget, which is why a local region is needed at all"
    )


def test_refining_the_port_face_cannot_move_the_lumped_port_geometry(mesh):
    """Palace takes the port's w and l from the bounding box of attribute 10
    (lumpedelement.cpp:22-69), and MFEM's bisection only inserts edge midpoints
    (mesh.cpp:10834-10841). Midpoints are convex combinations of existing
    vertices, so the box -- and hence w, l, L_s and kappa -- cannot change.

    Asserted by construction rather than argued: insert every midpoint and
    re-measure.
    """
    nodes, _, tris = mesh
    face = [c for phys, c in tris if phys == PORT_ATTR]
    verts = {v for c in face for v in c}

    def bbox(points):
        return tuple(
            (min(p[d] for p in points), max(p[d] for p in points)) for d in range(3)
        )

    before = bbox([nodes[v] for v in verts])
    midpoints = [
        tuple(0.5 * (nodes[a][d] + nodes[b][d]) for d in range(3))
        for c in face
        for a, b in ((c[0], c[1]), (c[1], c[2]), (c[0], c[2]))
    ]
    after = bbox([nodes[v] for v in verts] + midpoints)
    assert before == after

    # Two refinement levels likewise: midpoints of midpoints stay inside.
    twice = midpoints + [
        tuple(0.5 * (midpoints[i][d] + midpoints[j][d]) for d in range(3))
        for i in range(0, len(midpoints), 3)
        for j in (i + 1, i + 2)
    ]
    assert bbox([nodes[v] for v in verts] + twice) == before

    # The declared port is 0.020 x 0.040 mm, planar at z = 0.
    lengths = sorted(hi - lo for lo, hi in before)
    assert lengths[0] == pytest.approx(0.0, abs=1e-12), "planar"
    assert lengths[1] == pytest.approx(0.020, abs=1e-9)
    assert lengths[2] == pytest.approx(0.040, abs=1e-9)


def test_the_candidate_config_changes_only_the_refinement_block(candidate):
    """Everything the approval froze must be untouched: the delta is one block."""
    base = json.loads((SOLVER / "config.json").read_text())
    cand = json.loads((CANDIDATE / "config.candidate.json").read_text())

    assert cand["Model"]["Refinement"] != base["Model"]["Refinement"]
    boxes = cand["Model"]["Refinement"]["Boxes"]
    assert len(boxes) == 1 and boxes[0]["Levels"] == 1

    stripped_base = {**base, "Model": {k: v for k, v in base["Model"].items() if k != "Refinement"}}
    stripped_cand = {**cand, "Model": {k: v for k, v in cand["Model"].items() if k != "Refinement"}}
    assert stripped_cand == stripped_base, "only Model.Refinement may differ"

    # Specifically: the mesh file, the port and the solver are the baseline's.
    assert cand["Model"]["Mesh"] == base["Model"]["Mesh"]
    assert cand["Boundaries"] == base["Boundaries"]
    assert cand["Solver"] == base["Solver"]
    assert cand["Domains"] == base["Domains"]


def test_the_candidate_records_that_refinement_propagates_outside_the_box(candidate):
    """Conforming refinement restores conformity by refining neighbours. The
    record must say so rather than call this a box-only change."""
    prop = candidate["propagation"]
    assert prop["conforming"] is True
    assert "YES" in prop["beyond_the_region"]
    assert candidate["invariants_by_construction"]["parent_child"]


def test_the_marked_region_quality_is_reported_including_the_bad_news(candidate):
    """The marked tets are thinner than the mesh average; that is recorded."""
    q = candidate["quality"]
    assert q["radius_ratio_marked_tets"]["mean"] < q["radius_ratio_all_tets"]["mean"]
    assert 0.0 < q["radius_ratio_marked_tets"]["min"] <= 1.0
    # Both are rounded to 6 dp in the record, so compare at that precision.
    assert q["port_face_mean_edge_after_one_level_mm"] == pytest.approx(
        q["port_face_mean_edge_mm"] / 2, abs=1e-6
    )


def test_no_palace_job_is_triggered_by_this_candidate():
    """The candidate lives outside every workflow trigger path, so committing it
    starts nothing. The ladder trigger is the approval record alone."""
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    assert approval.get("port_refinement", {}).get("id") == "R1", (
        "the approval record must still name R1; N1 is not approved"
    )
    golden = (REPO_ROOT / ".github" / "workflows" / "palace-golden.yml").read_text()
    for path in ("solvers/palace/**", "docker/palace.Dockerfile", "scripts/palace_golden_run.py"):
        assert path in golden
    assert not str(CANDIDATE.relative_to(REPO_ROOT)).startswith(("solvers/palace", "docker"))
