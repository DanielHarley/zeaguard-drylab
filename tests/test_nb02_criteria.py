from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest
import yaml

from zeaguard import nb02_criteria as crit

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_HASH = "a" * 64


@pytest.fixture(scope="module")
def registry():
    return yaml.safe_load((ROOT / crit.REGISTRY_PATH).read_text(encoding="utf-8"))


def _criterion(registry, name):
    return next(c for c in registry["criteria"] if c["name"] == name)


def _problems(registry, mutate):
    mutated = copy.deepcopy(registry)
    mutate(mutated)
    return crit.validate_registry(mutated)


# ------------------------------------------------------------------ the frozen registry
def test_real_registry_is_valid_and_loads():
    assert crit.validate_registry(yaml.safe_load((ROOT / crit.REGISTRY_PATH).read_text(encoding="utf-8"))) == []
    assert crit.load_registry(ROOT)["status"] == "PRE_REGISTERED"


def test_mandatory_review_role_is_in_code_vocabulary_and_yaml_vocabulary(registry):
    assert "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW" in crit.ROLES
    assert "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW" in registry["vocabulary"]["roles"]
    assert set(registry["vocabulary"]["roles"]) == set(crit.ROLES)
    assert set(registry["vocabulary"]["evidence_categories"]) == set(crit.EVIDENCE_CATEGORIES)


def test_every_criterion_has_all_fields_a_known_category_known_roles_and_resolvable_refs(registry):
    sources = {s["id"] for s in registry["evidence_sources"]}
    for criterion in registry["criteria"]:
        assert all(field in criterion for field in crit.CRITERION_FIELDS), criterion["id"]
        assert criterion["evidence_category"] in crit.EVIDENCE_CATEGORIES
        assert set(criterion["roles"]) <= crit.ROLES and criterion["roles"]
        assert set(criterion["evidence_refs"]) <= sources
        if criterion["evidence_category"] != "PROJECT_CONVENTION":
            assert criterion["evidence_refs"], criterion["id"]


def test_other_transcript_is_descriptor_plus_mandatory_review_and_only_gates_the_shortlist(registry):
    other = _criterion(registry, "other_transcript_specificity")
    assert set(other["roles"]) == {"DESCRIPTOR", "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW"}
    assert other["affects"] == ["shortlist_gate"]
    assert [c["name"] for c in registry["criteria"] if "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW" in c["roles"]] == [
        "other_transcript_specificity"]
    assert "other_transcript_hits" in registry["policy"]["cell_signature_excludes"]
    assert registry["policy"]["cell_signature"] == crit.CELL_SIGNATURE


def test_position_is_a_pure_descriptor_outside_the_cell_signature(registry):
    position = _criterion(registry, "target_region_position")
    assert position["roles"] == ["DESCRIPTOR"] and position["affects"] == []
    assert "target_region_position" in registry["policy"]["cell_signature_excludes"]
    assert "target_region_position" not in registry["policy"]["cell_signature"]


def test_hard_filters_are_only_the_structural_ones_and_never_specificity_or_evalue_or_kmers(registry):
    hard = {c["name"] for c in registry["criteria"] if "HARD_FILTER" in c["roles"]}
    assert hard == crit.STRUCTURAL_HARD_FILTERS
    for name in ("specificity_evidence_vector", "homology_evidence_metrics_clipped", "other_transcript_specificity",
                 "strong_specificity_concern_paralog_cotarget", "search_detection_limit"):
        assert "HARD_FILTER" not in _criterion(registry, name)["roles"]


def test_no_hidden_cutoff_pairwise_overlap_or_composite_score(registry):
    assert "max_pairwise_overlap" not in registry["policy"]
    assert not any("weight" in c["name"] or "score" in c["name"] for c in registry["criteria"])
    assert any("no composite score and no weights" in step for step in registry["policy"]["prioritization"])
    for criterion in registry["criteria"]:
        if isinstance(criterion["threshold"], dict):
            assert not any(crit.FORBIDDEN_THRESHOLD_KEY.search(key) for key in criterion["threshold"]), criterion["id"]


def test_shuffled_control_is_descriptor_only_with_five_fixed_seeds(registry):
    control = _criterion(registry, "shuffled_control")
    assert control["roles"] == ["DESCRIPTOR"] and control["affects"] == []
    assert control["threshold"] == {"n_shuffles": 5, "seeds": [1, 2, 3, 4, 5]}


