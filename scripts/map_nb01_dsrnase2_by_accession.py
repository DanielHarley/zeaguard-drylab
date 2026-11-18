#!/usr/bin/env python3
"""Map the two complete TSA records attributed to Dmai-dsRNase-2 separately, one query per accession.

The historical mapping queried the published dsRNase-2 CDS once and could not say
which TSA record came from which locus. This run keeps the two records apart:
`GITV01008430.1` and `GITV01012450.1` carry CDS of the same length that are not
the same sequence, differing at seven positions, six of them IUPAC symbols and
one a defined substitution at CDS position 816.

Search parameters, locus formation, tiling, reporting tier and the one-locus
assignment rule come unchanged from ADR 0009 via `zeaguard.nb01_locus`. This
module adds no threshold of its own. What it adds is a per-position audit of the
seven informative positions, read from BLAST's own BTOP alignment, kept strictly
apart from BLAST's conventional identity.

Two things are deliberately kept apart throughout:

* the **geometry** of the alignments (which sequence, which span, which strand,
  which chain of blocks) from the **biological attribution** drawn from it.
  Two candidates sharing a span is a geometric coincidence; it becomes evidence
  for one shared locus only with the same strand and a concordant block chain.
* an **ambiguous genomic base** from both exact agreement and defined
  divergence. It is neither, and is recorded as its own verdict.

The repeat-bearing 3' flank of `GITV01012450.1` is not queried here. Nothing of
the historical run is read as writable or modified: this run claims a directory
of its own, exclusively, for the whole of its execution.
"""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeaguard import nb01_identity  # noqa: E402
from zeaguard.nb01_dsrnase_investigation import (  # noqa: E402
    IUPAC_EXPANSION,
    UNAMBIGUOUS_DNA,
    CommandLog,
    Hsp,
    format_fasta,
    parse_btop,
    sha256_file,
    sha256_text,
    write_tsv,
)
from zeaguard.nb01_locus import (  # noqa: E402
    ASSIGNMENT_MIN_IDENTITY_PCT,
    LOCUS_MIN_QUERY_COVERAGE_PCT,
    RELATED_LOCUS_MIN_COVERAGE_PCT,
    LocusInputError,
    _blast_with_archive,
    _check_hash,
    _resolve,
    check_declared_stats,
    cluster_loci,
    load_panel,
    scan_assembly,
    tile_hsps,
    tiled_coverage_pct,
)


def _load_sibling_script(name: str):
    """Import a sibling script as a module, to reuse what it already implements."""
    path = Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# The exclusive, atomic output-directory claim written for the Bloco 3 splice
# check: created with O_CREAT|O_EXCL, held until the last write, contents
# inspected under the claim. Reused rather than reimplemented.
_splice_check = _load_sibling_script("check_nb01_dsrnase_splicing.py")
reserve_output_dir = _splice_check.reserve_output_dir

DEFAULT_PANEL = Path("data/reference/nb01_dsrnase2_accession_panel.json")
DEFAULT_OUT = Path("results/bioinformatics/nb01/mappings/dsrnase2_by_accession_v1")

PANEL_KIND = "nb01_dsrnase2_accession_panel"
PANEL_SCHEMA_VERSION = 1

# Per-position verdicts. Each is a statement about one query base against one
# subject base; they are never summed into an identity figure, which stays
# BLAST's own.
EXACT = "EXACT"
AMBIGUITY_COMPATIBLE = "AMBIGUITY_COMPATIBLE"
AMBIGUITY_INCOMPATIBLE = "AMBIGUITY_INCOMPATIBLE"
SUBJECT_AMBIGUOUS = "SUBJECT_AMBIGUOUS"
DEFINED_MISMATCH = "DEFINED_MISMATCH"
GAP_IN_SUBJECT = "GAP_IN_SUBJECT"
NO_COVERAGE = "NO_COVERAGE"
CONFLICTING_HSPS = "CONFLICTING_HSPS"

DETERMINED = "DETERMINED"
INDETERMINATE = "INDETERMINATE"

COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVNacgtryswkmbdhvn",
                           "TGCAYRSWMKVHDBNtgcayrswmkvhdbn")


class AccessionMappingError(RuntimeError):
    """A declared input did not verify, or an alignment could not be walked."""


def complement(base: str) -> str:
    return base.translate(COMPLEMENT)


