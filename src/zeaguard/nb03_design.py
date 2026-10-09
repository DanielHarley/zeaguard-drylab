"""NB03 CP2: every CDS design interval and its descriptive annotations.

Order is increasing length, then increasing CDS start, both with step one.
Each sequence is reconstructed from the verified sense CDS and inclusive coordinates.
DUST runs on each window, in batches by length, using the NB02 default-parameter helper.
No candidate homology search, decisional comparison, cell construction or selection occurs.
"""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import statistics
from typing import Any, Iterator

from zeaguard import nb02_design, nb02_reference, nb03_criteria, nb03_reference
from zeaguard.nb01_dsrnase_investigation import sha256_text

OUTPUT_DIR = Path("results/bioinformatics/nb03/cp2")
BENCHMARK_ID = "BC-BENCH-0215-0587"
WINDOW_COLUMNS = (
    "window_id", "target", "membership", "length_stratum", "cds_start", "cds_end", "length_nt",
    "reference_accession", "reference_cds_sha256", "sequence_sha256", "hard_filters_pass",
    "gc_fraction", "longest_homopolymer", "low_complexity_fraction", "relative_midpoint", "target_region_position",
    "count_intersected_observed_sequence_differences", "intersected_observed_sequence_difference_positions",
    "potential_21nt_window_count", "potential_21nt_windows_intersecting_observed_sequence_differences",
    "potential_21nt_windows_unaffected_count", "fraction_unaffected",
    *nb03_criteria.BENCHMARK_RELATION_DESCRIPTORS,
)
BENCHMARK_COLUMNS = (*WINDOW_COLUMNS, "published_reported_length_nt", "operational_length_nt",
                     "length_discrepancy_status", "experimental_protocol_verification")
FORBIDDEN_COLUMN_FRAGMENTS = nb02_design.FORBIDDEN_COLUMN_FRAGMENTS
OUTPUT_NAMES = ("design_space.tsv", "benchmark_descriptor.tsv", "cp2_summary.json", "run_manifest.json")


class NB03DesignError(RuntimeError):
    """The descriptive design space does not satisfy the verified CP1 contract."""


def design_parameters(registry: dict[str, Any]) -> nb02_design.DesignParameters:
    by_name = {c["name"]: c for c in registry["criteria"]}
    cds, lengths = by_name["inside_operational_cds"]["threshold"], by_name["length_range"]["threshold"]
    strata = by_name["length_strata"]["threshold"]
    terciles = tuple(Fraction(v) for v in by_name["target_region_position"]["threshold"]["terciles"])
    return nb02_design.DesignParameters(
        cds_length=cds["cds_max"] - cds["cds_min"] + 1,
        length_min=lengths["min_nt"], length_max=lengths["max_nt"],
        ranking_length=strata["ranking_length_nt"], benchmark_length=strata["benchmark_comparator_length_nt"],
        sensitivity_lengths=tuple(strata["sensitivity_lengths_nt"]),
        k=by_name["potential_21nt_derived_windows"]["threshold"]["k"], terciles=terciles,
    )


def window_id(length: int, start: int, end: int) -> str:
    if start < 1 or end - start + 1 != length or length < 1:
        raise ValueError("window coordinates must be positive, inclusive and consistent with length")
    return f"BC-L{length}-{start:04d}-{end:04d}"


def iter_intervals(parameters: nb02_design.DesignParameters) -> Iterator[tuple[int, int, int]]:
    """Yield (length, start, end) in canonical geometric order, without any prioritization."""
    for length in range(parameters.length_min, parameters.length_max + 1):
        for start in nb02_design.windows_of_length(parameters.cds_length, length):
            yield length, start, start + length - 1


def passes_hard_filters(sequence: str, start: int, end: int, parameters: nb02_design.DesignParameters) -> bool:
    return (1 <= start <= end <= parameters.cds_length
            and parameters.length_min <= end - start + 1 <= parameters.length_max
            and len(sequence) == end - start + 1 and not set(sequence) - set("ACGT"))


def benchmark_overlap(start: int, end: int, benchmark_start: int, benchmark_end: int) -> dict[str, Any]:
    """Inclusive geometry with explicit denominators and strict containment categories."""
    if not 1 <= start <= end or not 1 <= benchmark_start <= benchmark_end:
        raise ValueError("intervals must be positive, nonempty and inclusive")
    overlap = max(0, min(end, benchmark_end) - max(start, benchmark_start) + 1)
    length, benchmark_length = end - start + 1, benchmark_end - benchmark_start + 1
    if overlap == 0:
        relation = "DISJOINT"
    elif (start, end) == (benchmark_start, benchmark_end):
        relation = "EXACT_MATCH"
    elif overlap == length and length < benchmark_length:
        relation = "FULLY_WITHIN"
    elif overlap == benchmark_length and length > benchmark_length:
        relation = "CONTAINS_BENCHMARK"
    else:
        relation = "PARTIAL_OVERLAP"
    return {"overlap_with_benchmark_nt": overlap, "overlap_fraction_of_candidate": overlap / length,
            "overlap_fraction_of_benchmark": overlap / benchmark_length, "relation_to_benchmark": relation}


