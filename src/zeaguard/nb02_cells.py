"""NB02 checkpoint 4: contiguous equivalence cells, ordering, and provisional candidates.

A cell is a MAXIMAL CONTIGUOUS run of adjacent windows of one length stratum that share the same
decisive signature (intercepted variants + the clipped DSRNASE1, DSRNASE3 and BICC vectors). With a
step of 1 nt two consecutive windows join the same cell only when ``next.cds_start == current.cds_start + 1``
and the signatures are equal; if a signature reappears after an interruption it starts a NEW cell, so
spatially disconnected regions are never merged because their tuples happen to match.

Cells are then ordered by the pre-registered hierarchy (structural, specificity by Pareto dominance
within one stratum, then variants), ties are preserved, and the representatives of the top tied cells
become PROVISIONAL candidates. A provisional candidate only becomes RECOMMENDED_SHORTLIST once a
versioned OTHER_TRANSCRIPT review decision exists for it (``nb02_criteria.assert_can_recommend``);
this module produces that evidence and never decides it.

No score, no weights, no cutoff on E-values or k-mer counts, no positional bonus, no overlap rule.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Hashable, Iterable, Sequence

from zeaguard import nb02_criteria, nb02_design, nb02_reference, nb02_specificity
from zeaguard.nb01_dsrnase_investigation import write_tsv

OUTPUT_DIR = Path("results/bioinformatics/nb02/cp4")
CP2_WINDOWS = Path("results/bioinformatics/nb02/strata_windows.tsv")
CP3_WINDOWS = Path("results/bioinformatics/nb02/cp3/specificity_windows.tsv")
CP3_PROVENANCE = Path("results/bioinformatics/nb02/cp3/hsp_provenance.tsv")

CELL_COLUMNS = (
    "cell_id", "signature_id", "length_stratum", "length_nt", "n_windows",
    "start_min", "start_max", "end_min", "end_max", "span_start", "span_end",
    "n_variant_sites", "variant_positions",
    "dsrnase1_vector", "dsrnase3_vector", "bicc_vector",
    "fraction_unaffected_min", "fraction_unaffected_max",
    "in_pareto_front", "ordering_group", "representative_candidate_id", "representative_cds_start",
    "representative_cds_end", "representative_target_region_position", "span_overlap_with_benchmark_nt",
)
CANDIDATE_COLUMNS = (
    "candidate_id", "cell_id", "status", "length_nt", "cds_start", "cds_end", "sequence_sha256",
    "n_variant_sites", "variant_positions", "fraction_potential_windows_unaffected",
    "dsrnase1_vector", "dsrnase3_vector", "bicc_vector",
    "other_transcript_longest_exact_match_clipped", "other_transcript_covered_nt_clipped",
    "other_transcript_best_local_identity_clipped", "other_transcript_best_identity_aligned_nt_clipped",
    "other_transcript_n_hsps_clipped", "other_transcript_exact_19mer_count_clipped",
    "other_transcript_exact_21mer_count_clipped", "other_transcript_hit_records",
    "target_region_position", "relative_midpoint", "gc_fraction", "longest_homopolymer",
    "low_complexity_fraction", "overlap_with_benchmark_nt", "review_decision", "recommendation_status",
)


class NB02CellError(RuntimeError):
    """The cells or the provisional candidates cannot be built as pre-registered."""


# --------------------------------------------------------------------------- contiguity
@dataclass(frozen=True)
class Cell:
    cell_id: str
    signature_id: str
    stratum: str
    length_nt: int
    signature: Hashable
    starts: tuple[int, ...]

    @property
    def start_min(self) -> int:
        return self.starts[0]

    @property
    def start_max(self) -> int:
        return self.starts[-1]


def contiguous_cells(
    entries: Sequence[tuple[int, Hashable]],
    stratum: str = "",
    length_nt: int = 0,
    step: int = 1,
) -> list[Cell]:
    """Group ``(start, signature)`` entries into maximal CONTIGUOUS runs of equal signature.

    ``entries`` must be sorted by start and have no duplicates. A run is broken by a gap in the
    starts (``next != current + step``) or by a change of signature; a signature that reappears
    after an interruption starts a new cell with a new ``cell_id`` but keeps its ``signature_id``.
    """
    starts = [start for start, _ in entries]
    if starts != sorted(set(starts)):
        raise NB02CellError("cell entries must be sorted by start and unique")
    cells: list[Cell] = []
    signature_ids: dict[Hashable, str] = {}
    run: list[int] = []
    current: Hashable = object()

    def flush() -> None:
        if not run:
            return
        signature_id = signature_ids.setdefault(current, f"SIG-{len(signature_ids) + 1:03d}")
        cells.append(Cell(f"D2C-L{length_nt:03d}-{len(cells) + 1:03d}" if length_nt else f"CELL-{len(cells) + 1:03d}",
                          signature_id, stratum, length_nt, current, tuple(run)))

    for start, signature in entries:
        if run and start == run[-1] + step and signature == current:
            run.append(start)
            continue
        flush()
        run, current = [start], signature
    flush()
    return cells


# --------------------------------------------------------------------------- reading the frozen inputs
def _read_tsv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _vector(row: dict[str, str], unit: str) -> tuple[float, float, float]:
    return (
        float(row[f"{unit}_longest_exact_match_clipped"]),
        float(row[f"{unit}_covered_nt_clipped"]),
        float(row[f"{unit}_best_local_identity_clipped"]),
    )


def load_windows(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Join the CP2 descriptors with the CP3 clipped specificity evidence, per length stratum."""
    root = Path(root)
    descriptors = {row["candidate_id"]: row for row in _read_tsv(root / CP2_WINDOWS)}
    joined: dict[str, list[dict[str, Any]]] = {}
    for row in _read_tsv(root / CP3_WINDOWS):
        descriptor = descriptors.get(row["candidate_id"])
        if descriptor is None:
            raise NB02CellError(f"{row['candidate_id']} has specificity evidence but no CP2 descriptors")
        variants = tuple(int(p) for p in descriptor["variant_positions"].split(",") if p)
        entry = {
            "candidate_id": row["candidate_id"],
            "length_stratum": row["length_stratum"],
            "length_nt": int(row["length_nt"]),
            "cds_start": int(row["cds_start"]),
            "cds_end": int(row["cds_end"]),
            "variants": variants,
            "n_variant_sites": len(variants),
            "fraction_unaffected": float(descriptor["fraction_potential_windows_unaffected"]),
            "dsrnase1": _vector(row, "dsrnase1"),
            "dsrnase3": _vector(row, "dsrnase3"),
            "bicc": _vector(row, "bicc"),
            "descriptor": descriptor,
        }
        joined.setdefault(entry["length_stratum"], []).append(entry)
    for entries in joined.values():
        entries.sort(key=lambda e: e["cds_start"])
    return joined


