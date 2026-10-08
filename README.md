# ZeaGuard dry lab

Computational workspace for designing and evaluating dsRNA sequences for RNAi
against *Dalbulus maidis*.

Current intervention targets are Bicaudal C and dsRNase-2. The dsRNase-1 and
dsRNase-3 paralogs are retained as references for specificity analysis.

## Setup

The supported platform is Linux. On Windows, use WSL2.

```bash
conda env create -f environment.yml
conda activate zeaguard
pip install -e . --no-deps
jupyter nbconvert --to notebook --execute src/workstreams/bioinformatics/notebooks/00_reproducibility_gate.ipynb
```

Notebook 00 verifies the declared environment and writes a local snapshot under
`artifacts/reproducibility/`. Generated snapshots are ignored by Git.

The evidence workstream stores its curated research database at
`src/workstreams/evidence/evidence_database.xlsx`.

Every downstream notebook must verify that its environment still matches the
latest local snapshot:

```python
import zeaguard.repro as repro
repro.assert_environment_ready()
```

Notebook 01 stage 1 reads target declarations from `config/project.yaml` and
validates external reference inputs declared in `data/reference/manifest.json`.
Dataset files remain local under `data/external/`; the notebook records their
SHA-256 digests and writes precondition and input-provenance reports under
`results/bioinformatics/nb01/` before stopping on any critical input failure.

Materialize the pinned NB01 TSA reference and update its manifest with:

```bash
python scripts/fetch_nb01_reference.py
```

Notebook 01 stage 2 loads bibliographic identity anchors from
`data/reference/target_anchors.tsv`, verifies exact coverage of the targets
declared in `config/project.yaml`, and writes
`results/bioinformatics/nb01/target_anchor_report.json`. Missing published
identifiers remain explicit `REVIEW` conditions for computational resolution in
stage 3.

Notebook 01 stage 3 reconciles the published anchor sequences against the
manifest-selected TSA through header matching, complete nucleotide sequence
matching in both orientations, and local BLASTn when exact evidence is absent.
It writes reviewable candidates and resolution decisions under
`results/bioinformatics/nb01/` without publishing definitive target FASTAs.

Notebook 01 stage 4 displays the stored results of the 2026-10-03 dsRNase-2
identity investigation (ADR 0004). Accession, CDS and protein remain
`AMBIGUOUS`; `GITV01008430.1` reproduces the published CDS and protein exactly.

## Notebook 02: candidate dsRNA regions against Dmai dsRNase-2

Notebook 02 selects **region and length** for a nominal 400 nt dsRNA against Dmai
dsRNase-2, with a published experimental benchmark of 330 nt and a
length-sensitivity analysis at 300 and 500 nt. The nominal length is a project
convention, not a biological optimum; the plausible space is 300-500 nt. The
criteria are frozen in `config/nb02_design_criteria.yaml`, committed before any
candidate window existed, and the policy is recorded in ADR 0005.

The NB01 hand-off is the versioned pin
`data/reference/nb01_dsrnase2_operational_reference.json`, re-derived from the
hash-validated TSA on every run, so NB02 reproduces in a clean clone without
depending on a gitignored file. Run the stages from the command line:

```bash
python -m zeaguard.nb02_design        # candidate space and descriptors
python -m zeaguard.nb02_specificity   # BLASTn evidence, clipped per candidate
python -m zeaguard.nb02_cells         # contiguous cells and provisional candidates
python -m zeaguard.nb02_handoff       # the versioned Wet Lab hand-off
```

Specificity is evidence, not a verdict: alignments are clipped to each candidate
interval and aggregated per biological unit (DSRNASE1, DSRNASE3, BICC), never
pooled across units, and compared by Pareto dominance within one length stratum.
There is no composite score, no weights, and no cutoff on E-values or on exact
19-mer and 21-mer counts. Homology against the rest of the *D. maidis*
transcriptome is a descriptor with a **mandatory pre-recommendation manual
review**: a candidate reaches `RECOMMENDED_SHORTLIST` only when a versioned
`APPROVED` decision for it exists in `config/nb02_manual_review_decisions.tsv`.

The hand-off is versioned at `data/reference/nb02_dsrnase2_candidate_regions.tsv`
and `.fasta` (coding/sense orientation, no tails). It separates the
`REFERENCE_SET` (the published benchmark, which never counts as a recommended
candidate) from the `RECOMMENDED_SHORTLIST`. The molecular architecture (linear,
hairpin, protected-end, dual-loop), primers, promoter, loop, terminator,
restriction sites, codon optimisation, plasmid backbone, ecological off-target
and any efficacy prediction are outside NB02; see the run record for the full
limitations.
