"""Contract tests for NB03 amendment 4 on synthetic data only; no real CP2/CP3 values are used."""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest

from zeaguard import nb03_criteria as criteria, nb03_selection as sel

ROOT = Path(__file__).resolve().parents[1]
NATIVE = criteria.CANONICAL_EVIDENCE_BASIS


def win(wid, start, bicc=(5, 20, 0.8), dsr=(0, 0, 0), diffs=(), length=400, **kwargs):
    evidence = criteria.SpecificityEvidence(wid, length, frozenset(diffs), bicc, dsr, NATIVE)
    return sel.Window(evidence, start, **kwargs)


def run(prefix, first_start, n, **kwargs):
    return [win(f"{prefix}{i}", first_start + i, **kwargs) for i in range(n)]


# ------------------------------------------------------------------ Pareto status
def test_dominance_needs_no_worse_everywhere_and_better_somewhere_and_equality_is_not_dominance():
    a, b = win("a", 1, bicc=(5, 20, 0.8)), win("b", 2, bicc=(6, 20, 0.8))
    twin = win("twin", 3, bicc=(5, 20, 0.8))
    status = sel.pareto_status([a, b, twin])
    assert status["a"] == (sel.NONDOMINATED, 0) and status["twin"] == (sel.NONDOMINATED, 0)
    assert status["b"] == (sel.DOMINATED, 2)


def test_trade_offs_between_units_are_incomparable_and_all_six_axes_are_used():
    bicc_better = win("x", 1, bicc=(1, 1, 0.1), dsr=(9, 9, 0.9))
    dsr_better = win("y", 2, bicc=(9, 9, 0.9), dsr=(1, 1, 0.1))
    assert set(sel.pareto_status([bicc_better, dsr_better]).values()) == {(sel.NONDOMINATED, 0)}
    assert len(bicc_better.evidence.joint) == 6
    worse_only_on_a_dsr_axis = win("z", 3, bicc=(1, 1, 0.1), dsr=(9, 9, 0.95))
    assert sel.pareto_status([bicc_better, worse_only_on_a_dsr_axis])["z"] == (sel.DOMINATED, 1)


def test_constant_dsrnase2_axes_do_not_break_pareto_and_stay_in_the_schema():
    windows = [win("a", 1, bicc=(1, 2, 0.5)), win("b", 2, bicc=(2, 2, 0.5)), win("c", 3, bicc=(1, 3, 0.4))]
    assert all(w.evidence.dsrnase2 == (0, 0, 0) and len(w.evidence.joint) == 6 for w in windows)
    assert sel.pareto_status(windows) == {"a": (sel.NONDOMINATED, 0), "b": (sel.DOMINATED, 1), "c": (sel.NONDOMINATED, 0)}


def test_pareto_is_computed_separately_per_length_stratum():
    short_best = win("s", 1, length=300, bicc=(0, 0, 0.0))
    long_worse = win("l", 1, length=400, bicc=(9, 9, 0.9))
    assert sel.pareto_status([short_best, long_worse]) == {"s": (sel.NONDOMINATED, 0), "l": (sel.NONDOMINATED, 0)}


def test_values_are_compared_as_stored_without_rounding_or_normalisation():
    close = win("close", 1, bicc=(5, 20, 0.8000001))
    base = win("base", 2, bicc=(5, 20, 0.8))
    assert sel.pareto_status([close, base])["close"] == (sel.DOMINATED, 1)


def test_pareto_ignores_difference_counts_descriptors_and_positions():
    a = win("a", 1, diffs=(10, 20, 30))
    b = win("b", 2, diffs=())
    assert sel.pareto_status([a, b]) == {"a": (sel.NONDOMINATED, 0), "b": (sel.NONDOMINATED, 0)}


def test_reference_set_and_non_native_basis_never_enter():
    benchmark = win("BC-BENCH-0215-0587", 215, length=373, membership="REFERENCE_SET")
    for function in (sel.pareto_status, sel.form_cells):
        with pytest.raises(sel.NB03SelectionError):
            function([win("a", 1), benchmark])
    diagnostic = sel.Window(dataclasses.replace(win("d", 1).evidence, specificity_evidence_basis=criteria.DIAGNOSTIC_EVIDENCE_BASIS), 1)
    with pytest.raises(criteria.NB03EvidenceBasisError):
        sel.pareto_status([diagnostic])


