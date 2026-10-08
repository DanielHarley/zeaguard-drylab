"""NB03 CP1: the pre-registered contract, validated by code before any candidate window exists.

Four things live here: (1) validation of ``config/nb03_design_criteria.yaml`` (vocabulary, roles, what each
criterion may influence); (2) validation of the versioned pin ``data/reference/nb01_bicc_operational_reference.json``
and its re-derivation from the hash-validated TSA, the versioned anchor FASTA and the pinned primers (the raw
primary Table S1 file is never needed); (3) validation of the unit membership decisions; and (4) a tiny,
data-free policy kernel for the joint six-axis Pareto comparison, taking explicit values.

Nothing here enumerates a window, runs a candidate search, forms a cell or recommends anything.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yaml

from zeaguard import nb02_criteria, nb03_benchmark, nb03_reference
from zeaguard.nb01_dsrnase_investigation import CommandLog

REGISTRY_PATH = Path("config/nb03_design_criteria.yaml")
MEMBERSHIP_PATH = Path("config/nb03_unit_membership_decisions.tsv")
PIN_PATH = Path("data/reference/nb01_bicc_operational_reference.json")

EVIDENCE_CATEGORIES = nb02_criteria.EVIDENCE_CATEGORIES
ROLES = nb02_criteria.ROLES
AFFECTS = nb02_criteria.AFFECTS
CRITERION_FIELDS = nb02_criteria.CRITERION_FIELDS
AMENDMENT_FIELDS = nb02_criteria.AMENDMENT_FIELDS
HEX64 = nb02_criteria.HEX64
UNIT_ROLES = frozenset({"KNOWN_COMPATIBLE_EXCLUDED_FROM_RISK", "DECISIONAL_INTERPRETABILITY",
                        "CO_TARGET_DECISIONAL_INTERPRETABILITY", "DESCRIPTIVE_ONLY", "DESCRIPTIVE_PLUS_MANUAL_REVIEW"})
STATEMENT_CATEGORIES = frozenset({"OBSERVATION", "INFERENCE", "HYPOTHESIS", "PROJECT_CONVENTION", "OPERATIONAL_ASSUMPTION"})
FORBIDDEN_THRESHOLD_KEY = nb02_criteria.FORBIDDEN_THRESHOLD_KEY
FORBIDDEN_POLICY_KEY = re.compile(r"(weight|score|sum|composite|normali[sz])", re.I)

HARD_FILTERS = frozenset({"inside_operational_cds", "length_range", "defined_bases_only"})
DECISIONAL_CRITERIA = frozenset({"specificity_evidence_vector", "count_intersected_observed_sequence_differences"})
ORDERING_AFFECTS = frozenset({"pareto", "cell_signature", "primary_ordering"})
MANDATORY_REVIEW_CRITERION = "other_transcript_specificity"
REQUIRED_DESCRIPTORS = frozenset({
    "gc_fraction", "longest_homopolymer", "low_complexity_fraction", "target_region_position", "potential_21nt_derived_windows",
    "fraction_unaffected", "exact_kmer_counts", "evalue_and_hsp_counts", "descriptive_only_units", "shuffled_control",
    "benchmark_relation_descriptors", "unit_relationship_status", "search_detection_limit", "homology_evidence_metrics_clipped",
    "length_strata", "published_benchmark_reference", "intersected_observed_sequence_difference_positions",
})
UNIT_ROLE_BY_NAME = {
    "KNOWN_BICC_COMPATIBLE": "KNOWN_COMPATIBLE_EXCLUDED_FROM_RISK", "BICC_LIKE": "DECISIONAL_INTERPRETABILITY",
    "DSRNASE2": "CO_TARGET_DECISIONAL_INTERPRETABILITY", "DSRNASE1": "DESCRIPTIVE_ONLY", "DSRNASE3": "DESCRIPTIVE_ONLY",
    "OTHER_TRANSCRIPT": "DESCRIPTIVE_PLUS_MANUAL_REVIEW",
}
PARETO_UNITS = ("BICC_LIKE", "DSRNASE2")
PARETO_AXES_PER_UNIT = ("longest_exact_match_clipped", "covered_nt_clipped", "best_local_identity_clipped")
CELL_SIGNATURE = ["count_intersected_observed_sequence_differences", "bicc_like_vector_clipped", "dsrnase2_vector_clipped"]
CELL_SIGNATURE_MUST_EXCLUDE = frozenset({"intersected_observed_sequence_difference_positions",
                                         "target_region_position", "other_transcript_hits", "potential_21nt_derived_windows",
                                         "fraction_unaffected", "benchmark_relation", "overlap_with_benchmark_nt",
                                         "overlap_fraction_of_candidate", "overlap_fraction_of_benchmark", "relation_to_benchmark"})
BENCHMARK_RELATION_CATEGORIES = frozenset({"DISJOINT", "PARTIAL_OVERLAP", "FULLY_WITHIN", "CONTAINS_BENCHMARK", "EXACT_MATCH"})
BENCHMARK_RELATION_DESCRIPTORS = (
    "overlap_with_benchmark_nt", "overlap_fraction_of_candidate", "overlap_fraction_of_benchmark", "relation_to_benchmark",
)
MEMBERSHIP_COLUMNS = ("record_id", "unit", "relationship_status", "decision", "rationale", "evidence_source",
                      "evidence_sha256", "decided_by", "decided_utc")
RELATIONSHIP_STATUSES = frozenset({"NOT_APPLICABLE", "UNRESOLVED"})


class NB03RegistryError(ValueError):
    """The criteria registry violates its own pre-registered rules."""


class NB03PinError(RuntimeError):
    """The versioned pin is inconsistent or is not reproduced by the recorded inputs."""


class NB03MembershipError(ValueError):
    """A unit membership decision is invalid."""


# --------------------------------------------------------------------------- registry
def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def registry_sha256(path: Path) -> str:
    """sha256 of the registry with CRLF normalised to LF (Windows checkouts)."""
    return _sha256_lf(path)


def load_registry(root: Path) -> dict[str, Any]:
    registry = yaml.safe_load((Path(root) / REGISTRY_PATH).read_text(encoding="utf-8"))
    problems = validate_registry(registry)
    if problems:
        raise NB03RegistryError("; ".join(problems))
    return registry


def validate_registry(registry: dict[str, Any]) -> list[str]:
    """Return every violation of the pre-registered rules (empty list = valid)."""
    for key in ("schema_version", "vocabulary", "evidence_sources", "criteria", "policy", "objective", "amendments"):
        if key not in registry:
            return [f"registry lacks {key!r}"]
    problems: list[str] = []
    vocabulary = registry["vocabulary"]
    for name, expected in (("evidence_categories", EVIDENCE_CATEGORIES), ("roles", ROLES), ("affects", AFFECTS),
                           ("unit_roles", UNIT_ROLES), ("statement_categories", STATEMENT_CATEGORIES)):
        if set(vocabulary.get(name, [])) != set(expected):
            problems.append(f"vocabulary.{name} differs from the code vocabulary")

    sources = {source["id"]: source for source in registry["evidence_sources"]}
    if len(sources) != len(registry["evidence_sources"]):
        problems.append("duplicate evidence source ids")

    by_name: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for criterion in registry["criteria"]:
        label = criterion.get("id", "?")
        missing = [field for field in CRITERION_FIELDS if field not in criterion]
        if missing:
            problems.append(f"{label}: missing fields {missing}")
            continue
        if criterion["id"] in seen_ids or criterion["name"] in by_name:
            problems.append(f"{label}: duplicate id or name")
        seen_ids.add(criterion["id"])
        by_name[criterion["name"]] = criterion
        roles, affects = set(criterion["roles"]), set(criterion["affects"])
        if not roles or not roles <= ROLES:
            problems.append(f"{label}: roles must be a non-empty subset of the vocabulary")
        if not affects <= AFFECTS:
            problems.append(f"{label}: affects outside the vocabulary")
        category, refs = criterion["evidence_category"], criterion["evidence_refs"]
        if category not in EVIDENCE_CATEGORIES:
            problems.append(f"{label}: unknown evidence_category {category!r}")
        if not isinstance(refs, list) or any(ref not in sources for ref in refs):
            problems.append(f"{label}: evidence_refs must be a list of known evidence source ids")
        elif category != "PROJECT_CONVENTION" and not refs:
            problems.append(f"{label}: {category} requires at least one evidence ref")
        threshold = criterion["threshold"]
        if isinstance(threshold, dict) and any(FORBIDDEN_THRESHOLD_KEY.search(str(key)) for key in threshold):
            problems.append(f"{label}: threshold keys suggest a hidden cutoff ({sorted(threshold)})")
        if "HARD_FILTER" in roles and (criterion["name"] not in HARD_FILTERS or affects != {"eligibility"}):
            problems.append(f"{label}: HARD_FILTER is reserved for the three structural criteria and may only affect eligibility")
        if roles == {"DESCRIPTOR"} and not affects <= {"comparison_scope"}:
            problems.append(f"{label}: a pure DESCRIPTOR may not affect ordering, cells or gates")
        if "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW" in roles and (
            criterion["name"] != MANDATORY_REVIEW_CRITERION
            or roles != {"DESCRIPTOR", "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW"} or affects != {"shortlist_gate"}
        ):
            problems.append(f"{label}: only {MANDATORY_REVIEW_CRITERION} may carry the mandatory review, as DESCRIPTOR + review, affecting only shortlist_gate")
    if {n for n, c in by_name.items() if "HARD_FILTER" in c["roles"]} != HARD_FILTERS:
        problems.append(f"the hard filters must be exactly {sorted(HARD_FILTERS)}")
    if MANDATORY_REVIEW_CRITERION not in by_name:
        problems.append(f"{MANDATORY_REVIEW_CRITERION} is missing")
    if {n for n, c in by_name.items() if set(c["affects"]) & ORDERING_AFFECTS} != DECISIONAL_CRITERIA:
        problems.append(f"only {sorted(DECISIONAL_CRITERIA)} may affect the Pareto, the cell signature or the ordering")
    for name in REQUIRED_DESCRIPTORS - set(by_name):
        problems.append(f"descriptor criterion {name} is missing")

    policy = registry["policy"]
    problems.extend(_validate_policy(policy, by_name))
    for amendment in registry["amendments"] or []:
        missing = [key for key in AMENDMENT_FIELDS if key not in amendment]
        if missing:
            problems.append(f"amendment lacks {missing}")
        elif not set(amendment["criteria"]) <= seen_ids:
            problems.append("amendment refers to unknown criteria")
    return problems


def _keys(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


def _validate_policy(policy: dict[str, Any], by_name: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    design = policy.get("design", {})
    if design.get("design_domain") != "CDS_ONLY":
        problems.append("design.design_domain must be CDS_ONLY")
    if design.get("allowed_design_lengths_nt") != {"min": 300, "max": 500}:
        problems.append("design.allowed_design_lengths_nt must be 300-500")
    if (design.get("ranking_length_nt"), design.get("ranking_length_classification"), design.get("ranking_length_is_biological_optimum")) != (
        400, "PROJECT_CONVENTION", False,
    ):
        problems.append("the 400 nt ranking length must be a PROJECT_CONVENTION and not a biological optimum")
    if design.get("sensitivity_lengths_nt") != [300, 500] or design.get("sequence_alphabet") != ["A", "C", "G", "T"]:
        problems.append("design sensitivity lengths and alphabet differ from the pre-registration")
    strata = by_name.get("length_strata", {})
    if strata.get("evidence_category") != "PROJECT_CONVENTION" or (strata.get("threshold") or {}).get("ranking_length_nt") != 400:
        problems.append("length_strata must be a PROJECT_CONVENTION with a 400 nt ranking length")

    if list(policy.get("hard_filters", [])) != ["inside_operational_cds", "length_range", "defined_bases_only"]:
        problems.append("policy.hard_filters must list exactly the three structural filters")
    descriptive = set(policy.get("descriptive_only_criteria", []))
    if not REQUIRED_DESCRIPTORS <= descriptive:
        problems.append(f"policy.descriptive_only_criteria lacks {sorted(REQUIRED_DESCRIPTORS - descriptive)}")
    for name in descriptive:
        criterion = by_name.get(name)
        if criterion is None or set(criterion["roles"]) != {"DESCRIPTOR"} or not set(criterion["affects"]) <= {"comparison_scope"}:
            problems.append(f"{name}: a descriptive-only criterion must be a pure DESCRIPTOR")

    pareto = policy.get("pareto", {})
    expected = {"comparison": "joint", "hierarchy_between_units": False, "direction": "lower_is_better",
                "direction_classification": "PROJECT_CONVENTION", "incomparable_is_tie": True,
                "within_one_length_stratum_only": True}
    if any(pareto.get(key) != value for key, value in expected.items()):
        problems.append("policy.pareto must be a joint, non-hierarchical, lower_is_better PROJECT_CONVENTION with incomparable = tie")
    if tuple(pareto.get("units", ())) != PARETO_UNITS or tuple(pareto.get("axes_per_unit", ())) != PARETO_AXES_PER_UNIT:
        problems.append("policy.pareto must compare exactly BICC_LIKE and DSRNASE2 on the three clipped axes")
    elif pareto.get("n_decisional_axes") != len(PARETO_UNITS) * len(PARETO_AXES_PER_UNIT) or pareto["n_decisional_axes"] != 6:
        problems.append("policy.pareto must have exactly six decisional axes")
    if any(FORBIDDEN_POLICY_KEY.search(key) for key in _keys(pareto)):
        problems.append("policy.pareto may not define weights, scores or sums")
    if not {"sum_across_units", "normalization", "weighting", "composite_score", "hierarchy_between_units", "evalue_axis",
            "hsp_count_axis"} <= set(pareto.get("forbidden_operations", [])):
        problems.append("policy.pareto.forbidden_operations is incomplete")

    obs = policy.get("observed_sequence_differences", {})
    if (obs.get("decisional_metric"), obs.get("direction"), obs.get("hard_exclusion"), obs.get("threshold"), obs.get("applied_after"),
        obs.get("read_support_status"), obs.get("nature_status")) != (
        "count_intersected_observed_sequence_differences", "lower_is_better", False, None, "specificity",
        "NOT_ASSESSED_FOR_NB03_CP0", "UNRESOLVED",
    ):
        problems.append("policy.observed_sequence_differences differs from the pre-registration")
    if obs.get("permitted_interpretation") != "greater robustness to the two currently observed sequences":
        problems.append("policy.observed_sequence_differences.permitted_interpretation must be the approved wording")
    if (obs.get("descriptive_metric"), obs.get("positions_role")) != (
        "intersected_observed_sequence_difference_positions", "DESCRIPTIVE_ONLY",
    ):
        problems.append("intersected observed difference positions must remain DESCRIPTIVE_ONLY")
    if policy.get("cell_signature") != CELL_SIGNATURE:
        problems.append(f"policy.cell_signature must be exactly {CELL_SIGNATURE}")
    if not CELL_SIGNATURE_MUST_EXCLUDE <= set(policy.get("cell_signature_excludes", [])):
        problems.append("policy.cell_signature_excludes lacks required descriptors")

    small = policy.get("small_rna_descriptor", {})
    k_criterion = by_name.get("potential_21nt_derived_windows", {})
    if (small.get("k"), small.get("classification"), small.get("role"), small.get("decisional")) != (21, "OPERATIONAL_ASSUMPTION", "DESCRIPTIVE_ONLY", False) \
            or k_criterion.get("evidence_category") != "OPERATIONAL_ASSUMPTION" or (k_criterion.get("threshold") or {}).get("k") != 21:
        problems.append("k = 21 must be an OPERATIONAL_ASSUMPTION used as a descriptor only")

    benchmark = policy.get("benchmark", {})
    want = {"membership": "REFERENCE_SET", "published_reported_length_nt": 372, "published_reported_length_role": "PUBLISHED_REPORTED_METADATA",
            "operational_sequence_length_nt": 373, "length_discrepancy_nt": 1,
            "length_discrepancy_status": "UNRESOLVED_PUBLICATION_INCONSISTENCY", "counts_as_recommended": False,
            "participates_in_candidate_cells": False, "proximity_influences_ranking": False, "relation_role": "DESCRIPTIVE_ONLY"}
    if any(benchmark.get(key) != value for key, value in want.items()):
        problems.append("policy.benchmark differs from the pre-registration")
    if set(benchmark.get("relation_categories", [])) != BENCHMARK_RELATION_CATEGORIES:
        problems.append("policy.benchmark.relation_categories differ from the pre-registration")
    if tuple(benchmark.get("relation_descriptors", [])) != BENCHMARK_RELATION_DESCRIPTORS or benchmark.get(
        "overlap_fraction_denominators"
    ) != {"overlap_fraction_of_candidate": "candidate_length_nt", "overlap_fraction_of_benchmark": "operational_benchmark_length_nt"}:
        problems.append("benchmark overlap descriptors must use explicit candidate and operational-benchmark denominators")
    comparator = (strata.get("threshold") or {})
    if (comparator.get("benchmark_comparator_length_nt"), comparator.get("benchmark_published_reported_length_nt")) != (373, 372):
        problems.append("length_strata must use the reconstructed 373 nt as comparator and keep 372 as published metadata")
    bounds = policy.get("recommended_candidates", {})
    if (bounds.get("min"), bounds.get("max")) != (2, 4):
        problems.append("recommended candidates must be 2-4")
    review = policy.get("manual_review_decisions", {})
    if tuple(review.get("scopes", ())) != ("OTHER_TRANSCRIPT", "BICC_LIKE", "DSRNASE2") or review.get("required_scope_for_recommendation") != "OTHER_TRANSCRIPT":
        problems.append("manual_review_decisions must define OTHER_TRANSCRIPT, BICC_LIKE and DSRNASE2 and require OTHER_TRANSCRIPT")
    if "max_pairwise_overlap" in policy or "max_pairwise_overlap" in by_name:
        problems.append("a max pairwise overlap must not be pre-registered")
    problems.extend(_validate_units(policy))
    return problems


def _validate_units(policy: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    units = policy.get("specificity_units", {})
    if {name: unit.get("role") for name, unit in units.items()} != UNIT_ROLE_BY_NAME:
        return ["policy.specificity_units must define exactly the six pre-registered units with their roles"]
    owners: dict[str, str] = {}
    for name, unit in units.items():
        members = unit["members"]
        if name == "OTHER_TRANSCRIPT":
            if not isinstance(members, str):
                problems.append("OTHER_TRANSCRIPT membership is the rest of the TSA, not a list")
            continue
        for member in members:
            if member in owners:
                problems.append(f"{member} belongs to both {owners[member]} and {name}")
            owners[member] = name
    if units["BICC_LIKE"]["relationship_status"] != "UNRESOLVED":
        problems.append("BICC_LIKE must keep relationship_status UNRESOLVED")
    if "GITV01000968.1" not in units["KNOWN_BICC_COMPATIBLE"]["members"] or "GITV01002238.1" not in units["BICC_LIKE"]["members"]:
        problems.append("GITV01000968.1 must be KNOWN_BICC_COMPATIBLE and GITV01002238.1 must be BICC_LIKE")
    if any("PARALOG" in str(value).upper() for unit in units.values() for value in (unit["role"], unit["relationship_status"])):
        problems.append("no unit may be labelled PARALOG")
    if policy.get("unit_aggregation", {}).get("pool_across_units") is not False:
        problems.append("units must never be pooled")
    return problems


# --------------------------------------------------------------------------- pin
def load_pin(root: Path) -> dict[str, Any]:
    path = Path(root) / PIN_PATH
    if not path.is_file():
        raise NB03PinError(f"pin missing: {PIN_PATH.as_posix()}")
    pin = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_pin(pin)
    if problems:
        raise NB03PinError("; ".join(problems))
    return pin


def pin_sha256(root: Path) -> str:
    return _sha256_lf(Path(root) / PIN_PATH)


_PIN_KEYS = ("schema_version", "kind", "source", "coordinates", "tsa", "operational_reference", "published_reference",
             "observed_sequence_differences", "benchmark", "cp0_outputs_sha256")
_RECORD_KEYS = ("accession", "record_length", "record_sha256", "strand", "cds_tx_start", "cds_tx_end", "cds_length", "cds_sha256",
                "protein_length", "protein_sha256", "utr5_length", "utr3_length", "iupac_metadata")


def validate_pin(pin: dict[str, Any]) -> list[str]:
    """Offline consistency of the pin: arithmetic, statuses and hash formats. It needs no external file."""
    missing = [key for key in _PIN_KEYS if key not in pin]
    if missing:
        return [f"pin lacks {missing}"]
    problems: list[str] = []
    op = pin["operational_reference"]
    if any(key not in op for key in _RECORD_KEYS):
        return ["pin.operational_reference is incomplete"]
    if op["cds_tx_end"] - op["cds_tx_start"] + 1 != op["cds_length"] or op["cds_length"] != 3 * op["protein_length"] + 3:
        problems.append("operational CDS bounds, length and protein length are inconsistent")
    if op["utr5_length"] + op["cds_length"] + op["utr3_length"] != op["record_length"]:
        problems.append("operational UTR and CDS lengths do not add up to the record length")
    for label, value in (("record", op["record_sha256"]), ("cds", op["cds_sha256"]), ("protein", op["protein_sha256"])):
        if not HEX64.match(value):
            problems.append(f"operational {label} sha256 is not a sha256")

    published = pin["published_reference"]
    if published["transcript_id"] != "TRINITY_DN24799_c0_g1_i7" or "ANTISENSE" not in published["stored_orientation"]:
        problems.append("published reference must be TRINITY_DN24799_c0_g1_i7 stored antisense")
    cds = published["cds_in_sense_orientation"]
    if cds["end"] - cds["start"] + 1 != cds["length"] or published["utr5_length"] + cds["length"] + published["utr3_length"] != published["transcript_length"]:
        problems.append("published transcript, CDS and UTR lengths are inconsistent")
    if cds["length"] != op["cds_length"] or not published["cds_relationship"]["same_length_as_operational_cds"]:
        problems.append("published and operational CDS must have the same length")

    obs = pin["observed_sequence_differences"]
    items = obs["items"]
    if (obs["nature_status"], obs["read_support_status"]) != ("UNRESOLVED", "NOT_ASSESSED_FOR_NB03_CP0") or len(items) != 7:
        problems.append("observed_sequence_differences must be 7 items with nature UNRESOLVED and read support NOT_ASSESSED_FOR_NB03_CP0")
    if any(term in key.lower() for item in items for key in item for term in nb03_reference.FORBIDDEN_NATURE_TERMS):
        problems.append("observed_sequence_differences items may not use fields that name a nature")
    if any(item["read_support_status"] != "NOT_ASSESSED_FOR_NB03_CP0" for item in items):
        problems.append("every observed difference must carry read_support_status NOT_ASSESSED_FOR_NB03_CP0")
    if [item["cds_position"] for item in items] != sorted(item["cds_position"] for item in items) or any(
        not 1 <= item["cds_position"] <= op["cds_length"] for item in items
    ):
        problems.append("observed difference positions must be sorted CDS positions")

    b = pin["benchmark"]
    tail = b["primers"]["partial_t7_tail_5to3"]
    if b["membership"] != "REFERENCE_SET" or b["reference_set_only"] is not True:
        problems.append("the benchmark must be REFERENCE_SET only")
    if b["source"]["primary_source_role"] != "PRIMARY_2022_TABLE_S1" or b["source"]["doi"] != "10.1002/ps.6937" \
            or b["source"]["primary_table_s1_sha256"] != nb03_benchmark.TABLE_S1_2022_SHA256 or b["source"]["raw_file_kept_in_git"] is not False:
        problems.append("benchmark source provenance differs from the primary 2022 Table S1")
    if len(tail) != b["primers"]["partial_t7_tail_length_nt"] or b["primers"]["t7_promoter_full_5to3"][-len(tail):] != tail:
        problems.append("the partial T7 tail is not the 3' end of the T7 promoter")
    for plain, t7 in (("forward", "forward_t7"), ("reverse", "reverse_t7")):
        if b["primers"][t7]["sequence"] != tail + b["primers"][plain]["sequence"]:
            problems.append(f"{t7} is not the tail plus the plain {plain} primer")
    if b["reconstructed_body_length_nt"] != b["body"]["length_nt"] or b["operational_sequence_length_nt"] != b["reconstructed_body_length_nt"]:
        problems.append("the operational benchmark length must be the reconstructed body length")
    if (b["published_reported_body_length_nt"], b["reconstructed_body_length_nt"]) != (372, 373) or b["length_discrepancy_nt"] != 1:
        problems.append("the benchmark must keep published 372 and reconstructed 373 with a discrepancy of 1")
    if b["length_discrepancy_nt"] != b["reconstructed_body_length_nt"] - b["published_reported_body_length_nt"]:
        problems.append("the discrepancy is not reconstructed minus published")
    if b["length_discrepancy_status"] != "UNRESOLVED_PUBLICATION_INCONSISTENCY" or b["length_discrepancy_cause_asserted"] is not False:
        problems.append("the length discrepancy must be UNRESOLVED_PUBLICATION_INCONSISTENCY with no asserted cause")
    if (b["published_reported_t7_amplicon_length_nt"], b["reconstructed_t7_amplicon_length_nt"]) != (402, 403) or \
            b["reconstructed_t7_amplicon_length_nt"] != b["body"]["length_nt"] + 2 * len(tail) or b["amplicon_with_t7_tails"]["length_nt"] != 403:
        problems.append("T7 amplicon lengths must be published 402 and reconstructed 403 = body + two 15 nt tails")
    if b["published_reported_length_role"] != "PUBLISHED_REPORTED_METADATA":
        problems.append("the published length must be PUBLISHED_REPORTED_METADATA")
    if (b["benchmark_sequence_basis"], b["primary_2022_primers_verification"], b["benchmark_sequence_verification"]) != (
        "PRIMARY_2022_PRIMER_DEFINED_RECONSTRUCTION", "VERIFIED_FROM_PRIMARY_2022_TABLE_S1",
        "VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY",
    ):
        problems.append("benchmark sequence basis and verification statuses differ from the approved ones")
    if b["experimental_protocol_verification"] != "PROJECT_PROVIDED_NOT_AGENT_VERIFIED":
        problems.append("the protocol layer may not be promoted by the sequence evidence")
    c = b["coordinates"]["cds_sense"]
    if c["end"] - c["start"] + 1 != b["body"]["length_nt"] or (c["start"], c["end"]) != (215, 587):
        problems.append("benchmark CDS coordinates must be 215-587 and span the body length")
    if b["benchmark_nt_inside_cds"] + b["benchmark_nt_outside_cds"] != b["body"]["length_nt"] or b["benchmark_nt_outside_cds"] != 0:
        problems.append("benchmark inside/outside CDS counts are inconsistent")
    if not HEX64.match(b["body"]["sha256"]):
        problems.append("benchmark body sha256 is not a sha256")
    inside = set(range(c["start"], c["end"] + 1))
    if b["observed_sequence_differences_intersected"] != [i["cds_position"] for i in items if i["cds_position"] in inside]:
        problems.append("the intersected observed differences do not match the benchmark span")
    registered = {k: v for k, v in pin["cp0_outputs_sha256"].items() if k != "note"}
    if not registered or any(not HEX64.match(v) for v in registered.values()):
        problems.append("cp0_outputs_sha256 must register sha256 values")
    return problems


def _table_from_pin(pin: dict[str, Any]) -> dict[str, Any]:
    b = pin["benchmark"]
    return {"bicc_forward": b["primers"]["forward"]["sequence"], "bicc_reverse": b["primers"]["reverse"]["sequence"],
            "reported_lengths_bp": {"bicc_template": b["published_reported_body_length_nt"],
                                    "bicc_with_t7": b["published_reported_t7_amplicon_length_nt"]},
            "source": {"source_role": nb03_benchmark.ROLE_2022, "origin": "pin"}}


def verify_pin(root: Path, workdir: Path) -> dict[str, Any]:
    """Re-derive everything the pin asserts from the TSA, the versioned anchor FASTA and the pinned primers.

    The raw Table S1 file and the gitignored CP0 results are not used. Raises :class:`NB03PinError` on any divergence.
    """
    root = Path(root).resolve()
    pin = load_pin(root)
    derived = nb03_reference.derive_reference(root, workdir, CommandLog())
    bench = nb03_benchmark.reconstruct(derived, _table_from_pin(pin))
    summary, op, pub = derived["summary"], pin["operational_reference"], pin["published_reference"]
    problems: list[str] = []

    def check(label: str, pinned: Any, found: Any) -> None:
        if pinned != found:
            problems.append(f"{label}: pin={pinned!r} derived={found!r}")

    check("tsa sha256", pin["tsa"]["file_sha256"], summary["tsa_file_sha256"])
    for key in _RECORD_KEYS:
        check(f"operational {key}", op[key], summary["operational"][key] if key != "iupac_metadata" else op[key])
    check("operational iupac positions", op["iupac_metadata"]["positions"], summary["operational"]["iupac_positions"])
    check("published stored sha256", pub["stored_sha256"], summary["published"]["stored_sha256"])
    check("published sense sha256", pub["sense_sha256"], summary["published"]["sense_sha256"])
    check("published cds sha256", pub["cds_sha256"], summary["published"]["cds_sha256"])
    check("published orientation", pub["stored_orientation"], summary["published"]["stored_orientation"])
    check("published CDS in sense", [pub["cds_in_sense_orientation"]["start"], pub["cds_in_sense_orientation"]["end"]],
          [summary["published"]["cds_start_in_sense"], summary["published"]["cds_end_in_sense"]])
    check("published span on record", pub["placement_on_operational_record"]["published_transcript_span_on_record"],
          summary["placement_on_operational_record"]["published_transcript_span_on_record"])
    check("observed_sequence_differences", pin["observed_sequence_differences"]["items"], derived["differences"])
    b = pin["benchmark"]
    check("benchmark body sha256", b["body"]["sha256"], bench["body"]["sha256"])
    check("benchmark amplicon sha256", b["amplicon_with_t7_tails"]["sha256"], bench["amplicon_with_t7_tails"]["sha256"])
    check("benchmark coordinates", b["coordinates"], {
        "published_cdna_as_stored": bench["coordinates"]["published_cdna_as_stored"],
        "published_cdna_sense": bench["coordinates"]["published_cdna_sense"],
        "operational_record": {k: v for k, v in bench["coordinates"]["operational_record"].items() if k != "n_body_positions_without_aligned_base"},
        "cds_sense": {"start": bench["coordinates"]["cds_sense"]["start"], "end": bench["coordinates"]["cds_sense"]["end"]},
    })
    check("benchmark observed_sequence_differences_intersected", b["observed_sequence_differences_intersected"],
          bench["observed_sequence_differences_intercepted"])  # CP0 spelled the derived key "intercepted"
    for key in ("benchmark_nt_inside_cds", "benchmark_nt_outside_cds",
                "published_reported_body_length_nt", "reconstructed_body_length_nt", "published_reported_t7_amplicon_length_nt",
                "reconstructed_t7_amplicon_length_nt", "length_discrepancy_nt", "length_discrepancy_status",
                "benchmark_sequence_verification", "primary_2022_primers_verification", "benchmark_sequence_basis"):
        check(f"benchmark {key}", b[key], bench[key])
    if problems:
        raise NB03PinError("the pin is not reproduced by the recorded inputs: " + "; ".join(problems))
    return {"pin_sha256": pin_sha256(root), "tsa_file_sha256": summary["tsa_file_sha256"], "checks": "all pinned values re-derived"}


def validate_registry_against_pin(registry: dict[str, Any], pin: dict[str, Any]) -> list[str]:
    """The registry and the pin must tell the same story about lengths and the CDS."""
    problems: list[str] = []
    policy, strata = registry["policy"], next(c for c in registry["criteria"] if c["name"] == "length_strata")["threshold"]
    cds = next(c for c in registry["criteria"] if c["name"] == "inside_operational_cds")["threshold"]
    b, op = pin["benchmark"], pin["operational_reference"]
    if cds["cds_max"] != op["cds_length"] or cds["cds_min"] != 1:
        problems.append("the registry CDS bounds differ from the pin")
    if strata["benchmark_comparator_length_nt"] != b["operational_sequence_length_nt"]:
        problems.append("the registry benchmark comparator is not the pin's operational sequence length")
    if strata["benchmark_published_reported_length_nt"] != b["published_reported_body_length_nt"]:
        problems.append("the registry published length differs from the pin")
    bench = policy["benchmark"]
    if (bench["published_reported_length_nt"], bench["operational_sequence_length_nt"], bench["length_discrepancy_nt"]) != (
        b["published_reported_body_length_nt"], b["operational_sequence_length_nt"], b["length_discrepancy_nt"],
    ):
        problems.append("policy.benchmark differs from the pin")
    if policy["observed_sequence_differences"]["n_items_in_pin"] != len(pin["observed_sequence_differences"]["items"]):
        problems.append("the number of observed differences differs from the pin")
    return problems


# --------------------------------------------------------------------------- membership decisions
@dataclass(frozen=True)
class MembershipDecision:
    record_id: str
    unit: str
    relationship_status: str
    decision: str
    rationale: str
    evidence_source: str
    evidence_sha256: str
    decided_by: str
    decided_utc: str


def load_membership_decisions(path: Path) -> list[MembershipDecision]:
    """Parse the versioned membership file; every row needs its fields and an evidence sha256."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != MEMBERSHIP_COLUMNS:
            raise NB03MembershipError(f"membership file columns must be {MEMBERSHIP_COLUMNS}")
        rows = []
        for line, row in enumerate(reader, start=2):
            decision = MembershipDecision(**{column: (row[column] or "").strip() for column in MEMBERSHIP_COLUMNS})
            for column in MEMBERSHIP_COLUMNS:
                if not getattr(decision, column):
                    raise NB03MembershipError(f"line {line}: {column} is required")
            if not HEX64.match(decision.evidence_sha256):
                raise NB03MembershipError(f"line {line}: evidence_sha256 must be a sha256")
            if decision.decision != "ACCEPTED" or decision.relationship_status not in RELATIONSHIP_STATUSES:
                raise NB03MembershipError(f"line {line}: decision or relationship_status outside the pre-registered vocabulary")
            if "PARALOG" in {decision.unit.upper(), decision.relationship_status.upper()}:
                raise NB03MembershipError(f"line {line}: PARALOG is not a permitted label at NB03")
            rows.append(decision)
    if len({row.record_id for row in rows}) != len(rows):
        raise NB03MembershipError("a record is decided more than once")
    return rows


