# References cited by the deep-research assessment

The assessment's citation markers were opaque tool tokens (`citeturn…`). They are
resolved to the keys used in the repository version below.

> **Verification limit, applies to every entry.** No source page could be opened
> from this session. Every scholarly host — `arxiv.org`, `journals.aps.org`,
> `link.aps.org`, `doi.org`, `ui.adsabs.harvard.edu`, `semanticscholar.org`,
> `osti.gov` — is refused by this environment's network policy with HTTP 403 at
> the CONNECT tunnel. Identification below rests on converging web-search
> snippets, not on read text. **No entry is confirmed against a source, and no
> attributed claim is confirmed against a source.** Volume, article and DOI fields
> are the least reliable and should be re-checked from an unblocked network before
> any of these are cited in a document that leaves the project.

## Entries

| Key | Work | Identification |
|---|---|---|
| **Singh** | S. Singh, E. Y. Huang, J. Hu, *et al.*, "Fast microwave-driven two-qubit gates between fluxonium qubits with a transmon coupler", arXiv:2504.13718 (Apr 2025); Phys. Rev. Applied **25**, 024020 (Feb 2026) | medium |
| **Ding** | L. Ding, M. Hays, Y. Sung, B. Kannan, *et al.*, "High-Fidelity, Frequency-Flexible Two-Qubit Fluxonium Gates with a Transmon Coupler", arXiv:2304.06087; Phys. Rev. X **13**, 031035 (2023) | medium |
| **FTF-2** | Unresolved. The assessment pairs a second token with Ding at three places. Candidates: "Transmon-assisted high-fidelity controlled-Z gates for integer fluxonium qubits", arXiv:2509.04776 (2025); or the Singh entry above. | low — do not cite |
| **ZA** | M. F. S. Zwanenburg and C. K. Andersen, "Crosstalk in Multi-Qubit Fluxonium Architectures with Transmon Couplers", arXiv:2603.09870 (2026); Phys. Rev. Applied, DOI 10.1103/rf7g-md41 | high for identity, unverified for volume/page |
| **Bryon** | J. Bryon, D. K. Weiss, X. You, S. Sussman, X. Croot, Z. Huang, J. Koch, A. A. Houck, "Time-Dependent Magnetic Flux in Devices for Circuit Quantum Electrodynamics", arXiv:2208.03738; Phys. Rev. Applied **19**, 034031 (2023) | medium |
| **YSK** | X. You, J. A. Sauls, J. Koch, "Circuit quantization in the presence of time-dependent external flux", arXiv:1902.04734; Phys. Rev. B **99**, 174512 (2019) — the source of the *irrotational* construction | medium |
| **RD** | R.-P. Riwar, D. P. DiVincenzo, "Circuit quantization with time-dependent magnetic fields for realistic geometries", arXiv:2103.03577; npj Quantum Inf. **8**, 36 (2022) | medium |
| **Lu** | Y. Lu, T. Zhao, A. Vallières, K. *et al.*, "Systematic Construction of Time-Dependent Hamiltonians for Microwave-Driven [superconducting circuits]", arXiv:2512.20743 (Dec 2025, rev. Jan 2026); Fermilab preprint FERMILAB-PUB-25-0960-SQMS. **Preprint; no journal version located.** | medium |
| **RO-modes** | A. Bista, M. Thibodeau, K. Nie, *et al.*, "Readout-induced leakage of the fluxonium qubit", arXiv:2501.17807; Phys. Rev. Applied **25**, 034058 (Mar 2026) | medium |
| **MIST-2026** | M. F. S. Zwanenburg, J. Hu, E. Huang, *et al.*, "Experimental Characterization and Modeling of Measurement-Induced State Transitions [in fluxonium]", arXiv:2606.17866 (Jun 2026). Preprint. | medium |
| **JJ-array** | S. Singh, G. Refael, A. A. Clerk, *et al.*, "Impact of Josephson junction array modes on fluxonium readout", arXiv:2412.14788; PRX Quantum **6**, 040304 (2025) — theory, not an experiment | medium |
| **RO-MIST** | K. N. Nesterov, I. V. Pechenezhskiy, "Measurement-induced state transitions in dispersive qubit-readout schemes", arXiv:2402.07360; Phys. Rev. Applied **22**, 064038 (2024) | medium |
| **QP-2026-expt** | M. Litskevich, K. Manivannan, *et al.*, "Quasiparticle-induced transitions in a fluxonium qubit", arXiv:2607.21329 (Jul 2026). Preprint. | low |
| **QP-2026-theory** | K. Azar, M. Hays, K. Serniak, "Numerical Modeling of Quasiparticle-Induced Dissipation in Fluxonium Qubits", arXiv:2607.24946 (Jul 2026). Preprint. | low |
| **Loss-Azar** | K. Azar, L. Ateshian, M. T. *et al.*, "Characterization and Comparison of Energy Relaxation in Fluxonium Qubits", arXiv:2603.23636 (2026). Preprint. | low |
| **Loss-Sun** | H. Sun, F. Wu, H.-S. Ku, *et al.*, "Characterization of Loss Mechanisms in a Fluxonium Qubit", arXiv:2302.08110; Phys. Rev. Applied **20**, 034016 (2023) | medium |
| **Somoroff** | A. Somoroff, Q. Ficheux, R. A. *et al.*, "Millisecond Coherence in a Superconducting Qubit", arXiv:2103.08578; Phys. Rev. Lett. **130**, 267001 (2023) | medium |

