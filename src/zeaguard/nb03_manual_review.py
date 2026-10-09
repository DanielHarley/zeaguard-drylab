"""NB03 CP4B: materialize the human manual-review decisions and the shortlist they define.

CP4B is HUMAN_ADJUDICATED. The scientific decisions were taken outside the algorithm, on the frozen CP4A evidence,
and live in the versioned record ``config/nb03_manual_review_decisions.tsv``. This module only reads that record,
validates it against the pre-registered contract, and materializes it:

    human decision record -> validate -> materialize -> summarize

Nothing here re-derives a decision. No OTHER_TRANSCRIPT, exact k-mer, BICC_LIKE, DSRNASE2, e-value, HSP-count or
benchmark value is compared against any number: those descriptors are carried through as text. No window id appears
in this file, so changing the record changes the outcome and editing the code cannot. Pareto status, cells and
difference tiers are read from the CP4A packet and never recomputed; BLAST and the exact k-mer scans are not re-run.

The per-scope decision vocabulary is read from the registry (``policy.manual_review_decisions``), never copied here.
``review_disposition`` and ``decision_role`` are separate columns precisely so that the registry's formal scope
vocabulary keeps its own meaning: a HOLD is never written as a STRONG_* concern.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

from zeaguard import nb03_criteria as criteria, nb03_design as design, nb03_selection as selection

DECISIONS_PATH = Path("config/nb03_manual_review_decisions.tsv")
CP2_DIR = Path("results/bioinformatics/nb03/cp2")
CP3_DIR = Path("results/bioinformatics/nb03/cp3")
CP4A_DIR = Path("results/bioinformatics/nb03/cp4a")
OUTPUT_DIR = Path("results/bioinformatics/nb03/cp4b")

#: The CP4A commit whose outputs this checkpoint adjudicates, and the hashes of the two frozen evidence files that
#: the CP4A manifest does not certify itself (the BICC_LIKE HSP reference was extracted from the certified
#: ``cp3/blast_hsps.tsv`` after CP4A was materialized; the manifest hash is the one quoted in the CP4B request).
CP4A_COMMIT = "fe311344cbea9c6b527013090b715eccd5c9ba4a"
CP4A_MANIFEST_SHA256 = "e2ff9292271fc229ce4bb69f05acf8e064a897acaff77b326f89c4aabb55820c"
BICC_LIKE_HSP_REFERENCE_SHA256 = "0e6ec0804e6f136a4a6dd1cde3a5dbc8c852d1bc508b42cd75b6b066531fa7f5"

DECISION_COLUMNS = ("window_id", "review_disposition", "decision_role", "other_transcript_decision", "bicc_like_decision",
                    "manual_reviewer_basis", "other_transcript_interpretation", "bicc_like_interpretation",
                    "observed_difference_interpretation", "relationship_status", "rationale", "reviewer", "decided_utc",
                    "evidence_packet_sha256", "other_transcript_hsp_reference_sha256", "bicc_like_hsp_reference_sha256")
#: Reviewed scopes, mapped to their column; DSRNASE2 is a registry scope that this review did not adjudicate and so
#: carries no column (the registry requires only OTHER_TRANSCRIPT before a recommendation).
SCOPE_COLUMNS = {"OTHER_TRANSCRIPT": "other_transcript_decision", "BICC_LIKE": "bicc_like_decision"}
REQUIRED_SCOPE = "OTHER_TRANSCRIPT"

ADVANCE = "ADVANCE_TO_SHORTLIST"
HOLD = "HOLD"
EXCLUDE = "EXCLUDE"
DISPOSITIONS = (ADVANCE, HOLD, EXCLUDE)
#: Explanatory roles, kept apart from the registry's formal per-scope vocabulary.
ROLES_BY_DISPOSITION = {ADVANCE: ("PRIMARY_CANDIDATE_PROVISIONAL", "SECONDARY_REGION_EQUIVALENT_ALTERNATIVE"),
                        HOLD: ("RESERVE", "HOLD_FOR_BACKGROUND_INTERPRETABILITY"),
                        EXCLUDE: ("EXCLUDED_AFTER_REVIEW",)}
HASH_COLUMNS = ("evidence_packet_sha256", "other_transcript_hsp_reference_sha256", "bicc_like_hsp_reference_sha256")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
RELATIONSHIP_STATUSES = ("NOT_APPLICABLE", "UNRESOLVED")

RESOLVED_COLUMNS = (*(c for c in selection.PACKET_COLUMNS if c != "manual_review_status"),
                    "review_disposition", "decision_role", "shortlist_member",
                    *(c for c in DECISION_COLUMNS if c not in ("window_id", "review_disposition", "decision_role")))
SHORTLIST_COLUMNS = ("window_id", "decision_role", "cds_start", "cds_end", "length_nt", "sequence_length_nt", "sequence_sha256",
                     "cell_id", "pareto_status", "difference_tier", "count_intersected_observed_sequence_differences",
                     "intersected_observed_sequence_difference_positions", "bicc_like_longest_exact_match", "bicc_like_covered_nt",
                     "bicc_like_best_local_identity", "bicc_like_aligned_nt_for_best_identity", "other_transcript_n_hsps",
                     "other_transcript_n_subject_records", "other_transcript_longest_exact_match", "other_transcript_covered_nt",
                     "exact_19mer_other_transcript", "exact_21mer_other_transcript", "gc_fraction", "longest_homopolymer",
                     "low_complexity_fraction", "target_region_position", "relation_to_benchmark", "review_disposition",
                     "other_transcript_decision", "bicc_like_decision", "relationship_status", *HASH_COLUMNS)
DETERMINISTIC_OUTPUTS = ("manual_review_resolved.tsv", "shortlist.tsv", "shortlist.fasta", "cp4b_summary.json")


class NB03ManualReviewError(ValueError):
    """The manual-review record or its materialization violates the pre-registered contract."""


# --------------------------------------------------------------------------- data-free kernel
@dataclass(frozen=True)
class ReviewDecision:
    """One frozen human decision for one reviewed window; every field comes from the versioned record."""

    window_id: str
    review_disposition: str
    decision_role: str
    other_transcript_decision: str
    bicc_like_decision: str
    manual_reviewer_basis: str
    other_transcript_interpretation: str
    bicc_like_interpretation: str
    observed_difference_interpretation: str
    relationship_status: str
    rationale: str
    reviewer: str
    decided_utc: str
    evidence_packet_sha256: str
    other_transcript_hsp_reference_sha256: str
    bicc_like_hsp_reference_sha256: str

    @property
    def advances(self) -> bool:
        return self.review_disposition == ADVANCE

    def scope_decision(self, scope: str) -> str:
        return getattr(self, SCOPE_COLUMNS[scope])


def concern_decisions(vocabulary: Mapping[str, Sequence[str]]) -> frozenset[str]:
    """Every non-APPROVED value of the registry vocabulary, i.e. the STRONG_* concerns."""
    return frozenset(value for values in vocabulary.values() for value in values if value != "APPROVED")


def validate_decision(decision: ReviewDecision, vocabulary: Mapping[str, Sequence[str]], where: str) -> None:
    """Check one record row against the pre-registered contract. No descriptor value is inspected."""
    for field in fields(decision):
        if not getattr(decision, field.name).strip():
            raise NB03ManualReviewError(f"{where}: {field.name} is required")
    if decision.review_disposition not in DISPOSITIONS:
        raise NB03ManualReviewError(f"{where}: unknown review_disposition {decision.review_disposition!r}")
    if decision.decision_role not in ROLES_BY_DISPOSITION[decision.review_disposition]:
        raise NB03ManualReviewError(f"{where}: decision_role {decision.decision_role!r} does not belong to "
                                    f"{decision.review_disposition}")
    for scope, column in SCOPE_COLUMNS.items():
        if scope not in vocabulary:
            raise NB03ManualReviewError(f"{where}: {scope} is not a registry manual-review scope")
        if getattr(decision, column) not in vocabulary[scope]:
            raise NB03ManualReviewError(f"{where}: {getattr(decision, column)!r} is not a registry decision for {scope}")
    if decision.relationship_status not in RELATIONSHIP_STATUSES:
        raise NB03ManualReviewError(f"{where}: unknown relationship_status {decision.relationship_status!r}")
    for column in HASH_COLUMNS:
        if not HEX64.match(getattr(decision, column)):
            raise NB03ManualReviewError(f"{where}: {column} must be the sha256 of the reviewed evidence file")
    concerns = concern_decisions(vocabulary)
    recorded = {scope: decision.scope_decision(scope) for scope in SCOPE_COLUMNS}
    if any(value in concerns for value in recorded.values()) and decision.review_disposition != EXCLUDE:
        raise NB03ManualReviewError(f"{where}: a STRONG_* concern must lead to {EXCLUDE} (registry on_strong_concern)")
    if decision.advances and recorded[REQUIRED_SCOPE] != "APPROVED":
        raise NB03ManualReviewError(f"{where}: {REQUIRED_SCOPE} must be APPROVED before a window may advance")


def load_decisions(path: Path, vocabulary: Mapping[str, Sequence[str]]) -> dict[str, ReviewDecision]:
    """Parse the versioned record: exact columns, no duplicate window, every value inside the frozen vocabularies."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != DECISION_COLUMNS:
            raise NB03ManualReviewError(f"decision record columns must be {DECISION_COLUMNS}")
        decisions: dict[str, ReviewDecision] = {}
        for line, row in enumerate(reader, start=2):
            if any(row[c] is None for c in DECISION_COLUMNS) or None in row:
                raise NB03ManualReviewError(f"line {line}: the row does not have exactly {len(DECISION_COLUMNS)} fields")
            decision = ReviewDecision(**{c: (row[c] or "").strip() for c in DECISION_COLUMNS})
            validate_decision(decision, vocabulary, f"line {line}")
            if decision.window_id in decisions:
                raise NB03ManualReviewError(f"line {line}: duplicate decision for {decision.window_id}")
            decisions[decision.window_id] = decision
    return decisions


