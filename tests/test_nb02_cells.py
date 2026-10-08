from __future__ import annotations

from pathlib import Path

import pytest

from zeaguard import nb02_cells as cells
from zeaguard import nb02_criteria as crit

ROOT = Path(__file__).resolve().parents[1]
HAS_CP3 = (ROOT / cells.CP3_WINDOWS).is_file() and (ROOT / cells.CP2_WINDOWS).is_file()
needs_cp3 = pytest.mark.skipif(not HAS_CP3, reason="the CP2/CP3 outputs are not materialised locally")


# ------------------------------------------------------------------ contiguity (the mandatory pre-CP4 rule)
def test_a_signature_that_reappears_after_an_interruption_starts_a_new_cell():
    # signatures A A A B B A A at consecutive starts 1..7
    entries = [(1, "A"), (2, "A"), (3, "A"), (4, "B"), (5, "B"), (6, "A"), (7, "A")]
    grouped = cells.contiguous_cells(entries)
    assert [(c.starts[0], c.starts[-1], c.signature) for c in grouped] == [
        (1, 3, "A"), (4, 5, "B"), (6, 7, "A")]
    assert [c.cell_id for c in grouped] == ["CELL-001", "CELL-002", "CELL-003"]
    # the two A runs are the same signature but must never be one cell
    assert [c.signature_id for c in grouped] == ["SIG-001", "SIG-002", "SIG-001"]
    assert len({c.cell_id for c in grouped if c.signature == "A"}) == 2
    assert all(len(c.starts) == len(set(c.starts)) for c in grouped)
    assert sum(len(c.starts) for c in grouped) == 7  # every window lands in exactly one cell


def test_a_gap_in_the_starts_breaks_a_cell_even_with_an_identical_signature():
    grouped = cells.contiguous_cells([(1, "A"), (2, "A"), (5, "A"), (6, "A")])
    assert [(c.starts[0], c.starts[-1]) for c in grouped] == [(1, 2), (5, 6)]
    assert [c.signature_id for c in grouped] == ["SIG-001", "SIG-001"]


def test_contiguous_cells_edge_cases_and_ids_in_a_length_stratum():
    assert cells.contiguous_cells([]) == []
    single = cells.contiguous_cells([(400, "A")], "RANKING_L400", 400)
    assert single[0].cell_id == "D2C-L400-001" and single[0].starts == (400,) and single[0].length_nt == 400
    alternating = cells.contiguous_cells([(1, "A"), (2, "B"), (3, "A")], "RANKING_L400", 400)
    assert [c.cell_id for c in alternating] == ["D2C-L400-001", "D2C-L400-002", "D2C-L400-003"]
    assert [c.signature_id for c in alternating] == ["SIG-001", "SIG-002", "SIG-001"]


def test_contiguous_cells_rejects_unsorted_or_duplicated_starts():
    with pytest.raises(cells.NB02CellError):
        cells.contiguous_cells([(2, "A"), (1, "A")])
    with pytest.raises(cells.NB02CellError):
        cells.contiguous_cells([(1, "A"), (1, "A")])


def test_real_signatures_use_variants_and_the_unit_vectors_only():
    base = {"candidate_id": "w", "length_nt": 400, "cds_start": 1, "cds_end": 400, "variants": (816,),
            "n_variant_sites": 1, "fraction_unaffected": 0.9, "dsrnase1": (0.0, 0.0, 0.0),
            "dsrnase3": (0.0, 0.0, 0.0), "bicc": (0.0, 0.0, 0.0), "descriptor": {}}
    same_position_different_descriptors = {**base, "fraction_unaffected": 0.5, "cds_start": 2}
    assert cells.window_signature(base) == cells.window_signature(same_position_different_descriptors)
    assert cells.window_signature({**base, "variants": (816, 1272)}) != cells.window_signature(base)
    assert cells.window_signature({**base, "dsrnase3": (21.0, 40.0, 1.0)}) != cells.window_signature(base)


# ------------------------------------------------------------------ ordering
def _cell(start, variants=(), dsrnase1=(0.0, 0.0, 0.0), dsrnase3=(0.0, 0.0, 0.0), n=1):
    entries = [{"candidate_id": f"D2-L400-{start + i:04d}", "length_nt": 400, "cds_start": start + i,
                "cds_end": start + i + 399, "variants": variants, "n_variant_sites": len(variants),
                "fraction_unaffected": 1.0, "dsrnase1": dsrnase1, "dsrnase3": dsrnase3, "bicc": (0.0, 0.0, 0.0),
                "descriptor": {}} for i in range(n)]
    cell = cells.Cell(f"D2C-L400-{start:03d}", "SIG-001", "RANKING_L400", 400, cells.window_signature(entries[0]),
                      tuple(e["cds_start"] for e in entries))
    return cells.OrderedCell(cell, entries)


