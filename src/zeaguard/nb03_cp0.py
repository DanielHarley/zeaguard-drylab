"""NB03 checkpoint 0: operational BicC reference, observed sequence differences, BicC-like discovery, benchmark reconstruction.

No candidate window is generated, nothing is ranked or recommended. The outputs under
``results/bioinformatics/nb03/cp0/`` are gitignored; ``run_manifest.json`` carries the input and output hashes.
Run with ``python -m zeaguard.nb03_cp0``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from zeaguard import nb02_reference, nb03_benchmark, nb03_discovery, nb03_reference
from zeaguard.nb01_dsrnase_investigation import CommandLog, write_tsv

# Tried before the user provided the primary 2022 Table S1 and not readable. Recorded, not bypassed; no further web search is done.
ATTEMPTED_UNRETRIEVED_SOURCES = (
    {"source_url": "https://www.biorxiv.org/content/10.1101/2022.01.17.476645.full.pdf", "outcome": "HTTP 403 (bot protection)",
     "intended_role": "2022 preprint: BicC dsRNA primers, fragment length, protocol"},
    {"source_url": "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1002%2Fps.6937&file=ps6937-sup-0001-Supinfo.txt",
     "outcome": "HTTP 403 (bot protection)", "intended_role": "2022 article supplement (ps6937-sup-0001-Supinfo.txt)"},
    {"source_url": "https://doi.org/10.1002/ps.6937", "outcome": "HTTP 403 (bot protection)", "intended_role": "2022 article main text"},
    {"source_url": "https://www.biorxiv.org/content/10.1101/2022.01.17.476645v1.full", "outcome": "HTTP 403 (fetch tool)",
     "intended_role": "2022 preprint full text"},
    {"source_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1101/2022.01.17.476645", "outcome": "indexed, no full text (inEPMC=N)",
     "intended_role": "open full text of the preprint or the article"},
)


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git(root: Path, *arguments: str) -> str:
    process = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False)
    return process.stdout.strip() if process.returncode == 0 else "unavailable"


def evaluate_g0(reference: dict[str, Any], benchmark: dict[str, Any] | None, benchmark_error: str | None,
                discovery: dict[str, Any], differences_written: bool) -> dict[str, Any]:
    """G0 as defined in the plan, updated for the primary 2022 Table S1.

    A 372/373 disagreement between the published length and the length the published primers define is a documented
    publication inconsistency, not a blocker: it only has to be preserved explicitly. A missing primary source or a
    primer mapping that is not unique still blocks.
    """
    primary = benchmark is not None and benchmark.get("primary_2022_primers_verification") == "VERIFIED_FROM_PRIMARY_2022_TABLE_S1"
    assessment = benchmark["length_assessment"] if benchmark is not None else {}
    preserved = benchmark is not None and assessment.get("length_discrepancy_status") in ("NONE", "UNRESOLVED_PUBLICATION_INCONSISTENCY") and all(
        assessment.get(k) is not None for k in ("published_reported_body_length_nt", "reconstructed_body_length_nt"))
    conditions = {
        "1_reference_rederived_and_verifiable": all(reference["summary"]["checks"].values()),
        "2_primary_2022_primers_verified": primary,
        "3_benchmark_reconstructed_deterministically": benchmark is not None,
        "4_length_discrepancy_explicitly_preserved": preserved,
        "5_discovery_reproducible": discovery["blastn_ran"] and discovery["tblastn_ran"],
        "6_observed_sequence_differences_documented": differences_written,
        "7_units_described_for_preregistration": discovery["operational_proposed"] and discovery["positive_control_present"],
    }
    if all(conditions.values()):
        status = "G0_PASS"
    elif benchmark_error and ("exactly once" in benchmark_error or "arrangement" in benchmark_error):
        status = "G0_FAIL"
    else:
        status = "G0_PARTIAL"
    return {"status": status, "conditions": conditions,
            "length_discrepancy_status": assessment.get("length_discrepancy_status"),
            "benchmark_error": benchmark_error,
            "cp1": "CP1_READY_TO_PLAN_OR_IMPLEMENT" if status == "G0_PASS" else "CP1_BLOCKED_UNTIL_BENCHMARK_VERIFIED"}


def run_cp0(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / nb03_reference.OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    log = CommandLog()

    reference = nb03_reference.derive_reference(root, out / "raw" / "placement", log)
    operational = reference["operational"]
    differences = reference["differences"]
    nb03_reference.assert_descriptive_columns(nb03_reference.DIFFERENCE_COLUMNS)
    write_tsv(out / "observed_sequence_differences.tsv", differences, nb03_reference.DIFFERENCE_COLUMNS)

    benchmark, benchmark_error, table = None, None, None
    try:
        table = nb03_benchmark.read_table_s1_2022(root)
        benchmark = nb03_benchmark.reconstruct(reference, table)
        benchmark["corroboration_2023"] = nb03_benchmark.corroborate_with_2023(root, table)
    except nb03_benchmark.NB03BenchmarkError as exc:
        benchmark_error = str(exc)

    search = nb03_discovery.search_settings(root)
    database = nb03_discovery.build_database(root, out / "raw", log)
    hits = nb03_discovery.run_searches(operational["_cds"], operational["_protein"], database["database"], search, out / "raw", log)
    rows = nb03_discovery.summarise_records(hits["blastn"], hits["tblastn"], len(operational["_cds"]), len(operational["_protein"]))
    selected = nb03_discovery.select_follow_up(rows, nb03_reference.OPERATIONAL_ACCESSION)
    followed = nb03_discovery.follow_up(root, rows, hits["tblastn"], operational["_protein"], selected,
                                        nb03_reference.OPERATIONAL_ACCESSION, out / "raw" / "followup", log)
    tables = nb03_discovery.write_tables(out, rows, followed)

    summary = dict(reference["summary"])
    summary["observed_sequence_differences"] = {
        "n": len(differences), "read_support_status": nb03_reference.READ_SUPPORT_STATUS,
        "nature": "unresolved (polymorphism, isoform, assembly difference, sequencing error or other); not established at CP0",
        "positions": [d["cds_position"] for d in differences],
    }
    summary["known_bicc_compatible_proposal"] = {
        "status": "PROPOSED_NOT_FROZEN",
        "members": [nb03_reference.OPERATIONAL_ACCESSION, nb03_reference.PUBLISHED_ID],
        "other_records_flagged_for_same_locus_review": [r["accession"] for r in followed if r["review_flag"].startswith("REVIEW_AS_SAME_LOCUS")],
    }
    summary["bicc_like_proposal"] = {
        "status": "PROPOSED_NOT_FROZEN", "relationship_status": nb03_discovery.STATUS_UNRESOLVED,
        "records": [r["accession"] for r in followed if r["unit_proposal"].startswith(nb03_discovery.UNIT_LIKE)],
    }
    (out / "reference_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    benchmark_payload = benchmark if benchmark is not None else {"error": benchmark_error}
    (out / "benchmark_reconstruction.json").write_text(json.dumps(benchmark_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    discovery_state = {
        "blastn_ran": bool(hits["blastn_command"]), "tblastn_ran": bool(hits["tblastn_command"]),
        "operational_proposed": any(r["unit_proposal"] == nb03_discovery.UNIT_KNOWN for r in followed),
        "positive_control_present": any(r["accession"] == nb03_discovery.NB02_POSITIVE_CONTROL_RECORD for r in followed),
    }
    g0 = evaluate_g0(reference, benchmark, benchmark_error, discovery_state, True)

    outputs = ["reference_summary.json", "observed_sequence_differences.tsv", "benchmark_reconstruction.json", *tables]
    manifest = {
        "stage": "NB03 CP0 (reference, observed differences, BicC-like discovery, benchmark reconstruction; no windows, no ranking)",
        "git": {"commit": _git(root, "rev-parse", "HEAD"), "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": bool(_git(root, "status", "--porcelain"))},
        "inputs": {"tsa_file_sha256": reference["summary"]["tsa_file_sha256"],
                   "anchor_sequences_sha256": _sha256_lf(root / "data/reference/target_anchor_sequences.fasta"),
                   "anchor_table_sha256": _sha256_lf(root / "data/reference/target_anchors.tsv"),
                   "nb02_registry_sha256": _sha256_lf(root / "config/nb02_design_criteria.yaml"),
                   "nb02_pin_sha256": nb02_reference.pin_sha256(root)},
        "external_sources_provided": [table["source"]] if table else [],
        "corroborating_source": benchmark.get("corroboration_2023") if benchmark else None,
        "external_sources_attempted_not_retrieved_before_the_primary_file_was_provided": list(ATTEMPTED_UNRETRIEVED_SOURCES),
        "search_detection_limit": search, "tblastn_extra": {"seg": "no", "evalue": search["evalue_report_limit"]},
        "database": database,
        "commands": log.entries,
        "follow_up_rule": {"rule": "TBLASTN union coverage of the BicC protein >= 0.5, plus the NB02 positive-control record",
                           "class": "INSPECTION (workload), not biological", "records": selected},
        "counts": {"records_in_all_records_table": len(rows), "blastn_hsps": len(hits["blastn"]), "tblastn_hsps": len(hits["tblastn"]),
                   "followed_up": len(followed), "observed_sequence_differences": len(differences)},
        "g0": g0,
        "outputs_sha256": {name: _sha256_lf(out / name) for name in outputs},
        "not_done": ["candidate windows", "ranking", "Pareto of candidates", "shortlist", "Wet Lab hand-off", "read analysis",
                     "BLASTp against translated TSA", "protocol verification against the primary text"],
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"manifest": manifest, "reference": reference, "benchmark": benchmark, "rows": rows, "followed": followed, "g0": g0}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp0(find_project_root())
    g0 = result["g0"]
    print(f"{g0['status']} | {g0['cp1']} | length discrepancy: {g0['length_discrepancy_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
