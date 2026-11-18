#!/usr/bin/env python3
"""RNA-seq support for the 642/643 junction of the published Dmai-dsRNase-3 CDS.

The question
------------
The published dsRNase-3 CDS (`TRINITY_DN5008_c0_g1_i24`, 1,236 nt) aligns to
`OZ319704.1` of `GCA_975739785.1` on the plus strand as one splice-aware chain
whose fourth junction leads out of the `ENSCHMG00000003138` region and into the
`ube2w` (`ENSCHMG00000002609`) region: the last aligned base before the gap is
122,007,348 and the first aligned base after it is 122,012,479, between CDS
positions 642 and 643. No annotated transcript on `OZ319704.1` carries an
intron with both of those boundaries. This command asks one thing of already
materialised RNA-seq alignments: **do reads cross that junction**, and if none
do, was the coverage informative enough for that absence to mean anything.

It answers nothing about the rest of the CDS. A fragment crossing 642/643
supports *that junction*; it does not place the whole 1,236 nt CDS on one
molecule. That attribution needs evidence linking this junction to the other
blocks of the chain and is explicitly out of scope here.

Indexing convention
-------------------
**Every coordinate in this module, its inputs and its outputs is 1-based and
inclusive**, on the forward strand of the named reference sequence.

- CDS positions are 1-based inclusive over the 1,236 nt published CDS.
- Genomic coordinates are 1-based inclusive, as SAM `POS` is.
- An intron is named by its own first and last base: the 642/643 gap is
  `122,007,349-122,012,478`, which is the last aligned base + 1 through the
  first aligned base - 1. A junction is *exact* only when the `N` operation of
  a CIGAR produces both of those coordinates.

Alignment input: materialised SAM
---------------------------------
Input is one plain-text SAM per library, with its header, produced beforehand
and declared with its `sha256`. This module runs no aligner: it reads
coordinates that a named aligner already assigned, which keeps the counting
reproducible from a fixed artifact and keeps the alignment itself auditable
separately. A BAM is converted with `samtools view -h` before it is declared.

The command that produces such a SAM from raw reads against the **complete**
assembly, annotation-free, is documented in `ALIGNMENT_RECIPE` below and is
reproduced in the manifest of every run.

Scope of the counting
---------------------
- Per library, and per fragment: each `QNAME` is counted once however many of
  its reads cross the junction.
- A crossing requires **both** exact intron boundaries in one read's CIGAR,
  with at least `min_anchor_nt` query bases aligned in the block on each side.
- Mappings that are ambiguous, flagged as duplicates, secondary,
  supplementary, or short-anchored are counted in their own columns and never
  as support. So are junctions near the target but not at it, and pairs whose
  two mates sit in the two flanks with no read crossing the junction.
- The two annotated junctions 456/457 and 870/871 are counted by the same rule
  in the same library, as the internal detectability control, and both flanks'
  coverage is reported beside them.
- An absence of crossing fragments is called interpretable only where a
  crossing read could have been seen: qualifying fragments must cover the whole
  `min_anchor_nt` footprint immediately against each edge of the junction, the
  `anchor zone`. Otherwise the library is reported inconclusive, however many
  fragments sit elsewhere in the flanks.

Run as:

    python -m zeaguard.nb01_dsrnase3_transcript_evidence \
        --root . --panel <libraries.json> \
        --out-subdir results/bioinformatics/nb01/<run-directory>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# --------------------------------------------------------------------------
# Reused machinery
#
# The SAM/CIGAR reader, the coordinate normalisation, the atomic output-
# directory claim and the hashing helpers already exist in the splice-aware
# check of this same investigation, with their own tests. They are imported
# from it rather than reimplemented, so both commands read a CIGAR by exactly
# one piece of code.
# --------------------------------------------------------------------------

_SPLICE_CHECK_NAME = "check_nb01_dsrnase_splicing"
_SPLICE_CHECK_PATH = Path(__file__).resolve().parents[2] / "scripts" / f"{_SPLICE_CHECK_NAME}.py"


def _load_splice_check():
    if _SPLICE_CHECK_NAME in sys.modules:
        return sys.modules[_SPLICE_CHECK_NAME]
    if not _SPLICE_CHECK_PATH.is_file():
        raise RuntimeError(f"required sibling module is missing: {_SPLICE_CHECK_PATH}")
    spec = importlib.util.spec_from_file_location(_SPLICE_CHECK_NAME, _SPLICE_CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so @dataclass can resolve the module's own
    # namespace under `from __future__ import annotations`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_splice = _load_splice_check()

VerificationError = _splice.VerificationError
parse_cigar = _splice.parse_cigar
parse_sam = _splice.parse_sam
normalise_walk = _splice.normalise_walk
read_length_from_cigar = _splice.read_length_from_cigar
reserve_output_dir = _splice.reserve_output_dir
sha256_file = _splice.sha256_file
sha256_text = _splice.sha256_text
union_length = _splice.union_length
walk_record = _splice.walk_record
write_tsv = _splice.write_tsv

# --------------------------------------------------------------------------
# The question, declared. These coordinates are the subject of the run and are
# not configurable: they come from the splice-aware alignment recorded in the
# NB01 run record of 2026-11-15 (addendum 2) and mean nothing on another
# reference, which is why the panel must declare the reference it used.
# --------------------------------------------------------------------------

INDEXING_CONVENTION = (
    "1-based inclusive on the forward strand of the named reference sequence, for both CDS "
    "and genomic coordinates; an intron is named by its own first and last base"
)

REFERENCE = {
    "assembly_accession": "GCA_975739785.1",
    "assembly_name": "ihDalMaid1.1",
    "sequence_name": "OZ319704.1",
    # Read directly from the assembly FASTA and cross-checked against the @SQ LN
    # of the saved alignment of the 2026-11-15 run record. A panel declaring any
    # other length is refused: these coordinates are defined on this sequence.
    "sequence_length_nt": 122_877_750,
    "cds_query": "TRINITY_DN5008_c0_g1_i24",
    "cds_length_nt": 1236,
    "cds_strand_on_reference": "+",
}


@dataclass(frozen=True)
class JunctionSpec:
    """One junction, as the published-CDS chain assigns it."""

    name: str
    intron_start: int          # first intronic base
    intron_end: int            # last intronic base
    cds_upstream: int          # last CDS position before the gap
    cds_downstream: int        # first CDS position after the gap
    annotated_intron: bool     # does an annotated transcript carry both boundaries

    @property
    def intron_len_nt(self) -> int:
        return self.intron_end - self.intron_start + 1


# The junction in question: no annotated transcript carries both boundaries.
TARGET_JUNCTION = JunctionSpec(
    name="cds_642_643", intron_start=122_007_349, intron_end=122_012_478,
    cds_upstream=642, cds_downstream=643, annotated_intron=False)

# The two annotated junctions of the same chain, used in the same library as
# the detectability control: a library in which no spliced read is found at an
# annotated junction cannot carry the absence of one at the target.
CONTROL_JUNCTIONS = (
    JunctionSpec(name="cds_456_457", intron_start=122_005_921, intron_end=122_007_162,
                 cds_upstream=456, cds_downstream=457, annotated_intron=True),
    JunctionSpec(name="cds_870_871", intron_start=122_012_707, intron_end=122_014_116,
                 cds_upstream=870, cds_downstream=871, annotated_intron=True),
)

# The aligned blocks immediately flanking the target junction, as the chain
# assigns them. Coverage of both is what makes an absence of crossing reads
# interpretable.
FLANKS = {
    "upstream": {"ref_start": 122_007_163, "ref_end": 122_007_348,
                 "cds_start": 457, "cds_end": 642},
    "downstream": {"ref_start": 122_012_479, "ref_end": 122_012_706,
                   "cds_start": 643, "cds_end": 870},
}

ALIGNMENT_RECIPE = {
    "reference": "GCA_975739785.1_ihDalMaid1.1_genomic.fna, the complete assembly, "
                 "sha256 54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04 "
                 "decompressed",
    "annotation_supplied_to_the_aligner": None,
    "tools": {"hisat2": "2.2.1", "samtools": "1.21"},
    "commands": [
        "hisat2-build -p 8 GCA_975739785.1_ihDalMaid1.1_genomic.fna ihDalMaid1.1",
        "hisat2 -p 8 --dta --max-intronlen 50000 -x ihDalMaid1.1 "
        "-1 <LIB>_1.fastq.gz -2 <LIB>_2.fastq.gz "
        "--summary-file <LIB>.hisat2.summary -S <LIB>.raw.sam",
        "samtools collate -@ 4 -O -u <LIB>.raw.sam "
        "| samtools fixmate -m -u - - "
        "| samtools sort -@ 4 -o <LIB>.pos.bam -",
        "samtools markdup -@ 4 <LIB>.pos.bam <LIB>.markdup.bam",
        "samtools index -@ 4 <LIB>.markdup.bam",
        "samtools view -h <LIB>.markdup.bam OZ319704.1 > <LIB>.OZ319704.1.sam",
    ],
    "notes": [
        "No annotation and no known-splice-site file is given to the aligner, so the "
        "target junction can only be found de novo.",
        "--max-intronlen 50000 keeps the 50 kb scale of the historical clustering and "
        "admits the 5,130 nt target gap.",
        "--no-mixed and --no-discordant are deliberately NOT used: discarding those "
        "alignments would discard the mate-bridging observations this command counts.",
        "samtools collate groups the records by read name, which is what fixmate "
        "requires: fixmate refuses to pair records it does not see adjacently, and "
        "without the mate-coordinate tag it writes, markdup cannot call duplicates. "
        "hisat2 happens to emit mates adjacently, so collate is a guarantee rather "
        "than a repair, and it is cheaper than a full name sort.",
        "markdup only flags duplicates (0x400); it must not remove them, because this "
        "command reports them in their own column.",
        "samtools index must run before the region view: without a .bai, "
        "'samtools view <bam> OZ319704.1' fails rather than reading the region.",
        "The final view keeps the header, so @SQ and @PG reach the manifest; slicing to "
        "OZ319704.1 is what keeps the declared input small.",
        "Anchor recovery measured on synthetic 100 nt reads crossing this junction "
        "(scripts/check_nb01_dsrnase3_alignment_recipe.py): hisat2 2.2.1 with --dta "
        "splices at the declared coordinates from a 20 nt anchor upwards on both "
        "sides; 15 nt only on the upstream side; 11-15 nt align unspliced as a "
        "full-length 100M carrying mismatches; 4-10 nt are soft-clipped. min_anchor_nt "
        "is set to 20 for that reason. The 11-15 nt behaviour matters twice: such a "
        "crossing read is invisible to this command, and it is reported as a confident "
        "unspliced alignment rather than as nothing.",
        "The boundary measured here is sequence-, read-length- and parameter-dependent, "
        "so it is the recovery of this configuration and not a property of hisat2.",
    ],
}


@dataclass(frozen=True)
class Criteria:
    """Quality, anchoring and informative-coverage criteria, declared before the run.

    `min_mapq` 30: above any aligner's multi-mapping plateau (HISAT2 reports 1 for
    two-locus hits and 0/3 below that; STAR reports 3 and below), so a read kept
    here is one the aligner placed at a single locus. Combined with `NH` when the
    aligner emits it, never replaced by it, since not every aligner does.

    `min_anchor_nt` 20: set to what the declared recipe actually recovers, not
    to a statistical floor. Measured on synthetic 100 nt reads crossing this
    junction at anchors 4 to 50 nt (`scripts/check_nb01_dsrnase3_alignment_recipe.py`),
    hisat2 2.2.1 with `--dta` reported a spliced alignment at the declared
    coordinates only from 20 nt upwards on both sides: 15 nt was spliced on the
    upstream side alone, 11 to 15 nt were aligned unspliced as a full-length
    `100M` with mismatches, and 4 to 10 nt were soft-clipped. A shorter anchor
    therefore never reaches this counter whatever it is set to, and a smaller
    value would also shrink the anchor zone below the footprint a real crossing
    read occupies. 20 aligned query bases on each side also put a chance match
    far below any plausible background.

    `min_support_fragments` 2: one fragment is one library-preparation artefact
    away from being nothing. The observed count is reported whatever it is, so
    the threshold labels the verdict without hiding the evidence.

    `neighbour_window_nt` 20: a junction within 20 nt of either declared
    boundary is recorded as a neighbour rather than silently dropped, which is
    what separates "no read crosses this junction" from "reads cross a junction
    nearby".

    `min_anchor_zone_fragments` 5: absence is only interpretable where a
    crossing read could have been seen, and a crossing read must align
    `min_anchor_nt` bases immediately against the boundary. So coverage is
    required over exactly that footprint — the `min_anchor_nt` bases adjacent to
    each edge of the junction, the `anchor zone` — and a fragment counts towards
    the floor only when it covers the whole zone on that side. Five such
    fragments on each side is the floor for calling a library informative.

    Counting fragments that merely overlap a wider window instead would let a
    library pass with the bases next to the boundary uncovered: 40 nt of a 50 nt
    window can be blank while five fragments still overlap its far end, and no
    anchored crossing read could ever have been observed there. That is why the
    criterion is the anchor footprint and not a window overlap.
    """

    min_mapq: int = 30
    min_anchor_nt: int = 20
    min_support_fragments: int = 2
    neighbour_window_nt: int = 20
    min_anchor_zone_fragments: int = 5
    require_control_junction_support: bool = True


VERDICTS = (
    "JUNCTION_SUPPORTED",
    "SUPPORT_BELOW_DECLARED_THRESHOLD",
    "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE",
    "INCONCLUSIVE_INSUFFICIENT_COVERAGE",
)

ORIGIN_CLASSES = ("confirmed_origin", "comparative", "open_link")

OUTPUT_ROOT = "results/bioinformatics/nb01"

# The two BioProjects the record disagrees about. Carried into every manifest so
# that no run can be read as having settled which library assembled the
# published contig.
LIBRARY_PROVENANCE_NOTE = {
    "PRJNA631706": "linked from the master GenBank record of the TSA assembly GITV00000000.1 "
                   "(SRA runs SRR11822333-SRR11822348)",
    "PRJNA579843": "cited by Xu et al. and recorded in data/reference/manifest.json",
    "status": "the two differ and neither is established as the source of the reads that "
              "assembled TRINITY_DN5008_c0_g1_i24; the dissertation of Victorio Palacio "
              "(https://repositorio.unnoba.edu.ar/xmlui/handle/23601/481) is a lead, not "
              "documentary evidence",
    "rule": "no library is classified confirmed_origin without documentary_evidence naming "
            "the document that ties it to the published assembly",
}


# --------------------------------------------------------------------------
# Input reading. Nothing here classifies and nothing here writes.
# --------------------------------------------------------------------------


def load_panel(path: Path, root: Path) -> dict:
    """Read and validate the library panel, resolving each declared SAM path."""
    try:
        panel = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise VerificationError(f"panel is not valid JSON: {path}: {error}") from None
    if not isinstance(panel, dict):
        raise VerificationError(f"panel must be a JSON object, found {type(panel).__name__}")

    reference = panel.get("reference")
    if not isinstance(reference, dict):
        raise VerificationError("panel is missing its 'reference' object")
    for key in ("assembly_accession", "sequence_name", "sequence_length_nt"):
        if key not in reference:
            raise VerificationError(f"panel reference is missing '{key}'")
    for key in ("assembly_accession", "sequence_name", "sequence_length_nt"):
        if reference[key] != REFERENCE[key]:
            raise VerificationError(
                f"panel reference {key} is {reference[key]!r}; these coordinates are only "
                f"defined on {REFERENCE[key]!r}")

    libraries = panel.get("libraries")
    if not isinstance(libraries, list) or not libraries:
        raise VerificationError("panel must declare a non-empty 'libraries' list")

    seen: set[str] = set()
    for entry in libraries:
        if not isinstance(entry, dict):
            raise VerificationError("every library entry must be a JSON object")
        for key in ("library_id", "sam", "sha256", "origin_class", "provenance"):
            if not entry.get(key):
                raise VerificationError(
                    f"library entry is missing '{key}': {entry.get('library_id', '<unnamed>')}")
        library_id = entry["library_id"]
        if library_id in seen:
            raise VerificationError(f"duplicate library_id in panel: {library_id}")
        seen.add(library_id)
        if entry["origin_class"] not in ORIGIN_CLASSES:
            raise VerificationError(
                f"{library_id}: origin_class {entry['origin_class']!r} is not one of "
                f"{', '.join(ORIGIN_CLASSES)}")
        if entry["origin_class"] == "confirmed_origin" and not entry.get("documentary_evidence"):
            raise VerificationError(
                f"{library_id}: origin_class 'confirmed_origin' requires "
                f"'documentary_evidence' naming the document that ties this library to the "
                f"assembly of the published contig")
        sam_path = (root / entry["sam"]).resolve()
        if not sam_path.is_file():
            raise VerificationError(f"{library_id}: declared SAM is missing: {entry['sam']}")
        observed = sha256_file(sam_path)
        if observed != entry["sha256"]:
            raise VerificationError(
                f"{library_id}: sha256 mismatch for {entry['sam']}: declared "
                f"{entry['sha256']}, observed {observed}")
        entry["_resolved_path"] = sam_path
        entry["_observed_sha256"] = observed
    return panel


def read_library_sam(path: Path, reference: dict) -> tuple[dict, list]:
    """Read one library's SAM, checking that its header describes the declared reference."""
    header, records = parse_sam(path.read_text(encoding="utf-8"))
    if not header:
        raise VerificationError(f"{path.name}: SAM has no header; @SQ and @PG are required")

    declared_len = None
    for line in header:
        if not line.startswith("@SQ"):
            continue
        fields = dict(
            part.split(":", 1) for part in line.split("\t")[1:] if ":" in part)
        if fields.get("SN") == REFERENCE["sequence_name"]:
            declared_len = int(fields["LN"])
    if declared_len is None:
        raise VerificationError(
            f"{path.name}: SAM header has no @SQ line for {REFERENCE['sequence_name']}")
    if declared_len != reference["sequence_length_nt"]:
        raise VerificationError(
            f"{path.name}: @SQ LN for {REFERENCE['sequence_name']} is {declared_len}, "
            f"the panel declares {reference['sequence_length_nt']}; the alignment was not "
            f"made against the declared reference")

    aligner_version, aligner_command = _splice.pg_version_from_header(header)
    programme = next((line for line in header if line.startswith("@PG")), None)
    if programme is None:
        raise VerificationError(
            f"{path.name}: SAM header has no @PG line, so the aligner that assigned these "
            f"coordinates is unrecorded")
    aligner_name = next(
        (part[3:] for part in programme.split("\t")[1:] if part.startswith("PN:")), None)
    return ({"sequence_length_nt": declared_len, "aligner_name": aligner_name,
             "aligner_version": aligner_version, "aligner_command": aligner_command,
             "n_header_lines": len(header)}, records)


