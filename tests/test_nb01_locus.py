"""Tests for the NB01 dsRNase locus mapping.

The locus logic is tested on synthetic HSPs and synthetic genomes, so none of it needs the
declared assemblies. The one test that uses a real input is the query derivation, which runs
against the repository anchor FASTA that ships with any checkout: that is the check that would
fail if the published ORF coordinates stopped falling out of the anchors.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from zeaguard import nb01_locus
from zeaguard.nb01_dsrnase_investigation import Hsp

ROOT = Path(__file__).resolve().parents[1]
ANCHORS = ROOT / "data/reference/target_anchor_sequences.fasta"

# The published ORF coordinates of Table 1 of Dalaison-Fuentes et al. 2023, which the
# derivation from the anchors must reproduce exactly.
PUBLISHED = [
    {"target_id": "dsRNase-1", "transcript_id": "TRINITY_DN13786_c0_g1_i8",
     "published_orf_start": 1640, "published_orf_end": 318, "cds_length": 1323, "protein_length": 440},
    {"target_id": "dsRNase-2", "transcript_id": "TRINITY_DN22752_c0_g2_i1",
     "published_orf_start": 1461, "published_orf_end": 37, "cds_length": 1425, "protein_length": 474},
    {"target_id": "dsRNase-3", "transcript_id": "TRINITY_DN5008_c0_g1_i24",
     "published_orf_start": 1539, "published_orf_end": 304, "cds_length": 1236, "protein_length": 411},
]


def hsp(qstart, qend, sstart, send, *, query="dsRNase-2", subject="chr1", qlen=1425, slen=100000,
        pident=100.0, mismatch=0, gaps=0, bitscore=None):
    """One HSP; the strand is read from the subject coordinates, as BLAST reports it."""
    length = abs(qend - qstart) + 1
    strand = "plus" if send >= sstart else "minus"
    return Hsp(query, subject, pident, length, qlen, slen, qstart, qend, sstart, send, strand,
               1e-50, bitscore if bitscore is not None else float(length), mismatch, 0, gaps,
               100.0, "")


# --------------------------------------------------------------------------- queries
def test_derive_queries_reproduces_the_published_orf_coordinates():
    rows = nb01_locus.derive_queries(ANCHORS, PUBLISHED)
    assert [row["target_id"] for row in rows] == ["dsRNase-1", "dsRNase-2", "dsRNase-3"]
    for row in rows:
        assert row["orf_coordinates_agree"] is True
        assert row["start_codon"] == "ATG"
        assert row["stop_codon"] in {"TAA", "TAG", "TGA"}
        assert row["cds_length"] == 3 * (row["protein_length"] + 1)
        assert len(row["cds"]) == row["cds_length"]


def test_derive_queries_refuses_a_wrong_published_coordinate():
    wrong = [{**PUBLISHED[1], "published_orf_start": 1462}]
    with pytest.raises(nb01_locus.LocusInputError, match="published ORF"):
        nb01_locus.derive_queries(ANCHORS, wrong)


def test_derive_queries_refuses_a_wrong_declared_length():
    wrong = [{**PUBLISHED[1], "cds_length": 1424}]
    with pytest.raises(nb01_locus.LocusInputError, match="cds_length"):
        nb01_locus.derive_queries(ANCHORS, wrong)


def test_derive_queries_refuses_an_absent_transcript():
    wrong = [{**PUBLISHED[1], "transcript_id": "TRINITY_ABSENT"}]
    with pytest.raises(nb01_locus.LocusInputError, match="not in"):
        nb01_locus.derive_queries(ANCHORS, wrong)


# --------------------------------------------------------------------------- clustering
def test_cluster_loci_splits_on_a_distance_above_the_intron_limit():
    near = [hsp(1, 700, 1000, 1699), hsp(701, 1425, 1699 + nb01_locus.MAX_INTRON_NT, 1699 + nb01_locus.MAX_INTRON_NT + 724)]
    assert len(nb01_locus.cluster_loci(near)) == 1
    far = [hsp(1, 700, 1000, 1699), hsp(701, 1425, 1700 + 2 * nb01_locus.MAX_INTRON_NT, 2424 + 2 * nb01_locus.MAX_INTRON_NT)]
    assert len(nb01_locus.cluster_loci(far)) == 2


def test_cluster_loci_never_merges_strands_or_sequences():
    mixed = [hsp(1, 700, 1000, 1699), hsp(1, 700, 1699, 1000), hsp(1, 700, 1000, 1699, subject="chr2")]
    assert len(nb01_locus.cluster_loci(mixed)) == 3


# --------------------------------------------------------------------------- tiling
def test_tile_hsps_keeps_the_best_of_two_overlapping_alignments():
    strong = hsp(1, 700, 1000, 1699, bitscore=900.0)
    weak = hsp(1, 700, 40000, 40699, bitscore=100.0)
    tiled = nb01_locus.tile_hsps([strong, weak])
    assert tiled == [strong]


def test_tile_hsps_keeps_both_exons_of_one_locus():
    first = hsp(1, 700, 1000, 1699)
    second = hsp(701, 1425, 5000, 5724)
    assert len(nb01_locus.tile_hsps([first, second])) == 2


def test_tile_hsps_tolerates_a_small_junction_overlap():
    first = hsp(1, 705, 1000, 1704)
    second = hsp(701, 1425, 5000, 5724)  # 5 nt of query overlap
    assert len(nb01_locus.tile_hsps([first, second])) == 2


def test_tiled_coverage_pct_is_the_union_over_the_query():
    assert nb01_locus.tiled_coverage_pct([hsp(1, 1425, 1, 1425)]) == 100.0
    half = nb01_locus.tiled_coverage_pct([hsp(1, 712, 1, 712)])
    assert 49.0 < half < 51.0


# --------------------------------------------------------------------------- splice sites
def synthetic_genome(exon_a="A" * 700, intron="GT" + "C" * 996 + "AG", exon_b="T" * 725,
                     flank="G" * 1000):
    return flank + exon_a + intron + exon_b + flank


def test_splice_junctions_read_canonical_termini_on_the_plus_strand():
    genome = synthetic_genome()
    exons = [hsp(1, 700, 1001, 1700), hsp(701, 1425, 2701, 3425)]
    assert nb01_locus.splice_junctions(exons, genome, "plus") == [("GT..AG", 0)]


def test_splice_junctions_read_canonical_termini_on_the_minus_strand():
    from zeaguard.nb01_identity import reverse_complement

    genome = reverse_complement(synthetic_genome())
    # the same locus, now on the other strand: subject coordinates mirror
    total = len(genome)
    a_start, a_end = total - 1700 + 1, total - 1001 + 1
    b_start, b_end = total - 3425 + 1, total - 2701 + 1
    exons = [hsp(1, 700, a_end, a_start), hsp(701, 1425, b_end, b_start)]
    assert nb01_locus.splice_junctions(exons, genome, "minus") == [("GT..AG", 0)]


def test_splice_junctions_report_a_non_canonical_intron_rather_than_hiding_it():
    genome = synthetic_genome(intron="AT" + "C" * 996 + "AC")
    exons = [hsp(1, 700, 1001, 1700), hsp(701, 1425, 2701, 3425)]
    # no shift in the window turns this into GT..AG, so the offset is None
    assert nb01_locus.splice_junctions(exons, genome, "plus") == [("AT..AC", None)]


def test_splice_junctions_find_a_canonical_site_the_alignment_boundary_overshot():
    """The real reason this matters: BLAST extends an exon a few bases into the intron.

    Here the true intron starts 3 nt later than the HSP boundary says, so the termini read
    at the boundary are not GT..AG, but a shift of +3 finds the canonical pair.
    """
    genome = synthetic_genome(exon_a="A" * 697 + "GGG", intron="GT" + "C" * 996 + "AG",
                              exon_b="T" * 725)
    exons = [hsp(1, 697, 1001, 1697), hsp(698, 1425, 2698, 3425)]
    observed, shift = nb01_locus.splice_junctions(exons, genome, "plus")[0]
    assert shift == 3
    assert observed != "GT..AG"
    assert nb01_locus.intron_termini(genome, 1697 + 3, 2698 + 3, "plus") == "GT..AG"


def test_splice_junctions_do_not_search_beyond_the_ambiguity_window():
    big = nb01_locus.MAX_TILE_OVERLAP_NT + 5
    genome = synthetic_genome(exon_a="A" * (700 - big) + "G" * big,
                              intron="GT" + "C" * 996 + "AG", exon_b="T" * 725)
    exons = [hsp(1, 700 - big, 1001, 1700 - big), hsp(701 - big, 1425, 2701 - big, 3425)]
    assert nb01_locus.splice_junctions(exons, genome, "plus")[0][1] is None


# --------------------------------------------------------------------------- locus rows
def sequences_for(name="chr1", length=None, description="Dalbulus maidis genome assembly, chromosome: 1"):
    return {name: {"description": description, "length": length, "n_count": 0,
                   "molecule": nb01_locus._molecule(description),
                   "role": "assembled-molecule" if "chromosome:" in description else "unlocalized-or-unplaced"}}


def test_locus_rows_reports_coverage_identity_and_inferred_structure():
    genome = synthetic_genome()
    exons = [hsp(1, 700, 1001, 1700), hsp(701, 1425, 2701, 3425)]
    rows = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})
    assert len(rows) == 1
    row = rows[0]
    assert row["query_coverage_pct"] == 100.0
    assert row["identity_pct"] == 100.0
    assert row["n_exons_inferred"] == 2
    assert row["n_introns_inferred"] == 1
    assert row["intron_sizes_nt"] == "1000"
    assert row["query_junction_offsets_nt"] == "0"
    assert row["splice_pairs_at_alignment_boundary"] == "GT..AG"
    assert row["canonical_splice_junctions"] == 1
    assert row["canonical_splice_shifts_nt"] == "0"
    assert row["colinear"] is True
    assert row["tier"] == "ASSIGNMENT_CRITERIA"
    assert row["molecule"] == "chromosome 1"
    assert row["locus_start"], row["locus_end"] == (1001, 3425)
    assert row["assembly_gap_nt_in_span"] == 0


def test_locus_rows_counts_assembly_gaps_inside_the_locus_span():
    genome = synthetic_genome(intron="GT" + "C" * 496 + "N" * 100 + "C" * 400 + "AG")
    exons = [hsp(1, 700, 1001, 1700), hsp(701, 1425, 2701, 3425)]
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    assert row["assembly_gap_nt_in_span"] == 100
    assert row["assembly_gap_runs_in_span"] == 1


def test_locus_rows_drops_a_cluster_below_the_related_coverage_threshold():
    genome = synthetic_genome()
    exons = [hsp(1, 200, 1001, 1200)]  # 200/1425 = 14 %
    assert nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome}) == []


def test_locus_rows_marks_a_diverged_locus_as_related_not_assignable():
    genome = synthetic_genome()
    exons = [hsp(1, 1425, 1001, 2425, pident=90.0, mismatch=142)]
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    assert row["query_coverage_pct"] == 100.0
    assert row["identity_pct"] < nb01_locus.ASSIGNMENT_MIN_IDENTITY_PCT
    assert row["tier"] == "RELATED"


def test_locus_rows_flags_a_non_colinear_cluster():
    genome = synthetic_genome()
    # the second half of the query aligns *before* the first half on a plus-strand locus
    exons = [hsp(1, 700, 2701, 3400), hsp(701, 1425, 1001, 1725)]
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    assert row["colinear"] is False


def test_locus_rows_reports_unaligned_query_nucleotides_at_a_junction():
    genome = synthetic_genome()
    exons = [hsp(1, 700, 1001, 1700), hsp(751, 1425, 2701, 3375)]  # 50 nt of CDS unaccounted
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    assert row["query_junction_offsets_nt"] == "50"
    assert row["query_coverage_pct"] < 100.0


def test_tiled_alignment_length_exceeds_the_cds_by_exactly_the_junction_overlap():
    """An invariant linking two reported columns, and the reason identity is trustworthy.

    With the CDS fully covered and no positive offset, every aligned nucleotide belongs to
    the CDS, counted once except at the tolerated junction overlaps. So the excess of
    ``aligned_nt`` over ``cds_length`` must equal the total overlap exactly; any other value
    would mean the tiling covers something outside the CDS, and the identity computed over
    ``aligned_nt`` would be measuring the wrong denominator.
    """
    genome = synthetic_genome()
    exons = [hsp(1, 704, 1001, 1704), hsp(701, 1425, 2701, 3425)]  # 4 nt of overlap
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    offsets = [int(x) for x in str(row["query_junction_offsets_nt"]).split(";") if x]
    assert all(off <= 0 for off in offsets)
    assert row["query_coverage_pct"] == 100.0
    assert int(row["aligned_nt"]) - int(row["cds_length"]) == -sum(offsets) == 4


def test_locus_rows_reports_a_junction_overlap_as_a_negative_offset():
    """A negative offset is alignment ambiguity, not missing CDS, so coverage stays complete."""
    genome = synthetic_genome()
    exons = [hsp(1, 705, 1001, 1705), hsp(701, 1425, 2701, 3425)]
    row = nb01_locus.locus_rows([exons], "asm", sequences_for(length=len(genome)), {"chr1": genome})[0]
    assert row["query_junction_offsets_nt"] == "-5"
    assert row["query_coverage_pct"] == 100.0


# --------------------------------------------------------------------------- calls
def locus(target, tier, locus_id, sequence="chr1", start=1000, end=4000, strand="plus"):
    return {"assembly_id": "asm", "target_id": target, "locus_id": locus_id, "tier": tier,
            "sequence_id": sequence, "molecule": "chromosome 1", "strand": strand,
            "locus_start": start, "locus_end": end, "query_coverage_pct": 99.0,
            "identity_pct": 99.5, "n_exons_inferred": 2, "related_locus_ids": ""}


def test_assignment_is_determined_for_exactly_one_passing_locus():
    rows = nb01_locus.assignment_rows("asm", [locus("dsRNase-3", "ASSIGNMENT_CRITERIA", "L1")], ["dsRNase-3"])
    assert rows[0]["status"] == nb01_locus.DETERMINED
    assert rows[0]["locus_id"] == "L1"
    assert rows[0]["n_loci_at_assignment_criteria"] == 1


def test_assignment_is_indeterminate_when_no_locus_passes():
    rows = nb01_locus.assignment_rows("asm", [locus("dsRNase-3", "RELATED", "L1")], ["dsRNase-3"])
    assert rows[0]["status"] == nb01_locus.INDETERMINATE
    assert rows[0]["status_reason"] == "NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA"
    assert rows[0]["n_related_loci"] == 1


def test_assignment_is_indeterminate_when_two_loci_pass():
    rows = nb01_locus.assignment_rows(
        "asm",
        [locus("dsRNase-2", "ASSIGNMENT_CRITERIA", "L1"),
         locus("dsRNase-2", "ASSIGNMENT_CRITERIA", "L2", start=500000, end=504000)],
        ["dsRNase-2"],
    )
    assert rows[0]["status"] == nb01_locus.INDETERMINATE
    assert rows[0]["status_reason"] == "MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA"
    assert rows[0]["n_loci_at_assignment_criteria"] == 2


def test_assignment_is_indeterminate_for_a_query_with_no_locus_at_all():
    rows = nb01_locus.assignment_rows("asm", [], ["dsRNase-1"])
    assert rows[0]["status"] == nb01_locus.INDETERMINATE
    assert rows[0]["n_loci_at_assignment_criteria"] == 0


# --------------------------------------------------------------------------- distinctness
def assigned(target, sequence, start, end, status=nb01_locus.DETERMINED):
    return {"target_id": target, "status": status, "sequence_id": sequence,
            "locus_start": start, "locus_end": end}


def test_distinct_loci_on_different_sequences():
    rows = nb01_locus.distinctness_rows(
        "asm", [assigned("dsRNase-1", "chr1", 100, 4000), assigned("dsRNase-3", "chr7", 100, 4000)])
    assert rows[0]["status"] == nb01_locus.DETERMINED
    assert rows[0]["status_reason"] == "DIFFERENT_ASSEMBLY_SEQUENCES"
    assert rows[0]["same_sequence"] is False


def test_distinct_loci_on_one_sequence_report_the_gap_between_them():
    rows = nb01_locus.distinctness_rows(
        "asm", [assigned("dsRNase-1", "chr1", 100, 4000), assigned("dsRNase-3", "chr1", 9001, 12000)])
    assert rows[0]["status"] == nb01_locus.DETERMINED
    assert rows[0]["status_reason"] == "SAME_SEQUENCE_NON_OVERLAPPING_SPANS"
    assert rows[0]["gap_between_spans_nt"] == 5000


def test_overlapping_spans_on_one_sequence_are_indeterminate_not_identical():
    rows = nb01_locus.distinctness_rows(
        "asm", [assigned("dsRNase-1", "chr1", 100, 4000), assigned("dsRNase-3", "chr1", 3000, 7000)])
    assert rows[0]["status"] == nb01_locus.INDETERMINATE
    assert rows[0]["status_reason"] == "OVERLAPPING_SPANS_ON_ONE_SEQUENCE"
    assert rows[0]["overlap_nt"] == 1001


def test_distinctness_is_indeterminate_when_either_locus_is_unassigned():
    rows = nb01_locus.distinctness_rows(
        "asm",
        [assigned("dsRNase-1", "chr1", 100, 4000),
         assigned("dsRNase-3", "", "", "", status=nb01_locus.INDETERMINATE)],
    )
    assert rows[0]["status"] == nb01_locus.INDETERMINATE
    assert rows[0]["status_reason"] == "UNASSIGNED_LOCUS:dsRNase-3"


def test_distinctness_covers_every_pair_of_three_targets():
    rows = nb01_locus.distinctness_rows(
        "asm",
        [assigned("dsRNase-1", "chr1", 100, 4000), assigned("dsRNase-2", "chr2", 100, 4000),
         assigned("dsRNase-3", "chr3", 100, 4000)],
    )
    assert {(r["target_a"], r["target_b"]) for r in rows} == {
        ("dsRNase-1", "dsRNase-2"), ("dsRNase-1", "dsRNase-3"), ("dsRNase-2", "dsRNase-3")}


# --------------------------------------------------------------------------- copy number
def test_copy_number_keys_the_reading_without_choosing_one():
    stats = {"number_of_sequences": 140, "scaffold_n50": 93705284}
    assignments = nb01_locus.assignment_rows(
        "asm", [locus("dsRNase-2", "ASSIGNMENT_CRITERIA", "L1")], ["dsRNase-2"])
    rows = nb01_locus.copy_number_rows("asm", assignments, stats, "Chromosome")
    assert rows[0]["interpretation_key"] == "ONE_LOCUS_DETECTED"
    assert rows[0]["n_loci_at_assignment_criteria"] == 1
    assert rows[0]["scaffold_n50"] == 93705284


def test_copy_number_reports_no_locus_detected_without_inventing_one():
    assignments = nb01_locus.assignment_rows("asm", [], ["dsRNase-1"])
    rows = nb01_locus.copy_number_rows(
        "asm", assignments, {"number_of_sequences": 1, "scaffold_n50": 1}, "Contig")
    assert rows[0]["interpretation_key"] == "NO_LOCUS_DETECTED"


# --------------------------------------------------------------------------- assembly FASTA
def write_assembly(path: Path) -> Path:
    path.write_text(
        ">chr1 Dalbulus maidis genome assembly, chromosome: 1\n"
        + "ACGT" * 25 + "\n" + "N" * 10 + "ACGT" * 10 + "\n"
        ">scf9 Dalbulus maidis genome assembly, unplaced scaffold\n"
        + "ACGT" * 5 + "\n",
        encoding="ascii", newline="\n",
    )
    return path


def test_scan_assembly_measures_what_the_file_actually_contains(tmp_path):
    path = write_assembly(tmp_path / "asm.fna")
    info, stats = nb01_locus.scan_assembly(path)
    assert stats["number_of_sequences"] == 2
    assert stats["total_sequence_length"] == 100 + 50 + 20
    assert stats["total_ungapped_length"] == 160
    assert stats["number_of_assembled_molecules"] == 1
    assert info["chr1"]["molecule"] == "chromosome 1"
    assert info["chr1"]["role"] == "assembled-molecule"
    assert info["scf9"]["role"] == "unlocalized-or-unplaced"
    assert info["chr1"]["n_count"] == 10


def test_scan_assembly_n50_is_the_length_at_half_the_assembly(tmp_path):
    path = tmp_path / "n50.fna"
    path.write_text(">a x\n" + "A" * 100 + "\n>b x\n" + "A" * 60 + "\n>c x\n" + "A" * 40 + "\n",
                    encoding="ascii", newline="\n")
    _, stats = nb01_locus.scan_assembly(path)
    assert stats["scaffold_n50"] == 100


def test_read_sequences_returns_only_what_was_asked_for(tmp_path):
    path = write_assembly(tmp_path / "asm.fna")
    assert set(nb01_locus.read_sequences(path, ["scf9"])) == {"scf9"}


def test_read_sequences_refuses_a_missing_sequence(tmp_path):
    path = write_assembly(tmp_path / "asm.fna")
    with pytest.raises(nb01_locus.LocusInputError, match="not found"):
        nb01_locus.read_sequences(path, ["chr1", "absent"])


def test_molecule_is_empty_when_the_defline_names_none():
    assert nb01_locus._molecule("Dalbulus maidis genome assembly, unplaced scaffold") == ""
    assert nb01_locus._molecule("x, linkage group: LG4") == "linkage group LG4"


def test_role_keeps_an_organelle_apart_from_the_nuclear_sequences():
    # This is what makes the declared sequence count reconcile with the NCBI scaffold count:
    # GCA_975739785.1 carries OZ319714.1, a mitochondrion, which NCBI's count excludes.
    assert nb01_locus._role("Dalbulus maidis genome assembly, organelle: mitochondrion") == "organelle"
    assert nb01_locus._role("Dalbulus maidis genome assembly, chromosome: X") == "assembled-molecule"
    assert nb01_locus._role(
        "Dalbulus maidis genome assembly, contig: HAP1_SCAFFOLD_15, whole genome shotgun sequence"
    ) == "unlocalized-or-unplaced"


def test_scan_assembly_counts_an_organelle_separately(tmp_path):
    path = tmp_path / "organelle.fna"
    path.write_text(
        ">chr1 Dalbulus maidis genome assembly, chromosome: 1\n" + "ACGT" * 25 + "\n"
        ">mito Dalbulus maidis genome assembly, organelle: mitochondrion\n" + "ACGT" * 5 + "\n",
        encoding="ascii", newline="\n",
    )
    _, stats = nb01_locus.scan_assembly(path)
    assert stats["number_of_sequences"] == 2
    assert stats["number_of_assembled_molecules"] == 1
    assert stats["number_of_organelle_sequences"] == 1


# --------------------------------------------------------------------------- declarations
def test_check_declared_stats_refuses_a_changed_assembly(tmp_path):
    declared = {"assembly_stats": {"number_of_sequences": 2, "total_sequence_length": 170}}
    observed = {"number_of_sequences": 2, "total_sequence_length": 171}
    with pytest.raises(nb01_locus.LocusInputError, match="total_sequence_length"):
        nb01_locus.check_declared_stats("asm", declared, observed)


def test_check_declared_stats_refuses_an_unknown_statistic():
    with pytest.raises(nb01_locus.LocusInputError, match="unknown assembly statistic"):
        nb01_locus.check_declared_stats("asm", {"assembly_stats": {"invented": 1}}, {})


def test_check_hash_refuses_a_changed_input(tmp_path):
    path = tmp_path / "input.gz"
    path.write_bytes(gzip.compress(b"payload"))
    good = hashlib.sha256(path.read_bytes()).hexdigest()
    assert nb01_locus._check_hash(path, {"verify": "sha256", "sha256": good, "path": "input.gz"}, "x")["sha256"] == good
    with pytest.raises(nb01_locus.LocusInputError, match="declared input changed"):
        nb01_locus._check_hash(path, {"verify": "sha256", "sha256": "0" * 64, "path": "input.gz"}, "x")


def test_check_hash_lf_normalizes_a_tracked_text_input(tmp_path):
    crlf = tmp_path / "text.txt"
    crlf.write_bytes(b"line\r\nline\r\n")
    expected = hashlib.sha256(b"line\nline\n").hexdigest()
    declared = {"verify": "sha256_lf_normalized", "sha256_lf_normalized": expected, "path": "text.txt"}
    assert nb01_locus._check_hash(crlf, declared, "x")["sha256_lf_normalized"] == expected


def test_check_hash_refuses_an_unknown_verify_mode(tmp_path):
    path = tmp_path / "x"
    path.write_bytes(b"x")
    with pytest.raises(nb01_locus.LocusInputError, match="unknown verify mode"):
        nb01_locus._check_hash(path, {"verify": "md5", "md5": "x", "path": "x"}, "x")


def test_resolve_names_the_download_url_of_a_missing_input(tmp_path):
    declared = {"path": "data/external/absent.gz", "source_url": "https://example.invalid/absent.gz"}
    with pytest.raises(nb01_locus.LocusInputError, match="example.invalid"):
        nb01_locus._resolve(tmp_path, declared, "absent")


def test_load_panel_refuses_a_file_of_another_kind(tmp_path):
    path = tmp_path / "panel.json"
    path.write_text(json.dumps({"kind": "something_else"}), encoding="utf-8")
    with pytest.raises(nb01_locus.LocusInputError, match="not a locus panel"):
        nb01_locus.load_panel(path)


# --------------------------------------------------------------------------- the shipped panel
def test_the_shipped_panel_declares_queries_that_match_the_anchors():
    panel = nb01_locus.load_panel(ROOT / nb01_locus.DEFAULT_PANEL)
    rows = nb01_locus.derive_queries(ANCHORS, panel["queries"])
    assert len(rows) == 3
    assert all(row["orf_coordinates_agree"] for row in rows)


def test_the_shipped_panel_declares_a_versioned_source_for_every_assembly():
    panel = nb01_locus.load_panel(ROOT / nb01_locus.DEFAULT_PANEL)
    assert panel["assemblies"], "the panel declares no assembly"
    for entry in panel["assemblies"]:
        assert entry["accession_version"].startswith(("GCA_", "GCF_"))
        assert entry["accession_version"].split(".")[-1].isdigit(), "accession carries no version"
        assert entry["source_url"].startswith("https://")
        assert len(entry["sha256"]) == 64
        assert entry["verify"] == "sha256"
        assert entry["reconstruction"]
        assert entry["assembly_stats"]["number_of_sequences"] > 0
