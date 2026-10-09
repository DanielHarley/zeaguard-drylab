# Run ID

`2026-10-08_nb03-cp4b-manual-review-resolution`

## Date

Record dated 2026-10-08, project timezone `America/Sao_Paulo`: the date of the CP4A evidence and of the manual review it resolves. The CP4B materialization itself executed on 2026-10-09; `execution_metadata.json` carries the exact timestamps.

## Commit

CP4B ran on `fe311344cbea9c6b527013090b715eccd5c9ba4a` (`cp4a_commit`: the commit that materialized the CP4A Pareto, cells and manual-review packet) with the CP4B decision record, implementation and tests still uncommitted; the commit that adds this record also adds them. Earlier checkpoints: CP2 `4e141876c478a76aada15d3f4b89b80dc9f6863f`, CP3 code and registry `748bd81248be0e34c2fc4158a78660d5e4f1ba25`, CP3 provenance record `d867a666661ddb611b977a260729a85a089d2d45`, amendment 4 `b8d15f36338922f870ec9f0bdd8004c1c04082ed`.

## Branch

`feat/nb03-bicc-candidate-regions`

## Execution status

`COMPLETED`. `G4_PASS`; `CP4B_COMPLETE`; `NEXT_STAGE_NOT_STARTED`. No CP5, no Wet Lab handoff.

## Question / objective

Record the manual scientific review of the ten L400 NONDOMINATED windows, which was carried out by a human outside the algorithm, validate it against the pre-registered contract, and materialize the shortlist it defines. The checkpoint decides nothing: it only turns a versioned human decision record into tables, a FASTA and a summary.

## Inputs

The frozen evidence the reviewer actually read, each verified against its certifying manifest before anything was written. Nothing was re-run: no BLAST, no exact k-mer scan, no shuffle, no Pareto recomputation.

| input | SHA-256 |
|---|---|
| CP4A `manual_review_packet.tsv` | `d1c9ea40ccc4b09083f2b107bac4188ab92a6a98dcb00375d92b5658aa2132fc` |
| CP4A `other_transcript_hsp_reference.tsv` | `8d7108f7ed187704a49d7d5b997ff75036a9bed87854a367e6d849fa4d340b7a` |
| CP4A `bicc_like_hsp_reference.tsv` | `0e6ec0804e6f136a4a6dd1cde3a5dbc8c852d1bc508b42cd75b6b066531fa7f5` |
| CP4A `benchmark_comparison.tsv` | `61f81a2f50a8b990336a397437dac79165eed26cfa19e8587cb04b3f84f02d31` |
| CP4A `run_manifest.json` | `e2ff9292271fc229ce4bb69f05acf8e064a897acaff77b326f89c4aabb55820c` |
| CP3 `queries/L400.fasta` (shortlist sequences only) | `5c872b627914dea3b3f65cd10dbda09341bcfeacb07aa861a1c2b92a3e5adab1` |
| CP2 `design_space.tsv` (sequence hashes and geometry) | `142e5e856a6740b2a225e947cbe7feae181ae0cab01d0084af56c74465719ee4` |
| Decision record `config/nb03_manual_review_decisions.tsv` (LF) | `80f26565e8ca8e7c713a88dbb628da32e9a5036e6eed0d1c1cdcecf33ba0c37d` |

`bicc_like_hsp_reference.tsv` is the only CP4A-directory file that the CP4A manifest does not certify: it was extracted from the certified `cp3/blast_hsps.tsv` after CP4A, during the independent BICC_LIKE audit, and its hash is pinned in `nb03_manual_review.BICC_LIKE_HSP_REFERENCE_SHA256`. CP4B additionally re-verified every CP2, CP3 and CP4A output against its own manifest and the registry against the hash CP4A was materialized under.

## Configuration

