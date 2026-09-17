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
    # The only available upper bound is uniform refinement, and it is OVER budget,
    # so the offline knowledge is an interval that straddles the limit. A lower
    # bound cannot discharge an upper limit and must not be quoted as headroom.
    assert dof["rigorous_upper_bound"] > BUDGET
    assert dof["rigorous_lower_bound"] < BUDGET < dof["rigorous_upper_bound"]
    assert "89x" in dof["breach_argument"], "the useful offline argument is the breach argument"
    # And the gate stays enforceable at launch rather than being weakened.
    assert "ND (p = 1)" in dof["enforcement"]


def test_inserted_midpoints_never_extend_the_port_point_cloud(mesh):
    """A NECESSARY condition for the lumped-port geometry to be invariant.

    Palace takes the port's w and l from ``mesh::GetBoundingBox`` on attribute 10
    (lumpedelement.cpp:22-69), and MFEM's bisection inserts only edge midpoints
    (mesh.cpp:10834-10841). This checks the axis-aligned extent is unmoved by
    inserting every midpoint.

    It is deliberately NOT the whole claim. Palace's box is ORIENTED, not
    axis-aligned (geodata.hpp:124-128), so this test checks a necessary
    condition, not the invariance itself. The two coincide here only because the
    port is an exactly axis-aligned planar rectangle, which is also asserted
    below. The remaining step -- that no midpoint can become a new extremum of
    the oriented box, and that the tie-break is rescued by axes being re-sorted
    by length -- is argued in the feasibility document, not here.
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


def test_the_approval_names_exactly_one_approved_experiment():
    """Whatever is approved, exactly ONE mechanism may be, under unchanged rules.

    Deliberately experiment-AGNOSTIC. An earlier version pinned the approved id,
    so every new approval broke it and had to be edited in the approving commit
    -- the same coupling that made seven historical R1 tests fail when N1 was
    approved. What must hold for any approval is asserted here; what was true of
    one finished run belongs in that run's own pinned fixture.
    """
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    mechanisms = [k for k in ("port_refinement", "palace_refinement") if k in approval]
    assert len(mechanisms) == 1, (
        f"exactly one refinement mechanism may be approved, found {mechanisms}: "
        "two would be two experiments on two different meshes"
    )
    which = mechanisms[0]
    assert approval[which].get("id"), "the approved experiment must be labelled"
    # Byte-identity with the named mesh is the control, so a hash is required.
    assert approval.get("baseline_mesh_sha256") or approval.get("dry_run_mesh_sha256")
    assert approval.get("baseline_record")
    # And the rules it runs under are the unchanged ones.
    assert approval["constraints"]["dof_budget"] == BUDGET
    assert approval["constraints"]["per_solve_wall_clock_cap_s"] == 2700
    golden = (REPO_ROOT / ".github" / "workflows" / "palace-golden.yml").read_text()
    for path in ("solvers/palace/**", "docker/palace.Dockerfile", "scripts/palace_golden_run.py"):
        assert path in golden
    assert not str(CANDIDATE.relative_to(REPO_ROOT)).startswith(("solvers/palace", "docker"))


# --- the executed path: Palace-side refinement and the DOF probe ---------------

def _ladder():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_ladder_n1", REPO_ROOT / "scripts" / "palace_order1_ladder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakePopen:
    """A Palace that prints the real assembly lines and then keeps going."""

    class _Pipe:
        """A closable line iterator, as subprocess hands back."""

        def __init__(self, lines):
            self._it = iter(lines)
            self.closed = False

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._it)

        def close(self):
            self.closed = True

    def __init__(self, lines, **_):
        self.stdout = self._Pipe(lines)
        self.returncode = 0
        self.waited = False

    def wait(self, timeout=None):
        self.waited = True
        return 0

    def kill(self):
        self.returncode = -9


ASSEMBLY = [
    " Parallel Mesh Stats:\n",
    " edges            79944       79944\n",
    "Assembling system matrices, number of global unknowns:\n",
    " H1 (p = 1): 13991, ND (p = 1): {dof}, RT (p = 1): 130388\n",
    "Configuring SLEPc eigenvalue solver:\n",
    " Found 6 converged eigenvalues\n",
]


def _run_with(monkeypatch, tmp_path, dof, budget):
    ladder = _ladder()
    lines = [line.format(dof=dof) for line in ASSEMBLY]
    killed = []
    monkeypatch.setattr(ladder.subprocess, "Popen", lambda *a, **k: _FakePopen(lines))
    monkeypatch.setattr(
        ladder.subprocess, "run",
        lambda cmd, **k: killed.append(cmd) or type("R", (), {"returncode": 0})(),
    )
    info = ladder._run_palace(
        "docker", "img", tmp_path, 1, "probe-test", dof_budget=budget,
    )
    return info, killed


def test_the_dof_probe_reads_the_count_palace_actually_assembled(monkeypatch, tmp_path):
    """Under budget: the count is recorded and nothing is killed."""
    info, killed = _run_with(monkeypatch, tmp_path, dof=81_000, budget=BUDGET)
    probe = info["dof_probe"]
    assert probe["armed"] is True
    assert probe["dof_reported"] == 81_000
    assert probe["refused"] is False
    assert not killed, "an in-budget run must not be killed"
    assert info["dof_probe"]["reader_error"] is None
    assert info["dof_probe"]["seen_at_wall_s"] is not None, "when the count arrived is recorded"
    assert "ND (p = 1): 81000" in (tmp_path / "palace_log.txt").read_text()


def test_the_dof_probe_kills_the_container_when_the_budget_is_exceeded(monkeypatch, tmp_path):
    """Over budget: refused, and the container is killed.

    This is the 250 000 rule for a mesh that cannot be counted offline. It has
    to fire on the assembly line, which Palace prints before it configures the
    eigensolver -- so the refusal costs seconds, not the 45-minute cap.
    """
    info, killed = _run_with(monkeypatch, tmp_path, dof=250_001, budget=BUDGET)
    probe = info["dof_probe"]
    assert probe["dof_reported"] == 250_001
    assert probe["refused"] is True
    assert killed and killed[0][:2] == ["docker", "kill"]


def test_the_probe_is_disarmed_when_the_mesh_was_counted_offline(monkeypatch, tmp_path):
    """A plain rung already refused before launch; the probe must not double up."""
    info, killed = _run_with(monkeypatch, tmp_path, dof=250_001, budget=None)
    assert info["dof_probe"]["armed"] is False
    assert info["dof_probe"]["refused"] is False
    assert not killed


def test_the_approval_refuses_both_mechanisms_at_once(tmp_path):
    """They are different experiments on different meshes. Approve one."""
    ladder = _ladder()
    approval = tmp_path / "a.json"
    approval.write_text(json.dumps({
        "level": 2,
        "baseline_record": "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "port_refinement": {"id": "R1", "h_port_mm": 0.003, "pad_mm": 0.01, "transition_mm": 0.02},
        "palace_refinement": {"id": "N1", "boxes": [
            {"Levels": 1, "BoundingBoxMin": [0, 0, 0], "BoundingBoxMax": [1, 1, 1]}]},
    }))
    with pytest.raises(ladder.LadderError, match="BOTH"):
        ladder.approved_palace_refinement(approval)


@pytest.mark.parametrize(
    "block, match",
    [
        ({"id": "N1"}, "missing"),
        ({"id": "N1", "boxes": [], "extra": 1}, "unknown"),
        ({"id": "N1", "boxes": []}, "non-empty"),
        ({"id": "N1", "boxes": [{"Levels": 0, "BoundingBoxMin": [0, 0, 0],
                                 "BoundingBoxMax": [1, 1, 1]}]}, "Levels"),
        ({"id": "N1", "boxes": [{"Levels": 1, "BoundingBoxMin": [1, 1, 1],
                                 "BoundingBoxMax": [0, 0, 0]}]}, "not strictly below"),
    ],
)
def test_a_malformed_approval_is_refused_rather_than_ignored(tmp_path, block, match):
    """A typo must not silently become 'no refinement' and solve the wrong thing."""
    ladder = _ladder()
    approval = tmp_path / "a.json"
    approval.write_text(json.dumps({
        "level": 2,
        "baseline_record": "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "palace_refinement": block,
    }))
    with pytest.raises(ladder.LadderError, match=match):
        ladder.approved_palace_refinement(approval)


def test_a_refined_record_is_kept_out_of_the_convergence_fit_by_either_mechanism():
    """any_refinement() is the single gate; neither mechanism may slip through."""
    ladder = _ladder()
    assert ladder.any_refinement({}) is None
    assert ladder.any_refinement({"port_refinement": None, "palace_refinement": None}) is None
    assert ladder.any_refinement({"port_refinement": {"id": "R1"}}) == {"id": "R1"}
    assert ladder.any_refinement({"palace_refinement": {"id": "N1"}}) == {"id": "N1"}


def test_a_silent_probe_refuses_rather_than_publishing_a_budget_claim(monkeypatch, tmp_path):
    """Armed and never fired means the 250 000 rule was never applied.

    A COMPLETED record would then assert budget compliance on the UNREFINED
    count. Refuse instead.
    """
    ladder = _ladder()
    lines = [line for line in ASSEMBLY if "ND (p = 1)" not in line]  # Palace never prints it
    monkeypatch.setattr(ladder.subprocess, "Popen", lambda *a, **k: _FakePopen(lines))
    monkeypatch.setattr(ladder.subprocess, "run",
                        lambda cmd, **k: type("R", (), {"returncode": 0})())
    info = ladder._run_palace("docker", "i", tmp_path, 1, "n", dof_budget=BUDGET)
    assert info["dof_probe"]["armed"] is True
    assert info["dof_probe"]["dof_reported"] is None
    assert info["dof_probe"]["refused"] is False, "nothing to refuse on; the miss is the problem"


def test_a_reader_failure_is_recorded_and_does_not_silently_disarm(monkeypatch, tmp_path):
    """An unguarded reader would disarm the probe AND truncate the log, silently."""
    ladder = _ladder()

    class _Exploding(_FakePopen):
        def __init__(self, *a, **k):
            super().__init__(["first\n"], **k)
            self._boom = True

        class _Pipe:
            def __init__(self, *_):
                self._n = 0

            def __iter__(self):
                return self

            def __next__(self):
                self._n += 1
                if self._n == 1:
                    return "first\n"
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad byte")

            def close(self):
                pass

    monkeypatch.setattr(ladder.subprocess, "Popen", lambda *a, **k: _Exploding())
    monkeypatch.setattr(ladder.subprocess, "run",
                        lambda cmd, **k: type("R", (), {"returncode": 0})())
    info = ladder._run_palace("docker", "i", tmp_path, 1, "n", dof_budget=BUDGET)
    assert info["dof_probe"]["reader_error"], "the failure must reach the record"
    assert "UnicodeDecodeError" in info["dof_probe"]["reader_error"]


def test_the_approval_requires_the_baseline_mesh_hash(tmp_path):
    """Byte-identity is the control. Without the hash the gate is skipped, so a
    missing key must refuse rather than silently drop it."""
    ladder = _ladder()
    approval = tmp_path / "a.json"
    body = {
        "level": 2,
        "baseline_record": "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "palace_refinement": {"id": "N1", "boxes": [
            {"Levels": 1, "BoundingBoxMin": [-0.62, -0.125, -0.01],
             "BoundingBoxMax": [-0.58, -0.065, 0.01]}]},
    }
    approval.write_text(json.dumps(body))
    with pytest.raises(ladder.LadderError, match="baseline_mesh_sha256"):
        ladder.approved_palace_refinement(approval)

    # And the gmsh path's key is NOT accepted in its place.
    approval.write_text(json.dumps({**body, "dry_run_mesh_sha256": {"N1": "deadbeef"}}))
    with pytest.raises(ladder.LadderError, match="baseline_mesh_sha256"):
        ladder.approved_palace_refinement(approval)


def test_a_record_reports_the_dof_it_solved_not_the_one_it_loaded():
    """Reporting the loaded 79 944 as a refined run's DOF would be false."""
    ladder = _ladder()
    assert ladder.solved_dof({"dof_measured": 79_944}) == 79_944
    assert ladder.solved_dof({"dof_measured": 79_944, "dof_solved": 96_300}) == 96_300
    assert ladder.solved_dof({}) is None


