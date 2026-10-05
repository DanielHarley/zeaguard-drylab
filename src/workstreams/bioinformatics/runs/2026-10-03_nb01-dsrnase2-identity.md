# Run ID

`2026-10-03_nb01-dsrnase2-identity`

## Date

2026-10-03 (analysis, first command about 19:50 local, UTC-03:00, last about 22:20) and 2026-10-05 (molecular checkpoint under the strict protein policy, and consolidation of this record, the ADR, the notebook section and the manifest).

## Commit

Base commit `0effa52fc11d6700340c59c9ceca3abbc2dad319` (`master`). No commit was created; `HEAD` is unchanged. The worktree was clean at the start and is dirty at the end (the new module, tests, ADR, run record, a notebook section and a README line, listed in `run_manifest.json` under `git`).

## Branch

`feat/nb01-dsrnase2-identity-resolution`, created from `master`. The semantic type `feat` follows the change-type decision order in `.agents/commits_and_PR_instructions.txt` (item 7: new capability / pipeline step / persisted artifact). The `<type>/<kebab-name>` shape follows the existing branches (`feat/reproducibility-gate`, `feat/nb01-input-provenance`, `feat/modeling-reports`); `.agents` itself defines no literal branch-naming rule.

## Execution status

`COMPLETED`

`COMPLETED` means that the execution of the investigation is finished (all planned computational steps ran, were checked and recorded). It does **not** mean that the biological identity of Dmai dsRNase-2 is completely resolved: accession, CDS and protein remain `AMBIGUOUS` (see Results and Interpretation). The P2 items (Windows reproduction, new reads, phylogeny) were not authorised and were not run.

All scientific analyses ran in the canonical Linux environment (conda env `zeaguard` from the unmodified `environment.yml`, WSL2 Ubuntu 24.04, Python 3.12.14, BLAST+ 2.17.0, HMMER 3.4). Helper tools outside it: pypdf 6.19.0 (isolated Windows venv, PDF text extraction) and DeepSig (isolated conda env `sp-deepsig`). Exact reproduction of the historical Windows environment (P2) was not attempted.

## Question / objective

Determine, with reproducible evidence, how the published sequence of Dmai dsRNase-2 (Dalaison Fuentes et al. 2023, Supplementary File S1) relates to the candidate transcripts of the *Dalbulus maidis* TSA `GITV00000000.1`, classifying separately the accession, the CDS and the protein, and recording correspondence to the published sequence separately from biological identity.

## Inputs

- TSA: `data/external/tsa.GITV.1.fsa_nt.gz`, 31,435,495 bytes, sha256 `22d0cff8d0867344a76d615bdca62c31ce0f9133f574058e8daa6b6e41925ae6` (matches `data/reference/manifest.json`; 56,117 records `GITV01000001.1`–`GITV01056117.1`; the master record is not a sequence).
- Supplementary File S1: `data/external/Dalaison-Fuentes2023_S1_mmc1.pdf`, 1,496,295 bytes, sha256 `b2859b4ad39383136fd73c0e7623c095d3b5324da1547385eca215268d6fe429`, obtained 2026-10-03T22:52:24Z (git-ignored).
- Pfam profile `PF01223.30` (`raw/PF01223.hmm.gz`, sha256 `176b48ea1a64ca211bc900815b6dabfe7844ce8510f4aa16eed2fd1036791015`), GenBank master record (`raw/genbank_master_record.txt`).
- Repository inputs: `data/reference/target_anchors.tsv`, `data/reference/target_anchor_sequences.fasta`, `data/reference/manifest.json` (working-tree CRLF hashes and LF-normalised hashes are both recorded in `run_manifest.json`).
- Reads: SRA run SRR11822347 (BioProject PRJNA631706), only the reads containing a site anchor were kept.
- Full list with hashes: `results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/run_manifest.json`.

## Configuration

[ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md) (Proposed). [ADR 0003](../decisions/0003-nb01-target-identity-resolution-policy.md) was not modified. `environment.yml` was not modified. Deviations from the declared canonical environment: PDF text extraction (pypdf) and signal peptide prediction (DeepSig, TensorFlow 2.13) were run in separate environments; `repro.assert_environment_ready()` required `allow_dirty=True` because the work is uncommitted.

