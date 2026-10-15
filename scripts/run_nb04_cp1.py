"""Prepare a pinned CP1 inventory, acquire selected resources, or verify them.

No blastn invocation, calibration, biological disposition or G1 certification.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zeaguard import nb04_resources as r

BASE = "data/external/nto/cp1_20261015"
SELECTION = {
    "APIS_MELLIFERA": ("AM_GCF003254395_2_RNA", "GCF_003254395.2", "RNA"),
    "ZEA_MAYS": ("ZM_GCF902167145_1_RNA", "GCF_902167145.1", "RNA"),
    "RHOPALOSIPHUM_MAIDIS": ("RM_GCF003676215_2_RNA", "GCF_003676215.2", "RNA"),
    "TETRAGONISCA_ANGUSTULA": ("TA_GCA036937485_2_CDS", "GCA_036937485.2", "CDS"),
    "ORIUS_INSIDIOSUS": ("OI_GCYL01_TSA", "GCYL00000000.1", "TSA"),
    "PEREGRINUS_MAIDIS": ("PM_GKDL01_TSA", "GKDL00000000.1", "TSA"),
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("https://sra-download.ncbi.nlm.nih.gov/"):
                self.urls.append(href)


def prepare() -> dict:
    r.verify_g0(ROOT)
    meta = ROOT / BASE / "metadata"
    raw = json.loads((meta / "inventory.json").read_text("utf-8"))
    r.require(len(raw) == 21, "inventory incomplete")
    organisms, selections = [], []
    receipts = {str(p.relative_to(ROOT)): json.loads(p.read_text("utf-8")) for p in sorted(meta.glob("*.receipt.json"))}
    for entry in raw:
        oid = entry["organism_id"]
        counts = {k: int(v["count"]) if v else None for k, v in entry["counts"].items()}
        complete = entry.get("assembly_inventory_status") == "COMPLETE_QUERIED_NCBI_DATASETS_SNAPSHOT" and all(counts.get(k) is not None for k in ["mrna", "tsa_master"])
        item = {k: entry[k] for k in ["organism_id", "scientific_name", "taxid", "taxonomy_status", "ecological_panel_tier", "preliminary_assessability"]}
        item.update({"taxonomy_evidence": entry["taxonomy_report"], "inventory_status": "COMPLETE_QUERIED_SOURCES" if complete else "PENDING_TAXONOMY_OR_RETRIEVAL",
                     "queried_source_counts": counts, "assemblies": [{"accession": a["accession"], "organism": a["organism"], "assembly_info": {k: a["assembly_info"][k] for k in ["assembly_name", "assembly_level", "assembly_status", "release_date", "refseq_category"] if k in a["assembly_info"]}, "annotation_info": a.get("annotation_info"), "assembly_stats": a.get("assembly_stats")} for a in entry["assembly_reports"]],
                     "tsa_summaries": entry.get("tsa_summaries"),
                     "resource_disposition": "SELECTED_PENDING_ACQUISITION" if oid in SELECTION else "OUTSIDE_ADOPTED_SCOPE" if entry["ecological_panel_tier"] not in {"CORE", "EXTENDED"} else "NO_USABLE_RESOURCE_DETECTED_IN_QUERIED_SOURCES" if complete and not entry["assembly_reports"] and counts["tsa_master"] == 0 and counts["mrna"] == 0 else "INSUFFICIENT_ELIGIBILITY_EVIDENCE"})
        # A single gene submission is retained as a limitation, not a species transcriptome.
        if oid == "CHRYSOPERLA_EXTERNA":
            item["resource_disposition"] = "INSUFFICIENT_ELIGIBILITY_EVIDENCE_SINGLE_MRNA"
        organisms.append(item)
        if oid not in SELECTION:
            continue
        r.require(entry["taxonomy_status"] == "EXACT_SPECIES_RESOLVED", "selected species unresolved")
        rid, accession, kind = SELECTION[oid]
        selection = {"organism_id": oid, "resource_id": rid, "taxid": entry["taxid"], "scientific_name": entry["scientific_name"], "accession_version": accession, "kind": kind, "files": []}
        if kind in {"RNA", "CDS"}:
            report = next(a for a in entry["assembly_reports"] if a["accession"] == accession)
            r.require(report["organism"]["tax_id"] == entry["taxid"], "assembly taxonomy mismatch")
            folder = r.assembly_ftp(report)
            checksums = meta / (oid + "_md5checksums.txt")
            r.download(folder + "/md5checksums.txt", checksums)
            md5 = {line.split()[1].removeprefix("./"): line.split()[0] for line in checksums.read_text().splitlines()}
            prefix = accession + "_" + report["assembly_info"]["assembly_name"]
            primary = prefix + ("_rna.fna.gz" if kind == "RNA" else "_cds_from_genomic.fna.gz")
            for role, name in [("sequence", primary), ("annotation", prefix + "_genomic.gff.gz"), ("assembly_report", prefix + "_assembly_report.txt")]:
                r.require(name in md5, "source file not in official checksum catalog")
                selection["files"].append({"role": role, "url": folder + "/" + name, "name": name, "source_md5": md5[name]})
            selection.update({"release": report["annotation_info"]["name"], "release_date": report["annotation_info"]["release_date"], "source_metadata": report,
                              "checksum_catalog": {"path": str(checksums.relative_to(ROOT)), "sha256": r.digest(checksums)},
                              "selection_basis": "PLAN F.1 annotated assembly linked full RNA preferred" if kind == "RNA" else "PLAN F.1 annotated CDS fallback. Official assembly directory has no full RNA FASTA."})
        else:
            summaries = entry["tsa_summaries"]["result"]
            summary = next(summaries[uid] for uid in summaries["uids"] if summaries[uid]["accessionversion"] == accession)
            r.require(summary["taxid"] == entry["taxid"], "TSA taxonomy mismatch")
            version = re.search(r"\|([A-Z]{4}\d{2})000000$", summary["extra"])
            r.require(version is not None, "TSA project version unresolved")
            project = version[1]
            page = meta / (project + "_pinned_download.html")
            r.download(f"https://www.ncbi.nlm.nih.gov/Traces/wgs/{project}?display=download", page)
            links = Links()
            links.feed(page.read_text("utf-8"))
            for role, suffix in [("sequence", ".fsa_nt.gz"), ("annotation", ".gbff.gz")]:
                urls = sorted({u for u in links.urls if u.endswith(suffix) and f"/{project}/" in u})
                r.require(len(urls) == 1, "TSA pinned download ambiguous")
                selection["files"].append({"role": role, "url": urls[0], "name": urls[0].split("/")[-1], "source_md5": None})
            selection.update({"release": project, "release_date": summary["updatedate"], "expected_record_count": summary["slen"], "source_metadata": summary,
                              "source_page": {"url": f"https://www.ncbi.nlm.nih.gov/Traces/wgs/{project}?display=download", "sha256": r.digest(page)},
                              "selection_basis": "PLAN F.1 whole species TSA as a fragmented transcript resource, with explicit orientation, redundancy and contamination limits."})
        selections.append(selection)
    inventory = {"schema_version": 1, "run_id": "NB04_CP1_RESOURCE_20261015_V1", "g0_certificate_sha256": r.digest(ROOT / r.G0_PATH),
                 "metadata_acquisition_after_g0": True, "organisms": organisms, "selected_resources": sorted(selections, key=lambda x: x["resource_id"]),
                 "source_receipts": receipts, "scope": "CORE_AND_EXTENDED_ADOPTED_RECEPTORS. CONDITIONAL_AND_EXCLUDED_METADATA_ONLY",
                 "scientific_decision_role": False}
    r.require(not (ROOT / r.INVENTORY).exists(), "inventory already frozen. Verify existing campaign instead of re-resolving latest metadata")
    r.write_json(ROOT / r.INVENTORY, inventory)
    return {"organisms": len(organisms), "selected_resources": len(selections), "inventory_sha256": r.digest(ROOT / r.INVENTORY)}


def acquire() -> dict:
    r.verify_g0(ROOT)
    inventory = json.loads((ROOT / r.INVENTORY).read_text("utf-8"))
    resources = []
    for selection in inventory["selected_resources"]:
        rid = selection["resource_id"]
        folder = ROOT / BASE / rid
        folder.mkdir(parents=True, exist_ok=True)
        processing = folder / "processing_record.json"
        if processing.exists():
            resource = json.loads(processing.read_text("utf-8"))
            r.require(resource["selection_sha256"] == __import__("hashlib").sha256(r.json_bytes(selection)).hexdigest(), "resource selection changed")
            for p, h in resource["artifacts_sha256"].items():
                r.require(r.digest(ROOT / p) == h, "processed resource changed")
        else:
            receipts, artifacts = {}, {}
            for item in selection["files"]:
                destination = folder / "original" / item["name"]
                receipts[item["role"]] = r.download(item["url"], destination, expected_md5=item["source_md5"])
                artifacts[str(destination.relative_to(ROOT))] = r.digest(destination)
                artifacts[str(destination.with_suffix(destination.suffix + ".receipt.json").relative_to(ROOT))] = r.digest(destination.with_suffix(destination.suffix + ".receipt.json"))
                if item["role"] == "sequence":
                    source = destination
            fasta, idmap = folder / "normalized.fasta", folder / "identifier_map.tsv"
            quality = r.normalize_fasta(source, fasta, idmap, rid)
            if "expected_record_count" in selection:
                r.require(quality["record_count"] == selection["expected_record_count"], "TSA record count differs from pinned master")
            database = r.build_database(fasta, folder / "blastdb", rid, selection["taxid"])
            r.write_json(folder / "database_build.json", database)
            for p in [fasta, idmap, folder / "database_build.json", *sorted((folder / "blastdb").iterdir())]:
                artifacts[str(p.relative_to(ROOT))] = r.digest(p)
            kind = selection["kind"]
            limitations = ["INTRASPECIFIC_DIVERSITY_NOT_REPRESENTED", "LIFE_STAGE_TISSUE_EXPRESSION_COVERAGE_UNRESOLVED", "CONTAMINATION_NOT_EXCLUDED", "NO_FUNCTIONAL_EFFECT_INFERENCE_FROM_SEQUENCE"]
            limitations += ["MIXED_CURATED_AND_PREDICTED_RNA", "ANNOTATION_IS_NOT_EXPRESSION_EVIDENCE"] if kind == "RNA" else ["CDS_ONLY_UTRS_AND_NONCODING_TRANSCRIPTS_NOT_REPRESENTED"] if kind == "CDS" else ["TSA_FRAGMENTATION_REDUNDANCY_ORIENTATION_UNCERTAINTY", "GENE_ASSIGNMENT_UNAVAILABLE"]
            if selection["organism_id"] == "ZEA_MAYS":
                limitations.append("B73_REFERENCE_DOES_NOT_REPRESENT_PARANA_COMMERCIAL_HYBRIDS")
            resource = {k: selection[k] for k in ["organism_id", "resource_id", "scientific_name", "taxid", "accession_version", "release", "release_date", "selection_basis"]}
            resource.update({"source_url": next(f["url"] for f in selection["files"] if f["role"] == "sequence"),
                             "selection_sha256": __import__("hashlib").sha256(r.json_bytes(selection)).hexdigest(), "acquired_utc": receipts["sequence"]["retrieved_utc"],
                             "resource_tier": "TRANSCRIPT_TIER", "resource_record_type": "TSA_FRAGMENT" if kind == "TSA" else "PREDICTED_TRANSCRIPT" if kind == "CDS" else "OTHER",
                             "record_type_notes": "Full assembly RNA mixes curated, predicted and noncoding RNA. Per-record accession retained in identifier map." if kind == "RNA" else "CDS subset" if kind == "CDS" else "Whole TSA project",
                             "annotation_status": "UNCHARACTERIZED" if kind == "TSA" else "ANNOTATED",
                             "adequate_annotated_transcript_set": kind == "RNA", "fasta_path": str(fasta.relative_to(ROOT)), "identifier_map_path": str(idmap.relative_to(ROOT)),
                             "database_prefix": str((folder / "blastdb/sequences").relative_to(ROOT)), "quality": quality,
                             "limitations": sorted(set(limitations)), "acquisition_receipts": receipts, "artifacts_sha256": artifacts,
                             "g0_certificate_sha256": r.digest(ROOT / r.G0_PATH)})
            r.write_json(processing, resource)
        consistency = r.annotation_consistency(ROOT, resource, selection)
        resource["annotation_consistency"] = consistency
        resource["quality"]["annotation_consistency_status"] = consistency["status"]
        resource["quality"]["annotation_coordinate_anomaly_count"] = consistency["coordinate_anomaly_count"]
        if consistency["status"] != "PASS":
            resource["limitations"] = sorted(set(resource["limitations"]) | {"SOURCE_ANNOTATION_COMPLEX_FEATURE_REVIEW_REQUIRED_NO_AUTOMATIC_LOCUS_PROMOTION"})
        # Preserve the original processing receipt as a distinct execution object.
        resource["artifacts_sha256"][str(processing.relative_to(ROOT))] = r.digest(processing)
        resources.append(resource)
        print(json.dumps({"resource_id": rid, "records": resource["quality"]["record_count"], "bases": resource["quality"]["total_bases"]}), flush=True)
    summary = r.materialize(ROOT, inventory, resources)
    r.write_json(ROOT / r.CP1 / "execution_metadata.json", {"executed_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()),
        "python": sys.version, "run_manifest_sha256": r.digest(ROOT / r.CP1 / "run_manifest.json"), "command": sys.argv})
    return summary


def verify() -> dict:
    r.verify_g0(ROOT)
    manifest = json.loads((ROOT / r.MANIFEST).read_text("utf-8"))
    r.require(manifest["inventory_sha256"] == r.digest(ROOT / r.INVENTORY), "inventory hash mismatch")
    for resource in manifest["resources"]:
        for p, h in resource["artifacts_sha256"].items():
            r.require(r.digest(r.relative_path(ROOT, p)) == h, "resource hash mismatch: " + p)
    run = json.loads((ROOT / r.CP1 / "run_manifest.json").read_text("utf-8"))
    for p, h in run["outputs_sha256"].items():
        r.require(r.digest(ROOT / p) == h, "CP1 output hash mismatch: " + p)
    for p, h in run["implementation_sha256_lf"].items():
        r.require(r.digest(ROOT / p, normalized=True) == h, "CP1 implementation changed: " + p)
    return {"integrity": "PASS", "resources": len(manifest["resources"]), "G1": "NOT_DECLARED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "acquire", "verify"])
    args = parser.parse_args()
    print(json.dumps({"prepare": prepare, "acquire": acquire, "verify": verify}[args.action](), sort_keys=True))
