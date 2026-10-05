"""NB02 checkpoint 2: the descriptive window space of the operational CDS.

Everything here is descriptive. It enumerates the candidate space (every interval of 300-500 nt,
step 1, inside the 1425 nt operational CDS), describes the published benchmark and the four length
strata, and annotates each window with composition, known variants, potential small-RNA windows
and position. It does NOT run any specificity search, form decisional cells, rank, or select.

All parameters (CDS bounds, length range, strata, k, position terciles) are read from the frozen
registry ``config/nb02_design_criteria.yaml``; nothing numeric about the design is defined here.
Coordinates are 1-based inclusive on the CDS in coding orientation, as in the pin.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Sequence

from zeaguard import nb02_criteria, nb02_reference
from zeaguard.nb01_dsrnase_investigation import sha256_text, write_tsv

OUTPUT_DIR = Path("results/bioinformatics/nb02")

WINDOW_COLUMNS = (
    "candidate_id", "length_stratum", "reference_set_member", "length_nt", "cds_start", "cds_end",
    "transcript_start", "transcript_end", "reference_accession", "reference_sequence_sha256", "sequence_sha256",
    "gc_fraction", "longest_homopolymer", "low_complexity_fraction",
    "n_variant_sites", "variant_positions", "n_defined_variants", "n_iupac_variants", "sites_supported_by_reads",
    "longest_conserved_subregion_nt", "n_potential_windows", "n_windows_intercepting_variants",
    "fraction_potential_windows_unaffected",
    "relative_midpoint", "dist_to_cds_start", "dist_to_cds_end", "target_region_position",
)
SUMMARY_COLUMNS = (
    "length_nt", "n_windows", "n_windows_expected", "gc_min", "gc_max", "n_variant_free_windows",
    "min_variant_sites", "max_variant_sites", "min_fraction_unaffected", "max_fraction_unaffected",
)
TRACK_COLUMNS = (
    "cds_pos", "transcript_pos", "base", "codon_index", "codon_position", "in_start_codon", "in_stop_codon",
    "is_known_variant_site", "variant_class", "sibling_symbol", "nb01_read_support",
)
# CP2 is descriptive: no output column may belong to specificity, cells, ranking or recommendation (CP3/CP4).
FORBIDDEN_COLUMN_FRAGMENTS = (
    "hsp", "blast", "evalue", "e_value", "kmer", "tier", "cell", "rank", "score", "paralog", "co_target",
    "cotarget", "other_transcript", "recommend", "pareto", "shortlist",
)


@dataclass(frozen=True)
class DesignParameters:
    cds_length: int
    length_min: int
    length_max: int
    ranking_length: int
    benchmark_length: int
    sensitivity_lengths: tuple[int, ...]
    k: int
    terciles: tuple[Fraction, Fraction]

    @property
    def strata(self) -> dict[int, str]:
        labels = {length: f"SENSITIVITY_L{length}" for length in self.sensitivity_lengths}
        labels[self.benchmark_length] = f"BENCHMARK_COMPARATOR_L{self.benchmark_length}"
        labels[self.ranking_length] = f"RANKING_L{self.ranking_length}"
        return dict(sorted(labels.items()))


def _criterion(registry: dict[str, Any], name: str) -> dict[str, Any]:
    return next(c for c in registry["criteria"] if c["name"] == name)


def design_parameters(registry: dict[str, Any]) -> DesignParameters:
    cds = _criterion(registry, "inside_operational_cds")["threshold"]
    length = _criterion(registry, "length_range")["threshold"]
    strata = _criterion(registry, "length_strata")["threshold"]
    low, high = (Fraction(value) for value in _criterion(registry, "target_region_position")["threshold"]["terciles"])
    return DesignParameters(
        cds_length=int(cds["cds_max"]) - int(cds["cds_min"]) + 1,
        length_min=int(length["min_nt"]),
        length_max=int(length["max_nt"]),
        ranking_length=int(strata["ranking_length_nt"]),
        benchmark_length=int(strata["benchmark_comparator_length_nt"]),
        sensitivity_lengths=tuple(int(value) for value in strata["sensitivity_lengths_nt"]),
        k=int(_criterion(registry, "potential_small_RNA_windows_unaffected")["threshold"]["k"]),
        terciles=(low, high),
    )


# --------------------------------------------------------------------------- window space
def window_id(length: int, start: int, end: int) -> str:
    return f"D2-L{length:03d}-{start:04d}-{end:04d}"


def windows_of_length(cds_length: int, length: int) -> range:
    """Start positions of every window of ``length`` that fits inside the CDS (step 1, no padding)."""
    return range(1, cds_length - length + 2)


def total_windows(cds_length: int, length_min: int, length_max: int) -> int:
    return sum(cds_length - length + 1 for length in range(length_min, length_max + 1))


# --------------------------------------------------------------------------- descriptors
def gc_fraction(sequence: str) -> float:
    return (sequence.count("G") + sequence.count("C")) / len(sequence)


def longest_homopolymer(sequence: str) -> int:
    longest = run = 1
    for previous, current in zip(sequence, sequence[1:]):
        run = run + 1 if current == previous else 1
        longest = max(longest, run)
    return longest


def variants_in_window(sorted_positions: Sequence[int], start: int, end: int) -> list[int]:
    return list(sorted_positions[bisect_left(sorted_positions, start) : bisect_right(sorted_positions, end)])


def longest_conserved_subregion(start: int, end: int, positions_in_window: Sequence[int]) -> int:
    """Longest stretch of the window (nt) containing no known variable site."""
    edges = [start - 1, *positions_in_window, end + 1]
    return max(right - left - 1 for left, right in zip(edges, edges[1:]))


def intercepted_subwindows(start: int, end: int, positions_in_window: Sequence[int], k: int) -> int:
    """Number of k-nt sub-windows lying inside [start, end] that cover at least one variable site."""
    last_start = end - k + 1
    spans = sorted(
        (max(start, position - k + 1), min(position, last_start)) for position in positions_in_window
    )
    total, covered_to = 0, start - 1
    for low, high in spans:
        if high < low:
            continue
        low = max(low, covered_to + 1)
        if high >= low:
            total += high - low + 1
            covered_to = high
    return total


def region_position(start: int, end: int, cds_length: int, terciles: tuple[Fraction, Fraction]) -> tuple[float, str]:
    """Continuous midpoint and the descriptive label (an annotation: it never orders or groups anything)."""
    exact = Fraction(start + end, 2 * cds_length)  # exact, so a midpoint on a tercile boundary is never misfiled
    midpoint = float(exact)
    if start == 1 or end == cds_length:
        return midpoint, "BOUNDARY"
    if exact < terciles[0]:
        return midpoint, "5_PRIME"
    return midpoint, "CENTRAL" if exact < terciles[1] else "3_PRIME"


def dustmasker_version() -> str:
    process = subprocess.run(["dustmasker", "-version-full"], capture_output=True, text=True, check=True)
    return " | ".join(line.strip() for line in process.stdout.splitlines()[:2])


def dustmasker_fractions(sequences: dict[str, str]) -> dict[str, float]:
    """Fraction of each sequence masked by dustmasker (default parameters, ``-outfmt interval``)."""
    with tempfile.TemporaryDirectory() as directory:
        fasta = Path(directory) / "windows.fasta"
        fasta.write_text("".join(f">{name}\n{sequence}\n" for name, sequence in sequences.items()), encoding="ascii")
        process = subprocess.run(
            ["dustmasker", "-in", str(fasta), "-outfmt", "interval"], capture_output=True, text=True, check=True
        )
    masked = {name: 0 for name in sequences}
    current = None
    for line in process.stdout.splitlines():
        if line.startswith(">"):
            current = line[1:].split()[0]
        elif line.strip() and current is not None:
            low, _, high = line.partition(" - ")
            masked[current] += int(high) - int(low) + 1
    return {name: masked[name] / len(sequence) for name, sequence in sequences.items()}


# --------------------------------------------------------------------------- rows
class _Context:
    """Verified reference data shared by every row."""

    def __init__(self, reference: dict[str, Any], parameters: DesignParameters):
        pin = reference["pin"]
        self.parameters = parameters
        self.cds: str = reference["operational_cds"]
        if len(self.cds) != parameters.cds_length:
            raise nb02_reference.NB02ContractError("the registry CDS bounds differ from the verified CDS length")
        operational = pin["records"]["operational"]
        self.accession: str = operational["accession"]
        self.cds_sha: str = operational["cds_sha256"]
        self.tx_end: int = operational["cds_tx_end"]
        self.variants = {row["cds_pos"]: row for row in pin["variants"]}
        self.positions = sorted(self.variants)
        interval = pin["benchmark"]["interval"]
        self.benchmark = (interval["cds_start"], interval["cds_end"])
        self.benchmark_id: str = pin["benchmark"]["id"]

    def describe(self, start: int, end: int, masked_fraction: float, stratum: str, candidate_id: str | None = None) -> dict[str, Any]:
        length, sequence = end - start + 1, self.cds[start - 1 : end]
        inside = variants_in_window(self.positions, start, end)
        intercepted = intercepted_subwindows(start, end, inside, self.parameters.k)
        potential = length - self.parameters.k + 1
        midpoint, label = region_position(start, end, self.parameters.cds_length, self.parameters.terciles)
        return {
            "candidate_id": candidate_id or window_id(length, start, end),
            "length_stratum": stratum,
            "reference_set_member": (start, end) == self.benchmark,
            "length_nt": length,
            "cds_start": start,
            "cds_end": end,
            "transcript_start": self.tx_end - end + 1,
            "transcript_end": self.tx_end - start + 1,
            "reference_accession": self.accession,
            "reference_sequence_sha256": self.cds_sha,
            "sequence_sha256": sha256_text(sequence),
            "gc_fraction": f"{gc_fraction(sequence):.6f}",
            "longest_homopolymer": longest_homopolymer(sequence),
            "low_complexity_fraction": f"{masked_fraction:.6f}",
            "n_variant_sites": len(inside),
            "variant_positions": ",".join(map(str, inside)),
            "n_defined_variants": sum(self.variants[p]["class"] == nb02_reference.CLASS_DEFINED for p in inside),
            "n_iupac_variants": sum(self.variants[p]["class"] == nb02_reference.CLASS_IUPAC for p in inside),
            "sites_supported_by_reads": ",".join(
                str(p) for p in inside if self.variants[p]["nb01_read_support"] == "BOTH_ALLELES_SUPPORTED"
            ),
            "longest_conserved_subregion_nt": longest_conserved_subregion(start, end, inside),
            "n_potential_windows": potential,
            "n_windows_intercepting_variants": intercepted,
            "fraction_potential_windows_unaffected": f"{1 - intercepted / potential:.6f}",
            "relative_midpoint": f"{midpoint:.6f}",
            "dist_to_cds_start": start - 1,
            "dist_to_cds_end": self.parameters.cds_length - end,
            "target_region_position": label,
        }


def window_space_summary(context: _Context) -> list[dict[str, Any]]:
    """One row per length of the whole continuous space (prefix sums; no per-window sequence work)."""
    params, cds = context.parameters, context.cds
    prefix = [0]
    for base in cds:
        prefix.append(prefix[-1] + (base in "GC"))
    rows = []
    for length in range(params.length_min, params.length_max + 1):
        gcs, counts, fractions = [], [], []
        for start in windows_of_length(params.cds_length, length):
            end = start + length - 1
            inside = variants_in_window(context.positions, start, end)
            counts.append(len(inside))
            gcs.append((prefix[end] - prefix[start - 1]) / length)
            fractions.append(1 - intercepted_subwindows(start, end, inside, params.k) / (length - params.k + 1))
        rows.append({
            "length_nt": length,
            "n_windows": len(counts),
            "n_windows_expected": params.cds_length - length + 1,
            "gc_min": f"{min(gcs):.6f}",
            "gc_max": f"{max(gcs):.6f}",
            "n_variant_free_windows": counts.count(0),
            "min_variant_sites": min(counts),
            "max_variant_sites": max(counts),
            "min_fraction_unaffected": f"{min(fractions):.6f}",
            "max_fraction_unaffected": f"{max(fractions):.6f}",
        })
    return rows


def position_tracks(context: _Context) -> list[dict[str, Any]]:
    rows = []
    for position, base in enumerate(context.cds, start=1):
        variant = context.variants.get(position)
        rows.append({
            "cds_pos": position,
            "transcript_pos": context.tx_end - position + 1,
            "base": base,
            "codon_index": (position - 1) // 3 + 1,
            "codon_position": (position - 1) % 3 + 1,
            "in_start_codon": position <= 3,
            "in_stop_codon": position > context.parameters.cds_length - 3,
            "is_known_variant_site": variant is not None,
            "variant_class": variant["class"] if variant else "",
            "sibling_symbol": variant["sibling_symbol"] if variant else "",
            "nb01_read_support": variant["nb01_read_support"] if variant else "",
        })
    return rows


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git(root: Path, *arguments: str) -> str:
    process = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False)
    return process.stdout.strip() if process.returncode == 0 else "unavailable"


def _git_state(root: Path) -> dict[str, Any]:
    commit = _git(root, "rev-parse", "HEAD")
    if commit == "unavailable":
        return {"commit": None, "branch": None, "dirty": None}
    return {"commit": commit, "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain"))}


def run_cp2(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Verify the contract, describe the window space and write the (gitignored) CP2 outputs."""
    root = Path(root).resolve()
    registry = nb02_criteria.load_registry(root)
    parameters = design_parameters(registry)
    reference = nb02_reference.verified_reference(root)
    context = _Context(reference, parameters)
    out = Path(output_dir) if output_dir else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    summary = window_space_summary(context)
    n_total = sum(row["n_windows"] for row in summary)
    if n_total != total_windows(parameters.cds_length, parameters.length_min, parameters.length_max):
        raise nb02_reference.NB02ContractError("enumerated windows differ from the closed-form count")
    if any(row["n_windows"] != row["n_windows_expected"] for row in summary):
        raise nb02_reference.NB02ContractError("a length stratum has an unexpected number of windows")

    strata = parameters.strata
    spans = [
        (start, start + length - 1, label)
        for length, label in strata.items()
        for start in windows_of_length(parameters.cds_length, length)
    ]
    bench_start, bench_end = context.benchmark
    sequences = {window_id(end - start + 1, start, end): context.cds[start - 1 : end] for start, end, _ in spans}
    sequences[context.benchmark_id] = context.cds[bench_start - 1 : bench_end]
    masked = dustmasker_fractions(sequences)
    windows = [
        context.describe(start, end, masked[window_id(end - start + 1, start, end)], label) for start, end, label in spans
    ]
    benchmark_row = context.describe(
        bench_start, bench_end, masked[context.benchmark_id], strata[parameters.benchmark_length], context.benchmark_id
    )
    benchmark_row["reference_set_member"] = True
    tracks = position_tracks(context)

    for columns in (WINDOW_COLUMNS, SUMMARY_COLUMNS, TRACK_COLUMNS):
        offenders = [c for c in columns if any(f in c for f in FORBIDDEN_COLUMN_FRAGMENTS)]
        if offenders:
            raise nb02_reference.NB02ContractError(f"CP2 outputs must stay descriptive; offending columns: {offenders}")

    files = {
        "window_space_summary.tsv": (summary, SUMMARY_COLUMNS),
        "strata_windows.tsv": (windows, WINDOW_COLUMNS),
        "benchmark_window.tsv": ([benchmark_row], WINDOW_COLUMNS),
        "position_tracks.tsv": (tracks, TRACK_COLUMNS),
    }
    for name, (rows, columns) in files.items():
        write_tsv(out / name, rows, columns)

    manifest = {
        "stage": "NB02 CP2 (descriptive window space; no specificity, cells, ranking or shortlist)",
        "git": _git_state(root),
        "inputs": {
            "criteria_registry_sha256": nb02_criteria.registry_sha256(root / nb02_criteria.REGISTRY_PATH),
            "pin_sha256": reference["report"]["pin_sha256_lf"],
            "tsa_file_sha256": reference["report"]["tsa_file_sha256"],
            "operational_cds_sha256": reference["report"]["operational"]["cds_sha256"],
        },
        "parameters": {
            "cds_length": parameters.cds_length, "length_range_nt": [parameters.length_min, parameters.length_max],
            "strata": {str(length): label for length, label in strata.items()}, "k": parameters.k,
            "terciles": [str(value) for value in parameters.terciles],
        },
        "tools": {"dustmasker": dustmasker_version()},
        "counts": {
            "total_windows_in_continuous_space": n_total,
            "strata_windows_written": len(windows),
            "benchmark_rows": 1,
            "position_track_rows": len(tracks),
            "lengths_summarised": len(summary),
        },
        "benchmark_reference_set_windows_in_strata": sum(1 for row in windows if row["reference_set_member"]),
        "outputs_sha256": {name: _sha256_lf(out / name) for name in files},
        "not_done": ["BLAST specificity search", "decisional cells", "Pareto comparison", "ranking", "shortlist"],
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"manifest": manifest, "summary": summary, "windows": windows, "benchmark": benchmark_row, "tracks": tracks}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp2(find_project_root())
    counts = result["manifest"]["counts"]
    print(f"windows in the continuous space: {counts['total_windows_in_continuous_space']}; strata rows: {counts['strata_windows_written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
