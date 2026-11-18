# Run ID

`2026-11-18_nb01-dsrnase3-transcript-evidence-pilot`

## Date

2026-11-18

## Commit

Implementation and execution: `4c842fcd47c49fa81b857e3f2a99b3eea7344d03`, recorded in the
manifest of every output of this run, each of which also records
`status_porcelain` empty.

Preceding commits of the same branch: `75192192eb203f35822ccbf570799d4a1952f567` added the
command, `e65d86da32a0719303dd125f9bb0d41758629ae1` corrected the informative-coverage rule
and the mate-bridge requirement, `48d563af9b21714c576c1a071d7fe1289cd18ac7` corrected the
support rule to per-read coverage of each anchor footprint, and `4c842fcd` bound the pilot's
hashes to the files the aligner opens. The pilot was executed on `4c842fcd` only; no result
below comes from an earlier version.

## Branch

`feat/nb01-dsrnase3-transcript-evidence`, cut from `43b0ff75881775b96a48be048da6fd8d9fe52d37`
of `feat/nb01-dsrnase-locus-mapping`.

## Execution status

`EXECUTED`. Four real RNA-seq libraries processed one at a time, each with its own
alignment, its own declared panel of one, its own output directory and its own verdict. No
count in this record is summed across libraries.

## Question / objective

Does RNA-seq evidence support the junction the splice-aware alignment assigns between
positions 642 and 643 of the published Dmai-dsRNase-3 CDS — the gap
`OZ319704.1:122,007,349-122,012,478` (5,130 nt) that leads out of the `ENSCHMG00000003138`
region into the `ube2w` region, and that no annotated transcript carries with both
boundaries?

This run asks that of four public libraries. It does not ask, and cannot answer, which reads
assembled the published contig `TRINITY_DN5008_c0_g1_i24`, nor whether the full 1,236 nt CDS
belongs to one molecule.

## Indexing convention

Every coordinate here is **1-based and inclusive**, on the forward strand of the named
reference sequence, for both CDS and genomic positions. An intron is named by its own first
and last base, so the junction in question is `122,007,349-122,012,478`: the last aligned
base before it is 122,007,348 and the first aligned base after it is 122,012,479.

## Inputs

### Reference

| | |
| --- | --- |
| assembly | `GCA_975739785.1` (`ihDalMaid1.1`), primary assembly |
| file | `GCA_975739785.1_ihDalMaid1.1_genomic.fna.gz` |
| `sha256` compressed | `aef4d8ec0891bece052bc58afa5b0da3e2a2bf047f9283032bbf253459509184` |
| `sha256` decompressed | `54411d6ee12a6c3f290428c08d3a046fb4e27bec83b9a75e9f42b866fc5d8a04` |
| sequence | `OZ319704.1`, **122,877,750 nt**, declared in `REFERENCE` and required of every panel |

Both assembly hashes are the values already declared by the NB01 locus mapping and by the
splice-aware check, and both were reproduced here before the index was built. The sequence
length agrees with the 2026-11-15 run record, which states `OZ319704.1` at 122,877,750 nt.

### Index

Built once by the first command of the declared recipe and reused by all four libraries,
with its provenance recorded in `index_build.json` and re-verified before each library:

```
hisat2-build -p 20 <assembly>.fna ihDalMaid1.1
```

Eight `.ht2` files, each with its byte count and `sha256` in the record. All eight were
recomputed after the run and match.

### Libraries

Four runs of BioProject **PRJNA631706**, chosen as the largest by spot count in each of the
four catalogued conditions. All are `origin_class: comparative`; see
[the candidate catalogue](../../../../data/reference/nb01_dsrnase3_comparative_library_candidates.json)
for why none is `confirmed_origin`.

| run | condition | spots per mate | bases per mate | mate 1 `sha256` | mate 2 `sha256` |
| --- | --- | --- | --- | --- | --- |
| `SRR11822340` | naive, 4 h | 22,519,390 | 2,251,939,000 | `b6931210…b5a17` | `514286da…74af8` |
| `SRR11822336` | MRFV exposed, 4 h | 25,686,310 | 2,568,631,000 | `079568db…89403` | `dcf41c6b…db154` |
| `SRR11822345` | naive, 7 days | 24,240,856 | 2,424,085,600 | `c60778e0…fd497` | `ecae7ed1…69650` |
| `SRR11822341` | MRFV exposed, 7 days | 23,039,932 | 2,303,993,200 | `e8ff4fe6…148c91` | `f01eaf59…7ec17` |

