#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Dummy-only diagnostic: can this Mac enforce the 1024 MiB memory cap the launcher needs?

DIAGNOSTIC ONLY. It uses no QMHP data, reads no QMHP file, never imports or runs the
launcher or the checker, and never touches the launch record or ledger. Every child
process is a dummy. Nothing here is QMHP evidence.

Why: the one approved launch stopped with
  BLOCKED-PREFLIGHT: the memory cap could not be applied (SubprocessError: Exception
  occurred in preexec_fn.)
The launcher sets RLIMIT_AS and then RLIMIT_DATA to soft = hard = 1 GiB in preexec_fn,
and Python discards the reason when preexec_fn fails.

Predeclared questions and measurements (one run; no retries; nothing is tuned afterwards):
  M1  Reproduce: the launcher's exact apply_memory_cap(1 GiB) in preexec_fn of a dummy
      child. Outcome: REPRODUCED (the same SubprocessError) or NOT-REPRODUCED.
  M2  Which call fails, and why: RLIMIT_AS alone, then RLIMIT_DATA alone, each set to
      1 GiB in preexec_fn through the C library, so the raw errno is kept.
      Outcome per limit: ACCEPTED or REJECTED (errno).
  M3  Where macOS draws the line for RLIMIT_AS: in a fresh dummy child, the smallest soft
      limit on a ladder from 1 GiB to 4 TiB that is accepted, next to the child's own
      virtual size as ps reports it.
  M4  Is RLIMIT_AS enforced at all: in a fresh dummy child, soft RLIMIT_AS = own virtual
      size + 1 GiB, then untouched anonymous mappings (address space only, no physical
      memory) in 64 MiB steps up to 2 GiB. ENFORCED if refused before 2 GiB, else
      NOT-ENFORCED; NOT-TESTED if the limit is rejected.
  M5  Is RLIMIT_DATA enforced (only if M2 accepted it): the launcher's own memory probe,
      verbatim (touched 64 MiB blocks up to 1536 MiB), in a dummy child with RLIMIT_DATA =
      1 GiB set in preexec_fn. ENFORCED if refused at or below 1024 MiB, else NOT-ENFORCED.
  M6  Can the approved runtime start under an accepted cap: import numpy, scipy and qutip
      (import only; nothing is calculated) with no cap (control), under (a) RLIMIT_DATA =
      1 GiB in preexec_fn and (b) the M4-style RLIMIT_AS = own size + 1 GiB. Outcome per cap:
      IMPORTED, FAILED-UNDER-CAP (the uncapped control imported), NOT-AVAILABLE (the control
      failed too), or NOT-TESTED if that cap was rejected.

Limits: each dummy child has a 60 s wall cap (120 s for M6) and is killed with its process
group at the cap. Physical memory used is at most about 1.5 GiB (M5 only). The whole run
takes well under 5 minutes. The script gives no verdict on the launcher; which enforcement
mechanism to use next is the owner's decision.

Output: a new folder ~/qmhp-mac-memory-diagnostic-<UTC>/ with diagnostic.json,
console.txt, a copy of this script, and SHA256SUMS.
Usage:  /usr/bin/python3 mac_memory_limit_diagnostic.py
Standard library only. Python 3.9 syntax.
"""

import ctypes
import datetime
import errno
import functools
import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tempfile

GIB = 1 << 30
CAP = 1 << 30  # the frozen rule: memory_limit_MB = 1024
CHILD_CAP_S = 60.0
IMPORT_CAP_S = 120.0
MEMORY_PROBE_ALLOCATE_MB = 1536
AS_LADDER_GIB = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)

# Verbatim from the launcher (qutip_branch_a_launcher.py, sha256 9d70d904...).
def apply_memory_cap(limit_bytes):
    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        which = getattr(resource, name)
        resource.setrlimit(which, (limit_bytes, limit_bytes))


# Verbatim from the launcher: the memory probe it runs under the cap.
MEMORY_PROBE_SOURCE = r"""
import sys
chunk, total, held, target = 64 << 20, 0, [], %d << 20
try:
    while total < target:
        held.append(b"\x01" * chunk)
        total += chunk
        print("ALLOCATED_MB", total >> 20, flush=True)
except MemoryError:
    print("REFUSED_AFTER_MB", total >> 20, flush=True)
    sys.exit(3)
print("NOT_REFUSED_MB", total >> 20, flush=True)
""" % MEMORY_PROBE_ALLOCATE_MB

# Shared by the dummy children: the C-library setrlimit, so the raw errno survives
# (CPython's resource.setrlimit turns EINVAL into a ValueError with a misleading text).
CHILD_PRELUDE = r"""
import ctypes, errno, json, os, resource, subprocess, sys

