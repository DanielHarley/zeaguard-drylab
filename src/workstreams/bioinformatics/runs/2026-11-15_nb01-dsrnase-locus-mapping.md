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

Completed means the mapping ran end to end from the declared inputs in an empty output directory, every integrity check it performs passed, and every question it was given received either an answer or an explicit `INDETERMINATE` with a reason. It does **not** mean the locus calls are correct, that the inferred exon/intron structures are the true gene structures, or that anything was established about enzymatic activity. The copy-number cross-check the method planned to make against the alternate haplotype **could not be made**; see Results and Anomalies item 1.

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

**No RefSeq (`GCF_`) assembly and no gene annotation exists for any of the three.** No locus call in this run can therefore be checked against an independent gene model.

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
6. **decide distinctness** pairwise, and **report copy number** under a neutral key.

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
- **Controls for the alternate-haplotype result**, run because "no hits" is the one result that an empty or broken database also produces. All three are recorded in Results; in short: the database is sound, and the absence is real.
- **Internal consistency of the tiling.** For each locus the total block-column count exceeds the CDS length by exactly the total query overlap at the junctions: 11 = 11, 25 = 25, 13 = 13 for dsRNase-1, -2 and -3. With the union query coverage at 100 % and no positive offset anywhere, this means each tiling accounts for the whole CDS — counted once except at the tolerated overlaps, where those positions are counted twice — and nothing outside it. So the aggregate identity is computed over alignment columns that all belong to the CDS, with the overlap fully quantified rather than unknown. Asserted as an invariant in the tests as well.
- **Clean-clone reconstruction, executed against the delivered commit `f00b87d`.** The reconstruction commands reproduce both declared hashes, the mapping refuses with exit 2 while the inputs are absent, 50 tests pass in the clone, and all five output tables come back byte-identical to the run recorded here. Full outcome in the dedicated section below.

## Results

### Question 1 — dsRNase-3 occupies a locus of its own: answered, `DETERMINED`

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

### Question 2 — the two TSA records of dsRNase-2: one locus detected, with a stated residual

Part of this question cannot be answered by sequence mapping, and that was stated before the run. `GITV01008430.1` and `GITV01012450.1` reproduce **the same** 1425 nt CDS (ADR 0004), so one query stands for both and no alignment can say which record came from which locus. That part remains `unresolved` by construction.

What the mapping does answer is the genomic copy number of that CDS:

| assembly | loci at assignment criteria | related loci | key |
| --- | --- | --- | --- |
| `ihDalMaid1.1_primary` | **1** | 0 | `ONE_LOCUS_DETECTED` |
| `ihDalMaid1.1_alternate` | 0 | 0 | `NO_LOCUS_DETECTED` |

In the chromosome-level assembly the dsRNase-2 CDS is found at exactly one genomic location, with every one of its 1,425 coding positions covered by the union of the tiled alignment blocks and an aggregate identity of 99.931 % over those blocks' 1,450 columns (25 query positions counted twice, at the six overlapping junctions), and with no second place in the genome reaching even half coverage. Two distinct loci would require two genomic copies, and none was detected.

### The alternate haplotype gave no cross-check, and the controls say why

ADR 0009 rule 10 declared the alternate pseudohaplotype as the one copy-number cross-check available without read depth. **It did not apply.** `blastn` returned **0 HSPs** for all three CDS against `GCA_975739835.1`, so all three are `INDETERMINATE / NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA` there and all three pairs are `INDETERMINATE / UNASSIGNED_LOCUS`.

Since "no hits" is also what an empty or broken database produces, three controls were run before reading anything into it:

