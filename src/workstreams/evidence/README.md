# Evidence database versioning

`evidence_database.xlsx` in this directory is always the current canonical
evidence database. `config/repro.yaml` and all workstream code reference this
exact path.

Rules:

1. `evidence_database.xlsx` is always the current canonical database.
2. `history/` contains immutable historical snapshots of previous canonical
   databases.
3. Files under `history/` must never be edited after being committed.
4. Before each future database replacement, the previous canonical database
   must be archived into `history/` with its SHA-256 recorded.
5. Each update must be recorded in `CHANGELOG.md`.
6. Each historical snapshot must be registered in `history/manifest.tsv` with
   its SHA-256.
7. Files such as `final.xlsx`, `v3.xlsx`, `new.xlsx`, or any other parallel
   active database copy must not remain in this directory once a replacement
   is promoted to canonical.
