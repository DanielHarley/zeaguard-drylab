"""NB01 dsRNase-2 identity investigation: reusable sequence, search and comparison logic.

Coordinate convention (declared once, used by every public function and output table):
internal slicing is Python 0-based half-open; every reported coordinate is 1-based
inclusive on the FORWARD strand of the sequence being described, with strand reported
separately. Use :func:`to_one_based` / :func:`to_zero_based` for the conversion.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

from zeaguard.nb01_identity import reverse_complement

CODON_TABLE = dict(
    zip(
        (a + b + c for a in "TCAG" for b in "TCAG" for c in "TCAG"),
        "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG",
    )
)
STOP = "*"
UNAMBIGUOUS_DNA = frozenset("ACGT")

BLAST_OUTFMT_FIELDS = (
    "qseqid sseqid pident length qlen slen qstart qend sstart send sstrand "
    "evalue bitscore mismatch gapopen gaps qcovs btop"
).split()
TBLASTN_OUTFMT_FIELDS = BLAST_OUTFMT_FIELDS[:11] + ["sframe"] + BLAST_OUTFMT_FIELDS[11:]


# --------------------------------------------------------------------------- basics
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def to_one_based(start0: int, end0_exclusive: int) -> tuple[int, int]:
    """0-based half-open ``[start0, end0)`` -> 1-based inclusive ``(start, end)``."""
    if end0_exclusive <= start0:
        raise ValueError("empty interval")
    return start0 + 1, end0_exclusive


def to_zero_based(start1: int, end1_inclusive: int) -> tuple[int, int]:
    """1-based inclusive ``(start, end)`` -> 0-based half-open ``(start0, end0)``."""
    if end1_inclusive < start1 or start1 < 1:
        raise ValueError("invalid 1-based interval")
    return start1 - 1, end1_inclusive


IUPAC_EXPANSION = {
    "A": "A", "C": "C", "G": "G", "T": "T", "R": "AG", "Y": "CT", "S": "CG", "W": "AT", "K": "GT",
    "M": "AC", "B": "CGT", "D": "AGT", "H": "ACT", "V": "ACG", "N": "ACGT",
}
_AA_CACHE: dict[str, frozenset[str]] = {}


def codon_amino_acids(codon: str) -> frozenset[str]:
    """All amino acids (``*`` = stop) a possibly IUPAC-ambiguous codon can encode."""
    codon = codon.upper().replace("U", "T")
    cached = _AA_CACHE.get(codon)
    if cached is None:
        if len(codon) != 3 or any(base not in IUPAC_EXPANSION for base in codon):
            cached = frozenset("X")
        else:
            cached = frozenset(
                CODON_TABLE[a + b + c]
                for a in IUPAC_EXPANSION[codon[0]]
                for b in IUPAC_EXPANSION[codon[1]]
                for c in IUPAC_EXPANSION[codon[2]]
            )
        _AA_CACHE[codon] = cached
    return cached


def translate(nucleotides: str, to_stop: bool = False) -> str:
    """Standard-code translation.

    A codon containing IUPAC ambiguity codes is translated to its amino acid when every
    resolution encodes the same residue (e.g. ``CTN`` -> ``L``, as BLAST does) and to
    ``X`` otherwise; it is never silently resolved to one arbitrary base.
    """
    seq = nucleotides.upper().replace("U", "T")
    protein: list[str] = []
    for index in range(0, len(seq) - len(seq) % 3, 3):
        options = codon_amino_acids(seq[index : index + 3])
        amino = next(iter(options)) if len(options) == 1 else "X"
        if to_stop and amino == STOP:
            break
        protein.append(amino)
    return "".join(protein)


def count_ambiguous(nucleotides: str) -> int:
    return sum(base not in UNAMBIGUOUS_DNA for base in nucleotides.upper())


# --------------------------------------------------------------------------- FASTA
def read_fasta_text(text: str) -> list[tuple[str, str, str]]:
    """Generic FASTA reader (any alphabet): returns ``(identifier, header, sequence)``."""
    records: list[tuple[str, str, str]] = []
    header: str | None = None
    parts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header.split()[0], header, "".join(parts)))
            header, parts = line[1:].strip(), []
        else:
            if header is None:
                raise ValueError("sequence before first FASTA header")
            parts.append("".join(line.split()))
    if header is not None:
        records.append((header.split()[0], header, "".join(parts)))
    ids = [record[0] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate FASTA identifiers")
    return records


def format_fasta(records: Iterable[tuple[str, str]], width: int = 70) -> str:
    """``(header, sequence)`` pairs -> FASTA text with LF line endings."""
    lines: list[str] = []
    for header, sequence in records:
        lines.append(f">{header}")
        lines.extend(sequence[i : i + width] for i in range(0, len(sequence), width))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- Supplement S1
_S1_HEADER = re.compile(r"^>(\S+)\s.*\((Dmai-dsRNase-\d)\)")


def parse_s1_text(text: str) -> dict[str, dict[str, object]]:
    """Parse the text layer of Supplementary File S1 (pages with the Trinity records).

    Returns ``{published_name: {"protein": (id, seq), "transcript": (id, seq)}}``.
    Protein records are those whose identifier ends in ``.pN``; the transcript header
    wraps over two lines (``path=[...]``) and is rejoined before parsing.
    """
    lines = [line.strip() for line in text.splitlines()]
    result: dict[str, dict[str, object]] = defaultdict(dict)
    current: tuple[str, str, str] | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is None:
            return
        identifier, name, kind = current
        result[name][kind] = (identifier, "".join(buffer).upper())

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(">"):
            flush()
            header = line
            while "(Dmai-dsRNase-" not in header and index + 1 < len(lines):
                index += 1
                header += " " + lines[index]
            match = _S1_HEADER.match(header)
            if not match:
                raise ValueError(f"unparseable S1 header: {header}")
            identifier, name = match.groups()
            kind = "protein" if re.search(r"\.p\d+$", identifier) else "transcript"
            current, buffer = (identifier, name, kind), []
        elif current is not None and not line.startswith("====="):
            if re.fullmatch(r"[A-Za-z*]+", line):
                buffer.append(line)
        index += 1
    flush()
    return dict(result)


# --------------------------------------------------------------------------- ORFs
@dataclass(frozen=True)
class Orf:
    """A stop-delimited reading segment (maximal open frame) on one strand.

    ``o_start/o_end`` are 0-based half-open on the strand-oriented sequence (stop codon
    included when ``has_stop``); ``start/end`` are 1-based inclusive on the forward
    strand of the transcript.
    """

    strand: str
    frame: int
    start: int
    end: int
    o_start: int
    o_end: int
    has_stop: bool
    begins_after_stop: bool
    protein: str  # translation of the segment, stop excluded

    @property
    def first_met(self) -> int:
        return self.protein.find("M")


def find_orfs(sequence: str, min_aa: int = 30) -> list[Orf]:
    """All stop-delimited segments of at least ``min_aa`` residues in the six frames."""
    seq = sequence.upper()
    length = len(seq)
    orfs: list[Orf] = []
    for strand in ("+", "-"):
        oriented = seq if strand == "+" else reverse_complement(seq)
        for frame in (0, 1, 2):
            protein = translate(oriented[frame:])
            aa_start = 0
            for aa_index, amino in enumerate(protein + STOP):
                if amino != STOP:
                    continue
                segment = protein[aa_start:aa_index]
                has_stop = aa_index < len(protein)
                if len(segment) >= min_aa:
                    o_start = frame + 3 * aa_start
                    o_end = frame + 3 * (aa_index + (1 if has_stop else 0))
                    if strand == "+":
                        start, end = to_one_based(o_start, o_end)
                    else:
                        start, end = to_one_based(length - o_end, length - o_start)
                    orfs.append(
                        Orf(
                            strand,
                            frame + 1,
                            start,
                            end,
                            o_start,
                            o_end,
                            has_stop,
                            aa_start > 0,
                            segment,
                        )
                    )
                aa_start = aa_index + 1
    return sorted(orfs, key=lambda orf: (orf.strand, orf.frame, orf.o_start))


def orf_sequence(sequence: str, orf: Orf) -> str:
    """Coding-orientation nucleotides of ``orf`` (stop codon included when present)."""
    oriented = sequence.upper() if orf.strand == "+" else reverse_complement(sequence)
    return oriented[orf.o_start : orf.o_end]


def locate_protein(cdna: str, protein: str) -> list[dict[str, object]]:
    """Exact placement of ``protein`` in the six-frame translation of ``cdna``.

    Reports every placement (normally one) with 1-based inclusive forward coordinates
    that include the stop codon when it follows the protein in frame.
    """
    seq = cdna.upper()
    hits: list[dict[str, object]] = []
    for strand in ("+", "-"):
        oriented = seq if strand == "+" else reverse_complement(seq)
        for frame in (0, 1, 2):
            translated = translate(oriented[frame:])
            at = translated.find(protein)
            while at != -1:
                o_start = frame + 3 * at
                o_end = o_start + 3 * len(protein)
                stop_present = translate(oriented[o_end : o_end + 3]) == STOP
                if stop_present:
                    o_end += 3
                if strand == "+":
                    start, end = to_one_based(o_start, o_end)
                else:
                    start, end = to_one_based(len(seq) - o_end, len(seq) - o_start)
                hits.append(
                    {
                        "strand": strand,
                        "frame": frame + 1,
                        "start": start,
                        "end": end,
                        "stop_present": stop_present,
                        "start_codon": oriented[o_start : o_start + 3],
                        "upstream_nt": o_start,
                        "downstream_nt": len(seq) - o_end,
                        "cds": oriented[o_start:o_end],
                    }
                )
                at = translated.find(protein, at + 1)
    return hits


# --------------------------------------------------------------------------- BLAST HSPs
@dataclass(frozen=True)
class Hsp:
    query: str
    subject: str
    pident: float
    length: int
    qlen: int
    slen: int
    qstart: int
    qend: int
    sstart: int
    send: int
    strand: str  # "plus" | "minus" (subject orientation)
    evalue: float
    bitscore: float
    mismatch: int
    gapopen: int
    gaps: int
    qcovs: float
    btop: str
    sframe: int | None = None

    @property
    def query_interval(self) -> tuple[int, int]:
        """1-based inclusive, ascending (BLAST reports queries ascending already)."""
        return min(self.qstart, self.qend), max(self.qstart, self.qend)

    @property
    def subject_interval(self) -> tuple[int, int]:
        """1-based inclusive, ascending; orientation lives in ``strand``."""
        return min(self.sstart, self.send), max(self.sstart, self.send)


def parse_hsp_table(text: str, fields: Sequence[str] = BLAST_OUTFMT_FIELDS) -> list[Hsp]:
    hsps: list[Hsp] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.rstrip("\n").split("\t")
        if len(cells) != len(fields):
            raise ValueError(f"HSP line {line_no}: {len(cells)} fields, expected {len(fields)}")
        row = dict(zip(fields, cells))
        hsps.append(
            Hsp(
                row["qseqid"],
                row["sseqid"],
                float(row["pident"]),
                int(row["length"]),
                int(row["qlen"]),
                int(row["slen"]),
                int(row["qstart"]),
                int(row["qend"]),
                int(row["sstart"]),
                int(row["send"]),
                row["sstrand"],
                float(row["evalue"]),
                float(row["bitscore"]),
                int(row["mismatch"]),
                int(row["gapopen"]),
                int(row["gaps"]),
                float(row["qcovs"]),
                row["btop"],
                int(row["sframe"]) if "sframe" in row else None,
            )
        )
    return hsps


def merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Union of 1-based inclusive intervals; abutting intervals (e.g. 1-5, 6-9) merge."""
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def union_length(intervals: Iterable[tuple[int, int]]) -> int:
    return sum(end - start + 1 for start, end in merge_intervals(intervals))


def summarize_hsps(hsps: Sequence[Hsp]) -> list[dict[str, object]]:
    """Non-redundant coverage per ``(query, subject, strand)``; strands never merge."""
    groups: dict[tuple[str, str, str], list[Hsp]] = defaultdict(list)
    for hsp in hsps:
        groups[(hsp.query, hsp.subject, hsp.strand)].append(hsp)
    rows: list[dict[str, object]] = []
    for (query, subject, strand), members in sorted(groups.items()):
        q_union = merge_intervals(h.query_interval for h in members)
        s_union = merge_intervals(h.subject_interval for h in members)
        covered = sum(end - start + 1 for start, end in q_union)
        rows.append(
            {
                "query": query,
                "subject": subject,
                "strand": strand,
                "n_hsps": len(members),
                "qlen": members[0].qlen,
                "slen": members[0].slen,
                "query_union_covered": covered,
                "query_union_coverage_pct": round(100 * covered / members[0].qlen, 3),
                "query_union_intervals": ";".join(f"{a}-{b}" for a, b in q_union),
                "subject_span_start": s_union[0][0],
                "subject_span_end": s_union[-1][1],
                "subject_union_intervals": ";".join(f"{a}-{b}" for a, b in s_union),
                "best_bitscore": max(h.bitscore for h in members),
                "best_evalue": min(h.evalue for h in members),
                "best_pident": max(h.pident for h in members),
            }
        )
    return rows


def parse_btop(btop: str) -> list[tuple[str, str, str]]:
    """BTOP string -> per-column ``(op, query_char, subject_char)``.

    ``op`` is ``=`` (match run, chars ``""``), ``X`` (substitution) or ``I``/``D`` for
    a gap in the subject / query respectively.
    """
    columns: list[tuple[str, str, str]] = []
    for count, pair in re.findall(r"(\d+)|([A-Za-z*-]{2})", btop):
        if count:
            columns.extend([("=", "", "")] * int(count))
        else:
            q, s = pair
            columns.append(("I" if s == "-" else "D" if q == "-" else "X", q, s))
    return columns


# --------------------------------------------------------------------------- alignment
NEG = -(10**9)
NUC_SCORES = {"match": 2, "mismatch": -3, "gap_open": 5, "gap_extend": 2}

_BLOSUM62_ROWS = """
   A  R  N  D  C  Q  E  G  H  I  L  K  M  F  P  S  T  W  Y  V  B  Z  X  *
A  4 -1 -2 -2  0 -1 -1  0 -2 -1 -1 -1 -1 -2 -1  1  0 -3 -2  0 -2 -1  0 -4
R -1  5  0 -2 -3  1  0 -2  0 -3 -2  2 -1 -3 -2 -1 -1 -3 -2 -3 -1  0 -1 -4
N -2  0  6  1 -3  0  0  0  1 -3 -3  0 -2 -3 -2  1  0 -4 -2 -3  3  0 -1 -4
D -2 -2  1  6 -3  0  2 -1 -1 -3 -4 -1 -3 -3 -1  0 -1 -4 -3 -3  4  1 -1 -4
C  0 -3 -3 -3  9 -3 -4 -3 -3 -1 -1 -3 -1 -2 -3 -1 -1 -2 -2 -1 -3 -3 -2 -4
Q -1  1  0  0 -3  5  2 -2  0 -3 -2  1  0 -3 -1  0 -1 -2 -1 -2  0  3 -1 -4
E -1  0  0  2 -4  2  5 -2  0 -3 -3  1 -2 -3 -1  0 -1 -3 -2 -2  1  4 -1 -4
G  0 -2  0 -1 -3 -2 -2  6 -2 -4 -4 -2 -3 -3 -2  0 -2 -2 -3 -3 -1 -2 -1 -4
H -2  0  1 -1 -3  0  0 -2  8 -3 -3 -1 -2 -1 -2 -1 -2 -2  2 -3  0  0 -1 -4
I -1 -3 -3 -3 -1 -3 -3 -4 -3  4  2 -3  1  0 -3 -2 -1 -3 -1  3 -3 -3 -1 -4
L -1 -2 -3 -4 -1 -2 -3 -4 -3  2  4 -2  2  0 -3 -2 -1 -2 -1  1 -4 -3 -1 -4
K -1  2  0 -1 -3  1  1 -2 -1 -3 -2  5 -1 -3 -1  0 -1 -3 -2 -2  0  1 -1 -4
M -1 -1 -2 -3 -1  0 -2 -3 -2  1  2 -1  5  0 -2 -1 -1 -1 -1  1 -3 -1 -1 -4
F -2 -3 -3 -3 -2 -3 -3 -3 -1  0  0 -3  0  6 -4 -2 -2  1  3 -1 -3 -3 -1 -4
P -1 -2 -2 -1 -3 -1 -1 -2 -2 -3 -3 -1 -2 -4  7 -1 -1 -4 -3 -2 -2 -1 -2 -4
S  1 -1  1  0 -1  0  0  0 -1 -2 -2  0 -1 -2 -1  4  1 -3 -2 -2  0  0  0 -4
T  0 -1  0 -1 -1 -1 -1 -2 -2 -1 -1 -1 -1 -2 -1  1  5 -2 -2  0 -1 -1  0 -4
W -3 -3 -4 -4 -2 -2 -3 -2 -2 -3 -2 -3 -1  1 -4 -3 -2 11  2 -3 -4 -3 -2 -4
Y -2 -2 -2 -3 -2 -1 -2 -3  2 -1 -1 -2 -1  3 -3 -2 -2  2  7 -1 -3 -2 -1 -4
V  0 -3 -3 -3 -1 -2 -2 -3 -3  3  1 -2  1 -1 -2 -2  0 -3 -1  4 -3 -2 -1 -4
B -2 -1  3  4 -3  0  1 -1  0 -3 -4  0 -3 -3 -2  0 -1 -4 -3 -3  4  1 -1 -4
Z -1  0  0  1 -3  3  4 -2  0 -3 -3  1 -1 -3 -1  0 -1 -3 -2 -2  1  4 -1 -4
X  0 -1 -1 -1 -2 -1 -1 -1 -1 -1 -1 -1 -1 -1 -2  0  0 -2 -1 -1 -1 -1 -1 -4
* -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4 -4  1
"""


def _load_blosum62() -> dict[tuple[str, str], int]:
    rows = [line.split() for line in _BLOSUM62_ROWS.strip().splitlines()]
    header = rows[0]
    return {(r[0], header[j]): int(v) for r in rows[1:] for j, v in enumerate(r[1:])}


BLOSUM62 = _load_blosum62()


@dataclass(frozen=True)
class Alignment:
    a_aligned: str
    b_aligned: str
    a_start: int  # 0-based index of first aligned residue of a
    a_end: int  # 0-based exclusive
    b_start: int
    b_end: int
    score: int
    mode: str


