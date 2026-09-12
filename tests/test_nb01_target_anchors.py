from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from zeaguard import nb01_inputs


def configured_targets() -> dict[str, list[dict[str, str]]]:
    return {
        "intervention_targets": [{"id": "target-a"}],
        "reference_targets": [{"id": "target-b"}],
    }


def anchor_record(
    target_id: str,
    target_role: str,
    evidence_strength: str = "strong",
    **overrides: str,
) -> dict[str, str]:
    record = {
        "target_id": target_id,
        "target_role": target_role,
        "aliases": "NA",
        "source_type": "primary_publication",
        "source_reference": "Fixture et al. 2026",
        "source_identifier": "DOI:10.0000/fixture",
        "published_transcript_id": "NA",
        "published_protein_id": "NA",
        "published_accession": "NA",
        "documented_features": "Documented fixture feature",
        "evidence_strength": evidence_strength,
        "identity_status": "requires_computational_resolution",
        "notes": "Identifier gaps are retained for the next stage.",
    }
    record.update(overrides)
    return record


def write_anchors(root: Path, records: list[dict[str, str]]) -> Path:
    path = root / "data" / "reference" / "target_anchors.tsv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=nb01_inputs.TARGET_ANCHOR_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)
    return path


def test_valid_anchor_table_accepts_na_identifiers_as_review(tmp_path):
    write_anchors(
        tmp_path,
        [
            anchor_record(
                "target-a",
                "intervention",
                published_transcript_id="published-transcript",
                published_protein_id="published-protein",
                published_accession="published-accession",
            ),
            anchor_record("target-b", "reference", evidence_strength="partial"),
        ],
    )

    records, checks, _ = nb01_inputs.inspect_target_anchors(
        tmp_path, configured_targets()
    )

    assert [record["target_id"] for record in records] == ["target-a", "target-b"]
    assert not [check for check in checks if check.status == "FAIL"]
    identifier_statuses = {
        check.requirement: check.status
        for check in checks
        if check.requirement.startswith("target_anchors.identifiers.")
    }
    assert identifier_statuses == {
        "target_anchors.identifiers.target-a": "PASS",
        "target_anchors.identifiers.target-b": "REVIEW",
    }


@pytest.mark.parametrize(
    ("records", "requirement"),
    [
        (
            [anchor_record("target-a", "intervention")],
            "target_anchors.expected_targets",
        ),
        (
            [
                anchor_record("target-a", "intervention"),
                anchor_record("target-b", "reference"),
                anchor_record("target-c", "reference"),
            ],
            "target_anchors.unexpected_targets",
        ),
        (
            [
                anchor_record("target-a", "intervention"),
                anchor_record("target-a", "intervention"),
                anchor_record("target-b", "reference"),
            ],
            "target_anchors.unique_target_id",
        ),
    ],
)
def test_anchor_table_rejects_target_set_errors(tmp_path, records, requirement):
    write_anchors(tmp_path, records)

    _, checks, _ = nb01_inputs.inspect_target_anchors(
        tmp_path, configured_targets()
    )

    assert any(
        check.requirement == requirement and check.status == "FAIL"
        for check in checks
    )


def test_anchor_table_rejects_missing_source_and_role_mismatch(tmp_path):
    write_anchors(
        tmp_path,
        [
            anchor_record(
                "target-a",
                "reference",
                source_reference="",
            ),
            anchor_record("target-b", "reference"),
        ],
    )

    _, checks, _ = nb01_inputs.inspect_target_anchors(
        tmp_path, configured_targets()
    )
    statuses = {check.requirement: check.status for check in checks}

    assert statuses["target_anchors.required_values"] == "FAIL"
    assert statuses["target_anchors.target_roles"] == "FAIL"


def test_prepare_stage2_writes_classified_report(tmp_path):
    anchor_path = write_anchors(
        tmp_path,
        [
            anchor_record("target-a", "intervention"),
            anchor_record("target-b", "reference", evidence_strength="partial"),
        ],
    )

    result = nb01_inputs.prepare_nb01_stage2(
        project_root=tmp_path,
        targets=configured_targets(),
    )

    assert result.anchor_path == anchor_path
    assert result.report_path.is_file()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["strong_anchors"] == ["target-a"]
    assert report["partial_anchors"] == ["target-b"]
    assert report["requires_computational_resolution"] == [
        "target-a",
        "target-b",
    ]
    assert [target["status"] for target in report["targets"]] == [
        "REVIEW",
        "REVIEW",
    ]
    assert len(report["target_anchor_file"]["sha256"]) == 64
    result.report.raise_if_failed()
