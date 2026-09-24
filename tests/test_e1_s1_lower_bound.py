# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""E1 - the static-capacitance lower-bound certificate for the S1 island: tests of the frozen
implementation (experiments/e1-s1-lower-bound) against the frozen contract
E1-CONTRACT.rev8.3.md (revision 8.2 plus the stand-in separation of D14; its sha256 is pinned
below and in the driver).

Synthetic data only, apart from the S1 GEOMETRY phase, which reads the pinned mesh and
assembles no matrix. No test computes an S1 capacitance, assembles an S1 matrix, runs
Palace or any solver, or spends the attempt: every attempt-path test runs in tmp_path with
the approval, ledger and record paths redirected there and small synthetic panel sets.

Groups: frozen inputs; entries, the c0 derivation and the enclosure (known answers and
negative controls); the trial vector and its fallbacks; check (g), K4 and the no-underflow
requirement; outputs and the output guard; probes, environment and invocation; the
approval; the one-attempt ledger and every failure path; the budget and signals in real
processes; geometry; the rehearsal (slow); the committed evidence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "experiments" / "e1-s1-lower-bound"
sys.path.insert(0, str(HERE))

import driver as dr  # noqa: E402
import e1_controls as ec  # noqa: E402
import e1_geometry as eg  # noqa: E402
import e1_numerics as nm  # noqa: E402
import e1_standin as es  # noqa: E402

manifest = dr.manifest
REAL_REQUIRE_APPROVAL = dr.require_approval
CONTRACT_TEXT = (HERE / "E1-CONTRACT.rev8.3.md").read_text()
CONTRACT_8_2 = HERE / "E1-CONTRACT.rev8.2.md"
CONTRACT_8_3_SHA256 = "2b9b9357bb438987723914727a851161201a7a9f477aa66ae674fb0ed9d6b296"
#: the implementation reviewed at 90bf9eb (frozen against revision 8.2); its committed pre-approval
#: evidence is superseded (the Confirmation's stand-in island was S1's island, finding D-1) and is
#: kept unchanged pending regeneration after the corrected separation has passed review
FROZEN_90BF9EB = {"driver.py": "d2bcff929f6c09f8d897a82ceb0ecd470d63a055093ab17551c2fdef1d8cd43d",
                  "e1_numerics.py": "513c0ddfbdf3927bee0e4d025b9e3537a55488a63eeed8402f35c01861ec26be",
                  "e1_geometry.py": "fb88d72d3a3e28ed27bb040eb083b8b7344a85f82c8a9a45c8d361e03489c772",
                  "e1_controls.py": "bb3ae0c8dff4bd8e7e715281c18d8639bcaf7ef2013f4b640def8a907f2625fa",
                  "e1_standin.py": "af183c6342b986c0cd2a3743d35974555c15319bc6be8185a2cd26e3176ddda2"}
EVIDENCE_90BF9EB = {"rehearsal.json": "3b6e31b198ae81b0d8a6a6ab24116457fb04c9d195f3fd373451f9856d45c2b8",
                    "proxyA-gE.json": "83f442794e5020732a68942e790f42b9715d078ba9c1feb12cb0f94a0139d222",
                    "confirmation-nominal.json": "522be6f04455aed92b1532558fd6110a340440dd4e33d2845c3ace2b9c32b2aa",
                    "confirmation-forced.json": "7a18cc98540e9fada6a5ee72d7e9c2ab9e1ad32c5a118532e212a5433a26564a"}
THREADS = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
LD = np.longdouble
U = Fraction(1, 2 ** 64)
HEADER = ("# Copyright (c) 2026 Brodie Duncan. All rights reserved.",
          "# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.")
EXECUTION_HOST_REPOSITORY = "/home/user/QMHP-CEM"
E1_SOURCES = ["driver.py", "e1_numerics.py", "e1_geometry.py", "e1_controls.py", "e1_standin.py"]


def _strict_json(path: Path):
    def bad(token):
        raise ValueError(f"non-standard JSON token {token} in {path.name}")
    return json.loads(path.read_text(), parse_constant=bad)


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _python(code: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, **THREADS}, cwd=str(REPO))


def _dec(fr: Fraction) -> Decimal:
    return Decimal(fr.numerator) / Decimal(fr.denominator)


def _exact_energy(R, sigma, prec: int = 60) -> Decimal:
    """sigma^T S sigma with every entry from the 60-digit closed form (the K2b reference)."""
    n = len(R)
    with localcontext() as ctx:
        ctx.prec = prec
        tot = Decimal(0)
        for i in range(n):
            for j in range(i, n):
                s, _ = ec.reference_dec(tuple(R[i]), tuple(R[j]), prec)
                t = Decimal(float(sigma[i])) * s * Decimal(float(sigma[j]))
                tot += t if i == j else 2 * t
        return tot


# --- small synthetic panel sets (never S1) ---------------------------------------------------------

def small_sets() -> dict:
    """An 8 x 8 graded island at (-0.6, 0) (the section 3.1 formula with n = 8, q = 2), 20 um
    ground squares outside a hole of half-width 0.1 mm, and an 'R1' made of the last 12
    ground squares by ascending x then y. Order: island, ground not in R1, R1."""
    isl = eg.island_panels(8, 2.0)
    half = eg.island_panels(8, 2.0, step=2)
    g = []
    side = 0.02
    for i in range(-6, 6):
        for j in range(-6, 6):
            x0, y0 = -0.6 + i * side, j * side
            if max(abs(x0 + side / 2 + 0.6), abs(y0 + side / 2)) < 0.1:
                continue
            g.append((x0 + 1e-9, x0 + side - 1e-9, y0 + 1e-9, y0 + side - 1e-9))
    order = sorted(range(len(g)), key=lambda k: ((g[k][0] + g[k][1]) / 2, (g[k][2] + g[k][3]) / 2))
    r1 = set(order[-12:])
    excl = [g[k] for k in range(len(g)) if k not in r1]
    on_r1 = [g[k] for k in range(len(g)) if k in r1]
    R = np.array(list(map(tuple, isl)) + excl + on_r1, dtype=np.float64)
    return {"R_E1_2": R, "n_island": len(isl), "n_excl": len(isl) + len(excl), "R_E1_1_half": half}


@pytest.fixture(scope="module")
def sets():
    return small_sets()


# === frozen inputs ================================================================================

def test_the_contract_in_the_directory_is_the_frozen_revision_8_3_and_8_2_is_kept():
    assert dr.CONTRACT_SHA256 == CONTRACT_8_3_SHA256 and dr.CONTRACT.name == "E1-CONTRACT.rev8.3.md"
    assert _sha(dr.CONTRACT) == dr.CONTRACT_SHA256
    assert CONTRACT_TEXT.startswith("# E1 ") and "revision 8.3" in CONTRACT_TEXT.splitlines()[0]
    assert _sha(CONTRACT_8_2) == "24ffff7d92c93757a13f9f6ba4505598be83b1628f4c5d6912c6abbbbdaf504c"
    for name in ("e1_numerics.py", "e1_geometry.py", "e1_controls.py", "e1_standin.py", "driver.py"):
        assert "rev8.3" in (HERE / name).read_text(), name


def test_revision_8_3_changes_only_the_stand_in_separation_d14_and_bookkeeping():
    """The diff from the frozen revision 8.2 is three replaced bookkeeping lines (title, status,
    superseded range) and added lines that are all about the stand-in separation, D14, the
    revision-8.2 row of section 9 or section 13. No line of physics, configuration, thresholds,
    controls, Q2/C_br or scope is removed or changed."""
    import difflib
    old, new = CONTRACT_8_2.read_text().splitlines(), CONTRACT_TEXT.splitlines()
    removed, added = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += old[i1:i2]
        if tag in ("replace", "insert"):
            added += new[j1:j2]
    assert removed == [old[0], old[2], "- **Superseded drafts.** Revisions 1–8.1."], removed
    markers = ("revision 8.3", "Revision 8.2 is frozen", "D14", "Separation (revision 8.3", "stand-in", "Stand-in",
               "x_k = −0.6 + s_k(0.075)", "Everything else (the ground sheet", "frozen revision 8.2 (implemented at",
               "## 13.", "| finding (frozen-code review", "|---|---|", "Nothing else changes from revision 8.2", "",
               "- **Superseded drafts.** Revisions 1–8.2.", "**Status: revision 8.3")
    stray = [ln for ln in added if not any(m in ln for m in markers)]
    assert stray == [], stray
    assert len(added) == 19, len(added)


def test_every_new_source_file_carries_the_proprietary_header():
    for path in [HERE / n for n in E1_SOURCES] + [Path(__file__)]:
        lines = path.read_text().splitlines()
        start = 1 if lines[0].startswith("#!") else 0
        assert tuple(lines[start:start + 2]) == HEADER, path.name


def test_the_pinned_digests_are_the_ones_the_contract_lists_in_section_9():
    sec9 = CONTRACT_TEXT[CONTRACT_TEXT.index("## 9. Inputs"):CONTRACT_TEXT.index("## 10.")]
    for key in ("mesh_sha256", "baseline_manifest_sha256", "baseline_summary_sha256", "anchor_fem_sha256",
                "manifest_py_sha256"):
        assert f"`{dr.CONFIG[key]}`" in sec9, key
    for path in ("mesh", "baseline_manifest", "baseline_summary"):
        assert dr.CONFIG[path] in sec9
    assert "python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39" in sec9
    assert (dr.ENVIRONMENT["python"], dr.ENVIRONMENT["numpy"], dr.ENVIRONMENT["scipy"], dr.ENVIRONMENT["glibc"]) == \
        ("3.11.15", "2.4.6", "1.17.1", "2.39")
    assert f"float64 {dr.CONFIG['C_hi_fF']!r} fF" in CONTRACT_TEXT and f"{dr.CONFIG['C_br_fF']!r} fF" in CONTRACT_TEXT
    assert dr.INVOCATION in CONTRACT_TEXT


def test_the_inputs_verify_and_a_changed_digest_or_a_broken_baseline_is_a_problem(monkeypatch):
    dig = dr.input_digests()
    assert dr.input_problems(dig) == []
    monkeypatch.setitem(dr.CONFIG, "mesh_sha256", "0" * 64)
    assert any("mesh" in p for p in dr.input_problems(dig))
    monkeypatch.setitem(dr.CONFIG, "mesh_sha256", dig["mesh"])
    bad = {**dig, "code": {**dig["code"], "anchor_fem.py": "0" * 64}}
    assert any("anchor_fem.py" in p for p in dr.input_problems(bad))
    monkeypatch.setattr(dr.manifest, "verify", lambda root, filename="manifest.sha256": ["summary.json differs"])
    assert any(p.startswith("baseline record") for p in dr.input_problems(dig))


def test_C_hi_and_C_br_are_recomputed_bit_exactly_from_the_verified_baseline():
    b = dr.baseline_values()
    assert b["C_hi_bit_exact"] and b["C_br_bit_exact"]
    assert b["C_hi_fF"].hex() == (67.9755386760262).hex() and b["C_br_fF"].hex() == (56.67470653023562).hex()


def test_the_frozen_constants_are_recomputed_and_a_wrong_epsilon0_is_refused():
    assert nm.frozen_constants_problems(dr.af.EPSILON0) == []
    assert Fraction(nm.EPS_AVG_LO_PQ) == (1 + Fraction(11.45)) / 2
    assert Fraction(249, 40) - Fraction(nm.EPS_AVG_LO_PQ) > 0
    kl = Fraction(nm.KAPPA_LO_PQ)
    assert abs(float(kl) - 692.6246598933774) < 1e-12
    assert len(nm.frozen_constants_problems(dr.af.EPSILON0 * (1 - 2 ** -52))) == 2
    pi50 = "3.14159265358979323846264338327950288419716939937510"
    assert nm.PI_LO == Fraction(Decimal(pi50[:36])) < Fraction(Decimal(pi50))       # the 35-digit truncation


# === entries, c0 and the enclosure =================================================================

def test_K1_the_unit_square_equals_its_closed_form_and_the_reference_is_that_closed_form():
    with localcontext() as ctx:
        ctx.prec = 60
        closed = Decimal(4) / 3 * (1 - Decimal(2).sqrt()) + 4 * (1 + Decimal(2).sqrt()).ln()
    assert str(closed).startswith("2.9732095982473787025281856676395717980197454792")
    k = ec.k1()
    assert k["pass"] and k["rel_long_double"] <= 1e-17 and k["rel_float64"] <= 1e-13


def test_a_diagonal_block_uses_the_i_le_j_value_for_both_triangles(sets):
    R = sets["R_E1_2"][:40]
    for dt in (LD, np.float64):
        S, B = nm.entry_block(R, 0, 40, 0, 40, dt, want_b=dt is LD)
        assert (S == S.T).all()
        for i, j in ((0, 5), (3, 39), (17, 18)):
            one = nm.entry(tuple(R[i]), tuple(R[j]), dt, want_b=dt is LD)
            val = one[0] if dt is LD else one
            assert S[i, j] == val and S[j, i] == val
        if dt is LD:
            assert (B == B.T).all()
    S64 = nm.assemble64(sets["R_E1_2"])
    assert S64.flags.f_contiguous and (S64 == S64.T).all()


def test_the_K2b_pair_list_is_the_frozen_one_and_its_F_zero_separations_are_log_spaced():
    pairs = ec.k2b_pairs()
    assert len(pairs) == 10096 and ec.k2b_pairs_sha256(pairs) == ec.K2B_PAIRS_SHA256
    D = 0.96 * math.sqrt(2)
    sep = [math.hypot((b[0] + b[1]) / 2 + 0.6, (b[2] + b[3]) / 2) for _, b in pairs[10000::4]]
    assert len(sep) == 24 and abs(sep[0] - 0.05) < 1e-15 and abs(sep[-1] - D) < 1e-15
    ratios = [sep[k + 1] / sep[k] for k in range(23)]
    assert max(ratios) - min(ratios) < 1e-12
    assert len(ec.k2b_side_classes()) == 22


def test_the_F_zero_lines_are_where_the_contract_says():
    t = ec.F_ZERO_T
    X = LD(1)
    f, _ = nm._F(np.array([X]), np.array([LD(t) * X]), LD)
    assert abs(float(f[0])) < 1e-15
    with localcontext() as ctx:
        ctx.prec = 40
        fz, _ = ec._F_dec(Decimal(1), Decimal(t))
        assert abs(fz) < Decimal("1e-15")


ANGLES = np.linspace(0, np.pi / 2, 200001)


