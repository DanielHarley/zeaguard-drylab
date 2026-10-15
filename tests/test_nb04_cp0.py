"""CP0 contract/integrity tests, without NTO searches or calibration fixtures."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from zeaguard import nb04_cp0 as cp0
from zeaguard.nb04_policy import CP0ContractError, load_policy, validate_policy, validate_tables
from zeaguard.nb04_serialization import NB04SerializationError
from zeaguard.nb04_complement import CONTRACT_PATH, RULE_ID, SOURCE_HASHES, load_complement, validate_complement


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy():
    return load_policy(ROOT)


@pytest.fixture
def tables():
    doc = json.loads((ROOT / cp0.DOC_INPUT).read_text("utf-8"))["materialized_tables"]
    return [cp0.read_tsv(ROOT / "config/nb04_nto_panel.tsv"), cp0.read_tsv(ROOT / "config/nb04_exposure_scenarios.tsv"), cp0.read_tsv(ROOT / "config/nb04_receptor_exposure.tsv"), doc["literature_register"], doc["resource_landscape"], doc["coverage_gaps"]]


@pytest.fixture
def registry():
    return json.loads((ROOT / cp0.PROVENANCE).read_text("utf-8"))


@pytest.fixture
def bundle(registry):
    return cp0.build_bundle(ROOT, registry)


def test_current_contract(policy, tables):
    validate_tables(*tables)
    assert policy["states"]["G0_PASS"] == "NOT_DECLARED"
    assert policy["states"]["CP1"] == "NOT_STARTED"


@pytest.mark.parametrize("change", [
    lambda p: p.update(canonical_k=[19]),
    lambda p: p.update(fallback_policy="B_SELECTED_PRE_G0"),
    lambda p: p.update(is_ranking=True),
    lambda p: p.update(unknown_key="x"),
    lambda p: p["states"].update(G0_PASS="DECLARED"),
    lambda p: p["states"].update(CP1="STARTED"),
    lambda p: p["states"].update(informative_calibration="EXECUTED"),
    lambda p: p["parameters"][0].update(biological_decision_role=True),
    lambda p: p["parameters"][0].update(parameter_role="DECISION_CRITERION"),
    lambda p: p["analysis_arms"].append(copy.deepcopy(p["analysis_arms"][0])),
    lambda p: p["analysis_arms"][0].update(search_configuration_id="G1_REAL_CONFIGURATION"),
    lambda p: p["analysis_arms"][1].update(modality_requirement_status="REQUIRED"),
    lambda p: p["analysis_arms"][3].update(analysis_role="CANONICAL"),
    lambda p: p["analysis_arms"][3].update(execution_required_for_completion=True),
    lambda p: p["formal_search_spaces"][0].update(k=[16]),
    lambda p: p["formal_search_spaces"][1].update(exact_difference_count=2),
    lambda p: p["formal_search_spaces"][0].update(occurrence_cap=100),
    lambda p: p["formal_search_spaces"][0].update(indels=True),
    lambda p: p["formal_search_spaces"][0].update(orientation="PLUS_ONLY"),
    lambda p: p["calibration"].update(numeric_coordinate_tolerances=5),
    lambda p: p["calibration"].update(informative_execution_requires_prior_complete_freeze=False),
    lambda p: p["calibration"].update(QA_H_blocks_configuration_freeze=True),
    lambda p: p["calibration"].update(PC03_detection_class="MUST_BE_REPORTED"),
    lambda p: p["calibration"].update(selection_rule_id="INFERRED_RULE"),
    lambda p: p["calibration"].update(selection_rule_id=None),
    lambda p: p["analysis_arms"][2].update(selection_rule_id="INFERRED_RULE"),
    lambda p: p["calibration"].update(selection_rule_status="UNRESOLVED_CONTRACT_REFERENCE"),
    lambda p: p["calibration"].update(source_document_sha256="0" * 64),
    lambda p: p["calibration"]["selection_rule"].update(validation_used_for_selection=True),
    lambda p: p["calibration"]["selection_rule"].update(validation_can_choose_substitute=True),
    lambda p: p["calibration"]["selection_rule"].update(order_may_change_after_results=True),
    lambda p: p["calibration"]["selection_rule"].update(characterization_used_as_new_threshold_or_weight=True),
    lambda p: p["calibration"]["selection_rule"].update(performance_threshold=0.95),
    lambda p: p["calibration"]["calibration_inconclusive_definition"]["result_vocabulary"].append("NOT_TESTED"),
    lambda p: p["calibration"]["calibration_inconclusive_definition"].update(selected_validation_failure="CHOOSE_ANOTHER_CANDIDATE"),
    lambda p: p["l9a_gap_contract"]["allowed_organism_ids"].append("NEW_SPECIES"),
    lambda p: p["calibration"].update(calibration_inconclusive_definition="INFERRED_CRITERION"),
    lambda p: p["calibration"].update(envelope_extrapolation_margin_bases=1),
    lambda p: p["decision_policy"].update(scientific_disposition_assignment="AUTOMATIC"),
])
def test_policy_rejects_contract_mutations(policy, change):
    change(policy)
    schema = json.loads((ROOT / "config/nb04_nto_policy.schema.json").read_text("utf-8"))
    with pytest.raises(CP0ContractError):
        validate_policy(policy, schema)


@pytest.mark.parametrize("change", [
    lambda t: t[0].append(copy.deepcopy(t[0][0])),
    lambda t: t[1].append(copy.deepcopy(t[1][0])),
    lambda t: t[2].append(copy.deepcopy(t[2][0])),
    lambda t: t[2].pop(),
    lambda t: t[2][0].update(organism_id="ORPHAN"),
    lambda t: t[2][0].update(scenario_id="ORPHAN"),
    lambda t: t[0][0].update(final_computational_assessability="ASSESSABLE"),
    lambda t: t[0][0].update(scenario_id="WRONG_GRAIN"),
    lambda t: t[0][0].update(justification=""),
    lambda t: t[0][0].update(ecological_panel_tier="EXTENDED"),
    lambda t: t[0][0].update(surrogate_status="SURROGATE_RESOURCE"),
    lambda t: t[0][0].update(preliminary_assessability_source="CP1_FINAL"),
    lambda t: t[0][0].update(source_ids="MISSING_SOURCE"),
    lambda t: t[0][0].update(ecological_functions="HOST_PLANT|HOST_PLANT"),
    lambda t: t[0][0].update(ecological_functions="HOST_PLANT|HERBIVORE_NON_TARGET"),
    lambda t: t[2][0].update(internal_dsrna_exposure="PLAUSIBLE"),
    lambda t: t[2][0].update(exposure_pathways="DIRECT_CONTACT|UNKNOWN"),
    lambda t: t[1][0].update(application_route="FOLIAR"),
    lambda t: t[1][0].update(application_frequency="1"),
    lambda t: t[4][0].update(resource_status="FROZEN"),
    lambda t: t[5].__setitem__(slice(None), [g for g in t[5] if g["gap_type"] != "L9A_METADATA_NOT_ASSESSED"]),
    lambda t: t[5].__setitem__(slice(None), [g for g in t[5] if g["gap_type"] != "SOIL_OR_RESIDUE_RECEPTOR_UNSPECIFIED_UNDER_CONSERVATIVE_ENVELOPE"]),
])
def test_tables_reject_contract_mutations(tables, change):
    change(tables)
    with pytest.raises((CP0ContractError, NB04SerializationError)):
        validate_tables(*tables)


def test_multiple_scenarios_preserve_receptor_grain(tables):
    second = copy.deepcopy(tables[1][0])
    second["scenario_id"] = "SAME_ENVELOPE_REPRESENTATION_TEST"
    tables[1].append(second)
    for row in list(tables[2]):
        new = dict(row, scenario_id=second["scenario_id"], external_exposure_plausibility="UNKNOWN")
        tables[2].append(new)
    validate_tables(*tables)
    assert len(tables[0]) * 2 == len(tables[2])


@pytest.mark.parametrize("change", [
    lambda rows, seq: rows.pop(),
    lambda rows, seq: rows.append(copy.deepcopy(rows[0])),
    lambda rows, seq: rows[0].update(query_id="EXTRA_QUERY"),
    lambda rows, seq: rows[0].update(query_role="CANDIDATE"),
    lambda rows, seq: rows[0].update(cds_start=216),
    lambda rows, seq: rows[0].update(sequence_sha256="0" * 64),
    lambda rows, seq: seq.update({rows[0]["query_id"]: "N" * 373}),
    lambda rows, seq: rows[0].update(selection_source_stage="NB03_CP4B"),
    lambda rows, seq: rows[0].update(publication_reported_length_bp=373),
    lambda rows, seq: rows[0].update(upstream_repository_commit="9ca3e0903e9bee10c0708fde95241b7fa671591a"),
])
def test_bundle_rejects_scope_and_provenance_mutations(bundle, change):
    rows, seq = bundle
    change(rows, seq)
    with pytest.raises((CP0ContractError, KeyError)):
        cp0.validate_bundle(rows, seq)


def test_layered_provenance_and_reference_pins(registry):
    observed = cp0.verify_inputs(ROOT, registry)
    assert len(observed) == 8
    assert registry["queries"]["BC-BENCH-0215-0587"]["upstream_repository_commit"] != registry["queries"]["BC-L400-1337-1736"]["upstream_repository_commit"]


def test_ratified_contract_binds_sources_without_executing_calibration(policy):
    complement = load_complement(ROOT)
    assert policy["calibration"]["selection_rule_id"] == RULE_ID
    assert policy["calibration"]["selection_rule"] == complement["selection_rule"]
    assert policy["calibration"]["calibration_inconclusive_definition"] == complement["calibration_inconclusive_definition"]
    assert {d["document_id"]: d["sha256"] for d in complement["source_documents"]} == SOURCE_HASHES
    assert policy["calibration"]["numeric_coordinate_tolerances"] is None
    assert policy["calibration"]["fixture_status"] == "NOT_MATERIALIZED"
    assert policy["calibration"]["qa_status"] == "NOT_TESTED"


def test_complement_rejects_content_tampering(tmp_path):
    destination = tmp_path / CONTRACT_PATH
    destination.parent.mkdir(parents=True)
    data = (ROOT / CONTRACT_PATH).read_bytes().replace(b"TUNING_ONLY", b"VALIDATION_ONLY", 1)
    destination.write_bytes(data)
    with pytest.raises(ValueError, match="provenance mismatch"):
        load_complement(tmp_path)


def test_complement_rejects_embedded_source_tampering():
    complement = load_complement(ROOT)
    complement["source_documents"][0]["content"] += "altered"
    with pytest.raises(ValueError, match="source provenance mismatch"):
        validate_complement(complement)


@pytest.mark.parametrize("organism,field,value", [
    ("PSEUDOLIGOSITA_LONGIFRANGIATA", "added_value_rationale", "ADDS_EXPOSURE_PATHWAY"),
    ("PSEUDOLIGOSITA_LONGIFRANGIATA", "justification_status", "SOURCE_SUPPORTED"),
    ("EXITIANUS_OBSCURINERVIS", "preliminary_assessability_source", "L9a_METADATA"),
    ("EXITIANUS_OBSCURINERVIS", "preliminary_computational_assessability", "UNASSESSABLE"),
    ("EXITIANUS_OBSCURINERVIS", "taxid_status", "RESOLVED"),
])
def test_tables_reject_promotion_of_project_or_missing_source_evidence(tables, organism, field, value):
    row = next(r for r in tables[0] if r["organism_id"] == organism)
    assert row[field] != value
    row[field] = value
    with pytest.raises(CP0ContractError):
        validate_tables(*tables)


def test_tables_reject_l9a_gap_without_nominal_ratified_reference(tables):
    next(g for g in tables[5] if g["gap_type"] == "L9A_METADATA_NOT_ASSESSED")["contract_reference"] = ""
    with pytest.raises(CP0ContractError, match="ratified explicit gap"):
        validate_tables(*tables)


def test_n20_profile_is_read_only_and_does_not_require_cp1():
    before = (ROOT / "config/repro.yaml").read_bytes()
    checks = cp0.check_cp0_paths(ROOT)
    assert checks and all(c.status == "PASS" for c in checks)
    assert all("nb04_nto_search_configuration" not in c.name and "nb04_nto_assessability" not in c.name for c in checks)
    assert (ROOT / "config/repro.yaml").read_bytes() == before


def test_configured_profile_checks_additional_paths_instead_of_masking_them(monkeypatch):
    from zeaguard import repro

    cfg = repro.load_repro_config()
    raw = copy.deepcopy(cfg.raw)
    missing = "config/nb04_missing_contract_for_test.json"
    raw["checkpoint_required_paths"]["nb04_cp0"].append(missing)
    monkeypatch.setattr(repro, "load_repro_config", lambda *args: repro.ReproConfig(raw, cfg.path))
    checks = cp0.check_cp0_paths(ROOT)
    assert any(c.name == f"path:{missing}" and c.status == "FAIL" for c in checks)


def test_configured_profile_cannot_omit_a_contract_path(monkeypatch):
    from zeaguard import repro

    cfg = repro.load_repro_config()
    raw = copy.deepcopy(cfg.raw)
    raw["checkpoint_required_paths"]["nb04_cp0"].remove(cp0.CONTRACT_PATH)
    monkeypatch.setattr(repro, "load_repro_config", lambda *args: repro.ReproConfig(raw, cfg.path))
    with pytest.raises(CP0ContractError, match="configured CP0 profile omits contract paths"):
        cp0.check_cp0_paths(ROOT)


def test_legacy_profile_proposal_remains_in_memory(monkeypatch):
    from zeaguard import repro

    cfg = repro.load_repro_config()
    raw = copy.deepcopy(cfg.raw)
    raw["schema_version"] = 1
    raw.pop("checkpoint_required_paths")
    original = copy.deepcopy(raw)
    monkeypatch.setattr(repro, "load_repro_config", lambda *args: repro.ReproConfig(raw, cfg.path))
    checks = cp0.check_cp0_paths(ROOT)
    assert checks and all(c.status == "PASS" for c in checks)
    assert raw == original


@pytest.mark.parametrize("field,value", [
    ("sequence_source_stage", "NB02_FAKE"),
    ("upstream_repository_commit", "0" * 40),
    ("sequence_source_artifact", "results/bioinformatics/nb03/cp4b/shortlist.fasta"),
    ("certification_artifact_sha256_lf", "0" * 64),
    ("selection_source_stage", "NB03_CP4B"),
])
def test_registry_rejects_false_origin_tuples(registry, field, value):
    registry["queries"]["D2-BENCH-0814-1143"][field] = value
    with pytest.raises(CP0ContractError):
        cp0.verify_inputs(ROOT, registry)


def test_hash_mismatch_before_any_git_or_output(registry, tmp_path, monkeypatch):
    for path in registry["artifacts"]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    artifact = next(iter(registry["artifacts"]))
    with (tmp_path / artifact).open("ab") as stream:
        stream.write(b"CORRUPT")
    monkeypatch.setattr(cp0, "git", lambda *a: pytest.fail("hash mismatch must precede Git provenance checks"))
    with pytest.raises(CP0ContractError, match="provenance mismatch"):
        cp0.verify_inputs(tmp_path, registry)


def test_overlap_partitions_cover_full_queries(bundle):
    rows, seq = bundle
    sharing = cp0.overlaps(rows, seq)
    assert len(sharing) == 9
    assert sorted(r["shared_nt"] for r in sharing) == [0, 0, 0, 0, 0, 316, 317, 327, 399]
    lengths = {r["query_id"]: r["length_nt"] for r in rows}
    for r in sharing:
        assert r["shared_nt"] + r["query_a_exclusive_nt"] == lengths[r["query_a"]]
        assert r["shared_nt"] + r["query_b_exclusive_nt"] == lengths[r["query_b"]]
        assert r["independence_claim"] == "NOT_ESTABLISHED"


def test_overlap_rejects_shared_base_disagreement(bundle):
    rows, seq = bundle
    q = "BC-L400-1254-1653"
    seq[q] = ("A" if seq[q][0] != "A" else "C") + seq[q][1:]
    with pytest.raises(CP0ContractError, match="shared bases"):
        cp0.overlaps(rows, seq)


def test_materialization_determinism_no_search_and_manifest_integrity(tmp_path, monkeypatch):
    real_git = cp0.git
    real_run = cp0.subprocess.run
    calls = []
    def guarded_run(command, *args, **kwargs):
        assert command[0] == "git", "CP0 must not execute a search, calibration or acquisition process"
        return real_run(command, *args, **kwargs)
    monkeypatch.setattr(cp0.subprocess, "run", guarded_run)
    def guarded_git(root, *args):
        calls.append(args)
        assert args[0] in {"merge-base", "show", "rev-parse", "branch", "status"}
        return real_git(root, *args)
    monkeypatch.setattr(cp0, "git", guarded_git)
    one, two = tmp_path / "one", tmp_path / "two"
    cp0.materialize(ROOT, one)
    cp0.materialize(ROOT, two)
    manifest = json.loads((one / cp0.CP0 / "run_manifest.json").read_text("utf-8"))
    summary = json.loads((one / cp0.CP0 / "cp0_summary.json").read_text("utf-8"))
    assert summary["normative_reference_pending"] is False
    assert summary["states"]["G0_PASS"] == "NOT_DECLARED"
    assert summary["certification_status"] == "PENDING_EXTERNAL_HUMAN_G0_REVIEW"
    assert summary["contract_equivalence"][1]["operational_profile"] == "CONFIGURED_IN_REPRO_YAML"
    assert manifest["inputs_sha256_lf"]["config/repro.yaml"] == cp0.digest(ROOT / "config/repro.yaml", normalized=True)
    assert manifest["certification_status"] == "NOT_CERTIFIED"
    for name, expected in manifest["outputs_sha256"].items():
        assert cp0.digest(one / name) == cp0.digest(two / name) == expected
        assert b"\r\n" not in (one / name).read_bytes()
    assert (one / cp0.CP0 / "run_manifest.json").read_bytes() == (two / cp0.CP0 / "run_manifest.json").read_bytes()
    assert calls
    assert not list(one.rglob("*.nhr"))
    assert not (one / "data/external/nto").exists()


def test_rejects_path_escape(tmp_path):
    with pytest.raises(CP0ContractError):
        cp0.local_path(tmp_path, "../elsewhere")


@pytest.mark.parametrize("content", [">same\nACGT\n>same\nACGT\n", "ACGT\n"])
def test_rejects_malformed_fasta(tmp_path, content):
    path = tmp_path / "input.fasta"
    path.write_text(content, encoding="ascii")
    with pytest.raises(CP0ContractError):
        cp0.read_fasta(path)
