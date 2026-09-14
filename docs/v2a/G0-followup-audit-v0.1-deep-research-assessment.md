# QMHP-CoPro V2A G0 Follow-Up Audit v0.1 — Deep Research Assessment

| | |
|---|---|
| Subject | QMHP-CoPro V2A G0 follow-up audit v0.1 |
| Assessment received | 2026-09-14 |
| Top-level disposition | **Physical G0 remains BLOCKED; M3 mechanism receives a CONDITIONAL GO for one bounded coherent prescreen** |
| Citation keys | `[Key]` markers resolve in [`references.md`](references.md), which records for each cited work whether its identity and the attributed claim were confirmed |
| Arithmetic | every stated number is reproduced by [`tools/v2a/check_assessment_arithmetic.py`](../../tools/v2a/check_assessment_arithmetic.py); inputs taken on report are listed in [`reported-not-reproduced.md`](reported-not-reproduced.md) |
| Registration | the three items to freeze before M3 are given executable form in [`m3-coherent-prescreen-registration.md`](m3-coherent-prescreen-registration.md) |

## Executive disposition

**The follow-up audit is technically coherent and materially strengthens the V2A programme. I agree with its top-level disposition: PHYSICAL G0 REMAINS BLOCKED.**

The most important change is that V2A has crossed from "plausible mechanism family" into a **specific coupled-circuit hypothesis with a quantitatively testable M3 mechanism**. The external literature strongly supports the scientific legitimacy of testing a state-conditioned transmon-mediator $2\pi$ cycle: experimentally realised fluxonium–transmon–fluxonium systems use exactly this broad mechanism class, with distinct mediator transition frequencies conditioned on the fluxonium states. The latest published Singh *et al.* experiment explicitly implements a conditional coupler rotation and finds that short gates are limited by unwanted nearby transitions while longer gates become limited by coupler relaxation. [Singh]

That does **not** validate QMHP's numerical circuit, $|0\rangle/|2\rangle$ encoding, 5.9 MHz conditional splitting, proposed control amplitude, $8\times10^{-4}$ screen, or loss model. Ding *et al.* demonstrated very high fidelity in a different FTF implementation, but those results establish the viability of the architecture class, not transferability of gate performance to V2A. [Ding; FTF-2]

My disposition by item is:

| Follow-up item | Deep-research disposition | Reason |
|---|---:|---|
| Lumped capacitance/coupling calculation | **PASS within declared model; reproduction not independently repeated here** | The conclusion is physically well framed. The new five-node matrix itself is not present in my accessible project artefact set, so I cannot independently re-invert it in this review. |
| Static SQUID sign convention | **PASS for static spectrum only** | The dynamic caveat is not optional: time-dependent flux can introduce derivative/connection terms depending on the coordinate choice. Experiment has confirmed errors from naïvely omitting them. [Bryon] |
| Dressed-state labelling | **PASS as reported at tested points; broader continuation still required** | The reported overlaps are strong for those points, but $f_C=0.28\Phi_0$ and driven trajectories have not thereby been certified. |
| M1 nominal static wait | **DEPRIORITISE** | The arithmetic supports the decision. It is a negative result for the tested nominal static-wait family, not a no-go theorem for all conditional-phase mechanisms. |
| M3 mechanism | **RETAIN** | The reported conditional spectrum and charge matrix element are sufficient to justify a bounded coherent selectivity study, but not optimisation or P4 admission. |
| Computational control/loss domains | **BOUND AS EXPLORATORY STRESS DOMAINS** | Sensible for sensitivity analysis; they are not measured hardware distributions or bounds. |
| Physical controls/loss | **BLOCKED** | No measured complex transfer function, EM-qualified mode structure, destination-resolved decay model or Branch-A driven measurements. |
| Four-layer structural schedule | **PASS structurally** | It proves edge colouring/scheduling, not hook safety, physical CZ compilation or readiness. |
| Once-only ownership rules | **PASS conceptually** | Numerical ledger reclosure must wait for the native all-in channel. |
| Native P4/P5 closure | **BLOCKED** | No converged driven/open-system V2A channel exists. |
| AMD-E | **DISABLED correctly** | There is still no native V2A gate from which a physically meaningful fault-conditioned observability calculation can be made. |

