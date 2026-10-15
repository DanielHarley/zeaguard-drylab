from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path
import platform

import jsonschema
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
    assert cfg.schema_version == 2
    assert cfg.raw["checkpoint_required_paths"] == {
        "nb04_cp0": [
            "config/nb04_nto_policy.yaml",
            "config/nb04_nto_panel.tsv",
            "config/nb04_exposure_scenarios.tsv",
            "config/nb04_receptor_exposure.tsv",
            "data/reference/nb04_nto_queries.tsv",
            "data/reference/nb04_nto_queries.fasta",
            "results/bioinformatics/nb04/cp0/resource_landscape.tsv",
            "data/reference/nb04_cp0_complementary_contract.json",
            "src/workstreams/bioinformatics/runs/2026-10-14_nb04-cp0-complementary-contract-patch.md",
        ],
    }
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


@pytest.fixture
def repro_schema():
    path = Path(__file__).parents[1] / "config" / "repro.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def schema_config():
    return {
        "schema_version": 1,
        "platform": {"allowed_systems": ["Linux"]},
        "python": {"spec": ">=3.12,<3.13"},
        "python_dependencies": [{"distribution": "demo", "module": "demo"}],
        "external_tools": [],
        "required_paths": ["base.txt"],
        "supporting_configs": [],
        "snapshot_dir": "snapshots",
    }


def test_schema_preserves_v1_and_rejects_checkpoint_extension(repro_schema, schema_config):
    jsonschema.Draft7Validator.check_schema(repro_schema)
    jsonschema.validate(schema_config, repro_schema)
    schema_config["checkpoint_required_paths"] = {}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(schema_config, repro_schema)


@pytest.mark.parametrize("profiles", [None, {}, {"nb04_cp0": []}, {"nb04_cp1": ["extra.txt"]}])
def test_schema_v2_accepts_optional_valid_profiles(repro_schema, schema_config, profiles):
    schema_config["schema_version"] = 2
    if profiles is not None:
        schema_config["checkpoint_required_paths"] = profiles
    jsonschema.validate(schema_config, repro_schema)


@pytest.mark.parametrize(
    "profiles",
    [None, [], "profile", {"": []}, {"cp": None}, {"cp": "extra.txt"},
     {"cp": {}}, {"cp": [1]}, {"cp": [""]}],
)
def test_schema_v2_rejects_malformed_profiles(repro_schema, schema_config, profiles):
    schema_config.update(schema_version=2, checkpoint_required_paths=profiles)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(schema_config, repro_schema)


@pytest.mark.parametrize("version", [0, 3, "2", True])
def test_schema_rejects_unsupported_versions(repro_schema, schema_config, version):
    schema_config["schema_version"] = version
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(schema_config, repro_schema)