def align(
    a: str,
    b: str,
    mode: str = "semiglobal",
    matrix: dict[tuple[str, str], int] | None = None,
    nuc: dict[str, int] | None = None,
    gap_open: int | None = None,
    gap_extend: int | None = None,
) -> Alignment:
    """Deterministic affine-gap (Gotoh) pairwise alignment for the small sequences of NB01.

    ``mode``: ``global``; ``semiglobal`` (free end gaps in both: overhangs are not
    penalised, used for transcript vs transcript); ``local``. Protein scoring when
    ``matrix`` is given (default gap 11/1), nucleotide scoring otherwise
    (match 2, mismatch -3, gap 5+2k). Ties prefer match/mismatch, then gap in ``b``.
    """
    if mode not in {"global", "semiglobal", "local"}:
        raise ValueError(mode)
    if matrix is not None:
        go, ge = (11 if gap_open is None else gap_open), (1 if gap_extend is None else gap_extend)

        def score(x: str, y: str) -> int:
            return matrix.get((x, y), matrix[("X", "X")])

    else:
        params = nuc or NUC_SCORES
        go = params["gap_open"] if gap_open is None else gap_open
        ge = params["gap_extend"] if gap_extend is None else gap_extend

        def score(x: str, y: str) -> int:
            if x not in UNAMBIGUOUS_DNA or y not in UNAMBIGUOUS_DNA:
                return 0
            return params["match"] if x == y else params["mismatch"]

    n, m = len(a), len(b)
    width = m + 1
    size = (n + 1) * width
    M = [NEG] * size
    X = [NEG] * size  # a[i-1] against a gap in b
    Y = [NEG] * size  # b[j-1] against a gap in a
    pm = bytearray(size)  # predecessor state: 0=M 1=X 2=Y 3=start
    px = bytearray(size)
    py = bytearray(size)
    local = mode == "local"
    free_ends = mode in {"semiglobal", "local"}
    M[0] = 0
    pm[0] = 3
    for i in range(1, n + 1):
        if free_ends:
            M[i * width] = 0
            pm[i * width] = 3
        else:
            X[i * width] = -(go + ge * i)
            px[i * width] = 1 if i > 1 else 0
    for j in range(1, m + 1):
        if free_ends:
            M[j] = 0
            pm[j] = 3
        else:
            Y[j] = -(go + ge * j)
            py[j] = 2 if j > 1 else 0
    gap_first = go + ge
    best = (NEG, 0, 0, 0)
    half_neg = NEG // 2
    for i in range(1, n + 1):
        ai = a[i - 1]
        row = i * width
        prev = row - width
        for j in range(1, m + 1):
            k = row + j
            diag = prev + j - 1
            s = score(ai, b[j - 1])
            m0, x0, y0 = M[diag], X[diag], Y[diag]
            if m0 >= x0 and m0 >= y0:
                top, state = m0, 0
            elif x0 >= y0:
                top, state = x0, 1
            else:
                top, state = y0, 2
            if local and top <= 0:
                M[k], pm[k] = s, 3
            elif top > half_neg:
                M[k], pm[k] = top + s, state
            up = prev + j
            o0, o1, o2 = M[up] - gap_first, X[up] - ge, Y[up] - gap_first
            if o0 >= o1 and o0 >= o2:
                top, state = o0, 0
            elif o1 >= o2:
                top, state = o1, 1
            else:
                top, state = o2, 2
            if top > half_neg:
                X[k], px[k] = top, state
            left = k - 1
            o0, o1, o2 = M[left] - gap_first, Y[left] - ge, X[left] - gap_first
            if o0 >= o1 and o0 >= o2:
                top, state = o0, 0
            elif o1 >= o2:
                top, state = o1, 2
            else:
                top, state = o2, 1
            if top > half_neg:
                Y[k], py[k] = top, state
            if local and M[k] > best[0]:
                best = (M[k], i, j, 0)
    if mode == "global":
        k = n * width + m
        end_state = max(((M[k], 0), (X[k], 1), (Y[k], 2)), key=lambda t: (t[0], -t[1]))
        best = (end_state[0], n, m, end_state[1])
    elif mode == "semiglobal":
        candidates = [(M[n * width + j], n, j, 0) for j in range(m + 1)]
        candidates += [(M[i * width + m], i, m, 0) for i in range(n + 1)]
        best = max(candidates, key=lambda t: (t[0], t[1] + t[2]))
    score_total, i, j, state = best
    end_i, end_j = i, j
    a_out: list[str] = []
    b_out: list[str] = []
    while True:
        k = i * width + j
        if state == 0:
            if i == 0 or j == 0:
                break
            prior = pm[k]
            a_out.append(a[i - 1])
            b_out.append(b[j - 1])
            i, j = i - 1, j - 1
            if prior == 3:
                break
            state = prior
        elif state == 1:
            prior = px[k]
            a_out.append(a[i - 1])
            b_out.append("-")
            i -= 1
            state = prior
        else:
            prior = py[k]
            a_out.append("-")
            b_out.append(b[j - 1])
            j -= 1
            state = prior
        if mode == "global" and i == 0 and j == 0:
            break
        if mode == "global" and (i == 0 or j == 0) and state == 0:
            break
    start_i, start_j = i, j
    a_out.reverse()
    b_out.reverse()
    a_head = a_tail = b_head = b_tail = ""
    if mode == "semiglobal":
        # unaligned overhangs are written as end gaps so both rows span both sequences
        a_head, b_head = a[:start_i], "-" * start_i
        a_head2, b_head2 = "-" * start_j, b[:start_j]
        a_head, b_head = a_head + a_head2, b_head + b_head2
        a_tail, b_tail = a[end_i:], "-" * (n - end_i)
        a_tail2, b_tail2 = "-" * (m - end_j), b[end_j:]
        a_tail, b_tail = a_tail + a_tail2, b_tail + b_tail2
    elif mode == "global":
        a_head, b_head = a[:start_i] + "-" * start_j, "-" * start_i + b[:start_j]
    return Alignment(
        a_head + "".join(a_out) + a_tail,
        b_head + "".join(b_out) + b_tail,
        start_i,
        end_i,
        start_j,
        end_j,
        score_total,
        mode,
    )


# --------------------------------------------------------------------------- comparisons
@dataclass(frozen=True)
class CdsSpec:
    """Coding interval of a reference sequence: 1-based inclusive forward coordinates."""

    start: int
    end: int
    strand: str  # "+" or "-"


def call_differences(
    alignment: Alignment,
    ref_seq: str,
    cand_seq: str,
    cds: CdsSpec | None,
    candidate: str,
    reference: str,
) -> list[dict[str, object]]:
    """Reference-vs-candidate differences from a nucleotide alignment (a=ref, b=cand).

    Substitutions are single-column events; consecutive gap columns form one
    insertion/deletion event. Events outside ``cds`` are ``flanking`` (never "UTR").
    Insertions are reported at the reference base preceding them.
    """
    ref_a, cand_a = alignment.a_aligned, alignment.b_aligned
    ref_pos = 0  # reference bases consumed
    cand_pos = 0
    raw: list[dict[str, object]] = []
    column = 0
    ncols = len(ref_a)
    first_ref_col = next((c for c in range(ncols) if ref_a[c] != "-" and cand_a[c] != "-"), None)
    last_ref_col = next((c for c in range(ncols - 1, -1, -1) if ref_a[c] != "-" and cand_a[c] != "-"), None)
    while column < ncols:
        r, c = ref_a[column], cand_a[column]
        if r != "-" and c != "-":
            ref_pos += 1
            cand_pos += 1
            if r != c:
                raw.append(
                    {"kind": "substitution", "ref_start": ref_pos, "ref_end": ref_pos,
                     "cand_start": cand_pos, "cand_end": cand_pos, "ref": r, "cand": c,
                     "terminal": False}
                )
            column += 1
            continue
        end = column
        while end < ncols and ((r == "-") == (ref_a[end] == "-")) and ((c == "-") == (cand_a[end] == "-")):
            end += 1
        ref_run = ref_a[column:end].replace("-", "")
        cand_run = cand_a[column:end].replace("-", "")
        terminal = first_ref_col is None or column < first_ref_col or end - 1 > last_ref_col
        if r == "-":  # insertion in candidate
            raw.append(
                {"kind": "insertion", "ref_start": ref_pos, "ref_end": ref_pos,
                 "cand_start": cand_pos + 1, "cand_end": cand_pos + len(cand_run),
                 "ref": "", "cand": cand_run, "terminal": terminal}
            )
            cand_pos += len(cand_run)
        else:  # deletion in candidate
            raw.append(
                {"kind": "deletion", "ref_start": ref_pos + 1, "ref_end": ref_pos + len(ref_run),
                 "cand_start": cand_pos, "cand_end": cand_pos, "ref": ref_run, "cand": "",
                 "terminal": terminal}
            )
            ref_pos += len(ref_run)
        column = end

    # global offsets: alignment may start inside the sequences (local/semiglobal heads)
    # semiglobal/global strings already span both sequences (overhangs written as end gaps);
    # only a local alignment starts inside the sequences.
    ref_offset, cand_offset = (alignment.a_start, alignment.b_start) if alignment.mode == "local" else (0, 0)
    subs = {
        e["ref_start"] + ref_offset: e["cand"] for e in raw if e["kind"] == "substitution"
    }
    rows: list[dict[str, object]] = []
    for event in raw:
        rs, re_ = event["ref_start"] + ref_offset, event["ref_end"] + ref_offset
        cs, ce = event["cand_start"] + cand_offset, event["cand_end"] + cand_offset
        kind = event["kind"]
        length = max(len(event["ref"]), len(event["cand"]))
        if kind == "insertion":
            inside = cds is not None and cds.start <= rs and rs + 1 <= cds.end
        else:
            inside = cds is not None and cds.start <= rs and re_ <= cds.end
        codon_change = aa_change = note = ""
        if cds is None or not inside:
            effect = "flanking"
        elif kind == "substitution":
            effect, codon_change, aa_change, note = _substitution_effect(rs, ref_seq, subs, cds)
        elif any(base not in UNAMBIGUOUS_DNA for base in (event["ref"] + event["cand"])):
            effect = "ambiguous"
        elif length % 3 == 0:
            effect = kind
        else:
            effect = "frameshift"
        rows.append(
            {
                "candidate": candidate,
                "reference": reference,
                "reference_position": rs if kind != "deletion" or rs == re_ else f"{rs}-{re_}",
                "candidate_position": cs if kind != "insertion" or cs == ce else f"{cs}-{ce}",
                "event_type": kind,
                "reference_base": event["ref"] or "-",
                "candidate_base": event["cand"] or "-",
                "length": length,
                "terminal": event["terminal"],
                "within_inferred_CDS": inside,
                "codon_change": codon_change,
                "amino_acid_change": aa_change,
                "effect": effect,
                "note": note,
                "ambiguity_includes_reference_base": (
                    event["ref"] in IUPAC_EXPANSION.get(event["cand"], "")
                    if kind == "substitution" and event["cand"] not in UNAMBIGUOUS_DNA
                    else ""
                ),
            }
        )
    return rows


def _substitution_effect(
    ref_pos: int, ref_seq: str, subs: dict[int, str], cds: CdsSpec
) -> tuple[str, str, str, str]:
    """Return ``(effect, codon_change, amino_acid_change, note)`` for a substitution."""
    if cds.strand == "+":
        offset = ref_pos - cds.start
        codon_start = cds.start + offset - offset % 3
        positions = [codon_start, codon_start + 1, codon_start + 2]
        oriented = lambda base: base  # noqa: E731
    else:
        offset = cds.end - ref_pos
        codon_start = cds.end - (offset - offset % 3)
        positions = [codon_start, codon_start - 1, codon_start - 2]
        oriented = lambda base: reverse_complement(base)  # noqa: E731
    if min(positions) < 1 or max(positions) > len(ref_seq):
        return "ambiguous", "", "", "codon extends beyond the reference sequence"
    ref_codon = "".join(oriented(ref_seq[p - 1]) for p in positions)
    cand_codon = "".join(oriented(subs.get(p, ref_seq[p - 1])) for p in positions)
    aa_index = offset // 3 + 1
    (ref_aa,) = codon_amino_acids(ref_codon)
    options = codon_amino_acids(cand_codon)
    change = f"{ref_codon}>{cand_codon}"
    if any(base not in UNAMBIGUOUS_DNA for base in cand_codon):
        listed = "/".join(sorted(options))
        if options == {ref_aa}:
            note = "IUPAC ambiguity code; every resolution encodes the reference residue"
            return "ambiguous", change, f"{ref_aa}{aa_index}{ref_aa}(ambiguity)", note
        return "ambiguous", change, f"{ref_aa}{aa_index}[{listed}]", f"IUPAC ambiguity code; possible residues {listed}"
    (cand_aa,) = options
    if ref_aa == cand_aa:
        effect = "synonymous"
    elif cand_aa == STOP:
        effect = "nonsense"
    else:
        effect = "missense"
    return effect, change, f"{ref_aa}{aa_index}{cand_aa}", ""


def protein_metrics(ref: str, cand: str) -> dict[str, object]:
    """Semi-global BLOSUM62 comparison; reports identity/similarity/coverage/gaps."""
    result = align(ref, cand, "semiglobal", matrix=BLOSUM62)
    ra, ca = result.a_aligned, result.b_aligned
    # restrict the statistics to the columns between the first and last aligned pair
    cols = [i for i in range(len(ra)) if ra[i] != "-" and ca[i] != "-"]
    if not cols:
        return {"alignment_length": 0, "identities": 0, "protein_identity": 0.0,
                "protein_similarity": 0.0, "gaps": 0, "reference_coverage": 0.0,
                "candidate_coverage": 0.0, "ref_aligned_start": 0, "ref_aligned_end": 0,
                "cand_aligned_start": 0, "cand_aligned_end": 0, "score": result.score}
    lo, hi = cols[0], cols[-1] + 1
    ra_c, ca_c = ra[lo:hi], ca[lo:hi]
    identities = sum(x == y for x, y in zip(ra_c, ca_c) if x != "-")
    positives = sum(
        BLOSUM62.get((x, y), -4) > 0 for x, y in zip(ra_c, ca_c) if x != "-" and y != "-"
    )
    gaps = ra_c.count("-") + ca_c.count("-")
    ref_aligned = len(ra_c.replace("-", ""))
    cand_aligned = len(ca_c.replace("-", ""))
    length = len(ra_c)
    return {
        "alignment_length": length,
        "identities": identities,
        "protein_identity": round(100 * identities / length, 3),
        "protein_similarity": round(100 * positives / length, 3),
        "identity_over_reference_length": round(100 * identities / len(ref), 3),
        "gaps": gaps,
        "reference_coverage": round(100 * ref_aligned / len(ref), 3),
        "candidate_coverage": round(100 * cand_aligned / len(cand), 3),
        "ref_aligned_start": result.a_start + 1,
        "ref_aligned_end": result.a_end,
        "cand_aligned_start": result.b_start + 1,
        "cand_aligned_end": result.b_end,
        "score": result.score,
    }


def anchor_alignment_ends(alignment: Alignment) -> Alignment:
    """Make both ends of a semi-global alignment start/stop on an identical column.

    Mismatch columns before the first (after the last) identical column are rewritten as unaligned
    overhangs, exactly what a local aligner such as BLAST reports, so end artefacts of forcing
    unrelated flanks together are not reported as substitutions.
    """
    a, b = alignment.a_aligned, alignment.b_aligned
    identical = [i for i, (x, y) in enumerate(zip(a, b)) if x == y and x != "-"]
    if not identical:
        return alignment
    first, last = identical[0], identical[-1] + 1

    def overhang(a_part: str, b_part: str) -> tuple[str, str]:
        a_res, b_res = a_part.replace("-", ""), b_part.replace("-", "")
        return a_res + "-" * len(b_res), "-" * len(a_res) + b_res

    head_a, head_b = overhang(a[:first], b[:first])
    tail_a, tail_b = overhang(a[last:], b[last:])
    return Alignment(head_a + a[first:last] + tail_a, head_b + b[first:last] + tail_b,
                     alignment.a_start, alignment.a_end, alignment.b_start, alignment.b_end, alignment.score, alignment.mode)


def format_alignment(alignment: Alignment, name_a: str, name_b: str, width: int = 80) -> str:
    """Readable block alignment with a match line (``|`` identical, ``.`` mismatch)."""
    mid = "".join(
        "|" if x == y and x != "-" else " " if "-" in (x, y) else "."
        for x, y in zip(alignment.a_aligned, alignment.b_aligned)
    )
    label = max(len(name_a), len(name_b))
    out: list[str] = [f"# mode={alignment.mode} score={alignment.score}"]
    for i in range(0, len(mid), width):
        out.append(f"{name_a:<{label}} {alignment.a_aligned[i:i+width]}")
        out.append(f"{'':<{label}} {mid[i:i+width]}")
        out.append(f"{name_b:<{label}} {alignment.b_aligned[i:i+width]}")
        out.append("")
    return "\n".join(out) + "\n"


# =========================================================================== orchestration
# Everything below talks to the file system / external tools. The functions above are pure.
import csv
import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess

from zeaguard import nb01_identity

TARGET_NAMES = ("Dmai-dsRNase-1", "Dmai-dsRNase-2", "Dmai-dsRNase-3")
SHORT = {"Dmai-dsRNase-1": "dsRNase-1", "Dmai-dsRNase-2": "dsRNase-2", "Dmai-dsRNase-3": "dsRNase-3"}
HISTORICAL_CANDIDATES = {
    "dsRNase-2": ("GITV01012450.1", "GITV01008430.1"),
    "dsRNase-1": ("GITV01001583.1",),
}
S1_SOURCE = "Dalaison-Fuentes2023_S1_mmc1.pdf"
INVESTIGATION_DIR = Path("results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity")
S1_TEXT = "raw/S1_text_layer_pypdf6.19.0.txt"
# from the GenBank record of GITV00000000.1 (DBLINK); note the repo manifest lists PRJNA579843
TSA_BIOPROJECT = "PRJNA631706"
TSA_SRA_RUNS = tuple(f"SRR118223{n}" for n in range(33, 49))

# Pre-registered before any search was run (see ADR 0004): discovery is deliberately broad
# and says nothing about identity.
DISCOVERY_MIN_UNION_COVERAGE_PCT = 50.0
DISCOVERY_MAX_EVALUE = 1e-5
BLASTN_PARAMS = ["-task", "blastn", "-dust", "no", "-evalue", "1e-5", "-max_target_seqs", "500"]
TBLASTN_PARAMS = ["-evalue", "1e-5", "-max_target_seqs", "500", "-db_gencode", "1", "-seg", "no"]
HISTORICAL_BLASTN_PARAMS = [
    "-task", "blastn", "-dust", "no", "-evalue", "1e-5", "-max_target_seqs", "100", "-max_hsps", "1",
]


class CommandLog:
    """Append-only record of every external command actually executed."""

    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    def run(self, command: list[str], stdout_path: Path | None = None) -> str:
        started = datetime.now(timezone.utc).isoformat()
        try:
            done = subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise nb01_identity.IdentityResolutionError(f"required executable is unavailable: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            raise nb01_identity.IdentityResolutionError(
                f"command failed: {' '.join(command)}\n{exc.stderr or exc.stdout}"
            ) from exc
        if stdout_path is not None:
            stdout_path.write_text(done.stdout, encoding="utf-8", newline="\n")
        self.entries.append({"command": " ".join(command), "started_utc": started, "returncode": 0})
        return done.stdout


def sha256_file(path: Path) -> str:
    return nb01_identity._sha256_file(path)


