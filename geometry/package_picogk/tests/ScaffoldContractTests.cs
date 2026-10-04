using System.Text.Json;

using Microsoft.VisualStudio.TestTools.UnitTesting;
using QmhpCem.Geometry;

namespace QmhpCem.Geometry.Tests;

[TestClass]
public sealed class ScaffoldContractTests
{
    [TestMethod]
    public void CandidateLoadAcceptsTheSupportedObjectType()
    {
        string path = WriteCandidate("object001_single_device_package");
        try
        {
            Candidate candidate = Candidate.Load(path);

            Assert.AreEqual("QMHP-CEM-A-RF-TEST", candidate.CandidateId);
            Assert.AreEqual("object001_single_device_package", candidate.ObjectType);
            Assert.AreEqual(22.0, candidate.Parameters.GetProperty("package_outer_x_mm").GetDouble());
        }
        finally
        {
            File.Delete(path);
        }
    }

    [TestMethod]
    public void CandidateLoadRejectsAnUnsupportedObjectType()
    {
        string path = WriteCandidate("not-an-object-001");
        try
        {
            InvalidDataException error = Assert.ThrowsExactly<InvalidDataException>(
                () => Candidate.Load(path));
            StringAssert.Contains(error.Message, "unsupported object_type");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [TestMethod]
    public void CommandLineRejectsMissingArguments()
    {
        Assert.AreEqual(2, QmhpCem.Geometry.Program.Main(Array.Empty<string>()));
    }

    [TestMethod]
    public void GeometryGeneratorRefusesToFabricateTheUnimplementedShape()
    {
        using JsonDocument document = JsonDocument.Parse("{\"package_outer_x_mm\":22.0}");
        var candidate = new Candidate(
            "QMHP-CEM-A-RF-TEST",
            "object001_single_device_package",
            document.RootElement.Clone());

        NotImplementedException error = Assert.ThrowsExactly<NotImplementedException>(
            () => Object001Package.Generate(candidate, Path.GetTempPath()));
        StringAssert.Contains(error.Message, "not implemented");
    }

    private static string WriteCandidate(string objectType)
    {
        string path = Path.Combine(Path.GetTempPath(), $"qmhp-cem-{Guid.NewGuid():N}.json");
        string json = JsonSerializer.Serialize(new
        {
            candidate_id = "QMHP-CEM-A-RF-TEST",
            object_type = objectType,
            parameters = new { package_outer_x_mm = 22.0 },
        });
        File.WriteAllText(path, json);
        return path;
    }
}
