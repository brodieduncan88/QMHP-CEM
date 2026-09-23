# SYNTHETIC — three-mode identifiability / coordinate-definition check

**Label: SYNTHETIC.** Every number in this directory comes from a known-parameter
three-node linear circuit written down in `inputs.json`. Nothing here is an EM
result, nothing reads a committed Palace record (the script only *lists* the
file names in the N1R/N2R `postpro/` directories, to answer which quantities
those records hold), and nothing here is consumed by `models/`, `orchestrator/`
or any acceptance gate. `models/route_a_inversion.py` is used read-only for the
registered target algebra (`charging_energy_GHz`, `coupling_GHz`) and, on exact
two-node data only, `invert_two_node` as a cross-check. `invert_two_node` and its
guards are unchanged.

The analysis and its conclusion are in
[`docs/coupled-candidate/synthetic-three-mode-identifiability.md`](../../docs/coupled-candidate/synthetic-three-mode-identifiability.md).

| file | content |
|---|---|
| `three_mode_identifiability.py` | the study; `--out DIR` writes the record (refuses any path under `results/`) |
| `inputs.json` | the exact synthetic circuits (node order F, R, X; `S` in GHz²), the declared `L_F`, the RNG seed |
| `results.json` | machine-readable results of every section; every recorded value was scanned and is finite (a non-finite value aborts the write) |
| `report.txt` | the printed report of the same run |
| `environment.json` | Python, platform, numpy, scipy, seed, and the tree (`git_head`) the study was run on |
| `manifest.sha256` | digests of the files above |

Re-run (from the repository root, same environment):

```
uv run python experiments/SYNTHETIC-three-mode-identifiability/three_mode_identifiability.py \
    --out experiments/SYNTHETIC-three-mode-identifiability
```

The run is seeded (`RNG_SEED = 20260919`) and takes about 15 s.
