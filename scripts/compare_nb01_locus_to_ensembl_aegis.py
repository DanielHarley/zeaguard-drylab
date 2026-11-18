"""Compare the three NB01 dsRNase loci (loci.tsv) against the Ensembl AEGIS
Genebuild gene models for GCA_975739785.1 (ihDalMaid1.1).

Verification-round script: reads the already-published locus mapping output
and an already-downloaded, hash-verified GFF3, and reports how the two
compare. It does not re-run blastn, does not touch loci.tsv or any other
historical artefact, and writes its own output directory.

Each candidate transcript is compared to the NB01 exon blocks on its own: no
segment is removed from a shared pool, so two isoforms that share an exon are
each scored on their own merits. The within-transcript correspondence is
ordered and one-to-one (it cannot match NB01 block 3 to CDS segment 5 and
then NB01 block 4 to CDS segment 2, because exons do not reorder), found by
weighted sequence alignment: maximise matched pairs, then minimise total
boundary distance; every tied optimum is kept.

Two things this script reports SEPARATELY, because they answer different
questions and can disagree:
  - gene support: does exactly one gene's transcript(s) account for every
    NB01 block? This is what "DETERMINED" means.
  - structural match: does the winning transcript's OWN CDS structure line
    up with the NB01 blocks one-to-one, or does it have CDS segments the
    NB01 tiling skipped over? A transcript can fully account for every NB01
    block (gene support stands) while still carrying a CDS segment with no
    NB01 counterpart (structural match is only PARTIAL).
Every locus x tolerance-mode combination gets an explicit summary row, even
when no gene overlaps the locus at all or every candidate scores zero pairs;
nothing is reported by omission.

The 20 nt match tolerance is EXPLORATORY, chosen after looking at this run's
own distances (see MATCH_TOLERANCE_EXPLORATORY_NT below); it has no
pre-registration to appeal to, and the manifest says so plainly. The exact
(0 nt) mode is not a tolerance choice at all -- it is coordinate identity,
which has no free parameter and so nothing to register. Every comparison in
this script runs under both modes and both are reported side by side.

Usage (from the repository root):
    py scripts/compare_nb01_locus_to_ensembl_aegis.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCI_TSV = ROOT / "results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/loci.tsv"
GFF3_GZ = ROOT / "data/external/nb01_locus_mapping/GCA_975739785.1_ensembl_2026_02_genes.gff3.gz"
OUT_DIR = ROOT / "results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/ensembl_aegis_comparison_v3"

GFF3_SOURCE_URL = "https://ftp.ebi.ac.uk/pub/ensemblorganisms/GCA/975/739/785/1/ensembl/2026_02/geneset/genes.gff3.gz"
ANNOTATION_VERSION = "Ensembl Genebuild geneset 2026_02 for GCA_975739785.1 (ihDalMaid1.1)"

# Declared inputs, verified by hash before anything runs (fail-closed, not
# just a post-hoc report). Both were computed and recorded in the first round
# of this comparison; loci.tsv's also matches the sha256 recorded in the NB01
# locus mapping run record itself.
DECLARED_INPUTS = {
    "loci_tsv": {
        "path": LOCI_TSV,
        "sha256": "57b0d68ce3d0460c832f15ab24bd8ab1214dd90e3dc63807140d62ed6ff172e4",
    },
    "gff3_gz": {
        "path": GFF3_GZ,
        "sha256": "2606dd4fbb71b9555c643656656bb2f2aad82a072422236df57eaed483cb411d",
        "md5_published_in_geneset_md5sum_txt": "f14acda9ad871e8b07fdfdc55f076846",
    },
}

# Coordinate equality, not a slack: two genomic intervals (a_start, a_end) and
# (b_start, b_end) are "exact" iff a_start == b_start AND a_end == b_end,
# under the shared 1-based inclusive coordinate convention already verified
# between loci.tsv and this GFF3 (see chromosome_1_correspondence in the
# manifest). There is no free parameter here, so "pre-registered" is not a
# meaningful label for it one way or the other -- there was nothing to decide
# in advance.
MATCH_TOLERANCE_EXACT_NT = 0

# Chosen in the first revision of this script AFTER observing this run's own
# data, not pre-registered: every segment that was unambiguously the same
# exon (dsRNase-1 and dsRNase-2, one gene per locus, no competing model)
# differed from its NB01 block by at most 6 nt combined; the one block with
# no real counterpart (dsRNase-3, block 4) differed by 71 nt. 20 nt separates
# the two cleanly while staying well above ADR 0009's declared +/-10 nt
# per-edge splice ambiguity window. Kept only as an exploratory, clearly
# labelled sensitivity lens alongside the exact comparison, never silently
# substituted for it. No ADR or other record declares this threshold ahead of
# the analysis; MATCH_TOLERANCE_EXACT_NT above is the only criterion in this
# script for which "pre-registered" could even apply, and it does not need
# to, being parameter-free.
MATCH_TOLERANCE_EXPLORATORY_NT = 20

TOLERANCE_MODES = {
    "exact": MATCH_TOLERANCE_EXACT_NT,
    "exploratory_20nt": MATCH_TOLERANCE_EXPLORATORY_NT,
}


class InputVerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs() -> None:
    """Fail closed before any comparison runs if a declared input is missing
    or its sha256 disagrees with what was recorded when this script was
    written. A hash mismatch means the input changed under us; running
    against it anyway would silently invalidate the whole comparison."""
    for label, declared in DECLARED_INPUTS.items():
        path: Path = declared["path"]
        if not path.is_file():
            raise InputVerificationError(f"declared input is missing: {label} -> {path}")
        observed = sha256_file(path)
        if observed != declared["sha256"]:
            raise InputVerificationError(
                f"{label} sha256 mismatch: declared {declared['sha256']}, observed {observed} ({path})"
            )


def load_loci(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        row["locus_start"] = int(row["locus_start"])
        row["locus_end"] = int(row["locus_end"])
        row["n_exons_inferred"] = int(row["n_exons_inferred"])
        row["gff3_strand"] = {"plus": "+", "minus": "-"}[row["strand"]]
        row["exon_blocks_subject"] = [
            tuple(int(x) for x in block.split("-"))
            for block in row["exon_blocks_subject"].split(";")
        ]
    return rows


class Gff3Index:
    """Chromosome-1 gene / mRNA / CDS features, keyed for overlap lookup."""

    def __init__(self) -> None:
        self.region_alias: str | None = None
        self.genes: dict[str, dict] = {}
        self.transcripts: dict[str, dict] = {}
        self.cds: dict[str, list[tuple[int, int]]] = {}

    @staticmethod
    def _attrs(field: str) -> dict[str, str]:
        out = {}
        for part in field.strip().split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    def load(self, gff3_gz: Path, seqid: str) -> None:
        with gzip.open(gff3_gz, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) != 9:
                    continue
                if cols[0] != seqid:
                    continue
                kind = cols[2]
                start, end, strand = int(cols[3]), int(cols[4]), cols[6]
                attrs = self._attrs(cols[8])
                if kind == "region":
                    self.region_alias = attrs.get("Alias")
                elif kind == "gene":
                    gene_id = attrs["gene_id"]
                    self.genes[gene_id] = {
                        "gene_id": gene_id,
                        "name": attrs.get("Name", ""),
                        "biotype": attrs.get("biotype", ""),
                        "start": start,
                        "end": end,
                        "strand": strand,
                    }
                elif kind == "mRNA":
                    transcript_id = attrs["transcript_id"]
                    gene_id = attrs["Parent"].split(":", 1)[1]
                    self.transcripts[transcript_id] = {
                        "transcript_id": transcript_id,
                        "gene_id": gene_id,
                        "start": start,
                        "end": end,
                        "strand": strand,
                        "is_canonical": attrs.get("tag") == "Ensembl_canonical",
                    }
                elif kind == "CDS":
                    transcript_id = attrs["Parent"].split(":", 1)[1]
                    self.cds.setdefault(transcript_id, []).append((start, end))

    def finalize(self) -> None:
        for segs in self.cds.values():
            segs.sort()

    def genes_overlapping(self, start: int, end: int, strand: str) -> list[dict]:
        return [
            g for g in self.genes.values()
            if g["strand"] == strand and g["start"] <= end and g["end"] >= start
        ]

    def transcripts_of(self, gene_id: str) -> list[dict]:
        return [t for t in self.transcripts.values() if t["gene_id"] == gene_id]


def transcription_sort(segments: list[tuple[int, int]], strand: str) -> list[tuple[int, int]]:
    """Order segments the way the ribosome would meet them: ascending genomic
    position on the plus strand, descending on the minus strand, where the
    first segment in reading order has the highest genomic coordinates."""
    return sorted(segments, key=lambda s: s[0], reverse=(strand == "-"))


def boundary_cost(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int, int]:
    """(combined cost, start diff a-b, end diff a-b). Symmetric in strand:
    swapping which end of a segment is "first" swaps both operands the same
    way, so the combined cost of a genomic start/end pair is unaffected by
    strand; only the reading ORDER used to enforce colinearity depends on it.
    Cost 0 is exactly coordinate equality (a == b on both boundaries)."""
    d_start, d_end = a[0] - b[0], a[1] - b[1]
    return abs(d_start) + abs(d_end), d_start, d_end


def align_transcript(
    nb01_sorted: list[tuple[int, int]],
    cds_sorted: list[tuple[int, int]],
    max_tol: int,
) -> tuple[tuple[int, int], list[list[tuple[int, int]]]]:
    """Ordered (colinear), one-to-one, partial matching between two sequences
    already in reading order. Maximises the number of matched pairs, then
    minimises their total boundary cost. Returns ((n_matched, total_cost),
    [alignment, ...]) where each alignment is a list of 0-based (nb01_index,
    cds_index) pairs; every alignment achieving the optimum is returned, not
    just one, so a genuine tie survives.

    This is ordinary weighted sequence alignment (Needleman-Wunsch shape):
    dp[i][j] is the best (count, cost) using the first i NB01 blocks and the
    first j CDS segments, built from "skip a block", "skip a segment", or
    "match the two" when their cost is within tolerance.
    """
    n, m = len(nb01_sorted), len(cds_sorted)
    dp: list[list[tuple[int, int]]] = [[(0, 0)] * (m + 1) for _ in range(n + 1)]
    choices: list[list[list[tuple]]] = [[[] for _ in range(m + 1)] for _ in range(n + 1)]

    def rank(value: tuple[int, int]) -> tuple[int, int]:
        return value[0], -value[1]

    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best_rank = None
            best_value = (0, 0)
            moves: list[tuple] = []

            def consider(value: tuple[int, int], move: tuple) -> None:
                nonlocal best_rank, best_value, moves
                r = rank(value)
                if best_rank is None or r > best_rank:
                    best_rank, best_value, moves = r, value, [move]
                elif r == best_rank:
                    moves.append(move)

            if i > 0:
                consider(dp[i - 1][j], ("skip_nb01",))
            if j > 0:
                consider(dp[i][j - 1], ("skip_cds",))
            if i > 0 and j > 0:
                cost, _, _ = boundary_cost(nb01_sorted[i - 1], cds_sorted[j - 1])
                if cost <= max_tol:
                    prev = dp[i - 1][j - 1]
                    consider((prev[0] + 1, prev[1] + cost), ("match",))
            dp[i][j] = best_value
            choices[i][j] = moves

    # Reconstruct every optimal alignment bottom-up, memoized per (i, j) cell.
    # A naive recursive backtrack re-derives the same destination many times
    # over equivalent orderings of "skip" moves -- with n = m = 12 and no
    # match anywhere, that lattice has C(24, 12) ~= 2.7M monotonic paths, all
    # collapsing to the same single empty alignment, and took ~1s to walk.
    # Filling reach[i][j] once per cell, as a set of already-deduplicated
    # pairings reachable there, makes each cell's work O(1) set unions
    # instead of re-exploring its whole upstream lattice.
    reach: list[list[set[tuple[tuple[int, int], ...]]]] = [
        [set() for _ in range(m + 1)] for _ in range(n + 1)
    ]
    reach[0][0] = {()}
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            acc: set[tuple[tuple[int, int], ...]] = set()
            for move in choices[i][j]:
                if move[0] == "skip_nb01":
                    acc |= reach[i - 1][j]
                elif move[0] == "skip_cds":
                    acc |= reach[i][j - 1]
                else:
                    acc |= {pairs + ((i - 1, j - 1),) for pairs in reach[i - 1][j - 1]}
            reach[i][j] = acc

    return dp[n][m], [list(a) for a in sorted(reach[n][m])]


def structural_match(n_matched: int, n_nb01: int, n_cds: int) -> tuple[str, str]:
    """Whether THIS transcript's own CDS structure lines up with the NB01
    blocks one-to-one -- independent of whether this transcript is the one
    carrying gene-level support for the locus. A transcript can fully account
    for every NB01 block (so gene support stands) while still having CDS
    segments the NB01 tiling has nothing to say about (PARTIAL_SKIPPED_SEGMENT)."""
    if n_matched == 0:
        return "NO_PAIRS", "no NB01 block matches any CDS segment of this transcript within tolerance"
    if n_matched < n_nb01:
        return ("PARTIAL_UNMATCHED_BLOCKS",
                f"only {n_matched}/{n_nb01} NB01 blocks match a CDS segment of this transcript")
    if n_matched < n_cds:
        return ("PARTIAL_SKIPPED_SEGMENT",
                f"all {n_nb01} NB01 blocks are matched, but {n_cds - n_matched} CDS segment(s) "
                f"of this transcript have no NB01 counterpart")
    return "FULL", f"all {n_nb01} NB01 blocks and all {n_cds} CDS segments are paired one-to-one"


def compare_locus_at_tolerance(locus: dict, index: Gff3Index, tolerance_mode: str, max_tol: int
                                ) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Returns (transcript_rows, pair_rows, junction_rows, locus_summary_row).
    locus_summary_row is ALWAYS produced, even with zero candidate genes or
    zero matched pairs anywhere -- nothing about this locus x mode is left to
    be inferred from an absence of rows elsewhere."""
    strand = locus["gff3_strand"]
    nb01_sorted = transcription_sort(locus["exon_blocks_subject"], strand)
    n_nb01_blocks = len(nb01_sorted)
    genes = index.genes_overlapping(locus["locus_start"], locus["locus_end"], strand)

    transcript_rows: list[dict] = []
    pair_rows: list[dict] = []
    junction_rows: list[dict] = []
    per_transcript_best: list[tuple[str, str, tuple[int, int]]] = []  # (gene_id, transcript_id, value)

    for gene in genes:
        for transcript in index.transcripts_of(gene["gene_id"]):
            cds_sorted = transcription_sort(index.cds.get(transcript["transcript_id"], []), strand)
            n_cds_segments = len(cds_sorted)
            value, alignments = align_transcript(nb01_sorted, cds_sorted, max_tol)
            per_transcript_best.append((gene["gene_id"], transcript["transcript_id"], value))
            struct_status, struct_reason = structural_match(value[0], n_nb01_blocks, n_cds_segments)

            for alignment_id, pairs in enumerate(alignments):
                matched_nb01 = {p[0] for p in pairs}
                matched_cds = {p[1] for p in pairs}
                transcript_rows.append({
                    "target_id": locus["target_id"],
                    "tolerance_mode": tolerance_mode,
                    "gene_id": gene["gene_id"],
                    "gene_name": gene["name"],
                    "transcript_id": transcript["transcript_id"],
                    "is_canonical": transcript["is_canonical"],
                    "strand": transcript["strand"],
                    "n_cds_segments": n_cds_segments,
                    "n_nb01_blocks": n_nb01_blocks,
                    "alignment_id": alignment_id,
                    "n_tied_optimal_alignments": len(alignments),
                    "n_matched_pairs": value[0],
                    "total_boundary_cost_nt": value[1],
                    "unmatched_nb01_block_ranks": ",".join(
                        str(k + 1) for k in range(n_nb01_blocks) if k not in matched_nb01
                    ),
                    "unmatched_cds_segment_ranks": ",".join(
                        str(k + 1) for k in range(n_cds_segments) if k not in matched_cds
                    ),
                    "structural_match_status": struct_status,
                    "structural_match_reason": struct_reason,
                })

                for nb01_idx, cds_idx in pairs:
                    cost, d_start, d_end = boundary_cost(nb01_sorted[nb01_idx], cds_sorted[cds_idx])
                    pair_rows.append({
                        "target_id": locus["target_id"],
                        "tolerance_mode": tolerance_mode,
                        "transcript_id": transcript["transcript_id"],
                        "alignment_id": alignment_id,
                        "nb01_rank": nb01_idx + 1,
                        "cds_rank": cds_idx + 1,
                        "nb01_start": nb01_sorted[nb01_idx][0],
                        "nb01_end": nb01_sorted[nb01_idx][1],
                        "cds_start": cds_sorted[cds_idx][0],
                        "cds_end": cds_sorted[cds_idx][1],
                        "start_diff_nt": d_start,
                        "end_diff_nt": d_end,
                        "cost_nt": cost,
                    })

                pair_by_nb01 = dict(pairs)
                for i in range(n_nb01_blocks - 1):
                    left_cds, right_cds = pair_by_nb01.get(i), pair_by_nb01.get(i + 1)
                    lo_a, hi_a = sorted((nb01_sorted[i], nb01_sorted[i + 1]))
                    nb01_intron_start, nb01_intron_end = lo_a[1] + 1, hi_a[0] - 1
                    row = {
                        "target_id": locus["target_id"],
                        "tolerance_mode": tolerance_mode,
                        "transcript_id": transcript["transcript_id"],
                        "alignment_id": alignment_id,
                        "junction_index": i + 1,
                        "nb01_block_ranks": f"{i + 1}-{i + 2}",
                        "nb01_intron_start": nb01_intron_start,
                        "nb01_intron_end": nb01_intron_end,
                        "nb01_intron_size_nt": nb01_intron_end - nb01_intron_start + 1,
                    }
                    if left_cds is None or right_cds is None:
                        row.update(
                            gff3_cds_ranks="NA", gff3_intron_start="NA", gff3_intron_end="NA",
                            gff3_intron_size_nt="NA", intron_start_diff_nt="NA",
                            intron_end_diff_nt="NA", intron_size_diff_nt="NA",
                            comparable=False, status="NOT_COMPARABLE_UNMATCHED_BLOCK",
                            note=f"NB01 block {i + 1 if left_cds is None else i + 2} has no CDS segment within tolerance",
                        )
                    else:
                        lo_b, hi_b = sorted((cds_sorted[left_cds], cds_sorted[right_cds]))
                        gff3_intron_start, gff3_intron_end = lo_b[1] + 1, hi_b[0] - 1
                        skipped = abs(right_cds - left_cds) - 1
                        if skipped > 0:
                            status, comparable = "SKIPPED_CDS_SEGMENT", False
                            note = f"{skipped} CDS segment(s) of {transcript['transcript_id']} fall between ranks {left_cds + 1} and {right_cds + 1}"
                        else:
                            status, comparable, note = "MATCHED", True, ""
                        row.update(
                            gff3_cds_ranks=f"{left_cds + 1}-{right_cds + 1}",
                            gff3_intron_start=gff3_intron_start, gff3_intron_end=gff3_intron_end,
                            gff3_intron_size_nt=gff3_intron_end - gff3_intron_start + 1,
                            intron_start_diff_nt=nb01_intron_start - gff3_intron_start,
                            intron_end_diff_nt=nb01_intron_end - gff3_intron_end,
                            intron_size_diff_nt=(nb01_intron_end - nb01_intron_start + 1)
                                                 - (gff3_intron_end - gff3_intron_start + 1),
                            comparable=comparable, status=status, note=note,
                        )
                    junction_rows.append(row)

    # Gene support: count genes by whether they have AT LEAST ONE transcript
    # that explains every NB01 block, BEFORE any cost-based tiebreak. Two
    # genes that both fully explain the locus are a genuine ambiguity even if
    # one does it more cheaply -- cost never resolves that ambiguity, it only
    # picks a "closest model" to show alongside it (see below).
    full_coverage = [(g, t, v) for g, t, v in per_transcript_best if v[0] == n_nb01_blocks]
    full_coverage_genes = sorted({g for g, _, _ in full_coverage})

    if not genes:
        gene_support_status = "NO_CANDIDATE_GENE"
        gene_support_reason = "no gene overlaps this locus on the matching strand"
        best: list[tuple[str, str]] = []
    elif full_coverage_genes:
        best = [(g, t) for g, t, _ in full_coverage]
        if len(full_coverage_genes) > 1:
            gene_support_status = "INDETERMINATE_CROSS_GENE_TIE"
            per_gene = "; ".join(
                f"{g}: {sorted(t for gg, t, _ in full_coverage if gg == g)}" for g in full_coverage_genes
            )
            gene_support_reason = (f"{len(full_coverage_genes)} distinct genes each have a transcript "
                                   f"explaining all {n_nb01_blocks} blocks ({per_gene}); cost does not "
                                   f"resolve this -- see closest_model_* for the cheapest of them")
        else:
            gene_id = full_coverage_genes[0]
            transcript_ids = sorted({t for _, t in best})
            gene_support_status = "DETERMINED"
            if len(transcript_ids) > 1:
                costs = ", ".join(f"{t}@{v[1]}nt" for _, t, v in full_coverage)
                gene_support_reason = (f"all {n_nb01_blocks} blocks are explained by {len(transcript_ids)} "
                                       f"isoforms of {gene_id} ({costs}); gene-level support holds "
                                       f"regardless of which isoform is closest")
            else:
                gene_support_reason = (f"all {n_nb01_blocks} blocks match {transcript_ids[0]}'s CDS "
                                       f"segments (cost {full_coverage[0][2][1]} nt)")
    else:
        nonzero = [(g, t, v) for g, t, v in per_transcript_best if v[0] > 0]
        if not nonzero:
            gene_support_status = "NO_PAIRS_MATCHED"
            gene_support_reason = (f"{len(genes)} candidate gene(s) overlap this locus, but no transcript "
                                   f"matches any NB01 block within tolerance")
            best = []
        else:
            best_partial_value = max((v for _, _, v in nonzero), key=lambda v: (v[0], -v[1]))
            best = [(g, t) for g, t, v in nonzero if v == best_partial_value]
            gene_support_status = "INDETERMINATE_PARTIAL_COVERAGE"
            gene_support_reason = (f"the best explanation, {sorted({t for _, t in best})}, "
                                   f"covers only {best_partial_value[0]}/{n_nb01_blocks} blocks "
                                   f"(cost {best_partial_value[1]} nt)")

    for row in transcript_rows:
        row["gene_support_status"] = gene_support_status
        row["gene_support_reason"] = gene_support_reason
        row["is_tied_best_transcript"] = (row["gene_id"], row["transcript_id"]) in best

    # Structural match rollup over the preserved support set -- computed
    # independently of the gene_support label above; a DETERMINED locus can
    # still roll up to PARTIAL_SKIPPED_SEGMENT here.
    best_struct_rows = [r for r in transcript_rows if (r["gene_id"], r["transcript_id"]) in best]
    if not best_struct_rows:
        structural_rollup_status = "NOT_APPLICABLE"
        structural_rollup_reason = "no candidate transcript to evaluate"
    else:
        statuses = sorted({r["structural_match_status"] for r in best_struct_rows})
        structural_rollup_status = ",".join(statuses)
        structural_rollup_reason = "; ".join(
            sorted({f"{r['transcript_id']}: {r['structural_match_reason']}" for r in best_struct_rows})
        )

    # Closest model: the single cheapest transcript in the preserved support
    # set, reported separately so a cost-based "best guess" is never mistaken
    # for -- or used to silently collapse -- the gene_support decision above.
    best_with_values = [(g, t, v) for g, t, v in per_transcript_best if (g, t) in best]
    if best_with_values:
        closest_gene, closest_transcript, closest_value = min(best_with_values, key=lambda x: x[2][1])
    else:
        closest_gene, closest_transcript, closest_value = "", "", (0, 0)

    locus_summary_row = {
        "target_id": locus["target_id"],
        "tolerance_mode": tolerance_mode,
        "n_nb01_blocks": n_nb01_blocks,
        "n_candidate_genes": len(genes),
        "n_candidate_transcripts": sum(len(index.transcripts_of(g["gene_id"])) for g in genes),
        "gene_support_status": gene_support_status,
        "gene_support_reason": gene_support_reason,
        "best_n_matched_pairs": best_with_values[0][2][0] if best_with_values else 0,
        "best_gene_ids": ",".join(sorted({g for g, _ in best})),
        "best_transcript_ids": ",".join(sorted({t for _, t in best})),
        "closest_model_gene_id": closest_gene,
        "closest_model_transcript_id": closest_transcript,
        "closest_model_cost_nt": closest_value[1] if best_with_values else "",
        "structural_match_status": structural_rollup_status,
        "structural_match_reason": structural_rollup_reason,
    }

    return transcript_rows, pair_rows, junction_rows, locus_summary_row


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def tolerance_sensitivity(locus_summary_rows: list[dict]) -> list[dict]:
    """For each locus, does the gene-support verdict or the winning
    transcript set change between the exact and exploratory comparison?"""
    by_locus_mode = {(r["target_id"], r["tolerance_mode"]): r for r in locus_summary_rows}
    rows = []
    for target_id in sorted({t for t, _ in by_locus_mode}):
        exact = by_locus_mode.get((target_id, "exact"))
        exploratory = by_locus_mode.get((target_id, "exploratory_20nt"))
        depends_on_tolerance = (
            exact is None or exploratory is None
            or exact["gene_support_status"] != exploratory["gene_support_status"]
            or exact["best_transcript_ids"] != exploratory["best_transcript_ids"]
        )
        rows.append({
            "target_id": target_id,
            "exact_gene_support_status": exact["gene_support_status"] if exact else "NA",
            "exact_best_transcript_ids": exact["best_transcript_ids"] if exact else "NA",
            "exploratory_gene_support_status": exploratory["gene_support_status"] if exploratory else "NA",
            "exploratory_best_transcript_ids": exploratory["best_transcript_ids"] if exploratory else "NA",
            "depends_on_exploratory_tolerance": depends_on_tolerance,
        })
    return rows


