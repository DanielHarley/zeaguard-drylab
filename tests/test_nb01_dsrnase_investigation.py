from __future__ import annotations

import pytest

from zeaguard import nb01_dsrnase_investigation as inv
from zeaguard.nb01_identity import reverse_complement

CDS = "ATG" + "GCT" + "GCT" + "GCT" + "AAA" + "GGC" + "TCT" + "TAA"  # M A A A K G S *
FLANK5, FLANK3 = "CCCCC", "GGGGG"
TRANSCRIPT = FLANK5 + CDS + FLANK3


def hsp(query="q", subject="s", qstart=1, qend=100, sstart=1, send=100, strand="plus", qlen=200, bitscore=100.0, evalue=1e-30):
    return inv.Hsp(query, subject, 99.0, qend - qstart + 1, qlen, 1000, qstart, qend, sstart, send, strand,
                   evalue, bitscore, 1, 0, 0, 50.0, f"{qend - qstart + 1}")


# ------------------------------------------------------------------ basics / coordinates
def test_reverse_complement_is_involutive_and_handles_iupac():
    assert reverse_complement("ATGCRYN") == "NRYGCAT"
    assert reverse_complement(reverse_complement(TRANSCRIPT)) == TRANSCRIPT


def test_translate_standard_and_internal_stop():
    assert inv.translate(CDS) == "MAAAKGS*"
    assert inv.translate(CDS, to_stop=True) == "MAAAKGS"
    assert inv.translate("ATGTAAGCT") == "M*A"  # stop kept in the middle, never silently dropped


def test_translate_resolves_unambiguous_iupac_codons_and_flags_the_rest():
    assert inv.translate("CTN") == "L"  # all four resolutions are Leu
    assert inv.translate("AGR") == "R"
    assert inv.translate("ARA") == "X"  # AAA (K) or AGA (R)
    assert inv.translate("NNN") == "X"
    assert inv.codon_amino_acids("ARA") == frozenset("KR")
    assert inv.count_ambiguous("ACGTNRY") == 3


def test_zero_to_one_based_conversion_round_trip():
    assert inv.to_one_based(0, 3) == (1, 3)
    assert inv.to_zero_based(1, 3) == (0, 3)
    assert inv.to_zero_based(*inv.to_one_based(7, 19)) == (7, 19)
    with pytest.raises(ValueError):
        inv.to_one_based(5, 5)
    with pytest.raises(ValueError):
        inv.to_zero_based(0, 3)


# ------------------------------------------------------------------ ORFs
def _the_orf(orfs, protein):
    """The open segment ending in ``protein``; segments are maximal and may carry upstream residues."""
    return next(o for o in orfs if o.protein.endswith(protein))


def test_complete_orf_forward_coordinates_are_one_based_inclusive():
    orf = _the_orf(inv.find_orfs(TRANSCRIPT, min_aa=5), "MAAAKGS")
    assert (orf.strand, orf.end, orf.has_stop) == ("+", 5 + len(CDS), True)
    assert TRANSCRIPT[orf.start - 1 : orf.end].endswith(CDS)
    assert inv.orf_sequence(TRANSCRIPT, orf).endswith(CDS) and len(inv.orf_sequence(TRANSCRIPT, orf)) == 3 * (len(orf.protein) + 1)


def test_orf_on_reverse_strand_is_reported_on_forward_coordinates():
    rc = reverse_complement(TRANSCRIPT)
    orf = _the_orf(inv.find_orfs(rc, min_aa=5), "MAAAKGS")
    assert orf.strand == "-"
    assert reverse_complement(rc[orf.start - 1 : orf.end]) == inv.orf_sequence(rc, orf)
    assert inv.orf_sequence(rc, orf).endswith(CDS)
    # forward coordinates: the stop codon (reverse complement of TAA) is the first base of the region
    assert orf.start == 1 + len(FLANK3) and rc[orf.start - 1 : orf.start + 2] == reverse_complement("TAA")


def test_orf_without_stop_runs_to_the_transcript_end():
    open_ended = FLANK5 + CDS[:-3]  # stop removed
    orf = _the_orf(inv.find_orfs(open_ended, min_aa=5), "MAAAKGS")
    assert orf.has_stop is False
    info = inv.infer_cds(open_ended, orf, "MAAAKGS")
    assert info["three_prime"] == "TRUNCATED_AT_TRANSCRIPT_END"


def test_orf_without_start_codon_is_flagged_as_truncated_and_never_invented():
    headless = CDS[3:] + FLANK3  # begins in frame 1 with no start codon
    orf = _the_orf(inv.find_orfs(headless, min_aa=4), "AAAKGS")
    assert orf.first_met == -1
    info = inv.infer_cds(headless, orf, "MAAAKGS")
    assert info["five_prime"] == "TRUNCATED_AT_TRANSCRIPT_END"
    assert info["cds"].startswith("GCT")  # start not fabricated


def test_complete_cds_is_anchored_on_the_published_n_terminus():
    orf = _the_orf(inv.find_orfs(TRANSCRIPT, min_aa=5), "MAAAKGS")
    info = inv.infer_cds(TRANSCRIPT, orf, "MAAAKGS")
    assert info["five_prime"] == "COMPLETE_START_MATCHES_PUBLISHED_N_TERMINUS"
    assert info["three_prime"] == "COMPLETE_STOP_AFTER_PUBLISHED_C_TERMINUS"
    assert (info["start"], info["end"], info["cds"]) == (6, 6 + len(CDS) - 1, CDS)