def test_the_not_refined_sentinel_is_one_constant():
    """Two copies drifted apart once and every plain rung grew two empty sections."""
    ladder = _ladder()
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    assert ladder.NOT_REFINED == "not a refined run"
    assert '"not a port-refined run"' not in source, "the stale literal must be gone"


# --- N2: one further level on the same region ---------------------------------

N2_CANDIDATE = REPO_ROOT / "experiments" / "N2-nested-port-refinement"
N1_RECORD = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-N1-20260917T001735Z"
L2_RECORD = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-20260916T080802Z"


@pytest.fixture(scope="module")
def n2():
    return json.loads((N2_CANDIDATE / "candidate.json").read_text())


def test_n2_pins_the_original_mesh_the_n1_record_and_the_stack(n2):
    """The three things that must not drift between now and approval."""
    pin = n2["pinned"]
    assert pin["original_L2_mesh_sha256"] == hashlib.sha256(MSH.read_bytes()).hexdigest()
    assert pin["original_L2_record"] == L2_RECORD.name
    assert pin["n1_reference_record"] == N1_RECORD.name
    assert (N1_RECORD / "summary.json").is_file(), "the N1 reference must be on disk"
    assert pin["palace_commit"] == "a61c8cbe0cacf496cde3c62e93085fae0d6299ac"
    assert pin["mfem_commit"] == "c444b17c973cc301590a6ac186fb33587b5881e6"