def main() -> None:
    verify_inputs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    loci = load_loci(LOCI_TSV)
    chromosomes = {row["sequence_id"] for row in loci}
    assert chromosomes == {"OZ319704.1"}, chromosomes

    index = Gff3Index()
    index.load(GFF3_GZ, seqid="1")
    index.finalize()
    assert index.region_alias == "OZ319704.1", (
        f"GFF3 region 1 declares Alias={index.region_alias!r}, expected OZ319704.1"
    )

    all_transcript_rows: list[dict] = []
    all_pair_rows: list[dict] = []
    all_junction_rows: list[dict] = []
    all_locus_summary_rows: list[dict] = []
    for locus in loci:
        for mode_name, max_tol in TOLERANCE_MODES.items():
            t_rows, p_rows, j_rows, summary_row = compare_locus_at_tolerance(locus, index, mode_name, max_tol)
            all_transcript_rows.extend(t_rows)
            all_pair_rows.extend(p_rows)
            all_junction_rows.extend(j_rows)
            all_locus_summary_rows.append(summary_row)

    sensitivity_rows = tolerance_sensitivity(all_locus_summary_rows)

    write_tsv(OUT_DIR / "per_locus_summary.tsv", all_locus_summary_rows)
    write_tsv(OUT_DIR / "per_transcript_comparison.tsv", all_transcript_rows)
    write_tsv(OUT_DIR / "per_pair_comparison.tsv", all_pair_rows)
    write_tsv(OUT_DIR / "per_junction_comparison.tsv", all_junction_rows)
    write_tsv(OUT_DIR / "tolerance_sensitivity.tsv", sensitivity_rows)

    manifest = {
        "inputs": {
            "loci_tsv": {"path": str(LOCI_TSV.relative_to(ROOT)), "sha256": sha256_file(LOCI_TSV)},
            "gff3": {
                "path": str(GFF3_GZ.relative_to(ROOT)),
                "source_url": GFF3_SOURCE_URL,
                "annotation_version": ANNOTATION_VERSION,
                "sha256": sha256_file(GFF3_GZ),
                "md5": md5_file(GFF3_GZ),
                "md5_published_in_geneset_md5sum_txt":
                    DECLARED_INPUTS["gff3_gz"]["md5_published_in_geneset_md5sum_txt"],
            },
        },
        "chromosome_1_correspondence": {
            "nb01_sequence_id": "OZ319704.1",
            "gff3_seqid": "1",
            "gff3_region_feature_alias": index.region_alias,
        },
        "matching_criterion": {
            "cost_formula": "cost(nb01_block, cds_segment) = abs(block.start - segment.start) + abs(block.end - segment.end), in nt",
            "coordinate_equality": "two genomic intervals (a_start, a_end) and (b_start, b_end) are EXACT iff "
                                    "a_start == b_start and a_end == b_end (cost == 0), under the shared 1-based "
                                    "inclusive coordinate convention already verified between loci.tsv and the "
                                    "GFF3 (see chromosome_1_correspondence above; no UTR or coordinate-convention "
                                    "mismatch was found for these three loci in the first round of this comparison)",
            "ordering": "each transcript's NB01 blocks and CDS segments are sorted independently into transcription (reading) order "
                        "(ascending genomic start on the plus strand, descending on the minus strand) before matching",
            "objective": "maximise the number of matched pairs subject to a colinear (order-preserving) one-to-one assignment; "
                         "break ties by minimising the summed cost of the matched pairs; every alignment achieving that optimum is kept",
            "tolerance_modes": {
                "exact": {
                    "max_cost_nt": MATCH_TOLERANCE_EXACT_NT,
                    "has_free_parameter": False,
                    "note": "coordinate identity (see coordinate_equality above), not a chosen slack; there is "
                            "no threshold to have pre-registered, so this mode makes no pre-registration claim "
                            "either way",
                },
                "exploratory_20nt": {
                    "max_cost_nt": MATCH_TOLERANCE_EXPLORATORY_NT,
                    "has_free_parameter": True,
                    "pre_registered": False,
                    "note": "chosen after observing this run's own boundary distances (see the comment above "
                            "MATCH_TOLERANCE_EXPLORATORY_NT in this script); no ADR or other record declares "
                            "this threshold ahead of the analysis, so it is reported only as a sensitivity lens "
                            "alongside the exact comparison, never as a pre-registered criterion",
                },
            },
            "transcripts_compared_independently": True,
            "note_on_independence": "each transcript is matched against the full NB01 block list on its own; a CDS segment "
                                     "shared by two isoforms is available to both and is never removed from a shared pool",
            "gene_support_vs_structural_match": "gene_support_status asks whether exactly one gene's transcript(s) "
                                                 "account for every NB01 block; structural_match_status asks "
                                                 "whether the winning transcript's own CDS segments are each paired "
                                                 "with an NB01 block with none left over. The two are computed "
                                                 "independently: a locus can be gene_support_status=DETERMINED "
                                                 "while its structural_match_status is PARTIAL_SKIPPED_SEGMENT.",
            "gene_support_tie_rule": "genes are counted as tied by whether they have AT LEAST ONE transcript "
                                     "reaching full NB01 block coverage, BEFORE any cost-based tiebreak; two "
                                     "genes that both fully explain the locus are reported as "
                                     "INDETERMINATE_CROSS_GENE_TIE and both are kept in best_gene_ids / "
                                     "best_transcript_ids even when their costs differ. The lowest-cost "
                                     "transcript among the preserved set is reported separately in "
                                     "closest_model_gene_id / closest_model_transcript_id / "
                                     "closest_model_cost_nt -- a descriptive pointer, never a resolution of "
                                     "the tie. NO_PAIRS_MATCHED leaves best_gene_ids, best_transcript_ids and "
                                     "closest_model_* empty: zero matched pairs is not a 'best' explanation.",
        },
        "per_locus_tolerance_sensitivity": sensitivity_rows,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for row in all_locus_summary_rows:
        print(f"{row['target_id']} [{row['tolerance_mode']}]: "
              f"gene_support={row['gene_support_status']} "
              f"structural_match={row['structural_match_status']} "
              f"({row['best_n_matched_pairs']}/{row['n_nb01_blocks']} blocks)")


if __name__ == "__main__":
    main()
