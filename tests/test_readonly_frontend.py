# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The evidence viewer in ``frontend/`` is read-only, and these tests say so in code.

Each property is tested two ways where possible: statically (what the source
CAN do - its imports, its calls, its route table) and dynamically (what a live
server DOES - which verbs it answers, and whether any byte of the repository
changes while every route is exercised).

  * no POST/PUT/PATCH/DELETE (or any other non-GET/HEAD) route exists;
  * no filesystem write call exists anywhere in the viewer;
  * no subprocess, shell or process execution exists;
  * no git write operation exists, and git metadata is only read;
  * no solver, orchestrator, evaluator, model, geometry or experiment code is imported;
  * no approval can be written, and approval files are unchanged by use;
  * the page itself issues GET requests only and has no forms;
  * labelling is conservative: MEASURED is never inferred, statuses are quoted.

No test executes viewer code against the real checkout. Dynamic tests run against
fixture repositories and a byte copy of the checkout, both under pytest's tmp_path;
the real tree is only snapshotted, to show it was not touched. The static tests are
what guard the real tree.
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import json
import os
import re
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from frontend import adapter as adapter_mod  # noqa: E402
from frontend import classify  # noqa: E402
from frontend.adapter import ReadOnlyAdapter  # noqa: E402
from frontend.repo_fs import AccessDenied, ReadOnlyRepo  # noqa: E402
from frontend.server import ROUTES, SECURITY_HEADERS, ReadOnlyHandler, make_server  # noqa: E402

FRONTEND = REPO_ROOT / "frontend"
PY_SOURCES = sorted(FRONTEND.rglob("*.py"))
JS_SOURCES = sorted((FRONTEND / "static").glob("*.js"))
HTML_SOURCES = sorted((FRONTEND / "static").glob("*.html"))

MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE",
                    "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE", "LOCK", "UNLOCK")

#: The complete set of adapter methods the HTTP layer may call. Every one is a read.
READ_METHODS = {"overview", "capabilities", "checkout", "records", "record", "verify_record",
                "experiments", "experiment", "candidates", "gates", "provenance", "approvals",
                "audit", "corrections", "classification", "documents", "file", "search"}

SNAPSHOT_SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache",
                 ".ruff_cache"}


