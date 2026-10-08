"""NB03 CP0, part 2: discovery of BicC-like records in the TSA, before any window exists.

BLASTn (operational CDS) and TBLASTN (operational protein) against the whole D. maidis TSA, at the detection
limit already declared for NB02 (C17: word size 11, E-value report limit 10, both strands, no subject or
HSP dropped; TBLASTN uses the same E-value limit and ``-seg no``). These are limits of DETECTION, not
biological criteria: every reported hit is in the all-records table.

Which records get an ORF and a targeted protein comparison is a workload rule fixed here, before the
results were seen: the records whose TBLASTN HSPs cover at least half of the BicC protein (union of query
positions), plus ``GITV01002238.1`` (the BicC-like record found by the NB02 positive control). It is an
INSPECTION rule, not a biological one. No BLASTp is run against the translated TSA.

Nothing is classified: ``GITV01002238.1`` and every other BicC-like record keep ``relationship_status =
UNRESOLVED``; ``PARALOG`` is never written. Unit membership is only PROPOSED here and frozen at CP1.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from zeaguard import nb01_identity, nb02_criteria, nb02_reference, nb02_specificity, nb03_reference
from zeaguard.nb01_dsrnase_investigation import (
    BLAST_OUTFMT_FIELDS, CommandLog, Hsp, parse_hsp_table, union_length, write_tsv,
)

TBLASTN_FIELDS = ("qseqid sseqid pident length qlen slen qstart qend sstart send sframe evalue bitscore "
                  "mismatch gapopen gaps qcovs").split()
BLASTP_FIELDS = "qseqid sseqid pident length qlen slen qstart qend sstart send evalue bitscore mismatch gaps qcovs".split()
FOLLOW_UP_MIN_PROTEIN_COVERAGE = 0.5  # INSPECTION rule (workload), not a biological threshold
NB02_POSITIVE_CONTROL_RECORD = "GITV01002238.1"
SAME_SEQUENCE_REVIEW_IDENTITY = 98.0  # min_identity of the NB01 RESOLVED_HIGH_CONFIDENCE criterion; used only to flag for review

UNIT_KNOWN = "KNOWN_BICC_COMPATIBLE"
UNIT_LIKE = "BICC_LIKE"
STATUS_UNRESOLVED = "UNRESOLVED"
FORBIDDEN_LABELS = ("PARALOG",)  # never written by CP0

ALL_COLUMNS = (
    "accession", "record_length", "found_by",
    "blastn_n_hsps", "blastn_covered_cds_nt", "blastn_covered_cds_fraction", "blastn_best_alignment_length",
    "blastn_best_identity_percent", "blastn_best_evalue", "blastn_best_bitscore", "blastn_best_query_start",
    "blastn_best_query_end", "blastn_best_subject_start", "blastn_best_subject_end", "blastn_best_subject_strand",
    "tblastn_n_hsps", "tblastn_covered_protein_aa", "tblastn_covered_protein_fraction", "tblastn_best_alignment_length_aa",
    "tblastn_best_identity_percent", "tblastn_best_evalue", "tblastn_best_bitscore", "tblastn_best_query_start",
    "tblastn_best_query_end", "tblastn_best_subject_start", "tblastn_best_subject_end", "tblastn_best_frame",
    "followed_up", "orf_evidence", "unit_proposal", "relationship_status", "proposal_basis",
)
FOLLOW_UP_COLUMNS = (
    "accession", "record_length", "orf_strand", "orf_tx_start", "orf_tx_end", "orf_length_nt", "orf_protein_length_aa",
    "orf_starts_with_met", "orf_overlap_with_best_tblastn_hsp_nt", "blastp_identity_percent", "blastp_alignment_length_aa",
    "blastp_query_coverage_percent", "blastp_evalue", "blastp_bitscore", "identical_residues_over_bicc_protein_length",
    "unit_proposal", "relationship_status", "review_flag",
)


class NB03DiscoveryError(RuntimeError):
    """The discovery cannot be produced as declared."""


def search_settings(root: Path) -> dict[str, Any]:
    """The NB02 C17 detection limit, read from the registry instead of restated."""
    registry = nb02_criteria.load_registry(Path(root))
    return dict(next(c for c in registry["criteria"] if c["name"] == "search_detection_limit")["threshold"])


def build_database(root: Path, out: Path, log: CommandLog) -> dict[str, Any]:
    """Nucleotide database of every TSA record under its plain accession."""
    tsa_path, tsa_sha = nb02_reference.validated_tsa_path(root)
    db_dir = out / "blastdb"
    db_dir.mkdir(parents=True, exist_ok=True)
    fasta = db_dir / "tsa.fasta"
    n = 0
    with fasta.open("w", encoding="ascii", newline="\n") as handle:
        for record in nb01_identity.parse_fasta(tsa_path):
            handle.write(f">{nb01_identity.canonical_tsa_accession(record.identifier)}\n{record.sequence}\n")
            n += 1
    database = db_dir / "nb03_cp0_tsa"
    log.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-out", str(database), "-title", "nb03_cp0_tsa"])
    info = log.run(["blastdbcmd", "-db", str(database), "-info"])
    match = re.search(r"([\d,]+) sequences; ([\d,]+) total bases", info)
    return {"database": str(database), "tsa_file_sha256": tsa_sha, "n_tsa_records": n,
            "fasta_sha256": hashlib.sha256(fasta.read_bytes()).hexdigest(),
            "n_sequences": int(match.group(1).replace(",", "")) if match else None,
            "total_bases": int(match.group(2).replace(",", "")) if match else None}


def run_searches(cds: str, protein: str, database: str, search: dict[str, Any], out: Path, log: CommandLog) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "bicc_cds.fasta").write_text(f">bicc_operational_cds\n{cds}\n", encoding="ascii", newline="\n")
    (out / "bicc_protein.fasta").write_text(f">bicc_operational_protein\n{protein}\n", encoding="ascii", newline="\n")
    blastn = ["blastn", "-query", str(out / "bicc_cds.fasta"), "-db", database, *nb02_specificity.blastn_arguments(search),
              "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)]
    blastn_text = log.run(blastn, stdout_path=out / "blastn_raw.outfmt6.tsv")
    tblastn = ["tblastn", "-query", str(out / "bicc_protein.fasta"), "-db", database, "-evalue", str(search["evalue_report_limit"]),
               "-seg", "no", "-max_target_seqs", str(search["max_target_seqs"]), "-num_threads", "1",
               "-outfmt", "6 " + " ".join(TBLASTN_FIELDS)]
    tblastn_text = log.run(tblastn, stdout_path=out / "tblastn_raw.outfmt6.tsv")
    return {"blastn": parse_hsp_table(blastn_text), "tblastn": parse_tblastn(tblastn_text),
            "blastn_command": " ".join(blastn), "tblastn_command": " ".join(tblastn)}


def parse_tblastn(text: str) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != len(TBLASTN_FIELDS):
            raise NB03DiscoveryError(f"TBLASTN line has {len(cells)} fields, expected {len(TBLASTN_FIELDS)}")
        row = dict(zip(TBLASTN_FIELDS, cells))
        for key in ("length", "qlen", "slen", "qstart", "qend", "sstart", "send", "sframe", "mismatch", "gapopen", "gaps"):
            row[key] = int(row[key])
        for key in ("pident", "evalue", "bitscore", "qcovs"):
            row[key] = float(row[key])
        rows.append(row)
    return rows


def _best(items: Iterable[Any], score) -> Any:
    return max(items, key=score)


def summarise_records(blastn: list[Hsp], tblastn: list[dict[str, Any]], cds_length: int, protein_length: int) -> list[dict[str, Any]]:
    """One row per subject found by either search; every reported hit counts, nothing is filtered."""
    by_n: dict[str, list[Hsp]] = {}
    by_t: dict[str, list[dict[str, Any]]] = {}
    for h in blastn:
        by_n.setdefault(h.subject, []).append(h)
    for r in tblastn:
        by_t.setdefault(r["sseqid"], []).append(r)
    rows: list[dict[str, Any]] = []
    for accession in sorted(set(by_n) | set(by_t)):
        n_hsps, t_hsps = by_n.get(accession, []), by_t.get(accession, [])
        row: dict[str, Any] = {c: "" for c in ALL_COLUMNS}
        row["accession"] = accession
        row["record_length"] = (n_hsps[0].slen if n_hsps else t_hsps[0]["slen"])
        row["found_by"] = "BOTH" if n_hsps and t_hsps else ("BLASTN" if n_hsps else "TBLASTN")
        if n_hsps:
            best = _best(n_hsps, lambda h: (h.bitscore, h.length))
            covered = union_length(h.query_interval for h in n_hsps)
            row.update({
                "blastn_n_hsps": len(n_hsps), "blastn_covered_cds_nt": covered,
                "blastn_covered_cds_fraction": round(covered / cds_length, 6), "blastn_best_alignment_length": best.length,
                "blastn_best_identity_percent": best.pident, "blastn_best_evalue": best.evalue, "blastn_best_bitscore": best.bitscore,
                "blastn_best_query_start": best.qstart, "blastn_best_query_end": best.qend,
                "blastn_best_subject_start": best.sstart, "blastn_best_subject_end": best.send,
                "blastn_best_subject_strand": best.strand,
            })
        if t_hsps:
            best_t = _best(t_hsps, lambda r: (r["bitscore"], r["length"]))
            covered_t = union_length((min(r["qstart"], r["qend"]), max(r["qstart"], r["qend"])) for r in t_hsps)
            row.update({
                "tblastn_n_hsps": len(t_hsps), "tblastn_covered_protein_aa": covered_t,
                "tblastn_covered_protein_fraction": round(covered_t / protein_length, 6),
                "tblastn_best_alignment_length_aa": best_t["length"], "tblastn_best_identity_percent": best_t["pident"],
                "tblastn_best_evalue": best_t["evalue"], "tblastn_best_bitscore": best_t["bitscore"],
                "tblastn_best_query_start": best_t["qstart"], "tblastn_best_query_end": best_t["qend"],
                "tblastn_best_subject_start": best_t["sstart"], "tblastn_best_subject_end": best_t["send"],
                "tblastn_best_frame": best_t["sframe"],
            })
        row.update({"followed_up": False, "orf_evidence": "NOT_EXAMINED", "unit_proposal": "NOT_PROPOSED",
                    "relationship_status": "", "proposal_basis": ""})
        rows.append(row)
    rows.sort(key=lambda r: (-(r["tblastn_covered_protein_fraction"] or 0), -(r["blastn_covered_cds_fraction"] or 0), r["accession"]))
    return rows


def select_follow_up(rows: list[dict[str, Any]], operational_accession: str) -> list[str]:
    """Pre-registered inspection rule (see the module docstring)."""
    chosen = {r["accession"] for r in rows if (r["tblastn_covered_protein_fraction"] or 0) >= FOLLOW_UP_MIN_PROTEIN_COVERAGE}
    chosen |= {operational_accession, NB02_POSITIVE_CONTROL_RECORD} & {r["accession"] for r in rows}
    return sorted(chosen)


def best_orf_for_hsp(sequence: str, hsp: dict[str, Any]) -> dict[str, Any] | None:
    """The complete ORF on the HSP's strand with the largest overlap with the HSP subject interval (stored coordinates)."""
    strand = "+" if hsp["sframe"] > 0 else "-"
    lo, hi = min(hsp["sstart"], hsp["send"]), max(hsp["sstart"], hsp["send"])
    candidates = []
    for orf in nb03_reference.find_orfs(sequence):
        if orf["strand"] != strand:
            continue
        overlap = min(hi, orf["cds_tx_end"]) - max(lo, orf["cds_tx_start"]) + 1
        if overlap > 0:
            candidates.append((overlap, orf["length_nt"], orf))
    if not candidates:
        return None
    overlap, _, orf = max(candidates, key=lambda c: (c[0], c[1]))
    return {**orf, "overlap_nt": overlap}


