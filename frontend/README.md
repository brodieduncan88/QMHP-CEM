# QMHP-CEM read-only evidence viewer

A local website that **displays, searches, filters and explains** what this
repository already records. It cannot change any of it.

```bash
python3 -m frontend                 # serves this checkout on http://127.0.0.1:8765/
python3 -m frontend --repo /path/to/another/checkout --port 9000
uv run python -m frontend           # the same, inside the locked environment
```

It needs the Python standard library only. PyYAML, already a locked project
dependency, is used when present to parse `master/validation_gates.yaml`.
There is no build step, no npm, no external font or script, and no outbound
network access. It binds to the loopback interface unless `--host` says otherwise.

> A computational PASS is not hardware validation. Every page carries that
> boundary, and every record page states whether the record is SYNTHETIC,
> SOLVED, ANALYSIS, DECLARATION, MEASURED or UNCLASSIFIED, and which rule
> assigned the label.

## Design

An editorial layout: a compact hero on the overview with a "Now" strip of the
latest verdicts directly beneath it, numbered section eyebrows, display type,
spec-table rows, alternating light and dark bands, a hardware-boundary ticker with
a pause control, scroll reveals, count-up figures, magnetic buttons and
cross-fading page transitions (View Transitions API where available). It follows
the system colour scheme; every text colour meets WCAG AA contrast on the surface
it sits on, including the dark bands in light mode. All motion stops under
`prefers-reduced-motion`, and the ticker starts paused.

**Artwork is original and drawn from the data.** There are no photographs. The
figures are SVG built in the browser from this checkout's own records, and each
caption says which data drew it:

| Figure | Where | Drawn from |
|---|---|---|
| Evidence lattice | Records (and the overview hero where 3-D is unavailable) | one row per record family, x = recorded time, shape = evidence basis, colour = most severe headline status, gold curves = records naming records; each mark opens its record |
| Stage stack (SVG) | Gates, Experiments (and the overview where 3-D is unavailable) | one plate per gate (or contract group / experiment); hatched = hardware-gated, PASS not permitted |
| Digest sigil | Provenance | a master file's SHA-256, re-measured on load: one tick per hex digit |
| Result matrix | Candidates | candidate x gate, coloured by the recorded status; each mark shows its reason |

**The live 3-D stage stack** (`static/scene3d.js`) is an original real-time
three.js model on the overview: one plate per frozen gate (gold = computational,
dark with a pulsing violet rim = hardware-gated, PASS not permitted), one bead per
record, placed by recorded time and coloured by its headline status. Hover a bead
for its record, click to open it. Scrolling separates and turns the stack (hero).

The wiring and the sample stage are drawn in detail but are illustrative: semi-rigid
coax lines (one per record family carries its beads; the rest are unlabelled) with
bulkhead connectors and nuts at every plate, attenuators, copper thermalisation
coils, and braided flex lines into a gold sample package with SMA launches, launch
traces and bond wires. The chip on it is a procedural texture (feedline, qubit
cells with meandered inductors, couplers, readout resonators, flux lines, bond-pad
ring), printed "ILLUSTRATIVE LAYOUT · NOT A DEVICE DESIGN"; its only data is that
each junction marker is tinted by one record's headline status. In "Gates only
hardware can close" the stage pins on wide screens while the stack separates and
the camera descends to the chip, where a callout repeats that it is artwork, not a
QMHP design and not a measurement. Everything is labelled on the page as not a
model of QMHP or of any real hardware.

It renders only while on screen and the tab is visible, runs at 30 fps on touch
devices, is disposed on every page change, and is skipped - the SVG figure is shown
instead - without WebGL, under `prefers-reduced-motion`, with Data Saver on, or on
devices reporting two or fewer CPU cores. It requests nothing: it receives data the
page already fetched through its single GET helper.

**three.js 0.186.1 (MIT)** is the one third-party script, vendored as a tree-shaken
bundle at `static/vendor/three.min.js` with its licence. The bundle contains no
network code at all. How it was built, and its SHA-256, are recorded in
`vendor-src/BUILD.md`; the tests pin the digest and assert the absence of any
network primitive.

