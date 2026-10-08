// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.

using System.Text.Json.Nodes;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

internal static class TestSupport
{
    /// <summary>The repository checkout these tests were built from.</summary>
    public static string RepoRoot { get; } = FindRepoRoot();

    /// <summary>
    /// The seed candidate exactly as the Python driver writes it
    /// (tests/test_geometry.py asserts the two stay identical).
    /// </summary>
    public static string SeedFixture =>
        Path.Combine(RepoRoot, "geometry", "package_picogk", "tests", "fixtures", "object001_seed.candidate.json");

    public static Candidate SeedCandidate() => Candidate.Load(SeedFixture);

    /// <summary>The seed candidate with its parameters edited, round-tripped through a file.</summary>
    public static Candidate Edited(Action<JsonObject> editParameters)
    {
        JsonObject root = JsonNode.Parse(File.ReadAllText(SeedFixture))!.AsObject();
        editParameters(root["parameters"]!.AsObject());
        string path = Path.Combine(Path.GetTempPath(), $"qmhp-cem-candidate-{Guid.NewGuid():N}.json");
        File.WriteAllText(path, root.ToJsonString());
        try
        {
            return Candidate.Load(path);
        }
        finally
        {
            File.Delete(path);
        }
    }

    public static string NewTempDir()
    {
        string dir = Path.Combine(Path.GetTempPath(), $"qmhp-cem-geometry-{Guid.NewGuid():N}");
        Directory.CreateDirectory(dir);
        return dir;
    }

    static readonly Lazy<string?> RuntimeProblem = new(() =>
    {
        try
        {
            using var lib = new PicoGK.Library(0.1f);
            return null;
        }
        catch (Exception ex) when (ex is DllNotFoundException or EntryPointNotFoundException or BadImageFormatException)
        {
            return ex.Message.Split('\n')[0].Trim();   // the loader's first line names the library
        }
    });

    public static bool NativeRuntimeAvailable => RuntimeProblem.Value is null;

    /// <summary>
    /// Native tests need PicoGK's native runtime (osx-arm64 on macOS 26.5+, or win-x64).
    /// Elsewhere they are inconclusive, never passed; where CI sets
    /// QMHP_REQUIRE_PICOGK_RUNTIME=1 a missing runtime is a failure.
    /// </summary>
    public static void RequireNativeRuntime()
    {
        if (RuntimeProblem.Value is string problem)
        {
            if (Environment.GetEnvironmentVariable("QMHP_REQUIRE_PICOGK_RUNTIME") == "1")
            {
                Assert.Fail($"QMHP_REQUIRE_PICOGK_RUNTIME=1 but the PicoGK native runtime did not load: {problem}");
            }
            Assert.Inconclusive($"PicoGK native runtime unavailable on this platform: {problem}");
        }
    }

    static string FindRepoRoot()
    {
        for (DirectoryInfo? dir = new(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            if (File.Exists(Path.Combine(dir.FullName, "geometry", "package_picogk", "QmhpCem.Geometry.csproj")))
            {
                return dir.FullName;
            }
        }
        throw new InvalidOperationException($"no repository root above {AppContext.BaseDirectory}");
    }
}