# --------------------------------------------------------------------------- panel
def load_accession_panel(path: Path) -> dict[str, object]:
    """Load the per-accession panel, refusing anything that is not one.

    The assemblies panel keeps its own historical loader: the two panels declare
    different things and are validated by different contracts.
    """
    if not path.is_file():
        raise AccessionMappingError(f"accession panel is missing: {path}")
    try:
        panel = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AccessionMappingError(f"{path.name}: not valid JSON: {error}") from None
    if not isinstance(panel, dict):
        raise AccessionMappingError(f"{path.name}: panel must be a JSON object")

    kind = panel.get("kind")
    if kind != PANEL_KIND:
        raise AccessionMappingError(
            f"{path.name}: declares kind={kind!r}, this run requires {PANEL_KIND!r}")
    version = panel.get("schema_version")
    if version != PANEL_SCHEMA_VERSION:
        raise AccessionMappingError(
            f"{path.name}: declares schema_version={version!r}, "
            f"this run implements {PANEL_SCHEMA_VERSION}")

    for field in ("tsa", "assemblies_panel", "queries", "informative_positions",
                  "discriminating_position"):
        if field not in panel:
            raise AccessionMappingError(f"{path.name}: panel has no {field!r}")

    queries = panel["queries"]
    if not isinstance(queries, list) or len(queries) != 2:
        raise AccessionMappingError(
            f"{path.name}: expected exactly two declared queries, found "
            f"{len(queries) if isinstance(queries, list) else type(queries).__name__}")
    for entry in queries:
        for field in ("query_id", "accession", "record_length", "strand",
                      "cds_tx_start", "cds_tx_end", "cds_length", "cds_sha256"):
            if field not in entry:
                raise AccessionMappingError(
                    f"{path.name}: query {entry.get('accession', '?')} has no {field!r}")

    positions = [int(p["cds_pos"]) for p in panel["informative_positions"]]
    discriminating = int(panel["discriminating_position"]["cds_pos"])
    if discriminating not in positions:
        raise AccessionMappingError(
            f"{path.name}: discriminating position {discriminating} is not among the "
            f"declared informative positions {positions}")
    return panel


# --------------------------------------------------------------------------- BTOP walk
@dataclass(frozen=True)
class Column:
    """One alignment column of an HSP, in query and subject coordinates.

    ``subject_pos`` is ``None`` exactly when the subject has a gap in this column,
    i.e. the query base aligns to nothing. ``subject_base`` is then ``""``.
    """

    query_pos: int | None
    subject_pos: int | None
    op: str
    query_base: str
    subject_base: str


def hsp_id(candidate_id: str, hsp: Hsp, index: int) -> str:
    """A stable identifier for one HSP inside one candidate."""
    low, high = hsp.query_interval
    s_low, s_high = hsp.subject_interval
    return f"{candidate_id}#hsp{index}:q{low}-{high}:s{s_low}-{s_high}:{hsp.strand}"


def walk_btop(hsp: Hsp, query_sequence: str | None = None) -> list[Column]:
    """Every alignment column of ``hsp``, in query and subject coordinates.

    BTOP operation semantics, which are the thing most easily got backwards:

    * ``=``  a run of matches. Both axes advance. The subject base equals the
      query base, so it is filled in from the query.
    * ``X``  a substitution. Both axes advance; both bases are given explicitly.
    * ``I``  a gap in the SUBJECT. The query has a base, the subject has none, so
      the QUERY advances and the subject does not. A query position can land here,
      and when it does there is no subject base to compare it against.
    * ``D``  a gap in the QUERY. The subject has a base, the query has none, so the
      SUBJECT advances and the query does not. A query position can never land on
      a ``D`` column.

    On a minus-strand HSP BLAST reports the query ascending and the subject
    descending, so the subject coordinate is decremented rather than incremented.
    The subject characters BTOP gives are already in the query's orientation; the
    plus-strand base at that coordinate is their complement.

    The walk is verified against the HSP's own end coordinates and refuses a BTOP
    that does not land exactly on them.
    """
    if hsp.qstart > hsp.qend:
        raise AccessionMappingError(
            f"query reported descending ({hsp.qstart}>{hsp.qend}); blastn reports queries ascending")
    if hsp.strand not in ("plus", "minus"):
        raise AccessionMappingError(f"unexpected subject strand {hsp.strand!r}")
    step = 1 if hsp.strand == "plus" else -1
    if (hsp.send - hsp.sstart) * step < 0:
        raise AccessionMappingError(
            f"subject {hsp.sstart}->{hsp.send} does not run {hsp.strand}")

    query_pos = hsp.qstart
    subject_pos = hsp.sstart
    columns: list[Column] = []
    for op, query_char, subject_char in parse_btop(hsp.btop):
        if op == "=":
            base = ""
            if query_sequence is not None:
                base = query_sequence[query_pos - 1]
            columns.append(Column(query_pos, subject_pos, op, base, base))
            query_pos += 1
            subject_pos += step
        elif op == "X":
            columns.append(Column(query_pos, subject_pos, op, query_char, subject_char))
            query_pos += 1
            subject_pos += step
        elif op == "I":  # gap in the subject: query advances, subject does not
            columns.append(Column(query_pos, None, op, query_char, ""))
            query_pos += 1
        elif op == "D":  # gap in the query: subject advances, query does not
            columns.append(Column(None, subject_pos, op, "", subject_char))
            subject_pos += step
        else:
            raise AccessionMappingError(f"unhandled BTOP operation {op!r}")

    if query_pos - 1 != hsp.qend:
        raise AccessionMappingError(
            f"BTOP walk ended at query {query_pos - 1}, HSP declares {hsp.qend}")
    if subject_pos - step != hsp.send:
        raise AccessionMappingError(
            f"BTOP walk ended at subject {subject_pos - step}, HSP declares {hsp.send}")
    return columns


