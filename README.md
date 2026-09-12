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