For each library the two mates carry the **same** spot count, and twice the per-mate base
count reproduces the `base_count` the ENA catalogue declares for that run. The spot counts
also reproduce the catalogue's `read_count` exactly, and `fasterq-dump` reported the same
figure for each.

Every `sha256` above is of the file **at the path the aligner opened**, under the library's
working directory, not of a catalogue copy. The full values are in `pilot_report.json`.

### How the reads were obtained, and a deviation from the catalogue's URL

The catalogue records ENA FASTQ URLs and their md5. ENA's HTTP mirror delivered about
0.45 MB/s from here, against about 8 MB/s from the NCBI SRA Open Data bucket, so the reads
were taken from the latter as `.sra` and converted locally. The verification chain therefore
differs from the catalogue's and is stated in full:

1. the `.sra` was resumed until its size equalled the bucket's `Content-Length`;
2. its `sha256` was recorded (`SRR11822340`: 3,101,541,872 bytes,
   `bba990c0bff8eb4c5cca60c14a7d109eac394e9b223a3b27087fcdde2283f961`);
3. `vdb-validate` 3.1.1 verified its internal checksums;
4. `fasterq-dump --split-3 --skip-technical` produced the pair, and its reported spot count
   was checked against the catalogue;
5. each FASTQ's `sha256`, spot count and base count were recorded, and the two mates were
   required to agree before any alignment ran.

The ENA md5 values were **not** used and are not claimed to hold for these files: a
`fasterq-dump` conversion is not byte-identical to ENA's own FASTQ.

### Criteria

Declared before the run, recorded in every manifest, unchanged during it:

```
min_mapq 30, min_anchor_nt 20, min_support_fragments 2,
neighbour_window_nt 20, min_anchor_zone_fragments 5,
require_control_junction_support true
```

Anchor zones, the footprint a crossing read must cover on each side:
upstream `122,007,329-122,007,348`, downstream `122,012,479-122,012,498`.

## Configuration

Canonical environment, conda env `zeaguard`: Python 3.12.14, hisat2 2.2.1, samtools 1.21,
sra-tools 3.1.1. `hisat2=2.2.1` and `samtools=1.21` are pinned in `environment.yml`.

## Method

The declared `ALIGNMENT_RECIPE` command templates were executed verbatim, with only paths,
the index name, the library name and thread counts substituted, under
`/bin/bash -o pipefail`:

```
hisat2 -p 20 --dta --max-intronlen 50000 -x <index> -1 <LIB>_1.fastq.gz -2 <LIB>_2.fastq.gz --summary-file <LIB>.hisat2.summary -S <LIB>.raw.sam
samtools collate -@ 20 -O -u <LIB>.raw.sam | samtools fixmate -m -u - - | samtools sort -@ 20 -o <LIB>.pos.bam -
samtools markdup -@ 20 <LIB>.pos.bam <LIB>.markdup.bam
samtools index -@ 20 <LIB>.markdup.bam
samtools view -h <LIB>.markdup.bam OZ319704.1 > <LIB>.OZ319704.1.sam
```

**No annotation and no known-splice-site file was given to the aligner.** The junction in
question could only be found de novo. `--max-intronlen 50000` admits the 5,130 nt gap.
`--no-mixed` and `--no-discordant` were deliberately not used. `markdup` only flags
duplicates; it does not remove them.

The counter then read each extracted SAM and required, for a junction to count as support,
the `N` operation with **both** exact boundaries and, in the same read, every one of the 20
reference bases of both anchor zones covered by `M`, `=` or `X`. The same rule decided the
two annotated control junctions.

## Outputs

Per library, under `results/bioinformatics/nb01/dsrnase3_transcript_evidence/pilot_v1/<run>/`
(git-ignored): the extracted region SAM, `panel.json`, the hisat2 summary, and
`counted/` with `per_library.tsv`, `junction_observations.tsv`,
`mate_bridged_fragments.tsv` and `manifest.json`. `pilot_report.json` and
`index_build.json` sit beside them.

