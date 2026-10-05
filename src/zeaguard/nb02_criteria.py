"""NB02 criteria registry and the policy kernel it pre-registers.

Two things live here and nothing else: (1) the validation of ``config/nb02_design_criteria.yaml``
(vocabulary, evidence categories, roles, what each criterion may influence) and (2) a tiny,
data-free policy kernel (cell signature, Pareto dominance within one length stratum, and the
versioned manual-review gate). The kernel takes explicit values, so the rules the registry freezes
are testable before any candidate window exists.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

import yaml

REGISTRY_PATH = Path("config/nb02_design_criteria.yaml")
REVIEW_DECISIONS_PATH = Path("config/nb02_manual_review_decisions.tsv")

EVIDENCE_CATEGORIES = frozenset(
    {"EVIDENCE_BACKED", "TOOL_DERIVED", "PROJECT_CONVENTION", "OPERATIONAL_ASSUMPTION"}
)
ROLES = frozenset(
    {
        "HARD_FILTER",
        "SOFT_PREFERENCE",
        "DESCRIPTOR",
        "TIE_BREAKER",
        "MANUAL_REVIEW_TRIGGER",
        "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW",
    }
)
AFFECTS = frozenset(
    {"eligibility", "comparison_scope", "pareto", "cell_signature", "primary_ordering", "shortlist_gate"}
)
SCOPES = ("OTHER_TRANSCRIPT", "PARALOG", "CO_TARGET")
DECISIONS_BY_SCOPE = {
    "OTHER_TRANSCRIPT": frozenset({"APPROVED", "STRONG_INTRASPECIES_SPECIFICITY_CONCERN"}),
    "PARALOG": frozenset({"APPROVED", "STRONG_SPECIFICITY_CONCERN"}),
    "CO_TARGET": frozenset({"APPROVED", "STRONG_SPECIFICITY_CONCERN"}),
}
CONCERN_DECISIONS = frozenset({"STRONG_INTRASPECIES_SPECIFICITY_CONCERN", "STRONG_SPECIFICITY_CONCERN"})
DECISION_COLUMNS = ("candidate_id", "scope", "decision", "justification", "reviewer", "decided_utc", "evidence_sha256")

STRUCTURAL_HARD_FILTERS = frozenset(
    {"inside_operational_cds", "length_range", "min_length_floor", "defined_bases_only"}
)
CELL_SIGNATURE = ["variants_intercepted", "paralog_vector_clipped", "co_target_vector_clipped"]
CRITERION_FIELDS = (
    "id", "name", "definition", "origin", "evidence_category", "roles", "affects", "threshold",
    "justification", "limitations", "revision_condition", "evidence_refs",
)
FORBIDDEN_THRESHOLD_KEY = re.compile(r"(overlap|kmer|k_mer|mer_cutoff|evalue_cutoff|e_value_cutoff|cutoff)", re.I)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class NB02RegistryError(ValueError):
    """The criteria registry violates its own pre-registered rules."""


class NB02ReviewError(ValueError):
    """A manual-review decision is invalid, or a recommendation lacks the required review."""


# --------------------------------------------------------------------------- registry
def registry_sha256(path: Path) -> str:
    """sha256 of the registry with CRLF normalised to LF (Windows checkouts)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_registry(root: Path) -> dict[str, Any]:
    path = Path(root) / REGISTRY_PATH
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = validate_registry(registry)
    if problems:
        raise NB02RegistryError("; ".join(problems))
    return registry


