"""Tests for the splice-aware check's SAM parser and coordinate normalisation.

The cases this round requires explicitly: a reverse-strand record, soft (S) and
hard (H) clipping, an N junction, and supplementary records whose union covers
the whole query.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_nb01_dsrnase_splicing.py"
_spec = importlib.util.spec_from_file_location("check_nb01_dsrnase_splicing", SCRIPT)
splice = importlib.util.module_from_spec(_spec)
# Registered before execution so that @dataclass can resolve the module's own
# namespace under `from __future__ import annotations`.
sys.modules[_spec.name] = splice
_spec.loader.exec_module(splice)


def analyse_cigar(cigar: str, ref_start: int = 1001, reverse: bool = False):
    ops = splice.parse_cigar(cigar)
    read_len = splice.read_length_from_cigar(ops)
    walk = splice.normalise_walk(splice.walk_record(ops, ref_start), read_len, reverse)
    return read_len, walk


# --------------------------------------------------------------------------
# CIGAR parsing
# --------------------------------------------------------------------------


def test_parse_cigar_rejects_malformed_strings():
    assert splice.parse_cigar("10=") == [(10, "=")]
    with pytest.raises(splice.VerificationError):
        splice.parse_cigar("10=junk")
    with pytest.raises(splice.VerificationError):
        splice.parse_cigar("=10")


def test_read_length_counts_hard_clips_but_reference_ops_do_not():
    ops = splice.parse_cigar("5H10=100N20=3S")
    # 5 hard + 10 aligned + 20 aligned + 3 soft = 38; the 100 N is reference only.
    assert splice.read_length_from_cigar(ops) == 38


# --------------------------------------------------------------------------
# Junctions
# --------------------------------------------------------------------------


def test_single_n_junction_gives_two_blocks_and_intron_coordinates():
    read_len, walk = analyse_cigar("50=200N50=", ref_start=1001)
    assert read_len == 100
    assert len(walk["blocks"]) == 2
    assert len(walk["junctions"]) == 1
    junction = walk["junctions"][0]
    # Block 1 occupies 1001-1050, so the intron is 1051-1250 and block 2 starts at 1251.
    assert junction["intron_ref_start"] == 1051
    assert junction["intron_ref_end"] == 1250
    assert junction["intron_len"] == 200
    assert walk["blocks"][0]["r_start"] == 1001
    assert walk["blocks"][0]["r_end"] == 1050
    assert walk["blocks"][1]["r_start"] == 1251
    assert walk["blocks"][1]["r_end"] == 1300
    # The junction sits between query positions 50 and 51 in the original orientation.
    assert junction["query_pos_upstream_orig"] == 50
    assert junction["query_pos_downstream_orig"] == 51


def test_codon_phase_is_reported_from_the_upstream_query_position():
    _, walk = analyse_cigar("642=5126N594=")
    junction = walk["junctions"][0]
    assert junction["query_pos_upstream_orig"] == 642
    # 642 is divisible by 3, so the junction falls on a codon boundary.
    assert junction["codon_phase_after_upstream"] == 0

    _, walk = analyse_cigar("643=5126N593=")
    assert walk["junctions"][0]["codon_phase_after_upstream"] == 1


# --------------------------------------------------------------------------
# Clipping
# --------------------------------------------------------------------------


def test_soft_clipping_is_reported_on_the_correct_side_forward_strand():
    read_len, walk = analyse_cigar("10S80=10S", reverse=False)
    assert read_len == 100
    assert walk["clip_left"] == {"S": 10, "H": 0}
    assert walk["clip_right"] == {"S": 10, "H": 0}
    assert walk["blocks"][0]["q_start_orig"] == 11
    assert walk["blocks"][0]["q_end_orig"] == 90


def test_hard_and_soft_clipping_are_counted_separately():
    read_len, walk = analyse_cigar("5H10S70=15H", reverse=False)
    assert read_len == 100
    assert walk["clip_left"] == {"S": 10, "H": 5}
    assert walk["clip_right"] == {"S": 0, "H": 15}
    # The first aligned base is query position 16 in the original orientation.
    assert walk["blocks"][0]["q_start_orig"] == 16
    assert walk["blocks"][0]["q_end_orig"] == 85


def test_clipping_sides_swap_on_the_reverse_strand():
    read_len, walk = analyse_cigar("20H80=", reverse=True)
    assert read_len == 100
    # In record space the clip leads; in the original query orientation it trails.
    assert walk["clip_left"] == {"S": 0, "H": 0}
    assert walk["clip_right"] == {"S": 0, "H": 20}
    assert walk["blocks"][0]["q_start_orig"] == 1
    assert walk["blocks"][0]["q_end_orig"] == 80


# --------------------------------------------------------------------------
# Reverse strand normalisation
# --------------------------------------------------------------------------


def test_reverse_strand_blocks_are_renumbered_in_original_query_order():
    read_len, walk = analyse_cigar("30=500N70=", ref_start=2001, reverse=True)
    assert read_len == 100
    # Record space: block A = query 1-30, block B = query 31-100.
    # Original orientation: block A = 71-100, block B = 1-70, so B sorts first.
    first, second = walk["blocks"]
    assert (first["q_start_orig"], first["q_end_orig"]) == (1, 70)
    assert (second["q_start_orig"], second["q_end_orig"]) == (71, 100)
    # The genomic coordinates are untouched by the query-orientation flip.
    assert (first["r_start"], first["r_end"]) == (2531, 2600)
    assert (second["r_start"], second["r_end"]) == (2001, 2030)


def test_reverse_strand_junction_query_positions_are_adjacent_after_normalisation():
    _, walk = analyse_cigar("30=500N70=", reverse=True)
    junction = walk["junctions"][0]
    assert junction["query_pos_upstream_orig"] == 70
    assert junction["query_pos_downstream_orig"] == 71


def test_to_original_interval_is_an_involution():
    for start, end in [(1, 10), (41, 60), (100, 100)]:
        flipped = splice.to_original_interval(start, end, 100, True)
        assert splice.to_original_interval(*flipped, 100, True) == (start, end)


# --------------------------------------------------------------------------
# Indels and mismatches
# --------------------------------------------------------------------------


def test_insertions_and_deletions_are_counted_without_consuming_the_wrong_axis():
    read_len, walk = analyse_cigar("20=3I20=5D20=", ref_start=1001)
    assert read_len == 63  # 20 + 3 inserted + 20 + 20
    block = walk["blocks"][0]
    assert block["n_match"] == 60
    assert block["n_ins_nt"] == 3
    assert block["n_ins_events"] == 1
    assert block["n_del_nt"] == 5
    assert block["n_del_events"] == 1
    # Reference consumed: 20 + 20 + 5 deleted + 20 = 65.
    assert block["r_end"] - block["r_start"] + 1 == 65


def test_mismatch_positions_are_reported_in_original_query_coordinates():
    query = "ACGTACGTAC"
    reference = "NNNNACGTTCGTACNNNN"  # reference 1-based; alignment starts at 5
    ops = splice.parse_cigar("4=1X5=")
    differences = splice.mismatch_positions(ops, query, reference, 5, len(query), False)
    assert [d["kind"] for d in differences] == ["substitution"]
    assert differences[0]["query_pos_orig"] == 5
    assert differences[0]["query_base_record_space"] == "A"
    assert differences[0]["ref_base"] == "T"


def test_mismatch_positions_flip_on_the_reverse_strand():
    original = "ACGTACGTAC"
    record_query = splice.revcomp(original)  # what SAM stores for a reverse record
    reference = "N" * 4 + record_query[:4] + "A" + record_query[5:]
    ops = splice.parse_cigar("4=1X5=")
    differences = splice.mismatch_positions(ops, record_query, reference, 5,
                                            len(original), True)
    # Record-space position 5 is original-space position 10 - 5 + 1 = 6.
    assert differences[0]["query_pos_orig"] == 6


# --------------------------------------------------------------------------
# Union coverage and split alignments
# --------------------------------------------------------------------------


def test_union_length_merges_overlapping_and_adjacent_intervals():
    assert splice.union_length([]) == 0
    assert splice.union_length([(1, 10)]) == 10
    assert splice.union_length([(1, 10), (6, 20)]) == 20          # overlapping
    assert splice.union_length([(1, 10), (11, 20)]) == 20         # adjacent
    assert splice.union_length([(1, 10), (21, 30)]) == 20         # disjoint
    assert splice.union_length([(21, 30), (1, 10)]) == 20         # unsorted input


SAM_SPLIT = """@HD\tVN:1.6\tSO:unsorted
@SQ\tSN:OZ319704.1\tLN:122877750
split-query\t0\tOZ319704.1\t1001\t60\t600=400N42=594S\t*\t0\t0\t*\t*\tNM:i:0
split-query\t2048\tOZ319704.1\t200001\t60\t642H594=\t*\t0\t0\t*\t*\tNM:i:0
split-query\t256\tOZ319704.1\t900001\t0\t300=936S\t*\t0\t0\t*\t*\tNM:i:0
"""


def test_supplementary_records_union_covers_the_whole_query():
    header, records = splice.parse_sam(SAM_SPLIT)
    assert len(header) == 2
    assert [r.record_class for r in records] == ["primary", "supplementary", "secondary"]

    cds_len = 1236
    intervals = []
    for record in records:
        if record.record_class == "secondary":
            continue
        ops = splice.parse_cigar(record.cigar)
        read_len = splice.read_length_from_cigar(ops)
        assert read_len == cds_len
        walk = splice.normalise_walk(splice.walk_record(ops, record.pos),
                                     read_len, record.is_reverse)
        intervals.extend(walk["aligned_intervals_orig"])

    # Primary covers 1-642 in two blocks across one junction; the supplementary
    # covers 643-1236. Together they are the whole CDS, with no single record
    # covering it alone.
    assert splice.union_length(intervals) == cds_len
    assert sorted(intervals) == [(1, 600), (601, 642), (643, 1236)]


def test_secondary_records_stay_visible_as_alternatives():
    _, records = splice.parse_sam(SAM_SPLIT)
    secondary = [r for r in records if r.record_class == "secondary"]
    assert len(secondary) == 1
    assert secondary[0].pos == 900001
    # A secondary record is an alternative, not part of the split chain.
    assert secondary[0].is_secondary and not secondary[0].is_supplementary


def test_parse_sam_rejects_truncated_alignment_lines():
    with pytest.raises(splice.VerificationError):
        splice.parse_sam("bad\t0\tchr1\t1\t60\n")


def test_parse_sam_reads_tags_with_colons_in_the_value():
    _, records = splice.parse_sam(
        "q\t0\tchr1\t1\t60\t10=\t*\t0\t0\t*\t*\tcs:Z::10\tNM:i:0\n")
    assert records[0].tags["cs"] == ":10"
    assert records[0].tags["NM"] == "0"


# --------------------------------------------------------------------------
# Junction motifs
# --------------------------------------------------------------------------


def test_transcript_oriented_motif_is_the_reverse_complement_on_the_minus_strand():
    # A canonical intron read on the minus strand shows CT..AC on the forward genome.
    assert splice.revcomp("CTAC") == "GTAG"
    assert splice.revcomp("GTAG") == "CTAC"


# --------------------------------------------------------------------------
# Coverage counts only query positions aligned to a reference base
# --------------------------------------------------------------------------


def test_inserted_query_positions_are_not_counted_as_aligned_coverage():
    cds_len = 1425
    read_len, walk = analyse_cigar("700=25I700=", ref_start=69024822)
    assert read_len == cds_len

    # One block spanning the whole query, but 25 of those positions align to nothing.
    assert len(walk["blocks"]) == 1
    block = walk["blocks"][0]
    assert (block["q_start_orig"], block["q_end_orig"]) == (1, 1425)
    assert block["n_ins_nt"] == 25

    # Per record: 1,400 of 1,425 nt are aligned to the genome.
    per_record = splice.union_length(walk["aligned_intervals_orig"])
    assert per_record == 1400
    assert walk["aligned_intervals_orig"] == [(1, 700), (726, 1425)]

    # In the union across the group, the same 1,400 nt, not 1,425.
    group_union = splice.union_length(list(walk["aligned_intervals_orig"]))
    assert group_union == 1400
    assert per_record / cds_len < 1.0

    # The insertion is still reported, in its own field.
    assert splice.union_length(block["aligned_orig"]) == 1400


def test_aligned_intervals_exclude_insertions_on_the_reverse_strand_too():
    read_len, walk = analyse_cigar("700=25I700=", ref_start=1001, reverse=True)
    assert read_len == 1425
    assert splice.union_length(walk["aligned_intervals_orig"]) == 1400
    # Flipped: the 25 inserted positions sit at 701-725 in the original orientation.
    assert walk["aligned_intervals_orig"] == [(1, 700), (726, 1425)]


# --------------------------------------------------------------------------
# Synthetic fixtures for the control and label criteria
# --------------------------------------------------------------------------

ACCESSION = "OZ319704.1"


def make_item(cigar, pos, cds_len, flag=0, rname=ACCESSION, index=0,
              substitutions=(), genes=()):
    record = splice.SamRecord(qname="q", flag=flag, rname=rname, pos=pos,
                              mapq=60, cigar=cigar)
    ops = splice.parse_cigar(cigar)
    read_len = splice.read_length_from_cigar(ops)
    walk = splice.normalise_walk(splice.walk_record(ops, pos), read_len, record.is_reverse)
    subs = [{"kind": "substitution", "query_pos_orig": p} for p in substitutions]
    return {
        "record": record,
        "index": index,
        "walk": walk,
        "query_intervals": walk["aligned_intervals_orig"],
        "genes": list(genes),
        "substitutions": subs,
        "differences": list(subs),
        "cds_len": cds_len,
    }


def make_annotation(genes=(), transcripts=()):
    annotation = splice.Annotation()
    annotation.seqid_to_accession = {"1": ACCESSION}
    annotation.accession_to_seqid = {ACCESSION: "1"}
    for gene_id, start, end, strand, name in genes:
        annotation.genes[gene_id] = {
            "gene_id": gene_id, "name": name, "biotype": "protein_coding",
            "accession": ACCESSION, "start": start, "end": end, "strand": strand}
    for transcript_id, gene_id, strand, segments in transcripts:
        annotation.transcripts[transcript_id] = {
            "transcript_id": transcript_id, "gene_id": gene_id, "accession": ACCESSION,
            "strand": strand, "start": min(s for s, _ in segments),
            "end": max(e for _, e in segments), "canonical": True,
            "exon": list(segments), "CDS": list(segments)}
    return annotation


# --------------------------------------------------------------------------
# Control criteria
# --------------------------------------------------------------------------


def test_perfect_alignment_on_another_scaffold_fails_the_control():
    reference = splice.CONTROL_REFERENCE["dsRNase-2"]
    # A flawless, gapless, full-length 1,425 nt alignment, but on the wrong sequence.
    item = make_item("1425=", 500000, 1425, rname="OZ319705.1")
    annotation = make_annotation()
    row = splice.evaluate_control("dsRNase-2", reference, [item], annotation)

    assert row["verdict"] == "FAILED"
    assert "ref_name(observed=OZ319705.1)" in row["failed_requirements"]
    # Full coverage and a clean alignment are not on their own enough.
    assert row["union_covered_nt"] == 1425
    assert row["observed_nt_differences"] == 0
    assert row["observed_clip_nt"] == 0


def test_control_names_every_requirement_that_fails():
    reference = splice.CONTROL_REFERENCE["dsRNase-2"]
    # Wrong strand, clipped, short of full coverage, and no junctions.
    item = make_item("100S1325=", 69024822, 1425, flag=0x10)
    row = splice.evaluate_control("dsRNase-2", reference, [item], annotation=make_annotation())
    failed = row["failed_requirements"]
    assert row["verdict"] == "FAILED"
    for requirement in ("full_coverage", "no_clipping", "strand", "n_junctions"):
        assert requirement in failed, f"{requirement} missing from {failed}"


def test_control_rejects_an_unspliced_alignment_at_the_right_start():
    reference = splice.CONTROL_REFERENCE["dsRNase-1"]
    start = reference["ref_start"]
    # Full coverage, no clipping, no indels, right sequence, right strand and the
    # right start, but collapsed into one block: no junctions, so the genomic
    # interval stops 5,295 nt short of the expected end.
    item = make_item("1323=", start, 1323)
    row = splice.evaluate_control("dsRNase-1", reference, [item], make_annotation())

    assert row["union_covered_nt"] == 1323
    assert row["observed_clip_nt"] == 0
    assert row["observed_ref_name"] == reference["ref_name"]
    assert row["verdict"] == "FAILED"
    failed = row["failed_requirements"]
    assert "n_junctions(observed=0)" in failed
    assert f"ref_interval(observed={start}-{start + 1322})" in failed
    assert "difference_positions" in failed


# The real dsRNase-1 alignment, whose six blocks span exactly the expected
# interval and whose mismatch falls at query position 840.
DSRNASE1_CIGAR = "121=293N131=1141N231=1236N189=1608N167=1X60=1017N423="
DSRNASE1_SEGMENTS = [
    (60966751, 60966871), (60967165, 60967295), (60968437, 60968667),
    (60969904, 60970092), (60971701, 60971928), (60972946, 60973368),
]


def dsrnase1_annotation(strand):
    return make_annotation(
        genes=[("ENSCHMG00000002600", 60961200, 60974367, strand, "")],
        transcripts=[("ENSCHMT00000004227", "ENSCHMG00000002600", strand, DSRNASE1_SEGMENTS)])


def test_control_rejects_an_expected_transcript_on_the_opposite_strand():
    reference = splice.CONTROL_REFERENCE["dsRNase-1"]
    item = make_item(DSRNASE1_CIGAR, reference["ref_start"], 1323, substitutions=[840])

    # Identical intron coordinates, but the transcript is annotated on the
    # opposite strand, so none of its junctions may be credited.
    row = splice.evaluate_control("dsRNase-1", reference, [item], dsrnase1_annotation("-"))
    assert row["verdict"] == "FAILED"
    assert row["n_junctions_matching_expected_transcript"] == 0
    assert row["expected_junction_transcript_strand"] == "-"
    assert "junction_transcript_on_alignment_strand" in row["failed_requirements"]

    # The same coordinates on the matching strand pass every requirement, which
    # shows the strand is the only thing the rejection above turns on.
    row = splice.evaluate_control("dsRNase-1", reference, [item], dsrnase1_annotation("+"))
    assert row["failed_requirements"] == ""
    assert row["verdict"] == "AS_EXPECTED"
    assert row["n_junctions_matching_expected_transcript"] == 5


def test_control_reports_no_alignment_rather_than_passing_vacuously():
    reference = splice.CONTROL_REFERENCE["dsRNase-1"]
    row = splice.evaluate_control("dsRNase-1", reference, [], make_annotation())
    assert row["verdict"] == "FAILED"
    assert row["failed_requirements"] == "no_alignment"


# --------------------------------------------------------------------------
# dsRNase-3 chain labels
# --------------------------------------------------------------------------

# A two-block chain: query 1-642 then 643-1236, with a 5,130 nt junction.
CHAIN_POS = 122005058
CHAIN_CIGAR = "642=5130N594="
CHAIN_BLOCK_1 = (CHAIN_POS, CHAIN_POS + 641)                 # 122005058-122005699
CHAIN_INTRON = (CHAIN_POS + 642, CHAIN_POS + 642 + 5129)     # 122005700-122010829
CHAIN_BLOCK_2 = (CHAIN_INTRON[1] + 1, CHAIN_INTRON[1] + 594)  # 122010830-122011423


def chain_annotation(strand):
    """One transcript matching the chain exactly, and the two genes it crosses."""
    return make_annotation(
        genes=[
            (splice.GENE_UPSTREAM, CHAIN_BLOCK_1[0], CHAIN_BLOCK_1[1], strand, ""),
            (splice.GENE_DOWNSTREAM, CHAIN_BLOCK_2[0], CHAIN_BLOCK_2[1], strand, "ube2w"),
        ],
        transcripts=[
            ("ENSCHMT_FULL", splice.GENE_UPSTREAM, strand, [CHAIN_BLOCK_1, CHAIN_BLOCK_2]),
        ])


def classify(items, annotation):
    analysis = {"by_query": {"dsRNase-3": items}, "junction_rows": []}
    rows, transition = splice.classify_dsrnase3(analysis, annotation)
    return {r["outcome_key"]: r for r in rows}, transition


def test_full_chain_labels_are_observed_only_with_full_coverage_and_matching_strand():
    item = make_item(CHAIN_CIGAR, CHAIN_POS, 1236,
                     genes=[splice.GENE_UPSTREAM, splice.GENE_DOWNSTREAM])
    assert splice.union_length(item["query_intervals"]) == 1236

    outcomes, _ = classify([item], chain_annotation("+"))
    assert outcomes["CHAIN_MATCHES_SINGLE_ANNOTATED_MODEL"]["status"] == "OBSERVED"
    assert outcomes["CHAIN_SPANS_BOTH_ANNOTATED_GENES"]["status"] == "OBSERVED"


def test_a_record_covering_200_of_1236_nt_satisfies_no_full_chain_label():
    # Same two blocks, but only 200 nt of the query is aligned.
    cigar = f"100={CHAIN_INTRON[1] - CHAIN_BLOCK_1[0] - 98}N100=1036S"
    item = make_item(cigar, CHAIN_POS, 1236,
                     genes=[splice.GENE_UPSTREAM, splice.GENE_DOWNSTREAM])
    assert splice.union_length(item["query_intervals"]) == 200

    outcomes, _ = classify([item], chain_annotation("+"))
    assert outcomes["CHAIN_MATCHES_SINGLE_ANNOTATED_MODEL"]["status"] == "NOT_OBSERVED"
    assert outcomes["CHAIN_SPANS_BOTH_ANNOTATED_GENES"]["status"] == "NOT_OBSERVED"
    # The partial correspondence is recorded rather than dropped.
    assert outcomes["PARTIAL_CORRESPONDENCE_SPANNING_BOTH_GENES"]["status"] == "OBSERVED"
    assert "200/1236" in outcomes["PARTIAL_CORRESPONDENCE_SPANNING_BOTH_GENES"]["detail"]


def test_annotation_on_the_opposite_strand_satisfies_no_full_chain_label():
    item = make_item(CHAIN_CIGAR, CHAIN_POS, 1236,
                     genes=[splice.GENE_UPSTREAM, splice.GENE_DOWNSTREAM])
    assert splice.union_length(item["query_intervals"]) == 1236

    # The record is on +, the annotation on -. Coverage is full, so the strand
    # requirement is the only thing that can reject these labels.
    outcomes, transition = classify([item], chain_annotation("-"))
    assert outcomes["CHAIN_MATCHES_SINGLE_ANNOTATED_MODEL"]["status"] == "NOT_OBSERVED"
    assert outcomes["CHAIN_SPANS_BOTH_ANNOTATED_GENES"]["status"] == "NOT_OBSERVED"
    # The verdict and the transition table share one criterion, so the table
    # must be empty too rather than reporting a transition the verdict denies.
    assert transition == []

    # Same data on the matching strand: verdict observed and exactly one row,
    # which is what makes the assertions above meaningful.
    outcomes, transition = classify([item], chain_annotation("+"))
    assert outcomes["CHAIN_SPANS_BOTH_ANNOTATED_GENES"]["status"] == "OBSERVED"
    assert len(transition) == 1
    assert transition[0]["jump_len_nt"] == 5130


def test_transition_table_reports_a_partial_record_the_verdict_rejects():
    # Full coverage is a requirement of the complete-chain label only, so a
    # partial record still contributes a transition row.
    cigar = f"100={CHAIN_INTRON[1] - CHAIN_BLOCK_1[0] - 98}N100=1036S"
    item = make_item(cigar, CHAIN_POS, 1236,
                     genes=[splice.GENE_UPSTREAM, splice.GENE_DOWNSTREAM])
    assert splice.union_length(item["query_intervals"]) == 200

    outcomes, transition = classify([item], chain_annotation("+"))
    assert outcomes["CHAIN_SPANS_BOTH_ANNOTATED_GENES"]["status"] == "NOT_OBSERVED"
    assert len(transition) == 1


def test_single_model_correspondence_requires_the_same_strand():
    item = make_item(CHAIN_CIGAR, CHAIN_POS, 1236)
    assert splice.single_model_correspondence(item, chain_annotation("+"))["full"] == ["ENSCHMT_FULL"]
    assert splice.single_model_correspondence(item, chain_annotation("-"))["full"] == []


def test_crossing_junction_requires_the_same_strand():
    item = make_item(CHAIN_CIGAR, CHAIN_POS, 1236)
    crossing = splice.crossing_junction(item, chain_annotation("+"))
    assert crossing is not None
    assert crossing["intron_len"] == 5130
    assert crossing["query_pos_upstream_orig"] == 642
    assert splice.crossing_junction(item, chain_annotation("-")) is None


# --------------------------------------------------------------------------
# Aligner version
# --------------------------------------------------------------------------


def test_pg_version_is_read_from_the_sam_header():
    header = [
        "@HD\tVN:1.6\tSO:unsorted",
        "@PG\tID:minimap2\tPN:minimap2\tVN:2.31-r1302\tCL:minimap2 -a -x splice:hq g.fna q.fna",
    ]
    version, command = splice.pg_version_from_header(header)
    assert version == splice.MINIMAP2_EXPECTED_VERSION == "2.31-r1302"
    assert command.startswith("minimap2 -a -x splice:hq")


def test_pg_version_is_absent_when_the_header_has_no_pg_line():
    assert splice.pg_version_from_header(["@HD\tVN:1.6"]) == (None, None)


# --------------------------------------------------------------------------
# Output directory
# --------------------------------------------------------------------------


def test_default_output_directory_is_its_own_for_new_runs():
    # Earlier rounds' directories are results in their own right.
    assert splice.OUTPUT_SUBDIR.endswith("splice_check_v3")
    for earlier in ("splice_check_v1", "splice_check_v2_reanalysis"):
        assert not splice.OUTPUT_SUBDIR.endswith(earlier)


def test_existing_non_empty_output_directory_is_refused_with_its_files_intact(tmp_path):
    out_dir = tmp_path / "existing"
    out_dir.mkdir()
    kept = out_dir / "per_record.tsv"
    kept.write_text("query\tcds_len_fasta\ndsRNase-3\t1236\n", encoding="utf-8")
    nested = out_dir / "raw"
    nested.mkdir()
    (nested / "minimap2_splice_hq.sam").write_text("@HD\tVN:1.6\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in out_dir.rglob("*") if p.is_file()}

    with pytest.raises(splice.VerificationError) as error:
        splice.reserve_output_dir(out_dir)
    assert "not empty" in str(error.value)
    assert "--out-subdir" in str(error.value)

    # Nothing was written, removed or truncated, and no claim was left behind.
    after = {p: p.read_bytes() for p in out_dir.rglob("*") if p.is_file()}
    assert after == before
    assert kept.read_text(encoding="utf-8").startswith("query\tcds_len_fasta")
    assert not (out_dir / splice.LOCK_NAME).exists()


def test_empty_output_directory_is_accepted_whenever_it_is_free(tmp_path):
    absent = tmp_path / "fresh" / "nested"
    reservation = splice.reserve_output_dir(absent)
    assert reservation.out_dir == absent
    assert absent.is_dir()
    reservation.release()

    # Released, still empty: accepted again.
    second = splice.reserve_output_dir(absent)
    assert second.out_dir == absent
    second.release()
    assert not (absent / splice.LOCK_NAME).exists()


def test_output_path_that_is_a_file_is_refused(tmp_path):
    occupied = tmp_path / "not_a_dir"
    occupied.write_text("x", encoding="utf-8")
    with pytest.raises(splice.VerificationError) as error:
        splice.reserve_output_dir(occupied)
    assert "not a directory" in str(error.value)
    assert occupied.read_text(encoding="utf-8") == "x"


def test_a_held_reservation_refuses_a_second_run_on_the_same_empty_destination(tmp_path):
    # Deterministic: the second attempt happens while the first claim is held,
    # which is exactly the window the emptiness test alone left open.
    out_dir = tmp_path / "shared"
    first = splice.reserve_output_dir(out_dir)
    try:
        with pytest.raises(splice.VerificationError) as error:
            splice.reserve_output_dir(out_dir)
        assert "reserved by another run" in str(error.value)
        assert "nothing was written" in str(error.value)
        # The refusal happened before any output could be written.
        assert sorted(p.name for p in out_dir.iterdir()) == [splice.LOCK_NAME]
    finally:
        first.release()
    assert list(out_dir.iterdir()) == []


OUTPUT_NAMES = [
    "per_record.tsv", "per_junction.tsv", "per_block.tsv", "controls.tsv",
    "dsrnase3_chain_classification.tsv", "dsrnase3_transition.tsv",
    "junction_vs_historical.tsv", "manifest.json",
]


def test_two_concurrent_runs_on_one_empty_destination_elect_a_single_writer(tmp_path):
    """Both runs start against the same empty directory, as in the reported failure.

    Before the claim, both passed the emptiness test and both wrote all eight
    files, each returning 0. Exactly one may write now.
    """
    out_dir = tmp_path / "contested"
    out_dir.mkdir()
    start = threading.Barrier(2)
    outcomes: list[tuple[str, str]] = []
    guard = threading.Lock()

    def attempt(name: str) -> None:
        start.wait(timeout=10)
        try:
            reservation = splice.reserve_output_dir(out_dir)
        except splice.VerificationError as error:
            with guard:
                outcomes.append(("refused", name))
            assert "nothing was written" in str(error)
            return
        try:
            for output in OUTPUT_NAMES:
                (out_dir / output).write_text(name, encoding="utf-8")
            with guard:
                outcomes.append(("wrote", name))
        finally:
            reservation.release()

    threads = [threading.Thread(target=attempt, args=(n,)) for n in ("run-A", "run-B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert not any(t.is_alive() for t in threads)

    # One writer, one refusal, whichever of the two won the race.
    assert sorted(kind for kind, _ in outcomes) == ["refused", "wrote"]
    winner = next(name for kind, name in outcomes if kind == "wrote")

    # Exactly the eight files, all from the single authorised writer, and the
    # claim released. The loser contributed nothing.
    assert sorted(p.name for p in out_dir.iterdir()) == sorted(OUTPUT_NAMES)
    assert {(out_dir / o).read_text(encoding="utf-8") for o in OUTPUT_NAMES} == {winner}
    assert not (out_dir / splice.LOCK_NAME).exists()


def test_a_completed_run_leaves_the_destination_refusable_by_the_next_run(tmp_path):
    out_dir = tmp_path / "done"
    with splice.reserve_output_dir(out_dir):
        (out_dir / "per_record.tsv").write_text("x", encoding="utf-8")

    # The claim is gone but the outputs remain, so the next run is refused for
    # content rather than for the claim.
    assert not (out_dir / splice.LOCK_NAME).exists()
    with pytest.raises(splice.VerificationError) as error:
        splice.reserve_output_dir(out_dir)
    assert "not empty" in str(error.value)