# =============================================================== helpers
def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_snapshot(root: Path, hash_limit: int = 1 << 20) -> dict[str, tuple]:
    """(size, mtime_ns, sha256-or-None) for every file under root, skipping caches."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SNAPSHOT_SKIP)
        for name in filenames:
            path = Path(dirpath) / name
            st = path.lstat()
            digest = _sha(path) if path.is_file() and not path.is_symlink() and st.st_size <= hash_limit else None
            out[path.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns, digest)
    return out


def git_meta_snapshot(root: Path) -> dict[str, tuple]:
    """Everything under .git except the object store: HEAD, index, refs, config, logs."""
    gitdir = root / ".git"
    out = {}
    if not gitdir.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(gitdir):
        dirnames[:] = [d for d in dirnames if d != "objects"]
        for name in filenames:
            path = Path(dirpath) / name
            st = path.lstat()
            out[path.relative_to(gitdir).as_posix()] = (st.st_size, st.st_mtime_ns)
    return out


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(node: ast.Call) -> str:
    return ast.unparse(node.func)


class Server:
    def __init__(self, root: Path):
        self.httpd = make_server(str(root), "127.0.0.1", 0, quiet=True)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, method: str, path: str, body: bytes | None = None) -> tuple[int, dict, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def get_json(self, path: str):
        status, _headers, body = self.request("GET", path)
        assert status == 200, (path, status, body[:300])
        return json.loads(body)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ======================================================= fixture repository
def _write(root: Path, rel: str, content) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    path.write_text(content, encoding="utf-8")
    return path


def _manifest(root: Path, record: str, files: list[str], corrupt: str | None = None,
              phantom: str | None = None) -> None:
    lines = []
    for rel in files:
        digest = _sha(root / "results" / record / rel)
        if rel == corrupt:
            digest = "0" * 64
        lines.append(f"{digest}  {rel}")
    if phantom:
        lines.append(f"{'a' * 64}  {phantom}")
    _write(root, f"results/{record}/manifest.sha256", "\n".join(lines) + "\n")


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """A small repository with every record shape the viewer handles."""
    root = tmp_path / "repo"
    # frozen master
    _write(root, "master/validation_gates.yaml", (
        "schema: test\nallowed_statuses: [PASS, FAIL, INCOMPLETE, HARDWARE-GATED]\n"
        "evidence_classes: [SOLVED, MEASURED]\n"
        "gates:\n"
        "  - gate_id: COLLISION\n    title: t\n    severity: HARD\n    hardware_required: false\n"
        "    required_evidence: [SOLVED]\n    allowed_statuses: [PASS, FAIL, INCOMPLETE]\n"
        "  - gate_id: P1\n    title: hw\n    severity: HARD\n    hardware_required: true\n"
        "    required_evidence: [MEASURED]\n    allowed_statuses: [HARDWARE-GATED, FAIL]\n"))
    gates_digest = _sha(root / "master/validation_gates.yaml")
    _write(root, "master/provenance.json", {
        "qmhp_master_revision": "vT", "qmhp_master_status": "FROZEN",
        "master_files": {"validation_gates.yaml": gates_digest},
        "master_pdf_verification": {"status": "UNRESOLVED", "statement": "not verified"},
        "evidence_boundary": {"measured_evidence_objects_present": False}})

    # a mock-solver batch: synthetic solver results, a hardware-gated gate, a bad manifest line
    b = "BATCH-20260101T000000Z"
    _write(root, f"results/{b}/batch_report.json", {
        "batch_id": b, "batch_outcome": "INCOMPLETE", "notes": ["mock solver"],
        "environment": {"started_utc": "2026-01-01T00:00:00Z"}})
    _write(root, f"results/{b}/C1/candidate.json", {"candidate_id": "C1", "classification": "ENGINEERING-SEED"})
    _write(root, f"results/{b}/C1/gate_report.json", {"candidate_id": "C1", "overall_status": "INCOMPLETE", "gates": [
        {"gate_id": "COLLISION", "status": "PASS", "evidence_class": "SOLVED", "hardware_required": False, "reason": "ok"},
        {"gate_id": "P1", "status": "HARDWARE-GATED", "evidence_class": None, "hardware_required": True,
         "reason": "requires MEASURED evidence"}]})
    _write(root, f"results/{b}/C1/solver/solver_results.json", {
        "solver": {"name": "mock", "version": "0", "classification": "TEST_FIXTURE"}, "synthetic": True})
    _manifest(root, b, ["batch_report.json", "C1/candidate.json", "C1/gate_report.json"],
              corrupt="C1/gate_report.json", phantom="C1/missing.json")

    # an explicitly synthetic record, by name
    s = "ROUTE-A-SYNTHETIC-20260102T000000Z"
    _write(root, f"results/{s}/summary.json", {"statement": "Synthetic demonstration.", "outcome": "PASS"})

    # a solved record that talks about measurement but does not declare MEASURED
    v = "PALACE-VERIFY-20260103T000000Z"
    _write(root, f"results/{v}/summary.json", {
        "started_utc": "2026-01-03T00:00:00Z", "statement": "measured on the solver's mesh; not measured hardware",
        "solver_provenance": {"palace_version": "0.13.0"}, "allowed": ["MEASURED", "SOLVED"],
        "mesh_convergence": {"verdict": "PASS"}, "height": {"object001_height": {"verdict": "BLOCKED"}},
        "runs": {"r1": {"status": "RUN_FAILED"}, "r2": {"status": "CONVERGED"}}})
    _write(root, f"results/{v}/campaign.json", {"a": 1})
    _write(root, f"results/{v}/campaign.sha256", f"{'b' * 64}  campaign.json\n")
    _manifest(root, v, ["summary.json", "campaign.json"])

    # a corrective analysis, a declared-MEASURED record, and an unclassifiable one
    c = "PILOT-CORR-20260104T000000Z"
    _write(root, f"results/{c}/corrective_analysis.json", {
        "kind": "corrective-analysis", "statement": "Corrective analysis of PILOT-20260101T000000Z.",
        "superseded_analysis": {"note": "the verdict of PILOT-20260101T000000Z is preserved unchanged"}})
    m = "BENCH-20260105T000000Z"
    _write(root, f"results/{m}/summary.json", {"evidence_class": "MEASURED", "outcome": {"verdict": "QUALIFIED"}})
    u = "ODD-20260106T000000Z"
    _write(root, f"results/{u}/summary.json", {"outcome": {"verdict": "UNQUALIFIED - residual too large"}})

    # experiments with every execution state
    _write(root, "experiments/exp-prepared/predeclaration.json", {
        "status": "PREPARED. NOT APPROVED. NOT EXECUTED. Nothing has run.", "question": "Does it?"})
    _write(root, "experiments/exp-prepared/TEST-APPROVAL.draft.json", {"DRAFT": "not an approval", "authorises": "x"})
    _write(root, "experiments/exp-approved/TEST-APPROVAL.json", {"authorises": "one run", "does_not_authorise": ["a retry"]})
    _write(root, "experiments/exp-withdrawn/WITHDRAWN.json", {"status": "WITHDRAWN. Never approved.", "date": "2026-01-07"})
    _write(root, "experiments/exp-withdrawn/predeclaration.json", {"status": "PREPARED. NOT APPROVED."})
    _write(root, "experiments/exp-spent/ATTEMPT-SPENT.json", {"record": v, "spent_utc": "2026-01-03T00:00:00+00:00"})
    _write(root, "experiments/exp-spent/STUDY-APPROVAL.consumed.json", {"authorises": "one run", "not_before_utc": "2026-01-02T23:00:00Z"})
    _write(root, "experiments/exp-spent/EXECUTION-LOG.json", {"start_utc": "2026-01-03T00:00:00Z", "end_utc": "2026-01-03T00:01:00Z", "exit_code": 0})
    _write(root, "experiments/SYNTHETIC-demo/results.json", {"label": "synthetic"})
    _write(root, "experiments/exp-mixed/fixture.json", {"not_qmhp": "fixture", "synthetic_only": True})
    _write(root, "experiments/exp-mixed/EXECUTION-APPROVAL.json", {"authorises": "one execution on real data"})
    _write(root, "experiments/exp-mixed/data.json", {"correction": "an earlier note in this record was wrong"})

    _write(root, "docs/notes.md", "# Notes\n\n## Correction of record\n\nThe earlier value was wrong.\n\n"
                                  "## This is correctly scoped\n\nNot a correction.\n")
    _write(root, "README.md", "# Fixture\n")
    _write(root, "uv.lock", "not served\n")
    # a symlink that points outside the repository
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, root / "docs" / "escape.md")
        os.symlink(tmp_path, root / "results" / "LINKED-20260108T000000Z")
    except (OSError, NotImplementedError):  # pragma: no cover - platform without symlinks
        pass
    return root


#: Largest file copied into the scratch copy of the repository. Larger files (meshes,
#: field dumps) are left out; manifest checks then report them ABSENT, which is fine for
#: tests about what the viewer writes rather than about the evidence's integrity.
COPY_LIMIT = 2 * 1024 * 1024
COPY_TOP = ("results", "experiments", "docs", "master", "manifests", "config", "contracts", "sweeps",
            ".github", "README.md", "QMHP-CEM_v0.1_Spec.md", "CLAUDE.md", "AGENTS.md", "LICENSE")


def copy_of_repository(dest: Path) -> Path:
    """A byte copy (never hard links) of the evidence-bearing parts of this checkout.

    The dynamic tests drive the viewer against this copy, not the real tree. Were the
    viewer ever broken into writing, the damage would land in tmp_path, and the static
    tests below - which never execute viewer code against the repository - would still
    fail on the defect. (Pointing a possibly-broken writer at committed evidence in
    order to prove it does not write is the failure this avoids.)"""
    for top in COPY_TOP:
        src = REPO_ROOT / top
        if src.is_file() and not src.is_symlink():
            (dest / top).parent.mkdir(parents=True, exist_ok=True)
            (dest / top).write_bytes(src.read_bytes())
            continue
        if not src.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(src):
            dirnames[:] = [d for d in dirnames if d not in SNAPSHOT_SKIP]
            for name in filenames:
                path = Path(dirpath) / name
                if path.is_symlink() or not path.is_file() or path.stat().st_size > COPY_LIMIT:
                    continue
                target = dest / path.relative_to(REPO_ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
    return dest


@pytest.fixture(scope="module")
def repo_copy(tmp_path_factory) -> Path:
    return copy_of_repository(tmp_path_factory.mktemp("repo-copy"))


@pytest.fixture(scope="module")
def live_repo_server(repo_copy):
    server = Server(repo_copy)
    yield server
    server.close()


# ================================================================ 1. HTTP
def test_handler_defines_get_and_head_and_nothing_else():
    verbs = sorted(name for name in dir(ReadOnlyHandler) if name.startswith("do_"))
    assert verbs == ["do_GET", "do_HEAD"]


def test_route_table_maps_only_to_read_methods():
    methods = {method for _pattern, method, _takes in ROUTES}
    assert methods <= READ_METHODS, methods - READ_METHODS
    forbidden = re.compile(r"write|save|delete|remove|update|create|approve|grant|consume|run|exec|launch|"
                           r"dispatch|commit|push|merge|edit|admin|upload|put|post|patch", re.I)
    for pattern, method, _ in ROUTES:
        assert not forbidden.search(pattern.pattern), pattern.pattern
        assert not forbidden.search(method), method


def test_adapter_has_no_public_method_beyond_the_read_set():
    public = {n for n in dir(ReadOnlyAdapter) if not n.startswith("_") and callable(getattr(ReadOnlyAdapter, n))}
    assert public <= READ_METHODS | {"index", "frozen_contracts", "gate_definitions", "master_provenance"}, public


def _concrete_paths(server: Server) -> list[str]:
    records = server.get_json("/api/records")["records"]
    rid = records[0]["id"] if records else "NONE-20260101T000000Z"
    exps = server.get_json("/api/experiments")["experiments"]
    eid = exps[0]["id"] if exps else "none"
    paths = []
    for pattern, _method, takes in ROUTES:
        p = pattern.pattern.strip("^$")
        p = re.sub(r"\(\?P<id>[^)]*\)", eid if "experiments" in p else rid, p)
        if takes == "path":
            p += "?path=README.md"
        elif takes == "q":
            p += "?q=PASS"
        paths.append(p)
    return paths + ["/", "/static/app.js", "/static/style.css", "/static/index.html"]


def test_mutating_methods_are_refused_on_every_route(live_repo_server):
    for path in _concrete_paths(live_repo_server):
        for method in MUTATING_METHODS:
            status, headers, body = live_repo_server.request(method, path, body=b'{"approved": true}')
            assert status == 501, (method, path, status)
            assert b'"approved"' not in body


def test_unknown_or_admin_style_paths_do_not_exist(live_repo_server):
    for path in ("/api/admin", "/api/approve", "/api/approvals/new", "/api/run", "/api/execute",
                 "/api/solve", "/api/palace", "/api/route-a", "/api/e1", "/api/write", "/api/commit",
                 "/api/push", "/api/config", "/api/records/X-20260101T000000Z/approve",
                 "/api/records/X-20260101T000000Z/delete", "/admin", "/api/debug", "/api/shell"):
        status, _h, _b = live_repo_server.request("GET", path)
        assert status == 404, path
        status, _h, _b = live_repo_server.request("POST", path, body=b"{}")
        assert status == 501, path


def test_security_headers_forbid_form_submission_and_framing(live_repo_server):
    status, headers, _ = live_repo_server.request("GET", "/api/capabilities")
    assert status == 200
    assert headers["Allow"] == "GET, HEAD"
    csp = headers["Content-Security-Policy"]
    assert "form-action 'none'" in csp and "frame-ancestors 'none'" in csp and "script-src 'self'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert SECURITY_HEADERS["Allow"] == "GET, HEAD"


def test_capabilities_declare_every_mutation_unavailable(live_repo_server):
    caps = live_repo_server.get_json("/api/capabilities")
    assert caps["read_only"] is True and caps["http_methods"] == ["GET", "HEAD"]
    actions = " ".join(u["action"] for u in caps["unavailable"]).lower()
    for needle in ("experiment", "solver", "palace", "route a", "e1", "approval", "contract", "commit", "push"):
        assert needle in actions, needle
    assert all(u["available"] is False for u in caps["unavailable"])


def test_exercising_every_route_changes_nothing_in_the_repository(live_repo_server, repo_copy):
    """The dynamic proof: snapshot a copy of the repository, drive every GET route -
    including re-hashing every manifest and opening every approval - and snapshot again.
    The real checkout is snapshotted too, as a check that the tests stayed on the copy."""
    before, real_before = tree_snapshot(repo_copy), tree_snapshot(REPO_ROOT, hash_limit=0)
    git_before = git_meta_snapshot(REPO_ROOT)
    for path in _concrete_paths(live_repo_server):
        status, _h, _b = live_repo_server.request("GET", path)
        assert status in (200, 404), path
        live_repo_server.request("HEAD", path)
    for rec in live_repo_server.get_json("/api/records")["records"]:
        live_repo_server.get_json(f"/api/records/{rec['id']}")
        verify = live_repo_server.get_json(f"/api/records/{rec['id']}/verify")
        for manifest in verify["manifests"]:
            for entry in manifest["entries"]:
                assert entry["status"] in ("MATCH", "MISMATCH", "ABSENT FROM CHECKOUT", "UNPARSEABLE",
                                           "REFUSED (outside the repository)")
    for exp in live_repo_server.get_json("/api/experiments")["experiments"]:
        live_repo_server.get_json(f"/api/experiments/{exp['id']}")
    for doc in live_repo_server.get_json("/api/documents")["documents"]:
        live_repo_server.get_json(f"/api/file?path={doc['path']}")
    for ap in live_repo_server.get_json("/api/approvals")["approvals"]:
        live_repo_server.get_json(f"/api/file?path={ap['path']}")
    assert tree_snapshot(repo_copy) == before
    assert tree_snapshot(REPO_ROOT, hash_limit=0) == real_before
    assert git_meta_snapshot(REPO_ROOT) == git_before


def test_static_route_serves_only_the_viewers_own_assets(live_repo_server):
    """Decorative images are served from frontend/static/img/ as image/webp; nothing else
    under that prefix, and no dot-segment or repository path, is reachable."""
    images = sorted((FRONTEND / "static" / "img").glob("*.webp"))
    assert images, "the viewer ships its decorative images"
    for img in images:
        status, headers, body = live_repo_server.request("GET", f"/static/img/{img.name}")
        assert status == 200 and headers["Content-Type"] == "image/webp", img.name
        assert body[:4] == b"RIFF" and body[8:12] == b"WEBP", img.name
    for bad in ("/static/img/../app.js", "/static/img/%2e%2e/app.js", "/static/img/x.jpg",
                "/static/img/sub/x.webp", "/static/img/", "/static/../frontend/server.py",
                "/static/img/..%2f..%2fREADME.md", "/static/README.md", "/results/README.md"):
        status, _h, body = live_repo_server.request("GET", bad)
        assert status == 404, (bad, status)
        assert b"import" not in body and b"QMHP-CEM" not in body, bad


def test_file_endpoint_is_confined_to_the_repository(fixture_repo):
    server = Server(fixture_repo)
    try:
        for bad in ("../outside-secret.txt", "/etc/passwd", ".git/config", ".git/HEAD", "results/../../x",
                    "docs/escape.md", "results/LINKED-20260108T000000Z/outside-secret.txt", "uv.lock",
                    "docs\\notes.md", "docs/notes.md%00", ".venv/x", "results/__pycache__/x"):
            status, _h, body = server.request("GET", "/api/file?path=" + bad.replace("%00", "%2500"))
            assert status in (403, 404), (bad, status)
            assert b"secret" not in body
        status, _h, _b = server.request("GET", "/api/file?path=docs/notes.md")
        assert status == 200
    finally:
        server.close()
    repo = ReadOnlyRepo(fixture_repo)
    for bad in ("../x", "/etc/passwd", ".git/config", "a/../../x", "docs/escape.md", "a\x00b"):
        with pytest.raises(AccessDenied):
            repo.resolve(bad)


# ====================================================== 2. static analysis
def test_no_filesystem_write_calls_anywhere_in_the_viewer():
    """Every open() is read-only and no write, rename, delete, mkdir or chmod exists."""
    forbidden_qualified = re.compile(
        r"^(os|shutil|tempfile|pathlib|Path)\.(remove|unlink|rename|replace|renames|makedirs|mkdir|"
        r"rmdir|removedirs|chmod|chown|lchown|utime|symlink|link|truncate|open|write|mkfifo|mknod|"
        r"copy\w*|move|rmtree|make_archive|mkstemp|mkdtemp|NamedTemporaryFile|TemporaryFile|"
        r"SpooledTemporaryFile|TemporaryDirectory)$")
    forbidden_attrs = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename",
                       "symlink_to", "hardlink_to", "chmod", "lchmod", "truncate", "writelines",
                       "dump", "savez", "save", "to_csv", "to_json"}
    offences = []
    for path in PY_SOURCES:
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            where = f"{path.relative_to(REPO_ROOT)}:{node.lineno} {name}"
            if forbidden_qualified.match(name):
                offences.append(where)
            if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_attrs:
                offences.append(where)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "write" \
                    and ast.unparse(node.func.value) != "self.wfile":
                offences.append(where + " (only the HTTP response stream may be written)")
            if name in ("open", "io.open", "codecs.open", "os.fdopen"):
                mode = None
                if len(node.args) >= 2:
                    mode = node.args[1]
                for kw in node.keywords:
                    if kw.arg == "mode":
                        mode = kw.value
                if mode is not None and not (isinstance(mode, ast.Constant) and mode.value in ("r", "rb", "rt")):
                    offences.append(where + " (open with a non-read mode)")
    assert not offences, offences


def test_no_process_shell_or_dynamic_code_execution():
    forbidden_modules = {"subprocess", "pty", "multiprocessing", "concurrent", "asyncio", "ctypes", "cffi",
                         "importlib", "runpy", "code", "pdb", "signal", "socketserver_exec", "sh", "plumbum",
                         "pexpect", "docker", "paramiko", "fabric"}
    forbidden_calls = re.compile(r"^(os\.(system|popen|exec\w*|spawn\w*|fork\w*|posix_spawn\w*|kill\w*|startfile)|"
                                 r"eval|exec|compile|__import__|breakpoint)$")
    offences = []
    for path in PY_SOURCES:
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offences += [f"{path.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in forbidden_modules]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] in forbidden_modules:
                    offences.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Call) and forbidden_calls.match(_call_name(node)):
                offences.append(f"{path.name}:{node.lineno} {_call_name(node)}")
            elif isinstance(node, ast.Attribute) and ast.unparse(node) in ("os.environ", "os.getenv", "os.putenv"):
                offences.append(f"{path.name}:{node.lineno} {ast.unparse(node)} (no environment-driven modes)")
    assert not offences, offences


#: The complete import allowlist for the viewer's Python. A positive list, so that
#: any new capability - network client, solver, database, archive writer - fails here.
ALLOWED_IMPORTS = {"__future__", "argparse", "hashlib", "json", "math", "os", "re", "sys", "threading",
                   "datetime", "typing", "pathlib", "http", "http.server", "urllib.parse", "yaml"}


def test_imports_are_exactly_the_allowlist():
    found = set()
    for path in PY_SOURCES:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Import):
                found |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                found.add(node.module)
    assert found <= ALLOWED_IMPORTS, found - ALLOWED_IMPORTS


def test_no_solver_pipeline_or_experiment_code_is_imported():
    """Named explicitly, because this is the property that keeps the viewer from ever
    becoming a second control surface over the scientific workflow."""
    scientific = {"solvers", "orchestrator", "evaluator", "models", "geometry", "contracts", "scripts",
                  "experiments", "tools", "master", "gmsh", "gdsfactory", "skrf", "scipy", "numpy",
                  "pydantic", "docker"}
    for path in PY_SOURCES:
        for node in ast.walk(_parse(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for n in names:
                assert n.split(".")[0] not in scientific, f"{path.name} imports {n}"
    # nor does it name their entry points as strings (e.g. to load them indirectly)
    for path in PY_SOURCES:
        text = path.read_text(encoding="utf-8")
        for entry in ("orchestrator.cem", "solvers.palace", "palace_golden_run", "palace_verify_campaign",
                      "run_diagnostic", "route_a_inversion", "study_driver", "cem sweep", "cem simulate"):
            assert entry not in text, f"{path.name} names {entry}"


def test_no_git_write_operation_and_git_metadata_is_only_read():
    git_write = re.compile(r"\bgit\s+(add|commit|push|pull|fetch|merge|rebase|reset|checkout|switch|branch|tag|"
                           r"cherry-pick|revert|am|apply|stash|rm|mv|clean|gc|update-ref|config|remote|init)\b")
    for path in PY_SOURCES + JS_SOURCES + HTML_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert not git_write.search(text), f"{path.name}: {git_write.search(text).group(0)}"
        for token in ("api.github.com", "pygit2", "dulwich", "GitPython", "git.Repo", "gh pr", "gh api"):
            assert token not in text, f"{path.name}: {token}"
    # the checkout reader opens git files, and only for reading (covered by the open-mode
    # test), and it never names the object store or the index
    src = (FRONTEND / "repo_fs.py").read_text()
    assert '"objects"' not in src and '"index"' not in src and "ORIG_HEAD" not in src


def test_no_approval_can_be_written(fixture_repo):
    """Approvals are displayed, never produced: no write primitive exists (above), no
    route names one, and using the viewer leaves every approval file byte-identical."""
    for pattern, method, _ in ROUTES:
        assert "approv" not in method or method == "approvals"
        assert "approv" not in pattern.pattern or pattern.pattern == "^/api/approvals$"
    approvals = sorted(fixture_repo.rglob("*APPROVAL*.json"))
    assert len(approvals) >= 4
    before = {p: (_sha(p), p.stat().st_mtime_ns) for p in approvals}
    server = Server(fixture_repo)
    try:
        listed = server.get_json("/api/approvals")["approvals"]
        assert {a["path"] for a in listed} == {p.relative_to(fixture_repo).as_posix() for p in approvals}
        for a in listed:
            server.get_json(f"/api/file?path={a['path']}")
        for exp in server.get_json("/api/experiments")["experiments"]:
            server.get_json(f"/api/experiments/{exp['id']}")
        server.get_json("/api/audit")
    finally:
        server.close()
    assert {p: (_sha(p), p.stat().st_mtime_ns) for p in approvals} == before
    assert sorted(fixture_repo.rglob("*APPROVAL*.json")) == approvals


# ============================================================ 3. the page
def test_page_issues_get_requests_only():
    js = "\n".join(p.read_text(encoding="utf-8") for p in JS_SOURCES)
    assert js.count("fetch(") == 1, "all network access must go through the single get() helper"
    methods = re.findall(r"method:\s*['\"]([A-Za-z]+)['\"]", js)
    assert methods == ["GET"], methods
    for banned in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "serviceWorker", "localStorage",
                   "sessionStorage", "indexedDB", "document.cookie", "FormData", ".submit(", "eval(",
                   "new Function", "postMessage", "window.open", "body:"):
        assert banned not in js, banned


def test_page_has_no_forms_inline_script_or_handlers():
    for path in HTML_SOURCES:
        html = path.read_text(encoding="utf-8").lower()
        assert "<form" not in html
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline script"
        assert not re.search(r"\son[a-z]+\s*=", html), "inline event handler"
        assert 'type="submit"' not in html
    js = "\n".join(p.read_text(encoding="utf-8") for p in JS_SOURCES)
    assert '"form"' not in js and "'form'" not in js


def test_every_api_path_the_page_calls_is_a_get_route():
    js = "\n".join(p.read_text(encoding="utf-8") for p in JS_SOURCES)
    calls = re.findall(r"get\(\s*[`'\"](/api/[^`'\"]*)[`'\"]", js)
    assert calls, "expected the page to call the API"
    for call in calls:
        concrete = re.sub(r"\$\{[^}]*\}", "X", call).split("?")[0]
        assert any(p.match(concrete) for p, _m, _t in ROUTES), call


# ================================================== 4. conservative labels
def test_classification_on_the_fixture(fixture_repo):
    a = ReadOnlyAdapter(str(fixture_repo))
    basis = {r["id"]: r["basis"] for r in a.records()["records"]}
    assert basis["BATCH-20260101T000000Z"]["basis"] == "SYNTHETIC"          # TEST_FIXTURE / synthetic: true
    assert basis["ROUTE-A-SYNTHETIC-20260102T000000Z"]["basis"] == "SYNTHETIC"
    assert basis["PALACE-VERIFY-20260103T000000Z"]["basis"] == "SOLVED"
    assert basis["PILOT-CORR-20260104T000000Z"]["basis"] == "ANALYSIS"
    assert basis["BENCH-20260105T000000Z"]["basis"] == "MEASURED"           # declared literally, so shown
    assert basis["ODD-20260106T000000Z"]["basis"] == "UNCLASSIFIED"         # no guess
    for rid, b in basis.items():
        assert b["rule"] and b["reason"], rid


def test_measured_is_never_inferred():
    docs = {"summary.json": {"statement": "MEASURED on the mesh", "allowed": ["MEASURED"],
                             "evidence_classes": ["MEASURED"], "note": "measured"}}
    assert classify.classify_record("X-20260101T000000Z", docs, [])["basis"] != "MEASURED"
    docs = {"summary.json": {"gates": [{"evidence_class": "MEASURED"}]}}
    assert classify.classify_record("X-20260101T000000Z", docs, [])["basis"] == "MEASURED"


def test_statuses_are_quoted_not_invented():
    item = classify.status_item("status", "PREPARED. NOT APPROVED. NOT EXECUTED. No solve has run.")
    assert item["tokens"] == ["PREPARED", "NOT APPROVED", "NOT EXECUTED"]
    assert classify.status_item("statement", "Numerical verification of the box") is None
    item = classify.status_item("outcome.verdict", "UNQUALIFIED - residual too large")
    assert item["tokens"] == ["UNQUALIFIED"] and item["families"] == ["UNQUALIFIED"]
    assert classify.family("SOMETHING-NEW") == "AS-RECORDED"
    assert classify.family("HARDWARE-GATED") == "HARDWARE-GATED"
    assert classify.family("REFUSED BY EGRESS POLICY") == "REFUSED"


def test_every_non_measured_record_is_flagged_computational(fixture_repo):
    a = ReadOnlyAdapter(str(fixture_repo))
    for row in a.records()["records"]:
        rec = a.record(row["id"])
        assert rec["computational_only"] is (rec["basis"]["basis"] != "MEASURED")
        assert "not hardware validation" in rec["disclaimer"]


def test_manifest_verification_is_reported_honestly(fixture_repo):
    a = ReadOnlyAdapter(str(fixture_repo))
    v = a.verify_record("BATCH-20260101T000000Z")
    statuses = {e["path"].split("/", 2)[-1]: e["status"] for e in v["manifests"][0]["entries"]}
    assert statuses["C1/gate_report.json"] == "MISMATCH"
    assert statuses["C1/candidate.json"] == "MATCH"
    assert statuses["C1/missing.json"] == "ABSENT FROM CHECKOUT"
    assert "results/BATCH-20260101T000000Z/C1/solver/solver_results.json" in v["unlisted_files"]
    # a .sha256 that is not a byte manifest is shown as declared and never byte-compared
    v = a.verify_record("PALACE-VERIFY-20260103T000000Z")
    assert [m["manifest"].rsplit("/", 1)[-1] for m in v["manifests"]] == ["manifest.sha256"]
    assert [d["path"].rsplit("/", 1)[-1] for d in v["declared_digest_files"]] == ["campaign.sha256"]


def test_experiment_states_and_approvals_are_read_from_their_files(fixture_repo):
    a = ReadOnlyAdapter(str(fixture_repo))
    states = {e["id"]: e["state"]["label"] for e in a.experiments()["experiments"]}
    assert states["exp-withdrawn"] == "WITHDRAWN"
    assert states["exp-spent"] == "ATTEMPT SPENT"
    assert states["exp-approved"] == "APPROVAL ON FILE"
    assert states["exp-prepared"] == "PREPARED / NOT APPROVED / NOT EXECUTED"
    bases = {e["id"]: e["basis"]["basis"] for e in a.experiments()["experiments"]}
    assert bases["SYNTHETIC-demo"] == "SYNTHETIC"
    assert bases["exp-mixed"] == "DECLARATION"       # one fixture file does not make it synthetic
    assert a.experiment("exp-mixed")["synthetic_files"]
    approvals = {x["path"].rsplit("/", 1)[-1]: x["state"] for x in a.approvals()["approvals"]}
    assert approvals["TEST-APPROVAL.draft.json"].startswith("DRAFT")
    assert approvals["STUDY-APPROVAL.consumed.json"].startswith("CONSUMED")
    assert approvals["TEST-APPROVAL.json"] == "ON FILE"
    kinds = [e["kind"] for e in a.audit()["events"]]
    assert "ATTEMPT SPENT" in kinds and "WITHDRAWN" in kinds and "EXECUTION STARTED" in kinds


def test_corrections_are_collected_without_false_positives(fixture_repo):
    items = ReadOnlyAdapter(str(fixture_repo)).corrections()["items"]
    types = {(i["type"], i["ref"]) for i in items}
    assert ("CORRECTIVE RECORD", "results/PILOT-CORR-20260104T000000Z") in types
    assert ("SUPERSESSION", "results/PILOT-CORR-20260104T000000Z") in types
    assert ("WITHDRAWAL", "experiments/exp-withdrawn") in types
    assert ("CORRECTION", "experiments/exp-mixed") in types
    headings = [i["json_path"] for i in items if i["type"] == "DOCUMENT SECTION"]
    assert headings == ["Correction of record"]


def test_gates_keep_the_hardware_boundary_visible(fixture_repo):
    g = ReadOnlyAdapter(str(fixture_repo)).gates()
    defs = {d["gate_id"]: d for d in g["definitions"]["gates"]}
    assert defs["P1"]["hardware_required"] and not defs["P1"]["pass_permitted"]
    row = g["results"][0]
    p1 = next(x for x in row["gates"] if x["gate_id"] == "P1")
    assert p1["status"] == "HARDWARE-GATED" and p1["tone"] == "gated"


def test_the_whole_fixture_is_unchanged_after_every_adapter_view(fixture_repo):
    before = tree_snapshot(fixture_repo)
    a = ReadOnlyAdapter(str(fixture_repo))
    for name in ("overview", "records", "experiments", "candidates", "gates", "provenance", "approvals",
                 "audit", "corrections", "classification", "documents", "capabilities", "checkout"):
        getattr(a, name)()
    for row in a.records()["records"]:
        a.record(row["id"])
        a.verify_record(row["id"])
    for e in a.experiments()["experiments"]:
        a.experiment(e["id"])
    for d in a.documents()["documents"]:
        try:
            a.file(d["path"])
        except AccessDenied:
            pass
    a.search("correction")
    assert tree_snapshot(fixture_repo) == before


def test_the_real_repository_reads_cleanly(repo_copy):
    """Smoke test on (a copy of) the checked-out repository: it indexes, nothing is
    MEASURED unless a record declares it, and the frozen master's hardware gates are listed."""
    a = ReadOnlyAdapter(str(repo_copy))
    ov = a.overview()
    assert ov["counts"]["records"] == len(a.records()["records"])
    measured = [r for r in a.records()["records"] if r["basis"]["basis"] == "MEASURED"]
    for r in measured:  # only by literal declaration
        assert r["basis"]["rule"] == "R3"
    assert ov["measured_evidence_present"] is bool(measured)
    if (repo_copy / "master" / "validation_gates.yaml").is_file():
        assert ov["hardware_gated_gates"], "the frozen master declares hardware gates"
    assert adapter_mod.HARDWARE_DISCLAIMER.startswith("A computational PASS is not hardware validation")
