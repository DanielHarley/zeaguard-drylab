from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from zeaguard import nb03_criteria as crit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = yaml.safe_load((ROOT / crit.REGISTRY_PATH).read_text(encoding="utf-8"))
PIN = json.loads((ROOT / crit.PIN_PATH).read_text(encoding="utf-8"))


def _criterion(registry, name):
    return next(c for c in registry["criteria"] if c["name"] == name)


def _mutated(mutation):
    registry = copy.deepcopy(REGISTRY)
    mutation(registry)
    return crit.validate_registry(registry)


# ------------------------------------------------------------------ registry and pin are valid and agree
def test_registry_is_valid_and_loads():
    assert crit.validate_registry(REGISTRY) == []
    assert crit.load_registry(ROOT)["registry"] == "nb03_design_criteria"
    assert REGISTRY["status"] == "PRE_REGISTERED"
    assert len(REGISTRY["amendments"]) == 4
    clarification = REGISTRY["amendments"][0]
    assert clarification["criteria"] == ["C23"]
    assert clarification["applied_before_window_generation"] is True
    assert clarification["changes_thresholds_roles_or_policy"] is False
    native_amendment = REGISTRY["amendments"][1]
    assert native_amendment["applied_before_candidate_specificity_analysis"] is True
    assert native_amendment["changes_thresholds_roles_or_policy"] is True
    assert native_amendment["applied_before_window_generation"] is False
    tie_documentation = REGISTRY["amendments"][2]
    assert tie_documentation["criteria"] == ["C05"]
    assert tie_documentation["changes_thresholds_roles_or_policy"] is False
    assert tie_documentation["documents_existing_implementation_behavior"] is True
    assert tie_documentation["cp3_outputs_changed"] is False
    cell_semantics = REGISTRY["amendments"][3]
    assert cell_semantics["criteria"] == ["C06", "C07"] and cell_semantics["applied_before_cp4a_results"] is True


def test_pin_is_valid_offline_and_agrees_with_the_registry():
    assert crit.validate_pin(PIN) == []
    assert crit.load_pin(ROOT)["kind"] == "nb01_bicc_operational_reference"
    assert crit.validate_registry_against_pin(REGISTRY, PIN) == []


def test_pin_does_not_need_the_raw_docx_or_the_gitignored_results():
    # offline validation uses only the versioned JSON; the raw file is recorded by hash and kept out of git
    source = PIN["benchmark"]["source"]
    assert source["raw_file_kept_in_git"] is False
    assert source["primary_table_s1_sha256"] == "0d235a577ed7ac5782a90e07cdb6679db1ecf2da4d0e9bc79e37bf377b0bc4be"
    assert source["primary_source_role"] == "PRIMARY_2022_TABLE_S1" and source["doi"] == "10.1002/ps.6937"
    assert source["source_url"] is None


