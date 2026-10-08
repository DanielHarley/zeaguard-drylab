# Run ID

`2026-10-07_nb02-dsrnase2-candidate-regions`

## Date

2026-10-05 (checkpoints 1 to 4) and 2026-10-07 (the OTHER_TRANSCRIPT review decisions, checkpoint 5 and the consolidation of this record, ADR 0005, the notebook and the documentation).

## Commit

Base commit `9e0a7a2f2b35adfded6fe79c17f0a74e346603bf` (`master`, the NB01 merge), with the NB01 BTOP hotfix `6239ab4` merged in from `master` before checkpoint 4. The checkpoint commits are listed under Related commits; the hand-off artefacts were generated from the certified `dc588d4` state and remain uncommitted pending the CP5 consolidation step described here.

## Branch

`feat/nb02-dsrnase2-dsrna-candidate-regions`, created from the updated `master`. The semantic type `feat` follows the change-type decision order in `.agents/commits_and_PR_instructions.txt` (item 7: new capability, pipeline step and persisted artefacts). The `<type>/<kebab-name>` shape follows the existing branches. The name says `candidate-regions`, not `design`, because NB02 selects region and length while the construct architecture belongs to the Wet Lab.

## Execution status

`COMPLETED`

`COMPLETED` describes CP1 to CP4 and the scientific construction of CP5. At the consolidation of this record, operational closure still requires the CP5 commit, the final reproducibility gate and the final execution of Notebook 02. It does **not** mean that any region is known to be effective: no efficacy was measured or predicted, no ecological off-target analysis was run, and the identity of the dsRNase-2 locus remains `AMBIGUOUS` from NB01 ([ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md)).

All analyses ran in the canonical Linux environment (conda env `zeaguard` from the unmodified `environment.yml`, WSL2 Ubuntu 24.04, Python 3.12.14, BLAST+ 2.17.0 including `dustmasker`). No new dependency was added.

## Question / objective

Which regions of the operational Dmai dsRNase-2 CDS are candidates for a nominal 400 nt dsRNA, how do they compare with the published 330 nt fragment, and how does each inclusion or exclusion trace back to a criterion fixed before the candidates were visible?

## Inputs

- Versioned hand-off pin `data/reference/nb01_dsrnase2_operational_reference.json`, sha256 (LF) `4ea481fb747f91ca22fc55fda2ab684884952650ad1cfa31cf3fe268011c9edb`.
- Criteria registry `config/nb02_design_criteria.yaml`, sha256 `70b2ae428ce2b3d9daad2495ee761476c8c400e4f54da68cb1dce5059ef46097`, committed before any candidate window existed.
- TSA `data/external/tsa.GITV.1.fsa_nt.gz`, sha256 `22d0cff8d0867344a76d615bdca62c31ce0f9133f574058e8daa6b6e41925ae6` (56,117 records), and the versioned published cDNAs in `data/reference/target_anchor_sequences.fasta`.
- Operational CDS `GITV01008430.1` 53-1477 on the minus strand, 1425 nt, sha256 `bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7`; sibling `GITV01012450.1` CDS sha256 `8c18687410248fb6036020cc50fc7577d23c7c44b9d0f30cc0677b95b28960f8`.
- Supplementary Table S1 of Dalaison-Fuentes et al. 2023 (`Dalaison-Fuentes2023_S1_mmc1.pdf`, sha256 `b2859b4ad39383136fd73c0e7623c095d3b5324da1547385eca215268d6fe429`) for the benchmark primers.
- Review decisions `config/nb02_manual_review_decisions.tsv` and limitations `config/nb02_candidate_limitations.tsv`.
- Full hashes per checkpoint: the `run_manifest.json` files under `results/bioinformatics/nb02/`.

## Configuration

[ADR 0005](../decisions/0005-nb02-dsrnase2-candidate-region-policy.md) (Proposed). ADR 0003 and ADR 0004 were not modified. `environment.yml` was not modified; `config/repro.yaml` gained a `dustmasker` probe and the new required paths.