def test_n2_is_two_total_levels_on_n1s_unchanged_box(n2):
    """TWO TOTAL levels from the original mesh -- one beyond N1, not two beyond."""
    region = n2["refinement_region"]
    assert region["Levels"] == 2
    n1_box = json.loads((N1_RECORD / "L2" / "solver" / "config.json").read_text())
    n1_box = n1_box["Model"]["Refinement"]["Boxes"][0]
    assert n1_box["Levels"] == 1, "N1 is the one-level point"
    assert region["BoundingBoxMin"] == n1_box["BoundingBoxMin"]
    assert region["BoundingBoxMax"] == n1_box["BoundingBoxMax"]

    cfg = json.loads((N2_CANDIDATE / "config.candidate.json").read_text())
    box = cfg["Model"]["Refinement"]["Boxes"][0]
    assert box["Levels"] == 2
    assert (box["BoundingBoxMin"], box["BoundingBoxMax"]) == (
        n1_box["BoundingBoxMin"], n1_box["BoundingBoxMax"]
    )
    # The mesh is the ORIGINAL L2 file, not a regenerated one.
    assert cfg["Model"]["Mesh"] == "coupled_chip_cell_L2.msh"


def test_the_n2_config_differs_from_n1s_only_in_the_level_count(n2):
    """Everything the approval froze must be untouched: the delta is one integer."""
    n1 = json.loads((N1_RECORD / "L2" / "solver" / "config.json").read_text())
    n2cfg = json.loads((N2_CANDIDATE / "config.candidate.json").read_text())
    strip = lambda c: {**c, "Model": {k: v for k, v in c["Model"].items() if k != "Refinement"}}
    assert strip(n2cfg) == strip(n1), "only Model.Refinement may differ"
    assert n2cfg["Solver"] == n1["Solver"], "no solver setting is changed to make N2 fit"
    assert n2cfg["Boundaries"] == n1["Boundaries"]
    assert n2cfg["Domains"] == n1["Domains"]


