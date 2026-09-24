#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""E1 - THE STATIC-CAPACITANCE LOWER-BOUND CERTIFICATE FOR THE S1 ISLAND (PROBLEM C).
PREPARED, NOT APPROVED, NOT EXECUTED.

The scientific contract is E1-CONTRACT.rev8.4.md in this directory (its sha256 is
CONTRACT_SHA256 below), frozen with this code. Revision 8.4 is revision 8.3 with the
structural separation rule of D15 and the corrected statements of what was computed. This file
implements it and does not restate it; section numbers refer to it.

E1 certifies only the static problem-C capacitance bound C_static in [C_lo^static, C_hi].
It makes no E_C and no suitability claim: E_C,F1F1 is the constant EC_NOT_EVALUATED_BY_E1,
the correspondence to the registered operator is NOT_ESTABLISHED, the deviation is
NOT_EVALUATED and suitability is SUITABILITY_NOT_ASSESSED in every state. No output contains
a GHz or MHz quantity. E1.1, E1.1-half and E1.2-excl-R1 are internal (K4 only).

Modes
-----
(default)            THE ATTEMPT (section 8). Run from the repository root with no arguments,
                     exactly as INVOCATION. Refuses before anything is spent unless every
                     refusal condition of section 8 is clear. One attempt, spent before any
                     control or geometry runs by three ledger entries: a marker in the git
                     common directory, ATTEMPT-SPENT.json, and the approval renamed to
                     E1-APPROVAL.consumed.json. Then provenance.json, controls.json,
                     geometry.json, the four sigma files, the three pass files, summary.json
                     (QUALIFIED or UNQUALIFIED) or failure.json (FAILED), and manifest.sha256
                     by orchestrator/manifest.py's write_verified.
``--rehearsal``      The synthetic control phase and the S1 GEOMETRY phase (section 5,
                     rehearsal). No matrix is assembled on S1 and no S1 capacitance is computed.
                     Every control set is checked against S1's E1.1 and E1.1-half (section 3.2
                     item 2 separation) before any control numerics, and against all four S1
                     attempt sets after the geometry phase. Exits 4 unless rehearsal_pass (the
                     preflight clean, the controls, the geometry and the separation) is true.
``--confirmation``   The resource Confirmation of section 3.2 item 2: the whole attempt path
                     under the declared budget, with the S1 geometry phase and all controls, on
                     the SYNTHETIC stand-in of the selected sizes (e1_standin.py), nominal or
                     with every factorisation fallback forced for E1.2 and E1.2-excl-R1. The
                     control sets are checked against S1's E1.1 and E1.1-half before any
                     control numerics, and the stand-in's four numeric sets against the S1
                     geometry phase's four sets before any stand-in matrix is assembled
                     (section 3.2 item 2 separation); if any contains an image of an S1 attempt
                     set, nothing further is computed. The S1 panel sets are then discarded; the
                     S1 mesh is read for geometry only. Every limit flag fails closed: a missing
                     measurement is a failure, and the mode exits 4 unless confirmation_pass is
                     true.
``--proxy-a-ge``     Refuses (exit 4), computing nothing: proxy A embeds a translated E1.1, so the
                     section 3.2 item 2 separation rule refuses any further run on it (D15). Proxy
                     A is historical configuration-selection evidence only.
``--show-invocation`` The measured invocation and its differences from INVOCATION.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import resource
import signal
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy

_T_START = time.monotonic()
#: as the static refinement study: repository modules are compiled from their source, so the
#: digests the approval binds are of the code that runs
NO_BYTECODE_CACHE = "/dev/null/qmhp-no-bytecode-cache"
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = NO_BYTECODE_CACHE
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))


def _load_by_path(name: str, path: Path):
    """Load one repository module without executing any package __init__."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


af = _load_by_path("anchor_fem", REPO / "experiments" / "static-anchor-hypothesis" / "anchor_fem.py")
manifest = _load_by_path("qmhp_orchestrator_manifest", REPO / "orchestrator" / "manifest.py")
import e1_controls as ec  # noqa: E402
import e1_geometry as eg  # noqa: E402
import e1_numerics as nm  # noqa: E402

CONTRACT = HERE / "E1-CONTRACT.rev8.4.md"
CONTRACT_SHA256 = "cdf6cced13e1965bbf017a4a7d3d4af0f661df0ca921e6dd69335b4a68971740"
APPROVAL = HERE / "E1-APPROVAL.json"
APPROVAL_CONSUMED = HERE / "E1-APPROVAL.consumed.json"
APPROVAL_DRAFT = HERE / "E1-APPROVAL.draft.json"
ATTEMPT_MARKER = HERE / "ATTEMPT-SPENT.json"
COMMON_LEDGER = Path("qmhp-attempts") / "E1-S1-LOWER-BOUND.json"
RESULTS_ROOT = REPO / "results"
RECORD_PREFIX = "E1-S1-LOWER-BOUND-"
#: every repository file the attempt executes; the attempt refuses if any other repository
#: module is loaded (e1_standin.py is loaded only by the pre-approval modes)
CODE_FILES = {"driver.py": HERE / "driver.py", "e1_numerics.py": HERE / "e1_numerics.py",
              "e1_geometry.py": HERE / "e1_geometry.py", "e1_controls.py": HERE / "e1_controls.py",
              "anchor_fem.py": REPO / "experiments" / "static-anchor-hypothesis" / "anchor_fem.py",
              "orchestrator/manifest.py": REPO / "orchestrator" / "manifest.py"}
#: the pre-approval code the attempt never loads but the approval binds: the stand-in and the
#: section 3.2 item 2 separation check, whose evidence the approver compares (L5-8)
PREAPPROVAL_CODE_FILES = {"e1_standin.py": HERE / "e1_standin.py"}
#: the inputs of section 9 read by E1 code
CONFIG = {
    "mesh": "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/coupled_chip_cell_L2.msh",
    "mesh_sha256": "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428",
    "baseline_manifest": "results/STATIC-REFINEMENT-STUDY-20260923T062048Z/manifest.sha256",
    "baseline_manifest_sha256": "e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622",
    "baseline_summary": "results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json",
    "baseline_summary_sha256": "7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298",
    "anchor_fem_sha256": "1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1",
    "manifest_py_sha256": "66a68dd40b8b2644efa8d204e723f27fe0a8e2127d038853e28271b8280d463f",
    "C_hi_fF": 67.9755386760262,
    "C_br_fF": 56.67470653023562,
    "gamma": "1e-6",
    "tolerance_set": "T0",
}
#: the pinned environment (section 4.4, section 9)
ENVIRONMENT = {"python": "3.11.15", "numpy": "2.4.6", "scipy": "1.17.1", "glibc": "2.39",
               "longdouble_nmant": 63,
               "threads_env": {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}}
#: the declared invocation (section 6) and how this process sees it
INVOCATION = ("env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 "
              ".venv/bin/python experiments/e1-s1-lower-bound/driver.py")
INVOCATION_MEASURED = {"argv": ["experiments/e1-s1-lower-bound/driver.py"],
                       "parent_argv": ["timeout", "--signal=KILL", "1260", ".venv/bin/python",
                                       "experiments/e1-s1-lower-bound/driver.py"],
                       "interpreter_prefix": ".venv"}
#: the budget (section 6). The 4 GiB address-space budget is the soft limit every allocation
#: of the attempt obeys; as in the static refinement study the hard limit sits 1 GiB above it
#: only so that the failure path, after the attempt has ended, can raise its own soft limit
#: to write the evidence (as RLIMIT_CPU's hard limit sits 60 s above its soft limit).
BUDGET = {"cpu_soft_s": 900, "cpu_hard_s": 960, "address_space_bytes": 4 * 1024 ** 3,
          "address_space_hard_headroom_bytes": 1024 ** 3, "wall_alarm_s": 1200, "outer_kill_s": 1260,
          "attempts": 1, "retry": "none"}
#: the Confirmation limits (section 3.2 item 2)
CONFIRMATION_LIMITS = {"cpu_s": 450.0, "peak_address_space_bytes": 2 * 1024 ** 3}
TOLERANCE_SCOPE_CHOICES = ("COPIED_NUMBERS_WITHIN_SCOPE", "COPIED_NUMBERS_EXCLUDED")
#: the approval fields a human fills in; every other field is bound (approval_want) or, for
#: does_not_authorise, must equal the draft's list. Any other field refuses (section 8).
HUMAN_FIELDS = ("source_commit", "not_before_utc", "not_after_utc", "tolerance_scope_decision", "q2_within_D5")
MAX_APPROVAL_WINDOW = timedelta(days=7)
STOP_SIGNALS = (signal.SIGXCPU, signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
FIXED_STATEMENTS = {
    "correspondence_to_registered_operator": "NOT_ESTABLISHED",
    "E_C_F1F1": "EC_NOT_EVALUATED_BY_E1",
    "deviation_from_registered_value": "NOT_EVALUATED",
    "suitability": "SUITABILITY_NOT_ASSESSED",
    "blindness": "not blind: exploratory prior knowledge exists (contract section 8)",
}
SETS = ("E1.2", "E1.2-excl-R1", "E1.1", "E1.1-half")


class Refusal(RuntimeError):
    """Raised instead of computing anything, before the attempt is spent."""


class BudgetExceeded(RuntimeError):
    """A declared budget limit or a termination signal was reached inside the attempt."""


class AttemptFailed(RuntimeError):
    """Anything that went wrong AFTER the attempt was spent: failure.json and a verified
    manifest are written where possible, and nothing is retried."""


# --- small utilities ----------------------------------------------------------------------------

def _sha(path: Path) -> str:
    return af.sha256(path)


def _usage(t0: float) -> dict:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    peak = None
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmPeak:"):
                peak = int(line.split()[1]) * 1024
    except OSError:
        pass
    return {"wall_s": time.monotonic() - t0, "cpu_s": ru.ru_utime + ru.ru_stime,
            "max_rss_bytes": ru.ru_maxrss * 1024, "peak_address_space_bytes": peak}


def _clean(o):
    """JSON-safe copy: non-finite floats become null, numpy scalars plain."""
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, Fraction):
        return nm.pq(o)
    if isinstance(o, np.ndarray):
        return [_clean(v) for v in o.tolist()]
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _dump(path: Path, obj) -> None:
    """Strict JSON, written atomically (<name>.partial, fsync, rename)."""
    text = json.dumps(_clean(obj), indent=1, allow_nan=False) + "\n"
    part = path.with_name(path.name + ".partial")
    with open(part, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(part, path)


def _render_for_record(name: str, obj) -> str:
    """The exact text a record file will hold, rendered and passed through the output guard.
    Called BEFORE the attempt is spent for everything known then (provenance, ledger), so no
    accepted approval can spend the attempt and then lose its provenance to the guard (C-1)."""
    try:
        text = json.dumps(_clean(obj), indent=1, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise Refusal(f"{name} cannot be rendered as strict JSON: {exc}") from exc
    bad = output_guard(json.loads(text), allow_capacitance=True)
    if bad:
        raise Refusal(f"the output guard refuses {name}: {bad}")
    return text


def _write_text(path: Path, text: str) -> None:
    """Text written atomically (<name>.partial, fsync, rename)."""
    part = path.with_name(path.name + ".partial")
    with open(part, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(part, path)


def _guarded_dump(path: Path, obj) -> None:
    """_dump behind the output guard's unit and E_C checks (every evidence file)."""
    bad = output_guard(_clean(obj), allow_capacitance=True)
    if bad:
        raise AttemptFailed(f"the output guard refused {path.name}: {bad}")
    _dump(path, obj)