def validate_registry(registry: dict[str, Any]) -> list[str]:
    """Return every violation of the pre-registered rules (empty list = valid)."""
    problems: list[str] = []
    for key in ("schema_version", "vocabulary", "evidence_sources", "criteria", "policy", "objective"):
        if key not in registry:
            return [f"registry lacks {key!r}"]

    vocabulary = registry["vocabulary"]
    for name, expected in (
        ("evidence_categories", EVIDENCE_CATEGORIES),
        ("roles", ROLES),
        ("affects", AFFECTS),
    ):
        if set(vocabulary.get(name, [])) != set(expected):
            problems.append(f"vocabulary.{name} differs from the code vocabulary")

    sources = {source["id"]: source for source in registry["evidence_sources"]}
    if len(sources) != len(registry["evidence_sources"]):
        problems.append("duplicate evidence source ids")

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    mandatory: list[str] = []
    for criterion in registry["criteria"]:
        label = criterion.get("id", "?")
        missing = [field for field in CRITERION_FIELDS if field not in criterion]
        if missing:
            problems.append(f"{label}: missing fields {missing}")
            continue
        if criterion["id"] in seen_ids or criterion["name"] in seen_names:
            problems.append(f"{label}: duplicate id or name")
        seen_ids.add(criterion["id"])
        seen_names.add(criterion["name"])
        roles, affects = set(criterion["roles"]), set(criterion["affects"])
        if not roles or not roles <= ROLES:
            problems.append(f"{label}: roles must be a non-empty subset of the vocabulary")
        if not affects <= AFFECTS:
            problems.append(f"{label}: affects outside the vocabulary")
        category = criterion["evidence_category"]
        if category not in EVIDENCE_CATEGORIES:
            problems.append(f"{label}: unknown evidence_category {category!r}")
        refs = criterion["evidence_refs"]
        if not isinstance(refs, list) or any(ref not in sources for ref in refs):
            problems.append(f"{label}: evidence_refs must be a list of known evidence source ids")
        elif category != "PROJECT_CONVENTION" and not refs:
            problems.append(f"{label}: {category} requires at least one evidence ref")
        threshold = criterion["threshold"]
        if isinstance(threshold, dict) and any(FORBIDDEN_THRESHOLD_KEY.search(str(key)) for key in threshold):
            problems.append(f"{label}: threshold keys suggest a hidden cutoff ({sorted(threshold)})")
        if "HARD_FILTER" in roles:
            if criterion["name"] not in STRUCTURAL_HARD_FILTERS:
                problems.append(f"{label}: HARD_FILTER is reserved for structural criteria")
            if affects != {"eligibility"}:
                problems.append(f"{label}: a HARD_FILTER may only affect eligibility")
        if roles == {"DESCRIPTOR"} and not affects <= {"comparison_scope"}:
            problems.append(f"{label}: a pure DESCRIPTOR may not affect ordering, cells or gates")
        if "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW" in roles:
            mandatory.append(criterion["name"])
            if roles != {"DESCRIPTOR", "MANDATORY_PRE_RECOMMENDATION_MANUAL_REVIEW"} or affects != {"shortlist_gate"}:
                problems.append(f"{label}: the mandatory-review criterion must be DESCRIPTOR + mandatory review and affect only shortlist_gate")
        if criterion["name"] == "target_region_position" and (roles != {"DESCRIPTOR"} or affects):
            problems.append(f"{label}: position must be a pure DESCRIPTOR that affects nothing")
    if mandatory != ["other_transcript_specificity"]:
        problems.append(f"exactly other_transcript_specificity must carry the mandatory review role, got {mandatory}")

    policy = registry["policy"]
    if policy.get("cell_signature") != CELL_SIGNATURE:
        problems.append(f"policy.cell_signature must be exactly {CELL_SIGNATURE}")
    excluded = set(policy.get("cell_signature_excludes", []))
    if not {"target_region_position", "other_transcript_hits"} <= excluded:
        problems.append("policy.cell_signature_excludes must list target_region_position and other_transcript_hits")
    bounds = policy.get("recommended_candidates", {})
    if (bounds.get("min"), bounds.get("max")) != (2, 4) or policy.get("benchmark_counts_as_recommended") is not False:
        problems.append("recommended candidates must be 2-4 and the benchmark must not count as recommended")
    review = policy.get("manual_review_decisions", {})
    if tuple(review.get("scopes", ())) != SCOPES or review.get("required_scope_for_recommendation") != "OTHER_TRANSCRIPT":
        problems.append("manual_review_decisions must define the three scopes and require OTHER_TRANSCRIPT")
    if tuple(review.get("columns", ())) != DECISION_COLUMNS:
        problems.append("manual_review_decisions columns differ from the code schema")
    if {key: set(value) for key, value in review.get("decisions", {}).items()} != {
        key: set(value) for key, value in DECISIONS_BY_SCOPE.items()
    }:
        problems.append("manual_review_decisions decision vocabulary differs from the code schema")
    if "max_pairwise_overlap" in policy or "max_pairwise_overlap" in {c.get("name") for c in registry["criteria"]}:
        problems.append("a max pairwise overlap must not be pre-registered")
    return problems


# --------------------------------------------------------------------------- manual-review decisions
@dataclass(frozen=True)
class ReviewDecision:
    candidate_id: str
    scope: str
    decision: str
    justification: str
    reviewer: str
    decided_utc: str
    evidence_sha256: str


