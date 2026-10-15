"""Import audited documentary tables and identity records for offline NB04 CP0.

External complete PLAN/review documents remain external. Original table records
retain their historical values. Adopted overlays are separate and explicit.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from zeaguard.nb04_cp0 import CP0, DOC_INPUT, PROVENANCE, QUERY_SPEC, digest, git, json_bytes, read_tsv, sha256, tsv_bytes
from zeaguard.nb04_policy import SCENARIO, SOIL_GAP, require
from zeaguard.nb04_complement import AUTHORITY_STATUS, CONTRACT_ID, CONTRACT_PATH, EXTENDED_VALUES, RULE_ID, SOURCE_HASHES, load_complement
from zeaguard.nb04_serialization import serialize_multivalue


NORMATIVE = {
    "01_PLAN_v2.2.5.md": ("9b759f71de500f65947bb150db71a5d20029da06971a26f7e20d1c72193dc83a", "v2.2.5", "APPROVED_WITH_ADOPTED_AMENDMENTS"),
    "B4_CALIBRATION_AMENDMENT_A1.md": ("0c1815be37ca6187639a27429fc0b38adb3f4be762f773f17a159f29b38f0ecc", "A1", "ADOPTED_AFTER_INDEPENDENT_AUDIT"),
    "NB04_PREAPPROVAL_CLOSURE.md": ("52b54d4fa633b2847818e7382e57fdbf9c1ec73588f662c93fb30f56aa7f618b", "2026/10/14", "RATIFIED_AFTER_INDEPENDENT_AUDIT"),
    "B6_GOVERNANCE_AMENDMENT_A1.md": ("9ea167a88359f78e916d753865d7d40a5c37d2ff04d3a09d73c647c3aebaa62b", "A1", "ADOPTED_AFTER_INDEPENDENT_AUDIT"),
}
NORMATIVE.update({name: (sha, "CP0_COMPLEMENT_V1", AUTHORITY_STATUS) for name, sha in SOURCE_HASHES.items()})
INITIAL_HEAD = "a34892d1874a7ea3298cb1873f02efd4cd99912a"
SNAPSHOT = "artifacts/reproducibility/20261014T200715078008Z_e37481d6d154/snapshot.json"
SNAPSHOT_HASH = "e396d89e56c1f205030ef19aae9e7fa8e4a217cd212741768be96d01cf5e1534"


def multi(cell: str) -> str:
    return serialize_multivalue([] if cell in {"", "NONE"} else cell.split("|"))


def dump(root: Path, name: str, data: bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def prepare(root: Path, package: Path, amendments: Path, b5: Path, b6: Path) -> None:
    complement = load_complement(root)
    require(git(root, "rev-parse", "HEAD").decode().strip() == INITIAL_HEAD, "initial HEAD changed")
    require(git(root, "branch", "--show-current").decode().strip() == "feat/nb04-cp0", "branch changed")
    require(digest(root / SNAPSHOT) == SNAPSHOT_HASH, "initial snapshot provenance mismatch")
    snapshot = json.loads((root / SNAPSHOT).read_text("utf-8"))
    for path, expected in snapshot["config_hashes"].items():
        require(digest(root / path) == expected, f"baseline config mismatch: {path}")
    documents = []
    source_paths = {}
    manifest = (package / "00_MANIFEST.md").read_text("utf-8")
    for name, prefix in re.findall(r"\| \d+ \| `([^`]+)` \| [\d,]+ \| `([0-9a-f]{16})` \|", manifest):
        path = package / name
        observed = digest(path)
        require(observed.startswith(prefix), f"package provenance mismatch: {name}, expected prefix={prefix}, observed={observed}")
        documents.append({"document_id": name, "version": name.removesuffix(".md").removesuffix(".tsv"), "sha256": observed, "verification": "PACKAGE_RECORDED_PREFIX_AND_OBSERVED_FULL", "applicability": "ADOPTED_BASELINE_PRESERVING_HISTORICAL_STATUS"})
        source_paths[name] = path
    require(len(documents) == 18, "package manifest must resolve 18 documents")
    for name, (expected, version, adoption) in NORMATIVE.items():
        path = package / name if name.startswith("01_") else root / "src/workstreams/bioinformatics/decisions" / name if name.startswith("B6_") else amendments / name
        observed = digest(path)
        require(observed == expected, f"provenance mismatch {name}: expected={expected}, observed={observed}")
        source_paths[name] = path
        documents = [d for d in documents if d["document_id"] != name]
        documents.append({"document_id": name, "version": version, "sha256": observed, "verification": "FULL_EXPECTED_SHA256", "applicability": adoption})
    for folder, scope in ((b5, "B5"), (b6, "B6")):
        for path in sorted(folder.iterdir()):
            if path.suffix not in {".tsv", ".md"}:
                continue
            observed = digest(path)
            if path.name == "B5_CONCERN_CRITERIA_REVIEW.md":
                require(observed == "ed7fd88c6ed8655d0c7b320bf21c618ef15ef11c478a60ec375436fcd4e37eb1", "B5 review provenance mismatch")
            documents.append({"document_id": path.name, "version": "HISTORICAL_AUDITED_BASELINE", "sha256": observed, "verification": "FULL_EXPECTED_SHA256" if path.name == "B5_CONCERN_CRITERIA_REVIEW.md" else "OBSERVED_FULL_IDENTITY", "applicability": "SUPERSEDED_FOR_GOVERNANCE_SCOPE_BY_B6_A1" if scope == "B6" and path.suffix == ".tsv" and path.name in {"b6_role_registry.tsv", "b6_competency_matrix.tsv", "b6_review_governance_matrix.tsv", "b6_disagreement_resolution.tsv", "b6_signoff_contract.tsv", "b6_review_workflow.tsv", "b6_amendment_matrix.tsv"} else "PRESERVED_WITH_ADOPTED_OVERLAYS"})
            source_paths[path.name] = path
    originals = {name: read_tsv(path) for name, path in sorted(source_paths.items()) if path.suffix == ".tsv"}
    ecology = originals["11_nto_candidate_receptors_precontract_v2.tsv"]
    l9a = originals["13_l9a_pre_g0_resource_landscape_v2.tsv"]
    literature = []
    for name in ("10_l1_l2_l3_l8_ecological_evidence_v2.tsv", "16_l4_b3_methodological_evidence_v2.tsv", "b5_concern_methodological_evidence.tsv"):
        for index, row in enumerate(originals[name], 1):
            source_id = row.get("evidence_id", row.get("unit_id", row.get("source_id", f"B5_{index:03}")))
            if name.startswith("b5_"):
                source_id = f"B5_{source_id}"
            literature.append({
                "source_id": source_id, "source_document": name,
                "citation": row.get("citation", "NOT_APPLICABLE"), "doi_or_url": row.get("doi_or_url", row.get("doi", "NOT_APPLICABLE")),
                **{key: row.get(key, "NOT_APPLICABLE") for key in ("location", "organism", "life_stage", "exposure_pathway", "ecological_role", "host_or_prey_relationship", "resource_or_sugar_use", "finding", "limitations", "transferability_to_project_geography", "evidence_status")},
                "scenario_id": SCENARIO if name.startswith("10_") else "",
                "original_record": json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            })
    literature.sort(key=lambda r: r["source_id"])
    panel, exposure, gaps = [], [], []
    def gap(gap_id, category, organism_id, gap_type, reason, scenario_id=""):
        gaps.append({"gap_id": gap_id, "category": category, "organism_id": organism_id, "scenario_id": scenario_id, "gap_type": gap_type, "status": "UNRESOLVED", "reason": reason, "computational_assessment_claim": "NONE", "resolution_stage": "CP1_OR_LATER_AUTHORIZED_AMENDMENT", "contract_reference": ""})
    for row in ecology:
        name = row["organism"]
        if name.startswith("Soil or residue"):
            continue
        if name.startswith("Coccinellidae:"):
            gap("COCCINELLIDAE_NOMINAL_RECEPTOR_PENDING", "PREDATOR", "", "OPTIONAL_NOMINAL_RECEPTOR_UNRESOLVED", row["main_limitation"])
            continue
        scientific_name = "Apis mellifera" if name.startswith("Apis mellifera") else name
        organism_id = scientific_name.upper().replace(" ", "_")
        metadata = [r for r in l9a if r["organism_id_or_name"] == organism_id and r["preliminary_computational_assessability"] in {"ASSESSABLE", "PARTIALLY_ASSESSABLE", "UNASSESSABLE"}]
        values = {r["preliminary_computational_assessability"] for r in metadata}
        require(len(values) <= 1, f"conflicting L9a assessability: {organism_id}")
        assessability = next(iter(values), "")
        tier = row["proposed_panel_tier"].removesuffix("_PROPOSED")
        overlay = "BASELINE_B2_ADOPTED"
        if tier == "UNRESOLVED":
            tier, overlay = "CONDITIONAL", "BASELINE_UNRESOLVED_RETAINED_CONDITIONALLY"
        if organism_id == "TRIGONA_SPINIPES":
            tier, overlay = "CONDITIONAL", "CLOSURE_E_OPTIONAL"
        if organism_id == "APIS_MELLIFERA":
            tier, overlay = "CORE", "CLOSURE_E_POLLINATOR_REPRESENTED"
        justification_status = "LITERATURE_BACKED" if row["justification_status"] == "LITERATURE_BACKED" else "SOURCE_REVIEW_PENDING"
        if tier == "EXTENDED":
            justification_status = row["justification_status"]
        if organism_id == "APIS_MELLIFERA":
            justification_status = "PROJECT_RATIFIED_TRANSFERABILITY_WITH_SOURCE_LIMITATIONS"
        panel.append({
            "organism_id": organism_id, "scientific_name": scientific_name,
            "taxid": row["taxid_if_known"] if row["taxid_if_known"].isdigit() else "",
            "taxid_status": "BASELINE_RESOLVED_NOT_REQUERIED" if row["taxid_if_known"].isdigit() else "UNRESOLVED",
            "receptor_class": row["receptor_class"], "ecological_functions": multi(row["ecological_functions"]),
            "phylogenetic_context": row["phylogenetic_context"], "ecological_panel_tier": tier,
            "reference_role": "ECOLOGICAL_NTO", "surrogate_status": "NOT_A_SURROGATE", "surrogate_for_organism_id": "",
            "preliminary_computational_assessability": assessability, "preliminary_assessability_source": "L9a_METADATA" if assessability else "L9a_SCOPE_GAP_REGISTER",
            "preliminary_assessability_status": "DOCUMENTED_IN_L9A" if assessability else "L9A_METADATA_NOT_ASSESSED",
            "justification": row["justification"], "justification_status": justification_status,
            "historical_justification_status": row["justification_status"], "historical_panel_tier": row["proposed_panel_tier"],
            "applicability_overlay": overlay, "source_ids": multi(row["source_ids"]),
            "limitations": row["main_limitation"],
            "added_value_rationale": EXTENDED_VALUES[organism_id] if tier == "EXTENDED" else "NONE",
            "added_value_registration_status": "PROJECT_RATIFIED_CLASSIFICATION_WITH_SOURCE_LIMITATIONS" if tier == "EXTENDED" else "NOT_APPLICABLE",
        })
        exposure.append({
            "organism_id": organism_id, "scenario_id": SCENARIO,
            "exposure_pathways": "NONE" if row["exposure_pathways_supported"] == "NOT_APPLICABLE_IN_THIS_GEOGRAPHY" else multi(row["exposure_pathways_supported"]),
            "external_exposure_plausibility": row["external_exposure_plausibility"], "internal_dsrna_exposure": "UNKNOWN",
            "source_ids": multi(row["source_ids"]), "rationale": row["justification"],
            "limitations": row["main_limitation"], "exposure_status": "PLANNING_PLAUSIBILITY_ONLY",
            "historical_exposure_pathways": row["exposure_pathways_supported"],
        })
        if not assessability:
            gap(f"L9A_{organism_id}", "COMPUTATIONAL_METADATA", organism_id, "L9A_METADATA_NOT_ASSESSED", "No species-specific preliminary assessment in the audited L9a. Empty assessability is missing metadata, not demonstrated resource absence.")
            gaps[-1]["contract_reference"] = complement["l9a_gap_contract"]["contract_id"]
            gaps[-1]["resolution_stage"] = "CP0_GAP_ADMISSION_RATIFIED_RESOURCE_RESOLUTION_BEFORE_CP1_USE_AND_FREEZE"
        elif assessability != "ASSESSABLE":
            gap(f"RESOURCE_{organism_id}", "COMPUTATIONAL_COVERAGE", organism_id, "PRELIMINARY_RESOURCE_COVERAGE_GAP", " | ".join(r["known_limitations"] for r in metadata))
        if not row["taxid_if_known"].isdigit():
            gap(f"TAXID_{organism_id}", "TAXONOMY", organism_id, "TAXID_UNRESOLVED", "No certified species taxid in the supplied baseline. Resolution remains future, before resource freeze.")
            gaps[-1]["contract_reference"] = complement["l9a_gap_contract"]["contract_id"]
            gaps[-1]["resolution_stage"] = "SPECIES_TAXONOMY_BEFORE_CP1_RESOURCE_USE_AND_FREEZE"
    gap(SOIL_GAP, "SOIL_OR_RESIDUE", "", SOIL_GAP, "Closure C.2: UNKNOWN activates PLAN D.5. No nominal species, taxid, organism_id or resource is assigned.", SCENARIO)
    gap("PARASITOID_PARANA_COVERAGE_GAP", "PARASITOID", "", "REGIONAL_ECOLOGICAL_COVERAGE_GAP", "Brazilian parasitoid evidence is preserved. Regional occurrence in Parana remains unresolved.", SCENARIO)
    gap("PHYLOGENETIC_COVERAGE_LIMITATION", "CLOSE_NON_TARGET_CICADELLIDAE", "", "PHYLOGENETIC_COVERAGE_LIMITATION", "SAME_FAMILY is represented. No justified same-genus regional non-target is assigned.", SCENARIO)
    landscape = [{"landscape_row_id": f"L9A_{i:03}", "organism_id": row["organism_id_or_name"], **row, "resource_status": "METADATA_ONLY_NOT_SELECTED_NOT_FROZEN"} for i, row in enumerate(l9a, 1)]
    scenario = {"scenario_id": SCENARIO, "scenario_status": "CONDITIONAL_ALTERNATIVE", "application_route": "UNKNOWN", "formulation_state": "UNKNOWN", "reference_use_geography": "Paraná, Brasil — sistemas de cultivo comercial de milho (Zea mays)", "planning_phenological_window": "EMERGENCE_THROUGH_HARVEST_AND_ASSOCIATED_RESIDUE_PERIOD", "spatial_domain": "COMMERCIAL_MAIZE_SYSTEM_IN_PARANA_WITH_JUSTIFIED_OR_UNKNOWN_RELEVANT_PATHWAYS", "foliar_bacillus_hypothesis": "PROJECT_SUPPLIED_WORKING_HYPOTHESIS_ONLY", "soil_or_residue_external_plausibility": "UNKNOWN", "aquatic_conditional": "NOT_ACTIVATED_BY_SOIL_UNKNOWN_ALONE", "scenario_provenance": "NB04_PREAPPROVAL_CLOSURE_C_RATIFIED", **{k: "UNKNOWN" for k in ("application_months", "application_dates", "crop_season", "application_window", "application_duration", "residue_duration", "application_frequency", "treated_area_ha", "dose")}}
    documentary = {
        "schema_version": 1, "normative_documents": sorted(documents, key=lambda d: d["document_id"]),
        "adoption_authority": "PROJECT_RESPONSIBLE_EXPLICIT_DECLARATION_2026_10_14",
        "initial_state": {"branch": "feat/nb04-cp0", "head": INITIAL_HEAD, "dirty": False, "snapshot": SNAPSHOT, "snapshot_sha256": SNAPSHOT_HASH, "snapshot_checks_pass": 31},
        "original_table_records": originals,
        "materialized_tables": {"literature_register": literature, "resource_landscape": landscape, "coverage_gaps": sorted(gaps, key=lambda r: r["gap_id"])},
        "complementary_contract": {"contract_id": CONTRACT_ID, "file": CONTRACT_PATH, "sha256": digest(root / CONTRACT_PATH), "authority": AUTHORITY_STATUS},
        "null_contract": {"preliminary_assessability": "Empty only under the ratified named L9a exception, with scope-gap provenance. No scientific resource absence inferred.", "taxid": "Empty with TAXID_UNRESOLVED gap", "source_selection": "Empty for REFERENCE_SET"},
    }
    dump(root, DOC_INPUT, json_bytes(documentary))
    # Pin independently certified source hashes, not merely observed replacements.
    artifacts = {}
    queries = {}
    d2_commit = "74b9d6584690b95d4c8175b7d487940f2372bda6"
    bc_commit = "9ca3e0903e9bee10c0708fde95241b7fa671591a"
    bench_commit = "099f751780283fecbc63da177c113aec9f6d60d5"
    for query_id, (_, role, _, _, _) in QUERY_SPEC.items():
        if query_id.startswith("D2"):
            sequence_path = "data/reference/nb02_dsrnase2_candidate_regions.fasta"
            selection_path = "data/reference/nb02_dsrnase2_candidate_regions.tsv" if role == "CANDIDATE" else ""
            manifest_path = "results/bioinformatics/nb02/cp5/run_manifest.json"
            commit, proof, kind, stage = d2_commit, sequence_path, "VERSIONED_BLOB", "NB02_CP5"
        elif role == "CANDIDATE":
            sequence_path, selection_path = "results/bioinformatics/nb03/cp4b/shortlist.fasta", "results/bioinformatics/nb03/cp4b/shortlist.tsv"
            manifest_path = "results/bioinformatics/nb03/cp4b/run_manifest.json"
            commit, proof, kind, stage = bc_commit, "src/workstreams/bioinformatics/runs/2026-10-08_nb03-cp4b-manual-review-resolution.md", "VERSIONED_HASH_RECORD", "NB03_CP4B"
        else:
            sequence_path, selection_path = "results/bioinformatics/nb03/cp0/benchmark_reconstruction.json", ""
            manifest_path = "results/bioinformatics/nb03/cp0/run_manifest.json"
            commit, proof, kind, stage = bench_commit, "data/reference/nb01_bicc_operational_reference.json", "VERSIONED_HASH_RECORD", "NB03_CP0_RECONSTRUCTION_CERTIFIED_BY_CP1_PIN"
        manifest_data = json.loads((root / manifest_path).read_text("utf-8"))
        for path in filter(None, (sequence_path, selection_path)):
            expected = manifest_data["outputs_sha256"].get(path, manifest_data["outputs_sha256"].get(Path(path).name))
            require(expected is not None, f"source absent from upstream manifest: {path}")
            require(digest(root / path, normalized=True) == expected, f"upstream artifact mismatch: {path}")
            artifacts[path] = {"sha256": expected, "hash_mode": "LF_NORMALIZED"}
        artifacts[manifest_path] = {"sha256": digest(root / manifest_path), "hash_mode": "RAW_BYTES"}
        queries[query_id] = {"sequence_source_stage": stage, "sequence_source_artifact": sequence_path, "sequence_format": "FASTA" if sequence_path.endswith(".fasta") else "BENCHMARK_JSON", "selection_source_stage": stage if selection_path else "NOT_APPLICABLE", "selection_source_artifact": selection_path, "source_manifest_artifact": manifest_path, "upstream_repository_commit": commit, "certification_artifact": proof, "certification_artifact_sha256_lf": sha256(git(root, "show", f"{commit}:{proof}").replace(b"\r\n", b"\n")), "certification_kind": kind, "notes": "Certified sequence and selection are separate. Experimental protocol claims remain PROJECT_PROVIDED_NOT_AGENT_VERIFIED. No efficacy or ecological safety inference."}
    pins = {
        "DSRNASE2": {"artifact": "data/reference/nb01_dsrnase2_operational_reference.json", "sha256_lf": "4ea481fb747f91ca22fc55fda2ab684884952650ad1cfa31cf3fe268011c9edb", "certifying_commit": d2_commit},
        "BICC": {"artifact": "data/reference/nb01_bicc_operational_reference.json", "sha256_lf": "5d4b2b24ec56aebcb55c73f6d23e719bab8d2506cdfa49c225453d93707bd21c", "certifying_commit": bench_commit},
    }
    dump(root, PROVENANCE, json_bytes({"schema_version": 1, "artifacts": artifacts, "queries": queries, "reference_pins": pins, "manifest_identity_scope": "Observed manifest bytes, output bindings independently checked against the versioned certifying record or blob"}))
    dump(root, "config/nb04_nto_panel.tsv", tsv_bytes(sorted(panel, key=lambda r: r["organism_id"])))
    dump(root, "config/nb04_exposure_scenarios.tsv", tsv_bytes([scenario]))
    dump(root, "config/nb04_receptor_exposure.tsv", tsv_bytes(sorted(exposure, key=lambda r: (r["organism_id"], r["scenario_id"])) ))
    policy = policy_record(root, originals)
    dump(root, "config/nb04_nto_policy.yaml", yaml.safe_dump(policy, allow_unicode=True, sort_keys=True).encode("utf-8"))


def policy_record(root: Path, originals: dict) -> dict:
    arms = []
    definitions = [
        ("EXACT_CANONICAL", "EXACT", "CANONICAL", "NB04_EXACT_K19_K21_BOTH_ACGT_V1", "NOT_APPLICABLE"),
        ("NEAR_MATCH_CANONICAL", "NEAR_MATCH", "CANONICAL", "NOT_APPLICABLE", "NOT_APPLICABLE"),
        ("LOCAL_ALIGNMENT_CANONICAL", "LOCAL_ALIGNMENT", "CANONICAL", "NOT_APPLICABLE", "NOT_APPLICABLE"),
        ("NEAR_MATCH_K21_H1", "NEAR_MATCH", "SENSITIVITY", "NB04_NEAR_K21_H1_BOTH_ACGT_V1", "NB04_LITERAL_HAMMING_UNGAPPED_V1"),
        ("NEAR_MATCH_K21_H2", "NEAR_MATCH", "SENSITIVITY", "NB04_NEAR_K21_H2_BOTH_ACGT_V1", "NB04_LITERAL_HAMMING_UNGAPPED_V1"),
        ("EXACT_K16_SENSITIVITY", "EXACT", "SENSITIVITY", "NB04_EXACT_K16_BOTH_ACGT_V1", "NOT_APPLICABLE"),
    ]
    for name, modality, role, space, model in definitions:
        required = role == "CANONICAL" and modality != "NEAR_MATCH"
        arms.append({"analysis_arm_id": name, "modality": modality, "analysis_role": role, "modality_requirement_status": "REQUIRED" if required else "NOT_REQUIRED_BY_FROZEN_POLICY", "formal_search_space_id": space, "pairing_model_id": model, "search_configuration_id": "DEFERRED_TO_G1" if modality == "LOCAL_ALIGNMENT" else "NOT_APPLICABLE", "search_calibration_id": "DEFERRED_TO_G1" if modality == "LOCAL_ALIGNMENT" else "NOT_APPLICABLE", "execution": "REQUIRED_AFTER_APPLICABLE_GATES" if required else "OPTIONAL" if role == "SENSITIVITY" else "NOT_REQUIRED", "execution_required_for_completion": required, "technical_state": "NOT_RUN", "evidence_state": "NOT_EVALUATED", "biological_decision_role": False, "purpose": "DESCRIPTIVE_SENSITIVITY" if role == "SENSITIVITY" else "CANONICAL_SEQUENCE_EVIDENCE", "declaration_requirement": "DECLARED_PRE_G0", "parameterization_requirement": "G1_AFTER_CALIBRATION" if modality == "LOCAL_ALIGNMENT" else "FULLY_PARAMETERIZED_PRE_G0" if space != "NOT_APPLICABLE" else "NOT_APPLICABLE", "selection_rule_id": None if modality == "LOCAL_ALIGNMENT" else "NOT_APPLICABLE", "validation_requirement": "B4_APPLICABLE_CALIBRATION_AND_EXECUTION_INTEGRITY" if modality == "LOCAL_ALIGNMENT" else "COMPLETE_WITHIN_DECLARED_FORMAL_SPACE" if space != "NOT_APPLICABLE" else "NOT_APPLICABLE"})
    spaces = []
    for identifier, ks, differences in [("NB04_EXACT_K19_K21_BOTH_ACGT_V1", [19, 21], 0), ("NB04_NEAR_K21_H1_BOTH_ACGT_V1", [21], 1), ("NB04_NEAR_K21_H2_BOTH_ACGT_V1", [21], 2), ("NB04_EXACT_K16_BOTH_ACGT_V1", [16], 0)]:
        spaces.append({"formal_search_space_id": identifier, "k": ks, "exact_difference_count": differences, "orientation": "PLUS_AND_REVERSE_COMPLEMENT", "alphabet": "ACGT", "indels": False, "difference_positions": "ALL_POSITIONS_LITERAL_UNIT_COST", "seed_model": "NOT_APPLICABLE", "g_u_discount": False, "subject_normalization": "UPPERCASE_U_TO_T_ON_DERIVED_ONLY", "ambiguity_policy": "EXCLUDE_NON_ACGT_WINDOWS_WITH_DENOMINATORS", "record_boundaries": "NEVER_CROSSED", "complexity_filter": "NONE", "occurrence_cap": None, "palindrome_rule": "COLLAPSE_IDENTICAL_ORIENTED_WORDS_PRESERVE_MAPPING", "biological_decision_role": False, "parameter_role": "SEARCH_PARAMETER"})
    parameters = []
    for row in originals["04_parameter_classification_v2.tsv"]:
        value = "METHODOLOGICAL_CONTRACT_APPROVAL_DECLARED" if row["parameter"] == "contract_proposal_status" else row["value_or_rule"]
        parameters.append({"parameter_id": "B3_" + row["parameter"], "value_or_rule": value, "parameter_role": row["parameter_role"], "biological_decision_role": False, "source_document": "04_parameter_classification_v2.tsv", "historical_record_preserved": True})
    for row in originals["08_b4_calibration_parameter_matrix_v2_1.tsv"]:
        parameters.append({"parameter_id": "B4_" + row["parameter_id"], "value_or_rule": row["candidate_design_space"], "parameter_role": row["parameter_role"], "biological_decision_role": False, "source_document": "08_b4_calibration_parameter_matrix_v2_1.tsv", "historical_record_preserved": True})
    policy = {
        "schema_version": 1, "policy_id": "NB04_NTO_SEQUENCE_SPECIFICITY_POLICY_V1", "version": "1.0.0",
        "states": {"METHODOLOGICAL_CONTRACT_APPROVAL": "DECLARED", "G0_PASS": "NOT_DECLARED", "CP1": "NOT_STARTED", "informative_calibration": "NOT_EXECUTED"},
        "documentary_inputs_sha256": digest(root / DOC_INPUT), "upstream_provenance_sha256": digest(root / PROVENANCE),
        "reference_use_geography": "Paraná, Brasil — sistemas de cultivo comercial de milho (Zea mays)",
        "canonical_k": [19, 21], "canonical_k_role": "FORMAL_SEARCH_SPACE_PROJECT_CONVENTION", "fallback_policy": "A_SELECTED_PRE_G0",
        "near_match_methodological_finding": "NEAR_MATCH_PARAMETERIZATION_NOT_JUSTIFIED", "pairing_model": {"pairing_model_id": "NB04_LITERAL_HAMMING_UNGAPPED_V1", "biological_validation": "NOT_ESTABLISHED", "scope": "LITERAL_HAMMING_UNGAPPED_UNIT_COST"},
        "analysis_arms": arms, "formal_search_spaces": spaces, "cp3_sensitivity_arms": [], "parameters": parameters,
        "calibration": {"design": "B4_v2.1.2_WITH_A1_AND_RATIFIED_CLOSURE", "selection_rule_id": None, "selection_rule_status": "UNRESOLVED_CONTRACT_REFERENCE", "calibration_inconclusive_definition": None, "complementary_record_requirement": "Selection rule, multiple admissible configuration handling, and operational CALIBRATION_INCONCLUSIVE distinct from FAILED and NOT_TESTED. Independent audit and project ratification required before G0 and corresponding calibration.", "selection_rule": "PLAN G.7c requires a pre-registered selection rule and CALIBRATION_INCONCLUSIVE criterion. Supplied B4 defines admissibility obligations but does not identify the concrete selection rule. Exact ratified reference requested. No selection criterion is created by CP0.", "numeric_coordinate_tolerances": None, "informative_execution_requires_prior_complete_freeze": True, "freeze_fields": ["fixture_set_id", "fixture_role", "planted_instance_id", "full_base_difference_gap_pattern", "expected_coordinates_and_orientation", "candidate_configuration_id", "candidate_version", "complete_effective_parameters_and_defaults", "pinned_build", "per_end_numeric_tolerance_nt", "independent_technical_justification", "freeze_id", "freeze_version", "fixture_sha256", "configuration_sha256", "tolerance_record_sha256", "freeze_time_before_any_informative_execution"], "QA_B_blocks_configuration_freeze": True, "QA_H_blocks_configuration_freeze": False, "PC03_detection_class": "CHARACTERIZED_NOT_ASSERTED", "PC06_detection_class": "CHARACTERIZED_NOT_ASSERTED", "tolerance_parameter_role": "QA_ACCEPTANCE_CRITERION", "biological_decision_role": False, "envelope_extrapolation_margin_bases": 0, "envelope_extrapolation_margin_records": 0, "envelope_geometry": "ONLY_ACTUALLY_TESTED_COMBINATIONS_AND_ARCHITECTURES_NO_AUTOMATIC_RECTANGLE", "qa_e_additional_permutations": 1, "qa_e_recipe": "CLOSURE_A.2_NB04_QAE_PERMUTATION_V1", "qa_f_shards": 2, "qa_f_partition": "CLOSURE_A.3_BALANCE_BASES_PRESERVE_WHOLE_RECORDS_CANONICAL_ORDER_TIE_FIRST", "qa_f1": "RECOVERY_WITHOUT_UNNORMALIZED_SET_EQUALITY", "qa_f2_normalization": "SEARCHSP_FROM_PINNED_BUILD_WHOLE_FIXTURE_REFERENCE_BEFORE_NORMALIZED_COMPARISON", "production_dbsize_searchsp": "NO_ARTIFICIAL_ADJUSTMENT", "warning_policy": "RELEVANT_WARNING_BLOCKS_QA_G_UNKNOWN_RELEVANCE_PENDING", "execution_preference": ["SINGLE_PASS_WITH_DECLARED_QA", "DETERMINISTIC_PARTITION_WHERE_REQUIRED", "TRUNCATION_UNRESOLVED"], "recipe_pc02_pc03_pc06": "NB04_SYNTHETIC_CASE_SHA256_ACGT_V1_CLOSURE_A.8", "fixture_status": "NOT_MATERIALIZED", "qa_status": "NOT_TESTED", "B4_8": "EXPLICIT_AUTHORIZATION_BEFORE_F01_TOY_HARNESS", "B4_9": "SCALE_DECISION_BEFORE_G1_F05_F06_CALIBRATION"},
        "resource_policy": {"landscape": "METADATA_ONLY_NOT_SELECTED_NOT_FROZEN", "eligibility_order": ["TRANSCRIPT_TIER", "ANNOTATED_CDS", "GENOME_COMPLEMENT_WITH_LIMITATIONS"], "barcode_only": "INADEQUATE_FOR_TARGET_RELEVANT_ABSENCE", "final_assessability_stage": "CP1_G1_SEPARATE_ARTIFACT", "missing_metadata": "NULL_WITH_EXPLICIT_GAP", "ecological_tier_independent_of_resource_availability": True},
        "decision_policy": {"scientific_disposition_assignment": "HUMAN_ONLY", "review_grain": "QUERY_X_CORE_ORGANISM", "canonical_evidence_grain": "QUERY_X_ORGANISM_X_RESOURCE_X_CANONICAL_MODALITY", "sensitivity_summary_grain": "QUERY_X_ORGANISM_X_RESOURCE_X_MODALITY_X_ANALYSIS_ARM_ID", "sensitivity_usability": "PER_ROW_AND_SCOPE_RUN_COMPLETE_AND_COMPLETE_WITHIN_DECLARED_FORMAL_SPACE", "plant_track": "SEPARATE_PLANT_CONTEXT_AND_DOSSIER_CLOSURE_B_B5_R09", "concern": "B5_R05_INDIVIDUALIZED_DOCUMENTED_RNA_RECOGNITION_HYPOTHESIS_AND_VALID_HUMAN_REVIEW", "qualified_negative_disposition": "B5_R16_ONLY_WITH_ASSESSED_SCOPE_AND_NO_BLOCKING_PENDING_MATTER", "no_sensitivity_substitution_for_canonical": True, "salience_model": "NO_SALIENCE_MODEL", "homology": "COMPUTATIONAL_EVIDENCE_WITHOUT_AUTOMATIC_BIOLOGICAL_IMPLICATION", "cp3_absence": "B4_SEVEN_CONDITIONS_CONJUNCTION_RUN_COMPLETE_ALONE_INSUFFICIENT", "scientific_dispositions": ["POTENTIAL_SPECIFICITY_CONCERN", "DETECTED_HOMOLOGY_WITHOUT_RESOLVED_BIOLOGICAL_IMPLICATION", "NO_SEQUENCE_SPECIFICITY_CONCERN_IDENTIFIED_WITHIN_ASSESSED_SCOPE", "UNRESOLVED"]},
        "governance": {"contract": "B6_GOVERNANCE_AMENDMENT_A1", "G0_external_qualified_distinct_human_review": "REQUIRED_BEFORE_CERTIFICATION", "preassigned_staffing_for_cp0": False},
        "serialization": {"multivalue": "N18_LITERAL_UNICODE_SORT_PIPE_NONE_EMPTY_UNKNOWN_ONLY_AUTHORIZED_AND_ALONE", "line_endings": "LF", "counts": "INTEGER", "ratios": "INTEGER_NUMERATOR_AND_DENOMINATOR", "volatile_metadata": "execution_metadata.json", "display_order_classification": "CANONICAL_DISPLAY_ORDER_ONLY"},
        "is_ranking": False,
    }
    complement = load_complement(root)
    policy["version"] = "1.1.0"
    policy["complementary_contract_id"] = CONTRACT_ID
    policy["complementary_contract_sha256"] = digest(root / CONTRACT_PATH)
    policy["l9a_gap_contract"] = complement["l9a_gap_contract"]
    calibration = policy["calibration"]
    calibration.update({
        "selection_rule_id": RULE_ID, "selection_rule_status": AUTHORITY_STATUS,
        "selection_rule": complement["selection_rule"],
        "calibration_inconclusive_definition": complement["calibration_inconclusive_definition"],
        "source_document_sha256": SOURCE_HASHES["NB04_CP0_COMPLEMENTARY_CONTRACT_PROPOSAL.md"],
        "complementary_record_requirement": "Ratification and independent audit completed for the pinned complementary contract. G0 remains pending external human review.",
    })
    for arm in policy["analysis_arms"]:
        if arm["modality"] == "LOCAL_ALIGNMENT":
            arm["selection_rule_id"] = RULE_ID
    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--amendments", type=Path, required=True)
    parser.add_argument("--b5", type=Path, required=True)
    parser.add_argument("--b6", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root.resolve(), args.package, args.amendments, args.b5, args.b6)


if __name__ == "__main__":
    main()
