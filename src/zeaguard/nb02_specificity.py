"""NB02 checkpoint 3: specificity EVIDENCE for the operational CDS (no decisions).

The operational CDS is searched with the pre-registered BLASTn settings against one combined
database (the whole D. maidis TSA plus the published cDNAs). Every HSP is classified by the frozen
biological units of the registry (DSRNASE1, DSRNASE3, BICC, KNOWN_DSRNASE2_COMPATIBLE, OTHER_TRANSCRIPT),
the alignments are rebuilt from BTOP, and each candidate interval is evaluated on the part of every
alignment that lies INSIDE the interval. Evidence is aggregated within a unit and never pooled across
units. Nothing here excludes, ranks, forms cells or recommends: E-values, exact 19-mer and 21-mer counts
and the shuffled controls are descriptors only, and OTHER_TRANSCRIPT never enters the vector.

Coordinates are 1-based inclusive on the CDS in coding orientation (BLAST reports the query ascending).
"""

from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
from typing import Any, Iterable, Sequence

from zeaguard import nb01_identity, nb02_criteria, nb02_design, nb02_reference
from zeaguard.nb01_dsrnase_investigation import (
    BLAST_OUTFMT_FIELDS, CommandLog, Hsp, merge_intervals, parse_hsp_table, union_length, write_tsv,
)

OUTPUT_DIR = Path("results/bioinformatics/nb02/cp3")
KNOWN = "KNOWN_DSRNASE2_COMPATIBLE"
OTHER = "OTHER_TRANSCRIPT"
UNIT_METRICS = (
    "longest_exact_match_clipped", "covered_nt_clipped", "best_local_identity_clipped",
    "best_identity_aligned_nt_clipped", "n_hsps_clipped", "exact_19mer_count_clipped",
    "exact_21mer_count_clipped", "hit_records",
)
# CP3 produces evidence only: no output column may belong to cells, ranking, Pareto, shortlist or recommendation.
FORBIDDEN_COLUMN_FRAGMENTS = ("cell", "tier", "rank", "_score", "score_", "pareto", "shortlist", "recommend", "dominat")


class NB02SpecificityError(RuntimeError):
    """The specificity evidence cannot be produced as pre-registered."""


# --------------------------------------------------------------------------- registry-driven policy
@dataclass(frozen=True)
class Policy:
    units: dict[str, tuple[str, frozenset[str]]]  # unit -> (group, members)
    known: frozenset[str]
    search: dict[str, Any]
    shuffle_seeds: tuple[int, ...]

    @property
    def unit_names(self) -> tuple[str, ...]:
        return tuple(self.units)

    def classify(self, subject: str) -> str:
        """Biological class of a database record: a unit, KNOWN_DSRNASE2_COMPATIBLE, or OTHER_TRANSCRIPT."""
        if subject in self.known:
            return KNOWN
        for name, (_, members) in self.units.items():
            if subject in members:
                return name
        return OTHER


def load_policy(registry: dict[str, Any]) -> Policy:
    policy = registry["policy"]
    criteria = {c["name"]: c for c in registry["criteria"]}
    return Policy(
        units={name: (unit["group"], frozenset(unit["members"])) for name, unit in policy["specificity_units"].items()},
        known=frozenset(policy["known_dsrnase2_compatible_excluded_from_risk"]),
        search=dict(criteria["search_detection_limit"]["threshold"]),
        shuffle_seeds=tuple(criteria["shuffled_control"]["threshold"]["seeds"]),
    )


def blastn_arguments(search: dict[str, Any]) -> list[str]:
    return [
        "-task", str(search["task"]), "-dust", str(search["dust"]), "-word_size", str(search["word_size"]),
        "-evalue", str(search["evalue_report_limit"]), "-strand", str(search["strand"]),
        "-max_target_seqs", str(search["max_target_seqs"]), "-num_threads", "1",
    ]


