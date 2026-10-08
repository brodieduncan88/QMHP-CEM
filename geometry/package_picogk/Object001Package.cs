// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Object 001 — single-device readout/Purcell/package test article (spec §7.4), built with
// PicoGK 2.3.0 headless: a Library instance created directly, no viewer, no Library.Go.
//
// Required features (spec §7.4) and where they come from:
//   package outer body, chip recess, package/vacuum cavity  candidate parameters (§7.5)
//   removable lid                                           plate + plug, assumption A4
//   two opposing SMP-style launch bores                     candidate diameter, A5
//   mounting features                                       A6
//   simple thermal-path geometry                            A7
//   filter housing allowance                                A8 (reserved, not cut)
//   explicit chip datum, solver-domain bounding definition  ports.json, geometry_manifest.json
// Not modelled (spec §7.4): microscopic junctions, the thin-film circuit, the 17-qubit tile.
//
// Coordinate convention (spec §7.3), frozen: origin = centre of the chip's top surface,
// +X/+Y = chip plane, +Z = from chip toward the lid, unit = mm.
//
// Nothing is published unless every acceptance check passes. Outputs are written to a
// staging directory and moved into place only then, geometry_manifest.json last. A run
// that fails a check publishes no geometry and writes geometry_rejected.json instead.

using System.Numerics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using PicoGK;

namespace QmhpCem.Geometry;

/// <summary>Defects planted on purpose by negative-control tests. The CLI never sets one.</summary>
public enum PlantedDefect { None, OmitBoreP2, OmitMountingHole0, OmitThermalLand }

public sealed record GenerationOptions(
    double VoxelSizeMm = Object001Assumptions.DefaultVoxelSizeMm,
    PlantedDefect PlantedDefect = PlantedDefect.None);

public sealed record GenerationResult(bool Published, string OutputDir, IReadOnlyList<CheckResult> Checks, string ReportPath);

/// <summary>PicoGK's native runtime could not be loaded on this platform.</summary>
public sealed class PicoGkRuntimeUnavailableException(string message, Exception inner) : Exception(message, inner);

public static class Object001Package
{
    /// <summary>Pinned exactly in QmhpCem.Geometry.csproj (spec §13.2).</summary>
    public const string PicoGkPackageVersion = "2.3.0";
    public const string GeneratorRevision = "object001-picogk/1";
    public const string ManifestSchema = "qmhp-cem.object001-geometry-manifest/1";
    public const string PortsSchema = "qmhp-cem.object001-ports/1";
    public static readonly IReadOnlyList<string> OutputFiles = new[] { "body.stl", "lid.stl", "ports.json", "geometry_manifest.json" };
    public const string RejectionReport = "geometry_rejected.json";
    /// <summary>Where the parts of a rejected run are kept, as evidence of what failed. Never inputs.</summary>
    public const string RejectedDir = "rejected";
    static readonly string[] RejectedParts = { "body.stl", "lid.stl" };