def classify(query_base: str, subject_base: str) -> str:
    """One query base against one subject base.

    An ambiguous base in the *genome* is its own outcome. It is not exact
    agreement, because the assembly does not state which base is there, and it is
    not a defined divergence, because nothing defined has been observed to
    differ. Promoting it to either would invent evidence, so it is reported as
    ``SUBJECT_AMBIGUOUS`` and counted separately.
    """
    if subject_base == "":
        return GAP_IN_SUBJECT
    query, subject = query_base.upper(), subject_base.upper()
    if subject not in UNAMBIGUOUS_DNA:
        return SUBJECT_AMBIGUOUS
    if query not in UNAMBIGUOUS_DNA:
        return (AMBIGUITY_COMPATIBLE if subject in IUPAC_EXPANSION.get(query, "")
                else AMBIGUITY_INCOMPATIBLE)
    return EXACT if query == subject else DEFINED_MISMATCH


def observe_positions(hsp: Hsp, positions: Iterable[int], query_sequence: str,
                      identifier: str = "") -> dict[int, dict[str, object]]:
    """Observation of each requested query position covered by this HSP."""
    wanted = set(positions)
    low, high = hsp.query_interval
    if not any(low <= p <= high for p in wanted):
        return {}
    found: dict[int, dict[str, object]] = {}
    for column in walk_btop(hsp, query_sequence):
        if column.query_pos is None or column.query_pos not in wanted:
            continue
        subject_base = column.subject_base
        found[column.query_pos] = {
            "hsp_id": identifier,
            "subject_sequence_id": hsp.subject,
            "subject_pos": column.subject_pos,
            "strand": hsp.strand,
            "query_base": column.query_base.upper(),
            "subject_base": subject_base.upper(),
            "subject_base_plus_strand": (
                complement(subject_base).upper()
                if subject_base and hsp.strand == "minus" else subject_base.upper()),
            "btop_op": column.op,
            "verdict": classify(column.query_base, subject_base),
        }
    return found


def reconcile(observations: Sequence[dict[str, object]]) -> dict[str, object]:
    """Collapse the observations of one position to a single call, or refuse to.

    Two observations agree only when they place the position at the same subject
    coordinate, on the same sequence and strand, with the same base and the same
    verdict. Agreeing on the base while disagreeing on where it sits is a
    conflict, not an agreement: the tiling tolerates a few nucleotides of query
    overlap, so two HSPs can cover one query position at two different genomic
    coordinates, and that is a fact about the evidence, not a detail to average
    away. The best-scoring HSP is never silently preferred.

    The individual observations are persisted separately; this is only the
    summary.
    """
    if not observations:
        return {"verdict": NO_COVERAGE, "n_hsps_covering": 0}
    keys = {(o["subject_sequence_id"], o["subject_pos"], o["strand"],
             o["subject_base"], o["verdict"]) for o in observations}
    summary = dict(observations[0])
    summary["n_hsps_covering"] = len(observations)
    summary["observed_by_hsps"] = ";".join(str(o.get("hsp_id", "")) for o in observations)
    if len(keys) == 1:
        return summary
    summary["verdict"] = CONFLICTING_HSPS
    summary["conflict_detail"] = "; ".join(
        f"{o['subject_sequence_id']}:{o['subject_pos']}({o['strand']})"
        f"={o['subject_base'] or '-'}/{o['verdict']}" for o in observations)
    return summary


# --------------------------------------------------------------------------- candidates
@dataclass
class Candidate:
    """A reported locus of one query, under the ADR 0009 reporting tier."""

    assembly_id: str
    query_id: str
    candidate_id: str
    subject: str
    strand: str
    start: int
    end: int
    coverage_pct: float
    identity_pct: float
    aligned_nt: int
    matched_nt: int
    mismatch_nt: int
    gaps_nt: int
    n_hsps: int
    hsps: list[Hsp]

    @property
    def eligible(self) -> bool:
        """ADR 0009 rule 5: assignment tier needs both coverage and identity."""
        return (self.coverage_pct >= LOCUS_MIN_QUERY_COVERAGE_PCT
                and self.identity_pct >= ASSIGNMENT_MIN_IDENTITY_PCT)

    @property
    def chain(self) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
        """``(query_interval, subject_interval)`` per block, ordered by query start.

        The correspondence between the two axes is the chain. Ordering by the
        genomic coordinate alone and dropping the query intervals would make two
        alignments that visit the same genomic blocks in opposite query order
        compare equal, which they are not: they describe different transcripts
        over the same ground.
        """
        return tuple((h.query_interval, h.subject_interval)
                     for h in sorted(self.hsps, key=lambda h: h.query_interval))

    @property
    def block_chain(self) -> tuple[tuple[int, int], ...]:
        """The genomic blocks alone, in query order; for display, not comparison."""
        return tuple(subject for _, subject in self.chain)

    @property
    def colinear(self) -> bool:
        """Do the genomic blocks advance in the direction the strand indicates?

        Reading the query from start to end, a plus-strand chain must move
        forward along the genome and a minus-strand chain backward. A chain that
        does not is not a colinear alignment of one transcript, whatever its
        outer bounds say.
        """
        starts = [subject[0] for _, subject in self.chain]
        pairs = list(zip(starts, starts[1:]))
        if not pairs:
            return True
        if self.strand == "plus":
            return all(earlier < later for earlier, later in pairs)
        return all(earlier > later for earlier, later in pairs)


