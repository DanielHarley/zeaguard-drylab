"""Unit tests for NB04 CP1 E01 preservation control and execution scope.

Uses tiny, non-informative synthetic fixtures and simulated tool probes.
Never invokes real BLAST searches, index builds, or calibration runs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

from zeaguard import nb04_calibration as cal
from zeaguard import nb04_resources as r


def _sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_lf(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _put(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _init_git_repo(root: Path) -> str:
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "core.autocrlf", "false"], check=True, capture_output=True)
    _put(root / ".gitignore", b"data/external/\nartifacts/\n# Agent context\n.agents\n")
    _put(root / "tracked.txt", b"initial\n")
    for rel in cal.HISTORICAL_CP1_PROTECTED_CODE_PATHS:
        _put(root / rel, f"# {rel}\n".encode("utf-8"))
    subprocess.run(["git", "-C", str(root), "add", ".gitignore", "tracked.txt", *cal.HISTORICAL_CP1_PROTECTED_CODE_PATHS], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


@pytest.fixture
def synthetic_e01_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a minimal synthetic workspace with all E01 categories and 2 normative docs."""
    root = tmp_path / "workspace"
    corpora_root = tmp_path / "external_corpora"
    head = _init_git_repo(root)

    # Set up .gitignore with plan_section_2 bytes and E01 baseline bytes (adding 'docs\n')
    plan_gitignore = b"data/external/\nartifacts/\n# Agent context\n.agents\n.claude\n.maestri\n.planning\n"
    e01_gitignore = b"data/external/\nartifacts/\n# Agent context\n.agents\n.claude\n.maestri\n.planning\ndocs\n"
    plan_gitignore_sha = hashlib.sha256(plan_gitignore).hexdigest()
    e01_gitignore_sha = hashlib.sha256(e01_gitignore).hexdigest()
    _put(root / ".gitignore", e01_gitignore)

    monkeypatch.setattr(cal, "PLAN_SECTION_2_GITIGNORE_RAW_SHA256", plan_gitignore_sha)
    monkeypatch.setattr(cal, "E01_BASELINE_GITIGNORE_RAW_SHA256", e01_gitignore_sha)

    # Synthetic normative corpus (1 in-repo + 1 external local corpus)
    b6_bytes = b"B6 A1 normative content\n"
    b6_path = _put(root / cal.IN_REPO_B6_A1_RELATIVE_PATH, b6_bytes)
    ext_doc_bytes = b"01 PLAN normative content\n"
    ext_corpus_dir = corpora_root / "NB04_B5_INPUTS"
    _put(ext_corpus_dir / "01_PLAN_v2.2.5.md", ext_doc_bytes)

    synth_norm_spec = {
        "01_PLAN_v2.2.5.md": {
            "expected_sha256": _sha256_raw(ext_doc_bytes),
            "hash_mode": "RAW",
            "location_class": "EXTERNAL_LOCAL_CORPUS",
            "corpus_id": "NB04_B5_INPUTS",
            "repository_relative_path": None,
        },
        "B6_GOVERNANCE_AMENDMENT_A1.md": {
            "expected_sha256": _sha256_raw(b6_bytes),
            "hash_mode": "RAW",
            "location_class": "IN_REPOSITORY",
            "corpus_id": "REPOSITORY_DECISIONS",
            "repository_relative_path": cal.IN_REPO_B6_A1_RELATIVE_PATH,
        },
    }
    monkeypatch.setattr(cal, "NORMATIVE_DOCUMENTS_SPEC", synth_norm_spec)

    # Snapshots
    g0_snap_rel = "artifacts/reproducibility/20261015T072304603205Z_e37481d6d154/snapshot.json"
    g0_snap_bytes = r.json_bytes({"schema_version": 1, "git": {"branch": "feat/nb04-cp0", "commit": head, "dirty": False}})
    g0_snap_path = _put(root / g0_snap_rel, g0_snap_bytes)
    cp1_snap_rel = cal.EXPECTED_CP1_SNAPSHOT_PATH
    cp1_snap_bytes = r.json_bytes({"schema_version": 1, "git": {"branch": "feat/nb04-cp1", "commit": head, "dirty": False}})
    cp1_snap_path = _put(root / cp1_snap_rel, cp1_snap_bytes)
    latest_bytes = r.json_bytes({
        "snapshot_file": "20261015T082821773339Z_e37481d6d154/snapshot.json",
        "snapshot_sha256": _sha256_raw(cp1_snap_bytes),
    })
    latest_path = _put(root / cal.EXPECTED_LATEST_POINTER_PATH, latest_bytes)
    monkeypatch.setattr(cal, "EXPECTED_LATEST_POINTER_SHA256", _sha256_raw(latest_bytes))
    monkeypatch.setattr(cal, "EXPECTED_CP1_SNAPSHOT_SHA256", _sha256_raw(cp1_snap_bytes))

    # G0 certified artifacts (one LF_NORMALIZED with CRLF on disk, one RAW)
    lf_art_bytes = b"col1\tcol2\r\n1\t2\r\n"
    raw_art_bytes = b">Q1\nACGT\n"
    _put(root / "config/frozen.tsv", lf_art_bytes)
    _put(root / "data/reference/queries.fasta", raw_art_bytes)
    cert = {
        "certification_id": "SYNTH_G0_V1",
        "gate": "G0",
        "status": "G0_PASS",
        "certified_artifacts": {
            "config/frozen.tsv": {
                "hash_mode": "LF_NORMALIZED",
                "sha256": _sha256_lf(lf_art_bytes),
            },
            "data/reference/queries.fasta": {
                "hash_mode": "RAW",
                "sha256": _sha256_raw(raw_art_bytes),
            },
        },
        "normative_documents": {
            name: spec["expected_sha256"] for name, spec in synth_norm_spec.items()
        },
        "environment_snapshot": {
            "path": g0_snap_rel,
            "sha256": _sha256_raw(g0_snap_bytes),
        },
    }
    r.write_json(root / r.G0_PATH, cert)
    g0_sha = _sha256_raw((root / r.G0_PATH).read_bytes())
    monkeypatch.setattr(cal, "EXPECTED_G0_CERTIFICATE_SHA256", g0_sha)

    # Commit G0 and tracked files so only .gitignore is dirty in git
    subprocess.run(
        ["git", "-C", str(root), "add", cal.IN_REPO_B6_A1_RELATIVE_PATH, "config/frozen.tsv", "data/reference/queries.fasta", r.G0_PATH],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(root), "commit", "-m", "add g0"], check=True, capture_output=True)

    # Synthetic CP1 resource + blastdb
    res_dir = root / "data/external/nto/cp1_synth/R1_RNA"
    fasta_bytes = b">R1_RNA__00000001\nACGTACGTACGTACGT\n"
    idmap_bytes = (
        b"analysis_id\tsource_id\tsource_header\tlength_nt\tsequence_sha256\n"
        b"R1_RNA__00000001\tSRC1.1\tSRC1.1 synthetic\t16\t00\n"
    )
    nsq_bytes = b"NSQ_INDEX_BYTES"
    nin_bytes = b"NIN_INDEX"
    fasta_path = _put(res_dir / "normalized.fasta", fasta_bytes)
    idmap_path = _put(res_dir / "identifier_map.tsv", idmap_bytes)
    nsq_path = _put(res_dir / "blastdb/sequences.nsq", nsq_bytes)
    nin_path = _put(res_dir / "blastdb/sequences.nin", nin_bytes)
    tool_str = "makeblastdb: 2.17.0+\n Package: blast 2.17.0, build Aug 22 2026 11:52:50"
    db_build_path = res_dir / "database_build.json"
    r.write_json(
        db_build_path,
        {
            "tool": tool_str,
            "index_sha256": {
                "sequences.nin": _sha256_raw(nin_bytes),
                "sequences.nsq": _sha256_raw(nsq_bytes),
            },
            "searches_executed": False,
        },
    )
    fasta_rel = fasta_path.relative_to(root).as_posix()
    idmap_rel = idmap_path.relative_to(root).as_posix()
    nsq_rel = nsq_path.relative_to(root).as_posix()
    nin_rel = nin_path.relative_to(root).as_posix()
    db_build_rel = db_build_path.relative_to(root).as_posix()

    inventory_path = root / r.INVENTORY
    r.write_json(inventory_path, {"schema_version": 1, "g0_certificate_sha256": g0_sha})
    inv_sha = _sha256_raw(inventory_path.read_bytes())

    manifest_data = {
        "schema_version": 1,
        "g0_certificate_sha256": g0_sha,
        "inventory_sha256": inv_sha,
        "resources": [
            {
                "resource_id": "R1_RNA",
                "organism_id": "ZEA_MAYS",
                "scientific_name": "Zea mays",
                "taxid": 4577,
                "fasta_path": fasta_rel,
                "identifier_map_path": idmap_rel,
                "quality": {
                    "record_count": 1,
                    "total_bases": 16,
                    "fasta_sha256": _sha256_raw(fasta_bytes),
                    "identifier_map_sha256": _sha256_raw(idmap_bytes),
                },
                "artifacts_sha256": {
                    fasta_rel: _sha256_raw(fasta_bytes),
                    idmap_rel: _sha256_raw(idmap_bytes),
                    nsq_rel: _sha256_raw(nsq_bytes),
                    nin_rel: _sha256_raw(nin_bytes),
                    db_build_rel: _sha256_raw(db_build_path.read_bytes()),
                },
            }
        ],
    }
    r.write_json(root / r.MANIFEST, manifest_data)
    _put(root / r.REGISTRY, b"resource_id\nR1_RNA\n")
    _put(root / r.ASSESSABILITY, b"organism_id\nZEA_MAYS\n")

    ref_shas = {
        rel: _sha256_raw((root / rel).read_bytes())
        for rel in (r.MANIFEST, r.INVENTORY, r.REGISTRY, r.ASSESSABILITY)
    }
    monkeypatch.setattr(cal, "EXPECTED_CP1_REFERENCE_SHA256", ref_shas)

    run_manifest_data = {
        "stage": "NB04_CP1",
        "outputs_sha256": dict(ref_shas),
        "implementation_sha256_lf": {
            rel: _sha256_lf((root / rel).read_bytes())
            for rel in cal.HISTORICAL_CP1_PROTECTED_CODE_PATHS
        },
    }
    r.write_json(root / cal.EXPECTED_CP1_RUN_MANIFEST_PATH, run_manifest_data)
    monkeypatch.setattr(
        cal,
        "EXPECTED_CP1_RUN_MANIFEST_SHA256",
        _sha256_raw((root / cal.EXPECTED_CP1_RUN_MANIFEST_PATH).read_bytes()),
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "add",
            r.INVENTORY,
            r.MANIFEST,
            r.REGISTRY,
            r.ASSESSABILITY,
            cal.EXPECTED_CP1_RUN_MANIFEST_PATH,
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(root), "commit", "-m", "add cp1"], check=True, capture_output=True)

    # Simulated BLAST tool binaries
    bin_dir = tmp_path / "fake_bin"
    for tool in cal.BLAST_TOOLS:
        _put(bin_dir / tool, f"ELF_BINARY_{tool}".encode("ascii"))

    def fake_which(name: str) -> str | None:
        candidate = bin_dir / name
        return str(candidate) if candidate.is_file() else None

    def fake_runner(cmd, **kwargs):
        exe_name = Path(cmd[0]).name
        out = f"{exe_name}: 2.17.0+\n Package: blast 2.17.0, build Aug 22 2026 11:52:50\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    orig_verify_g0 = cal.verify_g0_certified_artifacts_inventory
    orig_verify_cp1 = cal.verify_cp1_resources_and_manifests

    def _wrapped_verify_g0(rt, **kw):
        kw.setdefault("expected_artifact_count", 2)
        return orig_verify_g0(rt, **kw)

    def _wrapped_verify_cp1(rt, **kw):
        kw.setdefault("expected_resource_count", 1)
        return orig_verify_cp1(rt, **kw)

    monkeypatch.setattr(cal, "verify_g0_certified_artifacts_inventory", _wrapped_verify_g0)
    monkeypatch.setattr(cal, "verify_cp1_resources_and_manifests", _wrapped_verify_cp1)

    return {
        "root": root,
        "corpus_dirs": {"NB04_B5_INPUTS": ext_corpus_dir},
        "bin_dir": bin_dir,
        "fake_which": fake_which,
        "fake_runner": fake_runner,
    }


