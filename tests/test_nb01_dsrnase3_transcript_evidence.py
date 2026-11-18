"""Synthetic validation of the dsRNase-3 642/643 transcript-evidence command.

Every case the pre-run requires explicitly: the exact junction, a one-base
shift on either edge, a deletion inside a flanking block, a short anchor, an
ambiguous mapping, two mates of one pair both crossing, insufficient coverage,
invalid and truncated input, and an attempt to overwrite an earlier execution.

No real library is involved. All coordinates are the declared ones of the
target junction, so the fixtures exercise the same arithmetic the real round
will.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from zeaguard import nb01_dsrnase3_transcript_evidence as ev

SEQUENCE_LENGTH = ev.REFERENCE["sequence_length_nt"]             # 122,877,750

TARGET = ev.TARGET_JUNCTION
# A 50 nt read placed against each edge of the junction: it covers that side's
# whole anchor zone, which is what informative coverage requires.
UP_WINDOW_START = ev.FLANKS["upstream"]["ref_end"] - 49          # 122,007,299
DOWN_WINDOW_START = ev.FLANKS["downstream"]["ref_start"]         # 122,012,479

CROSSING_CIGAR = f"50M{TARGET.intron_len_nt}N50M"
CONTROL_456 = ev.CONTROL_JUNCTIONS[0]
CONTROL_870 = ev.CONTROL_JUNCTIONS[1]


def record_line(qname: str, pos: int, cigar: str, flag: int = 0, mapq: int = 60,
                rname: str = "OZ319704.1", tags: tuple[str, ...] = ()) -> str:
    return "\t".join([qname, str(flag), rname, str(pos), str(mapq), cigar,
                      "=", "0", "0", "*", "*", *tags])


def sam_text(lines: list[str], sequence_length: int = SEQUENCE_LENGTH,
             with_pg: bool = True, with_sq: bool = True) -> str:
    header = ["@HD\tVN:1.6\tSO:coordinate"]
    if with_sq:
        header.append(f"@SQ\tSN:OZ319704.1\tLN:{sequence_length}")
    if with_pg:
        header.append("@PG\tID:hisat2\tPN:hisat2\tVN:2.2.1\t"
                      "CL:hisat2 -p 8 --dta --max-intronlen 50000 -x ihDalMaid1.1")
    return "\n".join(header + lines) + "\n"


def parse_one(cigar: str, pos: int, **kwargs):
    _, records = ev.parse_sam(record_line("r1", pos, cigar, **kwargs))
    return records[0]


def observe(cigar: str, pos: int, criteria: ev.Criteria | None = None, **kwargs) -> dict:
    record = parse_one(cigar, pos, **kwargs)
    specs = (TARGET, *ev.CONTROL_JUNCTIONS)
    return ev.observe_record(record, 0, specs, criteria or ev.Criteria())


def target_junctions(observation: dict) -> list[dict]:
    return [j for j in observation["junctions"] if j["junction_name"] == TARGET.name]


def count(lines: list[str], criteria: ev.Criteria | None = None) -> dict:
    _, records = ev.parse_sam(sam_text(lines))
    return ev.count_library(records, criteria or ev.Criteria())


# --------------------------------------------------------------------------
# The declared question
# --------------------------------------------------------------------------


def test_declared_junction_matches_the_run_record_coordinates():
    # Last aligned base 122,007,348 and first aligned base 122,012,479, so the
    # intron is the 5,130 nt between them, 1-based inclusive.
    assert (TARGET.intron_start, TARGET.intron_end) == (122_007_349, 122_012_478)
    assert TARGET.intron_len_nt == 5_130
    assert (TARGET.cds_upstream, TARGET.cds_downstream) == (642, 643)
    assert TARGET.annotated_intron is False
    assert ev.FLANKS["upstream"]["ref_end"] == TARGET.intron_start - 1
    assert ev.FLANKS["downstream"]["ref_start"] == TARGET.intron_end + 1
    assert all(spec.annotated_intron for spec in ev.CONTROL_JUNCTIONS)


def test_reference_aligned_intervals_skip_deletions_and_junctions():
    intervals = ev.ref_aligned_intervals(ev.parse_cigar("10M2D5M100N20M"), 1_000)
    assert intervals == [(1_000, 1_009), (1_012, 1_016), (1_117, 1_136)]


# --------------------------------------------------------------------------
# Junction recognition
# --------------------------------------------------------------------------


def test_exact_junction_with_long_anchors_is_support():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "support"
    assert junction["counted_as_support"] is True
    assert (junction["intron_ref_start"], junction["intron_ref_end"]) == \
        (TARGET.intron_start, TARGET.intron_end)
    # Both anchor zones fully covered, which is what support requires.
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT
    assert junction["anchor_downstream_covered_nt"] == ANCHOR_NT
    assert junction["anchor_required_nt"] == ANCHOR_NT
    assert junction["anchor_zone_upstream"] == "122007329-122007348"
    assert junction["anchor_zone_downstream"] == "122012479-122012498"


def test_one_base_shift_on_both_edges_is_a_neighbour_not_support():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START + 1)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "neighbour"
    assert junction["category"] == "neighbour"
    assert junction["counted_as_support"] is False
    assert (junction["delta_intron_start_nt"], junction["delta_intron_end_nt"]) == (1, 1)


def test_one_base_shift_on_the_acceptor_only_keeps_the_donor_but_is_not_support():
    observation = observe(f"50M{TARGET.intron_len_nt + 1}N50M", UP_WINDOW_START)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "donor_only"
    assert junction["counted_as_support"] is False
    assert junction["delta_intron_start_nt"] == 0
    assert junction["delta_intron_end_nt"] == 1


ANCHOR_NT = ev.Criteria().min_anchor_nt


def test_a_deletion_outside_the_anchor_zone_still_supports():
    # 30M2D20M: the deletion sits 20 nt before the donor, so all 20 zone bases
    # are covered and the junction is supported.
    observation = observe(f"30M2D{ANCHOR_NT}M{TARGET.intron_len_nt}N50M",
                          TARGET.intron_start - ANCHOR_NT - 32)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT
    assert junction["category"] == "support"


# --------------------------------------------------------------------------
# The review's finding: a deletion at the edge must not be compensated for by
# bases further out. Coverage is counted on the reference axis, per read.
# --------------------------------------------------------------------------


def test_a_deletion_at_the_donor_edge_is_not_support():
    """Regression: 30M2D5130N70M was counted as support.

    The two reference bases immediately before the intron are deleted, so no
    anchored crossing read could have been read there, yet the block as a whole
    aligned 30 bases. Summing the block let those 30 compensate for the gap.
    """
    observation = observe(f"30M2D{TARGET.intron_len_nt}N70M", TARGET.intron_start - 32)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT - 2      # 18 of 20
    assert junction["anchor_downstream_covered_nt"] == ANCHOR_NT
    assert junction["category"] == "short_anchor"
    assert junction["counted_as_support"] is False


def test_a_deletion_at_the_acceptor_edge_is_not_support():
    observation = observe(f"50M{TARGET.intron_len_nt}N2D50M", TARGET.intron_start - 50)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT
    assert junction["anchor_downstream_covered_nt"] == ANCHOR_NT - 2
    assert junction["category"] == "short_anchor"


def test_a_deletion_immediately_after_n_does_not_refuse_the_library():
    """A D straight after an N is valid SAM; the sibling walker raises on it."""
    counts = count([
        record_line("after_n", TARGET.intron_start - 50,
                    f"50M{TARGET.intron_len_nt}N2D50M"),
        record_line("plain", UP_WINDOW_START, "50M"),
    ])
    assert counts["n_records_on_target_sequence"] == 2
    row = [j for observation in counts["observations"]
           for j in observation["junctions"] if observation["qname"] == "after_n"][0]
    assert row["category"] == "short_anchor"
    # And the reference walk itself places the first aligned base after the gap.
    walk = ev.walk_reference(ev.parse_cigar(f"50M{TARGET.intron_len_nt}N2D50M"),
                             TARGET.intron_start - 50)
    assert walk["junctions"][0]["intron_ref_start"] == TARGET.intron_start
    assert walk["junctions"][0]["intron_ref_end"] == TARGET.intron_end
    assert walk["aligned"][1][0] == TARGET.intron_end + 3


def test_a_deletion_inside_the_anchor_zone_is_not_support():
    # The gap is 10 nt in from the donor: still inside the 20 nt footprint.
    observation = observe(f"30M2D10M{TARGET.intron_len_nt}N50M",
                          TARGET.intron_start - 42)
    junction = target_junctions(observation)[0]
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT - 2
    assert junction["category"] == "short_anchor"


def test_two_incomplete_anchor_fragments_do_not_make_the_junction_supported():
    """The review's case: two such fragments reached JUNCTION_SUPPORTED."""
    result = verdict_for(informative_background() + [
        record_line("edge_del1", TARGET.intron_start - 32,
                    f"30M2D{TARGET.intron_len_nt}N70M", flag=0x1 | 0x40),
        record_line("edge_del2", TARGET.intron_start - 32,
                    f"30M2D{TARGET.intron_len_nt}N70M", flag=0x1 | 0x40),
    ])
    counts = result["counts"]
    assert counts["support_reads"] == 0
    assert counts["support_fragments"] == 0
    assert counts["short_anchor_fragments"] == 2
    assert result["verdict"] != "JUNCTION_SUPPORTED"
    assert result["verdict"] == "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"


