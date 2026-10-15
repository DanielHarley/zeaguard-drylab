# NB04 CP0 limited implementation and execution record

Date: 2026/10/14. Authoritative timezone for the project: America/Sao_Paulo. Execution timestamps in machine records are UTC.

Status: CP0_PARTIAL_MATERIALIZATION_CONTRACT_REFERENCE_PENDING. DEVELOPMENT_TEST_PASS describes the executed computational tests. G0_PASS=NOT_DECLARED. CP1=NOT_STARTED. No certification is claimed.

## 1. Authorization, scope and unresolved complementary contract

The project explicitly declared METHODOLOGICAL_CONTRACT_APPROVAL and authorized LIMITED_CP0_IMPLEMENTATION. On clarification during this execution, the responsible confirmed that no complete ratified selection rule, selection_rule_id or operational CALIBRATION_INCONCLUSIVE definition was located. Independent implementation and verification were explicitly authorized to continue. Existing QA admissibility conditions were not converted into a selection rule.

The policy preserves selection_rule_id=null and calibration_inconclusive_definition=null, with selection_rule_status=UNRESOLVED_CONTRACT_REFERENCE. The corresponding LOCAL_ALIGNMENT declaration also has a null selection_rule_id. The package remains partial. A complementary record must define selection, handling of multiple admissible configurations and CALIBRATION_INCONCLUSIVE, distinguishing it from FAILED and tests not executed. That record must be independently audited and ratified before G0 certification and any corresponding calibration execution. No inferred normative selection identifier or criterion was created.

## 2. Git and preserved environmental baseline

Initial and final branch: feat/nb04-cp0. Initial and final HEAD: a34892d1874a7ea3298cb1873f02efd4cd99912a. The initial Git for Windows status and staging were clean. At delivery the Windows working tree contains the CP0 additions and the four line decision index update. Staging remains empty. No commit, push, PR, merge, branch switch or operational snapshot publication occurred.

Baseline pointer: artifacts/reproducibility/latest.json. Preserved snapshot: artifacts/reproducibility/20261014T200715078008Z_e37481d6d154/snapshot.json. SHA256: e396d89e56c1f205030ef19aae9e7fa8e4a217cd212741768be96d01cf5e1534. The snapshot records this branch and HEAD, dirty=false, allow_dirty=false and 31 PASS. All five recorded configuration hashes were rechecked. This snapshot describes the initial state, before CP0 changes.

| Protected baseline configuration | Preserved SHA256 |
| --- | --- |
| config/project.yaml | d18483467237da02e0a5d03470cd8222963e2832cb4cb26d3abf9434e39c1e43 |
| config/repro.schema.json | 4e3fcaac20536007c0363728be046385fe4506b97b57744695ba32fb18345e06 |
| config/repro.yaml | df8c56b873e3090710a54800864077d86391e4a21ba9850b75db38ece7e4d1fb |
| environment.yml | 1559508a4ea10ba977ad9bac6814ae5a6f2f021f2879054f9438fa4f069901e6 |
| pyproject.toml | d83c59eab697e165d2cfdb93a51aaff38ef757d6c6a5876271706fae81162201 |

A raw byte inventory covered 429 baseline files. The only changed file in that inventory is src/workstreams/bioinformatics/decisions/README.md, which receives the required ADR 0006 and ADR 0007 index entries in both languages. All other 428 baseline files remain byte identical, including upstream NB01/NB02/NB03 files, N18/N20 implementation, reproducibility configuration and historical snapshots. The complete inventory is artifacts/validation/nb04_cp0/protected_baseline.json.

Platform observation: Git for Windows reports core.autocrlf=true from its system configuration. Git inside WSL has no configured core.autocrlf. WSL therefore additionally reports existing CRLF working copies against LF Git blobs, including config/repro.schema.json and nb04_serialization.py. git diff --ignore-cr-at-eol --stat inside WSL reduces tracked differences to the decision index. WSL also lists the local .claude/settings.local.json, whose observed creation/modification time is 2026/10/14 20:09:38 UTC, outside the CP0 output set. That file was not created or modified by this implementation. No historical line ending normalization was performed. See artifacts/validation/nb04_cp0/git_platform_observation.json and final_artifact_verification.json. Git for Windows is used for the delivery status listing.

## 3. Normative source identity and precedence

