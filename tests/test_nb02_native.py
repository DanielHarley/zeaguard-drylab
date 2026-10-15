"""Numerical, provenance and compatibility tests for the isolated NB02 path."""
from dataclasses import replace
import itertools
import json
from pathlib import Path
import shutil

import pytest

from zeaguard import nb02_native as n, nb02_specificity as old, nb02_criteria as criteria
from zeaguard import nb03_specificity as nb03

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy():
    return old.load_policy(criteria.load_registry(ROOT))


def row(btop="17", start=1, subject="GITV01001583.1", minus=False, qlen=40):
    cols = old.btop_columns(btop)
    ident = sum(q == s == "=" for q, s in cols)
    qspan = sum(q != "-" for q, s in cols)
    sspan = sum(s != "-" for q, s in cols)
    mm = sum(q != s and q != "-" and s != "-" for q, s in cols)
    gaps = sum(q == "-" or s == "-" for q, s in cols)
    opens, previous = 0, None
    for q, s in cols:
        kind = "Q" if q == "-" else "S" if s == "-" else None
        opens += kind is not None and kind != previous
        previous = kind
    a, b = (80, 80-sspan+1) if minus else (1, sspan)
    values = ("Q", subject, f"{100*ident/len(cols):.3f}", str(len(cols)), str(qlen), "100",
              str(start), str(start+qspan-1), str(a), str(b), "minus" if minus else "plus",
              "1", "31.9", str(mm), str(opens), str(gaps), "50", btop, "34", str(ident))
    return "\t".join(values)


def parse(text, policy, sequence="A"*40):
    return n.parse_native(text, {"Q": n.Query("Q", sequence, "DESIGN_SPACE", 1, len(sequence))}, policy)


@pytest.mark.parametrize("minus", [False, True])
def test_btop_orientations_and_both_gap_types(policy, minus):
    h = parse(row("5A-3-A2", minus=minus), policy)[0]
    ev = n.unit_evidence([h])
    assert h.native.raw.length == 12 and h.query_span == 11
    assert ev["best_local_identity"] == 10/12
    assert ev["covered_nt"] == 11 and ev["longest_exact_match"] == 5
    assert ev["alignment_columns_for_best_identity"] == 12
    assert ev["identical_columns_for_best_identity"] == 10


def test_real_boundary_formula_from_btop_without_real_search(policy):
    btop = "2AT2GC12CT1TA3TC1GCAT3GA1TG2GA5"
    sequence = "".join("A" if q == "=" else q for q,s in old.btop_columns(btop) if q != "-")
    hsps = parse(row(btop, qlen=len(sequence)), policy, sequence)
    assert n.unit_evidence(hsps)["best_local_identity"] == 32/42


def test_identity_does_not_use_reported_percent_as_numerator(policy):
    h = parse(row("3AC3"), policy)[0]
    assert n.unit_evidence([h])["best_local_identity"] == 6/7
    assert n.persisted(n.unit_evidence([h]))["best_local_identity"] == "0.857143"


@pytest.mark.parametrize("field,value", [("qlen","41"),("qend","41"),("sstart","0"),
    ("send","101"),("sstrand","minus"),("nident","16"),("mismatch","1"),
    ("gaps","1"),("gapopen","1"),("pident","nan"),("score","nan"),("qseqid","UNKNOWN")])
def test_rejects_invalid_geometry_counts_or_identity(policy, field, value):
    fields = dict(zip(n.FIELDS, row().split("\t")))
    fields[field] = value
    with pytest.raises((n.NativeError, nb03.NB03SpecificityError)):
        parse("\t".join(fields[k] for k in n.FIELDS), policy)


@pytest.mark.parametrize("btop", ["bogus", "5--12", "999", "1AC"])
def test_rejects_malformed_btop_or_span(policy, btop):
    fields = dict(zip(n.FIELDS, row().split("\t")))
    fields["btop"] = btop
    with pytest.raises((n.NativeError, nb03.NB03SpecificityError)):
        parse("\t".join(fields[k] for k in n.FIELDS), policy)