def test_the_same_rule_decides_the_annotated_controls():
    counts = count([
        record_line("ctl_ok", CONTROL_456.intron_start - 50,
                    f"50M{CONTROL_456.intron_len_nt}N50M"),
        record_line("ctl_edge_del", CONTROL_870.intron_start - 32,
                    f"30M2D{CONTROL_870.intron_len_nt}N70M"),
    ])
    assert counts["controls"][CONTROL_456.name]["support_fragments"] == 1
    assert counts["controls"][CONTROL_870.name]["support_fragments"] == 0


def test_an_insertion_outside_the_zone_leaves_support_intact():
    observation = observe(f"24M4I24M{TARGET.intron_len_nt}N50M", TARGET.intron_start - 48)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    # The insertion sits 24 nt before the donor; the zone itself is covered.
    assert junction["anchor_upstream_covered_nt"] == ANCHOR_NT
    assert junction["category"] == "support"


def test_an_insertion_cannot_lift_a_short_anchor_over_the_minimum():
    observation = observe(f"8M8I8M{TARGET.intron_len_nt}N50M", TARGET.intron_start - 16)
    junction = target_junctions(observation)[0]
    # 16 reference bases covered and 8 inserted: 24 query bases consumed, but an
    # insertion covers no reference base, so the 20 nt zone stays 4 nt short.
    assert junction["anchor_upstream_covered_nt"] == 16
    assert junction["category"] == "short_anchor"


