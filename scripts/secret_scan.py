#!/usr/bin/env python3
"""The repository's approved secret scanner (CLAUDE.md section 10).

STANDALONE AND VERSION-PINNED. gitleaks is not vendored, not committed and not a
Python dependency. It is provisioned from the Go module proxy at one pinned module
version, whose hash the Go checksum database verifies during `go install`, and the
resolved binary must report that version before a single byte is scanned.

SCOPES, the smallest set that covers what leaves a working tree:

  --staged       what `git commit` would record
  --range A..B   what `git push` would send
  --tree         the repository's TRACKED files, for read-only CI
  --dir PATH     a directory as it stands, for ad-hoc use and for the tests

--tree is tracked files only, and deliberately not `gitleaks dir` over the checkout.
gitleaks does not read .gitignore, so scanning the checkout directory scans .venv,
__pycache__ and the tool caches as well - on this repository that is 940 MB instead of
264 MB, and it reported a finding in a vendored gmsh CHANGELOG that is not repository
content at all. Tracked paths are hardlinked into a temporary directory, scanned there
and the paths mapped back, so the scope is exact without adding a .gitleaksignore -
which is the same suppress-by-list mechanism as a baseline and is likewise refused.

IT FAILS CLOSED. A scanner that is missing, unprovisionable, the wrong version, or
that exits for any reason other than a clean or leaky verdict is BLOCKED (exit 3) and
never a pass. `grep` is not a substitute and neither is a skipped step: a caller that
cannot run this must report BLOCKED.

THERE IS NO BASELINE. `--baseline-path` is refused rather than passed through: a
baseline is a committed list of secrets to ignore, which is the failure this exists to
prevent. Findings are suppressed only by gitleaks' own upstream rules.

FINDINGS ARE REDACTED TWICE. gitleaks runs with --redact=100, and this reporter prints
an ALLOWLIST of fields, so the secret, the matched text, the commit message and the
author are withheld even if a future gitleaks version changes its redaction default.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- the pin -------------------------------------------------------------------------
#
# Established 2026-09-21 against proxy.golang.org and sum.golang.org:
#
#   GET https://proxy.golang.org/github.com/zricethezav/gitleaks/v8/@v/v8.30.1.info
#     {"Version":"v8.30.1","Time":"2026-02-21T13:30:12Z",
#      "Origin":{"VCS":"git","URL":"https://github.com/zricethezav/gitleaks",
#                "Hash":"8d1f98c7967eb1e79cb44ac6241a124e145d2165",
#                "Ref":"refs/tags/v8.30.1"}}
#   GET https://sum.golang.org/lookup/github.com/zricethezav/gitleaks/v8@v8.30.1
#     github.com/zricethezav/gitleaks/v8 v8.30.1 h1:PmEvCfVI7ti9dV3s5aMZUY7sS2GxRvG3yzih7E+cS3w=
#
# `go install` verifies MODULE_H1 against the checksum database itself; it is recorded
# here so a silent change of the module contents is visible in this file's history.
# The module path is the historical zricethezav one: github.com/gitleaks/gitleaks/v8
# does not resolve, because the module never declared that path.
MODULE = "github.com/zricethezav/gitleaks/v8"
MODULE_VERSION = "v8.30.1"
MODULE_H1 = "h1:PmEvCfVI7ti9dV3s5aMZUY7sS2GxRvG3yzih7E+cS3w="
VCS_URL = "https://github.com/zricethezav/gitleaks"
VCS_TAG = "refs/tags/v8.30.1"
VCS_COMMIT = "8d1f98c7967eb1e79cb44ac6241a124e145d2165"

#: What `gitleaks version` must print. `go install` alone leaves it unset ("version is
#: set by the build process"), so the version is stamped with the SAME ldflag upstream's
#: own .goreleaser.yml uses, and then read back. An unstamped or mismatched binary is
#: BLOCKED: without this the pin would be unverifiable at the point of use.
TOOL_VERSION = "8.30.1"
LDFLAGS = f"-s -w -X={MODULE}/version.Version={TOOL_VERSION}"

#: MIT, "Copyright (c) 2019 Zachary Rice" (LICENSE in the module). Permissive, no
#: copyleft obligation on this repository, and nothing of gitleaks is redistributed
#: here: the binary is fetched at use time into a cache outside the working tree.
LICENCE = "MIT"

EXIT_CLEAN, EXIT_FINDINGS, EXIT_BLOCKED = 0, 1, 3

#: Printed for each finding. An ALLOWLIST, so a field added by a future gitleaks
#: version cannot leak a value by default.
REPORTED_FIELDS = ("RuleID", "Description", "File", "SymlinkFile", "StartLine", "EndLine",
                   "StartColumn", "EndColumn", "Commit", "Date", "Entropy", "Fingerprint",
                   "Tags")
#: Never printed, whatever --redact did: the secret itself, the line it sits on, the
#: commit message, and who wrote it.
WITHHELD_FIELDS = ("Secret", "Match", "Message", "Author", "Email")


class Blocked(RuntimeError):
    """The scan could not be performed. This is never a pass."""


def cache_binary() -> Path:
    """Outside the working tree: a scanner binary is not a repository artefact."""
    root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "qmhp-cem" / f"gitleaks-{TOOL_VERSION}" / "gitleaks"


def reported_version(binary: Path) -> str:
    try:
        out = subprocess.run([str(binary), "version"], capture_output=True, text=True,
                             timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Blocked(f"{binary} would not run: {exc}") from exc
    if out.returncode != 0:
        raise Blocked(f"{binary} version exited {out.returncode}: {out.stderr.strip()[:200]}")
    return out.stdout.strip()


def provision(dest: Path) -> Path:
    """`go install` the pinned module. The checksum database verifies it; a failure
    here is BLOCKED, never a silent fallback to some other gitleaks on PATH."""
    go = shutil.which("go")
    if not go:
        raise Blocked(
            f"no Go toolchain, so {MODULE}@{MODULE_VERSION} cannot be provisioned. "
            f"Install Go, or set QMHP_SECRET_SCANNER to a gitleaks {TOOL_VERSION} binary.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GOBIN=str(dest.parent), GOFLAGS="-trimpath")
    proc = subprocess.run([go, "install", f"-ldflags={LDFLAGS}",
                           f"{MODULE}@{MODULE_VERSION}"],
                          capture_output=True, text=True, env=env, timeout=1800)
    if proc.returncode != 0 or not dest.is_file():
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-6:]
        raise Blocked(f"go install {MODULE}@{MODULE_VERSION} failed "
                      f"(exit {proc.returncode}): " + " | ".join(tail))
    return dest


def resolve_scanner(*, provision_if_missing: bool = True) -> Path:
    """QMHP_SECRET_SCANNER, then the cache, then a pinned build. Version-checked."""
    override = os.environ.get("QMHP_SECRET_SCANNER")
    if override:
        binary = Path(override)
        if not binary.is_file():
            raise Blocked(f"QMHP_SECRET_SCANNER={override} is not a file")
    else:
        binary = cache_binary()
        if not binary.is_file():
            if not provision_if_missing:
                raise Blocked(f"no scanner at {binary} and provisioning is disabled")
            binary = provision(binary)
    got = reported_version(binary)
    if got != TOOL_VERSION:
        raise Blocked(f"{binary} reports version {got!r}, not the pinned {TOOL_VERSION!r}")
    return binary


def provenance(binary: Path) -> dict:
    """What was actually used. The binary digest is MEASURED here, not asserted: a Go
    binary is not bit-identical across toolchains, so the module version, its checksum
    database hash and the version the binary reports are the pin; the digest records
    which build produced this particular file."""
    return {
        "tool": "gitleaks",
        "module": MODULE,
        "module_version": MODULE_VERSION,
        "module_h1_expected": MODULE_H1,
        "vcs_url": VCS_URL,
        "vcs_tag": VCS_TAG,
        "vcs_commit": VCS_COMMIT,
        "licence": LICENCE,
        "binary": str(binary),
        "binary_sha256_measured": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "version_reported": reported_version(binary),
        "go": (subprocess.run([shutil.which("go") or "go", "version"], capture_output=True,
                              text=True).stdout.strip() if shutil.which("go") else None),
    }


def build_argv(binary: Path, *, mode: str, target: Path, rev_range: str | None) -> list[str]:
    """The exact argv a scan runs, exposed so tests can pin it without scanning."""
    common = ["--no-banner", "--redact=100", "--exit-code", str(EXIT_FINDINGS),
              "--report-format", "json", "--report-path", "-"]
    if mode in ("tree", "dir"):
        return [str(binary), "dir", *common, str(target)]
    if mode == "staged":
        return [str(binary), "git", "--staged", *common, str(target)]
    if mode == "range":
        return [str(binary), "git", f"--log-opts={rev_range}", *common, str(target)]
    raise Blocked(f"unknown scan mode {mode!r}")


def tracked_files(repo: Path) -> list[str]:
    """Exactly what git tracks, so the scope is the repository and not the disk."""
    proc = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise Blocked(f"{repo} is not a git repository, so --tree has no tracked scope "
                      f"(git said: {proc.stderr.strip()[:160]}). Use --dir for a plain "
                      "directory.")
    return [p for p in proc.stdout.split("\0") if p]


@contextlib.contextmanager
def materialised_tracked(repo: Path):
    """Hardlink the tracked files into a disposable directory and yield it.

    Hardlinks, not copies: the scanner only reads, and 264 MB of tracked content should
    not be duplicated on every scan. A symlink is recreated as a symlink so the scanner
    sees the same shape; a tracked path missing from the working tree is skipped,
    because there is nothing to scan.
    """
    repo = Path(repo).resolve()
    paths = tracked_files(repo)
    with tempfile.TemporaryDirectory(prefix="qmhp-secret-scan-") as tmp:
        root = Path(tmp)
        linked = 0
        for rel in paths:
            src, dst = repo / rel, root / rel
            if not src.is_symlink() and not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                os.symlink(os.readlink(src), dst)
            else:
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
            linked += 1
        if not linked:
            raise Blocked(f"{repo} tracks no files, so there is nothing to scan")
        yield root, linked


def redact(findings: list[dict]) -> list[dict]:
    """Allowlist the printable fields. Nothing in WITHHELD_FIELDS survives this."""
    return [{k: f[k] for k in REPORTED_FIELDS if k in f} for f in findings]


def _run(binary: Path, argv: list[str]) -> list[dict]:
    """One scanner invocation. Anything but a clean or leaky verdict is BLOCKED."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Blocked(f"the scanner did not complete: {exc}") from exc
    if proc.returncode not in (EXIT_CLEAN, EXIT_FINDINGS):
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        raise Blocked(f"the scanner exited {proc.returncode}, which is neither clean nor "
                      "findings: " + " | ".join(tail))
    try:
        findings = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise Blocked(f"the scanner's report did not parse: {exc}") from exc
    if proc.returncode == EXIT_FINDINGS and not findings:
        raise Blocked("the scanner reported findings but produced no report to redact")
    return findings