_FORBIDDEN_UNITS = re.compile(r"(?i)\b[GM]Hz\b|GHz|MHz")


def output_guard(obj, *, allow_capacitance: bool) -> list[str]:
    """Problems with an output object: any GHz or MHz key or text; an E_C field other than the
    constant; and, unless allowed, any capacitance value (a key ending in _fF with a number)."""
    bad = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{path}.{k}"
                if _FORBIDDEN_UNITS.search(str(k)):
                    bad.append(f"{p}: a GHz or MHz key")
                if str(k).lower().startswith(("e_c", "ec_")) and v != "EC_NOT_EVALUATED_BY_E1":
                    bad.append(f"{p}: an E_C field other than EC_NOT_EVALUATED_BY_E1")
                if not allow_capacitance and str(k).endswith("_fF") and isinstance(v, (int, float)) and not isinstance(v, bool):
                    bad.append(f"{p}: a capacitance value in a state that reports none")
                walk(v, p)
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif isinstance(o, str) and _FORBIDDEN_UNITS.search(o):
            bad.append(f"{path}: GHz or MHz in text")

    walk(obj, "")
    return bad


def _display(x: float, mode) -> str:
    """A float64 value as a 6-decimal display, rounded in the given direction."""
    f = Fraction(x)
    return str((Decimal(f.numerator) / Decimal(f.denominator)).quantize(Decimal("0.000001"), rounding=mode))


# --- inputs, environment, invocation and approval (refusals before anything is spent) ----------

def baseline_values() -> dict:
    """C_hi and C_br from the verified baseline, each required bit-exact (section 1)."""
    s = json.loads((REPO / CONFIG["baseline_summary"]).read_bytes())
    c = s["classes"]["C"]
    c_hi = c["upper_bound_fF"]
    c_br = float(np.float64(c["limit_bracket_model_based"][1]) * np.float64(s["C_fF"][2]) / np.float64(c["values"][2]))
    return {"C_hi_fF": c_hi, "C_br_fF": c_br,
            "C_hi_bit_exact": isinstance(c_hi, float) and c_hi == CONFIG["C_hi_fF"] and c_hi.hex() == CONFIG["C_hi_fF"].hex(),
            "C_br_bit_exact": c_br == CONFIG["C_br_fF"] and c_br.hex() == CONFIG["C_br_fF"].hex()}


def input_digests() -> dict:
    return {"contract": _sha(CONTRACT), "mesh": _sha(REPO / CONFIG["mesh"]),
            "baseline_manifest": _sha(REPO / CONFIG["baseline_manifest"]),
            "baseline_summary": _sha(REPO / CONFIG["baseline_summary"]),
            "code": {name: _sha(p) for name, p in CODE_FILES.items()}}


def input_problems(dig: dict) -> list[str]:
    """The section 9 digests, and the baseline record verified against its own manifest."""
    want = {"contract": CONTRACT_SHA256, "mesh": CONFIG["mesh_sha256"],
            "baseline_manifest": CONFIG["baseline_manifest_sha256"], "baseline_summary": CONFIG["baseline_summary_sha256"]}
    bad = [f"input digest {k} is {dig[k]}, pinned {v}" for k, v in want.items() if dig[k] != v]
    for name, key in (("anchor_fem.py", "anchor_fem_sha256"), ("orchestrator/manifest.py", "manifest_py_sha256")):
        if dig["code"][name] != CONFIG[key]:
            bad.append(f"input digest {name} is {dig['code'][name]}, pinned {CONFIG[key]}")
    bad += [f"baseline record: {p}" for p in manifest.verify((REPO / CONFIG["baseline_manifest"]).parent)]
    return bad


def _git_dirs(repo: Path = REPO) -> tuple[Path, Path]:
    g = repo / ".git"
    if g.is_file():
        gitdir = Path(g.read_text().split("gitdir:", 1)[1].strip())
        gitdir = gitdir if gitdir.is_absolute() else (repo / gitdir).resolve()
    else:
        gitdir = g
    common = gitdir
    if (gitdir / "commondir").is_file():
        common = (gitdir / (gitdir / "commondir").read_text().strip()).resolve()
    return gitdir, common


def common_ledger_path(repo: Path = REPO) -> Path:
    """The ledger entry that survives any checkout, reset or clean of this clone and of every
    worktree sharing its git directory. It is never committed."""
    return _git_dirs(repo)[1] / COMMON_LEDGER


def git_head(repo: Path = REPO) -> str:
    gitdir, common = _git_dirs(repo)
    head = (gitdir / "HEAD").read_text().strip()
    if not head.startswith("ref:"):
        return head
    ref = head[4:].strip()
    for base in (gitdir, common):
        if (base / ref).is_file():
            return (base / ref).read_text().strip()
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text().splitlines():
            if line and not line.startswith(("#", "^")):
                sha, name = line.split(" ", 1)
                if name.strip() == ref:
                    return sha
    raise Refusal(f"cannot resolve HEAD ({ref})")


def unbound_repo_modules() -> list[str]:
    bound = {p.resolve() for p in CODE_FILES.values()}
    envs = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    out = []
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        p = Path(f).resolve()
        if REPO not in p.parents or p in bound or any(e == p or e in p.parents for e in envs):
            continue
        out.append(str(p.relative_to(REPO)))
    return sorted(set(out))


def environment_problems() -> list[str]:
    have = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    bad = [f"{k} is {have[k]}, pinned {ENVIRONMENT[k]}" for k in ("python", "numpy", "scipy") if have[k] != ENVIRONMENT[k]]
    libc = platform.libc_ver()
    if libc != ("glibc", ENVIRONMENT["glibc"]):
        bad.append(f"libc is {libc}, pinned glibc {ENVIRONMENT['glibc']}")
    if int(np.finfo(np.longdouble).nmant) != ENVIRONMENT["longdouble_nmant"]:
        bad.append("np.longdouble does not have a 64-bit significand")
    for var, val in ENVIRONMENT["threads_env"].items():
        if os.environ.get(var) != val:
            bad.append(f"environment variable {var} is {os.environ.get(var)!r}, required {val!r}")
    return bad