# ------------------------------------------------------------------ cells
def test_a_cell_is_a_maximal_contiguous_run_with_the_same_signature():
    windows = run("w", 10, 4)
    cells = sel.form_cells(windows)
    assert len(cells) == 1 and cells[0].starts == (10, 11, 12, 13) and cells[0].window_ids == ("w0", "w1", "w2", "w3")


def test_a_gap_breaks_a_cell_and_a_reappearing_signature_starts_a_new_one():
    windows = run("a", 1, 2) + run("b", 5, 2)  # same signature, start 3-4 missing
    cells = sel.form_cells(windows)
    assert [c.starts for c in cells] == [(1, 2), (5, 6)] and cells[0].signature == cells[1].signature
    assert len({c.cell_id for c in cells}) == 2
    interrupted = [win("p", 1), win("q", 2, bicc=(9, 9, 0.9)), win("r", 3)]
    assert [c.starts for c in sel.form_cells(interrupted)] == [(1,), (2,), (3,)]


def test_the_difference_count_is_part_of_the_signature_but_positions_are_not():
    same_count_other_positions = [win("a", 1, diffs=(100,)), win("b", 2, diffs=(200,))]
    assert len(sel.form_cells(same_count_other_positions)) == 1
    different_count = [win("a", 1, diffs=(100,)), win("b", 2, diffs=(100, 200))]
    assert len(sel.form_cells(different_count)) == 2


def test_different_lengths_and_targets_never_share_a_cell():
    windows = [win("a", 1, length=300), win("b", 2, length=400), win("c", 3, length=500)]
    assert [(c.length_nt, c.starts) for c in sel.form_cells(windows)] == [(300, (1,)), (400, (2,)), (500, (3,))]
    other_target = [win("a", 1), win("b", 2, target="OTHER")]
    assert len(sel.form_cells(other_target)) == 2


def test_cells_are_formed_for_every_stratum_and_never_for_the_benchmark():
    windows = [w for length in sel.STRATA_NT for w in run(f"L{length}-", 1, 3, length=length)]
    assert sorted({c.length_nt for c in sel.form_cells(windows)}) == [300, 373, 400, 500]
    benchmark = win("BC-BENCH-0215-0587", 215, length=373, membership="REFERENCE_SET")
    with pytest.raises(sel.NB03SelectionError):
        sel.form_cells(windows + [benchmark])


def test_duplicate_starts_or_ids_are_rejected():
    with pytest.raises(sel.NB03SelectionError):
        sel.form_cells([win("a", 1), win("b", 1)])
    with pytest.raises(sel.NB03SelectionError):
        sel.pareto_status([win("a", 1), win("a", 2)])


def test_same_signature_means_same_pareto_status_and_a_mixed_cell_is_an_error():
    windows = run("w", 1, 3) + [win("z", 4, bicc=(1, 1, 0.1))] + run("v", 5, 2, bicc=(9, 9, 0.9))
    status = sel.pareto_status(windows)
    cells = sel.form_cells(windows)
    sel.check_cells_have_uniform_status(cells, status)
    assert {len({status[i][0] for i in c.window_ids}) for c in cells} == {1}
    tampered = dict(status)
    tampered["w1"] = (sel.NONDOMINATED if status["w1"][0] == sel.DOMINATED else sel.DOMINATED, 0)
    with pytest.raises(sel.NB03SelectionError):
        sel.check_cells_have_uniform_status(cells, tampered)


# ------------------------------------------------------------------ priority set, tiers, review scope
def dominated_and_priority_fixture():
    best_but_three = win("best3", 1, bicc=(1, 1, 0.1), diffs=(1, 2, 3))
    best_but_zero = win("best0", 50, bicc=(1, 1, 0.1), diffs=())
    dominated_zero = win("dom0", 100, bicc=(9, 9, 0.9), diffs=())
    return [best_but_three, best_but_zero, dominated_zero]


