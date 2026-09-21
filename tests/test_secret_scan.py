"""The approved secret scanner: that it is pinned, that it detects, and that it refuses.

Every test that writes runs in pytest's tmp_path. Nothing here touches the working tree,
and no synthetic secret is ever written into this repository: the fixtures are built in
disposable directories, and the literals are assembled from fragments at runtime so that
this file cannot itself trip the scanner it tests.

The refusal tests use stub binaries and therefore always run. The detection tests need
the real pinned scanner; if it cannot be resolved they skip, so
test_ci_runs_the_scanner_read_only pins the CI step separately - a skipped detection
test must not be able to remove the enforcement silently.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "secret_scan.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import secret_scan as ss  # noqa: E402


def _synthetic_github_pat() -> str:
    """A GitHub personal-access-token shape, assembled here so the literal never exists
    in a tracked file. Not a credential: the body is a fixed alphanumeric run."""
    return "ghp_" + "0123456789abcdefghijABCDEFGHIJ012345"


def _stub(path: Path, *, version: str, scan_exit: int, stdout: str = "[]") -> Path:
    """A fake scanner: answers `version`, and exits scan_exit for anything else."""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"if len(sys.argv) > 1 and sys.argv[1] == 'version':\n"
        f"    print({version!r}); raise SystemExit(0)\n"
        f"sys.stdout.write({stdout!r})\n"
        f"raise SystemExit({scan_exit})\n")
    path.chmod(0o755)
    return path


@pytest.fixture(scope="module")
def scanner() -> Path:
    try:
        return ss.resolve_scanner()
    except ss.Blocked as exc:
        pytest.skip(f"the pinned scanner could not be resolved here: {exc}")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for argv in (["init", "-q", "."], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "test"]):
        subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)
    (repo / "ok.txt").write_text("nothing to see\n")
    subprocess.run(["git", "add", "ok.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True, capture_output=True)
    return repo


# --- 1. the pin ----------------------------------------------------------------------

def test_the_scanner_pin_is_a_verifiable_module_version():
    """Version, module hash, VCS commit and licence are recorded, not implied."""
    assert ss.MODULE == "github.com/zricethezav/gitleaks/v8"
    assert ss.MODULE_VERSION == "v8.30.1" and ss.TOOL_VERSION == "8.30.1"
    assert ss.MODULE_VERSION == f"v{ss.TOOL_VERSION}"
    assert ss.MODULE_H1.startswith("h1:") and len(ss.MODULE_H1) == 47
    assert re.fullmatch(r"[0-9a-f]{40}", ss.VCS_COMMIT)
    assert ss.VCS_TAG == f"refs/tags/{ss.MODULE_VERSION}"
    assert ss.VCS_URL == "https://github.com/zricethezav/gitleaks"
    assert ss.LICENCE == "MIT"
    # the version is stamped with upstream's own .goreleaser.yml ldflag, so that
    # `gitleaks version` reports the pin rather than "set by the build process"
    assert f"-X={ss.MODULE}/version.Version={ss.TOOL_VERSION}" in ss.LDFLAGS
    # the scanner is fetched at use time, never committed here
    assert not list(REPO_ROOT.rglob("gitleaks"))
    assert ss.cache_binary().is_absolute() and REPO_ROOT not in ss.cache_binary().parents


def test_the_resolved_scanner_reports_the_pinned_version(scanner: Path):
    assert ss.reported_version(scanner) == ss.TOOL_VERSION
    prov = ss.provenance(scanner)
    assert prov["module_version"] == ss.MODULE_VERSION
    assert prov["vcs_commit"] == ss.VCS_COMMIT and prov["licence"] == "MIT"
    assert re.fullmatch(r"[0-9a-f]{64}", prov["binary_sha256_measured"])
    # the digest is MEASURED, not asserted against a constant: a Go binary is not
    # bit-identical across toolchains, so pinning it would fail for the wrong reason
    assert "binary_sha256_expected" not in prov


def test_the_argv_is_pinned_and_carries_no_baseline(tmp_path: Path):
    fake = tmp_path / "gl"
    for mode, rng in (("dir", None), ("tree", None), ("staged", None), ("range", "a..b")):
        argv = ss.build_argv(fake, mode=mode, target=tmp_path, rev_range=rng)
        assert "--redact=100" in argv, mode
        assert "--exit-code" in argv and argv[argv.index("--exit-code") + 1] == "1"
        assert not any(a.startswith("--baseline") or a == "-b" for a in argv), mode
        assert argv[1] == ("dir" if mode in ("tree", "dir") else "git")
    assert "--staged" in ss.build_argv(fake, mode="staged", target=tmp_path, rev_range=None)
    assert "--log-opts=a..b" in ss.build_argv(fake, mode="range", target=tmp_path,
                                              rev_range="a..b")
    with pytest.raises(ss.Blocked):
        ss.build_argv(fake, mode="history", target=tmp_path, rev_range=None)


# --- 2. it detects, and it withholds the value ---------------------------------------

def test_clean_content_scans_clean(scanner: Path, tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello\nthere are no credentials in this file\n")
    (tmp_path / "b.py").write_text("def f():\n    return 42\n")
    result = ss.scan(mode="dir", target=tmp_path)
    assert result["count"] == 0 and result["findings"] == []


def test_a_synthetic_secret_is_detected_and_its_value_is_withheld(scanner: Path,
                                                                  tmp_path: Path):
    secret = _synthetic_github_pat()
    (tmp_path / "config.env").write_text(f"GITHUB_TOKEN={secret}\n")
    result = ss.scan(mode="dir", target=tmp_path)
    assert result["count"] == 1, result
    finding = result["findings"][0]
    assert finding["RuleID"] == "github-pat"
    assert Path(finding["File"]).name == "config.env"
    assert finding["StartLine"] == 1
    # the value, and every value-bearing field, is absent from what we would print
    printed = json.dumps(result)
    assert secret not in printed
    assert "REDACTED" not in printed, "redacted placeholders should not survive either"
    for withheld in ss.WITHHELD_FIELDS:
        assert withheld not in finding


def test_the_reporter_allowlists_fields_so_a_new_one_cannot_leak():
    raw = [{"RuleID": "r", "File": "f", "StartLine": 1, "Secret": "sssh",
            "Match": "k=sssh", "Message": "commit msg", "Author": "a", "Email": "e",
            "SomeFutureField": "leak"}]
    out = ss.redact(raw)[0]
    assert out == {"RuleID": "r", "File": "f", "StartLine": 1}
    assert "SomeFutureField" not in out
    assert set(ss.WITHHELD_FIELDS).isdisjoint(ss.REPORTED_FIELDS)


def test_the_tree_scope_is_tracked_files_only(scanner: Path, git_repo: Path):
    """REGRESSION. `gitleaks dir` over the checkout does NOT read .gitignore: the first
    integration of this scanner reported a finding in .venv/share/doc/gmsh/CHANGELOG.txt,
    a vendored file that is gitignored, untracked and not repository content. --tree
    therefore scans what git tracks. An untracked secret is out of scope; the moment it
    is tracked it is in scope."""
    (git_repo / "ignored.env").write_text(f"T={_synthetic_github_pat()}\n")
    (git_repo / ".gitignore").write_text("ignored.env\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=git_repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "ignore it"], cwd=git_repo, check=True,
                   capture_output=True)
    clean = ss.scan(mode="tree", target=git_repo)
    assert clean["count"] == 0, clean["findings"]
    assert clean["tracked_files_scanned"] == 2      # ok.txt and .gitignore
    # the same bytes, scanned as a plain directory, ARE found - so the zero above is
    # scope, not a scanner that cannot see the file
    assert ss.scan(mode="dir", target=git_repo)["count"] == 1
    # and tracking it brings it into scope
    subprocess.run(["git", "add", "-f", "ignored.env"], cwd=git_repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "track it"], cwd=git_repo, check=True,
                   capture_output=True)
    tracked = ss.scan(mode="tree", target=git_repo)
    assert tracked["count"] == 1
    assert tracked["findings"][0]["File"] == "ignored.env", "paths map back to the repo"


def test_the_tree_scope_needs_a_repository(scanner: Path, tmp_path: Path):
    with pytest.raises(ss.Blocked, match="not a git repository"):
        ss.scan(mode="tree", target=tmp_path)


def test_staged_content_is_scanned_and_an_empty_stage_is_clean(scanner: Path,
                                                               git_repo: Path):
    assert ss.scan(mode="staged", target=git_repo)["count"] == 0
    (git_repo / "leak.txt").write_text(f"token = {_synthetic_github_pat()}\n")
    # unstaged is out of scope for what a commit would record
    assert ss.scan(mode="staged", target=git_repo)["count"] == 0
    subprocess.run(["git", "add", "leak.txt"], cwd=git_repo, check=True, capture_output=True)
    staged = ss.scan(mode="staged", target=git_repo)
    assert staged["count"] == 1 and staged["findings"][0]["RuleID"] == "github-pat"


def test_an_outgoing_commit_range_is_scanned_and_a_clean_range_stays_clean(
        scanner: Path, git_repo: Path):
    def rev(spec: str) -> str:
        return subprocess.run(["git", "rev-parse", spec], cwd=git_repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    base = rev("HEAD")
    (git_repo / "leak.txt").write_text(f"token = {_synthetic_github_pat()}\n")
    subprocess.run(["git", "add", "leak.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "adds a token"], cwd=git_repo, check=True,
                   capture_output=True)
    head = rev("HEAD")
    outgoing = ss.scan(mode="range", target=git_repo, rev_range=f"{base}..{head}")
    assert outgoing["count"] == 1 and outgoing["findings"][0]["Commit"] == head
    # the range that excludes the leaky commit must stay clean, or the range is ignored
    assert ss.scan(mode="range", target=git_repo, rev_range=f"{base}..{base}")["count"] == 0
    with pytest.raises(ss.Blocked, match="revision range"):
        ss.scan(mode="range", target=git_repo, rev_range=None)


# --- 3. it fails closed --------------------------------------------------------------

def test_a_missing_scanner_is_blocked_not_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(tmp_path / "nope"))
    with pytest.raises(ss.Blocked, match="not a file"):
        ss.scan(mode="dir", target=tmp_path)
    assert ss.main(["--dir", str(tmp_path)]) == ss.EXIT_BLOCKED


def test_provisioning_can_be_refused_rather_than_silently_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("QMHP_SECRET_SCANNER", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "empty-cache"))
    with pytest.raises(ss.Blocked, match="provisioning is disabled"):
        ss.resolve_scanner(provision_if_missing=False)


def test_a_scanner_that_fails_is_blocked_not_clean(tmp_path, monkeypatch):
    stub = _stub(tmp_path / "gl", version=ss.TOOL_VERSION, scan_exit=2, stdout="")
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(stub))
    with pytest.raises(ss.Blocked, match="neither clean nor findings"):
        ss.scan(mode="dir", target=tmp_path)
    assert ss.main(["--dir", str(tmp_path)]) == ss.EXIT_BLOCKED


def test_a_wrong_version_scanner_is_blocked(tmp_path, monkeypatch):
    stub = _stub(tmp_path / "gl", version="8.18.0", scan_exit=0)
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(stub))
    with pytest.raises(ss.Blocked, match="not the pinned"):
        ss.scan(mode="dir", target=tmp_path)


def test_an_unstamped_scanner_is_blocked(tmp_path, monkeypatch):
    """`go install` without the ldflag leaves this string; it must not be accepted."""
    stub = _stub(tmp_path / "gl", version="version is set by build process", scan_exit=0)
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(stub))
    with pytest.raises(ss.Blocked, match="not the pinned"):
        ss.scan(mode="dir", target=tmp_path)


def test_findings_without_a_readable_report_are_blocked(tmp_path, monkeypatch):
    """Exit 1 with nothing to redact must not be reported as a clean or silent pass."""
    stub = _stub(tmp_path / "gl", version=ss.TOOL_VERSION, scan_exit=1, stdout="")
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(stub))
    with pytest.raises(ss.Blocked, match="no report to redact"):
        ss.scan(mode="dir", target=tmp_path)
    bad = _stub(tmp_path / "gl2", version=ss.TOOL_VERSION, scan_exit=1, stdout="not json")
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(bad))
    with pytest.raises(ss.Blocked, match="did not parse"):
        ss.scan(mode="dir", target=tmp_path)


def test_a_baseline_is_refused(tmp_path, monkeypatch):
    stub = _stub(tmp_path / "gl", version=ss.TOOL_VERSION, scan_exit=0)
    monkeypatch.setenv("QMHP_SECRET_SCANNER", str(stub))
    baseline = tmp_path / "baseline.json"
    baseline.write_text("[]")
    with pytest.raises(ss.Blocked, match="baseline is refused"):
        ss.scan(mode="tree", target=tmp_path, baseline=str(baseline))
    assert ss.main(["--dir", str(tmp_path),
                    "--baseline-path", str(baseline)]) == ss.EXIT_BLOCKED
    assert "--baseline" not in SCRIPT.read_text().split("def build_argv")[1].split("def ")[0]


def test_the_exit_codes_distinguish_clean_findings_and_blocked(scanner, tmp_path, capsys):
    (tmp_path / "ok.txt").write_text("nothing here\n")
    assert ss.main(["--dir", str(tmp_path)]) == ss.EXIT_CLEAN
    (tmp_path / "leak.env").write_text(f"T={_synthetic_github_pat()}\n")
    assert ss.main(["--dir", str(tmp_path)]) == ss.EXIT_FINDINGS
    out = capsys.readouterr()
    assert _synthetic_github_pat() not in out.out + out.err
    assert ss.EXIT_CLEAN == 0 and ss.EXIT_FINDINGS == 1 and ss.EXIT_BLOCKED == 3


# --- 4. the integration is real ------------------------------------------------------

def test_ci_runs_the_scanner_read_only():
    """Pinned separately from the detection tests, which skip without the binary."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "scripts/secret_scan.py --tree" in ci
    # read-only: the scan step neither writes to the tree nor needs a token
    assert "secret_scan.py --tree --no-provision" not in ci, "CI must provision the pin"
    assert SCRIPT.is_file() and os.access(SCRIPT, os.X_OK)
