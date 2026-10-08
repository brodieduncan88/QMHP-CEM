// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// QMHP-CEM Object 001 geometry entry point (spec §7.2, §7.4).
//
// File-based boundary, deliberately thin:
//   input:   candidate.json
//   outputs: body.stl, lid.stl, ports.json, geometry_manifest.json
//
//   QmhpCem.Geometry --candidate <candidate.json> --output <dir> [--voxel-mm <size>]
//
// Exit codes:
//   0  geometry generated; every acceptance check passed; the four outputs are published
//   2  usage or input error (arguments, candidate file, parameters, an existing output)
//   4  an acceptance check failed; nothing published; geometry_rejected.json says which
//   5  the PicoGK native runtime cannot load on this platform; nothing written
//   6  unexpected internal error; nothing published
//
// PicoGK 2.3.0 ships native code only for osx-arm64 (macOS 26.5 or later) and win-x64,
// so on Linux this program refuses with exit code 5 rather than fabricating geometry.

using System.Security.Cryptography;
using System.Text.Json;

namespace QmhpCem.Geometry;

public static class Program
{
    public const int Ok = 0;
    public const int UsageOrInputError = 2;
    public const int AcceptanceFailed = 4;
    public const int RuntimeUnavailable = 5;
    public const int InternalError = 6;

    public static int Main(string[] args)
    {
        string? candidatePath = null;
        string? outputDir = null;
        double voxelMm = Object001Assumptions.DefaultVoxelSizeMm;

        for (int i = 0; i < args.Length; i += 2)
        {
            if (i + 1 >= args.Length)
            {
                return Usage($"option {args[i]} has no value");
            }
            switch (args[i])
            {
                case "--candidate" when candidatePath is null:
                    candidatePath = args[i + 1];
                    break;
                case "--output" when outputDir is null:
                    outputDir = args[i + 1];
                    break;
                case "--voxel-mm":
                    if (!double.TryParse(args[i + 1], System.Globalization.NumberStyles.Float,
                            System.Globalization.CultureInfo.InvariantCulture, out voxelMm)
                        || !double.IsFinite(voxelMm) || voxelMm <= 0)
                    {
                        return Usage($"--voxel-mm must be a finite size greater than 0, got '{args[i + 1]}'");
                    }
                    break;
                default:
                    return Usage($"unknown or repeated option {args[i]}");
            }
        }

        if (candidatePath is null || outputDir is null)
        {
            return Usage("--candidate and --output are required");
        }

        if (!File.Exists(candidatePath))
        {
            Console.Error.WriteLine($"candidate file not found: {candidatePath}");
            return UsageOrInputError;
        }

        Candidate candidate;
        try
        {
            candidate = Candidate.Load(candidatePath);
        }
        catch (Exception ex) when (ex is JsonException or InvalidDataException or KeyNotFoundException or InvalidOperationException)
        {
            Console.Error.WriteLine($"failed to read candidate: {ex.Message}");
            return UsageOrInputError;
        }

        try
        {
            GenerationResult result = Object001Package.Generate(candidate, outputDir, new GenerationOptions(voxelMm));
            if (!result.Published)
            {
                foreach (CheckResult failed in result.Checks.Where(c => !c.Passed))
                {
                    Console.Error.WriteLine($"FAILED {failed.Id}: {failed.Detail}");
                }
                Console.Error.WriteLine(
                    $"Object 001 geometry for {candidate.CandidateId} was REJECTED and nothing was published; " +
                    $"see {result.ReportPath}");
                return AcceptanceFailed;
            }
            Console.Error.WriteLine(
                $"Object 001 geometry for {candidate.CandidateId} generated; " +
                $"{result.Checks.Count} acceptance checks passed; manifest {result.ReportPath}");
            return Ok;
        }
        catch (InvalidDataException ex)
        {
            Console.Error.WriteLine($"invalid candidate parameters: {ex.Message}");
            return UsageOrInputError;
        }
        catch (KeyNotFoundException ex)
        {
            Console.Error.WriteLine($"invalid candidate parameters: {ex.Message}");
            return UsageOrInputError;
        }
        catch (IOException ex) when (ex is not FileNotFoundException and not DirectoryNotFoundException)
        {
            Console.Error.WriteLine($"refused: {ex.Message}");
            return UsageOrInputError;
        }
        catch (PicoGkRuntimeUnavailableException ex)
        {
            Console.Error.WriteLine(ex.Message);
            return RuntimeUnavailable;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"internal error, nothing published: {ex}");
            return InternalError;
        }
    }

    static int Usage(string problem)
    {
        Console.Error.WriteLine(problem);
        Console.Error.WriteLine(
            "usage: QmhpCem.Geometry --candidate <candidate.json> --output <dir> [--voxel-mm <size>]");
        return UsageOrInputError;
    }
}

/// <summary>Minimal view of candidate.json needed by the geometry generator.</summary>
public sealed record Candidate(
    string CandidateId,
    string ObjectType,
    JsonElement Parameters,
    string? SourceSha256 = null,
    string? MasterRevision = null)
{
    public static Candidate Load(string path)
    {
        byte[] bytes = File.ReadAllBytes(path);
        using JsonDocument doc = JsonDocument.Parse(bytes);
        JsonElement root = doc.RootElement;
        RefuseDuplicateKeys(root, "$");

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

        string? master = root.TryGetProperty("master_revision", out JsonElement m) && m.ValueKind == JsonValueKind.String
            ? m.GetString()
            : null;

        // Clone so the element outlives the JsonDocument.
        JsonElement parameters = root.GetProperty("parameters").Clone();
        string sha = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        return new Candidate(id, objectType, parameters, sha, master);
    }

    static void RefuseDuplicateKeys(JsonElement element, string where)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (!seen.Add(property.Name))
                {
                    throw new InvalidDataException($"duplicate key '{property.Name}' in {where}");
                }
                RefuseDuplicateKeys(property.Value, $"{where}.{property.Name}");
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            int i = 0;
            foreach (JsonElement item in element.EnumerateArray())
            {
                RefuseDuplicateKeys(item, $"{where}[{i++}]");
            }
        }
    }
}
