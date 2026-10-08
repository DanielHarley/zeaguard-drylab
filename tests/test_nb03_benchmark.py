from __future__ import annotations

from types import SimpleNamespace

import pytest

from zeaguard import nb03_benchmark as bench, nb03_reference as ref
from zeaguard.nb01_identity import reverse_complement
from zeaguard.nb03_benchmark import NB03BenchmarkError

TAIL = bench.T7_TAIL
CDS = "ATG" + "GCCAAACGTTTGGAAGAACTGAAAGGGCCCTTT" + "TAA"  # 39 nt
UTR5, UTR3 = "CATCGATTAC", "TGACTGATCGGA"


def _tokens(forward="TAGAGCCGGCAGATGAGTTT", reverse="TCCACACCTTCCATCTCTCC", lengths=(86, 108, 180, 128, 226, 445, 330, 372, 475, 360, 402)):
    return (["Table S1", "dsRNase2_Fw", "GTCAATGTCGCCCCTCAGT", "dsRNase2_Rv", "AGGCTCTGTTTGTTCGTGTTC",
             "BicC_Fw", forward, "BicC_Rv", reverse, "BicC_Fw_T7", TAIL, forward, "BicC_Rv_T7", TAIL, reverse,
             "BicC_Fw_qPCR", "A"] + [str(v) for v in lengths])


# ------------------------------------------------------------------ Table S1 parsing
def test_parse_table_s1_separates_primers_tails_and_lengths():
    table = bench.parse_table_s1(_tokens())
    assert table["bicc_forward"] == "TAGAGCCGGCAGATGAGTTT" and table["bicc_forward_t7"]["tail"] == TAIL
    assert table["reported_lengths_bp"]["bicc_template"] == 372 and table["reported_lengths_bp"]["bicc_with_t7"] == 402


def test_parse_table_s1_rejects_bad_tail_non_dna_and_short_columns():
    tokens = _tokens()
    bad_tail = [t if t != TAIL else "CGACTCACTATAGG" for t in tokens]
    with pytest.raises(NB03BenchmarkError):
        bench.parse_table_s1(bad_tail)
    with pytest.raises(NB03BenchmarkError):
        bench.parse_table_s1(_tokens(forward="TAGAGCCGGCAGATGAGTTN"))
    with pytest.raises(NB03BenchmarkError):
        bench.parse_table_s1(_tokens()[:-6])


# ------------------------------------------------------------------ primer mapping
def _sense():
    return UTR5 + CDS + UTR3


def test_map_primers_unique_orientation_and_body():
    sense = _sense()
    forward, reverse = sense[8:28], reverse_complement(sense[50:70] if len(sense) >= 70 else sense[-20:])
    stored = reverse_complement(sense)
    mapped = bench.map_primers(stored, forward, reverse)
    assert mapped["orientation"] == "reverse_complement_of_stored"
    assert mapped["body"] == sense[8 : 8 + len(mapped["body"])] and mapped["body"].startswith(forward)
    direct = bench.map_primers(sense, forward, reverse)
    assert direct["orientation"] == "stored" and direct["body"] == mapped["body"]


def test_map_primers_fails_on_absent_duplicated_or_both_strand_primers():
    sense = _sense()
    forward, reverse = sense[8:28], reverse_complement(sense[-20:])
    with pytest.raises(NB03BenchmarkError, match="exactly once"):
        bench.map_primers(sense, "ACGTACGTACGTACGTACGT", reverse)
    with pytest.raises(NB03BenchmarkError, match="exactly once"):
        bench.map_primers(sense + sense[8:28], forward, reverse)  # forward occurs twice
    with pytest.raises(NB03BenchmarkError, match="exactly once"):
        bench.map_primers(sense + reverse_complement(sense[8:28]), forward, reverse)  # and once on the other strand
    with pytest.raises(NB03BenchmarkError, match="arrangement"):
        bench.map_primers(sense, reverse_complement(sense[-20:]), reverse_complement(sense[8:28]))  # reversed roles