    static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    /// <summary>
    /// Generate Object 001 into <paramref name="outputDir"/>. Throws InvalidDataException for
    /// an invalid candidate, IOException when an output already exists (geometry is never
    /// overwritten) and PicoGkRuntimeUnavailableException when the native runtime cannot load.
    /// </summary>
    public static GenerationResult Generate(Candidate candidate, string outputDir, GenerationOptions? options = null)
    {
        options ??= new GenerationOptions();
        double v = options.VoxelSizeMm;
        if (!double.IsFinite(v) || v <= 0)
        {
            throw new InvalidDataException($"voxel size must be a finite length greater than 0 mm, got {v}");
        }
        Object001Layout layout = Object001Layout.FromCandidate(candidate);

        Directory.CreateDirectory(outputDir);
        foreach (string name in OutputFiles.Append(RejectionReport).Append(RejectedDir))
        {
            if (File.Exists(Path.Combine(outputDir, name)) || Directory.Exists(Path.Combine(outputDir, name)))
            {
                throw new IOException($"{name} already exists in {outputDir}; geometry is never overwritten");
            }
        }

        var checks = new List<CheckResult>(layout.AnalyticChecks(v));
        if (checks.Any(c => !c.Passed))
        {
            // The layout itself is invalid: refuse before touching PicoGK.
            return Reject(candidate, layout, options, outputDir, checks, runtime: null, parts: null, "analytic", staging: null);
        }

        string staging = Path.Combine(outputDir, $".staging-{Guid.NewGuid():N}");
        Directory.CreateDirectory(staging);
        try
        {
            using Library lib = OpenLibrary(v);
            JsonObject runtime = new()
            {
                ["picogk_package_version"] = PicoGkPackageVersion,
                ["native_library"] = Library.strName(),
                ["native_version"] = Library.strVersion(),
                ["native_build"] = Library.strBuildInfo(),
                ["dotnet_runtime"] = RuntimeInformation.FrameworkDescription,
                ["os"] = RuntimeInformation.OSDescription,
                ["runtime_identifier"] = RuntimeInformation.RuntimeIdentifier,
            };

            using Voxels body = BuildBody(lib, layout, v, options.PlantedDefect);
            using Voxels lid = BuildLid(lib, layout, v, options.PlantedDefect);

            checks.AddRange(ProbeChecks(layout, v, body, lid));

            var parts = new JsonObject();
            var stl = new Dictionary<string, byte[]>();
            foreach ((string name, Voxels vox, double volume, double area, Box bounds) in new[]
            {
                ("body", body, layout.BodyVolumeExact, layout.BodyAreaExact, layout.BodyBoundsExact),
                ("lid", lid, layout.LidVolumeExact, layout.LidAreaExact, layout.LidBoundsExact),
            })
            {
                string path = Path.Combine(staging, $"{name}.stl");
                using (Mesh mesh = new(vox))
                {
                    mesh.SaveToStlFile(path, Mesh.EStlUnit.MM);
                }
                byte[] bytes = File.ReadAllBytes(path);
                stl[name] = bytes;
                StlReport report = StlCheck.Analyse(bytes);
                checks.AddRange(MeshChecks(name, report, volume, area, bounds, v));
                parts[name] = PartRecord(name, bytes, report, volume, area, bounds);
            }

            if (checks.Any(c => !c.Passed) || options.PlantedDefect != PlantedDefect.None)
            {
                return Reject(candidate, layout, options, outputDir, checks, runtime, parts, "geometric", staging);
            }

            byte[] ports = Serialize(PortsJson(candidate, layout));
            File.WriteAllBytes(Path.Combine(staging, "ports.json"), ports);
            JsonObject manifest = ManifestJson(candidate, layout, options, checks, runtime, parts, "PASSED");
            manifest["outputs_sha256"] = new JsonObject
            {
                ["body.stl"] = Sha256(stl["body"]),
                ["lid.stl"] = Sha256(stl["lid"]),
                ["ports.json"] = Sha256(ports),
            };
            File.WriteAllBytes(Path.Combine(staging, "geometry_manifest.json"), Serialize(manifest));

            // Publish: geometry first, the manifest last, so a manifest is never present
            // without the files it hashes. File.Move refuses to overwrite.
            foreach (string name in OutputFiles)
            {
                File.Move(Path.Combine(staging, name), Path.Combine(outputDir, name), overwrite: false);
            }
            return new GenerationResult(true, outputDir, checks, Path.Combine(outputDir, "geometry_manifest.json"));
        }
        finally
        {
            Directory.Delete(staging, recursive: true);
        }
    }

    static Library OpenLibrary(double voxelSizeMm)
    {
        try
        {
            return new Library((float)voxelSizeMm);
        }
        catch (Exception ex) when (ex is DllNotFoundException or EntryPointNotFoundException or BadImageFormatException
                                   || ex.InnerException is DllNotFoundException or EntryPointNotFoundException or BadImageFormatException)
        {
            throw new PicoGkRuntimeUnavailableException(
                $"the PicoGK {PicoGkPackageVersion} native runtime could not be loaded on {RuntimeInformation.RuntimeIdentifier} " +
                $"({RuntimeInformation.OSDescription}). PicoGK {PicoGkPackageVersion} ships native code only for osx-arm64 " +
                $"(macOS 26.5 or later) and win-x64. Object 001 geometry was NOT generated. {ex.Message}", ex);
        }
    }

