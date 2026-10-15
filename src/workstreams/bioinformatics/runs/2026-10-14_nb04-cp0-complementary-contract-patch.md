# NB04 CP0 complementary contract patch

Execution record status: CP0_COMPLEMENTARY_CONTRACT_PATCH_VALIDATED.

The project responsible person ratified NB04_CP0_COMPLEMENTARY_CONTRACT_V1.
Independent documentary audit returned READY_FOR_CP0_CONTRACT_PATCH.
The unchanged proposal, ratification record and audit are embedded in
data/reference/nb04_cp0_complementary_contract.json.

The patch materializes the selection rule, outcome definitions, nine nominal
EXTENDED classifications and the explicit ten receptor L9a exception.
Scientific source limitations, ecological CORE, UNKNOWN exposure, N10 PLANT,
B3, B5 and the mandatory B4 A1 freeze remain preserved.

Branch: feat/nb04-cp0.
Initial HEAD: a34892d1874a7ea3298cb1873f02efd4cd99912a.

Original delivery preservation is recorded in
artifacts/validation/nb04_cp0/20261014T231547Z_complementary_contract/previous_delivery_archive.json.
The original partial run record remains unchanged.

G0_PASS=NOT_DECLARED. CP1=NOT_STARTED.
Informative calibration and real NTO searches remain NOT_EXECUTED.
The nb04_cp0 checkpoint profile is exercised in memory only.
config/repro.yaml and the previous snapshot remain preserved.

## 1. Normative authority and artifact identity

The human project decision "Eu ratifico. Pode prosseguir." ratified the complete
complementary proposal and authorized its prescribed localized CP0 patch.
The independent documentary agent audit subsequently returned
READY_FOR_CP0_CONTRACT_PATCH, with zero blockers and zero mandatory patches or
editorial corrections. This documentary agent audit supplies no external human
G0 review. The chronological ratification and audit records are preserved
separately from the unchanged proposal content and embedded in the source JSON.

Proposal SHA256:
617438b9bf5a0a4dd2e80fc832af288432060899e5f615384df3e306bb919c68.

Ratification record SHA256:
a0b3d81d2d94351663a758603470509c91d81d2fdf30e9519c3bf2bbc66d9232.

Independent audit record SHA256:
277ac250c6f66a0ff0d451682f75b08d325a33bd58d7d476a374ff2c22581572.

Compiled complementary source JSON SHA256:
3a89cbbebc9a207e776d2225748bf703a26ab02de56cb4df5f1c31a1cb23e818.

The loader pins this full artifact identity, validates the embedded source hashes
and enforces the ratified structured rules. The policy independently binds the
JSON artifact SHA256. The schema and semantic validator reject altered selection,
result definitions, biological roles and unnamed L9a exceptions.

## 2. Implemented changes and evidence limits

The policy version is 1.1.0. LOCAL_ALIGNMENT_CANONICAL references
NB04_TUNING_QA_CONFIG_HASH_ORDER_HOLDOUT_V1. The rule freezes a finite candidate
set and complete effective technical payloads before TUNING and selects the
first TUNING eligible candidate in frozen full SHA256 order. Free labels and
observed outcomes do not enter the order. VALIDATION confirms that candidate
without selecting a substitute. A subsequent campaign requires unused validation.
The implementation records and validates this contract. It executes no selection
campaign or calibration. The SHA256 ordering is administrative and establishes no
performance optimization, sensitivity ranking or biological implication.

The structured outcome contract distinguishes CHARACTERIZED,
CALIBRATION_INCONCLUSIVE and FAILED. Nonexecution remains an execution or QA
state, without a fabricated calibration result. Demonstrated blocking failure
takes precedence for the same result. QA-H, QA-O and QA-R remain characterization
without weights or new thresholds. Final validation evidence for QA-P remains a
future requirement. Numeric B4-12 tolerances remain null, with complete freeze
mandatory before every informative execution covered by B4 A1.

The nine EXTENDED classifications are materialized as project conventions.
Source justification status is preserved verbatim, including mixed regional
qualifiers for Peregrinus maidis and Tetragonisca angustula. Pseudoligosita's
ADDS_METHOD_REFERENCE records the ratified project comparison purpose and
introduces no empirical discovery. No source status is upgraded by admission.

