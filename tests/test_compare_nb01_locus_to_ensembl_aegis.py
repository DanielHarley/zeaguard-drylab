from __future__ import annotations

from scripts import compare_nb01_locus_to_ensembl_aegis as cmp


def make_locus(target_id: str, exon_blocks_subject: list[tuple[int, int]], strand: str = "+") -> dict:
    starts = [s for s, _ in exon_blocks_subject]
    ends = [e for _, e in exon_blocks_subject]
    return {
        "target_id": target_id,
        "gff3_strand": strand,
        "exon_blocks_subject": list(exon_blocks_subject),
        "locus_start": min(starts),
        "locus_end": max(ends),
    }


def make_index(genes: dict, transcripts: dict, cds: dict) -> cmp.Gff3Index:
    index = cmp.Gff3Index()
    index.genes = genes
    index.transcripts = transcripts
    index.cds = cds
    index.finalize()
    return index


def gene(gene_id: str, start: int, end: int, strand: str = "+", name: str = "") -> dict:
    return {"gene_id": gene_id, "name": name, "biotype": "protein_coding", "start": start, "end": end, "strand": strand}


def transcript(transcript_id: str, gene_id: str, start: int, end: int, strand: str = "+", canonical: bool = False) -> dict:
    return {"transcript_id": transcript_id, "gene_id": gene_id, "start": start, "end": end,
            "strand": strand, "is_canonical": canonical}


def run(locus, index, mode="exact", max_tol=0):
    return cmp.compare_locus_at_tolerance(locus, index, mode, max_tol=max_tol)


# ---------------------------------------------------------------------------
# boundary_cost / transcription_sort primitives
# ---------------------------------------------------------------------------

def test_boundary_cost_is_symmetric_in_strand_labelling():
    a, b = (100, 200), (105, 196)
    assert cmp.boundary_cost(a, b) == (9, -5, 4)


def test_transcription_sort_reverses_on_minus_strand():
    segs = [(100, 200), (300, 400), (500, 600)]
    assert cmp.transcription_sort(segs, "+") == [(100, 200), (300, 400), (500, 600)]
    assert cmp.transcription_sort(segs, "-") == [(500, 600), (300, 400), (100, 200)]


def test_structural_match_classification():
    assert cmp.structural_match(0, 3, 3)[0] == "NO_PAIRS"
    assert cmp.structural_match(2, 3, 3)[0] == "PARTIAL_UNMATCHED_BLOCKS"
    assert cmp.structural_match(3, 3, 4)[0] == "PARTIAL_SKIPPED_SEGMENT"
    assert cmp.structural_match(3, 3, 3)[0] == "FULL"


# ---------------------------------------------------------------------------
# (a) two isoforms that share CDS segments must each be scored on their own,
# not starved by a shared pool that the other isoform drained first.
# ---------------------------------------------------------------------------

def test_shared_segments_do_not_starve_either_isoform():
    nb01 = [(100, 200), (300, 400), (500, 600)]
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G": gene("G", 90, 650)},
        transcripts={
            "TX_LONG": transcript("TX_LONG", "G", 90, 650, canonical=True),
            "TX_SHORT": transcript("TX_SHORT", "G", 90, 400),
        },
        cds={
            "TX_LONG": [(100, 200), (300, 400), (500, 600)],
            "TX_SHORT": [(100, 200), (300, 400)],  # shares both segments with TX_LONG
        },
    )
    rows, pairs, _, summary = run(locus, index)
    by_tx = {r["transcript_id"]: r for r in rows}
    assert by_tx["TX_LONG"]["n_matched_pairs"] == 3
    assert by_tx["TX_SHORT"]["n_matched_pairs"] == 2  # not starved to 0 by TX_LONG claiming the shared pair first
    assert by_tx["TX_SHORT"]["unmatched_cds_segment_ranks"] == ""
    assert by_tx["TX_LONG"]["gene_support_status"] == "DETERMINED"
    assert by_tx["TX_LONG"]["is_tied_best_transcript"] is True
    assert by_tx["TX_SHORT"]["is_tied_best_transcript"] is False
    # The shared segments show up as their own rows for BOTH transcripts.
    assert len([p for p in pairs if p["transcript_id"] == "TX_SHORT"]) == 2
    assert len([p for p in pairs if p["transcript_id"] == "TX_LONG"]) == 3
    assert summary["n_candidate_transcripts"] == 2


# ---------------------------------------------------------------------------
# (b) a genuine tie between transcripts: same gene -> gene-level assignment
# still stands; different genes -> locus stays INDETERMINATE.
# ---------------------------------------------------------------------------

