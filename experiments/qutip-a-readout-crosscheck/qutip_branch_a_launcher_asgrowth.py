#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Revised macOS launcher for ONE QUTIP-A-READOUT-CROSSCHECK-v1 execution (address-space growth limit).

STATUS: PREPARED FOR HUMAN REVIEW. NOT RUN ON THE TARGET MAC. It supersedes nothing: the
first launcher (sha256 9d70d904...), its BLOCKED-PREFLIGHT record and the Mac memory
diagnostic are left exactly as they are.

WHY IT EXISTS. The first launcher set RLIMIT_AS and RLIMIT_DATA to a fixed 1 GiB. On the
owner's Mac (macOS 26.6.2, arm64) every fresh Python process already has about 415 GiB of
virtual address space, and the kernel rejects both limits with EINVAL, so that launch
stopped at BLOCKED-PREFLIGHT before anything ran. The diagnostic showed that an RLIMIT_AS
of "own size + 1 GiB" is accepted and enforced there.

RESOURCE RULE. This launcher implements RESOURCE_RULE_TEXT below, a NEW PROPOSED rule. It
is an ADDRESS-SPACE GROWTH LIMIT. It is NOT a 1 GiB total-memory limit and must never be
described as one. The frozen rule memory_limit_MB = 1024 is checked to be present and
unchanged in the frozen-rules file, recorded as frozen, and NOT enforced, reinterpreted or
replaced by this launcher. Scientific execution additionally requires a separate human
approval file for this rule (see --resource-rule-approval).

HOW THE LIMIT IS APPLIED. Every supervised child (the dummy probes and, in --execute, the
checker) starts as a small standard-library bootstrap (BOOTSTRAP_SOURCE) in its own
session and process group. The bootstrap, in the process that will run the target:
  a. measures its own baseline VSZ and RSS with `ps`, and again from the kernel directly
     (Mach task_info on macOS, /proc on Linux) as a units and parsing cross-check;
  b. sets RLIMIT_AS soft and hard both to baseline VSZ + 1,073,741,824 bytes;
  c. reads RLIMIT_AS back;
  d. sends that report to the launcher and WAITS. It has not read the target file yet.
The launcher then checks the report itself and measures the waiting child's VSZ and RSS
from outside with `ps`. Only if every check passes does it send GO. After GO the
bootstrap runs the target in the same process with runpy.run_path (sys.argv and
sys.path[0] as for `python target.py`), so the limit applies to the process that runs the
target and to anything that process starts.

MODES
  --qualify   PRE-FLIGHT QUALIFICATION ONLY. Verifies the inputs and runs the dummy probes
              under the exact limit, in a NEW record ~/qmhp-qutip-launcher-control-test-<UTC>.
              It never writes an attempt receipt, never creates or touches the one-attempt
              ledger, and never starts the checker. Exit 0 QUALIFICATION-PASSED,
              2 BLOCKED-PREFLIGHT, 3 REJECTED-INPUTS.
  --execute   The one approved attempt. Refuses unless the confirm token, the execution
              approval reference, a valid resource-rule approval file and the passed
              qualification record it names are all present. Then: inputs, probes, the
              armed checker child's limit report, and only then the receipt, the ledger
              and GO. Exit 0 EXECUTION-COMPLETED (NOT a scientific pass), 2 BLOCKED,
              3 REJECTED-INPUTS, 4 anything after GO.

PREFLIGHT (both modes; any failure is BLOCKED-PREFLIGHT before any receipt, ledger or
checker launch):
  P1 runtime probe:   the bootstrap's baseline and limit are valid; under that exact soft
                      and hard limit, numpy, scipy and qutip import (nothing is calculated)
                      with exactly the approved versions, and RLIMIT_AS read from inside the
                      target equals the intended soft and hard values.
  P2 memory probe:    under that exact limit, a dummy touches 16 MiB blocks of real memory
                      (every page written) up to 1536 MiB. It must be refused with a
                      controlled MemoryError (exit 3, no signal), close to the limit
                      (headroom at refusal between -64 MiB and 16 + 64 MiB), and its
                      resident memory must have grown by at least 80 % of what it touched.
  P3 group-kill probe: under that exact limit, a dummy parent and its grandchild (/bin/sleep)
                      must both be gone after a SIGKILL to the process group at a 1 s cap.
Unknown or unreadable process state counts as failure, never as success.

WHAT THIS DOES NOT ESTABLISH (LIMITATION_TEXT, recorded in every record):
  that physical memory committed later inside virtual-address regions already reserved
  before the limit was applied is bounded by the 1024 MiB growth allowance.

Standard library only. Python 3.9 syntax. Run it with the approved interpreter.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import select
import signal
import subprocess
import sys
import tarfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

PROTOCOL_ID = "QUTIP-A-READOUT-CROSSCHECK-v1"
SOURCE_COMMIT = "110a2e00198e5aab6093ad70b7d06ac8127ae550"
CONFIRM_TOKEN = "RUN-ONE-APPROVED-QUTIP-A-ATTEMPT"
LAUNCHER_ID = "qutip-branch-a-launcher-asgrowth-v1"

# ------------------------------------------------------------------ resource rule (PROPOSED)

RESOURCE_RULE_ID = "QUTIP-A-MACOS-AS-GROWTH-LIMIT-v1"
MEMORY_GROWTH_LIMIT_MIB = 1024
PERMITTED_GROWTH_BYTES = MEMORY_GROWTH_LIMIT_MIB * 1024 * 1024
if PERMITTED_GROWTH_BYTES != 1073741824:  # MiB, not MB
    raise SystemExit("internal error: the growth allowance is not 1,073,741,824 bytes")

RESOURCE_RULE_TEXT = (
    "QUTIP-A-MACOS-AS-GROWTH-LIMIT-v1 (PROPOSED; requires separate human approval before "
    "scientific execution). memory_growth_limit_MiB = 1024. Before any scientific code runs, the "
    "child Python process that will run the QUTIP-A-READOUT-CROSSCHECK-v1 checker measures its own "
    "baseline virtual address-space size (VSZ) and sets RLIMIT_AS, soft and hard both, to "
    "baseline_virtual_address_space_bytes + 1,073,741,824 bytes, and reads both values back. "
    "This is an ADDRESS-SPACE GROWTH LIMIT. It is NOT a 1 GiB total-memory limit and must never be "
    "described as one. It does not reinterpret, replace or enforce the frozen rule "
    "memory_limit_MB = 1024, which remains recorded as frozen."
)
RESOURCE_RULE_SHA256 = hashlib.sha256(RESOURCE_RULE_TEXT.encode("utf-8")).hexdigest()
LIMITATION_TEXT = (
    "NOT ESTABLISHED: this mechanism has NOT established that physical memory committed later inside "
    "virtual-address regions already reserved before the limit was applied is bounded by the 1024 MiB "
    "growth allowance. RLIMIT_AS counts growth of the process's virtual address space; pages first "
    "touched inside regions that were already reserved at the baseline are not counted against it "
    "(on the owner's Mac a fresh Python process already reserved about 415 GiB). It is also not a "
    "limit on resident memory, and a process the checker starts would inherit the same absolute "
    "RLIMIT_AS value rather than a growth allowance of its own."
)
FROZEN_MEMORY_RULE_NOTE = (
    "The frozen rule memory_limit_MB = 1024 is verified present and unchanged in the hash-pinned "
    "frozen-rules file and is recorded here as frozen. It is NOT enforced by this launcher, which "
    "cannot apply a 1024 MB total address-space limit on the target Mac, and it is NOT reinterpreted. "
    "Execution under " + RESOURCE_RULE_ID + " requires that rule's own human approval."
)

MEASUREMENT_TOLERANCE_BYTES = 64 << 20   # ps vs kernel, and baseline vs external measurement
MIN_PLAUSIBLE_VSZ_BYTES = 4 << 20        # a running CPython is never smaller than this
MEMORY_PROBE_CHUNK_BYTES = 16 << 20
MEMORY_PROBE_REQUEST_BYTES = 1536 << 20  # designed to exceed the 1024 MiB growth allowance
RSS_TOUCH_FRACTION = 0.8
ARM_TIMEOUT_S = 30.0
PROBE_WALL_CAP_S = 60.0
GROUP_KILL_PROBE_CAP_S = 1.0
BOOTSTRAP_EXIT_NO_GO = 90
BOOTSTRAP_EXIT_LIMIT_NOT_APPLIED = 91

# ------------------------------------------------------------------ pinned inputs (unchanged from v1)