Three dated amendments to the registry, all with `changes_thresholds_roles_or_policy: false`, all before the stage they affected: (1) the C03 redundancy note and the split of the benchmark provenance into `benchmark_sequence_verification` and `experimental_protocol_verification`; (2) the machine-readable C13 tercile boundaries and C16 `dustmasker` settings, before any window was generated; (3) the biological units of specificity and the within-unit aggregation, **before the first BLAST result existed**.

## Method

Five checkpoints, each authorised separately, with a mandatory stop between them.

1. **CP1** — preflight, contract and pre-registration: `zeaguard.nb02_reference` re-derives the pin from the hash-validated TSA (CDS hashes, the seven variable positions, the benchmark primer span) and fails hard on any divergence; `zeaguard.nb02_criteria` validates the frozen registry and holds the policy kernel (Pareto dominance within one length stratum, the cell signature and the review gate).
2. **CP2** — `zeaguard.nb02_design`: the candidate space (every interval of 300-500 nt, step 1 nt, 206,226 windows) with composition, known variants, potential small-RNA windows and position as descriptors, in four length strata.
3. **CP3** — `zeaguard.nb02_specificity`: BLASTn of the operational CDS and five composition-preserving shuffles against one combined database (TSA plus published cDNAs), alignments rebuilt from BTOP, clipped to each candidate interval and aggregated per biological unit.
4. **CP4** — `zeaguard.nb02_cells`: contiguous equivalence cells, the pre-registered ordering, and the provisional candidates with the OTHER_TRANSCRIPT evidence their review needs.
5. **CP5** — `zeaguard.nb02_handoff`: the shortlist closed under the review gate and written as the versioned Wet Lab hand-off.

Entry points: `python -m zeaguard.nb02_design`, `... nb02_specificity`, `... nb02_cells`, `... nb02_handoff`. Notebook 02 only loads and displays the stored results.

## Outputs

- Versioned: `data/reference/nb02_dsrnase2_candidate_regions.tsv` (sha256 `341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939`) and `.fasta` (sha256 `a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e`), both in coding/sense orientation without tails.
- Gitignored, under `results/bioinformatics/nb02/`: the CP2 window space (`window_space_summary.tsv`, `strata_windows.tsv`, `benchmark_window.tsv`, `position_tracks.tsv`), the CP3 evidence (`cp3/hsp_provenance.tsv`, `specificity_windows.tsv`, `benchmark_specificity.tsv`, `subject_summary.tsv`, `position_specificity_tracks.tsv`, `manual_review.tsv`, `shuffled_control_summary.tsv`, `other_transcript_descriptive_summary.json`, `kmer_selfcheck.json`), the CP4 cells (`cp4/cells_L400.tsv`, `provisional_candidates.tsv`, `other_transcript_review_evidence.tsv`, an inspection-only FASTA) and a `run_manifest.json` per checkpoint with the input and output hashes.

## Validation / QC

1. `pytest`: 108 passed before any NB02 change; 238 passed, 0 failed and 0 skipped in the validated CP5 readiness run (the 108 baseline, 4 from the NB01 BTOP hotfix and 126 new NB02 tests). Scope: structural and logical checks on synthetic data plus the recorded real values, not scientific validity.
2. `repro` environment gate: all checks PASS with `allow_dirty=False` after each checkpoint commit, including the new `dustmasker` probe.
3. Contract: the CDS and protein hashes of both records, the seven variable positions and their classes, and the benchmark span and sha256 are re-derived from the TSA on every run; the optional cross-check against the gitignored NB01 hand-off table returns `MATCH` (7 rows) after converting the transcript-strand bases to coding orientation.
4. Benchmark: the Table S1 primers match exactly and uniquely in the operational CDS (814-832 and 1123-1143), the span is 330 nt with sha256 `97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179`, the Table S1 amplicon lengths of 330 and 360 bp agree with the mapped span plus two 15 nt T7 tails, and the same body is found in the published cDNA `TRINITY_DN22752_c0_g2_i1`.
5. Window space: the enumerated 206,226 windows match the closed form, and every length stratum has exactly `1425 - L + 1` windows.
6. Specificity: an independent exact k-mer scan of the whole TSA agrees with the BLAST/BTOP reading in every class (1,407 19-mers and 1,405 21-mers in `KNOWN_DSRNASE2_COMPATIBLE`, zero elsewhere, no disagreement in either direction). A positive control, querying the published dsRNase-1, dsRNase-3 and BicC cDNAs against the same database, recovers all unit members including `GITV01000968.1` as BICC, so the zero vectors are not a classification or database failure.
7. Cells: the stratum cells are contiguous, disjoint and cover every window; adjacent cells differ in signature; changing only the OTHER_TRANSCRIPT hits changes neither the cell nor the Pareto position (tested).
8. Determinism: CP2, CP3, CP4 and CP5 were each re-run into a scratch directory and compared hash by hash; all outputs identical.
9. Review gate: the hand-off refuses to close without a versioned `APPROVED` OTHER_TRANSCRIPT decision (tested), and every sequence in the hand-off is verified against its sha256 and against the operational CDS.