def test_n2_does_not_invent_a_dof_it_cannot_measure(n2):
    """Stage 2 marks on the stage-1 mesh, which does not exist offline.

    No bound for stage 2 is computable -- not even the lower bound that stage 1
    had. A number here would be invented.
    """
    dof = n2["dof"]
    assert dof["n2_measured"] is None
    assert dof["why_no_n2_number"]
    assert dof["n1_measured"] == 84_485
    assert str(dof["n1_measured"]) in dof["rigorous_offline_statement"]
    assert dof["budget"] == BUDGET


def test_n2_discloses_the_hierarchy_change_and_refuses_to_extrapolate_runtime(n2):
    """N1 took 11.4x the baseline's time for 5.7 % more DOF; DOF does not predict runtime."""
    res = n2["resource_uncertainty"]
    assert res["n1_wall_clock_s"] == pytest.approx(923.5, abs=0.1)
    assert res["cap_s"] == 2700
    assert "not proportional" in res["do_not_extrapolate"].lower() or \
           "NOT proportional" in res["do_not_extrapolate"]
    assert "AUTOMATIC" in res["hierarchy_change_disclosed"]
    assert "THREE" in res["hierarchy_change_disclosed"], "N2 gets a third multigrid level"
    assert "CAP" in res["primary_risk"].upper()


