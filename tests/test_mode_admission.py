"""Mode admission, row correspondence and cross-run matching.

These are the regression tests for the corrective analysis of
``COUPLED-PILOT-20260916T035733Z``. They cover the two defects the pilot's own
analysis had — selecting a mode by smallest ``|p|``, and comparing signed
participations between independent solves — plus the joins and refusals that
prevent them recurring.

Synthetic fixtures exercise the rules; the real record is used where the point
is that the rule behaves correctly on the evidence that exposed the defect.
Nothing here launches a solver, and nothing writes inside the record.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import manifest
from solvers.palace.coupled_config import COUPLED_SOLVER_RULES
from solvers.palace.mode_admission import (
    ADMISSION_RULE,
    COMPARISON_CONVENTION,
    MATCHING_RULE,
    ModeRecord,
    ModeTableMismatch,
    admit_modes,
    check_row_correspondence,
    join_modes_by_id,
    label_roles,
    match_runs,
    unique_field_dominated,
)
from solvers.palace.outputs import parse_port_phasor_csv

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "results" / "COUPLED-PILOT-20260916T035733Z"
PORT_L_H = 1.0345665367517793e-07
BACKWARD_TOLERANCE = COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"]

#: Palace writes the four ``domain-E.csv`` columns headed "(J)" in units of
#: 1e9 joules: the energy dimensionalisation factor collapses to the
#: characteristic time, which Palace carries in nanoseconds. Recorded as a
#: constant because a test asserts it against the record rather than assuming
#: the header is right.
ENERGY_SCALE_TO_SI = 1.0e-9


# --- synthetic fixtures -----------------------------------------------------


def _write_postpro(
    root: Path,
    rows: list[dict[str, float]],
    *,
    eig_order: list[int] | None = None,
    drop_from_epr: int | None = None,
) -> Path:
    """Write a five-file Palace postpro directory from explicit per-mode rows.

    ``eig_order`` writes ``eig.csv``'s rows in a different order from the other
    files, which is what a positional join cannot survive.
    """
    root.mkdir(parents=True, exist_ok=True)
    by_mode = {int(r["m"]): r for r in rows}
    order = eig_order if eig_order is not None else sorted(by_mode)

    eig = ["               m,             Re{f} (GHz),             Im{f} (GHz),                       Q,           Error (Bkwd.),            Error (Abs.)"]
    for m in order:
        r = by_mode[m]
        eig.append(f" {float(m):.9e}, {r['f']:+.9e}, {0.0:+.9e}, {1.0e8:+.9e}, {r.get('bkwd', 1e-12):+.9e}, {1e-6:+.9e}")
    (root / "eig.csv").write_text("\n".join(eig) + "\n")

    dom = ["               m,              E_elec (J),               E_mag (J),               E_cap (J),               E_ind (J)"]
    for m in sorted(by_mode):
        r = by_mode[m]
        dom.append(f" {float(m):.9e}, {r['E_elec']:+.9e}, {r['E_mag']:+.9e}, {0.0:+.9e}, {r['E_ind']:+.9e}")
    (root / "domain-E.csv").write_text("\n".join(dom) + "\n")

    epr = ["               m,                    p[1]"]
    for m in sorted(by_mode):
        if m == drop_from_epr:
            continue
        r = by_mode[m]
        epr.append(f" {float(m):.9e}, {r['p']:+.9e}")
    (root / "port-EPR.csv").write_text("\n".join(epr) + "\n")

    cur = ["               m,            Re{I[1]} (A),            Im{I[1]} (A)"]
    volt = ["               m,            Re{V[1]} (V),            Im{V[1]} (V)"]
    for m in sorted(by_mode):
        r = by_mode[m]
        # I chosen so that 0.5 L |I|^2 * 1e9 == E_ind, with the phase free.
        magnitude = math.sqrt(2.0 * r["E_ind"] * ENERGY_SCALE_TO_SI / PORT_L_H)
        phase = r.get("phase_rad", 0.3)
        current = complex(magnitude * math.cos(phase), magnitude * math.sin(phase))
        omega = 2.0 * math.pi * r["f"] * 1e9
        voltage = 1j * omega * PORT_L_H * current
        cur.append(f" {float(m):.9e}, {current.real:+.9e}, {current.imag:+.9e}")
        volt.append(f" {float(m):.9e}, {voltage.real:+.9e}, {voltage.imag:+.9e}")
    (root / "port-I.csv").write_text("\n".join(cur) + "\n")
    (root / "port-V.csv").write_text("\n".join(volt) + "\n")
    return root


def _row(m: int, f: float, *, balanced: bool, p: float, bkwd: float = 1e-12, phase: float = 0.3) -> dict[str, float]:
    """One synthetic mode. ``p`` is the signed participation that must result."""
    electric = 6.671281904e-03
    inductive = abs(p) * electric
    magnetic = (electric - inductive) if balanced else (electric * 2.0e-5 - inductive)
    return {
        "m": float(m),
        "f": f,
        "E_elec": electric,
        "E_mag": magnetic,
        "E_ind": inductive,
        "p": p,
        "bkwd": bkwd,
        "phase_rad": phase if p >= 0 else phase + math.pi,
    }


def _records(rows: list[dict[str, float]], tmp_path: Path, name: str) -> list[ModeRecord]:
    return join_modes_by_id(_write_postpro(tmp_path / name, rows))


# --- the join ---------------------------------------------------------------


def test_the_join_is_by_mode_id_not_by_row_position(tmp_path):
    """eig.csv written in a different row order still joins correctly."""
    rows = [
        _row(1, 1.70, balanced=True, p=0.998),
        _row(2, 4.18, balanced=True, p=1.2e-3),
        _row(3, 8.84, balanced=False, p=-1.2e-7),
    ]
    shuffled = join_modes_by_id(_write_postpro(tmp_path / "shuffled", rows, eig_order=[3, 1, 2]))
    straight = join_modes_by_id(_write_postpro(tmp_path / "straight", rows))
    assert [r.mode for r in shuffled] == [1, 2, 3]
    for a, b in zip(shuffled, straight):
        assert a.frequency_GHz == pytest.approx(b.frequency_GHz)
        assert a.inductive_J == pytest.approx(b.inductive_J)
    # The mode at 8.84 GHz carries the 8.84 GHz energies, not the first row's.
    assert shuffled[2].frequency_GHz == pytest.approx(8.84)
    assert shuffled[2].energy_balance_defect > 0.9


def test_the_join_refuses_when_a_table_is_missing_a_mode(tmp_path):
    rows = [_row(1, 1.70, balanced=True, p=0.998), _row(2, 4.18, balanced=True, p=1.2e-3)]
    postpro = _write_postpro(tmp_path / "gap", rows, drop_from_epr=2)
    with pytest.raises(ModeTableMismatch) as excinfo:
        join_modes_by_id(postpro)
    assert "disagree about which modes exist" in str(excinfo.value)


def test_row_correspondence_catches_a_shifted_table(tmp_path):
    """Rolling one file by a row must break the identities, not pass quietly."""
    rows = [
        _row(1, 1.70, balanced=True, p=0.998),
        _row(2, 4.18, balanced=True, p=1.2e-3),
        _row(3, 8.84, balanced=True, p=5.0e-4),
    ]
    postpro = _write_postpro(tmp_path / "rolled", rows)
    good = check_row_correspondence(join_modes_by_id(postpro), {1: PORT_L_H})
    assert good.ok

    lines = (postpro / "port-I.csv").read_text().splitlines()
    rolled = [lines[0], lines[2], lines[3], lines[1]]
    # Keep the mode column truthful; only the data moves, as a slip would.
    fixed = [rolled[0]]
    for i, line in enumerate(rolled[1:], start=1):
        fixed.append(f" {float(i):.9e}," + line.split(",", 1)[1])
    (postpro / "port-I.csv").write_text("\n".join(fixed) + "\n")

    bad = check_row_correspondence(join_modes_by_id(postpro), {1: PORT_L_H})
    assert not bad.ok
    assert bad.max_port_impedance_mismatch > 0.1


# --- admission --------------------------------------------------------------


def test_admission_does_not_use_participation_rank(tmp_path):
    """The smallest |p| mode is admitted; a large |p| mode is rejected."""
    rows = [
        _row(1, 1.70, balanced=False, p=0.5),     # large |p|, unbalanced
        _row(2, 4.18, balanced=True, p=1.0e-6),   # smallest |p|, balanced
    ]
    report = admit_modes("synthetic", _records(rows, tmp_path, "rank"), backward_error_tolerance=BACKWARD_TOLERANCE)
    dispositions = {m.record.mode: m.disposition for m in report.modes}
    assert dispositions == {1: "REJECTED_ENERGY_BALANCE", 2: "ADMITTED"}


def test_admission_does_not_hard_code_mode_indices(tmp_path):
    """Modes 1 and 2 rejected, mode 3 admitted."""
    rows = [
        _row(1, 1.70, balanced=False, p=1.0e-7),
        _row(2, 4.18, balanced=False, p=2.0e-7),
        _row(3, 8.84, balanced=True, p=3.0e-3),
    ]
    report = admit_modes("synthetic", _records(rows, tmp_path, "index"), backward_error_tolerance=BACKWARD_TOLERANCE)
    assert [r.mode for r in report.admitted] == [3]


def test_algebraic_convergence_is_a_separate_disposition(tmp_path):
    """A balanced mode that did not converge is rejected for that reason."""
    rows = [_row(1, 1.70, balanced=True, p=0.998, bkwd=1.0e-3)]
    report = admit_modes("synthetic", _records(rows, tmp_path, "converge"), backward_error_tolerance=BACKWARD_TOLERANCE)
    entry = report.modes[0]
    assert entry.disposition == "REJECTED_NOT_CONVERGED"
    assert entry.balanced is True and entry.converged is False


def test_the_admission_threshold_is_not_silently_editable():
    """The rule's threshold and its declared status are part of the record."""
    assert ADMISSION_RULE["max_energy_balance_defect"] == 1.0e-3
    assert "retrospective" in ADMISSION_RULE["status"]
    assert "prospective" in ADMISSION_RULE["status"]
    assert "retrospective" in MATCHING_RULE["status"]
    assert "prospective" in MATCHING_RULE["status"]


