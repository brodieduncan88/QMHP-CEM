"""Phase C, increment 5: the secret scan runs BEFORE the push.

THE GAP, reproduced on the frozen snapshot ec8dd20d137425a9ccd0005b6cde1546475864e2.
The repository already had an approved scanner with tested `--staged` and `--range`
scopes and a read-only CI job. Nothing invoked it before a push. On that snapshot, a
commit containing a synthetic `github-pat` was pushed to a throwaway local bare
repository and ARRIVED; the same commit, handed to `scripts/secret_scan.py --range`,
reported exactly one finding. The scanner could see it and was simply never asked.

WHAT NOW ASKS IT. `.githooks/pre-push`, activated by `scripts/install_hooks.py`, which
points this clone's `core.hooksPath` at the tracked directory and never touches the
developer's global git configuration.

FAIL CLOSED, AND AFFIRMATIVELY. A push proceeds only on exit status 0 TOGETHER WITH the
scanner's own clean marker. The marker is not decoration: an uncaught Python exception
also exits 1, so the exit code alone cannot separate a findings verdict from a crash, and
an earlier draft of this hook reported a crash as "found secret(s)" - refusing correctly
while saying something untrue about why.

TWO DEFECTS IN THE HOOK ITSELF WERE FOUND BY THESE CONTROLS, both by the POSITIVE one:

  * the human label was passed through to the scanner as a positional argument, so
    argparse exited 2 and the indeterminate branch refused EVERY push, clean ones
    included. Fail-closed hid the bug rather than causing it.
  * a deletion-only push fell through to a full tree scan, so deleting a branch could be
    refused by an unrelated secret sitting in the working tree.

A guard that only ever refuses is indistinguishable from a broken one, which is why the
positive controls here carry as much weight as the negative controls.

Most tests drive the hook with a STUB scanner whose exit status and output they choose,
so every refusal path is exercised deterministically and fast. Two tests use the real
approved scanner end to end. Nothing here pushes anywhere but a temporary bare repository
inside `tmp_path`.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".githooks" / "pre-push"
INSTALLER = REPO_ROOT / "scripts" / "install_hooks.py"
REAL_SCANNER = REPO_ROOT / "scripts" / "secret_scan.py"

#: The frozen snapshot the pre-push gap was reproduced on.
FROZEN_SHA = "ec8dd20d137425a9ccd0005b6cde1546475864e2"

#: The hook, pinned by content. A hook emptied, truncated or replaced is not the hook
#: these controls exercise, and CI fails rather than reporting a present file as a guard.
HOOK_SHA256 = "3e25dd09e6985543c3268fa237079030dc3a7848888533ac00b0fec480155735"

ZERO = "0" * 40

#: What the real scanner prints. The hook keys on these, so a change to either side that
#: the other does not follow must fail here rather than in production.
CLEAN_MARKER = "secret scan clean"
FINDING_MARKER = "SECRET SCAN FOUND"
BLOCKED_MARKER = "SECRET SCAN BLOCKED"

SYNTHETIC_SECRET = "ghp_" + "0123456789abcdefghijABCDEFGHIJ012345"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check)


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@t")
    (repo / "scripts").mkdir()
    (repo / "README.md").write_text("a repository\n")
    shutil.copytree(REPO_ROOT / ".githooks", repo / ".githooks")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def stub_scanner(repo: Path, *, exit_code: int, output: str = "") -> None:
    """A scanner whose verdict the test chooses, so every branch is reachable."""
    body = "import sys\n"
    if output:
        body += f"print({output!r})\n"
    body += f"sys.exit({exit_code})\n"
    (repo / "scripts" / "secret_scan.py").write_text(body)


def run_hook(repo: Path, *, local_sha: str | None = None, remote_sha: str = ZERO,
             stdin: str | None = None) -> subprocess.CompletedProcess:
    """Invoke the hook exactly as git would: refs on stdin, cwd inside the repository."""
    if stdin is None:
        local_sha = local_sha or git(repo, "rev-parse", "HEAD").stdout.strip()
        stdin = f"refs/heads/x {local_sha} refs/heads/x {remote_sha}\n"
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(["sh", str(repo / ".githooks" / "pre-push"), "sandbox",
                           "file:///nonexistent"],
                          cwd=repo, input=stdin, capture_output=True, text=True, env=env)


# --- A. the hook is the reviewed hook ------------------------------------------------


def test_the_hook_exists_is_executable_and_is_the_reviewed_one():
    assert HOOK.is_file(), "the tracked hook is missing"
    assert os.access(HOOK, os.X_OK), "git silently skips a hook that is not executable"
    assert HOOK.read_text().startswith("#!"), "git cannot run a hook with no interpreter line"
    assert hashlib.sha256(HOOK.read_bytes()).hexdigest() == HOOK_SHA256, (
        "the pre-push hook has changed. That may be deliberate - if so, re-run the "
        "controls in this module and update HOOK_SHA256 in the same reviewed change.")


def test_the_hook_calls_the_approved_scanner_and_nothing_else():
    """It must not grow its own grep-based scanner, which the contract forbids."""
    text = HOOK.read_text()
    assert "scripts/secret_scan.py" in text
    assert "--tree" in text and "--range" in text
    for forbidden in ("--baseline", "gitleaks detect", "grep -rE", "|| true", "exit 0 #"):
        assert forbidden not in text, forbidden


# --- B. positive controls: a clean push proceeds -------------------------------------


def test_a_clean_new_branch_passes(tmp_path: Path):
    repo = make_repo(tmp_path)
    stub_scanner(repo, exit_code=0, output=f"{CLEAN_MARKER}: gitleaks 8.30.1, scope 'tree'")
    got = run_hook(repo, remote_sha=ZERO)
    assert got.returncode == 0, got.stderr
    assert "secret scan clean" in got.stderr


def test_a_clean_update_to_an_existing_branch_passes(tmp_path: Path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "more.txt").write_text("x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "second")
    stub_scanner(repo, exit_code=0, output=f"{CLEAN_MARKER}: scope 'range'")
    got = run_hook(repo, remote_sha=first)
    assert got.returncode == 0, got.stderr
    assert "clean" in got.stderr


def test_a_deletion_only_push_is_allowed_without_a_tree_scan(tmp_path: Path):
    """Found by the positive controls: a deletion pushes no content, and an earlier draft
    scanned the whole working tree for it - so an unrelated secret could block a delete."""
    repo = make_repo(tmp_path)
    stub_scanner(repo, exit_code=1, output=f"{FINDING_MARKER} 1 finding(s)")
    got = run_hook(repo, stdin=f"(delete) {ZERO} refs/heads/gone {'a' * 40}\n")
    assert got.returncode == 0, got.stderr
    assert "all deletions" in got.stderr


# --- C. negative controls: every way a scan can fail to be clean ---------------------


@pytest.mark.parametrize("exit_code,output,expected", [
    (1, f"{FINDING_MARKER} 2 finding(s) in scope 'range'", "found secret(s)"),
    (3, f"{BLOCKED_MARKER}: gitleaks unavailable", "BLOCKED"),
    (1, "Traceback (most recent call last): RuntimeError", "no recognised verdict"),
    (42, "who knows", "exited 42"),
    (2, "usage: secret_scan.py", "exited 2"),
    (0, "all good", "without its clean marker"),
    (0, "", "without its clean marker"),
])
def test_only_an_affirmative_clean_verdict_lets_a_push_through(
        tmp_path: Path, exit_code, output, expected):
    repo = make_repo(tmp_path, f"r{exit_code}{len(output)}")
    stub_scanner(repo, exit_code=exit_code, output=output)
    got = run_hook(repo)
    assert got.returncode != 0, f"ACCEPTED: exit {exit_code} with {output!r}"
    assert "PUSH REFUSED" in got.stderr
    assert expected in got.stderr, got.stderr
    # the advice line wraps, so match a fragment that cannot straddle the break
    assert "not add a baseline" in got.stderr


def test_a_missing_scanner_is_blocked_not_clean(tmp_path: Path):
    repo = make_repo(tmp_path)
    got = run_hook(repo)
    assert got.returncode != 0
    assert "the approved scanner is missing" in got.stderr and "BLOCKED" in got.stderr


def test_an_unresolvable_remote_commit_is_blocked(tmp_path: Path):
    """If the pushed range cannot be determined, the scan scope is unknown - which is not
    the same as empty."""
    repo = make_repo(tmp_path)
    stub_scanner(repo, exit_code=0, output=CLEAN_MARKER)
    got = run_hook(repo, remote_sha="b" * 40)
    assert got.returncode != 0
    assert "cannot resolve the remote commit" in got.stderr


def test_no_ref_information_still_scans(tmp_path: Path):
    """Empty stdin must not read as "nothing to push"."""
    repo = make_repo(tmp_path)
    stub_scanner(repo, exit_code=1, output=f"{FINDING_MARKER} 1 finding(s)")
    got = run_hook(repo, stdin="")
    assert got.returncode != 0
    assert "found secret(s)" in got.stderr


# --- D. end to end, with the real approved scanner ------------------------------------


@pytest.mark.parametrize("leak", [False, True], ids=["clean", "synthetic-secret"])
def test_the_real_scanner_end_to_end(tmp_path: Path, leak: bool):
    """The two controls that matter most, with no stub anywhere: the repository's own
    scanner, the repository's own hook, a real push to a throwaway bare repository."""
    repo = make_repo(tmp_path, "real")
    shutil.copy2(REAL_SCANNER, repo / "scripts" / "secret_scan.py")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "sandbox", f"file://{bare}")
    git(repo, "config", "core.hooksPath", ".githooks")
    if leak:
        (repo / "leak.py").write_text(f'TOKEN = "{SYNTHETIC_SECRET}"\n')
    else:
        (repo / "ok.py").write_text("VALUE = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")

    pushed = subprocess.run(["git", "-C", str(repo), "push", "sandbox", "HEAD:refs/heads/main"],
                            capture_output=True, text=True)
    listed = subprocess.run(["git", "-C", str(bare), "ls-tree", "-r", "--name-only", "main"],
                            capture_output=True, text=True)
    if leak:
        assert pushed.returncode != 0, "the secret was pushed"
        assert "found secret(s)" in pushed.stderr
        assert "leak.py" not in listed.stdout, "the secret reached the remote"
    else:
        assert pushed.returncode == 0, pushed.stderr
        assert "ok.py" in listed.stdout