def follow_up(root: Path, rows: list[dict[str, Any]], tblastn: list[dict[str, Any]], bicc_protein: str, accessions: list[str],
              operational_accession: str, out: Path, log: CommandLog) -> list[dict[str, Any]]:
    """ORF and targeted protein comparison for the selected records only."""
    sequences, _ = nb02_reference.tsa_sequences(Path(root), set(accessions))
    by_row = {r["accession"]: r for r in rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / "bicc_protein.fasta").write_text(f">bicc_operational_protein\n{bicc_protein}\n", encoding="ascii", newline="\n")
    results: list[dict[str, Any]] = []
    for accession in accessions:
        row = by_row[accession]
        record = {c: "" for c in FOLLOW_UP_COLUMNS}
        record.update({"accession": accession, "record_length": len(sequences[accession])})
        hsps = [r for r in tblastn if r["sseqid"] == accession]
        best = max(hsps, key=lambda r: (r["bitscore"], r["length"])) if hsps else None
        orf = best_orf_for_hsp(sequences[accession], best) if best else None
        if orf is None:
            record["review_flag"] = "NO_COMPLETE_ORF_OVERLAPPING_THE_BEST_TBLASTN_HSP"
            row["orf_evidence"] = record["review_flag"]
        else:
            cds = nb02_reference.extract_cds(sequences[accession], orf["strand"], orf["cds_tx_start"], orf["cds_tx_end"])
            protein = nb03_reference.translate(cds, to_stop=True)
            fasta = out / f"orf_{accession}.fasta"
            fasta.write_text(f">{accession}_orf\n{protein}\n", encoding="ascii", newline="\n")
            text = log.run(["blastp", "-query", str(out / "bicc_protein.fasta"), "-subject", str(fasta), "-evalue", "10",
                            "-outfmt", "6 " + " ".join(BLASTP_FIELDS)], stdout_path=out / f"blastp_{accession}.outfmt6.tsv")
            hits = [dict(zip(BLASTP_FIELDS, line.split("\t"))) for line in text.splitlines() if line.strip()]
            top = max(hits, key=lambda h: float(h["bitscore"])) if hits else None
            identical = round(float(top["pident"]) / 100 * int(top["length"])) if top else 0
            record.update({
                "orf_strand": orf["strand"], "orf_tx_start": orf["cds_tx_start"], "orf_tx_end": orf["cds_tx_end"],
                "orf_length_nt": orf["length_nt"], "orf_protein_length_aa": len(protein), "orf_starts_with_met": cds.startswith("ATG"),
                "orf_overlap_with_best_tblastn_hsp_nt": orf["overlap_nt"],
                "blastp_identity_percent": top["pident"] if top else "", "blastp_alignment_length_aa": top["length"] if top else "",
                "blastp_query_coverage_percent": top["qcovs"] if top else "", "blastp_evalue": top["evalue"] if top else "",
                "blastp_bitscore": top["bitscore"] if top else "",
                "identical_residues_over_bicc_protein_length": round(identical / len(bicc_protein), 6),
            })
            row["orf_evidence"] = f"ORF_{len(protein)}aa_strand{orf['strand']}_{orf['cds_tx_start']}-{orf['cds_tx_end']}"
        record.update(_proposal(accession, operational_accession, row))
        row.update({"followed_up": True, "unit_proposal": record["unit_proposal"],
                    "relationship_status": record["relationship_status"], "proposal_basis": record["_basis"]})
        record["review_flag"] = record["review_flag"] or record.pop("_flag", "")
        record.pop("_basis", None)
        record.pop("_flag", None)
        results.append(record)
    return results