def resolve(reviewed_ids: Sequence[str], decisions: Mapping[str, ReviewDecision]) -> tuple[ReviewDecision, ...]:
    """Require an exact one-to-one match with the reviewed scope and return the decisions in the given order."""
    if len(set(reviewed_ids)) != len(reviewed_ids):
        raise NB03ManualReviewError("the reviewed scope contains a duplicate window id")
    missing = [i for i in reviewed_ids if i not in decisions]
    extra = sorted(set(decisions) - set(reviewed_ids))
    if missing or extra:
        raise NB03ManualReviewError(f"the decision record must match the reviewed scope exactly; missing {missing}, extra {extra}")
    return tuple(decisions[i] for i in reviewed_ids)


def shortlist(resolved: Iterable[ReviewDecision]) -> tuple[ReviewDecision, ...]:
    """The windows the human review advanced, in the order they were given. Nothing is chosen here."""
    return tuple(d for d in resolved if d.advances)


def disposition_counts(resolved: Iterable[ReviewDecision]) -> dict[str, int]:
    counts = Counter(d.review_disposition for d in resolved)
    return {disposition: counts.get(disposition, 0) for disposition in DISPOSITIONS}


def role_counts(resolved: Iterable[ReviewDecision]) -> dict[str, int]:
    counts = Counter(d.decision_role for d in resolved)
    return {role: counts.get(role, 0) for roles in ROLES_BY_DISPOSITION.values() for role in roles}