def validate_membership(rows: list[MembershipDecision], registry: dict[str, Any], pin: dict[str, Any], root: Path) -> list[str]:
    """Membership must equal the registry units and every evidence hash must be real (a versioned file or a registered CP0 output)."""
    problems: list[str] = []
    units = registry["policy"]["specificity_units"]
    expected = {name: set(unit["members"]) for name, unit in units.items() if name != "OTHER_TRANSCRIPT"}
    found: dict[str, set[str]] = {}
    registered = {k: v for k, v in pin["cp0_outputs_sha256"].items() if k != "note"}
    for row in rows:
        found.setdefault(row.unit, set()).add(row.record_id)
        if row.unit not in expected:
            problems.append(f"{row.record_id}: unknown unit {row.unit}")
            continue
        if row.relationship_status != units[row.unit]["relationship_status"]:
            problems.append(f"{row.record_id}: relationship_status differs from the registry unit")
        versioned = Path(root) / row.evidence_source
        if versioned.is_file():
            if _sha256_lf(versioned) != row.evidence_sha256:
                problems.append(f"{row.record_id}: evidence_sha256 does not match {row.evidence_source}")
        elif registered.get(Path(row.evidence_source).name) != row.evidence_sha256:
            problems.append(f"{row.record_id}: evidence_sha256 is neither a versioned file hash nor a registered CP0 output hash")
    if found != expected:
        problems.append("membership decisions differ from the registry units")
    return problems


