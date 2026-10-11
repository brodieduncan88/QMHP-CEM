# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The release claim and exception registers, frozen from ba076d9, held to the evidence.

WHAT IS FROZEN. The owner approved a narrow release scope on 2026-09-26: the Palace
empty-cavity benchmark and the QuTiP fixed-point bundle only, with openEMS and geometry
explicitly unsupported. `docs/release/` holds that scope, a claim register, an exception
register and a dated status addendum, all measured from the git objects of
ba076d9d972077a7a3e256a6404ab455fd748461. This module pins those four files by sha256, so
they are append-only in the same sense as the records: a correction is a new, dated,
superseding file, never an edit.

WHAT IS CHECKED, beyond the freeze:

  * every path a register cites exists (evidence, quoted files and the Palace code lists);
    every digest and quotation on a path the register declares tree-bound still matches:
    the results, the QuTiP bridge and its provenance, and the openEMS and geometry files.
    Quotations on other paths are checked for existence only. The QuTiP provenance
    directory and the openEMS and geometry directories must hold exactly their frozen file
    sets, so that no second attempt ledger, and no new implementation file there, appears;
  * the in-scope record set, its quarantine and its launcher-registered records agree with
    the pins `tests/test_frozen_evidence.py` enforces. New records OUTSIDE the release
    families are allowed; a new record inside them must be named in ADDED_AFTER_FREEZE;
  * the structured facts behind each claim are re-read from the records themselves: the
    Palace frequencies, deviations, verdicts and byte patterns, and the QuTiP check values,
    limits and supporting-record flags. The QuTiP comparison, including the baseline
    Hermiticity defect from the 120 x 120 matrix, is recomputed from `raw.json` and the
    preserved CEM snapshot in plain Python floats;
  * the QuTiP classification is pinned in three parts, and the statuses that carry the
    release's boundaries cannot move;
  * a PHRASE-LEVEL TRIPWIRE, not a proof: guarded phrases (overall PASS, memory limit or cap,
    geometry-derived, independent confirmation, error bound, and a few variants) must be
    negated earlier in their own clause, in the registers and the two Markdown files. It
    catches the phrasings in the negative controls; it does not catch every paraphrase, so
    the absence of such descriptions rests on human review of the pinned bytes;
  * the unsupported paths refuse here: the registry-resolved openEMS adapter and the
    package-level planar cells are exercised, only while their bytes match the pins and
    with process-launch primitives disabled, and the PicoGK stub text is checked unless a
    pinned supersession declares REL-BD-03 superseded on this tree (SUP-2026-10-08-01
    does: the PicoGK generator is implemented). An implementation placed outside the
    bound directories is not detected.

SCOPE. Like the frozen-evidence guard, this checks bytes, facts and wording against the
committed evidence. It is not evidence governance: whether a claim is the right reading of
its evidence is a human-reviewed judgement, recorded in the registers, not decided here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE = REPO_ROOT / "docs" / "release"
RESULTS = REPO_ROOT / "results"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_frozen_evidence as tfe  # noqa: E402  - the pins this release must agree with

FROZEN_FROM = "ba076d9d972077a7a3e256a6404ab455fd748461"

#: The four release files, pinned. docs/release/ may hold nothing else.
RELEASE_SHA256 = {
    "RELEASE-SCOPE.md": "cafb1a80c96825ebc64f3caed730ad7b523a4c23a7f77fd1d3db4ecde923e40b",
    "CLAIM-REGISTER.json": "1a03d8dc793089f4029a9d8abc439e58fbabf84187ddb3e25610b78e7f1e39c9",
    "EXCEPTION-REGISTER.json": "cd61aac5f897fe897b6c8bda76039281c0a1a9d65f41407eb6dc7f1f389b1e86",
    "STATUS-ADDENDUM-2026-09-26.md": "36c80082de2f8d2078ac92610fa24512931219eb8953edf0c803580371392b2d",
}

#: Supersessions of the tree binding, outside docs/release/ so the frozen files stay
#: byte-identical. Each is pinned like a release file: supersede again, never edit. A
#: supersession may only replace the CURRENT pin of a named tree-bound file whose frozen
#: digest it quotes (a second supersession of the same file names the pin it replaces in
#: sha256_superseded), add names to an exact file set, and declare a claim no longer true
#: of this tree (claims_superseded). It may also correct words of an EARLIER supersession
#: (corrections), quoting them verbatim; the earlier record stays pinned and unedited.
#: Every other binding is unchanged, and the frozen registers keep describing the frozen
#: commit.
SUPERSESSIONS = REPO_ROOT / "docs" / "release-supersessions"
SUPERSESSION_SHA256 = {
    "SUP-2026-10-04-01-picogk-scaffold.json": "1260bce9c5c988683ec212417bef69f2f550776585e5310e1f7acc4f9a34f6ec",
    "SUP-2026-10-08-01-picogk-generator.json": "0c79f0e2b733756521e1bb0375191af8ef63385f1fde0f38076067acb5d1356a",
    "SUP-2026-10-09-01-picogk-windows-correction.json": "40484b6c6abce9849e2587fb3ee6b8af192b8fb89f5a7cc3a8048fc373c83ac6",
    "SUP-2026-10-11-01-picogk-windows-ci.json": "166e5cfdadf15eef0d68550ae25c0a8cfe02bbc0c99c809d9353e1358e254e21",
}

#: Records in a release-scope family (PALACE-GOLDEN, PALACE-VERIFY, QUTIP-A) committed
#: after the freeze. They are NOT part of this release and must be named here deliberately,
#: so that a new record can never be read as covered by claims frozen before it existed.
ADDED_AFTER_FREEZE: frozenset[str] = frozenset()
RELEASE_FAMILIES = ("PALACE-GOLDEN-", "PALACE-VERIFY-", "QUTIP-A-")

CLAIM_STATUSES = frozenset({"VERIFIED", "QUALIFIED", "BLOCKED", "NOT-ESTABLISHED", "ASSERTED",
                            "UNSUPPORTED", "OUT-OF-SCOPE"})
DISPOSITIONS = frozenset({"QUARANTINED", "APPROVED-BY-OWNER", "DISCLOSED-UNRESOLVED",
                          "IMMUTABLE-TEXT", "NOT-RECOMPUTABLE", "HUMAN-DECISION-REQUIRED",
                          "UNSUPPORTED", "DISCLOSURE"})

#: The QuTiP classification, in the three parts the owner approved. Never one verdict.
QUTIP_CLASSIFICATION = {
    "numerical_cross_check": "PASS 11/11 (per-check checker verdicts)",
    "execution_integrity": "VERIFIED",
    "protocol_conformance": "QUALIFIED: RESOURCE-LIMIT DEVIATION",
    "overall_scientific_verdict": "NOT ISSUED",
}

#: Phrases that may appear only when negated earlier in the SAME CLAUSE (no ., ;, :, !, ?
#: or comma in between). A NOT-ESTABLISHED claim's statement is itself the negated thing
#: and is exempt.
GUARDED_PHRASES = (r"overall (scientific )?pass", r"unqualified (overall )?pass", r"overall verdict:? pass",
                   r"passed overall", r"memory (limit|cap)", r"ram limit", r"capped (the )?memory",
                   r"geometry[- ]derived", r"derived from the (chip )?geometry", r"independent confirmation",
                   r"independently confirm", r"error bound")
NEGATION = re.compile(r"\b(not|never|no|nor|without|cannot)\b", re.IGNORECASE)
#: Clause breaks: punctuation followed by space (a decimal point is not one), a table pipe, a
#: bracket, or a conjunction that can start a new assertion.
CLAUSE_BREAK = re.compile(r"[.;:,!?|](?=\s|$)|[()]|\b(and|but|so|then|because|although|though|while|whereas)\b",
                          re.IGNORECASE)