def test_tie_between_isoforms_of_the_same_gene_keeps_gene_level_determined():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G": gene("G", 90, 450)},
        transcripts={
            "TX_A": transcript("TX_A", "G", 90, 450, canonical=True),
            "TX_B": transcript("TX_B", "G", 90, 450),
        },
        cds={
            # Identical segment sets for both isoforms -> a genuine tie: same
            # 2 pairs, same total cost (4+4)+(4+4) = 16, well within tolerance.
            "TX_A": [(104, 204), (296, 396)],
            "TX_B": [(104, 204), (296, 396)],
        },
    )
    rows, _, _, summary = run(locus, index, "exploratory_20nt", max_tol=20)
    by_tx = {r["transcript_id"]: r for r in rows}
    assert by_tx["TX_A"]["n_matched_pairs"] == by_tx["TX_B"]["n_matched_pairs"] == 2
    assert by_tx["TX_A"]["total_boundary_cost_nt"] == by_tx["TX_B"]["total_boundary_cost_nt"]
    assert by_tx["TX_A"]["gene_support_status"] == "DETERMINED"
    assert "isoforms of" in by_tx["TX_A"]["gene_support_reason"]
    assert by_tx["TX_A"]["is_tied_best_transcript"] is True
    assert by_tx["TX_B"]["is_tied_best_transcript"] is True
    assert summary["gene_support_status"] == "DETERMINED"
    assert set(summary["best_transcript_ids"].split(",")) == {"TX_A", "TX_B"}


def test_tie_between_transcripts_of_different_genes_stays_indeterminate():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G1": gene("G1", 90, 450), "G2": gene("G2", 90, 450)},
        transcripts={
            "TX_G1": transcript("TX_G1", "G1", 90, 450, canonical=True),
            "TX_G2": transcript("TX_G2", "G2", 90, 450, canonical=True),
        },
        cds={
            "TX_G1": [(100, 200), (300, 400)],  # exact, cost 0
            "TX_G2": [(100, 200), (300, 400)],  # identical structure, also cost 0 -> genuine cross-gene tie
        },
    )
    rows, _, _, summary = run(locus, index)
    by_tx = {r["transcript_id"]: r for r in rows}
    assert by_tx["TX_G1"]["gene_support_status"] == "INDETERMINATE_CROSS_GENE_TIE"
    assert "distinct genes" in by_tx["TX_G1"]["gene_support_reason"]
    assert by_tx["TX_G1"]["is_tied_best_transcript"] is True
    assert by_tx["TX_G2"]["is_tied_best_transcript"] is True
    assert summary["gene_support_status"] == "INDETERMINATE_CROSS_GENE_TIE"


# ---------------------------------------------------------------------------
# (c) a skipped CDS segment: the alignment must jump over it, not force a
# false adjacency; the junction spanning it is flagged, AND gene support can
# still stand even though the structural match is only partial.
# ---------------------------------------------------------------------------

def test_skipped_cds_segment_is_reported_not_silently_bridged():
    nb01 = [(100, 200), (300, 400), (700, 800)]  # no block for the real 3rd exon (500, 600)
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G": gene("G", 90, 850)},
        transcripts={"TX": transcript("TX", "G", 90, 850, canonical=True)},
        cds={"TX": [(100, 200), (300, 400), (500, 600), (700, 800)]},
    )
    rows, _, junctions, summary = run(locus, index)
    row = rows[0]
    assert row["n_matched_pairs"] == 3
    assert row["unmatched_cds_segment_ranks"] == "3"
    assert row["unmatched_nb01_block_ranks"] == ""
    j = {r["junction_index"]: r for r in junctions}
    assert j[1]["status"] == "MATCHED"
    assert j[2]["status"] == "SKIPPED_CDS_SEGMENT"
    assert j[2]["comparable"] is False
    assert j[2]["gff3_cds_ranks"] == "2-4"
    assert "1 CDS segment(s)" in j[2]["note"]


def test_gene_support_determined_can_coexist_with_partial_structural_match():
    """Every NB01 block finds a home (gene support stands), but the winning
    transcript has one extra CDS segment NB01 never saw -- the structural
    match must be reported as PARTIAL, independently of gene support."""
    nb01 = [(100, 200), (300, 400), (700, 800)]  # 3 blocks; nothing for (500, 600)
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G": gene("G", 90, 850)},
        transcripts={"TX": transcript("TX", "G", 90, 850, canonical=True)},
        cds={"TX": [(100, 200), (300, 400), (500, 600), (700, 800)]},  # 4 segments
    )
    rows, _, _, summary = run(locus, index)
    row = rows[0]
    assert row["n_matched_pairs"] == len(nb01) == 3  # every NB01 block IS accounted for
    assert row["gene_support_status"] == "DETERMINED"
    assert row["structural_match_status"] == "PARTIAL_SKIPPED_SEGMENT"
    assert summary["gene_support_status"] == "DETERMINED"
    assert summary["structural_match_status"] == "PARTIAL_SKIPPED_SEGMENT"