- Criteria registry [nb03_design_criteria.yaml](../../../../config/nb03_design_criteria.yaml), LF SHA-256 `5e2fa734ff55b1da57a62db592452c9915651ea5dfe5d12033cb4f34016d3b43`, unchanged by this checkpoint, and [ADR 0006](../decisions/0006-nb03-bicc-candidate-region-policy.md), also unchanged. No amendment was made: CP4B adds no criterion, threshold, role or vocabulary to the pre-registration.
- Implementation [nb03_manual_review.py](../../../zeaguard/nb03_manual_review.py), LF SHA-256 `e3b4090af5af13cf67929065e59674c87cc810e37313c784dfbe047341959cd1`.
- Tests [test_nb03_manual_review.py](../../../../tests/test_nb03_manual_review.py), LF SHA-256 `67448d92f95d73ffee8d6a8ae07d881f018908f8d31a2c9b89973b36a061cd1a`, plus the artifact-state sentinel in `tests/test_nb03_criteria.py` (see Regressions).

## Schema gate

The registry declares `policy.manual_review_decisions` with the path, the three scopes `OTHER_TRANSCRIPT`, `BICC_LIKE`, `DSRNASE2`, their decision vocabularies (`APPROVED` plus a `STRONG_*` concern) and `required_scope_for_recommendation: OTHER_TRANSCRIPT`. Unlike the NB02 registry it declares **no** `columns` key for this file, so no column schema is pre-registered and none had to be changed to accommodate the result. `policy.iterative_selection` says that an `APPROVED` candidate *may* enter `RECOMMENDED_SHORTLIST` and that a `STRONG_*` concern leads to `EXCLUDED_AFTER_REVIEW`.

`ADVANCE_TO_SHORTLIST` and `HOLD` are therefore representable without conflicting semantics, on three separate axes:

| axis | column(s) | vocabulary |
|---|---|---|
| formal per-scope specificity verdict | `other_transcript_decision`, `bicc_like_decision` | the registry's own (`APPROVED` / `STRONG_*`) |
| shortlist disposition at this checkpoint | `review_disposition` | `ADVANCE_TO_SHORTLIST`, `HOLD`, `EXCLUDE` |
| explanatory candidate role | `decision_role` | `PRIMARY_CANDIDATE_PROVISIONAL`, `SECONDARY_REGION_EQUIVALENT_ALTERNATIVE`, `RESERVE`, `HOLD_FOR_BACKGROUND_INTERPRETABILITY`, `EXCLUDED_AFTER_REVIEW` |

No `HOLD` was mapped to a `STRONG_*` concern. `DSRNASE2` is a declared scope that this review did not adjudicate, so it carries no column rather than a fabricated value; the registry requires only `OTHER_TRANSCRIPT` before a recommendation, and `cp4b_summary.json` records `registry_scopes.not_adjudicated: ["DSRNASE2"]` explicitly. The gate outcome is `MANUAL_REVIEW_SCHEMA_CONTRACT_SUFFICIENT`; `MANUAL_REVIEW_SCHEMA_CONTRACT_AMBIGUOUS` was not raised.

## OBSERVATION

Read from the frozen CP4A evidence; no value was recomputed here.

- The reviewed scope is exactly ten windows, all L400, all `NONDOMINATED`, all `manual_review_status = PENDING`, spread over nine cells (`BC-L400-1195-1594` and `BC-L400-1196-1595` share `BICC-L400-C0693`).
- Difference tiers present: tier 0 for `BC-L400-1337-1736` and `BC-L400-1614-2013`; tier 1 for `BC-L400-1195-1594`, `BC-L400-1196-1595`, `BC-L400-1253-1652`, `BC-L400-1254-1653`, each intersecting only CDS 1287; tier 3 for `BC-L400-0991-1390`, `BC-L400-1012-1411`, `BC-L400-1021-1420`, `BC-L400-1039-1438`, each intersecting CDS 1092, 1120 and 1287.
- `DSRNASE2`, `DSRNASE1` and `DSRNASE3` evidence is the zero vector for all ten windows.
- `BC-L400-1253-1652` and `BC-L400-1254-1653` occupy CDS 1253-1652 and 1254-1653: 399 shared positions, different cells only because their BICC_LIKE vectors differ, each better on one axis (covered_nt 390 against 393, identity about 0.70657 against 0.70629).
- Shortlist sequences, read from the certified CP3 native-query FASTA and re-hashed against the CP2 `sequence_sha256`: three distinct sequences of 400 nt over A/C/G/T, with `BC-L400-1253-1652[1:] == BC-L400-1254-1653[:-1]`.