There is one important practical refinement to the audit: **the bounded M3 coherent-selectivity prescreen can now be executed as an exploratory mechanism test, provided three registration ambiguities are closed first.** It must not be allowed to mutate into the 256-evaluation optimisation campaign.

## Circuit and static audit

### The static architecture has become scientifically testable

The proposed V2A circuit is consistent with an experimentally established class of fluxonium–transmon–fluxonium systems. In such systems, the transmon mediator couples strongly to higher fluxonium levels, producing logical-state-dependent mediator transition frequencies. Singh *et al.* experimentally observed four conditional coupler frequencies and drove one selectively to implement the conditional phase; Ding *et al.* demonstrated the broader FTF architecture with suppressed static $ZZ$ and high-fidelity controlled-phase operation. [Singh; Ding]

The audit's insistence that the Maxwell capacitance matrix generate both self-charging and coupling terms is therefore the right modelling discipline. It is materially better than specifying isolated $E_C$ values and then appending arbitrary $g$'s. However, positive definiteness of a lumped five-node capacitance matrix proves only that **that finite lumped electrical model is well posed**. It does not prove that the physical layout lacks distributed resonances, package modes, readout hybridisation or superinductor-array modes.

That distinction has become particularly important in fluxonium. Singh *et al.* report that fabrication uncertainty placed their transmon coupler close to a readout resonance, partly hybridising the two and degrading coherence. Experimental fluxonium readout work has also found that external/spurious modes can be required to explain observed leakage, while 2026 measurements of measurement-induced transitions found cases involving transmission-line-like modes of the fluxonium superinductor. [Singh; RO-modes; MIST-2026]

Accordingly, the audit is correct to leave **geometry/EM extraction BLOCKED**.

The latest methodology for driven Josephson circuits reinforces this. Lu *et al.* distinguish static circuit quantisation from the problem of deriving physically delivered microwave drives and port-induced noise in arbitrary geometry; their framework uses classical electromagnetic response to construct time-dependent drive Hamiltonians and corresponding dissipation channels. [Lu]

I would sharpen the G0 requirement slightly:

> A complex multiport $S$-matrix is necessary evidence for delivery and crosstalk, but is not by itself the complete driven Hamiltonian. G0 ultimately needs the calibrated mapping from physical port excitations to the effective charge/flux drive operators and their noise channels.

### The SQUID sign result is correctly scoped

The claim that reversing the tested imaginary hopping sign leaves the **static** eigenvalues unchanged is compatible with a static phase/gauge transformation. The audit correctly refuses to extrapolate this result to time-dependent mediator-flux control.

That caveat is experimentally important, not merely formal. Bryon *et al.* tested fast flux ramps in heavy fluxonium and found that naïvely dropping the term associated with $d\Phi/dt$ gives predictions inconsistent with experiment; the observations agree with formulations retaining the required derivative term or using appropriately chosen irrotational variables. [Bryon]

Therefore:

$$
\boxed{\text{static spectral equivalence}\not\Rightarrow
\text{dynamic-control equivalence}.}
$$

Before any M1 trajectory involving $f_C(t)$ is revived, its time-dependent Hamiltonian should be derived in a declared fixed basis or an equivalent gauge-consistent formulation. This is **not required for the first M3 study if M3 truly holds $f_C$ fixed**.

### Dressed labels are good enough for the current static screen

The reported minimum continuation overlap of $0.994562$ and final bare overlap of $0.897881$ are reassuring for the tested points. Agreement between independent bare-overlap and continuation labels further reduces the risk that the reported conditional lines are simple state-tracking mistakes.

But the current result does not yet justify assuming labels remain valid across the whole future screen. In particular, the proposed M3 sensitivity point

$$
f_C=0.28\Phi_0
$$

lies outside the two explicitly audited label points $0$ and $0.2\Phi_0$.

**Before using $0.28\Phi_0$ as a control sensitivity point, repeat the label and truncation checks there.**

This is a cheap prerequisite and should happen before propagation.

### M1 has been demoted correctly

The submitted sweep gives nominal static-wait times of roughly $8.05$–$8.37\,\mu{\rm s}$ over $f_C=0$ to $0.30\Phi_0$. The displayed point at $62.1$ kHz independently gives

$$
T_\pi=\frac{1}{2(62.1{\rm\,kHz})}\approx8.052\,\mu{\rm s}.
$$

A $1\,\mu{\rm s}$ pure-wait conditional-phase gate would require

