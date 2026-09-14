"""Regenerate v1.5.8f Master Figures 1-4 from shipped artifacts only."""
import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':9,'figure.dpi':160})
NAVY='#1a3556'; RED='#b03a2e'; GRN='#1e8449'; AMB='#b9770e'

# M1 - dressed-null truncation ladder; values from
# qmhp_v158f_readout_replication.py (re-executable, RUN.md step 2b)
lad={'(10,12)\nproduction':4.301974466,'(12,18)':4.301975388,
     '(14,25)\nspot check':4.301975383}
fig,ax=plt.subplots(figsize=(6.6,2.9))
ys=[(v-4.301974)*1e3 for v in lad.values()]
ax.plot(range(3),ys,'o-',color=NAVY,ms=7,lw=1.5)
ax.axhline((4.301975383-4.301974)*1e3,color=AMB,ls='--',lw=1.2,
           label='register value 4.301975383 GHz')
ax.set_xticks(range(3)); ax.set_xticklabels(lad.keys(),fontsize=8)
ax.set_ylabel('root - 4.301974 GHz (kHz)')
ax.set_title('Dressed logical-blind null vs truncation (Nq, Nph)',fontsize=10)
ax.grid(alpha=0.25); ax.legend(fontsize=7.5)
fig.tight_layout(); fig.savefig('figM1_truncation.png',bbox_inches='tight')

# M2 - 20-seed ensemble
d=json.load(open('ensemble_20seed.json'))
c=np.array(d['counts']); p=d['pooled_rate']
from scipy.stats import binom
fig,ax=plt.subplots(figsize=(6.6,3.0))
ax.hist(c,bins=np.arange(14,40,2),color=NAVY,alpha=0.85,
        label='20 seeds (1-20), this build')
k=np.arange(10,45)
ax.plot(k,binom.pmf(k,400,p)*len(c)*2,color=GRN,lw=1.5,
        label=f'Binomial(400, {p:.4f}) x bin')
ax.axvline(32,color=RED,ls='--',lw=1.3,
           label='release single draw 32/400 (+1.5 sigma)')
ax.set_xlabel('sub-13-MHz rejection count per 400-device draw')
ax.set_ylabel('seeds')
ax.set_title('Collision-screen rejection: independent 20-seed block (E19)',
             fontsize=10)
ax.legend(fontsize=7.2); ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig('figM2_ensemble.png',bbox_inches='tight')

# M3 - T.12' crossing d=3 f=1.00
runs=json.load(open('t12_realistic_location_runs.json'))
rel=json.load(open('qmhp_v158e_runs.json'))
lamC={r['d']:r['lambda_L'] for r in rel if r['name']=='C_m_full_ts'}
pts=sorted([r for r in runs if r['d']==3 and abs(r['f']-1.0)<1e-9
            and r['t_check']==2.0 and r['convention']=='scaled'],
           key=lambda r:r['p_induced'])
P=[r['p_induced'] for r in pts if r['p_induced']>=2e-3]
L=[r['lambda_L']/lamC[3] for r in pts if r['p_induced']>=2e-3]
be=json.load(open('t12_breakevens.json'))['d3_f1.0_t2.0_scaled']
fig,ax=plt.subplots(figsize=(6.6,3.0))
ax.plot(P,L,'o-',color=NAVY,ms=5,lw=1.4,
        label="T.12' grid, d=3, f=1.00, t_chk=2 us (scaled)")
ax.axhline(1.0,color='k',lw=1)
ax.axvspan(be['lo'],be['hi'],color=AMB,alpha=0.22,
           label=f"break-even {be['central']:.3e} [95% CI]")
ax.axvline(be['central'],color=AMB,ls='--',lw=1)
ax.set_xlabel('p_induced per data qubit per round')
ax.set_ylabel('hazard ratio lambda_A/lambda_C (matched)')
ax.set_title("T.12' cost-side crossing (independent execution)",fontsize=10)
ax.legend(fontsize=7.5); ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig('figM3_t12_crossing.png',bbox_inches='tight')

# M4 - T.13' bootstrap, regenerated at the JSON's declared seed/convention
t=json.load(open('t13_distance_trend_release_hazard.json'))['R7_over_R3']
assert t['hazard_convention']=='release'
rng=np.random.default_rng(t['seed']); reps=t['reps']; R=10
S1={("A",3):(25000,1950,20.0),("A",7):(60000,286,20.0),
    ("C",3):(25000,1414,13.5),("C",7):(100000,280,13.5)}
def lam(k,n,tt):
    pr=1-(1-k/n)**(1/R); return -np.log(1-pr)/tt*1000
S1[("A",5)]=(20000,364,20.0); S1[("C",5)]=(20000,267,13.5)
def draw(a,dd):
    n,k,tt=S1[(a,dd)]; return lam(rng.binomial(n,k/n,reps),n,tt)
# consume the RNG stream in the shipped module's exact order (d = 3, 5, 7;
# A then C each) so quantiles reproduce the JSON bit-comparably
hr={dd: draw("A",dd)/draw("C",dd) for dd in (3,5,7)}
Rr=hr[7]/hr[3]
med,lo,hi=np.median(Rr),np.quantile(Rr,0.025),np.quantile(Rr,0.975)
for got,want,tol in ((med,t['central'],5e-4),(lo,t['lo'],5e-4),(hi,t['hi'],5e-4)):
    assert abs(got-want)<tol, (got,want)
fig,ax=plt.subplots(figsize=(6.6,3.0))
ax.hist(Rr,bins=80,color=NAVY,alpha=0.85)
for xv,cc in ((1.0,'k'),(med,RED),(lo,AMB),(hi,AMB)):
    ax.axvline(xv,color=cc,ls='--',lw=1.2)
ax.set_xlabel('R7/R3 = HR(d=7)/HR(d=3)'); ax.set_ylabel('bootstrap count')
ax.set_title(f"T.13' double ratio: {med:.4f} [{lo:.4f}, {hi:.4f}], "
             f"P(R>1)={np.mean(Rr>1):.3f} - EXPLORATORY\n"
             f"(release -ln hazard convention, seed {t['seed']}, "
             f"{reps:,} resamples)",fontsize=8.4)
ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig('figM4_t13.png',bbox_inches='tight')
print("figM1-M4 regenerated from shipped artifacts; M4 matches its JSON")
