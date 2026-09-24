"""Does a C-only call chain leave a signal pending (Python handler not yet run) when the
C-level exception reaches Python code, and is the handler run at the next call?"""
import _thread, functools, json, operator, os, signal, sys, zlib, ctypes
bad = (lambda b: b[:-4] + bytes([(b[-4] + 1) % 256]) + b[-3:])(zlib.compress(bytes(100_000), 1))
libc = ctypes.CDLL(None)
DELIVERY = {
    "interrupt_main": lambda s: functools.partial(_thread.interrupt_main, s),
    "os_kill": lambda s: functools.partial(os.kill, os.getpid(), s),
    "libc_raise": lambda s: functools.partial(getattr(libc, "raise"), s),
}
out = {}
for how, mk in DELIVERY.items():
    for sig in (signal.SIGXCPU, signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        got = []
        signal.signal(sig, lambda n, f: got.append(n))
        try:
            list(map(operator.call, [mk(sig), functools.partial(zlib.decompress, bad)]))
            seen = "no exception"
        except zlib.error:
            seen = got[:]          # no call before this: BUILD_SLICE + BINARY_SUBSCR
        after = len(got)           # the handler runs at the end of this CALL
        after2 = got[:]
        signal.signal(sig, signal.SIG_DFL)
        out[f"{how}/{sig.name}"] = {"at_except": seen, "after_next_call": after2}
print(json.dumps(out, indent=0))
