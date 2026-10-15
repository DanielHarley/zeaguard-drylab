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


@pytest.mark.parametrize("mutation,pattern", [
    ("unselected", "outside frozen"), ("binding", "binding mismatch"),
    ("identity", "identity differs"), ("date", "before G0"),
    ("artifact", "outside nto"),
])
def test_materialization_requires_frozen_selection_and_post_g0_acquisition(tmp_path, monkeypatch, mutation, pattern):
    certificate = {"registered_utc": "2026-10-15T07:00:00+00:00"}
    monkeypatch.setattr(r, "verify_g0", lambda root: certificate)
    put(tmp_path / r.G0_PATH, b"certificate")
    put(tmp_path / "config/nb04_nto_panel.tsv", b"organism_id\nSPECIES\n")
    choice = {"resource_id": "R1", "organism_id": "SPECIES", "scientific_name": "Species alpha", "taxid": 12, "accession_version": "GCF_000000012.1", "release": "release 1"}
    inventory = {"g0_certificate_sha256": r.digest(tmp_path / r.G0_PATH),
                 "organisms": [{"organism_id": "SPECIES", "taxonomy_status": "EXACT_SPECIES_RESOLVED", "taxid": 12, "ecological_panel_tier": "CORE"}],
                 "selected_resources": [choice]}
    r.write_json(tmp_path / r.INVENTORY, inventory)
    resource = dict(choice, selection_sha256=hashlib.sha256(r.json_bytes(choice)).hexdigest(),
                    acquired_utc="2026-10-15T08:00:00+00:00", fasta_path="data/external/nto/input.fasta", artifacts_sha256={})
    if mutation == "unselected":
        resource["resource_id"] = "OTHER"
    elif mutation == "binding":
        resource["selection_sha256"] = "0" * 64
    elif mutation == "identity":
        resource["accession_version"] = "GCF_000000012.2"
    elif mutation == "date":
        resource["acquired_utc"] = "2026-10-15T06:00:00+00:00"
    else:
        resource["artifacts_sha256"] = {"src/unrelated.py": "0" * 64}
    with pytest.raises(r.ResourceContractError, match=pattern):
        r.materialize(tmp_path, inventory, [resource])
    assert not (tmp_path / r.MANIFEST).exists()


@pytest.mark.parametrize("anomaly,missing", [(False, False), (True, False), (False, True)])
def test_gff_source_consistency_preserves_exceptions_without_locus_promotion(tmp_path, anomaly, missing):
    folder = tmp_path / "resource"
    ids = put(folder / "identifiers.tsv", b"source_id\tsource_header\nXM_1.1\tXM_1.1 source\n")
    put(folder / "original/assembly_report.txt", b"chr1\trole\t1\ttype\tGB.1\t=\tRS.1\tunit\t100\n")
    line = b"RS.1\tRefSeq\tmRNA\t1\t4\t.\t+\t.\ttranscript_id=XM_1.1\n"
    if anomaly:
        line += b"RS.1\tRefSeq\tmRNA\t90\t20\t.\t?\t.\tID=complex;exception=trans-splicing\n"
    if missing:
        line = line.replace(b"XM_1.1", b"XM_2.1")
    put(folder / "original/annotation.gz", gzip.compress(line))
    resource = {"fasta_path": "resource/normalized.fasta", "identifier_map_path": "resource/identifiers.tsv", "quality": {"record_count": 1}}
    selection = {"kind": "RNA", "files": [{"role": "annotation", "name": "annotation.gz"}, {"role": "assembly_report", "name": "assembly_report.txt"}]}
    if missing:
        with pytest.raises(r.ResourceContractError, match="identifier missing"):
            r.annotation_consistency(tmp_path, resource, selection)
    else:
        before = (folder / "original/annotation.gz").read_bytes()
        result = r.annotation_consistency(tmp_path, resource, selection)
        assert result["coordinate_anomaly_count"] == int(anomaly)
        assert result["status"] == ("SOURCE_ANNOTATION_REVIEW_REQUIRED" if anomaly else "PASS")
        assert (folder / "original/annotation.gz").read_bytes() == before


@pytest.mark.parametrize("accession,taxid", [("ABCD01000001.1", 12), ("ABCD01000002.1", 12), ("ABCD01000001.1", 13)])
def test_tsa_checks_exact_accessions_and_source_taxonomy(tmp_path, accession, taxid):
    folder = tmp_path / "resource"
    put(folder / "ids.tsv", b"source_id\nABCD01000001.1\n")
    put(folder / "original/annotation.gz", gzip.compress(f'VERSION     {accession}\n                     /db_xref="taxon:{taxid}"\n'.encode()))
    resource = {"fasta_path": "resource/normalized.fasta", "identifier_map_path": "resource/ids.tsv", "quality": {"record_count": 1}}
    selection = {"kind": "TSA", "taxid": 12, "files": [{"role": "annotation", "name": "annotation.gz"}]}
    if accession != "ABCD01000001.1" or taxid != 12:
        with pytest.raises(r.ResourceContractError):
            r.annotation_consistency(tmp_path, resource, selection)
    else:
        assert r.annotation_consistency(tmp_path, resource, selection)["exact_accession_set_equality"] is True
