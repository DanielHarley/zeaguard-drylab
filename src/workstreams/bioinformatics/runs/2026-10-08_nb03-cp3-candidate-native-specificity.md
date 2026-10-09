# Run ID

`2026-10-08_nb03-cp3-candidate-native-specificity`

## Date

2026-10-08, project timezone `America/Sao_Paulo`. The canonical BLAST searches ran between 04:14 and 04:18 local time (07:14-07:18 UTC); exact UTC timestamps are in `execution_log.json`.

## Commit

Base: `b82dd0ddd55e62aa4111fcaca785e60c9362e1a3` (pre-CP3 native-alignment amendment). Earlier checkpoints: CP0 `2d1ae8f48e9af684422faabaebed0f6486f658c5`, CP1 `099f751780283fecbc63da177c113aec9f6d60d5`, CP2 `4e141876c478a76aada15d3f4b89b80dc9f6863f`.

Two executions are recorded:

1. The initial execution ran on `b82dd0d` with the CP3 implementation still uncommitted and the registry whose LF SHA-256 was `127106430145d5c8bed16b994c2372753908997baa8f181a1ebe86078b372cb7`. Its manifest hash was `680ebf1af243ec5ee2c7563ab290a909421ce457622c9e2a17f6f73312b7fcbd`. It is superseded as the provenance reference.
2. The canonical scientific execution was repeated at the CP3 commit, with that commit's code, tests, registry and ADR. It is the provenance reference.

```yaml
canonical_scientific_execution_commit: 748bd81248be0e34c2fc4158a78660d5e4f1ba25
canonical_registry_sha256_lf: ebce5b08354b1eb990da95b4a56e45cce018b3617197069906c6580cee832ef6
canonical_run_manifest_sha256: 19d280fc9b01c1e155d5b28825c84930792a76430018b245a6a0b98a9f2f2439
cp3_scientific_outputs_changed: false
```

The commit that later updates this record is documentation only and is deliberately not the execution commit: the manifest references `748bd81`, and no further execution is made to chase a self-referential fixed point.

## Branch

`feat/nb03-bicc-candidate-regions`

## Execution status

`COMPLETED`. `G3_PASS`, `CP3_PROVENANCE_NORMALIZED` and `CP4_READY_TO_IMPLEMENT` hold for the contract recorded below.

## Question / objective

Materialize candidate-native specificity evidence for the 7779 preregistered design-space windows and the separate benchmark, per frozen biological unit, before any Pareto comparison, cell, representative or shortlist exists. The canonical evidence basis is `specificity_evidence_basis = CANDIDATE_NATIVE_ALIGNMENT`: each candidate sequence is itself the BLAST query.

## Inputs

- Certified CP2 outputs (`design_space.tsv`, `benchmark_descriptor.tsv`, `run_manifest.json`), re-verified by hash on load. CP2 `design_space.tsv` SHA-256: `142e5e856a6740b2a225e947cbe7feae181ae0cab01d0084af56c74465719ee4`; CP2 manifest: `124ce71cc5f8d68fe1a7eb66f6d62630623d72bd3697268debac0cadb760a4e3`.
- Operational BicC CDS (`GITV01000968.1`, 2337 nt), SHA-256 `05cb44b0bf9d0c72d2adaa5b09cf9c0795039e29858e666c6082a170e5924f30`.
- TSA GITV01 (file SHA-256 `22d0cff8d0867344a76d615bdca62c31ce0f9133f574058e8daa6b6e41925ae6`) plus the four published cDNAs in `data/reference/target_anchor_sequences.fasta`.
- [Unit membership decisions](../../../../config/nb03_unit_membership_decisions.tsv), [criteria registry](../../../../config/nb03_design_criteria.yaml) and [ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md).

## Configuration