def build_candidates(assembly_id: str, query_id: str, hsps: Sequence[Hsp]) -> list[Candidate]:
    """Cluster, tile and tier the HSPs of one query, by the rules of ADR 0009."""
    candidates: list[Candidate] = []
    for index, members in enumerate(cluster_loci(hsps), start=1):
        tiled = tile_hsps(members)
        coverage = tiled_coverage_pct(tiled)
        if coverage < RELATED_LOCUS_MIN_COVERAGE_PCT:
            continue
        aligned = sum(h.length for h in tiled)
        mismatch = sum(h.mismatch for h in tiled)
        gaps = sum(h.gaps for h in tiled)
        matched = aligned - mismatch - gaps
        identity = 100 * matched / aligned if aligned else 0.0
        starts = [h.subject_interval[0] for h in tiled]
        ends = [h.subject_interval[1] for h in tiled]
        candidates.append(Candidate(
            assembly_id=assembly_id,
            query_id=query_id,
            candidate_id=f"{assembly_id}:{query_id}:{index}",
            subject=tiled[0].subject,
            strand=tiled[0].strand,
            start=min(starts),
            end=max(ends),
            coverage_pct=round(coverage, 3),
            identity_pct=round(identity, 3),
            aligned_nt=aligned,
            matched_nt=matched,
            mismatch_nt=mismatch,
            gaps_nt=gaps,
            n_hsps=len(tiled),
            hsps=list(tiled),
        ))
    candidates.sort(key=lambda c: (-c.coverage_pct, -c.identity_pct, c.start))
    return candidates


def audit_candidate(candidate: Candidate, positions: Sequence[int],
                    query_sequence: str) -> tuple[dict[int, dict[str, object]],
                                                  list[dict[str, object]]]:
    """Per-position summary and the individual observations it was built from."""
    per_position: dict[int, list[dict[str, object]]] = {p: [] for p in positions}
    observations: list[dict[str, object]] = []
    for index, hsp in enumerate(candidate.hsps, start=1):
        identifier = hsp_id(candidate.candidate_id, hsp, index)
        for position, observation in observe_positions(
                hsp, positions, query_sequence, identifier).items():
            per_position[position].append(observation)
            observations.append({"cds_pos": position, **observation})
    return {p: reconcile(obs) for p, obs in per_position.items()}, observations


def assignment_status(candidates: Sequence[Candidate],
                      had_hsps: bool) -> tuple[str, str, list[Candidate]]:
    """ADR 0009 rule 6, with no-HSPs kept distinct from no-eligible-candidate."""
    eligible = [c for c in candidates if c.eligible]
    if not had_hsps:
        return INDETERMINATE, "NO_HSPS", []
    if not eligible:
        return INDETERMINATE, "NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA", []
    if len(eligible) > 1:
        return INDETERMINATE, "MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA", eligible
    return DETERMINED, "ONE_LOCUS_MEETS_ASSIGNMENT_CRITERIA", eligible


def geometry(locus_a: Candidate, locus_b: Candidate) -> dict[str, object]:
    """What the two alignments share as geometry, before any attribution."""
    same_sequence = locus_a.subject == locus_b.subject
    return {
        "same_sequence": same_sequence,
        "same_strand": locus_a.strand == locus_b.strand,
        "same_span": (same_sequence and locus_a.start == locus_b.start
                      and locus_a.end == locus_b.end),
        "spans_overlap": (same_sequence and locus_a.start <= locus_b.end
                          and locus_b.start <= locus_a.end),
        # Compared as query-to-genome correspondence in query order, so the same
        # genomic blocks visited in a different query order do not count as the
        # same chain.
        "chains_concordant": locus_a.chain == locus_b.chain,
        "same_genomic_blocks": (sorted(locus_a.block_chain) == sorted(locus_b.block_chain)),
        "colinear_a": locus_a.colinear,
        "colinear_b": locus_b.colinear,
        "span_a": f"{locus_a.start}-{locus_a.end}",
        "span_b": f"{locus_b.start}-{locus_b.end}",
        "strand_a": locus_a.strand,
        "strand_b": locus_b.strand,
        "n_blocks_a": len(locus_a.chain),
        "n_blocks_b": len(locus_b.chain),
    }