def write_tsv(path: Path, rows: list[dict[str, object]], columns: Sequence[str] | None = None) -> None:
    columns = list(columns or (rows[0].keys() if rows else []))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_references(inv: Path) -> dict[str, dict[str, object]]:
    """Parse the S1 text layer and locate each published protein in its transcript."""
    s1 = parse_s1_text((inv / S1_TEXT).read_text(encoding="utf-8"))
    refs: dict[str, dict[str, object]] = {}
    for name in TARGET_NAMES:
        protein_id, protein = s1[name]["protein"]
        transcript_id, transcript = s1[name]["transcript"]
        placements = locate_protein(transcript, protein)
        placement = placements[0] if len(placements) == 1 else None
        refs[SHORT[name]] = {
            "published_name": name,
            "protein_id": protein_id,
            "protein": protein,
            "transcript_id": transcript_id,
            "transcript": transcript,
            "placements": placements,
            "placement": placement,
            "cds": placement["cds"] if placement else None,
        }
    return refs


def reference_validation_rows(refs: dict[str, dict[str, object]], anchors: dict[str, str], s1_sha: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ref in refs.values():
        placement = ref["placement"]
        cds = ref["cds"]
        common = {
            "published_name": ref["published_name"],
            "source": f"{S1_SOURCE} sha256={s1_sha}",
            "source_version": "Elsevier mmc1 (Last-Modified 2023-11-07)",
        }
        rows.append({
            **common, "reference_id": ref["transcript_id"], "sequence_type": "published_cDNA(Trinity transcript)",
            "length": len(ref["transcript"]), "sha256": sha256_text(ref["transcript"]),
            "ambiguous_characters": count_ambiguous(ref["transcript"]),
            "start_codon_present": "NA", "stop_codon_present": "NA", "translation_length": "NA",
            "note": f"identical_to_repo_anchor={anchors.get(ref['transcript_id']) == ref['transcript']}",
        })
        if placement:
            rows.append({
                **common, "reference_id": f"{ref['transcript_id']}.CDS",
                "sequence_type": "ORF_nucleotide(derived: S1 protein located in S1 cDNA)",
                "length": len(cds), "sha256": sha256_text(cds), "ambiguous_characters": count_ambiguous(cds),
                "start_codon_present": cds[:3] == "ATG", "stop_codon_present": translate(cds[-3:]) == STOP,
                "translation_length": len(translate(cds, to_stop=True)),
                "note": (
                    f"S1 provides no separate ORF nucleotide record; CDS = cDNA {placement['strand']} strand "
                    f"{placement['start']}-{placement['end']} frame {placement['frame']}; "
                    f"translation_equals_published_protein={translate(cds, to_stop=True) == ref['protein']}; "
                    f"flank_5prime_nt={placement['upstream_nt']}; flank_3prime_nt={placement['downstream_nt']}"
                ),
            })
        rows.append({
            **common, "reference_id": ref["protein_id"], "sequence_type": "published_protein",
            "length": len(ref["protein"]), "sha256": sha256_text(ref["protein"]),
            "ambiguous_characters": ref["protein"].count("X"),
            "start_codon_present": ref["protein"][0] == "M", "stop_codon_present": False,
            "translation_length": len(ref["protein"]), "note": "",
        })
    return rows


def stage_references(root: Path, inv: Path) -> dict[str, dict[str, object]]:
    refs = load_references(inv)
    anchors = {r.identifier: r.sequence for r in nb01_identity.parse_fasta(root / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH)}
    rows = reference_validation_rows(refs, anchors, sha256_file(root / "data/external" / S1_SOURCE))
    write_tsv(inv / "reference_validation.tsv", rows)
    records: list[tuple[str, str]] = []
    for short, ref in refs.items():
        p = ref["placement"]
        records.append((f"{short}.cDNA {ref['transcript_id']} published_cDNA length={len(ref['transcript'])}", ref["transcript"]))
        records.append((f"{short}.CDS {ref['transcript_id']} derived_ORF cDNA_strand={p['strand']} {p['start']}-{p['end']}", ref["cds"]))
        records.append((f"{short}.protein {ref['protein_id']} published_protein length={len(ref['protein'])}", ref["protein"]))
    (inv / "reference_sequences.fasta").write_text(format_fasta(records), encoding="ascii", newline="\n")
    return refs


def _write_queries(inv: Path, refs: dict[str, dict[str, object]]) -> dict[str, Path]:
    raw = inv / "raw"
    paths = {"nt": raw / "queries_nt.fasta", "cdna": raw / "queries_cdna.fasta", "protein": raw / "queries_protein.fasta"}
    cdna = [(f"{s}.cDNA", r["transcript"]) for s, r in refs.items()]
    cds = [(f"{s}.CDS", r["cds"]) for s, r in refs.items()]
    paths["cdna"].write_text(format_fasta(cdna), newline="\n")
    paths["nt"].write_text(format_fasta(cdna + cds), newline="\n")
    paths["protein"].write_text(format_fasta((f"{s}.protein", r["protein"]) for s, r in refs.items()), newline="\n")
    return paths


def _blast_with_archive(log: CommandLog, program: str, query: Path, db: Path, params: list[str],
                        stem: Path, fields: Sequence[str]) -> list[Hsp]:
    archive = stem.parent / (stem.name + ".asn")
    table = stem.parent / (stem.name + ".outfmt6.tsv")
    log.run([program, "-query", str(query), "-db", str(db), *params, "-outfmt", "11", "-out", str(archive)])
    log.run(["blast_formatter", "-archive", str(archive), "-outfmt", "6 " + " ".join(fields)], stdout_path=table)
    log.run(["blast_formatter", "-archive", str(archive), "-outfmt", "0"],
            stdout_path=stem.parent / (stem.name + ".pairwise.txt"))
    return parse_hsp_table(table.read_text(encoding="utf-8"), fields)


def stage_search(root: Path, inv: Path, refs: dict[str, dict[str, object]], log: CommandLog) -> dict[str, list[Hsp]]:
    raw = inv / "raw"
    db_dir = raw / "blastdb"
    db_dir.mkdir(exist_ok=True)
    manifest = json.loads((root / nb01_identity.DEFAULT_MANIFEST_PATH).read_text(encoding="utf-8"))
    tsa_gz = root / manifest["files"][0]["path"]
    fasta = db_dir / "tsa.GITV.1.fsa_nt"
    with gzip.open(tsa_gz, "rb") as source, fasta.open("wb") as target:
        shutil.copyfileobj(source, target)
    db = db_dir / "tsa_GITV"
    log.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-parse_seqids",
             "-title", "TSA GITV01 Dalbulus maidis", "-out", str(db)], stdout_path=raw / "makeblastdb.log")
    queries = _write_queries(inv, refs)
    return {
        "blastn": _blast_with_archive(log, "blastn", queries["nt"], db, BLASTN_PARAMS, raw / "blastn_discovery", BLAST_OUTFMT_FIELDS),
        "tblastn": _blast_with_archive(log, "tblastn", queries["protein"], db, TBLASTN_PARAMS, raw / "tblastn_discovery", TBLASTN_OUTFMT_FIELDS),
        "blastn_historical_params": _blast_with_archive(
            log, "blastn", queries["cdna"], db, HISTORICAL_BLASTN_PARAMS, raw / "blastn_historical_params", BLAST_OUTFMT_FIELDS),
    }


def _hsp_rows(hsps: Sequence[Hsp]) -> list[dict[str, object]]:
    canon = nb01_identity.canonical_tsa_accession
    return [
        {"query": h.query, "subject": canon(h.subject), "percent_identity": h.pident,
         "alignment_length": h.length, "query_length": h.qlen, "subject_length": h.slen,
         "query_start": h.query_interval[0], "query_end": h.query_interval[1],
         "subject_start": h.subject_interval[0], "subject_end": h.subject_interval[1], "strand": h.strand,
         "frame": h.sframe if h.sframe is not None else "", "evalue": h.evalue, "bitscore": h.bitscore,
         "mismatches": h.mismatch, "gap_opens": h.gapopen, "gaps": h.gaps, "blast_qcovs": h.qcovs, "btop": h.btop}
        for h in sorted(hsps, key=lambda h: (h.query, -h.bitscore, canon(h.subject), h.qstart))
    ]


def stage_candidates(inv: Path, hsps: dict[str, list[Hsp]]) -> dict[str, object]:
    """Write hit tables and the discovery set; no identity decision is made here."""
    canon = nb01_identity.canonical_tsa_accession
    files = {"blastn": "blastn_hits.tsv", "tblastn": "tblastn_hits.tsv", "blastn_historical_params": "blastn_historical_params_hits.tsv"}
    summaries: dict[str, list[dict[str, object]]] = {}
    for name, filename in files.items():
        write_tsv(inv / filename, _hsp_rows(hsps[name]), columns=list(_hsp_rows(hsps[name])[0].keys()) if hsps[name] else ["query"])
        normalized = [Hsp(**{**h.__dict__, "subject": canon(h.subject)}) for h in hsps[name]]
        summaries[name] = summarize_hsps(normalized)
        write_tsv(inv / f"{name}_coverage_summary.tsv", summaries[name], columns=list(summaries[name][0].keys()) if summaries[name] else ["query"])
    discovery: dict[str, set[str]] = {}
    for name in ("blastn", "tblastn"):
        for row in summaries[name]:
            if row["query_union_coverage_pct"] >= DISCOVERY_MIN_UNION_COVERAGE_PCT and row["best_evalue"] <= DISCOVERY_MAX_EVALUE:
                discovery.setdefault(str(row["subject"]), set()).add(
                    f"{name}:{row['query']}:{row['strand']}:{row['query_union_coverage_pct']}%")
    for short, accessions in HISTORICAL_CANDIDATES.items():
        for accession in accessions:
            discovery.setdefault(accession, set()).add(f"historical_candidate:{short}")
    return {"summaries": summaries, "discovery": {k: sorted(v) for k, v in sorted(discovery.items())}}


# --------------------------------------------------------------------------- ORFs / CDS / comparisons
# Pre-registered before ORFs were inspected: an ORF is "homology-supported" when its best
# local BLOSUM62 alignment (gap 11/1) against a published protein scores at least this raw score.
ORF_MIN_AA = 30
ORF_SUPPORT_MIN_SCORE = 80
# Pre-registered identity-competing rule (ADR 0004): the published dsRNase-2 must be the best
# protein match (ties count) and cover at least this share of the published protein.
COMPETING_MIN_REF_COVERAGE_PCT = 50.0


def load_tsa_records(root: Path) -> dict[str, nb01_identity.FastaRecord]:
    manifest = json.loads((root / nb01_identity.DEFAULT_MANIFEST_PATH).read_text(encoding="utf-8"))
    path = root / manifest["files"][0]["path"]
    return {nb01_identity.canonical_tsa_accession(r.identifier): r for r in nb01_identity.parse_fasta(path)}


def infer_cds(seq: str, orf: Orf, ref_protein: str) -> dict[str, object]:
    """CDS of ``orf`` anchored on the published protein, with converging completeness evidence.

    The start is the in-frame Met aligned to residue 1 of the published protein when the
    published N-terminus aligns; otherwise the segment start is kept and flagged. Nothing is
    inferred from the mere absence of an upstream stop codon.
    """
    local = align(ref_protein, orf.protein, "local", matrix=BLOSUM62)
    ref_n_aligned = local.a_start == 0
    met_at_start = ref_n_aligned and orf.protein[local.b_start : local.b_start + 1] == "M"
    cds_start_aa = local.b_start if met_at_start else 0
    evidence: list[str] = []
    if met_at_start:
        five = "COMPLETE_START_MATCHES_PUBLISHED_N_TERMINUS"
        evidence.append(f"Met aligned to published residue 1; {cds_start_aa} in-frame residues precede it in the open segment")
    elif ref_n_aligned:
        five = "PUBLISHED_RESIDUE1_ALIGNED_WITHOUT_MET"
    elif not orf.begins_after_stop and orf.o_start <= 2:
        five = "TRUNCATED_AT_TRANSCRIPT_END"
        evidence.append(f"published residues 1-{local.a_start} unaligned and the open segment reaches the transcript end")
    elif orf.begins_after_stop:
        five = "PUBLISHED_N_TERMINUS_NOT_ALIGNED_UPSTREAM_STOP_PRESENT"
        evidence.append(f"published residues 1-{local.a_start} unaligned; in-frame stop precedes the segment")
    else:
        five = "PUBLISHED_N_TERMINUS_NOT_ALIGNED"
    ref_c_aligned = local.a_end == len(ref_protein)
    if orf.has_stop and ref_c_aligned:
        three = "COMPLETE_STOP_AFTER_PUBLISHED_C_TERMINUS"
    elif not orf.has_stop:
        three = "TRUNCATED_AT_TRANSCRIPT_END"
    else:
        three = "STOP_BEFORE_PUBLISHED_C_TERMINUS"
        evidence.append(f"published residues {local.a_end + 1}-{len(ref_protein)} unaligned")
    oriented = seq.upper() if orf.strand == "+" else reverse_complement(seq)
    cds = oriented[orf.o_start + 3 * cds_start_aa : orf.o_end]
    if orf.strand == "+":
        start, end = orf.start + 3 * cds_start_aa, orf.end
    else:
        start, end = orf.start, orf.end - 3 * cds_start_aa
    return {
        "cds": cds, "protein": orf.protein[cds_start_aa:], "cds_start_aa": cds_start_aa,
        "start": start, "end": end, "strand": orf.strand, "five_prime": five, "three_prime": three,
        "evidence": "; ".join(evidence), "upstream_inframe_residues": cds_start_aa,
        "ref_aligned": (local.a_start + 1, local.a_end), "local_score": local.score,
    }


def stage_orfs(root: Path, inv: Path, refs: dict[str, dict[str, object]], accessions: Sequence[str]) -> dict[str, dict[str, object]]:
    tsa = load_tsa_records(root)
    (inv / "candidate_transcripts.fasta").write_text(
        format_fasta((f"{acc} {tsa[acc].description.split(' ', 1)[-1]}", tsa[acc].sequence) for acc in accessions),
        encoding="ascii", newline="\n")
    ref_proteins = {s: r["protein"] for s, r in refs.items()}
    info: dict[str, dict[str, object]] = {}
    orf_rows: list[dict[str, object]] = []
    for acc in accessions:
        seq = tsa[acc].sequence
        scored: list[dict[str, object]] = []
        for number, orf in enumerate(find_orfs(seq, ORF_MIN_AA), start=1):
            best = max(
                ((s, align(p, orf.protein, "local", matrix=BLOSUM62)) for s, p in ref_proteins.items()),
                key=lambda t: (t[1].score, t[0]),
            )
            ref_name, local = best
            aligned = [(x, y) for x, y in zip(local.a_aligned, local.b_aligned) if "-" not in (x, y)]
            identity = round(100 * sum(x == y for x, y in aligned) / max(len(aligned), 1), 3)
            scored.append({
                "candidate": acc, "orf_id": f"{acc}|ORF{number}", "orf": orf, "strand": orf.strand,
                "frame": orf.frame, "start": orf.start, "end": orf.end, "nt_length": orf.end - orf.start + 1,
                "segment_aa": len(orf.protein), "begins_after_stop": orf.begins_after_stop, "has_stop": orf.has_stop,
                "first_met_index_aa": orf.first_met + 1 if orf.first_met >= 0 else "",
                "ambiguous_nt": count_ambiguous(orf_sequence(seq, orf)), "best_reference": ref_name,
                "local_score": local.score, "aligned_identity_pct": identity,
                "reference_aligned_range": f"{local.a_start + 1}-{local.a_end}",
                "supported": local.score >= ORF_SUPPORT_MIN_SCORE, "role": "unsupported",
            })
        supported = sorted((r for r in scored if r["supported"]), key=lambda r: (-r["local_score"], r["orf_id"]))
        primary = supported[0] if supported else None
        for row in supported:
            row["role"] = "primary" if row is primary else "secondary_supported"
        entry: dict[str, object] = {"seq": seq, "orf_rows": scored, "primary": None, "secondary": supported[1:]}
        if primary:
            cds = infer_cds(seq, primary["orf"], ref_proteins[primary["best_reference"]])
            cds["best_reference"] = primary["best_reference"]
            cds["orf_id"] = primary["orf_id"]
            entry["primary"] = cds
        info[acc] = entry
        orf_rows.extend(scored)
    columns = ["candidate", "orf_id", "role", "strand", "frame", "start", "end", "nt_length", "segment_aa", "begins_after_stop",
               "has_stop", "first_met_index_aa", "ambiguous_nt", "best_reference", "local_score", "aligned_identity_pct",
               "reference_aligned_range", "supported", "cds_start", "cds_end", "cds_nt_length", "protein_aa", "five_prime_status",
               "three_prime_status", "n_terminal_evidence", "internal_stop_codons", "apparent_split_or_frameshift"]
    out_rows = []
    for row in orf_rows:
        extra = {k: "" for k in ("cds_start", "cds_end", "cds_nt_length", "protein_aa", "five_prime_status", "three_prime_status",
                                 "n_terminal_evidence", "internal_stop_codons", "apparent_split_or_frameshift")}
        primary = info[row["candidate"]]["primary"]
        if primary and primary["orf_id"] == row["orf_id"]:
            extra.update(cds_start=primary["start"], cds_end=primary["end"], cds_nt_length=len(primary["cds"]),
                         protein_aa=len(primary["protein"]), five_prime_status=primary["five_prime"],
                         three_prime_status=primary["three_prime"], n_terminal_evidence=primary["evidence"],
                         internal_stop_codons=primary["protein"].count(STOP))
        if row["role"] == "secondary_supported":
            extra["apparent_split_or_frameshift"] = (
                f"supported ORF in another frame/strand (ref range {row['reference_aligned_range']}); compare with primary "
                f"{info[row['candidate']]['primary']['orf_id']} (ref range {info[row['candidate']]['primary']['ref_aligned'][0]}-"
                f"{info[row['candidate']]['primary']['ref_aligned'][1]})")
        out_rows.append({**{k: v for k, v in row.items() if k != "orf"}, **extra})
    write_tsv(inv / "orf_candidates.tsv", out_rows, columns)
    cds_records, prot_records = [], []
    for acc in accessions:
        p = info[acc]["primary"]
        if p:
            tag = (f"{acc}.CDS {p['orf_id']} strand={p['strand']} {p['start']}-{p['end']} best_reference={p['best_reference']} "
                   f"5prime={p['five_prime']} 3prime={p['three_prime']}")
            cds_records.append((tag, p["cds"]))
            prot_records.append((tag.replace(".CDS", ".protein"), p["protein"]))
    (inv / "candidate_cds.fasta").write_text(format_fasta(cds_records), encoding="ascii", newline="\n")
    (inv / "candidate_proteins.fasta").write_text(format_fasta(prot_records), encoding="ascii", newline="\n")
    return info


