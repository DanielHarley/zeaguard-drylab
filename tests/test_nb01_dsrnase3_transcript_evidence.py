"""Synthetic validation of the dsRNase-3 642/643 transcript-evidence command.

Every case the pre-run requires explicitly: the exact junction, a one-base
shift on either edge, a deletion inside a flanking block, a short anchor, an
ambiguous mapping, two mates of one pair both crossing, insufficient coverage,
invalid and truncated input, and an attempt to overwrite an earlier execution.

No real library is involved. All coordinates are the declared ones of the
target junction, so the fixtures exercise the same arithmetic the real round
will.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from zeaguard import nb01_dsrnase3_transcript_evidence as ev

SEQUENCE_LENGTH = 146_000_000

TARGET = ev.TARGET_JUNCTION
# The last 50 nt of the upstream flank and the first 50 nt of the downstream
# flank: the windows the criteria call informative coverage over.
UP_WINDOW_START = ev.FLANKS["upstream"]["ref_end"] - 49          # 122,007,299
DOWN_WINDOW_START = ev.FLANKS["downstream"]["ref_start"]         # 122,012,479

CROSSING_CIGAR = f"50M{TARGET.intron_len_nt}N50M"
CONTROL_456 = ev.CONTROL_JUNCTIONS[0]
CONTROL_870 = ev.CONTROL_JUNCTIONS[1]


def record_line(qname: str, pos: int, cigar: str, flag: int = 0, mapq: int = 60,
                rname: str = "OZ319704.1", tags: tuple[str, ...] = ()) -> str:
    return "\t".join([qname, str(flag), rname, str(pos), str(mapq), cigar,
                      "=", "0", "0", "*", "*", *tags])


def sam_text(lines: list[str], sequence_length: int = SEQUENCE_LENGTH,
             with_pg: bool = True, with_sq: bool = True) -> str:
    header = ["@HD\tVN:1.6\tSO:coordinate"]
    if with_sq:
        header.append(f"@SQ\tSN:OZ319704.1\tLN:{sequence_length}")
    if with_pg:
        header.append("@PG\tID:hisat2\tPN:hisat2\tVN:2.2.1\t"
                      "CL:hisat2 -p 8 --dta --max-intronlen 50000 -x ihDalMaid1.1")
    return "\n".join(header + lines) + "\n"


def parse_one(cigar: str, pos: int, **kwargs):
    _, records = ev.parse_sam(record_line("r1", pos, cigar, **kwargs))
    return records[0]


def observe(cigar: str, pos: int, criteria: ev.Criteria | None = None, **kwargs) -> dict:
    record = parse_one(cigar, pos, **kwargs)
    specs = (TARGET, *ev.CONTROL_JUNCTIONS)
    return ev.observe_record(record, 0, specs, criteria or ev.Criteria())


def target_junctions(observation: dict) -> list[dict]:
    return [j for j in observation["junctions"] if j["junction_name"] == TARGET.name]


def count(lines: list[str], criteria: ev.Criteria | None = None) -> dict:
    _, records = ev.parse_sam(sam_text(lines))
    return ev.count_library(records, criteria or ev.Criteria())


# --------------------------------------------------------------------------
# The declared question
# --------------------------------------------------------------------------


def test_declared_junction_matches_the_run_record_coordinates():
    # Last aligned base 122,007,348 and first aligned base 122,012,479, so the
    # intron is the 5,130 nt between them, 1-based inclusive.
    assert (TARGET.intron_start, TARGET.intron_end) == (122_007_349, 122_012_478)
    assert TARGET.intron_len_nt == 5_130
    assert (TARGET.cds_upstream, TARGET.cds_downstream) == (642, 643)
    assert TARGET.annotated_intron is False
    assert ev.FLANKS["upstream"]["ref_end"] == TARGET.intron_start - 1
    assert ev.FLANKS["downstream"]["ref_start"] == TARGET.intron_end + 1
    assert all(spec.annotated_intron for spec in ev.CONTROL_JUNCTIONS)


def test_reference_aligned_intervals_skip_deletions_and_junctions():
    intervals = ev.ref_aligned_intervals(ev.parse_cigar("10M2D5M100N20M"), 1_000)
    assert intervals == [(1_000, 1_009), (1_012, 1_016), (1_117, 1_136)]


# --------------------------------------------------------------------------
# Junction recognition
# --------------------------------------------------------------------------


def test_exact_junction_with_long_anchors_is_support():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "support"
    assert junction["counted_as_support"] is True
    assert (junction["intron_ref_start"], junction["intron_ref_end"]) == \
        (TARGET.intron_start, TARGET.intron_end)
    assert junction["anchor_upstream_aligned_nt"] == 50
    assert junction["anchor_downstream_aligned_nt"] == 50


def test_one_base_shift_on_both_edges_is_a_neighbour_not_support():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START + 1)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "neighbour"
    assert junction["category"] == "neighbour"
    assert junction["counted_as_support"] is False
    assert (junction["delta_intron_start_nt"], junction["delta_intron_end_nt"]) == (1, 1)


def test_one_base_shift_on_the_acceptor_only_keeps_the_donor_but_is_not_support():
    observation = observe(f"50M{TARGET.intron_len_nt + 1}N50M", UP_WINDOW_START)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "donor_only"
    assert junction["counted_as_support"] is False
    assert junction["delta_intron_start_nt"] == 0
    assert junction["delta_intron_end_nt"] == 1


def test_a_deletion_inside_the_upstream_block_leaves_the_junction_exact():
    # 30M2D20M aligns 50 query bases over 52 reference bases and still ends on
    # the declared donor, so the junction stays exact and the anchor is the
    # aligned bases, not the reference span.
    observation = observe(f"30M2D20M{TARGET.intron_len_nt}N50M", UP_WINDOW_START - 2)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "support"
    assert junction["anchor_upstream_aligned_nt"] == 50


def test_an_insertion_does_not_inflate_the_anchor():
    observation = observe(f"6M4I6M{TARGET.intron_len_nt}N50M", TARGET.intron_start - 12)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    # 12 aligned bases, not 16: the 4 inserted bases align to nothing.
    assert junction["anchor_upstream_aligned_nt"] == 12
    assert junction["category"] == "support"


def test_a_short_anchor_is_recorded_separately_and_is_not_support():
    observation = observe(f"8M{TARGET.intron_len_nt}N50M", TARGET.intron_start - 8)
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "short_anchor"
    assert junction["anchor_upstream_aligned_nt"] == 8
    assert junction["counted_as_support"] is False


def test_a_reverse_strand_crossing_read_is_support_on_the_same_coordinates():
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START, flag=16)
    assert observation["strand"] == "-"
    assert target_junctions(observation)[0]["category"] == "support"


def test_a_junction_far_from_every_declared_one_is_not_recorded():
    observation = observe("50M4000N50M", 1_000_000)
    assert observation["junctions"] == []
    assert observation["n_cigar_junctions"] == 1


def test_the_two_annotated_control_junctions_are_recognised():
    control_a = observe(f"50M{CONTROL_456.intron_len_nt}N50M",
                        CONTROL_456.intron_start - 50)
    control_b = observe(f"50M{CONTROL_870.intron_len_nt}N50M",
                        CONTROL_870.intron_start - 50)
    assert [j["junction_name"] for j in control_a["junctions"]] == [CONTROL_456.name]
    assert control_a["junctions"][0]["category"] == "support"
    assert [j["junction_name"] for j in control_b["junctions"]] == [CONTROL_870.name]
    assert control_b["junctions"][0]["category"] == "support"


# --------------------------------------------------------------------------
# Disqualification: ambiguity, duplicates, secondary and supplementary records
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs, reason", [
    ({"mapq": 1}, "ambiguous_mapq_1"),
    ({"tags": ("NH:i:3",)}, "ambiguous_nh_3"),
    ({"flag": 0x100}, "secondary_alignment"),
    ({"flag": 0x800}, "supplementary_alignment"),
    ({"flag": 0x400}, "flagged_duplicate"),
])
def test_a_disqualified_crossing_read_is_never_support(kwargs, reason):
    observation = observe(CROSSING_CIGAR, UP_WINDOW_START, **kwargs)
    assert observation["disqualified_by"] == reason
    junction = target_junctions(observation)[0]
    assert junction["boundary_match"] == "exact"
    assert junction["category"] == "disqualified"
    assert junction["counted_as_support"] is False


def test_a_non_integer_nh_tag_is_refused():
    with pytest.raises(ev.VerificationError, match="NH tag is not an integer"):
        observe(CROSSING_CIGAR, UP_WINDOW_START, tags=("NH:i:many",))


def test_each_disqualification_lands_in_its_own_library_column():
    counts = count([
        record_line("amb", UP_WINDOW_START, CROSSING_CIGAR, mapq=1),
        record_line("dup", UP_WINDOW_START, CROSSING_CIGAR, flag=0x400),
        record_line("sec", UP_WINDOW_START, CROSSING_CIGAR, flag=0x100),
        record_line("sup", UP_WINDOW_START, CROSSING_CIGAR, flag=0x800),
    ])
    assert counts["support_fragments"] == 0
    assert (counts["ambiguous_reads"], counts["ambiguous_fragments"]) == (1, 1)
    assert (counts["duplicate_reads"], counts["duplicate_fragments"]) == (1, 1)
    assert counts["secondary_reads"] == 1
    assert counts["supplementary_reads"] == 1
    assert counts["disqualified_at_junction_fragments"] == 4


# --------------------------------------------------------------------------
# Per-fragment counting
# --------------------------------------------------------------------------


def test_both_mates_of_one_pair_crossing_count_as_one_fragment():
    counts = count([
        record_line("pair1", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x40),
        record_line("pair1", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x80),
    ])
    assert counts["support_reads"] == 2
    assert counts["support_fragments"] == 1


def test_mates_bridging_the_two_flanks_are_counted_apart_from_support():
    counts = count([
        record_line("bridge", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("bridge", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
    ])
    assert counts["support_fragments"] == 0
    assert counts["mate_bridge_fragments"] == 1
    assert counts["mate_bridge_fragment_names"] == ["bridge"]


def test_a_pair_with_a_crossing_read_is_not_also_counted_as_bridged():
    counts = count([
        record_line("both", UP_WINDOW_START, CROSSING_CIGAR, flag=0x1 | 0x40),
        record_line("both", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
    ])
    assert counts["support_fragments"] == 1
    assert counts["mate_bridge_fragments"] == 0


def test_records_on_another_sequence_are_counted_and_not_analysed():
    counts = count([
        record_line("elsewhere", 1_000, "50M", rname="OZ319705.1"),
        record_line("here", UP_WINDOW_START, "50M"),
    ])
    assert counts["n_records_off_target"] == 1
    assert counts["n_records_on_target_sequence"] == 1


def test_flank_coverage_counts_only_qualifying_records():
    counts = count([
        record_line("good", UP_WINDOW_START, "50M"),
        record_line("dup", UP_WINDOW_START, "50M", flag=0x400),
    ])
    upstream = counts["flanks"]["upstream"]
    assert upstream["window_fragments"] == 1
    assert upstream["covered_nt"] == 50
    assert upstream["length_nt"] == 186


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


def informative_background() -> list[str]:
    """Five bridged pairs over both windows plus one supported control junction."""
    lines = []
    for index in range(5):
        lines.append(record_line(f"bridge{index}", UP_WINDOW_START, "50M", flag=0x1 | 0x40))
        lines.append(record_line(f"bridge{index}", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80))
    lines.append(record_line("control", CONTROL_456.intron_start - 50,
                             f"50M{CONTROL_456.intron_len_nt}N50M"))
    return lines


def verdict_for(lines: list[str], criteria: ev.Criteria | None = None) -> dict:
    criteria = criteria or ev.Criteria()
    counts = count(lines, criteria)
    return {**ev.classify_library(counts, criteria), "counts": counts}


def test_two_crossing_fragments_support_the_junction():
    lines = informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR),
        record_line("cross2", UP_WINDOW_START, CROSSING_CIGAR),
    ]
    result = verdict_for(lines)
    assert result["verdict"] == "JUNCTION_SUPPORTED"
    assert result["informative_coverage"] is True
    assert result["counts"]["support_fragments"] == 2


def test_a_single_crossing_fragment_is_reported_below_the_declared_threshold():
    result = verdict_for(informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR)])
    assert result["verdict"] == "SUPPORT_BELOW_DECLARED_THRESHOLD"
    assert result["counts"]["support_fragments"] == 1


def test_zero_support_with_both_flanks_covered_is_a_result_not_a_gap():
    result = verdict_for(informative_background())
    assert result["verdict"] == "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    assert result["informative_coverage"] is True
    assert result["failed_requirements"] == ""
    assert result["counts"]["mate_bridge_fragments"] == 5


def test_insufficient_flank_coverage_is_inconclusive_and_names_the_side():
    result = verdict_for([
        record_line("bridge0", UP_WINDOW_START, "50M", flag=0x1 | 0x40),
        record_line("bridge0", DOWN_WINDOW_START, "50M", flag=0x1 | 0x80),
        record_line("control", CONTROL_456.intron_start - 50,
                    f"50M{CONTROL_456.intron_len_nt}N50M"),
    ])
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert result["informative_coverage"] is False
    assert "upstream_flank_window_fragments=1<5" in result["failed_requirements"]
    assert "downstream_flank_window_fragments=1<5" in result["failed_requirements"]


def test_zero_support_without_any_control_junction_is_not_informative():
    lines = [line for line in informative_background() if "control" not in line]
    result = verdict_for(lines)
    assert result["verdict"] == "INCONCLUSIVE_INSUFFICIENT_COVERAGE"
    assert "no_control_junction_support" in result["failed_requirements"]


def test_a_short_anchored_crossing_alone_does_not_support_the_junction():
    result = verdict_for(informative_background() + [
        record_line("short", TARGET.intron_start - 8, f"8M{TARGET.intron_len_nt}N50M")])
    assert result["verdict"] == "NO_SUPPORT_WITH_INFORMATIVE_COVERAGE"
    assert result["counts"]["short_anchor_fragments"] == 1


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------


def test_a_truncated_alignment_line_is_refused():
    with pytest.raises(ev.VerificationError, match="expected >= 11"):
        ev.parse_sam(sam_text(["r1\t0\tOZ319704.1\t100\t60"]))


def test_a_malformed_cigar_is_refused():
    with pytest.raises(ev.VerificationError, match="unparsable CIGAR"):
        observe("50M5130Njunk50M", UP_WINDOW_START)


def write_sam(path, lines, **kwargs):
    path.write_text(sam_text(lines, **kwargs), encoding="utf-8", newline="\n")
    return path


def test_a_sam_without_an_sq_line_for_the_reference_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], with_sq=False)
    with pytest.raises(ev.VerificationError, match="no @SQ line"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sam_without_a_pg_line_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], with_pg=False)
    with pytest.raises(ev.VerificationError, match="no @PG line"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sam_header_with_no_header_at_all_is_refused(tmp_path):
    path = tmp_path / "lib.sam"
    path.write_text(record_line("r1", UP_WINDOW_START, "50M") + "\n", encoding="utf-8")
    with pytest.raises(ev.VerificationError, match="no header"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_a_sequence_length_disagreeing_with_the_panel_is_refused(tmp_path):
    path = write_sam(tmp_path / "lib.sam", [], sequence_length=99)
    with pytest.raises(ev.VerificationError, match="was not made against the declared reference"):
        ev.read_library_sam(path, {"sequence_length_nt": SEQUENCE_LENGTH})


def test_the_aligner_is_read_from_the_pg_line(tmp_path):
    header, _ = ev.read_library_sam(write_sam(tmp_path / "lib.sam", []),
                                    {"sequence_length_nt": SEQUENCE_LENGTH})
    assert header["aligner_name"] == "hisat2"
    assert header["aligner_version"] == "2.2.1"


# --------------------------------------------------------------------------
# Panel validation and provenance
# --------------------------------------------------------------------------


def make_panel(root, libraries, reference=None):
    panel = {
        "reference": reference if reference is not None else {
            "assembly_accession": "GCA_975739785.1",
            "assembly_name": "ihDalMaid1.1",
            "sequence_name": "OZ319704.1",
            "sequence_length_nt": SEQUENCE_LENGTH,
        },
        "libraries": libraries,
    }
    path = root / "panel.json"
    path.write_text(json.dumps(panel, indent=2), encoding="utf-8", newline="\n")
    return path


def library_entry(root, library_id, lines, **overrides):
    sam_path = write_sam(root / f"{library_id}.sam", lines)
    entry = {
        "library_id": library_id,
        "sam": sam_path.name,
        "sha256": ev.sha256_file(sam_path),
        "origin_class": "open_link",
        "provenance": "synthetic fixture; no BioProject",
    }
    entry.update(overrides)
    return entry


def test_a_panel_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "panel.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ev.VerificationError, match="not valid JSON"):
        ev.load_panel(path, tmp_path)


def test_a_declared_sha256_that_does_not_match_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    entry["sha256"] = "0" * 64
    with pytest.raises(ev.VerificationError, match="sha256 mismatch"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_missing_sam_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    entry["sam"] = "absent.sam"
    with pytest.raises(ev.VerificationError, match="declared SAM is missing"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_confirmed_origin_without_documentary_evidence_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="confirmed_origin")
    with pytest.raises(ev.VerificationError, match="requires 'documentary_evidence'"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_confirmed_origin_with_documentary_evidence_is_accepted(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="confirmed_origin",
                          documentary_evidence="hypothetical document naming the libraries")
    panel = ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)
    assert panel["libraries"][0]["origin_class"] == "confirmed_origin"


def test_an_unknown_origin_class_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [], origin_class="probably_the_right_one")
    with pytest.raises(ev.VerificationError, match="is not one of"):
        ev.load_panel(make_panel(tmp_path, [entry]), tmp_path)


def test_a_duplicate_library_id_is_refused(tmp_path):
    first = library_entry(tmp_path, "lib1", [])
    second = dict(first)
    with pytest.raises(ev.VerificationError, match="duplicate library_id"):
        ev.load_panel(make_panel(tmp_path, [first, second]), tmp_path)


def test_a_panel_on_another_reference_is_refused(tmp_path):
    entry = library_entry(tmp_path, "lib1", [])
    reference = {"assembly_accession": "GCA_975739835.1", "sequence_name": "OZ319704.1",
                 "sequence_length_nt": SEQUENCE_LENGTH}
    with pytest.raises(ev.VerificationError, match="only defined on"):
        ev.load_panel(make_panel(tmp_path, [entry], reference), tmp_path)


def test_an_empty_library_list_is_refused(tmp_path):
    with pytest.raises(ev.VerificationError, match="non-empty 'libraries'"):
        ev.load_panel(make_panel(tmp_path, []), tmp_path)


# --------------------------------------------------------------------------
# End to end, including the refusal to overwrite an execution
# --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repository, so the manifest can record a real commit."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "base"], cwd=tmp_path, check=True)
    return tmp_path


OUT_SUBDIR = f"{ev.OUTPUT_ROOT}/dsrnase3_transcript_evidence_run1"


def test_a_full_run_writes_the_tables_and_a_success_manifest(repo):
    lines = informative_background() + [
        record_line("cross1", UP_WINDOW_START, CROSSING_CIGAR),
        record_line("cross2", UP_WINDOW_START, CROSSING_CIGAR),
    ]
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", lines)])
    assert ev.main(["--root", str(repo), "--panel", str(panel),
                    "--out-subdir", OUT_SUBDIR]) == 0

    out_dir = repo / OUT_SUBDIR
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["verdicts"] == {"SYNTH01": "JUNCTION_SUPPORTED"}
    assert len(manifest["git"]["commit"]) == 40
    assert manifest["git"]["clean"] is False  # the panel and the SAM are untracked
    assert manifest["indexing_convention"].startswith("1-based inclusive")
    assert manifest["target_junction"]["intron_start"] == TARGET.intron_start
    assert manifest["criteria"]["min_anchor_nt"] == 10
    assert manifest["panel"]["sha256"] == ev.sha256_file(panel)
    assert set(manifest["outputs"]) == {
        "per_library.tsv", "junction_observations.tsv", "mate_bridged_fragments.tsv"}
    for name, digest in manifest["outputs"].items():
        assert ev.sha256_file(out_dir / name) == digest
    assert manifest["validation"]["mate_bridged_fragments.tsv"]["rows"] == 5
    assert manifest["library_provenance_note"]["rule"].startswith("no library is classified")

    header, *rows = (out_dir / "per_library.tsv").read_text(encoding="utf-8").splitlines()
    row = dict(zip(header.split("\t"), rows[0].split("\t")))
    assert row["support_fragments"] == "2"
    assert row["mate_bridge_fragments"] == "5"
    assert row["control_cds_456_457_support_fragments"] == "1"
    assert row["aligner_name"] == "hisat2"
    assert row["origin_class"] == "open_link"
    assert row["verdict"] == "JUNCTION_SUPPORTED"

    observations = (out_dir / "junction_observations.tsv").read_text(encoding="utf-8").splitlines()
    assert sum(1 for line in observations[1:] if "\tsupport\t" in line) == 3  # 2 target + control


def test_a_second_run_on_the_same_directory_is_refused_with_the_first_intact(repo):
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", informative_background())])
    arguments = ["--root", str(repo), "--panel", str(panel), "--out-subdir", OUT_SUBDIR]
    assert ev.main(arguments) == 0
    before = ev.sha256_file(repo / OUT_SUBDIR / "manifest.json")
    with pytest.raises(ev.VerificationError, match="output directory is not empty"):
        ev.main(arguments)
    assert ev.sha256_file(repo / OUT_SUBDIR / "manifest.json") == before


def test_an_output_directory_outside_the_results_tree_is_refused(repo):
    panel = make_panel(repo, [library_entry(repo, "SYNTH01", [])])
    with pytest.raises(ev.VerificationError, match="must sit under"):
        ev.main(["--root", str(repo), "--panel", str(panel), "--out-subdir", "somewhere/else"])
    with pytest.raises(ev.VerificationError, match="must name a directory of its own"):
        ev.main(["--root", str(repo), "--panel", str(panel), "--out-subdir", ev.OUTPUT_ROOT])


def test_a_run_outside_a_git_checkout_is_refused_before_anything_is_written(tmp_path):
    panel = make_panel(tmp_path, [library_entry(tmp_path, "SYNTH01", [])])
    with pytest.raises(ev.VerificationError, match="cannot record the commit"):
        ev.run(tmp_path, panel, tmp_path / "out", ev.Criteria())
