// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Object 001 package layout (spec §7.3-§7.6). Pure C#: no PicoGK call. The layout, its
// exact volumes and areas, the analytic acceptance checks and the probe points therefore
// run and are tested on every platform, including Linux, where PicoGK 2.3.0 ships no
// native runtime.
//
// Every dimension is ENGINEERING-SEED (spec §7.5). The candidate fixes 16 numbers; the
// stack-up and the features the spec names but does not dimension are generator
// assumptions, listed in Object001Assumptions and written into geometry_manifest.json.

using System.Text.Json;

namespace QmhpCem.Geometry;

/// <summary>A point in the frozen frame (spec §7.3), in millimetres.</summary>
public readonly record struct Vec3(double X, double Y, double Z);

/// <summary>An axis-aligned box, closed. Min does not exceed Max on any axis.</summary>
public readonly record struct Box(Vec3 Min, Vec3 Max)
{
    public double SizeX => Max.X - Min.X;
    public double SizeY => Max.Y - Min.Y;
    public double SizeZ => Max.Z - Min.Z;
    public double Volume => SizeX * SizeY * SizeZ;
    public Vec3 Centre => new((Min.X + Max.X) / 2, (Min.Y + Max.Y) / 2, (Min.Z + Max.Z) / 2);

    public bool Contains(Vec3 p) =>
        p.X >= Min.X && p.X <= Max.X && p.Y >= Min.Y && p.Y <= Max.Y && p.Z >= Min.Z && p.Z <= Max.Z;

    public Box Grow(double d) =>
        new(new Vec3(Min.X - d, Min.Y - d, Min.Z - d), new Vec3(Max.X + d, Max.Y + d, Max.Z + d));

    /// <summary>Distance in the XY plane from a point to this box's footprint (0 inside).</summary>
    public double XyDistanceTo(double x, double y)
    {
        double dx = Math.Max(Math.Max(Min.X - x, x - Max.X), 0);
        double dy = Math.Max(Math.Max(Min.Y - y, y - Max.Y), 0);
        return Math.Sqrt(dx * dx + dy * dy);
    }
}

public enum CylinderAxis { X, Z }

/// <summary>
/// A right circular cylinder with its axis parallel to X or Z. For an X cylinder the axis
/// passes through (y, z) = (U, V) and runs from x = From to x = To; for a Z cylinder it
/// passes through (x, y) = (U, V) and runs from z = From to z = To.
/// </summary>
public readonly record struct AxisCylinder(CylinderAxis Axis, double U, double V, double From, double To, double Radius)
{
    public double Length => To - From;
    public double Volume => Math.PI * Radius * Radius * Length;

    public Vec3 OnAxis(double a) => Axis == CylinderAxis.X ? new Vec3(a, U, V) : new Vec3(U, V, a);

    public bool Contains(Vec3 p)
    {
        (double a, double u, double v) = Axis == CylinderAxis.X ? (p.X, p.Y, p.Z) : (p.Z, p.X, p.Y);
        return a >= From && a <= To && (u - U) * (u - U) + (v - V) * (v - V) <= Radius * Radius;
    }

    public Box Bounds => Axis == CylinderAxis.X
        ? new Box(new Vec3(From, U - Radius, V - Radius), new Vec3(To, U + Radius, V + Radius))
        : new Box(new Vec3(U - Radius, V - Radius, From), new Vec3(U + Radius, V + Radius, To));
}

