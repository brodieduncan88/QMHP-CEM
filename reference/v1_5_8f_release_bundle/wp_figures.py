"""v1.5.8e whitepaper figures.

Legacy figures are REGENERATED from the numerical values printed in the
v1.5.8d register. They are therefore new artifacts with new digests; the
original v1.5.8a-d PNGs remain provenance under their prior digests.
Figures whose underlying per-device distributions are not printed in the
register (P1, P2, Q4) are not regenerated and are cited as carried-forward
provenance rather than reproduced from incomplete data.
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

B, O, G, RD, GY = "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#7f7f7f"
OUT = "figs/"
import os
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT + name, dpi=150)
    plt.close(fig)


# --- Fig 1: dressed null -----------------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 3.9))
lab = ["Perturbative\nnominal", "Dressed\nnominal", "Ensemble p5",
       "Ensemble median", "Ensemble p95"]
val = [4.314628047, 4.301975383, 4.196973, 4.304923, 4.413971]
ax.plot(range(5), val, "o-", c=B, lw=1.6, ms=7)
ax.axhline(4.301975383, ls="--", c=GY, lw=1)
ax.set_xticks(range(5)); ax.set_xticklabels(lab, fontsize=8)
ax.set_ylabel("Readout-null frequency (GHz)")
ax.set_title("Half-flux logical-blind readout: perturbative vs dressed null")
save(fig, "fig01_dressed_null.png")

# --- Fig 2: collision yield --------------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 3.9))
x, y = ["<13 MHz", "<50 MHz", "<100 MHz"], [8.0, 26.25, 47.5]
ax.bar(x, y, color=B, width=0.55)
for i, v in enumerate(y):
    ax.text(i, v + 1, f"{v}%", ha="center", fontsize=9)
ax.set_ylabel("Devices below clearance threshold (%)")
ax.set_title(r"Exact dressed-null fabrication screen: |$\omega_{24}-f_r^{null}$|")
ax.set_ylim(0, 55)
save(fig, "fig02_collision_yield.png")

# --- Fig 3: Stage 2a corridor -----------------------------------------------
fig, ax = plt.subplots(figsize=(7.6, 4.2))
k = [1, 2, 5]
ax.plot(k, [18.1, 15.3, 7.4], "o-", c=B, label="Dark ceiling: dressed Kerr only")
ax.plot(k, [12.9, 9.8, 2.5], "o-", c=O, label="Dark ceiling: +147 kHz residual")
ax.plot([1, 2], [2.8, 6.2], "o-", c=G, label=r"Fixed-tone $\kappa$/2 self-Kerr knee")
ax.axvspan(2, 3, color=B, alpha=0.10)
ax.text(2.55, 6.0, "inferred\ncorridor", ha="center", fontsize=8)
ax.text(3.6, 8.0, r"No knee within $n\leq21$", fontsize=8, color=G)
ax.set_xlabel(r"$\kappa/2\pi$ (MHz)"); ax.set_ylabel("Achieved sink occupation, n")
ax.set_title("Stage 2a operating constraints"); ax.legend(fontsize=8)
ax.set_ylim(0, 21)
save(fig, "fig03_p6e_corridor.png")

# --- Fig 4: Floquet migration ------------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 4.0))
n = [0, 2, 5, 8, 10, 12, 12.334]
g_ = [180.84, 149.35, 103.84, 60.19, 32.02, 4.53, 0.0]
ax.plot(n, g_, "o-", c=B, lw=1.6)
ax.axhline(0, c=B, lw=1); ax.axvspan(5, 8, color=B, alpha=0.10)
ax.text(6.5, 78, "candidate corridor", ha="center", fontsize=8)
ax.set_xlabel(r"Sink occupation $\bar n$")
ax.set_ylabel(r"Diabatic $|1\rangle\leftrightarrow|14\rangle$ wrapped gap (MHz)")
ax.set_title(r"Stage 2b: 9-photon $|1\rangle\rightarrow|14\rangle$ Floquet-line migration")
save(fig, "fig04_floquet_gap.png")

# --- Fig 5: Purcell ----------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.bar([r"$\kappa/2\pi$ = 2 MHz", r"$\kappa/2\pi$ = 3 MHz"], [6.73, 4.49],
       color=B, width=0.5)
for i, v in enumerate([6.73, 4.49]):
    ax.text(i, v + 0.12, f"{v} $\\mu$s", ha="center", fontsize=9)
ax.set_ylabel(r"Unfiltered dressed $|2\rangle\rightarrow|1\rangle$ Purcell lifetime ($\mu$s)")
ax.set_title("Stage 3a: unfiltered resonator-induced decay"); ax.set_ylim(0, 8)
save(fig, "fig05_purcell.png")

# --- Fig H1: charge matrix ---------------------------------------------------
M = np.zeros((8, 8))
vals = {(0, 1): .080035, (0, 3): .591046, (0, 5): .080630, (0, 7): .018081,
        (1, 2): .659915, (1, 4): .315491, (1, 6): .001779, (2, 3): .581166,
        (2, 5): .418627, (2, 7): .005730, (3, 4): 1.006040, (3, 6): .350404,
        (4, 5): 1.152732, (4, 7): .336455, (5, 6): 1.343638, (6, 7): 1.490253}
for (i, j), v in vals.items():
    M[i, j] = M[j, i] = v
fig, ax = plt.subplots(figsize=(6.6, 5.2))
im = ax.imshow(M, cmap="viridis")
for i in range(8):
    for j in range(8):
        if i != j:
            t = f"{M[i,j]:.3f}" if M[i, j] > 0 else "<1e-9"
            ax.text(j, i, t, ha="center", va="center", fontsize=6.2,
                    color="w" if M[i, j] < 0.9 else "k")
ax.set_xticks(range(8)); ax.set_yticks(range(8))
ax.set_xlabel("j"); ax.set_ylabel("i")
ax.set_title(r"Half-flux charge matrix $|n_{ij}|$ (levels 0-7)")
fig.colorbar(im, ax=ax, label=r"$|n_{ij}|$")
save(fig, "figH1_charge_matrix.png")

# --- Fig J1: ledger budget ---------------------------------------------------
rows = [("4x CZ", 3.20e-3), ("Dephasing", 1.80e-3), ("1Q", 5.0e-4),
        ("Meas/decision", 4.0e-4), ("Missed erasures", 2.5e-4),
        ("QP bypass", 1.0e-4), ("Thermal 0->2", 1.0e-4), ("ZZ/spectator", 2.5e-4),
        ("Nonadiabatic", 2.0e-4), ("Reset back-action", 2.5e-4),
        ("Readout transitions", 1.0e-4), ("Higher leakage", 1.5e-4),
        ("Correlated reserve", 1.0e-3), ("Other residual", 2.0e-4)]
fig, ax = plt.subplots(figsize=(7.8, 4.6))
ax.barh([r[0] for r in rows][::-1], [r[1] for r in rows][::-1], color=B)
ax.axvline(1e-2, ls="--", c=GY, label="program ceiling 1e-2")
ax.axvline(8.5e-3, ls=":", c=GY, label="allocated total 0.0085")
ax.set_xlabel("Provisional unlocated allocation per 20 us round")
ax.set_title("Current 8.50e-3 unlocated-error allocation")
ax.legend(fontsize=8); ax.tick_params(labelsize=8)
save(fig, "figJ1_ledger_budget.png")

# --- Fig L1: validation ladder ----------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 5.4)); ax.axis("off")
steps = [("P0d / P1", "same-device reset + bypass"),
         ("P2 / P3", "logical control + coherence"),
         ("P4-pre / P4", "coupler model + 2Q gate"),
         ("P5", "erasure conversion"),
         ("P6-S / P6-E", "readout / optional data check"),
         ("P7-pre / QEC-MAP", "row-wise map, matched construction"),
         ("P7", "distance-3 logical test")]
for i, (a, b) in enumerate(steps):
    y = 1 - i * 0.142
    ax.add_patch(Rectangle((0.06, y - 0.075), 0.88, 0.085, fill=False, lw=1.1))
    ax.text(0.11, y - 0.033, a, fontsize=9, fontweight="bold", va="center")
    ax.text(0.40, y - 0.033, b, fontsize=8.5, va="center")
    if i < len(steps) - 1:
        ax.add_patch(FancyArrowPatch((0.5, y - 0.078), (0.5, y - 0.135),
                                     arrowstyle="->", mutation_scale=11, lw=1))
ax.set_title("Integrated validation ladder and evidence flow", fontsize=11)
ax.text(0.5, -0.03, "Any failed stop rule blocks downstream scale-up; "
        "measured anchors replace inherited constants.", ha="center", fontsize=7.5)
ax.set_xlim(0, 1); ax.set_ylim(-0.06, 1.06)
save(fig, "figL1_validation_ladder.png")

# --- Fig P3: collision-screen derivation ------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.2))
dphi = np.logspace(-5, -3, 200)
ax.loglog(dphi, 12.99 * (dphi / 1e-4), c=B, lw=1.8)
ax.axvline(1e-4, ls="--", c=B, lw=1); ax.axhline(12.99, ls="--", c=B, lw=1)
ax.plot(1e-4, 12.99, "o", c=B, ms=7)
ax.text(1.15e-4, 14.5, r"$|\delta\Phi|\leq10^{-4}\,\Phi_0$" "\n"
        r"$|\Delta_{24}|\geq12.99$ MHz", fontsize=8)
ax.set_xlabel(r"Registered readout-active flux envelope $|\delta\Phi|/\Phi_0$")
ax.set_ylabel(r"Minimum $|\Delta_{24}|$ for $p_{mix}\leq10^{-4}$ (MHz)")
ax.set_title("Derivation of the 13 MHz broken-parity collision screen")
ax.grid(alpha=0.3, which="both")
save(fig, "figP3_collision_screen.png")

# --- Fig P4: distance-scaling diagnostic ------------------------------------
fig, ax = plt.subplots(figsize=(6.8, 4.2))
ax.bar(["3", "5", "7"], [7.97, 22.48, 63.45], color=B, width=0.5)
ax.plot([0], [8.8], "x", c=O, ms=10, mew=2, label="executed d=3 upper bracket: 8.8x")
for i, v in enumerate([7.97, 22.48, 63.45]):
    ax.text(i, v * 1.04, f"{v}x", ha="center", fontsize=9)
ax.set_yscale("log"); ax.set_xlabel("Code distance d")
ax.set_ylabel("Relative perfect-location advantage (x)")
ax.set_title("Low-p distance-scaling diagnostic - not a circuit-level decoder run")
ax.legend(fontsize=8)
save(fig, "figP4_distance_scaling.png")

# --- Fig Q1 / Q2: decoder benchmark -----------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.0))
ax.bar(["legacy d=3\nfull", "v1.5.8b d=3\nfull", "legacy d=3\nPu", "v1.5.8b d=3\nPu"],
       [1.33e-5, 1.4151e-5, 1.50e-6, 1.50e-6], color=B, width=0.55)
ax.set_yscale("log"); ax.set_ylabel("Logical error per round")
ax.set_title("Independent d=3 reproduction of the legacy decoder anchors")
save(fig, "figQ1_d3_reimplementation.png")

fig, ax = plt.subplots(figsize=(7.4, 4.2))
w, xs = 0.36, np.arange(3)
ax.bar(xs - w / 2, [1.415e-5, 4.394e-7, 6.470e-9], w, color=B,
       label="Pu+Pe charged unlocated")
ax.bar(xs + w / 2, [1.500e-6, 1.988e-8, 9.702e-11], w, color=O,
       label="Pu only / perfect-free-location bracket")
ax.set_xticks(xs); ax.set_xticklabels(["d=3", "d=5", "d=7"])
ax.set_yscale("log"); ax.set_ylabel("Logical error per round")
ax.set_title("Clean-room d=3/5/7 extension under the legacy uniform-Pauli mapping")
ax.legend(fontsize=8)
save(fig, "figQ2_d357_extension.png")

# --- Fig Q3: sink survival ---------------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 4.0))
tm = np.linspace(1.5, 3.0, 50)
ax.plot(tm, -tm / np.log(0.9995) / 1000, c=B, lw=1.8)
ax.axhline(0.020, ls="--", c=B, lw=1.2, label=r"An-like ~20 us = 0.020 ms")
ax.set_xlabel(r"Measurement exposure ($\mu$s)")
ax.set_ylabel("Required driven sink lifetime (ms)")
ax.set_title(r"P6-E sink-survival requirement if dynamic destruction uses $q_{miss}\leq$5e-4")
ax.legend(fontsize=8); ax.set_ylim(0, 6.5)
save(fig, "figQ3_sink_survival.png")

# --- Fig R1: fault groups ----------------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 4.2))
ax.bar(["Data idle", "Ancilla H", "CNOT pairs", "Pre-measure", "Post-reset"],
       [9, 8, 24, 8, 8], color=B, width=0.55)
ax.set_ylabel("Fault groups per syndrome round")
ax.set_title("d=3 clean-room circuit: exact 57 cycle fault groups per round")
ax.text(0.02, 0.94, "596 total groups over 10 rounds = 17 initial + 10x57 cycle + 9 final",
        transform=ax.transAxes, fontsize=8.5)
ax.tick_params(labelsize=8); ax.set_ylim(0, 27)
save(fig, "figR1_mapping_audit.png")

# --- Fig R3: leakage persistence --------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 4.0))
c_ = [1, 2, 5, 10]
ax.plot(c_, [1.0, 1.5, 3.0, 5.5], "o-", c=B, label="Mean affected rounds")
ax.plot(c_, [1, 2, 5, 10], "s-", c=O, label="Maximum affected rounds")
ax.set_xlabel("Unconditional sink-reset cadence (rounds)")
ax.set_ylabel("Temporal support of a sink event (rounds)")
ax.set_title(r"Why Pe$\rightarrow$single-Pauli equivalence requires a reset/LRU cadence contract")
ax.legend(fontsize=8); ax.set_xticks(c_)
save(fig, "figR3_leakage_persistence.png")

# --- Fig R4: filter transition ----------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 4.2))
ax.axvspan(3.2056, 3.6727, color=B, alpha=0.15, label="Required stopband coverage")
ax.plot([3.2056, 3.6727], [-37.65, -37.65], ":", c=B, lw=1.6)
ax.plot([3.6727, 4.1370], [-37.65, 0], "o-", c=B, lw=1.8,
        label="Minimum average transition diagnostic")
ax.axvline(4.1370, ls="--", c=B, lw=1.2, label="Lowest synthetic readout root")
ax.text(3.72, -22, r"$\Delta f$ = 464.2 MHz" "\n" r"$\geq$ 81.1 dB/GHz avg", fontsize=8.5)
ax.set_xlabel("Frequency (GHz)"); ax.set_ylabel("Relative coupling / rejection (dB)")
ax.set_title("Common-filter sharpness requirement from the v1.5.8a ensemble")
ax.legend(fontsize=7.5, loc="lower right")
save(fig, "figR4_filter_transition.png")

# --- Fig S1: row concentration ----------------------------------------------
fig, ax = plt.subplots(figsize=(7.6, 4.2))
nm = ["two_qubit_CZ", "pure_dephasing", "one_qubit_aggregate",
      "measurement_decision", "correlated_reserve"]
pv = [1.20e-3, 1.80e-3, 1.00e-4, 4.50e-4, 3.75e-4]
ax.bar(range(5), pv, color=B, width=0.55)
ax.set_yscale("log"); ax.set_xticks(range(5))
ax.set_xticklabels(nm, rotation=18, ha="right", fontsize=8)
ax.set_ylabel("Per mapped opportunity event probability")
ax.set_title("d=3 row-wise map: concentration hidden by $P_{round}$/100")
save(fig, "figS1_row_concentration.png")

# --- Fig S5: paired filter margin -------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.0))
q = [0, 1, 5, 50, 95, 99, 100]
v = [761.5, 810.1, 841.5, 905.3, 977.2, 1006.5, 1030.8]
ax.plot(q, v, "o-", c=B, lw=1.8)
ax.axhline(464.24, ls="--", c=RD, lw=1.4,
           label="Cross-device common-filter worst pairing: 464.2 MHz")
ax.set_xlabel("Percentile of the N=400 paired same-device distribution")
ax.set_ylabel(r"$f_r - f_{21}$ separation (MHz)")
ax.set_title("Paired per-device filter transition margin (r = 0.860)")
ax.legend(fontsize=8); ax.set_ylim(400, 1100)
save(fig, "figS5_paired_filter_gap.png")

print("regenerated legacy figures ->", len(os.listdir(OUT)))

