# Run ID

`2026-11-15_nb01-dsrnase-locus-mapping`

## Date

2026-11-15 (implementation and first full execution, UTC-03:00).

## Commit

Base commit `08079cd65f76b3d542b6981840a53e194552b060` (`origin/master`, merge of PR #22, which carries ADR 0008). The local `master` of the checkout this branch was cut from was two commits behind that at the time, so `origin/master` was used as the base: it is the current main line, and cutting from the stale local `master` would have dropped ADR 0008 and made this record's ADR number wrong.

Implementation commit of this branch: **`f00b87d5f1a52d0a0402a96c136d5b4dd79dea2e`**, which is the commit the clean-clone reconstruction was verified against. This record's own clean-clone outcome is added by the commit that follows it.

The mapping records the commit it ran at in `manifest.json` under `git`. In the cross-OS worktree used for implementation that field came back **empty**; in the clean clone it is populated with `f00b87d`. See Anomalies item 4.

## Branch

`feat/nb01-dsrnase-locus-mapping`, created from `origin/master`. Semantic type `feat`: a new persisted capability (a command, its declared inputs and its outputs), per the change-type order in CONTRIBUTING.md §5.

Implemented in a separate git worktree rather than by switching branches in the main checkout, because that checkout held another session's uncommitted work. The branch's upstream, which `git worktree add` had set to `origin/master`, was unset immediately so that no bare `git push` from it could target `master` (CONTRIBUTING.md §7).

## Execution status

`COMPLETED`

Completed means the mapping ran end to end from the declared inputs in an empty output directory and passed its integrity checks. The status records execution of the declared method. The alternate assembly search yielded no locus under the applied parameters, leaving the comparison between haplotypes inconclusive. See Results and Anomalies item 1.

Ran in the canonical Linux environment (conda env `zeaguard`, WSL2, Python 3.12.14, BLAST+ 2.17.0).

## Question / objective

Map the three published Dmai-dsRNase coding sequences to the *Dalbulus maidis* genome in order to answer the two questions the NB01 family audit left explicitly open. That audit's run record, `2026-11-13_nb01-dsrnase-protein-audit.md`, is **not in this tree**: it lives on the branch `feat/nb01-dsrnase-protein-audit`, which is not yet published, so it is referenced here by name rather than by link and this run deliberately does not depend on its code.

1. does Dmai-dsRNase-3 occupy a locus of its own, distinct from those of dsRNase-1 and dsRNase-2;
2. do the two complete TSA records attributed to dsRNase-2, `GITV01008430.1` and `GITV01012450.1`, come from one genomic locus or from distinct loci (paralogues, alleles, or an assembly artefact).

The first thing to establish was whether a usable *D. maidis* assembly exists at all. That was treated as a question, not an assumption: had none existed, the finding would have been the result, and no mapping against another species' genome would have been attempted.

## Inputs

All declared in [`data/reference/nb01_dsrnase_locus_panel.json`](../../../../data/reference/nb01_dsrnase_locus_panel.json). The mapping verifies every declaration before using the file and refuses to run on any mismatch. Criteria and thresholds are **not** in the panel: they are constants of the module, pre-registered in [ADR 0009](../decisions/0009-nb01-dsrnase-locus-assignment-criteria.md) and recorded in `manifest.json`, so there is one place to change them and no chance of a panel and a module disagreeing silently.

### The assembly survey, which is itself a result

Queried on 2026-11-15. *Dalbulus maidis* resolves to **taxid 74065**; the NCBI assembly database returns **three** assemblies for it.

| accession | name | level | scaffolds | scaffold N50 | coverage | submitter | used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GCA_975739785.1` | ihDalMaid1.1 | Chromosome (10 chromosomes: 1-9, X) | 140 | 93,705,284 | 75x | Wellcome Sanger Institute | **yes**, primary target |
| `GCA_975739835.1` | ihDalMaid1.1 alternate haplotype | Scaffold (alternate-pseudohaplotype) | 7,864 | 492,899 | 75x | Wellcome Sanger Institute | **yes**, second target |
| `GCA_054756405.1` | CIAP v1 | Contig | 22,333 | 50,514 | 20x | CIAP-INTA | no, see below |

So the answer to the first question is **yes**: a chromosome-level assembly exists, flagged by NCBI as the reference genome for the species, released 2025-10-26. The two declared targets share biosample `SAMEA117578701`, i.e. they are the two pseudohaplotypes of one individual.

`GCA_054756405.1` was surveyed and deliberately **not** used, recorded in the panel under `surveyed_not_used` with the reason: at contig level with N50 50,514 nt and 20x coverage, a dsRNase locus with introns can straddle a contig boundary, so observing one locus there could not be distinguished from contig fragmentation, and a collapsed duplication is likelier than in the 75x chromosome-level assembly. It could therefore neither confirm nor refute a copy-number observation, which is the only thing it would have been added for.

**No RefSeq (`GCF_`) assembly exists for any of the three.** This run's own survey checked NCBI only and found no gene annotation for any of the three there; it did not check Ensembl, and makes no claim about whether an independent annotation existed anywhere at the time. This run's declared genomic targets were the two assembly FASTAs — no GFF3 was among them, and no locus call in this run could be checked against one. A later round on this branch retrieved and checked an Ensembl AEGIS gene annotation for the primary assembly for the first time. See the addendum below.

### Mandatory inputs and how each one is verified

| role | path | verified by | value |
| --- | --- | --- | --- |
| query source | `data/reference/target_anchor_sequences.fasta` | `sha256_lf_normalized` | `10cd666816d76fd4a87ae769849008551a40ddfde4081722d33f73e54cbea89b` |
| primary mapping target | `data/external/nb01_locus_mapping/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz` | `sha256` + `sha256_decompressed` | `aef4d8ec0891bece052bc58afa5b0da3e2a2bf047f9283032bbf253459509184` / `54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04` |
| alternate haplotype | `data/external/nb01_locus_mapping/GCA_975739835.1_ihDalMaid1.1_alternate_haplotype_genomic.fna.gz` | `sha256` + `sha256_decompressed` | `90e6c6ab4abcd7fb4fd8c53610e65c7dcc86a1cab406d9573c9b25743f8e1757` / `131755bbd68759ba9164eebc9e41cb944a9a2ce8593c9cfbd1b1b150f4f9036e` |

The anchor FASTA is tracked by git and is **not** pinned to `eol=lf` in `.gitattributes`, so the raw hash of the working copy depends on the checkout. Only the LF-normalised hash is authoritative; the panel records the CRLF value under `sha256_working_copy_crlf` and the mapping does not check it. The two assemblies are git-ignored binaries, so their raw hash is stable.

**A hash is not enough, and the mapping does not treat it as enough.** It also recomputes, from each assembly file at every run, the number of sequences, the total length, the ungapped length, the scaffold N50 and the number of assembled molecules, and compares them with the panel. A hash proves the bytes did not change; these prove the file is the assembly the panel describes.

### Queries, derived rather than transcribed

One query per published dsRNase: the CDS, derived from the Trinity transcript in the anchor FASTA as the longest stop-delimited ORF read from its first methionine. Nothing is read from the article or its supplement, so this run needs **no** PDF and no text layer — unlike the family audit, every input is either in the checkout or reconstructible from a versioned public URL.

The published Table 1 ORF coordinates are declared in the panel, and the derivation is checked against them. All three agree exactly, and the run aborts if any does not:

| target | transcript | published ORF | derived ORF | CDS nt | protein aa | start | stop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dsRNase-1 | `TRINITY_DN13786_c0_g1_i8` | 1640-318 | 1640-318 | 1323 | 440 | ATG | TAA |
| dsRNase-2 | `TRINITY_DN22752_c0_g2_i1` | 1461-37 | 1461-37 | 1425 | 474 | ATG | TAA |
| dsRNase-3 | `TRINITY_DN5008_c0_g1_i24` | 1539-304 | 1539-304 | 1236 | 411 | ATG | TAA |

The query is the CDS only, never the full transcript: coverage over a full transcript is dominated by flank length (ADR 0004), and the flanks carry the tandem-repeat structure the NB01 investigation observed in the 3' flank of `GITV01012450.1`. Restricting the query to the CDS keeps coverage interpretable and keeps that known repeat out of the query.

### Reconstructing every input from a clean checkout

One of the three comes with the checkout: `data/reference/target_anchor_sequences.fasta`. The two assemblies are git-ignored and must be downloaded. From the repository root:

```bash
mkdir -p data/external/nb01_locus_mapping
```

```bash
curl -sL --retry 3 -o data/external/nb01_locus_mapping/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/975/739/785/GCA_975739785.1_ihDalMaid1.1/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz
```

```bash
curl -sL --retry 3 -o data/external/nb01_locus_mapping/GCA_975739835.1_ihDalMaid1.1_alternate_haplotype_genomic.fna.gz https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/975/739/835/GCA_975739835.1_ihDalMaid1.1_alternate_haplotype/GCA_975739835.1_ihDalMaid1.1_alternate_haplotype_genomic.fna.gz
```

The `reconstruction` field of each panel entry carries the same command, and the mapping prints the declared URL of whichever input is missing. This procedure was executed in a clean clone; see Validation.

## Configuration

No new dependency and no change to `environment.yml`: `blastn`, `makeblastdb` and `blast_formatter` ship with the already-declared `blast>=2.13`. No existing module was modified — `nb01_locus.py` is additive, and the only edit outside it is the ADR index in `decisions/README.md`.

This branch deliberately does **not** depend on `zeaguard.nb01_family`, which lives on the unpublished branch `feat/nb01-dsrnase-protein-audit`. The input-verification helpers (`_resolve`, `_check_hash`, `HASH_MODES`, `load_panel`) are therefore duplicated here with identical names and semantics, with a comment saying so, so the two can be factored into one place once both are merged.

Pre-registered criteria, all from ADR 0009 and none adapted after seeing results:

| parameter | value |
| --- | --- |
| `blastn` | `-task blastn -dust no -evalue 1e-5` (the discovery set of ADR 0004) |
| `-max_target_seqs` | 20,000, above the 7,864 sequences of the larger assembly, so the limit provably cannot truncate |
| locus distance (`MAX_INTRON_NT`) | 50,000 nt |
| reporting coverage | 50.0 % (the discovery threshold of ADR 0004) |
| assignment coverage | 90.0 % |
| assignment identity | 98.0 % |
| junction overlap tolerance | 10 nt |

## Method

Entry point `zeaguard.nb01_locus.run_mapping`; reused from `zeaguard.nb01_dsrnase_investigation`: `find_orfs`, `orf_sequence`, `translate`, `parse_hsp_table`, `Hsp`, `merge_intervals`, `CommandLog`, `format_fasta`, `write_tsv`, `file_record`, `lf_sha256`, `sha256_file`, `sha256_text`, `_git`.

Per declared assembly: verify the hash, expand the `.gz`, verify the hash of the expansion, scan it once for per-sequence metadata and whole-assembly statistics, check those against the panel, `makeblastdb`, `blastn` into an ASN.1 archive, render the archive to a table and to pairwise text, then:

1. **cluster** HSPs of one query on one sequence and one strand into loci, splitting when the genomic distance exceeds 50,000 nt; strands never merge;
2. **tile** each locus best-score-first into one alignment block per inferred exon, allowing at most 10 nt of query overlap and no genomic overlap;
3. **screen** on coverage *before* reading any genomic sequence — with word size 11 against 972 Mb most clusters are short incidental matches, and loading every sequence carrying one would mean loading most of the genome;
4. **measure** coverage, identity over the tiling, span, inferred exon and intron structure, junction offsets, splice termini, assembly-gap content of the span, distance to the sequence ends, and colinearity;
5. **assign** a locus only when exactly one meets both assignment criteria;
6. **decide distinctness** pairwise and **report the locus count** for each published CDS under a neutral key.

The expanded FASTA and the BLAST database go to a temporary directory and are deleted when the run ends. They are derived, not results, and together are about 2.5x the assembly in size. Keeping them off the working tree also matters for speed: building the primary database on a 9p-mounted Windows working tree did not finish in 13 minutes, and finished in about 7 seconds on native disk.

Run it with (Linux, canonical `zeaguard` environment, from the repository root):

```bash
PYTHONPATH=src python -m zeaguard.nb01_locus --root .
```

## Outputs

Written to `results/bioinformatics/nb01/mappings/dsrnase_locus_mapping` (git-ignored).

| file | content |
| --- | --- |
| `queries.tsv` | per CDS: lengths, ORF strand and frame, published versus derived coordinates and whether they agree, start and stop codon, sha256 of CDS and protein |
| `loci.tsv` | one row per reported locus with every statistic the call is to be judged on, including the contiguity and repeat columns ADR 0009 rule 7 requires |
| `assignments.tsv` | one row per (assembly, CDS): the assigned locus or the reason none could be, with the counts of passing and related loci |
| `distinctness.tsv` | one row per (assembly, CDS pair): distinct, same, or indeterminate, with the gap or overlap between spans |
| `copy_number.tsv` | one row per (assembly, CDS): the locus count under a neutral interpretation key, with the assembly's contiguity |
| `manifest.json` | tool versions, command lines, parameters, declared versus observed hashes and assembly statistics, BLAST counts, and sha256 of every output |
| `raw/` | `cds_queries.fna`, the two `blastn` ASN.1 archives with their table and pairwise renderings, the two `makeblastdb` logs |

## Validation / QC

- `pytest tests/test_nb01_locus.py -q`: **50 passed.** The synthetic HSPs and synthetic genomes exercise every `INDETERMINATE` branch that the real data does not reach (no locus, two passing loci, overlapping spans, unassigned pair, non-colinear tiling, a cluster below the reporting threshold, a diverged locus that is `RELATED` not assignable), and the hash verification is exercised with the same content as LF and as CRLF. One test runs the real derivation against the real anchor FASTA, so it fails if the published ORF coordinates ever stop falling out of the anchors.
- `pytest -q` (full suite): **1725 passed, 10 failed, 67 skipped, 12 errors.** Every failure and error is in `tests/test_nb04_cp0.py` and is `FileNotFoundError: results/bioinformatics/nb02/cp5/run_manifest.json`, a prior-stage output that exists only in a checkout where NB02 CP5 has been run; this worktree's `results/` starts empty. **Verified pre-existing and unrelated:** a pristine clone of `master` (`9471494`, which does not contain `nb01_locus.py`) produces exactly the same 10 failures and 12 errors. Nothing in this branch is implicated.
- Run end to end in an empty output directory three times: before the splice-boundary correction of Anomalies item 2, after it, and once more at the delivered commit `f00b87d`. Locus coordinates, coverage, identity, exon counts, intron sizes and every assignment were identical across all three; only the splice columns changed, at the second run. The third run is the one recorded here, and the five output tables of the second and third are byte-identical.
- Every declared hash agreed with the observed one: both assemblies by `sha256` and by `sha256_decompressed`, and the anchor FASTA by its LF-normalised hash (`declared_hash_agrees` true throughout `manifest.json`).
- Every declared assembly statistic agreed with the file as read, for both assemblies.
- `-max_target_seqs` provably did not truncate: `observed_subjects_below_limit` is true for both assemblies (1 and 0 subjects with HSPs, against a limit of 20,000).
- **Controls for the alternate haplotype search.** The positive control produced the expected self match. The Results section records that control and the sensitivity sweep.
- **Internal consistency of the tiling.** For each locus the total block-column count exceeds the CDS length by exactly the total query overlap at the junctions: 11 = 11, 25 = 25, 13 = 13 for dsRNase-1, -2 and -3. With the union query coverage at 100 % and no positive offset anywhere, this means each tiling accounts for the whole CDS — counted once except at the tolerated overlaps, where those positions are counted twice — and nothing outside it. So the aggregate identity is computed over alignment columns that all belong to the CDS, with the overlap fully quantified rather than unknown. Asserted as an invariant in the tests as well.
- **Clean-clone reconstruction, executed against the delivered commit `f00b87d`.** The reconstruction commands reproduce both declared hashes, the mapping refuses with exit 2 while the inputs are absent, 50 tests pass in the clone, and all five output tables come back byte-identical to the run recorded here. Full outcome in the dedicated section below.

## Results

### Question 1 — historical result of the BLAST clustering: three disjoint alignment intervals, `DETERMINED`

In the primary assembly all three CDS are assigned, each to exactly one locus, and all three loci lie on **chromosome 1** (`OZ319704.1`, 122,877,750 nt), on the plus strand, megabases apart:

| CDS | span on `OZ319704.1` | span nt | union query coverage | aggregate block identity | block columns | mismatch | gaps | inferred exon blocks | inferred introns | colinear | assembly gaps in span | related loci |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dsRNase-1 | 60,966,751-60,973,368 | 6,618 | 100.0 % (1,323 / 1,323 nt) | 99.850 % | 1,334 | 2 | 0 | 6 | 5 | yes | 0 | 0 |
| dsRNase-2 | 69,024,822-69,037,412 | 12,591 | 100.0 % (1,425 / 1,425 nt) | 99.931 % | 1,450 | 1 | 0 | 7 | 6 | yes | 0 | 0 |
| dsRNase-3 | 122,005,058-122,014,482 | 9,425 | 100.0 % (1,236 / 1,236 nt) | 99.600 % | 1,249 | 5 | 0 | 5 | 4 | yes | 0 | 0 |

**How to read those two columns, because neither is a single end-to-end alignment.** No locus here was aligned to its CDS in one piece; each is a set of local BLAST alignment blocks (HSPs) tiled together by the method of ADR 0009 rule 4.

- **Union query coverage** is the union of CDS query positions covered by at least one of those blocks, divided by the CDS length. 100.0 % means every one of the 1,323 / 1,425 / 1,236 coding positions falls inside some block — not that any one alignment spans the CDS.
- **Aggregate block identity** is computed over the columns of the tiled blocks taken together: matched columns divided by total block columns. Because consecutive blocks **overlap on the query** at the tolerated junctions, some query positions sit in two blocks and therefore enter that calculation **more than once**. This is why the block-column count exceeds the CDS length in every row (1,334 > 1,323; 1,450 > 1,425; 1,249 > 1,236). The overlap is confined to the junctions and is small, but the figure is an aggregate over alignment columns, not a per-position identity over the CDS.

Confirmed per CDS from the recorded HSP table (`raw/blastn_ihDalMaid1.1_primary.outfmt6.tsv`) and the `exon_blocks_query` column of `loci.tsv`; the query blocks do overlap in all three, though not at every junction:

| CDS | query blocks | junctions with query overlap | overlap sizes (nt) | query positions counted twice |
| --- | --- | --- | --- | --- |
| dsRNase-1 | `1-121;122-252;251-487;482-672;671-901;901-1323` | 4 of 5 | 2, 6, 2, 1 | 11 |
| dsRNase-2 | `1-66;59-179;176-459;458-668;667-900;896-1184;1181-1425` | 6 of 6 | 8, 4, 2, 2, 5, 4 | 25 |
| dsRNase-3 | `1-102;99-458;457-643;639-872;871-1236` | 4 of 4 | 4, 2, 5, 2 | 13 |

dsRNase-1 is the one exception worth naming: its first junction (blocks `1-121` and `122-252`) is contiguous with no overlap, so 4 of its 5 junctions overlap, not all 5. For dsRNase-2 and dsRNase-3 every junction overlaps. In all three the doubly counted total equals the excess of block columns over CDS length exactly (11, 25, 13), so the overlap is fully accounted for and nothing outside the CDS enters the identity.

**The exon blocks and introns are inferred, not observed.** The two columns above count tiled alignment blocks and the gaps between them; they are not an annotation and no splice-aware alignment was used. The boundaries carry real uncertainty: the junction overlaps above *are* that uncertainty, and the first implementation of the splice check read the wrong two nucleotides straight off a block edge for exactly this reason (Anomalies item 2). Across these 15 inferred junctions the offset search found a **candidate** `GT..AG` motif at 7; a motif found by shifting a boundary inside its ambiguity window locates a position that could be a donor-acceptor pair, and does not confirm that any intron is spliced there.

All three pairs are `DETERMINED` distinct, by `SAME_SEQUENCE_NON_OVERLAPPING_SPANS`:

| pair | gap between spans |
| --- | --- |
| dsRNase-1 / dsRNase-2 | 8,051,453 nt |
| dsRNase-1 / dsRNase-3 | 61,031,689 nt |
| dsRNase-2 / dsRNase-3 | 52,967,645 nt |

The distinctness does not rest on coordinates alone, which is what ADR 0009 rule 7 exists for. The three loci carry **no assembly gap** inside any span, all sit inside a 122.9 Mb assembled chromosome rather than an unplaced scaffold, each tiling is colinear, and each CDS reaches the 50 % reporting threshold at **exactly one** place in the whole 972 Mb assembly — `n_related_loci` is 0 for all three. That last number is the repeat measure for the query: the three paralogues are divergent enough that none of them reaches half-coverage at the other's locus, so there is no repetitive region in which two of them could be confused. The nearest locus to a sequence end is dsRNase-3, 863,268 nt from the end of the chromosome.

### Question 2: one locus detected for the published dsRNase-2 CDS

The [operational reference](../../../../data/reference/nb01_dsrnase2_operational_reference.json) records CDS of 1425 nt with distinct SHA256 hashes for `GITV01008430.1` and `GITV01012450.1`. The run queried the published CDS, which exactly matches `GITV01008430.1`. The genomic origin of `GITV01012450.1` remains `unresolved`.

The locus counts below apply to the published CDS query under the declared criteria.

| assembly | loci at assignment criteria | related loci | key |
| --- | --- | --- | --- |
| `ihDalMaid1.1_primary` | **1** | 0 | `ONE_LOCUS_DETECTED` |
| `ihDalMaid1.1_alternate` | 0 | 0 | `NO_LOCUS_DETECTED` |

In the primary assembly, one locus met the assignment criteria for the published dsRNase-2 CDS. The union of the tiled alignment blocks covered all 1,425 coding positions. Aggregate identity was 99.931 % across 1,450 alignment columns (25 query positions counted twice at the six overlapping junctions). No other locus in that assembly reached the 50 % reporting threshold.

### Alternate assembly search and controls

Under the parameters applied for ADR 0009 rule 10, `blastn` returned **0 HSPs** for all three published CDS against `GCA_975739835.1`. All three queries are `INDETERMINATE / NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA` in that assembly and all three pairs are `INDETERMINATE / UNASSIGNED_LOCUS`.

Since "no hits" is also what an empty or broken database produces, three controls were run before reading anything into it:

1. **Positive control.** A 3,000 nt slice taken from an alternate-haplotype scaffold (`CDKMJQ010000001.1`), searched against the database built from that same assembly, finds itself at 100.000 % identity over 3,000 nt, e-value 0.0, bit score 5,411, and returns 33,739 HSPs in total. The database and the search work.
2. **Sensitivity sweep.** The same three CDS against the same database: 0 HSPs at e-value 1e-5, 9 at 1, 55 at 10, 3,781 at 1,000; 0 with `dc-megablast` at e-value 10. At e-value 1,000 the best hits are 23 to 53 nt fragments with bit scores 39 to 43 — noise-length matches, nothing resembling an exon of a 1.2 to 1.4 kb CDS.
3. **Calibration on the primary.** The same sweep against `GCA_975739785.1` gives 57 HSPs at 1e-5 (the 18 tiled exons plus their lower-scoring alternatives) and 187 at e-value 10 spread over all ten chromosomes, confirming that the declared 1e-5 cutoff is what isolates the real loci from relaxed-threshold noise.

The search detected no locus in the alternate assembly under the applied parameters. The comparison between haplotypes remains inconclusive.

### Inferred exon/intron structure, and the candidate `GT..AG` motifs found at its junctions

| CDS | inferred exon blocks | inferred intron sizes (5'->3', nt) | junction offsets (nt) | candidate `GT..AG` motifs found in the window |
| --- | --- | --- | --- | --- |
| dsRNase-1 | 6 | 293; 1,139; 1,230; 1,606; 1,016 | 0; -2; -6; -2; -1 | 2 of 5 (shifts 0, +6) |
| dsRNase-2 | 7 | 2,294; 2,525; 1,575; 1,189; 1,494; 2,064 | -8; -4; -2; -2; -5; -4 | 3 of 6 (shifts +9, +2, +2) |
| dsRNase-3 | 5 | 403; 1,240; 5,125; 1,408 | -4; -2; -5; -2 | 2 of 4 (shifts +2, +7) |

A negative junction offset is alignment ambiguity, not missing CDS: consecutive blocks overlap by a few query nucleotides there, so those positions are covered twice rather than not at all. In each of the three queries the union of the blocks covers every position of the CDS, which is the observation behind the 100 % union query coverage. The overlaps explain something separate: the repeated counting in the aggregate block identity, where those doubly covered positions enter the calculation twice.

Across the fifteen inferred junctions the offset search found a candidate `GT..AG` motif at seven, inside the +/-10 nt ambiguity window, and none at the other eight. Seven candidate motifs are not seven confirmed intron boundaries: the search reports that some shift within the window puts a `GT..AG` at the junction, which is consistent with a canonical intron there and is not evidence that the intron is spliced at that position. Two of the shifts found, +9 and +7, sit near the edge of the window, which suggests a wider window would turn up further candidates. **The window was not widened.** It is tied to the tiling tolerance, it was fixed in ADR 0009 before any alignment was run, and changing it after seeing the results is exactly what that rule forbids. A wider, independently justified window is recorded as a revision condition instead.

## Interpretation

Conditional on the declared method and ADR 0009:

**Historical result of the BLAST clustering: three disjoint alignment intervals, `DETERMINED`.** The clustering and tiling step of this run (ADR 0009 rules 4 and 8) found that the three published CDS correspond to three separate genomic locations on chromosome 1 of `GCA_975739785.1` — three colinear, mutually disjoint alignment-block intervals separated by 8.1, 53.0 and 61.0 Mb. For each, the union of its tiled alignment blocks covers every coding position of its CDS, the aggregate identity over those blocks' columns is 99.6 % or better, the span is gap-free sequence inside an assembled chromosome, and it is the only place in the assembly where that CDS reaches half coverage. `DETERMINED` is the outcome of that clustering and distinctness test — interval disjointness — and is not, by itself, a statement that each interval is the locus of a single gene.

The distinctness rests on the three intervals being disjoint and megabases apart, which is a statement about genomic position and is unaffected by how the within-locus coverage and identity are aggregated. The inferred exon boundaries inside each interval are a separate, weaker claim and are not what this disjointness finding depends on.

**The current result is narrower than "question 1 fully resolved."** The three alignment-block intervals remain disjoint; nothing in the addendum below relocates or merges any of them. Separately, whether the full published dsRNase-3 CDS attributes to a single gene is `INDETERMINATE`: the addendum finds the published CDS's ends corresponding to coding segments of two different annotated genes, with an intermediate HSP that corresponds cleanly to neither. Interval disjointness for the three loci does not, by itself, establish single-gene attribution for any one of them. For dsRNase-3: the original BLAST tiling produced three disjoint alignment intervals; the Ensembl comparison leaves the assignment of the full published dsRNase-3 CDS to a single gene indeterminate. This is the locus attribution the family audit declared outside its own scope.

**Question 2 remains open.** The single locus detected in the primary assembly is a result for the published dsRNase-2 CDS. The genomic origin of `GITV01012450.1` and whether the two TSA records share a locus remain unresolved.

A collapsed duplication remains possible. The run lacks read depth evidence over the locus, and the search of the alternate assembly yielded no locus under the applied parameters.

The inferred gene structures — 6, 7 and 5 exons, with introns from 293 nt to 5,125 nt — are consistent with insect gene structure and with the coding-region integrity and PF01223 classification the family audit established. They remain `inferred/interpreted`: they come from the gaps of an HSP tiling, and the offset search found a candidate `GT..AG` motif at fewer than half of their inferred junctions inside the declared window. This run's own declared genomic targets were the two assembly FASTAs; no GFF3 was a declared input and none was consulted. A later round on this branch retrieved and checked an Ensembl AEGIS gene annotation for the primary assembly against the three loci's inferred structure, reported in the addendum below. Agreement with an independent annotation strengthens the inferred structure for dsRNase-1 and dsRNase-2; it does not convert a tiled BLAST block into an observed splice junction, which is still only a `GT..AG` candidate within the declared window, never a confirmed one.

Nothing here bears on enzymatic activity, substrate specificity, expression, or any phenotype, and no such claim is made.

## Clean-clone reconstruction

The reconstruction instructions are to be verified by executing them, not by inspection. The procedure, against a fresh `git clone` of this branch into a directory holding no external inputs, is:

1. confirm the checkout contains `data/reference/target_anchor_sequences.fasta` and no `data/external` at all, and record whether the anchor FASTA arrived with LF or CRLF line endings;
2. run the mapping with the inputs absent: it must **refuse**, exit 2, and name the declared download URL of the missing input rather than produce a partial result;
3. run the two `curl` commands exactly as the panel declares them, and check both declared `sha256` values with `sha256sum`;
4. run `pytest tests/test_nb01_locus.py -q` in the clone;
5. run the mapping end to end and compare the sha256 of every output table with this run's.

### Observed outcome

Executed against commit **`f00b87d5f1a52d0a0402a96c136d5b4dd79dea2e`**, the implementation commit of this branch, cloned with `git clone --branch feat/nb01-dsrnase-locus-mapping --single-branch` into an empty directory. This section is recorded in the follow-up commit, because a record of a verification cannot sit inside the commit whose verification it reports.

1. The clone carried `data/reference/target_anchor_sequences.fasta` and **no `data/external` directory at all**. The anchor FASTA checked out with **LF** line endings, so its raw sha256 and its LF-normalised sha256 are both `10cd666816d76fd4a87ae769849008551a40ddfde4081722d33f73e54cbea89b`. The implementation worktree, on Windows, holds the same file with CRLF and a different raw hash. Verification by the LF-normalised hash accepts both, which is the whole reason that mode is used.
2. With the inputs absent the mapping **refused**, exited **2**, and printed the missing input with its declared download URL:
   `declared input is missing: ihDalMaid1.1_primary -> data/external/nb01_locus_mapping/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz` / `download it from: https://ftp.ncbi.nlm.nih.gov/...`. It produced `queries.tsv` and an empty `raw/` before refusing, because the queries are derived and checked before any assembly is opened, and **no** locus, assignment, distinctness, copy-number or manifest output. No search ran.
3. The two `curl` commands, copied verbatim from the panel, reproduced both assemblies at their exact declared byte counts, and `sha256sum` reproduced both declared hashes: `aef4d8ec...9184` and `90e6c6ab...1757`.
4. `pytest tests/test_nb01_locus.py -q` in the clone: **50 passed**.
5. The mapping ran end to end, exit 0, and reproduced this run **byte for byte**. All five output tables have the same sha256 as the run recorded above:

   | output | sha256 |
   | --- | --- |
   | `queries.tsv` | `c851b92484c1cf93581771c885f8ec8a22d85f8ce424325b39edd72d0c277964` |
   | `loci.tsv` | `57b0d68ce3d0460c832f15ab24bd8ab1214dd90e3dc63807140d62ed6ff172e4` |
   | `assignments.tsv` | `dae544940fdd73454109b2e5f66824f5640eba08eda53a70bbbc59123401bc8d` |
   | `distinctness.tsv` | `f66d6445a225e21f339a8fda977e23f46a9cff4567f22de82d0925a433b6e457` |
   | `copy_number.tsv` | `7dadd5d912d5081e280001246c982930f9f3ad3ecf0b9a51f2dbc907e58fa77b` |

   The BLAST counts matched as well: 57 HSPs on one subject for the primary, 0 for the alternate, and the same three loci, three assignments and three distinctness verdicts.

The clean clone also settles Anomalies item 4: in an ordinary checkout the manifest's `git` block is **populated** — `{"commit": "f00b87d5f1a52d0a0402a96c136d5b4dd79dea2e", "status_porcelain": ""}` — confirming that the empty block in the implementation worktree is an artefact of the cross-OS worktree and not of the module. `manifest.json` is not compared by hash because it legitimately differs between runs: it records the timestamp, the commit and the temporary paths of that run.

## Addendum (2026-11-15): comparison against the Ensembl AEGIS gene annotation

Added on the same branch, after the implementation above and after the `f00b87d` / clean-clone commits. No `blastn` search is re-run here and the historical result is not altered: every number in the Results section above, and the description of each locus as a chain of local BLAST blocks tiled over an interval rather than a single end-to-end alignment, stands as recorded. This addendum reads the already-recorded `loci.tsv` and the raw HSP table (`raw/blastn_ihDalMaid1.1_primary.outfmt6.tsv`) of that same run and compares them against a gene annotation that the original execution did not consult: that run's declared genomic targets were the two assembly FASTAs, blastn was run against them, and the GFF3 below was never a declared input. This addendum is the first time this repository checks it.

**The annotation.** The Ensembl AEGIS project (`projects.ensembl.org/aegis`) has published an Ensembl Genebuild gene annotation for `GCA_975739785.1`, geneset version `2026_02`:

- GFF3: `https://ftp.ebi.ac.uk/pub/ensemblorganisms/GCA/975/739/785/1/ensembl/2026_02/geneset/genes.gff3.gz`
- `sha256` of the downloaded file: `2606dd4fbb71b9555c643656656bb2f2aad82a072422236df57eaed483cb411d`
- `md5`: `f14acda9ad871e8b07fdfdc55f076846`, agreeing with the `md5sum.txt` published alongside the file on the same FTP path
- The genome and geneset files under that FTP path carry an mtime of 2026-05-01; `md5sum.txt` carries 2026-09-11. A file's mtime on a mirror is not a reliable proxy for when an annotation was first made public, so no claim is made here about whether this annotation existed before or after 2026-11-15, the date of the original execution. What is documented, because it is this repository's own history, is simpler: the original execution (`f00b87d`) declared and used the two assembly FASTAs as its genomic targets and did not consult any GFF3; this GFF3 was first retrieved and checked by this repository in this later round, on this branch.
- No RefSeq (`GCF_`) annotation exists for this assembly; this is an independent Ensembl Genebuild computational annotation, not an NCBI RefSeq annotation, and not an experimentally validated one.
- No equivalent annotation was used in this comparison for the alternate haplotype, `GCA_975739835.1`; the comparison below is therefore primary-assembly-only, same as the original mapping's assignment result. Whether an Ensembl AEGIS annotation exists for that haplotype was not checked here, and no claim is made about it either way.

**Chromosome 1 correspondence.** The GFF3 numbers chromosomes `1`-`9` and `X` rather than using INSDC accessions. The identity of GFF3 seqid `1` with this run's `OZ319704.1` is established four ways, all agreeing on the same length, 122,877,750 nt:

1. The GFF3 declares it directly: `##sequence-region 1 1 122877750` and a `region` feature `ID=region:1;Alias=OZ319704.1`.
2. NCBI's own `sequence_reports` for `GCA_975739785.1` gives `chr_name: "1"`, `genbank_accession: "OZ319704.1"`, `length: 122877750`.
3. Ensembl AEGIS's own `genome/chromosomes.tsv.gz` for this geneset lists `1  122877750`.
4. This matches `OZ319704.1`'s `sequence_length` column in `loci.tsv`, unchanged since the original run.

**The comparator.** `scripts/compare_nb01_locus_to_ensembl_aegis.py`, committed at `e1befb9069818e16d691ada54e04403327d9cee0` on this branch, with its tests in `tests/test_compare_nb01_locus_to_ensembl_aegis.py` (15 tests, passing at that commit). It verifies the declared `sha256` of `loci.tsv` and of the downloaded GFF3 before running and refuses on a mismatch. Reproduce with, from the repository root in the canonical environment:

```bash
python scripts/compare_nb01_locus_to_ensembl_aegis.py
```

Output tables are written to `results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/ensembl_aegis_comparison_v3/` (git-ignored), separate from this run's own `loci.tsv` and the other original outputs, which that script does not read as writable and does not modify.

**What the comparator checks, and what it does not.** It compares genomic *boundary coordinates*: does an NB01-inferred exon block's start and end match a GFF3 CDS segment's start and end, within a stated tolerance. It does not check nucleotide sequence identity between the two, which is a separate question answered below by direct extraction and comparison, not by the comparator.

**dsRNase-1 and dsRNase-2: the annotation corroborates both loci.** Under the comparator's exploratory 20 nt tolerance, both are `gene_support_status=DETERMINED` and `structural_match_status=FULL`: all 6 (dsRNase-1) and all 7 (dsRNase-2) NB01-inferred blocks pair one-to-one, in order, with the CDS segments of one Ensembl transcript (`ENSCHMT00000004227` and `ENSCHMT00000006229`, both the Ensembl-canonical isoform of their gene), with combined per-segment boundary differences of at most 6 nt (dsRNase-1) and 8 nt (dsRNase-2) — inside the ±10 nt per-edge ambiguity window ADR 0009 rule 7 already declared, and consistent with the junction-overlap offsets that window exists for.

Boundary agreement and sequence identity are different claims, and are kept distinct here. Under the comparator's *exact* (0 nt) tolerance, dsRNase-1 has 3 of 6 blocks with both boundaries byte-identical to the annotation and dsRNase-2 has **none** of its 7 — `gene_support_status=NO_PAIRS_MATCHED` for dsRNase-2 at that tolerance. Despite that, reconstructing each Ensembl transcript's spliced CDS directly from the primary assembly (concatenating its annotated CDS segments in genomic order, extracted with `blastdbcmd` from a locally rebuilt database, no search involved) and comparing it byte-for-byte against the published CDS in `raw/cds_queries.fna` gives:

| target | reconstructed length | published length | identical | mismatches | sha256 match |
| --- | --- | --- | --- | --- | --- |
| dsRNase-1 (`ENSCHMT00000004227`, 6 exons) | 1,323 nt | 1,323 nt | no | 1 (position 840, `G`→`A`; 99.92 % identity) | no |
| dsRNase-2 (`ENSCHMT00000006229`, 7 exons) | 1,425 nt | 1,425 nt | **yes** | 0 | **yes** (`bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7`, both sides) |

For dsRNase-2, the full spliced Ensembl CDS is identical to the published CDS even though no single tiled BLAST block had both boundaries exactly equal to the annotation's exon boundaries: the small per-exon boundary offsets this run already reported as alignment ambiguity (junction overlaps, ADR 0009 rule 7) cancel out when the exons are reconstructed and concatenated, because the ambiguous bases are present in both flanking blocks and are not actually missing or substituted. For dsRNase-1 the reconstructed sequence is one nucleotide away from the published CDS; this does not contradict the locus or exon-structure findings above, and is recorded here as the more precise of the two claims this run can now make about dsRNase-1, in place of the coarser "99.850 % aggregate block identity" already on record, which counts every doubly-covered junction position twice.

**dsRNase-3: single-gene attribution is `INDETERMINATE`, with a chimera hypothesis.** The comparator's best explanation differs by tolerance, and which transcript wins is itself part of the finding: under the *exact* (0 nt) comparison only 1 of the 5 inferred blocks matches any CDS segment at all, so the best available model is `ENSCHMT00000004222` (`ube2w`), `gene_support_status=INDETERMINATE_PARTIAL_COVERAGE`; under the *exploratory* (20 nt) tolerance the best model switches to `ENSCHMT00000005294` (`ENSCHMG00000003138`), covering 3 of the 5 blocks at a combined cost of 7 nt — a different gene, still only partial coverage. Neither tolerance, and no available transcript at either, accounts for the whole CDS. Reading the raw HSP table for the individual blocks resolves why, directly from the *already-recorded* BLAST output (no re-run):

- Query blocks 1–102, 99–458 and 457–643 (100.000 % identity, 0 mismatches each, per the recorded HSPs) land, within the same few-nt junction overlap already documented for this locus in the Results section, on the first three coding segments of `ENSCHMT00000005294` (the Ensembl-canonical transcript of `ENSCHMG00000003138`), whose own lengths are 100, 356 and 186 nt. None of these three blocks has both boundaries byte-identical to its segment, which is why the exact-tolerance comparison credits none of them.
- Query block 639–872 (234 nt, 99.573 % identity, 1 mismatch, per the recorded HSP) is an intermediate HSP: its genomic span, 122,012,475–122,012,708, partially overlaps the second coding segment of `ube2w`'s canonical transcript, `ENSCHMT00000004222` (122,012,544–122,012,706), but its own boundary sits roughly 69 nt outside that segment's boundary at the 5′ end — well outside the declared matching tolerance at either setting, so the comparator credits this block to no segment under either tolerance.
- Query block 871–1236 (366 nt, 98.907 % identity, **4 mismatches**, 0 gaps, per the recorded HSP) matches, boundary-for-boundary, the third and final coding segment of that same `ube2w` transcript (122,014,117–122,014,482; Ensembl's Genebuild names the gene `ube2w`, ubiquitin conjugating enzyme E2 W, by an NN prediction at 83.39 % score — a computational functional label, not experimentally confirmed).

These three query ranges are not three disjoint pieces that partition the 1,236 nt CDS: 1–643, 639–872 and 871–1236 overlap each other at their edges by a few nucleotides, the same kind of junction overlap recorded for most, though not every, junction in this run (dsRNase-1's first junction, by contrast, has zero overlap; see the Results section), and sum to 1,243 nt counted separately. No such partition is claimed. What the raw HSPs show is narrower: the published Dmai-dsRNase-3 CDS has a clean, high-identity correspondence to three real coding exons of one annotated gene at one end, a clean, high-identity correspondence to the last real coding exon of a second, unrelated annotated gene at the other end, and an intermediate HSP in between whose boundaries do not fall inside either gene's annotated CDS at the declared tolerance. **Recorded as a hypothesis, not a conclusion:** the published Dmai-dsRNase-3 transcript (`TRINITY_DN5008_c0_g1_i24`) may be a transcriptomic chimera — a Trinity assembly joining sequence from two unrelated genomic loci into one apparent transcript — rather than the mRNA of a single real gene. This comparison does not establish that hypothesis; it only shows that single-gene attribution for the full published CDS remains indeterminate under the Ensembl comparison, by the comparator's own gene-support and structural-match criteria (`scripts/compare_nb01_locus_to_ensembl_aegis.py`, committed at `e1befb9069818e16d691ada54e04403327d9cee0`), which evaluate correspondence per annotated transcript. This is a separate test from ADR 0009 rule 6, which classifies BLAST clusters into genomic loci, not annotated transcripts into genes. Confirming or refuting the chimera hypothesis is outside this addendum's scope: it would need the original Trinity assembly graph for `TRINITY_DN5008_c0_g1_i24`, RNA-seq read support spanning the query 639–872 region, or an independent transcript assembly, none of which this run or this addendum has.

The original BLAST tiling produced three disjoint alignment intervals. The Ensembl comparison leaves the assignment of the full published dsRNase-3 CDS to a single gene indeterminate. The three loci's genomic spans remain three disjoint, colinear intervals on chromosome 1, megabases apart, exactly as recorded above and in the Interpretation section; nothing in this addendum relocates any span or merges any two of them. What changes is narrower: whether the *published CDS*, as a whole, is the product of one gene. For dsRNase-3 it is not determinable from this comparison, and a specific, falsifiable mechanism — a chimeric transcript assembly — is recorded above as a hypothesis, one candidate explanation among others that have not been examined, not as the established or sole account.

## Addendum 2 (2026-11-16): splice-aware alignment of the three published CDS

A second, independent check on the same question, added after the addendum above. **The original BLAST execution is untouched and remains the record of this run:** every coordinate, count and verdict in the Results, Interpretation and Anomalies sections stands as written, no `blastn` search was re-run, and nothing here replaces the HSP tiling of ADR 0009 rules 4 and 7. What this adds is a different method applied to some of the same inputs — a splice-aware aligner, which assigns each junction a single pair of coordinates instead of leaving it inside the ambiguity window that the tiling's negative junction offsets represent.

**The check and the aligner.** [`scripts/check_nb01_dsrnase_splicing.py`](../../../../scripts/check_nb01_dsrnase_splicing.py), committed at **`7e5f748459f730fcdf512175c4d8a48dc5418cbf`** on this branch with its tests in `tests/test_check_nb01_dsrnase_splicing.py` (41 tests, passing at that commit). Aligner **minimap2 2.31-r1302**, pinned as `minimap2=2.31` in `environment.yml`, with the parameters:

```
-a -x splice:hq -uf --eqx --cs=long -G 50k -p 0.8 -N 5
```

The 50 kb intron limit keeps the scale of the historical clustering (`MAX_INTRON_NT` = 50,000 nt) and admits the candidate transition discussed below. `--eqx` puts `=`/`X` in the CIGAR, so substitutions are read from the alignment itself rather than inferred. `-p 0.8 -N 5` retains up to five secondary alignments as alternatives; **none was emitted** for any of the three queries.

**Declared inputs, verified by `sha256` before the check runs.** The check refuses on any mismatch. Two of the four are material the original BLAST execution also used; the other two enter only in the comparison that follows the alignment, and never reach the aligner:

| input | role in this check | `sha256` | relation to the original BLAST execution |
| --- | --- | --- | --- |
| `results/.../dsrnase_locus_mapping/raw/cds_queries.fna` | query | `7e378f84688253a78fbaa0aa631b536e94bcccca9d2a0433eb44bad7dd214bf2` | **shared**: written by that run and used as its `blastn` query |
| `data/external/nb01_locus_mapping/GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz` | alignment target | `aef4d8ec0891bece052bc58afa5b0da3e2a2bf047f9283032bbf253459509184` | **shared**: the same declared primary mapping target |
| `data/external/nb01_locus_mapping/GCA_975739785.1_ensembl_2026_02_genes.gff3.gz` | post-alignment comparison only | `2606dd4fbb71b9555c643656656bb2f2aad82a072422236df57eaed483cb411d` | not used by it; this is the annotation of the first addendum |
| `results/.../dsrnase_locus_mapping/loci.tsv` | post-alignment comparison only | `57b0d68ce3d0460c832f15ab24bd8ab1214dd90e3dc63807140d62ed6ff172e4` | not an input to it; it is that run's own output, read here only to reconcile junctions |

The queries are the same three published CDS the original run derived; nothing was re-derived here.

**The decompressed assembly is verified only on the path that runs the aligner.** The two paths read the assembly differently, and only one of them produces a decompressed file to hash.

- **Reanalysis**, the path these tables come from, never expands the assembly. It reads the compressed FASTA **as a stream**, decompressing on the fly and keeping only the sequences the SAM actually refers to — here `OZ319704.1` alone — which is how the genomic dinucleotides at each assigned junction and the sequence of each block are obtained. No temporary FASTA is written, so there is no decompressed file to hash: the manifest records `genome_decompressed_sha256: null`.
- **Alignment** additionally expands the `.gz` into a temporary uncompressed FASTA, because minimap2 needs a file to index, and checks that expansion against the already-declared `54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04` before calling the aligner. The expansion and its hash check exist to serve the aligner and belong to that path alone; the temporary file is deleted when the run ends.

Both paths verify the compressed `.gz` by its own declared `sha256` before using it for alignment or reanalysis, and both take their genomic sequence from that same compressed file by streaming. The decompressed hash quoted here was therefore verified on the alignment run that produced the SAM, not on the reanalysis that produced these tables.

**The GFF3 was used only after the alignment.** It is never passed to minimap2: the alignment is annotation-free, and the annotation enters afterwards, to compare junction coordinates and to name the models. The manifest records this as `annotation_used_after_alignment_only`. The same applies to `loci.tsv`, which is read only to reconcile the new junctions against the historical ones.

**The saved alignment, and the reanalysis these numbers come from.** The alignment was run once and its SAM preserved in full, with every record emitted, at `results/.../splice_check_v1/raw/minimap2_splice_hq.sam`:

- `sha256` `41b1bf583b132feb101b4155b5f901647e65450b3921a3fe85ef3c0078a773fc`
- `sha256` of the same file excluding its `@PG` line: `786097c3d3aec1e40644923e819ca7e4ad4cfb43d91994b9ce5c90300e42e5df`

The whole-file hash is **run-dependent**, because minimap2 writes the command line into `@PG` and that line carries the temporary path of the decompressed genome; the `@PG`-excluded hash does not depend on that path. The tables reported here were produced by **re-analysing that saved SAM**, not by a fresh alignment — the check reads the aligner version from the SAM's own `@PG` line and refuses if it is not 2.31-r1302.

The command that produced the tables reported here, recorded as the historical command and kept for provenance rather than for re-execution:

```bash
python scripts/check_nb01_dsrnase_splicing.py --root . --sam results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/splice_check_v1/raw/minimap2_splice_hq.sam --out-subdir results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/splice_check_v4_reanalysis
```

Re-running it verbatim is **refused**, by design: the check claims its output directory exclusively and will not write into one that already holds results. To reproduce the tables from the same SAM, give it a destination that does not yet exist:

```bash
python scripts/check_nb01_dsrnase_splicing.py --root . --sam results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/splice_check_v1/raw/minimap2_splice_hq.sam --out-subdir results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/splice_check_v5_reanalysis
```

The outputs of the historical command are in `results/.../dsrnase_locus_mapping/splice_check_v4_reanalysis/` (git-ignored), and the reference manifest for the numbers below is that directory's `manifest.json`, `sha256` **`3eddf06a565e5bc8562f0919712fba9b3e6f226cb16235d271fbdc60149aa51a`**, which records `mode: reanalysis_of_saved_alignment`, the source SAM with both hashes above, and `produced_in_this_run: false`. Earlier output directories of this check are kept as they were and are not overwritten.

**What was compared, and what that does and does not support.** A full alignment run was executed into a separate, temporary destination and its seven TSVs came back byte-identical to those of the reanalysis of the saved SAM. That supports one claim: the tables reported here do not depend on whether the SAM is read from disk or produced in the same process. It does **not** establish that a new alignment emits a SAM whose records are all identical to the saved one — the TSVs carry the fields this check derives, not every field of every record, so equality of the tables cannot stand in for equality of the alignment output. No such comparison of two independently produced SAMs is recorded here.

**All three queries align as a single primary record.** Three SAM records, all primary, all on `OZ319704.1`, all on the plus strand, all at MAPQ 60, with no secondary and no supplementary record, no clipping and no indel anywhere:

| CDS | span on `OZ319704.1` | blocks | junctions | query nt aligned to the genome | `NM` | substitutions at query position |
| --- | --- | --- | --- | --- | --- | --- |
| dsRNase-1 | 60,966,751-60,973,368 | 6 | 5 | 1,323 / 1,323 | 1 | 840 |
| dsRNase-2 | 69,024,822-69,037,412 | 7 | 6 | 1,425 / 1,425 | 0 | none |
| dsRNase-3 | 122,005,058-122,014,482 | 5 | 4 | 1,236 / 1,236 | 5 | 756; 1,059; 1,073; 1,078; 1,167 |

The three spans are the same intervals the BLAST tiling reported, to the nucleotide. At all **15** assigned junctions the genomic dinucleotides read a canonical `GT..AG` in the transcript's orientation. Each assigned intron equals the corresponding historical intron widened by exactly the query overlap that junction already carried, at all 15 (`junction_vs_historical.tsv`): the negative junction offsets this run recorded were alignment ambiguity, as stated, and the aligner replaces each ambiguous edge with one chosen coordinate.

**Controls.** dsRNase-1 and dsRNase-2 are not in question here, and both recover their expected locus and their annotated junctions. The check reports a control as `AS_EXPECTED` only when every declared requirement holds — primary record, full coverage, no clipping, no indels, the expected sequence, strand and genomic interval, the expected junction count, the expected nucleotide differences at the expected positions, and the expected transcript lying on the alignment's own strand — and names any requirement that fails:

| control | junctions matching the expected transcript | expected transcript | nucleotide differences | verdict |
| --- | --- | --- | --- | --- |
| dsRNase-1 | **5 / 5** | `ENSCHMT00000004227` (strand `+`) | 1, at query position 840 | `AS_EXPECTED` |
| dsRNase-2 | **6 / 6** | `ENSCHMT00000006229` (strand `+`) | 0 | `AS_EXPECTED` |

Every junction of both controls coincides *exactly*, on both edges, with an annotated intron of the expected transcript. This is the independent corroboration the addendum above could not give from boundary comparison alone, and it reproduces that addendum's reconstruction result for dsRNase-1 at the same query position, 840.

**dsRNase-3: one chain covers the whole published CDS and crosses both annotated gene regions.** A single primary record accounts for all 1,236 nt, contiguously — its five blocks tile query 1-1,236 with no gap, no overlap and no indel — while its alignment blocks overlap annotated CDS segments from **two different genes**:

| block | query | genomic | substitutions | overlap with annotated CDS |
| --- | --- | --- | --- | --- |
| 1 | 1-100 | 122,005,058-122,005,157 | 0 | within `ENSCHMG00000003138` |
| 2 | 101-456 | 122,005,565-122,005,920 | 0 | within `ENSCHMG00000003138` |
| 3 | 457-642 | 122,007,163-122,007,348 | 0 | within `ENSCHMG00000003138` |
| 4 | 643-870 | 122,012,479-122,012,706 | 1 | **partial** overlap with `ube2w` (`ENSCHMG00000002609`) |
| 5 | 871-1,236 | 122,014,117-122,014,482 | 4 | within `ube2w` (`ENSCHMG00000002609`) |

**Block 4 overlaps the annotated `ube2w` CDS only in part.** Of its 228 nt, the first **65 nt** — query 643-707, genomic 122,012,479-122,012,543 — fall inside an intron of the model `ENSCHMT00000004222`, which the annotation does not place in any coding segment. The remaining **163 nt** — query 708-870, genomic 122,012,544-122,012,706 — coincide with that model's annotated CDS segment. The block is therefore not contained in the annotated CDS; it begins 65 nt upstream of it.

Three of the four junctions coincide exactly with annotated introns — the first two with `ENSCHMT00000005294` and `ENSCHMT00000005281` of `ENSCHMG00000003138`, the last with `ENSCHMT00000004222` of `ube2w`. Throughout this addendum a junction means **the coordinates the aligner assigned** to a gap between two aligned blocks, under the parameters above; it is not an observed splice event, and a coincidence with an annotated intron is agreement between two computational calls, not confirmation that the intron is spliced there. The check's labels record this as `CHAIN_SPANS_BOTH_ANNOTATED_GENES` = `OBSERVED` and `CHAIN_MATCHES_SINGLE_ANNOTATED_MODEL` = `NOT_OBSERVED`; `COVERAGE_ONLY_BY_SEPARATE_ALIGNMENTS` is `NOT_OBSERVED`, because one record covers the CDS on its own rather than the coverage being assembled from separate alignments.

**The transition, between query nucleotides 642 and 643.** The remaining junction is the one that leads from the `ENSCHMG00000003138` region into the `ube2w` region:

| | |
| --- | --- |
| genomic gap, as assigned by the aligner | 122,007,349-122,012,478 |
| jump | **5,130 nt** |
| query positions | between **642** and **643** |
| coding phase | 0 — the junction falls on a codon boundary, the chain stays in frame |
| motif at the assigned coordinates | `GT..AG`, canonical |
| annotated intron at the same coordinates | **none** |

It sits at the position the BLAST tiling already pointed to, after query 642, and its length is the historical 5,125 nt widened by the 5 nt overlap that junction carried — the same reconciliation that holds for all 15 junctions.

**No annotated transcript has an intron with both of these boundaries**, checked across all 6,523 transcripts annotated on `OZ319704.1`. The two edges behave differently, and the difference is worth stating precisely:

- On the **donor** side there is a coincidence of boundaries: 122,007,348, the last base before the assigned gap, is the same coordinate at which annotated exon 4 of `ENSCHMT00000005294` ends (122,007,163-122,007,348). The two calls agree on that edge. They do not agree on what follows it: that transcript's own next exon starts at 122,007,664, so the intron the annotation places at that donor is 315 nt, where the aligner assigned 5,130.
- On the **acceptor** side there is no such coincidence: no annotated exon starts at 122,012,479. `ube2w`'s nearest annotated CDS segment begins at 122,012,544, **65 nt downstream**, which is the same 65 nt by which block 4 precedes the annotated segment.

So the assigned gap shares its donor coordinate with an annotated exon boundary while its acceptor coordinate matches none. The nearest annotated intron by combined edge distance is `ENSCHMT00000004222`'s, at −4,715 nt and −65 nt.

**What this settles, and what it does not.** What is on record is a **chain of splice-aware alignment covering all 1,236 nt of the query**: one primary record, five blocks tiling the query contiguously and in frame, four assigned junctions, each carrying a canonical `GT..AG` at the coordinates assigned. Concatenating the genomic sequence of those five blocks gives a sequence of **1,236 nt, the same length as the published CDS, differing from it by five substitutions** at query positions 756, 1,059, 1,073, 1,078 and 1,167. The concatenation is therefore not the published sequence, and no claim is made here that the assembly contains, or could yield, that sequence exactly. This is a statement about coordinates and about sequence read from the assembly, not about any transcript.

**The biological origin of the full published transcript remains `INDETERMINATE`.** An alignment chain is not transcript evidence: a canonical motif marks coordinates at which a donor-acceptor pair could sit, the junction that carries the whole chain is annotated in neither gene, and its acceptor coordinate matches no annotated boundary. The transcriptomic-chimera hypothesis recorded in the addendum above **remains a hypothesis** and is neither confirmed nor refuted here; what this check adds is that a single alignment chain spans both regions, which was not established before, and it removes none of the alternatives. Settling it needs RNA evidence spanning the 642/643 transition — RNA-seq reads crossing that junction, the original Trinity assembly graph for `TRINITY_DN5008_c0_g1_i24`, or an independent transcript assembly — none of which this run, the addendum above or this addendum has.

## Addendum 3 (2026-11-16): the two dsRNase-2 TSA records mapped separately, one query per accession

A third check on the question this run left open, added after the two addenda above. **Nothing of the original BLAST execution or of either addendum is modified:** no historical artifact was rewritten, the published-CDS mapping of the three dsRNases stands exactly as recorded, and this addendum reports a separate execution with its own panel, its own destination and its own outputs. What it adds is the one thing the original run could not do: it queries `GITV01008430.1` and `GITV01012450.1` as **two separate CDS** instead of one, so that the two records are distinguishable inputs rather than a single query standing for both.

**Why a separate run was needed.** The operational reference records CDS of 1,425 nt with **distinct** `sha256` for the two records — `bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7` and `8c18687410248fb6036020cc50fc7577d23c7c44b9d0f30cc0677b95b28960f8` — differing at seven positions: six IUPAC symbols (9, 30, 219, 312, 350, 1,272) and one defined substitution at 816. The original run queried the published CDS, which `GITV01008430.1` reproduces exactly, so its outputs cannot say which record came from which locus. They are not asked to: that is a limitation of the query, not of the tiling.

**The code and the two executions.** [`scripts/map_nb01_dsrnase2_by_accession.py`](../../../../scripts/map_nb01_dsrnase2_by_accession.py) with its panel [`data/reference/nb01_dsrnase2_accession_panel.json`](../../../../data/reference/nb01_dsrnase2_accession_panel.json) and its tests in `tests/test_map_nb01_dsrnase2_by_accession.py` (45 tests, passing on the content that was committed). Search parameters, locus formation, tiling, the 50 % reporting tier and the one-locus assignment rule of rule 6 come unchanged from ADR 0009 via `zeaguard.nb01_locus`; this run adds no threshold of its own and keeps BLAST's conventional identity as a column of its own. BLAST+ **2.17.0+** (`blastn`, `makeblastdb`, `blast_formatter`; Package: blast 2.17.0, build Aug 22 2026), Python 3.12.14, conda env `zeaguard` — the declared canonical environment, unchanged.

Two executions are on record, and they are not interchangeable:

| run | destination | what it is |
| --- | --- | --- |
| **v1** | `results/.../dsrnase2_by_accession_v1` | the **initial execution**, run from the reviewed working tree before the commit |
| **v2** | `results/.../dsrnase2_by_accession_v2_committed` | a **re-execution of `8a7d34c401fcdba7406976e89bd1cac16f6fa21e`**, the commit that carries the script, the panel and the tests |

**The historical command of v1.** v2 ran the same command with `--out results/bioinformatics/nb01/mappings/dsrnase2_by_accession_v2_committed`:

```
python scripts/map_nb01_dsrnase2_by_accession.py --root . \
  --panel data/reference/nb01_dsrnase2_accession_panel.json \
  --out results/bioinformatics/nb01/mappings/dsrnase2_by_accession_v1
```

Reproducing it takes a destination of its own, for example:

```
python scripts/map_nb01_dsrnase2_by_accession.py --root . \
  --panel data/reference/nb01_dsrnase2_accession_panel.json \
  --out results/bioinformatics/nb01/mappings/dsrnase2_by_accession_v3_repro
```

Neither recorded destination can be reused. The script claims its output directory exclusively and atomically, holds the claim until its last write, and refuses a directory that already holds files, so both `dsrnase2_by_accession_v1` and `dsrnase2_by_accession_v2_committed` are refused as they stand. That is what preserves them.

**Three separate things are documented here, and none of them makes v1 a run of the commit:** v1 ran before the commit existed.

- **The panel hash documents the panel v1 used.** v1's manifest records the panel it verified as `a403ed7cfacbc32341b68f5b3f077188fb4af17432dc03d15ba2bacaa840a6b2`, which is also the `sha256` of the panel blob at `8a7d34c4`: the declared input of that execution is byte-for-byte the panel the commit carries.
- **The file-to-blob comparison documents the content checked at the time of the commit.** Immediately after committing, the three working-tree files were compared against their committed blobs — `d5c2cd90…` for the script, `a7c5bb20…` for the tests, `a403ed7c…` for the panel, with the direct and LF-normalised hashes agreeing, so no line-ending normalisation is involved. That states what the tree held when the commit was made.
- **v2 demonstrates reproduction with the committed version.** It ran after the commit, from a clean tree, into a destination of its own, and its outputs are the comparison reported below.

**The two manifests, and what their comparison covers.** `results/.../dsrnase2_by_accession_v1/manifest.json` and `results/.../dsrnase2_by_accession_v2_committed/manifest.json`. Each records the verified `sha256` of both panels, the TSA archive and both assemblies (compressed and decompressed), the eight executed commands with return code and UTC start, `flank_in_scope: false`, the seven informative positions, the discriminating position, and the `sha256` of each of the six tables. Removing the `commands` block, **the two manifests hash identically**: `1d03376f060f4aeb290f8b0e747c14919560032c9931a0b514e3b39ad220362e`. The `commands` block is the only part that differs, in the three ways a second run must differ: the temporary directory of each BLAST database, the destination path embedded in the `-query`, `-out` and `-archive` arguments, and the timestamps. Both runs report eight commands, all with return code 0.

**Artifacts compared, and how.** The six tables were compared with `cmp`, byte for byte, not by hash alone:

| artifact | v1 vs v2 | `sha256` |
| --- | --- | --- |
| `queries.tsv` | identical | `8e5294f33adcafe21aad8b5da15fa097bc6afaafa3b6fa41ad4932f889b86ef2` |
| `candidates.tsv` | identical | `e895eb6c15fa6d8c3bac3c18931e0809013fa8d716204abb3fccc52658ff9e89` |
| `informative_positions.tsv` | identical | `760babd676c1737d2facb4fe596dd664c39728c94c3aa081c42e938701a39601` |
| `informative_observations.tsv` | identical | `961835fd05956dcb9d07c38a8b27eaf01e8610554f06dc46eac9f975e90275ea` |
| `assignments.tsv` | identical | `411e8a8ab7d57e11cf575aff7c5b8d1fa74266c4d286d6081b7cfa4bc06bb5a5` |
| `accession_pair.tsv` | identical | `4767a63d56991a270315119aa01755f5b98eaf6c53db5fc399029eaabc388eaa` |

Among the raw artifacts, the query FASTA and both `blastn` tabular outputs are byte-identical as well. The two BLAST archives are not, and the difference was located rather than assumed: in each `.asn` the only divergent line is `subject database`, which carries the temporary directory name of the database built for that run. No alignment record differs. The declared inputs are the TSA archive `22d0cff8d0867344a76d615bdca62c31ce0f9133f574058e8daa6b6e41925ae6`, copied into this worktree at the panel's declared relative path and re-verified by that hash on both runs, and the two assemblies already declared by `nb01_dsrnase_locus_panel.json`, which this panel references by path and verifies rather than redeclaring.

**Primary assembly: one eligible candidate per query, on the same chain.** Under ADR 0009 rule 6 each query has exactly one eligible locus, so each is `DETERMINED` with `ONE_LOCUS_MEETS_ASSIGNMENT_CRITERIA`:

| query | HSPs | candidates reported | eligible | locus | coverage | identity (BLAST) |
| --- | --: | --: | --: | --- | --: | --: |
| `GITV01008430.1` | 7 | 1 | 1 | `OZ319704.1:69,024,822-69,037,412` (+) | 100.0 % | 99.931 % |
| `GITV01012450.1` | 7 | 1 | 1 | `OZ319704.1:69,024,822-69,037,412` (+) | 100.0 % | 99.448 % |

The two candidates are not merely the same span: the **chain of seven blocks is identical**, block for block, in the same query order and colinear on the plus strand — `69,024,822-69,024,887`, `69,027,182-69,027,302`, `69,029,828-69,030,111`, `69,031,687-69,031,897`, `69,033,087-69,033,320`, `69,034,815-69,035,103`, `69,037,168-69,037,412`. The span equals the locus the original run recorded for the published dsRNase-2 CDS, which is the expected agreement, not a new result.

**Position 816, read from the alignment.** Both calls come from the same HSP (`q667-900:s69,033,087-69,033,320`, plus strand), covered by one HSP each, and were checked directly against the genomic FASTA at the coordinate the alignment assigns:

| query | base in the query | genomic coordinate | genomic base | verdict | BTOP operation |
| --- | --- | --- | --- | --- | --- |
| `GITV01008430.1` | `C` | `OZ319704.1:69,033,236` | `C` | `EXACT` | `=` |
| `GITV01012450.1` | `T` | `OZ319704.1:69,033,236` | `C` | `DEFINED_MISMATCH` | `X` |

**The assembly carries `C` at 816**, which is the base of the operational record and diverges from the `T` of `GITV01012450.1`. The **six IUPAC positions of the second record are compatible with the assembly**: at 9, 30, 219, 312, 350 and 1,272 the genomic bases are `C`, `C`, `T`, `A`, `G` and `T`, each inside the expansion of the symbol the record carries (`Y`, `Y`, `Y`, `R`, `R`, `Y`), and each is recorded as `AMBIGUITY_COMPATIBLE` — compatibility with an ambiguous symbol, never promoted to exact agreement. All fourteen calls (seven positions on each of the two eligible candidates) were re-read independently from the decompressed coordinates of `GCA_975739785.1`, recomputing the verdict from the FASTA: **14/14 agree in coordinate, strand and verdict**. Every HSP of this run is on the plus strand, so the reverse-strand path of that audit was exercised only by the synthetic tests, not by data here.

**What the alignment favours, and what stays open.** In the primary assembly the two queries each have one eligible locus and their chains are concordant and colinear on the same strand, so `accession_pair.tsv` records `alignment_status = DETERMINED` with `alignment_reason = FAVOURS_SHARED_LOCUS_IN_THIS_ASSEMBLY`. That is a statement about **mapped intervals in this assembly**, which is what an alignment can settle.

**The biological origin of the two records remains `INDETERMINATE`**, with the reason recorded as `SHARED_INTERVAL_CANNOT_ASSIGN_RECORDS`: one interval cannot say which record came from it. The base at 816 does not change this. It tells which record the assembly matches at that position — the operational one — and it is equally consistent with two records from one locus, one of them carrying a sequencing or assembly difference at 816 and six unresolved positions, and with two records from two loci of which this assembly contains or resolved only one. Nothing in these outputs distinguishes those. The run therefore keeps geometry, per-query eligibility, the evidence at 816 and the origin in separate column groups, so that a geometric coincidence is never read as an attribution.

**Alternate assembly: zero HSPs for both queries.** `blastn` returned **0 HSPs** for each of the two queries against `GCA_975739835.1`, so both are `INDETERMINATE` with `NO_HSPS` — the output separates absence of HSPs from HSPs that produce no eligible candidate, and this is the first case. Three artifacts carry it: the tabular output is empty (0 lines, 0 bytes, `sha256 e3b0c442…`, the hash of the empty file), the pairwise report says `***** No hits found *****` for both queries, and the database log records the whole assembly indexed, 7,864 sequences and 488,450,451 letters, with the declared statistics of that input verified before the search. This reproduces, per accession, what the original run found for all three published CDS. **The comparison between haplotypes remains inconclusive**, for the same reason as in the original run: **no locus was detected under the applied search parameters**, so the alternate assembly offers nothing to compare against. Zero HSPs for each query is the result on record; it is not evidence that the locus is absent from that haplotype.

**The two identities, and position 64.** The identities above are BLAST's conventional metric over the tiled HSPs, and both are explained by one column. `GITV01008430.1` has a single mismatch (99.931 % over 1,450 aligned nt, overlaps included), and `GITV01012450.1` has eight (99.448 %): the same one, plus its six IUPAC positions and the defined substitution at 816. The shared mismatch is at **CDS position 64**, where both records carry `G`.

Position 64 falls in the **overlap of two HSPs**, which the tiling of ADR 0009 rule 7 permits and which every junction of this run already carries. The two HSPs assign it different coordinates and read different bases there:

- HSP `q1-66` places it at **69,024,885**, where the assembly reads **`A`** — a mismatch. `63GA2` is the BTOP of **`GITV01008430.1`** on that HSP and records exactly that: 63 matches, then query `G` against subject `A`, then two more matches. **`GITV01012450.1`** has the same interval with BTOP `8YC20YC33GA2`: its ambiguous symbols at 9 and 30, 33 further matches, then the same `GA` column at 64 and two more matches. **Both records carry the mismatch at 64**, which is why the single shared column appears in both identity figures.
- HSP `q59-179` places it at **69,027,187**, where the assembly reads **`G`** — a match, inside a 121 nt HSP whose BTOP is `121` for both records, with no mismatch at all.

**Minimap2 uses the second coordinate.** In the splice-aware alignment of Addendum 2, the dsRNase-2 control's block 0 ends at query 61 / 69,024,882 and block 1 begins at query 62 / 69,027,185, so query 64 lands at 69,027,187 — the matching copy. The junction between them is the intron `69,024,883-69,027,184` (2,302 nt), canonical `GT..AG`, and an **exact coordinate match to the annotated intron of `ENSCHMT00000006229`** at both edges. The reconstruction of that aligner's segments coincides integrally with the published CDS: 7 blocks, 1,425 of 1,425 nt aligned, `n_mismatch_nt` 0 in every block, `NM` 0, no insertion, no deletion, no clipping, and the control verdict `AS_EXPECTED` with 6/6 junctions matching the expected transcript.

**So the mismatch BLAST counts comes from the edge of the tiling, not from a difference between the published sequence and the assembly.** HSP `q1-66` runs five nucleotides past the donor at 69,024,883 into that annotated intron, whose first bases read `GTAAA` where the coding sequence continues `GTGAA`; position 64 is the one of those five at which the two disagree. The exonic copy of the position is `G` in the assembly and `G` in both records. This is the same artefact the original run already recorded for the splice-site check — BLAST extending an HSP a few nucleotides past the exon into the intron, visible in the negative junction offsets — appearing here in an identity figure rather than in a junction motif. Both identities are reported as BLAST computed them, and are not corrected for it.

## What this run does NOT establish

- It does not establish that any locus call is correct, that either assembly is correct, or that the inferred exon/intron structures are the true gene structures. The offset search found a candidate `GT..AG` motif at fewer than half of the inferred junctions within the declared window, and a candidate motif is not a confirmed splice boundary. This run's own declared inputs did not include a GFF3; the addendum above checks, for the first time in this repository, an Ensembl AEGIS annotation of the primary assembly against them, which corroborates the boundary structure of dsRNase-1 and dsRNase-2 but does not turn a candidate `GT..AG` motif into a confirmed splice junction, and finds dsRNase-3's full CDS does not correspond to a single annotated gene.
- It does not establish or refute the transcriptomic-chimera hypothesis the addendum records for dsRNase-3. That hypothesis is a candidate explanation, not a finding of this run or of the addendum.
- The genomic origin of `GITV01012450.1` and its relationship to the locus detected for the published CDS remain `unresolved`. The third addendum above narrows what is open without closing it: queried on its own, that record's CDS aligns to the same locus as the operational record, over the same chain of seven blocks and at full coverage, which is a result about mapped intervals in the primary assembly. Which record came from which locus is not settled by one shared interval, and the base the assembly carries at the discriminating position does not settle it either.
- A duplication collapsed by the assembler remains possible. The run lacks read depth evidence over the locus.
- The comparison between haplotypes remains inconclusive because the search detected no locus in `GCA_975739835.1` under the applied parameters.
- It does not establish gene identity, orthology, paralogy, gene family size, or copy number in the species. Both declared assemblies come from one individual (`SAMEA117578701`); population-level copy-number variation is outside the run.
- It does not establish that each locus is a complete gene: the query is the CDS, so UTRs, promoters and any additional exons outside the coding region were never searched for.
- It does not establish anything about enzymatic activity, substrate specificity, expression, regulation, or any phenotype.
- It does not re-derive or validate the published ORF coordinates; it checks that its own derivation reproduces them.
- Successful execution does not demonstrate scientific validity, and computational reproducibility does not establish scientific validity.

## Anomalies / deviations

1. **The alternate assembly search yielded no locus for comparison.** `blastn` returned 0 HSPs for all three published CDS against `GCA_975739835.1` under the parameters applied. The Results section records the controls and the inconclusive comparison between haplotypes.

2. **The splice-site check was wrong in the first implementation and was corrected before the recorded run.** It read the two nucleotides straight off the HSP boundary and reported a canonical `GT..AG` at 1, 0 and 0 inferred junctions for the three loci. That was an artefact: BLAST extends an HSP a few nucleotides past the exon into the intron, which is visible in the negative junction offsets, so the termini at the alignment edge are the wrong two nucleotides. Reporting them would have been evidence against a structure the data do not argue against. The check now reports the termini at the boundary *and* the smallest shift within the declared +/-10 nt window at which the intron reads `GT..AG`, which raised the inferred junctions carrying a candidate `GT..AG` motif to 2, 3 and 2. The window was fixed in ADR 0009 before any alignment and was **not** widened after seeing which shifts were found.

3. **The primary assembly's sequence count does not match NCBI's, for a traceable reason.** The file carries 141 records and 972,225,736 nt; the NCBI Datasets report says 140 scaffolds and 972,206,121 nt. The difference is exactly one record, `OZ319714.1` (`organelle: mitochondrion`, 19,615 nt): 972,225,736 - 972,206,121 = 19,615. NCBI's scaffold count and lengths describe the nuclear assembly only. The panel declares the statistics **of the file** and records NCBI's alongside with this reconciliation; the mitochondrion is left in the search space, because removing a sequence from a declared input would make its hash unverifiable, and is classified under a role of its own so a count including it always reconciles. No dsRNase CDS has an HSP on it. NCBI's `number_of_contigs` and `contig_n50` describe pre-scaffolding components that a FASTA of scaffolds does not contain, so neither is declared or checked.

4. **`manifest.json` recorded an empty `git` block in the implementation worktree.** `_git` returned `""` for both the commit and the porcelain status. The cause is not the module: the worktree was created by Windows git, so its `.git` file holds the absolute path `C:/Programming/Python/zeaguard-drylab/.git/worktrees/...`, which the Linux git inside WSL resolves relative to the working directory and fails on. `_git` does not raise on a failed git call, so the field came back empty rather than aborting the run. **Confirmed by the clean clone**, where the same code records `{"commit": "f00b87d5f1a52d0a0402a96c136d5b4dd79dea2e", "status_porcelain": ""}`: the module is not at fault, the cross-OS worktree is. The commits are recorded in this file instead. Worth noting for review: a provenance manifest whose commit field can silently come back empty is a weakness of the shared `_git` helper, which is used by other NB01 modules as well; it is left unchanged here because it is outside this branch's scope, and is listed as a follow-up rather than fixed in passing.

5. **Building the BLAST database on the working tree did not finish in 13 minutes.** On a 9p-mounted Windows working tree under WSL, `makeblastdb` on the 972 Mb assembly had produced no output after 13 minutes and was abandoned; on native Linux disk it completes in about 7 seconds. The module now puts the expansion and the database in a temporary directory, which is both the correct place for a derived intermediate and the fast one. Anyone reproducing this with the repository on a Windows filesystem should keep `TMPDIR` on a native filesystem.

6. **`decisions/README.md` was missing ADR 0008 from its PTBR index.** The English index listed eight records, the PTBR index seven. Appending 0009 to both would have left the PTBR list skipping from 0007 to 0009, so the missing 0008 entry was added in the same edit. This is a documentation-index correction, not a change to ADR 0008.

7. **The branch was cut from `origin/master`, not from the local `master`.** The local `master` of the originating checkout was two commits behind (missing the merge of PR #22, which carries ADR 0008). Cutting from it would have produced an ADR numbered 0009 in a tree where 0008 did not exist. The base commit is `08079cd`.

8. **`git worktree add` set the new branch's upstream to `origin/master`.** Left as created, a bare `git push` from this branch would have targeted `master`, which CONTRIBUTING.md §7 prohibits. The upstream was unset immediately after creation, before any commit.

No deviation from the declared canonical environment: conda env `zeaguard`, BLAST+ 2.17.0 for all three executables, Python 3.12.14.

## Related decisions

[ADR 0009](../decisions/0009-nb01-dsrnase-locus-assignment-criteria.md) (`Proposed`) records the mapping criteria, which were set before alignment. The run reused the discovery parameters and 50 % reporting threshold from [ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md). [ADR 0003](../decisions/0003-nb01-target-identity-resolution-policy.md) records the earlier target identity policy.

Preceding run records: [2026-10-03 dsRNase-2 identity](2026-10-03_nb01-dsrnase2-identity.md), and the dsRNase protein audit of 2026-11-13 (`2026-11-13_nb01-dsrnase-protein-audit.md`, on the unpublished branch `feat/nb01-dsrnase-protein-audit`, hence unlinked), whose open questions this run addresses.

## Related Issue / PR / commits

Branch `feat/nb01-dsrnase-locus-mapping`, cut from `origin/master` at `08079cd`. `f00b87d` carries the implementation, the panel, ADR 0009 and this record; the commit that follows adds this record's clean-clone outcome, which could not be written before the verification it reports; `e1befb9069818e16d691ada54e04403327d9cee0` adds `scripts/compare_nb01_locus_to_ensembl_aegis.py` and its tests, the comparator the first addendum above reports on; `7e5f748459f730fcdf512175c4d8a48dc5418cbf` adds `scripts/check_nb01_dsrnase_splicing.py` and its tests, the splice-aware check the second addendum reports on, together with the `minimap2=2.31` pin it requires; `8a7d34c401fcdba7406976e89bd1cac16f6fa21e` adds `scripts/map_nb01_dsrnase2_by_accession.py`, its panel and its tests, the per-accession mapping the third addendum reports on.

Not pushed and no pull request opened: publication and merge are the repository owner's decisions (CONTRIBUTING.md §2 and §9).

## Evidence classification

1. `directly demonstrated`: the existence, versioned accessions and declared properties of the three *D. maidis* assemblies; the absence of any RefSeq assembly for the species, at the time of this run and since; the hash and statistic agreement of every declared input; the agreement between the derived and published ORF coordinates; the BLAST counts, including 0 HSPs against the alternate haplotype; the positive control's self-match at 100 % over 3,000 nt and the sensitivity sweep; the reconciliation of the 141st record as the mitochondrion; the test results; the clean-clone reconstruction. Added by the addendum: the existence, URL, `sha256` and `md5` of the Ensembl AEGIS GFF3 for the primary assembly; the four-way chromosome 1 / `OZ319704.1` correspondence; the raw BLAST HSP identity and mismatch counts for every dsRNase-3 query segment discussed in the addendum (0, 0, 0, 1 and 4 mismatches respectively); the genomic location of the dsRNase-3 query's middle 234 nt block, 122,012,475–122,012,708, per the recorded HSP; the byte-for-byte identity, with matching `sha256`, between the reconstructed Ensembl dsRNase-2 CDS and the published CDS; the single mismatch (position 840) between the reconstructed Ensembl dsRNase-1 CDS and the published CDS. Added by the second addendum: the minimap2 2.31-r1302 alignment records themselves, preserved in the saved SAM — for each query the single primary record, its span, its block and junction coordinates, its canonical `GT..AG` motifs, its `NM` and the query positions of its substitutions; that no annotated transcript on `OZ319704.1` carries an intron with both boundaries of the 122,007,349-122,012,478 junction, that an annotated exon of `ENSCHMT00000005294` ends at 122,007,348, and that no annotated exon starts at 122,012,479. Added by the third addendum: the per-accession BLAST counts, 7 HSPs for each of the two queries against the primary assembly and 0 for each against the alternate; the bases the primary assembly carries at the seven informative positions of the dsRNase-2 locus, re-read from the assembly at the coordinates the alignment assigns, with 14 of 14 calls agreeing in coordinate, strand and verdict; the `C` at `OZ319704.1:69,033,236`, the coordinate assigned to CDS position 816; the two coordinates 69,024,885 and 69,027,187 that the overlapping HSPs `q1-66` and `q59-179` assign to CDS position 64 and the `A` and `G` the assembly carries there; the minimap2 block boundaries that place position 64 at 69,027,187 and the dsRNase-2 control's 1,425 of 1,425 nt aligned with `NM` 0; the byte-for-byte identity of the six tables between the two executions and the equality of the two manifests outside their `commands` block.
2. `derived/computed`: the three CDS queries; every locus coordinate, span, coverage, identity, colinearity, assembly-gap content and distance to sequence end; the pairwise distinctness verdicts and the gaps between spans; the per-assembly locus counts. Added by the addendum: the comparator's `gene_support_status` and `structural_match_status` for each locus and tolerance mode, and the per-block correspondence of the dsRNase-3 CDS's five query blocks to coding segments of the two annotated genes (not a partition of the CDS: the blocks overlap each other, as every junction in this run already does). Added by the third addendum: the per-accession locus coordinates, block chains, coverage and conventional BLAST identity (99.931 % and 99.448 %); the geometric concordance of the two chains — same sequence, same span, same strand, same blocks in the same query order, colinear on both sides; and the classification of each informative position as `EXACT`, `AMBIGUITY_COMPATIBLE` or `DEFINED_MISMATCH`, read from the BTOP of the HSP that covers it.
3. `inferred/interpreted`: the exon/intron structures and intron sizes, read from the gaps of an HSP tiling rather than from an annotation or a splice-aware alignment; the inferred junctions at which the offset search found a candidate `GT..AG` motif, which depend on the declared ambiguity window and are not confirmed splice boundaries; that one detected locus per CDS means one genomic copy, which is conditional on the assembly not having collapsed a duplication. Added by the addendum, and explicitly a hypothesis rather than a finding: that the published Dmai-dsRNase-3 TSA transcript is a transcriptomic chimera of two unrelated genomic loci. Added by the third addendum: that the alignment favours one shared locus for the two dsRNase-2 records in the primary assembly, which is a reading of concordant geometry and not an attribution of the records; and that the single mismatch behind the 99.931 % identity is an artefact of the tiling edge rather than a difference between the published sequence and the assembly, which follows from the exonic copy of position 64 and the annotated intron boundary, not from the identity figure itself.
4. `unresolved`: the genomic origin of `GITV01012450.1` and whether the two dsRNase-2 TSA records share a locus; concordance between haplotypes; whether a duplication was collapsed by the genome assembler; copy number in the species and any population-level variation; the true splice boundaries of the eight junctions without a canonical pair inside the declared window; the complete gene structure outside the coding region; enzymatic activity, specificity, expression and any phenotype for all three proteins. Added by the addendum: single-gene attribution for the full dsRNase-3 CDS; confirmation or refutation of the transcriptomic-chimera hypothesis; whether the dsRNase-3 query's middle 234 nt block (located at 122,012,475–122,012,708, directly demonstrated above) is part of one continuous transcript together with the flanking blocks, or evidence of a chimeric assembly instead. Added by the second addendum, and unchanged by it: the biological origin of the full published dsRNase-3 transcript. What that addendum records is a splice-aware alignment chain covering all 1,236 nt of the query, whose five concatenated genomic blocks give a sequence of the same length as the published CDS differing from it by five substitutions; whether any transcript is actually spliced across the 642/643 transition is not addressed by a canonical motif at coordinates whose acceptor matches no annotated boundary, and needs RNA evidence spanning that junction. Added by the third addendum, and unchanged by it: the biological origin of the two dsRNase-2 TSA records. Querying them separately settles that their CDS map to one interval in the primary assembly over an identical chain, and that the assembly reads `C` at the discriminating position, matching the operational record; neither assigns the records to loci. One locus carrying a difference at 816 and six unresolved positions, and two loci of which this assembly contains or resolved only one, remain equally consistent with these outputs, and the alternate haplotype contributes nothing to the choice because it yields no HSP for either query.