def test_the_c0_derivation_constants_bound_their_angular_maxima():
    a, b = np.cos(ANGLES), np.sin(ANGLES)
    assert (0.5 * a * a * b).max() <= float(nm.K_T) and (0.5 * a * b * b).max() <= float(nm.K_T)
    assert (0.5 * a * b * (a + b)).max() <= float(nm.K_12)
    assert max(1 / 6, float(nm.K_12) - 1 / 6) <= float(nm.K_F)
    # F / r^3 itself, and (|X F_X| + |Y F_Y|) / r^3 from the analytic derivative
    with np.errstate(divide="ignore", invalid="ignore"):
        L1 = np.where(a > 0, np.arcsinh(b / a), 0.0)
        L2 = np.where(b > 0, np.arcsinh(a / b), 0.0)
    F = 0.5 * a * a * b * L1 + 0.5 * a * b * b * L2 - 1 / 6
    assert F.min() >= -1 / 6 - 1e-15 and F.max() <= float(nm.K_F)
    XFX = a * a * b * L1 + 0.5 * a * b * b * L2 - 0.5 * a * a
    YFY = b * b * a * L2 + 0.5 * b * a * a * L1 - 0.5 * b * b
    assert (np.abs(XFX) + np.abs(YFY)).max() <= float(nm.K_S)
    # the constants are tight upper bounds, not arbitrary
    assert float(nm.K_T) - 1 / (3 * math.sqrt(3)) < 1e-3 and float(nm.K_12) - 1 / (2 * math.sqrt(2)) < 1e-3
    assert float(nm.K_S) - 2 / math.sqrt(3) < 1e-3


def test_the_analytic_derivative_used_by_the_derivation_is_the_derivative_of_F():
    def F(X, Y):
        with localcontext() as ctx:
            ctx.prec = 50
            return ec._F_dec(Decimal(X), Decimal(Y))[0]
    for X, Y in ((0.3, 0.7), (1.0, 0.01), (0.05, 2.0)):
        h = Decimal("1e-20")
        with localcontext() as ctx:
            ctx.prec = 50
            dX = (F(Decimal(X) + h, Y) - F(Decimal(X) - h, Y)) / (2 * h)
        r = math.hypot(X, Y)
        ana = X * Y * math.asinh(Y / X) + 0.5 * Y * Y * math.asinh(X / Y) - 0.5 * r * X
        assert abs(float(dX) - ana) < 1e-12 * max(1.0, abs(ana))


def test_the_derived_c0_is_within_64_times_one_minus_gamma_qB():
    d = nm.derive_c0()
    assert d["q_B"] == 31 and d["within_limit"] is True
    assert d["c0"] <= 64 * (1 - nm.gamma(31)) and 11 < d["c0_float"] < 12
    assert (1 - nm.gamma(24)) / (1 + nm.gamma(7)) >= 1 - nm.gamma(31)
    assert d["c0"] == nm.derive_c0()["c0"]                      # deterministic, exact


def _k2b_sample(k: int = 400):
    pairs = ec.k2b_pairs()
    return pairs[:k] + pairs[-96:]


def test_the_entry_bound_holds_on_a_K2b_sample_and_a_too_small_constant_is_caught():
    """The K2b criteria on 496 of its pairs (the full list runs in the rehearsal). Negative
    control: a constant 100 times below the largest implied one is violated."""
    c0 = _dec(nm.derive_c0()["c0"])
    u = Decimal(1) / Decimal(2 ** 64)
    implied = []
    with localcontext() as ctx:
        ctx.prec = 60
        for a, b in _k2b_sample():
            S, B = nm.entry(a, b, LD, want_b=True)
            ref, r3AA = ec.reference_dec(a, b, 60)
            err = abs(_dec(nm.to_fr(S)) - ref)
            assert err <= _dec(nm.to_fr(B)) and err <= c0 * u * r3AA
            implied.append(err / (u * r3AA))
    worst = max(implied)
    assert 1e-3 < worst < 1                                      # the errors are real: c = worst/100 would fail


def test_the_enclosure_bounds_the_exact_energy_and_the_hat_energy_alone_does_not():
    """Known answer in exact arithmetic: E_up >= sigma^T S sigma with S from the 60-digit closed
    form, on a set with extreme cancellation (4.58 nm panels far apart). Negative control:
    for a sigma chosen against the entry error, E^ alone falls below the exact energy."""
    s = ec.smin()
    far = [(-0.6 - s / 2 + dx, -0.6 + s / 2 + dx, -s / 2 + dy, s / 2 + dy)
           for dx, dy in ((0.0, 0.0), (0.61, 0.43), (0.33, -0.47))]
    R = np.array(far + [(-0.61, -0.59, -0.01, 0.01)], dtype=np.float64)
    S, _ = nm.entry_block(R, 0, 4, 0, 4, LD)
    with localcontext() as ctx:
        ctx.prec = 60
        ref01 = ec.reference_dec(tuple(R[0]), tuple(R[1]), 60)[0]
    err01 = _dec(nm.to_fr(S[0, 1])) - ref01
    assert err01 != 0
    sign = -1.0 if err01 > 0 else 1.0
    # sigma against the error: the off-diagonal error dominates the (tiny) diagonal terms
    sig = np.array([1.0, sign * 1.0, 0.0, 0.0]) * 1e-12
    for sigma in (sig, np.array([1.0, 1.0, 1.0, 1.0]) * 1e-9, np.array([3e-13, -2e-13, 5e-13, 1e-6])):
        p = nm.ld_pass(R, [sigma])
        exact = _exact_energy(R, sigma)
        eup = nm.e_up(p["E"][0], p["W"][0], p["G"][0], p["m"])
        assert _dec(eup) >= exact
    p = nm.ld_pass(R, [sig])
    assert _dec(nm.to_fr(p["E"][0])) < _exact_energy(R, sig), "the negative control must bite"


def test_the_rounding_count_is_the_contract_table():
    sec = CONTRACT_TEXT[CONTRACT_TEXT.index("| pass | N | n_b | P(N) | m(N) |"):]
    rows = re.findall(r"\| [^|]+ \| ([\d,]+) \| (\d+) \| ([\d,]+) \| ([\d,]+) \|", sec[:900])
    assert len(rows) == 5
    for N, nb, P, m in rows:
        N, nb, P, m = (int(v.replace(",", "")) for v in (N, nb, P, m))
        assert -(-N // 256) == nb and nb * (nb + 1) // 2 == P and nm.m_count(N) == m
    assert [nm.m_count(n) for n in (9995, 1024, 256, 3080, 732)] == [1331, 521, 512, 602, 517]


def test_E_up_rd_and_gamma_are_exact():
    E, W, G, m = LD(2) / LD(3), LD(1) / LD(7), LD(5) / LD(3), 1331
    g = m * U / (1 - m * U)
    assert nm.gamma(m) == g
    assert nm.e_up(E, W, G, m) == nm.to_fr(E) + (nm.to_fr(W) + g * nm.to_fr(G)) / (1 - g)
    x = Fraction(1, 3)
    lo = nm.rd(x)
    assert Fraction(lo) <= x < Fraction(float(np.nextafter(lo, np.inf)))
    assert nm.rd(Fraction(1, 4)) == 0.25 and nm.ru(Fraction(1, 4)) == 0.25
    hi = nm.ru(x)
    assert Fraction(hi) >= x > Fraction(float(np.nextafter(hi, -np.inf)))
    assert nm.to_fr(LD(1) + LD(2) ** -63) == 1 + Fraction(1, 2 ** 63)


@pytest.mark.parametrize("E, W, G, Q, why", [
    (LD(1), LD(-1e-30), LD(1), Fraction(1), "negative W"),
    (LD(1), LD(0), LD(-1), Fraction(1), "negative G"),
    (LD(np.inf), LD(0), LD(1), Fraction(1), "non-finite E"),
    (LD(np.nan), LD(0), LD(1), Fraction(1), "NaN E"),
    (LD(1), LD(0), LD(1), Fraction(0), "Q = 0"),
    (LD(1), LD(0), LD(1), Fraction(-1), "Q < 0"),
    (LD(-2), LD(0), LD(1), Fraction(1), "non-positive E_up"),
])
def test_the_enclosure_refuses_every_invalid_component(E, W, G, Q, why):
    assert nm.enclosure(Q, E, W, G, 512, Fraction(nm.KAPPA_LO_PQ))["ok"] is False, why


def test_the_enclosure_rounds_down_once_and_the_width_is_nonnegative():
    enc = nm.enclosure(Fraction(3), LD(2), LD(1e-20), LD(3), 512, Fraction(nm.KAPPA_LO_PQ))
    exact = 9 * Fraction(nm.KAPPA_LO_PQ) / nm.e_up(LD(2), LD(1e-20), LD(3), 512)
    assert enc["ok"] and Fraction(enc["C_lo_fF"]) <= exact < Fraction(float(np.nextafter(enc["C_lo_fF"], np.inf)))
    assert enc["w_fF"] >= 0 and Fraction(enc["E_up_pq"]) == nm.e_up(LD(2), LD(1e-20), LD(3), 512)


def test_Q_is_the_exact_island_sum():
    sigma = np.array([1e16, 1.0, -1e16, 7.0])
    assert nm.island_charge(sigma, 3) == 1 and nm.island_charge(sigma, 4) == 8
    assert sum(sigma[:3]) == 0.0                                # float64 summation loses it


def test_the_no_underflow_requirement_and_its_negative_control():
    ok = nm.underflow_check([np.array([1e-10, 2.0, 0.0])], LD(1e-5), LD(1e-30))
    assert ok["ok"] and ok["min_abs_sigma"] == 1e-10
    tiny = LD(2) ** -16000
    bad = nm.underflow_check([np.array([1e-300, 1.0])], tiny, LD(1))
    assert bad["ok"] is False
    edge = nm.underflow_check([np.array([2.0 ** -300])], LD(2) ** -15900, LD(1))
    assert edge["ok"] is False                                  # second product 2^-16564
    assert nm.underflow_check([np.array([1.0])], LD(2) ** -16236, LD(1))["ok"] is True


# === the trial vector and its fallbacks ===========================================================

def test_the_nominal_solve_is_in_place_and_leaves_the_lower_triangle_and_diagonal(sets):
    R = sets["R_E1_2"]
    S = nm.assemble64(R)
    ref = S.copy(order="F")
    sol = nm.solve_sigma(S, sets["n_island"])
    assert sol["path"] == "cholesky" and sol["in_place"] is True
    assert (np.tril(S, -1) == np.tril(ref, -1)).all() and (sol["d"] == np.diag(ref)).all()
    rhs = np.zeros(len(R))
    rhs[:sets["n_island"]] = 1
    assert np.abs(ref @ sol["sigma"] - rhs).max() < 1e-9
    assert sol["Q"] == nm.island_charge(sol["sigma"], sets["n_island"]) > 0
    assert math.isclose(nm.energy64(S, sol["d"], sol["sigma"]), float(sol["sigma"] @ ref @ sol["sigma"]), rel_tol=1e-12)
    X = nm.principal_from_lower(S, sets["n_excl"], sol["d"])
    assert X.flags.f_contiguous and (X == ref[:sets["n_excl"], :sets["n_excl"]]).all()
    nm.restore_upper(S, sol["d"])
    assert (S == ref).all()


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_each_forced_fallback_step_is_the_declared_one_and_solves_its_system(sets, k):
    R, ni = sets["R_E1_2"], sets["n_island"]
    ref = nm.assemble64(R)
    S = ref.copy(order="F")
    sol = nm.solve_sigma(S, ni, force_fail=k)
    want = nm.FALLBACK_STEPS[k] if k < len(nm.FALLBACK_STEPS) else "last_resort"
    assert sol["path"] == want
    assert [a["step"] for a in sol["attempts"]] == list(nm.FALLBACK_STEPS[:k]) + [want]
    assert all(a["failed"] for a in sol["attempts"][:-1]) and sol["attempts"][-1]["failed"] is None
    assert (np.tril(S, -1) == np.tril(ref, -1)).all()
    d = np.diag(ref)
    rhs = np.zeros(len(R))
    rhs[:ni] = 1
    if want == "last_resort":
        assert (sol["sigma"] == np.where(rhs > 0, rhs / d, 0.0)).all() and sol["in_place"] is None
    else:
        tau = {"jacobi_scaled": 0.0, "shift_2^-40": 2.0 ** -40, "shift_2^-30": 2.0 ** -30, "shift_2^-20": 2.0 ** -20}[want]
        tau *= float(np.max(d / d))                              # the scaled diagonal is 1
        M = ref + tau * np.diag(d)                               # D^1/2 (D^-1/2 S D^-1/2 + tau I) D^1/2
        assert np.abs(M @ sol["sigma"] - rhs).max() < 1e-8 and sol["in_place"] is True
    assert sol["Q"] > 0 and np.isfinite(sol["sigma"]).all()


def test_a_genuinely_indefinite_matrix_reaches_the_shift_that_makes_it_definite():
    S = np.array([[1.0, 1.0000001], [1.0000001, 1.0]], order="F")
    sol = nm.solve_sigma(S, 1)
    assert sol["path"] == "shift_2^-20"
    assert [a["step"] for a in sol["attempts"]] == list(nm.FALLBACK_STEPS)


@pytest.mark.parametrize("diag0, msg", [(-1.0, "Q <= 0"), (0.0, "not finite")])
def test_an_invalid_last_resort_sigma_raises(diag0, msg):
    S = np.array([[diag0, 0.5], [0.5, 1.0]], order="F")
    with pytest.raises(nm.LastResortInvalid, match=msg):
        nm.solve_sigma(S, 1)


def test_solve_sigma_refuses_a_copying_layout():
    with pytest.raises(nm.NumericsError, match="F-ordered"):
        nm.solve_sigma(np.eye(3), 1)


def test_the_attempt_path_can_never_force_a_failure():
    tree = ast.parse((HERE / "driver.py").read_text())
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("execute", "main", "run_phases", "capacitance_phase", "rehearsal"):
        for call in (n for n in ast.walk(funcs[name]) if isinstance(n, ast.Call)):
            for kw in call.keywords:
                if kw.arg == "force_fail":
                    assert name in ("run_phases", "capacitance_phase") and isinstance(kw.value, ast.Name) \
                        and kw.value.id == "force_fail", (name, ast.dump(kw))
    calls = [n for n in ast.walk(funcs["execute"]) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "run_phases"]
    assert len(calls) == 1 and not any(k.arg == "force_fail" for k in calls[0].keywords)
    small = [n for n in ast.walk(funcs["capacitance_phase"]) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "solve_sigma"]
    assert sum(1 for c in small if any(k.arg == "force_fail" for k in c.keywords)) == 2   # E1.2, E1.2-excl-R1 only


# === check (g), K4 and the analysis =================================================================

def test_check_g_passes_within_1e_minus_7_and_fails_beyond_it():
    kap = Fraction(nm.KAPPA_LO_PQ)
    E_hat = LD(2)
    C_lo = float(4 * kap / nm.to_fr(E_hat))
    good = nm.check_g(Fraction(2), 2.0 * (1 + 5e-8), E_hat, C_lo, kap)
    bad = nm.check_g(Fraction(2), 2.0 * (1 + 2e-7), E_hat, C_lo, kap)
    assert good["ok"] and not bad["ok"] and bad["rel"] > 1e-7
    assert not nm.check_g(Fraction(2), math.inf, E_hat, C_lo, kap)["ok"]
    assert not nm.check_g(Fraction(2), -1.0, E_hat, C_lo, kap)["ok"]


def _k4_res(**over):
    base = {"E1.2": (Fraction(60), Fraction(60)), "E1.2-excl-R1": (Fraction(55), Fraction(55)),
            "E1.1": (Fraction(30), Fraction(30)), "E1.1-half": (Fraction(29), Fraction(29))}
    base.update(over)
    return {s: {"_C_lo_exact": v[0], "_C_tilde_exact": v[1]} for s, v in base.items()}


PATHS = {s: "cholesky" for s in dr.SETS}


@pytest.mark.parametrize("over, paths, statuses", [
    ({}, {}, ["PASS", "PASS", "PASS"]),
    ({"E1.1-half": (Fraction(31), Fraction(31))}, {}, ["FAIL", "PASS", "PASS"]),
    ({"E1.1-half": (Fraction(31), Fraction(31)), "E1.1": (Fraction(30), Fraction(30) + 2)}, {}, ["PASS", "PASS", "PASS"]),
    ({"E1.1": (Fraction(56), Fraction(56))}, {}, ["PASS", "FAIL", "PASS"]),
    ({"E1.2-excl-R1": (Fraction(61), Fraction(61))}, {}, ["PASS", "PASS", "FAIL"]),
    ({"E1.2-excl-R1": (Fraction(60) + Fraction(6, 10 ** 8), Fraction(60) + Fraction(6, 10 ** 8))}, {},
     ["PASS", "PASS", "PASS"]),                               # inside the 1e-9 C_lo(E1.2) slack
    ({"E1.2-excl-R1": (Fraction(60) + Fraction(7, 10 ** 8), Fraction(60) + Fraction(7, 10 ** 8))}, {},
     ["PASS", "PASS", "FAIL"]),
    ({"E1.2-excl-R1": (Fraction(61), Fraction(61))}, {"E1.2": "last_resort"},
     ["PASS", "PASS", "NOT_EVALUATED_LAST_RESORT"]),
    ({"E1.1": (Fraction(56), Fraction(56))}, {"E1.2-excl-R1": "last_resort", "E1.2": "last_resort"},
     ["PASS", "NOT_EVALUATED_LAST_RESORT", "NOT_EVALUATED_LAST_RESORT"]),
    ({"E1.2-excl-R1": (Fraction(61), Fraction(61))}, {"E1.2-excl-R1": "last_resort"},
     ["PASS", "NOT_EVALUATED_LAST_RESORT", "FAIL"]),          # a smaller-set last resort is still evaluated
    ({}, {"E1.1-half": "last_resort", "E1.2": "jacobi_scaled"}, ["PASS", "PASS", "PASS"]),
])
def test_K4_inequalities_and_the_last_resort_rule(over, paths, statuses):
    out = dr.k4(_k4_res(**over), {**PATHS, **paths})
    assert [o["status"] for o in out["inequalities"]] == statuses
    assert [(o["larger_set"], o["smaller_set"]) for o in out["inequalities"]] == \
        [("E1.1", "E1.1-half"), ("E1.2-excl-R1", "E1.1"), ("E1.2", "E1.2-excl-R1")]
    assert out["failed"] == [o["inequality"] for o in out["inequalities"] if o["status"] == "FAIL"]
    for o in out["inequalities"]:
        if o["status"] == "NOT_EVALUATED_LAST_RESORT":
            assert o["set_named"] == o["larger_set"]


def _capacitance(sets, force_fail=0):
    written = {}
    cap = dr.capacitance_phase(sets, lambda n, o: written.__setitem__(n, dr._clean(o)), force_fail)
    return cap, written


def test_the_capacitance_phase_writes_raw_files_first_and_the_analysis_qualifies(sets):
    cap, written = _capacitance(sets)
    assert list(written) == [f"sigma-{s}.json" for s in dr.SETS] + \
        ["pass-E1.2+E1.2-excl-R1.json", "pass-E1.1.json", "pass-E1.1-half.json"]
    for s in dr.SETS:
        w = written[f"sigma-{s}.json"]
        assert w["status"].startswith("RAW") and len(w["sigma"]) == w["N"] and w["path"] == "cholesky"
    p = written["pass-E1.2+E1.2-excl-R1.json"]
    assert p["m"] == nm.m_count(len(sets["R_E1_2"])) and p["sigmas"] == ["E1.2", "E1.2-excl-R1"]
    assert not any(k.endswith("_fF") for f in written.values() for k in f)
    an = dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), dr.CONFIG["C_hi_fF"])
    assert an["problems"] == [] and [o["status"] for o in an["K4"]["inequalities"]] == ["PASS"] * 3
    c = {s: an["sets"][s]["C_lo_fF"] for s in dr.SETS}
    assert c["E1.1-half"] <= c["E1.1"] <= c["E1.2-excl-R1"] <= c["E1.2"]
    for s in dr.SETS:
        v = an["sets"][s]
        assert v["C_lo_fF"] <= v["C_tilde_fF"] and v["check_g"]["ok"] and 0 <= v["width_rel"] < 1e-6


