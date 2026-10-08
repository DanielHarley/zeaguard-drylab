"""NB03 CP0, part 1: the BicC operational reference, re-derived from the hash-validated TSA.

Nothing here trusts a value written down elsewhere. The operational record is found in the TSA by
accession, its CDS is the longest complete ORF over both strands, and the published cDNA
(``TRINITY_DN24799_c0_g1_i7``, stored in the versioned anchor FASTA) is placed on it by a pairwise BLASTn
whose BTOP gives an exact position map. The only publication-local numbers used (2655 bp cDNA, 778 aa
protein) are read from ``data/reference/target_anchors.tsv`` and only as a cross-check.

Differences between the published CDS and the operational CDS are called ``observed_sequence_differences``.
Their nature (polymorphism, isoform, assembly difference, sequencing error, other) is unresolved and
no read support was assessed at CP0, so no output may classify them as anything more specific.

Coordinates: 1-based inclusive. ``cds_tx_*`` are on the stored strand of the record; every ``cds_pos`` is
on the CDS in coding (sense) orientation.
"""

from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Any, Sequence

from zeaguard import nb01_identity, nb02_reference
from zeaguard.nb01_dsrnase_investigation import (
    BLAST_OUTFMT_FIELDS, STOP, CommandLog, Hsp, codon_amino_acids, parse_hsp_table, sha256_text, translate,
)
from zeaguard.nb02_specificity import btop_columns

OPERATIONAL_ACCESSION = "GITV01000968.1"
PUBLISHED_ID = "TRINITY_DN24799_c0_g1_i7"
OUTPUT_DIR = Path("results/bioinformatics/nb03/cp0")
READ_SUPPORT_STATUS = "NOT_ASSESSED_FOR_NB03_CP0"
STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})

DIFFERENCE_COLUMNS = (
    "cds_position", "published_base", "operational_base", "published_codon", "operational_codon",
    "codon_position", "codon_index", "published_amino_acid", "operational_amino_acid",
    "synonymous_status", "substitution_class", "read_support_status",
)
# Words that would claim a nature for the differences. Only documentation may use them, and only to say it was not established.
FORBIDDEN_NATURE_TERMS = ("variant", "allele", "polymorph")
_PURINES, _PYRIMIDINES = frozenset("AG"), frozenset("CT")


class NB03ReferenceError(RuntimeError):
    """The BicC reference cannot be re-derived as required."""


# --------------------------------------------------------------------------- ORFs and records
def find_orfs(sequence: str) -> list[dict[str, Any]]:
    """Every complete ATG-to-stop ORF on both strands, longest first, with stored-strand coordinates.

    ORFs are maximal in the sense that scanning resumes after the stop, so a nested ATG is never reported.
    """
    sequence = sequence.upper()
    n = len(sequence)
    found: list[dict[str, Any]] = []
    for strand, oriented in (("+", sequence), ("-", nb01_identity.reverse_complement(sequence))):
        for frame in range(3):
            i = frame
            while i + 3 <= n:
                if oriented[i : i + 3] != "ATG":
                    i += 3
                    continue
                j = i
                while j + 3 <= n and oriented[j : j + 3] not in STOP_CODONS:
                    j += 3
                if j + 3 > n:  # no stop before the end of the record: not a complete ORF
                    break
                start, end = (i + 1, j + 3) if strand == "+" else (n - (j + 3) + 1, n - i)
                found.append({"strand": strand, "frame": frame, "cds_tx_start": start, "cds_tx_end": end,
                              "length_nt": j + 3 - i})
                i = j + 3
    return sorted(found, key=lambda o: (-o["length_nt"], o["strand"], o["cds_tx_start"]))