# --- matching ---------------------------------------------------------------


def _two(tmp_path, name, rows):
    report = admit_modes(name, _records(rows, tmp_path, name), backward_error_tolerance=BACKWARD_TOLERANCE)
    return report.admitted


def test_matching_refuses_on_a_count_mismatch(tmp_path):
    a = _two(tmp_path, "a1", [_row(1, 1.70, balanced=True, p=0.99), _row(2, 4.18, balanced=True, p=1e-3)])
    b = _two(tmp_path, "b1", [_row(1, 1.71, balanced=True, p=0.99)])
    report = match_runs("a vs b", a, b)
    assert report.status == "COUNT_MISMATCH"
    assert report.pairs == []
    assert not report.comparable


def test_matching_refuses_when_the_two_orderings_disagree(tmp_path):
    """Frequency order says 1↔1, |p| order says 1↔2: no comparison."""
    a = _two(tmp_path, "a2", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 4.18, balanced=True, p=1e-3)])
    b = _two(tmp_path, "b2", [_row(1, 1.71, balanced=True, p=1e-3), _row(2, 4.19, balanced=True, p=0.9)])
    report = match_runs("a vs b", a, b)
    assert report.status == "ORDERING_DISAGREEMENT"
    assert report.pairs == []


def test_matching_refuses_when_a_swap_cannot_be_excluded(tmp_path):
    """A shift comparable with the mode spacing is not a match."""
    a = _two(tmp_path, "a3", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 2.10, balanced=True, p=1e-3)])
    b = _two(tmp_path, "b3", [_row(1, 2.05, balanced=True, p=0.9), _row(2, 2.40, balanced=True, p=1e-3)])
    report = match_runs("a vs b", a, b)
    assert report.status == "SEPARATION_GUARD"
    assert report.pairs == []