The nominal ten receptor L9a exception is referenced by
NB04_L9A_NAMED_RECEPTOR_GAP_CONTRACT_V1. Empty preliminary values use
L9a_SCOPE_GAP_REGISTER provenance and L9A_METADATA_NOT_ASSESSED status. Actual
species assessments retain L9a_METADATA and the original scientific vocabulary.
Ten unresolved species taxids remain explicit. Their species identity and
applicable resource assessment must be resolved before CP1 use and freeze.
Genus level evidence cannot supply species identity or species assessment.

## 3. Current materialized package

There are seven queries, 21 nominal receptors, six CORE receptors, one exposure
scenario, 21 receptor by scenario relations, 80 literature records, 29 metadata
landscape records and 31 explicit gaps. The nine within reference query pairs
retain the same full interval partitions and verified shared bases. No query
sequence, overlap, exposure scenario, literature row or landscape record changed
from the original partial delivery. The published 372/373 nt inconsistency is
preserved explicitly.

The ten closed documentary gap records comprise nine formal EXTENDED categories
and the missing selection contract. The remaining gaps comprise ten L9a metadata
gaps, ten species taxids, seven preliminary coverage limitations, one unresolved
optional nominal receptor, one regional parasitoid gap, one phylogenetic coverage
limitation and the named SOIL_OR_RESIDUE gap. Their admission is bounded by the
ratified contract and closure. No gap has been converted into a negative biological
finding, measured exposure or certified resource absence.

normative_reference_pending=false.
certification_status=PENDING_EXTERNAL_HUMAN_G0_REVIEW_AND_OPERATIONAL_REPRO_PROFILE.
G0_PASS=NOT_DECLARED.
CP1=NOT_STARTED.
informative_calibration=NOT_EXECUTED.
real_nto_searches=NOT_EXECUTED.
resource_freeze=NOT_PERFORMED.

Current run manifest SHA256:
b5f2bb5acf8a19e2576e9963c612667fe576c38f3450837cd538484d91f03e6c.

The manifest binds current documentary inputs, implementation and deterministic
outputs. Volatile execution metadata remains separate. This identity refers to
the uncommitted CP0 working tree and supplies no certification of a new Git HEAD.

## 4. Executed validation

The canonical execution used Ubuntu 24.04.4 LTS in WSL, Python 3.12.14 from
/home/daniel/miniforge3/envs/zeaguard/bin/python, with PYTHONPATH=src:.
The environment PATH included the canonical Conda binary directory.

The preparation command was scripts/prepare_nb04_cp0_inputs.py with the repository,
documentary package, amendments, B5 and B6 directories supplied explicitly. The
script checked the expected source hashes before preparing the current records.
The materialization command was python -m zeaguard.nb04_cp0 with the explicit
repository root. Only the CP0 materializer and validators were invoked.

The canonical validation command was:

```text
python scripts/validate_nb04_cp0.py --root <repository> --full-suite
```

Exact subprocess arguments, package versions, execution directories and durations
are recorded in artifacts/validation/nb04_cp0/20261014T232522Z/validation_record.json.
The targeted runs and the full suite are distinct runs, with overlapping tests.
Their counts must not be summed as independent observations.

1. tests/test_nb04_cp0.py: 96 passed, zero failures, errors or skips.
2. tests/test_nb04_serialization.py: 55 passed, zero failures, errors or skips.
3. tests/test_repro.py: 74 passed, zero failures, errors or skips.
4. tests/test_nb01_inputs.py: nine passed, zero failures, errors or skips.
5. Full suite in the faithful isolated copy: 627 passed, zero failures, errors or
   skips, execution duration 123.085990439 seconds.

The isolated copy retained 418 compared protected inputs, 21 untracked patch files
and all 15 data files byte identically before execution. It included independent
regular files and Git history. Its path is recorded in the validation record and
is retained for audit. The main repository upstream artifacts remained preserved.

The tests reject holdout driven selection, postresult ordering, fabricated
calibration results, biological thresholds, altered nominal exceptions, missing
gap provenance, source promotion and changed source content. Existing integrity,
phase boundary, serialization, query provenance and determinism checks remain
active. Every target and full suite run passed in this validation round.

## 5. Historical preservation and Git state

The 40 original delivery files were archived with their original relative paths
and SHA256 values before patching. Their archive bytes match the original delivery
inventory. The original run record remains unchanged at SHA256
abe3440f35853dac13ef6061c4622e3a39a16d8870521632a79b25a24bc819a5.