$$
\frac{\zeta}{2\pi}\approx500{\rm\,kHz},
$$

so the tested nominal points are about a factor of eight too weak.

**DEPRIORITISE is exactly the right scientific decision.**

Do not call M1 "failed" globally. A different component point, avoided-crossing trajectory, geometric phase, or nonadiabatic control mechanism would constitute a materially different mechanism. But there is no reason to spend the next finite compute budget searching a nominal static-wait family that has already missed the timing allocation by this margin.

## M3 selectivity assessment

### The 5.9 MHz line separation is meaningful—but not yet generous

The most important new physical result is the reported conditional mediator spectrum, with the target $22$-conditioned transition near

$$
f_{22}=7.016031785\ {\rm GHz}
$$

and the nearest other logical-conditioned line roughly

$$
\Delta_{\min}\approx5.90\ {\rm MHz}.
$$

Combined with

$$
|\langle 22,1_C|\hat n_C|22,0_C\rangle|
\approx1.300454,
$$

this is enough to say that **M3 has a real driven transition to test**.

It is not enough to say that the transition is selectively addressable.

This distinction agrees closely with the current FTF literature. Zwanenburg and Andersen explicitly show that minimum conditional-line separation is an important gate parameter but does **not** determine leakage by itself: the drive matrix elements and additional higher-state transitions also matter. Their scaled FTF modelling also finds spectator-state-dependent target-frequency shifts of several MHz in architectures based on experimentally realised devices. [ZA]

That is highly relevant to V2A. A nominal **5.9 MHz desired conditional separation is of the same order as spectator shifts that have arisen in other FTF parameter regimes**. This does not predict that QMHP will have the same shift; the devices are different. It does demonstrate why spectator embedding cannot be deferred all the way to final certification. [ZA]

Singh *et al.* reached the same issue experimentally from the pulse side: at short duration, spectral overlap with unwanted conditional coupler transitions produced coherent errors, motivating DRAG and Fourier-engineered pulse shapes. [Singh]

### The proposed duration ladder contains an important boundary case

For an ideal resonant $2\pi$ cycle, the **target Rabi-cycle frequency** is

$$
f_R=\frac{1}{T}.
$$

For the proposed durations:

| $T$ | Required target $f_R$ | $f_R/\Delta_{\min}$, using $5.90$ MHz |
|---:|---:|---:|
| 150 ns | 6.67 MHz | 1.13 |
| 200 ns | 5.00 MHz | 0.85 |
| 300 ns | 3.33 MHz | 0.56 |
| 400 ns | 2.50 MHz | 0.42 |
| 500 ns | 2.00 MHz | 0.34 |
| 650 ns | 1.54 MHz | 0.26 |
| 800 ns | 1.25 MHz | 0.21 |

This table does **not** calculate leakage. It shows why leakage must be propagated.

At $150$ ns, the target Rabi scale actually exceeds the nominal separation to the nearest competing conditional line. At $200$ ns it is of the same order. Those points are therefore not in an intuitively narrowband regime. A shaped pulse can behave much better than a rectangular-pulse bandwidth estimate, and deliberately engineered interference can suppress unwanted response, but that improvement must emerge from the actual dynamics. Singh *et al.* needed pulse-spectrum engineering for exactly this reason. [Singh]

There is a second subtle issue. Using the audit's own convention and

$$
|n_C|\simeq1.30,
$$

the quoted 150 ns ideal-cycle coefficient is approximately

$$
|u_C|\simeq5.13{\rm\,MHz},
$$

which is already slightly **above** the proposed

$$
|u_C|\le5{\rm\,MHz}
$$

search cap. With $n_C$ toward 1.36 it may fall just inside the cap, but the exact target matrix element is reported closer to 1.300454. Moreover, any smooth envelope with finite edges normally has less integrated area than a rectangular pulse with the same peak.

Therefore I would change the registration wording from "150 ns is an admitted candidate duration" to:

> **150 ns is retained as a boundary/stress duration; feasibility under the 5 MHz peak coefficient cap must be established from the exact registered envelope and drive-Hamiltonian convention.**

No threshold needs to be changed.

### One factor-of-two convention must be frozen before propagation

The reported amplitude arithmetic implicitly adopts a particular definition of $u_C$. That definition must be written explicitly in the executable registration.

For example, expressions of the form