#: Statuses that must not move without a superseding register.
PINNED_STATUS = {"REL-QT-01": "QUALIFIED", "REL-PAL-08": "BLOCKED", "REL-QT-10": "ASSERTED",
                 "REL-BD-01": "UNSUPPORTED", "REL-BD-02": "UNSUPPORTED", "REL-BD-03": "UNSUPPORTED",
                 "REL-BD-04": "OUT-OF-SCOPE"}
NON_CLAIM = re.compile(r"^REL-[A-Z]{2,3}-Q?N\d+$")


def same(a, b) -> bool:
    """Type-strict equality: 1, 1.0 and true are three different values here."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


REF = re.compile(r"\b(REL-[A-Z]{2,3}-Q?N?\d+|EXC-[A-Z]\d{2})\b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_strict(text: str) -> dict:
    """JSON with duplicate keys and NaN/Infinity refused."""
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate key in {keys}")
        return dict(items)

    def constant(name):
        raise ValueError(f"non-finite constant {name}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def claim_register() -> dict:
    return load_strict((RELEASE / "CLAIM-REGISTER.json").read_text())


def exception_register() -> dict:
    return load_strict((RELEASE / "EXCEPTION-REGISTER.json").read_text())


def by_id(register: dict, key: str) -> dict[str, dict]:
    return {item["id"]: item for item in register[key]}


def supersessions() -> list[dict]:
    """The pinned supersessions, always read from the repository (not a test mirror)."""
    return [load_strict((SUPERSESSIONS / name).read_text()) for name in sorted(SUPERSESSION_SHA256)]


def effective_pin(path: str, frozen: str) -> str:
    """The pin a tree-bound file must match. Start from the frozen digest and follow, in
    file-name (date) order, each supersession that names this path, quotes exactly this
    frozen digest and replaces exactly the current pin (sha256_superseded, the frozen
    digest when absent). A link that does not continue the chain is ignored, so the file
    is then held to the last valid pin and fails."""
    pin = frozen
    for s in supersessions():
        for f in s["changed_bound_files"]:
            if f["path"] == path and f["sha256_at_frozen_commit"] == frozen \
                    and f.get("sha256_superseded", frozen) == pin:
                pin = f["sha256_superseding"]
    return pin


def superseded_claims() -> set[str]:
    """Claims a pinned supersession declares no longer true of this tree. The frozen
    register is unchanged and still describes the frozen commit; only the refusal checks
    consult this."""
    return {c["id"] for s in supersessions() for c in s.get("claims_superseded", [])}


def file_set_additions() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for s in supersessions():
        for directory, names in s["file_set_additions"].items():
            out.setdefault(directory, []).extend(names)
    return out


FIELD_PATH = re.compile(r"[A-Za-z_]+(?:\[\d+\])?(?:\.[A-Za-z_]+(?:\[\d+\])?)*")


def resolve_field(record: dict, field: str):
    """The value at a field path such as 'claims_superseded[0].on_this_tree'."""
    if not FIELD_PATH.fullmatch(field):
        raise ValueError(f"malformed field path {field!r}")
    value = record
    for name, index in re.findall(r"([A-Za-z_]+)(?:\[(\d+)\])?", field):
        value = value[name]
        if index:
            value = value[int(index)]
    return value


def correction_problems(records: list[dict]) -> list[str]:
    """A supersession may correct words of an EARLIER pinned supersession, which stays
    pinned and unedited. Each correction names that record and a field path resolving to
    text, quotes at least 20 characters of that text verbatim, and says what was wrong and
    what is correct instead. Records are in file-name (date) order."""
    problems = []
    for i, s in enumerate(records):
        earlier = {r["id"]: r for r in records[:i]}
        for c in s.get("corrections", []):
            where = f"{s['id']} corrects {c.get('record')} {c.get('field')}"
            target = earlier.get(c.get("record"))
            if target is None:
                problems.append(f"{where}: not an earlier pinned supersession")
                continue
            try:
                text = resolve_field(target, c.get("field", ""))
            except (KeyError, IndexError, TypeError, ValueError):
                problems.append(f"{where}: the field does not resolve")
                continue
            if not isinstance(text, str):
                problems.append(f"{where}: the field is not text")
                continue
            excerpt = c.get("original_excerpt", "")
            if len(excerpt) < 20 or excerpt not in text:
                problems.append(f"{where}: original_excerpt is not quoted verbatim")
            for key in ("what_was_wrong", "corrected"):
                if not str(c.get(key, "")).strip():
                    problems.append(f"{where}: {key} is empty")
    return problems


def load(path: Path) -> dict:
    return json.loads(path.read_text())


# --- structure ---------------------------------------------------------------------------

def structure_problems(claims: dict, exceptions: dict) -> list[str]:
    out: list[str] = []
    for reg in (claims, exceptions):
        if reg.get("frozen_from_commit") != FROZEN_FROM:
            out.append(f"{reg.get('register')}: frozen_from_commit is not {FROZEN_FROM}")
    ids = [c["id"] for c in claims["claims"]]
    xids = [x["id"] for x in exceptions["exceptions"]]
    for label, seq in (("claim", ids), ("exception", xids)):
        if len(seq) != len(set(seq)):
            out.append(f"duplicate {label} id")
    if set(claims["status_vocabulary"]) != CLAIM_STATUSES:
        out.append("claim status vocabulary changed")
    if set(exceptions["disposition_vocabulary"]) != DISPOSITIONS:
        out.append("disposition vocabulary changed")
    for c in claims["claims"]:
        if c["status"] not in CLAIM_STATUSES:
            out.append(f"{c['id']}: status {c['status']!r} is not in the vocabulary")
        if not c["evidence"]:
            out.append(f"{c['id']}: no evidence")
        if c["status"] == "QUALIFIED" and not c["limitations"]:
            out.append(f"{c['id']}: QUALIFIED without a qualification")
        if NON_CLAIM.match(c["id"]) and c["status"] != "NOT-ESTABLISHED":
            out.append(f"{c['id']}: a non-claim must stay NOT-ESTABLISHED")
    by_claim = {c["id"]: c["status"] for c in claims["claims"]}
    for cid, status in PINNED_STATUS.items():
        if by_claim.get(cid) != status:
            out.append(f"{cid}: status must stay {status}")
    for x in exceptions["exceptions"]:
        if x["disposition"] not in DISPOSITIONS:
            out.append(f"{x['id']}: disposition {x['disposition']!r} is not in the vocabulary")
        if not x["evidence"]:
            out.append(f"{x['id']}: no evidence")
    known = set(ids) | set(xids)
    for ref in sorted(set(REF.findall(json.dumps([claims, exceptions])))):
        if ref not in known:
            out.append(f"{ref}: cited but not defined")
    return out


def unnegated(text: str) -> list[str]:
    """Guarded phrases in text with no negation earlier in the same clause."""
    text = " ".join(text.split())
    found = []
    for pattern in GUARDED_PHRASES:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            before = text[:m.start()]
            breaks = list(CLAUSE_BREAK.finditer(before))
            clause = before[breaks[-1].end():] if breaks else before
            if not NEGATION.search(clause):
                found.append(m.group(0))
    return found


def language_problems(claims: dict, exceptions: dict, markdown: dict[str, str] | None = None) -> list[str]:
    """Every guarded phrase is negated in its own clause, in both registers and in the
    Markdown release files (the addendum's quotations of old text are exempt)."""
    out: list[str] = []

    def walk(node, where, exempt=False):
        if isinstance(node, dict):
            skip = node.get("status") == "NOT-ESTABLISHED"
            for key, value in node.items():
                walk(value, f"{where}.{key}", exempt=skip and key == "statement")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{where}[{i}]")
        elif isinstance(node, str) and not exempt:
            for phrase in unnegated(node):
                out.append(f"{where}: unnegated {phrase!r}")
    walk(claims, "claims")
    walk(exceptions, "exceptions")
    if markdown is None:
        markdown = {name: (RELEASE / name).read_text() for name in RELEASE_SHA256 if name.endswith(".md")}
    for name, text in markdown.items():
        own = re.sub(r"“[^”]*”", "“”", text)  # quotations of superseded text are not our words
        for unit in markdown_units(own):
            for phrase in unnegated(unit):
                out.append(f"{name}: unnegated {phrase!r} in {unit[:80]!r}")
    return out


def markdown_units(text: str) -> list[str]:
    """Paragraphs, list items, table rows and headings, each joined onto one line, so a
    sentence wrapped across lines is judged whole."""
    units: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            units.append([])
        elif re.match(r"(- |\d+\. |\||#)", stripped) or not units:
            units.append([stripped])
        else:
            units[-1].append(stripped)
    return [" ".join(u) for u in units if u]


# --- digests -----------------------------------------------------------------------------

def tree_bound(path: str, prefixes: list[str]) -> bool:
    return any(path == p or path.startswith(p) for p in prefixes)


def digest_problems(claims: dict, exceptions: dict, root: Path = REPO_ROOT) -> list[str]:
    """Every cited path exists; every digest on a tree-bound path still matches."""
    prefixes = claims["tree_binding"]["must_still_match"]
    if prefixes != exceptions["tree_binding"]["must_still_match"]:
        return ["the two registers declare different tree bindings"]
    out: list[str] = []
    cited: list[dict] = list(claims["in_scope_qutip_files"])
    for item in claims["claims"] + exceptions["exceptions"]:
        cited.extend(item["evidence"])
    for e in cited:
        path = root / e["path"]
        if not path.is_file():
            out.append(f"{e['path']}: cited but missing")
        elif "sha256_at_frozen_commit" in e and tree_bound(e["path"], prefixes) \
                and sha256(path) != effective_pin(e["path"], e["sha256_at_frozen_commit"]):
            out.append(f"{e['path']}: changed since the frozen commit")
    palace = claims["in_scope_palace_code_unpinned"]
    for listed in palace["paths"] + palace["shared_modules_also_used"]:
        if not (root / listed).exists():
            out.append(f"{listed}: listed as in-scope code but missing")
    for x in exceptions["exceptions"]:
        for q in x.get("quotes", []):
            path = root / q["path"]
            if not path.is_file():
                out.append(f"{x['id']}: quoted file {q['path']} is missing")
                continue
            if not tree_bound(q["path"], prefixes):
                continue  # recorded at the frozen commit only; the file may change later
            text = path.read_text()
            decoded = json.dumps(json.loads(text), ensure_ascii=False) \
                if text and q["path"].endswith(".json") else text
            if q["text"] not in text and q["text"] not in decoded:
                out.append(f"{x['id']}: quoted text no longer in {q['path']}")
    for r in claims["in_scope_records"]:
        record = root / "results" / r["record"]
        if not record.is_dir():
            out.append(f"{r['record']}: in scope but missing")
        elif r["register"] is not None and sha256(record / r["register"]) != r["register_sha256"]:
            out.append(f"{r['record']}: register changed since the frozen commit")
    return out + file_set_problems(claims, root)


def file_set_problems(claims: dict, root: Path = REPO_ROOT) -> list[str]:
    out: list[str] = []
    additions = file_set_additions()
    for directory, names in claims["tree_binding"]["exact_file_sets"].items():
        present = sorted(p.name for p in (root / directory).iterdir()
                         if p.name not in {"__pycache__", "bin", "obj"}) if (root / directory).is_dir() else []
        if present != sorted(names + additions.get(directory, [])):
            out.append(f"{directory}: holds {present}, not the frozen file set")
    return out


# --- record set --------------------------------------------------------------------------

def record_set_problems(claims: dict, exceptions: dict, on_disk: set[str], *,
                        manifested=tfe.MANIFESTED_RECORDS, quarantined=tfe.QUARANTINED,
                        launcher=tfe.LAUNCHER_REGISTERED, added_after=ADDED_AFTER_FREEZE) -> list[str]:
    """The release's records agree with the frozen-evidence pins. A record the guard pins
    outside the release families is none of this register's business; one inside them must
    be in scope or named as added after the freeze."""
    out: list[str] = []
    scoped = {r["record"]: r for r in claims["in_scope_records"]}
    family = {n for n in on_disk if n.startswith(RELEASE_FAMILIES)}
    for name in sorted((family - added_after) ^ set(scoped)):
        out.append(f"{name}: on disk in a release family but not in scope, or the reverse")
    for name in sorted(added_after & set(scoped)):
        out.append(f"{name}: both in scope and declared added after the freeze")
    for name, r in scoped.items():
        if name.startswith("QUTIP-A-"):
            if name not in launcher or not same([r["register"], r["register_sha256"]], list(launcher[name])):
                out.append(f"{name}: register differs from the frozen-evidence pin")
        elif r["register"] is None:
            if name not in quarantined:
                out.append(f"{name}: in scope without a register but not quarantined")
        elif r["register"] != "manifest.sha256" or name not in manifested:
            out.append(f"{name}: not a manifested record")
    listed_q = {x["quarantine_record"] for x in exceptions["exceptions"] if x["disposition"] == "QUARANTINED"}
    listed_l = by_id(exceptions, "exceptions")["EXC-Q02"]["launcher_registered"]
    for name in sorted(listed_q - set(quarantined)):
        out.append(f"{name}: listed as quarantined but not pinned as quarantined")
    for name in sorted(set(quarantined) - listed_q):
        if name.startswith(RELEASE_FAMILIES) and name not in added_after:
            out.append(f"{name}: a release-family quarantine missing from the exception register")
    for name, v in sorted(listed_l.items()):
        if name not in launcher or not same([v["register"], v["register_sha256"]], list(launcher[name])):
            out.append(f"{name}: launcher register differs from the frozen-evidence pin")
    for name in sorted(set(launcher) - set(listed_l)):
        if name.startswith(RELEASE_FAMILIES) and name not in added_after:
            out.append(f"{name}: a release-family launcher record missing from the exception register")
    return out


# --- unsupported paths -------------------------------------------------------------------

class LaunchBlocked(RuntimeError):
    """Raised by every process-launch primitive while the refusing code runs."""


LAUNCH_PRIMITIVES = (("subprocess", "Popen"), ("os", "system"), ("os", "popen"), ("os", "fork"),
                     ("os", "posix_spawn"), ("os", "posix_spawnp"), ("os", "execv"), ("os", "execve"),
                     ("os", "execvp"), ("os", "execvpe"), ("os", "spawnv"), ("os", "spawnve"))


def refusal_pins(claims: dict) -> dict[str, str]:
    """{path: sha256} of the files the unsupported-path claims bind."""
    c = by_id(claims, "claims")
    return {e["path"]: effective_pin(e["path"], e["sha256_at_frozen_commit"])
            for cid in ("REL-BD-01", "REL-BD-02", "REL-BD-03")
            for e in c[cid]["evidence"] if "sha256_at_frozen_commit" in e}


def unsupported_problems(claims: dict, root: Path = REPO_ROOT) -> list[str]:
    """openEMS refuses through the registry, with or without a container runtime; every
    package-level planar cell is the cells function and raises; the PicoGK program is still
    the not-implemented stub, unless a pinned supersession has superseded REL-BD-03. The
    refusing code is executed only while every bound file matches its pin, and with every
    process-launch primitive replaced by one that raises, so a changed adapter cannot
    launch anything from here."""
    import os
    import subprocess

    out = [f"{path}: bytes differ from the register pin; refusal code not executed"
           for path, pin in sorted(refusal_pins(claims).items()) if sha256(root / path) != pin]
    if out:
        return out

    def blocked(*_args, **_kwargs):
        raise LaunchBlocked("process launch attempted while checking a refusal")

    modules = {"subprocess": subprocess, "os": os}
    saved = [(mod, name, getattr(modules[mod], name)) for mod, name in LAUNCH_PRIMITIVES
             if hasattr(modules[mod], name)]
    for mod, name, _ in saved:
        setattr(modules[mod], name, blocked)
    try:
        from solvers import SolverUnavailable, get_adapter
        from solvers.openems import adapter as openems
        import geometry.chip_planar as planar
        from geometry.chip_planar import cells

        real_which = openems.shutil.which
        try:
            for which in (None, "/nonexistent/container-runtime"):
                openems.shutil.which = lambda _name, _w=which: _w
                solver = get_adapter("openems")
                if type(solver) is not openems.OpenemsSolver:
                    out.append(f"the registry resolves 'openems' to {type(solver).__module__}."
                               f"{type(solver).__name__}, not the refusing adapter")
                for label, call in (("preflight", solver.preflight), ("run", lambda: solver.run(None)),
                                    ("parse", lambda: solver.parse(None))):
                    try:
                        call()
                    except SolverUnavailable:
                        continue
                    except LaunchBlocked:
                        out.append(f"openEMS {label} attempted to launch a process (runtime {which!r})")
                        continue
                    except Exception as exc:  # any other failure is not the specified refusal
                        out.append(f"openEMS {label} raised {type(exc).__name__}, not SolverUnavailable")
                        continue
                    out.append(f"openEMS {label} did not refuse (runtime {which!r})")
        finally:
            openems.shutil.which = real_which
        for name in ("readout_resonator", "stepped_filter", "run_drc"):
            exported = getattr(planar, name)
            if exported is not getattr(cells, name):
                out.append(f"planar {name} exported by the package is not the cells function")
            try:
                exported(None)
            except cells.PlanarGeometryNotImplemented:
                continue
            except LaunchBlocked:
                out.append(f"planar {name} attempted to launch a process")
                continue
            out.append(f"planar {name} did not raise PlanarGeometryNotImplemented")
    finally:
        for mod, name, original in saved:
            setattr(modules[mod], name, original)
    if "REL-BD-03" not in superseded_claims():
        picogk = root / "geometry" / "package_picogk"
        program = (picogk / "Program.cs").read_text()
        if "geometry generation is NOT IMPLEMENTED in v0.1" not in program or "return 3;" not in program:
            out.append("PicoGK Program.cs is no longer the not-implemented stub")
        if "throw new NotImplementedException(" not in (picogk / "Object001Package.cs").read_text():
            out.append("PicoGK Object001Package.Generate no longer throws")
    return out


def host_split_problems(exceptions: dict, root: Path = REPO_ROOT) -> list[str]:
    """EXC-P02's host-side split, re-read from the golden records."""
    split = by_id(exceptions, "exceptions")["EXC-P02"]["host_side_split"]
    out: list[str] = []
    for group in split["quantum_results_sha256_groups"]:
        for name in group["records"]:
            if sha256(root / "results" / name / "QMHP-CEM-A-RF-000001" / "quantum_results.json") != group["sha256"]:
                out.append(f"EXC-P02: {name} quantum_results.json")
    for group in split["collision_measured_groups"]:
        for name in group["records"]:
            gates = load(root / "results" / name / "execution_record.json")["gates"]["gates"]
            if not same([g["measured"] for g in gates if g["gate_id"] == "COLLISION"], [group["value"]]):
                out.append(f"EXC-P02: {name} COLLISION measured")
    return out


# --- facts: Palace -----------------------------------------------------------------------

def palace_fact_problems(claims: dict, root: Path = REPO_ROOT) -> list[str]:
    c = by_id(claims, "claims")
    res = root / "results"
    out: list[str] = []

    def golden(name):
        return load(res / name / "execution_record.json")

    f1 = c["REL-PAL-01"]["facts"]
    for name in f1["records"]:
        er = golden(name)
        solver = res / name / "QMHP-CEM-A-RF-000001" / "solver"
        run = load(solver / "palace_run.json")
        got = [er["outcome"], run["returncode"], run["outcome"], er["environment"]["solver_version"],
               er["solver_provenance"]["palace_commit"], er["solver_provenance"]["mpi_processes"]]
        want = [f1["outcome"], f1["run_returncode"], f1["run_outcome"], f1["solver_version"],
                f1["palace_commit"], f1["mpi_processes"]]
        if not same(got, want):
            out.append(f"REL-PAL-01: {name} {got} != {want}")
        log = (solver / "palace_log.txt").read_text()
        if "Running with 1 MPI process" not in log or any("warning" in line.lower() for line in log.splitlines()):
            out.append(f"REL-PAL-01: {name} log is not a one-process log free of warning lines")
    f2 = c["REL-PAL-02"]["facts"]
    for name in f2["records"]:
        ac = golden(name)
        if not same([m["palace_GHz"] for m in ac["analytic_check"]["modes"]], ac["eigenmodes_GHz"]):
            out.append(f"REL-PAL-02: {name} analytic_check compares other frequencies than eigenmodes_GHz")
        got = {"eigenmodes_GHz": ac["eigenmodes_GHz"],
               "closed_form_GHz": [m["closed_form_GHz"] for m in ac["analytic_check"]["modes"]],
               "relative_deviation": [m["relative_deviation"] for m in ac["analytic_check"]["modes"]],
               "worst_relative_deviation": ac["analytic_check"]["worst_relative_deviation"],
               "tolerance": ac["analytic_check"]["tolerance"],
               "expected_relative_deviation": ac["analytic_check"]["expected_relative_deviation"]}
        for key, value in got.items():
            if not same(f2[key], value):
                out.append(f"REL-PAL-02: {name} {key}")
    for group in c["REL-PAL-03"]["facts"]["backward_error_groups"]:
        for name in group["records"]:
            conv = golden(name)["convergence"]
            if not same([conv["value"], conv["status"], conv["tolerance"]],
                        [group["value"], "CONVERGED", c["REL-PAL-03"]["facts"]["tolerance"]]):
                out.append(f"REL-PAL-03: {name}")
    f4 = c["REL-PAL-04"]["facts"]
    for group in f4["eig_csv_sha256_groups"]:
        for name in group["records"]:
            solver = res / name / "QMHP-CEM-A-RF-000001" / "solver"
            if (sha256(solver / "postpro" / "eig.csv"), sha256(solver / "mesh.msh"),
                    sha256(solver / "config.json")) != (group["sha256"], f4["mesh_sha256"], f4["config_sha256"]):
                out.append(f"REL-PAL-04: {name}")
    f5 = c["REL-PAL-05"]["facts"]
    for name in f5["records"]:
        gates = golden(name)["gates"]
        if not same([gates["overall_status"], {g["gate_id"]: g["status"] for g in gates["gates"]}],
                    [f5["overall_status"], f5["gate_status"]]):
            out.append(f"REL-PAL-05: {name}")
    key = {"REL-PAL-06": "mesh_convergence", "REL-PAL-07": "height_sensitivity_aux",
           "REL-PAL-08": "height_sensitivity_object001"}
    for cid, verdict in key.items():
        for name, want in c[cid]["recorded_verdicts"].items():
            if not same(load(res / name / "summary.json")["verdicts"][verdict], want):
                out.append(f"{cid}: {name} {verdict}")
    f6 = c["REL-PAL-06"]["facts"]
    mc = load(res / f6["table_record"] / "summary.json")["mesh_convergence"]
    if not same([[t["dof"] for t in mc["table"]], [t["max_abs_relative_analytic_error"] for t in mc["table"]],
                 [t["max_abs_relative_change_vs_previous_level"] for t in mc["table"]], mc["reasons"]],
                [f6["dof"], f6["max_abs_relative_analytic_error"],
                 f6["max_abs_relative_change_vs_previous_level"], f6["reasons"]]):
        out.append("REL-PAL-06: mesh table")
    f7 = c["REL-PAL-07"]["facts"]
    for name in f7["records_pass"]:
        aux = load(res / name / "summary.json")["height"]["aux_height"]
        for k in ("delta_f_palace_GHz", "delta_f_exact_GHz", "relative_disagreement",
                  "shift_to_uncertainty_ratio", "numerical_uncertainty_GHz", "levels_identified", "label"):
            if not same(aux[k], f7[k]):
                out.append(f"REL-PAL-07: {name} {k}")
    for name, runs in c["REL-PAL-08"]["facts"]["timeouts_3600s"].items():
        got = sorted(p.parents[1].name for p in (res / name / "runs").glob("*/solver/palace_run.json")
                     if load(p).get("outcome") == "timeout after 3600s")
        if got != sorted(runs):
            out.append(f"REL-PAL-08: {name} timeouts")
    f9 = c["REL-PAL-09"]["facts"]
    v065, v091, v115 = (res / n / "runs" for n in (
        "PALACE-VERIFY-20260915T065055Z", "PALACE-VERIFY-20260915T091242Z", "PALACE-VERIFY-20260915T115901Z"))
    for run in f9["byte_identical_091242Z_115901Z"]:
        if sha256(v091 / run / "solver/postpro/eig.csv") != sha256(v115 / run / "solver/postpro/eig.csv"):
            out.append(f"REL-PAL-09: {run} not byte-identical")
    for run in f9["differ_065055Z"]:
        if sha256(v091 / run / "solver/postpro/eig.csv") == sha256(v065 / run / "solver/postpro/eig.csv"):
            out.append(f"REL-PAL-09: {run} does not differ")
    return out


# --- facts: QuTiP ------------------------------------------------------------------------

X = "QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z"
ARCHIVE = Path("inputs") / "archive"
SNAPSHOT = ARCHIVE / "qmhp-qutip-branch-a-export-110a2e0-attempt1" / "branch-a-reference-v1.json"
FROZEN_RULES = ARCHIVE / "qmhp-qutip-branch-a-approval-110a2e0" / "frozen-rules.json"
EXPECTED = ARCHIVE / "qmhp-qutip-branch-a-preservation-110a2e0-attempt1" / "expected-hashes.json"
OBSERVABLES = ("pull_MHz_level0", "pull_MHz_level1", "pull_MHz_level2", "sink_logical_contrast_MHz",
               "sink_line_GHz", "dressed_emission_GHz", "f8_weight")


def recompute(raw: dict, snapshot: dict) -> dict:
    """The comparison, from the recorded QuTiP outputs and the CEM snapshot. Plain floats.
    An arithmetic consistency check on shared inputs, not independent confirmation."""
    q, b = raw["eigenvalues_GHz"], snapshot["baseline_eigenvalues"]
    if len(q) != len(b):
        raise ValueError("eigenvalue lists differ in length")
    out = {"ordered_eigenvalues_max": max(abs(x - y) for x, y in zip(q, b))}
    for k in OBSERVABLES:
        out[k] = abs(raw["observables"][k] - snapshot["baseline_observables"][k])
    hr, hi = snapshot["baseline_H_real"], snapshot["baseline_H_imag"]
    n = len(hr)
    if n != len(q) or any(len(row) != n for row in hr + hi):
        raise ValueError("baseline_H is not a square matrix of the model dimension")
    out["baseline_hermiticity"] = max(math.hypot(hr[i][j] - hr[j][i], hi[i][j] + hi[j][i])
                                      for i in range(n) for j in range(n))
    base = {(x["level"], x["photon"]): x["dressed_index"] for x in snapshot["baseline_labels"]}
    got = {(x["level"], x["photon"]): x["dressed_index"] for x in raw["labels"]}
    out["labels_equal_baseline"] = base == got
    out["min_qutip_overlap"] = min(x["overlap"] for x in raw["labels"])
    out["min_qutip_margin"] = min(x["overlap"] - x["runner_up_overlap"] for x in raw["labels"])
    return out


def qutip_fact_problems(claims: dict, root: Path = REPO_ROOT) -> list[str]:
    c = by_id(claims, "claims")
    rec = root / "results" / X
    exp = root / "experiments" / "qutip-a-readout-crosscheck"
    out: list[str] = []
    result = load(rec / "checker-output" / "result.json")
    f2 = c["REL-QT-02"]["facts"]
    if set(f2["checks"]) != set(result["checks"]) or len(f2["checks"]) != 11:
        out.append("REL-QT-02: the set of named checks differs")
    for name, want in f2["checks"].items():
        got = result["checks"].get(name, {})
        if not same([got.get("verdict"), got.get("limit_rule"), got.get("abs_difference"), got.get("limit")],
                    ["PASS", want["limit_rule"], want.get("value"), want.get("limit")]) or want["verdict"] != "PASS":
            out.append(f"REL-QT-02: {name}")
    herm = result["checks"]["hermiticity"]
    if not same([herm["independent_defect_GHz"], herm["baseline_defect_GHz"]],
                [f2["checks"]["hermiticity"]["independent_defect_GHz"],
                 f2["checks"]["hermiticity"]["baseline_defect_GHz"]]):
        out.append("REL-QT-02: hermiticity defects")
    if sha256(rec / FROZEN_RULES) != f2["frozen_rules_sha256"]:
        out.append("REL-QT-02: frozen rules digest")
    rules = load(rec / FROZEN_RULES)
    limit_of = {"max_hamiltonian_hermiticity_defect_GHz": rules["max_hamiltonian_hermiticity_defect_GHz"],
                **rules["thresholds"]}
    for name, check in result["checks"].items():
        if "limit" in check and not same(check["limit"], limit_of.get(check["limit_rule"])):
            out.append(f"REL-QT-02: {name} limit is not the frozen value")
    raw = load(rec / "checker-output" / "raw.json")
    snapshot = load(rec / SNAPSHOT)
    again = recompute(raw, snapshot)
    if not same(again, c["REL-QT-03"]["facts"]["recomputed"]):
        out.append("REL-QT-03: recomputation differs from the register")
    recorded = {"ordered_eigenvalues_max": result["checks"]["ordered_eigenvalues_max"]["abs_difference"],
                "baseline_hermiticity": herm["baseline_defect_GHz"],
                **{k: result["checks"][k]["abs_difference"] for k in OBSERVABLES}}
    for k, v in recorded.items():
        if not same(again[k], v):
            out.append(f"REL-QT-03: {k} does not recompute to the recorded value")
    if not again["labels_equal_baseline"] or again["min_qutip_overlap"] < rules["label_min_overlap"] \
            or again["min_qutip_margin"] < rules["label_min_margin"]:
        out.append("REL-QT-03: labels")
    f4 = c["REL-QT-04"]["facts"]
    ledger = load(exp / "ATTEMPT-LEDGER.QUTIP-A-READOUT-CROSSCHECK-v1-110a2e0-attempt1.json")
    if not (sha256(rec / "attempt-receipt.json") == ledger["receipt_sha256"] == f4["receipt_sha256"]):
        out.append("REL-QT-04: receipt and ledger")
    if not (sha256(exp / "qutip_branch_a_launcher_asgrowth.py") == ledger["launcher_sha256"] == f4["launcher_sha256"]):
        out.append("REL-QT-04: launcher and ledger")
    cout = sha256(rec / "checker-output" / "manifest.sha256")
    if cout != f4["checker_output_manifest_sha256"] or cout not in (rec / "checker.stdout").read_text():
        out.append("REL-QT-04: checker-output manifest")
    if (rec / "checker.stderr").stat().st_size != 0:
        out.append("REL-QT-04: checker.stderr is not empty")
    f5 = c["REL-QT-05"]["facts"]
    blocked = load(root / "results" / "QUTIP-A-LAUNCH-BLOCKED-20260926T025352Z" / "launcher-final.json")
    diag = load(root / "results" / "QUTIP-A-MAC-MEMORY-DIAGNOSTIC-20260926T045655Z" / "diagnostic.json")
    qual = load(root / "results" / "QUTIP-A-LAUNCHER-CONTROL-TEST-20260926T060642Z" / "qualification-final.json")
    for label, doc, want in (("blocked", blocked, f5["blocked"]), ("diagnostic", diag, f5["diagnostic"]),
                             ("qualification", qual, f5["qualification"])):
        if not same({k: doc.get(k) for k in want}, want):
            out.append(f"REL-QT-05: {label}")
    f6 = c["REL-QT-06"]["facts"]
    if not same([rules["memory_limit_MB"], rules["wall_time_limit_s"], rules["permitted_attempts"],
                 rules["approved_runtime"]], [f6["frozen_memory_limit_MB"], f6["wall_time_limit_s"],
                                              f6["permitted_attempts"], f6["approved_runtime"]]):
        out.append("REL-QT-06: frozen rules")
    for k, v in c["REL-QT-07"]["facts"].items():
        if not same(snapshot.get(k), v):
            out.append(f"REL-QT-07: {k}")
    expected = load(rec / EXPECTED)
    pinned = {**expected["source_file_hashes"], **expected["baseline_implementation_hashes"]}
    if not same(pinned, c["REL-QT-08"]["facts"]["expected_hashes_pinned"]):
        out.append("REL-QT-08: expected-hashes record")
    return out


# --- the committed release ---------------------------------------------------------------

def test_the_release_files_are_exactly_the_pinned_ones():
    present = sorted(p.name for p in RELEASE.iterdir())
    assert present == sorted(RELEASE_SHA256), present
    for name, pinned in RELEASE_SHA256.items():
        assert sha256(RELEASE / name) == pinned, f"{name} changed: supersede it, do not edit it"


def test_the_supersessions_are_exactly_the_pinned_ones():
    present = sorted(p.name for p in SUPERSESSIONS.iterdir())
    assert present == sorted(SUPERSESSION_SHA256), present
    for name, pinned in SUPERSESSION_SHA256.items():
        assert sha256(SUPERSESSIONS / name) == pinned, f"{name} changed: supersede it, do not edit it"


def test_each_supersession_binds_this_register_and_quotes_the_frozen_pins():
    claims, exceptions = claim_register(), exception_register()
    prefixes = claims["tree_binding"]["must_still_match"]
    frozen = {e["path"]: e["sha256_at_frozen_commit"]
              for item in claims["claims"] for e in item["evidence"] if "sha256_at_frozen_commit" in e}
    claim = by_id(claims, "claims")
    chains: dict[str, list[str]] = {}
    for s in supersessions():
        assert s["schema"] == "qmhp-cem.release-supersession/1"
        assert s["supersedes"]["register_sha256"] == sha256(RELEASE / "CLAIM-REGISTER.json")
        assert s["supersedes"]["register_revision"] == claims["register_revision"]
        assert s["supersedes"]["frozen_from_commit"] == FROZEN_FROM == claims["frozen_from_commit"]
        for f in s["changed_bound_files"]:
            assert tree_bound(f["path"], prefixes), f["path"]
            assert f["sha256_at_frozen_commit"] == frozen[f["path"]], f["path"]
            chain = chains.setdefault(f["path"], [f["sha256_at_frozen_commit"]])
            assert f.get("sha256_superseded", f["sha256_at_frozen_commit"]) == chain[-1], \
                f"{f['path']}: {s['id']} does not replace the current pin"
            chain.append(f["sha256_superseding"])
        for directory, names in s["file_set_additions"].items():
            assert directory in claims["tree_binding"]["exact_file_sets"], directory
            assert not set(names) & set(claims["tree_binding"]["exact_file_sets"][directory])
        assert {c["id"] for c in s["claims_assessed"]} <= set(claim)
        for c in s.get("claims_superseded", []):
            assert claim[c["id"]]["status"] == c["frozen_status"], c["id"]
        assert {x["id"] for x in s.get("exceptions_assessed", [])} <= set(by_id(exceptions, "exceptions"))
    for path, chain in chains.items():
        assert chain[-1] == sha256(REPO_ROOT / path), f"{path}: the end of its supersession chain is not the tree"


def test_without_the_generator_supersession_the_implemented_picogk_fails_closed(monkeypatch):
    """SUP-2026-10-08-01 is the only thing that excuses the implemented PicoGK generator.
    Without it, every file it supersedes, the new file names and the PicoGK refusal check
    fail again."""
    monkeypatch.delitem(SUPERSESSION_SHA256, "SUP-2026-10-08-01-picogk-generator.json")
    claims, exceptions = claim_register(), exception_register()
    problems = digest_problems(claims, exceptions)
    for name in ("Program.cs", "Object001Package.cs", "driver.py", "README.md"):
        assert f"geometry/package_picogk/{name}: changed since the frozen commit" in problems
    assert any(p.startswith("geometry/package_picogk/: holds") for p in problems)
    assert "REL-BD-03" not in superseded_claims()
    assert "geometry/package_picogk/Program.cs: bytes differ from the register pin; refusal code not executed" \
        in unsupported_problems(claims)


def test_a_supersession_excuses_only_the_files_it_names(tmp_path: Path):
    """Another bound file that drifts still fails, and a superseded file that drifts again
    (bytes no longer equal to the superseding digest) fails too."""
    claims, exceptions = claim_register(), exception_register()
    c = copy.deepcopy(claims)
    entry = next(e for e in by_id(c, "claims")["REL-BD-03"]["evidence"]
                 if e["path"] == "geometry/package_picogk/Program.cs")
    entry["sha256_at_frozen_commit"] = "0" * 64
    assert digest_problems(c, exceptions) == ["geometry/package_picogk/Program.cs: changed since the frozen commit"]
    c = copy.deepcopy(claims)
    entry = next(e for e in by_id(c, "claims")["REL-BD-03"]["evidence"]
                 if e["path"] == "geometry/package_picogk/README.md")
    entry["sha256_at_frozen_commit"] = "1" * 64   # no longer the digest the supersession quotes
    assert digest_problems(c, exceptions) == ["geometry/package_picogk/README.md: changed since the frozen commit"]
    copied = tmp_path / "geometry" / "package_picogk"
    shutil.copytree(REPO_ROOT / "geometry" / "package_picogk", copied,
                    ignore=shutil.ignore_patterns("__pycache__", "bin", "obj"))
    (copied / "extra.cs").write_text("// not named by any supersession\n")
    assert [p.split(":")[0] for p in file_set_problems(claims, tmp_path)
            if p.startswith("geometry/package_picogk/")] == ["geometry/package_picogk/"]


def test_corrections_quote_an_earlier_supersession_verbatim():
    """SUP-2026-10-09-01 corrects the win-x64 statements of SUP-2026-10-08-01, which is
    untouched: the generator's only recorded runs are on osx-arm64."""
    records = supersessions()
    assert correction_problems(records) == []
    corrected = {(c["record"], c["field"]) for s in records for c in s.get("corrections", [])}
    assert corrected == {("SUP-2026-10-08-01", "claims_superseded[0].on_this_tree"),
                         ("SUP-2026-10-08-01", "exceptions_assessed[0].assessment")}


def test_a_misquoted_or_misdirected_correction_is_refused():
    records = supersessions()
    i = next(n for n, s in enumerate(records) if s.get("corrections"))
    good = records[i]["corrections"][0]
    bad = {
        "misquoted": dict(good, original_excerpt=good["original_excerpt"].replace("win-x64", "win-arm64")),
        "a fragment": dict(good, original_excerpt="win-x64"),
        "a missing field": dict(good, field="claims_superseded[5].on_this_tree"),
        "a malformed path": dict(good, field="claims_superseded[0]..on_this_tree"),
        "not text": dict(good, field="claims_superseded[0]"),
        "its own record": dict(good, record=records[i]["id"]),
        "an unpinned record": dict(good, record="SUP-2099-01-01-01"),
        "no correction": dict(good, corrected=" "),
        "no reason": {k: v for k, v in good.items() if k != "what_was_wrong"},
    }
    for name, correction in bad.items():
        mutated = copy.deepcopy(records)
        mutated[i]["corrections"] = [correction]
        assert correction_problems(mutated), name


def test_without_the_correction_supersession_the_corrected_readme_fails(monkeypatch):
    """SUP-2026-10-09-01 links the PicoGK README's chain; without it the later pin
    (SUP-2026-10-11-01) no longer continues the chain, so the README fails."""
    monkeypatch.delitem(SUPERSESSION_SHA256, "SUP-2026-10-09-01-picogk-windows-correction.json")
    assert "geometry/package_picogk/README.md: changed since the frozen commit" \
        in digest_problems(claim_register(), exception_register())
    assert "REL-BD-03" in superseded_claims()   # still declared by SUP-2026-10-08-01 alone


def test_without_the_windows_ci_supersession_the_current_readme_fails(monkeypatch):
    """SUP-2026-10-11-01 pins the README that records the first Windows run."""
    monkeypatch.delitem(SUPERSESSION_SHA256, "SUP-2026-10-11-01-picogk-windows-ci.json")
    assert "geometry/package_picogk/README.md: changed since the frozen commit" \
        in digest_problems(claim_register(), exception_register())


def test_the_registers_parse_strictly_and_are_well_formed():
    claims, exceptions = claim_register(), exception_register()
    assert structure_problems(claims, exceptions) == []


def test_every_cited_path_exists_and_every_bound_digest_still_matches():
    assert digest_problems(claim_register(), exception_register()) == []


def test_the_record_set_agrees_with_the_frozen_evidence_guard():
    """In-scope records, quarantines and launcher registers are the ones the frozen-evidence
    guard enforces, and no record has joined a release-scope family unannounced."""
    on_disk = {p.name for p in RESULTS.iterdir() if p.is_dir()}
    assert record_set_problems(claim_register(), exception_register(), on_disk) == []


def test_the_palace_claims_match_the_records():
    assert palace_fact_problems(claim_register()) == []


def test_the_qutip_claims_match_the_record_and_recompute():
    assert qutip_fact_problems(claim_register()) == []


def test_the_qutip_classification_is_never_collapsed_into_an_overall_pass():
    claims, exceptions = claim_register(), exception_register()
    assert by_id(claims, "claims")["REL-QT-01"]["classification"] == QUTIP_CLASSIFICATION
    assert "PASS 11/11" in tfe.LAUNCHER_REGISTERED_CLASS[X]
    assert "QUALIFIED (resource-limit deviation)" in tfe.LAUNCHER_REGISTERED_CLASS[X]
    assert language_problems(claims, exceptions) == []
    for name in ("RELEASE-SCOPE.md", "STATUS-ADDENDUM-2026-09-26.md"):
        text = " ".join((RELEASE / name).read_text().split())
        assert "not an unqualified overall scientific PASS" in text, name
        assert "QUALIFIED: RESOURCE-LIMIT DEVIATION" in text, name


def test_the_unsupported_paths_refuse_here():
    """What this shows, exactly: the registry-resolved openEMS adapter refuses with no runtime
    and with a fake runtime path; the package-level planar cells raise unconditionally; the
    PicoGK sources are still the stub. The bytes and file sets are bound by the digest checks."""
    assert unsupported_problems(claim_register()) == []


def test_the_host_side_split_matches_the_records():
    assert host_split_problems(exception_register()) == []


# --- negative controls -------------------------------------------------------------------

def test_strict_loading_refuses_duplicate_keys_and_non_finite_numbers():
    with pytest.raises(ValueError):
        load_strict('{"a": 1, "a": 2}')
    with pytest.raises(ValueError):
        load_strict('{"a": NaN}')
    assert load_strict('{"a": 1}') == {"a": 1}


def test_the_structure_check_rejects_each_malformation():
    claims, exceptions = claim_register(), exception_register()

    def mutated(fn):
        c, x = copy.deepcopy(claims), copy.deepcopy(exceptions)
        fn(c, x)
        return structure_problems(c, x)

    assert mutated(lambda c, x: c.__setitem__("frozen_from_commit", "0" * 40))
    assert mutated(lambda c, x: c["claims"][0].__setitem__("status", "PASS"))
    qualified = next(i for i, k in enumerate(claims["claims"]) if k["status"] == "QUALIFIED")
    assert mutated(lambda c, x: c["claims"][qualified].__setitem__("limitations", []))
    assert mutated(lambda c, x: c["claims"][1].__setitem__("id", c["claims"][0]["id"]))
    assert mutated(lambda c, x: x["exceptions"][0].__setitem__("disposition", "WAIVED"))
    assert mutated(lambda c, x: c["claims"][0]["limitations"].append("see EXC-Z99"))
    assert mutated(lambda c, x: c["claims"][0].__setitem__("evidence", []))
    qt01 = next(i for i, k in enumerate(claims["claims"]) if k["id"] == "REL-QT-01")
    assert mutated(lambda c, x: c["claims"][qt01].__setitem__("status", "VERIFIED"))
    qn7 = next(i for i, k in enumerate(claims["claims"]) if k["id"] == "REL-QT-QN7")
    assert mutated(lambda c, x: c["claims"][qn7].__setitem__("status", "VERIFIED"))


def test_the_language_check_rejects_an_unnegated_overall_pass_or_memory_claim():
    claims, exceptions = claim_register(), exception_register()
    for bad in ("The execution is an overall scientific PASS.",
                "The launcher enforced a 1 GiB total-memory limit.",
                "The launcher enforced a 1 GiB memory limit.",
                "The checker ran under a 1024 MiB memory cap.",
                "g = 0.150 GHz is the geometry-derived coupling.",
                "The differences are an error bound.",
                "No errors were reported, so the execution is an overall scientific PASS.",
                "The run was not repeated; g = 0.150 GHz is geometry-derived."):
        c = copy.deepcopy(claims)
        c["claims"][0]["limitations"].append(bad)
        assert language_problems(c, exceptions), bad
        assert language_problems(claims, exceptions, markdown={"x.md": bad}), bad
    c = copy.deepcopy(claims)
    c["claims"][0]["limitations"].append("This is not an overall scientific PASS.")
    assert language_problems(c, exceptions) == []
    quoted = "The old page said “the execution is an overall scientific PASS”, which is superseded."
    assert language_problems(claims, exceptions, markdown={"x.md": quoted}) == []


def test_the_digest_check_rejects_a_changed_record_or_a_changed_bound_file():
    claims, exceptions = claim_register(), exception_register()
    c = copy.deepcopy(claims)
    c["in_scope_records"][0]["register_sha256"] = "0" * 64
    assert digest_problems(c, exceptions) == [f"{c['in_scope_records'][0]['record']}: register changed since the frozen commit"]
    c = copy.deepcopy(claims)
    entry = c["in_scope_qutip_files"][0]
    entry["sha256_at_frozen_commit"] = "0" * 64
    assert digest_problems(c, exceptions) == [f"{entry['path']}: changed since the frozen commit"]
    c = copy.deepcopy(claims)
    c["claims"][0]["evidence"].append({"path": "results/NO-SUCH-RECORD/x.json"})
    assert digest_problems(c, exceptions) == ["results/NO-SUCH-RECORD/x.json: cited but missing"]
    x = copy.deepcopy(exceptions)
    quoted = next(e for e in x["exceptions"] if e.get("quotes"))
    quoted["quotes"][0]["text"] = "text that was never there"
    assert digest_problems(claims, x) == [f"{quoted['id']}: quoted text no longer in {quoted['quotes'][0]['path']}"]


def test_the_fact_checks_reject_a_misstated_fact():
    claims = claim_register()
    c = copy.deepcopy(claims)
    by_id(c, "claims")["REL-PAL-02"]["facts"]["worst_relative_deviation"] = 4.7e-05
    assert any(p.startswith("REL-PAL-02") for p in palace_fact_problems(c))
    c = copy.deepcopy(claims)
    by_id(c, "claims")["REL-PAL-08"]["recorded_verdicts"]["PALACE-VERIFY-20260915T065055Z"] = "BLOCKED"
    assert any(p.startswith("REL-PAL-08") for p in palace_fact_problems(c))
    c = copy.deepcopy(claims)
    groups = by_id(c, "claims")["REL-PAL-04"]["facts"]["eig_csv_sha256_groups"]
    groups[0]["records"].append(groups[1]["records"].pop())
    assert any(p.startswith("REL-PAL-04") for p in palace_fact_problems(c))
    c = copy.deepcopy(claims)
    by_id(c, "claims")["REL-QT-02"]["facts"]["checks"]["f8_weight"]["value"] = 0.0
    assert any(p.startswith("REL-QT-02") for p in qutip_fact_problems(c))
    c = copy.deepcopy(claims)
    by_id(c, "claims")["REL-QT-05"]["facts"]["blocked"]["attempt_consumed"] = True
    assert any(p.startswith("REL-QT-05") for p in qutip_fact_problems(c))
    c = copy.deepcopy(claims)
    by_id(c, "claims")["REL-QT-07"]["facts"]["coupling_is_geometry_derived"] = True
    assert any(p.startswith("REL-QT-07") for p in qutip_fact_problems(c))
    x = copy.deepcopy(exception_register())
    by_id(x, "exceptions")["EXC-P02"]["host_side_split"]["collision_measured_groups"][0]["value"] = 98.41316039467607
    assert host_split_problems(x)
    for key, value in (("mpi_processes", 1.0), ("run_returncode", False)):  # equal under ==, not here
        c = copy.deepcopy(claims)
        by_id(c, "claims")["REL-PAL-01"]["facts"][key] = value
        assert any(p.startswith("REL-PAL-01") for p in palace_fact_problems(c)), key


def mirror(tmp_path: Path, copied: set[str]) -> Path:
    """A results root that links every record except the named ones, which are copied."""
    root = tmp_path / "root"
    (root / "results").mkdir(parents=True)
    for record in RESULTS.iterdir():
        if record.is_dir():
            target = root / "results" / record.name
            if record.name in copied:
                shutil.copytree(record, target)
            else:
                target.symlink_to(record, target_is_directory=True)
    return root


def test_the_palace_fact_check_reads_the_records_not_the_register(tmp_path: Path):
    """Mutating a copy of one golden record, never the committed one, is caught."""
    name = "PALACE-GOLDEN-20260915T014639Z"
    root = mirror(tmp_path, {name})
    claims = claim_register()
    assert palace_fact_problems(claims, root) == []
    solver = root / "results" / name / "QMHP-CEM-A-RF-000001" / "solver"
    with (solver / "palace_log.txt").open("a") as fh:
        fh.write("Warning: synthetic line added by a negative control\n")
    assert any("warning" in p for p in palace_fact_problems(claims, root))
    record = root / "results" / name / "execution_record.json"
    er = json.loads(record.read_text())
    er["analytic_check"]["modes"][0]["palace_GHz"] += 1e-6
    record.write_text(json.dumps(er))
    assert any("analytic_check compares other frequencies" in p for p in palace_fact_problems(claims, root))


def test_the_record_set_check_allows_outside_records_and_catches_family_ones():
    claims, exceptions = claim_register(), exception_register()
    on_disk = {p.name for p in RESULTS.iterdir() if p.is_dir()}
    assert record_set_problems(claims, exceptions, on_disk) == []
    new_golden, new_q = "PALACE-GOLDEN-20990101T000000Z", "QUTIP-A-FUTURE-20990101T000000Z"
    assert not {new_golden, new_q} & (ADDED_AFTER_FREEZE | on_disk), "control names must be unused"
    assert record_set_problems(claims, exceptions, on_disk | {new_golden})
    assert record_set_problems(claims, exceptions, on_disk | {new_golden},
                               added_after=ADDED_AFTER_FREEZE | {new_golden}) == []
    outside_q = dict(tfe.QUARANTINED, **{"COUPLED-FUTURE-20990101T000000Z": {}})
    assert record_set_problems(claims, exceptions, on_disk | {"COUPLED-FUTURE-20990101T000000Z"},
                               quarantined=outside_q) == []
    launcher = dict(tfe.LAUNCHER_REGISTERED, **{new_q: ("launcher-manifest.sha256", "0" * 64)})
    assert record_set_problems(claims, exceptions, on_disk | {new_q}, launcher=launcher)
    assert record_set_problems(claims, exceptions, on_disk | {new_q}, launcher=launcher,
                               added_after=ADDED_AFTER_FREEZE | {new_q}) == []
    tampered = dict(tfe.LAUNCHER_REGISTERED)
    tampered[X] = (tampered[X][0], "0" * 64)
    assert record_set_problems(claims, exceptions, on_disk, launcher=tampered)


def test_the_file_set_check_rejects_a_second_ledger_or_a_new_implementation_file(tmp_path: Path):
    claims = claim_register()
    for directory in claims["tree_binding"]["exact_file_sets"]:
        shutil.copytree(REPO_ROOT / directory, tmp_path / directory,
                        ignore=shutil.ignore_patterns("__pycache__"))
    assert file_set_problems(claims, tmp_path) == []
    ledger = tmp_path / "experiments/qutip-a-readout-crosscheck/ATTEMPT-LEDGER.QUTIP-A-READOUT-CROSSCHECK-v1-110a2e0-attempt2.json"
    ledger.write_text("{}\n")
    assert [p.split(":")[0] for p in file_set_problems(claims, tmp_path)] == ["experiments/qutip-a-readout-crosscheck/"]
    ledger.unlink()
    (tmp_path / "solvers/openems/working.py").write_text("# an implementation added beside the adapter\n")
    assert [p.split(":")[0] for p in file_set_problems(claims, tmp_path)] == ["solvers/openems/"]


def test_the_refusal_check_notices_an_implementation_without_launching_it(monkeypatch):
    """A registry override, a process launch and an exported replacement are each reported,
    and the launch is blocked, not performed. A changed pin stops execution entirely."""
    import subprocess
    import solvers.adapter as registry
    from solvers.openems import adapter as openems
    import geometry.chip_planar as planar

    launched = []

    class Implemented(openems.OpenemsSolver):
        def preflight(self):
            launched.append("preflight")
            subprocess.run(["true"], check=False)  # must be blocked by unsupported_problems

        def run(self, prepared):
            return None

    monkeypatch.setitem(registry._REGISTRY, "openems", Implemented)
    problems = unsupported_problems(claim_register())
    assert any("registry resolves 'openems'" in p for p in problems)
    assert any("preflight attempted to launch a process" in p for p in problems)
    assert any("run did not refuse" in p for p in problems)
    assert launched and all(p == "preflight" for p in launched)
    monkeypatch.undo()
    monkeypatch.setattr(planar, "readout_resonator", lambda candidate: object())
    assert unsupported_problems(claim_register()) == [
        "planar readout_resonator exported by the package is not the cells function",
        "planar readout_resonator did not raise PlanarGeometryNotImplemented"]
    monkeypatch.undo()
    claims = claim_register()
    entry = next(e for e in by_id(claims, "claims")["REL-BD-01"]["evidence"]
                 if e["path"] == "solvers/openems/adapter.py")
    entry["sha256_at_frozen_commit"] = "0" * 64
    assert unsupported_problems(claims) == [
        "solvers/openems/adapter.py: bytes differ from the register pin; refusal code not executed"]
