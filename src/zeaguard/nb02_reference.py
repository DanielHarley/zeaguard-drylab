"""NB02 input contract: the pinned NB01 operational reference, re-derived from the TSA.

The pin (``data/reference/nb01_dsrnase2_operational_reference.json``) is the versioned
hand-off from NB01. Nothing in it is trusted blindly: :func:`verify_reference` extracts the
two dsRNase-2 CDS from the hash-validated TSA, re-derives the known variants and re-finds
the published benchmark primers, and fails hard on any divergence. The gitignored NB01
hand-off table under ``results/`` is only an optional cross-check, never an input.

Coordinates: 1-based inclusive, on the CDS in coding (sense) orientation, unless a name says
otherwise (``cds_tx_start``/``cds_tx_end`` are on the stored strand of the TSA record).
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from zeaguard import nb01_identity, nb01_inputs
from zeaguard.nb01_dsrnase_investigation import IUPAC_EXPANSION, STOP, codon_amino_acids, sha256_text, translate

PIN_PATH = Path("data/reference/nb01_dsrnase2_operational_reference.json")
REFERENCE_CHECK_PATH = Path("results/bioinformatics/nb02/reference_check.json")
NB01_HANDOFF_PATH = Path(
    "results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/"
    "checkpoint_p0/handoff_attention_positions.tsv"
)

PIN_KEYS = (
    "schema_version", "kind", "source", "coordinates", "tsa", "records",
    "known_dsrnase2_compatible_records", "variants", "benchmark",
)
RECORD_KEYS = (
    "accession", "role", "record_length", "strand", "cds_tx_start", "cds_tx_end", "cds_length",
    "cds_sha256", "protein_length", "protein_sha256",
)
CLASS_DEFINED = "DEFINED_SUBSTITUTION"
CLASS_IUPAC = "IUPAC_AMBIGUITY"
PUBLISHED_DSRNASE2_CDNA_ID = "TRINITY_DN22752_c0_g2_i1"

# Two semantically separate provenance layers of the benchmark. The sequence layer is recomputed by
# verify_reference; the protocol layer is only promoted after the primary text is read by the agent.
SEQUENCE_VERIFICATION = "VERIFIED_FROM_SUPPLEMENT_AND_REFERENCE"
PROTOCOL_VERIFICATION_STATES = frozenset({"PROJECT_PROVIDED_NOT_AGENT_VERIFIED", "VERIFIED_AGAINST_PRIMARY_TEXT"})


class NB02ContractError(RuntimeError):
    """Raised when the NB01 -> NB02 contract is not reproduced by the recorded inputs."""


def load_pin(root: Path) -> dict[str, Any]:
    path = Path(root) / PIN_PATH
    if not path.is_file():
        raise NB02ContractError(f"pin missing: {PIN_PATH.as_posix()}")
    pin = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in PIN_KEYS if key not in pin]
    if missing:
        raise NB02ContractError(f"pin lacks keys: {missing}")
    for name in ("operational", "sibling"):
        record = pin["records"].get(name)
        if record is None or any(key not in record for key in RECORD_KEYS):
            raise NB02ContractError(f"pin record {name!r} is incomplete")
    return pin


def pin_sha256(root: Path) -> str:
    """sha256 of the pin with CRLF normalised to LF (Windows checkouts)."""
    data = (Path(root) / PIN_PATH).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def tsa_sequences(root: Path, accessions: set[str]) -> tuple[dict[str, str], str]:
    """Stream the manifest-validated TSA and return the requested records and the file sha256."""
    root = Path(root).resolve()
    manifest, files, checks, _ = nb01_inputs.inspect_manifest(root, nb01_identity.DEFAULT_MANIFEST_PATH)
    nb01_inputs.PreconditionReport(tuple(checks)).raise_if_failed()
    if manifest is None or len(files) != 1:
        raise NB02ContractError("exactly one validated primary TSA file is required")
    found: dict[str, str] = {}
    for record in nb01_identity.parse_fasta(root / files[0]["path"]):
        accession = nb01_identity.canonical_tsa_accession(record.identifier)
        if accession in accessions:
            found[accession] = record.sequence.upper()
            if len(found) == len(accessions):
                break
    absent = accessions - set(found)
    if absent:
        raise NB02ContractError(f"records absent from the TSA: {sorted(absent)}")
    return found, str(files[0]["sha256"])


def extract_cds(sequence: str, strand: str, start: int, end: int) -> str:
    """CDS in coding orientation from a record slice given on the stored strand (1-based inclusive)."""
    if strand not in ("+", "-"):
        raise NB02ContractError(f"invalid strand {strand!r}")
    if not 1 <= start <= end <= len(sequence):
        raise NB02ContractError(f"interval {start}-{end} outside the record (length {len(sequence)})")
    segment = sequence[start - 1 : end]
    return nb01_identity.reverse_complement(segment) if strand == "-" else segment


def derive_variants(operational_cds: str, sibling_cds: str) -> list[dict[str, Any]]:
    """Positions where the sibling CDS differs from the operational one, in coding orientation.

    Only equal-length CDS are supported (NB01 recorded 0 indels inside the CDS). The operational
    base must be defined and a sibling IUPAC symbol must include it (otherwise the premise that
    the symbol is mere uncertainty does not hold and the contract fails).
    """
    if len(operational_cds) != len(sibling_cds):
        raise NB02ContractError("CDS lengths differ; the contract only covers indel-free CDS")
    rows: list[dict[str, Any]] = []
    for index, (base, symbol) in enumerate(zip(operational_cds, sibling_cds)):
        if base == symbol:
            continue
        if base not in "ACGT":
            raise NB02ContractError(f"operational CDS is not defined at {index + 1}")
        iupac = symbol not in "ACGT"
        if iupac and base not in IUPAC_EXPANSION.get(symbol, ""):
            raise NB02ContractError(f"sibling symbol {symbol} excludes the operational base at {index + 1}")
        codon_start = index - index % 3
        operational_aa = "".join(sorted(codon_amino_acids(operational_cds[codon_start : codon_start + 3])))
        sibling_aa = "/".join(sorted(codon_amino_acids(sibling_cds[codon_start : codon_start + 3])))
        rows.append({
            "cds_pos": index + 1,
            "codon_index": index // 3 + 1,
            "codon_position": index % 3 + 1,
            "operational_base": base,
            "sibling_symbol": symbol,
            "class": CLASS_IUPAC if iupac else CLASS_DEFINED,
            "operational_amino_acid": operational_aa,
            "sibling_possible_amino_acids": sibling_aa,
        })
    return rows


def find_primer_span(cds: str, forward: str, reverse: str) -> tuple[int, int]:
    """1-based inclusive span between a forward primer and the reverse complement of a reverse primer.

    Each primer must match exactly once; absent or repeated sites are contract errors.
    """
    fw_site = _unique_site(cds, forward.upper(), "forward")
    rv_site = _unique_site(cds, nb01_identity.reverse_complement(reverse), "reverse")
    start, end = fw_site, rv_site + len(reverse) - 1
    if end < start:
        raise NB02ContractError("reverse primer site precedes the forward primer site")
    return start, end


def _unique_site(sequence: str, query: str, label: str) -> int:
    first = sequence.find(query)
    if first < 0:
        raise NB02ContractError(f"{label} primer site not found exactly in the CDS")
    if sequence.find(query, first + 1) >= 0:
        raise NB02ContractError(f"{label} primer site is not unique in the CDS")
    return first + 1


def published_cdna_body(root: Path, forward: str, reverse: str) -> str:
    """Benchmark body re-found in the published dsRNase-2 cDNA (versioned anchor FASTA), coding orientation.

    The cDNA is stored on the opposite strand of its CDS, so both orientations are tried and exactly
    one must carry the primer pair (forward forward, reverse reverse-complemented).
    """
    cdna = next(
        (r.sequence for r in nb01_identity.parse_fasta(Path(root) / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH)
         if r.identifier == PUBLISHED_DSRNASE2_CDNA_ID),
        None,
    )
    if cdna is None:
        raise NB02ContractError(f"{PUBLISHED_DSRNASE2_CDNA_ID} is absent from the versioned anchor FASTA")
    bodies: list[str] = []
    for oriented in (cdna, nb01_identity.reverse_complement(cdna)):
        try:
            start, end = find_primer_span(oriented, forward, reverse)
        except NB02ContractError:
            continue
        bodies.append(oriented[start - 1 : end])
    if len(bodies) != 1:
        raise NB02ContractError("the benchmark primers must match the published cDNA in exactly one orientation")
    return bodies[0]


def _strict_record(sequences: dict[str, str], record: dict[str, Any], problems: list[str]) -> str:
    accession = record["accession"]
    sequence = sequences[accession]
    cds = extract_cds(sequence, record["strand"], record["cds_tx_start"], record["cds_tx_end"])
    protein = translate(cds, to_stop=True)
    observed = {
        "record_length": len(sequence),
        "cds_length": len(cds),
        "cds_sha256": sha256_text(cds),
        "protein_length": len(protein),
        "protein_sha256": sha256_text(protein),
    }
    for key, value in observed.items():
        if record[key] != value:
            problems.append(f"{accession}: {key} pin={record[key]!r} derived={value!r}")
    if not (cds.startswith("ATG") and translate(cds[-3:]) == STOP):
        problems.append(f"{accession}: CDS is not ATG...stop")
    return cds


def verify_reference(root: Path) -> dict[str, Any]:
    """Re-derive and verify everything the pin asserts; raise :class:`NB02ContractError` on any divergence."""
    root = Path(root).resolve()
    pin = load_pin(root)
    operational, sibling = pin["records"]["operational"], pin["records"]["sibling"]
    sequences, tsa_sha = tsa_sequences(root, {operational["accession"], sibling["accession"]})
    problems: list[str] = []
    if tsa_sha != pin["tsa"]["file_sha256"]:
        problems.append(f"TSA sha256 pin={pin['tsa']['file_sha256']} manifest={tsa_sha}")
    operational_cds = _strict_record(sequences, operational, problems)
    sibling_cds = _strict_record(sequences, sibling, problems)
    if set(operational_cds) - set("ACGT"):
        problems.append("operational CDS contains non-ACGT symbols")

    variants = derive_variants(operational_cds, sibling_cds)
    keys = ("cds_pos", "codon_index", "codon_position", "operational_base", "sibling_symbol", "class",
            "operational_amino_acid", "sibling_possible_amino_acids")
    pinned = [{key: row[key] for key in keys} for row in pin["variants"]]
    if pinned != variants:
        problems.append("variant table differs from the one re-derived from the TSA")

    benchmark = _verify_benchmark(
        pin["benchmark"], operational_cds, sibling_cds, [v["cds_pos"] for v in variants], problems, root
    )
    crosscheck = crosscheck_nb01_handoff(root, variants)
    if crosscheck["status"] == "MISMATCH":
        problems.append("local NB01 hand-off table disagrees with the re-derived variants")
    if problems:
        raise NB02ContractError("; ".join(problems))
    return {
        "pin_sha256_lf": pin_sha256(root),
        "tsa_file_sha256": tsa_sha,
        "operational": {key: operational[key] for key in ("accession", "cds_length", "cds_sha256", "protein_sha256")},
        "sibling": {key: sibling[key] for key in ("accession", "cds_length", "cds_sha256", "protein_sha256")},
        "variants": variants,
        "benchmark": benchmark,
        "nb01_handoff_crosscheck": crosscheck,
    }


def _verify_benchmark(
    benchmark: dict[str, Any],
    operational_cds: str,
    sibling_cds: str,
    variant_positions: list[int],
    problems: list[str],
    root: Path | None = None,
) -> dict[str, Any]:
    forward, reverse = benchmark["primers"]["forward"]["sequence"], benchmark["primers"]["reverse"]["sequence"]
    start, end = find_primer_span(operational_cds, forward, reverse)
    body = operational_cds[start - 1 : end]
    interval = benchmark["interval"]
    derived = {"cds_start": start, "cds_end": end, "length_nt": len(body), "sequence_sha256": sha256_text(body)}
    for key, value in derived.items():
        if interval[key] != value:
            problems.append(f"benchmark {key}: pin={interval[key]!r} derived={value!r}")
    tail = len(benchmark["primers"]["t7_tail_5to3"])
    amplicons = benchmark["amplicon_lengths_bp"]
    if amplicons["without_t7_tails"] != len(body) or amplicons["with_t7_tails"] != len(body) + 2 * tail:
        problems.append("benchmark amplicon lengths in Table S1 do not match the mapped span")
    names = [protocol["name"] for protocol in benchmark["protocols"]]
    if names != ["INJECTION_PRECONDITIONING", "ORAL_COFEEDING"]:
        problems.append(f"benchmark protocols must be exactly the two separate protocols, got {names}")
    verification = benchmark.get("verification", {})
    if verification.get("benchmark_sequence_verification") != SEQUENCE_VERIFICATION:
        problems.append("benchmark_sequence_verification must be " + SEQUENCE_VERIFICATION)
    if verification.get("experimental_protocol_verification") not in PROTOCOL_VERIFICATION_STATES:
        problems.append("experimental_protocol_verification is missing or outside its vocabulary")
    for protocol in benchmark["protocols"]:
        if protocol.get("verification") != verification.get("experimental_protocol_verification"):
            problems.append(f"{protocol['name']}: protocol verification differs from experimental_protocol_verification")
    inside = [position for position in variant_positions if start <= position <= end]
    sibling_sites = {}
    for label, primer in (("forward", forward), ("reverse", nb01_identity.reverse_complement(reverse))):
        sibling_sites[label] = "EXACT_MATCH" if primer in sibling_cds else "NO_EXACT_MATCH"
    result = {**derived, "variants_inside": inside, "sibling_primer_sites": sibling_sites}
    if root is not None:
        cdna_body = published_cdna_body(root, forward, reverse)
        result["published_cdna_body"] = "EXACT_MATCH" if cdna_body == body else "DIFFERS"
        if cdna_body != body:
            problems.append("the benchmark body differs between the published cDNA and the operational CDS")
    return result


def crosscheck_nb01_handoff(root: Path, variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the re-derived variants with the local NB01 hand-off table, converting orientation.

    The table stores bases on the transcript strand and ``cds_coord`` in coding orientation; the
    CDS lies on the minus strand, so each base is complemented before comparison.
    """
    path = Path(root) / NB01_HANDOFF_PATH
    if not path.is_file():
        return {"status": "ABSENT", "path": NB01_HANDOFF_PATH.as_posix()}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle, delimiter="\t") if row["cds_coord"].strip().isdigit()]
    table = {
        int(row["cds_coord"]): (
            nb01_identity.reverse_complement(row["base_GITV01008430.1"]),
            nb01_identity.reverse_complement(row["base_GITV01012450.1"]),
            row["class"],
        )
        for row in rows
    }
    derived = {row["cds_pos"]: (row["operational_base"], row["sibling_symbol"], row["class"]) for row in variants}
    return {
        "status": "MATCH" if table == derived else "MISMATCH",
        "path": NB01_HANDOFF_PATH.as_posix(),
        "n_rows": len(table),
    }


def write_reference_check(root: Path) -> Path:
    """Verify the contract and write the (gitignored) report under ``results/bioinformatics/nb02/``."""
    report = verify_reference(root)
    path = Path(root) / REFERENCE_CHECK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path