| run | extracted SAM `sha256` | SAM bytes | counted `manifest.json` `sha256` |
| --- | --- | --- | --- |
| `SRR11822340` | `5e881e18ce5336b760c2aa44b2ca9e066aaf9a0eba7429af008dcfb5544249e9` | 1,643,700,922 | `1064456896ed894b3bd8ddbfe1177b08255c123d8476b4a19ab1ba5e2bed4d22` |
| `SRR11822336` | `9a0e57d852f04962f9c8576ee8e8af8dc128cd910003dd25cfd9f1c49f730044` | 1,763,501,481 | `c7464fb40eb10150faac61bfe3285df07955a680391ec9f23e7574dbc889f94d` |
| `SRR11822345` | `a7430e13c25360b66901e8fa35fa9a6c375478fc75253951e653dc2760625e41` | 1,522,056,412 | `2d26468d3c81684af8457c49bb31b6407758a99e6394b7d54af76293b68d48bc` |
| `SRR11822341` | `947b7df013c76e14e594c1107236c30e14015ec3a8718b94668b1f8be27aa731` | 1,445,301,091 | `a3863f30760a3ed7e4a935ceacf4fee9db0c4daea2fd8a2ea09754a880299bce` |

The SAMs total 6.0 GB and stay outside the repository; `results/` is git-ignored and the
copies kept for inspection exclude them.

## Validation / QC

- **Evidence chain, re-verified independently after the run.** For each library, 10 checks:
  the SAM's recomputed `sha256` equals the value in the pilot report, the value the panel
  declared and the value the counted manifest observed; the panel's and the manifest's own
  hashes equal the report's; the manifest records commit `4c842fcd` with a clean checkout;
  and each of the three TSVs matches its recorded hash. **40 of 40 matched.** All eight
  index files and all eight FASTQ files were also recomputed against their records and
  match.
- **hisat2 overall alignment rate**: 92.83 %, 93.01 %, 94.14 %, 93.39 %.
- **Internal detectability control.** Both annotated junctions of the same chain are
  supported in every library under the same rule, so a spliced read at this locus is
  demonstrably detectable in all four.
- **Software verification** is recorded separately: 87 tests of the command and 329 of the
  NB01 selection pass at `4c842fcd`, and the synthetic FASTQ-to-TSV recipe check runs the
  six recipe steps and reproduces the three verdicts. None of that is evidence about this
  locus.

## Results

### Per library

| run | upstream anchor zone `122,007,329-348` | downstream anchor zone `122,012,479-498` | control 456/457 | control 870/871 | eligible fragments at 642/643 | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `SRR11822340` | **20/20 nt**, 24 fragments | **0/20 nt**, 0 fragments | 55 | 42 | **0** | `INCONCLUSIVE_INSUFFICIENT_COVERAGE` |
| `SRR11822336` | **20/20 nt**, 18 fragments | **0/20 nt**, 0 fragments | 34 | 45 | **0** | `INCONCLUSIVE_INSUFFICIENT_COVERAGE` |
| `SRR11822345` | **20/20 nt**, 47 fragments | **0/20 nt**, 0 fragments | 83 | 73 | **0** | `INCONCLUSIVE_INSUFFICIENT_COVERAGE` |
| `SRR11822341` | **20/20 nt**, 31 fragments | **0/20 nt**, 0 fragments | 90 | 66 | **0** | `INCONCLUSIVE_INSUFFICIENT_COVERAGE` |

In every library the single failed requirement is the same:
`downstream_anchor_zone_fragments=0<5 over 122012479-122012498 (0/20 nt covered)`.

### The locus is deeply covered, and the acceptor-side footprint is not

| run | records on `OZ319704.1` | fragments | upstream flank covered | downstream flank covered |
| --- | --- | --- | --- | --- |
| `SRR11822340` | 4,160,041 | 2,090,923 | 186/186 nt (100 %) | 201/228 nt (88.16 %) |
| `SRR11822336` | 4,473,651 | 2,249,814 | 186/186 nt (100 %) | 201/228 nt (88.16 %) |
| `SRR11822345` | 3,872,526 | 1,924,317 | 186/186 nt (100 %) | 201/228 nt (88.16 %) |
| `SRR11822341` | 3,663,211 | 1,837,652 | 186/186 nt (100 %) | 201/228 nt (88.16 %) |

The uncovered part of the downstream flank is **one contiguous interval, identical in all
four libraries: `122,012,479-122,012,505`, 27 nt**, computed from qualifying records only.
Coverage of that flank begins at 122,012,506 and is unbroken to its end. So the first 27 nt
of the published CDS block 4 — CDS positions 643 to 669 — carry no qualifying aligned
coverage in any of these libraries, while the remaining 201 nt do.

### Every spliced read at the exact donor goes somewhere else, and to the same place

| run | fragments spliced from donor `122,007,349` | acceptor they reach | implied intron | fragments reaching `122,012,479` |
| --- | --- | --- | --- | --- |
| `SRR11822340` | 41 | `122,007,663` | 315 nt | **0** |
| `SRR11822336` | 27 | `122,007,663` | 315 nt | **0** |
| `SRR11822345` | 64 | `122,007,663` | 315 nt | **0** |
| `SRR11822341` | 39 | `122,007,663` | 315 nt | **0** |

