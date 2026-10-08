# Run ID

`2026-10-08_nb03-pre-cp3-native-alignment-amendment`

## Date

2026-10-08, project timezone `America/Sao_Paulo`. Original command timestamps in UTC are preserved in the diagnostic fixture.

## Commit

Parent CP2 commit: `4e141876c478a76aada15d3f4b89b80dc9f6863f`. This record and the approved amendment are prepared before real CP3 materialization.

## Branch

`feat/nb03-bicc-candidate-regions`

## Execution status

`COMPLETED` for the original synthetic diagnostic. Real candidate specificity was not executed before this amendment.

## Question / objective

Determine whether clipping HSPs detected with the full CDS is generally equivalent to presenting the candidate sequence itself as a BLAST query, then record the user's approved canonical evidence basis before CP3.

## Inputs

[Preserved regression evidence](../../../../tests/fixtures/nb03_clipping_non_equivalence/): the original three synthetic FASTAs, two raw BLAST output tables, diagnostic JSON and reproducer script. All seven files were copied byte-for-byte from `results/bioinformatics/nb03/cp3_method_check/`, which remains preserved and gitignored.

The original JSON records SHA-256 hashes of the inputs, raw tables and reproducer, complete commands and timestamps. Test fixture hash checks normalize Windows checkout CRLF to the original LF representation.

## Configuration

BLAST+ 2.17.0; blastn task, DUST disabled, word size 11, E-value report limit 10, both strands, max_target_seqs 100000, num_threads 1. One synthetic subject of 2337 nt. Random seed 193 generated the 2337 nt query. Subject positions 501-510 were modified; the tested 400 nt query is the original interval 501-900.

## Method

The original diagnostic executed one full-query BLAST and one candidate-query BLAST. NB02 BTOP footprints and unit aggregation were used to compare the same subject. No TSA or biological NB03 candidate was searched in this diagnostic. Existing clipping code and the reproducer are retained for `FULL_CDS_CLIPPED_ALIGNMENT_DIAGNOSTIC`, `DESCRIPTIVE_ONLY / QA_ONLY`.

## Results

The union coverage was 400 nt after clipping full-query HSPs, versus 390 nt from native-query HSPs. Both longest exact matches were 390 nt. The aggregate best identity was 1.0 in both cases, provided by a 12 nt HSP in the full-query case and a 390 nt HSP in the native-query case. The primary full-query HSP, clipped to the interval, had identity 0.9800995024875622; the primary native-query HSP had identity 1.0.

The regression asserts possible divergence and canonical-source enforcement. It does not require a fixed 10 nt difference or generalize it to biological candidates.

## Approved methodological correction

Full-CDS clipping was proposed as an optimization under an equivalence hypothesis. The synthetic counterexample falsifies general equivalence. Flanking context can affect HSP formation or extension. Because the experimental sequence evaluated is the candidate itself, candidate-native HSPs supply the canonical specificity metrics.

The registry now requires `specificity_evidence_basis = CANDIDATE_NATIVE_ALIGNMENT`. Canonical metrics are `longest_exact_match`, `covered_nt`, `best_local_identity` and descriptive `aligned_nt_for_best_identity`; the latter is HSP alignment-column length. Full-CDS-derived metrics cannot supply signatures or joint axes. The evidence basis is an explicit required field, with no implicit native default.

The C05/C06/C17/C18/C25 amendment was recorded before analysis of all 7779 biological windows. CP2 intervals already exist, so `applied_before_window_generation` is explicitly false while `applied_before_candidate_specificity_analysis` is true. This is a pre-analysis methodological correction based on synthetic evidence, not an adjustment based on biological candidate results.

Controls preserve seeds 1-5 and descriptive status, with five composition-preserving shuffles of each candidate and of the separate benchmark. Each query is evaluated natively; exact 19/21-mer descriptors remain independent of BLAST. Memberships, detection settings, six separate axes, count-only observed-difference policy and descriptive benchmark overlap are preserved.

## Validation / QC

Regression and provenance-guard tests are in [test_nb03_evidence_basis.py](../../../../tests/test_nb03_evidence_basis.py). Before the separate amendment commit and real CP3 execution, `PYTHONPATH=src python -m pytest` reported `351 passed in 108.04s`, with zero failures or skips. NB02 TSV and FASTA hashes were reconfirmed as `341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939` and `a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e`. `git diff --check` was clean. No real candidate-native TSA search preceded these checks.

## Interpretation and limitations

The evidence establishes possible methodological non-equivalence. It does not characterize real BicC specificity, RNAi efficacy, read support, evolutionary relationships or a universal discrepancy magnitude. The diagnostic is excluded from all selection variables.

## Related decisions

[ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md) and [criteria registry](../../../../config/nb03_design_criteria.yaml).

## Evidence classification

1. `directly demonstrated`: saved raw HSPs, recorded commands/timestamps and preserved input hashes.
2. `derived/computed`: coverage and identity differences under the two query bases.
3. `inferred/interpreted`: the approved choice of candidate-native alignments as the evidence basis.
4. `unresolved`: specificity and biological performance of actual NB03 candidates, pending downstream execution and experiments.
