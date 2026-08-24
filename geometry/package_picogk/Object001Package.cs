// Object 001 — single-device readout/Purcell/package test article (spec §7.4).
//
// Required geometric features:
//   * package outer body
//   * chip recess
//   * package/vacuum cavity
//   * removable lid
//   * two opposing SMP-style launch bores/interfaces
//   * mounting features
//   * simple thermal-path geometry
//   * filter housing allowance
//   * explicit chip datum
//   * solver-domain bounding definition
//
// Explicitly NOT modelled here (spec §7.4):
//   * microscopic junctions
//   * the full thin-film fluxonium circuit (that is gdsfactory's job)
//   * the 17-qubit tile
//
// Coordinate convention (spec §7.3), frozen:
//   origin = centre of top surface of chip substrate
//   +X/+Y  = chip plane
//   +Z     = from chip toward package lid
//   unit   = mm

namespace QmhpCem.Geometry;

public static class Object001Package
{
    /// <summary>
    /// Generate Object 001 geometry and write body.stl, lid.stl, ports.json
    /// and geometry_manifest.json into <paramref name="outputDir"/>.
    /// </summary>
    /// <remarks>NOT IMPLEMENTED in v0.1.</remarks>
    public static void Generate(Candidate candidate, string outputDir)
    {
        throw new NotImplementedException(
            "Object 001 PicoGK geometry generation is not implemented in " +
            "QMHP-CEM v0.1. Implement against PicoGK 2.3.0 and satisfy the " +
            "spec §7.6 acceptance tests: positive volume; recess fits inside " +
            "the package; chip fits inside the recess; cavity leaves positive " +
            "walls; launch bores connect exterior to the intended interior " +
            "region; mounting holes remain in valid structural material; " +
            "exported meshes watertight where checkable; ports present; all " +
            "geometry outputs hashed.");
    }
}
