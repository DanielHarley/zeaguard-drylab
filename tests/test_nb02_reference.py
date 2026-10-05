from __future__ import annotations

import json
from pathlib import Path

import pytest

from zeaguard import nb02_reference as ref
from zeaguard.nb01_identity import reverse_complement

ROOT = Path(__file__).resolve().parents[1]
HAS_TSA = (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").is_file()
needs_tsa = pytest.mark.skipif(not HAS_TSA, reason="the hash-pinned TSA is not materialised locally")

# Literal values recorded by NB01 (decision.json / candidate_classification.tsv) and re-derived in CP1.
OPERATIONAL_CDS_SHA = "bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7"
SIBLING_CDS_SHA = "8c18687410248fb6036020cc50fc7577d23c7c44b9d0f30cc0677b95b28960f8"
BENCHMARK_SHA = "97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179"
VARIANT_POSITIONS = [9, 30, 219, 312, 350, 816, 1272]


# ------------------------------------------------------------------ pure functions
def test_extract_cds_minus_strand_returns_coding_orientation():
    cds = "ATGGCCAAATAA"
    record = "TTTT" + reverse_complement(cds) + "GG"
    assert ref.extract_cds(record, "-", 5, 16) == cds
    assert ref.extract_cds("CC" + cds + "AA", "+", 3, 14) == cds


def test_extract_cds_rejects_bad_strand_and_bounds():
    with pytest.raises(ref.NB02ContractError):
        ref.extract_cds("ACGT", "*", 1, 4)
    with pytest.raises(ref.NB02ContractError):
        ref.extract_cds("ACGT", "+", 3, 9)
    with pytest.raises(ref.NB02ContractError):
        ref.extract_cds("ACGT", "+", 0, 2)


def test_derive_variants_defined_and_iupac_in_coding_orientation():
    operational = "ATGGTCAGAAAATAA"  # M V R K *
    sibling = "ATGGTTARAAAATAA"  # defined C->T at 6 (V->V); R (A/G) at 8 inside codon AGA -> ARA (K/R)
    rows = ref.derive_variants(operational, sibling)
    assert [(r["cds_pos"], r["class"]) for r in rows] == [(6, "DEFINED_SUBSTITUTION"), (8, "IUPAC_AMBIGUITY")]
    defined, iupac = rows
    assert (defined["codon_index"], defined["codon_position"]) == (2, 3)
    assert (defined["operational_amino_acid"], defined["sibling_possible_amino_acids"]) == ("V", "V")
    assert (iupac["codon_index"], iupac["codon_position"]) == (3, 2)
    assert (iupac["operational_amino_acid"], iupac["sibling_possible_amino_acids"]) == ("R", "K/R")


def test_derive_variants_refuses_broken_premises():
    with pytest.raises(ref.NB02ContractError):
        ref.derive_variants("ATGAAA", "ATGAAAA")  # different lengths (indel)
    with pytest.raises(ref.NB02ContractError):
        ref.derive_variants("ATGNAA", "ATGAAA")  # operational reference must be defined
    with pytest.raises(ref.NB02ContractError):
        ref.derive_variants("ATGCAA", "ATGRAA")  # R = A/G excludes the operational C: not mere uncertainty
    assert ref.derive_variants("ATGAAA", "ATGAAA") == []


def test_find_primer_span_forward_and_reverse_complement_exact():
    cds = "GGGG" + "ACGTACGTAC" + "TTTTTT" + "CCATGGCCAA" + "GGGG"
    forward, reverse = "ACGTACGTAC", reverse_complement("CCATGGCCAA")
    assert ref.find_primer_span(cds, forward, reverse) == (5, 30)


def test_find_primer_span_rejects_absent_repeated_or_misordered_sites():
    forward, reverse = "ACGTACGTAC", reverse_complement("CCATGGCCAA")
    with pytest.raises(ref.NB02ContractError):
        ref.find_primer_span("GGGGGGGG", forward, reverse)
    with pytest.raises(ref.NB02ContractError):
        ref.find_primer_span("TT" + forward + "A" + forward + "CCATGGCCAA", forward, reverse)
    with pytest.raises(ref.NB02ContractError):
        ref.find_primer_span("CCATGGCCAA" + "TT" + forward, forward, reverse)


def test_strict_record_flags_hash_and_length_divergence():
    cds = "ATG" + "GCT" * 3 + "TAA"
    record = {"accession": "X1", "strand": "-", "cds_tx_start": 3, "cds_tx_end": 3 + len(cds) - 1,
              "record_length": 20, "cds_length": len(cds), "cds_sha256": "0" * 64,
              "protein_length": 4, "protein_sha256": "0" * 64}
    problems: list[str] = []
    ref._strict_record({"X1": "AA" + reverse_complement(cds) + "CCCCC"}, record, problems)
    joined = " ".join(problems)
    assert "record_length" in joined and "cds_sha256" in joined and "protein_sha256" in joined


def _benchmark_for(cds: str, forward: str, reverse: str, **overrides):
    start, end = ref.find_primer_span(cds, forward, reverse)
    body = cds[start - 1 : end]
    from zeaguard.nb01_dsrnase_investigation import sha256_text

    benchmark = {
        "primers": {"forward": {"sequence": forward}, "reverse": {"sequence": reverse}, "t7_tail_5to3": "CGACTCACTATAGGG"},
        "amplicon_lengths_bp": {"without_t7_tails": len(body), "with_t7_tails": len(body) + 30},
        "interval": {"cds_start": start, "cds_end": end, "length_nt": len(body), "sequence_sha256": sha256_text(body)},
        "verification": {"benchmark_sequence_verification": ref.SEQUENCE_VERIFICATION,
                         "experimental_protocol_verification": "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"},
        "protocols": [{"name": "INJECTION_PRECONDITIONING", "verification": "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"},
                      {"name": "ORAL_COFEEDING", "verification": "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"}],
    }
    benchmark.update(overrides)
    return benchmark


def test_verify_benchmark_accepts_consistent_pin_and_reports_sibling_sites():
    forward, reverse = "ACGTACGTAC", "TTGGCCATGG"
    cds = "GG" + forward + "AAAA" + reverse_complement(reverse) + "GG"
    sibling = cds.replace("ACGTACGTAC", "ACRTACGTAC")  # IUPAC symbol inside the forward site
    problems: list[str] = []
    result = ref._verify_benchmark(_benchmark_for(cds, forward, reverse), cds, sibling, [5], problems)
    assert problems == []
    assert result["variants_inside"] == [5]
    assert result["sibling_primer_sites"] == {"forward": "NO_EXACT_MATCH", "reverse": "EXACT_MATCH"}


def test_verify_benchmark_flags_wrong_interval_amplicon_and_merged_protocols():
    forward, reverse = "ACGTACGTAC", "TTGGCCATGG"
    cds = "GG" + forward + "AAAA" + reverse_complement(reverse) + "GG"
    benchmark = _benchmark_for(cds, forward, reverse)
    benchmark["interval"]["cds_end"] += 1
    benchmark["amplicon_lengths_bp"]["with_t7_tails"] += 1
    benchmark["protocols"] = [{"name": "INJECTION_PRECONDITIONING"}]
    problems: list[str] = []
    ref._verify_benchmark(benchmark, cds, cds, [], problems)
    joined = " ".join(problems)
    assert "cds_end" in joined and "amplicon" in joined and "protocols" in joined


def test_crosscheck_converts_orientation_and_reports_match_mismatch_absent(tmp_path):
    variants = [
        {"cds_pos": 5, "operational_base": "C", "sibling_symbol": "Y", "class": "IUPAC_AMBIGUITY"},
        {"cds_pos": 9, "operational_base": "C", "sibling_symbol": "T", "class": "DEFINED_SUBSTITUTION"},
    ]
    assert ref.crosscheck_nb01_handoff(tmp_path, variants)["status"] == "ABSENT"
    path = tmp_path / ref.NB01_HANDOFF_PATH
    path.parent.mkdir(parents=True)
    header = "cds_coord\tclass\tbase_GITV01008430.1\tbase_GITV01012450.1\n"
    # transcript-strand bases are the complement of the coding-strand ones: C->G, Y->R, T->A
    rows = "5\tIUPAC_AMBIGUITY\tG\tR\n9\tDEFINED_SUBSTITUTION\tG\tA\n\tTERMINAL_INDEL_FLANKING\tAAGGA\t-\n"
    path.write_text(header + rows, encoding="utf-8")
    assert ref.crosscheck_nb01_handoff(tmp_path, variants)["status"] == "MATCH"
    path.write_text(header + "5\tIUPAC_AMBIGUITY\tC\tY\n9\tDEFINED_SUBSTITUTION\tG\tA\n", encoding="utf-8")  # forgot to complement
    assert ref.crosscheck_nb01_handoff(tmp_path, variants)["status"] == "MISMATCH"


# ------------------------------------------------------------------ the versioned pin
def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_pin_content_matches_nb01_and_cp1_values():
    pin = ref.load_pin(ROOT)
    operational, sibling = pin["records"]["operational"], pin["records"]["sibling"]
    assert (operational["accession"], operational["cds_length"], operational["cds_sha256"]) == ("GITV01008430.1", 1425, OPERATIONAL_CDS_SHA)
    assert (sibling["accession"], sibling["cds_length"], sibling["cds_sha256"]) == ("GITV01012450.1", 1425, SIBLING_CDS_SHA)
    assert (operational["strand"], operational["cds_tx_start"], operational["cds_tx_end"]) == ("-", 53, 1477)
    assert [v["cds_pos"] for v in pin["variants"]] == VARIANT_POSITIONS
    assert [v["class"] for v in pin["variants"]].count("DEFINED_SUBSTITUTION") == 1
    assert next(v for v in pin["variants"] if v["cds_pos"] == 816)["class"] == "DEFINED_SUBSTITUTION"
    assert next(v for v in pin["variants"] if v["cds_pos"] == 350)["sibling_possible_amino_acids"] == "K/R"
    assert pin["tsa"]["file_sha256"] == json.loads((ROOT / "data/reference/manifest.json").read_text())["files"][0]["sha256"]
    assert {r["id"] for r in pin["known_dsrnase2_compatible_records"]} == {
        "GITV01008430.1", "GITV01012450.1", "TRINITY_DN22752_c0_g2_i1"}


def test_pin_benchmark_is_reference_set_with_two_separate_protocols_and_no_efficacy_score():
    benchmark = ref.load_pin(ROOT)["benchmark"]
    assert benchmark["candidate_class"] == "PUBLISHED_EXPERIMENTAL_BENCHMARK"
    assert benchmark["evidence"] == "DIRECT_EXPERIMENTAL_D_MAIDIS"
    assert benchmark["reference_set_only"] is True
    assert (benchmark["interval"]["cds_start"], benchmark["interval"]["cds_end"], benchmark["interval"]["length_nt"]) == (814, 1143, 330)
    assert benchmark["interval"]["sequence_sha256"] == BENCHMARK_SHA
    assert benchmark["amplicon_lengths_bp"] == {"without_t7_tails": 330, "with_t7_tails": 360}
    assert benchmark["primers"]["t7_tails_in_dsrna_body"] is False
    assert [p["name"] for p in benchmark["protocols"]] == ["INJECTION_PRECONDITIONING", "ORAL_COFEEDING"]
    injection, cofeeding = benchmark["protocols"]
    assert injection["dsrnase2_dsrna"] == {"route": "injection", "dose_ng_per_uL": 200} and injection["recovery_hours"] == 48
    assert cofeeding["dsrnase2_dsrna"]["dose_ng_per_uL"] == 200 and cofeeding["bicc_dsrna"]["dose_ng_per_uL"] == 200
    assert cofeeding["feeding_days"] == 3 and cofeeding["diet_and_dsrna_renewed"] == "daily"
    assert not any("efficacy" in str(key).lower() and "score" in str(key).lower() for key in _keys(benchmark))
    assert benchmark["verification"]["experimental_protocol_verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"  # never claims an unread article as read


def test_pin_hash_is_line_ending_independent(tmp_path):
    (tmp_path / ref.PIN_PATH.parent).mkdir(parents=True)
    original = (ROOT / ref.PIN_PATH).read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / ref.PIN_PATH).write_bytes(original.replace(b"\n", b"\r\n"))
    assert ref.pin_sha256(tmp_path) == ref.pin_sha256(ROOT)


# ------------------------------------------------------------------ real data (skipped without the TSA)
@needs_tsa
def test_verify_reference_reproduces_pin_from_the_hash_validated_tsa():
    report = ref.verify_reference(ROOT)
    assert report["operational"]["cds_sha256"] == OPERATIONAL_CDS_SHA
    assert report["sibling"]["cds_sha256"] == SIBLING_CDS_SHA
    assert [v["cds_pos"] for v in report["variants"]] == VARIANT_POSITIONS
    benchmark = report["benchmark"]
    assert (benchmark["cds_start"], benchmark["cds_end"], benchmark["length_nt"], benchmark["sequence_sha256"]) == (814, 1143, 330, BENCHMARK_SHA)
    assert benchmark["variants_inside"] == [816]
    assert benchmark["sibling_primer_sites"] == {"forward": "NO_EXACT_MATCH", "reverse": "EXACT_MATCH"}
    assert report["nb01_handoff_crosscheck"]["status"] in {"MATCH", "ABSENT"}


# ------------------------------------------------------------------ two separate provenance layers of the benchmark
def test_pin_separates_sequence_verification_from_protocol_provenance():
    benchmark = ref.load_pin(ROOT)["benchmark"]
    verification = benchmark["verification"]
    assert verification["benchmark_sequence_verification"] == ref.SEQUENCE_VERIFICATION == "VERIFIED_FROM_SUPPLEMENT_AND_REFERENCE"
    assert verification["experimental_protocol_verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"
    assert verification["experimental_protocol_verification"] in ref.PROTOCOL_VERIFICATION_STATES
    assert all(p["verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED" for p in benchmark["protocols"])
    assert all(p["endpoints_reported"] is None or p["endpoints_reported"] for p in benchmark["protocols"])  # stored, not removed
    assert benchmark["protocols"][1]["endpoints_reported"]
    assert "generic" not in json.dumps(verification).lower()
    assert "promotion_condition" in json.dumps(verification)


def test_verify_benchmark_rejects_missing_or_inconsistent_verification_layers():
    forward, reverse = "ACGTACGTAC", "TTGGCCATGG"
    cds = "GG" + forward + "AAAA" + reverse_complement(reverse) + "GG"
    good = {"benchmark_sequence_verification": ref.SEQUENCE_VERIFICATION,
            "experimental_protocol_verification": "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"}
    protocols = [{"name": "INJECTION_PRECONDITIONING", "verification": good["experimental_protocol_verification"]},
                 {"name": "ORAL_COFEEDING", "verification": good["experimental_protocol_verification"]}]
    problems: list[str] = []
    ref._verify_benchmark(_benchmark_for(cds, forward, reverse, verification=good, protocols=protocols), cds, cds, [], problems)
    assert problems == []
    bad = {"benchmark_sequence_verification": "VERIFIED", "experimental_protocol_verification": "VERIFIED"}
    problems = []
    ref._verify_benchmark(_benchmark_for(cds, forward, reverse, verification=bad, protocols=protocols), cds, cds, [], problems)
    joined = " ".join(problems)
    assert "benchmark_sequence_verification" in joined and "experimental_protocol_verification" in joined
    protocols[0]["verification"] = "VERIFIED_AGAINST_PRIMARY_TEXT"  # one protocol promoted alone: inconsistent
    problems = []
    ref._verify_benchmark(_benchmark_for(cds, forward, reverse, verification=good, protocols=protocols), cds, cds, [], problems)
    assert any("differs from experimental_protocol_verification" in p for p in problems)


def test_published_cdna_body_matches_the_operational_benchmark_body():
    pin = ref.load_pin(ROOT)["benchmark"]
    body = ref.published_cdna_body(ROOT, pin["primers"]["forward"]["sequence"], pin["primers"]["reverse"]["sequence"])
    from zeaguard.nb01_dsrnase_investigation import sha256_text
    assert len(body) == 330 and sha256_text(body) == BENCHMARK_SHA
    with pytest.raises(ref.NB02ContractError):
        ref.published_cdna_body(ROOT, "AAAAAAAAAAAAAAAAAAAA", pin["primers"]["reverse"]["sequence"])
