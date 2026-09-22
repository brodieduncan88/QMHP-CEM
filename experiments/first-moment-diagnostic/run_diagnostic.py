#!/usr/bin/env python3
"""Launcher for the first-moment diagnostic: PREPARED, NOT ACTIVATED.

The documented ``docker run`` command is not by itself a timeout mechanism and
captures no provenance, so this module supplies both. It is inert: every entry
point refuses unless ``EXECUTION-APPROVAL.json`` exists beside this file AND
matches the prepared digests exactly. That file is deliberately absent, so
importing or invoking this module cannot start a solve. No workflow references
it and nothing in the test suite executes its run path.

What it enforces when a separate approval does exist:

  * WALL-CLOCK CAP - the container is read line by line with a deadline; on
    expiry the container is killed, the partial log is preserved and the run is
    recorded FAILED. No retry.
  * DOF CAP - the streamed log is probed for Palace's one-shot
    "number of global unknowns" line and the container is killed the moment the
    finest ND count exceeds the budget, before the solve proceeds.
  * IMAGE BINDING - the approval must NAME the image it authorises, as a full
    immutable ID. Before any container starts, the local image is resolved by
    METADATA INSPECTION ONLY (``docker image inspect``, which runs nothing) and
    that measured ID is compared with the approved one. A missing approval, a
    missing or malformed ``image_id``, an absent image, a failed inspection or
    any mismatch refuses. Everything afterwards - the identity-reading
    containers and the solve itself - is addressed by that immutable ID, never
    by the tag, and ``--pull=never`` means an absent image refuses instead of
    being fetched.
  * PROVENANCE - the image ID, repo digests and labels, the four PALACE_*
    identity files read from inside the image, and the sha256 of the config,
    mesh, patch, Dockerfile and of this diagnostic's own code are written to
    ``provenance.json`` beside the record. The approval that authorised the run
    is frozen beside it as ``approval-snapshot.json`` with its digest, so the
    record is judged against the approval that actually authorised it and not
    against whatever the live file says later. ``evaluate_record.py`` requires
    all of them and refuses to qualify a record that is missing any.

Nothing here computes a physical E_C or g.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from reference_model import DOF_HARD_CAP, WALL_HARD_CAP_S  # noqa: E402

#: The approval that would authorise ONE execution. Absent by design.
APPROVAL_PATH = HERE / "EXECUTION-APPROVAL.json"
CONTAINER_WORKDIR = "/work"
CONFIG_FILENAME = "config.json"
IMAGE = "qmhp-cem/palace-first-moment:0.13.0"
DIAGNOSTIC_CODE = ("reference_model.py", "prepare.py", "evaluate_record.py",
                   "run_diagnostic.py")
IMAGE_IDENTITY_FILES = ("PALACE_VERSION", "PALACE_COMMIT", "PALACE_PATCH",
                        "PALACE_PATCH_SHA256")
#: A full immutable image ID. A tag, a short ID or a repo digest is NOT an identity: a
#: tag can be moved between the check and the launch, and a short ID is not unique.
IMAGE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: The approval bytes, frozen beside the record they authorised.
APPROVAL_SNAPSHOT = "approval-snapshot.json"


class Refusal(RuntimeError):
    """Raised instead of launching anything."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dof_probe_pattern(order: int) -> "re.Pattern[str]":
    """The finest-space count, not a multigrid level.

    Palace prints "Assembling system matrices, number of global unknowns:" once, over
    GetFinestFESpace(), and separately prints per-level counts under "Assembling multigrid
    hierarchy:". Matching the hierarchy lines would enforce the budget against a coarse
    count, so the pattern deliberately matches only the header line's ND entry. This is
    the same pattern scripts/palace_order1_ladder.py enforces the 250 000 rule with.
    """
    return re.compile(rf"ND \(p = {order}\):\s*(\d+)")


