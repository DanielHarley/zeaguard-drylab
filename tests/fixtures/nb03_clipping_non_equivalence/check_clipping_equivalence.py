"""Synthetic diagnostic of fixed-HSP clipping versus a newly optimized window BLAST.

This is not the NB03 CP3 pipeline and uses no TSA or biological candidate sequence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess

from zeaguard import nb02_specificity as spec

OUT = Path(__file__).resolve().parent
commands = []


def run(command, output=None):
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.run(command, capture_output=True, text=True, check=True)
    commands.append({"command": command, "started_utc": started,
                     "finished_utc": datetime.now(timezone.utc).isoformat()})
    if output is not None:
        output.write_text(process.stdout, encoding="utf-8", newline="\n")
    return process.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


rng = random.Random(193)
full = "".join(rng.choice("ACGT") for _ in range(2337))
subject = list(full)
change = dict(zip("ACGT", "CGTA"))
for index in range(500, 510):
    subject[index] = change[subject[index]]
subject = "".join(subject)
start, end = 501, 900
window = full[start - 1:end]
for name, sequence in (("full_query", full), ("window_query", window), ("subject", subject)):
    (OUT / f"{name}.fasta").write_text(f">{name}\n{sequence}\n", encoding="ascii", newline="\n")
database = OUT / "synthetic_database"
version = run(["blastn", "-version"])
run(["makeblastdb", "-in", str(OUT / "subject.fasta"), "-dbtype", "nucl", "-out", str(database)])
database_info = run(["blastdbcmd", "-db", str(database), "-info"])
arguments = ["-task", "blastn", "-dust", "no", "-word_size", "11", "-evalue", "10", "-strand", "both",
             "-max_target_seqs", "100000", "-num_threads", "1", "-outfmt", "6 " + " ".join(spec.BLAST_OUTFMT_FIELDS)]
full_raw = run(["blastn", "-query", str(OUT / "full_query.fasta"), "-db", str(database), *arguments],
               OUT / "full_query_blast.outfmt6.tsv")
window_raw = run(["blastn", "-query", str(OUT / "window_query.fasta"), "-db", str(database), *arguments],
                 OUT / "window_query_blast.outfmt6.tsv")
full_hsps, window_hsps = spec.parse_hsp_table(full_raw), spec.parse_hsp_table(window_raw)
clipped = spec.unit_evidence([spec.footprint(h, "SYNTHETIC_SUBJECT") for h in full_hsps], start, end)
independent = spec.unit_evidence([spec.footprint(h, "SYNTHETIC_SUBJECT") for h in window_hsps], 1, len(window))
axes = ("longest_exact_match_clipped", "covered_nt_clipped", "best_local_identity_clipped")
report = {
    "scope": "synthetic_method_diagnostic_only_no_TSA_or_NB03_candidate_search",
    "blast_version": version.strip(), "database_info": database_info.strip(),
    "full_query_length": len(full), "window_length": len(window), "window_on_full_query": [start, end],
    "mismatched_subject_positions": list(range(501, 511)),
    "full_query_hsps": [{"qstart": h.qstart, "qend": h.qend, "sstart": h.sstart, "send": h.send,
                          "btop": h.btop, "identity_percent": h.pident, "alignment_length": h.length} for h in full_hsps],
    "independent_window_hsps": [{"qstart": h.qstart, "qend": h.qend, "sstart": h.sstart, "send": h.send,
                                  "btop": h.btop, "identity_percent": h.pident, "alignment_length": h.length} for h in window_hsps],
    "clip_full_query_hsps_to_window": clipped,
    "independent_window_alignment": independent,
    "same_three_metrics": all(clipped[axis] == independent[axis] for axis in axes),
    "commands": commands,
    "file_sha256": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix in {".fasta", ".tsv", ".py"}},
}
(OUT / "clipping_equivalence_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(report, indent=2))
