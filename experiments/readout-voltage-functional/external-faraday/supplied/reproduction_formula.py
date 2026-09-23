#!/usr/bin/env python3
"""
Reference formula for reproducing the QMHP Faraday comparison.

Requires the original field archives plus numpy, vtk, shapely. This package
does not include the >30 MB archives. Use the geometry and archive hashes in
evaluation/results.json.

Core dimensional conversion:
  omega_nd = 2*pi*f_GHz*(1e9*Lc/c0)
  Phi_nd   = Phi_Bz_mm2 / lambda**2
  V_Faraday = +1j * omega_nd * sqrt(Z0) * Phi_nd

The + sign is for exported +z B_z because the predeclared closed-loop
orientation is clockwise viewed from +z (surface normal -z).

The weighted flux includes:
  * all boundary pieces in A_west, including attribute 10 P_F1;
  * both readout gap strips with weight (x1-x)/w.

Do not restrict A_west to attribute 25 alone.
"""
print(__doc__)