def protein_comparison_rows(info: dict[str, dict[str, object]], refs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for acc, entry in info.items():
        p = entry["primary"]
        if not p:
            continue
        for short, ref in refs.items():
            m = protein_metrics(ref["protein"], p["protein"])
            rows.append({"candidate": acc, "reference": f"{short}.protein", **m, "internal_stop": p["protein"].count(STOP),
                         "N_terminal_completeness": p["five_prime"], "C_terminal_completeness": p["three_prime"],
                         "candidate_protein_sha256": sha256_text(p["protein"])})
    return rows


def _orient(seq_cds: CdsSpec, other_strand: str, other: str) -> tuple[str, str]:
    """Orient ``other`` to the strand of the reference CDS; returns (sequence, orientation label)."""
    if other_strand == seq_cds.strand:
        return other, "as_stored"
    return reverse_complement(other), "reverse_complemented"


def compare_pair(inv: Path, tag: str, ref_name: str, ref_seq: str, ref_cds: CdsSpec, cand_name: str, cand_seq: str,
                 cand_strand: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    cand_oriented, orientation = _orient(ref_cds, cand_strand, cand_seq)
    alignment = anchor_alignment_ends(align(ref_seq, cand_oriented, "semiglobal"))
    events = call_differences(alignment, ref_seq, cand_oriented, ref_cds, cand_name, ref_name)
    for event in events:
        event["pair"] = tag
        event["candidate_orientation"] = orientation
    (inv / "alignments" / f"{tag}.nt.alignment.txt").write_text(
        format_alignment(alignment, ref_name[:20], cand_name[:20]), encoding="utf-8", newline="\n")
    (inv / "alignments" / f"{tag}.nt.alignment.fasta").write_text(
        format_fasta([(ref_name, alignment.a_aligned), (cand_name + f" [{orientation}]", alignment.b_aligned)]), newline="\n")
    columns = sum(a != "-" and b != "-" for a, b in zip(alignment.a_aligned, alignment.b_aligned))
    matches = sum(a == b and a != "-" for a, b in zip(alignment.a_aligned, alignment.b_aligned))
    effects = defaultdict(int)
    for event in events:
        effects[event["effect"]] += 1
    summary = {
        "pair": tag, "reference": ref_name, "candidate": cand_name, "candidate_orientation": orientation,
        "reference_length": len(ref_seq), "candidate_length": len(cand_seq),
        "aligned_pairs": columns, "identical_pairs": matches,
        "identity_over_aligned_pairs_pct": round(100 * matches / max(columns, 1), 4),
        "reference_aligned_range": f"{alignment.a_start + 1}-{alignment.a_end}",
        "candidate_aligned_range_in_comparison_orientation": f"{alignment.b_start + 1}-{alignment.b_end}",
        "n_events": len(events), **{f"n_{k}": v for k, v in sorted(effects.items())},
    }
    return events, summary


def _cds_spec(p: dict[str, object]) -> CdsSpec:
    return CdsSpec(int(p["start"]), int(p["end"]), str(p["strand"]))


def nucleotide_identity(a: str, b: str, min_fraction: float = 0.5) -> dict[str, object]:
    """Semi-global nucleotide identity of two CDS (paralogy control).

    Divergent paralogs (about 30 % protein identity) are not alignable at nucleotide level; when fewer than
    ``min_fraction`` of the shorter CDS is paired the identity is reported as not alignable instead of as
    a number computed from a handful of paired bases.
    """
    al = align(a, b, "semiglobal")
    pairs = [(x, y) for x, y in zip(al.a_aligned, al.b_aligned) if x != "-" and y != "-"]
    same = sum(x == y for x, y in pairs)
    alignable = len(pairs) >= min_fraction * min(len(a), len(b))
    return {"nt_aligned_pairs": len(pairs), "nt_identical_pairs": same,
            "nt_identity_pct": round(100 * same / max(len(pairs), 1), 3) if alignable else "NOT_ALIGNABLE_AT_NUCLEOTIDE_LEVEL"}


def stage_compare(inv: Path, refs: dict[str, dict[str, object]], info: dict[str, dict[str, object]]) -> dict[str, object]:
    ds2_accessions = [a for a in info if info[a]["primary"] and info[a]["primary"]["best_reference"] == "dsRNase-2"]
    ds1_accessions = [a for a in info if info[a]["primary"] and info[a]["primary"]["best_reference"] == "dsRNase-1"]
    events: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []

    def run_pair(tag, ref_name, ref_seq, ref_cds, cand_name, cand_seq, cand_strand):
        e, s = compare_pair(inv, tag, ref_name, ref_seq, ref_cds, cand_name, cand_seq, cand_strand)
        events.extend(e)
        summaries.append(s)

    for short, accessions in (("dsRNase-2", ds2_accessions), ("dsRNase-1", ds1_accessions)):
        ref = refs[short]
        p = ref["placement"]
        spec = CdsSpec(p["start"], p["end"], p["strand"])
        for acc in accessions:
            run_pair(f"{short}.published_cDNA_vs_{acc}", ref["transcript_id"], ref["transcript"], spec,
                     acc, info[acc]["seq"], info[acc]["primary"]["strand"])
    # candidate vs candidate, reference side = the first accession (arbitrary, symmetric table)
    for group in (ds2_accessions, ds1_accessions):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                run_pair(f"{a}_vs_{b}", a, info[a]["seq"], _cds_spec(info[a]["primary"]), b, info[b]["seq"],
                         info[b]["primary"]["strand"])
    columns = ["pair", "candidate", "reference", "reference_position", "candidate_position", "event_type", "reference_base",
               "candidate_base", "length", "terminal", "within_inferred_CDS", "codon_change", "amino_acid_change", "effect",
               "ambiguity_includes_reference_base", "note", "candidate_orientation"]
    write_tsv(inv / "nucleotide_comparison.tsv", events, columns)
    write_tsv(inv / "nucleotide_comparison_summary.tsv", summaries)

    prot_rows = protein_comparison_rows(info, refs)
    # candidate-vs-candidate protein comparison (same-gene groups)
    for group in (ds2_accessions, ds1_accessions):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                m = protein_metrics(info[a]["primary"]["protein"], info[b]["primary"]["protein"])
                prot_rows.append({"candidate": b, "reference": f"{a}.protein", **m,
                                  "internal_stop": info[b]["primary"]["protein"].count(STOP),
                                  "N_terminal_completeness": info[b]["primary"]["five_prime"],
                                  "C_terminal_completeness": info[b]["primary"]["three_prime"],
                                  "candidate_protein_sha256": sha256_text(info[b]["primary"]["protein"])})
    write_tsv(inv / "protein_comparison.tsv", prot_rows)

    # paralogy control: every candidate against all three published CDS/proteins
    control: list[dict[str, object]] = []
    for acc, entry in info.items():
        p = entry["primary"]
        if not p:
            continue
        for short, ref in refs.items():
            metrics = protein_metrics(ref["protein"], p["protein"])
            control.append({"candidate": acc, "published_reference": short, "protein_identity_pct": metrics["protein_identity"],
                            "protein_similarity_pct": metrics["protein_similarity"],
                            "identity_over_reference_length_pct": metrics["identity_over_reference_length"],
                            "reference_coverage_pct": metrics["reference_coverage"],
                            "candidate_coverage_pct": metrics["candidate_coverage"], "gaps": metrics["gaps"],
                            **nucleotide_identity(ref["cds"], p["cds"])})
    write_tsv(inv / "paralogy_control.tsv", control)

    # pre-registered identity-competing rule for dsRNase-2
    classification: list[dict[str, object]] = []
    for acc, entry in info.items():
        p = entry["primary"]
        rows = sorted((c for c in control if c["candidate"] == acc), key=lambda c: -float(c["identity_over_reference_length_pct"]))
        if not rows:
            classification.append({"candidate": acc, "best_reference_by_protein": "none", "competing_for_dsRNase-2": False})
            continue
        best = rows[0]
        ds2 = next(c for c in rows if c["published_reference"] == "dsRNase-2")
        tie = [c["published_reference"] for c in rows if c["identity_over_reference_length_pct"] == best["identity_over_reference_length_pct"]]
        competing = ("dsRNase-2" in tie) and float(ds2["reference_coverage_pct"]) >= COMPETING_MIN_REF_COVERAGE_PCT
        classification.append({
            "candidate": acc, "best_reference_by_protein": "/".join(tie),
            "best_identity_over_reference_length_pct": best["identity_over_reference_length_pct"],
            "dsRNase-2_identity_over_reference_length_pct": ds2["identity_over_reference_length_pct"],
            "dsRNase-2_reference_coverage_pct": ds2["reference_coverage_pct"],
            "second_best_reference": rows[1]["published_reference"] if len(rows) > 1 else "",
            "second_best_identity_pct": rows[1]["identity_over_reference_length_pct"] if len(rows) > 1 else "",
            "competing_for_dsRNase-2": competing,
            "cds_length": len(p["cds"]), "cds_sha256": sha256_text(p["cds"]), "protein_length": len(p["protein"]),
            "protein_sha256": sha256_text(p["protein"]), "cds_ambiguous_nt": count_ambiguous(p["cds"]),
            "protein_X_residues": p["protein"].count("X"), "five_prime_status": p["five_prime"], "three_prime_status": p["three_prime"],
            "transcript_length": len(entry["seq"]),
            "five_prime_flank_nt": (len(entry["seq"]) - p["end"]) if p["strand"] == "-" else p["start"] - 1,
            "three_prime_flank_nt": (p["start"] - 1) if p["strand"] == "-" else len(entry["seq"]) - p["end"],
        })
    write_tsv(inv / "candidate_classification.tsv", classification)
    return {"events": events, "summaries": summaries, "protein_rows": prot_rows, "control": control,
            "classification": classification, "ds2_accessions": ds2_accessions, "ds1_accessions": ds1_accessions}


# --------------------------------------------------------------------------- PF01223 (HMMER)
PF01223_ID = "PF01223"
DOMTBLOUT_COLUMNS = (
    "target_name target_acc tlen query_name query_acc qlen full_evalue full_score full_bias dom_index dom_of "
    "c_evalue i_evalue dom_score dom_bias hmm_from hmm_to ali_from ali_to env_from env_to acc description"
).split()


def parse_domtblout(text: str) -> list[dict[str, object]]:
    """Parse ``hmmsearch --domtblout`` (one row per domain hit)."""
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split(None, len(DOMTBLOUT_COLUMNS) - 1)
        row = dict(zip(DOMTBLOUT_COLUMNS, cells))
        for key in ("tlen", "qlen", "dom_index", "dom_of", "hmm_from", "hmm_to", "ali_from", "ali_to", "env_from", "env_to"):
            row[key] = int(row[key])
        for key in ("full_evalue", "full_score", "c_evalue", "i_evalue", "dom_score"):
            row[key] = float(row[key])
        rows.append(row)
    return rows


def hmm_ga_threshold(hmm_text: str) -> tuple[float, float]:
    for line in hmm_text.splitlines():
        if line.startswith("GA "):
            a, b = line.split()[1:3]
            return float(a), float(b.rstrip(";"))
    raise ValueError("profile has no GA line")


def feature_rows(domains: list[dict[str, object]], proteins: dict[str, str], meta: dict[str, object],
                 ga: tuple[float, float]) -> list[dict[str, object]]:
    by_seq: dict[str, list[dict[str, object]]] = defaultdict(list)
    for d in domains:
        by_seq[str(d["target_name"])].append(d)
    rows: list[dict[str, object]] = []
    for name in proteins:
        hits = by_seq.get(name, [])
        if not hits:
            rows.append({**meta, "sequence_id": name, "feature": PF01223_ID, "domain_start": "", "domain_end": "",
                         "score": "", "evalue": "", "profile_coverage": 0.0, "sequence_coverage": 0.0,
                         "meets_GA": False, "threshold_used": f"GA {ga[0]}/{ga[1]}; no domain hit at E<=10"})
            continue
        for d in hits:
            profile_cov = (d["hmm_to"] - d["hmm_from"] + 1) / d["qlen"]
            seq_cov = (d["ali_to"] - d["ali_from"] + 1) / d["tlen"]
            meets = d["full_score"] >= ga[0] and d["dom_score"] >= ga[1]
            rows.append({**meta, "sequence_id": name, "feature": PF01223_ID, "domain_start": d["ali_from"],
                         "domain_end": d["ali_to"], "envelope_start": d["env_from"], "envelope_end": d["env_to"],
                         "hmm_from": d["hmm_from"], "hmm_to": d["hmm_to"], "score": d["dom_score"],
                         "evalue": d["i_evalue"], "c_evalue": d["c_evalue"],
                         "profile_coverage": round(100 * profile_cov, 2), "sequence_coverage": round(100 * seq_cov, 2),
                         "meets_GA": meets, "threshold_used": f"GA {ga[0]}/{ga[1]} (sequence/domain score)"})
    return rows


def stage_features(root: Path, inv: Path, refs: dict[str, dict[str, object]], info: dict[str, dict[str, object]],
                   log: CommandLog) -> list[dict[str, object]]:
    raw = inv / "raw"
    hmm_gz = raw / "PF01223.hmm.gz"
    hmm_path = raw / "PF01223.hmm"
    hmm_path.write_bytes(gzip.decompress(hmm_gz.read_bytes()))
    ga = hmm_ga_threshold(hmm_path.read_text())
    proteins: dict[str, str] = {r["protein_id"]: r["protein"] for r in refs.values()}
    for acc, entry in info.items():
        if entry["primary"]:
            proteins[f"{acc}.protein"] = entry["primary"]["protein"].replace(STOP, "")
    query = raw / "pf01223_queries.faa"
    query.write_text(format_fasta(proteins.items()), newline="\n")
    version = log.run(["hmmsearch", "-h"]).splitlines()[1].lstrip("# ").strip()
    out = raw / "hmmsearch_pf01223.domtblout"
    log.run(["hmmsearch", "--domtblout", str(out), "-E", "10", "--domE", "10", str(hmm_path), str(query)],
            stdout_path=raw / "hmmsearch_pf01223.stdout.txt")
    meta = {"tool": "hmmsearch", "tool_version": version, "database": "Pfam (EBI InterPro API download of single profile)",
            "database_version": "PF01223.30 (model DATE 2025-05-29; Pfam release number not exposed by the API)",
            "profile_id": f"{PF01223_ID}.30"}
    rows = feature_rows(parse_domtblout(out.read_text()), proteins, meta, ga)
    return rows


# --------------------------------------------------------------------------- read support at variable sites
ANCHOR = 16


def build_sites(backbone: str, positions: Sequence[int], anchor: int = ANCHOR) -> list[dict[str, object]]:
    """Anchors flanking each 1-based ``position`` of ``backbone`` (must not contain another site)."""
    sites: list[dict[str, object]] = []
    wanted = set(positions)
    for pos in positions:
        lo, hi = pos - 1 - anchor, pos + anchor
        if lo < 0 or hi > len(backbone):
            raise ValueError(f"site {pos}: anchors exceed the backbone")
        clash = sorted(q for q in wanted if q != pos and lo + 1 <= q <= hi)
        if clash:
            raise ValueError(f"site {pos}: anchors contain other variable site(s) {clash}")
        sites.append({"position": pos, "backbone_base": backbone[pos - 1], "left": backbone[lo : pos - 1], "right": backbone[pos:hi]})
    return sites


def anchor_patterns(sites: Sequence[dict[str, object]]) -> list[str]:
    """Fixed-string anchors (both strands) for a ``grep -F`` pre-filter."""
    patterns: list[str] = []
    for site in sites:
        for part in (site["left"], site["right"]):
            patterns.extend([part, reverse_complement(part)])
    return sorted(set(patterns))


def count_site_alleles(sequences: Iterable[str], sites: Sequence[dict[str, object]]) -> dict[int, dict[str, int]]:
    """Count the base between exact left/right anchors on either strand of each read."""
    compiled = [
        (site["position"], re.compile(f"{site['left']}([ACGT]){site['right']}"),
         re.compile(f"{reverse_complement(site['right'])}([ACGT]){reverse_complement(site['left'])}"))
        for site in sites
    ]
    counts: dict[int, dict[str, int]] = {site["position"]: {"A": 0, "C": 0, "G": 0, "T": 0} for site in sites}
    for read in sequences:
        read = read.strip().upper()
        for position, forward, reverse in compiled:
            hit = forward.search(read)
            if hit:
                counts[position][hit.group(1)] += 1
                continue
            hit = reverse.search(read)
            if hit:
                counts[position][reverse_complement(hit.group(1))] += 1
    return counts


def classify_site_support(counts: dict[str, int], alleles: Sequence[str], min_reads: int = 20,
                          min_allele_reads: int = 5, min_fraction: float = 0.05) -> dict[str, object]:
    """Pre-registered interpretation: informative >= 20 reads; supported >= 5 reads and >= 5 %."""
    total = sum(counts.values())
    supported = [a for a in alleles if counts.get(a, 0) >= min_allele_reads and counts.get(a, 0) / max(total, 1) >= min_fraction]
    other = {a: n for a, n in counts.items() if a not in alleles and n}
    if total < min_reads:
        verdict = "NOT_ASSESSABLE_LOW_DEPTH"
    elif len(supported) == len(alleles) and len(alleles) > 1:
        verdict = "BOTH_ALLELES_SUPPORTED"
    elif len(supported) == 1:
        verdict = f"ONLY_{supported[0]}_SUPPORTED"
    else:
        verdict = "NEITHER_EXPECTED_ALLELE_SUPPORTED"
    return {"informative_reads": total, "supported_alleles": "/".join(supported), "verdict": verdict,
            "other_bases": ";".join(f"{a}:{n}" for a, n in sorted(other.items()))}


def stream_command(run: str, mate: int, patterns: Path, out_file: Path, progress_file: Path) -> str:
    """Shell pipeline that streams one FASTQ mate and keeps only reads containing a site anchor.

    The (few) anchor-bearing reads are appended to ``out_file``; the number of reads scanned is logged to
    ``progress_file`` every million reads and at the end, so a stopped run still has a documented prefix.
    No retry flag is used on purpose: a restarted transfer would duplicate data inside the gzip stream.
    """
    url = f"https://ftp.sra.ebi.ac.uk/vol1/fastq/{run[:6]}/0{run[-2:]}/{run}/{run}_{mate}.fastq.gz"
    awk = ("awk 'NR%4==2{n++; if (n%1000000==0) {print n > \"" + str(progress_file) + "\"; fflush(\"" + str(progress_file)
           + "\")} print} END{print n > \"" + str(progress_file) + "\"}'")
    return f"curl -sSf '{url}' | gzip -dc | {awk} | grep -F -f '{patterns}' >> '{out_file}' || true"


def reads_scanned(progress_file: Path) -> int:
    lines = progress_file.read_text().split() if progress_file.exists() else []
    return int(lines[-1]) if lines else 0


def count_anchored_files(backbone: str, positions: Sequence[int], files: dict[str, dict[int, tuple[Path, Path]]]) -> dict[str, object]:
    """Allele counts from saved anchor-bearing reads: ``files = {run: {mate: (reads_file, progress_file)}}``."""
    sites = build_sites(backbone, positions)
    counts: dict[str, dict[int, dict[str, int]]] = {}
    scanned: dict[str, dict[str, int]] = {}
    for run, mates in files.items():
        total = {s["position"]: {"A": 0, "C": 0, "G": 0, "T": 0} for s in sites}
        scanned[run] = {}
        for mate, (reads_file, progress_file) in sorted(mates.items()):
            lines = reads_file.read_text().splitlines() if reads_file.exists() else []
            for position, c in count_site_alleles(lines, sites).items():
                for base, n in c.items():
                    total[position][base] += n
            scanned[run][f"mate{mate}"] = reads_scanned(progress_file)
        counts[run] = total
    return {"backbone": "GITV01008430.1", "sites": list(positions), "counts": counts, "reads_scanned": scanned}


# --------------------------------------------------------------------------- decision
def _ev(level: str, statement: str, source: str) -> dict[str, str]:
    assert level in {"OBSERVATION", "INFERENCE", "HYPOTHESIS"}
    return {"level": level, "statement": statement, "source": source}


def overall_label(accession: str, cds: str, protein: str) -> str:
    """Keep the three levels visible: e.g. ``AMBIGUOUS_AT_ACCESSION_LEVEL`` or ``..._ACCESSION_AND_CDS_LEVELS``."""
    levels = (("ACCESSION", accession), ("CDS", cds), ("PROTEIN", protein))
    parts = []
    for status in ("AMBIGUOUS", "UNRESOLVED"):
        names = [name for name, value in levels if value == status]
        if names:
            parts.append(f"{status}_AT_" + "_AND_".join(names) + ("_LEVEL" if len(names) == 1 else "_LEVELS"))
    return "_".join(parts) if parts else "RESOLVED_AT_ALL_LEVELS"


def residue_alternatives(events: list[dict[str, object]], pair: str) -> list[dict[str, object]]:
    """IUPAC events inside the CDS whose possible residues differ from the reference residue."""
    found: list[dict[str, object]] = []
    for e in events:
        if e["pair"] == pair and e["effect"] == "ambiguous" and e["within_inferred_CDS"] and "[" in str(e["amino_acid_change"]):
            found.append(e)
    return found


def excluded_inference(classification: list[dict[str, object]]) -> str:
    non = [c for c in classification if not c["competing_for_dsRNase-2"]]
    if not non:
        return "No record in the discovery set was excluded by the paralogy rule."
    ds2_max = max(float(c["dsRNase-2_identity_over_reference_length_pct"]) for c in non)
    best_min = min(float(c["best_identity_over_reference_length_pct"]) for c in non)
    return (f"The {len(non)} excluded record(s) match another published paralog better than dsRNase-2: best-reference protein identity "
            f">= {best_min} % versus at most {ds2_max} % to dsRNase-2 (decided on protein identity and coverage, not on BLAST rank).")


def ds3_statement(classification: list[dict[str, object]]) -> str:
    hits = [c["candidate"] for c in classification if "dsRNase-3" in str(c["best_reference_by_protein"])]
    if hits:
        return f"Records whose best protein match is dsRNase-3: {', '.join(hits)}."
    return ("No record of the discovery set has dsRNase-3 as its best protein match, so dsRNase-3 acts as a paralogy control only "
            "through protein comparison (no dsRNase-3 TSA locus was detected at e <= 1e-5).")


def build_decision(
    refs: dict[str, dict[str, object]],
    info: dict[str, dict[str, object]],
    comparison: dict[str, object],
    features: list[dict[str, object]],
    read_support: dict[str, object] | None,
    historical: dict[str, object],
) -> dict[str, object]:
    """Apply the pre-registered rules (ADR 0004). Nothing here adapts to the observed values."""
    pub = refs["dsRNase-2"]
    pub_cds_sha, pub_prot_sha = sha256_text(pub["cds"]), sha256_text(pub["protein"])
    classification = comparison["classification"]
    competing = [c for c in classification if c["competing_for_dsRNase-2"]]
    names = [c["candidate"] for c in competing]
    events = comparison["events"]
    protein_rows = comparison["protein_rows"]

    per_candidate: dict[str, dict[str, object]] = {}
    for c in competing:
        acc = c["candidate"]
        pair = f"dsRNase-2.published_cDNA_vs_{acc}"
        in_cds = [e for e in events if e["pair"] == pair and e["within_inferred_CDS"]]
        fixed = [e for e in in_cds if e["effect"] in {"synonymous", "missense", "nonsense"}]
        indels = [e for e in in_cds if e["effect"] in {"frameshift", "insertion", "deletion"}]
        ambiguous = [e for e in in_cds if e["effect"] == "ambiguous"]
        prot = next(r for r in protein_rows if r["candidate"] == acc and r["reference"] == "dsRNase-2.protein")
        per_candidate[acc] = {
            "cds_sha256": c["cds_sha256"], "protein_sha256": c["protein_sha256"],
            "exact_cds": c["cds_sha256"] == pub_cds_sha, "exact_protein": c["protein_sha256"] == pub_prot_sha,
            "fixed_cds_substitutions": len(fixed), "fixed_aa_changing": sum(e["effect"] in {"missense", "nonsense"} for e in fixed),
            "cds_indels": len(indels), "cds_iupac_codes": len(ambiguous), "protein_identity_pct": prot["protein_identity"],
            "protein_identities": prot["identities"], "reference_coverage_pct": prot["reference_coverage"],
            "complete": c["five_prime_status"].startswith("COMPLETE") and c["three_prime_status"].startswith("COMPLETE"),
            "five_prime_flank_nt": c["five_prime_flank_nt"], "three_prime_flank_nt": c["three_prime_flank_nt"],
            "alt_residues": residue_alternatives(events, pair),
        }

    # --- published_reference_correspondence (ties allowed; never forced)
    exact = [a for a, m in per_candidate.items() if m["exact_cds"] and m["exact_protein"]]
    rank = lambda a: (per_candidate[a]["cds_indels"], per_candidate[a]["fixed_aa_changing"],  # noqa: E731
                      per_candidate[a]["fixed_cds_substitutions"], per_candidate[a]["cds_iupac_codes"])
    if exact:
        best, status = exact, ("UNIQUE" if len(exact) == 1 else "TIED")
    else:
        usable = [a for a, m in per_candidate.items() if m["complete"] and float(m["protein_identity_pct"]) >= 95.0]
        top = [a for a in usable if rank(a) == min(rank(x) for x in usable)] if usable else []
        best, status = top, ("NO_CONFIDENT_MATCH" if not top else "UNIQUE" if len(top) == 1 else "TIED")
    correspondence_evidence = [
        _ev("OBSERVATION", f"{a}: CDS {'identical to' if m['exact_cds'] else 'differs from'} the published CDS "
            f"({m['fixed_cds_substitutions']} fixed substitution(s), {m['cds_iupac_codes']} IUPAC code(s), {m['cds_indels']} indel(s) in the CDS); "
            f"protein {m['protein_identities']}/{len(pub['protein'])} identical residues to the published protein.",
            "nucleotide_comparison.tsv; protein_comparison.tsv")
        for a, m in per_candidate.items()
    ]
    correspondence = {
        "status": status, "best_matching_accessions": best, "evidence": correspondence_evidence,
        "limitations": [
            "Correspondence to the published (Trinity) sequence is not unique biological identity: the published sequence and the TSA "
            "come from different assemblies and possibly different individuals.",
            "A candidate that does not reproduce the published sequence exactly is not thereby invalid: polymorphism, alleles, "
            "assembly consensus coding (IUPAC) and redundancy are all compatible with the observations.",
        ],
    }

    # --- accession: exclusion only for structural reasons, never for variant-level differences
    excluded = {}
    for c in classification:
        a = c["candidate"]
        if not c["competing_for_dsRNase-2"]:
            excluded[a] = f"best protein match is {c['best_reference_by_protein']}, not dsRNase-2"
        elif not per_candidate[a]["complete"]:
            excluded[a] = "CDS is incomplete at 5' and/or 3'"
    remaining = [a for a in names if a not in excluded]
    accession_status = "RESOLVED" if len(remaining) == 1 else "AMBIGUOUS" if len(remaining) > 1 else "UNRESOLVED"
    accession = {
        "status": accession_status, "selected_accession": remaining[0] if accession_status == "RESOLVED" else None,
        "remaining_candidates": remaining,
        "evidence": [
            _ev("OBSERVATION", f"{len(remaining)} TSA records pass the pre-registered identity-competing rule (dsRNase-2 is their best protein match, "
                f"coverage >= {COMPETING_MIN_REF_COVERAGE_PCT:.0f} %) and have complete CDS: {', '.join(remaining)}.", "candidate_classification.tsv"),
            _ev("OBSERVATION", "Excluded as non-competing: " + "; ".join(f"{a} ({why})" for a, why in sorted(excluded.items())), "candidate_classification.tsv"),
            _ev("INFERENCE", excluded_inference(classification), "candidate_classification.tsv; paralogy_control.tsv"),
        ],
        "limitations": [
            "A sequence difference from the published reference is not an exclusion criterion (ADR 0004): alleles, IUPAC consensus coding and assembly redundancy are not excluded.",
            ds3_statement(classification),
        ],
    }

    # --- CDS
    cds_groups: dict[str, list[str]] = defaultdict(list)
    for a in remaining:
        cds_groups[per_candidate[a]["cds_sha256"]].append(a)
    cds_status = "RESOLVED" if len(cds_groups) == 1 else "AMBIGUOUS" if len(cds_groups) > 1 else "UNRESOLVED"
    cds_sha = next(iter(cds_groups)) if cds_status == "RESOLVED" else None
    cds_evidence = [_ev("OBSERVATION", f"Distinct complete CDS among the remaining records: {len(cds_groups)} "
                        f"({'; '.join(f'{sha[:12]}: {accs}' for sha, accs in cds_groups.items())}); published CDS sha256 {pub_cds_sha[:12]}.",
                        "candidate_cds.fasta; reference_sequences.fasta")]
    for a in remaining:
        m = per_candidate[a]
        if not m["exact_cds"]:
            cds_evidence.append(_ev("OBSERVATION", f"{a} CDS: {m['fixed_cds_substitutions']} fixed substitution(s) and {m['cds_iupac_codes']} IUPAC code(s) versus the published CDS; "
                                    f"all fixed substitutions synonymous = {m['fixed_aa_changing'] == 0}.", "nucleotide_comparison.tsv"))
    if read_support:
        for row in read_support["rows"]:
            cds_evidence.append(_ev("OBSERVATION", f"Reads ({','.join(read_support['runs'])}) at GITV01008430.1 site {row['site_in_GITV01008430.1']} "
                                    f"({row['GITV01008430.1_base']} vs {row['GITV01012450.1_base']}; {row['amino_acid_change'] or row['effect_in_candidate_vs_published']}): "
                                    f"A={row['A']} C={row['C']} G={row['G']} T={row['T']} -> {row['verdict']}", "read_support.tsv"))
    cds = {"status": cds_status, "sequence_sha256": cds_sha, "supporting_accessions": remaining if cds_status == "RESOLVED" else [],
           "published_cds_sha256": pub_cds_sha, "published_cds_supported_exactly_by": [a for a in remaining if per_candidate[a]["exact_cds"]],
           "evidence": cds_evidence,
           "limitations": ["Two distinct CDS cannot be ranked without evidence that one of them is an artefact; IUPAC codes cannot be resolved from the assembly alone."]}

    # --- protein: plausible alternative residues stay plausible unless reads exclude them
    alt_status: list[dict[str, object]] = []
    plausible_extra = 0
    for a in remaining:
        for e in per_candidate[a]["alt_residues"]:
            verdict = "not tested"
            if read_support:
                site = read_support.get("sites_by_event", {}).get(f"{a}:{e['reference_position']}")
                verdict = site["verdict"] if site else "not tested"
            excluded_by_reads = verdict.startswith("ONLY_") and read_support.get("published_allele_only", {}).get(f"{a}:{e['reference_position']}", False)
            alt_status.append({"candidate": a, "reference_position": e["reference_position"], "residue": e["amino_acid_change"],
                               "read_verdict": verdict, "alternative_excluded": bool(excluded_by_reads)})
            if not excluded_by_reads:
                plausible_extra += 1
    prot_groups: dict[str, list[str]] = defaultdict(list)
    for a in remaining:
        prot_groups[per_candidate[a]["protein_sha256"]].append(a)
    distinct_exact = len(prot_groups)
    compatible_with_published = all(
        per_candidate[a]["exact_protein"] or (per_candidate[a]["fixed_aa_changing"] == 0 and per_candidate[a]["cds_indels"] == 0) for a in remaining)
    if not remaining:
        prot_status, prot_sha = "UNRESOLVED", None
    elif plausible_extra > 0:  # an undetermined residue with a surviving alternative is a second plausible protein
        prot_status, prot_sha = "AMBIGUOUS", None
    elif distinct_exact == 1:
        prot_status, prot_sha = "RESOLVED", next(iter(prot_groups))
    elif compatible_with_published:
        prot_status, prot_sha = "RESOLVED", pub_prot_sha
    else:
        prot_status, prot_sha = "AMBIGUOUS", None
    protein = {
        "status": prot_status, "sequence_sha256": prot_sha,
        "supporting_accessions": remaining if prot_status == "RESOLVED" else [],
        "published_protein_sha256": pub_prot_sha,
        "published_protein_supported_exactly_by": [a for a in remaining if per_candidate[a]["exact_protein"]],
        "residues_with_unresolved_alternatives": alt_status,
        "evidence": [_ev("OBSERVATION", f"Protein of {a}: {m['protein_identities']}/{len(pub['protein'])} residues identical to the published protein, coverage {m['reference_coverage_pct']} %, "
                         f"{len(m['alt_residues'])} residue(s) carrying an IUPAC-ambiguous codon with more than one possible amino acid.", "protein_comparison.tsv")
                     for a, m in per_candidate.items() if a in remaining],
        "limitations": ["A residue encoded by an IUPAC-ambiguous codon is undetermined in the assembly; only reads or independent sequencing can fix it.",
                        "Strict policy (ADR 0004 rule 7): an undetermined residue with more than one plausible amino acid keeps the protein AMBIGUOUS even when one possibility equals the published residue; compatibility with the reference is not resolution of the sequence."],
        "published_protein_compatible": {a: per_candidate[a]["fixed_aa_changing"] == 0 and per_candidate[a]["cds_indels"] == 0 for a in remaining},
        "protein_sequence_resolved": prot_status == "RESOLVED",
    }
    if read_support:
        for row in read_support["rows"]:
            if "[" in str(row["amino_acid_change"]):
                protein["evidence"].append(_ev("OBSERVATION", f"Reads ({','.join(read_support['runs'])}) at the ambiguous codon: A={row['A']} C={row['C']} G={row['G']} T={row['T']} "
                                               f"({row['informative_reads']} informative reads, {row['verdict']}). Insufficient for a unique resolution; the ratio is not used to declare the residue resolved. "
                                               "Compatible with polymorphism, allelic heterogeneity, biological mixture, sequencing error or other unresolved uncertainty.", "read_support.tsv"))

    domain_rows = [f for f in features if str(f["sequence_id"]).endswith(".protein") and str(f["sequence_id"]).split(".")[0] in remaining]
    domain_evidence = [_ev("OBSERVATION", f"{f['sequence_id']}: PF01223 {f['domain_start']}-{f['domain_end']}, score {f['score']}, GA met = {f['meets_GA']}", "protein_features.tsv")
                       for f in domain_rows]
    return {
        "target": "Dmai-dsRNase-2",
        "published_reference_correspondence": correspondence,
        "accession_resolution": accession,
        "cds_resolution": cds,
        "protein_resolution": protein,
        "overall": overall_label(accession_status, cds_status, prot_status),
        "family_domain": {"note": "PF01223 supports family membership only; it does not discriminate dsRNase-1/2/3.", "evidence": domain_evidence},
        "next_discriminating_evidence": [],
        "historical_comparison": historical,
        "per_candidate_metrics": per_candidate,
        "rules": {"competing_min_reference_coverage_pct": COMPETING_MIN_REF_COVERAGE_PCT, "orf_support_min_local_score": ORF_SUPPORT_MIN_SCORE,
                  "discovery_min_union_coverage_pct": DISCOVERY_MIN_UNION_COVERAGE_PCT, "discovery_max_evalue": DISCOVERY_MAX_EVALUE,
                  "adr": "src/workstreams/bioinformatics/decisions/0004-nb01-dsrnase2-identity-criteria.md (Proposed)"},
    }


# --------------------------------------------------------------------------- signal peptide
def parse_deepsig_gff(text: str) -> dict[str, dict[str, object]]:
    """DeepSig tabular/GFF output -> ``{sequence_id: {"signal_peptide": (start, end, score) | None}}``."""
    result: dict[str, dict[str, object]] = {}
    for line in text.splitlines():
        cells = line.rstrip("\n").split("\t")
        if len(cells) < 5:
            continue
        entry = result.setdefault(cells[0], {"signal_peptide": None})
        if cells[2].lower().startswith("signal"):
            entry["signal_peptide"] = (int(cells[3]), int(cells[4]), float(cells[5]) if cells[5] not in {".", ""} else None)
    return result


def signal_rows(predictions: dict[str, dict[str, object]], proteins: dict[str, str], n_terminal: dict[str, str],
                meta: dict[str, object]) -> list[dict[str, object]]:
    """One row per protein. N-terminal completeness is judged BEFORE any prediction is interpreted."""
    rows: list[dict[str, object]] = []
    for name in proteins:
        completeness = n_terminal.get(name, "COMPLETE_PUBLISHED_PROTEIN")
        complete = completeness.startswith("COMPLETE")
        entry = predictions.get(name)
        if not complete:
            call, score, cleavage = "NOT_ASSESSABLE_DUE_TO_N_TERMINAL_INCOMPLETENESS", "", ""
        elif entry is None:
            call, score, cleavage = "NOT_ASSESSED_NO_TOOL_OUTPUT", "", ""
        elif entry["signal_peptide"]:
            start, end, sc = entry["signal_peptide"]
            call, score, cleavage = "SIGNAL_PEPTIDE_PREDICTED", sc, f"after residue {end}"
        else:
            call, score, cleavage = "NO_SIGNAL_PEPTIDE_PREDICTED", "", ""
        rows.append({**meta, "sequence_id": name, "feature": "signal_peptide", "prediction": call, "score": score,
                     "cleavage_site": cleavage, "N_terminal_completeness": completeness})
    return rows


# --------------------------------------------------------------------------- run manifest / provenance
def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "safe.directory=*", "-c", "core.autocrlf=true", *args], cwd=root,
                          capture_output=True, text=True)
    return done.stdout.rstrip("\n")  # keep the leading space of porcelain status lines


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def file_record(root: Path, path: Path, with_lf: bool = False) -> dict[str, object]:
    record: dict[str, object] = {"path": path.resolve().relative_to(root.resolve()).as_posix(),
                                 "sha256": sha256_file(path), "bytes": path.stat().st_size}
    if with_lf:
        record["sha256_lf_normalized"] = lf_sha256(path)
    return record