def test_a_short_anchor_is_recorded_separately_and_is_not_support():
    observation = observe(f"8M{TARGET.intron_len_nt}N50M", TARGET.intron_start - 8)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "short_anchor"
    assert junction["anchor_upstream_covered_nt"] == 8
    assert junction["counted_as_support"] is False


def test_a_reverse_strand_crossing_read_is_support_on_the_same_coordinates():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START, flag=16)
    assert observation["strand"] == "-"
    assert target_junctions(observation)[0]["category"] == "support"


def test_a_junction_far_from_every_declared_one_is_not_recorded():
    observation = observe("50M4000N50M", 1_000_000)
    assert observation["junctions"] == []
    assert observation["n_cigar_junctions"] == 1


def test_the_two_annotated_control_junctions_are_recognised():
    control_a = observe(f"50M{CONTROL_456.intron_len_nt}N50M",
                        CONTROL_456.intron_start - 50)
    control_b = observe(f"50M{CONTROL_870.intron_len_nt}N50M",
                        CONTROL_870.intron_start - 50)
    assert [j["junction_name"] for j in control_a["junctions"]] == [CONTROL_456.name]
    assert control_a["junctions"][0]["category"] == "support"
    assert [j["junction_name"] for j in control_b["junctions"]] == [CONTROL_870.name]
    assert control_b["junctions"][0]["category"] == "support"


# --------------------------------------------------------------------------
# Disqualification: ambiguity, duplicates, secondary and supplementary records
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs, reason", [
    ({"mapq": 1}, "ambiguous_mapq_1"),
    ({"tags": ("NH:i:3",)}, "ambiguous_nh_3"),
    ({"flag": 0x100}, "secondary_alignment"),
    ({"flag": 0x800}, "supplementary_alignment"),
    ({"flag": 0x400}, "flagged_duplicate"),
])
def test_a_disqualified_crossing_read_is_never_support(kwargs, reason):
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START, **kwargs)
    assert observation["disqualified_by"] == reason
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "disqualified"
    assert junction["counted_as_support"] is False


def test_a_non_integer_nh_tag_is_refused():
    with pytest.raises(ev.VerificationError, match="NH tag is not an integer"):
        observe(CROSSING_CIGAR, UP_WINDOW_START, tags=("NH:i:many",))


def test_each_disqualification_lands_in_its_own_library_column():
    counts = count([
        record_line("amb", UP_WINDOW_START, CROSSING_CIGAR, mapq=1),
        record_line("dup", UP_WINDOW_START, CROSSING_CIGAR, flag=0x400),
        record_line("sec", UP_WINDOW_START, CROSSING_CIGAR, flag=0x100),
        record_line("sup", UP_WINDOW_START, CROSSING_CIGAR, flag=0x800),
    ])
    assert counts["support_fragments"] == 0
    assert (counts["ambiguous_reads"], counts["ambiguous_fragments"]) == (1, 1)
    assert (counts["duplicate_reads"], counts["duplicate_fragments"]) == (1, 1)
    assert counts["secondary_reads"] == 1
    assert counts["supplementary_reads"] == 1
    assert counts["disqualified_at_junction_fragments"] == 4


# --------------------------------------------------------------------------
# Per-fragment counting
# --------------------------------------------------------------------------


def test_both_mates_of_one_pair_crossing_count_as_one_fragment():
    counts = count([
        record_line("pair1", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x40),
        record_line("pair1", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x80),
    ])
    assert counts["support_reads"] == 2
    assert counts["support_fragments"] == 1