def test_dominated_windows_stay_out_of_the_priority_set_and_a_low_count_never_rescues_them():
    windows = dominated_and_priority_fixture()
    status = sel.pareto_status(windows)
    assert sel.priority_set(status) == {"best3", "best0"}
    tiers = sel.difference_tiers(windows, status)
    assert tiers == {"best3": 3, "best0": 0, "dom0": None}
    assert criteria.count_intersected(windows[2].evidence) == 0 and status["dom0"][0] == sel.DOMINATED


def test_lower_counts_form_better_tiers_only_inside_the_nondominated_set_and_nothing_is_excluded():
    windows = [win(f"n{c}", 10 * c + 1, bicc=(1, 1, 0.1), diffs=range(c)) for c in range(4)] + [win("d", 99, bicc=(9, 9, 0.9))]
    status = sel.pareto_status(windows)
    tiers = sel.difference_tiers(windows, status)
    assert [tiers[f"n{c}"] for c in range(4)] == [0, 1, 2, 3] and tiers["d"] is None
    assert sel.priority_set(status) == {"n0", "n1", "n2", "n3"}  # tier 3 is not removed
    equal = sel.difference_tiers([win("e1", 1), win("e2", 20)], sel.pareto_status([win("e1", 1), win("e2", 20)]))
    assert equal["e1"] == equal["e2"]


def test_nominal_manual_review_is_l400_nondominated_with_all_tiers_and_sensitivity_strata_are_not_forwarded():
    windows = ([win(f"a{c}", 10 * c + 1, bicc=(1, 1, 0.1), diffs=range(c)) for c in range(3)]
               + [win("dom", 90, bicc=(9, 9, 0.9))]
               + [win(f"s{length}", 1, length=length, bicc=(1, 1, 0.1)) for length in (300, 373, 500)])
    status = sel.pareto_status(windows)
    assert sel.manual_review_window_ids(windows, status) == {"a0", "a1", "a2"}
    assert {"s300", "s373", "s500"} <= sel.priority_set(status)  # nondominated, yet not forwarded to nominal review


def test_no_automatic_representative_exists_and_review_starts_pending():
    assert not [name for name in dir(sel) if "representative" in name.lower()]
    assert not [f.name for f in dataclasses.fields(sel.SelectionCell) if "representative" in f.name.lower()]
    assert sel.MANUAL_REVIEW_INITIAL_STATUS == "PENDING"
    registry = criteria.load_registry(ROOT)["policy"]["selection_semantics"]
    assert registry["automatic_representative"] is False and registry["manual_review_scope"]["initial_status"] == "PENDING"


# ------------------------------------------------------------------ display order
def test_display_order_is_deterministic_and_changes_no_status_tier_or_cell():
    windows = dominated_and_priority_fixture() + run("c", 200, 3)
    status = sel.pareto_status(windows)
    tiers = sel.difference_tiers(windows, status)
    cells = sel.form_cells(windows)
    cell_start = {i: c.starts[0] for c in cells for i in c.window_ids}
    rows = [{"window_id": w.window_id, "length_nt": w.length_nt, "cds_start": w.cds_start, "pareto_status": status[w.window_id][0],
             "difference_count": criteria.count_intersected(w.evidence), "cell_start": cell_start[w.window_id]} for w in windows]
    before = copy.deepcopy(rows)
    ordered = sel.display_order(rows)
    assert rows == before and sorted(map(str, ordered)) == sorted(map(str, rows))
    assert ordered == sel.display_order(list(reversed(rows)))
    assert status == sel.pareto_status(list(reversed(windows)))
    assert tiers == sel.difference_tiers(list(reversed(windows)), status)
    assert {c.cell_id: c.window_ids for c in cells} == {c.cell_id: c.window_ids for c in sel.form_cells(list(reversed(windows)))}
    assert sel.DISPLAY_ORDER_CLASSIFICATION == "CANONICAL_DISPLAY_ORDER_ONLY"


