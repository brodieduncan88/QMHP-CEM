"""Palace solver adapter (spec §10.3) — the v0.2 execution path.

Palace runs inside the container built from ``docker/palace.Dockerfile``. The
adapter keeps the spec §10.1 boundary exactly::

    prepare(candidate, geometry, run_context) -> PreparedInput
    run(prepared)                             -> PalaceRawOutput
    parse(raw)                                -> SolverResults
    validate_convergence(results)             -> SolverResults   (inherited)

What this milestone solves
--------------------------
The *empty* Object 001 vacuum cavity as a closed PEC box, derived from the
candidate's ENGINEERING-SEED dimensions (:func:`solvers.palace.config.solver_domain`).
The chip dielectric, recess step, launch bores and lid are not modelled yet.
That domain has a closed-form spectrum, so the run can be checked against a
number the solver did not produce. Mesh-refinement convergence campaigns are
deferred (spec §15); the convergence this adapter reports is the eigensolver's
own backward error on the mesh it was given.

What is recorded (spec §10.3)
-----------------------------
solver version and git commit, container image ID and registry digest where
one exists, the exact command line, SHA-256 of every input and output file,
and the convergence figure Palace itself reports. ``run()`` writes
``palace_run.json`` beside the outputs with all of it, because the strict
``SolverResults`` contract has room only for the identity, command line and
artifact hashes. The run record is written on every outcome — success,
non-zero exit, timeout and a runtime that could not be started — so a failed
run leaves the same evidence trail as a successful one.

Spec §10.5 is absolute: if Palace cannot execute, every entry point raises
:class:`SolverUnavailable` naming the remedy. Nothing here falls back to the
mock, and nothing here fabricates a result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.common import Classification, ConvergenceStatus
from contracts.results import (
    SOLVER_RESULTS_SCHEMA,
    Artifact,
    Convergence,
    Eigenmode,
    SolverIdentity,
    SolverResults,
)
from solvers.adapter import (
    PreparedInput,
    RunContext,
    SolverAdapter,
    SolverUnavailable,
    register,
)
from solvers.palace import config as palace_config
from solvers.palace import mesh as palace_mesh
from solvers.palace import outputs as palace_outputs

#: Image built from docker/palace.Dockerfile.
DEFAULT_IMAGE = "qmhp-cem/palace:0.13.0"
#: Files the Dockerfile writes so an image can state what it contains.
IMAGE_VERSION_FILE = "/opt/palace/PALACE_VERSION"
IMAGE_COMMIT_FILE = "/opt/palace/PALACE_COMMIT"
#: Inside the container the work directory is mounted here.
CONTAINER_WORKDIR = "/work"
#: Container-name prefix; the run and candidate IDs are appended so a hung
#: container can be found and killed by name.
CONTAINER_NAME_PREFIX = "qmhp-palace"

CONFIG_FILENAME = "config.json"
MESH_FILENAME = "mesh.msh"
OUTPUT_DIRNAME = "postpro"
#: ``.txt`` so the batch manifest treats the log as decision-relevant.
LOG_FILENAME = "palace_log.txt"
RUN_RECORD_FILENAME = "palace_run.json"
RUN_RECORD_SCHEMA = "qmhp-cem.palace-run/0.2.0"

#: Convergence metric name reported in SolverResults.convergence.
CONVERGENCE_METRIC = "eigenmode_backward_error_max"

_CONTAINER_NAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class PalaceRunFailed(RuntimeError):
    """Palace started but did not complete successfully."""


@dataclass(frozen=True)
class ImageIdentity:
    reference: str
    image_id: str
    repo_digest: str | None
    palace_version: str | None
    palace_commit: str | None
    labels: dict[str, str] = field(default_factory=dict)
    rootless: bool = False

    @property
    def digest_for_record(self) -> str:
        """Registry digest when the image has one, else the content-addressed ID."""
        return self.repo_digest or self.image_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "image_id": self.image_id,
            "repo_digest": self.repo_digest,
            "palace_version": self.palace_version,
            "palace_commit": self.palace_commit,
            "labels": dict(self.labels),
            "rootless_runtime": self.rootless,
        }


@dataclass
class PalaceRawOutput:
    """What :meth:`PalaceSolver.run` hands to :meth:`PalaceSolver.parse`."""

    prepared: PreparedInput
    image: ImageIdentity
    command_line: list[str]
    returncode: int | None
    started_utc: datetime
    ended_utc: datetime
    work_dir: Path
    log_path: Path
    output_dir: Path
    run_record_path: Path
    outcome: str = "completed"

    @property
    def command_string(self) -> str:
        return " ".join(shlex.quote(part) for part in self.command_line)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_text(data: bytes | str | None) -> str:
    """``TimeoutExpired`` carries bytes even for text-mode runs."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "no output"