def load_validated_membership(root: Path) -> list[MembershipDecision]:
    registry, pin = load_registry(root), load_pin(root)
    rows = load_membership_decisions(Path(root) / MEMBERSHIP_PATH)
    problems = validate_membership(rows, registry, pin, root)
    if problems:
        raise NB03MembershipError("; ".join(problems))
    return rows


# --------------------------------------------------------------------------- policy kernel (data-free)
Vector = tuple[float, float, float]  # longest_exact_match_clipped, covered_nt_clipped, best_local_identity_clipped


@dataclass(frozen=True)
class SpecificityEvidence:
    """Two decisional unit vectors and intersected differences retained for descriptive reporting and counting."""

    candidate_id: str
    length_nt: int
    observed_differences_intersected: frozenset[int]
    bicc_like: Vector
    dsrnase2: Vector

    @property
    def intersected_observed_sequence_difference_positions(self) -> tuple[int, ...]:
        """Sorted positions for descriptive reporting only, outside every decisional comparison."""
        return tuple(sorted(self.observed_differences_intersected))

    @property
    def joint(self) -> tuple[float, ...]:
        """The six decisional axes, in the registry order; never summed or weighted."""
        return (*self.bicc_like, *self.dsrnase2)


def decisive_signature(evidence: SpecificityEvidence) -> tuple[int, Vector, Vector]:
    """Cell signature: the intersected-differences count and the two unit vectors only."""
    return count_intersected(evidence), evidence.bicc_like, evidence.dsrnase2


def compare_specificity(a: SpecificityEvidence, b: SpecificityEvidence) -> str:
    """``A_BETTER``, ``B_BETTER`` or ``TIE`` by joint dominance on the six axes, within one length stratum."""
    if a.length_nt != b.length_nt:
        raise ValueError("specificity is compared only within one length stratum")
    if nb02_criteria.dominates(a.joint, b.joint):
        return "A_BETTER"
    if nb02_criteria.dominates(b.joint, a.joint):
        return "B_BETTER"
    return "TIE"


def count_intersected(evidence: SpecificityEvidence) -> int:
    return len(evidence.observed_differences_intersected)
