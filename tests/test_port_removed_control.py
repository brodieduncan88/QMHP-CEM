"""PO1, the port-removed control: exact delta, corrected accounting, and an option that is built but not armed."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REC = REPO_ROOT / "experiments" / "PO1-port-removed-control"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "po1-port-removed-control.md"
N2R_RECORD = "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z"
N2R_SOLVED = REPO_ROOT / "results" / N2R_RECORD / "L2" / "solver" / "config.json"
CANDIDATE_SHA256 = "2826e78c026097aeb90dc1f50ec2b08e2afefce7ecbb43270d34b7667e0d1728"
APPROVAL = REPO_ROOT / ".github" / "ladder-approval.json"


def _norm(text: str) -> str:
    lines = [ln.lstrip().removeprefix("> ").removeprefix(">") for ln in text.splitlines()]
    return " ".join(" ".join(lines).split())


def _leaves(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_leaves(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_leaves(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


@pytest.fixture(scope="module")
def candidate():
    return json.loads((REC / "candidate.json").read_text())


@pytest.fixture(scope="module")
def config():
    return json.loads((REC / "config.candidate.json").read_text())


@pytest.fixture(scope="module")
def ladder():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "po1_ladder", REPO_ROOT / "scripts" / "palace_order1_ladder.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def po1_approval():
    """An approval that WOULD authorise PO1. Written to a temporary file only."""
    approval = copy.deepcopy(json.loads(APPROVAL.read_text()))
    approval["port_control"] = "PO1-port-removed"
    approval["baseline_record"] = N2R_RECORD
    approval["palace_refinement"] = {
        "id": "PO1",
        "boxes": json.loads(N2R_SOLVED.read_text())["Model"]["Refinement"]["Boxes"],
        "solver_linear_overrides": {"MGMaxLevels": 1},
    }
    return approval


def _write(tmp_path: Path, approval: dict, name: str = "approval.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(approval, indent=1))
    return path


# --- the prepared candidate -----------------------------------------------------------


def test_the_candidate_is_prepared_not_approved(candidate):
    assert candidate["id"] == "PO1"
    assert candidate["status"] == "PREPARED, NOT APPROVED, NOT LAUNCHED"
    assert "NOT an extraction" in candidate["not_this"]
    assert "NOT APPROVED" in _norm(DOC.read_text())


def test_the_config_delta_against_N2R_is_exactly_two_additions(config):
    a, b = _leaves(json.loads(N2R_SOLVED.read_text())), _leaves(config)
    assert not {k for k in a.keys() & b.keys() if a[k] != b[k]}, "no existing value may change"
    assert not (a.keys() - b.keys()), "nothing may be removed"
    added = b.keys() - a.keys()
    assert "Boundaries.LumpedPort[0].Active" in added
    assert all(k.startswith("Domains.Postprocessing.Probe[") or k == "Boundaries.LumpedPort[0].Active"
               for k in added), sorted(added)


def test_the_operator_change_is_the_port_deactivation(config):
    port = config["Boundaries"]["LumpedPort"][0]
    assert port["Active"] is False
    assert port["Index"] == 1 and port["Attributes"] == [10] and port["Direction"] == "+Y"
    assert port["L"] == 1.0345665367517793e-07
    assert config["Solver"]["Order"] == 1
    assert config["Solver"]["Linear"]["MGMaxLevels"] == 1
    assert config["Model"]["Refinement"]["Boxes"][0]["Levels"] == 2
    assert config["Model"]["Refinement"]["UniformLevels"] == 0
    assert config["Model"]["Mesh"] == "coupled_chip_cell_L2.msh"
    assert config["Solver"]["Eigenmode"] == {"N": 6, "Tol": 1e-06, "Target": 0.5, "Save": 6}


def test_the_probe_block_is_postprocessing_only_and_pinned_in_source(config):
    from solvers.palace.coupled_config import PO1_PROBES_MM

    probes = config["Domains"]["Postprocessing"]["Probe"]
    assert [p["Index"] for p in probes] == [1, 2, 3]
    assert [p["Center"] for p in probes] == [list(c) for c in PO1_PROBES_MM]
    assert all(p["Center"][2] == 0.01 for p in probes), "one common height, fixed in advance"
    # prepare.py imports them rather than restating them, so the two cannot drift
    src = (REC / "prepare.py").read_text()
    assert "from solvers.palace.coupled_config import PO1_PROBES_MM as PROBES_MM" in src


def test_prepare_reproduces_the_candidate_byte_for_byte():
    before = (REC / "config.candidate.json").read_bytes()
    proc = subprocess.run([sys.executable, str(REC / "prepare.py")], capture_output=True, text=True,
                          cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    assert (REC / "config.candidate.json").read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == CANDIDATE_SHA256
    diff = (REC / "config.delta.txt").read_text()
    assert '+        "Active": false' in diff
    assert '"Probe"' in diff


# --- 1. the corrected null-space accounting ------------------------------------------


def test_the_one_extra_direction_claim_is_withdrawn_and_not_restated(candidate):
    ns = candidate["null_space"]
    w = ns["WITHDRAWN"]
    assert "EXACTLY ONE" in w["claim"]
    assert "PEC" in w["why_it_was_wrong"] and "pinned, not free" in w["why_it_was_wrong"]
    assert "no count is put in its place" in _norm(json.dumps(ns)).lower()
    # the falsification rule is gone, not reworded
    assert "more_than_one_near_zero_mode_would_falsify_this_accounting" not in ns
    assert "falsify" in w["the_falsification_rule_is_removed"]
    norm = _norm(DOC.read_text())
    assert "is withdrawn" in norm
    assert "not determined by anything in the record" in norm
    # and the old count is never restated as live
    assert "adds **exactly one**" not in norm


def test_the_four_spaces_are_distinguished(candidate):
    four = candidate["null_space"]["four_things_that_must_not_be_conflated"]
    assert set(four) == {
        "1_raw_gradient_null_space",
        "2_conductor_charge_modes",
        "3_the_projectors_removed_space",
        "4_returned_near_zero_eigenpairs",
    }
    assert "order 1e4, not 1" in four["1_raw_gradient_null_space"]
    assert "does not eliminate all DC modes" in four["3_the_projectors_removed_space"]
    bound = candidate["null_space"]["what_IS_provable_from_the_assembly"]
    assert "ker(K_curl) INTERSECT ker(K_port)" in bound["statement"]
    assert "at most rank(K_port)" in bound["the_only_bound"]


def test_the_projector_change_is_documented_and_not_configured(candidate):
    proj = candidate["null_space"]["the_projector_changes_AUTOMATICALLY_and_is_not_configured"]
    joined = " ".join(proj["mechanism"])
    assert "GetLsAttrList" in joined and "aux_bdr_marker" in joined
    assert "GetAuxBdrTDofLists" in joined or "GetEssentialTrueDofs" in joined
    assert "SHRINKS" in proj["the_consequence_here"]
    assert "DivFreeTol and DivFreeMaxIts stay at Palace's defaults" in proj["no_setting_is_touched"]
    assert "not to the operator alone" in proj["what_this_costs_the_control"]
    # the source facts the claim rests on
    norm = _norm(DOC.read_text())
    assert "aux_bdr_marker(PO1) = aux_bdr_marker(N2R) minus the port-face attribute" in norm
    assert "recorded, not configured" in norm


def test_N2R_m1_is_not_claimed_curl_free(candidate):
    ref = candidate["energy_diagnostics"]["N2R_reference_values_CORRECTED"]
    assert "not zero" in ref["m1_is_NOT_asserted_to_be_curl_free"]
    assert "1.184775005e-05" in ref["m1_is_NOT_asserted_to_be_curl_free"]
    assert "not asserted to be a curl-free" in _norm(DOC.read_text())


def test_near_zero_omega_postprocessing_is_accounted_for(candidate):
    nz = candidate["null_space"]["near_zero_frequency_postprocessing"]
    hazards = " ".join(nz["hazards_in_order"])
    assert "Frequency domain lumped port postprocessing requires nonzero frequency" in hazards
    assert "-1.0 / (1i * omega)" in hazards
    assert "no CSV rows at all" in hazards
    survives = " ".join(nz["evidence_that_survives_each_case"])
    assert "palace_log.txt" in survives and "bind-mounted" in survives
    assert "RUN_FAILED" in survives and "ERROR" in survives
    assert "There is no retry." in nz["pre_declared_handling"] or "no retry" in nz["pre_declared_handling"]
    assert "not rescued by retuning or rerunning" in nz["if_no_usable_positive_frequency_result"]
    assert "MFEM_USE_GSLIB" in candidate["null_space"]["gslib_precondition"]["requirement"]


def test_the_gslib_precondition_is_backed_by_the_repository(candidate):
    # the claim in the record must match the build file this workflow actually uses
    assert "-DPALACE_WITH_GSLIB=ON" in (REPO_ROOT / "docker" / "palace.Dockerfile").read_text()
    assert list((REPO_ROOT / "results").glob("PALACE-VERIFY-*/runs/*/solver/postpro/probe-E.csv"))


# --- 2. the corrected energy diagnostics ---------------------------------------------


def test_the_N2R_energy_ratios_are_the_corrected_ones(candidate):
    ref = candidate["energy_diagnostics"]["N2R_reference_values_CORRECTED"]
    assert ref["m1"] == pytest.approx(0.0017759330546, rel=1e-12)
    assert ref["m2"] == pytest.approx(0.9990613568591, rel=1e-12)
    # and they are what the record itself says, recomputed here
    rows = [
        [float(x) for x in line.split(",")]
        for line in (REPO_ROOT / "results" / N2R_RECORD / "L2" / "solver" / "postpro" /
                     "domain-E.csv").read_text().splitlines()[1:]
    ]
    for m, key in ((1, "m1"), (2, "m2")):
        _, e_elec, e_mag, e_cap, _ = rows[m - 1]
        assert e_mag / (e_elec + e_cap) == pytest.approx(ref[key], rel=1e-10)
    assert "0.9982" in ref["correction"], "the earlier misquote is named, not silently dropped"
    norm = _norm(DOC.read_text())
    assert "0.0017759330546" in norm and "0.9990613568591" in norm


def test_the_acceptance_threshold_is_stated_and_justified(candidate):
    acc = candidate["energy_diagnostics"]["acceptance_threshold"]
    assert acc["value"] == 1.0e-3
    assert "qmhp-cem.mode-admission/0.1.0" in acc["justification"]
    assert "not a bound derived" in acc["justification"]
    assert "backward error does not bound" in acc["explicitly_not_derived_from_the_backward_error"]
    assert "two independent columns" in acc["reported_separately"]
    assert "not moved after seeing the values" in acc["not_relaxed"]
    # the separation the justification cites is the record's own
    assert "2.12e-17" in acc["explicitly_not_derived_from_the_backward_error"]
    assert "backward error" in _norm(DOC.read_text())


def test_E_ind_and_the_port_participation_are_reference_only(candidate):
    hyp = candidate["energy_diagnostics"]["hypothetical_and_reference_only"]
    assert "no term in PO1's operator" in hyp["E_ind"].replace("NO term", "no term")
    assert "not computed as its acceptance test" in hyp["E_ind"]
    assert "NOT a classification gate" in hyp["derived_port_participation_p_port"]
    assert "1/omega^2" in hyp["derived_port_participation_p_port"]
    assert "No threshold is declared on it" in hyp["the_field_only_quantity_that_remains_meaningful"].replace(
        "No threshold", "No threshold")
    blocks = hyp["the_drivers_inherited_analysis_blocks"]
    assert "REFERENCE diagnostics" in blocks
    assert "neither suppressed" in blocks and "nor read as PO1's physical classification" in blocks


# --- 3. mode identification ----------------------------------------------------------


def test_the_localisation_diagnostic_is_declared_new(candidate):
    mi = candidate["mode_identification"]
    new = mi["this_is_a_NEW_diagnostic_not_the_declared_classifier"]
    assert "NEW diagnostic" in new["what_PO1_defines"]
    assert "UNEXECUTED" in new["what_it_does_not_do"]
    assert "does not replace it" in new["what_it_does_not_do"]
    assert "this control must not apply" in new["clause_i_cannot_be_applied_here"]
    assert "reported, not gated on" in new["clause_i_cannot_be_applied_here"]
    assert "not the same quantity" in new["clause_ii_names_two_different_quantities"]
    norm = _norm(DOC.read_text())
    assert "new diagnostic" in norm and "remains **unexecuted**" in norm


def test_the_rule_and_its_ad_hoc_margin_are_declared_in_advance(candidate):
    rule = candidate["mode_identification"]["the_rule"]
    assert rule["readout_like"] == "s_2 + s_3 >= 0.9"
    assert rule["island_like"] == "s_1 >= 0.9"
    assert "hidden" in rule["indeterminate"]
    margin = rule["the_0.9_margin_is_ad_hoc_and_declared_in_advance"]
    assert "BEFORE any PO1 number exists" in margin and "not derived" in margin
    assert "not moved after seeing the values" in margin
    assert "none of them gates it" in rule["no_second_gate"]
    assert candidate["mode_identification"]["declared_before_the_run"] is True


def test_three_points_are_not_claimed_to_establish_the_fundamental(candidate):
    nots = candidate["mode_identification"]["what_the_rule_does_NOT_establish"]
    assert "cannot establish" in nots["not_the_fundamental"]
    assert "candidate readout-like mode" in nots["not_the_fundamental"]
    assert "NOT part of the pre-declared rule" in nots["evidence_that_could_support_it"]
    assert "never used to choose a mode" in nots["s2_over_s3"]
    outcomes = " ".join(candidate["mode_identification"]["inconclusive_outcomes_declared_in_advance"])
    assert "INCONCLUSIVE FOR MODE IDENTITY" in outcomes
    assert "could not be found" in outcomes and "never accepted silently" in outcomes
    assert "not classified" in outcomes


def test_the_N2R_probe_comparison_is_labelled_unavailable(candidate):
    cmp = candidate["mode_identification"]["the_N2R_comparison_at_the_same_locations"]
    assert cmp["status"] == "UNAVAILABLE"
    assert "no probe-E.csv" in cmp["why"]
    assert "Float32" in cmp["the_only_conceivable_source"]
    assert "not approximated" in cmp["consequence"]
    assert "not replaced by a frequency argument" in cmp["consequence"]
    assert "not approved" in cmp["what_would_produce_one"]
    # never a frequency fallback, anywhere in the record
    norm = _norm(DOC.read_text())
    assert "is not an outcome this record may contain" in norm
    assert "frequency is never a selector" in candidate["mode_identification"]["principle"]
    # N2R really has no probe output
    assert not (REPO_ROOT / "results" / N2R_RECORD / "L2" / "solver" / "postpro" / "probe-E.csv").exists()
    assert "Postprocessing" not in json.loads(N2R_SOLVED.read_text())["Domains"]


# --- 4. the option: narrow, validated, and not armed ---------------------------------


def test_port_active_false_is_the_only_thing_the_option_changes():
    from solvers.palace.coupled_config import build_coupled_config

    common = dict(order=1, substrate_permittivity=11.45, port_inductance_H=1e-7,
                  port_direction="+Y", save_modes=6, port_field_probes=True)
    on = build_coupled_config("m.msh", **common)
    off = build_coupled_config("m.msh", **common, port_active=False)
    a, b = _leaves(on), _leaves(off)
    assert b.keys() - a.keys() == {"Boundaries.LumpedPort[0].Active"}
    assert not (a.keys() - b.keys())
    assert not {k for k in a.keys() & b.keys() if a[k] != b[k]}
    assert off["Boundaries"]["LumpedPort"][0]["Active"] is False
    # the default leaves every existing config byte-identical: no Active key at all
    assert "Active" not in on["Boundaries"]["LumpedPort"][0]


def test_the_driver_generated_config_matches_the_prepared_candidate():
    """The physics config the driver would write IS the prepared candidate, byte for byte."""
    from solvers.palace.coupled_config import (
        COUPLED_SOLVER_RULES,
        PO1_PROBES_MM,
        build_coupled_config,
        superinductor_henry,
    )

    decl = json.loads((REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text())
    substrate = next(m for m in decl["materials"] if m["id"] == "substrate")
    E_L = next(p for p in decl["parameter_register"] if p["id"] == "E_L_F1")["value"]
    port = next(p for p in decl["ports"] if p["id"] == "P_F1")
    direction = port["direction"] if isinstance(port["direction"], str) else port["direction"][0]

    config = build_coupled_config(
        "coupled_chip_cell_L2.msh",
        order=1,
        substrate_permittivity=float(substrate["permittivity"]),
        port_inductance_H=superinductor_henry(float(E_L)),
        port_direction=direction,
        save_modes=COUPLED_SOLVER_RULES["eigenmodes_requested"],
        port_field_probes=True,
        port_active=False,
        probes_mm=PO1_PROBES_MM,
    )
    # exactly what execute_level then does, in its order
    solved = json.loads(N2R_SOLVED.read_text())
    config.setdefault("Model", {}).setdefault("Refinement", {})["Boxes"] = solved["Model"]["Refinement"]["Boxes"]
    config.setdefault("Solver", {}).setdefault("Linear", {}).update({"MGMaxLevels": 1})

    text = json.dumps(config, indent=2) + "\n"
    assert text == (REC / "config.candidate.json").read_text()
    assert hashlib.sha256(text.encode()).hexdigest() == CANDIDATE_SHA256


def test_the_approval_accepts_only_the_pinned_identifier(ladder, po1_approval, tmp_path):
    assert ladder.approved_port_control(_write(tmp_path, po1_approval)) == "PO1-port-removed"
    label, boxes, sha, overrides = ladder.approved_palace_refinement(_write(tmp_path, po1_approval))
    assert label == "PO1" and overrides == {"MGMaxLevels": 1}
    assert boxes == json.loads(N2R_SOLVED.read_text())["Model"]["Refinement"]["Boxes"]
    assert sha == "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda a: a.__setitem__("port_control", "PO1"), "must be the exact string"),
        (lambda a: a.__setitem__("port_control", "po1-port-removed"), "must be the exact string"),
        (lambda a: a.__setitem__("port_control", True), "must be the exact string"),
        (lambda a: a.__setitem__("port_control", {"index": 1, "Active": False}), "must be the exact string"),
        (lambda a: a.pop("palace_refinement"), "requires the palace_refinement block"),
        (lambda a: a["palace_refinement"].__setitem__("id", "N2R"), "palace_refinement.id == 'PO1'"),
        (lambda a: a.__setitem__("baseline_record", "COUPLED-LADDER-O1-L2-20260916T080802Z"),
         "defined against the fixed baseline"),
        (lambda a: a.__setitem__("port_refinement", {"id": "R1", "h_port_mm": 0.003, "pad_mm": 0.02,
                                                     "transition_mm": 0.02}), "cannot be combined"),
    ],
)
def test_every_other_port_control_value_is_refused(ladder, po1_approval, tmp_path, mutate, fragment):
    bad = copy.deepcopy(po1_approval)
    mutate(bad)
    with pytest.raises(ladder.LadderError, match=fragment.replace("(", r"\(").replace(")", r"\)")):
        ladder.approved_port_control(_write(tmp_path, bad))


def test_the_identical_baseline_exception_fires_only_for_the_control(ladder, po1_approval, tmp_path):
    # with the control: an IDENTICAL refined baseline is accepted
    assert ladder.approved_palace_refinement(_write(tmp_path, po1_approval))[0] == "PO1"
    # without it: the unchanged rule refuses the same baseline
    no_control = copy.deepcopy(po1_approval)
    no_control.pop("port_control")
    with pytest.raises(ladder.LadderError, match="is itself a refined run"):
        ladder.approved_palace_refinement(_write(tmp_path, no_control, "b.json"))
    # and the exception is strictly equality, not "not shallower": a DEEPER box
    # is a refinement step and must not ride in on the control
    deeper = copy.deepcopy(po1_approval)
    deeper["palace_refinement"]["boxes"] = [dict(b, Levels=3) for b in deeper["palace_refinement"]["boxes"]]
    assert not ladder.is_identical_refinement(
        {"palace_refinement": {"boxes": deeper["palace_refinement"]["boxes"]}},
        {"palace_refinement": {"boxes": po1_approval["palace_refinement"]["boxes"]}},
    )
    # ... it is a sequence step instead, which the unchanged rule already allows
    assert ladder.is_prior_point_of_same_sequence(
        {"palace_refinement": {"boxes": deeper["palace_refinement"]["boxes"]}},
        {"palace_refinement": {"boxes": po1_approval["palace_refinement"]["boxes"]}},
    )


def test_the_record_declares_the_inactive_port_postprocessing_semantics(ladder, candidate):
    """Deactivation keeps every F-site functional; the record says they are non-loading."""
    entry = ladder.execute_level.__doc__  # presence only; the block itself is built below
    assert entry is None or isinstance(entry, str)
    src = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    block = src.split('"port_control": None if port_control is None else {', 1)[1][:4000]
    assert "f_site_diagnostics_are_non_loading" in block
    assert "no active check" in block
    assert "inherited_analysis_is_reference_only" in block
    assert "also_changed_automatically" in block and "aux_bdr_marker" in block
    survive = candidate["the_operator_change"]["diagnostics_that_SURVIVE_the_change"]
    for key in ("port-V.csv_and_port-I.csv", "port-EPR.csv", "E_ind_in_domain-E.csv"):
        assert "no active check" in survive[key]
    assert "never in value" in survive["what_that_means"]


def test_the_comparison_prose_for_the_control_is_not_the_refinement_prose(ladder):
    entry = {
        "status": "COMPLETED",
        "palace_refinement": {"boxes": [], "solver_linear_overrides": {"MGMaxLevels": 1}},
        "port_control": {"id": "PO1-port-removed"},
    }
    out = ladder.compare_against_baseline(entry, N2R_RECORD, root=REPO_ROOT / "results")
    assert "NOT A REFINEMENT STEP" in out["why_this_comparison"]
    assert "K - K_port" in out["why_this_comparison"]
    assert "aux_bdr_marker" in out["why_this_comparison"]
    assert "gates nothing" in out["why_this_comparison"]
    assert "port-removed control" in out["mechanism"]
    # the refinement prose is NOT used for it
    assert "attributable to added degrees of freedom" not in out["why_this_comparison"]


def test_a_failure_is_evidence_and_the_control_block_survives_it(ladder, tmp_path, monkeypatch):
    """Evidence durability, without a solve: the guarded window records, never raises.

    ``dry_run`` is replaced by one that raises, so nothing is meshed and nothing
    is launched. What is checked is that the port-control block is written into
    the record BEFORE anything can fail, and that the failure comes back as a
    recorded status rather than an exception that would lose the entry.
    """
    def boom(*a, **k):
        raise RuntimeError("no mesh is built in this test")

    monkeypatch.setattr(ladder, "dry_run", boom)
    declaration = json.loads(
        (REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text()
    )
    entry = ladder.execute_level(
        2, declaration, tmp_path, runtime="none", image="none", np_processes=1,
        prepare_only=True, port_control="PO1-port-removed",
        palace_refinement=json.loads(N2R_SOLVED.read_text())["Model"]["Refinement"]["Boxes"],
        palace_refinement_label="PO1", solver_linear_overrides={"MGMaxLevels": 1},
    )
    assert entry["status"] == "ERROR"
    assert "no mesh is built in this test" in entry["failure"]
    control = entry["port_control"]
    assert control["id"] == "PO1-port-removed"
    assert control["changes_the_operator"] is True and control["probes_change_the_operator"] is False
    assert control["probes_mm"] == [list(c) for c in
                                    __import__("solvers.palace.coupled_config", fromlist=["x"]).PO1_PROBES_MM]
    assert "no active check" in control["f_site_diagnostics_are_non_loading"]
    assert "reference diagnostics" in control["inherited_analysis_is_reference_only"]
    assert "aux_bdr_marker" in control["also_changed_automatically"]
    assert not list(tmp_path.rglob("palace_log.txt")), "nothing was run"
    # the driver always writes the merged Palace stream, whatever the exit code,
    # and only three statuses survive the guard unchanged
    src = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    run_body = src.split("def _run_palace(", 1)[1].split("\ndef ", 1)[0]
    assert '(solver_dir / "palace_log.txt").write_text' in run_body
    assert 'stderr=subprocess.STDOUT' in run_body
    guard = src.split("except Exception as exc:  # noqa: BLE001 - a failure is evidence", 1)[1][:400]
    assert '{"TIMEOUT", "RUN_FAILED", "REFUSED-DOF-BUDGET"}' in guard


def test_the_rendered_report_says_it_is_not_a_refinement_check(ladder):
    src = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    banner = src.split('if control:', 1)[1][:1800]
    assert "NOT A REFINEMENT CHECK" in banner
    assert "K \u2212 K_port" in banner or "K − K_port" in banner
    assert "reference diagnostics" in banner
    assert "must not enter" in banner
    # and it is reached only for a control: a plain rung has no port_control block
    head = src.split("def render_report", 1)[1].split("if control:", 1)[0]
    assert head.rstrip().endswith('control = entry.get("port_control")')


# --- nothing is armed ----------------------------------------------------------------


def test_the_approval_trigger_is_untouched_and_carries_no_control(ladder):
    approval = json.loads(APPROVAL.read_text())
    assert "port_control" not in approval
    assert approval["palace_refinement"]["id"] == "N1R"
    assert ladder.approved_port_control(APPROVAL) is None
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True,
                             cwd=REPO_ROOT).stdout.split()
    assert ".github/ladder-approval.json" not in changed
    workflow = (REPO_ROOT / ".github" / "workflows" / "palace-order1-ladder.yml").read_text()
    assert ".github/ladder-approval.json" in workflow
    assert ".github/workflows/palace-order1-ladder.yml" not in changed


def test_nothing_in_this_preparation_can_launch_palace():
    """Nothing PO1 adds can start a solve: no container command, no driver invocation."""
    forbidden = ("docker", "podman", "_run_palace", "execute_level", "subprocess.Popen", "main(")
    text = (REC / "prepare.py").read_text()
    for token in forbidden:
        assert token not in text.replace("def main()", "").replace("sys.exit(main())", ""), token
    # this test file itself runs only the offline candidate builder and git
    import ast

    tree = ast.parse(Path(__file__).read_text())
    runs = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "subprocess.run"]
    argv = [ast.unparse(n.args[0]) for n in runs]
    assert len(argv) == 2, argv
    assert any("prepare.py" in a for a in argv) and any("'git'" in a for a in argv)
    # the candidate is never written under results/, and no PO1 record exists
    assert "refusing to write a candidate under results/" in text
    assert not list((REPO_ROOT / "results").glob("*PO1*"))


def test_the_single_approval_is_stated(candidate):
    appr = candidate["the_single_approval_needed"]
    assert "ONE execution of PO1, once." == appr["what"]
    assert '"port_control": "PO1-port-removed"' in appr["how_it_is_given"]
    assert "one solve" in appr["what_it_authorises"] and "no retry" in appr["what_it_authorises"]
    for forbidden in ("no extraction", "no second attempt", "no merge of PR 7"):
        assert forbidden in appr["what_it_does_not_authorise"]
    norm = _norm(DOC.read_text())
    assert "The single approval needed" in norm
    assert "no merge of PR #7" in norm