def test_mates_bridging_the_two_flanks_are_counted_apart_from_support():
    counts = count([
        record_line("bridge", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("bridge", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
    ])
    assert counts["support_fragments"] == 0
    assert counts["mate_bridge_fragments"] == 1
    assert counts["mate_bridge_fragment_names"] == ["bridge"]


def test_two_records_sharing_a_qname_without_pairing_flags_are_not_a_bridge():
    """Regression: a shared QNAME alone was counted as a bridge."""
    counts = count([
        record_line("unpaired", UP_WINDOW_START, "50M"),
        record_line("unpaired", DOWN_WINDOW_START, "50M"),
    ])
    assert counts["mate_bridge_fragments"] == 0
    # The records are still read and still cover their flanks.
    assert counts["n_records_on_target_sequence"] == 2
    assert counts["flanks"]["upstream"]["anchor_zone_fragments"] == 1


def test_two_records_flagged_as_the_same_mate_are_not_a_bridge():
    counts = count([
        record_line("same_mate", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("same_mate", DOWN_WINDOW_START, "50M", flag=0x1 | 0x40),
    ])
    assert counts["mate_bridge_fragments"] == 0


def test_a_record_flagged_as_both_mates_is_not_a_bridge():
    counts = count([
        record_line("both_bits", UP_WINDOW_START, "50M", flag=0x1 | 0x40 | 0x80),
        record_line("both_bits", DOWN_WINDOW_START, "50M", flag=0x1 | 0x40 | 0x80),
    ])
    assert counts["mate_bridge_fragments"] == 0


def test_two_mates_in_the_same_flank_are_not_a_bridge():
    counts = count([
        record_line("one_side", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("one_side", UP_WINDOW_START - 60, "50M", flag=0x1 | 0x80),
    ])
    assert counts["mate_bridge_fragments"] == 0


def test_a_disqualified_mate_cannot_complete_a_bridge():
    counts = count([
        record_line("half_dup", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("half_dup", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80 | 0x400),
    ])
    assert counts["mate_bridge_fragments"] == 0


@pytest.mark.parametrize("flag_first, flag_second, expected", [
    (0x1 | 0x40, 0x1 | 0x80, 1),          # a proper pair
    (0x1 | 0x80, 0x1 | 0x40, 1),          # mates given in the other order
    (0x1, 0x1, 0),                        # paired but neither bit set
    (0, 0, 0),                            # not paired at all
    (0x1 | 0x40, 0x1 | 0x40, 0),          # both flagged first
    (0x1 | 0x80, 0x1 | 0x80, 0),          # both flagged second
])
def test_bridge_requires_one_first_and_one_second_mate(flag_first, flag_second, expected):
    counts = count([
        record_line("frag", UP_WINDOW_START, "50M", flag=flag_first),
        record_line("frag", DOWN_WINDOW_START, "50M", flag=flag_second),
    ])
    assert counts["mate_bridge_fragments"] == expected


def test_a_pair_with_a_crossing_read_is_not_also_counted_as_bridged():
    counts = count([
        record_line("both", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x40),
        record_line("both", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
    ])
    assert counts["support_fragments"] == 1
    assert counts["mate_bridge_fragments"] == 0


def test_records_on_another_sequence_are_counted_and_not_analysed():
    counts = count([
        record_line("elsewhere", 1_000, "50M", rname="OZ319705.1"),
        record_line("here", UP_WINDOW_START, "50M"),
    ])
    assert counts["n_records_off_target"] == 1
    assert counts["n_records_on_target_sequence"] == 1


def test_flank_coverage_counts_only_qualifying_records():
    counts = count([
        record_line("good", UP_WINDOW_START, "50M"),
        record_line("dup", UP_WINDOW_START, "50M", flag=0x400),
    ])
    upstream = counts["flanks"]["upstream"]
    assert upstream["anchor_zone_fragments"] == 1
    assert upstream["covered_nt"] == 50
    assert upstream["length_nt"] == 186


# --------------------------------------------------------------------------
# Informative coverage: the anchor zone, not a window overlap
# --------------------------------------------------------------------------


def test_the_anchor_zone_is_the_footprint_against_each_boundary():
    criteria = ev.Criteria()
    assert criteria.min_anchor_nt == 20          # the measured hisat2 --dta recovery floor
    assert ev.anchor_zone("upstream", criteria) == (122_007_329, 122_007_348)
    assert ev.anchor_zone("downstream", criteria) == (122_012_479, 122_012_498)
    # Immediately against the intron on both sides, min_anchor_nt long.
    for side in ("upstream", "downstream"):
        start, end = ev.anchor_zone(side, criteria)
        assert end - start + 1 == criteria.min_anchor_nt
    assert ev.anchor_zone("upstream", criteria)[1] == TARGET.intron_start - 1
    assert ev.anchor_zone("downstream", criteria)[0] == TARGET.intron_end + 1


def test_a_fragment_covering_the_zone_only_in_part_does_not_count():
    # 5 of the 20 anchor-zone bases: no anchored crossing read could sit here.
    counts = count([record_line("half", TARGET.intron_start - 5, "5M")])
    upstream = counts["flanks"]["upstream"]
    assert upstream["anchor_zone_covered_nt"] == 5
    assert upstream["anchor_zone_fragments"] == 0


def test_a_deletion_inside_the_anchor_zone_leaves_it_uncovered():
    # 2M2D16M ends on the boundary and spans the zone, but two of its bases are
    # deleted rather than aligned, so the footprint is not covered.
    counts = count([record_line("deleted", TARGET.intron_start - 20, "2M2D16M")])
    assert counts["flanks"]["upstream"]["anchor_zone_covered_nt"] == 18
    assert counts["flanks"]["upstream"]["anchor_zone_fragments"] == 0


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


def informative_background() -> list[str]:
    """Five bridged pairs over both windows plus one supported control junction."""
    lines = []
    for index in range(5):
        lines.append(record_line(f"bridge{index}", UP_WINDOW_START, "50M", flag=0x1 | 0x40))
        lines.append(record_line(f"bridge{index}", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80))
    lines.append(record_line("control", CONTROL_456.intron_start - 50,
                             f"50M{CONTROL_456.intron_len_nt}N50M"))
    return lines


def verdict_for(lines: list[str], criteria: ev.Criteria | None = None) -> dict:
    criteria = criteria or ev.Criteria()
    counts = count(lines, criteria)
    return {**ev.classify_library(counts, criteria), "counts": counts}


def test_two_crossing_fragments_support_the_junction():
    lines = informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR),
        record_line("cross2", UP_WINDOW_START, CROSSING_CIGAR),
    ]
    result = verdict_for(lines)
    assert result["verdict"] == "JUNCTION_SUPPORTED"
    assert result["informative_coverage"] is True
    assert result["counts"]["support_fragments"] == 2


def test_a_single_crossing_fragment_is_reported_below_the_declared_threshold():
    result = verdict_for(informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR)])
    assert result["verdict"] == "SUPPORT_BELOW_DECLARED_THRESHOLD"
    assert result["counts"]["support_fragments"] == 1


def test_zero_support_with_both_anchor_zones_covered_is_a_result_not_a_gap():
    """The control for the regression below: the criterion met, verdict preserved."""
    result = verdict_for(informative_background())
    assert result["verdict"] == "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    assert result["informative_coverage"] is True
    assert result["failed_requirements"] == ""
    assert result["counts"]["mate_bridge_fragments"] == 5
    for side in ("upstream", "downstream"):
        flank = result["counts"]["flanks"][side]
        assert flank["anchor_zone_covered_nt"] == 20
        assert flank["anchor_zone_fragments"] == 5


def test_insufficient_flank_coverage_is_inconclusive_and_names_the_side():
    result = verdict_for([
        record_line("bridge0", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("bridge0", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
        record_line("control", CONTROL_456.intron_start - 50,
                    f"50M{CONTROL_456.intron_len_nt}N50M"),
    ])
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert result["informative_coverage"] is False
    assert "upstream_anchor_zone_fragments=1<5" in result["failed_requirements"]
    assert "downstream_anchor_zone_fragments=1<5" in result["failed_requirements"]


UNCOVERED_NT = 40


def background_with_uncovered_anchor_zones() -> list[str]:
    """Five pairs and a spliced control, with 40 nt blank against each boundary.

    Each mate is a full `min_anchor_nt` long and sits in its flank, but 40 nt
    short of the edge, so five qualifying fragments cover each flank near the
    junction while the 40 nt immediately against each edge carry nothing. Under
    a rule that only counted fragments overlapping a wider window this library
    passed as informative.
    """
    anchor_nt = ev.Criteria().min_anchor_nt
    upstream_start = TARGET.intron_start - 1 - UNCOVERED_NT - anchor_nt + 1
    downstream_start = TARGET.intron_end + 1 + UNCOVERED_NT
    lines = []
    for index in range(5):
        lines.append(record_line(f"far{index}", upstream_start, f"{anchor_nt}M",
                                 flag=0x1 | 0x40))
        lines.append(record_line(f"far{index}", downstream_start, f"{anchor_nt}M",
                                 flag=0x1 | 0x80))
    lines.append(record_line("control", CONTROL_456.intron_start - 50,
                             f"50M{CONTROL_456.intron_len_nt}N50M"))
    return lines


def test_the_regression_fixture_really_leaves_forty_nt_blank():
    counts = count(background_with_uncovered_anchor_zones())
    anchor_nt = ev.Criteria().min_anchor_nt
    # Upstream: coverage stops 40 nt before the donor; downstream: starts 40 nt
    # after the acceptor. Both gaps are contiguous and adjacent to the edge.
    assert counts["flanks"]["upstream"]["covered_nt"] == anchor_nt + 50   # + the control block
    assert counts["flanks"]["downstream"]["covered_nt"] == anchor_nt
    for side in ("upstream", "downstream"):
        zone_start, zone_end = ev.anchor_zone(side, ev.Criteria())
        assert zone_end - zone_start + 1 == anchor_nt
        assert counts["flanks"][side]["anchor_zone_covered_nt"] == 0


def test_forty_uncovered_nt_against_each_boundary_is_inconclusive_not_zero_support():
    """Regression: five fragments per side are not informative with a blank anchor zone.

    This is the case the review raised. Before the correction the verdict was
    NO_SUPPORT_WITH_INFORMATIVE_COVERAGE, which asserted an interpretable
    absence over bases where no anchored crossing read could have aligned.
    """
    result = verdict_for(background_with_uncovered_anchor_zones())
    counts = result["counts"]
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert result["informative_coverage"] is False
    for side in ("upstream", "downstream"):
        flank = counts["flanks"][side]
        assert flank["anchor_zone_covered_nt"] == 0
        assert flank["anchor_zone_fragments"] == 0
        assert f"{side}_anchor_zone_fragments=0<5" in result["failed_requirements"]
    # The raw counts are preserved: nothing about the evidence is hidden by the
    # verdict, only its interpretation changes.
    assert counts["support_fragments"] == 0
    assert counts["mate_bridge_fragments"] == 5
    assert counts["n_fragments_on_target_sequence"] == 6
    # The far reads plus the control's 50 nt block at the far end of the upstream
    # flank: coverage exists, just not where it would be informative.
    assert counts["flanks"]["upstream"]["covered_nt"] == 70
    assert counts["flanks"]["downstream"]["covered_nt"] == 20
    assert counts["controls"][CONTROL_456.name]["support_fragments"] == 1


def test_coverage_reaching_the_boundary_restores_the_zero_support_verdict():
    """The same five fragments, moved against the boundary, are informative again."""
    assert verdict_for(informative_background())["verdict"] == \
        "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    # Only the upstream mates moved onto their anchor zone: one covered side is
    # not enough, both are required.
    anchor_nt = ev.Criteria().min_anchor_nt
    one_side = []
    for index in range(5):
        one_side.append(record_line(f"far{index}", TARGET.intron_start - anchor_nt,
                                    f"{anchor_nt}M", flag=0x1 | 0x40))
        one_side.append(record_line(f"far{index}", DOWN_WINDOW_START + 40, "10M",
                                    flag=0x1 | 0x80))
    one_side.append(record_line("control", CONTROL_456.intron_start - 50,
                                f"50M{CONTROL_456.intron_len_nt}N50M"))
    result = verdict_for(one_side)
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert result["counts"]["flanks"]["upstream"]["anchor_zone_fragments"] == 5
    assert result["counts"]["flanks"]["downstream"]["anchor_zone_fragments"] == 0
    assert "downstream_anchor_zone_fragments=0<5" in result["failed_requirements"]
    assert "upstream_anchor_zone" not in result["failed_requirements"]


def test_zero_support_without_any_control_junction_is_not_informative():
    lines = [line for line in informative_background() if "control" not in line]
    result = verdict_for(lines)
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert "no_control_junction_support" in result["failed_requirements"]


def test_a_short_anchored_crossing_alone_does_not_support_the_junction():
    result = verdict_for(informative_background() + [
        record_line("short", TARGET.intron_start - 8, f"8M{TARGET.intron_len_nt}N50M")])
    assert result["verdict"] == "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    assert result["counts"]["short_anchor_fragments"] == 1


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------


def test_a_truncated_alignment_line_is_refused():
    with pytest.raises(ev.VerificationError, match="expected >= 11"):
        ev.parse_sam(sam_text(["r1\t0\tOZ319704.1\t100\t60"]))


def test_a_malformed_cigar_is_refused():
    with pytest.raises(ev.VerificationError, match="unparsable CIGAR"):
        observe("50M5130Njunk50M", UP_WINDOW_START)


def write_sam(path, lines, **kwargs):
    path.write_text(sam_text(lines, **kwargs), encoding="utf-8", newline="\n")
    return path


def test_a_sam_without_an_sq_line_for_the_reference_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], with_sq=False)
    with pytest.raises(ev.VerificationError, match="no @SQ line"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sam_without_a_pg_line_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], with_pg=False)
    with pytest.raises(ev.VerificationError, match="no @PG line"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sam_header_with_no_header_at_all_is_refused(tmp_path):
    path = tmp_path / "lib.sam"
    path.write_text(record_line("r1", UP_WINDOW_START, "50M") + "\n", encoding="utf-8")
    with pytest.raises(ev.VerificationError, match="no header"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sequence_length_disagreeing_with_the_panel_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], sequence_length=99)
    with pytest.raises(ev.VerificationError, match="was not made against the declared reference"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_the_aligner_is_read_from_the_pg_line(tmp_path):
    header, _ = ev.read_library_sam(write_sam(tmp_path / "lib.sam", []),
                                    {"sequence_length_nt": SEQUENCE_LENGTH})
    assert header["aligner_name"] == "hisat2"
    assert header["aligner_version"] == "2.2.1"


# --------------------------------------------------------------------------
# Panel validation and provenance
# --------------------------------------------------------------------------


def make_panel(root, libraries, reference=None):
    panel = {
        "reference": reference if reference is not None else {
            "assembly_accession": "GCA_975739785.1",
            "assembly_name": "ihDalMaid1.1",
            "sequence_name": "OZ319704.1",
            "sequence_length_nt": SEQUENCE_LENGTH,
        },
        "libraries": libraries,
    }
    path = root / "panel.json"
    path.write_text(json.dumps(panel, indent=2), encoding="utf-8", newline="\n")
    return path


def library_entry(root, library_id, lines, **overrides):
    sam_path = write_sam(root / f"{library_id}.sam", lines)
    entry = {
        "library_id": library_id,
        "sam": sam_path.name,
        "sha256": ev.sha256_file(sam_path),
        "origin_class": "open_link",
        "provenance": "synthetic fixture; no BioProject",
    }
    entry.update(overrides)
    return entry


def test_a_panel_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "panel.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ev.VerificationError, match="not valid JSON"):
        ev.load_panel(path, tmp_path)


def test_a_declared_sha256_that_does_not_match_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    entry["sha256"] = "0" * 64
    with pytest.raises(ev.VerificationError, match="sha256 mismatch"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_missing_sam_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    entry["sam"] = "absent.sam"
    with pytest.raises(ev.VerificationError, match="declared SAM is missing"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_confirmed_origin_without_documentary_evidence_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="confirmed_origin")
    with pytest.raises(ev.VerificationError, match="requires 'documentary_evidence'"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_confirmed_origin_with_documentary_evidence_is_accepted(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="confirmed_origin",
                          documentary_evidence="hypothetical document naming the libraries")
    panel = ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)
    assert panel["libraries"][0]["origin_class"] == "confirmed_origin"


def test_an_unknown_origin_class_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="probably_the_right_one")
    with pytest.raises(ev.VerificationError, match="is not one of"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_duplicate_library_id_is_refused(tmp_path):
    first = library_entry(tmp_path, "lib1", [])
    second = dict(first)
    with pytest.raises(ev.VerificationError, match="duplicate library_id"):
        ev.load_panel(make_panel(tmp_path, [first, second]), tmp_path)


def test_a_panel_on_another_reference_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    reference = {"assembly_accession": "GCA_975739835.1", "sequence_name": "OZ319704.1",
                 "sequence_length_nt": SEQUENCE_LENGTH}
    with pytest.raises(ev.VerificationError, match="only defined on"):
        ev.load_panel(make_panel(tmp_path, [entry], reference), tmp_path)


def test_an_empty_library_list_is_refused(tmp_path):
    with pytest.raises(ev.VerificationError, match="non-empty 'libraries'"):
        ev.load_panel(make_panel(tmp_path, []), tmp_path)


# --------------------------------------------------------------------------
# End to end, including the refusal to overwrite an execution
# --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repository, so the manifest can record a real commit."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "base"], cwd=tmp_path, check=True)
    return tmp_path


OUT_SUBDIR = f"{ev.OUTPUT_ROOT}/dsrnase3_transcript_evidence_run1"


def test_a_full_run_writes_the_tables_and_a_success_manifest(repo):
    lines = informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR),
        record_line("cross2", UP_WINDOW_START, CROSSING_CIGAR),
    ]
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", lines)])
    assert ev.main(["--root", str(repo), "--panel", str(panel),
                    "--out-subdir", OUT_SUBDIR]) == 0

    out_dir = repo / OUT_SUBDIR
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["verdicts"] == {"SYNTH01": "JUNCTION_SUPPORTED"}
    assert len(manifest["git"]["commit"]) == 40
    assert manifest["git"]["clean"] is False  # the panel and the SAM are untracked
    assert manifest["indexing_convention"].startswith("1-based inclusive")
    assert manifest["target_junction"]["intron_start"] == TARGET.intron_start
    assert manifest["criteria"]["min_anchor_nt"] == 20
    assert manifest["anchor_zones"]["upstream"] == {
        "ref_start": 122_007_329, "ref_end": 122_007_348}
    assert manifest["anchor_zones"]["downstream"] == {
        "ref_start": 122_012_479, "ref_end": 122_012_498}
    assert manifest["reference"]["sequence_length_nt"] == 122_877_750
    assert manifest["panel"]["sha256"] == ev.sha256_file(panel)
    assert set(manifest["outputs"]) == {
        "per_library.tsv", "junction_observations.tsv", "mate_bridged_fragments.tsv"}
    for name, digest in manifest["outputs"].items():
        assert ev.sha256_file(out_dir / name) == digest
    assert manifest["validation"]["mate_bridged_fragments.tsv"]["rows"] == 5
    assert manifest["library_provenance_note"]["rule"].startswith("no library is classified")

    header, *rows = (out_dir / "per_library.tsv").read_text(encoding="utf-8").splitlines()
    row = dict(zip(header.split("\t"), rows[0].split("\t")))
    assert row["support_fragments"] == "2"
    assert row["mate_bridge_fragments"] == "5"
    assert row["control_cds_456_457_support_fragments"] == "1"
    assert row["aligner_name"] == "hisat2"
    assert row["origin_class"] == "open_link"
    assert row["verdict"] == "JUNCTION_SUPPORTED"

    observations = (out_dir / "junction_observations.tsv").read_text(encoding="utf-8").splitlines()
    assert sum(1 for line in observations[1:] if "\tsupport\t" in line) == 3  # 2 target + control


def test_a_second_run_on_the_same_directory_is_refused_with_the_first_intact(repo):
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", informative_background())])
    arguments = ["--root", str(repo), "--panel", str(panel), "--out-subdir", OUT_SUBDIR]
    assert ev.main(arguments) == 0
    before = ev.sha256_file(repo / OUT_SUBDIR / "manifest.json")
    with pytest.raises(ev.VerificationError, match="output directory is not empty"):
        ev.main(arguments)
    assert ev.sha256_file(repo / OUT_SUBDIR / "manifest.json") == before


def test_an_output_directory_outside_the_results_tree_is_refused(repo):
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", [])])
    with pytest.raises(ev.VerificationError, match="must sit under"):
        ev.main(["--root", str(repo), "--panel", str(panel), "--out-subdir", "somewhere/else"])
    with pytest.raises(ev.VerificationError, match="must name a directory of its own"):
        ev.main(["--root", str(repo), "--panel", str(panel), "--out-subdir", ev.OUTPUT_ROOT])


def test_a_run_outside_a_git_checkout_is_refused_before_anything_is_written(tmp_path):
    panel = make_panel(tmp_path, [library_entry(tmp_path, "SYNTH01", [])])
    with pytest.raises(ev.VerificationError, match="cannot record the commit"):
        ev.run(tmp_path, panel, tmp_path / "out", ev.Criteria())


# --------------------------------------------------------------------------
# The pilot executor: reuse of a working directory and of an index, and
# failures inside the recipe's pipeline.
# --------------------------------------------------------------------------

_PILOT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_nb01_dsrnase3_pilot.py"
_pilot_spec = importlib.util.spec_from_file_location("run_nb01_dsrnase3_pilot", _PILOT_PATH)
pilot = importlib.util.module_from_spec(_pilot_spec)
sys.modules[_pilot_spec.name] = pilot
_pilot_spec.loader.exec_module(pilot)


def test_staging_links_the_declared_input(tmp_path):
    source = tmp_path / "SRR_1.fastq.gz"
    source.write_bytes(b"x")
    target = tmp_path / "work" / "SRR_1.fastq.gz"
    target.parent.mkdir()
    pilot.stage_input(source, target)
    assert target.is_symlink() and target.resolve() == source.resolve()
    # Staging again over its own link is accepted and changes nothing.
    pilot.stage_input(source, target)
    assert target.resolve() == source.resolve()


def test_a_leftover_real_file_in_the_working_directory_is_refused(tmp_path):
    """Regression: the aligner would read this file while the manifest hashed another."""
    source = tmp_path / "SRR_1.fastq.gz"
    source.write_bytes(b"declared")
    target = tmp_path / "work" / "SRR_1.fastq.gz"
    target.parent.mkdir()
    target.write_bytes(b"stale and different")
    with pytest.raises(SystemExit, match="not a link to the declared input"):
        pilot.stage_input(source, target)
    assert target.read_bytes() == b"stale and different"      # nothing was overwritten


def test_a_link_to_another_input_is_refused(tmp_path):
    source = tmp_path / "SRR_1.fastq.gz"
    other = tmp_path / "other.fastq.gz"
    for path in (source, other):
        path.write_bytes(b"x")
    target = tmp_path / "work" / "SRR_1.fastq.gz"
    target.parent.mkdir()
    target.symlink_to(other)
    with pytest.raises(SystemExit, match="points at"):
        pilot.stage_input(source, target)


def test_a_missing_declared_read_file_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="declared read file is missing"):
        pilot.stage_input(tmp_path / "absent.fastq.gz", tmp_path / "work.fastq.gz")