def origin_inference(ids: Sequence[str], alignment_reason: str,
                     discriminating: dict[str, list[dict[str, object]]]) -> tuple[str, str]:
    """Where the two records came from, inferred separately from the alignment.

    What the alignments show about the mapped intervals and where the two TSA
    records came from are different questions. An alignment can settle the first
    — these intervals coincide, or they are disjoint — without settling the
    second: one interval can carry two records, and two intervals can carry one
    record that the assembler duplicated.

    No configuration in this run resolves the origin, so this function returns
    ``INDETERMINATE`` in every case and reports which evidence it weighed. The
    strongest configuration available is two disjoint mapped intervals, each
    matching its own record exactly at the discriminating position with a
    different base on each. That is a statement about this assembly: the
    discriminating position favours two distinct loci here, each carrying one of
    the two bases. It does not establish that the two TSA records came from two
    loci. Two assembled loci can be one locus duplicated in the assembly, or two
    alleles of one locus in a heterozygous individual, and either would place
    the two bases where they are seen; the published records say nothing about
    which. Resolving that needs evidence this run does not hold, so the origin
    is left as the separate, unresolved inference it is, while the geometry, the
    per-query eligibility, the per-candidate calls at the discriminating
    position and ``alignment_status`` all keep what they do establish.
    """
    calls = {query_id: discriminating.get(query_id, []) for query_id in ids}
    if any(len(c) != 1 for c in calls.values()):
        return INDETERMINATE, "NOT_EXACTLY_ONE_ELIGIBLE_CANDIDATE_PER_QUERY"
    single = {query_id: c[0] for query_id, c in calls.items()}

    if not alignment_reason.startswith("MAPPED_INTERVALS_DISTINCT"):
        if alignment_reason.startswith("FAVOURS_SHARED_LOCUS"):
            # One interval cannot say which record came from it.
            return INDETERMINATE, "SHARED_INTERVAL_CANNOT_ASSIGN_RECORDS"
        return INDETERMINATE, f"ALIGNMENT_NOT_DECISIVE:{alignment_reason}"

    not_exact = [q for q in ids if single[q]["verdict"] != EXACT]
    if not_exact:
        detail = ",".join(f"{q}:{single[q]['verdict']}" for q in not_exact)
        return INDETERMINATE, f"DISCRIMINATING_POSITION_NOT_CALLED_EXACT:{detail}"

    bases = {single[q].get("subject_base", "") for q in ids}
    if len(bases) != len(ids):
        return INDETERMINATE, "DISCRIMINATING_POSITION_DOES_NOT_DISCRIMINATE"
    # Each disjoint interval carries its own record's base at the discriminating
    # position. That favours two distinct loci in this assembly; it does not say
    # the two records came from two loci, since a duplicated locus or two
    # alleles of one locus would read the same way.
    return (INDETERMINATE,
            "DISCRIMINATING_POSITION_FAVOURS_DISTINCT_LOCI_IN_THIS_ASSEMBLY")


def pair_verdict(assignments: dict[str, dict[str, object]],
                 discriminating: dict[str, list[dict[str, object]]],
                 position: int) -> dict[str, object]:
    """One row for one assembly, in groups that are never merged.

    ``geometry_*``     what the alignments are: sequence, span, strand, chain.
    ``eligibility_*``  the per-query assignment under ADR 0009 rule 6.
    ``evidence816_*``  the discriminating position, per candidate.
    ``alignment_*``    what the alignments show about the mapped intervals.
    ``origin_*``       where the two records came from, inferred separately.

    Identical outer bounds are a geometric coincidence and do not on their own
    support one shared locus: two alignments can share a span on opposite
    strands, or share it while placing different blocks between those bounds, or
    while running through the same blocks in opposite query order. For the
    alignment to favour one shared locus it takes the same strand and a
    concordant, colinear chain.

    Even then the alignment speaks only about this assembly's intervals. Whether
    the two records came from one locus or two is a separate inference, and it
    stays ``INDETERMINATE`` wherever the available evidence does not resolve it.
    The evidence at the discriminating position is reported per candidate and
    never decides the alignment group: when a query has more than one eligible
    locus the pair stays INDETERMINATE even if that position would favour one
    association, because a discriminating base cannot repair an assignment that
    ADR 0009 rule 6 leaves unmade.
    """
    ids = sorted(assignments)

    eligibility: dict[str, object] = {}
    for query_id in ids:
        eligibility[f"eligibility_{query_id}_status"] = assignments[query_id]["status"]
        eligibility[f"eligibility_{query_id}_reason"] = assignments[query_id]["status_reason"]

    evidence: dict[str, object] = {"evidence816_position": position}
    for query_id in ids:
        calls = discriminating.get(query_id, [])
        evidence[f"evidence816_{query_id}_n_eligible_candidates"] = len(calls)
        evidence[f"evidence816_{query_id}_calls"] = "; ".join(
            f"{c['candidate_id']}={c.get('subject_base') or '-'}/{c['verdict']}"
            for c in calls) or NO_COVERAGE

    blank_geometry = {f"geometry_{key}": "" for key in (
        "same_sequence", "same_strand", "same_span", "spans_overlap",
        "chains_concordant", "same_genomic_blocks", "colinear_a", "colinear_b",
        "span_a", "span_b", "strand_a", "strand_b", "n_blocks_a", "n_blocks_b")}

    def row(shape: dict[str, object], status: str, reason: str) -> dict[str, object]:
        origin_status, origin_reason = origin_inference(ids, reason, discriminating)
        return {**{f"geometry_{k}": v for k, v in shape.items()},
                **eligibility, **evidence,
                "alignment_status": status, "alignment_reason": reason,
                "origin_status": origin_status, "origin_reason": origin_reason}

    unresolved = [i for i in ids if assignments[i]["status"] != DETERMINED]
    if unresolved:
        reasons = ",".join(f"{i}:{assignments[i]['status_reason']}" for i in unresolved)
        reason = f"UNASSIGNED_QUERY:{reasons}"
        return {**blank_geometry, **eligibility, **evidence,
                "alignment_status": INDETERMINATE, "alignment_reason": reason,
                "origin_status": INDETERMINATE,
                "origin_reason": f"ALIGNMENT_NOT_DECISIVE:{reason}"}

    locus_a = assignments[ids[0]]["locus"]
    locus_b = assignments[ids[1]]["locus"]
    shape = geometry(locus_a, locus_b)

    if not shape["colinear_a"] or not shape["colinear_b"]:
        return row(shape, INDETERMINATE, "NON_COLINEAR_CHAIN")
    if not shape["same_sequence"]:
        return row(shape, DETERMINED, "MAPPED_INTERVALS_DISTINCT_DIFFERENT_SEQUENCES")
    if not shape["spans_overlap"]:
        return row(shape, DETERMINED, "MAPPED_INTERVALS_DISTINCT_NON_OVERLAPPING_SPANS")
    if not shape["same_span"]:
        return row(shape, INDETERMINATE, "OVERLAPPING_SPANS_ON_ONE_SEQUENCE")
    # Same outer bounds from here on: geometry alone, not yet an inference.
    if not shape["same_strand"]:
        return row(shape, INDETERMINATE, "SAME_SPAN_OPPOSITE_STRAND")
    if not shape["chains_concordant"]:
        reason = ("SAME_SPAN_SAME_BLOCKS_DIFFERENT_QUERY_ORDER"
                  if shape["same_genomic_blocks"] else "SAME_SPAN_DISCORDANT_BLOCKS")
        return row(shape, INDETERMINATE, reason)
    return row(shape, DETERMINED, "FAVOURS_SHARED_LOCUS_IN_THIS_ASSEMBLY")