def _first_digest(text: str) -> str | None:
    """First registry digest from ``{{json .RepoDigests}}`` (a JSON list, or null).

    A comma-separated plain string is accepted too, for a runtime whose
    inspect output was produced with ``join``.
    """
    text = text.strip()
    if not text or text == "null":
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text.split(",")
    if isinstance(parsed, str):
        parsed = parsed.split(",")
    if not isinstance(parsed, list):
        return None
    for item in parsed:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _container_name(run_id: str, candidate_id: str) -> str:
    raw = f"{CONTAINER_NAME_PREFIX}-{run_id}-{candidate_id}"
    return _CONTAINER_NAME_SAFE.sub("-", raw)[:128]


@register
class PalaceSolver(SolverAdapter):
    """Palace finite-element EM solver, run in its container."""

    name = "palace"
    version = "0.2.0-adapter"
    classification = Classification.SOLVED

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        runtime: str = "docker",
        mpi_processes: int = 1,
        timeout_s: int = 3600,
        user: str | None = "auto",
    ) -> None:
        """
        ``user`` controls the container's ``--user`` flag: ``"auto"`` passes
        the invoking uid:gid unless the daemon is rootless (where the caller
        already owns the mounted files), ``None`` omits the flag, any other
        string is passed verbatim.
        """
        if mpi_processes < 1:
            raise ValueError("mpi_processes must be >= 1")
        self.image = image
        self.runtime = runtime
        self.mpi_processes = mpi_processes
        self.timeout_s = timeout_s
        self.user = user
        self._identity: ImageIdentity | None = None

    # --- §10.5: fail clearly, never substitute ------------------------------

    def preflight(self) -> None:
        """Raise :class:`SolverUnavailable` unless Palace can execute here.

        Checks, in order: the mesher, the container runtime binary, the
        runtime daemon, the image, and finally reads the image's own statement
        of which Palace it contains. The identity is cached for :meth:`run`.
        """
        if not palace_mesh.gmsh_available():
            palace_mesh._require_gmsh()  # raises with the remedy

        if shutil.which(self.runtime) is None:
            raise SolverUnavailable(
                self.name,
                f"container runtime {self.runtime!r} is not on PATH",
                f"Install {self.runtime}. The mock solver is a separate, explicit "
                f"choice (--solver mock) and is never substituted.",
            )

        # Docker reports rootless mode in its security options. A runtime that
        # does not understand this format string (podman's `info` is shaped
        # differently) is checked with a plain `info` instead; a rootless
        # daemon is then not detected and `--user` is passed, which is the
        # conservative choice.
        info = self._runtime(["info", "--format", "{{json .SecurityOptions}}"], timeout=60)
        rootless = info.returncode == 0 and "name=rootless" in info.stdout
        if info.returncode != 0:
            info = self._runtime(["info"], timeout=60)
        if info.returncode != 0:
            raise SolverUnavailable(
                self.name,
                f"the {self.runtime} daemon is not reachable "
                f"({_last_line(info.stderr or info.stdout)})",
                f"Start the {self.runtime} daemon, or run QMHP-CEM where one is available.",
            )

        # RepoDigests is emitted as JSON rather than joined: on Docker 28 the
        # `join` template function rejects the empty list a locally built
        # image carries ("expected []string; got []interface {}"), observed
        # on the first real run of this path.
        inspect = self._runtime(
            [
                "image",
                "inspect",
                "--format",
                "{{.Id}}\t{{json .RepoDigests}}\t{{json .Config.Labels}}",
                self.image,
            ],
            timeout=60,
        )
        if inspect.returncode != 0:
            raise SolverUnavailable(
                self.name,
                f"image {self.image!r} is not present",
                f"Build it: docker build -f docker/palace.Dockerfile -t {self.image} .",
            )
        image_id, _, rest = inspect.stdout.strip().partition("\t")
        digests, _, labels_json = rest.partition("\t")
        if not image_id:
            raise SolverUnavailable(
                self.name,
                f"{self.runtime} image inspect returned no image ID for {self.image!r}",
                "Rebuild the image and check `docker image inspect` works by hand.",
            )
        repo_digest = _first_digest(digests)
        try:
            labels = json.loads(labels_json) if labels_json.strip() else {}
        except json.JSONDecodeError:
            labels = {}
        if not isinstance(labels, dict):
            labels = {}

        palace_version, palace_commit = self._image_self_description()
        if palace_version is None:
            palace_version = labels.get("org.qmhp.cem.palace-version") or labels.get(
                "org.qmhp.cem.solver-version"
            )
        if palace_commit is None:
            palace_commit = labels.get("org.qmhp.cem.palace-commit")

        self._identity = ImageIdentity(
            reference=self.image,
            image_id=image_id,
            repo_digest=repo_digest,
            palace_version=palace_version,
            palace_commit=palace_commit,
            labels={k: str(v) for k, v in labels.items()},
            rootless=rootless,
        )

    def _image_self_description(self) -> tuple[str | None, str | None]:
        """Read the version and commit files the Dockerfile writes into the image.

        The probe runs the image once with the Palace entrypoint replaced by
        a shell; a probe that cannot run means the image cannot run Palace
        either, so that is reported as :class:`SolverUnavailable` rather than
        silently ignored.
        """
        script = (
            f"printf 'version=%s\\ncommit=%s\\n' "
            f'"$(cat {IMAGE_VERSION_FILE} 2>/dev/null)" '
            f'"$(cat {IMAGE_COMMIT_FILE} 2>/dev/null)"'
        )
        result = self._runtime(
            ["run", "--rm", "--network", "none", "--entrypoint", "/bin/sh", self.image, "-c", script],
            timeout=120,
        )
        if result.returncode != 0:
            raise SolverUnavailable(
                self.name,
                f"image {self.image!r} is present but a container from it could not "
                f"run ({_last_line(result.stderr or result.stdout)})",
                f"Check `{self.runtime} run --rm --entrypoint /bin/sh {self.image} -c true` by hand.",
            )
        fields: dict[str, str] = {}
        for line in _as_text(result.stdout).splitlines():
            key, sep, value = line.partition("=")
            if sep:
                fields[key.strip()] = value.strip()
        return fields.get("version") or None, fields.get("commit") or None

    def _runtime(self, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        argv = [self.runtime, *args]
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(
                argv, 1, _as_text(exc.stdout), _as_text(exc.stderr) or f"timed out after {timeout}s"
            )
        except OSError as exc:
            return subprocess.CompletedProcess(argv, 1, "", str(exc))
        return subprocess.CompletedProcess(
            argv, completed.returncode, _as_text(completed.stdout), _as_text(completed.stderr)
        )

    def _ensure_identity(self) -> ImageIdentity:
        if self._identity is None:
            self.preflight()
        assert self._identity is not None
        return self._identity

    # --- prepare ------------------------------------------------------------

    def prepare(self, candidate, geometry, run_context: RunContext) -> PreparedInput:  # noqa: ANN001
        """Mesh the solver domain and write the Palace configuration.

        Needs the mesher only; the container is first required by :meth:`run`,
        so an input can be prepared and inspected on a machine without Docker.
        The work directory is resolved to an absolute, symlink-free path once
        here; every later path in the run record is relative to it.
        """
        work_dir = Path(run_context.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        work_dir = work_dir.resolve()

        canonical = json.dumps(
            candidate.to_ordered_dict(), sort_keys=True, separators=(",", ":")
        )
        candidate_sha256 = hashlib.sha256(canonical.encode()).hexdigest()

        domain = palace_config.solver_domain(candidate)
        mesh_record = palace_mesh.generate_box_mesh(domain, work_dir / MESH_FILENAME)

        config = palace_config.build_config(MESH_FILENAME, domain, output_dir=OUTPUT_DIRNAME)
        config_path = work_dir / CONFIG_FILENAME
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
        config_sha256 = _sha256(config_path)

        if geometry is not None and getattr(geometry, "generated", False):
            geometry_note = (
                "PicoGK geometry artifacts exist for this candidate but are not "
                "consumed in this milestone; the solver domain is the empty "
                "vacuum cavity derived from the candidate parameters."
            )
        else:
            geometry_note = (
                "No PicoGK geometry was generated; the solver domain is the empty "
                "vacuum cavity derived from the candidate parameters."
            )

        payload: dict[str, Any] = {
            "adapter_version": self.version,
            "candidate_sha256": candidate_sha256,
            "solver_domain_mm": domain.as_dict(),
            "solver_domain_size_mm": list(domain.size_mm),
            "mesh": mesh_record.as_dict(),
            "config_file": CONFIG_FILENAME,
            "config_sha256": config_sha256,
            "config": config,
            "solver_rules": dict(palace_config.SOLVER_RULES),
            "analytic_reference": palace_config.analytic_reference(domain, count=8),
            "expected_solver_modes_GHz": palace_config.expected_solver_modes_GHz(domain),
            "geometry_note": geometry_note,
            "image": self.image,
            "runtime": self.runtime,
            "mpi_processes": self.mpi_processes,
            "output_dir": OUTPUT_DIRNAME,
        }
        return PreparedInput(
            candidate_id=candidate.candidate_id,
            run_id=run_context.run_id,
            work_dir=work_dir,
            payload=payload,
            input_files=[mesh_record.path, config_path],
        )

    # --- run ----------------------------------------------------------------

    def _user_flag(self, identity: ImageIdentity) -> list[str]:
        if self.user is None:
            return []
        if self.user != "auto":
            return ["--user", self.user]
        if identity.rootless or not hasattr(os, "getuid"):
            return []
        return ["--user", f"{os.getuid()}:{os.getgid()}"]

    def command_for(self, prepared: PreparedInput, identity: ImageIdentity) -> list[str]:
        """The exact argv :meth:`run` executes (exposed so tests can pin it)."""
        work_dir = Path(prepared.work_dir).resolve()
        command = [
            self.runtime,
            "run",
            "--rm",
            "--network",
            "none",
            # Open MPI resolves the local hostname at start-up; with no network
            # the only name guaranteed to resolve inside the container is
            # localhost, so that is what the container is called.
            "--hostname",
            "localhost",
            "--name",
            _container_name(prepared.run_id, prepared.candidate_id),
        ]
        command += self._user_flag(identity)
        command += [
            "-e",
            "HOME=/tmp",
            "-v",
            f"{work_dir}:{CONTAINER_WORKDIR}",
            "-w",
            CONTAINER_WORKDIR,
            self.image,
            "-np",
            str(self.mpi_processes),
            CONFIG_FILENAME,
        ]
        return command

    def run(self, prepared: PreparedInput) -> PalaceRawOutput:
        """Execute Palace in its container on the prepared input.

        Raises :class:`PalaceRunFailed` on a non-zero exit, a timeout or a
        runtime that could not be started. In every one of those cases the
        log (where any output exists) and ``palace_run.json`` are written
        first, so the failure is on the record.
        """
        identity = self._ensure_identity()
        work_dir = Path(prepared.work_dir).resolve()
        for required in prepared.input_files:
            if not Path(required).exists():
                raise PalaceRunFailed(f"prepared input {required} is missing")

        command = self.command_for(prepared, identity)
        container = command[command.index("--name") + 1]
        log_path = work_dir / LOG_FILENAME

        def make_raw(returncode: int | None, started: datetime, ended: datetime, outcome: str) -> PalaceRawOutput:
            return PalaceRawOutput(
                prepared=prepared,
                image=identity,
                command_line=command,
                returncode=returncode,
                started_utc=started,
                ended_utc=ended,
                work_dir=work_dir,
                log_path=log_path,
                output_dir=work_dir / OUTPUT_DIRNAME,
                run_record_path=work_dir / RUN_RECORD_FILENAME,
                outcome=outcome,
            )

        started = _utc()
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            ended = _utc()
            self._kill_container(container)
            log_path.write_text(self._log_text(exc.stdout, exc.stderr))
            self._write_run_record(make_raw(None, started, ended, f"timeout after {self.timeout_s}s"))
            raise PalaceRunFailed(
                f"Palace exceeded the {self.timeout_s}s timeout; the container "
                f"{container} was sent a kill; command: "
                f"{' '.join(shlex.quote(c) for c in command)}; log at {log_path}"
            ) from exc
        except OSError as exc:
            ended = _utc()
            log_path.write_text(f"--- {self.runtime} could not be started ---\n{exc}\n")
            self._write_run_record(make_raw(None, started, ended, f"runtime not started: {exc}"))
            raise PalaceRunFailed(f"could not start {self.runtime}: {exc}") from exc
        ended = _utc()

        log_text = self._log_text(completed.stdout, completed.stderr)
        log_path.write_text(log_text)
        returncode = completed.returncode
        raw = make_raw(
            returncode, started, ended, "completed" if returncode == 0 else f"exit {returncode}"
        )
        self._write_run_record(raw)

        if returncode != 0:
            tail = "\n".join(log_text.strip().splitlines()[-15:])
            raise PalaceRunFailed(
                f"Palace exited with code {returncode}; command: {raw.command_string}; "
                f"log tail:\n{tail}"
            )
        return raw

    @staticmethod
    def _log_text(stdout: bytes | str | None, stderr: bytes | str | None) -> str:
        out, err = _as_text(stdout), _as_text(stderr)
        return out + ("\n--- stderr ---\n" + err if err else "")

    def _kill_container(self, name: str) -> None:
        """Best effort: ``subprocess`` kills the CLI, not the container it started."""
        self._runtime(["kill", name], timeout=30)

    def _write_run_record(self, raw: PalaceRawOutput) -> None:
        """Everything spec §10.3 asks for that SolverResults cannot hold."""
        base = raw.work_dir

        def rel(path: Path) -> str:
            resolved = Path(path).resolve()
            try:
                return resolved.relative_to(base).as_posix()
            except ValueError:  # an input handed in from outside the work directory
                return resolved.as_posix()

        inputs = {rel(p): _sha256(p) for p in raw.prepared.input_files if Path(p).exists()}
        outputs: dict[str, str] = {}
        if raw.output_dir.exists():
            for path in sorted(raw.output_dir.rglob("*")):
                if path.is_file():
                    outputs[path.relative_to(base).as_posix()] = _sha256(path)
        if raw.log_path.exists():
            outputs[raw.log_path.relative_to(base).as_posix()] = _sha256(raw.log_path)
        record = {
            "schema": RUN_RECORD_SCHEMA,
            "candidate_id": raw.prepared.candidate_id,
            "run_id": raw.prepared.run_id,
            "adapter_version": self.version,
            "image": raw.image.as_dict(),
            "command_line": raw.command_line,
            "command_string": raw.command_string,
            "outcome": raw.outcome,
            "returncode": raw.returncode,
            "started_utc": raw.started_utc.isoformat(),
            "ended_utc": raw.ended_utc.isoformat(),
            "wall_time_s": (raw.ended_utc - raw.started_utc).total_seconds(),
            "mpi_processes": self.mpi_processes,
            "work_dir": str(base),
            "input_sha256": inputs,
            "output_sha256": outputs,
            "candidate_sha256": raw.prepared.payload.get("candidate_sha256"),
            "config_sha256": raw.prepared.payload.get("config_sha256"),
            "mesh_sha256": raw.prepared.payload.get("mesh", {}).get("sha256"),
            "solver_rules": raw.prepared.payload.get("solver_rules"),
        }
        raw.run_record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    # --- parse --------------------------------------------------------------

    def parse(self, raw_output: PalaceRawOutput) -> SolverResults:
        """Turn Palace's files into a :class:`SolverResults`.

        Convergence: Palace's own criterion is ``Solver.Eigenmode.Tol`` (the
        eigensolver stops when every requested mode meets it; a mode that
        appears in ``eig.csv`` met it). On top of that the adapter applies the
        ENGINEERING-RULE ``eigenmode_backward_error_max_tolerance`` to the
        a-posteriori backward error Palace writes per mode. Both numbers are
        recorded; neither is invented here.
        """
        raw = raw_output
        payload = raw.prepared.payload
        table = palace_outputs.parse_eig_csv(raw.output_dir / "eig.csv")
        meta = palace_outputs.read_metadata_json(raw.output_dir / "palace.json")
        log = palace_outputs.summarise_log(
            raw.log_path.read_text() if raw.log_path.exists() else ""
        )

        palace_version = (
            raw.image.palace_version
            or palace_outputs.git_tag_from_metadata(meta)
            or log.version
        )
        if not palace_version:
            raise palace_outputs.PalaceOutputError(
                "the Palace version could not be determined from the image, "
                "palace.json or the log; a SOLVED result without a solver version "
                "is not admissible (spec §10.3)"
            )
        commit = raw.image.palace_commit
        version_string = f"{palace_version}" + (f"+{commit[:12]}" if commit else "")

        requested = int(payload["config"]["Solver"]["Eigenmode"]["N"])
        palace_tol = float(payload["config"]["Solver"]["Eigenmode"]["Tol"])
        rules = payload.get("solver_rules") or palace_config.SOLVER_RULES
        tolerance = float(rules["eigenmode_backward_error_max_tolerance"])
        considered = table.rows[:requested]
        finite = all(
            r.frequency_re_GHz > 0 and r.frequency_re_GHz != float("inf") and r.backward_error == r.backward_error
            for r in considered
        )
        value = max((r.backward_error for r in considered), default=float("inf"))
        converged = (
            raw.returncode == 0
            and len(table.rows) >= requested
            and finite
            and value <= tolerance
        )
        convergence = Convergence(
            status=ConvergenceStatus.CONVERGED if converged else ConvergenceStatus.NOT_CONVERGED,
            metric=CONVERGENCE_METRIC,
            value=float(value) if value == value else float("inf"),
            tolerance=tolerance,
        )

        eigenmodes = [
            Eigenmode(
                frequency_GHz=r.frequency_re_GHz,
                quality_factor=(r.quality_factor if r.quality_factor and r.quality_factor > 0 and r.quality_factor != float("inf") else None),
                label=f"palace_mode_{r.index}",
            )
            for r in table.rows
            if r.frequency_re_GHz > 0
        ]

        artifacts = self._artifacts(raw)

        analytic = payload.get("analytic_reference") or []
        notes = [
            "Palace eigenmode solve of the EMPTY Object 001 vacuum cavity as a "
            "closed PEC box. The chip dielectric, recess step, launch bores and "
            "lid are not modelled in this milestone.",
            f"Solver domain (mm, spec §7.3 frame): {payload['solver_domain_mm']}.",
            f"Mesh: {payload['mesh']['tetrahedron_count']} tetrahedra, "
            f"{payload['mesh']['node_count']} nodes, gmsh {payload['mesh']['gmsh_version']}, "
            f"sha256 {payload['mesh']['sha256'][:16]}….",
            f"Convergence: Palace's own stopping criterion was Solver.Eigenmode.Tol = "
            f"{palace_tol:g}; the reported metric is the maximum a-posteriori backward "
            f"error over the {requested} requested mode(s) against the adapter rule "
            f"{tolerance:g}. A mesh-refinement convergence campaign is deferred (spec §15).",
        ]
        if analytic and eigenmodes:
            f_analytic = float(analytic[0]["frequency_GHz"])
            f_solved = eigenmodes[0].frequency_GHz
            deviation = (f_solved - f_analytic) / f_analytic
            notes.append(
                f"Analytic check: lowest mode {f_solved:.6f} GHz vs closed-form "
                f"{analytic[0]['label']} {f_analytic:.6f} GHz, relative deviation "
                f"{deviation:+.3e}. All requested modes are TM_mn0, so this checks "
                f"the X/Y extent and unit scaling, not the cavity height."
            )
        if log.git_changeset:
            notes.append(f"Palace banner git changeset: {log.git_changeset}.")
        if log.mpi_processes is not None:
            notes.append(f"Palace ran with {log.mpi_processes} MPI process(es).")
        if meta:
            tag = palace_outputs.git_tag_from_metadata(meta)
            if tag:
                notes.append(f"palace.json GitTag: {tag}.")
        if log.error_lines:
            notes.append(f"Palace log diagnostics: {log.error_lines[:3]}.")

        return SolverResults.model_validate(
            {
                "schema": SOLVER_RESULTS_SCHEMA,
                "candidate_id": raw.prepared.candidate_id,
                "solver": SolverIdentity(
                    name=self.name,
                    version=version_string,
                    classification=self.classification,
                    image_digest=raw.image.digest_for_record,
                    command_line=raw.command_string,
                ).model_dump(),
                "run_id": raw.prepared.run_id,
                "convergence": convergence.model_dump(),
                "frequency_GHz": [],
                "s_parameters": {},
                "z_parameters": {},
                "eigenmodes": [m.model_dump() for m in eigenmodes],
                "artifacts": [a.model_dump() for a in artifacts],
                "synthetic": False,
                "notes": notes,
            }
        )

    def _artifacts(self, raw: PalaceRawOutput) -> list[Artifact]:
        work = raw.work_dir
        roles = {
            CONFIG_FILENAME: "palace_config",
            MESH_FILENAME: "mesh",
            LOG_FILENAME: "palace_log",
            RUN_RECORD_FILENAME: "palace_run_record",
            f"{OUTPUT_DIRNAME}/eig.csv": "eigenmodes_csv",
            f"{OUTPUT_DIRNAME}/domain-E.csv": "domain_energy_csv",
            f"{OUTPUT_DIRNAME}/palace.json": "palace_metadata",
        }
        artifacts: list[Artifact] = []
        candidates = [work / CONFIG_FILENAME, work / MESH_FILENAME, raw.log_path, raw.run_record_path]
        if raw.output_dir.exists():
            candidates += sorted(p for p in raw.output_dir.rglob("*") if p.is_file())
        for path in candidates:
            if not path.exists():
                continue
            rel = path.relative_to(work).as_posix()
            artifacts.append(Artifact(path=rel, sha256=_sha256(path), role=roles.get(rel, "palace_output")))
        return artifacts

    # --- provenance ---------------------------------------------------------

    def provenance(self) -> dict[str, Any]:
        """Solver identity fields for the batch manifest (spec §10.3, §13.3)."""
        base: dict[str, Any] = {
            "solver": self.name,
            "adapter_version": self.version,
            "image": self.image,
            "runtime": self.runtime,
            "mpi_processes": self.mpi_processes,
        }
        if self._identity is not None:
            base.update(self._identity.as_dict())
        return base