def _parent_argv() -> list[str] | None:
    try:
        raw = Path(f"/proc/{os.getppid()}/cmdline").read_bytes()
    except OSError:
        return None
    return [a.decode(errors="replace") for a in raw.split(b"\0") if a]


def measure_invocation() -> dict:
    cached = {name: getattr(sys.modules.get(mod), "__cached__", None)
              for name, mod in (("e1_numerics.py", "e1_numerics"), ("e1_geometry.py", "e1_geometry"),
                                ("e1_controls.py", "e1_controls"), ("anchor_fem.py", "anchor_fem"),
                                ("orchestrator/manifest.py", "qmhp_orchestrator_manifest"))}
    return {"cwd": os.getcwd(), "argv": list(sys.argv), "parent_argv": _parent_argv(),
            "executable": sys.executable, "prefix": sys.prefix, "optimize": sys.flags.optimize,
            "dont_write_bytecode": bool(sys.dont_write_bytecode), "pycache_prefix": sys.pycache_prefix,
            "bytecode_cache_paths": cached,
            "threads_env": {v: os.environ.get(v) for v in ENVIRONMENT["threads_env"]}}


def invocation_problems(measured: dict | None = None) -> list[str]:
    m = measure_invocation() if measured is None else measured
    want = INVOCATION_MEASURED
    bad = []
    if Path(m["cwd"]).resolve() != REPO:
        bad.append(f"working directory {m['cwd']} is not the repository root {REPO}")
    if m["argv"] != want["argv"]:
        bad.append(f"argv {m['argv']} is not {want['argv']} (the attempt takes no arguments)")
    pa = m["parent_argv"]
    if not pa or Path(pa[0]).name != want["parent_argv"][0] or pa[1:] != want["parent_argv"][1:]:
        bad.append(f"the parent process {pa} is not the declared {want['parent_argv']}")
    if Path(m["prefix"]).resolve() != (REPO / want["interpreter_prefix"]).resolve():
        bad.append(f"interpreter prefix {m['prefix']} is not the repository's {want['interpreter_prefix']}")
    if m["optimize"] != 0:
        bad.append(f"python optimisation level {m['optimize']} (asserts removed)")
    if not (m["dont_write_bytecode"] and m["pycache_prefix"] == NO_BYTECODE_CACHE
            and all(c is None or str(c).startswith(NO_BYTECODE_CACHE) for c in m["bytecode_cache_paths"].values())):
        bad.append("repository modules were not compiled from their source (bytecode caches not bypassed)")
    return bad


def _parse_utc(s) -> datetime:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"{s!r} is not an ISO time") from exc
    if t.tzinfo is None:
        raise Refusal(f"{s!r} carries no time zone")
    return t.astimezone(timezone.utc)


def _read_approval() -> bytes:
    if not APPROVAL.is_file():
        raise Refusal("no E1-APPROVAL.json: E1 is PREPARED, NOT APPROVED. A human grants it by writing the "
                      "approval from E1-APPROVAL.draft.json (see its how_to_grant_it).")
    return APPROVAL.read_bytes()


def approval_want() -> dict:
    return {"authorises": "one execution of E1, the static-capacitance lower-bound certificate for the S1 island (problem C)",
            "attempt": 1, "prior_records": [], "contract_sha256": CONTRACT_SHA256,
            "mesh_sha256": CONFIG["mesh_sha256"], "baseline_manifest_sha256": CONFIG["baseline_manifest_sha256"],
            "baseline_summary_sha256": CONFIG["baseline_summary_sha256"],
            "code_sha256": {name: _sha(p) for name, p in CODE_FILES.items()},
            "preapproval_code_sha256": {name: _sha(p) for name, p in PREAPPROVAL_CODE_FILES.items()},
            "environment": ENVIRONMENT, "invocation": INVOCATION, "budget": BUDGET,
            "gamma": CONFIG["gamma"], "tolerance_set": CONFIG["tolerance_set"], "repository_path": str(REPO)}


def draft_approval() -> dict:
    """E1-APPROVAL.draft.json: what a human would grant, with the human's fields as
    placeholders. It authorises nothing; the driver reads only E1-APPROVAL.json."""
    return {
        "DRAFT": ("NOT AN APPROVAL. This is the approval a human would grant for E1, prepared for review. The "
                  "driver reads only E1-APPROVAL.json, and this file authorises nothing. E1 is PREPARED, NOT "
                  "APPROVED, NOT EXECUTED."),
        "how_to_grant_it": (
            "A human who approves writes experiments/e1-s1-lower-bound/E1-APPROVAL.json containing every field "
            "below except DRAFT and how_to_grant_it; does_not_authorise may be kept unchanged or left out, and "
            "any other field refuses, as does a repeated member or a non-standard JSON constant. Approve only a "
            "commit whose pre-approval evidence (the rehearsal and both Confirmation runs, produced from this "
            "commit after its review) carries the code_sha256 and preapproval_code_sha256 below; the evidence "
            "files committed at 90bf9eb are superseded, and proxyA-gE.json is historical configuration-selection "
            "evidence that is not re-run (contract section 3.2 item 2, D15). source_commit is replaced by the full "
            "SHA of the reviewed commit, which must be HEAD at execution. not_before_utc and not_after_utc are "
            "replaced by ISO-8601 UTC times at most 7 days apart. tolerance_scope_decision is replaced by one of "
            f"{list(TOLERANCE_SCOPE_CHOICES)} (contract section 7: whether numbers E1 only copies from the frozen "
            "static study are within the section 7 rule). q2_within_D5 is replaced by true (Q2 stays, contract "
            "section 1) or false (Q2 is dropped before execution). Every other field is copied unchanged. The "
            "driver refuses, spending nothing, if any digest, the environment, the invocation, the budget, the "
            "checkout path, HEAD or the time differs. Running it spends the one attempt before any control runs: "
            f"it creates <git common directory>/{COMMON_LEDGER} and ATTEMPT-SPENT.json exclusively and renames "
            "E1-APPROVAL.json to E1-APPROVAL.consumed.json. After the run, whatever the outcome, the record, "
            "ATTEMPT-SPENT.json and E1-APPROVAL.consumed.json are committed together before the environment is "
            "discarded; if no record directory exists, the git-common-directory entry is first copied byte for "
            "byte to experiments/e1-s1-lower-bound/ATTEMPT-LEDGER-NOTE.json and committed with them."),
        **approval_want(),
        "source_commit": "<the full SHA of the reviewed commit; must equal HEAD at execution>",
        "not_before_utc": "<ISO-8601 UTC>",
        "not_after_utc": "<ISO-8601 UTC, at most 7 days after not_before_utc>",
        "tolerance_scope_decision": f"<one of {list(TOLERANCE_SCOPE_CHOICES)}>",
        "q2_within_D5": "<true or false>",
        "does_not_authorise": [
            "a second attempt, whatever the first one's outcome",
            "running from another checkout, another commit or outside the validity window",
            "removing or editing ATTEMPT-SPENT.json, the git-common-directory ledger entry, "
            "E1-APPROVAL.consumed.json or the record",
            "any further capacitance computation on S1 after E1 (contract section 8 stop rule)",
            "any E_C, g, deviation or suitability statement, or any statement in frequency units, from any E1 number",
            "any tolerance T1-T4 not adopted by a recorded human decision before this approval",
            "any Palace solve, Route A inversion, workflow dispatch or physical extraction",
        ],
    }


def _members_once(pairs: list) -> dict:
    """object_pairs_hook: a JSON object whose members are all distinct. json.loads would keep
    only the last of a repeated member, so what a reader sees could differ from what is bound."""
    keys = [k for k, _ in pairs]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise Refusal(f"E1-APPROVAL.json repeats the member(s) {repeated}")
    return dict(pairs)


def _no_constant(token: str):
    raise Refusal(f"E1-APPROVAL.json holds the non-standard JSON constant {token}")


