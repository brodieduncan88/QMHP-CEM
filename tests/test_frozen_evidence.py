"""Phase C, increment 2: frozen-evidence integrity - membership AND content.

MEMBERSHIP IS NOT DECIDED HERE, and that is the point. A digest test is only as strong
as its membership rule, and a hard-coded list of filenames nobody else has declared
authoritative would prevent mutation but not omission. The repository already owns the
rule: `orchestrator/manifest.py` defines what counts as a decision-relevant artefact
(a suffix allowlist and excluded cache directories, spec section 11.4), and
`manifest.verify()` reports BOTH directions for a record -

    recorded in the manifest but missing from disk
    content changed since the manifest was written
    present on disk but absent from the manifest

Every executed record carries the `manifest.sha256` its own driver wrote at execution
time. That is the authoritative register, produced by the run rather than by a test.

What was missing is narrow and was the whole gap: NOTHING EVER RAN THAT VERIFIER OVER
THE COMMITTED RECORDS. `tests/test_verification.py` exercises it on a record it creates
in a temporary directory; the 33 historical records in `results/` were never checked.
This module runs the repository's own verifier over all of them, and adds the two things
per-record verification cannot do by itself:

  * the record SET is pinned, so a record cannot vanish, and a new one cannot arrive
    without being incorporated here deliberately;
  * the MANIFESTS THEMSELVES are pinned by an aggregate digest, so a file cannot be
    mutated and its manifest rewritten to agree - which per-record verification would
    happily call intact.

SCOPE. This enforces file immutability and manifest membership for `results/` records.
It is NOT evidence governance: it says nothing about whether a record's verdict is
justified, whether its provenance was sufficient, or whether a status was promoted
correctly. `results/README.md` is the campaign index - ordinary documentation, outside
any record, and deliberately not treated as evidence. `master/` and `reference/` have
their own verifiers already wired into CI; this module asserts those steps still exist
rather than duplicating them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"
sys.path.insert(0, str(REPO_ROOT))
from orchestrator import manifest  # noqa: E402  - the authoritative membership rule

#: The executed records that carry the manifest their driver wrote, pinned so that a
#: record cannot disappear and a new one cannot arrive unincorporated. A new approved
#: solve is expected to fail this test until it is added deliberately: that is the
#: "incorporated into the integrity record" step, not an obstacle to it.
MANIFESTED_RECORDS = frozenset({
    "COUPLED-CHECKPOINT-A-20260915T225104Z", "COUPLED-CHECKPOINT-A-20260915T231511Z",
    "COUPLED-CHECKPOINT-A-20260916T005601Z", "COUPLED-CHECKPOINT-A-20260916T010859Z",
    "COUPLED-LADDER-O1-L2-20260916T080802Z", "COUPLED-LADDER-O1-L2-N1-20260917T001735Z",
    "COUPLED-LADDER-O1-L2-N1R-20260919T110053Z", "COUPLED-LADDER-O1-L2-N2-20260917T103405Z",
    "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z", "COUPLED-LADDER-O1-L2-PO1-20260920T204837Z",
    "COUPLED-LADDER-O1-L2-R1-20260916T120954Z", "COUPLED-LADDER-O1-L3-20260916T091212Z",
    "COUPLED-PILOT-20260916T035733Z", "COUPLED-PILOT-CORR-20260916T064943Z",
    "COUPLED-S1-RECOVERY-20260916T105215Z",
    "PALACE-GOLDEN-20260915T014639Z", "PALACE-GOLDEN-20260915T015804Z",
    "PALACE-GOLDEN-20260915T025408Z", "PALACE-GOLDEN-20260915T030418Z",
    "PALACE-GOLDEN-20260915T050927Z", "PALACE-GOLDEN-20260915T063105Z",
    "PALACE-GOLDEN-20260915T065025Z", "PALACE-GOLDEN-20260915T091128Z",
    "PALACE-GOLDEN-20260915T115911Z", "PALACE-GOLDEN-20260915T225434Z",
    "PALACE-GOLDEN-20260915T233133Z", "PALACE-GOLDEN-20260916T023201Z",
    "PALACE-GOLDEN-20260920T120817Z",
    "PALACE-VERIFY-20260915T065055Z", "PALACE-VERIFY-20260915T091242Z",
    "PALACE-VERIFY-20260915T115901Z",
    "ROUTE-A-SYNTHETIC-20260915T231055Z",
})

#: QUARANTINE, not an exemption. This record has NO manifest.sha256, so `verify()`
#: cannot check it. That is a recorded failure of the run that produced it, not drift
#: discovered later: the commit subject that created it (9cf7cb1) says
#: "campaign step failure, manifest failure". It is left exactly as executed, because
#: writing a manifest for it now would alter historical evidence and would record a
#: digest taken long after the run. Its decision-relevant files are pinned here instead,
#: so their content is still frozen even though their membership has no register.
UNMANIFESTED_RECORD = "PALACE-VERIFY-20260915T063014Z"
UNMANIFESTED_DIGESTS = {
    "campaign.json": "ef3689ac76ef051235d11c8f6e937baae182fa1c12aa8c777c9b86f54cb21db7",
    "runs/ladder-L1/solver/config.json":
        "0f63c27c5cb57de81e74c37dddd83c377d2ca3c0c1d4717409cc9defec9843ba",
    "runs/ladder-L1/solver/mesh.msh":
        "7602c8c3815d1d76f670789328729389e2b83c978cce23e5557c9cfc48b2e3db",
    "runs/ladder-L1/solver/palace_log.txt":
        "2fff162675404e6886edae56c3cae098d18aa32b10f26da0db0a91e01f002237",
    "runs/ladder-L1/solver/palace_run.json":
        "3573959a058c953f924a7386336aa38e8e531346cbc53eec97d207082759d978",
    "runs/ladder-L1/solver/postpro/palace.json":
        "86e861e702205a0571da1ff651a10e807e7922d5e65d118eb384915d4c6d3c0c",
    "runs/ladder-L1/solver/solver_input.json":
        "c17f2046f2c420a8eb19638290e0bf0db9386d17ba7d8ed1a216cd62f3fd9a30",
    "summary.json": "c84549b80ccd8b5336c0f1289780b7ca44771a50730b8f4d220a8320a340b720",
}

#: sha256 over the canonical {record: sha256(its manifest.sha256)} map. Per-record
#: verification cannot catch a file that was mutated AND its manifest rewritten to
#: agree; this can, because the manifest's own bytes change.
MANIFEST_INDEX_DIGEST = "e880cc16f0453fb95e2011c2f8a9d5ac1a6c85f169899cd2f23788589b4661c2"

#: Not evidence. The campaign index lives beside the records and is ordinary
#: documentation; it is outside every record directory and is never manifested.
NOT_EVIDENCE = frozenset({"README.md"})


def records(root: Path = RESULTS) -> list[Path]:
    """Every record directory under a results root, in deterministic order."""
    return sorted(p for p in Path(root).iterdir() if p.is_dir())


def manifest_index(root: Path = RESULTS) -> dict[str, str]:
    """{record name: sha256 of its manifest.sha256} for every manifested record."""
    return {r.name: manifest.file_digest(r / "manifest.sha256")
            for r in records(root) if (r / "manifest.sha256").is_file()}


def index_digest(index: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(index, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evidence_mismatches(root: Path = RESULTS, *,
                        expect_manifested: frozenset[str] | None = None) -> list[str]:
    """Every discrepancy in a results tree, using the repository's own verifier.

    Covers content mutation, deletion, a manifest that names a file that is not there,
    a file present but unmanifested, a record that lost its manifest, and a record that
    arrived without being incorporated.
    """
    expect = MANIFESTED_RECORDS if expect_manifested is None else expect_manifested
    out: list[str] = []
    present = {r.name for r in records(root)}
    for name in sorted(present - expect - {UNMANIFESTED_RECORD}):
        out.append(f"{name}: a record not incorporated into the integrity record")
    for name in sorted(expect - present):
        out.append(f"{name}: incorporated but absent from disk")
    for record in records(root):
        if record.name not in expect:
            continue
        for finding in manifest.verify(record):
            out.append(f"{record.name}/{finding}")
    return out


# --- the committed evidence ----------------------------------------------------------

def test_every_committed_record_verifies_against_its_own_manifest():
    """The gap this increment closes. 32 records, each checked by the verifier its own
    driver's manifest was written for, in both directions."""
    assert evidence_mismatches() == []


