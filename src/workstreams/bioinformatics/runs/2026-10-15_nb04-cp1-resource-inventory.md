# NB04 CP1 resource inventory and acquisition

Date: 2026/10/15

## 1. Authority and chronological boundary

The principal owner approved the integrated CP0 package and explicitly waived
the qualified external human review requirement exclusively for G0. The original
B6 A1 and every later gate requirement remain preserved. The existing CP0
consolidated run record section 9 records the owner's exact approval and scope.

G0 was registered before CP1 began. The immutable certification is
data/reference/nb04_g0_certification.json, SHA256
4f4ebd05ad1bf3005ac9796f0d7b3f075c03e7f67de2c02444d349dae8f6fad1.
It examines integrated commit 30a132ff8d9d60c2dd9244027244b103117c500d
and snapshot 42bd6c1e1707fee23882f7cf9ed0965aeb1cd794ebcfa293bce24f792391f32b.
The G0 approval and certification were committed as 65d50d8 on feat/nb04-cp1.
No CP1 acquisition predates that certification.

The latest direct owner instruction authorizes CP1 inventory, identity
resolution, resource selection and acquisition, traceable normalization,
validation and Git publication. The computational author of this run record,
resource assessment and technical verification is the agent. No external human
G1 opinion is represented as having occurred.

## 2. Contract and preserved inputs

PLAN v2.2.5 sections F, J.1, J.1a, J.2 and K apply with the adopted B3, B4 A1,
B5, B6 A1, closure and complementary selection contract. verify_g0 checks every
certified path using its declared raw or LF normalized hash before resource
work and after materialization. CP1 writes separate resource, registry and
assessability artifacts. The G0 panel, policy, queries, scenario, relations,
provenance, CP0 outputs and original execution manifests remain unchanged.

All seven query roles and qualifications remain as certified. The NB02 native
review and its CP5 minimum two, maximum four recommendation gates remain
pending under their actual satisfied conditions. No candidate is added to meet
a quota. Homology, biological identity, functional effect and concern remain
distinct. GITV01009778.1 remains IDENTIDADE_BIOLOGICA_UNRESOLVED.

## 3. Inventory and explicit resource choices

The metadata inventory examined all 21 panel receptors using official NCBI
Datasets species and assembly reports and Entrez nucleotide counts and TSA
summaries. Exact current species name, species rank and taxid are required
before resource use. Nineteen species identities resolved. Anagrus breviphragma
and Gonatopus flavipes had no recognized exact species name in the queried
NCBI Datasets response and remain unresolved. No genus identity resolves them.
Conditional and excluded receptors are inventoried without being adopted for
resource screening. Ecological tiers are unchanged.

The frozen inventory is data/reference/nb04_nto_inventory.json, SHA256
f11ab874762ccd2b23fe8cbff0bdd2eaa4ead64d416893dcf4a6601aae13c027.
It preserves taxonomy evidence, all assembly candidate summaries, source query
counts, retrieval receipts, six selected resource identities, source metadata
and selection rationales. Complete original metadata responses remain under
data/external/nto/cp1_20261015/metadata with hashes and UTC retrieval receipts.
No metadata query during this existing campaign silently resolves a new latest
resource. inventory_nb04_cp1.py reuses and verifies this campaign's responses.

| Organism | Resource identity | Selected representation | Basis |
| --- | --- | --- | --- |
| Apis mellifera | GCF_003254395.2, Annotation Release 104 | Full assembly linked RNA and original GFF | Preferred annotated reference transcript resource under F.1 |
| Zea mays | GCF_902167145.1, RS_2025_02 | Full assembly linked RNA and original GFF | Preferred B73 reference transcript resource. Commercial hybrid diversity remains unrepresented |
| Rhopalosiphum maidis | GCF_003676215.2, Annotation Release 101 | Full assembly linked RNA and original GFF | Preferred annotated reference transcript resource |
| Tetragonisca angustula | GCA_036937485.2, submitted annotation 2024/05/22 | All annotated CDS and original GFF | The assembly directory supplies CDS and no full RNA FASTA. UTR and noncoding coverage remain absent |
| Orius insidiosus | GCYL00000000.1, project GCYL01 | Whole TSA FASTA and GenBank records | Species transcript resource with explicit fragmentation, redundancy, orientation and contamination limitations |
| Peregrinus maidis | GKDL00000000.1, project GKDL01 | Whole TSA FASTA and GenBank records | Same limited TSA interpretation. Genome availability does not make genomic homology transcript target evidence |