def _same_json(a, b) -> bool:
    """Equality of two JSON values including their types: true is not 1, and 1.0 is not 1."""
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def require_approval(now: datetime | None = None, *, raw: bytes | None = None) -> dict:
    """The approval (section 8): bound to this contract, the code, the mesh and the inputs;
    carrying gamma = 1e-6, tolerance set T0, the human's section 7 scope decision and the
    Q2 decision of section 1; for HEAD; inside a window of at most 7 days. Strict JSON: a
    repeated member or a non-standard constant refuses, and bound values compare with their
    JSON types."""
    try:
        ap = json.loads(_read_approval() if raw is None else raw, object_pairs_hook=_members_once,
                        parse_constant=_no_constant)
    except json.JSONDecodeError as exc:
        raise Refusal(f"E1-APPROVAL.json is not JSON: {exc}") from exc
    if not isinstance(ap, dict):
        raise Refusal("E1-APPROVAL.json is not an object")
    want = approval_want()
    unknown = sorted(set(ap) - set(want) - set(HUMAN_FIELDS) - {"does_not_authorise"})
    if unknown:
        raise Refusal(f"the approval carries fields the driver does not bind: {unknown}")
    if "does_not_authorise" in ap and not _same_json(ap["does_not_authorise"], draft_approval()["does_not_authorise"]):
        raise Refusal("approval does_not_authorise differs from the draft's list")
    for key, value in want.items():
        if key not in ap or not _same_json(ap[key], value):
            raise Refusal(f"approval {key} does not match: the reviewed state has changed")
    if not isinstance(ap.get("tolerance_scope_decision"), str) or ap["tolerance_scope_decision"] not in TOLERANCE_SCOPE_CHOICES:
        raise Refusal("the approval does not record the human's section 7 scope decision "
                      f"(tolerance_scope_decision must be one of {TOLERANCE_SCOPE_CHOICES})")
    if not isinstance(ap.get("q2_within_D5"), bool):
        raise Refusal("the approval does not record the section 1 Q2 decision (q2_within_D5 true or false)")
    if not re.fullmatch(r"[0-9a-f]{40}", str(ap.get("source_commit"))):
        raise Refusal("approval source_commit is not a full commit SHA")
    head = git_head(REPO)
    if head != ap["source_commit"]:
        raise Refusal(f"approval source_commit {ap['source_commit']} is not HEAD {head}")
    nb, na = _parse_utc(ap.get("not_before_utc")), _parse_utc(ap.get("not_after_utc"))
    if not (nb < na <= nb + MAX_APPROVAL_WINDOW):
        raise Refusal("the approval window is empty or longer than 7 days")
    now = datetime.now(timezone.utc) if now is None else now
    if not nb <= now <= na:
        raise Refusal("the approval is outside its validity window")
    return ap


def preflight_problems() -> dict:
    """Every refusal condition of section 8 that does not need the approval or the ledger."""
    dig = input_digests()
    base = baseline_values()
    probes = {"dispatch": nm.dispatch_probe(), "arithmetic": nm.arithmetic_probe()}
    c0 = nm.derive_c0()
    bad = input_problems(dig) + environment_problems()
    bad += [f"{k} probe failed" for k, v in probes.items() if not v["ok"]]
    bad += nm.frozen_constants_problems(af.EPSILON0)
    if not c0["within_limit"]:
        bad.append(f"the derived c0 = {c0['c0_float']} exceeds 64 (1 - gamma_{c0['q_B']})")
    if not base["C_hi_bit_exact"]:
        bad.append("C_hi is not bit-exact")
    if not base["C_br_bit_exact"]:
        bad.append("C_br is not bit-exact")
    return {"problems": bad, "digests": dig, "baseline": base, "probes": probes, "c0": c0}


# --- the budget and signals (as the static refinement study) ----------------------------------

_SIGNALS = {"stopping": False, "received": []}


def _on_limit(signum, _frame):
    name = signal.Signals(signum).name
    _SIGNALS["received"].append({"signal": name, "at_s": time.monotonic() - _T_START})
    if _SIGNALS["stopping"]:
        return
    _SIGNALS["stopping"] = True
    raise BudgetExceeded(f"{name}: a declared budget limit or a termination signal was reached")


def _require_enforceable_budget() -> None:
    wanted = {resource.RLIMIT_CPU: BUDGET["cpu_hard_s"],
              resource.RLIMIT_AS: BUDGET["address_space_bytes"] + BUDGET["address_space_hard_headroom_bytes"]}
    for rlim, value in wanted.items():
        hard = resource.getrlimit(rlim)[1]
        if hard != resource.RLIM_INFINITY and hard < value:
            raise Refusal(f"this environment's hard limit {hard} is below the declared budget {value}")


def _enforce_budget() -> dict:
    """CPU soft 900 s (SIGXCPU raises), hard 960 s; address space 4 GiB soft; SIGALRM 1,200 s
    after process start; SIGTERM, SIGHUP and SIGINT raise once (section 6)."""
    wall = max(1, int(BUDGET["wall_alarm_s"] - (time.monotonic() - _T_START)))
    mem = BUDGET["address_space_bytes"]
    _SIGNALS.update(stopping=False, received=[])
    for sig in STOP_SIGNALS:
        signal.signal(sig, _on_limit)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, STOP_SIGNALS)   # an inherited mask may block them (C-4)
    resource.setrlimit(resource.RLIMIT_CPU, (BUDGET["cpu_soft_s"], BUDGET["cpu_hard_s"]))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem + BUDGET["address_space_hard_headroom_bytes"]))
    signal.alarm(wall)
    return {"cpu_soft_s": BUDGET["cpu_soft_s"], "cpu_hard_s": BUDGET["cpu_hard_s"], "address_space_bytes": mem,
            "address_space_hard_bytes": mem + BUDGET["address_space_hard_headroom_bytes"], "wall_alarm_s": wall,
            "wall_alarm_from_start_s": BUDGET["wall_alarm_s"], "stop_signals": [s.name for s in STOP_SIGNALS]}


def _budget_enforcement_problems() -> list[str]:
    """Whether the budget is actually enforced in this process, read back after
    _enforce_budget: every stop signal unblocked and handled by _on_limit, both rlimits as
    declared, and the wall alarm armed. Anything else is 'budget enforcement is unavailable'
    (section 8): the attempt refuses before anything is spent."""
    bad = []
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    stuck = sorted(s.name for s in STOP_SIGNALS if s in blocked)
    if stuck:
        bad.append(f"stop signals are blocked: {stuck}")
    missing = [s.name for s in STOP_SIGNALS if signal.getsignal(s) is not _on_limit]
    if missing:
        bad.append(f"stop signals without the budget handler: {missing}")
    if resource.getrlimit(resource.RLIMIT_CPU) != (BUDGET["cpu_soft_s"], BUDGET["cpu_hard_s"]):
        bad.append(f"RLIMIT_CPU is {resource.getrlimit(resource.RLIMIT_CPU)}")
    if resource.getrlimit(resource.RLIMIT_AS)[0] != BUDGET["address_space_bytes"]:
        bad.append(f"RLIMIT_AS is {resource.getrlimit(resource.RLIMIT_AS)}")
    if not signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        bad.append("the wall alarm is not armed")
    return bad


def _disarm() -> None:
    _SIGNALS["stopping"] = True
    for sig in STOP_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)
    signal.alarm(0)
    for rlim in (resource.RLIMIT_CPU, resource.RLIMIT_AS):
        try:
            hard = resource.getrlimit(rlim)[1]
            resource.setrlimit(rlim, (hard, hard))
        except (ValueError, OSError):
            pass


def _shutdown() -> None:
    for _ in range(3):
        try:
            _disarm()
            return
        except BaseException:          # noqa: BLE001 - a signal raised once; retry
            _SIGNALS["stopping"] = True


def _guarded(fn):
    try:
        return fn()
    except BaseException as exc:        # noqa: BLE001
        return {"could_not_be_computed": repr(exc)}


def _create_exclusive(path: Path, text: str) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def spent_state(results_root: Path | None = None) -> list[str]:
    results_root = RESULTS_ROOT if results_root is None else results_root
    found = [p.name for p in (ATTEMPT_MARKER, APPROVAL_CONSUMED) if p.exists()]
    if common_ledger_path().exists():
        found.append(f"<git common dir>/{COMMON_LEDGER}")
    if results_root.exists():
        found += sorted(p.name for p in results_root.glob(RECORD_PREFIX + "*"))
    return found


def qmhp_mesh() -> dict:
    path = REPO / CONFIG["mesh"]
    if _sha(path) != CONFIG["mesh_sha256"]:
        raise Refusal("the mesh digest does not match")
    return af.read_gmsh22(path)


# --- the phases (shared by the attempt and the Confirmation) ---------------------------------

def controls_phase(c0: Fraction) -> dict:
    return ec.synthetic_controls(c0, af.EPSILON0)


def geometry_phase(mesh: dict) -> dict:
    return eg.geometry_phase(mesh)


def _sigma_record(name: str, sol: dict, E64: float, n: int, n_island: int) -> dict:
    return {"set": name, "N": n, "n_island_panels": n_island, "path": sol["path"], "attempts": sol["attempts"],
            "in_place": sol["in_place"], "pivot_ratio_squared": sol["pivot_ratio_squared"],
            "Q_pq": sol["Q"], "sigmaT_S64_sigma": E64, "sigma": sol["sigma"],
            "status": "RAW: recorded before any enclosure is computed; never changed"}


