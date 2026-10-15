"""CP1 contracts use small deterministic fixtures and no network or search."""
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from zeaguard import nb04_resources as r


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def g0_root(tmp_path):
    payload = put(tmp_path / "config/frozen.tsv", b"header\r\nvalue\r\n")
    b6 = put(tmp_path / "src/workstreams/bioinformatics/decisions/B6_GOVERNANCE_AMENDMENT_A1.md", b"historical B6\r\n")
    cert = {"gate": "G0", "status": "G0_PASS", "certified_artifacts": {
        "config/frozen.tsv": {"hash_mode": "LF_NORMALIZED", "sha256": r.digest(payload, normalized=True)}},
        "normative_documents": {b6.name: r.digest(b6)}}
    r.write_json(tmp_path / r.G0_PATH, cert)
    return tmp_path


def test_g0_validates_lf_semantics_without_mutating_bytes(g0_root):
    before = (g0_root / "config/frozen.tsv").read_bytes()
    assert r.verify_g0(g0_root)["status"] == "G0_PASS"
    assert (g0_root / "config/frozen.tsv").read_bytes() == before


@pytest.mark.parametrize("mutation", ["status", "mode", "scope", "payload", "b6", "path"])
def test_g0_fail_closed(g0_root, mutation):
    path = g0_root / r.G0_PATH
    cert = json.loads(path.read_text())
    if mutation == "status":
        cert["status"] = "NOT_DECLARED"
    elif mutation == "mode":
        cert["certified_artifacts"]["config/frozen.tsv"]["hash_mode"] = "COUNT_ONLY"
    elif mutation == "scope":
        cert["certified_artifacts"] = {}
    elif mutation == "path":
        cert["certified_artifacts"]["../outside"] = {"hash_mode": "RAW", "sha256": "0" * 64}
    elif mutation == "payload":
        (g0_root / "config/frozen.tsv").write_bytes(b"changed")
    else:
        (g0_root / "src/workstreams/bioinformatics/decisions/B6_GOVERNANCE_AMENDMENT_A1.md").write_bytes(b"changed")
    r.write_json(path, cert)
    with pytest.raises(r.ResourceContractError):
        r.verify_g0(g0_root)


def test_exact_species_requires_name_rank_and_taxid():
    report = {"reports": [{"taxonomy": {"rank": "SPECIES", "tax_id": 12, "current_scientific_name": {"name": "Species alpha"}}}]}
    assert r.resolve_species(report, "Species alpha", "12")["tax_id"] == 12
    for name, taxid in [("Species beta", "12"), ("Species alpha", "13")]:
        with pytest.raises(r.ResourceContractError):
            r.resolve_species(report, name, taxid)
    report["reports"][0]["taxonomy"]["rank"] = "GENUS"
    with pytest.raises(r.ResourceContractError):
        r.resolve_species(report, "Species alpha")


def test_assembly_url_requires_version_and_safe_name():
    report = {"accession": "GCF_003254395.2", "assembly_info": {"assembly_name": "Amel_HAv3.1"}}
    assert r.assembly_ftp(report).endswith("GCF/003/254/395/GCF_003254395.2_Amel_HAv3.1")
    report["accession"] = "GCF_003254395"
    with pytest.raises(r.ResourceContractError):
        r.assembly_ftp(report)


def test_normalization_retains_every_record_base_and_redundant_sequence(tmp_path):
    source = tmp_path / "source.fna.gz"
    with gzip.open(source, "wb") as stream:
        stream.write(b">A.1 alpha\nacgtNN\n>B.1 beta\nACGTNN\n>C.1\nRYS\n")
    fasta, identifiers = tmp_path / "normalized.fasta", tmp_path / "ids.tsv"
    quality = r.normalize_fasta(source, fasta, identifiers, "RESOURCE_1")
    assert quality["record_count"] == 3
    assert quality["total_bases"] == 15
    assert quality["ambiguous_bases"] == 7
    assert quality["lowercase_bases_in_source"] == 4
    assert quality["median_length_numerator"] == 12
    assert quality["median_length_denominator"] == 2
    assert fasta.read_bytes() == b">RESOURCE_1__00000001\nACGTNN\n>RESOURCE_1__00000002\nACGTNN\n>RESOURCE_1__00000003\nRYS\n"
    assert "A.1\tA.1 alpha\t6" in identifiers.read_text()
    assert quality == r.normalize_fasta(source, fasta, identifiers, "RESOURCE_1")


