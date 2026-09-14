// QMHP-CEM Object 001 geometry entry point (spec §7.2, §7.4).
//
// File-based boundary, deliberately thin:
//   input:   candidate.json
//   outputs: body.stl, lid.stl, ports.json, geometry_manifest.json
//
// STATUS: NOT IMPLEMENTED in v0.1. This project defines the boundary, the CLI
// contract and the acceptance checks; the PicoGK voxel construction itself is
// the first implementation task.

using System.Text.Json;

namespace QmhpCem.Geometry;

public static class Program
{
    public static int Main(string[] args)
    {
        string? candidatePath = null;
        string? outputDir = null;

        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--candidate") candidatePath = args[i + 1];
            if (args[i] == "--output") outputDir = args[i + 1];
        }

        if (candidatePath is null || outputDir is null)
        {
            Console.Error.WriteLine(
                "usage: QmhpCem.Geometry --candidate <candidate.json> --output <dir>");
            return 2;
        }

        if (!File.Exists(candidatePath))
        {
            Console.Error.WriteLine($"candidate file not found: {candidatePath}");
            return 2;
        }

        Candidate candidate;
        try
        {
            candidate = Candidate.Load(candidatePath);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"failed to read candidate: {ex.Message}");
            return 2;
        }

        Console.Error.WriteLine(
            $"QMHP-CEM Object 001 geometry generation is NOT IMPLEMENTED in v0.1 " +
            $"(spec §7.2/§7.4). Candidate {candidate.CandidateId} was read and " +
            $"validated, but no geometry was produced. Implement " +
            $"Object001Package.Generate() against PicoGK 2.3.0. " +
            $"No placeholder STL is written: fabricating geometry would put " +
            $"un-simulated artifacts into the append-only results tree.");

        return 3; // distinct from 2 (usage) and 0 (success)
    }
}

/// <summary>Minimal view of candidate.json needed by the geometry generator.</summary>
public sealed record Candidate(string CandidateId, string ObjectType, JsonElement Parameters)
{
    public static Candidate Load(string path)
    {
        using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(path));
        JsonElement root = doc.RootElement;

        string id = root.GetProperty("candidate_id").GetString()
            ?? throw new InvalidDataException("candidate_id is missing");
        string objectType = root.GetProperty("object_type").GetString()
            ?? throw new InvalidDataException("object_type is missing");

        if (objectType != "object001_single_device_package")
        {
            throw new InvalidDataException(
                $"unsupported object_type '{objectType}'; v0.1 implements only " +
                "object001_single_device_package");
        }

        // Clone so the element outlives the JsonDocument.
        JsonElement parameters = root.GetProperty("parameters").Clone();
        return new Candidate(id, objectType, parameters);
    }
}