- BLAST+ 2.17.0 (`blastn: 2.17.0+`, build Aug 22 2026), WSL2 Ubuntu-24.04, conda environment `zeaguard`, Python 3.12.14.
- Arguments: `-task blastn -dust no -word_size 11 -evalue 10 -strand both -max_target_seqs 100000 -num_threads 1`; no `-max_hsps` limit. Output format 6 with `btop`.
- Database: 56121 sequences, 94710159 bases (56117 TSA records plus the four published cDNAs `TRINITY_DN24799_c0_g1_i7`, `TRINITY_DN22752_c0_g2_i1`, `TRINITY_DN13786_c0_g1_i8`, `TRINITY_DN5008_c0_g1_i24`). Combined FASTA SHA-256 `ea236b31337549262969fdadd54fcce2ae1bb7bceef14e5ee51c95d952c63d4b`.
- Units: `KNOWN_BICC_COMPATIBLE` (`GITV01000968.1`, `TRINITY_DN24799_c0_g1_i7`), `BICC_LIKE` (`GITV01002238.1`, `relationship_status = UNRESOLVED`), `DSRNASE2` (`GITV01008430.1`, `GITV01012450.1`, `TRINITY_DN22752_c0_g2_i1`), `DSRNASE1` (4 records), `DSRNASE3` (1 record) and `OTHER_TRANSCRIPT` (every other record). A record belongs to exactly one unit.

## Method

Entry point: [nb03_specificity.py](../../../zeaguard/nb03_specificity.py).

```bash
PYTHONPATH=src python -m zeaguard.nb03_specificity
```