1. **Positive control.** A 3,000 nt slice taken from an alternate-haplotype scaffold (`CDKMJQ010000001.1`), searched against the database built from that same assembly, finds itself at 100.000 % identity over 3,000 nt, e-value 0.0, bit score 5,411, and returns 33,739 HSPs in total. The database and the search work.
2. **Sensitivity sweep.** The same three CDS against the same database: 0 HSPs at e-value 1e-5, 9 at 1, 55 at 10, 3,781 at 1,000; 0 with `dc-megablast` at e-value 10. At e-value 1,000 the best hits are 23 to 53 nt fragments with bit scores 39 to 43 — noise-length matches, nothing resembling an exon of a 1.2 to 1.4 kb CDS.
3. **Calibration on the primary.** The same sweep against `GCA_975739785.1` gives 57 HSPs at 1e-5 (the 18 tiled exons plus their lower-scoring alternatives) and 187 at e-value 10 spread over all ten chromosomes, confirming that the declared 1e-5 cutoff is what isolates the real loci from relaxed-threshold noise.

So the three loci are genuinely **not represented** in the alternate pseudohaplotype. That is a property of that assembly — an alternate pseudohaplotype carries only the regions where the assembler resolved two haplotypes, here 488 Mb against the primary's 972 Mb — and not a search failure. It is reported as the absence of a cross-check, not as evidence of absence in the genome.

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

**Question 1 is answered.** Dmai-dsRNase-3 occupies its own locus, distinct from those of dsRNase-1 and dsRNase-2. The three published CDS correspond to three separate genomic locations on chromosome 1 of `GCA_975739785.1` — three colinear, mutually disjoint intervals separated by 8.1, 53.0 and 61.0 Mb. For each, the union of its tiled alignment blocks covers every coding position of its CDS, the aggregate identity over those blocks' columns is 99.6 % or better, the span is gap-free sequence inside an assembled chromosome, and it is the only place in the assembly where that CDS reaches half coverage. The three are a gene family dispersed along one chromosome, not alleles or assembly duplicates of one another. This is the locus attribution the family audit declared outside its own scope.

The distinctness rests on the three intervals being disjoint and megabases apart, which is a statement about genomic position and is unaffected by how the within-locus coverage and identity are aggregated. The inferred exon boundaries inside each interval are a separate, weaker claim and are not what the answer to question 1 depends on.

**Question 2 is answered in one direction only.** The dsRNase-2 CDS has one detected genomic locus, so the two TSA records attributed to it are consistent with one locus represented twice in the transcriptome assembly, and are not consistent with two distinct paralogous loci. Combined with ADR 0004's finding that both records carry a byte-identical CDS, the reading that the two records are redundant representations of one gene is the one the evidence supports; two paralogues would have to be identical over all 1,425 coding nucleotides *and* collapsed into one place by the genome assembly.

That residual is real and is not dismissed. A recent duplication can be collapsed by an assembler, and this run has no read-depth evidence over the locus. The cross-check that was meant to reduce that possibility, the alternate haplotype, returned nothing usable. So the honest statement is: **one locus detected; a collapsed duplication is not excluded.** Nor can the mapping say which record came from which locus — with one CDS behind both, that stays `unresolved` whatever the genome shows.

The allele hypothesis named in the original question can be addressed more sharply, and it is addressed by ADR 0004 rather than by this run: two alleles of one locus differing in CDS would give two different CDS, and the two records carry the same one. Two identical alleles are indistinguishable from one sequence by any sequence method.

The inferred gene structures — 6, 7 and 5 exons, with introns from 293 nt to 5,125 nt — are consistent with insect gene structure and with three paralogues that have diverged in intron content while keeping coding-region integrity and the PF01223 classification the family audit established. They remain `inferred/interpreted`: they come from the gaps of an HSP tiling, the offset search found a candidate `GT..AG` motif at fewer than half of their inferred junctions inside the declared window, and neither assembly carries an annotation to check them against.

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

## What this run does NOT establish

