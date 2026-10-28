"""NB04 CP1 pre-freeze preservation control, execution scope, geometry, and E05 Part 1 inspection (E01, E03, E05).

Re-executable verification of G0 certified artifacts, the 43 normative documents,
the six frozen CP1 resources and their BLAST index volumes, historical snapshots,
observed BLAST tool builds, the closed dirty-tree allowlist, read-only
derivation of NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 records for the six resources,
and E05 Part 1 read-only tool build and parameter matrix configuration inspection.
No BLAST query, index build, fixture materialization, or calibration is executed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from zeaguard.nb04_resources import (
    ASSESSABILITY,
    CP1,
    DNA,
    G0_PATH,
    INVENTORY,
    MANIFEST,
    REGISTRY,
    RESOURCE_ID,
    ResourceContractError,
    digest,
    json_bytes,
    relative_path,
    require,
    verify_g0,
    write_json,
)

EXECUTION_SCOPE_PATH = "data/reference/nb04_calibration_execution_scope.json"
PRESERVATION_INVENTORY_DIR = "artifacts/validation/nb04_cp1_prefreeze"
PRESERVATION_INVENTORY_FILENAME = "preservation_inventory.json"

PLAN_V003_PATH = "docs/implementation/NB04_CP1_PREPARACAO_FREEZE_B4/plan_v003.md"
PLAN_V003_SHA256 = "dfaac13bd97ac0e9504dcd97443d0286a872b92046881f60fbf8e5fcdd43c72b"
EVALUATOR_OPINION_V003_PATH = "docs/implementation/NB04_CP1_PREPARACAO_FREEZE_B4/parecer_avaliador_v003.md"
EVALUATOR_OPINION_V003_SHA256 = "8b066d884b2044064f1c0d93a8f64a0e28c455b152bd76334da3fb083a346907"

PLAN_SECTION_2_GITIGNORE_RAW_SHA256 = "a40c0c295b5f1a6f31b8cd7f576307c0bc62aaa561bf43631c20fdbec21eed44"
E01_BASELINE_GITIGNORE_RAW_SHA256 = "2ed210bb34cedb631968097b078434ff4322a6cc6bdafcfbf6d34cf797fbce6a"

EXPECTED_G0_CERTIFICATE_SHA256 = "4f4ebd05ad1bf3005ac9796f0d7b3f075c03e7f67de2c02444d349dae8f6fad1"
REAL_CP1_MANIFEST_SHA256 = "2988284ac3e8a5c790f820dab479dacd5c9834f434eda5c9f6b9076fa2a99c52"
EXPECTED_CP1_REFERENCE_SHA256: dict[str, str] = {
    MANIFEST: REAL_CP1_MANIFEST_SHA256,
    INVENTORY: "f11ab874762ccd2b23fe8cbff0bdd2eaa4ead64d416893dcf4a6601aae13c027",
    REGISTRY: "fd4eb4f92898cbe7447c4c7f4ac7db2424613a1eba19f300e3bd559c13580a5a",
    ASSESSABILITY: "d81b50cb1da60f3692deb13c28912ad081f017e1deb1627cf0a4b927ef1807db",
}
EXPECTED_CP1_RESOURCE_IDS: tuple[str, ...] = (
    "AM_GCF003254395_2_RNA",
    "OI_GCYL01_TSA",
    "PM_GKDL01_TSA",
    "RM_GCF003676215_2_RNA",
    "TA_GCA036937485_2_CDS",
    "ZM_GCF902167145_1_RNA",
)
EXPECTED_CP1_RUN_MANIFEST_PATH = f"{CP1}/run_manifest.json"
EXPECTED_CP1_RUN_MANIFEST_SHA256 = "b050ea0123a299c4516527d01279186306a2770470ad034455e8f2d7468440fb"
EXPECTED_LATEST_POINTER_PATH = "artifacts/reproducibility/latest.json"
EXPECTED_LATEST_POINTER_SHA256 = "c14960d556afdbe2fe94b1893f20af7824b93df0b2cd969064f8276cd6a62b08"
EXPECTED_CP1_SNAPSHOT_PATH = "artifacts/reproducibility/20261015T082821773339Z_e37481d6d154/snapshot.json"
EXPECTED_CP1_SNAPSHOT_SHA256 = "c4ddbbabb42092ebcf24a2e8cbcd972995374d7b241185fc48007de5a27955c3"

HISTORICAL_CP1_PROTECTED_CODE_PATHS: tuple[str, ...] = (
    "src/zeaguard/nb04_resources.py",
    "scripts/run_nb04_cp1.py",
    "scripts/inventory_nb04_cp1.py",
)

PREPARATION_IMPLEMENTATION_PATHS: tuple[str, ...] = (
    "src/zeaguard/nb04_calibration.py",
    "scripts/prepare_nb04_calibration.py",
    "scripts/run_nb04_calibration.py",
    "tests/test_nb04_calibration.py",
)

PREPARATION_REFERENCE_ARTIFACT_PATHS: tuple[str, ...] = (
    EXECUTION_SCOPE_PATH,
    "data/reference/nb04_cp1_resource_review.json",
    "data/reference/nb04_calibration_fixture_catalog.json",
    "data/reference/nb04_calibration_candidate_configurations.json",
    "data/reference/nb04_calibration_tolerances.json",
    "data/reference/nb04_calibration_prefreeze.json",
)

POST_E08_VERSIONED_EXPORT_PATHS: tuple[str, ...] = (
    "data/reference/nb04_nto_search_configuration.json",
    "data/reference/nb04_nto_search_calibration.tsv",
)

CLOSED_PREPARATION_DIRTY_ALLOWLIST: tuple[str, ...] = (
    ".gitignore",
    *PREPARATION_IMPLEMENTATION_PATHS,
    *PREPARATION_REFERENCE_ARTIFACT_PATHS,
)

BLOCKED_OPERATIONS: tuple[str, ...] = (
    "INFORMATIVE_CALIBRATION",
    "REAL_NTO_SEARCHES",
    "E08_CALIBRATION_EXECUTION",
    "E09_G1_CERTIFICATION",
    "G1_CERTIFICATION_DECLARATION",
    "SYNTHETIC_FIXTURE_MATERIALIZATION",
    "BLAST_INDEX_BUILD_FOR_FIXTURES_OR_RESOURCES",
)

BLAST_TOOLS: tuple[str, ...] = ("blastn", "makeblastdb", "blastdbcmd")
# dustmasker reports its own tool version ("dustmasker: 1.0.0") under the shared BLAST package build.
INDEPENDENTLY_VERSIONED_TOOLS: frozenset[str] = frozenset({"dustmasker"})
_BLAST_VERSION_RE = re.compile(
    r"^\s*([A-Za-z0-9_+-]+):\s*(\S+)\s*\r?\n\s*Package:\s*([^,\r\n]+),\s*build\s+([^\r\n]+)\s*$"
)

IN_REPO_B6_A1_RELATIVE_PATH = "src/workstreams/bioinformatics/decisions/B6_GOVERNANCE_AMENDMENT_A1.md"

# Explicit declaration of the 43 G0 normative documents (no personal filesystem paths).
NORMATIVE_DOCUMENTS_SPEC: dict[str, dict[str, str | None]] = {
    "01_PLAN_v2.2.5.md": {
        "expected_sha256": "9b759f71de500f65947bb150db71a5d20029da06971a26f7e20d1c72193dc83a",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "02_B3_L4_REVIEW_v2.md": {
        "expected_sha256": "e8b4c4269a60bcaab97aa58a5b9936ed4d80e03233a41cf217cdd0f91a715ea4",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "03_B3_L4_METHOD_DECISION_MEMO_v2.md": {
        "expected_sha256": "580da72ed08859523ba2d079c249c4a75b59cb282c79e4c768eaffc26fabe70e",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "04_parameter_classification_v2.tsv": {
        "expected_sha256": "8203ca35bf290700c6d7ac541c1e953dfbe6ae33b91ed1c936e1ebbd9d10f45d",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md": {
        "expected_sha256": "aa156f77f02b618b878c8f4acac84bf45b36407c86ec9a674e2d5eb82ec3b91a",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "06_B4_TRUNCATION_AND_COMPLETENESS_CONTRACT_v2_1.md": {
        "expected_sha256": "9e559f9f3dac621afafb2dff53f7c392a439a76d1ed13bd031a5eb17ce174851",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "07_B4_TECHNICAL_DECISION_MEMO_v2_1_2.md": {
        "expected_sha256": "8e2ab29a2f08f13bd31076879e965205a732e2929156759c7e29e1b7dfdb5273",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "08_b4_calibration_parameter_matrix_v2_1.tsv": {
        "expected_sha256": "7731fa6bc8f4523f65d37c130e23885bab4358968ea655b2987712db160b8690",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "09_b4_calibration_qa_matrix_v2.tsv": {
        "expected_sha256": "db59d77f44ec6be32962f25cb4da1e3b4f7c58c3c9c1a55348ba4581d57608b0",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "10_l1_l2_l3_l8_ecological_evidence_v2.tsv": {
        "expected_sha256": "a253e6e2a1cde375e19e2457271683412cea7133673e7a3f23b275fe6b48494f",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "11_nto_candidate_receptors_precontract_v2.tsv": {
        "expected_sha256": "870e468d626fef05248e05da76ebb184f2604131fd2162ce0f06c2db8b53d72a",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "12_mandatory_category_closure_v2.tsv": {
        "expected_sha256": "04b3e7773186926942e9b4fecd087615c7a8a47518b20bb3b02746ce045a6505",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "13_l9a_pre_g0_resource_landscape_v2.tsv": {
        "expected_sha256": "68af318ed95fb4bbc808a8b2f249c0ed7ab59d15c0838844e25e67fae9ad0eab",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "14_l9a_resource_landscape_metadata_v2.tsv": {
        "expected_sha256": "c9aa0ceb988e440202c0b5e555ce341d3ffa10a2772170b993ec82d5a97bd7ed",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "15_SOURCE_AUDIT_v2.md": {
        "expected_sha256": "dd0d285366b4e73a4b3c7caad5da6024ecc4c7bae6c9bf7783dff06888d403c9",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "16_l4_b3_methodological_evidence_v2.tsv": {
        "expected_sha256": "9e26cc3b6c386fb5c6bd050f1264f924f66a98e9556d6dd4b83809e4b78ef61c",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "17_B4_V2_1_2_CHANGELOG.md": {
        "expected_sha256": "e99592617674668c4c6b9a00f1f3fc8563057e6fd91ef82fa553773d5a98d9d7",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "18_b4_fixture_spec_v2.tsv": {
        "expected_sha256": "1beb9845b357a279fca11d1ba317d91f79a84d7fdb3501169daa4c9229d6ad2c",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_INPUTS",
        "repository_relative_path": None,
    },
    "B4_CALIBRATION_AMENDMENT_A1.md": {
        "expected_sha256": "0c1815be37ca6187639a27429fc0b38adb3f4be762f773f17a159f29b38f0ecc",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_20261014_AMENDMENTS_AND_CLOSURE",
        "repository_relative_path": None,
    },
    "B5_CONCERN_CRITERIA_REVIEW.md": {
        "expected_sha256": "ed7fd88c6ed8655d0c7b320bf21c618ef15ef11c478a60ec375436fcd4e37eb1",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "B5_METHOD_DECISION_MEMO.md": {
        "expected_sha256": "179d262a41608af4759e95a918e702bce7477c88416618381d23d6ca97bcf57a",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "B5_SOURCE_AUDIT.md": {
        "expected_sha256": "ab02e65e2e8383940949bb328984fb49f332f342a7d328a5ed153cbe6d495be8",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "B6_GOVERNANCE_AMENDMENT_A1.md": {
        "expected_sha256": "9ea167a88359f78e916d753865d7d40a5c37d2ff04d3a09d73c647c3aebaa62b",
        "hash_mode": "RAW",
        "location_class": "IN_REPOSITORY",
        "corpus_id": "REPOSITORY_DECISIONS",
        "repository_relative_path": IN_REPO_B6_A1_RELATIVE_PATH,
    },
    "B6_GOVERNANCE_REVIEW.md": {
        "expected_sha256": "b239e42bcc8cede524418a4866aadc32ae6f3f081ee89592167156c23e4a0b20",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "B6_METHOD_DECISION_MEMO.md": {
        "expected_sha256": "6488b8cfc9bdab5d870402358f1fe955d050552ef3f586a30b24f69dee49dc00",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "B6_SOURCE_AUDIT.md": {
        "expected_sha256": "591270f9abb8bd90049cbd11b9dcab519c17aba9537dbcd4a4ebb7cbaf0bae60",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "NB04_CP0_COMPLEMENTARY_CONTRACT_PROPOSAL.md": {
        "expected_sha256": "617438b9bf5a0a4dd2e80fc832af288432060899e5f615384df3e306bb919c68",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_20261014_AMENDMENTS_AND_CLOSURE",
        "repository_relative_path": None,
    },
    "NB04_CP0_COMPLEMENTARY_INDEPENDENT_AUDIT.md": {
        "expected_sha256": "277ac250c6f66a0ff0d451682f75b08d325a33bd58d7d476a374ff2c22581572",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_20261014_AMENDMENTS_AND_CLOSURE",
        "repository_relative_path": None,
    },
    "NB04_CP0_COMPLEMENTARY_RATIFICATION_RECORD.md": {
        "expected_sha256": "a0b3d81d2d94351663a758603470509c91d81d2fdf30e9519c3bf2bbc66d9232",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_20261014_AMENDMENTS_AND_CLOSURE",
        "repository_relative_path": None,
    },
    "NB04_PREAPPROVAL_CLOSURE.md": {
        "expected_sha256": "52b54d4fa633b2847818e7382e57fdbf9c1ec73588f662c93fb30f56aa7f618b",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_20261014_AMENDMENTS_AND_CLOSURE",
        "repository_relative_path": None,
    },
    "b5_adjudication_matrix.tsv": {
        "expected_sha256": "cf28f1c388fd8a94de6477bf5afc552a6b2200db4ab06418db24ed8782b145a6",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "b5_concern_methodological_evidence.tsv": {
        "expected_sha256": "2b102d6ccddbe0f3e863e4022f91bdd89d5838395477d20f1b9ffca678558618",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "b5_review_trigger_registry.tsv": {
        "expected_sha256": "1058163a9294f3a114053b3213e418521fa2ccb95a6fece05219bac2cfd28146",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "b5_rule_classification.tsv": {
        "expected_sha256": "1a60e1ad00e201d26d4270a90af83a7f498bc58d4a80075971061352d3453636",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "b5_state_machine.tsv": {
        "expected_sha256": "9737888ce5633e890dfb394d18362167da8f0d3e16a5ddb01339e7593f89b3bb",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B5_REVIEW",
        "repository_relative_path": None,
    },
    "b6_amendment_matrix.tsv": {
        "expected_sha256": "bfae1f4685c5af44f836ba567f823c52fd1d041cfead3002b03eaab732e24f57",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_competency_matrix.tsv": {
        "expected_sha256": "1a6b16410d87a25fed0a2d3d83cc81a0af36356dbf9250196f44d2aea15a1670",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_disagreement_resolution.tsv": {
        "expected_sha256": "c6362ede9b0af46149072a0b2a0821980aca1c3b461ffc22657b0e998554a983",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_governance_methodological_evidence.tsv": {
        "expected_sha256": "2d31e1b6b499d7784e03cd80012a4a36ca4cef786b09dbad744266c724e81ff8",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_review_governance_matrix.tsv": {
        "expected_sha256": "bca35004c5306d3a6eb6b1f639c6fcd608d9cacb3f100b359329a3fbd02993a3",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_review_workflow.tsv": {
        "expected_sha256": "0c955d310013d820997c73a8f3bd44329868fad7b9845344002cf9764be9bb51",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_role_registry.tsv": {
        "expected_sha256": "005309631796d173f2fd747e94b665d4447fafd4d011c55da792c0b1c032d272",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
    "b6_signoff_contract.tsv": {
        "expected_sha256": "22da08f61ec6daef53fafe4e0dd5da2c6379d41d1b3a0798ea7235b4cfb322df",
        "hash_mode": "RAW",
        "location_class": "EXTERNAL_LOCAL_CORPUS",
        "corpus_id": "NB04_B6_REVIEW",
        "repository_relative_path": None,
    },
}


def _git_output(root: Path, *args: str) -> str:
    require(
        bool(args) and args[0] in {"rev-parse", "branch", "status", "diff", "show"},
        "only read-only Git inspection commands are permitted in E01",
    )
    local_autocrlf = subprocess.run(
        ["git", "-C", str(root), "config", "--local", "--get", "core.autocrlf"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    git_cmd = ["git", "-C", str(root)]
    if local_autocrlf.returncode != 0 or not local_autocrlf.stdout.strip():
        git_cmd.extend(["-c", "core.autocrlf=true"])
    git_cmd.extend(args)
    completed = subprocess.run(
        git_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    require(completed.returncode == 0, f"git {args[0]} failed: {completed.stderr.strip()}")
    return completed.stdout


def _unquote_git_path(path_text: str) -> str:
    if len(path_text) >= 2 and path_text.startswith('"') and path_text.endswith('"'):
        inner = path_text[1:-1]
        return bytes(inner, "utf-8").decode("unicode_escape").encode("latin1").decode("utf-8", errors="replace")
    return path_text


def _parse_porcelain_paths(porcelain_output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if "\x00" in porcelain_output:
        tokens = porcelain_output.split("\x00")
        if tokens and tokens[-1] == "":
            tokens.pop()
        idx = 0
        while idx < len(tokens):
            token = tokens[idx]
            idx += 1
            if not token:
                continue
            require(
                len(token) >= 4 and token[2] == " ",
                f"malformed git status -z entry: {token!r}",
            )
            status_code = token[:2]
            path_part = token[3:]
            if "R" in status_code or "C" in status_code:
                require(
                    idx < len(tokens) and bool(tokens[idx]),
                    f"missing source path in git status -z rename/copy entry: {token!r}",
                )
                orig_path = tokens[idx]
                idx += 1
                entries.append({"status": status_code, "path": orig_path})
                entries.append({"status": status_code, "path": path_part})
            else:
                entries.append({"status": status_code, "path": path_part})
        return entries

    for raw_line in porcelain_output.splitlines():
        if not raw_line:
            continue
        require(
            len(raw_line) >= 4 and raw_line[2] == " ",
            f"malformed git status porcelain line: {raw_line!r}",
        )
        status_code = raw_line[:2]
        path_part = raw_line[3:].strip()
        if ("R" in status_code or "C" in status_code) and " -> " in path_part:
            orig_part, dest_part = path_part.split(" -> ", 1)
            entries.append({"status": status_code, "path": _unquote_git_path(orig_part.strip())})
            entries.append({"status": status_code, "path": _unquote_git_path(dest_part.strip())})
        else:
            entries.append({"status": status_code, "path": _unquote_git_path(path_part)})
    return entries


def phase_git_and_snapshot_policy() -> dict[str, Any]:
    """Declare file classification and per-phase allow_dirty/snapshot rules (section 8.1)."""
    return {
        "file_classification": {
            "versioned_preparation_code_and_tests": list(PREPARATION_IMPLEMENTATION_PATHS),
            "versioned_preparation_reference_records": list(PREPARATION_REFERENCE_ARTIFACT_PATHS),
            "versioned_post_e08_normative_exports": list(POST_E08_VERSIONED_EXPORT_PATHS),
            "versioned_task_documentation_directory": "docs/implementation/NB04_CP1_PREPARACAO_FREEZE_B4",
            "protected_immutable_historical_cp1_code": list(HISTORICAL_CP1_PROTECTED_CODE_PATHS),
            "ignored_unversioned_campaign_outputs": [
                "data/external/nto",
                "results/bioinformatics/nb04",
                "artifacts/validation/nb04_cp1_prefreeze",
            ],
            "local_uncommitted_preserved_file": ".gitignore",
        },
        "phases": {
            "E01_TO_E07_PREFREEZE_PREPARATION": {
                "allow_dirty": True,
                "allowlist_required": True,
                "closed_dirty_allowlist": list(CLOSED_PREPARATION_DIRTY_ALLOWLIST),
                "repro_checkpoint": "nb04_cp0",
                "snapshot_policy": (
                    "Preserve existing historical snapshots without overwriting; "
                    "dirty working tree is explicitly declared and permitted only within "
                    "CLOSED_PREPARATION_DIRTY_ALLOWLIST."
                ),
                "informative_execution_permitted": False,
            },
            "E08_INFORMATIVE_CALIBRATION_EXECUTION": {
                "allow_dirty": False,
                "allowlist_required": False,
                "closed_dirty_allowlist": [],
                "repro_checkpoint": "nb04_cp0",
                "snapshot_policy": (
                    "Requires prior authorized freeze commit, isolated clean checkout "
                    "(without local .gitignore edit or private directories), a new Linux "
                    "environment snapshot matching the freeze commit, and VERIFIED_BYTE_COPY "
                    "of all ignored frozen inputs (sections 8.1 and 8.2)."
                ),
                "informative_execution_permitted": True,
            },
            "POST_E08_FINAL_ARTIFACT_MATERIALIZATION": {
                "allow_dirty": True,
                "allowlist_required": True,
                "closed_dirty_allowlist": list(POST_E08_VERSIONED_EXPORT_PATHS),
                "repro_checkpoint": "nb04_cp0",
                "snapshot_policy": (
                    "Execution receipts preserve the E08 freeze commit and snapshot; "
                    "dirty state is restricted strictly to the versioned final exports."
                ),
                "informative_execution_permitted": False,
            },
            "E09_G1_CERTIFICATION": {
                "allow_dirty": False,
                "allowlist_required": False,
                "closed_dirty_allowlist": [],
                "repro_checkpoint": "nb04_cp0",
                "snapshot_policy": (
                    "Requires authorized commit of final artifacts, a new Linux environment "
                    "snapshot of that published commit, allow_dirty=False preflight, and "
                    "qualified external human review."
                ),
                "informative_execution_permitted": False,
            },
        },
        "repro_profile_note": (
            "config/repro.yaml and config/repro.schema.json remain unmodified (G0 certified); "
            "no nb04_cp1 profile is added to config/repro.yaml, and checkpoint=None is preserved."
        ),
    }


_DEFAULT = object()


def normative_corpus_declaration(
    corpus_spec: Mapping[str, Mapping[str, str | None]] | None = None,
) -> dict[str, Any]:
    """Build the public-safe normative corpus declaration with location_class and corpus_id."""
    if corpus_spec is None:
        corpus_spec = NORMATIVE_DOCUMENTS_SPEC
    documents: dict[str, dict[str, str | None]] = {}
    corpus_counts: dict[str, int] = {}
    in_repo_count = 0
    external_count = 0
    for name in sorted(corpus_spec):
        entry = corpus_spec[name]
        loc_class = entry["location_class"]
        corpus_id = str(entry["corpus_id"])
        require(
            loc_class in {"IN_REPOSITORY", "EXTERNAL_LOCAL_CORPUS"},
            f"invalid normative location_class for {name}: {loc_class}",
        )
        require(entry.get("hash_mode") == "RAW", f"normative document hash_mode must be RAW: {name}")
        if loc_class == "IN_REPOSITORY":
            in_repo_count += 1
            availability = "VERSIONED_IN_REPOSITORY"
        else:
            external_count += 1
            availability = "LOCAL_TEMPORAL_OPERATOR_SUPPLIED_NOT_VERSIONED"
        corpus_counts[corpus_id] = corpus_counts.get(corpus_id, 0) + 1
        documents[name] = {
            "availability_semantics": availability,
            "corpus_id": corpus_id,
            "expected_sha256": entry["expected_sha256"],
            "hash_mode": "RAW",
            "location_class": loc_class,
            "repository_relative_path": entry.get("repository_relative_path"),
        }
    return {
        "total_documents": len(documents),
        "in_repository_count": in_repo_count,
        "external_local_corpus_count": external_count,
        "logical_corpora_document_counts": dict(sorted(corpus_counts.items())),
        "personal_paths_omitted": True,
        "availability_qualification": (
            "The 42 EXTERNAL_LOCAL_CORPUS documents reside outside version control in operator-supplied "
            "directories; their accessibility is local and temporal to the verification run."
        ),
        "inaccessibility_policy": (
            "Any missing corpus directory mapping or missing/unreadable file produces explicit status "
            "NORMATIVE_DOCUMENT_INACCESSIBLE and fails closed (raises ResourceContractError when strict=True); "
            "inaccessibility is never silently treated as approval."
        ),
        "documents": documents,
    }


def verify_gitignore_and_git_state(
    root: Path,
    *,
    expected_plan_raw_sha256: str | None = None,
    expected_baseline_raw_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify repository Git state and .gitignore RAW identity with byte-reduction proof."""
    root = root.resolve()
    if expected_plan_raw_sha256 is None:
        expected_plan_raw_sha256 = PLAN_SECTION_2_GITIGNORE_RAW_SHA256
    if expected_baseline_raw_sha256 is None:
        expected_baseline_raw_sha256 = E01_BASELINE_GITIGNORE_RAW_SHA256
    gitignore_path = relative_path(root, ".gitignore")
    require(gitignore_path.is_file(), ".gitignore missing from repository root")

    raw_bytes = gitignore_path.read_bytes()
    observed_raw = hashlib.sha256(raw_bytes).hexdigest()
    observed_lf = digest(gitignore_path, normalized=True)

    if b"\ndocs\n" in raw_bytes:
        reduced_bytes = raw_bytes.replace(b"\ndocs\n", b"\n", 1)
    elif b"\r\ndocs\r\n" in raw_bytes:
        reduced_bytes = raw_bytes.replace(b"\r\ndocs\r\n", b"\r\n", 1)
    elif raw_bytes.startswith(b"docs\n"):
        reduced_bytes = raw_bytes[len(b"docs\n") :]
    elif raw_bytes.startswith(b"docs\r\n"):
        reduced_bytes = raw_bytes[len(b"docs\r\n") :]
    else:
        reduced_bytes = raw_bytes

    docs_line_removed = reduced_bytes != raw_bytes
    reduced_raw_sha256 = hashlib.sha256(reduced_bytes).hexdigest() if docs_line_removed else None
    reproduces_plan_hash = bool(
        docs_line_removed
        and reduced_raw_sha256 is not None
        and reduced_raw_sha256 != observed_raw
        and reduced_raw_sha256 == expected_plan_raw_sha256
    )

    if observed_raw == expected_baseline_raw_sha256:
        require(
            reproduces_plan_hash,
            ".gitignore matches E01 baseline hash but single-line 'docs' removal did not produce a distinct byte sequence matching plan section 2 hash",
        )
        verdict = "PASS_EXPLAINED_BASELINE_FIXED"
    elif observed_raw == expected_plan_raw_sha256:
        raise ResourceContractError(
            f".gitignore preservation divergence: observed historical plan_v003.md section 2 hash "
            f"({observed_raw}) without preserved 'docs' line; E01 baseline requires {expected_baseline_raw_sha256}"
        )
    else:
        raise ResourceContractError(
            f"unexplained .gitignore RAW SHA256 divergence: observed={observed_raw}, "
            f"expected_baseline={expected_baseline_raw_sha256}, plan_section_2={expected_plan_raw_sha256}"
        )

    branch = _git_output(root, "branch", "--show-current").strip()
    head = _git_output(root, "rev-parse", "HEAD").strip()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", head)), f"invalid Git HEAD SHA: {head}")
    porcelain_raw = _git_output(root, "status", "--porcelain=v1", "-uall")
    porcelain_z = _git_output(root, "status", "--porcelain=v1", "-z", "-uall")
    porcelain_entries = _parse_porcelain_paths(porcelain_z)

    modified_tracked = sorted(
        {entry["path"] for entry in porcelain_entries if entry["status"] != "??"}
    )
    tracked_diffs: dict[str, dict[str, str]] = {}
    for rel_path in modified_tracked:
        file_path = relative_path(root, rel_path)
        diff_text = _git_output(root, "diff", "HEAD", "--", rel_path)
        tracked_diffs[rel_path] = {
            "diff_from_head": diff_text,
            "observed_raw_sha256": digest(file_path) if file_path.is_file() else "DELETED",
            "observed_lf_sha256": digest(file_path, normalized=True) if file_path.is_file() else "DELETED",
        }

    gitignore_diff_text = tracked_diffs.get(".gitignore", {}).get("diff_from_head") or _git_output(
        root, "diff", "HEAD", "--", ".gitignore"
    )
    observed_diff_added_lines = [
        line[1:].rstrip("\r")
        for line in gitignore_diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]

    return {
        "project_root_name": root.name,
        "branch": branch,
        "head": head,
        "working_tree_dirty": bool(porcelain_entries),
        "git_status_porcelain": [line for line in porcelain_raw.splitlines() if line],
        "modified_tracked_files": modified_tracked,
        "modified_tracked_diffs": tracked_diffs,
        "gitignore_preservation": {
            "path": ".gitignore",
            "plan_section_2_expected_raw_sha256": expected_plan_raw_sha256,
            "current_e01_baseline_raw_sha256": expected_baseline_raw_sha256,
            "observed_raw_sha256": observed_raw,
            "observed_lf_sha256": observed_lf,
            "matches_plan_section_2_raw_sha256": observed_raw == expected_plan_raw_sha256,
            "matches_current_e01_baseline_raw_sha256": observed_raw == expected_baseline_raw_sha256,
            "demonstrated_content_difference": {
                "evidence_class": "DEMONSTRATED_BY_GIT_DIFF_AND_BYTE_REDUCTION",
                "diff_vs_head_added_lines": observed_diff_added_lines,
                "reduction_operation": "REMOVE_SINGLE_LINE_DOCS",
                "removed_line_literal": "docs",
                "docs_line_removed": docs_line_removed,
                "reduced_bytes_raw_sha256": reduced_raw_sha256,
                "reproduces_plan_section_2_expected_raw_sha256": reproduces_plan_hash,
                "statement": (
                    "Removing exclusively the single line 'docs' from the observed .gitignore bytes "
                    f"({observed_raw}) yields distinct RAW SHA256 {reduced_raw_sha256}, which equals "
                    f"the exact plan_v003.md section 2 hash ({expected_plan_raw_sha256})."
                ),
            },
            "reported_attribution": {
                "evidence_class": "REPORTED_CONTEXT_NOT_DEMONSTRATED_BY_GIT_DIFF",
                "statement": (
                    "Coordinator delegation C-01 reports that the repository owner added the 'docs' "
                    "entry after plan_v003.md was drafted; authorship and timestamp of that untracked "
                    "working-tree edit are reported context, not demonstrated by git diff."
                ),
            },
            "verdict": verdict,
        },
    }