/// <summary>The candidate's Object 001 parameters (contracts/candidate.py), parsed strictly.</summary>
public sealed record Object001Parameters(
    double ChipWidthMm, double ChipHeightMm, double ChipThicknessMm,
    double PackageOuterWidthMm, double PackageOuterHeightMm, double BodyHeightMm, double FloorThicknessMm,
    double RecessXyClearanceMm, double RecessDepthMm,
    double CavityWidthMm, double CavityHeightMm, double CavityHeightAboveChipMm,
    double LidThicknessMm,
    double BoreDiameterMm, int LaunchCount,
    int MountingHoleCount)
{
    static readonly string[] Sections =
        { "chip", "package", "chip_recess", "vacuum_cavity", "lid", "launches", "mounting" };

    /// <summary>
    /// Parse candidate.json "parameters". Refuses a missing or unknown key, a duplicate key,
    /// a non-numeric, non-finite, zero or negative length, and a launch or mounting-hole
    /// count this generator does not build.
    /// </summary>
    public static Object001Parameters FromJson(JsonElement parameters)
    {
        RequireExactKeys(parameters, "parameters", Sections);
        JsonElement chip = Section(parameters, "chip", "width_mm", "height_mm", "thickness_mm");
        JsonElement pkg = Section(parameters, "package",
            "outer_width_mm", "outer_height_mm", "body_height_mm", "floor_thickness_mm");
        JsonElement recess = Section(parameters, "chip_recess", "xy_clearance_mm", "depth_mm");
        JsonElement cavity = Section(parameters, "vacuum_cavity", "width_mm", "height_mm", "height_above_chip_mm");
        JsonElement lid = Section(parameters, "lid", "thickness_mm");
        JsonElement launches = Section(parameters, "launches", "bore_diameter_mm", "count");
        JsonElement mounting = Section(parameters, "mounting", "hole_count");

        int launchCount = Count(launches, "launches", "count");
        if (launchCount != Object001Assumptions.SupportedLaunchCount)
        {
            throw new InvalidDataException(
                $"launches.count = {launchCount}: this generator builds exactly " +
                $"{Object001Assumptions.SupportedLaunchCount} opposing launches (spec §7.4)");
        }
        int holeCount = Count(mounting, "mounting", "hole_count");
        if (holeCount != Object001Assumptions.SupportedMountingHoleCount)
        {
            throw new InvalidDataException(
                $"mounting.hole_count = {holeCount}: this generator builds exactly " +
                $"{Object001Assumptions.SupportedMountingHoleCount} corner mounting holes");
        }

        return new Object001Parameters(
            Length(chip, "chip", "width_mm"), Length(chip, "chip", "height_mm"), Length(chip, "chip", "thickness_mm"),
            Length(pkg, "package", "outer_width_mm"), Length(pkg, "package", "outer_height_mm"),
            Length(pkg, "package", "body_height_mm"), Length(pkg, "package", "floor_thickness_mm"),
            Length(recess, "chip_recess", "xy_clearance_mm"), Length(recess, "chip_recess", "depth_mm"),
            Length(cavity, "vacuum_cavity", "width_mm"), Length(cavity, "vacuum_cavity", "height_mm"),
            Length(cavity, "vacuum_cavity", "height_above_chip_mm"),
            Length(lid, "lid", "thickness_mm"),
            Length(launches, "launches", "bore_diameter_mm"), launchCount,
            holeCount);
    }

    static JsonElement Section(JsonElement parameters, string name, params string[] keys)
    {
        JsonElement section = parameters.GetProperty(name);
        RequireExactKeys(section, $"parameters.{name}", keys);
        return section;
    }

    static void RequireExactKeys(JsonElement element, string where, string[] keys)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException($"{where} is not an object");
        }
        List<string> present = element.EnumerateObject().Select(p => p.Name).ToList();
        if (present.Count != present.Distinct(StringComparer.Ordinal).Count())
        {
            throw new InvalidDataException($"{where} has a duplicate key");
        }
        string[] missing = keys.Except(present, StringComparer.Ordinal).ToArray();
        string[] unknown = present.Except(keys, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0 || unknown.Length > 0)
        {
            throw new InvalidDataException(
                $"{where}: missing [{string.Join(", ", missing)}], unknown [{string.Join(", ", unknown)}]");
        }
    }

    static double Length(JsonElement section, string where, string key)
    {
        JsonElement value = section.GetProperty(key);
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetDouble(out double mm)
            || !double.IsFinite(mm) || mm <= 0)
        {
            throw new InvalidDataException(
                $"parameters.{where}.{key} must be a finite length greater than 0 mm, got {value.GetRawText()}");
        }
        return mm;
    }

    static int Count(JsonElement section, string where, string key)
    {
        JsonElement value = section.GetProperty(key);
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetInt32(out int n))
        {
            throw new InvalidDataException($"parameters.{where}.{key} must be an integer, got {value.GetRawText()}");
        }
        return n;
    }
}

/// <summary>A generator assumption: a dimension or rule the candidate does not fix.</summary>
public sealed record Assumption(string Id, string Statement, string Rationale);

/// <summary>
/// ENGINEERING-SEED assumptions introduced by this generator, because the frozen Master and
/// the §7.5 seed do not define them. None is a validated QMHP hardware dimension. Each is
/// recorded in geometry_manifest.json; changing one changes the geometry and must be
/// recorded as a new generator revision.
/// </summary>
public static class Object001Assumptions
{
    public const int SupportedLaunchCount = 2;
    public const int SupportedMountingHoleCount = 4;
    /// <summary>M2 clearance.</summary>
    public const double MountingHoleDiameterMm = 2.2;
    public const double ThermalLandHeightMm = 0.5;
    public const double FilterAllowanceLengthMm = 12.0;
    public const double FilterAllowanceMarginMm = 0.5;
    /// <summary>ENGINEERING-RULE. The coarsest size that resolves the seed's 0.45 mm recess with 4 voxels.</summary>
    public const double DefaultVoxelSizeMm = 0.1;
    /// <summary>ENGINEERING-RULE. Every wall, feature and margin must span at least this many voxels.</summary>
    public const double MinimumFeatureVoxels = 4.0;
    /// <summary>Cutting tools overshoot the faces they open by this many voxels.</summary>
    public const double ToolOvershootVoxels = 2.0;