| Document | Version/current applicability | Verified original SHA256 |
| --- | --- | --- |
| 01_PLAN_v2.2.5.md | v2.2.5 / APPROVED_WITH_ADOPTED_AMENDMENTS | 9b759f71de500f65947bb150db71a5d20029da06971a26f7e20d1c72193dc83a |
| B4_CALIBRATION_AMENDMENT_A1.md | A1 / ADOPTED_AFTER_INDEPENDENT_AUDIT | 0c1815be37ca6187639a27429fc0b38adb3f4be762f773f17a159f29b38f0ecc |
| NB04_PREAPPROVAL_CLOSURE.md | 2026/10/14 / RATIFIED_AFTER_INDEPENDENT_AUDIT | 52b54d4fa633b2847818e7382e57fdbf9c1ec73588f662c93fb30f56aa7f618b |
| B6_GOVERNANCE_AMENDMENT_A1.md | A1 / ADOPTED_AFTER_INDEPENDENT_AUDIT | 9ea167a88359f78e916d753865d7d40a5c37d2ff04d3a09d73c647c3aebaa62b |

The four complete expected hashes matched before editing and during preparation. No provenance mismatch was observed. The 18 input package entries were checked against the recorded manifest hash prefixes, with full observed SHA256 retained. B5_CONCERN_CRITERIA_REVIEW.md was additionally checked against the full hash cited by the ratified closure. Other historical B5/B6 files retain observed full identity, with that verification scope explicitly distinguished from an independently supplied full expected hash.

Permanent identities and original table records are in data/reference/nb04_cp0_documentary_inputs.json. Complete external PLAN/review documents were not imported. Applicability overlays preserve original status fields. B3 governs literal CP2 spaces, B4 and A1 govern calibration/admissibility, B5 governs interpretation/disposition and B6 A1 governs the specifically superseded governance scope. Closure B/C/D/E governs PLANT, N2, PLAN/B3 precedence and the subsequent POLLINATOR state.

## 4. Upstream provenance and query bundle

The eight source artifact/manifest identities and the two NB01 reference pins were rechecked. Each sequence source is checked against its manifest binding and either a certified Git blob or a hash in the specified versioned certifying record. Each certifying commit must be an ancestor of the delivery HEAD. The registry explicitly distinguishes observed manifest byte identity from the source artifact hash certified in Git. Execution Git metadata inside an old manifest is not substituted for the later certifying commit.

| Source artifact or manifest | Hash mode | Verified SHA256 |
| --- | --- | --- |
| data/reference/nb02_dsrnase2_candidate_regions.fasta | LF_NORMALIZED | a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e |
| data/reference/nb02_dsrnase2_candidate_regions.tsv | LF_NORMALIZED | 341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939 |
| results/bioinformatics/nb02/cp5/run_manifest.json | RAW_BYTES | 733fb625c1a96aa52febd199625d248b6904de4e172312c7f28678c2ee869b1a |
| results/bioinformatics/nb03/cp0/benchmark_reconstruction.json | LF_NORMALIZED | 30c29adbe899506b2ae3428d6ea3bd9b16d7523b95289fd7a79236459422a76f |
| results/bioinformatics/nb03/cp0/run_manifest.json | RAW_BYTES | 49276e4217d4250b46d2490b2f2ad4b827faea5fb12e887843e30dda08cff876 |
| results/bioinformatics/nb03/cp4b/run_manifest.json | RAW_BYTES | 938c379675234bcee844cd4dc4685011c0d539ff0801dffeb1bfe65cd87260a9 |
| results/bioinformatics/nb03/cp4b/shortlist.fasta | LF_NORMALIZED | 5049c9b29ec999cd9bea9606f194fe25b5fd0a5041c1d00a1e007ee06a97be7d |
| results/bioinformatics/nb03/cp4b/shortlist.tsv | LF_NORMALIZED | 3403c84e65ca099ee834dfb12d82020ed57207f5bc9f7b0f93ebe5ea8f96ae25 |

| Reference pin | Certifying commit | Verified LF SHA256 |
| --- | --- | --- |
| BICC / data/reference/nb01_bicc_operational_reference.json | 099f751780283fecbc63da177c113aec9f6d60d5 | 5d4b2b24ec56aebcb55c73f6d23e719bab8d2506cdfa49c225453d93707bd21c |
| DSRNASE2 / data/reference/nb01_dsrnase2_operational_reference.json | 74b9d6584690b95d4c8175b7d487940f2372bda6 | 4ea481fb747f91ca22fc55fda2ab684884952650ad1cfa31cf3fe268011c9edb |

