"""NB03 CP4A selection semantics (amendment 4): a data-free contract kernel plus the CP4A materialization.

The kernel functions take explicit values and touch no file. ``run_cp4a`` (bottom) feeds them the certified CP2/CP3
outputs and writes the Pareto, cell and manual-review tables; it recomputes no BLAST, k-mer or shuffle. The decision order is specificity first: Pareto status (per window, within one length stratum), then
difference tiers among NONDOMINATED windows only, then manual review. A cell is a maximal contiguous run of
DESIGN_SPACE windows with the same target, length and decisive signature; it is grouping, never preference.

No score, weight, sum, threshold, hard filter or automatic representative exists. Row ordering is
CANONICAL_DISPLAY_ORDER_ONLY: it is not a ranking and not a tie-breaker.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

from zeaguard import nb02_cells, nb02_criteria, nb03_criteria as criteria, nb03_design as design, nb03_specificity as spec

NONDOMINATED = "NONDOMINATED"
DOMINATED = "DOMINATED"
STRATA_NT = (300, 373, 400, 500)
NOMINAL_REVIEW_LENGTH_NT = 400
MANUAL_REVIEW_INITIAL_STATUS = "PENDING"
DISPLAY_ORDER_CLASSIFICATION = "CANONICAL_DISPLAY_ORDER_ONLY"
DISPLAY_FIELDS = ("length_nt", "pareto_status", "difference_count", "cell_start", "cds_start", "window_id")


class NB03SelectionError(ValueError):
    """The selection contract of amendment 4 is violated."""


@dataclass(frozen=True)
class Window:
    """A DESIGN_SPACE window; ``REFERENCE_SET`` members are rejected by every function below."""

    evidence: criteria.SpecificityEvidence
    cds_start: int
    target: str = "BICC"
    membership: str = "DESIGN_SPACE"

    @property
    def window_id(self) -> str:
        return self.evidence.candidate_id

    @property
    def length_nt(self) -> int:
        return self.evidence.length_nt


@dataclass(frozen=True)
class SelectionCell:
    cell_id: str
    target: str
    length_nt: int
    signature: tuple
    starts: tuple[int, ...]
    window_ids: tuple[str, ...]


def _design_windows(windows: Iterable[Window]) -> list[Window]:
    checked = list(windows)
    if any(w.membership != "DESIGN_SPACE" for w in checked):
        raise NB03SelectionError("only DESIGN_SPACE windows take part; REFERENCE_SET and controls never do")
    if len({w.window_id for w in checked}) != len(checked):
        raise NB03SelectionError("duplicate window ids")
    return checked


def pareto_status(windows: Iterable[Window]) -> dict[str, tuple[str, int]]:
    """``window_id -> (NONDOMINATED | DOMINATED, n_dominators)``, computed separately within each length stratum.

    Dominance is the six-axis rule of the registry on the stored values (no rounding, no normalisation); equality
    on every axis is not dominance. The result does not depend on the difference count.
    """
    checked = _design_windows(windows)
    by_length: dict[int, list[Window]] = {}
    for w in checked:
        by_length.setdefault(w.length_nt, []).append(w)
    status: dict[str, tuple[str, int]] = {}
    for group in by_length.values():
        vectors = Counter(w.evidence.joint for w in group)
        dominators = {v: sum(n for u, n in vectors.items() if nb02_criteria.dominates(u, v)) for v in vectors}
        for w in group:
            n = dominators[w.evidence.joint]
            status[w.window_id] = (DOMINATED if n else NONDOMINATED, n)
    return status


def form_cells(windows: Iterable[Window]) -> list[SelectionCell]:
    """Maximal contiguous runs (CDS start step 1 nt) of one target and length with an identical decisive signature.

    A signature that reappears after an interruption starts a new cell. All strata present are formed.
    """
    checked = _design_windows(windows)
    groups: dict[tuple[str, int], list[Window]] = {}
    for w in checked:
        groups.setdefault((w.target, w.length_nt), []).append(w)
    cells: list[SelectionCell] = []
    for (target, length), group in sorted(groups.items()):
        group.sort(key=lambda w: w.cds_start)
        if len({w.cds_start for w in group}) != len(group):
            raise NB03SelectionError("two windows share a CDS start inside one target and length")
        by_start = {w.cds_start: w for w in group}
        runs = nb02_cells.contiguous_cells([(w.cds_start, criteria.decisive_signature(w.evidence)) for w in group], step=1)
        for number, run in enumerate(runs, 1):
            cells.append(SelectionCell(f"{target}-L{length:03d}-C{number:04d}", target, length, run.signature, run.starts,
                                       tuple(by_start[start].window_id for start in run.starts)))
    return cells


def check_cells_have_uniform_status(cells: Iterable[SelectionCell], status: Mapping[str, tuple[str, int]]) -> None:
    """A cell never mixes DOMINATED and NONDOMINATED windows (the signature contains the Pareto vectors)."""
    for cell in cells:
        if len({status[window_id][0] for window_id in cell.window_ids}) != 1:
            raise NB03SelectionError(f"cell {cell.cell_id} mixes Pareto statuses")


def priority_set(status: Mapping[str, tuple[str, int]]) -> frozenset[str]:
    """The NONDOMINATED DESIGN_SPACE windows. Dominated windows stay in the tables and cells, not here."""
    return frozenset(window_id for window_id, (label, _) in status.items() if label == NONDOMINATED)


def difference_tiers(windows: Iterable[Window], status: Mapping[str, tuple[str, int]]) -> dict[str, int | None]:
    """Tier = ``count_intersected_observed_sequence_differences`` for NONDOMINATED windows, ``None`` for dominated ones.

    A lower tier is preferred, equal counts stay tied, nothing is excluded and there is no threshold. A dominated
    window is never rescued by a low count.
    """
    return {w.window_id: criteria.count_intersected(w.evidence) if status[w.window_id][0] == NONDOMINATED else None
            for w in _design_windows(windows)}


def manual_review_window_ids(windows: Iterable[Window], status: Mapping[str, tuple[str, int]]) -> frozenset[str]:
    """Nominal manual-review scope: every NONDOMINATED L400 window, all difference tiers present, no representative."""
    return frozenset(w.window_id for w in _design_windows(windows)
                     if w.length_nt == NOMINAL_REVIEW_LENGTH_NT and status[w.window_id][0] == NONDOMINATED)


def display_order(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Deterministic row order for files (CANONICAL_DISPLAY_ORDER_ONLY): not a ranking, not a tie-breaker.

    ``pareto_status`` lists NONDOMINATED first; other fields ascend. Statuses, tiers and cell membership are untouched.
    """
    def key(row: Mapping[str, object]) -> tuple:
        return (row["length_nt"], row["pareto_status"] != NONDOMINATED, row["difference_count"], row["cell_start"],
                row["cds_start"], row["window_id"])

    return sorted(rows, key=key)