# --------------------------------------------------------------------------
# Classification. Pure functions over parsed records; no file is read or
# written below this line.
# --------------------------------------------------------------------------


def ref_aligned_intervals(ops: list[tuple[int, str]], pos: int) -> list[tuple[int, int]]:
    """Reference intervals an alignment actually covers with a base, 1-based inclusive.

    Deletions and junctions advance the reference without covering it, so a
    coverage figure taken from here never counts a deleted or intronic base.
    """
    intervals: list[tuple[int, int]] = []
    reference = pos
    for length, op in ops:
        if op in ("M", "=", "X"):
            intervals.append((reference, reference + length - 1))
            reference += length
        elif op in ("D", "N"):
            reference += length
    return intervals


def _overlap_nt(intervals: list[tuple[int, int]], start: int, end: int) -> int:
    return sum(max(0, min(e, end) - max(s, start) + 1) for s, e in intervals)


def _aligned_nt(block: dict) -> int:
    """Query bases a block aligns to a reference base: M/=/X only, insertions excluded."""
    return sum(end - start + 1 for start, end in block["aligned"])


def is_duplicate(record) -> bool:
    """The optical/PCR duplicate flag (0x400), which `SamRecord` does not expose."""
    return bool(record.flag & 0x400)


def _nh_tag(record) -> int | None:
    value = record.tags.get("NH")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise VerificationError(f"{record.qname}: NH tag is not an integer: {value!r}") from None


