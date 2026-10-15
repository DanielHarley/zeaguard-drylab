"""Ratified CP0 documentary contract, without executing calibration or searches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CONTRACT_PATH = "data/reference/nb04_cp0_complementary_contract.json"
CONTRACT_ID = "NB04_CP0_COMPLEMENTARY_CONTRACT_V1"
CONTRACT_SHA256 = "3a89cbbebc9a207e776d2225748bf703a26ab02de56cb4df5f1c31a1cb23e818"
RULE_ID = "NB04_TUNING_QA_CONFIG_HASH_ORDER_HOLDOUT_V1"
AUTHORITY_STATUS = "PROJECT_RATIFIED_AND_INDEPENDENT_AUDIT_COMPLETED"
SOURCE_HASHES = {
    "NB04_CP0_COMPLEMENTARY_CONTRACT_PROPOSAL.md": "617438b9bf5a0a4dd2e80fc832af288432060899e5f615384df3e306bb919c68",
    "NB04_CP0_COMPLEMENTARY_RATIFICATION_RECORD.md": "a0b3d81d2d94351663a758603470509c91d81d2fdf30e9519c3bf2bbc66d9232",
    "NB04_CP0_COMPLEMENTARY_INDEPENDENT_AUDIT.md": "277ac250c6f66a0ff0d451682f75b08d325a33bd58d7d476a374ff2c22581572",
}
EXTENDED_VALUES = {
    "ANAGRUS_BREVIPHRAGMA": "ADDS_PHYLOGENETIC_COVERAGE",
    "CHRYSOPERLA_EXTERNA": "ADDS_EXPOSURE_PATHWAY",
    "GONATOPUS_FLAVIPES": "ADDS_ECOLOGICAL_FUNCTION",
    "ORIUS_INSIDIOSUS": "ADDS_PHYLOGENETIC_COVERAGE",
    "PEREGRINUS_MAIDIS": "ADDS_PHYLOGENETIC_COVERAGE",
    "PSEUDOLIGOSITA_LONGIFRANGIATA": "ADDS_METHOD_REFERENCE",
    "PYROPHAGUS_TIGRINUS": "ADDS_PHYLOGENETIC_COVERAGE",
    "RHOPALOSIPHUM_MAIDIS": "ADDS_PHYLOGENETIC_COVERAGE",
    "TETRAGONISCA_ANGUSTULA": "ADDS_PHYLOGENETIC_COVERAGE",
}
L9A_GAP_IDS = frozenset({
    "ANAGRUS_BREVIPHRAGMA", "EXITIANUS_OBSCURINERVIS", "GONATOPUS_FLAVIPES",
    "PARACENTROBIA_SUBFLAVA", "PEREGRINUS_MAIDIS", "PSEUDOLIGOSITA_LONGIFRANGIATA",
    "PYROPHAGUS_TIGRINUS", "SOGATELLA_KOLOPHON", "TETRAGONISCA_ANGUSTULA", "TRIGONA_SPINIPES",
})
BLOCKING_QA = ["QA-A", "QA-B", "QA-C", "QA-D", "QA-E", "QA-F1", "QA-F2", "QA-G", "QA-I", "QA-J", "QA-K", "QA-L", "QA-M", "QA-N", "QA-P", "QA-Q"]


def validate_complement(contract: dict) -> None:
    def check(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"complementary contract: {message}")

    check(contract["schema_version"] == 1 and contract["contract_id"] == CONTRACT_ID, "identity")
    check(contract["authority_status"] == AUTHORITY_STATUS, "authority")
    documents = contract["source_documents"]
    check(len(documents) == 3 and {d["document_id"] for d in documents} == set(SOURCE_HASHES), "source scope")
    for document in documents:
        expected = SOURCE_HASHES[document["document_id"]]
        observed = hashlib.sha256(document["content"].encode("utf-8")).hexdigest()
        check(document["sha256"] == observed == expected, "source provenance mismatch")
    rule = contract["selection_rule"]
    check(rule["selection_rule_id"] == RULE_ID, "selection rule identity")
    check(rule["selection_inputs"] == "TUNING_ONLY", "validation cannot select")
    check(rule["candidate_set"] == "FINITE_COMPLETE_FROZEN_BEFORE_FIRST_INFORMATIVE_TUNING", "candidate freeze")
    check(rule["candidate_order"] == "LEX_ASCENDING_SHA256_CANONICAL_EFFECTIVE_TECHNICAL_PAYLOAD_PRE_TUNING", "order freeze")
    check(rule["order_excludes"] == ["free_name", "candidate_configuration_id", "notes", "timestamps", "local_paths", "discovery_order", "results", "observed_metrics"], "order cannot depend on labels or results")
    check(rule["order_may_change_after_results"] is False, "post-result order")
    check(rule["selection"] == "FIRST_TUNING_ELIGIBLE_IN_FROZEN_ORDER", "selection")
    check(rule["validation"] == "CONFIRM_PRESELECTED_CONFIGURATION", "validation role")
    check(rule["validation_used_for_selection"] is False and rule["validation_can_choose_substitute"] is False, "validation leakage")
    check(rule["later_campaign_requires_unused_validation"] is True, "reused validation")
    check(rule["blocking_qa"] == BLOCKING_QA and rule["characterization_qa"] == ["QA-H", "QA-O", "QA-R"], "QA roles")
    check(rule["characterization_used_as_new_threshold_or_weight"] is False and rule["performance_threshold"] is None, "characterization threshold")
    check(rule["biological_decision_role"] is False, "biological role")
    check(rule["qa_p_timing"] == "STRUCTURAL_DISJOINTNESS_PRE_SELECTION_AND_FINAL_VALIDATION_EVIDENCE_PRE_G1", "QA-P phase")
    check(rule["numeric_parameter_selection_stage"] == "AUTHORIZED_CP1_G1_AFTER_G0", "numeric selection phase")
    result = contract["calibration_inconclusive_definition"]
    check(result["result_vocabulary"] == ["CHARACTERIZED", "CALIBRATION_INCONCLUSIVE", "FAILED"], "result vocabulary")
    check(result["not_tested_added_to_result_vocabulary"] is False, "not-tested is QA")
    check(result["not_executed"] == "EXECUTION_OR_QA_STATE_ONLY_WITH_NO_FABRICATED_CALIBRATION_RESULT", "non-execution")
    check(result["same_result_precedence"] == "DEMONSTRATED_BLOCKING_FAILURE_BEFORE_RESIDUAL_INSUFFICIENCY", "failure precedence")
    check(result["no_executions"] == "NO_CALIBRATION_RESULT", "non-executed campaign")
    check(result["all_tuning_candidates_demonstrably_failed"] == "FAILED" and result["partially_evaluated_tuning_campaign"] == "CALIBRATION_INCONCLUSIVE", "campaign outcomes")
    check(result["multiple_tuning_eligible"] == "SELECT_FIRST_FROZEN_ORDER_NOT_INCONCLUSIVE", "multiple eligible candidates")
    check(result["selected_validation_failure"] == "FAILED_ATTEMPT_NO_SUBSTITUTE_FROM_SAME_VALIDATION", "holdout failure")
    check(result["selected_validation_insufficient"] == "CALIBRATION_INCONCLUSIVE" and result["selected_validation_complete"] == "CHARACTERIZED_PENDING_EXISTING_G1_REVIEW_REQUIREMENTS", "holdout outcome")
    check(contract["extended_classifications"] == EXTENDED_VALUES, "nominal D.6 classes")
    gap = contract["l9a_gap_contract"]
    check(gap["contract_id"] == "NB04_L9A_NAMED_RECEPTOR_GAP_CONTRACT_V1", "L9a identity")
    check(len(gap["allowed_organism_ids"]) == 10 and set(gap["allowed_organism_ids"]) == L9A_GAP_IDS, "L9a scope")
    check(set(gap["core_organism_ids"]) == {"EXITIANUS_OBSCURINERVIS", "PARACENTROBIA_SUBFLAVA"}, "CORE scope")
    check(gap["scientific_value_vocabulary"] == ["ASSESSABLE", "PARTIALLY_ASSESSABLE", "UNASSESSABLE"], "scientific vocabulary")
    check(gap["gap_source"] == "L9a_SCOPE_GAP_REGISTER" and gap["assessed_source"] == "L9a_METADATA", "gap provenance")
    check(gap["gap_status"] == gap["gap_type"] == "L9A_METADATA_NOT_ASSESSED", "gap status")
    check(gap["empty_tsv_and_null_json_mean_unassessed"] is True, "unassessed semantics")
    check(gap["final_assessment"] == "CP1_G1_SEPARATE_ARTIFACT_PRESERVING_G0_PANEL", "final assessment phase")
    check(gap["species_taxonomy_required_before_resource_use_and_freeze"] is True and gap["genus_resource_or_taxid_does_not_resolve_species"] is True, "species identity")
    check(all(value is True for value in contract["scientific_preservation"].values()), "scientific preservation")


def load_complement(root: Path | None = None) -> dict:
    root = Path(__file__).resolve().parents[2] if root is None else root
    raw = (root / CONTRACT_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("complementary contract: source artifact provenance mismatch")
    contract = json.loads(raw.decode("utf-8"))
    validate_complement(contract)
    return contract