def test_internal_stop_splits_the_reading_frame():
    mutated = "ATG" + "GCT" + "TAA" + "GCT" + "AAA" + "GGC" + "TCT" + "TAA"
    orfs = inv.find_orfs(mutated, min_aa=1)
    proteins = {o.protein for o in orfs if o.strand == "+" and o.frame == 1}
    assert {"MA", "AKGS"} <= proteins  # never one 7-residue ORF
    assert all("*" not in o.protein for o in orfs)


def test_locate_protein_reports_strand_frame_flanks_and_stop():
    for seq, strand in ((TRANSCRIPT, "+"), (reverse_complement(TRANSCRIPT), "-")):
        (hit,) = inv.locate_protein(seq, "MAAAKGS")
        assert hit["strand"] == strand and hit["stop_present"] is True and hit["start_codon"] == "ATG"
        assert hit["cds"] == CDS
        assert (hit["upstream_nt"], hit["downstream_nt"]) == (5, 5)


# ------------------------------------------------------------------ HSP coverage
def test_interval_union_merges_overlapping_and_abutting_intervals():
    assert inv.merge_intervals([(1, 5), (6, 9), (20, 30), (25, 40)]) == [(1, 9), (20, 40)]
    assert inv.union_length([(1, 10), (5, 15)]) == 15


def test_overlapping_hsps_are_not_double_counted():
    (row,) = inv.summarize_hsps([hsp(qstart=1, qend=100), hsp(qstart=51, qend=150, sstart=51, send=150)])
    assert row["query_union_covered"] == 150 and row["query_union_coverage_pct"] == 75.0 and row["n_hsps"] == 2


def test_opposite_strand_hsps_are_never_merged():
    rows = inv.summarize_hsps([hsp(strand="plus", qstart=1, qend=100), hsp(strand="minus", qstart=1, qend=100)])
    assert sorted(r["strand"] for r in rows) == ["minus", "plus"]
    assert all(r["query_union_covered"] == 100 for r in rows)  # 100 each, not 200 and not merged


def test_multiple_candidates_for_one_query_are_all_preserved():
    hsps = [hsp(subject="A.1", bitscore=900), hsp(subject="B.1", bitscore=800), hsp(subject="C.1", bitscore=10)]
    rows = inv.summarize_hsps(hsps)
    assert [r["subject"] for r in rows] == ["A.1", "B.1", "C.1"]


def test_summaries_are_independent_of_input_order():
    hsps = [hsp(subject="A.1", qstart=1, qend=50), hsp(subject="B.1"), hsp(subject="A.1", qstart=40, qend=90)]
    assert inv.summarize_hsps(hsps) == inv.summarize_hsps(list(reversed(hsps)))


def test_hsp_tables_parse_both_blastn_and_tblastn_layouts():
    cells = ["q", "gb|X.1|", "99.0", "100", "200", "1000", "1", "100", "900", "801", "minus", "1e-30", "180", "1", "0", "0", "50", "100"]
    (n,) = inv.parse_hsp_table("\t".join(cells))
    assert n.strand == "minus" and n.subject_interval == (801, 900) and n.sframe is None
    t_cells = cells[:11] + ["-2"] + cells[11:]
    (t,) = inv.parse_hsp_table("\t".join(t_cells), inv.TBLASTN_OUTFMT_FIELDS)
    assert t.sframe == -2
    with pytest.raises(ValueError):
        inv.parse_hsp_table("a\tb")


def test_btop_parse():
    columns = inv.parse_btop("2AG1T-")
    assert [c[0] for c in columns] == ["=", "=", "X", "=", "I"]
    assert columns[2] == ("X", "A", "G") and columns[4] == ("I", "T", "-")
    assert [c[0] for c in inv.parse_btop("-A3")] == ["D", "=", "=", "="]


def _plus_hsp(btop, qend):
    return inv.Hsp("q", "s", 90.0, qend, 100, 100, 1, qend, 1, qend, "plus", 1.0, 20.0, 1, 1, 1, 1.0, btop)


def test_btop_substitutions_without_gaps_is_unchanged():
    assert inv.btop_substitutions(_plus_hsp("3AG2", 6)) == {4: ("A", "G")}
    assert inv.btop_substitutions(_plus_hsp("1TG1CA2", 6)) == {2: ("T", "G"), 4: ("C", "A")}


def test_btop_substitutions_counts_a_query_base_against_a_subject_gap_as_a_query_position():
    # BTOP "2A-1AG": = = | A vs gap in the SUBJECT | = | A/G  -> the mismatch is query position 5, not 4
    hsp = inv.Hsp("q", "s", 90.0, 6, 100, 100, 1, 5, 1, 5, "plus", 1.0, 20.0, 1, 1, 1, 1.0, "2A-1AG")
    assert [c[0] for c in inv.parse_btop(hsp.btop)] == ["=", "=", "I", "=", "X"]  # "I": the query position advances
    assert inv.btop_substitutions(hsp) == {5: ("A", "G")}
    query = "ACGTA"  # position 5 is the query A of the A/G mismatch
    assert query[5 - 1] == "A"


def test_btop_substitutions_does_not_advance_over_a_subject_base_against_a_query_gap():
    # query ACTAC aligned to subject ACGTGC:  AC-TAC / ACGTGC  -> BTOP "2-G1AG1"; the mismatch is query position 4
    query = "ACTAC"
    hsp = _plus_hsp("2-G1AG1", len(query))
    assert [c[0] for c in inv.parse_btop(hsp.btop)] == ["=", "=", "D", "=", "X", "="]  # "D": the query position stays
    found = inv.btop_substitutions(hsp)
    assert found == {4: ("A", "G")} and query[4 - 1] == "A"


