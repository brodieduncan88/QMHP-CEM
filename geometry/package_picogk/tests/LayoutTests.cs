// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// The layout and its analytic acceptance checks, without PicoGK: these run on every platform.

using System.Text.Json;
using System.Text.Json.Nodes;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

[TestClass]
public sealed class LayoutTests
{
    const double Exact = 1e-12;

    static Object001Layout Layout(Candidate candidate) => Object001Layout.FromCandidate(candidate);

    static Candidate Sweep(double heightAboveChip, double boreDiameter) => TestSupport.Edited(p =>
    {
        p["vacuum_cavity"]!["height_above_chip_mm"] = heightAboveChip;
        p["launches"]!["bore_diameter_mm"] = boreDiameter;
    });

    static IEnumerable<(double H, double D)> SweepGrid() =>
        from h in new[] { 1.25, 1.50, 1.75 } from d in new[] { 2.25, 2.50, 2.75 } select (h, d);

    static List<string> Failed(Object001Layout layout, double voxel = Object001Assumptions.DefaultVoxelSizeMm) =>
        layout.AnalyticChecks(voxel).Where(c => !c.Passed).Select(c => c.Id).ToList();

    [TestMethod]
    public void SeedLevelsFollowTheDocumentedStackUp()
    {
        Object001Layout l = Layout(TestSupport.SeedCandidate());
        Assert.AreEqual(-0.43, l.ZRecessFloor, Exact);
        Assert.AreEqual(0.02, l.ZCavityFloor, Exact);
        Assert.AreEqual(1.5, l.ZCavityCeiling, Exact);
        Assert.AreEqual(-1.43, l.ZBodyBottom, Exact);
        Assert.AreEqual(3.57, l.ZBodyTop, Exact);
        Assert.AreEqual(5.57, l.ZLidTop, Exact);
        Assert.AreEqual(-1.93, l.ZLandBottom, Exact);
        Assert.AreEqual(1.27, l.ZBoreAxis, Exact);
        Assert.AreEqual(2.07, l.PlugHeight, Exact);
        Assert.AreEqual(1.48, l.BoreApertureHeight, Exact);
        Assert.AreEqual(5.0, l.Bores[0].Length, Exact);
        foreach (AxisCylinder hole in l.MountingHoles)
        {
            Assert.AreEqual(13.5, Math.Abs(hole.U), Exact);
            Assert.AreEqual(13.5, Math.Abs(hole.V), Exact);
        }
        Assert.AreEqual(4, l.MountingHoles.Select(h => (h.U, h.V)).Distinct().Count());
    }

    [TestMethod]
    public void EveryCandidateOfTheSweepPassesTheAnalyticChecks()
    {
        foreach ((double h, double d) in SweepGrid())
        {
            Object001Layout l = Layout(Sweep(h, d));
            CollectionAssert.AreEqual(new List<string>(), Failed(l), $"height {h}, bore {d}");
            Assert.IsGreaterThan(0.0, l.BodyVolumeExact);
            Assert.IsGreaterThan(0.0, l.LidVolumeExact);
        }
    }

    [TestMethod]
    [DataRow(1.50, 2.50)]
    [DataRow(1.25, 2.75)]
    [DataRow(1.75, 2.25)]
    public void ClosedFormVolumesAgreeWithAnIndependentPointCount(double height, double bore)
    {
        // The closed forms subtract each cut's volume, which is right only if the cuts are
        // disjoint and inside the solid. Counting points against the CSG membership
        // functions checks that independently.
        Object001Layout l = Layout(Sweep(height, bore));
        var random = new Random(20261008);
        foreach ((string part, Box bounds, Func<Vec3, bool> contains, double exact) in new (string, Box, Func<Vec3, bool>, double)[]
        {
            ("body", l.BodyBoundsExact, l.BodyContains, l.BodyVolumeExact),
            ("lid", l.LidBoundsExact, l.LidContains, l.LidVolumeExact),
        })
        {
            const int n = 2_000_000;
            int inside = 0;
            for (int i = 0; i < n; i++)
            {
                var q = new Vec3(
                    bounds.Min.X + random.NextDouble() * bounds.SizeX,
                    bounds.Min.Y + random.NextDouble() * bounds.SizeY,
                    bounds.Min.Z + random.NextDouble() * bounds.SizeZ);
                if (contains(q)) inside++;
            }
            double fraction = (double)inside / n;
            double estimate = bounds.Volume * fraction;
            double sigma = bounds.Volume * Math.Sqrt(fraction * (1 - fraction) / n);
            Assert.IsLessThanOrEqualTo(5 * sigma, Math.Abs(estimate - exact),
                $"{part}: closed form {exact} mm^3, point count {estimate} mm^3 (sigma {sigma})");
        }
    }

