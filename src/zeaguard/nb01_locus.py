"""NB01 dsRNase locus mapping: the three published CDS against the Dalbulus maidis genome.

The mapping answers two questions the NB01 family audit left explicitly open, and nothing
else:

1. does Dmai-dsRNase-3 occupy a locus of its own, distinct from those of dsRNase-1 and
   dsRNase-2;
2. do the two complete TSA records attributed to dsRNase-2, ``GITV01008430.1`` and
   ``GITV01012450.1``, come from one genomic locus or from distinct loci.

Question 2 needs one statement made before any result is read. ADR 0004 established that the
two records reproduce **the same** 1425 nt CDS, so a single query sequence stands for both.
Sequence mapping therefore cannot say which record came from which locus; it can only count
how many genomic loci carry that CDS. That count is what this module reports, and the two
readings it permits are stated in the run record, not here.

What the module does *not* do is as important. It never equates "aligns to the same region"
with "is the same locus": a locus call is reported together with the contiguity of the
assembly around it (scaffold role, assembly gaps inside the span, distance to the scaffold
ends) and with the number of *other* genome loci that reach the related-locus coverage
threshold for the same query, which is the repeat measure for the query itself. Where the
pre-registered criteria do not decide, the answer is ``INDETERMINATE`` with a reason, never a
forced conclusion. No statement about enzymatic activity is made or implied anywhere.

Coordinate convention: 1-based inclusive throughout, as in
:mod:`zeaguard.nb01_dsrnase_investigation`. Query coordinates run along the CDS in coding
orientation. Subject coordinates run along the genomic sequence as the assembly distributes
it; the gene's orientation on that sequence lives in ``strand``.

Every position and statistic of the panel is a DECLARATION. Before a declared input is used,
the module checks it against the file: the hash of every input, the published ORF coordinates
against the ORF it derives itself from the repository anchors, and the declared assembly
statistics against the sequences actually read. Any disagreement aborts the run rather than
producing a quiet result.
"""

from __future__ import annotations

import gzip
import json
import platform
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from zeaguard import nb01_identity
from zeaguard.nb01_identity import reverse_complement
from zeaguard.nb01_dsrnase_investigation import (
    BLAST_OUTFMT_FIELDS,
    CommandLog,
    Hsp,
    _git,
    file_record,
    find_orfs,
    format_fasta,
    lf_sha256,
    merge_intervals,
    orf_sequence,
    parse_hsp_table,
    sha256_file,
    sha256_text,
    translate,
    write_tsv,
)

DEFAULT_PANEL = Path("data/reference/nb01_dsrnase_locus_panel.json")
DEFAULT_OUT = Path("results/bioinformatics/nb01/mappings/dsrnase_locus_mapping")

DETERMINED = "DETERMINED"
INDETERMINATE = "INDETERMINATE"

# --------------------------------------------------------------------------- criteria
# Pre-registered before any search was run; see ADR 0009. None of these is a result.
#
# Reused unchanged from ADR 0004 so that discovery breadth stays comparable across NB01:
BLASTN_PARAMS = ["-task", "blastn", "-dust", "no", "-evalue", "1e-5"]
#: Set above the sequence count of the largest declared assembly so the limit provably cannot
#: truncate the result. ``observed_subjects_below_limit`` in the manifest records that it did not.
MAX_TARGET_SEQS = 20000
#: Consecutive HSPs of one query on one sequence and strand belong to one locus when the
#: genomic distance between them is at most this. Deliberately generous: an intron longer than
#: this splits one locus into two reported loci, which is visible in the output as two partial
#: loci rather than hidden as one complete one.
MAX_INTRON_NT = 50_000
#: A locus must align at least this fraction of the CDS to be a locus candidate at all.
LOCUS_MIN_QUERY_COVERAGE_PCT = 90.0
#: ...and reach at least this identity over its tiled alignment to be *assigned* to the CDS.
#: The assembly and the published transcripts come from different individuals, so an allelic
#: difference is expected and a few percent of divergence is not evidence of a different gene.
ASSIGNMENT_MIN_IDENTITY_PCT = 98.0
#: Additional loci are reported down to this coverage, as related loci. Equal to
#: ``DISCOVERY_MIN_UNION_COVERAGE_PCT`` of ADR 0004: discovery breadth is deliberately broad
#: and says nothing about identity.
RELATED_LOCUS_MIN_COVERAGE_PCT = 50.0
#: Tolerated overlap, in query nucleotides, between two HSPs tiled as consecutive exons. A
#: real exon junction is often reported with a few ambiguous bases on both sides. Identity is
#: computed over the sum of the tiled alignment lengths, so an overlap of at most this many
#: nucleotides per junction is counted twice; with three queries of >1.2 kb the effect on the
#: reported identity is below the third decimal and is never near a threshold.
MAX_TILE_OVERLAP_NT = 10
#: Canonical spliceosomal intron termini, checked on the gene's orientation. A non-canonical
#: pair is reported, never filtered: it is an observation about the inferred structure.
CANONICAL_SPLICE = ("GT", "AG")

QUERY_COLUMNS = (
    "target_id transcript_id cds_length protein_length orf_strand orf_frame "
    "declared_orf_start declared_orf_end derived_orf_start derived_orf_end "
    "orf_coordinates_agree start_codon stop_codon cds_sha256 protein_sha256"
).split()