# --------------------------------------------------------------------------- CP4A materialization (reads the certified CP2/CP3 outputs)
CP2_DIR = design.OUTPUT_DIR
CP3_DIR = spec.OUTPUT_DIR
OUTPUT_DIR = Path("results/bioinformatics/nb03/cp4a")
SELECTION_POLICY_COMMIT = "b8d15f36338922f870ec9f0bdd8004c1c04082ed"
EXPECTED_STRATA = {300: 2038, 373: 1965, 400: 1938, 500: 1838}
UNITS = spec.UNITS
AXIS_COLUMNS = tuple(f"{unit}_{axis}" for unit in ("bicc_like", "dsrnase2") for axis in spec.AXES)
DETERMINISTIC_OUTPUTS = ("pareto_by_stratum.tsv", "cells.tsv", "cell_members.tsv", "manual_review_packet.tsv",
                         "other_transcript_hsp_reference.tsv", "benchmark_comparison.tsv", "cp4a_summary.json")

PARETO_COLUMNS = ("window_id", "length_nt", "cds_start", "cds_end", "pareto_status", "n_dominators",
                  "count_intersected_observed_sequence_differences", "difference_tier", "priority_set", "cell_id", *AXIS_COLUMNS)
CELL_COLUMNS = ("cell_id", "target", "length_nt", "cds_start_min", "cds_start_max", "cds_end_min", "cds_end_max", "n_members",
                "pareto_status", "difference_count", "difference_tier", "bicc_like_vector", "dsrnase2_vector", "manual_review_scope")