def list_outputs(root: Path, inv: Path) -> list[dict[str, object]]:
    skip = {"blastdb", "__pycache__"}
    rows = []
    for path in sorted(inv.rglob("*")):
        if path.is_file() and not (set(path.relative_to(inv).parts) & skip) and path.name != "run_manifest.json":
            rows.append(file_record(root, path))
    return rows


def build_run_manifest(root: Path, inv: Path, extra: dict[str, object]) -> dict[str, object]:
    """Execution facts only; interpretation lives in decision.json / README.md."""
    import platform
    raw = inv / "raw"
    commands: list[dict[str, object]] = []
    for path in sorted(raw.glob("commands_*.json")):
        commands.extend(json.loads(path.read_text(encoding="utf-8")))
    scripts = [file_record(root, p) for p in sorted(raw.glob("*.sh"))]
    status = _git(root, "status", "--porcelain")
    manifest_inputs = {
        "tsa": file_record(root, root / "data/external/tsa.GITV.1.fsa_nt.gz"),
        "dataset_manifest": file_record(root, root / "data/reference/manifest.json", with_lf=True),
        "target_anchors": file_record(root, root / "data/reference/target_anchors.tsv", with_lf=True),
        "target_anchor_sequences": file_record(root, root / "data/reference/target_anchor_sequences.fasta", with_lf=True),
        "supplement_S1_pdf": file_record(root, root / "data/external" / S1_SOURCE),
        "supplement_S1_text_layer": file_record(root, inv / S1_TEXT),
        "pfam_PF01223_hmm_gz": file_record(root, raw / "PF01223.hmm.gz"),
        "environment_yml": file_record(root, root / "environment.yml", with_lf=True),
    }
    return {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "investigation": "NB01 dsRNase-2 identity (2026-10-03)",
        "repository_policy": {
            "agents_files_read": sorted(p.relative_to(root).as_posix() for p in (root / ".agents").glob("*")),
            "semantic_type_source": ".agents/commits_and_PR_instructions.txt (type decision order, item 7 -> feat)",
            "branch_structure_source": "existing repository branch precedent (feat/reproducibility-gate, feat/nb01-input-provenance, feat/modeling-reports)",
            "branch_name": _git(root, "branch", "--show-current"),
            "base_branch": "master",
            "base_commit": _git(root, "merge-base", "master", "HEAD"),
            "commit_created": _git(root, "rev-parse", "HEAD") != _git(root, "merge-base", "master", "HEAD"),
            "push_performed": False,
            "pull_request_created": False,
        },
        "git": {
            "head": _git(root, "rev-parse", "HEAD"),
            "dirty_initial": False,
            "dirty_final": bool(status),
            "status_porcelain_final(core.autocrlf=true)": status.splitlines(),
        },
        "platform": {"system": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
                     "conda_environment": os.environ.get("CONDA_DEFAULT_ENV", ""), **extra.get("platform", {})},
        "tools": extra.get("tools", {}),
        "parameters": {
            "blastn_discovery": BLASTN_PARAMS, "tblastn_discovery": TBLASTN_PARAMS,
            "blastn_historical_params": HISTORICAL_BLASTN_PARAMS,
            "outfmt_fields_blastn": BLAST_OUTFMT_FIELDS, "outfmt_fields_tblastn": TBLASTN_OUTFMT_FIELDS,
            "discovery": {"min_union_query_coverage_pct": DISCOVERY_MIN_UNION_COVERAGE_PCT, "max_evalue": DISCOVERY_MAX_EVALUE},
            "orf": {"min_aa": ORF_MIN_AA, "support_min_local_blosum62_score": ORF_SUPPORT_MIN_SCORE},
            "competing": {"min_reference_coverage_pct": COMPETING_MIN_REF_COVERAGE_PCT},
            "nucleotide_alignment": NUC_SCORES, "protein_alignment": {"matrix": "BLOSUM62", "gap_open": 11, "gap_extend": 1},
            "hmmsearch": "-E 10 --domE 10 (GA 23/23 applied afterwards as meets_GA)",
            "read_support": {"anchor_nt": ANCHOR, "informative_min_reads": 20, "allele_min_reads": 5, "allele_min_fraction": 0.05},
        },
        "repository_files_changed": [
            {**file_record(root, root / line[3:].strip().strip('"')), "git_status": line[:2]}
            for line in status.splitlines() if (root / line[3:].strip().strip('"')).is_file()
        ],
        "inputs": manifest_inputs,
        "outputs": list_outputs(root, inv),
        "commands_logged_by_module": commands,
        "scripts_executed": scripts,
        "manual_steps": extra.get("manual_steps", []),
        "tests": extra.get("tests", {}),
        "historical_results": extra.get("historical_results", {}),
        "notes": extra.get("notes", []),
    }