    public static readonly IReadOnlyList<Assumption> All = new Assumption[]
    {
        new("A1", "The chip rests on the recess floor: recess floor z = -chip thickness.",
            "The seed gives the recess depth and the chip thickness but not the seat."),
        new("A2", "The vacuum-cavity ceiling is at z = vacuum_cavity.height_above_chip_mm, measured from the chip-top datum (spec §7.3).",
            "Reads the parameter name literally."),
        new("A3", "package.floor_thickness_mm is solid material below the recess floor; the body spans z = recess floor - floor thickness to that + body_height_mm.",
            "Matches contracts/candidate.py, which requires the recess to fit in body_height_mm - floor_thickness_mm."),
        new("A4", "The body pocket is open at the top with the vacuum-cavity footprint. The lid is a plate (package footprint x lid thickness) plus a plug with the cavity footprint that fills the pocket from the body top down to the cavity ceiling, line-to-line (0 mm clearance).",
            "With body_height_mm = 5.0 the pocket is deeper than height_above_chip_mm; a plug is the only way the seed's cavity height and body height both hold. The cavity height is then set by the lid, so the 3x3 sweep varies the lid, not the body."),
        new("A5", "Two coaxial launch bores of the candidate's diameter run along X at y = 0 through the -X and +X walls, from the outer face to the pocket wall, with the bore tangent to the cavity floor (axis z = cavity floor + bore radius).",
            "Every seed bore (2.25-2.75 mm) is taller than the cavity (1.23-1.73 mm). Tangent to the floor, the body bore is a clean through-hole into the pocket and never cuts below the cavity floor; the part above the cavity ceiling is closed by the lid plug. A real SMP launch would put its pin at the chip surface, which needs a pin and dielectric model this generator does not include."),
        new("A6", $"Four vertical mounting through-holes of {MountingHoleDiameterMm} mm diameter (M2 clearance) at (+/-(outer width + cavity width)/4, +/-(outer height + cavity height)/4), through the body and the lid plate.",
            "Centred in the corner wall bands; the spec names mounting features without dimensions."),
        new("A7", $"Thermal path: a raised contact land {ThermalLandHeightMm} mm high with the chip footprint, centred under the chip on the body underside.",
            "Defines the cold-plate contact area directly below the chip; the spec asks for simple thermal-path geometry without dimensions."),
        new("A8", $"Filter-housing allowance: a reserved, unmachined block in the +Y wall, {FilterAllowanceLengthMm} mm long in X centred on x = 0, inset {FilterAllowanceMarginMm} mm from the pocket wall, the outer face and the body top, from the cavity floor up. Nothing may be cut into it.",
            "The spec asks for an allowance, not a filter; reserving solid wall keeps space for a later housing without inventing its design."),
        new("A9", $"Voxel size {DefaultVoxelSizeMm} mm unless --voxel-mm is given; every feature, wall and margin must span at least {MinimumFeatureVoxels} voxels (ENGINEERING-RULE).",
            "PicoGK is a voxel kernel; the faces are planes but edges round at about one voxel."),
    };
}

/// <summary>One acceptance check: what it checks, whether it passed, and the numbers.</summary>
public sealed record CheckResult(string Id, string Spec, string Description, bool Passed, string Detail);

/// <summary>A point whose membership in a part is predicted by the layout.</summary>
public sealed record Probe(string Check, string Label, string Part, Vec3 Point, bool ExpectSolid);

/// <summary>The Object 001 layout in the frozen frame, derived from the parameters and Object001Assumptions.</summary>
public sealed class Object001Layout
{
    public Object001Parameters P { get; }

    // Z levels (A1-A5).
    public double ZChipTop => 0.0;
    public double ZChipBottom { get; }
    public double ZRecessFloor { get; }
    public double ZCavityFloor { get; }
    public double ZCavityCeiling { get; }
    public double ZBodyBottom { get; }
    public double ZBodyTop { get; }
    public double ZLidTop { get; }
    public double ZLandBottom { get; }
    public double ZBoreAxis { get; }
    public double PlugHeight => ZBodyTop - ZCavityCeiling;
    public double BoreRadius => P.BoreDiameterMm / 2;
    public double HoleRadius => Object001Assumptions.MountingHoleDiameterMm / 2;

    // Half sizes.
    public double Ox => P.PackageOuterWidthMm / 2;
    public double Oy => P.PackageOuterHeightMm / 2;
    public double Cx => P.CavityWidthMm / 2;
    public double Cy => P.CavityHeightMm / 2;
    public double Rx => P.ChipWidthMm / 2 + P.RecessXyClearanceMm;
    public double Ry => P.ChipHeightMm / 2 + P.RecessXyClearanceMm;
    public double Wx => P.ChipWidthMm / 2;
    public double Wy => P.ChipHeightMm / 2;

