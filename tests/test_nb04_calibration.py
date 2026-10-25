"""Unit tests for NB04 CP1 E01 preservation control and execution scope.

Uses tiny, non-informative synthetic fixtures and simulated tool probes.
Never invokes real BLAST searches, index builds, or calibration runs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from zeaguard import nb04_calibration as cal
from zeaguard import nb04_resources as r


def _sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_lf(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


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