The original partial manifest is preserved in
artifacts/validation/nb04_cp0/20261014T231547Z_complementary_contract/previous_delivery/results/bioinformatics/nb04/cp0/run_manifest.json
at SHA256
8c24e8ca2f7476734755a58d60868a6bc2cc25ceee06db8fe3701377776ab4e6.
Its earlier path now contains the current materialization. Historical references
in the original unchanged run record refer to that archived version.

Of the 429 protected baseline files, 428 remain byte identical. The only difference
is the previously delivered ADR index update. B3, B4 baseline, B5, adopted
amendments, upstream outputs, repro code/schema and historical line endings remain
preserved. The explicit CP0 text rules in .gitattributes are localized to CP0 files.

config/repro.yaml SHA256 remains
df8c56b873e3090710a54800864077d86391e4a21ba9850b75db38ece7e4d1fb.
The previous reproducibility snapshot SHA256 remains
e396d89e56c1f205030ef19aae9e7fa8e4a217cd212741768be96d01cf5e1534.
The snapshot and its latest pointer were preserved. It remains the clean initial
HEAD snapshot. It does not certify the present uncommitted CP0 patch.

The branch and HEAD remain feat/nb04-cp0 at
a34892d1874a7ea3298cb1873f02efd4cd99912a. Staging remains empty. No commit, push,
PR, merge, branch switch or new reproducibility snapshot was performed.

## 6. Unapplied operational reproducibility delta

The proposed delta changes schema_version from 1 to 2 and adds only the explicit
checkpoint_required_paths.nb04_cp0 profile below. Existing base required paths
and checkpoint=None behavior remain preserved. The complementary JSON is now
required for a complete readable CP0 contract. The profile references this current
run record, with the original partial record preserved separately.

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
    - data/reference/nb04_cp0_complementary_contract.json
    - src/workstreams/bioinformatics/runs/2026-10-14_nb04-cp0-complementary-contract-patch.md