def test_length_strata_and_nominal_length_are_conventions_not_filters(registry):
    strata = _criterion(registry, "length_strata")
    assert strata["evidence_category"] == "PROJECT_CONVENTION" and strata["roles"] == ["DESCRIPTOR"]
    assert strata["threshold"] == {"ranking_length_nt": 400, "benchmark_comparator_length_nt": 330, "sensitivity_lengths_nt": [300, 500]}
    assert (_criterion(registry, "length_range")["threshold"]) == {"min_nt": 300, "max_nt": 500}


def test_benchmark_is_reference_set_and_never_a_recommended_candidate(registry):
    assert registry["policy"]["benchmark_counts_as_recommended"] is False
    assert registry["policy"]["recommended_candidates"] == {"min": 2, "max": 4}
    assert "efficacy_score" in registry["policy"]["forbidden_in_nb02"]
    benchmark = _criterion(registry, "published_benchmark_reference")
    assert benchmark["roles"] == ["DESCRIPTOR"] and "INJECTION_PRECONDITIONING" in benchmark["definition"]


# ------------------------------------------------------------------ the registry rejects violations
@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda r: _criterion(r, "min_length_floor").update(evidence_refs=[]), "requires at least one evidence ref"),
        (lambda r: _criterion(r, "target_region_position").update(roles=["DESCRIPTOR", "SOFT_PREFERENCE"]), "position must be a pure DESCRIPTOR"),
        (lambda r: _criterion(r, "target_region_position").update(affects=["cell_signature"]), "position must be a pure DESCRIPTOR"),
        (lambda r: _criterion(r, "other_transcript_specificity").update(roles=["DESCRIPTOR", "SOFT_PREFERENCE"]), "mandatory"),
        (lambda r: _criterion(r, "other_transcript_specificity").update(affects=["pareto", "shortlist_gate"]), "only shortlist_gate"),
        (lambda r: _criterion(r, "specificity_evidence_vector").update(roles=["HARD_FILTER"]), "HARD_FILTER is reserved"),
        (lambda r: _criterion(r, "search_detection_limit")["threshold"].update(evalue_cutoff=1e-5), "hidden cutoff"),
        (lambda r: r["policy"].update(max_pairwise_overlap=0.5), "max pairwise overlap"),
        (lambda r: r["policy"]["cell_signature"].append("target_region_position"), "cell_signature must be exactly"),
        (lambda r: r["policy"]["cell_signature_excludes"].remove("other_transcript_hits"), "cell_signature_excludes"),
        (lambda r: _criterion(r, "gc_fraction").update(roles=["NOT_A_ROLE"]), "subset of the vocabulary"),
        (lambda r: r["vocabulary"]["roles"].remove("MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW"), "vocabulary.roles"),
        (lambda r: r["policy"].update(benchmark_counts_as_recommended=True), "benchmark must not count"),
        (lambda r: _criterion(r, "gc_fraction").update(evidence_refs=["unknown_source"]), "known evidence source ids"),
    ],
)
def test_registry_rejects_rule_violations(registry, mutate, needle):
    assert any(needle in problem for problem in _problems(registry, mutate)), needle


def test_registry_sha256_is_line_ending_independent_and_stable(tmp_path):
    lf, crlf = tmp_path / "lf.yaml", tmp_path / "crlf.yaml"
    lf.write_bytes(b"a: 1\nb: 2\n")
    crlf.write_bytes(b"a: 1\r\nb: 2\r\n")
    assert crit.registry_sha256(lf) == crit.registry_sha256(crlf)
    assert len(crit.registry_sha256(ROOT / crit.REGISTRY_PATH)) == 64


# ------------------------------------------------------------------ manual-review decisions and the recommendation gate
def _write_decisions(path, *rows):
    header = "\t".join(crit.DECISION_COLUMNS)
    path.write_text("\n".join([header, *("\t".join(r) for r in rows)]) + "\n", encoding="utf-8")


def _row(candidate="D2-L400-0100-0499", scope="OTHER_TRANSCRIPT", decision="APPROVED", justification="", evidence=EVIDENCE_HASH):
    return (candidate, scope, decision, justification, "reviewer", "2026-10-05T12:00:00Z", evidence)


def test_real_decision_file_is_versioned_header_only_with_no_decisions_yet():
    assert crit.load_review_decisions(ROOT / crit.REVIEW_DECISIONS_PATH) == {}