# ---------------------------------------------------------------------------
# (d) minus-strand reading order: segments are stored on disk in ascending
# genomic order regardless of strand; matching must still respect
# transcription order, not raw genomic order.
# ---------------------------------------------------------------------------

def test_minus_strand_blocks_match_in_transcription_order_not_genomic_order():
    # Genomic-ascending order, as both loci.tsv and GFF3 always store it.
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01, strand="-")
    index = make_index(
        genes={"G": gene("G", 90, 450, strand="-")},
        transcripts={"TX": transcript("TX", "G", 90, 450, strand="-", canonical=True)},
        cds={"TX": [(105, 205), (305, 405)]},
    )
    rows, _, junctions, _ = run(locus, index, "exploratory_20nt", max_tol=20)
    row = rows[0]
    # Correct (strand-aware) pairing: (100,200)<->(105,205) cost 10, (300,400)<->(305,405) cost 10.
    assert row["n_matched_pairs"] == 2
    assert row["total_boundary_cost_nt"] == 20
    assert row["unmatched_nb01_block_ranks"] == ""
    assert row["unmatched_cds_segment_ranks"] == ""
    assert len(junctions) == 1
    assert junctions[0]["status"] == "MATCHED"


def test_minus_strand_wrong_order_would_fail_naively():
    # Sanity companion: confirms the genomic-order (unsorted) pairing used by
    # the old, strand-naive approach would NOT have matched, so the fix above
    # is load-bearing rather than vacuous.
    a, b = (100, 200), (305, 405)
    cost, _, _ = cmp.boundary_cost(a, b)
    assert cost > cmp.MATCH_TOLERANCE_EXPLORATORY_NT


# ---------------------------------------------------------------------------
# (e) a locus with no overlapping gene model at all must still produce an
# explicit summary row -- not silence by omission.
# ---------------------------------------------------------------------------

def test_locus_with_no_candidate_gene_reports_explicit_summary():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01)
    index = make_index(genes={}, transcripts={}, cds={})
    rows, pairs, junctions, summary = run(locus, index)
    assert rows == [] and pairs == [] and junctions == []
    assert summary["n_candidate_genes"] == 0
    assert summary["n_candidate_transcripts"] == 0
    assert summary["gene_support_status"] == "NO_CANDIDATE_GENE"
    assert summary["best_n_matched_pairs"] == 0
    assert summary["best_transcript_ids"] == ""
    assert summary["structural_match_status"] == "NOT_APPLICABLE"


def test_locus_with_gene_on_wrong_strand_also_reports_no_candidate_gene():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01, strand="+")
    index = make_index(
        genes={"G": gene("G", 90, 450, strand="-")},  # overlaps by position, wrong strand
        transcripts={"TX": transcript("TX", "G", 90, 450, strand="-", canonical=True)},
        cds={"TX": [(100, 200), (300, 400)]},
    )
    _, _, _, summary = run(locus, index)
    assert summary["gene_support_status"] == "NO_CANDIDATE_GENE"
    assert summary["n_candidate_genes"] == 0


# ---------------------------------------------------------------------------
# (f) a candidate model that scores zero pairs must still be reported, not
# dropped, and the locus must say so explicitly rather than falling back to
# a generic "partial coverage" message.
# ---------------------------------------------------------------------------

def test_model_with_zero_matched_pairs_is_reported_explicitly():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G": gene("G", 50, 450)},  # overlaps the locus positionally...
        transcripts={"TX": transcript("TX", "G", 50, 450, canonical=True)},
        cds={"TX": [(50, 150), (350, 450)]},  # ...but its own exons sit nowhere near either NB01 block
    )
    rows, pairs, junctions, summary = run(locus, index, "exploratory_20nt", max_tol=20)
    row = rows[0]
    assert row["n_matched_pairs"] == 0
    assert row["structural_match_status"] == "NO_PAIRS"
    assert pairs == []  # a transcript with 0 matched pairs contributes 0 pair rows, not a crash
    assert summary["gene_support_status"] == "NO_PAIRS_MATCHED"
    assert summary["best_n_matched_pairs"] == 0
    # NO_PAIRS_MATCHED means there is no "best" explanation to roll up at
    # all -- best_gene_ids/best_transcript_ids/closest_model_* stay empty,
    # even though the candidate's own row above still reports NO_PAIRS.
    assert summary["best_gene_ids"] == ""
    assert summary["best_transcript_ids"] == ""
    assert summary["closest_model_transcript_id"] == ""
    assert summary["structural_match_status"] == "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# (g) two DIFFERENT genes each fully explain the locus at different cost: the