def _disqualification(record, criteria: Criteria) -> str | None:
    """Why this record may not count as support, or None if it may."""
    if is_duplicate(record):
        return "flagged_duplicate"
    if record.is_secondary:
        return "secondary_alignment"
    if record.is_supplementary:
        return "supplementary_alignment"
    nh = _nh_tag(record)
    if nh is not None and nh > 1:
        return f"ambiguous_nh_{nh}"
    if record.mapq < criteria.min_mapq:
        return f"ambiguous_mapq_{record.mapq}"
    return None


def _boundary_match(junction: dict, spec: JunctionSpec, criteria: Criteria) -> str | None:
    """How a CIGAR junction relates to a declared one: exact, one edge, near, or not at all."""
    start_delta = junction["intron_ref_start"] - spec.intron_start
    end_delta = junction["intron_ref_end"] - spec.intron_end
    if start_delta == 0 and end_delta == 0:
        return "exact"
    if start_delta == 0:
        return "donor_only"
    if end_delta == 0:
        return "acceptor_only"
    if (abs(start_delta) <= criteria.neighbour_window_nt
            and abs(end_delta) <= criteria.neighbour_window_nt):
        return "neighbour"
    return None


def observe_record(record, index: int, specs: tuple[JunctionSpec, ...],
                   criteria: Criteria) -> dict:
    """Everything one alignment record contributes, for every declared junction."""
    ops = parse_cigar(record.cigar)
    read_len = read_length_from_cigar(ops)
    walk = normalise_walk(walk_record(ops, record.pos), read_len, record.is_reverse)
    blocks = sorted(walk["blocks"], key=lambda block: block["r_start"])
    disqualified_by = _disqualification(record, criteria)

    junction_rows: list[dict] = []
    for junction in sorted(walk["junctions"], key=lambda j: j["intron_ref_start"]):
        for spec in specs:
            match = _boundary_match(junction, spec, criteria)
            if match is None:
                continue
            upstream = next((b for b in blocks if b["r_end"] == junction["intron_ref_start"] - 1),
                            None)
            downstream = next((b for b in blocks if b["r_start"] == junction["intron_ref_end"] + 1),
                              None)
            anchor_up = _aligned_nt(upstream) if upstream else 0
            anchor_down = _aligned_nt(downstream) if downstream else 0
            if match != "exact":
                category = match
            elif disqualified_by is not None:
                category = "disqualified"
            elif min(anchor_up, anchor_down) < criteria.min_anchor_nt:
                category = "short_anchor"
            else:
                category = "support"
            junction_rows.append({
                "junction_name": spec.name,
                "boundary_match": match,
                "category": category,
                "intron_ref_start": junction["intron_ref_start"],
                "intron_ref_end": junction["intron_ref_end"],
                "intron_len_nt": junction["intron_len"],
                "delta_intron_start_nt": junction["intron_ref_start"] - spec.intron_start,
                "delta_intron_end_nt": junction["intron_ref_end"] - spec.intron_end,
                "anchor_upstream_aligned_nt": anchor_up,
                "anchor_downstream_aligned_nt": anchor_down,
                "counted_as_support": category == "support",
            })

    return {
        "record_index": index,
        "qname": record.qname,
        "flag": record.flag,
        "mapq": record.mapq,
        "nh": _nh_tag(record),
        "strand": "-" if record.is_reverse else "+",
        "record_class": record.record_class,
        "is_duplicate": is_duplicate(record),
        "cigar": record.cigar,
        "ref_start": record.pos,
        "ref_end": walk["ref_end"],
        "ref_aligned_intervals": ref_aligned_intervals(ops, record.pos),
        "disqualified_by": disqualified_by,
        "junctions": junction_rows,
        "n_cigar_junctions": len(walk["junctions"]),
    }


