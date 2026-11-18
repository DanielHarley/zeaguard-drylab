"""Tests for the per-accession dsRNase-2 mapping: the BTOP walk and the audit.

The cases this round requires explicitly: a reverse-strand HSP, both kinds of
gap, overlapping HSPs that agree on the base but disagree on the coordinate, and
two eligible loci for both queries.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SCRIPT = ROOT / "scripts" / "map_nb01_dsrnase2_by_accession.py"
_spec = importlib.util.spec_from_file_location("map_nb01_dsrnase2_by_accession", SCRIPT)
acc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = acc
_spec.loader.exec_module(acc)

from zeaguard.nb01_dsrnase_investigation import Hsp  # noqa: E402


def make_hsp(btop, qstart, qend, sstart, send, strand="plus", subject="chr1",
             query="q", length=None, mismatch=0, gaps=0, bitscore=100.0, qlen=1425):
    return Hsp(
        query=query, subject=subject, pident=100.0,
        length=length if length is not None else qend - qstart + 1,
        qlen=qlen, slen=1_000_000, qstart=qstart, qend=qend, sstart=sstart, send=send,
        strand=strand, evalue=0.0, bitscore=bitscore, mismatch=mismatch, gapopen=0,
        gaps=gaps, qcovs=100.0, btop=btop,
    )


# --------------------------------------------------------------------------- BTOP walk
def test_plus_strand_walk_lands_on_the_declared_end_coordinates():
    hsp = make_hsp("10", qstart=1, qend=10, sstart=501, send=510)
    columns = acc.walk_btop(hsp, "A" * 10)
    assert len(columns) == 10
    assert columns[0].query_pos == 1 and columns[0].subject_pos == 501
    assert columns[-1].query_pos == 10 and columns[-1].subject_pos == 510


def test_minus_strand_walk_decrements_the_subject_coordinate():
    # Query ascending 1..10, subject descending 510..501.
    hsp = make_hsp("10", qstart=1, qend=10, sstart=510, send=501, strand="minus")
    columns = acc.walk_btop(hsp, "A" * 10)
    assert [c.subject_pos for c in columns] == list(range(510, 500, -1))
    assert columns[0].query_pos == 1 and columns[0].subject_pos == 510
    assert columns[-1].query_pos == 10 and columns[-1].subject_pos == 501


def test_walk_refuses_a_btop_that_does_not_reach_the_declared_end():
    hsp = make_hsp("5", qstart=1, qend=10, sstart=501, send=510)
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.walk_btop(hsp, "A" * 10)
    assert "ended at query" in str(error.value)


def test_walk_refuses_a_descending_query():
    hsp = make_hsp("10", qstart=10, qend=1, sstart=501, send=510)
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.walk_btop(hsp, "A" * 10)
    assert "ascending" in str(error.value)


def test_walk_refuses_a_subject_running_against_its_declared_strand():
    hsp = make_hsp("10", qstart=1, qend=10, sstart=501, send=510, strand="minus")
    with pytest.raises(acc.AccessionMappingError):
        acc.walk_btop(hsp, "A" * 10)


# --------------------------------------------------------------------------- gaps
def test_gap_in_the_subject_advances_the_query_only():
    # BTOP "4" then "A-" (query A against a subject gap) then "5".
    # Query 1..10, subject 501..509: nine subject bases for ten query bases.
    hsp = make_hsp("4A-5", qstart=1, qend=10, sstart=501, send=509, gaps=1)
    columns = acc.walk_btop(hsp, "A" * 10)
    gap = columns[4]
    assert gap.op == "I"
    assert gap.query_pos == 5
    assert gap.subject_pos is None
    assert gap.subject_base == ""
    # The subject coordinate does not advance across the gap.
    assert columns[3].subject_pos == 504 and columns[5].subject_pos == 505
    assert acc.classify(gap.query_base, gap.subject_base) == acc.GAP_IN_SUBJECT


def test_gap_in_the_query_advances_the_subject_only_and_consumes_no_query_position():
    # BTOP "4" then "-G" (subject G against a query gap) then "5".
    # Query 1..9, subject 501..510: ten subject bases for nine query bases.
    hsp = make_hsp("4-G5", qstart=1, qend=9, sstart=501, send=510, gaps=1)
    columns = acc.walk_btop(hsp, "A" * 9)
    gap = columns[4]
    assert gap.op == "D"
    assert gap.query_pos is None          # no query position lands on a D column
    assert gap.subject_pos == 505
    # The query coordinate does not advance across the gap.
    assert columns[3].query_pos == 4 and columns[5].query_pos == 5
    assert [c.query_pos for c in columns if c.query_pos is not None] == list(range(1, 10))


def test_an_informative_position_opposite_a_subject_gap_is_not_a_mismatch():
    hsp = make_hsp("4A-5", qstart=1, qend=10, sstart=501, send=509, gaps=1)
    observed = acc.observe_positions(hsp, [5], "A" * 10)
    assert observed[5]["verdict"] == acc.GAP_IN_SUBJECT
    assert observed[5]["subject_pos"] is None


# --------------------------------------------------------------------------- classification
def test_classify_distinguishes_the_three_cases_and_the_gap():
    assert acc.classify("C", "C") == acc.EXACT
    assert acc.classify("Y", "C") == acc.AMBIGUITY_COMPATIBLE   # Y = C or T
    assert acc.classify("Y", "T") == acc.AMBIGUITY_COMPATIBLE
    assert acc.classify("Y", "A") == acc.AMBIGUITY_INCOMPATIBLE
    assert acc.classify("R", "G") == acc.AMBIGUITY_COMPATIBLE   # R = A or G
    assert acc.classify("C", "T") == acc.DEFINED_MISMATCH
    assert acc.classify("C", "") == acc.GAP_IN_SUBJECT


def test_an_ambiguous_genomic_base_is_neither_exact_nor_a_defined_mismatch():
    # The assembly does not state which base is there, so nothing exact has been
    # observed and nothing defined has been observed to differ.
    assert acc.classify("C", "N") == acc.SUBJECT_AMBIGUOUS
    assert acc.classify("C", "Y") == acc.SUBJECT_AMBIGUOUS
    assert acc.classify("A", "R") == acc.SUBJECT_AMBIGUOUS
    # Not promoted even when the symbols are identical on both sides.
    assert acc.classify("Y", "Y") == acc.SUBJECT_AMBIGUOUS
    # ... and an ambiguous subject never counts as agreement with its own options.
    assert acc.classify("C", "N") != acc.EXACT
    assert acc.classify("C", "N") != acc.DEFINED_MISMATCH
    assert acc.classify("Y", "N") not in (acc.AMBIGUITY_COMPATIBLE,
                                          acc.AMBIGUITY_INCOMPATIBLE)


def test_subject_ambiguity_is_counted_in_its_own_column_not_folded_into_the_others():
    hsp = make_hsp("3CN6", qstart=1, qend=10, sstart=501, send=510, mismatch=1)
    observed = acc.observe_positions(hsp, [4], "A" * 10)
    assert observed[4]["verdict"] == acc.SUBJECT_AMBIGUOUS
    assert observed[4]["subject_base"] == "N"


def test_substitution_column_reports_both_bases_and_the_minus_strand_complement():
    hsp = make_hsp("3YA6", qstart=1, qend=10, sstart=510, send=501,
                   strand="minus", mismatch=1)
    observed = acc.observe_positions(hsp, [4], "A" * 10)
    call = observed[4]
    assert call["query_base"] == "Y"
    assert call["subject_base"] == "A"              # in the query's orientation
    assert call["subject_base_plus_strand"] == "T"  # complement on the genome's plus strand
    assert call["subject_pos"] == 507
    assert call["verdict"] == acc.AMBIGUITY_INCOMPATIBLE  # Y is C or T, not A


# --------------------------------------------------------------------------- overlaps
def test_overlapping_hsps_agreeing_on_base_but_not_coordinate_conflict():
    same_base_elsewhere = [
        {"subject_sequence_id": "chr1", "subject_pos": 600, "strand": "plus",
         "subject_base": "C", "verdict": acc.EXACT},
        {"subject_sequence_id": "chr1", "subject_pos": 9400, "strand": "plus",
         "subject_base": "C", "verdict": acc.EXACT},
    ]
    call = acc.reconcile(same_base_elsewhere)
    assert call["verdict"] == acc.CONFLICTING_HSPS
    assert "600" in call["conflict_detail"] and "9400" in call["conflict_detail"]
    assert call["n_hsps_covering"] == 2


def test_overlapping_hsps_agreeing_on_base_but_not_strand_conflict():
    call = acc.reconcile([
        {"subject_sequence_id": "chr1", "subject_pos": 600, "strand": "plus",
         "subject_base": "C", "verdict": acc.EXACT},
        {"subject_sequence_id": "chr1", "subject_pos": 600, "strand": "minus",
         "subject_base": "C", "verdict": acc.EXACT},
    ])
    assert call["verdict"] == acc.CONFLICTING_HSPS


def test_overlapping_hsps_that_agree_on_everything_collapse_to_one_call():
    observation = {"subject_sequence_id": "chr1", "subject_pos": 600, "strand": "plus",
                   "subject_base": "C", "verdict": acc.EXACT}
    call = acc.reconcile([dict(observation), dict(observation)])
    assert call["verdict"] == acc.EXACT
    assert call["n_hsps_covering"] == 2
    assert "conflict_detail" not in call


def test_a_position_no_hsp_covers_is_reported_as_no_coverage():
    call = acc.reconcile([])
    assert call["verdict"] == acc.NO_COVERAGE
    assert call["n_hsps_covering"] == 0


def test_two_overlapping_hsps_on_one_candidate_are_both_recorded():
    # The tiling tolerates a few nucleotides of query overlap, so query position
    # 10 is covered twice, at two different genomic coordinates.
    left = make_hsp("10", qstart=1, qend=10, sstart=501, send=510)
    right = make_hsp("10", qstart=10, qend=19, sstart=9001, send=9010)
    candidate = acc.Candidate(
        assembly_id="A", query_id="q", candidate_id="A:q:1", subject="chr1",
        strand="plus", start=501, end=9010, coverage_pct=100.0, identity_pct=100.0,
        aligned_nt=20, matched_nt=20, mismatch_nt=0, gaps_nt=0, n_hsps=2,
        hsps=[left, right])
    audited, observations = acc.audit_candidate(candidate, [10], "A" * 20)
    assert audited[10]["verdict"] == acc.CONFLICTING_HSPS
    assert audited[10]["n_hsps_covering"] == 2

    # The individual observations are persisted, each carrying its own HSP id,
    # and the summary names both of them.
    assert len(observations) == 2
    ids = [o["hsp_id"] for o in observations]
    assert len(set(ids)) == 2
    assert all(i.startswith("A:q:1#hsp") for i in ids)
    assert sorted(o["subject_pos"] for o in observations) == [510, 9001]
    for identifier in ids:
        assert identifier in audited[10]["observed_by_hsps"]


# --------------------------------------------------------------------------- assignment
def make_candidate(candidate_id, start, end, coverage=100.0, identity=100.0, subject="chr1",
                   strand="plus", blocks=None, query_order=None):
    """A candidate built from real HSPs, so its chain is the real correspondence.

    ``blocks`` are genomic intervals; ``query_order`` gives the index of the
    query block each one carries, so the same genomic blocks can be laid down in
    a different order along the query.
    """
    if blocks is None:
        blocks = [(start, end)]
    if query_order is None:
        query_order = list(range(len(blocks)))
    hsps = [make_hsp("1", qstart=1 + 10 * slot, qend=10 + 10 * slot,
                     sstart=a if strand == "plus" else b,
                     send=b if strand == "plus" else a,
                     strand=strand, subject=subject, length=10)
            for slot, (a, b) in zip(query_order, blocks)]
    return acc.Candidate(
        assembly_id="A", query_id="q", candidate_id=candidate_id, subject=subject,
        strand=strand, start=start, end=end, coverage_pct=coverage, identity_pct=identity,
        aligned_nt=1425, matched_nt=1425, mismatch_nt=0, gaps_nt=0, n_hsps=len(hsps),
        hsps=hsps)


def test_no_hsps_is_reported_apart_from_no_eligible_candidate():
    status, reason, eligible = acc.assignment_status([], had_hsps=False)
    assert (status, reason, eligible) == (acc.INDETERMINATE, "NO_HSPS", [])

    # HSPs existed, but nothing reached the assignment tier.
    weak = make_candidate("A:q:1", 500, 2000, coverage=60.0, identity=99.0)
    assert not weak.eligible
    status, reason, eligible = acc.assignment_status([weak], had_hsps=True)
    assert status == acc.INDETERMINATE
    assert reason == "NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA"
    assert eligible == []


def test_identity_below_the_threshold_is_not_eligible_even_at_full_coverage():
    assert not make_candidate("A:q:1", 1, 2, coverage=100.0, identity=97.9).eligible
    assert make_candidate("A:q:1", 1, 2, coverage=100.0, identity=98.0).eligible


def test_one_eligible_candidate_is_determined():
    status, reason, eligible = acc.assignment_status(
        [make_candidate("A:q:1", 500, 2000)], had_hsps=True)
    assert status == acc.DETERMINED
    assert reason == "ONE_LOCUS_MEETS_ASSIGNMENT_CRITERIA"
    assert len(eligible) == 1


# --------------------------------------------------------------------------- pair verdict
def determined(locus):
    return {"status": acc.DETERMINED, "status_reason": "ONE_LOCUS_MEETS_ASSIGNMENT_CRITERIA",
            "locus": locus}


def test_two_eligible_loci_for_both_queries_leave_the_pair_indeterminate():
    # Both queries have two eligible loci, so neither is assigned.
    statuses = {}
    for query_id in ("dsRNase-2@GITV01008430.1", "dsRNase-2@GITV01012450.1"):
        status, reason, eligible = acc.assignment_status(
            [make_candidate(f"A:{query_id}:1", 500, 2000),
             make_candidate(f"A:{query_id}:2", 80_000, 81_500)], had_hsps=True)
        assert status == acc.INDETERMINATE
        assert reason == "MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA"
        statuses[query_id] = {"status": status, "status_reason": reason, "locus": None}

    # ... and 816 favouring a specific association does not rescue it.
    discriminating = {
        query_id: [
            {"candidate_id": f"A:{query_id}:1", "verdict": acc.EXACT, "subject_base": base},
            {"candidate_id": f"A:{query_id}:2", "verdict": acc.EXACT, "subject_base": base},
        ]
        for query_id, base in (("dsRNase-2@GITV01008430.1", "C"),
                               ("dsRNase-2@GITV01012450.1", "T"))
    }
    verdict = acc.pair_verdict(statuses, discriminating, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["alignment_reason"].startswith("UNASSIGNED_QUERY:")
    assert "MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA" in verdict["alignment_reason"]
    # The evidence at 816 is still reported, per candidate, for both eligible
    # candidates of each query.
    for query_id, base in (("dsRNase-2@GITV01008430.1", "C"),
                           ("dsRNase-2@GITV01012450.1", "T")):
        assert verdict[f"evidence816_{query_id}_n_eligible_candidates"] == 2
        evidence = verdict[f"evidence816_{query_id}_calls"]
        assert evidence.count(";") == 1, "one entry per eligible candidate"
        assert f"={base}/{acc.EXACT}" in evidence
        assert ":1=" in evidence and ":2=" in evidence


def test_same_span_same_strand_and_concordant_chain_supports_one_shared_locus():
    blocks = [(69_024_822, 69_024_887), (69_037_168, 69_037_412)]
    a = make_candidate("A:a:1", 69_024_822, 69_037_412, blocks=blocks)
    b = make_candidate("A:b:1", 69_024_822, 69_037_412, blocks=blocks)
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, {}, 816)
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["alignment_reason"] == "FAVOURS_SHARED_LOCUS_IN_THIS_ASSEMBLY"
    assert verdict["geometry_same_span"] is True
    assert verdict["geometry_chains_concordant"] is True


def test_same_bounds_on_opposite_strands_is_not_a_shared_locus():
    # Both chains are colinear on their own strand, so colinearity cannot be the
    # reason: the plus chain advances along the genome as the query advances, the
    # minus chain recedes. The strand is the only thing left to reject them.
    a = make_candidate("A:a:1", 1_000, 2_400, strand="plus",
                       blocks=[(1_000, 1_200), (2_000, 2_400)], query_order=[0, 1])
    b = make_candidate("A:b:1", 1_000, 2_400, strand="minus",
                       blocks=[(2_000, 2_400), (1_000, 1_200)], query_order=[0, 1])
    assert a.colinear is True and b.colinear is True

    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["alignment_reason"] == "SAME_SPAN_OPPOSITE_STRAND"
    assert verdict["geometry_same_span"] is True
    assert verdict["geometry_same_strand"] is False
    assert verdict["geometry_colinear_a"] is True
    assert verdict["geometry_colinear_b"] is True
    assert verdict["origin_status"] == acc.INDETERMINATE


def test_same_bounds_with_different_internal_blocks_is_not_a_shared_locus():
    a = make_candidate("A:a:1", 1_000, 2_400, strand="plus",
                       blocks=[(1_000, 1_200), (2_000, 2_400)])
    b = make_candidate("A:b:1", 1_000, 2_400, strand="plus",
                       blocks=[(1_000, 1_500), (1_900, 2_400)])
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["alignment_reason"] == "SAME_SPAN_DISCORDANT_BLOCKS"
    assert verdict["geometry_same_span"] is True
    assert verdict["geometry_same_strand"] is True
    assert verdict["geometry_chains_concordant"] is False
    assert verdict["geometry_same_genomic_blocks"] is False
    assert verdict["geometry_n_blocks_a"] == verdict["geometry_n_blocks_b"] == 2


def test_concordant_chains_short_of_full_coverage_favour_sharing_but_not_an_origin():
    # 1,424 of 1,425 nt covered: eligible, assigned, geometrically concordant --
    # and position 816 is the one position no HSP reaches, in both queries.
    blocks = [(69_024_822, 69_024_887), (69_037_168, 69_037_412)]
    a = make_candidate("A:a:1", 69_024_822, 69_037_412, blocks=blocks,
                       coverage=round(100 * 1424 / 1425, 3))
    b = make_candidate("A:b:1", 69_024_822, 69_037_412, blocks=blocks,
                       coverage=round(100 * 1424 / 1425, 3))
    assert a.eligible and b.eligible, "1,424/1,425 nt clears the 90 % coverage tier"

    uncovered = {
        "a": [{"candidate_id": "A:a:1", "verdict": acc.NO_COVERAGE}],
        "b": [{"candidate_id": "A:b:1", "verdict": acc.NO_COVERAGE}],
    }
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, uncovered, 816)

    # The geometric concordance is preserved and reported.
    assert verdict["geometry_same_span"] is True
    assert verdict["geometry_same_strand"] is True
    assert verdict["geometry_chains_concordant"] is True
    assert verdict["geometry_colinear_a"] is True and verdict["geometry_colinear_b"] is True
    # The alignment favours one shared locus in this assembly.
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["alignment_reason"] == "FAVOURS_SHARED_LOCUS_IN_THIS_ASSEMBLY"
    # The origin is not promoted: a shared interval cannot assign the records,
    # and the discriminating position was never read.
    assert verdict["origin_status"] == acc.INDETERMINATE
    assert verdict["origin_reason"] == "SHARED_INTERVAL_CANNOT_ASSIGN_RECORDS"
    assert acc.NO_COVERAGE in verdict["evidence816_a_calls"]
    assert acc.NO_COVERAGE in verdict["evidence816_b_calls"]
    # Per-query eligibility survives in the row.
    assert verdict["eligibility_a_status"] == acc.DETERMINED
    assert verdict["eligibility_b_status"] == acc.DETERMINED


def test_disjoint_intervals_can_be_determined_while_the_origin_is_not():
    a = make_candidate("A:a:1", 1_000, 2_000, blocks=[(1_000, 2_000)])
    b = make_candidate("A:b:1", 80_000, 81_000, blocks=[(80_000, 81_000)])
    uncovered = {
        "a": [{"candidate_id": "A:a:1", "verdict": acc.NO_COVERAGE}],
        "b": [{"candidate_id": "A:b:1", "verdict": acc.NO_COVERAGE}],
    }
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, uncovered, 816)
    # The distinction between the mapped intervals is determined ...
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["alignment_reason"] == "MAPPED_INTERVALS_DISTINCT_NON_OVERLAPPING_SPANS"
    # ... while the origin of the records is a separate, unresolved inference.
    assert verdict["origin_status"] == acc.INDETERMINATE
    assert verdict["origin_reason"].startswith("DISCRIMINATING_POSITION_NOT_CALLED_EXACT")


def test_disjoint_intervals_each_matching_its_own_record_favour_distinct_loci():
    a = make_candidate("A:a:1", 1_000, 2_000, blocks=[(1_000, 2_000)])
    b = make_candidate("A:b:1", 80_000, 81_000, blocks=[(80_000, 81_000)])
    discriminating = {
        "a": [{"candidate_id": "A:a:1", "verdict": acc.EXACT, "subject_base": "C"}],
        "b": [{"candidate_id": "A:b:1", "verdict": acc.EXACT, "subject_base": "T"}],
    }
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)},
                               discriminating, 816)
    # The distinction between the two mapped intervals stays determined ...
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["alignment_reason"] == "MAPPED_INTERVALS_DISTINCT_NON_OVERLAPPING_SPANS"
    # ... and so do the per-candidate calls that carry the evidence.
    assert verdict["evidence816_a_calls"] == f"A:a:1=C/{acc.EXACT}"
    assert verdict["evidence816_b_calls"] == f"A:b:1=T/{acc.EXACT}"
    # ... while the origin of the two records is not promoted. The position
    # favours two distinct loci in this assembly, which a duplicated locus or
    # two alleles of one locus would read the same way.
    assert verdict["origin_status"] == acc.INDETERMINATE
    assert verdict["origin_reason"] == (
        "DISCRIMINATING_POSITION_FAVOURS_DISTINCT_LOCI_IN_THIS_ASSEMBLY")

    # The same geometry with one base on both intervals does not discriminate.
    same_base = {q: [{**c[0], "subject_base": "C"}] for q, c in discriminating.items()}
    verdict = acc.pair_verdict({"a": determined(a), "b": determined(b)}, same_base, 816)
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["origin_status"] == acc.INDETERMINATE
    assert verdict["origin_reason"] == "DISCRIMINATING_POSITION_DOES_NOT_DISCRIMINATE"


def test_same_genomic_blocks_in_inverted_query_order_is_not_a_shared_locus():
    # Identical genomic intervals, identical outer bounds, same sequence and
    # strand -- but the query runs through them in the opposite order, so the
    # two chains describe different transcripts over the same ground.
    blocks = [(1_000, 1_200), (2_000, 2_400)]
    forward = make_candidate("A:a:1", 1_000, 2_400, blocks=blocks, query_order=[0, 1])
    inverted = make_candidate("A:b:1", 1_000, 2_400, blocks=blocks, query_order=[1, 0])

    assert sorted(forward.block_chain) == sorted(inverted.block_chain)
    assert forward.chain != inverted.chain

    verdict = acc.pair_verdict(
        {"a": determined(forward), "b": determined(inverted)}, {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["geometry_same_genomic_blocks"] is True
    assert verdict["geometry_chains_concordant"] is False
    assert verdict["alignment_reason"] in (
        "SAME_SPAN_SAME_BLOCKS_DIFFERENT_QUERY_ORDER", "NON_COLINEAR_CHAIN")


def test_colinearity_is_judged_on_the_strand_the_hsps_declare():
    forward = make_candidate("A:a:1", 1_000, 2_400, strand="plus",
                             blocks=[(1_000, 1_200), (2_000, 2_400)], query_order=[0, 1])
    assert forward.colinear is True
    # Same blocks, same strand, but the query visits them backwards.
    backwards = make_candidate("A:a:2", 1_000, 2_400, strand="plus",
                               blocks=[(1_000, 1_200), (2_000, 2_400)], query_order=[1, 0])
    assert backwards.colinear is False

    # On the minus strand the genome must run backwards as the query advances.
    minus_ok = make_candidate("A:a:3", 1_000, 2_400, strand="minus",
                              blocks=[(2_000, 2_400), (1_000, 1_200)], query_order=[0, 1])
    assert minus_ok.colinear is True
    minus_bad = make_candidate("A:a:4", 1_000, 2_400, strand="minus",
                               blocks=[(1_000, 1_200), (2_000, 2_400)], query_order=[0, 1])
    assert minus_bad.colinear is False


def test_a_non_colinear_chain_cannot_support_a_shared_locus():
    blocks = [(1_000, 1_200), (2_000, 2_400)]
    good = make_candidate("A:a:1", 1_000, 2_400, blocks=blocks, query_order=[0, 1])
    bad = make_candidate("A:b:1", 1_000, 2_400, blocks=blocks, query_order=[1, 0])
    verdict = acc.pair_verdict({"a": determined(good), "b": determined(bad)}, {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["geometry_colinear_a"] is True
    assert verdict["geometry_colinear_b"] is False


def test_geometry_is_reported_apart_from_the_attribution():
    a = make_candidate("A:a:1", 1_000, 2_400, blocks=[(1_000, 2_400)])
    b = make_candidate("A:b:1", 1_000, 2_400, blocks=[(1_000, 2_400)], strand="minus")
    shape = acc.geometry(a, b)
    # Geometry says the bounds coincide; it says nothing about attribution.
    assert shape["same_span"] is True
    assert shape["same_sequence"] is True
    assert shape["same_strand"] is False
    assert "status" not in shape and "alignment_status" not in shape


def test_non_overlapping_spans_are_distinct_loci():
    verdict = acc.pair_verdict(
        {"a": determined(make_candidate("A:a:1", 1_000, 2_000)),
         "b": determined(make_candidate("A:b:1", 80_000, 81_000))}, {}, 816)
    assert verdict["alignment_status"] == acc.DETERMINED
    assert verdict["alignment_reason"] == "MAPPED_INTERVALS_DISTINCT_NON_OVERLAPPING_SPANS"


def test_overlapping_spans_on_one_sequence_stay_indeterminate():
    verdict = acc.pair_verdict(
        {"a": determined(make_candidate("A:a:1", 1_000, 2_000)),
         "b": determined(make_candidate("A:b:1", 1_500, 2_500))}, {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert verdict["alignment_reason"] == "OVERLAPPING_SPANS_ON_ONE_SEQUENCE"


def test_one_query_without_hsps_leaves_the_pair_indeterminate():
    verdict = acc.pair_verdict(
        {"a": determined(make_candidate("A:a:1", 1_000, 2_000)),
         "b": {"status": acc.INDETERMINATE, "status_reason": "NO_HSPS", "locus": None}},
        {}, 816)
    assert verdict["alignment_status"] == acc.INDETERMINATE
    assert "NO_HSPS" in verdict["alignment_reason"]


# --------------------------------------------------------------------------- run-path contracts
def test_command_log_exposes_the_attribute_the_manifest_records():
    # The manifest writes the executed commands; the real run is the only place
    # that would otherwise discover a wrong attribute name.
    from zeaguard.nb01_dsrnase_investigation import CommandLog
    assert isinstance(CommandLog().entries, list)
    assert not hasattr(CommandLog(), "records")


def test_thresholds_come_from_adr_0009_and_are_not_redefined_here():
    from zeaguard import nb01_locus
    assert acc.LOCUS_MIN_QUERY_COVERAGE_PCT is nb01_locus.LOCUS_MIN_QUERY_COVERAGE_PCT
    assert acc.ASSIGNMENT_MIN_IDENTITY_PCT is nb01_locus.ASSIGNMENT_MIN_IDENTITY_PCT
    assert acc.RELATED_LOCUS_MIN_COVERAGE_PCT is nb01_locus.RELATED_LOCUS_MIN_COVERAGE_PCT


# --------------------------------------------------------------------------- panel loader
def write_panel(path, **overrides):
    import json
    panel = {
        "schema_version": acc.PANEL_SCHEMA_VERSION,
        "kind": acc.PANEL_KIND,
        "criteria_reference": {"adr": "ADR 0009"},
        "assemblies_panel": {"path": "assemblies.json"},
        "tsa": {"path": "data/external/tsa.gz", "sha256": "0" * 64},
        "queries": [
            {"query_id": "q@A", "accession": "GITV01008430.1", "record_length": 10,
             "strand": "+", "cds_tx_start": 1, "cds_tx_end": 9, "cds_length": 9,
             "cds_sha256": "a" * 64},
            {"query_id": "q@B", "accession": "GITV01012450.1", "record_length": 10,
             "strand": "+", "cds_tx_start": 1, "cds_tx_end": 9, "cds_length": 9,
             "cds_sha256": "b" * 64},
        ],
        "informative_positions": [{"cds_pos": 3, "class": "DEFINED_SUBSTITUTION"}],
        "discriminating_position": {"cds_pos": 3},
    }
    panel.update(overrides)
    path.write_text(json.dumps(panel), encoding="utf-8")
    return path


def test_accession_panel_loader_accepts_a_well_formed_panel(tmp_path):
    panel = acc.load_accession_panel(write_panel(tmp_path / "p.json"))
    assert panel["kind"] == acc.PANEL_KIND


def test_accession_panel_loader_refuses_the_wrong_kind(tmp_path):
    path = write_panel(tmp_path / "p.json", kind="nb01_dsrnase_locus_panel")
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.load_accession_panel(path)
    assert "requires" in str(error.value) and acc.PANEL_KIND in str(error.value)


def test_accession_panel_loader_refuses_another_schema_version(tmp_path):
    path = write_panel(tmp_path / "p.json", schema_version=2)
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.load_accession_panel(path)
    assert "schema_version" in str(error.value)


def test_accession_panel_loader_refuses_a_missing_field_or_a_stray_discriminator(tmp_path):
    path = write_panel(tmp_path / "p.json")
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["tsa"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.load_accession_panel(path)
    assert "'tsa'" in str(error.value)

    stray = write_panel(tmp_path / "q.json", discriminating_position={"cds_pos": 999})
    with pytest.raises(acc.AccessionMappingError) as error:
        acc.load_accession_panel(stray)
    assert "not among the declared informative positions" in str(error.value)


def test_the_real_locus_panel_is_refused_by_the_accession_loader():
    # The historical panel keeps its own loader; this one must not accept it.
    with pytest.raises(acc.AccessionMappingError):
        acc.load_accession_panel(ROOT / "data/reference/nb01_dsrnase_locus_panel.json")


def test_the_historical_loader_still_reads_the_assemblies_panel():
    from zeaguard.nb01_locus import load_panel
    panel = load_panel(ROOT / "data/reference/nb01_dsrnase_locus_panel.json")
    assert [a["id"] for a in panel["assemblies"]]


# --------------------------------------------------------------------------- panel
def test_panel_declares_the_seven_informative_positions_and_the_discriminator():
    import json
    panel = json.loads((ROOT / "data/reference/nb01_dsrnase2_accession_panel.json")
                       .read_text(encoding="utf-8"))
    positions = [p["cds_pos"] for p in panel["informative_positions"]]
    assert positions == [9, 30, 219, 312, 350, 816, 1272]
    assert panel["discriminating_position"]["cds_pos"] == 816
    defined = [p["cds_pos"] for p in panel["informative_positions"]
               if p["class"] == "DEFINED_SUBSTITUTION"]
    assert defined == [816], "816 is the only position with two defined bases"
    assert [q["accession"] for q in panel["queries"]] == [
        "GITV01008430.1", "GITV01012450.1"]
    assert all(q["cds_length"] == 1425 for q in panel["queries"])


# --------------------------------------------------------------------------- integration
def build_synthetic_root(tmp_path):
    """A whole miniature repository: TSA, assembly, both panels, real hashes.

    Only the two external BLAST executables are stubbed; hash verification,
    assembly statistics, CDS extraction, the BTOP audit and every write run for
    real.
    """
    import gzip
    import hashlib
    import json
    from zeaguard.nb01_locus import scan_assembly

    root = tmp_path / "repo"
    (root / "data/external").mkdir(parents=True)
    (root / "data/reference").mkdir(parents=True)

    # Two TSA records whose CDS differ only at position 3: C against T.
    cds_a = "ATCGGGAAA" + "TTTCCCGGG"
    cds_b = "ATTGGGAAA" + "TTTCCCGGG"
    tsa_text = f">GITV01008430.1 synthetic\n{cds_a}\n>GITV01012450.1 synthetic\n{cds_b}\n"
    tsa_path = root / "data/external/tsa.gz"
    with gzip.open(tsa_path, "wt") as handle:
        handle.write(tsa_text)

    # The genome actually carries what the alignments will claim: a plus-strand
    # copy of CDS A, and a reverse-complement copy of CDS B, so one query aligns
    # forward and the other backward and both BTOPs are honest.
    from zeaguard.nb01_identity import reverse_complement
    pad1, pad2, pad3 = "A" * 10, "A" * 12, "A" * 10
    genome = pad1 + cds_a + pad2 + reverse_complement(cds_b) + pad3
    fasta_text = f">chr1 synthetic chromosome: 1\n{genome}\n"
    plain = tmp_path / "assembly.fna"
    plain.write_text(fasta_text, encoding="ascii", newline="\n")
    assembly_path = root / "data/external/assembly.fna.gz"
    with gzip.open(assembly_path, "wt", newline="\n") as handle:
        handle.write(fasta_text)
    _, stats = scan_assembly(plain)

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    (root / "data/reference/assemblies.json").write_text(json.dumps({
        "schema_version": 1,
        "kind": "nb01_dsrnase_locus_panel",
        "assemblies": [{
            "id": "synthetic_primary",
            "path": "data/external/assembly.fna.gz",
            "sha256": sha(assembly_path),
            "sha256_decompressed": hashlib.sha256(
                plain.read_bytes()).hexdigest(),
            "assembly_stats": {
                "number_of_sequences": stats["number_of_sequences"],
                "total_sequence_length": stats["total_sequence_length"],
                "scaffold_n50": stats["scaffold_n50"],
            },
        }],
    }), encoding="utf-8")

    (root / "data/reference/accession.json").write_text(json.dumps({
        "schema_version": acc.PANEL_SCHEMA_VERSION,
        "kind": acc.PANEL_KIND,
        "criteria_reference": {"adr": "ADR 0009"},
        "assemblies_panel": {"path": "data/reference/assemblies.json"},
        "tsa": {"path": "data/external/tsa.gz", "sha256": sha(tsa_path)},
        "queries": [
            {"query_id": "dsRNase-2@GITV01008430.1", "accession": "GITV01008430.1",
             "role": "OPERATIONAL_REFERENCE", "record_length": len(cds_a), "strand": "+",
             "cds_tx_start": 1, "cds_tx_end": len(cds_a), "cds_length": len(cds_a),
             "cds_sha256": hashlib.sha256(cds_a.encode()).hexdigest()},
            {"query_id": "dsRNase-2@GITV01012450.1", "accession": "GITV01012450.1",
             "role": "SIBLING", "record_length": len(cds_b), "strand": "+",
             "cds_tx_start": 1, "cds_tx_end": len(cds_b), "cds_length": len(cds_b),
             "cds_sha256": hashlib.sha256(cds_b.encode()).hexdigest()},
        ],
        "informative_positions": [{"cds_pos": 3, "class": "DEFINED_SUBSTITUTION"}],
        "discriminating_position": {"cds_pos": 3},
    }), encoding="utf-8")
    return root, genome, len(genome)


# Column order blastn is asked for, so the synthetic raw table is parsed by the
# real parser rather than by a stub of it.
from zeaguard.nb01_dsrnase_investigation import BLAST_OUTFMT_FIELDS  # noqa: E402


def raw_table(genome_length):
    """A synthetic outfmt6 table in BLAST's own column order.

    Query A occupies genome 11-28 on the plus strand; query B occupies 41-58 and
    is read backwards, so blastn reports its subject descending. Both are exact,
    so every BTOP is a single match run.
    """
    rows = [
        {"qseqid": "dsRNase-2@GITV01008430.1", "sstart": 11, "send": 28, "sstrand": "plus"},
        {"qseqid": "dsRNase-2@GITV01012450.1", "sstart": 58, "send": 41, "sstrand": "minus"},
    ]
    lines = []
    for row in rows:
        values = {
            "qseqid": row["qseqid"], "sseqid": "chr1", "pident": "100.000",
            "length": "18", "qlen": "18", "slen": str(genome_length),
            "qstart": "1", "qend": "18", "sstart": str(row["sstart"]),
            "send": str(row["send"]), "sstrand": row["sstrand"], "evalue": "1e-05",
            "bitscore": "36.2", "mismatch": "0", "gapopen": "0", "gaps": "0",
            "qcovs": "100", "btop": "18",
        }
        lines.append("\t".join(values[f] for f in BLAST_OUTFMT_FIELDS))
    return "\n".join(lines) + "\n"


def stub_external_processes(monkeypatch, executed, table_text):
    """Replace only the external executables, writing the raw outputs they would.

    `_blast_with_archive` and `parse_hsp_table` are left alone: the synthetic
    table below is parsed by the real parser, in BLAST's own column order.
    """
    def fake_run(self, command, stdout_path=None):
        executed.append(command[0])
        self.entries.append({"command": command})
        if command[0] == "blastn":
            Path(command[command.index("-out") + 1]).write_text(
                "synthetic archive\n", encoding="utf-8")
        if stdout_path is not None:
            path = Path(stdout_path)
            path.write_text(table_text if path.name.endswith(".outfmt6.tsv")
                            else "synthetic\n", encoding="utf-8", newline="\n")
        return ""

    monkeypatch.setattr(acc.CommandLog, "run", fake_run)


def test_cli_run_stubbing_only_blast_writes_every_table_and_the_manifest(tmp_path, monkeypatch):
    import json
    root, genome, genome_length = build_synthetic_root(tmp_path)
    executed = []
    stub_external_processes(monkeypatch, executed, raw_table(genome_length))

    out = "results/run_v1"
    assert acc.main(["--root", str(root), "--panel", "data/reference/accession.json",
                     "--out", out]) == 0
    # makeblastdb, blastn, and the two blast_formatter renderings: the external
    # processes and nothing else.
    assert executed == ["makeblastdb", "blastn", "blast_formatter", "blast_formatter"]
    # The real parser consumed the real file the stub wrote.
    assert (root / out / "raw/blastn_synthetic_primary.outfmt6.tsv").is_file()

    produced = root / out
    for name in ("queries.tsv", "candidates.tsv", "informative_positions.tsv",
                 "informative_observations.tsv", "assignments.tsv",
                 "accession_pair.tsv", "manifest.json"):
        assert (produced / name).is_file(), name
    # The claim was released after the last write.
    assert not (produced / ".splice_check.lock").exists()

    def rows(name):
        lines = (produced / name).read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        return [dict(zip(header, line.split("\t"))) for line in lines[1:]]

    assert len(rows("queries.tsv")) == 2
    positions = {r["query_id"]: r for r in rows("informative_positions.tsv")}
    assert len(positions) == 2, "one informative position per candidate, two candidates"

    # Every evidence row is checked against the test genome itself: the base the
    # row reports must be the base that is actually at that coordinate.
    forward = positions["dsRNase-2@GITV01008430.1"]
    assert forward["strand"] == "plus"
    assert forward["verdict"] == acc.EXACT
    coordinate = int(forward["subject_pos"])
    assert coordinate == 13, "query position 3 of a block starting at genome 11"
    assert genome[coordinate - 1] == "C"
    assert forward["subject_base_plus_strand"] == genome[coordinate - 1]
    assert forward["query_base"] == "C"

    # The reverse-strand case: the aligned base is in the query's orientation,
    # and the genome carries its complement at that coordinate.
    reverse = positions["dsRNase-2@GITV01012450.1"]
    assert reverse["strand"] == "minus"
    assert reverse["verdict"] == acc.EXACT
    coordinate = int(reverse["subject_pos"])
    assert coordinate == 56, "query position 3 counted backwards from genome 58"
    assert genome[coordinate - 1] == "A"
    assert reverse["query_base"] == "T"
    assert reverse["subject_base_query_orientation"] == "T"
    assert reverse["subject_base_plus_strand"] == "A" == genome[coordinate - 1]

    observations = rows("informative_observations.tsv")
    assert len(observations) == 2
    assert all(o["hsp_id"] for o in observations), "every observation names its HSP"
    for observation in observations:
        at = int(observation["subject_pos"])
        assert observation["subject_base_plus_strand"] == genome[at - 1]

    # The conventional BLAST identity survives as its own column, and the three
    # groups of the pair table are kept apart.
    assert all("identity_pct_blast" in r for r in rows("candidates.tsv"))
    assert all(r["colinear"] == "True" for r in rows("candidates.tsv"))
    pair = rows("accession_pair.tsv")[0]
    assert any(k.startswith("geometry_") for k in pair)
    assert any(k.startswith("evidence816_") for k in pair)
    assert {"alignment_status", "alignment_reason", "origin_status", "origin_reason"} <= set(pair)
    # Two separate, non-overlapping spans on one sequence: the alignment settles
    # the distinction between the mapped intervals.
    assert pair["alignment_status"] == acc.DETERMINED
    assert pair["alignment_reason"] == "MAPPED_INTERVALS_DISTINCT_NON_OVERLAPPING_SPANS"
    # Each interval carries its own record's base at the discriminating
    # position, and the written row still leaves the origin of the records
    # unresolved, naming the evidence it weighed.
    assert pair["origin_status"] == acc.INDETERMINATE
    assert pair["origin_reason"] == (
        "DISCRIMINATING_POSITION_FAVOURS_DISTINCT_LOCI_IN_THIS_ASSEMBLY")

    manifest = json.loads((produced / "manifest.json").read_text(encoding="utf-8"))
    verified = manifest["verified_inputs"]
    assert verified["accession_panel"]["sha256"]
    assert verified["assemblies_panel"]["sha256"]
    assert verified["tsa"]["sha256"]
    assert verified["assemblies"][0]["sha256"]
    assert verified["assemblies"][0]["sha256_decompressed"]
    assert manifest["flank_in_scope"] is False
    assert manifest["discriminating_position"] == 3


def test_cli_run_refuses_a_destination_that_already_holds_results(tmp_path, monkeypatch):
    root, _, _ = build_synthetic_root(tmp_path)
    occupied = root / "results/run_v1"
    occupied.mkdir(parents=True)
    (occupied / "candidates.tsv").write_text("kept\n", encoding="utf-8")

    with pytest.raises(Exception) as error:
        acc.main(["--root", str(root), "--panel", "data/reference/accession.json",
                  "--out", "results/run_v1"])
    assert "not empty" in str(error.value)
    assert (occupied / "candidates.tsv").read_text(encoding="utf-8") == "kept\n"