def test_coverage_is_union_across_redundant_subjects_and_orientations(policy):
    text = "\n".join([row("17"), row("17"), row("17", start=10, subject="GITV01002042.1", minus=True)])
    ev = n.unit_evidence(parse(text, policy))
    assert ev["covered_nt"] == 26
    assert ev["n_hsps"] == 3 and ev["n_subject_records"] == 2
    assert ev["longest_exact_match"] == 17


def test_descriptors_are_independently_aggregated(policy):
    ev = n.unit_evidence(parse(row("9AC10") + "\n" + row("4", start=5, subject="GITV01002042.1"), policy))
    assert ev["covered_nt"] == 20 and ev["longest_exact_match"] == 10
    assert ev["best_local_identity"] == 1 and ev["query_span_for_best_identity"] == 4


def test_legacy_query_span_tie_break_and_input_order_independence(policy):
    hsps = parse(row("3AC3AC", subject="GITV01002042.1") + "\n" + row("3-A-A3"), policy)
    for perm in itertools.permutations(hsps):
        ev = n.unit_evidence(list(perm))
        assert ev["best_local_identity"] == .75
        assert "GITV01002042.1" in ev["best_identity_hsp_id"]
        assert ev["query_span_for_best_identity"] == 8


def test_legacy_identifier_tie_break(policy):
    hsps = parse(row("17", subject="GITV01002042.1") + "\n" + row("17"), policy)
    assert "GITV01001583.1" in n.unit_evidence(hsps)["best_identity_hsp_id"]


def test_units_and_queries_cannot_be_pooled(policy):
    a = parse(row(), policy)[0]
    with pytest.raises(n.NativeError, match="pool"):
        n.unit_evidence([a, replace(a, native=replace(a.native, unit="BICC"))])
    with pytest.raises(n.NativeError, match="pool"):
        n.unit_evidence([a, replace(a, native=replace(a.native, raw=replace(a.native.raw, query="OTHER")))])


def test_no_reported_hsp_is_an_explicit_successful_search_state(policy):
    assert parse("", policy) == []
    ev = n.unit_evidence([])
    assert (ev["longest_exact_match"], ev["covered_nt"], ev["best_local_identity"]) == (0,0,0.0)
    assert ev["evidence_status"] == n.NO_HSP
    assert ev["best_identity_hsp_id"] == ""


def decision_fixture(identity):
    row = {"query_id":"Q1", "membership":"DESIGN_SPACE", "specificity_evidence_basis":n.BASIS}
    for unit in n.DECISIONAL:
        row.update({f"{unit.lower()}_{m}": "0.000000" if m == "best_local_identity" else "0" for m in n.AXES})
    row["dsrnase1_best_local_identity"] = identity
    d = {"length_nt":"400", "length_stratum":"RANKING_L400", "cds_start":"1", "cds_end":"400", "variant_positions":"", "n_variant_sites":"0"}
    return row, d


def test_six_decimal_persisted_boundary_drives_equality_pareto_and_signature():
    a,d = decision_fixture(f"{.1234564:.6f}")
    b,e = decision_fixture(f"{.12345649:.6f}")
    b["query_id"]="Q2"
    e.update(cds_start="2", cds_end="401")
    cs, assignments = n.build_native_cells([a,b], {"Q1":d,"Q2":e})
    assert len(cs) == 1 and cs[0]["n_windows"] == 2 and cs[0]["in_pareto_front"]
    assert assignments["Q1"] is assignments["Q2"]
    a["dsrnase1_best_local_identity"] = .1234564
    with pytest.raises(n.NativeError, match="persisted"):
        n.build_native_cells([a], {"Q1":d})


def test_cp4_rejects_non_native_basis():
    r,d = decision_fixture("0.000000")
    r["specificity_evidence_basis"] = "FULL_CDS_CLIPPED_ALIGNMENT_DIAGNOSTIC"
    with pytest.raises(n.NativeError, match="non-native"):
        n.build_native_cells([r], {"Q1":d})


def test_quantity_and_review_gates_are_separate_and_benchmark_does_not_count():
    bounds = {"min":2,"max":4}
    s = n.closure_status(["A"],["A"],True,bounds)
    assert s["human_review_complete"] and not s["closed"] and not s["quantity_gate_satisfied"]
    assert n.closure_status(["A","B"],["A","B"],True,bounds)["closed"]
    assert not n.closure_status(["A","B"],["A","B"],False,bounds)["closed"]
    for ids in (["D2-BENCH-0814-1143"],["A","A"]):
        with pytest.raises(n.NativeError):
            n.closure_status(ids,[],False,bounds)
    with pytest.raises(n.NativeError):
        n.closure_status(["A"],["A"],True,{"min":1,"max":4})