def test_the_zero_extended_excl_sigma_in_the_E1_2_pass_equals_its_own_pass(sets):
    cap, _ = _capacitance(sets)
    nx = sets["n_excl"]
    own = nm.ld_pass(sets["R_E1_2"][:nx], [cap["sols"]["E1.2-excl-R1"]["sigma"]])
    joint = cap["passes"]["E1.2+E1.2-excl-R1"]
    for key in ("E", "W", "G"):                                   # zero terms add no rounding
        assert nm.to_fr(joint[key][1]) == nm.to_fr(own[key][0]), key
    assert joint["m"] == nm.m_count(len(sets["R_E1_2"]))     # the E1.2 pass's m applies


def test_forced_fallbacks_reach_the_last_resort_and_K4_skips_exactly_the_declared_inequalities(sets):
    cap, written = _capacitance(sets, force_fail=len(nm.FALLBACK_STEPS))
    paths = {s: cap["sols"][s]["path"] for s in dr.SETS}
    assert paths == {"E1.2": "last_resort", "E1.2-excl-R1": "last_resort", "E1.1": "cholesky", "E1.1-half": "cholesky"}
    an = dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), dr.CONFIG["C_hi_fF"])
    st = [o["status"] for o in an["K4"]["inequalities"]]
    assert st[1:] == ["NOT_EVALUATED_LAST_RESORT"] * 2
    assert all(an["sets"][s]["ok"] for s in dr.SETS)          # the bound stays valid on every path


def test_C_lo_above_C_hi_is_unqualified_without_slack(sets):
    cap, _ = _capacitance(sets)
    an = dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), dr.CONFIG["C_hi_fF"])
    c = an["sets"]["E1.2"]["C_lo_fF"]
    assert "C_lo^static > C_hi" not in dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), c)["problems"]
    assert "C_lo^static > C_hi" in dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), float(np.nextafter(c, 0)))["problems"]


def test_every_analysis_failure_is_named(sets, monkeypatch):
    cap, _ = _capacitance(sets)
    kap = Fraction(nm.KAPPA_LO_PQ)
    bad = {**cap, "underflow": {**cap["underflow"], "E1.1": {"ok": False}}}
    assert "pass E1.1: the no-underflow requirement failed" in dr.analyse(bad, kap, 100.0)["problems"]
    p = dict(cap["passes"]["E1.1-half"], B_finite_nonneg=False)
    bad = {**cap, "passes": {**cap["passes"], "E1.1-half": p}}
    assert any("entry bound" in x for x in dr.analyse(bad, kap, 100.0)["problems"])
    e64 = {**cap["e64"], "E1.1": cap["e64"]["E1.1"] * (1 + 1e-6)}
    assert "E1.1: check (g) failed" in dr.analyse({**cap, "e64": e64}, kap, 100.0)["problems"]
    p = dict(cap["passes"]["E1.1"], E=[LD(np.inf)])
    an = dr.analyse({**cap, "passes": {**cap["passes"], "E1.1": p}}, kap, 100.0)
    assert any(x.startswith("E1.1: a non-finite") for x in an["problems"]) and an["K4"] is None


# === outputs and the output guard ==================================================================

def test_the_output_guard_catches_every_forbidden_form():
    g = dr.output_guard
    assert g({"a": 1}, allow_capacitance=False) == []
    assert g({"f_GHz": 1}, allow_capacitance=True)
    assert g({"x": ["ok", {"y": "about 5 MHz"}]}, allow_capacitance=True)
    assert g({"E_C_F1F1": 3.0}, allow_capacitance=True)
    assert g({"EC_value": "x"}, allow_capacitance=True)
    assert g({"E_C_F1F1": "EC_NOT_EVALUATED_BY_E1"}, allow_capacitance=True) == []
    assert g({"deep": [{"C_lo_fF": 5.0}]}, allow_capacitance=False)
    assert g({"deep": [{"C_lo_fF": 5.0}]}, allow_capacitance=True) == []
    assert g({"C_lo_fF": None, "flag_fF": True}, allow_capacitance=False) == []


def _analysis(sets):
    cap, _ = _capacitance(sets)
    return dr.analyse(cap, Fraction(nm.KAPPA_LO_PQ), dr.CONFIG["C_hi_fF"])


def _numbers_fF(o, out=None):
    out = [] if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k).endswith("_fF") and isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(k)
            _numbers_fF(v, out)
    elif isinstance(o, list):
        for v in o:
            _numbers_fF(v, out)
    return out


def test_an_unqualified_summary_carries_no_capacitance_value_but_the_diagnostics(sets):
    an = _analysis(sets)
    s = dr._clean(dr.build_summary("UNQUALIFIED", an, ["K4 inequality 2 failed"], None, dr.CONFIG["C_hi_fF"]))
    assert _numbers_fF(s) == [] and dr.output_guard(s, allow_capacitance=False) == []
    assert s["reported_result"].startswith("NONE") and "Q2" not in s
    assert s["fixed_statements"] == dr.FIXED_STATEMENTS and s["unqualified_reasons"] == ["K4 inequality 2 failed"]
    assert set(s["diagnostics"]["per_set"]) == set(dr.SETS) and s["diagnostics"]["K4"]["failed"] == []
    assert "E1.2" in json.dumps(s) and not re.search(r"\d+\.\d+e?-?\d* ?fF", json.dumps(s))


@pytest.mark.parametrize("q2_flag, label", [(True, "MODEL_BRACKET_"), (False, "Q2_DROPPED_AT_APPROVAL"),
                                            ("true", "Q2_DROPPED_AT_APPROVAL")])
def test_a_qualified_summary_carries_the_bound_and_Q2_only_as_approved(sets, q2_flag, label):
    an = _analysis(sets)
    ap = {"tolerance_scope_decision": "COPIED_NUMBERS_EXCLUDED", "q2_within_D5": q2_flag}
    s = dr._clean(dr.build_summary("QUALIFIED", an, [], ap, dr.CONFIG["C_hi_fF"]))
    r = s["reported_result"]
    assert r["C_lo_static_fF"] == an["sets"]["E1.2"]["C_lo_fF"] and r["C_hi_fF"] == dr.CONFIG["C_hi_fF"]
    lo, hi = r["display_fF"].strip("[]").split(", ")
    assert Decimal(lo) <= _dec(Fraction(r["C_lo_static_fF"])) and Decimal(hi) >= _dec(Fraction(r["C_hi_fF"]))
    assert s["Q2"]["label"].startswith(label) and s["tolerance_scope_decision"] == "COPIED_NUMBERS_EXCLUDED"
    assert dr.output_guard(s, allow_capacitance=True) == []
    assert set(_numbers_fF(s)) == {"C_lo_static_fF", "C_hi_fF"}   # internal sets are not in the summary
    iv = dr._clean(dr.internal_values(an))
    assert iv["status"].startswith("INTERNAL") and set(iv["per_set"]) == set(dr.SETS)


def test_Q2_is_exact_at_its_boundary():
    br = Fraction(dr.CONFIG["C_br_fF"])
    gam = 1 - Fraction(dr.CONFIG["gamma"])
    at = br / gam
    below, above = nm.rd(at), nm.ru(at)
    assert Fraction(below) * gam <= br < Fraction(above) * gam
    assert dr.q2(below)["label"] == "MODEL_BRACKET_NOT_CONTRADICTED"
    assert dr.q2(above)["label"] == "MODEL_BRACKET_PREMISE_REFUTED"
    assert dr.q2(dr.CONFIG["C_br_fF"])["label"] == "MODEL_BRACKET_NOT_CONTRADICTED"
    for x in (below, above):
        q = dr.q2(x)
        assert "LIBM" in q["basis"] and q["gamma"] == "1e-6"


def test_the_display_rounds_down_and_up():
    assert dr._display(67.9755386760262, ROUND_CEILING) == "67.975539"
    assert dr._display(67.9755386760262, ROUND_FLOOR) == "67.975538"
    assert dr._display(1.0, ROUND_FLOOR) == "1.000000"


def test_the_fixed_statements_are_the_contract_ones_and_every_output_string_is_frequency_free():
    fs = dr.FIXED_STATEMENTS
    assert (fs["correspondence_to_registered_operator"], fs["E_C_F1F1"], fs["deviation_from_registered_value"],
            fs["suitability"]) == ("NOT_ESTABLISHED", "EC_NOT_EVALUATED_BY_E1", "NOT_EVALUATED", "SUITABILITY_NOT_ASSESSED")
    assert dr.output_guard(dr._clean({"f": fs, "s": dr.build_summary("UNQUALIFIED", None, [], None, 1.0)}),
                           allow_capacitance=False) == []