No surrogate was adopted. No excluded Dalbulus elimatus or Homalodisca resource
is silently promoted because of its availability. No raw SRA assembly is
performed. Isolated nucleotide submissions and barcodes are not treated as a
species transcriptome. Chrysoperla externa has one mRNA submission and remains
pending resource eligibility review in this package. A completed metadata query
without a detected usable resource is a source scoped gap. It does not establish
global absence of resources, homology or biological concern.

These are project technical resource choices under the existing hierarchy,
independent of any NTO hit. The alignment configuration selection rule remains
NB04_TUNING_QA_CONFIG_HASH_ORDER_HOLDOUT_V1 and has not yet been executed.

## 4. Resource implementation and numerical representation

src/zeaguard/nb04_resources.py supplies hash bound G0 checks, exact taxonomy
validation, official HTTPS acquisition, source MD5 checks when supplied,
authoritative SHA256, atomic payload publication, gzip CRC verification, FASTA
normalization, identifier maps, isolated BLAST database construction and CP1
resource and assessability materialization. scripts/run_nb04_cp1.py exposes
prepare, acquire and verify. scripts/inventory_nb04_cp1.py records source
metadata and query scoped counts. No NB02 or NB03 helper is modified or adopted
as a search kernel.

Original compressed FASTA, annotation or GenBank files and assembly reports are
retained. Normalization preserves every record and base in original order,
uppercases IUPAC DNA and creates unique analysis identifiers with a source ID,
complete header, integer length and sequence SHA256 map. No length filtering,
sequence deduplication, truncation or occurrence cap is applied. U, gap symbols,
duplicate source identifiers, empty records and invalid DNA are rejected.
Ambiguous and originally lowercase bases are counted. Median lengths are stored
as an integer numerator and denominator. N18 serialization is reused for
multivalued cells. These representation rules have no biological decision role.

The database architecture is one database per species, resource, representation
and pinned version. makeblastdb explicitly uses nucleotide type, parsed sequence
IDs, BLAST database version 5 and the source metadata taxid. This taxid states
source attribution and does not exclude contamination. Every generated index
is hashed and its builder version and actual command recorded. Database index
bytes can contain build metadata. Identical byte hashes across independent
index builds are not claimed. FASTA and identifier maps are deterministic for
the same input bytes. No blastn search or informative calibration is invoked.

Final assessability values in the CP1 artifact are resource layer assessments
awaiting G1 certification. Adequate full annotated RNA sets permit ASSESSABLE
with explicit limitations. CDS and fragmented TSA coverage are PARTIALLY_ASSESSABLE.
Scientific data quality remains UNKNOWN as a categorical judgment. Measured
counts and source completeness metrics remain available independently of file
integrity. No new BUSCO or ambiguity threshold is invented. Taxonomy, inventory,
acquisition or eligibility uncertainty leaves final assessability unfilled with
a specific pending basis. Conditional and excluded receptors retain their
scope status. No global ecological coverage conclusion follows.

## 5. Initial validation and remaining CP1 requirements

Before sequence acquisition, 26 deterministic contract tests passed in the
canonical Python 3.12.14 environment. They include fail closed G0 hash checks,
taxonomy name and rank checks, versioned assembly URLs, lossless normalization,
redundant sequence preservation, invalid and truncated FASTA rejection, exact
assessability transitions, source checksum verification and failed database
publication cleanup. No test executes a sequence search or calibration.
The initial command and JUnit evidence are recorded at
artifacts/validation/nb04_g0_cp1/20261015/resource_tests.xml.