def test_output_guard_cannot_write_into_legacy_or_inputs(tmp_path):
    for relative in (".", "src", "config/new", "data/new", "results/bioinformatics/nb02/cp3/new"):
        with pytest.raises(n.NativeError):
            n.fresh_output(tmp_path, tmp_path / relative)
    out = n.fresh_output(tmp_path, tmp_path / "new")
    (out / "existing").write_text("preserve")
    with pytest.raises(n.NativeError, match="already"):
        n.fresh_output(tmp_path, out)


def test_shared_nb03_arguments_unchanged_and_scoring_is_native_only(policy):
    original = old.blastn_arguments(policy.search)
    native = n.blast_arguments(policy.search)
    assert native == original + ["-reward","2","-penalty","-3","-gapopen","5","-gapextend","2"]
    assert old.blastn_arguments(policy.search) == original
    assert "-searchsp" not in native and "-max_hsps" not in native
    assert n.FIELDS[:18] == tuple(n.BLAST_OUTFMT_FIELDS)


@pytest.mark.skipif(not (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").exists(), reason="requires local certified inputs")
def test_queries_match_every_certified_cp2_identity_and_reference():
    queries, ref, registry, inputs = n.load_queries(ROOT)
    assert len(queries) == 4175 and len({q.identifier for q in queries}) == 4175
    assert sum(q.membership == "REFERENCE_SET" for q in queries) == 1
    assert all(n.sequence_hash(q.sequence) for q in queries)
    assert queries[-1].length == 330
    assert registry["policy"]["recommended_candidates"] == {"min":2,"max":4}


def test_artifact_integrity_failure_cannot_be_read_as_no_hsp(tmp_path):
    p=tmp_path/"raw.tsv"
    p.write_text("")
    m={"outputs_sha256":{"raw.tsv":n.digest(p)}}
    p.write_text("truncated or altered")
    with pytest.raises(n.NativeError,match="integrity"):
        n.verify_outputs(tmp_path,m)


def test_failed_search_cannot_publish_complete_or_zero_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(n, "load_queries", lambda root: ([], {}, {}, {}))
    monkeypatch.setattr(old, "load_policy", lambda registry: None)
    def failed(log):
        raise RuntimeError("search process failed")
    monkeypatch.setattr(old, "blast_version", failed)
    out=tmp_path/"native"
    with pytest.raises(RuntimeError,match="search process failed"):
        n.run_cp3(tmp_path,out)
    assert json.loads((out/"execution_status.json").read_text())["status"] == "FAILED"
    assert not (out/"run_manifest.json").exists()
    assert not (out/"vectors.tsv").exists()


@pytest.mark.skipif(not (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").exists(), reason="requires local certified inputs")
@pytest.mark.parametrize("mutation", ["sequence", "identifier"])
def test_semantic_query_integrity_is_stricter_than_manifest_hashes(tmp_path, monkeypatch, mutation):
    queries, ref, registry, inputs = n.load_queries(ROOT)
    monkeypatch.setattr(n.reference,"verified_reference",lambda root:ref)
    monkeypatch.setattr(n.criteria,"load_registry",lambda root:registry)
    for relative in [n.criteria.REGISTRY_PATH, n.reference.PIN_PATH]:
        dst=tmp_path/relative
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,dst)
    shutil.copytree(ROOT/n.CP2,tmp_path/n.CP2,ignore=shutil.ignore_patterns("cp3","cp4","cp5","native_v1"))
    path=tmp_path/n.CP2/"strata_windows.tsv"
    rows=n.read_tsv(path)
    rows[0]["sequence_sha256" if mutation == "sequence" else "candidate_id"]="0"*64
    n.write_tsv(path,rows)
    mp=tmp_path/n.CP2/"run_manifest.json"
    m=json.loads(mp.read_text())
    m["outputs_sha256"][path.name]=n.digest(path,True)
    n.write_json(mp,m)
    with pytest.raises(n.NativeError,match="query"):
        n.load_queries(tmp_path)