# --------------------------------------------------------------------------- historical comparison
HISTORICAL_DIR = Path("results/bioinformatics/nb01")


def build_historical_comparison(root: Path, inv: Path) -> dict[str, object]:
    """Historical (2026-09-11, Windows) rows versus the canonical re-execution and the new searches.

    Reads the immutable historical files and the Linux reproduction (``historical_reproduction/``);
    never writes to either.
    """
    historical = root / HISTORICAL_DIR
    reproduction = root / INVESTIGATION_DIR / "historical_reproduction"
    rows_hist = [r for r in read_tsv(historical / "target_identity_candidates.tsv") if r["target_id"].startswith("dsRNase")]
    out: dict[str, object] = {
        "historical_environment": {
            "source": "src/workstreams/bioinformatics/runs/2026-09-11_nb01-target-identity-resolution.md; results/bioinformatics/nb01/run_manifest.json",
            "os": "Windows 11 build 10.0.26200", "python": "3.14.0 (.venv)", "blast": "BLAST+ 2.17.0 (NCBI Windows package)",
            "canonical": False,
        },
        "historical_rows": [{k: r[k] for k in ("target_id", "tsa_accession", "identity", "query_coverage", "alignment_length", "bitscore", "resolution_status")}
                            for r in rows_hist],
        "historical_files_sha256": {name: sha256_file(historical / name) for name in
                                    ("target_identity_candidates.tsv", "target_identity_report.json", "run_manifest.json", "target_anchor_report.json")},
    }
    if (reproduction / "target_identity_candidates.tsv").exists():
        report_h = json.loads((historical / "target_identity_report.json").read_text(encoding="utf-8"))
        report_n = json.loads((reproduction / "target_identity_report.json").read_text(encoding="utf-8"))
        lf = {key: lf_sha256(root / report_n["inputs"][key]["path"]) for key in ("target_anchors", "anchor_sequences", "dataset_manifest")}
        out["canonical_reproduction"] = {
            "environment": "WSL2 Ubuntu 24.04, conda env zeaguard (Python 3.12.14, BLAST+ 2.17.0, HMMER 3.4)",
            "candidates_tsv_byte_identical": sha256_file(historical / "target_identity_candidates.tsv") == sha256_file(reproduction / "target_identity_candidates.tsv"),
            "report_fields_that_differ": sorted(
                ["created_utc"] + [f"inputs.{k}.sha256" for k in ("target_anchors", "anchor_sequences", "dataset_manifest")
                                   if report_h["inputs"][k]["sha256"] != report_n["inputs"][k]["sha256"]]),
            "input_hash_differences_explained_by_crlf": all(lf[k] == report_h["inputs"][k]["sha256"] for k in lf),
            "summary_equal": report_h["summary"] == report_n["summary"],
            "tools_equal": report_h["tools"] == report_n["tools"],
        }
    hist_params = {(r["query"], r["subject"]): r for r in read_tsv(inv / "blastn_historical_params_hits.tsv")} if (inv / "blastn_historical_params_hits.tsv").exists() else {}
    comparison_rows = []
    for r in rows_hist:
        query = r["target_id"] + ".cDNA"
        new = hist_params.get((query, r["tsa_accession"]))
        comparison_rows.append({
            "target": r["target_id"], "accession": r["tsa_accession"], "historical_identity": r["identity"],
            "historical_query_coverage_pct": r["query_coverage"],
            "rerun_identity_historical_parameters": new["percent_identity"] if new else "not reported",
            "rerun_alignment_length": new["alignment_length"] if new else "",
            "rerun_matches_historical": (
                not any(q == query for q, _ in hist_params)  # historical "no hit" is reproduced only if the re-run has none either
                if r["tsa_accession"] == "NA"
                else bool(new) and abs(float(new["percent_identity"]) - float(r["identity"])) < 5e-4 and int(new["alignment_length"]) == int(r["alignment_length"])
            ),
        })
    out["rerun_with_historical_parameters"] = comparison_rows
    cov = {}
    path = inv / "blastn_coverage_summary.tsv"
    if path.exists():
        for row in read_tsv(path):
            if row["query"].endswith((".CDS", ".cDNA")) and float(row["query_union_coverage_pct"]) >= DISCOVERY_MIN_UNION_COVERAGE_PCT:
                cov.setdefault(row["query"], {})[row["subject"]] = f"{row['strand']}:{row['query_union_coverage_pct']}%"
    out["new_union_coverage_of_published_sequence"] = cov
    out["notes"] = [
        _ev("OBSERVATION", "The canonical Linux re-execution reproduces the historical candidates table byte for byte; only the timestamp and the CRLF-dependent input hashes differ.", "historical_reproduction/"),
        _ev("OBSERVATION", "The GenBank record of GITV00000000.1 lists BioProject PRJNA631706; data/reference/manifest.json lists PRJNA579843. The manifest was not edited.", "raw/genbank_master_record.txt"),
        _ev("INFERENCE", "Historical query coverage was computed over the whole published cDNA with -max_hsps 1, so it mixes CDS completeness with the length of flanking regions present in the published transcript.", "blastn_coverage_summary.tsv"),
    ]
    return out


# --------------------------------------------------------------------------- end-to-end
def run_investigation(root: Path, inv: Path | None = None, read_counts: Sequence[Path] = (),
                      deepsig_gff: Path | None = None, deepsig_meta: dict[str, object] | None = None) -> dict[str, object]:
    """Re-run every analytic stage from the stored external inputs (S1 text layer, PF01223 profile,
    DeepSig output, read counts). Used for the final reproducibility check; writes only into ``inv``."""
    root = root.resolve()
    inv = (inv or root / INVESTIGATION_DIR).resolve()
    for sub in ("raw", "alignments"):
        (inv / sub).mkdir(parents=True, exist_ok=True)
    log = CommandLog()
    refs = stage_references(root, inv)
    hsps = stage_search(root, inv, refs, log)
    candidates = stage_candidates(inv, hsps)
    accessions = sorted(candidates["discovery"])
    (inv / "raw" / "discovery_set.json").write_text(json.dumps(candidates["discovery"], indent=2) + "\n", encoding="utf-8")
    info = stage_orfs(root, inv, refs, accessions)
    comparison = stage_compare(inv, refs, info)
    crosscheck = stage_crosscheck(inv, comparison, hsps["blastn"], info, log)
    features = stage_features(root, inv, refs, info, log)
    proteins = {r["protein_id"]: r["protein"] for r in refs.values()}
    n_terminal = {}
    for acc, entry in info.items():
        if entry["primary"]:
            proteins[f"{acc}.protein"] = entry["primary"]["protein"].replace(STOP, "")
            n_terminal[f"{acc}.protein"] = entry["primary"]["five_prime"]
    if deepsig_gff is not None:
        features += signal_rows(parse_deepsig_gff(deepsig_gff.read_text(encoding="utf-8")), proteins, n_terminal, deepsig_meta or {})
    write_tsv(inv / "protein_features.tsv", features, sorted({k for r in features for k in r}, key=lambda k: (k != "sequence_id", k)))
    read_support = summarize_reads(inv, comparison, read_counts) if read_counts else None
    historical = build_historical_comparison(root, inv)
    decision = build_decision(refs, info, comparison, features, read_support, historical)
    (inv / "raw" / "commands_run_investigation.json").write_text(json.dumps(log.entries, indent=2) + "\n", encoding="utf-8")
    return {"refs": refs, "info": info, "comparison": comparison, "features": features, "decision": decision,
            "read_support": read_support, "crosscheck": crosscheck, "commands": log.entries}


def summarize_reads(inv: Path, comparison: dict[str, object], count_files: Sequence[Path]) -> dict[str, object]:
    """Merge stored per-run counts and apply the pre-registered interpretation to each site."""
    totals: dict[int, dict[str, int]] = {}
    per_run: dict[str, dict[int, dict[str, int]]] = {}
    for path in count_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for run, sites in data["counts"].items():
            per_run[run] = {int(p): c for p, c in sites.items()}
            for position, counts in sites.items():
                bucket = totals.setdefault(int(position), {"A": 0, "C": 0, "G": 0, "T": 0})
                for base, n in counts.items():
                    bucket[base] += n
    events = [e for e in comparison["events"] if e["pair"] == "GITV01008430.1_vs_GITV01012450.1" and e["event_type"] == "substitution"]
    rows, sites_by_event, published_only = [], {}, {}
    for e in events:
        position = int(e["reference_position"])
        if position not in totals:
            continue
        backbone_base, other = e["reference_base"], e["candidate_base"]
        alleles = [backbone_base] + ([b for b in IUPAC_EXPANSION.get(other, other) if b != backbone_base] if other not in UNAMBIGUOUS_DNA else [other])
        verdict = classify_site_support(totals[position], alleles)
        row = {"site_in_GITV01008430.1": position, "GITV01008430.1_base": backbone_base, "GITV01012450.1_base": other,
               "expected_alleles": "/".join(alleles), "A": totals[position]["A"], "C": totals[position]["C"],
               "G": totals[position]["G"], "T": totals[position]["T"], **verdict,
               "runs": ",".join(sorted(per_run)), "effect_in_candidate_vs_published": e["effect"], "amino_acid_change": e["amino_acid_change"]}
        rows.append(row)
        sites_by_event[f"GITV01012450.1:{_published_position_for(comparison, position)}"] = verdict
        published_only[f"GITV01012450.1:{_published_position_for(comparison, position)}"] = verdict["verdict"] == f"ONLY_{backbone_base}_SUPPORTED"
    write_tsv(inv / "read_support.tsv", rows)
    return {"runs": sorted(per_run), "rows": rows, "sites_by_event": sites_by_event, "published_allele_only": published_only}


def _published_position_for(comparison: dict[str, object], position_in_8430: int) -> object:
    """Map a GITV01008430.1 coordinate to the published-cDNA coordinate used in the published-vs-12450 events."""
    # 8430 and the published cDNA are identical over the shared span; use the published-vs-8430 events' offset
    shift = _alignment_shift(comparison)
    return position_in_8430 - shift


def _alignment_shift(comparison: dict[str, object]) -> int:
    """8430 coordinate minus published coordinate (constant across the identical shared span)."""
    events = [e for e in comparison["events"] if e["pair"] == "dsRNase-2.published_cDNA_vs_GITV01008430.1"
              and e["event_type"] == "insertion" and e["terminal"] and int(e["reference_position"]) == 0]
    return int(events[0]["length"]) if events else 0


def flank_summary(decision: dict[str, object]) -> str:
    return "; ".join(f"{a}: 5' flank {m['five_prime_flank_nt']} nt, 3' flank {m['three_prime_flank_nt']} nt"
                     for a, m in decision["per_candidate_metrics"].items())


def next_evidence(decision: dict[str, object], read_support: dict[str, object] | None) -> list[dict[str, str]]:
    """Concrete next tests for each ambiguity that remains (empty when nothing relevant remains)."""
    items: list[dict[str, str]] = []
    tested_runs = set(read_support["runs"]) if read_support else set()
    acc, cds, prot = (decision[k]["status"] for k in ("accession_resolution", "cds_resolution", "protein_resolution"))
    if prot != "RESOLVED":
        alt = decision["protein_resolution"]["residues_with_unresolved_alternatives"]
        items.append({"question": "Is the alternative residue encoded by the IUPAC-ambiguous codon(s) a real allele "
                                  f"({'; '.join(sorted({str(a['residue']) for a in alt if not a['alternative_excluded']}))})?",
                      "analysis": f"Count alleles at the codon in the SRA runs of {TSA_BIOPROJECT} not yet tested ({', '.join(r for r in TSA_SRA_RUNS if r not in tested_runs)}) with the same "
                                  "anchored-k-mer procedure, or map reads to GITV01008430.1; independently, amplicon Sanger/long-read sequencing of the CDS "
                                  "from the individuals used for dsRNA work (cDNA), which also phases the sites."})
    if cds != "RESOLVED":
        items.append({"question": "Are the fixed and ambiguous CDS differences between GITV01008430.1 and GITV01012450.1 allelic variation or assembly artefacts?",
                      "analysis": "Allele-resolved read evidence at the 7 CDS sites (see read_support.tsv) across all libraries and one amplicon sequenced "
                                  "from cDNA of the target population; the synonymous/ambiguous sites decide only which CDS variants must be avoided or "
                                  "tolerated when choosing dsRNA regions."})
    if acc != "RESOLVED":
        items.append({"question": "Do the two TSA records represent one locus or two?",
                      "analysis": "Genomic DNA PCR/long-read sequencing across the CDS and the divergent flanks (" + flank_summary(decision) +
                                  ") or a D. maidis genome assembly, if one becomes available; reads alone cannot select an accession."})
    return items


def btop_substitutions(hsp: Hsp) -> dict[int, tuple[str, str]]:
    """Mismatch columns of a plus-strand HSP as ``{query_position: (query_base, subject_base)}`` (1-based)."""
    position = hsp.query_interval[0] - 1
    found: dict[int, tuple[str, str]] = {}
    for op, q, s in parse_btop(hsp.btop):
        if op == "=":
            position += 1
        elif op == "X":
            position += 1
            found[position] = (q, s)
        elif op == "I":  # query base against a subject gap: the query position advances
            position += 1
        # op == "D": subject base against a query gap, query position unchanged
    return found


def crosscheck_with_btop(events: Sequence[dict[str, object]], hsps: Sequence[Hsp], pair: str, query: str, subject: str) -> list[dict[str, object]]:
    """Compare substitution events of ``pair`` (reference = BLAST query) with BLAST's own mismatches.

    Only the span covered by a plus-strand HSP is compared; positions are query (reference) coordinates.
    """
    rows: list[dict[str, object]] = []
    for hsp in hsps:
        if hsp.query != query or nb01_identity.canonical_tsa_accession(hsp.subject) != subject or hsp.strand != "plus":
            continue
        lo, hi = hsp.query_interval
        mine = {int(e["reference_position"]): (e["reference_base"], e["candidate_base"]) for e in events
                if e["pair"] == pair and e["event_type"] == "substitution" and lo <= int(e["reference_position"]) <= hi}
        theirs = btop_substitutions(hsp)
        for position in sorted(set(mine) | set(theirs)):
            rows.append({"pair": pair, "hsp_query_span": f"{lo}-{hi}", "reference_position": position,
                         "this_work": "/".join(mine[position]) if position in mine else "",
                         "blast_btop": "/".join(theirs[position]) if position in theirs else "",
                         "agree": mine.get(position) == theirs.get(position)})
        if not rows:
            rows.append({"pair": pair, "hsp_query_span": f"{lo}-{hi}", "reference_position": "", "this_work": "", "blast_btop": "", "agree": True})
    return rows


