"""CP0 contract validation. No search, calibration or scientific adjudication."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from zeaguard.nb04_complement import (
    AUTHORITY_STATUS, CONTRACT_ID, CONTRACT_PATH, EXTENDED_VALUES, L9A_GAP_IDS,
    RULE_ID, SOURCE_HASHES, load_complement, validate_complement,
)
from zeaguard.nb04_serialization import parse_multivalue, validate_multivalue


class CP0ContractError(ValueError):
    """A CP0 input fails its declared contract."""


FUNCTIONS = frozenset({
    "HOST_PLANT", "POLLINATOR", "PARASITOID", "PREDATOR", "HERBIVORE_NON_TARGET",
    "DETRITIVORE", "OTHER_ASSOCIATED", "REFERENCE_ONLY",
})
PATHWAYS = frozenset({
    "DIRECT_CONTACT", "PLANT_INGESTION", "PREY_MEDIATED", "PARASITOID_HOST_MEDIATED",
    "SOIL_OR_RESIDUE", "OTHER", "UNKNOWN",
})
TIERS = {"CORE", "EXTENDED", "CONDITIONAL", "EXCLUDED_WITH_RATIONALE"}
ASSESSABILITY = {"ASSESSABLE", "PARTIALLY_ASSESSABLE", "UNASSESSABLE"}
PLAUSIBILITY = {"PLAUSIBLE", "LOW_PLAUSIBILITY", "NOT_PLAUSIBLE", "UNKNOWN"}
SCENARIO = "NB04_N2_CONSERVATIVE_ENVELOPE_V1"
SOIL_GAP = "SOIL_OR_RESIDUE_RECEPTOR_UNSPECIFIED_UNDER_CONSERVATIVE_ENVELOPE"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CP0ContractError(message)


def load_policy(root: Path) -> dict:
    policy = yaml.safe_load((root / "config/nb04_nto_policy.yaml").read_text("utf-8"))
    schema = json.loads((root / "config/nb04_nto_policy.schema.json").read_text("utf-8"))
    import hashlib
    require(hashlib.sha256((root / CONTRACT_PATH).read_bytes()).hexdigest() == policy["complementary_contract_sha256"], "complementary source artifact mismatch")
    validate_policy(policy, schema, load_complement(root))
    return policy


def validate_policy(policy: dict, schema: dict, complement: dict | None = None) -> None:
    try:
        jsonschema.Draft202012Validator(schema).validate(policy)
    except jsonschema.ValidationError as exc:
        raise CP0ContractError(f"policy schema: {exc.message}") from exc
    complement = load_complement() if complement is None else complement
    try:
        validate_complement(complement)
    except (ValueError, KeyError, TypeError) as exc:
        raise CP0ContractError(str(exc)) from exc
    require(policy["complementary_contract_id"] == CONTRACT_ID, "complementary identity")
    require(policy["l9a_gap_contract"] == complement["l9a_gap_contract"], "L9a exception changed")
    require(policy["canonical_k"] == [19, 21], "canonical_k diverges from adopted B3")
    require(policy["fallback_policy"] == "A_SELECTED_PRE_G0", "fallback diverges from B3")
    require(policy["cp3_sensitivity_arms"] == [], "closure declares no CP3 sensitivity arm")
    require(policy["is_ranking"] is False, "CP0 display order cannot be a ranking")
    require(policy["states"] == {
        "METHODOLOGICAL_CONTRACT_APPROVAL": "DECLARED",
        "G0_PASS": "NOT_DECLARED", "CP1": "NOT_STARTED",
        "informative_calibration": "NOT_EXECUTED",
    }, "phase boundary violated")
    expected = {
        "EXACT_CANONICAL": ("EXACT", "CANONICAL", "REQUIRED", "NB04_EXACT_K19_K21_BOTH_ACGT_V1", "NOT_APPLICABLE"),
        "NEAR_MATCH_CANONICAL": ("NEAR_MATCH", "CANONICAL", "NOT_REQUIRED_BY_FROZEN_POLICY", "NOT_APPLICABLE", "NOT_APPLICABLE"),
        "LOCAL_ALIGNMENT_CANONICAL": ("LOCAL_ALIGNMENT", "CANONICAL", "REQUIRED", "NOT_APPLICABLE", "NOT_APPLICABLE"),
        "NEAR_MATCH_K21_H1": ("NEAR_MATCH", "SENSITIVITY", "NOT_REQUIRED_BY_FROZEN_POLICY", "NB04_NEAR_K21_H1_BOTH_ACGT_V1", "NB04_LITERAL_HAMMING_UNGAPPED_V1"),
        "NEAR_MATCH_K21_H2": ("NEAR_MATCH", "SENSITIVITY", "NOT_REQUIRED_BY_FROZEN_POLICY", "NB04_NEAR_K21_H2_BOTH_ACGT_V1", "NB04_LITERAL_HAMMING_UNGAPPED_V1"),
        "EXACT_K16_SENSITIVITY": ("EXACT", "SENSITIVITY", "NOT_REQUIRED_BY_FROZEN_POLICY", "NB04_EXACT_K16_BOTH_ACGT_V1", "NOT_APPLICABLE"),
    }
    arms = policy["analysis_arms"]
    require(len(arms) == len(expected) and {a["analysis_arm_id"] for a in arms} == set(expected), "analysis arm scope")
    spaces = {s["formal_search_space_id"]: s for s in policy["formal_search_spaces"]}
    require(len(spaces) == 4, "formal search space cardinality")
    for arm in arms:
        key = arm["analysis_arm_id"]
        actual = tuple(arm[k] for k in ("modality", "analysis_role", "modality_requirement_status", "formal_search_space_id", "pairing_model_id"))
        require(actual == expected[key], f"modality/identifier contract: {key}")
        require(arm["technical_state"] == "NOT_RUN" and arm["evidence_state"] == "NOT_EVALUATED", "CP0 contains execution evidence")
        if arm["analysis_role"] == "SENSITIVITY":
            require(arm["execution_required_for_completion"] is False and arm["execution"] == "OPTIONAL", "sensitivity cannot gate completion")
        if arm["modality"] in {"EXACT", "NEAR_MATCH"}:
            require(arm["search_configuration_id"] == arm["search_calibration_id"] == "NOT_APPLICABLE", "CP2 cannot resolve G1 identifiers")
            if arm["formal_search_space_id"] != "NOT_APPLICABLE":
                require(arm["formal_search_space_id"] in spaces, "orphan formal space")
        else:
            require(arm["search_configuration_id"] == arm["search_calibration_id"] == "DEFERRED_TO_G1", "CP3 parameters belong to G1")
            require(arm["selection_rule_id"] == RULE_ID, "CP3 selection rule is not ratified")
    space_expected = {
        "NB04_EXACT_K19_K21_BOTH_ACGT_V1": ([19, 21], 0),
        "NB04_EXACT_K16_BOTH_ACGT_V1": ([16], 0),
        "NB04_NEAR_K21_H1_BOTH_ACGT_V1": ([21], 1),
        "NB04_NEAR_K21_H2_BOTH_ACGT_V1": ([21], 2),
    }
    require(set(spaces) == set(space_expected), "formal space identity")
    for key, (ks, differences) in space_expected.items():
        space = spaces[key]
        require(space["k"] == ks and space["exact_difference_count"] == differences, "formal parameters diverge from B3")
        require(space["orientation"] == "PLUS_AND_REVERSE_COMPLEMENT" and space["indels"] is False, "formal orientation/gap contract")
        require(space["alphabet"] == "ACGT" and space["occurrence_cap"] is None, "formal alphabet/cap contract")
    for parameter in policy["parameters"]:
        require(parameter["biological_decision_role"] is False, "biological parameter role forbidden")
        require(parameter["parameter_role"] in {"SEARCH_PARAMETER", "COMPUTATIONAL_REPORTING_LIMIT", "QA_ACCEPTANCE_CRITERION", "RESOURCE_CONSTRAINT", "DISPLAY_PARAMETER"}, "parameter role is not admissible")
    calibration = policy["calibration"]
    require(calibration["selection_rule_id"] == RULE_ID, "selection rule identity")
    require(calibration["selection_rule_status"] == AUTHORITY_STATUS, "selection authority missing")
    require(calibration["source_document_sha256"] == SOURCE_HASHES["NB04_CP0_COMPLEMENTARY_CONTRACT_PROPOSAL.md"], "selection source identity")
    require(calibration["selection_rule"] == complement["selection_rule"], "selection differs from ratified contract")
    require(calibration["calibration_inconclusive_definition"] == complement["calibration_inconclusive_definition"], "inconclusive definition differs from ratified contract")
    require(calibration["numeric_coordinate_tolerances"] is None, "B4-12 values are future")
    require(calibration["informative_execution_requires_prior_complete_freeze"] is True, "B4 A1 freeze obligation missing")
    require(calibration["QA_B_blocks_configuration_freeze"] is True and calibration["QA_H_blocks_configuration_freeze"] is False, "QA-B/QA-H roles")
    require(calibration["PC03_detection_class"] == calibration["PC06_detection_class"] == "CHARACTERIZED_NOT_ASSERTED", "characterization promoted to assertion")
    require(calibration["envelope_extrapolation_margin_bases"] == calibration["envelope_extrapolation_margin_records"] == 0, "closure forbids extrapolation margin")
    require(policy["decision_policy"]["scientific_disposition_assignment"] == "HUMAN_ONLY", "automatic scientific decision forbidden")


def unique(rows: list[dict], keys: tuple[str, ...], label: str) -> set[tuple]:
    values = [tuple(row[k] for k in keys) for row in rows]
    require(len(values) == len(set(values)), f"duplicate {label}")
    return set(values)


def validate_tables(panel: list[dict], scenarios: list[dict], exposure: list[dict],
                    literature: list[dict], landscape: list[dict], gaps: list[dict],
                    complement: dict | None = None) -> None:
    complement = load_complement() if complement is None else complement
    require(bool(panel) and bool(scenarios) and bool(literature), "empty CP0 table")
    organisms = {k[0] for k in unique(panel, ("organism_id",), "organism_id")}
    scenario_ids = {k[0] for k in unique(scenarios, ("scenario_id",), "scenario_id")}
    source_ids = {k[0] for k in unique(literature, ("source_id",), "literature source_id")}
    keys = unique(exposure, ("organism_id", "scenario_id"), "receptor/scenario")
    require(keys == {(o, s) for o in organisms for s in scenario_ids}, "orphan or missing receptor/scenario row")
    unique(gaps, ("gap_id",), "gap_id")
    for row in gaps:
        require(not row["organism_id"] or row["organism_id"] in organisms, "orphan gap receptor")
        require(not row["scenario_id"] or row["scenario_id"] in scenario_ids, "orphan gap scenario")
    functions = {}
    for row in panel:
        require(not any(k.startswith("final_") for k in row), "premature final assessability")
        require(not (set(row) & {"exposure_pathways", "external_exposure_plausibility", "internal_dsrna_exposure", "scenario_id"}), "exposure belongs to receptor/scenario grain")
        require(row["ecological_panel_tier"] in TIERS, "invalid ecological tier")
        require(row["receptor_class"] in {"PLANT", "ARTHROPOD", "OTHER_INVERTEBRATE", "MICROORGANISM", "OTHER"}, "receptor class")
        require(row["phylogenetic_context"] in {"SAME_GENUS", "SAME_FAMILY", "SAME_ORDER", "OTHER_ARTHROPOD", "OTHER_KINGDOM", "UNRESOLVED"}, "phylogenetic context")
        require(bool(row["justification"]) and bool(row["justification_status"]), "ecological justification required independently of resources")
        expected_tier = row["historical_panel_tier"].removesuffix("_PROPOSED")
        if expected_tier == "UNRESOLVED" or row["organism_id"] == "TRIGONA_SPINIPES":
            expected_tier = "CONDITIONAL"
        require(row["ecological_panel_tier"] == expected_tier, "ecological tier changed without adopted overlay")
        value = row["preliminary_computational_assessability"]
        if value:
            require(row["preliminary_assessability_source"] == "L9a_METADATA", "preliminary provenance")
            require(value in ASSESSABILITY, "preliminary assessability vocabulary")
            require(any(r["organism_id"] == row["organism_id"] and r["preliminary_computational_assessability"] == value for r in landscape), "assessability not supported by L9a")
        else:
            require(row["organism_id"] in L9A_GAP_IDS, "unnamed L9a exception")
            require(row["preliminary_assessability_source"] == "L9a_SCOPE_GAP_REGISTER" and row["preliminary_assessability_status"] == "L9A_METADATA_NOT_ASSESSED", "gap provenance is not an assessment")
            require(any(g["organism_id"] == row["organism_id"] and g["gap_type"] == "L9A_METADATA_NOT_ASSESSED" and g.get("contract_reference") == complement["l9a_gap_contract"]["contract_id"] for g in gaps), "missing metadata needs ratified explicit gap")
        if not row["taxid"]:
            require(row["organism_id"] in L9A_GAP_IDS and row["taxid_status"] == "UNRESOLVED", "unregistered missing species taxid")
            require(any(g["organism_id"] == row["organism_id"] and g["gap_type"] == "TAXID_UNRESOLVED" for g in gaps), "missing taxid gap")
        if row["surrogate_status"] == "SURROGATE_RESOURCE":
            require(bool(row["surrogate_for_organism_id"]) and row["surrogate_for_organism_id"] in organisms, "surrogate requires original receptor")
        else:
            require(row["surrogate_status"] == "NOT_A_SURROGATE" and not row["surrogate_for_organism_id"], "surrogate contract")
        require(row["reference_role"] in {"ECOLOGICAL_NTO", "REFERENCE_NOT_ECOLOGICAL_NTO"}, "reference role")
        if row["ecological_panel_tier"] == "EXTENDED":
            require(row["added_value_rationale"] == EXTENDED_VALUES.get(row["organism_id"]), "unratified extended rationale")
            require(row["added_value_registration_status"] == "PROJECT_RATIFIED_CLASSIFICATION_WITH_SOURCE_LIMITATIONS", "extended adoption missing")
            require(row["justification_status"] == row["historical_justification_status"], "extended source status promoted")
        validate_multivalue(row["ecological_functions"], vocabulary=FUNCTIONS)
        fs = parse_multivalue(row["ecological_functions"], vocabulary=FUNCTIONS)
        functions[row["organism_id"]] = fs
        validate_multivalue(row["source_ids"])
        for src in parse_multivalue(row["source_ids"]):
            require(src in source_ids, "orphan panel literature reference")
    for row in exposure:
        validate_multivalue(row["exposure_pathways"], vocabulary=PATHWAYS)
        require(row["external_exposure_plausibility"] in PLAUSIBILITY, "external plausibility")
        require(row["internal_dsrna_exposure"] == "UNKNOWN", "internal exposure cannot be inferred")
        validate_multivalue(row["source_ids"])
        for src in parse_multivalue(row["source_ids"]):
            require(src in source_ids, "orphan exposure literature reference")
    for row in scenarios:
        require(row["scenario_status"] == "CONDITIONAL_ALTERNATIVE", "scenario status")
        require(row["application_route"] == row["formulation_state"] == "UNKNOWN", "operational exposure remains unknown")
        for field in ("application_months", "application_dates", "crop_season", "application_window", "application_duration", "residue_duration", "application_frequency", "treated_area_ha", "dose"):
            require(row[field] == "UNKNOWN", f"unfounded scenario field: {field}")
    require(SCENARIO in scenario_ids, "ratified scenario absent")
    core = [r for r in panel if r["ecological_panel_tier"] == "CORE"]
    require(any(r["organism_id"] == "ZEA_MAYS" and r["receptor_class"] == "PLANT" for r in core), "host plant closure")
    require(any(r["organism_id"] == "APIS_MELLIFERA" for r in core), "pollinator closure")
    for function in ("HOST_PLANT", "POLLINATOR", "PARASITOID", "PREDATOR"):
        require(any(function in functions[r["organism_id"]] for r in core) or any(g["category"] == function for g in gaps), f"mandatory category omitted: {function}")
    require(any(r["phylogenetic_context"] in {"SAME_GENUS", "SAME_FAMILY"} for r in core), "close non-target category omitted")
    soil = [g for g in gaps if g["gap_type"] == SOIL_GAP]
    require(len(soil) == 1 and soil[0]["organism_id"] == "" and soil[0]["scenario_id"] == SCENARIO, "soil category requires unnamed gap")
    for row in landscape:
        require(row["resource_status"] == "METADATA_ONLY_NOT_SELECTED_NOT_FROZEN", "premature resource freeze")
