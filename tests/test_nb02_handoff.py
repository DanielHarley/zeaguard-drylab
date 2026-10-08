from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from zeaguard import nb02_cells as cells
from zeaguard import nb02_criteria as crit
from zeaguard import nb02_handoff as handoff

ROOT = Path(__file__).resolve().parents[1]
HAS_HANDOFF = (ROOT / handoff.HANDOFF_TSV).is_file()
HAS_CP3 = (ROOT / cells.CP3_WINDOWS).is_file()
needs_handoff = pytest.mark.skipif(not HAS_HANDOFF, reason="the versioned hand-off is not materialised")
needs_cp3 = pytest.mark.skipif(not HAS_CP3, reason="the CP3 outputs are not materialised locally")

BENCHMARK = "D2-BENCH-0814-1143"
RECOMMENDED_IDS = ("D2-L400-0351-0750", "D2-L400-0817-1216")


@pytest.fixture(scope="module")
def rows():
    with (ROOT / handoff.HANDOFF_TSV).open(encoding="utf-8", newline="") as h:
        return list(csv.DictReader(h, delimiter="\t"))


# ------------------------------------------------------------------ schema and scope
def test_the_handoff_schema_carries_no_construct_engineering_or_off_target():
    assert not [c for c in handoff.HANDOFF_COLUMNS if any(f in c for f in handoff.FORBIDDEN_COLUMN_FRAGMENTS)]
    for forbidden in ("primer", "promoter", "terminator", "hairpin", "restriction", "efficacy"):
        assert not any(forbidden in column for column in handoff.HANDOFF_COLUMNS)


def test_the_versioned_limitations_file_covers_every_listed_candidate():
    limitations = handoff.load_limitations(ROOT)
    assert set(limitations) >= {BENCHMARK, *RECOMMENDED_IDS}
    assert "CDS 500-540" in limitations["D2-L400-0351-0750"]
    assert "CDS 1050-1081" in limitations["D2-L400-0817-1216"]
    assert all("unresolved" in limitations[c] for c in RECOMMENDED_IDS)


def test_load_limitations_rejects_a_wrong_header_or_an_empty_text(tmp_path):
    path = tmp_path / handoff.LIMITATIONS_PATH
    path.parent.mkdir(parents=True)
    path.write_text("candidate_id\tnote\nX\ty\n", encoding="utf-8")
    with pytest.raises(handoff.NB02HandoffError, match="columns"):
        handoff.load_limitations(tmp_path)
    path.write_text("candidate_id\tlimitations\nX\t\n", encoding="utf-8")
    with pytest.raises(handoff.NB02HandoffError, match="non-empty"):
        handoff.load_limitations(tmp_path)