def test_btop_substitutions_after_gaps_in_both_directions_and_before_them():
    # BTOP "1TG1A-1-C1AG" = | T/G | = | A vs subject gap (I) | = | subject-only C (D) | = | A/G
    # query positions 1,2,3,4,5,(none),6,7 -> mismatches at 2 and 7
    query = "ATCAGCA"
    hsp = _plus_hsp("1TG1A-1-C1AG", len(query))
    found = inv.btop_substitutions(hsp)
    assert found == {2: ("T", "G"), 7: ("A", "G")}
    assert all(query[position - 1] == base for position, (base, _) in found.items())
    # two query-gap columns in a row must not move the query at all
    assert inv.btop_substitutions(_plus_hsp("2-G-T1AG", 4)) == {4: ("A", "G")}
    # query gaps before an I: only the I advances
    assert inv.btop_substitutions(_plus_hsp("1-GA-1AG", 4)) == {4: ("A", "G")}


# ------------------------------------------------------------------ alignment
def test_alignment_is_deterministic_and_handles_all_modes():
    a, b = "ACGTACGTTTGACCA", "GGACGTACGATTGACCATT"
    first, second = inv.align(a, b, "semiglobal"), inv.align(a, b, "semiglobal")
    assert first == second
    assert first.a_aligned.replace("-", "") == a and first.b_aligned.replace("-", "") == b
    glob = inv.align("ACGTACGT", "ACGTCGT", "global")
    assert glob.a_aligned == "ACGTACGT" and glob.b_aligned.count("-") == 1
    local = inv.align("MKVLAAG", "XXMKVLAAGXX", "local", matrix=inv.BLOSUM62)
    assert (local.a_start, local.a_end, local.b_start, local.b_end) == (0, 7, 2, 9)


def test_protein_metrics_report_identity_similarity_and_coverage():
    m = inv.protein_metrics("MKVLAAGHHH", "MKVLTAGHHH")
    assert (m["identities"], m["alignment_length"], m["gaps"]) == (9, 10, 0)
    assert m["reference_coverage"] == 100.0 and m["candidate_coverage"] == 100.0
    truncated = inv.protein_metrics("MKVLAAGHHH", "AAGHHH")
    assert truncated["candidate_coverage"] == 100.0 and truncated["reference_coverage"] == 60.0


# ------------------------------------------------------------------ nucleotide difference classification
def _events(candidate: str, strand: str = "+"):
    ref = TRANSCRIPT
    cds = inv.CdsSpec(6, 5 + len(CDS), "+")
    cand = candidate
    if strand == "-":
        ref, cand = reverse_complement(ref), reverse_complement(cand)
        cds = inv.CdsSpec(6, 5 + len(CDS), "-")
    alignment = inv.align(ref, cand, "global")
    return inv.call_differences(alignment, ref, cand, cds, "cand", "ref")


def _mutate(position1: int, base: str) -> str:
    return TRANSCRIPT[: position1 - 1] + base + TRANSCRIPT[position1:]


@pytest.mark.parametrize("strand", ["+", "-"])
def test_substitution_effects_in_cds_are_classified_on_either_strand(strand):
    # codon 2 = GCT (Ala) occupies transcript positions 9-11
    (syn,) = _events(_mutate(11, "C"), strand)
    assert (syn["effect"], syn["codon_change"], syn["amino_acid_change"]) == ("synonymous", "GCT>GCC", "A2A")
    (mis,) = _events(_mutate(10, "A"), strand)
    assert (mis["effect"], mis["amino_acid_change"]) == ("missense", "A2D")
    # codon 5 = AAA (Lys) occupies 18-20; AAA>TAA is a stop gain
    (non,) = _events(_mutate(18, "T"), strand)
    assert (non["effect"], non["amino_acid_change"]) == ("nonsense", "K5*")
    (flank,) = _events(_mutate(2, "T"), strand)
    assert flank["effect"] == "flanking" and flank["within_inferred_CDS"] is False


def test_iupac_code_in_cds_is_ambiguous_and_reports_possible_residues():
    (event,) = _events(_mutate(19, "R"))  # AAA -> ARA : K or R
    assert event["effect"] == "ambiguous" and event["amino_acid_change"] == "K5[K/R]"
    assert event["ambiguity_includes_reference_base"] is True
    (silent,) = _events(_mutate(11, "Y"))  # GCT -> GCY : Ala either way
    assert silent["effect"] == "ambiguous" and silent["amino_acid_change"].endswith("(ambiguity)")


def test_indels_are_frameshift_or_in_frame_and_flanking_indels_are_flanking():
    deleted = TRANSCRIPT[:15] + TRANSCRIPT[16:]  # one base removed inside the CDS
    (fs,) = [e for e in _events(deleted) if e["event_type"] == "deletion"]
    assert fs["effect"] == "frameshift" and fs["within_inferred_CDS"] is True
    inserted = TRANSCRIPT[:14] + "TTT" + TRANSCRIPT[14:]
    (ins,) = [e for e in _events(inserted) if e["event_type"] == "insertion"]
    assert ins["effect"] == "insertion" and ins["length"] == 3
    in_flank = TRANSCRIPT[:2] + "T" + TRANSCRIPT[2:]
    (fl,) = [e for e in _events(in_flank) if e["event_type"] == "insertion"]
    assert fl["effect"] == "flanking"