def test_cells_with_zero_specificity_are_all_in_the_pareto_front_and_variants_order_them():
    ordered = cells.order_cells([_cell(1, variants=(9, 30)), _cell(400), _cell(800, variants=(816,))])
    assert all(cell.in_pareto_front for cell in ordered)
    assert [cell.cell.start_min for cell in ordered] == [400, 800, 1]
    assert [cell.ordering_group for cell in ordered] == [1, 2, 3]


def test_ties_are_preserved_in_one_ordering_group_and_the_representative_is_the_smallest_start():
    ordered = cells.order_cells([_cell(400, n=3), _cell(800, n=2)])
    assert {cell.ordering_group for cell in ordered} == {1}
    assert [cell.representative["cds_start"] for cell in ordered] == [400, 800]


def test_a_cell_dominated_in_specificity_leaves_the_pareto_front_and_is_ordered_after():
    clean, dominated = _cell(400), _cell(800, dsrnase1=(25.0, 80.0, 1.0))
    ordered = cells.order_cells([dominated, clean])
    assert [cell.cell.start_min for cell in ordered] == [400, 800]
    assert [cell.in_pareto_front for cell in ordered] == [True, False]
    assert ordered[0].ordering_group < ordered[1].ordering_group
    # specificity outranks variants: a clean cell with variants still beats a dominated variant-free cell
    with_variants = _cell(400, variants=(9, 30, 219))
    ordered = cells.order_cells([dominated, with_variants])
    assert ordered[0].cell.start_min == 400 and ordered[0].in_pareto_front


def test_a_specificity_trade_off_keeps_both_cells_in_the_front():
    better_on_1 = _cell(400, dsrnase1=(0.0, 0.0, 0.0), dsrnase3=(25.0, 80.0, 1.0))
    better_on_3 = _cell(800, dsrnase1=(25.0, 80.0, 1.0), dsrnase3=(0.0, 0.0, 0.0))
    ordered = cells.order_cells([better_on_1, better_on_3])
    assert all(cell.in_pareto_front for cell in ordered)
    assert {cell.ordering_group for cell in ordered} == {1}


def test_overlap_nt():
    assert cells.overlap_nt((814, 1143), (817, 1216)) == 327
    assert cells.overlap_nt((351, 750), (814, 1143)) == 0
    assert cells.overlap_nt((1, 10), (10, 20)) == 1


# ------------------------------------------------------------------ the real ranking stratum
@needs_cp3
def test_the_ranking_stratum_cells_are_contiguous_disjoint_and_cover_every_window():
    built = cells.build_cells(ROOT, 400)
    starts = [start for cell in built for start in cell.cell.starts]
    assert sorted(starts) == list(range(1, 1027)) and len(starts) == len(set(starts))
    for cell in built:
        assert list(cell.cell.starts) == list(range(cell.cell.start_min, cell.cell.start_max + 1))
        assert len({cells.window_signature(entry) for entry in cell.entries}) == 1
    # adjacent cells must differ in signature (otherwise they would be one contiguous cell)
    by_start = sorted(built, key=lambda c: c.cell.start_min)
    for left, right in zip(by_start, by_start[1:]):
        if right.cell.start_min == left.cell.start_max + 1:
            assert left.cell.signature != right.cell.signature


@needs_cp3
def test_the_top_tied_cells_are_variant_free_and_within_the_pre_registered_bounds():
    built = cells.build_cells(ROOT, 400)
    top = [cell for cell in built if cell.ordering_group == 1]
    assert 2 <= len(top) <= 4
    assert all(cell.variant_key == 0 for cell in top)
    assert all(cell.in_pareto_front for cell in built)  # every unit vector is zero in this dataset
    assert sum(len(cell.entries) for cell in top) == 122  # the variant-free windows of the stratum


@needs_cp3
def test_provisional_candidates_cannot_be_recommended_without_a_versioned_review():
    result = cells.run_cp4(ROOT, ROOT / "results/bioinformatics/nb02/cp4_test")
    assert result["manifest"]["counts"]["recommended"] == 0
    for candidate in result["candidates"]:
        assert candidate["recommendation_status"] == "PENDING_REVIEW" and candidate["status"] == "PROVISIONAL"
        assert candidate["review_decision"] == ""
        with pytest.raises(crit.NB02ReviewError):
            crit.assert_can_recommend(candidate["candidate_id"], {})
    assert "final shortlist" in result["manifest"]["not_done"]
