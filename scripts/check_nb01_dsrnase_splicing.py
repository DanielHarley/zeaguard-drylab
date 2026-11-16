#!/usr/bin/env python3
"""Splice-aware check of the three published Dmai-dsRNase CDS against GCA_975739785.1.

The question: which chains of genomic alignment explain the published dsRNase-3
CDS, in particular across the transition between the ENSCHMG00000003138 region
and the ube2w (ENSCHMG00000002609) region.

The GFF3 is read only after the alignment, to compare junctions against
annotated introns and to name the annotated models. It is never given to
minimap2: the alignment is annotation-free.

Runs in the canonical Linux environment (conda env `zeaguard`), which is where
minimap2 lives. Every declared input is verified by sha256 before use and the
run refuses on any mismatch.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Declared inputs. Verified before anything is read for content.
# --------------------------------------------------------------------------

DECLARED_INPUTS = {
    "cds_queries": {
        "path": "results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/raw/cds_queries.fna",
        "sha256": "7e378f84688253a78fbaa0aa631b536e94bcccca9d2a0433eb44bad7dd214bf2",
        "role": "query source, the three published CDS as derived by the historical run",
    },
    "genome_fna_gz": {
        "path": "data/external/nb01_locus_mapping/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz",
        "sha256": "aef4d8ec0891bece052bc58afa5b0da3e2a2bf047f9283032bbf253459509184",
        "sha256_decompressed": "54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04",
        "role": "alignment target, primary assembly",
    },
    "gff3_gz": {
        "path": "data/external/nb01_locus_mapping/GCA_975739785.1_ensembl_2026_02_genes.gff3.gz",
        "sha256": "2606dd4fbb71b9555c643656656bb2f2aad82a072422236df57eaed483cb411d",
        "role": "post-alignment comparison only, Ensembl AEGIS geneset 2026_02",
    },
    "loci_tsv": {
        "path": "results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/loci.tsv",
        "sha256": "57b0d68ce3d0460c832f15ab24bd8ab1214dd90e3dc63807140d62ed6ff172e4",
        "role": "post-alignment comparison only, the historical BLAST tiling's inferred junctions",
    },
}

OUTPUT_SUBDIR = "results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/splice_check_v3"

# Name of the exclusive claim held on an output directory while a run writes.
LOCK_NAME = ".splice_check.lock"

# Exactly the parameters this round declares, in this order.
MINIMAP2_PARAMS = ["-a", "-x", "splice:hq", "-uf", "--eqx", "--cs=long",
                   "-G", "50k", "-p", "0.8", "-N", "5"]

# The only aligner version these results are declared for. Verified both when
# running minimap2 and when re-analysing a saved SAM, whose @PG line carries it.
MINIMAP2_EXPECTED_VERSION = "2.31-r1302"

# The two annotated genes the question is about.
GENE_UPSTREAM = "ENSCHMG00000003138"
GENE_DOWNSTREAM = "ENSCHMG00000002609"  # Name=ube2w

# The historical BLAST-tiling candidate this round is asked to compare against.
HISTORICAL_TRANSITION_QUERY_POS = 642
HISTORICAL_TRANSITION_JUMP_RECORDED_NT = 5125   # run record, inferred intron 3 of dsRNase-3
HISTORICAL_TRANSITION_JUMP_AS_STATED_NT = 5130  # figure named in this round's task

# Control reference for the two loci that are not in question. Every field is a
# requirement: a control passes only when all of them hold, and the row names
# each one that does not.
CONTROL_REFERENCE = {
    "dsRNase-1": {
        "cds_len": 1323,
        "expected_nt_differences": 1,
        "difference_positions": [840],
        "ref_name": "OZ319704.1",
        "strand": "+",
        "ref_start": 60966751,
        "ref_end": 60973368,
        "n_junctions": 5,
        "junction_transcript": "ENSCHMT00000004227",
    },
    "dsRNase-2": {
        "cds_len": 1425,
        "expected_nt_differences": 0,
        "difference_positions": [],
        "ref_name": "OZ319704.1",
        "strand": "+",
        "ref_start": 69024822,
        "ref_end": 69037412,
        "n_junctions": 6,
        "junction_transcript": "ENSCHMT00000006229",
    },
}

CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")
COMPLEMENT = str.maketrans("ACGTNacgtnRYKMSWBDHVrykmswbdhv",
                           "TGCANtgcanYRMKSWVHDByrmkswvhdb")

ALIGNED_OPS = frozenset("M=X")
REF_CONSUMING = frozenset("M=XDN")
QUERY_COORD_CONSUMING = frozenset("M=XISH")
CLIP_OPS = frozenset("SH")


class VerificationError(RuntimeError):
    """A declared input did not verify, or an invariant failed."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def revcomp(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def read_fasta(path: Path, wanted: set[str] | None = None) -> dict[str, str]:
    """Read a FASTA, keeping only `wanted` sequence names when given."""
    opener = gzip.open if path.suffix == ".gz" else open
    sequences: dict[str, str] = {}
    name: str | None = None
    parts: list[str] = []

    def flush() -> None:
        if name is not None and (wanted is None or name in wanted):
            sequences[name] = "".join(parts)

    with opener(path, "rt") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                flush()
                name = line[1:].split()[0]
                parts = []
            else:
                if wanted is None or name in wanted:
                    parts.append(line)
    flush()
    return sequences


