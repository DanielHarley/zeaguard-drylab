"""NB04 CP1 pre-freeze preservation control, execution scope, and geometry derivation (E01, E03).

Re-executable verification of G0 certified artifacts, the 43 normative documents,
the six frozen CP1 resources and their BLAST index volumes, historical snapshots,
observed BLAST tool builds, the closed dirty-tree allowlist, and read-only
derivation of NB04_RESOURCE_ARCHITECTURE_GEOMETRY_V1 records for the six resources.
No BLAST query, index build, fixture materialization, or calibration is executed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
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
            parsed_tool["tool_version"] == expected_version
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

