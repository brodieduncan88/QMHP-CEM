// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Real PicoGK construction. Needs the native runtime (osx-arm64 on macOS 26.5+, or
// win-x64); elsewhere every test here is inconclusive, and the macOS CI job sets
// QMHP_REQUIRE_PICOGK_RUNTIME=1 so that a missing runtime fails instead.
//
// The planted-defect tests are the negative controls: each removes one feature from the
// construction and requires the check that guards it to fail and nothing to be published.

using System.Security.Cryptography;
using System.Text.Json;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

[TestClass]
[DoNotParallelize]
public sealed class NativeGenerationTests
{
    static GenerationResult Generate(Candidate candidate, string output, PlantedDefect defect = PlantedDefect.None) =>
        Object001Package.Generate(candidate, output, new GenerationOptions(Object001Assumptions.DefaultVoxelSizeMm, defect));

    static string Sha256(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    static void AssertPublishedAndConsistent(GenerationResult result, string output)
    {
        string failures = string.Join(" | ", result.Checks.Where(c => !c.Passed).Select(c => $"{c.Id}: {c.Detail}"));
        Assert.IsTrue(result.Published, failures);
        foreach (string name in Object001Package.OutputFiles)
        {
            Assert.IsTrue(File.Exists(Path.Combine(output, name)), name);
        }
        Assert.IsFalse(File.Exists(Path.Combine(output, Object001Package.RejectionReport)));

        using JsonDocument manifest = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, "geometry_manifest.json")));
        JsonElement root = manifest.RootElement;
        Assert.AreEqual("PASSED", root.GetProperty("status").GetString());
        Assert.IsTrue(root.GetProperty("acceptance").GetProperty("all_passed").GetBoolean());
        foreach (string name in new[] { "body.stl", "lid.stl", "ports.json" })
        {
            Assert.AreEqual(Sha256(Path.Combine(output, name)), root.GetProperty("outputs_sha256").GetProperty(name).GetString(), name);
        }

        // Read the published STLs back here, independently of the generator's own report.
        foreach (string part in new[] { "body", "lid" })
        {
            StlReport r = StlCheck.Analyse(File.ReadAllBytes(Path.Combine(output, $"{part}.stl")));
            Assert.IsTrue(r.Watertight, part);
            Assert.AreEqual(1, r.Components, part);
            Assert.AreEqual(root.GetProperty("parts").GetProperty(part).GetProperty("triangles").GetInt32(), r.Triangles, part);
        }

        using JsonDocument ports = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, "ports.json")));
        CollectionAssert.AreEqual(new List<string?> { "P1", "P2" },
            ports.RootElement.GetProperty("ports").EnumerateArray().Select(p => p.GetProperty("id").GetString()).ToList());
    }

    static List<string> FailedIds(GenerationResult result) => result.Checks.Where(c => !c.Passed).Select(c => c.Id).ToList();

    static void AssertRejectedWithNothingPublished(GenerationResult result, string output)
    {
        Assert.IsFalse(result.Published);
        foreach (string name in Object001Package.OutputFiles)
        {
            Assert.IsFalse(File.Exists(Path.Combine(output, name)), name);
        }
        using JsonDocument report = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, Object001Package.RejectionReport)));
        Assert.AreEqual("REJECTED", report.RootElement.GetProperty("status").GetString());
        Assert.AreEqual("geometric", report.RootElement.GetProperty("rejected_at_stage").GetString());
        // The failed parts are kept as evidence, renamed so they cannot pass for outputs.
        Assert.IsTrue(File.Exists(Path.Combine(output, Object001Package.RejectedDir, "body.rejected.stl")));
    }

    static void InTempDir(Action<string> body)
    {
        TestSupport.RequireNativeRuntime();
        string output = TestSupport.NewTempDir();
        try
        {
            body(output);
        }
        finally
        {
            Directory.Delete(output, recursive: true);
        }
    }

    [TestMethod]
    public void TheSeedGeneratesAndEveryCheckPasses() => InTempDir(output =>
    {
        GenerationResult result = Generate(TestSupport.SeedCandidate(), output);
        AssertPublishedAndConsistent(result, output);
        Assert.IsGreaterThan(20, result.Checks.Count);
        foreach (CheckResult c in result.Checks)
        {
            Console.WriteLine($"{c.Id}: {c.Detail}");
        }
    });

    [TestMethod]
    public void EveryCandidateOfTheSweepGenerates()
    {
        foreach (double h in new[] { 1.25, 1.50, 1.75 })
        {
            foreach (double d in new[] { 2.25, 2.50, 2.75 })
            {
                Candidate candidate = TestSupport.Edited(p =>
                {
                    p["vacuum_cavity"]!["height_above_chip_mm"] = h;
                    p["launches"]!["bore_diameter_mm"] = d;
                });
                InTempDir(output => AssertPublishedAndConsistent(Generate(candidate, output), output));
            }
        }
    }

    [TestMethod]
    public void AMissingLaunchBoreIsCaught() => InTempDir(output =>
    {
        GenerationResult result = Generate(TestSupport.SeedCandidate(), output, PlantedDefect.OmitBoreP2);
        AssertRejectedWithNothingPublished(result, output);
        CollectionAssert.Contains(FailedIds(result), "probes:launch_bores_connect_exterior_to_cavity");
    });

    [TestMethod]
    public void AMissingMountingHoleIsCaught() => InTempDir(output =>
    {
        GenerationResult result = Generate(TestSupport.SeedCandidate(), output, PlantedDefect.OmitMountingHole0);
        AssertRejectedWithNothingPublished(result, output);
        CollectionAssert.Contains(FailedIds(result), "probes:mounting_holes_in_material");
    });

    [TestMethod]
    public void AMissingThermalLandIsCaught() => InTempDir(output =>
    {
        GenerationResult result = Generate(TestSupport.SeedCandidate(), output, PlantedDefect.OmitThermalLand);
        AssertRejectedWithNothingPublished(result, output);
        List<string> failed = FailedIds(result);
        CollectionAssert.Contains(failed, "probes:thermal_path_present");
        CollectionAssert.Contains(failed, "body:bounds");
    });

    [TestMethod]
    public void RepeatedGenerationGivesTheSameGeometry() => InTempDir(root =>
    {
        // Byte identity is not required (PicoGK's meshing may order triangles differently
        // between runs); the measured geometry must agree.
        var reports = new List<StlReport>();
        foreach (string run in new[] { "a", "b" })
        {
            string output = Path.Combine(root, run);
            AssertPublishedAndConsistent(Generate(TestSupport.SeedCandidate(), output), output);
            reports.Add(StlCheck.Analyse(File.ReadAllBytes(Path.Combine(output, "body.stl"))));
            Console.WriteLine($"run {run}: body.stl sha256 {Sha256(Path.Combine(output, "body.stl"))}");
        }
        Assert.AreEqual(reports[0].Triangles, reports[1].Triangles);
        foreach ((Vec3 a, Vec3 b) in new[] { (reports[0].Min, reports[1].Min), (reports[0].Max, reports[1].Max) })
        {
            Assert.AreEqual(a.X, b.X, 1e-6);
            Assert.AreEqual(a.Y, b.Y, 1e-6);
            Assert.AreEqual(a.Z, b.Z, 1e-6);
        }
        Assert.AreEqual(reports[0].SignedVolumeMm3, reports[1].SignedVolumeMm3, 1e-6 * reports[0].SignedVolumeMm3);
    });
}