def verified_reference(root: Path) -> dict[str, Any]:
    """Consume the CP1 pin, rechecking sequences and differences without launching any BLAST.

    The TSA file is hash-validated, the unique complete ORFs are re-derived, and both CDS,
    every observed difference and the primer-defined benchmark are checked against the pin.
    Reference-placement BLAST and discovery remain CP0 checks, already covered by CP1 tests.
    """
    root = Path(root).resolve()
    registry, pin = nb03_criteria.load_registry(root), nb03_criteria.load_pin(root)
    problems = nb03_criteria.validate_registry_against_pin(registry, pin)
    nb03_criteria.load_validated_membership(root)
    record_sequence, tsa_sha = nb03_reference.tsa_record(root)
    record = nb03_reference.derive_record(nb03_reference.OPERATIONAL_ACCESSION, record_sequence)
    op = pin["operational_reference"]
    keys = ("accession", "record_length", "record_sha256", "strand", "cds_tx_start", "cds_tx_end", "cds_length",
            "cds_sha256", "protein_length", "protein_sha256", "utr5_length", "utr3_length")
    problems.extend(f"operational reference differs from pin: {key}" for key in keys if record[key] != op[key])
    if tsa_sha != pin["tsa"]["file_sha256"]:
        problems.append("TSA hash differs from the CP1 pin")
    if record["iupac_positions"] != op["iupac_metadata"]["positions"]:
        problems.append("operational ambiguity metadata differs from pin")
    stored, _ = nb03_reference.load_published(root)
    published = nb03_reference.derive_record(nb03_reference.PUBLISHED_ID, stored)
    pub = pin["published_reference"]
    if published["record_sha256"] != pub["stored_sha256"] or published["cds_sha256"] != pub["cds_sha256"]:
        problems.append("published cDNA or its sense CDS differs from pin")
    if nb03_reference.observed_sequence_differences(published["_cds"], record["_cds"]) != pin["observed_sequence_differences"]["items"]:
        problems.append("re-derived observed sequence differences differ from pin")
    benchmark = pin["benchmark"]
    span = nb02_reference.find_primer_span(record["_cds"], benchmark["primers"]["forward"]["sequence"],
                                        benchmark["primers"]["reverse"]["sequence"])
    coords = benchmark["coordinates"]["cds_sense"]
    body = record["_cds"][coords["start"] - 1:coords["end"]]
    if span != (coords["start"], coords["end"]) or sha256_text(body) != benchmark["body"]["sha256"]:
        problems.append("primer-defined benchmark differs from pin")
    if len(body) != benchmark["operational_sequence_length_nt"]:
        problems.append("operational benchmark length differs from pin")
    if set(record["_cds"]) - set("ACGT"):
        problems.append("the pinned operational CDS must contain only A/C/G/T")
    if problems:
        raise NB03DesignError("; ".join(problems))
    return {"pin": pin, "registry": registry, "operational_cds": record["_cds"], "tsa_file_sha256": tsa_sha}


