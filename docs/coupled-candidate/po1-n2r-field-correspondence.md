# PO1 m1 ↔ N2R: the field-correspondence attempt, and why it did not complete

**Status: CORRESPONDENCE NOT ESTABLISHED.** The declared method needs the
archived volume fields. They are not reachable from this environment, so steps
2–6 never ran and **no overlap number in this note is computed from a field**.
PO1's committed record and its pre-declared verdict — **INCONCLUSIVE FOR MODE
IDENTITY** — stand exactly as recorded; nothing here amends them. No coupling,
no `g`, no registered-definition change, no Palace run.
Record: `experiments/po1-n2r-correspondence/`.

> **Forward pointer, added later. Nothing below is withdrawn or edited.**
> The *transport limitation* of §3 — that the archives were unreachable, so
> steps 2–6 did not run — is superseded by
> [`po1-n2r-field-correspondence-external.md`](po1-n2r-field-correspondence-external.md),
> which records an overlap computed where the archives were readable:
> **PO1 m1 ↔ N2R m2, 0.999927020830**. That note *completes* §5's exclusion
> rather than contradicting it — the field data refutes m5 and Bessel bounds
> m8, leaving m2 alone. §2's digests, §5's exclusion and §6's conditional
> frequency comparison stand as written, and PO1's INCONCLUSIVE verdict is
> unchanged by either note.

## 1. The primary question

*Can a full-field comparison on the identical refined mesh establish which N2R
mode corresponds to PO1 mode 1 without using frequency as the selector?*

**In principle yes; here, not answered** — the inputs are unavailable. What the
committed scalar records can do instead is **exclude**, and they exclude six of
the nine candidates. They cannot select among the remaining three.

## 2. Step 1 — digest verification: the one step that completed

Both artefacts exist and their digests were read from the repository's own
Actions API:

| run | artifact | name | bytes | sha256 |
|---|---|---|---|---|
| PO1 `35536625799` | `10612713395` | `order1-ladder-fields-35536625799-1` | 114 545 095 | `a156768c…06ea8dc8` |
| N2R `35313973073` | `10533683685` | `order1-ladder-fields-35313973073-1` | 113 746 865 | `1ca851c4…9eb8b0e` |

N2R's digest **equals the one supplied separately**, before the API was
queried. Two independent statements about the same archive agree, so the
archive is identified. PO1's digest is recorded here for the first time.

## 3. Steps 2–6 — not executed

The artifacts API answers `302` to `*.blob.core.windows.net`
(`productionresultssa16` for PO1, `productionresultssa10` for N2R). The agent
proxy answers **403 to the CONNECT** for that host — `connect_rejected`,
organisation policy. The GitHub MCP server exposes no artifact-download tool,
and a GitHub artifact cannot be fetched by any other route. **No attempt was
made to work around the control.**

So: no mesh-identity check on the exported volumes, no complex-E overlap
matrix, no weighted inner product, no optimal phase or scale, no weighted RMS
difference. Those remain undone, not merely unreported.

## 4. The externally supplied numbers — not reproduced

> PO1 m1 → N2R m2: overlap ≈ 0.999927, optimal-phase weighted RMS ≈ 0.01208;
> overlaps with N2R m1, m3, m4, m5, m6 ≈ 0.0120, 0.000006, 0.000011, 0.000055,
> 0.000287.

Recorded as **unverified third-party input**, not adopted. The task required
independent reproduction; the inputs it needs are unreachable, so nothing here
confirms or contradicts them.

One remark about their internal structure, which is *not* a verification: the
quoted overlap with N2R m1, 0.0120, equals the quoted RMS difference to three
figures. That is the shape a near-unit overlap with m2 plus a small residue
along m1 would take, and it is what removing a term supported at the F1 site
would produce. It is consistent; it is not evidence.

## 5. What the committed records do establish, without frequency

Both runs scale **every** eigenvector to the same unit electric energy —
`E_elec = 6.671281904e-03 J` in every row of both `domain-E.csv` files — so
functionals of `E` are directly comparable between them. Three are available
for every mode of both runs and carry **no** `ω`, `L_s` or inductance:
`p_D` and `p_MA` from `surface-Q.csv` (the integrals of `|E|²` and `|E_n|²`
over the F1 port face, normalised by `E_elec + E_cap`), and `|V|` from
`port-V.csv`.

