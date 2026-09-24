"""C-2 diagnosis on the frozen pre-fix snapshot (read-only): the original wall-clock test's child,
unchanged, plus one observation: the ITIMER_REAL time remaining when the driver's _disarm calls
signal.alarm(0). A proxy of the signal module records it; nothing else in the path changes.
Classes: A = SIGALRM recorded, timer expired before disarm; B = nothing recorded, timer NOT yet
expired at disarm (alarm(0) cancelled it: the test's precondition failed); C = nothing recorded
although the timer had expired (a lost signal: an implementation defect); D = anything else."""
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path
FROZEN = Path(sys.argv[1]); runs = int(sys.argv[2]); fractions = [float(x) for x in sys.argv[3].split(",")]
OUTDIR = Path(sys.argv[4]); OUTDIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(FROZEN / "tests"))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import test_e1_s1_lower_bound as t
EXTRA = """
    import signal, time, zlib, types, atexit
    blob = zlib.compress(bytes(200_000_000), 1)
    bad = blob[:-4] + bytes([(blob[-4] + 1) % 256]) + blob[-3:]
    t = time.perf_counter()
    try:
        zlib.decompress(bad)
    except zlib.error:
        pass
    duration = time.perf_counter() - t
    DIAG = {{"duration": duration, "fraction": {f}, "alarm_calls": []}}
    _real_alarm = signal.alarm
    proxy = types.ModuleType("signal_proxy")
    proxy.__dict__.update({{k: getattr(signal, k) for k in dir(signal) if not k.startswith("__")}})
    def _alarm(s):
        DIAG["alarm_calls"].append({{"arg": s, "itimer_remaining": signal.getitimer(signal.ITIMER_REAL)[0],
                                     "t": time.perf_counter()}})
        return _real_alarm(s)
    proxy.alarm = _alarm
    dr.signal = proxy
    def boom(mesh):
        DIAG["t_set"] = time.perf_counter()
        signal.setitimer(signal.ITIMER_REAL, {f} * duration)
        zlib.decompress(bad)
    dr.geometry_phase = boom
    atexit.register(lambda: open({out!r}, "w").write(json.dumps(DIAG)))
"""
rows = []
for f in fractions:
    for i in range(runs):
        d = Path(tempfile.mkdtemp(prefix=f"c2-{f}-{i}-", dir=OUTDIR))
        out = d / "diag.json"
        code = t._child(d, EXTRA.format(f=f, out=str(out)))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                           env={**os.environ, **t.THREADS}, cwd=str(FROZEN))
        recs = list((d / "results").glob(t.dr.RECORD_PREFIX + "*"))
        fj = json.loads((recs[0] / "failure.json").read_text()) if recs and (recs[0] / "failure.json").is_file() else None
        sig = [e["signal"] for e in fj["signals_received"]] if fj else None
        diag = json.loads(out.read_text()) if out.is_file() else None
        disarm = [c for c in (diag or {}).get("alarm_calls", []) if c["arg"] == 0]
        rem = disarm[-1]["itimer_remaining"] if disarm else None
        el = disarm[-1]["t"] - diag["t_set"] if disarm and diag and "t_set" in diag else None
        mverify = t.dr.manifest.verify(recs[0]) if recs else None
        if sig == ["SIGALRM"] and rem == 0: cls = "A"
        elif sig == [] and rem is not None and rem > 0: cls = "B"
        elif sig == [] and rem == 0: cls = "C"
        else: cls = "D"
        row = {"fraction": f, "run": i, "exit": p.returncode, "signals": sig, "zlib_error": bool(fj and "incorrect data check" in fj["error"]),
               "manifest_ok": mverify == [], "itimer_remaining_at_disarm_s": rem, "timer_s": f * diag["duration"] if diag else None,
               "elapsed_set_to_disarm_s": el, "duration1_s": diag["duration"] if diag else None, "class": cls}
        rows.append(row); print(json.dumps(row), flush=True)
(OUTDIR / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
from collections import Counter
print("SUMMARY", json.dumps({str(f): dict(Counter(r["class"] for r in rows if r["fraction"] == f)) for f in fractions}))