$$
\frac{H_d(t)}{h}
=
2u_C(t)\hat n_C
\cos(2\pi f_dt+\phi)
$$

and

$$
\frac{H_d(t)}{h}
=
u_C(t)\hat n_C
\cos(2\pi f_dt+\phi)
$$

differ by a factor of two in the relationship between the quoted laboratory-frequency coefficient and the rotating-wave Rabi rate.

This is a classic place for otherwise correct gate studies to acquire an invisible factor-of-two discrepancy.

The M3 prescreen registration should therefore give, literally:

$$
\boxed{H_d(t)=\text{exact expression in the simulation}}
$$

including whether $u_C$ is:

- a peak cosine coefficient,
- an RWA coupling,
- a Rabi frequency,
- or an angular-frequency amplitude.

The same rule applies to MHz versus Mrad/s.

### The first prescreen should remain deliberately primitive

I would **not** begin with DRAG, FAST-DRAG, reinforcement learning or a 256-evaluation optimiser.

The first calculation should answer a simpler falsification question:

> With the frozen coupled Hamiltonian and one prospectively registered smooth one-tone envelope family, can a $22$-conditional mediator cycle acquire the intended phase, return the mediator, and leave the other logical sectors acceptably undisturbed anywhere inside the allowed $150$–$800$ ns / $5$ MHz model domain?

The external experiments show that sophisticated pulse shaping can materially reduce coherent leakage. That is precisely why using it immediately would weaken this first screen: an optimisation method might manufacture a highly tuned numerical success before the basic spectral mechanism has demonstrated a usable window. [Singh; FTF-2]

For each registered duration, I would export at least:

$$
\phi_{ZZ},
\quad
P_{\rm return}^{ij},
\quad
P_{\rm residual,C}^{ij},
\quad
P_{\rm sink}^{ij},
\quad
P_{\rm higher}^{ij},
\quad
P_{\rm RO}^{ij},
$$

for all four encoded basis sectors, along with the full coherent logical map and the operator-maximised terminal loss over arbitrary logical superpositions.

Also retain:

$$
A_C=\int p_C(t)\,dt
$$

and peak mediator population, but **do not translate either quantity directly into P4 error**.

That translation requires a physical dissipative model.

## Controls, loss and omitted physics

### The loss grid is suitable as a stress test, not as evidence

The proposed mediator lifetime sweep from $1.2\,\mu{\rm s}$ to $1\,{\rm ms}$ is a reasonable exploratory span. In particular, the $1.2\,\mu{\rm s}$ low end is traceable to a real FTF experiment: Singh *et al.* report operating their transmon coupler at a point where its lifetimes were around $1.2\,\mu{\rm s}$, and longer gate durations were experimentally limited by coupler relaxation. [Singh]

That makes $1.2\,\mu{\rm s}$ a defensible **adverse comparator**.

It does not make it a V2A rate.

Likewise, other FTF work has reached much better gate performance in different devices and operating regimes. Those experiments confirm that the architecture class is capable of much better performance; they do not tell us which $T_1$ to assign to the QMHP mediator. [Ding; FTF-2]

The audit is therefore correct:

$$
\boxed{\text{unknown physical rates remain unknown}.}
$$

### A single $T_1/T_\phi$ pair will eventually be inadequate

The eventual physical model should be **operator- and destination-resolved**, not merely one $T_1$ and one $T_\phi$ attached to every level.

Fluxonium relaxation is known experimentally to depend on bias, frequency, temperature and mechanism. Recent studies separately identify dielectric loss, flux noise, quasiparticle processes, radiative/control-line coupling and other mechanisms as relevant depending on the device and operating point. [Loss-1; Loss-2; Loss-3]

The July/August 2026 quasiparticle work is especially useful conceptually: measured excitation and de-excitation rates depend on flux and require details such as superconducting-gap asymmetry to model correctly. It is another warning against replacing missing Branch-A rates with a generic literature lifetime. [QP-2026; Loss-3]

For V2A, physical G0 therefore still needs at minimum evidence sufficient to construct transition-specific rates of the form

$$
\Gamma_{i\rightarrow j}^{(\alpha)}
$$

for relevant operators/mechanisms $\alpha$, or defensible upper bounds where direct measurement is not yet possible.

The project-specific direct unlocated

$$
2\rightarrow0
$$

