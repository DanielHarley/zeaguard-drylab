# Run ID

`2026-10-08_nb03-cp2-descriptive-design-space`

## Date

2026-10-08, project timezone `America/Sao_Paulo`.

## Commit

`099f751780283fecbc63da177c113aec9f6d60d5` (CP1). The worktree contains the uncommitted CP2 implementation and descriptive clarification. No CP2 commit, push or PR was authorized or performed.

## Branch

`feat/nb03-bicc-candidate-regions`

## Execution status

`COMPLETED`

Checkpoint assessment: `G2_PASS`. Downstream readiness: `CP3_READY_TO_PLAN_OR_IMPLEMENT`, pending a separate user instruction.

## Question / objective

Enumerate and describe every interval of 300-500 nt inside the 2337 nt operational BicC sense CDS, with length and start steps of one nucleotide. Preserve the primer-defined 373 nt benchmark as a separate `REFERENCE_SET` row. No specificity analysis or candidate selection belongs to this checkpoint.

## Inputs

[BicC operational-reference pin](../../../../data/reference/nb01_bicc_operational_reference.json), [primary-data manifest](../../../../data/reference/manifest.json), [anchor sequences](../../../../data/reference/target_anchor_sequences.fasta) and [unit membership decisions](../../../../config/nb03_unit_membership_decisions.tsv). The [CP2 manifest](../../../../results/bioinformatics/nb03/cp2/run_manifest.json) records input and implementation hashes.

The TSA is checked against its manifest hash. The operational record and unique complete ORF, published CDS, observed sequence differences and primer-defined benchmark are rechecked against the CP1 pin without invoking any BLAST. Reference placement and BicC-like discovery remain the CP0/CP1 verification surfaces exercised by their existing regression tests.

## Configuration

[NB03 criteria registry](../../../../config/nb03_design_criteria.yaml) and [ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md), whose formal status remains `Accepted` for the preregistration policy through CP1.

Before the first NB03 window was generated, the user approved the C23 descriptive clarification: replace ambiguous `overlap_fraction` with `overlap_fraction_of_candidate` and `overlap_fraction_of_benchmark`, using candidate length and operational benchmark length as denominators. Add `EXACT_MATCH` for CDS 215-587, with strict shorter/longer containment categories. The registry amendment records `changes_thresholds_roles_or_policy: false` and `applied_before_window_generation: true`. All overlap fields remain outside decisions and tie-breaking.

Canonical execution environment: WSL2 Ubuntu-24.04, conda environment `zeaguard`, Python 3.12.14, pytest 9.1.1, BLAST+ package 2.17.0 and dustmasker 1.0.0. DUST uses defaults and `-outfmt interval`, counting masked positions inclusively, independently for each window.

## Method

Entry point: [nb03_design.py](../../../zeaguard/nb03_design.py).

```bash
PYTHONPATH=src python -m zeaguard.nb03_design
```

The implementation reuses NB02 pure interval, composition, homopolymer, positional and intercepted-subwindow functions, plus its DUST helper. The three structural requirements are the only hard filters. The complete operational CDS contains only A/C/G/T, so every enumerated interval passes.

Canonical order is increasing `length_nt`, then increasing `cds_start`. IDs depend only on target and geometry, for example `BC-L400-0001-0400`. Sequences are omitted from the mass TSV and reconstructed exactly from the verified CDS and inclusive coordinates; each row records its sequence SHA-256.

Potential 21-nt derived windows are descriptive under `OPERATIONAL_ASSUMPTION`. The number of affected starts is the union of the start intervals intercepting observed differences, so each subwindow is counted once. Exact difference positions remain descriptive, while their count retains its preregistered potential downstream decisional role. CP2 performs no ordering by either quantity.

The benchmark ID is `BC-BENCH-0215-0587`, with membership `REFERENCE_SET`. The geometric design window `BC-L373-0215-0587` is retained among the 1965 length-373 intervals, with membership `DESIGN_SPACE`.

## Outputs

All outputs remain gitignored under `results/bioinformatics/nb03/cp2/`.

1. [design_space.tsv](../../../../results/bioinformatics/nb03/cp2/design_space.tsv): all 389538 descriptive design rows.
2. [benchmark_descriptor.tsv](../../../../results/bioinformatics/nb03/cp2/benchmark_descriptor.tsv): one separate operational benchmark row.
3. [cp2_summary.json](../../../../results/bioinformatics/nb03/cp2/cp2_summary.json): counts by all 201 lengths and descriptive summaries for the four registered strata.
4. [run_manifest.json](../../../../results/bioinformatics/nb03/cp2/run_manifest.json): input, code, parameter, tool and output provenance.

The manifest hashes the three data outputs. Its own hash is reported externally to avoid self-referential hashing. JSON and TSV use LF newlines; TSV descriptors have six decimal places. No wall-clock time or temporary/output path is embedded in the four outputs.