def derive_record(accession: str, sequence: str) -> dict[str, Any]:
    """CDS = the longest complete ORF; strictly the longest (a tie is a contract error)."""
    sequence = sequence.upper()
    orfs = find_orfs(sequence)
    if not orfs:
        raise NB03ReferenceError(f"{accession}: no complete ORF")
    if len(orfs) > 1 and orfs[0]["length_nt"] == orfs[1]["length_nt"]:
        raise NB03ReferenceError(f"{accession}: the longest ORF is not unique")
    top = orfs[0]
    cds = nb02_reference.extract_cds(sequence, top["strand"], top["cds_tx_start"], top["cds_tx_end"])
    protein = translate(cds, to_stop=True)
    if not (cds.startswith("ATG") and translate(cds[-3:]) == STOP):
        raise NB03ReferenceError(f"{accession}: CDS is not ATG...stop")
    n = len(sequence)
    if top["strand"] == "+":
        utr5, utr3 = top["cds_tx_start"] - 1, n - top["cds_tx_end"]
    else:
        utr5, utr3 = n - top["cds_tx_end"], top["cds_tx_start"] - 1
    inside = lambda p: top["cds_tx_start"] <= p <= top["cds_tx_end"]  # noqa: E731
    iupac = [{"record_position": p + 1, "symbol": base,
              "region": "CDS" if inside(p + 1) else "UTR"} for p, base in enumerate(sequence) if base not in "ACGT"]
    return {
        "accession": accession, "record_length": n, "record_sha256": sha256_text(sequence),
        "strand": top["strand"], "cds_tx_start": top["cds_tx_start"], "cds_tx_end": top["cds_tx_end"],
        "cds_length": len(cds), "cds_sha256": sha256_text(cds), "protein_length": len(protein),
        "protein_sha256": sha256_text(protein), "utr5_length": utr5, "utr3_length": utr3,
        "iupac_positions": iupac, "second_longest_orf_nt": orfs[1]["length_nt"] if len(orfs) > 1 else None,
        "_cds": cds, "_protein": protein,
    }


def load_published(root: Path) -> tuple[str, dict[str, Any]]:
    """Published BicC cDNA as stored, and the publication-local figures documented in the anchor table."""
    stored = next((r.sequence for r in nb01_identity.parse_fasta(Path(root) / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH)
                   if r.identifier == PUBLISHED_ID), None)
    if stored is None:
        raise NB03ReferenceError(f"{PUBLISHED_ID} is absent from the versioned anchor FASTA")
    with (Path(root) / nb01_identity.DEFAULT_ANCHOR_PATH).open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle, delimiter="\t") if r["published_transcript_id"] == PUBLISHED_ID]
    if len(rows) != 1:
        raise NB03ReferenceError("the anchor table must hold exactly one BicC row")
    match = re.search(r"(\d+) bp full-length cDNA encoding a predicted (\d+) amino acid", rows[0]["documented_features"])
    if match is None:
        raise NB03ReferenceError("the anchor table does not state the cDNA and protein lengths")
    return stored, {"cdna_length": int(match.group(1)), "protein_length": int(match.group(2))}


def tsa_record(root: Path) -> tuple[str, str]:
    found, tsa_sha = nb02_reference.tsa_sequences(Path(root), {OPERATIONAL_ACCESSION})
    return found[OPERATIONAL_ACCESSION], tsa_sha


# --------------------------------------------------------------------------- placement of the published cDNA on the record
def position_map(hsp: Hsp) -> dict[int, int | None]:
    """Query position -> subject position along one HSP (``None`` for a query base against a subject gap)."""
    mapping: dict[int, int | None] = {}
    q, s = min(hsp.qstart, hsp.qend), hsp.sstart
    step = -1 if hsp.strand == "minus" else 1
    for query_char, subject_char in btop_columns(hsp.btop):
        if query_char == "-":  # subject base against a query gap: only the subject advances
            s += step
            continue
        if subject_char == "-":
            mapping[q] = None
            q += 1
            continue
        mapping[q] = s
        q += 1
        s += step
    if q - 1 != max(hsp.qstart, hsp.qend):
        raise NB03ReferenceError("BTOP does not span the HSP query interval")
    return mapping