    // --- construction ----------------------------------------------------------------------

    static Voxels BuildBody(Library lib, Object001Layout l, double v, PlantedDefect defect)
    {
        double over = Object001Assumptions.ToolOvershootVoxels * v;
        Voxels body = Solid(lib, l.BodyBlock, v);
        if (defect != PlantedDefect.OmitThermalLand)
        {
            // Overlap the land into the block so the two fuse into one solid.
            using Voxels land = Solid(lib, l.ThermalLand with { Max = l.ThermalLand.Max with { Z = l.ZBodyBottom + over } }, v);
            body.BoolAdd(land);
        }
        using (Voxels pocket = Solid(lib, l.Pocket with { Max = l.Pocket.Max with { Z = l.ZBodyTop + over } }, v))
        {
            body.BoolSubtract(pocket);
        }
        using (Voxels recess = Solid(lib, l.Recess with { Max = l.Recess.Max with { Z = l.ZCavityFloor + over } }, v))
        {
            body.BoolSubtract(recess);
        }
        for (int i = 0; i < l.Bores.Count; i++)
        {
            if (defect == PlantedDefect.OmitBoreP2 && i == 1)
            {
                continue;
            }
            AxisCylinder bore = l.Bores[i];
            // Overshoot through the outer face and into the (already empty) pocket.
            AxisCylinder tool = bore with { From = bore.From - over, To = bore.To + over };
            using Voxels cut = Solid(lib, tool, v);
            body.BoolSubtract(cut);
        }
        for (int i = 0; i < l.MountingHoles.Count; i++)
        {
            if (defect == PlantedDefect.OmitMountingHole0 && i == 0)
            {
                continue;
            }
            AxisCylinder hole = l.MountingHoles[i];
            using Voxels cut = Solid(lib, hole with { From = l.ZBodyBottom - over, To = l.ZBodyTop + over }, v);
            body.BoolSubtract(cut);
        }
        return body;
    }

    static Voxels BuildLid(Library lib, Object001Layout l, double v, PlantedDefect defect)
    {
        double over = Object001Assumptions.ToolOvershootVoxels * v;
        Voxels lid = Solid(lib, l.LidPlate, v);
        if (l.PlugHeight > 0)
        {
            using Voxels plug = Solid(lib, l.LidPlug with { Max = l.LidPlug.Max with { Z = l.ZBodyTop + over } }, v);
            lid.BoolAdd(plug);
        }
        for (int i = 0; i < l.MountingHoles.Count; i++)
        {
            if (defect == PlantedDefect.OmitMountingHole0 && i == 0)
            {
                continue;
            }
            AxisCylinder hole = l.MountingHoles[i];
            using Voxels cut = Solid(lib, hole with { From = l.ZBodyTop - over, To = l.ZLidTop + over }, v);
            lid.BoolSubtract(cut);
        }
        return lid;
    }

    static Voxels Solid(Library lib, Box box, double v) => new(lib, new BoxImplicit(box, PaddingFor(v)));

    static Voxels Solid(Library lib, AxisCylinder cylinder, double v) => new(lib, new CylinderImplicit(cylinder, PaddingFor(v)));

    /// <summary>
    /// PicoGK evaluates an implicit only inside its bounds, so the bounds are padded by three
    /// voxels to give the level set a correct band on the outside of every face.
    /// </summary>
    static float PaddingFor(double v) => (float)(3 * v);

    /// <summary>Exact signed distance to an axis-aligned box (negative inside).</summary>
    sealed class BoxImplicit(Box box, float pad) : IBoundedImplicit
    {
        readonly Vector3 centre = new((float)box.Centre.X, (float)box.Centre.Y, (float)box.Centre.Z);
        readonly Vector3 half = new((float)(box.SizeX / 2), (float)(box.SizeY / 2), (float)(box.SizeZ / 2));

        public BBox3 oBounds { get; } = new(
            new Vector3((float)box.Min.X - pad, (float)box.Min.Y - pad, (float)box.Min.Z - pad),
            new Vector3((float)box.Max.X + pad, (float)box.Max.Y + pad, (float)box.Max.Z + pad));