def build_command(image: str = IMAGE, *, workdir: Path, name: str, np_processes: int = 1,
                  runtime: str = "docker", line_buffered: bool = True,
                  user: bool = True) -> list[str]:
    """The exact argv a run would execute, exposed so tests can pin it without running it.

    ``--network none`` because the diagnostic needs no network; stdbuf fronts the image
    ENTRYPOINT so the DOF line reaches the probe when Palace prints it rather than a
    4 KiB buffer later.
    """
    entry = ["--entrypoint", "stdbuf"] if line_buffered else []
    palace = ["-oL", "-eL", "palace"] if line_buffered else []
    user_flag = (["--user", f"{os.getuid()}:{os.getgid()}"]
                 if user and runtime == "docker" and hasattr(os, "getuid") else [])
    return [
        runtime, "run", "--rm", "--network", "none", "--hostname", "localhost",
        # an absent image must REFUSE, never be fetched: a pull would replace the image
        # whose ID was just approved with whatever a registry serves now
        "--pull=never",
        "--name", name, *user_flag, *entry,
        "-e", "HOME=/tmp", "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{Path(workdir).resolve()}:{CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR,
        image, *palace, "-np", str(np_processes), CONFIG_FILENAME,
    ]


def load_approval(path: Path = APPROVAL_PATH, *, required: dict | None = None,
                  require_image_id: bool = True) -> dict:
    """Refuse unless a separate approval exists, matches the prepared digests AND names
    the exact image it authorises.

    Read FIRST, before anything is inspected and long before anything is launched. The
    image identity is the approval's to state; it is never taken from the launcher, the
    tag, the environment or the machine.
    """
    if not Path(path).is_file():
        raise Refusal(
            f"no execution approval at {path}: the first-moment diagnostic is PREPARED, "
            "NOT ACTIVATED. One separate approval, naming the mechanism, is required; "
            "the spent PO1 approval and .github/ladder-approval.json must not be reused.")
    body = json.loads(Path(path).read_text())
    if body.get("diagnostic") != "first-moment":
        raise Refusal("the approval is not for the first-moment diagnostic")
    if body.get("authorises") != "one execution":
        raise Refusal("the approval does not authorise exactly one execution")
    for key, want in (required or {}).items():
        if body.get(key) != want:
            raise Refusal(f"approval {key} is {body.get(key)!r}, prepared value is {want!r}")
    if require_image_id:
        approved_image_id(body)          # raises unless it is there and well formed
    return body


def approved_image_id(approval: dict) -> str:
    """The image the APPROVAL names. Never defaulted, never inferred, never observed."""
    value = approval.get("image_id")
    if not isinstance(value, str) or not value.strip():
        raise Refusal(
            "the approval names no image_id: an execution approval must bind to the "
            "exact image it authorises. The identity may not be supplied by the "
            "launcher, the tag, the environment or the run itself.")
    value = value.strip()
    if not IMAGE_ID_RE.fullmatch(value):
        raise Refusal(
            f"approval image_id {value!r} is not a full immutable image ID "
            "(sha256:<64 hex>). A tag can be moved and a short ID is not unique; "
            "neither is an identity.")
    return value