| Query | Role | Length nt | Sequence SHA256 |
| --- | --- | --- | --- |
| BC-BENCH-0215-0587 | REFERENCE_SET | 373 | e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb |
| BC-L400-1253-1652 | CANDIDATE | 400 | 828dfa52251bfeefd182b698e3c5aaddfd13b0996e0d393fdda13e538cc20ad5 |
| BC-L400-1254-1653 | CANDIDATE | 400 | 2281891befd9eaaecda500789892e3ea461fdcc71e0bd28ff035836a804ac12e |
| BC-L400-1337-1736 | CANDIDATE | 400 | 71e0788174a9ce7884eb257924dd808f94a3f018eb38fbf70a5fd3002493344e |
| D2-BENCH-0814-1143 | REFERENCE_SET | 330 | 97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179 |
| D2-L400-0351-0750 | CANDIDATE | 400 | 5c2b656e80265d1f248fb16cca21aff092b12169c1348758d78959b3d4e5cdc3 |
| D2-L400-0817-1216 | CANDIDATE | 400 | eb32cfa98180028dab7cfc045171f152d6be34658d02b3259e70857586bc9977 |

| Query | Sequence stage | Selection stage | Certifying commit |
| --- | --- | --- | --- |
| BC-BENCH-0215-0587 | NB03_CP0_RECONSTRUCTION_CERTIFIED_BY_CP1_PIN | NOT_APPLICABLE | 099f751780283fecbc63da177c113aec9f6d60d5 |
| BC-L400-1253-1652 | NB03_CP4B | NB03_CP4B | 9ca3e0903e9bee10c0708fde95241b7fa671591a |
| BC-L400-1254-1653 | NB03_CP4B | NB03_CP4B | 9ca3e0903e9bee10c0708fde95241b7fa671591a |
| BC-L400-1337-1736 | NB03_CP4B | NB03_CP4B | 9ca3e0903e9bee10c0708fde95241b7fa671591a |
| D2-BENCH-0814-1143 | NB02_CP5 | NOT_APPLICABLE | 74b9d6584690b95d4c8175b7d487940f2372bda6 |
| D2-L400-0351-0750 | NB02_CP5 | NB02_CP5 | 74b9d6584690b95d4c8175b7d487940f2372bda6 |
| D2-L400-0817-1216 | NB02_CP5 | NB02_CP5 | 74b9d6584690b95d4c8175b7d487940f2372bda6 |

Per query source artifact, selection artifact, both hashes, source manifest and hash, certification record and hash are retained in data/reference/nb04_nto_queries.tsv and data/reference/nb04_upstream_provenance.json. BicC candidates use CP4B commit 9ca3e0903e9bee10c0708fde95241b7fa671591a. BicC benchmark uses its CP0 reconstruction, whose hash is certified in the CP1 pin at 099f751780283fecbc63da177c113aec9f6d60d5. dsRNase candidates and benchmark use the NB02 CP5 handoff at 74b9d6584690b95d4c8175b7d487940f2372bda6. Reference queries have no selection artifact.

All seven complete sequences match their certified SHA256, lengths and ACGT alphabet. BicC 1253/1254 remain distinct. BicC benchmark uses 373 nt and preserves publication_reported_length_bp=372 with UNRESOLVED_PUBLICATION_INCONSISTENCY. Upstream experimental_protocol_verification limitations remain unchanged. Semantics are NB04_SEQUENCE_SCREENING_INPUT and SELECTED_SEQUENCE_FOR_NTO_SCREENING for selected candidates.

## 5. Deterministic overlap verification

| Query A | Query B | Shared nt | A exclusive nt | B exclusive nt | Shared bases |
| --- | --- | --- | --- | --- | --- |
| BC-BENCH-0215-0587 | BC-L400-1253-1652 | 0 | 373 | 400 | NOT_APPLICABLE |
| BC-BENCH-0215-0587 | BC-L400-1254-1653 | 0 | 373 | 400 | NOT_APPLICABLE |
| BC-BENCH-0215-0587 | BC-L400-1337-1736 | 0 | 373 | 400 | NOT_APPLICABLE |
| BC-L400-1253-1652 | BC-L400-1254-1653 | 399 | 1 | 1 | VERIFIED_IDENTICAL |
| BC-L400-1253-1652 | BC-L400-1337-1736 | 316 | 84 | 84 | VERIFIED_IDENTICAL |
| BC-L400-1254-1653 | BC-L400-1337-1736 | 317 | 83 | 83 | VERIFIED_IDENTICAL |
| D2-BENCH-0814-1143 | D2-L400-0351-0750 | 0 | 330 | 400 | NOT_APPLICABLE |
| D2-BENCH-0814-1143 | D2-L400-0817-1216 | 327 | 3 | 73 | VERIFIED_IDENTICAL |
| D2-L400-0351-0750 | D2-L400-0817-1216 | 0 | 400 | 400 | NOT_APPLICABLE |