        public float fSignedDistance(in Vector3 p)
        {
            Vector3 q = Vector3.Abs(p - centre) - half;
            float outside = Vector3.Max(q, Vector3.Zero).Length();
            float inside = MathF.Min(MathF.Max(q.X, MathF.Max(q.Y, q.Z)), 0f);
            return outside + inside;
        }
    }

    /// <summary>Exact signed distance to a capped cylinder along X or Z (negative inside).</summary>
    sealed class CylinderImplicit(AxisCylinder c, float pad) : IBoundedImplicit
    {
        public BBox3 oBounds { get; } = new(
            new Vector3((float)c.Bounds.Min.X - pad, (float)c.Bounds.Min.Y - pad, (float)c.Bounds.Min.Z - pad),
            new Vector3((float)c.Bounds.Max.X + pad, (float)c.Bounds.Max.Y + pad, (float)c.Bounds.Max.Z + pad));

        public float fSignedDistance(in Vector3 p)
        {
            (float a, float u, float w) = c.Axis == CylinderAxis.X ? (p.X, p.Y, p.Z) : (p.Z, p.X, p.Y);
            float radial = MathF.Sqrt((u - (float)c.U) * (u - (float)c.U) + (w - (float)c.V) * (w - (float)c.V)) - (float)c.Radius;
            float axial = MathF.Max((float)c.From - a, a - (float)c.To);
            float outside = MathF.Sqrt(MathF.Max(radial, 0) * MathF.Max(radial, 0) + MathF.Max(axial, 0) * MathF.Max(axial, 0));
            float inside = MathF.Min(MathF.Max(radial, axial), 0);
            return outside + inside;
        }
    }

    // --- geometric checks --------------------------------------------------------------------

    static IEnumerable<CheckResult> ProbeChecks(Object001Layout layout, double v, Voxels body, Voxels lid)
    {
        IReadOnlyList<Probe> probes = layout.Probes(v);
        var failures = new Dictionary<string, List<string>>();
        var counts = new Dictionary<string, int>();
        foreach (Probe probe in probes)
        {
            var at = new Vector3((float)probe.Point.X, (float)probe.Point.Y, (float)probe.Point.Z);
            bool solid = probe.Part switch
            {
                "body" => body.bIsInside(at),
                "lid" => lid.bIsInside(at),
                _ => body.bIsInside(at) || lid.bIsInside(at),
            };
            counts[probe.Check] = counts.GetValueOrDefault(probe.Check) + 1;
            if (solid != probe.ExpectSolid)
            {
                failures.TryAdd(probe.Check, new List<string>());
                failures[probe.Check].Add(
                    $"{probe.Label} ({probe.Part}) at ({probe.Point.X:R}, {probe.Point.Y:R}, {probe.Point.Z:R}) is " +
                    $"{(solid ? "solid" : "void")}, expected {(probe.ExpectSolid ? "solid" : "void")}");
            }
        }
        foreach ((string check, int n) in counts.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            bool ok = !failures.TryGetValue(check, out List<string>? bad);
            yield return new CheckResult(
                $"probes:{check}", "§7.6", $"Point-membership probes of the voxel parts for '{check}'.", ok,
                ok ? $"{n} probes, all as predicted"
                   : $"{bad!.Count} of {n} probes wrong; first: {string.Join(" | ", bad.Take(3))}");
        }
    }