    public Box BodyBlock { get; }
    public Box ThermalLand { get; }
    public Box Pocket { get; }
    public Box Recess { get; }
    public Box Chip { get; }
    public Box VacuumCavity { get; }
    public Box LidPlate { get; }
    /// <summary>Zero height when the cavity ceiling is the body top (then the lid has no plug).</summary>
    public Box LidPlug { get; }
    public Box FilterAllowance { get; }
    /// <summary>P1 at -X, P2 at +X, each from the outer face to the pocket wall.</summary>
    public IReadOnlyList<AxisCylinder> Bores { get; }
    /// <summary>Through the body and the lid plate, z = body bottom to lid top.</summary>
    public IReadOnlyList<AxisCylinder> MountingHoles { get; }

    public Object001Layout(Object001Parameters p)
    {
        P = p;
        ZChipBottom = -p.ChipThicknessMm;
        ZRecessFloor = -p.ChipThicknessMm;                       // A1
        ZCavityFloor = ZRecessFloor + p.RecessDepthMm;
        ZCavityCeiling = p.CavityHeightAboveChipMm;              // A2
        ZBodyBottom = ZRecessFloor - p.FloorThicknessMm;         // A3
        ZBodyTop = ZBodyBottom + p.BodyHeightMm;
        ZLidTop = ZBodyTop + p.LidThicknessMm;
        ZLandBottom = ZBodyBottom - Object001Assumptions.ThermalLandHeightMm;   // A7
        ZBoreAxis = ZCavityFloor + p.BoreDiameterMm / 2;         // A5

        BodyBlock = new Box(new Vec3(-Ox, -Oy, ZBodyBottom), new Vec3(Ox, Oy, ZBodyTop));
        ThermalLand = new Box(new Vec3(-Wx, -Wy, ZLandBottom), new Vec3(Wx, Wy, ZBodyBottom));
        Pocket = new Box(new Vec3(-Cx, -Cy, ZCavityFloor), new Vec3(Cx, Cy, ZBodyTop));
        Recess = new Box(new Vec3(-Rx, -Ry, ZRecessFloor), new Vec3(Rx, Ry, ZCavityFloor));
        Chip = new Box(new Vec3(-Wx, -Wy, ZChipBottom), new Vec3(Wx, Wy, ZChipTop));
        VacuumCavity = new Box(new Vec3(-Cx, -Cy, ZCavityFloor), new Vec3(Cx, Cy, ZCavityCeiling));
        LidPlate = new Box(new Vec3(-Ox, -Oy, ZBodyTop), new Vec3(Ox, Oy, ZLidTop));
        LidPlug = new Box(new Vec3(-Cx, -Cy, Math.Min(ZCavityCeiling, ZBodyTop)), new Vec3(Cx, Cy, ZBodyTop));
        double m = Object001Assumptions.FilterAllowanceMarginMm;
        double half = Object001Assumptions.FilterAllowanceLengthMm / 2;
        FilterAllowance = new Box(new Vec3(-half, Cy + m, ZCavityFloor), new Vec3(half, Oy - m, ZBodyTop - m));   // A8

        Bores = new[]
        {
            new AxisCylinder(CylinderAxis.X, 0, ZBoreAxis, -Ox, -Cx, BoreRadius),
            new AxisCylinder(CylinderAxis.X, 0, ZBoreAxis, Cx, Ox, BoreRadius),
        };
        double mx = (Ox + Cx) / 2, my = (Oy + Cy) / 2;           // A6
        MountingHoles = new[]
        {
            new AxisCylinder(CylinderAxis.Z, -mx, -my, ZBodyBottom, ZLidTop, HoleRadius),
            new AxisCylinder(CylinderAxis.Z, mx, -my, ZBodyBottom, ZLidTop, HoleRadius),
            new AxisCylinder(CylinderAxis.Z, mx, my, ZBodyBottom, ZLidTop, HoleRadius),
            new AxisCylinder(CylinderAxis.Z, -mx, my, ZBodyBottom, ZLidTop, HoleRadius),
        };
    }

    public static Object001Layout FromCandidate(Candidate candidate) =>
        new(Object001Parameters.FromJson(candidate.Parameters));

    // --- membership (the CSG the PicoGK construction must reproduce) ----------------------

    public bool BodyContains(Vec3 q)
    {
        bool solid = BodyBlock.Contains(q) || ThermalLand.Contains(q);
        bool cut = InteriorOf(Pocket, q) || InteriorOf(Recess, q)
            || Bores.Any(b => b.Contains(q)) || MountingHoles.Any(h => h.Contains(q));
        return solid && !cut;
    }

    public bool LidContains(Vec3 q)
    {
        bool solid = LidPlate.Contains(q) || (PlugHeight > 0 && LidPlug.Contains(q));
        return solid && !MountingHoles.Any(h => h.Contains(q));
    }