def window_evidence(entry: dict[str, Any]) -> nb02_criteria.SpecificityEvidence:
    """The decisive evidence of one window, in the frozen kernel's shape (OTHER_TRANSCRIPT excluded)."""
    return nb02_criteria.SpecificityEvidence(
        entry["candidate_id"], entry["length_nt"], frozenset(entry["variants"]),
        entry["dsrnase1"], entry["dsrnase3"], entry["bicc"],
    )


def window_signature(entry: dict[str, Any]) -> Hashable:
    return nb02_criteria.decisive_signature(window_evidence(entry))


# --------------------------------------------------------------------------- ordering
@dataclass
class OrderedCell:
    cell: Cell
    entries: list[dict[str, Any]]
    in_pareto_front: bool = False
    ordering_group: int = 0
    representative: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence(self) -> nb02_criteria.SpecificityEvidence:
        return window_evidence(self.entries[0])

    @property
    def variant_key(self) -> int:
        """C11: number of intercepted known variable sites; constant inside a cell (part of the signature)."""
        return self.entries[0]["n_variant_sites"]


def pareto_front(cells: Sequence[OrderedCell]) -> list[bool]:
    """Non-dominated cells under C07 (Pareto on the unit vectors, within one stratum)."""
    return [
        not any(nb02_criteria.compare_specificity(other.evidence, cell.evidence) == "A_BETTER"
                for j, other in enumerate(cells) if j != i)
        for i, cell in enumerate(cells)
    ]