    static IEnumerable<CheckResult> MeshChecks(string part, StlReport r, double exactVolume, double exactArea, Box exactBounds, double v)
    {
        yield return new CheckResult($"{part}:watertight", "§7.6",
            $"The exported {part}.stl is closed, 2-manifold and consistently outward-oriented (read back from the file).",
            r.Watertight,
            $"{r.Triangles} triangles, {r.Vertices} welded vertices, {r.DegenerateTriangles} degenerate, " +
            $"{r.BoundaryEdges} boundary edges, {r.OverusedEdges} over-used edges, signed volume {r.SignedVolumeMm3:R} mm^3");
        yield return new CheckResult($"{part}:single_solid", "§7.6",
            $"{part}.stl is one connected solid.", r.Components == 1, $"{r.Components} connected component(s)");

        // Derived bound, fixed before any run: the meshed surface of a voxel model lies within
        // half a voxel of each true face, so the enclosed volume differs from the exact one by
        // at most area x voxel / 2. That catches a missing pocket, recess, plug or land; small
        // features (bores, holes) are checked by the probes, not by volume. The measured
        // difference is recorded so the bound can be tightened on evidence.
        double tolerance = exactArea * v / 2;
        double error = r.SignedVolumeMm3 - exactVolume;
        yield return new CheckResult($"{part}:volume", "§7.6",
            $"Volume enclosed by {part}.stl matches the exact layout volume within area x voxel / 2.",
            Math.Abs(error) <= tolerance,
            $"STL {r.SignedVolumeMm3:R} mm^3, exact {exactVolume:R} mm^3, difference {error:R} mm^3, tolerance {tolerance:R} mm^3");

        double worst = new[]
        {
            Math.Abs(r.Min.X - exactBounds.Min.X), Math.Abs(r.Min.Y - exactBounds.Min.Y), Math.Abs(r.Min.Z - exactBounds.Min.Z),
            Math.Abs(r.Max.X - exactBounds.Max.X), Math.Abs(r.Max.Y - exactBounds.Max.Y), Math.Abs(r.Max.Z - exactBounds.Max.Z),
        }.Max();
        yield return new CheckResult($"{part}:bounds", "§7.6",
            $"Bounding box of {part}.stl matches the exact layout bounds within one voxel on every face.",
            worst <= v,
            $"largest face offset {worst:R} mm, tolerance {v:R} mm");
    }

    // --- records -----------------------------------------------------------------------------

    static GenerationResult Reject(Candidate candidate, Object001Layout layout, GenerationOptions options, string outputDir,
        List<CheckResult> checks, JsonObject? runtime, JsonObject? parts, string stage, string? staging)
    {
        JsonObject report = ManifestJson(candidate, layout, options, checks, runtime, parts, "REJECTED");
        report["rejected_at_stage"] = stage;
        report["published"] = false;
        report["note"] = "No geometry was published: body.stl, lid.stl, ports.json and geometry_manifest.json are absent by design. " +
                         "Parts built before the rejection are kept under rejected/ as evidence of what failed; they are not outputs.";
        var kept = new JsonObject();
        if (staging is not null)
        {
            // Raw evidence survives the rejection (CLAUDE.md §4): keep the failed parts, renamed
            // so nothing that reads outputs can mistake them for geometry.
            string rejected = Path.Combine(outputDir, RejectedDir);
            foreach (string part in RejectedParts.Where(n => File.Exists(Path.Combine(staging, n))))
            {
                Directory.CreateDirectory(rejected);
                string target = Path.Combine(rejected, Path.GetFileNameWithoutExtension(part) + ".rejected.stl");
                File.Move(Path.Combine(staging, part), target, overwrite: false);
                kept[$"{RejectedDir}/{Path.GetFileName(target)}"] = Sha256(File.ReadAllBytes(target));
            }
        }
        report["rejected_parts_sha256"] = kept;
        string path = Path.Combine(outputDir, RejectionReport);
        using (FileStream f = new(path, FileMode.CreateNew, FileAccess.Write))
        {
            f.Write(Serialize(report));
        }
        return new GenerationResult(false, outputDir, checks, path);
    }

