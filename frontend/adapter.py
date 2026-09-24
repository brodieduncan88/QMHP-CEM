# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The read-only data adapter.

Parses what the repository already holds - results/ records, experiments/,
approval files, manifests, the frozen master layer and documents - into the
views the frontend displays. Every method is a read. Hash verification
re-measures bytes and compares them with what a manifest declares; it records
nothing.

What this module will not do, by construction
---------------------------------------------
* write, move or delete any file (all I/O goes through ``repo_fs``);
* import or call solver, orchestrator, evaluator, geometry, model or
  experiment code;
* start a process, a shell, a container or a git command;
* create, modify, consume or validate an approval.

Actions that would need any of those are listed by ``capabilities()`` as
unavailable, with the reason.
"""

from __future__ import annotations

import json
import math
import re
import threading
from datetime import datetime, timezone
from typing import Any

from . import classify
from .repo_fs import AccessDenied, NotFound, ReadOnlyRepo, TooLarge

try:  # PyYAML is already a locked project dependency; the viewer degrades without it.
    import yaml as _yaml
except ImportError:  # pragma: no cover - exercised only outside the locked env
    _yaml = None

_RECORD_ID = re.compile(r"^(?P<family>.+?)-(?P<ts>\d{8}T\d{6}Z)$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,199}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_LINE = re.compile(r"^(?P<hash>[0-9a-fA-F]{64})\s+\*?(?P<path>.+?)\s*$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")

PRIMARY_DOCS = ("summary.json", "execution_record.json", "batch_report.json",
                "corrective_analysis.json")
TEXT_SUFFIXES = (".json", ".md", ".yaml", ".yml", ".txt", ".sha256", ".csv", ".py",
                 ".toml", ".cs", ".csproj", ".svg", ".msh", ".log", ".cfg", ".ini")
SEARCH_SUFFIXES = (".json", ".md", ".yaml", ".yml", ".txt", ".sha256")
SEARCH_FILE_LIMIT = 1024 * 1024

#: Top-level entries the file viewer serves. Anything else is refused.
SERVABLE_TOP = frozenset({
    "results", "experiments", "docs", "master", "manifests", "config", "contracts",
    "reference", "sweeps", "evaluator", "models", "orchestrator", "solvers", "geometry",
    "scripts", "tools", "tests", "docker", ".github", "frontend",
    "README.md", "QMHP-CEM_v0.1_Spec.md", "CLAUDE.md", "AGENTS.md", "LICENSE",
    "pyproject.toml",
})

HARDWARE_DISCLAIMER = ("A computational PASS is not hardware validation. Hardware-dependent "
                       "gates remain HARDWARE-GATED until legitimate measured evidence is "
                       "supplied.")

#: Things a reader might expect a research dashboard to do, and why this one cannot.
UNAVAILABLE_ACTIONS = (
    ("Run an experiment", "execution"),
    ("Run a solver", "execution"),
    ("Launch a Palace run", "execution"),
    ("Run Route A", "execution"),
    ("Execute E1", "execution"),
    ("Dispatch a GitHub workflow", "execution"),
    ("Create, grant, consume or edit an approval", "approval"),
    ("Edit a contract, predeclaration or config", "mutation"),
    ("Edit or annotate results, evidence, manifests or provenance", "mutation"),
    ("Write to results/, experiments/, docs/ or manifests/", "mutation"),
    ("Commit, push, branch, merge or open/close a PR", "git"),
)
_REASONS = {
    "execution": "This viewer has no execution path. Any consequential run needs the "
                 "repository's approved launcher and an explicit, scoped human approval, "
                 "outside this viewer.",
    "approval": "Approvals are human decisions recorded in the repository. The viewer "
                "displays approval files; it cannot create, alter, consume or validate one.",
    "mutation": "The repository is treated as an immutable evidence source. Corrections are "
                "made as new linked records through the normal review process, not here.",
    "git": "The viewer reads which commit is checked out from git's files and never runs "
           "git. It cannot change repository history or branches.",
}


def json_safe(obj: Any) -> Any:
    """Replace non-finite floats, which JSON cannot carry, with labelled strings.

    Only the parsed view is changed. The file viewer always offers the exact
    raw text alongside."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return "NaN" if math.isnan(obj) else ("Infinity" if obj > 0 else "-Infinity")
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