bypass limit of $5\,{\rm s}^{-1}$ must remain a separate requirement. A long logical $T_1$ elsewhere in the spectrum cannot be used to establish that rate.

### Temperature and initial mediator population should remain separate stress dimensions

The $15/20/30$ mK sweep and the initial mediator populations $0,\ 10^{-3},\ 10^{-2}$ should not be conflated.

At a roughly $7.016$ GHz mediator transition, the equilibrium Bose occupation implied by those temperatures is extremely small—approximately $1.8\times10^{-10}$, $4.9\times10^{-8}$, and $1.3\times10^{-5}$, respectively. Therefore initial occupations of $10^{-3}$ or $10^{-2}$ are best interpreted as **non-equilibrium/residual-excitation stress conditions**, not consequences of a 15–30 mK thermal bath.

That is scientifically useful. Keep both parameters independently.

### The proposed crosstalk sweep needs an explicit dB definition

For a complex voltage or scattering amplitude, the registration should say whether

$$
{\rm dB}=20\log_{10}|S_{ij}|
$$

is intended, and specify the port normalisation and the phase reference.

Under that conventional amplitude definition, $-40$ dB means an amplitude ratio of $10^{-2}$, while $-80$ dB means $10^{-4}$.

This is important because the FTF literature finds drive crosstalk to be consequential. Singh *et al.* report strong numerical sensitivity to the relative drive seen by the mediator and other circuit elements; Zwanenburg and Andersen separately examine microwave and coupler-to-coupler crosstalk in scaled FTF architectures. [Singh; ZA]

The four quadrature phases are a good start, but they are **stress samples**, not a measured transfer function.

Physical closure still requires the actual complex multiport response.

### Readout modes cannot yet be treated as harmless passive decorations

Retaining two readout modes in the static calculation is better than deleting them. But their physical effect is still unresolved.

Experiments have found readout photons can produce transitions both inside and outside the fluxonium computational subspace; spurious modes can be necessary to explain observed behaviour. More recent fluxonium MIST experiments also identify contributions from superinductor modes. [RO-MIST; MIST-2026]

This directly supports the audit's requested output field

$$
P_{\rm readout\ mode}
$$

and the continued requirement for omitted-mode/EM validation.

It also means that a future M3 propagation showing negligible population in the **two modelled** readout modes would not by itself close the mode question.

## Timing, spectators and once-only accounting

### The four-layer schedule is valid graph structure, not yet a valid syndrome circuit

The reported physical pair counts

$$
[2,3,2,3,4,3,2,3,2]
$$

sum to $24$, consistent with four layers of six interactions.

That is useful: the pair graph can be edge-coloured into the desired four conflict-free layers.

But it does not establish:

- the required ancilla preparation convention,
- the direction/sign of the available native conditional phase,
- hook-error ordering,
- all basis adapters,
- the claimed $N_{1Q}\le5$,
- mediator reset/recovery,
- or physical next-operation readiness.

The audit correctly leaves the **native hook/basis/readiness compile BLOCKED**.

That caution is reinforced by 2026 FTF scaling analysis. Spectator states can shift both transition frequencies and matrix elements, and naïvely scaling an experimentally motivated FTF architecture can produce very large gate errors unless couplings and inactive couplers are specifically engineered. [ZA]

For V2A, this means the native pair channel cannot be validated entirely in isolation and then assumed unchanged when embedded in a four-neighbour syndrome geometry.

The **P6-E7 resident-sink-to-syndrome test therefore remains an independent mandatory experiment/model validation**, not an optional later detail.

### The once-only accounting rules are fundamentally right

This is one of the strongest parts of the follow-up audit.

If an all-in native V2A propagation already contains mediator relaxation, dephasing, residual excitation, ramp errors, correlated $ZZ$, and some data-qubit decoherence during its interval, those same physical mechanisms must not then be re-added as independent scalar penalties over the same interval.

Similarly, removing background charges outside a gate channel is justified only where:

1. the physical mechanism is actually represented inside the native channel;
2. the same interval is being replaced;
3. its destination semantics are equivalent;
4. correlations introduced by the native gate are retained rather than converted into unrelated scalar error.

The arithmetic

$$
\frac{24(8\times10^{-4})}{9}
=
2.133\ldots\times10^{-3}
$$

is a valid **diagnostic average**, but it is not a logical-noise model and must not replace destination-resolved propagation.

