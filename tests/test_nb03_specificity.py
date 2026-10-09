from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib
import json
import random
import shutil

import pytest

from zeaguard import nb01_identity, nb02_specificity as old, nb03_criteria as criteria, nb03_design as design
from zeaguard import nb03_specificity as spec
from zeaguard.nb01_dsrnase_investigation import Hsp, parse_hsp_table

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/nb03_clipping_non_equivalence"
HAS_REAL = (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").exists() and shutil.which("blastn") is not None


def make_hsp(btop, qstart=1, query_length=30, subject="S", unit="BICC_LIKE", identifier="h1", strand="plus"):
    columns = old.btop_columns(btop)
    query_bases = sum(q != "-" for q, _ in columns)
    subject_bases = sum(s != "-" for _, s in columns)
    identical = sum(q == s == "=" for q, s in columns)
    seq = ["A"] * query_length
    qpos = qstart - 1
    for q, _ in columns:
        if q != "-":
            if q != "=":
                seq[qpos] = q
            qpos += 1
    query = spec.Query("Q", "".join(seq), "DESIGN_SPACE", 1, query_length)
    sstart, send = (100, 100 + subject_bases - 1) if strand == "plus" else (100 + subject_bases - 1, 100)
    raw = Hsp("Q", subject, round(100 * identical / len(columns), 3), len(columns), query_length, 1000,
              qstart, qstart + query_bases - 1, sstart, send, strand, 0.01, 30, 0, 0,
              sum(q == "-" or s == "-" for q, s in columns), 50, btop)
    return spec.native_hsp(raw, query, unit, identifier), query


def test_native_btop_reconstructs_mismatches_and_gaps_in_both_directions():
    h, _ = make_hsp("2AG1-C1A-1")
    assert h.raw.qend == 7  # I (A-) advances query; D (-C) does not.
    assert h.exact_runs == ((1, 2), (4, 4), (5, 5), (7, 7))
    assert h.identical_columns == 5 and h.raw.length == 8
    assert float(h.identity) == 5 / 8
    evidence = spec.unit_evidence([h])
    assert evidence["covered_nt"] == 7 and evidence["aligned_nt_for_best_identity"] == 8
    assert evidence["longest_exact_match"] == 2


@pytest.mark.parametrize("strand", ["plus", "minus"])
def test_subject_orientation_preserves_native_query_metrics(strand):
    h, _ = make_hsp("5AG3-A4", qstart=10, strand=strand)
    assert h.raw.qstart == 10 and h.raw.qend == 22
    assert h.exact_runs == ((10, 14), (16, 18), (19, 22))
    assert spec.evidence_vector(spec.unit_evidence([h])) == (5, 13, 12 / 14)


def test_native_parsing_rejects_full_cds_query_length_and_malformed_spans():
    h, query = make_hsp("20")
    with pytest.raises(spec.NB03SpecificityError):
        spec.native_hsp(replace(h.raw, qlen=2337), query, h.unit, "bad")
    with pytest.raises(spec.NB03SpecificityError):
        spec.native_hsp(replace(h.raw, qend=21), query, h.unit, "bad")
    with pytest.raises(spec.NB03SpecificityError):
        spec.native_hsp(replace(h.raw, btop="20!"), query, h.unit, "bad")
    with pytest.raises(spec.NB03SpecificityError):
        spec.native_hsp(replace(h.raw, pident=50), query, h.unit, "bad")


def test_multiple_hsps_and_redundant_records_use_query_union_and_maxima():
    a, _ = make_hsp("20", qstart=1, identifier="a", subject="S1")
    b, _ = make_hsp("20", qstart=11, identifier="b", subject="S2")
    redundant, _ = make_hsp("20", qstart=1, identifier="c", subject="S3")
    evidence = spec.unit_evidence([a, b, redundant])
    assert spec.evidence_vector(evidence) == (20, 30, 1.0)
    assert evidence["n_hsps"] == evidence["n_subject_records"] == 3
    assert evidence["subject_accessions"] == "S1,S2,S3"


def test_best_identity_keeps_alignment_column_length_and_deterministic_ties():
    short, _ = make_hsp("12", identifier="short")
    long, _ = make_hsp("20AG5", identifier="long")
    assert spec.unit_evidence([long, short])["aligned_nt_for_best_identity"] == 12
    perfect, _ = make_hsp("25", identifier="perfect")
    assert spec.unit_evidence([perfect, short])["aligned_nt_for_best_identity"] == 25
    assert spec.unit_evidence([short, perfect]) == spec.unit_evidence([perfect, short])


def test_identity_tie_with_different_lengths_takes_the_longest_alignment_in_any_order():
    short, _ = make_hsp("4AG5", identifier="a")  # 9/10 identical columns
    long, _ = make_hsp("4AG4AG10", identifier="b")  # 18/20 identical columns: the same exact fraction
    assert short.identity == long.identity
    for order in ([short, long], [long, short]):
        evidence = spec.unit_evidence(order)
        assert evidence["best_local_identity"] == 0.9 and evidence["aligned_nt_for_best_identity"] == 20
        assert evidence["identical_nt_for_best_identity"] == 18


def test_registry_documents_the_descriptive_deterministic_tie_break():
    unit_aggregation = criteria.load_registry(ROOT)["policy"]["unit_aggregation"]
    rule = unit_aggregation["aligned_nt_for_best_identity"]
    assert rule["role"] == "DESCRIPTIVE_ONLY" and rule["effect_on_best_local_identity"] == "none"
    assert rule["enters_pareto_or_decisive_signature"] is False and rule["expresses_biological_preference"] is False
    assert [step.split(" ")[0] for step in rule["tie_break_order"]] == ["highest", "longest", "lowest"]
    assert "aligned_nt_for_best_identity" not in spec.AXES


def test_distinct_units_or_queries_cannot_be_pooled():
    a, _ = make_hsp("20")
    b = replace(a, unit="DSRNASE2")
    with pytest.raises(spec.NB03SpecificityError):
        spec.unit_evidence([a, b])
    with pytest.raises(spec.NB03SpecificityError):
        spec.unit_evidence([a, replace(a, raw=replace(a.raw, query="different"))])


def test_no_hit_produces_zero_native_vector():
    assert spec.evidence_vector(spec.unit_evidence([])) == (0, 0, 0.0)
    assert spec.unit_evidence([])["aligned_nt_for_best_identity"] == 0


def test_policy_preserves_frozen_memberships_and_descriptive_units():
    policy = spec.load_policy(criteria.load_registry(ROOT))
    assert policy.classify("GITV01000968.1") == policy.classify("TRINITY_DN24799_c0_g1_i7") == "KNOWN_BICC_COMPATIBLE"
    assert policy.classify("GITV01002238.1") == "BICC_LIKE" and policy.relationships["BICC_LIKE"] == "UNRESOLVED"
    assert policy.classify("GITV01008430.1") == policy.classify("GITV01012450.1") == "DSRNASE2"
    assert policy.units["DSRNASE2"][0] == "CO_TARGET_DECISIONAL_INTERPRETABILITY"
    assert policy.units["DSRNASE1"][0] == policy.units["DSRNASE3"][0] == "DESCRIPTIVE_ONLY"
    assert policy.classify("GITV09999999.1") == "OTHER_TRANSCRIPT"
    assert policy.units["OTHER_TRANSCRIPT"][0] == "DESCRIPTIVE_PLUS_MANUAL_REVIEW"
    assert old.blastn_arguments(policy.search) == ["-task", "blastn", "-dust", "no", "-word_size", "11",
                                                "-evalue", "10", "-strand", "both", "-max_target_seqs", "100000", "-num_threads", "1"]


def test_native_counterexample_and_basis_guard_remain_canonical():
    query_record = next(nb01_identity.parse_fasta(FIXTURE / "window_query.fasta"))
    query = spec.Query(query_record.identifier, query_record.sequence, "DESIGN_SPACE", 501, 900)
    native = parse_hsp_table((FIXTURE / "window_query_blast.outfmt6.tsv").read_text())
    evidence = spec.unit_evidence([spec.native_hsp(h, query, "BICC_LIKE", str(i)) for i, h in enumerate(native)])
    full = parse_hsp_table((FIXTURE / "full_query_blast.outfmt6.tsv").read_text())
    diagnostic = old.unit_evidence([old.footprint(h, "SYNTHETIC") for h in full], 501, 900)
    assert evidence["covered_nt"] != diagnostic["covered_nt_clipped"]
    with pytest.raises(spec.NB03SpecificityError):
        spec.native_hsp(full[0], query, "BICC_LIKE", "wrong_basis")


def test_only_canonical_units_supply_adapter_vectors_and_descriptors_are_ignored():
    query = spec.Query("synthetic", "A" * 400, "DESIGN_SPACE", 1, 400)
    row = spec.query_row(query, {})
    row.update(other_transcript_covered_nt=400, dsrnase1_covered_nt=400, exact_21mer_match_count=999)
    evidence = spec.as_decisional_evidence(row, [100])
    assert evidence.bicc_like == evidence.dsrnase2 == (0, 0, 0)
    assert criteria.decisive_signature(evidence) == (1, (0, 0, 0), (0, 0, 0))
    with pytest.raises(criteria.NB03EvidenceBasisError):
        spec.as_decisional_evidence({**row, "specificity_evidence_basis": criteria.DIAGNOSTIC_EVIDENCE_BASIS}, [])


def test_shuffles_have_candidate_native_length_composition_ids_and_seeds(tmp_path):
    query = spec.Query("BC-L300-0001-0300", "ACGT" * 75, "DESIGN_SPACE", 1, 300)
    shuffles = spec.shuffled_queries([query], [1, 2, 3, 4, 5])
    assert len(shuffles) == 5 and {q.seed for q in shuffles} == {1, 2, 3, 4, 5}
    assert all(q.length == 300 and sorted(q.sequence) == sorted(query.sequence) for q in shuffles)
    assert all(q.membership == "SHUFFLED_CONTROL" and q.source_window_id == query.identifier for q in shuffles)
    assert shuffles == spec.shuffled_queries([query], [1, 2, 3, 4, 5])
    spec.write_queries(tmp_path / "one.fasta", shuffles)
    spec.write_queries(tmp_path / "two.fasta", shuffles)
    assert (tmp_path / "one.fasta").read_bytes() == (tmp_path / "two.fasta").read_bytes()


@pytest.mark.parametrize("membership", ["REFERENCE_SET", "SHUFFLED_CONTROL"])
def test_reference_and_control_queries_cannot_enter_candidate_signature(membership):
    query = spec.Query("synthetic", "A" * 400, membership, 1, 400)
    row = spec.query_row(query, {})
    assert row["query_role"] in {"REFERENCE_ONLY", "DESCRIPTIVE_ONLY"}
    with pytest.raises(criteria.NB03EvidenceBasisError):
        spec.as_decisional_evidence(row, [])


def test_cp3_columns_have_no_selection_fields_or_canonical_clipped_suffix():
    for columns in (spec.HSP_COLUMNS, spec.WINDOW_COLUMNS, spec.CONTROL_COLUMNS, spec.OTHER_COLUMNS, spec.KMER_COLUMNS):
        assert not [c for c in columns if any(fragment in c for fragment in old.FORBIDDEN_COLUMN_FRAGMENTS)]
        assert not [c for c in columns if "_clipped" in c]
    assert "aligned_nt_for_best_identity" not in spec.AXES


@pytest.fixture(scope="module")
def real_reference():
    if not HAS_REAL:
        pytest.skip("needs TSA and BLAST+")
    return design.verified_reference(ROOT)


def test_all_queries_match_cp2_ids_hashes_and_benchmark_is_separate(real_reference):
    queries, benchmark, _ = spec.load_queries(ROOT, real_reference)
    assert len(queries) == 7779
    assert {length: sum(q.length == length for q in queries) for length in (300, 373, 400, 500)} == {300: 2038, 373: 1965, 400: 1938, 500: 1838}
    equivalent = next(q for q in queries if q.identifier == "BC-L373-0215-0587")
    assert benchmark.identifier == "BC-BENCH-0215-0587" and benchmark.membership == "REFERENCE_SET"
    assert equivalent.membership == "DESIGN_SPACE" and equivalent.sequence == benchmark.sequence
    groups = spec.batches(queries, benchmark, (1, 2, 3, 4, 5))
    assert len(groups) == 10 and len(dict(groups)["benchmark"]) == 1
    assert sum(len(g) for name, g in groups if name.startswith("controls_")) == 38900
    assert all(q.identifier.startswith("SHUF-") for name, group in groups if name.startswith("controls_") for q in group)


def test_independent_exact_scan_and_interval_counts_agree_with_brute_candidate_substrings(tmp_path):
    policy = spec.load_policy(criteria.load_registry(ROOT))
    rng = random.Random(13)
    cds = "".join(rng.choice("ACGT") for _ in range(500))
    shared = cds[100:135]
    subject = "AAAA" + nb01_identity.reverse_complement(shared) + "TTTT"
    (tmp_path / "blastdb").mkdir()
    (tmp_path / "blastdb/combined.fasta").write_text(f">background\n{subject}\n>GITV01000968.1\n{cds}\n")
    query = spec.Query("Q", cds[50:350], "DESIGN_SPACE", 51, 350)
    benchmark = spec.Query("B", cds[100:400], "REFERENCE_SET", 101, 400)
    summary = spec.exact_kmer_output(ROOT, tmp_path, cds, [query], benchmark, policy)
    expected = {k: sum(query.sequence[s:s + k] in subject or nb01_identity.reverse_complement(query.sequence[s:s + k]) in subject
                       for s in range(query.length - k + 1)) for k in (19, 21)}
    assert summary["300"]["OTHER_TRANSCRIPT"]["19"]["max"] == expected[19]
    assert summary["300"]["OTHER_TRANSCRIPT"]["21"]["max"] == expected[21]


def test_real_native_batch_is_deterministic_and_self_positive(real_reference, tmp_path):
    policy = spec.load_policy(real_reference["registry"])
    queries, _, _ = spec.load_queries(ROOT, real_reference)
    selected = [next(q for q in queries if q.identifier == name) for name in ("BC-L400-0001-0400", "BC-L400-1938-2337")]
    log = spec.ExecutionLog(tmp_path)
    database = spec.build_database(ROOT, tmp_path, policy, log)
    fasta = tmp_path / "small_native.fasta"
    spec.write_queries(fasta, selected)
    command = ["blastn", "-query", str(fasta), "-db", database["path"], *old.blastn_arguments(policy.search),
               "-outfmt", "6 " + " ".join(spec.BLAST_OUTFMT_FIELDS)]
    first, second = log.run(command), log.run(command)
    assert first == second
    raw = parse_hsp_table(first)
    assert raw and {h.query for h in raw} == {q.identifier for q in selected}
    lookup = {q.identifier: q for q in selected}
    by_query = {q.identifier: [] for q in selected}
    for i, h in enumerate(raw):
        native = spec.native_hsp(h, lookup[h.query], policy.classify(h.subject), str(i))
        if h.subject == "GITV01000968.1":
            by_query[h.query].append(native)
    for q in selected:
        assert spec.evidence_vector(spec.unit_evidence(by_query[q.identifier])) == (400, 400, 1.0)
