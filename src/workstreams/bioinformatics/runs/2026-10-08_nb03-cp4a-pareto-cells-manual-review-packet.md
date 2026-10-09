# Run ID

`2026-10-08_nb03-cp4a-pareto-cells-manual-review-packet`

## Date

2026-10-08, project timezone `America/Sao_Paulo`.

## Commit

The CP4A materialization ran on `b8d15f36338922f870ec9f0bdd8004c1c04082ed` (`selection_policy_commit`: the commit that froze amendment 4 before any CP4A result existed) with the CP4A implementation still uncommitted. The commit that adds this record also adds that implementation. Earlier checkpoints: CP2 `4e141876c478a76aada15d3f4b89b80dc9f6863f`, CP3 code and registry `748bd81248be0e34c2fc4158a78660d5e4f1ba25`, CP3 provenance record `d867a666661ddb611b977a260729a85a089d2d45`.

## Branch

`feat/nb03-bicc-candidate-regions`

## Execution status

`COMPLETED`. `G4A_PASS`; next state `CP4_MANUAL_REVIEW_REQUIRED`. `G4_PASS` is not declared: no manual review has taken place.

## Question / objective

Freeze, mechanically and before any qualitative review, the candidate structure defined by the preregistered policy: six-axis Pareto status within each length stratum, maximal contiguous cells, the nondominated priority set, observed-difference tiers and a pending manual-review packet for the nominal L400 stratum. The checkpoint selects nothing.

## Inputs

Certified outputs of earlier checkpoints, each verified against its own run manifest before any calculation. Nothing was re-run: no BLAST, exact k-mer scan or shuffle.

| input | SHA-256 |
|---|---|
| CP2 `design_space.tsv` | `142e5e856a6740b2a225e947cbe7feae181ae0cab01d0084af56c74465719ee4` |
| CP2 `benchmark_descriptor.tsv` | `4cb81a3b9514ec77e1b1a5ce9add88df933696cde633288485da57a718b65272` |
| CP3 `candidate_unit_specificity.tsv` | `5d22a6d4af34d4de6f760f0f4d25c5751c0e74f2e09ed82b24e6a5fd2adf2ded` |
| CP3 `other_transcript_summary.tsv` | `8ce2949789b9f3f57c26ccda41b14258989895483d7483122377c3968c51797d` |
| CP3 `exact_kmer_summary.tsv` | `2595d96b7b09779673c3246f95be6760fce00198884f3c3eba5eaf53917d074d` |
| CP3 `benchmark_specificity.tsv` | `ea206eed11fafefb4a1f83590332732e1343019383961c55e5b0454ea22a89af` |
| CP3 `cp3_summary.json` | `8013cc52306530ef130859aec366d35f6d52edf54662c2c637fa715d80ca3157` |
| CP3 `blast_hsps.tsv` (read only for the HSP reference) | `514e6f34f99c3b4131e5d90b5dfe8b44bd64b74d285d208407dd5da0607221ff` |
| CP3 `run_manifest.json` | `19d280fc9b01c1e155d5b28825c84930792a76430018b245a6a0b98a9f2f2439` |

The CP3 manifest records the registry used at CP3 time (`ebce5b08354b1eb990da95b4a56e45cce018b3617197069906c6580cee832ef6`). The registry changed afterwards only by amendment 4 (downstream CP4 semantics, `cp3_outputs_changed: false`) and does not invalidate the certified CP3 outputs.

## Configuration

- Criteria registry [nb03_design_criteria.yaml](../../../../config/nb03_design_criteria.yaml), LF SHA-256 `5e2fa734ff55b1da57a62db592452c9915651ea5dfe5d12033cb4f34016d3b43`, and [ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md) with amendment 4.
- Canonical environment: WSL2 Ubuntu-24.04, conda environment `zeaguard`, Python 3.12.14.

## Method

Entry point: [nb03_selection.py](../../../zeaguard/nb03_selection.py).

```bash
PYTHONPATH=src python -m zeaguard.nb03_selection
```

