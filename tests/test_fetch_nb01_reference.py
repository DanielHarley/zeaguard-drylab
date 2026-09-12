from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path

import pytest

from scripts import fetch_nb01_reference as fetch
from zeaguard import nb01_inputs


class FakeResponse(BytesIO):
    def __init__(self, payload: bytes, url: str = fetch.SOURCE_URL):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def fixed_clock() -> datetime:
    return datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)


def test_acquire_downloads_and_materializes_manifest_without_network(tmp_path):
    payload = b"compressed fixture bytes"
    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(payload)

    result = fetch.acquire_reference(tmp_path, opener=opener, now=fixed_clock)

    destination = tmp_path / fetch.DESTINATION_RELATIVE
    manifest_path = tmp_path / fetch.MANIFEST_RELATIVE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert destination.read_bytes() == payload
    assert result.reused is False
    assert result.sha256 == fetch._sha256_file(destination)
    assert result.acquired_utc == "2026-09-11T12:30:00Z"
    assert manifest["dataset"] == {
        "name": fetch.DATASET_NAME,
        "accession": fetch.TSA_ACCESSION,
        "version": fetch.TSA_ACCESSION_VERSION,
        "bioproject": fetch.BIOPROJECT_ACCESSION,
    }
    assert manifest["origin"] == fetch.SOURCE_URL
    assert manifest["files"][0]["sha256"] == result.sha256
    assert len(requests) == 1

    _, validated_files, checks, _ = nb01_inputs.inspect_manifest(tmp_path)
    assert not [check for check in checks if check.status == "FAIL"]
    assert validated_files[0]["sha256"] == result.sha256


def test_acquire_reuses_file_when_manifest_hash_matches(tmp_path):
    payload = b"stable bytes"
    fetch.acquire_reference(
        tmp_path,
        opener=lambda request, timeout: FakeResponse(payload),
        now=fixed_clock,
    )

    def forbidden_opener(request, timeout):
        raise AssertionError("network opener must not be called during reuse")

    result = fetch.acquire_reference(tmp_path, opener=forbidden_opener)

    assert result.reused is True
    assert result.acquired_utc == "2026-09-11T12:30:00Z"


def test_acquire_rematerializes_missing_file_without_rewriting_pinned_manifest(
    tmp_path,
):
    payload = b"stable bytes"
    fetch.acquire_reference(
        tmp_path,
        opener=lambda request, timeout: FakeResponse(payload),
        now=fixed_clock,
    )
    destination = tmp_path / fetch.DESTINATION_RELATIVE
    manifest_path = tmp_path / fetch.MANIFEST_RELATIVE
    original_manifest = manifest_path.read_bytes()
    destination.unlink()

    result = fetch.acquire_reference(
        tmp_path,
        opener=lambda request, timeout: FakeResponse(payload),
        now=lambda: datetime(2030, 1, 1, tzinfo=timezone.utc),
    )

    assert result.reused is False
    assert destination.read_bytes() == payload
    assert manifest_path.read_bytes() == original_manifest
    assert result.acquired_utc == "2026-09-11T12:30:00Z"


def test_acquire_rejects_existing_file_with_hash_mismatch(tmp_path):
    fetch.acquire_reference(
        tmp_path,
        opener=lambda request, timeout: FakeResponse(b"original bytes"),
        now=fixed_clock,
    )
    destination = tmp_path / fetch.DESTINATION_RELATIVE
    destination.write_bytes(b"changed bytes")

    def forbidden_opener(request, timeout):
        raise AssertionError("network opener must not be called after mismatch")

    with pytest.raises(fetch.AcquisitionError, match="differs from the manifest"):
        fetch.acquire_reference(tmp_path, opener=forbidden_opener)
    assert destination.read_bytes() == b"changed bytes"


def test_acquire_rejects_existing_file_without_manifest_entry(tmp_path):
    destination = tmp_path / fetch.DESTINATION_RELATIVE
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"untracked bytes")
    manifest_path = tmp_path / fetch.MANIFEST_RELATIVE
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset": {"name": "PENDING", "version": "PENDING"},
                "origin": "PENDING",
                "acquired_utc": None,
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(fetch.AcquisitionError, match="refusing to overwrite"):
        fetch.acquire_reference(tmp_path)
    assert destination.read_bytes() == b"untracked bytes"


def test_acquire_cleans_partial_download_on_content_length_mismatch(tmp_path):
    class TruncatedResponse(FakeResponse):
        def __init__(self):
            super().__init__(b"short")
            self.headers["Content-Length"] = "100"

    with pytest.raises(fetch.AcquisitionError, match="incomplete download"):
        fetch.acquire_reference(
            tmp_path,
            opener=lambda request, timeout: TruncatedResponse(),
            now=fixed_clock,
        )

    assert not (tmp_path / fetch.DESTINATION_RELATIVE).exists()
    assert not list((tmp_path / fetch.DESTINATION_RELATIVE).parent.glob("*.part-*"))