    [TestMethod]
    public void EveryProbeAgreesWithTheLayoutsOwnMembership()
    {
        // A probe that disagreed with the CSG definition would blame PicoGK for a probe error.
        foreach ((double h, double d) in SweepGrid())
        {
            Object001Layout l = Layout(Sweep(h, d));
            IReadOnlyList<Probe> probes = l.Probes(Object001Assumptions.DefaultVoxelSizeMm);
            Assert.IsGreaterThan(100, probes.Count);
            foreach (Probe p in probes)
            {
                bool solid = p.Part switch
                {
                    "body" => l.BodyContains(p.Point),
                    "lid" => l.LidContains(p.Point),
                    _ => l.BodyContains(p.Point) || l.LidContains(p.Point),
                };
                Assert.AreEqual(p.ExpectSolid, solid, $"{p.Check} / {p.Label} at {p.Point} (height {h}, bore {d})");
            }
            CollectionAssert.IsSubsetOf(
                probes.Select(p => p.Check).Distinct().ToList(),
                l.AnalyticChecks(Object001Assumptions.DefaultVoxelSizeMm).Select(c => c.Id).ToList());
        }
    }

    // --- negative controls: each defect must fail the check named for it ----------------

    [TestMethod]
    public void ABoreThatBreaksThroughTheBodyTopIsRefused()
    {
        // contracts/candidate.py accepts any bore below body height - floor (4.0 mm).
        CollectionAssert.Contains(Failed(Layout(TestSupport.Edited(p => p["launches"]!["bore_diameter_mm"] = 3.6))),
            "launch_bores_connect_exterior_to_cavity");
    }

    [TestMethod]
    public void ACavityCeilingAboveTheBodyTopIsRefused()
    {
        List<string> failed = Failed(Layout(TestSupport.Edited(p => p["vacuum_cavity"]!["height_above_chip_mm"] = 4.0)));
        CollectionAssert.Contains(failed, "cavity_leaves_positive_walls");
        CollectionAssert.Contains(failed, "solver_domain_bounded");
    }

    [TestMethod]
    public void MountingHolesThatBreakIntoThePocketAreRefused()
    {
        CollectionAssert.Contains(Failed(Layout(TestSupport.Edited(p =>
        {
            p["vacuum_cavity"]!["width_mm"] = 29.0;
            p["vacuum_cavity"]!["height_mm"] = 29.0;
        }))), "mounting_holes_in_material");
    }

    [TestMethod]
    public void ARecessWiderThanTheCavityIsRefused()
    {
        CollectionAssert.Contains(Failed(Layout(TestSupport.Edited(p => p["chip_recess"]!["xy_clearance_mm"] = 1.5))),
            "recess_fits_inside_package");
    }

    [TestMethod]
    public void AChipThickerThanTheRecessIsRefused()
    {
        CollectionAssert.Contains(Failed(Layout(TestSupport.Edited(p => p["chip"]!["thickness_mm"] = 0.5))),
            "chip_fits_inside_recess");
    }

    [TestMethod]
    public void AVoxelTooCoarseForTheSmallestFeatureIsRefused()
    {
        Object001Layout seed = Layout(TestSupport.SeedCandidate());
        CollectionAssert.AreEqual(new List<string>(), Failed(seed, 0.1));
        CollectionAssert.AreEqual(new List<string> { "feature_resolution" }, Failed(seed, 0.2));
        CollectionAssert.Contains(Failed(seed, double.NaN), "feature_resolution");
    }

    [TestMethod]
    [DataRow("chip", "width_mm", "0")]
    [DataRow("chip", "width_mm", "-20")]
    [DataRow("package", "body_height_mm", "\"5\"")]
    [DataRow("lid", "thickness_mm", "1e400")]
    [DataRow("launches", "count", "3")]
    [DataRow("launches", "count", "2.5")]
    [DataRow("mounting", "hole_count", "2")]
    public void InvalidParametersAreRefusedWhenParsed(string section, string key, string raw)
    {
        Candidate candidate = TestSupport.Edited(p => p[section]![key] = JsonNode.Parse(raw));
        Assert.ThrowsExactly<InvalidDataException>(() => Object001Parameters.FromJson(candidate.Parameters));
    }

    [TestMethod]
    public void UnknownOrMissingParametersAreRefused()
    {
        Candidate extra = TestSupport.Edited(p => p["lid"]!["plug_mm"] = 1.0);
        Assert.ThrowsExactly<InvalidDataException>(() => Object001Parameters.FromJson(extra.Parameters));
        Candidate missing = TestSupport.Edited(p => p["chip_recess"]!.AsObject().Remove("depth_mm"));
        Assert.ThrowsExactly<InvalidDataException>(() => Object001Parameters.FromJson(missing.Parameters));
        Candidate noSection = TestSupport.Edited(p => p.Remove("mounting"));
        Assert.ThrowsExactly<InvalidDataException>(() => Object001Parameters.FromJson(noSection.Parameters));
        using JsonDocument wrongType = JsonDocument.Parse("[]");
        Assert.ThrowsExactly<InvalidDataException>(() => Object001Parameters.FromJson(wrongType.RootElement));
    }
}
