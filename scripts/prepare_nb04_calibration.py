"""Prepare NB04 B4 pre-freeze calibration artifacts without executing any search.

Importing or running this script never invokes blastn searches, builds indices,
or runs informative calibration. Subcommand `e01` executes E01 preservation
verification and materializes the execution scope and preservation inventory
artifacts. Subcommand `e03` derives the read-only
NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 records for the six certified CP1
resources. Subcommand `e05` executes E05 Part 1 configuration inspection
(`-version` and `-help` only) and materializes the inspection artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from zeaguard import nb04_calibration as cal
from zeaguard.nb04_resources import ResourceContractError, digest, json_bytes, require


def parse_corpus_mappings(items: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in items:
        require("=" in item, f"corpus mapping must have format CORPUS_ID=PATH: {item!r}")
        corpus_id, raw_path = item.split("=", 1)
        corpus_id = corpus_id.strip()
        raw_path = raw_path.strip()
        require(bool(corpus_id) and bool(raw_path), f"empty corpus_id or path in {item!r}")
        require(corpus_id not in mapping, f"duplicate corpus_id mapping: {corpus_id}")
        mapping[corpus_id] = Path(raw_path)
    return mapping


def run_e01(
    root: Path,
    corpus_directories: dict[str, Path],
    *,
    scope_output: Path | None = None,
    inventory_output: Path | None = None,
    executed_utc: str | None = None,
) -> dict[str, object]:
    root = root.resolve()
    scope_target = cal.validate_e01_scope_destination(root, scope_output)
    inv_target = cal.validate_e01_inventory_destination(root, inventory_output)

    scope_payload = cal.build_execution_scope_artifact(root)
    encoded_scope = json_bytes(scope_payload)
    if scope_target.exists():
        require(
            scope_target.is_file() and scope_target.read_bytes() == encoded_scope,
            f"execution scope destination already exists with divergent content and must not be overwritten: {scope_target}",
        )

    inventory = cal.build_preservation_inventory(
        root,
        corpus_directories,
        executed_utc=executed_utc,
    )

    scope_path, _ = cal.write_execution_scope_artifact(root, scope_target)
    written_inventory_path = cal.write_preservation_inventory(
        root,
        inventory,
        output_path=inv_target,
    )

    return {
        "stage": "NB04_CP1_E01",
        "execution_scope_path": scope_path.relative_to(root).as_posix(),
        "execution_scope_sha256": digest(scope_path),
        "preservation_inventory_path": written_inventory_path.relative_to(root).as_posix(),
        "preservation_inventory_sha256": digest(written_inventory_path),
        "g0_certified_artifacts_verdict": inventory["b_g0_certified_artifacts"]["verdict"],
        "normative_documents_verdict": inventory["c_normative_documents"]["verdict"],
        "cp1_resources_verdict": inventory["d_cp1_resources_and_manifests"]["verdict"],
        "snapshots_verdict": inventory["e_reproducibility_snapshots"]["verdict"],
        "blast_tool_builds_status": inventory["f_observed_blast_tool_builds"]["overall_status"],
        "allowlist_verdict": inventory["g_preparation_allowlist_control"]["verdict"],
        "searches_executed": False,
    }


def run_e03(
    root: Path,
    *,
    campaign_id: str = cal.DEFAULT_GEOMETRY_CAMPAIGN_ID,
    destination_overrides: dict[str, Path] | None = None,
) -> dict[str, object]:
    return cal.derive_and_write_all_resources_geometry(
        root,
        campaign_id=campaign_id,
        destination_overrides=destination_overrides,
    )


def run_e05(
    root: Path,
    corpus_directories: dict[str, Path],
    *,
    campaign_id: str = cal.DEFAULT_GEOMETRY_CAMPAIGN_ID,
    output_path: Path | None = None,
) -> dict[str, object]:
    root = root.resolve()
    validated_target = cal.validate_e05_inspection_destination(root, output_path)
    payload = cal.build_e05_configuration_inspection(
        root,
        corpus_directories,
        campaign_id=campaign_id,
    )
    written_path, artifact_sha256 = cal.write_e05_configuration_inspection(
        root,
        payload,
        destination=validated_target,
    )
    return {
        "stage": "NB04_CP1_E05_PART_1",
        "inspection_artifact_path": written_path.relative_to(root).as_posix(),
        "inspection_artifact_sha256": artifact_sha256,
        "tools_overall_status": payload["a_observed_tool_builds"]["overall_status"],
        "comparison_status": payload["b_build_comparison_with_cp1_receipts_and_derivations"]["comparison_status"],
        "equivalent_build_reuse_blocked": payload["b_build_comparison_with_cp1_receipts_and_derivations"]["equivalent_build_reuse_blocked"],
        "total_parameters_inspected": payload["c_parameter_matrix_inspection"]["total_parameters"],
        "output_integrity_mechanism": payload["d_output_integrity_mechanism"]["selected_mechanism"],
        "total_qa_criteria_classified": payload["e_configuration_qa_matrix_status"]["total_criteria"],
        "searches_executed": False,
        "queries_executed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    e01 = subparsers.add_parser(
        "e01",
        help="Verify E01 preservation controls and materialize execution scope and inventory.",
    )
    e01.add_argument("--root", type=Path, default=ROOT, help="Repository root path.")
    e01.add_argument(
        "--corpus",
        action="append",
        default=[],
        metavar="CORPUS_ID=PATH",
        help="Runtime directory mapping for an external normative corpus (repeatable).",
    )
    e01.add_argument(
        "--scope-output",
        type=Path,
        default=None,
        help=f"Optional output path for execution scope (default: {cal.EXECUTION_SCOPE_PATH}).",
    )
    e01.add_argument(
        "--inventory-output",
        type=Path,
        default=None,
        help="Optional output path for preservation inventory (default: timestamped under artifacts/validation/nb04_cp1_prefreeze/).",
    )
    e01.add_argument(
        "--executed-utc",
        type=str,
        default=None,
        help="Optional explicit UTC timestamp string for deterministic inventory generation.",
    )

    e03 = subparsers.add_parser(
        "e03",
        help="Derive read-only NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 records for the six CP1 resources.",
    )
    e03.add_argument("--root", type=Path, default=ROOT, help="Repository root path.")
    e03.add_argument(
        "--campaign-id",
        type=str,
        default=cal.DEFAULT_GEOMETRY_CAMPAIGN_ID,
        help=f"Target campaign identifier under data/external/nto/<campaign_id>/geometry/ (default: {cal.DEFAULT_GEOMETRY_CAMPAIGN_ID}).",
    )

    e05 = subparsers.add_parser(
        "e05",
        help="Execute E05 Part 1 read-only tool build and 31-parameter configuration inspection.",
    )
    e05.add_argument("--root", type=Path, default=ROOT, help="Repository root path.")
    e05.add_argument(
        "--corpus",
        action="append",
        default=[],
        metavar="CORPUS_ID=PATH",
        help="Runtime directory mapping for an external normative corpus (repeatable).",
    )
    e05.add_argument(
        "--campaign-id",
        type=str,
        default=cal.DEFAULT_GEOMETRY_CAMPAIGN_ID,
        help=f"CP1 campaign identifier for E03 geometry verification (default: {cal.DEFAULT_GEOMETRY_CAMPAIGN_ID}).",
    )
    e05.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Optional output path under {cal.PRESERVATION_INVENTORY_DIR}/ (default: {cal.E05_INSPECTION_DEFAULT_PATH}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "e01":
        corpora = parse_corpus_mappings(args.corpus)
        summary = run_e01(
            args.root,
            corpora,
            scope_output=args.scope_output,
            inventory_output=args.inventory_output,
            executed_utc=args.executed_utc,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.subcommand == "e03":
        summary = run_e03(
            args.root,
            campaign_id=args.campaign_id,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.subcommand == "e05":
        corpora = parse_corpus_mappings(args.corpus)
        summary = run_e05(
            args.root,
            corpora,
            campaign_id=args.campaign_id,
            output_path=args.output,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    raise ResourceContractError(f"unsupported subcommand: {args.subcommand}")


if __name__ == "__main__":
    raise SystemExit(main())