def anchor_zone(side: str, criteria: Criteria) -> tuple[int, int]:
    """The bases a crossing read must align on `side` of the target junction.

    Immediately against the boundary and extending away from the intron, so it
    is exactly the footprint an anchored crossing read occupies on that side.
    """
    if side == "upstream":
        return (TARGET_JUNCTION.intron_start - criteria.min_anchor_nt,
                TARGET_JUNCTION.intron_start - 1)
    return (TARGET_JUNCTION.intron_end + 1,
            TARGET_JUNCTION.intron_end + criteria.min_anchor_nt)


def _flank_statistics(observations: list[dict], criteria: Criteria) -> dict:
    """Coverage of each flank and of its anchor zone, from qualifying records only."""
    statistics: dict = {}
    for side, flank in FLANKS.items():
        start, end = flank["ref_start"], flank["ref_end"]
        zone_start, zone_end = anchor_zone(side, criteria)
        covered: list[tuple[int, int]] = []
        zone_covered: list[tuple[int, int]] = []
        zone_fragments: set[str] = set()
        for observation in observations:
            if observation["disqualified_by"] is not None:
                continue
            intervals = observation["ref_aligned_intervals"]
            for interval_start, interval_end in intervals:
                if interval_end >= start and interval_start <= end:
                    covered.append((max(interval_start, start), min(interval_end, end)))
                if interval_end >= zone_start and interval_start <= zone_end:
                    zone_covered.append((max(interval_start, zone_start),
                                         min(interval_end, zone_end)))
            # A fragment counts only if it covers the whole anchor zone: that is
            # the coverage an anchored crossing read would have needed here.
            if _overlap_nt(intervals, zone_start, zone_end) == criteria.min_anchor_nt:
                zone_fragments.add(observation["qname"])
        length = end - start + 1
        covered_nt = union_length(covered)
        statistics[side] = {
            "ref_start": start, "ref_end": end, "length_nt": length,
            "covered_nt": covered_nt,
            "covered_frac": round(covered_nt / length, 6),
            "anchor_zone_ref_start": zone_start, "anchor_zone_ref_end": zone_end,
            "anchor_zone_covered_nt": union_length(zone_covered),
            "anchor_zone_fragments": len(zone_fragments),
        }
    return statistics


