from __future__ import annotations

import json
from pathlib import Path
import platform

import pytest

import zeaguard.repro as repro


def make_config(tmp_path: Path, **overrides) -> repro.ReproConfig:
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "repro.yaml"
    config_path.write_text("schema_version: 1\n", encoding="utf-8")
    raw = {
        "schema_version": 1,
        "platform": {"allowed_systems": [platform.system()]},
        "python": {"spec": ">=3"},
        "python_dependencies": [],
        "external_tools": [],
        "required_paths": [],
        "supporting_configs": [],
        "snapshot_dir": "artifacts/reproducibility",
    }
    raw.update(overrides)
    return repro.ReproConfig(raw, config_path)


def context(commit: str = "a" * 40, dirty: bool = False) -> dict:
    return {
        "created_utc": "2026-09-11T00:00:00+00:00",
        "project_root": "unused",
        "platform": {"system": "Linux", "machine": "x86_64"},
        "python": {"version": "3.12.1", "executable": "/python"},
        "git": {
            "available": True,
            "commit": commit,
            "branch": "master",
            "dirty": dirty,
        },
    }


def passing_report() -> repro.ReproReport:
    return repro.ReproReport([repro.CheckResult("example", "PASS", "ok")])


def test_find_project_root_from_nested_directory():
    nested = Path(__file__).parent
    assert repro.find_project_root(nested) == Path(__file__).parents[1]


def test_find_project_root_rejects_unmarked_tree(tmp_path):
    with pytest.raises(repro.ReproGateError, match="project root"):
        repro.find_project_root(tmp_path)


def test_load_real_configuration():
    cfg = repro.load_repro_config()
    assert cfg.schema_version == 1
    assert cfg.snapshot_dir == "artifacts/reproducibility"
    assert cfg.supporting_configs == ["config/project.yaml"]