def test_matching_compares_magnitudes_not_signs(tmp_path):
    """Two runs whose participations differ only in sign agree exactly."""
    a = _two(tmp_path, "a4", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 4.18, balanced=True, p=+1.0e-3)])
    b = _two(tmp_path, "b4", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 4.18, balanced=True, p=-1.0e-3)])
    report = match_runs("a vs b", a, b)
    assert report.status == "MATCHED"
    pair = report.pairs[1]
    assert pair.delta_abs_participation_relative[1] == pytest.approx(0.0, abs=1e-12)
    # The signed difference a naive comparison would have produced.
    signed = abs(pair.a.signed_participation() - pair.b.signed_participation()) / max(
        abs(pair.a.signed_participation()), abs(pair.b.signed_participation())
    )
    assert signed == pytest.approx(2.0, rel=1e-9)
    assert "MAGNITUDES" in COMPARISON_CONVENTION["delta_p"]


def test_the_signed_participation_and_complex_current_are_preserved(tmp_path):
    a = _two(tmp_path, "a5", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 4.18, balanced=True, p=+1.0e-3)])
    b = _two(tmp_path, "b5", [_row(1, 1.70, balanced=True, p=0.9), _row(2, 4.18, balanced=True, p=-1.0e-3)])
    payload = match_runs("a vs b", a, b).as_dict()
    preserved = payload["pairs"][1]["signed_participation_preserved"]
    assert preserved["a"][1] > 0 and preserved["b"][1] < 0
    mode = a[1].as_dict()
    assert set(mode["current_A"][1]) == {"re", "im", "abs"}
    assert mode["participation_signed"][1] == pytest.approx(1.0e-3)