ARCHIVE_SHA256 = "949ff07b393be684709422abdb9295aecc4379f3642ea6f1bfbe5615434fae6a"
CHECKER_SHA256 = "9f0798c5b307aa455a3bd6482ab5b46c513d448413de9e8aa14ae48d2733e2b1"
SCHEMA_SHA256 = "a65958dbb6c0c1407c5368b66abaf524a85d5a8ddb928e50d68b80504c234cfe"

EXPORT_DIR = "qmhp-qutip-branch-a-export-110a2e0-attempt1"
APPROVAL_DIR = "qmhp-qutip-branch-a-approval-110a2e0"
PRESERVATION_DIR = "qmhp-qutip-branch-a-preservation-110a2e0-attempt1"
SNAPSHOT = EXPORT_DIR + "/branch-a-reference-v1.json"
EXPECTED = PRESERVATION_DIR + "/expected-hashes.json"
FROZEN_RULES = APPROVAL_DIR + "/frozen-rules.json"
EXPORT_APPROVAL = APPROVAL_DIR + "/approval-attempt1.json"
SUMS = PRESERVATION_DIR + "/PRESERVATION-SHA256SUMS"
ARCHIVE_DIRS = (EXPORT_DIR, APPROVAL_DIR, PRESERVATION_DIR)
ARCHIVE_FILES = tuple(sorted([
    SNAPSHOT, EXPORT_DIR + "/manifest.sha256",
    EXPORT_APPROVAL, APPROVAL_DIR + "/approval-attempt1.sha256",
    FROZEN_RULES, APPROVAL_DIR + "/frozen-rules.sha256",
    APPROVAL_DIR + "/postrun-verification.txt", APPROVAL_DIR + "/predeclaration-dependencies.txt",
    APPROVAL_DIR + "/predeclaration.txt", APPROVAL_DIR + "/run-attempt1.ended_utc",
    APPROVAL_DIR + "/run-attempt1.exit_code", APPROVAL_DIR + "/run-attempt1.log",
    APPROVAL_DIR + "/run-attempt1.process_wall_seconds", APPROVAL_DIR + "/run-attempt1.started_utc",
    SUMS, PRESERVATION_DIR + "/README.txt", EXPECTED, PRESERVATION_DIR + "/expected-hashes.sha256",
]))
ARCHIVE_FILE_PINS = {
    SNAPSHOT: "bb09bcbd68a83a2e99a3530cc73e2c5083966322d7eb2fb453fb846fb27222b9",
    EXPECTED: "b667aad5841de92a0c135f8551bc0ecde29f487cb4d354e647af778f195e0a24",
    FROZEN_RULES: "42e1c2a9963b92b7a3d54ff86bdebae479b8aee9a81fbd519821d32b1f3c57d6",
    EXPORT_APPROVAL: "a6559309677532e1e65aae657f3431b2ca36b956fe5b398ab02f8f8ca96cfef6",
}
# The frozen rules must still say exactly this (verified, never edited). memory_limit_MB is
# checked as frozen evidence only; it is not the limit this launcher applies.
FROZEN_EXPECTATIONS = {
    "protocol_id": PROTOCOL_ID,
    "rules_status": "FROZEN-BY-HUMAN-APPROVAL (ENGINEERING-RULE, not MASTER-FROZEN)",
    "wall_time_limit_s": 60,
    "memory_limit_MB": 1024,
    "permitted_attempts": 1,
    "approved_runtime": {"python_version": "3.9.6", "numpy_version": "2.0.2",
                         "scipy_version": "1.13.1", "qutip_version": "5.0.4"},
}

EXECUTE_RECORD_DEFAULT = "~/qmhp-qutip-branch-a-qutip-110a2e0-attempt1-asgrowth"
V1_BLOCKED_RECORD = "~/qmhp-qutip-branch-a-qutip-110a2e0-attempt1"
QUALIFICATION_RECORD_PREFIX = "~/qmhp-qutip-launcher-control-test-"
LEDGER_DIR = "~/.qmhp-qutip-branch-a-launch-ledger"
LEDGER_NAME = "QUTIP-A-READOUT-CROSSCHECK-v1-110a2e0-attempt1.json"

EXIT_COMPLETED, EXIT_BLOCKED, EXIT_REJECTED, EXIT_AFTER_LAUNCH = 0, 2, 3, 4

# ------------------------------------------------------------------ child-side sources

# Runs as `python -c BOOTSTRAP_SOURCE <report_fd> <go_fd> <growth_bytes> <target> [args...]`.
BOOTSTRAP_SOURCE = r'''
import ctypes, json, os, resource, runpy, subprocess, sys, types

REPORT_FD, GO_FD, GROWTH = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
TARGET, TARGET_ARGS = sys.argv[4], sys.argv[5:]


class _RLimit(ctypes.Structure):
    _fields_ = [("cur", ctypes.c_uint64), ("max", ctypes.c_uint64)]


class _MachTaskBasicInfo(ctypes.Structure):
    _fields_ = [("virtual_size", ctypes.c_uint64), ("resident_size", ctypes.c_uint64),
                ("resident_size_max", ctypes.c_uint64), ("user_time", ctypes.c_int32 * 2),
                ("system_time", ctypes.c_int32 * 2), ("policy", ctypes.c_int32),
                ("suspend_count", ctypes.c_int32)]


def _libc():
    if sys.platform == "darwin":
        try:
            return ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        except OSError:
            pass
    return ctypes.CDLL(None, use_errno=True)


_LIBC = _libc()


def native_size():
    """(virtual_bytes, resident_bytes) straight from the kernel; spawns nothing."""
    if sys.platform == "darwin":
        task_info = _LIBC.task_info
        task_info.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        task_info.restype = ctypes.c_int32
        info = _MachTaskBasicInfo()
        count = ctypes.c_uint32(ctypes.sizeof(_MachTaskBasicInfo) // 4)
        task = ctypes.c_uint32.in_dll(_LIBC, "mach_task_self_").value
        kr = task_info(task, 20, ctypes.byref(info), ctypes.byref(count))  # 20 = MACH_TASK_BASIC_INFO
        if kr != 0:
            raise OSError("task_info(MACH_TASK_BASIC_INFO) returned %d" % kr)
        return int(info.virtual_size), int(info.resident_size)
    if sys.platform.startswith("linux"):
        fields = {}
        with open("/proc/self/status") as handle:
            for line in handle:
                key, _, value = line.partition(":")
                fields[key] = value.split()
        return int(fields["VmSize"][0]) * 1024, int(fields["VmRSS"][0]) * 1024
    raise OSError("no kernel size source on %s" % sys.platform)


def ps_size(pid):
    out = subprocess.run(["ps", "-o", "vsz=,rss=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    tokens = out.stdout.split()
    if out.returncode != 0 or len(tokens) != 2 or not all(t.isdigit() for t in tokens):
        raise OSError("unreadable ps output %r (exit %s)" % (out.stdout[:200], out.returncode))
    return int(tokens[0]) * 1024, int(tokens[1]) * 1024


def set_rlimit_as(soft, hard):
    rl = _RLimit(soft, hard)
    if _LIBC.setrlimit(resource.RLIMIT_AS, ctypes.byref(rl)) == 0:
        return {"result": "ACCEPTED", "soft": soft, "hard": hard}
    code = ctypes.get_errno()
    return {"result": "REJECTED", "soft": soft, "hard": hard, "errno": code, "strerror": os.strerror(code)}


report = {"pid": os.getpid(), "growth_bytes": GROWTH, "target": TARGET, "platform": sys.platform}
intended = None
try:
    report["rlimit_as_before"] = list(resource.getrlimit(resource.RLIMIT_AS))
    report["baseline_vsz_bytes"], report["baseline_rss_bytes"] = ps_size(os.getpid())
    report["kernel_vsz_bytes"], report["kernel_rss_bytes"] = native_size()
    intended = report["baseline_vsz_bytes"] + GROWTH
    report["intended_limit_bytes"] = intended
    report["setrlimit"] = set_rlimit_as(intended, intended)
    report["rlimit_as_readback"] = list(resource.getrlimit(resource.RLIMIT_AS))
except BaseException as exc:
    report["error"] = "%s: %s" % (type(exc).__name__, exc)
data = memoryview((json.dumps(report) + "\n").encode("utf-8"))
while data:
    data = data[os.write(REPORT_FD, data):]
os.close(REPORT_FD)

command = b""
while len(command) < 3:
    piece = os.read(GO_FD, 3 - len(command))
    if not piece:
        break
    command += piece
os.close(GO_FD)
if command != b"GO\n":
    os._exit(90)
if ("error" in report or intended is None or report.get("setrlimit", {}).get("result") != "ACCEPTED"
        or list(resource.getrlimit(resource.RLIMIT_AS)) != [intended, intended]):
    os._exit(91)

helper = types.ModuleType("qmhp_as_growth_bootstrap")
helper.native_size = native_size
helper.report = report
sys.modules[helper.__name__] = helper
sys.argv = [TARGET] + TARGET_ARGS
sys.path[0] = os.path.dirname(os.path.abspath(TARGET))
runpy.run_path(TARGET, run_name="__main__")
'''

