"""Input contracts and computational provenance helpers for NB01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import zeaguard.repro as repro


MANIFEST_SCHEMA_VERSION = 1
PROVENANCE_SCHEMA_VERSION = 1
DEFAULT_PROJECT_CONFIG = Path("config/project.yaml")
DEFAULT_MANIFEST = Path("data/reference/manifest.json")
DEFAULT_EXTERNAL_DATA_DIR = Path("data/external")
DEFAULT_OUTPUT_DIR = Path("results/bioinformatics/nb01")
DEFAULT_TARGET_ANCHORS = Path("data/reference/target_anchors.tsv")
UNKNOWN_VALUES = {"", "PENDING", "REVIEW_REQUIRED", "TBD", "UNKNOWN"}
EMPTY_ANCHOR_VALUES = {"", "NA"}
TARGET_ANCHOR_COLUMNS = (
    "target_id",
    "target_role",
    "aliases",
    "source_type",
    "source_reference",
    "source_identifier",
    "published_transcript_id",
    "published_protein_id",
    "published_accession",
    "documented_features",
    "evidence_strength",
    "identity_status",
    "notes",
)
TARGET_ANCHOR_REQUIRED_VALUES = (
    "target_id",
    "target_role",
    "aliases",
    "source_type",
    "source_reference",
    "source_identifier",
    "documented_features",
    "evidence_strength",
    "identity_status",
    "notes",
)
TARGET_ANCHOR_EVIDENCE_STRENGTHS = {"strong", "partial"}
TARGET_ANCHOR_IDENTITY_STATUSES = {"requires_computational_resolution"}


class InputContractError(RuntimeError):
    """Raised when critical NB01 input preconditions are not satisfied."""


@dataclass(frozen=True)
class PreconditionCheck:
    requirement: str
    status: str
    detail: str


@dataclass(frozen=True)
class PreconditionReport:
    checks: tuple[PreconditionCheck, ...]

    def failures(self) -> list[PreconditionCheck]:
        return [check for check in self.checks if check.status == "FAIL"]

    def raise_if_failed(self) -> None:
        failures = self.failures()
        if failures:
            details = "\n".join(
                f"{check.requirement}: {check.detail}" for check in failures
            )
            raise InputContractError(f"NB01 input preconditions failed:\n{details}")

    def to_text(self) -> str:
        return "\n".join(
            f"{check.status:6}  {check.requirement}: {check.detail}"
            for check in self.checks
        )

    def counts(self) -> dict[str, int]:
        return {
            status: sum(check.status == status for check in self.checks)
            for status in ("PASS", "REVIEW", "FAIL")
        }


@dataclass(frozen=True)
class Stage1Result:
    project_root: Path
    output_dir: Path
    report_path: Path
    provenance_path: Path
    targets: dict[str, list[dict[str, Any]]]
    manifest: dict[str, Any] | None
    report: PreconditionReport


@dataclass(frozen=True)
class Stage2Result:
    project_root: Path
    anchor_path: Path
    report_path: Path
    anchors: tuple[dict[str, str], ...]
    report: PreconditionReport
    target_statuses: tuple[dict[str, Any], ...]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(_json_bytes(value))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_unknown(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and value.strip().upper() in UNKNOWN_VALUES
    )


def _metadata_check(requirement: str, value: Any) -> PreconditionCheck:
    if _is_unknown(value):
        return PreconditionCheck(
            requirement,
            "REVIEW",
            "metadata is pending and must be supplied before scientific use",
        )
    if not isinstance(value, str):
        return PreconditionCheck(requirement, "FAIL", "must be a non-empty string")
    return PreconditionCheck(requirement, "PASS", value)


def _acquired_utc_check(value: Any) -> PreconditionCheck:
    requirement = "manifest.acquired_utc"
    if _is_unknown(value):
        return PreconditionCheck(
            requirement,
            "REVIEW",
            "acquisition timestamp is pending and must be recorded in UTC",
        )
    if not isinstance(value, str):
        return PreconditionCheck(requirement, "FAIL", "must be an ISO 8601 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return PreconditionCheck(requirement, "FAIL", "invalid ISO 8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return PreconditionCheck(requirement, "FAIL", "timestamp must include UTC offset")
    return PreconditionCheck(requirement, "PASS", value)


def load_project_targets(
    project_root: Path,
    project_config: Path = DEFAULT_PROJECT_CONFIG,
) -> tuple[dict[str, list[dict[str, Any]]], list[PreconditionCheck], Path]:
    """Load target declarations verbatim from the existing project configuration."""
    import yaml

    root = project_root.resolve()
    config_path = (root / project_config).resolve()
    checks: list[PreconditionCheck] = []
    targets = {"intervention_targets": [], "reference_targets": []}

    try:
        config_path.relative_to(root)
    except ValueError:
        return targets, [PreconditionCheck("project_config", "FAIL", "path escapes project root")], config_path

    if not config_path.is_file():
        return targets, [PreconditionCheck("project_config", "FAIL", "missing or not a regular file")], config_path

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return targets, [PreconditionCheck("project_config", "FAIL", f"unreadable or invalid YAML: {exc}")], config_path

    if not isinstance(raw, dict):
        return targets, [PreconditionCheck("project_config", "FAIL", "top level must be a mapping")], config_path

    checks.append(PreconditionCheck("project_config", "PASS", _relative_path(root, config_path)))
    for key in targets:
        declared = raw.get(key)
        if not isinstance(declared, list) or not declared:
            checks.append(PreconditionCheck(f"project_config.{key}", "FAIL", "must be a non-empty list"))
            continue
        invalid = [
            index
            for index, item in enumerate(declared)
            if not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ]
        if invalid:
            checks.append(
                PreconditionCheck(
                    f"project_config.{key}",
                    "FAIL",
                    f"entries without a non-empty id: {invalid}",
                )
            )
            continue
        targets[key] = declared
        checks.append(
            PreconditionCheck(
                f"project_config.{key}",
                "PASS",
                f"{len(declared)} target declarations loaded from project.yaml",
            )
        )
    return targets, checks, config_path


def inspect_manifest(
    project_root: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    external_data_dir: Path = DEFAULT_EXTERNAL_DATA_DIR,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[PreconditionCheck], Path]:
    """Validate the external dataset manifest and every declared file."""
    root = project_root.resolve()
    path = (root / manifest_path).resolve()
    external_root = (root / external_data_dir).resolve()
    checks: list[PreconditionCheck] = []
    validated_files: list[dict[str, Any]] = []

    try:
        path.relative_to(root)
    except ValueError:
        return None, validated_files, [PreconditionCheck("manifest", "FAIL", "path escapes project root")], path

    if not path.is_file():
        return None, validated_files, [PreconditionCheck("manifest", "FAIL", "missing or not a regular file")], path

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, validated_files, [PreconditionCheck("manifest", "FAIL", f"unreadable or invalid JSON: {exc}")], path

    checks.append(PreconditionCheck("manifest", "PASS", _relative_path(root, path)))
    if not isinstance(manifest, dict):
        checks.append(PreconditionCheck("manifest.structure", "FAIL", "top level must be an object"))
        return None, validated_files, checks, path

    schema_version = manifest.get("schema_version")
    checks.append(
        PreconditionCheck(
            "manifest.schema_version",
            "PASS" if schema_version == MANIFEST_SCHEMA_VERSION else "FAIL",
            str(schema_version) if schema_version == MANIFEST_SCHEMA_VERSION else f"expected {MANIFEST_SCHEMA_VERSION}",
        )
    )

    dataset = manifest.get("dataset")
    if not isinstance(dataset, dict):
        checks.append(PreconditionCheck("manifest.dataset", "FAIL", "must be an object"))
        dataset = {}
    else:
        checks.append(PreconditionCheck("manifest.dataset", "PASS", "dataset metadata object present"))
    checks.extend(
        [
            _metadata_check("manifest.dataset.name", dataset.get("name")),
            _metadata_check("manifest.dataset.version", dataset.get("version")),
            _metadata_check("manifest.origin", manifest.get("origin")),
            _acquired_utc_check(manifest.get("acquired_utc")),
        ]
    )

    files = manifest.get("files")
    if not isinstance(files, list):
        checks.append(PreconditionCheck("manifest.files", "FAIL", "must be a list"))
        return manifest, validated_files, checks, path
    if not files:
        checks.append(
            PreconditionCheck(
                "manifest.files",
                "FAIL",
                "no external input files are declared; NB01 cannot continue",
            )
        )
        return manifest, validated_files, checks, path

    checks.append(PreconditionCheck("manifest.files", "PASS", f"{len(files)} file entries declared"))
    seen_paths: set[str] = set()
    for index, entry in enumerate(files):
        requirement = f"manifest.files[{index}]"
        if not isinstance(entry, dict):
            checks.append(PreconditionCheck(requirement, "FAIL", "entry must be an object"))
            continue
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative, str) or not relative.strip():
            checks.append(PreconditionCheck(requirement, "FAIL", "path must be a non-empty string"))
            continue
        relative_path = Path(relative)
        if relative_path.is_absolute():
            checks.append(PreconditionCheck(requirement, "FAIL", "path must be relative to project root"))
            continue
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(external_root)
        except ValueError:
            checks.append(PreconditionCheck(requirement, "FAIL", "path must remain under data/external"))
            continue
        canonical = str(candidate).casefold()
        if canonical in seen_paths:
            checks.append(PreconditionCheck(requirement, "FAIL", f"duplicate path: {relative}"))
            continue
        seen_paths.add(canonical)
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            checks.append(PreconditionCheck(requirement, "FAIL", f"invalid SHA-256 for {relative}"))
            continue
        try:
            int(expected_hash, 16)
        except ValueError:
            checks.append(PreconditionCheck(requirement, "FAIL", f"invalid SHA-256 for {relative}"))
            continue
        if not candidate.is_file():
            checks.append(PreconditionCheck(requirement, "FAIL", f"missing regular file: {relative}"))
            continue
        try:
            observed_hash = sha256_file(candidate)
            size_bytes = candidate.stat().st_size
        except OSError as exc:
            checks.append(PreconditionCheck(requirement, "FAIL", f"unreadable file {relative}: {exc}"))
            continue
        if observed_hash != expected_hash.lower():
            checks.append(
                PreconditionCheck(
                    requirement,
                    "FAIL",
                    f"SHA-256 mismatch for {relative}: expected {expected_hash.lower()}, observed {observed_hash}",
                )
            )
            continue
        checks.append(PreconditionCheck(requirement, "PASS", f"{relative}; SHA-256 verified"))
        validated_files.append(
            {"path": Path(relative).as_posix(), "sha256": observed_hash, "size_bytes": size_bytes}
        )
    return manifest, validated_files, checks, path


def read_reproducibility_snapshot_identity(project_root: Path) -> dict[str, str]:
    """Read the already validated NB00 snapshot pointer for provenance recording."""
    root = project_root.resolve()
    cfg = repro.load_repro_config()
    snapshot_dir = (root / cfg.snapshot_dir).resolve()
    latest_path = snapshot_dir / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    snapshot_path = (snapshot_dir / latest["snapshot_file"]).resolve()
    snapshot_path.relative_to(snapshot_dir)
    return {
        "pointer_path": _relative_path(root, latest_path),
        "snapshot_path": _relative_path(root, snapshot_path),
        "snapshot_sha256": latest["snapshot_sha256"],
    }


def prepare_nb01_stage1(
    project_root: Path | None = None,
    project_config: Path = DEFAULT_PROJECT_CONFIG,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    run_context: dict[str, Any] | None = None,
    reproducibility_snapshot: dict[str, str] | None = None,
) -> Stage1Result:
    """Inspect NB01 inputs and persist deterministic precondition/provenance reports."""
    root = (project_root or repro.find_project_root()).resolve()
    destination = (root / output_dir).resolve()
    destination.relative_to(root)
    destination.mkdir(parents=True, exist_ok=True)

    targets, project_checks, config_path = load_project_targets(root, project_config)
    manifest, validated_files, manifest_checks, resolved_manifest = inspect_manifest(
        root, manifest_path
    )
    report = PreconditionReport(tuple([*project_checks, *manifest_checks]))

    context = run_context or repro.collect_run_context(root)
    snapshot_identity = reproducibility_snapshot or read_reproducibility_snapshot_identity(root)
    manifest_hash = sha256_file(resolved_manifest) if resolved_manifest.is_file() else None
    config_hash = sha256_file(config_path) if config_path.is_file() else None

    report_document = {
        "schema_version": 1,
        "stage": "NB01_STAGE_1",
        "summary": report.counts(),
        "checks": [asdict(check) for check in report.checks],
    }
    provenance_document = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "stage": "NB01_STAGE_1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": context.get("git"),
        "reproducibility_snapshot": snapshot_identity,
        "project_config": {
            "path": _relative_path(root, config_path),
            "sha256": config_hash,
        },
        "declared_targets": targets,
        "dataset_manifest": {
            "path": _relative_path(root, resolved_manifest),
            "sha256": manifest_hash,
            "content": manifest,
        },
        "validated_files": validated_files,
        "precondition_summary": report.counts(),
    }

    report_path = destination / "preconditions.json"
    provenance_path = destination / "input_provenance.json"
    _atomic_write_json(report_path, report_document)
    _atomic_write_json(provenance_path, provenance_document)
    return Stage1Result(
        project_root=root,
        output_dir=destination,
        report_path=report_path,
        provenance_path=provenance_path,
        targets=targets,
        manifest=manifest,
        report=report,
    )


def _declared_target_roles(
    targets: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], dict[str, str], list[PreconditionCheck]]:
    ordered_ids: list[str] = []
    roles: dict[str, str] = {}
    checks: list[PreconditionCheck] = []
    for collection, role in (
        ("intervention_targets", "intervention"),
        ("reference_targets", "reference"),
    ):
        for declaration in targets.get(collection, []):
            target_id = declaration.get("id")
            if not isinstance(target_id, str) or not target_id.strip():
                checks.append(
                    PreconditionCheck(
                        "target_anchors.project_targets",
                        "FAIL",
                        f"invalid target declaration in {collection}",
                    )
                )
                continue
            target_id = target_id.strip()
            if target_id in roles:
                checks.append(
                    PreconditionCheck(
                        "target_anchors.project_targets",
                        "FAIL",
                        f"duplicate target_id in project configuration: {target_id}",
                    )
                )
                continue
            ordered_ids.append(target_id)
            roles[target_id] = role
    if not checks:
        checks.append(
            PreconditionCheck(
                "target_anchors.project_targets",
                "PASS",
                f"{len(ordered_ids)} unique target declarations loaded from project.yaml",
            )
        )
    return ordered_ids, roles, checks


def _anchor_value_missing(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _anchor_value_unavailable(value: Any) -> bool:
    return _anchor_value_missing(value) or value.strip().upper() in EMPTY_ANCHOR_VALUES


def inspect_target_anchors(
    project_root: Path,
    targets: dict[str, list[dict[str, Any]]],
    anchor_path: Path = DEFAULT_TARGET_ANCHORS,
) -> tuple[list[dict[str, str]], list[PreconditionCheck], Path]:
    """Read and structurally validate target identity anchors without sequences."""
    root = project_root.resolve()
    path = (root / anchor_path).resolve()
    checks: list[PreconditionCheck] = []
    records: list[dict[str, str]] = []

    try:
        path.relative_to(root)
    except ValueError:
        return records, [PreconditionCheck("target_anchors", "FAIL", "path escapes project root")], path
    if not path.is_file():
        return records, [PreconditionCheck("target_anchors", "FAIL", "missing or not a regular file")], path

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fieldnames = reader.fieldnames
            if fieldnames is None:
                return records, [PreconditionCheck("target_anchors.header", "FAIL", "missing TSV header")], path
            if len(fieldnames) != len(set(fieldnames)):
                checks.append(
                    PreconditionCheck(
                        "target_anchors.header",
                        "FAIL",
                        "duplicate column names are not allowed",
                    )
                )
            missing_columns = [
                column for column in TARGET_ANCHOR_COLUMNS if column not in fieldnames
            ]
            if missing_columns:
                checks.append(
                    PreconditionCheck(
                        "target_anchors.header",
                        "FAIL",
                        f"missing required columns: {missing_columns}",
                    )
                )
            elif len(fieldnames) == len(set(fieldnames)):
                checks.append(
                    PreconditionCheck(
                        "target_anchors.header",
                        "PASS",
                        f"all {len(TARGET_ANCHOR_COLUMNS)} required columns are present",
                    )
                )
            records = [
                {key: (value or "").strip() for key, value in row.items() if key is not None}
                for row in reader
            ]
    except (OSError, UnicodeError, csv.Error) as exc:
        return records, [PreconditionCheck("target_anchors", "FAIL", f"unreadable or invalid TSV: {exc}")], path

    checks.append(PreconditionCheck("target_anchors", "PASS", _relative_path(root, path)))
    expected_ids, expected_roles, declaration_checks = _declared_target_roles(targets)
    checks.extend(declaration_checks)

    observed_ids = [record.get("target_id", "") for record in records]
    duplicate_ids = sorted(
        target_id
        for target_id in set(observed_ids)
        if target_id and observed_ids.count(target_id) > 1
    )
    checks.append(
        PreconditionCheck(
            "target_anchors.unique_target_id",
            "FAIL" if duplicate_ids else "PASS",
            f"duplicate target_id values: {duplicate_ids}"
            if duplicate_ids
            else f"{len(observed_ids)} unique rows",
        )
    )

    expected_set = set(expected_ids)
    observed_set = {target_id for target_id in observed_ids if target_id}
    missing_targets = [target_id for target_id in expected_ids if target_id not in observed_set]
    extra_targets = sorted(observed_set - expected_set)
    checks.append(
        PreconditionCheck(
            "target_anchors.expected_targets",
            "FAIL" if missing_targets else "PASS",
            f"missing project targets: {missing_targets}"
            if missing_targets
            else "every project target has an anchor row",
        )
    )
    checks.append(
        PreconditionCheck(
            "target_anchors.unexpected_targets",
            "FAIL" if extra_targets else "PASS",
            f"unexpected target_id values: {extra_targets}"
            if extra_targets
            else "no target outside project.yaml is present",
        )
    )

    missing_values: list[str] = []
    role_mismatches: list[str] = []
    invalid_evidence: list[str] = []
    invalid_identity_status: list[str] = []
    for row_number, record in enumerate(records, start=2):
        target_id = record.get("target_id", "")
        for field in TARGET_ANCHOR_REQUIRED_VALUES:
            value = record.get(field)
            allows_na = field in {"aliases", "notes"}
            if _anchor_value_missing(value) or (
                not allows_na and _anchor_value_unavailable(value)
            ):
                missing_values.append(f"row {row_number} {target_id or '<empty>'}.{field}")
        expected_role = expected_roles.get(target_id)
        if expected_role and record.get("target_role") != expected_role:
            role_mismatches.append(
                f"{target_id}: expected {expected_role}, observed {record.get('target_role') or '<empty>'}"
            )
        evidence = record.get("evidence_strength")
        if evidence and evidence not in TARGET_ANCHOR_EVIDENCE_STRENGTHS:
            invalid_evidence.append(f"{target_id}: {evidence}")
        identity_status = record.get("identity_status")
        if identity_status and identity_status not in TARGET_ANCHOR_IDENTITY_STATUSES:
            invalid_identity_status.append(f"{target_id}: {identity_status}")

    checks.extend(
        [
            PreconditionCheck(
                "target_anchors.required_values",
                "FAIL" if missing_values else "PASS",
                f"missing required values: {missing_values}"
                if missing_values
                else "all required structural values are present",
            ),
            PreconditionCheck(
                "target_anchors.target_roles",
                "FAIL" if role_mismatches else "PASS",
                f"role mismatches: {role_mismatches}"
                if role_mismatches
                else "all roles match project.yaml target collections",
            ),
            PreconditionCheck(
                "target_anchors.evidence_strength",
                "FAIL" if invalid_evidence else "PASS",
                f"invalid values: {invalid_evidence}"
                if invalid_evidence
                else "all evidence strength values are recognized",
            ),
            PreconditionCheck(
                "target_anchors.identity_status",
                "FAIL" if invalid_identity_status else "PASS",
                f"invalid values: {invalid_identity_status}"
                if invalid_identity_status
                else "all identity status values are recognized",
            ),
        ]
    )

    for target_id in expected_ids:
        matching = [record for record in records if record.get("target_id") == target_id]
        if len(matching) != 1:
            continue
        missing_identifiers = [
            field
            for field in (
                "published_transcript_id",
                "published_protein_id",
                "published_accession",
            )
            if _anchor_value_unavailable(matching[0].get(field))
        ]
        checks.append(
            PreconditionCheck(
                f"target_anchors.identifiers.{target_id}",
                "REVIEW" if missing_identifiers else "PASS",
                f"published identifiers unavailable: {missing_identifiers}; retained for stage 3"
                if missing_identifiers
                else "all published identifier fields are populated",
            )
        )
    return records, checks, path


def prepare_nb01_stage2(
    project_root: Path | None = None,
    targets: dict[str, list[dict[str, Any]]] | None = None,
    anchor_path: Path = DEFAULT_TARGET_ANCHORS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Stage2Result:
    """Validate curated target anchors and persist the NB01 stage 2 report."""
    root = (project_root or repro.find_project_root()).resolve()
    if targets is None:
        targets, project_checks, _ = load_project_targets(root)
    else:
        project_checks = []
    anchors, anchor_checks, resolved_anchor_path = inspect_target_anchors(
        root, targets, anchor_path
    )
    report = PreconditionReport(tuple([*project_checks, *anchor_checks]))
    ordered_ids, _, _ = _declared_target_roles(targets)
    structurally_valid = not report.failures()
    target_statuses: list[dict[str, Any]] = []
    for target_id in ordered_ids:
        matching = [anchor for anchor in anchors if anchor.get("target_id") == target_id]
        if len(matching) != 1 or not structurally_valid:
            target_statuses.append(
                {
                    "target_id": target_id,
                    "status": "FAIL",
                    "evidence_strength": matching[0].get("evidence_strength") if matching else None,
                    "identity_status": matching[0].get("identity_status") if matching else None,
                    "missing_published_identifiers": [],
                }
            )
            continue
        anchor = matching[0]
        missing_identifiers = [
            field
            for field in (
                "published_transcript_id",
                "published_protein_id",
                "published_accession",
            )
            if _anchor_value_unavailable(anchor.get(field))
        ]
        target_statuses.append(
            {
                "target_id": target_id,
                "status": "REVIEW" if missing_identifiers else "PASS",
                "evidence_strength": anchor["evidence_strength"],
                "identity_status": anchor["identity_status"],
                "missing_published_identifiers": missing_identifiers,
                "source_reference": anchor["source_reference"],
                "source_identifier": anchor["source_identifier"],
            }
        )

    destination = (root / output_dir).resolve()
    destination.relative_to(root)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "target_anchor_report.json"
    report_document = {
        "schema_version": 1,
        "stage": "NB01_STAGE_2",
        "target_anchor_file": {
            "path": _relative_path(root, resolved_anchor_path),
            "sha256": sha256_file(resolved_anchor_path)
            if resolved_anchor_path.is_file()
            else None,
        },
        "expected_target_ids": ordered_ids,
        "summary": report.counts(),
        "checks": [asdict(check) for check in report.checks],
        "strong_anchors": [
            status["target_id"]
            for status in target_statuses
            if status["evidence_strength"] == "strong"
        ],
        "partial_anchors": [
            status["target_id"]
            for status in target_statuses
            if status["evidence_strength"] == "partial"
        ],
        "requires_computational_resolution": [
            status["target_id"]
            for status in target_statuses
            if status["identity_status"] == "requires_computational_resolution"
        ],
        "targets": target_statuses,
    }
    _atomic_write_json(report_path, report_document)
    return Stage2Result(
        project_root=root,
        anchor_path=resolved_anchor_path,
        report_path=report_path,
        anchors=tuple(anchors),
        report=report,
        target_statuses=tuple(target_statuses),
    )
