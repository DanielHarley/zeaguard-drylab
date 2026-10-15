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
