"""NB03 CP4A selection semantics (amendment 4): a data-free contract kernel.

Explicit values in, explicit values out. Nothing here reads CP2/CP3 outputs, writes a file or inspects a real
window. The decision order is specificity first: Pareto status (per window, within one length stratum), then
difference tiers among NONDOMINATED windows only, then manual review. A cell is a maximal contiguous run of
DESIGN_SPACE windows with the same target, length and decisive signature; it is grouping, never preference.

No score, weight, sum, threshold, hard filter or automatic representative exists. Row ordering is
CANONICAL_DISPLAY_ORDER_ONLY: it is not a ranking and not a tie-breaker.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from zeaguard import nb02_cells, nb02_criteria, nb03_criteria as criteria

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