```

This delta is validated in memory with 29 required path PASS checks. Its machine
readable proposal is recorded in
artifacts/validation/nb04_cp0/20261014T231547Z_complementary_contract/proposed_repro_delta.json.
Application requires specific authorization. config/repro.yaml remains unchanged.

## 7. Continuation boundary

The CP0 complementary patch is materialized and development validated. External
human G0 review and certification remain pending. The operational reproducibility
delta and subsequent Git publication require their separate authorizations.
Snapshot renewal must follow the selected versioned state and applicable config.
All CP1 acquisition, actual searches and informative calibration remain behind
G0_PASS and their applicable freeze and authorization requirements.

Current raw hashes and preservation verification are recorded in
artifacts/validation/nb04_cp0/20261014T231547Z_complementary_contract/delivery_hashes.json
and preservation_verification.json. The inventory excludes its own hash to avoid
self reference. The run record is finalized after tests and does not retroactively
alter the validated implementation.

## 8. Technical consolidation and final reproducibility, 2026/10/15

This section records the subsequent technical consolidation. Sections 1 through
7 retain their historical chronology, hashes and statements about the then
unapplied reproducibility profile. The project responsible person authorized
inspection, necessary contract preserving corrections, validation, documentation,
commits, push, PR, merge, synchronization and the final clean HEAD snapshot.
The original supplied authorization has SHA256
103267a8cb88ddc094f364930a4201804e68516d863c3178a6a17e0437a85508.
No additional methodological decision or scientific criterion is introduced.

The observed starting branch was feat/nb04-cp0 at
ac791160e056433d25e818fc94e6f0139810d80f, after NB02 PR 13, with three modified
tracked files, 20 new CP0 files and empty staging. The exact file inventory and
459 protected file hashes are retained in
artifacts/validation/nb04_cp0/20261015_consolidation/before.json.

### 8.1 Contract and package verification

All 43 registered normative document identities were checked against local
sources or exact embedded canonical content. The three embedded complementary
documents retain their original proposal, ratification and audit hashes. Their
compiled JSON retains SHA256
3a89cbbebc9a207e776d2225748bf703a26ab02de56cb4df5f1c31a1cb23e818.
Original status lines remain preserved and their later adoption is separate.

The package retains seven queries, 21 nominal receptors, six CORE receptors,
one NB04_N2_CONSERVATIVE_ENVELOPE_V1 scenario, 21 receptor by scenario relations,
80 literature records, 29 landscape records and 31 gaps. Zea mays remains PLANT,
Apis mellifera represents POLLINATOR and the unnamed SOIL_OR_RESIDUE gap remains
explicit. UNKNOWN exposure, nine ratified EXTENDED categories, ten named L9a
exceptions and their source limitations are preserved. No resource was selected
or frozen. Bundle, certified provenance, reference pins and overlaps were checked.

The versioned scope consists of the three CP0 modules, two preparation/validation
scripts, CP0 and reproducibility tests, policy/schema, panel/scenario/relations,
documentary JSONs, seven-query bundle and provenance, localized .gitattributes,
ADR/index and the two existing CP0 run records. The exact 23 paths are in the
starting inventory and the reviewed PR diff. Existing N18 serialization,
repro.py, repro.schema.json, NB01, NB02 and NB03 implementation are unchanged.
Generated results, logs, validation records and snapshots follow the existing
ignored artifact conventions.

### 8.2 Operational correction and preservation

The CP0 helper previously substituted an in-memory profile for the configured
nb04_cp0 profile. That could mask additional configured paths or an omitted
mandatory path. The summary also continued to record PROPOSED_NOT_APPLIED.

The corrected helper checks the effective N20 profile, rejects omitted mandatory
CP0 paths and retains a read only in-memory proposal fallback for historical
configuration without that profile. The current summary records
CONFIGURED_IN_REPRO_YAML and external human G0 review pending. The new manifest
binds repro.yaml and its schema because that description depends on their actual
content. Three regressions cover additional missing paths, omitted contract paths
and the legacy fallback without mutation.

schema_version=2 and the nine nb04_cp0 paths were already materialized at the
start of consolidation and retain their content. The 20 base required_paths and
supporting_configs list match the starting committed configuration exactly.
checkpoint=None preserves historical order and multiplicity. Explicit nb04_cp0
checks the sorted union of 29 paths. With environment and Git checks, the final
verification contains 40 checks. No legacy readiness implementation was changed.

The original CP0 manifest remains
b5f2bb5acf8a19e2576e9963c612667fe576c38f3450837cd538484d91f03e6c.
A separate materialization under
artifacts/validation/nb04_cp0/20261015_consolidation/materialized_current/
has manifest SHA256
adce402466eac6aa0eb43136b50ed447ce5fb692ee3bd6cf33252878b03a4ba4.
Its six outputs other than the operational summary match the old hashes exactly.
The differences concern summary state, implementation/configuration provenance
and volatile execution metadata. Previous manifests and results were preserved.
The previous implementation bytes affected by the correction are archived under
previous_implementation with their verified execution hashes.

### 8.3 Validation and resolved isolation defect

The verified runtime was WSL Ubuntu 24.04.4 LTS, Python 3.12.14 from
/home/daniel/miniforge3/envs/zeaguard/bin/python, PyYAML 6.0.3, jsonschema 4.26.0,
packaging 26.3 and pytest 9.1.1. BLAST 2.17.0, HMMER 3.4 and dustmasker 1.0.0
satisfy the configured environment contract. PYTHONPATH=src:. is explicit.
The preintegration environmental check passed all 40 checks with dirty state
explicitly allowed for development. The final snapshot requires allow_dirty=False.

The targeted run passed 273 tests with zero failures, errors or skips: CP0 99,
N18 55, reproducibility 74, NB01 inputs nine and NB02 native 36. These overlap
the full suite and are not independent totals. The earlier 663 test execution
remains evidence for its earlier unchanged patch. The operational correction
motivated the new regression runs.

The first isolated full run recorded 665 passed and one failed. The NB03
test_pin_registered_cp0_hashes_equal_a_fresh_cp0_run exposed a copy defect:
the WSL copy preserved PDF bytes but truncated its modification timestamp from
2026-10-03T22:52:24.554220+00:00 to 2026-10-03T22:52:24+00:00. NB03 includes that
timestamp in the documented historical retrieval provenance. Changing only this
field in a copy of the historical JSON reproduced exactly the failing hash
8bd3bc683fdf55c6fc94f5a1f3a706bca9f38e3019903aa16b3c89862750487a.
The full diagnostic is isolation_metadata_diagnostic.json.

A fresh independent Git clone and native Windows copy corrected the isolation
recipe. All 445 compared files matched in bytes and modification timestamps
before repetition, without hardlinks or alternates. The first failed copy and
its logs remain preserved. No NB03 source, pin or historical result was changed.
The completed repeat passed all 666 tests in 168.66 seconds, with zero failures,
errors or skips. It is recorded in full_suite_corrected.json, its XML and log.
Exact commands, timings and preservation
records are under artifacts/validation/nb04_cp0/20261015_consolidation/.

### 8.4 NB02 qualifications and NB04 applicability

The [NB02 analysis](C:/Programming/Python/zeaguard-drylab/src/workstreams/bioinformatics/runs/2026-10-15_nb02-native-correction.md:154)
and current project instruction support keeping the seven queries for their
registered historical sequence comparison purpose. Their sequences, hashes,
formal roles and layered provenance remain unchanged.

D2-L400-0351-0750 remains the computationally preferred provisional representative.
Its decisive zero vectors coexist with an OTHER_TRANSCRIPT packet expanded from
ten to 28 HSPs, requiring actual human review before a native recommendation.
D2-L400-0817-1216 remains a historically selected candidate and sequence comparator.
It leaves the native L400 Pareto and moves to group 7. Its historical top-group
tie is not represented as a current native preference. Both retain CANDIDATE
and historical NB02_CP5 selection provenance. D2-BENCH-0814-1143 retains
REFERENCE_SET without a selection source. The four BicC queries retain NB03
provenance and the published benchmark limitations remain explicit.

GITV01009778.1 remains IDENTIDADE_BIOLOGICA_UNRESOLVED. Homology, biological
identity, functional effect and concern remain separate. Native NB02 human
review and CP5 closure retain their real pending states, with the existing
two-to-four recommendation rule. Those pending states do not automatically
block technical CP0 consolidation or justify changing the historical bundle.

### 8.5 Execution HEAD, publication HEAD and snapshot evidence

The original CP0 execution metadata records a34892d1874a7ea3298cb1873f02efd4cd99912a
and an uncommitted patch. The corrected prepublication materialization records
ac79116 with corrected working-tree code. The later publication commit identifies
the versioned implementation. Neither earlier execution HEAD is retroactively
replaced by that publication commit.

After integration and synchronization, published_materialization in the current
validation directory records the clean integrated HEAD without overwriting
previous manifests. The final snapshot uses the existing repro.run_all_checks,
build_snapshot, write_env_snapshot and assert_environment_ready mechanism,
explicitly with checkpoint="nb04_cp0" and allow_dirty=False. All versioned files
are finalized before snapshot publication. Its final HEAD, location, SHA256,
config/input hashes, tool probes, prior snapshot preservation and latest.json
binding are recorded in snapshot_record.json in the ignored validation directory.
The existing latest_validation.json mechanism points to the consolidated
validation record. These records publish final evidence while keeping the
versioned tree clean and confer no scientific gate status.

### 8.6 Objective readiness for G0

| Scope | Established condition or remaining requirement |
| --- | --- |
| Method authority | PLAN, adopted amendments, complementary selection rule and inconclusive definition retain verified ratified identities |
| CP0 artifacts | Queries, provenance, overlap partitions, preliminary panel, scenario relations, literature, landscape and gaps are validated |
| Operational reproducibility | Schema 2 and nb04_cp0 are configured. Final clean HEAD checks and snapshot evidence are published after integration in snapshot_record.json |
| Historical integrity | Previous outputs, manifests, canonical content and snapshots are preserved. Execution and publication commits remain distinct |
| Human G0 requirement | A qualified external human distinct from the principal producer must review the actual package, provenance, overlaps, preliminary assessability and NB02 qualifications before certification |
| Human record required | Identity, examined artifact/version and hashes, date, reasoned opinion, limitations and relevant participation or interests must be recorded under B6 A1. No opinion is invented here |
| Admitted gaps | Ten L9a scope gaps, ten species taxids and the other named ecological/coverage limitations remain explicit under the adopted contracts. These are not converted into biological absence or an automatic fabricated G0 failure |
| Later CP1/G1 work | Acquisition, species/resource identity before use, final assessability, resource choices, numeric configuration, B4-12 tolerances and the complete pre-informative calibration freeze remain later authorized work |
| NB02 obligations | Native human review and CP5 quantity closure remain pending. No second candidate is added to satisfy the minimum |

G0_PASS=NOT_DECLARED. CP1 NB04=NOT_STARTED.
Informative calibration=NOT_EXECUTED. Real NTO searches=NOT_EXECUTED.
Resource freeze=NOT_PERFORMED. Environment readiness remains distinct from human
review and scientific certification.


## 9. Owner approval, G0 governance exception and certification on 2026/10/15

This section is a later decision and certification. Sections 1 through 8 retain
their historical states and authorship. The principal owner stated directly:

> Eu revisei o material apresentado e aprovo o pacote CP0.

> Dispenso exclusivamente para G0 a exigência de revisão humana externa prevista
> no B6 A1. A certificação deste gate poderá ser concluída pelo responsável
> principal com apoio das verificações técnicas e da revisão computacional por
> agente já realizadas.

This is an explicit governance amendment limited to the external human review
requirement of G0. The original B6 A1 remains byte preserved, SHA256
9ea167a88359f78e916d753865d7d40a5c37d2ff04d3a09d73c647c3aebaa62b.
Scientific and technical requirements and the review requirements of G1, G2,
G3, G5 and G6 retain their scope. The owner review is attributed to the principal
owner. The technical checks and computational review are attributed to the
agent. External human review was waived for G0 and was not performed. No
independent human opinion, qualification or conflict declaration is fabricated.

The examined checkout was clean on feat/nb04-cp0 at integrated implementation
30a132ff8d9d60c2dd9244027244b103117c500d, CP0 PR 14. The renewed examination
verified all 43 normative identities, ratified complementary authority, seven
sequence and selection provenance chains, source manifests and certifying Git
objects, deterministic overlaps and sequence consistency, 21 preliminary panel
rows, six CORE receptors, one scenario, 21 relations, 80 literature rows, 29
landscape rows and 31 explicit gaps. Zea mays remains on the PLANT track and
Apis mellifera represents POLLINATOR. The documented soil or residue gap remains.

The current NB02 analysis was examined before affirming bundle applicability.
0351 remains a provisional computational representative requiring native human
review. 0817 remains a historical selected sequence comparator despite leaving
the native Pareto. The benchmark retains REFERENCE_SET. Their roles, seven
sequences and historical provenance are preserved. GITV01009778.1 remains
IDENTIDADE_BIOLOGICA_UNRESOLVED. NB02 native CP5 remains incomplete under its
actual human review and unchanged minimum two, maximum four recommendation gates.

All 40 environment checks passed again at the examined clean HEAD. The snapshot
artifacts/reproducibility/20261015T072304603205Z_e37481d6d154/snapshot.json has
SHA256 42bd6c1e1707fee23882f7cf9ed0965aeb1cd794ebcfa293bce24f792391f32b.
Canonical runtime remains WSL Ubuntu 24.04, Python 3.12.14, BLAST 2.17.0,
HMMER 3.4 and dustmasker 1.0.0. Existing 273 targeted and 666 isolated full suite
passes were reused after verifying unchanged relevant implementation and input
hashes. They are prior executions, not tests claimed as newly executed today.

G0_PASS is now registered under the owner's approval and G0 only exception.
The immutable machine readable certification is
data/reference/nb04_g0_certification.json, SHA256 4f4ebd05ad1bf3005ac9796f0d7b3f075c03e7f67de2c02444d349dae8f6fad1.
It binds the 26 examined artifact paths with explicit raw or LF normalized
hash semantics, both preserved CP0 manifests, normative identities, examined
implementation commit and snapshot. The published CP0 manifest remains
adce402466eac6aa0eb43136b50ed447ce5fb692ee3bd6cf33252878b03a4ba4 and the
original manifest remains
b5f2bb5acf8a19e2576e9963c612667fe576c38f3450837cd538484d91f03e6c.
The fresh verification evidence is
artifacts/validation/nb04_g0_cp1/20261015/g0_verification.json, SHA256
8d246d20348ef9ab05aec357550e3e4e1eccd3fda91ce00334ddb8e328f0519b.

Frozen CP0 policy and execution metadata retain their pre certification states.
They are historical artifacts. This later hash bound certification is the
authoritative operational progression record. CP1 was not started at the time
of these G0 checks. The owner's conditional authorization now permits CP1 on a
new branch. Calibration remains unexecuted and requires the prior complete
B4 A1 freeze, including independently justified numeric tolerances. Later human
gate reviews remain required. No resource or search parameter is certified by G0.