def test_a_second_field_dominated_mode_makes_the_criterion_subject_ambiguous(tmp_path):
    admitted = _two(
        tmp_path,
        "roles",
        [
            _row(1, 1.70, balanced=True, p=0.9),
            _row(2, 4.18, balanced=True, p=1.0e-3),
            _row(3, 8.40, balanced=True, p=2.0e-5),
        ],
    )
    labels = [r.label for r in label_roles(admitted)]
    assert labels == ["LUMPED_DOMINATED", "FIELD_DOMINATED", "FIELD_DOMINATED"]
    assert unique_field_dominated(admitted) is None
    assert unique_field_dominated(admitted[:2]) is not None


# --- against the preserved record -------------------------------------------


@pytest.fixture(scope="module")
def record_reports():
    if not RECORD.is_dir():
        pytest.skip(f"{RECORD} is not present")
    reports = {}
    for run in ("P1", "P2", "P3"):
        modes = join_modes_by_id(RECORD / run / "solver" / "postpro")
        reports[run] = admit_modes(
            run,
            modes,
            backward_error_tolerance=BACKWARD_TOLERANCE,
            row_correspondence=check_row_correspondence(modes, {1: PORT_L_H}),
        )
    return reports


def test_the_record_row_correspondence_holds(record_reports):
    for run, report in record_reports.items():
        correspondence = report.row_correspondence
        assert correspondence.ok, f"{run}: {correspondence}"
        assert correspondence.max_participation_energy_mismatch < 1e-8
        assert correspondence.max_port_impedance_mismatch < 1e-8


def test_the_record_energies_are_scaled_by_1e9_not_si_joules(record_reports):
    """``domain-E.csv`` is headed "(J)" but carries 1e9 times the SI value."""
    worst = 0.0
    for report in record_reports.values():
        for entry in report.modes:
            record = entry.record
            si = 0.5 * PORT_L_H * abs(record.current_A[1]) ** 2
            predicted = si / ENERGY_SCALE_TO_SI
            worst = max(worst, abs(record.inductive_J - predicted) / predicted)
    assert worst < 1e-8, f"E_ind is not 1e9 * 0.5 L |I|^2 (worst {worst:.3e})"