def test_the_record_set_is_exactly_the_pinned_one():
    present = {r.name for r in records()}
    assert present == MANIFESTED_RECORDS | {UNMANIFESTED_RECORD}, {
        "unincorporated": sorted(present - MANIFESTED_RECORDS - {UNMANIFESTED_RECORD}),
        "missing": sorted((MANIFESTED_RECORDS | {UNMANIFESTED_RECORD}) - present)}
    assert len(MANIFESTED_RECORDS) == 32


def test_the_manifests_themselves_cannot_be_rewritten():
    """A mutation plus a rewritten manifest verifies clean per record. The aggregate
    digest over the manifests' own bytes is what refuses it."""
    index = manifest_index()
    assert set(index) == MANIFESTED_RECORDS
    assert index_digest(index) == MANIFEST_INDEX_DIGEST


def test_the_record_without_a_manifest_is_quarantined_not_ignored():
    """Pinned by content, since it has no register to be pinned by. The claim that it
    lacks a manifest is checked, not assumed."""
    record = RESULTS / UNMANIFESTED_RECORD
    assert record.is_dir()
    assert not (record / "manifest.sha256").exists(), \
        "it now has a manifest; move it into MANIFESTED_RECORDS"
    assert manifest.verify(record) == [f"manifest.sha256 is missing from {record}"]
    found = {p.relative_to(record).as_posix(): manifest.file_digest(p)
             for p in sorted(record.rglob("*"))
             if p.is_file() and manifest.is_decision_relevant(p, record)}
    assert found == UNMANIFESTED_DIGESTS