# --------------------------------------------------------------------------- alignments rebuilt from BTOP
@dataclass(frozen=True)
class Footprint:
    """One HSP on the query: exact runs and prefix sums over its query positions (BLAST query is ascending)."""

    hsp_id: str
    subject: str
    cls: str
    strand: str
    q_lo: int
    q_hi: int
    runs: tuple[tuple[int, int], ...]  # maximal runs of identical columns, as query intervals (1-based inclusive)
    ident_cum: tuple[int, ...]  # identical columns among the first i query positions
    ins_cum: tuple[int, ...]  # query-gap columns (subject-only bases) after the first i query positions


_BTOP = re.compile(r"(\d+)|([A-Za-z*-])([A-Za-z*-])")


def btop_columns(btop: str) -> list[tuple[str, str]]:
    """BTOP -> alignment columns ``(query_char, subject_char)``; matches are ``("=", "=")``.

    A pair ``(q, "-")`` is a query base against a subject gap; ``("-", s)`` is a subject base against
    a query gap (a column without a query position). Characters are read as written, so the result is
    independent of strand: BLAST lists the alignment along the ascending query.
    """
    columns: list[tuple[str, str]] = []
    for count, query_char, subject_char in _BTOP.findall(btop):
        if count:
            columns.extend([("=", "=")] * int(count))
        else:
            columns.append((query_char, subject_char))
    return columns


def hsp_identifier(hsp: Hsp) -> str:
    return f"{hsp.query}|{hsp.subject}|{hsp.qstart}-{hsp.qend}|{hsp.sstart}-{hsp.send}"


def footprint_from_btop(hsp_id: str, subject: str, cls: str, strand: str, q_lo: int, q_hi: int, btop: str) -> Footprint:
    identical: list[int] = []
    insertions: list[int] = []
    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    position = q_lo - 1
    for query_char, subject_char in btop_columns(btop):
        if query_char == "-":  # subject base against a query gap: no query position, breaks any exact run
            if insertions:
                insertions[-1] += 1
            if run_start is not None:
                runs.append((run_start, position))
                run_start = None
            continue
        position += 1
        exact = query_char == "=" and subject_char == "="
        identical.append(int(exact))
        insertions.append(0)
        if exact:
            run_start = run_start if run_start is not None else position
        elif run_start is not None:
            runs.append((run_start, position - 1))
            run_start = None
    if run_start is not None:
        runs.append((run_start, position))
    if position != q_hi or len(identical) != q_hi - q_lo + 1:
        raise NB02SpecificityError(f"{hsp_id}: BTOP spans {len(identical)} query positions, HSP says {q_hi - q_lo + 1}")
    ident_cum, ins_cum = [0], [0]
    for flag, extra in zip(identical, insertions):
        ident_cum.append(ident_cum[-1] + flag)
        ins_cum.append(ins_cum[-1] + extra)
    return Footprint(hsp_id, subject, cls, strand, q_lo, q_hi, tuple(runs), tuple(ident_cum), tuple(ins_cum))


def footprint(hsp: Hsp, cls: str) -> Footprint:
    low, high = hsp.query_interval
    return footprint_from_btop(hsp_identifier(hsp), hsp.subject, cls, hsp.strand, low, high, hsp.btop)


# --------------------------------------------------------------------------- clipping and unit aggregation
@dataclass(frozen=True)
class Clip:
    hsp_id: str
    subject: str
    lo: int
    hi: int
    aligned_nt: int
    identity: float
    longest_exact: int
    runs: tuple[tuple[int, int], ...]


