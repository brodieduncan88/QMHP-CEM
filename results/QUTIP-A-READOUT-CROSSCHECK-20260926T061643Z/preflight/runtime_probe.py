
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