def test_the_probe_enforces_on_the_largest_count_not_the_first(monkeypatch, tmp_path):
    """A multi-level hierarchy must not let an earlier, coarser count pass.

    Palace prints this line once from the finest space, so today first == finest.
    The guard takes the max anyway: enforcing on a coarse count is the one
    failure it exists to prevent.
    """
    ladder = _ladder()
    lines = [
        " H1 (p = 1): 13991, ND (p = 1): 79944, RT (p = 1): 130388\n",   # coarse, in budget
        " H1 (p = 1): 40000, ND (p = 1): 260000, RT (p = 1): 400000\n",  # finest, OVER
    ]
    killed = []
    monkeypatch.setattr(ladder.subprocess, "Popen", lambda *a, **k: _FakePopen(lines))
    monkeypatch.setattr(ladder.subprocess, "run",
                        lambda cmd, **k: killed.append(cmd) or type("R", (), {"returncode": 0})())
    info = ladder._run_palace("docker", "i", tmp_path, 1, "n", dof_budget=BUDGET)
    probe = info["dof_probe"]
    assert probe["dof_reported_all"] == [79_944, 260_000]
    assert probe["dof_reported"] == 260_000, "the largest, not the first"
    assert probe["ambiguous"] is True, "two distinct counts is an ambiguity worth recording"
    assert probe["refused"] is True and killed