### Documentation correction: BICC_LIKE gaps

The audit of the detailed BICC_LIKE HSPs resolved where the gaps sit, which earlier wording left ambiguous:

| window | alignment length | covered_nt | gaps |
|---|---|---|---|
| `BC-L400-1337-1736` | 369 | 369 | 3 gaps in the **subject**, 0 in the query |
| `BC-L400-1614-2013` | 385 | 385 | 9 gaps in the **subject**, 0 in the query |
| `BC-L400-1195-1594` | 434 | 398 | 36 gaps in the **query** |
| `BC-L400-1196-1595` | 434 | 398 | 36 gaps in the **query** |
| `BC-L400-1253-1652` | 426 | 390 | 36 gaps in the **query** |
| `BC-L400-1254-1653` | 429 | 393 | 36 gaps in the **query** |

Alignment length exceeds `covered_nt` by exactly the number of query gaps; where the gaps are in the subject the two are equal. This is `DOCUMENTATION_ONLY` and changed no decision.

## INFERENCE

- The BICC_LIKE axes already took part in the six-axis Pareto comparison that produced this very scope, so applying them again after the Pareto would be double-counting. CP4B therefore reapplies no BICC_LIKE filter; the audit of the detailed HSPs produced no new qualitative phenomenon and hence no new veto.
- No pre-registered cutoff exists for OTHER_TRANSCRIPT HSP or subject counts, `covered_nt`, longest exact tract, identity or e-value, nor for the exact 19-mer and 21-mer counts (`DESCRIPTIVE_ONLY`, C18), nor for pairwise overlap between candidates (the registry forbids pre-registering one). Comparisons between candidates in the rationales are relative statements, not thresholds.
- `BC-L400-1253-1652` and `BC-L400-1254-1653` are incomparable under the Pareto contract, so no frozen rule resolves their trade-off.
- The four tier-3 windows share one block at CDS 997-1069 seen through four window offsets, not four independent findings.
- The two perfect 23-nt tracts of `BC-L400-1614-2013` lie in two distinct subject records whose query intervals overlap by 2 nt, so they are not two independent events.
- The biological relation of `GITV01002238.1` (BICC_LIKE) and of the OTHER_TRANSCRIPT records `GITV01029469.1`, `GITV01039726.1` and `GITV01051646.1` to BicC is not resolved by these files.

## HUMAN DECISION

Taken outside the algorithm on the evidence above, frozen in [config/nb03_manual_review_decisions.tsv](../../../../config/nb03_manual_review_decisions.tsv), and only validated and materialized here. Ten rows, one per reviewed window, each carrying its own auditable rationale and the SHA-256 of the three evidence files it was based on.

| window | `review_disposition` | `decision_role` | tier |
|---|---|---|---|
| `BC-L400-1337-1736` | `ADVANCE_TO_SHORTLIST` | `PRIMARY_CANDIDATE_PROVISIONAL` | 0 |
| `BC-L400-1253-1652` | `ADVANCE_TO_SHORTLIST` | `SECONDARY_REGION_EQUIVALENT_ALTERNATIVE` | 1 |
| `BC-L400-1254-1653` | `ADVANCE_TO_SHORTLIST` | `SECONDARY_REGION_EQUIVALENT_ALTERNATIVE` | 1 |
| `BC-L400-1195-1594` | `HOLD` | `RESERVE` | 1 |
| `BC-L400-1196-1595` | `HOLD` | `RESERVE` | 1 |
| `BC-L400-1614-2013` | `HOLD` | `HOLD_FOR_BACKGROUND_INTERPRETABILITY` | 0 |
| `BC-L400-0991-1390` | `HOLD` | `HOLD_FOR_BACKGROUND_INTERPRETABILITY` | 3 |
| `BC-L400-1012-1411` | `HOLD` | `HOLD_FOR_BACKGROUND_INTERPRETABILITY` | 3 |
| `BC-L400-1021-1420` | `HOLD` | `HOLD_FOR_BACKGROUND_INTERPRETABILITY` | 3 |
| `BC-L400-1039-1438` | `HOLD` | `HOLD_FOR_BACKGROUND_INTERPRETABILITY` | 3 |