@pytest.mark.parametrize("data", [b"", b"ACGT\n", b">A\n", b">A\nACGT\n>A\nTT\n", b">A\nAC-G\n", b">A\nACGU\n", b">\nACGT\n"])
def test_invalid_fasta_leaves_no_normalized_artifact(tmp_path, data):
    source = put(tmp_path / "source.fasta", data)
    fasta, ids = tmp_path / "normalized.fasta", tmp_path / "ids.tsv"
    with pytest.raises(r.ResourceContractError):
        r.normalize_fasta(source, fasta, ids, "R1")
    assert not fasta.exists()
    assert not ids.exists()


def test_gzip_truncation_is_not_accepted(tmp_path):
    source = put(tmp_path / "source.gz", gzip.compress(b">A\nACGT\n")[:-5])
    with pytest.raises((EOFError, OSError)):
        r.normalize_fasta(source, tmp_path / "out.fasta", tmp_path / "ids.tsv", "R")
    assert not (tmp_path / "out.fasta").exists()


def test_normalization_rejects_changed_existing_output(tmp_path):
    source = put(tmp_path / "source.fasta", b">A\nACGT\n")
    output = put(tmp_path / "out.fasta", b"older different output")
    with pytest.raises(r.ResourceContractError):
        r.normalize_fasta(source, output, tmp_path / "ids.tsv", "R")
    assert output.read_bytes() == b"older different output"


@pytest.mark.parametrize("old,new,expected", [
    (None, "UNASSESSABLE", "RESOLVED_FROM_UNKNOWN"),
    ("UNASSESSABLE", "PARTIALLY_ASSESSABLE", "UPGRADED"),
    ("ASSESSABLE", "PARTIALLY_ASSESSABLE", "DOWNGRADED"),
    ("PARTIALLY_ASSESSABLE", "PARTIALLY_ASSESSABLE", "UNCHANGED"),
])
def test_assessability_transition_is_independent_of_ecological_tier(old, new, expected):
    assert r.assessment_change(old, new) == expected


def test_download_checks_source_checksum_and_cleans_failure(tmp_path, monkeypatch):
    class Response:
        headers = {"Content-Length": "4"}
        url = "https://ftp.ncbi.nlm.nih.gov/pinned.gz"
        def __enter__(self):
            from io import BytesIO
            self.stream = BytesIO(b"ACGT")
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return self.stream.read(size)
    monkeypatch.setattr(r, "urlopen", lambda *a, **k: Response())
    dest = tmp_path / "source.gz"
    with pytest.raises(r.ResourceContractError, match="MD5"):
        r.download(Response.url, dest, expected_md5="0" * 32)
    assert not dest.exists()
    assert not dest.with_suffix(".gz.part").exists()
    receipt = r.download(Response.url, dest, expected_md5=hashlib.md5(b"ACGT").hexdigest())
    assert receipt["sha256"] == hashlib.sha256(b"ACGT").hexdigest()
    assert r.download(Response.url, dest) == receipt
    dest.write_bytes(b"tampered")
    with pytest.raises(r.ResourceContractError):
        r.download(Response.url, dest)


def test_download_rejects_untrusted_source(tmp_path):
    with pytest.raises(r.ResourceContractError):
        r.download("https://example.org/source", tmp_path / "source")


def test_db_failure_does_not_publish_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(r.subprocess, "run", lambda *a, **k: type("Result", (), {"returncode": 1, "stderr": "failed"})())
    with pytest.raises(r.ResourceContractError, match="makeblastdb"):
        r.build_database(put(tmp_path / "in.fa", b">A\nACGT\n"), tmp_path / "db", "R", 1)
    assert not (tmp_path / "db").exists()