def capacitance_phase(sets: dict, write, force_fail: int = 0) -> dict:
    """Section 4.3-4.5 on one panel family: sigma for E1.2, E1.2-excl-R1, E1.1 and E1.1-half
    (each recorded before any enclosure), then the long-double passes (E1.2 and
    E1.2-excl-R1 in one pass, E1.1 and E1.1-half in their own), raw. ``force_fail`` forces the
    factorisations of E1.2 and E1.2-excl-R1 to fail (the Confirmation's forced run only)."""
    R, ni, nx, Rh = sets["R_E1_2"], sets["n_island"], sets["n_excl"], sets["R_E1_1_half"]
    S = nm.assemble64(R)
    S11 = np.array(S[:ni, :ni], order="F")
    sols, e64 = {}, {}
    sols["E1.2"] = nm.solve_sigma(S, ni, force_fail=force_fail)
    e64["E1.2"] = nm.energy64(S, sols["E1.2"]["d"], sols["E1.2"]["sigma"])
    Sx = nm.principal_from_lower(S, nx, sols["E1.2"]["d"])
    del S
    gc.collect()
    sols["E1.2-excl-R1"] = nm.solve_sigma(Sx, ni, force_fail=force_fail)
    e64["E1.2-excl-R1"] = nm.energy64(Sx, sols["E1.2-excl-R1"]["d"], sols["E1.2-excl-R1"]["sigma"])
    del Sx
    gc.collect()
    sols["E1.1"] = nm.solve_sigma(S11, ni)
    e64["E1.1"] = nm.energy64(S11, sols["E1.1"]["d"], sols["E1.1"]["sigma"])
    del S11
    Sh = nm.assemble64(Rh)
    sols["E1.1-half"] = nm.solve_sigma(Sh, len(Rh))
    e64["E1.1-half"] = nm.energy64(Sh, sols["E1.1-half"]["d"], sols["E1.1-half"]["sigma"])
    del Sh
    sizes = {"E1.2": (len(R), ni), "E1.2-excl-R1": (nx, ni), "E1.1": (ni, ni), "E1.1-half": (len(Rh), len(Rh))}
    for name in SETS:
        write(f"sigma-{name}.json", _sigma_record(name, sols[name], e64[name], *sizes[name]))
    sx = np.zeros(len(R))
    sx[:nx] = sols["E1.2-excl-R1"]["sigma"]
    passes = {"E1.2+E1.2-excl-R1": nm.ld_pass(R, [sols["E1.2"]["sigma"], sx]),
              "E1.1": nm.ld_pass(R[:ni], [sols["E1.1"]["sigma"]]),
              "E1.1-half": nm.ld_pass(Rh, [sols["E1.1-half"]["sigma"]])}
    uf = {"E1.2+E1.2-excl-R1": nm.underflow_check([sols["E1.2"]["sigma"], sx], passes["E1.2+E1.2-excl-R1"]["min_abs_S"],
                                                  passes["E1.2+E1.2-excl-R1"]["min_B"]),
          "E1.1": nm.underflow_check([sols["E1.1"]["sigma"]], passes["E1.1"]["min_abs_S"], passes["E1.1"]["min_B"]),
          "E1.1-half": nm.underflow_check([sols["E1.1-half"]["sigma"]], passes["E1.1-half"]["min_abs_S"],
                                          passes["E1.1-half"]["min_B"])}
    for pname, p in passes.items():
        write(f"pass-{pname}.json", {
            "pass": pname, "N": p["N"], "m": p["m"], "gamma_m_pq": nm.gamma(p["m"]),
            "E_hat_pq": [nm.pq_or_label(v) for v in p["E"]], "W_hat_pq": [nm.pq_or_label(v) for v in p["W"]],
            "G_hat_pq": [nm.pq_or_label(v) for v in p["G"]], "sigmas": ["E1.2", "E1.2-excl-R1"] if pname.startswith("E1.2") else [pname],
            "B_finite_nonnegative": p["B_finite_nonneg"], "S_finite": p["S_finite"], "underflow": uf[pname],
            "status": "RAW: long-double sums; no capacitance"})
    idx = {"E1.2": ("E1.2+E1.2-excl-R1", 0), "E1.2-excl-R1": ("E1.2+E1.2-excl-R1", 1),
           "E1.1": ("E1.1", 0), "E1.1-half": ("E1.1-half", 0)}
    return {"sols": sols, "e64": e64, "passes": passes, "underflow": uf, "idx": idx}


def k4(res: dict, paths: dict) -> dict:
    """K4 (section 5) with the last-resort rule, exactly in rationals. res[set] holds the exact
    C_lo and C~ (Fractions)."""
    C = {s: res[s]["_C_lo_exact"] for s in SETS}
    w = {s: res[s]["_C_tilde_exact"] - res[s]["_C_lo_exact"] for s in SETS}
    tol = Fraction(1, 10 ** 9)
    ineq = [("1", "E1.1", "E1.1-half", lambda: C["E1.1"] >= C["E1.1-half"] - (w["E1.1"] + w["E1.1-half"])),
            ("2", "E1.2-excl-R1", "E1.1",
             lambda: C["E1.1"] <= C["E1.2-excl-R1"] + w["E1.1"] + w["E1.2-excl-R1"] + tol * C["E1.2-excl-R1"]),
            ("3", "E1.2", "E1.2-excl-R1",
             lambda: C["E1.2-excl-R1"] <= C["E1.2"] + w["E1.2-excl-R1"] + w["E1.2"] + tol * C["E1.2"])]
    out = []
    for num, larger, smaller, test in ineq:
        if paths[larger] == "last_resort":
            out.append({"inequality": num, "larger_set": larger, "smaller_set": smaller,
                        "status": "NOT_EVALUATED_LAST_RESORT", "set_named": larger})
        else:
            out.append({"inequality": num, "larger_set": larger, "smaller_set": smaller,
                        "status": "PASS" if test() else "FAIL"})
    return {"inequalities": out, "failed": [o["inequality"] for o in out if o["status"] == "FAIL"]}


def analyse(cap: dict, kappa_lo: Fraction, c_hi: float) -> dict:
    """Enclosures, check (g), the no-underflow requirement, K4 and C_lo^static <= C_hi. Returns
    the per-set results (internal) and the list of UNQUALIFIED reasons (no numbers)."""
    problems, res = [], {}
    for pname, p in cap["passes"].items():
        if not p["B_finite_nonneg"]:
            problems.append(f"pass {pname}: an entry bound is not finite and non-negative")
        if not cap["underflow"][pname]["ok"]:
            problems.append(f"pass {pname}: the no-underflow requirement failed")
    for s in SETS:
        pname, k = cap["idx"][s]
        p = cap["passes"][pname]
        sol = cap["sols"][s]
        enc = nm.enclosure(sol["Q"], p["E"][k], p["W"][k], p["G"][k], p["m"], kappa_lo)
        if not enc["ok"]:
            problems.append(f"{s}: a non-finite or non-positive energy, or Q <= 0")
            res[s] = enc
            continue
        g = nm.check_g(sol["Q"], cap["e64"][s], p["E"][k], enc["C_lo_fF"], kappa_lo)
        if not g["ok"]:
            problems.append(f"{s}: check (g) failed")
        res[s] = {**enc, "check_g": g, "path": sol["path"], "_C_lo_exact": Fraction(enc["C_lo_fF"]),
                  "_C_tilde_exact": sol["Q"] * sol["Q"] * kappa_lo / nm.to_fr(p["E"][k]),
                  "_E_up": nm.e_up(p["E"][k], p["W"][k], p["G"][k], p["m"])}
    kk4 = None
    if not problems:
        kk4 = k4(res, {s: cap["sols"][s]["path"] for s in SETS})
        problems += [f"K4 inequality {n} failed" for n in kk4["failed"]]
        if res["E1.2"]["_C_lo_exact"] > Fraction(c_hi):
            problems.append("C_lo^static > C_hi")
    return {"sets": res, "K4": kk4, "problems": problems}


def q2(c_lo_static: float) -> dict:
    """Q2 (section 1): C_lo^static (1 - gamma) > C_br, exactly."""
    lhs = Fraction(c_lo_static) * (1 - Fraction(CONFIG["gamma"]))
    label = "MODEL_BRACKET_PREMISE_REFUTED" if lhs > Fraction(CONFIG["C_br_fF"]) else "MODEL_BRACKET_NOT_CONTRADICTED"
    return {"label": label, "gamma": CONFIG["gamma"], "basis": "CONDITIONAL_ON_LIBM_ASSUMPTION (contract section 4.4)",
            "premise": "two terms, orders 1 and q in (1, 2], coefficients of one sign",
            "note": ("MODEL_BRACKET_NOT_CONTRADICTED is not evidence for the bracket"
                     if label == "MODEL_BRACKET_NOT_CONTRADICTED" else
                     "for this model; a separate correction record follows; the frozen study is not edited")}


