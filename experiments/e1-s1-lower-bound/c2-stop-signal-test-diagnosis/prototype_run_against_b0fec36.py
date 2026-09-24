"""Prototype of the deterministic C-2 tests, run against the frozen pre-fix snapshot."""
import json, os, subprocess, sys, textwrap
from pathlib import Path
import pytest
FROZEN = Path(os.environ["C2_FROZEN"])
sys.path.insert(0, str(FROZEN / "tests"))
from test_e1_s1_lower_bound import _child, THREADS, REPO, dr, manifest, _strict_json  # noqa: E402

# --- begin block to be copied into tests/test_e1_s1_lower_bound.py ---
#: how the stop signal is delivered inside one C-level call chain (C-2). interrupt_main trips the
#: signal exactly as CPython's C-level signal handler does (trip_signal) for every stop signal; the
#: real SIGALRM comes from a 1 ms ITIMER_REAL armed inside the same chain, ahead of a 200 MB
#: inflate that cannot finish in 1 ms, so it expires while the chain is still in C
_C2_ARM = {"interrupt_main": ("functools.partial(_thread.interrupt_main, signal.{sig})", 100_000),
           "itimer": ("functools.partial(signal.setitimer, signal.ITIMER_REAL, 0.001)", 200_000_000)}
_C2_CASES = [("interrupt_main", s.name) for s in dr.STOP_SIGNALS] + [("itimer", "SIGALRM")]
_C2_CHAIN = """
    import _thread, functools, operator, signal, zlib
    blob = zlib.compress(bytes({size}), 1)
    bad = blob[:-4] + bytes([(blob[-4] + 1) % 256]) + blob[-3:]
    arm = {arm}
    def c_chain():
        # one C-level call: the signal is tripped (or its timer armed), then zlib raises
        # zlib.error from C. No bytecode runs in between, so no Python signal handler can run
        # before the exception reaches Python code.
        list(map(operator.call, [arm, functools.partial(zlib.decompress, bad)]))
"""


def _c2_chain(how: str, sig: str) -> str:
    arm, size = _C2_ARM[how]
    return textwrap.dedent(_C2_CHAIN.format(size=size, arm=arm.format(sig=sig)))


@pytest.mark.parametrize("how, sig", _C2_CASES)
def test_the_C2_call_chain_leaves_the_stop_signal_pending_until_the_next_call(how, sig):
    """The positive control of the mechanism, without the driver: when the C-level exception
    reaches Python code the handler has not run; it runs at the next call."""
    code = _c2_chain(how, sig) + textwrap.dedent(f"""
        import json
        got = []
        signal.signal(signal.{sig}, lambda n, f: got.append(signal.Signals(n).name))
        try:
            c_chain()
            at_except = "no exception"
        except zlib.error:
            at_except = got[:]              # a slice runs no signal handler
        timer_left = signal.getitimer(signal.ITIMER_REAL)[0]
        print(json.dumps({{"at_except": at_except, "after_next_call": got[:], "timer_left": timer_left}}))
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                         env={**os.environ, **THREADS})
    assert out.returncode == 0, out.stderr[-800:]
    assert json.loads(out.stdout) == {"at_except": [], "after_next_call": [sig], "timer_left": 0.0}


@pytest.mark.parametrize("how, sig", _C2_CASES)
def test_a_stop_signal_pending_when_a_C_level_exception_propagates_still_leaves_a_sealed_record(tmp_path, how, sig):
    """C-2: a stop signal delivered during a C call that then raises a C-level exception is
    pending when the failure path starts. It must be recorded, not raised: exit 3, failure.json
    with the C-level error and the signal, provenance.json and a verified manifest. The signal
    is delivered inside one C-level call chain, so no wall-clock race decides where it lands
    (the positive control above shows it is still pending when the exception reaches Python)."""
    code = _child(tmp_path, _c2_chain(how, sig) + "\ndr.geometry_phase = lambda mesh: c_chain()\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS}, cwd=str(REPO))
    assert out.returncode == 3, (out.returncode, out.stderr[-1500:])
    (rec,) = (tmp_path / "results").glob(dr.RECORD_PREFIX + "*")
    f = _strict_json(rec / "failure.json")
    assert "incorrect data check" in f["error"] and [e["signal"] for e in f["signals_received"]] == [sig]
    assert (rec / "provenance.json").is_file() and manifest.verify(rec) == []


def test_the_C2_test_fails_when_the_handler_raises_in_the_failure_path(tmp_path):
    """The negative control: with a handler that raises even once the failure path has begun
    (the defect C-2 guards against), the same chain leaves no failure.json and no manifest."""
    code = _child(tmp_path, _c2_chain("interrupt_main", "SIGALRM") + textwrap.dedent("""
        dr.geometry_phase = lambda mesh: c_chain()
        def raising(signum, frame):
            dr._SIGNALS["received"].append({"signal": signal.Signals(signum).name, "at_s": 0.0})
            raise dr.BudgetExceeded("raised in the failure path")
        dr._on_limit = raising
    """))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS}, cwd=str(REPO))
    assert out.returncode != 3 and "raised in the failure path" in out.stderr, (out.returncode, out.stderr[-1500:])
    (rec,) = (tmp_path / "results").glob(dr.RECORD_PREFIX + "*")
    assert not (rec / "failure.json").exists() and manifest.verify(rec) != []
# --- end block ---