- It does not establish that any locus call is correct, that either assembly is correct, or that the inferred exon/intron structures are the true gene structures. The offset search found a candidate `GT..AG` motif at fewer than half of the inferred junctions within the declared window, a candidate motif is not a confirmed splice boundary, and no annotation exists to check any of them against.
- It does not establish which of `GITV01008430.1` and `GITV01012450.1` came from which genomic locus. One identical CDS stands for both records, so this is `unresolved` by construction, not for want of data.
- It does not exclude a duplication collapsed by the genome assembler. That would require read-depth evidence over the locus, which this run does not have, and the alternate-haplotype cross-check returned nothing usable.
- It does not establish that the three loci are absent from the alternate pseudohaplotype **of the genome**; it establishes that they are absent from that assembly, which represents about half of it.
- It does not establish gene identity, orthology, paralogy, gene family size, or copy number in the species. Both declared assemblies come from one individual (`SAMEA117578701`); population-level copy-number variation is outside the run.
- It does not establish that each locus is a complete gene: the query is the CDS, so UTRs, promoters and any additional exons outside the coding region were never searched for.
- It does not establish anything about enzymatic activity, substrate specificity, expression, regulation, or any phenotype.
- It does not re-derive or validate the published ORF coordinates; it checks that its own derivation reproduces them.
- Successful execution does not demonstrate scientific validity, and computational reproducibility does not establish scientific validity.

## Anomalies / deviations

1. **The declared alternate-haplotype cross-check did not apply.** ADR 0009 rule 10 declared it as the one available copy-number cross-check; `blastn` returned 0 HSPs for all three CDS against it. This is recorded as a deviation rather than quietly dropped, because the ADR committed to a check that the data could not supply. Three controls (Results) establish that the database and the search are sound and that the absence is a property of the assembly. The rule itself is not amended: it is correct as written, and it simply did not fire here.

2. **The splice-site check was wrong in the first implementation and was corrected before the recorded run.** It read the two nucleotides straight off the HSP boundary and reported a canonical `GT..AG` at 1, 0 and 0 inferred junctions for the three loci. That was an artefact: BLAST extends an HSP a few nucleotides past the exon into the intron, which is visible in the negative junction offsets, so the termini at the alignment edge are the wrong two nucleotides. Reporting them would have been evidence against a structure the data do not argue against. The check now reports the termini at the boundary *and* the smallest shift within the declared +/-10 nt window at which the intron reads `GT..AG`, which raised the inferred junctions carrying a candidate `GT..AG` motif to 2, 3 and 2. The window was fixed in ADR 0009 before any alignment and was **not** widened after seeing which shifts were found.

3. **The primary assembly's sequence count does not match NCBI's, for a traceable reason.** The file carries 141 records and 972,225,736 nt; the NCBI Datasets report says 140 scaffolds and 972,206,121 nt. The difference is exactly one record, `OZ319714.1` (`organelle: mitochondrion`, 19,615 nt): 972,225,736 - 972,206,121 = 19,615. NCBI's scaffold count and lengths describe the nuclear assembly only. The panel declares the statistics **of the file** and records NCBI's alongside with this reconciliation; the mitochondrion is left in the search space, because removing a sequence from a declared input would make its hash unverifiable, and is classified under a role of its own so a count including it always reconciles. No dsRNase CDS has an HSP on it. NCBI's `number_of_contigs` and `contig_n50` describe pre-scaffolding components that a FASTA of scaffolds does not contain, so neither is declared or checked.

4. **`manifest.json` recorded an empty `git` block in the implementation worktree.** `_git` returned `""` for both the commit and the porcelain status. The cause is not the module: the worktree was created by Windows git, so its `.git` file holds the absolute path `C:/Programming/Python/zeaguard-drylab/.git/worktrees/...`, which the Linux git inside WSL resolves relative to the working directory and fails on. `_git` does not raise on a failed git call, so the field came back empty rather than aborting the run. **Confirmed by the clean clone**, where the same code records `{"commit": "f00b87d5f1a52d0a0402a96c136d5b4dd79dea2e", "status_porcelain": ""}`: the module is not at fault, the cross-OS worktree is. The commits are recorded in this file instead. Worth noting for review: a provenance manifest whose commit field can silently come back empty is a weakness of the shared `_git` helper, which is used by other NB01 modules as well; it is left unchanged here because it is outside this branch's scope, and is listed as a follow-up rather than fixed in passing.

5. **Building the BLAST database on the working tree did not finish in 13 minutes.** On a 9p-mounted Windows working tree under WSL, `makeblastdb` on the 972 Mb assembly had produced no output after 13 minutes and was abandoned; on native Linux disk it completes in about 7 seconds. The module now puts the expansion and the database in a temporary directory, which is both the correct place for a derived intermediate and the fast one. Anyone reproducing this with the repository on a Windows filesystem should keep `TMPDIR` on a native filesystem.