# --------------------------------------------------------------------------- CP4B materialization
def verify_frozen_evidence(root: Path) -> dict[str, str]:
    """The CP4A evidence, the CP2/CP3 sequence sources and the registry must match their certified hashes."""
    root = Path(root)
    cp4a, cp2, cp3 = root / CP4A_DIR, root / CP2_DIR, root / CP3_DIR
    manifest = json.loads((cp4a / "run_manifest.json").read_text(encoding="utf-8"))
    manifest_sha = design._sha256(cp4a / "run_manifest.json")
    if manifest_sha != CP4A_MANIFEST_SHA256:
        raise NB03ManualReviewError("the CP4A manifest is not the frozen one adjudicated by this review")
    if manifest.get("stage") != "NB03_CP4A_PARETO_CELLS_AND_MANUAL_REVIEW_PACKET":
        raise NB03ManualReviewError("the CP4A manifest does not describe the CP4A stage")
    if manifest["selection_policy_commit"] != selection.SELECTION_POLICY_COMMIT:
        raise NB03ManualReviewError("the CP4A manifest was built under a different selection-policy commit")
    hashes: dict[str, str] = {}
    for name, expected in manifest["outputs_sha256"].items():
        actual = design._sha256(cp4a / name)
        if actual != expected:
            raise NB03ManualReviewError(f"frozen CP4A evidence changed: cp4a/{name}")
        hashes[f"cp4a/{name}"] = actual
    hashes["cp4a/run_manifest.json"] = manifest_sha
    bicc = design._sha256(cp4a / "bicc_like_hsp_reference.tsv")
    if bicc != BICC_LIKE_HSP_REFERENCE_SHA256:
        raise NB03ManualReviewError("frozen BICC_LIKE HSP reference changed")
    hashes["cp4a/bicc_like_hsp_reference.tsv"] = bicc

    registry_sha = criteria.registry_sha256(root / criteria.REGISTRY_PATH)
    if registry_sha != manifest["inputs"]["registry_sha256_lf"]:
        raise NB03ManualReviewError("the registry differs from the one CP4A was materialized under")
    hashes["config/nb03_design_criteria.yaml"] = registry_sha

    manifest2 = json.loads((cp2 / "run_manifest.json").read_text(encoding="utf-8"))
    manifest3 = json.loads((cp3 / "run_manifest.json").read_text(encoding="utf-8"))
    for label, directory, manifest_json in (("cp2", cp2, manifest2), ("cp3", cp3, manifest3)):
        own = design._sha256(directory / "run_manifest.json")
        if own != manifest["inputs"]["certified_input_sha256"][f"{label}/run_manifest.json"]:
            raise NB03ManualReviewError(f"{label} manifest differs from the one CP4A certified")
        hashes[f"{label}/run_manifest.json"] = own
    for name in ("design_space.tsv", "benchmark_descriptor.tsv"):
        actual = design._sha256(cp2 / name)
        if actual != manifest2["outputs_sha256"][name]:
            raise NB03ManualReviewError(f"certified CP2 input changed: cp2/{name}")
        hashes[f"cp2/{name}"] = actual
    for name in manifest3["outputs_sha256"]:
        actual = design._sha256(cp3 / name)
        if actual != manifest3["outputs_sha256"][name]:
            raise NB03ManualReviewError(f"certified CP3 output changed: cp3/{name}")
        hashes[f"cp3/{name}"] = actual
    return hashes