SUBJECT_S1 = "C_static, problem C, of the meshed S1 model (contract section 1)"
SUBJECT_STANDIN = "SYNTHETIC STAND-IN of the Confirmation (contract section 3.2 item 2): NOT S1"


def _diagnostics(analysis: dict | None) -> dict | None:
    """Dimensionless per-set diagnostics and the K4 statuses: no capacitance value."""
    if not analysis:
        return None
    per = {k: {"path": v.get("path"), "m": v.get("m"), "enclosure_ok": v.get("ok"),
               "check_g_ok": (v.get("check_g") or {}).get("ok"), "check_g_rel": (v.get("check_g") or {}).get("rel"),
               "g_E": (v.get("check_g") or {}).get("g_E"), "width_rel": v.get("width_rel")}
           for k, v in analysis["sets"].items()}
    return {"per_set": per, "K4": analysis["K4"]}


def build_summary(outcome: str, analysis: dict | None, problems: list, approval: dict | None, c_hi: float,
                  subject: str = SUBJECT_S1) -> dict:
    """summary.json. Every state carries the fixed statements, the dimensionless diagnostics
    and the K4 statuses; only QUALIFIED carries a capacitance value (C_lo^static and C_hi)
    and Q2 (contract sections 1 and 8)."""
    s = {"subject": subject, "outcome": outcome, "fixed_statements": FIXED_STATEMENTS,
         "tolerance_set": CONFIG["tolerance_set"], "gamma": CONFIG["gamma"],
         "tolerance_scope_decision": approval.get("tolerance_scope_decision") if approval else None,
         "not_reported": "E_C,F1F1 and g; no quantity in frequency units; no suitability or deviation label",
         "diagnostics": _diagnostics(analysis)}
    if outcome != "QUALIFIED":
        s["unqualified_reasons"] = problems
        s["reported_result"] = "NONE: an UNQUALIFIED run reports no capacitance value (contract section 8)"
        return s
    c_lo = analysis["sets"]["E1.2"]["C_lo_fF"]
    s["reported_result"] = {
        "quantity": subject,
        "C_lo_static_fF": c_lo, "C_hi_fF": c_hi,
        "display_fF": f"[{_display(c_lo, ROUND_FLOOR)}, {_display(c_hi, ROUND_CEILING)}]",
        "C_lo_static_basis": ("certified Thomson/Galerkin lower bound for E1.2 under the libm ASSUMPTION of "
                              "section 4.4, in the model's eps0 convention (1/(mu0 c_light^2), mu0 = 4 pi 1e-7 H/m)"),
        "C_hi_basis": ("the frozen static study's Dirichlet upper bound, rigorous relative to the assembled "
                       "operator up to the uncertified rho (contract section 1)")}
    if approval and approval.get("q2_within_D5") is True:
        s["Q2"] = q2(c_lo)
    else:
        s["Q2"] = {"label": "Q2_DROPPED_AT_APPROVAL", "note": "the approval did not confirm that Q2 stays within D5"}
    return s


def internal_values(analysis: dict) -> dict:
    """internal-sets.json, written only for a QUALIFIED outcome: the K4 inputs of the internal
    sets, for audit. They are not results (D2, D10) and never enter any application (section 7)."""
    return {"status": "INTERNAL: not results; no physical or E_C interpretation (D2, D10; contract sections 2, 7)",
            "per_set": {k: {"C_lo_fF": v["C_lo_fF"], "C_tilde_fF": v["C_tilde_fF"], "w_fF": v["w_fF"]}
                        for k, v in analysis["sets"].items()}}


def finish(write, result: dict, problems: list, approval: dict | None, subject: str, extra: dict) -> dict:
    """The end of the attempt path: the outcome, internal-sets.json (QUALIFIED only) and
    summary.json, each through the output guard. Returns the summary."""
    outcome = "QUALIFIED" if not problems and result["outcome"] == "QUALIFIED" else "UNQUALIFIED"
    summary = build_summary(outcome, result.get("analysis"), problems, approval, CONFIG["C_hi_fF"], subject)
    summary.update(extra)
    guard = output_guard(_clean(summary), allow_capacitance=outcome == "QUALIFIED")
    if guard:
        raise AttemptFailed(f"the output guard refused the summary: {guard}")
    if outcome == "QUALIFIED":
        write("internal-sets.json", internal_values(result["analysis"]))
    write("summary.json", summary)
    return summary


def run_phases(write, *, mesh: dict, c0: Fraction, standin: dict | None = None, force_fail: int = 0,
               check_standin=None, check_controls=None) -> dict:
    """The phases in contract order: synthetic controls, the S1 geometry phase (a failure in
    either stops before any matrix is assembled), then the capacitance phase on the S1 panel
    sets (attempt) or on the synthetic stand-in (Confirmation, where the S1 sets are
    discarded first). In the Confirmation (standin given) the section 3.2 item 2 separation is
    checked twice, failing closed and computing nothing further on a coincidence or a missing
    check: the control sets before any control numerics (check_controls), and the stand-in's
    sets against the geometry phase's before any stand-in matrix (check_standin). Returns the
    outcome and the analysis."""
    control_separation = None
    if standin is not None:
        control_separation = check_controls() if check_controls is not None else ["no control separation check was supplied"]
        if control_separation:
            return {"outcome": "UNQUALIFIED", "problems": [f"control separation: {b}" for b in control_separation],
                    "control_separation": control_separation}
    controls = controls_phase(c0)
    write("controls.json", controls)
    if controls["failures"]:
        return {"outcome": "UNQUALIFIED", "problems": [f"control {k} failed" for k in controls["failures"]]}
    geo = geometry_phase(mesh)
    write("geometry.json", {k: v for k, v in geo.items() if not k.startswith("R_")})
    if geo["failures"]:
        return {"outcome": "UNQUALIFIED", "problems": [f"geometry: {f}" for f in geo["failures"]]}
    separation = None
    if standin is None:
        sets = {k: geo[k] for k in ("R_E1_2", "n_island", "n_excl", "R_E1_1_half")}
    else:
        # section 3.2 item 2 separation: fail closed, and compute nothing on the stand-in, if any
        # of its numeric sets coincides with an S1 attempt set or no check was supplied
        separation = check_standin(geo) if check_standin is not None else ["no separation check was supplied"]
        if separation:
            return {"outcome": "UNQUALIFIED", "problems": [f"separation: {b}" for b in separation],
                    "separation": separation, "control_separation": control_separation}
        sets = standin
    del geo
    gc.collect()
    try:
        cap = capacitance_phase(sets, write, force_fail)
    except nm.LastResortInvalid as exc:
        return {"outcome": "UNQUALIFIED", "problems": [f"trial vector: {exc}"]}
    an = analyse(cap, Fraction(nm.KAPPA_LO_PQ), CONFIG["C_hi_fF"])
    return {"outcome": "QUALIFIED" if not an["problems"] else "UNQUALIFIED", "problems": an["problems"],
            "analysis": an, "paths": {s: cap["sols"][s]["path"] for s in SETS}, "separation": separation,
            "control_separation": control_separation}


# --- the attempt -----------------------------------------------------------------------------