def _proposal(accession: str, operational_accession: str, row: dict[str, Any]) -> dict[str, Any]:
    """Unit PROPOSAL only; nothing is frozen, and nothing is called a paralog."""
    if accession == operational_accession:
        return {"unit_proposal": UNIT_KNOWN, "relationship_status": "NOT_APPLICABLE",
                "_basis": "operational reference (NB01 RESOLVED_HIGH_CONFIDENCE, re-derived at CP0)", "_flag": ""}
    identity = row["blastn_best_identity_percent"]
    flag = ""
    if identity != "" and float(identity) >= SAME_SEQUENCE_REVIEW_IDENTITY:
        flag = "REVIEW_AS_SAME_LOCUS_CANDIDATE: BLASTn best HSP identity >= the NB01 high-confidence identity criterion"
    basis = ("found by the NB02 positive control as BicC-like; similarity to BicC at nucleotide and protein level; relation unresolved"
             if accession == NB02_POSITIVE_CONTROL_RECORD else "BicC-like by the pre-registered inspection rule; relation unresolved")
    return {"unit_proposal": UNIT_LIKE if not flag else f"{UNIT_LIKE}_OR_{UNIT_KNOWN}_PENDING_REVIEW", "relationship_status": STATUS_UNRESOLVED,
            "_basis": basis, "_flag": flag}


def assert_no_paralog_label(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        for value in row.values():
            if isinstance(value, str) and any(label in value.upper() for label in FORBIDDEN_LABELS):
                raise NB03DiscoveryError(f"CP0 may not write {FORBIDDEN_LABELS}: {value!r}")


def write_tables(out: Path, rows: list[dict[str, Any]], followed: list[dict[str, Any]]) -> dict[str, Path]:
    assert_no_paralog_label(rows)
    assert_no_paralog_label(followed)
    relevant = [r for r in rows if r["followed_up"]]
    paths = {"bicc_like_discovery_all_records.tsv": (rows, ALL_COLUMNS), "bicc_like_discovery.tsv": (relevant, ALL_COLUMNS),
             "bicc_like_followup.tsv": (followed, FOLLOW_UP_COLUMNS)}
    written = {}
    for name, (table, columns) in paths.items():
        write_tsv(out / name, table, columns)
        written[name] = out / name
    return written