All nine within reference pairs are present. Coordinate partitions cover both queries completely. Shared base strings agree exactly. Their hashes and exclusive intervals are in query_overlap.tsv. Cross target coordinate comparisons are NOT_APPLICABLE_DIFFERENT_REFERENCE_COORDINATE_SYSTEMS. Coordinate sharing supports no independence claim and never deduplicates evidence.

## 6. Policy, panel, scenarios, literature and gaps

| Materialized scope | Observed rows/count |
| --- | --- |
| query_count | 7 |
| within_reference_pairs | 9 |
| receptor_count | 21 |
| core_receptor_count | 6 |
| scenario_count | 1 |
| receptor_scenario_rows | 21 |
| literature_rows | 80 |
| landscape_rows | 29 |
| gap_rows | 41 |

The six CORE receptors are Zea mays, Agallia albidula, Exitianus obscurinervis, Doru luteipes, Apis mellifera and Paracentrobia subflava. Zea mays remains PLANT with its separate interpretation context. Apis follows closure E. Trigona remains conditional/optional. Historical nominal proposals and their full ecological justifications are retained. The unresolved Coccinellidae group remains a gap. No soil receptor identity is assigned.

The single NB04_N2_CONSERVATIVE_ENVELOPE_V1 scenario remains CONDITIONAL_ALTERNATIVE. Operational route, formulation, months, dates, season, application window and duration, residue duration, frequency, area and dose are UNKNOWN. Foliar/Bacillus remains a working hypothesis. Internal exposure is UNKNOWN in every receptor row. Soil/residue UNKNOWN activates the mandatory category, represented by SOIL_OR_RESIDUE_RECEPTOR_UNSPECIFIED_UNDER_CONSERVATIVE_ENVELOPE. AQUATIC is not activated by UNKNOWN alone.

Preliminary assessability is used only where supported by species specific L9a metadata. Ten nominal receptors have an empty preliminary value with L9A_METADATA_NOT_ASSESSED. These include CORE Exitianus obscurinervis and Paracentrobia subflava. Genus level Paracentrobia metadata is preserved at its original scope and is not promoted to species certification. Empty values express missing metadata. No resource absence is inferred. No final_* field is present in the panel. Ten taxids remain empty with explicit gaps. No taxonomy or resource payload was acquired.

Nine historical EXTENDED_PROPOSED entries preserve their source tier and justification but have no independently supplied normalized D.6 added value category. added_value_rationale=NONE and an explicit source specific gap prevent an invented category. These rows are not claimed as certified admitted EXTENDED receptors. Their admission/category must be reviewed before the relevant G0 scope freeze or ecological interpretation. Ecological tiers are never demoted because of resource availability.

| Gap type | Rows |
| --- | --- |
| EXTENDED_ADDED_VALUE_FORMAL_CATEGORY_PENDING | 9 |
| L9A_METADATA_NOT_ASSESSED | 10 |
| OPTIONAL_NOMINAL_RECEPTOR_UNRESOLVED | 1 |
| PHYLOGENETIC_COVERAGE_LIMITATION | 1 |
| PRELIMINARY_RESOURCE_COVERAGE_GAP | 7 |
| REGIONAL_ECOLOGICAL_COVERAGE_GAP | 1 |
| SOIL_OR_RESIDUE_RECEPTOR_UNSPECIFIED_UNDER_CONSERVATIVE_ENVELOPE | 1 |
| TAXID_UNRESOLVED | 10 |
| UNRESOLVED_CONTRACT_REFERENCE | 1 |

All literature findings, pending source status, transferability restrictions and original records remain traceable. The landscape retains all 29 existing metadata rows with METADATA_ONLY_NOT_SELECTED_NOT_FROZEN. Structural tests do not certify ecological sufficiency or turn a documented gap into completed scientific evidence.

## 7. Code and deterministic serialization

src/zeaguard/nb04_policy.py validates the policy schema and table relations. src/zeaguard/nb04_cp0.py checks provenance, builds the exact bundle and compares within reference intervals and bases. scripts/prepare_nb04_cp0_inputs.py imports audited documentary records and separate applicability overlays. scripts/validate_nb04_cp0.py records test execution, copies faithful inputs and patch into an independent directory and checks preservation. tests/test_nb04_cp0.py tests scope, roles, hashes, origin tuples, orphan references, cardinality, phase boundaries, premature final assessability, calibration obligations, modality separation and deterministic output.

