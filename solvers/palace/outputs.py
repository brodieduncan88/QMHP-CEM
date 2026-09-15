"""Parsers for what Palace writes.

Palace's eigenmode post-processing writes, under ``Problem.Output``:

* ``eig.csv`` — one row per computed mode: index, Re{f}, Im{f}, Q, and the
  eigensolver's backward error (and, in recent releases, an absolute error).
  The backward error is the solver's own convergence measure and is what the
  ``SolverResults.convergence`` block reports. Nothing here invents one.
* ``domain-E.csv`` — per-mode field energies (hashed as an artifact, not
  interpreted in this milestone).
* ``palace.json`` — run metadata including the Palace git tag and MPI size,
  where the release writes it.

The solver also prints a banner to stdout carrying its git changeset ID (the
output of ``git describe``, so ``v0.13.0`` for a release-tag build) and the
MPI process count; the adapter captures stdout to ``palace_log.txt`` and this
module extracts those fields.

Every parser here is header-driven and tolerant of column order and padding,
so a release that reorders or adds a column does not break it. A release that
removes the backward-error column does break it, deliberately: without that
column there is no genuine convergence figure to report.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PalaceOutputError(RuntimeError):
    """Palace output was missing or not in the expected form."""


@dataclass(frozen=True)
class EigenmodeRow:
    index: int
    frequency_re_GHz: float
    frequency_im_GHz: float
    quality_factor: float | None
    backward_error: float
    absolute_error: float | None


@dataclass
class EigenmodeTable:
    rows: list[EigenmodeRow]
    columns: list[str]
    source: Path

    @property
    def max_backward_error(self) -> float:
        return max(r.backward_error for r in self.rows) if self.rows else math.inf


def _match_column(columns: list[str], *needles: str) -> int | None:
    lowered = [c.lower() for c in columns]
    for i, col in enumerate(lowered):
        if all(n.lower() in col for n in needles):
            return i
    return None


def _to_float(text: str) -> float:
    text = text.strip()
    if text in ("", "nan", "NaN"):
        return math.nan
    if text.lower() in ("inf", "+inf", "infinity"):
        return math.inf
    return float(text)


def parse_eig_csv(path: Path) -> EigenmodeTable:
    """Parse Palace's ``eig.csv``."""
    path = Path(path)
    if not path.exists():
        raise PalaceOutputError(f"{path} was not written; Palace did not complete the eigenmode solve")
    with path.open(newline="") as fh:
        reader = csv.reader(fh)
        rows = [[c.strip() for c in row] for row in reader if any(c.strip() for c in row)]
    if len(rows) < 2:
        raise PalaceOutputError(f"{path} holds a header but no modes")
    header = rows[0]
    i_m = _match_column(header, "m")
    i_re = _match_column(header, "re", "f")
    i_im = _match_column(header, "im", "f")
    i_q = _match_column(header, "q")
    i_bkwd = _match_column(header, "bkwd")
    i_abs = _match_column(header, "abs")
    # 'm' matches many columns; require the exact single-letter header.
    exact_m = [i for i, c in enumerate(header) if c.strip().lower() == "m"]
    i_m = exact_m[0] if exact_m else i_m
    exact_q = [i for i, c in enumerate(header) if c.strip().lower() == "q"]
    i_q = exact_q[0] if exact_q else i_q
    missing = [name for name, idx in (("m", i_m), ("Re{f}", i_re), ("Im{f}", i_im), ("Error (Bkwd.)", i_bkwd)) if idx is None]
    if missing:
        raise PalaceOutputError(
            f"{path} header {header} lacks required column(s) {missing}; "
            f"without the backward error there is no genuine convergence figure"
        )
    parsed: list[EigenmodeRow] = []
    for row in rows[1:]:
        try:
            parsed.append(
                EigenmodeRow(
                    index=int(float(row[i_m])),
                    frequency_re_GHz=_to_float(row[i_re]),
                    frequency_im_GHz=_to_float(row[i_im]),
                    quality_factor=(_to_float(row[i_q]) if i_q is not None and i_q < len(row) else None),
                    backward_error=_to_float(row[i_bkwd]),
                    absolute_error=(_to_float(row[i_abs]) if i_abs is not None and i_abs < len(row) else None),
                )
            )
        except (ValueError, IndexError) as exc:
            raise PalaceOutputError(f"{path}: unparseable row {row}: {exc}") from exc
    return EigenmodeTable(rows=parsed, columns=header, source=path)


# Palace prints ``Git changeset ID: <git describe --tags --always --dirty>``.
# For a build from a release tag that is the tag itself (``v0.13.0``); for a
# build from an untagged commit it is ``<tag>-<n>-g<sha>`` or a bare sha. It
# prints no separate "Palace vX.Y.Z" line, so the version is derived from a
# leading ``vX.Y.Z`` in the changeset when present.
_BANNER_PATTERNS = {
    "git_changeset": re.compile(r"Git changeset ID:\s*(\S+)"),
    "version_from_changeset": re.compile(r"^v?(\d+\.\d+\.\d+)"),
    "mpi_processes": re.compile(r"Running with\s+(\d+)\s+MPI process", re.IGNORECASE),
    "openmp_threads": re.compile(r"(\d+)\s+OpenMP thread", re.IGNORECASE),
    "libceed_backend": re.compile(r"libCEED backend:\s*(\S+)"),
    "device": re.compile(r"Device configuration:\s*(\S+)"),
}
# Palace's own stdout eigenvalue table carries "Bkwd. Error" / "Abs. Error"
# column headings, so a bare word match on "error" would flag every
# successful run. Only line-leading diagnostics count.
_ERROR_LINE = re.compile(
    r"^\s*(error|fatal|abort(ed|ing)?|mfem abort|exception|segmentation fault|"
    r"petsc error|slepc error|\[[^\]]*\] \*\*\* process received signal)",
    re.IGNORECASE,
)