class DesignContext:
    """Verified sense CDS and descriptive metadata used by every interval."""

    def __init__(self, reference: dict[str, Any], parameters: nb02_design.DesignParameters):
        self.parameters, self.pin, self.cds = parameters, reference["pin"], reference["operational_cds"]
        if len(self.cds) != parameters.cds_length or sha256_text(self.cds) != self.pin["operational_reference"]["cds_sha256"]:
            raise NB03DesignError("CDS length or hash differs from the verified design contract")
        self.positions = [item["cds_position"] for item in self.pin["observed_sequence_differences"]["items"]]
        coord = self.pin["benchmark"]["coordinates"]["cds_sense"]
        self.benchmark = (coord["start"], coord["end"])

    def describe(self, start: int, end: int, masked_fraction: float, *, benchmark: bool = False) -> dict[str, Any]:
        sequence = self.cds[start - 1:end]
        if not passes_hard_filters(sequence, start, end, self.parameters):
            raise NB03DesignError("interval fails a pre-registered structural hard filter")
        if not 0 <= masked_fraction <= 1:
            raise NB03DesignError("DUST masked fraction must lie in [0, 1]")
        if benchmark and (start, end) != self.benchmark:
            raise NB03DesignError("REFERENCE_SET row must match the operational benchmark")
        length = len(sequence)
        inside = nb02_design.variants_in_window(self.positions, start, end)
        potential = length - self.parameters.k + 1
        affected = nb02_design.intercepted_subwindows(start, end, inside, self.parameters.k)
        midpoint, label = nb02_design.region_position(start, end, len(self.cds), self.parameters.terciles)
        overlap = benchmark_overlap(start, end, *self.benchmark)
        row = {
            "window_id": BENCHMARK_ID if benchmark else window_id(length, start, end), "target": "BICC",
            "membership": "REFERENCE_SET" if benchmark else "DESIGN_SPACE",
            "length_stratum": self.parameters.strata.get(length, "CONTINUOUS_DESIGN_SPACE"),
            "cds_start": start, "cds_end": end, "length_nt": length,
            "reference_accession": self.pin["operational_reference"]["accession"],
            "reference_cds_sha256": self.pin["operational_reference"]["cds_sha256"],
            "sequence_sha256": sha256_text(sequence), "hard_filters_pass": True,
            "gc_fraction": f"{nb02_design.gc_fraction(sequence):.6f}",
            "longest_homopolymer": nb02_design.longest_homopolymer(sequence),
            "low_complexity_fraction": f"{masked_fraction:.6f}",
            "relative_midpoint": f"{midpoint:.6f}", "target_region_position": label,
            "count_intersected_observed_sequence_differences": len(inside),
            "intersected_observed_sequence_difference_positions": ",".join(map(str, inside)),
            "potential_21nt_window_count": potential,
            "potential_21nt_windows_intersecting_observed_sequence_differences": affected,
            "potential_21nt_windows_unaffected_count": potential - affected,
            "fraction_unaffected": f"{(potential - affected) / potential:.6f}",
            **overlap,
        }
        for key in ("overlap_fraction_of_candidate", "overlap_fraction_of_benchmark"):
            row[key] = f"{row[key]:.6f}"
        if benchmark:
            b = self.pin["benchmark"]
            row.update(published_reported_length_nt=b["published_reported_body_length_nt"],
                       operational_length_nt=b["operational_sequence_length_nt"],
                       length_discrepancy_status=b["length_discrepancy_status"],
                       experimental_protocol_verification=b["experimental_protocol_verification"])
        return row


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _stratum_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"n_windows": len(rows)}
    for column in ("gc_fraction", "longest_homopolymer", "low_complexity_fraction", "fraction_unaffected"):
        values = [float(row[column]) for row in rows]
        summary[column] = {"min": min(values), "median": round(statistics.median(values), 6),
                           "mean": round(statistics.fmean(values), 6), "max": max(values)}
    counts = Counter(row["count_intersected_observed_sequence_differences"] for row in rows)
    summary["observed_sequence_difference_count_distribution"] = {str(k): counts[k] for k in sorted(counts)}
    relations = Counter(row["relation_to_benchmark"] for row in rows)
    summary["benchmark_relation_distribution"] = {k: relations[k] for k in sorted(nb03_criteria.BENCHMARK_RELATION_CATEGORIES)}
    return summary