def test_load_configuration_rejects_invalid_schema(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "config" / "repro.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    schema = {
        "type": "object",
        "required": ["missing"],
        "properties": {"missing": {"type": "string"}},
    }
    (tmp_path / "config" / "repro.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(repro.ReproGateError, match="invalid reproducibility"):
        repro.load_repro_config()


def test_report_raises_for_failure():
    report = repro.ReproReport([repro.CheckResult("example", "PASS", "ok")])
    report.raise_if_failed()
    report.results.append(repro.CheckResult("example", "FAIL", "broken"))
    with pytest.raises(repro.ReproGateError, match="example: broken"):
        report.raise_if_failed()


def test_check_platform(monkeypatch, tmp_path):
    cfg = make_config(tmp_path, platform={"allowed_systems": ["Linux"]})
    monkeypatch.setattr(repro.platform, "system", lambda: "Linux")
    assert repro.check_platform(cfg)[0].status == "PASS"
    monkeypatch.setattr(repro.platform, "system", lambda: "Windows")
    assert repro.check_platform(cfg)[0].status == "FAIL"


def test_check_python(monkeypatch, tmp_path):
    cfg = make_config(tmp_path, python={"spec": ">=3.12,<3.13"})
    monkeypatch.setattr(repro.platform, "python_version", lambda: "3.12.9")
    assert repro.check_python(cfg)[0].status == "PASS"
    monkeypatch.setattr(repro.platform, "python_version", lambda: "3.13.0")
    assert repro.check_python(cfg)[0].status == "FAIL"


def test_check_python_dependencies_records_versions(monkeypatch, tmp_path):
    cfg = make_config(
        tmp_path,
        python_dependencies=[{"distribution": "demo", "module": "demo"}],
    )
    monkeypatch.setattr(repro.util, "find_spec", lambda name: object())
    monkeypatch.setattr(repro.metadata, "version", lambda name: "1.2.3")
    results, versions = repro.check_python_dependencies(cfg)
    assert results[0].status == "PASS"
    assert versions == {"demo": "1.2.3"}


def test_check_python_dependencies_rejects_missing_module(monkeypatch, tmp_path):
    cfg = make_config(
        tmp_path,
        python_dependencies=[{"distribution": "demo", "module": "demo"}],
    )
    monkeypatch.setattr(repro.util, "find_spec", lambda name: None)
    monkeypatch.setattr(repro.metadata, "version", lambda name: "1.2.3")
    results, _ = repro.check_python_dependencies(cfg)
    assert results[0].status == "FAIL"


def test_probe_tool_reports_missing_command(monkeypatch):
    monkeypatch.setattr(repro.shutil, "which", lambda command: None)
    probe = repro._probe_tool(
        {"command": ["missing", "--version"], "version_regex": r"([0-9.]+)"}
    )
    assert probe == {"available": False, "version": None, "detail": "command not found"}


def test_check_external_tools_enforces_minimum_version(monkeypatch, tmp_path):
    cfg = make_config(
        tmp_path,
        external_tools=[
            {
                "name": "demo",
                "command": ["demo", "--version"],
                "version_regex": r"([0-9.]+)",
                "min_version": "2.0",
            }
        ],
    )
    monkeypatch.setattr(
        repro,
        "_probe_tool",
        lambda tool: {"available": True, "version": "1.9", "detail": "version detected"},
    )
    results, _ = repro.check_external_tools(cfg)
    assert results[0].status == "FAIL"


@pytest.mark.parametrize(
    ("git_context", "allow_dirty", "expected"),
    [
        (context(), False, "PASS"),
        (context(dirty=True), False, "FAIL"),
        (context(dirty=True), True, "PASS"),
        (context(commit="invalid"), False, "FAIL"),
    ],
)
def test_check_git_state(git_context, allow_dirty, expected):
    assert repro.check_git_state(git_context, allow_dirty)[0].status == expected


def test_check_required_paths(tmp_path):
    (tmp_path / "present").write_text("ok", encoding="utf-8")
    cfg = make_config(tmp_path, required_paths=["present", "missing"])
    results = repro.check_required_paths(cfg)
    assert [item.status for item in results] == ["PASS", "FAIL"]


def test_collect_config_hashes(tmp_path):
    cfg = make_config(tmp_path, supporting_configs=["config/project.yaml"])
    (tmp_path / "environment.yml").write_text("env", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("project", encoding="utf-8")
    (tmp_path / "config" / "repro.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "config" / "project.yaml").write_text("project", encoding="utf-8")
    hashes = repro.collect_config_hashes(cfg)
    assert set(hashes) == {
        "config/repro.yaml",
        "config/repro.schema.json",
        "environment.yml",
        "pyproject.toml",
        "config/project.yaml",
    }
    assert all(len(value) == 64 for value in hashes.values())


def test_runtime_fingerprint_is_deterministic_and_sensitive():
    ctx = context()
    first = repro.compute_runtime_fingerprint(ctx, {"demo": "1.0"}, {})
    second = repro.compute_runtime_fingerprint(ctx, {"demo": "1.0"}, {})
    changed = repro.compute_runtime_fingerprint(ctx, {"demo": "2.0"}, {})
    assert first == second
    assert first["sha256"] != changed["sha256"]


def test_build_snapshot_rejects_failed_report(tmp_path):
    cfg = make_config(tmp_path)
    report = repro.ReproReport([repro.CheckResult("example", "FAIL", "broken")])
    with pytest.raises(repro.ReproGateError):
        repro.build_snapshot(context(), cfg, report, {})


def test_write_env_snapshot_publishes_pointer(tmp_path):
    snapshot = {
        "runtime_fingerprint": {"sha256": "f" * 64},
        "value": 1,
    }
    snapshot_path = repro.write_env_snapshot(snapshot, tmp_path)
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert snapshot_path.is_file()
    assert latest["snapshot_file"] == f"{snapshot_path.parent.name}/snapshot.json"
    assert latest["snapshot_sha256"] == repro._sha256_file(snapshot_path)


def test_assert_environment_ready_accepts_matching_snapshot(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    ctx = context()
    collected = {
        "context": ctx,
        "config_hashes": {"config/repro.yaml": "a" * 64},
        "runtime_fingerprint": {"sha256": "b" * 64},
    }
    snapshot = repro.build_snapshot(ctx, cfg, passing_report(), collected)
    repro.write_env_snapshot(snapshot, tmp_path / "artifacts" / "reproducibility")
    monkeypatch.setattr(
        repro,
        "run_all_checks",
        lambda allow_dirty=False: (cfg, passing_report(), collected),
    )
    repro.assert_environment_ready()


def test_assert_environment_ready_rejects_changed_fingerprint(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    ctx = context()
    collected = {
        "context": ctx,
        "config_hashes": {"config/repro.yaml": "a" * 64},
        "runtime_fingerprint": {"sha256": "b" * 64},
    }
    snapshot = repro.build_snapshot(ctx, cfg, passing_report(), collected)
    repro.write_env_snapshot(snapshot, tmp_path / "artifacts" / "reproducibility")
    changed = {**collected, "runtime_fingerprint": {"sha256": "c" * 64}}
    monkeypatch.setattr(
        repro,
        "run_all_checks",
        lambda allow_dirty=False: (cfg, passing_report(), changed),
    )
    with pytest.raises(repro.ReproGateError, match="fingerprint"):
        repro.assert_environment_ready()


def test_notebook_is_valid_json():
    notebook = (
        Path(__file__).parents[1]
        / "src"
        / "workstreams"
        / "bioinformatics"
        / "notebooks"
        / "00_reproducibility_gate.ipynb"
    )
    parsed = json.loads(notebook.read_text(encoding="utf-8"))
    assert parsed["nbformat"] == 4
    assert all(cell["execution_count"] is None for cell in parsed["cells"] if cell["cell_type"] == "code")