def test_a_shallower_point_of_the_same_sequence_is_a_valid_baseline():
    """N1 is refined, and IS N2's correct baseline. Anything else still is not."""
    ladder = _ladder()
    box = {"Levels": 1, "BoundingBoxMin": [-0.62, -0.125, -0.01],
           "BoundingBoxMax": [-0.58, -0.065, 0.01]}
    n1_rung = {"palace_refinement": {"boxes": [box]}}
    n2_entry = {"palace_refinement": {"boxes": [{**box, "Levels": 2}]}}

    assert ladder.is_prior_point_of_same_sequence(n2_entry, n1_rung) is True
    # Same depth is not a step.
    assert ladder.is_prior_point_of_same_sequence(n2_entry, {"palace_refinement": {"boxes": [{**box, "Levels": 2}]}}) is False
    # Deeper baseline is not a prior point.
    assert ladder.is_prior_point_of_same_sequence(n1_rung, n2_entry) is False
    # A DIFFERENT region is not this sequence, whatever its depth.
    other = {"palace_refinement": {"boxes": [{**box, "Levels": 1,
                                             "BoundingBoxMin": [0.0, 0.0, 0.0]}]}}
    assert ladder.is_prior_point_of_same_sequence(n2_entry, other) is False

    # A per-box REGRESSION must not hide behind an increase in another box.
    b2 = {"Levels": 1, "BoundingBoxMin": [1.0, 1.0, 1.0], "BoundingBoxMax": [2.0, 2.0, 2.0]}
    deeper_but_regressed = {"palace_refinement": {"boxes": [{**box, "Levels": 9},
                                                            {**b2, "Levels": 1}]}}
    baseline_two = {"palace_refinement": {"boxes": [{**box, "Levels": 1},
                                                    {**b2, "Levels": 5}]}}
    assert ladder.is_prior_point_of_same_sequence(deeper_but_regressed, baseline_two) is False

    # Reordering the boxes is the SAME prescription and must still be accepted.
    reordered = {"palace_refinement": {"boxes": [{**b2, "Levels": 5}, {**box, "Levels": 1}]}}
    deeper = {"palace_refinement": {"boxes": [{**box, "Levels": 2}, {**b2, "Levels": 5}]}}
    assert ladder.is_prior_point_of_same_sequence(deeper, reordered) is True
    # A gmsh-refined record is never a point of a Palace sequence.
    assert ladder.is_prior_point_of_same_sequence(n2_entry, {"port_refinement": {"id": "R1"}}) is False


def test_sequence_records_must_end_at_the_baseline(tmp_path):
    """The primary comparison is the LAST step; a mismatch would silently
    compare against something other than the record named as the baseline."""
    ladder = _ladder()
    approval = tmp_path / "a.json"
    body = {
        "level": 2,
        "baseline_record": N1_RECORD.name,
        "baseline_mesh_sha256": hashlib.sha256(MSH.read_bytes()).hexdigest(),
        "palace_refinement": {"id": "N2", "boxes": [
            {"Levels": 2, "BoundingBoxMin": [-0.62, -0.125, -0.01],
             "BoundingBoxMax": [-0.58, -0.065, 0.01]}]},
        "sequence_records": [L2_RECORD.name],   # ends at L2, not at the baseline
    }
    approval.write_text(json.dumps(body))
    with pytest.raises(ladder.LadderError, match="must end at baseline_record"):
        ladder.approved_palace_refinement(approval)

    body["sequence_records"] = [L2_RECORD.name, "COUPLED-LADDER-O1-L2-NOPE"]
    approval.write_text(json.dumps(body))
    with pytest.raises(ladder.LadderError, match="not a record on disk"):
        ladder.approved_palace_refinement(approval)

    body["sequence_records"] = [L2_RECORD.name, N1_RECORD.name]
    approval.write_text(json.dumps(body))
    label, boxes, sha = ladder.approved_palace_refinement(approval)
    assert label == "N2" and boxes[0]["Levels"] == 2


def test_the_sequence_reports_both_participations_without_conflating_them():
    """Derived and reported are different quantities; the record says which."""
    ladder = _ladder()
    step = ladder.compare_against_baseline(
        json.loads((N1_RECORD / "summary.json").read_text())["rung"], L2_RECORD.name,
    )
    assert step["available"]
    for pair in step["pairs"]:
        derived = pair["port_participation_from_probes"]
        reported = pair["port_participation_reported_by_palace"]
        assert derived["baseline"] is not None and reported["baseline"] is not None
        assert "SURROGATE" in reported["what"]
        # Cauchy-Schwarz bounds E_ind/E_port <= 1 for the EXACT quantities. The
        # derived value is itself an estimate built from the difference
        # p_Default - p_MA, so this ordering is guaranteed for the exact ratio
        # and OBSERVED here. Asserted at the margin the data actually has (~1e-5
        # on mode 1, ~2.4e-4 on mode 2), not at 1e-9, so a run where the
        # cancellation bites is reported rather than failing this test.
        assert reported["baseline"] <= derived["baseline"] * (1 + 1e-3)
        assert reported["refined"] <= derived["refined"] * (1 + 1e-3)