class _RLimit(ctypes.Structure):
    _fields_ = [("cur", ctypes.c_uint64), ("max", ctypes.c_uint64)]

_libc = ctypes.CDLL(None, use_errno=True)

def c_setrlimit(which, soft, hard):
    rl = _RLimit(soft, hard)
    if _libc.setrlimit(which, ctypes.byref(rl)) == 0:
        return {"result": "ACCEPTED", "soft": soft, "hard": hard}
    code = ctypes.get_errno()
    return {"result": "REJECTED", "soft": soft, "hard": hard, "errno": code,
            "errno_name": errno.errorcode.get(code), "strerror": os.strerror(code)}

def ps_size():
    out = subprocess.run(["ps", "-o", "vsz=,rss=", "-p", str(os.getpid())], capture_output=True,
                         text=True, timeout=10).stdout.split()
    return {"vsz_bytes": int(out[0]) * 1024, "rss_bytes": int(out[1]) * 1024}

def emit(report):
    print("CHILD " + json.dumps(report), flush=True)
"""

REPORT_LIMITS_SOURCE = CHILD_PRELUDE + r"""
emit({"rlimit_as": list(resource.getrlimit(resource.RLIMIT_AS)),
      "rlimit_data": list(resource.getrlimit(resource.RLIMIT_DATA))})
"""

AS_LADDER_SOURCE = CHILD_PRELUDE + r"""
ladder = [int(x) for x in sys.argv[1:]]
soft0, hard0 = resource.getrlimit(resource.RLIMIT_AS)
report = {"size_before": ps_size(), "rlimit_as_before": [soft0, hard0], "tries": []}
for gib in ladder:
    attempt = c_setrlimit(resource.RLIMIT_AS, gib << 30, hard0)
    attempt["gib"] = gib
    report["tries"].append(attempt)
    if attempt["result"] == "ACCEPTED":
        report["smallest_accepted_gib"] = gib
        report["restore"] = c_setrlimit(resource.RLIMIT_AS, soft0, hard0)
        break
emit(report)
"""

AS_ENFORCEMENT_SOURCE = CHILD_PRELUDE + r"""
import mmap
soft0, hard0 = resource.getrlimit(resource.RLIMIT_AS)
size = ps_size()
limit = size["vsz_bytes"] + (1 << 30)
report = {"size_before": size, "rlimit_as_before": [soft0, hard0], "as_soft_limit_bytes": limit}
report["setrlimit"] = c_setrlimit(resource.RLIMIT_AS, limit, hard0)
if report["setrlimit"]["result"] == "ACCEPTED":
    held, total, chunk = [], 0, 64 << 20
    try:
        while total < (2 << 30):
            held.append(mmap.mmap(-1, chunk, flags=mmap.MAP_PRIVATE))
            total += chunk
        report["refused"] = False
    except (OSError, MemoryError, ValueError) as exc:
        report["refused"] = True
        report["refusal"] = "%s: %s" % (type(exc).__name__, exc)
    report["mapped_untouched_bytes"] = total
emit(report)
"""

IMPORT_SOURCE = CHILD_PRELUDE + r"""
mode = sys.argv[1]
report = {"mode": mode}
if mode == "as-relative":
    soft0, hard0 = resource.getrlimit(resource.RLIMIT_AS)
    size = ps_size()
    report["size_before"] = size
    report["setrlimit"] = c_setrlimit(resource.RLIMIT_AS, size["vsz_bytes"] + (1 << 30), hard0)
    if report["setrlimit"]["result"] != "ACCEPTED":
        emit(report)
        sys.exit(0)