def test_module_has_no_score_weight_sum_or_threshold_interface():
    for forbidden in ("score", "weight", "threshold", "normal", "rank", "recommend", "shortlist"):
        assert not [name for name in dir(sel) if forbidden in name.lower() and not name.startswith("_") and name != "dataclass"]


# ------------------------------------------------------------------ registry contract
def test_registry_records_amendment_4_and_rejects_changes_to_the_semantics():
    registry = criteria.load_registry(ROOT)
    assert criteria.validate_registry(registry) == []
    amendment = registry["amendments"][3]
    assert amendment["criteria"] == ["C06", "C07"] and amendment["applied_before_cp4a_results"] is True
    assert amendment["cp3_outputs_changed"] is False and "AMENDMENT 4" in amendment["change"]
    mutations = (
        lambda p: p.update(specificity_first=False),
        lambda p: p.update(differences_rescue_dominated_windows=True),
        lambda p: p["cell"].update(reappearing_signature_after_interruption="MERGE"),
        lambda p: p["cell"].update(reference_set_members=True),
        lambda p: p["cell"].update(scope="L400_ONLY"),
        lambda p: p["manual_review_scope"].update(length_nt=300),
        lambda p: p["manual_review_scope"].update(pareto_status="DOMINATED"),
        lambda p: p["difference_tier"].update(hard_filter=True),
        lambda p: p["difference_tier"].update(threshold=2),
        lambda p: p.update(automatic_representative=True),
        lambda p: p["display_order"].update(is_ranking=True),
        lambda p: p.pop("pareto"),
    )
    for mutate in mutations:
        changed = copy.deepcopy(registry)
        mutate(changed["policy"]["selection_semantics"])
        assert criteria.validate_registry(changed), mutate
    removed = copy.deepcopy(registry)
    del removed["policy"]["selection_semantics"]
    assert criteria.validate_registry(removed)


# ================================================================== real certified CP2/CP3 inputs
# These tests check the MECHANISM on the real tables with an independent brute-force recomputation. The counts in
# the regression-snapshot test are computational snapshots of one run, not policy definitions.
import csv  # noqa: E402
from types import SimpleNamespace  # noqa: E402

HAS_REAL = all((ROOT / "results/bioinformatics/nb03" / name).exists() for name in ("cp2/design_space.tsv", "cp3/run_manifest.json"))
STRATA = {300: 2038, 373: 1965, 400: 1938, 500: 1838}


