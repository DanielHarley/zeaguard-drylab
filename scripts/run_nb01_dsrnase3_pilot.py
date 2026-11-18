#!/usr/bin/env python3
"""Run the declared ALIGNMENT_RECIPE on real RNA-seq libraries, one library at a time.

This executes the same command templates the synthetic check validates, with
real FASTQ pairs, and then counts each library on its own. Nothing is pooled:
each library gets its own alignment, its own declared panel of one, its own
output directory and its own verdict, because a count summed across libraries
would hide which library carries the evidence.

Provenance recorded for every library: the run accession, the sha256 and spot
and base counts of both FASTQ files, the assembly and its sha256, the index and
how it was built, every command as executed, the tool versions, and the sha256
of the extracted SAM the counter consumed.

Two steps, so the index can be built once and reused across libraries:

    python scripts/run_nb01_dsrnase3_pilot.py --prepare-index-only \
        --genome <genomic.fna.gz> --index-dir <dir>

    python scripts/run_nb01_dsrnase3_pilot.py --root . \
        --index-dir <dir> --reads-dir <dir> \
        --runs SRR11822340 SRR11822336 SRR11822345 SRR11822341 \
        --out-subdir results/bioinformatics/nb01/dsrnase3_transcript_evidence/pilot_v1
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeaguard import nb01_dsrnase3_transcript_evidence as ev  # noqa: E402

INDEX_NAME = "ihDalMaid1.1"
INDEX_RECORD = "index_build.json"

# The declared sha256 of the primary assembly, as the NB01 locus mapping and the
# splice-aware check declare it. Checked before the index is built.
GENOME_SHA256 = "aef4d8ec0891bece052bc58afa5b0da3e2a2bf047f9283032bbf253459509184"
GENOME_SHA256_DECOMPRESSED = "54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04"


def versions() -> dict:
    def first(command: list[str], pattern: str) -> str:
        done = subprocess.run(command, capture_output=True, text=True)
        for line in (done.stdout + done.stderr).splitlines():
            if pattern in line:
                return line.strip()
        return "unknown"
    return {
        "hisat2": first(["hisat2", "--version"], "version"),
        "hisat2-build": first(["hisat2-build", "--version"], "version"),
        "samtools": first(["samtools", "--version"], "samtools"),
        "python": sys.version.split()[0],
    }


def run_command(command: str, cwd: Path) -> dict:
    print(f"[run] {command}", file=sys.stderr)
    done = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    record = {"command": command, "returncode": done.returncode,
              "stderr_tail": done.stderr.strip().splitlines()[-6:]}
    if done.returncode != 0:
        raise SystemExit(f"step failed ({done.returncode}): {command}\n{done.stderr}")
    return record


def decompress(source: Path, target: Path) -> str:
    if not target.is_file():
        with gzip.open(source, "rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1 << 22)
    return ev.sha256_file(target)


def prepare_index(genome_gz: Path, index_dir: Path, threads: int) -> dict:
    index_dir.mkdir(parents=True, exist_ok=True)
    record_path = index_dir / INDEX_RECORD
    if record_path.is_file():
        print(f"[index] reusing {record_path}", file=sys.stderr)
        return json.loads(record_path.read_text(encoding="utf-8"))

    observed = ev.sha256_file(genome_gz)
    if observed != GENOME_SHA256:
        raise SystemExit(f"assembly sha256 mismatch: declared {GENOME_SHA256}, "
                         f"observed {observed}")
    genome = index_dir / "GCA_975739785.1_ihDalMaid1.1_genomic.fna"
    plain = decompress(genome_gz, genome)
    if plain != GENOME_SHA256_DECOMPRESSED:
        raise SystemExit(f"decompressed assembly sha256 mismatch: declared "
                         f"{GENOME_SHA256_DECOMPRESSED}, observed {plain}")
    print(f"[index] assembly verified: {observed} / {plain}", file=sys.stderr)

    template = ev.ALIGNMENT_RECIPE["commands"][0]
    command = ev.fill_recipe_command(template, genome, INDEX_NAME, "", threads)
    executed = run_command(command, index_dir)
    record = {
        "assembly": {
            "accession": ev.REFERENCE["assembly_accession"],
            "file": genome_gz.name,
            "sha256_gz": observed,
            "sha256_decompressed": plain,
        },
        "index_name": INDEX_NAME,
        "build": executed,
        "versions": versions(),
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": ev.sha256_file(path)}
                  for path in sorted(index_dir.glob(f"{INDEX_NAME}.*.ht2"))},
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"[index] built, {len(record['files'])} files", file=sys.stderr)
    return record


def fastq_facts(path: Path) -> dict:
    spots = bases = 0
    with gzip.open(path, "rt", encoding="ascii") as handle:
        for number, line in enumerate(handle):
            if number % 4 == 1:
                spots += 1
                bases += len(line) - 1
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": ev.sha256_file(path),
            "spots": spots, "bases": bases}


def process_library(run: str, reads_dir: Path, index_dir: Path, work: Path,
                    out_dir: Path, root: Path, threads: int, criteria: ev.Criteria) -> dict:
    print(f"=== {run} ===", file=sys.stderr)
    library_work = work / run
    library_work.mkdir(parents=True, exist_ok=True)
    for mate in (1, 2):
        source = reads_dir / f"{run}_{mate}.fastq.gz"
        if not source.is_file():
            raise SystemExit(f"{run}: missing {source}")
        link = library_work / f"{run}_{mate}.fastq.gz"
        if not link.exists():
            link.symlink_to(source)

    reads = [fastq_facts(reads_dir / f"{run}_{mate}.fastq.gz") for mate in (1, 2)]
    print(f"[{run}] {reads[0]['spots']} spots per mate", file=sys.stderr)

    genome = index_dir / "GCA_975739785.1_ihDalMaid1.1_genomic.fna"
    executed = []
    for template in ev.ALIGNMENT_RECIPE["commands"][1:]:
        command = ev.fill_recipe_command(template, genome, str(index_dir / INDEX_NAME),
                                         run, threads)
        executed.append(run_command(command, library_work))

    library_out = out_dir / run
    library_out.mkdir(parents=True, exist_ok=True)
    extracted = library_out / f"{run}.{ev.REFERENCE['sequence_name']}.sam"
    shutil.move(str(library_work / f"{run}.{ev.REFERENCE['sequence_name']}.sam"),
                str(extracted))
    summary = library_work / f"{run}.hisat2.summary"
    if summary.is_file():
        shutil.copyfile(summary, library_out / summary.name)

    panel = {
        "reference": {key: ev.REFERENCE[key] for key in
                      ("assembly_accession", "assembly_name", "sequence_name",
                       "sequence_length_nt")},
        "libraries": [{
            "library_id": run,
            "sam": extracted.relative_to(root).as_posix(),
            "sha256": ev.sha256_file(extracted),
            "origin_class": "comparative",
            "provenance": f"SRA run {run} of BioProject PRJNA631706, catalogued in "
                          f"data/reference/nb01_dsrnase3_comparative_library_candidates.json; "
                          f"no document ties it to the assembly of "
                          f"TRINITY_DN5008_c0_g1_i24",
        }],
    }
    panel_path = library_out / "panel.json"
    panel_path.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8", newline="\n")

    counted = library_out / "counted"
    with ev.reserve_output_dir(counted) as reservation:
        manifest = ev.run(root, panel_path, reservation.out_dir, criteria)

    # The volume stays out of the repository: only the extracted region SAM, the
    # panel and the counted tables remain, and the BAMs are removed here.
    for leftover in library_work.glob("*.bam*"):
        leftover.unlink()
    for leftover in library_work.glob("*.sam"):
        leftover.unlink()

    return {
        "run_accession": run,
        "reads": reads,
        "commands": executed,
        "extracted_sam": {"path": extracted.relative_to(root).as_posix(),
                          "sha256": ev.sha256_file(extracted),
                          "bytes": extracted.stat().st_size},
        "panel": {"path": panel_path.relative_to(root).as_posix(),
                  "sha256": ev.sha256_file(panel_path)},
        "counted_manifest_sha256": ev.sha256_file(counted / "manifest.json"),
        "verdict": manifest["verdicts"][run],
        "hisat2_summary": (library_out / summary.name).read_text(encoding="utf-8")
                          if (library_out / summary.name).is_file() else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--genome", default=None, help="the assembly .fna.gz, for the index")
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--reads-dir", default=None)
    parser.add_argument("--runs", nargs="*", default=[])
    parser.add_argument("--out-subdir", default=None)
    parser.add_argument("--work-dir", default=None,
                        help="where the alignment intermediates go; keep it off any "
                             "filesystem that is backed up or committed")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--prepare-index-only", action="store_true")
    args = parser.parse_args(argv)

    index_dir = Path(args.index_dir).resolve()
    if args.prepare_index_only:
        if not args.genome:
            raise SystemExit("--prepare-index-only needs --genome")
        prepare_index(Path(args.genome).resolve(), index_dir, args.threads)
        return 0

    for required in ("reads_dir", "out_subdir", "work_dir"):
        if not getattr(args, required):
            raise SystemExit(f"--{required.replace('_', '-')} is required")
    root = Path(args.root).resolve()
    if ev.OUTPUT_ROOT not in Path(args.out_subdir).as_posix():
        raise SystemExit(f"--out-subdir must sit under {ev.OUTPUT_ROOT}/")
    out_dir = root / args.out_subdir
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"destination is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    index_record_path = index_dir / INDEX_RECORD
    if not index_record_path.is_file():
        raise SystemExit(f"no {INDEX_RECORD} in {index_dir}: build the index first with "
                         f"--prepare-index-only, so its provenance is recorded")
    index_record = json.loads(index_record_path.read_text(encoding="utf-8"))

    criteria = ev.Criteria()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    libraries = []
    for run in args.runs:
        libraries.append(process_library(run, Path(args.reads_dir).resolve(), index_dir,
                                         work, out_dir, root, args.threads, criteria))
        print(f"[{run}] verdict={libraries[-1]['verdict']}", file=sys.stderr)

    report = {
        "question": "does RNA-seq from PRJNA631706 support the 642/643 junction of the "
                    "published Dmai-dsRNase-3 CDS",
        "processed_one_library_at_a_time": True,
        "never_pooled": "each library has its own alignment, panel, output directory and "
                        "verdict; no count in this report is summed across libraries",
        "reference": ev.REFERENCE,
        "criteria": ev.asdict(criteria),
        "versions": versions(),
        "index": index_record,
        "git": ev._git_state(root),
        "libraries": libraries,
        "verdicts": {library["run_accession"]: library["verdict"] for library in libraries},
    }
    report_path = out_dir / "pilot_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"[write] {report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