def test_the_record_admits_a_mode_that_is_neither_one_nor_two(record_reports):
    """P2's admitted set includes mode 9, above six rejected rows."""
    admitted = [r.mode for r in record_reports["P2"].admitted]
    assert admitted == [1, 2, 9]
    rejected = [m.record.mode for m in record_reports["P2"].rejected]
    assert rejected == [3, 4, 5, 6, 7, 8]


def test_the_two_populations_are_well_separated_in_the_record(record_reports):
    for run, report in record_reports.items():
        separation = report.separation_decades
        assert separation is not None and separation > 4.0, f"{run}: {separation}"


def test_every_record_mode_converged_but_most_are_not_admitted(record_reports):
    """Algebraic convergence and mode validity are genuinely different questions."""
    for run, report in record_reports.items():
        assert all(m.converged for m in report.modes), run
    assert sum(len(r.admitted) for r in record_reports.values()) == 7
    assert sum(len(r.modes) for r in record_reports.values()) == 23


def test_the_smallest_absolute_participation_rule_would_pick_a_rejected_row(record_reports):
    """The defect this corrects, asserted against the record that exposed it."""
    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    for run in ("P1", "P3"):
        report = record_reports[run]
        in_window = [m for m in report.modes if m.record.in_window(floor, ceiling)]
        picked = min(in_window, key=lambda m: m.record.abs_participation())
        assert picked.disposition == "REJECTED_ENERGY_BALANCE", (
            f"{run}: smallest |p| selected mode {picked.record.mode}, which this rule admits"
        )
        assert picked.record.mode not in [r.mode for r in report.admitted]


def test_the_record_comparisons_match_and_still_fail_the_frozen_frequency_check(record_reports):
    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    windows = {run: r.admitted_in_window(floor, ceiling) for run, r in record_reports.items()}
    for label, (a, b) in {"order": ("P1", "P2"), "halo": ("P1", "P3")}.items():
        report = match_runs(label, windows[a], windows[b])
        assert report.status == "MATCHED", f"{label}: {report.reason}"
        assert len(report.pairs) == 2
        # The frozen frequency tolerance is 1e-4; every pair exceeds it.
        assert all(p.delta_f_relative > 1e-4 for p in report.pairs)


# --- the frozen tolerances and the preserved source -------------------------


def test_the_frozen_criteria_are_unchanged_in_both_places():
    approval = json.loads((REPO_ROOT / ".github" / "pilot-approval.json").read_text())["frozen_criteria"]
    assert approval["max_relative_participation_change"] == 1.0e-2
    assert approval["max_relative_frequency_change"] == 1.0e-4
    driver = (REPO_ROOT / "scripts" / "palace_coupled_pilot.py").read_text()
    assert '"max_relative_participation_change": 1.0e-2' in driver
    assert '"max_relative_frequency_change": 1.0e-4' in driver


@pytest.mark.skipif(not RECORD.is_dir(), reason="the pilot record is not present")
def test_the_corrective_analysis_does_not_touch_the_source_record():
    before = manifest.verify(RECORD)
    assert before == [], before
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "coupled_pilot_corrective.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert "NOT-A-HALO-VERDICT" in result.stdout
    assert manifest.verify(RECORD) == [], "the corrective analysis modified the source record"


@pytest.mark.skipif(not RECORD.is_dir(), reason="the pilot record is not present")
def test_the_source_record_report_and_summary_are_untouched():
    """The pilot's own report and summary stay exactly as executed."""
    recorded = {}
    for line in (RECORD / "manifest.sha256").read_text().splitlines():
        if line.strip():
            digest, _, rel = line.partition("  ")
            recorded[rel.strip()] = digest.strip()
    for name in ("report.md", "summary.json"):
        assert manifest.file_digest(RECORD / name) == recorded[name]
    summary = json.loads((RECORD / "summary.json").read_text())
    # The superseded verdict is preserved verbatim, not rewritten.
    assert summary["halo_verdict"]["verdict"] == "NOT-A-HALO-VERDICT"
    assert summary["halo_verdict"]["delta_p_relative"] == pytest.approx(1.6477708822867019)