Likewise, four $1\,\mu{\rm s}$ gate layers inside a $20\,\mu{\rm s}$ schedule leave

$$
16\,\mu{\rm s}=0.8\times20\,\mu{\rm s}
$$

outside the native-gate intervals. Therefore genuinely linear-in-time background terms would scale by 0.8 if—and only if—the other 20% has been fully incorporated into the all-in channel.

Thus,

$$
1.700\times10^{-3}\times0.8
=
1.360\times10^{-3}
$$

checks arithmetically.

The quoted $1.441\times10^{-3}$ dephasing residual similarly corresponds to applying the same 0.8 time factor to an approximately $1.80125\times10^{-3}$ parent quantity.

**These are bookkeeping identities, not yet authorised physics substitutions.**

The audit is right not to close the ledger numerically until the native channel exists.

## Revised G0 decision and immediate programme

The audit has advanced enough that I would divide the current state into **computational mechanism admission** and **physical G0 admission**.

### Computational mechanism admission

**M3: CONDITIONAL GO for one bounded coherent prescreen.**

Before executing it, freeze three small but material items:

| Registration item | Required closure |
|---|---|
| Drive normalisation | Exact $H_d(t)$, including factor-of-two, Hz/rad-s convention, peak versus RWA definition of $u_C$. |
| Crosstalk convention | Explicit $20\log_{10}|S|$ or other declared definition, port normalisation and phase convention. |
| $f_C=0.28\Phi_0$ validity | Repeat state-label and truncation/convergence checks at the new sensitivity point before driven use. |

I would also formally mark the **150 ns point as a boundary/stress case**, because the $n_C\simeq1.300454$ ideal-cycle estimate slightly exceeds the $5$ MHz coefficient cap even before finite-edge pulse-area effects.

Then run only the registered one-tone coherent study. Do not allow automatic waveform proliferation, reinforcement learning, gradient optimisation or a 256-evaluation search.

The result should be either:

**Mechanism retained:** at least one useful duration/control region exists and is numerically converged enough to justify physical-model work;

or

**Mechanism redesign:** the registered simple M3 mechanism cannot simultaneously obtain the required conditional phase, mediator return and sufficiently low coherent disturbance inside the admitted model domain.

Until the P4 screen semantics are completely registered, I would report the complete error curves rather than retroactively choosing a coherent-error cutoff after seeing them.

### Physical G0 admission

**BLOCKED.**

The exact missing evidence remains:

| Physical prerequisite | What would actually close it |
|---|---|
| Geometry/modes | Realisable geometry plus EM/mode extraction demonstrating the five-node reduction is adequate over the relevant band. |
| Delivered M3 control | Calibrated complex multiport response and mapping from source waveform to $u_C(t)$, unintended data/mode drives and flux offsets. |
| Physical loss model | Branch-A/mediator level- and destination-resolved decay/dephasing evidence or justified experimental bounds, including driven-state behaviour. |
| Branch-A sink behaviour | Driven sink occupation, lifetime, direct bypass, recovery and next-gate readiness measurements on the relevant device class. |
| Spectator/P6-E7 | Native pair model or experiment with a resident sink and the relevant syndrome/spectator environment. |
| Native schedule | Hook-safe basis/ancilla compile with ramps, embedded phases, recovery and readiness inside each $1\,\mu{\rm s}$ layer. |
| P4/P5 reclosure | Frozen all-in channel followed by once-only destination-resolved round accounting. |
| Experimental ownership | Named experimental lead plus an agreed scoped measurement plan. Nothing in the evidence supplied here establishes that this has yet been secured. |

The latest external evidence makes these requirements **more**, not less, important. Transmon-mediated fluxonium gates are now experimentally well established, but the same literature shows that nearby transitions, coupler $T_1$, drive crosstalk, readout hybridisation and spectators can each dominate performance in different regimes. [Singh; Ding; ZA]

The loss literature likewise shows that fluxonium decay cannot safely be represented by one transferable literature lifetime: dielectric loss, flux noise, quasiparticles, temperature, radiative channels and higher-mode physics can all become relevant depending on device and bias. [Loss-2; Loss-3; Loss-1]

The programme restrictions should therefore remain exactly as they are:

**No 196.773 ns Surface-17 insertion. No Branch-A-versus-Branch-C architecture claim. No conversion of exploratory stress values into hardware measurements. No fabrication-yield statement from the component-box sweep. No PED/AMD-E observability calculation until a native V2A gate exists and its physical fault destinations have been established.**