# --------------------------------------------------------------------------- inputs
def load_queries(root: Path, panel: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Extract and verify one CDS per declared accession from the validated TSA."""
    tsa = panel["tsa"]
    tsa_path = _resolve(root, tsa, "tsa")
    observed = sha256_file(tsa_path)
    if observed != tsa["sha256"]:
        raise AccessionMappingError(
            f"declared input changed: tsa\n  declared sha256={tsa['sha256']}\n"
            f"  observed sha256={observed}")
    print(f"[verify] tsa: sha256 {observed} OK", file=sys.stderr)

    wanted = {str(q["accession"]) for q in panel["queries"]}
    records: dict[str, str] = {}
    for record in nb01_identity.parse_fasta(tsa_path):
        accession = nb01_identity.canonical_tsa_accession(record.identifier)
        if accession in wanted:
            records[accession] = record.sequence.upper()
            if len(records) == len(wanted):
                break
    absent = wanted - set(records)
    if absent:
        raise AccessionMappingError(f"records absent from the TSA: {sorted(absent)}")

    rows: list[dict[str, object]] = []
    for entry in panel["queries"]:
        accession = str(entry["accession"])
        record = records[accession]
        if len(record) != int(entry["record_length"]):
            raise AccessionMappingError(
                f"{accession}: declared record_length={entry['record_length']}, "
                f"observed {len(record)}")
        start, end = int(entry["cds_tx_start"]), int(entry["cds_tx_end"])
        if not 1 <= start <= end <= len(record):
            raise AccessionMappingError(
                f"{accession}: CDS {start}-{end} outside the record")
        segment = record[start - 1:end]
        cds = nb01_identity.reverse_complement(segment) if entry["strand"] == "-" else segment
        if len(cds) != int(entry["cds_length"]):
            raise AccessionMappingError(
                f"{accession}: declared cds_length={entry['cds_length']}, observed {len(cds)}")
        digest = sha256_text(cds)
        if digest != entry["cds_sha256"]:
            raise AccessionMappingError(
                f"{accession}: declared cds_sha256={entry['cds_sha256']}, observed {digest}")
        print(f"[verify] {accession}: CDS {len(cds)} nt, sha256 {digest} OK", file=sys.stderr)
        rows.append({
            "query_id": str(entry["query_id"]),
            "accession": accession,
            "role": entry.get("role", ""),
            "record_length": len(record),
            "strand": entry["strand"],
            "cds_tx_start": start,
            "cds_tx_end": end,
            "cds_length": len(cds),
            "cds_sha256": digest,
            "n_iupac_symbols": sum(b not in UNAMBIGUOUS_DNA for b in cds),
            "cds": cds,
        })
    return rows, {"path": str(tsa["path"]), "sha256": observed}


# --------------------------------------------------------------------------- run
CANDIDATE_COLUMNS = [
    "assembly_id", "query_id", "accession", "candidate_id", "sequence_id", "strand",
    "locus_start", "locus_end", "locus_span_nt", "chain_query_to_genome",
    "block_chain", "n_blocks", "colinear",
    "query_coverage_pct", "identity_pct_blast", "aligned_nt", "matched_nt",
    "mismatch_nt", "gaps_nt", "n_hsps_tiled", "eligible_for_assignment",
    "informative_exact", "informative_ambiguity_compatible",
    "informative_ambiguity_incompatible", "informative_subject_ambiguous",
    "informative_defined_mismatch", "informative_not_called",
]
POSITION_COLUMNS = [
    "assembly_id", "query_id", "accession", "candidate_id", "cds_pos", "declared_class",
    "is_discriminating_position", "query_base", "subject_sequence_id", "subject_pos",
    "strand", "subject_base_query_orientation", "subject_base_plus_strand", "btop_op",
    "n_hsps_covering", "observed_by_hsps", "verdict", "conflict_detail",
]
OBSERVATION_COLUMNS = [
    "assembly_id", "query_id", "accession", "candidate_id", "hsp_id", "cds_pos",
    "query_base", "subject_sequence_id", "subject_pos", "strand",
    "subject_base_query_orientation", "subject_base_plus_strand", "btop_op", "verdict",
]
ASSIGNMENT_COLUMNS = [
    "assembly_id", "query_id", "accession", "n_hsps", "n_candidates_reported",
    "n_candidates_eligible", "status", "status_reason", "locus_id", "sequence_id", "span",
]


def run(root: Path, out: Path, panel_path: Path) -> int:
    panel = load_accession_panel(root / panel_path)
    assemblies_panel_path = root / str(panel["assemblies_panel"]["path"])
    assemblies_panel = load_panel(assemblies_panel_path)

    verified: dict[str, object] = {
        "accession_panel": {"path": str(panel_path),
                            "sha256": sha256_file(root / panel_path)},
        "assemblies_panel": {"path": str(panel["assemblies_panel"]["path"]),
                             "sha256": sha256_file(assemblies_panel_path)},
    }

    with reserve_output_dir(out) as reservation:
        print(f"[output] {reservation.out_dir} (reserved)", file=sys.stderr)
        raw = out / "raw"
        raw.mkdir(exist_ok=True)
        log = CommandLog()

        queries, tsa_record = load_queries(root, panel)
        verified["tsa"] = tsa_record
        positions = [int(p["cds_pos"]) for p in panel["informative_positions"]]
        declared_class = {int(p["cds_pos"]): str(p["class"])
                          for p in panel["informative_positions"]}
        discriminating_position = int(panel["discriminating_position"]["cds_pos"])

        write_tsv(out / "queries.tsv",
                  [{k: v for k, v in q.items() if k != "cds"} for q in queries],
                  ["query_id", "accession", "role", "record_length", "strand",
                   "cds_tx_start", "cds_tx_end", "cds_length", "cds_sha256",
                   "n_iupac_symbols"])
        query_path = raw / "dsrnase2_accession_queries.fna"
        query_path.write_text(
            format_fasta((str(q["query_id"]), str(q["cds"])) for q in queries),
            encoding="ascii", newline="\n")

        candidate_rows: list[dict[str, object]] = []
        position_rows: list[dict[str, object]] = []
        observation_rows: list[dict[str, object]] = []
        assignment_rows: list[dict[str, object]] = []
        pair_rows: list[dict[str, object]] = []
        verified_assemblies: list[dict[str, object]] = []

        for entry in assemblies_panel["assemblies"]:
            label = str(entry["id"])
            archive = _resolve(root, entry, label)
            hashes = _check_hash(archive, entry, label)
            scratch = Path(tempfile.mkdtemp(prefix=f"nb01_d2acc_{label}_"))
            try:
                fasta = scratch / f"{label}.fna"
                with gzip.open(archive, "rb") as source, fasta.open("wb") as target:
                    shutil.copyfileobj(source, target)
                decompressed = sha256_file(fasta)
                declared_decompressed = entry.get("sha256_decompressed")
                if declared_decompressed and decompressed != declared_decompressed:
                    raise AccessionMappingError(
                        f"declared input changed: {label} (decompressed)\n"
                        f"  declared sha256={declared_decompressed}\n"
                        f"  observed sha256={decompressed}")
                _, stats = scan_assembly(fasta)
                check_declared_stats(label, entry, stats)
                verified_assemblies.append({
                    "id": label, "path": str(entry["path"]),
                    "sha256": hashes.get("sha256"),
                    "sha256_decompressed": decompressed,
                })
                db = scratch / f"{label}.db"
                log.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl",
                         "-title", label, "-out", str(db)],
                        stdout_path=raw / f"{label}.makeblastdb.log")
                hsps = _blast_with_archive(log, query_path, db, raw / f"blastn_{label}")
            finally:
                shutil.rmtree(scratch, ignore_errors=True)

            assignments: dict[str, dict[str, object]] = {}
            discriminating: dict[str, list[dict[str, object]]] = {}
            for query in queries:
                query_id = str(query["query_id"])
                mine = [h for h in hsps if h.query == query_id]
                candidates = build_candidates(label, query_id, mine)
                status, reason, eligible = assignment_status(candidates, bool(mine))
                assignments[query_id] = {
                    "status": status, "status_reason": reason,
                    "locus": eligible[0] if len(eligible) == 1 else None,
                }
                assignment_rows.append({
                    "assembly_id": label, "query_id": query_id,
                    "accession": query["accession"], "n_hsps": len(mine),
                    "n_candidates_reported": len(candidates),
                    "n_candidates_eligible": sum(1 for c in candidates if c.eligible),
                    "status": status, "status_reason": reason,
                    "locus_id": eligible[0].candidate_id if len(eligible) == 1 else "",
                    "sequence_id": eligible[0].subject if len(eligible) == 1 else "",
                    "span": (f"{eligible[0].start}-{eligible[0].end}"
                             if len(eligible) == 1 else ""),
                })

                discriminating[query_id] = []
                for candidate in candidates:
                    audited, observations = audit_candidate(
                        candidate, positions, str(query["cds"]))
                    counts = {v: sum(1 for c in audited.values() if c["verdict"] == v)
                              for v in (EXACT, AMBIGUITY_COMPATIBLE,
                                        AMBIGUITY_INCOMPATIBLE, SUBJECT_AMBIGUOUS,
                                        DEFINED_MISMATCH)}
                    candidate_rows.append({
                        "assembly_id": label, "query_id": query_id,
                        "accession": query["accession"],
                        "candidate_id": candidate.candidate_id,
                        "sequence_id": candidate.subject, "strand": candidate.strand,
                        "locus_start": candidate.start, "locus_end": candidate.end,
                        "locus_span_nt": candidate.end - candidate.start + 1,
                        "chain_query_to_genome": ";".join(
                            f"q{q0}-{q1}>s{s0}-{s1}"
                            for (q0, q1), (s0, s1) in candidate.chain),
                        "block_chain": ";".join(f"{a}-{b}" for a, b in candidate.block_chain),
                        "n_blocks": len(candidate.chain),
                        "colinear": candidate.colinear,
                        "query_coverage_pct": candidate.coverage_pct,
                        "identity_pct_blast": candidate.identity_pct,
                        "aligned_nt": candidate.aligned_nt,
                        "matched_nt": candidate.matched_nt,
                        "mismatch_nt": candidate.mismatch_nt,
                        "gaps_nt": candidate.gaps_nt,
                        "n_hsps_tiled": candidate.n_hsps,
                        "eligible_for_assignment": candidate.eligible,
                        "informative_exact": counts[EXACT],
                        "informative_ambiguity_compatible": counts[AMBIGUITY_COMPATIBLE],
                        "informative_ambiguity_incompatible": counts[AMBIGUITY_INCOMPATIBLE],
                        "informative_subject_ambiguous": counts[SUBJECT_AMBIGUOUS],
                        "informative_defined_mismatch": counts[DEFINED_MISMATCH],
                        "informative_not_called": sum(
                            1 for c in audited.values()
                            if c["verdict"] in (NO_COVERAGE, GAP_IN_SUBJECT,
                                                CONFLICTING_HSPS)),
                    })
                    for observation in observations:
                        observation_rows.append({
                            "assembly_id": label, "query_id": query_id,
                            "accession": query["accession"],
                            "candidate_id": candidate.candidate_id,
                            "hsp_id": observation["hsp_id"],
                            "cds_pos": observation["cds_pos"],
                            "query_base": observation["query_base"],
                            "subject_sequence_id": observation["subject_sequence_id"],
                            "subject_pos": (observation["subject_pos"]
                                            if observation["subject_pos"] is not None else ""),
                            "strand": observation["strand"],
                            "subject_base_query_orientation": observation["subject_base"],
                            "subject_base_plus_strand": observation["subject_base_plus_strand"],
                            "btop_op": observation["btop_op"],
                            "verdict": observation["verdict"],
                        })
                    for position in positions:
                        call = audited[position]
                        position_rows.append({
                            "assembly_id": label, "query_id": query_id,
                            "accession": query["accession"],
                            "candidate_id": candidate.candidate_id,
                            "cds_pos": position,
                            "declared_class": declared_class[position],
                            "is_discriminating_position": position == discriminating_position,
                            "query_base": call.get("query_base", ""),
                            "subject_sequence_id": call.get("subject_sequence_id", ""),
                            "subject_pos": (call.get("subject_pos", "")
                                            if call.get("subject_pos") is not None else ""),
                            "strand": call.get("strand", ""),
                            "subject_base_query_orientation": call.get("subject_base", ""),
                            "subject_base_plus_strand": call.get("subject_base_plus_strand", ""),
                            "btop_op": call.get("btop_op", ""),
                            "n_hsps_covering": call.get("n_hsps_covering", 0),
                            "observed_by_hsps": call.get("observed_by_hsps", ""),
                            "verdict": call["verdict"],
                            "conflict_detail": call.get("conflict_detail", ""),
                        })
                    # Evidence at the discriminating position is kept per
                    # candidate, including when several are eligible.
                    if candidate.eligible:
                        discriminating[query_id].append({
                            "candidate_id": candidate.candidate_id,
                            **audited[discriminating_position],
                        })

            pair_rows.append({"assembly_id": label,
                              **pair_verdict(assignments, discriminating,
                                             discriminating_position)})

        write_tsv(out / "candidates.tsv", candidate_rows, CANDIDATE_COLUMNS)
        write_tsv(out / "informative_positions.tsv", position_rows, POSITION_COLUMNS)
        write_tsv(out / "informative_observations.tsv", observation_rows, OBSERVATION_COLUMNS)
        write_tsv(out / "assignments.tsv", assignment_rows, ASSIGNMENT_COLUMNS)
        pair_columns = sorted({k for row in pair_rows for k in row}) if pair_rows else ["assembly_id"]
        write_tsv(out / "accession_pair.tsv", pair_rows, pair_columns)

        verified["assemblies"] = verified_assemblies
        manifest = {
            "question": "do GITV01008430.1 and GITV01012450.1 come from one genomic locus or two",
            "criteria_reference": panel["criteria_reference"],
            "flank_in_scope": False,
            "verified_inputs": verified,
            "queries": [{k: v for k, v in q.items() if k != "cds"} for q in queries],
            "informative_positions": positions,
            "discriminating_position": discriminating_position,
            "commands": log.entries,
            "outputs": {
                name: sha256_file(out / name)
                for name in ("queries.tsv", "candidates.tsv", "informative_positions.tsv",
                             "informative_observations.tsv", "assignments.tsv",
                             "accession_pair.tsv")
            },
        }
        (out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8", newline="\n")
        print(f"[write] {out}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--panel", default=str(DEFAULT_PANEL))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    return run(root, root / args.out, Path(args.panel))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AccessionMappingError, LocusInputError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(2)