## Validation / QC

Preflight before editing: expected CP1 HEAD and clean worktree confirmed; the full suite reported `320 passed in 31.83s`, with zero failures or skips. Pin, registry and their agreement were explicitly checked, including CDS-only domain, operational benchmark length 373, ranking stratum 400 and sensitivity lengths 300/500.

Final regression command:

```bash
PYTHONPATH=src python -m pytest
```

Final result: `343 passed in 99.32s`, with zero failures or skips. The full suite includes 105 NB03 tests, of which 23 belong to the new CP2 test module.

The real-data audit visits all 389538 persisted rows and checks canonical order, unique geometric IDs, CDS bounds, reconstructed sequence lengths and bases, sequence hashes, difference positions/counts, affected/unaffected potential subwindow counts and serialized fractions, GC and benchmark geometry. Tests compare all four output files byte-for-byte between two independent complete runs. A command guard permits only DUST and read-only Git commands in the CP2 runner, rejecting any attempted BLAST or other external tool. Output schemas exclude specificity, cells, ranking and selection columns.

An additional independent CP2 execution was compared directly with the canonical output directory: all four files were byte-identical and had equal SHA-256 hashes. The temporary verification directory was removed after comparison. An independent PowerShell calculation reproduced the length-400 difference-count distribution and benchmark relation counts. NB02 files, configuration and implementation have no diff. The NB02 TSV and FASTA hashes remain exactly those supplied in the checkpoint request. Final `git diff --check` is clean.

## Results

All 389538 intervals pass the structural filters. Counts are calculated and checked against `2337 - L + 1` for every length, and against its sum over 300-500.

Registered-stratum counts: L300 = 2038, L373 = 1965, L400 = 1938, L500 = 1838. The separate benchmark row is excluded from these design-space counts.

For L400, observed-difference counts 0/1/2/3 occur in 699/760/216/263 windows. Benchmark relations are `DISJOINT` = 1351, `PARTIAL_OVERLAP` = 559 and `CONTAINS_BENCHMARK` = 28. `FULLY_WITHIN` and `EXACT_MATCH` are both zero at length 400. These are descriptive distributions and select no interval.

The structured summary contains the full GC, homopolymer, DUST and unaffected-fraction statistics. The benchmark has zero intersected observed differences, 353 potential 21-nt derived windows, all 353 unaffected, and `EXACT_MATCH` geometry. Its published reported length remains 372, its operational length remains 373, and experimental protocol verification remains `PROJECT_PROVIDED_NOT_AGENT_VERIFIED`.

## Interpretation

`G2_PASS` establishes complete deterministic descriptive enumeration under the CP1 contract and its user-approved geometric clarification. The count of observed differences is available for a later checkpoint, without performing candidate-specificity calculations or applying the decisional policy to these windows.

The operational reference remains transcript-level evidence. Observed sequence differences remain `UNRESOLVED`, with `read_support_status = NOT_ASSESSED_FOR_NB03_CP0`.

## What this run does NOT establish

RNAi efficacy, active or effective small RNAs, population conservation, the nature of observed differences, cross-silencing, ecological specificity, an optimal length or region, benchmark protocol verification, or suitability for synthesis. CP3, real Pareto comparison, cells, representatives, ranking, shortlist, Wet Lab handoff, Notebook 03 and CP5 reference artifacts remain unimplemented in this work.

## Anomalies / deviations

The first post-implementation regression reported 342 passing tests and one failing assertion at a six-decimal halfway rounding boundary: decimal 0.4453125 serialized as 0.445312, with binary floating-point subtraction slightly exceeding the test's 0.0000005 tolerance. The audit now checks exact declared six-decimal serialization. Production descriptors and output hashes were unchanged by this test correction. The final complete regression passed.

The worktree is intentionally dirty because the user requested review before commit. No deviation from the canonical operating system or environment was introduced.

## Related decisions

[ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md), with its pre-CP2 C23 clarification. NB02 is consumed through existing helpers and remains unchanged.

## Related Issue / PR / commits

CP0: `2d1ae8f48e9af684422faabaebed0f6486f658c5`. CP1: `099f751780283fecbc63da177c113aec9f6d60d5`. No CP2 commit, push, issue or PR was created.

## Evidence classification

1. `directly demonstrated`: local input hashes, observed execution environment, command restrictions, test results and byte comparisons.
2. `derived/computed`: interval enumeration, sequence hashes and all descriptive window/benchmark metrics.
3. `inferred/interpreted`: checkpoint readiness conditional on the declared CP1 contract and user-provided scientific approval.
4. `unresolved`: biological nature of sequence differences, read support, BicC-like relationship, experimental protocol verification and biological performance of every design interval.