1. Every candidate is aligned natively. Queries are written as deterministic multi-query FASTAs per length stratum, so the search uses ten BLAST processes, not 7779 independent ones. No HSP is clipped from a full-CDS search.
2. Each HSP is rebuilt from its BTOP and validated against its coordinates, strand, alignment length and reported identity. BTOP `I` (query base against subject gap) advances the query; `D` (query gap) does not.
3. HSPs are aggregated per query and per unit, never across units: `longest_exact_match` (maximum), `covered_nt` (union of candidate-query positions covered by HSPs of the unit, i.e. the plan's `union_covered_nt`; the column keeps the name `covered_nt`), `best_local_identity` (maximum identical-column fraction) and the descriptive `aligned_nt_for_best_identity`.
4. `aligned_nt_for_best_identity` is `DESCRIPTIVE_ONLY`. When several HSPs share the maximal identity (exact fraction) the descriptor comes from the longest alignment, then the lowest HSP id in the deterministic raw-table ordering. This only makes the descriptor reproducible; it never changes `best_local_identity`, enters no Pareto or decisive signature and expresses no biological preference. The rule is registered in the criteria registry and ADR 0006, and was already the implemented behaviour.
5. A unit without a detected HSP has vector `(0, 0, 0)`. This means only "no homology detected under the configured candidate-native BLAST detection settings".
6. Each query passes a positive self-control (whole-sequence recovery on `GITV01000968.1` at its expected coordinates); all 7780 passed.
7. Exact 19-mer and 21-mer counts come from an independent direct scan of both strands. They count the query starts whose entire k-mer lies inside the window and occurs in the unit; they are `DESCRIPTIVE_ONLY` and reported separately for every unit, so `KNOWN_BICC_COMPATIBLE` does not contaminate the `OTHER_TRANSCRIPT` counts.
8. Five composition-preserving shuffles (seeds 1-5) of every candidate and of the benchmark pass through the same native settings. They are `DESCRIPTIVE_ONLY`.

BLAST batches (all returned code 0):

| batch | queries |
|---|---|
| L300 | 2038 |
| L373 | 1965 |
| L400 | 1938 |
| L500 | 1838 |
| benchmark | 1 |
| controls_L300 | 10190 |
| controls_L373 | 9825 |
| controls_L400 | 9690 |
| controls_L500 | 9190 |
| controls_benchmark | 5 |

## Outputs

All CP3 outputs are gitignored under `results/bioinformatics/nb03/cp3/`. Full SHA-256 values of the canonical execution at `748bd81`, recomputed directly from the files. The first seven rows are byte-identical to the initial execution; the last three differ from it (see below):

| file | SHA-256 |
|---|---|
| `blast_hsps.tsv` | `514e6f34f99c3b4131e5d90b5dfe8b44bd64b74d285d208407dd5da0607221ff` |
| `candidate_unit_specificity.tsv` | `5d22a6d4af34d4de6f760f0f4d25c5751c0e74f2e09ed82b24e6a5fd2adf2ded` |
| `other_transcript_summary.tsv` | `8ce2949789b9f3f57c26ccda41b14258989895483d7483122377c3968c51797d` |
| `exact_kmer_summary.tsv` | `2595d96b7b09779673c3246f95be6760fce00198884f3c3eba5eaf53917d074d` |
| `shuffled_controls.tsv` | `a11b3df7125601e9b97d54404915fc4f3eb0d0ba118a200af93831e5eb84328c` |
| `benchmark_specificity.tsv` | `ea206eed11fafefb4a1f83590332732e1343019383961c55e5b0454ea22a89af` |
| `cp3_summary.json` | `8013cc52306530ef130859aec366d35f6d52edf54662c2c637fa715d80ca3157` |
| `run_manifest.json` | `19d280fc9b01c1e155d5b28825c84930792a76430018b245a6a0b98a9f2f2439` |
| `database_info.txt` | `b64a5badaaec1d84ddf0f792d1aae39207b196336f3ceed71b9304d4baa4f401` |
| `execution_log.json` | `3cbd689e82f76d0ead9b3284a863ea96b132f111ef3243ec551c75b1c351105a` |

The first eight are deterministic evidence outputs. `database_info.txt` and `execution_log.json` are execution/provenance metadata: they contain timestamps and absolute paths and need not be byte-identical between executions. They are deliberately not promoted to canonical evidence and are not hashed in the manifest. The manifest hashes the seven data/summary evidence files plus the ten query FASTAs and ten raw BLAST tables; all 27 declared entries were recomputed and matched. Its own hash is reported here, not inside itself. The initial execution's values for the three non-identical files were `680ebf1af243ec5ee2c7563ab290a909421ce457622c9e2a17f6f73312b7fcbd` (manifest), `ef58fcaaa176d23d0d680cebb184795161b7f6a01f3c3228fde44ee0722a00d0` (`database_info.txt`) and `22e23e0b86106bbd48eea80eda191d5b79cde6bd4b7004a569db04938784fb9b` (`execution_log.json`).

## Validation / QC

- Independent audit (read-only) of the pre-commit state: 403276 HSPs rebuilt from BTOP with zero discrepancies in coordinates, strand, lengths, mismatches, gaps, query-base fidelity, exact runs, query hashes and unit membership; zero unknown queries or subjects. Maximum difference between BTOP identity and BLAST `pident`: 0.0005 percentage points, i.e. rounding.
- Independent recomputation of every query-by-unit aggregate gave zero differences in `candidate_unit_specificity.tsv` (7779 rows), `other_transcript_summary.tsv` (7779), `benchmark_specificity.tsv` (1) and `shuffled_controls.tsv` (38900). The 7779 IDs equal the canonical CP2 list with no missing, extra or duplicated query; `cp3_summary.json` was re-derived from the tables. An independent re-implementation of the exact k-mer scan matched all 46680 rows.
- `independent_reexecution = BYTE_IDENTICAL_FOR_CANONICAL_EVIDENCE_OUTPUTS`: a second full materialization into a temporary directory reproduced the eight evidence outputs, including `run_manifest.json`, the ten query FASTAs and ten raw tables, byte for byte. `database_info.txt` and `execution_log.json` were not compared for identity, by design. No third execution was run for this record, because the implementation and the evidence outputs are unchanged since that audit.
- Tests, canonical WSL environment: `PYTHONPATH=src python -m pytest tests/test_nb03_specificity.py` gave `20 passed in 10.52s`; `PYTHONPATH=src python -m pytest` gave `371 passed in 110.75s`, with zero failures or skips. The audit baseline was 18 CP3 and 369 total; the two new tests cover an identity tie between HSPs of different lengths (in both input orders) and the registered tie rule.
- Provenance normalization: after amendment 3 (tie-break and `covered_nt` documentation, `cp3_outputs_changed: false`) the registry LF hash changed from `127106430145d5c8bed16b994c2372753908997baa8f181a1ebe86078b372cb7` to `ebce5b08354b1eb990da95b4a56e45cce018b3617197069906c6580cee832ef6`. The canonical CP3 was therefore re-executed with the official command (`python -m zeaguard.nb03_specificity`, same BLAST parameters, ten batches) on the committed `748bd81` code and registry. The new manifest records the final registry hash; relative to the initial manifest only `inputs.registry_sha256_lf` and the `git` block changed, and its 27 declared hashes (7 evidence files, 10 query FASTAs, 10 raw tables) are identical and match the files. The seven scientific outputs are byte-identical to the initial execution (`cp3_scientific_outputs_changed = false`). Full suite after the re-execution: `371 passed in 108.08s`, zero failures or skips. `nb03_specificity.py` is unchanged (LF SHA-256 `e8d04d5f2874241592187bc82eb79cce1bbaa9dd4bbc004f3c0c615864894824`).
- NB02 regression: `data/reference/nb02_dsrnase2_candidate_regions.tsv` SHA-256 `341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939`; `.fasta` SHA-256 `a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e`. No NB02 file differs from `master`.
- CP2 regression: `design_space.tsv` `142e5e856a6740b2a225e947cbe7feae181ae0cab01d0084af56c74465719ee4`; `benchmark_descriptor.tsv` `4cb81a3b9514ec77e1b1a5ce9add88df933696cde633288485da57a718b65272`; `cp2_summary.json` `7c390f0a7a81f080d52bf402e661674be579235230a06b910d52e59a12282239`; `run_manifest.json` `124ce71cc5f8d68fe1a7eb66f6d62630623d72bd3697268debac0cadb760a4e3`.

## Results

- Logical queries: L300 = 2038, L373 = 1965, L400 = 1938, L500 = 1838, so `DESIGN_SPACE` = 7779. The separate `REFERENCE_SET` is `BC-BENCH-0215-0587`. Shuffled controls: 38900 (7780 sources times seeds 1, 2, 3, 4, 5). Total HSPs: 403276.
- HSPs by membership and unit: `DESIGN_SPACE` 8114 `BICC_LIKE`, 16524 `KNOWN_BICC_COMPATIBLE`, 97933 `OTHER_TRANSCRIPT`, none for `DSRNASE1`, `DSRNASE2`, `DSRNASE3`; `REFERENCE_SET` 1, 2 and 17 (same units); `SHUFFLED_CONTROL` 19 `BICC_LIKE`, 27 `DSRNASE1`, 28 `DSRNASE2`, 7 `DSRNASE3`, 35 `KNOWN_BICC_COMPATIBLE`, 280569 `OTHER_TRANSCRIPT`.
- `BICC_LIKE` (`relationship_status = UNRESOLVED`): a hit is detected for all 7779 windows (no zero vector), with 2466 distinct vectors, so the unit has discriminating power in this evidence. `best_local_identity` spans about 0.68 (minimum) to about 0.91 (99th percentile) and does not saturate at 1.0. This describes detected homology only; it does not establish a paralogy or any other relationship.
- `DSRNASE2`: 7779 zero vectors; no HSP was detected for any real candidate under the declared settings. `DSRNASE1`: 7779 zero vectors. `DSRNASE3`: 7779 zero vectors. These zeros mean only "no homology detected under the configured candidate-native BLAST detection settings". Shuffled controls do produce occasional low-level hits to these units, so the search is not blind to chance matches. For a later checkpoint, the three `DSRNASE2` axes are constant across the analyzed space.
- `OTHER_TRANSCRIPT`: 48 zero vectors; `best_local_identity` is frequently 1.0 (7054 of 7779 windows) because of short perfect HSPs. It stays `DESCRIPTIVE_PLUS_MANUAL_REVIEW` and does not enter the decisional vector.
- Identity ties for the best identity occurred in 9535 query-by-unit cases of the candidate table, 2651 with different alignment lengths. They only affect the descriptive `aligned_nt_for_best_identity`.
- Exact k-mers: `KNOWN_BICC_COMPATIBLE` matches every window (the reference itself); `DSRNASE2`, `DSRNASE1` and `DSRNASE3` match none; `BICC_LIKE` and `OTHER_TRANSCRIPT` match some windows. For L400, windows with at least one 19-mer / 21-mer match: `BICC_LIKE` 1031 / 385, `OTHER_TRANSCRIPT` 911 / 901 of 1938.
- Benchmark: `BC-BENCH-0215-0587` (`REFERENCE_SET`, CDS 215-587, 373 nt, SHA-256 `e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb`) and `BC-L373-0215-0587` (`DESIGN_SPACE`) have identical sequences but different logical roles, and neither was deduplicated. Their specificity rows are identical in every column except `window_id`, `membership` and `query_role`. The benchmark `BICC_LIKE` vector as stored is `longest_exact_match = 20`, `covered_nt = 371`, `best_local_identity = 0.84905660377358494`, and the other units are zero vectors except `OTHER_TRANSCRIPT` and the `KNOWN_BICC_COMPATIBLE` self-hit. The benchmark is not added to any shortlist, defines no threshold and takes no part in future cells as a `REFERENCE_SET`.

## Interpretation

`G3_PASS` establishes that reproducible candidate-native specificity evidence exists for the preregistered strata, with the canonical basis enforced by provenance checks, and that no Pareto, cell, representative or shortlist was produced. The six decisional axes are available only from `BICC_LIKE` and `DSRNASE2`; every other unit, the exact k-mers, the controls and the diagnostics stay descriptive.

## What this run does NOT establish

RNAi efficacy, active or effective small RNAs, that any region is safe, free of off-target effects or biologically absent from a transcript, that co-silencing is impossible, the biological nature of `GITV01002238.1` or the observed sequence differences, ecological specificity, an optimal length or region, benchmark protocol verification, or suitability for synthesis. Pareto comparison, ordering, cells, representatives, the shortlist, recommendations, the Wet Lab handoff, Notebook 03 and CP5 reference artifacts are not implemented in this run.

## Anomalies / deviations

None in the scientific results. The independent audit found only traceability gaps, closed by this record: the missing run record, the undocumented best-identity tie rule, and the unhashed execution metadata (kept as metadata by decision). The synthetic non-equivalence diagnostic that motivated the native basis is preserved in `tests/fixtures/nb03_clipping_non_equivalence/` and in [its record](2026-10-08_nb03-pre-cp3-native-alignment-amendment.md). Subject bases were not re-compared with the database in the audit; subject coordinates and orientation were.

## Manifest `git.dirty` (PROVENANCE_PLATFORM_ARTIFACT)

The canonical manifest records `git.dirty = true`, preserved exactly as written. The interpretation is a platform artifact, not a corrupt manifest and not a modified analysis: `git status` in the Windows checkout was clean (0 entries) and `git -c core.autocrlf=true status` in WSL was also clean, while the WSL Git without that setting reported the CRLF working tree as modified (30 entries). No tracked file was scientifically modified during the execution, and the runner was not changed. The statement `dirty = false` is therefore not made; the manifest value is kept and explained here.

## Related decisions

[ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md), including the pre-CP3 amendment and the tie-handling paragraph, and the [criteria registry](../../../../config/nb03_design_criteria.yaml).

## Related Issue / PR / commits

CP0 `2d1ae8f48e9af684422faabaebed0f6486f658c5`, CP1 `099f751780283fecbc63da177c113aec9f6d60d5`, CP2 `4e141876c478a76aada15d3f4b89b80dc9f6863f`, amendment `b82dd0ddd55e62aa4111fcaca785e60c9362e1a3`. The CP3 code, tests, registry and ADR commit is `748bd81248be0e34c2fc4158a78660d5e4f1ba25`, the canonical scientific execution commit. A later documentation-only commit finalizes this record. No push, issue or PR was created.

## Evidence classification

1. `directly demonstrated`: raw BLAST tables, hashes, command log, audit reconstruction of every HSP, byte-identical second materialization and test results.
2. `derived/computed`: unit aggregates, vectors, k-mer counts, control summaries and the zero-vector counts.
3. `inferred/interpreted`: readiness for CP4 under the declared contract and the user's approval of the candidate-native basis.
4. `unresolved`: biological meaning of every homology hit and non-hit, the `BICC_LIKE` relationship, RNAi performance, and anything beyond the configured detection limit.