def write_tsv(path: Path, columns: list[str], rows: list[dict]) -> None:
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join("" if row.get(c) is None else str(row.get(c)) for c in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# CIGAR / SAM parsing. Pure functions, so the tests can drive them directly.
# --------------------------------------------------------------------------


def parse_cigar(cigar: str) -> list[tuple[int, str]]:
    """Parse a CIGAR string, rejecting anything that does not round-trip."""
    if cigar == "*":
        return []
    ops = CIGAR_RE.findall(cigar)
    if "".join(length + op for length, op in ops) != cigar:
        raise VerificationError(f"unparsable CIGAR: {cigar!r}")
    return [(int(length), op) for length, op in ops]


def read_length_from_cigar(ops: list[tuple[int, str]]) -> int:
    """Full original read length, counting hard clips."""
    return sum(length for length, op in ops if op in QUERY_COORD_CONSUMING)


@dataclass
class SamRecord:
    qname: str
    flag: int
    rname: str
    pos: int
    mapq: int
    cigar: str
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def is_reverse(self) -> bool:
        return bool(self.flag & 0x10)

    @property
    def is_secondary(self) -> bool:
        return bool(self.flag & 0x100)

    @property
    def is_supplementary(self) -> bool:
        return bool(self.flag & 0x800)

    @property
    def is_unmapped(self) -> bool:
        return bool(self.flag & 0x4)

    @property
    def record_class(self) -> str:
        if self.is_unmapped:
            return "unmapped"
        if self.is_secondary:
            return "secondary"
        if self.is_supplementary:
            return "supplementary"
        return "primary"


def parse_sam(text: str) -> tuple[list[str], list[SamRecord]]:
    """Split SAM text into header lines and alignment records."""
    header: list[str] = []
    records: list[SamRecord] = []
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("@"):
            header.append(line)
            continue
        fields = line.split("\t")
        if len(fields) < 11:
            raise VerificationError(f"SAM line has {len(fields)} fields, expected >= 11")
        tags: dict[str, str] = {}
        for field_text in fields[11:]:
            parts = field_text.split(":", 2)
            if len(parts) == 3:
                tags[parts[0]] = parts[2]
        records.append(SamRecord(
            qname=fields[0],
            flag=int(fields[1]),
            rname=fields[2],
            pos=int(fields[3]),
            mapq=int(fields[4]),
            cigar=fields[5],
            tags=tags,
        ))
    return header, records


def to_original_interval(start: int, end: int, read_len: int, is_reverse: bool) -> tuple[int, int]:
    """Map a 1-based inclusive interval from record space to original query orientation."""
    if not is_reverse:
        return start, end
    return read_len - end + 1, read_len - start + 1


def walk_record(ops: list[tuple[int, str]], ref_start: int) -> dict:
    """Walk a CIGAR, returning blocks, junctions and clipping in RECORD query space.

    `aligned` intervals are the query positions actually aligned to a reference
    base, that is the M, = and X runs only. Insertions sit inside a block's query
    extent but align to nothing, so coverage is computed from `aligned`, never
    from the block extent.
    """
    qpos = 1
    rpos = ref_start
    blocks: list[dict] = []
    junctions: list[dict] = []
    aligned: list[tuple[int, int]] = []
    leading = {"S": 0, "H": 0}
    trailing = {"S": 0, "H": 0}
    current: dict | None = None
    seen_aligned = False

    def new_block() -> dict:
        return {"q_start": qpos, "r_start": rpos, "q_end": None, "r_end": None,
                "n_match": 0, "n_mismatch": 0, "n_m_ambiguous": 0,
                "n_ins_nt": 0, "n_ins_events": 0, "n_del_nt": 0, "n_del_events": 0,
                "aligned": []}

    for length, op in ops:
        if op in CLIP_OPS:
            (trailing if seen_aligned else leading)[op] += length
            qpos += length
            continue
        if op == "P":
            continue
        if op in ALIGNED_OPS:
            if current is None:
                current = new_block()
            if op == "=":
                current["n_match"] += length
            elif op == "X":
                current["n_mismatch"] += length
            else:
                current["n_m_ambiguous"] += length
            current["aligned"].append((qpos, qpos + length - 1))
            aligned.append((qpos, qpos + length - 1))
            qpos += length
            rpos += length
            current["q_end"] = qpos - 1
            current["r_end"] = rpos - 1
            seen_aligned = True
        elif op == "I":
            if current is None:
                raise VerificationError("insertion before any aligned base")
            current["n_ins_nt"] += length
            current["n_ins_events"] += 1
            qpos += length
        elif op == "D":
            if current is None:
                raise VerificationError("deletion before any aligned base")
            current["n_del_nt"] += length
            current["n_del_events"] += 1
            rpos += length
            current["r_end"] = rpos - 1
        elif op == "N":
            if current is None:
                raise VerificationError("junction before any aligned base")
            blocks.append(current)
            junctions.append({
                "intron_ref_start": rpos,
                "intron_ref_end": rpos + length - 1,
                "intron_len": length,
                "q_pos_before": qpos - 1,
                "q_pos_after": qpos,
            })
            rpos += length
            current = None
        else:
            raise VerificationError(f"unhandled CIGAR operation {op!r}")

    if current is not None:
        blocks.append(current)
    if not blocks:
        raise VerificationError("CIGAR contains no aligned block")

    return {
        "blocks": blocks,
        "junctions": junctions,
        "aligned": aligned,
        "clip_leading": leading,
        "clip_trailing": trailing,
        "ref_end": blocks[-1]["r_end"],
    }


def normalise_walk(walk: dict, read_len: int, is_reverse: bool) -> dict:
    """Put a walk's query coordinates into the original query orientation."""
    blocks = []
    for block in walk["blocks"]:
        q_start, q_end = to_original_interval(block["q_start"], block["q_end"], read_len, is_reverse)
        block_aligned = [to_original_interval(s, e, read_len, is_reverse)
                         for s, e in block["aligned"]]
        blocks.append({**block, "q_start_orig": q_start, "q_end_orig": q_end,
                       "aligned_orig": sorted(block_aligned)})
    blocks.sort(key=lambda b: b["q_start_orig"])

    aligned_orig = sorted(to_original_interval(s, e, read_len, is_reverse)
                          for s, e in walk["aligned"])

    junctions = []
    for junction in walk["junctions"]:
        before = junction["q_pos_before"]
        after = junction["q_pos_after"]
        if is_reverse:
            before_orig = read_len - before + 1
            after_orig = read_len - after + 1
        else:
            before_orig, after_orig = before, after
        upstream = min(before_orig, after_orig)
        junctions.append({
            **junction,
            "query_pos_upstream_orig": upstream,
            "query_pos_downstream_orig": max(before_orig, after_orig),
            "codon_phase_after_upstream": upstream % 3,
        })
    junctions.sort(key=lambda j: j["query_pos_upstream_orig"])

    if is_reverse:
        clip_left, clip_right = walk["clip_trailing"], walk["clip_leading"]
    else:
        clip_left, clip_right = walk["clip_leading"], walk["clip_trailing"]

    return {
        "blocks": blocks,
        "junctions": junctions,
        "aligned_intervals_orig": aligned_orig,
        "clip_left": clip_left,
        "clip_right": clip_right,
        "ref_end": walk["ref_end"],
    }


def union_length(intervals: list[tuple[int, int]]) -> int:
    """Total length covered by a set of 1-based inclusive intervals."""
    if not intervals:
        return 0
    total = 0
    current_start, current_end = None, None
    for start, end in sorted(intervals):
        if current_start is None:
            current_start, current_end = start, end
            continue
        if start <= current_end + 1:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start + 1
            current_start, current_end = start, end
    total += current_end - current_start + 1
    return total


def mismatch_positions(ops: list[tuple[int, str]], record_query: str, ref_seq: str,
                       ref_start: int, read_len: int, is_reverse: bool) -> list[dict]:
    """Per-base differences implied by the CIGAR, in original query coordinates."""
    differences: list[dict] = []
    qpos = 1
    rpos = ref_start
    for length, op in ops:
        if op in CLIP_OPS:
            qpos += length
            continue
        if op == "P":
            continue
        if op in ALIGNED_OPS:
            if op != "=":
                for offset in range(length):
                    q_at = qpos + offset
                    r_at = rpos + offset
                    q_base = record_query[q_at - 1]
                    r_base = ref_seq[r_at - 1]
                    if op == "X" or q_base.upper() != r_base.upper():
                        q_orig = read_len - q_at + 1 if is_reverse else q_at
                        differences.append({
                            "kind": "substitution",
                            "query_pos_orig": q_orig,
                            "ref_pos": r_at,
                            "query_base_record_space": q_base,
                            "ref_base": r_base,
                        })
            qpos += length
            rpos += length
        elif op == "I":
            q_start_orig, q_end_orig = to_original_interval(qpos, qpos + length - 1, read_len, is_reverse)
            differences.append({
                "kind": "insertion_in_query",
                "query_pos_orig": q_start_orig,
                "query_end_orig": q_end_orig,
                "ref_pos": rpos,
                "length": length,
            })
            qpos += length
        elif op == "D":
            differences.append({
                "kind": "deletion_from_query",
                "query_pos_orig": read_len - qpos + 2 if is_reverse else qpos - 1,
                "ref_pos": rpos,
                "ref_end": rpos + length - 1,
                "length": length,
            })
            rpos += length
        elif op == "N":
            rpos += length
    return differences


# --------------------------------------------------------------------------
# GFF3, read only after the alignment
# --------------------------------------------------------------------------


def parse_attributes(text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for item in text.rstrip(";").split(";"):
        if not item:
            continue
        key, _, value = item.partition("=")
        attributes[key] = value
    return attributes


@dataclass
class Annotation:
    seqid_to_accession: dict[str, str] = field(default_factory=dict)
    accession_to_seqid: dict[str, str] = field(default_factory=dict)
    genes: dict[str, dict] = field(default_factory=dict)
    transcripts: dict[str, dict] = field(default_factory=dict)

    def introns_of(self, transcript_id: str, kind: str = "exon") -> list[tuple[int, int]]:
        segments = sorted(self.transcripts[transcript_id][kind])
        return [(segments[i][1] + 1, segments[i + 1][0] - 1) for i in range(len(segments) - 1)]


def load_annotation(path: Path, wanted_accessions: set[str]) -> Annotation:
    annotation = Annotation()
    opener = gzip.open if path.suffix == ".gz" else open
    gene_types = {"gene", "ncRNA_gene", "pseudogene"}
    transcript_parent: dict[str, str] = {}

    with opener(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9:
                continue
            seqid, _, feature, start, end, _, strand, phase, attribute_text = fields[:9]
            attributes = parse_attributes(attribute_text)

            if feature == "region":
                alias = attributes.get("Alias")
                if alias:
                    annotation.seqid_to_accession[seqid] = alias
                    annotation.accession_to_seqid[alias] = seqid
                continue

            accession = annotation.seqid_to_accession.get(seqid)
            if accession is None or accession not in wanted_accessions:
                continue

            start_i, end_i = int(start), int(end)
            if feature in gene_types:
                gene_id = attributes.get("gene_id") or attributes.get("ID", "").partition(":")[2]
                annotation.genes[gene_id] = {
                    "gene_id": gene_id,
                    "name": attributes.get("Name", ""),
                    "biotype": attributes.get("biotype", ""),
                    "accession": accession,
                    "start": start_i,
                    "end": end_i,
                    "strand": strand,
                }
            elif "transcript_id" in attributes:
                transcript_id = attributes["transcript_id"]
                gene_id = attributes.get("Parent", "").partition(":")[2]
                transcript_parent[transcript_id] = gene_id
                annotation.transcripts.setdefault(transcript_id, {
                    "transcript_id": transcript_id,
                    "gene_id": gene_id,
                    "accession": accession,
                    "strand": strand,
                    "start": start_i,
                    "end": end_i,
                    "canonical": "Ensembl_canonical" in attributes.get("tag", ""),
                    "exon": [],
                    "CDS": [],
                })
            elif feature in ("exon", "CDS"):
                transcript_id = attributes.get("Parent", "").partition(":")[2]
                if not transcript_id:
                    continue
                entry = annotation.transcripts.setdefault(transcript_id, {
                    "transcript_id": transcript_id,
                    "gene_id": transcript_parent.get(transcript_id, ""),
                    "accession": accession,
                    "strand": strand,
                    "start": start_i,
                    "end": end_i,
                    "canonical": False,
                    "exon": [],
                    "CDS": [],
                })
                entry[feature].append((start_i, end_i))

    for transcript in annotation.transcripts.values():
        if not transcript["gene_id"]:
            transcript["gene_id"] = transcript_parent.get(transcript["transcript_id"], "")
    return annotation


def genes_overlapping(annotation: Annotation, accession: str, start: int, end: int,
                      cds_only: bool = True) -> list[str]:
    """Gene ids whose CDS segments (or whose gene span) overlap an interval."""
    hits: set[str] = set()
    if cds_only:
        for transcript in annotation.transcripts.values():
            if transcript["accession"] != accession:
                continue
            for seg_start, seg_end in transcript["CDS"]:
                if seg_start <= end and start <= seg_end:
                    hits.add(transcript["gene_id"])
                    break
    else:
        for gene in annotation.genes.values():
            if gene["accession"] == accession and gene["start"] <= end and start <= gene["end"]:
                hits.add(gene["gene_id"])
    return sorted(hits)


def gene_label(annotation: Annotation, gene_id: str) -> str:
    gene = annotation.genes.get(gene_id)
    if gene and gene.get("name"):
        return f"{gene_id}({gene['name']})"
    return gene_id


def match_junction_to_annotation(annotation: Annotation, accession: str,
                                 intron_start: int, intron_end: int) -> dict:
    exact: list[str] = []
    nearest = None
    for transcript in annotation.transcripts.values():
        if transcript["accession"] != accession:
            continue
        for ann_start, ann_end in annotation.introns_of(transcript["transcript_id"]):
            d_start = intron_start - ann_start
            d_end = intron_end - ann_end
            if d_start == 0 and d_end == 0:
                exact.append(transcript["transcript_id"])
            cost = abs(d_start) + abs(d_end)
            if nearest is None or cost < nearest["cost"]:
                nearest = {
                    "cost": cost,
                    "transcript_id": transcript["transcript_id"],
                    "gene_id": transcript["gene_id"],
                    "intron_start": ann_start,
                    "intron_end": ann_end,
                    "d_start": d_start,
                    "d_end": d_end,
                }
    exact_genes = sorted({annotation.transcripts[t]["gene_id"] for t in exact})
    return {"exact_transcripts": sorted(exact), "exact_genes": exact_genes, "nearest": nearest}


# --------------------------------------------------------------------------
# Verification and the alignment run
# --------------------------------------------------------------------------


class OutputReservation:
    """An exclusive claim on one output directory, held until the last write."""

    def __init__(self, out_dir: Path, lock_path: Path, fd: int):
        self.out_dir = out_dir
        self.lock_path = lock_path
        self._fd: int | None = fd

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "OutputReservation":
        return self

    def __exit__(self, *_exc_info: object) -> bool:
        self.release()
        return False


def reserve_output_dir(out_dir: Path) -> OutputReservation:
    """Claim `out_dir` exclusively, refusing one another run holds or that has content.

    Testing emptiness and then writing is two steps, and two runs starting
    against the same empty destination can both pass the test before either
    writes. The claim closes that window: creating the lock file with
    O_CREAT|O_EXCL is a single atomic operation, so exactly one run can hold a
    given destination, and the contents are inspected *under* the claim. The
    loser is refused before it writes anything.

    The claim is held until the last write and released afterwards, so a
    completed run leaves only its outputs behind. A directory that is empty and
    unclaimed is accepted; one that already holds outputs is refused.
    """
    if out_dir.exists() and not out_dir.is_dir():
        raise VerificationError(f"output path exists and is not a directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    lock_path = out_dir / LOCK_NAME
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise VerificationError(
            f"output directory is reserved by another run: {lock_path} already exists; "
            f"nothing was written. Wait for that run to finish, pass --out-subdir to "
            f"name a different directory, or remove the lock file if an interrupted "
            f"run left it behind.") from None

    reservation = OutputReservation(out_dir, lock_path, fd)
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
        # Checked under the claim: no other run can add files between here and
        # the first write.
        existing = sorted(path.name for path in out_dir.iterdir() if path.name != LOCK_NAME)
        if existing:
            shown = ", ".join(existing[:3]) + (", ..." if len(existing) > 3 else "")
            raise VerificationError(
                f"output directory is not empty: {out_dir} holds {len(existing)} "
                f"entries ({shown}); nothing was written. Pass --out-subdir to "
                f"name a new directory.")
    except BaseException:
        reservation.release()
        raise
    return reservation


def verify_inputs(root: Path) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for role, declaration in DECLARED_INPUTS.items():
        path = root / declaration["path"]
        if not path.is_file():
            raise VerificationError(f"declared input is missing: {role} -> {declaration['path']}")
        observed = sha256_file(path)
        if observed != declaration["sha256"]:
            raise VerificationError(
                f"sha256 mismatch for {role}: declared {declaration['sha256']}, observed {observed}")
        resolved[role] = path
        print(f"[verify] {role}: sha256 {observed} OK", file=sys.stderr)
    return resolved


def pg_version_from_header(header: list[str]) -> tuple[str | None, str | None]:
    """The aligner version and command line recorded in a SAM's @PG line."""
    for line in header:
        if not line.startswith("@PG"):
            continue
        version = command = None
        for field_text in line.split("\t")[1:]:
            if field_text.startswith("VN:"):
                version = field_text[3:]
            elif field_text.startswith("CL:"):
                command = field_text[3:]
        return version, command
    return None, None


def run_minimap2(genome: Path, queries: Path, sam_out: Path, log_out: Path) -> dict:
    version = subprocess.run(["minimap2", "--version"], capture_output=True, text=True,
                             check=True).stdout.strip()
    if version != MINIMAP2_EXPECTED_VERSION:
        raise VerificationError(
            f"minimap2 version mismatch: expected {MINIMAP2_EXPECTED_VERSION}, found {version}")
    command = ["minimap2", *MINIMAP2_PARAMS, str(genome), str(queries)]
    print(f"[minimap2] {' '.join(command)}", file=sys.stderr)
    with sam_out.open("wb") as sam_handle, log_out.open("wb") as log_handle:
        subprocess.run(command, stdout=sam_handle, stderr=log_handle, check=True)
    return {"version": version, "command": command}


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


def analyse(records: list[SamRecord], queries: dict[str, str], genome: dict[str, str],
            annotation: Annotation) -> dict:
    record_rows: list[dict] = []
    block_rows: list[dict] = []
    junction_rows: list[dict] = []
    analysed: list[dict] = []

    for index, record in enumerate(records):
        if record.is_unmapped:
            record_rows.append({
                "query": record.qname,
                "cds_len_fasta": len(queries[record.qname]),
                "record_index": index,
                "flag": record.flag,
                "record_class": "unmapped",
                "ref_name": "",
                "strand": "",
            })
            continue

        original = queries[record.qname]
        cds_len = len(original)
        ops = parse_cigar(record.cigar)
        read_len = read_length_from_cigar(ops)
        if read_len != cds_len:
            raise VerificationError(
                f"{record.qname} record {index}: CIGAR accounts for {read_len} nt, "
                f"FASTA CDS is {cds_len} nt")

        walk = normalise_walk(walk_record(ops, record.pos), read_len, record.is_reverse)
        record_query = revcomp(original) if record.is_reverse else original
        ref_seq = genome[record.rname]

        n_match = sum(b["n_match"] for b in walk["blocks"])
        n_mismatch = sum(b["n_mismatch"] for b in walk["blocks"])
        n_m_ambiguous = sum(b["n_m_ambiguous"] for b in walk["blocks"])
        n_ins_nt = sum(b["n_ins_nt"] for b in walk["blocks"])
        n_ins_events = sum(b["n_ins_events"] for b in walk["blocks"])
        n_del_nt = sum(b["n_del_nt"] for b in walk["blocks"])
        n_del_events = sum(b["n_del_events"] for b in walk["blocks"])
        # Coverage counts only query positions aligned to a reference base.
        query_intervals = walk["aligned_intervals_orig"]
        query_aligned_nt = union_length(query_intervals)
        if query_aligned_nt != n_match + n_mismatch + n_m_ambiguous:
            raise VerificationError(
                f"{record.qname} record {index}: aligned-interval union is {query_aligned_nt} nt "
                f"but M/=/X account for {n_match + n_mismatch + n_m_ambiguous} nt")
        block_extents = [(b["q_start_orig"], b["q_end_orig"]) for b in walk["blocks"]]
        query_start_orig = min(s for s, _ in block_extents)
        query_end_orig = max(e for _, e in block_extents)

        differences = mismatch_positions(ops, record_query, ref_seq, record.pos,
                                         read_len, record.is_reverse)
        substitutions = [d for d in differences if d["kind"] == "substitution"]

        strand = "-" if record.is_reverse else "+"
        gene_hits: set[str] = set()
        for block_index, block in enumerate(walk["blocks"]):
            overlapping = genes_overlapping(annotation, record.rname, block["r_start"], block["r_end"])
            gene_hits.update(overlapping)
            block_rows.append({
                "query": record.qname,
                "record_index": index,
                "record_class": record.record_class,
                "strand": strand,
                "block_index": block_index,
                "query_start_orig": block["q_start_orig"],
                "query_end_orig": block["q_end_orig"],
                "query_len_nt": block["q_end_orig"] - block["q_start_orig"] + 1,
                "query_aligned_nt": union_length(block["aligned_orig"]),
                "ref_name": record.rname,
                "ref_start": block["r_start"],
                "ref_end": block["r_end"],
                "ref_len_nt": block["r_end"] - block["r_start"] + 1,
                "n_match_nt": block["n_match"],
                "n_mismatch_nt": block["n_mismatch"],
                "n_ins_nt": block["n_ins_nt"],
                "n_del_nt": block["n_del_nt"],
                "genes_with_cds_overlap": ",".join(gene_label(annotation, g) for g in overlapping),
            })

        for junction_index, junction in enumerate(walk["junctions"]):
            intron_start = junction["intron_ref_start"]
            intron_end = junction["intron_ref_end"]
            donor = ref_seq[intron_start - 1:intron_start + 1]
            acceptor = ref_seq[intron_end - 2:intron_end]
            motif_forward = (donor + acceptor).upper()
            motif_transcript = revcomp(motif_forward) if record.is_reverse else motif_forward
            match = match_junction_to_annotation(annotation, record.rname, intron_start, intron_end)
            nearest = match["nearest"] or {}
            junction_rows.append({
                "query": record.qname,
                "record_index": index,
                "record_class": record.record_class,
                "strand": strand,
                "junction_index": junction_index,
                "ref_name": record.rname,
                "intron_ref_start": intron_start,
                "intron_ref_end": intron_end,
                "intron_len_nt": junction["intron_len"],
                "query_pos_upstream_orig": junction["query_pos_upstream_orig"],
                "query_pos_downstream_orig": junction["query_pos_downstream_orig"],
                "codon_phase_after_upstream": junction["codon_phase_after_upstream"],
                "motif_forward_genome": motif_forward,
                "motif_transcript_oriented": motif_transcript,
                "motif_is_canonical_gtag": motif_transcript == "GTAG",
                "annotated_exact_match_transcripts": ",".join(match["exact_transcripts"]),
                "annotated_exact_match_genes": ",".join(
                    gene_label(annotation, g) for g in match["exact_genes"]),
                "nearest_annotated_transcript": nearest.get("transcript_id", ""),
                "nearest_annotated_gene": gene_label(annotation, nearest["gene_id"])
                if nearest.get("gene_id") else "",
                "nearest_intron_ref_start": nearest.get("intron_start", ""),
                "nearest_intron_ref_end": nearest.get("intron_end", ""),
                "nearest_d_start_nt": nearest.get("d_start", ""),
                "nearest_d_end_nt": nearest.get("d_end", ""),
            })

        analysed.append({
            "record": record,
            "index": index,
            "walk": walk,
            "query_intervals": query_intervals,
            "genes": sorted(gene_hits),
            "substitutions": substitutions,
            "differences": differences,
            "cds_len": cds_len,
        })

        record_rows.append({
            "query": record.qname,
            "cds_len_fasta": cds_len,
            "record_index": index,
            "flag": record.flag,
            "record_class": record.record_class,
            "mapq": record.mapq,
            "ref_name": record.rname,
            "ref_start": record.pos,
            "ref_end": walk["ref_end"],
            "ref_span_nt": walk["ref_end"] - record.pos + 1,
            "strand": strand,
            "query_start_orig": query_start_orig,
            "query_end_orig": query_end_orig,
            "query_span_orig_nt": query_end_orig - query_start_orig + 1,
            "n_blocks": len(walk["blocks"]),
            "n_junctions": len(walk["junctions"]),
            "query_aligned_nt": query_aligned_nt,
            "query_insertion_nt": n_ins_nt,
            "query_clip_left_nt": walk["clip_left"]["S"] + walk["clip_left"]["H"],
            "query_clip_right_nt": walk["clip_right"]["S"] + walk["clip_right"]["H"],
            "clip_left_soft_nt": walk["clip_left"]["S"],
            "clip_left_hard_nt": walk["clip_left"]["H"],
            "clip_right_soft_nt": walk["clip_right"]["S"],
            "clip_right_hard_nt": walk["clip_right"]["H"],
            "n_match_nt": n_match,
            "n_mismatch_nt": n_mismatch,
            "n_m_ambiguous_nt": n_m_ambiguous,
            "n_ins_events": n_ins_events,
            "n_ins_nt": n_ins_nt,
            "n_del_events": n_del_events,
            "n_del_nt": n_del_nt,
            "nm_tag": record.tags.get("NM", ""),
            "coverage_aligned_frac": round(query_aligned_nt / cds_len, 6),
            "genes_with_cds_overlap": ",".join(gene_label(annotation, g) for g in sorted(gene_hits)),
            "n_substitutions_observed": len(substitutions),
            "substitution_query_positions": ",".join(
                str(d["query_pos_orig"]) for d in substitutions[:20]),
        })

    # Split-alignment groups: one primary chain per query (primary + supplementary),
    # each secondary record standing alone as an alternative.
    for row in record_rows:
        row.setdefault("split_group", "")
        row.setdefault("group_n_records", "")
        row.setdefault("group_union_covered_nt", "")
        row.setdefault("group_union_coverage_frac", "")

    by_query: dict[str, list[dict]] = {}
    for item in analysed:
        by_query.setdefault(item["record"].qname, []).append(item)

    for qname, items in by_query.items():
        chain = [i for i in items if i["record"].record_class in ("primary", "supplementary")]
        cds_len = items[0]["cds_len"]
        if chain:
            intervals = [iv for i in chain for iv in i["query_intervals"]]
            covered = union_length(intervals)
            for item in chain:
                row = next(r for r in record_rows if r["record_index"] == item["index"])
                row["split_group"] = f"{qname}:primary_chain"
                row["group_n_records"] = len(chain)
                row["group_union_covered_nt"] = covered
                row["group_union_coverage_frac"] = round(covered / cds_len, 6)
        for item in items:
            if item["record"].record_class == "secondary":
                row = next(r for r in record_rows if r["record_index"] == item["index"])
                covered = union_length(item["query_intervals"])
                row["split_group"] = f"{qname}:secondary_{item['index']}"
                row["group_n_records"] = 1
                row["group_union_covered_nt"] = covered
                row["group_union_coverage_frac"] = round(covered / cds_len, 6)

    return {
        "record_rows": record_rows,
        "block_rows": block_rows,
        "junction_rows": junction_rows,
        "analysed": analysed,
        "by_query": by_query,
    }


def load_historical_junctions(path: Path) -> dict[str, list[dict]]:
    """Inferred intron sizes and query-junction offsets of the historical BLAST tiling."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    target_i = header.index("target_id")
    sizes_i = header.index("intron_sizes_nt")
    offsets_i = header.index("query_junction_offsets_nt")
    historical: dict[str, list[dict]] = {}
    for line in lines[1:]:
        if not line:
            continue
        fields = line.split("\t")
        sizes = [int(v) for v in fields[sizes_i].split(";") if v]
        offsets = [int(v) for v in fields[offsets_i].split(";") if v]
        if len(sizes) != len(offsets):
            raise VerificationError(
                f"{fields[target_i]}: {len(sizes)} intron sizes but {len(offsets)} offsets")
        historical.setdefault(fields[target_i], []).extend(
            {"intron_size_nt": size, "query_junction_offset_nt": offset}
            for size, offset in zip(sizes, offsets))
    return historical


def build_junction_reconciliation(analysis: dict,
                                  historical: dict[str, list[dict]]) -> list[dict]:
    """Each splice-aware junction against the historical tiling's inferred intron.

    The historical tiling reported a negative query-junction offset wherever two
    BLAST blocks overlapped on the query, which is alignment ambiguity rather
    than missing CDS. If the splice-aware aligner resolves each junction to the
    canonical site, its intron should be the historical intron widened by
    exactly that overlap.
    """
    rows: list[dict] = []
    for query, junctions in historical.items():
        chain = [i for i in analysis["by_query"].get(query, [])
                 if i["record"].record_class in ("primary", "supplementary")]
        observed = [j for item in chain for j in item["walk"]["junctions"]]
        observed.sort(key=lambda j: j["query_pos_upstream_orig"])
        for index, entry in enumerate(junctions):
            overlap = abs(entry["query_junction_offset_nt"])
            expected = entry["intron_size_nt"] + overlap
            actual = observed[index]["intron_len"] if index < len(observed) else None
            rows.append({
                "query": query,
                "junction_index": index,
                "historical_intron_size_nt": entry["intron_size_nt"],
                "historical_query_junction_offset_nt": entry["query_junction_offset_nt"],
                "historical_plus_overlap_nt": expected,
                "splice_aware_intron_len_nt": actual if actual is not None else "",
                "difference_nt": actual - expected if actual is not None else "",
                "agrees": actual == expected if actual is not None else False,
            })
    return rows


def evaluate_control(query: str, reference: dict, items: list[dict],
                     annotation: Annotation) -> dict:
    """Check one control against every declared requirement, naming each failure."""
    failures: list[str] = []
    primaries = [i for i in items if i["record"].record_class == "primary"]
    chain = [i for i in items if i["record"].record_class in ("primary", "supplementary")]

    if len(primaries) != 1:
        failures.append(f"single_primary_record(observed={len(primaries)})")
    if not chain:
        return {
            "query": query,
            "expected_cds_len": reference["cds_len"],
            "expected_nt_differences": reference["expected_nt_differences"],
            "failed_requirements": "no_alignment",
            "verdict": "FAILED",
        }

    item = primaries[0] if primaries else chain[0]
    record = item["record"]
    cds_len = item["cds_len"]
    covered = union_length(item["query_intervals"])
    substitutions = item["substitutions"]
    indels = [d for d in item["differences"]
              if d["kind"] in ("insertion_in_query", "deletion_from_query")]
    junctions = item["walk"]["junctions"]
    clip_left = item["walk"]["clip_left"]
    clip_right = item["walk"]["clip_right"]
    clip_total = sum(clip_left.values()) + sum(clip_right.values())
    strand = "-" if record.is_reverse else "+"

    # The expected transcript must be on the alignment's own sequence and strand
    # before any of its junctions are credited: identical intron coordinates on
    # the opposite strand are a different model, not a match.
    expected_transcript = reference["junction_transcript"]
    transcript = annotation.transcripts.get(expected_transcript)
    transcript_strand = transcript["strand"] if transcript else None
    transcript_usable = (
        transcript is not None
        and transcript["accession"] == record.rname
        and transcript_strand == strand)

    matched_transcript = 0
    if transcript_usable:
        for junction in junctions:
            match = match_junction_to_annotation(
                annotation, record.rname,
                junction["intron_ref_start"], junction["intron_ref_end"])
            if expected_transcript in match["exact_transcripts"]:
                matched_transcript += 1

    n_differences = len(substitutions) + sum(d["length"] for d in indels)
    observed_positions = sorted(d["query_pos_orig"] for d in substitutions)

    if cds_len != reference["cds_len"]:
        failures.append(f"cds_len(observed={cds_len})")
    if covered != cds_len:
        failures.append(f"full_coverage(observed={covered}/{cds_len})")
    if clip_total != 0:
        failures.append(f"no_clipping(observed={clip_total})")
    if indels:
        failures.append(f"no_indels(observed={len(indels)})")
    if record.rname != reference["ref_name"]:
        failures.append(f"ref_name(observed={record.rname})")
    if strand != reference["strand"]:
        failures.append(f"strand(observed={strand})")
    if record.pos != reference["ref_start"] or item["walk"]["ref_end"] != reference["ref_end"]:
        failures.append(
            f"ref_interval(observed={record.pos}-{item['walk']['ref_end']})")
    if len(junctions) != reference["n_junctions"]:
        failures.append(f"n_junctions(observed={len(junctions)})")
    if not transcript_usable:
        failures.append(
            f"junction_transcript_on_alignment_strand({expected_transcript} "
            f"strand={transcript_strand or 'absent'}, alignment={record.rname} strand={strand})")
    if matched_transcript != reference["n_junctions"]:
        failures.append(
            f"junctions_match_{expected_transcript}"
            f"(observed={matched_transcript}/{reference['n_junctions']})")
    if n_differences != reference["expected_nt_differences"]:
        failures.append(f"nt_differences(observed={n_differences})")
    if observed_positions != sorted(reference["difference_positions"]):
        failures.append(f"difference_positions(observed={observed_positions or 'none'})")

    return {
        "query": query,
        "expected_cds_len": reference["cds_len"],
        "observed_cds_len": cds_len,
        "expected_ref_interval": f"{reference['ref_start']}-{reference['ref_end']}",
        "observed_ref_interval": f"{record.pos}-{item['walk']['ref_end']}",
        "expected_ref_name": reference["ref_name"],
        "observed_ref_name": record.rname,
        "expected_strand": reference["strand"],
        "observed_strand": strand,
        "expected_nt_differences": reference["expected_nt_differences"],
        "observed_nt_differences": n_differences,
        "expected_difference_positions": ",".join(
            str(p) for p in reference["difference_positions"]),
        "observed_difference_positions": ",".join(str(p) for p in observed_positions),
        "observed_indel_events": len(indels),
        "observed_clip_nt": clip_total,
        "union_covered_nt": covered,
        "union_coverage_frac": round(covered / cds_len, 6),
        "n_primary_records": len(primaries),
        "expected_n_junctions": reference["n_junctions"],
        "observed_n_junctions": len(junctions),
        "expected_junction_transcript": expected_transcript,
        "expected_junction_transcript_strand": transcript_strand or "absent",
        "n_junctions_matching_expected_transcript": matched_transcript,
        "genes_with_cds_overlap": ",".join(
            gene_label(annotation, g) for g in sorted(item["genes"])),
        "failed_requirements": ",".join(failures),
        "verdict": "AS_EXPECTED" if not failures else "FAILED",
    }


def build_controls(analysis: dict, annotation: Annotation) -> list[dict]:
    return [
        evaluate_control(query, reference, analysis["by_query"].get(query, []), annotation)
        for query, reference in CONTROL_REFERENCE.items()
    ]


def record_strand(record: SamRecord) -> str:
    return "-" if record.is_reverse else "+"


def crossing_junctions(item: dict, annotation: Annotation) -> list[dict]:
    """Every junction of this record that leads from GENE_UPSTREAM into GENE_DOWNSTREAM.

    This is the single shared transition criterion: it decides both the
    `CHAIN_SPANS_BOTH_ANNOTATED_GENES` verdict and the rows of
    `dsrnase3_transition.tsv`, so the two can never disagree. Both genes must
    lie on the record's own strand — a junction landing inside a gene annotated
    on the opposite strand is not a transition between those two models.

    Full query coverage is deliberately NOT part of this criterion: it is a
    separate requirement of the complete-chain label, so a partial record's
    transition is still reported in the table.
    """
    record = item["record"]
    strand = record_strand(record)
    upstream_gene = annotation.genes.get(GENE_UPSTREAM)
    downstream_gene = annotation.genes.get(GENE_DOWNSTREAM)
    if not upstream_gene or not downstream_gene:
        return []
    if upstream_gene["strand"] != strand or downstream_gene["strand"] != strand:
        return []
    found: list[dict] = []
    for junction_index, junction in enumerate(item["walk"]["junctions"]):
        start = junction["intron_ref_start"]
        end = junction["intron_ref_end"]
        before = set(genes_overlapping(annotation, record.rname, start - 1, start - 1))
        before |= set(genes_overlapping(annotation, record.rname, start - 1, start - 1,
                                        cds_only=False))
        after = set(genes_overlapping(annotation, record.rname, end + 1, end + 1))
        after |= set(genes_overlapping(annotation, record.rname, end + 1, end + 1,
                                       cds_only=False))
        if GENE_UPSTREAM in before and GENE_DOWNSTREAM in after:
            found.append({"junction_index": junction_index,
                          "upstream_genes": sorted(before),
                          "downstream_genes": sorted(after),
                          **junction})
    return found


def crossing_junction(item: dict, annotation: Annotation) -> dict | None:
    """The first junction satisfying the shared transition criterion, if any."""
    found = crossing_junctions(item, annotation)
    return found[0] if found else None


def single_model_correspondence(item: dict, annotation: Annotation) -> dict:
    """Transcripts whose CDS segments and introns correspond, in order, to this record.

    `full` requires exact ordered one-to-one equality of the record's coding
    blocks with the transcript's CDS segments and of its junctions with that
    transcript's CDS introns, on the same strand. `partial` collects transcripts
    that account for some but not all of them.
    """
    record = item["record"]
    strand = record_strand(record)
    blocks_ref = sorted((b["r_start"], b["r_end"]) for b in item["walk"]["blocks"])
    junction_keys = sorted((j["intron_ref_start"], j["intron_ref_end"])
                           for j in item["walk"]["junctions"])
    full: list[str] = []
    partial: list[str] = []

    for transcript_id, transcript in annotation.transcripts.items():
        if transcript["accession"] != record.rname or not transcript["CDS"]:
            continue
        if transcript["strand"] != strand:
            continue
        segments = sorted(transcript["CDS"])
        introns = sorted(annotation.introns_of(transcript_id, "CDS"))
        blocks_agree = blocks_ref == segments
        junctions_agree = junction_keys == introns
        if blocks_agree and junctions_agree:
            full.append(transcript_id)
        elif junction_keys and set(junction_keys) & set(introns):
            shared = len(set(junction_keys) & set(introns))
            partial.append(f"{transcript_id}({shared}/{len(junction_keys)} junctions)")
    return {"full": sorted(full), "partial": sorted(partial)}


def classify_dsrnase3(analysis: dict, annotation: Annotation) -> tuple[list[dict], list[dict]]:
    query = "dsRNase-3"
    items = analysis["by_query"].get(query, [])
    classification: list[dict] = []
    transition_rows: list[dict] = []

    cds_len = items[0]["cds_len"] if items else None
    chain = [i for i in items if i["record"].record_class in ("primary", "supplementary")]
    chain_union = union_length([iv for i in chain for iv in i["query_intervals"]]) if chain else 0

    complete_single_model: list[str] = []
    partial_single_model: list[str] = []
    complete_crossing: list[str] = []
    partial_crossing: list[str] = []
    full_coverage_records: list[dict] = []

    for item in items:
        record = item["record"]
        covered = union_length(item["query_intervals"])
        covers_all = cds_len is not None and covered == cds_len
        if covers_all:
            full_coverage_records.append(item)
        label = f"record {item['index']} ({record.record_class}, strand {record_strand(record)})"

        correspondence = single_model_correspondence(item, annotation)
        if correspondence["full"] and covers_all:
            complete_single_model.append(
                f"{label} covers all {cds_len} nt, blocks and junctions ordered one-to-one with "
                + "/".join(correspondence["full"]))
        elif correspondence["full"]:
            partial_single_model.append(
                f"{label} matches " + "/".join(correspondence["full"])
                + f" but covers only {covered}/{cds_len} nt")
        elif correspondence["partial"]:
            partial_single_model.append(
                f"{label} covers {covered}/{cds_len} nt, partial junction overlap with "
                + "/".join(correspondence["partial"]))

        crossing = crossing_junction(item, annotation)
        if crossing and covers_all:
            complete_crossing.append(
                f"{label} covers all {cds_len} nt with junction {crossing['junction_index']} "
                f"({crossing['intron_ref_start']}-{crossing['intron_ref_end']}, "
                f"{crossing['intron_len']} nt) leading from {GENE_UPSTREAM} into {GENE_DOWNSTREAM}")
        elif crossing:
            partial_crossing.append(
                f"{label} has a {GENE_UPSTREAM}->{GENE_DOWNSTREAM} junction but covers only "
                f"{covered}/{cds_len} nt")
        elif GENE_UPSTREAM in item["genes"] and GENE_DOWNSTREAM in item["genes"]:
            partial_crossing.append(
                f"{label} has CDS overlap in both genes but no identifiable junction between them "
                f"on strand {record_strand(record)}")

    classification.append({
        "outcome_key": "CHAIN_MATCHES_SINGLE_ANNOTATED_MODEL",
        "status": "OBSERVED" if complete_single_model else "NOT_OBSERVED",
        "detail": "; ".join(complete_single_model) if complete_single_model else
                  "no single record covers the whole query with its coding blocks and junctions "
                  "corresponding, in order, to one annotated transcript on the same strand",
    })
    classification.append({
        "outcome_key": "CHAIN_SPANS_BOTH_ANNOTATED_GENES",
        "status": "OBSERVED" if complete_crossing else "NOT_OBSERVED",
        "detail": "; ".join(complete_crossing) if complete_crossing else
                  f"no single record covers the whole query with an identifiable junction from "
                  f"{GENE_UPSTREAM} into {GENE_DOWNSTREAM} on the same strand",
    })
    classification.append({
        "outcome_key": "COVERAGE_ONLY_BY_SEPARATE_ALIGNMENTS",
        "status": "OBSERVED" if (not full_coverage_records and chain_union == cds_len)
                  else "NOT_OBSERVED",
        "detail": (
            f"no single record covers all {cds_len} nt; the primary chain of {len(chain)} records "
            f"covers {chain_union} nt as a union"
            if not full_coverage_records and chain_union == cds_len else
            f"{len(full_coverage_records)} record(s) cover all {cds_len} nt on their own; "
            f"primary-chain union is {chain_union} nt"),
    })
    classification.append({
        "outcome_key": "PARTIAL_CORRESPONDENCE_SINGLE_ANNOTATED_MODEL",
        "status": "OBSERVED" if partial_single_model else "NOT_OBSERVED",
        "detail": "; ".join(partial_single_model) if partial_single_model else "none",
    })
    classification.append({
        "outcome_key": "PARTIAL_CORRESPONDENCE_SPANNING_BOTH_GENES",
        "status": "OBSERVED" if partial_crossing else "NOT_OBSERVED",
        "detail": "; ".join(partial_crossing) if partial_crossing else "none",
    })

    # The transition table is built from the same shared criterion as the
    # verdict above, so a junction appears here if and only if it counts there.
    for item in items:
        record = item["record"]
        for junction in crossing_junctions(item, annotation):
            junction_index = junction["junction_index"]
            intron_start = junction["intron_ref_start"]
            intron_end = junction["intron_ref_end"]
            ref_seq_name = record.rname
            match = match_junction_to_annotation(annotation, ref_seq_name, intron_start, intron_end)
            nearest = match["nearest"] or {}
            upstream_q = junction["query_pos_upstream_orig"]
            motif_row = next(
                (r for r in analysis["junction_rows"]
                 if r["record_index"] == item["index"] and r["junction_index"] == junction_index),
                {})
            transition_rows.append({
                "query": query,
                "record_index": item["index"],
                "record_class": record.record_class,
                "strand": "-" if record.is_reverse else "+",
                "junction_index": junction_index,
                "ref_name": ref_seq_name,
                "intron_ref_start": intron_start,
                "intron_ref_end": intron_end,
                "jump_len_nt": junction["intron_len"],
                "query_pos_upstream_orig": upstream_q,
                "query_pos_downstream_orig": junction["query_pos_downstream_orig"],
                "codon_phase_after_upstream": junction["codon_phase_after_upstream"],
                "in_frame_at_codon_boundary": junction["codon_phase_after_upstream"] == 0,
                "motif_forward_genome": motif_row.get("motif_forward_genome", ""),
                "motif_transcript_oriented": motif_row.get("motif_transcript_oriented", ""),
                "motif_is_canonical_gtag": motif_row.get("motif_is_canonical_gtag", ""),
                "upstream_gene_context": ",".join(
                    gene_label(annotation, g) for g in junction["upstream_genes"]),
                "downstream_gene_context": ",".join(
                    gene_label(annotation, g) for g in junction["downstream_genes"]),
                "annotated_exact_match_transcripts": ",".join(match["exact_transcripts"]),
                "nearest_annotated_transcript": nearest.get("transcript_id", ""),
                "nearest_d_start_nt": nearest.get("d_start", ""),
                "nearest_d_end_nt": nearest.get("d_end", ""),
                "historical_candidate_query_pos": HISTORICAL_TRANSITION_QUERY_POS,
                "delta_query_pos_vs_historical": upstream_q - HISTORICAL_TRANSITION_QUERY_POS,
                "historical_jump_recorded_nt": HISTORICAL_TRANSITION_JUMP_RECORDED_NT,
                "delta_jump_vs_recorded_nt": junction["intron_len"] - HISTORICAL_TRANSITION_JUMP_RECORDED_NT,
                "historical_jump_as_stated_nt": HISTORICAL_TRANSITION_JUMP_AS_STATED_NT,
                "delta_jump_vs_stated_nt": junction["intron_len"] - HISTORICAL_TRANSITION_JUMP_AS_STATED_NT,
            })

    return classification, transition_rows


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def run_check(args: argparse.Namespace, root: Path, out_dir: Path) -> int:
    inputs = verify_inputs(root)

    queries = read_fasta(inputs["cds_queries"])
    print(f"[queries] {', '.join(f'{k}={len(v)} nt' for k, v in queries.items())}", file=sys.stderr)

    sam_path = None
    log_path = None

    with tempfile.TemporaryDirectory(prefix="nb01-splice-") as tmp:
        tmp_dir = Path(tmp)
        if args.sam:
            # Re-analysis of a saved alignment: no aligner is run, and the SAM
            # the tables come from is referenced where it already lives.
            sam_path = Path(args.sam).resolve()
            if not sam_path.is_file():
                raise VerificationError(f"saved SAM not found: {sam_path}")
            sam_header, _ = parse_sam(sam_path.read_text(encoding="utf-8"))
            sam_version, sam_command = pg_version_from_header(sam_header)
            if sam_version != MINIMAP2_EXPECTED_VERSION:
                raise VerificationError(
                    f"saved SAM was written by minimap2 {sam_version!r}, "
                    f"expected {MINIMAP2_EXPECTED_VERSION}")
            print(f"[reanalysis] saved SAM from minimap2 {sam_version}", file=sys.stderr)
            minimap2_run = {
                "version": sam_version,
                "command": sam_command.split() if sam_command else [],
                "executed_in_this_run": False,
            }
            decompressed_hash = None
        else:
            raw_dir = out_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            sam_path = raw_dir / "minimap2_splice_hq.sam"
            log_path = raw_dir / "minimap2.stderr.log"
            genome_plain = tmp_dir / "genome.fna"
            print(f"[genome] decompressing to {genome_plain}", file=sys.stderr)
            with gzip.open(inputs["genome_fna_gz"], "rb") as src, genome_plain.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1 << 22)
            decompressed_hash = sha256_file(genome_plain)
            declared_decompressed = DECLARED_INPUTS["genome_fna_gz"]["sha256_decompressed"]
            if decompressed_hash != declared_decompressed:
                raise VerificationError(
                    f"decompressed genome sha256 mismatch: declared {declared_decompressed}, "
                    f"observed {decompressed_hash}")
            print(f"[verify] genome decompressed: sha256 {decompressed_hash} OK", file=sys.stderr)
            minimap2_run = run_minimap2(genome_plain, inputs["cds_queries"], sam_path, log_path)
            minimap2_run["executed_in_this_run"] = True

        sam_text = sam_path.read_text(encoding="utf-8")
        header, records = parse_sam(sam_text)
        print(f"[sam] {len(records)} alignment records, {len(header)} header lines", file=sys.stderr)

        used_accessions = {r.rname for r in records if not r.is_unmapped}
        genome_seqs = read_fasta(inputs["genome_fna_gz"], wanted=used_accessions)
        missing = used_accessions - set(genome_seqs)
        if missing:
            raise VerificationError(f"reference sequences not found in the genome FASTA: {missing}")

    annotation = load_annotation(inputs["gff3_gz"], used_accessions)
    print(f"[gff3] {len(annotation.genes)} genes, {len(annotation.transcripts)} transcripts "
          f"on {sorted(used_accessions)}", file=sys.stderr)

    analysis = analyse(records, queries, genome_seqs, annotation)
    controls = build_controls(analysis, annotation)
    classification, transition_rows = classify_dsrnase3(analysis, annotation)
    historical = load_historical_junctions(inputs["loci_tsv"])
    reconciliation = build_junction_reconciliation(analysis, historical)

    record_columns = [
        "query", "cds_len_fasta", "record_index", "flag", "record_class", "mapq",
        "ref_name", "ref_start", "ref_end", "ref_span_nt", "strand",
        "query_start_orig", "query_end_orig", "query_span_orig_nt",
        "n_blocks", "n_junctions",
        "query_aligned_nt", "query_insertion_nt",
        "query_clip_left_nt", "query_clip_right_nt",
        "clip_left_soft_nt", "clip_left_hard_nt", "clip_right_soft_nt", "clip_right_hard_nt",
        "n_match_nt", "n_mismatch_nt", "n_m_ambiguous_nt",
        "n_ins_events", "n_ins_nt", "n_del_events", "n_del_nt", "nm_tag",
        "coverage_aligned_frac",
        "split_group", "group_n_records", "group_union_covered_nt", "group_union_coverage_frac",
        "genes_with_cds_overlap", "n_substitutions_observed", "substitution_query_positions",
    ]
    junction_columns = [
        "query", "record_index", "record_class", "strand", "junction_index", "ref_name",
        "intron_ref_start", "intron_ref_end", "intron_len_nt",
        "query_pos_upstream_orig", "query_pos_downstream_orig", "codon_phase_after_upstream",
        "motif_forward_genome", "motif_transcript_oriented", "motif_is_canonical_gtag",
        "annotated_exact_match_transcripts", "annotated_exact_match_genes",
        "nearest_annotated_transcript", "nearest_annotated_gene",
        "nearest_intron_ref_start", "nearest_intron_ref_end",
        "nearest_d_start_nt", "nearest_d_end_nt",
    ]
    block_columns = [
        "query", "record_index", "record_class", "strand", "block_index",
        "query_start_orig", "query_end_orig", "query_len_nt", "query_aligned_nt",
        "ref_name", "ref_start", "ref_end", "ref_len_nt",
        "n_match_nt", "n_mismatch_nt", "n_ins_nt", "n_del_nt", "genes_with_cds_overlap",
    ]
    control_columns = [
        "query", "expected_cds_len", "observed_cds_len",
        "expected_ref_name", "observed_ref_name",
        "expected_strand", "observed_strand",
        "expected_ref_interval", "observed_ref_interval",
        "expected_n_junctions", "observed_n_junctions",
        "expected_junction_transcript", "expected_junction_transcript_strand",
        "n_junctions_matching_expected_transcript",
        "expected_nt_differences", "observed_nt_differences",
        "expected_difference_positions", "observed_difference_positions",
        "observed_indel_events", "observed_clip_nt",
        "union_covered_nt", "union_coverage_frac", "n_primary_records",
        "genes_with_cds_overlap", "failed_requirements", "verdict",
    ]
    transition_columns = [
        "query", "record_index", "record_class", "strand", "junction_index", "ref_name",
        "intron_ref_start", "intron_ref_end", "jump_len_nt",
        "query_pos_upstream_orig", "query_pos_downstream_orig",
        "codon_phase_after_upstream", "in_frame_at_codon_boundary",
        "motif_forward_genome", "motif_transcript_oriented", "motif_is_canonical_gtag",
        "upstream_gene_context", "downstream_gene_context",
        "annotated_exact_match_transcripts", "nearest_annotated_transcript",
        "nearest_d_start_nt", "nearest_d_end_nt",
        "historical_candidate_query_pos", "delta_query_pos_vs_historical",
        "historical_jump_recorded_nt", "delta_jump_vs_recorded_nt",
        "historical_jump_as_stated_nt", "delta_jump_vs_stated_nt",
    ]

    outputs = {
        "per_record.tsv": (record_columns, analysis["record_rows"]),
        "per_junction.tsv": (junction_columns, analysis["junction_rows"]),
        "per_block.tsv": (block_columns, analysis["block_rows"]),
        "controls.tsv": (control_columns, controls),
        "dsrnase3_chain_classification.tsv": (["outcome_key", "status", "detail"], classification),
        "dsrnase3_transition.tsv": (transition_columns, transition_rows),
        "junction_vs_historical.tsv": ([
            "query", "junction_index",
            "historical_intron_size_nt", "historical_query_junction_offset_nt",
            "historical_plus_overlap_nt", "splice_aware_intron_len_nt",
            "difference_nt", "agrees",
        ], reconciliation),
    }
    for name, (columns, rows) in outputs.items():
        write_tsv(out_dir / name, columns, rows)
        print(f"[write] {name}: {len(rows)} rows", file=sys.stderr)

    sam_text_no_pg = "\n".join(
        line for line in sam_path.read_text(encoding="utf-8").splitlines()
        if not line.startswith("@PG"))
    manifest = {
        "question": "which chains of genomic alignment explain the published dsRNase-3 CDS, "
                    "in particular across the ENSCHMG00000003138 / ube2w transition",
        "mode": "reanalysis_of_saved_alignment" if args.sam else "alignment_and_analysis",
        "source_alignment": {
            "path": str(sam_path.relative_to(root)) if sam_path.is_relative_to(root)
                    else str(sam_path),
            "generated_by_minimap2_version": minimap2_run["version"],
            "produced_in_this_run": minimap2_run.get("executed_in_this_run", False),
            "sha256": sha256_file(sam_path),
            "sha256_excluding_pg_line": sha256_text(sam_text_no_pg + "\n"),
            "note": "the @PG line embeds the temporary genome path, so the whole-file sha256 "
                    "is run-dependent while sha256_excluding_pg_line is not",
        },
        "minimap2": minimap2_run,
        "python": sys.version.split()[0],
        "declared_inputs": {
            role: {
                "path": declaration["path"],
                "declared_sha256": declaration["sha256"],
                "observed_sha256": sha256_file(inputs[role]),
                "role": declaration["role"],
            }
            for role, declaration in DECLARED_INPUTS.items()
        },
        "genome_decompressed_sha256": decompressed_hash,
        "annotation_used_after_alignment_only": True,
        "query_lengths_nt": {name: len(seq) for name, seq in queries.items()},
        "n_sam_records": len(records),
        "record_classes": {
            cls: sum(1 for r in records if r.record_class == cls)
            for cls in sorted({r.record_class for r in records})
        },
        "outputs": {
            name: sha256_file(out_dir / name) for name in outputs
        },
        "raw_outputs": {
            "raw/minimap2.stderr.log": sha256_file(log_path)
            if log_path is not None and log_path.is_file() else None,
        },
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (out_dir / "manifest.json").write_text(manifest_text, encoding="utf-8", newline="\n")
    print(f"[write] manifest.json: sha256 {sha256_text(manifest_text)}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--sam", default=None,
                        help="re-analyse this saved SAM instead of running minimap2")
    parser.add_argument("--out-subdir", default=OUTPUT_SUBDIR,
                        help="output directory, relative to the repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    # The destination is claimed first: a refusal must happen before any read
    # of a 281 MB input and before any file is written. The claim is held for
    # the whole run and released only after the last write.
    with reserve_output_dir(root / args.out_subdir) as reservation:
        print(f"[output] {reservation.out_dir} (reserved)", file=sys.stderr)
        return run_check(args, root, reservation.out_dir)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VerificationError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(2)