1. **Join.** The 7779 DESIGN_SPACE windows of the four strata come from CP2 and must equal, with no missing, extra or duplicate id, the CP3 DESIGN_SPACE ids; geometry, evidence basis and sequence hash must agree. The `REFERENCE_SET` benchmark stays outside.
2. **Pareto, separately per length.** L300, L373, L400 and L500 are never compared with each other. Six axes, all lower is better: `longest_exact_match`, `covered_nt` and `best_local_identity` of BICC_LIKE and of DSRNASE2, taken as stored (no rounding, normalisation, sum, weight or score). A dominates B if it is no worse on all six and strictly better on at least one; equality is not dominance. Each window receives `pareto_status` (`NONDOMINATED` or `DOMINATED`) and `n_dominators`; no layered Pareto rank is computed.
3. **DSRNASE2 axes: OBSERVATION.** `DSRNASE2 = (0, 0, 0)` for all 7779 windows, verified before the Pareto. The three frozen axes are formally preserved and do not discriminate dominance in this observed dataset. This is an observation from CP3, not a methodological change.
4. **Priority set.** `PRIORITY_SET` = the NONDOMINATED DESIGN_SPACE windows. Dominated windows stay in every table and in the cells; they do not advance to nominal manual review, and the label means only "Pareto-dominated under the preregistered specificity axes".
5. **Difference tier.** For NONDOMINATED windows the tier equals `count_intersected_observed_sequence_differences` (number of the seven observed sequence differences that the window intersects; no dense rank, no threshold, no exclusion); for DOMINATED windows it is `NA`. A low count never rescues a dominated window. Permitted reading: greater robustness to the two currently observed sequences; never population, allele or conservation claims.
6. **Cells.** A cell is a maximal contiguous run of DESIGN_SPACE windows with the same target, the same length, consecutive CDS starts (step 1 nt) and an identical decisive signature `(count, bicc_like_vector, dsrnase2_vector)`. A signature that reappears after an interruption starts a new cell. Cells are materialized for all four strata, including dominated windows; each cell carries exactly one Pareto status (a mixed cell would be an error). Cell membership is grouping, not preference.
7. **No automatic representative.** The algorithm chooses none; every member remains available and the schema has no representative column.
8. **Nominal manual review.** L400 AND NONDOMINATED, all members of those cells and all difference tiers present. Every row has `manual_review_status = PENDING`. L300, L373 and L500 are analytical sensitivity strata and do not enter the nominal packet.
9. **Descriptive layers.** `OTHER_TRANSCRIPT` stays `DESCRIPTIVE_PLUS_MANUAL_REVIEW`; exact 19-mer and 21-mer counts stay `DESCRIPTIVE_ONLY`; DSRNASE1, DSRNASE3, GC, homopolymer, DUST, position, benchmark overlap, `fraction_unaffected`, HSP counts and E-values stay descriptive. None of them is in the Pareto, the signature, the cells, the tiers or the display order.
10. **Display order.** Files are ordered by length, Pareto status, difference count, cell start, CDS start and window id. This is `CANONICAL_DISPLAY_ORDER_ONLY`: not a ranking and not a tie-breaker; scientific ties remain ties.

## Outputs

All under `results/bioinformatics/nb03/cp4a/`, gitignored. SHA-256:

| file | SHA-256 |
|---|---|
| `pareto_by_stratum.tsv` | `aba1f87a4e5daa96b7039155c7ff0d9d0d199fc6fb7e9ff7345817eda3d64873` |
| `cells.tsv` | `87a1fbb18c6a4238feefdd70825e0c998cd03626a000b9af9890aaad50bbe828` |
| `cell_members.tsv` | `1c037ec497aa7fe2f77771d994ce6b6f8ee0e452bdf4f80734f141b5c1b45cec` |
| `manual_review_packet.tsv` | `d1c9ea40ccc4b09083f2b107bac4188ab92a6a98dcb00375d92b5658aa2132fc` |
| `other_transcript_hsp_reference.tsv` | `8d7108f7ed187704a49d7d5b997ff75036a9bed87854a367e6d849fa4d340b7a` |
| `benchmark_comparison.tsv` | `61f81a2f50a8b990336a397437dac79165eed26cfa19e8587cb04b3f84f02d31` |
| `cp4a_summary.json` | `83b4dc0798cb602dc56d1beafb1b585c48a0a2af885eb3ecc7545f3425d298da` |
| `run_manifest.json` | `e2ff9292271fc229ce4bb69f05acf8e064a897acaff77b326f89c4aabb55820c` |

`execution_metadata.json` carries timestamps and is not a deterministic output. The manifest hashes the other outputs, the registry, the inputs and the implementation, and records `selection_policy_commit`.

## Validation / QC

- Deterministic outputs were reproduced byte for byte in an independent execution into a temporary directory (all seven data files plus the run manifest). The test suite repeats this comparison between two fresh executions.
- The Pareto status of every window was recomputed by an independent brute-force implementation in the tests; cells were checked for contiguity, maximality, one signature and one Pareto status each.
- Full suite: `403 passed`, zero failures or skips (392 before CP4A plus 11 real-data tests; the kernel has 21 synthetic contract tests from the amendment). Counts in the single regression-snapshot test are a computational snapshot, not a policy definition.
- NB02 regression: TSV `341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939`, FASTA `a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e`; no NB02 file changed.
- CP2 outputs unchanged (`cp2_summary.json` `7c390f0a7a81f080d52bf402e661674be579235230a06b910d52e59a12282239`, `run_manifest.json` `124ce71cc5f8d68fe1a7eb66f6d62630623d72bd3697268debac0cadb760a4e3`, plus the two hashes above) and the certified CP3 outputs unchanged.

## Results

Pareto status per stratum (7779 windows):