    static JsonObject ManifestJson(Candidate candidate, Object001Layout l, GenerationOptions options, List<CheckResult> checks,
        JsonObject? runtime, JsonObject? parts, string status)
    {
        return new JsonObject
        {
            ["schema"] = ManifestSchema,
            ["status"] = status,
            ["generator"] = new JsonObject
            {
                ["name"] = "QmhpCem.Geometry",
                ["revision"] = GeneratorRevision,
                ["picogk_package_version"] = PicoGkPackageVersion,
                ["shapekernel"] = "not used",
                ["runtime"] = runtime?.DeepClone(),
                ["voxel_size_mm"] = options.VoxelSizeMm,
                ["planted_defect"] = options.PlantedDefect == PlantedDefect.None ? null : options.PlantedDefect.ToString(),
            },
            ["candidate"] = new JsonObject
            {
                ["candidate_id"] = candidate.CandidateId,
                ["object_type"] = candidate.ObjectType,
                ["candidate_json_sha256"] = candidate.SourceSha256,
                ["master_revision"] = candidate.MasterRevision,
            },
            ["classification"] = "ENGINEERING-SEED",
            ["classification_note"] = "Every dimension is a QMHP-CEM bootstrap assumption (spec §7.5), not a validated QMHP hardware dimension.",
            ["frame"] = Frame(),
            ["generator_assumptions"] = new JsonArray(Object001Assumptions.All.Select(a => (JsonNode)new JsonObject
            {
                ["id"] = a.Id,
                ["statement"] = a.Statement,
                ["rationale"] = a.Rationale,
                ["classification"] = "ENGINEERING-SEED",
            }).ToArray()),
            ["layout_mm"] = new JsonObject
            {
                ["z_chip_top"] = l.ZChipTop,
                ["z_chip_bottom"] = l.ZChipBottom,
                ["z_recess_floor"] = l.ZRecessFloor,
                ["z_cavity_floor"] = l.ZCavityFloor,
                ["z_cavity_ceiling"] = l.ZCavityCeiling,
                ["z_body_bottom"] = l.ZBodyBottom,
                ["z_body_top"] = l.ZBodyTop,
                ["z_lid_top"] = l.ZLidTop,
                ["z_thermal_land_bottom"] = l.ZLandBottom,
                ["z_bore_axis"] = l.ZBoreAxis,
                ["lid_plug_height"] = l.PlugHeight,
                ["body_block"] = BoxJson(l.BodyBlock),
                ["thermal_land"] = BoxJson(l.ThermalLand),
                ["pocket"] = BoxJson(l.Pocket),
                ["chip_recess"] = BoxJson(l.Recess),
                ["lid_plate"] = BoxJson(l.LidPlate),
                ["lid_plug"] = l.PlugHeight > 0 ? BoxJson(l.LidPlug) : null,
                ["filter_housing_allowance"] = BoxJson(l.FilterAllowance),
                ["launch_bores"] = new JsonArray(l.Bores.Select(b => (JsonNode)CylinderJson(b)).ToArray()),
                ["mounting_holes"] = new JsonArray(l.MountingHoles.Select(h => (JsonNode)CylinderJson(h)).ToArray()),
            },
            ["chip_datum"] = ChipDatum(l),
            ["solver_domain"] = SolverDomain(l),
            ["parts"] = parts?.DeepClone(),
            ["acceptance"] = new JsonObject
            {
                ["all_passed"] = checks.All(c => c.Passed),
                ["checks"] = new JsonArray(checks.Select(c => (JsonNode)new JsonObject
                {
                    ["id"] = c.Id,
                    ["spec"] = c.Spec,
                    ["description"] = c.Description,
                    ["passed"] = c.Passed,
                    ["detail"] = c.Detail,
                }).ToArray()),
            },
        };
    }

    static JsonObject PortsJson(Candidate candidate, Object001Layout l)
    {
        JsonObject Port(string id, AxisCylinder bore, int side)
        {
            double face = side * l.Ox;
            return new JsonObject
            {
                ["id"] = id,
                ["kind"] = "SMP-style launch bore (ENGINEERING-SEED, assumption A5)",
                ["side"] = side < 0 ? "-X" : "+X",
                ["port_plane_x_mm"] = face,
                ["port_plane_centre_mm"] = new JsonArray(face, 0.0, l.ZBoreAxis),
                ["inward_normal"] = new JsonArray(-side * 1.0, 0.0, 0.0),
                ["bore_diameter_mm"] = 2 * bore.Radius,
                ["bore_axis_z_mm"] = l.ZBoreAxis,
                ["bore_length_mm"] = bore.Length,
                ["aperture_plane_x_mm"] = side * l.Cx,
                ["aperture_into_cavity_z_mm"] = new JsonArray(l.ZCavityFloor, l.ZCavityFloor + l.BoreApertureHeight),
                ["opens_into"] = "vacuum_cavity",
            };
        }
        return new JsonObject
        {
            ["schema"] = PortsSchema,
            ["candidate_id"] = candidate.CandidateId,
            ["frame"] = Frame(),
            ["ports"] = new JsonArray(Port("P1", l.Bores[0], -1), Port("P2", l.Bores[1], +1)),
            ["chip_datum"] = ChipDatum(l),
        };
    }