report["rlimit_as"] = list(resource.getrlimit(resource.RLIMIT_AS))
report["rlimit_data"] = list(resource.getrlimit(resource.RLIMIT_DATA))
for name in ("numpy", "scipy", "qutip"):
    try:
        module = __import__(name)
        report[name] = getattr(module, "__version__", None)
    except BaseException as exc:
        report[name] = None
        report[name + "_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
emit(report)
"""


class RLimit(ctypes.Structure):
    _fields_ = [("cur", ctypes.c_uint64), ("max", ctypes.c_uint64)]


LIBC = ctypes.CDLL(None, use_errno=True)


def c_preexec(names, limit, report_path):
    """preexec_fn that sets each named limit through the C library and records the raw
    errno in report_path. It never raises, so the dummy child still starts."""

    def preexec():
        results = []
        for name in names:
            rl = RLimit(limit, limit)
            if LIBC.setrlimit(getattr(resource, name), ctypes.byref(rl)) == 0:
                results.append({"limit": name, "result": "ACCEPTED"})
            else:
                code = ctypes.get_errno()
                results.append({"limit": name, "result": "REJECTED", "errno": code,
                                "errno_name": errno.errorcode.get(code), "strerror": os.strerror(code)})
        fd = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, json.dumps(results).encode("utf-8"))
        finally:
            os.close(fd)

    return preexec


def data_cap_preexec(limit):
    def preexec():
        resource.setrlimit(resource.RLIMIT_DATA, (limit, limit))
    return preexec


def run_child(source, args=(), preexec=None, cap_s=CHILD_CAP_S):
    """A dummy child of this same interpreter, in its own process group, killed at cap_s."""
    outcome = {"argv_tail": list(args), "cap_s": cap_s, "killed_at_cap": False, "spawn_error": None}
    workdir = tempfile.mkdtemp(prefix="qmhp-memdiag-")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # as the launcher does; imports write no .pyc files
    try:
        proc = subprocess.Popen([sys.executable, "-c", source] + list(args), cwd=workdir, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, preexec_fn=preexec)
    except (OSError, subprocess.SubprocessError) as exc:
        outcome["spawn_error"] = "%s: %s" % (type(exc).__name__, exc)
        shutil.rmtree(workdir, ignore_errors=True)
        return outcome
    try:
        out, err = proc.communicate(timeout=cap_s)
    except subprocess.TimeoutExpired:
        outcome["killed_at_cap"] = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        out, err = proc.communicate()
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    text = out.decode("utf-8", "replace")
    outcome["returncode"] = proc.returncode
    outcome["stdout_tail"] = text.splitlines()[-5:]
    outcome["stderr_tail"] = err.decode("utf-8", "replace").strip().splitlines()[-5:]
    for line in text.splitlines():
        if line.startswith("CHILD "):
            try:
                outcome["report"] = json.loads(line[len("CHILD "):])
            except ValueError:
                outcome["report"] = None
    return outcome


def parent_size():
    try:
        out = subprocess.run(["ps", "-o", "vsz=,rss=", "-p", str(os.getpid())], capture_output=True,
                             text=True, timeout=10).stdout.split()
        return {"vsz_bytes": int(out[0]) * 1024, "rss_bytes": int(out[1]) * 1024}
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def command_text(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:
        return "unavailable (%s)" % type(exc).__name__


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


class Console:
    def __init__(self):
        self.lines = []

    def __call__(self, message=""):
        print(message, flush=True)
        self.lines.append(message)


say = Console()


def gib(n):
    return "%.2f GiB" % (n / GIB)


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    home = os.path.expanduser("~")
    out_dir = os.path.join(home, "qmhp-mac-memory-diagnostic-" + stamp)
    os.mkdir(out_dir)
    me = os.path.abspath(__file__)
    record = {"diagnostic": "mac-memory-limit-diagnostic", "status": "DIAGNOSTIC ONLY; NOT QMHP EVIDENCE",
              "utc": stamp, "script_sha256": sha256_file(me), "measurements": {}}
    try:
        measure(record, out_dir)
        record["completed"] = True
    except BaseException as exc:
        record["completed"] = False
        record["error"] = "%s: %s" % (type(exc).__name__, exc)
        say("")
        say("DIAGNOSTIC STOPPED EARLY: %s (what was measured is kept)" % record["error"])
    finally:
        write_record(record, out_dir, me)
    say("Record: %s" % out_dir)
    return 0 if record["completed"] else 1


def write_record(record, out_dir, me):
    shutil.copyfile(me, os.path.join(out_dir, os.path.basename(me)))
    with open(os.path.join(out_dir, "diagnostic.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=1, default=str) + "\n")
    with open(os.path.join(out_dir, "console.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(say.lines) + "\n")
    names = sorted(os.listdir(out_dir))
    with open(os.path.join(out_dir, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        for name in names:
            handle.write("%s  %s\n" % (sha256_file(os.path.join(out_dir, name)), name))


def measure(record, out_dir):
    m = record["measurements"]

    say("Mac memory-limit diagnostic (dummy processes only; no QMHP data; nothing is launched)")
    say("script sha256 %s" % record["script_sha256"])
    record["host"] = {"sw_vers": command_text(["sw_vers"]), "uname": command_text(["uname", "-a"]),
                      "machine": platform.machine(), "python": sys.version, "executable": sys.executable,
                      "RLIMIT_AS": resource.RLIMIT_AS, "RLIMIT_DATA": resource.RLIMIT_DATA,
                      "RLIMIT_RSS": getattr(resource, "RLIMIT_RSS", None),
                      "parent_rlimit_as": list(resource.getrlimit(resource.RLIMIT_AS)),
                      "parent_rlimit_data": list(resource.getrlimit(resource.RLIMIT_DATA)),
                      "parent_size": parent_size()}
    say("python %s at %s (%s)" % (sys.version.split()[0], sys.executable, platform.machine()))
    size = record["host"]["parent_size"]
    if "vsz_bytes" in size:
        say("this process: virtual size %s, resident %s" % (gib(size["vsz_bytes"]), gib(size["rss_bytes"])))

    say("")
    say("M1  the launcher's own apply_memory_cap(1 GiB) in preexec_fn of a dummy child")
    o = run_child(REPORT_LIMITS_SOURCE, preexec=functools.partial(apply_memory_cap, CAP))
    m["M1_launcher_equivalent"] = o
    reproduced = bool(o["spawn_error"]) and "preexec_fn" in o["spawn_error"]
    m["M1_outcome"] = "REPRODUCED" if reproduced else "NOT-REPRODUCED"
    say("    %s  %s" % (m["M1_outcome"], o["spawn_error"] or "child started; limits %s" % o.get("report")))

    say("")
    say("M2  which call fails: each limit alone at 1 GiB, set in preexec_fn via the C library")
    m2 = {}
    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        report_path = os.path.join(tempfile.mkdtemp(prefix="qmhp-memdiag-m2-"), "preexec.json")
        o = run_child(REPORT_LIMITS_SOURCE, preexec=c_preexec([name], CAP, report_path))
        try:
            o["preexec_results"] = json.load(open(report_path))
        except (OSError, ValueError) as exc:
            o["preexec_results"] = None
            o["preexec_results_error"] = "%s: %s" % (type(exc).__name__, exc)
        shutil.rmtree(os.path.dirname(report_path), ignore_errors=True)
        m2[name] = o
        result = (o["preexec_results"] or [{}])[0]
        detail = result.get("result", "UNKNOWN")
        if result.get("result") == "REJECTED":
            detail += " (errno %s %s: %s)" % (result.get("errno"), result.get("errno_name"), result.get("strerror"))
        elif result.get("result") == "ACCEPTED":
            detail += "; the dummy child then reported %s" % (o.get("report"),)
        say("    %-11s %s" % (name, detail))
    m["M2_each_limit_alone"] = m2
    data_accepted = ((m2["RLIMIT_DATA"].get("preexec_results") or [{}])[0].get("result") == "ACCEPTED"
                     and isinstance(m2["RLIMIT_DATA"].get("report"), dict))

    say("")
    say("M3  RLIMIT_AS: smallest accepted soft limit on the ladder %s GiB" % (list(AS_LADDER_GIB),))
    o = run_child(AS_LADDER_SOURCE, args=[str(x) for x in AS_LADDER_GIB])
    m["M3_as_ladder"] = o
    rep = o.get("report") or {}
    child_size = (rep.get("size_before") or {}).get("vsz_bytes")
    say("    fresh child's virtual size: %s" % (gib(child_size) if child_size else "unknown"))
    say("    smallest accepted: %s" % ("%s GiB" % rep["smallest_accepted_gib"] if "smallest_accepted_gib" in rep
                                       else "none on the ladder"))
    rejected = [t for t in rep.get("tries", []) if t.get("result") == "REJECTED"]
    if rejected:
        say("    rejections: errno %s" % sorted({"%s %s" % (t.get("errno"), t.get("errno_name")) for t in rejected}))

    say("")
    say("M4  is RLIMIT_AS enforced: soft limit = own size + 1 GiB, then untouched mappings up to 2 GiB")
    o = run_child(AS_ENFORCEMENT_SOURCE)
    m["M4_as_enforcement"] = o
    rep = o.get("report") or {}
    setr = rep.get("setrlimit") or {}
    if setr.get("result") != "ACCEPTED":
        m["M4_outcome"] = "NOT-TESTED"
        say("    NOT-TESTED: the limit was %s %s" % (setr.get("result", "not set"), setr.get("errno_name") or ""))
    elif rep.get("refused"):
        m["M4_outcome"] = "ENFORCED"
        say("    ENFORCED: refused after %s of new mappings (%s)" % (gib(rep["mapped_untouched_bytes"]),
                                                                   rep.get("refusal")))
    elif rep.get("refused") is False:
        m["M4_outcome"] = "NOT-ENFORCED"
        say("    NOT-ENFORCED: %s of new mappings were allowed above a 1 GiB margin" % gib(
            rep["mapped_untouched_bytes"]))
    else:
        m["M4_outcome"] = "UNKNOWN"
        say("    UNKNOWN: no report (exit %s, %s)" % (o.get("returncode"), o.get("stderr_tail")))

    say("")
    say("M5  is RLIMIT_DATA enforced: the launcher's memory probe under RLIMIT_DATA = 1 GiB")
    if not data_accepted:
        m["M5_outcome"] = "NOT-TESTED"
        say("    NOT-TESTED: RLIMIT_DATA = 1 GiB was not accepted in M2")
    else:
        o = run_child(MEMORY_PROBE_SOURCE, preexec=data_cap_preexec(CAP))
        m["M5_data_enforcement"] = o
        lines = o.get("stdout_tail", [])
        refused = [line for line in lines if line.startswith("REFUSED_AFTER_MB")]
        if o.get("returncode") == 3 and refused and int(refused[-1].split()[1]) <= 1024:
            m["M5_outcome"] = "ENFORCED"
        elif any(line.startswith("NOT_REFUSED_MB") for line in lines):
            m["M5_outcome"] = "NOT-ENFORCED"
        else:
            m["M5_outcome"] = "UNKNOWN"
        say("    %s  (exit %s, last output %s)" % (m["M5_outcome"], o.get("returncode"), lines[-1:] or o.get(
            "spawn_error")))

    say("")
    say("M6  can the approved runtime import numpy, scipy, qutip under a cap (import only)")
    control_ok = None
    for key, mode, preexec in (("M6_control_no_cap", "no-cap", None),
                               ("M6a_data_cap", "data-cap", data_cap_preexec(CAP) if data_accepted else None),
                               ("M6b_as_relative", "as-relative", None)):
        if mode == "data-cap" and not data_accepted:
            m[key] = {"outcome": "NOT-TESTED", "reason": "RLIMIT_DATA = 1 GiB was not accepted in M2"}
            say("    %-15s NOT-TESTED (RLIMIT_DATA not accepted)" % mode)
            continue
        o = run_child(IMPORT_SOURCE, args=[mode], preexec=preexec, cap_s=IMPORT_CAP_S)
        rep = o.get("report") or {}
        if mode == "as-relative" and (rep.get("setrlimit") or {}).get("result") not in (None, "ACCEPTED"):
            outcome = "NOT-TESTED"
        elif rep and all(rep.get(n) for n in ("numpy", "scipy", "qutip")):
            outcome = "IMPORTED"
        elif mode == "no-cap":
            outcome = "FAILED"
        else:
            outcome = "FAILED-UNDER-CAP" if control_ok else "NOT-AVAILABLE"
        if mode == "no-cap":
            control_ok = outcome == "IMPORTED"
        o["outcome"] = outcome
        m[key] = o
        versions = " ".join("%s %s" % (n, rep.get(n)) for n in ("numpy", "scipy", "qutip")) if rep else ""
        if outcome == "NOT-TESTED":
            versions = "the limit was %s %s" % ((rep.get("setrlimit") or {}).get("result"),
                                                (rep.get("setrlimit") or {}).get("errno_name") or "")
        errors = "; ".join(rep[n + "_error"] for n in ("numpy", "scipy", "qutip") if rep.get(n + "_error"))
        say("    %-15s %s  %s" % (mode, outcome, versions or o.get("spawn_error") or o.get("stderr_tail")))
        if errors:
            say("                    %s" % errors[:300])

    say("")
    say("Summary (facts only; no verdict on the launcher):")
    say("  M1 launcher-equivalent cap: %s" % m["M1_outcome"])
    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        result = (m2[name].get("preexec_results") or [{}])[0]
        say("  M2 %s = 1 GiB in preexec_fn: %s %s" % (name, result.get("result", "UNKNOWN"),
                                                       result.get("errno_name") or ""))
    say("  M4 RLIMIT_AS enforcement (own size + 1 GiB): %s" % m["M4_outcome"])
    say("  M5 RLIMIT_DATA enforcement (1 GiB): %s" % m["M5_outcome"])
    say("  M6 imports: no-cap %s, data-cap %s, as-relative %s" % (
        m["M6_control_no_cap"].get("outcome"), m["M6a_data_cap"].get("outcome"),
        m["M6b_as_relative"].get("outcome")))
    say("")
    say("Nothing was launched. The QMHP launch record and ledger were not touched.")


if __name__ == "__main__":
    sys.exit(main())