    // The pocket and recess are open to the top: points on their open faces are void.
    static bool InteriorOf(Box b, Vec3 q) =>
        q.X > b.Min.X && q.X < b.Max.X && q.Y > b.Min.Y && q.Y < b.Max.Y && q.Z > b.Min.Z && q.Z <= b.Max.Z;

    // --- exact volumes, areas and bounds ----------------------------------------------------
    //
    // Valid when the analytic checks pass: every cut lies inside the solid it cuts and no two
    // cuts overlap, so the solid is the block plus the land minus the sum of the cuts.

    public double BodyVolumeExact =>
        BodyBlock.Volume + ThermalLand.Volume - Pocket.Volume - Recess.Volume
        - Bores.Sum(b => b.Volume) - MountingHoles.Count * Math.PI * HoleRadius * HoleRadius * P.BodyHeightMm;

    public double LidVolumeExact =>
        LidPlate.Volume + (PlugHeight > 0 ? LidPlug.Volume : 0)
        - MountingHoles.Count * Math.PI * HoleRadius * HoleRadius * P.LidThicknessMm;

    public double BodyAreaExact
    {
        get
        {
            double holes = MountingHoles.Count * Math.PI * HoleRadius * HoleRadius;
            double boreDiscs = Bores.Count * Math.PI * BoreRadius * BoreRadius;
            double footprint = 4 * Ox * Oy;
            double landTop = 4 * Wx * Wy;
            return (footprint - landTop - holes)                                    // block underside
                + landTop + 2 * (2 * Wx + 2 * Wy) * Object001Assumptions.ThermalLandHeightMm   // land
                + (footprint - 4 * Cx * Cy - holes)                                 // top rim
                + 4 * (Ox + Oy) * P.BodyHeightMm - boreDiscs                        // outer sides
                + 4 * (Cx + Cy) * (ZBodyTop - ZCavityFloor) - boreDiscs             // pocket walls
                + (4 * Cx * Cy - 4 * Rx * Ry)                                       // pocket floor ring
                + 4 * (Rx + Ry) * P.RecessDepthMm + 4 * Rx * Ry                     // recess walls and floor
                + Bores.Sum(b => 2 * Math.PI * b.Radius * b.Length)                 // bore walls
                + MountingHoles.Count * 2 * Math.PI * HoleRadius * P.BodyHeightMm;  // hole walls
        }
    }

    public double LidAreaExact
    {
        get
        {
            double holes = MountingHoles.Count * Math.PI * HoleRadius * HoleRadius;
            double footprint = 4 * Ox * Oy;
            double plug = PlugHeight > 0 ? PlugHeight : 0;
            return (footprint - holes)                                              // plate top
                + (footprint - 4 * Cx * Cy - holes) + 4 * Cx * Cy                   // plate underside and plug bottom
                + 4 * (Ox + Oy) * P.LidThicknessMm                                  // plate sides
                + 4 * (Cx + Cy) * plug                                              // plug sides
                + MountingHoles.Count * 2 * Math.PI * HoleRadius * P.LidThicknessMm; // hole walls
        }
    }

    public Box BodyBoundsExact => new(new Vec3(-Ox, -Oy, ZLandBottom), new Vec3(Ox, Oy, ZBodyTop));

    public Box LidBoundsExact =>
        new(new Vec3(-Ox, -Oy, PlugHeight > 0 ? ZCavityCeiling : ZBodyTop), new Vec3(Ox, Oy, ZLidTop));

    /// <summary>Height of the bore opening into the vacuum cavity (below the cavity ceiling).</summary>
    public double BoreApertureHeight => Math.Min(ZCavityCeiling, ZBoreAxis + BoreRadius) - ZCavityFloor;

    /// <summary>The height at which the bore-to-cavity path probes run: the middle of the aperture.</summary>
    public double BorePathZ => ZCavityFloor + BoreApertureHeight / 2;

    // --- analytic acceptance checks (spec §7.6) --------------------------------------------

