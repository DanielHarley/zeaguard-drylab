"""NB04 CP1 resource integrity and assessability, without search or calibration.

The G0 certificate is a prerequisite. Resource quality and ecological membership
are independent. This module never certifies G1 or assigns biological concern.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from zeaguard.nb04_serialization import serialize_multivalue

G0_PATH = "data/reference/nb04_g0_certification.json"
RUN_RECORD = "src/workstreams/bioinformatics/runs/2026-10-15_nb04-cp1-resource-inventory.md"
MANIFEST = "data/reference/nb04_nto_resources_manifest.json"
INVENTORY = "data/reference/nb04_nto_inventory.json"
REGISTRY = "data/reference/nb04_nto_resource_registry.tsv"
ASSESSABILITY = "data/reference/nb04_nto_assessability.tsv"
CP1 = "results/bioinformatics/nb04/cp1"
ACCESSION = re.compile(r"GC[AF]_\d{9}\.\d+$")
RESOURCE_ID = re.compile(r"[A-Z0-9_]+$")
DNA = frozenset("ACGTRYSWKMBDHVN")


class ResourceContractError(ValueError):
    """An input, frozen identity or acquired artifact is incompatible."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ResourceContractError(message)


def digest(path: Path, *, normalized: bool = False) -> str:
    if normalized:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def relative_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative != "", "empty path")
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), f"path outside project: {relative}")
    return path


def verify_g0(root: Path) -> dict:
    certificate = json.loads((root / G0_PATH).read_text("utf-8"))
    require(certificate.get("gate") == "G0" and certificate.get("status") == "G0_PASS", "G0_PASS required")
    require(bool(certificate.get("certified_artifacts")), "G0 artifact scope missing")
    for relative, record in certificate["certified_artifacts"].items():
        require(record.get("hash_mode") in {"RAW", "LF_NORMALIZED"}, "unknown hash mode")
        path = relative_path(root, relative)
        require(path.is_file(), f"G0 artifact missing: {relative}")
        observed = digest(path, normalized=record["hash_mode"] == "LF_NORMALIZED")
        require(observed == record["sha256"], f"G0 artifact changed: {relative}")
    b6 = root / "src/workstreams/bioinformatics/decisions/B6_GOVERNANCE_AMENDMENT_A1.md"
    require(digest(b6) == certificate["normative_documents"][b6.name], "B6 A1 changed")
    return certificate


def resolve_species(report: dict, name: str, expected_taxid: str = "") -> dict:
    taxa = [r["taxonomy"] for r in report.get("reports", [])
            if r.get("taxonomy", {}).get("current_scientific_name", {}).get("name") == name
            and r["taxonomy"].get("rank") == "SPECIES"]
    require(len(taxa) == 1, f"exact species identity unresolved: {name}")
    taxon = taxa[0]
    require(not expected_taxid or int(expected_taxid) == taxon["tax_id"], f"incompatible taxonomy: {name}")
    return taxon


def assembly_ftp(report: dict) -> str:
    accession = report["accession"]
    require(bool(ACCESSION.fullmatch(accession)), "versioned assembly accession required")
    name = report["assembly_info"]["assembly_name"]
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", name)), "unsafe assembly name")
    digits = accession.split("_")[1].split(".")[0]
    return "https://ftp.ncbi.nlm.nih.gov/genomes/all/" + "/".join(
        [accession[:3], digits[:3], digits[3:6], digits[6:9], accession + "_" + name])


