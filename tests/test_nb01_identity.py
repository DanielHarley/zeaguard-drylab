from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from zeaguard import nb01_identity


def record(identifier: str, sequence: str, description: str | None = None):
    return nb01_identity.FastaRecord(
        identifier,
        description or f"{identifier} synthetic record",
        sequence,
    )


def hit(
    accession: str,
    identity: float = 99.0,
    coverage: float = 99.0,
    evalue: float = 1e-40,
    bitscore: float = 500.0,
):
    return nb01_identity.BlastHit(
        query="published-query",
        tsa_accession=accession,
        identity=identity,
        alignment_length=990,
        query_length=1000,
        query_coverage=coverage,
        evalue=evalue,
        bitscore=bitscore,
    )


def test_parse_gzip_fasta(tmp_path):
    path = tmp_path / "fixture.fasta.gz"
    with gzip.open(path, "wt", encoding="ascii", newline="\n") as handle:
        handle.write(">ACC1.1 first record\nACGT\nNN\n>ACC2.1\nTTAA\n")

    parsed = tuple(nb01_identity.parse_fasta(path))

    assert parsed == (
        record("ACC1.1", "ACGTNN", "ACC1.1 first record"),
        record("ACC2.1", "TTAA", "ACC2.1"),
    )


def test_index_fasta_records_indexes_accessions_and_header_tokens():
    index = nb01_identity.index_fasta_records(
        [record("ACC1.1", "ACGT", "ACC1.1 TSA published-alias transcript")]
    )

    assert index.by_identifier["ACC1.1"].sequence == "ACGT"
    assert index.by_header_key["acc1"][0].identifier == "ACC1.1"
    assert index.by_header_key["published-alias"][0].identifier == "ACC1.1"


def test_find_direct_header_match_uses_anchor_identifier_without_hardcoding():
    index = nb01_identity.index_fasta_records(
        [
            record("ACC1.1", "ACGT", "ACC1.1 source-id retained"),
            record("ACC2.1", "TGCA"),
        ]
    )
    anchor = {
        "published_transcript_id": "source-id",
        "aliases": "published alias",
    }

    matches = nb01_identity.find_direct_header_matches(anchor, index)

    assert [match.identifier for match in matches] == ["ACC1.1"]


def test_find_exact_sequence_match_supports_forward_and_reverse_complement():
    query = "AAGTCCTA"
    records = [
        record("FORWARD.1", f"NN{query}NN"),
        record("REVERSE.1", f"NN{nb01_identity.reverse_complement(query)}NN"),
    ]

    matches = nb01_identity.find_exact_sequence_matches(query, records)

    assert [(match.record.identifier, match.method) for match in matches] == [
        ("FORWARD.1", "exact_nucleotide"),
        ("REVERSE.1", "exact_reverse_complement"),
    ]


def test_exact_sequence_matching_preserves_multiple_records():
    matches = nb01_identity.find_exact_sequence_matches(
        "AACCGG",
        [record("A.1", "TTAACCGGTT"), record("B.1", "AACCGG")],
    )

    assert [match.record.identifier for match in matches] == ["A.1", "B.1"]


def test_classify_blast_hits_marks_competitive_support_ambiguous():
    decision = nb01_identity.classify_blast_hits(
        [
            hit("A.1", identity=99.5, coverage=99.0, bitscore=500.0),
            hit("B.1", identity=99.0, coverage=98.0, bitscore=480.0),
        ]
    )

    assert decision.status == nb01_identity.AMBIGUOUS
    assert decision.competing_hits == 1
    assert [candidate.tsa_accession for candidate in decision.reported_hits] == [
        "A.1",
        "B.1",
    ]


def test_absent_exact_and_blast_matches_remain_unresolved():
    exact = nb01_identity.find_exact_sequence_matches(
        "AACCGG",
        [record("A.1", "TTTTTT")],
    )
    decision = nb01_identity.classify_blast_hits([])

    assert exact == ()
    assert decision.status == nb01_identity.UNRESOLVED
    assert decision.top_hit is None


def test_parse_blast_tabular_reads_declared_metrics():
    parsed = nb01_identity.parse_blast_tabular(
        "query-1\tgb|GITV01000001.1|\t99.125\t875\t900\t97.222\t2e-120\t1620\n"
    )

    assert parsed == (
        nb01_identity.BlastHit(
            query="query-1",
            tsa_accession="GITV01000001.1",
            identity=99.125,
            alignment_length=875,
            query_length=900,
            query_coverage=97.222,
            evalue=2e-120,
            bitscore=1620.0,
        ),
    )


@pytest.mark.parametrize(
    ("hits", "expected"),
    [
        (
            [
                hit(
                    "BOUNDARY.1",
                    identity=nb01_identity.HIGH_CONFIDENCE_MIN_IDENTITY,
                    coverage=nb01_identity.HIGH_CONFIDENCE_MIN_QUERY_COVERAGE,
                    evalue=nb01_identity.HIGH_CONFIDENCE_MAX_EVALUE,
                )
            ],
            nb01_identity.RESOLVED_HIGH_CONFIDENCE,
        ),
        (
            [
                hit(
                    "LOW_IDENTITY.1",
                    identity=nb01_identity.HIGH_CONFIDENCE_MIN_IDENTITY - 0.001,
                )
            ],
            nb01_identity.UNRESOLVED,
        ),
        (
            [
                hit("TOP.1", identity=99.0, coverage=99.0, bitscore=500.0),
                hit("DISTANT.1", identity=98.0, coverage=95.0, bitscore=470.0),
            ],
            nb01_identity.RESOLVED_HIGH_CONFIDENCE,
        ),
    ],
)
def test_resolution_thresholds_are_applied_deterministically(hits, expected):
    assert nb01_identity.classify_blast_hits(hits).status == expected