def test_the_phasor_parser_keeps_the_phase(tmp_path):
    path = tmp_path / "port-I.csv"
    path.write_text(
        "               m,            Re{I[1]} (A),            Im{I[1]} (A)\n"
        " 1.000000000e+00,       +1.000000000e-03,       -2.000000000e-03\n"
    )
    rows = parse_port_phasor_csv(path, "I")
    assert rows[0].mode == 1
    assert rows[0].phasor[1] == complex(1.0e-3, -2.0e-3)


# --- the corrected statements stay corrected --------------------------------

#: Statements withdrawn by the corrective analysis. Matched against the
#: document with blockquotes and REGISTERED citations removed, so a correction
#: that names the wording it withdraws does not trip the guard, while any other
#: appearance of that wording does.
WITHDRAWN_CLAIMS = [
    # A mechanism asserted where only a correlation was observed.
    r"null-space\s*/\s*gradient artefacts that the divergence-free projection did not\s*remove",
    # A rule by mode index.
    r"Only mode 1 and mode 2 of each solve are physical circuit modes",
    r"##\s*2\.\s*Only two modes in the window are physical",
    # A solver gauge artefact described as physics.
    r"the current direction through the port\s*is not stable under discretisation",
    r"needs a sign convention that survives\s*discretisation",
]

GUARDED_DOCS = [
    REPO_ROOT / "docs" / "coupled-candidate" / "pilot-outcome.md",
    REPO_ROOT / "docs" / "coupled-candidate" / "corrective-analysis.md",
]

#: The ONLY quotations exempt from the guard, named one by one.
#:
#: A correction has to be able to quote the wording it withdraws, but exempting
#: italic text in general would exempt a great deal more than that: any future
#: claim could be slipped past the guard by italicising it. So the exemption is
#: a closed registry — document basename to the exact flattened strings it may
#: contain — and it applies only where the string appears wrapped as ``*"..."*``
#: AND the document also states that it is withdrawn or superseded. Everything
#: else, italic or not, is the document speaking in its own voice.
CITATION_EXEMPTIONS: dict[str, tuple[str, ...]] = {
    "pilot-outcome.md": (
        "Only mode 1 and mode 2 of each solve are physical circuit modes",
        "the current direction through the port is not stable under discretisation",
        "needs a sign convention that survives discretisation",
        "null-space / gradient artefacts that the divergence-free projection did not remove",
    ),
    "corrective-analysis.md": (
        "Only mode 1 and mode 2 of each solve are physical circuit modes.",
        # The document quotes this twice, once mid-sentence and once in the
        # corrections table where it ends the sentence. Both spellings are
        # registered explicitly; near-duplicates are the price of exactness.
        "null-space / gradient artefacts that the divergence-free projection did not remove",
        "null-space / gradient artefacts that the divergence-free projection did not remove.",
        "the current direction through the port is not stable under discretisation",
        "bit-for-bit",
    ),
}

#: A document may quote a withdrawn claim only if it says so.
WITHDRAWAL_MARKERS = ("withdrawn", "superseded", "was wrong", "no longer")


def _flatten(text: str) -> str:
    """Drop blockquoted citations, then collapse whitespace."""
    kept = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return re.sub(r"\s+", " ", "\n".join(kept))


def _assertions_only(text: str, exemptions: tuple[str, ...] = ()) -> str:
    """The document speaking in its own voice.

    Removes blockquotes, and then each REGISTERED citation, but only where it
    appears wrapped as ``*"..."*``. An unregistered quotation is left in place,
    so italicising a claim does not hide it from the guard.
    """
    body = _flatten(text)
    for claim in exemptions:
        body = body.replace(f'*"{claim}"*', " ")
    return body


