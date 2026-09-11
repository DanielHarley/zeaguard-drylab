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