def _parse_ts(value: Any) -> str | None:
    """An ISO-8601 UTC string for a timestamp-like value, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    m = re.match(r"^(\d{8})T(\d{6})Z$", value)
    if m:
        d, t = m.groups()
        return f"{d[:4]}-{d[4:6]}-{d[6:]}T{t[:2]}:{t[2:4]}:{t[4:]}Z"
    if _ISO.match(value):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:10] if re.match(r"^\d{4}-\d{2}-\d{2}$", value[:10]) else None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def _excerpt(value: Any, limit: int = 600) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(json_safe(value), ensure_ascii=False, indent=1)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _file_kind(path: str) -> str:
    low = path.lower()
    if low.endswith(".json"):
        return "json"
    if low.endswith(".md"):
        return "markdown"
    if low.endswith((".yaml", ".yml")):
        return "yaml"
    if low.endswith(".sha256"):
        return "manifest"
    if low.endswith(TEXT_SUFFIXES) or "." not in low.rsplit("/", 1)[-1]:
        return "text"
    return "binary"


class ReadOnlyAdapter:
    """GET-shaped views over one repository checkout. No method writes."""

    def __init__(self, root: str) -> None:
        self.repo = ReadOnlyRepo(root)
        self._lock = threading.Lock()
        self._index: dict | None = None
        self._fingerprint: tuple | None = None
        self._search_corpus: list[tuple[str, str]] | None = None

    # ============================================================== index
    def _current_fingerprint(self) -> tuple:
        parts = ("results", "experiments", "docs", "master", ".github", "manifests")
        stamps = tuple(self.repo.mtime_ns(p) for p in parts)
        head = self.repo.checkout().get("head_sha")
        return stamps + (head,)

    def index(self) -> dict:
        with self._lock:
            fp = self._current_fingerprint()
            if self._index is None or fp != self._fingerprint:
                self._index = self._build_index()
                self._fingerprint = fp
                self._search_corpus = None
            return self._index

    def _load_json(self, rel: str) -> tuple[Any, str | None]:
        try:
            return self.repo.read_json(rel), None
        except TooLarge:
            return None, "too large to parse"
        except (ValueError, UnicodeDecodeError) as exc:
            return None, f"not valid JSON: {exc.__class__.__name__}"
        except (NotFound, AccessDenied, OSError) as exc:
            return None, str(exc)

    def _build_index(self) -> dict:
        records = self._scan_records()
        experiments = self._scan_experiments()
        record_ids = {r["id"] for r in records}
        # cross-links: which experiments name which records
        for exp in experiments:
            exp["linked_records"] = sorted(i for i in exp.pop("_mentions") if i in record_ids)
        by_id = {r["id"]: r for r in records}
        for exp in experiments:
            for rid in exp["linked_records"]:
                by_id[rid]["referenced_by"].append(f"experiments/{exp['id']}")
        for rec in records:
            rec["links"] = sorted(i for i in rec.pop("_mentions") if i in record_ids and i != rec["id"])
            for rid in rec["links"]:
                by_id[rid]["referenced_by"].append(f"results/{rec['id']}")
        for rec in records:
            rec["referenced_by"] = sorted(set(rec["referenced_by"]))
        approvals = self._scan_approvals()
        return {"records": records, "experiments": experiments, "approvals": approvals,
                "by_id": by_id}

    # ------------------------------------------------------------ records
    def _scan_records(self) -> list[dict]:
        if not self.repo.is_dir("results"):
            return []
        out = []
        for name, is_dir in self.repo.list_dir("results"):
            if is_dir and _SAFE_ID.match(name):
                out.append(self._record_summary(name))
        out.sort(key=lambda r: (r["timestamp"] or "", r["id"]), reverse=True)
        return out

    def _record_summary(self, rid: str) -> dict:
        base = f"results/{rid}"
        m = _RECORD_ID.match(rid)
        family = m.group("family") if m else rid
        top = self.repo.list_dir(base)
        top_files = [n for n, d in top if not d]
        subdirs = [n for n, d in top if d]
        files = self.repo.walk_files(base, max_depth=6)

        docs: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for fname in top_files:
            if fname.endswith(".json"):
                doc, err = self._load_json(f"{base}/{fname}")
                if err:
                    errors[fname] = err
                else:
                    docs[fname] = doc
        primary_name = next((n for n in PRIMARY_DOCS if n in docs), None)
        primary = docs.get(primary_name) if primary_name else None

        candidates = []
        for sub in subdirs:
            if self.repo.is_file(f"{base}/{sub}/candidate.json") or \
                    self.repo.is_file(f"{base}/{sub}/gate_report.json"):
                candidates.append(self._candidate(rid, sub))
        for cand in candidates:
            if cand.get("_gate_doc") is not None:
                docs[f"{cand['candidate_dir']}/gate_report.json"] = cand["_gate_doc"]
            if cand.get("_solver_doc") is not None:
                docs[f"{cand['candidate_dir']}/solver/solver_results.json"] = cand["_solver_doc"]

        basis = classify.classify_record(rid, docs, files)
        headline = classify.headline_statuses(primary) if primary is not None else []
        statuses = []
        for fname, doc in docs.items():
            for item in classify.all_statuses(doc):
                item = dict(item, file=fname)
                statuses.append(item)
        families = sorted({f for s in statuses for f in s["families"]} |
                          {f for s in headline for f in s["families"]})

        ts = None
        if isinstance(primary, dict):
            for key in ("started_utc", "generated_utc", "ended_utc"):
                ts = _parse_ts(primary.get(key))
                if ts:
                    break
        if ts is None and m:
            ts = _parse_ts(m.group("ts"))

        statement = None
        if isinstance(primary, dict):
            for key in ("statement", "note", "what"):
                if isinstance(primary.get(key), str):
                    statement = primary[key]
                    break

        # Only files named *manifest.sha256 are byte manifests. Other .sha256 files may
        # digest something other than the bytes beside them (PALACE-VERIFY's
        # campaign.sha256 digests the definition's canonical JSON form), so they are
        # shown as declared digests and never byte-compared.
        manifests = [f for f in files if f.endswith("manifest.sha256") and "/solver/" not in f]
        digest_files = [f for f in files if f.endswith(".sha256") and f not in manifests
                        and "/solver/" not in f]
        runs = self._runs(primary)
        mentions = set()
        for doc in docs.values():
            for _p, v in classify.walk(doc, max_depth=5):
                if isinstance(v, str):
                    for token in re.findall(r"[A-Z][A-Z0-9\-]+-\d{8}T\d{6}Z", v):
                        mentions.add(token)
        return {
            "id": rid, "family": family, "timestamp": ts, "path": base,
            "basis": basis, "headline": headline, "families": families,
            "statement": statement, "primary": f"{base}/{primary_name}" if primary_name else None,
            "report": f"{base}/report.md" if "report.md" in top_files else None,
            "manifests": manifests, "digest_files": digest_files, "file_count": len(files),
            "files": files[:400], "files_truncated": len(files) > 400,
            "candidates": [{k: v for k, v in c.items() if not k.startswith("_")} for c in candidates],
            "runs": runs, "parse_errors": errors, "referenced_by": [],
            "_statuses": statuses, "_mentions": mentions,
            "computational_only": basis["basis"] != "MEASURED",
        }

    def _candidate(self, rid: str, sub: str) -> dict:
        base = f"results/{rid}/{sub}"
        cand, _ = self._load_json(f"{base}/candidate.json") if self.repo.is_file(f"{base}/candidate.json") else (None, None)
        gate, _ = self._load_json(f"{base}/gate_report.json") if self.repo.is_file(f"{base}/gate_report.json") else (None, None)
        solver, _ = (self._load_json(f"{base}/solver/solver_results.json")
                     if self.repo.is_file(f"{base}/solver/solver_results.json") else (None, None))
        gates = []
        if isinstance(gate, dict):
            for g in gate.get("gates", []) or []:
                if isinstance(g, dict):
                    row = {k: g.get(k) for k in ("gate_id", "status", "severity",
                           "hardware_required", "evidence_class", "reason", "measured",
                           "threshold", "margin", "units", "spec_section")}
                    row["tone"] = classify.token_tone(row["status"])
                    gates.append(row)
        solver_id = None
        synthetic = None
        convergence = None
        if isinstance(solver, dict):
            sid = solver.get("solver")
            if isinstance(sid, dict):
                solver_id = {k: sid.get(k) for k in ("name", "version", "classification", "image_digest")}
            synthetic = solver.get("synthetic")
            conv = solver.get("convergence")
            if isinstance(conv, dict):
                convergence = conv.get("status")
        return {
            "record_id": rid, "candidate_dir": sub,
            "candidate_id": (cand or {}).get("candidate_id", sub) if isinstance(cand, dict) else sub,
            "classification": (cand or {}).get("classification") if isinstance(cand, dict) else None,
            "overall_status": gate.get("overall_status") if isinstance(gate, dict) else None,
            "overall_tone": classify.token_tone(gate.get("overall_status")) if isinstance(gate, dict) else "neutral",
            "gates": gates, "solver": solver_id, "synthetic": synthetic,
            "convergence": convergence, "path": base,
            "_gate_doc": gate, "_solver_doc": solver,
        }

    @staticmethod
    def _runs(primary: Any) -> list[dict]:
        runs = primary.get("runs") if isinstance(primary, dict) else None
        out = []
        if isinstance(runs, dict):
            for name, run in runs.items():
                if isinstance(run, dict):
                    status = run.get("status") or run.get("status_as_executed")
                    status = status if isinstance(status, str) else None
                    out.append({"name": name, "status": status,
                                "palace_status": run.get("palace_status"),
                                "tokens": classify.leading_tokens(status) if status else [],
                                "tone": classify.token_tone(status)})
        return out

    # -------------------------------------------------------- experiments
    _ROLE_RULES = (
        (re.compile(r"(^|/)WITHDRAWN\.json$"), "withdrawal"),
        (re.compile(r"(^|/)ATTEMPT-SPENT\.json$"), "attempt-spent"),
        (re.compile(r"(^|/)EXECUTION-LOG\.json$"), "execution-log"),
        (re.compile(r"approval", re.I), "approval"),
        (re.compile(r"(^|/)(predeclaration|proposal)\.json$"), "predeclaration"),
        (re.compile(r"(^|/)(candidate|config\.candidate|inputs)\.json$|config\.delta\.txt$"), "frozen-configuration"),
        (re.compile(r"(^|/)review/"), "review"),
        (re.compile(r"\.md$"), "documentation"),
        (re.compile(r"\.py$"), "code"),
        (re.compile(r"\.sha256$"), "manifest"),
    )

    def _role(self, rel_in_exp: str) -> str:
        for pattern, role in self._ROLE_RULES:
            if pattern.search(rel_in_exp):
                return role
        return "data"

    def _scan_experiments(self) -> list[dict]:
        if not self.repo.is_dir("experiments"):
            return []
        out = []
        for name, is_dir in self.repo.list_dir("experiments"):
            if is_dir and _SAFE_ID.match(name):
                out.append(self._experiment(name))
        return out

    def _experiment(self, name: str) -> dict:
        base = f"experiments/{name}"
        files = self.repo.walk_files(base, max_depth=5)
        entries = []
        docs: dict[str, Any] = {}
        mentions: set[str] = set()
        for path in files:
            inner = path[len(base) + 1:]
            role = self._role(inner)
            entry = {"path": path, "name": inner, "role": role, "size": self.repo.size(path)}
            if path.endswith(".json") and entry["size"] <= 4 * 1024 * 1024:
                doc, err = self._load_json(path)
                if err is None:
                    docs[inner] = doc
                    for _p, v in classify.walk(doc, max_depth=5):
                        if isinstance(v, str):
                            mentions.update(re.findall(r"[A-Z][A-Z0-9\-]+-\d{8}T\d{6}Z", v))
                    if isinstance(doc, dict):
                        heads = classify.headline_statuses(doc)
                        if heads:
                            entry["statuses"] = heads
                else:
                    entry["parse_error"] = err
            entries.append(entry)
        roles = {e["role"] for e in entries}
        state = self._experiment_state(entries, docs)
        basis = classify.classify_experiment(name, docs)
        readme = next((e["path"] for e in entries if e["name"].lower() == "readme.md"), None)
        pre = next((e for e in entries if e["role"] == "predeclaration"), None)
        question = None
        if pre and isinstance(docs.get(pre["name"]), dict):
            q = docs[pre["name"]].get("question")
            question = q if isinstance(q, str) else None
        return {"id": name, "path": base, "files": entries, "roles": sorted(roles),
                "state": state, "basis": basis, "readme": readme, "question": question,
                "synthetic_files": classify.synthetic_files(docs), "_mentions": mentions}

    @staticmethod
    def _experiment_state(entries: list[dict], docs: dict[str, Any]) -> dict:
        """Execution state as the directory's own files state it, with the file."""
        names = {e["name"]: e for e in entries}
        def st(label, reason, source):
            first = label.split(" / ")[0]
            tone = "muted" if first.startswith(("NO EXECUTION", "DRAFT")) else classify.token_tone(first)
            return {"label": label, "reason": reason, "source": source, "tone": tone}
        for e in entries:
            if e["role"] == "withdrawal":
                return st("WITHDRAWN", "a WITHDRAWN record is present", e["path"])
        for e in entries:
            if e["role"] == "attempt-spent":
                return st("ATTEMPT SPENT", "the one permitted attempt is recorded as spent", e["path"])
        for e in entries:
            if e["role"] == "execution-log":
                return st("EXECUTED", "an execution log is present", e["path"])
        approvals = [e for e in entries if e["role"] == "approval"]
        live = [e for e in approvals if not _approval_state(e["name"], docs.get(e["name"]))
                .startswith(("DRAFT", "CONSUMED"))]
        if live:
            return st("APPROVAL ON FILE",
                      "an approval file is present; whether it has been used is not recorded "
                      "in this directory - see the linked results records and the audit trail",
                      live[0]["path"])
        as_written = ("as stated in this file when it was written; a later execution may be "
                      "recorded elsewhere - check the linked results records")
        for role in ("predeclaration", "frozen-configuration"):
            for e in entries:
                if e["role"] != role:
                    continue
                heads = [h for h in (e.get("statuses") or []) if h["path"] == "status"]
                toks = [t for h in heads for t in h["tokens"]]
                if toks:
                    return st(" / ".join(toks[:3]), as_written, e["path"])
                doc = docs.get(e["name"])
                if isinstance(doc, dict) and isinstance(doc.get("status"), dict) \
                        and doc["status"].get("approved") is False:
                    return st("NOT APPROVED", "status.approved is false - " + as_written, e["path"])
        if approvals:
            return st("DRAFT APPROVAL ONLY", "only draft or consumed approvals are present",
                      approvals[0]["path"])
        return st("NO EXECUTION RECORD IN DIRECTORY",
                  "no status, approval, execution log or withdrawal is present in this "
                  "directory; it holds analysis, data or code. Linked results records, if any, "
                  "are listed separately.", None)

    # ---------------------------------------------------------- approvals
    def _scan_approvals(self) -> list[dict]:
        paths = []
        for root in ("experiments", ".github", "docs"):
            if self.repo.is_dir(root):
                depth = 1 if root == ".github" else 6
                for p in self.repo.walk_files(root, max_depth=depth, skip_dirs=("workflows",)):
                    fname = p.rsplit("/", 1)[-1]
                    if "approval" in fname.lower() and fname.endswith(".json"):
                        paths.append(p)
        out = []
        for p in sorted(paths):
            doc, err = self._load_json(p)
            fname = p.rsplit("/", 1)[-1]
            state = _approval_state(fname, doc)
            item = {"path": p, "state": state, "sha256": self.repo.sha256(p), "parse_error": err,
                    "tone": "neutral" if state == "ON FILE" else "muted"}
            if isinstance(doc, dict):
                for key in ("approved_by", "approved_utc", "authorises", "scope", "what",
                            "run_label", "attempt", "not_before_utc", "not_after_utc",
                            "does_not_authorise", "how_to_grant_it", "diagnostic", "supersedes"):
                    if key in doc:
                        item[key] = json_safe(doc[key])
                one = doc.get("one_attempt")
                if isinstance(one, dict):
                    item["one_attempt"] = {k: one.get(k) for k in ("run_number", "run_attempt",
                                                                   "workflow_path", "ref")}
            out.append(item)
        return out

    # =========================================================== views
    def checkout(self) -> dict:
        return self.repo.checkout()

    def capabilities(self) -> dict:
        return {
            "read_only": True,
            "http_methods": ["GET", "HEAD"],
            "writes": "none - no endpoint, code path or mode writes to the repository",
            "unavailable": [{"action": a, "category": c, "available": False, "reason": _REASONS[c]}
                            for a, c in UNAVAILABLE_ACTIONS],
        }

    def overview(self) -> dict:
        idx = self.index()
        records, experiments = idx["records"], idx["experiments"]
        by_basis = {b: 0 for b in classify.BASES}
        by_family: dict[str, int] = {}
        for r in records:
            by_basis[r["basis"]["basis"]] += 1
            for f in {f for h in r["headline"] for f in h["families"]}:
                by_family[f] = by_family.get(f, 0) + 1
        latest: dict[str, dict] = {}
        for r in records:  # already newest first
            latest.setdefault(r["family"], _record_row(r))
        exp_states: dict[str, int] = {}
        for e in experiments:
            exp_states[e["state"]["label"]] = exp_states.get(e["state"]["label"], 0) + 1
        gates = self.gate_definitions()
        master = self.master_provenance()
        present = {d: self.repo.is_dir(d) for d in ("results", "experiments", "docs", "master",
                                                     "manifests", "contracts", "config")}
        notes = []
        if not present["experiments"]:
            notes.append("There is no experiments/ directory in this checkout. Experiments, "
                         "approvals and execution logs that exist on other branches are not "
                         "shown until they are part of the checked-out commit.")
        measured_present = by_basis["MEASURED"] > 0
        return {
            "checkout": self.checkout(),
            "disclaimer": HARDWARE_DISCLAIMER,
            "counts": {"records": len(records), "experiments": len(experiments),
                       "approvals": len(idx["approvals"]),
                       "candidates": sum(len(r["candidates"]) for r in records),
                       "corrections": len(self.corrections()["items"])},
            "by_basis": by_basis, "by_status_family": dict(sorted(by_family.items())),
            "experiment_states": exp_states,
            "measured_evidence_present": measured_present,
            "measured_statement": ("MEASURED evidence is present in at least one record." if measured_present
                                   else "No record in this checkout carries MEASURED hardware evidence. "
                                        "Everything shown is computational, synthetic, analytical or declarative."),
            "hardware_gated_gates": [g for g in gates.get("gates", []) if g.get("hardware_required")],
            "master": {k: master.get(k) for k in ("revision", "status", "date", "issues")},
            "latest_by_family": sorted(latest.values(), key=lambda r: r["timestamp"] or "", reverse=True),
            "directories_present": present, "notes": notes,
            "capabilities": self.capabilities(),
        }

    def records(self) -> dict:
        idx = self.index()
        return {"records": [_record_row(r) for r in idx["records"]],
                "rules": classify.RECORD_RULES, "families": _families_legend()}

    def record(self, rid: str) -> dict:
        idx = self.index()
        rec = idx["by_id"].get(rid)
        if rec is None:
            raise NotFound(rid)
        out = {k: v for k, v in rec.items() if not k.startswith("_")}
        out["statuses"] = rec["_statuses"][:400]
        out["declared_digests"] = self._declared_digests(rec)
        out["disclaimer"] = HARDWARE_DISCLAIMER
        return out

    def _declared_digests(self, rec: dict, limit: int = 300) -> list[dict]:
        """SHA-256 values the record's own JSON declares. Declared, not re-measured."""
        out = []
        for path in ([rec["primary"]] if rec["primary"] else []):
            doc, err = self._load_json(path)
            if err:
                continue
            for p, v in classify.walk(doc, max_depth=7):
                if isinstance(v, str):
                    hexpart = v.removeprefix("sha256:")
                    if _HEX64.match(hexpart):
                        out.append({"file": path, "path": p, "sha256": hexpart})
                        if len(out) >= limit:
                            return out
        return out

    def verify_record(self, rid: str) -> dict:
        """Re-measure every file each manifest of the record lists. Read-only."""
        idx = self.index()
        rec = idx["by_id"].get(rid)
        if rec is None:
            raise NotFound(rid)
        return self._verify_manifests(rec["path"], rec["manifests"], set(rec["files"]))

    def _verify_manifests(self, base: str, manifests: list[str], present: set[str]) -> dict:
        results = []
        listed: set[str] = set()
        for mpath in manifests:
            mdir = mpath.rsplit("/", 1)[0]
            try:
                text = self.repo.read_text(mpath)
            except (TooLarge, UnicodeDecodeError, NotFound, AccessDenied) as exc:
                results.append({"manifest": mpath, "error": str(exc), "entries": []})
                continue
            entries = []
            for n, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                m = _MANIFEST_LINE.match(line)
                if not m:
                    entries.append({"line": n, "status": "UNPARSEABLE", "text": line[:200]})
                    continue
                declared = m.group("hash").lower()
                rel = f"{mdir}/{m.group('path')}"
                listed.add(rel)
                try:
                    measured = self.repo.sha256(rel)
                    status = "MATCH" if measured == declared else "MISMATCH"
                except NotFound:
                    measured, status = None, "ABSENT FROM CHECKOUT"
                except AccessDenied:
                    measured, status = None, "REFUSED (outside the repository)"
                entries.append({"line": n, "path": rel, "declared": declared,
                                "measured": measured, "status": status})
            counts: dict[str, int] = {}
            for e in entries:
                counts[e["status"]] = counts.get(e["status"], 0) + 1
            results.append({"manifest": mpath, "entries": entries, "counts": counts})
        unlisted = sorted(p for p in present if p not in listed and p not in manifests
                          and not p.endswith(".sha256"))
        return {"base": base, "manifests": results, "unlisted_files": unlisted[:500],
                "unlisted_count": len(unlisted),
                "measured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "declared_digest_files": self._digest_files(manifests, present),
                "note": "Measured values were computed by this viewer just now from the "
                        "checked-out bytes. Declared values are what the manifest says. "
                        "Nothing was written. A MISMATCH means the checked-out bytes differ "
                        "from the declared digest; it does not by itself say why."}

    def _digest_files(self, manifests: list[str], present: set[str]) -> list[dict]:
        out = []
        for path in sorted(p for p in present if p.endswith(".sha256") and p not in manifests
                           and "/solver/" not in p):
            try:
                text = self.repo.read_text(path, limit=65536)
            except (TooLarge, UnicodeDecodeError, NotFound, AccessDenied):
                continue
            out.append({"path": path, "content": text.strip()[:2000],
                        "note": "Declared digest file. Not byte-compared: what it digests "
                                "(file bytes or a canonical form) is defined by the code that "
                                "wrote it, not by this viewer."})
        return out

    def experiments(self) -> dict:
        idx = self.index()
        rows = []
        for e in idx["experiments"]:
            rows.append({k: e[k] for k in ("id", "path", "roles", "state", "basis", "question",
                                           "linked_records")} | {"file_count": len(e["files"])})
        return {"present": self.repo.is_dir("experiments"), "experiments": rows,
                "frozen_contracts": self.frozen_contracts(), "rules": classify.EXPERIMENT_RULES}

    def experiment(self, name: str) -> dict:
        idx = self.index()
        for e in idx["experiments"]:
            if e["id"] == name:
                approvals = [a for a in idx["approvals"] if a["path"].startswith(e["path"] + "/")]
                return dict(e, approvals=approvals)
        raise NotFound(name)

    def frozen_contracts(self) -> list[dict]:
        """The frozen master layer and the code-level data contracts, as files."""
        out = []
        groups = (("master", "Frozen machine-readable requirements (authority level 3)"),
                  ("contracts", "Pydantic data contracts (code)"),
                  ("config", "Seed candidate configuration"),
                  ("sweeps", "Deterministic sweep definitions"))
        for d, label in groups:
            if not self.repo.is_dir(d):
                continue
            files = [p for p in self.repo.walk_files(d, max_depth=3)]
            out.append({"group": d, "label": label,
                        "files": [{"path": p, "size": self.repo.size(p)} for p in files]})
        if self.repo.is_file("QMHP-CEM_v0.1_Spec.md"):
            out.insert(0, {"group": "spec", "label": "Software specification (authority level 2)",
                           "files": [{"path": "QMHP-CEM_v0.1_Spec.md",
                                      "size": self.repo.size("QMHP-CEM_v0.1_Spec.md")}]})
        return out

    def candidates(self) -> dict:
        idx = self.index()
        cands, runs = [], []
        for r in idx["records"]:
            for c in r["candidates"]:
                cands.append(dict(c, basis=r["basis"], record_timestamp=r["timestamp"],
                                  family=r["family"]))
            for run in r["runs"]:
                runs.append(dict(run, record_id=r["id"], basis=r["basis"], family=r["family"],
                                 record_timestamp=r["timestamp"]))
        return {"candidates": cands, "runs": runs, "disclaimer": HARDWARE_DISCLAIMER}

    def gate_definitions(self) -> dict:
        path = "master/validation_gates.yaml"
        if not self.repo.is_file(path):
            return {"present": False, "gates": []}
        text = self.repo.read_text(path)
        if _yaml is None:
            return {"present": True, "parsed": False, "raw_path": path, "gates": []}
        try:
            doc = _yaml.safe_load(text)
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return {"present": True, "parsed": False, "error": str(exc), "gates": []}
        gates = []
        for g in (doc or {}).get("gates", []) or []:
            if isinstance(g, dict):
                allowed = g.get("allowed_statuses") or []
                gates.append(json_safe({**{k: g.get(k) for k in (
                    "gate_id", "title", "kind", "severity", "spec_section", "required_evidence",
                    "hardware_required", "allowed_statuses", "pass_condition")},
                    "pass_permitted": "PASS" in allowed}))
        return {"present": True, "parsed": True, "path": path,
                "schema": (doc or {}).get("schema"), "master_revision": (doc or {}).get("master_revision"),
                "allowed_statuses": (doc or {}).get("allowed_statuses"),
                "evidence_classes": (doc or {}).get("evidence_classes"), "gates": gates}

    def gates(self) -> dict:
        idx = self.index()
        rows = []
        for r in idx["records"]:
            for c in r["candidates"]:
                if c["gates"]:
                    rows.append({"record_id": r["id"], "candidate_id": c["candidate_id"],
                                 "candidate_dir": c["candidate_dir"], "basis": r["basis"],
                                 "overall_status": c["overall_status"], "gates": c["gates"]})
        verdicts = []
        for r in idx["records"]:
            if r["headline"]:
                verdicts.append({"record_id": r["id"], "family": r["family"], "basis": r["basis"],
                                 "timestamp": r["timestamp"], "headline": r["headline"]})
        return {"definitions": self.gate_definitions(), "results": rows,
                "record_verdicts": verdicts, "families": _families_legend(),
                "disclaimer": HARDWARE_DISCLAIMER}

    def master_provenance(self) -> dict:
        path = "master/provenance.json"
        if not self.repo.is_file(path):
            return {"present": False, "issues": []}
        doc, err = self._load_json(path)
        if err or not isinstance(doc, dict):
            return {"present": True, "error": err, "issues": []}
        checks = []
        for fname, declared in (doc.get("master_files") or {}).items():
            checks.append(self._check_digest(f"master/{fname}", declared))
        spec = doc.get("cem_spec_file")
        if isinstance(spec, str) and isinstance(doc.get("cem_spec_sha256"), str):
            checks.append(self._check_digest(spec, doc["cem_spec_sha256"]))
        issues = []
        for key, value in doc.items():
            if key.endswith("_verification") and isinstance(value, dict):
                issues.append({"field": key, "status": value.get("status"),
                               "statement": value.get("statement")})
        return {"present": True, "path": path, "revision": doc.get("qmhp_master_revision"),
                "status": doc.get("qmhp_master_status"), "date": doc.get("qmhp_master_date"),
                "evidence_boundary": doc.get("evidence_boundary"), "checks": checks,
                "issues": issues, "reference_bundle": doc.get("reference_bundle")}

    def _check_digest(self, rel: str, declared: Any) -> dict:
        try:
            measured = self.repo.sha256(rel)
            status = "MATCH" if isinstance(declared, str) and measured == declared.lower() else "MISMATCH"
        except NotFound:
            measured, status = None, "ABSENT FROM CHECKOUT"
        except AccessDenied:
            measured, status = None, "REFUSED"
        return {"path": rel, "declared": declared, "measured": measured, "status": status}

    def provenance(self) -> dict:
        idx = self.index()
        rows = []
        for r in idx["records"]:
            env = {}
            if r["primary"]:
                doc, err = self._load_json(r["primary"])
                if not err and isinstance(doc, dict):
                    e = doc.get("environment")
                    if isinstance(e, dict):
                        env = {k: e.get(k) for k in ("git_commit", "solver_identity", "solver_version",
                                                     "python_version", "os", "dependency_lock_sha256")
                               if e.get(k) is not None}
                    for k in ("campaign_sha256", "golden_sha256", "approval_sha256",
                              "predeclaration_sha256", "mesh_sha256", "manifest_sha256"):
                        if isinstance(doc.get(k), str):
                            env[k] = doc[k]
            rows.append({"record_id": r["id"], "family": r["family"], "basis": r["basis"],
                         "timestamp": r["timestamp"], "manifests": r["manifests"],
                         "file_count": r["file_count"], "environment": env})
        return {"master": self.master_provenance(), "records": rows,
                "approvals": [{k: a.get(k) for k in ("path", "state", "sha256")} for a in idx["approvals"]],
                "note": "Declared digests are what a record states. Measured digests are "
                        "recomputed by this viewer from the checked-out bytes on request. "
                        "The two are always shown separately."}

    def approvals(self) -> dict:
        return {"approvals": self.index()["approvals"],
                "statement": "Displayed only. This viewer cannot create, grant, modify, consume "
                             "or validate an approval, and showing a file here says nothing "
                             "about whether it authorises anything."}

    def audit(self) -> dict:
        """A timeline of what the repository's own records say happened, and when."""
        idx = self.index()
        events = []
        for r in idx["records"]:
            events.append({"ts": r["timestamp"], "kind": "RESULT RECORD", "ref": f"results/{r['id']}",
                           "record_id": r["id"], "basis": r["basis"]["basis"],
                           "summary": r["statement"] or "", "headline": r["headline"]})
        for a in idx["approvals"]:
            ts = _parse_ts(a.get("approved_utc")) or _parse_ts(a.get("not_before_utc"))
            events.append({"ts": ts, "kind": f"APPROVAL ({a['state']})", "ref": a["path"],
                           "summary": _excerpt(a.get("authorises") or a.get("what") or a.get("scope") or "", 300)})
        for e in idx["experiments"]:
            for f in e["files"]:
                if f["role"] not in ("execution-log", "attempt-spent", "withdrawal"):
                    continue
                doc, err = self._load_json(f["path"])
                if err or not isinstance(doc, dict):
                    continue
                if f["role"] == "execution-log":
                    events.append({"ts": _parse_ts(doc.get("start_utc")), "kind": "EXECUTION STARTED",
                                   "ref": f["path"], "experiment": e["id"],
                                   "summary": _excerpt(doc.get("invocation") or doc.get("record") or "", 300)})
                    events.append({"ts": _parse_ts(doc.get("end_utc")), "kind": "EXECUTION ENDED",
                                   "ref": f["path"], "experiment": e["id"],
                                   "summary": f"exit_code = {doc.get('exit_code')!r}"})
                elif f["role"] == "attempt-spent":
                    events.append({"ts": _parse_ts(doc.get("spent_utc")), "kind": "ATTEMPT SPENT",
                                   "ref": f["path"], "experiment": e["id"],
                                   "summary": f"record {doc.get('record')}"})
                else:
                    events.append({"ts": _parse_ts(doc.get("date")), "kind": "WITHDRAWN",
                                   "ref": f["path"], "experiment": e["id"],
                                   "summary": _excerpt(doc.get("status") or "", 300)})
        dated = sorted((e for e in events if e["ts"]), key=lambda e: e["ts"], reverse=True)
        undated = [e for e in events if not e["ts"]]
        states = [{"experiment": e["id"], **e["state"]} for e in idx["experiments"]]
        return {"events": dated + undated, "experiment_states": states,
                "checkout": self.checkout(),
                "note": "Built only from timestamps recorded inside the repository's files. "
                        "Git history and workflow run logs are not read."}

    _CORRECTION_KEYS = {"supersedes": "SUPERSESSION", "superseded_by": "SUPERSESSION",
                        "superseded_analysis": "SUPERSESSION", "correction": "CORRECTION",
                        "corrections": "CORRECTION", "bookkeeping_correction": "CORRECTION",
                        "withdrawn_claims": "WITHDRAWAL", "retraction": "RETRACTION",
                        "retracted": "RETRACTION", "errata": "CORRECTION"}
    _CORRECTION_HEADING = re.compile(
        r"^#{1,4}\s+(.*\b(corrections?|corrected|corrective|corrigend\w*|retract\w*|withdraw\w*"
        r"|supersed\w*|errat\w*)\b.*)$", re.I | re.M)

    def corrections(self) -> dict:
        """Correction, supersession, withdrawal and retraction statements, where recorded."""
        return self._memo("corrections", self._corrections)

    def _memo(self, name: str, build):
        """Derived views are cached in process memory alongside the index they came from."""
        idx = self.index()
        cache = idx.setdefault("_memo", {})
        if name not in cache:
            cache[name] = build()
        return cache[name]

    def _corrections(self) -> dict:
        idx = self.index()
        items = []
        for r in idx["records"]:
            if "-CORR-" in r["id"] or "corrective" in r["basis"]["reason"]:
                items.append({"type": "CORRECTIVE RECORD", "ref": f"results/{r['id']}",
                              "path": r["primary"], "json_path": None,
                              "excerpt": r["statement"] or "", "links": r["links"]})
            if r["primary"]:
                doc, err = self._load_json(r["primary"])
                if not err:
                    items.extend(self._correction_keys(doc, r["primary"], f"results/{r['id']}"))
        for e in idx["experiments"]:
            for f in e["files"]:
                if not f["path"].endswith(".json") or f["size"] > 4 * 1024 * 1024:
                    continue
                if f["role"] == "withdrawal":
                    doc, err = self._load_json(f["path"])
                    items.append({"type": "WITHDRAWAL", "ref": f"experiments/{e['id']}", "path": f["path"],
                                  "json_path": None,
                                  "excerpt": _excerpt((doc or {}).get("status") if isinstance(doc, dict) else "", 600),
                                  "links": e["linked_records"]})
                    continue
                doc, err = self._load_json(f["path"])
                if not err:
                    items.extend(self._correction_keys(doc, f["path"], f"experiments/{e['id']}"))
        for path in self._markdown_docs():
            if not path.startswith("docs/"):
                continue
            try:
                text = self.repo.read_text(path)
            except (TooLarge, UnicodeDecodeError, NotFound, AccessDenied):
                continue
            if "correct" in path.rsplit("/", 1)[-1].lower():
                items.append({"type": "CORRECTIVE DOCUMENT", "ref": path, "path": path,
                              "json_path": None, "excerpt": _first_paragraph(text), "links": []})
            for m in self._CORRECTION_HEADING.finditer(text):
                items.append({"type": "DOCUMENT SECTION", "ref": path, "path": path,
                              "json_path": m.group(1).strip()[:200],
                              "excerpt": _first_paragraph(text[m.end():]), "links": []})
        return {"items": items,
                "statement": "Corrections in this repository are new linked records; originals are "
                             "preserved. This list is assembled from explicit correction, "
                             "supersession, withdrawal and retraction fields and headings. It does "
                             "not read git history, so corrections stated only in commit messages "
                             "are not shown."}

    def _correction_keys(self, doc: Any, path: str, ref: str) -> list[dict]:
        out = []
        def rec(obj, prefix, depth):
            if depth > 3 or not isinstance(obj, dict):
                return
            for key, value in obj.items():
                p = f"{prefix}.{key}" if prefix else key
                if key in self._CORRECTION_KEYS and value not in (None, "", [], {}):
                    links = set()
                    for _q, v in classify.walk(value, max_depth=4):
                        if isinstance(v, str):
                            links.update(re.findall(r"[A-Z][A-Z0-9\-]+-\d{8}T\d{6}Z", v))
                    out.append({"type": self._CORRECTION_KEYS[key], "ref": ref, "path": path,
                                "json_path": p, "excerpt": _excerpt(value, 800),
                                "links": sorted(links)})
                elif isinstance(value, dict):
                    rec(value, p, depth + 1)
        rec(doc, "", 0)
        return out

    def classification(self) -> dict:
        idx = self.index()
        groups: dict[str, list] = {b: [] for b in classify.BASES}
        for r in idx["records"]:
            groups[r["basis"]["basis"]].append(_record_row(r))
        exp_groups: dict[str, list] = {}
        for e in idx["experiments"]:
            exp_groups.setdefault(e["basis"]["basis"], []).append(
                {"id": e["id"], "basis": e["basis"], "state": e["state"]})
        return {"bases": [{"basis": b, "explanation": classify.BASIS_EXPLANATIONS[b],
                           "count": len(groups[b])} for b in classify.BASES],
                "record_rules": classify.RECORD_RULES, "experiment_rules": classify.EXPERIMENT_RULES,
                "records_by_basis": groups, "experiments_by_basis": exp_groups,
                "families": _families_legend(), "disclaimer": HARDWARE_DISCLAIMER,
                "measured_statement": ("No record in this checkout declares MEASURED evidence."
                                       if not groups["MEASURED"] else
                                       f"{len(groups['MEASURED'])} record(s) declare MEASURED evidence.")}

    # ----------------------------------------------------- documents/files
    def _markdown_docs(self) -> list[str]:
        out = []
        for name, is_dir in self.repo.list_dir(""):
            if not is_dir and name.endswith(".md") and name in SERVABLE_TOP:
                out.append(name)
        for d in ("docs", "manifests", "experiments"):
            if self.repo.is_dir(d):
                out += [p for p in self.repo.walk_files(d, max_depth=6) if p.endswith(".md")]
        if self.repo.is_dir("results"):
            if self.repo.is_file("results/README.md"):
                out.append("results/README.md")
            for name, is_dir in self.repo.list_dir("results"):
                if is_dir and self.repo.is_file(f"results/{name}/report.md"):
                    out.append(f"results/{name}/report.md")
        return out

    def documents(self) -> dict:
        docs = []
        for path in self._markdown_docs():
            title = None
            try:
                head = self.repo.read_text(path, limit=TEXT_LIMIT_DOC)
                m = re.search(r"^#\s+(.+)$", head, re.M)
                title = m.group(1).strip() if m else None
            except (TooLarge, UnicodeDecodeError):
                pass
            docs.append({"path": path, "title": title, "size": self.repo.size(path)})
        return {"documents": docs}

    def file(self, rel: str) -> dict:
        top = rel.split("/", 1)[0] if rel else ""
        if top not in SERVABLE_TOP:
            raise AccessDenied("the viewer does not serve this location")
        path = self.repo.resolve(rel)
        if path.is_dir():
            entries = [{"name": n, "is_dir": d, "path": f"{rel.rstrip('/')}/{n}"}
                       for n, d in self.repo.list_dir(rel)]
            return {"path": rel, "kind": "directory", "entries": entries}
        if not path.is_file():
            raise NotFound(rel)
        size = self.repo.size(rel)
        kind = _file_kind(rel)
        out = {"path": rel, "kind": kind, "size": size, "sha256_measured": self.repo.sha256(rel),
               "content": None, "parsed": None, "truncated": False}
        if kind == "binary":
            out["note"] = "Binary file: described, not displayed."
            return out
        try:
            text = self.repo.read_text(rel)
        except TooLarge:
            out["note"] = "Too large to display in the viewer. Its digest above was measured in full."
            out["truncated"] = True
            return out
        except UnicodeDecodeError:
            out["kind"] = "binary"
            out["note"] = "Not UTF-8 text: described, not displayed."
            return out
        out["content"] = text
        if kind == "json":
            try:
                out["parsed"] = json_safe(json.loads(text))
            except ValueError as exc:
                out["parse_error"] = str(exc)
        elif kind == "yaml" and _yaml is not None:
            try:
                out["parsed"] = json_safe(_yaml.safe_load(text))
            except Exception as exc:  # noqa: BLE001 - reported, not hidden
                out["parse_error"] = str(exc)
        refs = [f"results/{r['id']}" for r in self.index()["records"] if rel.startswith(r["path"] + "/")]
        out["in_record"] = refs[0] if refs else None
        return out

    def search(self, query: str, limit: int = 200) -> dict:
        query = (query or "").strip()
        if len(query) < 2:
            return {"query": query, "hits": [], "note": "type at least two characters"}
        query = query[:200]
        needle = query.lower()
        corpus = self._corpus()
        hits, files_hit = [], 0
        for path, text in corpus:
            low = text.lower()
            pos = low.find(needle)
            if pos < 0:
                continue
            files_hit += 1
            snippets = []
            while pos >= 0 and len(snippets) < 3:
                line_no = text.count("\n", 0, pos) + 1
                start = text.rfind("\n", 0, pos) + 1
                end = text.find("\n", pos)
                line = text[start: end if end >= 0 else len(text)]
                snippets.append({"line": line_no, "text": line.strip()[:300]})
                pos = low.find(needle, pos + len(needle))
            hits.append({"path": path, "snippets": snippets})
            if len(hits) >= limit:
                break
        records = [_record_row(r) for r in self.index()["records"]
                   if needle in r["id"].lower() or needle in (r["statement"] or "").lower()]
        return {"query": query, "hits": hits, "files_matched": files_hit,
                "truncated": len(hits) >= limit, "records": records[:50]}

    def _corpus(self) -> list[tuple[str, str]]:
        self.index()
        with self._lock:
            if self._search_corpus is not None:
                return self._search_corpus
        corpus = []
        roots = ("results", "experiments", "docs", "master", "manifests", "config", "sweeps", ".github")
        paths = [n for n, d in self.repo.list_dir("") if not d and n in SERVABLE_TOP]
        for root in roots:
            if self.repo.is_dir(root):
                paths += self.repo.walk_files(root, max_depth=6, skip_dirs=("solver", "workflows")
                                              if root != ".github" else ())
        for p in paths:
            if not p.endswith(SEARCH_SUFFIXES):
                continue
            try:
                if self.repo.size(p) > SEARCH_FILE_LIMIT:
                    continue
                corpus.append((p, self.repo.read_text(p, limit=SEARCH_FILE_LIMIT)))
            except (TooLarge, UnicodeDecodeError, NotFound, AccessDenied, OSError):
                continue
        with self._lock:
            self._search_corpus = corpus
        return corpus


TEXT_LIMIT_DOC = 64 * 1024


def _approval_state(fname: str, doc: Any) -> str:
    low = fname.lower()
    if ".draft" in low or (isinstance(doc, dict) and "DRAFT" in doc):
        return "DRAFT (not an approval)"
    if ".consumed" in low:
        return "CONSUMED (historical)"
    return "ON FILE"


def _record_row(r: dict) -> dict:
    return {k: r[k] for k in ("id", "family", "timestamp", "basis", "headline", "families",
                              "statement", "manifests", "file_count", "computational_only",
                              "referenced_by", "links")} | {"candidate_count": len(r["candidates"]),
                                                           "run_count": len(r["runs"])}


def _families_legend() -> list[dict]:
    return [{"family": f, "tone": t, "meaning": m} for f, (t, m) in classify.FAMILIES.items()]


def _first_paragraph(text: str, limit: int = 500) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block and not block.startswith("#"):
            return block[:limit] + ("…" if len(block) > limit else "")
    return ""
