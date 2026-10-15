"""Offline materialization of the ratified NB04 CP0 contracts and query bundle.

Only read-only Git subprocesses are used. No alignment, kmer screening, fixture
generation, acquisition, final resource selection or gate declaration exists here.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import itertools
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from zeaguard.nb04_policy import CP0ContractError, load_policy, require, validate_tables
from zeaguard.nb04_complement import CONTRACT_PATH, load_complement


QUERY_SPEC = {
    "D2-L400-0351-0750": ("DSRNASE2", "CANDIDATE", 351, 750, "5c2b656e80265d1f248fb16cca21aff092b12169c1348758d78959b3d4e5cdc3"),
    "D2-L400-0817-1216": ("DSRNASE2", "CANDIDATE", 817, 1216, "eb32cfa98180028dab7cfc045171f152d6be34658d02b3259e70857586bc9977"),
    "D2-BENCH-0814-1143": ("DSRNASE2", "REFERENCE_SET", 814, 1143, "97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179"),
    "BC-L400-1337-1736": ("BICC", "CANDIDATE", 1337, 1736, "71e0788174a9ce7884eb257924dd808f94a3f018eb38fbf70a5fd3002493344e"),
    "BC-L400-1253-1652": ("BICC", "CANDIDATE", 1253, 1652, "828dfa52251bfeefd182b698e3c5aaddfd13b0996e0d393fdda13e538cc20ad5"),
    "BC-L400-1254-1653": ("BICC", "CANDIDATE", 1254, 1653, "2281891befd9eaaecda500789892e3ea461fdcc71e0bd28ff035836a804ac12e"),
    "BC-BENCH-0215-0587": ("BICC", "REFERENCE_SET", 215, 587, "e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb"),
}
CP0 = "results/bioinformatics/nb04/cp0"
DOC_INPUT = "data/reference/nb04_cp0_documentary_inputs.json"
PROVENANCE = "data/reference/nb04_upstream_provenance.json"
RUN_RECORD = "src/workstreams/bioinformatics/runs/2026-10-14_nb04-cp0-complementary-contract-patch.md"
CP0_REQUIRED_PATHS = (
    "config/nb04_nto_policy.yaml", "config/nb04_nto_panel.tsv",
    "config/nb04_exposure_scenarios.tsv", "config/nb04_receptor_exposure.tsv",
    "data/reference/nb04_nto_queries.tsv", "data/reference/nb04_nto_queries.fasta",
    f"{CP0}/resource_landscape.tsv", CONTRACT_PATH, RUN_RECORD,
)


def cp0_repro_configuration(root: Path) -> tuple:
    """Distinguish a configured profile from the historical in-memory proposal."""
    from zeaguard.repro import load_repro_config

    cfg = load_repro_config(root / "config/repro.yaml", root / "config/repro.schema.json")
    configured = "nb04_cp0" in cfg.raw.get("checkpoint_required_paths", {})
    if configured:
        require(set(CP0_REQUIRED_PATHS) <= set(cfg.raw["checkpoint_required_paths"]["nb04_cp0"]),
                "configured CP0 profile omits contract paths")
    return cfg, configured


def check_cp0_paths(root: Path) -> list:
    """Check the effective N20 profile, with a read-only legacy proposal fallback."""
    import jsonschema
    from zeaguard.repro import ReproConfig, check_required_paths

    cfg, configured = cp0_repro_configuration(root)
    if configured:
        return check_required_paths(cfg, checkpoint="nb04_cp0")
    raw = copy.deepcopy(cfg.raw)
    raw["schema_version"] = 2
    raw.setdefault("checkpoint_required_paths", {})["nb04_cp0"] = list(CP0_REQUIRED_PATHS)
    jsonschema.validate(raw, json.loads((root / "config/repro.schema.json").read_text("utf-8")))
    return check_required_paths(ReproConfig(raw=raw, path=cfg.path), checkpoint="nb04_cp0")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def digest(path: Path, *, normalized: bool = False) -> str:
    data = path.read_bytes()
    return sha256(lf(data) if normalized else data)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def tsv_bytes(rows: list[dict]) -> bytes:
    require(bool(rows), "TSV cannot infer columns from empty data")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), f"duplicate/empty TSV header: {path}")
        rows = list(reader)
    require(all(None not in r and None not in r.values() for r in rows), f"malformed TSV: {path}")
    return rows


def read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    current = None
    for line in path.read_text("ascii").splitlines():
        if line.startswith(">"):
            current = line[1:].split()[0]
            require(current not in records, f"duplicate FASTA id: {current}")
            records[current] = ""
        elif line:
            require(current is not None, "FASTA sequence before header")
            records[current] += line
    return records


def git(root: Path, *args: str) -> bytes:
    require(args[0] in {"show", "cat-file", "merge-base", "rev-parse", "status", "branch", "ls-files"}, "CP0 permits read-only Git operations")
    try:
        return subprocess.run(["git", "-C", str(root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    except subprocess.CalledProcessError as exc:
        raise CP0ContractError(f"Git provenance check failed: {args}") from exc


def local_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and not Path(relative).is_absolute(), "artifact path outside workspace")
    return path


def verify_inputs(root: Path, registry: dict) -> dict:
    """Hash-check source artifacts, manifests, certifying commits and records."""
    observations = {}
    for name, entry in registry["artifacts"].items():
        path = local_path(root, name)
        observed = digest(path, normalized=entry["hash_mode"] == "LF_NORMALIZED")
        require(observed == entry["sha256"], f"provenance mismatch {name}: expected={entry['sha256']} observed={observed}")
        observations[name] = {"sha256": observed, "raw_sha256": digest(path), "hash_mode": entry["hash_mode"]}
    for query_id, q in registry["queries"].items():
        require(query_id in QUERY_SPEC, "unexpected provenance query")
        if query_id.startswith("D2"):
            origin = ("NB02_CP5", "data/reference/nb02_dsrnase2_candidate_regions.fasta", "74b9d6584690b95d4c8175b7d487940f2372bda6")
            selection = "data/reference/nb02_dsrnase2_candidate_regions.tsv"
        elif QUERY_SPEC[query_id][1] == "CANDIDATE":
            origin = ("NB03_CP4B", "results/bioinformatics/nb03/cp4b/shortlist.fasta", "9ca3e0903e9bee10c0708fde95241b7fa671591a")
            selection = "results/bioinformatics/nb03/cp4b/shortlist.tsv"
        else:
            origin = ("NB03_CP0_RECONSTRUCTION_CERTIFIED_BY_CP1_PIN", "results/bioinformatics/nb03/cp0/benchmark_reconstruction.json", "099f751780283fecbc63da177c113aec9f6d60d5")
            selection = ""
        require(tuple(q[k] for k in ("sequence_source_stage", "sequence_source_artifact", "upstream_repository_commit")) == origin, "query-specific origin tuple diverges from certified source")
        if QUERY_SPEC[query_id][1] == "REFERENCE_SET":
            require(q["selection_source_stage"] == "NOT_APPLICABLE" and not q["selection_source_artifact"], "benchmark cannot inherit selection")
        else:
            require(q["selection_source_stage"] == origin[0] and q["selection_source_artifact"] == selection, "selection source diverges from certified stage")
        commit = q["upstream_repository_commit"]
        require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "full upstream commit required")
        git(root, "merge-base", "--is-ancestor", commit, "HEAD")
        proof = git(root, "show", f"{commit}:{q['certification_artifact']}")
        require(sha256(lf(proof)) == q["certification_artifact_sha256_lf"], "certification artifact mismatch")
        artifact = q["sequence_source_artifact"]
        expected = registry["artifacts"][artifact]["sha256"]
        if q["certification_kind"] == "VERSIONED_BLOB":
            require(sha256(lf(git(root, "show", f"{commit}:{artifact}"))) == expected, "sequence source differs from certified Git blob")
        else:
            require(expected.encode() in proof, "source hash absent from certifying record")
        manifest_path = q["source_manifest_artifact"]
        manifest = json.loads(local_path(root, manifest_path).read_text("utf-8"))
        outputs = manifest["outputs_sha256"]
        require(outputs.get(artifact, outputs.get(Path(artifact).name)) == expected, "manifest does not bind source artifact")
        if q["selection_source_artifact"]:
            selection = q["selection_source_artifact"]
            selection_hash = registry["artifacts"][selection]["sha256"]
            require(outputs.get(selection, outputs.get(Path(selection).name)) == selection_hash, "manifest does not bind selection source")
            if q["certification_kind"] == "VERSIONED_BLOB":
                require(sha256(lf(git(root, "show", f"{commit}:{selection}"))) == selection_hash, "selection differs from certified blob")
            else:
                require(selection_hash.encode() in proof, "selection hash absent from certification record")
    require(set(registry["queries"]) == set(QUERY_SPEC), "provenance scope must contain seven exact queries")
    require(set(registry["reference_pins"]) == {"BICC", "DSRNASE2"}, "both reference pins are required")
    for target, pin in registry["reference_pins"].items():
        require(target in {"BICC", "DSRNASE2"}, "unexpected reference pin")
        require(digest(root / pin["artifact"], normalized=True) == pin["sha256_lf"], "reference pin hash mismatch")
        require(sha256(lf(git(root, "show", f"{pin['certifying_commit']}:{pin['artifact']}"))) == pin["sha256_lf"], "reference pin differs from certified blob")
    return observations


def build_bundle(root: Path, registry: dict) -> tuple[list[dict], dict[str, str]]:
    verify_inputs(root, registry)
    rows, sequences = [], {}
    for query_id in sorted(QUERY_SPEC):
        target, role, start, end, sequence_hash = QUERY_SPEC[query_id]
        source = registry["queries"][query_id]
        artifact = source["sequence_source_artifact"]
        if source["sequence_format"] == "FASTA":
            sequence = read_fasta(root / artifact)[query_id]
        else:
            sequence = json.loads((root / artifact).read_text("utf-8"))["body"]["sequence"]
        require(len(sequence) == end - start + 1 and set(sequence) <= set("ACGT"), f"query length/alphabet: {query_id}")
        require(sha256(sequence.encode("ascii")) == sequence_hash, f"sequence hash mismatch: {query_id}")
        if source["selection_source_artifact"]:
            selected = [r for r in read_tsv(root / source["selection_source_artifact"]) if r.get("candidate_id", r.get("window_id")) == query_id]
            require(len(selected) == 1, "selection missing or duplicated")
            require(selected[0]["sequence_sha256"] == sequence_hash and int(selected[0]["cds_start"]) == start and int(selected[0]["cds_end"]) == end, "selection sequence/coordinate divergence")
        seq_entry = registry["artifacts"][artifact]
        row = {
            "query_id": query_id, "target": target, "query_role": role,
            "sequence_source_stage": source["sequence_source_stage"],
            "sequence_source_artifact": artifact,
            "sequence_source_artifact_sha256": seq_entry["sha256"],
            "source_manifest_artifact": source["source_manifest_artifact"],
            "source_manifest_sha256": registry["artifacts"][source["source_manifest_artifact"]]["sha256"],
            "selection_source_stage": source["selection_source_stage"],
            "selection_source_artifact": source["selection_source_artifact"] or "",
            "selection_source_artifact_sha256": registry["artifacts"][source["selection_source_artifact"]]["sha256"] if source["selection_source_artifact"] else "",
            "upstream_repository_commit": source["upstream_repository_commit"],
            "certification_artifact": source["certification_artifact"],
            "certification_artifact_sha256_lf": source["certification_artifact_sha256_lf"],
            "sequence_sha256": sequence_hash, "length_nt": end - start + 1,
            "cds_start": start, "cds_end": end,
            "operational_coordinates": f"{start}:{end}:1_BASED_INCLUSIVE:CODING_SENSE",
            "selection_status": "SELECTED_SEQUENCE_FOR_NTO_SCREENING" if role == "CANDIDATE" else "NOT_APPLICABLE_REFERENCE_SET",
            "input_semantics": "NB04_SEQUENCE_SCREENING_INPUT",
            "query_family": target,
            "conceptual_candidate_region_id": "BICC_SECONDARY_1253_1254" if query_id in {"BC-L400-1253-1652", "BC-L400-1254-1653"} else query_id if role == "CANDIDATE" else "NOT_APPLICABLE",
            "publication_reported_length_bp": 372 if query_id == "BC-BENCH-0215-0587" else "",
            "publication_length_status": "UNRESOLVED_PUBLICATION_INCONSISTENCY" if query_id == "BC-BENCH-0215-0587" else "NOT_APPLICABLE",
            "notes": source["notes"],
        }
        rows.append(row)
        sequences[query_id] = sequence
    validate_bundle(rows, sequences)
    return rows, sequences


def validate_bundle(rows: list[dict], sequences: dict[str, str]) -> None:
    ids = [r["query_id"] for r in rows]
    require(len(ids) == 7 and len(set(ids)) == 7 and set(ids) == set(sequences) == set(QUERY_SPEC), "missing/extra/duplicate bundle query")
    for row in rows:
        target, role, start, end, expected_hash = QUERY_SPEC[row["query_id"]]
        sequence = sequences[row["query_id"]]
        require((row["target"], row["query_role"], int(row["cds_start"]), int(row["cds_end"])) == (target, role, start, end), "bundle role/coordinate mismatch")
        require(int(row["length_nt"]) == len(sequence) == end - start + 1 and set(sequence) <= set("ACGT"), "bundle length/alphabet")
        require(row["sequence_sha256"] == sha256(sequence.encode("ascii")) == expected_hash, "bundle sequence hash")
        require(row["input_semantics"] == "NB04_SEQUENCE_SCREENING_INPUT", "bundle semantic type")
        if role == "REFERENCE_SET":
            require(row["selection_source_stage"] == "NOT_APPLICABLE" and not row["selection_source_artifact"], "benchmark has selection provenance")
        if row["query_id"] == "BC-BENCH-0215-0587":
            require("cp4b" not in row["sequence_source_artifact"] and row["upstream_repository_commit"] != "9ca3e0903e9bee10c0708fde95241b7fa671591a", "BicC benchmark inherited CP4B provenance")
            require(int(row["publication_reported_length_bp"]) == 372 and row["publication_length_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY", "published inconsistency lost")


def overlaps(rows: list[dict], sequences: dict[str, str]) -> list[dict]:
    """All nine within-reference pairs, plus their explicit coordinate partitions."""
    output = []
    for a, b in itertools.combinations(rows, 2):
        if a["target"] != b["target"]:
            continue
        a0, a1, b0, b1 = (int(a["cds_start"]), int(a["cds_end"]), int(b["cds_start"]), int(b["cds_end"]))
        lo, hi = max(a0, b0), min(a1, b1)
        shared = max(0, hi - lo + 1)
        if shared:
            segment_a = sequences[a["query_id"]][lo - a0:hi - a0 + 1]
            segment_b = sequences[b["query_id"]][lo - b0:hi - b0 + 1]
            require(segment_a == segment_b, "shared bases disagree at certified coordinates")
        else:
            segment_a = ""
        def exclusive(start, end):
            return f"{start}:{end}" if not shared else "|".join(f"{x}:{y}" for x, y in ((start, lo - 1), (hi + 1, end)) if x <= y)
        output.append({
            "query_a": a["query_id"], "query_b": b["query_id"], "target": a["target"],
            "shared_start": lo if shared else "", "shared_end": hi if shared else "",
            "shared_nt": shared, "shared_sequence_sha256": sha256(segment_a.encode()) if shared else "",
            "shared_bases_status": "VERIFIED_IDENTICAL" if shared else "NOT_APPLICABLE",
            "query_a_exclusive_intervals": exclusive(a0, a1), "query_b_exclusive_intervals": exclusive(b0, b1),
            "query_a_exclusive_nt": a1 - a0 + 1 - shared, "query_b_exclusive_nt": b1 - b0 + 1 - shared,
            "shared_partition": "SHARED_REGION" if shared else "NONE",
            "a_partition": "QUERY_A_EXCLUSIVE_REGION", "b_partition": "QUERY_B_EXCLUSIVE_REGION",
            "mixed_or_unresolved_partition_nt": 0,
            "sequence_sharing_status": "MIXED" if shared else "NO_COORDINATE_OVERLAP",
            "independence_claim": "NOT_ESTABLISHED", "is_ranking": "false",
        })
    expected = {
        frozenset({"BC-L400-1253-1652", "BC-L400-1254-1653"}): 399,
        frozenset({"BC-L400-1337-1736", "BC-L400-1253-1652"}): 316,
        frozenset({"BC-L400-1337-1736", "BC-L400-1254-1653"}): 317,
        frozenset({"D2-L400-0817-1216", "D2-BENCH-0814-1143"}): 327,
    }
    require(len(output) == 9, "overlap pair cardinality")
    for row in output:
        require(row["shared_nt"] == expected.get(frozenset({row["query_a"], row["query_b"]}), 0), "overlap disagrees with PLAN G.6")
    return output


def materialize(root: Path, output_root: Path | None = None) -> dict:
    """Validate every input before publishing any CP0 output."""
    root = root.resolve()
    destination = root if output_root is None else output_root.resolve()
    policy = load_policy(root)
    complement = load_complement(root)
    _, configured_profile = cp0_repro_configuration(root)
    documentary = json.loads((root / DOC_INPUT).read_text("utf-8"))
    registry = json.loads((root / PROVENANCE).read_text("utf-8"))
    require(digest(root / DOC_INPUT) == policy["documentary_inputs_sha256"], "documentary inputs mismatch")
    require(digest(root / PROVENANCE) == policy["upstream_provenance_sha256"], "upstream registry mismatch")
    panel = read_tsv(root / "config/nb04_nto_panel.tsv")
    scenarios = read_tsv(root / "config/nb04_exposure_scenarios.tsv")
    exposure = read_tsv(root / "config/nb04_receptor_exposure.tsv")
    tables = documentary["materialized_tables"]
    validate_tables(panel, scenarios, exposure, tables["literature_register"], tables["resource_landscape"], tables["coverage_gaps"], complement)
    query_rows, sequences = build_bundle(root, registry)
    sharing = overlaps(query_rows, sequences)
    outputs = {
        "data/reference/nb04_nto_queries.tsv": tsv_bytes(query_rows),
        "data/reference/nb04_nto_queries.fasta": "".join(f">{key}\n{sequences[key]}\n" for key in sorted(sequences)).encode("ascii"),
        f"{CP0}/query_overlap.tsv": tsv_bytes(sharing),
    }
    for name, data in tables.items():
        outputs[f"{CP0}/{name}.tsv"] = tsv_bytes(data)
    summary = {
        "schema_version": 1, "stage": "NB04_CP0", "execution_status": "CP0_MATERIALIZED_COMPLEMENTARY_CONTRACT_PENDING_G0_REVIEW",
        "states": policy["states"], "certification_status": (
            "PENDING_EXTERNAL_HUMAN_G0_REVIEW" if configured_profile else
            "PENDING_EXTERNAL_HUMAN_G0_REVIEW_AND_OPERATIONAL_REPRO_PROFILE"),
        "complementary_contract_id": complement["contract_id"], "complementary_contract_authority": complement["authority_status"],
        "query_count": len(query_rows), "query_ids": sorted(sequences), "query_validation": "PASS",
        "overlap_validation": "PASS", "within_reference_pairs": len(sharing),
        "cross_target_coordinate_overlap": "NOT_APPLICABLE_DIFFERENT_REFERENCE_COORDINATE_SYSTEMS",
        "receptor_count": len(panel), "core_receptor_count": sum(r["ecological_panel_tier"] == "CORE" for r in panel),
        "scenario_count": len(scenarios), "receptor_scenario_rows": len(exposure),
        "literature_rows": len(tables["literature_register"]), "landscape_rows": len(tables["resource_landscape"]),
        "gap_rows": len(tables["coverage_gaps"]), "preliminary_only": True,
        "publication_inconsistency": "UNRESOLVED_PUBLICATION_INCONSISTENCY",
        "fixtures_materialized": False, "calibration_qa_status": "NOT_TESTED",
        "normative_reference_pending": policy["calibration"]["selection_rule_id"] is None,
        "real_nto_searches": "NOT_EXECUTED", "resource_freeze": "NOT_PERFORMED",
        "display_order_classification": "CANONICAL_DISPLAY_ORDER_ONLY", "is_ranking": False,
        "contract_equivalence": [
            {"component": "nb04_serialization", "reuse": "DIRECT", "basis": "N18 canonical serialization and rejection tests"},
            {"component": "repro.check_required_paths", "reuse": "EXPLICIT_ADDITIVE_CHECKPOINT_PROFILE", "basis": "N20, checkpoint=None remains historical", "operational_profile": "CONFIGURED_IN_REPRO_YAML" if configured_profile else "PROPOSED_NOT_APPLIED"},
            {"component": "NB02/NB03 search and selection kernels", "reuse": "NOT_REUSED", "basis": "CP0 consumes certified artifacts only"},
        ],
    }
    outputs[f"{CP0}/cp0_summary.json"] = json_bytes(summary)
    config_paths = [".gitattributes", "src/workstreams/bioinformatics/decisions/0007-nb04-nto-sequence-specificity-policy.md", "config/repro.yaml", "config/repro.schema.json", "config/nb04_nto_policy.yaml", "config/nb04_nto_policy.schema.json", "config/nb04_nto_panel.tsv", "config/nb04_exposure_scenarios.tsv", "config/nb04_receptor_exposure.tsv", DOC_INPUT, PROVENANCE, CONTRACT_PATH]
    implementation = ["src/zeaguard/nb04_cp0.py", "src/zeaguard/nb04_policy.py", "src/zeaguard/nb04_complement.py", "src/zeaguard/nb04_serialization.py", "scripts/prepare_nb04_cp0_inputs.py", "scripts/validate_nb04_cp0.py", "tests/test_nb04_cp0.py"]
    manifest = {
        "schema_version": 1, "stage": "NB04_CP0_LIMITED_IMPLEMENTATION",
        "states": policy["states"], "normative_documents": documentary["normative_documents"],
        "inputs_sha256_lf": {p: digest(root / p, normalized=True) for p in config_paths},
        "implementation_sha256_lf": {p: digest(root / p, normalized=True) for p in implementation},
        "upstream_artifacts": registry["artifacts"], "upstream_queries": registry["queries"],
        "reference_pins": registry["reference_pins"],
        "deterministic_outputs": sorted(outputs), "outputs_sha256": {p: sha256(data) for p, data in sorted(outputs.items())},
        "execution_metadata": {"file": "execution_metadata.json", "excluded_from_deterministic_outputs": True},
        "certification_status": "NOT_CERTIFIED", "certification_requires": "B6_A1_EXTERNAL_QUALIFIED_HUMAN_REVIEW",
    }
    outputs[f"{CP0}/run_manifest.json"] = json_bytes(manifest)
    for relative, data in outputs.items():
        path = local_path(destination, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    metadata = {
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git(root, "rev-parse", "HEAD").decode().strip(),
        "git_branch": git(root, "branch", "--show-current").decode().strip(),
        "git_dirty": bool(git(root, "status", "--porcelain=v1").strip()),
        "baseline_head": documentary["initial_state"]["head"],
        "baseline_snapshot_sha256": documentary["initial_state"]["snapshot_sha256"],
        "run_manifest_sha256": sha256(outputs[f"{CP0}/run_manifest.json"]),
    }
    (destination / CP0 / "execution_metadata.json").write_bytes(json_bytes(metadata))
    return {**summary, "run_manifest_sha256": metadata["run_manifest_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.root, args.output_root), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
