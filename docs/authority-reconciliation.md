# Authority reconciliation register

**Status:** OPEN — human adjudication required.  This register describes
conflicts and repository-verifiability gaps; it does not amend the frozen
Master, `QMHP-CEM_v0.1_Spec.md`, or the machine-readable master files.

## Canonical Master PDF digest

`master/provenance.json` carries the specification's Master PDF SHA-256,
`c59c518b…7499e`. That digest matches neither PDF present in the vendored
v1.5.8f bundle. The same provenance record also notes that the confirmed digest
labelled as the v1.5.8e *operative* base by the specification is labelled as the
*provenance* base by the AMD-C manifest.

Until the technical authority designates the canonical byte sequences:

- do not substitute either observed PDF digest for the recorded digest;
- do not describe the parent Master PDF as repository-verified; and
- report verification of the machine-readable files separately from
  verification of the unavailable canonical PDF.

## Replication status versus evidence available here

Appendix A of `QMHP-CEM_v0.1_Spec.md` describes the curvature/Richardson/QP
bypass and Eq.(7) diagnostic layers as `INDEPENDENTLY REPLICATED`. The vendored
bundle available to this repository contains no implementation of the Eq.(7)
diagnostic or the curvature/quasiparticle quantities. Consequently, the CEM can
carry their frozen values but cannot reproduce those particular quantities
from the available artefacts. `master/qmhp_v158f_requirements.yaml` and
`docs/regression-pins.md` record that narrower, repository-verifiable fact.

This is not a finding that Appendix A is false: the independent replication
may exist outside the vendored bundle. It is an unresolved evidence-location
and authority-reconciliation issue. Until the missing implementation or an
authority decision is supplied:

- preserve the Appendix A status without silently editing it;
- do not claim that this repository independently reproduces the four carried
  values;
- keep those values out of computed-regression pass claims; and
- distinguish `MASTER-FROZEN` carriage from reproduction by executable code.

The four affected values are:

- `perturbative_root_GHz`;
- `eq7_chi_MHz`;
- `richardson_curvature_GHz_per_Phi0_sq`; and
- `gamma_qp_over_xqp_per_s`.

## Closure record required

A closure should name the deciding authority, identify the canonical artefact
and its digest, state whether a missing replication implementation is being
added or the status wording is being revised, and land as a reviewed change.
Runtime code, generated evidence and test tolerances must not resolve either
question implicitly.