| stratum | role | total | NONDOMINATED | DOMINATED |
|---|---|---|---|---|
| L300 | sensitivity only | 2038 | 39 | 1999 |
| L373 | sensitivity only | 1965 | 26 | 1939 |
| L400 | nominal ranking stratum | 1938 | 10 | 1928 |
| L500 | sensitivity only | 1838 | 17 | 1821 |

L400: 670 distinct decisive signatures; 1132 cells; 9 priority cells; 10 priority windows. Difference tiers among the 10 NONDOMINATED windows: tier 0 = 2, tier 1 = 4, tier 3 = 4. Cell sizes (members per cell):

| size | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cells | 826 | 74 | 134 | 32 | 17 | 23 | 11 | 9 | 1 | 2 | 3 |

826 singleton cells; the largest cell has 11 members. The sensitivity strata have 18 (L300), 12 (L373) and 11 (L500) distinct nondominated signatures, as detailed in `cp4a_summary.json`, which also holds their cell-size and difference-count distributions.

**Manual-review packet.** `manual_review_packet.tsv` has 10 rows (9 cells), every one with `manual_review_status = PENDING`. No human decision is recorded. `other_transcript_hsp_reference.tsv` lists the 117 OTHER_TRANSCRIPT HSPs of these windows, linked by `window_id`, so that the hits can be reviewed qualitatively.

**OTHER_TRANSCRIPT (descriptive observation, no cutoff).** All 10 windows have at least one hit. `n_hsps` ranges from 8 to 14, `longest_exact_match` from 17 to 73 and `covered_nt` from 74 to 199. `best_local_identity` is 1 in every window, because of short perfect local HSPs. The 10 windows involve 33 distinct subjects; `GITV01049170.1` occurs in 8 of the 10 windows. No subject is interpreted as a biological risk by this record.

**Exact k-mers (`DESCRIPTIVE_ONLY`, no exclusion rule).** In the packet, BICC_LIKE, DSRNASE1, DSRNASE2 and DSRNASE3 have exact 19-mer and 21-mer counts of 0 in every window. KNOWN_BICC_COMPATIBLE has 382 (19-mer) and 380 (21-mer) in every window. OTHER_TRANSCRIPT has a 19-mer median of 5 and maximum of 55, and a 21-mer median of 3 and maximum of 53, with matches in 5 of the 10 windows.

**Benchmark (separate `REFERENCE_SET`).** `BC-BENCH-0215-0587` has BICC_LIKE `longest_exact_match = 20`, `covered_nt = 371`, `best_local_identity = 0.84905660377358494`, DSRNASE2 `(0, 0, 0)` and 0 intersected observed differences. It has no Pareto status, no cell and no tier, and is not a candidate. `BC-L373-0215-0587` is a DESIGN_SPACE window with the same sequence but a different logical role; it is DOMINATED, sits in cell `BICC-L373-C0114` and is outside the nominal manual review.

## Interpretation

`G4A_PASS` establishes that the candidate structure was derived mechanically from the preregistered policy: Pareto before differences, cells as defined by amendment 4, the nondominated priority set and a complete pending review packet, with deterministic outputs and intact earlier checkpoints. The next state is `CP4_MANUAL_REVIEW_REQUIRED`.

The frontier is small because the three BICC_LIKE axes carry all the discrimination (the DSRNASE2 axes are constant) and because the signature changes almost every window, which makes most cells singletons. Both are consequences of the preregistered definitions, observed here and not adjusted.

## What this run does NOT establish

That any window is better, safe, effective or recommended; RNAi efficacy; the biological meaning of any OTHER_TRANSCRIPT hit, k-mer count or observed difference; cross-silencing; population robustness; an optimal region or length. No manual review, approval, rejection, representative, shortlist, recommendation or Wet Lab handoff exists. CP4B, CP5, Notebook 03 and the reference artifacts under `data/reference/` are not implemented.

## Anomalies / deviations

None in the results. The CP4A implementation was written before the 392-test preflight was repeated on the modified tree; the 392 tests had passed on the same clean tree immediately before the amendment commit, and the final suite is 403.

## Related decisions

[ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md), including amendment 4 (pre-CP4A cell and prioritization semantics), and the [criteria registry](../../../../config/nb03_design_criteria.yaml).

## Related Issue / PR / commits

Amendment 4: `b8d15f36338922f870ec9f0bdd8004c1c04082ed`. CP3: `748bd81248be0e34c2fc4158a78660d5e4f1ba25` and `d867a666661ddb611b977a260729a85a089d2d45`. The CP4A commit is the one that adds this record. No push, issue or PR was created.

## Evidence classification

1. `directly demonstrated`: certified input hashes, output hashes, byte-identical independent execution and test results.
2. `derived/computed`: Pareto status, dominator counts, cells, tiers and all counts above.
3. `inferred/interpreted`: readiness for manual review under the preregistered, user-approved policy.
4. `unresolved`: the qualitative meaning of every OTHER_TRANSCRIPT hit, the nature of the observed sequence differences, and any biological performance of the windows.