def test_assess_length_preserves_published_and_reconstructed_lengths_side_by_side():
    match = bench.assess_length(372, 372, 402, 15)
    assert match["status"] == "MATCH" and match["length_discrepancy_status"] == "NONE" and match["length_discrepancy_nt"] == 0
    off = bench.assess_length(373, 372, 402, 15)
    assert (off["published_reported_body_length_nt"], off["reconstructed_body_length_nt"]) == (372, 373)
    assert (off["published_reported_t7_amplicon_length_nt"], off["reconstructed_t7_amplicon_length_nt"]) == (402, 403)
    assert off["length_discrepancy_nt"] == 1 and off["t7_amplicon_discrepancy_nt"] == 1
    assert off["length_discrepancy_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY" and off["cause_asserted"] is False
    assert "not an explanation" in off["hypothesis_not_promoted"]  # the non-inclusive-count idea stays a separate hypothesis
    assert bench.assess_length(372, 372, 400, 15)["published_t7_arithmetic_consistent"] is False


# ------------------------------------------------------------------ reconstruction with a synthetic reference (UTR handling)
def _reference(forward: str, reverse: str):
    sense = _sense()
    operational = {"accession": "OP", "cds_length": len(CDS)}
    published = {"strand": "-", "utr5_length": len(UTR5)}
    return {
        "published_stored": reverse_complement(sense), "published_sense": sense, "published": published, "operational": operational,
        "sense_to_record": {i: i for i in range(1, len(sense) + 1)}, "record_sequence": sense,
        "placement": {"hsp": SimpleNamespace(strand="minus")},
        "differences": [{"cds_position": 5}, {"cds_position": 30}],
    }


def _table(forward, reverse, body_len, role=bench.ROLE_2022):
    return {"bicc_forward": forward, "bicc_reverse": reverse, "source": {"filename": "x", "source_role": role},
            "reported_lengths_bp": {"bicc_template": body_len, "bicc_with_t7": body_len + 30}}


def test_reconstruct_separates_body_t7_and_amplicon_and_hashes_the_body():
    sense = _sense()
    start, end = len(UTR5) + 4, len(UTR5) + 30  # fully inside the CDS
    forward, reverse = sense[start - 1 : start + 19], reverse_complement(sense[end - 20 : end])
    result = bench.reconstruct(_reference(forward, reverse), _table(forward, reverse, end - start + 1))
    body = result["body"]
    assert body["sequence"] == sense[start - 1 : end] and body["length_nt"] == end - start + 1 and body["t7_tails_in_body"] is False
    assert not body["sequence"].startswith(TAIL)
    assert result["amplicon_with_t7_tails"]["length_nt"] == body["length_nt"] + 30
    assert result["primers_with_t7"]["forward"] == TAIL + forward
    assert result["length_assessment"]["status"] == "MATCH"
    assert result["benchmark_sequence_verification"] == bench.SEQUENCE_VERIFIED
    assert result["experimental_protocol_verification"] == bench.PROTOCOL_UNVERIFIED  # never inferred from the sequence layer
    assert result["benchmark_nt_outside_cds"] == 0 and result["benchmark_fully_inside_cds"] is True
    assert result["observed_sequence_differences_intercepted"] == [5, 30]
    assert result["body_identical_in_operational_record"] is True


def test_benchmark_crossing_the_utr_keeps_the_cds_only_design_domain():
    sense = _sense()
    forward, reverse = sense[2:22], reverse_complement(sense[-20:])  # starts in the 5' UTR, ends in the 3' UTR
    reference = _reference(forward, reverse)
    result = bench.reconstruct(reference, _table(forward, reverse, len(sense) - 2))
    assert result["benchmark_nt_inside_cds"] == len(CDS)
    assert result["benchmark_nt_outside_cds"] == result["body"]["length_nt"] - len(CDS) > 0
    assert result["benchmark_fully_inside_cds"] is False
    assert result["design_domain_cds"] == [1, len(CDS)] == list(ref.design_domain(reference["operational"]))
    assert result["coordinates"]["cds_sense"]["start"] < 1 and result["coordinates"]["cds_sense"]["end"] > len(CDS)


def test_benchmark_entirely_in_a_utr_has_no_cds_overlap_and_does_not_widen_the_domain():
    long_utr3 = "GATCCTAGGCATTCGAAGTCCATGCATTGACCTAGGATTCCAGT"
    sense = UTR5 + CDS + long_utr3
    f, r = long_utr3[2:22], reverse_complement(long_utr3[-18:])
    reference = _reference(f, r)
    reference.update({"published_stored": reverse_complement(sense), "published_sense": sense, "record_sequence": sense,
                      "sense_to_record": {i: i for i in range(1, len(sense) + 1)}})
    body_len = len(long_utr3) - 2
    result = bench.reconstruct(reference, _table(f, r, body_len))
    assert result["benchmark_nt_inside_cds"] == 0 and result["benchmark_nt_outside_cds"] == result["body"]["length_nt"] == body_len
    assert result["design_domain_cds"] == [1, len(CDS)]
    assert result["observed_sequence_differences_intercepted"] == []
    assert result["benchmark_fully_inside_cds"] is False


def test_primers_from_a_non_primary_source_do_not_carry_the_2022_verification():
    sense = _sense()
    forward, reverse = sense[11:31], reverse_complement(sense[40:60])
    result = bench.reconstruct(_reference(forward, reverse), _table(forward, reverse, 49, role=bench.ROLE_2023))
    assert result["benchmark_sequence_verification"] == bench.SEQUENCE_NOT_PRIMARY
    assert result["primary_2022_primers_verification"] == "NOT_VERIFIED"


def test_inconsistent_length_without_explanation_is_not_verified_as_a_match():
    sense = _sense()
    forward, reverse = sense[11:31], reverse_complement(sense[40:60])
    result = bench.reconstruct(_reference(forward, reverse), _table(forward, reverse, 3))
    assert result["length_assessment"]["status"] == bench.DISCREPANCY_UNRESOLVED
    assert result["benchmark_sequence_verification"] == bench.SEQUENCE_VERIFIED_DISCREPANT
    assert result["body"]["length_nt"] != 3  # the reported length never truncates or reshapes the body


# ------------------------------------------------------------------ real data (shared CP0 run)
def test_real_primary_2022_table_is_ingested_with_provenance(cp0_result):
    b = cp0_result["result"]["benchmark"]
    source = b["source"]
    assert source["source_role"] == "PRIMARY_2022_TABLE_S1" and source["doi"] == "10.1002/ps.6937"
    assert source["sha256"] == "0d235a577ed7ac5782a90e07cdb6679db1ecf2da4d0e9bc79e37bf377b0bc4be" and source["size_bytes"] == 14909
    assert source["filename"] == "ps6937-sup-0006-tables1.docx" and source["origin"] == "user-provided primary supplementary file"
    assert source["source_url"] is None and source["source_url_status"] == "NOT_RECORDED_FOR_USER_PROVIDED_FILE"
    assert source["source_description"] == "Table S1. Primers used for dsRNA synthesis and RT-(q)PCR"
    corroboration = b["corroboration_2023"]
    assert corroboration["source_role"] == bench.ROLE_2023 and corroboration["agrees_with_2022_primers_and_lengths"] is True
    assert "not evidence" in corroboration["note"]


def test_real_2022_primers_and_t7_are_exactly_the_published_ones(cp0_result):
    from pathlib import Path

    table = bench.read_table_s1_2022(Path(__file__).resolve().parents[1])
    assert table["bicc_forward"] == "TAGAGCCGGCAGATGAGTTT" and table["bicc_reverse"] == "TCCACACCTTCCATCTCTCC"
    assert table["bicc_forward_t7"]["sequence"] == "CGACTCACTATAGGGTAGAGCCGGCAGATGAGTTT"
    assert table["bicc_reverse_t7"]["sequence"] == "CGACTCACTATAGGGTCCACACCTTCCATCTCTCC"
    assert table["bicc_forward_t7"]["tail"] == "CGACTCACTATAGGG" and len(table["bicc_forward_t7"]["tail"]) == 15
    assert table["t7_promoter_full"] == "TAATACGACTCACTATAGGG" and table["usage"]["t7"] == "dsRNA synthesis"
    assert table["reported_lengths_bp"] == {"bicc_template": 372, "bicc_with_t7": 402}
    assert "partial T7 promoter" in table["partial_t7_note"]


def test_real_benchmark_body_tails_amplicon_and_coordinates(cp0_result):
    b = cp0_result["result"]["benchmark"]
    assert b["primers_without_t7"] == {"forward": "TAGAGCCGGCAGATGAGTTT", "reverse": "TCCACACCTTCCATCTCTCC"}
    assert b["primer_occurrences_on_both_strands"] == {"forward": 1, "reverse": 1}
    assert b["primer_orientation_on_stored_cdna"] == "reverse_complement_of_stored"
    assert b["body"]["length_nt"] == 373 and not b["body"]["sequence"].startswith(TAIL)
    assert b["body"]["sha256"] == "e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb"
    assert b["amplicon_with_t7_tails"]["length_nt"] == 403
    c = b["coordinates"]
    assert (c["published_cdna_as_stored"]["start"], c["published_cdna_as_stored"]["end"]) == (2020, 2392)
    assert (c["published_cdna_sense"]["start"], c["published_cdna_sense"]["end"]) == (264, 636)
    assert (c["operational_record"]["start"], c["operational_record"]["end"], c["operational_record"]["strand_of_body"]) == (279, 651, "+")
    assert (c["cds_sense"]["start"], c["cds_sense"]["end"]) == (215, 587)
    assert (b["benchmark_nt_inside_cds"], b["benchmark_nt_outside_cds"]) == (373, 0)
    assert b["body_identical_in_operational_record"] is True and b["observed_sequence_differences_intercepted"] == []


def test_real_length_discrepancy_is_preserved_not_adjusted_and_does_not_block_g0(cp0_result):
    b = cp0_result["result"]["benchmark"]
    assert (b["published_reported_body_length_nt"], b["reconstructed_body_length_nt"]) == (372, 373)
    assert (b["published_reported_t7_amplicon_length_nt"], b["reconstructed_t7_amplicon_length_nt"]) == (402, 403)
    assert b["length_discrepancy_nt"] == 1 and b["length_discrepancy_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY"
    assert b["body"]["length_nt"] == 373 and b["amplicon_with_t7_tails"]["length_nt"] == 403  # nothing truncated
    assert b["primary_2022_primers_verification"] == "VERIFIED_FROM_PRIMARY_2022_TABLE_S1"
    assert b["benchmark_sequence_basis"] == "PRIMARY_2022_PRIMER_DEFINED_RECONSTRUCTION"
    assert b["benchmark_sequence_verification"] == "VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY"
    assert b["experimental_protocol_verification"] == bench.PROTOCOL_UNVERIFIED  # Table S1 does not verify the protocol
    g0 = cp0_result["result"]["g0"]
    assert g0["status"] == "G0_PASS" and g0["cp1"] == "CP1_READY_TO_PLAN_OR_IMPLEMENT"
    assert g0["length_discrepancy_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY"


def test_real_web_attempts_are_recorded_as_pre_primary_and_not_bypassed(cp0_result):
    manifest = cp0_result["result"]["manifest"]
    assert len(manifest["external_sources_provided"]) == 1
    attempts = manifest["external_sources_attempted_not_retrieved_before_the_primary_file_was_provided"]
    assert any("403" in s["outcome"] for s in attempts)


# ------------------------------------------------------------------ Table S1 (2022) DOCX parsing, synthetic
def _docx(rows, notes, extra=""):
    import io
    import zipfile

    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def cell(text, merge=None):
        pr = "" if merge is None else (f'<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>' if merge == "restart" else "<w:tcPr><w:vMerge/></w:tcPr>")
        return f"<w:tc>{pr}<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"

    body = "<w:tbl>" + "".join("<w:tr>" + "".join(cell(*c) if isinstance(c, tuple) else cell(c) for c in row) + "</w:tr>" for row in rows) + "</w:tbl>"
    body += "".join(f"<w:p><w:r><w:t>{n}</w:t></w:r></w:p>" for n in notes)
    xml = f'{extra}<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


F, R = "TAGAGCCGGCAGATGAGTTT", "TCCACACCTTCCATCTCTCC"
NOTE = "+partial T7 promoter sequence is indicated in bold. T7 promoter: 5\u2032-TAATACGACTCACTATAGGG-3\u2032."
HEADER = ["Primer name", "Usage", "Sequence (5'\u20133')+", "Amplicon length (bp)"]


def _rows(fw_t7=TAIL + F):
    return [HEADER,
            ["BicC_Fw", ("RT-PCR", "restart"), F, ("372", "restart")], ["BicC_Rv", ("", "cont"), R, ("", "cont")],
            ["BicC_Fw_T7", ("dsRNA synthesis", "restart"), fw_t7, ("402", "restart")], ["BicC_Rv_T7", ("", "cont"), TAIL + R, ("", "cont")]]


def test_parse_2022_table_reads_vertically_merged_cells():
    table = bench.parse_table_s1_2022(*bench.docx_table_and_notes(_docx(_rows(), [NOTE])))
    assert (table["bicc_forward"], table["bicc_reverse"]) == (F, R)
    assert table["reported_lengths_bp"] == {"bicc_template": 372, "bicc_with_t7": 402}
    assert table["usage"] == {"plain": "RT-PCR", "t7": "dsRNA synthesis"}


def test_parse_2022_table_rejects_wrong_t7_wrong_note_and_entities():
    with pytest.raises(NB03BenchmarkError, match="plain primers plus"):
        bench.parse_table_s1_2022(*bench.docx_table_and_notes(_docx(_rows(fw_t7="CGACTCACTATAGG" + F), [NOTE])))
    with pytest.raises(NB03BenchmarkError, match="promoter note"):
        bench.parse_table_s1_2022(*bench.docx_table_and_notes(_docx(_rows(), ["T7 promoter: 5-GGGGGGGGGGGGGGGGGGGG-3"])))
    with pytest.raises(NB03BenchmarkError, match="refused"):
        bench.docx_table_and_notes(_docx(_rows(), [NOTE], extra='<!DOCTYPE x [<!ENTITY a "b">]>'))
    bad_header = _rows()
    bad_header[0] = ["Name", "Usage", "Sequence", "Length"]
    with pytest.raises(NB03BenchmarkError, match="header"):
        bench.parse_table_s1_2022(*bench.docx_table_and_notes(_docx(bad_header, [NOTE])))


def test_read_2022_table_refuses_a_file_with_a_different_sha256(tmp_path):
    target = tmp_path / bench.TABLE_S1_2022_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(_docx(_rows(), [NOTE]))
    with pytest.raises(NB03BenchmarkError, match="sha256"):
        bench.read_table_s1_2022(tmp_path)
    with pytest.raises(NB03BenchmarkError, match="not available"):
        bench.read_table_s1_2022(tmp_path / "empty")