def stage_crosscheck(inv: Path, comparison: dict[str, object], hsps: Sequence[Hsp], info: dict[str, dict[str, object]],
                     log: CommandLog) -> list[dict[str, object]]:
    """Independent check of the event table against BLAST's own alignments (btop)."""
    events = comparison["events"]
    rows: list[dict[str, object]] = []
    for acc in comparison["ds2_accessions"]:
        rows += crosscheck_with_btop(events, hsps, f"dsRNase-2.published_cDNA_vs_{acc}", "dsRNase-2.cDNA", acc)
    group = comparison["ds2_accessions"]
    for i, a in enumerate(group):
        for b in group[i + 1:]:
            qf, sf = inv / "raw" / f"pair_{a}.fasta", inv / "raw" / f"pair_{b}.fasta"
            qf.write_text(format_fasta([(a, info[a]["seq"])]), newline="\n")
            sf.write_text(format_fasta([(b, info[b]["seq"])]), newline="\n")
            out = inv / "raw" / f"pairwise_blastn_{a}_vs_{b}.outfmt6.tsv"
            log.run(["blastn", "-task", "blastn", "-dust", "no", "-query", str(qf), "-subject", str(sf), "-evalue", "1e-5",
                     "-outfmt", "6 " + " ".join(BLAST_OUTFMT_FIELDS)], stdout_path=out)
            pair_hsps = parse_hsp_table(out.read_text(), BLAST_OUTFMT_FIELDS)
            rows += crosscheck_with_btop(events, pair_hsps, f"{a}_vs_{b}", a, b)
    write_tsv(inv / "btop_crosscheck.tsv", rows, ["pair", "hsp_query_span", "reference_position", "this_work", "blast_btop", "agree"])
    return rows


def format_table(rows: Sequence[dict[str, object]], columns: Sequence[str], max_width: int = 60) -> str:
    """Plain-text table for notebook display (no third-party dependency)."""
    cells = [[str(row.get(col, ""))[:max_width] for col in columns] for row in rows]
    widths = [max([len(col)] + [len(line[i]) for line in cells]) for i, col in enumerate(columns)]
    lines = ["  ".join(col.ljust(widths[i]) for i, col in enumerate(columns)),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(value.ljust(widths[i]) for i, value in enumerate(line)) for line in cells]
    return "\n".join(lines)


def load_investigation_outputs(inv: Path) -> dict[str, object]:
    """Read-only access to a finished investigation directory (for notebooks)."""
    return {
        "decision": json.loads((inv / "decision.json").read_text(encoding="utf-8")),
        "classification": read_tsv(inv / "candidate_classification.tsv"),
        "events": read_tsv(inv / "nucleotide_comparison.tsv"),
        "proteins": read_tsv(inv / "protein_comparison.tsv"),
        "features": read_tsv(inv / "protein_features.tsv"),
        "reads": read_tsv(inv / "read_support.tsv") if (inv / "read_support.tsv").exists() else [],
    }


def cds_sites_from_events(inv: Path, pair: str = "GITV01008430.1_vs_GITV01012450.1", cds: tuple[int, int] = (53, 1477)) -> list[int]:
    """Substitution sites of ``pair`` that lie inside the reference CDS (reference = backbone for read anchors)."""
    return sorted({int(e["reference_position"]) for e in read_tsv(inv / "nucleotide_comparison.tsv")
                   if e["pair"] == pair and e["event_type"] == "substitution" and cds[0] <= int(e["reference_position"]) <= cds[1]})