def clip_footprint(fp: Footprint, start: int, end: int) -> Clip | None:
    """The part of an alignment inside [start, end]; ``None`` when no query nt remains (it contributes nothing).

    Columns kept: every query position in the interval plus the subject-only columns between two kept
    positions; a gap column at either border is dropped. Identity = identical columns / kept columns.
    """
    lo, hi = max(start, fp.q_lo), min(end, fp.q_hi)
    if hi < lo:
        return None
    first, last = lo - fp.q_lo, hi - fp.q_lo
    aligned = hi - lo + 1
    identical = fp.ident_cum[last + 1] - fp.ident_cum[first]
    extra = fp.ins_cum[last] - fp.ins_cum[first]
    runs = tuple((max(a, lo), min(b, hi)) for a, b in fp.runs if b >= lo and a <= hi)
    longest = max((b - a + 1 for a, b in runs), default=0)
    return Clip(fp.hsp_id, fp.subject, lo, hi, aligned, identical / (aligned + extra), longest, runs)


def _kmer_count(clips: Iterable[Clip], k: int) -> int:
    starts = [(a, b - k + 1) for clip in clips for a, b in clip.runs if b - a + 1 >= k]
    return union_length(starts)


def unit_evidence(footprints: Sequence[Footprint], start: int, end: int) -> dict[str, Any]:
    """Clipped evidence of ONE biological unit for the interval [start, end].

    Longest exact match = maximum over the unit's clipped HSPs; covered nt = union of query positions over
    all records and HSPs of the unit (a redundant record never adds); best local identity = maximum, reported
    with the aligned nt of the HSP that gave it (ties: more aligned nt, then HSP id). Never pooled across units.
    """
    clips = [clip for fp in footprints if (clip := clip_footprint(fp, start, end)) is not None]
    if not clips:
        return {"longest_exact_match_clipped": 0, "covered_nt_clipped": 0, "best_local_identity_clipped": 0.0,
                "best_identity_aligned_nt_clipped": 0, "n_hsps_clipped": 0, "exact_19mer_count_clipped": 0,
                "exact_21mer_count_clipped": 0, "hit_records": ""}
    best = min(clips, key=lambda c: (-c.identity, -c.aligned_nt, c.hsp_id))
    return {
        "longest_exact_match_clipped": max(c.longest_exact for c in clips),
        "covered_nt_clipped": union_length((c.lo, c.hi) for c in clips),
        "best_local_identity_clipped": best.identity,
        "best_identity_aligned_nt_clipped": best.aligned_nt,
        "n_hsps_clipped": len(clips),
        "exact_19mer_count_clipped": _kmer_count(clips, 19),
        "exact_21mer_count_clipped": _kmer_count(clips, 21),
        "hit_records": ",".join(sorted({c.subject for c in clips})),
    }


def vector(evidence: dict[str, Any]) -> tuple[float, float, float]:
    """The Pareto vector of one unit: (longest exact, covered nt, best local identity); lower is better."""
    return (evidence["longest_exact_match_clipped"], evidence["covered_nt_clipped"], evidence["best_local_identity_clipped"])


def candidate_evidence(footprints_by_class: dict[str, list[Footprint]], start: int, end: int) -> dict[str, dict[str, Any]]:
    """Evidence of every class for one interval (used for the benchmark and, later, for provisional candidates)."""
    return {cls: unit_evidence(fps, start, end) for cls, fps in footprints_by_class.items()}


# --------------------------------------------------------------------------- the persisted evidence (HSP provenance)
PROVENANCE_COLUMNS = (
    "hsp_id", "query", "subject", "class", "strand", "qstart", "qend", "sstart", "send", "pident", "alignment_length",
    "mismatch", "gaps", "evalue", "bitscore", "longest_exact_match_full", "exact_19mer_count_full",
    "exact_21mer_count_full", "btop",
)


def provenance_rows(hsps: Sequence[Hsp], policy: Policy) -> list[dict[str, Any]]:
    rows = []
    for hsp in hsps:
        fp = footprint(hsp, policy.classify(hsp.subject))
        rows.append({
            "hsp_id": fp.hsp_id, "query": hsp.query, "subject": hsp.subject, "class": fp.cls, "strand": hsp.strand,
            "qstart": fp.q_lo, "qend": fp.q_hi, "sstart": hsp.sstart, "send": hsp.send, "pident": hsp.pident,
            "alignment_length": hsp.length, "mismatch": hsp.mismatch, "gaps": hsp.gaps, "evalue": f"{hsp.evalue:.3g}",
            "bitscore": hsp.bitscore,
            "longest_exact_match_full": max((b - a + 1 for a, b in fp.runs), default=0),
            "exact_19mer_count_full": union_length((a, b - 18) for a, b in fp.runs if b - a + 1 >= 19),
            "exact_21mer_count_full": union_length((a, b - 20) for a, b in fp.runs if b - a + 1 >= 21),
            "btop": hsp.btop,
        })
    return rows


