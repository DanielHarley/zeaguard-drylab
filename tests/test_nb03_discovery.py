from __future__ import annotations

import pytest

from zeaguard import nb03_cp0, nb03_discovery as disc
from zeaguard.nb01_dsrnase_investigation import Hsp


def _blastn(subject, qstart, qend, ident=90.0, bit=100.0, length=None):
    return Hsp("q", subject, ident, length or qend - qstart + 1, 100, 500, qstart, qend, 1, 50, "plus", 1e-5, bit, 0, 0, 0, 0.0, "")


def _tblastn(subject, qstart, qend, bit=50.0, frame=1, sstart=1, send=90):
    return {"sseqid": subject, "slen": 500, "pident": 40.0, "length": qend - qstart + 1, "qstart": qstart, "qend": qend,
            "sstart": sstart, "send": send, "sframe": frame, "evalue": 1e-5, "bitscore": bit}


# ------------------------------------------------------------------ pure functions
def test_parse_tblastn_types_and_rejects_bad_lines():
    line = "\t".join(["q", "s", "50.0", "30", "778", "900", "1", "30", "10", "99", "2", "1e-5", "40.1", "5", "0", "0", "4"])
    row = disc.parse_tblastn(line + "\n")[0]
    assert row["sframe"] == 2 and row["length"] == 30 and row["bitscore"] == 40.1
    with pytest.raises(disc.NB03DiscoveryError):
        disc.parse_tblastn("q\ts\n")


def test_summarise_records_unions_coverage_and_filters_nothing():
    rows = disc.summarise_records(
        [_blastn("A", 1, 100), _blastn("A", 50, 150), _blastn("B", 1, 10)],
        [_tblastn("A", 1, 20), _tblastn("A", 10, 40), _tblastn("C", 1, 5)],
        cds_length=300, protein_length=100)
    by = {r["accession"]: r for r in rows}
    assert set(by) == {"A", "B", "C"}  # every reported hit is listed
    assert by["A"]["found_by"] == "BOTH" and by["B"]["found_by"] == "BLASTN" and by["C"]["found_by"] == "TBLASTN"
    assert by["A"]["blastn_covered_cds_nt"] == 150 and by["A"]["tblastn_covered_protein_aa"] == 40
    assert by["A"]["tblastn_covered_protein_fraction"] == 0.4
    assert all(r["unit_proposal"] == "NOT_PROPOSED" and not r["followed_up"] for r in rows)


def test_follow_up_rule_is_the_preregistered_inspection_rule():
    rows = [{"accession": "OP", "tblastn_covered_protein_fraction": 1.0}, {"accession": "HALF", "tblastn_covered_protein_fraction": 0.5},
            {"accession": "LOW", "tblastn_covered_protein_fraction": 0.4999}, {"accession": "GITV01002238.1", "tblastn_covered_protein_fraction": 0.1}]
    assert disc.select_follow_up(rows, "OP") == ["GITV01002238.1", "HALF", "OP"]
    assert disc.FOLLOW_UP_MIN_PROTEIN_COVERAGE == 0.5


def test_best_orf_follows_the_hsp_strand_and_overlap():
    cds = "ATG" + "GCC" * 30 + "TAA"
    sequence = "CCCCC" + cds + "GGGGG"
    plus = disc.best_orf_for_hsp(sequence, {"sframe": 1, "sstart": 20, "send": 60})
    assert plus["strand"] == "+" and (plus["cds_tx_start"], plus["cds_tx_end"]) == (6, 5 + len(cds))
    assert disc.best_orf_for_hsp(sequence, {"sframe": -1, "sstart": 20, "send": 60}) is None


def test_bicc_like_stays_unresolved_and_is_never_a_paralog():
    row = {"blastn_best_identity_percent": 79.655}
    like = disc._proposal("GITV01002238.1", "GITV01000968.1", row)
    assert like["unit_proposal"] == "BICC_LIKE" and like["relationship_status"] == "UNRESOLVED"
    known = disc._proposal("GITV01000968.1", "GITV01000968.1", {"blastn_best_identity_percent": 100.0})
    assert known["unit_proposal"] == "KNOWN_BICC_COMPATIBLE"
    flagged = disc._proposal("OTHER", "GITV01000968.1", {"blastn_best_identity_percent": 99.0})
    assert flagged["unit_proposal"].endswith("PENDING_REVIEW") and flagged["_flag"].startswith("REVIEW_AS_SAME_LOCUS")
    assert flagged["relationship_status"] == "UNRESOLVED"
    disc.assert_no_paralog_label([like, known])
    with pytest.raises(disc.NB03DiscoveryError):
        disc.assert_no_paralog_label([{"unit_proposal": "paralog"}])


def test_search_settings_are_the_nb02_detection_limit():
    from pathlib import Path

    s = disc.search_settings(Path(__file__).resolve().parents[1])
    assert (s["task"], s["word_size"], s["evalue_report_limit"], s["strand"]) == ("blastn", 11, 10, "both")


