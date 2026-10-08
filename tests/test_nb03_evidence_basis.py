from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from zeaguard import nb02_specificity as old, nb03_criteria as criteria

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/nb03_clipping_non_equivalence"


def test_preserved_diagnostic_inputs_match_the_original_recorded_hashes():
    report = json.loads((FIXTURE / "clipping_equivalence_report.json").read_text(encoding="utf-8"))
    for name, expected in report["file_sha256"].items():
        # The original experiment wrote LF; normalize Windows checkout newlines to that original representation.
        data = (FIXTURE / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == expected
    assert report["same_three_metrics"] is False


def test_native_evidence_is_canonical_when_fixed_full_cds_hsp_clipping_diverges():
    full = old.parse_hsp_table((FIXTURE / "full_query_blast.outfmt6.tsv").read_text(encoding="utf-8"))
    native = old.parse_hsp_table((FIXTURE / "window_query_blast.outfmt6.tsv").read_text(encoding="utf-8"))
    diagnostic = old.unit_evidence([old.footprint(h, "SYNTHETIC") for h in full], 501, 900)
    canonical = old.unit_evidence([old.footprint(h, "SYNTHETIC") for h in native], 1, 400)
    # Possible non-equivalence is the invariant; the difference is not constrained to a biological constant.
    assert diagnostic["covered_nt_clipped"] != canonical["covered_nt_clipped"]
    native_vector = old.vector(canonical)
    native_evidence = criteria.SpecificityEvidence("synthetic", 400, frozenset(), native_vector,
                                                  (0, 0, 0), criteria.CANONICAL_EVIDENCE_BASIS)
    assert criteria.decisive_signature(native_evidence)[1] == native_vector
    diagnostic_evidence = replace(native_evidence, bicc_like=old.vector(diagnostic),
                                  specificity_evidence_basis=criteria.DIAGNOSTIC_EVIDENCE_BASIS)
    with pytest.raises(criteria.NB03EvidenceBasisError):
        criteria.decisive_signature(diagnostic_evidence)
    with pytest.raises(criteria.NB03EvidenceBasisError):
        _ = diagnostic_evidence.joint


@pytest.mark.parametrize("basis", [criteria.DIAGNOSTIC_EVIDENCE_BASIS, "UNDECLARED", "", None])
def test_decisive_signature_and_axes_reject_non_native_or_undeclared_provenance(basis):
    evidence = criteria.SpecificityEvidence("synthetic", 400, frozenset(), (1, 2, 3), (4, 5, 6), basis)
    with pytest.raises(criteria.NB03EvidenceBasisError):
        criteria.decisive_signature(evidence)
    with pytest.raises(criteria.NB03EvidenceBasisError):
        _ = evidence.joint


def test_specificity_evidence_requires_an_explicit_basis():
    with pytest.raises(TypeError):
        criteria.SpecificityEvidence("synthetic", 400, frozenset(), (1, 2, 3), (4, 5, 6))


def test_registry_requires_native_basis_and_diagnostic_only_clipping():
    import copy

    registry = criteria.load_registry(ROOT)
    assert registry["policy"]["specificity_evidence_basis"] == criteria.CANONICAL_EVIDENCE_BASIS
    assert registry["policy"]["shuffled_control_query_unit"] == "EACH_CANDIDATE_SEQUENCE"
    diagnostic = next(c for c in registry["criteria"] if c["name"] == "full_cds_clipped_alignment_diagnostic")
    assert diagnostic["roles"] == ["DESCRIPTOR"] and diagnostic["affects"] == []
    for mutation in (
        lambda r: r["policy"].update(specificity_evidence_basis=criteria.DIAGNOSTIC_EVIDENCE_BASIS),
        lambda r: r["policy"].update(shuffled_control_query_unit="FULL_CDS"),
        lambda r: r["policy"]["full_cds_clipped_alignment_diagnostic"].update(enters_decisive_signature=True),
        lambda r: r["policy"]["unit_aggregation"].update(candidate_native_hsps_only=False),
        lambda r: r["policy"]["pareto"].update(axes_per_unit=["longest_exact_match_clipped", "covered_nt_clipped", "best_local_identity_clipped"]),
    ):
        changed = copy.deepcopy(registry)
        mutation(changed)
        assert criteria.validate_registry(changed)