N18 functions are reused directly, with canonical serialization validated. N20 is reused through an explicit proposed nb04_cp0 profile in memory. The proposed profile produced 28 readable path checks, retaining the existing 20 always required paths and adding eight CP0 paths. config/repro.yaml is unchanged. Historical checkpoint=None behavior is covered by the 74 test N20 regression suite. No NB02/NB03 search, selection or Pareto kernel is reused as a NB04 search implementation.

New CP0 text uses LF, integer counts and no ranking. New .gitattributes rules apply only to CP0 paths. Volatile execution metadata is separated. The deterministic test runs materialization twice into separate temporary output roots and compares seven payload outputs plus run_manifest.json byte for byte. Raw manifest outputs and normalized versioned inputs/implementation hashes were checked again by final_artifact_verification.json.

## 8. Executed validation and logs

Canonical environment: PRETTY_NAME="Ubuntu 24.04.4 LTS". Interpreter: /home/daniel/miniforge3/envs/zeaguard/bin/python. Python: 3.12.14 (main, Sep  2 2026, 23:27:36) [GCC 15.3.0]. PYTHONPATH=src:..

| Dependency | Observed version |
| --- | --- |
| PyYAML | 6.0.3 |
| jsonschema | 4.26.0 |
| packaging | 26.3 |
| pytest | 9.1.1 |

Final validation entrypoint: /home/daniel/miniforge3/envs/zeaguard/bin/python scripts/validate_nb04_cp0.py --full-suite, invoked through WSL Ubuntu-24.04. Test subprocesses explicitly set the canonical environment bin directory on PATH and PYTHONPATH=src:.. Exact commands and cwd are recorded in artifacts/validation/nb04_cp0/20261014T204640Z/validation_record.json.

| Run | Passed | Failures | Errors | Skipped | Duration seconds |
| --- | --- | --- | --- | --- | --- |
| cp0_contract | 76 | 0 | 0 | 0 | 25.145 |
| n18_serialization | 55 | 0 | 0 | 0 | 0.464 |
| n20_repro | 74 | 0 | 0 | 0 | 1.373 |
| nb01_inputs_regression | 9 | 0 | 0 | 0 | 0.499 |
| full_suite_isolated | 607 | 0 | 0 | 0 | 114.114 |

Command cp0_contract:

```text
PYTHONPATH=src:. /home/daniel/miniforge3/envs/zeaguard/bin/python -m pytest -q tests/test_nb04_cp0.py --junitxml=/mnt/c/Programming/Python/zeaguard-drylab/artifacts/validation/nb04_cp0/20261014T204640Z/cp0_contract.xml
```

Command n18_serialization:

```text
PYTHONPATH=src:. /home/daniel/miniforge3/envs/zeaguard/bin/python -m pytest -q tests/test_nb04_serialization.py --junitxml=/mnt/c/Programming/Python/zeaguard-drylab/artifacts/validation/nb04_cp0/20261014T204640Z/n18_serialization.xml
```

Command n20_repro:

```text
PYTHONPATH=src:. /home/daniel/miniforge3/envs/zeaguard/bin/python -m pytest -q tests/test_repro.py --junitxml=/mnt/c/Programming/Python/zeaguard-drylab/artifacts/validation/nb04_cp0/20261014T204640Z/n20_repro.xml
```

Command nb01_inputs_regression:

```text
PYTHONPATH=src:. /home/daniel/miniforge3/envs/zeaguard/bin/python -m pytest -q tests/test_nb01_inputs.py --junitxml=/mnt/c/Programming/Python/zeaguard-drylab/artifacts/validation/nb04_cp0/20261014T204640Z/nb01_inputs_regression.xml
```

Command full_suite_isolated:

```text
PYTHONPATH=src:. /home/daniel/miniforge3/envs/zeaguard/bin/python -m pytest -q --junitxml=/mnt/c/Programming/Python/zeaguard-drylab/artifacts/validation/nb04_cp0/20261014T204640Z/full_suite_isolated.xml
```

The full suite contains 607 tests, including the 76 new CP0 tests. Counts from targeted subsets are not added to the full suite as distinct tests. The historical 531 test baseline was not treated as validation of new code. Final observed result is 607 passed, zero failures, errors or skips. The earlier implementation revision had 606 passed in its separate isolated run. It remains a historical validation record.