def load_footprints(provenance_tsv: Path, query: str = "operational_cds") -> dict[str, list[Footprint]]:
    """Rebuild the footprints of one query from the persisted provenance table (no BLAST rerun needed)."""
    by_class: dict[str, list[Footprint]] = defaultdict(list)
    with Path(provenance_tsv).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["query"] == query:
                by_class[row["class"]].append(footprint_from_btop(
                    row["hsp_id"], row["subject"], row["class"], row["strand"], int(row["qstart"]), int(row["qend"]), row["btop"]))
    return dict(by_class)


# --------------------------------------------------------------------------- database and search
def _log_run(log: CommandLog, command: list[str], stdout_path: Path | None = None) -> str:
    return log.run(command, stdout_path=stdout_path)


def build_database(root: Path, out: Path, policy: Policy, log: CommandLog) -> dict[str, Any]:
    """Combined database: every TSA record (plain accession ids) plus the published cDNAs of the anchors."""
    tsa_path, tsa_sha = nb02_reference.validated_tsa_path(root)
    db_dir = out / "blastdb"
    db_dir.mkdir(parents=True, exist_ok=True)
    combined = db_dir / "combined.fasta"
    ids: set[str] = set()
    n_tsa = 0
    with combined.open("w", encoding="ascii", newline="\n") as handle:
        for record in nb01_identity.parse_fasta(tsa_path):
            accession = nb01_identity.canonical_tsa_accession(record.identifier)
            handle.write(f">{accession}\n{record.sequence}\n")
            ids.add(accession)
            n_tsa += 1
        anchors = list(nb01_identity.parse_fasta(root / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH))
        for record in anchors:
            if record.identifier in ids:
                raise NB02SpecificityError(f"identifier collision between the TSA and the anchors: {record.identifier}")
            handle.write(f">{record.identifier}\n{record.sequence}\n")
            ids.add(record.identifier)
    required = set(policy.known) | {m for _, members in policy.units.values() for m in members}
    if required - ids:
        raise NB02SpecificityError(f"unit or known records missing from the database: {sorted(required - ids)}")
    database = db_dir / "nb02_cp3"
    _log_run(log, ["makeblastdb", "-in", str(combined), "-dbtype", "nucl", "-out", str(database), "-title", "nb02_cp3"])
    info = _log_run(log, ["blastdbcmd", "-db", str(database), "-info"])
    match = re.search(r"([\d,]+) sequences; ([\d,]+) total bases", info)
    return {
        "database": str(database),
        "tsa_file_sha256": tsa_sha,
        "n_tsa_records": n_tsa,
        "published_cdna_records": [record.identifier for record in anchors],
        "n_sequences": int(match.group(1).replace(",", "")) if match else None,
        "total_bases": int(match.group(2).replace(",", "")) if match else None,
        "combined_fasta_sha256": hashlib.sha256(combined.read_bytes()).hexdigest(),
    }


def shuffled_sequence(sequence: str, seed: int) -> str:
    """Composition-preserving (mononucleotide) shuffle with a fixed seed; a descriptive control only."""
    letters = list(sequence)
    random.Random(seed).shuffle(letters)
    return "".join(letters)


