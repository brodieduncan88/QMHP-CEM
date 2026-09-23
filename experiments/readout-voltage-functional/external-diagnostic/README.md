# External readout-field diagnostic: preserved package and review

**Provenance.** `supplied/` is the byte-for-byte content of the package
`QMHP_Readout_Field_Diagnostic.zip` received through the session upload
mechanism on 2026-09-20 (SHA-256 in `supplied-archive.sha256`; the package's
own `manifest.sha256` verifies). It was produced **outside** this repository's
analysis environment, from the two hash-verified N1R/N2R field archives, which
that environment cannot read (organisation network policy; the archives were
not uploaded). Its `evaluation/results.json` is therefore an
**EXTERNALLY PRODUCED** diagnostic: the script `evaluate_readout_fields.py`
was **not** run here, and nothing in this directory claims a local
reproduction of its field integrals.

What was verified locally is recorded in `provenance.json`: the script's
pinned blob SHAs for `functional.json` and both `port-V.csv` files match the
repository at 5bc50d0; its port-voltage reference values equal the committed
CSVs; its surface rectangles, directions, widths and unit scale equal
`functional.json`; and the Palace source explains the interface attribute the
diagnostic integrates over.

`review_external_diagnostic.py` derives the assessment tables (complex
voltages, signed differences, relative differences, `ρ_m`, `r₁₂`, surface
dependence separately from mesh change, and internal consistency checks) from
the supplied JSON by arithmetic only, and writes `review.json`. Every derived
number is labelled DERIVED-FROM-EXTERNAL.

The review itself is in
[`docs/coupled-candidate/readout-surface-difference-review.md`](../../../docs/coupled-candidate/readout-surface-difference-review.md).

The field archives must never be committed (`.gitignore`: `*_fields_*.zip`).