# ------------------------------------------------------------------ G0 logic
def _benchmark(status="UNRESOLVED_PUBLICATION_INCONSISTENCY", primary=True):
    return {"primary_2022_primers_verification": "VERIFIED_FROM_PRIMARY_2022_TABLE_S1" if primary else "NOT_VERIFIED",
            "length_assessment": {"length_discrepancy_status": status, "published_reported_body_length_nt": 372,
                                  "reconstructed_body_length_nt": 373}}


def _g0(benchmark, error=None, others=True):
    reference = {"summary": {"checks": {"a": True}}}
    discovery = {"blastn_ran": others, "tblastn_ran": True, "operational_proposed": True, "positive_control_present": True}
    return nb03_cp0.evaluate_g0(reference, benchmark, error, discovery, True)


def test_g0_passes_with_a_preserved_publication_discrepancy():
    g0 = _g0(_benchmark())
    assert g0["status"] == "G0_PASS" and g0["cp1"] == "CP1_READY_TO_PLAN_OR_IMPLEMENT"
    assert g0["length_discrepancy_status"] == "UNRESOLVED_PUBLICATION_INCONSISTENCY"
    assert _g0(_benchmark("NONE"))["status"] == "G0_PASS"


def test_g0_is_not_pass_without_the_primary_source_or_with_an_ambiguous_mapping():
    partial = _g0(_benchmark(primary=False))
    assert partial["status"] == "G0_PARTIAL" and partial["cp1"] == "CP1_BLOCKED_UNTIL_BENCHMARK_VERIFIED"
    failed = _g0(None, "each primer must occur exactly once on the two strands")
    assert failed["status"] == "G0_FAIL" and failed["cp1"] == "CP1_BLOCKED_UNTIL_BENCHMARK_VERIFIED"
    assert _g0(None, "the 2022 Table S1 is not available")["status"] == "G0_PARTIAL"
    assert _g0(_benchmark(), others=False)["status"] != "G0_PASS"


def test_g0_does_not_require_paralogy_reads_or_an_explanation_of_the_discrepancy():
    conditions = _g0(_benchmark())["conditions"]
    assert not any("paralog" in k or "read" in k or "explain" in k for k in conditions)
    assert len(conditions) == 7


# ------------------------------------------------------------------ real data (shared CP0 run)
def test_real_discovery_ran_blastn_and_tblastn_with_explicit_commands(cp0_result):
    manifest = cp0_result["result"]["manifest"]
    commands = [c["command"] for c in manifest["commands"]]
    assert any(c.startswith("blastn ") and "-db" in c and "-word_size 11" in c and "-evalue 10" in c for c in commands)
    assert any(c.startswith("tblastn ") and "-seg no" in c and "-evalue 10" in c for c in commands)
    assert not any(c.startswith("blastp ") and "tsa" in c for c in commands)  # no BLASTp against the translated TSA
    assert manifest["counts"]["blastn_hsps"] > 0 and manifest["counts"]["tblastn_hsps"] > 0


def test_real_gitv01002238_is_bicc_like_unresolved(cp0_result):
    by = {r["accession"]: r for r in cp0_result["result"]["followed"]}
    assert set(by) == {"GITV01000968.1", "GITV01002238.1"}
    like = by["GITV01002238.1"]
    assert like["unit_proposal"] == "BICC_LIKE" and like["relationship_status"] == "UNRESOLVED"
    assert like["orf_protein_length_aa"] == 789 and like["orf_strand"] == "-"
    assert by["GITV01000968.1"]["unit_proposal"] == "KNOWN_BICC_COMPATIBLE"
    assert float(by["GITV01000968.1"]["blastp_identity_percent"]) == 100.0


def test_real_outputs_never_contain_the_paralog_label(cp0_result):
    for path in cp0_result["out"].glob("*.tsv"):
        assert "PARALOG" not in path.read_text(encoding="utf-8").upper(), path.name
    for name in ("run_manifest.json", "reference_summary.json", "benchmark_reconstruction.json"):
        text = (cp0_result["out"] / name).read_text(encoding="utf-8").upper()
        assert "PARALOG" not in text.replace("NO AUTOMATIC CLASSIFICATION OF PARALOGY", ""), name


def test_real_all_records_table_lists_every_reported_hit(cp0_result):
    result = cp0_result["result"]
    rows = result["rows"]
    assert len(rows) == result["manifest"]["counts"]["records_in_all_records_table"]
    assert {r["accession"] for r in rows if r["found_by"] == "BOTH"} >= {"GITV01000968.1", "GITV01002238.1"}


def test_real_cp0_is_hash_reproducible(cp0_result, tmp_path):
    first = cp0_result["result"]["manifest"]["outputs_sha256"]
    again = nb03_cp0.run_cp0(__import__("pathlib").Path(__file__).resolve().parents[1], tmp_path)
    assert again["manifest"]["outputs_sha256"] == first