# --- E. the installer ------------------------------------------------------------------


def installer(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(repo / "scripts" / "install_hooks.py"), *args],
                          cwd=repo, capture_output=True, text=True)


def test_the_installer_reports_an_uninstalled_checkout_then_installs_it(tmp_path: Path):
    repo = make_repo(tmp_path)
    shutil.copy2(INSTALLER, repo / "scripts" / "install_hooks.py")

    before = installer(repo, "--check")
    assert before.returncode == 1 and "HOOKS NOT INSTALLED" in before.stderr

    done = installer(repo)
    assert done.returncode == 0 and "core.hooksPath=.githooks" in done.stdout
    assert git(repo, "config", "--local", "--get", "core.hooksPath").stdout.strip() == ".githooks"

    after = installer(repo, "--check")
    assert after.returncode == 0 and "hooks installed" in after.stdout
    assert installer(repo).returncode == 0, "the installer must be idempotent"


def test_the_installer_never_touches_the_global_configuration():
    """A repository may govern itself and nothing more.

    Checked over the AST rather than the source text: the module's own docstring says it
    never touches `git config --global`, and a substring search on the file would be
    satisfied by that sentence while missing a real call.
    """
    import ast

    tree = ast.parse(INSTALLER.read_text())
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    call_args = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_args |= {a.value for a in node.args
                          if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    assert "--global" not in call_args, "the installer passes --global to a call"
    assert "--global" not in (literals - {v for v in literals if "\n" in v}), \
        "a bare '--global' literal exists outside prose"
    assert "--local" in call_args, "the installer must scope its config writes locally"


def test_a_hook_that_is_present_but_not_executable_is_reported(tmp_path: Path):
    """git skips a non-executable hook in silence, which would look exactly like a clean
    push. --check must not call that installed."""
    repo = make_repo(tmp_path)
    shutil.copy2(INSTALLER, repo / "scripts" / "install_hooks.py")
    installer(repo)
    (repo / ".githooks" / "pre-push").chmod(0o644)
    got = installer(repo, "--check")
    assert got.returncode == 1 and "not executable" in got.stderr


def test_a_missing_hook_is_reported(tmp_path: Path):
    repo = make_repo(tmp_path)
    shutil.copy2(INSTALLER, repo / "scripts" / "install_hooks.py")
    installer(repo)
    (repo / ".githooks" / "pre-push").unlink()
    got = installer(repo, "--check")
    assert got.returncode == 1 and "is missing" in got.stderr


def test_this_checkout_has_the_hooks_installed():
    """A developer running the suite is TOLD when their checkout is unprotected, which is
    the closest thing to enforcement git allows: hooks cannot be activated by cloning,
    deliberately, because a repository that ran code on clone would be a delivery
    mechanism. Skipped in CI, which pushes nothing."""
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        pytest.skip("CI checkouts push nothing; the hook is a developer-side control")
    got = subprocess.run([sys.executable, str(INSTALLER), "--check"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    assert got.returncode == 0, (
        "this checkout is not protected by the pre-push secret scan. "
        "Run: python scripts/install_hooks.py\n" + got.stderr)