    static JsonObject PartRecord(string name, byte[] stl, StlReport r, double exactVolume, double exactArea, Box exactBounds) => new()
    {
        ["file"] = $"{name}.stl",
        ["sha256"] = Sha256(stl),
        ["bytes"] = stl.Length,
        ["stl_header"] = r.Header,
        ["triangles"] = r.Triangles,
        ["welded_vertices"] = r.Vertices,
        ["watertight"] = r.Watertight,
        ["components"] = r.Components,
        ["volume_mm3_stl"] = r.SignedVolumeMm3,
        ["volume_mm3_exact"] = exactVolume,
        ["area_mm2_exact"] = exactArea,
        ["bounds_mm_stl"] = BoxJson(new Box(r.Min, r.Max)),
        ["bounds_mm_exact"] = BoxJson(exactBounds),
    };

    static JsonObject Frame() => new()
    {
        ["origin"] = "centre of top surface of chip substrate",
        ["x_y"] = "chip plane",
        ["z_axis"] = "+Z = from chip toward package lid",
        ["unit"] = "mm",
    };

    static JsonObject ChipDatum(Object001Layout l) => new()
    {
        ["origin_mm"] = new JsonArray(0.0, 0.0, 0.0),
        ["chip_top_z_mm"] = l.ZChipTop,
        ["chip_box_mm"] = BoxJson(l.Chip),
        ["chip_seat"] = "recess floor (assumption A1)",
    };

    static JsonObject SolverDomain(Object001Layout l)
    {
        var regions = new JsonArray
        {
            new JsonObject { ["name"] = "vacuum_cavity", ["box_mm"] = BoxJson(l.VacuumCavity) },
            new JsonObject { ["name"] = "chip_recess", ["box_mm"] = BoxJson(l.Recess) },
            new JsonObject { ["name"] = "launch_bore_P1", ["cylinder_mm"] = CylinderJson(l.Bores[0]) },
            new JsonObject { ["name"] = "launch_bore_P2", ["cylinder_mm"] = CylinderJson(l.Bores[1]) },
        };
        double zTop = Math.Max(l.ZCavityCeiling, l.ZBoreAxis + l.BoreRadius);
        return new JsonObject
        {
            ["definition"] = "The void of the assembled body and lid that the launch ports open into: the vacuum cavity, " +
                             "the chip recess and the two launch bores, bounded by package metal and closed by the port planes. " +
                             "The chip occupies part of the recess as a dielectric; PicoGK does not model it.",
            ["regions"] = regions,
            ["dielectric_regions"] = new JsonArray(new JsonObject { ["name"] = "chip_substrate", ["box_mm"] = BoxJson(l.Chip) }),
            ["bounding_box_mm"] = BoxJson(new Box(new Vec3(-l.Ox, -l.Cy, l.ZRecessFloor), new Vec3(l.Ox, l.Cy, zTop))),
            ["port_planes_x_mm"] = new JsonArray(-l.Ox, l.Ox),
        };
    }

    static JsonObject BoxJson(Box b) => new()
    {
        ["min"] = new JsonArray(b.Min.X, b.Min.Y, b.Min.Z),
        ["max"] = new JsonArray(b.Max.X, b.Max.Y, b.Max.Z),
    };

    static JsonObject CylinderJson(AxisCylinder c) => new()
    {
        ["axis"] = c.Axis == CylinderAxis.X ? "X" : "Z",
        ["start"] = new JsonArray(c.OnAxis(c.From).X, c.OnAxis(c.From).Y, c.OnAxis(c.From).Z),
        ["end"] = new JsonArray(c.OnAxis(c.To).X, c.OnAxis(c.To).Y, c.OnAxis(c.To).Z),
        ["radius"] = c.Radius,
    };

    static byte[] Serialize(JsonNode node)
    {
        string text = node.ToJsonString(Indented) + "\n";
        return System.Text.Encoding.UTF8.GetBytes(text);
    }

    static string Sha256(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
}