MEMBER_COLUMNS = ("cell_id", "window_id", "length_nt", "cds_start", "cds_end", "member_index", "pareto_status")
UNIT_PACKET_METRICS = (*spec.AXES, "aligned_nt_for_best_identity")
OTHER_METRICS = ("n_hsps", "n_subject_records", *UNIT_PACKET_METRICS, "subject_accessions")
KMER_COLUMNS = tuple(f"exact_{k}mer_{unit.lower()}" for k in (19, 21) for unit in UNITS)
CP2_DESCRIPTORS = ("gc_fraction", "longest_homopolymer", "low_complexity_fraction", "relative_midpoint", "target_region_position",
                   "potential_21nt_window_count", "potential_21nt_windows_unaffected_count", "fraction_unaffected",
                   "overlap_with_benchmark_nt", "overlap_fraction_of_candidate", "overlap_fraction_of_benchmark", "relation_to_benchmark")
PACKET_COLUMNS = (
    "window_id", "cds_start", "cds_end", "length_nt", "cell_id", "cell_start", "cell_end", "cell_size",
    "pareto_status", "n_dominators", "difference_tier", "count_intersected_observed_sequence_differences",
    "intersected_observed_sequence_difference_positions",
    *(f"bicc_like_{m}" for m in UNIT_PACKET_METRICS), *(f"dsrnase2_{m}" for m in UNIT_PACKET_METRICS),
    *(f"dsrnase1_{m}" for m in (*spec.AXES, "n_hsps")), *(f"dsrnase3_{m}" for m in (*spec.AXES, "n_hsps")),
    *(f"other_transcript_{m}" for m in OTHER_METRICS), *KMER_COLUMNS, *CP2_DESCRIPTORS, "manual_review_status")
HSP_REFERENCE_COLUMNS = ("window_id", "hsp_id", "subject", "strand", "qstart", "qend", "sstart", "send", "alignment_length",
                         "identical_columns", "local_identity", "reported_identity_percent", "longest_exact_match",
                         "covered_query_nt", "evalue", "bitscore", "mismatch", "gapopen", "gaps", "btop")
BENCHMARK_COLUMNS = ("window_id", "membership", "query_role", "comparison_role", "length_nt", "cds_start", "cds_end", "sequence_sha256",
                     "participates_in_pareto", "participates_in_cells", "pareto_status", "cell_id", "difference_tier",
                     "count_intersected_observed_sequence_differences", *AXIS_COLUMNS,
                     *(f"other_transcript_{m}" for m in OTHER_METRICS), *KMER_COLUMNS)


def _fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def _vector_text(vector: Sequence[float]) -> str:
    return ";".join(_fmt(v) for v in vector)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_table(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_fmt(row[c]) for c in columns])
            count += 1
    return count