def test_the_sequence_refuses_to_fit_an_order_or_a_limit():
    """Three local points are not a convergence sequence in h."""
    ladder = _ladder()
    out = ladder.refinement_sequence({"palace_refinement": {"boxes": []}}, [])
    assert out["available"] is False
    text = out["not_a_convergence_fit"]
    assert "LOCAL" in text and "NOT global mesh convergence" in text
    assert "no order is fitted" in text and "no continuum limit" in text


def test_the_approval_carries_exactly_the_reviewed_n2_keys():
    """N2 is approved. The live approval must match the reviewed candidate."""
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    cand = json.loads((N2_CANDIDATE / "candidate.json").read_text())
    assert approval["palace_refinement"]["id"] == "N2"
    assert "port_refinement" not in approval, "the gmsh path is not approved"
    box = approval["palace_refinement"]["boxes"][0]
    region = cand["refinement_region"]
    assert box["Levels"] == region["Levels"] == 2, "TWO TOTAL levels from the original mesh"
    assert box["BoundingBoxMin"] == region["BoundingBoxMin"]
    assert box["BoundingBoxMax"] == region["BoundingBoxMax"]
    assert approval["baseline_record"] == cand["pinned"]["n1_reference_record"]
    assert approval["sequence_records"] == [
        cand["pinned"]["original_L2_record"], cand["pinned"]["n1_reference_record"]
    ]
    assert approval["baseline_mesh_sha256"] == cand["pinned"]["original_L2_mesh_sha256"]
    # The rule and the cap are the unchanged ones.
    assert approval["constraints"]["dof_budget"] == BUDGET
    assert approval["constraints"]["per_solve_wall_clock_cap_s"] == 2700
    assert not str(N2_CANDIDATE.relative_to(REPO_ROOT)).startswith(("solvers/palace", "docker"))


def test_every_summary_field_has_a_default_before_the_guarded_window():
    """A field initialised INSIDE the post-solve guard is unbound if the analysis
    raises early, and the summary write then fails OUTSIDE the guard.

    That is how a completed solve was destroyed once, and adding
    `refinement_sequence` reintroduced it. This asserts structurally that every
    name the summary reads is bound before the `try`, so the next field added
    cannot repeat it.
    """
    import ast

    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    tree = ast.parse(source)
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")

    # The guarded window is the try whose handler records post-solve failure.
    guard = next(n for n in ast.walk(main)
                 if isinstance(n, ast.Try)
                 and any("analysis_failed" in ast.dump(h) for h in n.handlers))

    bound_before = set()
    for node in main.body:
        if node is guard:
            break
        for sub in ast.walk(node):
            if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                bound_before.add(sub.target.id)
            elif isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if isinstance(t, ast.Name):
                        bound_before.add(t.id)

    # Names the summary dict reads, that are also assigned inside the guard.
    assigned_in_guard = {
        sub.target.id if isinstance(sub, ast.AnnAssign) else t.id
        for node in guard.body for sub in ast.walk(node)
        if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name)
        for t in [sub.target]
    } | {
        t.id
        for node in guard.body for sub in ast.walk(node)
        if isinstance(sub, ast.Assign)
        for t in sub.targets if isinstance(t, ast.Name)
    }

    summary_assign = next(
        n for n in ast.walk(main)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "summary" for t in n.targets)
    )
    read_by_summary = {n.id for n in ast.walk(summary_assign.value) if isinstance(n, ast.Name)}

    at_risk = (read_by_summary & assigned_in_guard) - bound_before
    assert not at_risk, (
        f"{sorted(at_risk)} are read by the summary but only bound inside the guarded "
        f"window; an early analysis failure would raise UnboundLocalError outside the guard"
    )
