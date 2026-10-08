from __future__ import annotations

from collections import Counter
import csv
import hashlib
from fractions import Fraction
from pathlib import Path
import random
import shutil

import pytest

from zeaguard import nb02_design, nb03_criteria as criteria, nb03_design as design

ROOT = Path(__file__).resolve().parents[1]
HAS_REAL_INPUTS = (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").is_file() and shutil.which("dustmasker") is not None
needs_real = pytest.mark.skipif(not HAS_REAL_INPUTS, reason="needs the hash-pinned TSA and dustmasker")


@pytest.fixture(scope="module")
def parameters():
    return design.design_parameters(criteria.load_registry(ROOT))


@pytest.fixture(scope="module")
def reference():
    if not HAS_REAL_INPUTS:
        pytest.skip("needs the hash-pinned TSA and dustmasker")
    return design.verified_reference(ROOT)


@pytest.fixture(scope="module")
def context(reference, parameters):
    return design.DesignContext(reference, parameters)


def test_parameters_are_read_from_cp1_registry(parameters):
    assert (parameters.cds_length, parameters.length_min, parameters.length_max, parameters.k) == (2337, 300, 500, 21)
    assert (parameters.ranking_length, parameters.benchmark_length, parameters.sensitivity_lengths) == (400, 373, (300, 500))
    assert parameters.terciles == (Fraction(1, 3), Fraction(2, 3))
    assert parameters.strata == {300: "SENSITIVITY_L300", 373: "BENCHMARK_COMPARATOR_L373",
                                 400: "RANKING_L400", 500: "SENSITIVITY_L500"}


def test_all_intervals_counts_and_canonical_order_follow_closed_form(parameters):
    counts = Counter()
    previous = None
    for length, start, end in design.iter_intervals(parameters):
        assert 1 <= start <= end <= 2337 and end - start + 1 == length
        if previous is not None:
            assert (length, start) > previous
        previous = (length, start)
        counts[length] += 1
    expected_total = sum(2337 - length + 1 for length in range(300, 501))
    assert sum(counts.values()) == expected_total == 389538
    assert len(counts) == 201
    assert all(counts[length] == 2337 - length + 1 for length in range(300, 501))


@pytest.mark.parametrize("length, count", [(300, 2038), (373, 1965), (400, 1938), (500, 1838)])
def test_first_last_and_count_of_each_stratum(length, count):
    starts = nb02_design.windows_of_length(2337, length)
    assert len(starts) == 2337 - length + 1 == count
    assert (starts[0], starts[0] + length - 1) == (1, length)
    assert (starts[-1], starts[-1] + length - 1) == (count, 2337)
    assert design.window_id(length, 1, length) == f"BC-L{length}-0001-{length:04d}"
    assert design.window_id(length, count, 2337) == f"BC-L{length}-{count:04d}-2337"


def test_ids_and_sequence_hashes_are_deterministic(context):
    assert design.window_id(400, 1, 400) == "BC-L400-0001-0400"
    assert design.window_id(400, 1938, 2337) == "BC-L400-1938-2337"
    row = context.describe(1, 400, 0)
    assert row["sequence_sha256"] == hashlib.sha256(context.cds[:400].encode("ascii")).hexdigest()
    assert context.describe(1, 400, 0) == row
    with pytest.raises(ValueError):
        design.window_id(400, 1, 399)


def test_only_structural_hard_filters_are_applied(parameters, context):
    assert design.passes_hard_filters("A" * 300, 1, 300, parameters)
    assert design.passes_hard_filters("G" * 500, 1, 500, parameters)
    assert not design.passes_hard_filters("A" * 299, 1, 299, parameters)
    assert not design.passes_hard_filters("A" * 501, 1, 501, parameters)
    assert not design.passes_hard_filters("A" * 300, 0, 299, parameters)
    assert not design.passes_hard_filters("A" * 300, 2039, 2338, parameters)
    assert not design.passes_hard_filters("N" + "A" * 299, 1, 300, parameters)
    # Fully masked intervals and intervals intersecting observed differences remain eligible.
    assert context.describe(500, 899, 1)["hard_filters_pass"] is True
    with pytest.raises(design.NB03DesignError):
        context.describe(1, 299, 0)


def test_difference_count_positions_and_potential_subwindows(context):
    row = context.describe(1000, 1399, 0)
    assert row["intersected_observed_sequence_difference_positions"] == "1092,1120,1287"
    assert row["count_intersected_observed_sequence_differences"] == 3
    assert row["potential_21nt_window_count"] == 400 - 20 == 380
    affected = sum(any(s <= p <= s + 20 for p in (1092, 1120, 1287)) for s in range(1000, 1380))
    assert row["potential_21nt_windows_intersecting_observed_sequence_differences"] == affected
    assert row["potential_21nt_windows_unaffected_count"] == 380 - affected
    assert float(row["fraction_unaffected"]) == pytest.approx((380 - affected) / 380, abs=0.0000005)
    boundary = context.describe(597, 996, 0)
    assert boundary["potential_21nt_windows_intersecting_observed_sequence_differences"] == 1


def test_affected_subwindows_are_counted_once_for_multiple_differences():
    # Two adjacent sites in the interior cover 22 distinct starts, rather than 42.
    assert nb02_design.intercepted_subwindows(1, 400, [100, 101], 21) == 22
    rng = random.Random(31)
    for _ in range(150):
        start = rng.randint(1, 100)
        length = rng.randint(300, 500)
        end = start + length - 1
        positions = sorted(rng.sample(range(start, end + 1), rng.randint(0, 7)))
        expected = sum(any(s <= p <= s + 20 for p in positions) for s in range(start, end - 19))
        assert nb02_design.intercepted_subwindows(start, end, positions, 21) == expected


@pytest.mark.parametrize("start,end,overlap,relation", [
    (588, 987, 0, "DISJOINT"),
    (200, 599, 373, "CONTAINS_BENCHMARK"),
    (250, 549, 300, "FULLY_WITHIN"),
    (215, 587, 373, "EXACT_MATCH"),
    (216, 588, 372, "PARTIAL_OVERLAP"),
    (1, 400, 186, "PARTIAL_OVERLAP"),
    (1, 215, 1, "PARTIAL_OVERLAP"),
])
def test_benchmark_overlap_has_explicit_denominators_and_unambiguous_categories(start, end, overlap, relation):
    result = design.benchmark_overlap(start, end, 215, 587)
    assert result["overlap_with_benchmark_nt"] == overlap
    assert result["overlap_fraction_of_candidate"] == overlap / (end - start + 1)
    assert result["overlap_fraction_of_benchmark"] == overlap / 373
    assert result["relation_to_benchmark"] == relation
    assert "overlap_fraction" not in result


def test_descriptive_positions_and_overlap_do_not_enter_decisional_signature(context):
    # Synthetic vectors only. No candidate specificity is calculated here.
    def signature(row):
        positions = frozenset(int(p) for p in row["intersected_observed_sequence_difference_positions"].split(",") if p)
        return criteria.decisive_signature(criteria.SpecificityEvidence("synthetic", row["length_nt"], positions,
                                                                       (1, 2, 3), (4, 5, 6)))

    left, right = context.describe(198, 597, 0), context.describe(693, 1092, 0)
    assert left["count_intersected_observed_sequence_differences"] == right["count_intersected_observed_sequence_differences"] == 1
    assert left["relation_to_benchmark"] != right["relation_to_benchmark"]
    assert left["intersected_observed_sequence_difference_positions"] != right["intersected_observed_sequence_difference_positions"]
    assert signature(left) == signature(right)
    assert set(criteria.BENCHMARK_RELATION_DESCRIPTORS) <= set(criteria.load_registry(ROOT)["policy"]["cell_signature_excludes"])


def test_output_schema_has_no_specificity_selection_or_nature_claim():
    for columns in (design.WINDOW_COLUMNS, design.BENCHMARK_COLUMNS):
        assert not [c for c in columns if any(f in c for f in design.FORBIDDEN_COLUMN_FRAGMENTS)]
        assert not [c for c in columns if any(f in c for f in ("variant", "allele", "polymorph"))]
        assert "overlap_fraction" not in columns
        assert "sequence" not in columns
    assert not (ROOT / "data/reference/nb03_bicc_candidate_regions.tsv").exists()
    assert not (ROOT / "data/reference/nb03_bicc_candidate_regions.fasta").exists()


@pytest.fixture(scope="module")
def real_runs(tmp_path_factory):
    if not HAS_REAL_INPUTS:
        pytest.skip("needs the hash-pinned TSA and dustmasker")
    first_dir = tmp_path_factory.mktemp("nb03_cp2_first")
    second_dir = tmp_path_factory.mktemp("nb03_cp2_second")
    commands = []
    original_run = nb02_design.subprocess.run

    def only_descriptive_commands(command, *args, **kwargs):
        tool = Path(command[0]).name
        assert tool in {"dustmasker", "git"}, f"CP2 tried to execute a forbidden tool: {command}"
        if tool == "git":
            assert command[3] in {"rev-parse", "status"}
        commands.append(command)
        return original_run(command, *args, **kwargs)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(nb02_design.subprocess, "run", only_descriptive_commands)
        first = design.run_cp2(ROOT, first_dir)
        second = design.run_cp2(ROOT, second_dir)
    return first, first_dir, second, second_dir, commands


@needs_real
def test_real_outputs_match_formula_and_every_sequence_is_reconstructible(real_runs, context):
    first, out, _, _, _ = real_runs
    counts = Counter()
    previous = None
    with (out / "design_space.tsv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert tuple(reader.fieldnames) == design.WINDOW_COLUMNS
        for row in reader:
            length, start, end = (int(row[c]) for c in ("length_nt", "cds_start", "cds_end"))
            assert 1 <= start <= end <= len(context.cds) and end - start + 1 == length
            if previous is not None:
                assert (length, start) > previous
            previous = (length, start)
            sequence = context.cds[start - 1:end]
            assert len(sequence) == length and set(sequence) <= set("ACGT")
            assert row["sequence_sha256"] == hashlib.sha256(sequence.encode("ascii")).hexdigest()
            assert row["window_id"] == design.window_id(length, start, end)
            assert row["membership"] == "DESIGN_SPACE" and row["target"] == "BICC" and row["hard_filters_pass"] == "True"
            inside = [p for p in context.positions if start <= p <= end]
            assert row["intersected_observed_sequence_difference_positions"] == ",".join(map(str, inside))
            assert int(row["count_intersected_observed_sequence_differences"]) == len(inside)
            assert int(row["potential_21nt_window_count"]) == length - 20
            affected = int(row["potential_21nt_windows_intersecting_observed_sequence_differences"])
            unaffected = int(row["potential_21nt_windows_unaffected_count"])
            assert affected + unaffected == length - 20
            assert affected == nb02_design.intercepted_subwindows(start, end, inside, 21)
            # Compare the declared six-decimal serialization exactly, including half-way rounding.
            assert row["fraction_unaffected"] == f"{unaffected / (length - 20):.6f}"
            assert row["gc_fraction"] == f"{(sequence.count('G') + sequence.count('C')) / length:.6f}"
            assert 0 <= float(row["low_complexity_fraction"]) <= 1
            assert 1 <= int(row["longest_homopolymer"]) <= length
            expected_overlap = design.benchmark_overlap(start, end, *context.benchmark)
            assert int(row["overlap_with_benchmark_nt"]) == expected_overlap["overlap_with_benchmark_nt"]
            assert row["relation_to_benchmark"] == expected_overlap["relation_to_benchmark"]
            for key in ("overlap_fraction_of_candidate", "overlap_fraction_of_benchmark"):
                assert row[key] == f"{expected_overlap[key]:.6f}"
            counts[length] += 1
    assert sum(counts.values()) == sum(2337 - length + 1 for length in range(300, 501)) == 389538
    assert first["summary"]["total_windows"] == first["summary"]["hard_filters_pass"] == 389538
    assert first["summary"]["hard_filters_fail"] == 0 and first["summary"]["cds_contains_only_acgt"] is True
    assert all(counts[length] == 2337 - length + 1 for length in range(300, 501))
    for length, expected in ((300, 2038), (373, 1965), (400, 1938), (500, 1838)):
        assert counts[length] == first["summary"]["strata"][str(length)]["n_windows"] == expected


@needs_real
def test_benchmark_is_a_separate_reference_row_and_geometric_design_window_stays_design_space(real_runs):
    first, out, _, _, _ = real_runs
    with (out / "benchmark_descriptor.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 1
    benchmark = rows[0]
    assert benchmark["window_id"] == "BC-BENCH-0215-0587" and benchmark["membership"] == "REFERENCE_SET"
    assert benchmark["published_reported_length_nt"] == "372"
    assert benchmark["length_nt"] == benchmark["operational_length_nt"] == "373"
    assert benchmark["sequence_sha256"] == "e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb"
    assert benchmark["count_intersected_observed_sequence_differences"] == "0"
    assert benchmark["intersected_observed_sequence_difference_positions"] == ""
    assert benchmark["potential_21nt_window_count"] == benchmark["potential_21nt_windows_unaffected_count"] == "353"
    assert benchmark["fraction_unaffected"] == "1.000000"
    assert benchmark["relation_to_benchmark"] == "EXACT_MATCH"
    assert benchmark["experimental_protocol_verification"] == "PROJECT_PROVIDED_NOT_AGENT_VERIFIED"
    with (out / "design_space.tsv").open(encoding="utf-8", newline="") as handle:
        equivalent = next(row for row in csv.DictReader(handle, delimiter="\t") if row["window_id"] == "BC-L373-0215-0587")
    assert equivalent["membership"] == "DESIGN_SPACE" and equivalent["sequence_sha256"] == benchmark["sequence_sha256"]
    assert equivalent["relation_to_benchmark"] == "EXACT_MATCH"
    assert equivalent["low_complexity_fraction"] == benchmark["low_complexity_fraction"]
    assert first["summary"]["strata"]["373"]["benchmark_relation_distribution"]["EXACT_MATCH"] == 1


@needs_real
def test_all_four_outputs_are_byte_identical_between_independent_runs(real_runs):
    first, first_dir, second, second_dir, _ = real_runs
    assert first["outputs_sha256"] == second["outputs_sha256"]
    assert set(p.name for p in first_dir.iterdir()) == set(design.OUTPUT_NAMES)
    for name in design.OUTPUT_NAMES:
        # Chunk comparison checks actual bytes in addition to hashes, without loading the mass TSV into RAM.
        with (first_dir / name).open("rb") as left, (second_dir / name).open("rb") as right:
            while True:
                a, b = left.read(1024 * 1024), right.read(1024 * 1024)
                assert a == b
                if not a:
                    break
        hasher = hashlib.sha256()
        with (first_dir / name).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(block)
        assert hasher.hexdigest() == first["outputs_sha256"][name]
    assert first["manifest"]["outputs_sha256"] == {k: v for k, v in first["outputs_sha256"].items() if k != "run_manifest.json"}


@needs_real
def test_cp2_launches_only_dustmasker_and_read_only_git_commands(real_runs):
    result, _, _, _, commands = real_runs
    assert {Path(c[0]).name for c in commands} == {"dustmasker", "git"}
    dust_runs = [c for c in commands if c[0] == "dustmasker" and "-in" in c]
    assert len(dust_runs) == 2 * (201 + 1)
    assert "candidate_x_TSA_BLAST" in result["manifest"]["not_done"]
    assert "Pareto" in result["manifest"]["not_done"] and "cells" in result["manifest"]["not_done"]
    assert "shortlist" in result["manifest"]["not_done"]
    assert result["manifest"]["parameters"]["orientation"] == "sense"