def _mate_role(flag: int) -> str | None:
    """"first" or "second" for a paired record that says which mate it is.

    None for an unpaired record (0x1 clear) and for one that sets neither or
    both of 0x40 and 0x80 — in the SAM specification that is a segment of a
    template whose position is unknown, not a mate of a pair.
    """
    if not flag & 0x1:
        return None
    first, second = bool(flag & 0x40), bool(flag & 0x80)
    if first == second:
        return None
    return "first" if first else "second"


def _mate_bridging_fragments(observations: list[dict], criteria: Criteria,
                             crossing_or_near: set[str]) -> set[str]:
    """Pairs whose two mates sit in opposite flanks with no read crossing the junction.

    A bridge requires two *distinct* records of one fragment, one the first mate
    and one the second, each paired, each anchored in a different flank. Two
    alignments that merely share a QNAME are not a bridge: without the pairing
    flags they may be one read reported twice, and both mates flagged alike are
    not two mates.

    Counted and reported on its own: a bridged pair constrains the distance
    between the two regions on one fragment, and says nothing about where, or
    whether, that fragment is spliced.
    """
    by_qname: dict[str, list[tuple[int, str, set[str]]]] = {}
    for observation in observations:
        if observation["disqualified_by"] is not None:
            continue
        role = _mate_role(observation["flag"])
        if role is None:
            continue
        sides = {
            side for side, flank in FLANKS.items()
            if _overlap_nt(observation["ref_aligned_intervals"],
                           flank["ref_start"], flank["ref_end"]) >= criteria.min_anchor_nt
        }
        by_qname.setdefault(observation["qname"], []).append(
            (observation["record_index"], role, sides))

    bridged: set[str] = set()
    for qname, entries in by_qname.items():
        if qname in crossing_or_near:
            continue
        firsts = [entry for entry in entries if entry[1] == "first"]
        seconds = [entry for entry in entries if entry[1] == "second"]
        for index_a, _, sides_a in firsts:
            for index_b, _, sides_b in seconds:
                if index_a == index_b:
                    continue
                if (("upstream" in sides_a and "downstream" in sides_b)
                        or ("downstream" in sides_a and "upstream" in sides_b)):
                    bridged.add(qname)
    return bridged