@dataclass
class LogSummary:
    git_changeset: str | None = None
    version: str | None = None
    mpi_processes: int | None = None
    openmp_threads: int | None = None
    libceed_backend: str | None = None
    device: str | None = None
    error_lines: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "git_changeset": self.git_changeset,
            "version": self.version,
            "mpi_processes": self.mpi_processes,
            "openmp_threads": self.openmp_threads,
            "libceed_backend": self.libceed_backend,
            "device": self.device,
            "error_lines": list(self.error_lines),
        }


def summarise_log(text: str) -> LogSummary:
    """Pull identity fields and error lines out of Palace's stdout/stderr."""
    out = LogSummary()
    m = _BANNER_PATTERNS["git_changeset"].search(text)
    if m:
        out.git_changeset = m.group(1)
        v = _BANNER_PATTERNS["version_from_changeset"].match(out.git_changeset)
        if v:
            out.version = v.group(1)
    m = _BANNER_PATTERNS["mpi_processes"].search(text)
    if m:
        out.mpi_processes = int(m.group(1))
    m = _BANNER_PATTERNS["openmp_threads"].search(text)
    if m:
        out.openmp_threads = int(m.group(1))
    m = _BANNER_PATTERNS["libceed_backend"].search(text)
    if m:
        out.libceed_backend = m.group(1)
    m = _BANNER_PATTERNS["device"].search(text)
    if m:
        out.device = m.group(1)
    out.error_lines = [ln.strip() for ln in text.splitlines() if _ERROR_LINE.search(ln)][:20]
    return out


@dataclass(frozen=True)
class ProbeSample:
    mode_index: int
    probe_index: int
    E: tuple[complex, complex, complex]

    @property
    def intensity(self) -> float:
        return sum(abs(c) ** 2 for c in self.E)


_PROBE_COLUMN = re.compile(r"^(Re|Im)\{E_([xyz])\[(\d+)\]\}", re.IGNORECASE)


def parse_probe_csv(path: Path) -> list[ProbeSample]:
    """Parse Palace's ``probe-E.csv`` (eigenmode driver: one row per mode).

    Columns are ``m`` then ``Re{E_x[i]} (V/m)``, ``Im{E_x[i]} (V/m)``, ... for
    each probe index ``i`` and component. Header-driven; an absent file gives
    an empty list because probes are optional.
    """
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        rows = [[c.strip() for c in row] for row in csv.reader(fh) if any(c.strip() for c in row)]
    if len(rows) < 2:
        return []
    header = rows[0]
    columns: dict[tuple[int, str, str], int] = {}
    for i, name in enumerate(header):
        m = _PROBE_COLUMN.match(name)
        if m:
            columns[(int(m.group(3)), m.group(2).lower(), m.group(1).lower())] = i
    if not columns:
        raise PalaceOutputError(f"{path} carries no Re{{E_x[i]}} probe columns: header {header}")
    probe_indices = sorted({k[0] for k in columns})
    samples: list[ProbeSample] = []
    for row in rows[1:]:
        try:
            mode_index = int(float(row[0]))
            for idx in probe_indices:
                comps = []
                for axis in ("x", "y", "z"):
                    re_i = columns.get((idx, axis, "re"))
                    im_i = columns.get((idx, axis, "im"))
                    re_v = _to_float(row[re_i]) if re_i is not None else 0.0
                    im_v = _to_float(row[im_i]) if im_i is not None else 0.0
                    comps.append(complex(re_v, im_v))
                samples.append(ProbeSample(mode_index, idx, (comps[0], comps[1], comps[2])))
        except (ValueError, IndexError) as exc:
            raise PalaceOutputError(f"{path}: unparseable probe row {row}: {exc}") from exc
    return samples


def z_polarisation_fraction(samples: list[ProbeSample]) -> dict[int, float | None]:
    """Per mode, ``sum |E_z|^2 / sum |E|^2`` over all probes.

    A TM_mn0 mode of a box has E purely along z everywhere, so its fraction is
    1 wherever the field is non-zero; a TE mode with p >= 1 has E_z = 0 and
    fraction 0; a TM mode with p >= 1 lies in between. ``None`` when every
    probe saw a zero field (all probes on nodal planes).
    """
    total: dict[int, float] = {}
    z_part: dict[int, float] = {}
    for sample in samples:
        total[sample.mode_index] = total.get(sample.mode_index, 0.0) + sample.intensity
        z_part[sample.mode_index] = z_part.get(sample.mode_index, 0.0) + abs(sample.E[2]) ** 2
    return {
        mode: (z_part[mode] / total[mode] if total[mode] > 0 else None)
        for mode in sorted(total)
    }


def read_metadata_json(path: Path) -> dict[str, Any]:
    """Palace's ``palace.json`` where present; empty dict where not."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PalaceOutputError(f"{path} is not valid JSON: {exc}") from exc
    return data if isinstance(data, dict) else {}


def git_tag_from_metadata(meta: dict[str, Any]) -> str | None:
    for key in ("GitTag", "git_tag", "Version", "version"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return None