## Results

1. **Candidate space**: 206,226 windows of 300-500 nt; 4,174 fully described in the four strata. No window of any stratum is masked by `dustmasker`, the longest homopolymer anywhere is 6 nt, and GC ranges from 0.3633 to 0.5067 across the space.
2. **Specificity**: of the 44 HSPs of the operational CDS, 3 fall on the `KNOWN_DSRNASE2_COMPATIBLE` records and 41 on `OTHER_TRANSCRIPT`. **No HSP was found against DSRNASE1, DSRNASE3 or BICC**, so the clipped vector of every decisional unit is `(0, 0, 0)` for every candidate and the specificity level of the hierarchy does not separate any candidate. The OTHER_TRANSCRIPT background is 41 HSPs in 41 distinct records, longest exact tract 8-18 nt (median 15), with no exact 19-mer or 21-mer. The five shuffled controls gave 17-31 HSPs each with a longest exact tract of 18-20 nt, the same order of magnitude.
3. **Cells**: 9 contiguous cells in the 400 nt ranking stratum, all in the Pareto front. Two are tied at the top, both variant-free and sharing signature `SIG-006` while remaining separate cells because they are not adjacent: `D2C-L400-006` (66 windows, starts 351-416) and `D2C-L400-008` (56 windows, starts 817-872). Together they hold the 122 variant-free windows of the stratum. The remaining cells carry 1 to 5 known variable sites.
4. **Review**: both provisional candidates were reviewed against the complete TSA on 2026-10-07 and recorded as `APPROVED` (reviewer Daniel Harley, evidence sha256 `5b377739627c1eb4b10ce484c21ce714c903d77720a5a5a78dbc138cce46e2d4`). The recorded justification is that the concentration of short HSPs alone does not meet the evidence required for `STRONG_INTRASPECIES_SPECIFICITY_CONCERN`, and that the shuffled controls show exact tracts of the same order of magnitude, so those values are not turned into a post-hoc cutoff.
5. **Hand-off**: `REFERENCE_SET` holds `D2-BENCH-0814-1143` (CDS 814-1143, 330 nt). `RECOMMENDED_SHORTLIST` holds exactly two candidates, `D2-L400-0351-0750` (CENTRAL, GC 0.405, longest OTHER_TRANSCRIPT exact tract 18 nt) and `D2-L400-0817-1216` (3_PRIME, GC 0.483, 17 nt). No candidate from the one-variant group was added to lengthen the list.
6. **Convergence**: `D2-L400-0817-1216` overlaps the published benchmark by 327 of its 330 nt, starting 1 nt after the defined synonymous variant at CDS 816 that the benchmark contains. This is recorded as an observation and **did not participate in the ranking**: the benchmark is not part of the ordering and never counts as a recommended candidate.

## Interpretation