def verify_preparation_allowlist(
    root: Path,
    *,
    allowlist: tuple[str, ...] | None = None,
    expected_gitignore_baseline_sha256: str | None = None,
    expected_gitignore_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Enforce the closed section 8.1 allowlist on all dirty tracked and untracked files."""
    root = root.resolve()
    if allowlist is None:
        allowlist = CLOSED_PREPARATION_DIRTY_ALLOWLIST
    if expected_gitignore_baseline_sha256 is None:
        expected_gitignore_baseline_sha256 = E01_BASELINE_GITIGNORE_RAW_SHA256
    if expected_gitignore_plan_sha256 is None:
        expected_gitignore_plan_sha256 = PLAN_SECTION_2_GITIGNORE_RAW_SHA256
    require(bool(allowlist), "closed preparation allowlist cannot be empty")
    allowed_set = set(allowlist)

    porcelain_z = _git_output(root, "status", "--porcelain=v1", "-z", "-uall")
    porcelain_entries = _parse_porcelain_paths(porcelain_z)
    dirty_paths = sorted({entry["path"] for entry in porcelain_entries})
    unauthorized = [path for path in dirty_paths if path not in allowed_set]

    tracked_diffs: dict[str, str] = {}
    dirty_file_hashes: dict[str, dict[str, str | None]] = {}
    for entry in porcelain_entries:
        rel_path = entry["path"]
        file_path = relative_path(root, rel_path)
        if entry["status"] != "??":
            tracked_diffs[rel_path] = _git_output(root, "diff", "HEAD", "--", rel_path)
        if file_path.is_file():
            dirty_file_hashes[rel_path] = {
                "status": entry["status"],
                "raw_sha256": digest(file_path),
                "lf_sha256": digest(file_path, normalized=True),
            }
        else:
            dirty_file_hashes[rel_path] = {
                "status": entry["status"],
                "raw_sha256": None,
                "lf_sha256": None,
            }

    gitignore_file = relative_path(root, ".gitignore")
    require(gitignore_file.is_file(), ".gitignore missing from repository root")
    gitignore_observed_raw = digest(gitignore_file)
    require(
        gitignore_observed_raw == expected_gitignore_baseline_sha256,
        f".gitignore RAW SHA256 diverges from preserved E01 baseline: observed={gitignore_observed_raw} expected={expected_gitignore_baseline_sha256}",
    )

    require(
        not unauthorized,
        f"dirty working-tree files outside closed preparation allowlist: {unauthorized}",
    )

    for protected in HISTORICAL_CP1_PROTECTED_CODE_PATHS:
        require(
            protected not in dirty_file_hashes,
            f"protected historical CP1 file cannot be dirty: {protected}",
        )

    implementation_hashes: dict[str, dict[str, str | bool | None]] = {}
    for rel_path in (*HISTORICAL_CP1_PROTECTED_CODE_PATHS, *PREPARATION_IMPLEMENTATION_PATHS):
        path = relative_path(root, rel_path)
        if path.is_file():
            implementation_hashes[rel_path] = {
                "present": True,
                "raw_sha256": digest(path),
                "lf_sha256": digest(path, normalized=True),
            }
        else:
            implementation_hashes[rel_path] = {
                "present": False,
                "raw_sha256": None,
                "lf_sha256": None,
            }

    return {
        "readiness_allow_dirty": True,
        "closed_allowlist": list(allowlist),
        "dirty_paths_observed": dirty_paths,
        "unauthorized_dirty_paths": unauthorized,
        "dirty_file_hashes": dict(sorted(dirty_file_hashes.items())),
        "tracked_diffs": dict(sorted(tracked_diffs.items())),
        "current_implementation_sha256": implementation_hashes,
        "verdict": "PASS",
    }


def verify_g0_certified_artifacts_inventory(
    root: Path,
    *,
    expected_certificate_sha256: Any = _DEFAULT,
    expected_artifact_count: Any = _DEFAULT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reuse zeaguard.nb04_resources.verify_g0 and record per-artifact verification."""
    root = root.resolve()
    if expected_certificate_sha256 is _DEFAULT:
        expected_certificate_sha256 = EXPECTED_G0_CERTIFICATE_SHA256
    if expected_artifact_count is _DEFAULT:
        expected_artifact_count = 26
    g0_file = relative_path(root, G0_PATH)
    require(g0_file.is_file(), f"G0 certificate missing: {G0_PATH}")
    observed_cert_sha256 = digest(g0_file)
    if expected_certificate_sha256 is not None:
        require(
            observed_cert_sha256 == expected_certificate_sha256,
            f"G0 certificate SHA256 mismatch: expected={expected_certificate_sha256} observed={observed_cert_sha256}",
        )

    certificate = verify_g0(root)
    artifacts = certificate["certified_artifacts"]
    if expected_artifact_count is not None:
        require(
            len(artifacts) == expected_artifact_count,
            f"G0 certified_artifacts count mismatch: expected={expected_artifact_count} observed={len(artifacts)}",
        )

    records: dict[str, dict[str, str]] = {}
    for rel_path in sorted(artifacts):
        entry = artifacts[rel_path]
        hash_mode = entry["hash_mode"]
        path = relative_path(root, rel_path)
        observed = digest(path, normalized=hash_mode == "LF_NORMALIZED")
        require(observed == entry["sha256"], f"G0 artifact changed: {rel_path}")
        records[rel_path] = {
            "hash_mode": hash_mode,
            "expected_sha256": entry["sha256"],
            "observed_sha256": observed,
            "verdict": "PASS",
        }

    summary = {
        "certificate_path": G0_PATH,
        "certificate_id": certificate.get("certification_id"),
        "expected_certificate_sha256": expected_certificate_sha256,
        "observed_certificate_sha256": observed_cert_sha256,
        "gate": certificate["gate"],
        "status": certificate["status"],
        "artifact_count": len(records),
        "artifacts": records,
        "verdict": "PASS",
    }
    return certificate, summary


def verify_normative_documents(
    root: Path,
    certificate: Mapping[str, Any],
    corpus_directories: Mapping[str, Path] | None = None,
    *,
    corpus_spec: Mapping[str, Mapping[str, str | None]] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Verify the 43 G0 normative documents without recording personal paths."""
    root = root.resolve()
    if corpus_spec is None:
        corpus_spec = NORMATIVE_DOCUMENTS_SPEC
    cert_normatives = certificate.get("normative_documents")
    require(
        isinstance(cert_normatives, Mapping) and bool(cert_normatives),
        "G0 certificate normative_documents missing or empty",
    )
    spec_hashes = {name: entry["expected_sha256"] for name, entry in corpus_spec.items()}
    require(
        dict(cert_normatives) == spec_hashes,
        "normative_documents in G0 certificate diverge from declared NORMATIVE_DOCUMENTS_SPEC",
    )

    corpus_dirs = dict(corpus_directories or {})
    results: dict[str, dict[str, Any]] = {}
    inaccessible: list[str] = []
    mismatched: list[str] = []

    for doc_name in sorted(corpus_spec):
        require(
            Path(doc_name).name == doc_name and "/" not in doc_name and "\\" not in doc_name and ".." not in doc_name,
            f"unsafe normative document name: {doc_name}",
        )
        spec = corpus_spec[doc_name]
        expected_sha = str(spec["expected_sha256"])
        loc_class = str(spec["location_class"])
        corpus_id = str(spec["corpus_id"])
        hash_mode = str(spec.get("hash_mode", "RAW"))
        require(hash_mode == "RAW", f"unknown normative hash_mode for {doc_name}: {hash_mode}")

        if loc_class == "IN_REPOSITORY":
            rel_repo = spec.get("repository_relative_path")
            require(isinstance(rel_repo, str) and bool(rel_repo), f"missing repo path for {doc_name}")
            candidate_path = relative_path(root, rel_repo)
            availability_semantics = "VERSIONED_IN_REPOSITORY"
        elif loc_class == "EXTERNAL_LOCAL_CORPUS":
            availability_semantics = "LOCAL_TEMPORAL_OPERATOR_SUPPLIED_NOT_VERSIONED"
            base_dir = corpus_dirs.get(corpus_id)
            if base_dir is None:
                candidate_path = None
            else:
                resolved_base = Path(base_dir).resolve()
                candidate_path = (resolved_base / doc_name).resolve()
                require(
                    candidate_path.is_relative_to(resolved_base),
                    f"normative document path escapes corpus directory: {doc_name}",
                )
        else:
            raise ResourceContractError(f"unknown location_class for {doc_name}: {loc_class}")

        if candidate_path is None or not candidate_path.is_file():
            inaccessible.append(doc_name)
            results[doc_name] = {
                "corpus_id": corpus_id,
                "location_class": loc_class,
                "repository_relative_path": spec.get("repository_relative_path"),
                "availability_semantics": availability_semantics,
                "hash_mode": hash_mode,
                "expected_sha256": expected_sha,
                "observed_sha256": None,
                "status": "NORMATIVE_DOCUMENT_INACCESSIBLE",
                "verdict": "FAIL_INACCESSIBLE",
            }
            continue

        observed_sha = digest(candidate_path)
        if observed_sha != expected_sha:
            mismatched.append(doc_name)
            results[doc_name] = {
                "corpus_id": corpus_id,
                "location_class": loc_class,
                "repository_relative_path": spec.get("repository_relative_path"),
                "availability_semantics": availability_semantics,
                "hash_mode": hash_mode,
                "expected_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "status": "NORMATIVE_DOCUMENT_HASH_MISMATCH",
                "verdict": "FAIL_HASH_MISMATCH",
            }
        else:
            results[doc_name] = {
                "corpus_id": corpus_id,
                "location_class": loc_class,
                "repository_relative_path": spec.get("repository_relative_path"),
                "availability_semantics": availability_semantics,
                "hash_mode": hash_mode,
                "expected_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "status": (
                    "VERIFIED_IN_REPOSITORY"
                    if loc_class == "IN_REPOSITORY"
                    else "VERIFIED_LOCAL_TEMPORAL"
                ),
                "verdict": "PASS",
            }

    if strict:
        require(
            not inaccessible,
            f"NORMATIVE_DOCUMENT_INACCESSIBLE: {inaccessible}",
        )
        require(
            not mismatched,
            f"normative document SHA256 mismatch: {mismatched}",
        )

    overall_verdict = (
        "PASS"
        if not inaccessible and not mismatched
        else "FAIL_INACCESSIBLE"
        if inaccessible
        else "FAIL_HASH_MISMATCH"
    )
    return {
        "total_documents": len(results),
        "verified_count": sum(1 for item in results.values() if item["verdict"] == "PASS"),
        "inaccessible_count": len(inaccessible),
        "inaccessible_documents": inaccessible,
        "mismatch_count": len(mismatched),
        "mismatched_documents": mismatched,
        "personal_paths_omitted": True,
        "availability_qualification": (
            "External normative documents (EXTERNAL_LOCAL_CORPUS) are verified at runtime from "
            "operator-supplied directories; their availability is local and temporal, and future "
            "inaccessibility transitions explicitly to NORMATIVE_DOCUMENT_INACCESSIBLE."
        ),
        "documents": results,
        "verdict": overall_verdict,
    }


def verify_cp1_resources_and_manifests(
    root: Path,
    *,
    expected_reference_sha256: Any = _DEFAULT,
    expected_run_manifest_sha256: Any = _DEFAULT,
    expected_resource_count: Any = _DEFAULT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stream-verify all CP1 reference manifests, 6 resources, FASTA, ID maps, and blastdb volumes."""
    root = root.resolve()
    if expected_reference_sha256 is _DEFAULT:
        expected_reference_sha256 = EXPECTED_CP1_REFERENCE_SHA256
    if expected_run_manifest_sha256 is _DEFAULT:
        expected_run_manifest_sha256 = EXPECTED_CP1_RUN_MANIFEST_SHA256
    if expected_resource_count is _DEFAULT:
        expected_resource_count = 6
    reference_records: dict[str, dict[str, str]] = {}
    ref_expectations = dict(expected_reference_sha256 or {})
    for rel_path in (MANIFEST, INVENTORY, REGISTRY, ASSESSABILITY):
        path = relative_path(root, rel_path)
        require(path.is_file(), f"CP1 reference artifact missing: {rel_path}")
        observed = digest(path)
        expected = ref_expectations.get(rel_path)
        if expected is not None:
            require(
                observed == expected,
                f"CP1 reference artifact hash mismatch for {rel_path}: expected={expected} observed={observed}",
            )
        reference_records[rel_path] = {
            "hash_mode": "RAW",
            "expected_sha256": expected or observed,
            "observed_sha256": observed,
            "verdict": "PASS",
        }

    manifest = json.loads(relative_path(root, MANIFEST).read_text("utf-8"))
    g0_sha = digest(relative_path(root, G0_PATH))
    inv_sha = reference_records[INVENTORY]["observed_sha256"]
    require(
        manifest.get("g0_certificate_sha256") == g0_sha,
        "manifest g0_certificate_sha256 binding mismatch",
    )
    require(
        manifest.get("inventory_sha256") == inv_sha,
        "manifest inventory_sha256 binding mismatch",
    )

    run_manifest_path = relative_path(root, EXPECTED_CP1_RUN_MANIFEST_PATH)
    require(run_manifest_path.is_file(), f"CP1 run_manifest missing: {EXPECTED_CP1_RUN_MANIFEST_PATH}")
    observed_run_manifest_sha = digest(run_manifest_path)
    if expected_run_manifest_sha256 is not None:
        require(
            observed_run_manifest_sha == expected_run_manifest_sha256,
            f"CP1 run_manifest SHA256 mismatch: expected={expected_run_manifest_sha256} observed={observed_run_manifest_sha}",
        )
    run_manifest = json.loads(run_manifest_path.read_text("utf-8"))
    for out_rel, exp_sha in sorted(run_manifest.get("outputs_sha256", {}).items()):
        out_path = relative_path(root, out_rel)
        require(out_path.is_file(), f"CP1 run_manifest output missing: {out_rel}")
        require(digest(out_path) == exp_sha, f"CP1 run_manifest output hash mismatch: {out_rel}")
    for code_rel, exp_lf_sha in sorted(run_manifest.get("implementation_sha256_lf", {}).items()):
        code_path = relative_path(root, code_rel)
        require(code_path.is_file(), f"CP1 implementation file missing: {code_rel}")
        require(
            digest(code_path, normalized=True) == exp_lf_sha,
            f"CP1 protected implementation LF hash changed: {code_rel}",
        )

    resources = manifest.get("resources", [])
    if expected_resource_count is not None:
        require(
            len(resources) == expected_resource_count,
            f"CP1 resource count mismatch: expected={expected_resource_count} observed={len(resources)}",
        )

    nto_root = (root / "data/external/nto").resolve()
    resource_records: dict[str, dict[str, Any]] = {}
    total_bytes_checked = 0

    for resource in sorted(resources, key=lambda item: item["resource_id"]):
        rid = resource["resource_id"]
        fasta_rel = resource["fasta_path"]
        idmap_rel = resource["identifier_map_path"]
        fasta_path = relative_path(root, fasta_rel)
        idmap_path = relative_path(root, idmap_rel)
        require(fasta_path.is_relative_to(nto_root), f"FASTA path outside data/external/nto: {fasta_rel}")
        require(idmap_path.is_relative_to(nto_root), f"ID map path outside data/external/nto: {idmap_rel}")
        require(fasta_path.is_file(), f"resource FASTA missing: {fasta_rel}")
        require(idmap_path.is_file(), f"resource identifier_map missing: {idmap_rel}")

        expected_fasta_sha = resource["quality"]["fasta_sha256"]
        expected_idmap_sha = resource["quality"]["identifier_map_sha256"]
        artifacts_map = resource.get("artifacts_sha256", {})
        require(bool(artifacts_map), f"resource artifacts_sha256 empty: {rid}")
        require(
            artifacts_map.get(fasta_rel) == expected_fasta_sha,
            f"resource FASTA hash disagrees with artifacts_sha256: {rid}",
        )
        require(
            artifacts_map.get(idmap_rel) == expected_idmap_sha,
            f"resource identifier_map hash disagrees with artifacts_sha256: {rid}",
        )

        artifact_verifications: dict[str, dict[str, Any]] = {}
        blastdb_volumes: dict[str, dict[str, Any]] = {}
        blastdb_total_bytes = 0

        for art_rel in sorted(artifacts_map):
            expected_art_sha = artifacts_map[art_rel]
            art_path = relative_path(root, art_rel)
            require(art_path.is_relative_to(nto_root), f"resource artifact outside data/external/nto: {art_rel}")
            require(art_path.is_file(), f"resource artifact missing: {art_rel}")
            observed_art_sha = digest(art_path)
            require(
                observed_art_sha == expected_art_sha,
                f"resource artifact SHA256 mismatch for {art_rel}: expected={expected_art_sha} observed={observed_art_sha}",
            )
            size_bytes = art_path.stat().st_size
            total_bytes_checked += size_bytes
            entry_record = {
                "bytes": size_bytes,
                "expected_sha256": expected_art_sha,
                "hash_mode": "RAW",
                "observed_sha256": observed_art_sha,
                "verdict": "PASS",
            }
            artifact_verifications[art_rel] = entry_record
            if "/blastdb/" in art_rel.replace("\\", "/"):
                blastdb_volumes[art_path.name] = entry_record
                blastdb_total_bytes += size_bytes

        require(bool(blastdb_volumes), f"no blastdb index volumes in artifacts_sha256 for {rid}")
        db_build_path = fasta_path.parent / "database_build.json"
        require(db_build_path.is_file(), f"database_build.json missing for {rid}")
        db_build = json.loads(db_build_path.read_text("utf-8"))
        require(
            {name: rec["observed_sha256"] for name, rec in blastdb_volumes.items()} == db_build.get("index_sha256"),
            f"blastdb index_sha256 in database_build.json diverges from artifacts_sha256 for {rid}",
        )
        blastdb_dir = fasta_path.parent / "blastdb"
        actual_blastdb_files = sorted(p.name for p in blastdb_dir.iterdir() if p.is_file())
        require(
            actual_blastdb_files == sorted(blastdb_volumes),
            f"unlisted or missing files in blastdb directory for {rid}",
        )

        fasta_bytes = fasta_path.stat().st_size
        require(fasta_bytes > 0, f"empty FASTA file for {rid}")
        ratio = round(blastdb_total_bytes / fasta_bytes, 6)

        resource_records[rid] = {
            "organism_id": resource["organism_id"],
            "scientific_name": resource["scientific_name"],
            "taxid": resource["taxid"],
            "record_count": resource["quality"]["record_count"],
            "total_bases": resource["quality"]["total_bases"],
            "fasta_path": fasta_rel,
            "fasta_bytes": fasta_bytes,
            "fasta_expected_sha256": expected_fasta_sha,
            "fasta_observed_sha256": artifact_verifications[fasta_rel]["observed_sha256"],
            "identifier_map_path": idmap_rel,
            "identifier_map_expected_sha256": expected_idmap_sha,
            "identifier_map_observed_sha256": artifact_verifications[idmap_rel]["observed_sha256"],
            "blastdb_volume_count": len(blastdb_volumes),
            "blastdb_total_bytes": blastdb_total_bytes,
            "index_to_fasta_byte_ratio": ratio,
            "blastdb_volumes": blastdb_volumes,
            "artifacts_count": len(artifact_verifications),
            "artifacts": artifact_verifications,
            "verdict": "PASS",
        }

    summary = {
        "reference_artifacts": reference_records,
        "cp1_run_manifest": {
            "path": EXPECTED_CP1_RUN_MANIFEST_PATH,
            "expected_sha256": expected_run_manifest_sha256 or observed_run_manifest_sha,
            "observed_sha256": observed_run_manifest_sha,
            "protected_implementation_sha256_lf": run_manifest.get("implementation_sha256_lf", {}),
            "verdict": "PASS",
        },
        "manifest_bindings": {
            "g0_certificate_sha256": {
                "expected": manifest["g0_certificate_sha256"],
                "observed": g0_sha,
                "verdict": "PASS",
            },
            "inventory_sha256": {
                "expected": manifest["inventory_sha256"],
                "observed": inv_sha,
                "verdict": "PASS",
            },
        },
        "streaming_hash_mode": "CHUNKED_1MB_O_B_TIME_O_1_MEMORY",
        "total_resource_artifact_bytes_streamed": total_bytes_checked,
        "resource_count": len(resource_records),
        "resources": resource_records,
        "verdict": "PASS",
    }
    return manifest, summary


def compute_index_size_ratio_summary(resources_summary: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize the empirical BLAST index-to-FASTA byte ratio across the 6 real CP1 resources."""
    per_resource: dict[str, dict[str, int | float]] = {}
    ratios: list[float] = []
    for rid, rec in sorted(resources_summary["resources"].items()):
        ratio = float(rec["index_to_fasta_byte_ratio"])
        ratios.append(ratio)
        per_resource[rid] = {
            "fasta_bytes": int(rec["fasta_bytes"]),
            "blastdb_total_bytes": int(rec["blastdb_total_bytes"]),
            "blastdb_volume_count": int(rec["blastdb_volume_count"]),
            "index_to_fasta_byte_ratio": ratio,
        }
    require(bool(ratios), "cannot compute index size ratio summary from empty resource set")
    return {
        "empirical_origin": "REAL_BIOLOGICAL_NTO_CP1_RESOURCES",
        "observed_min_ratio": min(ratios),
        "observed_max_ratio": max(ratios),
        "plan_section_5_approx_range": [0.298, 0.402],
        "per_resource": per_resource,
        "domain_restrictions": [
            "NOT_GUARANTEED_ESTIMATE_FOR_SYNTHETIC_ACGT_FIXTURES",
            "NOT_A_RUNTIME_OR_RAM_ESTIMATE",
            "EMPIRICAL_BIOLOGICAL_TRANSCRIPT_COMPOSITION_AND_REDUNDANCY_ONLY",
        ],
        "statement": (
            "Observed CP1 BLAST index byte sizes range from approximately 0.298 to 0.402 of the "
            "corresponding normalized FASTA byte size across the six real biological resources "
            "(plan_v003.md section 5). Synthetic ACGT fixtures may exhibit different compressibility "
            "and index structure; this ratio is not a guaranteed bound for synthetic fixtures and "
            "does not estimate runtime or RAM."
        ),
    }


def verify_historical_snapshots(
    root: Path,
    certificate: Mapping[str, Any],
    *,
    working_tree_dirty: bool,
    expected_latest_pointer_sha256: Any = _DEFAULT,
    expected_cp1_snapshot_sha256: Any = _DEFAULT,
) -> dict[str, Any]:
    """Verify the G0 certificate snapshot and latest CP1 snapshot, declaring dirty-tree non-equivalence."""
    root = root.resolve()
    if expected_latest_pointer_sha256 is _DEFAULT:
        expected_latest_pointer_sha256 = EXPECTED_LATEST_POINTER_SHA256
    if expected_cp1_snapshot_sha256 is _DEFAULT:
        expected_cp1_snapshot_sha256 = EXPECTED_CP1_SNAPSHOT_SHA256
    env_snap = certificate.get("environment_snapshot")
    require(
        isinstance(env_snap, Mapping) and "path" in env_snap and "sha256" in env_snap,
        "G0 certificate environment_snapshot missing",
    )
    g0_snap_rel = str(env_snap["path"])
    g0_snap_expected = str(env_snap["sha256"])
    g0_snap_path = relative_path(root, g0_snap_rel)
    require(g0_snap_path.is_file(), f"G0 environment_snapshot missing: {g0_snap_rel}")
    g0_snap_observed = digest(g0_snap_path)
    require(
        g0_snap_observed == g0_snap_expected,
        f"G0 environment_snapshot SHA256 mismatch: expected={g0_snap_expected} observed={g0_snap_observed}",
    )
    g0_snap_payload = json.loads(g0_snap_path.read_text("utf-8"))

    latest_record: dict[str, Any] | None = None
    latest_path = relative_path(root, EXPECTED_LATEST_POINTER_PATH)
    if latest_path.is_file() or expected_latest_pointer_sha256 is not None:
        require(latest_path.is_file(), f"latest reproducibility pointer missing: {EXPECTED_LATEST_POINTER_PATH}")
        latest_observed_sha = digest(latest_path)
        if expected_latest_pointer_sha256 is not None:
            require(
                latest_observed_sha == expected_latest_pointer_sha256,
                f"latest.json SHA256 mismatch: expected={expected_latest_pointer_sha256} observed={latest_observed_sha}",
            )
        latest_payload = json.loads(latest_path.read_text("utf-8"))
        cp1_snap_rel = f"artifacts/reproducibility/{latest_payload['snapshot_file']}"
        cp1_snap_path = relative_path(root, cp1_snap_rel)
        require(cp1_snap_path.is_file(), f"latest snapshot missing: {cp1_snap_rel}")
        cp1_snap_observed = digest(cp1_snap_path)
        require(
            cp1_snap_observed == latest_payload["snapshot_sha256"],
            "latest.json snapshot_sha256 does not match target snapshot file",
        )
        if expected_cp1_snapshot_sha256 is not None:
            require(
                cp1_snap_observed == expected_cp1_snapshot_sha256,
                f"CP1 snapshot SHA256 mismatch: expected={expected_cp1_snapshot_sha256} observed={cp1_snap_observed}",
            )
        cp1_snap_payload = json.loads(cp1_snap_path.read_text("utf-8"))
        latest_record = {
            "latest_pointer_path": EXPECTED_LATEST_POINTER_PATH,
            "latest_pointer_expected_sha256": expected_latest_pointer_sha256 or latest_observed_sha,
            "latest_pointer_observed_sha256": latest_observed_sha,
            "snapshot_path": cp1_snap_rel,
            "snapshot_expected_sha256": expected_cp1_snapshot_sha256 or cp1_snap_observed,
            "snapshot_observed_sha256": cp1_snap_observed,
            "snapshot_git": cp1_snap_payload.get("git"),
            "verdict": "PASS",
        }

    return {
        "g0_certificate_environment_snapshot": {
            "path": g0_snap_rel,
            "expected_sha256": g0_snap_expected,
            "observed_sha256": g0_snap_observed,
            "snapshot_git": g0_snap_payload.get("git"),
            "verdict": "PASS",
        },
        "latest_published_snapshot": latest_record,
        "current_working_tree_dirty": working_tree_dirty,
        "historical_snapshot_captures_current_working_tree_state": False,
        "dirty_tree_non_equivalence_declaration": (
            "The current working tree is dirty (.gitignore locally modified and preparation "
            "files present), whereas historical snapshots recorded dirty=false at their capture "
            "commits; therefore historical snapshots are preserved as historical provenance only "
            "and are not a capture of the current working-tree state (plan_v003.md section 2)."
        ),
        "verdict": "PASS",
    }


def _parse_blast_version_text(text: str) -> dict[str, str] | None:
    match = _BLAST_VERSION_RE.match(text.strip())
    if match is None:
        return None
    return {
        "reported_tool_name": match.group(1),
        "tool_version": match.group(2),
        "package_version": match.group(3).strip(),
        "build_date": match.group(4).strip(),
    }


def observe_blast_tool_builds(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    tool_names: tuple[str, ...] = BLAST_TOOLS,
    which_resolver: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Observe blastn, makeblastdb, and blastdbcmd builds and compare with the 6 CP1 receipts."""
    root = root.resolve()
    receipt_builds: dict[str, dict[str, Any]] = {}
    unique_receipt_signatures: set[tuple[str, str, str]] = set()
    unique_receipt_raw_strings: set[str] = set()

    for resource in sorted(manifest.get("resources", []), key=lambda item: item["resource_id"]):
        rid = resource["resource_id"]
        fasta_path = relative_path(root, resource["fasta_path"])
        db_build_rel = (fasta_path.parent / "database_build.json").relative_to(root).as_posix()
        db_build_path = relative_path(root, db_build_rel)
        require(db_build_path.is_file(), f"database_build.json missing: {db_build_rel}")
        db_build = json.loads(db_build_path.read_text("utf-8"))
        raw_tool_str = str(db_build.get("tool", "")).strip()
        parsed = _parse_blast_version_text(raw_tool_str)
        require(parsed is not None, f"unparseable tool string in {db_build_rel}: {raw_tool_str!r}")
        signature = (parsed["tool_version"], parsed["package_version"], parsed["build_date"])
        unique_receipt_signatures.add(signature)
        unique_receipt_raw_strings.add(raw_tool_str)
        receipt_builds[rid] = {
            "database_build_path": db_build_rel,
            "database_build_sha256": digest(db_build_path),
            "raw_tool_field": raw_tool_str,
            "tool_version": parsed["tool_version"],
            "package_version": parsed["package_version"],
            "build_date": parsed["build_date"],
            "historical_executable_sha256": db_build.get("executable_sha256"),
        }

    require(
        len(unique_receipt_signatures) == 1,
        f"historical database_build.json receipts do not share a single build signature: {unique_receipt_signatures}",
    )
    expected_version, expected_package, expected_build_date = next(iter(unique_receipt_signatures))
    expected_makeblastdb_raw = next(iter(unique_receipt_raw_strings))

    observed_tools: dict[str, dict[str, Any]] = {}
    reuse_block_reasons: list[str] = []

    for tool in tool_names:
        resolved = which_resolver(tool)
        if not resolved or not Path(resolved).is_file():
            reason = f"{tool} executable not found in PATH"
            reuse_block_reasons.append(f"{tool}: BUILD_NOT_OBSERVED ({reason})")
            observed_tools[tool] = {
                "tool_name": tool,
                "status": "BUILD_NOT_OBSERVED",
                "reason": reason,
                "tool_version": None,
                "package_version": None,
                "build_date": None,
                "raw_version_output": None,
                "prospective_executable_sha256": None,
                "prospective_executable_bytes": None,
                "matches_historical_receipt_version_package_build": False,
            }
            continue

        exec_path = Path(resolved).resolve()
        try:
            completed = runner(
                [str(exec_path), "-version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            reason = f"{tool} -version execution failed: {exc}"
            reuse_block_reasons.append(f"{tool}: BUILD_NOT_OBSERVED ({reason})")
            observed_tools[tool] = {
                "tool_name": tool,
                "status": "BUILD_NOT_OBSERVED",
                "reason": reason,
                "tool_version": None,
                "package_version": None,
                "build_date": None,
                "raw_version_output": None,
                "prospective_executable_sha256": None,
                "prospective_executable_bytes": None,
                "matches_historical_receipt_version_package_build": False,
            }
            continue

        raw_out = (completed.stdout or "").strip()
        parsed_tool = _parse_blast_version_text(raw_out) if completed.returncode == 0 else None
        if completed.returncode != 0 or parsed_tool is None:
            reason = f"{tool} -version returned code {completed.returncode} with unparseable output"
            reuse_block_reasons.append(f"{tool}: BUILD_NOT_OBSERVED ({reason})")
            observed_tools[tool] = {
                "tool_name": tool,
                "status": "BUILD_NOT_OBSERVED",
                "reason": reason,
                "tool_version": None,
                "package_version": None,
                "build_date": None,
                "raw_version_output": raw_out or None,
                "prospective_executable_sha256": None,
                "prospective_executable_bytes": None,
                "matches_historical_receipt_version_package_build": False,
            }
            continue

        exec_sha256 = digest(exec_path)
        exec_bytes = exec_path.stat().st_size
        matches_signature = (
            (tool in INDEPENDENTLY_VERSIONED_TOOLS or parsed_tool["tool_version"] == expected_version)
            and parsed_tool["package_version"] == expected_package
            and parsed_tool["build_date"] == expected_build_date
        )
        if tool == "makeblastdb":
            matches_signature = matches_signature and (raw_out == expected_makeblastdb_raw)

        if not matches_signature:
            reuse_block_reasons.append(
                f"{tool}: observed ({parsed_tool['tool_version']}, {parsed_tool['package_version']}, "
                f"{parsed_tool['build_date']}) diverges from historical receipt "
                f"({expected_version}, {expected_package}, {expected_build_date})"
            )

        observed_tools[tool] = {
            "tool_name": tool,
            "status": "OBSERVED",
            "reason": None,
            "tool_version": parsed_tool["tool_version"],
            "package_version": parsed_tool["package_version"],
            "build_date": parsed_tool["build_date"],
            "raw_version_output": raw_out,
            "prospective_executable_sha256": exec_sha256,
            "prospective_executable_bytes": exec_bytes,
            "matches_historical_receipt_version_package_build": matches_signature,
        }

    all_observed = all(item["status"] == "OBSERVED" for item in observed_tools.values())
    all_match = all_observed and all(
        item["matches_historical_receipt_version_package_build"] for item in observed_tools.values()
    )
    if all_match:
        overall_status = "OBSERVED_MATCHES_HISTORICAL_RECEIPTS"
    elif any(item["status"] == "BUILD_NOT_OBSERVED" for item in observed_tools.values()):
        overall_status = "BUILD_NOT_OBSERVED"
    else:
        overall_status = "BUILD_DIVERGENCE_DETECTED_REUSE_BLOCKED"

    return {
        "historical_receipt_reference": {
            "tool_version": expected_version,
            "package_version": expected_package,
            "build_date": expected_build_date,
            "makeblastdb_raw_tool_field": expected_makeblastdb_raw,
            "retrospective_executable_sha256_in_receipts": None,
            "receipts_by_resource": receipt_builds,
        },
        "observed_tools": observed_tools,
        "all_tools_observed": all_observed,
        "all_tools_match_historical_receipts": all_match,
        "equivalent_build_reuse_blocked": not all_match,
        "reuse_block_reasons": reuse_block_reasons,
        "overall_status": overall_status,
        "section_6_4_note": (
            "Historical database_build.json receipts record makeblastdb version, package, and build "
            "date without a retrospective executable hash; prospective executable SHA256 hashes are "
            "pinned here for current tools without retrospectively attributing binary hashes to "
            "historical builds (plan_v003.md section 6.4)."
        ),
    }


def build_execution_scope_artifact(root: Path) -> dict[str, Any]:
    """Build the deterministic E01 execution scope artifact (data/reference/nb04_calibration_execution_scope.json)."""
    root = root.resolve()
    _, g0_summary = verify_g0_certified_artifacts_inventory(root)
    _, resources_summary = verify_cp1_resources_and_manifests(root)
    ratio_summary = compute_index_size_ratio_summary(resources_summary)

    return {
        "schema_version": 1,
        "artifact_id": "NB04_CALIBRATION_EXECUTION_SCOPE_V1",
        "stage": "NB04_CP1_E01_PREFREEZE_PREPARATION_SCOPE",
        "authority_bindings": {
            "plan_path": PLAN_V003_PATH,
            "plan_sha256": PLAN_V003_SHA256,
            "evaluator_opinion_path": EVALUATOR_OPINION_V003_PATH,
            "evaluator_opinion_sha256": EVALUATOR_OPINION_V003_SHA256,
            "g0_certificate_path": G0_PATH,
            "g0_certificate_sha256": g0_summary["observed_certificate_sha256"],
            "cp1_resources_manifest_path": MANIFEST,
            "cp1_resources_manifest_sha256": resources_summary["reference_artifacts"][MANIFEST]["observed_sha256"],
            "e01_gitignore_baseline_raw_sha256": E01_BASELINE_GITIGNORE_RAW_SHA256,
            "plan_section_2_gitignore_raw_sha256": PLAN_SECTION_2_GITIGNORE_RAW_SHA256,
        },
        "closed_preparation_dirty_allowlist": list(CLOSED_PREPARATION_DIRTY_ALLOWLIST),
        "index_to_fasta_size_ratio": ratio_summary,
        "phase_git_and_snapshot_policy": phase_git_and_snapshot_policy(),
        "normative_corpus_declaration": normative_corpus_declaration(),
        "blocked_operations": list(BLOCKED_OPERATIONS),
        "state_declarations": {
            "G0": "G0_PASS",
            "G1": "NOT_DECLARED",
            "b4_complete_prior_freeze": "NOT_DECLARED",
            "synthetic_fixtures_materialized": False,
            "informative_calibration": "NOT_EXECUTED",
            "real_nto_searches": "NOT_EXECUTED",
        },
    }


def validate_e01_scope_destination(
    root: Path,
    destination: Path | None = None,
) -> Path:
    """Validate that the execution scope destination is strictly the authorized E01 scope path."""
    root = root.resolve()
    expected_target = relative_path(root, EXECUTION_SCOPE_PATH)
    if destination is None:
        target = expected_target
    else:
        raw_dest = Path(destination)
        target = (root / raw_dest).resolve() if not raw_dest.is_absolute() else raw_dest.resolve()
    require(target.is_relative_to(root), f"execution scope path outside project root: {target}")
    rel = target.relative_to(root).as_posix()
    require(
        target == expected_target and rel == EXECUTION_SCOPE_PATH,
        f"execution scope destination outside authorized E01 output path ({EXECUTION_SCOPE_PATH}): {rel}",
    )
    require(not target.is_dir(), f"execution scope destination cannot be a directory: {rel}")
    return target


def validate_e01_inventory_destination(
    root: Path,
    output_path: Path | None = None,
) -> Path:
    """Validate that the preservation inventory destination is a new file inside the E01 inventory directory."""
    root = root.resolve()
    inv_base = relative_path(root, PRESERVATION_INVENTORY_DIR)
    if output_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = relative_path(
            root,
            f"{PRESERVATION_INVENTORY_DIR}/{stamp}/{PRESERVATION_INVENTORY_FILENAME}",
        )
    else:
        raw_dest = Path(output_path)
        target = (root / raw_dest).resolve() if not raw_dest.is_absolute() else raw_dest.resolve()
    require(target.is_relative_to(root), f"preservation inventory path outside project root: {target}")
    rel = target.relative_to(root).as_posix()
    require(
        target.is_relative_to(inv_base)
        and target.parent != inv_base
        and target.parent.parent == inv_base
        and target.name == PRESERVATION_INVENTORY_FILENAME,
        f"preservation inventory destination outside authorized directory ({PRESERVATION_INVENTORY_DIR}/<run_id>/{PRESERVATION_INVENTORY_FILENAME}): {rel}",
    )
    require(
        not target.exists(),
        f"preservation inventory destination already exists and must never be overwritten: {target}",
    )
    return target


def write_execution_scope_artifact(
    root: Path,
    destination: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Materialize the deterministic execution scope JSON artifact without corrupting existing files."""
    root = root.resolve()
    target = validate_e01_scope_destination(root, destination)
    payload = build_execution_scope_artifact(root)
    encoded = json_bytes(payload)
    if target.exists():
        require(
            target.is_file() and target.read_bytes() == encoded,
            f"execution scope destination already exists with divergent content and must not be overwritten: {target}",
        )
        return target, payload
    write_json(target, payload)
    return target, payload


def build_preservation_inventory(
    root: Path,
    corpus_directories: Mapping[str, Path],
    *,
    executed_utc: str | None = None,
    which_resolver: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Execute all E01 preservation checks (items a through h) and return the inventory dict."""
    root = root.resolve()
    timestamp = executed_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    git_state = verify_gitignore_and_git_state(root)
    certificate, g0_artifacts = verify_g0_certified_artifacts_inventory(root)
    normatives = verify_normative_documents(root, certificate, corpus_directories, strict=True)
    manifest, resources_summary = verify_cp1_resources_and_manifests(root)
    snapshots = verify_historical_snapshots(
        root,
        certificate,
        working_tree_dirty=git_state["working_tree_dirty"],
    )
    tool_builds = observe_blast_tool_builds(
        root,
        manifest,
        which_resolver=which_resolver,
        runner=runner,
    )
    allowlist_control = verify_preparation_allowlist(root)

    return {
        "schema_version": 1,
        "artifact_id": "NB04_CP1_E01_PRESERVATION_INVENTORY_V1",
        "stage": "NB04_CP1_E01_PRESERVATION_CONTROL",
        "executed_utc": timestamp,
        "a_git_and_gitignore_state": git_state,
        "b_g0_certified_artifacts": g0_artifacts,
        "c_normative_documents": normatives,
        "d_cp1_resources_and_manifests": resources_summary,
        "e_reproducibility_snapshots": snapshots,
        "f_observed_blast_tool_builds": tool_builds,
        "g_preparation_allowlist_control": allowlist_control,
        "h_file_classification_and_phase_policy": phase_git_and_snapshot_policy(),
        "index_to_fasta_size_ratio_summary": compute_index_size_ratio_summary(resources_summary),
        "scientific_execution_performed": False,
        "searches_executed": False,
        "fixtures_materialized": False,
    }


def write_preservation_inventory(
    root: Path,
    inventory: Mapping[str, Any],
    *,
    output_path: Path | None = None,
) -> Path:
    """Write the preservation inventory to a new timestamped path without overwriting any prior record."""
    target = validate_e01_inventory_destination(root, output_path)
    write_json(target, dict(inventory))
    return target


# ======================================================================
# E03: Read-only geometry derivation for the six CP1 resources (section 5)
# ======================================================================

DEFAULT_GEOMETRY_CAMPAIGN_ID = "cp1_20261015"
GEOMETRY_CAMPAIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
GEOMETRY_DESCRIPTOR_SCHEMA_ID = "NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1"
GEOMETRY_RECORD_ARTIFACT_ID = "NB04_CP1_E03_RESOURCE_GEOMETRY_RECORD_V1"
GEOMETRY_DERIVATION_VERSION = "NB04_RESOURCE_ARCHITECTURE_GEOMETRY_DERIVATION_V1"
ALPHABET_POLICY_UPPERCASE_IUPAC_DNA = "UPPERCASE_IUPAC_DNA"
RECORD_BOUNDARY_POLICY_NEVER_CROSSED = "NEVER_CROSSED"
GEOMETRY_DESCRIPTOR_KEYS: frozenset[str] = frozenset(
    {
        "record_count",
        "total_bases",
        "ordered_record_lengths",
        "ordered_ambiguous_base_counts",
        "alphabet_policy",
        "record_boundary_policy",
    }
)
GEOMETRY_NOMINAL_LIMITATIONS: tuple[str, ...] = (
    "ENVELOPE_GEOMETRY_ONLY_REAL_COMPOSITION_NOT_REPRESENTED",
    "RESOURCE_SPECIFIC_TRUNCATION_QA_REQUIRED",
)
IDENTIFIER_MAP_REQUIRED_COLUMNS: tuple[str, ...] = (
    "analysis_id",
    "source_id",
    "source_header",
    "length_nt",
    "sequence_sha256",
)


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_geometry_campaign_id(campaign_id: object) -> str:
    require(
        isinstance(campaign_id, str)
        and bool(GEOMETRY_CAMPAIGN_ID_PATTERN.fullmatch(campaign_id))
        and campaign_id not in {".", ".."}
        and ".." not in campaign_id,
        f"invalid geometry campaign_id: {campaign_id!r}",
    )
    return campaign_id


def validate_geometry_descriptor(descriptor: object) -> dict[str, Any]:
    """Validate that a descriptor is strictly the 6-field NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 object."""
    require(isinstance(descriptor, Mapping), "geometry descriptor must be a mapping")
    keys = set(descriptor.keys())
    extra = sorted(keys - GEOMETRY_DESCRIPTOR_KEYS)
    missing = sorted(GEOMETRY_DESCRIPTOR_KEYS - keys)
    require(
        not extra and not missing,
        f"NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 requires exactly {sorted(GEOMETRY_DESCRIPTOR_KEYS)}; extra={extra}, missing={missing}",
    )

    record_count = descriptor["record_count"]
    total_bases = descriptor["total_bases"]
    lengths = descriptor["ordered_record_lengths"]
    ambig_counts = descriptor["ordered_ambiguous_base_counts"]
    alphabet_policy = descriptor["alphabet_policy"]
    boundary_policy = descriptor["record_boundary_policy"]

    require(
        _is_strict_int(record_count) and record_count > 0,
        f"record_count must be a positive integer: {record_count!r}",
    )
    require(
        _is_strict_int(total_bases) and total_bases > 0,
        f"total_bases must be a positive integer: {total_bases!r}",
    )
    require(
        isinstance(lengths, list) and len(lengths) == record_count,
        f"ordered_record_lengths must be a list of length record_count ({record_count})",
    )
    require(
        all(_is_strict_int(x) and x > 0 for x in lengths),
        "every element of ordered_record_lengths must be a positive integer",
    )
    lengths_sum = sum(lengths)
    require(
        lengths_sum == total_bases,
        f"sum of ordered_record_lengths ({lengths_sum}) does not equal total_bases ({total_bases})",
    )
    require(
        isinstance(ambig_counts, list) and len(ambig_counts) == record_count,
        f"ordered_ambiguous_base_counts must be a list of length record_count ({record_count})",
    )
    require(
        all(
            _is_strict_int(a) and 0 <= a <= lengths[i]
            for i, a in enumerate(ambig_counts)
        ),
        "every element of ordered_ambiguous_base_counts must be an integer in [0, record_length]",
    )
    require(
        alphabet_policy == ALPHABET_POLICY_UPPERCASE_IUPAC_DNA,
        f"alphabet_policy must be {ALPHABET_POLICY_UPPERCASE_IUPAC_DNA!r}: {alphabet_policy!r}",
    )
    require(
        boundary_policy == RECORD_BOUNDARY_POLICY_NEVER_CROSSED,
        f"record_boundary_policy must be {RECORD_BOUNDARY_POLICY_NEVER_CROSSED!r}: {boundary_policy!r}",
    )

    return {
        "record_count": int(record_count),
        "total_bases": int(total_bases),
        "ordered_record_lengths": [int(x) for x in lengths],
        "ordered_ambiguous_base_counts": [int(a) for a in ambig_counts],
        "alphabet_policy": ALPHABET_POLICY_UPPERCASE_IUPAC_DNA,
        "record_boundary_policy": RECORD_BOUNDARY_POLICY_NEVER_CROSSED,
    }


def compute_geometry_descriptor_sha256(descriptor: object) -> str:
    """Compute descriptor_sha256 strictly over the 6-field NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 JSON bytes."""
    clean = validate_geometry_descriptor(descriptor)
    return hashlib.sha256(json_bytes(clean)).hexdigest()


def extract_geometry_descriptor_sha256_from_record(geometry_record: Mapping[str, Any]) -> str:
    """Extract and verify descriptor_sha256 from a provenance record, ignoring outer administrative metadata."""
    require(isinstance(geometry_record, Mapping), "geometry record must be a mapping")
    require(
        geometry_record.get("descriptor_schema_id") == GEOMETRY_DESCRIPTOR_SCHEMA_ID,
        f"unexpected descriptor_schema_id: {geometry_record.get('descriptor_schema_id')!r}",
    )
    require(
        "architecture_descriptor" in geometry_record,
        "geometry record missing architecture_descriptor",
    )
    computed = compute_geometry_descriptor_sha256(geometry_record["architecture_descriptor"])
    if "descriptor_sha256" in geometry_record:
        require(
            geometry_record["descriptor_sha256"] == computed,
            f"geometry record descriptor_sha256 mismatch: declared={geometry_record['descriptor_sha256']} computed={computed}",
        )
    return computed


def geometry_cell_covers_resource(
    cell_descriptor: object,
    resource_descriptor: object,
    *,
    cell_descriptor_sha256: str | None = None,
    resource_descriptor_sha256: str | None = None,
) -> bool:
    """Evaluate the section 5 exact geometry coverage predicate without summary approximations."""
    clean_cell = validate_geometry_descriptor(cell_descriptor)
    clean_res = validate_geometry_descriptor(resource_descriptor)
    cell_bytes = json_bytes(clean_cell)
    res_bytes = json_bytes(clean_res)
    cell_hash = hashlib.sha256(cell_bytes).hexdigest()
    res_hash = hashlib.sha256(res_bytes).hexdigest()

    if cell_descriptor_sha256 is not None:
        require(
            cell_descriptor_sha256 == cell_hash,
            f"cell_descriptor_sha256 mismatch: expected={cell_descriptor_sha256} computed={cell_hash}",
        )
    if resource_descriptor_sha256 is not None:
        require(
            resource_descriptor_sha256 == res_hash,
            f"resource_descriptor_sha256 mismatch: expected={resource_descriptor_sha256} computed={res_hash}",
        )
    if cell_hash == res_hash:
        require(
            cell_bytes == res_bytes and clean_cell == clean_res,
            "descriptor hash collision with distinct descriptor bytes",
        )
    return clean_cell == clean_res and cell_bytes == res_bytes


def validate_e03_geometry_destination(
    root: Path,
    destination: Path | None = None,
    *,
    campaign_id: str = DEFAULT_GEOMETRY_CAMPAIGN_ID,
    resource_id: str,
) -> Path:
    """Validate that an E03 geometry output path is strictly the canonical non-existent destination."""
    root = root.resolve()
    validate_geometry_campaign_id(campaign_id)
    require(
        isinstance(resource_id, str) and bool(RESOURCE_ID.fullmatch(resource_id)),
        f"invalid resource_id: {resource_id!r}",
    )
    expected_rel = f"data/external/nto/{campaign_id}/geometry/{resource_id}.json"
    expected_target = relative_path(root, expected_rel)
    if destination is None:
        target = expected_target
    else:
        raw_dest = Path(destination)
        target = (root / raw_dest).resolve() if not raw_dest.is_absolute() else raw_dest.resolve()
    require(target.is_relative_to(root), f"geometry destination outside project root: {target}")
    rel = target.relative_to(root).as_posix()
    require(
        target == expected_target and rel == expected_rel,
        f"geometry destination outside authorized E03 path ({expected_rel}): {rel}",
    )
    require(
        not target.exists(),
        f"geometry destination already exists and must never be overwritten: {target}",
    )
    return target


def verify_authoritative_cp1_manifest_for_e03(
    root: Path,
    *,
    expected_reference_sha256: Any = _DEFAULT,
    expected_run_manifest_sha256: Any = _DEFAULT,
    expected_resource_count: Any = _DEFAULT,
    expected_resource_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Verify the authoritative CP1 preservation contract before any E03 geometry derivation or write."""
    root = root.resolve()
    if expected_reference_sha256 is _DEFAULT:
        expected_reference_sha256 = EXPECTED_CP1_REFERENCE_SHA256
    if expected_run_manifest_sha256 is _DEFAULT:
        expected_run_manifest_sha256 = EXPECTED_CP1_RUN_MANIFEST_SHA256

    require(
        isinstance(expected_reference_sha256, Mapping),
        "expected_reference_sha256 must be a mapping of authoritative CP1 reference artifact SHA256 expectations",
    )
    for rel_path in (MANIFEST, INVENTORY, REGISTRY, ASSESSABILITY):
        expected_sha = expected_reference_sha256.get(rel_path)
        require(
            isinstance(expected_sha, str) and bool(expected_sha),
            f"missing authoritative SHA256 expectation for CP1 reference artifact: {rel_path}",
        )
        ref_path = relative_path(root, rel_path)
        require(ref_path.is_file(), f"CP1 reference artifact missing: {rel_path}")
        observed_sha = digest(ref_path)
        require(
            observed_sha == expected_sha,
            f"CP1 reference artifact hash mismatch for {rel_path}: expected={expected_sha} observed={observed_sha}",
        )

    require(
        isinstance(expected_run_manifest_sha256, str) and bool(expected_run_manifest_sha256),
        "missing authoritative SHA256 expectation for CP1 run_manifest",
    )
    run_manifest_path = relative_path(root, EXPECTED_CP1_RUN_MANIFEST_PATH)
    require(run_manifest_path.is_file(), f"CP1 run_manifest missing: {EXPECTED_CP1_RUN_MANIFEST_PATH}")
    observed_run_manifest_sha = digest(run_manifest_path)
    require(
        observed_run_manifest_sha == expected_run_manifest_sha256,
        f"CP1 run_manifest SHA256 mismatch: expected={expected_run_manifest_sha256} observed={observed_run_manifest_sha}",
    )

    verify_g0_certified_artifacts_inventory(root)

    manifest_path = relative_path(root, MANIFEST)
    manifest = json.loads(manifest_path.read_text("utf-8"))
    resources = manifest.get("resources")
    require(isinstance(resources, list) and len(resources) > 0, "CP1 manifest contains no resources")
    observed_resource_ids = [r.get("resource_id") for r in resources]
    require(
        len(set(observed_resource_ids)) == len(observed_resource_ids),
        "duplicate resource_id in CP1 manifest",
    )

    expected_manifest_sha256 = str(expected_reference_sha256[MANIFEST])
    if expected_resource_ids is None and expected_manifest_sha256 == REAL_CP1_MANIFEST_SHA256:
        expected_resource_ids = EXPECTED_CP1_RESOURCE_IDS
    if expected_resource_ids is not None:
        require(
            tuple(observed_resource_ids) == tuple(expected_resource_ids),
            f"CP1 authoritative resource_id sequence mismatch: expected={list(expected_resource_ids)} observed={observed_resource_ids}",
        )

    for res in resources:
        rid = res.get("resource_id")
        require(
            isinstance(rid, str) and bool(RESOURCE_ID.fullmatch(rid)),
            f"invalid resource_id: {rid!r}",
        )
        fasta_rel = res.get("fasta_path")
        idmap_rel = res.get("identifier_map_path")
        require(isinstance(fasta_rel, str) and bool(fasta_rel), f"missing fasta_path for {rid}")
        require(isinstance(idmap_rel, str) and bool(idmap_rel), f"missing identifier_map_path for {rid}")
        fasta_path = relative_path(root, fasta_rel)
        idmap_path = relative_path(root, idmap_rel)
        require(fasta_path.is_file(), f"normalized FASTA missing for {rid}: {fasta_rel}")
        require(idmap_path.is_file(), f"identifier_map.tsv missing for {rid}: {idmap_rel}")
        quality = res.get("quality")
        artifacts_sha256 = res.get("artifacts_sha256")
        require(isinstance(quality, Mapping), f"missing quality block for {rid}")
        require(isinstance(artifacts_sha256, Mapping), f"missing artifacts_sha256 block for {rid}")
        expected_fasta_sha256 = quality.get("fasta_sha256")
        expected_idmap_sha256 = quality.get("identifier_map_sha256")
        require(
            isinstance(expected_fasta_sha256, str)
            and bool(expected_fasta_sha256)
            and artifacts_sha256.get(fasta_rel) == expected_fasta_sha256,
            f"manifest fasta_sha256 binding inconsistent for {rid}",
        )
        require(
            isinstance(expected_idmap_sha256, str)
            and bool(expected_idmap_sha256)
            and artifacts_sha256.get(idmap_rel) == expected_idmap_sha256,
            f"manifest identifier_map_sha256 binding inconsistent for {rid}",
        )
        observed_fasta_sha256 = digest(fasta_path)
        require(
            observed_fasta_sha256 == expected_fasta_sha256,
            f"certified fasta_sha256 mismatch before geometry derivation for {rid}: observed={observed_fasta_sha256} expected={expected_fasta_sha256}",
        )
        observed_idmap_sha256 = digest(idmap_path)
        require(
            observed_idmap_sha256 == expected_idmap_sha256,
            f"certified identifier_map_sha256 mismatch before geometry derivation for {rid}: observed={observed_idmap_sha256} expected={expected_idmap_sha256}",
        )

    cp1_kwargs: dict[str, Any] = {
        "expected_reference_sha256": expected_reference_sha256,
        "expected_run_manifest_sha256": expected_run_manifest_sha256,
    }
    if expected_resource_count is not _DEFAULT:
        cp1_kwargs["expected_resource_count"] = expected_resource_count
    verified_manifest, cp1_summary = verify_cp1_resources_and_manifests(root, **cp1_kwargs)
    manifest_sha256 = str(cp1_summary["reference_artifacts"][MANIFEST]["observed_sha256"])
    return verified_manifest, cp1_summary, manifest_sha256


def derive_resource_geometry_record(
    root: Path,
    resource: Mapping[str, Any],
    *,
    campaign_id: str = DEFAULT_GEOMETRY_CAMPAIGN_ID,
    manifest_sha256: str | None = None,
    expected_reference_sha256: Any = _DEFAULT,
    expected_run_manifest_sha256: Any = _DEFAULT,
    expected_resource_count: Any = _DEFAULT,
    expected_resource_ids: Sequence[str] | None = None,
    _verified_manifest_context: tuple[dict[str, Any], str] | None = None,
) -> dict[str, Any]:
    """Derive the E03 geometry record for one certified CP1 resource in a single read-only streaming pass."""
    root = root.resolve()
    validate_geometry_campaign_id(campaign_id)
    require(isinstance(resource, Mapping), "resource entry must be a mapping")
    resource_id = resource.get("resource_id")
    require(
        isinstance(resource_id, str) and bool(RESOURCE_ID.fullmatch(resource_id)),
        f"invalid resource_id: {resource_id!r}",
    )

    if _verified_manifest_context is None:
        auth_manifest, _, verified_manifest_sha256 = verify_authoritative_cp1_manifest_for_e03(
            root,
            expected_reference_sha256=expected_reference_sha256,
            expected_run_manifest_sha256=expected_run_manifest_sha256,
            expected_resource_count=expected_resource_count,
            expected_resource_ids=expected_resource_ids,
        )
    else:
        auth_manifest, verified_manifest_sha256 = _verified_manifest_context
        require(
            digest(relative_path(root, MANIFEST)) == verified_manifest_sha256,
            "CP1 manifest changed on disk after authoritative pre-derivation verification",
        )

    if manifest_sha256 is not None:
        require(
            manifest_sha256 == verified_manifest_sha256,
            f"supplied manifest_sha256 ({manifest_sha256}) diverges from authoritative CP1 manifest SHA256 ({verified_manifest_sha256})",
        )

    auth_matches = [
        item
        for item in auth_manifest.get("resources", [])
        if isinstance(item, Mapping) and item.get("resource_id") == resource_id
    ]
    require(
        len(auth_matches) == 1,
        f"resource {resource_id!r} missing or duplicated in authoritative CP1 manifest",
    )
    require(
        dict(resource) == dict(auth_matches[0]),
        f"resource entry for {resource_id} diverges from authoritative CP1 manifest",
    )

    fasta_rel = resource.get("fasta_path")
    idmap_rel = resource.get("identifier_map_path")
    require(isinstance(fasta_rel, str) and bool(fasta_rel), f"missing fasta_path for {resource_id}")
    require(isinstance(idmap_rel, str) and bool(idmap_rel), f"missing identifier_map_path for {resource_id}")
    fasta_path = relative_path(root, fasta_rel)
    idmap_path = relative_path(root, idmap_rel)
    require(fasta_path.is_file(), f"normalized FASTA missing for {resource_id}: {fasta_rel}")
    require(idmap_path.is_file(), f"identifier_map.tsv missing for {resource_id}: {idmap_rel}")

    quality = resource.get("quality")
    artifacts_sha256 = resource.get("artifacts_sha256")
    require(isinstance(quality, Mapping), f"missing quality block for {resource_id}")
    require(isinstance(artifacts_sha256, Mapping), f"missing artifacts_sha256 block for {resource_id}")

    expected_fasta_sha256 = quality.get("fasta_sha256")
    expected_idmap_sha256 = quality.get("identifier_map_sha256")
    require(
        isinstance(expected_fasta_sha256, str)
        and bool(expected_fasta_sha256)
        and artifacts_sha256.get(fasta_rel) == expected_fasta_sha256,
        f"manifest fasta_sha256 binding inconsistent for {resource_id}",
    )
    require(
        isinstance(expected_idmap_sha256, str)
        and bool(expected_idmap_sha256)
        and artifacts_sha256.get(idmap_rel) == expected_idmap_sha256,
        f"manifest identifier_map_sha256 binding inconsistent for {resource_id}",
    )

    # Mandatory pre-derivation check: verify observed fasta_sha256 and identifier_map_sha256 against certified manifest
    observed_fasta_sha256 = digest(fasta_path)
    require(
        observed_fasta_sha256 == expected_fasta_sha256,
        f"certified fasta_sha256 mismatch before geometry derivation for {resource_id}: observed={observed_fasta_sha256} expected={expected_fasta_sha256}",
    )
    observed_idmap_sha256 = digest(idmap_path)
    require(
        observed_idmap_sha256 == expected_idmap_sha256,
        f"certified identifier_map_sha256 mismatch before geometry derivation for {resource_id}: observed={observed_idmap_sha256} expected={expected_idmap_sha256}",
    )

    # Read-only line-by-line streaming pass over normalized.fasta without materializing full sequences in memory
    # (O(B + R) time, O(R) per-resource vector/ID/hash state)
    ordered_analysis_ids: list[str] = []
    ordered_record_lengths: list[int] = []
    ordered_ambiguous_base_counts: list[int] = []
    ordered_sequence_sha256: list[str] = []
    total_bases = 0
    total_ambiguous_bases = 0

    current_id: str | None = None
    current_len = 0
    current_ambig = 0
    current_seq_hasher = hashlib.sha256()

    def flush_record() -> None:
        nonlocal total_bases, total_ambiguous_bases
        require(
            current_id is not None and current_len > 0,
            f"empty FASTA record in {fasta_rel}: {current_id!r}",
        )
        ordered_analysis_ids.append(current_id)
        ordered_record_lengths.append(current_len)
        ordered_ambiguous_base_counts.append(current_ambig)
        ordered_sequence_sha256.append(current_seq_hasher.hexdigest())
        total_bases += current_len
        total_ambiguous_bases += current_ambig

    with fasta_path.open("rt", encoding="ascii", errors="strict") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    flush_record()
                header = line[1:]
                require(bool(header), f"empty FASTA header in {fasta_rel}")
                expected_id = f"{resource_id}__{len(ordered_analysis_ids) + 1:08d}"
                require(
                    header == expected_id,
                    f"canonical FASTA analysis_id order mismatch in {fasta_rel}: observed={header!r} expected={expected_id!r}",
                )
                current_id = header
                current_len = 0
                current_ambig = 0
                current_seq_hasher = hashlib.sha256()
            else:
                require(current_id is not None, f"sequence before FASTA header in {fasta_rel}")
                require(
                    set(line) <= DNA,
                    f"non-uppercase-IUPAC DNA in {fasta_rel} record {current_id}",
                )
                current_len += len(line)
                # Exact normalize_fasta ambiguity criterion: IUPAC DNA base not in "ACGT"
                current_ambig += sum(base not in "ACGT" for base in line)
                current_seq_hasher.update(line.encode("ascii"))
        if current_id is not None:
            flush_record()

    record_count = len(ordered_record_lengths)
    require(record_count > 0, f"no FASTA records in {fasta_rel}")

    # Mandatory read-only cross-check against identifier_map.tsv
    ordered_source_ids: list[str] = []
    seen_source_ids: set[str] = set()
    map_row_count = 0
    with idmap_path.open("r", encoding="utf-8", newline="") as id_stream:
        reader = csv.DictReader(id_stream, delimiter="\t")
        require(
            tuple(reader.fieldnames or ()) == IDENTIFIER_MAP_REQUIRED_COLUMNS,
            f"unexpected identifier_map.tsv columns in {idmap_rel}: {reader.fieldnames!r}",
        )
        for idx, row in enumerate(reader):
            map_row_count += 1
            require(
                idx < record_count,
                f"identifier_map record count mismatch for {resource_id}: map has more than {record_count} records",
            )
            map_analysis_id = row["analysis_id"]
            require(
                map_analysis_id == ordered_analysis_ids[idx],
                f"identifier_map analysis_id order mismatch at index {idx} for {resource_id}: map={map_analysis_id!r} fasta={ordered_analysis_ids[idx]!r}",
            )
            try:
                map_len = int(row["length_nt"])
            except (TypeError, ValueError) as exc:
                raise ResourceContractError(
                    f"invalid integer length_nt in {idmap_rel} at {map_analysis_id}: {row.get('length_nt')!r}"
                ) from exc
            require(
                map_len == ordered_record_lengths[idx],
                f"identifier_map length_nt mismatch at {map_analysis_id} for {resource_id}: map={map_len} fasta={ordered_record_lengths[idx]}",
            )
            require(
                row["sequence_sha256"] == ordered_sequence_sha256[idx],
                f"identifier_map sequence_sha256 mismatch at {map_analysis_id} for {resource_id}: map={row['sequence_sha256']} fasta={ordered_sequence_sha256[idx]}",
            )
            source_id = row["source_id"]
            require(
                isinstance(source_id, str) and bool(source_id) and source_id not in seen_source_ids,
                f"missing or duplicate source_id in {idmap_rel} at {map_analysis_id}: {source_id!r}",
            )
            seen_source_ids.add(source_id)
            ordered_source_ids.append(source_id)

    require(
        map_row_count == record_count,
        f"identifier_map record count mismatch for {resource_id}: map={map_row_count} fasta={record_count}",
    )

    # Mandatory cross-checks against internal vector sums/counts and manifest quality fields
    require(
        len(ordered_record_lengths) == record_count
        and len(ordered_ambiguous_base_counts) == record_count
        and len(ordered_analysis_ids) == record_count
        and len(ordered_source_ids) == record_count,
        f"geometry vector length mismatch against record_count for {resource_id}",
    )
    lengths_sum = sum(ordered_record_lengths)
    require(
        lengths_sum == total_bases,
        f"sum of ordered_record_lengths ({lengths_sum}) differs from total_bases ({total_bases}) for {resource_id}",
    )
    ambig_sum = sum(ordered_ambiguous_base_counts)
    require(
        ambig_sum == total_ambiguous_bases,
        f"sum of ordered_ambiguous_base_counts ({ambig_sum}) differs from total_ambiguous_bases ({total_ambiguous_bases}) for {resource_id}",
    )

    manifest_record_count = quality.get("record_count")
    manifest_total_bases = quality.get("total_bases")
    manifest_ambiguous_bases = quality.get("ambiguous_bases")
    require(
        _is_strict_int(manifest_record_count) and record_count == manifest_record_count,
        f"record_count mismatch against manifest quality for {resource_id}: observed={record_count} manifest={manifest_record_count!r}",
    )
    require(
        _is_strict_int(manifest_total_bases) and total_bases == manifest_total_bases,
        f"total_bases mismatch against manifest quality for {resource_id}: observed={total_bases} manifest={manifest_total_bases!r}",
    )
    require(
        _is_strict_int(manifest_ambiguous_bases) and total_ambiguous_bases == manifest_ambiguous_bases,
        f"ambiguous_bases sum mismatch against manifest quality for {resource_id}: observed={total_ambiguous_bases} manifest={manifest_ambiguous_bases!r}",
    )

    descriptor = validate_geometry_descriptor(
        {
            "record_count": record_count,
            "total_bases": total_bases,
            "ordered_record_lengths": ordered_record_lengths,
            "ordered_ambiguous_base_counts": ordered_ambiguous_base_counts,
            "alphabet_policy": ALPHABET_POLICY_UPPERCASE_IUPAC_DNA,
            "record_boundary_policy": RECORD_BOUNDARY_POLICY_NEVER_CROSSED,
        }
    )
    descriptor_sha256 = compute_geometry_descriptor_sha256(descriptor)

    resolved_manifest_sha256 = verified_manifest_sha256

    return {
        "schema_version": 1,
        "artifact_id": GEOMETRY_RECORD_ARTIFACT_ID,
        "derivation_version": GEOMETRY_DERIVATION_VERSION,
        "stage": "NB04_CP1_E03_STRUCTURAL_GEOMETRY_DERIVATION",
        "campaign_id": campaign_id,
        "resource_id": resource_id,
        "organism_id": str(resource["organism_id"]),
        "scientific_name": str(resource["scientific_name"]),
        "taxid": int(resource["taxid"]),
        "accession_version": str(resource["accession_version"]),
        "resource_record_type": str(resource["resource_record_type"]),
        "source_fasta": {
            "fasta_path": fasta_rel,
            "certified_fasta_sha256": expected_fasta_sha256,
            "observed_fasta_sha256": observed_fasta_sha256,
            "identifier_map_path": idmap_rel,
            "certified_identifier_map_sha256": expected_idmap_sha256,
            "observed_identifier_map_sha256": observed_idmap_sha256,
            "resources_manifest_path": MANIFEST,
            "resources_manifest_sha256": resolved_manifest_sha256,
            "g0_certificate_sha256": str(resource["g0_certificate_sha256"]),
        },
        "canonical_order": {
            "order_rule": "NORMALIZED_FASTA_SOURCE_ORDER_SEQUENTIAL_ANALYSIS_ID",
            "analysis_id_range": f"{resource_id}__00000001..{resource_id}__{record_count:08d}",
            "ordered_analysis_ids": ordered_analysis_ids,
            "ordered_source_ids": ordered_source_ids,
        },
        "descriptor_schema_id": GEOMETRY_DESCRIPTOR_SCHEMA_ID,
        "descriptor_sha256": descriptor_sha256,
        "architecture_descriptor": descriptor,
        "verification_against_certified_sources": {
            "fasta_sha256_matches_manifest": True,
            "identifier_map_sha256_matches_manifest": True,
            "identifier_map_record_count": map_row_count,
            "identifier_map_record_count_matches": True,
            "identifier_map_all_record_lengths_match": True,
            "identifier_map_all_sequence_sha256_match": True,
            "identifier_map_all_analysis_ids_match_canonical_order": True,
            "manifest_quality_record_count": int(manifest_record_count),
            "manifest_quality_total_bases": int(manifest_total_bases),
            "manifest_quality_ambiguous_bases": int(manifest_ambiguous_bases),
            "observed_record_count": record_count,
            "observed_total_bases": total_bases,
            "observed_total_ambiguous_bases": total_ambiguous_bases,
            "sum_of_ordered_record_lengths_matches_total_bases": True,
            "vector_length_matches_record_count": True,
            "sum_of_ordered_ambiguous_base_counts_matches_manifest_quality": True,
            "verdict": "PASS",
        },
        "policy_and_scientific_limitations": {
            "coverage_predicate_rule": (
                "A geometry cell covers the resource if and only if all scalars "
                "(record_count, total_bases), integral vectors (ordered_record_lengths, "
                "ordered_ambiguous_base_counts), and policies (alphabet_policy, "
                "record_boundary_policy) of NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 are "
                "identically equal (plan_v003.md section 5). No missing value, summary "
                "statistic, mean, median, histogram, or presumed interval satisfies "
                "this predicate."
            ),
            "candidate_identity_binding_rule": (
                "Only descriptor_sha256 (computed strictly over the 6-field "
                "NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 object without paths, "
                "administrative IDs, or derivation metadata) enters candidate "
                "configuration identity; geometry_record_sha256 covers the full "
                "provenance file."
            ),
            "ambiguity_definition": "IUPAC_DNA_BASE_NOT_IN_ACGT_AFTER_UPPERCASE_NORMALIZATION",
            "prior_state_declaration": (
                "Prior to this E03 read-only derivation, only the aggregate "
                "quality.ambiguous_bases scalar was materialized in the CP1 manifest; "
                "the per-record ordered_ambiguous_base_counts vector remained "
                "explicitly unmaterialized (plan_v003.md section 5)."
            ),
            "simplification_id": "S05",
            "nominal_limitations": list(GEOMETRY_NOMINAL_LIMITATIONS),
            "excluded_from_geometry_predicate": [
                "BASE_COMPOSITION_AND_GC_CONTENT",
                "REPETITIVE_MOTIF_IDENTITY_LOCATION_AND_EXTENT",
                "LOW_COMPLEXITY_REGIONS",
                "PARALOG_FAMILY_STRUCTURE",
                "TSA_REDUNDANCY_AND_FRAGMENTATION",
                "EXACT_INTRARECORD_POSITIONS_AND_RUN_DISTRIBUTIONS_OF_AMBIGUOUS_BASES",
            ],
            "scientific_scope_statement": (
                "Simplification S05 (plan_v003.md sections 5 and 11): discrete geometry "
                "cells preserve exact record_count, total_bases, ordered_record_lengths, "
                "quantitative per-record ambiguity counts, and record boundaries, and "
                "reduce generalization to resources or dimensions outside this descriptor. "
                "Acceptability of this reduction is restricted to geometric dimension "
                "verification under closure A.1 and QA-L and depends on per-query, "
                "per-resource saturation and truncation controls (section 6.6) and the "
                "remaining B4 detectors before any future absence statement. Equal "
                "geometry does not imply biological equivalence, sequence composition "
                "equivalence, equal seedable/effective search space (even under dust=no "
                "and lcase_masking=false), or search recovery equivalence, and makes no "
                "claim of global biological sensitivity."
            ),
            "structural_preparation_only": True,
            "queries_executed": False,
            "recovery_evaluation_executed": False,
            "biological_decision_role": False,
        },
    }


def write_resource_geometry_record(
    root: Path,
    geometry_record: Mapping[str, Any],
    *,
    destination: Path | None = None,
) -> tuple[Path, str, str]:
    """Validate and write a single resource geometry record without overwriting any existing file."""
    root = root.resolve()
    require(
        "descriptor_sha256" in geometry_record,
        "geometry_record missing declared descriptor_sha256",
    )
    descriptor_sha256 = extract_geometry_descriptor_sha256_from_record(geometry_record)
    campaign_id = validate_geometry_campaign_id(geometry_record.get("campaign_id"))
    resource_id = geometry_record.get("resource_id")
    require(
        isinstance(resource_id, str) and bool(RESOURCE_ID.fullmatch(resource_id)),
        f"invalid resource_id in geometry_record: {resource_id!r}",
    )
    rec_count = geometry_record["architecture_descriptor"]["record_count"]
    canon = geometry_record.get("canonical_order")
    require(
        isinstance(canon, Mapping)
        and isinstance(canon.get("ordered_analysis_ids"), list)
        and len(canon["ordered_analysis_ids"]) == rec_count
        and isinstance(canon.get("ordered_source_ids"), list)
        and len(canon["ordered_source_ids"]) == rec_count,
        f"geometry_record canonical_order ID vectors do not match record_count ({rec_count})",
    )
    verif = geometry_record.get("verification_against_certified_sources")
    require(
        isinstance(verif, Mapping) and verif.get("verdict") == "PASS",
        f"geometry_record verification_against_certified_sources verdict must be PASS for {resource_id}",
    )
    target = validate_e03_geometry_destination(
        root,
        destination,
        campaign_id=campaign_id,
        resource_id=resource_id,
    )
    payload = dict(geometry_record)
    encoded = json_bytes(payload)
    geometry_record_sha256 = hashlib.sha256(encoded).hexdigest()
    write_json(target, payload)
    return target, geometry_record_sha256, descriptor_sha256


def derive_and_write_all_resources_geometry(
    root: Path,
    *,
    campaign_id: str = DEFAULT_GEOMETRY_CAMPAIGN_ID,
    destination_overrides: Mapping[str, Path] | None = None,
    expected_reference_sha256: Any = _DEFAULT,
    expected_run_manifest_sha256: Any = _DEFAULT,
    expected_resource_count: Any = _DEFAULT,
    expected_resource_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Derive and sequentially write E03 geometry records for all certified CP1 resources after full pre-write validation."""
    root = root.resolve()
    validate_geometry_campaign_id(campaign_id)

    # Step 1: Verify the authoritative CP1 preservation contract before inspecting resources or touching destinations
    manifest, _, manifest_sha256 = verify_authoritative_cp1_manifest_for_e03(
        root,
        expected_reference_sha256=expected_reference_sha256,
        expected_run_manifest_sha256=expected_run_manifest_sha256,
        expected_resource_count=expected_resource_count,
        expected_resource_ids=expected_resource_ids,
    )
    resources = manifest["resources"]
    resource_ids = [r["resource_id"] for r in resources]
    if destination_overrides:
        unknown = sorted(set(destination_overrides.keys()) - set(resource_ids))
        require(not unknown, f"destination_overrides for unknown resource_id(s): {unknown}")

    # Step 2: Validate all destination paths upfront before any derivation or write
    validated_targets: dict[str, Path] = {}
    for res in resources:
        rid = res["resource_id"]
        override = destination_overrides.get(rid) if destination_overrides else None
        validated_targets[rid] = validate_e03_geometry_destination(
            root,
            override,
            campaign_id=campaign_id,
            resource_id=rid,
        )

    # Step 3: Complete all read-only derivations and cross-checks in memory before any disk write
    derived_records: list[tuple[str, Path, dict[str, Any]]] = []
    for res in resources:
        rid = res["resource_id"]
        record = derive_resource_geometry_record(
            root,
            res,
            campaign_id=campaign_id,
            manifest_sha256=manifest_sha256,
            _verified_manifest_context=(manifest, manifest_sha256),
        )
        derived_records.append((rid, validated_targets[rid], record))

    # Step 4: Sequentially materialize all validated geometry records via write_json
    summary_by_resource: dict[str, dict[str, Any]] = {}
    total_records = 0
    total_bases = 0
    total_ambiguous = 0
    for rid, target, record in derived_records:
        written_path, geom_sha256, desc_sha256 = write_resource_geometry_record(
            root,
            record,
            destination=target,
        )
        desc = record["architecture_descriptor"]
        ver = record["verification_against_certified_sources"]
        rec_count = int(desc["record_count"])
        rec_bases = int(desc["total_bases"])
        rec_ambig = int(ver["observed_total_ambiguous_bases"])
        total_records += rec_count
        total_bases += rec_bases
        total_ambiguous += rec_ambig
        summary_by_resource[rid] = {
            "geometry_record_path": written_path.relative_to(root).as_posix(),
            "geometry_record_sha256": geom_sha256,
            "descriptor_sha256": desc_sha256,
            "fasta_path": record["source_fasta"]["fasta_path"],
            "fasta_sha256": record["source_fasta"]["observed_fasta_sha256"],
            "identifier_map_path": record["source_fasta"]["identifier_map_path"],
            "identifier_map_sha256": record["source_fasta"]["observed_identifier_map_sha256"],
            "record_count": rec_count,
            "total_bases": rec_bases,
            "ambiguous_bases": rec_ambig,
            "alphabet_policy": desc["alphabet_policy"],
            "record_boundary_policy": desc["record_boundary_policy"],
            "identifier_map_verdict": "PASS",
            "manifest_quality_verdict": "PASS",
        }

    return {
        "stage": "NB04_CP1_E03_GEOMETRY_DERIVATION",
        "campaign_id": campaign_id,
        "descriptor_schema_id": GEOMETRY_DESCRIPTOR_SCHEMA_ID,
        "derivation_version": GEOMETRY_DERIVATION_VERSION,
        "resource_count": len(derived_records),
        "total_records_across_resources": total_records,
        "total_bases_across_resources": total_bases,
        "total_ambiguous_bases_across_resources": total_ambiguous,
        "resources": summary_by_resource,
        "queries_executed": False,
        "recovery_evaluation_executed": False,
        "fixtures_materialized": False,
    }



# ======================================================================
# E05 Part 1: build inspection, 31-parameter matrix, output integrity and
# QA configuration state. Only `-version` and `-help` of the tools are run.
# ======================================================================

E05_INSPECTION_ARTIFACT_ID = "NB04_E05_CONFIGURATION_INSPECTION_V1"
E05_INSPECTION_VERSION = "1.0.0"
E05_INSPECTION_DEFAULT_PATH = f"{PRESERVATION_INVENTORY_DIR}/e05_configuration_inspection.json"
E05_U04_RESERVED_PATH = "data/reference/nb04_calibration_candidate_configurations.json"

E05_REQUIRED_TOOLS: tuple[str, ...] = ("blastn", "makeblastdb", "blastdbcmd", "blast_formatter", "dustmasker")

E05_NORMATIVE_DOCUMENTS_SHA256: dict[str, str] = {
    "08_b4_calibration_parameter_matrix_v2_1.tsv": "7731fa6bc8f4523f65d37c130e23885bab4358968ea655b2987712db160b8690",
    "09_b4_calibration_qa_matrix_v2.tsv": "db59d77f44ec6be32962f25cb4da1e3b4f7c58c3c9c1a55348ba4581d57608b0",
    "06_B4_TRUNCATION_AND_COMPLETENESS_CONTRACT_v2_1.md": "9e559f9f3dac621afafb2dff53f7c392a439a76d1ed13bd031a5eb17ce174851",
    "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md": "aa156f77f02b618b878c8f4acac84bf45b36407c86ec9a674e2d5eb82ec3b91a",
}

E05_PARAMETER_MATRIX_HEADER: tuple[str, ...] = (
    "parameter_id", "tool", "parameter", "current_precedent", "candidate_design_space", "parameter_role",
    "biological_decision_role", "calibration_question", "failure_mode", "truncation_relevance",
    "database_size_relevance", "determinism_relevance", "decision_stage", "status", "notes",
)
E05_QA_MATRIX_HEADER: tuple[str, ...] = (
    "qa_id", "criterion", "fixture_dependency", "metric", "expected_behavior", "failure_interpretation",
    "blocks_configuration_freeze", "biological_decision_role", "status",
)

# -outfmt 6 specifiers: the NB01-NB03 precedent, in the order written in the P26 matrix row
# (`current_precedent`), plus `score` (raw score), which plan_v003.md section 8 requires the parser to
# preserve. `nident` and `qcovhsp` are supported by the build but nothing in the matrix, in the G0 policy
# row B4_P26 or in PLAN G.8 requires them, so they are recorded as available and NOT adopted.
E05_OUTFMT_6_PRECEDENT: tuple[str, ...] = (
    "qseqid", "sseqid", "pident", "length", "qlen", "slen", "qstart", "qend", "sstart", "send",
    "sstrand", "evalue", "bitscore", "mismatch", "gapopen", "gaps", "qcovs", "btop",
)
E05_OUTFMT_6_ADDITIONS: tuple[str, ...] = ("score",)
E05_OUTFMT_6_AVAILABLE_NOT_ADOPTED: tuple[str, ...] = ("nident", "qcovhsp")

E05_COORDINATOR_DECISION_RECORD = (
    "docs/implementation/NB04_CP1_PREPARACAO_FREEZE_B4/implementation/cycle-001/coordination.md"
)

STATE_PENDING = "PENDING_CALIBRATION"
STATE_RECORDED = "RECORDED_NOT_DECIDED_IN_U03"
STATE_EXCLUDED = "OPTION_NOT_APPLIED_EXCLUDED_BY_ARCHITECTURE"
STATE_FIXED = "FIXED_BY_ARCHITECTURE_AS_PROPOSED_IN_MATRIX"
STATE_HYPOTHESIS = "STARTING_HYPOTHESIS_RECORDED"
STATE_DECIDED = "DECIDED_BY_COORDINATOR_CONTRACT_CONFORMANCE"
E05_STAGE_STATE: dict[str, str] = {
    "G1_AFTER_CALIBRATION": STATE_PENDING,
    "G1_RECORD_EXPLICITLY": STATE_RECORDED,
    "EXCLUDED_BY_ARCHITECTURE": STATE_EXCLUDED,
}
E05_PARAMETER_IDS: tuple[str, ...] = tuple(f"P{n:02d}" for n in range(1, 32))

# Parameters carried by a command-line flag: the flags looked up in the tool's -help (tool column of the matrix).
E05_PARAMETER_FLAGS: dict[str, tuple[str, ...]] = {
    "P02": ("-task",), "P03": ("-word_size",), "P04": ("-evalue",), "P05": ("-reward",), "P06": ("-penalty",),
    "P07": ("-gapopen",), "P08": ("-gapextend",), "P09": ("-dust",), "P10": ("-soft_masking",),
    "P11": ("-lcase_masking",), "P12": ("-strand",), "P13": ("-max_target_seqs",), "P14": ("-max_hsps",),
    "P15": ("-perc_identity",), "P16": ("-qcov_hsp_perc",), "P17": ("-culling_limit",),
    "P18": ("-best_hit_overhang",), "P19": ("-best_hit_score_edge",), "P20": ("-subject_besthit",),
    "P21": ("-xdrop_ungap", "-xdrop_gap", "-xdrop_gap_final"), "P22": ("-window_size",),
    "P23": ("-dbsize", "-searchsp"), "P24": ("-ungapped",), "P25": ("-sum_stats",), "P26": ("-outfmt",),
    "P27": ("-num_threads",), "P28": ("-dbtype", "-parse_seqids", "-title", "-out"),
    "P29": ("-max_file_sz",),
}

E05_P23_EFFECTIVE_VALUE: dict[str, str] = {
    "-dbsize": "NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET",
    "-searchsp": "NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET",
    "primary_candidate_configurations": "NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET",
    "production_policy": "PENDING_G1_DECISION",
    "qa_f2": "EXPLICIT_NORMALIZATION_SANCTIONED_QA_F2_ONLY_VALUE_AFTER_FREEZE",
    "search_space_policy_token": (
        "NATURAL_SEARCH_SPACE_IN_PRIMARY_CANDIDATES_WITH_QA_F2_EXPLICIT_NORMALIZATION_G1_CONFIRMED"
    ),
}
E05_P30_RULE_TOKEN = "ASCENDING_ASCII_DEFLINE_RECORD_ID_HASHED_WITH_DOWNSTREAM_HSP_TIE_SORT"

# Parameters whose effective value is determinable in E05 Part 1 (decision_stage ARCHITECTURAL_PRE_G1 or
# QA_ONLY_PLUS_G1_PRODUCTION_DECISION): (state, value).
E05_EFFECTIVE_VALUES: dict[str, tuple[str, Any]] = {
    "P01": (STATE_FIXED, "blastn"),
    "P09": (STATE_FIXED, "no"),
    "P11": (STATE_FIXED, "false"),
    "P12": (STATE_FIXED, "both"),
    "P23": (STATE_DECIDED, E05_P23_EFFECTIVE_VALUE),
    "P26": (
        STATE_HYPOTHESIS,
        {
            "adopted_specifiers_precedent_in_matrix_order": list(E05_OUTFMT_6_PRECEDENT),
            "adopted_specifiers_added_from_plan_section_8": list(E05_OUTFMT_6_ADDITIONS),
            "available_not_adopted": list(E05_OUTFMT_6_AVAILABLE_NOT_ADOPTED),
            "field_order_closed": False,
            "authoritative_output_format": "11",
        },
    ),
    "P28": (STATE_HYPOTHESIS, {"-dbtype": "nucl", "-parse_seqids": True}),
    "P30": (STATE_DECIDED, E05_P30_RULE_TOKEN),
    "P31": (STATE_HYPOTHESIS, None),  # value taken verbatim from the matrix candidate_design_space
}

E05_COORDINATOR_DECISIONS: dict[str, dict[str, Any]] = {
    "P30": {
        "decision_record": E05_COORDINATOR_DECISION_RECORD,
        "decision_section": "20.8",
        "decision_class": "ESTABLISHED_BY_CONTRACT_NOT_RESERVED",
        "decided_by": "IMPLEMENTATION_COORDINATOR",
        "decision_date": "2026-10-25",
        "decision": E05_P30_RULE_TOKEN,
        "classification_basis": (
            "Conformance to the contract plus technical instantiation: the matrix requires a declared, hashed "
            "canonical record order (status REQUIRES_DESIGN) and does not literally write the ASCII rule."
        ),
        "scope": (
            "Fixes canonical_record_order_rule (plan_v003.md section 7) for the six certified CP1 resources and "
            "for future E04 synthetic fixtures. It does not decide the HSP tie-break in the output."
        ),
        "alternatives_considered": {
            "P30_ALT_1_ASCENDING_ASCII_DEFLINE_RECORD_ID": "ADOPTED. The six certified FASTA files already satisfy it (section b, canonical_record_order_check).",
            "P30_ALT_2_RESORT_BY_UPSTREAM_SOURCE_ID": "REJECTED. It would invalidate the certified normalized.fasta files, identifier maps, indexes, manifest and E03 descriptor hashes.",
            "P30_ALT_3_UNCONSTRAINED_INPUT_ORDER": "REJECTED. It violates P30 and leaves QA-E without a baseline order to permute.",
        },
    },
    "P23": {
        "decision_record": E05_COORDINATOR_DECISION_RECORD,
        "decision_section": "20.9",
        "decision_class": "ESTABLISHED_BY_CONTRACT_NOT_RESERVED",
        "decided_by": "IMPLEMENTATION_COORDINATOR",
        "decision_date": "2026-10-25",
        "decision": E05_P23_EFFECTIVE_VALUE["search_space_policy_token"],
        "scope": (
            "Covers the candidate configurations before the freeze and the QA-F2 normalization. The production "
            "policy is NOT decided: the matrix says 'preferred', so it remains pending at gate G1."
        ),
        "alternatives_considered": {
            "P23_ALT_1_NATURAL_PRIMARY_WITH_QA_F2_NORMALIZATION": "ADOPTED.",
            "P23_ALT_2_FIXED_SEARCH_SPACE_IN_PRIMARY_CANDIDATES": "REJECTED. Reported E-values would no longer describe the resource searched.",
            "P23_ALT_3_NEVER_NORMALIZE_EVEN_IN_QA_F2": "REJECTED. The matrix sanctions normalization as a QA-F2 technique.",
        },
    },
}

# Corrections issued by the Coordinator to its own earlier instructions (U03 correction round, Coordinator message
# 028). They are recorded so the history does not attribute these premises to the Programmer.
E05_COORDINATOR_INSTRUCTION_CORRECTIONS: tuple[dict[str, str], ...] = (
    {
        "correction_id": "COORDINATOR_ERROR_1_QA_METRIC_COMPUTABILITY",
        "earlier_instruction": "Condition 6: state that no QA metric is computable without a search.",
        "correction": (
            "Withdrawn. It generalized 'no QA metric of this campaign was computed in U03' into an impossibility the "
            "matrix does not support (for example QA-P defines a set intersection of identifiers and QA-I defines parser "
            "outcomes on valid and corrupted tables). The record now states only what was observed and qualifies the rest."
        ),
    },
    {
        "correction_id": "COORDINATOR_ERROR_2_EXPORT_COMMAND_THREE_PARAMETERS",
        "earlier_instruction": "Precision 3: the export command must be reconstructible with the three formatter parameters explicit.",
        "correction": (
            "Withdrawn. The help declares -max_target_seqs incompatible with -num_descriptions and -num_alignments, and "
            "-num_descriptions not applicable to outfmt greater than 4, so passing all three would be illegal. Correct "
            "formulation: a reconstructible record of values or of explicit not-applied states in a legal combination."
        ),
    },
    {
        "correction_id": "COORDINATOR_ERROR_3_EXPORT_INTEGRITY_ONLY_SUBJECT_COUNT",
        "earlier_instruction": "Precision 2: the verification must compare, per query, the subject count of the derived tabular export with that of the archive.",
        "correction": (
            "Insufficient. A subject count alone does not demonstrate preservation of every HSP and every query. The "
            "future integrity contract must also cover loss of HSPs and queries, the semantic equality required of the "
            "export, a legitimately empty output and cuts at a line boundary."
        ),
    },
)

# QA criteria: (configuration preconditions inspected in E05 Part 1, deferred to, note). No QA metric is
# computed here; every note avoids numbers read from the build so that it cannot drift from the observed help.
_E05_EXEC = "E04 fixtures and E08 search execution"
E05_QA_SPEC: dict[str, tuple[bool, str, str]] = {
    "QA-A": (False, _E05_EXEC, "Requires planted-alignment fixtures and search execution."),
    "QA-B": (False, _E05_EXEC, "Requires planted coordinates and search execution."),
    "QA-C": (True, "E08 search execution", "Inspected: the -strand record (P12) and the sstrand specifier support (section d). Minus-strand coordinate behaviour requires search execution."),
    "QA-D": (False, _E05_EXEC, "Requires repeated executions."),
    "QA-E": (True, _E05_EXEC, "Inspected: P30 canonical record order and its check on the six certified FASTA files (section b). Result-set equality across record orders requires fixtures and search execution."),
    "QA-F1": (False, _E05_EXEC, "Requires integral and sharded executions."),
    "QA-F2": (True, "E08 search execution", "Inspected: -dbsize and -searchsp are documented by the build (P23 record). The normalized comparison requires a frozen reference value and search execution."),
    "QA-G": (True, "E02 (PC13 versus QA-G is reserved), E04 and E08", "Inspected: documented build defaults recorded for P13 and P14 without assigning values; P15-P20 recorded as unapplied; export-path default caps recorded (section d). Saturation indicators require search execution. The PC13 versus QA-G tension is a reserved E02 decision and is not resolved here."),
    "QA-H": (True, "E08 search execution", "Inspected: P04, P23, P25 and P26 records. Score and E-value series require search execution."),
    "QA-I": (True, "E04/E06 parser tests and E08", "Inspected: archive output availability in blastn and archive input in blast_formatter (section d). Evaluating parser outcomes on valid, truncated, malformed and corrupted tables needs the parser and those tables; this metric is structural and does not by definition need a search, and it is not evaluated in this unit."),
    "QA-J": (False, _E05_EXEC, "Requires repeated process invocations."),
    "QA-K": (True, "E08 calibration artifacts", "Inspected: tool name, version, package build and prospective executable SHA256 for each tool (section a) and a state for each of the 31 parameters (section c). Fixture hashes, database binary hashes, command line and UTC date belong to later artifacts."),
    "QA-L": (True, "E02 scale cells (reserved), E04 and E08", "Inspected: exact total_bases and record_count of the six real resources from the E03 geometry records (section b). Class envelopes require reserved scale-cell decisions and fixtures."),
    "QA-M": (True, "E06 harness and E08 execution", "Inspected: each of the 31 matrix parameters has a state, value or documented-default status (section c). The matrix does not enumerate every build option (section c, build_help_flags_outside_matrix); enlarging the parameter set would be a normative change outside the scope of any agent. Comparing reconstructed and executed command lines requires the harness and executions."),
    "QA-N": (False, _E05_EXEC, "Requires no-planted-alignment background fixtures and search execution."),
    "QA-O": (True, "E08 search execution", "Inspected: P24 recorded as unapplied and P07/P08 recorded as pending. Gapped recovery requires search execution."),
    "QA-P": (False, "E02/E04 fixture-role partitioning and E08 selection records", "Needs the campaign's fixture roles and selection records, which do not exist yet. The metric (set intersection of identifiers) is structural and does not by definition need a search; it is not evaluated in this unit."),
    "QA-Q": (True, "E08 search execution", "Inspected: the P27 record. Result-set invariance across thread counts requires search execution."),
    "QA-R": (False, _E05_EXEC, "Requires timing and memory measurements during executions."),
}

E05_INFORMATIONAL_FLAGS = frozenset({"-h", "-help", "-help-full", "-version"})
E05_EXPORT_PATH_CAP_FLAGS: tuple[str, ...] = ("-max_target_seqs", "-num_descriptions", "-num_alignments")


def validate_e05_inspection_destination(root: Path, destination: Path | None = None) -> Path:
    """Validate the E05 Part 1 inspection destination before any write; refuse pre-existing or protected paths."""
    root = root.resolve()
    if destination is None:
        target = relative_path(root, E05_INSPECTION_DEFAULT_PATH)
    else:
        raw_dest = Path(destination)
        target = (root / raw_dest).resolve() if not raw_dest.is_absolute() else raw_dest.resolve()
    require(target.is_relative_to(root), f"E05 inspection destination outside project root: {target}")
    rel = target.relative_to(root).as_posix()
    require(
        rel != E05_U04_RESERVED_PATH,
        f"E05 Part 1 inspection artifact must not occupy {E05_U04_RESERVED_PATH} (reserved for U04)",
    )
    require(
        rel.startswith(f"{PRESERVATION_INVENTORY_DIR}/") and rel.endswith(".json"),
        f"E05 inspection destination outside authorized directory {PRESERVATION_INVENTORY_DIR}/: {rel}",
    )
    require(
        target.name != PRESERVATION_INVENTORY_FILENAME,
        f"E05 inspection destination must not target a preservation inventory file: {rel}",
    )
    require(not target.exists(), f"E05 inspection destination already exists and must never be overwritten: {target}")
    return target


def _read_matrix_tsv(text: str, header: tuple[str, ...], name: str, key: str) -> dict[str, dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip()]
    rows = list(csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))
    require(rows and tuple(rows[0]) == header, f"unexpected header in {name}: {rows[0] if rows else None!r}")
    out: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        require(len(row) == len(header), f"malformed row in {name}: {row!r}")
        item = dict(zip(header, row, strict=True))
        require(item[key] not in out, f"duplicate {key} in {name}: {item[key]}")
        out[item[key]] = item
    return out


def verify_and_read_e05_normative_inputs(
    root: Path,
    corpus_directories: Mapping[str, Path],
    *,
    expected_normative_sha256: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify the SHA256 of the 4 NB04_B5_INPUTS documents before reading them, then parse both matrices."""
    root = root.resolve()
    expected_map = dict(E05_NORMATIVE_DOCUMENTS_SHA256 if expected_normative_sha256 is None else expected_normative_sha256)
    require(
        set(expected_map) == set(E05_NORMATIVE_DOCUMENTS_SHA256),
        f"E05 normative document set mismatch: {sorted(expected_map)}",
    )
    cert, _ = verify_g0_certified_artifacts_inventory(root)
    cert_norm = cert.get("normative_documents", {})

    corpus_dir_raw = corpus_directories.get("NB04_B5_INPUTS")
    require(corpus_dir_raw is not None, "NORMATIVE_DOCUMENT_INACCESSIBLE: corpus NB04_B5_INPUTS directory not provided")
    corpus_dir = Path(corpus_dir_raw).resolve()
    require(corpus_dir.is_dir(), "NORMATIVE_DOCUMENT_INACCESSIBLE: corpus NB04_B5_INPUTS directory does not exist")

    verified_docs: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    for doc_name in sorted(expected_map):
        expected_sha = expected_map[doc_name]
        spec_entry = NORMATIVE_DOCUMENTS_SPEC.get(doc_name)
        if spec_entry is not None:
            require(
                spec_entry.get("hash_mode") == "RAW"
                and spec_entry.get("corpus_id") == "NB04_B5_INPUTS"
                and spec_entry.get("expected_sha256") == expected_sha,
                f"E05 normative specification mismatch for {doc_name}",
            )
        if doc_name in cert_norm:
            require(cert_norm[doc_name] == expected_sha, f"G0 certificate normative SHA256 mismatch for {doc_name}")
        candidate = corpus_dir / doc_name
        require(candidate.is_file(), f"NORMATIVE_DOCUMENT_INACCESSIBLE: {doc_name}")
        raw_bytes = candidate.read_bytes()
        observed_sha = hashlib.sha256(raw_bytes).hexdigest()
        require(
            observed_sha == expected_sha,
            f"E05 normative document SHA256 mismatch before reading {doc_name}: "
            f"expected={expected_sha} observed={observed_sha}",
        )
        texts[doc_name] = raw_bytes.decode("utf-8").replace("\r\n", "\n")
        verified_docs[doc_name] = {
            "corpus_id": "NB04_B5_INPUTS",
            "expected_sha256": expected_sha,
            "hash_mode": "RAW",
            "location_class": "EXTERNAL_LOCAL_CORPUS",
            "observed_sha256": observed_sha,
            "size_bytes": len(raw_bytes),
            "status": "VERIFIED_BEFORE_READ",
        }

    parameter_rows = _read_matrix_tsv(
        texts["08_b4_calibration_parameter_matrix_v2_1.tsv"],
        E05_PARAMETER_MATRIX_HEADER,
        "08_b4_calibration_parameter_matrix_v2_1.tsv",
        "parameter_id",
    )
    require(
        tuple(sorted(parameter_rows)) == E05_PARAMETER_IDS,
        f"parameter matrix must contain exactly P01..P31; observed={sorted(parameter_rows)}",
    )
    for pid, row in parameter_rows.items():
        require(row["biological_decision_role"] == "false", f"{pid} must carry biological_decision_role=false")
    qa_rows = _read_matrix_tsv(
        texts["09_b4_calibration_qa_matrix_v2.tsv"],
        E05_QA_MATRIX_HEADER,
        "09_b4_calibration_qa_matrix_v2.tsv",
        "qa_id",
    )
    require(
        set(qa_rows) == set(E05_QA_SPEC),
        f"QA matrix must contain exactly the 19 criteria {sorted(E05_QA_SPEC)}; observed={sorted(qa_rows)}",
    )

    # Verbatim contractual reason for the PROPOSED_EXCLUDED parameters (design document section 7).
    match = re.search(
        r"\*\*`PROPOSED_EXCLUDED`\*\*.*?(?=\*\*`OPEN_DESIGN_QUESTION`\*\*)",
        texts["05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md"],
        flags=re.DOTALL,
    )
    require(match is not None, "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md: PROPOSED_EXCLUDED passage not found")
    excluded_passage = match.group(0).strip()
    for pid, row in parameter_rows.items():
        if row["decision_stage"] == "EXCLUDED_BY_ARCHITECTURE":
            require(
                row["parameter"] in excluded_passage,
                f"{pid} {row['parameter']} is not named in the design document PROPOSED_EXCLUDED passage",
            )
    return {
        "verification_summary": {
            "corpus_id": "NB04_B5_INPUTS",
            "documents": verified_docs,
            "personal_paths_omitted": True,
            "total_documents_verified": len(verified_docs),
            "verdict": "PASS",
        },
        "parameter_matrix_rows": parameter_rows,
        "qa_matrix_rows": qa_rows,
        "excluded_passage": excluded_passage,
    }


def parse_blast_help_flags(help_text: str) -> dict[str, dict[str, Any]]:
    """Parse NCBI BLAST+ `-help` into per-flag metadata; `Default = ...` is taken only when the help states it."""
    flags: dict[str, list[str]] = {}
    current: str | None = None
    in_arguments = False
    for raw_line in help_text.splitlines():
        stripped = raw_line.strip()
        if stripped in ("REQUIRED ARGUMENTS", "OPTIONAL ARGUMENTS"):
            in_arguments = True
            continue
        if not in_arguments:
            continue
        if raw_line.startswith(" ***"):
            current = None
            continue
        match = re.match(r"^ (-[A-Za-z0-9_-]+)(?:\s|$)", raw_line)
        if match:
            current = match.group(1)
            flags[current] = [stripped]
        elif current is not None and stripped:
            flags[current].append(stripped)

    parsed: dict[str, dict[str, Any]] = {}
    for flag, lines in flags.items():
        body: list[str] = []
        constraints: list[str] = []
        for line in lines[1:]:
            if constraints or line.startswith(("* Incompatible with:", "* Requires:")):
                constraints.append(line)
            else:
                body.append(line)
        description = " ".join(body)
        default_match = re.search(r"(Default = .*?)$", description)
        parsed[flag] = {
            "constraints": " ".join(constraints) if constraints else None,
            "description": description,
            "documented_default_in_build_help": (
                default_match.group(1).strip() if default_match else "NOT_DOCUMENTED_IN_BUILD_HELP"
            ),
            "flag": flag,
            "header_line": lines[0],
            "present_in_build_help": True,
        }
    return parsed


def _default_tool_which(tool: str) -> str | None:
    """Resolve a tool in PATH or alongside the active Python executable (e.g. conda env bin/)."""
    found = shutil.which(tool)
    if found:
        return found
    candidate = Path(sys.executable).resolve().parent / tool
    return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None


def _e05_not_applicable_tool(tool: str, reason: str) -> dict[str, Any]:
    return {
        "applicability_justification": (
            f"{reason}; recorded as NOT_APPLICABLE with this justification and never presumed as passing."
        ),
        "executable_sha256": "NOT_APPLICABLE",
        "help_output_sha256_lf": "NOT_APPLICABLE",
        "matches_receipt_build": False,
        "package_build": "NOT_APPLICABLE",
        "status": "NOT_APPLICABLE",
        "tool_name": tool,
        "tool_version": "NOT_APPLICABLE",
    }


# Accepted whole-file identities of the six E03 geometry records closed in U02 (coordination.md section 17.4;
# the files are under the Git-ignored data/external/nto/). A geometry record is consumed by E05 only if its
# whole-file SHA256 equals the accepted identity; an internally consistent descriptor hash is not enough.
EXPECTED_GEOMETRY_RECORD_SHA256: dict[str, str] = {
    "AM_GCF003254395_2_RNA": "59053ae756ed96b13bca9d6fb41ced3df57e69e8e4c4c01921fa4a13c71ef655",
    "OI_GCYL01_TSA": "3db2cf98c3457a44c49ee004dd72f23b8f3c86a589169dcfa3e470d43df01ff9",
    "PM_GKDL01_TSA": "18de969107295f1a9313884de3bdd88d5cccfd30bd718d45b36939b032d9d632",
    "RM_GCF003676215_2_RNA": "1025de99050f1eff490ee78993701378d67eb00f6fa79d8f363739aa2af78f04",
    "TA_GCA036937485_2_CDS": "b1dc59a7f1ae40f03223c3e9624692a0b7cd4f90c60288c59fd7bf94091a3bec",
    "ZM_GCF902167145_1_RNA": "cc572d3cb424b205f85f6f2833ba932f3b93902a5ea455a1fb20b01442d53ae7",
}


def _e05_geometry_derivations(
    root: Path,
    manifest: Mapping[str, Any],
    campaign_id: str,
    require_e03_geometry: bool,
    accepted_record_sha256: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    """Consume each E03 geometry record only after its whole-file identity and its content match the authoritative sources.

    A record that fails either control is refused (the inspection stops); it is never reported as verified and none
    of its quantities reaches the inspection record.
    """
    derivations: dict[str, dict[str, Any]] = {}
    for resource in sorted(manifest.get("resources", []), key=lambda item: item["resource_id"]):
        rid = resource["resource_id"]
        geom_rel = f"data/external/nto/{campaign_id}/geometry/{rid}.json"
        geom_path = relative_path(root, geom_rel)
        if not geom_path.is_file():
            require(not require_e03_geometry, f"required E03 geometry record missing for {rid}: {geom_rel}")
            derivations[rid] = {"geometry_record_path": geom_rel, "status": "NOT_MATERIALIZED"}
            continue
        # Control 1: whole-file identity against the accepted U02 identity.
        accepted = accepted_record_sha256.get(rid)
        require(accepted, f"no accepted E03 geometry record identity for {rid}; it is not consumed as verified")
        record_sha256 = digest(geom_path)
        require(
            record_sha256 == accepted,
            f"E03 geometry record identity mismatch for {rid}: accepted={accepted} observed={record_sha256}",
        )
        # Control 2: content against the authoritative manifest, scalars, vectors and the ID list (order and cardinality).
        record = json.loads(geom_path.read_text("utf-8"))
        descriptor = validate_geometry_descriptor(record.get("architecture_descriptor"))
        descriptor_sha = extract_geometry_descriptor_sha256_from_record(record)
        source = record.get("source_fasta", {})
        quality = resource["quality"]
        ids = record["canonical_order"]["ordered_analysis_ids"]
        count = descriptor["record_count"]
        lengths = descriptor["ordered_record_lengths"]
        require(
            record.get("resource_id") == rid
            and source.get("observed_fasta_sha256") == quality["fasta_sha256"]
            and source.get("observed_identifier_map_sha256") == quality["identifier_map_sha256"]
            and count == quality["record_count"]
            and descriptor["total_bases"] == quality["total_bases"]
            and sum(descriptor["ordered_ambiguous_base_counts"]) == quality["ambiguous_bases"]
            and min(lengths) == quality["minimum_length"]
            and max(lengths) == quality["maximum_length"]
            and ids == [f"{rid}__{index:08d}" for index in range(1, count + 1)],
            f"E03 geometry record content inconsistent with the authoritative CP1 manifest for {rid}",
        )
        # The identifier map is hash-bound by the authoritative manifest barrier above; the vectors must agree with it.
        with relative_path(root, resource["identifier_map_path"]).open("r", encoding="utf-8", newline="") as stream:
            map_rows = list(csv.DictReader(stream, delimiter="\t"))
        require(
            [row["analysis_id"] for row in map_rows] == ids
            and [int(row["length_nt"]) for row in map_rows] == lengths
            and [row["source_id"] for row in map_rows] == record["canonical_order"]["ordered_source_ids"],
            f"E03 geometry record vectors inconsistent with the authoritative identifier map for {rid}",
        )
        derivations[rid] = {
            "canonical_record_order_check": {
                "fasta_sha256": source["observed_fasta_sha256"],
                "ordered_record_id_count": len(ids),
                "ordered_record_id_count_matches_manifest_record_count": len(ids) == quality["record_count"],
                "strictly_ascending_ascii_record_id": all(a < b for a, b in zip(ids, ids[1:])),
            },
            "descriptor_sha256": descriptor_sha,
            "geometry_record_path": geom_rel,
            "geometry_record_sha256": record_sha256,
            "status": "VERIFIED_AGAINST_ACCEPTED_RECORD_IDENTITY_AND_AUTHORITATIVE_CP1_MANIFEST",
            "total_bases": descriptor["total_bases"],
        }
    return derivations


def _receipt_max_file_size(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Whether -max_file_sz was passed in a makeblastdb receipt command, and the size its stdout reported."""
    reported = re.search(r"Maximum file size:\s*(\d+)B", str(receipt.get("stdout", "")))
    return {
        "max_file_sz_flag_passed_in_recorded_command": "-max_file_sz" in receipt.get("command", []),
        "stdout_reported_maximum_file_size_bytes": int(reported.group(1)) if reported else None,
    }


def _e05_receipt_makeblastdb_options(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Structured provenance for P29: the historical size limit was reported by makeblastdb, not passed by the project."""
    by_resource: dict[str, dict[str, Any]] = {}
    for resource in sorted(manifest.get("resources", []), key=lambda item: item["resource_id"]):
        receipt_path = relative_path(root, resource["fasta_path"]).parent / "database_build.json"
        by_resource[resource["resource_id"]] = _receipt_max_file_size(json.loads(receipt_path.read_text("utf-8")))
    return {
        "p29_status": "PENDING_NO_VALUE_ASSIGNED",
        "receipts_by_resource": by_resource,
        "statement": (
            "Where max_file_sz_flag_passed_in_recorded_command is false, the size in the receipt stdout is the value "
            "makeblastdb reported, not an option passed by the project. It must not be promoted to an explicitly passed "
            "flag in U04. P29 stays pending and no value is assigned here."
        ),
    }


def inspect_e05_tool_builds_and_help(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    campaign_id: str = DEFAULT_GEOMETRY_CAMPAIGN_ID,
    which_resolver: Callable[[str], str | None] = _default_tool_which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_e03_geometry: bool = True,
    expected_geometry_record_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Observe `-version`/`-help` of the 5 tools (reusing E01 observation) and compare with receipts and E03 records."""
    root = root.resolve()
    accepted_geometry = EXPECTED_GEOMETRY_RECORD_SHA256 if expected_geometry_record_sha256 is None else expected_geometry_record_sha256
    observation = observe_blast_tool_builds(
        root, manifest, tool_names=E05_REQUIRED_TOOLS, which_resolver=which_resolver, runner=runner
    )
    reuse_block_reasons = list(observation["reuse_block_reasons"])
    tools: dict[str, dict[str, Any]] = {}
    help_texts: dict[str, str] = {}
    for tool, obs in observation["observed_tools"].items():
        if obs["status"] != "OBSERVED":
            tools[tool] = _e05_not_applicable_tool(tool, str(obs["reason"]))
            continue
        try:
            help_proc = runner(
                [str(Path(which_resolver(tool)).resolve()), "-help"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            help_text = (help_proc.stdout or "").replace("\r\n", "\n")
            reason = None if help_proc.returncode == 0 and help_text.strip() else f"{tool} -help returned code {help_proc.returncode} or empty output"
        except (OSError, subprocess.SubprocessError) as exc:
            help_text, reason = "", f"{tool} -help execution failed: {exc}"
        if reason is not None:
            reuse_block_reasons.append(f"{tool}: NOT_APPLICABLE ({reason})")
            tools[tool] = _e05_not_applicable_tool(tool, reason)
            continue
        help_texts[tool] = help_text
        tools[tool] = {
            "applicability_justification": f"Observed in the canonical environment via read-only `{tool} -version` and `{tool} -help` (plan_v003.md section 7 item 2).",
            "executable_bytes": obs["prospective_executable_bytes"],
            "executable_sha256": obs["prospective_executable_sha256"],
            "executable_sha256_scope": "PROSPECTIVE_CURRENT_BINARY_ONLY_NEVER_ATTRIBUTED_TO_HISTORICAL_BUILDS",
            "help_output_sha256_lf": hashlib.sha256(help_text.encode("utf-8")).hexdigest(),
            "matches_receipt_build": obs["matches_historical_receipt_version_package_build"],
            "package_build": f"{obs['package_version']}, build {obs['build_date']}",
            "raw_version_output": obs["raw_version_output"],
            "status": "OBSERVED",
            "tool_name": tool,
            "tool_version": obs["tool_version"],
            "tool_version_compared_with_receipt": tool not in INDEPENDENTLY_VERSIONED_TOOLS,
        }

    all_observed = all(item["status"] == "OBSERVED" for item in tools.values())
    all_match = all_observed and all(item["matches_receipt_build"] for item in tools.values())
    if all_match:
        overall, comparison = "ALL_FIVE_TOOLS_OBSERVED_AND_MATCH_RECEIPT_PACKAGE_BUILD", "MAKEBLASTDB_MATCHES_RECEIPTS_AND_ALL_FIVE_TOOLS_SHARE_PACKAGE_BUILD"
    elif not all_observed:
        overall, comparison = "INCOMPLETE_TOOLSET_NOT_APPLICABLE_RECORDED", "TOOL_MISSING_OR_UNINSPECTABLE_REUSE_BLOCKED"
    else:
        overall, comparison = "ALL_FIVE_TOOLS_OBSERVED_WITH_BUILD_DIVERGENCE", "BUILD_DIVERGENCE_DETECTED_REUSE_BLOCKED"

    section_a = {
        "all_five_tools_observed": all_observed,
        "only_version_and_help_invoked": True,
        "overall_status": overall,
        "required_tools": list(E05_REQUIRED_TOOLS),
        "searches_executed": False,
        "tools": tools,
    }
    section_b = {
        "comparison_status": comparison,
        "current_e03_geometry_derivations": _e05_geometry_derivations(
            root, manifest, campaign_id, require_e03_geometry, accepted_geometry
        ),
        "equivalent_build_reuse_blocked": not all_match,
        "historical_cp1_database_build_receipts": observation["historical_receipt_reference"],
        "historical_makeblastdb_receipt_options": _e05_receipt_makeblastdb_options(root, manifest),
        "receipt_coverage_declaration": {
            "covered_by_database_build_receipts": [
                "makeblastdb tool_version and package build (the `tool` field)",
                "makeblastdb command line with its flags (-dbtype, -parse_seqids, -blastdb_version, -taxid, -title, -out)",
                "per-volume index_sha256 digests",
                "searches_executed=False attestation",
            ],
            "not_covered_by_database_build_receipts": [
                "executable SHA256 of makeblastdb",
                "tool_version, package build or executable SHA256 of blastn, blastdbcmd, blast_formatter and dustmasker",
            ],
            "scope_statement": (
                "The `tool` field of the six database_build.json receipts records only the makeblastdb version "
                "and package build string. Prospective executable_sha256 values in section a apply to the current "
                "binaries only and are not attributed retrospectively to the historical construction."
            ),
        },
        "retrospective_executable_hash_attributed": False,
        "reuse_block_reasons": reuse_block_reasons,
    }
    return section_a, section_b, help_texts


def _export_cap_established(formatter_flags: Mapping[str, Mapping[str, Any]]) -> str:
    """State only what the inspected blast_formatter help actually shows for the export-path cap flags."""
    if not formatter_flags:
        return "blast_formatter help was not inspected; nothing is established about export-path default caps."
    documented = [
        flag for flag in E05_EXPORT_PATH_CAP_FLAGS
        if formatter_flags.get(flag, {}).get("documented_default_in_build_help", "NOT_DOCUMENTED_IN_BUILD_HELP")
        != "NOT_DOCUMENTED_IN_BUILD_HELP"
    ]
    if not documented:
        return "The inspected blast_formatter help documents no default for -max_target_seqs, -num_descriptions or -num_alignments."
    undocumented = [flag for flag in E05_EXPORT_PATH_CAP_FLAGS if flag not in documented]
    return (
        f"The inspected blast_formatter help documents a default for {', '.join(documented)}, independent of the "
        "blastn search flag"
        + (f"; it documents none for {', '.join(undocumented)}." if undocumented else ".")
    )


def inspect_e05_output_integrity_mechanism(
    observed_tools: Mapping[str, Mapping[str, Any]], help_texts: Mapping[str, str]
) -> dict[str, Any]:
    """Determine from the build help whether the ASN.1 archive plus blast_formatter tabular export is available."""
    parsed = {tool: parse_blast_help_flags(help_texts[tool]) for tool in ("blastn", "blast_formatter") if tool in help_texts}
    blastn_help = help_texts.get("blastn", "")
    formatter_help = help_texts.get("blast_formatter", "")
    formatter_flags = parsed.get("blast_formatter", {})
    blastn_flags = parsed.get("blastn", {})

    def lacks(specifiers: Sequence[str], text: str) -> list[str]:
        return [s for s in specifiers if not re.search(rf"\b{re.escape(s)}\s+means\b", text)]

    adopted = E05_OUTFMT_6_PRECEDENT + E05_OUTFMT_6_ADDITIONS
    missing_blastn = lacks(adopted, blastn_help)
    missing_formatter = lacks(adopted, formatter_help)
    archive_in_blastn = "-outfmt" in blastn_flags and "11 = BLAST archive (ASN.1)" in blastn_help
    archive_in_formatter = "BLAST Archive format in ASN.1" in formatter_flags.get("-archive", {}).get("description", "")
    tabular_in_formatter = "-outfmt" in formatter_flags and "6 = Tabular" in formatter_help
    supported = (
        archive_in_blastn and archive_in_formatter and tabular_in_formatter
        and not missing_blastn and not missing_formatter
    )

    def cap(flags: Mapping[str, Mapping[str, Any]], flag: str) -> dict[str, Any]:
        item = flags.get(flag)
        return {
            "constraints": item["constraints"] if item else None,
            "documented_default_in_build_help": item["documented_default_in_build_help"] if item else "NOT_DOCUMENTED_IN_BUILD_HELP",
            "present_in_build_help": bool(item),
        }

    return {
        "adopted_tabular_specifiers": list(adopted),
        "available_not_adopted_specifiers": {
            s: not lacks([s], blastn_help) and not lacks([s], formatter_help) for s in E05_OUTFMT_6_AVAILABLE_NOT_ADOPTED
        },
        "blast_archive_outfmt_11_available_in_blastn": archive_in_blastn,
        "blast_formatter_archive_input_available": archive_in_formatter,
        "blast_formatter_missing_adopted_specifiers": missing_formatter,
        "blast_formatter_outfmt_6_available": tabular_in_formatter,
        "blastn_missing_adopted_specifiers": missing_blastn,
        "export_path_default_cap_observation": {
            "classification": "INSPECTION_OBSERVATION_WITH_CONDITION_TO_VERIFY",
            "blast_formatter_flags": {flag: cap(formatter_flags, flag) for flag in E05_EXPORT_PATH_CAP_FLAGS},
            "blastn_search_stage_max_target_seqs": cap(blastn_flags, "-max_target_seqs"),
            "destination": "E04 and E06",
            "distinctness": (
                "The blastn -max_target_seqs (search stage, parameter P13) and the blast_formatter -max_target_seqs "
                "(export stage) are distinct caps of distinct tools at distinct stages, whatever their documented defaults."
            ),
            "established": _export_cap_established(formatter_flags),
            "not_established": (
                "Whether this default truncates the tabular export of an archive holding more subjects per query "
                "than the default. Verifying it requires running blast_formatter on an archive, which requires a "
                "search and is forbidden in this unit. Truncation is not asserted."
            ),
            "conditions_to_verify": [
                (
                    "The future output-integrity contract must cover loss of HSPs and loss of queries, the semantic "
                    "equality required of the export, a legitimately empty output and cuts at a line boundary. "
                    "Comparing per-query subject counts alone does not demonstrate that every HSP and every query was preserved."
                ),
                (
                    "The export command must be reconstructible from a record of values, or of explicit not-applied "
                    "states, for these options, in a combination that respects the constraints recorded above "
                    "(options the help declares incompatible cannot all be passed). No values and no combination are fixed here."
                ),
            ],
            "payload_boundary": (
                "No field is added to the section 7 payload: its schema is closed and these caps do not belong to "
                "search_parameters. They belong to the contract referenced by "
                "execution_architecture.output_integrity_contract_id. If no existing contract identifier can carry them, "
                "that is a normative gap to be reported, not an extension of the schema."
            ),
        },
        "qa_i_mechanism_status": (
            "SUFFICIENT_MECHANISM_AVAILABLE_IN_PINNED_BUILD_EXECUTION_VERIFICATION_IN_E06_AND_E08"
            if supported else "QA_I_PENDING_NO_SUFFICIENT_MECHANISM_CONFIRMED"
        ),
        "selected_mechanism": (
            "IDENTIFIED_BLAST_ASN1_ARCHIVE_WITH_VERIFIABLE_BLAST_FORMATTER_TABULAR_EXPORT"
            if supported else "INSUFFICIENT_BUILD_SUPPORT_QA_I_PENDING"
        ),
        "termination_marker_and_query_count_fallback_required": not supported,
        "termination_marker_fallback_disposition": (
            "NOT_REQUIRED: the pinned blastn documents `11 = BLAST archive (ASN.1)` and the pinned blast_formatter "
            "documents `-archive` with `-outfmt 6` and every adopted specifier (plan_v003.md section 8)."
            if supported else
            "Archive output or blast_formatter archive export was not confirmed in the inspected build; without a "
            "verified termination-marker and per-query-count alternative QA-I remains pending."
        ),
    }


def validate_e05_parameter_records(parameters: Mapping[str, Mapping[str, Any]]) -> None:
    """Enforce the contractual invariants across the 31 parameter records."""
    require(set(parameters) == set(E05_PARAMETER_IDS), f"E05 parameter records must be exactly P01..P31 (count={len(parameters)})")
    for pid, rec in parameters.items():
        default = rec.get("documented_default_in_build_help")
        require(isinstance(default, str) and default.strip(), f"E05 parameter {pid} needs a documented_default_in_build_help string")
        require(
            isinstance(rec.get("applicability_justification"), str) and rec["applicability_justification"].strip(),
            f"E05 parameter {pid} needs a non-empty applicability_justification",
        )
        stage, state, value = rec.get("decision_stage"), rec.get("effective_value_state"), rec.get("effective_value")
        if stage == "G1_AFTER_CALIBRATION":
            require(
                state == STATE_PENDING and value is None,
                f"E05 parameter {pid} is G1_AFTER_CALIBRATION and must stay {STATE_PENDING} with no value "
                f"(state={state!r}, value={value!r})",
            )
        elif stage == "G1_RECORD_EXPLICITLY":
            require(
                state == STATE_RECORDED and value is None,
                f"E05 parameter {pid} is G1_RECORD_EXPLICITLY and must be recorded without a decided value",
            )
        elif stage == "EXCLUDED_BY_ARCHITECTURE":
            reason = rec.get("contractual_exclusion_reason")
            require(
                state == STATE_EXCLUDED and value == "OPTION_NOT_APPLIED" and rec.get("option_applied") is False
                and isinstance(reason, Mapping)
                and all(isinstance(reason.get(k), str) and reason[k].strip() for k in ("design_document_passage_verbatim", "matrix_failure_mode_verbatim", "matrix_notes_verbatim"))
                and rec.get("parameter", "\0") in reason["design_document_passage_verbatim"],
                f"E05 excluded parameter {pid} requires OPTION_NOT_APPLIED and a verbatim contractual exclusion reason",
            )
        elif pid in E05_COORDINATOR_DECISIONS:
            decision = rec.get("coordinator_decision")
            require(
                state == STATE_DECIDED and value is not None and isinstance(decision, Mapping)
                and decision.get("decided_by") == "IMPLEMENTATION_COORDINATOR" and decision.get("decision_section"),
                f"E05 parameter {pid} must record the Coordinator decision it applies, not a Programmer choice",
            )
        else:
            require(state in (STATE_FIXED, STATE_HYPOTHESIS) and value is not None, f"E05 parameter {pid} has an unexpected state {state!r}")


def build_e05_parameter_matrix_inspection(
    parameter_rows: Mapping[str, Mapping[str, str]],
    observed_tools: Mapping[str, Mapping[str, Any]],
    help_texts: Mapping[str, str],
    excluded_passage: str,
) -> dict[str, Any]:
    """Build the 31-parameter table from the matrix rows (verbatim) and the live build help."""
    parsed_help = {tool: parse_blast_help_flags(text) for tool, text in help_texts.items()}
    parameters: dict[str, dict[str, Any]] = {}
    for pid in E05_PARAMETER_IDS:
        row = parameter_rows[pid]
        stage, tool = row["decision_stage"], row["tool"]
        flags = E05_PARAMETER_FLAGS.get(pid, ())
        if stage in E05_STAGE_STATE:
            require(pid not in E05_EFFECTIVE_VALUES, f"{pid} must not have an assigned value at stage {stage}")
            state = E05_STAGE_STATE[stage]
            value = "OPTION_NOT_APPLIED" if state == STATE_EXCLUDED else None
        else:
            require(pid in E05_EFFECTIVE_VALUES, f"{pid} at stage {stage} needs an effective-value specification")
            state, value = E05_EFFECTIVE_VALUES[pid]
        if state == STATE_FIXED:
            require(str(value) == row["candidate_design_space"], f"{pid} value {value!r} differs from the matrix candidate_design_space")
        if pid == "P26":
            precedent = row["current_precedent"]
            require(
                [t for t in precedent.split() if t in E05_OUTFMT_6_PRECEDENT] == list(E05_OUTFMT_6_PRECEDENT),
                "P26 precedent specifiers differ from the matrix current_precedent",
            )
        if pid == "P31":
            value = row["candidate_design_space"]

        per_flag: dict[str, dict[str, Any]] = {}
        if not flags:
            documented = "NOT_DOCUMENTED_IN_BUILD_HELP"
        elif observed_tools.get(tool, {}).get("status") != "OBSERVED":
            documented = "NOT_APPLICABLE"
            per_flag = {f: {"documented_default_in_build_help": "NOT_APPLICABLE", "present_in_build_help": False} for f in flags}
        else:
            for flag in flags:
                per_flag[flag] = dict(parsed_help[tool].get(flag, {
                    "documented_default_in_build_help": "NOT_DOCUMENTED_IN_BUILD_HELP",
                    "flag": flag,
                    "present_in_build_help": False,
                }))
            defaults = [per_flag[f]["documented_default_in_build_help"] for f in flags]
            if len(flags) == 1:
                documented = defaults[0]
            elif all(d == "NOT_DOCUMENTED_IN_BUILD_HELP" for d in defaults):
                documented = "NOT_DOCUMENTED_IN_BUILD_HELP"
            else:
                documented = "PARTIAL_BY_FLAG: " + "; ".join(f"{f}={d}" for f, d in zip(flags, defaults, strict=True))

        record: dict[str, Any] = {
            "applicability_justification": (
                f"decision_stage {stage}, status {row['status']} in 08_b4_calibration_parameter_matrix_v2_1.tsv; "
                f"state {state}. Matrix text is copied verbatim below; the documented default is read from the build help."
            ),
            "biological_decision_role": row["biological_decision_role"],
            "calibration_question": row["calibration_question"],
            "candidate_design_space_in_matrix": row["candidate_design_space"],
            "current_precedent_in_matrix": row["current_precedent"],
            "database_size_relevance": row["database_size_relevance"],
            "decision_stage": stage,
            "determinism_relevance": row["determinism_relevance"],
            "documented_default_in_build_help": documented,
            "effective_value": value,
            "effective_value_state": state,
            "failure_mode": row["failure_mode"],
            "matrix_notes": row["notes"],
            "option_applied": False if stage == "EXCLUDED_BY_ARCHITECTURE" else None,
            "parameter": row["parameter"],
            "parameter_id": pid,
            "parameter_role": row["parameter_role"],
            "per_flag_build_help": per_flag,
            "status": row["status"],
            "tool": tool,
            "truncation_relevance": row["truncation_relevance"],
        }
        if stage == "EXCLUDED_BY_ARCHITECTURE":
            record["contractual_exclusion_reason"] = {
                "design_document": "05_B4_LOCAL_ALIGNMENT_CALIBRATION_DESIGN_v2_1_2.md section 7",
                "design_document_passage_verbatim": excluded_passage,
                "matrix_failure_mode_verbatim": row["failure_mode"],
                "matrix_notes_verbatim": row["notes"],
            }
        if pid in E05_COORDINATOR_DECISIONS:
            record["coordinator_decision"] = E05_COORDINATOR_DECISIONS[pid]
        if pid in ("P13", "P14"):
            record["reserved_decision_note"] = (
                "The PC13 versus QA-G tension is a reserved E02 decision (plan_v003.md section 6.6). It is not "
                "resolved here and no value is assigned."
            )
        if pid == "P02" and "-task" in per_flag:
            task_default = re.search(r"Default = `([^']+)'", documented)
            admitted = [t.strip() for t in row["candidate_design_space"].split(";")]
            record["task_default_observation"] = {
                "admitted_tasks_in_matrix": admitted,
                "documented_default_task": task_default.group(1) if task_default else None,
                "documented_default_task_is_admitted": bool(task_default and task_default.group(1) in admitted),
            }
        parameters[pid] = record

    validate_e05_parameter_records(parameters)
    counts: dict[str, dict[str, int]] = {"by_decision_stage": {}, "by_effective_value_state": {}}
    for rec in parameters.values():
        for key, field in (("by_decision_stage", "decision_stage"), ("by_effective_value_state", "effective_value_state")):
            counts[key][rec[field]] = counts[key].get(rec[field], 0) + 1

    outside: dict[str, dict[str, str]] = {}
    for tool in ("blastn", "makeblastdb"):
        if tool in parsed_help:
            covered = {f for pid, rec in parameters.items() if rec["tool"] == tool for f in E05_PARAMETER_FLAGS.get(pid, ())}
            outside[tool] = {
                flag: item["documented_default_in_build_help"]
                for flag, item in sorted(parsed_help[tool].items())
                if flag not in covered and flag not in E05_INFORMATIONAL_FLAGS
            }
    return {
        "build_help_flags_outside_matrix": {
            "observation_only": True,
            "statement": (
                "The matrix has 31 parameters. The flags below exist in the build help but are not matrix "
                "parameters; none is adopted. Enlarging the parameter set would be a normative change outside the "
                "scope of any agent."
            ),
            "flags_with_documented_default_by_tool": outside,
        },
        "counts": counts,
        "parameters": parameters,
        "parameters_without_documented_default": sorted(
            pid for pid, rec in parameters.items() if rec["documented_default_in_build_help"] == "NOT_DOCUMENTED_IN_BUILD_HELP"
        ),
        "total_parameters": len(parameters),
    }


def build_e05_qa_configuration_inspection(
    qa_rows: Mapping[str, Mapping[str, str]], output_integrity: Mapping[str, Any]
) -> dict[str, Any]:
    """Record, for the 19 QA criteria, the configuration preconditions inspected; no QA metric is computed."""
    criteria: dict[str, dict[str, Any]] = {}
    for qid in sorted(E05_QA_SPEC):
        inspected, deferred_to, note = E05_QA_SPEC[qid]
        row = qa_rows[qid]
        criteria[qid] = {
            "biological_decision_role": row["biological_decision_role"],
            "blocks_configuration_freeze": row["blocks_configuration_freeze"],
            "configuration_preconditions_inspected_in_e05_part1": inspected,
            "criterion": row["criterion"],
            "deferred_to": deferred_to,
            "expected_behavior": row["expected_behavior"],
            "failure_interpretation": row["failure_interpretation"],
            "fixture_dependency": row["fixture_dependency"],
            "matrix_initial_status": row["status"],
            "metric": row["metric"],
            "metric_computed_in_e05_part1": False,
            "precondition_note": note,
            "qa_id": qid,
            "state_after_e05_part1": "NOT_TESTED",
        }
    inspected_ids = [q for q, c in criteria.items() if c["configuration_preconditions_inspected_in_e05_part1"]]
    return {
        "criteria": criteria,
        "observed_in_this_unit": (
            "No QA metric of the campaign was evaluated in E05 Part 1 and no QA criterion was approved; all 19 "
            "criteria remain NOT_TESTED. For the criteria marked as preconditions inspected, only configuration "
            "preconditions were inspected."
        ),
        "qa_i_linked_output_integrity_status": output_integrity["qa_i_mechanism_status"],
        "scope_qualification": (
            "This record does not assert which QA metrics are computable without a search. Some metric components "
            "are structural (for example a set operation on declared identifier sets, or parser outcomes on supplied "
            "tables) and do not by definition need a search; they were not evaluated here. Evaluating the criteria for "
            "the campaign needs the campaign's fixtures and, for the recovery-type criteria, search results."
        ),
        "total_criteria": len(criteria),
        "preconditions_inspected_count": len(inspected_ids),
        "preconditions_inspected_ids": inspected_ids,
        "preconditions_not_inspected_count": len(criteria) - len(inspected_ids),
        "preconditions_not_inspected_ids": [q for q in criteria if q not in inspected_ids],
    }


def build_e05_design_decisions(parameter_rows: Mapping[str, Mapping[str, str]], qa_rows: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """Questions P30 and P23 with matrix evidence (verbatim) and the Coordinator decisions applied."""
    return {
        "P30": {
            "question": "Which deterministic record order (canonical_record_order_rule, plan_v003.md section 7) governs the FASTA before makeblastdb?",
            "evidence_matrix_candidate_design_space_verbatim": parameter_rows["P30"]["candidate_design_space"],
            "evidence_matrix_notes_verbatim": parameter_rows["P30"]["notes"],
            "decision": E05_COORDINATOR_DECISIONS["P30"],
        },
        "P23": {
            "question": "How are -dbsize and -searchsp specified in the primary candidates and in QA-F2, and when is production decided?",
            "evidence_matrix_candidate_design_space_verbatim": parameter_rows["P23"]["candidate_design_space"],
            "evidence_matrix_notes_verbatim": parameter_rows["P23"]["notes"],
            "evidence_qa_f2_expected_behavior_verbatim": qa_rows["QA-F2"]["expected_behavior"],
            "decision": E05_COORDINATOR_DECISIONS["P23"],
        },
    }


def build_e05_configuration_inspection(
    root: Path,
    corpus_directories: Mapping[str, Path],
    *,
    campaign_id: str = DEFAULT_GEOMETRY_CAMPAIGN_ID,
    expected_normative_sha256: Mapping[str, str] | None = None,
    expected_reference_sha256: Any = _DEFAULT,
    expected_run_manifest_sha256: Any = _DEFAULT,
    expected_resource_count: Any = _DEFAULT,
    expected_resource_ids: Sequence[str] | None = None,
    which_resolver: Callable[[str], str | None] = _default_tool_which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_e03_geometry: bool = True,
    expected_geometry_record_sha256: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute the E05 Part 1 read-only configuration inspection and assemble the deterministic record."""
    root = root.resolve()
    validate_geometry_campaign_id(campaign_id)
    normative = verify_and_read_e05_normative_inputs(
        root, corpus_directories, expected_normative_sha256=expected_normative_sha256
    )
    manifest, _, manifest_sha256 = verify_authoritative_cp1_manifest_for_e03(
        root,
        expected_reference_sha256=expected_reference_sha256,
        expected_run_manifest_sha256=expected_run_manifest_sha256,
        expected_resource_count=expected_resource_count,
        expected_resource_ids=expected_resource_ids,
    )
    section_a, section_b, help_texts = inspect_e05_tool_builds_and_help(
        root, manifest, campaign_id=campaign_id, which_resolver=which_resolver, runner=runner,
        require_e03_geometry=require_e03_geometry, expected_geometry_record_sha256=expected_geometry_record_sha256,
    )
    section_c = build_e05_parameter_matrix_inspection(
        normative["parameter_matrix_rows"], section_a["tools"], help_texts, normative["excluded_passage"]
    )
    section_d = inspect_e05_output_integrity_mechanism(section_a["tools"], help_texts)
    return {
        "schema_version": 1,
        "artifact_id": E05_INSPECTION_ARTIFACT_ID,
        "inspection_version": E05_INSPECTION_VERSION,
        "stage": "NB04_CP1_E05_PART_1_CONFIGURATION_INSPECTION",
        "scope_boundary": {
            "candidate_configurations_materialized": False,
            "candidate_payload_section_7_assembled": False,
            "candidate_sha256_ordering_or_aliases_computed": False,
            "information_from_recovery_used": False,
            "only_version_and_help_executed": True,
            "queries_executed": False,
            "reserved_decisions_untouched": True,
            "u04_target_path_occupied": False,
            "u04_target_path_reserved": E05_U04_RESERVED_PATH,
        },
        "authoritative_inputs_verified": {
            "cp1_manifest_path": MANIFEST,
            "cp1_manifest_sha256": manifest_sha256,
            "normative_corpus": normative["verification_summary"],
            "plan_v003_path": PLAN_V003_PATH,
            "plan_v003_sha256": PLAN_V003_SHA256,
        },
        "a_observed_tool_builds": section_a,
        "b_build_comparison_with_cp1_receipts_and_derivations": section_b,
        "c_parameter_matrix_inspection": section_c,
        "d_output_integrity_mechanism": section_d,
        "e_configuration_qa_matrix_status": build_e05_qa_configuration_inspection(normative["qa_matrix_rows"], section_d),
        "design_questions_decided_by_coordinator": build_e05_design_decisions(
            normative["parameter_matrix_rows"], normative["qa_matrix_rows"]
        ),
        "coordinator_instruction_corrections": E05_COORDINATOR_INSTRUCTION_CORRECTIONS,
        "simplification_s02_declaration": {
            "simplification_id": "S02",
            "statement": (
                "Plan_v003.md section 11 S02: three initial candidate bundles (blastn, blastn-short, dc-megablast). "
                "It reduces fine optimization and supports no claim of an optimal configuration. This inspection "
                "materializes no candidate."
            ),
        },
    }


def write_e05_configuration_inspection(
    root: Path, inspection_payload: Mapping[str, Any], *, destination: Path | None = None
) -> tuple[Path, str]:
    """Validate the payload and the destination before writing; never overwrite an existing file."""
    root = root.resolve()
    target = validate_e05_inspection_destination(root, destination)
    require(
        inspection_payload.get("artifact_id") == E05_INSPECTION_ARTIFACT_ID,
        f"unexpected artifact_id in E05 inspection payload: {inspection_payload.get('artifact_id')!r}",
    )
    section_c = inspection_payload.get("c_parameter_matrix_inspection", {})
    require(isinstance(section_c, Mapping) and "parameters" in section_c, "E05 inspection payload missing c_parameter_matrix_inspection.parameters")
    validate_e05_parameter_records(section_c["parameters"])
    payload = dict(inspection_payload)
    write_json(target, payload)
    return target, hashlib.sha256(json_bytes(payload)).hexdigest()

# Section 7 is a closed technical payload. Administrative links and provenance stay in its envelope.
E05_SECTION7_SEARCH_FIELDS = (
    "task", "word_size", "evalue_reporting_limit", "reward", "penalty", "gapopen", "gapextend", "dust",
    "soft_masking", "lcase_masking", "strand", "max_target_seqs", "max_hsps", "perc_identity", "qcov_hsp_perc",
    "culling_limit", "best_hit_overhang", "best_hit_score_edge", "subject_besthit", "xdrop_ungap", "xdrop_gap",
    "xdrop_gap_final", "window_size", "dbsize", "searchsp", "ungapped", "sum_stats", "num_threads",
)
E05_SECTION7_KEYS = {
    "tool_build": ("blastn", "makeblastdb", "blastdbcmd", "blast_formatter", "dustmasker"),
    "search_parameters": E05_SECTION7_SEARCH_FIELDS,
    "database_build": ("dbtype", "parse_seqids", "blastdb_version", "max_file_sz_effective", "volume_strategy", "taxid_policy"),
    "execution_architecture": (
        "strategy", "canonical_record_order_rule", "qa_sharding_rule", "qa_shard_count", "outfmt_fields",
        "authoritative_output_format", "parser_contract_id", "parser_implementation_sha256", "output_integrity_contract_id",
    ),
    "technical_domain": ("modality", "analysis_role", "resource_geometry_cells", "applicability_limitations"),
}
E05_SECTION7_TOOL_FIELDS = ("tool_name", "tool_version", "package_build", "executable_sha256")
E05_SECTION7_CELL_FIELDS = ("total_bases", "record_count", "descriptor_sha256", "database_volume_count")
E05_SECTION7_PARAMETER_PATHS = {
    pid: tuple(f"search_parameters.{flag[1:] if flag != '-evalue' else 'evalue_reporting_limit'}" for flag in flags)
    for pid, flags in E05_PARAMETER_FLAGS.items() if pid not in ("P26", "P28", "P29")
}
E05_SECTION7_PARAMETER_PATHS.update({
    "P01": ("technical_domain.modality",),
    "P26": ("execution_architecture.outfmt_fields", "execution_architecture.authoritative_output_format"),
    "P28": ("database_build.dbtype", "database_build.parse_seqids", "database_build.blastdb_version", "database_build.taxid_policy"),
    "P29": ("database_build.max_file_sz_effective", "database_build.volume_strategy", "technical_domain.resource_geometry_cells"),
    "P30": ("execution_architecture.canonical_record_order_rule",),
    "P31": ("execution_architecture.parser_contract_id", "execution_architecture.parser_implementation_sha256",
            "execution_architecture.output_integrity_contract_id"),
})
E05_U03_R3_PATH = f"{PRESERVATION_INVENTORY_DIR}/e05_configuration_inspection_r3.json"
E05_U03_R3_SHA256 = "5fc259de14b51829f60cdf3ee8f21f0c9212e28c0373fb45efea8c658f8dd843"
E05_SECTION7_TASKS = ("blastn", "blastn-short", "dc-megablast")
E05_SECTION7_CLOSURE_QUALIFICATION = {
    "closure_scope": "COMPUTATIONAL_PREDICATES_ON_SUPPLIED_DECLARATIONS",
    "authority_verification": "EXTERNAL_DOCUMENTARY_E02_E03_REQUIRED",
    "g1_certification": "NOT_EVALUATED",
}


def _section7_keys(value: Any, expected: Sequence[str], path: str) -> None:
    require(isinstance(value, Mapping), f"{path}: expected object")
    require(all(isinstance(key, str) for key in value), f"{path}: object keys must be strings")
    require(set(value) == set(expected), f"{path}: closed schema keys differ: missing={sorted(set(expected)-set(value))}, extra={sorted(set(value)-set(expected))}")


def _section7_unresolved(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        # Administrative sentinels retain their meaning when a component prefixes or suffixes the marker.
        return not value.strip() or re.search(
            r"(?:^|[^A-Z0-9])(?:TODO|TBD|UNKNOWN|PENDING|UNRESOLVED|RECORDED_NOT_DECIDED|"
            r"NOT_ESTABLISHED|NOT_DECLARED|NOT_MATERIALIZED|NOT_MEASURED|NOT_EVALUATED|NOT_APPLICABLE|NAO[ _]MEDIDO)(?:$|[^A-Z0-9])",
            value.upper(),
        ) is not None
    if isinstance(value, Mapping):
        return not value or any(_section7_unresolved(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return not value or any(_section7_unresolved(v) for v in value)
    return False


def validate_section7_payload(payload: Mapping[str, Any], *, allow_unresolved: bool = False) -> None:
    """Validate exact keys and value kinds. Open drafts may contain None, never metadata or extra keys."""
    _section7_keys(payload, ("schema_version", *E05_SECTION7_KEYS), "payload")
    require(type(payload["schema_version"]) is int and payload["schema_version"] == 1, "schema_version: expected 1")
    for section, keys in E05_SECTION7_KEYS.items():
        _section7_keys(payload[section], keys, section)

    def check(value: Any, kind: str, path: str) -> None:
        if allow_unresolved and value is None:
            return
        if kind != "prose":
            require(not _section7_unresolved(value), f"{path}: unresolved required value")
        if kind in ("integer", "positive_integer"):
            valid = type(value) is int and value >= (1 if kind == "positive_integer" else 0)
        elif kind == "number":
            valid = type(value) in (int, float) and float('-inf') < value < float('inf')
        elif kind == "boolean":
            valid = type(value) is bool
        elif kind == "sha256":
            valid = isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        elif kind == "token":
            valid = isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:#+ -]+", value) is not None
        else:
            valid = isinstance(value, str) and bool(value.strip())
        require(valid, f"{path}: invalid {kind}")

    for tool, entry in payload["tool_build"].items():
        if entry == "NOT_APPLICABLE":
            continue
        _section7_keys(entry, E05_SECTION7_TOOL_FIELDS, f"tool_build.{tool}")
        for field in E05_SECTION7_TOOL_FIELDS:
            check(entry[field], "sha256" if field == "executable_sha256" else "string", f"tool_build.{tool}.{field}")
        require(entry["tool_name"] == tool, f"tool_build.{tool}: tool_name differs")

    integer_fields = {"word_size", "reward", "penalty", "gapopen", "gapextend", "max_target_seqs", "max_hsps", "culling_limit", "window_size", "dbsize", "searchsp", "num_threads"}
    no_option_state = {"task", "word_size", "evalue_reporting_limit", "reward", "penalty", "gapopen", "gapextend", "max_target_seqs", "num_threads"}
    for field, value in payload["search_parameters"].items():
        path = f"search_parameters.{field}"
        if value == "OPTION_NOT_APPLIED":
            require(field not in no_option_state, f"{path}: omission would select an effective engine option")
            continue
        if field == "task":
            require(value in E05_SECTION7_TASKS or (allow_unresolved and value is None), f"{path}: task must be explicit and admitted")
        elif field in ("soft_masking", "lcase_masking", "subject_besthit", "ungapped", "sum_stats"):
            require(value in ("true", "false") or (allow_unresolved and value is None), f"{path}: expected explicit boolean flag value")
        elif field == "strand":
            require(value in ("both", "plus", "minus") or (allow_unresolved and value is None), f"{path}: invalid strand")
        elif field == "dust":
            require(value in ("yes", "no") or (isinstance(value, str) and re.fullmatch(r"\d+ \d+ \d+", value)) or (allow_unresolved and value is None), f"{path}: invalid DUST value")
        elif field == "penalty":
            require(type(value) is int or (allow_unresolved and value is None), f"{path}: invalid integer")
        else:
            check(value, "positive_integer" if field == "max_target_seqs" else "integer" if field in integer_fields else "number", path)

    db = payload["database_build"]
    for field in E05_SECTION7_KEYS["database_build"]:
        check(db[field], "boolean" if field == "parse_seqids" else "integer" if field in ("blastdb_version", "max_file_sz_effective") else "token", f"database_build.{field}")
    if db["taxid_policy"] is not None:
        require(db["taxid_policy"] in ("SOURCE_SPECIES_METADATA", "OMIT_FOR_SYNTHETIC_NO_TAXONOMIC_FILTER"), "database_build.taxid_policy: invalid policy")
    arch = payload["execution_architecture"]
    for field in E05_SECTION7_KEYS["execution_architecture"]:
        if field == "outfmt_fields":
            value = arch[field]
            require((allow_unresolved and value is None) or (isinstance(value, list) and bool(value) and all(isinstance(v, str) and re.fullmatch(r"[a-z0-9_]+", v) for v in value) and len(value) == len(set(value))), "execution_architecture.outfmt_fields: expected distinct native specifiers")
        else:
            check(arch[field], "integer" if field == "qa_shard_count" else "sha256" if field == "parser_implementation_sha256" else "token", f"execution_architecture.{field}")
    require(arch["qa_shard_count"] == 2 or (allow_unresolved and arch["qa_shard_count"] is None), "execution_architecture.qa_shard_count: section 7 requires 2")
    domain = payload["technical_domain"]
    check(domain["modality"], "token", "technical_domain.modality")
    check(domain["analysis_role"], "token", "technical_domain.analysis_role")
    for field in ("resource_geometry_cells", "applicability_limitations"):
        require(isinstance(domain[field], list) and bool(domain[field]), f"technical_domain.{field}: expected nonempty array")
    for index, cell in enumerate(domain["resource_geometry_cells"]):
        path = f"technical_domain.resource_geometry_cells[{index}]"
        _section7_keys(cell, E05_SECTION7_CELL_FIELDS, path)
        for field in E05_SECTION7_CELL_FIELDS:
            check(cell[field], "sha256" if field == "descriptor_sha256" else "positive_integer", f"{path}.{field}")
    for value in domain["applicability_limitations"]:
        check(value, "prose", "technical_domain.applicability_limitations")


def _section7_declared_values(
    pid: str, record: Mapping[str, Any], paths: Sequence[str],
) -> Mapping[str, Any] | None:
    """Normalize complete path maps or explicitly supported legacy representations."""
    value = record.get("effective_value")
    state = record.get("effective_value_state")
    if isinstance(value, Mapping) and set(value) == set(paths):
        return value
    if state == "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE":
        return None
    if pid == "P01" and state == STATE_FIXED and value == "blastn":
        return {"technical_domain.modality": "LOCAL_ALIGNMENT_CANONICAL"}
    if pid == "P23" and state == STATE_DECIDED and value == E05_P23_EFFECTIVE_VALUE:
        return {path: "OPTION_NOT_APPLIED" for path in paths}
    if len(paths) == 1 and not isinstance(value, Mapping):
        return {paths[0]: value}
    return None

def evaluate_section7_closure(
    payload: Mapping[str, Any], parameter_rows: Mapping[str, Mapping[str, str]],
    parameter_records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate computational consistency. Authority, preregistration and G1 require external documentary review."""
    require(set(parameter_rows) == set(E05_PARAMETER_IDS), "closure requires the complete parameter matrix")
    schema_errors: list[str] = []
    try:
        validate_section7_payload(payload, allow_unresolved=True)
    except ResourceContractError as exc:
        schema_errors.append(str(exc))

    def at(path: str) -> Any:
        value: Any = payload
        for part in path.split("."):
            value = value.get(part) if isinstance(value, Mapping) else None
        return value

    blockers = []
    for pid in E05_PARAMETER_IDS:
        record = parameter_records.get(pid, {})
        paths = E05_SECTION7_PARAMETER_PATHS[pid]
        unresolved = [path for path in paths if _section7_unresolved(at(path))]
        if pid == "P29":
            cells = at("technical_domain.resource_geometry_cells")
            if isinstance(cells, list) and any(not isinstance(cell, Mapping) or any(_section7_unresolved(cell.get(field)) for field in E05_SECTION7_CELL_FIELDS) for cell in cells):
                if "technical_domain.resource_geometry_cells" not in unresolved:
                    unresolved.append("technical_domain.resource_geometry_cells")
        state = record.get("effective_value_state")
        # A prospective, explicit candidate-design declaration can precede the empirical adoption decision.
        declared_states = {STATE_FIXED, STATE_EXCLUDED, STATE_DECIDED, "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE"}
        values = _section7_declared_values(pid, record, paths)
        try:
            mismatched = [path for path in paths if values is not None and json_bytes(values[path]) != json_bytes(at(path))]
        except (TypeError, ValueError):
            mismatched = list(paths)
        declaration_error = (
            "DECLARATION_STATE_UNRESOLVED_OR_UNSUPPORTED" if state not in declared_states else
            "DECLARATION_REPRESENTATION_INCOMPLETE_OR_UNSUPPORTED" if values is None else
            "DECLARATION_PAYLOAD_MISMATCH" if mismatched else None
        )
        if unresolved or declaration_error or record.get("effective_value") is None:
            row = parameter_rows[pid]
            blockers.append({"parameter_id": pid, "status": row["status"], "candidate_design_space": row["candidate_design_space"],
                             "unresolved_payload_fields": unresolved, "declaration_state": state,
                             "declaration_error": declaration_error, "declaration_mismatch_fields": mismatched})
    unresolved_fields: list[str] = []

    def walk(value: Any, path: str) -> None:
        if path.startswith("technical_domain.applicability_limitations[") and isinstance(value, str):
            if not value.strip():
                unresolved_fields.append(path)
            return
        if path in {f"tool_build.{tool}" for tool in E05_SECTION7_KEYS["tool_build"]} and value == "NOT_APPLICABLE":
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
            if not value:
                unresolved_fields.append(path)
        elif _section7_unresolved(value):
            unresolved_fields.append(path)
    walk(payload, "")
    for section, keys in E05_SECTION7_KEYS.items():
        value = payload.get(section, {}) if isinstance(payload, Mapping) else {}
        for field in keys:
            if not isinstance(value, Mapping) or field not in value:
                unresolved_fields.append(f"{section}.{field}")
    for tool in E05_SECTION7_KEYS["tool_build"]:
        entry = at(f"tool_build.{tool}")
        if entry != "NOT_APPLICABLE":
            for field in E05_SECTION7_TOOL_FIELDS:
                if not isinstance(entry, Mapping) or field not in entry:
                    unresolved_fields.append(f"tool_build.{tool}.{field}")
    cells = at("technical_domain.resource_geometry_cells")
    if isinstance(cells, list):
        for index, cell in enumerate(cells):
            for field in E05_SECTION7_CELL_FIELDS:
                if not isinstance(cell, Mapping) or field not in cell:
                    unresolved_fields.append(f"technical_domain.resource_geometry_cells[{index}].{field}")
    closed = not (blockers or unresolved_fields or schema_errors)
    if closed:
        validate_section7_payload(payload)
    return {"state": "CLOSED" if closed else "OPEN", "blocking_parameters": blockers,
            "unresolved_payload_fields": unresolved_fields, "schema_errors": schema_errors,
            "closure_dependency": "PRE_FREEZE_DOCUMENTARY_CANDIDATE_DESIGN_DECLARATION_E02_E03",
            **E05_SECTION7_CLOSURE_QUALIFICATION}


def evaluate_section7_candidate_set(
    candidates: Sequence[Mapping[str, Any]], parameter_rows: Mapping[str, Mapping[str, str]],
    *, design_space_declaration: str | None = None,
) -> dict[str, Any]:
    """Check each payload against its attached declarations. Completeness and authority are supplied externally."""
    closures = [evaluate_section7_closure(candidate["payload"], parameter_rows, candidate.get("parameter_records") or {}) for candidate in candidates]
    return {"state": "CLOSED" if candidates and design_space_declaration and design_space_declaration.strip() and all(c["state"] == "CLOSED" for c in closures) else "OPEN",
            "design_space_declaration": design_space_declaration, "candidate_closures": closures,
            **E05_SECTION7_CLOSURE_QUALIFICATION}


def section7_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    validate_section7_payload(payload)
    return json_bytes(payload)


def section7_payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(section7_payload_bytes(payload)).hexdigest()


def order_section7_payloads(
    payloads_by_alias: Mapping[str, Mapping[str, Any]], *,
    hash_function: Callable[[bytes], str] = lambda data: hashlib.sha256(data).hexdigest(),
) -> list[dict[str, Any]]:
    """Only resolved payloads enter identity ordering. Same hash with unequal bytes always blocks."""
    by_hash: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for alias, payload in payloads_by_alias.items():
        require(isinstance(alias, str) and bool(alias.strip()), "alias must be documented in the envelope")
        raw = section7_payload_bytes(payload)
        sha = hash_function(raw)
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha) is not None, "identity hash must be a full SHA256-shaped digest")
        if sha in by_hash:
            require(by_hash[sha][0] == raw, f"payload identity collision: hash equal with distinct bytes ({sha})")
            by_hash[sha][1]["aliases"].append(alias)
        else:
            by_hash[sha] = (raw, {"payload": json.loads(raw), "payload_sha256": sha, "aliases": [alias]})
    result = [by_hash[sha][1] for sha in sorted(by_hash)]
    for entry in result:
        entry["aliases"].sort()
    return result


def inspect_section7_database_volumes(
    root: Path, resource: Mapping[str, Any], *, executable: str = "blastdbcmd",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Enumerate index-volume triplets and cross-check read-only blastdbcmd -info metadata; never query."""
    prefix = relative_path(root, resource["database_prefix"])
    names_by_suffix = {
        suffix: {p.name[:-len(suffix)] for p in prefix.parent.glob(prefix.name + "*" + suffix) if p.is_file()}
        for suffix in (".nin", ".nhr", ".nsq")
    }
    volumes = names_by_suffix[".nin"]
    require(volumes and all(names == volumes for names in names_by_suffix.values()), "database volume components incomplete")
    require(all(re.fullmatch(re.escape(prefix.name) + r"(?:\.\d+)?", name) for name in volumes), "unexpected database volume basename")
    require(not (prefix.name in volumes and len(volumes) > 1), "mixed single and numbered volume basenames")
    command = [executable, "-db", str(prefix), "-dbtype", "nucl", "-info"]
    done = runner(command, capture_output=True, text=True, check=False, timeout=30)
    require(done.returncode == 0, f"blastdbcmd metadata failed: {done.stderr}")
    match = re.search(r"([\d,]+) sequences;\s*([\d,]+) total bases", done.stdout)
    version = re.search(r"BLASTDB Version:\s*(\d+)", done.stdout)
    require(match is not None and version is not None and "Volumes:" in done.stdout, "incomplete blastdbcmd metadata")
    metadata_volumes = [Path(line.strip()).name for line in done.stdout.split("Volumes:", 1)[1].splitlines() if line.strip()]
    require(len(metadata_volumes) == len(set(metadata_volumes)) and set(metadata_volumes) == volumes, "enumeration and blastdbcmd volume metadata differ")
    count, bases = (int(value.replace(",", "")) for value in match.groups())
    require(count == resource["quality"]["record_count"] and bases == resource["quality"]["total_bases"], "blastdbcmd resource scalars differ from authenticated geometry")
    return {"database_volume_count": len(volumes), "blastdb_version": int(version.group(1)),
            "method": "INDEX_VOLUME_TRIPLET_ENUMERATION_CROSS_CHECKED_WITH_BLASTDBCMD_INFO",
            "volume_basenames": sorted(volumes), "command": command, "metadata_stdout": done.stdout, "metadata_stderr": done.stderr}


def build_e05_section7_preparation(
    root: Path, corpus_directory: Path, *, accepted_geometry_record_sha256: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    which_resolver: Callable[[str], str | None] = _default_tool_which,
) -> dict[str, Any]:
    """Assemble open drafts from U03 and authenticated E03 records without reading or deriving FASTA geometry."""
    root = root.resolve()
    inspection_path = relative_path(root, E05_U03_R3_PATH)
    require(digest(inspection_path) == E05_U03_R3_SHA256, "U03 r3 inspection identity differs")
    inspection = json.loads(inspection_path.read_text("utf-8"))
    manifest_path = relative_path(root, MANIFEST)
    require(digest(manifest_path) == REAL_CP1_MANIFEST_SHA256, "authoritative CP1 manifest identity differs")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    matrix_path = corpus_directory / "08_b4_calibration_parameter_matrix_v2_1.tsv"
    require(digest(matrix_path) == E05_NORMATIVE_DOCUMENTS_SHA256[matrix_path.name], "parameter matrix identity differs")
    rows = _read_matrix_tsv(matrix_path.read_text("utf-8"), E05_PARAMETER_MATRIX_HEADER, matrix_path.name, "parameter_id")
    parameters = inspection["c_parameter_matrix_inspection"]["parameters"]
    validate_e05_parameter_records(parameters)
    require(set(rows) == set(E05_PARAMETER_IDS), "complete matrix is required")
    for pid, row in rows.items():
        require(parameters[pid]["status"] == row["status"] and parameters[pid]["candidate_design_space_in_matrix"] == row["candidate_design_space"], f"{pid}: U03 and matrix differ")
    tools = {name: {field: inspection["a_observed_tool_builds"]["tools"][name][field] for field in E05_SECTION7_TOOL_FIELDS}
             for name in E05_SECTION7_KEYS["tool_build"]}
    executable = which_resolver("blastdbcmd")
    require(executable is not None and digest(Path(executable)) == tools["blastdbcmd"]["executable_sha256"], "blastdbcmd executable differs from U03")
    for resource in manifest["resources"]:
        require(digest(relative_path(root, resource["identifier_map_path"])) == resource["quality"]["identifier_map_sha256"], "identifier map identity differs")
    derivations = _e05_geometry_derivations(root, manifest, DEFAULT_GEOMETRY_CAMPAIGN_ID, True, accepted_geometry_record_sha256)
    receipts, volume_evidence, cells = {}, {}, []
    db_options = []
    for resource in sorted(manifest["resources"], key=lambda r: r["resource_id"]):
        rid = resource["resource_id"]
        receipt_path = relative_path(root, resource["fasta_path"]).with_name("database_build.json")
        rel = receipt_path.relative_to(root).as_posix()
        require(digest(receipt_path) == resource["artifacts_sha256"][rel], "database receipt identity differs")
        receipt = json.loads(receipt_path.read_text("utf-8"))
        command = receipt["command"]
        def option(flag: str) -> str:
            require(command.count(flag) == 1 and command.index(flag) + 1 < len(command), f"receipt requires explicit {flag}")
            return command[command.index(flag) + 1]
        size = _receipt_max_file_size(receipt)
        require(not size["max_file_sz_flag_passed_in_recorded_command"] and size["stdout_reported_maximum_file_size_bytes"] is not None, "historical default max_file_sz provenance differs")
        require("-parse_seqids" in command and "-taxid" in command, "historical identifier or source-taxid policy differs")
        require(option("-taxid") == str(resource["taxid"]), "receipt taxid differs from source species metadata")
        probe = inspect_section7_database_volumes(root, resource, executable=executable, runner=runner)
        require(probe["blastdb_version"] == int(option("-blastdb_version")), "database version and receipt differ")
        for filename, expected in receipt["index_sha256"].items():
            require(digest(relative_path(root, resource["database_prefix"]).parent / filename) == expected, "database index identity differs")
        receipts[rid] = {**size, "max_file_sz_origin": "ENGINE_DEFAULT_REPORTED_IN_RECEIPT_STDOUT",
                         "source_taxid": resource["taxid"], "receipt_sha256": digest(receipt_path)}
        volume_evidence[rid] = probe
        db_options.append((option("-dbtype"), True, probe["blastdb_version"], size["stdout_reported_maximum_file_size_bytes"]))
        geometry = derivations[rid]
        cells.append({"total_bases": geometry["total_bases"], "record_count": geometry["canonical_record_order_check"]["ordered_record_id_count"],
                      "descriptor_sha256": geometry["descriptor_sha256"], "database_volume_count": probe["database_volume_count"]})
    require(len(set(db_options)) == 1, "historical database build options differ across resources")
    dbtype, parse_seqids, version, historical_size = db_options[0]
    require(digest(relative_path(root, PLAN_V003_PATH)) == PLAN_V003_SHA256, "plan identity differs")
    plan_text = relative_path(root, PLAN_V003_PATH).read_text("utf-8")
    # Copy exact applicability paragraphs from the approved plan.
    limitations = []
    for start in ("O descritor delimita arquitetura", "Registrar ENVELOPE_GEOMETRY_ONLY", "Magnitude aritmética de escala", "Simplificação S05", "OBSERVATION. Os seis database_build.json", "E01 e E05 compararão", "O caminho de código de fixtures", "A arquitetura preferida é um banco"):
        matches = [p for p in plan_text.split("\n\n") if p.startswith(start)]
        require(len(matches) == 1, f"required limitation paragraph missing: {start}")
        limitations.append(matches[0])
    database_build = {"dbtype": dbtype, "parse_seqids": parse_seqids, "blastdb_version": version,
                      "max_file_sz_effective": historical_size, "volume_strategy": "ENGINE_MANAGED_VOLUMES",
                      "taxid_policy": "SOURCE_SPECIES_METADATA"}
    parser_identity = nb04_parser_implementation_identity(root)
    qa_path = corpus_directory / "09_b4_calibration_qa_matrix_v2.tsv"
    require(digest(qa_path) == E05_NORMATIVE_DOCUMENTS_SHA256[qa_path.name], "QA matrix identity differs")
    qa_i = _read_matrix_tsv(qa_path.read_text("utf-8"), E05_QA_MATRIX_HEADER, qa_path.name, "qa_id")["QA-I"]
    architecture = {"strategy": "INTEGRAL_REFERENCE_CALIBRATION", "canonical_record_order_rule": parameters["P30"]["effective_value"],
                    "qa_sharding_rule": "TWO_SHARDS_CANONICAL_ORDER_GREEDY_LEAST_CURRENT_BASE_SUM_WHOLE_RECORDS_TIES_FIRST", "qa_shard_count": 2,
                    "outfmt_fields": list(inspection["d_output_integrity_mechanism"]["adopted_tabular_specifiers"]),
                    "authoritative_output_format": "11", "parser_contract_id": None, "parser_implementation_sha256": parser_identity["parser_implementation_sha256"],
                    "output_integrity_contract_id": None}
    domain = {"modality": "LOCAL_ALIGNMENT_CANONICAL", "analysis_role": "CALIBRATION",
              "resource_geometry_cells": sorted(cells, key=json_bytes), "applicability_limitations": limitations}
    sections = {"tool_build": tools, "database_build": database_build, "execution_architecture": architecture, "technical_domain": domain}
    search = dict.fromkeys(E05_SECTION7_SEARCH_FIELDS)
    for pid in ("P09", "P11", "P12", "P15", "P16", "P17", "P18", "P19", "P20", "P24"):
        field = E05_SECTION7_PARAMETER_PATHS[pid][0].split(".")[1]
        search[field] = parameters[pid]["effective_value"]
    search["dbsize"] = search["searchsp"] = "OPTION_NOT_APPLIED"
    skeletons = []
    for task in E05_SECTION7_TASKS:
        payload = json.loads(json_bytes({"schema_version": 1, **sections, "search_parameters": search}))
        payload["search_parameters"]["task"] = task
        # The observed historical default is evidence, while P29's future candidate design remains undeclared.
        payload["database_build"]["max_file_sz_effective"] = None
        payload["database_build"]["taxid_policy"] = "OMIT_FOR_SYNTHETIC_NO_TAXONOMIC_FILTER"
        candidate_records = {pid: {"effective_value_state": record["effective_value_state"], "effective_value": record["effective_value"]}
                             for pid, record in parameters.items()}
        for pid in ("P26", "P28"):
            values = {}
            for path in E05_SECTION7_PARAMETER_PATHS[pid]:
                section, field = path.split(".")
                values[path] = payload[section][field]
            candidate_records[pid] = {"effective_value_state": "CANDIDATE_DESIGN_DECLARED_PRE_FREEZE", "effective_value": values}
        validate_section7_payload(payload, allow_unresolved=True)
        skeletons.append({"task": task, "task_flag_explicit": True, "payload": payload, "parameter_records": candidate_records,
                          "closure": evaluate_section7_closure(payload, rows, candidate_records)})
    return {"state": "OPEN", "design_space_complete": False, **E05_SECTION7_CLOSURE_QUALIFICATION,
            "determinate_sections": sections, "candidate_skeletons": skeletons,
            "candidate_set_closure": evaluate_section7_candidate_set(skeletons, rows),
            "provenance": {"parser_implementation": parser_identity, "u03_inspection_sha256": E05_U03_R3_SHA256, "historical_database_build": receipts,
                           "volume_evidence": volume_evidence, "geometry_derivations": derivations,
                           "geometry_cell_resource_links": [{"resource_id": r["resource_id"], "descriptor_sha256": derivations[r["resource_id"]]["descriptor_sha256"]} for r in manifest["resources"]],
                           "production_partition_plan": "POST_CALIBRATION_RESOURCE_SCOPED"},
            "qa_i_parser_precondition": build_u05_parser_precondition(qa_i),
            "prospective_dependencies": {"candidate_design": "PRE_FREEZE_DOCUMENTARY_DECLARATIONS_E02_E03",
                "producer_lexical_format": "APPLICABLE_PINNED_BUILD_FORMAT_EVIDENCE_BEFORE_CAMPAIGN_USE",
                "parser_contract_id": "NORMATIVE_BINDING_NOT_ESTABLISHED",
                "output_integrity_contract_id": "NORMATIVE_BINDING_NOT_ESTABLISHED",
                "derived_fields_E04_E06": ["low_complexity_overlap_fraction", "match_strand", "subject_coordinate_system", "transcript_strand", "guide_pairing_interpretation", "covered_nt", "best_local_identity", "longest_exact_match_in_reported_hsps", "n_hsps", "n_subject_records", "n_resolved_loci"],
                "output_integrity_conditions": inspection["d_output_integrity_mechanism"]["export_path_default_cap_observation"]["conditions_to_verify"]}}

# Strict nucleotide HSP parsing is software preparation. Its execution witness and QA fixtures are external inputs.
from decimal import Decimal, InvalidOperation

U05_PARSER_SOURCE_PATHS = ("src/zeaguard/nb04_calibration.py", "src/zeaguard/nb04_resources.py")
U05_HSP_FIELDS = E05_OUTFMT_6_PRECEDENT + E05_OUTFMT_6_ADDITIONS


def parse_nb04_btop(btop: str) -> tuple[int | str, ...]:
    """Consume all BTOP tokens. Counts are canonical ASCII integers, including a literal zero run."""
    require(isinstance(btop, str) and bool(btop), "BTOP must be a nonempty string")
    tokens: list[int | str] = []
    position = 0
    while position < len(btop):
        match = re.compile(r"[0-9]+|[ACGTRYSWKMBDHVN-]{2}").match(btop, position)
        require(match is not None, f"BTOP illegal character or incomplete pair at offset {position}")
        token = match.group()
        if token[0] in "0123456789":
            require(token == "0" or token[0] != "0", "BTOP count has a leading zero")
            tokens.append(int(token))
        else:
            require(token != "--", "BTOP double-gap pair")
            require(token[0] != token[1], "BTOP identical letters must be represented by an identity run")
            require(all(char in DNA or char == "-" for char in token), "BTOP pair outside nucleotide alphabet")
            tokens.append(token)
        position = match.end()
    return tuple(tokens)


def parse_nb04_hsp_table(table: bytes | str, *, expected_row_count: int | None = None) -> dict[str, Any]:
    """Parse the adopted native fields atomically. An external row-count witness checks boundary cuts only within its scope.

    Input uses ASCII and LF exclusively, including the last nonempty record terminator. Read files as bytes to retain
    newline anomalies. No blank or comment record is skipped. Decimal fields retain exact Decimal values.
    Numeric fields accept surrounding ASCII spaces only, preserving every original lexeme in raw_numeric_fields.
    A matching supplied count establishes count agreement, while execution integrity and witness authority remain external.
    """
    require(isinstance(table, (bytes, str)), "HSP table must be bytes or text")
    if isinstance(table, bytes):
        try:
            table = table.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ResourceContractError("HSP table contains a non-ASCII character") from exc
    require(all(char in "\t\n" or 32 <= ord(char) <= 126 for char in table), "HSP table contains an illegal control, CR or non-ASCII character")
    require(not table or table.endswith("\n"), "HSP table has no final LF terminator")
    require(expected_row_count is None or (type(expected_row_count) is int and expected_row_count >= 0), "expected_row_count must be a nonnegative integer witness")
    lines = table[:-1].split("\n") if table else []
    rows: list[dict[str, Any]] = []
    decimal_fields = {"pident", "evalue", "bitscore", "qcovs"}
    positive_fields = {"length", "qlen", "slen", "qstart", "qend", "sstart", "send"}
    for number, line in enumerate(lines, 1):
        cells = line.split("\t")
        require(len(cells) == len(U05_HSP_FIELDS), f"HSP line {number}: field count differs from the adopted schema")
        row: dict[str, Any] = {}
        raw_numeric_fields: dict[str, str] = {}
        for field, cell in zip(U05_HSP_FIELDS, cells, strict=True):
            if field not in ("qseqid", "sseqid", "sstrand", "btop"):
                raw_numeric_fields[field] = cell
                cell = cell.strip(" ")
            prefix = f"HSP line {number} field {field}"
            if field in ("qseqid", "sseqid"):
                require(bool(cell) and all(33 <= ord(char) <= 126 for char in cell), f"{prefix}: invalid identifier")
                value: Any = cell
            elif field == "sstrand":
                require(cell in ("plus", "minus"), f"{prefix}: invalid strand")
                value = cell
            elif field == "btop":
                btop_tokens = parse_nb04_btop(cell)
                value = cell
            elif field in decimal_fields:
                require(re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", cell) is not None, f"{prefix}: invalid unsigned decimal representation")
                try:
                    value = Decimal(cell)
                except InvalidOperation as exc:
                    raise ResourceContractError(f"{prefix}: decimal is not representable") from exc
                require(value.is_finite() and value >= 0, f"{prefix}: decimal must be finite and nonnegative")
                if field in ("pident", "qcovs"):
                    require(value <= 100, f"{prefix}: percentage exceeds 100")
            else:
                require(re.fullmatch(r"0|[1-9][0-9]*", cell) is not None, f"{prefix}: invalid unsigned integer representation")
                value = int(cell)
                require(value >= (1 if field in positive_fields else 0), f"{prefix}: invalid integer domain")
            row[field] = value
        require(1 <= row["qstart"] <= row["qlen"] and 1 <= row["qend"] <= row["qlen"], f"HSP line {number}: query coordinates outside qlen")
        require(1 <= row["sstart"] <= row["slen"] and 1 <= row["send"] <= row["slen"], f"HSP line {number}: subject coordinates outside slen")
        require((row["sstrand"] == "plus" and row["sstart"] <= row["send"]) or (row["sstrand"] == "minus" and row["sstart"] >= row["send"]), f"HSP line {number}: strand and subject coordinates disagree")
        columns = query_bases = subject_bases = mismatches = gaps = opens = 0
        previous_gap = None
        for token in btop_tokens:
            if isinstance(token, int):
                columns += token
                query_bases += token
                subject_bases += token
                if token:
                    previous_gap = None
            else:
                q, s = token
                columns += 1
                query_bases += q != "-"
                subject_bases += s != "-"
                side = "query" if q == "-" else "subject" if s == "-" else None
                gaps += side is not None
                mismatches += side is None
                opens += side is not None and side != previous_gap
                previous_gap = side
        require(columns == row["length"] and query_bases == abs(row["qend"] - row["qstart"]) + 1 and subject_bases == abs(row["send"] - row["sstart"]) + 1, f"HSP line {number}: BTOP length or coordinate span mismatch")
        require((mismatches, gaps, opens) == (row["mismatch"], row["gaps"], row["gapopen"]), f"HSP line {number}: BTOP replacement or gap counts disagree")
        row["raw_numeric_fields"] = raw_numeric_fields
        rows.append(row)
    require(expected_row_count is None or len(rows) == expected_row_count, "HSP table row count differs from the supplied execution witness")
    return {"rows": rows, "row_count": len(rows), "expected_row_count": expected_row_count,
            "producer_lexical_compatibility": "NOT_ESTABLISHED_FOR_PINNED_BUILD",
            "producer_format_dependency": "APPLICABLE_PINNED_BUILD_FORMAT_EVIDENCE_BEFORE_CAMPAIGN_USE",
            "numeric_lexical_policy": "SURROUNDING_ASCII_SPACES_ONLY_WITH_ORIGINAL_LEXEMES_PRESERVED",
            "completeness_state": "EXPECTED_ROW_COUNT_MATCHED" if expected_row_count is not None else "COMPLETENESS_WITNESS_REQUIRED",
            "line_boundary_truncation_checked": expected_row_count is not None,
            "execution_integrity_established": False,
            "completeness_dependency": "EXTERNAL_EXECUTION_EXPECTED_ROW_COUNT_AND_WITNESS_AUTHORITY",
            "completeness_limitations": "A count witness checks supplied row-count agreement only. Execution success, full output, query preservation and witness authority require the execution-level integrity contract."}


def nb04_parser_implementation_identity(root: Path) -> dict[str, Any]:
    """Coordinator scope decision: whole source files, LF-normalized, with the inventory serialized by json_bytes."""
    inventory = {path: digest(relative_path(root.resolve(), path), normalized=True) for path in U05_PARSER_SOURCE_PATHS}
    # ponytail: whole-file identity overcovers unrelated edits; upgrade to a declared narrower scope with dependency guards if post-freeze churn becomes a real constraint.
    return {"parser_implementation_sha256": hashlib.sha256(json_bytes(inventory)).hexdigest(),
            "implementation_sha256_lf": inventory,
            "scope": {"source_files": list(U05_PARSER_SOURCE_PATHS), "normalization": "CRLF_TO_LF",
                      "hash_input": "json_bytes of exactly the relative-path to LF-normalized SHA256 inventory",
                      "decision_authority": "IMPLEMENTATION_COORDINATOR", "decision_status": "SUBJECT_TO_SCIENTIFIC_REVIEW_REVISABLE_BEFORE_FREEZE",
                      "convention_scope": "NB03_PRECEDENTS_SUPPORT_THE_FAMILY_OF_WHOLE_FILE_LF_IDENTITIES_THE_EXACT_PAIR_AND_AGGREGATE_ARE_THE_COORDINATOR_DECISION",
                      "runtime_limitation": "Source identity does not certify the interpreter, standard library or execution environment and is not complete behavioral identity across runtimes.",
                      "prefreeze_dependency": "RECOMPUTE_IDENTITIES_FROM_FINAL_SOURCE_BEFORE_FREEZING_AND_ORDERING_CANDIDATES",
                      "convention_references": ["src/zeaguard/nb03_manual_review.py:399", "src/zeaguard/nb03_selection.py:496", "src/zeaguard/nb03_specificity.py:502"],
                      "overcoverage_limitation": "Any unrelated change in either whole file also changes parser identity and may require a new candidate. A narrower scope requires an explicit dependency guard and a new scope decision."}}


def build_u05_parser_precondition(qa_i_row: Mapping[str, str]) -> dict[str, Any]:
    """Record software preparation without promoting the fixture-dependent campaign criterion."""
    require(qa_i_row.get("qa_id") == "QA-I" and qa_i_row.get("criterion") == "STABLE_PARSING", "expected the QA-I stable-parsing row")
    require(qa_i_row.get("biological_decision_role") == "false" and qa_i_row.get("blocks_configuration_freeze") == "YES", "QA-I role or freeze dependency differs")
    return {"qa_id": "QA-I", "state": "NOT_TESTED", "configuration_preconditions_inspected": True,
            "criterion": qa_i_row["criterion"], "metric": qa_i_row["metric"], "expected_behavior": qa_i_row["expected_behavior"],
            "fixture_dependency": qa_i_row["fixture_dependency"], "fixtures_materialized": False,
            "fixture_materialization_dependency": "E04_F01_F02_AND_CORRUPTED_VALID_OUTPUT_COPIES",
            "behavior_verification_scope": "SYNTHETIC_TABLE_SOFTWARE_TESTS_ONLY",
            "execution_completeness_dependency": "EXTERNAL_EXECUTION_EXPECTED_ROW_COUNT_AND_WITNESS_AUTHORITY",
            "campaign_qa_approved": False, "biological_decision_role": False, "blocks_configuration_freeze": True}

# U06: declarative reconstruction only. No command in this region is executed.
U06_EXCLUDED_PARAMETERS = frozenset(('P15', 'P16', 'P17', 'P18', 'P19', 'P20', 'P24'))
U06_COMMAND_LIMITATIONS = (
    'Declarative reconstruction only. No executable, database, query, archive or output is opened or executed.',
    'Closure checks computational consistency of supplied declarations. Documentary authority and E02/E03 decisions require external review.',
    'Only base candidates are supported. QA execution payloads and all overrides are refused.',
    'Supported route: explicit archive format 11 and tabular export 6, named output paths, no stdout or positional operands.',
    'Only the measured header and default forms are supported. Unknown forms are refused.',
    'Export tool-build binding is not established: the lateral record has no tool_build carrier. No carrier or contract identifier is invented.',
    'Help metadata and executable provenance are supplied assertions. Runtime/build equivalence and producer interoperability are not certified.',
    'QA-M requires an actually executed and logged command after the authorized freeze. QA-I remains NOT_TESTED.',
    'The specific parser and output-integrity contract bindings remain prospective dependencies. Export reconstruction does not establish completeness or absence of truncation.',
)


def _u06_text(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 or ord(c) == 127 for c in value),
            f'{label}: expected declared text without control characters')
    return value


def _u06_envelope(envelope: Mapping[str, Any], tool: str, paths: Sequence[str], keys: Sequence[str]) -> list[str]:
    require(isinstance(envelope, Mapping), 'command envelope must be an object')
    for key in ('overrides', 'execution_payload', 'parent_candidate_hash', 'qa_case_id'):
        require(key not in envelope, f'{key}: execution overrides are unsupported for base reconstruction, including max_target_seqs')
    _section7_keys(envelope, ('executable', 'paths', *keys), 'command envelope')
    executable = _u06_text(envelope['executable'], 'executable')
    require(executable.replace('\\', '/').split('/')[-1] in (tool, tool + '.exe'), f'executable must select {tool}')
    _section7_keys(envelope['paths'], paths, 'envelope.paths')
    for flag in paths:
        path = _u06_text(envelope['paths'][flag], f'envelope.paths.{flag}')
        require(not path.startswith('-'), f'envelope.paths.{flag}: option-like path must be qualified explicitly')
    return [executable]


def _u06_flag_domain(flag: str, value: Any, help_flags: Mapping[str, Any], *, path_operand: bool = False) -> bool:
    """Check the finite header forms measured for this route, including named paths."""
    from decimal import Decimal
    header = help_flags.get(flag, {}).get('header_line')
    require(isinstance(header, str), f'{flag}: absent from supplied build help')
    if path_operand:
        require(re.match(re.escape(flag) + r' <(?:String|File_In|File_Out)(?:>|, )', header) is not None, f'{flag}: path flag requires one string/file operand')
    if header == flag:
        require(type(value) is bool or value in ('true', 'false'), f'{flag}: invalid presence-only flag value')
        return True
    numeric = re.fullmatch(re.escape(flag) + r' <(Integer|Int8|Real)(?:, (.*))?>', header)
    if numeric:
        kind, restriction = numeric.groups()
        require(type(value) in ((int, float) if kind == 'Real' else (int,)), f'{flag}: invalid {kind} value')
        number = Decimal(str(value))
        require(number.is_finite(), f'{flag}: nonfinite numeric value')
        if restriction:
            bound = re.fullmatch(r'(>=|<=)(-?[0-9]+)', restriction)
            interval = re.fullmatch(r'(-?[0-9]+)\.\.(-?[0-9]+)', restriction)
            open_interval = re.fullmatch(r'\(>([0-9]+(?:\.[0-9]+)?) and <([0-9]+(?:\.[0-9]+)?)\)', restriction)
            if bound:
                valid = number >= Decimal(bound[2]) if bound[1] == '>=' else number <= Decimal(bound[2])
            elif interval:
                valid = Decimal(interval[1]) <= number <= Decimal(interval[2])
            elif open_interval:
                valid = Decimal(open_interval[1]) < number < Decimal(open_interval[2])
            else:
                raise ResourceContractError(f'{flag}: unsupported header domain {header}')
            require(valid, f'{flag}: value outside documented header domain {header}')
        return False
    if header == f'{flag} <Boolean>':
        require(value in ('true', 'false'), f'{flag}: invalid Boolean value')
        return False
    _u06_text(value, f'{flag}.value')
    if header in (f'{flag} <String>', f'{flag} <File_In>', f'{flag} <File_Out>'):
        return False
    if header.startswith(f'{flag} <String, '):
        choices = re.findall(r"[`']([^`']+)'", header)
        require(bool(choices) and value in choices, f'{flag}: value outside documented string domain {header}')
        return False
    file_limit = re.fullmatch(re.escape(flag) + r' <File_Out, file name length < ([0-9]+)>', header)
    require(file_limit is not None, f'{flag}: unsupported header domain {header}')
    require(len(value) < int(file_limit[1]), f'{flag}: value outside documented header domain {header}')
    return False


def _u06_option(
    flag: str, value: Any, provenance: Mapping[str, Any], help_flags: Mapping[str, Any], *, task: str | None = None, path_operand: bool = False,
) -> list[str]:
    """One emission mechanism for both tools. Values never determine whether a flag was passed."""
    require(isinstance(provenance, Mapping), f'{flag}: missing provenance declaration')
    _section7_keys(provenance, ('option_applied', 'origin'), f'{flag}.provenance')
    applied, origin = provenance['option_applied'], provenance['origin']
    require(type(applied) is bool, f'{flag}: option_applied must be explicitly boolean')
    # Path operands are literal envelope text, never parameter-state declarations.
    if not path_operand and value == 'OPTION_NOT_APPLIED':
        require(not applied and origin in ('OPTION_NOT_APPLIED', 'NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET'),
                f'{flag}: OPTION_NOT_APPLIED cannot emit a token or use default provenance')
        require(origin != 'NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET' or flag in ('-dbsize', '-searchsp'),
                f'{flag}: natural-resource policy applies only to dbsize/searchsp')
        return []
    if origin == 'NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET':
        raise ResourceContractError(f'{flag}: natural-resource policy requires OPTION_NOT_APPLIED in the payload')
    require(path_operand or not _section7_unresolved(value), f'{flag}: unresolved value')
    switch = _u06_flag_domain(flag, value, help_flags, path_operand=path_operand)
    if applied:
        require(origin == 'EXPLICIT', f'{flag}: passed flag requires EXPLICIT provenance')
        if switch:
            require(value in ('true', True), f'{flag}: presence-only flag requires true')
            return [flag]
        return [flag, str(value)]
    if origin == 'OPTION_NOT_APPLIED':
        require(switch and value in ('false', False), f'{flag}: effective value cannot be omitted without documented-default provenance')
        return []
    require(origin == 'DOCUMENTED_ENGINE_DEFAULT', f'{flag}: missing explicit origin for omitted effective value')
    default = help_flags[flag].get('documented_default_in_build_help', '')
    match = re.fullmatch(r"Default = `([^']*)'", default)
    expected = match[1] if match else None
    # Only these observed conditional forms are supported. Unknown default prose fails closed.
    conditional = None
    if flag == '-evalue':
        conditional = re.fullmatch(r'Default = ([0-9]+) \(([0-9]+) for blastn-short\)', default)
    elif flag == '-dust':
        conditional = re.fullmatch(r"Default = '([^']+)' \('([^']+)' for blastn-short\)", default)
    if conditional:
        require(task in E05_SECTION7_TASKS, f'{flag}: admitted explicit task required for documented default')
        expected = conditional[2] if task == 'blastn-short' else conditional[1]
    require(expected is not None, f'{flag}: default is not documented in a supported form in supplied build help')
    same = str(value) == expected
    if type(value) in (int, float):
        from decimal import Decimal, InvalidOperation
        try:
            same = Decimal(str(value)) == Decimal(expected)
        except InvalidOperation:
            same = False
    require(same, f'{flag}: declared effective value differs from documented default for task {task}')
    return []


def _u06_incompatibilities(passed_flags: Sequence[str], help_flags: Mapping[str, Any]) -> None:
    # Only the measured "Incompatible with" clauses contribute pairs, never descriptive prose.
    passed = set(passed_flags)
    for flag in sorted(passed):
        constraints = help_flags[flag].get('constraints') or ''
        for clause in re.findall(r'\* Incompatible with:\s*([^*]+)', constraints):
            conflicts = {'-' + name.strip() for name in clause.split(',')}
            require(not (conflicts & passed), f'{flag}: incompatible passed flags {sorted(conflicts & passed)}')


def _u06_command_result(argv: list[str], stage: str, provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {'stage': stage, 'argv': argv, 'flag_provenance': dict(provenance),
            'argument_order': 'PARAMETER_ID_P01_TO_P31_THEN_DECLARED_PATH_ORDER' if stage == 'SEARCH' else 'OUTFMT_THEN_EXPORT_CAP_ORDER_THEN_DECLARED_PATH_ORDER',
            'order_decision_authority': 'IMPLEMENTATION_COORDINATOR_REVISABLE_BEFORE_FREEZE',
            'execution_performed': False, 'campaign_qa_approved': False,
            'qa_m': {'qa_id': 'QA-M', 'state': 'NOT_TESTED', 'reason': 'ACTUAL_EXECUTION_AND_LOG_COMPARISON_PROHIBITED_BEFORE_AUTHORIZED_FREEZE'},
            'limitations': list(U06_COMMAND_LIMITATIONS)}


def reconstruct_section7_search_command(
    payload: Mapping[str, Any], parameter_rows: Mapping[str, Mapping[str, str]],
    parameter_records: Mapping[str, Mapping[str, Any]], envelope: Mapping[str, Any], *, help_text: str,
) -> dict[str, Any]:
    """Reconstruct base blastn argv from closed values plus declared origins/paths, without execution."""
    closure = evaluate_section7_closure(payload, parameter_rows, parameter_records)
    require(closure['state'] == 'CLOSED', f"search payload OPEN: blocking_parameters={closure['blocking_parameters']}; schema_errors={closure['schema_errors']}; unresolved={closure['unresolved_payload_fields']}")
    tool = payload['tool_build']['blastn']
    require(isinstance(tool, Mapping) and tool.get('tool_name') == 'blastn', 'tool_build.blastn: selected tool must be applicable with complete identity')
    argv = _u06_envelope(envelope, 'blastn', ('-db', '-query', '-out'), ('flag_provenance',))
    help_flags = parse_blast_help_flags(help_text)
    flags = [flag for pid in E05_PARAMETER_IDS if pid not in ('P28', 'P29') for flag in E05_PARAMETER_FLAGS.get(pid, ())]
    provenance = envelope['flag_provenance']
    _section7_keys(provenance, flags, 'flag_provenance')
    for flag in flags:
        _section7_keys(provenance[flag], ('option_applied', 'origin'), f'{flag}.provenance')
    for pid in E05_PARAMETER_IDS:
        if pid in ('P01', 'P28', 'P29', 'P30', 'P31'):
            continue
        for index, flag in enumerate(E05_PARAMETER_FLAGS[pid]):
            path = E05_SECTION7_PARAMETER_PATHS[pid][index] if pid != 'P26' else 'execution_architecture.authoritative_output_format'
            section, field = path.split('.')
            value = payload[section][field]
            if pid in U06_EXCLUDED_PARAMETERS:
                require(value == 'OPTION_NOT_APPLIED', f'{pid} {flag}: excluded by architecture, effective value forbidden')
            if pid == 'P02':
                require(provenance[flag].get('option_applied') is True and provenance[flag].get('origin') == 'EXPLICIT', 'P02 -task must be explicit')
            if pid == 'P23':
                require(value == 'OPTION_NOT_APPLIED' and provenance[flag].get('origin') == 'NATURAL_RESOURCE_SEARCH_SPACE_NOT_SET',
                        f'P23 {flag}: base candidate requires natural-resource search space, flag not passed')
            if pid == 'P26':
                require(value == '11' and provenance[flag].get('option_applied') is True, 'P26: authoritative archive format 11 must be passed explicitly')
            argv.extend(_u06_option(flag, value, provenance[flag], help_flags, task=payload['search_parameters']['task']))
    for flag in ('-db', '-query', '-out'):
        argv.extend(_u06_option(flag, envelope['paths'][flag], {'option_applied': True, 'origin': 'EXPLICIT'}, help_flags, path_operand=True))
    _u06_incompatibilities([flag for flag, declaration in provenance.items() if declaration['option_applied']], help_flags)
    return _u06_command_result(argv, 'SEARCH', provenance)


def reconstruct_blast_formatter_command(record: Mapping[str, Any], *, help_text: str) -> dict[str, Any]:
    """Side-envelope export declarations. Search-stage caps are never reused implicitly."""
    argv = _u06_envelope(record, 'blast_formatter', ('-archive', '-out'), ('options',))
    flags = ('-outfmt', *E05_EXPORT_PATH_CAP_FLAGS)
    _section7_keys(record['options'], flags, 'export.options')
    help_flags = parse_blast_help_flags(help_text)
    provenance = {}
    for flag in flags:
        option = record['options'][flag]
        _section7_keys(option, ('value', 'option_applied', 'origin'), f'export.options.{flag}')
        value = option['value']
        provenance[flag] = {key: option[key] for key in ('option_applied', 'origin')}
        if flag == '-outfmt':
            require(isinstance(value, str) and value.startswith('6 ') and option['option_applied'] is True,
                    'export -outfmt: explicit tabular format and native field list required')
            fields = value.split(' ')[1:]
            require(fields == list(E05_OUTFMT_6_PRECEDENT + E05_OUTFMT_6_ADDITIONS), 'export -outfmt: adopted native field order differs')
        argv.extend(_u06_option(flag, value, provenance[flag], help_flags))
    for flag in ('-archive', '-out'):
        argv.extend(_u06_option(flag, record['paths'][flag], {'option_applied': True, 'origin': 'EXPLICIT'}, help_flags, path_operand=True))
    _u06_incompatibilities([flag for flag, declaration in provenance.items() if declaration['option_applied']], help_flags)
    return _u06_command_result(argv, 'EXPORT', provenance)


def compare_qa_m_argv(reconstructed_argv: Sequence[str], logged_argv: Sequence[str], *, help_text: str) -> dict[str, Any]:
    """Compare supplied argv only. Supplied logs do not establish execution or campaign QA approval."""
    help_flags = parse_blast_help_flags(help_text)

    def normalize(argv: Sequence[str]) -> dict[str, Any]:
        require(isinstance(argv, (list, tuple)) and bool(argv), 'argv must be a nonempty token sequence')
        for token in argv:
            _u06_text(token, 'argv token')
        flags = {}
        index = 1
        while index < len(argv):
            token = argv[index]
            if token in help_flags:
                require(token not in flags, f'{token}: duplicate flag is ambiguous')
                header = help_flags[token]['header_line']
                if header == token:
                    flags[token] = None
                    index += 1
                else:
                    require(index + 1 < len(argv) and argv[index + 1] not in help_flags, f'{token}: missing value')
                    require(re.fullmatch(r'-[A-Za-z_].*|--.*', argv[index + 1]) is None, f'{token}: option-like value is ambiguous')
                    flags[token] = argv[index + 1]
                    index += 2
            else:
                require(re.fullmatch(r'-[A-Za-z_].*|--.*', token) is None, f'{token}: unknown option in supplied help')
                raise ResourceContractError(f'{token}: unexpected positional argument, only named options are supported')
        return {'executable': argv[0], 'flags': dict(sorted(flags.items())), 'positional': []}

    left, right = normalize(reconstructed_argv), normalize(logged_argv)
    differences = []
    for flag in sorted(set(left['flags']) | set(right['flags'])):
        if flag not in left['flags'] or flag not in right['flags'] or left['flags'][flag] != right['flags'][flag]:
            differences.append({'flag': flag, 'reconstructed_present': flag in left['flags'], 'logged_present': flag in right['flags'],
                                'reconstructed_value': left['flags'].get(flag), 'logged_value': right['flags'].get(flag)})
    return {'qa_id': 'QA-M', 'state': 'NOT_TESTED', 'correspondence': left == right,
            'reason': 'ACTUAL_EXECUTION_AND_LOG_COMPARISON_PROHIBITED_BEFORE_AUTHORIZED_FREEZE',
            'execution_performed': False, 'campaign_qa_approved': False,
            'normalization': {'executable': 'EXACT_TOKEN_NO_PATH_RESOLUTION', 'flags': 'SET_OF_FLAG_VALUE_PAIRS_USING_SUPPLIED_HELP_ARITY',
                              'positional': 'REJECTED_NO_POSITIONAL_ARGUMENTS_SUPPORTED', 'token_order': 'IGNORED', 'values': 'EXACT_TEXT_NO_NUMERIC_OR_PATH_NORMALIZATION',
                              'duplicate_flags': 'REJECTED_AS_AMBIGUOUS', 'decision_authority': 'IMPLEMENTATION_COORDINATOR_REVISABLE_BEFORE_FREEZE'},
            'normalized_reconstructed': left, 'normalized_logged': right, 'flag_differences': differences,
            'executable_differs': left['executable'] != right['executable'],
            'positional_differences': {'only_reconstructed': sorted(set(left['positional']) - set(right['positional'])),
                                       'only_logged': sorted(set(right['positional']) - set(left['positional']))},
            'limitations': list(U06_COMMAND_LIMITATIONS)}

# U07 evaluates declarations only. This region has no freeze writer or executor.
E07_COMPONENTS = (
    'cross_references', 'hashes', 'roles', 'parameters', 'tolerance_fields', 'qa',
    'scale_decisions', 'authorization', 'precedence', 'finite_input_inventory',
    'availability_regimes', 'freeze_commit', 'snapshot', 'verified_transport', 'allow_dirty',
)
E07_DECLARED_ORDER = (
    'G0', 'APPROVED_METHOD_AND_DESIGN', 'MATERIALIZED_FIXTURES_AND_CANDIDATES',
    'NUMERIC_TOLERANCES', 'PREFREEZE', 'FREEZE_COMMIT', 'MATCHING_SNAPSHOT',
    'VERIFIED_TRANSPORT', 'FIRST_INFORMATIVE_COMMAND',
)
E07_PRECEDENCE_EDGES = (
    ('G0', 'MATERIALIZED_FIXTURES_AND_CANDIDATES'),
    ('APPROVED_METHOD_AND_DESIGN', 'MATERIALIZED_FIXTURES_AND_CANDIDATES'),
    ('MATERIALIZED_FIXTURES_AND_CANDIDATES', 'NUMERIC_TOLERANCES'),
    ('NUMERIC_TOLERANCES', 'PREFREEZE'), ('PREFREEZE', 'FREEZE_COMMIT'),
    ('FREEZE_COMMIT', 'MATCHING_SNAPSHOT'), ('FREEZE_COMMIT', 'VERIFIED_TRANSPORT'),
    ('MATCHING_SNAPSHOT', 'FIRST_INFORMATIVE_COMMAND'),
    ('VERIFIED_TRANSPORT', 'FIRST_INFORMATIVE_COMMAND'),
)
E07_PENDING_DECISION_IDS = ('I01', 'I02', 'I03', 'I04', 'PC13', 'F07', 'B4-8', 'B4-9')
E07_DOCUMENTARY_INPUTS_SHA256 = '657861b2007251b0fe0ec53aa6b0b8f3099c8d4cbdeab523063dc786f1af34bb'
E07_UNRESOLVED_DEPENDENCIES = {
    'preparation_record_carriers_not_established': PREPARATION_REFERENCE_ARTIFACT_PATHS[1:],
    'database_file_coverage': 'COMPLETE_DATABASE_FILE_LIST_WITH_CATALOG_LINK_NOT_ESTABLISHED',
    'tolerance_representation': 'REQUIRED_INTERNAL_KEYS_NOT_ESTABLISHED',
    'tolerance_applicability': 'APPLICABLE_INSTANCES_WITHOUT_TOLERANCE_REGISTER_NOT_ESTABLISHED',
}
E07_LIMITATIONS = (
    'Local declaration schema only. Component digests bind json_bytes of declarations, not a normative artifact or freeze identity.',
    'Matching supplied hashes, references and receipts does not verify actual files, transport, snapshot, authorization or chronology.',
    'Declared order is checked without a clock. Documentary authority and scientific justification require external review.',
    'QA fidelity uses original_table_records from the hash-pinned, versioned data/reference/nb04_cp0_documentary_inputs.json. Missing or different sources remain blocked. Only literal documentary equality is checked, without interpreting or applying QA-G or any criterion. QA-M and QA-I remain NOT_TESTED and no QA result is approved.',
    'The five preparation records named in unresolved_dependencies have no supported supplied carrier here. This evaluator does not infer their existence from other declarations. The real-state inspection reports their actual absence.',
    'The complete database file list and its catalog link are not established. Declared -query coverage is checked literally; -db is a prefix whose full file coverage remains blocked without that catalog. -out is a future destination, never required as an input.',
    'Tolerance declared contents are checked for internal absence, without inventing mandatory internal keys. Required representation and applicable instances remain unresolved without the tolerance register and catalog; tolerance_fields remains blocked. Empty arrays can explicitly declare no differences or gaps. Prose is not scanned for pending-state words.',
    'No freeze, UTC, freeze identifier, version, closed receipt, snapshot, transport or informative command is produced.',
    'Complete declarations do not satisfy E07, B4, G1 or any gate. Informative execution remains blocked.',
    'Scientific adequacy of supplied tolerance justifications, applicability and documentary dispositions is not established by matching declarations.',
)


def _e07_declaration_sha256(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _e07_relative_input_path(value: Any) -> str:
    path = _u06_text(value, 'inventory path')
    require(not path.startswith('/') and '\\' not in path and ':' not in path and all(p not in ('', '.', '..') for p in path.split('/')), 'inventory path must be contained and relative')
    require(path.startswith(('src/', 'scripts/', 'tests/', 'docs/implementation/', 'config/', 'data/reference/', 'data/external/nto/', 'results/bioinformatics/nb04/', 'artifacts/')), 'inventory path outside preparation directories')
    return path


def _e07_declared_content(value: Any, location: str) -> None:
    """Require content for declared JSON members, without prescribing scientific keys."""
    require(value is not None, f'{location}: declared structured value absent')
    if isinstance(value, Mapping):
        require(bool(value), f'{location}: declared object empty')
        for key, item in value.items():
            require(isinstance(key, str) and key.strip(), f'{location}: empty or invalid member name')
            _e07_declared_content(item, f'{location}.{key}')
    elif isinstance(value, list):
        # Empty arrays explicitly declare zero items, including zero differences/gaps.
        for index, item in enumerate(value):
            _e07_declared_content(item, f'{location}[{index}]')
    elif isinstance(value, str):
        require(bool(value.strip()), f'{location}: declared text empty')
    else:
        require(type(value) in (bool, int, float), f'{location}: unsupported declared content')
        if type(value) is float:
            require(-float('inf') < value < float('inf'), f'{location}: nonfinite declared number')


def evaluate_e07_preconditions(envelope: Mapping[str, Any], *, documentary_inputs_path: Path | None = None) -> dict[str, Any]:
    """Check declarations against an explicitly supplied, hash-pinned QA source. Never authorize or freeze."""
    qa_source = {'document': 'data/reference/nb04_cp0_documentary_inputs.json',
                 'table': '09_b4_calibration_qa_matrix_v2.tsv',
                 'expected_sha256': E07_DOCUMENTARY_INPUTS_SHA256,
                 'verification': 'NOT_VERIFIED'}
    envelope_errors = []
    if not isinstance(envelope, Mapping):
        envelope_errors.append('envelope must be an object')
        envelope = {}
    try:
        _section7_keys(envelope, E07_COMPONENTS, 'e07_envelope')
    except ResourceContractError as exc:
        envelope_errors.append(str(exc))
    blockers = []
    parameter_blockers = []
    unresolved_decisions = []
    hashes = envelope.get('hashes')
    bindings = hashes.get('components', {}) if isinstance(hashes, Mapping) else {}
    refs = envelope.get('cross_references')
    refs = refs if isinstance(refs, Mapping) else {}
    inventory = envelope.get('finite_input_inventory')
    inventory = inventory if isinstance(inventory, list) else []
    entries = {e['path']: e for e in inventory if isinstance(e, Mapping) and isinstance(e.get('path'), str)}
    candidate_hashes = []
    roles = envelope.get('roles')
    roles = roles if isinstance(roles, Mapping) else {}
    all_fixture_ids = [f for values in roles.values() if isinstance(values, list) for f in values]

    for component in E07_COMPONENTS:
        try:
            require(component in envelope and envelope[component] is not None, 'required declaration missing')
            value = envelope[component]
            if component != 'hashes':
                require(isinstance(bindings, Mapping) and component in bindings, 'component hash binding missing')
                require(bindings[component] == _e07_declaration_sha256(value), 'component altered against declared hash binding')
            if component == 'cross_references':
                _section7_keys(value, ('required_paths', 'fixture_ids', 'candidate_payload_sha256s', 'applicable_tolerances'), component)
                require(isinstance(value['required_paths'], list) and value['required_paths'] and len(value['required_paths']) == len(set(value['required_paths'])), 'required paths must be finite and distinct')
                require(set(value['required_paths']) == set(entries), 'required paths and finite inventory differ')
                require(set(value['fixture_ids']) == set(all_fixture_ids), 'fixture references and roles differ')
                require(value['candidate_payload_sha256s'], 'candidate references missing')
                require(isinstance(value['applicable_tolerances'], list) and value['applicable_tolerances'], 'tolerance applicability declarations missing')
                require(all(len(row) == 3 and row[0] in all_fixture_ids and row[2] in value['candidate_payload_sha256s'] for row in value['applicable_tolerances']), 'tolerance applicability references differ')
            elif component == 'hashes':
                _section7_keys(value, ('components', 'files'), component)
                require(isinstance(bindings, Mapping) and set(bindings) == set(E07_COMPONENTS) - {'hashes'}, 'complete component hash bindings required, without self-hash')
                require(all(isinstance(h, str) and re.fullmatch(r'[0-9a-f]{64}', h) for h in bindings.values()), 'invalid component SHA256')
                require(value['files'] == {p: e.get('sha256') for p, e in entries.items()} and bool(entries), 'declared file hashes and inventory differ')
                require(all(bindings[c] == _e07_declaration_sha256(envelope.get(c)) for c in bindings), 'component hash binding mismatch')
            elif component == 'roles':
                _section7_keys(value, ('TUNING', 'VALIDATION'), component)
                require(all(isinstance(v, list) and v and all(isinstance(f, str) and f.strip() for f in v) for v in value.values()), 'explicit nonempty roles required')
                require(len(all_fixture_ids) == len(set(all_fixture_ids)), 'fixture roles overlap or repeat')
            elif component == 'parameters':
                require(isinstance(value, Mapping) and isinstance(value.get('candidates'), list) and value['candidates'], 'candidate declarations missing')
                require(isinstance(value.get('parameter_rows'), Mapping) and all(isinstance(row, Mapping) for row in value['parameter_rows'].values()), 'parameter matrix declarations missing')
                require(all(isinstance(c, Mapping) and isinstance(c.get('payload'), Mapping) and isinstance(c.get('parameter_records'), Mapping) and all(isinstance(r, Mapping) for r in c['parameter_records'].values()) for c in value['candidates']), 'candidate records malformed')
                closures = [evaluate_section7_closure(c['payload'], value['parameter_rows'], c.get('parameter_records', {})) for c in value['candidates']]
                parameter_blockers.extend(b for closure in closures for b in closure['blocking_parameters'])
                require(all(c['state'] == 'CLOSED' for c in closures), 'section 7 closure refused: ' + repr(sorted({b['parameter_id'] for b in parameter_blockers})))
                require(isinstance(value.get('design_space_declaration'), str) and value['design_space_declaration'].strip(), 'finite design-space declaration missing')
                for candidate in value['candidates']:
                    reconstruct_section7_search_command(candidate['payload'], value['parameter_rows'], candidate['parameter_records'], candidate['command_envelope'], help_text=candidate['help_text'])
                    candidate_hashes.append(section7_payload_sha256(candidate['payload']))
                require(candidate_hashes == refs.get('candidate_payload_sha256s'), 'candidate payload references differ')
            elif component == 'tolerance_fields':
                require(isinstance(value, list) and value, 'tolerance declarations missing')
                required = ('fixture_id', 'candidate_payload_sha256', 'instance_id', 'pattern', 'expected_coordinates', 'orientation', 'comparison_object', 'fragmentation_rule', 'unit', 'applicable_endpoints', 'numeric_by_endpoint', 'independent_justification')
                for record in value:
                    require(isinstance(record, Mapping) and all(k in record and record[k] is not None for k in required), 'mandatory tolerance fields missing')
                    require(all(isinstance(record[k], str) and record[k].strip() for k in ('instance_id', 'comparison_object', 'fragmentation_rule')), 'required tolerance descriptors empty or invalid')
                    require(all(isinstance(record[k], Mapping) and record[k] for k in ('pattern', 'expected_coordinates')), 'required pattern or coordinate declaration empty')
                    for field in ('pattern', 'expected_coordinates'):
                        _e07_declared_content(record[field], f'tolerance.{record["instance_id"]}.{field}')
                    require(record['orientation'] in ('PLUS', 'MINUS'), 'tolerance orientation missing or invalid')
                    require(record['fixture_id'] in all_fixture_ids and record['candidate_payload_sha256'] in refs.get('candidate_payload_sha256s', []), 'tolerance references differ')
                    require(record['unit'] == 'nt' and isinstance(record['independent_justification'], str) and record['independent_justification'].strip(), 'unit or independent justification missing')
                    numbers = record['numeric_by_endpoint']
                    require(isinstance(numbers, Mapping) and numbers and set(numbers) == set(record['applicable_endpoints']) and set(numbers) <= {'qstart', 'qend', 'sstart', 'send'}, 'declared endpoint fields missing or unsupported')
                    require(all(type(n) in (int, float) and 0 <= n < float('inf') for n in numbers.values()), 'unresolved or invalid numerical tolerance')
                declared = [(r['fixture_id'], r['instance_id'], r['candidate_payload_sha256']) for r in value]
                require(len(declared) == len(set(declared)) and set(declared) == {tuple(row) for row in refs.get('applicable_tolerances', [])}, 'tolerance coverage of declared applicable instances incomplete')
                # ponytail: keep this domain closed until E04/E06 supply the declared carriers.
                # Upgrade by checking their identified representation and applicability, without guessing keys.
                require(False, 'tolerance representation and applicability unresolved: data/reference/nb04_calibration_tolerances.json and data/reference/nb04_calibration_fixture_catalog.json have no established carrier')
            elif component == 'qa':
                require(isinstance(value, Mapping) and set(value) == set(E05_QA_SPEC), 'complete QA criteria declarations required')
                require(documentary_inputs_path is not None, 'QA normative source not identified: versioned documentary inputs path required')
                documentary_bytes = Path(documentary_inputs_path).read_bytes()
                require(hashlib.sha256(documentary_bytes).hexdigest() == qa_source['expected_sha256'], 'QA documentary carrier RAW identity differs')
                source_rows = json.loads(documentary_bytes)['original_table_records'][qa_source['table']]
                require(isinstance(source_rows, list) and all(isinstance(row, Mapping) for row in source_rows), 'QA source table malformed')
                matrix = {row['qa_id']: row for row in source_rows}
                require(len(source_rows) == len(matrix) and set(matrix) == set(E05_QA_SPEC), 'QA source criteria incomplete or repeated')
                qa_source['verification'] = 'PINNED_RAW_SHA256_AND_CONTENT_READ'
                normative_fields = ('criterion', 'metric', 'expected_behavior', 'fixture_dependency',
                                    'failure_interpretation', 'biological_decision_role', 'blocks_configuration_freeze')
                for qid, record in value.items():
                    require(isinstance(record, Mapping) and record.get('qa_id') == qid and all(isinstance(record.get(k), str) and record[k].strip() for k in ('criterion', 'metric', 'expected_behavior', 'fixture_dependency')), f'{qid}: criterion declaration incomplete')
                    for field in normative_fields:
                        require(record.get(field) == matrix[qid][field], f'{qid}.{field}: declaration differs from pinned QA matrix')
                    status_fields = [key for key in ('status', 'state_after_e05_part1', 'matrix_initial_status') if key in record]
                    require(status_fields and all(record[key] == 'NOT_TESTED' for key in status_fields), f'{qid}: this preparation evaluates declarations only, never QA outcomes')
            elif component == 'scale_decisions':
                require(isinstance(value, Mapping), 'scale/decision declarations missing')
                unresolved_decisions.extend(d for d in E07_PENDING_DECISION_IDS if not isinstance(value.get(d), Mapping) or value[d].get('state') != 'DECLARED' or value[d].get('reference') not in refs.get('required_paths', []) or not isinstance(value[d].get('disposition'), str) or not value[d]['disposition'].strip())
                require(not unresolved_decisions, 'documentary dispositions unresolved: ' + repr(unresolved_decisions))
            elif component == 'authorization':
                require(isinstance(value, Mapping) and value.get('reference') in refs.get('required_paths', []) and isinstance(value.get('authorized_stages'), list) and 'E08' in value['authorized_stages'], 'explicit transition authorization declaration missing')
            elif component == 'precedence':
                require(isinstance(value, list) and len(value) == len(E07_DECLARED_ORDER) and set(value) == set(E07_DECLARED_ORDER), 'declared phase events missing or repeated')
                positions = {event: index for index, event in enumerate(value)}
                require(all(positions[before] < positions[after] for before, after in E07_PRECEDENCE_EDGES), 'declared phase order inconsistent with required precedence')
            elif component == 'finite_input_inventory':
                require(inventory and len(entries) == len(inventory), 'finite file inventory missing or paths repeated')
                for entry in inventory:
                    _e07_relative_input_path(entry['path'])
                    require(isinstance(entry.get('role'), str) and entry['role'].strip(), 'file role missing')
                    require(type(entry.get('size_bytes')) is int and entry['size_bytes'] >= 0, 'file size missing or invalid')
                    require(isinstance(entry.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', entry['sha256']), 'file RAW SHA256 missing or invalid')
                    require(entry.get('regime') in ('TRACKED_COMMIT_BLOB', 'VERIFIED_BYTE_COPY'), 'availability regime missing or unsupported')
                    ignored_roots = phase_git_and_snapshot_policy()['file_classification']['ignored_unversioned_campaign_outputs']
                    ignored = entry['path'].startswith(tuple(path + '/' for path in [*ignored_roots, 'artifacts']))
                    require(entry['regime'] == ('VERIFIED_BYTE_COPY' if ignored else 'TRACKED_COMMIT_BLOB'), 'availability regime conflicts with declared phase file classification')
                    if entry['regime'] == 'TRACKED_COMMIT_BLOB':
                        require(entry.get('commit') == envelope.get('freeze_commit'), 'tracked commit reference differs')
                parameters = envelope.get('parameters')
                require(isinstance(parameters, Mapping) and isinstance(parameters.get('candidates'), list) and parameters['candidates'], 'command input dependencies unavailable')
                database_prefixes = []
                for candidate in parameters['candidates']:
                    command = candidate.get('command_envelope') if isinstance(candidate, Mapping) else None
                    require(isinstance(command, Mapping) and isinstance(command.get('paths'), Mapping), 'command input paths unavailable')
                    paths = command['paths']
                    query = _e07_relative_input_path(paths.get('-query'))
                    database_prefixes.append(_e07_relative_input_path(paths.get('-db')))
                    require(query in entries, f'required command input -query not enumerated: {query}')
                require(False, 'complete database file coverage unresolved for -db ' + repr(database_prefixes) + ': catalog-linked file list unavailable in data/reference/nb04_calibration_fixture_catalog.json; no index extensions inferred')
            elif component == 'availability_regimes':
                require(bool(entries) and value == {p: e.get('regime') for p, e in entries.items()}, 'per-file availability regimes differ from inventory')
            elif component == 'freeze_commit':
                require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value), 'freeze commit declaration missing or malformed')
            elif component == 'snapshot':
                require(isinstance(value, Mapping) and value.get('commit') == envelope.get('freeze_commit'), 'snapshot does not correspond to declared commit')
                _e07_relative_input_path(value.get('path'))
                require(isinstance(value.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', value['sha256']), 'snapshot SHA256 missing')
            elif component == 'verified_transport':
                snapshot = envelope.get('snapshot')
                require(isinstance(value, Mapping) and isinstance(snapshot, Mapping) and value.get('commit') == envelope.get('freeze_commit') and value.get('snapshot_sha256') == snapshot.get('sha256'), 'transport commit/snapshot references differ')
                require(value.get('independent_copies') is True and value.get('hardlinks') is False and value.get('alternates') is False, 'independent verified copies must be declared without hardlinks or alternates')
                require(json_bytes(value.get('files')) == json_bytes({p: {'sha256': e.get('sha256'), 'size_bytes': e.get('size_bytes')} for p, e in entries.items()}) and bool(entries), 'transport file declarations differ from finite inventory')
            elif component == 'allow_dirty':
                require(value is False, 'transition requires explicitly declared allow_dirty=false')
        except (ResourceContractError, KeyError, TypeError, ValueError, OSError, UnicodeError) as exc:
            blockers.append({'component': component, 'reason': str(exc)})
    if not isinstance(envelope.get('scale_decisions'), Mapping):
        unresolved_decisions = list(E07_PENDING_DECISION_IDS)
    return {'state': 'PRECONDICOES_DECLARADAS_COMPLETAS' if not blockers and not envelope_errors else 'RECUSADO',
            'blocking_components': blockers, 'envelope_errors': envelope_errors,
            'blocking_parameters': parameter_blockers, 'unresolved_decision_ids': unresolved_decisions,
            'freeze_produced': False, 'informative_command_allowed': False, 'authority_verified': False,
            **E05_SECTION7_CLOSURE_QUALIFICATION, 'qa_source': qa_source,
            'unresolved_dependencies': {k: list(v) if isinstance(v, tuple) else v for k, v in E07_UNRESOLVED_DEPENDENCIES.items()},
            'limitations': list(E07_LIMITATIONS)}


def inspect_e07_declared_state(root: Path, preservation_inventory_path: str, accepted_preservation_sha256: str) -> dict[str, Any]:
    """Read preserved declarations only. Never materialize missing preconditions or probe a database."""
    root = root.resolve()
    require(digest(relative_path(root, preservation_inventory_path)) == accepted_preservation_sha256, 'preservation inventory identity differs')
    preservation = json.loads(relative_path(root, preservation_inventory_path).read_text('utf-8'))
    require(digest(relative_path(root, E05_U03_R3_PATH)) == E05_U03_R3_SHA256, 'U03 r3 identity differs')
    inspection = json.loads(relative_path(root, E05_U03_R3_PATH).read_text('utf-8'))
    certificate = verify_g0(root)
    documentary = json.loads(relative_path(root, 'data/reference/nb04_cp0_documentary_inputs.json').read_text('utf-8'))
    rows = {r['parameter_id']: r for r in documentary['original_table_records']['08_b4_calibration_parameter_matrix_v2_1.tsv']}
    records = inspection['c_parameter_matrix_inspection']['parameters']
    geometry = inspection['b_build_comparison_with_cp1_receipts_and_derivations']['current_e03_geometry_derivations']
    for record in geometry.values():
        require(digest(relative_path(root, record['geometry_record_path'])) == record['geometry_record_sha256'], 'accepted geometry identity differs')
    parser_identity = nb04_parser_implementation_identity(root)
    tools = {tool: {field: inspection['a_observed_tool_builds']['tools'][tool][field] for field in E05_SECTION7_TOOL_FIELDS} for tool in E05_SECTION7_KEYS['tool_build']}
    # This diagnostic view is partial. It never fills undetermined parameters or creates candidate identity.
    partial = {'schema_version': 1, 'tool_build': tools, 'search_parameters': dict.fromkeys(E05_SECTION7_SEARCH_FIELDS)}
    for pid, paths in E05_SECTION7_PARAMETER_PATHS.items():
        values = _section7_declared_values(pid, records[pid], paths)
        if values is not None:
            for path, value in values.items():
                section, field = path.split('.')
                partial.setdefault(section, {})[field] = value
    partial.setdefault('execution_architecture', {})['parser_implementation_sha256'] = parser_identity['parser_implementation_sha256']
    candidates = []
    for task in E05_SECTION7_TASKS:
        payload = json.loads(json_bytes(partial))
        payload['search_parameters']['task'] = task
        candidates.append({'payload': payload, 'parameter_records': records, 'command_envelope': None, 'help_text': None})
    envelope = dict.fromkeys(E07_COMPONENTS)
    envelope['parameters'] = {'parameter_rows': rows, 'candidates': candidates, 'design_space_declaration': None}
    envelope['qa'] = inspection['e_configuration_qa_matrix_status']['criteria']
    envelope['hashes'] = {'components': {key: _e07_declaration_sha256(envelope[key]) for key in E07_COMPONENTS if key != 'hashes'}, 'files': {}}
    result = evaluate_e07_preconditions(envelope, documentary_inputs_path=relative_path(root, 'data/reference/nb04_cp0_documentary_inputs.json'))
    result['preserved_source_evidence'] = {
        'preservation_inventory': {'path': preservation_inventory_path, 'sha256': accepted_preservation_sha256, 'stage': preservation['stage']},
        'geometry_records': {rid: {'path': r['geometry_record_path'], 'sha256': r['geometry_record_sha256']} for rid, r in geometry.items()},
        'u03_inspection': {'path': E05_U03_R3_PATH, 'sha256': E05_U03_R3_SHA256},
        'g0_read_only_verification': certificate['status'], 'parser_implementation_sha256': parser_identity['parser_implementation_sha256'],
        'pending_calibration_parameter_ids': [pid for pid in E05_PARAMETER_IDS if records[pid]['effective_value_state'] == STATE_PENDING],
        'missing_preparation_artifacts': [path for path in PREPARATION_REFERENCE_ARTIFACT_PATHS if not relative_path(root, path).is_file()],
    }
    result['limitations'].append('Real-state evaluation uses a partial U03 declaration view, not a newly materialized candidate or complete section 7 payload. Missing preparation artifacts remain absent. No CP1 normalized FASTA, index or archive is read. verify_g0 hashes its certified inputs read-only.')
    return result


# U08 checks supplied catalog declarations only. It contains no generator or executor.
E04_CATALOG_DESIGN_DECLARATIONS = (
    'length_vector_rule', 'balancing_regime', 'PC04', 'PC05', 'PC07', 'PC08A', 'PC08B',
    'PC09', 'PC10', 'PC11', 'PC12', 'PC13', 'PC14', 'PC15', 'F07', 'B4-8', 'B4-9',
    'I01', 'I02', 'I03', 'I04',
)
E04_CATALOG_LIMITATIONS = (
    'Local declaration format for pure software verification, not a normative artifact or a materialized fixture catalog.',
    'Declaration consistency does not verify documentary authority, scientific adequacy, actual FASTA/index files or an actual database inspection. No QA is evaluated or approved.',
    'Numerically specified construction checks cover PC01, PC02, PC03 and PC06. Other classes remain pending even if a generic specification is supplied.',
    'Coordinates describe supplied complete planted objects, not recovered HSPs. Recovery, extension tolerances, incidental matches and statistical independence are not established.',
    'The recipe literal and declared generation keys are checked without generating bases. The integer seed is required but its derivation is not regenerated.',
    'BLAST file-list completeness and applicability are not established by supplied index-file declarations. This verifier does not remove any U07 barrier or supply its missing carriers.',
    'This local format does not verify table 18 multiplicity declarations, including PC01 unit multiplicity across F01 through F07. DECLARATIONS_CONSISTENT does not attest conformity to those rows.',
    'RAW comparisons for src/zeaguard/nb04_calibration.py and tests/test_nb04_calibration.py and module prefixes 179161, 221104, 239075 and 266347 bytes must use Git blobs or LF-normalized content, never Windows checkout bytes. The line-ending exposure remains escalated. No attribute, configuration or certificate is changed.',
    'QA-M and QA-I remain NOT_TESTED. No materialization, execution, freeze, B4 or G1 authorization is produced.',
)


def _e04_expected_coordinates(installation: Mapping[str, Any], record_length: int) -> None:
    """Validate the declared projection of the complete planted object, without HSP recovery."""
    length = installation['length']
    require(type(length) is int and type(record_length) is int and 0 < length <= record_length, 'installation length does not fit its record')
    start = (record_length - length) // 2 + 1
    end = start + length - 1
    require(installation['planted_interval'] == [start, end] and all(type(n) is int for n in installation['planted_interval']), 'planted_interval differs from the centered 1-based inclusive formula')
    orientation = installation['orientation']
    require(orientation in ('PLUS', 'MINUS'), 'computational orientation missing or invalid')
    coordinates = installation['coordinates']
    require(isinstance(coordinates, Mapping), 'distinct coordinate declaration required')
    emitted = coordinates['emitted']
    _section7_keys(emitted, ('qstart', 'qend', 'sstart', 'send'), 'declared coordinate projection')
    require(all(type(v) is int for v in emitted.values()), 'coordinate values must be integers')
    require(coordinates.get('coordinate_system') == 'ONE_BASED_INCLUSIVE', 'coordinate origin/system differs')
    expected_subject = [start, end] if orientation == 'PLUS' else [end, start]
    require([emitted['qstart'], emitted['qend']] == [1, length], 'query projection endpoints differ from complete planted object')
    require([emitted['sstart'], emitted['send']] == expected_subject, 'subject projection/orientation does not remap exactly to planted interval')
    require(coordinates['ascending_subject_interval'] == sorted(expected_subject) and all(type(n) is int for n in coordinates['ascending_subject_interval']), 'ascending subject interval is inconsistent or not distinct')


def _e04_construction(installation: Mapping[str, Any], record: Mapping[str, Any]) -> None:
    """Compare supplied bases and complete difference arrays with the specified construction."""
    case, length = installation['class'], installation['length']
    require(case in ('PC01', 'PC02', 'PC03', 'PC06'), f'PENDING_CLASS_SPECIFICATION:{case}')
    require(installation['expected_detection_class'] == ('MUST_BE_REPORTED' if case in ('PC01', 'PC02') else 'CHARACTERIZED_NOT_ASSERTED'), f'{case}: declared detection class differs from contract')
    query = _u06_text(installation['query_sequence'], 'query_sequence')
    require(len(query) == length and set(query) <= set('ACGT'), 'query length/alphabet differs')
    start = (len(record['sequence']) - length) // 2
    target = record['sequence'][start:start + length]
    if installation['orientation'] == 'MINUS':
        target = target.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
    differences = [position for position, (left, right) in enumerate(zip(query, target), 1) if left != right]
    require(installation['gaps'] == [], 'specified ungapped construction cannot contain gaps')
    if case == 'PC01':
        expected = []
    else:
        require(installation['orientation'] == 'PLUS', f'{case}: closure construction requires PLUS')
        fixture = installation['fixture_id']
        if case == 'PC02':
            require(fixture in ('F01', 'F02'), 'PC02 fixture not specified')
            require(length == (200 if fixture == 'F01' else 400), 'PC02 length differs from closure')
            require(len(record['sequence']) == (2500 if fixture == 'F01' else 2000), 'PC02 subject record length differs from closure')
            expected = [length // 2]
        else:
            require(fixture in ('F02', 'F04', 'F05'), f'{case}: fixture not specified')
            require(len(record['sequence']) == {'F02': 2000, 'F04': 15000000, 'F05': 230000000}[fixture], 'subject record length differs from closure')
            if case == 'PC03':
                require(length == 400, 'PC03 length must be 400')
                first, last, divisor = 151, 250, 4
            else:
                require(length in (800, 1600), 'PC06 length must be 800 or 1600')
                first = (length - length // 4) // 2 + 1
                last, divisor = first + length // 4 - 1, 3
            expected = [position for position in range(1, length + 1) if position % divisor == 0 and not first <= position <= last]
        replacement = dict(zip('ACGT', 'CGTA'))
        require(all(target[p - 1] == replacement[query[p - 1]] for p in expected), 'substitution bases differ from closure cycle')
        module = installation['local_module']
        module_start = (len(record['sequence']) - 2000) // 2
        require(len(module) == 2000 and set(module) <= set('ACGT') and module == record['sequence'][module_start:module_start + 2000], 'local module differs from centered declared ACGT record content')
    require(differences == expected, f'{case}: constructed difference positions differ')
    require(installation['difference_positions'] == expected and all(type(p) is int for p in installation['difference_positions']), 'declared complete difference array differs')
    require(installation['constructed_identity'] == [length - len(expected), length] and all(type(n) is int for n in installation['constructed_identity']), 'constructed identity numerator/denominator differs')
    if case == 'PC01':
        _e04_expected_coordinates(installation, len(record['sequence']))


def evaluate_e04_fixture_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Check a local JSON declaration in memory. No file, sequence generator or engine is invoked."""
    issues: list[dict[str, str]] = []
    checked: list[str] = []
    if not isinstance(catalog, Mapping):
        issues.append({'component': 'catalog', 'location': 'catalog', 'reason': 'catalog must be an object'})
        catalog = {}
    fixtures = catalog.get('fixtures')
    fixtures = fixtures if isinstance(fixtures, list) else []
    installations = catalog.get('installations')
    installations = installations if isinstance(installations, list) else []
    fixtures_by_key = {(f['fixture_set_id'], f['fixture_role'], f['fixture_id']): f for f in fixtures if isinstance(f, Mapping) and all(isinstance(f.get(k), str) for k in ('fixture_set_id', 'fixture_role', 'fixture_id'))}
    records = {r.get('analysis_id'): (f, r) for f in fixtures if isinstance(f, Mapping) and isinstance(f.get('records'), list) for r in f['records'] if isinstance(r, Mapping) and isinstance(r.get('analysis_id'), str)}
    declarations = catalog.get('design_declarations')
    declarations = declarations if isinstance(declarations, Mapping) else {}
    # Missing members are enumerated individually before any dependent check can fail.
    required = ('version', 'recipe', 'generator_version', 'seed', 'alphabet', 'closure_reference',
                'fixtures', 'installations', 'identifier_map', 'headers', 'normative_lines', 'declared_normative_entry_count',
                'execution_declarations', 'traceability', 'fragmentation_rule', 'build_rules', 'index_files', 'database_id_inspection', 'design_declarations')
    field_objects = [('catalog', catalog, required)]
    for index, fixture in enumerate(fixtures):
        field_objects.append((f'fixtures[{index}]', fixture, ('fixture_set_id', 'fixture_id', 'fixture_role', 'prefix', 'record_lengths', 'record_count', 'total_bases', 'ambiguities', 'repeats', 'fasta_sha256', 'records')))
        if isinstance(fixture, Mapping) and isinstance(fixture.get('records'), list):
            for row_index, record in enumerate(fixture['records']):
                field_objects.append((f'fixtures[{index}].records[{row_index}]', record, ('analysis_id', 'class', 'sequence', 'sequence_sha256', 'logical_origin', 'ambiguous_positions')))
    for index, installation in enumerate(installations):
        field_objects.append((f'installations[{index}]', installation, ('installation_id', 'planted_instance_id', 'instance_identity', 'fixture_set_id', 'fixture_id', 'fixture_role', 'analysis_id', 'class', 'expected_detection_class', 'length', 'query_sequence', 'query_sha256', 'local_module', 'local_module_sha256', 'generation_keys', 'orientation', 'planted_interval', 'coordinates', 'gaps', 'difference_positions', 'constructed_identity')))
    for location, obj, fields in field_objects:
        for field in fields:
            if not isinstance(obj, Mapping) or field not in obj or obj[field] is None or (isinstance(obj[field], str) and not obj[field].strip()):
                issues.append({'component': 'required_fields', 'location': f'{location}.{field}', 'reason': 'required declaration absent'})
    for name in E04_CATALOG_DESIGN_DECLARATIONS:
        try:
            value = declarations.get(name)
            require(isinstance(value, Mapping) and value.get('state') == 'DECLARED', 'PENDING: explicit documentary design declaration missing')
            _u06_text(value.get('reference'), name + '.reference')
            _e07_declared_content(value.get('specification'), name + '.specification')
        except (ResourceContractError, TypeError, ValueError) as exc:
            issues.append({'component': 'design_declarations', 'location': name, 'reason': str(exc)})

    work = [('catalog_fields', 'catalog', catalog), ('headers', 'catalog', catalog),
            ('bijection', 'catalog', catalog), ('roles', 'catalog', catalog), ('coverage', 'catalog', catalog),
            ('build_declarations', 'catalog', catalog), ('fragmentation', 'catalog', catalog)]
    work.extend(('fixture', f'fixtures[{i}]', row) for i, row in enumerate(fixtures))
    work.extend((kind, f'installations[{i}]', row) for i, row in enumerate(installations) for kind in ('literals', 'construction', 'coordinates'))
    for component, location, value in work:
        try:
            require(isinstance(value, Mapping), 'declaration must be an object')
            if component == 'catalog_fields':
                require(fixtures and installations, 'fixture and installation declarations required')
                require(catalog['recipe'] == 'NB04_SYNTHETIC_CASE_SHA256_ACGT_V1', 'recipe literal differs; closure provenance never belongs in recipe')
                require(type(catalog['seed']) is int, 'declared integer seed required')
                require(catalog['alphabet'] == 'UPPERCASE_IUPAC_DNA', 'alphabet policy differs')
                for field in ('version', 'generator_version', 'closure_reference'):
                    _u06_text(catalog[field], field)
                require(len(fixtures_by_key) == len(fixtures), 'fixture identity repeated within role')
            elif component == 'fixture':
                _u06_text(value['fixture_set_id'], 'fixture_set_id')
                _u06_text(value['fixture_id'], 'fixture_id')
                require(value['fixture_role'] in ('TUNING', 'VALIDATION'), 'fixture role invalid')
                lengths = value['record_lengths']
                require(isinstance(lengths, list) and lengths and all(type(n) is int and n > 0 for n in lengths), 'record length vector missing or invalid')
                require(type(value['record_count']) is int and value['record_count'] == len(lengths) == len(value['records']), 'record counts/vector differ')
                require(type(value['total_bases']) is int and value['total_bases'] == sum(lengths), 'total bases differ from complete vector')
                require(re.fullmatch(r'[0-9a-f]{64}', value['fasta_sha256']) is not None, 'declared FASTA hash invalid')
                for field in ('ambiguities', 'repeats'):
                    _e07_declared_content(value[field], field)
                require(isinstance(value['repeats'], Mapping) and all(isinstance(value['repeats'].get(k), list) for k in ('motifs', 'positions')), 'repeat motifs and positions must be declared explicitly')
                for row, length in zip(value['records'], lengths):
                    sequence = _u06_text(row['sequence'], row['analysis_id'] + '.sequence')
                    require(len(sequence) == length and set(sequence) <= DNA, 'declared record length/alphabet differs')
                    require(hashlib.sha256(sequence.encode('ascii')).hexdigest() == row['sequence_sha256'], 'declared sequence SHA256 differs from supplied content')
                    require(row['ambiguous_positions'] == [i for i, base in enumerate(sequence, 1) if base not in 'ACGT'] and all(type(p) is int for p in row['ambiguous_positions']), 'declared ambiguity positions differ from content')
                    _u06_text(row['logical_origin'], 'logical_origin')
                require(type(value['ambiguities']['count']) is int and value['ambiguities']['count'] == sum(len(row['ambiguous_positions']) for row in value['records']), 'declared ambiguity count differs')
            elif component == 'headers':
                prefixes: dict[str, tuple[str, str]] = {}
                owners: dict[tuple[str, str], str] = {}
                grouped: dict[tuple[str, str], list[int]] = {}
                for fixture in fixtures:
                    prefix = fixture['prefix']
                    require(isinstance(prefix, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,23}', prefix), 'unsafe FASTA prefix')
                    owner = (fixture['fixture_set_id'], fixture['fixture_role'])
                    require(prefix not in prefixes or prefixes[prefix] == owner, 'prefix repeated across set/role')
                    require(owner not in owners or owners[owner] == prefix, 'set/role must have one declared prefix')
                    prefixes[prefix] = owner
                    owners[owner] = prefix
                    for record in fixture['records']:
                        match = re.fullmatch(re.escape(prefix) + r'__([0-9]{8})', record['analysis_id'])
                        require(match is not None, 'unsafe FASTA analysis_id/header')
                        grouped.setdefault(owner, []).append(int(match.group(1)))
                for numbers in grouped.values():
                    require(sorted(numbers) == list(range(1, len(numbers) + 1)), 'FASTA numbering must start at 00000001 without holes or duplicates')
            elif component == 'bijection':
                headers, rows = catalog['headers'], catalog['identifier_map']
                require(isinstance(headers, list) and isinstance(rows, list), 'declared headers/map must be lists')
                total = sum(len(f['records']) for f in fixtures)
                map_ids = [row['analysis_id'] for row in rows]
                require(len(records) == total == len(headers) == len(set(headers)) == len(rows) == len(set(map_ids)), 'catalog/map/header counts or duplicate IDs differ')
                require(set(records) == set(headers) == set(map_ids), 'catalog/map/header bijection broken')
                for row in rows:
                    fixture, record = records[row['analysis_id']]
                    installation_ids = sorted(i['installation_id'] for i in installations if i['analysis_id'] == row['analysis_id'])
                    expected = {'fixture_set_id': fixture['fixture_set_id'], 'fixture_role': fixture['fixture_role'],
                                'fixture_id': fixture['fixture_id'], 'class': record['class'], 'length': len(record['sequence']),
                                'version': catalog['version'], 'installation_ids': installation_ids,
                                'logical_origin': record['logical_origin'], 'sequence_sha256': record['sequence_sha256']}
                    require(all(json_bytes(row.get(key)) == json_bytes(item) for key, item in expected.items()), 'identifier_map binding differs from catalog/installation')
            elif component == 'roles':
                require({f['fixture_role'] for f in fixtures} == {'TUNING', 'VALIDATION'}, 'both distinct fixture roles required')
                for field in ('analysis_id', 'sequence_sha256', 'sequence'):
                    role_sets = {role: {r[field] for f in fixtures if f['fixture_role'] == role for r in f['records']} for role in ('TUNING', 'VALIDATION')}
                    require(not role_sets['TUNING'] & role_sets['VALIDATION'], f'TUNING/VALIDATION overlap in {field}')
                require(not {f['fasta_sha256'] for f in fixtures if f['fixture_role'] == 'TUNING'} & {f['fasta_sha256'] for f in fixtures if f['fixture_role'] == 'VALIDATION'}, 'TUNING/VALIDATION FASTA hash overlap')
                identities: dict[str, tuple[str, str, int, str]] = {}
                repeated: dict[tuple[str, str, int, str], tuple[str, str, str]] = {}
                record_owners: dict[tuple[str, str, str, str], tuple[str, str, int, str]] = {}
                specified_instance_ids: dict[tuple[str, str, int, str, str], str] = {}
                specified_instance_counts: dict[tuple[str, str, int, str, str], int] = {}
                for row in installations:
                    _u06_text(row['installation_id'], 'installation_id')
                    _u06_text(row['planted_instance_id'], 'planted_instance_id')
                    role = row['fixture_role']
                    identity = row['instance_identity']
                    expected = {'fixture_role': role, 'class': row['class'], 'length': row['length'], 'version': catalog['version']}
                    require(json_bytes(identity) == json_bytes(expected), 'instance identity must explicitly include matching role/class/length/version')
                    key = (role, row['class'], row['length'], catalog['version'])
                    require(row['planted_instance_id'] not in identities or identities[row['planted_instance_id']] == key, 'planted_instance_id reused for a different identity or role')
                    identities[row['planted_instance_id']] = key
                    if row['class'] in ('PC02', 'PC03', 'PC06'):
                        fixture_scope = (row['fixture_set_id'], role, row['fixture_id'])
                        instance_key = key + (row['fixture_id'],)
                        declared_instance_id = specified_instance_ids.get(instance_key)
                        require(declared_instance_id is None or declared_instance_id == row['planted_instance_id'], 'one logical instance and fixture cannot use multiple planted_instance_id aliases')
                        specified_instance_ids[instance_key] = row['planted_instance_id']
                        record_key = fixture_scope + (row['analysis_id'],)
                        record_instance = record_owners.get(record_key)
                        require(record_instance is None or record_instance == key, 'distinct A.8 logical instances must occupy distinct records within a fixture')
                        record_owners[record_key] = key
                        specified_instance_counts[instance_key] = specified_instance_counts.get(instance_key, 0) + 1
                        require(specified_instance_counts[instance_key] == 1, 'specified planted instance permits one installation per fixture')
                    if row['class'] in ('PC03', 'PC06'):
                        signature = (row['query_sequence'], row['local_module'], row['planted_instance_id'])
                        require(key not in repeated or repeated[key] == signature, 'PC03/PC06 query or local module differs between fixture sizes')
                        repeated[key] = signature
                for field in ('query_sequence', 'query_sha256', 'local_module', 'local_module_sha256'):
                    by_role = {role: {row[field] for row in installations if row['fixture_role'] == role} for role in ('TUNING', 'VALIDATION')}
                    require(not by_role['TUNING'] & by_role['VALIDATION'], f'TUNING/VALIDATION overlap in {field}')
            elif component == 'literals':
                role, case, length = value['fixture_role'], value['class'], value['length']
                require(role in ('TUNING', 'VALIDATION') and isinstance(case, str) and re.fullmatch(r'PC[0-9]{2}[AB]?', case), 'generation role/class invalid')
                require(type(length) is int and length > 0, 'generation length must be positive integer')
                counters: dict[str, list[int]] = {}
                require(isinstance(value['generation_keys'], list) and value['generation_keys'], 'declared generation keys missing')
                for entry in value['generation_keys']:
                    stream, counter = entry['stream'], entry['counter']
                    _u06_text(stream, 'generation stream')
                    require('|' not in stream and all(marker not in stream.lower() for marker in ('closure a.8', 'nb04_preapproval_closure')), 'unsafe generation stream/provenance')
                    require(type(counter) is int and counter >= 0, 'counter must be nonnegative integer')
                    key = f'NB04_SYNTHETIC_CASE_V1|{role}|{case}|{length}|{stream}|{counter}'
                    require(entry['key'] == key, 'generation key differs from exact UTF8 literal; closure reference must be separate')
                    counters.setdefault(stream, []).append(counter)
                require(all(sorted(values) == list(range(len(values))) for values in counters.values()), 'generation counters must start at zero without leading zeros, holes or duplicates')
                for field, digest_field in (('query_sequence', 'query_sha256'), ('local_module', 'local_module_sha256')):
                    content = _u06_text(value[field], field)
                    require(set(content) <= DNA, f'{field}: declared sequence alphabet invalid')
                    require(hashlib.sha256(content.encode('ascii')).hexdigest() == value[digest_field], f'{digest_field} differs from supplied content')
            elif component in ('construction', 'coordinates'):
                require(value['analysis_id'] in records, 'installation refers to absent catalog record')
                fixture, record = records[value['analysis_id']]
                require((value['fixture_set_id'], value['fixture_role'], value['fixture_id']) == (fixture['fixture_set_id'], fixture['fixture_role'], fixture['fixture_id']), 'installation fixture set/role differs from record')
                if component == 'construction':
                    _e04_construction(value, record)
                else:
                    require(value['class'] in ('PC01', 'PC02', 'PC03', 'PC06') and value['gaps'] == [], f'PENDING_COORDINATE_SPECIFICATION:{value["class"]}')
                    _e04_expected_coordinates(value, len(record['sequence']))
            elif component == 'coverage':
                lines, executions, trace = catalog['normative_lines'], catalog['execution_declarations'], catalog['traceability']
                require(isinstance(lines, list) and lines and type(catalog['declared_normative_entry_count']) is int and len(lines) == catalog['declared_normative_entry_count'], 'declared normative entry target/count differs')
                line_map = {line['line_id']: line for line in lines}
                install_map = {row['installation_id']: row for row in installations}
                execution_map = {row['execution_id']: row for row in executions}
                require(len(line_map) == len(lines) and len(install_map) == len(installations) and len(execution_map) == len(executions), 'line/installation/execution IDs repeated')
                require(all(type(line.get('applicable')) is bool for line in lines), 'line applicability must be explicit')
                require(isinstance(trace, list) and trace, 'line-installation-execution-QA traceability missing')
                for execution in executions:
                    execution_id = execution['execution_id']
                    _u06_text(execution_id, 'execution_id')
                    execution_installations = execution['installation_ids']
                    require(isinstance(execution_installations, list), f'{execution_id}: installation_ids must be a declared list')
                    for installation_id in execution_installations:
                        require(isinstance(installation_id, str) and installation_id in install_map, f'{execution_id}: unknown installation_id:{installation_id}')
                    execution_qas = execution['qa_ids']
                    require(isinstance(execution_qas, list), f'{execution_id}: qa_ids must be a declared list')
                    for qa_id in execution_qas:
                        require(isinstance(qa_id, str) and qa_id in E05_QA_SPEC, f'{execution_id}: unknown qa_id:{qa_id}')
                    require(execution['state'] == 'NOT_EXECUTED', f'{execution_id}: only unexecuted declarations accepted, never recovery results')
                covered_lines, covered_installations = set(), set()
                for link in trace:
                    line, installation, execution = line_map[link['line_id']], install_map[link['installation_id']], execution_map[link['execution_id']]
                    require(line['applicable'] is True, 'trace points to an inapplicable line')
                    require(all(line[field] == installation[field] for field in ('fixture_id', 'fixture_role', 'class')), 'normative line/installation binding differs')
                    require(link['qa_id'] in E05_QA_SPEC and link['qa_id'] in execution['qa_ids'] and installation['installation_id'] in execution['installation_ids'], 'execution/QA trace binding differs')
                    covered_lines.add(line['line_id'])
                    covered_installations.add(installation['installation_id'])
                require(covered_lines == {line['line_id'] for line in lines if line['applicable']} and covered_installations == set(install_map), 'applicable line or installation lacks traceability')
            elif component == 'fragmentation':
                rule = catalog['fragmentation_rule']
                require(isinstance(rule, Mapping), 'explicit fragmentation declaration required')
                require(rule.get('preserve_each_hsp') is True and rule.get('preserve_planted_subinterval_links') is True, 'each HSP and its planted-subinterval links must be preserved')
                require(rule.get('fabricate_continuous_hsp') is False and rule.get('cross_record_concatenation') is False, 'fabricated HSPs and cross-record concatenation are forbidden')
            elif component == 'build_declarations':
                build = catalog['build_rules']
                require(isinstance(build, Mapping) and isinstance(build['fixture'], Mapping) and isinstance(build['production'], Mapping), 'fixture and production build declarations required')
                for side_name in ('fixture', 'production'):
                    side = build[side_name]
                    require(type(side['dbtype']) is str and side['dbtype'] == 'nucl', f'{side_name}: dbtype must match the declared nucleotide build')
                    require(type(side['parse_seqids']) is bool and side['parse_seqids'] is True, f'{side_name}: parse_seqids must be true')
                    require(type(side['blastdb_version']) is int and side['blastdb_version'] == 5, f'{side_name}: blastdb_version must be the fixed version 5')
                    require(type(side['max_file_sz_effective']) is int, f'{side_name}: max_file_sz_effective must be an integer; no value or range is selected here')
                    require(type(side['volume_strategy']) is str and type(side['taxid_policy']) is str, f'{side_name}: volume and taxid policies must be text')
                for field in E05_SECTION7_KEYS['database_build']:
                    require(field in build['fixture'] and field in build['production'], f'build field missing:{field}')
                    if field != 'taxid_policy':
                        require(not _section7_unresolved(build['fixture'][field]) and json_bytes(build['fixture'][field]) == json_bytes(build['production'][field]), f'fixture/production build differs:{field}')
                require(build['fixture']['taxid_policy'] == 'OMIT_FOR_SYNTHETIC_NO_TAXONOMIC_FILTER' and build['production']['taxid_policy'] == 'SOURCE_SPECIES_METADATA', 'synthetic/source taxid policy differs')
                require(isinstance(catalog['index_files'], list) and catalog['index_files'], 'index file declarations missing')
                for row in catalog['index_files']:
                    _e07_relative_input_path(row['path'])
                    require(re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is not None, 'index hash declaration invalid')
                inspection = catalog['database_id_inspection']
                require(inspection['state'] == 'DECLARED' and inspection['analysis_ids'] == catalog['headers'], 'database inspection declaration missing or differs from headers')
                aliases = inspection['engine_to_analysis_id']
                require(isinstance(aliases, Mapping) and aliases and set(aliases.values()) == set(records), 'explicit engine ID/alias mapping incomplete')
                require(all(isinstance(key, str) and key.strip() for key in aliases), 'engine identifier missing')
            checked.append(f'{component}:{location}')
        except (ResourceContractError, KeyError, TypeError, ValueError, AttributeError) as exc:
            issues.append({'component': component, 'location': location, 'reason': str(exc)})
    return {'state': 'DECLARATIONS_CONSISTENT' if not issues else 'RECUSADO', 'blocking_declarations': issues,
            'checked_declarations': checked, 'authority_verified': False, 'materialization_performed': False,
            'execution_performed': False, 'informative_command_allowed': False, 'freeze_produced': False,
            'qa_status': 'NOT_TESTED', 'limitations': list(E04_CATALOG_LIMITATIONS)}


# U09 is a local declared schema for plan_v003 section 6.5, pending adjudication.
E06_TOLERANCE_SCHEMA_CHOICES = {
    'applicable_instances': 'Declared applicability inventory. instance_identity retains role/class/length/version. fixture and build bind each installation scope.',
    'complete_patterns': 'Declared complete patterns, supplied by the caller. Completeness and scientific correspondence are not established here.',
    'expected_object': 'Declared comparison object. exact_endpoints lists contractual exactness, with exactness_contractual_reason. PC01 requires all four endpoints.',
    'candidate_configurations': 'Candidate ID to declared configuration content. References from records resolve within each applicable instance.',
    'domains': 'Domain ID to comparison policy. CONSTANT requires common_domain. CANDIDATE_SPECIFIC requires same_rigor_by_candidate covering every candidate.',
    'records': 'Exactly one entry per applicable instance, domain and candidate. instance_id/domain_id/candidate_id resolve the role, patterns, expected object, configuration, fixture and build.',
    'endpoints': 'qstart/qend/sstart/send each carry value and unit nt, or value NOT_APPLICABLE and contractual_reason. Other tolerance categories are forbidden.',
    'independent_basis': 'reference/content/units/assumptions/pattern_and_extension_parameters are nonempty declarations. numeric_criterion_provided is an explicit boolean. Defensibility is not assessed.',
    'covers_entire_interval': 'Explicit declared interval coverage. A true value requires discriminating_criterion. Its scientific adequacy is not assessed.',
    'conditional_tolerance_basis': 'PC03 declaration of its previously grounded conditional tolerance. qa_b_applicable remains false.',
    'structured_declarations': 'Closed local shapes: complete_patterns requires query_pattern/subject_pattern. fixture requires fixture_id/version. build requires build_id. candidate configuration requires configuration. expected_object.content requires object. Optional reference hashes are pattern_sha256/fixture_sha256/build_sha256/configuration_sha256/reference_sha256 only in their corresponding shape. Patterns and expected object may describe orientation/origin/coordinate_system as text and coordinates as qstart/qend/sstart/send integers. score_recovery_model is admitted only in expected_object.content and independent_basis, with scoring_inputs/reference/assumptions. Its scoring_inputs are symbolic parameter names only. Labels, measured extents, arbitrary nested members and lists of pairs are outside these shapes.',
}


def _e06_fields(value: Any, required: tuple[str, ...], location: str, optional: tuple[str, ...] = ()) -> None:
    require(isinstance(value, Mapping), f'{location}: declared object required')
    for field in required:
        require(field in value, f'{location}.{field}: required declaration absent')
    require(set(value) <= set(required + optional), f'{location}: undeclared field or forbidden tolerance category:{sorted(set(value) - set(required + optional), key=str)}')


def _e06_symbolic_score_model(value: Any, location: str) -> None:
    """Admit symbolic input references only, without empirical fields or model approval."""
    _e06_fields(value, ('scoring_inputs', 'reference', 'assumptions'), location)
    inputs = value['scoring_inputs']
    symbols = ('reward', 'penalty', 'gapopen', 'gapextend', 'xdrop', 'xdrop_ungap', 'xdrop_gap', 'xdrop_gap_final')
    require(isinstance(inputs, list) and inputs and all(type(item) is str and item in symbols for item in inputs),
            f'{location}.scoring_inputs: declared symbolic scoring parameter names required')
    require(len(set(inputs)) == len(inputs), f'{location}.scoring_inputs: duplicate symbolic input')
    _u06_text(value['reference'], location + '.reference')
    _u06_text(value['assumptions'], location + '.assumptions')


def _e06_structured_declaration(value: Any, kind: str, location: str) -> None:
    """Close each binding shape rather than infer content categories from field spelling."""
    description_fields = ('orientation', 'origin', 'coordinate_system', 'coordinates')
    shapes = {
        'complete_patterns': (('query_pattern', 'subject_pattern'), description_fields + ('pattern_sha256',)),
        'fixture': (('fixture_id', 'version'), ('fixture_sha256',)),
        'build': (('build_id',), ('build_sha256',)),
        'configuration': (('configuration',), ('configuration_sha256',)),
        'expected_object': (('object',), description_fields + ('reference_sha256', 'score_recovery_model')),
    }
    required, optional = shapes[kind]
    _e06_fields(value, required, location, optional)
    for field, item in value.items():
        field_location = location + '.' + field
        if field == 'score_recovery_model':
            _e06_symbolic_score_model(item, field_location)
        elif field == 'coordinates':
            _e06_fields(item, ('qstart', 'qend', 'sstart', 'send'), field_location)
            require(all(type(number) is int and number > 0 for number in item.values()), f'{field_location}: declared one based coordinates required')
        elif field.endswith('_sha256'):
            require(isinstance(item, str) and re.fullmatch(r'[0-9a-f]{64}', item) is not None, f'{field_location}: reference SHA256 declaration required')
        else:
            _u06_text(item, field_location)


def evaluate_e06_tolerance_register(register: Mapping[str, Any]) -> dict[str, Any]:
    """Check only supplied declarations. Never choose tolerances or authorize E06/E07."""
    issues: list[dict[str, str]] = []
    checked: list[str] = []
    blocked: list[dict[str, str]] = []
    instances: dict[str, Mapping[str, Any]] = {}
    instance_scopes: set[bytes] = set()
    expected: set[tuple[str, str, str]] = set()
    seen: set[tuple[str, str, str]] = set()
    group_values: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    canonical_content = None
    endpoint_names = ('qstart', 'qend', 'sstart', 'send')
    try:
        _e06_fields(register, ('applicable_instances', 'records'), 'register')
        _e07_declared_content(register, 'register')
        require(isinstance(register['applicable_instances'], list) and register['applicable_instances'], 'applicable_instances: nonempty declared inventory required')
        require(isinstance(register['records'], list), 'records: declared list required')
        checked.append('canonical_fields')
    except (ResourceContractError, TypeError, ValueError) as exc:
        issues.append({'component': 'register', 'location': 'register', 'reason': str(exc)})

    declarations = register.get('applicable_instances', []) if isinstance(register, Mapping) else []
    for index, instance in enumerate(declarations if isinstance(declarations, list) else []):
        location = f'applicable_instances[{index}]'
        try:
            _e06_fields(instance, ('instance_id', 'instance_identity', 'complete_patterns', 'expected_object', 'fixture', 'build',
                                   'candidate_configurations', 'domains', 'expected_detection_class', 'qa_b_applicable'), location,
                        ('conditional_tolerance_basis',))
            instance_id = _u06_text(instance['instance_id'], location + '.instance_id')
            require(instance_id not in instances, f'{location}: duplicate instance_id')
            identity = instance['instance_identity']
            _e06_fields(identity, ('fixture_role', 'class', 'length', 'version'), location + '.instance_identity')
            require(identity['fixture_role'] in ('TUNING', 'VALIDATION'), f'{location}: invalid fixture_role')
            require(isinstance(identity['class'], str) and re.fullmatch(r'PC[0-9]{2}[AB]?', identity['class']), f'{location}: invalid class')
            require(type(identity['length']) is int and identity['length'] > 0, f'{location}: invalid length')
            _u06_text(identity['version'], location + '.version')
            for field in ('complete_patterns', 'fixture', 'build'):
                _e06_structured_declaration(instance[field], field, location + '.' + field)
            obj = instance['expected_object']
            _e06_fields(obj, ('content', 'exact_endpoints', 'exactness_contractual_reason'), location + '.expected_object')
            _e06_structured_declaration(obj['content'], 'expected_object', location + '.expected_object.content')
            require(isinstance(obj['exact_endpoints'], list) and len(set(obj['exact_endpoints'])) == len(obj['exact_endpoints'])
                    and set(obj['exact_endpoints']) <= set(endpoint_names), f'{location}: invalid exact_endpoints')
            _u06_text(obj['exactness_contractual_reason'], location + '.exactness_contractual_reason')
            case = identity['class']
            if case == 'PC01':
                require(set(obj['exact_endpoints']) == set(endpoint_names), f'{location}: PC01 exactness requires all endpoints')
            detection = {'PC01': 'MUST_BE_REPORTED', 'PC02': 'MUST_BE_REPORTED',
                         'PC03': 'CHARACTERIZED_NOT_ASSERTED', 'PC06': 'CHARACTERIZED_NOT_ASSERTED'}
            _u06_text(instance['expected_detection_class'], location + '.expected_detection_class')
            if case in detection:
                require(instance['expected_detection_class'] == detection[case], f'{location}: contractual detection class differs')
            require(type(instance['qa_b_applicable']) is bool, f'{location}: qa_b_applicable must be explicit boolean')
            if case == 'PC03':
                require(instance['qa_b_applicable'] is False, f'{location}: PC03 remains outside QA-B')
                _u06_text(instance.get('conditional_tolerance_basis'), location + '.conditional_tolerance_basis')
            if case == 'PC06':
                require(instance['qa_b_applicable'] is True, f'{location}: PC06 emitted objects participate in QA-B')
            candidates, domains = instance['candidate_configurations'], instance['domains']
            require(isinstance(candidates, Mapping) and candidates, f'{location}.candidate_configurations: nonempty candidate declarations required')
            for candidate_id, configuration in candidates.items():
                _u06_text(candidate_id, location + '.candidate_id')
                _e06_structured_declaration(configuration, 'configuration', location + '.candidate_configurations.' + candidate_id)
            require(isinstance(domains, Mapping) and domains, f'{location}.domains: nonempty domains required')
            for domain_id, policy in domains.items():
                _u06_text(domain_id, location + '.domain_id')
                _e06_fields(policy, ('tolerance_mode',), location + '.domains.' + domain_id,
                            ('common_domain', 'same_rigor_by_candidate'))
                require(policy['tolerance_mode'] in ('CONSTANT', 'CANDIDATE_SPECIFIC'), f'{location}: invalid tolerance_mode')
                if 'common_domain' in policy:
                    _u06_text(policy['common_domain'], location + '.common_domain')
                if 'same_rigor_by_candidate' in policy:
                    rigor = policy['same_rigor_by_candidate']
                    require(isinstance(rigor, Mapping) and set(rigor) == set(candidates), f'{location}: same rigor declaration required for every candidate')
                    for candidate_id, content in rigor.items():
                        _u06_text(content, location + '.same_rigor_by_candidate.' + candidate_id)
                if policy['tolerance_mode'] == 'CONSTANT':
                    _u06_text(policy.get('common_domain'), location + '.common_domain')
                else:
                    rigor = policy.get('same_rigor_by_candidate')
                    require(isinstance(rigor, Mapping) and set(rigor) == set(candidates), f'{location}: same rigor declaration required for every candidate')
                    for candidate_id, content in rigor.items():
                        _u06_text(content, location + '.same_rigor_by_candidate.' + candidate_id)
                expected.update((instance_id, domain_id, candidate_id) for candidate_id in candidates)
            # Identity includes fixture/build, allowing the same logical instance in distinct installation scopes.
            scope = json_bytes({key: instance[key] for key in ('instance_identity', 'fixture', 'build')})
            require(scope not in instance_scopes, f'{location}: duplicate logical instance/fixture/build under another alias')
            instance_scopes.add(scope)
            instances[instance_id] = instance
            checked.append(location)
        except (ResourceContractError, KeyError, TypeError, ValueError, AttributeError) as exc:
            issues.append({'component': 'applicability', 'location': location, 'reason': str(exc)})

    records = register.get('records', []) if isinstance(register, Mapping) else []
    for index, record in enumerate(records if isinstance(records, list) else []):
        location = f'records[{index}]'
        try:
            _e06_fields(record, ('instance_id', 'domain_id', 'candidate_id', 'endpoints', 'independent_basis', 'covers_entire_interval'), location,
                        ('discriminating_criterion',))
            key = tuple(_u06_text(record[field], location + '.' + field) for field in ('instance_id', 'domain_id', 'candidate_id'))
            require(key in expected and key[0] in instances, f'{location}: undeclared instance/domain/candidate binding')
            require(key not in seen, f'{location}: duplicate instance/domain/candidate record')
            seen.add(key)
            instance = instances[key[0]]
            endpoints = record['endpoints']
            _e06_fields(endpoints, endpoint_names, location + '.endpoints')
            for endpoint in endpoint_names:
                item = endpoints[endpoint]
                require(isinstance(item, Mapping) and 'value' in item, f'{location}.{endpoint}.value: numeric nt or NOT_APPLICABLE required')
                if item['value'] == 'NOT_APPLICABLE':
                    _e06_fields(item, ('value', 'contractual_reason'), location + '.' + endpoint)
                    _u06_text(item['contractual_reason'], location + '.' + endpoint + '.contractual_reason')
                else:
                    _e06_fields(item, ('value', 'unit'), location + '.' + endpoint)
                    value = item['value']
                    require(type(value) in (int, float) and 0 <= value < float('inf') and item['unit'] == 'nt',
                            f'{location}.{endpoint}: finite nonnegative numerical tolerance in nt required')
                if endpoint in instance['expected_object']['exact_endpoints']:
                    require(type(item['value']) in (int, float) and item['value'] == 0, f'{location}.{endpoint}: contractual exactness requires zero nt')
            basis = record['independent_basis']
            _e06_fields(basis, ('reference', 'content', 'units', 'assumptions', 'pattern_and_extension_parameters', 'numeric_criterion_provided'), location + '.independent_basis',
                        ('score_recovery_model',))
            if 'score_recovery_model' in basis:
                _e06_symbolic_score_model(basis['score_recovery_model'], location + '.independent_basis.score_recovery_model')
            for field in ('reference', 'content', 'units', 'assumptions', 'pattern_and_extension_parameters'):
                _u06_text(basis[field], location + '.independent_basis.' + field)
            require(type(basis['numeric_criterion_provided']) is bool, f'{location}: numeric_criterion_provided must be explicit boolean')
            require(basis['numeric_criterion_provided'] is True, f'{location}: STOP_INDEPENDENT_NUMERIC_CRITERION_UNAVAILABLE')
            require(type(record['covers_entire_interval']) is bool, f'{location}: interval coverage declaration required')
            if record['covers_entire_interval']:
                _u06_text(record.get('discriminating_criterion'), location + '.discriminating_criterion')
            policy = instance['domains'][key[1]]
            values = tuple(endpoints[endpoint]['value'] for endpoint in endpoint_names)
            previous = group_values.setdefault(key[:2], [])
            if policy['tolerance_mode'] == 'CONSTANT':
                require(not previous or values == previous[0], f'{location}: CONSTANT tolerances differ between candidates')
            previous.append(values)
            checked.append(location)
        except (ResourceContractError, KeyError, TypeError, ValueError, AttributeError) as exc:
            issues.append({'component': 'record', 'location': location, 'reason': str(exc)})
            if isinstance(record, Mapping):
                blocked.append({field: record.get(field) for field in ('instance_id', 'domain_id', 'candidate_id')})
    for instance_id, domain_id, candidate_id in sorted(expected - seen):
        missing = dict(instance_id=instance_id, domain_id=domain_id, candidate_id=candidate_id)
        blocked.append(missing)
        issues.append({'component': 'coverage', 'location': ':'.join((instance_id, domain_id, candidate_id)),
                       'reason': 'required instance/domain/candidate record absent'})
    for (instance_id, domain_id), values in group_values.items():
        if len(values) > 1 and all(value == values[0] for value in values):
            try:
                _u06_text(instances[instance_id]['domains'][domain_id].get('common_domain'), f'{instance_id}:{domain_id}.common_domain')
            except ResourceContractError as exc:
                issues.append({'component': 'candidate_comparison', 'location': f'{instance_id}:{domain_id}', 'reason': str(exc)})
    if not issues:
        canonical_content = json_bytes(register).decode('utf-8')
    return {'state': 'DECLARATIONS_CONSISTENT' if not issues else 'RECUSADO', 'blocking_declarations': issues,
            'checked_declarations': checked, 'blocked_records': blocked,
            'dependent_instances_blocked': bool(issues), 'dependent_executions_blocked': True,
            'canonical_content': canonical_content, 'schema_choices': dict(E06_TOLERANCE_SCHEMA_CHOICES),
            'authority_verified': False, 'scientific_defensibility_assessed': False,
            'materialization_performed': False, 'execution_performed': False, 'informative_command_allowed': False,
            'freeze_produced': False, 'qa_status': 'NOT_TESTED',
            'limitations': ['Declared inventory coverage only. Actual applicability, complete patterns, provenance, exactness outside PC01, and interval coverage require independent adjudication.',
                           'Basis, common domain, discriminating criterion and equal rigor are checked for declared presence only. Their scientific adequacy is not assessed.',
                           'Closed local shapes admit declared bindings and symbolic scoring input references. Unknown fields and alternate structural encodings are refused. Free text is not semantically adjudicated and symbolic models are not scientifically approved.',
                           'No numerical tolerance is selected or grounded here. E06 is not completed and U07 tolerance_representation remains blocked.']}
