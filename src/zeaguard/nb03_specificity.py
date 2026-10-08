"""NB03 CP3: candidate-native specificity evidence, batched by registered length.

All canonical HSPs come from the candidate query itself. Full-CDS clipping is never used.
The benchmark and controls are separate logical queries. Nothing here compares candidates,
forms cells, chooses representatives, ranks, recommends, or writes CP4/CP5 artifacts.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import Any, Iterable, Sequence

from zeaguard import nb01_identity, nb02_design, nb02_reference, nb02_specificity as mechanics
from zeaguard import nb03_criteria as criteria, nb03_design as design
from zeaguard.nb01_dsrnase_investigation import BLAST_OUTFMT_FIELDS, Hsp, parse_hsp_table, sha256_text, union_length

OUTPUT_DIR = Path("results/bioinformatics/nb03/cp3")
UNITS = ("KNOWN_BICC_COMPATIBLE", "BICC_LIKE", "DSRNASE2", "DSRNASE1", "DSRNASE3", "OTHER_TRANSCRIPT")
AXES = ("longest_exact_match", "covered_nt", "best_local_identity")
UNIT_METRICS = (*AXES, "aligned_nt_for_best_identity", "identical_nt_for_best_identity", "n_hsps", "n_subject_records", "subject_accessions")
QUERY_ROLES = {"DESIGN_SPACE": "SPECIFICITY_EVIDENCE_ONLY", "REFERENCE_SET": "REFERENCE_ONLY", "SHUFFLED_CONTROL": "DESCRIPTIVE_ONLY"}
BASE_COLUMNS = ("window_id", "membership", "query_role", "length_nt", "cds_start", "cds_end", "sequence_sha256", "specificity_evidence_basis")
WINDOW_COLUMNS = (*BASE_COLUMNS, *(f"{unit.lower()}_{metric}" for unit in UNITS for metric in UNIT_METRICS))
OTHER_COLUMNS = (*BASE_COLUMNS, *UNIT_METRICS)
CONTROL_COLUMNS = (*WINDOW_COLUMNS, "source_window_id", "seed")
KMER_COLUMNS = ("window_id", "membership", "length_nt", "unit", "role", "evidence_basis", "exact_19mer_match_count", "exact_21mer_match_count")
HSP_COLUMNS = ("hsp_id", "query", "membership", "query_role", "source_window_id", "seed", "unit", "role", "relationship_status",
               "specificity_evidence_basis", "query_sequence_sha256", "subject", "strand", "qlen", "slen",
               "qstart", "qend", "sstart", "send", "btop", "alignment_length", "identical_columns",
               "local_identity", "reported_identity_percent", "longest_exact_match", "covered_query_nt",
               "evalue", "bitscore", "mismatch", "gapopen", "gaps")
EVIDENCE_FILES = ("blast_hsps.tsv", "candidate_unit_specificity.tsv", "other_transcript_summary.tsv",
                  "exact_kmer_summary.tsv", "shuffled_controls.tsv", "benchmark_specificity.tsv",
                  "cp3_summary.json", "run_manifest.json")
_BTOP_VALID = re.compile(r"(?:[0-9]+|[A-Za-z*\-]{2})+")


class NB03SpecificityError(RuntimeError):
    """Candidate-native evidence fails a mechanical or provenance contract."""


@dataclass(frozen=True)
class Policy:
    units: dict[str, tuple[str, frozenset[str]]]
    owners: dict[str, str]
    relationships: dict[str, str]
    search: dict[str, Any]
    seeds: tuple[int, ...]

    def classify(self, subject: str) -> str:
        return self.owners.get(subject, "OTHER_TRANSCRIPT")


def load_policy(registry: dict[str, Any]) -> Policy:
    if criteria.validate_registry(registry):
        raise NB03SpecificityError("invalid preregistered native-alignment contract")
    frozen = registry["policy"]["specificity_units"]
    units = {name: (frozen[name]["role"], frozenset(frozen[name]["members"]) if name != "OTHER_TRANSCRIPT" else frozenset())
             for name in UNITS}
    owners = {member: name for name, (_, members) in units.items() for member in members}
    by_name = {c["name"]: c for c in registry["criteria"]}
    return Policy(units, owners, {name: frozen[name]["relationship_status"] for name in UNITS},
                  by_name["search_detection_limit"]["threshold"], tuple(by_name["shuffled_control"]["threshold"]["seeds"]))


@dataclass(frozen=True)
class Query:
    identifier: str
    sequence: str
    membership: str
    cds_start: int
    cds_end: int
    source_window_id: str = ""
    seed: int = 0

    @property
    def length(self) -> int:
        return len(self.sequence)


def load_queries(root: Path, reference: dict[str, Any]) -> tuple[list[Query], Query, dict[str, str]]:
    """Read the certified CP2 outputs; preserve exact IDs, roles and sequence hashes."""
    out = Path(root) / design.OUTPUT_DIR
    old_manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    for name, expected in old_manifest["outputs_sha256"].items():
        if design._sha256(out / name) != expected:
            raise NB03SpecificityError(f"CP2 output integrity mismatch: {name}")
    cds = reference["operational_cds"]
    if old_manifest["inputs"]["operational_cds_sha256"] != sha256_text(cds):
        raise NB03SpecificityError("CP2 and CP3 operational CDS hashes differ")
    parameters = design.design_parameters(reference["registry"])
    allowed = set(parameters.strata)
    queries: list[Query] = []
    seen = set()
    with (out / "design_space.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            length = int(row["length_nt"])
            if length not in allowed:
                continue
            start, end = int(row["cds_start"]), int(row["cds_end"])
            seq = cds[start - 1:end]
            identifier = design.window_id(length, start, end)
            if (not design.passes_hard_filters(seq, start, end, parameters) or row["window_id"] != identifier
                    or identifier in seen or row["membership"] != "DESIGN_SPACE" or sha256_text(seq) != row["sequence_sha256"]):
                raise NB03SpecificityError("invalid, duplicate or mismatched CP2 design query")
            seen.add(identifier)
            queries.append(Query(identifier, seq, "DESIGN_SPACE", start, end))
    expected = {length: len(nb02_design.windows_of_length(len(cds), length)) for length in allowed}
    if Counter(q.length for q in queries) != expected or len(queries) != 7779:
        raise NB03SpecificityError("native-query strata must contain exactly 7779 design-space windows")
    queries.sort(key=lambda q: (q.length, q.cds_start))
    with (out / "benchmark_descriptor.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        raise NB03SpecificityError("CP2 must provide exactly one separate benchmark")
    row = rows[0]
    start, end = int(row["cds_start"]), int(row["cds_end"])
    benchmark = Query(row["window_id"], cds[start - 1:end], row["membership"], start, end)
    if (benchmark.identifier != design.BENCHMARK_ID or benchmark.membership != "REFERENCE_SET"
            or (start, end) != (215, 587) or benchmark.length != 373
            or sha256_text(benchmark.sequence) != reference["pin"]["benchmark"]["body"]["sha256"]):
        raise NB03SpecificityError("the native benchmark differs from the operational pin")
    return queries, benchmark, {"cp2_manifest_sha256": design._sha256(out / "run_manifest.json"),
                                "cp2_design_space_sha256": old_manifest["outputs_sha256"]["design_space.tsv"]}


def shuffled_queries(queries: Sequence[Query], seeds: Sequence[int]) -> list[Query]:
    return [Query(f"SHUF-s{seed}-{q.identifier}", mechanics.shuffled_sequence(q.sequence, seed), "SHUFFLED_CONTROL",
                  q.cds_start, q.cds_end, q.identifier, seed) for seed in seeds for q in queries]


@dataclass(frozen=True)
class NativeHsp:
    identifier: str
    raw: Hsp
    unit: str
    exact_runs: tuple[tuple[int, int], ...]
    identical_columns: int

    @property
    def identity(self) -> Fraction:
        return Fraction(self.identical_columns, self.raw.length)

    @property
    def longest_exact(self) -> int:
        return max((b - a + 1 for a, b in self.exact_runs), default=0)


def native_hsp(hsp: Hsp, query: Query, unit: str, identifier: str) -> NativeHsp:
    """Validate full native HSP columns; I consumes query, D consumes subject only.

    Exact runs and identity are reconstructed from BTOP. No HSP clipping is performed.
    """
    if hsp.query != query.identifier or hsp.qlen != query.length or not 1 <= hsp.qstart <= hsp.qend <= query.length:
        raise NB03SpecificityError("HSP query identity/length/coordinates do not match the native query")
    if (hsp.strand not in {"plus", "minus"} or not 1 <= min(hsp.sstart, hsp.send) <= max(hsp.sstart, hsp.send) <= hsp.slen
            or (hsp.strand == "plus" and hsp.sstart > hsp.send) or (hsp.strand == "minus" and hsp.sstart < hsp.send)):
        raise NB03SpecificityError("invalid native HSP subject coordinates or orientation")
    if not _BTOP_VALID.fullmatch(hsp.btop):
        raise NB03SpecificityError("malformed native HSP BTOP")
    columns = mechanics.btop_columns(hsp.btop)
    if len(columns) != hsp.length or not columns:
        raise NB03SpecificityError("BTOP alignment-column count differs from HSP length")
    position = hsp.qstart - 1
    subject_bases = identical = 0
    runs = []
    run_start = None
    for q, s in columns:
        if q == s == "-":
            raise NB03SpecificityError("BTOP cannot contain a double-gap column")
        subject_bases += s != "-"
        if q == "-":  # D: no query advance; insertion in subject interrupts exact runs.
            if run_start is not None:
                runs.append((run_start, position))
                run_start = None
            continue
        position += 1  # I (query base vs subject gap) also advances query.
        if position > query.length:
            raise NB03SpecificityError("BTOP extends beyond the native query")
        if q != "=" and query.sequence[position - 1] != q:
            raise NB03SpecificityError("BTOP query base disagrees with the native sequence")
        if q == s == "=":
            identical += 1
            if run_start is None:
                run_start = position
        elif run_start is not None:
            runs.append((run_start, position - 1))
            run_start = None
    if run_start is not None:
        runs.append((run_start, position))
    if position != hsp.qend or subject_bases != abs(hsp.send - hsp.sstart) + 1:
        raise NB03SpecificityError("BTOP query or subject span differs from native HSP coordinates")
    if abs(100 * identical / len(columns) - hsp.pident) > 0.000501:
        raise NB03SpecificityError("BTOP identity differs from the reported rounded HSP identity")
    return NativeHsp(identifier, hsp, unit, tuple(runs), identical)


def unit_evidence(hsps: Sequence[NativeHsp]) -> dict[str, Any]:
    if len({h.raw.query for h in hsps}) > 1 or len({h.unit for h in hsps}) > 1:
        raise NB03SpecificityError("aggregation cannot pool different native queries or biological units")
    if not hsps:
        return dict(zip(UNIT_METRICS, (0, 0, 0.0, 0, 0, 0, 0, "")))
    best = min(hsps, key=lambda h: (-h.identity, -h.raw.length, h.identifier))
    subjects = sorted({h.raw.subject for h in hsps})
    return {"longest_exact_match": max(h.longest_exact for h in hsps),
            "covered_nt": union_length((h.raw.qstart, h.raw.qend) for h in hsps),
            "best_local_identity": float(best.identity), "aligned_nt_for_best_identity": best.raw.length,
            "identical_nt_for_best_identity": best.identical_columns, "n_hsps": len(hsps),
            "n_subject_records": len(subjects), "subject_accessions": ",".join(subjects)}


def evidence_vector(evidence: dict[str, Any]) -> tuple[float, float, float]:
    return tuple(evidence[axis] for axis in AXES)


def as_decisional_evidence(row: dict[str, Any], observed_positions: Iterable[int]) -> criteria.SpecificityEvidence:
    """Provenance-gated adapter for a future CP4 consumer; CP3 never invokes comparisons."""
    basis = row["specificity_evidence_basis"]
    if row["membership"] != "DESIGN_SPACE":
        raise criteria.NB03EvidenceBasisError("controls and REFERENCE_SET cannot enter the candidate decisional signature")
    if basis != criteria.CANONICAL_EVIDENCE_BASIS:
        raise criteria.NB03EvidenceBasisError("native canonical basis required for the CP4 adapter")
    return criteria.SpecificityEvidence(row["window_id"], int(row["length_nt"]), frozenset(observed_positions),
                                       tuple(float(row[f"bicc_like_{axis}"]) for axis in AXES),
                                       tuple(float(row[f"dsrnase2_{axis}"]) for axis in AXES), basis)


def _writer(path: Path, columns: Sequence[str]):
    handle = path.open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    return handle, writer


def _serialized(row: dict[str, Any]) -> dict[str, Any]:
    return {key: format(value, ".17g") if isinstance(value, float) else value for key, value in row.items()}


class ExecutionLog:
    def __init__(self, out: Path):
        self.out = out
        self.entries = []

    def run(self, command: list[str], output: Path | None = None) -> str:
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        if output is not None:
            output.write_text(process.stdout, encoding="utf-8", newline="\n")
        self.entries.append({"command": command, "started_utc": started,
                             "finished_utc": datetime.now(timezone.utc).isoformat(), "returncode": process.returncode})
        design._write_json(self.out / "execution_log.json", {"commands": self.entries})
        return process.stdout


def build_database(root: Path, out: Path, policy: Policy, log: ExecutionLog) -> dict[str, Any]:
    tsa_path, tsa_sha = nb02_reference.validated_tsa_path(root)
    db_dir = out / "blastdb"
    db_dir.mkdir(parents=True, exist_ok=True)
    combined = db_dir / "combined.fasta"
    ids, count = set(), 0
    anchors = list(nb01_identity.parse_fasta(root / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH))
    with combined.open("w", encoding="ascii", newline="\n") as handle:
        for record in nb01_identity.parse_fasta(tsa_path):
            accession = nb01_identity.canonical_tsa_accession(record.identifier)
            if accession in ids:
                raise NB03SpecificityError("duplicate TSA accession in the native database")
            ids.add(accession)
            count += 1
            handle.write(f">{accession}\n{record.sequence.upper()}\n")
        for record in anchors:
            if record.identifier in ids:
                raise NB03SpecificityError("duplicate anchor/TSA identifier in the native database")
            ids.add(record.identifier)
            handle.write(f">{record.identifier}\n{record.sequence.upper()}\n")
    if set(policy.owners) - ids:
        raise NB03SpecificityError("a frozen biological-unit member is absent from the native database")
    database = db_dir / "nb03_candidate_native"
    log.run(["makeblastdb", "-in", str(combined), "-dbtype", "nucl", "-out", str(database), "-title", "nb03_candidate_native"])
    info = log.run(["blastdbcmd", "-db", str(database), "-info"], out / "database_info.txt")
    match = re.search(r"([\d,]+) sequences; ([\d,]+) total bases", info)
    if match is None:
        raise NB03SpecificityError("native database statistics were not parsed")
    return {"path": str(database), "combined_fasta": str(combined), "combined_fasta_sha256": design._sha256(combined),
            "tsa_file_sha256": tsa_sha, "n_tsa_records": count, "published_cdna_records": [r.identifier for r in anchors],
            "n_sequences": int(match[1].replace(",", "")), "total_bases": int(match[2].replace(",", ""))}


def write_queries(path: Path, queries: Sequence[Query]) -> None:
    if len({q.identifier for q in queries}) != len(queries) or any(set(q.sequence) - set("ACGT") for q in queries):
        raise NB03SpecificityError("native query FASTA requires unique IDs and A/C/G/T sequences")
    path.write_text("".join(f">{q.identifier}\n{q.sequence}\n" for q in queries), encoding="ascii", newline="\n")


def batches(queries: Sequence[Query], benchmark: Query, seeds: Sequence[int]) -> list[tuple[str, list[Query]]]:
    primary = [(f"L{length}", [q for q in queries if q.length == length]) for length in sorted({q.length for q in queries})]
    primary.append(("benchmark", [benchmark]))
    return primary + [(f"controls_{name}", shuffled_queries(group, seeds)) for name, group in primary]


def query_row(query: Query, by_unit: dict[str, list[NativeHsp]]) -> dict[str, Any]:
    row = {"window_id": query.identifier, "membership": query.membership, "query_role": QUERY_ROLES[query.membership], "length_nt": query.length,
           "cds_start": query.cds_start, "cds_end": query.cds_end, "sequence_sha256": sha256_text(query.sequence),
           "specificity_evidence_basis": criteria.CANONICAL_EVIDENCE_BASIS}
    for unit in UNITS:
        row.update({f"{unit.lower()}_{key}": value for key, value in unit_evidence(by_unit.get(unit, [])).items()})
    return row


def hsp_row(hsp: NativeHsp, query: Query, policy: Policy) -> dict[str, Any]:
    raw = hsp.raw
    return {"hsp_id": hsp.identifier, "query": raw.query, "membership": query.membership, "query_role": QUERY_ROLES[query.membership],
            "source_window_id": query.source_window_id, "seed": query.seed, "unit": hsp.unit,
            "role": policy.units[hsp.unit][0], "relationship_status": policy.relationships[hsp.unit],
            "specificity_evidence_basis": criteria.CANONICAL_EVIDENCE_BASIS, "query_sequence_sha256": sha256_text(query.sequence),
            "subject": raw.subject, "strand": raw.strand, "qlen": raw.qlen, "slen": raw.slen,
            "qstart": raw.qstart, "qend": raw.qend, "sstart": raw.sstart, "send": raw.send, "btop": raw.btop,
            "alignment_length": raw.length, "identical_columns": hsp.identical_columns, "local_identity": float(hsp.identity),
            "reported_identity_percent": raw.pident, "longest_exact_match": hsp.longest_exact,
            "covered_query_nt": raw.qend - raw.qstart + 1, "evalue": raw.evalue, "bitscore": raw.bitscore,
            "mismatch": raw.mismatch, "gapopen": raw.gapopen, "gaps": raw.gaps}


def _describe_numbers(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {"min": ordered[0], "median": statistics.median(ordered), "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
            "max": ordered[-1], "mean": statistics.fmean(ordered)}


def summarize_rows(rows: Sequence[dict[str, Any]], unit: str) -> dict[str, Any]:
    prefix = unit.lower()
    vectors = Counter(tuple(row[f"{prefix}_{axis}"] for axis in AXES) for row in rows)
    return {"n_queries": len(rows), "zero_vectors": vectors.get((0, 0, 0.0), 0), "n_unique_vectors": len(vectors),
            "vector_distribution": [{"vector": list(vector), "count": count} for vector, count in sorted(vectors.items())],
            **{metric: _describe_numbers([row[f"{prefix}_{metric}"] for row in rows])
               for metric in (*AXES, "n_hsps", "n_subject_records", "aligned_nt_for_best_identity")}}


def materialize(root: Path, out: Path, queries: Sequence[Query], benchmark: Query, policy: Policy,
                batch_groups: Sequence[tuple[str, list[Query]]]) -> dict[str, Any]:
    """Deterministically derive evidence from saved native-query raw tables, without BLAST or clipping."""
    candidates, benchmark_rows = [], []
    hsp_counts = Counter()
    controls_summary = {}
    by_stratum = defaultdict(list)
    handles = []
    try:
        for name, columns in (("blast_hsps.tsv", HSP_COLUMNS), ("candidate_unit_specificity.tsv", WINDOW_COLUMNS),
                              ("benchmark_specificity.tsv", WINDOW_COLUMNS), ("other_transcript_summary.tsv", OTHER_COLUMNS),
                              ("shuffled_controls.tsv", CONTROL_COLUMNS)):
            handle, writer = _writer(out / name, columns)
            handles.append(handle)
            if name == "blast_hsps.tsv":
                hsp_writer = writer
            elif name == "candidate_unit_specificity.tsv":
                candidate_writer = writer
            elif name == "benchmark_specificity.tsv":
                benchmark_writer = writer
            elif name == "other_transcript_summary.tsv":
                other_writer = writer
            else:
                control_writer = writer
        for batch_name, group in batch_groups:
            lookup = {q.identifier: q for q in group}
            raw = parse_hsp_table((out / "raw" / f"{batch_name}.outfmt6.tsv").read_text(encoding="utf-8"))
            raw.sort(key=lambda h: (h.query, h.subject, h.qstart, h.qend, h.sstart, h.send, h.btop, h.evalue, h.bitscore, h.pident))
            grouped = defaultdict(lambda: defaultdict(list))
            for index, h in enumerate(raw, 1):
                if h.query not in lookup:
                    raise NB03SpecificityError("native raw output contains an undeclared query")
                native = native_hsp(h, lookup[h.query], policy.classify(h.subject), f"{batch_name}:HSP{index:08d}")
                grouped[h.query][native.unit].append(native)
                hsp_writer.writerow(_serialized(hsp_row(native, lookup[h.query], policy)))
                hsp_counts[(lookup[h.query].membership, native.unit)] += 1
            controls = defaultdict(list)
            for q in group:
                row = query_row(q, grouped.get(q.identifier, {}))
                if q.membership == "SHUFFLED_CONTROL":
                    row.update(source_window_id=q.source_window_id, seed=q.seed)
                    control_writer.writerow(_serialized(row))
                    controls[q.seed].append(row)
                    continue
                # Positive control: recover the whole native sequence at its expected operational-record location.
                self_hsps = [h for h in grouped[q.identifier]["KNOWN_BICC_COMPATIBLE"] if h.raw.subject == "GITV01000968.1"]
                if not any(h.longest_exact == q.length and h.raw.qstart == 1 and h.raw.qend == q.length
                           and h.raw.strand == "plus" and h.raw.sstart == 65 + q.cds_start - 1
                           and h.raw.send == 65 + q.cds_end - 1 for h in self_hsps):
                    raise NB03SpecificityError(f"positive self-control failed for {q.identifier}")
                if q.membership == "DESIGN_SPACE":
                    candidate_writer.writerow(_serialized(row))
                    candidates.append(row)
                    by_stratum[q.length].append(row)
                    other = {key: row[key] for key in BASE_COLUMNS}
                    other.update({metric: row[f"other_transcript_{metric}"] for metric in UNIT_METRICS})
                    other_writer.writerow(_serialized(other))
                else:
                    benchmark_writer.writerow(_serialized(row))
                    benchmark_rows.append(row)
            if controls:
                controls_summary[batch_name] = {str(seed): {unit: summarize_rows(rows, unit) for unit in UNITS}
                                               for seed, rows in sorted(controls.items())}
    finally:
        for handle in handles:
            handle.close()
    if len(candidates) != 7779 or len(benchmark_rows) != 1:
        raise NB03SpecificityError("CP3 logical query counts differ from the four strata and separate benchmark")
    return {"candidates": candidates, "benchmark": benchmark_rows[0], "by_stratum": dict(by_stratum),
            "hsp_counts": hsp_counts, "controls_summary": controls_summary}


def exact_kmer_output(root: Path, out: Path, cds: str, queries: Sequence[Query], benchmark: Query, policy: Policy) -> dict[str, Any]:
    """Index CDS words once, scan each database record once, then count fully-contained starts per query.

    Exact substring inclusion is independent of local-alignment optimization and of BLAST detection.
    """
    records = ((r.identifier, r.sequence.upper()) for r in nb01_identity.parse_fasta(out / "blastdb" / "combined.fasta"))
    scan = mechanics.exact_kmer_scan(cds, records, policy)
    positions = {k: {unit: sorted(scan[k].get(unit, set())) for unit in UNITS} for k in (19, 21)}
    summaries = defaultdict(lambda: defaultdict(list))
    handle, writer = _writer(out / "exact_kmer_summary.tsv", KMER_COLUMNS)
    try:
        for q in (*queries, benchmark):
            for unit in UNITS:
                counts = {k: bisect_right(positions[k][unit], q.cds_end - k + 1) - bisect_left(positions[k][unit], q.cds_start)
                          for k in (19, 21)}
                writer.writerow({"window_id": q.identifier, "membership": q.membership, "length_nt": q.length,
                                 "unit": unit, "role": "DESCRIPTIVE_ONLY", "evidence_basis": "INDEPENDENT_DIRECT_SEQUENCE_SCAN_BOTH_STRANDS",
                                 "exact_19mer_match_count": counts[19], "exact_21mer_match_count": counts[21]})
                if q.membership == "DESIGN_SPACE":
                    for k in (19, 21):
                        summaries[(q.length, unit)][k].append(counts[k])
    finally:
        handle.close()
    return {str(length): {unit: {str(k): {**_describe_numbers(summaries[(length, unit)][k]),
                                        "queries_with_matches": sum(v > 0 for v in summaries[(length, unit)][k])}
                                  for k in (19, 21)} for unit in UNITS}
            for length in sorted({q.length for q in queries})}


def run_cp3(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    reference = design.verified_reference(root)
    registry = reference["registry"]
    policy = load_policy(registry)
    queries, benchmark, cp2_provenance = load_queries(root, reference)
    out = Path(output_dir) if output_dir is not None else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    for name in ("queries", "raw"):
        (out / name).mkdir(exist_ok=True)
    log = ExecutionLog(out)
    version = " | ".join(log.run(["blastn", "-version"]).splitlines()[:2])
    database = build_database(root, out, policy, log)
    batch_groups = batches(queries, benchmark, policy.seeds)
    query_hashes, raw_hashes = {}, {}
    for batch_name, group in batch_groups:
        fasta, raw = out / "queries" / f"{batch_name}.fasta", out / "raw" / f"{batch_name}.outfmt6.tsv"
        write_queries(fasta, group)
        print(f"BLAST native batch {batch_name}: {len(group)} queries", flush=True)
        log.run(["blastn", "-query", str(fasta), "-db", database["path"], *mechanics.blastn_arguments(policy.search),
                 "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)], raw)
        query_hashes[f"queries/{fasta.name}"] = design._sha256(fasta)
        raw_hashes[f"raw/{raw.name}"] = design._sha256(raw)
    print("Materializing candidate-native HSP evidence", flush=True)
    result = materialize(root, out, queries, benchmark, policy, batch_groups)
    print("Independent exact 19/21-mer scan", flush=True)
    kmer_summary = exact_kmer_output(root, out, reference["operational_cds"], queries, benchmark, policy)
    per_stratum = {str(length): {unit: summarize_rows(rows, unit) for unit in UNITS}
                   for length, rows in sorted(result["by_stratum"].items())}
    counts = result["hsp_counts"]
    summary = {"stage": "NB03_CP3_CANDIDATE_NATIVE_SPECIFICITY_EVIDENCE", "evidence_status": "MATERIALIZED",
               "specificity_evidence_basis": criteria.CANONICAL_EVIDENCE_BASIS,
               "candidate_query_count": len(queries), "benchmark_query_count": 1,
               "candidate_queries_by_length": {str(k): v for k, v in sorted(Counter(q.length for q in queries).items())},
               "shuffled_query_count": sum(len(g) for name, g in batch_groups if name.startswith("controls_")),
               "hsp_total": sum(counts.values()), "hsp_counts_by_membership_and_unit":
               {membership: {unit: counts[(membership, unit)] for unit in UNITS}
                for membership in ("DESIGN_SPACE", "REFERENCE_SET", "SHUFFLED_CONTROL")},
               "strata": per_stratum, "benchmark": result["benchmark"], "exact_kmers": kmer_summary,
               "shuffled_controls": result["controls_summary"],
               "no_hit_interpretation": "no homology detected under the configured candidate-native BLAST detection settings",
               "positive_self_controls_passed": len(queries) + 1,
               "not_executed": ["full_CDS_decisional_clipping", "Pareto", "dominance", "cells", "representatives", "ranking",
                                "shortlist", "CP4", "Wet_Lab_handoff", "Notebook_03"]}
    design._write_json(out / "cp3_summary.json", summary)
    stable_database = {k: v for k, v in database.items() if k not in {"path", "combined_fasta"}}
    manifest = {"schema_version": 1, "stage": summary["stage"], "git": nb02_design._git_state(root), "python_version": sys.version.split()[0],
                "specificity_evidence_basis": criteria.CANONICAL_EVIDENCE_BASIS,
                "inputs": {"registry_sha256_lf": criteria.registry_sha256(root / criteria.REGISTRY_PATH),
                           "pin_sha256_lf": criteria.pin_sha256(root), "membership_sha256_lf": criteria.registry_sha256(root / criteria.MEMBERSHIP_PATH),
                           "operational_cds_sha256": sha256_text(reference["operational_cds"]), **cp2_provenance},
                "implementation_sha256_lf": criteria.registry_sha256(root / "src/zeaguard/nb03_specificity.py"),
                "blast": {"version": version, "arguments": mechanics.blastn_arguments(policy.search), "outfmt": list(BLAST_OUTFMT_FIELDS)},
                "database": stable_database, "units": {unit: {"role": policy.units[unit][0], "members": sorted(policy.units[unit][1]),
                                                              "relationship_status": policy.relationships[unit]} for unit in UNITS},
                "batch_query_counts": {name: len(group) for name, group in batch_groups},
                "query_fasta_sha256": query_hashes, "raw_hsp_sha256": raw_hashes,
                "outputs_sha256": {name: design._sha256(out / name) for name in EVIDENCE_FILES if name != "run_manifest.json"},
                "runtime_provenance": {"file": "execution_log.json", "includes": ["complete_commands", "UTC_timestamps", "database_binary_hashes"],
                                       "volatile_metadata_excluded_from_deterministic_evidence": True}}
    design._write_json(out / "run_manifest.json", manifest)
    design._write_json(out / "execution_log.json", {"commands": log.entries,
                       "database_binary_sha256": {p.name: design._sha256(p) for p in sorted((out / "blastdb").iterdir()) if p.suffix != ".fasta"}})
    result.update(summary=summary, manifest=manifest, outputs_sha256={name: design._sha256(out / name) for name in EVIDENCE_FILES})
    return result


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp3(find_project_root())
    print(json.dumps({"candidate_query_count": result["summary"]["candidate_query_count"],
                      "benchmark_query_count": 1, "hsp_counts": result["summary"]["hsp_counts_by_membership_and_unit"],
                      "outputs_sha256": result["outputs_sha256"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
