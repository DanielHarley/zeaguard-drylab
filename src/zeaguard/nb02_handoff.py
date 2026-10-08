"""NB02 checkpoint 5: the versioned Wet Lab hand-off.

Closes the shortlist once every recommended candidate carries a versioned APPROVED OTHER_TRANSCRIPT
review decision, and writes the two versioned artefacts the Wet Lab consumes:
``data/reference/nb02_dsrnase2_candidate_regions.tsv`` and its FASTA (coding/sense orientation, no tails).

Two lists are kept apart. REFERENCE_SET holds the published 330 nt benchmark, which appears in every
table and never counts as a recommended candidate. RECOMMENDED_SHORTLIST holds the new candidates.
The hand-off carries region, length, provenance, variants, specificity and limitations only: construct
engineering (architecture, primers, promoter, loop, terminator, restriction sites, codon optimisation,
backbone, T7 tails) and ecological off-target stay outside NB02.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from zeaguard import nb02_cells, nb02_criteria, nb02_design, nb02_reference, nb02_specificity
from zeaguard.nb01_dsrnase_investigation import write_tsv

HANDOFF_TSV = Path("data/reference/nb02_dsrnase2_candidate_regions.tsv")
HANDOFF_FASTA = Path("data/reference/nb02_dsrnase2_candidate_regions.fasta")
LIMITATIONS_PATH = Path("config/nb02_candidate_limitations.tsv")
OUTPUT_DIR = Path("results/bioinformatics/nb02/cp5")

REFERENCE_SET = "REFERENCE_SET"
RECOMMENDED = "RECOMMENDED_SHORTLIST"

HANDOFF_COLUMNS = (
    "candidate_id", "list_membership", "candidate_class",
    "reference_accession", "reference_sequence_sha256", "cds_start", "cds_end", "length_nt",
    "transcript_start", "transcript_end", "sequence_sha256", "sequence",
    "relative_midpoint", "target_region_position",
    "cell_id", "cell_start_min", "cell_start_max", "cell_end_min", "cell_end_max", "cell_n_windows",
    "n_variant_sites", "variant_positions", "n_defined_variants", "n_iupac_variants",
    "variant_sites_supported_by_reads", "n_potential_small_rna_windows",
    "fraction_potential_small_rna_windows_unaffected",
    "dsrnase1_specificity_clipped", "dsrnase3_specificity_clipped", "bicc_specificity_clipped",
    "other_transcript_longest_exact_match_clipped", "other_transcript_covered_nt_clipped",
    "other_transcript_n_hsps_clipped", "other_transcript_exact_19mer_count_clipped",
    "other_transcript_exact_21mer_count_clipped",
    "review_scope", "review_decision", "review_reviewer", "review_decided_utc", "review_evidence_sha256",
    "benchmark_sequence_verification", "experimental_protocol_verification",
    "overlap_with_benchmark_nt", "converges_with_benchmark", "convergence_participated_in_ranking",
    "gc_fraction", "longest_homopolymer", "low_complexity_fraction",
    "inclusion_rationale", "limitations",
)
# The hand-off is region and length only: construct engineering and off-target must not leak into the schema.
FORBIDDEN_COLUMN_FRAGMENTS = (
    "primer", "promoter", "loop", "terminator", "restriction", "codon", "backbone", "plasmid",
    "hairpin", "t7", "efficacy", "ecological", "_score", "score_",
)


class NB02HandoffError(RuntimeError):
    """The hand-off cannot be closed as pre-registered."""


def load_limitations(root: Path) -> dict[str, str]:
    with (Path(root) / LIMITATIONS_PATH).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != ("candidate_id", "limitations"):
            raise NB02HandoffError("the limitations file must have the columns candidate_id and limitations")
        rows = {row["candidate_id"]: row["limitations"].strip() for row in reader}
    if any(not text for text in rows.values()):
        raise NB02HandoffError("every listed candidate must carry a non-empty limitation")
    return rows


def _vector_text(values: tuple[float, ...]) -> str:
    return f"longest_exact={values[0]:g}; covered_nt={values[1]:g}; best_local_identity={values[2]:g}"


def _benchmark_row(root: Path, reference: dict[str, Any], limitations: dict[str, str], cds: str) -> dict[str, Any]:
    """The published benchmark, described exactly like a candidate so the comparison is like for like."""
    pin = reference["pin"]["benchmark"]
    start, end = pin["interval"]["cds_start"], pin["interval"]["cds_end"]
    descriptors = {row["candidate_id"]: row for row in nb02_cells._read_tsv(root / "results/bioinformatics/nb02/benchmark_window.tsv")}
    descriptor = descriptors[pin["id"]]
    evidence = {row["class"]: row for row in nb02_cells._read_tsv(root / "results/bioinformatics/nb02/cp3/benchmark_specificity.tsv")}
    other = evidence[nb02_specificity.OTHER]
    record = reference["pin"]["records"]["operational"]
    return {
        "candidate_id": pin["id"], "list_membership": REFERENCE_SET, "candidate_class": pin["candidate_class"],
        "reference_accession": record["accession"], "reference_sequence_sha256": record["cds_sha256"],
        "cds_start": start, "cds_end": end, "length_nt": pin["interval"]["length_nt"],
        "transcript_start": descriptor["transcript_start"], "transcript_end": descriptor["transcript_end"],
        "sequence_sha256": pin["interval"]["sequence_sha256"], "sequence": cds[start - 1 : end],
        "relative_midpoint": descriptor["relative_midpoint"], "target_region_position": descriptor["target_region_position"],
        "cell_id": "", "cell_start_min": "", "cell_start_max": "", "cell_end_min": "", "cell_end_max": "", "cell_n_windows": "",
        "n_variant_sites": descriptor["n_variant_sites"], "variant_positions": descriptor["variant_positions"],
        "n_defined_variants": descriptor["n_defined_variants"], "n_iupac_variants": descriptor["n_iupac_variants"],
        "variant_sites_supported_by_reads": descriptor["sites_supported_by_reads"],
        "n_potential_small_rna_windows": descriptor["n_potential_windows"],
        "fraction_potential_small_rna_windows_unaffected": descriptor["fraction_potential_windows_unaffected"],
        **{f"{unit.lower()}_specificity_clipped": _vector_text((
            float(evidence[unit]["longest_exact_match_clipped"]), float(evidence[unit]["covered_nt_clipped"]),
            float(evidence[unit]["best_local_identity_clipped"]))) for unit in ("DSRNASE1", "DSRNASE3", "BICC")},
        "other_transcript_longest_exact_match_clipped": other["longest_exact_match_clipped"],
        "other_transcript_covered_nt_clipped": other["covered_nt_clipped"],
        "other_transcript_n_hsps_clipped": other["n_hsps_clipped"],
        "other_transcript_exact_19mer_count_clipped": other["exact_19mer_count_clipped"],
        "other_transcript_exact_21mer_count_clipped": other["exact_21mer_count_clipped"],
        "review_scope": "", "review_decision": "NOT_APPLICABLE_REFERENCE_SET", "review_reviewer": "",
        "review_decided_utc": "", "review_evidence_sha256": "",
        "benchmark_sequence_verification": pin["verification"]["benchmark_sequence_verification"],
        "experimental_protocol_verification": pin["verification"]["experimental_protocol_verification"],
        "overlap_with_benchmark_nt": pin["interval"]["length_nt"], "converges_with_benchmark": "",
        "convergence_participated_in_ranking": False,
        "gc_fraction": descriptor["gc_fraction"], "longest_homopolymer": descriptor["longest_homopolymer"],
        "low_complexity_fraction": descriptor["low_complexity_fraction"],
        "inclusion_rationale": (
            "Published experimental benchmark of Dmai dsRNase-2 (330 nt, Dalaison-Fuentes et al. 2023): it is listed "
            "in the reference set for comparison, is evaluated with the same criteria and never counts as a "
            "recommended candidate."
        ),
        "limitations": limitations[pin["id"]],
    }


def _candidate_row(
    candidate: dict[str, Any], cell: dict[str, Any], descriptor: dict[str, str], decision: Any,
    reference: dict[str, Any], limitations: dict[str, str], cds: str, bench_span: tuple[int, int],
) -> dict[str, Any]:
    start, end = candidate["cds_start"], candidate["cds_end"]
    overlap = nb02_cells.overlap_nt((start, end), bench_span)
    record = reference["pin"]["records"]["operational"]
    return {
        "candidate_id": candidate["candidate_id"], "list_membership": RECOMMENDED,
        "candidate_class": "RECOMMENDED_NEW_CANDIDATE",
        "reference_accession": record["accession"], "reference_sequence_sha256": record["cds_sha256"],
        "cds_start": start, "cds_end": end, "length_nt": candidate["length_nt"],
        "transcript_start": descriptor["transcript_start"], "transcript_end": descriptor["transcript_end"],
        "sequence_sha256": candidate["sequence_sha256"], "sequence": cds[start - 1 : end],
        "relative_midpoint": descriptor["relative_midpoint"], "target_region_position": descriptor["target_region_position"],
        "cell_id": cell["cell_id"], "cell_start_min": cell["start_min"], "cell_start_max": cell["start_max"],
        "cell_end_min": cell["end_min"], "cell_end_max": cell["end_max"], "cell_n_windows": cell["n_windows"],
        "n_variant_sites": descriptor["n_variant_sites"], "variant_positions": descriptor["variant_positions"],
        "n_defined_variants": descriptor["n_defined_variants"], "n_iupac_variants": descriptor["n_iupac_variants"],
        "variant_sites_supported_by_reads": descriptor["sites_supported_by_reads"],
        "n_potential_small_rna_windows": descriptor["n_potential_windows"],
        "fraction_potential_small_rna_windows_unaffected": descriptor["fraction_potential_windows_unaffected"],
        "dsrnase1_specificity_clipped": _vector_text((0.0, 0.0, 0.0)) if candidate["dsrnase1_vector"] == "(0,0,0)" else candidate["dsrnase1_vector"],
        "dsrnase3_specificity_clipped": _vector_text((0.0, 0.0, 0.0)) if candidate["dsrnase3_vector"] == "(0,0,0)" else candidate["dsrnase3_vector"],
        "bicc_specificity_clipped": _vector_text((0.0, 0.0, 0.0)) if candidate["bicc_vector"] == "(0,0,0)" else candidate["bicc_vector"],
        "other_transcript_longest_exact_match_clipped": candidate["other_transcript_longest_exact_match_clipped"],
        "other_transcript_covered_nt_clipped": candidate["other_transcript_covered_nt_clipped"],
        "other_transcript_n_hsps_clipped": candidate["other_transcript_n_hsps_clipped"],
        "other_transcript_exact_19mer_count_clipped": candidate["other_transcript_exact_19mer_count_clipped"],
        "other_transcript_exact_21mer_count_clipped": candidate["other_transcript_exact_21mer_count_clipped"],
        "review_scope": decision.scope, "review_decision": decision.decision, "review_reviewer": decision.reviewer,
        "review_decided_utc": decision.decided_utc, "review_evidence_sha256": decision.evidence_sha256,
        "benchmark_sequence_verification": "", "experimental_protocol_verification": "",
        "overlap_with_benchmark_nt": overlap, "converges_with_benchmark": overlap > 0,
        "convergence_participated_in_ranking": False,
        "gc_fraction": descriptor["gc_fraction"], "longest_homopolymer": descriptor["longest_homopolymer"],
        "low_complexity_fraction": descriptor["low_complexity_fraction"],
        "inclusion_rationale": (
            f"Representative of the contiguous equivalence cell {cell['cell_id']} (windows "
            f"{cell['start_min']}-{cell['start_max']}), tied at the top of ordering group "
            f"{cell['ordering_group']} of the {candidate['length_nt']} nt ranking stratum: zero clipped "
            "specificity vector against DSRNASE1, DSRNASE3 and BICC, no intercepted known variable site, and a "
            f"versioned APPROVED OTHER_TRANSCRIPT review decision ({decision.decided_utc})."
        ),
        "limitations": limitations[candidate["candidate_id"]],
    }


def run_cp5(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Close the shortlist and write the versioned Wet Lab hand-off plus its run manifest."""
    root = Path(root).resolve()
    registry = nb02_criteria.load_registry(root)
    parameters = nb02_design.design_parameters(registry)
    reference = nb02_reference.verified_reference(root)
    cds = reference["operational_cds"]
    bench = reference["pin"]["benchmark"]["interval"]
    bench_span = (bench["cds_start"], bench["cds_end"])
    limitations = load_limitations(root)
    decisions = nb02_criteria.load_review_decisions(root / nb02_criteria.REVIEW_DECISIONS_PATH)
    out = Path(output_dir) if output_dir else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    cp4 = nb02_cells.run_cp4(root, out / "cp4_recheck")
    cells = {row["representative_candidate_id"]: row for row in cp4["cell_rows"]}
    descriptors = {row["candidate_id"]: row for row in nb02_cells._read_tsv(root / nb02_cells.CP2_WINDOWS)}

    bounds = registry["policy"]["recommended_candidates"]
    rows = [_benchmark_row(root, reference, limitations, cds)]
    for candidate in cp4["candidates"]:
        nb02_criteria.assert_can_recommend(candidate["candidate_id"], decisions)  # the mandatory review gate
        rows.append(_candidate_row(
            candidate, cells[candidate["candidate_id"]], descriptors[candidate["candidate_id"]],
            decisions[(candidate["candidate_id"], "OTHER_TRANSCRIPT")], reference, limitations, cds, bench_span))

    recommended = [row for row in rows if row["list_membership"] == RECOMMENDED]
    if not bounds["min"] <= len(recommended) <= bounds["max"]:
        raise NB02HandoffError(f"{len(recommended)} recommended candidates is outside the pre-registered {bounds}")
    if any(row["list_membership"] != REFERENCE_SET for row in rows if row["candidate_class"] == "PUBLISHED_EXPERIMENTAL_BENCHMARK"):
        raise NB02HandoffError("the published benchmark must stay in the reference set")
    offenders = [c for c in HANDOFF_COLUMNS if any(f in c for f in FORBIDDEN_COLUMN_FRAGMENTS)]
    if offenders:
        raise NB02HandoffError(f"the hand-off schema must not carry construct engineering: {offenders}")
    for row in rows:
        if row["sequence_sha256"] != hashlib.sha256(row["sequence"].encode("ascii")).hexdigest():
            raise NB02HandoffError(f"{row['candidate_id']}: the sequence does not match its sha256")

    write_tsv(root / HANDOFF_TSV, rows, HANDOFF_COLUMNS)
    fasta = "".join(
        f">{row['candidate_id']} {row['list_membership']} reference={row['reference_accession']} "
        f"cds={row['cds_start']}-{row['cds_end']} length={row['length_nt']} sense_strand "
        f"sha256={row['sequence_sha256']}\n{row['sequence']}\n"
        for row in rows
    )
    (root / HANDOFF_FASTA).write_text(fasta, encoding="ascii", newline="\n")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    manifest = {
        "stage": "NB02 CP5 (versioned Wet Lab hand-off)",
        "git": nb02_design._git_state(root),
        "inputs": {
            "criteria_registry_sha256": nb02_criteria.registry_sha256(root / nb02_criteria.REGISTRY_PATH),
            "pin_sha256": reference["report"]["pin_sha256_lf"],
            "operational_cds_sha256": reference["report"]["operational"]["cds_sha256"],
            "review_decisions_sha256": digest(root / nb02_criteria.REVIEW_DECISIONS_PATH),
            "limitations_sha256": digest(root / LIMITATIONS_PATH),
        },
        "ranking_stratum_nt": parameters.ranking_length,
        "lists": {
            REFERENCE_SET: [row["candidate_id"] for row in rows if row["list_membership"] == REFERENCE_SET],
            RECOMMENDED: [row["candidate_id"] for row in recommended],
        },
        "recommended_candidate_bounds": bounds,
        "review": {
            row["candidate_id"]: {"scope": row["review_scope"], "decision": row["review_decision"],
                                  "reviewer": row["review_reviewer"], "decided_utc": row["review_decided_utc"],
                                  "evidence_sha256": row["review_evidence_sha256"]}
            for row in recommended
        },
        "convergence_with_benchmark": {
            row["candidate_id"]: {"overlap_nt": row["overlap_with_benchmark_nt"],
                                  "converges": row["converges_with_benchmark"],
                                  "participated_in_ranking": False}
            for row in recommended
        },
        "outputs_sha256": {path.as_posix(): digest(root / path) for path in (HANDOFF_TSV, HANDOFF_FASTA)},
        "out_of_scope": [
            "molecular architecture (linear, hairpin, protected-end, dual-loop)", "primers and T7 tails",
            "promoter, loop, terminator, restriction sites, codon optimisation, plasmid backbone",
            "ecological off-target against non-target organisms", "efficacy prediction or any efficacy score",
        ],
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
                                           encoding="utf-8", newline="\n")
    return {"manifest": manifest, "rows": rows, "recommended": recommended, "fasta": fasta}


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp5(find_project_root())
    print(json.dumps(result["manifest"]["lists"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