G1 remains NOT_DECLARED. Search configuration and calibration artifacts are not
fabricated with FROZEN_AT_G1 states. Required work includes the complete B4 A1
freeze with independently justified numerical per end coordinate tolerances,
the complete finite candidate configuration set and effective defaults, pinned
build, disjoint TUNING and VALIDATION fixtures, instance patterns and expected
coordinates, hashes, version and timestamp strictly before any informative run.
B4 8 authorization and B4 9 scale decisions retain their timing. QA B blocks
configuration freeze. QA H and PC03/PC06 remain CHARACTERIZED_NOT_ASSERTED
where applicable. No numerical tolerance has been inferred from observed hits.

The declared selection rule must then be applied to the frozen campaign.
Calibration, qualifying record truncation demonstration and the independently
reviewed configuration are indispensable G1 requirements. Qualified external
human G1 review is still required. The G0 waiver does not extend to G1.
CP2 and CP3 NB04 remain unexecuted.

The frozen repro.yaml and schema are protected by G0. This resource layer checks
the existing nb04_cp0 environmental checkpoint and explicitly validates its own
CP1 contracts. It does not claim an nb04_cp1 repro profile has been configured.
Any later extension of a G0 certified configuration must use the explicit
applicability and versioning procedure. A renewed environment snapshot records
the actual publication HEAD without replacing earlier snapshots or granting G1.

## 6. Official acquisition references

[NCBI taxonomy metadata](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/taxonomy/taxonomy/)
describes species identity metadata. [NCBI genome data packages](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/command-line/datasets/download/genome/)
describes assembly and annotation resources. Exact API URLs, original FTP
checksum catalogs and TSA project download URLs are retained in the inventory
and acquisition receipts, rather than resolved dynamically by later searches.


## 7. Executed resource layer, source exception and final verification

All six selected resources were acquired after the registered G0 decision.
Original files, source MD5 catalogs where available, HTTP receipts, UTC dates,
SHA256, normalized FASTA, identifier maps and six species specific databases
are materialized under data/external/nto/cp1_20261015. The original acquisition
execution used clean versioned implementation 3a2d3cab9d9583d99a4676bccfca8ae9cd90c952
and its strict environment snapshot
artifacts/reproducibility/20261015T080504253837Z_e37481d6d154/snapshot.json,
SHA256 ebc6ba278110d66da3b0f714695a0abb533681deabec07463d75a57f77d91955.

| Resource | Records | Bases | Normalized FASTA SHA256 |
| --- | --- | --- | --- |
| AM_GCF003254395_2_RNA | 27887 | 98645700 | 8d02f5524887e5a873ecf6991185219f67e97b60c7e65800d61e14c2c6db515c |
| OI_GCYL01_TSA | 25913 | 26926668 | b9775828bf71623342876c4be13011c0de98b22d3ebc8ffce6a41614825bbc3a |
| PM_GKDL01_TSA | 23687 | 57025928 | 17b084765d5615f37707d82efd5d6c98f4916c2277ae15633830e33d7a4e9c96 |
| RM_GCF003676215_2_RNA | 20783 | 48930188 | 05c7a785901ff0ba6ed4e0bf128ab61d41ed608bef0c888f147fce1fd2e8ece3 |
| TA_GCA036937485_2_CDS | 17458 | 33940605 | 30cc04b91c568d11fc7f270bc425b0fd1995694c5e81ac5a5277e7697f313de1 |
| ZM_GCF902167145_1_RNA | 76549 | 162712215 | cb2a632363d19d2ce63b25ed951308dfbd0e823fb07abec84652850df1b4af21 |

Total: 192277 records and 428181304 bases. Counts are resource records, not
independent loci, genes, organisms or experimental samples. Mixed curated,
predicted and noncoding RNA are retained in the full source RNA files. Original
case is recorded in quality counts before uppercase normalization. No sequence
or redundant record was removed.

