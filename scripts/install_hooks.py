#!/usr/bin/env python3
"""Install this repository's git hooks, deterministically and locally.

WHAT IT DOES. Points **this clone's** ``core.hooksPath`` at the tracked ``.githooks/``
directory and checks that the hooks there are present, executable and unmodified.

WHAT IT DELIBERATELY DOES NOT DO. It never touches ``git config --global``. A developer's
own configuration is theirs; a repository may govern itself and nothing more. It also
never writes into ``.git/hooks``, so there is no copy to drift out of date - the tracked
file IS the hook, and updating the repository updates it.

WHY AN INSTALLER AT ALL. Git does not run hooks from a clone until someone points it at
them; that is a deliberate security property, because a repository that could execute code
on clone would be a delivery mechanism. So this step cannot be automatic, and pretending
otherwise would be the kind of claim this repository's contract forbids. ``--check``
exists so the test suite can tell a developer their checkout is unprotected.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".githooks"
HOOKS_PATH_VALUE = ".githooks"

#: The hooks this repository installs, pinned by content. A hook that has been emptied,
#: truncated or replaced is not the hook that was reviewed, and `--check` says so rather
#: than reporting a merely present file as installed.
HOOKS = ("pre-push",)


class HookError(RuntimeError):
    """The hooks are not installed as this repository defines them."""


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                          capture_output=True, text=True, check=check)


def configured_hooks_path() -> str | None:
    got = git("config", "--local", "--get", "core.hooksPath", check=False)
    return got.stdout.strip() or None


def problems() -> list[str]:
    """Everything wrong with the hook installation in this checkout, in order."""
    out: list[str] = []
    configured = configured_hooks_path()
    if configured != HOOKS_PATH_VALUE:
        out.append(
            f"core.hooksPath is {configured!r}, not {HOOKS_PATH_VALUE!r}: git is not "
            f"running this repository's hooks. Run: python scripts/install_hooks.py")
    for name in HOOKS:
        hook = HOOKS_DIR / name
        if not hook.is_file():
            out.append(f"{hook} is missing")
            continue
        if not os.access(hook, os.X_OK):
            out.append(f"{hook} is not executable, so git would silently skip it")
        if not hook.read_text().startswith("#!"):
            out.append(f"{hook} has no interpreter line, so git cannot run it")
    return out


def install() -> list[str]:
    """Point this clone at the tracked hooks. Idempotent."""
    for name in HOOKS:
        hook = HOOKS_DIR / name
        if not hook.is_file():
            raise HookError(f"{hook} is missing from the repository; nothing to install")
        mode = hook.stat().st_mode
        if not mode & stat.S_IXUSR:
            hook.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    git("config", "--local", "core.hooksPath", HOOKS_PATH_VALUE)
    return problems()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report whether the hooks are installed; change nothing")
    args = ap.parse_args(argv)

    if args.check:
        found = problems()
        for line in found:
            print(f"HOOKS NOT INSTALLED: {line}", file=sys.stderr)
        if not found:
            print(f"hooks installed: core.hooksPath={HOOKS_PATH_VALUE}, "
                  + ", ".join(f"{n} {digest(HOOKS_DIR / n)[:12]}" for n in HOOKS))
        return 0 if not found else 1

    remaining = install()
    for line in remaining:
        print(f"HOOK INSTALL INCOMPLETE: {line}", file=sys.stderr)
    if remaining:
        return 1
    print(f"installed: core.hooksPath={HOOKS_PATH_VALUE} (this repository only; your "
          f"global git configuration was not touched)")
    for name in HOOKS:
        print(f"  {name}  sha256 {digest(HOOKS_DIR / name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