def download(url: str, destination: Path, *, expected_md5: str | None = None,
             expected_sha256: str | None = None) -> dict:
    """Acquire one pinned official file atomically, preserving source bytes."""
    parsed = urlparse(url)
    require(parsed.scheme == "https" and (parsed.hostname or "").endswith(".ncbi.nlm.nih.gov"), "official HTTPS NCBI URL required")
    receipt_path = destination.with_suffix(destination.suffix + ".receipt.json")
    if destination.exists():
        require(receipt_path.exists(), "existing payload has no acquisition receipt")
        receipt = json.loads(receipt_path.read_text("utf-8"))
        require(receipt["url"] == url and digest(destination) == receipt["sha256"], "existing payload provenance mismatch")
        require(not expected_sha256 or receipt["sha256"] == expected_sha256, "SHA256 mismatch")
        require(not expected_md5 or receipt["md5"] == expected_md5, "source MD5 mismatch")
        return receipt
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    require(not part.exists(), "incomplete acquisition exists, inspect before retry")
    sha = hashlib.sha256()
    md5 = hashlib.md5()
    count = 0
    try:
        with urlopen(Request(url, headers={"User-Agent": "ZeaGuard-NB04-CP1/1.0"}), timeout=60) as response, part.open("xb") as stream:
            require((urlparse(response.url).hostname or "").endswith(".ncbi.nlm.nih.gov"), "unexpected redirect host")
            headers = dict(response.headers)
            for block in iter(lambda: response.read(1024 * 1024), b""):
                stream.write(block)
                sha.update(block)
                md5.update(block)
                count += len(block)
        require(count > 0, "empty acquisition")
        if headers.get("Content-Length"):
            require(count == int(headers["Content-Length"]), "truncated acquisition")
        require(not expected_md5 or md5.hexdigest() == expected_md5, "source MD5 mismatch")
        require(not expected_sha256 or sha.hexdigest() == expected_sha256, "SHA256 mismatch")
        receipt = {"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                   "sha256": sha.hexdigest(), "md5": md5.hexdigest(), "bytes": count,
                   "http_headers": headers}
        os.replace(part, destination)
        write_json(receipt_path, receipt)
        return receipt
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def normalize_fasta(source: Path, output: Path, identifier_map: Path, resource_id: str) -> dict:
    """Uppercase IUPAC DNA, retain every record/base and map every source ID.

    Source order is preserved. Duplicate accessions are rejected. Sequences are
    neither deduplicated nor filtered. Gzip CRC and EOF are verified by reading
    the entire stream. Only normalized output headers are replaced.
    """
    require(bool(RESOURCE_ID.fullmatch(resource_id)), "invalid resource_id")
    output.parent.mkdir(parents=True, exist_ok=True)
    identifier_map.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if source.suffix == ".gz" else Path.open
    lengths, seen = [], set()
    ambiguous = lowercase = total = 0
    source_header = None
    sequence = []
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        fasta_temp, map_temp = Path(temp) / "normalized.fasta", Path(temp) / "identifiers.tsv"
        with fasta_temp.open("w", encoding="ascii", newline="\n") as dst, map_temp.open("w", encoding="utf-8", newline="") as ids:
            writer = csv.DictWriter(ids, fieldnames=["analysis_id", "source_id", "source_header", "length_nt", "sequence_sha256"], delimiter="\t", lineterminator="\n")
            writer.writeheader()

            def emit():
                nonlocal total, ambiguous, lowercase
                require(source_header is not None and bool(sequence), "empty FASTA record")
                original = "".join(sequence)
                seq = original.upper()
                require(set(seq) <= DNA, "non-IUPAC DNA in FASTA")
                source_id = source_header.split()[0]
                require(source_id not in seen, "duplicate FASTA accession")
                seen.add(source_id)
                analysis_id = f"{resource_id}__{len(lengths) + 1:08d}"
                dst.write(f">{analysis_id}\n")
                for start in range(0, len(seq), 80):
                    dst.write(seq[start:start + 80] + "\n")
                writer.writerow({"analysis_id": analysis_id, "source_id": source_id, "source_header": source_header,
                                 "length_nt": len(seq), "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest()})
                lengths.append(len(seq))
                total += len(seq)
                ambiguous += sum(base not in "ACGT" for base in seq)
                lowercase += sum(base.islower() for base in original)

            with opener(source, "rt", encoding="ascii") as src:
                for raw in src:
                    line = raw.strip()
                    if not line:
                        continue
                    if line.startswith(">"):
                        if source_header is not None:
                            emit()
                        source_header, sequence = line[1:], []
                        require(bool(source_header), "empty FASTA header")
                    else:
                        require(source_header is not None, "sequence before FASTA header")
                        sequence.append(line)
                if source_header is not None:
                    emit()
            require(bool(lengths), "no FASTA records")
        for temp_path, destination in [(fasta_temp, output), (map_temp, identifier_map)]:
            if destination.exists():
                require(digest(destination) == digest(temp_path), "normalization would overwrite different artifact")
            else:
                shutil.copyfile(temp_path, destination)
    lengths.sort()
    return {"record_count": len(lengths), "total_bases": total, "ambiguous_bases": ambiguous,
            "lowercase_bases_in_source": lowercase, "minimum_length": lengths[0], "maximum_length": lengths[-1],
            "median_length_numerator": lengths[(len(lengths) - 1) // 2] + lengths[len(lengths) // 2],
            "median_length_denominator": 2, "source_sha256": digest(source), "fasta_sha256": digest(output),
            "identifier_map_sha256": digest(identifier_map), "normalization": "SOURCE_ORDER_ALL_RECORDS_UPPERCASE_IUPAC_DNA_NO_FILTER_NO_DEDUPLICATION"}


def build_database(fasta: Path, directory: Path, resource_id: str, taxid: int) -> dict:
    """Build an isolated species/resource database. Never execute blastn."""
    require(bool(RESOURCE_ID.fullmatch(resource_id)) and taxid > 0, "database identity invalid")
    require(not directory.exists(), "database directory already exists")
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent) as temp:
        temporary = Path(temp)
        command = ["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-parse_seqids", "-blastdb_version", "5", "-taxid", str(taxid), "-title", resource_id, "-out", str(temporary / "sequences")]
        completed = subprocess.run(command, text=True, capture_output=True)
        require(completed.returncode == 0, "makeblastdb failed: " + completed.stderr)
        files = sorted(p for p in temporary.iterdir() if p.is_file())
        require(bool(files), "database builder produced no index")
        directory.mkdir()
        for path in files:
            shutil.copyfile(path, directory / path.name)
    info = subprocess.run(["blastdbcmd", "-db", str(directory / "sequences"), "-info"], text=True, capture_output=True, check=True)
    return {"tool": subprocess.check_output(["makeblastdb", "-version"], text=True).strip(),
            "command": command, "stdout": completed.stdout, "stderr": completed.stderr,
            "database_info": info.stdout, "index_sha256": {p.name: digest(p) for p in sorted(directory.iterdir()) if p.is_file()},
            "taxid_interpretation": "SOURCE_SPECIES_METADATA_NOT_CONTAMINATION_EXCLUSION", "searches_executed": False}


def assessment_change(preliminary: str | None, final: str) -> str:
    states = ["UNASSESSABLE", "PARTIALLY_ASSESSABLE", "ASSESSABLE"]
    require(final in states, "final assessability vocabulary")
    if not preliminary:
        return "RESOLVED_FROM_UNKNOWN"
    require(preliminary in states, "preliminary assessability vocabulary")
    return "UNCHANGED" if preliminary == final else "UPGRADED" if states.index(final) > states.index(preliminary) else "DOWNGRADED"


def annotation_consistency(root: Path, resource: dict, selection: dict) -> dict:
    """Check source identifiers and preserve complex annotation limitations.

    This verifies the resource's own annotation, not biological contamination,
    expression, transcript identity or functional effect. Exceptional GFF rows
    are retained explicitly and must not support automatic locus promotion.
    """
    folder = (root / resource["fasta_path"]).parent
    with (root / resource["identifier_map_path"]).open(encoding="utf-8", newline="") as stream:
        identifiers = list(csv.DictReader(stream, delimiter="\t"))
    require(len(identifiers) == resource["quality"]["record_count"], "identifier map count mismatch")
    annotation = folder / "original" / next(f["name"] for f in selection["files"] if f["role"] == "annotation")
    result = {"annotation_sha256": digest(annotation), "fasta_records": len(identifiers)}
    if selection["kind"] == "TSA":
        accessions, taxids = [], set()
        with gzip.open(annotation, "rt", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("VERSION "):
                    accessions.append(line.split()[1])
                taxon = re.search(r'/db_xref="taxon:(\d+)"', line)
                if taxon:
                    taxids.add(int(taxon[1]))
        source_ids = set()
        for row in identifiers:
            accession = re.search(r"[A-Z]{4}\d{8}\.\d+", row["source_id"])
            require(accession is not None, "TSA versioned source accession absent")
            source_ids.add(accession[0])
        require(len(accessions) == len(set(accessions)) == len(identifiers) and set(accessions) == source_ids, "TSA FASTA and annotation accession sets differ")
        require(taxids == {selection["taxid"]}, "TSA annotation taxonomy mismatch")
        return result | {"annotation_records": len(accessions), "exact_accession_set_equality": True, "taxids": sorted(taxids), "status": "PASS", "coordinate_anomaly_count": 0}
    report = folder / "original" / next(f["name"] for f in selection["files"] if f["role"] == "assembly_report")
    contigs = set()
    for line in report.read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            columns = line.split("\t")
            require(len(columns) >= 9, "malformed assembly report")
            contigs.update(value for value in [columns[0], columns[4], columns[6]] if value != "na")
    transcripts, proteins, feature_contigs = set(), set(), set()
    anomalies, count = [], 0
    with gzip.open(annotation, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#") or not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            require(len(columns) == 9, "malformed GFF row")
            start, end = int(columns[3]), int(columns[4])
            if not 1 <= start <= end:
                anomalies.append(line.rstrip("\n"))
            feature_contigs.add(columns[0])
            transcripts.update(re.findall(r"(?:^|;)transcript_id=([^;]+)", columns[8]))
            proteins.update(re.findall(r"(?:^|;)protein_id=([^;]+)", columns[8]))
            count += 1
    require(feature_contigs <= contigs, "GFF contig not in own assembly report")
    if selection["kind"] == "RNA":
        missing = {row["source_id"] for row in identifiers} - transcripts
    else:
        source_proteins = set()
        for row in identifiers:
            protein = re.search(r"\[protein_id=([^]]+)\]", row["source_header"])
            require(protein is not None, "CDS source protein identifier absent")
            source_proteins.add(protein[1])
        missing = source_proteins - proteins
    require(not missing, "FASTA identifier missing from own annotation")
    return result | {"gff_features": count, "gff_contigs": len(feature_contigs), "all_gff_contigs_in_assembly_report": True,
                     "annotation_identifier_coverage": "ALL_MATCHED", "coordinate_anomaly_count": len(anomalies), "coordinate_anomalies": anomalies,
                     "status": "SOURCE_ANNOTATION_REVIEW_REQUIRED" if anomalies else "PASS"}


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def materialize(root: Path, inventory: dict, resources: list[dict]) -> dict:
    """Publish traceable CP1 progress with final assessments pending G1 review.

    Gaps derived from completed metadata queries are source-scoped. Retrieval,
    taxonomy or resource eligibility uncertainty remains pending, and never
    becomes a fabricated negative search result.
    """
    certificate = verify_g0(root)
    require(inventory == json.loads((root / INVENTORY).read_text("utf-8")), "inventory differs from persisted input")
    require(inventory["g0_certificate_sha256"] == digest(root / G0_PATH), "inventory G0 binding mismatch")
    panel = list(csv.DictReader((root / "config/nb04_nto_panel.tsv").open(encoding="utf-8"), delimiter="\t"))
    taxa = {r["organism_id"]: r for r in inventory["organisms"]}
    require(set(taxa) == {r["organism_id"] for r in panel}, "inventory/panel identity mismatch")
    require(len(taxa) == len(inventory["organisms"]), "duplicate inventory organism")
    require(len({r["resource_id"] for r in resources}) == len(resources), "duplicate resource_id")
    selected = {r["resource_id"]: r for r in inventory["selected_resources"]}
    require(len(selected) == len(inventory["selected_resources"]), "duplicate selected resource")
    for resource in resources:
        require(resource["resource_id"] in selected, "resource outside frozen inventory selection")
        choice = selected[resource["resource_id"]]
        require(resource["selection_sha256"] == hashlib.sha256(json_bytes(choice)).hexdigest(), "resource selection binding mismatch")
        for key in ["organism_id", "scientific_name", "taxid", "accession_version", "release"]:
            require(resource[key] == choice[key], "resource identity differs from frozen selection: " + key)
        require(datetime.fromisoformat(resource["acquired_utc"]) > datetime.fromisoformat(certificate["registered_utc"]), "resource acquired before G0")
        oid = resource["organism_id"]
        require(oid in taxa and taxa[oid]["taxonomy_status"] == "EXACT_SPECIES_RESOLVED", "resource taxonomy unresolved")
        require(int(resource["taxid"]) == taxa[oid]["taxid"], "resource taxonomy incompatible")
        require(taxa[oid]["ecological_panel_tier"] in {"CORE", "EXTENDED"}, "unadopted conditional or excluded resource")
        require(relative_path(root, resource["fasta_path"]).is_relative_to((root / "data/external/nto").resolve()), "resource payload outside nto directory")
        for relative, expected in resource["artifacts_sha256"].items():
            require(relative_path(root, relative).is_relative_to((root / "data/external/nto").resolve()), "resource artifact outside nto directory")
            require(digest(relative_path(root, relative)) == expected, "resource artifact mismatch: " + relative)
    manifest = {"schema_version": 1, "stage": "NB04_CP1_RESOURCE_INVENTORY_AND_FREEZE", "status": "RESOURCE_LAYER_MATERIALIZED_G1_PENDING",
                "g0_certificate_sha256": digest(root / G0_PATH), "g0_certified_artifacts": certificate["certified_artifacts"],
                "inventory_sha256": digest(root / INVENTORY), "resources": sorted(resources, key=lambda r: r["resource_id"]),
                "database_architecture": "ONE_DATABASE_PER_SPECIES_RESOURCE_SEQUENCE_TYPE_VERSION",
                "alignment_selection_rule_id": "NB04_TUNING_QA_CONFIG_HASH_ORDER_HOLDOUT_V1",
                "search_configuration": None, "search_calibration": None,
                "G1": "NOT_DECLARED", "informative_calibration": "NOT_EXECUTED", "real_nto_searches": "NOT_EXECUTED"}
    write_json(root / MANIFEST, manifest)
    manifest_hash = digest(root / MANIFEST)
    registry_rows = []
    for resource in sorted(resources, key=lambda r: r["resource_id"]):
        registry_rows.append({key: resource[key] for key in ["resource_id", "organism_id", "scientific_name", "taxid", "accession_version", "release", "resource_tier", "resource_record_type", "annotation_status", "fasta_path", "source_url", "acquired_utc"]} | {
            "fasta_sha256": resource["quality"]["fasta_sha256"], "record_count": resource["quality"]["record_count"], "total_bases": resource["quality"]["total_bases"],
            "limitations": serialize_multivalue(resource["limitations"]), "certification_status": "PENDING_G1"})
    write_tsv(root / REGISTRY, registry_rows, ["resource_id", "organism_id", "scientific_name", "taxid", "accession_version", "release", "resource_tier", "resource_record_type", "annotation_status", "fasta_path", "source_url", "acquired_utc", "fasta_sha256", "record_count", "total_bases", "limitations", "certification_status"])
    assessments, limitations = [], []
    for receptor in panel:
        oid = receptor["organism_id"]
        available = [r for r in resources if r["organism_id"] == oid]
        inv = taxa[oid]
        if receptor["ecological_panel_tier"] not in {"CORE", "EXTENDED"}:
            final, basis, limits = "", "OUTSIDE_ADOPTED_RESOURCE_SCOPE", ["ECOLOGICAL_EXCLUSION_OR_CONDITIONAL_INCLUSION_UNRESOLVED"]
        elif inv["taxonomy_status"] != "EXACT_SPECIES_RESOLVED" or inv["inventory_status"] != "COMPLETE_QUERIED_SOURCES":
            final, basis, limits = "", "INSUFFICIENT_INVENTORY_EVIDENCE", ["TAXONOMY_OR_INVENTORY_UNRESOLVED"]
        elif available:
            final = "ASSESSABLE" if any(r["adequate_annotated_transcript_set"] for r in available) else "PARTIALLY_ASSESSABLE"
            basis = "ACQUIRED_FULL_RESOURCE_INTEGRITY_AND_SOURCE_METADATA"
            limits = sorted({x for r in available for x in r["limitations"]})
        elif inv["resource_disposition"] == "NO_USABLE_RESOURCE_DETECTED_IN_QUERIED_SOURCES":
            final, basis, limits = "UNASSESSABLE", "COMPLETED_NCBI_METADATA_QUERY_SNAPSHOT", ["RESOURCE_UNAVAILABLE_IN_QUERIED_SOURCES", "NOT_EVIDENCE_OF_GLOBAL_RESOURCE_ABSENCE"]
        else:
            final, basis, limits = "", "RESOURCE_ACQUISITION_OR_ELIGIBILITY_PENDING", ["FINAL_ASSESSABILITY_PENDING"]
        assessment = {"organism_id": oid, "preliminary_computational_assessability": receptor["preliminary_computational_assessability"],
                      "preliminary_assessability_source": receptor["preliminary_assessability_source"], "final_computational_assessability": final,
                      "final_assessability_source": "CP1_RESOURCE_REVIEW_PENDING_G1" if final else "",
                      "assessment_change_status": assessment_change(receptor["preliminary_computational_assessability"] or None, final) if final else "",
                      "resource_ids": serialize_multivalue(sorted(r["resource_id"] for r in available)), "assessment_basis": basis,
                      "assessment_limitations": serialize_multivalue(limits), "cp1_run_record": RUN_RECORD,
                      "policy_hash": certificate["certified_artifacts"]["config/nb04_nto_policy.yaml"]["sha256"], "resource_manifest_hash": manifest_hash}
        assessments.append(assessment)
        for limitation in limits:
            limitations.append({"organism_id": oid, "resource_ids": assessment["resource_ids"], "limitation": limitation, "ecological_panel_tier": receptor["ecological_panel_tier"]})
    write_tsv(root / ASSESSABILITY, assessments, list(assessments[0]))
    quality_rows = [{"resource_id": r["resource_id"], **r["quality"], "sequence_data_quality": "UNKNOWN", "gene_space_completeness": "SOURCE_METRICS_ONLY_NOT_INFERRED_FROM_FILE_INTEGRITY"} for r in resources]
    write_tsv(root / CP1 / "resource_quality.tsv", quality_rows, list(quality_rows[0]) if quality_rows else ["resource_id"])
    write_tsv(root / CP1 / "limitations.tsv", limitations, ["organism_id", "resource_ids", "limitation", "ecological_panel_tier"])
    summary = {"stage": "NB04_CP1", "status": "PARTIAL_PENDING_CALIBRATION_AND_G1_REVIEW", "G0": "PASS", "G1": "NOT_DECLARED",
               "resource_count": len(resources), "organism_count": len(taxa), "assessments_materialized": sum(bool(r["final_computational_assessability"]) for r in assessments),
               "assessments_certified": False, "informative_calibration": "NOT_EXECUTED", "real_nto_searches": "NOT_EXECUTED",
               "pending": ["B4_A1_COMPLETE_PRIOR_FREEZE_WITH_JUSTIFIED_NUMERIC_TOLERANCES", "SEARCH_SENSITIVITY_CALIBRATION", "SEARCH_CONFIGURATION_SELECTION_AND_FREEZE", "QUALIFYING_RECORD_TRUNCATION_DEMONSTRATION", "G1_EXTERNAL_QUALIFIED_HUMAN_REVIEW"],
               "nb04_cp1_repro_profile": "NOT_ADDED_TO_G0_CERTIFIED_CONFIG", "environment_checkpoint_checked": "nb04_cp0"}
    write_json(root / CP1 / "cp1_summary.json", summary)
    outputs = [MANIFEST, REGISTRY, ASSESSABILITY, CP1 + "/resource_quality.tsv", CP1 + "/limitations.tsv", CP1 + "/cp1_summary.json"]
    run_manifest = {"stage": "NB04_CP1", "G1": "NOT_DECLARED", "inputs_sha256": {G0_PATH: digest(root / G0_PATH), INVENTORY: digest(root / INVENTORY)},
                    "implementation_sha256_lf": {p: digest(root / p, normalized=True) for p in ["src/zeaguard/nb04_resources.py", "scripts/run_nb04_cp1.py", "scripts/inventory_nb04_cp1.py"]},
                    "outputs_sha256": {p: digest(root / p) for p in outputs}, "resource_manifest_sha256": manifest_hash,
                    "execution_metadata": "execution_metadata.json", "certification_status": "NOT_CERTIFIED"}
    write_json(root / CP1 / "run_manifest.json", run_manifest)
    verify_g0(root)
    return summary