def inspect_image_id(image: str, *, runtime: str = "docker") -> str:
    """The LOCAL image's immutable ID, by METADATA INSPECTION ONLY.

    ``image inspect`` reads metadata and starts NOTHING. It is deliberately separate
    from capture_image_identity(), which runs containers to read the in-image PALACE_*
    files and may only be called once the ID below has been accepted.
    """
    try:
        out = subprocess.run([runtime, "image", "inspect", image, "--format", "{{.Id}}"],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refusal(f"could not inspect {image!r} with {runtime!r}: {exc}") from exc
    if out.returncode != 0:
        detail = (out.stderr or out.stdout or "").strip().splitlines()
        raise Refusal(
            f"{runtime} could not inspect {image!r} (exit {out.returncode}): "
            f"{detail[0] if detail else 'no output'}. The image must already be present; "
            "this launcher never pulls one.")
    measured = (out.stdout or "").strip()
    if not IMAGE_ID_RE.fullmatch(measured):
        raise Refusal(
            f"{runtime} reported {measured!r} for {image!r}, which is not a full image "
            "ID. An unreadable identity is not a matching one.")
    return measured


def require_approved_image(approval: dict, image: str = IMAGE, *,
                           runtime: str = "docker") -> str:
    """Compare the APPROVED image ID with the one actually present, and return the
    immutable ID that everything afterwards must use.

    This is the whole binding. It runs before any container starts, and every way it can
    fail - no approval image_id, a malformed one, an absent image, a failed inspection,
    a mismatch - refuses rather than launching.
    """
    approved = approved_image_id(approval)
    measured = inspect_image_id(image, runtime=runtime)
    if measured != approved:
        raise Refusal(
            f"image mismatch: the approval authorises {approved}, but {image!r} resolves "
            f"to {measured}. Nothing was launched.")
    return approved


def _read_only_git(*args: str) -> str:
    """A read-only git query, for the approval's repository identity. Both subcommands
    report state; neither writes, checks out, resets or cleans anything."""
    if not args or args[0] not in ("rev-parse", "status"):
        raise Refusal(f"{args[0] if args else '(none)'} is not a read-only git command")
    try:
        out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def freeze_approval(record_dir: Path, approval_path: Path) -> dict:
    """Preserve the approval EXACTLY as it stood when it authorised this run.

    This is a COPY OF A HUMAN APPROVAL, not a grant the launcher makes: the file must
    already exist and have been accepted before this is called, and nothing here writes
    to it. The live file can be edited or deleted afterwards, so a record judged against
    whatever it says later is not judged against the approval that authorised it.
    evaluate_record.py reads this snapshot and never the live file.
    """
    raw = Path(approval_path).read_bytes()
    (Path(record_dir) / APPROVAL_SNAPSHOT).write_bytes(raw)
    try:
        source = str(Path(approval_path).resolve().relative_to(REPO))
    except ValueError:
        source = str(Path(approval_path).resolve())
    return {
        "approval_snapshot": APPROVAL_SNAPSHOT,
        "approval_sha256": hashlib.sha256(raw).hexdigest(),
        "approval_source_path": source,
        "approval_source_commit": _read_only_git("rev-parse", "HEAD") or "unavailable",
        "approval_source_tree_dirty": bool(_read_only_git("status", "--porcelain")),
        "approval_snapshot_is": ("a copy of the human approval as it was accepted; the "
                                 "launcher never creates, edits or grants an approval"),
    }


def capture_image_identity(image_id: str, *, runtime: str = "docker") -> dict:
    """Image ID, repo digests, labels and the identity files read from inside the image.

    This STARTS CONTAINERS, so it takes the immutable image ID that
    require_approved_image() returned and refuses anything else. Addressing the tag here
    would let a tag moved after the check decide what actually runs. There is no default:
    it cannot be called without naming what was approved.
    """
    image = str(image_id)
    if not IMAGE_ID_RE.fullmatch(image):
        raise Refusal(
            f"refusing to read identity from {image!r}: this takes the approved immutable "
            "image ID, not a tag")

    def _inspect(fmt: str) -> str:
        out = subprocess.run([runtime, "image", "inspect", image, "--format", fmt],
                             capture_output=True, text=True, timeout=120)
        return out.stdout.strip() if out.returncode == 0 else ""

    files = {}
    for name in IMAGE_IDENTITY_FILES:
        out = subprocess.run(
            [runtime, "run", "--rm", "--network", "none", "--pull=never",
             "--entrypoint", "/bin/sh", image,
             "-c", f"cat /opt/palace/{name}"], capture_output=True, text=True, timeout=300)
        files[name] = out.stdout.strip() if out.returncode == 0 else "unavailable"
    return {
        "image": image,
        "image_id": _inspect("{{.Id}}"),
        "repo_digests": _inspect("{{json .RepoDigests}}"),
        "labels": _inspect("{{json .Config.Labels}}"),
        "identity_files": files,
    }


def input_digests(config: Path, mesh: Path) -> dict:
    return {
        "config_sha256": sha256(config),
        "mesh_sha256": sha256(mesh),
        "patch_sha256": sha256(REPO / "docker" / "patches" / "first-moment-diagnostic.patch"),
        "dockerfile_sha256": sha256(REPO / "docker" / "palace-first-moment.Dockerfile"),
        "code_sha256": {n: sha256(HERE / n) for n in DIAGNOSTIC_CODE},
    }


def _stream_with_caps(command: list[str], *, name: str, runtime: str, order: int,
                      dof_cap: int, wall_cap_s: float) -> dict:
    """Run, streaming stdout, killing the container on either cap. Never retries."""
    dof_re = dof_probe_pattern(order)
    probe = {"dof_cap": dof_cap, "dof_reported": None, "dof_reported_all": [],
             "refused_on_dof": False, "wall_cap_s": wall_cap_s, "timed_out": False}
    lines: list[str] = []
    started = time.perf_counter()

    def kill() -> None:
        subprocess.run([runtime, "kill", name], capture_output=True, text=True,
                       timeout=60, check=False)

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)

    def pump() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            lines.append(raw)
            match = dof_re.search(raw)
            if match:
                reported = int(match.group(1))
                probe["dof_reported_all"].append(reported)
                probe["dof_reported"] = max(probe["dof_reported_all"])
                if reported > dof_cap:
                    probe["refused_on_dof"] = True
                    kill()

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        returncode = proc.wait(timeout=wall_cap_s)
    except subprocess.TimeoutExpired:
        probe["timed_out"] = True
        kill()
        try:
            returncode = proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait(timeout=30)
    reader.join(timeout=60)
    probe["returncode"] = returncode
    probe["wall_s"] = time.perf_counter() - started
    probe["log"] = "".join(lines)
    return probe


