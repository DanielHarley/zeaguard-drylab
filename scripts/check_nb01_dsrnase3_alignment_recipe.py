#!/usr/bin/env python3
"""Run the declared ALIGNMENT_RECIPE end to end on synthetic FASTQs, then the NB01 command.

Why this exists
---------------
`zeaguard.nb01_dsrnase3_transcript_evidence` declares, but does not execute, the
recipe that turns raw reads into the SAM it counts. Two of its steps are easy to
get wrong in a way that only shows up on real data: `samtools fixmate` needs the
records grouped by read name, and `samtools view <bam> <region>` needs an index.
This script executes the recipe's command templates **verbatim**, substituting
only paths and thread counts, so the declared recipe is the thing that was
tested.

It also measures what the configuration can actually see. Crossing reads are
generated at a range of anchor lengths, including the length the counter
declares as its minimum, and the script reports which of them hisat2 reports as
a spliced alignment at the exact declared coordinates under `--dta`. That
measurement is what `min_anchor_nt` has to respect: an anchor the aligner
soft-clips never reaches the counter, however the counter is configured.

Everything is synthetic. The reference is a sequence named `OZ319704.1` of the
declared length whose bases are `N` except for a window around the locus, so the
declared coordinates are real coordinates and nothing else in the genome can
attract a read. No biological sequence and no real library is involved.

    python scripts/check_nb01_dsrnase3_alignment_recipe.py --root . \
        --out-subdir results/bioinformatics/nb01/dsrnase3_transcript_evidence/recipe_v1
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeaguard import nb01_dsrnase3_transcript_evidence as ev  # noqa: E402

LIBRARY_ID = "SYNTH_RECIPE"
READ_LENGTH = 100
WINDOW = (121_999_001, 122_020_000)   # the only non-N stretch of the fixture reference
SEED = 20261118

TARGET = ev.TARGET_JUNCTION
CONTROL_456, CONTROL_870 = ev.CONTROL_JUNCTIONS

# The chain's aligned blocks on OZ319704.1, from the 2026-11-15 run record.
BLOCKS = {
    1: (122_005_058, 122_005_157),
    2: (122_005_565, 122_005_920),
    3: (122_007_163, 122_007_348),     # upstream flank of the target junction
    4: (122_012_479, 122_012_706),     # downstream flank of the target junction
    5: (122_014_117, 122_014_482),
}

# Anchor lengths probed on each side of the target junction. The sweep is
# contiguous from 4 to 20 so no length below the counter's declared
# min_anchor_nt is left unsampled, then thins out above it.
ANCHOR_LENGTHS = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 30, 50)

COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def revcomp(sequence: str) -> str:
    return sequence.translate(COMPLEMENT)[::-1]


class Reference:
    """The fixture reference, held as the non-N window plus its offset."""

    def __init__(self) -> None:
        rng = random.Random(SEED)
        self.start, self.end = WINDOW
        self.window = [rng.choice("ACGT") for _ in range(self.end - self.start + 1)]
        # Canonical GT..AG at every junction the counter declares, so hisat2 can
        # find them de novo without an annotation.
        for spec in (TARGET, CONTROL_456, CONTROL_870):
            self._put(spec.intron_start, "GT")
            self._put(spec.intron_end - 1, "AG")

    def _put(self, position: int, bases: str) -> None:
        offset = position - self.start
        for index, base in enumerate(bases):
            self.window[offset + index] = base

    def slice(self, start: int, end: int) -> str:
        """1-based inclusive genomic slice; must sit inside the non-N window."""
        if start < self.start or end > self.end:
            raise ValueError(f"{start}-{end} falls outside the fixture window")
        return "".join(self.window[start - self.start:end - self.start + 1])

    def write_fasta(self, path: Path) -> None:
        name = ev.REFERENCE["sequence_name"]
        total = ev.REFERENCE["sequence_length_nt"]
        line = 60
        with path.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(f">{name} synthetic fixture, {total} nt\n")
            position = 1
            chunk: list[str] = []
            while position <= total:
                end = min(position + line - 1, total)
                if end < self.start or position > self.end:
                    chunk.append("N" * (end - position + 1))
                else:
                    chunk.append("".join(
                        self.window[index - self.start] if self.start <= index <= self.end else "N"
                        for index in range(position, end + 1)))
                position = end + 1
                if len(chunk) >= 20_000:
                    handle.write("\n".join(chunk) + "\n")
                    chunk = []
            if chunk:
                handle.write("\n".join(chunk) + "\n")


def crossing_read(reference: Reference, spec, upstream_anchor: int) -> str:
    """A read spanning `spec` with `upstream_anchor` bases on the upstream side."""
    downstream = READ_LENGTH - upstream_anchor
    return (reference.slice(spec.intron_start - upstream_anchor, spec.intron_start - 1)
            + reference.slice(spec.intron_end + 1, spec.intron_end + downstream))


def build_reads(reference: Reference) -> tuple[list[tuple[str, str, str]], dict]:
    """The read pairs, and the design record that says what each pair is for."""
    pairs: list[tuple[str, str, str]] = []
    design: dict = {"anchor_probe": {}, "other": {}}

    # Mates for the crossing reads, taken from the downstream flank so the
    # fragment spans the junction the way a real pair would. The two families
    # get different mates so that the symmetric 50/50 crossing read, which is
    # the same sequence in both, still forms two distinct fragments rather than
    # a duplicate pair.
    mate_for_up = revcomp(reference.slice(BLOCKS[4][1] - 126, BLOCKS[4][1] - 27))
    mate_for_down = revcomp(reference.slice(BLOCKS[4][1] - 116, BLOCKS[4][1] - 17))
    mate_upstream = revcomp(reference.slice(BLOCKS[3][0] + 20, BLOCKS[3][0] + 119))

    for anchor in ANCHOR_LENGTHS:
        name = f"cross_up{anchor:02d}"
        pairs.append((name, crossing_read(reference, TARGET, anchor), mate_for_up))
        design["anchor_probe"][name] = {"side": "upstream", "anchor_nt": anchor,
                                        "other_side_nt": READ_LENGTH - anchor}
        name = f"cross_down{anchor:02d}"
        pairs.append((name, crossing_read(reference, TARGET, READ_LENGTH - anchor),
                      mate_for_down))
        design["anchor_probe"][name] = {"side": "downstream", "anchor_nt": anchor,
                                        "other_side_nt": READ_LENGTH - anchor}

    # Six pairs bridging the two flanks, each mate covering its side's anchor
    # zone, so the library reaches the informative-coverage floor without any
    # crossing read. Their lengths are staggered so the six are distinct
    # fragments: identical outer coordinates would make markdup collapse five of
    # them and the floor would be met by accident.
    for index in range(6):
        length = READ_LENGTH - index
        pairs.append((
            f"bridge{index}",
            reference.slice(TARGET.intron_start - length, TARGET.intron_start - 1),
            revcomp(reference.slice(TARGET.intron_end + 1, TARGET.intron_end + length)),
        ))
    design["other"]["bridge0-5"] = ("six pairs of staggered length covering both anchor "
                                    "zones, no crossing read")

    # Two concordant pairs identical to each other inside the upstream flank:
    # markdup has to flag one of them, which is what the duplicate column
    # counts. They are deliberately not bridges.
    duplicate_1 = reference.slice(BLOCKS[3][0], BLOCKS[3][0] + READ_LENGTH - 1)
    duplicate_2 = revcomp(reference.slice(BLOCKS[3][1] - READ_LENGTH + 1, BLOCKS[3][1]))
    for name in ("dupA", "dupB"):
        pairs.append((name, duplicate_1, duplicate_2))
    design["other"]["dupA/dupB"] = ("identical concordant pairs inside the upstream "
                                    "flank, so markdup flags one as 0x400")

    # Two identical crossing pairs, so markdup flags one of them and the
    # duplicate column is exercised at the junction itself, not only in a flank.
    crossing = crossing_read(reference, TARGET, 50)
    mate_for_dup = revcomp(reference.slice(BLOCKS[4][1] - 106, BLOCKS[4][1] - 7))
    for name in ("cross_dupA", "cross_dupB"):
        pairs.append((name, crossing, mate_for_dup))
    design["other"]["cross_dupA/cross_dupB"] = (
        "identical 50/50 crossing pairs, so markdup flags one crossing read as 0x400")

    # The two annotated control junctions, at a 50 nt anchor.
    pairs.append(("ctl456", crossing_read(reference, CONTROL_456, 50), mate_upstream))
    pairs.append(("ctl870", crossing_read(reference, CONTROL_870, 50), mate_for_up))
    design["other"]["ctl456/ctl870"] = "the two annotated junctions, 50 nt anchors"
    return pairs, design


def write_fastqs(pairs, directory: Path, library: str) -> tuple[Path, Path]:
    paths = []
    for mate in (1, 2):
        path = directory / f"{library}_{mate}.fastq.gz"
        with gzip.open(path, "wt", encoding="ascii", newline="\n") as handle:
            for name, read_1, read_2 in pairs:
                sequence = read_1 if mate == 1 else read_2
                handle.write(f"@{name}/{mate}\n{sequence}\n+\n{'I' * len(sequence)}\n")
        paths.append(path)
    return paths[0], paths[1]


def tool_version(command: list[str], pattern: str) -> str:
    done = subprocess.run(command, capture_output=True, text=True)
    for line in (done.stdout + done.stderr).splitlines():
        if pattern in line:
            return line.strip()
    return "unknown"


def observed_junctions(sam_text: str, criteria: ev.Criteria) -> dict:
    """Per read name, what the aligner reported for the target junction.

    The anchors reported here are the counter's own measure: reference bases of
    each anchor zone covered by M, = or X in that read.
    """
    _, records = ev.parse_sam(sam_text)
    upstream_zone = ev.junction_anchor_zone(TARGET, "upstream", criteria)
    downstream_zone = ev.junction_anchor_zone(TARGET, "downstream", criteria)
    observed: dict[str, dict] = {}
    for record in records:
        if record.is_unmapped or record.rname != ev.REFERENCE["sequence_name"]:
            continue
        walk = ev.walk_reference(ev.parse_cigar(record.cigar), record.pos)
        exact = any(junction["intron_ref_start"] == TARGET.intron_start
                    and junction["intron_ref_end"] == TARGET.intron_end
                    for junction in walk["junctions"])
        entry = observed.setdefault(record.qname, {
            "cigars": [], "spliced_at_target": False, "anchor_upstream_nt": None,
            "anchor_downstream_nt": None, "mapq": record.mapq})
        entry["cigars"].append(record.cigar)
        if exact:
            entry["spliced_at_target"] = True
            entry["anchor_upstream_nt"] = ev._overlap_nt(walk["aligned"], *upstream_zone)
            entry["anchor_downstream_nt"] = ev._overlap_nt(walk["aligned"], *downstream_zone)
    return observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--out-subdir", required=True,
                        help=f"destination for this check, under {ev.OUTPUT_ROOT}/")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--keep-work", default=None,
                        help="keep the alignment working directory here instead of /tmp")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out_dir = root / args.out_subdir
    if ev.OUTPUT_ROOT not in Path(args.out_subdir).as_posix():
        raise SystemExit(f"--out-subdir must sit under {ev.OUTPUT_ROOT}/")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"destination is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    versions = {
        "hisat2": tool_version(["hisat2", "--version"], "version"),
        "hisat2-build": tool_version(["hisat2-build", "--version"], "version"),
        "samtools": tool_version(["samtools", "--version"], "samtools"),
        "python": sys.version.split()[0],
    }
    print(json.dumps(versions, indent=2), file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="nb01-dsrnase3-recipe-") as temporary:
        work = Path(args.keep_work).resolve() if args.keep_work else Path(temporary)
        work.mkdir(parents=True, exist_ok=True)
        print(f"[work] {work}", file=sys.stderr)

        reference = Reference()
        genome = work / "genome.fna"
        reference.write_fasta(genome)
        print(f"[genome] {genome} {genome.stat().st_size} bytes", file=sys.stderr)

        pairs, design = build_reads(reference)
        write_fastqs(pairs, work, LIBRARY_ID)
        print(f"[fastq] {len(pairs)} pairs", file=sys.stderr)

        executed = []
        for template in ev.ALIGNMENT_RECIPE["commands"]:
            command = ev.fill_recipe_command(template, genome, "ihDalMaid1.1",
                                             LIBRARY_ID, args.threads)
            print(f"[recipe] {command}", file=sys.stderr)
            done = subprocess.run(command, shell=True, cwd=work,
                                  capture_output=True, text=True)
            executed.append({"template": template, "command": command,
                             "returncode": done.returncode,
                             "stderr_tail": done.stderr.strip().splitlines()[-4:]})
            if done.returncode != 0:
                (out_dir / "recipe_failure.json").write_text(
                    json.dumps(executed, indent=2) + "\n", encoding="utf-8", newline="\n")
                raise SystemExit(f"recipe step failed: {command}\n{done.stderr}")

        sam_name = f"{LIBRARY_ID}.{ev.REFERENCE['sequence_name']}.sam"
        extracted = out_dir / sam_name
        shutil.copyfile(work / sam_name, extracted)
        summary = work / f"{LIBRARY_ID}.hisat2.summary"
        if summary.is_file():
            shutil.copyfile(summary, out_dir / summary.name)

    criteria = ev.Criteria()
    sam_text = extracted.read_text(encoding="utf-8")
    observed = observed_junctions(sam_text, criteria)

    recovery = []
    for name, probe in sorted(design["anchor_probe"].items()):
        entry = observed.get(name, {})
        anchor_key = ("anchor_upstream_nt" if probe["side"] == "upstream"
                      else "anchor_downstream_nt")
        recovery.append({
            "read": name, "designed_side": probe["side"],
            "designed_anchor_nt": probe["anchor_nt"],
            "aligned": bool(entry),
            "spliced_at_target": entry.get("spliced_at_target", False),
            "observed_anchor_nt": entry.get(anchor_key),
            "cigars": ";".join(entry.get("cigars", [])),
            "mapq": entry.get("mapq"),
        })
    ev.write_tsv(out_dir / "anchor_recovery.tsv",
                 ["read", "designed_side", "designed_anchor_nt", "aligned",
                  "spliced_at_target", "observed_anchor_nt", "mapq", "cigars"],
                 recovery)

    recovered = sorted({row["designed_anchor_nt"] for row in recovery
                        if row["spliced_at_target"]})
    missed = sorted({row["designed_anchor_nt"] for row in recovery
                     if not row["spliced_at_target"]})
    print(f"[anchors] spliced at the declared coordinates: {recovered}", file=sys.stderr)
    print(f"[anchors] not spliced there: {missed}", file=sys.stderr)

    panel = {
        "reference": {key: ev.REFERENCE[key] for key in
                      ("assembly_accession", "assembly_name", "sequence_name",
                       "sequence_length_nt")},
        "libraries": [{
            "library_id": LIBRARY_ID,
            "sam": extracted.relative_to(root).as_posix(),
            "sha256": ev.sha256_file(extracted),
            "origin_class": "open_link",
            "provenance": "synthetic FASTQs aligned by the declared recipe in this run; "
                          "no biological origin and no BioProject",
        }],
    }
    panel_path = out_dir / "panel.json"
    panel_path.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8", newline="\n")

    counted = out_dir / "counted"
    with ev.reserve_output_dir(counted) as reservation:
        result = ev.run(root, panel_path, reservation.out_dir, criteria)

    report = {
        "versions": versions,
        "recipe_commands_executed": executed,
        "read_design": design,
        "anchor_lengths_probed": list(ANCHOR_LENGTHS),
        "anchor_lengths_spliced_at_declared_coordinates": recovered,
        "anchor_lengths_not_spliced": missed,
        "min_anchor_nt_declared": criteria.min_anchor_nt,
        "calibration_statement": (
            "These are the lengths TESTED, on a synthetic reference with random flanking "
            "sequence, at one read length and one set of alignment penalties. "
            "min_anchor_nt is a conservative operational cut equal to the shortest tested "
            "length that recovered the junction on both sides; it is not a measured "
            "detection threshold, and the sensitivity of this pipeline on real libraries "
            "remains unknown."),
        "extracted_sam": {"path": extracted.relative_to(root).as_posix(),
                          "sha256": ev.sha256_file(extracted)},
        "panel": {"path": panel_path.relative_to(root).as_posix(),
                  "sha256": ev.sha256_file(panel_path)},
        "nb01_verdicts": result["verdicts"],
        "nb01_manifest_sha256": ev.sha256_file(counted / "manifest.json"),
        "outputs": {"anchor_recovery.tsv": ev.sha256_file(out_dir / "anchor_recovery.tsv")},
    }
    (out_dir / "recipe_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"[write] {out_dir / 'recipe_report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
