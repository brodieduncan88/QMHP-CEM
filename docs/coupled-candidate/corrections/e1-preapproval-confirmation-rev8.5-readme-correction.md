# Correction: which numbers in the revision-8.5 pre-approval Confirmation evidence are S1's

Prepared 2026-09-24. This is a correction record under CLAUDE.md §1 and §14. It changes no evidence file, index or manifest. It supersedes one sentence of the evidence index and nothing else.

## 1. The original claim

- **File.** `experiments/e1-s1-lower-bound/preapproval-confirmation-rev8.5/README.md`, line 39.
  - It was committed at `6135a80d56a8f6d5eb2910282d584acdfee9cf86`.
  - Its sha256 is `bee5fc8282f512d9bbfaefcdabb555ae258115b66ab0d3d5c6299885eec442ae`.
  - It is listed in that directory's `MANIFEST.sha256`, whose sha256 is `8761f952eca2ea305659737a27aae16c87a1584135a4e8989383dfcfb50c16b8`.
- **Verbatim.** "The numbers in `summary.json` and `internal-sets.json` are the synthetic stand-in's, not S1 values."

## 2. What is wrong

- **S1's C_hi is in `summary.json`.** Each `summary.json` carries S1's frozen C_hi in `reported_result`. The files are:
  - `nominal/evidence-dir/summary.json`, sha256 `813ff6f178d27916db1d1a023a57f1aef68d60ce27d702a707c8cb88056a22aa`;
  - `forced/evidence-dir/summary.json`, sha256 `1982e3381e75ee50ca5d18992a5f4ee351ecf2965a518d1fedc3ed777f9944f4`.

  In each, S1's value appears twice:
  - `C_hi_fF` = 67.9755386760262;
  - the upper end of `display_fF` (67.975539), which is that value rounded up.

  This is the frozen static study's Dirichlet upper bound for S1. The driver holds it as the constant `CONFIG["C_hi_fF"]`, and `C_hi_basis` names it as that bound. It was copied, not computed on the stand-in.
- **Mechanism.** `finish()` always passes `CONFIG["C_hi_fF"]` to `build_summary()` (`experiments/e1-s1-lower-bound/driver.py` line 912, sha256 `75121e5f199bce4344e2dc84d4c6fc2d966659ae72233807d6439ef1f133d807`). It does this in Confirmation mode too.
- **Effect on the outcome.** In Confirmation mode, `analyse()` is also called with the same S1 value (line 964). It adds the problem "C_lo^static > C_hi" when the stand-in's E1.2 C_lo exceeds that value (lines 839–840).
  - So each stand-in's QUALIFIED outcome includes a comparison of its synthetic C_lo with S1's C_hi.
  - The comparison passed in both runs.
  - It exercises the code path. It is not a physical comparison, because the stand-in has no upper bound of its own.
- **What the sentence gets right.**
  - Every number in `internal-sets.json` is the stand-in's.
  - Every number in `summary.json` except the two named above is the stand-in's.
  - Check that was run: a key-by-key scan of all 22 JSON files in the two `evidence-dir` copies. It looked for any float within 1e-6 (relative) of S1's C_hi or C_br, and for any string containing "67.975" or "56.674".
  - Result: the only matches were `reported_result/C_hi_fF` and `reported_result/display_fF`, in each `summary.json`. C_br appears nowhere, because Q2 is dropped in a Confirmation.

## 3. Corrected statement

"Every number in `internal-sets.json` is the synthetic stand-in's. So is every number in `summary.json`, except `reported_result.C_hi_fF` and the upper end of `reported_result.display_fF`. Those two carry S1's frozen static-study upper bound C_hi = 67.9755386760262 fF, which is copied from the driver's configuration and not computed. The stand-in's outcome includes the check C_lo^static ≤ C_hi against that copied value."

## 4. Related wording, not changed

- **The predeclaration.** `PREDECLARATION.md` line 60 (sha256 `17602835148980c5f1102b5df8270ca69a283d6b77fe5f2c250b93a693840a82`) says: "The stand-in's numbers are synthetic, not S1 values."
  - It was committed at `ca19ece` before the runs.
  - As a statement about the numbers computed on the stand-in, it is correct.
  - It does not mention that `summary.json` also carries the copied C_hi.
  - It is a predeclaration and stays as committed.

## 5. What is preserved

- **Byte-unchanged.** These files are all left exactly as committed at `6135a80`:
  - `README.md`, `MANIFEST.sha256`, `PREDECLARATION.md` and `run.sh`;
  - every file under `nominal/` and `forced/`.

  This record is kept outside that directory, so that `MANIFEST.sha256` still covers every file in it.
- **No computation.** No computation was run for this record.
- **What was read.**
  - The key names of the two `summary.json` files and of the two `internal-sets.json` files.
  - The `reported_result` values of the two `summary.json` files: the synthetic C_lo, the copied C_hi and the two basis texts.
  - The key paths from the scan above.