def run_cp2(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Write the full descriptive space and a separate reference benchmark, with stable bytes.

    No timestamp, absolute output path, temporary directory or elapsed time is embedded in outputs.
    The manifest hashes the three data outputs; its own SHA-256 is returned to the caller.
    """
    root = Path(root).resolve()
    reference = verified_reference(root)
    parameters = design_parameters(reference["registry"])
    context = DesignContext(reference, parameters)
    for columns in (WINDOW_COLUMNS, BENCHMARK_COLUMNS):
        if any(fragment in c for c in columns for fragment in FORBIDDEN_COLUMN_FRAGMENTS):
            raise NB03DesignError("CP2 columns must remain descriptive")
    out = Path(output_dir) if output_dir is not None else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    dust_version = nb02_design.dustmasker_version()
    lengths, strata = {}, {}
    total = passed = 0
    with (out / "design_space.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WINDOW_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for length in range(parameters.length_min, parameters.length_max + 1):
            starts = nb02_design.windows_of_length(parameters.cds_length, length)
            sequences = {window_id(length, s, s + length - 1): context.cds[s - 1:s + length - 1] for s in starts}
            masked = nb02_design.dustmasker_fractions(sequences)
            rows = [context.describe(s, s + length - 1, masked[window_id(length, s, s + length - 1)]) for s in starts]
            expected = parameters.cds_length - length + 1
            if len(rows) != expected:
                raise NB03DesignError("enumerated stratum differs from the closed-form count")
            writer.writerows(rows)
            n_passed = sum(row["hard_filters_pass"] for row in rows)
            lengths[str(length)] = {"n_windows": len(rows), "expected_by_formula": expected, "hard_filters_pass": n_passed}
            total += len(rows)
            passed += n_passed
            if length in parameters.strata:
                strata[str(length)] = _stratum_summary(rows)
    expected_total = nb02_design.total_windows(parameters.cds_length, parameters.length_min, parameters.length_max)
    if total != expected_total or passed != total:
        raise NB03DesignError("full window space count or structural-filter count violates the contract")
    b_start, b_end = context.benchmark
    b_seq = context.cds[b_start - 1:b_end]
    masked_benchmark = nb02_design.dustmasker_fractions({BENCHMARK_ID: b_seq})
    benchmark = context.describe(b_start, b_end, masked_benchmark[BENCHMARK_ID], benchmark=True)
    with (out / "benchmark_descriptor.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BENCHMARK_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerow(benchmark)
    summary = {"stage": "NB03_CP2_DESCRIPTIVE_DESIGN_SPACE", "enumeration_status": "COMPLETE",
               "canonical_order": ["length_nt", "cds_start"],
               "total_windows": total, "hard_filters_pass": passed, "hard_filters_fail": total - passed,
               "cds_contains_only_acgt": set(context.cds) <= set("ACGT"), "length_counts": lengths,
               "strata": strata, "benchmark": benchmark, "benchmark_rows": 1,
               "benchmark_geometric_design_window_id": window_id(len(b_seq), b_start, b_end),
               "descriptor_precision_decimal_places": 6,
               "small_rna_descriptor": reference["registry"]["policy"]["small_rna_descriptor"]}
    _write_json(out / "cp2_summary.json", summary)
    source_paths = (Path("src/zeaguard/nb03_design.py"), Path("src/zeaguard/nb03_criteria.py"),
                    Path("src/zeaguard/nb03_reference.py"), Path("src/zeaguard/nb02_design.py"),
                    Path("src/zeaguard/nb02_reference.py"), Path("src/zeaguard/nb01_dsrnase_investigation.py"))
    manifest = {"schema_version": 1, "stage": summary["stage"], "git": nb02_design._git_state(root),
                "inputs": {"criteria_registry_sha256_lf": nb03_criteria.registry_sha256(root / nb03_criteria.REGISTRY_PATH),
                           "pin_sha256_lf": nb03_criteria.pin_sha256(root),
                           "membership_sha256_lf": nb03_criteria.registry_sha256(root / nb03_criteria.MEMBERSHIP_PATH),
                           "tsa_file_sha256": reference["tsa_file_sha256"],
                           "operational_cds_sha256": context.pin["operational_reference"]["cds_sha256"]},
                "code_sha256_lf": {p.as_posix(): nb03_criteria.registry_sha256(root / p) for p in source_paths},
                "parameters": {"cds_length_nt": parameters.cds_length, "design_domain": "CDS_ONLY", "orientation": "sense",
                               "length_range_nt": [parameters.length_min, parameters.length_max], "length_step_nt": 1,
                               "start_step_nt": 1, "canonical_order": summary["canonical_order"],
                               "strata": parameters.strata, "k": parameters.k, "terciles": [str(v) for v in parameters.terciles]},
                "tools": {"dustmasker": {"version": dust_version, "parameters": "defaults", "outfmt": "interval",
                                         "masked_nt_convention": "inclusive end - start + 1", "scope": "each window independently"}},
                "counts": {"design_space_rows": total, "hard_filters_pass": passed, "benchmark_rows": 1},
                "analyses_executed": ["sequence_contract_checks_without_blast", "CDS_interval_enumeration",
                                      "composition_and_position_descriptors", "per_window_dustmasker", "observed_difference_descriptors",
                                      "potential_21nt_derived_window_descriptors", "benchmark_overlap_geometry"],
                "not_done": ["candidate_x_TSA_BLAST", "candidate_specificity", "TSA_exact_19mer_or_21mer",
                             "specificity_shuffled_controls", "Pareto", "dominance", "cells", "representatives",
                             "ranking", "shortlist", "Wet_Lab_handoff", "Notebook_03"],
                "outputs_sha256": {name: _sha256(out / name) for name in OUTPUT_NAMES[:-1]}}
    _write_json(out / "run_manifest.json", manifest)
    return {"summary": summary, "manifest": manifest, "outputs_sha256": {name: _sha256(out / name) for name in OUTPUT_NAMES}}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp2(find_project_root())
    print(json.dumps({"enumeration_status": result["summary"]["enumeration_status"], "total_windows": result["summary"]["total_windows"],
                      "outputs_sha256": result["outputs_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