# ------------------------------------------------------------------ benchmark 372 / 373
def test_benchmark_keeps_published_and_operational_lengths_side_by_side():
    b = PIN["benchmark"]
    assert (b["published_reported_body_length_nt"], b["reconstructed_body_length_nt"], b["operational_sequence_length_nt"]) == (372, 373, 373)
    assert (b["published_reported_t7_amplicon_length_nt"], b["reconstructed_t7_amplicon_length_nt"]) == (402, 403)
    assert b["length_discrepancy_nt"] == 1 and b["length_discrepancy_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY"
    assert b["length_discrepancy_cause_asserted"] is False and b["published_reported_length_role"] == "PUBLISHED_REPORTED_METADATA"
    assert b["primers"]["partial_t7_tail_5to3"] == "CGACTCACTATAGGG" and b["primers"]["partial_t7_tail_length_nt"] == 15
    assert b["body"]["sha256"] == "e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb"
    assert (b["coordinates"]["cds_sense"]["start"], b["coordinates"]["cds_sense"]["end"]) == (215, 587)
    assert (b["benchmark_nt_inside_cds"], b["benchmark_nt_outside_cds"], b["observed_sequence_differences_intersected"]) == (373, 0, [])
    assert b["benchmark_sequence_verification"] == "VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY"
    assert b["benchmark_sequence_basis"] == "PRIMARY_2022_PRIMER_DEFINED_RECONSTRUCTION"
    assert b["experimental_protocol_verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"


def test_registry_strata_use_the_real_373_and_keep_372_as_metadata():
    strata = _criterion(REGISTRY, "length_strata")["threshold"]
    assert strata["benchmark_comparator_length_nt"] == 373 and strata["benchmark_published_reported_length_nt"] == 372
    assert strata["ranking_length_nt"] == 400 and strata["sensitivity_lengths_nt"] == [300, 500]
    assert _criterion(REGISTRY, "length_strata")["evidence_category"] == "PROJECT_CONVENTION"
    assert REGISTRY["policy"]["design"]["ranking_length_is_biological_optimum"] is False
    problems = _mutated(lambda r: _criterion(r, "length_strata")["threshold"].update(benchmark_comparator_length_nt=372))
    assert any("373" in p for p in problems)


def test_pin_validation_rejects_a_forced_or_inconsistent_benchmark():
    for mutation in (
        lambda p: p["benchmark"].update(reconstructed_body_length_nt=372),
        lambda p: p["benchmark"].update(length_discrepancy_nt=0),
        lambda p: p["benchmark"].update(published_reported_t7_amplicon_length_nt=403),
        lambda p: p["benchmark"].update(experimental_protocol_verification="VERIFIED_AGAINST_PRIMARY_TEXT"),
        lambda p: p["benchmark"].update(membership="RECOMMENDED_SHORTLIST"),
        lambda p: p["benchmark"]["primers"]["forward_t7"].update(sequence="CGACTCACTATAGG" + p["benchmark"]["primers"]["forward"]["sequence"]),
    ):
        pin = copy.deepcopy(PIN)
        mutation(pin)
        assert crit.validate_pin(pin), mutation


def test_benchmark_is_a_reference_set_member_that_never_counts_as_recommended():
    bench = REGISTRY["policy"]["benchmark"]
    assert bench["membership"] == "REFERENCE_SET" and bench["counts_as_recommended"] is False
    assert bench["participates_in_candidate_cells"] is False and bench["proximity_influences_ranking"] is False
    assert PIN["benchmark"]["membership"] == "REFERENCE_SET" and PIN["benchmark"]["reference_set_only"] is True


def test_benchmark_relation_is_descriptive_and_outside_the_signature():
    criterion = _criterion(REGISTRY, "benchmark_relation_descriptors")
    assert criterion["roles"] == ["DESCRIPTOR"] and criterion["affects"] == []
    bench = REGISTRY["policy"]["benchmark"]
    assert set(bench["relation_categories"]) == {"DISJOINT", "PARTIAL_OVERLAP", "FULLY_WITHIN", "CONTAINS_BENCHMARK", "EXACT_MATCH"}
    assert tuple(bench["relation_descriptors"]) == crit.BENCHMARK_RELATION_DESCRIPTORS
    assert set(bench["relation_descriptors"]) <= set(REGISTRY["policy"]["cell_signature_excludes"])
    assert "overlap_fraction" not in bench["relation_descriptors"]
    assert _mutated(lambda r: r["policy"]["benchmark"]["relation_descriptors"].__setitem__(1, "overlap_fraction"))
    assert _mutated(lambda r: r["policy"]["benchmark"]["relation_categories"].remove("EXACT_MATCH"))
    assert _mutated(lambda r: r["policy"]["benchmark"]["overlap_fraction_denominators"].update(overlap_fraction_of_benchmark="candidate_length_nt"))
    assert bench["relation_role"] == "DESCRIPTIVE_ONLY" and "benchmark_relation" in REGISTRY["policy"]["cell_signature_excludes"]
    problems = _mutated(lambda r: _criterion(r, "benchmark_relation_descriptors").update(roles=["SOFT_PREFERENCE"], affects=["primary_ordering"]))
    assert problems


# ------------------------------------------------------------------ domain, hard filters, conventions
def test_only_the_three_structural_hard_filters_exist():
    hard = {c["name"] for c in REGISTRY["criteria"] if "HARD_FILTER" in c["roles"]}
    assert hard == {"inside_operational_cds", "length_range", "defined_bases_only"}
    assert REGISTRY["policy"]["hard_filters"] == ["inside_operational_cds", "length_range", "defined_bases_only"]
    assert REGISTRY["policy"]["design"]["design_domain"] == "CDS_ONLY"
    assert REGISTRY["policy"]["design"]["allowed_design_lengths_nt"] == {"min": 300, "max": 500}
    for name in ("gc_fraction", "longest_homopolymer", "low_complexity_fraction"):
        criterion = _criterion(REGISTRY, name)
        assert criterion["roles"] == ["DESCRIPTOR"] and criterion["threshold"] in (None, _criterion(REGISTRY, name)["threshold"])
        assert "HARD_FILTER" not in criterion["roles"]
    assert _criterion(REGISTRY, "inside_operational_cds")["threshold"]["cds_max"] == PIN["operational_reference"]["cds_length"]


def test_a_new_hard_filter_or_a_hidden_threshold_is_rejected():
    assert _mutated(lambda r: _criterion(r, "gc_fraction").update(roles=["HARD_FILTER"], affects=["eligibility"]))
    assert _mutated(lambda r: _criterion(r, "longest_homopolymer").update(threshold={"max_run_cutoff": 6}))
    assert _mutated(lambda r: r["policy"].update(design={**r["policy"]["design"], "design_domain": "CDS_AND_UTR"}))
    assert _mutated(lambda r: r["policy"]["design"].update(ranking_length_classification="EVIDENCE_BACKED"))
    assert _mutated(lambda r: r["policy"].update(max_pairwise_overlap=0.5))


# ------------------------------------------------------------------ Pareto
def test_pareto_is_joint_with_exactly_six_axes_and_no_weights_scores_or_sums():
    pareto = REGISTRY["policy"]["pareto"]
    assert pareto["units"] == ["BICC_LIKE", "DSRNASE2"]
    assert pareto["axes_per_unit"] == ["longest_exact_match", "covered_nt", "best_local_identity"]
    assert pareto["n_decisional_axes"] == 6 == len(pareto["units"]) * len(pareto["axes_per_unit"])
    assert pareto["direction"] == "lower_is_better" and pareto["direction_classification"] == "PROJECT_CONVENTION"
    assert pareto["comparison"] == "joint" and pareto["hierarchy_between_units"] is False and pareto["incomparable_is_tie"] is True
    assert not any(any(t in key for t in ("weight", "score", "sum")) for key in crit._keys(pareto))
    assert not any("weight" in name or "score" in name for name in (c["name"] for c in REGISTRY["criteria"]))


def test_pareto_policy_mutations_are_rejected():
    assert _mutated(lambda r: r["policy"]["pareto"]["axes_per_unit"].append("evalue"))
    assert _mutated(lambda r: r["policy"]["pareto"].update(units=["BICC_LIKE"]))
    assert _mutated(lambda r: r["policy"]["pareto"].update(hierarchy_between_units=True))
    assert _mutated(lambda r: r["policy"]["pareto"].update(unit_weights={"BICC_LIKE": 2}))
    assert _mutated(lambda r: r["policy"]["pareto"].update(direction="higher_is_better"))
    assert _mutated(lambda r: r["policy"]["pareto"].update(n_decisional_axes=7))


def _evidence(cid, bicc, ds2, diffs=(), length=400):
    return crit.SpecificityEvidence(cid, length, frozenset(diffs), bicc, ds2, crit.CANONICAL_EVIDENCE_BASIS)


def test_joint_dominance_ties_and_no_hierarchy():
    zero = (0.0, 0.0, 0.0)
    a, b = _evidence("A", (10, 10, 80), zero), _evidence("B", (12, 10, 80), zero)
    assert crit.compare_specificity(a, b) == "A_BETTER" and crit.compare_specificity(b, a) == "B_BETTER"
    assert len(a.joint) == 6
    # a trade-off between the two units is a tie, in both directions: no unit outranks the other
    left, right = _evidence("L", (5, 5, 70), (30, 30, 90)), _evidence("R", (20, 20, 90), (4, 4, 60))
    assert crit.compare_specificity(left, right) == "TIE" == crit.compare_specificity(right, left)
    # equal vectors tie; domination needs a strict improvement somewhere
    assert crit.compare_specificity(_evidence("X", zero, zero), _evidence("Y", zero, zero)) == "TIE"
    with pytest.raises(ValueError):
        crit.compare_specificity(_evidence("X", zero, zero, length=400), _evidence("Y", zero, zero, length=300))


def test_signature_has_no_descriptor_and_the_count_is_the_decisional_metric():
    evidence = _evidence("A", (1, 2, 3), (4, 5, 6), diffs={597, 1092})
    count, bicc_like, dsrnase2 = crit.decisive_signature(evidence)
    assert count == crit.count_intersected(evidence) == 2
    assert bicc_like == (1, 2, 3) and dsrnase2 == (4, 5, 6)
    assert evidence.intersected_observed_sequence_difference_positions == (597, 1092)
    assert REGISTRY["policy"]["cell_signature"] == crit.CELL_SIGNATURE == [
        "count_intersected_observed_sequence_differences", "bicc_like_vector", "dsrnase2_vector",
    ]


def test_equal_vectors_and_counts_with_different_positions_have_the_same_decisional_signature():
    a = _evidence("A", (1, 2, 3), (4, 5, 6), diffs={597, 1092})
    b = _evidence("B", (1, 2, 3), (4, 5, 6), diffs={1120, 1287})
    assert a.intersected_observed_sequence_difference_positions == (597, 1092)
    assert b.intersected_observed_sequence_difference_positions == (1120, 1287)
    assert crit.count_intersected(a) == crit.count_intersected(b) == 2
    assert crit.decisive_signature(a) == crit.decisive_signature(b) == (2, (1, 2, 3), (4, 5, 6))
    assert crit.compare_specificity(a, b) == crit.compare_specificity(b, a) == "TIE"


def test_different_counts_change_the_signature_without_changing_specificity():
    a = _evidence("A", (1, 2, 3), (4, 5, 6), diffs={597})
    b = _evidence("B", (1, 2, 3), (4, 5, 6), diffs={597, 1092})
    assert crit.decisive_signature(a) != crit.decisive_signature(b)
    assert crit.decisive_signature(a)[0] == 1 and crit.decisive_signature(b)[0] == 2
    assert crit.compare_specificity(a, b) == "TIE"


def test_intersected_positions_are_descriptive_and_cannot_influence_decisions():
    name = "intersected_observed_sequence_difference_positions"
    positions = _criterion(REGISTRY, name)
    assert positions["roles"] == ["DESCRIPTOR"] and positions["affects"] == []
    policy = REGISTRY["policy"]
    assert policy["observed_sequence_differences"]["descriptive_metric"] == name
    assert policy["observed_sequence_differences"]["positions_role"] == "DESCRIPTIVE_ONLY"
    assert name in policy["descriptive_only_criteria"] and name in policy["cell_signature_excludes"]
    assert name not in policy["cell_signature"]
    for affect in ("pareto", "cell_signature", "primary_ordering"):
        assert _mutated(lambda r: _criterion(r, name).update(roles=["SOFT_PREFERENCE"], affects=[affect]))
    assert _mutated(lambda r: _criterion(r, name).update(roles=["TIE_BREAKER"], affects=["primary_ordering"]))
    assert _mutated(lambda r: r["policy"]["cell_signature"].__setitem__(0, name))
    assert _mutated(lambda r: r["policy"]["cell_signature_excludes"].remove(name))
    assert _mutated(lambda r: r["policy"]["observed_sequence_differences"].update(positions_role="DECISIONAL"))


# ------------------------------------------------------------------ observed_sequence_differences
def test_observed_differences_policy_and_pin_terms():
    policy = REGISTRY["policy"]["observed_sequence_differences"]
    assert policy["decisional_metric"] == "count_intersected_observed_sequence_differences" and policy["direction"] == "lower_is_better"
    assert policy["hard_exclusion"] is False and policy["threshold"] is None and policy["applied_after"] == "specificity"
    assert policy["permitted_interpretation"] == "greater robustness to the two currently observed sequences"
    assert {"population robustness", "allele robustness", "polymorphism robustness", "population conservation"} == set(policy["forbidden_interpretations"])
    obs = PIN["observed_sequence_differences"]
    assert obs["nature_status"] == "UNRESOLVED" and obs["read_support_status"] == "NOT_ASSESSED_FOR_NB03_CP0"
    assert [i["cds_position"] for i in obs["items"]] == [597, 1092, 1120, 1287, 2094, 2259, 2280]
    assert all(i["read_support_status"] == "NOT_ASSESSED_FOR_NB03_CP0" for i in obs["items"])
    assert {"published_codon", "operational_codon", "published_amino_acid", "operational_amino_acid", "synonymous_status"} <= set(obs["items"][0])
    # schema check: no field of an item names a nature
    assert not any(any(t in key for t in ("variant", "allele", "polymorph")) for item in obs["items"] for key in item)


def test_fraction_unaffected_and_the_differences_metric_have_the_right_roles():
    fraction = _criterion(REGISTRY, "fraction_unaffected")
    assert fraction["roles"] == ["DESCRIPTOR"] and fraction["affects"] == []
    metric = _criterion(REGISTRY, "count_intersected_observed_sequence_differences")
    assert metric["roles"] == ["SOFT_PREFERENCE"] and set(metric["affects"]) == {"cell_signature", "primary_ordering"}
    assert _mutated(lambda r: _criterion(r, "fraction_unaffected").update(roles=["SOFT_PREFERENCE"], affects=["primary_ordering"]))


def test_pin_validation_rejects_a_nature_claim_on_the_differences():
    pin = copy.deepcopy(PIN)
    pin["observed_sequence_differences"]["items"][0]["variant_class"] = "SNP"
    assert crit.validate_pin(pin)
    pin = copy.deepcopy(PIN)
    pin["observed_sequence_differences"]["nature_status"] = "POLYMORPHISM"
    assert crit.validate_pin(pin)


# ------------------------------------------------------------------ descriptors, k = 21, decisional set
def test_only_the_two_pre_registered_criteria_are_decisional():
    decisional = {c["name"] for c in REGISTRY["criteria"] if set(c["affects"]) & crit.ORDERING_AFFECTS}
    assert decisional == {"specificity_evidence_vector", "count_intersected_observed_sequence_differences"}
    assert _mutated(lambda r: _criterion(r, "gc_fraction").update(roles=["SOFT_PREFERENCE"], affects=["primary_ordering"]))


def test_k21_is_an_operational_assumption_used_only_as_a_descriptor():
    small = REGISTRY["policy"]["small_rna_descriptor"]
    assert (small["k"], small["classification"], small["role"], small["decisional"]) == (21, "OPERATIONAL_ASSUMPTION", "DESCRIPTIVE_ONLY", False)
    criterion = _criterion(REGISTRY, "potential_21nt_derived_windows")
    assert criterion["evidence_category"] == "OPERATIONAL_ASSUMPTION" and criterion["roles"] == ["DESCRIPTOR"] and criterion["affects"] == []
    assert small["permitted_term"] == "potential 21-nt derived windows"
    assert _mutated(lambda r: _criterion(r, "potential_21nt_derived_windows").update(affects=["pareto"]))
    assert _mutated(lambda r: r["policy"]["small_rna_descriptor"].update(decisional=True))


def test_every_pre_registered_descriptor_is_a_pure_descriptor():
    for name in sorted(crit.REQUIRED_DESCRIPTORS):
        criterion = _criterion(REGISTRY, name)
        assert criterion["roles"] == ["DESCRIPTOR"], name
        assert set(criterion["affects"]) <= {"comparison_scope"}, name
    assert crit.REQUIRED_DESCRIPTORS <= set(REGISTRY["policy"]["descriptive_only_criteria"])
    assert {"target_region_position", "other_transcript_hits", "benchmark_relation", "fraction_unaffected"} <= set(REGISTRY["policy"]["cell_signature_excludes"])


# ------------------------------------------------------------------ units
def test_unit_taxonomy_and_roles_are_frozen():
    units = REGISTRY["policy"]["specificity_units"]
    assert {n: u["role"] for n, u in units.items()} == crit.UNIT_ROLE_BY_NAME
    assert units["KNOWN_BICC_COMPATIBLE"]["members"] == ["GITV01000968.1", "TRINITY_DN24799_c0_g1_i7"]
    assert units["BICC_LIKE"]["members"] == ["GITV01002238.1"] and units["BICC_LIKE"]["relationship_status"] == "UNRESOLVED"
    assert units["DSRNASE2"]["members"] == ["GITV01008430.1", "GITV01012450.1", "TRINITY_DN22752_c0_g2_i1"]
    assert units["DSRNASE2"]["role"] == "CO_TARGET_DECISIONAL_INTERPRETABILITY"
    assert units["DSRNASE1"]["role"] == units["DSRNASE3"]["role"] == "DESCRIPTIVE_ONLY"
    assert units["OTHER_TRANSCRIPT"]["role"] == "DESCRIPTIVE_PLUS_MANUAL_REVIEW"
    assert REGISTRY["policy"]["unit_aggregation"]["pool_across_units"] is False
    other = _criterion(REGISTRY, "other_transcript_specificity")
    assert set(other["roles"]) == {"DESCRIPTOR", "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW"} and other["affects"] == ["shortlist_gate"]


def test_unit_mutations_are_rejected():
    assert _mutated(lambda r: r["policy"]["specificity_units"]["BICC_LIKE"].update(relationship_status="PARALOG"))
    assert _mutated(lambda r: r["policy"]["specificity_units"]["DSRNASE1"].update(role="DECISIONAL_INTERPRETABILITY"))
    assert _mutated(lambda r: r["policy"]["specificity_units"]["OTHER_TRANSCRIPT"].update(role="DECISIONAL_INTERPRETABILITY"))
    assert _mutated(lambda r: r["policy"]["specificity_units"]["DSRNASE2"]["members"].append("GITV01002238.1"))
    assert _mutated(lambda r: _criterion(r, "other_transcript_specificity").update(affects=["pareto", "shortlist_gate"]))
    assert _mutated(lambda r: r["policy"]["cell_signature"].append("other_transcript_hits"))


# ------------------------------------------------------------------ membership decisions
def _rows():
    return crit.load_membership_decisions(ROOT / crit.MEMBERSHIP_PATH)


def test_membership_loads_validates_and_matches_the_registry():
    rows = _rows()
    assert crit.validate_membership(rows, REGISTRY, PIN, ROOT) == []
    assert crit.load_validated_membership(ROOT)
    by_record = {r.record_id: r for r in rows}
    like = by_record["GITV01002238.1"]
    assert (like.unit, like.relationship_status, like.decision) == ("BICC_LIKE", "UNRESOLVED", "ACCEPTED")
    assert all(crit.HEX64.match(r.evidence_sha256) and r.decided_by and r.decided_utc and r.rationale for r in rows)


def test_membership_requires_a_real_evidence_sha256(tmp_path):
    header = "\t".join(crit.MEMBERSHIP_COLUMNS)
    good = "GITV01002238.1\tBICC_LIKE\tUNRESOLVED\tACCEPTED\twhy\tx\t" + "a" * 64 + "\tme\t2026-10-08T00:00:00Z"
    path = tmp_path / "m.tsv"
    for bad in (good.replace("a" * 64, ""), good.replace("a" * 64, "not-a-hash"), good.replace("UNRESOLVED", "PARALOG"),
                good.replace("ACCEPTED", "MAYBE"), good.replace("\tme\t", "\t\t")):
        path.write_text(header + "\n" + bad + "\n", encoding="utf-8")
        with pytest.raises(crit.NB03MembershipError):
            crit.load_membership_decisions(path)
    path.write_text(header + "\n" + good + "\n" + good + "\n", encoding="utf-8")
    with pytest.raises(crit.NB03MembershipError, match="more than once"):
        crit.load_membership_decisions(path)
    path.write_text("a\tb\n", encoding="utf-8")
    with pytest.raises(crit.NB03MembershipError, match="columns"):
        crit.load_membership_decisions(path)


def test_membership_evidence_hash_must_be_real_not_invented():
    rows = _rows()
    forged = [crit.MembershipDecision(**{**r.__dict__, "evidence_sha256": "0" * 64}) if r.record_id == "GITV01002238.1" else r for r in rows]
    problems = crit.validate_membership(forged, REGISTRY, PIN, ROOT)  # message depends on whether the gitignored file exists locally
    assert problems and all("evidence_sha256" in p for p in problems)
    wrong_versioned = [crit.MembershipDecision(**{**r.__dict__, "evidence_sha256": "1" * 64}) if r.record_id == "GITV01008430.1" else r for r in rows]
    assert any("does not match" in p for p in crit.validate_membership(wrong_versioned, REGISTRY, PIN, ROOT))
    assert any("differ" in p for p in crit.validate_membership(rows[:-1], REGISTRY, PIN, ROOT))
    wrong_status = [crit.MembershipDecision(**{**r.__dict__, "relationship_status": "NOT_APPLICABLE"}) if r.unit == "BICC_LIKE" else r for r in rows]
    assert any("relationship_status" in p for p in crit.validate_membership(wrong_status, REGISTRY, PIN, ROOT))


def test_membership_evidence_hashes_of_cp0_outputs_are_registered_in_the_pin():
    registered = {k: v for k, v in PIN["cp0_outputs_sha256"].items() if k != "note"}
    cp0_rows = [r for r in _rows() if r.evidence_source.startswith("results/")]
    assert cp0_rows and all(registered[Path(r.evidence_source).name] == r.evidence_sha256 for r in cp0_rows)


# ------------------------------------------------------------------ nothing from CP2 exists
def test_adr_accepts_only_the_preregistration_policy_through_cp1():
    path = ROOT / "src/workstreams/bioinformatics/decisions/0006-nb03-bicc-candidate-region-policy.md"
    adr = path.read_text(encoding="utf-8")
    assert adr.split("## Status\n\n", 1)[1].splitlines()[0] == "Accepted"
    assert adr.split("## Estado\n\n", 1)[1].splitlines()[0] == "Accepted"
    assert "ACCEPTED_FOR_NB03_PREREGISTRATION" not in adr
    assert "This ADR accepts the NB03 preregistration policy through CP1." in adr
    assert "It does not imply acceptance of downstream candidate-selection results, which remain pending CP2–CP5." in adr


def test_no_candidate_window_artifact_is_versioned():
    assert not list((ROOT / "data/reference").glob("nb03_*candidate*"))
    assert not (ROOT / "config/nb03_manual_review_decisions.tsv").exists()
    assert REGISTRY["policy"]["manual_review_decisions"]["created_at"] == "CP4"


# ------------------------------------------------------------------ real data (shared CP0 run)
def test_pin_is_reproduced_from_the_tsa_anchors_and_pinned_primers(cp0_result, tmp_path):
    report = crit.verify_pin(ROOT, tmp_path)
    assert report["tsa_file_sha256"] == PIN["tsa"]["file_sha256"]


def test_pin_registered_cp0_hashes_equal_a_fresh_cp0_run(cp0_result):
    fresh = cp0_result["result"]["manifest"]["outputs_sha256"]
    registered = {k: v for k, v in PIN["cp0_outputs_sha256"].items() if k != "note"}
    assert registered == fresh


def test_verify_pin_fails_when_the_pin_disagrees_with_the_derivation(cp0_result, tmp_path, monkeypatch):
    pin = copy.deepcopy(PIN)
    pin["operational_reference"]["cds_tx_start"] = 66
    pin["operational_reference"]["cds_tx_end"] = 2402
    monkeypatch.setattr(crit, "load_pin", lambda root: pin)
    with pytest.raises(crit.NB03PinError, match="not reproduced"):
        crit.verify_pin(ROOT, tmp_path)