Conditional on ADR 0005 and the recorded inputs, all 122 variant-free windows at the nominal 400 nt length fall into two decision-equivalence cells (66 windows in `D2C-L400-006` and 56 in `D2C-L400-008`), from which one representative per cell was selected for the recommended shortlist. The selected representatives have identical decisional vectors and zero variant counts, so they are reported as a tie rather than ranked (`derived/computed`). The absence of any detected homology with dsRNase-1, dsRNase-3 and BicC is consistent with NB01, where dsRNase-2 was not alignable at nucleotide level with its paralogs (`directly demonstrated` for the search, `inferred/interpreted` for the biological reading).

That an independent, benchmark-blind procedure landed on a region overlapping the published fragment by 327 nt is a convergence worth recording, but it is not evidence that either region works: the benchmark's own experimental claim rests on protocol statements that were not verified against the primary text, and its oral co-feeding design also delivers BicC dsRNA, so its endpoints are not attributable to the dsRNase-2 fragment alone (`unresolved`).

"No homology detected" means no homology detected at the declared search sensitivity, never safety (`inferred/interpreted`). The concentration of short OTHER_TRANSCRIPT matches around CDS 500-540 and 1050-1081, recurrent across several TSA records in the second case, is recorded as a limitation of both recommended regions and remains biologically `unresolved`.

## Hand-off to the next stage

- **Versioned artefacts**: `data/reference/nb02_dsrnase2_candidate_regions.tsv` and `.fasta`, both in coding/sense orientation and without any tail or vector sequence.
- **What the Wet Lab decides**: the molecular architecture (linear, hairpin, protected-end, dual-loop or other), primers and T7 tails, promoter, loop, terminator, restriction sites, codon optimisation and plasmid backbone. NB02 deliberately selected region and length only.
- **Anchoring flexibility**: each recommended candidate is the representative of a contiguous cell, chosen by the frozen rule (smallest start at fixed length). Every window of the same cell has identical decisive attributes, so the start may be moved inside `cell_start_min`-`cell_start_max` (351-416 and 817-872) without changing variants or specificity; the descriptors do vary slightly (GC 0.405-0.423 and 0.465-0.488).
- **Before synthesis**: the dsRNA will be made from the cDNA of the laboratory colony, not from the TSA. Any chosen region should be confirmed by sequencing that colony, and the 2,000+ nt extension of `GITV01012450.1` and the unresolved nature of the two accessions remain open from NB01.
- **Still outside NB02**: ecological off-target against non-target organisms, for the regions that survive, and any efficacy measurement or prediction.

## What this run does NOT establish

- That any recommended region silences Dmai dsRNase-2, or does so better than the published fragment.
- An optimal dsRNA length: 300-500 nt is a defensible space and 400 nt a project convention, neither is a biological optimum.
- That 5', central or 3' regions differ in efficacy: position is a descriptor and no controlled comparison exists in *D. maidis*.
- That the absence of detected homology with the paralogs, BicC or other transcripts implies the absence of cross-silencing.
- The scientific calibration of any numeric value in the registry; the 60 bp floor, the 19/21 nt indicator and the 21 nt sub-window unit come from Coleoptera and Diptera.
- The experimental protocols of the benchmark: they are `PROJECT_PROVIDED_NOT_AGENT_VERIFIED`.
- Successful execution and reproducibility do not demonstrate scientific validity.

## Anomalies / deviations