def index_record(index_dir, **overrides):
    files = {}
    for number in range(1, 9):
        path = index_dir / f"{pilot.INDEX_NAME}.{number}.ht2"
        path.write_bytes(bytes([number]) * number)
        files[path.name] = {"bytes": path.stat().st_size, "sha256": ev.sha256_file(path)}
    record = {
        "assembly": {"accession": ev.REFERENCE["assembly_accession"],
                     "sha256_gz": pilot.GENOME_SHA256,
                     "sha256_decompressed": pilot.GENOME_SHA256_DECOMPRESSED},
        "index_name": pilot.INDEX_NAME,
        "files": files,
    }
    record.update(overrides)
    (index_dir / pilot.INDEX_RECORD).write_text(json.dumps(record), encoding="utf-8")
    return record


def test_a_recorded_index_verifies_when_every_file_matches(tmp_path):
    index_record(tmp_path)
    assert len(pilot.verify_index(tmp_path)["files"]) == 8


def test_an_index_without_a_build_record_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="build the index"):
        pilot.verify_index(tmp_path)


def test_an_index_for_another_assembly_is_refused(tmp_path):
    index_record(tmp_path, assembly={"accession": "GCA_975739835.1",
                                     "sha256_gz": pilot.GENOME_SHA256,
                                     "sha256_decompressed": pilot.GENOME_SHA256_DECOMPRESSED})
    with pytest.raises(SystemExit, match="recorded index is for assembly"):
        pilot.verify_index(tmp_path)