# ------------------------------------------------------------------ the two separate lists
@needs_handoff
def test_the_benchmark_is_reference_set_and_never_a_recommended_candidate(rows):
    benchmark = next(row for row in rows if row["candidate_id"] == BENCHMARK)
    assert benchmark["list_membership"] == handoff.REFERENCE_SET
    assert benchmark["candidate_class"] == "PUBLISHED_EXPERIMENTAL_BENCHMARK"
    assert (benchmark["cds_start"], benchmark["cds_end"], benchmark["length_nt"]) == ("814", "1143", "330")
    assert benchmark["review_decision"] == "NOT_APPLICABLE_REFERENCE_SET"
    assert benchmark["experimental_protocol_verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"
    assert benchmark["benchmark_sequence_verification"] == "VERIFIED_FROM_SUPPLEMENT_AND_REFERENCE"
    assert BENCHMARK not in [row["candidate_id"] for row in rows if row["list_membership"] == handoff.RECOMMENDED]


@needs_handoff
def test_exactly_the_two_reviewed_candidates_are_recommended(rows):
    recommended = [row["candidate_id"] for row in rows if row["list_membership"] == handoff.RECOMMENDED]
    assert tuple(recommended) == RECOMMENDED_IDS
    assert len(recommended) == 2  # no candidate from the one-variant group was added to lengthen the list
    for row in rows:
        if row["list_membership"] == handoff.RECOMMENDED:
            assert row["n_variant_sites"] == "0" and row["length_nt"] == "400"
            assert row["review_decision"] == "APPROVED" and row["review_scope"] == "OTHER_TRANSCRIPT"
            assert row["review_reviewer"] and len(row["review_evidence_sha256"]) == 64
            assert "longest_exact=0" in row["dsrnase1_specificity_clipped"]
            assert row["other_transcript_exact_19mer_count_clipped"] == "0"
            assert row["other_transcript_exact_21mer_count_clipped"] == "0"


@needs_handoff
def test_every_sequence_matches_its_hash_and_the_operational_reference(rows):
    from zeaguard import nb02_reference

    cds = nb02_reference.verified_reference(ROOT)["operational_cds"] if HAS_CP3 else None
    for row in rows:
        assert hashlib.sha256(row["sequence"].encode()).hexdigest() == row["sequence_sha256"]
        assert len(row["sequence"]) == int(row["length_nt"])
        assert row["reference_accession"] == "GITV01008430.1"
        if cds is not None:
            assert cds[int(row["cds_start"]) - 1 : int(row["cds_end"])] == row["sequence"]


@needs_handoff
def test_the_fasta_matches_the_tsv_in_order_sequence_and_membership(rows):
    text = (ROOT / handoff.HANDOFF_FASTA).read_text(encoding="ascii")
    records = [block.split("\n", 1) for block in text.split(">")[1:]]
    assert [header.split()[0] for header, _ in records] == [row["candidate_id"] for row in rows]
    for (header, sequence), row in zip(records, rows):
        assert sequence.strip() == row["sequence"]
        assert row["list_membership"] in header and "sense_strand" in header
        assert row["sequence_sha256"] in header
    assert "T7" not in text and "primer" not in text.lower()


# ------------------------------------------------------------------ convergence with the benchmark
@needs_handoff
def test_the_convergence_is_recorded_and_declared_outside_the_ranking(rows):
    by_id = {row["candidate_id"]: row for row in rows}
    assert by_id["D2-L400-0817-1216"]["overlap_with_benchmark_nt"] == "327"
    assert by_id["D2-L400-0817-1216"]["converges_with_benchmark"] == "True"
    assert by_id["D2-L400-0351-0750"]["overlap_with_benchmark_nt"] == "0"
    assert by_id["D2-L400-0351-0750"]["converges_with_benchmark"] == "False"
    assert all(row["convergence_participated_in_ranking"] == "False" for row in rows)


# ------------------------------------------------------------------ the mandatory-review gate still guards the hand-off
@needs_cp3
def test_the_handoff_refuses_to_close_without_the_versioned_review(tmp_path, monkeypatch):
    empty = tmp_path / "no_decisions.tsv"
    empty.write_text("\t".join(crit.DECISION_COLUMNS) + "\n", encoding="utf-8")
    monkeypatch.setattr(crit, "REVIEW_DECISIONS_PATH", empty.relative_to(tmp_path))
    monkeypatch.setattr(handoff.nb02_criteria, "REVIEW_DECISIONS_PATH", empty)
    with pytest.raises(crit.NB02ReviewError, match="RECOMMENDED_SHORTLIST"):
        handoff.run_cp5(ROOT, tmp_path / "out")


@needs_cp3
def test_closing_the_handoff_is_deterministic_and_records_its_inputs(tmp_path):
    first = handoff.run_cp5(ROOT, tmp_path / "a")["manifest"]
    second = handoff.run_cp5(ROOT, tmp_path / "b")["manifest"]
    assert first["outputs_sha256"] == second["outputs_sha256"]
    assert first["lists"][handoff.RECOMMENDED] == list(RECOMMENDED_IDS)
    assert first["inputs"]["criteria_registry_sha256"] == crit.registry_sha256(ROOT / crit.REGISTRY_PATH)
    assert len(first["inputs"]["review_decisions_sha256"]) == 64
    assert "ecological off-target against non-target organisms" in first["out_of_scope"]