def run_blast(cds: str, seeds: Sequence[int], database: str, search: dict[str, Any], out: Path, log: CommandLog) -> list[Hsp]:
    queries = out / "queries.fasta"
    text = f">operational_cds\n{cds}\n" + "".join(f">shuffle_{seed}\n{shuffled_sequence(cds, seed)}\n" for seed in seeds)
    queries.write_text(text, encoding="ascii", newline="\n")
    table = out / "blastn_raw.outfmt6.tsv"
    command = ["blastn", "-query", str(queries), "-db", database, *blastn_arguments(search),
               "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)]
    _log_run(log, command, stdout_path=table)
    hsps = parse_hsp_table(table.read_text(encoding="utf-8"))
    return sorted(hsps, key=lambda h: (h.query, h.subject, h.qstart, h.qend, h.sstart, h.send, h.btop))


def blast_version(log: CommandLog) -> str:
    return " | ".join(line.strip() for line in _log_run(log, ["blastn", "-version"]).splitlines()[:2])


# --------------------------------------------------------------------------- independent exact k-mer self-check
def exact_kmer_scan(cds: str, records: Iterable[tuple[str, str]], policy: Policy) -> dict[int, dict[str, set[int]]]:
    """Query start positions of exact 19-mers and 21-mers (both strands) found in each class, by direct scan."""
    index: dict[int, dict[str, set[int]]] = {19: defaultdict(set), 21: defaultdict(set)}
    for k in (19, 21):
        for i in range(len(cds) - k + 1):
            word = cds[i : i + k]
            index[k][word].add(i + 1)
            index[k][nb01_identity.reverse_complement(word)].add(i + 1)
    found: dict[int, dict[str, set[int]]] = {19: defaultdict(set), 21: defaultdict(set)}
    words19, words21 = index[19], index[21]
    for accession, sequence in records:
        cls = policy.classify(accession)
        for j in range(len(sequence) - 18):
            hit = words19.get(sequence[j : j + 19])
            if hit is None:
                continue
            found[19][cls].update(hit)
            hit21 = words21.get(sequence[j : j + 21])
            if hit21 is not None:
                found[21][cls].update(hit21)
    return found


def kmer_selfcheck(footprints_by_class: dict[str, list[Footprint]], scan: dict[int, dict[str, set[int]]]) -> dict[str, Any]:
    """Compare the k-mer starts read from BLAST/BTOP with the direct scan, per class (descriptive agreement report)."""
    report: dict[str, Any] = {}
    classes = set(footprints_by_class) | set(scan[19]) | set(scan[21])
    for cls in sorted(classes):
        for k in (19, 21):
            blast_starts = {s for fp in footprints_by_class.get(cls, []) for a, b in fp.runs if b - a + 1 >= k for s in range(a, b - k + 2)}
            direct = scan[k].get(cls, set())
            report[f"{cls}_k{k}"] = {
                "blast_btop": len(blast_starts), "direct_scan": len(direct),
                "only_in_direct_scan": len(direct - blast_starts), "only_in_blast_btop": len(blast_starts - direct),
            }
    return report


# --------------------------------------------------------------------------- summaries
def _quantiles(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"min": ordered[0], "median": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], "max": ordered[-1]}


def subject_summary(footprints: Sequence[Footprint], hsps_by_id: dict[str, Hsp]) -> list[dict[str, Any]]:
    """One row per hit record (class, covered nt of the full alignments, longest exact run, best identity, E-value)."""
    by_subject: dict[str, list[Footprint]] = defaultdict(list)
    for fp in footprints:
        by_subject[fp.subject].append(fp)
    rows = []
    for subject, fps in by_subject.items():
        hsps = [hsps_by_id[fp.hsp_id] for fp in fps]
        rows.append({
            "subject": subject, "class": fps[0].cls, "n_hsps": len(fps),
            "covered_nt_full": union_length((fp.q_lo, fp.q_hi) for fp in fps),
            "longest_exact_match_full": max((b - a + 1 for fp in fps for a, b in fp.runs), default=0),
            "best_identity_full": max(h.pident for h in hsps), "min_evalue": f"{min(h.evalue for h in hsps):.3g}",
        })
    # inspection order only (class, then covered nt descending): it is not a decision rule
    return sorted(rows, key=lambda r: (r["class"], -r["covered_nt_full"], r["subject"]))