6. **`decisions/README.md` was missing ADR 0008 from its PTBR index.** The English index listed eight records, the PTBR index seven. Appending 0009 to both would have left the PTBR list skipping from 0007 to 0009, so the missing 0008 entry was added in the same edit. This is a documentation-index correction, not a change to ADR 0008.

7. **The branch was cut from `origin/master`, not from the local `master`.** The local `master` of the originating checkout was two commits behind (missing the merge of PR #22, which carries ADR 0008). Cutting from it would have produced an ADR numbered 0009 in a tree where 0008 did not exist. The base commit is `08079cd`.

8. **`git worktree add` set the new branch's upstream to `origin/master`.** Left as created, a bare `git push` from this branch would have targeted `master`, which CONTRIBUTING.md §7 prohibits. The upstream was unset immediately after creation, before any commit.

No deviation from the declared canonical environment: conda env `zeaguard`, BLAST+ 2.17.0 for all three executables, Python 3.12.14.

## Related decisions

[ADR 0009](../decisions/0009-nb01-dsrnase-locus-assignment-criteria.md) (`Proposed`), written before any alignment was run, carries the criteria this run applies. It depends on, and does not modify, [ADR 0004](../decisions/0004-nb01-dsrnase2-identity-criteria.md) (the identical CDS behind the two dsRNase-2 records, and the discovery parameters and 50 % coverage threshold reused here) and [ADR 0003](../decisions/0003-nb01-target-identity-resolution-policy.md).

Preceding run records: [2026-10-03 dsRNase-2 identity](2026-10-03_nb01-dsrnase2-identity.md), and the dsRNase protein audit of 2026-11-13 (`2026-11-13_nb01-dsrnase-protein-audit.md`, on the unpublished branch `feat/nb01-dsrnase-protein-audit`, hence unlinked), whose open questions this run addresses.

## Related Issue / PR / commits

Branch `feat/nb01-dsrnase-locus-mapping`, cut from `origin/master` at `08079cd`. Two commits: `f00b87d` carries the implementation, the panel, ADR 0009 and this record; the commit that follows adds this record's clean-clone outcome, which could not be written before the verification it reports.

Not pushed and no pull request opened: publication and merge are the repository owner's decisions (CONTRIBUTING.md §2 and §9).

## Evidence classification

1. `directly demonstrated`: the existence, versioned accessions and declared properties of the three *D. maidis* assemblies; the absence of any RefSeq assembly or gene annotation for the species; the hash and statistic agreement of every declared input; the agreement between the derived and published ORF coordinates; the BLAST counts, including 0 HSPs against the alternate haplotype; the positive control's self-match at 100 % over 3,000 nt and the sensitivity sweep; the reconciliation of the 141st record as the mitochondrion; the test results; the clean-clone reconstruction.
2. `derived/computed`: the three CDS queries; every locus coordinate, span, coverage, identity, colinearity, assembly-gap content and distance to sequence end; the pairwise distinctness verdicts and the gaps between spans; the per-assembly locus counts.
3. `inferred/interpreted`: the exon/intron structures and intron sizes, read from the gaps of an HSP tiling rather than from an annotation or a splice-aware alignment; the inferred junctions at which the offset search found a candidate `GT..AG` motif, which depend on the declared ambiguity window and are not confirmed splice boundaries; that one detected locus per CDS means one genomic copy, which is conditional on the assembly not having collapsed a duplication; that the two dsRNase-2 TSA records are redundant representations of one gene; that the three loci being absent from the alternate pseudohaplotype reflects that assembly's partial coverage of the genome.
4. `unresolved`: which TSA record came from which genomic locus; whether a duplication was collapsed by the genome assembler; copy number in the species and any population-level variation; the true splice boundaries of the eight junctions without a canonical pair inside the declared window; the complete gene structure outside the coding region; enzymatic activity, specificity, expression and any phenotype for all three proteins.