The own source consistency review checked exact FASTA and annotation accession
set equality and declared species taxids for both TSAs. For each RNA or CDS
assembly resource, every FASTA transcript or protein identifier maps to its own
source GFF annotation, and every GFF contig appears in its own assembly report.
All annotation gzip streams were read to EOF. This is structural and source
annotation evidence. It does not establish absence of contamination, expression,
biological identity of any future hit or functional concern.

The initial generic GFF coordinate check stopped on one source row in maize:

```text
NC_007982.1 RefSeq mRNA 691776 267232 . ? . ID=rna-ZeamMp017;Parent=gene-ZeamMp017;Dbxref=GeneID:37545003;exception=trans-splicing%2C RNA editing;gbkey=mRNA;gene=nad1;locus_tag=ZeamMp017
```

The original GFF SHA256 is
c346640f06bfed314e00173a4fb8dc2ca85952ef9f6c82dfa3c23b3c08fe4675
and its compressed source MD5 matches the official catalog. The source declares
a complex mitochondrial feature, with start greater than end and strand ?.
No coordinate repair or source rewriting was performed. A simple contiguous
interval interpretation is not established for that row. It is retained as
SOURCE_ANNOTATION_REVIEW_REQUIRED, with
SOURCE_ANNOTATION_COMPLEX_FEATURE_REVIEW_REQUIRED_NO_AUTOMATIC_LOCUS_PROMOTION.
All 76549 maize FASTA record identifiers still match source annotation identifiers.
The record therefore distinguishes usable nucleotide content from unresolved
interpretation of an exceptional source annotation. No automatic locus
promotion may rely on this exceptional row. Resolution is a named resource
review issue before G1 certification and any affected locus interpretation.

The [NCBI GFF3 specification](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/)
documents complex annotation conventions. It does not establish a resolution of
the particular row observed here. The initial failed consistency script and
failure record, the completed independent source checks and all original
payloads are preserved under the validation and acquisition paths.

The processing patch additionally rejects resources outside the frozen selected
set, mismatched version or identity, a different selection hash, acquisition
before G0, and payload paths outside data/external/nto. These are integrity
requirements. They introduce no selection thresholds or biological criteria.
The final materialization recomputed source annotation consistency directly
from the acquired files. It did not consume diagnostic outputs as pipeline
data. Original processing receipts and the first CP1 execution manifest remain
preserved in initial_resource_layer under the validation directory. Resource
payloads and built databases were reused after exact hash verification.

The later consistency materialization records HEAD
3a2d3cab9d9583d99a4676bccfca8ae9cd90c952 with git_dirty=true and explicit
allow_dirty=True readiness for that development patch. Its actual implementation
hashes are in the CP1 run manifest. Publication of the tested patch and clean
final snapshot are later events and do not replace that execution HEAD.

Resource layer assessments are materialized for 12 adopted receptors:
three ASSESSABLE, three PARTIALLY_ASSESSABLE and six UNASSESSABLE within the
queried sources. Four CORE receptors have these source scoped resource gaps:
Agallia albidula, Doru luteipes, Exitianus obscurinervis and Paracentrobia
subflava. Pseudoligosita longifrangiata and Pyrophagus tigrinus are the two
EXTENDED source scoped gaps. Their ecological inclusion is unchanged.
Anagrus breviphragma and Gonatopus flavipes require species identity resolution.
Chrysoperla externa requires an explicit adequacy decision about its isolated
mRNA evidence. Their final assessability stays unfilled with a named basis.
The six conditional or excluded rows stay outside the adopted resource scope.
None of these assessments is G1 certified.

The final targeted contract run passed 37 tests in 0.21 seconds. The independent
full suite passed 703 tests in 159.16 seconds, zero failures, errors or skips.
The 37 tests are included in the full total. No informative calibration or
NB04 screening was executed. These are DEVELOPMENT_TEST_PASS results and
resource integrity evidence, with no G1 certification claim.