1. **No homology against the decisional units.** Every DSRNASE1, DSRNASE3 and BICC vector is zero, so the specificity level of the hierarchy, the most elaborate part of the policy, had no discriminating power in this dataset. The ordering was decided entirely by the variant counts. A positive control confirmed the units are reachable in the database.
2. **The `fraction_unaffected` lifting is undecided.** C12 is a window-level metric and no convention was pre-registered for aggregating it to a cell. It did not bind here because every window of both top cells has `fraction_unaffected = 1.0`. If a future top tier contains cells with variants, that convention must be decided before the results are seen.
3. **The representative inside a cell is arbitrary** among decisively identical windows; the frozen rule (smallest start) was applied and the full cell extent is reported so the choice is visible and reversible.
4. **BicC in the TSA.** `GITV01000968.1` was added to the BICC unit before the first BLAST, following the NB01 high-confidence resolution, so homology with BicC could not be split between a decisional group and the unreviewed background. The positive control also found `GITV01002238.1` at 79.7 % identity over 2,382 nt to the BicC cDNA, classified as `OTHER_TRANSCRIPT`; no dsRNase-2 candidate reaches that record.
5. **NB01 BTOP hotfix.** While building the clipped alignments, `btop_substitutions` in the NB01 module was found to advance the query position on the wrong gap operation. It was fixed on a separate branch (`6239ab4`) and merged before CP4. The historical NB01 crosscheck is unaffected: the 3 HSPs it compared have `gaps = 0` and no `I` or `D` column, and the pre-fix and post-fix functions return identical positions for each (class `NOT_AFFECTED_NO_GAPPED_HSPS`). NB02 uses its own BTOP reader, tested with gaps in both directions.
6. **The benchmark main text was not read.** Two attempts failed (a ScienceDirect captcha that was not bypassed, and the CONICET repository handle `11336/221063` unreachable from this machine). The protocols and the Results 3.4 endpoints are stored unchanged with `experimental_protocol_verification = PROJECT_PROVIDED_NOT_AGENT_VERIFIED` and an explicit promotion condition.
7. **The three literature reviews that shaped the policy** (position, specificity, length and architecture) are recorded in the registry as conclusions supplied by the project with `CITATIONS_NOT_PROVIDED`. The independent sources checked for this run were read at abstract level only.
8. **Evidence database out of date.** Line 37 of `evidence_database.xlsx` records the dsRNase-2 dsRNA as injection only, while the benchmark is now described as also used in oral co-feeding. Updating it belongs to the evidence workstream and was not done here.
9. **BioProject discrepancy** (`data/reference/manifest.json` lists PRJNA579843, the GenBank record of `GITV00000000.1` lists PRJNA631706) remains an unresolved provenance limitation from NB01; NB02 depends on the TSA by hash, not on the BioProject.
10. The gate snapshot is invalidated by every commit, so notebook 00 was re-run after each checkpoint commit; `artifacts/` is gitignored.

## Related decisions

[ADR 0005](../decisions/0005-nb02-dsrnase2-candidate-region-policy.md) (new, Proposed), [ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md) and [ADR 0003](../decisions/0003-nb01-target-identity-resolution-policy.md) (both unchanged), [NB01 run record](2026-10-03_nb01-dsrnase2-identity.md).

## Related Issue / PR / commits

`not recoverable` (no issue). Commits on this branch: `4a97aff` (pin and contract), `3c62f2d` (criteria registry and review gate), `240db7e` (ADR 0005 draft), `e480fe9` (benchmark provenance split), `c637d44` (machine-readable C13 and C16), `0ed5dd4` (candidate space), `7e8729a` (specificity units frozen before BLAST), `caa8ab5` (specificity evidence), `64d1b14` (merge of the NB01 hotfix), `dc588d4` (contiguous cells and provisional candidates). The CP5 consolidation commit will carry the review decisions, the hand-off, the notebook and this run record. The hotfix itself is `6239ab4` on `master`.

## Evidence classification

1. `directly demonstrated`: input hashes, the CDS and protein hashes, the seven variable positions, the benchmark primer span and sha256, the BLAST and `dustmasker` outputs and versions, the window counts, the byte-identical re-runs, the k-mer self-check agreement.
2. `derived/computed`: the window descriptors, the clipped per-unit evidence, the contiguous cells and their ordering, the convergence overlap of 327 nt.
3. `inferred/interpreted`: that the two recommended regions are equivalent rather than one being better, the reading of "no homology detected", the transferability of the 60 bp floor and the 19/21 nt indicator to *D. maidis*, the review judgement that the concentrated short matches do not meet the concern threshold.
4. `unresolved`: the efficacy of any region, the optimal length, the effect of position, the biological relevance of the concentrated short OTHER_TRANSCRIPT matches, the experimental protocols of the benchmark, and whether the two dsRNase-2 accessions are one locus or two.