Totals: 10 reviewed, 3 `ADVANCE_TO_SHORTLIST`, 7 `HOLD`, 0 `EXCLUDE`; 1 primary, 2 secondary equivalent alternatives, 2 reserve, 5 background hold. Every window carries `other_transcript_decision = APPROVED` and `bicc_like_decision = APPROVED`: no `STRONG_*` concern was recorded in any scope. `HOLD` preserves a candidate and means neither unsafe, nor ineffective, nor off-target confirmed. The shortlist holds 3 candidates, inside the pre-registered 2-4.

## Explicit statements for the record

- The manual review was carried out by a human **outside the algorithm**; CP4B validated and materialized it and re-derived no decision.
- `OTHER_TRANSCRIPT` received **no cutoff**: HSP counts, subject counts, `covered_nt`, longest exact tract, identity and e-value were carried through as text.
- Exact 19-mer and 21-mer counts received **no cutoff** and stayed `DESCRIPTIVE_ONLY`.
- `BICC_LIKE` was **not reapplied as a post-Pareto filter**.
- **No window** was classified as a confirmed off-target or a strong biological off-target.
- The `GITV` relationships relevant to this review remain `RELATIONSHIP_UNRESOLVED`.
- The published benchmark was used as a **descriptive reference only**, never as a limit of acceptability, and `BC-BENCH-0215-0587` appears nowhere in the CP4B outputs.
- `BC-L400-1253-1652` and `BC-L400-1254-1653` remain alternatives **with no automatic preference**; `secondary_region_preference` is `UNRESOLVED`. They share 399 of 400 genomic/CDS positions and are not described as biologically identical. A later choice between them may consider construction or primer feasibility; that is not part of CP4B.
- Pareto status, cells and difference tiers were read from the CP4A packet and never recomputed; no BLAST and no k-mer scan ran.

## Method

`zeaguard.nb03_manual_review` is a data-free kernel plus a thin CP4B layer: `load_decisions` (exact column set, closed vocabularies read from the registry, no duplicate window, hex-64 evidence hashes, non-empty fields, a `STRONG_*` concern must lead to `EXCLUDE`, advancing requires `OTHER_TRANSCRIPT = APPROVED`), `resolve` (exact one-to-one match with the reviewed scope; an extra, missing or duplicated id is an error), `shortlist`, `disposition_counts`, `role_counts`. The module contains no window id, so the versioned record is the only source of the decisions; editing the code cannot change them. Row order in every output is the CP4A packet order, `CANONICAL_DISPLAY_ORDER_ONLY`, not a ranking and not a tie-breaker.

Shortlist sequences are read from the certified CP3 native-query FASTA, checked for length, alphabet and `sequence_sha256` against CP2, and written with deterministic `>window_id` headers; `HOLD` windows appear in no shortlist file.

## Outputs

`results/bioinformatics/nb03/cp4b/` (gitignored, as every other results directory).

| output | SHA-256 |
|---|---|
| `manual_review_resolved.tsv` | `aa395135ad11d222875241ccd69b2630afa424a2d29c00d5437d5527e75459c2` |
| `shortlist.tsv` | `3403c84e65ca099ee834dfb12d82020ed57207f5bc9f7b0f93ebe5ea8f96ae25` |
| `shortlist.fasta` | `5049c9b29ec999cd9bea9606f194fe25b5fd0a5041c1d00a1e007ee06a97be7d` |
| `cp4b_summary.json` | `a1b6777bbb2e7edace0cf9eac334c10774617fca10b8df4b81fc1fa5c7e8442d` |
| `run_manifest.json` | `938c379675234bcee844cd4dc4685011c0d539ff0801dffeb1bfe65cd87260a9` |