Declared rule: exclude any N2R mode differing from PO1 m1 by a factor **≥ 10**
in any of the three. Loose on purpose — these are the quantities the operator
change perturbs most, and a tight threshold would exclude the true partner.

| N2R m | `p_D` ratio | `p_MA` ratio | `\|V\|` ratio | verdict |
|---|---|---|---|---|
| 1 | 224.4 | 270.5 | 15.1 | **excluded** |
| 2 | 1.37 | 1.75 | 1.18 | survives |
| 3 | 10 443 | 21 257 | 0.042 | **excluded** |
| 4 | 10 986 | 24 159 | 0.018 | **excluded** |
| 5 | 0.51 | 1.42 | 0.61 | survives |
| 6 | 13 347 | 54 901 | 0.196 | **excluded** |
| 7 | 13 050 | 36 706 | 0.112 | **excluded** |
| 8 | 1.67 | 3.16 | 0.91 | survives |
| 9 | 13 786 | 25 839 | 0.093 | **excluded** |

**Six of nine excluded; `{m2, m5, m8}` survive and cannot be separated.** The
six are N2R m1 — the port-supported island mode — and the five
port-operator-localised artefacts. The three survivors are exactly N2R's
field-resonant modes.

**Why this cannot confirm anything.** Three scalars against ~10⁵ degrees of
freedom, and all three are supported on the port face — precisely where the
operator changed. PO1 m1 and N2R m2 differ by ~37 % in `p_D`, which is fully
compatible with agreeing to ~10⁻² in a global norm. These functionals are the
**worst** available proxy for a global overlap: they rule modes out, and can
never rule one in.

## 6. Frequency comparison — conditional

Reported because it was asked for, and flagged because it **presumes the
correspondence this note did not establish**. Choosing among `{m2, m5, m8}` by
frequency is exactly the tiebreak the approval forbids.

PO1 m1 measured: **3.885827871 GHz**.

| prediction | GHz | signed | absolute | relative |
|---|---|---|---|---|
| conditional `K − Q` (declared removal) | 3.885826970 | **+900.6 Hz** | 900.6 Hz | 2.318e-07 |
| conditional `K − Q/N` (normalised removal) | 3.885825996 | **+1874.9 Hz** | 1874.9 Hz | 4.825e-07 |

The two predictions are 974.3 Hz apart (2.507e-07 relative). PO1 m1 lies
**above both**, nearer the declared removal `K − Q`. Both errors sit ~400×
inside the frozen `Δf ≤ 1e-4` **relative** criterion — which is context, not a
gate, and not a bound.

## 7. Evidentiary scope

**In scope:** two artefact digests verified against the repository's API, one
of them corroborated by an independent prior statement; six of nine N2R modes
excluded as partners for PO1 m1 by frequency-free field functionals on an
identical mesh; an exact frequency comparison against two already-recorded
conditional predictions.

**Out of scope, because it did not run:** every field-based quantity — overlap
matrix, best and second-best correspondence, optimal phase and scale, weighted
RMS difference, and the mesh-identity verification of the exported volumes.

**Unchanged:** PO1's record, its INCONCLUSIVE verdict, the registered R1
definition, the frozen criteria, `invert_two_node` and its guards. No `g`, no
residue, no `E_C`, no invariant triple.

## 8. What this resolves, and what still blocks `g`

**Resolves.** The partner of PO1 m1, if it exists, is one of N2R `{m2, m5, m8}`
— established without frequency. N2R m1 and the five artefacts are ruled out,
which independently corroborates the earlier finding that those five are modes
*of* the port term now removed.

**Still blocks `g`.** (i) The correspondence itself is unestablished, so PO1's
mode identity remains INCONCLUSIVE as recorded. (ii) PO1 measures the operator
change **and** the divergence-free projector's changed constraint set together
and cannot separate them, so even an established correspondence would not
isolate the operator-mapping error. (iii) The normalisation `N = fᵀK⁺f/L` is
still unmeasured, so `E_C,F1F1` stays **UNAVAILABLE** — and without it no
coupling can be formed. (iv) One mesh: nothing here is a continuum result or a
bound.

## 9. One minimum next action

**Obtain the two field archives in an environment whose egress policy permits
`*.blob.core.windows.net`, and run steps 2–6 there.** That is a transport
problem, not a scientific one: the archives exist, their digests are pinned
above, and the analysis is fully specified. Nothing else in this chain can move
until the overlap matrix exists — and it alone would still leave (ii), (iii)
and (iv) above untouched.
