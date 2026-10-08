from __future__ import annotations

from pathlib import Path
import random
import shutil
import subprocess

import pytest
import yaml

from zeaguard import nb01_identity
from zeaguard import nb02_criteria as crit
from zeaguard import nb02_specificity as spec
from zeaguard.nb01_dsrnase_investigation import Hsp

ROOT = Path(__file__).resolve().parents[1]
HAS_BLAST = shutil.which("blastn") is not None and shutil.which("makeblastdb") is not None
needs_blast = pytest.mark.skipif(not HAS_BLAST, reason="BLAST+ is not installed")


@pytest.fixture(scope="module")
def registry():
    return yaml.safe_load((ROOT / crit.REGISTRY_PATH).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def policy(registry):
    return spec.load_policy(registry)


def fp(btop, q_lo, q_hi, cls="DSRNASE1", subject="S1", hsp_id=None, strand="plus"):
    return spec.footprint_from_btop(hsp_id or f"{subject}:{q_lo}-{q_hi}", subject, cls, strand, q_lo, q_hi, btop)


# ------------------------------------------------------------------ BTOP -> footprint (gaps, runs)
def test_btop_columns_reads_matches_mismatches_and_both_kinds_of_gap():
    assert spec.btop_columns("2AG1-C1A-1") == [("=", "="), ("=", "="), ("A", "G"), ("=", "="), ("-", "C"), ("=", "="), ("A", "-"), ("=", "=")]


def test_footprint_runs_break_at_mismatches_and_at_subject_only_bases():
    f = fp("5AG3-A4", 101, 113)  # 5 equal, mismatch (106), 3 equal (107-109), subject-only base, 4 equal (110-113)
    assert f.runs == ((101, 105), (107, 109), (110, 113))
    assert f.ident_cum[-1] == 12 and f.ins_cum[-1] == 1


def test_footprint_counts_a_query_base_against_a_subject_gap_as_aligned_but_not_identical():
    f = fp("3A-2", 1, 6)
    assert f.runs == ((1, 3), (5, 6))
    clip = spec.clip_footprint(f, 1, 6)
    assert clip.aligned_nt == 6 and clip.identity == pytest.approx(5 / 6)


def test_footprint_rejects_btop_that_disagrees_with_the_query_span():
    with pytest.raises(spec.NB02SpecificityError):
        fp("10", 1, 12)


def test_clipping_is_inclusive_and_drops_gap_columns_at_the_borders():
    f = fp("5AG3-A4", 101, 113)
    inside = spec.clip_footprint(f, 103, 111)
    assert (inside.lo, inside.hi, inside.aligned_nt, inside.longest_exact) == (103, 111, 9, 3)
    assert inside.identity == pytest.approx(8 / 10)  # 9 query positions + the subject-only base between 109 and 110
    assert spec.clip_footprint(f, 105, 109).identity == pytest.approx(4 / 5)  # the gap after 109 is dropped
    right = spec.clip_footprint(f, 110, 113)
    assert right.identity == 1.0 and right.longest_exact == 4  # the gap before 110 is dropped
    assert spec.clip_footprint(f, 114, 200) is None and spec.clip_footprint(f, 1, 100) is None
    one = spec.clip_footprint(f, 113, 500)
    assert (one.lo, one.hi, one.aligned_nt, one.longest_exact) == (113, 113, 1, 1)


# ------------------------------------------------------------------ 1-2: only the part inside the candidate counts
def test_hsp_mostly_outside_the_candidate_contributes_only_the_inside_part():
    long_hsp = fp("300", 101, 400)
    evidence = spec.unit_evidence([long_hsp], 390, 500)
    assert (evidence["longest_exact_match_clipped"], evidence["covered_nt_clipped"]) == (11, 11)
    assert evidence["best_local_identity_clipped"] == 1.0 and evidence["best_identity_aligned_nt_clipped"] == 11
    assert evidence["exact_21mer_count_clipped"] == 0 and evidence["exact_19mer_count_clipped"] == 0
    assert spec.unit_evidence([long_hsp], 401, 700)["n_hsps_clipped"] == 0  # zero nt after clipping: nothing


def test_changing_the_part_of_the_hsp_outside_the_candidate_changes_neither_vector_nor_dominance():
    plain = fp("300", 101, 400)  # all identical
    noisy = fp("100AG250", 50, 400)  # a mismatch far outside, longer alignment on the left
    a, b = spec.unit_evidence([plain], 390, 500), spec.unit_evidence([noisy], 390, 500)
    assert spec.vector(a) == spec.vector(b) == (11, 11, 1.0)
    ev_a = crit.SpecificityEvidence("a", 111, frozenset(), spec.vector(a), (0, 0, 0.0), (0, 0, 0.0))
    ev_b = crit.SpecificityEvidence("b", 111, frozenset(), spec.vector(b), (0, 0, 0.0), (0, 0, 0.0))
    assert crit.decisive_signature(ev_a) == crit.decisive_signature(ev_b)
    assert crit.compare_specificity(ev_a, ev_b) == "TIE"
    # the same HSP evaluated on a window that DOES contain the mismatch is different evidence
    assert spec.unit_evidence([noisy], 100, 200)["best_local_identity_clipped"] < 1.0


# ------------------------------------------------------------------ 3-4: units aggregate redundant records and never pool
def test_redundant_dsrnase1_records_do_not_duplicate_covered_nt():
    one = [fp("80", 201, 280, subject="GITV01001583.1")]
    three = one + [fp("80", 201, 280, subject="GITV01002042.1"), fp("80", 201, 280, subject="TRINITY_DN13786_c0_g1_i8")]
    a, b = spec.unit_evidence(one, 150, 350), spec.unit_evidence(three, 150, 350)
    assert a["covered_nt_clipped"] == b["covered_nt_clipped"] == 80
    assert a["longest_exact_match_clipped"] == b["longest_exact_match_clipped"] == 80
    assert (a["n_hsps_clipped"], b["n_hsps_clipped"]) == (1, 3)  # a descriptor, not an axis
    assert b["hit_records"] == "GITV01001583.1,GITV01002042.1,TRINITY_DN13786_c0_g1_i8"
    partial = three + [fp("40", 261, 300, subject="GITV01003945.1")]  # overlaps 261-280, extends to 300
    assert spec.unit_evidence(partial, 150, 350)["covered_nt_clipped"] == 100  # union 201-300, not 80 + 80 + 80 + 40


def test_dsrnase1_and_dsrnase3_coverages_are_never_added():
    by_class = {"DSRNASE1": [fp("80", 201, 280)], "DSRNASE3": [fp("80", 201, 280, cls="DSRNASE3", subject="S3")]}
    evidence = spec.candidate_evidence(by_class, 150, 350)
    assert evidence["DSRNASE1"]["covered_nt_clipped"] == 80 and evidence["DSRNASE3"]["covered_nt_clipped"] == 80
    assert set(evidence) == {"DSRNASE1", "DSRNASE3"}  # no pooled PARALOG entry exists
    candidate = crit.SpecificityEvidence("x", 201, frozenset(), spec.vector(evidence["DSRNASE1"]), spec.vector(evidence["DSRNASE3"]), (0, 0, 0.0))
    assert candidate.paralog == (80, 80, 1.0, 80, 80, 1.0)  # two vectors side by side, not a 160 nt PARALOG vector


def test_trade_off_between_dsrnase1_and_dsrnase3_is_incomparable():
    clean_1 = spec.candidate_evidence({"DSRNASE1": [], "DSRNASE3": [fp("60", 201, 260, cls="DSRNASE3", subject="S3")]}, 150, 350)
    clean_3 = spec.candidate_evidence({"DSRNASE1": [fp("60", 201, 260)], "DSRNASE3": []}, 150, 350)

    def evidence(candidate, units):
        return crit.SpecificityEvidence(candidate, 201, frozenset(), spec.vector(units["DSRNASE1"]), spec.vector(units["DSRNASE3"]), (0, 0, 0.0))

    a, b = evidence("a", clean_1), evidence("b", clean_3)
    assert crit.compare_specificity(a, b) == "TIE" == crit.compare_specificity(b, a)


def test_best_identity_is_reported_with_the_aligned_nt_that_gave_it():
    short_perfect = fp("12", 220, 231, subject="A")
    long_imperfect = fp("50AG49", 201, 300, subject="B")
    evidence = spec.unit_evidence([short_perfect, long_imperfect], 150, 350)
    assert evidence["best_local_identity_clipped"] == 1.0 and evidence["best_identity_aligned_nt_clipped"] == 12
    equal = spec.unit_evidence([fp("30", 201, 230, subject="A"), fp("50", 201, 250, subject="B")], 150, 350)
    assert (equal["best_local_identity_clipped"], equal["best_identity_aligned_nt_clipped"]) == (1.0, 50)  # tie: more aligned nt


# ------------------------------------------------------------------ 6-7: OTHER_TRANSCRIPT, E-values and k-mer counts decide nothing
def _evidence_from(by_class):
    units = spec.candidate_evidence(by_class, 150, 350)
    return crit.SpecificityEvidence(
        "c", 201, frozenset({200}), spec.vector(units["DSRNASE1"]), spec.vector(units["DSRNASE3"]), spec.vector(units["BICC"]),
        tuple({"subject": f.subject} for f in by_class.get("OTHER_TRANSCRIPT", [])))


def test_other_transcript_hits_do_not_change_signature_or_pareto_position():
    base = {"DSRNASE1": [fp("30", 201, 230)], "DSRNASE3": [], "BICC": [], "OTHER_TRANSCRIPT": []}
    noisy = {**base, "OTHER_TRANSCRIPT": [fp("120", 160 + i, 279 + i, cls="OTHER_TRANSCRIPT", subject=f"X{i}") for i in range(40)]}
    a, b = _evidence_from(base), _evidence_from(noisy)
    assert crit.decisive_signature(a) == crit.decisive_signature(b)
    rival = _evidence_from({"DSRNASE1": [fp("80", 201, 280)], "DSRNASE3": [], "BICC": []})
    assert crit.compare_specificity(a, rival) == crit.compare_specificity(b, rival) == "A_BETTER"
    assert crit.compare_specificity(a, b) == "TIE"


def test_evalue_and_kmer_counts_are_not_part_of_the_vector_or_the_order():
    evidence = spec.unit_evidence([fp("40", 201, 240)], 150, 350)
    assert spec.vector(evidence) == (40, 40, 1.0)
    tampered = {**evidence, "exact_19mer_count_clipped": 999, "exact_21mer_count_clipped": 999, "n_hsps_clipped": 7, "evalue": 1e-200}
    assert spec.vector(tampered) == spec.vector(evidence)
    assert evidence["exact_21mer_count_clipped"] == 20 and evidence["exact_19mer_count_clipped"] == 22  # still reported as descriptors


# ------------------------------------------------------------------ classification by the frozen biological units
def test_classification_uses_the_frozen_units_and_keeps_bicc_tsa_record_out_of_other_transcript(policy):
    assert policy.classify("GITV01000968.1") == "BICC" == policy.classify("TRINITY_DN24799_c0_g1_i7")
    assert {policy.classify(a) for a in ("GITV01001583.1", "GITV01002042.1", "GITV01003945.1", "TRINITY_DN13786_c0_g1_i8")} == {"DSRNASE1"}
    assert policy.classify("TRINITY_DN5008_c0_g1_i24") == "DSRNASE3"
    assert {policy.classify(a) for a in ("GITV01008430.1", "GITV01012450.1", "TRINITY_DN22752_c0_g2_i1")} == {spec.KNOWN}
    assert policy.classify("GITV01000001.1") == spec.OTHER
    assert policy.unit_names == ("DSRNASE1", "DSRNASE3", "BICC")


def test_search_settings_and_shuffle_seeds_come_from_the_registry(policy):
    assert spec.blastn_arguments(policy.search) == [
        "-task", "blastn", "-dust", "no", "-word_size", "11", "-evalue", "10", "-strand", "both",
        "-max_target_seqs", "100000", "-num_threads", "1"]
    assert policy.shuffle_seeds == (1, 2, 3, 4, 5)


def test_shuffled_control_preserves_composition_is_reproducible_and_differs_by_seed():
    sequence = "ACGT" * 50 + "GGGCCC" * 10
    first = spec.shuffled_sequence(sequence, 1)
    assert sorted(first) == sorted(sequence) and first == spec.shuffled_sequence(sequence, 1)
    assert first != sequence and first != spec.shuffled_sequence(sequence, 2)


def test_cp3_output_columns_never_belong_to_cells_ranking_pareto_shortlist_or_recommendation(policy):
    columns = list(spec.PROVENANCE_COLUMNS) + list(spec._window_columns(policy.unit_names)) + list(spec.UNIT_METRICS)
    assert not [c for c in columns if any(f in c for f in spec.FORBIDDEN_COLUMN_FRAGMENTS)]


# ------------------------------------------------------------------ persisted evidence can be reloaded without BLAST
def test_footprints_reload_from_the_provenance_table(tmp_path, policy):
    hsp = Hsp("operational_cds", "GITV01001583.1", 97.0, 13, 1425, 3000, 101, 113, 50, 62, "plus", 1e-4, 30.0, 1, 1, 0, 1.0, "5AG3-A4")
    rows = spec.provenance_rows([hsp], policy)
    assert rows[0]["class"] == "DSRNASE1" and rows[0]["longest_exact_match_full"] == 5
    spec.write_tsv(tmp_path / "p.tsv", rows, spec.PROVENANCE_COLUMNS)
    reloaded = spec.load_footprints(tmp_path / "p.tsv")
    assert reloaded["DSRNASE1"][0] == spec.footprint(hsp, "DSRNASE1")


# ------------------------------------------------------------------ independent k-mer self-check
def test_exact_kmer_scan_and_selfcheck_agree_on_a_synthetic_case(policy):
    rng = random.Random(3)
    cds = "".join(rng.choice("ACGT") for _ in range(300))
    shared = cds[100:130]
    records = [("GITV01001583.1", "TTTT" + shared + "AAAA"), ("GITV09999999.1", "GGGG" + nb01_identity.reverse_complement(cds[10:40]) + "CCCC")]
    scan = spec.exact_kmer_scan(cds, records, policy)
    assert scan[21]["DSRNASE1"] == set(range(101, 111)) and scan[19]["DSRNASE1"] == set(range(101, 113))
    assert scan[21][spec.OTHER] == set(range(11, 21))  # found on the reverse strand, reported on the forward query
    blast_like = {"DSRNASE1": [fp("30", 101, 130)], spec.OTHER: [fp("30", 11, 40, cls=spec.OTHER, subject="GITV09999999.1")]}
    report = spec.kmer_selfcheck(blast_like, scan)
    assert all(v["only_in_direct_scan"] == 0 and v["only_in_blast_btop"] == 0 for v in report.values())


# ------------------------------------------------------------------ 8: strand and gaps in BTOP, with the real BLAST
@needs_blast
def test_btop_footprints_are_correct_for_plus_and_minus_strand_hits_with_gaps(tmp_path):
    rng = random.Random(11)
    query = "".join(rng.choice("ACGT") for _ in range(500))
    # gap positions must not sit in a homopolymer, or BLAST may left/right-align the gap and the expectation would be ambiguous
    deleted = next(p for p in range(195, 240) if query[p - 1] != query[p - 2] and query[p - 1] != query[p])
    segment = list(query[50:350])  # query positions 51..350
    segment[150 - 51] = "A" if query[149] != "A" else "C"  # mismatch at 150
    extra = next(b for b in "ACGT" if b not in (query[249], query[250]))
    segment.insert(250 - 51 + 1, extra)  # one subject-only base after query position 250
    del segment[deleted - 51]  # query base `deleted` has no subject base
    subject = "".join(segment)
    plus = "TTTTTCCCCC" + subject + "CCCCCTTTTT"
    minus = nb01_identity.reverse_complement(plus)
    fasta = tmp_path / "s.fa"
    fasta.write_text(f">plus_subject\n{plus}\n>minus_subject\n{minus}\n", encoding="ascii")
    (tmp_path / "q.fa").write_text(f">q\n{query}\n", encoding="ascii")
    subprocess.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-out", str(tmp_path / "db")], check=True, capture_output=True)
    process = subprocess.run(
        ["blastn", "-query", str(tmp_path / "q.fa"), "-db", str(tmp_path / "db"), "-task", "blastn", "-dust", "no", "-word_size", "11",
         "-evalue", "10", "-strand", "both", "-outfmt", "6 " + " ".join(spec.BLAST_OUTFMT_FIELDS)],
        check=True, capture_output=True, text=True)
    hsps = spec.parse_hsp_table(process.stdout)
    by_subject = {h.subject: h for h in hsps if h.length > 100}
    assert set(by_subject) == {"plus_subject", "minus_subject"}
    assert by_subject["plus_subject"].strand == "plus" and by_subject["minus_subject"].strand == "minus"
    footprints = {name: spec.footprint(h, "OTHER_TRANSCRIPT") for name, h in by_subject.items()}
    plus_fp, minus_fp = footprints["plus_subject"], footprints["minus_subject"]
    for f in (plus_fp, minus_fp):
        assert (f.q_lo, f.q_hi) == (51, 350)
        identical = {f.q_lo + i for i in range(f.q_hi - f.q_lo + 1) if f.ident_cum[i + 1] - f.ident_cum[i]}
        assert set(range(51, 351)) - identical == {150, deleted}  # the mismatch and the query base opposite the subject gap
        assert f.ins_cum[-1] == 1 and f.ins_cum[250 - 51 + 1] - f.ins_cum[250 - 51] == 1  # the subject-only base follows query base 250
        assert f.runs == ((51, 149), (151, deleted - 1), (deleted + 1, 250), (251, 350))
    assert plus_fp.runs == minus_fp.runs and plus_fp.ident_cum == minus_fp.ident_cum and plus_fp.ins_cum == minus_fp.ins_cum
    # clipping rebuilt from BTOP is identical in both orientations, including a window that cuts through the gaps
    for start, end in ((51, 350), (190, 260), (200, 251), (240, 251), (250, 250)):
        a, b = spec.clip_footprint(plus_fp, start, end), spec.clip_footprint(minus_fp, start, end)
        assert (a.identity, a.longest_exact, a.aligned_nt, a.lo, a.hi, a.runs) == (b.identity, b.longest_exact, b.aligned_nt, b.lo, b.hi, b.runs)