`execution_metadata.json` carries the timestamps, interpreter and platform and is excluded from the deterministic set.

## Determinism

CP4B ran three times (the canonical directory and two temporary directories). All five deterministic outputs, `run_manifest.json` included, are byte-identical across runs; only `execution_metadata.json` differs. The manifest contains no output path and no timestamp.

## Regressions

Re-verified after CP4B, each against its own manifest: CP2 (3 outputs), CP3 (7 outputs), CP4A (7 outputs), all unchanged, plus the NB02 final handoff `nb02_dsrnase2_candidate_regions.tsv` `341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939` and `.fasta` `a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e`. The registry, ADR 0006 and `nb03_selection.py`, `nb03_criteria.py` and `nb03_specificity.py` are byte-unchanged. No CP2, CP3 or CP4A output was rewritten and no earlier manifest was re-executed.

Test suite: 425 passed, 0 failed, 0 skipped (403 before CP4B plus 22 new CP4B tests), with BLAST+ and dustmasker on `PATH` and the hash-pinned TSA present.

One pre-existing assertion was superseded, not loosened, and the new state was then made explicit. `tests/test_nb03_criteria.py::test_no_candidate_window_artifact_is_versioned` asserted that `config/nb03_manual_review_decisions.tsv` does **not** exist. That was the pre-CP4 state; the same test also asserts the registry line `manual_review_decisions.created_at: CP4`, and CP4B is the checkpoint that creates the file, so the two assertions became contradictory. The sentinel now states the artifact state positively:

| artifact | asserted state |
|---|---|
| `config/nb03_manual_review_decisions.tsv` | `EXPECTED_AT_CP4B` (exists) |
| `data/reference/nb03_bicc_candidate_regions.tsv` | `NOT_YET_MATERIALIZED` (absent) |
| `data/reference/nb03_bicc_candidate_regions.fasta` | `NOT_YET_MATERIALIZED` (absent) |

The glob guard against any `nb03_*candidate*` artifact in `data/reference` and the `created_at: CP4` assertion are unchanged, and the record's schema and scope are checked by `tests/test_nb03_manual_review.py`. This is an artifact-state sentinel, not a test of a scientific value: no scientific assertion, threshold or expected value was weakened anywhere in the suite.

## Working tree note

`git status` lists 30 modified files whose diffs vanish under `git diff --ignore-cr-at-eol`: NB01-era sources, notebooks and documents whose working copies carry CRLF while the committed blobs are LF. No NB02, NB03, `config/` or results file is among them, and the on-disk hashes of the registry, membership record and NB03 modules equal their `HEAD` blobs. This is the same `PROVENANCE_PLATFORM_ARTIFACT` recorded at CP3 and CP4A, not a content change.

## Limitations

- The shortlist is a human adjudication of the recorded evidence, not a safety or efficacy claim. `PRIMARY_CANDIDATE_PROVISIONAL` is provisional by name.
- `DSRNASE2` was not adjudicated. Its evidence is the zero vector for all ten windows, which is an OBSERVATION from CP3, not a decision; the registry does not require that scope before a recommendation.
- The seven `HOLD` windows stay available. Nothing in this checkpoint rules them out.
- The relation of the `GITV` records involved to BicC stays unresolved, so the background evidence is held for interpretation rather than resolved.
- L300, L373 and L500 remain analytical sensitivity strata and were not reviewed.

## Not done

CP5, the Wet Lab handoff, and `data/reference/nb03_bicc_candidate_regions.{tsv,fasta}`: the shortlist stays in `results/bioinformatics/nb03/cp4b/`. No automatic choice between the two secondary alternatives, no representative selection, no registry or ADR change, no BLAST, no k-mer recomputation, no Pareto recomputation, no push and no pull request.