LOCUS_COLUMNS = (
    "assembly_id target_id locus_id sequence_id sequence_role molecule sequence_length strand "
    "locus_start locus_end locus_span_nt query_coverage_pct query_covered_nt cds_length "
    "identity_pct aligned_nt matched_nt mismatch_nt gap_nt n_exons_inferred n_introns_inferred "
    "colinear intron_sizes_nt query_junction_offsets_nt splice_pairs_at_alignment_boundary "
    "canonical_splice_junctions canonical_splice_shifts_nt "
    "assembly_gap_nt_in_span assembly_gap_runs_in_span distance_to_sequence_end_nt "
    "exon_blocks_subject exon_blocks_query best_bitscore best_evalue tier"
).split()

ASSIGNMENT_COLUMNS = (
    "assembly_id target_id status status_reason locus_id sequence_id molecule strand "
    "locus_start locus_end query_coverage_pct identity_pct n_exons_inferred "
    "n_loci_at_assignment_criteria n_related_loci related_locus_ids"
).split()

DISTINCTNESS_COLUMNS = (
    "assembly_id target_a target_b status status_reason same_sequence sequence_a sequence_b "
    "span_a span_b spans_overlap overlap_nt gap_between_spans_nt"
).split()

COPY_NUMBER_COLUMNS = (
    "assembly_id target_id n_loci_at_assignment_criteria n_related_loci locus_ids "
    "assembly_level n_scaffolds scaffold_n50 interpretation_key"
).split()


class LocusInputError(RuntimeError):
    """Raised when a declared input is missing or does not match its declaration."""


# --------------------------------------------------------------------------- declared inputs
# NOTE ON DUPLICATION. The four helpers below repeat the input-verification pattern of the
# NB01 protein audit deliberately. That audit lives on an unpublished branch, so importing it
# here would make this module depend on code that is not in the main line. The names and
# semantics are kept identical so the two can be factored into one place once both are merged.

#: How a declared input is verified. ``sha256_lf_normalized`` is the only safe choice for a
#: git-tracked text file: unless the path is pinned to ``eol=lf`` in ``.gitattributes``, the
#: raw hash of the working copy depends on the checkout (CRLF on Windows, LF elsewhere).
HASH_MODES = {
    "sha256": sha256_file,
    "sha256_lf_normalized": lf_sha256,
}


def _resolve(root: Path, declared: dict[str, object], label: str) -> Path:
    path = root / str(declared["path"])
    if not path.is_file():
        hint = declared.get("source_url")
        where = f"\n  download it from: {hint}" if hint else ""
        raise LocusInputError(f"declared input is missing: {label} -> {declared['path']}{where}")
    return path


def _check_hash(path: Path, declared: dict[str, object], label: str) -> dict[str, str]:
    """Verify the declared hash of one input and return every hash computed for it."""
    mode = str(declared.get("verify", "sha256"))
    if mode not in HASH_MODES:
        raise LocusInputError(f"{label}: unknown verify mode {mode!r}")
    expected = declared.get(mode)
    if not expected:
        raise LocusInputError(f"{label}: declares verify={mode} but carries no {mode} value")
    # Only the hash this input is verified by is computed: LF normalisation is meaningless for
    # a binary input, and recording it there would be noise that reads like evidence.
    observed = {mode: HASH_MODES[mode](path)}
    observed.setdefault("sha256", sha256_file(path))
    if observed[mode] != expected:
        raise LocusInputError(
            f"declared input changed: {label} -> {declared['path']}\n"
            f"  verified by: {mode}\n  declared {mode}={expected}\n  observed {mode}={observed[mode]}"
        )
    return {**observed, "verified_by": mode}


def load_panel(panel_path: Path) -> dict[str, object]:
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    if panel.get("kind") != "nb01_dsrnase_locus_panel":
        raise LocusInputError(f"not a locus panel: {panel_path}")
    return panel