def count_library(records: list, criteria: Criteria) -> dict:
    """Count one library's evidence. Pure: takes parsed records, returns counts."""
    specs = (TARGET_JUNCTION, *CONTROL_JUNCTIONS)
    observations: list[dict] = []
    off_target = 0
    unmapped = 0
    for index, record in enumerate(records):
        if record.is_unmapped:
            unmapped += 1
            continue
        if record.rname != REFERENCE["sequence_name"]:
            off_target += 1
            continue
        observations.append(observe_record(record, index, specs, criteria))

    def categories(junction_name: str) -> dict[str, dict[str, set | int]]:
        buckets: dict[str, dict] = {}
        for observation in observations:
            for junction in observation["junctions"]:
                if junction["junction_name"] != junction_name:
                    continue
                bucket = buckets.setdefault(junction["category"], {"reads": 0, "fragments": set()})
                bucket["reads"] += 1
                bucket["fragments"].add(observation["qname"])
        return buckets

    target = categories(TARGET_JUNCTION.name)

    def count(name: str, key: str) -> int:
        bucket = target.get(name)
        if bucket is None:
            return 0
        return bucket["reads"] if key == "reads" else len(bucket["fragments"])

    crossing_or_near = {
        observation["qname"] for observation in observations
        for junction in observation["junctions"]
        if junction["junction_name"] == TARGET_JUNCTION.name
    }

    disqualified: dict[str, dict] = {}
    for observation in observations:
        reason = observation["disqualified_by"]
        if reason is None:
            continue
        kind = reason.split("_")[0] if reason.startswith("ambiguous") else reason
        bucket = disqualified.setdefault(kind, {"reads": 0, "fragments": set()})
        bucket["reads"] += 1
        bucket["fragments"].add(observation["qname"])

    flanks = _flank_statistics(observations, criteria)
    bridged = _mate_bridging_fragments(observations, criteria, crossing_or_near)

    controls = {}
    for spec in CONTROL_JUNCTIONS:
        buckets = categories(spec.name)
        support = buckets.get("support")
        controls[spec.name] = {
            "support_reads": support["reads"] if support else 0,
            "support_fragments": len(support["fragments"]) if support else 0,
            "annotated_intron": spec.annotated_intron,
        }

    return {
        "n_records": len(records),
        "n_records_unmapped": unmapped,
        "n_records_off_target": off_target,
        "n_records_on_target_sequence": len(observations),
        "n_fragments_on_target_sequence": len({o["qname"] for o in observations}),
        "support_reads": count("support", "reads"),
        "support_fragments": count("support", "fragments"),
        "short_anchor_reads": count("short_anchor", "reads"),
        "short_anchor_fragments": count("short_anchor", "fragments"),
        "disqualified_at_junction_reads": count("disqualified", "reads"),
        "disqualified_at_junction_fragments": count("disqualified", "fragments"),
        "donor_only_fragments": count("donor_only", "fragments"),
        "acceptor_only_fragments": count("acceptor_only", "fragments"),
        "neighbour_fragments": count("neighbour", "fragments"),
        "ambiguous_reads": disqualified.get("ambiguous", {}).get("reads", 0),
        "ambiguous_fragments": len(disqualified.get("ambiguous", {}).get("fragments", set())),
        "duplicate_reads": disqualified.get("flagged_duplicate", {}).get("reads", 0),
        "duplicate_fragments": len(
            disqualified.get("flagged_duplicate", {}).get("fragments", set())),
        "secondary_reads": disqualified.get("secondary_alignment", {}).get("reads", 0),
        "supplementary_reads": disqualified.get("supplementary_alignment", {}).get("reads", 0),
        "mate_bridge_fragments": len(bridged),
        "mate_bridge_fragment_names": sorted(bridged),
        "flanks": flanks,
        "controls": controls,
        "observations": observations,
    }


def classify_library(counts: dict, criteria: Criteria) -> dict:
    """Turn one library's counts into a verdict, naming every requirement that failed."""
    failed: list[str] = []
    for side, flank in counts["flanks"].items():
        if flank["anchor_zone_fragments"] < criteria.min_anchor_zone_fragments:
            failed.append(
                f"{side}_anchor_zone_fragments={flank['anchor_zone_fragments']}"
                f"<{criteria.min_anchor_zone_fragments} over "
                f"{flank['anchor_zone_ref_start']}-{flank['anchor_zone_ref_end']} "
                f"({flank['anchor_zone_covered_nt']}/{criteria.min_anchor_nt} nt covered)")
    control_support = sum(
        control["support_fragments"] for control in counts["controls"].values())
    if criteria.require_control_junction_support and control_support == 0:
        failed.append("no_control_junction_support: no annotated junction of this chain is "
                      "supported in this library, so splicing is not demonstrably detectable")
    informative = not failed

    support = counts["support_fragments"]
    if support >= criteria.min_support_fragments:
        verdict = "JUNCTION_SUPPORTED"
    elif support > 0:
        verdict = "SUPPORT_BELOW_DECLARED_THRESHOLD"
    elif informative:
        verdict = "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    else:
        verdict = "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    return {
        "verdict": verdict,
        "informative_coverage": informative,
        "control_junction_support_fragments": control_support,
        "failed_requirements": "; ".join(failed),
    }


# --------------------------------------------------------------------------
# Output writing. Nothing here classifies.
# --------------------------------------------------------------------------

PER_LIBRARY_COLUMNS = [
    "library_id", "origin_class", "documentary_evidence", "provenance",
    "sam_path", "sam_sha256", "aligner_name", "aligner_version",
    "n_records", "n_records_unmapped", "n_records_off_target",
    "n_records_on_target_sequence", "n_fragments_on_target_sequence",
    "support_reads", "support_fragments",
    "short_anchor_reads", "short_anchor_fragments",
    "disqualified_at_junction_reads", "disqualified_at_junction_fragments",
    "donor_only_fragments", "acceptor_only_fragments", "neighbour_fragments",
    "ambiguous_reads", "ambiguous_fragments",
    "duplicate_reads", "duplicate_fragments",
    "secondary_reads", "supplementary_reads",
    "mate_bridge_fragments",
    "upstream_flank_covered_nt", "upstream_flank_length_nt", "upstream_flank_covered_frac",
    "upstream_anchor_zone_ref_start", "upstream_anchor_zone_ref_end",
    "upstream_anchor_zone_covered_nt", "upstream_anchor_zone_fragments",
    "downstream_flank_covered_nt", "downstream_flank_length_nt", "downstream_flank_covered_frac",
    "downstream_anchor_zone_ref_start", "downstream_anchor_zone_ref_end",
    "downstream_anchor_zone_covered_nt", "downstream_anchor_zone_fragments",
    "control_cds_456_457_support_fragments", "control_cds_870_871_support_fragments",
    "control_junction_support_fragments",
    "informative_coverage", "verdict", "failed_requirements",
]