def test_terminal_overhangs_are_flagged_and_never_called_utr():
    cand = "TTTTTTTT" + TRANSCRIPT + "AAAA"
    alignment = inv.align(TRANSCRIPT, cand, "semiglobal")
    events = inv.call_differences(alignment, TRANSCRIPT, cand, inv.CdsSpec(6, 5 + len(CDS), "+"), "cand", "ref")
    assert {e["event_type"] for e in events} == {"insertion"}
    assert all(e["terminal"] and e["effect"] == "flanking" for e in events)
    assert "UTR" not in " ".join(str(v) for e in events for v in e.values())


# ------------------------------------------------------------------ parsers, FASTA, consistency
def test_fasta_round_trip_keeps_identifiers_and_sequences_in_sync_with_tables():
    records = [("GITV01000001.1 TSA: x", "ACGT" * 30), ("GITV01000002.1 TSA: y", "TTGA")]
    parsed = inv.read_fasta_text(inv.format_fasta(records))
    assert [p[0] for p in parsed] == ["GITV01000001.1", "GITV01000002.1"]
    assert [p[2] for p in parsed] == [r[1] for r in records]
    from zeaguard.nb01_identity import canonical_tsa_accession

    assert canonical_tsa_accession("gb|GITV01000001.1|") in {p[0] for p in parsed}
    with pytest.raises(ValueError):
        inv.read_fasta_text(">a\nAC\n>a\nGT\n")


def test_s1_parser_rejoins_wrapped_transcript_headers():
    text = (
        "=====PAGE 5=====\n>X_i1.p1 (Dmai-dsRNase-9) \nMKV\nLAA \n>X_i1 len=10 path=[1:0-5\n2:6-9] (Dmai-dsRNase-9) \nACGT\nACGTAC \n"
    )
    parsed = inv.parse_s1_text(text)
    assert parsed["Dmai-dsRNase-9"]["protein"] == ("X_i1.p1", "MKVLAA")
    assert parsed["Dmai-dsRNase-9"]["transcript"] == ("X_i1", "ACGTACGTAC")


def test_domtblout_parser_and_feature_row_coverages():
    line = ("seq1 - 400 Endonuclease_NS PF01223.30 223 1e-40 120.0 0.1 1 1 1e-41 2e-41 116.0 0.0 5 220 145 450 140 455 0.95 desc")
    (domain,) = inv.parse_domtblout("# comment\n" + line + "\n")
    assert (domain["ali_from"], domain["ali_to"], domain["i_evalue"]) == (145, 450, 2e-41)
    (row,) = inv.feature_rows([domain], {"seq1": "M" * 400}, {"tool": "hmmsearch"}, (23.0, 23.0))
    assert row["domain_start"] == 145 and row["meets_GA"] is True
    assert row["profile_coverage"] == round(100 * 216 / 223, 2) and row["sequence_coverage"] == round(100 * 306 / 400, 2)
    (absent,) = inv.feature_rows([], {"seq2": "M"}, {"tool": "hmmsearch"}, (23.0, 23.0))
    assert absent["meets_GA"] is False and absent["domain_start"] == ""
    assert inv.hmm_ga_threshold("NAME x\nGA    23 23;\nTC 1 1;\n") == (23.0, 23.0)


# ------------------------------------------------------------------ read support
def test_site_anchors_refuse_to_span_other_variable_sites():
    backbone = "ACGT" * 30
    with pytest.raises(ValueError):
        inv.build_sites(backbone, [30, 40])
    with pytest.raises(ValueError):
        inv.build_sites(backbone, [5])