## Method

Entry point `python -m zeaguard.nb01_dsrnase_investigation` (`src/zeaguard/nb01_dsrnase_investigation.py`); stages: S1 reference validation, BLASTn and TBLASTN discovery (union coverage per query, subject and strand), discovery set, six-frame ORF scan with homology-based ORF and CDS selection, nucleotide and protein comparison (deterministic Gotoh alignments cross-checked against BLAST `btop`), paralogy control, PF01223 (`hmmsearch`), signal peptide (DeepSig, N-terminal completeness first), read-level allele counting, and the decision rules of ADR 0004. The historical pipeline (`prepare_nb01_stage3`) was re-executed unmodified into `historical_reproduction/`.

## Outputs

`results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/` (git-ignored, like all of `results/`): `decision.json`, `run_manifest.json` (hashes of every output), `provenance.tsv`, `README.md`, FASTA files, hit and comparison tables, `alignments/`, `raw/`, `historical_reproduction/`. Notebook Stage 4 displays them. Historical files under `results/bioinformatics/nb01/` were not modified (hashes recorded before and after in `run_manifest.json`).

## Validation / QC

1. Baseline `pytest`: 55 passed before any change. Final `pytest`: 108 passed, 0 failed, 0 skipped (the 55 baseline tests plus 53 new ones in `tests/test_nb01_dsrnase_investigation.py`, including explicit IUPAC translation cases and the strict protein policy) (`raw/pytest_final.txt`). Scope: structural and logic checks on synthetic data, not scientific validity.
2. `repro` environment gate: all checks PASS (`raw/assert_environment_ready.txt`).
3. Historical re-execution in the canonical environment: candidates table byte-identical; report differs only in timestamp and CRLF-dependent input hashes (`historical_reproduction/comparison_vs_historical.txt`).
4. S1 transcripts equal the repository anchors; each published ORF translates to its published protein (`manual_verification.txt`).
5. Event table versus BLAST `btop`: 0 disagreements (`btop_crosscheck.tsv`); independent position-by-position comparison of the two candidates agrees (`manual_verification.txt`).
6. Stored CDS translate to the stored proteins; accessions in every table exist in the TSA and match the FASTA files (`manual_verification.txt`).
7. Determinism: a second complete run into a scratch directory compared byte for byte with the stored outputs: 47 files identical, 0 differing (excluded on purpose: `run_manifest.json`, `provenance.tsv`, binary BLAST archives and databases, and the BLAST database 'Posted date' line; `raw/determinism_check.txt`).
8. DeepSig installation checked against its own test set: 46/46 presence calls, 42/42 identical spans (`raw/deepsig_selfcheck.txt`).
9. Stage 4 notebook cells executed on the stored results (`raw/wsl_notebook_stage4_check.sh`).
10. Molecular checkpoint (2026-10-05, `checkpoint_p0/`): S1 orientation verified two independent ways for all three dsRNases; per-position differences and codons re-derived directly from the TSA (`independent_check.txt`); paralogy by 212 discriminating positions; preliminary decision identical to `decision.json` under the strict policy. The consistency of statuses across artefacts is recorded in `checkpoint_p0/consistency_check.txt`.

## Results

Structured result: `decision.json` in the investigation directory. In short:

1. `published_reference_correspondence`: `UNIQUE`, `GITV01008430.1` (CDS and protein identical to the published ones).
2. `accession_resolution`: `AMBIGUOUS` (`GITV01008430.1`, `GITV01012450.1` both remain compatible).
3. `cds_resolution`: `AMBIGUOUS` (two distinct complete 1425-nt CDS; `GITV01012450.1` differs at 7 positions: 1 fixed synonymous substitution and 6 IUPAC codes, each including the other record's base).
4. `protein_resolution`: `AMBIGUOUS`, confined to residue 117 (R in the publication and in `GITV01008430.1`; `ARA` = K or R in `GITV01012450.1`). Strict policy (ADR 0004 rule 7): the published residue remains compatible but K remains possible, so `published_protein_compatible = yes` and `protein_sequence_resolved = no`; compatibility with the reference is not resolution of the sequence. `GITV01012450.1` is not classified as biologically incorrect.
5. `overall`: `AMBIGUOUS_AT_ACCESSION_AND_CDS_AND_PROTEIN_LEVELS`.
6. Paralogy: both candidates are 100 % / 99.789 % identical to the published dsRNase-2 protein and at most about 33 % to dsRNase-1/-3; the dsRNase-1 records are 100 % identical to dsRNase-1; dsRNase-3 has no TSA record of its own.
7. PF01223.30 meets the curated GA threshold in all candidates (dsRNase-2 domain 145-450). DeepSig predicts a 21-aa signal peptide for dsRNase-2 and both candidates (N-termini complete).
8. Reads (SRR11822347, 43.6 M reads scanned, 112 anchor-bearing): one of seven CDS sites informative (site 206: A 28 / G 24, both alleles supported); R117 has 6 informative reads and the fixed G/A site 15 (both not assessable).
9. Historical numbers (99.405 % / 98 %, 100 % / 96 %, 99.797 % / 85 %, no dsRNase-3 hit) are reproduced exactly with the historical parameters; the historical coverage is over the whole published cDNA, while both dsRNase-2 and both dsRNase-1 records cover the full published CDS (100 %).

## Interpretation

Three statements are kept apart: `published_reference_correspondence` (`UNIQUE`, `GITV01008430.1`), protein compatibility with the published protein (yes for both records) and protein sequence resolution (no). The ambiguity of `GITV01012450.1` comes from 1 defined synonymous substitution, 6 IUPAC symbols in the CDS (uncertainty, not substitutions) and one of those symbols allowing two amino acids. The residue 117 lies outside both the predicted signal peptide (1-21) and the PF01223 domain (145-450). The reads already obtained (6 informative at the codon: 5 R, 1 K) are insufficient and are compatible with polymorphism, allelic heterogeneity, biological mixture, sequencing error or other unresolved uncertainty; they were not re-analysed and the ratio is not used to resolve the protein.

Conditional on ADR 0004 and the recorded inputs: Dmai dsRNase-2 is represented in the TSA by a complete CDS and protein, and the published sequence is reproduced exactly by `GITV01008430.1` (an `OBSERVATION`). That is correspondence to a publication, not unique biological identity (an `INFERENCE` boundary): `GITV01012450.1` differs by one fixed synonymous substitution and six IUPAC codes, and a read test in one library shows that at least one of those codes marks real variation (site 206), so allelic variation is a live explanation (`HYPOTHESIS`); an assembly artefact is also live because the same record carries a ~2-kb repeat extension holding most of its IUPAC codes (`HYPOTHESIS`). The protein is the published protein except for one residue that the data cannot fix. For the next ZeaGuard step the CDS is established to within seven known variable positions.

## Handoff to the next stage

No dsRNA design, fragment selection or off-target analysis was done. For a future design stage:

- **Operational reference for correspondence to the published sequence:** `GITV01008430.1`, because it reproduces the published CDS and protein exactly. Caveat: this does not establish a unique biological identity of the locus; accession, CDS and protein remain ambiguous at the recorded levels.
- **Positions of attention:** every position where `GITV01008430.1` and `GITV01012450.1` differ or are ambiguous must be preserved as a region of attention (`checkpoint_p0/handoff_attention_positions.tsv`): in the CDS the defined synonymous substitution at CDS position 816 (residue 272) and the IUPAC positions at CDS positions 9, 30, 219, 312, 350 and 1272 (residues 3, 10, 73, 104, 117 and 424; residue 117 is K or R), plus the flanking differences (the first 5 nt of `GITV01008430.1`, 1970 nt and 26 nt present only in `GITV01012450.1`, and one IUPAC symbol at `GITV01008430.1` position 1492).
- Do not treat `GITV01012450.1` as biologically incorrect; it remains strongly compatible with Dmai dsRNase-2.

## What this run does NOT establish

- Biological identity of the dsRNase-2 transcript in the organism: the published sequence and the TSA come from different assemblies and possibly different individuals.
- That the record that does not reproduce the published sequence (`GITV01012450.1`) is invalid or redundant; polymorphism, an allele, consensus coding of repeated sequence and assembly redundancy are all compatible with the observations.
- Absence of other dsRNase-2-like loci outside this TSA, or the genomic copy number.
- The scientific calibration of any threshold in ADR 0004.
- That DeepSig's signal-peptide calls agree with SignalP (they disagree with the paper for dsRNase-1 and dsRNase-3).
- Successful execution and reproducibility do not demonstrate scientific validity.

## Anomalies / deviations

1. Supplementary File S1 contains no separate ORF nucleotide record (the paper says it does). ORFs were derived by locating each published protein in its published transcript.
2. During the run two method errors were found and corrected before the final run: translation did not resolve IUPAC codons whose resolutions encode one residue (BLAST does), and semi-global alignments reported forced end mismatches as substitutions. Both are covered by tests; the earlier exploratory outputs were overwritten by the final run.
3. A nucleotide-level identity between paralog CDS was first reported from a handful of paired bases; it is now reported as not alignable.
4. `GITV01012450.1` and `GITV01003945.1` contain many IUPAC codes (152 and 172); these were kept as such.
5. SignalP is not installed (licence). The PyPI package `deepsig` is an unrelated statistics library (name collision) and was rejected; the bioconda `deepsig` could not be solved (TensorFlow 2.2.0 unavailable); `deepsig-biocomp` was used.
6. Read analysis (P2 promoted to P0): the hypothesis was registered before any download. Deviations are recorded in the addendum of `raw/read_hypothesis_preregistration.md`: the planned first run (SRR11822333) was abandoned after 0 anchor-bearing reads in 349,638, a 12 MB abundance screen of all 16 runs selected SRR11822347, and a fixed stopping rule limited streaming time. Mate 2 of SRR11822347 stopped on a gzip CRC error at 21,713,087 of 21,895,394 reads (reported, not repaired).
7. **Provenance limitation (BioProject):** `data/reference/manifest.json` lists BioProject PRJNA579843; the GenBank record of `GITV00000000.1` lists PRJNA631706 (SRA runs SRR11822333-SRR11822348). Neither is chosen here and the manifest was not edited. The reads analysed in this run were taken from the SRA runs listed in the GenBank record. This discrepancy must be resolved before any future analysis based on reads or on the BioProject.
8. WSL git sees the CRLF working tree as modified unless `core.autocrlf=true` is set; git state in the manifest uses that setting. A first scratch run with a mis-converted `/tmp` path created a directory `C:` inside the repository; it contained only that run's BLAST files and was removed.
9. NB01 Stage 3 (existing cell) writes into `results/bioinformatics/nb01/`, the historical directory; executing that cell overwrites the historical outputs. It was not executed; Stage 4 only reads the new directory. This is an existing property of the notebook, not changed here.
10. A first draft of the 2026-10-05 molecular checkpoint treated a residue whose possible translations include the published amino acid as `RESOLVED`. That reading was rejected by the investigator in favour of the strict policy (ADR 0004 rule 7); the checkpoint, `decision.json`, the README, the ADR, this record and the notebook were then aligned and checked (`checkpoint_p0/consistency_check.txt`). Only `decision.json` and the checkpoint files changed as analytic outputs; all tables were byte-identical afterwards, apart from logs that carry timestamps.

## Related decisions

[ADR 0003](../decisions/0003-nb01-target-identity-resolution-policy.md) (unchanged), [ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md) (new, Proposed), [historical run record](2026-09-11_nb01-target-identity-resolution.md).

## Related Issue / PR / commits

`not recoverable` (no issue or PR); no commit created.

## Evidence classification

1. `directly demonstrated`: input hashes, tool versions, S1 sequences, BLAST/HMMER/DeepSig outputs, read counts, byte-identical historical reproduction.
2. `derived/computed`: ORFs and CDS, alignments and difference tables, coverage by interval union, protein comparisons, classifications under ADR 0004.
3. `inferred/interpreted`: the resolution statuses, the reading of IUPAC codes, the paralogy conclusions.
4. `unresolved`: whether the two TSA records are one locus or two; the origin of the IUPAC codes and of the repeat-containing extension of `GITV01012450.1`; the identity of residue 117 and of the fixed G/A site in `GITV01012450.1`, which need deeper read evidence or amplicon sequencing.
