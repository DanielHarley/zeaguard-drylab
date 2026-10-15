"""Isolated NB02 candidate-native specificity and persisted CP4 workflow.

Historical NB02/NB03 modules and registry remain unchanged. Native evidence uses
the original units, hierarchy, query-span tie break and six-decimal CP3 boundary.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

from zeaguard import nb01_identity, nb02_cells as cells, nb02_criteria as criteria
from zeaguard import nb02_design as design, nb02_reference as reference, nb02_specificity as legacy
from zeaguard.nb01_dsrnase_investigation import BLAST_OUTFMT_FIELDS, CommandLog, parse_hsp_table, union_length, write_tsv
from zeaguard.nb03_specificity import Query, NativeHsp, native_hsp

BASIS = "CANDIDATE_NATIVE_ALIGNMENT"
NO_HSP = "NO_REPORTED_HSP_UNDER_CONFIGURED_SEARCH"
FIELDS = (*BLAST_OUTFMT_FIELDS, "score", "nident")
DECISIONAL = ("DSRNASE1", "DSRNASE3", "BICC")
UNITS = (*DECISIONAL, legacy.KNOWN, legacy.OTHER)
AXES = ("longest_exact_match", "covered_nt", "best_local_identity")
DATABASE_SHA256 = "ea236b31337549262969fdadd54fcce2ae1bb7bceef14e5ee51c95d952c63d4b"
OUTPUT = Path("results/bioinformatics/nb02/native_v1")
CP2 = Path("results/bioinformatics/nb02")


class NativeError(RuntimeError):
    """Invalid, incomplete or incompatible native evidence."""


def digest(path: Path, normalized: bool = False) -> str:
    payload = path.read_bytes()
    return hashlib.sha256(payload.replace(b"\r\n", b"\n") if normalized else payload).hexdigest()


def sequence_hash(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def blast_arguments(search: dict) -> list[str]:
    """Add explicit scoring only to NB02 native calls, preserving shared defaults."""
    return [*legacy.blastn_arguments(search), "-reward", "2", "-penalty", "-3",
            "-gapopen", "5", "-gapextend", "2"]


def verify_outputs(directory: Path, manifest: dict) -> None:
    for name, expected in manifest["outputs_sha256"].items():
        path = directory / name
        if not path.is_file() or digest(path) != expected:
            raise NativeError(f"artifact integrity mismatch: {path}")


def load_queries(root: Path) -> tuple[list[Query], dict, dict, dict[str, str]]:
    """Consume certified CP2, never diagnostic outputs or historical CP3 metrics."""
    registry = criteria.load_registry(root)
    ref = reference.verified_reference(root)
    cds = ref["operational_cds"]
    mpath = root / CP2 / "run_manifest.json"
    manifest = json.loads(mpath.read_text())
    if manifest["inputs"]["operational_cds_sha256"] != sequence_hash(cds):
        raise NativeError("CP2 operational CDS hash mismatch")
    if manifest["inputs"]["pin_sha256"] != ref["report"]["pin_sha256_lf"]:
        raise NativeError("CP2 reference pin mismatch")
    inputs = {str(CP2 / "run_manifest.json"): digest(mpath),
              str(criteria.REGISTRY_PATH): digest(root / criteria.REGISTRY_PATH),
              "data/reference/nb01_dsrnase2_operational_reference.json": digest(root / reference.PIN_PATH)}
    for name, expected in manifest["outputs_sha256"].items():
        path = root / CP2 / name
        if digest(path, normalized=True) != expected:
            raise NativeError(f"CP2 artifact integrity mismatch: {name}")
        inputs[str(CP2 / name)] = digest(path)
    parameters = design.design_parameters(registry)
    descriptors = read_tsv(root / CP2 / "strata_windows.tsv")
    expected = {design.window_id(length, start, start + length - 1): (start, start + length - 1, label)
                for length, label in parameters.strata.items()
                for start in design.windows_of_length(len(cds), length)}
    if len(descriptors) != len(expected) or {r["candidate_id"] for r in descriptors} != set(expected):
        raise NativeError("CP2 exact query identifiers differ from the declared design space")
    queries = []
    for row in descriptors:
        qid = row["candidate_id"]
        start, end, label = expected[qid]
        sequence = cds[start - 1:end]
        if (int(row["cds_start"]), int(row["cds_end"]), row["length_stratum"]) != (start, end, label):
            raise NativeError(f"CP2 query coordinates/stratum mismatch: {qid}")
        if int(row["length_nt"]) != len(sequence) or row["sequence_sha256"] != sequence_hash(sequence):
            raise NativeError(f"CP2 query sequence hash/length mismatch: {qid}")
        queries.append(Query(qid, sequence, "DESIGN_SPACE", start, end))
    pin = ref["pin"]["benchmark"]
    span = pin["interval"]
    benchmark = cds[span["cds_start"] - 1:span["cds_end"]]
    if sequence_hash(benchmark) != span["sequence_sha256"]:
        raise NativeError("benchmark sequence hash mismatch")
    queries.append(Query(pin["id"], benchmark, "REFERENCE_SET", span["cds_start"], span["cds_end"]))
    return queries, ref, registry, inputs


@dataclass(frozen=True)
class ObservedHsp:
    native: NativeHsp
    fields: dict[str, str]
    line: int

    @property
    def identity(self) -> float:
        return self.native.identical_columns / self.native.raw.length

    @property
    def query_span(self) -> int:
        return self.native.raw.qend - self.native.raw.qstart + 1

    @property
    def identifier(self) -> str:
        return legacy.hsp_identifier(self.native.raw)


def parse_native(text: str, queries: dict[str, Query], policy: legacy.Policy) -> list[ObservedHsp]:
    """Reuse pure NB03 BTOP validation, without its policy, runner or tie break."""
    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip() and not line.startswith("#")]
    parsed = parse_hsp_table(text, FIELDS)
    result = []
    for (line_no, line), raw in zip(lines, parsed):
        if raw.query not in queries:
            raise NativeError(f"unknown native query: {raw.query}")
        fields = dict(zip(FIELDS, line.split("\t")))
        item = native_hsp(raw, queries[raw.query], policy.classify(raw.subject), legacy.hsp_identifier(raw))
        columns = legacy.btop_columns(raw.btop)
        mismatch = sum(q != s and q != "-" and s != "-" for q, s in columns)
        gaps = sum(q == "-" or s == "-" for q, s in columns)
        gapopen, previous = 0, None
        for q, s in columns:
            kind = "QUERY" if q == "-" else "SUBJECT" if s == "-" else None
            gapopen += kind is not None and kind != previous
            previous = kind
        if (int(fields["nident"]), raw.mismatch, raw.gaps, raw.gapopen) != (item.identical_columns, mismatch, gaps, gapopen):
            raise NativeError(f"BTOP instrumented counts mismatch: line {line_no}")
        if not all(math.isfinite(v) and v >= 0 for v in (raw.pident, raw.evalue, raw.bitscore, float(fields["score"]), raw.qcovs)) or raw.pident > 100:
            raise NativeError(f"invalid numeric provenance: line {line_no}")
        result.append(ObservedHsp(item, fields, line_no))
    return sorted(result, key=lambda h: (h.native.raw.query, h.native.raw.subject, h.native.raw.qstart,
                  h.native.raw.qend, h.native.raw.sstart, h.native.raw.send, h.native.raw.btop))


def exact_starts(hsps: list[ObservedHsp], k: int) -> set[int]:
    return {s for h in hsps for a, b in h.native.exact_runs for s in range(a, b - k + 2)}


def unit_evidence(hsps: list[ObservedHsp]) -> dict:
    if len({h.native.raw.query for h in hsps}) > 1 or len({h.native.unit for h in hsps}) > 1:
        raise NativeError("cannot pool native queries or biological units")
    if not hsps:
        return {"longest_exact_match": 0, "covered_nt": 0, "best_local_identity": 0.0,
                "alignment_columns_for_best_identity": 0, "query_span_for_best_identity": 0,
                "identical_columns_for_best_identity": 0, "best_identity_hsp_id": "",
                "n_hsps": 0, "n_subject_records": 0, "subject_accessions": "",
                "exact_19mer_count": 0, "exact_21mer_count": 0, "evidence_status": NO_HSP}
    # Stable canonical ordering resolves the remaining legacy identifier collisions by BTOP.
    ordered = sorted(hsps, key=lambda h: (h.native.raw.query, h.native.raw.subject, h.native.raw.qstart,
                     h.native.raw.qend, h.native.raw.sstart, h.native.raw.send, h.native.raw.btop))
    best = min(ordered, key=lambda h: (-h.identity, -h.query_span, h.identifier))
    subjects = sorted({h.native.raw.subject for h in hsps})
    return {"longest_exact_match": max(h.native.longest_exact for h in hsps),
            "covered_nt": union_length((h.native.raw.qstart, h.native.raw.qend) for h in hsps),
            "best_local_identity": best.identity,
            "alignment_columns_for_best_identity": best.native.raw.length,
            "query_span_for_best_identity": best.query_span,
            "identical_columns_for_best_identity": best.native.identical_columns,
            "best_identity_hsp_id": best.identifier, "n_hsps": len(hsps),
            "n_subject_records": len(subjects), "subject_accessions": ",".join(subjects),
            "exact_19mer_count": len(exact_starts(hsps, 19)), "exact_21mer_count": len(exact_starts(hsps, 21)),
            "evidence_status": "REPORTED_HSP_PRESENT"}


def persisted(evidence: dict) -> dict:
    return {k: f"{v:.6f}" if isinstance(v, float) else v for k, v in evidence.items()}


def fresh_output(root: Path, out: Path) -> Path:
    root, out = root.resolve(), out.resolve()
    protected = [root / p for p in ("src", "config", "data", "tests", "scripts")]
    protected += [root / CP2 / p for p in ("cp3", "cp4", "cp5")]
    if out == root or any(out == p or out.is_relative_to(p) for p in protected):
        raise NativeError("output would overwrite protected historical/input paths")
    if out.exists() and any(out.iterdir()):
        raise NativeError(f"output already contains artifacts: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


def manifest_outputs(out: Path) -> dict[str, str]:
    return {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob("*"))
            if p.is_file() and p.name not in {"run_manifest.json", "execution_status.json"}}


def run_cp3(root: Path, output_dir: Path | None = None) -> dict:
    root = root.resolve()
    queries, ref, registry, inputs = load_queries(root)
    policy = legacy.load_policy(registry)
    out = fresh_output(root, output_dir or root / OUTPUT / "cp3")
    log = CommandLog()
    write_json(out / "execution_status.json", {"status": "RUNNING"})
    try:
        version = legacy.blast_version(log)
        if not version.startswith("blastn: 2.17.0+"):
            raise NativeError(f"unexpected BLAST version: {version}")
        database = legacy.build_database(root, out, policy, log)
        if (database["combined_fasta_sha256"], database["n_sequences"], database["total_bases"]) != (DATABASE_SHA256, 56121, 94710159):
            raise NativeError("combined database identity mismatch")
        for name in ("data/external/tsa.GITV.1.fsa_nt.gz", str(nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH)):
            inputs[name] = digest(root / name)
        fasta = out / "queries.fasta"
        fasta.write_text("".join(f">{q.identifier}\n{q.sequence}\n" for q in queries), encoding="ascii")
        write_tsv(out / "query_registry.tsv", [{"query_id": q.identifier, "membership": q.membership,
                  "cds_start": q.cds_start, "cds_end": q.cds_end, "length_nt": q.length,
                  "sequence_sha256": sequence_hash(q.sequence), "specificity_evidence_basis": BASIS} for q in queries])
        raw_path = out / "blastn_native.outfmt6.tsv"
        command = ["blastn", "-query", str(fasta), "-db", database["database"], *blast_arguments(policy.search),
                   "-outfmt", "6 " + " ".join(FIELDS)]
        log.run(command, stdout_path=raw_path)
        observed = parse_native(raw_path.read_text(), {q.identifier: q for q in queries}, policy)
        grouped = defaultdict(list)
        provenance = []
        for h in observed:
            grouped[(h.native.raw.query, h.native.unit)].append(h)
            provenance.append({"hsp_id": h.identifier, "source_line": h.line, "unit": h.native.unit,
                               "specificity_evidence_basis": BASIS, **h.fields,
                               "identity_numerator": h.native.identical_columns,
                               "identity_denominator": h.native.raw.length})
        write_tsv(out / "hsp_provenance.tsv", provenance, ("hsp_id", "source_line", "unit", "specificity_evidence_basis", *FIELDS,
                  "identity_numerator", "identity_denominator"))
        units, vectors, distributions = [], [], Counter()
        for q in queries:
            evs = {unit: unit_evidence(grouped[(q.identifier, unit)]) for unit in UNITS}
            for unit, ev in evs.items():
                units.append({"query_id": q.identifier, "membership": q.membership, "unit": unit,
                              "specificity_evidence_basis": BASIS, **persisted(ev)})
            vector = {f"{unit.lower()}_{axis}": persisted(evs[unit])[axis] for unit in DECISIONAL for axis in AXES}
            vectors.append({"query_id": q.identifier, "membership": q.membership, "length_nt": q.length,
                            "specificity_evidence_basis": BASIS, **vector})
            if q.membership == "DESIGN_SPACE":
                distributions[(q.length, tuple(str(v) for v in vector.values()))] += 1
        write_tsv(out / "candidate_unit_specificity.tsv", units)
        write_tsv(out / "vectors.tsv", vectors)
        write_tsv(out / "benchmark_specificity.tsv", [r for r in units if r["membership"] == "REFERENCE_SET"])
        write_tsv(out / "vector_distributions.tsv", [{"length_nt": k[0], "vector": json.dumps(k[1]), "candidates": n}
                  for k, n in sorted(distributions.items())])
        # C18 is reproduced exactly as historical whole-CDS controls, never per candidate.
        control_dir = out / "historical_controls"
        control_dir.mkdir()
        controls = legacy.run_blast(ref["operational_cds"], policy.shuffle_seeds, database["database"], policy.search, control_dir, log)
        control_summary = []
        for name in ("operational_cds", *[f"shuffle_{seed}" for seed in policy.shuffle_seeds]):
            hits = [h for h in controls if h.query == name]
            fps = [legacy.footprint(h, policy.classify(h.subject)) for h in hits]
            control_summary.append({"query": name, "n_hsps": len(hits),
                    "longest_exact_match": max((b-a+1 for f in fps for a,b in f.runs), default=0),
                    "role": "DESCRIPTIVE_ONLY_HISTORICAL_CDS_CONTROL"})
        write_tsv(control_dir / "summary.tsv", control_summary)
        # Exact scan starts on the certified CDS are restricted to each actual query interval.
        tsa, _ = reference.validated_tsa_path(root)
        tsa_records = ((nb01_identity.canonical_tsa_accession(r.identifier), r.sequence) for r in nb01_identity.parse_fasta(tsa))
        anchors = ((r.identifier, r.sequence) for r in nb01_identity.parse_fasta(root / nb01_identity.DEFAULT_ANCHOR_SEQUENCE_PATH))
        direct = legacy.exact_kmer_scan(ref["operational_cds"], itertools.chain(tsa_records, anchors), policy)
        checks = []
        for q in queries:
            for unit in UNITS:
                for k in (19, 21):
                    found = {s-q.cds_start+1 for s in direct[k].get(unit, set()) if q.cds_start <= s <= q.cds_end-k+1}
                    reconstructed = exact_starts(grouped[(q.identifier, unit)], k)
                    checks.append({"query_id": q.identifier, "unit": unit, "k": k, "direct": len(found),
                        "btop": len(reconstructed), "only_direct": len(found-reconstructed), "only_btop": len(reconstructed-found)})
        write_tsv(out / "exact_kmer_checks.tsv", checks)
        write_json(out / "commands.json", log.entries)
        source_paths = ["src/zeaguard/" + name + ".py" for name in ("nb02_native", "nb02_specificity", "nb03_specificity", "nb02_criteria", "nb02_cells", "nb02_reference", "nb02_design", "nb01_dsrnase_investigation")]
        summary = {"query_count": len(queries), "design_queries": len(queries)-1, "native_hsps": len(observed),
                   "unit_rows": len(units), "kmer_disagreement_rows": sum(bool(r["only_direct"] or r["only_btop"]) for r in checks),
                   "controls": {"historical_CDS_shuffles_reproduced": list(policy.shuffle_seeds),
                                "candidate_specific_shuffles": "NOT_EXECUTED_OUT_OF_SCOPE", "biological_decision_role": False},
                   "membership_uncertainty": {"GITV01009778.1": "IDENTIDADE_BIOLOGICA_UNRESOLVED"}}
        write_json(out / "summary.json", summary)
        manifest = {"stage": "NB02_NATIVE_CP3", "status": "COMPLETE", "specificity_evidence_basis": BASIS,
                    "git": design._git_state(root), "python": sys.version, "inputs_sha256": inputs,
                    "implementation_sha256": {p: digest(root / p) for p in source_paths},
                    "blast": {"version": version, "arguments": blast_arguments(policy.search), "fields": FIELDS},
                    "database": database, "units": registry["policy"]["specificity_units"],
                    "outputs_sha256": manifest_outputs(out), "summary": summary,
                    "chronology": "POST_DIAGNOSTIC_CORRECTION_WITH_KNOWN_CANDIDATE_EFFECTS",
                    "no_diagnostic_computational_inputs": True}
        write_json(out / "run_manifest.json", manifest)
        write_json(out / "execution_status.json", {"status": "COMPLETE"})
        return manifest
    except Exception as error:
        write_json(out / "commands.json", log.entries)
        write_json(out / "execution_status.json", {"status": "FAILED", "error_type": type(error).__name__, "error": str(error)})
        raise


def closure_status(provisional: list[str], approved: list[str], review_complete: bool,
                   bounds: dict) -> dict:
    """Report gates independently; never fabricate a decision or publish a handoff."""
    if bounds != {"min": 2, "max": 4}:
        raise NativeError("this delivery preserves the historical 2-4 recommendation bounds")
    if (len(set(provisional)) != len(provisional) or len(set(approved)) != len(approved)
            or not set(approved) <= set(provisional)
            or any(q.startswith("D2-BENCH") for q in provisional)):
        raise NativeError("invalid/duplicate recommendation membership or benchmark")
    quantity = bounds["min"] <= len(approved) <= bounds["max"]
    return {"provisional_candidates": provisional, "reviewed_approved_candidates": approved,
            "recommended_candidate_bounds": bounds, "human_review_complete": review_complete,
            "quantity_gate_satisfied": quantity, "closed": quantity and review_complete,
            "blocking_reasons": ([] if review_complete else ["HUMAN_REVIEW_PENDING"]) +
                                ([] if quantity else ["RECOMMENDED_QUANTITY_OUTSIDE_BOUNDS"]),
            "handoff_promoted": False, "scientific_audit": "PENDING_INDEPENDENT_REVIEW"}


def load_cp3(root: Path, cp3: Path) -> tuple[dict, list[dict], dict[str, dict]]:
    manifest = json.loads((cp3 / "run_manifest.json").read_text())
    status = json.loads((cp3 / "execution_status.json").read_text())
    if manifest.get("status") != "COMPLETE" or status.get("status") != "COMPLETE" or manifest.get("specificity_evidence_basis") != BASIS:
        raise NativeError("CP3 evidence is failed, incomplete or not native")
    verify_outputs(cp3, manifest)
    for name, expected in {**manifest["inputs_sha256"], **manifest["implementation_sha256"]}.items():
        if digest(root / name) != expected:
            raise NativeError(f"CP3 input/implementation changed: {name}")
    rows = read_tsv(cp3 / "vectors.tsv")
    registry = read_tsv(cp3 / "query_registry.tsv")
    qids = [r["query_id"] for r in registry]
    if len(set(qids)) != len(qids) or len(rows) != len(qids) or {r["query_id"] for r in rows} != set(qids):
        raise NativeError("CP3 exact query identifier equality/completeness failed")
    if any(r["specificity_evidence_basis"] != BASIS for r in rows + registry):
        raise NativeError("mixed specificity evidence bases")
    expected = {(q, u) for q in qids for u in UNITS}
    unit_rows = read_tsv(cp3 / "candidate_unit_specificity.tsv")
    if len(unit_rows) != len(expected) or {(r["query_id"], r["unit"]) for r in unit_rows} != expected:
        raise NativeError("CP3 query x unit completeness failed")
    if any(r["specificity_evidence_basis"] != BASIS for r in unit_rows):
        raise NativeError("non-native unit evidence")
    return manifest, rows, {r["query_id"]: r for r in registry}


def build_native_cells(rows: list[dict], descriptors: dict[str, dict]) -> tuple[list[dict], dict[str, dict]]:
    strata = defaultdict(list)
    for row in rows:
        if row["membership"] != "DESIGN_SPACE":
            continue
        if row["specificity_evidence_basis"] != BASIS:
            raise NativeError("non-native decision evidence")
        qid = row["query_id"]
        if qid not in descriptors:
            raise NativeError("native evidence has no CP2 descriptor")
        d = descriptors[qid]
        entry = {"candidate_id": qid, "length_nt": int(d["length_nt"]), "length_stratum": d["length_stratum"],
                 "cds_start": int(d["cds_start"]), "cds_end": int(d["cds_end"]),
                 "variants": tuple(int(p) for p in d["variant_positions"].split(",") if p),
                 "n_variant_sites": int(d["n_variant_sites"]), "descriptor": d}
        for unit in DECISIONAL:
            token = row[f"{unit.lower()}_best_local_identity"]
            if not isinstance(token, str) or not re.fullmatch(r"(?:0\.\d{6}|1\.000000)", token):
                raise NativeError("CP4 requires the persisted six-decimal identity boundary")
            vector = tuple(float(row[f"{unit.lower()}_{axis}"]) for axis in AXES)
            if not all(math.isfinite(v) and v >= 0 for v in vector) or vector[2] > 1:
                raise NativeError("invalid persisted specificity vector")
            entry[unit.lower()] = vector
        strata[entry["length_nt"]].append(entry)
    result, per_query = [], {}
    for length, entries in sorted(strata.items()):
        entries.sort(key=lambda e: e["cds_start"])
        cs = cells.contiguous_cells([(e["cds_start"], cells.window_signature(e)) for e in entries],
                                    entries[0]["length_stratum"], length)
        bystart = {e["cds_start"]: e for e in entries}
        ordered = cells.order_cells([cells.OrderedCell(c, [bystart[s] for s in c.starts]) for c in cs])
        for c in ordered:
            row = {"cell_id": c.cell.cell_id, "signature_id": c.cell.signature_id,
                   "signature": json.dumps(c.cell.signature), "length_nt": length,
                   "start_min": c.cell.start_min, "start_max": c.cell.start_max,
                   "end_min": c.cell.start_min+length-1, "end_max": c.cell.start_max+length-1,
                   "n_windows": len(c.entries), "in_pareto_front": c.in_pareto_front,
                   "ordering_group": c.ordering_group, "representative": c.representative["candidate_id"]}
            result.append(row)
            for e in c.entries:
                per_query[e["candidate_id"]] = row
    return result, per_query


def historical_comparison(root: Path, rows: list[dict], native_cells: list[dict], assignments: dict) -> tuple[list, list, dict]:
    """Historical evidence is read only after native CP4 has been calculated."""
    directory = root / CP2 / "cp3"
    manifest = json.loads((directory / "run_manifest.json").read_text())
    path = directory / "specificity_windows.tsv"
    if digest(path, normalized=True) != manifest["outputs_sha256"][path.name]:
        raise NativeError("historical CP3 artifact integrity mismatch")
    old = {r["candidate_id"]: r for r in read_tsv(path)}
    design_rows = [r for r in rows if r["membership"] == "DESIGN_SPACE"]
    if set(old) != {r["query_id"] for r in design_rows}:
        raise NativeError("historical and native design identifiers differ")
    original_cells = {}
    for length in sorted({int(r["length_nt"]) for r in design_rows}):
        for c in cells.build_cells(root, length):
            for entry in c.entries:
                original_cells[entry["candidate_id"]] = c
    delta, unit_delta, counts, units_changed = [], [], Counter(), Counter()
    for r in design_rows:
        qid = r["query_id"]
        changed = False
        for unit in DECISIONAL:
            a = tuple(float(old[qid][f"{unit.lower()}_{m}_clipped"]) for m in AXES)
            b = tuple(float(r[f"{unit.lower()}_{m}"]) for m in AXES)
            is_changed = a != b
            changed |= is_changed
            units_changed[unit] += is_changed
            unit_delta.append({"query_id": qid, "length_nt": r["length_nt"], "unit": unit,
                               "historical_vector": json.dumps(a), "native_vector": json.dumps(b), "changed": is_changed})
        c, d = original_cells[qid], assignments[qid]
        counts[int(r["length_nt"])] += changed
        delta.append({"query_id": qid, "length_nt": r["length_nt"], "vector_changed": changed,
                      "historical_pareto": c.in_pareto_front, "native_pareto": d["in_pareto_front"],
                      "historical_cell": c.cell.cell_id, "native_cell": d["cell_id"],
                      "historical_representative": c.representative["candidate_id"], "native_representative": d["representative"],
                      "historical_group": c.ordering_group, "native_group": d["ordering_group"]})
    fronts = {}
    for length in sorted(counts):
        a = {qid for qid, c in original_cells.items() if c.cell.length_nt == length and c.in_pareto_front}
        b = {qid for qid, c in assignments.items() if c["length_nt"] == length and c["in_pareto_front"]}
        fronts[length] = {"historical": len(a), "native": len(b), "intersection": len(a & b),
                          "only_historical": len(a-b), "only_native": len(b-a),
                          "historical_cells": len({c.cell.cell_id for c in original_cells.values() if c.cell.length_nt == length}),
                          "native_cells": sum(c["length_nt"] == length for c in native_cells)}
    return delta, unit_delta, {"total_candidates": len(design_rows), "N1_different": sum(counts.values()),
                               "differences_by_length": dict(counts), "differences_by_unit": dict(units_changed),
                               "pareto_by_length": fronts, "historical_CP3_manifest_sha256": digest(directory / "run_manifest.json")}


def run_cp4(root: Path, cp3: Path | None = None, output_dir: Path | None = None) -> dict:
    root = root.resolve()
    cp3 = cp3 or root / OUTPUT / "cp3"
    manifest, vectors, registry = load_cp3(root, cp3)
    descriptors = {r["candidate_id"]: r for r in read_tsv(root / CP2 / "strata_windows.tsv")}
    crows, assignments = build_native_cells(vectors, descriptors)
    out = fresh_output(root, output_dir or root / OUTPUT / "cp4")
    write_json(out / "execution_status.json", {"status": "RUNNING"})
    try:
        write_tsv(out / "cells.tsv", crows)
        write_tsv(out / "pareto.tsv", [{"query_id": q, "length_nt": c["length_nt"], "cell_id": c["cell_id"],
                  "in_pareto_front": c["in_pareto_front"]} for q, c in sorted(assignments.items())])
        delta, unit_delta, comparison = historical_comparison(root, vectors, crows, assignments)
        write_tsv(out / "delta_by_candidate.tsv", delta)
        write_tsv(out / "delta_by_unit.tsv", unit_delta)
        write_json(out / "comparison_summary.json", comparison)
        criteria_registry = criteria.load_registry(root)
        ranking = design.design_parameters(criteria_registry).ranking_length
        top = [c for c in crows if c["length_nt"] == ranking and c["ordering_group"] == 1]
        provisional = [c["representative"] for c in top]
        write_tsv(out / "provisional_candidates.tsv", [{"candidate_id": q, "status": "PENDING_REVIEW",
                  "specificity_evidence_basis": BASIS, **registry[q]} for q in provisional],
                  ("candidate_id", "status", *registry[next(iter(registry))].keys()))
        packet = [r for r in read_tsv(cp3 / "hsp_provenance.tsv") if r["qseqid"] in provisional]
        write_tsv(out / "review_evidence.tsv", packet, ("hsp_id", "source_line", "unit", "specificity_evidence_basis", *FIELDS,
                  "identity_numerator", "identity_denominator"))
        write_json(out / "review_packet_manifest.json", {"evidence_sha256": digest(out / "review_evidence.tsv"),
                   "cp3_manifest_sha256": digest(cp3 / "run_manifest.json"), "provisional_candidates": provisional,
                   "human_decisions": [], "historical_review_transferred": False})
        status = closure_status(provisional, [], False, criteria_registry["policy"]["recommended_candidates"])
        status.update({"cp3_computational_execution": "COMPLETE", "cp4_computational_execution": "COMPLETE",
                       "NB04_UPSTREAM_APPLICABILITY_REVIEW": "REQUIRED_BEFORE_G0_IF_SELECTION_OR_JUSTIFICATION_CHANGES",
                       "NB04_updated": False, "G0_PASS": "NOT_DECLARED", "CP1": "NOT_STARTED"})
        write_json(out / "closure_status.json", status)
        summary = {"comparison": comparison, "closure": status,
                   "selected": {q: assignments[q] for q in ("D2-L400-0351-0750", "D2-L400-0817-1216") if q in assignments},
                   "benchmark_vectors": [r for r in vectors if r["membership"] == "REFERENCE_SET"],
                   "diagnostic_expectations_not_forced": {"different_vectors": 907, "L400_pareto": 667, "L400_cells": 12}}
        write_json(out / "summary.json", summary)
        result = {"stage": "NB02_NATIVE_CP4", "status": "COMPLETE", "specificity_evidence_basis": BASIS,
                  "cp3_manifest_sha256": digest(cp3 / "run_manifest.json"),
                  "implementation_sha256": digest(Path(__file__)), "outputs_sha256": manifest_outputs(out), "summary": summary}
        write_json(out / "run_manifest.json", result)
        write_json(out / "execution_status.json", {"status": "COMPLETE"})
        return result
    except Exception as error:
        write_json(out / "execution_status.json", {"status": "FAILED", "error_type": type(error).__name__, "error": str(error)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("cp3", "cp4"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_cp3(args.root, args.output) if args.stage == "cp3" else run_cp4(args.root, output_dir=args.output)
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
