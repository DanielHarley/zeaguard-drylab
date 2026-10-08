from __future__ import annotations

from types import SimpleNamespace

import pytest

from zeaguard import nb03_reference as ref
from zeaguard.nb01_identity import reverse_complement
from zeaguard.nb01_dsrnase_investigation import Hsp

CDS = "ATG" + "GCCAAACGTTTGGAAGAACTG" + "TAA"  # M A K R L E E L *  (27 nt)


def _record(strand: str, utr5: str = "CCCCC", utr3: str = "GGGGGGG") -> str:
    sense = utr5 + CDS + utr3
    return sense if strand == "+" else reverse_complement(sense)


# ------------------------------------------------------------------ ORFs and records
def test_derive_record_plus_strand_coordinates_utrs_and_hashes():
    rec = ref.derive_record("X", _record("+"))
    assert (rec["strand"], rec["cds_tx_start"], rec["cds_tx_end"], rec["cds_length"]) == ("+", 6, 32, 27)
    assert (rec["utr5_length"], rec["utr3_length"], rec["protein_length"]) == (5, 7, 8)
    assert rec["_cds"] == CDS and rec["_protein"] == "MAKRLEEL"
    assert rec["utr5_length"] + rec["cds_length"] + rec["utr3_length"] == rec["record_length"]


def test_derive_record_minus_strand_returns_coding_orientation():
    rec = ref.derive_record("X", _record("-"))
    assert rec["strand"] == "-" and rec["_cds"] == CDS
    assert (rec["utr5_length"], rec["utr3_length"]) == (5, 7)
    assert rec["record_sha256"] != ref.derive_record("X", _record("+"))["record_sha256"]


def test_derive_record_is_deterministic():
    assert ref.derive_record("X", _record("-")) == ref.derive_record("X", _record("-"))


def test_derive_record_rejects_tied_longest_orf_and_no_orf():
    with pytest.raises(ref.NB03ReferenceError, match="not unique"):
        ref.derive_record("X", CDS + "CCCCCCCC" + CDS)
    with pytest.raises(ref.NB03ReferenceError, match="no complete ORF"):
        ref.derive_record("X", "CCCCCCCCCC")


def test_derive_record_lists_iupac_symbols_and_their_region():
    sequence = "CCCRC" + CDS + "GGGGGGG"
    rec = ref.derive_record("X", sequence)
    assert rec["iupac_positions"] == [{"record_position": 4, "symbol": "R", "region": "UTR"}]


# ------------------------------------------------------------------ observed_sequence_differences
def test_differences_fields_status_and_classes():
    published = "ATGGCCAAACGTTTGGAAGAACTGTAA"
    operational = "ATGACCAAGCGTTTGGAAGAACTGTAA"  # pos 4 G>A (A>T), pos 9 A>G synonymous (K)
    rows = ref.observed_sequence_differences(published, operational)
    assert [r["cds_position"] for r in rows] == [4, 9]
    first, second = rows
    assert (first["published_base"], first["operational_base"], first["codon_position"]) == ("G", "A", 1)
    assert (first["published_amino_acid"], first["operational_amino_acid"]) == ("A", "T")
    assert (first["synonymous_status"], first["substitution_class"]) == ("NONSYNONYMOUS", "TRANSITION")
    assert (second["synonymous_status"], second["substitution_class"]) == ("SYNONYMOUS", "TRANSITION")
    assert all(r["read_support_status"] == "NOT_ASSESSED_FOR_NB03_CP0" for r in rows)


def test_differences_transversion_and_unequal_lengths():
    rows = ref.observed_sequence_differences("ATGAAA", "ATGAAT")
    assert rows[0]["substitution_class"] == "TRANSVERSION"
    with pytest.raises(ref.NB03ReferenceError):
        ref.observed_sequence_differences("ATGAAA", "ATGAA")


def test_differences_schema_never_names_their_nature():
    ref.assert_descriptive_columns(ref.DIFFERENCE_COLUMNS)
    assert not any(any(t in c.lower() for t in ref.FORBIDDEN_NATURE_TERMS) for c in ref.DIFFERENCE_COLUMNS)
    for bad in ("variant_position", "allele", "polymorphism_class"):
        with pytest.raises(ref.NB03ReferenceError):
            ref.assert_descriptive_columns(("cds_position", bad))


# ------------------------------------------------------------------ coordinates
def _hsp(strand: str, qstart: int, qend: int, sstart: int, send: int, btop: str) -> Hsp:
    return Hsp("q", "s", 99.0, 0, 0, 0, qstart, qend, sstart, send, strand, 0.0, 0.0, 0, 0, 0, 0.0, btop)


