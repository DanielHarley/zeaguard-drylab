from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from zeaguard import nb01_inputs


def write_project_config(root: Path) -> None:
    config = root / "config"
    config.mkdir(parents=True)
    (config / "project.yaml").write_text(
        """schema_version: 1
intervention_targets:
  - id: configured-intervention
    aliases: [configured-alias]
reference_targets:
  - id: configured-reference
    role: configured-role
""",
        encoding="utf-8",
    )


def write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "data" / "reference" / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def valid_manifest(relative_path: str, digest: str) -> dict:
    return {
        "schema_version": 1,
        "dataset": {"name": "fixture", "version": "1.0"},
        "origin": "https://example.invalid/fixture",
        "acquired_utc": "2026-09-11T12:00:00Z",
        "files": [{"path": relative_path, "sha256": digest}],
    }


def test_load_project_targets_uses_only_project_configuration(tmp_path):
    write_project_config(tmp_path)

    targets, checks, _ = nb01_inputs.load_project_targets(tmp_path)

    assert targets == {
        "intervention_targets": [
            {"id": "configured-intervention", "aliases": ["configured-alias"]}
        ],
        "reference_targets": [
            {"id": "configured-reference", "role": "configured-role"}
        ],
    }
    assert all(check.status == "PASS" for check in checks)


def test_placeholder_manifest_requires_review_and_fails_without_files(tmp_path):
    write_manifest(
        tmp_path,
        {
            "schema_version": 1,
            "dataset": {"name": "PENDING", "version": "PENDING"},
            "origin": "PENDING",
            "acquired_utc": None,
            "files": [],
        },
    )

    _, files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    statuses = {check.requirement: check.status for check in checks}
    assert statuses["manifest.dataset.name"] == "REVIEW"
    assert statuses["manifest.dataset.version"] == "REVIEW"
    assert statuses["manifest.origin"] == "REVIEW"
    assert statuses["manifest.acquired_utc"] == "REVIEW"
    assert statuses["manifest.files"] == "FAIL"
    assert files == []


def test_missing_manifest_is_a_critical_failure(tmp_path):
    manifest, files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    assert manifest is None
    assert files == []
    assert checks == [
        nb01_inputs.PreconditionCheck(
            "manifest", "FAIL", "missing or not a regular file"
        )
    ]


def test_manifest_verifies_file_integrity(tmp_path):
    data_file = tmp_path / "data" / "external" / "fixture.dat"
    data_file.parent.mkdir(parents=True)
    data_file.write_bytes(b"reference input\n")
    digest = hashlib.sha256(data_file.read_bytes()).hexdigest()
    write_manifest(tmp_path, valid_manifest("data/external/fixture.dat", digest))

    _, files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    assert not [check for check in checks if check.status == "FAIL"]
    assert files == [
        {
            "path": "data/external/fixture.dat",
            "sha256": digest,
            "size_bytes": len(b"reference input\n"),
        }
    ]


def test_manifest_rejects_hash_mismatch(tmp_path):
    data_file = tmp_path / "data" / "external" / "fixture.dat"
    data_file.parent.mkdir(parents=True)
    data_file.write_bytes(b"reference input\n")
    write_manifest(tmp_path, valid_manifest("data/external/fixture.dat", "0" * 64))

    _, files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    assert any("SHA-256 mismatch" in check.detail for check in checks)
    assert files == []


def test_manifest_rejects_missing_declared_file(tmp_path):
    write_manifest(
        tmp_path,
        valid_manifest("data/external/missing.dat", "0" * 64),
    )

    _, files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    assert any("missing regular file" in check.detail for check in checks)
    assert files == []


def test_manifest_rejects_paths_outside_external_data_directory(tmp_path):
    outside = tmp_path / "outside.dat"
    outside.write_bytes(b"outside")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    write_manifest(tmp_path, valid_manifest("outside.dat", digest))

    _, _, checks, _ = nb01_inputs.inspect_manifest(tmp_path)

    assert any(
        check.status == "FAIL" and "data/external" in check.detail
        for check in checks
    )


def test_prepare_stage1_writes_deterministic_reports_before_failure(tmp_path):
    write_project_config(tmp_path)
    write_manifest(
        tmp_path,
        {
            "schema_version": 1,
            "dataset": {"name": "PENDING", "version": "PENDING"},
            "origin": "PENDING",
            "acquired_utc": None,
            "files": [],
        },
    )
    context = {
        "git": {
            "available": True,
            "commit": "a" * 40,
            "branch": "fixture",
            "dirty": False,
        }
    }
    snapshot = {
        "pointer_path": "artifacts/reproducibility/latest.json",
        "snapshot_path": "artifacts/reproducibility/fixture/snapshot.json",
        "snapshot_sha256": "b" * 64,
    }

    result = nb01_inputs.prepare_nb01_stage1(
        project_root=tmp_path,
        run_context=context,
        reproducibility_snapshot=snapshot,
    )

    assert result.output_dir == tmp_path / "results" / "bioinformatics" / "nb01"
    assert result.report_path.is_file()
    assert result.provenance_path.is_file()
    provenance = json.loads(result.provenance_path.read_text(encoding="utf-8"))
    assert provenance["declared_targets"] == result.targets
    assert provenance["dataset_manifest"]["sha256"]
    assert provenance["reproducibility_snapshot"] == snapshot
    with pytest.raises(nb01_inputs.InputContractError, match="manifest.files"):
        result.report.raise_if_failed()


def test_nb01_is_valid_nbformat_and_starts_with_existing_gate():
    notebook_path = (
        Path(__file__).parents[1]
        / "src"
        / "workstreams"
        / "bioinformatics"
        / "notebooks"
        / "01_reference_dataset_and_target_identity.ipynb"
    )
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert isinstance(notebook["nbformat_minor"], int)
    assert isinstance(notebook["metadata"], dict)
    assert isinstance(notebook["cells"], list)
    assert notebook["cells"]
    assert all(
        isinstance(cell.get("metadata"), dict)
        and cell.get("cell_type") in {"code", "markdown", "raw"}
        and isinstance(cell.get("source"), list)
        for cell in notebook["cells"]
    )
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert "repro.assert_environment_ready()" in "".join(code_cells[0]["source"])
    assert all(cell["execution_count"] is None for cell in code_cells)
    assert all(cell["outputs"] == [] for cell in code_cells)
