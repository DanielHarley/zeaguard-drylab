"""NB03 CP0, part 3: reconstruction of the published BicC dsRNA fragment (the "372 bp" benchmark).

The primary evidence is Supplementary Table S1 of Dalaison-Fuentes et al. 2022 (DOI 10.1002/ps.6937), a
user-provided DOCX checked against its sha256: it lists BicC_Fw / BicC_Rv, the T7 versions used for dsRNA
synthesis and the amplicon lengths 372 / 402 bp. The 2023 supplement (PDF) carries the same primers and
lengths and is kept only as a corroboration, never as the basis.

The body is whatever the published primers delimit in the published cDNA, computed deterministically. When it
disagrees with the reported length the two numbers are both preserved and the difference is recorded as an
unresolved publication inconsistency; nothing is truncated, shifted or adjusted, and no cause is asserted.

BODY (what the primers delimit), T7 TAILS (15 nt added by the second PCR) and the full AMPLICON are kept apart.
Two provenance layers stay independent: the sequence layer and the experimental-protocol layer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import zlib
from typing import Any

from zeaguard import nb01_identity, nb02_reference, nb03_reference
from zeaguard.nb01_dsrnase_investigation import sha256_text

TABLE_S1_2022_PATH = Path("data/external/nb03_cp0_sources/dalaison2022_table_s1/ps6937-sup-0006-tables1.docx")
TABLE_S1_2022_SHA256 = "0d235a577ed7ac5782a90e07cdb6679db1ecf2da4d0e9bc79e37bf377b0bc4be"
TABLE_S1_2022_INGESTED_ON = "2026-10-08"
SUPPLEMENT_PATH = Path("data/external/Dalaison-Fuentes2023_S1_mmc1.pdf")
SUPPLEMENT_URL = "https://ars.els-cdn.com/content/image/1-s2.0-S0048357523002833-mmc1.pdf"
SUPPLEMENT_LOCATOR = "Table S1 (primer sequences and amplicon lengths)"
T7_TAIL = "CGACTCACTATAGGG"

# Sequence layer.
SEQUENCE_VERIFIED = "VERIFIED_FROM_PRIMARY_2022_PRIMERS"
SEQUENCE_VERIFIED_DISCREPANT = "VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY"
SEQUENCE_NOT_PRIMARY = "NOT_VERIFIED_AGAINST_THE_2022_PRIMARY_SOURCE"
PRIMERS_VERIFIED_2022 = "VERIFIED_FROM_PRIMARY_2022_TABLE_S1"
SEQUENCE_BASIS = "PRIMARY_2022_PRIMER_DEFINED_RECONSTRUCTION"
DISCREPANCY_UNRESOLVED = "UNRESOLVED_PUBLICATION_INCONSISTENCY"
ROLE_2022 = "PRIMARY_2022_TABLE_S1"
ROLE_2023 = "CORROBORATING_2023_SUPPLEMENT_TABLE_S1"
T7_PROMOTER = "TAATACGACTCACTATAGGG"
# Protocol layer (never inferred from the sequence layer).
PROTOCOL_UNVERIFIED = "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"
PROTOCOL_VERIFIED = "VERIFIED_AGAINST_PRIMARY_TEXT"

_TABLE_MARKER = "BicC_Fw"


class NB03BenchmarkError(RuntimeError):
    """The benchmark cannot be reconstructed without ambiguity."""


# --------------------------------------------------------------------------- Table S1 (2022) from the DOCX
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADER = ["Primer name", "Usage", "Sequence (5'\u20133')+", "Amplicon length (bp)"]


def docx_table_and_notes(data: bytes) -> tuple[list[list[dict[str, Any]]], list[str]]:
    """Rows of the first table (cell text, vertical-merge continuation flag) and the paragraphs outside it.

    The DOCX is untrusted input: it is only read as XML text, never executed, and a DOCTYPE or ENTITY
    declaration is refused before parsing.
    """
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise NB03BenchmarkError("the DOCX declares a DOCTYPE or ENTITY; refused")
    body = ET.fromstring(xml).find(_W + "body")
    if body is None:
        raise NB03BenchmarkError("the DOCX has no body")

    def text(node: Any) -> str:
        return "".join(t.text or "" for t in node.iter(_W + "t"))

    rows: list[list[dict[str, Any]]] = []
    notes: list[str] = []
    for child in body:
        if child.tag == _W + "tbl" and not rows:
            for tr in child.iter(_W + "tr"):
                cells = []
                for tc in tr.findall(_W + "tc"):
                    merge = tc.find(f"{_W}tcPr/{_W}vMerge")
                    continuation = merge is not None and merge.get(_W + "val") != "restart"
                    cells.append({"text": text(tc).strip(), "continuation": continuation})
                rows.append(cells)
        elif child.tag == _W + "p":
            notes.append(text(child).strip())
    if not rows:
        raise NB03BenchmarkError("no table in the DOCX")
    return rows, [n for n in notes if n]


def parse_table_s1_2022(rows: list[list[dict[str, Any]]], notes: list[str]) -> dict[str, Any]:
    """BicC primers, T7 primers, partial T7 promoter note and amplicon lengths; fails if the layout is not the expected one."""
    if [c["text"] for c in rows[0]] != _HEADER:
        raise NB03BenchmarkError("unexpected Table S1 header")
    records: dict[str, dict[str, str]] = {}
    carried = {"usage": "", "length": ""}
    for cells in rows[1:]:
        if len(cells) != 4:
            raise NB03BenchmarkError("unexpected number of cells in a Table S1 row")
        name, usage, sequence, length = cells
        for key, cell in (("usage", usage), ("length", length)):
            if cell["text"]:
                carried[key] = cell["text"]
            elif not cell["continuation"]:
                carried[key] = ""
        records[name["text"]] = {"usage": carried["usage"], "sequence": sequence["text"], "length": carried["length"]}
    need = ("BicC_Fw", "BicC_Rv", "BicC_Fw_T7", "BicC_Rv_T7")
    if any(n not in records for n in need):
        raise NB03BenchmarkError(f"Table S1 lacks one of {need}")
    note = next((n for n in notes if "partial T7 promoter" in n), None)
    compact = re.sub(r"[^ACGT]", "", note.upper().split("T7 PROMOTER:")[-1]) if note else ""
    if not compact.endswith(T7_PROMOTER):
        raise NB03BenchmarkError("the partial T7 promoter note is missing or lists a different promoter")
    forward, reverse = records["BicC_Fw"]["sequence"], records["BicC_Rv"]["sequence"]
    for key in (forward, reverse):
        if not re.fullmatch(r"[ACGT]+", key):
            raise NB03BenchmarkError(f"not a DNA string: {key!r}")
    if T7_PROMOTER[-len(T7_TAIL):] != T7_TAIL:
        raise NB03BenchmarkError("the 15 nt tail is not the 3' end of the T7 promoter")
    if records["BicC_Fw_T7"]["sequence"] != T7_TAIL + forward or records["BicC_Rv_T7"]["sequence"] != T7_TAIL + reverse:
        raise NB03BenchmarkError("the T7 primers are not the plain primers plus the 15 nt partial T7 sequence")
    if records["BicC_Fw_T7"]["usage"] != "dsRNA synthesis" or records["BicC_Rv_T7"]["usage"] != "dsRNA synthesis":
        raise NB03BenchmarkError("the T7 primers are not listed for dsRNA synthesis")
    if records["BicC_Fw"]["length"] != records["BicC_Rv"]["length"] or records["BicC_Fw_T7"]["length"] != records["BicC_Rv_T7"]["length"]:
        raise NB03BenchmarkError("the primer pairs do not share an amplicon length")
    return {
        "bicc_forward": forward, "bicc_reverse": reverse,
        "bicc_forward_t7": {"tail": T7_TAIL, "sequence": records["BicC_Fw_T7"]["sequence"]},
        "bicc_reverse_t7": {"tail": T7_TAIL, "sequence": records["BicC_Rv_T7"]["sequence"]},
        "t7_promoter_full": T7_PROMOTER, "partial_t7_note": note,
        "usage": {"plain": records["BicC_Fw"]["usage"], "t7": records["BicC_Fw_T7"]["usage"]},
        "reported_lengths_bp": {"bicc_template": int(records["BicC_Fw"]["length"]), "bicc_with_t7": int(records["BicC_Fw_T7"]["length"])},
    }


def read_table_s1_2022(root: Path) -> dict[str, Any]:
    """Parse the user-provided 2022 Table S1 after checking its sha256."""
    path = Path(root) / TABLE_S1_2022_PATH
    if not path.is_file():
        raise NB03BenchmarkError(f"the primary 2022 Table S1 is not available at {TABLE_S1_2022_PATH.as_posix()}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != TABLE_S1_2022_SHA256:
        raise NB03BenchmarkError("the 2022 Table S1 does not match the sha256 of the file provided by the user")
    table = parse_table_s1_2022(*docx_table_and_notes(data))
    table["source"] = {
        "source_role": ROLE_2022, "source_description": "Table S1. Primers used for dsRNA synthesis and RT-(q)PCR",
        "source_publication": "Dalaison-Fuentes et al. 2022", "doi": "10.1002/ps.6937",
        "filename": path.name, "size_bytes": len(data), "sha256": TABLE_S1_2022_SHA256,
        "origin": "user-provided primary supplementary file", "ingested_on": TABLE_S1_2022_INGESTED_ON,
        "source_url": None, "source_url_status": "NOT_RECORDED_FOR_USER_PROVIDED_FILE",
    }
    return table


def corroborate_with_2023(root: Path, table_2022: dict[str, Any]) -> dict[str, Any] | None:
    """Same primers and lengths in the 2023 supplement? A cross-check only; the basis stays the 2022 table."""
    if not (Path(root) / SUPPLEMENT_PATH).is_file():
        return None
    older = read_table_s1(root)
    a, b = older["reported_lengths_bp"], table_2022["reported_lengths_bp"]
    agree = ((older["bicc_forward"], older["bicc_reverse"]) == (table_2022["bicc_forward"], table_2022["bicc_reverse"])
             and (a["bicc_template"], a["bicc_with_t7"]) == (b["bicc_template"], b["bicc_with_t7"]))
    return {"source_role": ROLE_2023, "agrees_with_2022_primers_and_lengths": agree, "source": older["source"],
            "note": "corroboration only; the 2023 file is not evidence of what was used in 2022"}


# --------------------------------------------------------------------------- Table S1 from the PDF text layer
def pdf_text_operations(data: bytes) -> list[str]:
    """Text-showing operations of the page stream that holds the primer table (plain flate streams only)."""
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            content = zlib.decompress(match.group(1))
        except zlib.error:
            continue
        operations: list[str] = []
        for shown in re.finditer(rb"\[(.*?)\]\s*TJ|\((.*?)(?<!\\)\)\s*Tj", content, re.S):
            if shown.group(1) is not None:
                operations.append(b"".join(re.findall(rb"\((.*?)(?<!\\)\)", shown.group(1), re.S)).decode("latin-1"))
            else:
                operations.append(shown.group(2).decode("latin-1"))
        if _TABLE_MARKER in operations:
            return operations
    raise NB03BenchmarkError("the primer table was not found in the PDF text layer")


def _value_after(tokens: list[str], name: str, offset: int = 1, occurrence: int = 0) -> str:
    hits = [i for i, token in enumerate(tokens) if token == name]
    if len(hits) <= occurrence:
        raise NB03BenchmarkError(f"{name} not found in Table S1")
    return tokens[hits[occurrence] + offset]


def parse_table_s1(tokens: list[str]) -> dict[str, Any]:
    """BicC primers (plain and T7), tails and amplicon lengths; fails if the layout is not the expected one."""
    numeric = [t for t in tokens if re.fullmatch(r"\d+", t)]
    if len(numeric) < 11:
        raise NB03BenchmarkError("Table S1 amplicon-length column is shorter than expected")
    lengths = [int(t) for t in numeric[-11:]]  # qPCR x5, template amplicons x3 (dsRNase1, dsRNase2, BicC), with T7 x3
    table = {
        "bicc_forward": _value_after(tokens, "BicC_Fw"),
        "bicc_reverse": _value_after(tokens, "BicC_Rv"),
        "bicc_forward_t7": {"tail": _value_after(tokens, "BicC_Fw_T7", 1), "sequence": _value_after(tokens, "BicC_Fw_T7", 2)},
        "bicc_reverse_t7": {"tail": _value_after(tokens, "BicC_Rv_T7", 1), "sequence": _value_after(tokens, "BicC_Rv_T7", 2)},
        "dsrnase2_forward": _value_after(tokens, "dsRNase2_Fw"),
        "dsrnase2_reverse": _value_after(tokens, "dsRNase2_Rv"),
        "reported_lengths_bp": {"dsrnase1_template": lengths[5], "dsrnase2_template": lengths[6], "bicc_template": lengths[7],
                                "dsrnase1_with_t7": lengths[8], "dsrnase2_with_t7": lengths[9], "bicc_with_t7": lengths[10]},
    }
    for key in ("bicc_forward", "bicc_reverse", "dsrnase2_forward", "dsrnase2_reverse"):
        if not re.fullmatch(r"[ACGT]+", table[key]):
            raise NB03BenchmarkError(f"{key} is not a DNA string: {table[key]!r}")
    for key in ("bicc_forward_t7", "bicc_reverse_t7"):
        if table[key]["tail"] != T7_TAIL:
            raise NB03BenchmarkError(f"{key}: unexpected tail {table[key]['tail']!r}")
    if table["bicc_forward_t7"]["sequence"] != table["bicc_forward"] or table["bicc_reverse_t7"]["sequence"] != table["bicc_reverse"]:
        raise NB03BenchmarkError("the T7 primers are not the plain primers plus the tail")
    return table


def read_table_s1(root: Path) -> dict[str, Any]:
    """Parse Table S1 after checking the PDF against the sha256 already pinned by NB02."""
    path = Path(root) / SUPPLEMENT_PATH
    data = path.read_bytes()
    pin = nb02_reference.load_pin(Path(root))
    pinned = pin["benchmark"]["source"]["supplement_sha256"]
    if hashlib.sha256(data).hexdigest() != pinned:
        raise NB03BenchmarkError("the supplement does not match the sha256 pinned by NB02")
    table = parse_table_s1(pdf_text_operations(data))
    # Column-assignment cross-check on the target NB02 already verified: dsRNase-2 must reproduce 330 / 360.
    nb02 = pin["benchmark"]
    if (table["dsrnase2_forward"], table["dsrnase2_reverse"]) != (nb02["primers"]["forward"]["sequence"], nb02["primers"]["reverse"]["sequence"]):
        raise NB03BenchmarkError("the dsRNase-2 primers of Table S1 differ from the NB02 pin")
    reported = table["reported_lengths_bp"]
    if (reported["dsrnase2_template"], reported["dsrnase2_with_t7"]) != (
        nb02["amplicon_lengths_bp"]["without_t7_tails"], nb02["amplicon_lengths_bp"]["with_t7_tails"],
    ):
        raise NB03BenchmarkError("the amplicon-length column does not reproduce the dsRNase-2 lengths of the NB02 pin")
    table["source"] = source_record(path)
    return table


def source_record(path: Path) -> dict[str, Any]:
    from datetime import datetime, timezone

    stat = path.stat()
    return {
        "source_url": SUPPLEMENT_URL, "filename": path.name, "size_bytes": stat.st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "retrieved_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "retrieved_at_basis": "local file modification time (the file predates NB03; the download time was not logged)",
        "source_role": ROLE_2023,
        "locator": SUPPLEMENT_LOCATOR,
    }


# --------------------------------------------------------------------------- mapping the primers
def _count(haystack: str, needle: str) -> int:
    return sum(1 for i in range(len(haystack) - len(needle) + 1) if haystack.startswith(needle, i))


def map_primers(stored: str, forward: str, reverse: str) -> dict[str, Any]:
    """Locate the primer pair in ``stored`` on both strands; each primer must occur exactly once in total.

    Returns the orientation (``stored`` or ``reverse_complement_of_stored``) in which the forward primer reads
    forward, and the span of the body in that orientation and on the stored sequence (1-based inclusive).
    """
    reverse_complement = nb01_identity.reverse_complement
    sites = {name: _count(stored, primer) + _count(stored, reverse_complement(primer))
             for name, primer in (("forward", forward), ("reverse", reverse))}
    if sites != {"forward": 1, "reverse": 1}:
        raise NB03BenchmarkError(f"each primer must occur exactly once on the two strands; occurrences: {sites}")
    for label, oriented in (("stored", stored), ("reverse_complement_of_stored", reverse_complement(stored))):
        try:
            start, end = nb02_reference.find_primer_span(oriented, forward, reverse)
        except nb02_reference.NB02ContractError:
            continue
        stored_span = (start, end) if label == "stored" else (len(stored) - end + 1, len(stored) - start + 1)
        return {"orientation": label, "span_in_orientation": (start, end), "span_on_stored": stored_span,
                "body": oriented[start - 1 : end], "occurrences": sites}
    raise NB03BenchmarkError("the primers are not in a forward/reverse arrangement on the published cDNA")


def assess_length(measured: int, reported_body: int, reported_with_tails: int, tail_length: int) -> dict[str, Any]:
    """Preserve the published and the reconstructed lengths side by side; never adjust either."""
    reconstructed_amplicon = measured + 2 * tail_length
    match = measured == reported_body
    result = {
        "published_reported_body_length_nt": reported_body, "reconstructed_body_length_nt": measured,
        "published_reported_t7_amplicon_length_nt": reported_with_tails,
        "reconstructed_t7_amplicon_length_nt": reconstructed_amplicon,
        "length_discrepancy_nt": measured - reported_body,
        "t7_amplicon_discrepancy_nt": reconstructed_amplicon - reported_with_tails,
        "published_t7_arithmetic_consistent": reported_with_tails - reported_body == 2 * tail_length,
        "length_discrepancy_status": "NONE" if match else DISCREPANCY_UNRESOLVED,
        "status": "MATCH" if match else DISCREPANCY_UNRESOLVED,
        "cause_asserted": False,
    }
    if not match:
        result["hypothesis_not_promoted"] = (
            "a reported length equal to (end - start) of the mapped span would be a non-inclusive count; this is a "
            "separate hypothesis, not an explanation, and no value is adjusted")
    return result


# --------------------------------------------------------------------------- reconstruction
def reconstruct(reference: dict[str, Any], table: dict[str, Any]) -> dict[str, Any]:
    """Body, tails, amplicon and coordinates of the BicC fragment on the stored cDNA, the sense transcript, the record and the CDS."""
    stored, sense = reference["published_stored"], reference["published_sense"]
    published, operational = reference["published"], reference["operational"]
    mapped = map_primers(stored, table["bicc_forward"], table["bicc_reverse"])
    body = mapped["body"]
    sense_is_oriented = (mapped["orientation"] == "reverse_complement_of_stored") == (published["strand"] == "-")
    body_sense = body if sense_is_oriented else nb01_identity.reverse_complement(body)
    if published["strand"] == "+":
        s_lo, s_hi = mapped["span_on_stored"]
    else:
        s_lo = nb03_reference.stored_to_sense(mapped["span_on_stored"][1], len(stored))
        s_hi = nb03_reference.stored_to_sense(mapped["span_on_stored"][0], len(stored))
    if sense[s_lo - 1 : s_hi] != body_sense:
        raise NB03BenchmarkError("the body is not the sense-transcript slice of the mapped span")

    utr5 = published["utr5_length"]
    cds_lo, cds_hi = nb03_reference.sense_to_cds(s_lo, utr5), nb03_reference.sense_to_cds(s_hi, utr5)
    cds_length = operational["cds_length"]
    inside = [p for p in range(cds_lo, cds_hi + 1) if 1 <= p <= cds_length]
    outside = len(body) - len(inside)
    s2r = reference["sense_to_record"]
    record_positions = [s2r.get(p) for p in range(s_lo, s_hi + 1)]
    aligned = [p for p in record_positions if p is not None]
    record_span = (min(aligned), max(aligned)) if aligned else None

    # The body as the operational record carries it, in the same (sense) orientation.
    record_sequence = reference["record_sequence"]
    placement_strand = nb03_reference._sense_strand_on_record(reference["placement"]["hsp"].strand, published["strand"])
    if record_span is not None:
        piece = record_sequence[record_span[0] - 1 : record_span[1]]
        operational_body = piece if placement_strand == "+" else nb01_identity.reverse_complement(piece)
    else:
        operational_body = None
    in_cds = (cds_lo, cds_hi) if cds_lo >= 1 and cds_hi <= cds_length else None
    intercepted = [d["cds_position"] for d in reference["differences"] if d["cds_position"] in set(inside)]

    tail = T7_TAIL
    amplicon = tail + body + nb01_identity.reverse_complement(tail)
    reported = table["reported_lengths_bp"]
    length = assess_length(len(body), reported["bicc_template"], reported["bicc_with_t7"], len(tail))
    primary = table["source"].get("source_role") == ROLE_2022
    if not primary:
        sequence_state = SEQUENCE_NOT_PRIMARY
    else:
        sequence_state = SEQUENCE_VERIFIED if length["status"] == "MATCH" else SEQUENCE_VERIFIED_DISCREPANT
    return {
        "primers_without_t7": {"forward": table["bicc_forward"], "reverse": table["bicc_reverse"]},
        "primers_with_t7": {"forward": tail + table["bicc_forward"], "reverse": tail + table["bicc_reverse"]},
        "t7_tail_5to3": tail, "t7_tail_length_nt": len(tail),
        "primer_occurrences_on_both_strands": mapped["occurrences"],
        "primer_orientation_on_stored_cdna": mapped["orientation"],
        "body": {"sequence": body_sense, "orientation": "CODING_SENSE", "length_nt": len(body), "sha256": sha256_text(body_sense),
                 "t7_tails_in_body": False},
        "amplicon_with_t7_tails": {"length_nt": len(amplicon), "sha256": sha256_text(amplicon),
                                   "structure": "T7_TAIL(15) + BODY + REVERSE_COMPLEMENT(T7_TAIL)(15)"},
        "length_assessment": length,
        "coordinates": {
            "published_cdna_as_stored": {"start": mapped["span_on_stored"][0], "end": mapped["span_on_stored"][1],
                                         "strand_of_body_on_stored": "+" if mapped["orientation"] == "stored" else "-"},
            "published_cdna_sense": {"start": s_lo, "end": s_hi},
            "operational_record": {"accession": operational["accession"], "start": record_span[0] if record_span else None,
                                   "end": record_span[1] if record_span else None,
                                   "strand_of_body": placement_strand, "n_body_positions_without_aligned_base": record_positions.count(None)},
            "cds_sense": {"start": cds_lo, "end": cds_hi, "cds_length": cds_length},
        },
        "design_domain_cds": list(nb03_reference.design_domain(operational)),
        "benchmark_nt_inside_cds": len(inside),
        "benchmark_nt_outside_cds": outside,
        "benchmark_fully_inside_cds": in_cds is not None,
        "body_identical_in_operational_record": operational_body == body_sense,
        "observed_sequence_differences_intercepted": intercepted,
        "primary_2022_primers_verification": PRIMERS_VERIFIED_2022 if primary else "NOT_VERIFIED",
        "benchmark_sequence_basis": SEQUENCE_BASIS if primary else "NON_PRIMARY_PRIMER_SOURCE",
        "benchmark_sequence_verification": sequence_state,
        "benchmark_sequence_verification_detail": (
            "primers read from Table S1 of Dalaison-Fuentes et al. 2022 (user-provided DOCX, sha256 checked) and mapped exactly "
            "and uniquely on the published cDNA; the reconstructed body is the operational benchmark sequence"),
        "published_reported_body_length_nt": length["published_reported_body_length_nt"],
        "reconstructed_body_length_nt": length["reconstructed_body_length_nt"],
        "published_reported_t7_amplicon_length_nt": length["published_reported_t7_amplicon_length_nt"],
        "reconstructed_t7_amplicon_length_nt": length["reconstructed_t7_amplicon_length_nt"],
        "length_discrepancy_nt": length["length_discrepancy_nt"],
        "length_discrepancy_status": length["length_discrepancy_status"],
        "experimental_protocol_verification": PROTOCOL_UNVERIFIED,
        "experimental_protocol_verification_detail": (
            "Table S1 confirms primers, T7 use for dsRNA synthesis and the published lengths; it does not verify the oral/injection "
            "protocol, doses or endpoints, which remain as supplied by the project documents"),
        "source": table["source"],
    }
