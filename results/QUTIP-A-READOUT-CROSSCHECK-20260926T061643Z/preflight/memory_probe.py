
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