def test_candidate_without_other_transcript_review_cannot_become_recommended(tmp_path):
    path = tmp_path / "d.tsv"
    _write_decisions(path)
    decisions = crit.load_review_decisions(path)
    assert crit.recommendation_status("D2-L400-0100-0499", decisions) == "PENDING_REVIEW"
    with pytest.raises(crit.NB02ReviewError):
        crit.assert_can_recommend("D2-L400-0100-0499", decisions)
    # reviewing PARALOG / CO_TARGET alone does not substitute for the complete-TSA review
    _write_decisions(path, _row(scope="PARALOG"), _row(scope="CO_TARGET"))
    decisions = crit.load_review_decisions(path)
    assert crit.recommendation_status("D2-L400-0100-0499", decisions, ("PARALOG", "CO_TARGET")) == "PENDING_REVIEW"


def test_explicit_approved_decision_allows_recommendation(tmp_path):
    path = tmp_path / "d.tsv"
    _write_decisions(path, _row())
    decisions = crit.load_review_decisions(path)
    assert crit.recommendation_status("D2-L400-0100-0499", decisions) == "RECOMMENDABLE"
    crit.assert_can_recommend("D2-L400-0100-0499", decisions)
    # an open paralog trigger keeps the candidate pending until that scope is also approved
    assert crit.recommendation_status("D2-L400-0100-0499", decisions, ("PARALOG",)) == "PENDING_REVIEW"
    _write_decisions(path, _row(), _row(scope="PARALOG"))
    assert crit.recommendation_status("D2-L400-0100-0499", crit.load_review_decisions(path), ("PARALOG",)) == "RECOMMENDABLE"


def test_strong_intraspecies_concern_blocks_recommendation_and_requires_justification(tmp_path):
    path = tmp_path / "d.tsv"
    _write_decisions(path, _row(decision="STRONG_INTRASPECIES_SPECIFICITY_CONCERN", justification="extensive local homology with transcript X"))
    decisions = crit.load_review_decisions(path)
    assert crit.recommendation_status("D2-L400-0100-0499", decisions) == "EXCLUDED_AFTER_REVIEW"
    with pytest.raises(crit.NB02ReviewError):
        crit.assert_can_recommend("D2-L400-0100-0499", decisions)
    _write_decisions(path, _row(decision="STRONG_INTRASPECIES_SPECIFICITY_CONCERN", justification=""))
    with pytest.raises(crit.NB02ReviewError, match="justification"):
        crit.load_review_decisions(path)


def test_concern_in_any_scope_excludes_even_when_other_transcript_was_approved(tmp_path):
    path = tmp_path / "d.tsv"
    _write_decisions(path, _row(), _row(scope="PARALOG", decision="STRONG_SPECIFICITY_CONCERN", justification="homologous to dsRNase-1"))
    assert crit.recommendation_status("D2-L400-0100-0499", crit.load_review_decisions(path)) == "EXCLUDED_AFTER_REVIEW"


@pytest.mark.parametrize(
    "row, message",
    [
        (_row(scope="UNKNOWN"), "unknown scope"),
        (_row(scope="OTHER_TRANSCRIPT", decision="STRONG_SPECIFICITY_CONCERN", justification="x"), "not valid for scope"),
        (_row(scope="PARALOG", decision="STRONG_INTRASPECIES_SPECIFICITY_CONCERN", justification="x"), "not valid for scope"),
        (_row(evidence="short"), "evidence_sha256"),
        (_row(candidate=""), "candidate_id"),
    ],
)
def test_decision_file_rejects_invalid_rows(tmp_path, row, message):
    path = tmp_path / "d.tsv"
    _write_decisions(path, row)
    with pytest.raises(crit.NB02ReviewError, match=message):
        crit.load_review_decisions(path)


def test_decision_file_rejects_duplicates_and_wrong_header(tmp_path):
    path = tmp_path / "d.tsv"
    _write_decisions(path, _row(), _row())
    with pytest.raises(crit.NB02ReviewError, match="duplicate"):
        crit.load_review_decisions(path)
    path.write_text("candidate_id\tdecision\n", encoding="utf-8")
    with pytest.raises(crit.NB02ReviewError, match="columns"):
        crit.load_review_decisions(path)