    public IReadOnlyList<CheckResult> AnalyticChecks(double voxelSizeMm)
    {
        var checks = new List<CheckResult>();
        void Add(string id, string spec, string description, bool passed, string detail) =>
            checks.Add(new CheckResult(id, spec, description, passed, detail));

        Add("positive_volume", "§7.6", "Body and lid have positive volume.",
            BodyVolumeExact > 0 && LidVolumeExact > 0,
            $"body {BodyVolumeExact:R} mm^3, lid {LidVolumeExact:R} mm^3");

        Add("recess_fits_inside_package", "§7.6",
            "The recess lies inside the package footprint and the cavity footprint, above a positive floor.",
            Rx < Cx && Ry < Cy && Cx < Ox && Cy < Oy && ZRecessFloor - ZBodyBottom > 0 && ZCavityFloor < ZBodyTop,
            $"recess half sizes ({Rx:R}, {Ry:R}) < cavity ({Cx:R}, {Cy:R}) < package ({Ox:R}, {Oy:R}); floor below recess {ZRecessFloor - ZBodyBottom:R} mm");

        Add("chip_fits_inside_recess", "§7.6",
            "The chip fits inside the recess with positive XY clearance and its top at or below the recess rim.",
            Wx < Rx && Wy < Ry && ZChipTop <= ZCavityFloor,
            $"chip half sizes ({Wx:R}, {Wy:R}) < recess ({Rx:R}, {Ry:R}); recess rim {ZCavityFloor:R} mm above the chip top");

        double wallX = Ox - Cx, wallY = Oy - Cy, cavityHeight = ZCavityCeiling - ZCavityFloor;
        Add("cavity_leaves_positive_walls", "§7.6",
            "Side walls, floor and lid are positive; the cavity has positive height and its ceiling is not above the body top.",
            wallX > 0 && wallY > 0 && P.FloorThicknessMm > 0 && P.LidThicknessMm > 0 && cavityHeight > 0 && PlugHeight >= 0,
            $"walls X {wallX:R} mm, Y {wallY:R} mm; cavity height {cavityHeight:R} mm; lid plug {PlugHeight:R} mm");

        double wallAboveBore = ZBodyTop - (ZBoreAxis + BoreRadius);
        bool boresClear = Bores.All(b => MountingHoles.All(h => !Overlap(b.Bounds, h.Bounds)) && !Overlap(b.Bounds, FilterAllowance));
        Add("launch_bores_connect_exterior_to_cavity", "§7.4, §7.6",
            "Each bore runs from the outer face to the pocket wall, inside the wall's height and width, opens into the vacuum cavity, and misses the holes and the filter allowance.",
            Ox - Cx > 0 && ZBoreAxis - BoreRadius >= ZCavityFloor && wallAboveBore > 0 && BoreRadius < Cy
                && BoreApertureHeight > 0 && boresClear,
            $"bore length {Ox - Cx:R} mm; axis z {ZBoreAxis:R} mm; wall above bore {wallAboveBore:R} mm; aperture into the cavity {BoreApertureHeight:R} mm high");

        double holeMargin = HoleMaterialMargin();
        Add("mounting_holes_in_material", "§7.4, §7.6",
            "Each mounting hole is surrounded by solid wall: clear of the pocket, the outer faces, the thermal land, the bores and the filter allowance.",
            holeMargin > 0,
            $"smallest solid margin around a hole {holeMargin:R} mm");

        Add("thermal_path_present", "§7.4", "A thermal contact land sits under the chip footprint, inside the body footprint.",
            Object001Assumptions.ThermalLandHeightMm > 0 && Wx < Ox && Wy < Oy,
            $"land {2 * Wx:R} x {2 * Wy:R} x {Object001Assumptions.ThermalLandHeightMm:R} mm");

        Box allowance = FilterAllowance;
        bool allowanceInWall = allowance.Min.Y > Cy && allowance.Max.Y < Oy && allowance.Min.X > -Ox && allowance.Max.X < Ox
            && allowance.SizeX > 0 && allowance.SizeY > 0 && allowance.SizeZ > 0
            && allowance.Min.Z >= ZBodyBottom && allowance.Max.Z < ZBodyTop;
        bool allowanceClear = MountingHoles.All(h => allowance.XyDistanceTo(h.U, h.V) > h.Radius);
        Add("filter_allowance_reserved", "§7.4",
            "The filter-housing allowance is solid wall that no feature cuts.",
            allowanceInWall && allowanceClear,
            $"allowance {allowance.SizeX:R} x {allowance.SizeY:R} x {allowance.SizeZ:R} mm in the +Y wall");

        Add("chip_datum_defined", "§7.3, §7.4", "The origin is the centre of the chip's top surface.",
            Chip.Max.Z == 0 && Chip.Min.X == -Chip.Max.X && Chip.Min.Y == -Chip.Max.Y,
            "chip top at z = 0, centred in X and Y");

        Add("solver_domain_bounded", "§7.4",
            "The solver domain (cavity, recess, bores) lies inside the package envelope and is closed by body and lid.",
            Recess.Min.Z > ZBodyBottom && VacuumCavity.Max.Z <= ZBodyTop && PlugHeight >= 0 && ZLidTop > ZBodyTop,
            $"domain z {ZRecessFloor:R} to {Math.Max(ZCavityCeiling, ZBoreAxis + BoreRadius):R} mm inside the body z {ZBodyBottom:R} to {ZBodyTop:R} mm");

        var features = FeatureSizes();
        double need = Object001Assumptions.MinimumFeatureVoxels * voxelSizeMm;
        var thin = features.Where(f => f.Value < need).Select(f => $"{f.Key} {f.Value:R} mm").ToList();
        Add("feature_resolution", "§7.6",
            $"Every feature, wall and margin spans at least {Object001Assumptions.MinimumFeatureVoxels} voxels of {voxelSizeMm:R} mm.",
            double.IsFinite(voxelSizeMm) && voxelSizeMm > 0 && thin.Count == 0,
            thin.Count == 0 ? $"smallest: {features.MinBy(f => f.Value).Key} {features.Min(f => f.Value):R} mm >= {need:R} mm"
                            : $"below {need:R} mm: {string.Join("; ", thin)}");
        return checks;
    }

