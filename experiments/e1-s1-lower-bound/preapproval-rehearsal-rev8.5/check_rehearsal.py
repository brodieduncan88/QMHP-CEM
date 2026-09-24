"""The predeclared acceptance checks of part 1 of the revision-8.5 pre-approval rehearsal
(PREDECLARATION.md), applied to the driver's rehearsal output. Usage, from the repository root:
    .venv/bin/python experiments/e1-s1-lower-bound/preapproval-rehearsal-rev8.5/check_rehearsal.py <rehearsal.json>
Prints one JSON object: every check with its result, and "all_pass". Reads the S1 geometry facts,
the synthetic control results, the pass flags and the digests; it prints no capacitance value."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "experiments" / "e1-s1-lower-bound"))
import driver as dr  # noqa: E402
import e1_geometry as eg  # noqa: E402

r = json.loads(Path(sys.argv[1]).read_text())
draft = json.loads((REPO / "experiments" / "e1-s1-lower-bound" / "E1-APPROVAL.draft.json").read_text())
norm = lambda o: json.loads(json.dumps(dr._clean(o)))  # noqa: E731 - the output's own serialisation
facts, c, g = r["geometry"]["facts"], r["controls"], r["geometry"]
checks = {
    "mode_is_rehearsal": r["mode"] == "rehearsal",
    "rehearsal_pass": r["rehearsal_pass"] is True,
    "passes_all_true": r["passes"] == {"preflight_clean": True, "controls_pass": True, "geometry_pass": True,
                                       "separation_pass": True},
    "preflight_problems_empty": r["preflight_problems_on_this_host"] == [],
    "separation_problems_empty": r["separation_problems"] == [] and r["separation_pass"] is True,
    "control_failures_empty": c["failures"] == [] and r["controls_pass"] is True,
    "geometry_failures_empty": g["failures"] == [] and r["geometry_pass"] is True,
    "code_sha256_equals_draft": r["code_sha256"] == {**draft["code_sha256"], **draft["preapproval_code_sha256"]},
    "contract_sha256_equals_pin": r["contract_sha256"] == dr.CONTRACT_SHA256 == draft["contract_sha256"],
    "inputs_equal_pins": (r["inputs"]["contract"], r["inputs"]["mesh"], r["inputs"]["baseline_manifest"],
                          r["inputs"]["baseline_summary"], r["inputs"]["code"]) ==
                         (dr.CONTRACT_SHA256, draft["mesh_sha256"], draft["baseline_manifest_sha256"],
                          draft["baseline_summary_sha256"], draft["code_sha256"]),
    "baseline_bit_exact_flags": r["baseline"]["C_hi_bit_exact"] is True and r["baseline"]["C_br_bit_exact"] is True,
    "geometry_facts_equal_section_3_3": {k: facts.get(k) == v for k, v in norm(eg.EXPECTED).items()},
    "K2b": c["K2b"]["pairs"] == 10096 and c["K2b"]["pair_list_matches_frozen"] is True
           and c["K2b"]["violations_of_B"] == 0 and c["K2b"]["violations_of_c0_bound"] == 0,
    "N4_broken_routine_fails_K2": c["N4"]["broken_routine_fails_K2"] is True,
    "K2_max_rel_ld_vs_quad_le_1e-9": c["K2"]["max_rel_ld_vs_quad"] <= 1e-9,
    "geometry_controls_pass": {n: g["controls"][n]["pass"] is True for n in ("N1", "N2", "N3b", "N3c")},
    "K3_ratio_to_D_in_0.97_1": 0.97 <= c["K3"]["ratio_to_D"] <= 1,
    "N3_ratio_gt_10": c["N3"]["ratio"] > 10,
    "s1_matrices_assembled_statement": r["s1_matrices_assembled"] ==
        "none: the geometry phase assembles no matrix (tested with a spy)",
}
flat = [v if isinstance(v, bool) else all(v.values()) for v in checks.values()]
print(json.dumps({"checks": checks, "all_pass": all(flat), "resources": r["resources"]}, indent=1))
sys.exit(0 if all(flat) else 1)