def load_review_decisions(path: Path) -> dict[tuple[str, str], ReviewDecision]:
    """Parse and validate the versioned decision file; the header-only file is valid (no decisions yet)."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != DECISION_COLUMNS:
            raise NB02ReviewError(f"decision file columns must be {DECISION_COLUMNS}")
        decisions: dict[tuple[str, str], ReviewDecision] = {}
        for line, row in enumerate(reader, start=2):
            decision = ReviewDecision(**{column: (row[column] or "").strip() for column in DECISION_COLUMNS})
            _validate_decision(decision, line)
            key = (decision.candidate_id, decision.scope)
            if key in decisions:
                raise NB02ReviewError(f"line {line}: duplicate decision for {key}")
            decisions[key] = decision
    return decisions


def _validate_decision(decision: ReviewDecision, line: int) -> None:
    where = f"line {line}"
    for column in ("candidate_id", "reviewer", "decided_utc"):
        if not getattr(decision, column):
            raise NB02ReviewError(f"{where}: {column} is required")
    if decision.scope not in DECISIONS_BY_SCOPE:
        raise NB02ReviewError(f"{where}: unknown scope {decision.scope!r}")
    if decision.decision not in DECISIONS_BY_SCOPE[decision.scope]:
        raise NB02ReviewError(f"{where}: decision {decision.decision!r} is not valid for scope {decision.scope}")
    if not HEX64.match(decision.evidence_sha256):
        raise NB02ReviewError(f"{where}: evidence_sha256 must be the sha256 of the reviewed hit table")
    if decision.decision in CONCERN_DECISIONS and not decision.justification:
        raise NB02ReviewError(f"{where}: a concern decision requires a justification")


def recommendation_status(
    candidate_id: str,
    decisions: dict[tuple[str, str], ReviewDecision],
    required_scopes: Sequence[str] = ("OTHER_TRANSCRIPT",),
) -> str:
    """``EXCLUDED_AFTER_REVIEW``, ``PENDING_REVIEW`` or ``RECOMMENDABLE``.

    A concern decision in any scope excludes the candidate. Without an APPROVED decision in every
    required scope (OTHER_TRANSCRIPT always; PARALOG / CO_TARGET when they raised a trigger) the
    candidate stays pending and cannot be recommended.
    """
    own = {scope: decisions[(candidate_id, scope)] for scope in SCOPES if (candidate_id, scope) in decisions}
    if any(decision.decision in CONCERN_DECISIONS for decision in own.values()):
        return "EXCLUDED_AFTER_REVIEW"
    if all(scope in own and own[scope].decision == "APPROVED" for scope in set(required_scopes) | {"OTHER_TRANSCRIPT"}):
        return "RECOMMENDABLE"
    return "PENDING_REVIEW"


def assert_can_recommend(
    candidate_id: str,
    decisions: dict[tuple[str, str], ReviewDecision],
    required_scopes: Sequence[str] = ("OTHER_TRANSCRIPT",),
) -> None:
    status = recommendation_status(candidate_id, decisions, required_scopes)
    if status != "RECOMMENDABLE":
        raise NB02ReviewError(f"{candidate_id} cannot be RECOMMENDED_SHORTLIST: {status}")


# --------------------------------------------------------------------------- policy kernel
Vector = tuple[float, float, float]  # longest_exact_match_clipped, covered_nt_clipped, local_identity_clipped


@dataclass(frozen=True)
class SpecificityEvidence:
    """Decisive evidence of one candidate; ``other_transcript_hits`` is carried but never used to decide."""

    candidate_id: str
    length_nt: int
    variants_intercepted: frozenset[int]
    paralog: Vector
    co_target: Vector
    other_transcript_hits: tuple[dict[str, Any], ...] = ()


def decisive_signature(evidence: SpecificityEvidence) -> tuple[tuple[int, ...], Vector, Vector]:
    """Cell signature: variants intercepted + PARALOG vector + CO_TARGET vector (nothing else)."""
    return (tuple(sorted(evidence.variants_intercepted)), evidence.paralog, evidence.co_target)


def dominates(a: Iterable[float], b: Iterable[float]) -> bool:
    """Pareto dominance, lower is better on every axis: no worse everywhere and strictly better somewhere."""
    left, right = tuple(a), tuple(b)
    return all(x <= y for x, y in zip(left, right)) and any(x < y for x, y in zip(left, right))


def compare_specificity(a: SpecificityEvidence, b: SpecificityEvidence) -> str:
    """``A_BETTER``, ``B_BETTER`` or ``TIE`` within one length stratum; PARALOG first, then CO_TARGET.

    Equal vectors defer to the next group; incomparable vectors are a tie (no weights are invented).
    Comparing different lengths is refused: no normalisation is neutral across lengths.
    """
    if a.length_nt != b.length_nt:
        raise ValueError("specificity is compared only within one length stratum")
    for left, right in ((a.paralog, b.paralog), (a.co_target, b.co_target)):
        if left == right:
            continue
        if dominates(left, right):
            return "A_BETTER"
        if dominates(right, left):
            return "B_BETTER"
        return "TIE"
    return "TIE"