def position_tracks(footprints_by_class: dict[str, list[Footprint]], cds_length: int, class_order: Sequence[str]) -> list[dict[str, Any]]:
    depth = {cls: [0] * (cds_length + 1) for cls in class_order}
    longest = {cls: [0] * (cds_length + 1) for cls in class_order}
    for cls in class_order:
        for fp in footprints_by_class.get(cls, []):
            for position in range(fp.q_lo, fp.q_hi + 1):
                depth[cls][position] += 1
            for a, b in fp.runs:
                for position in range(a, b + 1):
                    longest[cls][position] = max(longest[cls][position], b - a + 1)
    rows = []
    for position in range(1, cds_length + 1):
        row: dict[str, Any] = {"cds_pos": position}
        for cls in class_order:
            row[f"{cls}_hsp_depth"] = depth[cls][position]
            row[f"{cls}_longest_exact_full_covering"] = longest[cls][position]
        rows.append(row)
    return rows


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _window_columns(unit_names: Sequence[str]) -> tuple[str, ...]:
    base = ("candidate_id", "length_stratum", "length_nt", "cds_start", "cds_end")
    return base + tuple(f"{unit.lower()}_{metric}" for unit in unit_names for metric in UNIT_METRICS)


def _flatten(unit: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {f"{unit.lower()}_{metric}": (f"{value:.6f}" if isinstance(value, float) else value) for metric, value in evidence.items()}


# --------------------------------------------------------------------------- the checkpoint
def run_cp3(root: Path, output_dir: Path | None = None, kmer_scan: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    registry = nb02_criteria.load_registry(root)
    policy = load_policy(registry)
    parameters = nb02_design.design_parameters(registry)
    reference = nb02_reference.verified_reference(root)
    cds = reference["operational_cds"]
    out = Path(output_dir) if output_dir else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    log = CommandLog()

    version = blast_version(log)
    composition = build_database(root, out, policy, log)
    hsps = run_blast(cds, policy.shuffle_seeds, composition["database"], policy.search, out, log)
    hsps_by_id = {hsp_identifier(h): h for h in hsps}
    classes = (*policy.unit_names, KNOWN, OTHER)

    operational = [h for h in hsps if h.query == "operational_cds"]
    provenance = provenance_rows(operational, policy)
    write_tsv(out / "hsp_provenance.tsv", provenance, PROVENANCE_COLUMNS)
    footprints = [footprint(h, policy.classify(h.subject)) for h in operational]
    by_class: dict[str, list[Footprint]] = {cls: [fp for fp in footprints if fp.cls == cls] for cls in classes}

    # per-window clipped evidence of the decisional units for the CP2 strata (OTHER_TRANSCRIPT is not computed per window)
    windows = []
    unit_footprints = {unit: by_class[unit] for unit in policy.unit_names}
    for length, label in parameters.strata.items():
        for start in nb02_design.windows_of_length(parameters.cds_length, length):
            end = start + length - 1
            row: dict[str, Any] = {"candidate_id": nb02_design.window_id(length, start, end), "length_stratum": label,
                                   "length_nt": length, "cds_start": start, "cds_end": end}
            for unit in policy.unit_names:
                row.update(_flatten(unit, unit_evidence(unit_footprints[unit], start, end)))
            windows.append(row)
    window_columns = _window_columns(policy.unit_names)
    write_tsv(out / "specificity_windows.tsv", windows, window_columns)

    # the published benchmark in every class, including OTHER_TRANSCRIPT and the known records (reference set)
    pin = reference["pin"]["benchmark"]["interval"]
    benchmark = candidate_evidence(by_class, pin["cds_start"], pin["cds_end"])
    bench_rows = [{"candidate_id": reference["pin"]["benchmark"]["id"], "class": cls,
                   **{m: (f"{v:.6f}" if isinstance(v, float) else v) for m, v in ev.items()}} for cls, ev in benchmark.items()]
    write_tsv(out / "benchmark_specificity.tsv", bench_rows, ("candidate_id", "class", *UNIT_METRICS))

    summary_rows = subject_summary(footprints, hsps_by_id)
    write_tsv(out / "subject_summary.tsv", summary_rows,
              ("subject", "class", "n_hsps", "covered_nt_full", "longest_exact_match_full", "best_identity_full", "min_evalue"))
    tracks = position_tracks(by_class, len(cds), classes)
    track_columns = ("cds_pos", *[f"{cls}_{kind}" for cls in classes for kind in ("hsp_depth", "longest_exact_full_covering")])
    write_tsv(out / "position_specificity_tracks.tsv", tracks, track_columns)

    other_rows = [r for r in provenance if r["class"] == OTHER]
    other_summary = {
        "n_hsps": len(other_rows),
        "n_records_hit": len({r["subject"] for r in other_rows}),
        "longest_exact_match_full": _quantiles([r["longest_exact_match_full"] for r in other_rows]),
        "n_hsps_with_exact_19mer": sum(r["exact_19mer_count_full"] > 0 for r in other_rows),
        "n_hsps_with_exact_21mer": sum(r["exact_21mer_count_full"] > 0 for r in other_rows),
        "record_covered_nt_full": _quantiles([r["covered_nt_full"] for r in summary_rows if r["class"] == OTHER]),
        "records_by_covered_nt_full_top10": [r for r in summary_rows if r["class"] == OTHER][:10],
        "role": "DESCRIPTOR + MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW; outside the vector, Pareto, cells and primary ordering",
    }

    # MANUAL_REVIEW_TRIGGER: every HSP against a decisional unit is listed for the reviewer (no cutoff)
    triggers = [{"trigger": "UNIT_HSP_PRESENT", "unit": r["class"], "group": policy.units[r["class"]][0], "hsp_id": r["hsp_id"],
                 "subject": r["subject"], "qstart": r["qstart"], "qend": r["qend"], "longest_exact_match_full": r["longest_exact_match_full"],
                 "pident": r["pident"], "alignment_length": r["alignment_length"], "evalue_provenance": r["evalue"], "status": "PENDING"}
                for r in provenance if r["class"] in policy.unit_names]
    write_tsv(out / "manual_review.tsv", triggers,
              ("trigger", "unit", "group", "hsp_id", "subject", "qstart", "qend", "longest_exact_match_full", "pident",
               "alignment_length", "evalue_provenance", "status"))

    # shuffled controls: the same pipeline on non-biological input (descriptive sanity check only)
    control_rows = []
    ranking = parameters.ranking_length
    for query in ("operational_cds", *[f"shuffle_{seed}" for seed in policy.shuffle_seeds]):
        q_hsps = [h for h in hsps if h.query == query]
        q_fps = [footprint(h, policy.classify(h.subject)) for h in q_hsps]
        row: dict[str, Any] = {"query": query, "n_hsps_total": len(q_hsps),
                               "n_hsps_with_exact_21mer": sum(any(b - a + 1 >= 21 for a, b in fp.runs) for fp in q_fps),
                               "longest_exact_match_full_max": max((b - a + 1 for fp in q_fps for a, b in fp.runs), default=0)}
        for cls in classes:
            row[f"n_hsps_{cls}"] = sum(fp.cls == cls for fp in q_fps)
        for unit in policy.unit_names:
            unit_fps = [fp for fp in q_fps if fp.cls == unit]
            evidence = [unit_evidence(unit_fps, s, s + ranking - 1) for s in nb02_design.windows_of_length(parameters.cds_length, ranking)]
            row[f"{unit}_windows_with_any_hsp"] = sum(e["n_hsps_clipped"] > 0 for e in evidence)
            row[f"{unit}_max_longest_exact_clipped"] = max(e["longest_exact_match_clipped"] for e in evidence)
            row[f"{unit}_max_covered_nt_clipped"] = max(e["covered_nt_clipped"] for e in evidence)
        control_rows.append(row)
    write_tsv(out / "shuffled_control_summary.tsv", control_rows)

    selfcheck = None
    if kmer_scan:
        tsa_path, _ = nb02_reference.validated_tsa_path(root)
        records = ((nb01_identity.canonical_tsa_accession(r.identifier), r.sequence) for r in nb01_identity.parse_fasta(tsa_path))
        anchors = ((r.identifier, r.sequence) for r in nb01_identity.parse_fasta(root / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH))
        scan = exact_kmer_scan(cds, _chain(records, anchors), policy)
        selfcheck = kmer_selfcheck(by_class, scan)
        (out / "kmer_selfcheck.json").write_text(json.dumps(selfcheck, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "other_transcript_descriptive_summary.json").write_text(
        json.dumps(other_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    for columns in (PROVENANCE_COLUMNS, window_columns, track_columns, UNIT_METRICS):
        offenders = [c for c in columns if any(f in c for f in FORBIDDEN_COLUMN_FRAGMENTS)]
        if offenders:
            raise NB02SpecificityError(f"CP3 outputs must stay descriptive; offending columns: {offenders}")

    per_class = {cls: {"n_hsps": sum(fp.cls == cls for fp in footprints),
                       "n_records": len({fp.subject for fp in footprints if fp.cls == cls})} for cls in classes}
    files = ["hsp_provenance.tsv", "specificity_windows.tsv", "benchmark_specificity.tsv", "subject_summary.tsv",
             "position_specificity_tracks.tsv", "manual_review.tsv", "shuffled_control_summary.tsv",
             "other_transcript_descriptive_summary.json", "blastn_raw.outfmt6.tsv", "queries.fasta"]
    if selfcheck is not None:
        files.append("kmer_selfcheck.json")
    manifest = {
        "stage": "NB02 CP3 (specificity evidence; no decisions, cells, ranking or shortlist)",
        "git": nb02_design._git_state(root),
        "python": sys.version.split()[0],
        "inputs": {
            "criteria_registry_sha256": nb02_criteria.registry_sha256(root / nb02_criteria.REGISTRY_PATH),
            "pin_sha256": reference["report"]["pin_sha256_lf"],
            "operational_cds_sha256": reference["report"]["operational"]["cds_sha256"],
        },
        "blast": {"version": version, "arguments": blastn_arguments(policy.search), "outfmt": BLAST_OUTFMT_FIELDS,
                  "e_values_depend_on_database_size": composition["total_bases"]},
        "database": {k: v for k, v in composition.items() if k != "database"},
        "units": {name: {"group": group, "members": sorted(members)} for name, (group, members) in policy.units.items()},
        "hsps_by_class_operational_query": per_class,
        "n_hsps_all_queries": len(hsps),
        "counts": {"specificity_windows": len(windows), "manual_review_rows": len(triggers), "shuffled_queries": len(policy.shuffle_seeds)},
        "kmer_selfcheck": selfcheck,
        "commands": log.entries,
        "outputs_sha256": {name: _sha256_lf(out / name) for name in files},
        "not_done": ["cells", "Pareto comparison", "ranking", "shortlist", "OTHER_TRANSCRIPT review of any candidate",
                     "ecological off-target"],
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
                                           encoding="utf-8", newline="\n")
    return {"manifest": manifest, "hsps": hsps, "provenance": provenance, "windows": windows, "benchmark": benchmark,
            "subjects": summary_rows, "controls": control_rows, "other_summary": other_summary, "triggers": triggers,
            "selfcheck": selfcheck, "by_class": by_class}


def _chain(*iterables: Iterable[Any]):
    for iterable in iterables:
        yield from iterable


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp3(find_project_root())
    print(json.dumps(result["manifest"]["hsps_by_class_operational_query"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