def test_the_evidence_writes_are_atomic_strict_and_guarded(tmp_path, monkeypatch):
    t = tmp_path / "x.json"
    dr._guarded_dump(t, {"nan": float("nan"), "inf": [np.inf], "np": np.float64(2.5), "i": np.int64(3),
                         "b": np.bool_(True), "fr": Fraction(1, 3), "_private": 1})
    assert _strict_json(t) == {"nan": None, "inf": [None], "np": 2.5, "i": 3, "b": True, "fr": "1/3"}
    with pytest.raises(dr.AttemptFailed, match="output guard"):
        dr._guarded_dump(tmp_path / "y.json", {"freq_GHz": 5.0})
    assert not (tmp_path / "y.json").exists()

    def interrupted(src, dst):
        raise dr.BudgetExceeded("SIGTERM")

    monkeypatch.setattr(dr.os, "replace", interrupted)
    with pytest.raises(dr.BudgetExceeded):
        dr._dump(tmp_path / "z.json", {"a": 1})
    assert not (tmp_path / "z.json").exists() and (tmp_path / "z.json.partial").is_file()


# === probes, environment and invocation =============================================================

def test_the_probes_pass_here_and_each_detects_its_fault(monkeypatch):
    assert nm.arithmetic_probe()["ok"] and nm.dispatch_probe(300)["ok"]
    real_log = np.log

    def off_by_one_ulp(x, *a, **k):
        y = real_log(x, *a, **k)
        return np.nextafter(y, np.full_like(y, np.inf)) if np.asarray(y).dtype == LD else y

    with monkeypatch.context() as mp:
        mp.setattr(np, "log", off_by_one_ulp)
        r = nm.dispatch_probe(60)
        assert not r["ok"] and r["mismatches"] > 0
    with monkeypatch.context() as mp, np.errstate(over="ignore"):
        mp.setattr(nm, "LD", np.float64)                        # 53-bit arithmetic, as a PC word would give
        assert nm.arithmetic_probe()["ok"] is False


def test_the_environment_check_and_each_difference(monkeypatch):
    import platform

    import scipy
    here = {**dr.ENVIRONMENT, "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "glibc": platform.libc_ver()[1]}
    monkeypatch.setattr(dr, "ENVIRONMENT", here)
    for k, v in THREADS.items():
        monkeypatch.setenv(k, v)
    assert dr.environment_problems() == []
    for key in ("python", "numpy", "scipy", "glibc"):
        monkeypatch.setattr(dr, "ENVIRONMENT", {**here, key: "0.0"})
        assert dr.environment_problems(), key
    monkeypatch.setattr(dr, "ENVIRONMENT", here)
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    assert any("OMP_NUM_THREADS" in p for p in dr.environment_problems())
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    real = np.finfo
    monkeypatch.setattr(dr.np, "finfo", lambda t: real(np.float64))
    assert any("64-bit significand" in p for p in dr.environment_problems())


def test_the_invocation_is_measured_and_every_difference_refuses():
    good = {"cwd": str(REPO), "argv": ["experiments/e1-s1-lower-bound/driver.py"],
            "parent_argv": ["/usr/bin/timeout", "--signal=KILL", "1260", ".venv/bin/python",
                            "experiments/e1-s1-lower-bound/driver.py"],
            "prefix": str(REPO / ".venv"), "optimize": 0, "dont_write_bytecode": True,
            "pycache_prefix": dr.NO_BYTECODE_CACHE, "bytecode_cache_paths": {"x": dr.NO_BYTECODE_CACHE + "/x.pyc"}}
    assert dr.invocation_problems(good) == []
    for over, needle in (({"cwd": "/tmp"}, "working directory"), ({"argv": good["argv"] + ["--x"]}, "argv"),
                         ({"parent_argv": ["bash"]}, "parent process"),
                         ({"parent_argv": good["parent_argv"][:2] + ["3600"] + good["parent_argv"][3:]}, "parent process"),
                         ({"prefix": "/usr"}, "prefix"), ({"optimize": 1}, "optimisation"),
                         ({"pycache_prefix": None}, "bytecode"),
                         ({"bytecode_cache_paths": {"x": "/repo/__pycache__/x.pyc"}}, "bytecode")):
        assert any(needle in p for p in dr.invocation_problems({**good, **over})), needle
    assert dr.INVOCATION.endswith(" ".join(dr.INVOCATION_MEASURED["parent_argv"]))
    assert "timeout --signal=KILL 1260" in dr.INVOCATION and dr.BUDGET["outer_kill_s"] == 1260


def test_the_driver_process_measures_its_real_invocation_and_bypasses_bytecode_caches():
    out = subprocess.run(["timeout", "--signal=KILL", "120", sys.executable, "experiments/e1-s1-lower-bound/driver.py",
                          "--show-invocation"], cwd=str(REPO), capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS})
    assert out.returncode == 0, out.stderr[-500:]
    r = json.loads(out.stdout)
    m = r["measured"]
    assert Path(m["parent_argv"][0]).name == "timeout" and m["dont_write_bytecode"]
    assert set(m["bytecode_cache_paths"]) == {"e1_numerics.py", "e1_geometry.py", "e1_controls.py", "anchor_fem.py",
                                              "orchestrator/manifest.py"}
    assert all(c.startswith(dr.NO_BYTECODE_CACHE) for c in m["bytecode_cache_paths"].values())
    assert any(d.startswith("argv") for d in r["differences_from_declared"])
    assert not any("bytecode" in d or "working directory" in d for d in r["differences_from_declared"])


def test_the_attempt_path_loads_only_bound_repository_code_and_the_stand_in_is_detected():
    out = _python(f"""
        import sys; sys.path.insert(0, {str(HERE)!r})
        import driver as dr
        print(dr.unbound_repo_modules())
        import e1_standin
        print(dr.unbound_repo_modules())
    """)
    assert out.returncode == 0, out.stderr[-800:]
    first, second = out.stdout.strip().splitlines()
    assert first == "[]" and "e1_standin.py" in second
    src = (HERE / "driver.py").read_text()
    tree = ast.parse(src)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any("e1_standin" in ast.dump(n) for n in top)
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        if any(isinstance(x, ast.Import) and any(a.name == "e1_standin" for a in x.names) for x in ast.walk(fn)):
            assert fn.name in ("rehearsal", "confirmation", "proxy_a_ge"), fn.name


def test_nothing_in_the_E1_code_can_launch_a_process_or_a_solver():
    for name in E1_SOURCES:
        tree = ast.parse((HERE / name).read_text())
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not mods & {"subprocess", "multiprocessing", "socket", "urllib", "requests", "http", "shutil"}, name
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not attrs & {"system", "popen", "execv", "execve", "spawnv", "fork", "Popen"}, name


# === the approval ===================================================================================

def test_the_draft_approval_matches_the_frozen_code_and_authorises_nothing():
    draft = _strict_json(dr.APPROVAL_DRAFT)
    live = dr._clean(dr.draft_approval())
    # the checkout path is the execution host's; any other checkout (CI) differs only there
    assert draft["repository_path"] == EXECUTION_HOST_REPOSITORY
    assert {k: v for k, v in draft.items() if k != "repository_path"} == \
        {k: v for k, v in live.items() if k != "repository_path"}
    assert draft["DRAFT"].startswith("NOT AN APPROVAL") and not dr.APPROVAL.exists()
    assert draft["contract_sha256"] == dr.CONTRACT_SHA256 and draft["gamma"] == "1e-6" and draft["tolerance_set"] == "T0"
    assert draft["code_sha256"] == {n: _sha(p) for n, p in dr.CODE_FILES.items()}
    with pytest.raises(dr.Refusal):
        dr.require_approval(raw=dr.APPROVAL_DRAFT.read_bytes())


def _approval(**over):
    now = datetime.now(timezone.utc)
    ap = {k: v for k, v in dr.draft_approval().items() if k not in ("DRAFT", "how_to_grant_it", "does_not_authorise")}
    ap.update(source_commit=dr.git_head(REPO), not_before_utc=(now - timedelta(hours=1)).isoformat(),
              not_after_utc=(now + timedelta(days=6)).isoformat(),
              tolerance_scope_decision="COPIED_NUMBERS_WITHIN_SCOPE", q2_within_D5=True)
    ap.update(over)
    return json.dumps(dr._clean(ap)).encode()


def test_a_complete_approval_is_accepted():
    ap = dr.require_approval(raw=_approval())
    assert ap["q2_within_D5"] is True and ap["attempt"] == 1


@pytest.mark.parametrize("over, needle", [
    ({"contract_sha256": "0" * 64}, "contract_sha256 does not match"),
    ({"mesh_sha256": "0" * 64}, "mesh_sha256 does not match"),
    ({"code_sha256": {"driver.py": "0" * 64}}, "code_sha256 does not match"),
    ({"gamma": "1e-5"}, "gamma does not match"),
    ({"tolerance_set": "T1"}, "tolerance_set does not match"),
    ({"attempt": 2}, "attempt does not match"),
    ({"prior_records": ["x"]}, "prior_records does not match"),
    ({"budget": {**dr.BUDGET, "cpu_soft_s": 1800}}, "budget does not match"),
    ({"invocation": "python driver.py"}, "invocation does not match"),
    ({"environment": {**dr.ENVIRONMENT, "numpy": "2.0.0"}}, "environment does not match"),
    ({"repository_path": "/elsewhere"}, "repository_path does not match"),
    ({"tolerance_scope_decision": None}, "section 7 scope decision"),
    ({"tolerance_scope_decision": "EITHER"}, "section 7 scope decision"),
    ({"q2_within_D5": "true"}, "Q2 decision"),
    ({"q2_within_D5": None}, "Q2 decision"),
    ({"source_commit": "abc"}, "not a full commit SHA"),
    ({"source_commit": "0" * 40}, "is not HEAD"),
    ({"not_after_utc": "2026-01-01T00:00:00"}, "no time zone"),
    ({"not_before_utc": "2020-01-01T00:00:00+00:00", "not_after_utc": "2020-01-02T00:00:00+00:00"}, "outside"),
    ({"note": "anything"}, "fields the driver does not bind"),
    ({"DRAFT": "NOT AN APPROVAL"}, "fields the driver does not bind"),
    ({"does_not_authorise": ["nothing"]}, "does_not_authorise differs"),
])
def test_a_stale_incomplete_or_misbound_approval_is_refused(over, needle):
    raw = json.loads(_approval())
    for k, v in over.items():
        if v is None:
            raw.pop(k, None)
        else:
            raw[k] = v
    with pytest.raises(dr.Refusal, match=re.escape(needle)):
        dr.require_approval(raw=json.dumps(raw).encode())


def test_an_approval_window_longer_than_seven_days_or_unparseable_is_refused():
    now = datetime.now(timezone.utc)
    with pytest.raises(dr.Refusal, match="longer than 7 days"):
        dr.require_approval(raw=_approval(not_before_utc=(now - timedelta(days=1)).isoformat(),
                                          not_after_utc=(now + timedelta(days=6, hours=1)).isoformat()))
    with pytest.raises(dr.Refusal, match="not JSON"):
        dr.require_approval(raw=b"{")
    with pytest.raises(dr.Refusal, match="not an object"):
        dr.require_approval(raw=b"[]")


# === the one attempt and its failure paths (synthetic, in tmp_path) =================================

DIG = {"contract": dr.CONTRACT_SHA256, "mesh": "m" * 64, "baseline_manifest": "b" * 64,
       "baseline_summary": "s" * 64, "code": {"driver.py": "d" * 64}}