# ------------------------------------------------------------------ policy kernel: cells and Pareto
def _evidence(candidate="a", length=400, variants=(816,), dsrnase1=(0.0, 0.0, 0.0), dsrnase3=(0.0, 0.0, 0.0),
              co_target=(0.0, 0.0, 0.0), other=()):
    return crit.SpecificityEvidence(candidate, length, frozenset(variants), dsrnase1, dsrnase3, co_target, tuple(other))


def test_changing_only_other_transcript_hits_changes_neither_cell_nor_pareto_position():
    quiet = _evidence(other=())
    noisy = _evidence(other=({"target": "GITV01000001.1", "longest_exact_match_clipped": 25, "covered_nt_clipped": 300},) * 50)
    assert crit.decisive_signature(quiet) == crit.decisive_signature(noisy)
    rival = _evidence("b", dsrnase1=(12.0, 30.0, 0.8))
    assert crit.compare_specificity(quiet, rival) == crit.compare_specificity(noisy, rival) == "A_BETTER"
    assert crit.compare_specificity(rival, quiet) == crit.compare_specificity(rival, noisy) == "B_BETTER"
    assert crit.compare_specificity(quiet, noisy) == "TIE"


def test_cell_signature_has_no_position_gc_or_other_transcript_input():
    names = {field.name for field in dataclasses.fields(crit.SpecificityEvidence)}
    assert not {"target_region_position", "relative_midpoint", "gc_fraction"} & names
    a, b = _evidence(), _evidence()
    assert crit.decisive_signature(a) == crit.decisive_signature(b)
    assert crit.decisive_signature(_evidence(variants=(816, 1272))) != crit.decisive_signature(a)  # variants do matter


def test_pareto_dominance_incomparable_equal_and_group_order():
    assert crit.dominates((1, 5, 0.5), (2, 5, 0.5))
    assert not crit.dominates((1, 5, 0.5), (1, 5, 0.5))
    assert not crit.dominates((1, 9, 0.5), (2, 5, 0.5)) and not crit.dominates((2, 5, 0.5), (1, 9, 0.5))
    better, worse = _evidence("a", dsrnase1=(11, 20, 0.7)), _evidence("b", dsrnase1=(15, 40, 0.9))
    assert crit.compare_specificity(better, worse) == "A_BETTER" and crit.compare_specificity(worse, better) == "B_BETTER"
    incomparable_a, incomparable_b = _evidence("a", dsrnase1=(11, 40, 0.7)), _evidence("b", dsrnase1=(15, 20, 0.7))
    assert crit.compare_specificity(incomparable_a, incomparable_b) == "TIE"  # no invented weights
    # equal PARALOG vectors defer to CO_TARGET
    assert crit.compare_specificity(_evidence("a", co_target=(0, 0, 0)), _evidence("b", co_target=(14, 30, 0.8))) == "A_BETTER"
    # an incomparable PARALOG pair is not rescued by the CO_TARGET group
    assert crit.compare_specificity(_evidence("a", dsrnase1=(11, 40, 0.7), co_target=(0, 0, 0)),
                                    _evidence("b", dsrnase1=(15, 20, 0.7), co_target=(30, 90, 1.0))) == "TIE"


def test_specificity_is_refused_across_length_strata():
    with pytest.raises(ValueError, match="length stratum"):
        crit.compare_specificity(_evidence(length=300), _evidence(length=500))


# ------------------------------------------------------------------ dated amendments (closing review of CP1)
def test_amendment_records_c03_redundancy_and_the_provenance_split_without_changing_policy(registry):
    amendment = registry["amendments"][0]
    assert amendment["criteria"] == ["C03", "C19"]
    assert amendment["changes_thresholds_roles_or_policy"] is False and amendment["applied_before_window_generation"] is True
    c03 = _criterion(registry, "min_length_floor")
    assert "Redundant given C02" in c03["limitations"] and c03["threshold"] == {"min_nt": 60}
    c19 = _criterion(registry, "published_benchmark_reference")
    assert "benchmark_sequence_verification" in c19["definition"] and "experimental_protocol_verification" in c19["definition"]
    assert "PROJECT_PROVIDED_NOT_AGENT_VERIFIED" in c19["limitations"]


def test_registry_rejects_incomplete_or_dangling_amendments(registry):
    assert any("amendment lacks" in p for p in _problems(registry, lambda r: r["amendments"][0].pop("reason")))
    assert any("unknown criteria" in p for p in _problems(registry, lambda r: r["amendments"][0].update(criteria=["C99"])))