def execute(results_root: Path | None = None) -> Path:
    t0 = time.monotonic()
    results_root = RESULTS_ROOT if results_root is None else results_root
    if _sha(CONTRACT) != CONTRACT_SHA256:
        raise Refusal(f"the contract file is not the frozen {CONTRACT.name} (sha256 {CONTRACT_SHA256})")
    spent = spent_state(results_root)
    if spent:
        raise Refusal(f"{spent[0]} exists: the one attempt is spent")
    raw = _read_approval()
    approval = require_approval(raw=raw)
    unbound = unbound_repo_modules()
    if unbound:
        raise Refusal(f"repository code the approval does not bind is loaded: {unbound}")
    inv_bad = invocation_problems()
    if inv_bad:
        raise Refusal(f"the invocation differs from the declared one: {inv_bad}")
    pre = preflight_problems()
    if pre["problems"]:
        raise Refusal(f"a section 8 refusal condition holds: {pre['problems']}")
    _require_enforceable_budget()
    mesh = qmhp_mesh()
    common = common_ledger_path()
    provenance = {"contract_sha256": CONTRACT_SHA256, "approval_sha256": hashlib.sha256(raw).hexdigest(),
                  "approval": approval, "source_commit_measured": git_head(REPO), "repository_path": str(REPO),
                  "inputs": pre["digests"], "baseline": pre["baseline"], "probes": pre["probes"], "c0": pre["c0"],
                  "environment": {"python": platform.python_version(), "numpy": np.__version__,
                                  "scipy": scipy.__version__, "platform": platform.platform(),
                                  "longdouble": nm.longdouble_facts()},
                  "invocation": measure_invocation(), "started_utc": datetime.now(timezone.utc).isoformat()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rec = results_root / f"{RECORD_PREFIX}{stamp}"
    ledger = {"record": rec.name, "approval_sha256": provenance["approval_sha256"],
              "source_commit": provenance["source_commit_measured"], "repository_path": str(REPO),
              "spent_utc": provenance["started_utc"]}
    written, created, limits, refused_exists, prov_text = [], [], None, False, None

    def write(name, obj):
        _guarded_dump(rec / name, obj)
        written.append(name)

    try:
        limits = _enforce_budget()
        enforcement = _budget_enforcement_problems()
        if enforcement:
            raise Refusal(f"budget enforcement is unavailable: {enforcement}")
        provenance["limits"] = limits
        # everything known before spending is rendered and guarded now (C-1)
        prov_text = _render_for_record("provenance.json", provenance)
        ledger_text = _render_for_record("the ledger entry", ledger)
        common.parent.mkdir(exist_ok=True)
        try:
            _create_exclusive(common, ledger_text)
        except FileExistsError:
            refused_exists = True
            raise
        created.append(common)
        _create_exclusive(ATTEMPT_MARKER, ledger_text)
        created.append(ATTEMPT_MARKER)
        os.rename(APPROVAL, APPROVAL_CONSUMED)
        results_root.mkdir(exist_ok=True)
        rec.mkdir(exist_ok=False)
        _write_text(rec / "provenance.json", prov_text)
        written.append("provenance.json")
        result = run_phases(write, mesh=mesh, c0=pre["c0"]["c0"])
        problems = list(result["problems"])
        remeasured = input_digests()
        if remeasured != pre["digests"]:
            problems.append("a provenance re-measurement differs from the start")
        _SIGNALS["stopping"] = True        # from here a stop signal is recorded, never raised
        _shutdown()
        if _SIGNALS["received"]:           # ... and one received before the attempt ended is FAILED
            raise BudgetExceeded(f"{[e['signal'] for e in _SIGNALS['received']]}: a stop signal was received "
                                 "before the attempt ended")
        finish(write, result, problems, approval, SUBJECT_S1,
               {"provenance": "provenance.json", "resources": _usage(t0), "signals_received": _SIGNALS["received"],
                "provenance_remeasured_equal": remeasured == pre["digests"]})
        manifest.write_verified(rec)
    except BaseException as exc:
        # first, before any call: a stop signal pending here must not raise out of the failure
        # path (C-2; a plain subscript store runs no signal handler)
        _SIGNALS["stopping"] = True
        _shutdown()
        if refused_exists:
            raise Refusal(f"{COMMON_LEDGER} exists in the git common directory: the one attempt is spent") from None
        if not common.exists():
            raise Refusal(f"the attempt could not be started and nothing was spent: {exc!r}") from exc
        _record_failure(exc, rec, ledger, created, written, limits, provenance, prov_text, t0)
    return rec


def _record_failure(exc, rec: Path, ledger: dict, created: list, written: list, limits, provenance,
                    prov_text, t0) -> None:
    """The failure path of a spent attempt (FAILED). Signals can no longer raise. Every extra
    is guarded, so failure.json and the manifest are written whatever else fails. Provenance
    that was not yet written is written here (C-3); if provenance.json still cannot be written,
    failure.json carries the provenance itself; and if failure.json cannot be written either,
    the ledger entries are overwritten with a note that carries it (as when no record directory
    exists). Only when every one of these writes fails is the provenance lost (L1-1)."""
    tb = _guarded(traceback.format_exc)
    _guarded(lambda: traceback.clear_frames(exc.__traceback__))
    _guarded(gc.collect)
    if APPROVAL.exists() and not APPROVAL_CONSUMED.exists():
        _guarded(lambda: os.rename(APPROVAL, APPROVAL_CONSUMED))
    if not rec.is_dir():
        note = {**ledger, "record_created": False, "error": repr(exc), "traceback": tb,
                "outcome": "FAILED - the one attempt is spent; no record could be created; no retry",
                "provenance": provenance}
        where = created or [common_ledger_path()]
        errs = [_guarded(lambda p=p: _dump(p, note)) for p in where]
        raise AttemptFailed(f"{rec.name}: {exc!r}; no record could be created; the error is in "
                            f"{[str(p) for p in where]} {[e for e in errs if e]}") from exc
    prov_note = "provenance.json"
    if not (rec / "provenance.json").is_file():
        def _save_provenance():
            if prov_text is not None:
                _write_text(rec / "provenance.json", prov_text)
            else:
                _dump(rec / "provenance.json", provenance)
        err_p = _guarded(_save_provenance)
        prov_note = ("provenance.json (written by the failure path)" if (rec / "provenance.json").is_file()
                     else f"NOT WRITTEN: {err_p}")
    prov_missing = not (rec / "provenance.json").is_file()
    failure = {"outcome": "FAILED - the one attempt is spent; no retry", "error": repr(exc), "traceback": tb,
               "fixed_statements": FIXED_STATEMENTS, "reported_result": "NONE",
               "files_written": list(written),
               "partial_files": _guarded(lambda: sorted(p.name for p in rec.glob("*.partial"))),
               "summary_json_superseded": (rec / "summary.json").is_file(),
               "signals_received": list(_SIGNALS["received"]), "limits": limits,
               "resources": _guarded(lambda: _usage(t0)), "provenance": prov_note}
    if prov_missing:
        # the text rendered and guarded before spending, else the in-memory provenance (L1-1)
        failure["provenance_content"] = _guarded(lambda: json.loads(prov_text)) if prov_text is not None else provenance
    err = None
    try:
        _dump(rec / "failure.json", failure)
    except BaseException as exc1:       # noqa: BLE001
        err = exc1
    if prov_missing and err is not None:
        note = {**ledger, "record_created": True, "error": repr(exc), "traceback": tb,
                "outcome": ("FAILED - the one attempt is spent; no retry; neither provenance.json nor "
                            "failure.json could be written"),
                "failure_json_error": repr(err), "provenance": failure["provenance_content"]}
        for p in (created or [common_ledger_path()]):
            _guarded(lambda p=p: _dump(p, note))
    try:
        manifest.write_verified(rec)
    except BaseException as exc2:       # noqa: BLE001
        raise AttemptFailed(f"{rec.name}: {exc!r}; the failure record could not be completed: {err!r} {exc2!r}") from exc
    if err is not None:
        raise AttemptFailed(f"{rec.name}: {exc!r}; failure.json could not be written ({err!r}); "
                            "the record is sealed by its manifest") from exc
    raise AttemptFailed(f"{rec.name}: {exc!r} (recorded in failure.json; the one attempt is spent; no retry)") from exc


# --- rehearsal, Confirmation and proxy A (never the attempt) ------------------------------------

def _code_digests(extra: dict | None = None) -> dict:
    files = {**CODE_FILES, **(extra or {})}
    return {name: _sha(p) for name, p in files.items()}


def _measured_within(value, limit) -> bool:
    """A resource flag that fails closed: a missing or non-finite measurement is a failure."""
    return value is not None and nm.finite(value) and value <= limit


def _island_sets_match(geo: dict, island: dict) -> list[str]:
    """The geometry phase's E1.1 and E1.1-half are the formula sets the early separation check
    used (section 3.1): byte for byte, else that check proved nothing."""
    got = {"E1.1": geo["R_E1_2"][:geo["n_island"]], "E1.1-half": geo["R_E1_1_half"]}
    return [f"the geometry phase's {k} is not the section 3.1 formula set the early separation check used"
            for k in island if got[k].shape != island[k].shape or got[k].tobytes() != island[k].tobytes()]


def rehearsal() -> dict:
    """The synthetic control phase and the S1 geometry phase (section 5, rehearsal). No matrix
    is assembled on S1 and no S1 capacitance is computed. Section 3.2 item 2 separation: every
    control set is checked against S1's E1.1 and E1.1-half (from the section 3.1 formula;
    enough for all four attempt sets) BEFORE any control numerics, and nothing is computed on
    a coincidence; after the geometry phase, against all four S1 attempt sets.
    rehearsal_pass needs the preflight clean as well (L5-6)."""
    import e1_standin  # noqa: PLC0415 - synthetic; never on the attempt path
    t0 = time.monotonic()
    pre = preflight_problems()
    control_sets = ec.control_numeric_sets()
    island = e1_standin.s1_island_sets()
    separation = e1_standin.separation_problems(control_sets, island)
    controls = None if separation else controls_phase(pre["c0"]["c0"])
    geo = geometry_phase(qmhp_mesh())
    s1 = e1_standin.numeric_sets(geo) if not geo["failures"] else {}
    if s1:
        separation = separation + _island_sets_match(geo, island) + e1_standin.separation_problems(control_sets, s1)
    else:
        separation = separation + ["no S1 sets to check"]
    controls_pass = controls is not None and not controls["failures"]
    passed = {"preflight_clean": not pre["problems"], "controls_pass": controls_pass,
              "geometry_pass": not geo["failures"], "separation_pass": not separation}
    return {"mode": "rehearsal", "contract_sha256": CONTRACT_SHA256,
            "rehearsal_pass": all(passed.values()), "passes": passed,
            "s1_matrices_assembled": "none: the geometry phase assembles no matrix (tested with a spy)",
            "preflight_problems_on_this_host": pre["problems"], "probes": pre["probes"], "c0": pre["c0"],
            "baseline": pre["baseline"], "inputs": pre["digests"],
            "controls": controls, "controls_pass": controls_pass,
            "geometry": {k: v for k, v in geo.items() if not k.startswith("R_")},
            "geometry_pass": not geo["failures"],
            "separation_problems": separation, "separation_pass": not separation,
            "resources": _usage(t0),
            "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                            "longdouble": nm.longdouble_facts(), "threads_env": measure_invocation()["threads_env"]},
            "code_sha256": _code_digests(PREAPPROVAL_CODE_FILES)}


def confirmation(forced: bool, evidence_dir: Path | None = None) -> dict:
    """The resource Confirmation (section 3.2 item 2): the whole attempt path under the declared
    budget, with the S1 geometry phase and all controls, on the synthetic stand-in; nominal or
    with every factorisation fallback forced for E1.2 and E1.2-excl-R1. No ledger, no approval.
    The per-phase files are written into ``evidence_dir`` (a fresh temporary directory) and
    sealed by write_verified, as in the attempt. Fails closed: confirmation_pass is true only if
    every measurement exists and is within its limit, the budget was enforced, the control sets
    and the stand-in were separated from the S1 sets (section 3.2 item 2, each checked before
    any numerics on them), the capacitance phase ran on the expected paths, no stop signal
    arrived, nothing raised and the evidence directory verifies."""
    import e1_standin  # noqa: PLC0415 - synthetic; never on the attempt path
    t0 = time.monotonic()
    pre = preflight_problems()
    evidence_dir = Path(tempfile.mkdtemp(prefix="qmhp-e1-confirmation-")) if evidence_dir is None else evidence_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)
    written = []
    result, summary, limits, enforcement, error, stand = None, None, None, None, None, None

    def write(name, obj):
        _guarded_dump(evidence_dir / name, obj)
        written.append(name)

    island = e1_standin.s1_island_sets()

    def separation(geo):
        return _island_sets_match(geo, island) + e1_standin.separation_problems(
            e1_standin.numeric_sets(stand), e1_standin.numeric_sets(geo))

    def control_separation():
        return e1_standin.separation_problems(ec.control_numeric_sets(), island)

    try:
        limits = _enforce_budget()
        enforcement = _budget_enforcement_problems()
        stand = e1_standin.standin()
        result = run_phases(write, mesh=qmhp_mesh(), c0=pre["c0"]["c0"], standin=stand,
                            force_fail=len(nm.FALLBACK_STEPS) if forced else 0, check_standin=separation,
                            check_controls=control_separation)
        summary = finish(write, result, list(result["problems"]), None, SUBJECT_STANDIN, {})
        manifest.write_verified(evidence_dir)
    except BaseException as exc:            # noqa: BLE001 - recorded; the Confirmation fails closed
        _SIGNALS["stopping"] = True
        error = repr(exc)
    finally:
        _SIGNALS["stopping"] = True
        _shutdown()
    usage = _usage(t0)
    an = (result or {}).get("analysis") or {}
    paths = (result or {}).get("paths")
    want_paths = ({"E1.2": "last_resort", "E1.2-excl-R1": "last_resort"} if forced else {})
    paths_ok = paths is not None and all(paths.get(k) == v for k, v in want_paths.items())
    verify = _guarded(lambda: manifest.verify(evidence_dir))
    checks = {
        "cpu_within_limit": _measured_within(usage.get("cpu_s"), CONFIRMATION_LIMITS["cpu_s"]),
        "peak_within_limit": _measured_within(usage.get("peak_address_space_bytes"),
                                              CONFIRMATION_LIMITS["peak_address_space_bytes"]),
        "budget_enforced": enforcement == [],
        "separated_from_s1": (result is not None and result.get("separation") == []
                              and result.get("control_separation") == []),
        "capacitance_phase_ran_on_expected_paths": paths_ok,
        "no_stop_signal": not _SIGNALS["received"],
        "no_error": error is None,
        "evidence_directory_verifies": verify == [],
        "preflight_clean_on_this_host": not pre["problems"],
    }
    return {"mode": "confirmation-" + ("forced-fallback" if forced else "nominal"), "contract_sha256": CONTRACT_SHA256,
            "confirmation_pass": all(checks.values()), "checks": checks, "error": error, "limits": limits,
            "budget_enforcement_problems": enforcement, "resources": usage, "confirmation_limits": CONFIRMATION_LIMITS,
            "cpu_within_limit": checks["cpu_within_limit"], "peak_within_limit": checks["peak_within_limit"],
            "stand_in": ({"N": len(stand["R_E1_2"]), "N_x": stand["n_excl"], "n_island": stand["n_island"],
                          "sheet_panels": stand.get("sheet_panels")} if stand else None),
            "separation_problems": (result or {}).get("separation"),
            "control_separation_problems": (result or {}).get("control_separation"),
            "outcome_on_stand_in": (result or {}).get("outcome"), "problems_on_stand_in": (result or {}).get("problems"),
            "paths": paths, "K4": an.get("K4"),
            "per_set": {k: {"path": v.get("path"), "m": v.get("m"), "width_rel": v.get("width_rel"),
                            "check_g_rel": (v.get("check_g") or {}).get("rel"), "g_E": (v.get("check_g") or {}).get("g_E")}
                        for k, v in an.get("sets", {}).items()},
            "evidence_writes": {"directory": str(evidence_dir), "files": written, "manifest_verify": verify},
            "summary_outcome_on_stand_in": (summary or {}).get("outcome"), "signals_received": list(_SIGNALS["received"]),
            "preflight_problems_on_this_host": pre["problems"],
            "code_sha256": _code_digests(PREAPPROVAL_CODE_FILES)}