Faithful isolated copy: /tmp/zeaguard_nb04_cp0_oifaux0j/workspace. Compared 418 copied protected inputs, 18 untracked local/patch files and all 14 data files. All were byte identical to the corresponding source files before tests. The untracked count includes the existing local .claude file and is not a count of new CP0 implementation files. The isolated copy is retained for audit. Historical NB01/NB02/NB03 tests may regenerate and search their existing target inputs inside that copy. They execute no NB04 NTO search or B4 informative calibration campaign. No source upstream file was overwritten.

Final validation record SHA256: ee81534b0bccad3cdfcf584010627157d33eee56797630ba69d92ab67ddb0039.

This run record was completed after validation so that it could report observed
results. The tested implementation, schema, policy, documentary inputs and query
artifacts retain the hashes recorded in the manifest. The final run record hash
is supplied separately in delivery_hashes.json and is not claimed as a test input.

| Log or machine record | SHA256 |
| --- | --- |
| artifacts/validation/nb04_cp0/20261014T204640Z/cp0_contract.log | f671101ed7e5c8d185b510691378febe3353e0df4451b3705c0f8d34850e6459 |
| artifacts/validation/nb04_cp0/20261014T204640Z/cp0_contract.xml | f710b46a3a3108bbd06733d1d58da05358a44aeb135eb90324de0eaf70cce964 |
| artifacts/validation/nb04_cp0/20261014T204640Z/full_suite_isolated.log | 040068933b5dead203b5ef074bb7ddcf4889bdafc6f29712f8d4438c75430d20 |
| artifacts/validation/nb04_cp0/20261014T204640Z/full_suite_isolated.xml | 5226cbee43015cde529582ddda03bef22cffb7ea532147a38b296085df0d7ed3 |
| artifacts/validation/nb04_cp0/20261014T204640Z/n18_serialization.log | 3de65ccf5d79566e77273c1db03ad7fb132b93d88ad31a23e41aa463f375c7a4 |
| artifacts/validation/nb04_cp0/20261014T204640Z/n18_serialization.xml | 9e18369c9e5c602b83098466286b472bf15ecef4d39773cb8b705f2baf7d727e |
| artifacts/validation/nb04_cp0/20261014T204640Z/n20_repro.log | 00610e5fa36d37da05fab2a3972cf554140d05c293c008a1f4e3511465156a60 |
| artifacts/validation/nb04_cp0/20261014T204640Z/n20_repro.xml | 37fe1d630f72227162058f38666a2615d2451c8026768d710c399c12280c0d16 |
| artifacts/validation/nb04_cp0/20261014T204640Z/nb01_inputs_regression.log | 47150831b8aff85930d88a893091ffb4810a1dcf7f23b1d3052f1d9e5e14e60c |
| artifacts/validation/nb04_cp0/20261014T204640Z/nb01_inputs_regression.xml | 8e3a8278bb457ad114e5bec5feafd1dd24f890c37ca111d80b5a0924c94fefc4 |
| artifacts/validation/nb04_cp0/20261014T204640Z/validation_record.json | ee81534b0bccad3cdfcf584010627157d33eee56797630ba69d92ab67ddb0039 |

Development materialization initially stopped on three integration issues before any output write: a schema list length mismatch, a positional call to N18 requiring a keyword argument and a baseline excluded receptor pathway sentinel outside the operational vocabulary. They were corrected before the successful materialization and final tests. The excluded pathway is now represented as NONE while the original NOT_APPLICABLE_IN_THIS_GEOGRAPHY text remains in historical_exposure_pathways. The initial schema failure is retained in artifacts/validation/nb04_cp0/materialize_initial.log. Final test suites have no failure or skip. Materialization does not execute searches or calibration.

## 9. Deterministic artifacts and integrity

