#!/usr/bin/env python3
"""Recount, straight from a pilot SAM, the spliced reads at the donor 642/643 shares.

The `donor_only` rows of `junction_observations.tsv` are not a fragment count:
they are one row per alignment record, and for a non-exact boundary match the
category is assigned before the quality check, so records that failed it are
included. `donor_only_fragments` in `per_library.tsv` deduplicates by QNAME but
still includes those records. Neither figure is the number of fragments that
could have carried the junction.

This prints three counts per library, each with its denominator stated, so the
number used in a record says which one it is:

  1. alignment_records  - lines whose CIGAR carries an N junction starting at the
                          shared donor and ending anywhere other than the
                          declared acceptor. No filter applied.
  2. fragments_after_filters
                        - distinct QNAMEs among those records after the
                          counter's own filters: flagged duplicate, secondary,
                          supplementary, NH > 1, MAPQ < min_mapq.
  3. fragments_anchored - of those, the distinct QNAMEs where one read covers all
                          min_anchor_nt reference bases of BOTH anchor zones of
                          the junction it actually takes, by M, = or X. This is
                          the eligible count, under the same rule the counter
                          applies to 642/643.

It also reports which acceptors those anchored fragments reach, so the claim that
they follow one intron is checked rather than asserted.

    python scripts/recount_nb01_dsrnase3_donor.py <pilot_v1 dir> [<run> ...]
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeaguard import nb01_dsrnase3_transcript_evidence as ev  # noqa: E402

SHARED_DONOR = ev.TARGET_JUNCTION.intron_start          # 122,007,349
DECLARED_ACCEPTOR = ev.TARGET_JUNCTION.intron_end       # 122,012,478


def recount(sam_path: Path, criteria: ev.Criteria) -> dict:
    records = 0
    filtered: set[str] = set()
    anchored: set[str] = set()
    acceptors: collections.Counter = collections.Counter()

    with sam_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("@"):
                continue
            fields = line.rstrip("\n").split("\t")
            if fields[2] != ev.REFERENCE["sequence_name"] or "N" not in fields[5]:
                continue
            walk = ev.walk_reference(ev.parse_cigar(fields[5]), int(fields[3]))
            alternative = [junction for junction in walk["junctions"]
                           if junction["intron_ref_start"] == SHARED_DONOR
                           and junction["intron_ref_end"] != DECLARED_ACCEPTOR]
            if not alternative:
                continue
            records += 1

            # The counter's own filters, applied through the counter's own code.
            tags = {part.split(":", 1)[0]: part.split(":", 2)[-1]
                    for part in fields[11:] if ":" in part}
            record = ev._splice.SamRecord(qname=fields[0], flag=int(fields[1]),
                                          rname=fields[2], pos=int(fields[3]),
                                          mapq=int(fields[4]), cigar=fields[5], tags=tags)
            if ev._disqualification(record, criteria) is not None:
                continue
            filtered.add(fields[0])

            for junction in alternative:
                spec = ev.JunctionSpec(name="alternative", intron_start=SHARED_DONOR,
                                       intron_end=junction["intron_ref_end"],
                                       cds_upstream=0, cds_downstream=0,
                                       annotated_intron=False)
                zones = [ev.junction_anchor_zone(spec, side, criteria)
                         for side in ("upstream", "downstream")]
                if all(ev._overlap_nt(walk["aligned"], *zone) == criteria.min_anchor_nt
                       for zone in zones):
                    anchored.add(fields[0])
                    acceptors[junction["intron_ref_end"]] += 1
    return {"alignment_records": records,
            "fragments_after_filters": len(filtered),
            "fragments_anchored": len(anchored),
            "acceptors_of_anchored": dict(acceptors)}


def main(argv: list[str]) -> int:
    base = Path(argv[1]).resolve()
    runs = argv[2:] or ["SRR11822340", "SRR11822336", "SRR11822345", "SRR11822341"]
    criteria = ev.Criteria()
    print(f"shared donor {SHARED_DONOR}, declared acceptor {DECLARED_ACCEPTOR}, "
          f"min_anchor_nt {criteria.min_anchor_nt}, min_mapq {criteria.min_mapq}")
    print(f"{'run':14s} {'records':>8s} {'fragments':>10s} {'anchored':>9s}  acceptors")
    totals = collections.Counter()
    for run in runs:
        sam = base / run / f"{run}.{ev.REFERENCE['sequence_name']}.sam"
        counts = recount(sam, criteria)
        totals.update({key: value for key, value in counts.items() if key != "acceptors_of_anchored"})
        print(f"{run:14s} {counts['alignment_records']:8d} "
              f"{counts['fragments_after_filters']:10d} {counts['fragments_anchored']:9d}  "
              f"{counts['acceptors_of_anchored']}")
    print(f"{'total':14s} {totals['alignment_records']:8d} "
          f"{totals['fragments_after_filters']:10d} {totals['fragments_anchored']:9d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