    /// <summary>Smallest solid margin around any mounting hole (negative when a hole breaks into something).</summary>
    public double HoleMaterialMargin()
    {
        double margin = double.PositiveInfinity;
        foreach (AxisCylinder h in MountingHoles)
        {
            margin = Math.Min(margin, Pocket.XyDistanceTo(h.U, h.V) - h.Radius);
            margin = Math.Min(margin, ThermalLand.XyDistanceTo(h.U, h.V) - h.Radius);
            margin = Math.Min(margin, FilterAllowance.XyDistanceTo(h.U, h.V) - h.Radius);
            margin = Math.Min(margin, Ox - (Math.Abs(h.U) + h.Radius));
            margin = Math.Min(margin, Oy - (Math.Abs(h.V) + h.Radius));
            foreach (AxisCylinder b in Bores)
            {
                // A Z hole and an X bore at y = 0 are disjoint when the hole clears the bore's Y band.
                margin = Math.Min(margin, Math.Abs(h.V - b.U) - h.Radius - b.Radius);
            }
        }
        return margin;
    }

    /// <summary>Every thickness the voxel construction has to resolve.</summary>
    public IReadOnlyDictionary<string, double> FeatureSizes()
    {
        var sizes = new Dictionary<string, double>
        {
            ["recess depth"] = P.RecessDepthMm,
            ["floor below recess"] = P.FloorThicknessMm,
            ["pocket floor ring"] = Math.Min(Cx - Rx, Cy - Ry),
            ["side wall X"] = Ox - Cx,
            ["side wall Y"] = Oy - Cy,
            ["lid plate"] = P.LidThicknessMm,
            ["thermal land"] = Object001Assumptions.ThermalLandHeightMm,
            ["wall above bore"] = ZBodyTop - (ZBoreAxis + BoreRadius),
            ["bore diameter"] = P.BoreDiameterMm,
            ["bore aperture height"] = BoreApertureHeight,
            ["mounting hole diameter"] = Object001Assumptions.MountingHoleDiameterMm,
            ["material around holes"] = HoleMaterialMargin(),
        };
        if (PlugHeight > 0)
        {
            sizes["lid plug"] = PlugHeight;
        }
        return sizes;
    }

    static bool Overlap(Box a, Box b) =>
        a.Min.X < b.Max.X && b.Min.X < a.Max.X && a.Min.Y < b.Max.Y && b.Min.Y < a.Max.Y && a.Min.Z < b.Max.Z && b.Min.Z < a.Max.Z;

    // --- probes for the voxel construction ---------------------------------------------------

