"""Contract tests for NB03 CP4B: the human decision record is validated and materialized, never re-derived.

The synthetic block uses invented window ids and invented descriptor values; the real-data block checks that the
frozen record in ``config/nb03_manual_review_decisions.tsv`` materializes into the shortlist it declares. The frozen
ids appear in the regression snapshot because they are a human result, not a scientific policy of this code.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from zeaguard import nb03_manual_review as review, nb03_selection as sel

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY = {"OTHER_TRANSCRIPT": ["APPROVED", "STRONG_INTRASPECIES_SPECIFICITY_CONCERN"],
              "BICC_LIKE": ["APPROVED", "STRONG_SPECIFICITY_CONCERN"],
              "DSRNASE2": ["APPROVED", "STRONG_SPECIFICITY_CONCERN"]}
HASH_A, HASH_B, HASH_C = ("a" * 64, "b" * 64, "c" * 64)


def decision(window_id, disposition=review.ADVANCE, role="PRIMARY_CANDIDATE_PROVISIONAL", **kwargs):
    base = dict(window_id=window_id, review_disposition=disposition, decision_role=role,
                other_transcript_decision="APPROVED", bicc_like_decision="APPROVED",
                manual_reviewer_basis="HUMAN_ADJUDICATED_OUTSIDE_ALGORITHM",
                other_transcript_interpretation="synthetic", bicc_like_interpretation="synthetic",
                observed_difference_interpretation="synthetic", relationship_status="UNRESOLVED",
                rationale="synthetic", reviewer="Tester", decided_utc="2026-01-01T00:00:00Z",
                evidence_packet_sha256=HASH_A, other_transcript_hsp_reference_sha256=HASH_B,
                bicc_like_hsp_reference_sha256=HASH_C)
    return review.ReviewDecision(**{**base, **kwargs})


def write_record(path, decisions):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(review.DECISION_COLUMNS)
        for item in decisions:
            writer.writerow([getattr(item, c) for c in review.DECISION_COLUMNS])
    return path


# ------------------------------------------------------------------ synthetic: the record is the only source
def test_the_disposition_vocabulary_is_closed_and_each_role_belongs_to_one_disposition():
    items = [decision("W1"), decision("W2", review.HOLD, "RESERVE")]
    assert review.DISPOSITIONS == (review.ADVANCE, review.HOLD, review.EXCLUDE)
    assert set(review.ROLES_BY_DISPOSITION) == set(review.DISPOSITIONS)
    roles = [role for group in review.ROLES_BY_DISPOSITION.values() for role in group]
    assert len(roles) == len(set(roles))
    assert items[0].advances and not items[1].advances


def test_loading_rejects_unknown_dispositions_roles_scope_decisions_hashes_and_blanks(tmp_path):
    good = write_record(tmp_path / "ok.tsv", [decision("W1")])
    assert set(review.load_decisions(good, VOCABULARY)) == {"W1"}
    bad_rows = {
        "disposition": decision("W1", "MAYBE"),
        "role": decision("W1", review.ADVANCE, "RESERVE"),
        "scope": decision("W1", other_transcript_decision="LOOKS_FINE"),
        "relationship": decision("W1", relationship_status="PARALOG"),
        "hash": decision("W1", evidence_packet_sha256="not-a-hash"),
        "blank": decision("W1", rationale="   "),
    }
    for label, item in bad_rows.items():
        path = write_record(tmp_path / f"{label}.tsv", [item])
        with pytest.raises(review.NB03ManualReviewError):
            review.load_decisions(path, VOCABULARY)


def test_loading_rejects_a_duplicate_window_and_a_different_column_set(tmp_path):
    duplicate = write_record(tmp_path / "dup.tsv", [decision("W1"), decision("W1", review.HOLD, "RESERVE")])
    with pytest.raises(review.NB03ManualReviewError):
        review.load_decisions(duplicate, VOCABULARY)
    renamed = (tmp_path / "cols.tsv")
    renamed.write_text("window_id\tdisposition\n W1\tADVANCE_TO_SHORTLIST\n", encoding="utf-8")
    with pytest.raises(review.NB03ManualReviewError):
        review.load_decisions(renamed, VOCABULARY)


def test_a_strong_concern_must_exclude_and_advancing_needs_the_required_scope_approved(tmp_path):
    concern = decision("W1", bicc_like_decision="STRONG_SPECIFICITY_CONCERN")
    with pytest.raises(review.NB03ManualReviewError):
        review.load_decisions(write_record(tmp_path / "a.tsv", [concern]), VOCABULARY)
    excluded = dataclasses.replace(concern, review_disposition=review.EXCLUDE, decision_role="EXCLUDED_AFTER_REVIEW")
    assert review.load_decisions(write_record(tmp_path / "b.tsv", [excluded]), VOCABULARY)["W1"].review_disposition == review.EXCLUDE
    not_approved = decision("W1", other_transcript_decision="STRONG_INTRASPECIES_SPECIFICITY_CONCERN")
    with pytest.raises(review.NB03ManualReviewError):
        review.load_decisions(write_record(tmp_path / "c.tsv", [not_approved]), VOCABULARY)


def test_resolve_requires_an_exact_one_to_one_match_with_the_reviewed_scope():
    decisions = {"W1": decision("W1"), "W2": decision("W2", review.HOLD, "RESERVE")}
    assert [d.window_id for d in review.resolve(["W2", "W1"], decisions)] == ["W2", "W1"]
    with pytest.raises(review.NB03ManualReviewError):  # a reviewed window without a decision
        review.resolve(["W1", "W2", "W3"], decisions)
    with pytest.raises(review.NB03ManualReviewError):  # a decision for a window outside the reviewed scope
        review.resolve(["W1"], decisions)
    with pytest.raises(review.NB03ManualReviewError):  # a duplicated reviewed id
        review.resolve(["W1", "W1", "W2"], decisions)


def test_the_shortlist_and_the_counts_follow_the_record_and_nothing_else():
    items = [decision("W1"), decision("W2", review.HOLD, "RESERVE"),
             decision("W3", review.ADVANCE, "SECONDARY_REGION_EQUIVALENT_ALTERNATIVE"),
             decision("W4", review.HOLD, "HOLD_FOR_BACKGROUND_INTERPRETABILITY")]
    assert [d.window_id for d in review.shortlist(items)] == ["W1", "W3"]
    assert review.disposition_counts(items) == {review.ADVANCE: 2, review.HOLD: 2, review.EXCLUDE: 0}
    assert review.role_counts(items)["RESERVE"] == 1 and review.role_counts(items)["EXCLUDED_AFTER_REVIEW"] == 0
    flipped = [dataclasses.replace(items[1], review_disposition=review.ADVANCE, decision_role="PRIMARY_CANDIDATE_PROVISIONAL"),
               *items[2:]]
    assert [d.window_id for d in review.shortlist(flipped)] == ["W2", "W3"]


def test_the_module_hardcodes_no_window_id_and_compares_no_descriptor_to_a_number():
    source = (ROOT / "src/zeaguard/nb03_manual_review.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert "BC-L400-" not in code and "BC-BENCH" not in code
    for descriptor in ("exact_19mer", "exact_21mer", "longest_exact_match", "covered_nt", "best_local_identity",
                       "n_hsps", "n_subject_records", "evalue", "bitscore", "subject_accessions", "benchmark_comparison"):
        for operator in (">", "<", ">=", "<=", "=="):
            assert f'{descriptor}"] {operator}' not in code and f"{descriptor} {operator}" not in code


def test_shared_positions_is_an_inclusive_intersection():
    assert review._shared_positions([(1253, 1652), (1254, 1653)]) == 399
    assert review._shared_positions([(1, 400), (900, 1000)]) == 0
    assert review._shared_positions([(1, 400)]) == 0


# ------------------------------------------------------------------ real frozen record and CP4A evidence
HAS_REAL = all((ROOT / "results/bioinformatics/nb03" / name).exists()
               for name in ("cp4a/manual_review_packet.tsv", "cp4a/bicc_like_hsp_reference.tsv", "cp3/queries/L400.fasta"))
FROZEN_SHORTLIST = ("BC-L400-1337-1736", "BC-L400-1253-1652", "BC-L400-1254-1653")
FROZEN_HELD = ("BC-L400-1614-2013", "BC-L400-1195-1594", "BC-L400-1196-1595",
               "BC-L400-0991-1390", "BC-L400-1012-1411", "BC-L400-1021-1420", "BC-L400-1039-1438")


def read(directory, name):
    with (Path(directory) / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    if not HAS_REAL:
        pytest.skip("needs the frozen CP4A evidence and the certified CP3 query FASTA")
    first, second = tmp_path_factory.mktemp("cp4b_first"), tmp_path_factory.mktemp("cp4b_second")
    result = review.run_cp4b(ROOT, first)
    review.run_cp4b(ROOT, second)
    return SimpleNamespace(result=result, first=first, second=second,
                           resolved=read(first, "manual_review_resolved.tsv"), short=read(first, "shortlist.tsv"),
                           summary=json.loads((first / "cp4b_summary.json").read_text(encoding="utf-8")),
                           packet=read(ROOT / "results/bioinformatics/nb03/cp4a", "manual_review_packet.tsv"))


def test_real_record_covers_the_reviewed_scope_exactly(real):
    ids = [r["window_id"] for r in read(ROOT / "config", "nb03_manual_review_decisions.tsv")]
    assert len(ids) == len(set(ids)) == 10
    assert set(ids) == {r["window_id"] for r in real.packet}
    assert [r["window_id"] for r in real.resolved] == [r["window_id"] for r in real.packet]


def test_real_counts_are_three_advance_seven_hold_and_no_exclude(real):
    assert (real.summary["n_reviewed"], real.summary["n_advance"], real.summary["n_hold"], real.summary["n_exclude"]) == (10, 3, 7, 0)
    assert real.summary["roles"]["EXCLUDED_AFTER_REVIEW"] == 0
    assert (real.summary["n_primary"], real.summary["n_secondary_equivalent_alternatives"],
            real.summary["n_reserve"], real.summary["n_background_hold"]) == (1, 2, 2, 5)
    assert {r["review_disposition"] for r in real.resolved} == {review.ADVANCE, review.HOLD}


def test_real_shortlist_holds_exactly_the_three_frozen_windows(real):
    assert tuple(real.summary["shortlist_ids"]) == FROZEN_SHORTLIST
    assert tuple(r["window_id"] for r in real.short) == FROZEN_SHORTLIST
    assert all(w not in real.summary["shortlist_ids"] for w in FROZEN_HELD)
    bounds = real.summary["recommended_candidates_bounds"]
    assert bounds["min"] <= len(real.short) <= bounds["max"]


def test_real_both_secondary_alternatives_stay_and_neither_is_preferred(real):
    secondary = [r["window_id"] for r in real.short if r["decision_role"] == "SECONDARY_REGION_EQUIVALENT_ALTERNATIVE"]
    assert secondary == ["BC-L400-1253-1652", "BC-L400-1254-1653"]
    assert real.summary["secondary_region_preference"] == "UNRESOLVED"
    assert "399 of 400" in real.summary["secondary_region_note"]
    assert "automatic_choice_between_the_secondary_alternatives" in real.summary["not_executed"]


def test_real_shortlist_fasta_has_three_distinct_certified_400_nt_sequences(real):
    text = (real.first / "shortlist.fasta").read_text(encoding="utf-8")
    assert "\r" not in text
    names, sequences = [], []
    for line in text.splitlines():
        (names if line.startswith(">") else sequences).append(line.lstrip(">"))
    assert tuple(names) == FROZEN_SHORTLIST and len(sequences) == 3
    assert {len(s) for s in sequences} == {400} and len(set(sequences)) == 3
    assert all(set(s) <= set("ACGT") for s in sequences)
    by_id = dict(zip(names, sequences))
    assert by_id["BC-L400-1253-1652"][1:] == by_id["BC-L400-1254-1653"][:-1]  # 399 shared CDS positions
    hashes = {r["window_id"]: r["sequence_sha256"] for r in real.short}
    cp2 = {r["window_id"]: r for r in read(ROOT / "results/bioinformatics/nb03/cp2", "design_space.tsv")}
    assert all(hashes[w] == cp2[w]["sequence_sha256"] for w in FROZEN_SHORTLIST)
    assert all(r["sequence_length_nt"] == "400" for r in real.short)


def test_real_no_held_window_reaches_the_shortlist_files(real):
    for name in ("shortlist.tsv", "shortlist.fasta"):
        text = (real.first / name).read_text(encoding="utf-8")
        assert all(held not in text for held in FROZEN_HELD), name


def test_real_dispositions_come_from_the_record_and_not_from_the_descriptors(real, tmp_path):
    """Rewriting the record flips the shortlist even though every descriptor is unchanged."""
    original = {r["window_id"]: r for r in read(ROOT / "config", "nb03_manual_review_decisions.tsv")}
    swapped = []
    for window_id, row in original.items():
        item = review.ReviewDecision(**{c: row[c] for c in review.DECISION_COLUMNS})
        if window_id == "BC-L400-1337-1736":
            item = dataclasses.replace(item, review_disposition=review.HOLD, decision_role="RESERVE")
        elif window_id == "BC-L400-1614-2013":
            item = dataclasses.replace(item, review_disposition=review.ADVANCE, decision_role="PRIMARY_CANDIDATE_PROVISIONAL")
        swapped.append(item)
    resolved = review.resolve([r["window_id"] for r in real.packet], {d.window_id: d for d in swapped})
    assert [d.window_id for d in review.shortlist(resolved)] == ["BC-L400-1614-2013", "BC-L400-1253-1652", "BC-L400-1254-1653"]
    assert review.disposition_counts(resolved) == {review.ADVANCE: 3, review.HOLD: 7, review.EXCLUDE: 0}


def test_real_no_scope_concern_was_recorded_and_the_unreviewed_scope_is_declared(real):
    assert real.summary["scope_decisions"] == {"OTHER_TRANSCRIPT": {"APPROVED": 10}, "BICC_LIKE": {"APPROVED": 10}}
    assert real.summary["registry_scopes"]["not_adjudicated"] == ["DSRNASE2"]
    assert real.summary["registry_scopes"]["required_scope_for_recommendation"] == "OTHER_TRANSCRIPT"
    # every mention of off-target in a rationale is a negation, never an assertion that one was confirmed
    assert all(" not " in r["rationale"] or "does not" in r["rationale"]
               for r in real.resolved if "off-target" in r["rationale"])
    assert all("STRONG_" not in r[column] for r in real.resolved
               for column in ("other_transcript_decision", "bicc_like_decision"))


def test_real_descriptors_are_carried_through_unchanged_and_never_gate_the_outcome(real):
    """The packet's OTHER_TRANSCRIPT, k-mer and BICC_LIKE values appear verbatim; held and advanced windows share them."""
    packet = {r["window_id"]: r for r in real.packet}
    carried = ("other_transcript_n_hsps", "other_transcript_covered_nt", "other_transcript_longest_exact_match",
               "exact_19mer_other_transcript", "exact_21mer_other_transcript", "bicc_like_longest_exact_match",
               "bicc_like_covered_nt", "bicc_like_best_local_identity", "pareto_status", "difference_tier")
    for row in real.resolved:
        assert all(row[c] == packet[row["window_id"]][c] for c in carried)
    advanced = {r["window_id"] for r in real.resolved if r["review_disposition"] == review.ADVANCE}
    # the same longest exact tract (17) and the same zero k-mer counts occur on both sides of the disposition,
    # so no cutoff on those descriptors can explain the split
    tracts = {side: {packet[w]["other_transcript_longest_exact_match"] for w in packet if (w in advanced) == (side == "advanced")}
              for side in ("advanced", "held")}
    assert "17" in tracts["advanced"] and "17" in tracts["held"]
    assert {packet[w]["exact_19mer_other_transcript"] for w in advanced} == {"0"}
    assert any(packet[w]["exact_19mer_other_transcript"] == "0" for w in packet if w not in advanced)