def test_an_index_whose_recorded_reference_hash_differs_is_refused(tmp_path):
    index_record(tmp_path, assembly={"accession": ev.REFERENCE["assembly_accession"],
                                     "sha256_gz": "0" * 64,
                                     "sha256_decompressed": pilot.GENOME_SHA256_DECOMPRESSED})
    with pytest.raises(SystemExit, match="sha256_gz"):
        pilot.verify_index(tmp_path)


def test_a_missing_index_file_is_refused(tmp_path):
    index_record(tmp_path)
    (tmp_path / f"{pilot.INDEX_NAME}.5.ht2").unlink()
    with pytest.raises(SystemExit, match="index file missing"):
        pilot.verify_index(tmp_path)


def test_an_index_file_of_the_wrong_size_is_refused(tmp_path):
    index_record(tmp_path)
    # Truncated to a different length, so the size check is what rejects it.
    (tmp_path / f"{pilot.INDEX_NAME}.5.ht2").write_bytes(b"ab")
    with pytest.raises(SystemExit, match="bytes on disk"):
        pilot.verify_index(tmp_path)


def test_an_index_file_whose_content_changed_is_refused(tmp_path):
    index_record(tmp_path)
    path = tmp_path / f"{pilot.INDEX_NAME}.5.ht2"
    path.write_bytes(b"\xff" * path.stat().st_size)     # same size, different bytes
    with pytest.raises(SystemExit, match="sha256"):
        pilot.verify_index(tmp_path)


def test_an_index_record_with_fewer_than_eight_files_is_refused(tmp_path):
    record = index_record(tmp_path)
    record["files"].pop(f"{pilot.INDEX_NAME}.8.ht2")
    (tmp_path / pilot.INDEX_RECORD).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(SystemExit, match="expected 8"):
        pilot.verify_index(tmp_path)


def test_a_failing_pipeline_stage_fails_the_step_even_when_the_last_stage_exits_zero(tmp_path):
    """Regression: samtools sort exits 0 on a truncated stream from a failed collate."""
    # `false` stands for the failing stage; `cat` for a last stage that is happy
    # with an empty stream and returns 0. Without pipefail this returns 0.
    plain = subprocess.run("false | cat", shell=True, cwd=tmp_path)
    assert plain.returncode == 0, "the shell really does report only the last stage"
    with pytest.raises(SystemExit, match="step failed"):
        pilot.run_command("false | cat", tmp_path)


def test_a_pipeline_whose_every_stage_succeeds_is_recorded_verbatim(tmp_path):
    record = pilot.run_command("true | cat", tmp_path)
    assert record["returncode"] == 0
    assert record["command"] == "true | cat"
    assert "pipefail" in record["shell"]