def test_load_v2_configuration_with_actual_schema(tmp_path, monkeypatch, repro_schema, schema_config):
    import yaml

    (tmp_path / "config").mkdir()
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    schema_config.update(schema_version=2, checkpoint_required_paths={"nb04_cp0": []})
    (tmp_path / "config" / "repro.yaml").write_text(yaml.safe_dump(schema_config), encoding="utf-8")
    (tmp_path / "config" / "repro.schema.json").write_text(json.dumps(repro_schema), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = repro.load_repro_config()
    assert cfg.schema_version == 2
    assert cfg.raw["checkpoint_required_paths"] == {"nb04_cp0": []}


def test_checkpoint_none_preserves_legacy_order_multiplicity_and_details(tmp_path):
    (tmp_path / "present").write_text("ok", encoding="utf-8")
    cfg = make_config(
        tmp_path,
        required_paths=["present", "missing", "present"],
    )
    expected = [
        repro.CheckResult("path:present", "PASS", "readable"),
        repro.CheckResult("path:missing", "FAIL", "missing or unreadable"),
        repro.CheckResult("path:present", "PASS", "readable"),
    ]
    assert repro.check_required_paths(cfg) == expected
    assert repro.check_required_paths(cfg, checkpoint=None) == expected
    cfg.raw.update(schema_version=2, checkpoint_required_paths={"nb04_cp1": ["extra"]})
    assert repro.check_required_paths(cfg, checkpoint=None) == expected


def test_checkpoint_profiles_are_additive_and_isolated(tmp_path):
    (tmp_path / "base.txt").write_text("base", encoding="utf-8")
    cfg = make_config(
        tmp_path, schema_version=2, required_paths=["base.txt"],
        checkpoint_required_paths={"nb04_cp0": [], "nb04_cp1": ["cp1_only.txt"]},
    )
    assert repro.check_required_paths(cfg, "nb04_cp0") == [
        repro.CheckResult("path:base.txt", "PASS", "readable"),
    ]
    cp1 = repro.check_required_paths(cfg, "nb04_cp1")
    assert [item.name for item in cp1] == ["path:base.txt", "path:cp1_only.txt"]
    assert [item.status for item in cp1] == ["PASS", "FAIL"]
    (tmp_path / "cp1_only.txt").write_text("extra", encoding="utf-8")
    (tmp_path / "base.txt").unlink()
    assert [item.status for item in repro.check_required_paths(cfg, "nb04_cp1")] == ["FAIL", "PASS"]
    assert repro.check_required_paths(cfg, "nb04_cp0")[0].status == "FAIL"


@pytest.mark.parametrize("version", [1, 2])
def test_explicit_checkpoint_without_configured_profiles_fails(tmp_path, version):
    cfg = make_config(tmp_path, schema_version=version)
    assert repro.check_required_paths(cfg, None) == []
    with pytest.raises(repro.ReproGateError, match="unknown or unconfigured checkpoint"):
        repro.check_required_paths(cfg, "nb04_cp0")


@pytest.mark.parametrize("checkpoint", ["missing", "", 1, []])
def test_unknown_or_invalid_checkpoint_fails_explicitly(tmp_path, checkpoint):
    cfg = make_config(tmp_path, schema_version=2, checkpoint_required_paths={"nb04_cp0": []})
    with pytest.raises(repro.ReproGateError, match="unknown or unconfigured checkpoint"):
        repro.check_required_paths(cfg, checkpoint)


def test_explicit_profile_deduplicates_literals_and_ignores_list_order(tmp_path):
    for name in ("a", "b", "c"):
        (tmp_path / name).write_text("ok", encoding="utf-8")
    cfg = make_config(tmp_path, schema_version=2)
    expected = [repro.CheckResult(f"path:{name}", "PASS", "readable") for name in ("a", "b", "c")]
    for base in permutations(("b", "a", "b")):
        for extras in permutations(("c", "a", "c")):
            cfg.raw["required_paths"] = list(base)
            cfg.raw["checkpoint_required_paths"] = {"nb04_cp0": list(extras)}
            assert repro.check_required_paths(cfg, "nb04_cp0") == expected


def test_explicit_profile_does_not_normalize_path_spellings(tmp_path):
    cfg = make_config(
        tmp_path, schema_version=2, required_paths=["A", "./A"],
        checkpoint_required_paths={"nb04_cp0": ["a", "A"]},
    )
    assert [item.name for item in repro.check_required_paths(cfg, "nb04_cp0")] == [
        "path:./A", "path:A", "path:a",
    ]


def test_checkpoint_path_reports_unreadable_file(tmp_path, monkeypatch):
    (tmp_path / "extra.txt").write_text("ok", encoding="utf-8")
    cfg = make_config(
        tmp_path, schema_version=2, checkpoint_required_paths={"nb04_cp1": ["extra.txt"]},
    )
    monkeypatch.setattr(repro.os, "access", lambda path, mode: False)
    assert repro.check_required_paths(cfg, "nb04_cp1") == [
        repro.CheckResult("path:extra.txt", "FAIL", "missing or unreadable"),
    ]


@pytest.fixture
def mocked_runtime(tmp_path, monkeypatch):
    cfg = make_config(tmp_path, required_paths=["base.txt"])
    (tmp_path / "base.txt").write_text("base", encoding="utf-8")
    ctx = context()
    monkeypatch.setattr(repro, "load_repro_config", lambda *args: cfg)
    monkeypatch.setattr(repro, "collect_run_context", lambda root: ctx)
    monkeypatch.setattr(repro, "check_platform", lambda cfg: [])
    monkeypatch.setattr(repro, "check_python", lambda cfg: [])
    monkeypatch.setattr(repro, "check_python_dependencies", lambda cfg: ([], {}))
    monkeypatch.setattr(repro, "check_external_tools", lambda cfg: ([], {}))
    monkeypatch.setattr(repro, "collect_config_hashes", lambda cfg: {"config/repro.yaml": "a" * 64})
    return cfg, ctx


def test_run_all_checks_none_keeps_legacy_path_call(mocked_runtime, monkeypatch):
    cfg, ctx = mocked_runtime
    paths = [repro.CheckResult("path:legacy", "PASS", "readable")]
    monkeypatch.setattr(repro, "check_required_paths", lambda config: paths)
    implicit = repro.run_all_checks()
    explicit = repro.run_all_checks(checkpoint=None)
    assert implicit == explicit
    assert implicit[1].results == [*repro.check_git_state(ctx, False), *paths]


def test_run_all_checks_forwards_checkpoint_without_changing_fingerprint(mocked_runtime):
    cfg, _ = mocked_runtime
    cfg.raw.update(
        schema_version=2,
        checkpoint_required_paths={"nb04_cp0": [], "nb04_cp1": ["cp1_only.txt"]},
    )
    _, cp0, baseline = repro.run_all_checks(checkpoint="nb04_cp0")
    _, cp1, extended = repro.run_all_checks(checkpoint="nb04_cp1")
    assert cp0.failures() == []
    assert [item.name for item in cp1.failures()] == ["path:cp1_only.txt"]
    assert baseline == extended
    with pytest.raises(repro.ReproGateError, match="unknown or unconfigured checkpoint"):
        repro.run_all_checks(checkpoint="unknown")


@pytest.mark.parametrize("checkpoint", [None, "nb04_cp0"])
@pytest.mark.parametrize("allow_dirty", [False, True])
def test_run_all_checks_preserves_allow_dirty(mocked_runtime, checkpoint, allow_dirty):
    cfg, ctx = mocked_runtime
    cfg.raw.update(schema_version=2, checkpoint_required_paths={"nb04_cp0": []})
    ctx["git"]["dirty"] = True
    _, report, _ = repro.run_all_checks(allow_dirty=allow_dirty, checkpoint=checkpoint)
    git_check = next(item for item in report.results if item.name == "git")
    assert git_check == repro.check_git_state(ctx, allow_dirty)[0]
    assert git_check.status == ("PASS" if allow_dirty else "FAIL")


def test_assert_environment_ready_checks_profile_paths_before_snapshot(mocked_runtime):
    cfg, _ = mocked_runtime
    cfg.raw.update(schema_version=2, checkpoint_required_paths={"nb04_cp1": ["missing_extra"]})
    with pytest.raises(repro.ReproGateError, match="path:missing_extra: missing or unreadable"):
        repro.assert_environment_ready(checkpoint="nb04_cp1")
    with pytest.raises(repro.ReproGateError, match="unknown or unconfigured checkpoint"):
        repro.assert_environment_ready(checkpoint="unknown")


@pytest.mark.parametrize("checkpoint", [None, "nb04_cp0"])
def test_assert_environment_ready_rejects_dirty_state_before_snapshot(mocked_runtime, checkpoint):
    cfg, ctx = mocked_runtime
    cfg.raw.update(schema_version=2, checkpoint_required_paths={"nb04_cp0": []})
    ctx["git"]["dirty"] = True
    with pytest.raises(repro.ReproGateError, match="git: working tree is dirty"):
        repro.assert_environment_ready(checkpoint=checkpoint)


@pytest.mark.parametrize("allow_dirty", [False, True])
@pytest.mark.parametrize("checkpoint", [None, "nb04_cp0"])
def test_assert_environment_ready_forwards_arguments(monkeypatch, allow_dirty, checkpoint):
    calls = []

    def checks(**kwargs):
        calls.append(kwargs)
        report = repro.ReproReport([repro.CheckResult("synthetic", "FAIL", "stop after forwarding")])
        return None, report, {}

    monkeypatch.setattr(repro, "run_all_checks", checks)
    with pytest.raises(repro.ReproGateError, match="stop after forwarding"):
        repro.assert_environment_ready(allow_dirty=allow_dirty, checkpoint=checkpoint)
    expected = {"allow_dirty": allow_dirty}
    if checkpoint is not None:
        expected["checkpoint"] = checkpoint
    assert calls == [expected]


@pytest.mark.parametrize("checkpoint", [None, "nb04_cp0"])
@pytest.mark.parametrize("mismatch", [None, "Git commit", "configuration hashes", "runtime fingerprint"])
def test_allow_dirty_keeps_snapshot_comparisons(mocked_runtime, monkeypatch, checkpoint, mismatch):
    cfg, ctx = mocked_runtime
    cfg.raw.update(schema_version=2, checkpoint_required_paths={"nb04_cp0": []})
    ctx["git"]["dirty"] = True
    _, report, collected = repro.run_all_checks(allow_dirty=True, checkpoint=checkpoint)
    snapshot = repro.build_snapshot(context(), cfg, report, collected)
    if mismatch == "Git commit":
        snapshot["git"]["commit"] = "d" * 40
    elif mismatch == "configuration hashes":
        snapshot["config_hashes"] = {"config/repro.yaml": "d" * 64}
    elif mismatch == "runtime fingerprint":
        snapshot["runtime_fingerprint"] = {"sha256": "d" * 64}

    snapshot_dir = cfg.root / cfg.snapshot_dir
    latest_path = snapshot_dir / "latest.json"
    snapshot_path = (snapshot_dir / "synthetic" / "snapshot.json").resolve()
    latest = {"snapshot_file": "synthetic/snapshot.json", "snapshot_sha256": "c" * 64}
    original_is_file = Path.is_file
    original_read_text = Path.read_text

    def is_file(path):
        return True if path == latest_path else original_is_file(path)

    def read_text(path, *args, **kwargs):
        if path == latest_path:
            return json.dumps(latest)
        if path == snapshot_path:
            return json.dumps(snapshot)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(repro, "_sha256_file", lambda path: "c" * 64)
    if mismatch is None:
        repro.assert_environment_ready(allow_dirty=True, checkpoint=checkpoint)
    else:
        with pytest.raises(repro.ReproGateError, match=mismatch):
            repro.assert_environment_ready(allow_dirty=True, checkpoint=checkpoint)