**Badge details** (the JSON path and recorded text behind a status, the rule
behind a basis, a gate's reason) open in a popover on hover, keyboard focus or
tap; Escape closes it. On phones every table except the gate matrix becomes a
stack of labelled cards, and touch targets are at least 24 px.

**Type** is Geist, Geist Mono and Instrument Serif, SIL Open Font License 1.1,
vendored as WOFF2 under `static/fonts/` with their licence texts (OFL requires
the licence to travel with the fonts). No font is fetched from a third party.

## What it will not do

| Not available | Why |
|---|---|
| Run an experiment, a solver, Palace, Route A or E1; dispatch a workflow | There is no execution path. Consequential runs need the repository's approved launcher and a scoped human approval. |
| Create, grant, consume or edit an approval | Approvals are human decisions. The viewer shows approval files and their digests; it cannot validate that one authorises anything. |
| Edit a contract, predeclaration, config, result, manifest or provenance record | The repository is an immutable evidence source. Corrections are new linked records made through review. |
| Commit, push, branch, merge, or act on a PR | The viewer reads which commit is checked out from git's own files and never runs git. |

These are listed in the UI under **Unavailable actions** as disabled controls
with the reasons, rather than being implemented. There is no hidden admin or
write mode, no flag and no environment variable that enables one: the code does
not exist.

## Architecture

```
browser ──GET──▶ server.py ──▶ adapter.py ──▶ repo_fs.py ──▶ repository files (read)
                 GET/HEAD only   views, labels   the only file access
                                  │
                                  └──▶ classify.py   explicit labelling rules
```

| Module | Role |
|---|---|
| `repo_fs.py` | The single filesystem gateway. List, stat, read and hash only; every open is `"rb"`. Paths are confined to the repository: absolute paths, `..`, backslashes, NUL, `.git`, `.venv`, caches and symlinks resolving outside the root are refused. Git metadata (HEAD, refs) is read from fixed files, never from a caller-supplied path. |
| `classify.py` | The labelling rules, stated as data and shown verbatim in the UI. |
| `adapter.py` | Parses `results/`, `experiments/`, approval files, manifests, `master/` and documents into views. Re-hashing a manifest is a read. |
| `server.py` | `http.server` handler with `do_GET` and `do_HEAD` only; the standard library answers every other verb with `501`. All routes are in `ROUTES`. Repository content is returned as JSON strings and rendered as text, so a committed HTML/SVG file cannot run in the viewer's origin. Strict CSP, including `form-action 'none'`. |
| `static/` | A vanilla-JS single page. One `fetch` helper, `method: "GET"`. No forms, no storage, no inline script or style. Fonts are served only as `fonts/<name>.woff2`. |

## Information architecture

| Section | Shows | Source |
|---|---|---|
| Overview | Checkout, counts by evidence basis and status family, latest record per family, hardware-gated gates, frozen-master status and open provenance questions | everything below |
| Experiments & contracts | Spec, `master/`, `contracts/`, `config/`, `sweeps/`; each `experiments/<id>/` with its files by role, execution state as its own files state it, approvals, linked records | `experiments/**`, `master/**` |
| Evidence records | Every `results/<id>/`, filterable by basis, status family and family; per-record statement, headline statuses with their JSON paths, report, primary JSON tree, all status statements, files and links | `results/*/summary.json`, `execution_record.json`, `batch_report.json`, `corrective_analysis.json`, `report.md` |
| Candidates & runs | Candidate gate evaluations and named runs | `results/*/<candidate>/gate_report.json`, `summary.runs` |
| Gate status | Frozen gate definitions (hardware gates omit PASS), result matrix, distinct recorded reasons, record verdicts | `master/validation_gates.yaml`, gate reports |
| Provenance & hashes | Master digests re-measured; per-record byte manifests re-measured on request; declared digests shown separately from measured ones | `master/provenance.json`, `results/*/manifest.sha256` |
| Execution & audit trail | Experiment states, approval files with state (ON FILE / DRAFT / CONSUMED), timeline of records, approvals, executions, spent attempts and withdrawals | timestamps inside the files |
| Corrections | Corrective records, `supersedes` / `correction` / `withdrawn_claims` fields, WITHDRAWN records, correction headings in `docs/` | JSON fields and markdown headings |
| Evidence classification | The basis rules, the status families and what they mean, records grouped by basis | `classify.py` |

When a directory such as `experiments/` is absent from the checked-out commit,
the viewer says so; it never reaches into other branches.

## How labels are assigned

**Evidence basis** is decided by ordered rules (first match wins), each shown
on the record page with the reason it fired:

| Rule | Basis | Condition |
|---|---|---|
| R1 | SYNTHETIC | identifier contains `SYNTHETIC` |
| R2 | SYNTHETIC | `synthetic`/`synthetic_only` true, a `not_qmhp` key, or a `TEST_FIXTURE` classification |
| R3 | MEASURED | a key `evidence_class`/`classification`/`evidence_basis` literally equals `MEASURED` |
| R4 | ANALYSIS | `palace_launched: false`, a corrective-analysis `kind`, or a dry-run/admission record |
| R5 | SOLVED | solver execution provenance, a SOLVED gate result, or a `solver/` output directory |
| R6 | SOLVED | an approval-bound execution: `approval_sha256` plus recorded `resources` |
| R0 | UNCLASSIFIED | nothing matched; the viewer does not guess |

MEASURED is never inferred from prose, lists of allowed classes or anything
else. Experiments are SYNTHETIC only by name; a directory that merely contains
a synthetic fixture file is listed as a DECLARATION with that file flagged.

**Status labels** are tokens quoted from the record's own `status`, `verdict`,
`outcome`, `disposition` (and similar) fields, e.g. `"PREPARED. NOT APPROVED.
NOT EXECUTED. ..."` yields `PREPARED`, `NOT APPROVED`, `NOT EXECUTED`. A
*family* (QUALIFIED, UNQUALIFIED, FAILED, REFUSED, INCOMPLETE, HARDWARE-GATED,
BLOCKED, TIMEOUT, INCONCLUSIVE, WITHDRAWN, PREPARED, ...) only picks the colour
and the filter facet. Unknown tokens are shown as recorded, in a neutral colour.
The badge text is always the original token; hovering shows its JSON path.

**Hashes.** Only files named `*manifest.sha256` are byte manifests and are
re-measured (MATCH / MISMATCH / ABSENT FROM CHECKOUT). Other `.sha256` files
are shown as declared digests and never byte-compared, because what they
digest is defined by the code that wrote them: `PALACE-VERIFY-*/campaign.sha256`,
for example, digests the campaign definition's canonical JSON form, not the
bytes of `campaign.json`.

## Tests

`tests/test_readonly_frontend.py` runs in the default suite (`uv run pytest`).
It proves the read-only property statically and dynamically:

* the handler defines only `do_GET`/`do_HEAD`; every route answers `501` to
  POST, PUT, PATCH, DELETE, OPTIONS, TRACE and WebDAV verbs; admin-style paths
  do not exist;
* no filesystem write, rename, delete, mkdir, chmod or non-read `open` exists
  in the package (AST);
* no subprocess, shell, `os.system`/`exec*`/`spawn*`, `eval`/`exec` or
  environment-driven mode exists;
* imports are a fixed allowlist: no solver, orchestrator, evaluator, model,
  geometry, contract, script or experiment code, and no network client;
* no git write command, git library or GitHub API appears anywhere;
* approval files are byte- and mtime-identical after being listed, opened and
  cross-referenced, and no route names an approval action;
* the page uses one GET-only `fetch`, no forms, storage, beacons or sockets;
* driving every route, including re-hashing every manifest, leaves a byte copy
  of the repository unchanged, and the real checkout and its `.git` metadata
  untouched.

No test runs viewer code against the real checkout: dynamic tests use fixture
repositories and a byte copy under `tmp_path`, so even a broken viewer could not
damage committed evidence while being tested.