def place_published(stored: str, record: str, workdir: Path, log: CommandLog) -> dict[str, Any]:
    """Pairwise BLASTn of the stored published cDNA against the record; the single HSP that spans the most query."""
    workdir.mkdir(parents=True, exist_ok=True)
    query, subject = workdir / "published_cdna.fasta", workdir / "operational_record.fasta"
    query.write_text(f">{PUBLISHED_ID}\n{stored}\n", encoding="ascii", newline="\n")
    subject.write_text(f">{OPERATIONAL_ACCESSION}\n{record}\n", encoding="ascii", newline="\n")
    command = ["blastn", "-task", "blastn", "-dust", "no", "-word_size", "11", "-evalue", "10", "-strand", "both",
               "-query", str(query), "-subject", str(subject), "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)]
    hsps = parse_hsp_table(log.run(command, stdout_path=workdir / "published_vs_record.outfmt6.tsv"))
    if not hsps:
        raise NB03ReferenceError("the published cDNA does not align to the operational record")
    best = max(hsps, key=lambda h: (h.qend - h.qstart + 1, h.bitscore))
    return {"n_hsps": len(hsps), "hsp": best, "map": position_map(best),
            "other_hsps": [(h.qstart, h.qend, h.sstart, h.send) for h in hsps if h is not best]}


# --------------------------------------------------------------------------- observed_sequence_differences
def observed_sequence_differences(published_cds: str, operational_cds: str) -> list[dict[str, Any]]:
    """Positions where the two CDS differ. Only equal-length (indel-free) CDS are supported at CP0."""
    if len(published_cds) != len(operational_cds):
        raise NB03ReferenceError("CDS lengths differ; CP0 only describes indel-free CDS pairs")
    rows: list[dict[str, Any]] = []
    for index, (pub, op) in enumerate(zip(published_cds, operational_cds)):
        if pub == op:
            continue
        start = index - index % 3
        pub_codon, op_codon = published_cds[start : start + 3], operational_cds[start : start + 3]
        pub_aa, op_aa = (_one_aa(pub_codon), _one_aa(op_codon))
        if pub in "ACGT" and op in "ACGT":
            klass = "TRANSITION" if ({pub, op} <= _PURINES or {pub, op} <= _PYRIMIDINES) else "TRANSVERSION"
            status = "SYNONYMOUS" if pub_aa == op_aa else "NONSYNONYMOUS"
        else:
            klass, status = "INVOLVES_AMBIGUITY_CODE", "NOT_DETERMINED"
        rows.append({
            "cds_position": index + 1, "published_base": pub, "operational_base": op,
            "published_codon": pub_codon, "operational_codon": op_codon, "codon_position": index % 3 + 1,
            "codon_index": index // 3 + 1, "published_amino_acid": pub_aa, "operational_amino_acid": op_aa,
            "synonymous_status": status, "substitution_class": klass, "read_support_status": READ_SUPPORT_STATUS,
        })
    return rows


def _one_aa(codon: str) -> str:
    options = codon_amino_acids(codon)
    return next(iter(options)) if len(options) == 1 else "X"


def assert_descriptive_columns(columns: Sequence[str]) -> None:
    offenders = [c for c in columns if any(term in c.lower() for term in FORBIDDEN_NATURE_TERMS)]
    if offenders:
        raise NB03ReferenceError(f"columns may not name the nature of the differences: {offenders}")


# --------------------------------------------------------------------------- coordinate conversions
def stored_to_sense(position: int, length: int) -> int:
    """Position on the stored (antisense) cDNA -> position on its reverse complement (the transcript sense)."""
    return length - position + 1


def cds_to_record(cds_pos: int, record: dict[str, Any]) -> int:
    if record["strand"] == "+":
        return record["cds_tx_start"] + cds_pos - 1
    return record["cds_tx_end"] - cds_pos + 1


def design_domain(operational: dict[str, Any]) -> tuple[int, int]:
    """New candidates live only inside the operational CDS; a benchmark in a UTR never widens this."""
    return 1, operational["cds_length"]


def sense_to_cds(sense_pos: int, utr5_length: int) -> int:
    """1-based position in the sense transcript -> CDS position (<= 0 is 5' UTR, > cds_length is 3' UTR)."""
    return sense_pos - utr5_length


def _sense_strand_on_record(hsp_strand: str, stored_cds_strand: str) -> str:
    """Strand of the record that carries the published transcript in sense orientation."""
    on_record = "+" if hsp_strand == "plus" else "-"
    if stored_cds_strand == "+":
        return on_record
    return "-" if on_record == "+" else "+"


# --------------------------------------------------------------------------- the CP0 reference summary
def derive_reference(root: Path, workdir: Path, log: CommandLog) -> dict[str, Any]:
    """Re-derive the operational record, the published cDNA, their placement and the observed differences."""
    root = Path(root).resolve()
    record_sequence, tsa_sha = tsa_record(root)
    operational = derive_record(OPERATIONAL_ACCESSION, record_sequence)
    stored, documented = load_published(root)
    published = derive_record(PUBLISHED_ID, stored)
    # The CDS must be on the opposite strand of the stored cDNA for the published figures to refer to it.
    orientation = ("STORED_ANTISENSE_REVERSE_COMPLEMENT_OF_CODING" if published["strand"] == "-"
                   else "STORED_SENSE")
    sense = nb01_identity.reverse_complement(stored) if published["strand"] == "-" else stored
    placement = place_published(stored, record_sequence, workdir, log)
    differences = observed_sequence_differences(published["_cds"], operational["_cds"])
    assert_descriptive_columns(DIFFERENCE_COLUMNS)

    published_cds_start_in_sense = published["utr5_length"] + 1
    hsp: Hsp = placement["hsp"]
    sense_to_record = {}
    # published stored position -> record position (through BTOP); sense position uses the reverse complement
    mapped = placement["map"]
    for stored_pos, record_pos in mapped.items():
        sense_to_record[stored_to_sense(stored_pos, len(stored))] = record_pos
    # Independent route: the CDS offset. They must agree wherever the transcript aligned inside the CDS.
    cds_routes_disagree = [
        cds_pos for cds_pos in range(1, operational["cds_length"] + 1)
        if sense_to_record.get(published_cds_start_in_sense + cds_pos - 1) != cds_to_record(cds_pos, operational)
    ]
    checks = {
        "published_cdna_length_matches_anchor_table": len(stored) == documented["cdna_length"],
        "published_protein_length_matches_anchor_table": published["protein_length"] == documented["protein_length"],
        "operational_protein_length_matches_anchor_table": operational["protein_length"] == documented["protein_length"],
        "published_and_operational_cds_same_length": published["cds_length"] == operational["cds_length"],
        "cds_position_routes_agree": not cds_routes_disagree,
    }
    record_positions = [p for p in sense_to_record.values() if p is not None]
    summary = {
        "tsa_file_sha256": tsa_sha,
        "operational": {k: v for k, v in operational.items() if not k.startswith("_")},
        "published": {
            **{k: v for k, v in published.items() if not k.startswith("_")},
            "stored_orientation": orientation, "stored_length": len(stored), "stored_sha256": sha256_text(stored),
            "sense_sha256": sha256_text(sense), "documented_in_anchor_table": documented,
            "cds_start_in_sense": published_cds_start_in_sense,
            "cds_end_in_sense": published_cds_start_in_sense + published["cds_length"] - 1,
        },
        "placement_on_operational_record": {
            "method": "pairwise blastn (query published cDNA as stored, subject operational record), best-spanning HSP",
            "n_hsps": placement["n_hsps"], "other_hsps_qstart_qend_sstart_send": placement["other_hsps"],
            "qstart": hsp.qstart, "qend": hsp.qend, "sstart": hsp.sstart, "send": hsp.send, "subject_strand": hsp.strand,
            "alignment_length": hsp.length, "identity_percent": hsp.pident, "mismatch": hsp.mismatch, "gaps": hsp.gaps,
            "published_transcript_span_on_record": [min(record_positions), max(record_positions)],
            "record_strand_of_published_sense": _sense_strand_on_record(hsp.strand, published["strand"]),
        },
        "cds_to_cds": {"n_observed_sequence_differences": len(differences),
                       "protein_identical": published["_protein"] == operational["_protein"]},
        "checks": checks,
        "cds_position_disagreements": cds_routes_disagree[:20],
    }
    if not all(checks.values()):
        raise NB03ReferenceError(f"reference checks failed: {[k for k, v in checks.items() if not v]}")
    return {"summary": summary, "differences": differences, "operational": operational, "published": published,
            "published_stored": stored, "published_sense": sense, "record_sequence": record_sequence,
            "sense_to_record": sense_to_record, "placement": placement}