def _gate(tmp_path, monkeypatch, sets, controls=None, geometry=None):
    """Route execute() onto the small synthetic sets in tmp_path. Every pre-attempt check is
    stubbed to pass here; each has its own test above."""
    approval = tmp_path / "E1-APPROVAL.json"
    approval.write_text("{}")
    monkeypatch.setattr(dr, "APPROVAL", approval)
    monkeypatch.setattr(dr, "APPROVAL_CONSUMED", tmp_path / "E1-APPROVAL.consumed.json")
    monkeypatch.setattr(dr, "ATTEMPT_MARKER", tmp_path / "ATTEMPT-SPENT.json")
    monkeypatch.setattr(dr, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(dr, "common_ledger_path", lambda repo=None: tmp_path / "gitcommon" / dr.COMMON_LEDGER)
    (tmp_path / "gitcommon").mkdir()
    monkeypatch.setattr(dr, "require_approval", lambda now=None, **k: {
        "tolerance_scope_decision": "COPIED_NUMBERS_WITHIN_SCOPE", "q2_within_D5": True, "run": "synthetic"})
    monkeypatch.setattr(dr, "unbound_repo_modules", lambda: [])
    monkeypatch.setattr(dr, "invocation_problems", lambda m=None: [])
    monkeypatch.setattr(dr, "preflight_problems", lambda: {"problems": [], "digests": DIG, "baseline": {},
                                                           "probes": {}, "c0": nm.derive_c0()})
    monkeypatch.setattr(dr, "input_digests", lambda: DIG)
    monkeypatch.setattr(dr, "_require_enforceable_budget", lambda: None)
    monkeypatch.setattr(dr, "qmhp_mesh", lambda: {"synthetic": True})
    monkeypatch.setattr(dr, "controls_phase", controls or (lambda c0: {"K1": {"pass": True}, "failures": []}))
    monkeypatch.setattr(dr, "geometry_phase", geometry or (lambda mesh: {"facts": {"synthetic": True},
                                                                         "failures": [], **sets}))
    monkeypatch.setattr(dr, "_enforce_budget", lambda: {"synthetic": "no limits in pytest"})
    monkeypatch.setattr(dr, "_budget_enforcement_problems", lambda: [])
    monkeypatch.setattr(dr, "_disarm", lambda: None)
    monkeypatch.setattr(dr, "_SIGNALS", {"stopping": False, "received": []})   # what _enforce_budget resets


RAW_FILES = ["provenance.json", "controls.json", "geometry.json"] + [f"sigma-{s}.json" for s in dr.SETS] + \
    ["pass-E1.2+E1.2-excl-R1.json", "pass-E1.1.json", "pass-E1.1-half.json"]


def test_without_an_approval_the_attempt_refuses_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "APPROVAL", tmp_path / "E1-APPROVAL.json")
    monkeypatch.setattr(dr, "APPROVAL_CONSUMED", tmp_path / "E1-APPROVAL.consumed.json")
    monkeypatch.setattr(dr, "ATTEMPT_MARKER", tmp_path / "ATTEMPT-SPENT.json")
    monkeypatch.setattr(dr, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(dr, "common_ledger_path", lambda repo=None: tmp_path / "gitcommon" / dr.COMMON_LEDGER)
    with pytest.raises(dr.Refusal, match="PREPARED, NOT APPROVED"):
        dr.execute()
    assert sorted(tmp_path.iterdir()) == []


def test_the_repository_holds_no_approval_no_ledger_and_no_E1_record():
    assert not dr.APPROVAL.exists() and not dr.APPROVAL_CONSUMED.exists() and not dr.ATTEMPT_MARKER.exists()
    assert list((REPO / "results").glob(dr.RECORD_PREFIX + "*")) == []


def test_a_granted_attempt_writes_every_file_in_order_then_a_verified_manifest(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    order = []
    real, real_text = dr._guarded_dump, dr._write_text
    monkeypatch.setattr(dr, "_guarded_dump", lambda p, o: (order.append(p.name), real(p, o)))
    monkeypatch.setattr(dr, "_write_text", lambda p, t: (order.append(p.name), real_text(p, t)))
    rec = dr.execute()
    assert rec.parent == tmp_path / "results" and rec.name.startswith(dr.RECORD_PREFIX)
    assert order == RAW_FILES + ["internal-sets.json", "summary.json"]
    assert sorted(p.name for p in rec.iterdir()) == sorted(order + ["manifest.sha256"])
    assert manifest.verify(rec) == [] and manifest.unexpected_files(rec) == []
    for p in rec.glob("*.json"):
        _strict_json(p)
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "QUALIFIED" and s["Q2"]["label"].startswith("MODEL_BRACKET_")
    assert s["subject"] == dr.SUBJECT_S1 and s["signals_received"] == [] and s["provenance_remeasured_equal"]
    prov = _strict_json(rec / "provenance.json")
    assert prov["approval_sha256"] == hashlib.sha256(b"{}").hexdigest() and prov["contract_sha256"] == dr.CONTRACT_SHA256
    assert prov["source_commit_measured"] == dr.git_head(REPO)
    for entry in (dr.common_ledger_path(), dr.ATTEMPT_MARKER):
        assert _strict_json(entry)["record"] == rec.name
    assert not dr.APPROVAL.exists() and dr.APPROVAL_CONSUMED.read_text() == "{}"
    with pytest.raises(dr.Refusal, match="the one attempt is spent"):
        dr.execute()


def test_a_checkout_that_removes_the_tracked_ledger_does_not_reopen_the_attempt(tmp_path, monkeypatch, sets):
    import shutil
    _gate(tmp_path, monkeypatch, sets)
    rec = dr.execute()
    shutil.rmtree(rec.parent)
    dr.ATTEMPT_MARKER.unlink()
    dr.APPROVAL.write_text("{}")
    with pytest.raises(dr.Refusal, match="the one attempt is spent"):
        dr.execute()
    dr.APPROVAL_CONSUMED.unlink()
    with pytest.raises(dr.Refusal, match="git common dir"):
        dr.execute()
    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize("make", ["marker", "consumed", "record"])
def test_any_one_ledger_entry_alone_refuses(tmp_path, monkeypatch, sets, make):
    _gate(tmp_path, monkeypatch, sets)
    if make == "marker":
        dr.ATTEMPT_MARKER.write_text("{}")
    elif make == "consumed":
        dr.APPROVAL_CONSUMED.write_text("{}")
    else:
        (tmp_path / "results" / (dr.RECORD_PREFIX + "20260101T000000Z")).mkdir(parents=True)
    with pytest.raises(dr.Refusal, match="the one attempt is spent"):
        dr.execute()
    assert not dr.common_ledger_path().exists() and dr.APPROVAL.exists()


def test_the_ledger_entries_are_created_exclusively(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "spent_state", lambda root=None: [])
    common = dr.common_ledger_path()
    common.parent.mkdir(parents=True)
    common.write_text('{"someone": "else"}')
    with pytest.raises(dr.Refusal, match="git common directory: the one attempt is spent"):
        dr.execute()
    assert common.read_text() == '{"someone": "else"}' and dr.APPROVAL.exists() and not dr.ATTEMPT_MARKER.exists()
    common.unlink()
    dr.ATTEMPT_MARKER.write_text('{"someone": "else"}')
    with pytest.raises(dr.AttemptFailed, match="no record could be created"):
        dr.execute()
    assert dr.ATTEMPT_MARKER.read_text() == '{"someone": "else"}'
    note = _strict_json(common)
    assert note["record_created"] is False and "FileExistsError" in note["error"]
    assert dr.APPROVAL_CONSUMED.exists() and not dr.APPROVAL.exists()


def test_a_failure_before_the_record_exists_is_written_into_the_ledger(tmp_path, monkeypatch, sets, capsys):
    _gate(tmp_path, monkeypatch, sets)
    (tmp_path / "results").write_text("not a directory")
    assert dr.main([]) == 3
    assert "no record could be created" in capsys.readouterr().err
    for entry in (dr.common_ledger_path(), dr.ATTEMPT_MARKER):
        note = _strict_json(entry)
        assert note["record_created"] is False and note["traceback"]
    assert dr.APPROVAL_CONSUMED.exists()
    assert dr.main([]) == 2


def test_a_failure_before_the_first_ledger_entry_spends_nothing(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)

    def broken():
        raise OSError("setrlimit failed")

    monkeypatch.setattr(dr, "_enforce_budget", broken)
    with pytest.raises(dr.Refusal, match="nothing was spent"):
        dr.execute()
    assert dr.spent_state() == [] and dr.APPROVAL.exists()


@pytest.mark.parametrize("patch, needle", [
    ("preflight", "section 8 refusal condition"), ("invocation", "invocation differs"),
    ("unbound", "does not bind"), ("budget", "hard limit"), ("contract", "frozen revision 8.2"),
])
def test_every_pre_attempt_refusal_spends_nothing(tmp_path, monkeypatch, sets, patch, needle):
    _gate(tmp_path, monkeypatch, sets)
    if patch == "preflight":
        monkeypatch.setattr(dr, "preflight_problems", lambda: {"problems": ["dispatch probe failed"]})
    elif patch == "invocation":
        monkeypatch.setattr(dr, "invocation_problems", lambda m=None: ["argv"])
    elif patch == "unbound":
        monkeypatch.setattr(dr, "unbound_repo_modules", lambda: ["experiments/e1-s1-lower-bound/e1_standin.py"])
    elif patch == "budget":
        def low():
            raise dr.Refusal("this environment's hard limit 1 is below the declared budget 960")
        monkeypatch.setattr(dr, "_require_enforceable_budget", low)
    else:
        monkeypatch.setattr(dr, "CONTRACT_SHA256", "0" * 64)
    with pytest.raises(dr.Refusal, match=re.escape(needle)):
        dr.execute()
    assert dr.spent_state() == [] and dr.APPROVAL.exists() and not (tmp_path / "results").exists()


def test_the_real_budget_availability_check_refuses_a_low_hard_limit(monkeypatch):
    import resource
    monkeypatch.setattr(dr.resource, "getrlimit", lambda r: (10, 10))
    with pytest.raises(dr.Refusal, match="hard limit"):
        dr._require_enforceable_budget()
    monkeypatch.setattr(dr.resource, "getrlimit", lambda r: (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    dr._require_enforceable_budget()


def test_a_failed_control_stops_before_any_matrix_and_reports_no_value(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets, controls=lambda c0: {"K3": {"pass": False}, "failures": ["K3"]})
    monkeypatch.setattr(nm, "assemble64", lambda *a, **k: pytest.fail("a matrix was assembled after a failed control"))
    rec = dr.execute()
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and s["unqualified_reasons"] == ["control K3 failed"]
    assert _numbers_fF(s) == [] and s["diagnostics"] is None and "Q2" not in s
    assert sorted(p.name for p in rec.iterdir()) == ["controls.json", "manifest.sha256", "provenance.json", "summary.json"]
    assert manifest.verify(rec) == []


def test_a_failed_geometry_check_stops_before_any_matrix(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets, geometry=lambda mesh: {"facts": {}, "failures": ["N_E1_2: measured 1"]})
    monkeypatch.setattr(nm, "assemble64", lambda *a, **k: pytest.fail("a matrix was assembled after a geometry failure"))
    rec = dr.execute()
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and s["unqualified_reasons"] == ["geometry: N_E1_2: measured 1"]
    assert not list(rec.glob("sigma-*")) and manifest.verify(rec) == []


def test_an_invalid_last_resort_is_unqualified_with_no_value(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)

    def invalid(S, n_island, *, force_fail=0):
        raise nm.LastResortInvalid("the last-resort sigma has Q <= 0")

    monkeypatch.setattr(nm, "solve_sigma", invalid)
    rec = dr.execute()
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and "trial vector" in s["unqualified_reasons"][0] and _numbers_fF(s) == []
    assert not (rec / "internal-sets.json").exists()


def test_a_provenance_remeasurement_mismatch_is_unqualified(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "input_digests", lambda: {**DIG, "mesh": "x" * 64})   # the re-measurement at the end
    rec = dr.execute()
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and s["provenance_remeasured_equal"] is False
    assert "a provenance re-measurement differs from the start" in s["unqualified_reasons"] and _numbers_fF(s) == []
    assert not (rec / "internal-sets.json").exists()


def test_C_lo_above_C_hi_in_the_attempt_is_unqualified(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setitem(dr.CONFIG, "C_hi_fF", 1e-3)
    s = _strict_json(dr.execute() / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and "C_lo^static > C_hi" in s["unqualified_reasons"] and _numbers_fF(s) == []


@pytest.mark.parametrize("where", ["ld_pass", "second_solve", "enclosure"])
def test_a_crash_after_spending_is_FAILED_with_the_raw_files_and_a_verified_manifest(tmp_path, monkeypatch, sets, where,
                                                                                    capsys):
    _gate(tmp_path, monkeypatch, sets)
    if where == "ld_pass":
        monkeypatch.setattr(nm, "ld_pass", lambda *a, **k: (_ for _ in ()).throw(ZeroDivisionError("boom")))
    elif where == "second_solve":
        real, n = nm.solve_sigma, []

        def once(*a, **k):
            n.append(1)
            if len(n) == 2:
                raise MemoryError("second factorisation")
            return real(*a, **k)

        monkeypatch.setattr(nm, "solve_sigma", once)
    else:
        monkeypatch.setattr(nm, "enclosure", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    assert dr.main([]) == 3
    assert "recorded in failure.json" in capsys.readouterr().err
    (rec,) = (tmp_path / "results").iterdir()
    f = _strict_json(rec / "failure.json")
    assert f["outcome"].startswith("FAILED") and f["reported_result"] == "NONE" and manifest.verify(rec) == []
    assert not (rec / "summary.json").exists() and _numbers_fF(f) == []
    if where in ("ld_pass", "enclosure"):
        assert all((rec / f"sigma-{s}.json").is_file() for s in dr.SETS)
    if where == "enclosure":
        assert (rec / "pass-E1.2+E1.2-excl-R1.json").is_file()
    assert dr.main([]) == 2


def test_the_output_guard_refusing_the_summary_is_FAILED(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "FIXED_STATEMENTS", {**dr.FIXED_STATEMENTS, "note": "5 GHz"})
    with pytest.raises(dr.AttemptFailed, match="output guard"):
        dr.execute()
    (rec,) = (tmp_path / "results").iterdir()
    assert (rec / "failure.json").is_file() and not (rec / "summary.json").exists() and manifest.verify(rec) == []


def test_a_budget_signal_inside_the_attempt_is_FAILED(tmp_path, monkeypatch, sets):
    def stop(mesh):
        raise dr.BudgetExceeded("SIGXCPU: a declared budget limit or a termination signal was reached")

    _gate(tmp_path, monkeypatch, sets, geometry=stop)
    with pytest.raises(dr.AttemptFailed, match="SIGXCPU"):
        dr.execute()
    (rec,) = (tmp_path / "results").iterdir()
    assert "SIGXCPU" in _strict_json(rec / "failure.json")["error"] and manifest.verify(rec) == []


# === the budget and signals in real processes =====================================================

_CHILD_GATE = """
import sys, json, time
sys.path.insert(0, {here!r}); sys.path.insert(0, {tests!r})
import driver as dr, e1_numerics as nm
from pathlib import Path
from test_e1_s1_lower_bound import small_sets, DIG
tmp = Path({tmp!r})
dr.APPROVAL = tmp / "E1-APPROVAL.json"; dr.APPROVAL.write_text("{{}}")
dr.APPROVAL_CONSUMED = tmp / "E1-APPROVAL.consumed.json"
dr.ATTEMPT_MARKER = tmp / "ATTEMPT-SPENT.json"
dr.RESULTS_ROOT = tmp / "results"
dr.common_ledger_path = lambda repo=None: tmp / "gitcommon" / dr.COMMON_LEDGER
(tmp / "gitcommon").mkdir()
dr.require_approval = lambda now=None, **k: {{"q2_within_D5": True, "tolerance_scope_decision": "COPIED_NUMBERS_EXCLUDED"}}
dr.unbound_repo_modules = lambda: []
dr.invocation_problems = lambda m=None: []
dr.preflight_problems = lambda: {{"problems": [], "digests": DIG, "baseline": {{}}, "probes": {{}}, "c0": nm.derive_c0()}}
dr.input_digests = lambda: DIG
dr.qmhp_mesh = lambda: {{}}
dr.controls_phase = lambda c0: {{"failures": []}}
{extra}
sys.exit(dr.main([]))
"""


def _child(tmp_path, extra: str) -> str:
    return _CHILD_GATE.format(here=str(HERE), tests=str(REPO / "tests"), tmp=str(tmp_path), extra=textwrap.dedent(extra))


@pytest.mark.parametrize("budget, work, expect", [
    ({"wall_alarm_s": 2}, "import time\nwhile True: time.sleep(0.05)", "SIGALRM"),
    ({"cpu_soft_s": 1, "cpu_hard_s": 30}, "while True: pass", "SIGXCPU"),
    ({"address_space_bytes": 1024 ** 3}, "import numpy\nnumpy.ones(2 * 1024**3 // 8)", "MemoryError"),
    ({}, "import os, signal, time\nos.kill(os.getpid(), signal.SIGTERM)\ntime.sleep(5)", "SIGTERM"),
    ({}, "import os, signal, time\nos.kill(os.getpid(), signal.SIGHUP)\ntime.sleep(5)", "SIGHUP"),
    ({}, "import os, signal, time\nos.kill(os.getpid(), signal.SIGINT)\ntime.sleep(5)", "SIGINT"),
])
def test_the_declared_budget_binds_a_real_process(budget, work, expect):
    code = (f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport driver as dr\n"
            f"dr.BUDGET = {{**dr.BUDGET, **{budget!r}}}\nprint(dr._enforce_budget())\n{work}\n")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90,
                          env={**os.environ, **THREADS})
    assert proc.returncode != 0 and expect in proc.stderr, proc.stderr[-600:]


def test_the_declared_limits_are_the_contract_ones():
    b = dr.BUDGET
    assert (b["cpu_soft_s"], b["cpu_hard_s"], b["address_space_bytes"], b["wall_alarm_s"], b["outer_kill_s"]) == \
        (900, 960, 4 * 1024 ** 3, 1200, 1260)
    assert b["attempts"] == 1 and b["retry"] == "none"
    assert dr.CONFIRMATION_LIMITS == {"cpu_s": 450.0, "peak_address_space_bytes": 2 * 1024 ** 3}
    for phrase in ("RLIMIT_CPU soft 900 s, hard 960 s", "RLIMIT_AS 4 GiB", "SIGALRM 1,200 s after process start",
                   "outer SIGKILL at 1,260 s", "≤ 450 s CPU and ≤ 2 GiB"):
        assert phrase in CONTRACT_TEXT, phrase


def test_disarm_ignores_every_stop_signal_cancels_the_alarm_and_lifts_the_soft_limits():
    out = _python(f"""
        import sys, json, signal, resource
        sys.path.insert(0, {str(HERE)!r})
        import driver as dr
        lim = dr._enforce_budget()
        armed = [signal.getsignal(s) is dr._on_limit for s in dr.STOP_SIGNALS]
        soft = [resource.getrlimit(r) for r in (resource.RLIMIT_CPU, resource.RLIMIT_AS)]
        dr._disarm()
        print(json.dumps({{"armed": armed, "soft": soft, "stopping": dr._SIGNALS["stopping"],
                          "ignored": [signal.getsignal(s) == signal.SIG_IGN for s in dr.STOP_SIGNALS],
                          "alarm_left": signal.alarm(0),
                          "soft_eq_hard": [resource.getrlimit(r)[0] == resource.getrlimit(r)[1]
                                           for r in (resource.RLIMIT_CPU, resource.RLIMIT_AS)]}}))
    """)
    assert out.returncode == 0, out.stderr[-500:]
    r = json.loads(out.stdout)
    assert r["armed"] == [True] * 5 and r["stopping"] and r["ignored"] == [True] * 5 and r["alarm_left"] == 0
    assert r["soft"] == [[900, 960], [4 * 1024 ** 3, 5 * 1024 ** 3]] and r["soft_eq_hard"] == [True, True]


@pytest.mark.parametrize("sig", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_a_stop_signal_to_the_process_group_leaves_a_sealed_FAILED_record(tmp_path, sig):
    """The real _enforce_budget, _on_limit, _disarm and failure path, under the declared
    wrapper, with the signal sent to the whole process group (as GNU timeout forwards it)."""
    import signal as sg
    import time
    for trial in range(2):
        d = tmp_path / f"t{trial}"
        d.mkdir()
        code = _child(d, """
            def busy(mesh):
                print("READY", flush=True)
                while True:
                    pass
            dr.geometry_phase = busy
        """)
        proc = subprocess.Popen(["timeout", "--signal=KILL", "120", sys.executable, "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True, env={**os.environ, **THREADS}, cwd=str(REPO))
        assert proc.stdout.readline().strip() == "READY", proc.stderr.read()[-800:]
        time.sleep(0.05 * trial)
        os.killpg(proc.pid, getattr(sg, sig))
        _, err = proc.communicate(timeout=120)
        assert proc.returncode == 3, (trial, proc.returncode, err[-1500:])
        (rec,) = (d / "results").glob(dr.RECORD_PREFIX + "*")
        assert manifest.verify(rec) == [], trial
        f = _strict_json(rec / "failure.json")
        got = {e["signal"] for e in f["signals_received"]}
        assert sig in f["error"] and got == {sig}, (trial, got)
        assert (d / "gitcommon" / dr.COMMON_LEDGER).is_file() and (d / "E1-APPROVAL.consumed.json").is_file()


def test_the_failure_path_survives_memory_exhaustion_by_small_allocations(tmp_path):
    code = _child(tmp_path, """
        dr.BUDGET = {**dr.BUDGET, "address_space_bytes": 1536 * 1024 ** 2}
        def hog(mesh):
            keep = []
            while True:
                keep.append(bytearray(64 * 1024))
        dr.geometry_phase = hog
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS}, cwd=str(REPO))
    assert out.returncode == 3 and "MemoryError" in out.stderr, out.stderr[-1500:]
    (rec,) = (tmp_path / "results").glob(dr.RECORD_PREFIX + "*")
    assert "MemoryError" in _strict_json(rec / "failure.json")["error"] and manifest.verify(rec) == []


def test_a_real_process_runs_the_small_synthetic_attempt_end_to_end_under_the_real_budget(tmp_path):
    out = subprocess.run([sys.executable, "-c", _child(tmp_path, """
        dr.geometry_phase = lambda mesh: {"facts": {}, "failures": [], **small_sets()}
    """)], capture_output=True, text=True, timeout=300, env={**os.environ, **THREADS}, cwd=str(REPO))
    assert out.returncode == 0, out.stderr[-1500:]
    (rec,) = (tmp_path / "results").glob(dr.RECORD_PREFIX + "*")
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "QUALIFIED" and manifest.verify(rec) == []
    lim = _strict_json(rec / "provenance.json")["limits"]
    assert (lim["cpu_soft_s"], lim["cpu_hard_s"], lim["address_space_bytes"]) == (900, 960, 4 * 1024 ** 3)


# === revision 8.3: separation of every pre-approval numeric set from the S1 attempt sets (D14) ======

S1_ISLAND_SETS = {"E1.1": eg.island_panels(32, 3.5), "E1.1-half": eg.island_panels(32, 3.5, step=2)}


def test_the_stand_in_island_is_the_revision_8_3_construction():
    """Contract section 6 (revision 8.3): x_k = -0.6 + s_k(0.075), y_k = s_k(0.0625), s_k(a) the
    section 3.1 formula with n = 32, q = 3.5; the nested grid uses the even k. Recomputed here
    independently with libm pow."""
    def s_k(a):
        return [math.copysign(1.0, k) * (a - 1e-12) * (1 - math.pow(1 - abs(k) / 16, 3.5)) if k else 0.0
                for k in range(-16, 17)]
    sx, sy = s_k(0.075), s_k(0.0625)
    want = np.array([(-0.6 + sx[i], -0.6 + sx[i + 1], sy[j], sy[j + 1]) for i in range(32) for j in range(32)])
    assert (es.standin_island() == want).all()
    ex, ey = sx[::2], sy[::2]
    half = np.array([(-0.6 + ex[i], -0.6 + ex[i + 1], ey[j], ey[j + 1]) for i in range(16) for j in range(16)])
    assert (es.standin_island(step=2) == half).all()
    assert (es.ISLAND_HALF_X, es.ISLAND_HALF_Y) == (0.075, 0.0625)
    assert "y_k = s_k(0.0625)" in CONTRACT_TEXT and "x_k = −0.6 + s_k(0.075)" in CONTRACT_TEXT


def test_the_stand_in_keeps_the_selected_sizes_and_the_frozen_ground_rules():
    st = es.standin()
    R, ni, nx = st["R_E1_2"], st["n_island"], st["n_excl"]
    assert (len(R), nx, ni, len(st["R_E1_1_half"]), st["sheet_panels"]) == (9995, 6710, 1024, 256, 58116)
    assert (R[:ni] == es.standin_island()).all() and (st["R_E1_1_half"] == es.standin_island(step=2)).all()
    ground = R[ni:]
    side = np.round((ground[:, 1] - ground[:, 0]) * 1000, 6)
    assert int((np.abs(side - 20) < 1e-3).sum()) == 36 and int((np.abs(side - 40) < 1e-3).sum()) == 9
    c = np.stack([(ground[:, 0] + ground[:, 1]) / 2, (ground[:, 2] + ground[:, 3]) / 2], axis=1)
    key = [tuple(v) for v in c]
    assert max(key[:nx - ni]) < min(key[nx - ni:])            # R1 = the last 3,285 by ascending x, then y


def test_the_stand_in_numeric_sets_are_separated_from_the_S1_island_sets():
    st = es.standin()
    sets = es.numeric_sets(st)
    assert es.separation_problems(sets, S1_ISLAND_SETS) == []
    for k, T in sets.items():
        for A in S1_ISLAND_SETS.values():
            assert T.shape != A.shape or T.tobytes() != A.tobytes(), k
    # the aspect-ratio multisets differ, so the island sets are not similar under any allowed map
    assert not np.allclose(es._aspects(sets["E1.1"]), es._aspects(S1_ISLAND_SETS["E1.1"]))


@pytest.mark.parametrize("transform, expect", [
    ("identical", "byte-identical"), ("rows permuted", "similar"), ("translated", "similar"),
    ("scaled and translated", "similar"), ("x and y exchanged", "similar"), ("reflected in x", "similar"),
    ("reflected in y", "similar"), ("revision-8.3 stand-in island", None), ("one panel perturbed by 1e-6", None),
])
def test_the_separation_rule_detects_every_coincidence_and_only_those(transform, expect):
    A = S1_ISLAND_SETS["E1.1"]
    T = {"identical": A.copy(), "rows permuted": A[::-1].copy(),
         "translated": A + np.array([0.3137, 0.3137, -0.011, -0.011]),
         "scaled and translated": A * 1.7 + 0.01, "x and y exchanged": A[:, [2, 3, 0, 1]],
         "reflected in x": np.stack([-A[:, 1], -A[:, 0], A[:, 2], A[:, 3]], 1),
         "reflected in y": np.stack([A[:, 0], A[:, 1], -A[:, 3], -A[:, 2]], 1),
         "revision-8.3 stand-in island": es.standin_island()}.get(transform)
    if T is None:
        T = A.copy()
        T[500, 1] += 1e-6
    bad = es.separation_problems({"T": T}, {"E1.1": A})
    assert (bad == []) if expect is None else (len(bad) == 1 and expect in bad[0]), bad


def test_every_rehearsal_control_set_and_proxy_A_are_separated_from_the_S1_island_sets():
    cs = ec.control_numeric_sets()
    assert len(cs) == 1 + 24 + 10096 + 3
    assert es.separation_problems(cs, S1_ISLAND_SETS) == []
    assert es.separation_problems({"proxy A": es.proxy_a()["R"]}, S1_ISLAND_SETS) == []


def _other_sets():
    """A synthetic family that is not similar to small_sets(): its island's y coordinates are
    scaled by 0.8 (it plays the stand-in against small_sets() playing S1)."""
    o = small_sets()
    R = o["R_E1_2"].copy()
    R[:o["n_island"], 2:] *= 0.8
    H = o["R_E1_1_half"].copy()
    H[:, 2:] *= 0.8
    return {**o, "R_E1_2": R, "R_E1_1_half": H}


@pytest.mark.parametrize("case", ["coinciding stand-in", "no check supplied"])
def test_run_phases_computes_nothing_on_a_stand_in_it_cannot_separate(monkeypatch, sets, case):
    monkeypatch.setattr(dr, "controls_phase", lambda c0: {"failures": []})
    monkeypatch.setattr(dr, "geometry_phase", lambda mesh: {"facts": {}, "failures": [], **sets})
    monkeypatch.setattr(dr, "capacitance_phase", lambda *a, **k: pytest.fail("a stand-in matrix was assembled"))
    check = (lambda geo: es.separation_problems(es.numeric_sets(sets), es.numeric_sets(geo))) \
        if case == "coinciding stand-in" else None
    out = dr.run_phases(lambda n, o: None, mesh={}, c0=nm.derive_c0()["c0"], standin=sets, check_standin=check)
    assert out["outcome"] == "UNQUALIFIED" and out["separation"] and all(p.startswith("separation:") for p in out["problems"])


def _confirmation_gate(monkeypatch, tmp_path, *, usage=None, stand=None, controls_fail=False, geometry=None):
    s1 = small_sets()
    monkeypatch.setattr(es, "standin", lambda: stand if stand is not None else _other_sets())
    monkeypatch.setattr(dr, "preflight_problems", lambda: {"problems": [], "digests": DIG, "baseline": {},
                                                           "probes": {}, "c0": nm.derive_c0()})
    monkeypatch.setattr(dr, "controls_phase",
                        lambda c0: {"failures": ["K3"] if controls_fail else [], "K3": {"pass": not controls_fail}})
    monkeypatch.setattr(dr, "geometry_phase", geometry or (lambda mesh: {"facts": {}, "failures": [], **s1}))
    monkeypatch.setattr(dr, "qmhp_mesh", lambda: {})
    monkeypatch.setattr(dr, "_enforce_budget", lambda: {"synthetic": "no limits in pytest"})
    monkeypatch.setattr(dr, "_budget_enforcement_problems", lambda: [])
    monkeypatch.setattr(dr, "_disarm", lambda: None)
    monkeypatch.setattr(dr, "_SIGNALS", {"stopping": False, "received": []})   # what _enforce_budget resets
    if usage is not None:
        monkeypatch.setattr(dr, "_usage", lambda t0: dict(usage))
    return tmp_path / "evidence"


def test_the_confirmation_refuses_a_stand_in_that_coincides_with_an_S1_set(monkeypatch, tmp_path):
    ev = _confirmation_gate(monkeypatch, tmp_path, stand=small_sets(), usage={"cpu_s": 1.0, "peak_address_space_bytes": 1})
    monkeypatch.setattr(dr, "capacitance_phase", lambda *a, **k: pytest.fail("a stand-in matrix was assembled"))
    r = dr.confirmation(False, ev)
    assert r["confirmation_pass"] is False and r["checks"]["separated_from_s1"] is False
    assert any("byte-identical" in p for p in r["separation_problems"]) and r["paths"] is None


# === anticipated numerical abnormalities are UNQUALIFIED, never FAILED (B-1) ======================

def _wrap_entry_block(monkeypatch, edit):
    real = nm.entry_block

    def wrapped(R, i0, i1, j0, j1, dt, want_b=False):
        S, B = real(R, i0, i1, j0, j1, dt, want_b)
        if dt is LD and want_b and i0 == 0 and j0 == 0:
            edit(S, B)
        return S, B

    monkeypatch.setattr(nm, "entry_block", wrapped)


def _wrap_ld_pass(monkeypatch, **fields):
    real = nm.ld_pass

    def wrapped(R, sigmas, **k):
        p = real(R, sigmas, **k)
        for key, value in fields.items():
            p[key] = [value] * len(sigmas) if key in ("E", "W", "G") else value
        return p

    monkeypatch.setattr(nm, "ld_pass", wrapped)


def _nan_k1_controls(monkeypatch):
    real = nm.entry
    monkeypatch.setattr(nm, "entry", lambda a, b, dt=LD, want_b=False:
                        ((dt(np.nan), dt(np.nan)) if want_b else dt(np.nan)) if a == (0.0, 1.0, 0.0, 1.0)
                        else real(a, b, dt, want_b))

    def controls(c0):
        k = ec.k1()
        return {"K1": k, "failures": [] if k["pass"] else ["K1"]}
    return controls


ABNORMAL = {
    "NaN entry in the long-double pass": lambda mp: _wrap_entry_block(mp, lambda S, B: S.__setitem__((0, 0), np.nan)),
    "infinite entry bound": lambda mp: _wrap_entry_block(mp, lambda S, B: B.__setitem__((0, 0), np.inf)),
    "negative entry bound": lambda mp: _wrap_entry_block(mp, lambda S, B: B.__setitem__((0, 1), -1.0)),
    "E^ exactly zero": lambda mp: _wrap_ld_pass(mp, E=LD(0)),
    "E^ negative": lambda mp: _wrap_ld_pass(mp, E=LD(-1)),
    "W^ negative": lambda mp: _wrap_ld_pass(mp, W=LD(-1e-30)),
    "G^ not finite": lambda mp: _wrap_ld_pass(mp, G=LD(np.inf)),
    "no-underflow requirement fails": lambda mp: _wrap_ld_pass(mp, min_abs_S=LD(2) ** -16350),
    "smallest entry not finite": lambda mp: _wrap_ld_pass(mp, min_abs_S=LD(np.nan)),
    "sigma^T S64 sigma not finite": lambda mp: mp.setattr(nm, "energy64", lambda *a, **k: float("nan")),
    "all-zero sigma (Q = 0)": lambda mp: mp.setattr(nm, "solve_sigma", lambda S, ni, force_fail=0: {
        "sigma": np.zeros(S.shape[0]), "path": "cholesky", "d": np.diag(S).copy(), "Q": Fraction(0),
        "in_place": True, "pivot_ratio_squared": 1.0, "attempts": []}),
    "last-resort sigma invalid": lambda mp: mp.setattr(nm, "solve_sigma", lambda *a, **k: (_ for _ in ()).throw(
        nm.LastResortInvalid("the last-resort sigma has Q <= 0"))),
}


@pytest.mark.parametrize("kind", sorted(ABNORMAL) + ["NaN in control K1"])
def test_an_anticipated_numerical_abnormality_is_unqualified_never_failed(tmp_path, monkeypatch, sets, kind):
    """Contract sections 4.3, 5 and 8: a non-finite or non-positive quantity, a failed requirement
    or an invalid last-resort sigma is UNQUALIFIED - summary.json, no failure.json, no value -
    through the real attempt path, with every raw file already written kept and sealed."""
    if kind == "NaN in control K1":
        _gate(tmp_path, monkeypatch, sets, controls=_nan_k1_controls(monkeypatch))
    else:
        _gate(tmp_path, monkeypatch, sets)
        ABNORMAL[kind](monkeypatch)
    rec = dr.execute()
    names = sorted(p.name for p in rec.iterdir())
    assert "failure.json" not in names and "summary.json" in names, names
    s = _strict_json(rec / "summary.json")
    assert s["outcome"] == "UNQUALIFIED" and s["unqualified_reasons"] and _numbers_fF(s) == []
    assert "internal-sets.json" not in names and manifest.verify(rec) == []
    for p in rec.glob("*.json"):
        _strict_json(p)


def test_non_finite_control_values_fail_the_control_without_raising(monkeypatch):
    with monkeypatch.context() as mp:
        _nan_k1_controls(mp)
        k = ec.k1()
        assert k["pass"] is False and k["rel_long_double"] is None and k["rel_float64"] is None
    pairs = ec.k2b_pairs()[:3]
    with monkeypatch.context() as mp:
        mp.setattr(ec, "k2b_pairs", lambda: pairs)
        mp.setattr(nm, "entry", lambda a, b, dt=LD, want_b=False: (dt(np.nan), dt(np.inf)) if want_b else dt(np.nan))
        r = ec.k2b(nm.derive_c0()["c0"])
        assert r["pass"] is False and r["non_finite_pairs"] == 3 and r["violations_of_B"] == 3
    kf = Fraction(nm.KAPPA_FREE_PQ)
    with monkeypatch.context() as mp:
        mp.setattr(nm, "solve_sigma", lambda *a, **k: (_ for _ in ()).throw(nm.LastResortInvalid("Q <= 0")))
        assert ec.n3(kf, dr.af.EPSILON0)["pass"] is False
        assert ec.certify_single(ec.disk(4), kf)["ok"] is False
        mp.setattr(ec, "disk", lambda n, a=0.1: np.array([(0, 0.01, 0, 0.01), (0.02, 0.03, 0, 0.01)], dtype=float))
        assert ec.k3(kf)["pass"] is False
    with monkeypatch.context() as mp:
        real = nm.assemble64
        mp.setattr(nm, "assemble64", lambda R, *a, **k: real(R, *a, **k) * np.nan)
        assert ec.n3(kf, dr.af.EPSILON0)["pass"] is False
    with monkeypatch.context() as mp:
        _wrap_entry_block(mp, lambda S, B: B.__setitem__((0, 1), -1.0))
        r = ec.certify_single(ec.disk(4), kf)
        assert r["ok"] is False and "C_lo_fF" not in r and r["requirements"]["B_finite_nonnegative"] is False


def test_the_numerics_never_raise_on_non_finite_or_non_positive_values():
    kap = Fraction(nm.KAPPA_LO_PQ)
    assert nm.enclosure(Fraction(1), LD(0), LD(1e-30), LD(1), 512, kap)["ok"] is False
    assert nm.enclosure(Fraction(1), LD(np.nan), LD(0), LD(1), 512, kap)["ok"] is False
    assert nm.underflow_check([np.zeros(4)], LD(1), LD(1))["ok"] is False
    assert nm.underflow_check([np.ones(4)], LD(np.nan), LD(1))["ok"] is False
    assert nm.underflow_check([np.ones(4)], LD(np.inf), LD(np.inf))["ok"] is False
    assert nm.check_g(Fraction(1), 1.0, LD(1), 0.0, kap)["rel"] is None
    assert nm.check_g(Fraction(1), 1.0, LD(0), 1.0, kap)["ok"] is False
    assert nm.pq_or_label(LD(np.nan)).startswith("non-finite") and nm.pq_or_label(LD(0.5)) == "1/2"
    assert nm.finite(None) is False and nm.finite(LD(np.inf)) is False and nm.finite(1.0) is True


# === an accepted approval can never spend the attempt and then lose provenance (C-1, C-3) ==========

def _full_approval(**over):
    now = datetime.now(timezone.utc)
    ap = {k: v for k, v in dr.draft_approval().items() if k not in ("DRAFT", "how_to_grant_it")}
    ap.update(source_commit=dr.git_head(REPO), not_before_utc=(now - timedelta(hours=1)).isoformat(),
              not_after_utc=(now + timedelta(days=6)).isoformat(),
              tolerance_scope_decision="COPIED_NUMBERS_EXCLUDED", q2_within_D5=True)
    ap.update(over)
    return dr._clean(ap)


APPROVAL_VARIANTS = {
    "the full draft, with does_not_authorise": lambda: _full_approval(),
    "without does_not_authorise": lambda: {k: v for k, v in _full_approval().items() if k != "does_not_authorise"},
    "does_not_authorise edited to say GHz": lambda: _full_approval(
        does_not_authorise=_full_approval()["does_not_authorise"] + ["any 5 GHz statement"]),
    "an extra note saying MHz": lambda: _full_approval(note="valid to 5 MHz"),
    "the DRAFT field kept": lambda: _full_approval(DRAFT="NOT AN APPROVAL"),
    "an E_C field": lambda: _full_approval(E_C_F1F1=1.0),
}


@pytest.mark.parametrize("variant", sorted(APPROVAL_VARIANTS))
def test_an_approval_either_refuses_with_nothing_spent_or_the_record_has_its_provenance(tmp_path, monkeypatch, sets,
                                                                                         variant):
    """The property behind C-1: for every approval, with the REAL require_approval and the real
    provenance and ledger rendering, either the run refuses with nothing spent, or the record
    holds provenance.json. The attempt is never spent with its provenance lost to the guard."""
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "require_approval", REAL_REQUIRE_APPROVAL)
    dr.APPROVAL.write_text(json.dumps(APPROVAL_VARIANTS[variant]()))
    try:
        rec = dr.execute()
    except dr.Refusal:
        assert dr.spent_state() == [] and dr.APPROVAL.exists() and not (tmp_path / "results").exists()
        assert variant not in ("the full draft, with does_not_authorise", "without does_not_authorise")
        return
    prov = _strict_json(rec / "provenance.json")
    assert prov["approval"]["q2_within_D5"] is True and manifest.verify(rec) == []
    assert _strict_json(rec / "summary.json")["outcome"] == "QUALIFIED"


@pytest.mark.parametrize("poison", ["argv text", "not JSON-serialisable"])
def test_provenance_the_guard_or_json_would_refuse_refuses_before_spending(tmp_path, monkeypatch, sets, poison):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "require_approval", REAL_REQUIRE_APPROVAL)
    dr.APPROVAL.write_text(json.dumps(_full_approval()))
    if poison == "argv text":
        real = dr.measure_invocation
        monkeypatch.setattr(dr, "measure_invocation", lambda: {**real(), "argv": ["driver.py", "5 MHz"]})
    else:
        monkeypatch.setattr(dr.nm, "longdouble_facts", lambda: {"unserialisable": {1, 2}})
    with pytest.raises(dr.Refusal, match="nothing was spent"):
        dr.execute()
    assert dr.spent_state() == [] and dr.APPROVAL.exists() and not (tmp_path / "results").exists()


def test_the_provenance_is_rendered_and_guarded_before_the_first_ledger_entry():
    tree = ast.parse((HERE / "driver.py").read_text())
    ex = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "execute")
    calls = [(n.lineno, n.func.id) for n in ast.walk(ex) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    render = [ln for ln, f in calls if f == "_render_for_record"]
    create = [ln for ln, f in calls if f == "_create_exclusive"]
    enforce = [ln for ln, f in calls if f == "_budget_enforcement_problems"]
    assert len(render) == 2 and create and enforce and max(render) < min(create) and max(enforce) < min(create)


@pytest.mark.parametrize("failures", [1, 99])
def test_a_provenance_write_that_fails_after_spending_is_recovered_or_declared(tmp_path, monkeypatch, sets, failures):
    """C-3: the failure path writes the in-memory provenance when provenance.json is missing, and
    says so; if it cannot, failure.json says NOT WRITTEN. Either way the record is sealed."""
    _gate(tmp_path, monkeypatch, sets)
    real, left = dr._write_text, [failures]

    def flaky(path, text):
        if path.name == "provenance.json" and left[0] > 0:
            left[0] -= 1
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(dr, "_write_text", flaky)
    with pytest.raises(dr.AttemptFailed, match="disk full"):
        dr.execute()
    (rec,) = (tmp_path / "results").iterdir()
    f = _strict_json(rec / "failure.json")
    assert manifest.verify(rec) == []
    if failures == 1:
        assert f["provenance"] == "provenance.json (written by the failure path)"
        assert _strict_json(rec / "provenance.json")["contract_sha256"] == dr.CONTRACT_SHA256
    else:
        assert f["provenance"].startswith("NOT WRITTEN") and not (rec / "provenance.json").exists()


def test_a_ledger_only_failure_keeps_the_provenance_in_the_ledger_note(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    (tmp_path / "results").write_text("not a directory")
    with pytest.raises(dr.AttemptFailed, match="no record could be created"):
        dr.execute()
    note = _strict_json(dr.common_ledger_path())
    assert note["provenance"]["contract_sha256"] == dr.CONTRACT_SHA256 and note["record_created"] is False


# === stop signals: the failure path survives them and the budget is really enforced (C-2, C-4) =====

@pytest.mark.parametrize("delay_s", [0.02, 0.05, 0.1])
def test_a_stop_signal_pending_when_a_C_level_exception_propagates_still_leaves_a_sealed_record(tmp_path, delay_s):
    """C-2: a stop signal delivered during a C call that then raises a C-level exception is
    pending when the failure path starts. It must be recorded, not raised: exit 3, failure.json,
    provenance.json and a verified manifest. zlib raises zlib.error from C after ~0.5 s."""
    code = _child(tmp_path, f"""
        import signal, zlib
        blob = zlib.compress(bytes(200_000_000), 1)
        bad = blob[:-4] + bytes([(blob[-4] + 1) % 256]) + blob[-3:]
        def boom(mesh):
            signal.setitimer(signal.ITIMER_REAL, {delay_s})
            zlib.decompress(bad)
        dr.geometry_phase = boom
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS}, cwd=str(REPO))
    assert out.returncode == 3, (out.returncode, out.stderr[-1500:])
    (rec,) = (tmp_path / "results").glob(dr.RECORD_PREFIX + "*")
    f = _strict_json(rec / "failure.json")
    assert "incorrect data check" in f["error"] and [e["signal"] for e in f["signals_received"]] == ["SIGALRM"]
    assert (rec / "provenance.json").is_file() and manifest.verify(rec) == []


def test_a_stop_signal_recorded_before_the_attempt_ends_makes_it_FAILED_with_evidence(tmp_path, monkeypatch, sets):
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "_shutdown", lambda: dr._SIGNALS["received"].append({"signal": "SIGXCPU", "at_s": 1.0}))
    with pytest.raises(dr.AttemptFailed, match="SIGXCPU"):
        dr.execute()
    (rec,) = (tmp_path / "results").iterdir()
    assert (rec / "failure.json").is_file() and not (rec / "summary.json").exists() and manifest.verify(rec) == []


def test_stop_signals_blocked_by_the_parent_are_unblocked_and_the_budget_still_raises(tmp_path):
    """C-4: GNU timeout passes the parent's signal mask on. The budget unblocks the stop signals,
    so SIGXCPU raises BudgetExceeded (a FAILED record) instead of ending in the hard kill."""
    import signal as sg
    code = (f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport driver as dr\n"
            "dr.BUDGET = {**dr.BUDGET, 'cpu_soft_s': 1, 'cpu_hard_s': 4}\ndr._enforce_budget()\n"
            "print('PROBLEMS', dr._budget_enforcement_problems(), flush=True)\nwhile True: pass\n")
    block = {sg.SIGALRM, sg.SIGXCPU, sg.SIGTERM, sg.SIGHUP, sg.SIGINT}
    out = subprocess.run(["timeout", "--signal=KILL", "60", sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=90, env={**os.environ, **THREADS}, preexec_fn=lambda: sg.pthread_sigmask(sg.SIG_BLOCK, block))
    assert "PROBLEMS []" in out.stdout and "BudgetExceeded: SIGXCPU" in out.stderr, (out.returncode, out.stderr[-600:])


def test_budget_enforcement_that_cannot_be_verified_refuses_before_spending(tmp_path, monkeypatch, sets):
    out = _python(f"""
        import sys, signal
        sys.path.insert(0, {str(HERE)!r})
        import driver as dr
        dr._enforce_budget()
        signal.pthread_sigmask(signal.SIG_BLOCK, {{signal.SIGTERM}})
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        print(dr._budget_enforcement_problems())
    """)
    assert "stop signals are blocked: ['SIGTERM']" in out.stdout and "SIGHUP" in out.stdout, out.stderr[-500:]
    _gate(tmp_path, monkeypatch, sets)
    monkeypatch.setattr(dr, "_budget_enforcement_problems", lambda: ["stop signals are blocked: ['SIGTERM']"])
    with pytest.raises(dr.Refusal, match="budget enforcement is unavailable"):
        dr.execute()
    assert dr.spent_state() == [] and dr.APPROVAL.exists()


# === the Confirmation fails closed: a missing measurement is a failure (D-2) =======================

@pytest.mark.parametrize("usage, forced, controls_fail, passes", [
    ({"cpu_s": 10.0, "peak_address_space_bytes": 10 ** 9}, False, False, True),
    ({"cpu_s": 10.0, "peak_address_space_bytes": 10 ** 9}, True, False, True),
    ({"cpu_s": 10.0, "peak_address_space_bytes": None}, False, False, False),
    ({"cpu_s": None, "peak_address_space_bytes": 10 ** 9}, False, False, False),
    ({"cpu_s": float("nan"), "peak_address_space_bytes": 10 ** 9}, False, False, False),
    ({"cpu_s": 10.0, "peak_address_space_bytes": float("inf")}, False, False, False),
    ({"cpu_s": 451.0, "peak_address_space_bytes": 10 ** 9}, False, False, False),
    ({"cpu_s": 10.0, "peak_address_space_bytes": 2 * 1024 ** 3 + 1}, False, False, False),
    ({"cpu_s": 10.0, "peak_address_space_bytes": 10 ** 9}, False, True, False),
])
def test_the_confirmation_fails_closed(monkeypatch, tmp_path, usage, forced, controls_fail, passes):
    ev = _confirmation_gate(monkeypatch, tmp_path, usage=usage, controls_fail=controls_fail)
    r = dr.confirmation(forced, ev)
    assert r["confirmation_pass"] is passes, r["checks"]
    assert r["cpu_within_limit"] is (usage["cpu_s"] is not None and usage["cpu_s"] == usage["cpu_s"]
                                     and usage["cpu_s"] <= 450)
    if passes:
        assert r["separation_problems"] == [] and r["checks"]["capacitance_phase_ran_on_expected_paths"]
        if forced:
            assert r["paths"]["E1.2"] == r["paths"]["E1.2-excl-R1"] == "last_resort"
    json.dumps(dr._clean(r), allow_nan=False)


def test_a_confirmation_that_raises_or_is_signalled_reports_a_failure_instead_of_crashing(monkeypatch, tmp_path):
    def stop(mesh):
        raise dr.BudgetExceeded("SIGXCPU: a declared budget limit or a termination signal was reached")

    ev = _confirmation_gate(monkeypatch, tmp_path, usage={"cpu_s": 1.0, "peak_address_space_bytes": 1}, geometry=stop)
    r = dr.confirmation(False, ev)
    assert r["confirmation_pass"] is False and "SIGXCPU" in r["error"] and r["checks"]["no_error"] is False


@pytest.mark.parametrize("peak, code", [(10 ** 9, 0), (None, 4)])
def test_the_confirmation_mode_exits_nonzero_unless_it_passes(monkeypatch, tmp_path, capsys, peak, code):
    _confirmation_gate(monkeypatch, tmp_path, usage={"cpu_s": 1.0, "peak_address_space_bytes": peak})
    real = dr.confirmation
    monkeypatch.setattr(dr, "confirmation", lambda forced: real(forced, tmp_path / "ev"))
    assert dr.main(["--confirmation", "nominal", "--out", str(tmp_path / "c.json")]) == code
    assert _strict_json(tmp_path / "c.json")["confirmation_pass"] is (code == 0)


# === geometry =======================================================================================

def test_the_island_nodes_are_the_section_3_1_formula_and_the_frozen_sides():
    for n, q in ((32, 3.5), (32, 1.5), (64, 2.0), (8, 2.0)):
        k = np.arange(-n // 2, n // 2 + 1)
        vec = np.sign(k) * (0.075 - 1e-12) * (1 - (1 - np.abs(k) / (n // 2)) ** q)
        assert (eg.island_nodes(n, q) == vec).all(), (n, q)
    s = np.diff(eg.island_nodes(32, 3.5))
    assert f"{s.min() * 1000:.9f}" == "0.004577637" and f"{s.max() * 1000:.6f}" == "15.164251"
    assert ec.smin() == s.min() and len(eg.island_panels()) == 1024 and len(eg.island_panels(step=2)) == 256
    half = eg.island_panels(step=2)
    assert set(map(tuple, half[:, [0, 1]])) <= {(a, b) for a in eg.island_nodes()[::2] - 0.6 for b in eg.island_nodes()[::2] - 0.6}


def test_the_merge_rule_partitions_every_candidate_once_and_is_nested_in_kappa():
    per = 800
    I0, J0 = -160, -96
    C = np.ones((256, 192), bool)
    C[100:140, 60:100] = False
    C[10:14, :] = False
    parts = {}
    for kap in (0.5, 1.25, 3.0):
        P, _ = eg.merge(C, I0, J0, kap, (32, 16, 8, 4, 2))
        cover = np.zeros_like(C, int)
        for a, a2, b, b2 in P:
            cover[a:a2, b:b2] += 1
            m = a2 - a
            assert b2 - b == m and (I0 + a) % m == 0 and (J0 + b) % m == 0 and m in (1, 2, 4, 8, 16, 32)
        assert (cover == C.astype(int)).all()
        parts[kap] = P
    for coarse, fine in ((0.5, 1.25), (1.25, 3.0)):
        for a, a2, b, b2 in parts[fine]:
            assert any(A <= a and a2 <= A2 and B <= b and b2 <= B2 for A, A2, B, B2 in parts[coarse])


def test_exact_clipping_accepts_a_covered_panel_and_refuses_one_shifted_off_the_metal():
    tri = [(Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)), (Fraction(1), Fraction(1))]
    tri2 = [(Fraction(0), Fraction(0)), (Fraction(1), Fraction(1)), (Fraction(0), Fraction(1))]
    def area(r):
        return sum((eg.parea(eg.clip(t, *(Fraction(v) for v in r))) for t in (tri, tri2)), Fraction(0))
    r = (0.25, 0.5, 0.25, 0.75)
    assert area(r) == Fraction(0.25) * Fraction(0.5)
    shifted = (0.75, 1.0 + 1e-12, 0.25, 0.5)
    assert area(shifted) < (Fraction(shifted[1]) - Fraction(shifted[0])) * Fraction(0.25)


@pytest.mark.slow
def test_the_rehearsal_runs_the_real_controls_and_the_S1_geometry_phase_and_assembles_nothing_on_S1(monkeypatch):
    """Contract section 5, rehearsal: K1, K2, K2b, K3, N3, N4 with the frozen inputs and seed,
    and the S1 geometry phase on the pinned mesh reproducing section 3.3. The only matrices
    assembled are the synthetic ones of K3 and N3."""
    sizes = []
    real = nm.assemble64
    monkeypatch.setattr(nm, "assemble64", lambda R, *a, **k: (sizes.append(len(R)), real(R, *a, **k))[1])
    real_geo = eg.geometry_phase

    def geo_spy(mesh):
        before = len(sizes)
        out = real_geo(mesh)
        assert len(sizes) == before, "the S1 geometry phase assembled a matrix"
        return out

    monkeypatch.setattr(dr, "geometry_phase", geo_spy)
    r = dr.rehearsal()
    assert r["separation_pass"] and r["separation_problems"] == []
    assert r["controls_pass"] and r["controls"]["failures"] == [], r["controls"]["failures"]
    assert r["geometry_pass"] and r["geometry"]["failures"] == [], r["geometry"]["failures"]
    assert sorted(sizes) == sorted([3080, 732, 256, 256])      # K3 (two disks) and N3 (twice): synthetic only
    f = r["geometry"]["facts"]
    for k, want in eg.EXPECTED.items():
        assert f[k] == want, k
    k2b = r["controls"]["K2b"]
    assert k2b["pairs"] == 10096 and k2b["pair_list_matches_frozen"] and k2b["violations_of_B"] == 0 \
        and k2b["violations_of_c0_bound"] == 0
    assert r["controls"]["N4"]["broken_routine_fails_K2"] and r["controls"]["K2"]["max_rel_ld_vs_quad"] <= 1e-9
    for name in ("N1", "N2", "N3b", "N3c"):
        assert r["geometry"]["controls"][name]["pass"], name
    assert 0.97 <= r["controls"]["K3"]["ratio_to_D"] <= 1 and r["controls"]["N3"]["ratio"] > 10


@pytest.mark.slow
def test_no_confirmation_or_rehearsal_numeric_set_coincides_with_an_S1_attempt_set():
    """Section 3.2 item 2 (revision 8.3): the four S1 attempt sets from the real geometry phase
    (geometry only, no matrix) against every numeric set of the Confirmation (the stand-in's four
    sets), the rehearsal (every control set) and proxy A: none is byte-identical or similar. The
    revision-8.2 stand-in (the S1 island) is the positive control: it coincides."""
    import e1_standin as es
    geo = eg.geometry_phase(dr.qmhp_mesh())
    assert geo["failures"] == []
    s1 = es.numeric_sets(geo)
    stand = es.standin()
    synthetic = {**{f"stand-in {k}": v for k, v in es.numeric_sets(stand).items()},
                 **ec.control_numeric_sets(), "proxy A": es.proxy_a()["R"]}
    assert es.separation_problems(synthetic, s1) == []
    for k, T in synthetic.items():
        for A in s1.values():
            assert T.shape != A.shape or T.tobytes() != A.tobytes(), k
    old = {**stand, "R_E1_2": np.concatenate([eg.island_panels(), stand["R_E1_2"][1024:]]),
           "R_E1_1_half": eg.island_panels(step=2)}
    bad = es.separation_problems({f"8.2 stand-in {k}": v for k, v in es.numeric_sets(old).items()}, s1)
    assert sorted(bad) == ["8.2 stand-in E1.1 is byte-identical to the S1 set E1.1",
                           "8.2 stand-in E1.1-half is byte-identical to the S1 set E1.1-half"]


def test_the_expected_counts_are_the_contract_section_3_3_numbers():
    sec = CONTRACT_TEXT[CONTRACT_TEXT.index("### 3.3 Expected counts"):CONTRACT_TEXT.index("## 4. Numerical")]
    nums = {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", sec)}
    e = eg.EXPECTED
    for k in ("cells_5um", "candidates", "cells_in_r1", "cells_island_full", "cells_no_metal", "ground_panels",
              "ground_on_r1", "ground_excl_r1", "N_E1_2", "N_E1_2_excl_R1", "N_E1_1", "N_E1_1_half", "r1_cut_edges"):
        assert e[k] in nums, k
    assert set(e["ground_by_side_um"].values()) <= nums and set(e["r1_components"]) <= nums
    sec31 = CONTRACT_TEXT[CONTRACT_TEXT.index("### 3.1"):CONTRACT_TEXT.index("### 3.2")]
    assert "283 triangles and 189 nodes" in sec31 and "0.022500000000000003" in sec31
    assert all(repr(abs(v)) in sec31 for v in e["island_bbox"])
    assert (eg.CONFIG["n"], eg.CONFIG["q"], eg.CONFIG["per_mm"], eg.CONFIG["w_mm"], eg.CONFIG["kappa"],
            eg.CONFIG["blocks"]) == (32, 3.5, 800, 0.48, 1.25, (32, 16, 8, 4, 2))


# === the committed pre-approval evidence: produced at 90bf9eb, superseded, kept unchanged ==========

def _evidence(name):
    path = HERE / name
    if not path.exists():
        pytest.fail(f"{name} is missing")
    return _strict_json(path)


@pytest.mark.parametrize("name", sorted(EVIDENCE_90BF9EB))
def test_the_90bf9eb_evidence_is_kept_byte_unchanged_and_is_not_the_current_codes(name):
    """The rehearsal, proxy-A and Confirmation evidence committed at 90bf9eb was produced by that
    code. Its Confirmations ran the stand-in whose island was S1's island (finding D-1), so it is
    superseded; it is kept byte-unchanged (append-only) and is regenerated only after the
    corrected separation has passed review. No current test treats it as the current code's."""
    assert _sha(HERE / name) == EVIDENCE_90BF9EB[name]
    r = _evidence(name)
    assert {k: v for k, v in r["code_sha256"].items() if k in FROZEN_90BF9EB} == \
        {k: v for k, v in FROZEN_90BF9EB.items() if k in r["code_sha256"]}
    current = {n: _sha(p) for n, p in {**dr.CODE_FILES, "e1_standin.py": HERE / "e1_standin.py"}.items()}
    assert any(r["code_sha256"].get(k) != current[k] for k in FROZEN_90BF9EB if k in r["code_sha256"])


def test_the_doc_states_that_the_pre_approval_evidence_is_pending_regeneration():
    doc = (REPO / "docs" / "coupled-candidate" / "e1-s1-lower-bound.md").read_text()
    assert "PENDING REGENERATION" in doc and "90bf9eb" in doc and "unintended pre-execution computation" in doc
    assert "no S1 Galerkin matrix has been assembled or factorised, and no S1\nenergy has been formed" not in doc


@pytest.mark.skipif(os.environ.get("E1_RUN_CONFIRMATION") != "1",
                    reason="the ~5-minute Confirmation runs re-run only with E1_RUN_CONFIRMATION=1, and not before "
                           "the corrected stand-in separation has passed review")
@pytest.mark.parametrize("mode", ["nominal", "forced"])
def test_the_confirmation_re_runs_within_the_limits(mode, tmp_path):
    out = subprocess.run(["timeout", "--signal=KILL", "1260", sys.executable, "experiments/e1-s1-lower-bound/driver.py",
                          "--confirmation", mode, "--out", str(tmp_path / "c.json")], cwd=str(REPO),
                         capture_output=True, text=True, timeout=1300, env={**os.environ, **THREADS})
    assert out.returncode == 0, out.stderr[-1500:]
    r = _strict_json(tmp_path / "c.json")
    assert r["confirmation_pass"] is True and all(r["checks"].values()) and r["separation_problems"] == []
    assert r["resources"]["cpu_s"] <= 450 and r["resources"]["peak_address_space_bytes"] <= 2 * 1024 ** 3