def run(record_dir: Path, *, config: Path, mesh: Path, image: str = IMAGE,
        runtime: str = "docker", order: int = 1, np_processes: int = 1,
        dof_cap: int = DOF_HARD_CAP, wall_cap_s: float = WALL_HARD_CAP_S,
        approval: Path = APPROVAL_PATH) -> dict:
    """One execution, under the caps, with provenance. Refuses without an approval."""
    # 1. THE APPROVAL, FIRST. Nothing is inspected and nothing is created until a human
    #    approval exists, matches the prepared digests and names the image it authorises.
    digests = input_digests(config, mesh)
    body = load_approval(approval, required={"config_sha256": digests["config_sha256"],
                                             "mesh_sha256": digests["mesh_sha256"],
                                             "patch_sha256": digests["patch_sha256"]})
    # 2. THE BINDING. Metadata inspection only - no container has started, and none may
    #    until the image actually present is the image the approval named.
    image_id = require_approved_image(body, image, runtime=runtime)
    if not IMAGE_ID_RE.fullmatch(image_id):        # unreachable; the invariant, asserted
        raise Refusal("internal: the accepted image reference is not an immutable ID")
    # 3. Only now may anything be written or launched, and only ever by that ID.
    record_dir = Path(record_dir)
    solver = record_dir / "solver"
    solver.mkdir(parents=True, exist_ok=False)
    shutil.copy2(config, solver / CONFIG_FILENAME)
    shutil.copy2(mesh, solver / Path(mesh).name)
    frozen = freeze_approval(record_dir, approval)
    name = f"qmhp-first-moment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    command = build_command(image_id, workdir=solver, name=name,
                            np_processes=np_processes, runtime=runtime)
    identity = capture_image_identity(image_id, runtime=runtime)
    probe = _stream_with_caps(command, name=name, runtime=runtime, order=order,
                              dof_cap=dof_cap, wall_cap_s=wall_cap_s)
    (solver / "palace_log.txt").write_text(probe.pop("log"))
    provenance = {
        "launcher": "experiments/first-moment-diagnostic/run_diagnostic.py",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "caps": {"dof": dof_cap, "wall_s": wall_cap_s,
                 "meaning": "hard caps on this execution, not runtime promises"},
        "probe": probe,
        "status": ("COMPLETED" if probe["returncode"] == 0 and not probe["timed_out"]
                   and not probe["refused_on_dof"] else "FAILED"),
        "no_retry": "a timeout, a DOF refusal or a nonzero exit is the recorded outcome",
        "image_binding": {
            "approved_image_id": image_id,
            "image_requested": image,
            "compared_before_any_container_started": True,
            "resolved_by": f"{runtime} image inspect --format {{{{.Id}}}} (starts nothing)",
            "launched_as": image_id,
            "pull": "never",
        },
        **frozen,
        **identity,
        **digests,
    }
    (record_dir / "provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    return provenance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record-dir", type=Path)
    ap.add_argument("--config", type=Path, default=HERE / "config.candidate.json")
    ap.add_argument("--mesh", type=Path)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--print-command", action="store_true",
                    help="print the argv a run would execute and exit without running")
    args = ap.parse_args(argv)
    if args.print_command:
        print(json.dumps(build_command(args.image, workdir=Path("<workdir>"),
                                       name="<name>"), indent=1))
        return 0
    try:
        load_approval()
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if not args.record_dir or not args.mesh:
        print("REFUSED: --record-dir and --mesh are required", file=sys.stderr)
        return 2
    prov = run(args.record_dir, config=args.config, mesh=args.mesh, image=args.image)
    print(json.dumps({k: prov[k] for k in ("status", "image_id", "config_sha256")}, indent=1))
    return 0 if prov["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