RUNTIME_PROBE_SOURCE = r'''
import json, resource, sys
helper = sys.modules["qmhp_as_growth_bootstrap"]
out = {"python_version": sys.version.split()[0], "executable": sys.executable}
out["vsz_before_imports_bytes"], out["rss_before_imports_bytes"] = helper.native_size()
for name in ("numpy", "scipy", "qutip"):
    try:
        module = __import__(name)
        out[name + "_version"] = getattr(module, "__version__", None)
        out[name + "_file"] = getattr(module, "__file__", None)
    except BaseException as exc:
        out[name + "_version"] = None
        out[name + "_error"] = repr(exc)[:400]
out["vsz_after_imports_bytes"], out["rss_after_imports_bytes"] = helper.native_size()
out["rlimit_as_inside_target"] = list(resource.getrlimit(resource.RLIMIT_AS))
print("RUNTIME " + json.dumps(out), flush=True)
'''

MEMORY_PROBE_SOURCE = r'''
import json, sys
helper = sys.modules["qmhp_as_growth_bootstrap"]
chunk, request = int(sys.argv[1]), int(sys.argv[2])
vsz0, rss0 = helper.native_size()
held, total, refused = [], 0, False
try:
    while total < request:
        held.append(b"\x01" * chunk)  # bytes repetition writes every byte: every page is touched
        total += chunk
except MemoryError:
    refused = True
vsz1, rss1 = helper.native_size()
report = {"chunk_bytes": chunk, "requested_bytes": request, "allocated_touched_bytes": total,
          "refused": refused, "vsz_before_bytes": vsz0, "rss_before_bytes": rss0,
          "vsz_at_end_bytes": vsz1, "rss_at_end_bytes": rss1}
del held
print("MEMPROBE " + json.dumps(report), flush=True)
sys.exit(3 if refused else 0)
'''

GROUP_KILL_PROBE_SOURCE = r'''
import subprocess, sys, time
child = subprocess.Popen(["/bin/sleep", "60"])  # a small grandchild; the probe tests the kill, not exec size
print("GRANDCHILD", child.pid, flush=True)
time.sleep(60)
'''