@pytest.mark.parametrize("path", GUARDED_DOCS, ids=lambda p: p.name)
def test_no_document_repeats_a_withdrawn_claim(path):
    """The guard proper: a withdrawn claim may be quoted, never asserted."""
    if not path.exists():
        pytest.skip(f"{path.name} is not present")
    text = _assertions_only(
        path.read_text(encoding="utf-8"), CITATION_EXEMPTIONS.get(path.name, ())
    )
    for pattern in WITHDRAWN_CLAIMS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        assert match is None, f"{path.name} repeats a withdrawn claim: {match.group(0)[:120]!r}"


def test_the_guard_covers_every_document_that_should_be_guarded():
    """A guard nobody runs is not a guard. Both documents must exist and be read."""
    assert len(GUARDED_DOCS) == 2
    for path in GUARDED_DOCS:
        assert path.exists(), f"{path} is guarded but missing, so the guard skips it"


def test_the_withdrawn_quotations_are_still_present_to_be_withdrawn():
    """The corrections name what they withdraw; they do not quietly delete it."""
    text = (REPO_ROOT / "docs" / "coupled-candidate" / "pilot-outcome.md").read_text(encoding="utf-8")
    assert "is withdrawn" in text
    assert "null-space / gradient artefacts" in text  # named, inside a registered citation
    assert "Only mode 1 and mode 2 of each solve are physical" in text


@pytest.mark.parametrize("path", GUARDED_DOCS, ids=lambda p: p.name)
def test_every_registered_citation_is_used_and_is_actually_withdrawn(path):
    """No dead registry entries, and no quoting without withdrawing."""
    if not path.exists():
        pytest.skip(f"{path.name} is not present")
    flat = _flatten(path.read_text(encoding="utf-8"))
    lowered = flat.lower()
    for claim in CITATION_EXEMPTIONS.get(path.name, ()):
        assert f'*"{claim}"*' in flat, (
            f"{path.name}: the registry exempts {claim!r} but the document does not quote it; "
            f"a dead exemption is a hole waiting to open"
        )
    if CITATION_EXEMPTIONS.get(path.name):
        assert any(marker in lowered for marker in WITHDRAWAL_MARKERS), (
            f"{path.name} quotes a withdrawn claim but never says it is withdrawn"
        )


def test_the_registry_names_only_documents_the_guard_covers():
    covered = {p.name for p in GUARDED_DOCS}
    assert set(CITATION_EXEMPTIONS) <= covered


def test_the_exemption_is_not_a_general_licence_to_italicise():
    """An UNREGISTERED claim in italic quotes is still caught."""
    registered = "the current direction through the port is not stable under discretisation"
    unregistered = "Only mode 1 and mode 2 of each solve are physical circuit modes"
    exemptions = (registered,)

    assert registered not in _assertions_only(f'As noted, *"{registered}"*, now withdrawn.\n', exemptions)
    # Same shape, same italics — but not in the registry, so it survives.
    assert unregistered in _assertions_only(f'As noted, *"{unregistered}"*, now withdrawn.\n', exemptions)
    # A registered claim asserted bare is not a citation and is not exempt.
    assert registered in _assertions_only(f"{registered}, as the pilot showed.\n", exemptions)
    # Blockquoted citations remain exempt, as before.
    assert registered not in _assertions_only(f"> {registered}\n", ())


def test_the_exemption_removes_only_the_quoted_span():
    claim = "the current direction through the port is not stable under discretisation"
    text = f'Before. *"{claim}"* After.\n'
    cleaned = _assertions_only(text, (claim,))
    assert "Before." in cleaned and "After." in cleaned
    assert claim not in cleaned
    # An unterminated italic quotation must not swallow the rest of the file.
    assert claim in _assertions_only(f'*"a stray open quote\n\n{claim}\n', (claim,))