def load_reviewed_packet(root: Path) -> list[dict[str, str]]:
    """The CP4A manual-review packet, in the order CP4A wrote it (CANONICAL_DISPLAY_ORDER_ONLY, not a ranking)."""
    rows = selection._read_tsv(Path(root) / CP4A_DIR / "manual_review_packet.tsv")
    if not rows:
        raise NB03ManualReviewError("the CP4A manual-review packet is empty")
    if {r["manual_review_status"] for r in rows} != {selection.MANUAL_REVIEW_INITIAL_STATUS}:
        raise NB03ManualReviewError("every packet row must carry the initial PENDING status")
    if {r["pareto_status"] for r in rows} != {selection.NONDOMINATED} or {r["length_nt"] for r in rows} != {
            str(selection.NOMINAL_REVIEW_LENGTH_NT)}:
        raise NB03ManualReviewError("the reviewed scope must be exactly the L400 NONDOMINATED windows")
    return rows


def load_certified_sequences(root: Path, rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    """Read each window's sequence from the CP3 native-query FASTA and verify it against the CP2 sequence hash."""
    root = Path(root)
    manifest3 = json.loads((root / CP3_DIR / "run_manifest.json").read_text(encoding="utf-8"))
    cp2 = {r["window_id"]: r for r in selection._read_tsv(root / CP2_DIR / "design_space.tsv")}
    wanted = {r["window_id"]: int(r["length_nt"]) for r in rows}
    sequences: dict[str, str] = {}
    for length in sorted(set(wanted.values())):
        relative = f"queries/L{length}.fasta"
        path = root / CP3_DIR / relative
        if design._sha256(path) != manifest3["query_fasta_sha256"][relative]:
            raise NB03ManualReviewError(f"certified CP3 query FASTA changed: cp3/{relative}")
        name = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(">"):
                name = line[1:].strip()
            elif name in wanted:
                sequences[name] = sequences.get(name, "") + line.strip()
    for window_id, length in wanted.items():
        sequence = sequences.get(window_id, "")
        row = cp2.get(window_id)
        if row is None:
            raise NB03ManualReviewError(f"{window_id} is absent from the certified CP2 design space")
        if len(sequence) != length or int(row["length_nt"]) != length:
            raise NB03ManualReviewError(f"{window_id}: the certified sequence is not {length} nt")
        if set(sequence) - set("ACGT"):
            raise NB03ManualReviewError(f"{window_id}: the certified sequence is not restricted to A/C/G/T")
        if design.sha256_text(sequence) != row["sequence_sha256"]:
            raise NB03ManualReviewError(f"{window_id}: the native query sequence differs from the CP2 sequence hash")
    return sequences


def run_cp4b(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Materialize the frozen human decisions and the shortlist they define. No decision is re-derived here."""
    started = datetime.now(timezone.utc).isoformat()
    root = Path(root).resolve()
    registry = criteria.load_registry(root)
    if criteria.validate_registry(registry):
        raise NB03ManualReviewError("the NB03 registry is invalid")
    review_policy = registry["policy"]["manual_review_decisions"]
    if Path(review_policy["path"]) != DECISIONS_PATH or review_policy["required_scope_for_recommendation"] != REQUIRED_SCOPE:
        raise NB03ManualReviewError("the registry does not declare this decision-record path and required scope")
    vocabulary = review_policy["decisions"]
    bounds = registry["policy"]["recommended_candidates"]

    input_hashes = verify_frozen_evidence(root)
    rows = load_reviewed_packet(root)
    reviewed_ids = [r["window_id"] for r in rows]
    decisions = load_decisions(root / DECISIONS_PATH, vocabulary)
    resolved = resolve(reviewed_ids, decisions)
    advanced = shortlist(resolved)
    counts, roles = disposition_counts(resolved), role_counts(resolved)
    if not bounds["min"] <= len(advanced) <= bounds["max"]:
        raise NB03ManualReviewError(f"the shortlist must hold {bounds['min']}-{bounds['max']} candidates, got {len(advanced)}")
    for decision in resolved:
        if decision.evidence_packet_sha256 != input_hashes["cp4a/manual_review_packet.tsv"]:
            raise NB03ManualReviewError(f"{decision.window_id}: the reviewed packet hash is not the frozen one")
        if decision.other_transcript_hsp_reference_sha256 != input_hashes["cp4a/other_transcript_hsp_reference.tsv"]:
            raise NB03ManualReviewError(f"{decision.window_id}: the reviewed OTHER_TRANSCRIPT evidence hash differs")
        if decision.bicc_like_hsp_reference_sha256 != input_hashes["cp4a/bicc_like_hsp_reference.tsv"]:
            raise NB03ManualReviewError(f"{decision.window_id}: the reviewed BICC_LIKE evidence hash differs")

    sequences = load_certified_sequences(root, [r for r in rows if r["window_id"] in {d.window_id for d in advanced}])
    cp2 = {r["window_id"]: r for r in selection._read_tsv(root / CP2_DIR / "design_space.tsv")}
    out = Path(output_dir) if output_dir else root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ resolved review table (all reviewed windows)
    by_id = {d.window_id: d for d in resolved}
    resolved_rows = []
    for row in rows:
        decision = by_id[row["window_id"]]
        resolved_rows.append({**{c: row[c] for c in selection.PACKET_COLUMNS if c != "manual_review_status"},
                              "review_disposition": decision.review_disposition, "decision_role": decision.decision_role,
                              "shortlist_member": decision.advances,
                              **{c: getattr(decision, c) for c in DECISION_COLUMNS
                                 if c not in ("window_id", "review_disposition", "decision_role")}})
    selection._write_table(out / "manual_review_resolved.tsv", RESOLVED_COLUMNS, resolved_rows)

    # ------------------------------------------------------------------ shortlist table and FASTA
    packet_by_id = {r["window_id"]: r for r in rows}
    shortlist_rows = []
    for decision in advanced:
        row, sequence = packet_by_id[decision.window_id], sequences[decision.window_id]
        shortlist_rows.append({**{c: row[c] for c in SHORTLIST_COLUMNS if c in row},
                               "decision_role": decision.decision_role, "review_disposition": decision.review_disposition,
                               "sequence_length_nt": len(sequence), "sequence_sha256": cp2[decision.window_id]["sequence_sha256"],
                               **{c: getattr(decision, c) for c in ("other_transcript_decision", "bicc_like_decision",
                                                                    "relationship_status", *HASH_COLUMNS)}})
    selection._write_table(out / "shortlist.tsv", SHORTLIST_COLUMNS, shortlist_rows)
    (out / "shortlist.fasta").write_text(
        "".join(f">{d.window_id}\n{sequences[d.window_id]}\n" for d in advanced), encoding="utf-8", newline="\n")

    # ------------------------------------------------------------------ summary
    shared = _shared_positions([(int(packet_by_id[d.window_id]["cds_start"]), int(packet_by_id[d.window_id]["cds_end"]))
                                for d in advanced if d.decision_role == "SECONDARY_REGION_EQUIVALENT_ALTERNATIVE"])
    summary = {
        "stage": "NB03_CP4B_MANUAL_REVIEW_RESOLUTION_AND_SHORTLIST", "adjudication": "HUMAN_ADJUDICATED",
        "manual_review_completed": True, "cp4a_commit": CP4A_COMMIT,
        "decision_record": str(DECISIONS_PATH).replace("\\", "/"),
        "n_reviewed": len(resolved), "n_advance": counts[ADVANCE], "n_hold": counts[HOLD], "n_exclude": counts[EXCLUDE],
        "n_primary": roles["PRIMARY_CANDIDATE_PROVISIONAL"],
        "n_secondary_equivalent_alternatives": roles["SECONDARY_REGION_EQUIVALENT_ALTERNATIVE"],
        "n_reserve": roles["RESERVE"], "n_background_hold": roles["HOLD_FOR_BACKGROUND_INTERPRETABILITY"],
        "shortlist_ids": [d.window_id for d in advanced],
        "shortlist_roles": {d.window_id: d.decision_role for d in advanced},
        "shortlist_n_sequences": len(advanced),
        "shortlist_sequence_lengths_nt": sorted({len(sequences[d.window_id]) for d in advanced}),
        "secondary_region_preference": "UNRESOLVED",
        "secondary_region_note": (f"the two secondary alternatives share {shared} of 400 genomic/CDS positions and no frozen "
                                  "decision rule resolves their trade-off; they are not described as biologically identical, "
                                  "and construction or primer feasibility is a later step, not part of CP4B"),
        "dispositions": counts, "roles": roles,
        "scope_decisions": {scope: dict(Counter(d.scope_decision(scope) for d in resolved)) for scope in SCOPE_COLUMNS},
        "registry_scopes": {"declared": list(review_policy["scopes"]), "adjudicated": sorted(SCOPE_COLUMNS),
                            "not_adjudicated": [s for s in review_policy["scopes"] if s not in SCOPE_COLUMNS],
                            "required_scope_for_recommendation": REQUIRED_SCOPE},
        "recommended_candidates_bounds": {"min": bounds["min"], "max": bounds["max"], "n_advanced": len(advanced)},
        "display_order": {"classification": selection.DISPLAY_ORDER_CLASSIFICATION, "source": "CP4A manual_review_packet.tsv",
                          "is_ranking": False, "is_tie_breaker": False},
        "statements": [
            "the manual review was carried out by a human outside the algorithm; this checkpoint only validated and materialized it",
            "no decision was re-derived from any descriptor: the dispositions and roles come from the versioned decision record",
            "no cutoff was introduced for OTHER_TRANSCRIPT HSP or subject counts, covered_nt, longest exact tract, identity or e-value",
            "exact 19-mer and 21-mer counts stayed DESCRIPTIVE_ONLY and no k-mer threshold was created",
            "BICC_LIKE evidence already took part in the six-axis Pareto comparison and was not reapplied as a post-Pareto filter",
            "no window was classified as a confirmed off-target and no STRONG_* specificity concern was recorded",
            "the GITV relationships relevant to this review remain RELATIONSHIP_UNRESOLVED",
            "the published benchmark was used as a descriptive reference only, never as a limit of acceptability",
            "HOLD preserves a candidate; it does not mean unsafe, ineffective or off-target confirmed",
            "neither secondary alternative was chosen over the other",
            "Pareto status, cells and difference tiers were read from the CP4A packet and never recomputed"],
        "not_executed": ["pareto_recomputation", "blast", "kmer_recomputation", "automatic_representative_selection",
                         "automatic_choice_between_the_secondary_alternatives", "CP5", "wet_lab_handoff",
                         "data/reference handoff materialization"]}
    design._write_json(out / "cp4b_summary.json", summary)

    outputs = {name: design._sha256(out / name) for name in DETERMINISTIC_OUTPUTS}
    sources = ("src/zeaguard/nb03_manual_review.py", "src/zeaguard/nb03_selection.py", "src/zeaguard/nb03_criteria.py")
    manifest = {"schema_version": 1, "stage": summary["stage"], "adjudication": "HUMAN_ADJUDICATED",
                "cp4a_commit": CP4A_COMMIT, "selection_policy_commit": selection.SELECTION_POLICY_COMMIT,
                "python_version": sys.version.split()[0],
                "inputs": {"decision_record_sha256_lf": criteria.registry_sha256(root / DECISIONS_PATH),
                           "certified_input_sha256": input_hashes},
                "implementation_sha256_lf": {p: criteria.registry_sha256(root / p) for p in sources},
                "counts": {"reviewed_windows": len(resolved), "advance": counts[ADVANCE], "hold": counts[HOLD],
                           "exclude": counts[EXCLUDE], "shortlist_sequences": len(advanced)},
                "outputs_sha256": outputs, "deterministic_outputs": list(DETERMINISTIC_OUTPUTS),
                "execution_metadata": {"file": "execution_metadata.json", "excluded_from_deterministic_outputs": True}}
    design._write_json(out / "run_manifest.json", manifest)
    design._write_json(out / "execution_metadata.json", {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                                                         "python": sys.version, "platform": sys.platform})
    return {"summary": summary, "manifest": manifest, "resolved": resolved, "shortlist": advanced, "rows": resolved_rows,
            "sequences": sequences, "outputs_sha256": {**outputs, "run_manifest.json": design._sha256(out / "run_manifest.json")}}


def _shared_positions(intervals: Sequence[tuple[int, int]]) -> int:
    """Inclusive intersection length of the given intervals; 0 when fewer than two are present."""
    if len(intervals) < 2:
        return 0
    return max(0, min(end for _, end in intervals) - max(start for start, _ in intervals) + 1)


def main() -> int:
    from zeaguard.repro import find_project_root

    result = run_cp4b(find_project_root())
    print(json.dumps({"outputs_sha256": result["outputs_sha256"], "shortlist_ids": result["summary"]["shortlist_ids"]}, indent=2),
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