def order_cells(cells: Sequence[OrderedCell]) -> list[OrderedCell]:
    """Apply the pre-registered hierarchy; equal cells keep the same ``ordering_group`` (ties preserved).

    Structural requirements hold by construction (every window comes from the frozen candidate space).
    Level 3 is specificity by Pareto dominance, level 4 is the variant count (C11); descriptors never
    order. The representative of a cell is its window with the smallest ``cds_start``, the frozen
    representative rule specialised to a fixed-length stratum.
    """
    front = pareto_front(cells)
    for cell, in_front in zip(cells, front):
        cell.in_pareto_front = in_front
        cell.representative = cell.entries[0]
    ranked = sorted(cells, key=lambda c: (not c.in_pareto_front, c.variant_key, c.cell.start_min))
    group = 0
    previous: tuple[bool, int] | None = None
    for cell in ranked:
        key = (cell.in_pareto_front, cell.variant_key)
        if key != previous:
            group += 1
            previous = key
        cell.ordering_group = group
    return ranked


def build_cells(root: Path, stratum_length: int) -> list[OrderedCell]:
    """Contiguous cells of one length stratum, ordered by the pre-registered hierarchy."""
    strata = load_windows(root)
    entries = [e for group in strata.values() for e in group if e["length_nt"] == stratum_length]
    if not entries:
        raise NB02CellError(f"no windows of length {stratum_length} in the stored CP2/CP3 outputs")
    entries.sort(key=lambda e: e["cds_start"])
    stratum = entries[0]["length_stratum"]
    cells = contiguous_cells([(e["cds_start"], window_signature(e)) for e in entries], stratum, stratum_length)
    by_start = {e["cds_start"]: e for e in entries}
    return order_cells([OrderedCell(cell, [by_start[s] for s in cell.starts]) for cell in cells])


# --------------------------------------------------------------------------- provisional candidates
def overlap_nt(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)


def other_transcript_evidence(root: Path, start: int, end: int) -> dict[str, Any]:
    """Clipped OTHER_TRANSCRIPT evidence of one interval, rebuilt from the persisted CP3 provenance."""
    footprints = nb02_specificity.load_footprints(Path(root) / CP3_PROVENANCE)
    return nb02_specificity.unit_evidence(footprints.get(nb02_specificity.OTHER, []), start, end)


def _fmt(value: Any) -> Any:
    return f"{value:.6f}" if isinstance(value, float) else value


def _vector_text(vector: tuple[float, float, float]) -> str:
    return f"({vector[0]:g},{vector[1]:g},{vector[2]:g})"