# ------------------------------------------------------------------ biological units of specificity (amendment 3, frozen before any BLAST)
def test_units_are_frozen_with_bicc_including_the_nb01_tsa_record(registry):
    units = registry["policy"]["specificity_units"]
    assert {k: v["group"] for k, v in units.items()} == {"DSRNASE1": "PARALOG", "DSRNASE3": "PARALOG", "BICC": "CO_TARGET"}
    assert units["DSRNASE1"]["members"] == ["GITV01001583.1", "GITV01002042.1", "GITV01003945.1", "TRINITY_DN13786_c0_g1_i8"]
    assert units["DSRNASE3"]["members"] == ["TRINITY_DN5008_c0_g1_i24"]
    assert units["BICC"]["members"] == ["TRINITY_DN24799_c0_g1_i7", "GITV01000968.1"]
    assert registry["policy"]["unit_aggregation"]["pool_across_units"] is False
    assert set(registry["policy"]["known_dsrnase2_compatible_excluded_from_risk"]) == {
        "GITV01008430.1", "GITV01012450.1", "TRINITY_DN22752_c0_g2_i1"}


def test_third_amendment_is_pre_data_without_threshold_or_score(registry):
    amendment = registry["amendments"][2]
    assert amendment["made_before_blast_results"] is True
    assert amendment["introduces_threshold"] is False and amendment["introduces_score"] is False
    assert amendment["changes_thresholds_roles_or_policy"] is False
    assert set(amendment["criteria"]) == {"C06", "C07", "C17"}
    assert "GITV01000968.1" in amendment["change"] and "OTHER_TRANSCRIPT" in amendment["change"]
    assert _criterion(registry, "search_detection_limit")["threshold"]["max_target_seqs"] == 100000


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda r: r["policy"]["specificity_units"]["BICC"]["members"].remove("GITV01000968.1"), "BICC must contain"),
        (lambda r: r["policy"]["specificity_units"]["DSRNASE3"]["members"].append("GITV01001583.1"), "belongs to both"),
        (lambda r: r["policy"]["unit_aggregation"].update(pool_across_units=True), "never be pooled"),
        (lambda r: r["policy"]["specificity_units"]["DSRNASE1"].update(group="CO_TARGET"), "specificity_units must be"),
        (lambda r: r["policy"]["specificity_units"]["DSRNASE1"]["members"].append("GITV01008430.1"), "KNOWN_DSRNASE2_COMPATIBLE"),
    ],
)
def test_registry_rejects_unit_violations(registry, mutate, needle):
    assert any(needle in problem for problem in _problems(registry, mutate)), needle


def test_tradeoff_between_dsrnase1_and_dsrnase3_is_incomparable_and_never_summed():
    better_on_1 = _evidence("a", dsrnase1=(0, 0, 0.0), dsrnase3=(25, 80, 1.0))
    better_on_3 = _evidence("b", dsrnase1=(25, 80, 1.0), dsrnase3=(0, 0, 0.0))
    assert crit.compare_specificity(better_on_1, better_on_3) == "TIE" == crit.compare_specificity(better_on_3, better_on_1)
    # 80 nt against each paralog is not "160 nt against PARALOG": the evidence keeps the units apart
    both = _evidence("c", dsrnase1=(0, 80, 0.6), dsrnase3=(0, 80, 0.6))
    assert crit.decisive_signature(both)[1] == ((0, 80, 0.6), (0, 80, 0.6))
    assert both.paralog == (0, 80, 0.6, 0, 80, 0.6)
    # dominance needs "no worse" on the axes of BOTH units
    assert crit.compare_specificity(_evidence("d", dsrnase1=(0, 40, 0.5), dsrnase3=(0, 40, 0.5)), both) == "A_BETTER"
    assert crit.compare_specificity(_evidence("e", dsrnase1=(0, 40, 0.5), dsrnase3=(0, 90, 0.5)), both) == "TIE"


def test_exact_kmer_counts_and_evalues_are_not_inputs_of_the_dominance_order():
    names = {field.name for field in dataclasses.fields(crit.SpecificityEvidence)}
    assert not {"evalue", "e_value", "exact_19mer_count", "exact_21mer_count", "aligned_nt_clipped"} & names
