from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import random
import shutil

import pytest
import yaml

from zeaguard import nb02_criteria as crit
from zeaguard import nb02_design as design

ROOT = Path(__file__).resolve().parents[1]
HAS_TSA = (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").is_file()
HAS_DUST = shutil.which("dustmasker") is not None
needs_dust = pytest.mark.skipif(not HAS_DUST, reason="dustmasker (BLAST+) is not installed")
needs_real_run = pytest.mark.skipif(not (HAS_TSA and HAS_DUST), reason="needs the hash-pinned TSA and dustmasker")
BENCHMARK_SHA = "97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179"


@pytest.fixture(scope="module")
def registry():
    return yaml.safe_load((ROOT / crit.REGISTRY_PATH).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ parameters come from the frozen registry
def test_design_parameters_are_read_from_the_registry(registry):
    params = design.design_parameters(registry)
    assert (params.cds_length, params.length_min, params.length_max, params.k) == (1425, 300, 500, 21)
    assert (params.ranking_length, params.benchmark_length, params.sensitivity_lengths) == (400, 330, (300, 500))
    assert params.terciles == (Fraction(1, 3), Fraction(2, 3))
    assert params.strata == {300: "SENSITIVITY_L300", 330: "BENCHMARK_COMPARATOR_L330", 400: "RANKING_L400", 500: "SENSITIVITY_L500"}


# ------------------------------------------------------------------ window space
def test_continuous_space_has_206226_windows_and_every_window_fits_without_padding():
    assert design.total_windows(1425, 300, 500) == 206226
    assert len(design.windows_of_length(1425, 400)) == 1026
    for length in (300, 400, 500, 1425):
        starts = design.windows_of_length(1425, length)
        assert starts[0] == 1 and starts[-1] + length - 1 == 1425
    assert len(design.windows_of_length(10, 10)) == 1 and len(design.windows_of_length(10, 11)) == 0


def test_window_id_is_zero_padded_and_unique_per_interval():
    assert design.window_id(400, 1, 400) == "D2-L400-0001-0400"
    ids = {design.window_id(length, start, start + length - 1) for length in (300, 301) for start in design.windows_of_length(1425, length)}
    assert len(ids) == (1426 - 300) + (1426 - 301)


# ------------------------------------------------------------------ descriptors
def test_gc_and_homopolymer_on_synthetic_sequences():
    assert design.gc_fraction("GGCCAATT") == 0.5
    assert design.gc_fraction("AAAA") == 0.0 and design.gc_fraction("GCGC") == 1.0
    assert design.longest_homopolymer("ACGT") == 1
    assert design.longest_homopolymer("AACCCGGTTTT") == 4
    assert design.longest_homopolymer("A") == 1


def test_variants_in_window_are_inclusive_at_both_borders():
    positions = [9, 30, 219]
    assert design.variants_in_window(positions, 9, 30) == [9, 30]
    assert design.variants_in_window(positions, 10, 29) == []
    assert design.variants_in_window(positions, 30, 219) == [30, 219]
    assert design.variants_in_window(positions, 31, 218) == []


def test_longest_conserved_subregion():
    assert design.longest_conserved_subregion(1, 100, []) == 100
    assert design.longest_conserved_subregion(1, 100, [50]) == 50
    assert design.longest_conserved_subregion(10, 20, [10, 20]) == 9  # variants at both ends leave 11..19
    assert design.longest_conserved_subregion(10, 20, [15]) == 5


def _brute_intercepted(start, end, positions, k):
    return sum(any(j <= p <= j + k - 1 for p in positions) for j in range(start, end - k + 2))


def test_intercepted_subwindows_matches_brute_force_including_overlaps_and_edges():
    rng = random.Random(7)
    for _ in range(400):
        length = rng.randint(21, 80)
        start = rng.randint(1, 50)
        end = start + length - 1
        positions = sorted(rng.sample(range(start, end + 1), rng.randint(0, 6)))
        assert design.intercepted_subwindows(start, end, positions, 21) == _brute_intercepted(start, end, positions, 21), (start, end, positions)


def test_a_single_variant_intercepts_at_most_k_subwindows_and_none_when_absent():
    assert design.intercepted_subwindows(1, 400, [], 21) == 0
    assert design.intercepted_subwindows(1, 400, [200], 21) == 21
    assert design.intercepted_subwindows(1, 400, [1], 21) == 1  # at the window edge only one sub-window covers it
    assert design.intercepted_subwindows(1, 400, [400], 21) == 1


def test_region_position_is_a_label_with_exact_tercile_boundaries():
    terciles = (Fraction(1, 3), Fraction(2, 3))
    assert design.region_position(1, 300, 1425, terciles)[1] == "BOUNDARY"  # contains the whole start codon
    assert design.region_position(1126, 1425, 1425, terciles)[1] == "BOUNDARY"
    assert design.region_position(100, 399, 1425, terciles)[1] == "5_PRIME"
    assert design.region_position(500, 899, 1425, terciles)[1] == "CENTRAL"
    assert design.region_position(900, 1300, 1425, terciles)[1] == "3_PRIME"
    # toy CDS of 9 nt: a midpoint exactly on a tercile boundary falls in the upper class (never < 1/3, never < 2/3)
    assert design.region_position(2, 3, 9, terciles)[1] == "5_PRIME"  # 5/18
    midpoint, label = design.region_position(2, 4, 9, terciles)  # 6/18 = 1/3 exactly
    assert midpoint == pytest.approx(1 / 3) and label == "CENTRAL"
    midpoint, label = design.region_position(5, 7, 9, terciles)  # 12/18 = 2/3 exactly
    assert midpoint == pytest.approx(2 / 3) and label == "3_PRIME"


@needs_dust
def test_dustmasker_flags_low_complexity_and_spares_random_sequence():
    rng = random.Random(1)
    random_sequence = "".join(rng.choice("ACGT") for _ in range(300))
    fractions = design.dustmasker_fractions({"polyA": "A" * 300, "random": random_sequence, "repeat": "GATTACA" * 40})
    assert fractions["polyA"] == 1.0 and fractions["repeat"] > 0.9 and fractions["random"] < 0.2


# ------------------------------------------------------------------ CP2 stays descriptive
def test_cp2_output_columns_never_belong_to_specificity_cells_ranking_or_recommendation():
    for columns in (design.WINDOW_COLUMNS, design.SUMMARY_COLUMNS, design.TRACK_COLUMNS):
        assert not [c for c in columns if any(f in c for f in design.FORBIDDEN_COLUMN_FRAGMENTS)]
    assert "target_region_position" in design.WINDOW_COLUMNS  # annotation only; registry C13 keeps it out of every decision


# ------------------------------------------------------------------ the real CP2 run (needs the TSA and dustmasker)
@pytest.fixture(scope="module")
def cp2(tmp_path_factory):
    out = tmp_path_factory.mktemp("cp2")
    return design.run_cp2(ROOT, out), out


@needs_real_run
def test_cp2_counts_and_files(cp2):
    result, out = cp2
    counts = result["manifest"]["counts"]
    assert counts["total_windows_in_continuous_space"] == 206226
    assert counts["strata_windows_written"] == (1426 - 300) + (1426 - 330) + (1426 - 400) + (1426 - 500) == 4174
    assert counts["lengths_summarised"] == 201 and counts["position_track_rows"] == 1425
    assert sum(row["n_windows"] for row in result["summary"]) == 206226
    assert {p.name for p in out.iterdir()} == {
        "window_space_summary.tsv", "strata_windows.tsv", "benchmark_window.tsv", "position_tracks.tsv", "run_manifest.json"}
    assert "BLAST specificity search" in result["manifest"]["not_done"]


@needs_real_run
def test_cp2_benchmark_row_is_the_verified_330_nt_fragment(cp2):
    row = cp2[0]["benchmark"]
    assert (row["candidate_id"], row["length_nt"], row["cds_start"], row["cds_end"]) == ("D2-BENCH-0814-1143", 330, 814, 1143)
    assert row["sequence_sha256"] == BENCHMARK_SHA and row["reference_set_member"] is True
    assert (row["n_variant_sites"], row["variant_positions"], row["n_defined_variants"], row["n_iupac_variants"]) == (1, "816", 1, 0)
    assert (row["n_potential_windows"], row["n_windows_intercepting_variants"]) == (310, 3)
    assert row["fraction_potential_windows_unaffected"] == f"{307 / 310:.6f}"
    assert row["target_region_position"] == "3_PRIME"
    assert (row["transcript_start"], row["transcript_end"]) == (1477 - 1143 + 1, 1477 - 814 + 1)
    members = [w for w in cp2[0]["windows"] if w["reference_set_member"]]
    assert len(members) == 1 and members[0]["sequence_sha256"] == BENCHMARK_SHA and members[0]["length_stratum"] == "BENCHMARK_COMPARATOR_L330"


@needs_real_run
def test_cp2_strata_variants_and_tracks_are_consistent(cp2):
    result = cp2[0]
    ranking = [w for w in result["windows"] if w["length_stratum"] == "RANKING_L400"]
    assert len(ranking) == 1026 and {w["length_nt"] for w in ranking} == {400}
    assert all(1 <= w["cds_start"] and w["cds_end"] <= 1425 for w in result["windows"])
    assert all(w["n_variant_sites"] == w["n_defined_variants"] + w["n_iupac_variants"] for w in result["windows"])
    assert all(w["n_windows_intercepting_variants"] <= 21 * w["n_variant_sites"] for w in result["windows"])
    tracks = result["tracks"]
    sites = [t["cds_pos"] for t in tracks if t["is_known_variant_site"]]
    assert sites == [9, 30, 219, 312, 350, 816, 1272]
    assert next(t for t in tracks if t["cds_pos"] == 1272)["nb01_read_support"] == "BOTH_ALLELES_SUPPORTED"
    assert (tracks[0]["in_start_codon"], tracks[-1]["in_stop_codon"], tracks[-1]["transcript_pos"]) == (True, True, 1477 - 1425 + 1)


@needs_real_run
def test_cp2_is_deterministic_and_records_inputs(cp2, tmp_path):
    first = cp2[0]["manifest"]
    second = design.run_cp2(ROOT, tmp_path)["manifest"]
    assert first["outputs_sha256"] == second["outputs_sha256"]
    assert first["inputs"]["criteria_registry_sha256"] == crit.registry_sha256(ROOT / crit.REGISTRY_PATH)
    assert first["inputs"]["operational_cds_sha256"] == "bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7"