def run_cp4(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Form the contiguous cells of the ranking stratum, pick the provisional candidates and their
    OTHER_TRANSCRIPT evidence, and report the recommendation status under the mandatory-review gate."""
    root = Path(root).resolve()
    registry = nb02_criteria.load_registry(root)
    parameters = nb02_design.design_parameters(registry)
    reference = nb02_reference.verified_reference(root)
    cds = reference["operational_cds"]
    benchmark = reference["pin"]["benchmark"]
    bench_span = (benchmark["interval"]["cds_start"], benchmark["interval"]["cds_end"])
    out = Path(output_dir) if output_dir else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    cells = build_cells(root, parameters.ranking_length)
    top = [cell for cell in cells if cell.ordering_group == 1]
    bounds = registry["policy"]["recommended_candidates"]
    if len(top) > bounds["max"]:
        raise NB02CellError(
            f"{len(top)} cells are tied at the top (limit {bounds['max']}); ties must not be broken by an invented rule"
        )

    decisions = nb02_criteria.load_review_decisions(root / nb02_criteria.REVIEW_DECISIONS_PATH)
    footprints = nb02_specificity.load_footprints(root / CP3_PROVENANCE)
    other_footprints = footprints.get(nb02_specificity.OTHER, [])

    candidates: list[dict[str, Any]] = []
    for cell in top:
        representative = cell.representative
        start, end = representative["cds_start"], representative["cds_end"]
        other = nb02_specificity.unit_evidence(other_footprints, start, end)
        decision = decisions.get((representative["candidate_id"], "OTHER_TRANSCRIPT"))
        status = nb02_criteria.recommendation_status(representative["candidate_id"], decisions)
        descriptor = representative["descriptor"]
        candidates.append({
            "candidate_id": representative["candidate_id"],
            "cell_id": cell.cell.cell_id,
            "status": "PROVISIONAL" if status == "PENDING_REVIEW" else status,
            "length_nt": representative["length_nt"],
            "cds_start": start,
            "cds_end": end,
            "sequence_sha256": descriptor["sequence_sha256"],
            "n_variant_sites": representative["n_variant_sites"],
            "variant_positions": descriptor["variant_positions"],
            "fraction_potential_windows_unaffected": descriptor["fraction_potential_windows_unaffected"],
            "dsrnase1_vector": _vector_text(representative["dsrnase1"]),
            "dsrnase3_vector": _vector_text(representative["dsrnase3"]),
            "bicc_vector": _vector_text(representative["bicc"]),
            **{f"other_transcript_{key}": _fmt(value) for key, value in other.items()},
            "target_region_position": descriptor["target_region_position"],
            "relative_midpoint": descriptor["relative_midpoint"],
            "gc_fraction": descriptor["gc_fraction"],
            "longest_homopolymer": descriptor["longest_homopolymer"],
            "low_complexity_fraction": descriptor["low_complexity_fraction"],
            "overlap_with_benchmark_nt": overlap_nt((start, end), bench_span),
            "review_decision": decision.decision if decision else "",
            "recommendation_status": status,
        })

    cell_rows = []
    for cell in cells:
        fractions = [entry["fraction_unaffected"] for entry in cell.entries]
        representative, first = cell.representative, cell.entries[0]
        cell_rows.append({
            "cell_id": cell.cell.cell_id, "signature_id": cell.cell.signature_id,
            "length_stratum": cell.cell.stratum, "length_nt": cell.cell.length_nt, "n_windows": len(cell.entries),
            "start_min": cell.cell.start_min, "start_max": cell.cell.start_max,
            "end_min": cell.entries[0]["cds_end"], "end_max": cell.entries[-1]["cds_end"],
            "span_start": cell.cell.start_min, "span_end": cell.entries[-1]["cds_end"],
            "n_variant_sites": cell.variant_key,
            "variant_positions": ",".join(map(str, first["variants"])),
            "dsrnase1_vector": _vector_text(first["dsrnase1"]), "dsrnase3_vector": _vector_text(first["dsrnase3"]),
            "bicc_vector": _vector_text(first["bicc"]),
            "fraction_unaffected_min": f"{min(fractions):.6f}", "fraction_unaffected_max": f"{max(fractions):.6f}",
            "in_pareto_front": cell.in_pareto_front, "ordering_group": cell.ordering_group,
            "representative_candidate_id": representative["candidate_id"],
            "representative_cds_start": representative["cds_start"], "representative_cds_end": representative["cds_end"],
            "representative_target_region_position": representative["descriptor"]["target_region_position"],
            "span_overlap_with_benchmark_nt": overlap_nt((cell.cell.start_min, cell.entries[-1]["cds_end"]), bench_span),
        })
    cells_name = f"cells_L{parameters.ranking_length}.tsv"
    write_tsv(out / cells_name, cell_rows, CELL_COLUMNS)
    write_tsv(out / "provisional_candidates.tsv", candidates, CANDIDATE_COLUMNS)

    # OTHER_TRANSCRIPT hits of each provisional candidate, for the mandatory review (no cutoff, inspection order only)
    review_rows = []
    for candidate in candidates:
        start, end = candidate["cds_start"], candidate["cds_end"]
        for fp in other_footprints:
            clip = nb02_specificity.clip_footprint(fp, start, end)
            if clip is None:
                continue
            review_rows.append({
                "candidate_id": candidate["candidate_id"], "cell_id": candidate["cell_id"],
                "subject": clip.subject, "hsp_id": clip.hsp_id,
                "candidate_qstart": clip.lo, "candidate_qend": clip.hi,
                "aligned_nt_clipped": clip.aligned_nt, "longest_exact_match_clipped": clip.longest_exact,
                "local_identity_clipped": f"{clip.identity:.6f}",
                "hsp_full_qstart": fp.q_lo, "hsp_full_qend": fp.q_hi, "strand": fp.strand,
                "decision": "", "justification": "",
            })
    review_rows.sort(key=lambda r: (r["candidate_id"], -r["longest_exact_match_clipped"], r["subject"]))
    write_tsv(out / "other_transcript_review_evidence.tsv", review_rows)

    # provisional FASTA, inspection only: this is not the Wet Lab hand-off
    fasta = "".join(
        f">{c['candidate_id']} PROVISIONAL_INSPECTION_ONLY cell={c['cell_id']} cds={c['cds_start']}-{c['cds_end']} "
        f"length={c['length_nt']} sha256={c['sequence_sha256']} review={c['recommendation_status']}\n"
        f"{cds[c['cds_start'] - 1 : c['cds_end']]}\n"
        for c in candidates
    )
    (out / "provisional_candidates_inspection_only.fasta").write_text(fasta, encoding="ascii", newline="\n")

    files = [cells_name, "provisional_candidates.tsv",
             "other_transcript_review_evidence.tsv", "provisional_candidates_inspection_only.fasta"]
    manifest = {
        "stage": "NB02 CP4 (contiguous cells, ordering and provisional candidates; no final shortlist)",
        "git": nb02_design._git_state(root),
        "inputs": {
            "criteria_registry_sha256": nb02_criteria.registry_sha256(root / nb02_criteria.REGISTRY_PATH),
            "pin_sha256": reference["report"]["pin_sha256_lf"],
            "cp2_strata_windows": CP2_WINDOWS.as_posix(),
            "cp3_specificity_windows": CP3_WINDOWS.as_posix(),
            "cp3_hsp_provenance": CP3_PROVENANCE.as_posix(),
            "review_decisions": nb02_criteria.REVIEW_DECISIONS_PATH.as_posix(),
        },
        "cell_rule": ("maximal contiguous run of adjacent windows (step 1 nt) with an identical decisive "
                      "signature; a repeated signature after an interruption starts a new cell"),
        "cell_signature": registry["policy"]["cell_signature"],
        "ranking_stratum_nt": parameters.ranking_length,
        "counts": {
            "cells": len(cells),
            "cells_in_pareto_front": sum(cell.in_pareto_front for cell in cells),
            "cells_tied_at_the_top": len(top),
            "provisional_candidates": len(candidates),
            "other_transcript_review_rows": len(review_rows),
            "recommended": sum(c["recommendation_status"] == "RECOMMENDABLE" for c in candidates),
        },
        "recommended_candidate_bounds": bounds,
        "benchmark": {"candidate_id": benchmark["id"], "cds_start": bench_span[0], "cds_end": bench_span[1],
                      "length_nt": benchmark["interval"]["length_nt"], "counts_as_recommended": False},
        "outputs_sha256": {name: hashlib.sha256((out / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for name in files},
        "not_done": ["final shortlist", "Wet Lab hand-off", "ecological off-target", "ADR or run record updates"],
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
                                           encoding="utf-8", newline="\n")
    return {"manifest": manifest, "cells": cells, "cell_rows": cell_rows, "candidates": candidates,
            "review_rows": review_rows, "benchmark_span": bench_span}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp4(find_project_root())
    print(json.dumps(result["manifest"]["counts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
