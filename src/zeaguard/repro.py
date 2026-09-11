"""Minimal reproducibility gate for ZeaGuard workstreams."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any


SNAPSHOT_SCHEMA_VERSION = 1


class ReproGateError(RuntimeError):
    """Raised when the current environment cannot satisfy the gate."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


@dataclass
class ReproReport:
    results: list[CheckResult]

    def failures(self) -> list[CheckResult]:
        return [result for result in self.results if result.status == "FAIL"]

    def raise_if_failed(self) -> None:
        failures = self.failures()
        if failures:
            details = "\n".join(f"{item.name}: {item.detail}" for item in failures)
            raise ReproGateError(f"reproducibility gate failed:\n{details}")

    def to_text(self) -> str:
        return "\n".join(
            f"{item.status:4}  {item.name}: {item.detail}" for item in self.results
        )


@dataclass(frozen=True)
class ReproConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def root(self) -> Path:
        return self.path.parent.parent

    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest parent containing the ZeaGuard project markers."""
    candidate = (start or Path.cwd()).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (directory / "pyproject.toml").is_file() and (
            directory / "config" / "repro.yaml"
        ).is_file():
            return directory
    raise ReproGateError("could not find project root")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(_json_bytes(value))
    os.replace(temporary, path)


def load_repro_config(
    path: str | Path = "config/repro.yaml",
    schema_path: str | Path = "config/repro.schema.json",
) -> ReproConfig:
    """Load and structurally validate the gate configuration."""
    root = find_project_root()
    config_file = Path(path)
    schema_file = Path(schema_path)
    if not config_file.is_absolute():
        config_file = root / config_file
    if not schema_file.is_absolute():
        schema_file = root / schema_file

    try:
        import yaml
        import jsonschema
    except ImportError as exc:
        raise ReproGateError("PyYAML and jsonschema are required") from exc

    try:
        raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReproGateError(f"could not load reproducibility configuration: {exc}") from exc

    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError as exc:
        raise ReproGateError(f"invalid reproducibility configuration: {exc.message}") from exc

    return ReproConfig(raw=raw, path=config_file)


def _git(root: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if process.returncode:
        raise ReproGateError(process.stderr.strip() or "git command failed")
    return process.stdout.strip()


def collect_run_context(root: Path | None = None) -> dict[str, Any]:
    """Collect execution and Git identity without changing the workspace."""
    project_root = (root or find_project_root()).resolve()
    try:
        commit = _git(project_root, "rev-parse", "HEAD")
        branch = _git(project_root, "rev-parse", "--abbrev-ref", "HEAD")
        dirty = bool(_git(project_root, "status", "--porcelain"))
        git = {"available": True, "commit": commit, "branch": branch, "dirty": dirty}
    except (OSError, subprocess.SubprocessError, ReproGateError):
        git = {"available": False, "commit": None, "branch": None, "dirty": None}

    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "git": git,
    }


def check_platform(cfg: ReproConfig) -> list[CheckResult]:
    current = platform.system()
    allowed = cfg.platform["allowed_systems"]
    passed = current in allowed
    return [
        CheckResult(
            "platform",
            "PASS" if passed else "FAIL",
            f"{current}; allowed: {', '.join(allowed)}",
        )
    ]


def check_python(cfg: ReproConfig) -> list[CheckResult]:
    from packaging.specifiers import SpecifierSet

    current = platform.python_version()
    spec = cfg.python["spec"]
    passed = current in SpecifierSet(spec)
    return [
        CheckResult(
            "python",
            "PASS" if passed else "FAIL",
            f"{current}; required: {spec}",
        )
    ]


def check_python_dependencies(
    cfg: ReproConfig,
) -> tuple[list[CheckResult], dict[str, str | None]]:
    results: list[CheckResult] = []
    versions: dict[str, str | None] = {}
    for dependency in cfg.python_dependencies:
        distribution = dependency["distribution"]
        module = dependency["module"]
        importable = util.find_spec(module) is not None
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            version = None
        versions[distribution] = version
        passed = importable and version is not None
        detail = version if passed else f"module={importable}, distribution={version}"
        results.append(
            CheckResult(
                f"python_dependency:{distribution}",
                "PASS" if passed else "FAIL",
                detail,
            )
        )
    return results, versions


def _probe_tool(tool: dict[str, Any]) -> dict[str, Any]:
    command = tool["command"]
    if shutil.which(command[0]) is None:
        return {"available": False, "version": None, "detail": "command not found"}
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "version": None, "detail": str(exc)}
    output = f"{process.stdout}\n{process.stderr}"
    match = re.search(tool["version_regex"], output)
    if process.returncode != 0 or match is None:
        return {
            "available": False,
            "version": None,
            "detail": f"version probe failed with exit code {process.returncode}",
        }
    return {"available": True, "version": match.group(1), "detail": "version detected"}


def check_external_tools(
    cfg: ReproConfig,
) -> tuple[list[CheckResult], dict[str, dict[str, Any]]]:
    from packaging.version import InvalidVersion, Version

    results: list[CheckResult] = []
    probes: dict[str, dict[str, Any]] = {}
    for tool in cfg.external_tools:
        name = tool["name"]
        probe = _probe_tool(tool)
        probes[name] = probe
        passed = probe["available"]
        if passed:
            try:
                passed = Version(probe["version"]) >= Version(tool["min_version"])
            except InvalidVersion:
                passed = False
        detail = (
            f"{probe['version']}; required >= {tool['min_version']}"
            if probe["available"]
            else probe["detail"]
        )
        results.append(CheckResult(f"external_tool:{name}", "PASS" if passed else "FAIL", detail))
    return results, probes


def check_git_state(context: dict[str, Any], allow_dirty: bool) -> list[CheckResult]:
    git = context["git"]
    if not git["available"]:
        return [CheckResult("git", "FAIL", "Git repository unavailable")]
    if not re.fullmatch(r"[0-9a-f]{40}", git["commit"] or ""):
        return [CheckResult("git", "FAIL", "invalid commit SHA")]
    if git["dirty"] and not allow_dirty:
        return [CheckResult("git", "FAIL", "working tree is dirty")]
    detail = f"{git['commit']} on {git['branch']}"
    if git["dirty"]:
        detail += ", dirty state explicitly allowed"
    return [CheckResult("git", "PASS", detail)]


def check_required_paths(cfg: ReproConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    for relative in cfg.required_paths:
        path = cfg.root / relative
        passed = path.exists() and os.access(path, os.R_OK)
        results.append(
            CheckResult(
                f"path:{relative}",
                "PASS" if passed else "FAIL",
                "readable" if passed else "missing or unreadable",
            )
        )
    return results


def collect_config_hashes(cfg: ReproConfig) -> dict[str, str]:
    relative_paths = [
        "config/repro.yaml",
        "config/repro.schema.json",
        "environment.yml",
        "pyproject.toml",
        *cfg.supporting_configs,
    ]
    hashes: dict[str, str] = {}
    for relative in dict.fromkeys(relative_paths):
        path = cfg.root / relative
        if not path.is_file():
            raise ReproGateError(f"configuration file missing: {relative}")
        hashes[relative] = _sha256_file(path)
    return hashes


def compute_runtime_fingerprint(
    context: dict[str, Any],
    python_versions: dict[str, str | None],
    tool_probes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fields = {
        "platform": context["platform"],
        "python_version": context["python"]["version"],
        "python_dependencies": python_versions,
        "external_tools": {
            name: probe["version"] for name, probe in sorted(tool_probes.items())
        },
    }
    return {"fields": fields, "sha256": _sha256_bytes(_json_bytes(fields))}


def run_all_checks(
    config_path: str | Path = "config/repro.yaml",
    schema_path: str | Path = "config/repro.schema.json",
    allow_dirty: bool = False,
) -> tuple[ReproConfig, ReproReport, dict[str, Any]]:
    cfg = load_repro_config(config_path, schema_path)
    context = collect_run_context(cfg.root)
    dependency_results, dependency_versions = check_python_dependencies(cfg)
    tool_results, tool_probes = check_external_tools(cfg)
    results = [
        *check_platform(cfg),
        *check_python(cfg),
        *dependency_results,
        *tool_results,
        *check_git_state(context, allow_dirty),
        *check_required_paths(cfg),
    ]
    collected = {
        "context": context,
        "config_hashes": collect_config_hashes(cfg),
        "python_versions": dependency_versions,
        "tool_probes": tool_probes,
    }
    collected["runtime_fingerprint"] = compute_runtime_fingerprint(
        context, dependency_versions, tool_probes
    )
    return cfg, ReproReport(results), collected


def build_snapshot(
    context: dict[str, Any],
    cfg: ReproConfig,
    report: ReproReport,
    collected: dict[str, Any],
    allow_dirty: bool = False,
) -> dict[str, Any]:
    report.raise_if_failed()
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_utc": context["created_utc"],
        "git": context["git"],
        "allow_dirty": allow_dirty,
        "config_hashes": collected["config_hashes"],
        "runtime_fingerprint": collected["runtime_fingerprint"],
        "checks": [asdict(item) for item in report.results],
    }


def write_env_snapshot(snapshot: dict[str, Any], snapshot_dir: str | Path) -> Path:
    """Publish an immutable snapshot directory and update ``latest.json`` atomically."""
    root = find_project_root()
    destination = Path(snapshot_dir)
    if not destination.is_absolute():
        destination = root / destination
    destination.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory_name = f"{stamp}_{snapshot['runtime_fingerprint']['sha256'][:12]}"
    temporary = destination / f".tmp-{os.getpid()}-{stamp}"
    final = destination / directory_name
    temporary.mkdir()
    try:
        snapshot_file = temporary / "snapshot.json"
        snapshot_file.write_bytes(_json_bytes(snapshot))
        snapshot_hash = _sha256_file(snapshot_file)
        os.replace(temporary, final)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    _atomic_write_json(
        destination / "latest.json",
        {
            "snapshot_file": f"{directory_name}/snapshot.json",
            "snapshot_sha256": snapshot_hash,
        },
    )
    return final / "snapshot.json"


def assert_environment_ready(allow_dirty: bool = False) -> None:
    """Verify that the current environment matches the latest local snapshot."""
    cfg, report, collected = run_all_checks(allow_dirty=allow_dirty)
    report.raise_if_failed()
    snapshot_dir = cfg.root / cfg.snapshot_dir
    latest_path = snapshot_dir / "latest.json"
    if not latest_path.is_file():
        raise ReproGateError("latest reproducibility snapshot is missing; run Notebook 00")

    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        snapshot_path = (snapshot_dir / latest["snapshot_file"]).resolve()
        snapshot_path.relative_to(snapshot_dir.resolve())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise ReproGateError(f"invalid latest reproducibility snapshot: {exc}") from exc

    if _sha256_file(snapshot_path) != latest.get("snapshot_sha256"):
        raise ReproGateError("snapshot hash mismatch; run Notebook 00")

    problems: list[str] = []
    if collected["context"]["git"]["commit"] != snapshot["git"]["commit"]:
        problems.append("Git commit changed")
    if collected["config_hashes"] != snapshot["config_hashes"]:
        problems.append("configuration hashes changed")
    if collected["runtime_fingerprint"]["sha256"] != snapshot["runtime_fingerprint"]["sha256"]:
        problems.append("runtime fingerprint changed")
    if problems:
        raise ReproGateError("environment differs from snapshot: " + ", ".join(problems))