OBSERVATION_COLUMNS = [
    "library_id", "junction_name", "category", "boundary_match", "counted_as_support",
    "qname", "record_index", "flag", "strand", "mapq", "nh", "record_class", "is_duplicate",
    "disqualified_by", "ref_name", "ref_start", "ref_end", "cigar",
    "intron_ref_start", "intron_ref_end", "intron_len_nt",
    "delta_intron_start_nt", "delta_intron_end_nt",
    "anchor_upstream_aligned_nt", "anchor_downstream_aligned_nt",
    "n_cigar_junctions",
]

MATE_BRIDGE_COLUMNS = ["library_id", "qname", "note"]


def per_library_row(entry: dict, header: dict, counts: dict, verdict: dict) -> dict:
    row = {
        "library_id": entry["library_id"],
        "origin_class": entry["origin_class"],
        "documentary_evidence": entry.get("documentary_evidence", ""),
        "provenance": entry["provenance"],
        "sam_path": entry["sam"],
        "sam_sha256": entry["_observed_sha256"],
        "aligner_name": header["aligner_name"],
        "aligner_version": header["aligner_version"],
    }
    for key in ("n_records", "n_records_unmapped", "n_records_off_target",
                "n_records_on_target_sequence", "n_fragments_on_target_sequence",
                "support_reads", "support_fragments",
                "short_anchor_reads", "short_anchor_fragments",
                "disqualified_at_junction_reads", "disqualified_at_junction_fragments",
                "donor_only_fragments", "acceptor_only_fragments", "neighbour_fragments",
                "ambiguous_reads", "ambiguous_fragments",
                "duplicate_reads", "duplicate_fragments",
                "secondary_reads", "supplementary_reads", "mate_bridge_fragments"):
        row[key] = counts[key]
    for side in ("upstream", "downstream"):
        flank = counts["flanks"][side]
        row[f"{side}_flank_covered_nt"] = flank["covered_nt"]
        row[f"{side}_flank_length_nt"] = flank["length_nt"]
        row[f"{side}_flank_covered_frac"] = flank["covered_frac"]
        row[f"{side}_anchor_zone_ref_start"] = flank["anchor_zone_ref_start"]
        row[f"{side}_anchor_zone_ref_end"] = flank["anchor_zone_ref_end"]
        row[f"{side}_anchor_zone_covered_nt"] = flank["anchor_zone_covered_nt"]
        row[f"{side}_anchor_zone_fragments"] = flank["anchor_zone_fragments"]
    for spec in CONTROL_JUNCTIONS:
        row[f"control_{spec.name}_support_fragments"] = \
            counts["controls"][spec.name]["support_fragments"]
    row["control_junction_support_fragments"] = verdict["control_junction_support_fragments"]
    row["informative_coverage"] = verdict["informative_coverage"]
    row["verdict"] = verdict["verdict"]
    row["failed_requirements"] = verdict["failed_requirements"]
    return row


def observation_rows(library_id: str, counts: dict) -> list[dict]:
    """One row per junction observation that bears on a declared junction."""
    rows: list[dict] = []
    for observation in counts["observations"]:
        for junction in observation["junctions"]:
            rows.append({
                "library_id": library_id,
                "ref_name": REFERENCE["sequence_name"],
                **{key: observation[key] for key in (
                    "qname", "record_index", "flag", "strand", "mapq", "nh", "record_class",
                    "is_duplicate", "disqualified_by", "ref_start", "ref_end", "cigar",
                    "n_cigar_junctions")},
                **junction,
            })
    rows.sort(key=lambda row: (row["junction_name"], row["category"], row["qname"],
                               row["record_index"]))
    return rows