def finalize_investigation(root: Path, inv: Path) -> dict[str, object]:
    """Write run_manifest.json and provenance.tsv from stored facts (no analysis is repeated)."""
    raw = inv / "raw"
    versions = json.loads((raw / "tool_versions.json").read_text(encoding="utf-8"))
    manual = json.loads((raw / "manual_steps.json").read_text(encoding="utf-8"))
    tests_text = (raw / "pytest_final.txt").read_text(encoding="utf-8") if (raw / "pytest_final.txt").exists() else ""
    counts = {key: int(m.group(1)) if (m := re.search(rf"(\d+) {key}", tests_text)) else 0 for key in ("passed", "failed", "skipped")}
    initial = {}
    for line in (raw / "historical_hashes_initial.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match:
            initial[match.group(2)] = match.group(1)
    final = {path: sha256_file(root / path) for path in initial}
    extra = {
        "tools": versions["tools"], "platform": versions["platform"], "manual_steps": manual,
        "tests": {"command": "python -m pytest -q  (conda env zeaguard)", **counts,
                  "baseline_before_changes": "55 passed (raw/env_probe_and_baseline_tests.txt)", "output_file": "raw/pytest_final.txt"},
        "historical_results": {"sha256_initial": initial, "sha256_final": final, "unchanged": initial == final},
        "notes": ["Reads were streamed and never stored except anchor-bearing reads.",
                  "Cross-platform checks: git state taken with core.autocrlf=true to match the Windows checkout."],
    }
    manifest = build_run_manifest(root, inv, extra)
    (inv / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    rows = [{"step_id": f"M{i:02d}", "step": s["step"], "tool": s["tool"], "command_or_script": s["command"], "inputs": s.get("inputs", ""),
             "outputs": s.get("outputs", ""), "notes": s.get("notes", "")} for i, s in enumerate(manual, start=1)]
    for i, entry in enumerate(manifest["commands_logged_by_module"], start=1):
        rows.append({"step_id": f"C{i:02d}", "step": "command executed by the module", "tool": str(entry["command"]).split()[0],
                     "command_or_script": entry["command"], "inputs": "", "outputs": "", "notes": entry.get("started_utc", "")})
    write_tsv(inv / "provenance.tsv", rows)
    return manifest


# --------------------------------------------------------------------------- P0 molecular checkpoint
CHECKPOINT_DIR_NAME = "checkpoint_p0"


def ambiguous_codon_report(codon: str, published_aa: str) -> dict[str, object]:
    """Classify a possibly IUPAC-ambiguous codon against the published residue.

    ``case_A``: every valid expansion encodes the same amino acid. ``case_B``: more than one amino acid
    is possible. ``case_C``: the published residue is among the possible translations. Expansions are
    enumerated explicitly, never resolved to one arbitrary base.
    """
    codon = codon.upper()
    if len(codon) != 3 or any(base not in IUPAC_EXPANSION for base in codon):
        raise ValueError(f"not a codon: {codon!r}")
    expansions = [a + b + c for a in sorted(IUPAC_EXPANSION[codon[0]]) for b in sorted(IUPAC_EXPANSION[codon[1]])
                  for c in sorted(IUPAC_EXPANSION[codon[2]])]
    amino = sorted({CODON_TABLE[x] for x in expansions})
    return {
        "codon": codon, "ambiguous": any(base not in UNAMBIGUOUS_DNA for base in codon),
        "expansions": expansions, "expansion_translations": ";".join(f"{x}={CODON_TABLE[x]}" for x in expansions),
        "amino_acids": amino, "case_A_all_same_amino_acid": len(amino) == 1,
        "case_B_multiple_amino_acids": len(amino) > 1, "case_C_published_in_possible_set": published_aa in amino,
        "published_aa": published_aa,
    }


def _coding_coordinate(position: int, spec: CdsSpec) -> int:
    """1-based coordinate along the coding orientation of the CDS (1 = first base of ATG)."""
    return spec.end - position + 1 if spec.strand == "-" else position - spec.start + 1


def _as_bool(value: object) -> bool:
    return value in (True, "True", "true", 1, "1")


def _symbol_expansions(symbol: str, strand: str) -> tuple[str, str]:
    """Valid nucleotides of ``symbol`` on the stored (transcript) strand and on the coding strand."""
    stored = sorted(IUPAC_EXPANSION[symbol])
    coding = sorted(reverse_complement(base) for base in stored) if strand == "-" else stored
    return ",".join(stored), ",".join(coding)


def orientation_rows(refs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """S1 transcript -> strand -> CDS -> translated protein -> published protein, checked two independent ways."""
    rows: list[dict[str, object]] = []
    for short, ref in refs.items():
        transcript, protein, cds, p = ref["transcript"], ref["protein"], ref["cds"], ref["placement"]
        strand = p["strand"]
        start, end = p["start"], p["end"]
        stored_slice = transcript[start - 1 : end]  # exactly as printed in S1
        from_slice = reverse_complement(stored_slice) if strand == "-" else stored_slice
        oriented = reverse_complement(transcript) if strand == "-" else transcript
        from_oriented = oriented[p["upstream_nt"] : p["upstream_nt"] + len(cds)]
        translated = translate(from_slice, to_stop=True)
        rows.append({
            "reference": short, "published_transcript_id": ref["transcript_id"], "published_protein_id": ref["protein_id"],
            "S1_transcript_length": len(transcript), "orientation_of_CDS_in_S1_transcript": "reverse (minus) strand" if strand == "-" else "forward (plus) strand",
            "reverse_complement_required": strand == "-", "reading_frame_on_that_strand": p["frame"],
            "CDS_start_in_S1_transcript": start, "CDS_end_in_S1_transcript": end, "CDS_strand": strand,
            "CDS_start_in_coding_orientation": p["upstream_nt"] + 1, "CDS_end_in_coding_orientation": p["upstream_nt"] + len(cds),
            "CDS_length_nt_with_stop": len(cds), "first_codon": cds[:3], "last_codon": cds[-3:],
            "flank_before_start_codon_nt_coding_orientation": p["upstream_nt"], "flank_after_stop_codon_nt_coding_orientation": p["downstream_nt"],
            "translated_protein_length_aa": len(translated), "published_protein_length_aa": len(protein),
            "internal_stop_codons": translated.count(STOP), "translation_equals_published_protein": translated == protein,
            "S1_slice_(reverse_complemented_if_minus)_equals_CDS": from_slice == cds,
            "reverse_complement_of_whole_transcript_slice_equals_CDS": from_oriented == cds,
            "n_placements_of_published_protein_in_six_frames": len(ref["placements"]),
        })
    return rows


def nucleotide_difference_rows(
    events: Sequence[dict[str, object]], pair: str, name_a: str, spec_a: CdsSpec, cds_a: str, name_b: str, spec_b: CdsSpec,
    cds_b: str, published_protein: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Per-position description of the differences of ``pair`` (a = reference column, b = candidate column).

    A defined substitution (both symbols are A/C/G/T) is kept apart from IUPAC uncertainty, which is never
    counted as a biological substitution. Returns ``(difference_rows, ambiguous_codon_rows)``.
    """
    rows: list[dict[str, object]] = []
    codons: list[dict[str, object]] = []
    for event in events:
        if event["pair"] != pair:
            continue
        kind = event["event_type"]
        inside = _as_bool(event["within_inferred_CDS"])
        if kind != "substitution":
            rows.append({
                "position_class": "TERMINAL_INDEL_FLANKING" if _as_bool(event.get("terminal")) else "INDEL", "event_type": kind,
                f"transcript_coord_{name_a}": event["reference_position"], f"transcript_coord_{name_b}": event["candidate_position"],
                "cds_coord": "", "codon_index": "", "codon_position": "", f"base_{name_a}": event["reference_base"] if len(event["reference_base"]) < 15 else f"{len(event['reference_base'])} nt",
                f"base_{name_b}": event["candidate_base"] if len(event["candidate_base"]) < 15 else f"{len(event['candidate_base'])} nt",
                "iupac_symbol_present": "", "other_record_base_in_expansion": "", "expansions_transcript_strand": "", "expansions_coding_strand": "",
                f"codon_{name_a}": "", f"codon_{name_b}": "", f"amino_acids_possible_{name_a}": "", f"amino_acids_possible_{name_b}": "", "published_aa": "",
                "possible_amino_acid_consequence": "", "within_inferred_CDS": inside, "effect": event["effect"], "length_nt": event["length"],
            })
            continue
        pos_a, pos_b = int(event["reference_position"]), int(event["candidate_position"])
        base_a, base_b = event["reference_base"], event["candidate_base"]
        iupac_a, iupac_b = base_a not in UNAMBIGUOUS_DNA, base_b not in UNAMBIGUOUS_DNA
        row: dict[str, object] = {
            "position_class": "IUPAC_AMBIGUITY" if (iupac_a or iupac_b) else "DEFINED_SUBSTITUTION", "event_type": "substitution",
            f"transcript_coord_{name_a}": pos_a, f"transcript_coord_{name_b}": pos_b, "cds_coord": "", "codon_index": "", "codon_position": "",
            f"base_{name_a}": base_a, f"base_{name_b}": base_b,
            "iupac_symbol_present": ("in " + name_a if iupac_a else "") + ("in " + name_b if iupac_b else "") or "no",
            "other_record_base_in_expansion": "", "expansions_transcript_strand": "", "expansions_coding_strand": "",
            f"codon_{name_a}": "", f"codon_{name_b}": "", f"amino_acids_possible_{name_a}": "", f"amino_acids_possible_{name_b}": "", "published_aa": "",
            "possible_amino_acid_consequence": "", "within_inferred_CDS": inside, "effect": event["effect"], "length_nt": 1,
        }
        for symbol, other, label in ((base_b, base_a, name_b), (base_a, base_b, name_a)):
            if symbol not in UNAMBIGUOUS_DNA:
                stored, coding = _symbol_expansions(symbol, spec_a.strand)
                row["other_record_base_in_expansion"] = other in IUPAC_EXPANSION[symbol]
                row["expansions_transcript_strand"] = f"{label}: {stored}"
                row["expansions_coding_strand"] = f"{label}: {coding}"
        if inside:
            coord = _coding_coordinate(pos_a, spec_a)
            index, offset = (coord - 1) // 3 + 1, (coord - 1) % 3 + 1
            row["cds_coord"], row["codon_index"], row["codon_position"] = coord, index, offset
            codon_a, codon_b = cds_a[3 * (index - 1) : 3 * index], cds_b[3 * (index - 1) : 3 * index]
            published = published_protein[index - 1] if index <= len(published_protein) else STOP
            report_a, report_b = ambiguous_codon_report(codon_a, published), ambiguous_codon_report(codon_b, published)
            row.update({f"codon_{name_a}": codon_a, f"codon_{name_b}": codon_b, f"amino_acids_possible_{name_a}": "/".join(report_a["amino_acids"]),
                        f"amino_acids_possible_{name_b}": "/".join(report_b["amino_acids"]), "published_aa": published})
            if row["position_class"] == "IUPAC_AMBIGUITY":
                row["possible_amino_acid_consequence"] = f"{published}{index} -> {{{'/'.join(report_b['amino_acids'] if iupac_b else report_a['amino_acids'])}}}"
                symbol_report = report_b if iupac_b else report_a
                codons.append({
                    "pair": pair, "codon_index": index, "codon_position_of_symbol": offset, "cds_coord": coord,
                    "transcript_coord_" + name_a: pos_a, "transcript_coord_" + name_b: pos_b,
                    "iupac_symbol_on_transcript_strand": base_b if iupac_b else base_a, "nucleotides_possible_transcript_strand": row["expansions_transcript_strand"],
                    "nucleotides_possible_coding_strand": row["expansions_coding_strand"], "ambiguous_codon_coding_strand": symbol_report["codon"],
                    "valid_codon_expansions_and_translations": symbol_report["expansion_translations"],
                    "amino_acids_possible": "/".join(symbol_report["amino_acids"]), "published_aa": published,
                    "case_A_all_expansions_same_amino_acid": symbol_report["case_A_all_same_amino_acid"],
                    "case_B_multiple_amino_acids_possible": symbol_report["case_B_multiple_amino_acids"],
                    "case_C_published_aa_among_possible": symbol_report["case_C_published_in_possible_set"],
                    "codon_in_the_other_record": codon_a if iupac_b else codon_b, "record_with_the_symbol": name_b if iupac_b else name_a, "effect": "ambiguous",
                })
            else:
                row["possible_amino_acid_consequence"] = f"{report_a['amino_acids'][0]}{index}{report_b['amino_acids'][0]}"
        rows.append(row)
    return rows, codons


def _aligned_map(a: str, b: str) -> dict[int, str]:
    """Residue of ``b`` aligned to each (0-based) position of ``a`` in a semi-global alignment."""
    result = align(a, b, "semiglobal", matrix=BLOSUM62)
    mapping: dict[int, str] = {}
    index = -1
    for x, y in zip(result.a_aligned, result.b_aligned):
        if x != "-":
            index += 1
            mapping[index] = y
    return mapping


def discriminating_positions(ds2: str, ds1: str, ds3: str, candidate: str) -> dict[str, object]:
    """Positions where published dsRNase-2 differs from BOTH dsRNase-1 and dsRNase-3 (3-way, ds2 coordinates).

    At each such position the candidate residue is scored as matching dsRNase-2, dsRNase-1, dsRNase-3,
    another residue, an undetermined residue (X) or a gap.
    """
    m1, m3, mc = _aligned_map(ds2, ds1), _aligned_map(ds2, ds3), _aligned_map(ds2, candidate)
    counts = {"matches_dsRNase-2": 0, "matches_dsRNase-1": 0, "matches_dsRNase-3": 0, "other_residue": 0, "undetermined_X": 0, "gap_or_unaligned": 0}
    positions: list[dict[str, object]] = []
    for i, residue in enumerate(ds2):
        r1, r3 = m1.get(i, "-"), m3.get(i, "-")
        if "-" in (r1, r3) or r1 == residue or r3 == residue:
            continue
        c = mc.get(i, "-")
        if c == "-":
            call = "gap_or_unaligned"
        elif c == "X":
            call = "undetermined_X"
        elif c == residue:
            call = "matches_dsRNase-2"
        elif c == r1:
            call = "matches_dsRNase-1"
        elif c == r3:
            call = "matches_dsRNase-3"
        else:
            call = "other_residue"
        counts[call] += 1
        positions.append({"ds2_position": i + 1, "dsRNase-2": residue, "dsRNase-1": r1, "dsRNase-3": r3, "candidate": c, "call": call})
    return {"n_discriminating_positions": len(positions), **counts, "positions": positions}


def paralogy_summary_rows(refs: dict[str, dict[str, object]], proteins: dict[str, str], classification: Sequence[dict[str, str]],
                          control: Sequence[dict[str, str]], cds_vs_published: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []
    for c in classification:
        acc = c["candidate"]
        if acc not in proteins:
            continue
        disc = discriminating_positions(refs["dsRNase-2"]["protein"], refs["dsRNase-1"]["protein"], refs["dsRNase-3"]["protein"], proteins[acc])
        by_ref = {r["published_reference"]: r for r in control if r["candidate"] == acc}
        scores = {k: float(v["identity_over_reference_length_pct"]) for k, v in by_ref.items()}
        best = max(scores.values())
        summary.append({
            "candidate": acc,
            "protein_identity_dsRNase-1_pct": by_ref["dsRNase-1"]["protein_identity_pct"], "protein_identity_dsRNase-2_pct": by_ref["dsRNase-2"]["protein_identity_pct"],
            "protein_identity_dsRNase-3_pct": by_ref["dsRNase-3"]["protein_identity_pct"],
            "reference_coverage_dsRNase-1_pct": by_ref["dsRNase-1"]["reference_coverage_pct"], "reference_coverage_dsRNase-2_pct": by_ref["dsRNase-2"]["reference_coverage_pct"],
            "reference_coverage_dsRNase-3_pct": by_ref["dsRNase-3"]["reference_coverage_pct"], "candidate_coverage_vs_dsRNase-2_pct": by_ref["dsRNase-2"]["candidate_coverage_pct"],
            "CDS_compatibility_with_published_dsRNase-2": cds_vs_published.get(acc, "not alignable at nucleotide level (divergent paralog)"),
            "n_positions_where_dsRNase-2_differs_from_both_paralogs": disc["n_discriminating_positions"],
            **{k: disc[k] for k in ("matches_dsRNase-2", "matches_dsRNase-1", "matches_dsRNase-3", "other_residue", "undetermined_X", "gap_or_unaligned")},
            "five_prime_status": c["five_prime_status"], "three_prime_status": c["three_prime_status"],
            "more_compatible_with_dsRNase-2_than_with_dsRNase-1_or_-3": scores["dsRNase-2"] == best and sum(v == best for v in scores.values()) == 1,
            "best_reference_by_protein": c["best_reference_by_protein"],
        })
        positions += [{"candidate": acc, **p} for p in disc["positions"]]
    return summary, positions


def effective_relation(rows: Sequence[dict[str, object]], codon_rows: Sequence[dict[str, object]]) -> dict[str, object]:
    """CDS and protein relation of two records from a per-position difference table (CDS rows only)."""
    in_cds = [r for r in rows if _as_bool(r["within_inferred_CDS"])]
    defined = [r for r in in_cds if r["position_class"] == "DEFINED_SUBSTITUTION"]
    indels = [r for r in in_cds if r["event_type"] != "substitution"]
    iupac = [r for r in in_cds if r["position_class"] == "IUPAC_AMBIGUITY"]
    incompatible = [r for r in iupac if r["other_record_base_in_expansion"] is False]
    defined_aa = [r for r in defined if r["effect"] in {"missense", "nonsense"}]
    published_excluded = [c for c in codon_rows if not c["case_C_published_aa_among_possible"]]
    multi = [c for c in codon_rows if c["case_B_multiple_amino_acids_possible"]]
    if not defined and not indels and not iupac:
        cds_relation = "IDENTICAL"
    elif not defined and not indels and not incompatible:
        cds_relation = "COMPATIBLE_BUT_INCOMPLETELY_DETERMINED"
    else:
        cds_relation = "DIFFERENT"
    if defined_aa or indels or published_excluded:
        protein_relation = "DIFFERENT"
    elif multi:
        protein_relation = "COMPATIBLE_WITH_UNRESOLVED_RESIDUE"
    else:
        protein_relation = "IDENTICAL"
    return {"cds_relation": cds_relation, "protein_relation": protein_relation, "defined_cds_substitutions": len(defined),
            "defined_cds_indels": len(indels), "iupac_positions_in_cds": len(iupac), "iupac_incompatible_with_other_record": len(incompatible),
            "defined_amino_acid_changes": len(defined_aa), "ambiguous_codons_with_multiple_amino_acids": len(multi),
            "ambiguous_codons_excluding_published_residue": len(published_excluded)}


def build_preliminary_p0_decision(
    classification: Sequence[dict[str, str]], published_correspondence: dict[str, object], relations: dict[str, dict[str, object]],
    pair_relation: dict[str, object], orientation: Sequence[dict[str, object]], paralogy: Sequence[dict[str, object]],
) -> dict[str, object]:
    """Preliminary P0 decision from molecular comparison only (no domain, signal peptide or read evidence).

    Policy (strict, ADR 0004 rule 7): an IUPAC-ambiguous symbol is uncertainty, not a biological substitution,
    but a protein is ``RESOLVED`` only when every compatible record supports the same protein sequence or
    discriminating evidence removes the alternatives. A residue with more than one possible amino acid keeps the
    protein ``AMBIGUOUS`` even when the published residue is one of the possibilities: compatibility with the
    reference is not resolution of the sequence.
    """
    competing = [c["candidate"] for c in classification if _as_bool(c["competing_for_dsRNase-2"])]
    cds_relations = {relations[a]["cds_relation"] for a in competing}
    pair_cds = pair_relation["cds_relation"]
    pub_cds_ok = all(r["translation_equals_published_protein"] for r in orientation)
    accession = "RESOLVED" if len(competing) == 1 else "AMBIGUOUS" if competing else "UNRESOLVED"
    protein_compatible = {a: relations[a]["protein_relation"] != "DIFFERENT" for a in competing}
    if not competing:
        cds, protein = "UNRESOLVED", "UNRESOLVED"
    else:
        cds = "RESOLVED" if (pair_cds in {"IDENTICAL", "COMPATIBLE_BUT_INCOMPLETELY_DETERMINED"} or len(competing) == 1) else "AMBIGUOUS"
        protein = "RESOLVED" if all(relations[a]["protein_relation"] == "IDENTICAL" for a in competing) else "AMBIGUOUS"
    return {
        "published_reference_correspondence": published_correspondence, "accession_resolution": accession, "cds_resolution": cds,
        "protein_resolution": protein, "overall": overall_label(accession, cds, protein), "competing_candidates": competing,
        "protein_distinction": {
            "published_reference_correspondence": published_correspondence["status"],
            "published_protein_compatible": protein_compatible,
            "protein_sequence_resolved": protein == "RESOLVED",
            "rule": "compatibility with the published protein is not resolution of the protein sequence (ADR 0004 rule 7)",
        },
        "pair_relation": pair_relation, "relations_to_published": relations, "s1_orientation_all_verified": pub_cds_ok,
        "cds_relations_to_published": sorted(cds_relations),
    }


def variable_site_context_rows(diff_rows: Sequence[dict[str, object]], features: Sequence[dict[str, str]], protein_id: str) -> list[dict[str, object]]:
    """Where each variable CDS site falls relative to the predicted signal peptide and the PF01223 domain.

    Uses the stored PF01223 and signal peptide rows of ``protein_id``; nothing is re-predicted.
    """
    domain = next(f for f in features if f["sequence_id"] == protein_id and f["feature"] == "PF01223")
    signal = next(f for f in features if f["sequence_id"] == protein_id and f["feature"] == "signal_peptide")
    d_start, d_end = int(domain["domain_start"]), int(domain["domain_end"])
    sp_end = int(re.search(r"(\d+)", signal["cleavage_site"]).group(1)) if signal["prediction"] == "SIGNAL_PEPTIDE_PREDICTED" else 0
    rows = []
    for r in diff_rows:
        if not _as_bool(r["within_inferred_CDS"]) or r["event_type"] != "substitution":
            continue
        residue = int(r["codon_index"])
        in_sp, in_domain = residue <= sp_end, d_start <= residue <= d_end
        region = "signal peptide" if in_sp else "PF01223 domain" if in_domain else "mature protein outside the PF01223 domain"
        rows.append({"residue": residue, "cds_coord": r["cds_coord"], "position_class": r["position_class"], "effect": r["effect"],
                     "possible_amino_acid_consequence": r["possible_amino_acid_consequence"], "region": region,
                     "inside_predicted_signal_peptide": in_sp, "inside_PF01223_domain": in_domain,
                     "signal_peptide_span": f"1-{sp_end}" if sp_end else "none", "PF01223_domain_span": f"{d_start}-{d_end}"})
    return sorted(rows, key=lambda x: x["residue"])


def run_p0_checkpoint(root: Path, inv: Path) -> dict[str, object]:
    """Write ``checkpoint_p0/`` from the stored outputs (nothing else in ``inv`` is touched)."""
    out = inv / CHECKPOINT_DIR_NAME
    out.mkdir(exist_ok=True)
    refs = load_references(inv)
    events = read_tsv(inv / "nucleotide_comparison.tsv")
    classification = read_tsv(inv / "candidate_classification.tsv")
    control = read_tsv(inv / "paralogy_control.tsv")
    cds_seq = {rid.replace(".CDS", ""): seq for rid, _, seq in read_fasta_text((inv / "candidate_cds.fasta").read_text(encoding="ascii"))}
    prot_seq = {rid.replace(".protein", ""): seq for rid, _, seq in read_fasta_text((inv / "candidate_proteins.fasta").read_text(encoding="ascii"))}
    specs = {r["candidate"]: CdsSpec(int(r["cds_start"]), int(r["cds_end"]), r["strand"]) for r in read_tsv(inv / "orf_candidates.tsv") if r["cds_start"]}
    published = refs["dsRNase-2"]
    pub_spec = CdsSpec(published["placement"]["start"], published["placement"]["end"], published["placement"]["strand"])

    orient = orientation_rows(refs)
    write_tsv(out / "s1_orientation_validation.tsv", orient)

    a, b = "GITV01008430.1", "GITV01012450.1"
    pair = f"{a}_vs_{b}"
    diff, codons = nucleotide_difference_rows(events, pair, a, specs[a], cds_seq[a], b, specs[b], cds_seq[b], published["protein"])
    columns = list(dict.fromkeys(k for r in diff for k in r))
    write_tsv(out / "nucleotide_differences_8430_vs_12450.tsv", diff, columns)
    write_tsv(out / "iupac_codon_analysis.tsv", codons)
    if (inv / "protein_features.tsv").exists():
        write_tsv(out / "variable_site_context.tsv", variable_site_context_rows(diff, read_tsv(inv / "protein_features.tsv"), f"{a}.protein"))
    pair_rel = effective_relation(diff, codons)

    relations, cds_vs_pub, all_diff, all_codon = {}, {}, [], []
    for acc in (a, b):
        tag = f"dsRNase-2.published_cDNA_vs_{acc}"
        d, c = nucleotide_difference_rows(events, tag, "published", pub_spec, published["cds"], acc, specs[acc], cds_seq[acc], published["protein"])
        relations[acc] = effective_relation(d, c)
        all_diff += [{"pair": tag, **r} for r in d]
        all_codon += c
        cds_vs_pub[acc] = (f"{relations[acc]['cds_relation']}: {relations[acc]['defined_cds_substitutions']} defined substitution(s), "
                           f"{relations[acc]['iupac_positions_in_cds']} IUPAC position(s) in the CDS")
    write_tsv(out / "nucleotide_differences_published_vs_candidates.tsv", all_diff, list(dict.fromkeys(k for r in all_diff for k in r)))
    summary, positions = paralogy_summary_rows(refs, prot_seq, classification, control, cds_vs_pub)
    write_tsv(out / "paralogy_summary.tsv", summary)
    write_tsv(out / "paralogy_discriminating_positions.tsv", positions)

    pub_cds_sha, pub_prot_sha = sha256_text(published["cds"]), sha256_text(published["protein"])
    exact = [x for x in (a, b) if sha256_text(cds_seq[x]) == pub_cds_sha and sha256_text(prot_seq[x].replace(STOP, "")) == pub_prot_sha]
    corr = {"status": "UNIQUE" if len(exact) == 1 else "TIED" if exact else "NO_CONFIDENT_MATCH", "best_matching_accessions": exact}
    decision = build_preliminary_p0_decision(classification, corr, relations, pair_rel, orient, summary)
    multi = [c for c in codons if c["case_B_multiple_amino_acids_possible"]]
    synonymous_only = [c for c in codons if c["case_A_all_expansions_same_amino_acid"]]
    defined_rows = [r for r in diff if r["position_class"] == "DEFINED_SUBSTITUTION" and _as_bool(r["within_inferred_CDS"])]
    ds2_rows = {r["candidate"]: r for r in summary}
    read_evidence: list[dict[str, str]] = []
    if (inv / "read_support.tsv").exists():  # existing read counts are only reported, never re-analysed or used to resolve
        for row in read_tsv(inv / "read_support.tsv"):
            if "[" in row["amino_acid_change"]:
                read_evidence.append(_ev("OBSERVATION", f"Reads at the ambiguous codon (already obtained, not re-analysed): A={row['A']} C={row['C']} G={row['G']} T={row['T']} "
                                         f"({row['informative_reads']} informative reads, verdict {row['verdict']}). This is insufficient for a unique resolution; the 5:1 ratio is not used to declare the residue resolved. "
                                         "Compatible with polymorphism, allelic heterogeneity, biological mixture, sequencing error or other unresolved uncertainty.", "read_support.tsv"))
    decision["items"] = {
        "published_reference_correspondence": {
            "status": corr["status"], "decisive_evidence": [
                _ev("OBSERVATION", f"{a}: CDS and protein identical to the published ones ({relations[a]['defined_cds_substitutions']} defined substitutions, {relations[a]['iupac_positions_in_cds']} IUPAC positions in the CDS).", "nucleotide_differences_published_vs_candidates.tsv"),
                _ev("OBSERVATION", f"{b}: {relations[b]['defined_cds_substitutions']} defined substitution(s) and {relations[b]['iupac_positions_in_cds']} IUPAC position(s) in the CDS versus the published CDS; no defined amino-acid change.", "nucleotide_differences_published_vs_candidates.tsv")],
            "limitations": ["Correspondence to a published Trinity assembly is not unique biological identity; the TSA and the publication come from different assemblies and possibly different individuals."]},
        "accession_resolution": {
            "status": decision["accession_resolution"], "decisive_evidence": [
                _ev("OBSERVATION", f"Both records have dsRNase-2 as best protein match ({ds2_rows[a]['protein_identity_dsRNase-2_pct']} % and {ds2_rows[b]['protein_identity_dsRNase-2_pct']} %; reference coverage 100 %) and complete CDS; the dsRNase-1 records and the dsRNase-1-like record are excluded by paralogy.", "paralogy_summary.tsv"),
                _ev("INFERENCE", "A difference from the published sequence is not an exclusion criterion; the second record's IUPAC symbols all include the first record's base.", "iupac_codon_analysis.tsv")],
            "limitations": ["No evidence in this comparison selects one record; whether they are one locus, two alleles or redundant assembly output is untested (HYPOTHESIS)."]},
        "cds_resolution": {
            "status": decision["cds_resolution"], "decisive_evidence": [
                _ev("OBSERVATION", f"{len(defined_rows)} defined nucleotide difference in the CDS between the records: " + "; ".join(f"CDS position {r['cds_coord']} ({r['base_' + a]}>{r['base_' + b]}, {r['possible_amino_acid_consequence']}, {r['effect']})" for r in defined_rows) + ".", "nucleotide_differences_8430_vs_12450.tsv"),
                _ev("OBSERVATION", f"{pair_rel['iupac_positions_in_cds']} further CDS positions carry an IUPAC symbol in {b}; each symbol includes the base of {a} ({pair_rel['iupac_incompatible_with_other_record']} incompatible).", "iupac_codon_analysis.tsv"),
                _ev("INFERENCE", "The two CDS are not the same effective sequence because of the defined difference, but they are compatible everywhere else.", "nucleotide_differences_8430_vs_12450.tsv")],
            "limitations": ["The defined difference may be a real variant, a polymorphism or an assembly error; the IUPAC positions are undetermined (uncertainty, not substitutions)."]},
        "protein_resolution": {
            "status": decision["protein_resolution"], "decisive_evidence": [
                _ev("OBSERVATION", f"No defined amino-acid change; {len(synonymous_only)} IUPAC codons encode the same amino acid under every expansion; {len(multi)} codon(s) allow several amino acids: " + "; ".join(f"codon {c['codon_index']} {c['ambiguous_codon_coding_strand']} -> {{{c['amino_acids_possible']}}} (published {c['published_aa']})" for c in multi) + ".", "iupac_codon_analysis.tsv"),
                _ev("OBSERVATION", f"The published protein is compatible with every record (published_protein_compatible = {decision['protein_distinction']['published_protein_compatible']}), but a second amino acid remains possible at the ambiguous residue.", "iupac_codon_analysis.tsv"),
                _ev("INFERENCE", "Strict policy: compatibility with the published residue is not resolution of the protein sequence. The protein stays AMBIGUOUS while another translation is possible and no discriminating evidence removes it.", "ADR 0004 rule 7")] + read_evidence,
            "limitations": ["The residue is undetermined in the second record; K and R both remain possible.",
                            "published_reference_correspondence (UNIQUE), protein compatibility with the published sequence (yes) and protein sequence resolved (no) are three different statements and are kept apart."]},
        "overall": {"status": decision["overall"], "decisive_evidence": [_ev("INFERENCE", "Accession, CDS and protein are all unresolved; the published sequence is reproduced exactly by one record and is compatible with the other.", "this file")],
                    "limitations": ["Preliminary; molecular comparison only."]},
    }
    decision["note"] = ("P0 molecular checkpoint under the strict sequence-resolution policy (ADR 0004 rule 7); same classification as decision.json "
                        "of the full run. GITV01012450.1 is not classified as biologically incorrect: it remains highly compatible with dsRNase-2.")
    (out / "preliminary_p0_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"orientation": orient, "differences": diff, "codons": codons, "pair_relation": pair_rel, "relations": relations,
            "paralogy": summary, "decision": decision}


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="NB01 dsRNase-2 identity investigation (re-runs all stages from stored external inputs)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=None, help="output directory (default: the dated investigation directory)")
    parser.add_argument("--read-counts", nargs="*", default=[], help="read_site_counts_*.json files")
    parser.add_argument("--deepsig-gff", default=None)
    parser.add_argument("--count-anchored", metavar="RUN", default=None,
                        help="count alleles from the saved anchor-bearing reads of RUN (raw/anchored_reads_RUN_m*.txt) and write raw/read_site_counts_RUN.json")
    parser.add_argument("--finalize", action="store_true", help="write run_manifest.json and provenance.tsv from stored facts")
    parser.add_argument("--p0-checkpoint", action="store_true", help="write checkpoint_p0/ (molecular comparison, IUPAC analysis, S1 orientation, paralogy, preliminary decision) from the stored outputs")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    inv = Path(args.out).resolve() if args.out else root / INVESTIGATION_DIR
    if args.count_anchored:
        run = args.count_anchored
        raw = inv / "raw"
        backbone = load_tsa_records(root)["GITV01008430.1"].sequence
        files = {run: {mate: (raw / f"anchored_reads_{run}_m{mate}.txt", raw / f"reads_scanned_{run}_m{mate}.log") for mate in (1, 2)}}
        result = count_anchored_files(backbone, cds_sites_from_events(inv), files)
        (raw / f"read_site_counts_{run}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, indent=1))
        return 0
    if args.p0_checkpoint:
        result = run_p0_checkpoint(root, inv)
        print(json.dumps({k: result["decision"][k] for k in ("accession_resolution", "cds_resolution", "protein_resolution", "overall")}, indent=1))
        return 0
    if args.finalize:
        finalize_investigation(root, inv)
        print("run_manifest.json and provenance.tsv written")
        return 0
    meta = {"tool": "DeepSig", "tool_version": "deepsig-biocomp 0.9 (TensorFlow 2.13.1, Keras 2.13.1; repo commit 727941b1)",
            "model": "euk (models bundled in the repository checkout)"}
    result = run_investigation(root, inv, [Path(p) for p in args.read_counts], Path(args.deepsig_gff) if args.deepsig_gff else None, meta)
    decision = result["decision"]
    decision["next_discriminating_evidence"] = next_evidence(decision, result["read_support"])
    (inv / "decision.json").write_text(json.dumps(decision, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: decision[k]["status"] for k in ("accession_resolution", "cds_resolution", "protein_resolution")}, indent=1), decision["overall"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