def proxy_a_ge() -> dict:
    """Proxy A (section 3.2 item 5) is historical configuration-selection evidence only (D15).
    Its first 1,024 panels are S1's E1.1 translated by +0.6 mm in x, so the section 3.2 item 2
    separation rule refuses any further run on it. This mode checks that and refuses (exit 4),
    computing nothing on proxy A."""
    import e1_standin  # noqa: PLC0415
    px = e1_standin.proxy_a()
    separation = e1_standin.separation_problems({"proxy A": px["R"]}, e1_standin.s1_island_sets())
    return {"mode": "proxy-A g_E", "contract_sha256": CONTRACT_SHA256, "N": len(px["R"]),
            "separation_problems": separation, "g_E": None, "g_E_within_1e-9": False,
            "status": ("REFUSED, nothing computed: proxy A is historical configuration-selection evidence only "
                       "(contract section 3.2 items 2 and 5, D15)"),
            "code_sha256": _code_digests(PREAPPROVAL_CODE_FILES)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--rehearsal", action="store_true")
    g.add_argument("--confirmation", choices=("nominal", "forced"))
    g.add_argument("--proxy-a-ge", action="store_true")
    g.add_argument("--show-invocation", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    code = 0
    try:
        if args.show_invocation:
            m = measure_invocation()
            res = {"measured": m, "differences_from_declared": invocation_problems(m)}
        elif args.rehearsal:
            res = rehearsal()
            code = 0 if res["rehearsal_pass"] else 4
        elif args.confirmation:
            res = confirmation(args.confirmation == "forced")
            code = 0 if res["confirmation_pass"] else 4
        elif args.proxy_a_ge:
            res = proxy_a_ge()
            code = 4
        else:
            print(execute())
            return 0
        text = json.dumps(_clean(res), indent=1, allow_nan=False)
        if args.out:
            Path(args.out).write_text(text + "\n")
        print(text)
    except AttemptFailed as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 3
    except Refusal as exc:
        print(f"REFUSED (nothing spent): {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