def _git_state(root: Path) -> dict:
    """Commit and working-tree state, or a refusal.

    `_git` as used elsewhere in this package returns an empty string when the
    git call fails, which has already produced a manifest with an empty commit
    field in a cross-OS worktree. Here a failed git call refuses the run
    instead, because a success manifest without a commit is not provenance.
    """
    def run(*args: str) -> str:
        done = subprocess.run(
            ["git", "-c", "safe.directory=*", *args], cwd=root,
            capture_output=True, text=True)
        if done.returncode != 0:
            raise VerificationError(
                f"git {' '.join(args)} failed in {root}: {done.stderr.strip() or 'no stderr'}; "
                f"the manifest cannot record the commit and checkout state")
        return done.stdout
    commit = run("rev-parse", "HEAD").strip()
    if len(commit) != 40:
        raise VerificationError(f"git rev-parse HEAD returned {commit!r}, not a commit sha")
    status = run("status", "--porcelain")
    return {
        "commit": commit,
        "branch": run("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "status_porcelain": status.rstrip("\n"),
        "clean": status.strip() == "",
    }


def run(root: Path, panel_path: Path, out_dir: Path, criteria: Criteria) -> dict:
    """Read, classify, write, validate, then emit the success manifest."""
    git_state = _git_state(root)
    panel = load_panel(panel_path, root)

    library_rows: list[dict] = []
    all_observations: list[dict] = []
    bridge_rows: list[dict] = []
    headers: dict[str, dict] = {}
    for entry in panel["libraries"]:
        header, records = read_library_sam(entry["_resolved_path"], panel["reference"])
        counts = count_library(records, criteria)
        verdict = classify_library(counts, criteria)
        headers[entry["library_id"]] = header
        library_rows.append(per_library_row(entry, header, counts, verdict))
        all_observations.extend(observation_rows(entry["library_id"], counts))
        bridge_rows.extend(
            {"library_id": entry["library_id"], "qname": qname,
             "note": "both mates in the two flanks, no read crossing the junction"}
            for qname in counts["mate_bridge_fragment_names"])
        print(f"[{entry['library_id']}] {counts['n_records_on_target_sequence']} records on "
              f"{REFERENCE['sequence_name']}, support_fragments="
              f"{counts['support_fragments']}, verdict={verdict['verdict']}", file=sys.stderr)

    outputs = {
        "per_library.tsv": (PER_LIBRARY_COLUMNS, library_rows),
        "junction_observations.tsv": (OBSERVATION_COLUMNS, all_observations),
        "mate_bridged_fragments.tsv": (MATE_BRIDGE_COLUMNS, bridge_rows),
    }
    for name, (columns, rows) in outputs.items():
        write_tsv(out_dir / name, columns, rows)
        print(f"[write] {name}: {len(rows)} rows", file=sys.stderr)

    # Validated before the success manifest is emitted: every table is read back
    # and its row count confirmed against what was written.
    validation = {}
    for name, (columns, rows) in outputs.items():
        lines = (out_dir / name).read_text(encoding="utf-8").splitlines()
        if lines[0].split("\t") != columns:
            raise VerificationError(f"{name}: header read back does not match the declared columns")
        if len(lines) - 1 != len(rows):
            raise VerificationError(
                f"{name}: wrote {len(rows)} rows, read back {len(lines) - 1}")
        validation[name] = {"rows": len(rows), "columns": len(columns)}

    manifest = {
        "question": "does RNA-seq support the 642/643 junction of the published "
                    "Dmai-dsRNase-3 CDS, between OZ319704.1 122,007,348 and 122,012,479",
        "indexing_convention": INDEXING_CONVENTION,
        "reference": {**REFERENCE, **panel["reference"]},
        "target_junction": asdict(TARGET_JUNCTION),
        "control_junctions": [asdict(spec) for spec in CONTROL_JUNCTIONS],
        "flanks": FLANKS,
        "anchor_zones": {
            side: dict(zip(("ref_start", "ref_end"), anchor_zone(side, criteria)))
            for side in FLANKS
        },
        "criteria": asdict(criteria),
        "verdict_vocabulary": list(VERDICTS),
        "alignment_recipe": ALIGNMENT_RECIPE,
        "library_provenance_note": LIBRARY_PROVENANCE_NOTE,
        "git": git_state,
        "python": sys.version.split()[0],
        "panel": {
            "path": panel_path.relative_to(root).as_posix()
                    if panel_path.is_relative_to(root) else str(panel_path),
            "sha256": sha256_file(panel_path),
        },
        "libraries": [
            {
                "library_id": entry["library_id"],
                "origin_class": entry["origin_class"],
                "provenance": entry["provenance"],
                "documentary_evidence": entry.get("documentary_evidence"),
                "sam": entry["sam"],
                "declared_sha256": entry["sha256"],
                "observed_sha256": entry["_observed_sha256"],
                "aligner": headers[entry["library_id"]],
            }
            for entry in panel["libraries"]
        ],
        "verdicts": {row["library_id"]: row["verdict"] for row in library_rows},
        "validation": validation,
        "outputs": {name: sha256_file(out_dir / name) for name in outputs},
        "limitations": [
            "A fragment crossing 642/643 supports that junction only. Assigning the whole "
            "1,236 nt published CDS to a single molecule needs evidence linking this "
            "junction to the other blocks of the chain, which this command does not "
            "produce.",
            "Counting reads coordinates that an aligner already assigned: a crossing read "
            "the aligner declined to splice is invisible here, so the counts are a lower "
            "bound on crossing reads in the library. Measured on the declared recipe, "
            "that applies below a 20 nt anchor, where hisat2 soft-clips the short side "
            "or aligns the read unspliced with mismatches; such a pair is reported in "
            "the mate-bridge column instead, if its mate lies in the other flank.",
            "MAPQ scales are aligner-specific. Where the aligner emits no NH tag, "
            "uniqueness rests on min_mapq alone.",
            "Flagged duplicates are reported but not re-derived; the duplicate call is the "
            "one the declared SAM carries.",
            "A library's origin_class is a declaration checked for internal consistency, "
            "not an attribution: no run of this command establishes which library "
            "assembled the published contig.",
            "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE is conditional on the library and the "
            "method, never a statement about the transcript: it says that in this "
            "library, under these criteria and this aligner's junction calls, no "
            "qualifying fragment crossed, while both anchor zones carried the coverage "
            "an anchored crossing read would have needed. A library sampling another "
            "tissue, stage or depth, or an aligner with different junction behaviour, "
            "can still show the junction.",
        ],
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (out_dir / "manifest.json").write_text(manifest_text, encoding="utf-8", newline="\n")
    print(f"[write] manifest.json: sha256 {sha256_text(manifest_text)}", file=sys.stderr)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="RNA-seq support for the 642/643 junction of the published dsRNase-3 CDS")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--panel", required=True,
                        help="JSON panel declaring the reference and one SAM per library")
    parser.add_argument("--out-subdir", required=True,
                        help=f"output directory for this run, under {OUTPUT_ROOT}/")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out_subdir = Path(args.out_subdir)
    if out_subdir.is_absolute():
        raise VerificationError("--out-subdir must be relative to the repository root")
    if OUTPUT_ROOT not in out_subdir.as_posix():
        raise VerificationError(f"--out-subdir must sit under {OUTPUT_ROOT}/: {out_subdir}")
    if out_subdir.as_posix().rstrip("/") == OUTPUT_ROOT:
        raise VerificationError(
            f"--out-subdir must name a directory of its own under {OUTPUT_ROOT}/")

    panel_path = Path(args.panel)
    if not panel_path.is_absolute():
        panel_path = root / panel_path
    if not panel_path.is_file():
        raise VerificationError(f"panel not found: {panel_path}")

    # The destination is claimed before anything is read, so a refused run
    # writes nothing and cannot overwrite an earlier execution.
    with reserve_output_dir(root / out_subdir) as reservation:
        print(f"[output] {reservation.out_dir} (reserved)", file=sys.stderr)
        run(root, panel_path.resolve(), reservation.out_dir, Criteria())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VerificationError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(2)