def test_the_driver_no_longer_selects_a_mode_by_smallest_participation():
    driver = (REPO_ROOT / "scripts" / "palace_coupled_pilot.py").read_text()
    assert "_readout_like_mode" not in driver
    assert "_fluxonium_like_mode" not in driver
    assert "from solvers.palace.mode_admission import" in driver
    assert "join_modes_by_id" in driver
    assert "match_runs" in driver


def test_the_driver_records_energy_balance_keyed_by_mode_not_positionally():
    driver = (REPO_ROOT / "scripts" / "palace_coupled_pilot.py").read_text()
    assert "energy_balance_by_mode" in driver
    assert "entry[\"equipartition_residuals\"] = [" not in driver




def test_the_documents_state_the_same_counts_the_code_computes(record_reports):
    """Prose drifts; this ties the two documents to the computed split."""
    admitted = sum(len(r.admitted) for r in record_reports.values())
    rejected = sum(len(r.rejected) for r in record_reports.values())
    assert (admitted, rejected) == (7, 16)

    words = {7: "Seven", 16: "sixteen"}
    corrective = (REPO_ROOT / "docs" / "coupled-candidate" / "corrective-analysis.md").read_text()
    assert f"{words[admitted]} rows lie at or below" in corrective
    assert f"other {words[rejected]} lie at or above" in corrective
    assert f"**{rejected} of the 23 converged rows fail" in corrective

    outcome = (REPO_ROOT / "docs" / "coupled-candidate" / "pilot-outcome.md").read_text()
    assert f"{admitted} rows have `|R − 1| ≤" in outcome
    assert f"the other {rejected} have" in outcome


def test_the_backward_error_is_normalised_by_a_global_operator_norm(record_reports):
    """Error(Abs.)/Error(Bkwd.) is a per-run constant, not a per-mode quantity.

    That is what makes the printed backward error a weaker certificate than its
    size suggests: it is the true residual divided by a number of order 1e5.
    """
    for run, report in record_reports.items():
        ratios = [
            m.record.absolute_error / m.record.backward_error
            for m in report.modes
            if m.record.absolute_error and m.record.backward_error
        ]
        assert len(ratios) == len(report.modes), run
        spread = max(ratios) / min(ratios) - 1.0
        assert spread < 1e-4, f"{run}: ratio is not constant ({spread:.3e})"
        assert 1e4 < min(ratios) < 1e6, f"{run}: {min(ratios):.3e}"


def test_the_failing_rows_form_one_family_by_their_stiffness_proxy(record_reports):
    """(E_mag + E_ind)*f^2 clusters for rejected rows and does not for admitted."""
    rejected, admitted = [], []
    for report in record_reports.values():
        for entry in report.modes:
            value = entry.record.magnetic_side_J * entry.record.frequency_GHz ** 2
            (admitted if entry.disposition == "ADMITTED" else rejected).append(value)
    assert len(rejected) == 16 and len(admitted) == 7
    assert max(rejected) / min(rejected) < 6.0
    assert min(admitted) / max(rejected) > 100.0


def test_the_documents_reference_a_corrective_record_that_exists():
    """A document that cites a record by name must cite one that is there."""
    import re

    referenced = set()
    for name in ("corrective-analysis.md", "pilot-outcome.md"):
        text = (REPO_ROOT / "docs" / "coupled-candidate" / name).read_text()
        referenced.update(re.findall(r"COUPLED-PILOT-CORR-[0-9TZ]+", text))
    assert referenced, "no corrective record is referenced by either document"
    for record in sorted(referenced):
        directory = REPO_ROOT / "results" / record
        assert directory.is_dir(), f"{record} is referenced but not present"
        assert manifest.verify(directory) == [], record
        payload = json.loads((directory / "corrective_analysis.json").read_text())
        assert payload["schema"] == "qmhp-cem.corrective-analysis/0.1.0"
        assert payload["source_record"]["record"] == RECORD.name
        assert payload["environment"]["solver_launched"] is False
        # The source record's digests are carried, not just its name.
        assert payload["source_record"]["file_count"] == 35
        assert payload["halo_disposition"]["verdict"] == "NOT-A-HALO-VERDICT"