def scan(*, mode: str, target: Path = REPO_ROOT, rev_range: str | None = None,
         provision_if_missing: bool = True, baseline: str | None = None) -> dict:
    if baseline:
        raise Blocked("a baseline is refused: this scanner does not carry a list of "
                      "secrets to ignore. Remove the finding, do not record it.")
    if mode == "range" and not rev_range:
        raise Blocked("--range needs a revision range, e.g. origin/main..HEAD")
    target = Path(target)
    binary = resolve_scanner(provision_if_missing=provision_if_missing)
    scanned = None
    if mode == "tree":
        with materialised_tracked(target) as (root, linked):
            findings = _run(binary, build_argv(binary, mode="dir", target=root,
                                               rev_range=None))
            scanned = linked
            # map the temporary paths back onto the repository they came from
            for f in findings:
                for key in ("File", "SymlinkFile"):
                    if f.get(key):
                        with contextlib.suppress(ValueError):
                            f[key] = str(Path(f[key]).resolve().relative_to(root))
    else:
        findings = _run(binary, build_argv(binary, mode=mode, target=target,
                                           rev_range=rev_range))
    return {"mode": mode, "target": str(target), "range": rev_range,
            "tracked_files_scanned": scanned, "provenance": provenance(binary),
            "findings": redact(findings), "count": len(findings)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--staged", action="store_true", help="what a commit would record")
    scope.add_argument("--range", dest="rev_range", metavar="A..B",
                       help="what a push would send")
    scope.add_argument("--tree", action="store_true",
                       help="the repository's tracked files (read-only CI)")
    scope.add_argument("--dir", dest="plain_dir", metavar="PATH",
                       help="a directory as it stands, tracked or not")
    scope.add_argument("--print-provenance", action="store_true",
                       help="resolve the scanner and print its pin, without scanning")
    ap.add_argument("--target", type=Path, default=REPO_ROOT)
    ap.add_argument("--no-provision", action="store_true",
                    help="do not build the pinned scanner if it is absent (BLOCKS instead)")
    ap.add_argument("--baseline-path", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        if args.print_provenance:
            binary = resolve_scanner(provision_if_missing=not args.no_provision)
            print(json.dumps(provenance(binary), indent=1))
            return EXIT_CLEAN
        mode = ("staged" if args.staged else "range" if args.rev_range
                else "dir" if args.plain_dir else "tree")
        target = Path(args.plain_dir) if args.plain_dir else args.target
        result = scan(mode=mode, target=target, rev_range=args.rev_range,
                      provision_if_missing=not args.no_provision,
                      baseline=args.baseline_path)
    except Blocked as exc:
        print(f"SECRET SCAN BLOCKED: {exc}", file=sys.stderr)
        print("A blocked scan is not a clean scan. Do not push.", file=sys.stderr)
        return EXIT_BLOCKED
    print(json.dumps(result, indent=1))
    if result["count"]:
        print(f"SECRET SCAN FOUND {result['count']} finding(s) in scope {mode!r}. "
              "Values are withheld; remove the secret and rewrite the change.",
              file=sys.stderr)
        return EXIT_FINDINGS
    print(f"secret scan clean: gitleaks {TOOL_VERSION}, scope {mode!r}", file=sys.stderr)
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
