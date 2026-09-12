"""Deterministic reconciliation of published NB01 anchors against a TSA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Iterable, Iterator, Sequence

from zeaguard import nb01_inputs


DEFAULT_ANCHOR_PATH = Path("data/reference/target_anchors.tsv")
DEFAULT_ANCHOR_SEQUENCE_PATH = Path("data/reference/target_anchor_sequences.fasta")
DEFAULT_MANIFEST_PATH = Path("data/reference/manifest.json")
DEFAULT_OUTPUT_DIR = Path("results/bioinformatics/nb01")

RESOLVED_EXACT = "RESOLVED_EXACT"
RESOLVED_HIGH_CONFIDENCE = "RESOLVED_HIGH_CONFIDENCE"
AMBIGUOUS = "AMBIGUOUS"
UNRESOLVED = "UNRESOLVED"

HIGH_CONFIDENCE_MIN_IDENTITY = 98.0
HIGH_CONFIDENCE_MIN_QUERY_COVERAGE = 95.0
HIGH_CONFIDENCE_MAX_EVALUE = 1e-20
COMPETITIVE_MIN_BITSCORE_RATIO = 0.95
COMPETITIVE_MAX_IDENTITY_DELTA = 1.0
COMPETITIVE_MAX_QUERY_COVERAGE_DELTA = 2.0
BLAST_SEARCH_MAX_EVALUE = 1e-5
BLAST_MAX_TARGET_SEQS = 100

CANDIDATE_COLUMNS = (
    "target_id",
    "published_transcript_id",
    "tsa_accession",
    "resolution_method",
    "identity",
    "query_coverage",
    "alignment_length",
    "evalue",
    "bitscore",
    "competing_hits",
    "resolution_status",
    "evidence_source",
    "notes",
)
IUPAC_DNA = frozenset("ACGTRYSWKMBDHVN")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
TSA_ACCESSION_PATTERN = re.compile(r"^[A-Z]{4}\d{8}(?:\.\d+)?$")
COMPLEMENT = str.maketrans(
    "ACGTRYKMSWBDHVN",
    "TGCAYRMKSWVHDBN",
)


class IdentityResolutionError(RuntimeError):
    """Raised when Stage 3 cannot execute with its declared inputs."""


@dataclass(frozen=True)
class FastaRecord:
    identifier: str
    description: str
    sequence: str


@dataclass(frozen=True)
class FastaIndex:
    records: tuple[FastaRecord, ...]
    by_identifier: dict[str, FastaRecord]
    by_header_key: dict[str, tuple[FastaRecord, ...]]


@dataclass(frozen=True)
class ExactMatch:
    record: FastaRecord
    method: str


@dataclass(frozen=True)
class BlastHit:
    query: str
    tsa_accession: str
    identity: float
    alignment_length: int
    query_length: int
    query_coverage: float
    evalue: float
    bitscore: float


@dataclass(frozen=True)
class BlastDecision:
    status: str
    top_hit: BlastHit | None
    reported_hits: tuple[BlastHit, ...]
    competing_hits: int
    reason: str


@dataclass(frozen=True)
class Stage3Result:
    candidates_path: Path
    report_path: Path
    candidates: tuple[dict[str, str], ...]
    decisions: tuple[dict[str, object], ...]


def _open_fasta_text(path: Path):
    if path.suffix.casefold() == ".gz":
        return gzip.open(path, "rt", encoding="ascii", newline=None)
    return path.open("r", encoding="ascii", newline=None)


def parse_fasta(path: Path) -> Iterator[FastaRecord]:
    """Parse a plain or gzip-compressed nucleotide FASTA."""
    identifier: str | None = None
    description = ""
    sequence_parts: list[str] = []
    seen_identifiers: set[str] = set()

    def emit() -> FastaRecord | None:
        if identifier is None:
            return None
        sequence = "".join(sequence_parts).upper()
        if not sequence:
            raise IdentityResolutionError(f"empty FASTA sequence: {identifier}")
        invalid = sorted(set(sequence) - IUPAC_DNA)
        if invalid:
            raise IdentityResolutionError(
                f"invalid nucleotide symbols for {identifier}: {invalid}"
            )
        return FastaRecord(identifier, description, sequence)

    with _open_fasta_text(path) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                record = emit()
                if record is not None:
                    yield record
                header = line[1:].strip()
                if not header:
                    raise IdentityResolutionError(
                        f"empty FASTA header at line {line_number}"
                    )
                identifier = header.split(maxsplit=1)[0]
                if identifier in seen_identifiers:
                    raise IdentityResolutionError(
                        f"duplicate FASTA identifier: {identifier}"
                    )
                seen_identifiers.add(identifier)
                description = header
                sequence_parts = []
                continue
            if identifier is None:
                raise IdentityResolutionError(
                    f"sequence before first FASTA header at line {line_number}"
                )
            sequence_parts.append("".join(line.split()))
    record = emit()
    if record is not None:
        yield record


def _header_keys(record: FastaRecord) -> set[str]:
    keys = {record.identifier.casefold(), record.description.casefold()}
    if "." in record.identifier:
        keys.add(record.identifier.rsplit(".", 1)[0].casefold())
    keys.update(token.casefold() for token in TOKEN_PATTERN.findall(record.description))
    return keys


def index_fasta_records(records: Iterable[FastaRecord]) -> FastaIndex:
    """Create deterministic identifier and header indexes for FASTA records."""
    ordered = tuple(records)
    by_identifier: dict[str, FastaRecord] = {}
    mutable_header_index: dict[str, list[FastaRecord]] = {}
    for record in ordered:
        if record.identifier in by_identifier:
            raise IdentityResolutionError(
                f"duplicate FASTA identifier: {record.identifier}"
            )
        by_identifier[record.identifier] = record
        for key in _header_keys(record):
            mutable_header_index.setdefault(key, []).append(record)
    by_header_key = {
        key: tuple(sorted(values, key=lambda value: value.identifier))
        for key, values in mutable_header_index.items()
    }
    return FastaIndex(ordered, by_identifier, by_header_key)


def _anchor_search_terms(anchor: dict[str, str]) -> tuple[str, ...]:
    terms = [anchor.get("published_transcript_id", "")]
    terms.extend(anchor.get("aliases", "").split("|"))
    return tuple(
        term.strip()
        for term in terms
        if term.strip() and term.strip().upper() != "NA"
    )


def find_direct_header_matches(
    anchor: dict[str, str],
    index: FastaIndex,
) -> tuple[FastaRecord, ...]:
    """Find records whose header preserves a published ID or alias exactly."""
    matches: dict[str, FastaRecord] = {}
    for term in _anchor_search_terms(anchor):
        folded = term.casefold()
        for record in index.by_header_key.get(folded, ()):
            matches[record.identifier] = record
        if " " in term:
            bounded = re.compile(
                rf"(?<![A-Za-z0-9_.-]){re.escape(term)}(?![A-Za-z0-9_.-])",
                re.IGNORECASE,
            )
            for record in index.records:
                if bounded.search(record.description):
                    matches[record.identifier] = record
    return tuple(matches[key] for key in sorted(matches))


def reverse_complement(sequence: str) -> str:
    return sequence.upper().translate(COMPLEMENT)[::-1]


def canonical_tsa_accession(identifier: str) -> str:
    """Return the accession component of a BLAST/FASTA sequence identifier."""
    for component in identifier.split("|"):
        candidate = component.strip()
        if TSA_ACCESSION_PATTERN.fullmatch(candidate.upper()):
            return candidate
    return identifier


def find_exact_sequence_matches(
    query_sequence: str,
    records: Iterable[FastaRecord],
) -> tuple[ExactMatch, ...]:
    """Find complete query containment in forward or reverse orientation."""
    query = query_sequence.upper()
    if not query:
        raise IdentityResolutionError("exact sequence query cannot be empty")
    reverse = reverse_complement(query)
    matches: list[ExactMatch] = []
    for record in records:
        if query in record.sequence:
            matches.append(ExactMatch(record, "exact_nucleotide"))
        elif reverse in record.sequence:
            matches.append(ExactMatch(record, "exact_reverse_complement"))
    return tuple(sorted(matches, key=lambda match: match.record.identifier))


def parse_blast_tabular(text: str) -> tuple[BlastHit, ...]:
    """Parse the fixed eight-column BLAST outfmt used by Stage 3."""
    hits: list[BlastHit] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 8:
            raise IdentityResolutionError(
                f"BLAST line {line_number} has {len(fields)} fields, expected 8"
            )
        try:
            hit = BlastHit(
                query=fields[0],
                tsa_accession=canonical_tsa_accession(fields[1]),
                identity=float(fields[2]),
                alignment_length=int(fields[3]),
                query_length=int(fields[4]),
                query_coverage=float(fields[5]),
                evalue=float(fields[6]),
                bitscore=float(fields[7]),
            )
        except ValueError as exc:
            raise IdentityResolutionError(
                f"invalid numeric BLAST value at line {line_number}: {exc}"
            ) from exc
        hits.append(hit)
    return tuple(hits)


def _is_high_confidence(hit: BlastHit) -> bool:
    return (
        hit.identity >= HIGH_CONFIDENCE_MIN_IDENTITY
        and hit.query_coverage >= HIGH_CONFIDENCE_MIN_QUERY_COVERAGE
        and hit.evalue <= HIGH_CONFIDENCE_MAX_EVALUE
    )


def _is_competitive(candidate: BlastHit, top: BlastHit) -> bool:
    return (
        _is_high_confidence(candidate)
        and candidate.bitscore >= top.bitscore * COMPETITIVE_MIN_BITSCORE_RATIO
        and candidate.identity >= top.identity - COMPETITIVE_MAX_IDENTITY_DELTA
        and candidate.query_coverage
        >= top.query_coverage - COMPETITIVE_MAX_QUERY_COVERAGE_DELTA
    )


def classify_blast_hits(hits: Sequence[BlastHit]) -> BlastDecision:
    """Apply the visible Stage 3 thresholds without adapting them to results."""
    ordered = tuple(
        sorted(
            hits,
            key=lambda hit: (
                -hit.bitscore,
                -hit.query_coverage,
                -hit.identity,
                hit.tsa_accession,
            ),
        )
    )
    if not ordered:
        return BlastDecision(
            UNRESOLVED,
            None,
            (),
            0,
            "BLASTn returned no hits",
        )
    top = ordered[0]
    if not _is_high_confidence(top):
        return BlastDecision(
            UNRESOLVED,
            top,
            (top,),
            0,
            "best BLASTn hit does not satisfy all high-confidence thresholds",
        )
    competitors = tuple(
        hit
        for hit in ordered[1:]
        if hit.tsa_accession != top.tsa_accession and _is_competitive(hit, top)
    )
    if competitors:
        return BlastDecision(
            AMBIGUOUS,
            top,
            (top, *competitors),
            len(competitors),
            "multiple TSA records have competitively similar high-confidence support",
        )
    return BlastDecision(
        RESOLVED_HIGH_CONFIDENCE,
        top,
        (top,),
        0,
        "one BLASTn hit satisfies all thresholds without a competitive alternative",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_sequence(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_anchors(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise IdentityResolutionError("target anchor TSV has no header")
        required = {"target_id", "published_transcript_id", "aliases", "source_identifier"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise IdentityResolutionError(
                f"target anchor TSV is missing fields: {missing}"
            )
        anchors = tuple(
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        )
    target_ids = [anchor["target_id"] for anchor in anchors]
    if len(target_ids) != len(set(target_ids)):
        raise IdentityResolutionError("target anchor TSV has duplicate target_id values")
    if not anchors:
        raise IdentityResolutionError("target anchor TSV has no records")
    return anchors


def _load_anchor_sequences(
    path: Path,
    anchors: Sequence[dict[str, str]],
) -> dict[str, FastaRecord]:
    index = index_fasta_records(parse_fasta(path))
    published_ids = {
        anchor["published_transcript_id"]
        for anchor in anchors
        if anchor["published_transcript_id"].upper() != "NA"
    }
    extra = sorted(set(index.by_identifier) - published_ids)
    missing = sorted(published_ids - set(index.by_identifier))
    if missing or extra:
        raise IdentityResolutionError(
            f"anchor sequence FASTA mismatch; missing={missing}, extra={extra}"
        )
    return index.by_identifier


def _validated_tsa_from_manifest(
    root: Path,
    manifest_path: Path,
) -> tuple[Path, dict[str, object], Path]:
    manifest, files, checks, resolved_manifest = nb01_inputs.inspect_manifest(
        root, manifest_path
    )
    report = nb01_inputs.PreconditionReport(tuple(checks))
    report.raise_if_failed()
    if manifest is None or len(files) != 1:
        raise IdentityResolutionError(
            "Stage 3 requires exactly one validated primary TSA file in the manifest"
        )
    tsa_path = (root / files[0]["path"]).resolve()
    return tsa_path, manifest, resolved_manifest


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise IdentityResolutionError(
            f"required executable is unavailable: {command[0]}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise IdentityResolutionError(
            f"command failed ({command[0]}): {detail}"
        ) from exc


def _write_query_fasta(path: Path, queries: dict[str, str]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as handle:
        for query_id in sorted(queries):
            handle.write(f">{query_id}\n{queries[query_id]}\n")


def run_blastn(
    queries: dict[str, str],
    tsa_path: Path,
) -> tuple[tuple[BlastHit, ...], dict[str, str]]:
    """Run local BLASTn against a temporary database built from the TSA."""
    if not queries:
        return (), {}
    versions = {
        "blastn": _run_command(["blastn", "-version"]).stdout.splitlines()[0],
        "makeblastdb": _run_command(["makeblastdb", "-version"]).stdout.splitlines()[0],
    }
    with tempfile.TemporaryDirectory(prefix="zeaguard-nb01-stage3-") as temp_name:
        temporary = Path(temp_name)
        subject_path = temporary / "tsa.fasta"
        if tsa_path.suffix.casefold() == ".gz":
            with gzip.open(tsa_path, "rb") as source, subject_path.open("wb") as target:
                shutil.copyfileobj(source, target)
        else:
            shutil.copyfile(tsa_path, subject_path)
        query_path = temporary / "queries.fasta"
        _write_query_fasta(query_path, queries)
        database_prefix = temporary / "tsa_db"
        _run_command(
            [
                "makeblastdb",
                "-in",
                str(subject_path),
                "-dbtype",
                "nucl",
                "-parse_seqids",
                "-out",
                str(database_prefix),
            ]
        )
        result = _run_command(
            [
                "blastn",
                "-task",
                "blastn",
                "-dust",
                "no",
                "-query",
                str(query_path),
                "-db",
                str(database_prefix),
                "-evalue",
                str(BLAST_SEARCH_MAX_EVALUE),
                "-max_target_seqs",
                str(BLAST_MAX_TARGET_SEQS),
                "-max_hsps",
                "1",
                "-outfmt",
                "6 qseqid sseqid pident length qlen qcovs evalue bitscore",
            ]
        )
    return parse_blast_tabular(result.stdout), versions


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "NA"
    if isinstance(value, int):
        return str(value)
    return format(value, ".12g")


def _candidate_row(
    anchor: dict[str, str],
    accession: str,
    method: str,
    status: str,
    competing_hits: int,
    notes: str,
    identity: float | None = None,
    coverage: float | None = None,
    alignment_length: int | None = None,
    evalue: float | None = None,
    bitscore: float | None = None,
) -> dict[str, str]:
    return {
        "target_id": anchor["target_id"],
        "published_transcript_id": anchor["published_transcript_id"],
        "tsa_accession": accession or "NA",
        "resolution_method": method,
        "identity": _format_number(identity),
        "query_coverage": _format_number(coverage),
        "alignment_length": _format_number(alignment_length),
        "evalue": _format_number(evalue),
        "bitscore": _format_number(bitscore),
        "competing_hits": str(competing_hits),
        "resolution_status": status,
        "evidence_source": anchor["source_identifier"],
        "notes": notes,
    }


def _atomic_write_json(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_tsv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=CANDIDATE_COLUMNS,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare_nb01_stage3(
    project_root: Path,
    anchor_path: Path = DEFAULT_ANCHOR_PATH,
    anchor_sequence_path: Path = DEFAULT_ANCHOR_SEQUENCE_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Stage3Result:
    """Resolve published anchors against the manifest-selected TSA in layers."""
    root = project_root.resolve()
    resolved_anchor_path = (root / anchor_path).resolve()
    resolved_sequence_path = (root / anchor_sequence_path).resolve()
    for path in (resolved_anchor_path, resolved_sequence_path):
        path.relative_to(root)
        if not path.is_file():
            raise IdentityResolutionError(f"missing Stage 3 input: {path}")

    anchors = _load_anchors(resolved_anchor_path)
    reference_sequences = _load_anchor_sequences(resolved_sequence_path, anchors)
    tsa_path, manifest, resolved_manifest_path = _validated_tsa_from_manifest(
        root, manifest_path
    )
    tsa_index = index_fasta_records(parse_fasta(tsa_path))

    candidate_rows: list[dict[str, str]] = []
    decisions: list[dict[str, object]] = []
    pending_blast: dict[str, tuple[dict[str, str], str]] = {}

    for anchor in anchors:
        published_id = anchor["published_transcript_id"]
        query_record = reference_sequences.get(published_id)
        header_matches = find_direct_header_matches(anchor, tsa_index)
        if len(header_matches) == 1:
            row = _candidate_row(
                anchor,
                canonical_tsa_accession(header_matches[0].identifier),
                "header_identifier",
                RESOLVED_EXACT,
                0,
                "one TSA header preserves a published identifier or alias",
            )
            candidate_rows.append(row)
            decisions.append(
                {
                    "target_id": anchor["target_id"],
                    "published_transcript_id": published_id,
                    "status": RESOLVED_EXACT,
                    "method": "header_identifier",
                    "candidates": [row],
                }
            )
            continue
        if len(header_matches) > 1:
            rows = [
                _candidate_row(
                    anchor,
                    canonical_tsa_accession(match.identifier),
                    "header_identifier",
                    AMBIGUOUS,
                    len(header_matches) - 1,
                    "multiple TSA headers preserve a published identifier or alias",
                )
                for match in header_matches
            ]
            candidate_rows.extend(rows)
            decisions.append(
                {
                    "target_id": anchor["target_id"],
                    "published_transcript_id": published_id,
                    "status": AMBIGUOUS,
                    "method": "header_identifier",
                    "candidates": rows,
                }
            )
            continue
        if query_record is None:
            row = _candidate_row(
                anchor,
                "",
                "reference_sequence_unavailable",
                UNRESOLVED,
                0,
                "no official published nucleotide sequence is materialized",
            )
            candidate_rows.append(row)
            decisions.append(
                {
                    "target_id": anchor["target_id"],
                    "published_transcript_id": published_id,
                    "status": UNRESOLVED,
                    "method": "reference_sequence_unavailable",
                    "candidates": [row],
                }
            )
            continue
        exact_matches = find_exact_sequence_matches(
            query_record.sequence, tsa_index.records
        )
        if exact_matches:
            status = RESOLVED_EXACT if len(exact_matches) == 1 else AMBIGUOUS
            rows = [
                _candidate_row(
                    anchor,
                    canonical_tsa_accession(match.record.identifier),
                    match.method,
                    status,
                    len(exact_matches) - 1,
                    "complete published nucleotide sequence matched a TSA record",
                    identity=100.0,
                    coverage=100.0,
                    alignment_length=len(query_record.sequence),
                )
                for match in exact_matches
            ]
            candidate_rows.extend(rows)
            decisions.append(
                {
                    "target_id": anchor["target_id"],
                    "published_transcript_id": published_id,
                    "status": status,
                    "method": exact_matches[0].method,
                    "candidates": rows,
                }
            )
            continue
        pending_blast[published_id] = (anchor, query_record.sequence)

    blast_hits, tool_versions = run_blastn(
        {query_id: value[1] for query_id, value in pending_blast.items()},
        tsa_path,
    )
    hits_by_query: dict[str, list[BlastHit]] = {}
    for hit in blast_hits:
        hits_by_query.setdefault(hit.query, []).append(hit)

    for published_id, (anchor, query_sequence) in pending_blast.items():
        decision = classify_blast_hits(hits_by_query.get(published_id, []))
        rows: list[dict[str, str]] = []
        if decision.reported_hits:
            for hit in decision.reported_hits:
                rows.append(
                    _candidate_row(
                        anchor,
                        hit.tsa_accession,
                        "blastn",
                        decision.status,
                        decision.competing_hits,
                        decision.reason,
                        identity=hit.identity,
                        coverage=hit.query_coverage,
                        alignment_length=hit.alignment_length,
                        evalue=hit.evalue,
                        bitscore=hit.bitscore,
                    )
                )
        else:
            rows.append(
                _candidate_row(
                    anchor,
                    "",
                    "blastn",
                    UNRESOLVED,
                    0,
                    decision.reason,
                )
            )
        candidate_rows.extend(rows)
        decisions.append(
            {
                "target_id": anchor["target_id"],
                "published_transcript_id": published_id,
                "query_length": len(query_sequence),
                "query_sha256": _sha256_sequence(query_sequence),
                "status": decision.status,
                "method": "blastn",
                "competing_hits": decision.competing_hits,
                "reason": decision.reason,
                "candidates": rows,
            }
        )

    decision_order = {anchor["target_id"]: index for index, anchor in enumerate(anchors)}
    decisions.sort(key=lambda decision: decision_order[str(decision["target_id"])])
    candidate_rows.sort(
        key=lambda row: (
            decision_order[row["target_id"]],
            row["tsa_accession"],
        )
    )
    destination = (root / output_dir).resolve()
    destination.relative_to(root)
    destination.mkdir(parents=True, exist_ok=True)
    candidates_path = destination / "target_identity_candidates.tsv"
    report_path = destination / "target_identity_report.json"
    _atomic_write_tsv(candidates_path, candidate_rows)

    report_document: dict[str, object] = {
        "schema_version": 1,
        "stage": "NB01_STAGE_3",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "RESOLVED_EXACT": (
                "one TSA header preserves a published identifier or alias, or one "
                "TSA record contains the complete published nucleotide sequence in "
                "forward or reverse-complement orientation"
            ),
            "RESOLVED_HIGH_CONFIDENCE": {
                "min_identity": HIGH_CONFIDENCE_MIN_IDENTITY,
                "min_query_coverage": HIGH_CONFIDENCE_MIN_QUERY_COVERAGE,
                "max_evalue": HIGH_CONFIDENCE_MAX_EVALUE,
                "competitive_min_bitscore_ratio": COMPETITIVE_MIN_BITSCORE_RATIO,
                "competitive_max_identity_delta": COMPETITIVE_MAX_IDENTITY_DELTA,
                "competitive_max_query_coverage_delta": (
                    COMPETITIVE_MAX_QUERY_COVERAGE_DELTA
                ),
            },
            "AMBIGUOUS": (
                "multiple exact matches or at least one competitively similar "
                "high-confidence BLASTn hit"
            ),
            "UNRESOLVED": (
                "no exact match and no unique BLASTn hit satisfying every "
                "high-confidence threshold"
            ),
        },
        "inputs": {
            "target_anchors": {
                "path": _relative_path(root, resolved_anchor_path),
                "sha256": _sha256_file(resolved_anchor_path),
            },
            "anchor_sequences": {
                "path": _relative_path(root, resolved_sequence_path),
                "sha256": _sha256_file(resolved_sequence_path),
            },
            "dataset_manifest": {
                "path": _relative_path(root, resolved_manifest_path),
                "sha256": _sha256_file(resolved_manifest_path),
                "dataset": manifest.get("dataset"),
            },
            "tsa": {
                "path": _relative_path(root, tsa_path),
                "sha256": _sha256_file(tsa_path),
                "records": len(tsa_index.records),
            },
        },
        "tools": tool_versions,
        "summary": {
            status: sum(decision["status"] == status for decision in decisions)
            for status in (
                RESOLVED_EXACT,
                RESOLVED_HIGH_CONFIDENCE,
                AMBIGUOUS,
                UNRESOLVED,
            )
        },
        "targets": decisions,
    }
    _atomic_write_json(report_path, report_document)
    return Stage3Result(
        candidates_path=candidates_path,
        report_path=report_path,
        candidates=tuple(candidate_rows),
        decisions=tuple(decisions),
    )