def test_documentation_beside_the_records_is_not_treated_as_evidence():
    """Ordinary documentation must not be frozen just for living near evidence."""
    for name in NOT_EVIDENCE:
        assert (RESULTS / name).is_file()
        assert not (RESULTS / name).is_dir()
        assert name not in {r.name for r in records()}


# --- the membership rule is the repository's, not this file's ------------------------

def test_the_membership_rule_comes_from_the_repository():
    """This module must not carry its own idea of what counts as evidence. The suffix
    allowlist and the cache exclusions belong to orchestrator/manifest.py, which the
    drivers use when they WRITE a manifest; a second, divergent copy here would make the
    guard check something the records were never built against."""
    source = Path(__file__).read_text()
    for owned in ("DECISION_RELEVANT_SUFFIXES", "EXCLUDED_DIRS", "EXCLUDED_NAMES"):
        assert f"{owned} = " not in source, f"{owned} must come from orchestrator.manifest"
        assert hasattr(manifest, owned)
    assert ".json" in manifest.DECISION_RELEVANT_SUFFIXES
    assert "manifest.sha256" in manifest.EXCLUDED_NAMES
    assert {"__pycache__", "scratch", "tmp"} <= set(manifest.EXCLUDED_DIRS)


def test_the_existing_master_and_reference_verifiers_are_still_wired_into_ci():
    """`master/` and `reference/` are frozen too and have their own verifiers. This
    module does not duplicate them, so it asserts they cannot be silently removed."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "cem verify-master" in ci
    assert "scripts/verify_reference_bundle.py" in ci
    assert (REPO_ROOT / "master" / "provenance.json").is_file()


# --- negative controls ---------------------------------------------------------------

@pytest.fixture
def synthetic_results(tmp_path: Path) -> Path:
    """A results tree with one properly manifested record, built by the repository's own
    writer so the controls exercise the real format."""
    root = tmp_path / "results"
    record = root / "SYNTHETIC-RECORD-20260921T000000Z"
    (record / "solver" / "postpro").mkdir(parents=True)
    (record / "summary.json").write_text('{"verdict": "PASS"}\n')
    (record / "solver" / "config.json").write_text('{"Problem": {"Type": "Eigenmode"}}\n')
    (record / "solver" / "postpro" / "eig.csv").write_text("m,f\n1,5.0\n")
    manifest.write(record)
    return root


def test_the_guard_rejects_mutation_deletion_mismatch_and_unregistered_addition(
        synthetic_results: Path):
    """The four failures the guard exists for, each applied to a real manifested record
    and each required to be named."""
    root = synthetic_results
    pinned = frozenset({"SYNTHETIC-RECORD-20260921T000000Z"})
    record = root / "SYNTHETIC-RECORD-20260921T000000Z"
    baseline = (record / "summary.json").read_text()
    assert evidence_mismatches(root, expect_manifested=pinned) == [], "the fixture is clean"

    def check() -> list[str]:
        return evidence_mismatches(root, expect_manifested=pinned)

    # 1. content mutation
    (record / "summary.json").write_text('{"verdict": "FAIL"}\n')
    found = check()
    assert any("summary.json: content changed since the manifest was written" in m
               for m in found), found
    (record / "summary.json").write_text(baseline)
    assert check() == [], "restoring the content must clear the finding"

    # 2. deletion
    (record / "solver" / "postpro" / "eig.csv").unlink()
    found = check()
    assert any("eig.csv: recorded in manifest but missing from disk" in m
               for m in found), found
    (record / "solver" / "postpro" / "eig.csv").write_text("m,f\n1,5.0\n")
    assert check() == []

    # 3. a digest mismatch introduced by editing the MANIFEST rather than the file
    man = record / "manifest.sha256"
    original = man.read_text()
    man.write_text(original.replace(original[:8], "deadbeef", 1))
    found = check()
    assert any("content changed since the manifest was written" in m for m in found), found
    man.write_text(original)
    assert check() == []

    # 4. an unregistered evidence file appearing inside a manifested record
    (record / "solver" / "postpro" / "surface-Q.csv").write_text("m,q\n1,1e5\n")
    found = check()
    assert any("surface-Q.csv: present on disk but absent from the manifest" in m
               for m in found), found
    (record / "solver" / "postpro" / "surface-Q.csv").unlink()
    assert check() == []

    # 5. a whole record arriving unincorporated, and one disappearing
    extra = root / "SYNTHETIC-RECORD-20260922T000000Z"
    (extra / "solver").mkdir(parents=True)
    (extra / "summary.json").write_text("{}\n")
    manifest.write(extra)
    found = check()
    assert any("not incorporated into the integrity record" in m for m in found), found
    import shutil
    shutil.rmtree(extra)
    assert check() == []
    shutil.rmtree(record)
    assert any("incorporated but absent from disk" in m for m in check())


def test_a_rewritten_manifest_passes_per_record_but_fails_the_aggregate(
        synthetic_results: Path):
    """The reason the aggregate digest exists. Mutate a file AND rewrite the manifest to
    agree: per-record verification calls it intact, and only the manifest's own digest
    shows that the register moved."""
    root = synthetic_results
    pinned = frozenset({"SYNTHETIC-RECORD-20260921T000000Z"})
    record = root / "SYNTHETIC-RECORD-20260921T000000Z"
    before = index_digest(manifest_index(root))

    (record / "summary.json").write_text('{"verdict": "FAIL"}\n')
    manifest.write(record)                      # the cover-up
    assert evidence_mismatches(root, expect_manifested=pinned) == [], \
        "per-record verification is satisfied by a rewritten manifest - that is the point"
    assert index_digest(manifest_index(root)) != before, \
        "the aggregate digest must move when a manifest is rewritten"