class Stop(Exception):
    def __init__(self, status: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.status = status
        self.exit_code = exit_code


# ------------------------------------------------------------------ small utilities (as v1)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _full_sync(fd: int) -> None:
    try:
        import fcntl
        if hasattr(fcntl, "F_FULLFSYNC"):
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            return
    except OSError:
        pass
    os.fsync(fd)


def _sync_dir(path: str) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def durable_write(path: str, data: bytes, mode: int = 0o444) -> None:
    """Create a NEW file (never overwrite), write, fsync, sync the directory."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        _full_sync(fd)
    finally:
        os.close(fd)
    _sync_dir(os.path.dirname(path) or ".")


def write_json(path: str, value: Any) -> None:
    durable_write(path, (json.dumps(value, indent=1, allow_nan=False, sort_keys=False, default=str)
                         + "\n").encode("utf-8"))


def strict_json(data: bytes) -> Any:
    def no_duplicates(pairs):
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate JSON key")
        return dict(pairs)

    def no_constants(token):
        raise ValueError("non-finite JSON constant %s" % token)

    return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates, parse_constant=no_constants)


class Log:
    def __init__(self, path: Optional[str]) -> None:
        self.path = path

    def console(self, message: str) -> None:
        print("%s %s" % (utc_now(), message), flush=True)

    def __call__(self, message: str) -> None:
        line = "%s %s" % (utc_now(), message)
        print(line, flush=True)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                _full_sync(handle.fileno())


def expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def ledger_path() -> str:
    return os.path.join(expand(LEDGER_DIR), LEDGER_NAME)


# ------------------------------------------------------------------ process state (fail closed)


def parse_ps_sizes(text: str) -> Tuple[int, int]:
    """`ps -o vsz=,rss=` output (KiB) -> (vsz_bytes, rss_bytes). Anything else raises."""
    tokens = text.split()
    if len(tokens) != 2 or not all(token.isdigit() for token in tokens):
        raise ValueError("unreadable ps output %r" % text[:200])
    return int(tokens[0]) * 1024, int(tokens[1]) * 1024


def external_ps_sizes(pid: int) -> Dict[str, Any]:
    try:
        out = subprocess.run(["ps", "-o", "vsz=,rss=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=10)
        if out.returncode != 0:
            raise ValueError("ps exit %s: %r" % (out.returncode, out.stderr[:200]))
        vsz, rss = parse_ps_sizes(out.stdout)
        return {"vsz_bytes": vsz, "rss_bytes": rss}
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def _process_table() -> Optional[List[List[str]]]:
    """(pid, pgid, stat) rows, or None if the table cannot be read. Unknown is never 'dead'."""
    try:
        text = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,stat="], capture_output=True, text=True,
                              check=True, timeout=10).stdout
    except Exception:
        return None
    rows = [line.split() for line in text.splitlines()]
    if not rows or any(len(row) < 3 or not row[0].isdigit() or not row[1].isdigit() for row in rows):
        return None
    return rows


def group_alive(pgid: int) -> bool:
    table = _process_table()
    if table is None:
        return True
    return any(row[1] == str(pgid) and not row[2].startswith("Z") for row in table)


def pid_alive(pid: int) -> bool:
    table = _process_table()
    if table is None:
        return True
    return any(row[0] == str(pid) and not row[2].startswith("Z") for row in table)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def verify_armed_report(report: Any, external: Dict[str, Any], pid: Optional[int]) -> List[str]:
    """Independent launcher-side checks of a bootstrap's limit report. Empty list = valid."""
    if not isinstance(report, dict):
        return ["no readable limit report from the bootstrap"]
    problems: List[str] = []
    if "error" in report:
        problems.append("bootstrap error: %s" % report["error"])
    if pid is not None and report.get("pid") != pid:
        problems.append("report pid %r is not the child pid %r" % (report.get("pid"), pid))
    if report.get("growth_bytes") != PERMITTED_GROWTH_BYTES or not _is_int(report.get("growth_bytes")):
        problems.append("growth_bytes %r is not %d (1024 MiB)" % (report.get("growth_bytes"), PERMITTED_GROWTH_BYTES))
    keys = ("baseline_vsz_bytes", "baseline_rss_bytes", "kernel_vsz_bytes", "kernel_rss_bytes",
            "intended_limit_bytes")
    bad = [key for key in keys if not _is_int(report.get(key)) or report.get(key) <= 0]
    if bad:
        problems.append("missing or non-positive %s" % bad)
        return problems
    vsz, rss = report["baseline_vsz_bytes"], report["baseline_rss_bytes"]
    if vsz < MIN_PLAUSIBLE_VSZ_BYTES:
        problems.append("baseline VSZ %d bytes is implausibly small (units error?)" % vsz)
    if rss > vsz:
        problems.append("baseline RSS %d exceeds baseline VSZ %d (RSS/VSZ confusion)" % (rss, vsz))
    if abs(vsz - report["kernel_vsz_bytes"]) > MEASUREMENT_TOLERANCE_BYTES:
        problems.append("ps VSZ %d and kernel VSZ %d disagree by more than %d bytes"
                        % (vsz, report["kernel_vsz_bytes"], MEASUREMENT_TOLERANCE_BYTES))
    if abs(rss - report["kernel_rss_bytes"]) > MEASUREMENT_TOLERANCE_BYTES:
        problems.append("ps RSS %d and kernel RSS %d disagree by more than %d bytes"
                        % (rss, report["kernel_rss_bytes"], MEASUREMENT_TOLERANCE_BYTES))
    intended = vsz + PERMITTED_GROWTH_BYTES
    if report["intended_limit_bytes"] != intended:
        problems.append("intended limit %d is not baseline VSZ + 1,073,741,824 = %d"
                        % (report["intended_limit_bytes"], intended))
    setr = report.get("setrlimit")
    if not isinstance(setr, dict) or setr.get("result") != "ACCEPTED":
        problems.append("setting RLIMIT_AS soft and hard was not accepted: %r" % (setr,))
    elif setr.get("soft") != intended or setr.get("hard") != intended:
        problems.append("RLIMIT_AS was set to soft %r hard %r, not both %d" % (setr.get("soft"), setr.get("hard"), intended))
    if report.get("rlimit_as_readback") != [intended, intended]:
        problems.append("RLIMIT_AS readback %r is not [%d, %d]" % (report.get("rlimit_as_readback"), intended, intended))
    if "error" in external:
        problems.append("launcher could not read the armed child's size: %s" % external["error"])
    else:
        if abs(external["vsz_bytes"] - vsz) > MEASUREMENT_TOLERANCE_BYTES:
            problems.append("launcher-measured VSZ %d disagrees with the reported baseline %d"
                            % (external["vsz_bytes"], vsz))
        if external["rss_bytes"] > external["vsz_bytes"]:
            problems.append("launcher-measured RSS exceeds VSZ (unreadable or confused sizes)")
        if external["vsz_bytes"] > intended:
            problems.append("armed child is already above its limit")
    return problems


# ------------------------------------------------------------------ armed supervision


def _read_until_eof(fd: int, deadline: float) -> Optional[bytes]:
    chunks = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            return None
        piece = os.read(fd, 65536)
        if not piece:
            return b"".join(chunks)
        chunks.append(piece)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_armed(target: str, target_args: List[str], cwd: str, stdout_path: str, stderr_path: str,
              wall_limit_s: float, env: Dict[str, str],
              before_go: Optional[Callable[[Dict[str, Any]], None]] = None,
              outcome: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start the bootstrap for target, verify its limit report, optionally run before_go
    (receipt and ledger), then send GO and supervise with SIGKILL to the whole process group
    at wall_limit_s after GO. Without a valid report the target is never started. It never
    raises for anything the child or before_go does; everything is recorded in outcome."""
    if outcome is None:
        outcome = {}
    outcome.update({"target": target, "target_args": target_args, "arm_timeout_s": ARM_TIMEOUT_S,
                    "wall_limit_s": wall_limit_s, "armed_report": None, "external_measurement": None,
                    "arm_problems": None, "before_go_done": False, "before_go_error": None, "go_error": None,
                    "go_sent": False, "killed_by_launcher": False, "interrupted": False, "spawn_error": None})
    report_r, report_w = os.pipe()
    go_r, go_w = os.pipe()
    argv = [sys.executable, "-c", BOOTSTRAP_SOURCE, str(report_w), str(go_r), str(PERMITTED_GROWTH_BYTES),
            target] + list(target_args)
    with open(stdout_path, "xb") as out, open(stderr_path, "xb") as err:
        outcome["started_utc"] = utc_now()
        start = time.monotonic()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    close_fds=True, pass_fds=(report_w, go_r), start_new_session=True, env=env)
        except (OSError, subprocess.SubprocessError) as exc:
            outcome["spawn_error"] = "%s: %s" % (type(exc).__name__, exc)
            for fd in (report_r, report_w, go_r, go_w):
                os.close(fd)
            outcome["ended_utc"] = utc_now()
            return outcome
        finally:
            if outcome["spawn_error"] is None:
                os.close(report_w)
                os.close(go_r)
        outcome["pid"] = proc.pid
        go_open = True
        try:
            try:
                raw = _read_until_eof(report_r, start + ARM_TIMEOUT_S)
            finally:
                os.close(report_r)
            report = None
            if raw is None:
                problems = ["no limit report within %.0f s" % ARM_TIMEOUT_S]
            else:
                try:
                    report = strict_json(raw.strip())
                    problems = []
                except (ValueError, UnicodeDecodeError) as exc:
                    problems = ["limit report is not strict JSON: %s" % exc]
            external = external_ps_sizes(proc.pid)
            outcome["armed_report"] = report
            outcome["external_measurement"] = external
            problems += verify_armed_report(report, external, proc.pid) if not problems else []
            outcome["arm_problems"] = problems
            if not problems and before_go is not None:
                try:
                    before_go(outcome)
                    outcome["before_go_done"] = True
                except BaseException as exc:  # includes KeyboardInterrupt: no GO in any case
                    outcome["before_go_error"] = "%s: %s" % (type(exc).__name__, exc)
                    problems = ["before-GO step failed: %s" % outcome["before_go_error"]]
            if not problems:
                try:
                    os.write(go_w, b"GO\n")
                except OSError as exc:
                    outcome["go_error"] = "%s: %s" % (type(exc).__name__, exc)
                    problems = ["GO could not be delivered: %s" % outcome["go_error"]]
            if problems:
                os.close(go_w)
                go_open = False
                _kill_group(proc.pid)
                proc.wait()
            else:
                os.close(go_w)
                go_open = False
                outcome["go_sent"] = True
                outcome["go_utc"] = utc_now()
                go_time = time.monotonic()
                try:
                    proc.wait(timeout=wall_limit_s)
                except subprocess.TimeoutExpired:
                    outcome["killed_by_launcher"] = True
                    _kill_group(proc.pid)
                    proc.wait()
                outcome["elapsed_after_go_s"] = time.monotonic() - go_time
        except KeyboardInterrupt:
            outcome["interrupted"] = True
            _kill_group(proc.pid)
            proc.wait()
        finally:
            if go_open:
                try:
                    os.close(go_w)
                except OSError:
                    pass
            if proc.returncode is None:
                _kill_group(proc.pid)
                proc.wait()
            outcome["elapsed_s"] = time.monotonic() - start
            outcome["ended_utc"] = utc_now()
            outcome["returncode"] = proc.returncode
            outcome["signal"] = -proc.returncode if proc.returncode < 0 else None
            _kill_group(proc.pid)
            deadline = time.monotonic() + 3.0
            while group_alive(proc.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            outcome["group_cleared"] = not group_alive(proc.pid)
    return outcome


# ------------------------------------------------------------------ inputs (as v1)


def safe_extract(archive: str, dest: str) -> None:
    os.mkdir(dest)
    seen = set()
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar.getmembers():
            name = member.name
            parts = name.split("/")
            if not name or name.startswith("/") or ".." in parts or any(part == "" for part in parts):
                raise Stop("REJECTED-INPUTS", "unsafe archive member name %r" % name, EXIT_REJECTED)
            if member.isdir():
                if name not in ARCHIVE_DIRS:
                    raise Stop("REJECTED-INPUTS", "unexpected archive directory %r" % name, EXIT_REJECTED)
                continue
            if not member.isfile():
                raise Stop("REJECTED-INPUTS", "archive member %r is not a regular file" % name, EXIT_REJECTED)
            if name not in ARCHIVE_FILES or name in seen:
                raise Stop("REJECTED-INPUTS", "unexpected or repeated archive file %r" % name, EXIT_REJECTED)
            seen.add(name)
            handle = tar.extractfile(member)
            data = handle.read() if handle is not None else b""
            target = os.path.join(dest, *parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            durable_write(target, data)
    missing = sorted(set(ARCHIVE_FILES) - seen)
    if missing:
        raise Stop("REJECTED-INPUTS", "archive lacks %r" % missing, EXIT_REJECTED)


def verify_inputs(archive: str, checker: str, schema: str, inputs: str, log: Log) -> Dict[str, Any]:
    measured: Dict[str, Any] = {}
    if not os.path.isfile(archive):
        raise Stop("REJECTED-INPUTS", "archive not found: %s" % archive, EXIT_REJECTED)
    measured["archive_sha256"] = sha256_file(archive)
    if measured["archive_sha256"] != ARCHIVE_SHA256:
        raise Stop("REJECTED-INPUTS", "archive sha256 %s is not the pinned %s"
                   % (measured["archive_sha256"], ARCHIVE_SHA256), EXIT_REJECTED)
    extracted = os.path.join(inputs, "archive")
    safe_extract(archive, extracted)
    sums_text = open(os.path.join(extracted, SUMS), "rb").read().decode("utf-8")
    listed = {}
    for line in sums_text.splitlines():
        digest, _, rel = line.partition("  ")
        listed[rel] = digest
    if set(listed) != set(ARCHIVE_FILES) - {SUMS}:
        raise Stop("REJECTED-INPUTS", "PRESERVATION-SHA256SUMS does not list exactly the archive files", EXIT_REJECTED)
    for rel, digest in sorted(listed.items()):
        actual = sha256_file(os.path.join(extracted, rel))
        if actual != digest:
            raise Stop("REJECTED-INPUTS", "%s: sha256 %s does not match PRESERVATION-SHA256SUMS" % (rel, actual),
                       EXIT_REJECTED)
    for rel, pin in sorted(ARCHIVE_FILE_PINS.items()):
        actual = sha256_file(os.path.join(extracted, rel))
        if actual != pin:
            raise Stop("REJECTED-INPUTS", "%s: sha256 %s is not the pinned %s" % (rel, actual, pin), EXIT_REJECTED)
        measured[rel] = actual
    log("archive verified: %d files match PRESERVATION-SHA256SUMS and the pins" % len(listed))
    for label, source, pin, name in (("checker", checker, CHECKER_SHA256, "check_branch_a_reference.py"),
                                     ("schema", schema, SCHEMA_SHA256, "branch-a-reference-v1.schema.json")):
        if not os.path.isfile(source):
            raise Stop("REJECTED-INPUTS", "%s not found: %s" % (label, source), EXIT_REJECTED)
        data = open(source, "rb").read()
        if sha256_bytes(data) != pin:
            raise Stop("REJECTED-INPUTS", "%s sha256 %s is not the pinned %s (commit %s)"
                       % (label, sha256_bytes(data), pin, SOURCE_COMMIT), EXIT_REJECTED)
        durable_write(os.path.join(inputs, name), data)
        measured[label + "_sha256"] = pin
    log("checker and schema match the pinned bytes at %s" % SOURCE_COMMIT)
    try:
        rules = strict_json(open(os.path.join(extracted, FROZEN_RULES), "rb").read())
        expected = strict_json(open(os.path.join(extracted, EXPECTED), "rb").read())
    except (ValueError, UnicodeDecodeError) as exc:
        raise Stop("REJECTED-INPUTS", "frozen rules or expected-hashes are not strict JSON: %s" % exc, EXIT_REJECTED)
    for key, value in FROZEN_EXPECTATIONS.items():
        if rules.get(key) != value or type(rules.get(key)) is not type(value):
            raise Stop("REJECTED-INPUTS", "frozen rules %s is %r, launcher requires %r" % (key, rules.get(key), value),
                       EXIT_REJECTED)
    if expected.get("snapshot_sha256") != ARCHIVE_FILE_PINS[SNAPSHOT] or expected.get("schema_sha256") != SCHEMA_SHA256:
        raise Stop("REJECTED-INPUTS", "expected-hashes record does not name the pinned snapshot and schema", EXIT_REJECTED)
    measured["wall_time_limit_s"] = rules["wall_time_limit_s"]
    measured["frozen_memory_limit_MB"] = rules["memory_limit_MB"]
    measured["frozen_memory_limit_status"] = FROZEN_MEMORY_RULE_NOTE
    measured["approved_runtime"] = rules["approved_runtime"]
    log("frozen rules: wall %ss, 1 attempt, runtime %s; memory_limit_MB = %s recorded as frozen, NOT enforced"
        % (rules["wall_time_limit_s"], rules["approved_runtime"], rules["memory_limit_MB"]))
    return measured


# ------------------------------------------------------------------ probes


def _probe_file(preflight: str, name: str, source: str) -> str:
    path = os.path.join(preflight, name + ".py")
    durable_write(path, source.encode("utf-8"), mode=0o444)
    return path


def _stdout_lines(path: str, prefix: str) -> List[str]:
    try:
        text = open(path, "rb").read().decode("utf-8", "replace")
    except OSError:
        return []
    return [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]


def _armed_summary(outcome: Dict[str, Any]) -> Dict[str, Any]:
    report = outcome.get("armed_report") or {}
    external = outcome.get("external_measurement") or {}
    readback = report.get("rlimit_as_readback") if isinstance(report, dict) else None
    return {"baseline_vsz_bytes": report.get("baseline_vsz_bytes"),
            "baseline_rss_bytes": report.get("baseline_rss_bytes"),
            "kernel_vsz_bytes": report.get("kernel_vsz_bytes"), "kernel_rss_bytes": report.get("kernel_rss_bytes"),
            "launcher_measured_vsz_bytes": external.get("vsz_bytes"),
            "launcher_measured_rss_bytes": external.get("rss_bytes"),
            "rlimit_as_soft_bytes": readback[0] if isinstance(readback, list) and len(readback) == 2 else None,
            "rlimit_as_hard_bytes": readback[1] if isinstance(readback, list) and len(readback) == 2 else None,
            "permitted_growth_bytes": report.get("growth_bytes"),
            "intended_limit_bytes": report.get("intended_limit_bytes")}


def _exit_state(outcome: Dict[str, Any]) -> Dict[str, Any]:
    return {key: outcome.get(key) for key in ("spawn_error", "arm_problems", "go_sent", "returncode", "signal",
                                               "killed_by_launcher", "interrupted", "group_cleared",
                                               "elapsed_s", "elapsed_after_go_s")}


def evaluate_runtime_probe(outcome: Dict[str, Any], approved: Dict[str, str]) -> Tuple[List[str], Any]:
    problems: List[str] = []
    lines = _stdout_lines(outcome["stdout_path"], "RUNTIME ")
    report = None
    if lines:
        try:
            report = strict_json(lines[-1].encode("utf-8"))
        except ValueError:
            report = None
    if outcome.get("returncode") != 0 or outcome.get("signal") or outcome.get("killed_by_launcher"):
        problems.append("runtime probe did not exit cleanly (exit %r, signal %r, killed %r)"
                        % (outcome.get("returncode"), outcome.get("signal"), outcome.get("killed_by_launcher")))
    if not isinstance(report, dict):
        problems.append("runtime probe gave no readable report")
        return problems, report
    for key, value in approved.items():
        if report.get(key) != value:
            problems.append("runtime %s is %r under the limit, approved %r (%s)"
                            % (key, report.get(key), value, report.get(key.split("_")[0] + "_error", "")))
    intended = (outcome.get("armed_report") or {}).get("intended_limit_bytes")
    if report.get("rlimit_as_inside_target") != [intended, intended]:
        problems.append("RLIMIT_AS read inside the target is %r, not [%r, %r]"
                        % (report.get("rlimit_as_inside_target"), intended, intended))
    return problems, report


def evaluate_memory_probe(outcome: Dict[str, Any]) -> Tuple[List[str], Any]:
    problems: List[str] = []
    lines = _stdout_lines(outcome["stdout_path"], "MEMPROBE ")
    report = None
    if lines:
        try:
            report = strict_json(lines[-1].encode("utf-8"))
        except ValueError:
            report = None
    rc, sig = outcome.get("returncode"), outcome.get("signal")
    if outcome.get("killed_by_launcher"):
        problems.append("memory probe hit the wall cap and was killed")
    if sig:
        problems.append("memory probe died by signal %s, not by a controlled refusal" % sig)
    elif rc == 0:
        problems.append("the oversized allocation was NOT refused (exit 0)")
    elif rc != 3:
        problems.append("memory probe exit %r is not the controlled-refusal exit 3" % rc)
    if not isinstance(report, dict):
        problems.append("memory probe gave no readable report")
        return problems, report
    ints = ("allocated_touched_bytes", "vsz_before_bytes", "rss_before_bytes", "vsz_at_end_bytes", "rss_at_end_bytes")
    if not all(_is_int(report.get(key)) for key in ints) or report.get("refused") is not True:
        problems.append("memory probe report is incomplete or reports no refusal: %r" % (report,))
        return problems, report
    armed = outcome.get("armed_report") or {}
    intended, baseline = armed.get("intended_limit_bytes"), armed.get("baseline_vsz_bytes")
    if not _is_int(intended) or not _is_int(baseline):
        problems.append("no valid armed limit to compare against")
        return problems, report
    if report.get("requested_bytes") != MEMORY_PROBE_REQUEST_BYTES or report.get("chunk_bytes") != MEMORY_PROBE_CHUNK_BYTES:
        problems.append("memory probe ran with unexpected request/chunk sizes")
    if report["allocated_touched_bytes"] >= MEMORY_PROBE_REQUEST_BYTES:
        problems.append("the probe touched its whole request; nothing was refused")
    headroom = intended - report["vsz_at_end_bytes"]
    report["headroom_at_refusal_bytes"] = headroom
    report["vsz_growth_at_refusal_bytes"] = report["vsz_at_end_bytes"] - baseline
    report["rss_growth_bytes"] = report["rss_at_end_bytes"] - report["rss_before_bytes"]
    if not (-MEASUREMENT_TOLERANCE_BYTES <= headroom <= MEMORY_PROBE_CHUNK_BYTES + MEASUREMENT_TOLERANCE_BYTES):
        problems.append("refusal is not explained by the configured limit: headroom at refusal %d bytes" % headroom)
    if report["rss_growth_bytes"] < RSS_TOUCH_FRACTION * report["allocated_touched_bytes"]:
        problems.append("resident memory grew by %d bytes for %d bytes touched: real pages were not exercised"
                        % (report["rss_growth_bytes"], report["allocated_touched_bytes"]))
    return problems, report


def evaluate_group_kill_probe(outcome: Dict[str, Any]) -> Tuple[List[str], Any]:
    problems: List[str] = []
    grandchild = []
    for rest in _stdout_lines(outcome["stdout_path"], "GRANDCHILD "):
        if rest.strip().isdigit():
            grandchild.append(int(rest.strip()))
    alive = None
    if grandchild:
        deadline = time.monotonic() + 3.0
        while pid_alive(grandchild[0]) and time.monotonic() < deadline:
            time.sleep(0.05)
        alive = pid_alive(grandchild[0])
    details = {"grandchild_pid": grandchild[0] if grandchild else None, "grandchild_alive": alive}
    if not outcome.get("go_sent"):
        problems.append("group-kill probe was never started")
    if not outcome.get("killed_by_launcher"):
        problems.append("group-kill probe was not killed at its cap")
    if not outcome.get("group_cleared"):
        problems.append("process group not confirmed gone (or process table unreadable)")
    if not grandchild:
        problems.append("no grandchild was reported")
    elif alive:
        problems.append("grandchild %d survived the group kill (or its state is unreadable)" % grandchild[0])
    return problems, details


def run_probes(preflight: str, approved: Dict[str, str], env: Dict[str, str], log: Log,
               probes: Dict[str, Any]) -> Dict[str, Any]:
    """All three probes under the exact armed limit, filling probes in place so that every
    result survives. Raises Stop(BLOCKED-PREFLIGHT) on anything other than a clean pass."""
    specs = (
        ("runtime", RUNTIME_PROBE_SOURCE, [], PROBE_WALL_CAP_S, lambda o: evaluate_runtime_probe(o, approved)),
        ("memory", MEMORY_PROBE_SOURCE, [str(MEMORY_PROBE_CHUNK_BYTES), str(MEMORY_PROBE_REQUEST_BYTES)],
         PROBE_WALL_CAP_S, evaluate_memory_probe),
        ("group_kill", GROUP_KILL_PROBE_SOURCE, [], GROUP_KILL_PROBE_CAP_S, evaluate_group_kill_probe),
    )
    for name, source, args, cap, evaluate in specs:
        target = _probe_file(preflight, name + "_probe", source)
        stdout_path = os.path.join(preflight, name + "-probe.stdout")
        outcome = run_armed(target, args, preflight, stdout_path, os.path.join(preflight, name + "-probe.stderr"),
                            cap, env)
        outcome["stdout_path"] = stdout_path
        entry: Dict[str, Any] = {"exit_state": _exit_state(outcome), "limit": _armed_summary(outcome),
                                 "outcome": outcome}
        probes[name] = entry
        if outcome.get("spawn_error"):
            problems = ["could not start: %s" % outcome["spawn_error"]]
        elif outcome.get("arm_problems"):
            problems = ["limit not verified: " + "; ".join(outcome["arm_problems"])]
        elif outcome.get("interrupted"):
            problems = ["interrupted"]
        else:
            problems, details = evaluate(outcome)
            entry["result"] = details
            if name != "group_kill" and not outcome.get("group_cleared"):
                problems.append("probe process group not confirmed gone (or process table unreadable)")
        entry["problems"] = problems
        if problems:
            raise Stop("BLOCKED-PREFLIGHT", "%s probe: %s" % (name, "; ".join(problems)), EXIT_BLOCKED)
        log("%s probe passed under RLIMIT_AS soft = hard = %s bytes (baseline VSZ %s + %d)"
            % (name, entry["limit"]["rlimit_as_soft_bytes"], entry["limit"]["baseline_vsz_bytes"],
               PERMITTED_GROWTH_BYTES))
    return probes


def resource_control_summary(probes: Dict[str, Any]) -> Dict[str, Any]:
    memory = (probes.get("memory") or {}).get("result") or {}
    runtime = (probes.get("runtime") or {}).get("result") or {}
    return {
        "rule_id": RESOURCE_RULE_ID, "rule_text": RESOURCE_RULE_TEXT, "rule_text_sha256": RESOURCE_RULE_SHA256,
        "rule_status": "PROPOSED; requires separate human approval before scientific execution",
        "memory_growth_limit_MiB": MEMORY_GROWTH_LIMIT_MIB, "permitted_growth_bytes": PERMITTED_GROWTH_BYTES,
        "limitation": LIMITATION_TEXT, "frozen_memory_rule": FROZEN_MEMORY_RULE_NOTE,
        "per_probe_limit": {name: entry.get("limit") for name, entry in probes.items()},
        "memory_probe": {key: memory.get(key) for key in (
            "requested_bytes", "chunk_bytes", "allocated_touched_bytes", "refused", "vsz_before_bytes",
            "rss_before_bytes", "vsz_at_end_bytes", "rss_at_end_bytes", "vsz_growth_at_refusal_bytes",
            "rss_growth_bytes", "headroom_at_refusal_bytes")},
        "runtime_versions": {key: runtime.get(key) for key in (
            "python_version", "numpy_version", "scipy_version", "qutip_version", "executable")},
        "probe_exit_states": {name: entry.get("exit_state") for name, entry in probes.items()},
    }


# ------------------------------------------------------------------ records


def verify_sha256sum_manifest(root: str, name: str) -> List[str]:
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        return ["%s missing" % name]
    problems, listed = [], set()
    for line in open(path, "rb").read().decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        listed.add(rel)
        target = os.path.join(root, rel)
        if not os.path.isfile(target):
            problems.append("%s listed but missing" % rel)
        elif sha256_file(target) != digest:
            problems.append("%s changed" % rel)
    for directory, _dirs, files in os.walk(root):
        for filename in files:
            rel = os.path.relpath(os.path.join(directory, filename), root).replace(os.sep, "/")
            if rel != name and rel not in listed:
                problems.append("%s not in %s" % (rel, name))
    return problems


def write_record_manifest(record: str, name: str) -> List[str]:
    rows = []
    for directory, _dirs, files in os.walk(record):
        for filename in files:
            full = os.path.join(directory, filename)
            rel = os.path.relpath(full, record).replace(os.sep, "/")
            if rel != name:
                rows.append((rel, sha256_file(full)))
    body = "".join("%s  %s\n" % (digest, rel) for rel, digest in sorted(rows))
    durable_write(os.path.join(record, name), body.encode("utf-8"))
    return verify_sha256sum_manifest(record, name)


def inventory(root: str) -> List[Dict[str, Any]]:
    rows = []
    if os.path.isdir(root):
        for directory, _dirs, files in os.walk(root):
            for filename in sorted(files):
                full = os.path.join(directory, filename)
                rows.append({"path": os.path.relpath(full, root).replace(os.sep, "/"),
                             "bytes": os.path.getsize(full), "sha256": sha256_file(full)})
    return sorted(rows, key=lambda row: row["path"])


def classify(outcome: Dict[str, Any], checker_output: str, stderr_path: str) -> Dict[str, Any]:
    """Read-only. Nothing in checker_output is modified."""
    info: Dict[str, Any] = {"checker_output_inventory": inventory(checker_output)}
    attempt_exists = os.path.isfile(os.path.join(checker_output, "attempt.json"))
    manifest_problems = verify_sha256sum_manifest(checker_output, "manifest.sha256") if os.path.isdir(
        checker_output) else ["checker output directory missing"]
    result, result_error = None, None
    result_path = os.path.join(checker_output, "result.json")
    if os.path.isfile(result_path):
        try:
            result = strict_json(open(result_path, "rb").read())
        except (ValueError, UnicodeDecodeError) as exc:
            result_error = "result.json is not complete strict JSON: %s" % exc
    else:
        result_error = "result.json missing"
    info.update({"attempt_json_present": attempt_exists, "checker_manifest_problems": manifest_problems,
                 "result_json_error": result_error})
    try:
        info["memory_error_in_stderr"] = b"MemoryError" in open(stderr_path, "rb").read()
    except OSError:
        info["memory_error_in_stderr"] = None
    if isinstance(result, dict):
        info["checker_execution_status"] = result.get("execution_status")
        info["checker_provenance_qualification"] = result.get("provenance_qualification")
        checks = result.get("checks")
        if isinstance(checks, dict):
            verdicts = {name: (value.get("verdict") if isinstance(value, dict) else None)
                        for name, value in checks.items()}
            info["named_check_verdicts_verbatim"] = verdicts
    rc = outcome.get("returncode")
    intact = not manifest_problems and isinstance(result, dict)
    if outcome.get("spawn_error"):
        status = "LAUNCH-FAILED"
    elif outcome.get("interrupted"):
        status = "LAUNCHER-INTERRUPTED"
    elif outcome.get("killed_by_launcher"):
        status = "TIMEOUT-KILLED"
    elif rc == BOOTSTRAP_EXIT_LIMIT_NOT_APPLIED:
        status = "BOOTSTRAP-REFUSED-AFTER-GO"
    elif rc == 0:
        status = ("EXECUTION-COMPLETED" if intact and result.get("execution_status") == "COMPLETED"
                  and isinstance(result.get("checks"), dict) else "INCONSISTENT-RECORD")
    elif rc == 2:
        status = "CHECKER-BLOCKED"
    elif rc == 3:
        status = "CHECKER-REJECTED"
    elif rc == 4:
        status = ("CHECKER-EXECUTION-FAILED" if intact and result.get("execution_status") == "EXECUTION-FAILED"
                  else "CHECKER-DID-NOT-FINALISE")
    else:
        status = "CHECKER-DID-NOT-FINALISE" if attempt_exists else "CHECKER-CRASHED"
    info["status"] = status
    return info


def launcher_identity() -> Dict[str, Any]:
    path = os.path.abspath(__file__)
    return {"launcher_id": LAUNCHER_ID, "launcher_path": path, "launcher_sha256": sha256_file(path),
            "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "machine": platform.machine()}


def finalise(record: str, final_name: str, final: Dict[str, Any], failure: Optional[Dict[str, Any]],
             manifest_name: str, log: Log) -> None:
    try:
        write_json(os.path.join(record, final_name), final)
        if failure is not None:
            write_json(os.path.join(record, "launcher-failure-record.json"), failure)
    finally:
        problems = write_record_manifest(record, manifest_name)
        log.console("record manifest written; verification: %s" % (problems or "intact"))


# ------------------------------------------------------------------ qualification


def qualify(args: argparse.Namespace) -> int:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = expand(QUALIFICATION_RECORD_PREFIX + stamp)
    ledger = ledger_path()
    ledger_before = os.path.lexists(ledger)
    if os.path.lexists(record):
        print("BLOCKED: %s already exists; nothing was created" % record)
        return EXIT_BLOCKED
    os.mkdir(record)
    log = Log(os.path.join(record, "launcher.log"))
    identity = launcher_identity()
    final: Dict[str, Any] = {
        "protocol_id": PROTOCOL_ID, "mode": "PRE-FLIGHT QUALIFICATION ONLY", "launcher": identity,
        "record_kind": "launcher-control-test (NOT QMHP scientific evidence)",
        "checker_launched": False, "attempt_receipt_written": False, "attempt_ledger_touched": False,
        "scientific_verdict": "NONE: qualification runs dummy probes only",
        "resource_rule": {"rule_id": RESOURCE_RULE_ID, "rule_text": RESOURCE_RULE_TEXT,
                          "rule_text_sha256": RESOURCE_RULE_SHA256, "limitation": LIMITATION_TEXT,
                          "frozen_memory_rule": FROZEN_MEMORY_RULE_NOTE},
        "ledger_path": ledger, "ledger_present_before": ledger_before, "started_utc": utc_now(),
    }
    log("QUALIFICATION ONLY: launcher %s (sha256 %s) under %s" % (identity["launcher_path"],
                                                                 identity["launcher_sha256"], identity["executable"]))
    log("proposed rule %s: RLIMIT_AS soft = hard = baseline VSZ + %d bytes (address-space GROWTH limit; "
        "NOT a total-memory limit)" % (RESOURCE_RULE_ID, PERMITTED_GROWTH_BYTES))
    inputs, preflight = os.path.join(record, "inputs"), os.path.join(record, "preflight")
    os.mkdir(inputs)
    os.mkdir(preflight)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probes: Dict[str, Any] = {}
    exit_code = EXIT_COMPLETED
    try:
        measured = verify_inputs(expand(args.archive), expand(args.checker), expand(args.schema), inputs, log)
        final["inputs"] = measured
        run_probes(preflight, measured["approved_runtime"], env, log, probes)
        final["status"] = "QUALIFICATION-PASSED"
    except Stop as stop:
        log("%s: %s" % (stop.status, stop))
        final["status"], final["message"] = stop.status, str(stop)
        exit_code = stop.exit_code
    except KeyboardInterrupt:
        final["status"], final["message"] = "BLOCKED-PREFLIGHT", "interrupted"
        exit_code = EXIT_BLOCKED
    final["probes"] = probes
    final["resource_control"] = resource_control_summary(probes)
    final["ledger_present_after"] = os.path.lexists(ledger)
    if final["ledger_present_after"] != ledger_before:
        final["status"] = "BLOCKED-PREFLIGHT"
        final["message"] = "the attempt ledger changed during qualification"
        exit_code = EXIT_BLOCKED
    final["ended_utc"] = utc_now()
    log("qualification status: %s" % final["status"])
    finalise(record, "qualification-final.json", final, None, "qualification-manifest.sha256", log)
    log.console("record: %s" % record)
    log.console("no attempt receipt, no ledger entry and no checker launch were made")
    return exit_code


# ------------------------------------------------------------------ execution (the one attempt)


def check_rule_approval(path: str, qualification_dir: str) -> Dict[str, Any]:
    """The separate human approval of RESOURCE_RULE_ID, bound to a passed qualification."""
    try:
        approval = strict_json(open(expand(path), "rb").read())
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise Stop("BLOCKED", "resource-rule approval unreadable or not strict JSON: %s" % exc, EXIT_BLOCKED)
    required = {"protocol_id": PROTOCOL_ID, "resource_rule_id": RESOURCE_RULE_ID,
                "resource_rule_text_sha256": RESOURCE_RULE_SHA256,
                "acknowledges_limitation_not_established": True,
                "acknowledges_frozen_memory_limit_MB_not_enforced": True}
    for key, value in required.items():
        if approval.get(key) != value or type(approval.get(key)) is not type(value):
            raise Stop("BLOCKED", "resource-rule approval %s is %r, required %r" % (key, approval.get(key), value),
                       EXIT_BLOCKED)
    reference = approval.get("approval_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise Stop("BLOCKED", "resource-rule approval has no approval_reference", EXIT_BLOCKED)
    qdir = expand(qualification_dir)
    final_path = os.path.join(qdir, "qualification-final.json")
    if verify_sha256sum_manifest(qdir, "qualification-manifest.sha256"):
        raise Stop("BLOCKED", "qualification record %s does not verify against its manifest" % qdir, EXIT_BLOCKED)
    if approval.get("qualification_final_sha256") != sha256_file(final_path):
        raise Stop("BLOCKED", "approval does not name this qualification record's final file", EXIT_BLOCKED)
    qualification = strict_json(open(final_path, "rb").read())
    me = launcher_identity()
    if qualification.get("status") != "QUALIFICATION-PASSED":
        raise Stop("BLOCKED", "qualification status is %r" % qualification.get("status"), EXIT_BLOCKED)
    for key in ("launcher_sha256", "executable"):
        if (qualification.get("launcher") or {}).get(key) != me[key]:
            raise Stop("BLOCKED", "qualification %s differs from this run" % key, EXIT_BLOCKED)
    return {"approval_path": expand(path), "approval_sha256": sha256_file(expand(path)),
            "approval_reference": reference, "qualification_record": qdir,
            "qualification_final_sha256": approval["qualification_final_sha256"]}


def execute(args: argparse.Namespace) -> int:
    record = expand(args.record)
    ledger = ledger_path()
    if args.confirm != CONFIRM_TOKEN:
        print("BLOCKED: --confirm must be exactly %s; nothing was created" % CONFIRM_TOKEN)
        return EXIT_BLOCKED
    if not isinstance(args.execution_approval_reference, str) or not args.execution_approval_reference.strip():
        print("BLOCKED: --execution-approval-reference is empty; nothing was created")
        return EXIT_BLOCKED
    if os.path.lexists(ledger):
        print("BLOCKED: the one attempt is already spent (%s exists); nothing was created" % ledger)
        return EXIT_BLOCKED
    if record == expand(V1_BLOCKED_RECORD) or os.path.lexists(record):
        print("BLOCKED: the record directory %s already exists or is the preserved v1 record; nothing was created"
              % record)
        return EXIT_BLOCKED
    try:
        approval = check_rule_approval(args.resource_rule_approval, args.qualification_record)
    except Stop as stop:
        print("BLOCKED: %s; nothing was created" % stop)
        return EXIT_BLOCKED
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print("BLOCKED: approval or qualification record unreadable (%s); nothing was created" % exc)
        return EXIT_BLOCKED

    os.mkdir(record)
    log = Log(os.path.join(record, "launcher.log"))
    identity = launcher_identity()
    final: Dict[str, Any] = {
        "protocol_id": PROTOCOL_ID, "mode": "EXECUTE", "source_commit": SOURCE_COMMIT, "launcher": identity,
        "execution_approval_reference": args.execution_approval_reference, "resource_rule_approval": approval,
        "resource_rule": {"rule_id": RESOURCE_RULE_ID, "rule_text": RESOURCE_RULE_TEXT,
                          "rule_text_sha256": RESOURCE_RULE_SHA256, "limitation": LIMITATION_TEXT,
                          "frozen_memory_rule": FROZEN_MEMORY_RULE_NOTE},
        "scientific_verdict": "NOT ISSUED BY THE LAUNCHER OR THE CHECKER; named checks are reported verbatim "
                              "and any verdict is a human decision",
        "exit_code_zero_is_not_a_pass": True,
    }
    log("launcher %s (sha256 %s) under %s" % (identity["launcher_path"], identity["launcher_sha256"],
                                              identity["executable"]))
    inputs, preflight = os.path.join(record, "inputs"), os.path.join(record, "preflight")
    os.mkdir(inputs)
    os.mkdir(preflight)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probes: Dict[str, Any] = {}

    def blocked(stop: Stop) -> int:
        log("%s: %s" % (stop.status, stop))
        final.update({"status": stop.status, "message": str(stop), "checker_launched": False,
                      "attempt_receipt_written": False, "attempt_consumed": False, "probes": probes,
                      "resource_control": resource_control_summary(probes), "ended_utc": utc_now()})
        finalise(record, "launcher-final.json", final, {"status": stop.status, "message": str(stop),
                                                        "checker_launched": False},
                 "launcher-manifest.sha256", log)
        return stop.exit_code

    try:
        measured = verify_inputs(expand(args.archive), expand(args.checker), expand(args.schema), inputs, log)
        final["inputs"] = measured
        run_probes(preflight, measured["approved_runtime"], env, log, probes)
    except Stop as stop:
        return blocked(stop)
    except KeyboardInterrupt:
        return blocked(Stop("BLOCKED-PREFLIGHT", "interrupted before launch", EXIT_BLOCKED))
    final["probes"] = probes
    final["resource_control"] = resource_control_summary(probes)

    extracted = os.path.join(inputs, "archive")
    checker_output = os.path.join(record, "checker-output")
    checker_path = os.path.join(inputs, "check_branch_a_reference.py")
    checker_args = [
        "--snapshot", os.path.join(extracted, SNAPSHOT),
        "--schema", os.path.join(inputs, "branch-a-reference-v1.schema.json"),
        "--expected", os.path.join(extracted, EXPECTED),
        "--expected-sha256", ARCHIVE_FILE_PINS[EXPECTED],
        "--execute",
        "--frozen-rules", os.path.join(extracted, FROZEN_RULES),
        "--frozen-rules-sha256", ARCHIVE_FILE_PINS[FROZEN_RULES],
        "--output", checker_output,
    ]
    for path, pin in ((checker_path, CHECKER_SHA256), (checker_args[3], SCHEMA_SHA256),
                      (checker_args[1], ARCHIVE_FILE_PINS[SNAPSHOT]), (checker_args[5], ARCHIVE_FILE_PINS[EXPECTED]),
                      (checker_args[10], ARCHIVE_FILE_PINS[FROZEN_RULES])):
        if sha256_file(path) != pin:
            return blocked(Stop("REJECTED-INPUTS", "%s changed before launch" % path, EXIT_REJECTED))

    receipt_path = os.path.join(record, "attempt-receipt.json")

    def receipt_then_ledger(armed: Dict[str, Any]) -> None:
        receipt = {
            "protocol_id": PROTOCOL_ID, "attempt": 1, "status": "RECEIPT-WRITTEN-BEFORE-CALCULATION",
            "written_utc": utc_now(), "source_commit": SOURCE_COMMIT, "launcher": identity,
            "execution_approval_reference": args.execution_approval_reference,
            "resource_rule_approval": approval, "inputs": measured,
            "limits": {"wall_time_limit_s": measured["wall_time_limit_s"],
                       "wall_enforcement": "launcher-supervised SIGKILL of the child's process group at "
                                           "wall_time_limit_s after GO; not a kernel wall-clock limit",
                       "resource_rule": RESOURCE_RULE_ID, "resource_rule_sha256": RESOURCE_RULE_SHA256,
                       "checker_process_limit": _armed_summary(armed),
                       "limitation": LIMITATION_TEXT, "frozen_memory_rule": FROZEN_MEMORY_RULE_NOTE,
                       "attempts": "one: O_EXCL ledger entry %s written before GO" % ledger},
            "checker_process_armed_report": armed.get("armed_report"),
            "checker_process_external_measurement": armed.get("external_measurement"),
            "probes_summary": final["resource_control"], "target": checker_path, "target_args": checker_args,
            "cwd": inputs, "stdout": "checker.stdout", "stderr": "checker.stderr",
        }
        write_json(receipt_path, receipt)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        durable_write(ledger, (json.dumps({"protocol_id": PROTOCOL_ID, "record": record, "written_utc": utc_now(),
                                           "launcher_sha256": identity["launcher_sha256"],
                                           "receipt_sha256": sha256_file(receipt_path)}, indent=1)
                               + "\n").encode("utf-8"))
        log("receipt written and attempt consumed (%s); sending GO" % ledger)

    outcome: Dict[str, Any] = {}
    try:
        run_armed(checker_path, checker_args, inputs, os.path.join(record, "checker.stdout"),
                  os.path.join(record, "checker.stderr"), float(measured["wall_time_limit_s"]), env,
                  before_go=receipt_then_ledger, outcome=outcome)
    except BaseException as exc:  # the launcher itself failed around the checker
        outcome["launcher_error"] = "%s: %s" % (type(exc).__name__, exc)
    final["checker_run"] = outcome
    receipt_written = os.path.lexists(receipt_path)
    if not outcome.get("go_sent"):
        if not receipt_written and not outcome.get("before_go_done") and not os.path.lexists(ledger):
            problems = (outcome.get("arm_problems") or [outcome.get("spawn_error") or outcome.get("launcher_error")
                                                        or "not armed"])
            return blocked(Stop("BLOCKED-PREFLIGHT", "checker process limit not verified: " + "; ".join(
                str(p) for p in problems), EXIT_BLOCKED))
        consumed = os.path.lexists(ledger)
        final.update({"status": "LAUNCH-FAILED-BEFORE-GO",
                      "message": outcome.get("before_go_error") or outcome.get("go_error")
                      or outcome.get("launcher_error") or "GO was not sent",
                      "checker_launched": False, "attempt_receipt_written": receipt_written,
                      "attempt_consumed": consumed, "ended_utc": utc_now()})
        finalise(record, "launcher-final.json", final, {"status": final["status"], "message": final["message"]},
                 "launcher-manifest.sha256", log)
        return EXIT_AFTER_LAUNCH if consumed else EXIT_BLOCKED
    info = classify(outcome, checker_output, os.path.join(record, "checker.stderr"))
    final.update({"status": info["status"], "checker_launched": True, "attempt_receipt_written": True,
                  "attempt_consumed": True, "classification": info, "ended_utc": utc_now()})
    failure = None
    if info["status"] != "EXECUTION-COMPLETED":
        failure = {"status": info["status"], "run": _exit_state(outcome),
                   "preserved_as_is": [row["path"] for row in info.get("checker_output_inventory", [])],
                   "note": "Partial checker output is preserved byte for byte and never rewritten."}
    log("checker finished: status %s, exit %s" % (info["status"], outcome.get("returncode")))
    finalise(record, "launcher-final.json", final, failure, "launcher-manifest.sha256", log)
    return EXIT_COMPLETED if info["status"] == "EXECUTION-COMPLETED" else EXIT_AFTER_LAUNCH


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--qualify", action="store_true", help="PRE-FLIGHT QUALIFICATION ONLY (dummy probes)")
    mode.add_argument("--execute", action="store_true", help="the one approved attempt")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--checker", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--record", default=EXECUTE_RECORD_DEFAULT, help="--execute only: NEW record directory")
    parser.add_argument("--execution-approval-reference", help="--execute only")
    parser.add_argument("--resource-rule-approval", help="--execute only: approval JSON for " + RESOURCE_RULE_ID)
    parser.add_argument("--qualification-record", help="--execute only: the passed qualification it approves")
    parser.add_argument("--confirm", help="--execute only: must be exactly %s" % CONFIRM_TOKEN)
    args = parser.parse_args(argv)
    if args.qualify:
        extra = [name for name in ("execution_approval_reference", "resource_rule_approval", "qualification_record",
                                   "confirm") if getattr(args, name) is not None]
        if extra or args.record != EXECUTE_RECORD_DEFAULT:
            parser.error("--qualify takes only --archive, --checker and --schema")
        return qualify(args)
    missing = [name for name in ("execution_approval_reference", "resource_rule_approval", "qualification_record",
                                 "confirm") if getattr(args, name) is None]
    if missing:
        print("BLOCKED: --execute needs %s; nothing was created" % ", ".join("--" + m.replace("_", "-") for m in missing))
        return EXIT_BLOCKED
    return execute(args)


if __name__ == "__main__":
    sys.exit(main())
