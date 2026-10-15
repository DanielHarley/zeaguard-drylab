"""Record CP0 tests and optionally run the full regression in a faithful copy."""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def filehash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--full-suite", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "artifacts/validation/nb04_cp0" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True)
    protected = json.loads((root / "artifacts/validation/nb04_cp0/protected_baseline.json").read_text())
    env = dict(os.environ, PYTHONPATH="src:.")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    report = {
        "executed_utc": datetime.now(timezone.utc).isoformat(), "python_executable": sys.executable,
        "python_version": sys.version, "platform": platform.platform(),
        "os_release": Path("/etc/os-release").read_text() if Path("/etc/os-release").exists() else "",
        "PYTHONPATH": env["PYTHONPATH"], "runs": [], "isolated_copy": None,
        "python_dependencies": {name: version(name) for name in ("PyYAML", "jsonschema", "packaging", "pytest")},
        "informative_nb04_calibration": "NOT_EXECUTED", "real_nto_searches": "NOT_EXECUTED",
    }
    def run(name, test_args, cwd):
        xml = out / f"{name}.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", *test_args, f"--junitxml={xml}"]
        start = time.monotonic()
        result = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (out / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        suites = list(ET.parse(xml).getroot().iter("testsuite")) if xml.exists() else []
        counts = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
        counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
        entry = {"name": name, "command": cmd, "cwd": str(cwd), "returncode": result.returncode, "duration_seconds": time.monotonic() - start, **counts}
        report["runs"].append(entry)
        print(json.dumps(entry), flush=True)
        return result.returncode == 0
    ok = True
    for name, files in (
        ("cp0_contract", ["tests/test_nb04_cp0.py"]),
        ("n18_serialization", ["tests/test_nb04_serialization.py"]),
        ("n20_repro", ["tests/test_repro.py"]),
        ("nb01_inputs_regression", ["tests/test_nb01_inputs.py"]),
    ):
        ok = run(name, files, root) and ok
    if args.full_suite and ok:
        # Independent regular files, including Git history and all ignored input
        # payloads and upstream outputs. No shared writable file or symlink.
        isolated_parent = Path(tempfile.mkdtemp(prefix="zeaguard_nb04_cp0_"))
        isolated = isolated_parent / "workspace"
        shutil.copytree(root, isolated, ignore=shutil.ignore_patterns("artifacts", ".venv", "__pycache__", ".pytest_cache", ".agents", ".codex"))
        input_hashes = {p: filehash(isolated / p) for p in protected if (isolated / p).is_file()}
        source_hashes = {p: filehash(root / p) for p in input_hashes}
        patch_files = subprocess.check_output(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"]).decode().split("\0")
        patch_hashes = {p: filehash(root / p) for p in patch_files if p and (root / p).is_file()}
        patch_equal = all(filehash(isolated / p) == h for p, h in patch_hashes.items())
        data_files = {p.relative_to(root).as_posix(): filehash(p) for p in (root / "data").rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        data_equal = all((isolated / p).is_file() and filehash(isolated / p) == h for p, h in data_files.items())
        report["isolated_copy"] = {"path": str(isolated), "protected_inputs_compared": len(input_hashes), "protected_inputs_byte_identical": input_hashes == source_hashes, "untracked_patch_files_compared": len(patch_hashes), "untracked_patch_byte_identical": patch_equal, "data_files_compared": len(data_files), "data_byte_identical": data_equal, "cleanup": "RETAINED_FOR_AUDIT"}
        assert input_hashes == source_hashes and patch_equal and data_equal, "isolated copy differs from execution inputs or patch"
        print(json.dumps(report["isolated_copy"]), flush=True)
        ok = run("full_suite_isolated", [], isolated) and ok
    allowed = {"src/workstreams/bioinformatics/decisions/README.md"}
    differences = {p: {"before": h, "after": filehash(root / p) if (root / p).exists() else None} for p, h in protected.items() if not (root / p).exists() or filehash(root / p) != h}
    report["protected_files"] = {"baseline_count": len(protected), "differences": differences, "unexpected_differences": sorted(set(differences) - allowed)}
    ok = ok and not report["protected_files"]["unexpected_differences"]
    report["validation_result"] = "DEVELOPMENT_TEST_PASS" if ok else "VALIDATION_FAILED"
    report["certification_status"] = "NOT_CERTIFIED_PENDING_EXTERNAL_HUMAN_G0_REVIEW_AND_OPERATIONAL_REPRO_PROFILE"
    (out / "validation_record.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "artifacts/validation/nb04_cp0/latest_validation.json").write_text(json.dumps({"record": str((out / "validation_record.json").relative_to(root)), "sha256": filehash(out / "validation_record.json")}, indent=2) + "\n")
    print(f"Validation record: {out / 'validation_record.json'}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