def test_gitignore_demonstrated_reduction_and_unexplained_divergence(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    gi_path = root / ".gitignore"
    baseline_bytes = gi_path.read_bytes()

    state = cal.verify_gitignore_and_git_state(root)
    gi = state["gitignore_preservation"]
    assert gi["verdict"] == "PASS_EXPLAINED_BASELINE_FIXED"
    assert gi["matches_current_e01_baseline_raw_sha256"] is True
    assert gi["matches_plan_section_2_raw_sha256"] is False
    demo = gi["demonstrated_content_difference"]
    assert demo["docs_line_removed"] is True
    assert demo["reproduces_plan_section_2_expected_raw_sha256"] is True
    assert demo["reduced_bytes_raw_sha256"] != gi["observed_raw_sha256"]
    assert demo["diff_vs_head_added_lines"] == [".claude", ".maestri", ".planning", "docs"]
    assert demo["evidence_class"] == "DEMONSTRATED_BY_GIT_DIFF_AND_BYTE_REDUCTION"
    assert gi["reported_attribution"]["evidence_class"] == "REPORTED_CONTEXT_NOT_DEMONSTRATED_BY_GIT_DIFF"

    # U01_F03: Removing 'docs' line (reverting to historical plan_v003.md section 2 hash)
    # must fail closed in both verify_gitignore_and_git_state and verify_preparation_allowlist
    # and never fabricate a removal proof statement.
    gi_path.write_bytes(baseline_bytes.replace(b"\ndocs\n", b"\n", 1))
    with pytest.raises(r.ResourceContractError, match="observed historical plan_v003.md section 2 hash"):
        cal.verify_gitignore_and_git_state(root)
    with pytest.raises(r.ResourceContractError, match="diverges from preserved E01 baseline"):
        cal.verify_preparation_allowlist(root)

    # Unexplained modification to .gitignore must fail closed in both verifiers
    gi_path.write_bytes(b"# unexpected edit\n")
    with pytest.raises(r.ResourceContractError, match="unexplained .gitignore"):
        cal.verify_gitignore_and_git_state(root)
    with pytest.raises(r.ResourceContractError, match="diverges from preserved E01 baseline"):
        cal.verify_preparation_allowlist(root)

    gi_path.write_bytes(baseline_bytes)


def test_hash_divergence_and_missing_files_across_all_categories(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    corpus_dirs = synthetic_e01_env["corpus_dirs"]

    # 1. G0 certified artifact hash mismatch and missing file
    frozen = root / "config/frozen.tsv"
    orig_bytes = frozen.read_bytes()
    frozen.write_bytes(b"corrupted\n")
    with pytest.raises(r.ResourceContractError, match="G0 artifact changed"):
        cal.verify_g0_certified_artifacts_inventory(root)
    frozen.unlink()
    with pytest.raises(r.ResourceContractError, match="G0 artifact missing"):
        cal.verify_g0_certified_artifacts_inventory(root)
    frozen.write_bytes(orig_bytes)

    # 2. Normative document inaccessibility and hash mismatch
    cert = json.loads((root / r.G0_PATH).read_text("utf-8"))
    non_strict = cal.verify_normative_documents(root, cert, {}, strict=False)
    assert non_strict["verdict"] == "FAIL_INACCESSIBLE"
    assert non_strict["documents"]["01_PLAN_v2.2.5.md"]["status"] == "NORMATIVE_DOCUMENT_INACCESSIBLE"
    with pytest.raises(r.ResourceContractError, match="NORMATIVE_DOCUMENT_INACCESSIBLE"):
        cal.verify_normative_documents(root, cert, {}, strict=True)

    ext_file = corpus_dirs["NB04_B5_INPUTS"] / "01_PLAN_v2.2.5.md"
    orig_ext = ext_file.read_bytes()
    ext_file.write_bytes(b"tampered normative\n")
    with pytest.raises(r.ResourceContractError, match="normative document SHA256 mismatch"):
        cal.verify_normative_documents(root, cert, corpus_dirs, strict=True)
    ext_file.write_bytes(orig_ext)

    # 3. CP1 resource blastdb volume hash mismatch and missing file
    nsq = root / "data/external/nto/cp1_synth/R1_RNA/blastdb/sequences.nsq"
    orig_nsq = nsq.read_bytes()
    nsq.write_bytes(b"corrupted_nsq")
    with pytest.raises(r.ResourceContractError, match="resource artifact SHA256 mismatch"):
        cal.verify_cp1_resources_and_manifests(root)
    nsq.unlink()
    with pytest.raises(r.ResourceContractError, match="resource artifact missing"):
        cal.verify_cp1_resources_and_manifests(root)
    nsq.write_bytes(orig_nsq)

    # 4. Protected historical CP1 code modification rejected
    res_py = root / "src/zeaguard/nb04_resources.py"
    orig_res_py = res_py.read_bytes()
    res_py.write_bytes(b"# modified historical code\n")
    with pytest.raises(r.ResourceContractError, match="CP1 protected implementation LF hash changed"):
        cal.verify_cp1_resources_and_manifests(root)
    res_py.write_bytes(orig_res_py)

    # 5. Snapshot hash mismatch and missing file
    snap = root / cal.EXPECTED_CP1_SNAPSHOT_PATH
    orig_snap = snap.read_bytes()
    snap.write_bytes(b"{}")
    with pytest.raises(r.ResourceContractError, match="snapshot_sha256 does not match"):
        cal.verify_historical_snapshots(root, cert, working_tree_dirty=True)
    snap.unlink()
    with pytest.raises(r.ResourceContractError, match="latest snapshot missing"):
        cal.verify_historical_snapshots(root, cert, working_tree_dirty=True)
    snap.write_bytes(orig_snap)


def test_unknown_hash_mode_and_path_outside_root_rejected(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    cert_path = root / r.G0_PATH
    orig_cert_bytes = cert_path.read_bytes()

    # Unknown hash_mode in G0 certificate
    cert = json.loads(orig_cert_bytes.decode("utf-8"))
    cert["certified_artifacts"]["config/frozen.tsv"]["hash_mode"] = "MD5_ONLY"
    r.write_json(cert_path, cert)
    with pytest.raises(r.ResourceContractError, match="unknown hash mode"):
        cal.verify_g0_certified_artifacts_inventory(root, expected_certificate_sha256=None)

    # Path outside root in G0 certificate
    cert = json.loads(orig_cert_bytes.decode("utf-8"))
    cert["certified_artifacts"]["../escape.txt"] = {"hash_mode": "RAW", "sha256": "0" * 64}
    r.write_json(cert_path, cert)
    with pytest.raises(r.ResourceContractError, match="path outside project"):
        cal.verify_g0_certified_artifacts_inventory(root, expected_certificate_sha256=None, expected_artifact_count=None)
    cert_path.write_bytes(orig_cert_bytes)

    # Unknown hash_mode in normative corpus spec
    bad_spec = dict(cal.NORMATIVE_DOCUMENTS_SPEC)
    bad_spec["01_PLAN_v2.2.5.md"] = dict(bad_spec["01_PLAN_v2.2.5.md"], hash_mode="LF_ONLY")
    with pytest.raises(r.ResourceContractError, match="hash_mode must be RAW"):
        cal.normative_corpus_declaration(bad_spec)

    # Inventory destination outside root rejected
    with pytest.raises(r.ResourceContractError, match="outside project root"):
        cal.write_preservation_inventory(root, {"schema_version": 1}, output_path=root.parent / "outside.json")

    # U01_F01: Protected in-root destinations (certified artifact and historical inventory)
    # must be rejected before any write, keeping existing bytes identical.
    frozen_path = root / "config/frozen.tsv"
    frozen_before = frozen_path.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E01 output path"):
        cal.write_execution_scope_artifact(root, destination=frozen_path)
    assert frozen_path.read_bytes() == frozen_before

    with pytest.raises(r.ResourceContractError, match="outside authorized directory"):
        cal.write_preservation_inventory(root, {"schema_version": 1}, output_path=frozen_path)
    assert frozen_path.read_bytes() == frozen_before

    hist_inv = _put(
        root / "artifacts/validation/nb04_cp1_prefreeze/20261025T075045Z/preservation_inventory.json",
        b'{"historical_round":1}\n',
    )
    hist_before = hist_inv.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E01 output path"):
        cal.write_execution_scope_artifact(root, destination=hist_inv)
    assert hist_inv.read_bytes() == hist_before

    with pytest.raises(r.ResourceContractError, match="never be overwritten"):
        cal.write_preservation_inventory(root, {"schema_version": 1}, output_path=hist_inv)
    assert hist_inv.read_bytes() == hist_before


def test_allowlist_accepts_authorized_paths_and_rejects_unauthorized_dirty_files(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    # Allowed untracked file inside CLOSED_PREPARATION_DIRTY_ALLOWLIST
    allowed_file = _put(root / "src/zeaguard/nb04_calibration.py", b"# authorized unit\n")
    result = cal.verify_preparation_allowlist(root)
    assert result["verdict"] == "PASS"
    assert result["readiness_allow_dirty"] is True
    assert "src/zeaguard/nb04_calibration.py" in result["dirty_paths_observed"]

    # Unauthorized modified tracked file outside allowlist must fail
    tracked = root / "tracked.txt"
    tracked.write_bytes(b"unauthorized edit\n")
    with pytest.raises(r.ResourceContractError, match="outside closed preparation allowlist"):
        cal.verify_preparation_allowlist(root)
    tracked.write_bytes(b"initial\n")

    # Unauthorized untracked file outside allowlist must fail
    rogue = _put(root / "src/zeaguard/rogue_module.py", b"# unauthorized\n")
    with pytest.raises(r.ResourceContractError, match="outside closed preparation allowlist"):
        cal.verify_preparation_allowlist(root)
    rogue.unlink()
    allowed_file.unlink()

    # U01_F02: Renaming a tracked file outside allowlist to an allowed destination
    # must fail and explicitly identify the unauthorized source path ('tracked.txt').
    subprocess.run(
        ["git", "-C", str(root), "mv", "tracked.txt", "src/zeaguard/nb04_calibration.py"],
        check=True,
        capture_output=True,
    )
    with pytest.raises(r.ResourceContractError, match=r"tracked\.txt"):
        cal.verify_preparation_allowlist(root)
    subprocess.run(
        ["git", "-C", str(root), "mv", "src/zeaguard/nb04_calibration.py", "tracked.txt"],
        check=True,
        capture_output=True,
    )

    # U01_F02: Delimiter/quote/space handling in _parse_porcelain_paths (-z and v1 lines)
    parsed_z = cal._parse_porcelain_paths(
        "R  src/zeaguard/nb04_calibration.py\x00tracked with space.txt\x00 M .gitignore\x00"
    )
    assert [item["path"] for item in parsed_z] == [
        "tracked with space.txt",
        "src/zeaguard/nb04_calibration.py",
        ".gitignore",
    ]
    parsed_v1 = cal._parse_porcelain_paths(
        'R  "tracked with space.txt" -> "src/zeaguard/nb04_calibration.py"\n'
    )
    assert [item["path"] for item in parsed_v1] == [
        "tracked with space.txt",
        "src/zeaguard/nb04_calibration.py",
    ]

    # U01_F02: Rename where both source and destination are inside the allowlist succeeds
    custom_allowlist = (*cal.CLOSED_PREPARATION_DIRTY_ALLOWLIST, "tracked.txt")
    subprocess.run(
        ["git", "-C", str(root), "mv", "tracked.txt", "src/zeaguard/nb04_calibration.py"],
        check=True,
        capture_output=True,
    )
    allowed_rename = cal.verify_preparation_allowlist(root, allowlist=custom_allowlist)
    assert allowed_rename["verdict"] == "PASS"
    assert "tracked.txt" in allowed_rename["dirty_paths_observed"]
    assert "src/zeaguard/nb04_calibration.py" in allowed_rename["dirty_paths_observed"]
    subprocess.run(
        ["git", "-C", str(root), "mv", "src/zeaguard/nb04_calibration.py", "tracked.txt"],
        check=True,
        capture_output=True,
    )


def test_blast_tool_build_observation_missing_and_divergent_states(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    manifest = json.loads((root / r.MANIFEST).read_text("utf-8"))

    # 1. All tools present and matching historical receipts
    observed = cal.observe_blast_tool_builds(
        root,
        manifest,
        which_resolver=synthetic_e01_env["fake_which"],
        runner=synthetic_e01_env["fake_runner"],
    )
    assert observed["overall_status"] == "OBSERVED_MATCHES_HISTORICAL_RECEIPTS"
    assert observed["all_tools_observed"] is True
    assert observed["all_tools_match_historical_receipts"] is True
    assert observed["equivalent_build_reuse_blocked"] is False
    for tool in cal.BLAST_TOOLS:
        assert len(observed["observed_tools"][tool]["prospective_executable_sha256"]) == 64

    # 2. Missing tool recorded as BUILD_NOT_OBSERVED, never treated as passing
    missing_obs = cal.observe_blast_tool_builds(
        root,
        manifest,
        which_resolver=lambda name: None if name == "blastdbcmd" else synthetic_e01_env["fake_which"](name),
        runner=synthetic_e01_env["fake_runner"],
    )
    assert missing_obs["overall_status"] == "BUILD_NOT_OBSERVED"
    assert missing_obs["all_tools_observed"] is False
    assert missing_obs["equivalent_build_reuse_blocked"] is True
    assert missing_obs["observed_tools"]["blastdbcmd"]["status"] == "BUILD_NOT_OBSERVED"
    assert missing_obs["observed_tools"]["blastdbcmd"]["prospective_executable_sha256"] is None

    # 3. Divergent build version blocks equivalent reuse without crashing inventory
    def divergent_runner(cmd, **kwargs):
        exe_name = Path(cmd[0]).name
        out = f"{exe_name}: 2.16.0+\n Package: blast 2.16.0, build Jan 10 2025 00:00:00\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    div_obs = cal.observe_blast_tool_builds(
        root,
        manifest,
        which_resolver=synthetic_e01_env["fake_which"],
        runner=divergent_runner,
    )
    assert div_obs["overall_status"] == "BUILD_DIVERGENCE_DETECTED_REUSE_BLOCKED"
    assert div_obs["all_tools_observed"] is True
    assert div_obs["all_tools_match_historical_receipts"] is False
    assert div_obs["equivalent_build_reuse_blocked"] is True


def test_artifact_bytes_are_deterministic_and_inventory_never_overwrites(synthetic_e01_env):
    root = synthetic_e01_env["root"]
    corpus_dirs = synthetic_e01_env["corpus_dirs"]

    scope_obj = cal.build_execution_scope_artifact(root)
    scope_a = r.json_bytes(scope_obj)
    scope_b = r.json_bytes(cal.build_execution_scope_artifact(root))
    assert scope_a == scope_b
    assert b"external_corpora" not in scope_a

    # Independent semantic checks on execution scope payload
    assert scope_obj["artifact_id"] == "NB04_CALIBRATION_EXECUTION_SCOPE_V1"
    assert scope_obj["normative_corpus_declaration"]["total_documents"] == 2
    assert scope_obj["normative_corpus_declaration"]["personal_paths_omitted"] is True
    # 24 index bytes (15 + 9) / 35 FASTA bytes = 0.685714
    assert scope_obj["index_to_fasta_size_ratio"]["per_resource"]["R1_RNA"]["index_to_fasta_byte_ratio"] == 0.685714

    # Scope writer refuses to overwrite an existing file with divergent content
    scope_target = root / cal.EXECUTION_SCOPE_PATH
    divergent_bytes = b'{"divergent":true}\n'
    _put(scope_target, divergent_bytes)
    with pytest.raises(r.ResourceContractError, match="divergent content and must not be overwritten"):
        cal.write_execution_scope_artifact(root)
    assert scope_target.read_bytes() == divergent_bytes
    scope_target.unlink()

    written_scope, _ = cal.write_execution_scope_artifact(root)
    assert written_scope == scope_target
    assert scope_target.read_bytes() == scope_a

    inv_a = r.json_bytes(
        cal.build_preservation_inventory(
            root,
            corpus_dirs,
            executed_utc="2026-10-25T07:00:00Z",
            which_resolver=synthetic_e01_env["fake_which"],
            runner=synthetic_e01_env["fake_runner"],
        )
    )
    inv_b = r.json_bytes(
        cal.build_preservation_inventory(
            root,
            corpus_dirs,
            executed_utc="2026-10-25T07:00:00Z",
            which_resolver=synthetic_e01_env["fake_which"],
            runner=synthetic_e01_env["fake_runner"],
        )
    )
    assert inv_a == inv_b
    assert b"external_corpora" not in inv_a

    inv_dest = root / "artifacts/validation/nb04_cp1_prefreeze/20261025T070000Z/preservation_inventory.json"
    written = cal.write_preservation_inventory(root, json.loads(inv_a.decode("utf-8")), output_path=inv_dest)
    assert written == inv_dest
    with pytest.raises(r.ResourceContractError, match="never be overwritten"):
        cal.write_preservation_inventory(root, json.loads(inv_a.decode("utf-8")), output_path=inv_dest)


def test_prepare_nb04_calibration_cli_e01(synthetic_e01_env, monkeypatch, capsys):
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "prepare_nb04_calibration.py"
    spec = importlib.util.spec_from_file_location("prepare_nb04_calibration", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    root = synthetic_e01_env["root"]
    ext_dir = synthetic_e01_env["corpus_dirs"]["NB04_B5_INPUTS"]

    with pytest.raises(r.ResourceContractError, match="CORPUS_ID=PATH"):
        module.parse_corpus_mappings(["INVALID_ENTRY"])
    with pytest.raises(r.ResourceContractError, match="duplicate corpus_id"):
        module.parse_corpus_mappings(["A=/x", "A=/y"])

    orig_build = cal.build_preservation_inventory
    monkeypatch.setattr(
        cal,
        "build_preservation_inventory",
        lambda rt, cd, **kw: orig_build(
            rt,
            cd,
            which_resolver=synthetic_e01_env["fake_which"],
            runner=synthetic_e01_env["fake_runner"],
            **kw,
        ),
    )

    # U01_F01: Passing a certified artifact or historical inventory as scope_output
    # must fail before any write and leave the target bytes intact.
    frozen_victim = root / "config/frozen.tsv"
    frozen_before = frozen_victim.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E01 output path"):
        module.run_e01(root, synthetic_e01_env["corpus_dirs"], scope_output=frozen_victim)
    assert frozen_victim.read_bytes() == frozen_before

    hist_inv = _put(
        root / "artifacts/validation/nb04_cp1_prefreeze/20261025T075045Z/preservation_inventory.json",
        b'{"historical_round":1}\n',
    )
    hist_before = hist_inv.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E01 output path"):
        module.run_e01(root, synthetic_e01_env["corpus_dirs"], scope_output=hist_inv)
    assert hist_inv.read_bytes() == hist_before

    # U01_F01: Failure in inventory destination or downstream verification must not leave
    # a newly written execution scope file on disk.
    scope_default = root / cal.EXECUTION_SCOPE_PATH
    assert not scope_default.exists()
    with pytest.raises(r.ResourceContractError, match="never be overwritten"):
        module.run_e01(root, synthetic_e01_env["corpus_dirs"], inventory_output=hist_inv)
    assert not scope_default.exists()
    assert hist_inv.read_bytes() == hist_before

    with pytest.raises(r.ResourceContractError, match="NORMATIVE_DOCUMENT_INACCESSIBLE"):
        module.run_e01(root, {})
    assert not scope_default.exists()

    rc = module.main(
        [
            "e01",
            "--root",
            str(root),
            "--corpus",
            f"NB04_B5_INPUTS={ext_dir}",
            "--executed-utc",
            "2026-10-25T07:05:00Z",
        ]
    )
    assert rc == 0
    stdout_json = json.loads(capsys.readouterr().out)
    assert stdout_json["stage"] == "NB04_CP1_E01"
    assert stdout_json["searches_executed"] is False
    assert stdout_json["blast_tool_builds_status"] == "OBSERVED_MATCHES_HISTORICAL_RECEIPTS"
    assert (root / stdout_json["execution_scope_path"]).is_file()
    assert (root / stdout_json["preservation_inventory_path"]).is_file()


def test_reviewer_round_001_adversarial_counterexamples(synthetic_e01_env):
    """Directly exercise the three adversarial counterexamples from review.md Round 001."""
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "prepare_nb04_calibration.py"
    spec = importlib.util.spec_from_file_location("prepare_nb04_calibration", script_path)
    cli = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cli)

    root = synthetic_e01_env["root"]

    # Counterexample 1 (U01_F01): scope_output targeting a certified artifact inside root
    victim = root / "config/frozen.tsv"
    before = victim.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E01 output path"):
        cli.run_e01(root, synthetic_e01_env["corpus_dirs"], scope_output=victim)
    assert victim.read_bytes() == before

    # Counterexample 2 (U01_F02): git mv from forbidden source ('tracked.txt') to allowed destination
    subprocess.run(
        ["git", "-C", str(root), "mv", "tracked.txt", "src/zeaguard/nb04_calibration.py"],
        check=True,
        capture_output=True,
    )
    assert not (root / "tracked.txt").exists()
    with pytest.raises(r.ResourceContractError, match=r"tracked\.txt"):
        cal.verify_preparation_allowlist(root)
    subprocess.run(
        ["git", "-C", str(root), "mv", "src/zeaguard/nb04_calibration.py", "tracked.txt"],
        check=True,
        capture_output=True,
    )

    # Counterexample 3 (U01_F03): removing 'docs' line from .gitignore (reversion to historical plan hash)
    gi = root / ".gitignore"
    orig_gi = gi.read_bytes()
    gi.write_bytes(orig_gi.replace(b"\ndocs\n", b"\n", 1))
    assert b"docs\n" not in gi.read_bytes()
    with pytest.raises(r.ResourceContractError, match="observed historical plan_v003.md section 2 hash"):
        cal.verify_gitignore_and_git_state(root)
    with pytest.raises(r.ResourceContractError, match="diverges from preserved E01 baseline"):
        cal.verify_preparation_allowlist(root)
    gi.write_bytes(orig_gi)


# ======================================================================
# U02 / E03: Read-only geometry derivation unit tests
# ======================================================================


def _build_synthetic_resource(
    root: Path,
    resource_id: str,
    records: list[tuple[str, str, str]],
    *,
    campaign_id: str = "cp1_20261015",
    g0_sha: str = "0" * 64,
) -> dict:
    """Create a tiny synthetic resource directory (normalized.fasta + identifier_map.tsv + blastdb) using independent hashes."""
    res_dir = f"data/external/nto/{campaign_id}/{resource_id}"
    fasta_rel = f"{res_dir}/normalized.fasta"
    idmap_rel = f"{res_dir}/identifier_map.tsv"
    nsq_rel = f"{res_dir}/blastdb/sequences.nsq"
    nin_rel = f"{res_dir}/blastdb/sequences.nin"
    db_build_rel = f"{res_dir}/database_build.json"

    fasta_lines: list[str] = []
    idmap_lines: list[str] = ["analysis_id\tsource_id\tsource_header\tlength_nt\tsequence_sha256\n"]
    total_bases = 0
    total_ambig = 0
    lengths: list[int] = []

    for idx, (source_id, source_header, seq) in enumerate(records, start=1):
        analysis_id = f"{resource_id}__{idx:08d}"
        fasta_lines.append(f">{analysis_id}\n")
        for start in range(0, len(seq), 80):
            fasta_lines.append(seq[start : start + 80] + "\n")
        seq_sha = hashlib.sha256(seq.encode("ascii")).hexdigest()
        idmap_lines.append(f"{analysis_id}\t{source_id}\t{source_header}\t{len(seq)}\t{seq_sha}\n")
        lengths.append(len(seq))
        total_bases += len(seq)
        total_ambig += sum(ch not in "ACGT" for ch in seq)

    fasta_bytes = "".join(fasta_lines).encode("ascii")
    idmap_bytes = "".join(idmap_lines).encode("utf-8")
    nsq_bytes = f"NSQ_INDEX_BYTES_{resource_id}".encode("ascii")
    nin_bytes = f"NIN_INDEX_{resource_id}".encode("ascii")
    _put(root / fasta_rel, fasta_bytes)
    _put(root / idmap_rel, idmap_bytes)
    _put(root / nsq_rel, nsq_bytes)
    _put(root / nin_rel, nin_bytes)

    tool_str = "makeblastdb: 2.17.0+\n Package: blast 2.17.0, build Aug 22 2026 11:52:50"
    db_build_path = root / db_build_rel
    r.write_json(
        db_build_path,
        {
            "tool": tool_str,
            "index_sha256": {
                "sequences.nin": _sha256_raw(nin_bytes),
                "sequences.nsq": _sha256_raw(nsq_bytes),
            },
            "searches_executed": False,
        },
    )

    fasta_sha = _sha256_raw(fasta_bytes)
    idmap_sha = _sha256_raw(idmap_bytes)
    sorted_lengths = sorted(lengths)
    return {
        "resource_id": resource_id,
        "organism_id": "APIS_MELLIFERA",
        "scientific_name": "Apis mellifera",
        "taxid": 7460,
        "accession_version": "GCF_003254395.2",
        "release": "Release 104",
        "release_date": "2018-09-13",
        "resource_tier": "TRANSCRIPT_TIER",
        "resource_record_type": "OTHER",
        "annotation_status": "ANNOTATED",
        "adequate_annotated_transcript_set": True,
        "fasta_path": fasta_rel,
        "identifier_map_path": idmap_rel,
        "database_prefix": f"{res_dir}/blastdb/sequences",
        "source_url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/003/254/395/test.fna.gz",
        "acquired_utc": "2026-10-15T08:05:36+00:00",
        "selection_sha256": "1" * 64,
        "g0_certificate_sha256": g0_sha,
        "quality": {
            "record_count": len(records),
            "total_bases": total_bases,
            "ambiguous_bases": total_ambig,
            "lowercase_bases_in_source": 0,
            "minimum_length": sorted_lengths[0],
            "maximum_length": sorted_lengths[-1],
            "median_length_numerator": sorted_lengths[(len(sorted_lengths) - 1) // 2] + sorted_lengths[len(sorted_lengths) // 2],
            "median_length_denominator": 2,
            "source_sha256": "2" * 64,
            "fasta_sha256": fasta_sha,
            "identifier_map_sha256": idmap_sha,
            "normalization": "SOURCE_ORDER_ALL_RECORDS_UPPERCASE_IUPAC_DNA_NO_FILTER_NO_DEDUPLICATION",
            "annotation_consistency_status": "PASS",
            "annotation_coordinate_anomaly_count": 0,
        },
        "artifacts_sha256": {
            fasta_rel: fasta_sha,
            idmap_rel: idmap_sha,
            nsq_rel: _sha256_raw(nsq_bytes),
            nin_rel: _sha256_raw(nin_bytes),
            db_build_rel: _sha256_raw(db_build_path.read_bytes()),
        },
    }


def _establish_synthetic_cp1_baseline(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    resources: list[dict],
) -> tuple[dict[str, str], str]:
    """Write synthetic manifest and run_manifest and freeze their hashes as the accepted U01/E03 baseline."""
    manifest_path = root / r.MANIFEST
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["resources"] = resources
    r.write_json(manifest_path, manifest)

    expectations = dict(cal.EXPECTED_CP1_REFERENCE_SHA256)
    expectations[r.MANIFEST] = _sha256_raw(manifest_path.read_bytes())
    monkeypatch.setattr(cal, "EXPECTED_CP1_REFERENCE_SHA256", expectations)

    run_path = root / cal.EXPECTED_CP1_RUN_MANIFEST_PATH
    run_data = json.loads(run_path.read_text("utf-8"))
    run_data["outputs_sha256"][r.MANIFEST] = expectations[r.MANIFEST]
    r.write_json(run_path, run_data)
    run_sha = _sha256_raw(run_path.read_bytes())
    monkeypatch.setattr(cal, "EXPECTED_CP1_RUN_MANIFEST_SHA256", run_sha)

    orig_verify_cp1 = cal.verify_cp1_resources_and_manifests.__wrapped__ if hasattr(cal.verify_cp1_resources_and_manifests, "__wrapped__") else cal.verify_cp1_resources_and_manifests
    expected_count = len(resources)

    def _wrapped_verify_cp1(rt, **kw):
        kw.setdefault("expected_resource_count", expected_count)
        return orig_verify_cp1(rt, **kw)

    _wrapped_verify_cp1.__wrapped__ = orig_verify_cp1
    monkeypatch.setattr(cal, "verify_cp1_resources_and_manifests", _wrapped_verify_cp1)
    return expectations, run_sha


def test_e03_descriptor_sha256_boundary_and_coverage_predicate():
    """Verify the strict 6-field boundary of descriptor_sha256 vs geometry_record_sha256 and the coverage predicate."""
    base_descriptor = {
        "record_count": 3,
        "total_bases": 28,
        "ordered_record_lengths": [8, 12, 8],
        "ordered_ambiguous_base_counts": [0, 3, 1],
        "alphabet_policy": "UPPERCASE_IUPAC_DNA",
        "record_boundary_policy": "NEVER_CROSSED",
    }

    # Independent SHA256 oracle over the exact canonical JSON literal of the 6 fields
    expected_canonical_bytes = (
        '{\n'
        '  "alphabet_policy": "UPPERCASE_IUPAC_DNA",\n'
        '  "ordered_ambiguous_base_counts": [\n'
        '    0,\n'
        '    3,\n'
        '    1\n'
        '  ],\n'
        '  "ordered_record_lengths": [\n'
        '    8,\n'
        '    12,\n'
        '    8\n'
        '  ],\n'
        '  "record_boundary_policy": "NEVER_CROSSED",\n'
        '  "record_count": 3,\n'
        '  "total_bases": 28\n'
        '}\n'
    ).encode("utf-8")
    expected_desc_sha = hashlib.sha256(expected_canonical_bytes).hexdigest()

    computed_desc_sha = cal.compute_geometry_descriptor_sha256(base_descriptor)
    assert computed_desc_sha == expected_desc_sha

    # 1. Adding administrative metadata, paths, or IDs to the provenance record does NOT alter descriptor_sha256,
    #    while geometry_record_sha256 DOES change.
    rec_a = {
        "schema_version": 1,
        "artifact_id": cal.GEOMETRY_RECORD_ARTIFACT_ID,
        "campaign_id": "cp1_20261015",
        "resource_id": "R1_RNA",
        "descriptor_schema_id": cal.GEOMETRY_DESCRIPTOR_SCHEMA_ID,
        "descriptor_sha256": expected_desc_sha,
        "architecture_descriptor": dict(base_descriptor),
    }
    rec_b = {
        **rec_a,
        "administrative_note": "extra metadata outside descriptor",
        "source_fasta": {"fasta_path": "data/external/nto/cp1_20261015/R1_RNA/normalized.fasta"},
        "operator_audit_id": "AUDIT_99",
    }
    assert cal.extract_geometry_descriptor_sha256_from_record(rec_a) == expected_desc_sha
    assert cal.extract_geometry_descriptor_sha256_from_record(rec_b) == expected_desc_sha
    assert _sha256_raw(r.json_bytes(rec_a)) != _sha256_raw(r.json_bytes(rec_b))

    # Injecting an administrative field inside architecture_descriptor during record extraction fails closed
    rec_polluted = {
        **rec_a,
        "architecture_descriptor": {**base_descriptor, "administrative_id": "POLLUTED"},
    }
    with pytest.raises(r.ResourceContractError, match="extra=\\['administrative_id'\\]"):
        cal.extract_geometry_descriptor_sha256_from_record(rec_polluted)

    # 2. Altering ANY of the 6 fields changes descriptor_sha256 (or fails validation if invalid policy/sum)
    mut_lengths_permuted = {
        **base_descriptor,
        "ordered_record_lengths": [12, 8, 8],  # same sum=28 and record_count=3, different order
    }
    assert cal.compute_geometry_descriptor_sha256(mut_lengths_permuted) != expected_desc_sha

    mut_ambig_permuted = {
        **base_descriptor,
        "ordered_ambiguous_base_counts": [1, 3, 0],  # same sum=4, different order
    }
    assert cal.compute_geometry_descriptor_sha256(mut_ambig_permuted) != expected_desc_sha

    mut_ambig_value = {
        **base_descriptor,
        "ordered_ambiguous_base_counts": [0, 2, 1],
    }
    assert cal.compute_geometry_descriptor_sha256(mut_ambig_value) != expected_desc_sha

    mut_count_and_vectors = {
        **base_descriptor,
        "record_count": 2,
        "ordered_record_lengths": [16, 12],
        "ordered_ambiguous_base_counts": [0, 4],
    }
    assert cal.compute_geometry_descriptor_sha256(mut_count_and_vectors) != expected_desc_sha

    mut_total_bases = {
        **base_descriptor,
        "total_bases": 29,
        "ordered_record_lengths": [9, 12, 8],
    }
    assert cal.compute_geometry_descriptor_sha256(mut_total_bases) != expected_desc_sha

    with pytest.raises(r.ResourceContractError, match="alphabet_policy"):
        cal.validate_geometry_descriptor({**base_descriptor, "alphabet_policy": "LOWERCASE_DNA"})

    with pytest.raises(r.ResourceContractError, match="record_boundary_policy"):
        cal.validate_geometry_descriptor({**base_descriptor, "record_boundary_policy": "CONCATENATED"})

    # 3. Slipping extra fields (paths, IDs, mean, median, histogram, interval) or omitting a field in descriptor fails closed
    for forbidden_key, val in [
        ("fasta_path", "data/external/nto/cp1_20261015/R1/normalized.fasta"),
        ("resource_id", "R1"),
        ("mean_length", 9.33),
        ("median_length", 8),
        ("histogram", {"8": 2, "12": 1}),
        ("length_interval", [8, 12]),
    ]:
        with pytest.raises(r.ResourceContractError, match="NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 requires exactly"):
            cal.validate_geometry_descriptor({**base_descriptor, forbidden_key: val})

    for key in base_descriptor:
        incomplete = {k: v for k, v in base_descriptor.items() if k != key}
        with pytest.raises(r.ResourceContractError, match="NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 requires exactly"):
            cal.validate_geometry_descriptor(incomplete)

    # Boolean values disguised as integers are rejected
    with pytest.raises(r.ResourceContractError, match="positive integer"):
        cal.validate_geometry_descriptor({**base_descriptor, "record_count": True})
    with pytest.raises(r.ResourceContractError, match="positive integer"):
        cal.validate_geometry_descriptor({**base_descriptor, "ordered_record_lengths": [True, 19, 8]})

    # 4. Coverage predicate requires exact equality across all scalars, vectors, and policies
    assert cal.geometry_cell_covers_resource(
        base_descriptor,
        dict(base_descriptor),
        cell_descriptor_sha256=expected_desc_sha,
        resource_descriptor_sha256=expected_desc_sha,
    ) is True
    assert cal.geometry_cell_covers_resource(mut_lengths_permuted, base_descriptor) is False
    assert cal.geometry_cell_covers_resource(mut_ambig_permuted, base_descriptor) is False
    assert cal.geometry_cell_covers_resource(mut_ambig_value, base_descriptor) is False


def test_e03_geometry_derivation_iupac_ambiguity_canonical_order_and_determinism(synthetic_e01_env, monkeypatch, capsys):
    """Verify IUPAC ambiguity counting (N and non-N IUPAC bases), canonical order, scientific limitations, and byte determinism."""
    import importlib.util

    root = synthetic_e01_env["root"]
    g0_sha = _sha256_raw((root / r.G0_PATH).read_bytes())

    # Record 1: 16 nt pure ACGT -> 0 ambiguous
    # Record 2: 15 nt containing N and all non-ACGT IUPAC DNA symbols (R,Y,S,W,K,M,B,D,H,V,N = 11 ambiguous + 4 ACGT = 15 nt)
    # Record 3: 90 nt wrapped across 2 lines (80 + 10), with 2 'N' and 1 'R' -> 3 ambiguous
    rec3_seq = ("ACGT" * 20) + "ACGTNNRACG"
    assert len(rec3_seq) == 90
    res_entry = _build_synthetic_resource(
        root,
        "R1_RNA",
        [
            ("TX_002.1", "TX_002.1 Pure ACGT transcript", "ACGTACGTACGTACGT"),
            ("TX_001.1", "TX_001.1 IUPAC ambiguity transcript", "ACGTRYSWKMBDHVN"),
            ("TX_003.1", "TX_003.1 Wrapped transcript", rec3_seq),
        ],
        g0_sha=g0_sha,
    )

    _establish_synthetic_cp1_baseline(root, monkeypatch, [res_entry])

    derived_1 = cal.derive_resource_geometry_record(root, res_entry)
    derived_2 = cal.derive_resource_geometry_record(root, res_entry)
    assert r.json_bytes(derived_1) == r.json_bytes(derived_2)

    desc = derived_1["architecture_descriptor"]
    assert set(desc.keys()) == cal.GEOMETRY_DESCRIPTOR_KEYS
    assert desc["record_count"] == 3
    assert desc["total_bases"] == 16 + 15 + 90
    assert desc["ordered_record_lengths"] == [16, 15, 90]
    assert desc["ordered_ambiguous_base_counts"] == [0, 11, 3]
    assert desc["alphabet_policy"] == "UPPERCASE_IUPAC_DNA"
    assert desc["record_boundary_policy"] == "NEVER_CROSSED"

    # Canonical order preserved (TX_002.1 first, TX_001.1 second, TX_003.1 third)
    assert derived_1["canonical_order"]["ordered_analysis_ids"] == [
        "R1_RNA__00000001",
        "R1_RNA__00000002",
        "R1_RNA__00000003",
    ]
    assert derived_1["canonical_order"]["ordered_source_ids"] == [
        "TX_002.1",
        "TX_001.1",
        "TX_003.1",
    ]

    # Scientific limitations and S05 declarations present; no summary statistics (mean, median, histogram, interval)
    policy = derived_1["policy_and_scientific_limitations"]
    assert policy["simplification_id"] == "S05"
    assert "ENVELOPE_GEOMETRY_ONLY_REAL_COMPOSITION_NOT_REPRESENTED" in policy["nominal_limitations"]
    assert "RESOURCE_SPECIFIC_TRUNCATION_QA_REQUIRED" in policy["nominal_limitations"]
    assert "unmaterialized" in policy["prior_state_declaration"]
    assert policy["structural_preparation_only"] is True
    assert policy["queries_executed"] is False
    assert policy["recovery_evaluation_executed"] is False
    for summary_field in ("mean_length", "median_length", "minimum_length", "maximum_length", "histogram", "interval"):
        assert summary_field not in desc
        assert summary_field not in derived_1

    # Run CLI subcommand e03 and verify output file and hashes
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "prepare_nb04_calibration.py"
    spec = importlib.util.spec_from_file_location("prepare_nb04_calibration", script_path)
    cli = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cli)

    rc = cli.main(["e03", "--root", str(root)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "NB04_CP1_E03_GEOMETRY_DERIVATION"
    assert out["campaign_id"] == "cp1_20261015"
    assert out["queries_executed"] is False
    assert out["recovery_evaluation_executed"] is False
    res_out = out["resources"]["R1_RNA"]
    geom_path = root / res_out["geometry_record_path"]
    assert geom_path.is_file()
    assert res_out["geometry_record_sha256"] == _sha256_raw(geom_path.read_bytes())
    assert res_out["descriptor_sha256"] == cal.compute_geometry_descriptor_sha256(desc)
    assert res_out["geometry_record_sha256"] != res_out["descriptor_sha256"]


def test_e03_cross_check_failures_block_derivation(synthetic_e01_env, monkeypatch):
    """Verify that any mismatch in fasta_sha256, identifier_map.tsv, quality, or sequence alphabet blocks derivation."""
    root = synthetic_e01_env["root"]
    g0_sha = _sha256_raw((root / r.G0_PATH).read_bytes())
    base_res = _build_synthetic_resource(
        root,
        "R1_RNA",
        [
            ("TX_1", "TX_1 desc", "ACGTACGTNN"),
            ("TX_2", "TX_2 desc", "ACGTRYSW"),
        ],
        g0_sha=g0_sha,
    )
    _establish_synthetic_cp1_baseline(root, monkeypatch, [base_res])
    fasta_path = root / base_res["fasta_path"]
    idmap_path = root / base_res["identifier_map_path"]
    orig_fasta = fasta_path.read_bytes()
    orig_idmap = idmap_path.read_bytes()

    # 1. fasta_sha256 mismatch on disk vs certified manifest blocks derivation
    fasta_path.write_bytes(orig_fasta + b"\n")
    with pytest.raises(r.ResourceContractError, match="certified fasta_sha256 mismatch before geometry derivation"):
        cal.derive_resource_geometry_record(root, base_res)
    fasta_path.write_bytes(orig_fasta)

    # 2. identifier_map_sha256 mismatch on disk vs certified manifest blocks derivation
    idmap_path.write_bytes(orig_idmap + b"\n")
    with pytest.raises(r.ResourceContractError, match="certified identifier_map_sha256 mismatch before geometry derivation"):
        cal.derive_resource_geometry_record(root, base_res)
    idmap_path.write_bytes(orig_idmap)

    # Helper to test internal post-hash checks by updating synthetic baseline expectations for the mutated file
    def _with_current_hashes(res_copy: dict) -> dict:
        f_sha = _sha256_raw(fasta_path.read_bytes())
        i_sha = _sha256_raw(idmap_path.read_bytes())
        res_copy = json.loads(json.dumps(res_copy))
        res_copy["quality"]["fasta_sha256"] = f_sha
        res_copy["quality"]["identifier_map_sha256"] = i_sha
        res_copy["artifacts_sha256"][res_copy["fasta_path"]] = f_sha
        res_copy["artifacts_sha256"][res_copy["identifier_map_path"]] = i_sha
        _establish_synthetic_cp1_baseline(root, monkeypatch, [res_copy])
        return res_copy

    # 3. Record count mismatch against identifier_map.tsv (fewer rows in map)
    lines = orig_idmap.decode("utf-8").splitlines(keepends=True)
    idmap_path.write_bytes("".join(lines[:-1]).encode("utf-8"))
    with pytest.raises(r.ResourceContractError, match="identifier_map record count mismatch"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    idmap_path.write_bytes(orig_idmap)

    # 4. Per-record length_nt mismatch in identifier_map.tsv (even when total sum is preserved: 11 + 7 == 10 + 8)
    bad_len_lines = [
        lines[0],
        lines[1].replace("\t10\t", "\t11\t"),
        lines[2].replace("\t8\t", "\t7\t"),
    ]
    idmap_path.write_bytes("".join(bad_len_lines).encode("utf-8"))
    with pytest.raises(r.ResourceContractError, match="identifier_map length_nt mismatch"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    idmap_path.write_bytes(orig_idmap)

    # 5. Canonical analysis_id order mismatch in identifier_map.tsv
    swapped_lines = [lines[0], lines[2], lines[1]]
    idmap_path.write_bytes("".join(swapped_lines).encode("utf-8"))
    with pytest.raises(r.ResourceContractError, match="identifier_map analysis_id order mismatch"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    idmap_path.write_bytes(orig_idmap)

    # 6. Per-record sequence_sha256 mismatch in identifier_map.tsv (Reviewer gap from Round 003)
    rec1_true_sha = hashlib.sha256(b"ACGTACGTNN").hexdigest()
    bad_seq_sha_lines = [
        lines[0],
        lines[1].replace(rec1_true_sha, "f" * 64),
        lines[2],
    ]
    idmap_path.write_bytes("".join(bad_seq_sha_lines).encode("utf-8"))
    with pytest.raises(r.ResourceContractError, match="identifier_map sequence_sha256 mismatch at R1_RNA__00000001"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    idmap_path.write_bytes(orig_idmap)

    # 7. Ambiguity sum mismatch against manifest quality.ambiguous_bases
    bad_ambig_res = json.loads(json.dumps(base_res))
    bad_ambig_res["quality"]["ambiguous_bases"] = 999
    with pytest.raises(r.ResourceContractError, match="ambiguous_bases sum mismatch against manifest quality"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(bad_ambig_res))

    # 8. Total bases mismatch against manifest quality.total_bases
    bad_total_res = json.loads(json.dumps(base_res))
    bad_total_res["quality"]["total_bases"] = 999
    with pytest.raises(r.ResourceContractError, match="total_bases mismatch against manifest quality"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(bad_total_res))

    # 9. Record count mismatch against manifest quality.record_count
    bad_count_res = json.loads(json.dumps(base_res))
    bad_count_res["quality"]["record_count"] = 99
    with pytest.raises(r.ResourceContractError, match="record_count mismatch against manifest quality"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(bad_count_res))

    # 10. Lowercase or non-IUPAC base ('Z') in normalized.fasta rejected
    fasta_path.write_bytes(orig_fasta.replace(b"ACGTACGTNN", b"acgtacgtnn"))
    with pytest.raises(r.ResourceContractError, match="non-uppercase-IUPAC DNA"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    fasta_path.write_bytes(orig_fasta.replace(b"ACGTACGTNN", b"ACGTACGTNZ"))
    with pytest.raises(r.ResourceContractError, match="non-uppercase-IUPAC DNA"):
        cal.derive_resource_geometry_record(root, _with_current_hashes(base_res))
    fasta_path.write_bytes(orig_fasta)


def test_e03_destination_protection_and_atomic_batch_prewrite_validation(synthetic_e01_env, monkeypatch):
    """Verify that protected or pre-existing destinations are rejected before any write and batch failure writes nothing."""
    root = synthetic_e01_env["root"]
    g0_sha = _sha256_raw((root / r.G0_PATH).read_bytes())

    res1 = _build_synthetic_resource(
        root,
        "R1_RNA",
        [("TX_1", "TX_1 desc", "ACGTACGTNN")],
        g0_sha=g0_sha,
    )
    res2 = _build_synthetic_resource(
        root,
        "R2_RNA",
        [("TX_2", "TX_2 desc", "ACGTRYSW")],
        g0_sha=g0_sha,
    )

    _establish_synthetic_cp1_baseline(root, monkeypatch, [res1, res2])

    # 1. Protected in-root destination rejected before any write
    victim = root / "config/frozen.tsv"
    victim_before = victim.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized E03 path"):
        cal.derive_and_write_all_resources_geometry(
            root,
            destination_overrides={"R1_RNA": victim},
        )
    assert victim.read_bytes() == victim_before
    assert not (root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json").exists()
    assert not (root / "data/external/nto/cp1_20261015/geometry/R2_RNA.json").exists()

    # 2. Out-of-root destination and unsafe campaign_id rejected
    with pytest.raises(r.ResourceContractError, match="outside project root"):
        cal.validate_e03_geometry_destination(root, root.parent / "escape.json", resource_id="R1_RNA")
    with pytest.raises(r.ResourceContractError, match="invalid geometry campaign_id"):
        cal.validate_e03_geometry_destination(root, campaign_id="../escape", resource_id="R1_RNA")

    # 3. Pre-existing destination on R2_RNA blocks the entire batch BEFORE writing R1_RNA
    r2_target = root / "data/external/nto/cp1_20261015/geometry/R2_RNA.json"
    _put(r2_target, b'{"preexisting": true}\n')
    with pytest.raises(r.ResourceContractError, match="already exists and must never be overwritten"):
        cal.derive_and_write_all_resources_geometry(root)
    assert r2_target.read_bytes() == b'{"preexisting": true}\n'
    assert not (root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json").exists()
    r2_target.unlink()

    # 4. Verification failure on R2_RNA (corrupted FASTA) blocks the entire batch BEFORE writing R1_RNA
    r2_fasta = root / res2["fasta_path"]
    orig_r2_fasta = r2_fasta.read_bytes()
    r2_fasta.write_bytes(orig_r2_fasta + b"A\n")
    with pytest.raises(r.ResourceContractError, match="certified fasta_sha256 mismatch"):
        cal.derive_and_write_all_resources_geometry(root)
    assert not (root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json").exists()
    assert not (root / "data/external/nto/cp1_20261015/geometry/R2_RNA.json").exists()
    r2_fasta.write_bytes(orig_r2_fasta)

    # 5. Clean batch succeeds and writes both R1_RNA.json and R2_RNA.json; a second run is refused (pre-existing)
    summary = cal.derive_and_write_all_resources_geometry(root)
    assert summary["resource_count"] == 2
    assert (root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json").is_file()
    assert (root / "data/external/nto/cp1_20261015/geometry/R2_RNA.json").is_file()

    with pytest.raises(r.ResourceContractError, match="already exists and must never be overwritten"):
        cal.derive_and_write_all_resources_geometry(root)


def test_u02_f01_authoritative_manifest_trust_boundary_and_reviewer_counterexample(
    synthetic_e01_env,
    monkeypatch,
):
    """Verify U02_F01 resolution: E03 enforces the fixed authoritative CP1 manifest identity before derivation or write."""
    root = synthetic_e01_env["root"]
    g0_sha = _sha256_raw((root / r.G0_PATH).read_bytes())

    # Build an accepted 2-resource baseline and freeze its expectations ONCE.
    res1 = _build_synthetic_resource(
        root,
        "R1_RNA",
        [("SRC1.1", "SRC1.1 synthetic", "ACGTACGTACGTACGT")],
        g0_sha=g0_sha,
    )
    res2 = _build_synthetic_resource(
        root,
        "R2_RNA",
        [("SRC2.1", "SRC2.1 synthetic", "ACGTRYSW")],
        g0_sha=g0_sha,
    )
    baseline_expectations, baseline_run_sha = _establish_synthetic_cp1_baseline(
        root,
        monkeypatch,
        [res1, res2],
    )
    manifest_path = root / r.MANIFEST
    baseline_manifest_bytes = manifest_path.read_bytes()
    r1_fasta_path = root / res1["fasta_path"]
    r1_idmap_path = root / res1["identifier_map_path"]
    baseline_r1_fasta = r1_fasta_path.read_bytes()
    baseline_r1_idmap = r1_idmap_path.read_bytes()
    r1_geom_path = root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json"
    r2_geom_path = root / "data/external/nto/cp1_20261015/geometry/R2_RNA.json"

    # Confirm initial accepted baseline passes U01 and E03 read-only checks
    _, accepted_u01 = cal.verify_cp1_resources_and_manifests(root)
    assert accepted_u01["verdict"] == "PASS"
    initial_geom = cal.derive_resource_geometry_record(root, res1)
    assert initial_geom["architecture_descriptor"]["ordered_ambiguous_base_counts"] == [0]

    # 1. Reviewer's exact Round 003 counterexample (U02_F01):
    #    Replace base T -> N in FASTA, update sequence_sha256 in identifier_map.tsv, and update
    #    fasta_sha256, identifier_map_sha256, ambiguous_bases=1, and artifacts_sha256 in manifest.json,
    #    while preserving the prior accepted baseline expectations (baseline_expectations).
    r1_fasta_path.write_bytes(baseline_r1_fasta.replace(b"ACGTACGTACGTACGT", b"ACGTACGTACGTACGN"))
    orig_seq_sha = hashlib.sha256(b"ACGTACGTACGTACGT").hexdigest()
    mod_seq_sha = hashlib.sha256(b"ACGTACGTACGTACGN").hexdigest()
    r1_idmap_path.write_bytes(baseline_r1_idmap.replace(orig_seq_sha.encode("ascii"), mod_seq_sha.encode("ascii")))

    mutated_res1 = json.loads(json.dumps(res1))
    mutated_res1["quality"]["fasta_sha256"] = _sha256_raw(r1_fasta_path.read_bytes())
    mutated_res1["quality"]["identifier_map_sha256"] = _sha256_raw(r1_idmap_path.read_bytes())
    mutated_res1["quality"]["ambiguous_bases"] = 1
    mutated_res1["artifacts_sha256"][res1["fasta_path"]] = mutated_res1["quality"]["fasta_sha256"]
    mutated_res1["artifacts_sha256"][res1["identifier_map_path"]] = mutated_res1["quality"]["identifier_map_sha256"]

    mutated_manifest = json.loads(baseline_manifest_bytes.decode("utf-8"))
    mutated_manifest["resources"] = [mutated_res1, res2]
    r.write_json(manifest_path, mutated_manifest)
    assert _sha256_raw(manifest_path.read_bytes()) != baseline_expectations[r.MANIFEST]

    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.verify_cp1_resources_and_manifests(root)

    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_resource_geometry_record(root, mutated_res1)

    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_and_write_all_resources_geometry(root)

    assert not r1_geom_path.exists()
    assert not r2_geom_path.exists()

    # Restore R1 FASTA and ID map to baseline
    r1_fasta_path.write_bytes(baseline_r1_fasta)
    r1_idmap_path.write_bytes(baseline_r1_idmap)

    # 2. Altered manifest metadata (without touching FASTA/ID map) rejected before any write
    altered_meta_manifest = json.loads(baseline_manifest_bytes.decode("utf-8"))
    altered_meta_manifest["resources"][0]["scientific_name"] = "Tampered species"
    r.write_json(manifest_path, altered_meta_manifest)
    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_and_write_all_resources_geometry(root)
    assert not r1_geom_path.exists()
    assert not r2_geom_path.exists()

    # 3. Resource reduction ([res1, res2] -> [res1]) with consistent internal hashes rejected before any write
    reduced_manifest = json.loads(baseline_manifest_bytes.decode("utf-8"))
    reduced_manifest["resources"] = [res1]
    r.write_json(manifest_path, reduced_manifest)
    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_and_write_all_resources_geometry(root)
    assert not r1_geom_path.exists()
    assert not r2_geom_path.exists()

    # Even if an caller passes updated reference/run_manifest hashes for the reduced manifest,
    # the fixed expected_resource_count=2 and expected_resource_ids=("R1_RNA", "R2_RNA") reject the reduction.
    reduced_ref = dict(baseline_expectations, **{r.MANIFEST: _sha256_raw(manifest_path.read_bytes())})
    run_path = root / cal.EXPECTED_CP1_RUN_MANIFEST_PATH
    orig_run_bytes = run_path.read_bytes()
    reduced_run = json.loads(orig_run_bytes.decode("utf-8"))
    reduced_run["outputs_sha256"][r.MANIFEST] = reduced_ref[r.MANIFEST]
    r.write_json(run_path, reduced_run)
    reduced_run_sha = _sha256_raw(run_path.read_bytes())
    with pytest.raises(r.ResourceContractError, match="CP1 resource count mismatch: expected=2 observed=1"):
        cal.derive_and_write_all_resources_geometry(
            root,
            expected_reference_sha256=reduced_ref,
            expected_run_manifest_sha256=reduced_run_sha,
            expected_resource_count=2,
        )
    with pytest.raises(r.ResourceContractError, match="CP1 authoritative resource_id sequence mismatch"):
        cal.derive_and_write_all_resources_geometry(
            root,
            expected_reference_sha256=reduced_ref,
            expected_run_manifest_sha256=reduced_run_sha,
            expected_resource_count=1,
            expected_resource_ids=("R1_RNA", "R2_RNA"),
        )
    run_path.write_bytes(orig_run_bytes)
    assert not r1_geom_path.exists()
    assert not r2_geom_path.exists()

    # 4. Resource substitution ([res1, res2] -> [res1, res3]) with equal count=2 and internally consistent hashes rejected
    res3 = _build_synthetic_resource(
        root,
        "R3_RNA",
        [("SRC3.1", "SRC3.1 substituted", "ACGTNNNNACGT")],
        g0_sha=g0_sha,
    )
    substituted_manifest = json.loads(baseline_manifest_bytes.decode("utf-8"))
    substituted_manifest["resources"] = [res1, res3]
    r.write_json(manifest_path, substituted_manifest)
    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_and_write_all_resources_geometry(root)

    sub_ref = dict(baseline_expectations, **{r.MANIFEST: _sha256_raw(manifest_path.read_bytes())})
    sub_run = json.loads(orig_run_bytes.decode("utf-8"))
    sub_run["outputs_sha256"][r.MANIFEST] = sub_ref[r.MANIFEST]
    r.write_json(run_path, sub_run)
    sub_run_sha = _sha256_raw(run_path.read_bytes())
    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 authoritative resource_id sequence mismatch: expected=\['R1_RNA', 'R2_RNA'\] observed=\['R1_RNA', 'R3_RNA'\]",
    ):
        cal.derive_and_write_all_resources_geometry(
            root,
            expected_reference_sha256=sub_ref,
            expected_run_manifest_sha256=sub_run_sha,
            expected_resource_count=2,
            expected_resource_ids=("R1_RNA", "R2_RNA"),
        )
    run_path.write_bytes(orig_run_bytes)
    assert not r1_geom_path.exists()
    assert not r2_geom_path.exists()
    assert not (root / "data/external/nto/cp1_20261015/geometry/R3_RNA.json").exists()

    # 5. Direct call to derive_resource_geometry_record with a modified resource mapping while manifest on disk is untouched
    manifest_path.write_bytes(baseline_manifest_bytes)
    forged_res1 = json.loads(json.dumps(res1))
    forged_res1["scientific_name"] = "Forged caller dict"
    with pytest.raises(r.ResourceContractError, match="resource entry for R1_RNA diverges from authoritative CP1 manifest"):
        cal.derive_resource_geometry_record(root, forged_res1)

    # 6. Valid path on restored authoritative baseline succeeds and preserves pre-existing files on any subsequent failure
    summary = cal.derive_and_write_all_resources_geometry(
        root,
        expected_reference_sha256=baseline_expectations,
        expected_run_manifest_sha256=baseline_run_sha,
        expected_resource_count=2,
        expected_resource_ids=("R1_RNA", "R2_RNA"),
    )
    assert summary["resource_count"] == 2
    assert r1_geom_path.is_file()
    assert r2_geom_path.is_file()
    r1_saved_bytes = r1_geom_path.read_bytes()
    r2_saved_bytes = r2_geom_path.read_bytes()

    # Subsequent tampered manifest fails before touching existing geometry records
    r.write_json(manifest_path, mutated_manifest)
    with pytest.raises(
        r.ResourceContractError,
        match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json",
    ):
        cal.derive_and_write_all_resources_geometry(root)
    assert r1_geom_path.read_bytes() == r1_saved_bytes
    assert r2_geom_path.read_bytes() == r2_saved_bytes


# ======================================================================
# U03 / E05 Part 1: build inspection, 31-parameter matrix, output integrity,
#                   19 QA criteria and the P30 / P23 Coordinator decisions
# ======================================================================

# (parameter_id, tool, parameter, decision_stage, status) exactly as in 08_b4_calibration_parameter_matrix_v2_1.tsv
_E05_MATRIX_ROWS = (
    ("P01", "blastn", "program selection (blastn vs megablast vs dc-megablast)", "ARCHITECTURAL_PRE_G1", "PROPOSED_FIXED_BY_ARCHITECTURE"),
    ("P02", "blastn", "-task", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P03", "blastn", "-word_size", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P04", "blastn", "-evalue (reporting limit)", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P05", "blastn", "-reward", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P06", "blastn", "-penalty", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P07", "blastn", "-gapopen", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P08", "blastn", "-gapextend", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P09", "blastn", "-dust", "ARCHITECTURAL_PRE_G1", "PROPOSED_FIXED_BY_ARCHITECTURE"),
    ("P10", "blastn", "-soft_masking", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P11", "blastn", "-lcase_masking", "ARCHITECTURAL_PRE_G1", "PROPOSED_FIXED_BY_ARCHITECTURE"),
    ("P12", "blastn", "-strand", "ARCHITECTURAL_PRE_G1", "PROPOSED_FIXED_BY_ARCHITECTURE"),
    ("P13", "blastn", "-max_target_seqs", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION_AND_EMPIRICAL_PROOF"),
    ("P14", "blastn", "-max_hsps", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION_AND_EMPIRICAL_PROOF"),
    ("P15", "blastn", "-perc_identity", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P16", "blastn", "-qcov_hsp_perc", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P17", "blastn", "-culling_limit", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P18", "blastn", "-best_hit_overhang", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P19", "blastn", "-best_hit_score_edge", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P20", "blastn", "-subject_besthit", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P21", "blastn", "-xdrop_ungap, -xdrop_gap, -xdrop_gap_final", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P22", "blastn", "-window_size (two-hit window)", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P23", "blastn", "-dbsize / -searchsp", "QA_ONLY_PLUS_G1_PRODUCTION_DECISION", "OPEN_DESIGN_QUESTION"),
    ("P24", "blastn", "-ungapped", "EXCLUDED_BY_ARCHITECTURE", "PROPOSED_EXCLUDED"),
    ("P25", "blastn", "-sum_stats", "G1_RECORD_EXPLICITLY", "REQUIRES_EXPLICIT_RECORDING"),
    ("P26", "blastn", "-outfmt and the field set", "ARCHITECTURAL_PRE_G1", "REUSABLE_AS_STARTING_HYPOTHESIS"),
    ("P27", "blastn", "-num_threads", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P28", "makeblastdb", "-dbtype, -parse_seqids, -title, -out", "ARCHITECTURAL_PRE_G1", "REUSABLE_AS_STARTING_HYPOTHESIS"),
    ("P29", "makeblastdb", "-max_file_sz and resulting volume count", "G1_AFTER_CALIBRATION", "REQUIRES_CALIBRATION"),
    ("P30", "pipeline", "deterministic record ordering of the input FASTA", "ARCHITECTURAL_PRE_G1", "REQUIRES_DESIGN"),
    ("P31", "pipeline", "HSP table parser and BTOP validation", "ARCHITECTURAL_PRE_G1", "REUSABLE_AS_STARTING_HYPOTHESIS"),
)
_E05_FIXED_CANDIDATES = {"P01": "blastn", "P09": "no", "P11": "false", "P12": "both"}
_E05_P26_PRECEDENT = "outfmt 6 with " + " ".join(cal.E05_OUTFMT_6_PRECEDENT) + " (NB01-NB03)"
_E05_ALL_SPECIFIERS = cal.E05_OUTFMT_6_PRECEDENT + cal.E05_OUTFMT_6_ADDITIONS + cal.E05_OUTFMT_6_AVAILABLE_NOT_ADOPTED
_E05_EXCLUDED_PASSAGE = (
    "**`PROPOSED_EXCLUDED`** — recommended not used at all: `-perc_identity`,\n"
    "`-qcov_hsp_perc`, `-culling_limit`, `-best_hit_overhang`, `-best_hit_score_edge`,\n"
    "`-subject_besthit`, `-ungapped`. Synthetic passage standing in for design document section 7."
)


def _e05_outfmt_block() -> str:
    return (
        " -outfmt <String>\n   alignment view options:\n     6 = Tabular,\n    11 = BLAST archive (ASN.1),\n"
        + "".join(f"   \t    {s} means {s}\n" for s in _E05_ALL_SPECIFIERS)
        + "   Default = `0'\n"
    )


_FAKE_BLASTN_HELP = (
    "USAGE\n  blastn [-h] [-help]\nOPTIONAL ARGUMENTS\n"
    " -h\n   Print USAGE and DESCRIPTION;  ignore all other parameters\n"
    " *** Input query options\n"
    " -strand <String, `both', `minus', `plus'>\n   Query strand(s) to search against database/subject\n   Default = `both'\n"
    " *** General search options\n"
    " -task <String, Permissible values: 'blastn' 'blastn-short' 'dc-megablast'\n                'megablast' 'rmblastn' >\n   Task to execute\n   Default = `megablast'\n"
    " -out <File_Out, file name length < 256>\n   Output file name\n   Default = `-'\n"
    " -evalue <Real>\n   Expectation value (E) threshold for saving hits. Default = 10 (1000 for\n   blastn-short)\n"
    " -word_size <Integer, >=4>\n   Word size for wordfinder algorithm (length of best perfect match)\n"
    " -gapopen <Integer>\n   Cost to open a gap\n"
    " -gapextend <Integer>\n   Cost to extend a gap\n"
    " -penalty <Integer, <=0>\n   Penalty for a nucleotide mismatch\n"
    " -reward <Integer, >=0>\n   Reward for a nucleotide match\n"
    " *** Formatting options\n" + _e05_outfmt_block() +
    " *** Query filtering options\n"
    " -dust <String>\n   Filter query sequence with DUST (Format: 'yes', 'level window linker', or\n   'no' to disable) Default = '20 64 1' ('no' for blastn-short)\n"
    " -soft_masking <Boolean>\n   Apply filtering locations as soft masks\n   Default = `true'\n"
    " -lcase_masking\n   Use lower case filtering in query and subject sequence(s)?\n"
    " *** Restrict search or results\n"
    " -perc_identity <Real, 0..100>\n   Percent identity\n"
    " -qcov_hsp_perc <Real, 0..100>\n   Percent query coverage per hsp\n"
    " -max_hsps <Integer, >=1>\n   Set maximum number of HSPs per subject sequence to save for each query\n"
    " -culling_limit <Integer, >=0>\n   If the query range of a hit is enveloped by that of at least this many\n   higher-scoring hits, delete the hit\n    * Incompatible with:  best_hit_overhang, best_hit_score_edge\n"
    " -best_hit_overhang <Real, (>0 and <0.5)>\n   Best Hit algorithm overhang value (recommended value: 0.1)\n    * Incompatible with:  culling_limit\n"
    " -best_hit_score_edge <Real, (>0 and <0.5)>\n   Best Hit algorithm score edge value (recommended value: 0.1)\n    * Incompatible with:  culling_limit\n"
    " -subject_besthit\n   Return only the best HSP for each non overlapping query region\n"
    " -max_target_seqs <Integer, >=1>\n   Maximum number of aligned sequences to keep \n   (value of 5 or more is recommended)\n   Default = `500'\n    * Incompatible with:  num_descriptions, num_alignments\n"
    " *** Statistical options\n"
    " -dbsize <Int8>\n   Effective length of the database \n"
    " -searchsp <Int8, >=0>\n   Effective length of the search space\n"
    " *** Extension options\n"
    " -xdrop_ungap <Real>\n   X-dropoff value (in bits) for ungapped extensions\n"
    " -xdrop_gap <Real>\n   X-dropoff value (in bits) for preliminary gapped extensions\n"
    " -xdrop_gap_final <Real>\n   X-dropoff value (in bits) for final gapped alignment\n"
    " -ungapped\n   Perform ungapped alignment only?\n"
    " -window_size <Integer, >=0>\n   Multiple hits window size, use 0 to specify 1-hit algorithm\n"
    " -off_diagonal_range <Integer, >=0>\n   Number of off-diagonals to search for the 2nd hit, use 0 to turn off\n   Default = `0'\n"
    " *** Miscellaneous options\n"
    " -num_threads <Integer, >=1>\n   Number of threads (CPUs) to use in the BLAST search\n   Default = `1'\n    * Incompatible with:  remote\n"
)

_FAKE_MAKEBLASTDB_HELP = (
    "USAGE\n  makeblastdb [-h] [-help]\nREQUIRED ARGUMENTS\n"
    " -dbtype <String, `nucl', `prot'>\n   Molecule type of target db\n"
    "OPTIONAL ARGUMENTS\n"
    " *** Configuration options\n"
    " -title <String>\n   Title for BLAST database\n   Default = input file name provided to -in argument\n"
    " -parse_seqids\n   Option to parse seqid for FASTA input if set, for all other input types\n   seqids are parsed automatically\n"
    " -out <String>\n   Name of BLAST database to be created\n   Default = input file name provided to -in argumentRequired if multiple\n   file(s)/database(s) are provided as input\n"
    " -blastdb_version <Integer, 4..5>\n   Version of BLAST database to be created\n   Default = `5'\n"
    " -max_file_sz <String>\n   Maximum file size for BLAST database files\n   Default = `3GB'\n"
)

_FAKE_BLAST_FORMATTER_HELP = (
    "USAGE\n  blast_formatter [-h] [-help]\nOPTIONAL ARGUMENTS\n"
    " *** Input options\n"
    " -archive <File_In>\n   File containing BLAST Archive format in ASN.1 (i.e.: output format 11)\n    * Incompatible with:  rid\n"
    " *** Formatting options\n" + _e05_outfmt_block() +
    " -num_descriptions <Integer, >=0>\n   Number of database sequences to show one-line descriptions for\n   Not applicable for outfmt > 4\n   Default = `500'\n    * Incompatible with:  max_target_seqs\n"
    " -num_alignments <Integer, >=0>\n   Number of database sequences to show alignments for\n   Default = `250'\n    * Incompatible with:  max_target_seqs\n"
    " *** Restrict search or results\n"
    " -max_target_seqs <Integer, >=1>\n   Maximum number of aligned sequences to keep \n   (value of 5 or more is recommended)\n   Default = `500'\n    * Incompatible with:  num_descriptions, num_alignments\n"
)

_FAKE_BLASTDBCMD_HELP = "USAGE\n  blastdbcmd [-h] [-help]\nOPTIONAL ARGUMENTS\n -entry <String>\n   Comma-delimited search string(s) of sequence identifiers\n"
_FAKE_DUSTMASKER_HELP = "USAGE\n  dustmasker [-h] [-help]\nOPTIONAL ARGUMENTS\n -window <Integer>\n   DUST window length\n   Default = `64'\n"


@pytest.fixture
def synthetic_e05_env(synthetic_e01_env, monkeypatch: pytest.MonkeyPatch):
    """Extend synthetic_e01_env with the 5 E05 tools, the 4 NB04_B5_INPUTS documents and an E03 geometry record."""
    root = synthetic_e01_env["root"]
    ext_dir = synthetic_e01_env["corpus_dirs"]["NB04_B5_INPUTS"]
    bin_dir = synthetic_e01_env["bin_dir"]

    for tool in cal.E05_REQUIRED_TOOLS:
        _put(bin_dir / tool, f"ELF_BINARY_{tool}".encode("ascii"))

    def parameter_row(pid, tool, parameter, stage, status):
        candidate = _E05_FIXED_CANDIDATES.get(pid, f"design_space_{pid}")
        precedent = _E05_P26_PRECEDENT if pid == "P26" else f"precedent_{pid}"
        return "\t".join([
            pid, tool, parameter, precedent, candidate, "SEARCH_PARAMETER", "false", f"question_{pid}",
            f"failure_mode_{pid}", "LOW", "LOW", "NONE", stage, status, f"notes_{pid}",
        ])

    param_bytes = ("\n".join(["\t".join(cal.E05_PARAMETER_MATRIX_HEADER)] + [parameter_row(*row) for row in _E05_MATRIX_ROWS]) + "\n").encode("utf-8")
    qa_lines = ["\t".join(cal.E05_QA_MATRIX_HEADER)] + [
        "\t".join([qid, "STABLE_PARSING" if qid == "QA-I" else f"CRITERION_{qid}", "F01, F02, plus deliberately corrupted copies of a valid output" if qid == "QA-I" else f"fixtures_{qid}", f"metric_{qid}", f"expected_{qid}", f"failure_{qid}", "YES", "false", "NOT_TESTED"])
        for qid in sorted(cal.E05_QA_SPEC)
    ]
    qa_bytes = ("\n".join(qa_lines) + "\n").encode("utf-8")
    doc06_bytes = b"# 06 Truncation and Completeness Contract (synthetic)\n"
    doc05_bytes = (
        "# 05 Design (synthetic)\n\n" + _E05_EXCLUDED_PASSAGE + "\n\n**`OPEN_DESIGN_QUESTION`** - synthetic.\n"
    ).encode("utf-8")

    _put(ext_dir / "08_b4_calibration_parameter_matrix_v2_1.tsv", param_bytes)
    _put(ext_dir / "09_b4_calibration_qa_matrix_v2.tsv", qa_bytes)
    _put(ext_dir / "06_B4_TRUNCATION_AND_COMPLETENESS_CONTRACT_v2_1.md", doc06_bytes)
    _put(ext_dir / "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md", doc05_bytes)
    e05_norm_shas = {
        "08_b4_calibration_parameter_matrix_v2_1.tsv": _sha256_raw(param_bytes),
        "09_b4_calibration_qa_matrix_v2.tsv": _sha256_raw(qa_bytes),
        "06_B4_TRUNCATION_AND_COMPLETENESS_CONTRACT_v2_1.md": _sha256_raw(doc06_bytes),
        "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md": _sha256_raw(doc05_bytes),
    }
    monkeypatch.setattr(cal, "E05_NORMATIVE_DOCUMENTS_SHA256", e05_norm_shas)

    norm_spec = dict(cal.NORMATIVE_DOCUMENTS_SPEC)
    cert_path = root / r.G0_PATH
    cert = json.loads(cert_path.read_text("utf-8"))
    for doc_name, sha in e05_norm_shas.items():
        norm_spec[doc_name] = {
            "expected_sha256": sha, "hash_mode": "RAW", "location_class": "EXTERNAL_LOCAL_CORPUS",
            "corpus_id": "NB04_B5_INPUTS", "repository_relative_path": None,
        }
        cert["normative_documents"][doc_name] = sha
    monkeypatch.setattr(cal, "NORMATIVE_DOCUMENTS_SPEC", norm_spec)
    r.write_json(cert_path, cert)
    g0_sha = _sha256_raw(cert_path.read_bytes())
    monkeypatch.setattr(cal, "EXPECTED_G0_CERTIFICATE_SHA256", g0_sha)

    inv_path = root / r.INVENTORY
    r.write_json(inv_path, {"schema_version": 1, "g0_certificate_sha256": g0_sha})
    inv_sha = _sha256_raw(inv_path.read_bytes())
    manifest_path = root / r.MANIFEST
    manifest_obj = json.loads(manifest_path.read_text("utf-8"))
    manifest_obj["g0_certificate_sha256"] = g0_sha
    manifest_obj["inventory_sha256"] = inv_sha
    r.write_json(manifest_path, manifest_obj)
    run_path = root / cal.EXPECTED_CP1_RUN_MANIFEST_PATH
    run_obj = json.loads(run_path.read_text("utf-8"))
    run_obj["outputs_sha256"][r.INVENTORY] = inv_sha
    r.write_json(run_path, run_obj)
    exp_refs = dict(cal.EXPECTED_CP1_REFERENCE_SHA256)
    exp_refs[r.INVENTORY] = inv_sha
    monkeypatch.setattr(cal, "EXPECTED_CP1_REFERENCE_SHA256", exp_refs)

    res1 = _build_synthetic_resource(
        root, "R1_RNA",
        [("TX_1", "TX_1 synthetic", "ACGTACGTACGTACGT"), ("TX_2", "TX_2 synthetic", "ACGTRYSW")],
        g0_sha=g0_sha,
    )
    baseline_expectations, baseline_run_sha = _establish_synthetic_cp1_baseline(root, monkeypatch, [res1])
    monkeypatch.setattr(cal, "EXPECTED_CP1_RESOURCE_IDS", ("R1_RNA",))
    cal.derive_and_write_all_resources_geometry(
        root,
        expected_reference_sha256=baseline_expectations,
        expected_run_manifest_sha256=baseline_run_sha,
        expected_resource_count=1,
        expected_resource_ids=("R1_RNA",),
    )
    geometry_path = root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json"
    monkeypatch.setattr(cal, "EXPECTED_GEOMETRY_RECORD_SHA256", {"R1_RNA": _sha256_raw(geometry_path.read_bytes())})

    help_map = {
        "blastn": _FAKE_BLASTN_HELP, "makeblastdb": _FAKE_MAKEBLASTDB_HELP,
        "blast_formatter": _FAKE_BLAST_FORMATTER_HELP, "blastdbcmd": _FAKE_BLASTDBCMD_HELP,
        "dustmasker": _FAKE_DUSTMASKER_HELP,
    }

    def fake_e05_runner(cmd, **kwargs):
        exe_name, arg = Path(cmd[0]).name, (cmd[1] if len(cmd) > 1 else "")
        if arg == "-version":
            ver = "1.0.0" if exe_name == "dustmasker" else "2.17.0+"
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{exe_name}: {ver}\n Package: blast 2.17.0, build Aug 22 2026 11:52:50\n", stderr="")
        if arg == "-help":
            return subprocess.CompletedProcess(cmd, 0, stdout=help_map[exe_name], stderr="")
        raise AssertionError(f"Forbidden tool invocation in E05: {cmd!r}")

    return {**synthetic_e01_env, "e05_norm_shas": e05_norm_shas, "fake_e05_runner": fake_e05_runner, "help_map": help_map}


def _e05_inspect(env, **kwargs):
    kwargs.setdefault("which_resolver", env["fake_which"])
    kwargs.setdefault("runner", env["fake_e05_runner"])
    return cal.build_e05_configuration_inspection(env["root"], env["corpus_dirs"], expected_resource_count=1, **kwargs)


def test_e05_normative_documents_sha256_and_missing_file_gate(synthetic_e05_env):
    """Any divergent SHA256, missing file or tampered CP1 manifest blocks reading and inspection."""
    root = synthetic_e05_env["root"]
    ext_dir = synthetic_e05_env["corpus_dirs"]["NB04_B5_INPUTS"]

    with pytest.raises(r.ResourceContractError, match="NORMATIVE_DOCUMENT_INACCESSIBLE"):
        cal.verify_and_read_e05_normative_inputs(root, {})

    for doc_name in cal.E05_NORMATIVE_DOCUMENTS_SHA256:
        target = ext_dir / doc_name
        original = target.read_bytes()
        target.write_bytes(original + b" ")
        with pytest.raises(r.ResourceContractError, match=rf"E05 normative document SHA256 mismatch before reading {re.escape(doc_name)}"):
            _e05_inspect(synthetic_e05_env)
        target.unlink()
        with pytest.raises(r.ResourceContractError, match=rf"NORMATIVE_DOCUMENT_INACCESSIBLE: {re.escape(doc_name)}"):
            _e05_inspect(synthetic_e05_env)
        target.write_bytes(original)

    manifest_path = root / r.MANIFEST
    original = manifest_path.read_bytes()
    manifest_path.write_bytes(original + b"\n")
    with pytest.raises(r.ResourceContractError, match=r"CP1 reference artifact hash mismatch for data/reference/nb04_nto_resources_manifest\.json"):
        _e05_inspect(synthetic_e05_env)
    manifest_path.write_bytes(original)


def test_e05_tool_builds_missing_tool_not_applicable_and_divergent_build_blocks_reuse(synthetic_e05_env):
    """5-tool observation; a missing tool is NOT_APPLICABLE with grounds; divergence blocks reuse without failing."""
    env = synthetic_e05_env
    insp = _e05_inspect(env)
    sec_a = insp["a_observed_tool_builds"]
    sec_b = insp["b_build_comparison_with_cp1_receipts_and_derivations"]
    assert sec_a["all_five_tools_observed"] is True
    assert sec_b["equivalent_build_reuse_blocked"] is False
    assert sec_b["retrospective_executable_hash_attributed"] is False
    assert sec_a["tools"]["dustmasker"]["tool_version"] == "1.0.0"
    assert sec_a["tools"]["dustmasker"]["tool_version_compared_with_receipt"] is False
    assert sec_a["tools"]["blastn"]["tool_version"] == "2.17.0+"
    for tool in cal.E05_REQUIRED_TOOLS:
        assert sec_a["tools"][tool]["package_build"] == "blast 2.17.0, build Aug 22 2026 11:52:50"
        assert sec_a["tools"][tool]["executable_sha256"] == _sha256_raw(f"ELF_BINARY_{tool}".encode("ascii"))
    covered = sec_b["receipt_coverage_declaration"]
    assert any("blastn" in item and "dustmasker" in item for item in covered["not_covered_by_database_build_receipts"])

    missing = _e05_inspect(env, which_resolver=lambda name: None if name == "dustmasker" else env["fake_which"](name))
    dm = missing["a_observed_tool_builds"]["tools"]["dustmasker"]
    assert missing["a_observed_tool_builds"]["all_five_tools_observed"] is False
    assert missing["b_build_comparison_with_cp1_receipts_and_derivations"]["equivalent_build_reuse_blocked"] is True
    assert (dm["status"], dm["tool_version"], dm["package_build"], dm["executable_sha256"]) == ("NOT_APPLICABLE",) * 4
    assert "not found in PATH" in dm["applicability_justification"]

    def divergent_runner(cmd, **kwargs):
        if cmd[1] == "-version":
            out = f"{Path(cmd[0]).name}: 2.16.0+\n Package: blast 2.16.0, build Jan 10 2025 00:00:00\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        return env["fake_e05_runner"](cmd, **kwargs)

    divergent = _e05_inspect(env, runner=divergent_runner)["b_build_comparison_with_cp1_receipts_and_derivations"]
    assert divergent["comparison_status"] == "BUILD_DIVERGENCE_DETECTED_REUSE_BLOCKED"
    assert divergent["equivalent_build_reuse_blocked"] is True
    assert len(divergent["reuse_block_reasons"]) == 5

    # dustmasker is versioned independently: another tool_version under the same package build still matches.
    def other_dustmasker_version(cmd, **kwargs):
        if cmd[1] == "-version" and Path(cmd[0]).name == "dustmasker":
            return subprocess.CompletedProcess(cmd, 0, stdout="dustmasker: 1.2.3\n Package: blast 2.17.0, build Aug 22 2026 11:52:50\n", stderr="")
        return env["fake_e05_runner"](cmd, **kwargs)

    assert _e05_inspect(env, runner=other_dustmasker_version)["b_build_comparison_with_cp1_receipts_and_derivations"]["equivalent_build_reuse_blocked"] is False

    # A tool whose -help fails is NOT_APPLICABLE, never a pass.
    def broken_help(cmd, **kwargs):
        if cmd[1] == "-help" and Path(cmd[0]).name == "blast_formatter":
            return subprocess.CompletedProcess(cmd, 3, stdout="", stderr="boom")
        return env["fake_e05_runner"](cmd, **kwargs)

    broken = _e05_inspect(env, runner=broken_help)
    assert broken["a_observed_tool_builds"]["tools"]["blast_formatter"]["status"] == "NOT_APPLICABLE"
    assert broken["d_output_integrity_mechanism"]["selected_mechanism"] == "INSUFFICIENT_BUILD_SUPPORT_QA_I_PENDING"


def test_e05_parameter_matrix_defaults_pending_values_exclusions_and_coordinator_decisions(synthetic_e05_env):
    """31 parameters: documented vs undocumented defaults, no value for G1_AFTER_CALIBRATION, verbatim exclusion reasons."""
    insp = _e05_inspect(synthetic_e05_env)
    sec_c = insp["c_parameter_matrix_inspection"]
    params = sec_c["parameters"]
    assert len(params) == 31 and sec_c["total_parameters"] == 31
    assert sec_c["counts"]["by_decision_stage"] == {
        "ARCHITECTURAL_PRE_G1": 8, "EXCLUDED_BY_ARCHITECTURE": 7, "G1_AFTER_CALIBRATION": 9,
        "G1_RECORD_EXPLICITLY": 6, "QA_ONLY_PLUS_G1_PRODUCTION_DECISION": 1,
    }

    # Defaults come from the help text, and are NOT_DOCUMENTED_IN_BUILD_HELP otherwise.
    documented = {
        "P02": "Default = `megablast'", "P04": "Default = 10 (1000 for blastn-short)",
        "P09": "Default = '20 64 1' ('no' for blastn-short)", "P10": "Default = `true'", "P12": "Default = `both'",
        "P13": "Default = `500'", "P26": "Default = `0'", "P27": "Default = `1'", "P29": "Default = `3GB'",
    }
    for pid, text in documented.items():
        assert params[pid]["documented_default_in_build_help"] == text
    assert params["P28"]["documented_default_in_build_help"].startswith("PARTIAL_BY_FLAG:")
    assert sec_c["parameters_without_documented_default"] == [
        "P01", "P03", "P05", "P06", "P07", "P08", "P11", "P14", "P15", "P16", "P17", "P18", "P19", "P20",
        "P21", "P22", "P23", "P24", "P25", "P30", "P31",
    ]
    assert params["P25"]["per_flag_build_help"]["-sum_stats"]["present_in_build_help"] is False
    task = params["P02"]["task_default_observation"]
    assert task["documented_default_task"] == "megablast" and task["documented_default_task_is_admitted"] is False

    # A default that the help does not state is never completed from elsewhere.
    no_default = _e05_inspect(
        synthetic_e05_env,
        runner=lambda cmd, **kw: (
            subprocess.CompletedProcess(cmd, 0, stdout=synthetic_e05_env["help_map"]["blastn"].replace("   Default = `megablast'\n", ""), stderr="")
            if Path(cmd[0]).name == "blastn" and cmd[1] == "-help" else synthetic_e05_env["fake_e05_runner"](cmd, **kw)
        ),
    )
    assert no_default["c_parameter_matrix_inspection"]["parameters"]["P02"]["documented_default_in_build_help"] == "NOT_DOCUMENTED_IN_BUILD_HELP"

    # G1_AFTER_CALIBRATION: pending, no value, and a value is refused (P13 and P14 included).
    pending = ("P02", "P03", "P04", "P07", "P08", "P13", "P14", "P27", "P29")
    for pid in pending:
        assert (params[pid]["effective_value_state"], params[pid]["effective_value"]) == (cal.STATE_PENDING, None)
        mutated = json.loads(json.dumps(params))
        mutated[pid]["effective_value"] = 500
        with pytest.raises(r.ResourceContractError, match=rf"parameter {pid} is G1_AFTER_CALIBRATION"):
            cal.validate_e05_parameter_records(mutated)
    assert "reserved E02 decision" in params["P13"]["reserved_decision_note"]
    assert "reserved E02 decision" in params["P14"]["reserved_decision_note"]

    # G1_RECORD_EXPLICITLY: recorded, not decided.
    for pid in ("P05", "P06", "P10", "P21", "P22", "P25"):
        assert (params[pid]["effective_value_state"], params[pid]["effective_value"]) == (cal.STATE_RECORDED, None)
        mutated = json.loads(json.dumps(params))
        mutated[pid]["effective_value"] = 1
        with pytest.raises(r.ResourceContractError, match=rf"parameter {pid} is G1_RECORD_EXPLICITLY"):
            cal.validate_e05_parameter_records(mutated)

    # EXCLUDED_BY_ARCHITECTURE: unapplied, with the contractual reason copied verbatim, never one of the Programmer's.
    for pid in ("P15", "P16", "P17", "P18", "P19", "P20", "P24"):
        rec = params[pid]
        assert (rec["effective_value_state"], rec["effective_value"], rec["option_applied"]) == (cal.STATE_EXCLUDED, "OPTION_NOT_APPLIED", False)
        reason = rec["contractual_exclusion_reason"]
        assert reason["design_document_passage_verbatim"] == _E05_EXCLUDED_PASSAGE
        assert reason["matrix_failure_mode_verbatim"] == f"failure_mode_{pid}"
        assert reason["matrix_notes_verbatim"] == f"notes_{pid}"
        for broken in ({"contractual_exclusion_reason": None}, {"option_applied": True}, {"effective_value": "x"}):
            mutated = json.loads(json.dumps(params))
            mutated[pid].update(broken)
            with pytest.raises(r.ResourceContractError, match=rf"excluded parameter {pid} requires"):
                cal.validate_e05_parameter_records(mutated)

    # P30 and P23 apply the Coordinator decisions (coordination.md 20.8 and 20.9) and carry their reference.
    assert params["P30"]["effective_value"] == "ASCENDING_ASCII_DEFLINE_RECORD_ID_HASHED_WITH_DOWNSTREAM_HSP_TIE_SORT"
    assert params["P23"]["effective_value"]["primary_candidate_configurations"] == "NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET"
    assert params["P23"]["effective_value"]["production_policy"] == "PENDING_G1_DECISION"
    assert params["P23"]["effective_value"]["search_space_policy_token"].startswith("NATURAL_SEARCH_SPACE_IN_PRIMARY_CANDIDATES")
    for pid, section in (("P30", "20.8"), ("P23", "20.9")):
        decision = params[pid]["coordinator_decision"]
        assert (params[pid]["effective_value_state"], decision["decided_by"], decision["decision_section"]) == (cal.STATE_DECIDED, "IMPLEMENTATION_COORDINATOR", section)
        assert decision["decision_class"] == "ESTABLISHED_BY_CONTRACT_NOT_RESERVED"
        mutated = json.loads(json.dumps(params))
        del mutated[pid]["coordinator_decision"]
        with pytest.raises(r.ResourceContractError, match=rf"parameter {pid} must record the Coordinator decision"):
            cal.validate_e05_parameter_records(mutated)

    # P26 is a starting hypothesis: precedent + score; nident and qcovhsp available, NOT adopted.
    p26 = params["P26"]
    assert p26["effective_value_state"] == cal.STATE_HYPOTHESIS and p26["effective_value"]["field_order_closed"] is False
    assert p26["effective_value"]["adopted_specifiers_precedent_in_matrix_order"] == list(cal.E05_OUTFMT_6_PRECEDENT)
    assert p26["effective_value"]["adopted_specifiers_added_from_plan_section_8"] == ["score"]
    assert p26["effective_value"]["available_not_adopted"] == ["nident", "qcovhsp"]

    # Flags outside the 31-parameter matrix are an observation only.
    outside = sec_c["build_help_flags_outside_matrix"]
    assert outside["observation_only"] is True
    assert outside["flags_with_documented_default_by_tool"]["blastn"]["-off_diagonal_range"] == "Default = `0'"
    assert "-strand" not in outside["flags_with_documented_default_by_tool"]["blastn"]
    assert "-blastdb_version" in outside["flags_with_documented_default_by_tool"]["makeblastdb"]


def test_e05_matrix_text_is_checked_against_the_specification(synthetic_e05_env, monkeypatch):
    """A fixed-by-architecture value or the P26 precedent that differs from the matrix is refused."""
    with monkeypatch.context() as patch:
        patch.setitem(cal.E05_EFFECTIVE_VALUES, "P12", (cal.STATE_FIXED, "plus"))
        with pytest.raises(r.ResourceContractError, match="P12 value 'plus' differs from the matrix candidate_design_space"):
            _e05_inspect(synthetic_e05_env)
    with monkeypatch.context() as patch:
        swapped = (cal.E05_OUTFMT_6_PRECEDENT[1], cal.E05_OUTFMT_6_PRECEDENT[0]) + cal.E05_OUTFMT_6_PRECEDENT[2:]
        patch.setattr(cal, "E05_OUTFMT_6_PRECEDENT", swapped)
        with pytest.raises(r.ResourceContractError, match="P26 precedent specifiers differ"):
            _e05_inspect(synthetic_e05_env)


def test_e05_output_integrity_export_caps_and_qa_state(synthetic_e05_env):
    """Archive + blast_formatter mechanism, the export-path default caps, and 19 QA criteria without any metric."""
    env = synthetic_e05_env
    insp = _e05_inspect(env)
    sec_d = insp["d_output_integrity_mechanism"]
    assert sec_d["selected_mechanism"] == "IDENTIFIED_BLAST_ASN1_ARCHIVE_WITH_VERIFIABLE_BLAST_FORMATTER_TABULAR_EXPORT"
    assert sec_d["termination_marker_and_query_count_fallback_required"] is False
    assert sec_d["adopted_tabular_specifiers"] == list(cal.E05_OUTFMT_6_PRECEDENT + cal.E05_OUTFMT_6_ADDITIONS)
    assert sec_d["available_not_adopted_specifiers"] == {"nident": True, "qcovhsp": True}
    cap = sec_d["export_path_default_cap_observation"]
    assert cap["classification"] == "INSPECTION_OBSERVATION_WITH_CONDITION_TO_VERIFY"
    assert cap["blast_formatter_flags"]["-max_target_seqs"]["documented_default_in_build_help"] == "Default = `500'"
    assert cap["blast_formatter_flags"]["-num_descriptions"]["documented_default_in_build_help"] == "Default = `500'"
    assert cap["blast_formatter_flags"]["-num_alignments"]["documented_default_in_build_help"] == "Default = `250'"
    assert cap["blastn_search_stage_max_target_seqs"]["present_in_build_help"] is True
    assert "Truncation is not asserted" in cap["not_established"] and cap["destination"] == "E04 and E06"
    assert len(cap["conditions_to_verify"]) == 2 and "output_integrity_contract_id" in cap["payload_boundary"]
    joined = " ".join(cap["conditions_to_verify"])
    assert "loss of HSPs and loss of queries" in joined and "legitimately empty output" in joined and "line boundary" in joined
    assert "respects the constraints recorded above" in joined and "three parameters" not in joined
    assert cap["established"].startswith("The inspected blast_formatter help documents a default for -max_target_seqs, -num_descriptions, -num_alignments")

    # U03_S01: the narrative follows the evidence actually present in the help (no defaults; tool unavailable).
    no_defaults_help = "\n".join(l for l in env["help_map"]["blast_formatter"].splitlines() if "Default =" not in l) + "\n"
    absent_cap = _e05_inspect(env, runner=lambda cmd, **kw: (
        subprocess.CompletedProcess(cmd, 0, stdout=no_defaults_help, stderr="")
        if Path(cmd[0]).name == "blast_formatter" and cmd[1] == "-help" else env["fake_e05_runner"](cmd, **kw)
    ))["d_output_integrity_mechanism"]["export_path_default_cap_observation"]
    assert all(v["documented_default_in_build_help"] == "NOT_DOCUMENTED_IN_BUILD_HELP" for v in absent_cap["blast_formatter_flags"].values())
    assert absent_cap["established"] == "The inspected blast_formatter help documents no default for -max_target_seqs, -num_descriptions or -num_alignments."
    unavailable_cap = _e05_inspect(env, which_resolver=lambda name: None if name == "blast_formatter" else env["fake_which"](name))[
        "d_output_integrity_mechanism"]["export_path_default_cap_observation"]
    assert unavailable_cap["established"] == "blast_formatter help was not inspected; nothing is established about export-path default caps."
    partial_help = env["help_map"]["blast_formatter"].replace("   Default = `250'\n", "")
    partial_cap = _e05_inspect(env, runner=lambda cmd, **kw: (
        subprocess.CompletedProcess(cmd, 0, stdout=partial_help, stderr="")
        if Path(cmd[0]).name == "blast_formatter" and cmd[1] == "-help" else env["fake_e05_runner"](cmd, **kw)
    ))["d_output_integrity_mechanism"]["export_path_default_cap_observation"]
    assert partial_cap["established"].endswith("it documents none for -num_alignments.")

    # Without the archive input or an adopted specifier the mechanism is insufficient and QA-I stays pending.
    no_archive = _e05_inspect(env, runner=lambda cmd, **kw: (
        subprocess.CompletedProcess(cmd, 0, stdout=env["help_map"]["blast_formatter"].replace(" -archive <File_In>", " -arch <File_In>"), stderr="")
        if Path(cmd[0]).name == "blast_formatter" and cmd[1] == "-help" else env["fake_e05_runner"](cmd, **kw)
    ))["d_output_integrity_mechanism"]
    assert no_archive["selected_mechanism"] == "INSUFFICIENT_BUILD_SUPPORT_QA_I_PENDING"
    assert no_archive["qa_i_mechanism_status"] == "QA_I_PENDING_NO_SUFFICIENT_MECHANISM_CONFIRMED"
    no_score = _e05_inspect(env, runner=lambda cmd, **kw: (
        subprocess.CompletedProcess(cmd, 0, stdout=env["help_map"]["blastn"].replace("score means score", "scoreless means none"), stderr="")
        if Path(cmd[0]).name == "blastn" and cmd[1] == "-help" else env["fake_e05_runner"](cmd, **kw)
    ))["d_output_integrity_mechanism"]
    assert no_score["blastn_missing_adopted_specifiers"] == ["score"]
    assert no_score["selected_mechanism"] == "INSUFFICIENT_BUILD_SUPPORT_QA_I_PENDING"

    sec_e = insp["e_configuration_qa_matrix_status"]
    assert sec_e["total_criteria"] == 19
    assert (sec_e["preconditions_inspected_count"], sec_e["preconditions_not_inspected_count"]) == (11, 8)
    for qid, item in sec_e["criteria"].items():
        assert item["metric_computed_in_e05_part1"] is False and item["state_after_e05_part1"] == "NOT_TESTED"
    assert "verifiable_by_configuration_inspection_without_query" not in sec_e["criteria"]["QA-C"]
    # Only what was observed is stated; no universal impossibility is asserted (U03_F02).
    assert "no_qa_metric_computable_without_search" not in sec_e
    assert "no QA criterion was approved" in sec_e["observed_in_this_unit"]
    assert "does not assert which QA metrics are computable without a search" in sec_e["scope_qualification"]
    assert "structural" in sec_e["criteria"]["QA-P"]["precondition_note"] and "structural" in sec_e["criteria"]["QA-I"]["precondition_note"]
    current = {key: value for key, value in insp.items() if key != "coordinator_instruction_corrections"}
    assert not re.search(r"no QA metric .{0,40}computable", json.dumps(current), flags=re.IGNORECASE)
    notes = " ".join(c["precondition_note"] for c in sec_e["criteria"].values())
    assert not any(token in notes for token in ("Default", "500", "250", "megablast"))  # no build values in static text


def test_e05_canonical_record_order_is_computed_from_an_authenticated_geometry_record(synthetic_e05_env):
    """P30 check on an accepted record: identity-bound, content-checked against the manifest, order and cardinality computed."""
    sec_b = _e05_inspect(synthetic_e05_env)["b_build_comparison_with_cp1_receipts_and_derivations"]
    derivation = sec_b["current_e03_geometry_derivations"]["R1_RNA"]
    check = derivation["canonical_record_order_check"]
    assert derivation["status"] == "VERIFIED_AGAINST_ACCEPTED_RECORD_IDENTITY_AND_AUTHORITATIVE_CP1_MANIFEST"
    assert derivation["geometry_record_sha256"] == cal.EXPECTED_GEOMETRY_RECORD_SHA256["R1_RNA"]
    assert derivation["total_bases"] == 24
    assert check["strictly_ascending_ascii_record_id"] is True and check["ordered_record_id_count"] == 2
    assert check["ordered_record_id_count_matches_manifest_record_count"] is True and check["fasta_sha256"]


def test_u03_f01_adulterated_geometry_is_refused_not_promoted_to_verified(synthetic_e05_env, monkeypatch):
    """Reviewer counterexample (round 005): an adulterated geometry with a recomputed descriptor hash is refused."""
    root = synthetic_e05_env["root"]
    geom_path = root / "data/external/nto/cp1_20261015/geometry/R1_RNA.json"
    original = geom_path.read_bytes()
    accepted = dict(cal.EXPECTED_GEOMETRY_RECORD_SHA256)

    def rewrite(mutate):
        record = json.loads(original.decode("utf-8"))
        mutate(record)
        record["descriptor_sha256"] = cal.compute_geometry_descriptor_sha256(record["architecture_descriptor"])
        geom_path.write_bytes(r.json_bytes(record))

    def counterexample(record):  # +100 on the first length and on total_bases, ID list reduced to one element
        record["architecture_descriptor"]["ordered_record_lengths"][0] += 100
        record["architecture_descriptor"]["total_bases"] += 100
        record["canonical_order"]["ordered_analysis_ids"] = record["canonical_order"]["ordered_analysis_ids"][:1]
        record["canonical_order"]["ordered_source_ids"] = record["canonical_order"]["ordered_source_ids"][:1]

    def truncated_ids_only(record):  # descriptor untouched; only the ID list is incomplete
        record["canonical_order"]["ordered_analysis_ids"] = record["canonical_order"]["ordered_analysis_ids"][:1]

    def reversed_ids(record):
        record["canonical_order"]["ordered_analysis_ids"] = record["canonical_order"]["ordered_analysis_ids"][::-1]

    def lengths_swapped(record):  # same total, different vector
        lengths = record["architecture_descriptor"]["ordered_record_lengths"]
        lengths[0], lengths[1] = lengths[1], lengths[0]

    try:
        # Control 1: the whole-file identity refuses every mutation, even with a recomputed internal descriptor hash.
        for mutate in (counterexample, truncated_ids_only, reversed_ids, lengths_swapped):
            rewrite(mutate)
            with pytest.raises(r.ResourceContractError, match="E03 geometry record identity mismatch for R1_RNA"):
                _e05_inspect(synthetic_e05_env)
        # A wrongly anchored identity (the tampered file registered as accepted) is still caught by control 2,
        # which revalidates counts, totals, vectors and the ID list (order and cardinality) against the manifest.
        for mutate in (counterexample, truncated_ids_only, reversed_ids, lengths_swapped):
            rewrite(mutate)
            monkeypatch.setattr(cal, "EXPECTED_GEOMETRY_RECORD_SHA256", {"R1_RNA": _sha256_raw(geom_path.read_bytes())})
            with pytest.raises(r.ResourceContractError, match=r"inconsistent with the authoritative (CP1 manifest|identifier map) for R1_RNA"):
                _e05_inspect(synthetic_e05_env)
        # No accepted identity for a resource: not consumed as verified.
        geom_path.write_bytes(original)
        monkeypatch.setattr(cal, "EXPECTED_GEOMETRY_RECORD_SHA256", {})
        with pytest.raises(r.ResourceContractError, match="no accepted E03 geometry record identity for R1_RNA"):
            _e05_inspect(synthetic_e05_env)
        # The unmodified accepted record is still verified, and an absent record is NOT_MATERIALIZED, never verified.
        monkeypatch.setattr(cal, "EXPECTED_GEOMETRY_RECORD_SHA256", accepted)
        assert _e05_inspect(synthetic_e05_env)["b_build_comparison_with_cp1_receipts_and_derivations"][
            "current_e03_geometry_derivations"]["R1_RNA"]["total_bases"] == 24
        geom_path.unlink()
        with pytest.raises(r.ResourceContractError, match="required E03 geometry record missing for R1_RNA"):
            _e05_inspect(synthetic_e05_env)
        absent = _e05_inspect(synthetic_e05_env, require_e03_geometry=False)
        assert absent["b_build_comparison_with_cp1_receipts_and_derivations"]["current_e03_geometry_derivations"]["R1_RNA"] == {
            "geometry_record_path": "data/external/nto/cp1_20261015/geometry/R1_RNA.json", "status": "NOT_MATERIALIZED"}
    finally:
        geom_path.write_bytes(original)
    assert _sha256_raw(geom_path.read_bytes()) == accepted["R1_RNA"]


def test_u03_s02_receipt_provenance_of_max_file_size_is_structured(synthetic_e05_env):
    """P29 stays pending; the historical size limit is recorded as reported by makeblastdb, not as a passed flag."""
    section = _e05_inspect(synthetic_e05_env)["b_build_comparison_with_cp1_receipts_and_derivations"]["historical_makeblastdb_receipt_options"]
    assert section["p29_status"] == "PENDING_NO_VALUE_ASSIGNED" and "must not be promoted" in section["statement"]
    assert set(section["receipts_by_resource"]) == {"R1_RNA"}
    assert cal._receipt_max_file_size({"command": ["makeblastdb", "-dbtype", "nucl"], "stdout": "Maximum file size: 3000000000B\n"}) == {
        "max_file_sz_flag_passed_in_recorded_command": False, "stdout_reported_maximum_file_size_bytes": 3000000000}
    assert cal._receipt_max_file_size({"command": ["makeblastdb", "-max_file_sz", "1GB"], "stdout": ""}) == {
        "max_file_sz_flag_passed_in_recorded_command": True, "stdout_reported_maximum_file_size_bytes": None}
    assert cal._receipt_max_file_size({}) == {"max_file_sz_flag_passed_in_recorded_command": False, "stdout_reported_maximum_file_size_bytes": None}


def test_u03_coordinator_instruction_corrections_and_p30_classification_are_recorded(synthetic_e05_env):
    insp = _e05_inspect(synthetic_e05_env)
    ids = [item["correction_id"] for item in insp["coordinator_instruction_corrections"]]
    assert ids == [
        "COORDINATOR_ERROR_1_QA_METRIC_COMPUTABILITY",
        "COORDINATOR_ERROR_2_EXPORT_COMMAND_THREE_PARAMETERS",
        "COORDINATOR_ERROR_3_EXPORT_INTEGRITY_ONLY_SUBJECT_COUNT",
    ]
    p30 = insp["c_parameter_matrix_inspection"]["parameters"]["P30"]["coordinator_decision"]
    assert p30["classification_basis"].startswith("Conformance to the contract plus technical instantiation")


def test_e05_destination_protection_determinism_and_cli(synthetic_e05_env, monkeypatch, capsys):
    """Protected or pre-existing destinations are refused before any write; bytes are deterministic; CLI works once."""
    import importlib.util

    env = synthetic_e05_env
    root, ext_dir = env["root"], env["corpus_dirs"]["NB04_B5_INPUTS"]
    payload_a, payload_b = _e05_inspect(env), _e05_inspect(env)
    bytes_a = r.json_bytes(payload_a)
    assert bytes_a == r.json_bytes(payload_b)
    for marker in (b"external_corpora", b"fake_bin", b"/home/", b"/mnt/"):
        assert marker not in bytes_a

    victim = root / "config/frozen.tsv"
    before = victim.read_bytes()
    with pytest.raises(r.ResourceContractError, match="outside authorized directory"):
        cal.write_e05_configuration_inspection(root, payload_a, destination=victim)
    assert victim.read_bytes() == before
    reserved = root / cal.E05_U04_RESERVED_PATH
    with pytest.raises(r.ResourceContractError, match="reserved for U04"):
        cal.validate_e05_inspection_destination(root, reserved)
    assert not reserved.exists()
    inventory = _put(root / "artifacts/validation/nb04_cp1_prefreeze/20261025T070000Z/preservation_inventory.json", b'{"inventory":true}\n')
    with pytest.raises(r.ResourceContractError, match="must not target a preservation inventory"):
        cal.write_e05_configuration_inspection(root, payload_a, destination=inventory)
    assert inventory.read_bytes() == b'{"inventory":true}\n'
    with pytest.raises(r.ResourceContractError, match="outside project root"):
        cal.validate_e05_inspection_destination(root, root.parent / "escape_e05.json")
    invalid = json.loads(json.dumps(payload_a))
    invalid["c_parameter_matrix_inspection"]["parameters"]["P13"]["effective_value"] = 500
    with pytest.raises(r.ResourceContractError, match="parameter P13 is G1_AFTER_CALIBRATION"):
        cal.write_e05_configuration_inspection(root, invalid)
    assert not (root / cal.E05_INSPECTION_DEFAULT_PATH).exists()

    spec = importlib.util.spec_from_file_location("prepare_nb04_calibration", Path(__file__).resolve().parents[1] / "scripts" / "prepare_nb04_calibration.py")
    cli = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cli)
    original_build = cal.build_e05_configuration_inspection
    monkeypatch.setattr(cal, "build_e05_configuration_inspection", lambda rt, cd, **kw: original_build(
        rt, cd, which_resolver=env["fake_which"], runner=env["fake_e05_runner"], expected_resource_count=1, **kw))
    argv = ["e05", "--root", str(root), "--corpus", f"NB04_B5_INPUTS={ext_dir}"]
    assert cli.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "NB04_CP1_E05_PART_1" and out["inspection_artifact_path"] == cal.E05_INSPECTION_DEFAULT_PATH
    assert out["searches_executed"] is False and out["queries_executed"] is False
    assert (root / cal.E05_INSPECTION_DEFAULT_PATH).read_bytes() == bytes_a
    with pytest.raises(r.ResourceContractError, match="never be overwritten"):
        cli.main(argv)


def test_e05_parser_and_mechanism_against_the_real_pinned_build_help():
    """Runs only `-version` and `-help` of the real tools; SKIPPED (never passed) when the pinned build is absent."""
    tools = {name: cal._default_tool_which(name) for name in ("blastn", "blast_formatter")}
    absent = [name for name, path in tools.items() if path is None]
    if absent:
        pytest.skip(f"real BLAST+ tools not available in this environment: {absent}")

    def run(tool, flag):
        done = subprocess.run([tools[tool], flag], capture_output=True, text=True, timeout=30, check=False)
        assert done.returncode == 0
        return done.stdout.replace("\r\n", "\n")

    if "2.17.0+" not in run("blastn", "-version"):
        pytest.skip("real BLAST+ build is not the pinned 2.17.0+; facts below were observed on that build")
    helps = {tool: run(tool, "-help") for tool in tools}
    blastn, formatter = cal.parse_blast_help_flags(helps["blastn"]), cal.parse_blast_help_flags(helps["blast_formatter"])
    assert blastn["-task"]["documented_default_in_build_help"] == "Default = `megablast'"
    assert blastn["-max_target_seqs"]["documented_default_in_build_help"] == "Default = `500'"
    assert blastn["-max_hsps"]["documented_default_in_build_help"] == "NOT_DOCUMENTED_IN_BUILD_HELP"
    assert "-sum_stats" not in blastn
    assert formatter["-max_target_seqs"]["documented_default_in_build_help"] == "Default = `500'"
    assert formatter["-num_descriptions"]["documented_default_in_build_help"] == "Default = `500'"
    assert formatter["-num_alignments"]["documented_default_in_build_help"] == "Default = `250'"
    mechanism = cal.inspect_e05_output_integrity_mechanism(
        {"blastn": {"status": "OBSERVED"}, "blast_formatter": {"status": "OBSERVED"}}, helps)
    assert mechanism["selected_mechanism"] == "IDENTIFIED_BLAST_ASN1_ARCHIVE_WITH_VERIFIABLE_BLAST_FORMATTER_TABULAR_EXPORT"
    assert mechanism["available_not_adopted_specifiers"] == {"nident": True, "qcovhsp": True}

# Section 7 tests use declared scalar inputs and simulated metadata, with no search-recovery information.
def _section7_test_payload():
    search = {name: "OPTION_NOT_APPLIED" for name in cal.E05_SECTION7_SEARCH_FIELDS}
    search.update(task="blastn", word_size=11, evalue_reporting_limit=10.0, reward=2, penalty=-3,
                  gapopen=5, gapextend=2, dust="no", soft_masking="false", lcase_masking="false",
                  strand="both", max_target_seqs=100, num_threads=1)
    return {
        "schema_version": 1,
        "tool_build": {name: {"tool_name": name, "tool_version": "TEST_ONLY", "package_build": "TEST_ONLY",
                              "executable_sha256": "a" * 64} for name in cal.E05_SECTION7_KEYS["tool_build"]},
        "search_parameters": search,
        "database_build": {"dbtype": "nucl", "parse_seqids": True, "blastdb_version": 5,
                           "max_file_sz_effective": 1000, "volume_strategy": "TEST_ONLY",
                           "taxid_policy": "OMIT_FOR_SYNTHETIC_NO_TAXONOMIC_FILTER"},
        "execution_architecture": {
            "strategy": "TEST_ONLY", "canonical_record_order_rule": cal.E05_P30_RULE_TOKEN,
            "qa_sharding_rule": "TEST_ONLY", "qa_shard_count": 2,
            "outfmt_fields": list(cal.E05_OUTFMT_6_PRECEDENT + cal.E05_OUTFMT_6_ADDITIONS),
            "authoritative_output_format": "11", "parser_contract_id": "SYNTHETIC_TEST_ONLY",
            "parser_implementation_sha256": "b" * 64, "output_integrity_contract_id": "SYNTHETIC_TEST_ONLY"},
        "technical_domain": {"modality": "LOCAL_ALIGNMENT_CANONICAL", "analysis_role": "CALIBRATION",
            "resource_geometry_cells": [{"total_bases": 7, "record_count": 2, "descriptor_sha256": "c" * 64,
                                         "database_volume_count": 1}],
            "applicability_limitations": ["SYNTHETIC_SOFTWARE_TEST_ONLY"]}}


def _section7_test_declarations(payload):
    rows, records = {}, {}
    for pid in cal.E05_PARAMETER_IDS:
        rows[pid] = {"status": f"verbatim status {pid}", "candidate_design_space": f"verbatim space {pid}; unchanged"}
        values = {}
        for path in cal.E05_SECTION7_PARAMETER_PATHS[pid]:
            section, field = path.split(".")
            values[path] = payload[section][field]
        records[pid] = {"effective_value_state": "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE", "effective_value": values}
    return rows, records


def test_section7_literal_schema_and_every_key_boundary():
    payload = _section7_test_payload()
    assert cal.E05_SECTION7_SEARCH_FIELDS == (
        "task", "word_size", "evalue_reporting_limit", "reward", "penalty", "gapopen", "gapextend", "dust",
        "soft_masking", "lcase_masking", "strand", "max_target_seqs", "max_hsps", "perc_identity", "qcov_hsp_perc",
        "culling_limit", "best_hit_overhang", "best_hit_score_edge", "subject_besthit", "xdrop_ungap", "xdrop_gap",
        "xdrop_gap_final", "window_size", "dbsize", "searchsp", "ungapped", "sum_stats", "num_threads")
    cal.validate_section7_payload(payload)
    paths = [()] + [(name,) for name in cal.E05_SECTION7_KEYS]
    paths += [("tool_build", name) for name in payload["tool_build"]]
    paths += [("technical_domain", "resource_geometry_cells", 0)]
    for path in paths:
        obj = payload
        for part in path:
            obj = obj[part]
        for key in tuple(obj):
            for rename in (False, True):
                mutated = json.loads(r.json_bytes(payload))
                target = mutated
                for part in path:
                    target = target[part]
                value = target.pop(key)
                if rename:
                    target[key + "_renamed"] = value
                with pytest.raises(r.ResourceContractError, match="keys differ"):
                    cal.validate_section7_payload(mutated, allow_unresolved=True)
        for forbidden in ("free_name", "administrative_id", "notes", "date", "local_path", "discovery_order", "results", "observed_metrics", "production_partition_plan"):
            mutated = json.loads(r.json_bytes(payload))
            target = mutated
            for part in path:
                target = target[part]
            target[forbidden] = "forbidden envelope metadata"
            with pytest.raises(r.ResourceContractError, match="keys differ"):
                cal.validate_section7_payload(mutated, allow_unresolved=True)


@pytest.mark.parametrize("section,field,value", [
    ("search_parameters", "task", "megablast"),
    ("search_parameters", "max_target_seqs", "OPTION_NOT_APPLIED"),
    ("search_parameters", "word_size", True),
    ("search_parameters", "word_size", "PENDING_CALIBRATION"),
    ("search_parameters", "evalue_reporting_limit", float("nan")),
    ("search_parameters", "evalue_reporting_limit", float("inf")),
    ("execution_architecture", "outfmt_fields", [{"notes": "metadata"}]),
    ("execution_architecture", "outfmt_fields", ["qseqid", "qseqid"]),
    ("execution_architecture", "parser_contract_id", "/tmp/local-contract"),
    ("execution_architecture", "qa_shard_count", 3),
    ("database_build", "taxid_policy", "ARBITRARY_TAXID"),
])
def test_section7_value_shapes_reject_unresolved_and_nontechnical_values(section, field, value):
    payload = _section7_test_payload()
    payload[section][field] = value
    with pytest.raises(r.ResourceContractError):
        cal.validate_section7_payload(payload)


def test_section7_serialization_hash_and_open_identity_barrier(monkeypatch):
    payload = _section7_test_payload()
    original = r.json_bytes
    calls = []
    monkeypatch.setattr(cal, "json_bytes", lambda obj: (calls.append(obj), original(obj))[1])
    raw = cal.section7_payload_bytes(payload)
    assert raw == original(payload) and raw.endswith(b"\n") and b"\r\n" not in raw
    assert cal.section7_payload_sha256(payload) == hashlib.sha256(raw).hexdigest()
    assert len(calls) == 2
    payload["search_parameters"]["word_size"] = None
    cal.validate_section7_payload(payload, allow_unresolved=True)
    for operation in (cal.section7_payload_bytes, cal.section7_payload_sha256, lambda p: cal.order_section7_payloads({"draft": p})):
        with pytest.raises(r.ResourceContractError):
            operation(payload)


def test_section7_full_hash_order_aliases_threads_build_and_collisions():
    first = _section7_test_payload()
    second = json.loads(r.json_bytes(first))
    second["search_parameters"]["num_threads"] = 2
    third = json.loads(r.json_bytes(first))
    third["tool_build"]["blastn"]["package_build"] = "OTHER_TEST_BUILD"
    # The entire prefix agrees. Alias order and input order deliberately oppose the digest suffix order.
    hashes = {1: "a" * 63 + "f", 2: "a" * 63 + "0"}
    ordered = cal.order_section7_payloads({"a": first, "z": second, "alias": json.loads(r.json_bytes(first))},
        hash_function=lambda raw: hashes[json.loads(raw)["search_parameters"]["num_threads"]])
    assert [entry["payload_sha256"] for entry in ordered] == [hashes[2], hashes[1]]
    assert ordered[1]["aliases"] == ["a", "alias"]
    real = cal.order_section7_payloads({"first": first, "threads": second, "build": third})
    assert len(real) == 3 and [e["payload_sha256"] for e in real] == sorted(cal.section7_payload_sha256(p) for p in (first, second, third))
    with pytest.raises(r.ResourceContractError, match="collision"):
        cal.order_section7_payloads({"first": first, "threads": second}, hash_function=lambda raw: "0" * 64)


def test_section7_closure_requires_declarations_and_every_required_field():
    payload = _section7_test_payload()
    rows, records = _section7_test_declarations(payload)
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"
    for field in cal.E05_SECTION7_SEARCH_FIELDS:
        pid = next(pid for pid, paths in cal.E05_SECTION7_PARAMETER_PATHS.items() if f"search_parameters.{field}" in paths)
        for missing in (False, True):
            draft = json.loads(r.json_bytes(payload))
            if missing:
                del draft["search_parameters"][field]
            else:
                draft["search_parameters"][field] = None
            result = cal.evaluate_section7_closure(draft, rows, records)
            assert result["state"] == "OPEN"
            blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == pid)
            assert blocker["status"] == rows[pid]["status"]
            assert blocker["candidate_design_space"] == rows[pid]["candidate_design_space"]
    for pid in cal.E05_PARAMETER_IDS:
        missing_record = dict(records)
        del missing_record[pid]
        assert pid in [b["parameter_id"] for b in cal.evaluate_section7_closure(payload, rows, missing_record)["blocking_parameters"]]
    records["P26"]["effective_value_state"] = cal.STATE_HYPOTHESIS
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "OPEN"
    rows, records = _section7_test_declarations(payload)
    records["P13"] = {"effective_value_state": cal.STATE_PENDING, "effective_value": None}
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "OPEN"
    rows, records = _section7_test_declarations(payload)
    records["P13"]["effective_value"]["search_parameters.max_target_seqs"] += 1
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "OPEN"
    for field in cal.E05_SECTION7_CELL_FIELDS:
        malformed = json.loads(r.json_bytes(payload))
        del malformed["technical_domain"]["resource_geometry_cells"][0][field]
        malformed_rows, malformed_records = _section7_test_declarations(malformed)
        result = cal.evaluate_section7_closure(malformed, malformed_rows, malformed_records)
        assert result["state"] == "OPEN"
        assert "P29" in [b["parameter_id"] for b in result["blocking_parameters"]]
        assert f"technical_domain.resource_geometry_cells[0].{field}" in result["unresolved_payload_fields"]
    rows, records = _section7_test_declarations(payload)
    candidates = [{"payload": payload, "parameter_records": records}]
    assert cal.evaluate_section7_candidate_set(candidates, rows)["state"] == "OPEN"
    assert cal.evaluate_section7_candidate_set([], rows, design_space_declaration="TEST_ONLY")["state"] == "OPEN"
    assert cal.evaluate_section7_candidate_set(candidates, rows, design_space_declaration="TEST_ONLY")["state"] == "CLOSED"
    payload["execution_architecture"]["parser_contract_id"] = None
    assert cal.evaluate_section7_candidate_set(candidates, rows, design_space_declaration="TEST_ONLY")["state"] == "OPEN"


def test_section7_volume_enumeration_cross_checks_metadata_without_queries(tmp_path):
    prefix = tmp_path / "db" / "sequences"
    for volume in ("sequences.00", "sequences.01"):
        for suffix in (".nin", ".nhr", ".nsq"):
            _put(prefix.with_name(volume + suffix), b"constructed metadata-test component")
    resource = {"database_prefix": "db/sequences", "quality": {"record_count": 2, "total_bases": 7}}
    stdout = f"Database: TEST\n2 sequences; 7 total bases\nBLASTDB Version: 5\nVolumes:\n{prefix}.00\n{prefix}.01\n"
    calls = []
    def runner(command, **kwargs):
        assert command == ["SIMULATED", "-db", str(prefix), "-dbtype", "nucl", "-info"]
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
    result = cal.inspect_section7_database_volumes(tmp_path, resource, executable="SIMULATED", runner=runner)
    assert result["database_volume_count"] == 2 and len(calls) == 1
    for corrupted in (stdout.replace("sequences.01", "sequences.02"), stdout.replace("2 sequences", "3 sequences"), stdout.replace("BLASTDB Version: 5", "")):
        with pytest.raises(r.ResourceContractError):
            cal.inspect_section7_database_volumes(tmp_path, resource, runner=lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout=corrupted, stderr=""))
    with pytest.raises(r.ResourceContractError, match="metadata failed"):
        cal.inspect_section7_database_volumes(tmp_path, resource, runner=lambda *a, **k: subprocess.CompletedProcess(a[0], 1, stdout="", stderr="simulated failure"))
    prefix.with_name("sequences.01.nhr").unlink()
    with pytest.raises(r.ResourceContractError, match="components incomplete"):
        cal.inspect_section7_database_volumes(tmp_path, resource, runner=lambda *a, **k: pytest.fail("engine must not be invoked"))


def test_section7_preparation_integrates_authenticated_geometry_and_keeps_drafts_open(synthetic_e05_env, monkeypatch):
    env = synthetic_e05_env
    root = env["root"]
    inspection = _e05_inspect(env)
    path = _put(root / cal.E05_U03_R3_PATH, r.json_bytes(inspection))
    monkeypatch.setattr(cal, "E05_U03_R3_SHA256", _sha256_raw(path.read_bytes()))
    manifest = json.loads((root / r.MANIFEST).read_text())
    resource = manifest["resources"][0]
    receipt_path = (root / resource["fasta_path"]).with_name("database_build.json")
    receipt = json.loads(receipt_path.read_text())
    receipt["command"] = ["makeblastdb", "-dbtype", "nucl", "-parse_seqids", "-blastdb_version", "5", "-taxid", str(resource["taxid"])]
    receipt["stdout"] = "Maximum file size: 3000000000B\n"
    _put((root / resource["database_prefix"]).with_suffix(".nhr"), b"constructed header component")
    r.write_json(receipt_path, receipt)
    resource["artifacts_sha256"][receipt_path.relative_to(root).as_posix()] = _sha256_raw(receipt_path.read_bytes())
    r.write_json(root / r.MANIFEST, manifest)
    monkeypatch.setattr(cal, "REAL_CP1_MANIFEST_SHA256", _sha256_raw((root / r.MANIFEST).read_bytes()))
    starts = ("O descritor delimita arquitetura", "Registrar ENVELOPE_GEOMETRY_ONLY", "Magnitude aritmética de escala", "Simplificação S05", "OBSERVATION. Os seis database_build.json", "E01 e E05 compararão", "O caminho de código de fixtures", "A arquitetura preferida é um banco")
    plan = _put(root / cal.PLAN_V003_PATH, "\n\n".join(s + " SYNTHETIC TEST ONLY." for s in starts).encode())
    monkeypatch.setattr(cal, "PLAN_V003_SHA256", _sha256_raw(plan.read_bytes()))
    original_geometry = cal._e05_geometry_derivations
    geometry_calls = []
    def geometry(*args):
        assert args[3] is True and args[4] == cal.EXPECTED_GEOMETRY_RECORD_SHA256
        geometry_calls.append(args)
        return original_geometry(*args)
    monkeypatch.setattr(cal, "_e05_geometry_derivations", geometry)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        assert path.name != "normalized.fasta", "U04 must not read FASTA"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    def runner(command, **kwargs):
        assert command[1:] == ["-db", str(root / resource["database_prefix"]), "-dbtype", "nucl", "-info"]
        return subprocess.CompletedProcess(command, 0, stdout="Database: TEST\n2 sequences; 24 total bases\nBLASTDB Version: 5\nVolumes:\nsequences\n", stderr="")
    _put(root / "src/zeaguard/nb04_calibration.py", b"# directly constructed implementation identity input\n")
    result = cal.build_e05_section7_preparation(root, env["corpus_dirs"]["NB04_B5_INPUTS"],
        accepted_geometry_record_sha256=cal.EXPECTED_GEOMETRY_RECORD_SHA256, runner=runner, which_resolver=env["fake_which"])
    assert len(geometry_calls) == 1
    assert result["state"] == "OPEN" and result["design_space_complete"] is False
    assert result["candidate_set_closure"]["state"] == "OPEN"
    assert result["qa_i_parser_precondition"]["state"] == "NOT_TESTED"
    assert result["prospective_dependencies"]["producer_lexical_format"] == "APPLICABLE_PINNED_BUILD_FORMAT_EVIDENCE_BEFORE_CAMPAIGN_USE"
    assert result["qa_i_parser_precondition"]["campaign_qa_approved"] is False
    identity = cal.nb04_parser_implementation_identity(root)
    assert result["determinate_sections"]["execution_architecture"]["parser_implementation_sha256"] == identity["parser_implementation_sha256"]
    assert result["provenance"]["parser_implementation"] == identity
    assert result["closure_scope"] == "COMPUTATIONAL_PREDICATES_ON_SUPPLIED_DECLARATIONS"
    assert result["authority_verification"] == "EXTERNAL_DOCUMENTARY_E02_E03_REQUIRED"
    assert result["g1_certification"] == "NOT_EVALUATED"
    assert result["determinate_sections"]["tool_build"]["dustmasker"]["tool_version"] == "1.0.0"
    assert result["determinate_sections"]["database_build"]["max_file_sz_effective"] == 3000000000
    assert result["determinate_sections"]["execution_architecture"]["outfmt_fields"] == list(cal.E05_OUTFMT_6_PRECEDENT + cal.E05_OUTFMT_6_ADDITIONS)
    assert "low_complexity_overlap_fraction" in result["prospective_dependencies"]["derived_fields_E04_E06"]
    evidence = result["provenance"]["historical_database_build"]["R1_RNA"]
    assert evidence["max_file_sz_flag_passed_in_recorded_command"] is False
    assert evidence["max_file_sz_origin"] == "ENGINE_DEFAULT_REPORTED_IN_RECEIPT_STDOUT"
    assert [s["task"] for s in result["candidate_skeletons"]] == ["blastn", "blastn-short", "dc-megablast"]
    before = r.json_bytes(inspection["c_parameter_matrix_inspection"]["parameters"])
    for skeleton in result["candidate_skeletons"]:
        assert skeleton["task_flag_explicit"] is True and skeleton["payload"]["search_parameters"]["task"] == skeleton["task"]
        assert skeleton["closure"]["state"] == "OPEN" and "payload_sha256" not in skeleton
        assert skeleton["payload"]["database_build"]["max_file_sz_effective"] is None
        assert skeleton["payload"]["database_build"]["taxid_policy"] == "OMIT_FOR_SYNTHETIC_NO_TAXONOMIC_FILTER"
        blocked = {b["parameter_id"] for b in skeleton["closure"]["blocking_parameters"]}
        assert {"P02", "P03", "P04", "P07", "P08", "P13", "P14", "P27", "P29", "P31"} <= blocked
        assert skeleton["payload"]["execution_architecture"]["parser_contract_id"] is None
    assert before == r.json_bytes(inspection["c_parameter_matrix_inspection"]["parameters"])
    with pytest.raises(r.ResourceContractError, match="identity differs"):
        monkeypatch.setattr(cal, "E05_U03_R3_SHA256", "0" * 64)
        cal.build_e05_section7_preparation(root, env["corpus_dirs"]["NB04_B5_INPUTS"], accepted_geometry_record_sha256=cal.EXPECTED_GEOMETRY_RECORD_SHA256)

@pytest.mark.parametrize("state", [cal.STATE_FIXED, cal.STATE_EXCLUDED, cal.STATE_DECIDED, "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE"])
def test_u04_f01_all_accepted_states_compare_every_parameter_path(state):
    payload = _section7_test_payload()
    rows, original = _section7_test_declarations(payload)
    for pid, paths in cal.E05_SECTION7_PARAMETER_PATHS.items():
        records = json.loads(r.json_bytes(original))
        records[pid]["effective_value_state"] = state
        assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"
        for path in paths:
            bad = json.loads(r.json_bytes(records))
            bad[pid]["effective_value"][path] = "CONTRADICTS_PAYLOAD"
            result = cal.evaluate_section7_closure(payload, rows, bad)
            assert result["state"] == "OPEN"
            blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == pid)
            assert path in blocker["declaration_mismatch_fields"]
            assert blocker["declaration_error"] == "DECLARATION_PAYLOAD_MISMATCH"
        for value in ("CONTRADICTS_PAYLOAD", {}):
            bad = json.loads(r.json_bytes(records))
            bad[pid]["effective_value"] = value
            result = cal.evaluate_section7_closure(payload, rows, bad)
            assert result["state"] == "OPEN"
            blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == pid)
            assert blocker["declaration_error"]


def test_u04_f01_translates_only_unambiguous_legacy_declarations():
    payload = _section7_test_payload()
    rows, records = _section7_test_declarations(payload)
    records["P01"] = {"effective_value_state": cal.STATE_FIXED, "effective_value": "blastn"}
    records["P09"] = {"effective_value_state": cal.STATE_FIXED, "effective_value": "no"}
    records["P15"] = {"effective_value_state": cal.STATE_EXCLUDED, "effective_value": "OPTION_NOT_APPLIED"}
    records["P30"] = {"effective_value_state": cal.STATE_DECIDED, "effective_value": cal.E05_P30_RULE_TOKEN}
    records["P23"] = {"effective_value_state": cal.STATE_DECIDED, "effective_value": dict(cal.E05_P23_EFFECTIVE_VALUE)}
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"
    for field in cal.E05_P23_EFFECTIVE_VALUE:
        bad = json.loads(r.json_bytes(records))
        bad["P23"]["effective_value"][field] = "CONTRADICTS_PAYLOAD"
        result = cal.evaluate_section7_closure(payload, rows, bad)
        assert result["state"] == "OPEN"
        blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == "P23")
        assert blocker["declaration_error"] == "DECLARATION_REPRESENTATION_INCOMPLETE_OR_UNSUPPORTED"


@pytest.mark.parametrize("marker", [
    "NORMATIVE_BINDING_NOT_ESTABLISHED", "IMPLEMENTATION_NOT_ESTABLISHED", "NOT_APPLICABLE", "G1_NOT_EVALUATED",
    "NOT_ESTABLISHED", "NOT_ESTABLISHED_SUFFIX", "X_NOT_ESTABLISHED_SUFFIX", "PENDING_CALIBRATION",
    "X_PENDING", "X_PENDING_SUFFIX", "NOT_MATERIALIZED", "GEOMETRY_NOT_MATERIALIZED",
    "GEOMETRY_NOT_MATERIALIZED_SUFFIX", "UNRESOLVED", "X_UNRESOLVED_SUFFIX", "X_NOT_APPLICABLE_SUFFIX",
])
def test_u04_f02_dependency_markers_cannot_become_contract_identities(marker):
    assert cal._section7_unresolved(marker)
    for field in ("parser_contract_id", "output_integrity_contract_id"):
        payload = _section7_test_payload()
        payload["execution_architecture"][field] = marker
        rows, records = _section7_test_declarations(payload)
        result = cal.evaluate_section7_closure(payload, rows, records)
        assert result["state"] == "OPEN"
        blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == "P31")
        assert f"execution_architecture.{field}" in blocker["unresolved_payload_fields"]
        assert f"execution_architecture.{field}" in result["unresolved_payload_fields"]
        for operation in (cal.validate_section7_payload, cal.section7_payload_bytes,
                          lambda p: cal.order_section7_payloads({"SYNTHETIC_TEST_ONLY": p})):
            with pytest.raises(r.ResourceContractError):
                operation(payload)


def test_u04_f02_applicability_is_contextual_and_zero_is_resolved():
    assert not cal._section7_unresolved(0)
    assert not cal._section7_unresolved("OPTION_NOT_APPLIED")
    assert not cal._section7_unresolved("SYNTHETIC_TEST_ONLY")
    payload = _section7_test_payload()
    payload["tool_build"]["blast_formatter"] = "NOT_APPLICABLE"
    rows, records = _section7_test_declarations(payload)
    cal.validate_section7_payload(payload)
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"


@pytest.mark.parametrize("field", ["max_target_seqs", "record_count", "total_bases", "database_volume_count"])
def test_u04_f03_required_positive_domains_and_valid_minimum(field):
    for value in (-1, 0, 1):
        payload = _section7_test_payload()
        target = payload["search_parameters"] if field == "max_target_seqs" else payload["technical_domain"]["resource_geometry_cells"][0]
        target[field] = value
        rows, records = _section7_test_declarations(payload)
        result = cal.evaluate_section7_closure(payload, rows, records)
        if value == 1:
            assert result["state"] == "CLOSED"
            assert cal.section7_payload_bytes(payload)
        else:
            assert result["state"] == "OPEN" and result["schema_errors"]
            with pytest.raises(r.ResourceContractError, match="positive_integer"):
                cal.validate_section7_payload(payload)
            with pytest.raises(r.ResourceContractError):
                cal.section7_payload_bytes(payload)


def test_u04_f03_zero_remains_valid_where_the_existing_domain_allows_it():
    payload = _section7_test_payload()
    for field in ("culling_limit", "perc_identity", "qcov_hsp_perc"):
        payload["search_parameters"][field] = 0
    rows, records = _section7_test_declarations(payload)
    cal.validate_section7_payload(payload)
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"


@pytest.mark.parametrize("tasks", [("blastn", "blastn-short"), ("blastn", "blastn-short", "dc-megablast")])
def test_u04_f04_each_candidate_uses_its_corresponding_declarations(tasks):
    candidates = []
    for task in tasks:
        payload = _section7_test_payload()
        payload["search_parameters"]["task"] = task
        rows, records = _section7_test_declarations(payload)
        assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"
        candidates.append({"payload": payload, "parameter_records": records})
    result = cal.evaluate_section7_candidate_set(candidates, rows, design_space_declaration="SYNTHETIC_TEST_ONLY")
    assert result["state"] == "CLOSED"
    assert all(c["state"] == "CLOSED" for c in result["candidate_closures"])
    assert cal.evaluate_section7_candidate_set(candidates, rows)["state"] == "OPEN"
    for index in range(len(candidates)):
        missing = json.loads(r.json_bytes(candidates))
        del missing[index]["parameter_records"]
        result = cal.evaluate_section7_candidate_set(missing, rows, design_space_declaration="SYNTHETIC_TEST_ONLY")
        assert result["state"] == "OPEN"
        assert "P02" in [b["parameter_id"] for b in result["candidate_closures"][index]["blocking_parameters"]]
        mismatched = json.loads(r.json_bytes(candidates))
        mismatched[index]["parameter_records"] = candidates[(index + 1) % len(candidates)]["parameter_records"]
        result = cal.evaluate_section7_candidate_set(mismatched, rows, design_space_declaration="SYNTHETIC_TEST_ONLY")
        assert result["state"] == "OPEN"
        assert "P02" in [b["parameter_id"] for b in result["candidate_closures"][index]["blocking_parameters"]]


def test_u04_s01_closed_explicitly_describes_computational_scope_and_external_authority():
    payload = _section7_test_payload()
    rows, records = _section7_test_declarations(payload)
    candidate = {"payload": payload, "parameter_records": records}
    for result in (cal.evaluate_section7_closure(payload, rows, records),
                   cal.evaluate_section7_candidate_set([candidate], rows, design_space_declaration="UNAUTHENTICATED_TEST_STRING")):
        assert result["state"] == "CLOSED"
        assert result["closure_scope"] == "COMPUTATIONAL_PREDICATES_ON_SUPPLIED_DECLARATIONS"
        assert result["authority_verification"] == "EXTERNAL_DOCUMENTARY_E02_E03_REQUIRED"
        assert result["g1_certification"] == "NOT_EVALUATED"

@pytest.mark.parametrize("state", [cal.STATE_FIXED, cal.STATE_EXCLUDED, cal.STATE_DECIDED, "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE"])
def test_u04_f01_declarations_preserve_canonical_value_types(state):
    payload = _section7_test_payload()
    rows, records = _section7_test_declarations(payload)
    for pid, path, value in (("P28", "database_build.parse_seqids", 1),
                             ("P27", "search_parameters.num_threads", True),
                             ("P07", "search_parameters.gapopen", 5.0),
                             ("P26", "execution_architecture.outfmt_fields", {"qseqid"})):
        bad = json.loads(r.json_bytes(records))
        bad[pid]["effective_value_state"] = state
        bad[pid]["effective_value"][path] = value
        result = cal.evaluate_section7_closure(payload, rows, bad)
        assert result["state"] == "OPEN"
        blocker = next(b for b in result["blocking_parameters"] if b["parameter_id"] == pid)
        assert path in blocker["declaration_mismatch_fields"]
        assert blocker["declaration_error"] == "DECLARATION_PAYLOAD_MISMATCH"

# These are hand-constructed HSP tables, with no BLAST query, fixture B4 or recovery observation.
def _u05_table(**overrides):
    row = dict(zip(cal.U05_HSP_FIELDS, ("Q", "S", "100.000", "4", "4", "4", "1", "4", "1", "4",
                                       "plus", "0.0", "8.0", "0", "0", "0", "100", "4", "8"), strict=True))
    row.update(overrides)
    return ("\t".join(row[field] for field in cal.U05_HSP_FIELDS) + "\n").encode("ascii")


@pytest.mark.parametrize("btop", ["", "10!!5", "4A", "4AC!", "4AX2", "4A*2", "4--2", "01", "00", "4aC2", "4A\x002", "٤"])
def test_u05_btop_total_consumption_and_nucleotide_alphabet(btop):
    with pytest.raises(r.ResourceContractError):
        cal.parse_nb04_btop(btop)


def test_u05_btop_counts_pairs_zero_runs_and_no_column_expansion():
    assert cal.parse_nb04_btop("2AG0-A1T-") == (2, "AG", 0, "-A", 1, "T-")
    assert cal.parse_nb04_btop("0ACGT0") == (0, "AC", "GT", 0)
    assert cal.parse_nb04_btop("1000000000") == (1000000000,)


def test_u05_literal_qa_i_cases_and_explicit_completeness_boundary():
    valid = _u05_table()
    result = cal.parse_nb04_hsp_table(valid, expected_row_count=1)
    assert result["row_count"] == 1 and result["completeness_state"] == "EXPECTED_ROW_COUNT_MATCHED"
    assert result["execution_integrity_established"] is False
    assert result["rows"][0]["pident"] == cal.Decimal("100.000")
    assert tuple(result["rows"][0]) == (*cal.U05_HSP_FIELDS, "raw_numeric_fields")
    for corrupt in (valid[:-3], _u05_table(btop="2!!2"), _u05_table(qseqid="Q\x00")):
        with pytest.raises(r.ResourceContractError):
            cal.parse_nb04_hsp_table(corrupt, expected_row_count=1)
    two = valid + _u05_table(qseqid="Q2")
    assert cal.parse_nb04_hsp_table(two, expected_row_count=2)["row_count"] == 2
    with pytest.raises(r.ResourceContractError, match="witness"):
        cal.parse_nb04_hsp_table(valid, expected_row_count=2)
    unwitnessed = cal.parse_nb04_hsp_table(valid)
    assert unwitnessed["completeness_state"] == "COMPLETENESS_WITNESS_REQUIRED"
    assert unwitnessed["line_boundary_truncation_checked"] is False
    assert unwitnessed["execution_integrity_established"] is False
    assert "WITNESS_AUTHORITY" in unwitnessed["completeness_dependency"]
    assert cal.parse_nb04_hsp_table(b"", expected_row_count=0)["rows"] == []
    assert cal.parse_nb04_hsp_table(b"")["completeness_state"] == "COMPLETENESS_WITNESS_REQUIRED"
    with pytest.raises(r.ResourceContractError):
        cal.parse_nb04_hsp_table(b"", expected_row_count=1)


@pytest.mark.parametrize("witness", [-1, True, "1", 1.0])
def test_u05_witness_type_and_domain(witness):
    with pytest.raises(r.ResourceContractError, match="witness"):
        cal.parse_nb04_hsp_table(_u05_table(), expected_row_count=witness)


@pytest.mark.parametrize("corrupt", [
    lambda t: t[:-1], lambda t: t + b"\n", lambda t: t.replace(b"\n", b"\r\n"),
    lambda t: t + b"\r", lambda t: t.replace(b"Q", b"Q\x00", 1),
    lambda t: t.replace(b"Q", b"Q\x7f", 1), lambda t: t.replace(b"Q", b"Q\x0b", 1),
    lambda t: t.replace(b"Q", b"Q\xff", 1), lambda t: t.replace(b"Q", b"Q\tEXTRA", 1),
    lambda t: t.replace(b"\t", b"", 1), lambda t: b"# comment\n" + t,
])
def test_u05_newline_control_and_field_count_failures(corrupt):
    with pytest.raises(r.ResourceContractError):
        cal.parse_nb04_hsp_table(corrupt(_u05_table()), expected_row_count=1)


@pytest.mark.parametrize("field,value", [
    ("qseqid", ""), ("sseqid", "S P"), ("sstrand", "UNKNOWN"), ("sstrand", "Plus"),
    ("length", "0"), ("qlen", "0"), ("slen", "0"), ("qstart", "0"), ("qend", "5"),
    ("sstart", "0"), ("send", "5"), ("length", "04"), ("score", "1.0"), ("score", "-1"),
    ("mismatch", "-1"), ("gapopen", "1_0"), ("gaps", "+0"), ("pident", "100.001"),
    ("qcovs", "101"), ("evalue", "NaN"), ("bitscore", "Infinity"), ("evalue", "-0.1"),
    ("pident", "10 0"), ("pident", "100 .0"), ("bitscore", ".5"), ("btop", "3"),
    ("mismatch", "1"), ("gapopen", "1"), ("gaps", "1"),
])
def test_u05_exact_field_domains_and_structural_invariants(field, value):
    with pytest.raises(r.ResourceContractError):
        cal.parse_nb04_hsp_table(_u05_table(**{field: value}), expected_row_count=1)


def test_u05_illegal_character_in_each_native_field_raises():
    for field in cal.U05_HSP_FIELDS:
        with pytest.raises(r.ResourceContractError):
            cal.parse_nb04_hsp_table(_u05_table(**{field: "\x00"}), expected_row_count=1)


def test_u05_gaps_replacements_minus_coordinates_and_exact_decimal_values():
    row = cal.parse_nb04_hsp_table(_u05_table(pident="80", length="5", slen="5", send="5", btop="2-A2", gapopen="1", gaps="1"), expected_row_count=1)["rows"][0]
    assert row["length"] == 5 and row["qlen"] == 4 and row["gaps"] == 1
    row = cal.parse_nb04_hsp_table(_u05_table(pident="80", length="5", qlen="5", slen="5", qend="5", send="5", btop="2AG2", mismatch="1"), expected_row_count=1)["rows"][0]
    assert row["mismatch"] == 1
    row = cal.parse_nb04_hsp_table(_u05_table(sstart="4", send="1", sstrand="minus", evalue="1e-999", bitscore="8.123456789123456789"), expected_row_count=1)["rows"][0]
    assert row["sstart"] == 4 and row["send"] == 1
    assert row["evalue"] == cal.Decimal("1e-999") and row["evalue"] != 0
    assert row["bitscore"] == cal.Decimal("8.123456789123456789")
    with pytest.raises(r.ResourceContractError, match="strand"):
        cal.parse_nb04_hsp_table(_u05_table(sstart="4", send="1", sstrand="plus"))


def test_u05_parser_identity_scope_is_exact_and_lf_normalized(tmp_path):
    expected_paths = ("src/zeaguard/nb04_calibration.py", "src/zeaguard/nb04_resources.py")
    assert cal.U05_PARSER_SOURCE_PATHS == expected_paths
    raw = {expected_paths[0]: b"parser\nhelper\n", expected_paths[1]: b"DNA\nrequire\n"}
    for path, content in raw.items():
        _put(tmp_path / path, content)
    identity = cal.nb04_parser_implementation_identity(tmp_path)
    expected = {path: hashlib.sha256(content).hexdigest() for path, content in raw.items()}
    assert identity["implementation_sha256_lf"] == expected
    assert identity["parser_implementation_sha256"] == hashlib.sha256(r.json_bytes(expected)).hexdigest()
    assert identity["scope"]["source_files"] == list(expected_paths)
    assert identity["scope"]["normalization"] == "CRLF_TO_LF"
    for path, content in raw.items():
        _put(tmp_path / path, content.replace(b"\n", b"\r\n"))
    assert cal.nb04_parser_implementation_identity(tmp_path) == identity
    for path in expected_paths:
        saved = (tmp_path / path).read_bytes()
        (tmp_path / path).write_bytes(saved + b"unrelated change\r\n")
        assert cal.nb04_parser_implementation_identity(tmp_path)["parser_implementation_sha256"] != identity["parser_implementation_sha256"]
        (tmp_path / path).write_bytes(saved)


def test_u05_qa_i_precondition_preserves_not_tested_and_fixture_dependency():
    source = {"qa_id": "QA-I", "criterion": "STABLE_PARSING", "metric": "synthetic metric text",
              "expected_behavior": "synthetic expected text", "fixture_dependency": "F01, F02, plus deliberately corrupted copies of a valid output",
              "biological_decision_role": "false", "blocks_configuration_freeze": "YES"}
    result = cal.build_u05_parser_precondition(source)
    assert result["state"] == "NOT_TESTED" and result["configuration_preconditions_inspected"] is True
    assert result["fixtures_materialized"] is False and result["campaign_qa_approved"] is False
    assert result["fixture_dependency"] == source["fixture_dependency"]
    assert result["metric"] == source["metric"] and result["expected_behavior"] == source["expected_behavior"]


@pytest.mark.parametrize("prose", [
    "The limitation contains UNKNOWN and remains explicit.",
    "the severity of the 2018 behaviour in a 2026 build is unknown to this work",
])
def test_u05_s02_prose_with_uncertainty_does_not_resolve_contract_markers(prose):
    payload = _section7_test_payload()
    payload["technical_domain"]["applicability_limitations"] = [prose]
    rows, records = _section7_test_declarations(payload)
    cal.validate_section7_payload(payload)
    assert cal.evaluate_section7_closure(payload, rows, records)["state"] == "CLOSED"
    for marker in ("UNKNOWN", "unknown", "NORMATIVE_BINDING_NOT_ESTABLISHED", "X_PENDING", "NOT_APPLICABLE"):
        for field in ("parser_contract_id", "output_integrity_contract_id"):
            bad = json.loads(r.json_bytes(payload))
            bad["execution_architecture"][field] = marker
            rr, dd = _section7_test_declarations(bad)
            result = cal.evaluate_section7_closure(bad, rr, dd)
            assert result["state"] == "OPEN" and "P31" in [b["parameter_id"] for b in result["blocking_parameters"]]
            with pytest.raises(r.ResourceContractError):
                cal.section7_payload_bytes(bad)

_U05_REVISION_FIELDS = ("qseqid", "sseqid", "pident", "length", "qlen", "slen", "qstart", "qend", "sstart", "send",
                        "sstrand", "evalue", "bitscore", "mismatch", "gapopen", "gaps", "qcovs", "btop", "score")
_U05_REVISION_LITERAL = b"Q\tS\t100.000\t4\t4\t4\t1\t4\t1\t4\tplus\t0.0\t8.0\t0\t0\t0\t100\t4\t8\n"
_U05_REVISION_NUMERIC = ("pident", "length", "qlen", "slen", "qstart", "qend", "sstart", "send", "evalue", "bitscore", "mismatch", "gapopen", "gaps", "qcovs", "score")


def _u05_revision_table(**changes):
    row = dict(zip(_U05_REVISION_FIELDS, _U05_REVISION_LITERAL.decode("ascii").removesuffix("\n").split("\t"), strict=True))
    row.update(changes)
    return ("\t".join(row[field] for field in _U05_REVISION_FIELDS) + "\n").encode("ascii")


def test_u05_revision_f01_preserves_lexical_evidence_alongside_exact_values():
    assert cal.U05_HSP_FIELDS == _U05_REVISION_FIELDS
    a = cal.parse_nb04_hsp_table(_u05_revision_table(evalue="1e-3", bitscore="8e0", score=" 8 "), expected_row_count=1)
    b = cal.parse_nb04_hsp_table(_u05_revision_table(evalue="0.001", bitscore="8", score="8"), expected_row_count=1)
    assert a != b
    first, second = a["rows"][0], b["rows"][0]
    assert first["evalue"] == second["evalue"] == cal.Decimal("0.001")
    assert first["bitscore"] == second["bitscore"] == cal.Decimal("8")
    assert first["score"] == second["score"] == 8
    assert {field: first["raw_numeric_fields"][field] for field in ("evalue", "bitscore", "score")} == {"evalue": "1e-3", "bitscore": "8e0", "score": " 8 "}
    assert {field: second["raw_numeric_fields"][field] for field in ("evalue", "bitscore", "score")} == {"evalue": "0.001", "bitscore": "8", "score": "8"}
    assert set(first["raw_numeric_fields"]) == set(_U05_REVISION_NUMERIC)
    two = cal.parse_nb04_hsp_table(_u05_revision_table(evalue="1e-3") + _u05_revision_table(evalue="0.001"), expected_row_count=2)
    assert [r["raw_numeric_fields"]["evalue"] for r in two["rows"]] == ["1e-3", "0.001"]
    assert a["execution_integrity_established"] is False
    assert cal.parse_nb04_hsp_table(_U05_REVISION_LITERAL)["completeness_state"] == "COMPLETENESS_WITNESS_REQUIRED"
    with pytest.raises(r.ResourceContractError, match="witness"):
        cal.parse_nb04_hsp_table(_U05_REVISION_LITERAL, expected_row_count=2)


def test_u05_revision_f02_rejects_equal_letters_and_preserves_all_distinct_pairs():
    alphabet = "ACGTRYSWKMBDHVN-"
    accepted = []
    for q in alphabet:
        for s in alphabet:
            if q != s:
                pair = q + s
                assert cal.parse_nb04_btop(pair) == (pair,)
                accepted.append(pair)
    assert len(accepted) == 240
    for letter in "ACGTRYSWKMBDHVN":
        pair = letter + letter
        with pytest.raises(r.ResourceContractError, match="identical"):
            cal.parse_nb04_btop(pair)
        bad = _u05_revision_table(length="1", qlen="1", slen="1", qend="1", send="1", btop=pair, mismatch="1", pident="0", score="1", bitscore="1.0")
        with pytest.raises(r.ResourceContractError, match="identical"):
            cal.parse_nb04_hsp_table(bad, expected_row_count=1)
    assert cal.parse_nb04_btop("0ACGT0") == (0, "AC", "GT", 0)
    row = cal.parse_nb04_hsp_table(_u05_revision_table(length="6", slen="6", send="6", btop="2-A0-C2", gaps="2", gapopen="1", pident="66.667"), expected_row_count=1)["rows"][0]
    assert row["gaps"] == 2 and row["gapopen"] == 1


@pytest.mark.parametrize("field", _U05_REVISION_NUMERIC)
def test_u05_revision_f03_accepts_only_surrounding_ascii_numeric_padding(field):
    core = dict(zip(_U05_REVISION_FIELDS, _U05_REVISION_LITERAL.decode("ascii").removesuffix("\n").split("\t"), strict=True))[field]
    padded = "  " + core + " "
    result = cal.parse_nb04_hsp_table(_u05_revision_table(**{field: padded}), expected_row_count=1)
    row = result["rows"][0]
    assert row["raw_numeric_fields"][field] == padded
    assert row[field] == (cal.Decimal(core) if field in ("pident", "evalue", "bitscore", "qcovs") else int(core))
    assert result["producer_lexical_compatibility"] == "NOT_ESTABLISHED_FOR_PINNED_BUILD"
    assert result["producer_format_dependency"] == "APPLICABLE_PINNED_BUILD_FORMAT_EVIDENCE_BEFORE_CAMPAIGN_USE"


@pytest.mark.parametrize("field,value", [
    ("bitscore", " 8.0"), ("bitscore", "20.0 "), ("evalue", "  1e-05"), ("score", " 8 "),
])
def test_u05_revision_f03_reported_padding_examples_preserve_text(field, value):
    row = cal.parse_nb04_hsp_table(_u05_revision_table(**{field: value}), expected_row_count=1)["rows"][0]
    assert row["raw_numeric_fields"][field] == value


@pytest.mark.parametrize("field,value", [
    ("bitscore", " 8 .0 "), ("bitscore", " +8.0 "), ("bitscore", " 08.0 "), ("bitscore", " NaN "),
    ("evalue", " 1e--3 "), ("score", " 8.0 "), ("score", " -8 "), ("score", " 08 "),
    ("qseqid", " Q"), ("sseqid", "S "), ("sstrand", " plus "), ("btop", " 4 "),
])
def test_u05_revision_f03_keeps_numeric_core_and_nonnumeric_fields_strict(field, value):
    with pytest.raises(r.ResourceContractError):
        cal.parse_nb04_hsp_table(_u05_revision_table(**{field: value}), expected_row_count=1)


def test_u05_revision_f03_rejects_controls_and_non_ascii_before_padding_handling():
    for illegal in (b"\x00", b"\r", b"\x0b", b"\x7f", b"\xc2\xa0", b"\t"):
        table = _U05_REVISION_LITERAL.replace(b"\t8.0\t", b"\t " + illegal + b"8.0 \t")
        with pytest.raises(r.ResourceContractError):
            cal.parse_nb04_hsp_table(table, expected_row_count=1)


def test_u05_revision_identity_has_an_independent_canonical_oracle_and_scope_limits(tmp_path):
    sources = {"src/zeaguard/nb04_calibration.py": b"calibration\r\n", "src/zeaguard/nb04_resources.py": b"resources\n"}
    for path, raw in sources.items():
        _put(tmp_path / path, raw)
    inventory = {path: hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() for path, raw in sources.items()}
    canonical = (json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    identity = cal.nb04_parser_implementation_identity(tmp_path)
    assert identity["parser_implementation_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert identity["implementation_sha256_lf"] == inventory
    assert "interpreter" in identity["scope"]["runtime_limitation"]
    assert "standard library" in identity["scope"]["runtime_limitation"]
    assert identity["scope"]["prefreeze_dependency"] == "RECOMPUTE_IDENTITIES_FROM_FINAL_SOURCE_BEFORE_FREEZING_AND_ORDERING_CANDIDATES"
    assert identity["scope"]["decision_authority"] == "IMPLEMENTATION_COORDINATOR"

# U06 uses declarations and token arrays only, with no command execution.
_U06_NATIVE_TABULAR = '6 qseqid sseqid pident length qlen slen qstart qend sstart send sstrand evalue bitscore mismatch gapopen gaps qcovs btop score'
_U06_SEARCH_HELP = _FAKE_BLASTN_HELP + '\n -db <String>\n -query <File_In>\n -out <File_Out>\n'
_U06_EXPORT_HELP = _FAKE_BLAST_FORMATTER_HELP + '\n -out <File_Out>\n'


def _u06_search_inputs():
    payload = _section7_test_payload()
    rows, records = _section7_test_declarations(payload)
    provenance = {}
    for param_id, flags in cal.E05_PARAMETER_FLAGS.items():
        if param_id in ('P28', 'P29'):
            continue
        for index, flag in enumerate(flags):
            if param_id == 'P26':
                value = '11'
            else:
                value = payload['search_parameters'][cal.E05_SECTION7_PARAMETER_PATHS[param_id][index].split('.')[1]]
            omitted = value == 'OPTION_NOT_APPLIED' or flag == '-lcase_masking'
            origin = 'OPTION_NOT_APPLIED' if omitted else 'EXPLICIT'
            if param_id == 'P23':
                origin = 'NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET'
            provenance[flag] = {'option_applied': not omitted, 'origin': origin}
    envelope = {'executable': 'blastn', 'paths': {'-db': 'synthetic/db', '-query': 'synthetic/query.fa', '-out': 'synthetic/output.asn'},
                'flag_provenance': provenance}
    return payload, rows, records, envelope


def _u06_search(payload=None, rows=None, records=None, envelope=None, help_text=_U06_SEARCH_HELP):
    if payload is None:
        payload, rows, records, envelope = _u06_search_inputs()
    return cal.reconstruct_section7_search_command(payload, rows, records, envelope, help_text=help_text)


def _u06_export_record():
    return {'executable': 'blast_formatter', 'paths': {'-archive': 'synthetic/output.asn', '-out': 'synthetic/output.tsv'},
            'options': {'-outfmt': {'value': _U06_NATIVE_TABULAR, 'option_applied': True, 'origin': 'EXPLICIT'},
                        '-max_target_seqs': {'value': 'OPTION_NOT_APPLIED', 'option_applied': False, 'origin': 'OPTION_NOT_APPLIED'},
                        '-num_descriptions': {'value': 'OPTION_NOT_APPLIED', 'option_applied': False, 'origin': 'OPTION_NOT_APPLIED'},
                        '-num_alignments': {'value': 'OPTION_NOT_APPLIED', 'option_applied': False, 'origin': 'OPTION_NOT_APPLIED'}}}


def test_u06_search_literal_argv_and_no_mutation():
    inputs = _u06_search_inputs()
    before = r.json_bytes(inputs)
    result = _u06_search(*inputs)
    assert result['argv'] == ['blastn', '-task', 'blastn', '-word_size', '11', '-evalue', '10.0', '-reward', '2',
                              '-penalty', '-3', '-gapopen', '5', '-gapextend', '2', '-dust', 'no', '-soft_masking', 'false',
                              '-strand', 'both', '-max_target_seqs', '100', '-outfmt', '11', '-num_threads', '1',
                              '-db', 'synthetic/db', '-query', 'synthetic/query.fa', '-out', 'synthetic/output.asn']
    assert r.json_bytes(inputs) == before
    assert result['qa_m']['state'] == 'NOT_TESTED' and result['limitations']
    assert result['order_decision_authority'] == 'IMPLEMENTATION_COORDINATOR_REVISABLE_BEFORE_FREEZE'
    assert '-max_file_sz' not in result['argv'] and '-parse_seqids' not in result['argv']
    for flag in ('-dbsize', '-searchsp', '-lcase_masking', '-sum_stats'):
        assert flag not in result['argv']


@pytest.mark.parametrize('task', ['blastn', 'blastn-short', 'dc-megablast'])
def test_u06_each_admitted_task_is_explicit(task):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters']['task'] = task
    rows, records = _section7_test_declarations(payload)
    result = _u06_search(payload, rows, records, envelope)
    assert result['argv'][1:3] == ['-task', task]


def test_u06_provenance_controls_emission_even_when_explicit_value_equals_default():
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters']['max_target_seqs'] = 500
    rows, records = _section7_test_declarations(payload)
    explicit = _u06_search(payload, rows, records, envelope)['argv']
    envelope['flag_provenance']['-max_target_seqs'] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    defaulted = _u06_search(payload, rows, records, envelope)
    assert explicit[explicit.index('-max_target_seqs') + 1] == '500'
    assert '-max_target_seqs' not in defaulted['argv']
    assert payload['search_parameters']['max_target_seqs'] == 500
    assert defaulted['flag_provenance']['-max_target_seqs']['origin'] == 'DOCUMENTED_ENGINE_DEFAULT'


@pytest.mark.parametrize('change, message', [
    ('missing_flag', 'closed schema'), ('missing_origin', 'closed schema'), ('non_boolean', 'explicitly boolean'),
    ('wrong_default', 'differs from documented default'), ('undocumented_default', 'not documented'),
    ('explicit_without_origin', 'EXPLICIT'), ('omitted_effective', 'without documented-default'),
    ('task_default', 'task must be explicit'), ('outfmt_omitted', 'P26'), ('absent_build_flag', 'absent from supplied build help'),
    ('missing_record', 'payload OPEN'), ('missing_value', 'payload OPEN'),
])
def test_u06_search_refuses_incomplete_or_contradictory_declarations(change, message):
    payload, rows, records, envelope = _u06_search_inputs()
    help_text = _U06_SEARCH_HELP
    if change == 'missing_flag':
        del envelope['flag_provenance']['-word_size']
    elif change == 'missing_origin':
        del envelope['flag_provenance']['-word_size']['origin']
    elif change == 'non_boolean':
        envelope['flag_provenance']['-word_size']['option_applied'] = 1
    elif change == 'wrong_default':
        envelope['flag_provenance']['-max_target_seqs'] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    elif change == 'undocumented_default':
        envelope['flag_provenance']['-gapopen'] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    elif change == 'explicit_without_origin':
        envelope['flag_provenance']['-word_size']['origin'] = 'DOCUMENTED_ENGINE_DEFAULT'
    elif change == 'omitted_effective':
        envelope['flag_provenance']['-word_size'] = {'option_applied': False, 'origin': 'OPTION_NOT_APPLIED'}
    elif change == 'task_default':
        envelope['flag_provenance']['-task'] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    elif change == 'outfmt_omitted':
        envelope['flag_provenance']['-outfmt']['option_applied'] = False
    elif change == 'absent_build_flag':
        help_text = help_text.replace(' -word_size <Integer, >=4>', ' -unavailable_word_size <Integer, >=4>')
    elif change == 'missing_record':
        del records['P13']
    else:
        del payload['search_parameters']['word_size']
    with pytest.raises(r.ResourceContractError, match=message):
        _u06_search(payload, rows, records, envelope, help_text=help_text)


@pytest.mark.parametrize('param_id', ['P15', 'P16', 'P17', 'P18', 'P19', 'P20', 'P24'])
def test_u06_architecture_exclusions_never_emit_even_with_fresh_consistent_declarations(param_id):
    payload, rows, records, envelope = _u06_search_inputs()
    flag = cal.E05_PARAMETER_FLAGS[param_id][0]
    field = cal.E05_SECTION7_PARAMETER_PATHS[param_id][0].split('.')[1]
    payload['search_parameters'][field] = 'true' if param_id in ('P20', 'P24') else 1
    rows, records = _section7_test_declarations(payload)
    with pytest.raises(r.ResourceContractError, match=param_id + ' .*excluded by architecture'):
        _u06_search(payload, rows, records, envelope)
    payload['search_parameters'][field] = 'OPTION_NOT_APPLIED'
    rows, records = _section7_test_declarations(payload)
    envelope['flag_provenance'][flag] = {'option_applied': True, 'origin': 'EXPLICIT'}
    with pytest.raises(r.ResourceContractError, match='OPTION_NOT_APPLIED cannot emit'):
        _u06_search(payload, rows, records, envelope)


@pytest.mark.parametrize('flag', ['-dbsize', '-searchsp'])
def test_u06_natural_search_space_is_explicit_nonapplication(flag):
    payload, rows, records, envelope = _u06_search_inputs()
    assert flag not in _u06_search(payload, rows, records, envelope)['argv']
    envelope['flag_provenance'][flag]['origin'] = 'OPTION_NOT_APPLIED'
    with pytest.raises(r.ResourceContractError, match='P23 .*natural-resource search space'):
        _u06_search(payload, rows, records, envelope)
    envelope['flag_provenance'][flag] = {'option_applied': True, 'origin': 'EXPLICIT'}
    payload['search_parameters'][flag[1:]] = 1
    rows, records = _section7_test_declarations(payload)
    with pytest.raises(r.ResourceContractError, match='P23'):
        _u06_search(payload, rows, records, envelope)


def test_u06_nine_pending_fields_cannot_emit():
    payload, rows, records, envelope = _u06_search_inputs()
    pending = ('P02', 'P03', 'P04', 'P07', 'P08', 'P13', 'P14', 'P27', 'P29')
    for param_id in pending:
        section, field = cal.E05_SECTION7_PARAMETER_PATHS[param_id][0].split('.')
        payload[section][field] = None
        records[param_id] = {'effective_value': None, 'effective_value_state': cal.STATE_PENDING}
    with pytest.raises(r.ResourceContractError, match='search payload OPEN') as exc:
        _u06_search(payload, rows, records, envelope)
    assert all(param_id in str(exc.value) for param_id in pending)


@pytest.mark.parametrize('stage, flag', [('search', '-db'), ('search', '-query'), ('search', '-out'), ('export', '-archive'), ('export', '-out')])
@pytest.mark.parametrize('bad_value', [None, '', 'x\x00y', '-query'])
def test_u06_required_paths_are_declared_and_unambiguous(stage, flag, bad_value):
    if stage == 'search':
        inputs = _u06_search_inputs()
        envelope = inputs[-1]
        call = lambda: _u06_search(*inputs)
    else:
        envelope = _u06_export_record()
        call = lambda: cal.reconstruct_blast_formatter_command(envelope, help_text=_U06_EXPORT_HELP)
    if bad_value is None:
        del envelope['paths'][flag]
    else:
        envelope['paths'][flag] = bad_value
    with pytest.raises(r.ResourceContractError, match='paths'):
        call()


@pytest.mark.parametrize('key', ['overrides', 'execution_payload', 'parent_candidate_hash', 'qa_case_id'])
@pytest.mark.parametrize('stage', ['search', 'export'])
def test_u06_execution_overrides_are_explicitly_refused(stage, key):
    if stage == 'search':
        inputs = _u06_search_inputs()
        inputs[-1][key] = {'max_target_seqs': 1}
        call = lambda: _u06_search(*inputs)
    else:
        record = _u06_export_record()
        record[key] = {'max_target_seqs': 1}
        call = lambda: cal.reconstruct_blast_formatter_command(record, help_text=_U06_EXPORT_HELP)
    with pytest.raises(r.ResourceContractError, match='execution overrides are unsupported.*max_target_seqs'):
        call()


def test_u06_export_literal_argv_and_default_cap_not_emitted():
    record = _u06_export_record()
    record['options']['-max_target_seqs'] = {'value': 500, 'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    result = cal.reconstruct_blast_formatter_command(record, help_text=_U06_EXPORT_HELP)
    assert result['argv'] == ['blast_formatter', '-outfmt', _U06_NATIVE_TABULAR, '-archive', 'synthetic/output.asn', '-out', 'synthetic/output.tsv']
    assert result['qa_m']['state'] == 'NOT_TESTED' and result['limitations']


@pytest.mark.parametrize('other', ['-num_descriptions', '-num_alignments'])
def test_u06_export_refuses_measured_incompatibilities(other):
    record = _u06_export_record()
    for flag in ('-max_target_seqs', other):
        record['options'][flag] = {'value': 1, 'option_applied': True, 'origin': 'EXPLICIT'}
    with pytest.raises(r.ResourceContractError, match='incompatible passed flags'):
        cal.reconstruct_blast_formatter_command(record, help_text=_U06_EXPORT_HELP)


def test_u06_export_does_not_invent_incompatibility_between_description_and_alignment_flags():
    record = _u06_export_record()
    for flag in ('-num_descriptions', '-num_alignments'):
        record['options'][flag] = {'value': 1, 'option_applied': True, 'origin': 'EXPLICIT'}
    assert cal.reconstruct_blast_formatter_command(record, help_text=_U06_EXPORT_HELP)['argv'] == [
        'blast_formatter', '-outfmt', _U06_NATIVE_TABULAR, '-num_descriptions', '1', '-num_alignments', '1',
        '-archive', 'synthetic/output.asn', '-out', 'synthetic/output.tsv']


@pytest.mark.parametrize('change', ['missing_cap', 'missing_value', 'pending', 'negative', 'cap_zero', 'extra_option', 'wrong_outfmt', 'not_applied_emitted'])
def test_u06_export_refuses_incomplete_or_invalid_records(change):
    record = _u06_export_record()
    option = record['options']['-max_target_seqs']
    if change == 'missing_cap':
        del record['options']['-max_target_seqs']
    elif change == 'missing_value':
        del option['value']
    elif change == 'pending':
        option['value'] = None
    elif change in ('negative', 'cap_zero'):
        option.update(value=-1 if change == 'negative' else 0, option_applied=True, origin='EXPLICIT')
    elif change == 'extra_option':
        record['options']['-max_hsps'] = option.copy()
    elif change == 'wrong_outfmt':
        record['options']['-outfmt']['value'] = '6 qseqid score'
    else:
        option.update(option_applied=True, origin='EXPLICIT')
    with pytest.raises(r.ResourceContractError):
        cal.reconstruct_blast_formatter_command(record, help_text=_U06_EXPORT_HELP)


def test_u06_comparator_declares_order_normalization_and_never_approves_qa():
    a = ['blastn', '-task', 'blastn', '-penalty', '-3', '-lcase_masking']
    b = ['blastn', '-lcase_masking', '-penalty', '-3', '-task', 'blastn']
    result = cal.compare_qa_m_argv(a, b, help_text=_U06_SEARCH_HELP)
    assert result['correspondence'] is True and result['state'] == 'NOT_TESTED'
    assert result['normalization'] == {
        'executable': 'EXACT_TOKEN_NO_PATH_RESOLUTION', 'flags': 'SET_OF_FLAG_VALUE_PAIRS_USING_SUPPLIED_HELP_ARITY',
        'positional': 'REJECTED_NO_POSITIONAL_ARGUMENTS_SUPPORTED', 'token_order': 'IGNORED', 'values': 'EXACT_TEXT_NO_NUMERIC_OR_PATH_NORMALIZATION',
        'duplicate_flags': 'REJECTED_AS_AMBIGUOUS', 'decision_authority': 'IMPLEMENTATION_COORDINATOR_REVISABLE_BEFORE_FREEZE'}
    assert result['flag_differences'] == [] and result['limitations']


def test_u06_comparator_reports_each_flag_and_other_difference():
    result = cal.compare_qa_m_argv(['blastn', '-task', 'blastn', '-evalue', '1'],
                                 ['other_blastn', '-task', 'blastn-short', '-out', 'x'], help_text=_U06_SEARCH_HELP)
    assert result['correspondence'] is False and result['executable_differs'] is True
    assert result['flag_differences'] == [
        {'flag': '-evalue', 'reconstructed_present': True, 'logged_present': False, 'reconstructed_value': '1', 'logged_value': None},
        {'flag': '-out', 'reconstructed_present': False, 'logged_present': True, 'reconstructed_value': None, 'logged_value': 'x'},
        {'flag': '-task', 'reconstructed_present': True, 'logged_present': True, 'reconstructed_value': 'blastn', 'logged_value': 'blastn-short'}]
    assert result['positional_differences'] == {'only_reconstructed': [], 'only_logged': []}
    assert cal.compare_qa_m_argv(['blastn', '-evalue', '1'], ['blastn', '-evalue', '1.0'], help_text=_U06_SEARCH_HELP)['correspondence'] is False


@pytest.mark.parametrize('argv', [[], ['blastn', '-task'], ['blastn', '-task', '-out', 'x'],
                                  ['blastn', '-task', 'blastn', '-task', 'blastn'], ['blastn', '-undeclared'], ['blastn', 'x\x00y']])
def test_u06_comparator_refuses_ambiguous_argv(argv):
    with pytest.raises(r.ResourceContractError):
        cal.compare_qa_m_argv(['blastn'], argv, help_text=_U06_SEARCH_HELP)

def test_u06_legacy_p23_record_uses_natural_resource_policy_without_flags():
    payload, rows, records, envelope = _u06_search_inputs()
    records['P23'] = {'effective_value_state': cal.STATE_DECIDED, 'effective_value': cal.E05_P23_EFFECTIVE_VALUE.copy()}
    result = _u06_search(payload, rows, records, envelope)
    assert '-dbsize' not in result['argv'] and '-searchsp' not in result['argv']
    assert result['execution_performed'] is False and result['campaign_qa_approved'] is False


def test_u06_presence_only_flag_and_parameter_order_ignore_envelope_insertion_order():
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters']['lcase_masking'] = 'true'
    payload['search_parameters'].update(xdrop_ungap=20.0, xdrop_gap=30.0, xdrop_gap_final=100.0, window_size=40)
    rows, records = _section7_test_declarations(payload)
    for flag in ('-lcase_masking', '-xdrop_ungap', '-xdrop_gap', '-xdrop_gap_final', '-window_size'):
        envelope['flag_provenance'][flag] = {'option_applied': True, 'origin': 'EXPLICIT'}
    envelope['flag_provenance'] = dict(reversed(list(envelope['flag_provenance'].items())))
    argv = _u06_search(payload, rows, records, envelope)['argv']
    assert argv[argv.index('-lcase_masking'):argv.index('-lcase_masking') + 2] == ['-lcase_masking', '-strand']
    assert argv[argv.index('-xdrop_ungap'):argv.index('-outfmt')] == ['-xdrop_ungap', '20.0', '-xdrop_gap', '30.0', '-xdrop_gap_final', '100.0', '-window_size', '40']


def test_u06_comparator_refuses_unknown_option_disguised_as_a_value():
    with pytest.raises(r.ResourceContractError, match='option-like value'):
        cal.compare_qa_m_argv(['blastn'], ['blastn', '-task', '-unknown'], help_text=_U06_SEARCH_HELP)


def test_u06_output_cannot_be_used_as_execution_or_integrity_approval():
    result = cal.compare_qa_m_argv(['blastn'], ['blastn'], help_text=_U06_SEARCH_HELP)
    assert result['correspondence'] is True and result['state'] == 'NOT_TESTED'
    assert result['execution_performed'] is False and result['campaign_qa_approved'] is False
    assert any('QA-I remains NOT_TESTED' in text for text in result['limitations'])
    assert any('truncation' in text for text in result['limitations'])

@pytest.fixture(scope='module')
def u06_revision_pinned_help():
    """Read only help/version. These probes never execute a reconstructed argv."""
    helps = {}
    for tool in ('blastn', 'blast_formatter'):
        executable = cal._default_tool_which(tool)
        if executable is None:
            pytest.skip(f'pinned {tool} help unavailable outside canonical environment')
        version = subprocess.run([executable, '-version'], capture_output=True, text=True, check=True).stdout
        if '2.17.0+' not in version:
            pytest.skip(f'{tool} build differs from pinned help contract')
        helps[tool] = subprocess.run([executable, '-help'], capture_output=True, text=True, check=True).stdout
    return helps


@pytest.mark.parametrize('task,evalue,dust', [
    ('blastn', 10, '20 64 1'), ('blastn-short', 1000, 'no'), ('dc-megablast', 10, '20 64 1'),
])
@pytest.mark.parametrize('flag,field', [('-evalue', 'evalue_reporting_limit'), ('-dust', 'dust')])
def test_u06_revision_real_task_defaults_are_omitted_and_explicit_values_still_emit(u06_revision_pinned_help, task, evalue, dust, flag, field):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters'].update(task=task, evalue_reporting_limit=evalue, dust=dust)
    rows, records = _section7_test_declarations(payload)
    envelope['flag_provenance'][flag] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    inputs = (payload, rows, records, envelope)
    before = r.json_bytes(inputs)
    result = _u06_search(*inputs, help_text=u06_revision_pinned_help['blastn'])
    assert result['argv'][1:3] == ['-task', task] and flag not in result['argv']
    assert result['qa_m']['state'] == 'NOT_TESTED' and result['execution_performed'] is False
    assert r.json_bytes(inputs) == before
    envelope['flag_provenance'][flag] = {'option_applied': True, 'origin': 'EXPLICIT'}
    argv = _u06_search(*inputs, help_text=u06_revision_pinned_help['blastn'])['argv']
    assert argv[argv.index(flag) + 1] == str(evalue if field == 'evalue_reporting_limit' else dust)


@pytest.mark.parametrize('task,evalue,dust', [
    ('blastn', 1000, 'no'), ('blastn-short', 10, '20 64 1'), ('dc-megablast', 1000, 'no'),
])
@pytest.mark.parametrize('flag,field', [('-evalue', 'evalue_reporting_limit'), ('-dust', 'dust')])
def test_u06_revision_default_must_match_the_declared_task(u06_revision_pinned_help, task, evalue, dust, flag, field):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters'].update(task=task)
    payload['search_parameters'][field] = evalue if field == 'evalue_reporting_limit' else dust
    rows, records = _section7_test_declarations(payload)
    envelope['flag_provenance'][flag] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    with pytest.raises(r.ResourceContractError, match='differs from documented default for task ' + task):
        _u06_search(payload, rows, records, envelope, help_text=u06_revision_pinned_help['blastn'])


@pytest.mark.parametrize('flag', ['-evalue', '-dust'])
def test_u06_revision_unknown_default_forms_fail_closed(u06_revision_pinned_help, flag):
    payload, rows, records, envelope = _u06_search_inputs()
    text = u06_revision_pinned_help['blastn']
    default = cal.parse_blast_help_flags(text)[flag]['documented_default_in_build_help']
    pattern = r'\s+'.join(re.escape(word) for word in default.split())
    altered, count = re.subn(pattern, 'Default = unrecognized conditional prose', text)
    assert count == 1
    assert cal.parse_blast_help_flags(altered)[flag]['documented_default_in_build_help'] == 'Default = unrecognized conditional prose'
    envelope['flag_provenance'][flag] = {'option_applied': False, 'origin': 'DOCUMENTED_ENGINE_DEFAULT'}
    with pytest.raises(r.ResourceContractError, match='default is not documented in a supported form'):
        _u06_search(payload, rows, records, envelope, help_text=altered)


@pytest.mark.parametrize('field,value', [('word_size', 1), ('num_threads', 0), ('max_hsps', 0), ('penalty', 1)])
def test_u06_revision_rejects_explicit_values_outside_real_header_domains(u06_revision_pinned_help, field, value):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters'][field] = value
    rows, records = _section7_test_declarations(payload)
    envelope['flag_provenance']['-' + field] = {'option_applied': True, 'origin': 'EXPLICIT'}
    assert cal.evaluate_section7_closure(payload, rows, records)['state'] == 'CLOSED'
    with pytest.raises(r.ResourceContractError, match='outside documented header domain'):
        _u06_search(payload, rows, records, envelope, help_text=u06_revision_pinned_help['blastn'])


@pytest.mark.parametrize('field,value', [('word_size', 4), ('num_threads', 1), ('max_hsps', 1), ('penalty', -3), ('penalty', 0), ('reward', 0), ('window_size', 0)])
def test_u06_revision_accepts_exact_boundaries_and_legitimate_negatives(u06_revision_pinned_help, field, value):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters'][field] = value
    rows, records = _section7_test_declarations(payload)
    envelope['flag_provenance']['-' + field] = {'option_applied': True, 'origin': 'EXPLICIT'}
    argv = _u06_search(payload, rows, records, envelope, help_text=u06_revision_pinned_help['blastn'])['argv']
    assert argv[argv.index('-' + field) + 1] == str(value)


@pytest.mark.parametrize('flag,value', [('-max_target_seqs', 0), ('-num_descriptions', -1), ('-num_alignments', -1), ('-max_target_seqs', '1')])
def test_u06_revision_export_uses_the_same_real_header_domain_checks(u06_revision_pinned_help, flag, value):
    record = _u06_export_record()
    record['options'][flag] = {'value': value, 'option_applied': True, 'origin': 'EXPLICIT'}
    with pytest.raises(r.ResourceContractError, match='documented header domain|invalid Integer value'):
        cal.reconstruct_blast_formatter_command(record, help_text=u06_revision_pinned_help['blast_formatter'])


@pytest.mark.parametrize('flag,value', [('-max_target_seqs', 1), ('-num_descriptions', 0), ('-num_alignments', 0)])
def test_u06_revision_export_accepts_header_boundaries(u06_revision_pinned_help, flag, value):
    record = _u06_export_record()
    record['options'][flag] = {'value': value, 'option_applied': True, 'origin': 'EXPLICIT'}
    argv = cal.reconstruct_blast_formatter_command(record, help_text=u06_revision_pinned_help['blast_formatter'])['argv']
    assert argv[argv.index(flag) + 1] == str(value)


@pytest.mark.parametrize('stage,flag', [('blastn', '-db'), ('blastn', '-query'), ('blastn', '-out'), ('blast_formatter', '-archive'), ('blast_formatter', '-out')])
@pytest.mark.parametrize('alteration', ['absent', 'presence_only', 'wrong_type'])
def test_u06_revision_every_path_requires_supported_help_and_one_file_operand(u06_revision_pinned_help, stage, flag, alteration):
    text = u06_revision_pinned_help[stage]
    header = cal.parse_blast_help_flags(text)[flag]['header_line']
    replacement = header.replace(flag, '-unavailable_path', 1) if alteration == 'absent' else flag if alteration == 'presence_only' else flag + ' <Integer>'
    assert header in text
    altered = text.replace(header, replacement)
    if alteration == 'absent':
        assert flag not in cal.parse_blast_help_flags(altered)
    if stage == 'blastn':
        inputs = _u06_search_inputs()
        # Even a path spelled "true" must never turn into a valueless switch.
        if alteration == 'presence_only':
            inputs[-1]['paths'][flag] = 'true'
        call = lambda: _u06_search(*inputs, help_text=altered)
    else:
        record = _u06_export_record()
        if alteration == 'presence_only':
            record['paths'][flag] = 'true'
        call = lambda: cal.reconstruct_blast_formatter_command(record, help_text=altered)
    with pytest.raises(r.ResourceContractError, match='absent from supplied build help|path flag requires one string/file operand'):
        call()


@pytest.mark.parametrize('length', [255, 256])
def test_u06_revision_real_output_header_length_boundary(u06_revision_pinned_help, length):
    inputs = _u06_search_inputs()
    inputs[-1]['paths']['-out'] = 'a' * length
    if length == 256:
        with pytest.raises(r.ResourceContractError, match='outside documented header domain'):
            _u06_search(*inputs, help_text=u06_revision_pinned_help['blastn'])
    else:
        argv = _u06_search(*inputs, help_text=u06_revision_pinned_help['blastn'])['argv']
        assert argv[-2:] == ['-out', 'a' * length]


@pytest.mark.parametrize('alteration', ['not_applicable', 'missing_sha', 'wrong_name'])
def test_u06_revision_selected_blastn_requires_complete_applicable_identity(alteration):
    payload, rows, records, envelope = _u06_search_inputs()
    if alteration == 'not_applicable':
        payload['tool_build']['blastn'] = 'NOT_APPLICABLE'
    elif alteration == 'missing_sha':
        del payload['tool_build']['blastn']['executable_sha256']
    else:
        payload['tool_build']['blastn']['tool_name'] = 'blast_formatter'
    rows, records = _section7_test_declarations(payload)
    if alteration == 'not_applicable':
        assert cal.evaluate_section7_closure(payload, rows, records)['state'] == 'CLOSED'
    with pytest.raises(r.ResourceContractError, match='tool_build.blastn'):
        _u06_search(payload, rows, records, envelope)


def test_u06_revision_unused_tool_can_still_be_inapplicable():
    payload, rows, records, envelope = _u06_search_inputs()
    payload['tool_build']['dustmasker'] = 'NOT_APPLICABLE'
    assert _u06_search(payload, rows, records, envelope)['argv'][0] == 'blastn'


@pytest.mark.parametrize('argv', [
    ['blastn', '-lcase_masking', 'false', 'a'], ['blastn', 'a', '-lcase_masking', 'false', 'a'],
    ['blastn', 'a'], ['blastn', '-3'], ['blast_formatter', '-archive', 'synthetic/output.asn', 'extra'],
])
def test_u06_revision_comparator_refuses_all_unexpected_positionals(argv):
    with pytest.raises(r.ResourceContractError, match='unexpected positional argument'):
        cal.compare_qa_m_argv(argv, argv, help_text=_U06_SEARCH_HELP + _U06_EXPORT_HELP)


def test_u06_revision_scope_limits_are_in_the_returned_envelope():
    result = cal.reconstruct_blast_formatter_command(_u06_export_record(), help_text=_U06_EXPORT_HELP)
    assert any('no tool_build carrier' in text for text in result['limitations'])
    assert any('no stdout or positional operands' in text for text in result['limitations'])
    assert result['qa_m']['state'] == 'NOT_TESTED' and result['campaign_qa_approved'] is False

_U06_F04_PATH_CASES = [('blastn', '-db'), ('blastn', '-query'), ('blastn', '-out'),
                       ('blast_formatter', '-archive'), ('blast_formatter', '-out')]


@pytest.mark.parametrize('stage,flag', _U06_F04_PATH_CASES)
@pytest.mark.parametrize('literal_path', [
    'synthetic/UNKNOWN.fa', 'synthetic/PENDING/db', 'synthetic/TBD_run.tsv',
    'synthetic/NOT_APPLICABLE.fa', 'synthetic/nao_medido/db',
    'synthetic/NORMATIVE_BINDING_NOT_ESTABLISHED.asn', 'OPTION_NOT_APPLIED',
    'synthetic/UNKNOWN result with spaces.asn', ' synthetic/UNKNOWN.asn ',
])
def test_u06_f04_path_names_are_literal_and_preserved_byte_for_byte(u06_revision_pinned_help, stage, flag, literal_path):
    if stage == 'blastn':
        inputs = _u06_search_inputs()
        inputs[-1]['paths'][flag] = literal_path
        call = lambda: _u06_search(*inputs, help_text=u06_revision_pinned_help[stage])
    else:
        inputs = _u06_export_record()
        inputs['paths'][flag] = literal_path
        call = lambda: cal.reconstruct_blast_formatter_command(inputs, help_text=u06_revision_pinned_help[stage])
    before = r.json_bytes(inputs)
    result = call()
    emitted = result['argv'][result['argv'].index(flag) + 1]
    assert emitted.encode('utf-8') == literal_path.encode('utf-8')
    assert r.json_bytes(inputs) == before
    assert result['execution_performed'] is False and result['campaign_qa_approved'] is False


@pytest.mark.parametrize('stage,flag', _U06_F04_PATH_CASES)
@pytest.mark.parametrize('invalid_path', [None, '   ', 'synthetic/UNKNOWN\x00.fa', '-looks_like_option', '-UNKNOWN'])
def test_u06_f04_literal_context_preserves_envelope_rejections(u06_revision_pinned_help, stage, flag, invalid_path):
    if stage == 'blastn':
        inputs = _u06_search_inputs()
        inputs[-1]['paths'][flag] = invalid_path
        call = lambda: _u06_search(*inputs, help_text=u06_revision_pinned_help[stage])
    else:
        inputs = _u06_export_record()
        inputs['paths'][flag] = invalid_path
        call = lambda: cal.reconstruct_blast_formatter_command(inputs, help_text=u06_revision_pinned_help[stage])
    with pytest.raises(r.ResourceContractError, match='envelope.paths'):
        call()


@pytest.mark.parametrize('marker', [None, 'UNKNOWN', 'PENDING_CALIBRATION', 'TBD', 'NOT_APPLICABLE', 'nao_medido', 'NORMATIVE_BINDING_NOT_ESTABLISHED'])
def test_u06_f04_parameter_values_still_block_closure(marker):
    payload, rows, records, envelope = _u06_search_inputs()
    payload['search_parameters']['word_size'] = marker
    rows, records = _section7_test_declarations(payload)
    closure = cal.evaluate_section7_closure(payload, rows, records)
    assert closure['state'] == 'OPEN'
    assert 'P03' in {entry['parameter_id'] for entry in closure['blocking_parameters']}
    with pytest.raises(r.ResourceContractError, match='search payload OPEN'):
        _u06_search(payload, rows, records, envelope)


def test_u06_f04_named_spaces_and_negative_value_still_compare_by_unique_pairs():
    a = ['blastn', '-dust', '20 64 1', '-out', 'synthetic/UNKNOWN result with spaces.asn', '-penalty', '-3']
    b = ['blastn', '-penalty', '-3', '-out', 'synthetic/UNKNOWN result with spaces.asn', '-dust', '20 64 1']
    result = cal.compare_qa_m_argv(a, b, help_text=_U06_SEARCH_HELP)
    assert result['correspondence'] is True and result['state'] == 'NOT_TESTED'

# U07 metadata is directly constructed software input. No fixture or command is materialized.
_U07_COMPONENT_NAMES = ('cross_references', 'hashes', 'roles', 'parameters', 'tolerance_fields', 'qa',
                      'scale_decisions', 'authorization', 'precedence', 'finite_input_inventory',
                      'availability_regimes', 'freeze_commit', 'snapshot', 'verified_transport', 'allow_dirty')


def _u07_hash(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')).hexdigest()


def _u07_bind(envelope):
    envelope['hashes'] = {'components': {name: _u07_hash(envelope[name]) for name in _U07_COMPONENT_NAMES if name != 'hashes'},
                          'files': {entry['path']: entry['sha256'] for entry in envelope['finite_input_inventory']}}
    return envelope


def _u07_envelope():
    candidates = []
    for task in ('blastn', 'blastn-short', 'dc-megablast'):
        payload, rows, records, command_envelope = _u06_search_inputs()
        payload['search_parameters']['task'] = task
        rows, records = _section7_test_declarations(payload)
        candidates.append({'payload': payload, 'parameter_records': records, 'command_envelope': command_envelope, 'help_text': _U06_SEARCH_HELP})
    candidate_hashes = [_u07_hash(c['payload']) for c in candidates]
    commit = 'a' * 40
    paths = ['docs/implementation/synthetic/authority.json', 'data/external/nto/synthetic/tuning.bin', 'data/external/nto/synthetic/validation.bin']
    inventory = [{'path': path, 'role': 'SYNTHETIC_SOFTWARE_DECLARATION', 'size_bytes': 3,
                  'sha256': hashlib.sha256(b'{}\n').hexdigest(), 'regime': 'TRACKED_COMMIT_BLOB' if i == 0 else 'VERIFIED_BYTE_COPY',
                  **({'commit': commit} if i == 0 else {})} for i, path in enumerate(paths)]
    tolerances = [{'fixture_id': fixture, 'candidate_payload_sha256': candidate, 'instance_id': 'PC01_TEST',
                   'pattern': {'bases': 'AAAA', 'differences': [], 'gaps': []},
                   'expected_coordinates': {'query': [1, 4], 'subject': [1, 4]}, 'orientation': 'PLUS',
                   'comparison_object': 'SYNTHETIC_EXACT_INTERVAL', 'fragmentation_rule': 'SYNTHETIC_NO_CONCATENATION',
                   'unit': 'nt', 'applicable_endpoints': ['qstart', 'qend', 'sstart', 'send'],
                   'numeric_by_endpoint': {'qstart': 0, 'qend': 0, 'sstart': 0, 'send': 0},
                   'independent_justification': 'Analytical software input; unknown biological applicability.'}
                  for fixture in ('FX_T', 'FX_V') for candidate in candidate_hashes]
    envelope = {
        'cross_references': {'required_paths': paths, 'fixture_ids': ['FX_T', 'FX_V'], 'candidate_payload_sha256s': candidate_hashes,
                             'applicable_tolerances': [[t['fixture_id'], t['instance_id'], t['candidate_payload_sha256']] for t in tolerances]},
        'roles': {'TUNING': ['FX_T'], 'VALIDATION': ['FX_V']},
        'parameters': {'parameter_rows': rows, 'candidates': candidates, 'design_space_declaration': 'COMPLETE_SYNTHETIC_SOFTWARE_TEST_ONLY'},
        'tolerance_fields': tolerances,
        'qa': {qid: {'qa_id': qid, 'criterion': 'SYNTHETIC_CRITERION', 'metric': 'SYNTHETIC_METRIC',
                     'expected_behavior': 'DECLARED_SOFTWARE_INPUT', 'fixture_dependency': 'FX_T, FX_V',
                     'biological_decision_role': 'false', 'blocks_configuration_freeze': 'NO' if qid in ('QA-H', 'QA-O', 'QA-R') else 'YES',
                     'status': 'NOT_TESTED'} for qid in cal.E05_QA_SPEC},
        'scale_decisions': {name: {'state': 'DECLARED', 'reference': paths[0], 'disposition': 'SYNTHETIC_SOFTWARE_TEST_ONLY'}
                            for name in ('I01', 'I02', 'I03', 'I04', 'PC13', 'F07', 'B4-8', 'B4-9')},
        'authorization': {'authorized_stages': ['E08'], 'reference': paths[0]},
        'precedence': ['G0', 'APPROVED_METHOD_AND_DESIGN', 'MATERIALIZED_FIXTURES_AND_CANDIDATES', 'NUMERIC_TOLERANCES',
                       'PREFREEZE', 'FREEZE_COMMIT', 'MATCHING_SNAPSHOT', 'VERIFIED_TRANSPORT', 'FIRST_INFORMATIVE_COMMAND'],
        'finite_input_inventory': inventory,
        'availability_regimes': {entry['path']: entry['regime'] for entry in inventory},
        'freeze_commit': commit,
        'snapshot': {'commit': commit, 'path': 'artifacts/reproducibility/synthetic/snapshot.json', 'sha256': 'b' * 64},
        'verified_transport': {'commit': commit, 'snapshot_sha256': 'b' * 64, 'independent_copies': True,
                               'hardlinks': False, 'alternates': False,
                               'files': {entry['path']: {'sha256': entry['sha256'], 'size_bytes': entry['size_bytes']} for entry in inventory}},
        'allow_dirty': False,
    }
    return _u07_bind(envelope)


def test_u07_complete_declarations_never_produce_freeze_or_authorization(monkeypatch):
    assert cal.E07_COMPONENTS == _U07_COMPONENT_NAMES
    envelope = _u07_envelope()
    before = r.json_bytes(envelope)
    def forbidden(*args, **kwargs):
        pytest.fail('declarative barrier attempted an external operation')
    monkeypatch.setattr(cal.subprocess, 'run', forbidden)
    monkeypatch.setattr(cal, 'write_json', forbidden)
    monkeypatch.setattr(cal, 'datetime', None)
    result = cal.evaluate_e07_preconditions(envelope)
    assert result['state'] == 'PRECONDICOES_DECLARADAS_COMPLETAS', result
    assert result['blocking_components'] == [] and result['blocking_parameters'] == []
    assert result['freeze_produced'] is False and result['informative_command_allowed'] is False and result['authority_verified'] is False
    assert result['closure_scope'] == 'COMPUTATIONAL_PREDICATES_ON_SUPPLIED_DECLARATIONS'
    assert result['limitations'] and r.json_bytes(envelope) == before
    assert not ({'utc', 'freeze_id', 'freeze_timestamp_utc', 'version', 'schema_version', 'receipt', 'closed_receipt'} & set(result))


@pytest.mark.parametrize('component', _U07_COMPONENT_NAMES)
@pytest.mark.parametrize('operation', ['remove', 'alter'])
def test_u07_every_required_component_removal_and_alteration_refuses(component, operation):
    envelope = _u07_envelope()
    if operation == 'remove':
        del envelope[component]
    else:
        envelope[component] = True if component == 'allow_dirty' else {'ALTERED': True}
    result = cal.evaluate_e07_preconditions(envelope)
    assert result['state'] == 'RECUSADO'
    assert component in {b['component'] for b in result['blocking_components']}
    assert result['freeze_produced'] is False and result['informative_command_allowed'] is False


@pytest.mark.parametrize('case,component', [
    ('dirty', 'allow_dirty'), ('roles_overlap', 'roles'), ('parameter_pending', 'parameters'),
    ('command_origin_missing', 'parameters'), ('tolerance_missing', 'tolerance_fields'), ('tolerance_pending', 'tolerance_fields'),
    ('qa_missing', 'qa'), ('qa_promoted', 'qa'), ('characterization_promoted', 'qa'), ('scale_pending', 'scale_decisions'),
    ('authorization_scope', 'authorization'), ('order_reversed', 'precedence'), ('inventory_escape', 'finite_input_inventory'),
    ('regime_changed', 'availability_regimes'), ('snapshot_commit', 'snapshot'), ('transport_file', 'verified_transport'),
    ('hardlink', 'verified_transport'), ('unlisted_file', 'cross_references'), ('file_hash_changed', 'hashes'),
])
def test_u07_inconsistencies_still_refuse_after_rebinding_component_hashes(case, component):
    e = _u07_envelope()
    if case == 'dirty': e['allow_dirty'] = True
    elif case == 'roles_overlap': e['roles']['VALIDATION'] = ['FX_T']
    elif case == 'parameter_pending': e['parameters']['candidates'][0]['payload']['search_parameters']['max_target_seqs'] = None
    elif case == 'command_origin_missing': del e['parameters']['candidates'][0]['command_envelope']['flag_provenance']['-task']
    elif case == 'tolerance_missing': e['tolerance_fields'].pop()
    elif case == 'tolerance_pending': e['tolerance_fields'][0]['numeric_by_endpoint']['qstart'] = None
    elif case == 'qa_missing': del e['qa']['QA-M']
    elif case == 'qa_promoted': e['qa']['QA-I']['status'] = 'PASS'
    elif case == 'characterization_promoted': e['qa']['QA-H']['blocks_configuration_freeze'] = 'YES'
    elif case == 'scale_pending': e['scale_decisions']['B4-8']['state'] = 'PENDING'
    elif case == 'authorization_scope': e['authorization']['authorized_stages'] = ['E07']
    elif case == 'order_reversed': e['precedence'][2:4] = reversed(e['precedence'][2:4])
    elif case == 'inventory_escape': e['finite_input_inventory'][0]['path'] = '../outside'
    elif case == 'regime_changed': e['availability_regimes'][e['finite_input_inventory'][0]['path']] = 'REMATERIALIZE'
    elif case == 'snapshot_commit': e['snapshot']['commit'] = 'c' * 40
    elif case == 'transport_file': e['verified_transport']['files'].pop(e['finite_input_inventory'][1]['path'])
    elif case == 'hardlink': e['verified_transport']['hardlinks'] = True
    elif case == 'unlisted_file': e['cross_references']['required_paths'].append('data/external/nto/synthetic/unlisted.bin')
    _u07_bind(e)
    if case == 'file_hash_changed': e['hashes']['files'][e['finite_input_inventory'][0]['path']] = '0' * 64
    result = cal.evaluate_e07_preconditions(e)
    assert result['state'] == 'RECUSADO' and component in {b['component'] for b in result['blocking_components']}, result
    assert result['freeze_produced'] is False and result['authority_verified'] is False


def test_u07_empty_envelope_enumerates_every_missing_component():
    result = cal.evaluate_e07_preconditions({})
    assert {b['component'] for b in result['blocking_components']} == set(_U07_COMPONENT_NAMES)
    assert result['state'] == 'RECUSADO' and result['freeze_produced'] is False


def test_u07_actual_declared_state_refuses_without_opening_cp1_sequences_or_invoking_tools(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    inventory_path = 'artifacts/validation/nb04_cp1_prefreeze/20261025T082358Z/preservation_inventory.json'
    if not (root / inventory_path).is_file():
        pytest.skip('operator-local preserved declarations unavailable outside canonical checkout')
    def forbidden(*args, **kwargs):
        pytest.fail('real-state declaration inspection attempted an external operation')
    monkeypatch.setattr(cal.subprocess, 'run', forbidden)
    monkeypatch.setattr(cal, 'write_json', forbidden)
    real_open = Path.open
    def guarded_open(path, *args, **kwargs):
        if 'cp1_20261015' in path.parts and path.suffix != '.json':
            pytest.fail('real-state barrier attempted to open a CP1 sequence, map or index')
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_open)
    result = cal.inspect_e07_declared_state(root, inventory_path, 'b8c791bc24fec382823a9d1695c93c94affb62eb90ff7e21f4603b243a3bef55')
    assert result['state'] == 'RECUSADO' and result['freeze_produced'] is False
    assert result['informative_command_allowed'] is False and result['authority_verified'] is False
    assert {b['component'] for b in result['blocking_components']} >= {'parameters', 'tolerance_fields', 'authorization', 'scale_decisions', 'precedence', 'finite_input_inventory', 'freeze_commit', 'snapshot', 'verified_transport', 'allow_dirty'}
    pending = {'P02', 'P03', 'P04', 'P07', 'P08', 'P13', 'P14', 'P27', 'P29'}
    assert set(result['preserved_source_evidence']['pending_calibration_parameter_ids']) == pending
    assert {b['parameter_id'] for b in result['blocking_parameters']} >= pending
    assert set(result['unresolved_decision_ids']) == {'I01', 'I02', 'I03', 'I04', 'PC13', 'F07', 'B4-8', 'B4-9'}
    assert result['preserved_source_evidence']['g0_read_only_verification'] == 'G0_PASS'

@pytest.mark.parametrize('invalid', [None, [], {'extra': True}, {1: 'invalid key'}])
def test_u07_malformed_envelope_refuses_and_still_enumerates_components(invalid):
    result = cal.evaluate_e07_preconditions(invalid)
    assert result['state'] == 'RECUSADO' and result['envelope_errors']
    assert {b['component'] for b in result['blocking_components']} == set(_U07_COMPONENT_NAMES)
    assert result['freeze_produced'] is False


@pytest.mark.parametrize('number', [-1, True, float('nan'), float('inf')])
def test_u07_invalid_numeric_tolerance_refuses_even_with_matching_bindings(number):
    envelope = _u07_envelope()
    envelope['tolerance_fields'][0]['numeric_by_endpoint']['qstart'] = number
    _u07_bind(envelope)
    result = cal.evaluate_e07_preconditions(envelope)
    assert result['state'] == 'RECUSADO'
    assert 'tolerance_fields' in {b['component'] for b in result['blocking_components']}

@pytest.mark.parametrize('swap', [(0, 1), (6, 7)])
def test_u07_independent_declared_events_can_exchange_order(swap):
    e = _u07_envelope()
    first, second = swap
    e['precedence'][first], e['precedence'][second] = e['precedence'][second], e['precedence'][first]
    _u07_bind(e)
    result = cal.evaluate_e07_preconditions(e)
    assert result['state'] == 'PRECONDICOES_DECLARADAS_COMPLETAS', result
    assert result['freeze_produced'] is False and result['informative_command_allowed'] is False

@pytest.mark.parametrize('field,empty', [('instance_id', ''), ('comparison_object', ' '), ('fragmentation_rule', ''),
                                       ('pattern', {}), ('expected_coordinates', {}), ('orientation', 'UNKNOWN')])
def test_u07_required_tolerance_descriptors_cannot_be_empty(field, empty):
    envelope = _u07_envelope()
    envelope['tolerance_fields'][0][field] = empty
    _u07_bind(envelope)
    result = cal.evaluate_e07_preconditions(envelope)
    assert result['state'] == 'RECUSADO'
    assert 'tolerance_fields' in {b['component'] for b in result['blocking_components']}

@pytest.mark.parametrize('index,regime', [(0, 'VERIFIED_BYTE_COPY'), (1, 'TRACKED_COMMIT_BLOB')])
def test_u07_regime_cannot_bypass_the_existing_phase_file_classification(index, regime):
    e = _u07_envelope()
    entry = e['finite_input_inventory'][index]
    entry['regime'] = regime
    entry['commit'] = e['freeze_commit']
    e['availability_regimes'][entry['path']] = regime
    _u07_bind(e)
    result = cal.evaluate_e07_preconditions(e)
    assert result['state'] == 'RECUSADO'
    assert 'finite_input_inventory' in {b['component'] for b in result['blocking_components']}

@pytest.mark.parametrize('case,component', [('qa_status_conflict', 'qa'), ('transport_bool_size', 'verified_transport')])
def test_u07_conflicting_or_differently_typed_declarations_refuse(case, component):
    e = _u07_envelope()
    if case == 'qa_status_conflict':
        e['qa']['QA-M']['state_after_e05_part1'] = 'PASS'
    else:
        path = e['finite_input_inventory'][1]['path']
        e['finite_input_inventory'][1]['size_bytes'] = 1
        e['verified_transport']['files'][path]['size_bytes'] = True
    _u07_bind(e)
    result = cal.evaluate_e07_preconditions(e)
    assert result['state'] == 'RECUSADO'
    assert component in {b['component'] for b in result['blocking_components']}