| Deterministic output | Verified raw SHA256 |
| --- | --- |
| data/reference/nb04_nto_queries.fasta | 486adee671664db73a2e8ef3dea84650638ce749b835cbd33c97c36a5874a234 |
| data/reference/nb04_nto_queries.tsv | b952466940c776032ad2ad2361668fc118cec7baa7328b01a5d1998e6bdf6007 |
| results/bioinformatics/nb04/cp0/coverage_gaps.tsv | 7af0709b949b06fc5ac7a468f262f6aa647bffddc576b5a7574626ffe5adc374 |
| results/bioinformatics/nb04/cp0/cp0_summary.json | 8e088cc4d75264951895a62ee583bbbf30b4dde939140d062b0c817da6eec258 |
| results/bioinformatics/nb04/cp0/literature_register.tsv | e23b4411fefd80157d80945ff5a3dd2acbaf620f83b12fe89a8c0950c6f3b8a8 |
| results/bioinformatics/nb04/cp0/query_overlap.tsv | 725b2d56216e13a7a052677e013d602c313451ea921855462e17f8e854a00446 |
| results/bioinformatics/nb04/cp0/resource_landscape.tsv | 1dc0da08c14037b80131041405dd6a64c78166f4e81c4ed4bbd1e001ea6c0aa2 |
| results/bioinformatics/nb04/cp0/run_manifest.json | 8c24e8ca2f7476734755a58d60868a6bc2cc25ceee06db8fe3701377776ab4e6 |

run_manifest.json contains seven deterministic payload outputs and their hashes, original document identities, source registry, query specific origin records, reference pins, input hashes and implementation hashes. Its own hash is recorded externally here and in delivery_hashes.json, avoiding a self hash cycle. execution_metadata.json is volatile and excluded from the deterministic set. This run record is likewise versioned separately and its final hash is in delivery_hashes.json.

| Versioned input / implementation / ADR | Verified LF SHA256 |
| --- | --- |
| .gitattributes | e6f2fff699dfe3d7309be5ebb8d5728400d3cc903944a237f5f0c222ededbf2a |
| config/nb04_exposure_scenarios.tsv | 09fcdb662a3063328fa308fd39f13cec9446def1ae7c7fa3642b6c01fd757439 |
| config/nb04_nto_panel.tsv | 7b03b4ec12e2bad7b0d4341233786d238102e07be79e08c1459490c6c6e74cd9 |
| config/nb04_nto_policy.schema.json | 25963a8d3a1735da78f9e6ee7b02cc4c5231e441b84f3862af549f4086e63980 |
| config/nb04_nto_policy.yaml | b928bc02a4414cd9d79f1495ed253cf2a5dc3cf34b6badf41bcf13b5d0943426 |
| config/nb04_receptor_exposure.tsv | 3fbc6edce1c229aff5aef3e871582bb16d6d51fec625aa31240bceb0383f354c |
| data/reference/nb04_cp0_documentary_inputs.json | 0177fb567315067f746b55f6b8de1159139e39d38afafc09d5ee5f72265c5257 |
| data/reference/nb04_upstream_provenance.json | 2ea6f2b771ca58e6b660a214162c93f05706b5ba981114c56e4ae139b3f9bedd |
| scripts/prepare_nb04_cp0_inputs.py | 1379417c69bec5d33b88530b53f90253e3856388ba1932565b3bf1e4445cc4c4 |
| scripts/validate_nb04_cp0.py | fcf1b64e0ba749e49e84f1c07ff1f967a306218e1d16383954358e83d897aa89 |
| src/workstreams/bioinformatics/decisions/0007-nb04-nto-sequence-specificity-policy.md | a5af769accf1d1733cc44f42a8054179124afe4e11f65cd6075f47024293800d |
| src/zeaguard/nb04_cp0.py | 4c6dd83c2eb7a7de654a1886d636f9fdffec898d918930e21e086e7dbab4ac70 |
| src/zeaguard/nb04_policy.py | 7529fabe3b35a2145c565e8d3135b2bc25daf3ae2aa3ac3336b610f38fbc7ddd |
| src/zeaguard/nb04_serialization.py | 74e5360ba458b9240a29dd7a952753736e22e3a884c06c65935b0a29f6e6bd25 |
| tests/test_nb04_cp0.py | a90eb1b860d6064120c8292e02c7e219eddd09ed2998290d53fc28d68415b2b7 |

## 10. Proposed minimal operational repro.yaml delta, not applied

Retain every existing always required path, external tool requirement and supporting config. Change schema_version from 1 to 2 and add only the following nb04_cp0 profile. The existing N20 schema already supports this shape. No CP1 only path is added. Explicit authorization remains required before changing config/repro.yaml.

```yaml
schema_version: 2
checkpoint_required_paths:
  nb04_cp0:
    - config/nb04_nto_policy.yaml
    - config/nb04_nto_panel.tsv
    - config/nb04_exposure_scenarios.tsv
    - config/nb04_receptor_exposure.tsv
    - data/reference/nb04_nto_queries.tsv
    - data/reference/nb04_nto_queries.fasta
    - results/bioinformatics/nb04/cp0/resource_landscape.tsv
    - src/workstreams/bioinformatics/runs/2026-10-14_nb04-cp0-limited-implementation.md
```