    /// <summary>
    /// Points whose membership the voxel parts must reproduce. Each lies at least two voxels
    /// from every surface (the analytic resolution check guarantees the room). Paths are
    /// sampled every half voxel, so a solid skin one voxel thick cannot hide between samples.
    /// </summary>
    public IReadOnlyList<Probe> Probes(double voxelSizeMm)
    {
        double g = 2 * voxelSizeMm, step = voxelSizeMm / 2;
        var probes = new List<Probe>();
        void Solid(string check, string label, string part, Vec3 q) => probes.Add(new Probe(check, label, part, q, true));
        void Void(string check, string label, string part, Vec3 q) => probes.Add(new Probe(check, label, part, q, false));
        double midBody = (ZBodyBottom + ZBodyTop) / 2;

        Solid("positive_volume", "floor below the recess", "body", new Vec3(0, 0, (ZBodyBottom + ZRecessFloor) / 2));
        Solid("positive_volume", "+Y side wall", "body", new Vec3(0, (Oy + Cy) / 2, midBody));
        Solid("positive_volume", "-Y side wall", "body", new Vec3(0, -(Oy + Cy) / 2, midBody));
        Solid("cavity_leaves_positive_walls", "-X wall below the bore", "body", new Vec3(-(Ox + Cx) / 2, 0, (ZBodyBottom + ZCavityFloor) / 2));
        Solid("cavity_leaves_positive_walls", "+X wall above the bore", "body", new Vec3((Ox + Cx) / 2, 0, (ZBoreAxis + BoreRadius + ZBodyTop) / 2));
        Void("recess_fits_inside_package", "recess", "body", new Vec3(0, 0, (ZRecessFloor + ZCavityFloor) / 2));
        Void("recess_fits_inside_package", "recess near its +X wall", "body", new Vec3(Rx - g, 0, (ZRecessFloor + ZCavityFloor) / 2));
        Solid("recess_fits_inside_package", "pocket floor ring beyond the recess", "body", new Vec3((Rx + Cx) / 2, 0, (ZRecessFloor + ZCavityFloor) / 2));
        Void("cavity_leaves_positive_walls", "pocket", "body", new Vec3(0, 0, (ZCavityFloor + ZBodyTop) / 2));
        Void("cavity_leaves_positive_walls", "above the body", "body", new Vec3(0, 0, ZBodyTop + g));
        Void("cavity_leaves_positive_walls", "outside +X", "body", new Vec3(Ox + g, Oy / 2, midBody));
        Solid("thermal_path_present", "thermal land", "body", new Vec3(0, 0, (ZLandBottom + ZBodyBottom) / 2));
        Void("thermal_path_present", "below the land", "body", new Vec3(0, 0, ZLandBottom - g));
        Void("thermal_path_present", "beside the land, below the body", "body", new Vec3(0, (Wy + Oy) / 2, (ZLandBottom + ZBodyBottom) / 2));

        Box a = FilterAllowance;
        Solid("filter_allowance_reserved", "allowance centre", "body", a.Centre);
        foreach (double x in new[] { a.Min.X + g, a.Max.X - g })
            foreach (double y in new[] { a.Min.Y + g, a.Max.Y - g })
                foreach (double z in new[] { a.Min.Z + g, a.Max.Z - g })
                    Solid("filter_allowance_reserved", "allowance corner", "body", new Vec3(x, y, z));

        // Launch bores: a straight void path from outside the package, through the bore and
        // its opening, to the centre of the vacuum cavity, in the body and in the lid.
        foreach ((AxisCylinder bore, string port) in Bores.Zip(new[] { "P1", "P2" }))
        {
            double outside = bore.From < 0 ? -(Ox + g) : Ox + g;
            int n = (int)Math.Ceiling(Math.Abs(outside) / step);
            for (int i = 0; i <= n; i++)
            {
                double x = outside * (1 - (double)i / n);
                Void("launch_bores_connect_exterior_to_cavity", $"{port} path", "assembly", new Vec3(x, 0, BorePathZ));
            }
            double xm = (bore.From + bore.To) / 2;
            Solid("launch_bores_connect_exterior_to_cavity", $"{port} wall beside the bore", "body", new Vec3(xm, BoreRadius + g, ZBoreAxis));
            Solid("launch_bores_connect_exterior_to_cavity", $"{port} wall beside the bore", "body", new Vec3(xm, -(BoreRadius + g), ZBoreAxis));
        }

        // Mounting holes: void along the whole axis through body and lid, solid all round.
        foreach ((AxisCylinder hole, int k) in MountingHoles.Select((h, k) => (h, k)))
        {
            int n = (int)Math.Ceiling((ZLidTop - ZBodyBottom + 2 * g) / step);
            for (int i = 0; i <= n; i++)
            {
                double z = ZBodyBottom - g + i * (ZLidTop - ZBodyBottom + 2 * g) / n;
                Void("mounting_holes_in_material", $"hole {k} axis", "assembly", new Vec3(hole.U, hole.V, z));
            }
            double r = hole.Radius + g;
            foreach ((double dx, double dy) in new[] { (r, 0.0), (-r, 0.0), (0.0, r), (0.0, -r) })
            {
                Solid("mounting_holes_in_material", $"hole {k} surround", "body", new Vec3(hole.U + dx, hole.V + dy, midBody));
                Solid("mounting_holes_in_material", $"hole {k} surround", "lid", new Vec3(hole.U + dx, hole.V + dy, (ZBodyTop + ZLidTop) / 2));
            }
        }

        // Lid.
        Solid("positive_volume", "lid plate", "lid", new Vec3(0, 0, (ZBodyTop + ZLidTop) / 2));
        Void("positive_volume", "above the lid", "lid", new Vec3(0, 0, ZLidTop + g));
        if (PlugHeight > 0)
        {
            Solid("cavity_leaves_positive_walls", "lid plug", "lid", new Vec3(0, 0, (ZCavityCeiling + ZBodyTop) / 2));
        }
        Void("cavity_leaves_positive_walls", "no lid material in the wall band", "lid", new Vec3((Ox + Cx) / 2, 0, (ZCavityFloor + ZBodyTop) / 2));

        // Assembly: the solver domain is void.
        Void("solver_domain_bounded", "vacuum cavity centre", "assembly", new Vec3(0, 0, (ZCavityFloor + ZCavityCeiling) / 2));
        Void("solver_domain_bounded", "vacuum cavity near a corner", "assembly", new Vec3(Cx - g, Cy - g, (ZCavityFloor + ZCavityCeiling) / 2));
        Void("solver_domain_bounded", "recess (the chip seat; the chip is not a part)", "assembly", new Vec3(0, 0, (ZRecessFloor + ZCavityFloor) / 2));
        return probes;
    }
}