def test_real_benchmark_takes_no_part_in_the_outcome(real):
    text = json.dumps(real.summary) + (real.first / "manual_review_resolved.tsv").read_text(encoding="utf-8")
    assert "BC-BENCH" not in text
    assert "descriptive reference only" in " ".join(real.summary["statements"])
    assert not [c for c in real.short[0] if "benchmark" in c and c != "relation_to_benchmark"]


def test_real_outputs_are_byte_identical_on_rerun_and_metadata_stays_separate(real):
    for name in (*review.DETERMINISTIC_OUTPUTS, "run_manifest.json"):
        assert (real.first / name).read_bytes() == (real.second / name).read_bytes(), name
    assert (real.first / "execution_metadata.json").read_bytes() != (real.second / "execution_metadata.json").read_bytes()
    manifest = (real.first / "run_manifest.json").read_text(encoding="utf-8")
    assert str(real.first) not in manifest and "utc" not in manifest.lower()
    assert review.CP4A_COMMIT == "fe311344cbea9c6b527013090b715eccd5c9ba4a"
    assert real.result["manifest"]["selection_policy_commit"] == sel.SELECTION_POLICY_COMMIT


def test_real_frozen_evidence_hashes_are_the_ones_the_reviewer_signed(real):
    certified = real.result["manifest"]["inputs"]["certified_input_sha256"]
    for row in real.resolved:
        assert row["evidence_packet_sha256"] == certified["cp4a/manual_review_packet.tsv"]
        assert row["other_transcript_hsp_reference_sha256"] == certified["cp4a/other_transcript_hsp_reference.tsv"]
        assert row["bicc_like_hsp_reference_sha256"] == certified["cp4a/bicc_like_hsp_reference.tsv"]
    assert certified["cp4a/bicc_like_hsp_reference.tsv"] == review.BICC_LIKE_HSP_REFERENCE_SHA256
    assert certified["cp4a/run_manifest.json"] == review.CP4A_MANIFEST_SHA256


def test_real_cp4a_outputs_are_untouched_by_this_checkpoint(real):
    cp4a = ROOT / "results/bioinformatics/nb03/cp4a"
    manifest = json.loads((cp4a / "run_manifest.json").read_text(encoding="utf-8"))
    certified = real.result["manifest"]["inputs"]["certified_input_sha256"]
    assert all(certified[f"cp4a/{name}"] == expected for name, expected in manifest["outputs_sha256"].items())
    assert not (cp4a / "shortlist.tsv").exists() and not (cp4a / "manual_review_resolved.tsv").exists()


def test_real_no_wet_lab_handoff_was_materialized(real):
    for name in ("nb03_bicc_candidate_regions.tsv", "nb03_bicc_candidate_regions.fasta"):
        assert not (ROOT / "data/reference" / name).exists()
    assert "wet_lab_handoff" in real.summary["not_executed"] and "CP5" in real.summary["not_executed"]