The donor coordinate is shared exactly with the junction in question. In all four libraries,
**every** qualifying spliced read at that donor — 171 fragments in total, with no exception
in any library — ends its intron at 122,007,663 and resumes at 122,007,664, an intron of
315 nt. That is the intron the Ensembl AEGIS annotation places at that donor for
`ENSCHMT00000005294`, as the 2026-11-15 run record states. Not one read took the 5,130 nt
jump.

`acceptor_only` and `neighbour` counts are **0** in every library: no qualifying read
reaches 122,012,479 from any donor, and none carries a junction within 20 nt of either
declared boundary other than the donor coincidence above.

### Other counters

Reported for completeness, never as support: ambiguous fragments 48,646 to 59,264 per
library; flagged duplicates 407,472 to 880,424; mate-bridged fragments 0, 0, 2 and 5;
short-anchor and disqualified fragments at the target junction 0 in all four.

## Interpretation

**By library and by method.** In each of the four libraries, under this recipe and these
criteria, the verdict is `INCONCLUSIVE_INSUFFICIENT_COVERAGE`, and for one reason: the 20
reference bases a crossing read would have had to cover on the acceptor side carry no
qualifying coverage at all. The criteria are built so that an absence of crossing reads is
only called interpretable where a crossing read could have been seen. Here it could not,
so **zero eligible crossings is not reported as zero support** in any library.

Three things are nevertheless on record, and they point the same way in all four libraries:

1. The locus is not short of reads. Each library puts 3.7 to 4.5 million records on this
   chromosome, covers the upstream flank completely and the downstream flank to 88 %, and
   supports both annotated junctions of the same chain tens of times over. Splicing at this
   locus is detectable in these data.
2. The acceptor the junction in question requires, 122,012,479, is reached by **no**
   qualifying read, and the 27 nt from it onward are uncovered in every library, as one
   contiguous interval with identical boundaries. Coverage resumes at 122,012,506, which is
   38 nt before the annotated `ube2w` coding segment begins at 122,012,544.
3. At the donor the junction shares, 171 fragments across the four libraries splice, and all
   of them take the annotated 315 nt intron to 122,007,664 instead.

Taken together these are consistent with the donor being a real, used splice donor whose
acceptor in these libraries is the annotated one, and with the published block 4 beginning
27 nt before anything these libraries transcribe. They are **not** a refutation of the
642/643 junction: a junction can be real and absent from four libraries of one isolate, one
tissue preparation, one locality and one temperature, and an uncovered footprint cannot
carry an absence claim. The declared verdict stands as the result; the three observations
above are the evidence a later round would have to explain.

**What a single eligible crossing would have meant.** One eligible crossing fragment
supports the local 642/643 junction in the library it was found in. None was found, and
none could have been recognised here.

**The two open questions are untouched.** The origin of the contig
`TRINITY_DN5008_c0_g1_i24` — which reads and which assembly produced it — and the
attribution of the complete 1,236 nt CDS to a single molecule remain open, and nothing in
this run addresses either. The libraries used here are `comparative`: whether any of them
also contributed to that assembly is neither established nor excluded.

## What this run does NOT establish

- It does not establish that the 642/643 junction is absent from the species, from this
  isolate, or from any tissue or condition not sampled here. Four libraries of one
  California isolate collected in Wooster, Ohio, whole insects, pooled sexes, at 30 °C,
  naive or MRFV-exposed at 4 h and 7 days, are a narrow sample.
- It does not establish that the junction is spliced anywhere. No read supports it here.
- It does not refute the transcriptomic-chimera hypothesis the 2026-11-15 record carries,
  and does not confirm it.
- It does not bound the sensitivity of this pipeline on real libraries. The 20 nt
  operational anchor cut is a conservative figure two nucleotides above the shortest anchor
  recovered on both sides of a **synthetic** reference (15 nt upstream, 18 nt downstream);
  what fraction of real crossing reads this configuration would recover is unknown, so every
  count here is a lower bound of unquantified tightness.
- It does not assign any library to the assembly of the published contig, and no
  `origin_class` here is `confirmed_origin`.
- It does not establish gene identity, expression level, regulation, enzymatic activity or
  any phenotype.
- Successful execution and reproducible hashes do not demonstrate scientific validity.

## Anomalies / deviations