## Attributed claims that the search evidence does not support

These bear on the assessment's own reasoning, not just its citations.

**The ≈1.2 µs mediator lifetime is not confirmed [Singh].** The assessment uses it
twice as the "traceable" and "defensible adverse comparator" low end of the loss
stress sweep. No retrievable text from the Singh work gives any coupler `T₁` or
`T₂` value; only the qualitative statement that longer gates become
relaxation-limited is supported. **The low end of the loss grid is therefore an
unsourced number**, and should be described as a chosen adverse value, not a
traceable one, until the paper is read.

**"Spectator shifts of several MHz" is not confirmed and the evidence points an
order of magnitude lower [ZA].** The only magnitude recovered is a spectator-state
dependence of the conditionally driven transition of ≈10 kHz after the paper's
engineering fixes. The assessment's inference that "5.9 MHz is of the same order
as spectator shifts that have arisen in other FTF parameter regimes" does not
survive on this evidence.

**The same source cuts the other way on line separation [ZA].** The recovered text
reports many operational points where the nearest unwanted transition is more than
**100 MHz** detuned, with leakage at 10⁻⁵ for a 70 ns Gaussian pulse. If that
holds, V2A's 5.90 MHz is roughly 17× *worse* than what that architecture achieves,
which strengthens the assessment's caution about selectivity rather than
supporting its "same order as spectator shifts" framing. The assessment's other
attribution to this source — that minimum line separation "does not determine
leakage by itself" — is its own framing; the paper's emphasis runs the other way,
that leakage transitions are suppressed by designing them far detuned.

**Mechanism mismatch not flagged [ZA].** That gate is a conditional coupler
rotation driven through a fluxonium charge drive; V2A's M3 is a `|22⟩`-conditioned
`2π` mediator cycle driven on the mediator. The architectures are the same class;
the driven transition is not the same object.

**The conditional lines are not conditioned on a `|0⟩/|2⟩` encoding [Singh].** The
four coupler lines correspond to `|00⟩, |01⟩, |10⟩, |11⟩` of two standard fluxonium
qubits. V2A's encoding is different, so the four-line structure is an analogy, not
a precedent.

**Short-gate context the assessment omits [Singh].** That experiment's best
measured performance is ≈98.9 % at 68 ns and ≈99.0 % at 64 ns — errors of order
10⁻², against V2A's 8×10⁻⁴ screen. Citing it as the exemplar of the short-gate
selectivity limit is fair; citing it without that number understates how far the
demonstrated state of the art sits from the screen.

**"Strong numerical sensitivity to the relative drive seen by the mediator" is not
confirmed [Singh].** Only a general statement that microwave crosstalk is a key
engineering concern, and that coupling strengths were designed to minimise
residual crosstalk, was recovered.

**The quasiparticle result is under injection, not ambient conditions
[QP-2026-expt].** Rates were measured under controlled on-chip quasiparticle
injection. The flux dependence and the gap-asymmetry requirement are established
for injected quasiparticles, which is a different claim from ambient operation.
The source's wording is "gap asymmetry across the Josephson junctions", not
"between the two junction electrodes". The assessment also refers to "the
July/August 2026 quasiparticle work" in the singular while attaching two tokens;
there are two distinct and non-interchangeable papers, one experiment and one
numerical model.

**The loss mechanisms are not co-equal [Loss-Sun; Loss-Azar; Somoroff].** The
assessment lists dielectric loss, flux noise, quasiparticle processes and
radiative/control-line coupling as if comparable. The recovered evidence does not
support parity: one study explains the relaxation rate with dielectric loss plus
1/f flux noise and no quasiparticle term; another treats radiative loss to control
and readout circuitry as a subtracted, independently estimated contribution rather
than a leading mechanism; and the millisecond-coherence work explicitly *excludes*
non-equilibrium quasiparticles as the limiter in its circuit. No source was found
identifying radiative/control-line coupling as a leading mechanism in its own
right. The assessment's underlying point — that one transferable literature
lifetime will not do — survives, but its enumeration overstates the evidence.

**Singular versus plural [RO-modes; MIST-2026].** One spurious mode, not modes,
was needed in the readout-leakage work. One 2026 experiment, not "experiments",
identifies superinductor array-mode contributions.

**Suppression, not absence [Ding].** The source's claim is static `ZZ` suppressed
"down to kHz levels" without strict parameter matching — not `ZZ`-free.

**Name collision.** Three different authors named Singh appear across this
literature: Siddharth Singh (the fluxonium–transmon–fluxonium gate experiment) and
Shraddha Singh (Josephson-junction array modes) are different people. The
assessment's bare "Singh *et al.*" is ambiguous next to the array-mode citations.

## Reference correction of record

The Bryon author list is **J. Bryon, D. K. Weiss, X. You, S. Sussman, X. Croot,
Z. Huang, J. Koch, A. A. Houck**. Renderings giving "S. Sanders" or "A. Ozturk"
are wrong. The preprint and journal titles also differ. The *irrotational*
variable construction belongs to **YSK**, not **RD**; the latter derives the
Hamiltonian from circuit geometry and the field's threading instead.
