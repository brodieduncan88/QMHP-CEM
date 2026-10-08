// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// The file boundary and the CLI's exit codes. Everything here runs on every platform: the
// paths that would reach PicoGK either stop before it or assert the runtime's absence.

using System.Text.Json;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

[TestClass]
public sealed class CandidateAndCliTests
{
    static string WriteTemp(string json)
    {
        string path = Path.Combine(Path.GetTempPath(), $"qmhp-cem-{Guid.NewGuid():N}.json");
        File.WriteAllText(path, json);
        return path;
    }

    static string[] Args(string output, params string[] extra) =>
        new[] { "--candidate", TestSupport.SeedFixture, "--output", output }.Concat(extra).ToArray();

    [TestMethod]
    public void CandidateLoadReadsTheSeedFixture()
    {
        Candidate c = TestSupport.SeedCandidate();
        Assert.AreEqual("QMHP-CEM-A-RF-000001", c.CandidateId);
        Assert.AreEqual("object001_single_device_package", c.ObjectType);
        Assert.AreEqual("v1.5.8f", c.MasterRevision);
        Assert.AreEqual(64, c.SourceSha256!.Length);
        Assert.AreEqual(20.0, c.Parameters.GetProperty("chip").GetProperty("width_mm").GetDouble());
    }

    [TestMethod]
    public void CandidateLoadRejectsAnUnsupportedObjectType()
    {
        string path = WriteTemp("{\"candidate_id\":\"X\",\"object_type\":\"not-an-object-001\",\"parameters\":{}}");
        try
        {
            InvalidDataException error = Assert.ThrowsExactly<InvalidDataException>(() => Candidate.Load(path));
            StringAssert.Contains(error.Message, "unsupported object_type");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [TestMethod]
    public void CandidateLoadRejectsADuplicateKeyAnywhere()
    {
        string json = File.ReadAllText(TestSupport.SeedFixture)
            .Replace("\"depth_mm\": 0.45,", "\"depth_mm\": 0.45, \"depth_mm\": 9.0,");
        string path = WriteTemp(json);
        try
        {
            InvalidDataException error = Assert.ThrowsExactly<InvalidDataException>(() => Candidate.Load(path));
            StringAssert.Contains(error.Message, "duplicate key 'depth_mm'");
        }
        finally
        {
            File.Delete(path);
        }
    }

    public static IEnumerable<object[]> BadInvocations => new[]
    {
        new object[] { Array.Empty<string>() },
        new object[] { new[] { "--candidate", "a.json" } },
        new object[] { new[] { "--candidate", "a.json", "--output", "o", "--bogus", "1" } },
        new object[] { new[] { "--candidate", "a.json", "--candidate", "b.json", "--output", "o" } },
        new object[] { new[] { "--candidate", "a.json", "--output" } },
        new object[] { new[] { "--candidate", "a.json", "--output", "o", "--voxel-mm", "abc" } },
        new object[] { new[] { "--candidate", "a.json", "--output", "o", "--voxel-mm", "-0.1" } },
        new object[] { new[] { "--candidate", "a.json", "--output", "o", "--voxel-mm", "NaN" } },
        new object[] { new[] { "--candidate", "does-not-exist.json", "--output", "o" } },
    };

    [TestMethod]
    [DynamicData(nameof(BadInvocations))]
    public void BadInvocationsExitWithTwo(string[] args)
    {
        Assert.AreEqual(Program.UsageOrInputError, Program.Main(args));
    }

    [TestMethod]
    public void AnAnalyticRejectionPublishesNothingAndExplainsWhy()
    {
        string output = TestSupport.NewTempDir();
        try
        {
            Assert.AreEqual(Program.AcceptanceFailed, Program.Main(Args(output, "--voxel-mm", "0.2")));
            foreach (string name in Object001Package.OutputFiles)
            {
                Assert.IsFalse(File.Exists(Path.Combine(output, name)), name);
            }
            using JsonDocument report = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(output, Object001Package.RejectionReport)));
            Assert.AreEqual("REJECTED", report.RootElement.GetProperty("status").GetString());
            Assert.AreEqual("analytic", report.RootElement.GetProperty("rejected_at_stage").GetString());
            var failed = report.RootElement.GetProperty("acceptance").GetProperty("checks").EnumerateArray()
                .Where(c => !c.GetProperty("passed").GetBoolean()).Select(c => c.GetProperty("id").GetString()).ToList();
            CollectionAssert.AreEqual(new List<string?> { "feature_resolution" }, failed);
        }
        finally
        {
            Directory.Delete(output, recursive: true);
        }
    }

    [TestMethod]
    public void ExistingGeometryIsNeverOverwritten()
    {
        string output = TestSupport.NewTempDir();
        try
        {
            File.WriteAllText(Path.Combine(output, "body.stl"), "earlier geometry");
            Assert.AreEqual(Program.UsageOrInputError, Program.Main(Args(output)));
            Assert.AreEqual("earlier geometry", File.ReadAllText(Path.Combine(output, "body.stl")));
            Assert.IsFalse(File.Exists(Path.Combine(output, Object001Package.RejectionReport)));
        }
        finally
        {
            Directory.Delete(output, recursive: true);
        }
    }

    [TestMethod]
    public void WithoutTheNativeRuntimeTheProgramRefusesAndWritesNothing()
    {
        if (TestSupport.NativeRuntimeAvailable)
        {
            Assert.Inconclusive("the PicoGK native runtime is available here; NativeGenerationTests cover this platform");
        }
        string output = TestSupport.NewTempDir();
        try
        {
            Assert.AreEqual(Program.RuntimeUnavailable, Program.Main(Args(output)));
            Assert.AreEqual(0, Directory.EnumerateFileSystemEntries(output).Count());
        }
        finally
        {
            Directory.Delete(output, recursive: true);
        }
    }
}