def test_allele_counting_uses_both_strands_and_exact_anchors():
    backbone = "".join("ACGT"[(i * 7 + i // 3) % 4] for i in range(120))
    (site,) = inv.build_sites(backbone, [60])
    base = backbone[59]
    alt = "A" if base != "A" else "C"
    forward = backbone[40:59] + alt + backbone[60:80]
    reverse = reverse_complement(backbone[40:59] + base + backbone[60:80])
    broken = backbone[40:45] + ("A" if backbone[45] != "A" else "C") + backbone[46:59] + alt + backbone[60:80]
    counts = inv.count_site_alleles([forward, forward, reverse, broken], [site])[60]
    assert counts[alt] == 2 and counts[base] == 1 and sum(counts.values()) == 3  # the read with a damaged anchor is ignored
    assert len(inv.anchor_patterns([site])) <= 4


def test_site_support_classification_follows_the_preregistered_rule():
    assert inv.classify_site_support({"A": 40, "G": 30}, ["A", "G"])["verdict"] == "BOTH_ALLELES_SUPPORTED"
    assert inv.classify_site_support({"A": 70, "G": 2}, ["A", "G"])["verdict"] == "ONLY_A_SUPPORTED"
    assert inv.classify_site_support({"A": 10, "G": 5}, ["A", "G"])["verdict"] == "NOT_ASSESSABLE_LOW_DEPTH"
    assert inv.classify_site_support({"T": 50}, ["A", "G"])["verdict"] == "NEITHER_EXPECTED_ALLELE_SUPPORTED"


def test_end_anchoring_turns_terminal_mismatches_into_overhangs():
    ref = "AAGGA" + "ACGTACGTTGCATGCATTGACC" + "GG"
    cand = "TTTTTTTTTTTTTTTT" + "TTTTT" + "ACGTACGTTGCATGCATTGACC" + "CCCCCCCC"
    raw_alignment = inv.align(ref, cand, "semiglobal")
    anchored = inv.anchor_alignment_ends(raw_alignment)
    assert anchored.a_aligned.replace("-", "") == ref and anchored.b_aligned.replace("-", "") == cand
    events = inv.call_differences(anchored, ref, cand, None, "cand", "ref")
    assert all(e["event_type"] != "substitution" for e in events)  # no end artefacts reported as substitutions
    assert all(e["terminal"] for e in events)


# ------------------------------------------------------------------ decision rules (ADR 0004 scenarios)
PUB_CDS, PUB_PROT = "ATGAAATAA", "MK"


def _candidate(acc, cds="ATGAAATAA", prot="MK", complete=True, competing=True, events=(), identities=2):
    cds_sha, prot_sha = inv.sha256_text(cds), inv.sha256_text(prot)
    row = {"candidate": acc, "competing_for_dsRNase-2": competing, "cds_sha256": cds_sha, "protein_sha256": prot_sha,
           "five_prime_status": "COMPLETE_X" if complete else "TRUNCATED_AT_TRANSCRIPT_END", "three_prime_status": "COMPLETE_Y",
           "five_prime_flank_nt": 10, "three_prime_flank_nt": 20, "best_reference_by_protein": "dsRNase-2" if competing else "dsRNase-1",
           "dsRNase-2_identity_over_reference_length_pct": 100.0 if competing else 30.0,
           "best_identity_over_reference_length_pct": 100.0}
    evs = [{"pair": f"dsRNase-2.published_cDNA_vs_{acc}", "within_inferred_CDS": True, "reference_position": 5, "event_type": "substitution",
            "amino_acid_change": "", **e} for e in events]
    prot_row = {"candidate": acc, "reference": "dsRNase-2.protein", "protein_identity": 100.0 * identities / 2, "identities": identities,
                "reference_coverage": 100.0}
    return row, evs, prot_row


def _decide(candidates, read_support=None):
    rows, events, prots = zip(*candidates)
    refs = {"dsRNase-2": {"cds": PUB_CDS, "protein": PUB_PROT}}
    comparison = {"classification": list(rows), "events": [e for evs in events for e in evs], "protein_rows": list(prots)}
    return inv.build_decision(refs, {}, comparison, [], read_support, {})


def test_scenario_a_same_cds_and_protein_leaves_only_the_accession_ambiguous():
    decision = _decide([_candidate("A.1"), _candidate("B.1")])
    assert decision["published_reference_correspondence"]["status"] == "TIED"
    assert decision["published_reference_correspondence"]["best_matching_accessions"] == ["A.1", "B.1"]
    assert [decision[k]["status"] for k in ("accession_resolution", "cds_resolution", "protein_resolution")] == ["AMBIGUOUS", "RESOLVED", "RESOLVED"]
    assert decision["overall"] == "AMBIGUOUS_AT_ACCESSION_LEVEL"
    assert decision["cds_resolution"]["sequence_sha256"] == inv.sha256_text(PUB_CDS)


def test_scenario_b_synonymous_variant_gives_unique_correspondence_but_ambiguous_accession_and_cds():
    syn = [{"effect": "synonymous"}, {"effect": "ambiguous", "amino_acid_change": "K2K(ambiguity)"}]
    decision = _decide([_candidate("A.1"), _candidate("B.1", cds="ATGAAGTAA", events=syn)])
    assert decision["published_reference_correspondence"]["status"] == "UNIQUE"
    assert decision["published_reference_correspondence"]["best_matching_accessions"] == ["A.1"]
    assert decision["accession_resolution"]["status"] == "AMBIGUOUS" and decision["accession_resolution"]["selected_accession"] is None
    assert decision["cds_resolution"]["status"] == "AMBIGUOUS"
    assert decision["protein_resolution"]["status"] == "RESOLVED"
    assert decision["overall"] == "AMBIGUOUS_AT_ACCESSION_AND_CDS_LEVELS"


def test_ambiguous_residue_keeps_protein_open_until_reads_exclude_the_alternative():
    amb = [{"effect": "ambiguous", "amino_acid_change": "K2[K/R]", "reference_position": 7}]
    candidates = [_candidate("A.1"), _candidate("B.1", events=amb, identities=1)]
    assert _decide(candidates)["protein_resolution"]["status"] == "AMBIGUOUS"
    published_only = {"sites_by_event": {"B.1:7": {"verdict": "ONLY_C_SUPPORTED"}}, "published_allele_only": {"B.1:7": True}, "rows": [], "runs": []}
    assert _decide(candidates, published_only)["protein_resolution"]["status"] == "RESOLVED"
    both = {"sites_by_event": {"B.1:7": {"verdict": "BOTH_ALLELES_SUPPORTED"}}, "published_allele_only": {"B.1:7": False}, "rows": [], "runs": []}
    assert _decide(candidates, both)["protein_resolution"]["status"] == "AMBIGUOUS"


def test_single_complete_competitor_resolves_the_accession():
    decision = _decide([_candidate("A.1"), _candidate("P.1", competing=False)])
    assert decision["accession_resolution"]["status"] == "RESOLVED" and decision["accession_resolution"]["selected_accession"] == "A.1"
    assert "P.1" in decision["accession_resolution"]["evidence"][1]["statement"]  # exclusion is documented, not silent


def test_variant_level_difference_is_not_an_exclusion_criterion():
    missense = [{"effect": "missense", "amino_acid_change": "K2R"}]
    decision = _decide([_candidate("A.1"), _candidate("B.1", prot="MR", cds="ATGAGATAA", events=missense, identities=1)])
    assert decision["accession_resolution"]["status"] == "AMBIGUOUS"  # B.1 stays a candidate
    assert decision["protein_resolution"]["status"] == "AMBIGUOUS"
    assert decision["published_reference_correspondence"]["best_matching_accessions"] == ["A.1"]


def test_no_complete_candidate_is_unresolved_and_not_forced():
    decision = _decide([_candidate("A.1", complete=False, cds="ATGAAA", events=[{"effect": "deletion"}], identities=1)])
    assert decision["accession_resolution"]["status"] == "UNRESOLVED"
    assert decision["cds_resolution"]["status"] == "UNRESOLVED" and decision["protein_resolution"]["status"] == "UNRESOLVED"
    assert decision["published_reference_correspondence"]["status"] == "NO_CONFIDENT_MATCH"


def test_overall_label_keeps_every_level_visible():
    assert inv.overall_label("RESOLVED", "RESOLVED", "RESOLVED") == "RESOLVED_AT_ALL_LEVELS"
    assert inv.overall_label("AMBIGUOUS", "RESOLVED", "RESOLVED") == "AMBIGUOUS_AT_ACCESSION_LEVEL"
    assert inv.overall_label("AMBIGUOUS", "AMBIGUOUS", "UNRESOLVED") == "AMBIGUOUS_AT_ACCESSION_AND_CDS_LEVELS_UNRESOLVED_AT_PROTEIN_LEVEL"


def test_signal_peptide_is_never_interpreted_for_an_n_terminally_truncated_protein():
    predictions = inv.parse_deepsig_gff("p1\tDeepSig\tSignal peptide\t1\t21\t1.0\t.\t.\te\np1\tDeepSig\tChain\t22\t474\t.\t.\t.\te\np2\tDeepSig\tChain\t1\t300\t.\t.\t.\te\n")
    rows = inv.signal_rows(predictions, {"p1": "M", "p2": "M", "p3": "M"}, {"p2": "TRUNCATED_AT_TRANSCRIPT_END", "p3": "COMPLETE_X"}, {"tool": "DeepSig"})
    calls = {r["sequence_id"]: r["prediction"] for r in rows}
    assert calls == {"p1": "SIGNAL_PEPTIDE_PREDICTED", "p2": "NOT_ASSESSABLE_DUE_TO_N_TERMINAL_INCOMPLETENESS", "p3": "NOT_ASSESSED_NO_TOOL_OUTPUT"}
    assert rows[0]["cleavage_site"] == "after residue 21" and rows[0]["score"] == 1.0


def test_divergent_cds_are_reported_as_not_alignable_instead_of_a_misleading_identity():
    same = inv.nucleotide_identity(CDS + "AAACCC" * 20, CDS + "AAACCC" * 20)
    assert same["nt_identity_pct"] == 100.0
    divergent = inv.nucleotide_identity("A" * 60 + "C" * 60, "G" * 60 + "T" * 60)
    assert divergent["nt_identity_pct"] == "NOT_ALIGNABLE_AT_NUCLEOTIDE_LEVEL"
    assert divergent["nt_identical_pairs"] == 0


# ------------------------------------------------------------------ P0 checkpoint: IUPAC translation behaviour
def test_iupac_codon_whose_expansions_all_encode_the_same_amino_acid():
    report = inv.ambiguous_codon_report("CTN", "L")  # CTA/CTC/CTG/CTT are all Leu
    assert report["amino_acids"] == ["L"] and len(report["expansions"]) == 4
    assert report["case_A_all_same_amino_acid"] is True and report["case_B_multiple_amino_acids"] is False
    assert report["case_C_published_in_possible_set"] is True
    assert inv.translate("CTN") == "L"  # resolved because it is unambiguous at amino-acid level


def test_iupac_codon_with_several_possible_amino_acids_is_reported_as_a_set_and_translates_to_x():
    report = inv.ambiguous_codon_report("ARA", "R")  # AAA = K, AGA = R
    assert report["amino_acids"] == ["K", "R"] and report["expansion_translations"] == "AAA=K;AGA=R"
    assert report["case_A_all_same_amino_acid"] is False and report["case_B_multiple_amino_acids"] is True
    assert inv.translate("ARA") == "X"  # never silently resolved to one residue


def test_published_amino_acid_among_the_possible_translations_is_compatible():
    assert inv.ambiguous_codon_report("ARA", "R")["case_C_published_in_possible_set"] is True
    assert inv.ambiguous_codon_report("ARA", "K")["case_C_published_in_possible_set"] is True
    report = inv.ambiguous_codon_report("RAY", "N")  # AAC/AAT = N, GAC/GAT = D
    assert report["amino_acids"] == ["D", "N"] and report["case_C_published_in_possible_set"] is True


def test_published_amino_acid_incompatible_with_every_expansion_is_flagged():
    report = inv.ambiguous_codon_report("ARA", "L")
    assert report["case_C_published_in_possible_set"] is False
    assert inv.ambiguous_codon_report("CTN", "K")["case_C_published_in_possible_set"] is False
    assert inv.ambiguous_codon_report("TRA", "W")["amino_acids"] == ["*"]  # TAA / TGA, both stops


def test_ambiguous_codon_reports_are_deterministic_and_validate_input():
    assert inv.ambiguous_codon_report("NNN", "M") == inv.ambiguous_codon_report("NNN", "M")
    assert len(inv.ambiguous_codon_report("NNN", "M")["expansions"]) == 64
    assert inv.ambiguous_codon_report("ATG", "M")["ambiguous"] is False
    with pytest.raises(ValueError):
        inv.ambiguous_codon_report("AT", "M")
    with pytest.raises(ValueError):
        inv.ambiguous_codon_report("AXG", "M")


# ------------------------------------------------------------------ P0 checkpoint: orientation, differences, paralogy, decision
def _ref_for(transcript: str, protein: str):
    (placement,) = inv.locate_protein(transcript, protein)
    return {"transcript": transcript, "protein": protein, "cds": placement["cds"], "placement": placement, "placements": [placement],
            "transcript_id": "T1", "protein_id": "T1.p1"}


def test_s1_orientation_rows_demonstrate_the_reverse_complement_relation_on_both_strands():
    plus = _ref_for(TRANSCRIPT, "MAAAKGS")
    minus = _ref_for(reverse_complement(TRANSCRIPT), "MAAAKGS")
    rows = {r["reference"]: r for r in inv.orientation_rows({"plus": plus, "minus": minus})}
    assert rows["plus"]["reverse_complement_required"] is False and rows["minus"]["reverse_complement_required"] is True
    for row in rows.values():
        assert row["translation_equals_published_protein"] is True and row["internal_stop_codons"] == 0
        assert row["S1_slice_(reverse_complemented_if_minus)_equals_CDS"] is True
        assert row["reverse_complement_of_whole_transcript_slice_equals_CDS"] is True
        assert row["CDS_length_nt_with_stop"] == len(CDS) and row["CDS_start_in_coding_orientation"] == 6
    assert (rows["plus"]["CDS_start_in_S1_transcript"], rows["plus"]["CDS_end_in_S1_transcript"]) == (6, 5 + len(CDS))
    assert (rows["minus"]["CDS_start_in_S1_transcript"], rows["minus"]["CDS_end_in_S1_transcript"]) == (6, 5 + len(CDS))


def _pair_events(candidate: str, strand: str = "+"):
    ref = TRANSCRIPT if strand == "+" else reverse_complement(TRANSCRIPT)
    cand = candidate if strand == "+" else reverse_complement(candidate)
    spec = inv.CdsSpec(6, 5 + len(CDS), strand)
    events = inv.call_differences(inv.align(ref, cand, "global"), ref, cand, spec, "cand", "ref")
    for e in events:
        e["pair"] = "ref_vs_cand"
    cds_cand = (candidate[5 : 5 + len(CDS)])
    return events, spec, cds_cand


@pytest.mark.parametrize("strand", ["+", "-"])
def test_difference_rows_keep_defined_substitutions_apart_from_iupac_uncertainty(strand):
    mutated = list(TRANSCRIPT)
    mutated[10] = "C"   # GCT -> GCC (codon 2, defined, synonymous)
    mutated[18] = "R"   # AAA -> ARA (codon 5, IUPAC: K or R)
    events, spec, cds_cand = _pair_events("".join(mutated), strand)
    rows, codons = inv.nucleotide_difference_rows(events, "ref_vs_cand", "ref", spec, CDS, "cand", spec, cds_cand, "MAAAKGS")
    by_class = {r["position_class"]: r for r in rows}
    defined, iupac = by_class["DEFINED_SUBSTITUTION"], by_class["IUPAC_AMBIGUITY"]
    assert (defined["effect"], defined["possible_amino_acid_consequence"], defined["cds_coord"]) == ("synonymous", "A2A", 6)
    assert iupac["effect"] == "ambiguous" and iupac["possible_amino_acid_consequence"] == "K5 -> {K/R}"
    assert iupac["other_record_base_in_expansion"] is True and iupac["codon_index"] == 5
    (codon,) = codons
    assert codon["case_B_multiple_amino_acids_possible"] is True and codon["case_C_published_aa_among_possible"] is True
    assert codon["amino_acids_possible"] == "K/R" and codon["valid_codon_expansions_and_translations"] == "AAA=K;AGA=R"
    relation = inv.effective_relation(rows, codons)
    assert relation["defined_cds_substitutions"] == 1 and relation["iupac_positions_in_cds"] == 1
    assert (relation["cds_relation"], relation["protein_relation"]) == ("DIFFERENT", "COMPATIBLE_WITH_UNRESOLVED_RESIDUE")


def test_effective_relations_cover_identical_compatible_and_different_cases():
    cds = lambda cls, effect="ambiguous", compatible=True, event="substitution": {  # noqa: E731
        "within_inferred_CDS": True, "position_class": cls, "event_type": event, "effect": effect, "other_record_base_in_expansion": compatible}
    codon = lambda published_in, multi=True: {"case_C_published_aa_among_possible": published_in, "case_B_multiple_amino_acids_possible": multi}  # noqa: E731
    assert inv.effective_relation([], [])["cds_relation"] == "IDENTICAL"
    only_iupac = inv.effective_relation([cds("IUPAC_AMBIGUITY")], [codon(True)])
    assert (only_iupac["cds_relation"], only_iupac["protein_relation"]) == ("COMPATIBLE_BUT_INCOMPLETELY_DETERMINED", "COMPATIBLE_WITH_UNRESOLVED_RESIDUE")
    missense = inv.effective_relation([cds("DEFINED_SUBSTITUTION", "missense", "")], [])
    assert (missense["cds_relation"], missense["protein_relation"]) == ("DIFFERENT", "DIFFERENT")
    excluded = inv.effective_relation([cds("IUPAC_AMBIGUITY")], [codon(False)])
    assert excluded["protein_relation"] == "DIFFERENT"  # the published residue is not among the possible ones


def test_discriminating_positions_score_candidates_against_the_three_paralogs():
    ds2 = "MKTAYIAKQRQISFVKSHFSRQ"
    ds1 = ds2[:4] + "W" + ds2[5:9] + "D" + ds2[10:]    # differs at 5 and 10
    ds3 = ds2[:9] + "E" + ds2[10:14] + "P" + ds2[15:]  # differs at 10 and 15
    as_ds2 = inv.discriminating_positions(ds2, ds1, ds3, ds2)
    assert as_ds2["n_discriminating_positions"] == 1 and as_ds2["matches_dsRNase-2"] == 1  # only position 10 differs from both
    as_ds1 = inv.discriminating_positions(ds2, ds1, ds3, ds1)
    assert as_ds1["matches_dsRNase-1"] == 1 and as_ds1["matches_dsRNase-2"] == 0
    with_x = inv.discriminating_positions(ds2, ds1, ds3, ds2[:9] + "X" + ds2[10:])
    assert with_x["undetermined_X"] == 1  # an ambiguous residue is never counted as a match or a mismatch


def test_preliminary_decision_follows_the_strict_sequence_policy():
    classification = [{"candidate": "A.1", "competing_for_dsRNase-2": "True"}, {"candidate": "B.1", "competing_for_dsRNase-2": "True"}]
    correspondence = {"status": "UNIQUE", "best_matching_accessions": ["A.1"]}
    orient = [{"translation_equals_published_protein": True}]
    same = {"cds_relation": "IDENTICAL", "protein_relation": "IDENTICAL"}
    # same effective CDS and protein in both records: only the accession stays open (early-stop scenario A)
    early_stop = inv.build_preliminary_p0_decision(classification, correspondence, {"A.1": same, "B.1": same}, same, orient, [])
    assert (early_stop["accession_resolution"], early_stop["cds_resolution"], early_stop["protein_resolution"]) == ("AMBIGUOUS", "RESOLVED", "RESOLVED")
    assert early_stop["overall"] == "AMBIGUOUS_AT_ACCESSION_LEVEL"
    # a residue with several possible amino acids keeps the protein AMBIGUOUS even though the published residue is one of them
    unresolved = {"cds_relation": "DIFFERENT", "protein_relation": "COMPATIBLE_WITH_UNRESOLVED_RESIDUE"}
    strict = inv.build_preliminary_p0_decision(classification, correspondence, {"A.1": same, "B.1": unresolved}, unresolved, orient, [])
    assert (strict["cds_resolution"], strict["protein_resolution"]) == ("AMBIGUOUS", "AMBIGUOUS")
    assert strict["overall"] == "AMBIGUOUS_AT_ACCESSION_AND_CDS_AND_PROTEIN_LEVELS"
    distinction = strict["protein_distinction"]
    assert distinction["published_protein_compatible"] == {"A.1": True, "B.1": True} and distinction["protein_sequence_resolved"] is False
    assert strict["published_reference_correspondence"]["status"] == "UNIQUE"
    # a defined amino-acid difference is neither compatible nor resolved
    different_protein = {"cds_relation": "DIFFERENT", "protein_relation": "DIFFERENT"}
    open_protein = inv.build_preliminary_p0_decision(classification, correspondence, {"A.1": same, "B.1": different_protein}, different_protein, orient, [])
    assert open_protein["protein_resolution"] == "AMBIGUOUS"
    assert open_protein["protein_distinction"]["published_protein_compatible"]["B.1"] is False
    # a single competitor resolves the accession, but the protein is resolved only if it has no unresolved residue
    single = inv.build_preliminary_p0_decision(classification[:1], correspondence, {"A.1": same}, same, orient, [])
    assert (single["accession_resolution"], single["protein_resolution"]) == ("RESOLVED", "RESOLVED")
    single_open = inv.build_preliminary_p0_decision(classification[:1], correspondence, {"A.1": unresolved}, unresolved, orient, [])
    assert single_open["protein_resolution"] == "AMBIGUOUS"


def test_variable_site_context_places_residues_in_signal_peptide_domain_or_mature_region():
    features = [
        {"sequence_id": "P", "feature": "PF01223", "domain_start": "145", "domain_end": "450"},
        {"sequence_id": "P", "feature": "signal_peptide", "prediction": "SIGNAL_PEPTIDE_PREDICTED", "cleavage_site": "after residue 21"},
    ]
    diff = [{"within_inferred_CDS": True, "event_type": "substitution", "codon_index": idx, "cds_coord": 3 * idx, "position_class": "IUPAC_AMBIGUITY",
             "effect": "ambiguous", "possible_amino_acid_consequence": "x"} for idx in (3, 117, 272)]
    diff.append({"within_inferred_CDS": False, "event_type": "substitution", "codon_index": "", "cds_coord": "", "position_class": "x", "effect": "flanking",
                 "possible_amino_acid_consequence": ""})
    rows = {r["residue"]: r["region"] for r in inv.variable_site_context_rows(diff, features, "P")}
    assert rows == {3: "signal peptide", 117: "mature protein outside the PF01223 domain", 272: "PF01223 domain"}