def read(directory, name):
    with (Path(directory) / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    if not HAS_REAL:
        pytest.skip("needs the certified CP2/CP3 outputs")
    first, second = tmp_path_factory.mktemp("cp4a_first"), tmp_path_factory.mktemp("cp4a_second")
    result = sel.run_cp4a(ROOT, first)
    sel.run_cp4a(ROOT, second)
    return SimpleNamespace(result=result, first=first, second=second, pareto=read(first, "pareto_by_stratum.tsv"),
                           cells=read(first, "cells.tsv"), members=read(first, "cell_members.tsv"),
                           packet=read(first, "manual_review_packet.tsv"), bench=read(first, "benchmark_comparison.tsv"),
                           hsps=read(first, "other_transcript_hsp_reference.tsv"))


def test_real_joins_are_complete_and_the_benchmark_is_excluded(real):
    ids = [r["window_id"] for r in real.pareto]
    assert len(ids) == len(set(ids)) == 7779
    assert {length: sum(int(r["length_nt"]) == length for r in real.pareto) for length in STRATA} == STRATA
    design_ids = {r["window_id"] for r in read(ROOT / "results/bioinformatics/nb03/cp2", "design_space.tsv") if int(r["length_nt"]) in STRATA}
    cp3_ids = {r["window_id"] for r in read(ROOT / "results/bioinformatics/nb03/cp3", "candidate_unit_specificity.tsv")}
    assert set(ids) == design_ids == cp3_ids
    for rows in (real.pareto, real.members, real.packet):
        assert "BC-BENCH-0215-0587" not in {r["window_id"] for r in rows}
    assert not [c for c in real.cells if "BENCH" in c["cell_id"]]


def test_real_six_axis_schema_and_constant_dsrnase2_axes(real):
    assert list(sel.AXIS_COLUMNS) == ["bicc_like_longest_exact_match", "bicc_like_covered_nt", "bicc_like_best_local_identity",
                                      "dsrnase2_longest_exact_match", "dsrnase2_covered_nt", "dsrnase2_best_local_identity"]
    assert set(real.pareto[0]) >= set(sel.AXIS_COLUMNS)
    assert all(float(r[c]) == 0 for r in real.pareto for c in sel.AXIS_COLUMNS[3:])
    assert real.result["summary"]["dsrnase2_axes_constant"] is True


def test_real_pareto_matches_an_independent_brute_force_per_stratum(real):
    cp3 = {r["window_id"]: r for r in read(ROOT / "results/bioinformatics/nb03/cp3", "candidate_unit_specificity.tsv")}
    axes = ("longest_exact_match", "covered_nt", "best_local_identity")
    by_id = {r["window_id"]: r for r in real.pareto}
    for length in STRATA:
        vectors = {wid: tuple(float(cp3[wid][f"{u}_{a}"]) for u in ("bicc_like", "dsrnase2") for a in axes)
                   for wid, r in by_id.items() if int(r["length_nt"]) == length}
        for wid, v in vectors.items():
            dominators = sum(all(x <= y for x, y in zip(u, v)) and any(x < y for x, y in zip(u, v)) for u in vectors.values())
            assert int(by_id[wid]["n_dominators"]) == dominators
            assert by_id[wid]["pareto_status"] == (sel.DOMINATED if dominators else sel.NONDOMINATED)


def test_real_priority_set_tiers_and_no_rescue_of_dominated_windows(real):
    for r in real.pareto:
        nondominated = r["pareto_status"] == sel.NONDOMINATED
        assert (r["priority_set"] == "true") == nondominated
        assert r["difference_tier"] == (r["count_intersected_observed_sequence_differences"] if nondominated else "NA")
    assert any(r["pareto_status"] == sel.DOMINATED and r["count_intersected_observed_sequence_differences"] == "0" for r in real.pareto)


def test_real_cells_are_maximal_contiguous_runs_with_uniform_status(real):
    by_id = {r["window_id"]: r for r in real.pareto}
    members = {}
    for m in real.members:
        members.setdefault(m["cell_id"], []).append(m)
    assert sum(len(v) for v in members.values()) == 7779 == len({m["window_id"] for m in real.members})

    def signature(r):
        return r["length_nt"], r["count_intersected_observed_sequence_differences"], tuple(r[c] for c in sel.AXIS_COLUMNS)

    for rows in members.values():
        starts = [int(m["cds_start"]) for m in rows]
        assert starts == list(range(starts[0], starts[0] + len(starts)))
        assert len({signature(by_id[m["window_id"]]) for m in rows}) == 1
        assert len({by_id[m["window_id"]]["pareto_status"] for m in rows}) == 1
    ordered = sorted(real.pareto, key=lambda r: (int(r["length_nt"]), int(r["cds_start"])))
    for a, b in zip(ordered, ordered[1:]):  # maximality: a run is broken only by a gap, another length or a new signature
        adjacent = a["length_nt"] == b["length_nt"] and int(b["cds_start"]) == int(a["cds_start"]) + 1
        assert (a["cell_id"] == b["cell_id"]) == (adjacent and signature(a) == signature(b))
    cell_rows = {c["cell_id"]: c for c in real.cells}
    assert set(cell_rows) == set(members) and all(int(cell_rows[i]["n_members"]) == len(m) for i, m in members.items())


def test_real_outputs_contain_no_representative_and_keep_descriptors_out_of_decisions(real):
    for rows in (real.pareto, real.cells, real.members, real.packet, real.bench):
        assert not [c for c in rows[0] if "representative" in c.lower() or c.lower() in {"approved", "rejected", "recommended", "shortlist"}]
    for columns in (sel.PARETO_COLUMNS, sel.CELL_COLUMNS, sel.MEMBER_COLUMNS):
        assert not [c for c in columns if "other_transcript" in c or "kmer" in c or "gc_fraction" in c or "benchmark" in c]


def test_real_manual_review_scope_is_exactly_l400_nondominated_and_pending(real):
    expected = {r["window_id"] for r in real.pareto if r["length_nt"] == "400" and r["pareto_status"] == sel.NONDOMINATED}
    assert {r["window_id"] for r in real.packet} == expected and len(real.packet) == len(expected)
    assert {r["length_nt"] for r in real.packet} == {"400"} and {r["pareto_status"] for r in real.packet} == {sel.NONDOMINATED}
    assert {r["manual_review_status"] for r in real.packet} == {"PENDING"}
    assert all(r["difference_tier"] == r["count_intersected_observed_sequence_differences"] for r in real.packet)
    scopes = {c["cell_id"]: c["manual_review_scope"] for c in real.cells}
    assert {scopes[r["cell_id"]] for r in real.packet} == {"NOMINAL_L400"}
    assert all(c["manual_review_scope"] == "NOT_PRIORITY" for c in real.cells if c["pareto_status"] == sel.DOMINATED)
    assert all(c["manual_review_scope"] == "SENSITIVITY_ONLY" for c in real.cells if c["pareto_status"] == sel.NONDOMINATED and c["length_nt"] != "400")


def test_real_other_transcript_hsp_reference_matches_the_packet(real):
    counts = {}
    for h in real.hsps:
        counts[h["window_id"]] = counts.get(h["window_id"], 0) + 1
    assert {r["window_id"]: int(r["other_transcript_n_hsps"]) for r in real.packet} == {r["window_id"]: counts.get(r["window_id"], 0) for r in real.packet}


def test_real_benchmark_comparison_is_descriptive_only(real):
    benchmark, equivalent = real.bench
    assert benchmark["window_id"] == "BC-BENCH-0215-0587" and benchmark["membership"] == "REFERENCE_SET"
    assert (benchmark["participates_in_pareto"], benchmark["participates_in_cells"]) == ("false", "false")
    assert (benchmark["pareto_status"], benchmark["cell_id"], benchmark["difference_tier"]) == ("NA", "NA", "NA")
    assert equivalent["window_id"] == "BC-L373-0215-0587" and equivalent["membership"] == "DESIGN_SPACE"
    assert equivalent["sequence_sha256"] == benchmark["sequence_sha256"] and equivalent["participates_in_pareto"] == "true"


def test_real_outputs_are_in_canonical_display_order_and_byte_identical_on_rerun(real):
    for name in sel.DETERMINISTIC_OUTPUTS + ("run_manifest.json",):
        assert (real.first / name).read_bytes() == (real.second / name).read_bytes(), name
    cell_start = {c["cell_id"]: int(c["cds_start_min"]) for c in real.cells}
    keys = [(int(r["length_nt"]), r["pareto_status"] != sel.NONDOMINATED, int(r["count_intersected_observed_sequence_differences"]),
             cell_start[r["cell_id"]], int(r["cds_start"]), r["window_id"]) for r in real.pareto]
    assert keys == sorted(keys)
    assert real.result["summary"]["display_order"] == {"classification": sel.DISPLAY_ORDER_CLASSIFICATION, "fields": list(sel.DISPLAY_FIELDS),
                                                       "is_ranking": False, "is_tie_breaker": False}
    assert real.result["manifest"]["selection_policy_commit"] == "b8d15f36338922f870ec9f0bdd8004c1c04082ed"
    text = (real.first / "run_manifest.json").read_text(encoding="utf-8")
    assert str(real.first) not in text and "utc" not in text.lower()


def test_regression_snapshot_of_one_run_not_a_policy_definition(real):
    """Computational snapshot of the first CP4A run; a change here signals different inputs, not a policy change."""
    strata = real.result["summary"]["strata"]
    assert {s: v["n_nondominated"] for s, v in strata.items()} == {"L300": 39, "L373": 26, "L400": 10, "L500": 17}
    assert len(real.packet) == 10 and len(real.cells) == sum(v["n_cells"] for v in strata.values())
