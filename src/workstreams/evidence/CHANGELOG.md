# Evidence database changelog

## 2026-09-12 — canonical database replaced (v001 → current)

- Responsible contributors: Beatriz, Nicolas.
- Previous historical snapshot: `history/2026-09-12_evidence_database_v001.xlsx`.
- Canonical database path (unchanged): `evidence_database.xlsx`.
- Previous canonical SHA-256: `40c5a035afa3c063a6127c4fc26c9d109cec03e707136e43fb6f38c517d3f151`.
- New canonical SHA-256: `5912284c2b91b70a001c0fd871f588ea8adf3a9f59f29a3cbbab578879efb7cd`.

### Structural comparison

Both workbooks load successfully and contain the same 7 sheets: `Banco v2`,
`Parametros (long)`, `Listas`, `Lacunas`, `Resumo da triagem`, `Guia v2`,
`Etapa 2 - Triagem LLM (orig)`. Sheet order differs (`Guia v2` and `Resumo da
triagem` are swapped); no sheet was added or removed.

Per-sheet dimensions (`max_row`/`max_column`) are identical between the
previous and new canonical workbook for every sheet. No row was added or
removed in any sheet (last non-empty row is unchanged per sheet). No column
range changed. No schema change (sheet set, row extent, or column extent) was
observed.

### Cell-level differences (structural comparison only, no semantic interpretation)

- `Banco v2`: 80 cells differ at the same coordinates between the previous and
  new workbook; populated cell count changed from 1231 to 1178 (net -53
  populated cells).
- `Parametros (long)`: 115 cells differ at the same coordinates; populated
  cell count changed from 1053 to 1147 (net +94 populated cells).
- `Listas`, `Lacunas`, `Resumo da triagem`, `Guia v2`, `Etapa 2 - Triagem LLM
  (orig)`: byte-for-byte identical cell values; 0 differing cells.

### What this entry does NOT establish

This comparison is derived only from a binary/structural inspection of the
two workbooks (sheet names, dimensions, formula counts, and cell-by-cell value
equality at matching coordinates). It does not interpret what the changed
cells in `Banco v2` or `Parametros (long)` mean scientifically, does not
identify which evidence records were added, removed, or revised, and does not
establish the reason for the change. That interpretation is not recoverable
from the workbook diff alone and is not recorded here.