def test_position_map_plus_and_minus_with_gaps():
    plus = ref.position_map(_hsp("plus", 1, 6, 11, 16, "6"))
    assert plus == {1: 11, 2: 12, 3: 13, 4: 14, 5: 15, 6: 16}
    minus = ref.position_map(_hsp("minus", 1, 6, 16, 11, "6"))
    assert minus == {1: 16, 2: 15, 3: 14, 4: 13, 5: 12, 6: 11}
    # query base against a subject gap -> None; subject-only base advances only the subject
    with_gaps = ref.position_map(_hsp("plus", 1, 5, 1, 5, "2A-1-A1"))
    assert with_gaps == {1: 1, 2: 2, 3: None, 4: 3, 5: 5}
    inserted = ref.position_map(_hsp("plus", 1, 4, 1, 5, "2-G2"))
    assert inserted == {1: 1, 2: 2, 3: 4, 4: 5}


def test_position_map_rejects_btop_that_does_not_span_the_hsp():
    with pytest.raises(ref.NB03ReferenceError):
        ref.position_map(_hsp("plus", 1, 6, 1, 6, "4"))


def test_coordinate_conversions_round_trip():
    rec = ref.derive_record("X", _record("-"))
    assert ref.stored_to_sense(1, 10) == 10 and ref.stored_to_sense(10, 10) == 1
    assert ref.sense_to_cds(rec["utr5_length"] + 1, rec["utr5_length"]) == 1
    assert ref.cds_to_record(1, rec) == rec["cds_tx_end"] and ref.cds_to_record(27, rec) == rec["cds_tx_start"]
    plus = ref.derive_record("X", _record("+"))
    assert ref.cds_to_record(1, plus) == plus["cds_tx_start"]
    assert ref.design_domain(rec) == (1, 27)


def test_sense_strand_on_record_flips_with_the_stored_cds_strand():
    assert ref._sense_strand_on_record("minus", "-") == "+"
    assert ref._sense_strand_on_record("plus", "-") == "-"
    assert ref._sense_strand_on_record("plus", "+") == "+"


# ------------------------------------------------------------------ real data (shared CP0 run)
def test_real_operational_reference_is_rederived(cp0_result):
    op = cp0_result["result"]["reference"]["summary"]["operational"]
    assert op["accession"] == "GITV01000968.1" and op["strand"] == "+"
    assert (op["cds_tx_start"], op["cds_tx_end"], op["cds_length"], op["protein_length"]) == (65, 2401, 2337, 778)
    assert (op["utr5_length"], op["utr3_length"], op["record_length"]) == (64, 3665, 6066)
    assert op["cds_sha256"] == "05cb44b0bf9d0c72d2adaa5b09cf9c0795039e29858e666c6082a170e5924f30"
    assert op["protein_sha256"] == "b6318f70856358ef1ed021d974bebcae5df73bf2cb5eb1f8f02d84eaa1a391bc"
    assert op["record_sha256"] == "6d67491d7042b2377ae2149249b530c93442136b74d20038f67903593259bc9a"
    assert op["iupac_positions"] == [{"record_position": 3624, "symbol": "R", "region": "UTR"}]


def test_real_published_cdna_is_stored_antisense_and_lengths_relate(cp0_result):
    summary = cp0_result["result"]["reference"]["summary"]
    pub, placement = summary["published"], summary["placement_on_operational_record"]
    assert pub["stored_orientation"] == "STORED_ANTISENSE_REVERSE_COMPLEMENT_OF_CODING"
    assert (pub["stored_length"], pub["cds_length"], pub["utr5_length"], pub["utr3_length"]) == (2655, 2337, 49, 269)
    assert pub["utr5_length"] + pub["cds_length"] + pub["utr3_length"] == pub["stored_length"]
    assert pub["cds_start_in_sense"] == 50 and pub["cds_end_in_sense"] == 2386
    assert placement["subject_strand"] == "minus" and placement["record_strand_of_published_sense"] == "+"
    assert placement["published_transcript_span_on_record"] == [16, 2663]
    assert all(summary["checks"].values()) and summary["cds_position_disagreements"] == []


def test_real_observed_differences(cp0_result):
    rows = cp0_result["result"]["reference"]["differences"]
    assert [r["cds_position"] for r in rows] == [597, 1092, 1120, 1287, 2094, 2259, 2280]
    assert sum(r["synonymous_status"] == "NONSYNONYMOUS" for r in rows) == 1
    assert all(r["read_support_status"] == "NOT_ASSESSED_FOR_NB03_CP0" for r in rows)
    text = (cp0_result["out"] / "observed_sequence_differences.tsv").read_text(encoding="utf-8").lower()
    assert not any(term in text for term in ref.FORBIDDEN_NATURE_TERMS)
    summary = cp0_result["result"]["reference"]["summary"]
    assert summary["cds_to_cds"]["protein_identical"] is False


def test_real_reference_is_deterministic(cp0_result, tmp_path):
    from zeaguard.nb01_dsrnase_investigation import CommandLog

    again = ref.derive_reference(_root(), tmp_path, CommandLog())
    first = cp0_result["result"]["reference"]["summary"]
    assert again["summary"]["operational"] == first["operational"]
    assert again["differences"] == cp0_result["result"]["reference"]["differences"]


def _root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]