# --------------------------------------------------------------------------- queries
def derive_queries(anchor_path: Path, declared: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Derive each CDS from the repository anchors and check it against its declaration.

    The CDS is the longest stop-delimited open reading frame of the published Trinity
    transcript, read from its first methionine. The published ORF coordinates are a
    DECLARATION that this derivation is checked against; a disagreement aborts the run.
    """
    records = {r.identifier: r.sequence.upper() for r in nb01_identity.parse_fasta(anchor_path)}
    rows: list[dict[str, object]] = []
    for entry in declared:
        transcript = str(entry["transcript_id"])
        if transcript not in records:
            raise LocusInputError(
                f"{entry['target_id']}: transcript {transcript} is not in {anchor_path.name}"
            )
        sequence = records[transcript]
        orfs = [o for o in find_orfs(sequence, min_aa=100) if o.first_met >= 0]
        if not orfs:
            raise LocusInputError(f"{entry['target_id']}: no open reading frame of 100 aa or more")
        orf = max(orfs, key=lambda o: len(o.protein) - o.first_met)
        offset = 3 * orf.first_met
        cds = orf_sequence(sequence, orf)[offset:]
        protein = translate(cds, to_stop=True)
        # Forward 1-based coordinates of the A of the ATG and of the last base of the stop
        # codon, printed in the publication's own order (start first, stop second).
        if orf.strand == "+":
            start, end = orf.start + offset, orf.end
        else:
            start, end = orf.end - offset, orf.start
        agrees = [start, end] == [int(entry["published_orf_start"]), int(entry["published_orf_end"])]
        if not agrees:
            raise LocusInputError(
                f"{entry['target_id']}: published ORF {entry['published_orf_start']}.."
                f"{entry['published_orf_end']}, derived {start}..{end}"
            )
        for field, observed in (("cds_length", len(cds)), ("protein_length", len(protein))):
            if int(entry[field]) != observed:
                raise LocusInputError(
                    f"{entry['target_id']}: declared {field}={entry[field]}, derived {observed}"
                )
        rows.append({
            "target_id": entry["target_id"],
            "transcript_id": transcript,
            "cds": cds,
            "protein": protein,
            "cds_length": len(cds),
            "protein_length": len(protein),
            "orf_strand": orf.strand,
            "orf_frame": orf.frame,
            "declared_orf_start": entry["published_orf_start"],
            "declared_orf_end": entry["published_orf_end"],
            "derived_orf_start": start,
            "derived_orf_end": end,
            "orf_coordinates_agree": agrees,
            "start_codon": cds[:3],
            "stop_codon": cds[-3:],
            "cds_sha256": sha256_text(cds),
            "protein_sha256": sha256_text(protein),
        })
    return rows


# --------------------------------------------------------------------------- assembly FASTA
def iter_fasta(path: Path) -> Iterator[tuple[str, str, str]]:
    """Stream ``(sequence_id, description, sequence)`` from a FASTA file.

    Streaming rather than loading: the declared assemblies are hundreds of megabases and only
    the handful of sequences that carry a locus is ever needed in memory.
    """
    name = description = None
    chunks: list[str] = []
    with path.open("r", encoding="ascii") as handle:
        for line in handle:
            if line.startswith(">"):
                if name is not None:
                    yield name, description or "", "".join(chunks)
                header = line[1:].strip()
                name, _, description = header.partition(" ")
                chunks = []
            else:
                chunks.append(line.strip())
    if name is not None:
        yield name, description or "", "".join(chunks)


def scan_assembly(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """One pass over an assembly FASTA: per-sequence metadata and whole-assembly statistics."""
    info: dict[str, dict[str, object]] = {}
    total = ungapped = 0
    for name, description, sequence in iter_fasta(path):
        n_count = sequence.count("N") + sequence.count("n")
        info[name] = {
            "description": description,
            "length": len(sequence),
            "n_count": n_count,
            "molecule": _molecule(description),
            "role": _role(description),
        }
        total += len(sequence)
        ungapped += len(sequence) - n_count
    lengths = sorted((entry["length"] for entry in info.values()), reverse=True)
    half, running, n50 = total / 2, 0, 0
    for length in lengths:
        running += length
        if running >= half:
            n50 = length
            break
    stats = {
        "number_of_sequences": len(info),
        "total_sequence_length": total,
        "total_ungapped_length": ungapped,
        "scaffold_n50": n50,
        "number_of_assembled_molecules": sum(1 for e in info.values() if e["role"] == "assembled-molecule"),
        "number_of_organelle_sequences": sum(1 for e in info.values() if e["role"] == "organelle"),
    }
    return info, stats


#: Defline keys that name a placed molecule, in the order a defline may carry them.
MOLECULE_KEYS = ("chromosome", "linkage group", "organelle", "plasmid")


def _molecule(description: str) -> str:
    """The molecule an NCBI assembly defline names, or ``""`` when it names none."""
    for part in description.split(","):
        key, sep, value = part.partition(":")
        if sep and key.strip().lower() in MOLECULE_KEYS:
            return f"{key.strip().lower()} {value.strip()}"
    return ""


def _role(description: str) -> str:
    """What the defline says the sequence is.

    ``organelle`` is kept apart from the nuclear sequences because an organelle genome is in
    the search space but is not a scaffold of the nuclear assembly: NCBI's own scaffold count
    and total length exclude it, and a count that silently included it would not reconcile.
    """
    molecule = _molecule(description)
    if molecule.startswith(("organelle", "plasmid")):
        return "organelle"
    if molecule:
        return "assembled-molecule"
    return "unlocalized-or-unplaced"


def check_declared_stats(label: str, declared: dict[str, object], observed: dict[str, object]) -> dict[str, object]:
    """Abort unless every declared assembly statistic matches the sequences actually read."""
    checked: dict[str, object] = {}
    for key, value in (declared.get("assembly_stats") or {}).items():
        if key not in observed:
            raise LocusInputError(f"{label}: declares unknown assembly statistic {key!r}")
        checked[key] = {"declared": value, "observed": observed[key], "agrees": value == observed[key]}
        if value != observed[key]:
            raise LocusInputError(
                f"declared input changed: {label}\n  assembly statistic {key}: "
                f"declared {value}, observed {observed[key]}"
            )
    return checked


def read_sequences(path: Path, wanted: Iterable[str]) -> dict[str, str]:
    """Read only the named sequences of a FASTA, streaming past everything else."""
    wanted = set(wanted)
    found = {name: sequence for name, _, sequence in iter_fasta(path) if name in wanted}
    missing = wanted - set(found)
    if missing:
        raise LocusInputError(f"{path.name}: sequences not found: {', '.join(sorted(missing))}")
    return found


# --------------------------------------------------------------------------- loci
def cluster_loci(hsps: Sequence[Hsp], max_intron: int = MAX_INTRON_NT) -> list[list[Hsp]]:
    """Group HSPs into loci: one query, one sequence, one strand, genomically close.

    HSPs are grouped when the genomic distance between consecutive ones is at most
    ``max_intron``. Strands never merge: the same CDS found on both strands of one region is
    two loci, and the output says so.
    """
    groups: dict[tuple[str, str, str], list[Hsp]] = defaultdict(list)
    for hsp in hsps:
        groups[(hsp.query, hsp.subject, hsp.strand)].append(hsp)
    loci: list[list[Hsp]] = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda h: h.subject_interval)
        current = [members[0]]
        reach = members[0].subject_interval[1]
        for hsp in members[1:]:
            start, end = hsp.subject_interval
            if start - reach - 1 <= max_intron:
                current.append(hsp)
                reach = max(reach, end)
            else:
                loci.append(current)
                current, reach = [hsp], end
        loci.append(current)
    return loci


def tile_hsps(hsps: Sequence[Hsp], max_overlap: int = MAX_TILE_OVERLAP_NT) -> list[Hsp]:
    """A non-redundant exon tiling of one locus: best HSPs first, overlaps dropped.

    An HSP joins the tiling when it overlaps the already-accepted ones by at most
    ``max_overlap`` query nucleotides and not at all in the genome. What is left is one
    alignment block per inferred exon, which is what the exon/intron structure is read from.
    """
    accepted: list[Hsp] = []
    for hsp in sorted(hsps, key=lambda h: (-h.bitscore, h.query_interval, h.subject_interval)):
        q_start, q_end = hsp.query_interval
        s_start, s_end = hsp.subject_interval
        clash = False
        for other in accepted:
            o_qs, o_qe = other.query_interval
            o_ss, o_se = other.subject_interval
            if min(q_end, o_qe) - max(q_start, o_qs) + 1 > max_overlap:
                clash = True
                break
            if min(s_end, o_se) - max(s_start, o_ss) + 1 > 0:
                clash = True
                break
        if not clash:
            accepted.append(hsp)
    return sorted(accepted, key=lambda h: h.query_interval)


def tiled_coverage_pct(exons: Sequence[Hsp]) -> float:
    """Percentage of the CDS covered by a tiling, computed without the genome.

    Separated from :func:`locus_rows` so a locus can be screened against
    ``RELATED_LOCUS_MIN_COVERAGE_PCT`` *before* any genomic sequence is read: with word size
    11 against a 972 Mb assembly, most clusters are short incidental matches, and loading
    every sequence that carries one would mean loading most of the genome.
    """
    covered = sum(end - start + 1 for start, end in merge_intervals(h.query_interval for h in exons))
    return 100 * covered / exons[0].qlen


def _n_runs(sequence: str) -> tuple[int, int]:
    """``(total N nucleotides, number of maximal N runs)`` of ``sequence``."""
    upper = sequence.upper()
    total = upper.count("N")
    runs = 0
    previous = ""
    for char in upper:
        if char == "N" and previous != "N":
            runs += 1
        previous = char
    return total, runs


def intron_termini(genome: str, exon_end: int, next_start: int, strand: str) -> str:
    """``"GT..AG"``-style termini of the intron between two exon blocks, on the gene's strand.

    ``exon_end`` and ``next_start`` are 1-based inclusive subject coordinates, so the intron
    is ``exon_end + 1 .. next_start - 1``.
    """
    intron = genome[exon_end : next_start - 1]
    if len(intron) < 4:
        return ""
    if strand == "minus":
        intron = reverse_complement(intron)
    return f"{intron[:2].upper()}..{intron[-2:].upper()}"


def splice_junctions(exons: Sequence[Hsp], genome: str, strand: str,
                     window: int = MAX_TILE_OVERLAP_NT) -> list[tuple[str, int | None]]:
    """Per inferred intron: the termini at the HSP boundary, and the canonical shift if any.

    An alignment boundary is not a splice boundary. BLAST routinely extends an HSP a few
    nucleotides past the exon into the intron, which is why consecutive exon blocks overlap
    in the query; the termini read straight off the HSP edge are then the wrong two
    nucleotides. Reading only those would report a non-canonical intron for a junction that
    is in fact canonical a base or two away, which is evidence against a structure that the
    data do not argue against.

    So each junction is reported twice: the termini at the boundary as aligned, and the
    smallest shift within the junction ambiguity window (``+/- window``, the same tolerance
    the tiling allows) at which the intron reads ``GT..AG``, or ``None`` when no shift in
    that window does. The shift keeps the intron length fixed and moves only the boundary.
    This locates a canonical junction; it does not prove the intron is spliced there.
    """
    blocks = sorted(h.subject_interval for h in exons)
    found: list[tuple[str, int | None]] = []
    for (_, end), (start, _) in zip(blocks, blocks[1:]):
        observed = intron_termini(genome, end, start, strand)
        canonical: int | None = None
        for shift in sorted(range(-window, window + 1), key=lambda d: (abs(d), d)):
            if intron_termini(genome, end + shift, start + shift, strand) == "..".join(CANONICAL_SPLICE):
                canonical = shift
                break
        found.append((observed, canonical))
    if strand == "minus":
        found.reverse()  # report introns in the gene's own 5'->3' order
    return found


def locus_rows(
    loci: Sequence[Sequence[Hsp]],
    assembly_id: str,
    sequences: dict[str, dict[str, object]],
    genomes: dict[str, str],
) -> list[dict[str, object]]:
    """One row per locus, with every statistic the locus call is to be judged on."""
    rows: list[dict[str, object]] = []
    counters: dict[str, int] = defaultdict(int)
    for members in loci:
        exons = tile_hsps(members)
        query = exons[0].query
        subject = exons[0].subject
        strand = exons[0].strand
        cds_length = exons[0].qlen
        coverage = tiled_coverage_pct(exons)
        if coverage < RELATED_LOCUS_MIN_COVERAGE_PCT:
            continue
        covered = sum(end - start + 1 for start, end in merge_intervals(h.query_interval for h in exons))
        aligned = sum(h.length for h in exons)
        mismatch = sum(h.mismatch for h in exons)
        gaps = sum(h.gaps for h in exons)
        matched = aligned - mismatch - gaps
        identity = 100 * matched / aligned if aligned else 0.0
        blocks = sorted(h.subject_interval for h in exons)
        locus_start, locus_end = blocks[0][0], blocks[-1][1]
        introns = [start - end - 1 for (_, end), (start, _) in zip(blocks, blocks[1:])]
        # Unaligned query nucleotides between consecutive exons: zero at a clean junction,
        # non-zero wherever the inferred structure does not account for the whole CDS.
        in_query = sorted(h.query_interval for h in exons)
        # Signed, and the sign carries the meaning: positive is CDS the inferred structure
        # does not account for, negative is the alignment ambiguity at the junction (the
        # tolerated overlap), which is why a boundary may need shifting to read canonically.
        query_offsets = [start - end - 1 for (_, end), (start, _) in zip(in_query, in_query[1:])]
        by_query = sorted(exons, key=lambda h: h.query_interval)
        subject_order = [h.subject_interval[0] for h in by_query]
        colinear = subject_order == sorted(subject_order, reverse=(strand == "minus"))
        genome = genomes[subject]
        span = genome[locus_start - 1 : locus_end]
        gap_nt, gap_runs = _n_runs(span)
        junctions = splice_junctions(exons, genome, strand)
        info = sequences[subject]
        counters[query] += 1
        tier = (
            "ASSIGNMENT_CRITERIA"
            if coverage >= LOCUS_MIN_QUERY_COVERAGE_PCT and identity >= ASSIGNMENT_MIN_IDENTITY_PCT
            else "RELATED"
        )
        if strand == "minus":
            introns.reverse()
        rows.append({
            "assembly_id": assembly_id,
            "target_id": query,
            "locus_id": f"{assembly_id}:{query}:{counters[query]}",
            "sequence_id": subject,
            "sequence_role": info["role"],
            "molecule": info["molecule"],
            "sequence_length": info["length"],
            "strand": strand,
            "locus_start": locus_start,
            "locus_end": locus_end,
            "locus_span_nt": locus_end - locus_start + 1,
            "query_coverage_pct": round(coverage, 3),
            "query_covered_nt": covered,
            "cds_length": cds_length,
            "identity_pct": round(identity, 3),
            "aligned_nt": aligned,
            "matched_nt": matched,
            "mismatch_nt": mismatch,
            "gap_nt": gaps,
            "n_exons_inferred": len(exons),
            "colinear": colinear,
            "n_introns_inferred": len(introns),
            "intron_sizes_nt": ";".join(str(n) for n in introns),
            "query_junction_offsets_nt": ";".join(str(n) for n in query_offsets),
            "splice_pairs_at_alignment_boundary": ";".join(pair for pair, _ in junctions),
            "canonical_splice_junctions": sum(1 for _, shift in junctions if shift is not None),
            "canonical_splice_shifts_nt": ";".join(
                "" if shift is None else str(shift) for _, shift in junctions
            ),
            "assembly_gap_nt_in_span": gap_nt,
            "assembly_gap_runs_in_span": gap_runs,
            "distance_to_sequence_end_nt": min(locus_start - 1, int(info["length"]) - locus_end),
            "exon_blocks_subject": ";".join(f"{a}-{b}" for a, b in blocks),
            "exon_blocks_query": ";".join(f"{a}-{b}" for a, b in in_query),
            "best_bitscore": max(h.bitscore for h in exons),
            "best_evalue": min(h.evalue for h in exons),
            "tier": tier,
        })
    rows.sort(key=lambda r: (str(r["target_id"]), -float(r["best_bitscore"])))
    return rows


# --------------------------------------------------------------------------- calls
def assignment_rows(assembly_id: str, loci: Sequence[dict[str, object]],
                    targets: Sequence[str]) -> list[dict[str, object]]:
    """One row per CDS: the locus assigned to it, or why none could be."""
    rows: list[dict[str, object]] = []
    for target in targets:
        mine = [row for row in loci if row["target_id"] == target]
        passing = [row for row in mine if row["tier"] == "ASSIGNMENT_CRITERIA"]
        related = [row for row in mine if row["tier"] == "RELATED"]
        chosen: dict[str, object] | None = None
        if not passing:
            status, reason = INDETERMINATE, "NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA"
        elif len(passing) > 1:
            status, reason = INDETERMINATE, "MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA"
        else:
            status, reason, chosen = DETERMINED, "", passing[0]
        rows.append({
            "assembly_id": assembly_id,
            "target_id": target,
            "status": status,
            "status_reason": reason,
            "locus_id": chosen["locus_id"] if chosen else "",
            "sequence_id": chosen["sequence_id"] if chosen else "",
            "molecule": chosen["molecule"] if chosen else "",
            "strand": chosen["strand"] if chosen else "",
            "locus_start": chosen["locus_start"] if chosen else "",
            "locus_end": chosen["locus_end"] if chosen else "",
            "query_coverage_pct": chosen["query_coverage_pct"] if chosen else "",
            "identity_pct": chosen["identity_pct"] if chosen else "",
            "n_exons_inferred": chosen["n_exons_inferred"] if chosen else "",
            "n_loci_at_assignment_criteria": len(passing),
            "n_related_loci": len(related),
            "related_locus_ids": ";".join(str(r["locus_id"]) for r in related),
        })
    return rows


def distinctness_rows(assembly_id: str, assignments: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Pairwise: do two CDS occupy distinct loci, the same locus, or is it undecidable?"""
    by_target = {row["target_id"]: row for row in assignments}
    rows: list[dict[str, object]] = []
    targets = [row["target_id"] for row in assignments]
    for index, target_a in enumerate(targets):
        for target_b in targets[index + 1 :]:
            a, b = by_target[target_a], by_target[target_b]
            unresolved = [t for t, row in ((target_a, a), (target_b, b)) if row["status"] != DETERMINED]
            if unresolved:
                rows.append({
                    "assembly_id": assembly_id, "target_a": target_a, "target_b": target_b,
                    "status": INDETERMINATE,
                    "status_reason": "UNASSIGNED_LOCUS:" + ",".join(unresolved),
                    "same_sequence": "", "sequence_a": a["sequence_id"], "sequence_b": b["sequence_id"],
                    "span_a": "", "span_b": "", "spans_overlap": "", "overlap_nt": "",
                    "gap_between_spans_nt": "",
                })
                continue
            same = a["sequence_id"] == b["sequence_id"]
            a_start, a_end = int(a["locus_start"]), int(a["locus_end"])
            b_start, b_end = int(b["locus_start"]), int(b["locus_end"])
            overlap = min(a_end, b_end) - max(a_start, b_start) + 1 if same else 0
            overlaps = same and overlap > 0
            if not same:
                status, reason = DETERMINED, "DIFFERENT_ASSEMBLY_SEQUENCES"
            elif not overlaps:
                status, reason = DETERMINED, "SAME_SEQUENCE_NON_OVERLAPPING_SPANS"
            else:
                status, reason = INDETERMINATE, "OVERLAPPING_SPANS_ON_ONE_SEQUENCE"
            rows.append({
                "assembly_id": assembly_id, "target_a": target_a, "target_b": target_b,
                "status": status, "status_reason": reason, "same_sequence": same,
                "sequence_a": a["sequence_id"], "sequence_b": b["sequence_id"],
                "span_a": f"{a_start}-{a_end}", "span_b": f"{b_start}-{b_end}",
                "spans_overlap": overlaps,
                "overlap_nt": max(overlap, 0) if same else 0,
                "gap_between_spans_nt": (max(a_start, b_start) - min(a_end, b_end) - 1) if same and not overlaps else "",
            })
    return rows


def copy_number_rows(assembly_id: str, assignments: Sequence[dict[str, object]],
                     stats: dict[str, object], level: str) -> list[dict[str, object]]:
    """Genomic copy number per CDS: the count that question 2 actually turns on."""
    return [{
        "assembly_id": assembly_id,
        "target_id": row["target_id"],
        "n_loci_at_assignment_criteria": row["n_loci_at_assignment_criteria"],
        "n_related_loci": row["n_related_loci"],
        "locus_ids": str(row["locus_id"]) or str(row["related_locus_ids"]),
        "assembly_level": level,
        "n_scaffolds": stats["number_of_sequences"],
        "scaffold_n50": stats["scaffold_n50"],
        "interpretation_key": (
            "ONE_LOCUS_DETECTED" if row["n_loci_at_assignment_criteria"] == 1
            else "MULTIPLE_LOCI_DETECTED" if row["n_loci_at_assignment_criteria"] > 1
            else "NO_LOCUS_DETECTED"
        ),
    } for row in assignments]


# --------------------------------------------------------------------------- run
def _blast_with_archive(log: CommandLog, query: Path, db: Path, stem: Path) -> list[Hsp]:
    """blastn into an ASN.1 archive, then two renderings of it; the archive is the record."""
    archive = stem.parent / (stem.name + ".asn")
    table = stem.parent / (stem.name + ".outfmt6.tsv")
    log.run(["blastn", "-query", str(query), "-db", str(db), *BLASTN_PARAMS,
             "-max_target_seqs", str(MAX_TARGET_SEQS), "-outfmt", "11", "-out", str(archive)])
    log.run(["blast_formatter", "-archive", str(archive),
             "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)], stdout_path=table)
    log.run(["blast_formatter", "-archive", str(archive), "-outfmt", "0"],
            stdout_path=stem.parent / (stem.name + ".pairwise.txt"))
    return parse_hsp_table(table.read_text(encoding="utf-8"), BLAST_OUTFMT_FIELDS)


def _assembly_record(root: Path, entry: dict[str, object], hashes: dict[str, dict[str, object]],
                     checked: dict[str, object]) -> dict[str, object]:
    """Provenance for one declared assembly: declared versus observed, compared not asserted."""
    label = str(entry["id"])
    mode = str(hashes[label]["verified_by"])
    observed = hashes[label][mode]
    declared_decompressed = entry.get("sha256_decompressed")
    observed_decompressed = hashes[label]["sha256_decompressed"]
    return {
        **file_record(root, root / str(entry["path"])),
        "id": label,
        "accession_version": entry["accession_version"],
        "assembly_name": entry.get("assembly_name"),
        "role": entry.get("role"),
        "assembly_level": entry.get("assembly_level"),
        "biosample": entry.get("biosample"),
        "verified_by": mode,
        "declared_value": entry.get(mode),
        "observed_value": observed,
        "declared_hash_agrees": observed == entry.get(mode),
        "sha256_decompressed_declared": declared_decompressed,
        "sha256_decompressed_observed": observed_decompressed,
        "sha256_decompressed_agrees": observed_decompressed == declared_decompressed,
        "checked": checked[label],
    }


def run_mapping(root: Path, out: Path, panel_path: Path) -> dict[str, object]:
    root, out = root.resolve(), out.resolve()
    panel = load_panel(panel_path)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    log = CommandLog()
    versions = {
        "blastn": log.run(["blastn", "-version"]).splitlines()[0].strip(),
        "makeblastdb": log.run(["makeblastdb", "-version"]).splitlines()[0].strip(),
        "blast_formatter": log.run(["blast_formatter", "-version"]).splitlines()[0].strip(),
    }

    # 1. queries, derived from the repository anchors and checked against the publication.
    anchor_declared = panel["repository_inputs"]["target_anchor_sequences"]
    anchor_path = _resolve(root, anchor_declared, "target_anchor_sequences")
    anchor_hashes = _check_hash(anchor_path, anchor_declared, "target_anchor_sequences")
    queries = derive_queries(anchor_path, panel["queries"])
    write_tsv(out / "queries.tsv", queries, QUERY_COLUMNS)
    query_path = raw / "cds_queries.fna"
    query_path.write_text(
        format_fasta((str(q["target_id"]), str(q["cds"])) for q in queries),
        encoding="ascii", newline="\n",
    )
    targets = [str(q["target_id"]) for q in queries]

    # 2. one mapping per declared assembly.
    assembly_hashes: dict[str, dict[str, object]] = {}
    assembly_checked: dict[str, object] = {}
    all_loci: list[dict[str, object]] = []
    all_assignments: list[dict[str, object]] = []
    all_distinctness: list[dict[str, object]] = []
    all_copy_number: list[dict[str, object]] = []
    blast_counts: dict[str, object] = {}
    for entry in panel["assemblies"]:
        label = str(entry["id"])
        archive_path = _resolve(root, entry, label)
        assembly_hashes[label] = _check_hash(archive_path, entry, label)
        # The expanded FASTA and the BLAST database are ~2.5x the assembly in size, are
        # derived rather than results, and are deleted when the run ends. They go to a
        # temporary directory, which also keeps them off a network or 9p-mounted working
        # tree: building a 1 Gb database over such a mount is slower by more than an order
        # of magnitude. Set TMPDIR to choose where that is.
        scratch = Path(tempfile.mkdtemp(prefix=f"nb01_locus_{label}_"))
        fasta = scratch / f"{label}.fna"
        with gzip.open(archive_path, "rb") as source, fasta.open("wb") as target:
            shutil.copyfileobj(source, target)
        observed_decompressed = sha256_file(fasta)
        declared_decompressed = entry.get("sha256_decompressed")
        if declared_decompressed and observed_decompressed != declared_decompressed:
            raise LocusInputError(
                f"declared input changed: {label} (decompressed FASTA)\n"
                f"  declared sha256={declared_decompressed}\n  observed sha256={observed_decompressed}"
            )
        assembly_hashes[label]["sha256_decompressed"] = observed_decompressed
        sequences, stats = scan_assembly(fasta)
        assembly_checked[label] = check_declared_stats(label, entry, stats)

        db = scratch / f"{label}.db"
        log.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-title", label, "-out", str(db)],
                stdout_path=raw / f"{label}.makeblastdb.log")
        hsps = _blast_with_archive(log, query_path, db, raw / f"blastn_{label}")
        subjects = {h.subject for h in hsps}
        loci = cluster_loci(hsps)
        # Screen on coverage before touching the genome: see tiled_coverage_pct().
        kept = [members for members in loci if tiled_coverage_pct(tile_hsps(members)) >= RELATED_LOCUS_MIN_COVERAGE_PCT]
        blast_counts[label] = {
            "hsps": len(hsps),
            "subjects_with_hsps": len(subjects),
            "max_target_seqs": MAX_TARGET_SEQS,
            "observed_subjects_below_limit": len(subjects) < MAX_TARGET_SEQS,
            "clusters": len(loci),
            "clusters_at_related_coverage": len(kept),
        }
        wanted = {members[0].subject for members in kept}
        genomes = read_sequences(fasta, wanted) if wanted else {}
        rows = locus_rows(kept, label, sequences, genomes)
        assignments = assignment_rows(label, rows, targets)
        all_loci += rows
        all_assignments += assignments
        all_distinctness += distinctness_rows(label, assignments)
        all_copy_number += copy_number_rows(label, assignments, stats, str(entry.get("assembly_level", "")))
        assembly_checked[label] = {"assembly_stats": assembly_checked[label], "observed_stats": stats}
        # The declared .gz is the input of record; both the expansion and the database are
        # reproducible from it by the commands recorded in the manifest.
        shutil.rmtree(scratch, ignore_errors=True)

    write_tsv(out / "loci.tsv", all_loci, LOCUS_COLUMNS)
    write_tsv(out / "assignments.tsv", all_assignments, ASSIGNMENT_COLUMNS)
    write_tsv(out / "distinctness.tsv", all_distinctness, DISTINCTNESS_COLUMNS)
    write_tsv(out / "copy_number.tsv", all_copy_number, COPY_NUMBER_COLUMNS)

    manifest = {
        "schema_version": 1,
        "kind": "nb01_dsrnase_locus_mapping",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "status_porcelain": _git(root, "status", "--porcelain"),
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            **versions,
        },
        "parameters": {
            "blastn": BLASTN_PARAMS,
            "max_target_seqs": MAX_TARGET_SEQS,
            "max_intron_nt": MAX_INTRON_NT,
            "locus_min_query_coverage_pct": LOCUS_MIN_QUERY_COVERAGE_PCT,
            "assignment_min_identity_pct": ASSIGNMENT_MIN_IDENTITY_PCT,
            "related_locus_min_coverage_pct": RELATED_LOCUS_MIN_COVERAGE_PCT,
            "max_tile_overlap_nt": MAX_TILE_OVERLAP_NT,
            "canonical_splice": list(CANONICAL_SPLICE),
            "panel": panel_path.resolve().relative_to(root).as_posix(),
        },
        "commands": log.entries,
        "inputs": {
            # The panel is itself an input: it carries every declaration the run was checked
            # against, so the manifest pins which version of it was used. Tracked text, so
            # the LF-normalised hash is the checkout-independent one.
            "panel": {
                **file_record(root, panel_path, with_lf=True),
                "kind": panel.get("kind"),
                "schema_version": panel.get("schema_version"),
            },
            "repository": {
                "target_anchor_sequences": {
                    **file_record(root, anchor_path,
                                  with_lf=anchor_hashes["verified_by"] == "sha256_lf_normalized"),
                    "role": anchor_declared.get("role"),
                    "verified_by": anchor_hashes["verified_by"],
                    "declared_value": anchor_declared.get(anchor_hashes["verified_by"]),
                    "observed_value": anchor_hashes[anchor_hashes["verified_by"]],
                    "declared_hash_agrees":
                        anchor_hashes[anchor_hashes["verified_by"]]
                        == anchor_declared.get(anchor_hashes["verified_by"]),
                },
            },
            "assemblies": [_assembly_record(root, entry, assembly_hashes, assembly_checked)
                           for entry in panel["assemblies"]],
            "surveyed_not_used": panel.get("surveyed_not_used", []),
            "queries": [
                {key: row[key] for key in QUERY_COLUMNS} for row in queries
            ],
        },
        "results": {
            "blast": blast_counts,
            "loci_reported": len(all_loci),
            "loci_at_assignment_criteria": sum(1 for r in all_loci if r["tier"] == "ASSIGNMENT_CRITERIA"),
            "assignments_determined": sum(1 for r in all_assignments if r["status"] == DETERMINED),
            "assignments_indeterminate": sum(1 for r in all_assignments if r["status"] == INDETERMINATE),
            "distinctness_determined": sum(1 for r in all_distinctness if r["status"] == DETERMINED),
            "distinctness_indeterminate": sum(1 for r in all_distinctness if r["status"] == INDETERMINATE),
            "copy_number": {
                f"{r['assembly_id']}:{r['target_id']}": r["n_loci_at_assignment_criteria"]
                for r in all_copy_number
            },
        },
        "outputs": [
            {"path": path.relative_to(out).as_posix(), "sha256": sha256_file(path),
             "bytes": path.stat().st_size}
            for path in sorted(out.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="NB01 dsRNase locus mapping: the three published CDS against the declared "
                    "Dalbulus maidis genome assemblies, from declared inputs only."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=None, help=f"output directory (default: {DEFAULT_OUT})")
    parser.add_argument("--panel", default=None, help=f"input panel (default: {DEFAULT_PANEL})")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out).resolve() if args.out else root / DEFAULT_OUT
    panel_path = Path(args.panel).resolve() if args.panel else root / DEFAULT_PANEL
    try:
        manifest = run_mapping(root, out, panel_path)
    except LocusInputError as exc:
        print(f"mapping refused to run:\n{exc}")
        return 2
    print(json.dumps(manifest["results"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