The full suite used an independent clone and a native Windows copy preserving
bytes and nanosecond modification timestamps for 765 files. No hardlinks or
Git object alternates were used. PYTHONPATH=src:. and the canonical Python
3.12.14 environment were explicit. Existing historical NB02 and NB03 tests ran
only in that copy. Preservation checks confirmed no unexpected modification
among 460 previously protected files. Every G0 certified
artifact hash remains unchanged. The later owner approval appended to the
existing CP0 run record and the latest environment snapshot pointer are the
only expected baseline file changes in that preservation comparison.

Exact commands and logs: artifacts/validation/nb04_g0_cp1/20261015/.
The final targeted JUnit is resource_tests_consistency.xml. Full suite records
are full_suite.json, full_suite.xml and full_suite.log. The full log SHA256 is
e654b01fcd93e94673471e46ec4bef25ffb963d7848c76cbde549ad8d4bb890a, the XML SHA256 is
c235b64f9e014628007816ee567ccdc79c751aa9aaa5c63269bef243045eba69 and isolation record SHA256 is
253db8ddcfefd81e060cf75c82cc74c07b9ab8c95b0e3c56e258787324109b38. Source consistency evidence is
resource_consistency.json and the preservation record is preservation.json.

## 8. Published artifacts, pending requirements and continuation

| Artifact | SHA256 |
| --- | --- |
| data/reference/nb04_nto_resources_manifest.json | 2988284ac3e8a5c790f820dab479dacd5c9834f434eda5c9f6b9076fa2a99c52 |
| data/reference/nb04_nto_resource_registry.tsv | fd4eb4f92898cbe7447c4c7f4ac7db2424613a1eba19f300e3bd559c13580a5a |
| data/reference/nb04_nto_assessability.tsv | d81b50cb1da60f3692deb13c28912ad081f017e1deb1627cf0a4b927ef1807db |
| results/bioinformatics/nb04/cp1/run_manifest.json | b050ea0123a299c4516527d01279186306a2770470ad034455e8f2d7468440fb |

The resource manifest binds acquisition, normalization, identifier maps,
annotation consistency, original processing receipts and all index hashes.
The run manifest binds exact implementation and input hashes and CP1 outputs.
The versioned metadata allows fresh clone interpretation. Full reexecution
requires the recorded payload acquisition paths and certified CP0 artifacts.
It is not inferred from metadata alone.

The state is G0_PASS, CP1 resource layer materialized, G1 NOT_DECLARED.
Indispensable pending work is:

1. Resolve the two named species identities before using or freezing a resource
   for them, close the Chrysoperla adequacy assessment and review the maize
   exceptional annotation without silently repairing source data.
2. Complete the prior B4 A1 freeze, with independently justified numeric per end
   tolerances, actual fixture instances and roles, effective candidate
   configurations and defaults, pinned build, hashes, versions and time.
   Numeric tolerances remain null. No fixture scale is invented or materialized.
3. Execute authorized calibration only after that freeze, apply the existing
   selection rule, demonstrate qualifying record truncation handling, and
   materialize the actual search configuration and calibration evidence.
4. Complete final resource and assessability review and obtain the qualified
   external human G1 opinion required by unchanged B6 A1. The G0 exception has
   no force at G1.

The technical next action is to close source identity and annotation issues
and prepare the independently justified B4 freeze record from the measured
resource scale. Until the complete freeze exists, informative TUNING,
VALIDATION, harness, QA F2 and equivalent executions stay blocked.
Unexecuted calibration has no fabricated CHARACTERIZED, FAILED or
CALIBRATION_INCONCLUSIVE result. B3 fallback A, B5 human concern interpretation,
QA B and QA H roles and biological_decision_role=false remain unchanged.

Final publication is permitted for this completed resource implementation and
its explicitly partial CP1 results. It does not certify G1, authorize CP2/CP3
or transfer the G0 external review waiver to any later gate. The final strict
snapshot and Git integration record are published in the existing validation
directory after integration, preserving all previous execution records.