def verify_certified_inputs(root: Path) -> dict[str, str]:
    """Every CP2/CP3 scientific input must match the hashes certified by its own run manifest."""
    cp2, cp3 = root / CP2_DIR, root / CP3_DIR
    manifest2 = json.loads((cp2 / "run_manifest.json").read_text(encoding="utf-8"))
    manifest3 = json.loads((cp3 / "run_manifest.json").read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for directory, manifest, names in ((cp2, manifest2, ("design_space.tsv", "benchmark_descriptor.tsv")),
                                       (cp3, manifest3, tuple(manifest3["outputs_sha256"]))):
        for name in names:
            actual = design._sha256(directory / name)
            if actual != manifest["outputs_sha256"][name]:
                raise NB03SelectionError(f"certified input changed: {directory.name}/{name}")
            hashes[f"{directory.name}/{name}"] = actual
    if manifest3["specificity_evidence_basis"] != criteria.CANONICAL_EVIDENCE_BASIS:
        raise NB03SelectionError("CP3 evidence basis is not CANDIDATE_NATIVE_ALIGNMENT")
    if manifest3["inputs"]["cp2_design_space_sha256"] != hashes["cp2/design_space.tsv"]:
        raise NB03SelectionError("CP3 was not built on the present CP2 design space")
    for directory, label in ((cp2, "cp2"), (cp3, "cp3")):
        hashes[f"{label}/run_manifest.json"] = design._sha256(directory / "run_manifest.json")
    return hashes


def _vector(row: Mapping[str, str], unit: str) -> tuple[int, int, float]:
    return (int(row[f"{unit}_longest_exact_match"]), int(row[f"{unit}_covered_nt"]), float(row[f"{unit}_best_local_identity"]))


def load_windows(root: Path) -> tuple[list[Window], dict[str, dict[str, Any]], dict[str, Any]]:
    """Join CP2 geometry/descriptors with CP3 evidence; every id must appear exactly once on both sides."""
    cp2, cp3 = root / CP2_DIR, root / CP3_DIR
    design_rows = [r for r in _read_tsv(cp2 / "design_space.tsv") if int(r["length_nt"]) in EXPECTED_STRATA]
    if Counter(int(r["length_nt"]) for r in design_rows) != Counter(EXPECTED_STRATA):
        raise NB03SelectionError("CP2 strata counts differ from 2038/1965/1938/1838")
    if any(r["membership"] != "DESIGN_SPACE" or r["hard_filters_pass"] != "True" or r["window_id"].startswith("BC-BENCH") for r in design_rows):
        raise NB03SelectionError("CP2 strata must contain only DESIGN_SPACE windows that pass the structural filters")
    cand_rows = _read_tsv(cp3 / "candidate_unit_specificity.tsv")
    other_rows = _read_tsv(cp3 / "other_transcript_summary.tsv")
    ids2 = [r["window_id"] for r in design_rows]
    for label, rows in (("CP2", design_rows), ("CP3 candidates", cand_rows), ("CP3 OTHER_TRANSCRIPT", other_rows)):
        if len({r["window_id"] for r in rows}) != len(rows):
            raise NB03SelectionError(f"duplicate window ids in {label}")
    if set(ids2) != {r["window_id"] for r in cand_rows} or set(ids2) != {r["window_id"] for r in other_rows} or len(ids2) != 7779:
        raise NB03SelectionError("CP2 ids differ from CP3 DESIGN_SPACE ids (missing or extra windows)")
    cand, other = {r["window_id"]: r for r in cand_rows}, {r["window_id"]: r for r in other_rows}
    windows: list[Window] = []
    info: dict[str, dict[str, Any]] = {}
    for r in design_rows:
        wid = r["window_id"]
        c, o = cand[wid], other[wid]
        if (c["membership"], c["specificity_evidence_basis"], int(c["length_nt"]), int(c["cds_start"]), int(c["cds_end"]), c["sequence_sha256"]) != (
                "DESIGN_SPACE", criteria.CANONICAL_EVIDENCE_BASIS, int(r["length_nt"]), int(r["cds_start"]), int(r["cds_end"]), r["sequence_sha256"]):
            raise NB03SelectionError(f"{wid}: CP2 and CP3 disagree on membership, basis, geometry or sequence hash")
        if any(c[f"other_transcript_{m}"] != o[m] for m in OTHER_METRICS):
            raise NB03SelectionError(f"{wid}: CP3 candidate table and OTHER_TRANSCRIPT summary disagree")
        positions = frozenset(int(p) for p in r["intersected_observed_sequence_difference_positions"].split(",") if p)
        if len(positions) != int(r["count_intersected_observed_sequence_differences"]):
            raise NB03SelectionError(f"{wid}: difference count and positions disagree")
        bicc, dsr = _vector(c, "bicc_like"), _vector(c, "dsrnase2")
        windows.append(Window(criteria.SpecificityEvidence(wid, int(r["length_nt"]), positions, bicc, dsr, criteria.CANONICAL_EVIDENCE_BASIS),
                              int(r["cds_start"]), r["target"], "DESIGN_SPACE"))
        info[wid] = {"cp2": r, "cand": c, "other": o, "cds_end": int(r["cds_end"])}
    if any(w.evidence.dsrnase2 != (0, 0, 0) for w in windows):
        raise NB03SelectionError("the CP3 observation DSRNASE2 = (0, 0, 0) for every window no longer holds")
    kmers: dict[tuple[str, str], tuple[int, int]] = {}
    for r in _read_tsv(cp3 / "exact_kmer_summary.tsv"):
        if r["role"] != "DESCRIPTIVE_ONLY":
            raise NB03SelectionError("exact k-mer rows must be DESCRIPTIVE_ONLY")
        kmers[(r["window_id"], r["unit"])] = (int(r["exact_19mer_match_count"]), int(r["exact_21mer_match_count"]))
    if any((wid, unit) not in kmers for wid in ids2 for unit in UNITS):
        raise NB03SelectionError("exact k-mer rows are missing for a window and unit")
    return windows, info, {"kmers": kmers}


def _scope(length_nt: int, label: str) -> str:
    if label != NONDOMINATED:
        return "NOT_PRIORITY"
    return "NOMINAL_L400" if length_nt == NOMINAL_REVIEW_LENGTH_NT else "SENSITIVITY_ONLY"


def _stratum_summary(windows: list[Window], status: Mapping[str, tuple[str, int]], cells: list[SelectionCell]) -> dict[str, Any]:
    n = len(windows)
    nondominated = [w for w in windows if status[w.window_id][0] == NONDOMINATED]
    sizes = [len(c.window_ids) for c in cells]
    priority_cells = [c for c in cells if status[c.window_ids[0]][0] == NONDOMINATED]
    return {"n_total": n, "n_nondominated": len(nondominated), "n_dominated": n - len(nondominated),
            "fraction_nondominated": len(nondominated) / n,
            "n_distinct_decisive_signatures": len({criteria.decisive_signature(w.evidence) for w in windows}),
            "n_distinct_nondominated_signatures": len({criteria.decisive_signature(w.evidence) for w in nondominated}),
            "n_cells": len(cells), "n_priority_cells": len(priority_cells), "n_priority_windows": len(nondominated),
            "n_singleton_cells": sum(s == 1 for s in sizes), "largest_cell_size": max(sizes),
            "cell_size_distribution": {str(size): count for size, count in sorted(Counter(sizes).items())},
            "cell_size_description": spec._describe_numbers(sizes),
            "difference_count_distribution_among_nondominated": {
                str(count): number for count, number in sorted(Counter(criteria.count_intersected(w.evidence) for w in nondominated).items())}}


def run_cp4a(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Materialize Pareto status, cells, the priority set and the L400 manual-review packet from certified CP2/CP3 outputs.

    No BLAST, k-mer or shuffle is recomputed. No representative, ranking, approval or shortlist is produced.
    """
    started = datetime.now(timezone.utc).isoformat()
    root = Path(root).resolve()
    registry = criteria.load_registry(root)
    if criteria.validate_registry(registry):
        raise NB03SelectionError("the NB03 registry is invalid")
    input_hashes = verify_certified_inputs(root)
    windows, info, extra = load_windows(root)
    kmers = extra["kmers"]
    status = pareto_status(windows)
    cells = form_cells(windows)
    check_cells_have_uniform_status(cells, status)
    priority = priority_set(status)
    tiers = difference_tiers(windows, status)
    review_ids = manual_review_window_ids(windows, status)
    if review_ids != {w.window_id for w in windows if w.length_nt == NOMINAL_REVIEW_LENGTH_NT and w.window_id in priority}:
        raise NB03SelectionError("the nominal review scope is not exactly L400 and NONDOMINATED")
    if sorted(i for c in cells for i in c.window_ids) != sorted(info):
        raise NB03SelectionError("cells must partition the DESIGN_SPACE windows")
    by_id = {w.window_id: w for w in windows}
    cell_of = {i: c for c in cells for i in c.window_ids}
    cell_end = {c.cell_id: (min(info[i]["cds_end"] for i in c.window_ids), max(info[i]["cds_end"] for i in c.window_ids)) for c in cells}

    out = Path(output_dir) if output_dir is not None else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    def window_row(w: Window) -> dict[str, Any]:
        wid, cell = w.window_id, cell_of[w.window_id]
        label, n_dominators = status[wid]
        row = {"window_id": wid, "length_nt": w.length_nt, "cds_start": w.cds_start, "cds_end": info[wid]["cds_end"],
               "pareto_status": label, "n_dominators": n_dominators, "difference_count": criteria.count_intersected(w.evidence),
               "count_intersected_observed_sequence_differences": criteria.count_intersected(w.evidence),
               "difference_tier": tiers[wid], "priority_set": wid in priority, "cell_id": cell.cell_id, "cell_start": cell.starts[0]}
        row.update(zip(AXIS_COLUMNS, (*w.evidence.bicc_like, *w.evidence.dsrnase2)))
        return row

    rows = display_order([window_row(w) for w in windows])
    _write_table(out / "pareto_by_stratum.tsv", PARETO_COLUMNS, rows)
    cell_rows = []
    for c in cells:
        label = status[c.window_ids[0]][0]
        ends = cell_end[c.cell_id]
        cell_rows.append({"cell_id": c.cell_id, "target": c.target, "length_nt": c.length_nt, "cds_start_min": c.starts[0],
                          "cds_start_max": c.starts[-1], "cds_end_min": ends[0], "cds_end_max": ends[1], "n_members": len(c.window_ids),
                          "pareto_status": label, "difference_count": c.signature[0], "difference_tier": tiers[c.window_ids[0]],
                          "bicc_like_vector": _vector_text(c.signature[1]), "dsrnase2_vector": _vector_text(c.signature[2]),
                          "manual_review_scope": _scope(c.length_nt, label), "cell_start": c.starts[0], "cds_start": c.starts[0],
                          "window_id": c.cell_id})
    _write_table(out / "cells.tsv", CELL_COLUMNS, display_order(cell_rows))
    members = [{"cell_id": c.cell_id, "window_id": i, "length_nt": c.length_nt, "cds_start": by_id[i].cds_start, "cds_end": info[i]["cds_end"],
                "member_index": index, "pareto_status": status[i][0], "difference_count": c.signature[0], "cell_start": c.starts[0]}
               for c in cells for index, i in enumerate(c.window_ids, 1)]
    _write_table(out / "cell_members.tsv", MEMBER_COLUMNS, display_order(members))

    packet = []
    for row in rows:
        wid = row["window_id"]
        if wid not in review_ids:
            continue
        cell, cand, other, cp2 = cell_of[wid], info[wid]["cand"], info[wid]["other"], info[wid]["cp2"]
        item = {k: row[k] for k in ("window_id", "cds_start", "cds_end", "length_nt", "cell_id", "pareto_status", "n_dominators",
                                    "difference_tier", "count_intersected_observed_sequence_differences")}
        item.update(cell_start=cell.starts[0], cell_end=cell_end[cell.cell_id][1], cell_size=len(cell.window_ids),
                    intersected_observed_sequence_difference_positions=cp2["intersected_observed_sequence_difference_positions"])
        for unit in ("bicc_like", "dsrnase2"):
            item.update({f"{unit}_{m}": cand[f"{unit}_{m}"] for m in UNIT_PACKET_METRICS})
        for unit in ("dsrnase1", "dsrnase3"):
            item.update({f"{unit}_{m}": cand[f"{unit}_{m}"] for m in (*spec.AXES, "n_hsps")})
        item.update({f"other_transcript_{m}": other[m] for m in OTHER_METRICS})
        for k_index, k in enumerate((19, 21)):
            item.update({f"exact_{k}mer_{unit.lower()}": kmers[(wid, unit)][k_index] for unit in UNITS})
        item.update({c: cp2[c] for c in CP2_DESCRIPTORS})
        item["manual_review_status"] = MANUAL_REVIEW_INITIAL_STATUS
        packet.append(item)
    _write_table(out / "manual_review_packet.tsv", PACKET_COLUMNS, packet)

    # HSP detail for the packet only: the OTHER_TRANSCRIPT hits that the reviewer needs, linked by window_id.
    order = {item["window_id"]: index for index, item in enumerate(packet)}
    hsp_rows = []
    with (root / CP3_DIR / "blast_hsps.tsv").open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            if r["unit"] == "OTHER_TRANSCRIPT" and r["query"] in order:
                hsp_rows.append({**r, "window_id": r["query"]})
    hsp_rows.sort(key=lambda r: (order[r["window_id"]], r["hsp_id"]))
    counts = Counter(r["window_id"] for r in hsp_rows)
    if any(counts.get(item["window_id"], 0) != int(item["other_transcript_n_hsps"]) for item in packet):
        raise NB03SelectionError("the HSP reference does not match the OTHER_TRANSCRIPT HSP counts of the packet")
    _write_table(out / "other_transcript_hsp_reference.tsv", HSP_REFERENCE_COLUMNS, hsp_rows)

    # Descriptive benchmark comparison: the REFERENCE_SET never takes a status, a tier or a cell.
    bench_cand = _read_tsv(root / CP3_DIR / "benchmark_specificity.tsv")
    bench_desc = _read_tsv(root / CP2_DIR / "benchmark_descriptor.tsv")
    if len(bench_cand) != 1 or len(bench_desc) != 1 or bench_cand[0]["membership"] != "REFERENCE_SET" or bench_cand[0]["window_id"] != design.BENCHMARK_ID:
        raise NB03SelectionError("the benchmark must be one separate REFERENCE_SET row")
    bench = bench_cand[0]
    equivalent_id = "BC-L373-0215-0587"
    if info[equivalent_id]["cand"]["sequence_sha256"] != bench["sequence_sha256"]:
        raise NB03SelectionError("the geometric design window differs in sequence from the benchmark")

    def benchmark_row(window_id: str, cand_row: Mapping[str, str], other_values: Mapping[str, str], membership: str, role: str,
                      comparison: str, count: str, in_selection: bool) -> dict[str, Any]:
        row = {"window_id": window_id, "membership": membership, "query_role": role, "comparison_role": comparison,
               "length_nt": cand_row["length_nt"], "cds_start": cand_row["cds_start"], "cds_end": cand_row["cds_end"],
               "sequence_sha256": cand_row["sequence_sha256"], "participates_in_pareto": in_selection, "participates_in_cells": in_selection,
               "pareto_status": status[window_id][0] if in_selection else None,
               "cell_id": cell_of[window_id].cell_id if in_selection else None,
               "difference_tier": tiers[window_id] if in_selection else None,
               "count_intersected_observed_sequence_differences": count}
        for unit in ("bicc_like", "dsrnase2"):
            for axis in spec.AXES:
                row[f"{unit}_{axis}"] = cand_row[f"{unit}_{axis}"]
        row.update({f"other_transcript_{m}": other_values[m] for m in OTHER_METRICS})
        for k_index, k in enumerate((19, 21)):
            row.update({f"exact_{k}mer_{unit.lower()}": kmers[(window_id, unit)][k_index] for unit in UNITS})
        return row

    benchmark_rows = [
        benchmark_row(design.BENCHMARK_ID, bench, {m: bench[f"other_transcript_{m}"] for m in OTHER_METRICS}, "REFERENCE_SET", "REFERENCE_ONLY",
                      "REFERENCE_SET_NOT_A_CANDIDATE", bench_desc[0]["count_intersected_observed_sequence_differences"], False),
        benchmark_row(equivalent_id, info[equivalent_id]["cand"], info[equivalent_id]["other"], "DESIGN_SPACE", "SPECIFICITY_EVIDENCE_ONLY",
                      "DESIGN_SPACE_WINDOW_WITH_THE_SAME_SEQUENCE", info[equivalent_id]["cp2"]["count_intersected_observed_sequence_differences"], True)]
    _write_table(out / "benchmark_comparison.tsv", BENCHMARK_COLUMNS, benchmark_rows)

    # ------------------------------------------------------------------ summary
    strata = {}
    for length in sorted(EXPECTED_STRATA):
        group = [w for w in windows if w.length_nt == length]
        strata[f"L{length}"] = _stratum_summary(group, status, [c for c in cells if c.length_nt == length])
        strata[f"L{length}"]["role"] = "NOMINAL_RANKING_STRATUM" if length == NOMINAL_REVIEW_LENGTH_NT else "SENSITIVITY_ONLY"
    numbers = lambda metric: [float(item[f"other_transcript_{metric}"]) for item in packet]  # noqa: E731
    subjects = Counter(s for item in packet for s in item["other_transcript_subject_accessions"].split(",") if s)
    packet_tiers = Counter(item["difference_tier"] for item in packet)
    summary = {
        "stage": "NB03_CP4A_PARETO_CELLS_AND_MANUAL_REVIEW_PACKET", "evidence_status": "MATERIALIZED", "next_state": "CP4_MANUAL_REVIEW_REQUIRED",
        "selection_policy_commit": SELECTION_POLICY_COMMIT, "specificity_evidence_basis": criteria.CANONICAL_EVIDENCE_BASIS,
        "n_design_space_windows": len(windows), "n_reference_set_rows_excluded": 1,
        "dsrnase2_axes_constant": True,
        "dsrnase2_axes_note": ("the frozen DSRNASE2 axes are retained formally but do not discriminate dominance in this observed dataset "
                               "(OBSERVATION from CP3, not a methodological change)"),
        "strata": strata,
        "display_order": {"classification": DISPLAY_ORDER_CLASSIFICATION, "fields": list(DISPLAY_FIELDS),
                          "is_ranking": False, "is_tie_breaker": False},
        "difference_tier": "equals count_intersected_observed_sequence_differences for NONDOMINATED windows, NA for DOMINATED; no dense rank, no threshold",
        "manual_review_packet": {
            "scope": "L400 AND NONDOMINATED", "n_windows": len(packet), "manual_review_status": dict(Counter(i["manual_review_status"] for i in packet)),
            "difference_tier_distribution": {str(t): n for t, n in sorted(packet_tiers.items())},
            "n_cells": len({item["cell_id"] for item in packet}),
            "other_transcript": {"n_windows_with_zero_hits": sum(int(i["other_transcript_n_hsps"]) == 0 for i in packet),
                                 "n_windows_with_hits": sum(int(i["other_transcript_n_hsps"]) > 0 for i in packet),
                                 **{metric: spec._describe_numbers(numbers(metric)) for metric in ("n_hsps", "n_subject_records", "longest_exact_match",
                                                                                                    "covered_nt", "best_local_identity",
                                                                                                    "aligned_nt_for_best_identity")},
                                 "n_unique_subjects": len(subjects),
                                 "most_frequent_subjects_descriptive_only": [[s, n] for s, n in sorted(subjects.items(), key=lambda p: (-p[1], p[0]))[:25]]},
            "exact_kmers_descriptive_only": {unit: {str(k): {**spec._describe_numbers([int(i[f"exact_{k}mer_{unit.lower()}"]) for i in packet]),
                                                              "windows_with_matches": sum(int(i[f"exact_{k}mer_{unit.lower()}"]) > 0 for i in packet)}
                                                   for k in (19, 21)} for unit in UNITS},
            "hsp_reference_rows": len(hsp_rows)},
        "benchmark": {"window_id": design.BENCHMARK_ID, "membership": "REFERENCE_SET", "role": "descriptive comparison only; no Pareto, cell, tier or candidate role",
                      "same_sequence_as": equivalent_id, "row_in_benchmark_comparison": benchmark_rows[0]},
        "statements": ["no representative was selected", "no shortlist, approval, rejection or recommendation was produced",
                       "OTHER_TRANSCRIPT, exact k-mers, DSRNASE1/DSRNASE3 and all CP2 descriptors stayed outside Pareto, signature, cells and tiers",
                       "dominated windows mean Pareto-dominated under the preregistered specificity axes only"],
        "not_executed": ["manual_review", "representative_selection", "shortlist", "CP4B", "CP5", "Wet_Lab_handoff", "BLAST", "kmer_recomputation"]}
    design._write_json(out / "cp4a_summary.json", summary)

    outputs = {name: design._sha256(out / name) for name in DETERMINISTIC_OUTPUTS}
    sources = ("src/zeaguard/nb03_selection.py", "src/zeaguard/nb03_criteria.py", "src/zeaguard/nb03_specificity.py")
    manifest = {"schema_version": 1, "stage": summary["stage"], "selection_policy_commit": SELECTION_POLICY_COMMIT,
                "python_version": sys.version.split()[0],
                "inputs": {"registry_sha256_lf": criteria.registry_sha256(root / criteria.REGISTRY_PATH),
                           "certified_input_sha256": input_hashes},
                "implementation_sha256_lf": {p: criteria.registry_sha256(root / p) for p in sources},
                "counts": {"design_space_windows": len(windows), "cells": len(cells), "manual_review_packet_rows": len(packet),
                           "strata": {str(k): v for k, v in EXPECTED_STRATA.items()}},
                "outputs_sha256": outputs,
                "deterministic_outputs": list(DETERMINISTIC_OUTPUTS),
                "execution_metadata": {"file": "execution_metadata.json", "excluded_from_deterministic_outputs": True}}
    design._write_json(out / "run_manifest.json", manifest)
    design._write_json(out / "execution_metadata.json", {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                                                         "python": sys.version, "platform": sys.platform})
    return {"summary": summary, "manifest": manifest, "windows": windows, "status": status, "cells": cells, "packet": packet,
            "outputs_sha256": {**outputs, "run_manifest.json": design._sha256(out / "run_manifest.json")}}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp4a(find_project_root())
    print(json.dumps({"outputs_sha256": result["outputs_sha256"], "evidence_status": result["summary"]["evidence_status"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
