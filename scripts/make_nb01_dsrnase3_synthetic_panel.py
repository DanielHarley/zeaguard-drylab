#!/usr/bin/env python3
"""Materialise the synthetic SAM libraries and panel the dsRNase-3 pre-run is validated on.

This exists so the recorded synthetic validation of
`zeaguard.nb01_dsrnase3_transcript_evidence` is reproducible from a clean
checkout: it writes three fixture libraries, one per verdict, at the declared
coordinates of the target junction, and the panel that declares them with their
`sha256`.

It carries no biological content. Every read is constructed from the junction
coordinates the module declares, and no library here corresponds to any real
sequencing run.

    python scripts/make_nb01_dsrnase3_synthetic_panel.py --root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeaguard import nb01_dsrnase3_transcript_evidence as ev  # noqa: E402

SUBDIR = "results/bioinformatics/nb01/dsrnase3_transcript_evidence/synthetic_inputs"

# The real length of OZ319704.1, which the module declares and enforces: the SAM
# headers and the panel must both carry it.
SEQUENCE_LENGTH = ev.REFERENCE["sequence_length_nt"]

TARGET = ev.TARGET_JUNCTION
CONTROL_456, CONTROL_870 = ev.CONTROL_JUNCTIONS
UP_WINDOW = ev.FLANKS["upstream"]["ref_end"] - 49
DOWN_WINDOW = ev.FLANKS["downstream"]["ref_start"]
CROSSING = f"50M{TARGET.intron_len_nt}N50M"


def line(qname: str, pos: int, cigar: str, flag: int = 0, mapq: int = 60,
         rname: str = "OZ319704.1", tags: tuple[str, ...] = ()) -> str:
    return "\t".join([qname, str(flag), rname, str(pos), str(mapq), cigar,
                      "=", "0", "0", "*", "*", *tags])


def sam_text(lines: list[str]) -> str:
    header = [
        "@HD\tVN:1.6\tSO:coordinate",
        f"@SQ\tSN:OZ319704.1\tLN:{SEQUENCE_LENGTH}",
        "@PG\tID:hisat2\tPN:hisat2\tVN:2.2.1\t"
        "CL:hisat2 -p 8 --dta --max-intronlen 50000 -x ihDalMaid1.1 -1 R1 -2 R2",
    ]
    return "\n".join(header + lines) + "\n"


def bridged_pairs(count: int) -> list[str]:
    """Pairs whose mates sit in the two flanks, with no read crossing the junction."""
    lines = []
    for index in range(count):
        lines.append(line(f"bridge{index}", UP_WINDOW, "50M", flag=0x1 | 0x40))
        lines.append(line(f"bridge{index}", DOWN_WINDOW, "50M", flag=0x1 | 0x80))
    return lines


CONTROL_456_READ = line("ctl456", CONTROL_456.intron_start - 50,
                        f"50M{CONTROL_456.intron_len_nt}N50M")
CONTROL_870_READ = line("ctl870", CONTROL_870.intron_start - 50,
                        f"50M{CONTROL_870.intron_len_nt}N50M")

LIBRARIES: dict[str, list[str]] = {
    # Two genuine crossings, and one read for every rejection the criteria make.
    "SYNTH_SUPPORTED": bridged_pairs(5) + [
        CONTROL_456_READ, CONTROL_870_READ,
        line("cross_pair", UP_WINDOW, CROSSING, flag=0x1 | 0x40),
        line("cross_pair", UP_WINDOW, CROSSING, flag=0x1 | 0x80),
        line("cross_del", UP_WINDOW - 2, f"30M2D20M{TARGET.intron_len_nt}N50M"),
        line("short_anchor", TARGET.intron_start - 8, f"8M{TARGET.intron_len_nt}N50M"),
        line("shift_one_base", UP_WINDOW + 1, CROSSING),
        line("shift_acceptor", UP_WINDOW, f"50M{TARGET.intron_len_nt + 1}N50M"),
        line("duplicate", UP_WINDOW, CROSSING, flag=0x400),
        line("ambiguous_mapq", UP_WINDOW, CROSSING, mapq=1),
        line("ambiguous_nh", UP_WINDOW, CROSSING, tags=("NH:i:4",)),
        line("secondary", UP_WINDOW, CROSSING, flag=0x100),
        line("off_target", 1_000, "50M", rname="OZ319705.1"),
    ],
    # Both flanks covered, both annotated junctions spliced, nothing crossing.
    "SYNTH_ZERO_INFORMATIVE": bridged_pairs(5) + [CONTROL_456_READ, CONTROL_870_READ],
    # One pair only: too little coverage for an absence to mean anything.
    "SYNTH_INCONCLUSIVE": bridged_pairs(1) + [CONTROL_456_READ],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out_dir = root / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for library_id, lines in LIBRARIES.items():
        path = out_dir / f"{library_id}.sam"
        path.write_text(sam_text(lines), encoding="utf-8", newline="\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({
            "library_id": library_id,
            "sam": path.relative_to(root).as_posix(),
            "sha256": digest,
            "origin_class": "open_link",
            "provenance": "synthetic fixture, no biological origin and no BioProject",
        })
        print(f"{library_id}: {len(lines)} records, sha256 {digest}")

    panel = {
        "reference": {
            "assembly_accession": "GCA_975739785.1",
            "assembly_name": "ihDalMaid1.1",
            "sequence_name": "OZ319704.1",
            "sequence_length_nt": SEQUENCE_LENGTH,
        },
        "libraries": entries,
    }
    panel_path = out_dir / "panel.json"
    panel_path.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"panel: {panel_path.relative_to(root).as_posix()} "
          f"sha256 {hashlib.sha256(panel_path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
