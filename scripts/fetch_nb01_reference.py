"""Acquire the pinned public TSA reference dataset required by NB01."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, BinaryIO, Callable
from urllib.request import Request, urlopen


TSA_ACCESSION = "GITV00000000"
TSA_ACCESSION_VERSION = "GITV00000000.1"
BIOPROJECT_ACCESSION = "PRJNA579843"
DATASET_NAME = "TSA: Dalbulus maidis, transcriptome shotgun assembly"
SOURCE_URL = "https://ftp.ncbi.nlm.nih.gov/genbank/tsa/G/tsa.GITV.1.fsa_nt.gz"
DESTINATION_RELATIVE = Path("data/external/tsa.GITV.1.fsa_nt.gz")
MANIFEST_RELATIVE = Path("data/reference/manifest.json")
USER_AGENT = "zeaguard-drylab/0.0.1 (NB01 public dataset acquisition)"
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class AcquisitionError(RuntimeError):
    """Raised when acquisition cannot preserve the declared dataset contract."""


@dataclass(frozen=True)
class AcquisitionResult:
    path: str
    sha256: str
    size_bytes: int
    acquired_utc: str
    origin: str
    reused: bool


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"existing manifest is unreadable or invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise AcquisitionError("existing manifest top level must be an object")
    return value


def _manifest_file_entry(
    manifest: dict[str, Any] | None,
    relative_path: str,
) -> dict[str, Any] | None:
    if manifest is None:
        return None
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    matches = [
        entry
        for entry in files
        if isinstance(entry, dict) and entry.get("path") == relative_path
    ]
    if len(matches) > 1:
        raise AcquisitionError(f"manifest contains duplicate entries for {relative_path}")
    return matches[0] if matches else None


def _validated_manifest_hash(entry: dict[str, Any] | None) -> str | None:
    if entry is None:
        return None
    value = entry.get("sha256")
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise AcquisitionError("existing manifest contains an invalid SHA-256")
    return value.lower()


def _validate_reusable_manifest(manifest: dict[str, Any]) -> None:
    dataset = manifest.get("dataset")
    expected = {
        "name": DATASET_NAME,
        "accession": TSA_ACCESSION,
        "version": TSA_ACCESSION_VERSION,
        "bioproject": BIOPROJECT_ACCESSION,
    }
    if manifest.get("schema_version") != 1:
        raise AcquisitionError("existing manifest schema_version does not equal 1")
    if not isinstance(dataset, dict):
        raise AcquisitionError("existing manifest dataset metadata is missing")
    for field, expected_value in expected.items():
        if dataset.get(field) != expected_value:
            raise AcquisitionError(
                f"existing manifest dataset.{field} does not match {expected_value}"
            )
    if manifest.get("origin") != SOURCE_URL:
        raise AcquisitionError("existing manifest origin does not match the pinned source URL")
    acquired_utc = manifest.get("acquired_utc")
    if not isinstance(acquired_utc, str) or not acquired_utc:
        raise AcquisitionError("existing manifest acquired_utc is missing")


def _write_manifest_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _manifest_payload(
    digest: str,
    size_bytes: int,
    acquired_utc: str,
    origin: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "dataset": {
            "name": DATASET_NAME,
            "accession": TSA_ACCESSION,
            "version": TSA_ACCESSION_VERSION,
            "bioproject": BIOPROJECT_ACCESSION,
        },
        "origin": origin,
        "acquired_utc": acquired_utc,
        "files": [
            {
                "path": DESTINATION_RELATIVE.as_posix(),
                "sha256": digest,
                "size_bytes": size_bytes,
            }
        ],
    }


def _download_to_temporary(
    temporary: Path,
    opener: Callable[..., BinaryIO],
    timeout: float,
) -> tuple[str, int, str]:
    request = Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    transferred = 0
    try:
        with opener(request, timeout=timeout) as response, temporary.open("xb") as handle:
            effective_url = response.geturl()
            content_length = response.headers.get("Content-Length")
            expected_size = int(content_length) if content_length is not None else None
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                transferred += len(block)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    if expected_size is not None and transferred != expected_size:
        temporary.unlink(missing_ok=True)
        raise AcquisitionError(
            f"incomplete download: expected {expected_size} bytes, received {transferred}"
        )
    return digest.hexdigest(), transferred, effective_url


def acquire_reference(
    project_root: Path,
    opener: Callable[..., BinaryIO] = urlopen,
    now: Callable[[], datetime] | None = None,
    timeout: float = 120.0,
) -> AcquisitionResult:
    """Materialize the pinned TSA file and its manifest without silent replacement."""
    root = project_root.resolve()
    destination = (root / DESTINATION_RELATIVE).resolve()
    manifest_path = (root / MANIFEST_RELATIVE).resolve()
    destination.relative_to(root)
    manifest_path.relative_to(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(manifest_path)
    relative_path = DESTINATION_RELATIVE.as_posix()
    entry = _manifest_file_entry(manifest, relative_path)
    expected_hash = _validated_manifest_hash(entry)
    pinned_manifest = manifest is not None and expected_hash is not None
    if pinned_manifest:
        _validate_reusable_manifest(manifest)

    if destination.exists():
        if not destination.is_file():
            raise AcquisitionError(f"destination exists and is not a regular file: {destination}")
        if manifest is None or expected_hash is None:
            raise AcquisitionError(
                "destination already exists without a matching manifest hash; refusing to overwrite"
            )
        observed_hash = _sha256_file(destination)
        if observed_hash != expected_hash:
            raise AcquisitionError(
                "destination SHA-256 differs from the manifest; refusing to overwrite"
            )
        return AcquisitionResult(
            path=relative_path,
            sha256=observed_hash,
            size_bytes=destination.stat().st_size,
            acquired_utc=manifest["acquired_utc"],
            origin=manifest["origin"],
            reused=True,
        )

    temporary = destination.with_name(f".{destination.name}.part-{os.getpid()}")
    if temporary.exists():
        raise AcquisitionError(f"temporary download path already exists: {temporary}")
    digest, size_bytes, effective_url = _download_to_temporary(
        temporary, opener, timeout
    )
    if effective_url != SOURCE_URL:
        temporary.unlink(missing_ok=True)
        raise AcquisitionError(
            f"download resolved to an unexpected URL: {effective_url}"
        )
    if expected_hash is not None and digest != expected_hash:
        temporary.unlink(missing_ok=True)
        raise AcquisitionError(
            "downloaded SHA-256 differs from the existing manifest; refusing publication"
        )

    if pinned_manifest:
        acquired_utc = manifest["acquired_utc"]
        origin = manifest["origin"]
        new_manifest = None
    else:
        clock = now or (lambda: datetime.now(timezone.utc))
        acquired_utc = (
            clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        origin = effective_url
        new_manifest = _manifest_payload(
            digest, size_bytes, acquired_utc, effective_url
        )
    try:
        os.replace(temporary, destination)
        if new_manifest is not None:
            _write_manifest_atomic(manifest_path, new_manifest)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
    return AcquisitionResult(
        path=relative_path,
        sha256=digest,
        size_bytes=size_bytes,
        acquired_utc=acquired_utc,
        origin=origin,
        reused=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="ZeaGuard repository root; discovered automatically when omitted",
    )
    args = parser.parse_args(argv)
    root = (
        args.project_root.resolve()
        if args.project_root
        else Path(__file__).resolve().parents[1]
    )
    try:
        result = acquire_reference(root)
    except (AcquisitionError, OSError) as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
