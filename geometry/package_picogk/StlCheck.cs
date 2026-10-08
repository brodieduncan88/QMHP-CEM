// Copyright (c) 2026 Brodie Duncan. All rights reserved.
// Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
//
// Reads an exported binary STL back from its bytes and measures it, independently of the
// PicoGK objects that wrote it: triangle count, welded vertices, edge manifoldness,
// orientation, connected components, enclosed volume and bounds. The spec asks for a
// watertight check "where the exporter supports a reliable check" (§7.6); this is that
// check, run on the file that is actually published.

using System.Buffers.Binary;

namespace QmhpCem.Geometry;

public sealed record StlReport(
    int Triangles,
    int Vertices,
    int DegenerateTriangles,
    int BoundaryEdges,
    int OverusedEdges,
    int Components,
    double SignedVolumeMm3,
    Vec3 Min,
    Vec3 Max,
    string Header)
{
    /// <summary>
    /// Closed, 2-manifold and consistently outward-oriented: every directed edge occurs
    /// exactly once and so does its reverse, no triangle repeats a vertex, and the enclosed
    /// volume is positive.
    /// </summary>
    public bool Watertight =>
        Triangles > 0 && DegenerateTriangles == 0 && BoundaryEdges == 0 && OverusedEdges == 0 && SignedVolumeMm3 > 0;
}

public static class StlCheck
{
    const int HeaderBytes = 80;
    const int TriangleBytes = 50;

    /// <summary>Analyse a binary STL. Throws InvalidDataException for a malformed file.</summary>
    public static StlReport Analyse(ReadOnlySpan<byte> stl)
    {
        if (stl.Length < HeaderBytes + 4)
        {
            throw new InvalidDataException($"STL is {stl.Length} bytes, shorter than its 84-byte header");
        }
        uint count = BinaryPrimitives.ReadUInt32LittleEndian(stl.Slice(HeaderBytes, 4));
        long expected = HeaderBytes + 4 + (long)count * TriangleBytes;
        if (count == 0 || stl.Length != expected)
        {
            throw new InvalidDataException(
                $"STL declares {count} triangles, which needs {expected} bytes; the file has {stl.Length}");
        }
        string header = System.Text.Encoding.ASCII.GetString(stl.Slice(0, HeaderBytes)).TrimEnd(' ', '\0');

        var index = new Dictionary<(int, int, int), int>();
        var points = new List<Vec3>();
        var triangles = new (int A, int B, int C)[count];
        int degenerate = 0;
        double volume = 0;
        double minX = double.PositiveInfinity, minY = double.PositiveInfinity, minZ = double.PositiveInfinity;
        double maxX = double.NegativeInfinity, maxY = double.NegativeInfinity, maxZ = double.NegativeInfinity;

        int Weld(ReadOnlySpan<byte> at)
        {
            float x = BinaryPrimitives.ReadSingleLittleEndian(at);
            float y = BinaryPrimitives.ReadSingleLittleEndian(at.Slice(4));
            float z = BinaryPrimitives.ReadSingleLittleEndian(at.Slice(8));
            if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z))
            {
                throw new InvalidDataException("STL holds a non-finite vertex coordinate");
            }
            // +0 and -0 are the same point.
            var key = (BitConverter.SingleToInt32Bits(x == 0 ? 0f : x),
                       BitConverter.SingleToInt32Bits(y == 0 ? 0f : y),
                       BitConverter.SingleToInt32Bits(z == 0 ? 0f : z));
            if (!index.TryGetValue(key, out int id))
            {
                id = points.Count;
                index[key] = id;
                points.Add(new Vec3(x, y, z));
                minX = Math.Min(minX, x); minY = Math.Min(minY, y); minZ = Math.Min(minZ, z);
                maxX = Math.Max(maxX, x); maxY = Math.Max(maxY, y); maxZ = Math.Max(maxZ, z);
            }
            return id;
        }

        for (int t = 0; t < count; t++)
        {
            ReadOnlySpan<byte> rec = stl.Slice(HeaderBytes + 4 + t * TriangleBytes, TriangleBytes);
            int a = Weld(rec.Slice(12)), b = Weld(rec.Slice(24)), c = Weld(rec.Slice(36));
            triangles[t] = (a, b, c);
            if (a == b || b == c || c == a)
            {
                degenerate++;
                continue;
            }
            Vec3 p = points[a], q = points[b], r = points[c];
            volume += (p.X * (q.Y * r.Z - q.Z * r.Y) - p.Y * (q.X * r.Z - q.Z * r.X) + p.Z * (q.X * r.Y - q.Y * r.X)) / 6.0;
        }

        // Directed-edge census. A closed, consistently oriented 2-manifold uses every directed
        // edge exactly once and its reverse exactly once.
        var edges = new Dictionary<(int, int), int>();
        foreach ((int a, int b, int c) in triangles)
        {
            if (a == b || b == c || c == a)
            {
                continue;
            }
            foreach (var e in new[] { (a, b), (b, c), (c, a) })
            {
                edges[e] = edges.TryGetValue(e, out int n) ? n + 1 : 1;
            }
        }
        int boundary = 0, overused = 0;
        foreach (var ((u, w), n) in edges)
        {
            if (n > 1) overused++;
            if (!edges.ContainsKey((w, u))) boundary++;
        }

        // Connected components over the welded vertices that triangles use.
        var parent = Enumerable.Range(0, points.Count).ToArray();
        int Find(int i)
        {
            while (parent[i] != i)
            {
                parent[i] = parent[parent[i]];
                i = parent[i];
            }
            return i;
        }
        void Union(int i, int j) => parent[Find(i)] = Find(j);
        var used = new HashSet<int>();
        foreach ((int a, int b, int c) in triangles)
        {
            Union(a, b);
            Union(b, c);
            used.Add(a); used.Add(b); used.Add(c);
        }
        int components = used.Select(Find).Distinct().Count();

        return new StlReport((int)count, points.Count, degenerate, boundary, overused, components, volume,
            new Vec3(minX, minY, minZ), new Vec3(maxX, maxY, maxZ), header);
    }
}