The strongest next scientific move is now very narrow:

$$
\boxed{
\text{Run one frozen, non-optimising M3 coherent-selectivity prescreen}
}
$$

after the three registration fixes above, while in parallel preparing—not inventing—the missing physical control, loss, EM and spectator evidence.

The follow-up audit therefore represents **real progress without a change in physical G0 disposition**. The central question is no longer whether V2A has a conceivable interaction mechanism. It does. The question is whether the reported $\sim5.9$ MHz conditional mediator structure can support a clean, recoverable conditional cycle under a converged model and, later, under physically measured controls and loss. That is now the correct falsifiable question.

## Summary of the immediate programme

The main change is that M3 has crossed the threshold for a bounded exploratory run, while physical G0 remains blocked. Nothing in this assessment authorises the 256-evaluation optimiser, open-system P4 closure, AMD-E, or any architecture claim.

Before running M3, exactly three registration items are frozen (executable form in [`m3-coherent-prescreen-registration.md`](m3-coherent-prescreen-registration.md)):

1. **Drive convention.** Bind permanently either

   $$
   \frac{H_d(t)}{h}=2u_C(t)\,\hat n_C\cos(2\pi f_d t+\phi)
   \qquad\text{or}\qquad
   \frac{H_d(t)}{h}=u_C(t)\,\hat n_C\cos(2\pi f_d t+\phi),
   $$

   state whether $u_C$ means the peak lab-frame coefficient, the RWA coupling, or the Rabi frequency, and keep all values in cycles per second unless explicitly converted. The one-factor form is the convention under which the "≈5.13 MHz at 150 ns" figure above is correct; under the two-factor form the same cycle needs ≈2.56 MHz. The 150 ns boundary label stands under either.
2. **Crosstalk convention.** Use $\mathrm{XT}_{ij}=20\log_{10}|S_{ij}|$ with port normalisation and phase reference specified. Keep −80/−60/−50/−40 dB as stress points only.
3. **$f_C=0.28\,\Phi_0$ validity.** Repeat dressed-label continuation and the same truncation/grid checks there before any driven propagation. If state identity becomes ambiguous, that sensitivity point is removed rather than relabelled manually.

Then run a deliberately small one-tone coherent-selectivity prescreen. No DRAG, reinforcement learning, gradient optimisation, or adaptive waveform search.

For each duration $T\in\{150,200,300,400,500,650,800\}$ ns, propagate all four logical sectors $00,02,20,22$ and export

$$
\phi_{ZZ},\quad P_{\rm return}^{ij},\quad P_{C,\rm residual}^{ij},\quad P_{\rm sink}^{ij},\quad P_{\rm higher}^{ij},\quad P_{\rm RO}^{ij},
$$

plus the untwirled logical channel, worst-input terminal loss, peak mediator population and $A_C=\int p_C(t)\,dt$.

The 150 ns point is labelled boundary/stress, not a normal candidate: with $n_C\approx1.300$ it is at or slightly beyond the nominal 5 MHz coefficient cap under the one-factor convention before finite pulse edges are charged, and its target Rabi scale (6.67 MHz) exceeds the 5.90 MHz nearest-line separation under any convention.

The result has only two legitimate outcomes:

- **M3 retained:** at least one duration gives a numerically stable conditional cycle with mediator return and a clearly usable coherent-error window.
- **M3 redesign:** the simple registered one-tone mechanism cannot simultaneously produce the required conditional phase, return the mediator, and keep unwanted logical/sink/higher-state disturbance acceptably small.

The final $8\times10^{-4}$ P4 pass is **not** decided from this run. The physical dissipative model is still missing, and the external literature shows the expected trade-off: short pulses suffer spectral-selectivity errors while longer pulses become increasingly exposed to coupler relaxation [Singh].

So the immediate programme is

$$
\boxed{\text{freeze 3 conventions}\;\rightarrow\;\text{run bounded M3 coherent prescreen}\;\rightarrow\;\text{retain or redesign M3}}
$$

while the physical track proceeds in parallel on EM/modes, delivered $S_{21}$, destination-resolved loss, sink behaviour, spectators/P6-E7 and native schedule compilation.

AMD-E stays off until after a native V2A gate survives that chain.