# cheaper one must not silently win. Both are preserved as a genuine
# cross-gene ambiguity; the cheaper one is only ever surfaced as a separate
# "closest model" pointer, never as the resolution of the tie.
# ---------------------------------------------------------------------------

def test_full_coverage_tie_across_genes_survives_unequal_cost():
    nb01 = [(100, 200), (300, 400)]
    locus = make_locus("T", nb01)
    index = make_index(
        genes={"G_CHEAP": gene("G_CHEAP", 90, 450), "G_EXPENSIVE": gene("G_EXPENSIVE", 90, 450)},
        transcripts={
            "TX_CHEAP": transcript("TX_CHEAP", "G_CHEAP", 90, 450, canonical=True),
            "TX_EXPENSIVE": transcript("TX_EXPENSIVE", "G_EXPENSIVE", 90, 450, canonical=True),
        },
        cds={
            "TX_CHEAP": [(100, 200), (300, 400)],  # cost 0, full coverage
            "TX_EXPENSIVE": [(102, 200), (300, 402)],  # cost 2+0 + 0+2 = 4, also full coverage
        },
    )
    rows, _, _, summary = run(locus, index, "exploratory_20nt", max_tol=20)
    by_tx = {r["transcript_id"]: r for r in rows}
    assert by_tx["TX_CHEAP"]["n_matched_pairs"] == by_tx["TX_EXPENSIVE"]["n_matched_pairs"] == 2
    assert by_tx["TX_CHEAP"]["total_boundary_cost_nt"] == 0
    assert by_tx["TX_EXPENSIVE"]["total_boundary_cost_nt"] == 4
    # Despite the cost difference, BOTH count as gene support -- a cheaper
    # match does not resolve which gene the locus belongs to.
    assert by_tx["TX_CHEAP"]["gene_support_status"] == "INDETERMINATE_CROSS_GENE_TIE"
    assert by_tx["TX_EXPENSIVE"]["gene_support_status"] == "INDETERMINATE_CROSS_GENE_TIE"
    assert by_tx["TX_CHEAP"]["is_tied_best_transcript"] is True
    assert by_tx["TX_EXPENSIVE"]["is_tied_best_transcript"] is True
    assert summary["gene_support_status"] == "INDETERMINATE_CROSS_GENE_TIE"
    assert set(summary["best_gene_ids"].split(",")) == {"G_CHEAP", "G_EXPENSIVE"}
    assert set(summary["best_transcript_ids"].split(",")) == {"TX_CHEAP", "TX_EXPENSIVE"}
    # The cheaper model is surfaced separately, not as a tiebreak winner.
    assert summary["closest_model_gene_id"] == "G_CHEAP"
    assert summary["closest_model_transcript_id"] == "TX_CHEAP"
    assert summary["closest_model_cost_nt"] == 0


# ---------------------------------------------------------------------------
# (h) alignment reconstruction must not re-explore equivalent skip orderings.
# With 12 blocks and 12 segments that never match, the naive recursive
# backtrack walks C(24, 12) ~= 2.7M monotonic paths (measured ~1s); the
# memoized bottom-up version does O(n*m) work and must return in well under
# that, with a single (empty) alignment, not 2.7M duplicates of it.
# ---------------------------------------------------------------------------

def test_no_match_alignment_does_not_reexplore_equivalent_skip_paths():
    import time

    nb01_sorted = [(i * 1000, i * 1000 + 10) for i in range(12)]
    # Offset by 1 nt from every NB01 block, including the one at the same
    # index, so every pairwise cost is >= 2 nt -- strictly above max_tol=0.
    cds_sorted = [(i * 1000 + 1, i * 1000 + 11) for i in range(12)]
    started = time.perf_counter()
    value, alignments = cmp.align_transcript(nb01_sorted, cds_sorted, max_tol=0)
    elapsed = time.perf_counter() - started
    assert value == (0, 0)
    assert alignments == [[]]
    assert elapsed < 0.3, f"took {elapsed:.3f}s -- looks like the old re-exploration regressed"
