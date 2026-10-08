// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Known-answer and planted-defect tests for the STL read-back check, on synthetic files.

using System.Buffers.Binary;
using System.Numerics;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

[TestClass]
public sealed class StlCheckTests
{
    static byte[] Stl(IReadOnlyList<(Vector3 A, Vector3 B, Vector3 C)> triangles)
    {
        var bytes = new byte[84 + 50 * triangles.Count];
        System.Text.Encoding.ASCII.GetBytes("synthetic UNITS=mm").CopyTo(bytes, 0);
        BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(80), (uint)triangles.Count);
        for (int t = 0; t < triangles.Count; t++)
        {
            Span<byte> rec = bytes.AsSpan(84 + 50 * t, 50);
            int o = 12;   // the stored normal is left zero: the check must not rely on it
            foreach (Vector3 v in new[] { triangles[t].A, triangles[t].B, triangles[t].C })
            {
                BinaryPrimitives.WriteSingleLittleEndian(rec.Slice(o), v.X);
                BinaryPrimitives.WriteSingleLittleEndian(rec.Slice(o + 4), v.Y);
                BinaryPrimitives.WriteSingleLittleEndian(rec.Slice(o + 8), v.Z);
                o += 12;
            }
        }
        return bytes;
    }

    /// <summary>12 outward-wound triangles of an axis-aligned box.</summary>
    static List<(Vector3 A, Vector3 B, Vector3 C)> Cube(Vector3 min, Vector3 max)
    {
        var tris = new List<(Vector3, Vector3, Vector3)>();
        Vector3 size = max - min, centre = (min + max) / 2;
        // (outward normal, u, v) with u x v = normal, so (-u-v, +u-v, +u+v, -u+v) is counter-clockwise from outside.
        foreach ((Vector3 n, Vector3 u, Vector3 v) in new[]
        {
            (Vector3.UnitX, Vector3.UnitY, Vector3.UnitZ), (-Vector3.UnitX, Vector3.UnitZ, Vector3.UnitY),
            (Vector3.UnitY, Vector3.UnitZ, Vector3.UnitX), (-Vector3.UnitY, Vector3.UnitX, Vector3.UnitZ),
            (Vector3.UnitZ, Vector3.UnitX, Vector3.UnitY), (-Vector3.UnitZ, Vector3.UnitY, Vector3.UnitX),
        })
        {
            Vector3 c = centre + n * size / 2, hu = u * size / 2, hv = v * size / 2;
            Vector3 p0 = c - hu - hv, p1 = c + hu - hv, p2 = c + hu + hv, p3 = c - hu + hv;
            tris.Add((p0, p1, p2));
            tris.Add((p0, p2, p3));
        }
        return tris;
    }

    static readonly Vector3 Lo = new(-1, -2, -3), Hi = new(2, 1, 0.5f);

    [TestMethod]
    public void AClosedBoxIsWatertightWithItsExactVolumeAndBounds()
    {
        StlReport r = StlCheck.Analyse(Stl(Cube(Lo, Hi)));
        Assert.IsTrue(r.Watertight);
        Assert.AreEqual(12, r.Triangles);
        Assert.AreEqual(8, r.Vertices);
        Assert.AreEqual(1, r.Components);
        Assert.AreEqual(3.0 * 3.0 * 3.5, r.SignedVolumeMm3, 1e-9);
        Assert.AreEqual(new Vec3(-1, -2, -3), r.Min);
        Assert.AreEqual(new Vec3(2, 1, 0.5), r.Max);
        Assert.AreEqual("synthetic UNITS=mm", r.Header);
    }

    [TestMethod]
    public void AMissingTriangleLeavesBoundaryEdges()
    {
        var tris = Cube(Lo, Hi);
        tris.RemoveAt(5);
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.AreEqual(3, r.BoundaryEdges);
        Assert.IsFalse(r.Watertight);
    }

    [TestMethod]
    public void AFlippedTriangleIsInconsistentlyOriented()
    {
        var tris = Cube(Lo, Hi);
        tris[7] = (tris[7].A, tris[7].C, tris[7].B);
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.AreNotEqual(0, r.OverusedEdges);
        Assert.IsFalse(r.Watertight);
    }

    [TestMethod]
    public void AnInsideOutBoxHasNegativeVolumeAndIsRefused()
    {
        var tris = Cube(Lo, Hi).Select(t => (t.A, t.C, t.B)).ToList();
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.AreEqual(-3.0 * 3.0 * 3.5, r.SignedVolumeMm3, 1e-9);
        Assert.IsFalse(r.Watertight);
    }

    [TestMethod]
    public void TwoSeparateBoxesAreTwoComponents()
    {
        var tris = Cube(Lo, Hi);
        tris.AddRange(Cube(new Vector3(10, 10, 10), new Vector3(11, 11, 11)));
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.IsTrue(r.Watertight);
        Assert.AreEqual(2, r.Components);
    }

    [TestMethod]
    public void ADegenerateTriangleIsCounted()
    {
        var tris = Cube(Lo, Hi);
        tris.Add((Lo, Lo, Hi));
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.AreEqual(1, r.DegenerateTriangles);
        Assert.IsFalse(r.Watertight);
    }

    [TestMethod]
    public void PositiveAndNegativeZeroAreOnePoint()
    {
        var tris = Cube(new Vector3(0, 0, 0), new Vector3(1, 1, 1))
            .Select(t => (Neg(t.A), t.B, t.C)).ToList();
        StlReport r = StlCheck.Analyse(Stl(tris));
        Assert.AreEqual(8, r.Vertices);
        Assert.IsTrue(r.Watertight);

        static Vector3 Neg(Vector3 p) => new(p.X == 0 ? -0f : p.X, p.Y == 0 ? -0f : p.Y, p.Z == 0 ? -0f : p.Z);
    }

    [TestMethod]
    public void MalformedFilesAreRefused()
    {
        byte[] good = Stl(Cube(Lo, Hi));
        Assert.ThrowsExactly<InvalidDataException>(() => StlCheck.Analyse(good.AsSpan(0, good.Length - 1)));
        Assert.ThrowsExactly<InvalidDataException>(() => StlCheck.Analyse(good.AsSpan(0, 40)));
        Assert.ThrowsExactly<InvalidDataException>(() => StlCheck.Analyse(Stl(Array.Empty<(Vector3, Vector3, Vector3)>())));
        byte[] nan = (byte[])good.Clone();
        BinaryPrimitives.WriteSingleLittleEndian(nan.AsSpan(84 + 12), float.NaN);
        Assert.ThrowsExactly<InvalidDataException>(() => StlCheck.Analyse(nan));
    }
}
