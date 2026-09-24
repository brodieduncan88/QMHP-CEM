"""C-2 closure checks on the frozen pre-fix snapshot: (1) the deterministic tests
(prototype_run_against_b0fec36.py) repeated, some repetitions under full CPU load; (2) the same
tests in git worktrees of that snapshot with the repository's new test file, unmutated (M0) and
with three driver mutations M1-M3. Prints one line per run; nothing is written to the repository."""
import os, subprocess, sys, time
from pathlib import Path
REPO = Path(sys.argv[1]); FROZEN = Path(sys.argv[2]); PROTO = Path(sys.argv[3]); NEWTEST = Path(sys.argv[4])
SCRATCH = Path(sys.argv[5]); PLAIN, LOADED = int(sys.argv[6]), int(sys.argv[7])
PY = str(REPO / ".venv/bin/python")
SCRATCH.mkdir(parents=True, exist_ok=False)
ENV = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
       "PYTHONDONTWRITEBYTECODE": "1", "C2_FROZEN": str(FROZEN)}
def pytest(cwd, target, tag, extra=()):
    p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(SCRATCH / tag), *extra, str(target)],
                       cwd=cwd, env=ENV, capture_output=True, text=True, timeout=600)
    return p.stdout.strip().splitlines()[-1]
print(f"frozen HEAD {subprocess.run(['git', '-C', str(FROZEN), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}")
for i in range(PLAIN):
    print(f"plain {i}: {pytest(str(PROTO.parent), PROTO, f'd-plain-{i}')}", flush=True)
busy = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(os.cpu_count() or 1)]
try:
    time.sleep(1)
    for i in range(LOADED):
        print(f"loaded ({len(busy)} busy loops, load {os.getloadavg()[0]:.2f}) {i}: "
              f"{pytest(str(PROTO.parent), PROTO, f'd-load-{i}')}", flush=True)
finally:
    for b in busy:
        b.kill()
MUTANTS = {
    "M0": None,
    "M1 (the handler raises even while stopping)":
        ('    if _SIGNALS["stopping"]:\n        return\n    _SIGNALS["stopping"] = True\n    raise BudgetExceeded',
         '    _SIGNALS["stopping"] = True\n    raise BudgetExceeded'),
    "M2 (failure.json drops the received signals)":
        ('"signals_received": list(_SIGNALS["received"]), "limits": limits,', '"signals_received": [], "limits": limits,'),
    "M3 (stopping is set only after _shutdown)":
        ('        # path (C-2; a plain subscript store runs no signal handler)\n        _SIGNALS["stopping"] = True\n        _shutdown()\n        if refused_exists:',
         '        # path (C-2; a plain subscript store runs no signal handler)\n        _shutdown()\n        _SIGNALS["stopping"] = True\n        if refused_exists:'),
}
sha = subprocess.run(["git", "-C", str(FROZEN), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
for name, mut in MUTANTS.items():
    wt = SCRATCH / ("wt-" + name.split()[0])
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach", "-q", str(wt), sha], check=True)
    try:
        (wt / "tests" / "test_e1_s1_lower_bound.py").write_bytes(NEWTEST.read_bytes())
        if mut:
            p = wt / "experiments/e1-s1-lower-bound/driver.py"; s = p.read_text()
            assert s.count(mut[0]) == 1; p.write_text(s.replace(mut[0], mut[1]))
        line = pytest(str(wt), "tests/test_e1_s1_lower_bound.py", "m-" + name.split()[0],
                      ("-k", "C_level_exception or C2_call_chain or C2_test_fails"))
        print(f"{name}: {line}", flush=True)
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)], check=True)