1. **The read source differs from the catalogue's URL**, with a different verification
   chain, for the throughput reason recorded under Inputs. ENA's md5 values do not apply to
   the converted files and are not claimed to.
2. **One step was repeated.** The first conversion attempt for `SRR11822340` was lost
   because two instances of the fetch script ran at once and the second deleted the first's
   in-progress output. No counted result came from it; the repeat is visible in
   `fetch_reads.log`, which retains both attempts. The script now takes an exclusive
   `flock`, resumes by comparing size against the bucket's `Content-Length` rather than
   trusting a non-empty file, and checks `fasterq-dump`'s exit status, which it previously
   ignored.
3. **The pilot was relaunched before any alignment ran.** An orchestration queued against
   `48d563af` was stopped while still blocked on the fetch lock, and relaunched against
   `4c842fcd` so that every library would be processed by the hardened executor. No
   alignment or count was produced by the earlier version.
4. **`samtools view` by region needs an index, and `fixmate` needs name-grouped input.**
   Both were missing from the recipe in an earlier version of this branch and were added
   with `samtools index` and `samtools collate` before this run.
5. **Three defects of the counter were corrected before this run and are not reflected in
   any output here**: an informative-coverage rule that accepted a blank footprint beside
   each boundary, a mate-bridge rule that counted two alignments sharing only a read name,
   and an anchor rule that let aligned bases further out compensate for a deletion at the
   edge. Each is recorded in its commit with a regression test.

No deviation from the declared canonical environment.

## Related decisions

[ADR 0009](../decisions/0009-nb01-dsrnase-locus-assignment-criteria.md) records the locus
assignment criteria this branch builds on. The criteria of **this** command are declared in
`Criteria` in `src/zeaguard/nb01_dsrnase3_transcript_evidence.py` and reproduced in every
manifest; no ADR governs them yet, and whether they warrant one is a question for the
Coordinator.

Preceding run record: [2026-11-15 NB01 dsRNase locus mapping](2026-11-15_nb01-dsrnase-locus-mapping.md),
whose second addendum assigns the junction this run interrogates and states that settling the
origin of the transcript needs RNA evidence spanning it. The TSA search outcome for
dsRNase-3 is documented in [2026-10-03 NB01 dsRNase-2 identity](2026-10-03_nb01-dsrnase2-identity.md),
Results items 6 and 9.

## Related Issue / PR / commits

Branch `feat/nb01-dsrnase3-transcript-evidence`. `7519219` adds the command, `e65d86d`,
`48d563a` and `4c842fc` correct it; all four are pushed. This record is committed and **not
pushed**: it is scientific documentation, and the disclosure, privacy, pertinence and
integrity review that precedes its publication is the repository owner's decision under
CONTRIBUTING.md §8. No pull request has been opened.

## Evidence classification

1. `directly demonstrated`: the `sha256` of the assembly in both forms, of the eight index
   files, of the eight FASTQ files as opened by the aligner, of each extracted SAM, panel,
   table and manifest, each recomputed independently after the run; the spot and base counts
   of all eight FASTQ files and their agreement with the ENA catalogue and with
   `fasterq-dump`; the hisat2 alignment rates; the record and fragment counts on
   `OZ319704.1` per library; the coverage of both flanks and of both anchor zones per
   library; the 27 nt uncovered interval `122,012,479-122,012,505` and its identity across
   all four libraries; the fragment counts supporting both annotated control junctions; that
   no qualifying read in any of the four libraries carries an `N` operation ending at
   122,012,478 or beginning an aligned block at 122,012,479; and that every qualifying
   spliced read at donor 122,007,349 ends its intron at 122,007,663.
2. `derived/computed`: the per-library verdicts under the declared criteria; the
   per-fragment deduplication; the ambiguous, duplicate, mate-bridge, short-anchor and
   neighbour counts.
3. `inferred/interpreted`: that splicing is detectable at this locus in these libraries,
   inferred from the annotated control junctions being supported; that the donor is a real
   splice donor whose acceptor in these libraries is the annotated one at 122,007,664; that
   the published block 4 begins upstream of anything these libraries transcribe. Each is a
   reading of the counts above and not an observation of a splice event.
4. `unresolved`: whether the 642/643 junction is spliced in any transcript; the biological
   origin of the published dsRNase-3 transcript; which reads and which assembly produced
   `TRINITY_DN5008_c0_g1_i24`; whether the complete CDS belongs to one molecule; the
   sensitivity of this pipeline on real libraries; and whether the 25 °C libraries of
   PRJNA579843, or the remaining twelve runs of PRJNA631706, would change any count here.