The in memory profile test passed without changing the file. It is a path contract check, not a fresh environment gate certificate or G0 certificate. The unchanged operational configuration still has schema_version=1 and no nb04_cp0 profile. The initial snapshot is retained as baseline evidence and is not relabeled as a snapshot of this uncommitted CP0 patch.

## 11. Pending requirements and stage boundaries

| Requirement | Required stage / consequence |
| --- | --- |
| Complementary selection rule, selection_rule_id, multiple admissible configuration treatment and operational CALIBRATION_INCONCLUSIVE definition, distinct from FAILED and NOT_TESTED | Independent audit and project ratification before G0 and any corresponding calibration. CP0 remains partial. |
| D.6 formal added value classification/admission for nine optional historical EXTENDED proposals | Source specific review before admitted EXTENDED ecological interpretation or the applicable G0 scope freeze. No category inferred. |
| Preliminary L9a metadata gaps and unresolved taxids | Remain explicit in CP0. Species taxonomy and eligible final resources must be resolved/assessed in authorized CP1 before their use and freeze. No final assessment is implied by a blank CP0 cell. |
| Qualified external human G0 review, distinct from the producer, with identity, evidence hashes, limitations and relevant interests | Before G0 certification under B6 A1. No staffing matrix or advance assignment is demanded for independent CP0 implementation. |
| Operational repro.yaml nb04_cp0 profile | Separate explicit authorization and versioning before using the operational profile. |
| B4 A1 candidate/fixture/tolerance freeze and numeric B4-12 values | Complete independent technical justification, version, hashes and prior timestamp before any corresponding informative execution. QA-B remains blocking and QA-H remains characterization. |
| B4-8 authorization and B4-9 scale decision | At their original declared moments before affected materialization/harness or G1 calibration. No F01/F04/F05/F06 fixture was generated here. |
| CP1 inventory, acquisition and resource/configuration/calibration artifacts | Remain NOT_STARTED pending G0_PASS and the applicable subsequent authorization. |

## 12. Proposed later versioning and snapshot sequence

1. Produce, independently audit and ratify the complementary selection contract. Preserve historical source bytes and register subsequent adoption separately. Resolve the applicable D.6 optional admission records without inferring scientific criteria.
2. Update the CP0 documentary/policy references to the ratified complement, regenerate affected hashes and rerun the relevant contract and regression checks. Obtain review of that concrete patch.
3. Under separate Git authorization, version implementation/schema/tests and the CP0 input bundle/documentary provenance/ADR/run record in reviewable scopes. Preserve ignored output hash records and the partial historical run record. No commit is performed by this delivery.
4. Under explicit authorization for config/repro.yaml, apply the reviewed minimal profile and version that operational change. Keep always required paths and CP1 timing intact.
5. At the applicable committed clean HEAD, generate and verify a new operational reproducibility snapshot in the canonical environment. Preserve this initial snapshot and all previous snapshots. Record the exact new HEAD and hashes rather than publishing a snapshot over uncommitted code.
6. Obtain the B6 A1 qualified independent G0 review bound to the final package hashes. Only the responsible subsequent certification process may declare G0_PASS. CP1 and corresponding calibration remain blocked until their requirements are met.

## 13. File scope and reproducibility limits

Tracked modification: src/workstreams/bioinformatics/decisions/README.md. CP0 additions are .gitattributes, the five config/nb04 files, four data/reference/nb04 files, two scripts, two CP0 modules, one test module, ADR 0007 and this run record. Ignored results are results/bioinformatics/nb04/cp0, with its manifest and volatile execution metadata. Validation logs/inventories remain under artifacts/validation/nb04_cp0. No CP1 directory or data/external/nto payload directory exists.

A fresh clone can interpret the versioned policy, documentary records and complete query bundle. Reexecution of provenance checks and the full historical regression suite requires the ignored certified upstream source artifacts and input payloads represented by their hashes. Their absence is not evidence of a new source, an unassessable organism or an absence of homology. Full reexecution is not claimed without those inputs.

Artifact integrity, deterministic transformations and test execution are the observed computational evidence. Ecological sufficiency, biological function/identity, exposure, guide formation, uptake, susceptibility, effects and product acceptability are not established by those checks. No scientific disposition or ranking was assigned. No G0_PASS, CP1 execution, real NTO screening or informative NB04 calibration occurred. The final package remains partial with the explicit requirements above.
