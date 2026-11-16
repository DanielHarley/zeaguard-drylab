# Title

Assign a published Dmai-dsRNase CDS to a genomic locus only on pre-registered coverage, identity and contiguity criteria, and report locus distinctness separately from sequence similarity

## Status

Proposed

## Date

2026-11-15

## Context / problem

[ADR 0004](0004-nb01-dsrnase2-identity-criteria.md) classified Dmai-dsRNase-2 as `AMBIGUOUS` at the accession, CDS and protein levels. The [operational reference](../../../../data/reference/nb01_dsrnase2_operational_reference.json) records CDS of 1425 nt for both TSA accessions, `GITV01008430.1` and `GITV01012450.1`, with distinct SHA256 hashes. `GITV01008430.1` exactly matches the published CDS. The NB01 family audit then confirmed coding-region integrity and PF01223 classification for all three published proteins and stated explicitly that it does **not** establish attribution to loci. Its run record, `2026-11-13_nb01-dsrnase-protein-audit.md`, is not in this tree: it lives on the unpublished branch `feat/nb01-dsrnase-protein-audit`, so it is named rather than linked, and nothing in this record or its implementation depends on that branch.

Two questions were left open, and both are questions about the genome, not about the transcriptome:

1. does Dmai-dsRNase-3 occupy a locus of its own, distinct from those of dsRNase-1 and dsRNase-2;
2. do `GITV01008430.1` and `GITV01012450.1` come from one genomic locus or from distinct loci (paralogues, alleles, or an assembly artefact of the TSA).

Answering either one requires a genome assembly of *Dalbulus maidis*, criteria for when an alignment is a locus assignment rather than a similarity, and criteria for when two assignments are distinct loci rather than two views of one region. None of those criteria exists in this repository. The transcript-level thresholds of ADR 0004 do not transfer: they were written for a transcriptome in which a locus has no coordinates, and they say nothing about assembly contiguity, repeat content, or exon structure.

There is a specific trap to avoid, already visible in NB01's own observations. The investigation recorded tandem-repeat structure in the 3' flank of `GITV01012450.1`. An alignment that lands in a repetitive or fragmented region can place two sequences in "the same region" without those sequences coming from the same locus, and a fragmented assembly can split one locus across two sequences or collapse two loci into one. A criterion that reads only identity and coverage will report a confident answer in exactly the cases where no answer is available.

This record does **not** modify ADR 0003, ADR 0004, or the family audit. It adds criteria for a new mapping whose results are recorded in the [run record](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md).

## Question being decided

Under what preregistered criteria can a published Dmai-dsRNase CDS be assigned to a locus in a declared *D. maidis* assembly? When can two assignments be classified as distinct loci, the same locus or `INDETERMINATE`? How should each assembly's locus count for the published dsRNase-2 CDS be reported?

## Evidence

1. Existence and versioned identity of the assemblies, queried from NCBI for taxid 74065 on 2026-11-15 (`directly demonstrated`; the survey and the three accessions it returned are recorded in [`data/reference/nb01_dsrnase_locus_panel.json`](../../../../data/reference/nb01_dsrnase_locus_panel.json) and in the run record). This was treated as the first question to answer, not as an assumption: had no usable assembly existed, that finding would have been the result.
2. ADR 0004, the [operational reference](../../../../data/reference/nb01_dsrnase2_operational_reference.json) and the [NB01 dsRNase-2 identity run record](../runs/2026-10-03_nb01-dsrnase2-identity.md) document equal CDS lengths and distinct CDS hashes for the two TSA records, as well as tandem repeats in the 3′ flank of `GITV01012450.1` (`derived/computed`).
3. The family audit run record `2026-11-13_nb01-dsrnase-protein-audit.md` (on the unpublished branch `feat/nb01-dsrnase-protein-audit`), which states that locus attribution is outside its scope (`directly demonstrated`).
4. Primary source: Dalaisón-Fuentes et al. 2023, Pestic. Biochem. Physiol. 196:105618 (DOI 10.1016/j.pestbp.2023.105618, PMID 37945254), Table 1 ORF coordinates and Supplementary File S1 (`directly demonstrated` for the printed coordinates).
5. Implementation: [`nb01_locus.py`](../../../zeaguard/nb01_locus.py) and its [tests](../../../../tests/test_nb01_locus.py).
6. The repository anchors [`data/reference/target_anchor_sequences.fasta`](../../../../data/reference/target_anchor_sequences.fasta), from which the three CDS queries are derived (`derived/computed`).
7. Added after this record was fixed, not consulted in the original execution: the Ensembl AEGIS Genebuild gene annotation (geneset `2026_02`) for `GCA_975739785.1`, compared against the three inferred loci by [`scripts/compare_nb01_locus_to_ensembl_aegis.py`](../../../../scripts/compare_nb01_locus_to_ensembl_aegis.py) at commit `e1befb9069818e16d691ada54e04403327d9cee0`, with the GFF3's URL, `sha256` and the chromosome 1 / `OZ319704.1` correspondence recorded in the [run record's addendum](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md#addendum-2026-11-15-comparison-against-the-ensembl-aegis-gene-annotation) (`directly demonstrated` for the annotation's provenance and the raw BLAST identity/mismatch counts it reuses; `inferred/interpreted` for the transcriptomic-chimera hypothesis it records for dsRNase-3).

## Evidence classification

Every material claim of this record, in the weakest category the evidence supports.

| Claim | Category |
| --- | --- |
| Three assemblies exist for taxid 74065 with the versioned accessions recorded in the panel | `directly demonstrated` |
| The declared assembly statistics are the statistics of the declared files | `derived/computed` (recomputed from each file at every run) |
| The three CDS queries, and their agreement with the published Table 1 ORF coordinates | `derived/computed` |
| Coverage, identity, locus span, assembly-gap content and contiguity of each locus | `derived/computed` |
| The exon/intron structure of a locus | `inferred/interpreted` — read from the gaps of an HSP tiling, not from an annotation or a spliced aligner |
| That a locus with one alignment per CDS is a single genomic copy | `inferred/interpreted` — conditional on the assembly not having collapsed a duplication |
| Genomic origin of `GITV01012450.1` and whether the two TSA records share a locus | `unresolved` in this run, which queried the published CDS |
| Any statement about enzymatic activity | out of scope; not made |

All thresholds below are `operational assumption`. None has bibliographic or empirical calibration for *D. maidis*, and none is adapted after seeing results.

## Alternatives considered

- **A spliced aligner** (`minimap2 -ax splice`, `miniprot`, `exonerate`, `GMAP`) instead of BLASTn HSP tiling. Rejected for this run: none is in the declared canonical environment (`environment.yml`: BLAST+ 2.17.0, HMMER 3.4), and adding a dependency to a reproducibility-bound pipeline is a larger change than the question requires. Consequence accepted and recorded: the exon/intron structure is `inferred/interpreted` from HSP gaps, a weaker basis than a splice-aware alignment, and short terminal exons may be missed. This is the main revision condition below.
- **Mapping the published transcripts rather than the derived CDS.** Rejected: the published transcripts carry long flanking regions, and ADR 0004 recorded that coverage computed over a full transcript is dominated by flank length. Flanks also carry the tandem-repeat structure that makes a locus call unsafe. Restricting the query to the CDS keeps coverage interpretable and keeps the known repeat out of the query.
- **Mapping the proteins with TBLASTN.** Rejected as the primary method: a protein alignment cannot measure nucleotide identity between an allele and a reference, which is the measurement that separates "the same gene in another individual" from "a paralogue". Not excluded as a future corroboration.
- **Using a genome of another leafhopper species.** Rejected: a locus in another species is not a locus in *D. maidis*. Had no *D. maidis* assembly existed, the result of the run would have been that finding.
- **Including the third surveyed assembly, `GCA_054756405.1` (CIAP v1), as a mapping target.** Rejected and recorded in the panel under `surveyed_not_used`, with the reason: contig-level, scaffold N50 50,514 nt, 20× coverage. In such an assembly a single-locus observation cannot be distinguished from contig fragmentation, and a collapsed duplication is more likely than in the 75× chromosome-level assembly, so it could neither confirm nor refute a copy-number observation.
- **Calling two loci "the same" when their spans overlap.** Rejected: see the decision below. Overlap on one sequence is the case in which the method cannot distinguish one locus from two overlapping alignments of a repeat, so it is `INDETERMINATE`.

## Decision

Apply the following, in this order, without adapting any criterion after seeing results.

1. **Assembly admissibility.** A mapping target must be a public genome assembly of *Dalbulus maidis* (taxid 74065) with a versioned accession. Its file is declared in the input panel with source URL, `sha256`, and verification mode, and is verified before use. In addition, the number of sequences, total length, ungapped length, scaffold N50 and number of assembled molecules declared in the panel are recomputed from the file at every run; a disagreement aborts the run. A hash alone proves the bytes did not change, not that the file is the assembly the panel describes.

2. **Queries.** One query per published dsRNase: the CDS, derived from the Trinity transcript in the repository anchors as the longest stop-delimited ORF read from its first methionine. The published Table 1 ORF coordinates, CDS length and protein length are declared in the panel and the derivation is checked against them; a disagreement aborts the run. The query is the CDS only, never the full transcript.

3. **Search.** `blastn -task blastn -dust no -evalue 1e-5`, the discovery parameter set of ADR 0004, with `-max_target_seqs` set above the sequence count of the largest declared assembly so the limit provably cannot truncate the result; the run records that the observed subject count stayed below the limit. No `-max_hsps`: exons are HSPs, and discarding HSPs would discard the exon structure.

4. **Locus formation.** HSPs of one query on one sequence and one strand form one locus when the genomic distance between consecutive HSPs is at most 50,000 nt. Strands never merge. Within a locus, HSPs are tiled best-score-first into one alignment block per inferred exon; a block joins the tiling when it overlaps the accepted blocks by at most 10 query nucleotides and not at all in the genome.

5. **Reporting tier.** A locus is reported when it covers at least 50 % of the CDS — the discovery coverage threshold of ADR 0004, deliberately broad, saying nothing about identity. Reported loci are tiered: `ASSIGNMENT_CRITERIA` when query coverage is at least 90 % **and** identity over the tiled alignment is at least 98 %, otherwise `RELATED`.

6. **Assignment.** A CDS is assigned to a locus (`DETERMINED`) only when **exactly one** locus of that assembly meets `ASSIGNMENT_CRITERIA`. Zero loci gives `INDETERMINATE / NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA`; two or more gives `INDETERMINATE / MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA`. The count of loci at assignment criteria and the count of related loci are reported in both cases. A locus is never chosen by rank: the best-scoring of several passing loci is not an assignment.

7. **Contiguity and repeat context, reported with every locus and never omitted.** The sequence the locus sits on and its role (assembled molecule versus unlocalized or unplaced sequence), its length, the locus span, the number of assembly-gap nucleotides and gap runs inside the span, the distance from the span to the nearer end of the sequence, the number of other loci of the same query reaching the 50 % reporting threshold, the colinearity of the tiling, the inferred intron sizes, the unaligned CDS nucleotides at each junction, and the two-nucleotide termini of each inferred intron with a count of canonically spliceable `GT..AG` pairs. A non-canonical pair is reported, never filtered.

8. **Distinctness, decided pairwise and separately from similarity.** Two assigned loci are `DETERMINED` distinct when they lie on different assembly sequences, or on one sequence with non-overlapping spans, in which case the gap between the spans is reported. They are `INDETERMINATE / OVERLAPPING_SPANS_ON_ONE_SEQUENCE` when their spans overlap: that is the configuration a repeat and a true shared locus both produce, and the method does not separate them. If either locus is unassigned, the pair is `INDETERMINATE / UNASSIGNED_LOCUS`.

9. **Locus counts for the published dsRNase-2 CDS.** Report the number of loci that meet the assignment criteria for the published CDS in each assembly using the keys `ONE_LOCUS_DETECTED`, `MULTIPLE_LOCI_DETECTED` and `NO_LOCUS_DETECTED`. The count applies to the published query, which matches `GITV01008430.1`. The genomic origin of `GITV01012450.1` remains `unresolved`.

10. **Alternate haplotype.** When an alternate pseudohaplotype of the same biosample is available it is mapped as a second, independent target, because a heterozygous duplication collapsed in one pseudohaplotype may be resolved in the other. Agreement between the two haplotypes strengthens a copy-number observation; it does not convert it into a demonstration, because both derive from one individual.

## Rationale

The 90 % coverage and 98 % identity thresholds separate the two errors that matter here. Coverage below 90 % means the locus does not account for the CDS, which is what a partial or fragmented locus looks like; identity below 98 % between a published transcript and an assembly of a different individual of the same species is more divergence than an allelic difference would predict, which is what a paralogue looks like. Requiring both, and requiring uniqueness rather than a best score, means the method answers "is there exactly one genomic locus that accounts for this CDS" instead of "which region scores highest", and the second question always has an answer while the first one does not.

The 50,000 nt locus distance is deliberately generous relative to insect intron lengths. The asymmetry is intentional: an intron longer than the limit splits one locus into two partial loci, each failing the coverage threshold and visible in the output as a partial locus, whereas too small a limit would hide the split inside a single confident-looking call.

Reporting contiguity and repeat context with every locus, as rule 7 requires, is what keeps rule 8 honest. The task that motivated this record states the risk directly: two sequences mapping to one region do not establish one locus if the region is repetitive or the assembly fragmented. The repeat measure for the query is the count of other loci the same CDS reaches at the reporting threshold; the fragmentation measure is the gap content of the span and the distance to the sequence ends. Both are computed from the declared input at every run, so a reviewer never has to take the locus call on trust.

Rule 9 ties the count to the query and the declared criteria. The genomic relationship between the TSA records remains open.

## Consequences

- NB01 gains a reproducible locus-mapping command with declared, hash-verified inputs, pre-registered criteria, and an `INDETERMINATE` outcome that is a result rather than a failure.
- The criteria are specific to a CDS-against-genome mapping with HSP tiling. They are not identity criteria and do not supersede ADR 0003 or ADR 0004.
- The exon/intron structure the mapping reports is `inferred/interpreted` and must be labelled so wherever it is reused. It is not a gene annotation, and the repository gains no annotation from this run.
- Review focus follows from rule 7: a locus call is to be judged together with its contiguity and repeat columns, not from coverage and identity alone.
- Nothing in this record authorizes any scientific execution beyond the declared mapping, and nothing in it bears on NB02 region selection, NB03, or NB04 gates.

## Limitations

- BLASTn HSP tiling is not a splice-aware alignment. Exons shorter than the effective seed length may be missed, junction coordinates are approximate within the tolerated overlap, and the inferred structure is weaker evidence than a spliced aligner or an annotation would give.
- This record's own survey checked NCBI only and found no gene annotation for either declared assembly; it did not check Ensembl, and makes no claim about whether an independent annotation existed anywhere at the time. The mapping's own declared genomic targets were the two assembly FASTAs; no GFF3 was declared or consulted. A later round on this branch retrieved and checked an Ensembl AEGIS Genebuild annotation (geneset `2026_02`) for the primary assembly, `GCA_975739785.1`, for the first time; the alternate haplotype, `GCA_975739835.1`, still has none checked. The comparison against that annotation is recorded in the addendum to the [run record](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md#addendum-2026-11-15-comparison-against-the-ensembl-aegis-gene-annotation), not in this ADR's own criteria, which this annotation does not supersede on its own (see the falsification condition below).
- Both declared assemblies derive from one biosample (`SAMEA117578701`). The locus counts pertain to those assemblies. Population level variation remains unresolved.
- The run detected one locus for the published dsRNase-2 CDS in the primary assembly. The search of the alternate assembly detected no locus under the applied parameters, leaving the comparison between haplotypes inconclusive. A collapsed duplication remains possible.
- The 98 % identity threshold assumes that allelic divergence between the sequenced individuals is below 2 %. That assumption is not calibrated for *D. maidis*.
- The published transcripts and the assemblies come from different individuals and different studies; no statement about the same individual is available.

## What this decision does NOT establish

- It does not establish that any locus call is correct, that any assembly is correct, or that the inferred exon/intron structure is the true gene structure.
- The genomic origin of `GITV01012450.1` and its relationship to the locus detected for the published CDS remain `unresolved`.
- It does not establish gene identity, orthology, paralogy, gene family size, or copy number in the species.
- It does not establish or bear on enzymatic activity, substrate specificity, expression, or any phenotype. No such claim is made anywhere in the mapping.
- It does not establish scientific validity. A successful execution and a reproducible result are neither.

## Falsification / revision conditions

- An annotated *D. maidis* assembly, or one with RNA-seq-supported gene models, would supersede the HSP-tiling inference and is reason to revise rules 4 and 7. **Partially triggered:** a later round on this branch retrieved and checked an Ensembl AEGIS Genebuild annotation for `GCA_975739785.1`, comparing it against the three inferred loci (see the run record addendum). Whether this annotation existed before or after this ADR was written is not established and is not claimed; what is documented is the order in which this repository checked for and used it. This record treats that comparison as corroborating evidence, not as a supersession: it does not revise rules 4 or 7, does not re-run or replace the HSP tiling, and the comparison itself required no splice-aware alignment. Revising rules 4 and 7 to use the annotation directly, or to add a splice-aware aligner, remains deferred to a future round.
- Adding a splice-aware aligner to the declared environment is reason to revise the method and to re-examine every `inferred/interpreted` structure.
- An assembly of a second individual at chromosome level is reason to revise rule 9: copy number could then be compared across individuals.
- Read-depth evidence over an assigned locus is reason to revise the collapsed-duplication limitation.
- A measured estimate of allelic divergence in *D. maidis* is reason to revise the 98 % identity threshold.
- Observing that a declared assembly has been replaced or suppressed at NCBI is reason to revise the panel, not to relax verification.

## Related notebook

`src/zeaguard/nb01_locus.py`

## Related dataset / artifact

`data/reference/nb01_dsrnase_locus_panel.json`; outputs under `results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/` (git-ignored, reproducible from the declared inputs).

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed`

## Provenance

Recorded contemporaneously with the implementation, on the branch `feat/nb01-dsrnase-locus-mapping` cut from `origin/master`. Evidence inspected before the criteria were fixed: the NCBI taxonomy and assembly records for taxid 74065 and the NCBI Datasets reports of the three accessions; ADR 0003, ADR 0004 and the three NB01 run records named above; `data/reference/target_anchor_sequences.fasta` and `data/reference/target_anchors.tsv`; `environment.yml` and the tool inventory of the canonical conda environment. The thresholds in the decision were written before any alignment against either assembly was run; the run record states the commit at which the first full execution happened.

# Versão em PTBR

# Título

Atribuir uma CDS publicada de Dmai-dsRNase a um locus genômico somente sob critérios pré-registrados de cobertura, identidade e contiguidade, e relatar a distinção entre loci separadamente da simples similaridade de sequência

## Estado

Proposed

## Data

2026-11-15

## Contexto / problema

O [ADR 0004](0004-nb01-dsrnase2-identity-criteria.md) classificou Dmai-dsRNase-2 como `AMBIGUOUS` nos níveis de acesso, CDS e proteína. A [referência operacional](../../../../data/reference/nb01_dsrnase2_operational_reference.json) registra CDS de 1425 nt para os dois acessos do TSA, `GITV01008430.1` e `GITV01012450.1`, com hashes SHA256 distintos. A CDS de `GITV01008430.1` coincide exatamente com a publicada. A auditoria de família do NB01 confirmou a integridade das regiões codificantes e a classificação PF01223 das três proteínas publicadas e declarou explicitamente que **não** estabelece atribuição a loci. Seu registro de execução, `2026-11-13_nb01-dsrnase-protein-audit.md`, não está nesta árvore: está na branch não publicada `feat/nb01-dsrnase-protein-audit`, por isso é citado pelo nome e não por link, e nada neste registro nem em sua implementação depende daquela branch.

Duas perguntas ficaram abertas, e ambas são perguntas sobre o genoma, não sobre o transcriptoma:

1. Dmai-dsRNase-3 ocupa um locus próprio, distinto dos de dsRNase-1 e dsRNase-2;
2. `GITV01008430.1` e `GITV01012450.1` vêm de um mesmo locus genômico ou de loci distintos (parálogos, alelos ou artefato de montagem do TSA).

Responder a qualquer uma delas exige uma montagem genômica de *Dalbulus maidis*, critérios para quando um alinhamento é uma atribuição a locus e não uma similaridade, e critérios para quando duas atribuições são loci distintos e não duas vistas de uma mesma região. Nenhum desses critérios existe neste repositório. Os limiares de nível transcrito da ADR 0004 não se transferem: foram escritos para um transcriptoma em que um locus não tem coordenadas, e nada dizem sobre contiguidade de montagem, conteúdo repetitivo ou estrutura de éxons.

Há uma armadilha específica a evitar, já visível nas próprias observações do NB01. A investigação registrou estrutura de repetição em tandem no flanco 3' de `GITV01012450.1`. Um alinhamento que cai em região repetitiva ou fragmentada pode colocar duas sequências na "mesma região" sem que elas venham do mesmo locus, e uma montagem fragmentada pode partir um locus entre duas sequências ou colapsar dois loci em um. Um critério que leia apenas identidade e cobertura relatará uma resposta confiante exatamente nos casos em que nenhuma resposta está disponível.

Este registro **não** modifica a ADR 0003, a ADR 0004 nem a auditoria de família. Acrescenta critérios para um novo mapeamento cujos resultados estão no [registro de execução](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md).

## Questão sendo decidida

Sob quais critérios definidos previamente uma CDS publicada de Dmai-dsRNase pode ser atribuída a um locus em uma montagem declarada de *D. maidis*? Quando duas atribuições podem ser classificadas como loci distintos, como o mesmo locus ou como `INDETERMINADO`? Como relatar a contagem de loci para a CDS publicada de dsRNase-2 em cada montagem?

## Evidências

1. Existência e identidade versionada das montagens, consultadas no NCBI para o taxid 74065 em 2026-11-15 (`diretamente demonstrado`; o levantamento e os três acessos retornados estão em [`data/reference/nb01_dsrnase_locus_panel.json`](../../../../data/reference/nb01_dsrnase_locus_panel.json) e no registro de execução). Isso foi tratado como a primeira pergunta a responder, não como pressuposto: se não houvesse montagem utilizável, esse achado seria o resultado.
2. O ADR 0004, a [referência operacional](../../../../data/reference/nb01_dsrnase2_operational_reference.json) e o [registro de execução da identidade de dsRNase-2](../runs/2026-10-03_nb01-dsrnase2-identity.md) documentam CDS de mesmo comprimento e hashes distintos nos dois registros do TSA, além de repetições em tandem no flanco 3′ de `GITV01012450.1` (`derivado/computado`).
3. O registro da auditoria de família `2026-11-13_nb01-dsrnase-protein-audit.md` (na branch não publicada `feat/nb01-dsrnase-protein-audit`), que declara a atribuição a loci fora de seu escopo (`diretamente demonstrado`).
4. Fonte primária: Dalaisón-Fuentes et al. 2023, Pestic. Biochem. Physiol. 196:105618 (DOI 10.1016/j.pestbp.2023.105618, PMID 37945254), coordenadas de ORF da Tabela 1 e Arquivo Suplementar S1 (`diretamente demonstrado` para as coordenadas impressas).
5. Implementação: [`nb01_locus.py`](../../../zeaguard/nb01_locus.py) e seus [testes](../../../../tests/test_nb01_locus.py).
6. Os âncoras do repositório [`data/reference/target_anchor_sequences.fasta`](../../../../data/reference/target_anchor_sequences.fasta), de onde as três CDS de consulta são derivadas (`derivado/computado`).
7. Acrescentada depois que este registro foi fixado, não consultada na execução original: a anotação de genes do Ensembl Genebuild do Ensembl AEGIS (conjunto de genes `2026_02`) para `GCA_975739785.1`, comparada contra os três loci inferidos por [`scripts/compare_nb01_locus_to_ensembl_aegis.py`](../../../../scripts/compare_nb01_locus_to_ensembl_aegis.py) no commit `e1befb9069818e16d691ada54e04403327d9cee0`, com a URL do GFF3, o `sha256` e a correspondência entre o cromossomo 1 e `OZ319704.1` registrados no [adendo do registro de execução](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md#addendum-2026-11-15-comparison-against-the-ensembl-aegis-gene-annotation) (`diretamente demonstrado` para a proveniência da anotação e as contagens de identidade/divergência do BLAST bruto que ela reutiliza; `inferido/interpretado` para a hipótese de quimera transcriptômica que registra para dsRNase-3).

## Classificação das evidências

Cada afirmação material deste registro, na categoria mais fraca que a evidência sustenta.

| Afirmação | Categoria |
| --- | --- |
| Existem três montagens para o taxid 74065 com os acessos versionados registrados no painel | `diretamente demonstrado` |
| As estatísticas declaradas de montagem são as estatísticas dos arquivos declarados | `derivado/computado` (recomputadas a cada execução) |
| As três CDS de consulta e sua concordância com as coordenadas de ORF da Tabela 1 | `derivado/computado` |
| Cobertura, identidade, extensão do locus, conteúdo de lacunas de montagem e contiguidade de cada locus | `derivado/computado` |
| A estrutura éxon/íntron de um locus | `inferido/interpretado` — lida das lacunas de um empilhamento de HSPs, não de uma anotação nem de um alinhador splice-aware |
| Que um locus com um alinhamento por CDS é uma cópia genômica única | `inferido/interpretado` — condicional a a montagem não ter colapsado uma duplicação |
| Origem genômica de `GITV01012450.1` e eventual compartilhamento de locus entre os dois registros do TSA | `não resolvido` nesta execução, que consultou a CDS publicada |
| Qualquer afirmação sobre atividade enzimática | fora de escopo; não feita |

Todos os limiares abaixo são `pressuposto operacional`. Nenhum tem calibração bibliográfica ou empírica para *D. maidis*, e nenhum é adaptado depois de ver resultados.

## Alternativas consideradas

- **Um alinhador splice-aware** (`minimap2 -ax splice`, `miniprot`, `exonerate`, `GMAP`) em vez do empilhamento de HSPs do BLASTn. Rejeitado nesta execução: nenhum está no ambiente canônico declarado (`environment.yml`: BLAST+ 2.17.0, HMMER 3.4), e acrescentar dependência a um pipeline vinculado a reprodutibilidade é mudança maior do que a pergunta exige. Consequência aceita e registrada: a estrutura éxon/íntron é `inferido/interpretado` a partir de lacunas de HSPs, base mais fraca que um alinhamento splice-aware, e éxons terminais curtos podem passar sem detecção. É a principal condição de revisão abaixo.
- **Mapear os transcritos publicados em vez das CDS derivadas.** Rejeitado: os transcritos publicados carregam flancos longos, e a ADR 0004 registrou que cobertura computada sobre o transcrito inteiro é dominada pelo comprimento dos flancos. Os flancos também carregam a estrutura de repetição em tandem que torna insegura a atribuição a locus. Restringir a consulta à CDS mantém a cobertura interpretável e mantém a repetição conhecida fora da consulta.
- **Mapear as proteínas com TBLASTN.** Rejeitado como método primário: um alinhamento de proteína não mede identidade nucleotídica entre um alelo e uma referência, que é a medida que separa "o mesmo gene em outro indivíduo" de "um parálogo". Não excluído como corroboração futura.
- **Usar o genoma de outra espécie de cigarrinha.** Rejeitado: um locus em outra espécie não é um locus em *D. maidis*. Se não existisse montagem de *D. maidis*, o resultado da execução seria esse achado.
- **Incluir a terceira montagem levantada, `GCA_054756405.1` (CIAP v1), como alvo de mapeamento.** Rejeitado e registrado no painel em `surveyed_not_used`, com o motivo: nível de contig, N50 de scaffold 50.514 nt, cobertura 20×. Em tal montagem, a observação de um locus único não se distingue de fragmentação de contigs, e uma duplicação colapsada é mais provável que na montagem cromossômica de 75×, de modo que não poderia confirmar nem refutar uma observação de número de cópias.
- **Chamar dois loci de "o mesmo" quando suas extensões se sobrepõem.** Rejeitado: ver a decisão abaixo. Sobreposição em uma sequência é justamente o caso em que o método não distingue um locus de dois alinhamentos sobrepostos de uma repetição, logo é `INDETERMINADO`.

## Decisão

Aplicar o seguinte, nesta ordem, sem adaptar nenhum critério depois de ver resultados.

1. **Admissibilidade da montagem.** Um alvo de mapeamento deve ser uma montagem genômica pública de *Dalbulus maidis* (taxid 74065) com acesso versionado. Seu arquivo é declarado no painel de insumos com URL de origem, `sha256` e modo de verificação, e é verificado antes do uso. Além disso, o número de sequências, o comprimento total, o comprimento sem lacunas, o N50 de scaffold e o número de moléculas montadas declarados no painel são recomputados do arquivo a cada execução; uma discordância aborta a execução. Um hash sozinho prova que os bytes não mudaram, não que o arquivo é a montagem que o painel descreve.

2. **Consultas.** Uma consulta por dsRNase publicada: a CDS, derivada do transcrito Trinity dos âncoras do repositório como o maior ORF delimitado por stop, lido a partir da primeira metionina. As coordenadas de ORF da Tabela 1 publicada, o comprimento da CDS e o comprimento da proteína são declarados no painel, e a derivação é conferida contra eles; uma discordância aborta a execução. A consulta é somente a CDS, nunca o transcrito completo.

3. **Busca.** `blastn -task blastn -dust no -evalue 1e-5`, o conjunto de parâmetros de descoberta da ADR 0004, com `-max_target_seqs` acima da contagem de sequências da maior montagem declarada, de modo que o limite comprovadamente não possa truncar o resultado; a execução registra que a contagem observada de sujeitos ficou abaixo do limite. Sem `-max_hsps`: éxons são HSPs, e descartar HSPs descartaria a estrutura de éxons.

4. **Formação do locus.** HSPs de uma consulta em uma sequência e em uma fita formam um locus quando a distância genômica entre HSPs consecutivos é de no máximo 50.000 nt. Fitas nunca se fundem. Dentro de um locus, os HSPs são empilhados em ordem decrescente de escore em um bloco de alinhamento por éxon inferido; um bloco entra no empilhamento quando sobrepõe os blocos aceitos em no máximo 10 nucleotídeos de consulta e em nada no genoma.

5. **Faixa de relato.** Um locus é relatado quando cobre ao menos 50 % da CDS — o limiar de cobertura de descoberta da ADR 0004, deliberadamente amplo, que nada diz sobre identidade. Os loci relatados são classificados em faixas: `ASSIGNMENT_CRITERIA` quando a cobertura da consulta é de ao menos 90 % **e** a identidade sobre o alinhamento empilhado é de ao menos 98 %; caso contrário `RELATED`.

6. **Atribuição.** Uma CDS é atribuída a um locus (`DETERMINED`) somente quando **exatamente um** locus daquela montagem atende a `ASSIGNMENT_CRITERIA`. Zero loci dá `INDETERMINATE / NO_LOCUS_MEETS_ASSIGNMENT_CRITERIA`; dois ou mais dá `INDETERMINATE / MULTIPLE_LOCI_MEET_ASSIGNMENT_CRITERIA`. A contagem de loci em critérios de atribuição e a de loci relacionados são relatadas nos dois casos. Um locus nunca é escolhido por ranking: o de maior escore entre vários aprovados não é uma atribuição.

7. **Contiguidade e contexto repetitivo, relatados com todo locus e nunca omitidos.** A sequência em que o locus se encontra e seu papel (molécula montada versus sequência não localizada ou não posicionada), seu comprimento, a extensão do locus, o número de nucleotídeos de lacuna de montagem e de corridas de lacuna dentro da extensão, a distância da extensão à extremidade mais próxima da sequência, o número de outros loci da mesma consulta que atingem o limiar de 50 %, a colinearidade do empilhamento, os tamanhos de íntron inferidos, os nucleotídeos de CDS não alinhados em cada junção, e os terminais de dois nucleotídeos de cada íntron inferido com a contagem de pares canônicos `GT..AG`. Um par não canônico é relatado, nunca filtrado.

8. **Distinção, decidida par a par e separada da similaridade.** Dois loci atribuídos são `DETERMINED` distintos quando estão em sequências diferentes da montagem, ou em uma sequência com extensões não sobrepostas, caso em que a lacuna entre as extensões é relatada. São `INDETERMINATE / OVERLAPPING_SPANS_ON_ONE_SEQUENCE` quando as extensões se sobrepõem: é a configuração que tanto uma repetição quanto um locus verdadeiramente compartilhado produzem, e o método não as separa. Se qualquer um dos loci não estiver atribuído, o par é `INDETERMINATE / UNASSIGNED_LOCUS`.

9. **Contagem de loci para a CDS publicada de dsRNase-2.** Relatar o número de loci que atendem aos critérios de atribuição para a CDS publicada em cada montagem com as chaves `ONE_LOCUS_DETECTED`, `MULTIPLE_LOCI_DETECTED` e `NO_LOCUS_DETECTED`. A contagem se aplica à consulta publicada, cuja CDS coincide com a de `GITV01008430.1`. A origem genômica de `GITV01012450.1` permanece `não resolvida`.

10. **Haplótipo alternativo.** Quando houver um pseudo-haplótipo alternativo do mesmo biosample, ele é mapeado como segundo alvo independente, porque uma duplicação heterozigota colapsada em um pseudo-haplótipo pode estar resolvida no outro. Concordância entre os dois haplótipos fortalece uma observação de número de cópias; não a converte em demonstração, pois ambos derivam de um único indivíduo.

## Justificativa

Os limiares de 90 % de cobertura e 98 % de identidade separam os dois erros que importam aqui. Cobertura abaixo de 90 % significa que o locus não dá conta da CDS, que é a aparência de um locus parcial ou fragmentado; identidade abaixo de 98 % entre um transcrito publicado e a montagem de outro indivíduo da mesma espécie é mais divergência do que uma diferença alélica preveria, que é a aparência de um parálogo. Exigir os dois, e exigir unicidade em vez de maior escore, faz o método responder "existe exatamente um locus genômico que dá conta desta CDS" em lugar de "qual região tem o maior escore", e a segunda pergunta sempre tem resposta enquanto a primeira não.

A distância de 50.000 nt é deliberadamente generosa em relação aos comprimentos de íntron de insetos. A assimetria é intencional: um íntron maior que o limite parte um locus em dois loci parciais, cada um reprovando no limiar de cobertura e visível na saída como locus parcial, enquanto um limite pequeno demais esconderia a partição dentro de uma única chamada de aparência confiante.

Relatar contiguidade e contexto repetitivo com todo locus, como exige a regra 7, é o que mantém a regra 8 honesta. A tarefa que motivou este registro declara o risco diretamente: duas sequências que mapeiam em uma mesma região não estabelecem um mesmo locus se a região for repetitiva ou a montagem fragmentada. A medida de repetição para a consulta é a contagem de outros loci que a mesma CDS atinge no limiar de relato; a medida de fragmentação é o conteúdo de lacunas da extensão e a distância às extremidades da sequência. Ambas são computadas do insumo declarado a cada execução, de modo que um revisor nunca precisa aceitar a chamada de locus por confiança.

A regra 9 vincula a contagem à consulta e aos critérios declarados. A relação genômica entre os registros do TSA permanece em aberto.

## Consequências

- O NB01 ganha um comando reprodutível de mapeamento a loci, com insumos declarados e verificados por hash, critérios pré-registrados e um desfecho `INDETERMINADO` que é resultado, não falha.
- Os critérios são específicos de um mapeamento CDS-contra-genoma com empilhamento de HSPs. Não são critérios de identidade e não substituem a ADR 0003 nem a ADR 0004.
- A estrutura éxon/íntron relatada é `inferido/interpretado` e deve ser rotulada assim onde for reutilizada. Não é anotação de genes, e o repositório não ganha anotação com esta execução.
- O foco de revisão decorre da regra 7: uma chamada de locus deve ser julgada junto com suas colunas de contiguidade e repetição, não apenas por cobertura e identidade.
- Nada neste registro autoriza execução científica além do mapeamento declarado, e nada nele afeta a seleção de regiões do NB02, o NB03 ou os gates do NB04.

## Limitações

- O empilhamento de HSPs do BLASTn não é alinhamento splice-aware. Éxons menores que o comprimento efetivo de semente podem passar sem detecção, as coordenadas de junção são aproximadas dentro da sobreposição tolerada, e a estrutura inferida é evidência mais fraca do que daria um alinhador splice-aware ou uma anotação.
- O levantamento deste próprio registro consultou apenas o NCBI e não encontrou anotação de genes para nenhuma das montagens declaradas; não consultou o Ensembl, e não faz nenhuma afirmação sobre se uma anotação independente existia em algum lugar nessa época. Os alvos genômicos declarados do mapeamento eram os dois FASTAs de montagem; nenhum GFF3 foi declarado ou consultado. Uma rodada posterior nesta branch obteve e conferiu, pela primeira vez, uma anotação do Ensembl Genebuild do Ensembl AEGIS (conjunto de genes `2026_02`) para a montagem principal, `GCA_975739785.1`; o haplótipo alternativo, `GCA_975739835.1`, ainda não tem nenhuma conferida. A comparação contra essa anotação está registrada no adendo do [registro de execução](../runs/2026-11-15_nb01-dsrnase-locus-mapping.md#addendum-2026-11-15-comparison-against-the-ensembl-aegis-gene-annotation), não nos critérios desta ADR, que essa anotação não substitui por si só (ver a condição de falseamento abaixo).
- As duas montagens declaradas derivam de um único biosample (`SAMEA117578701`). As contagens de loci se referem a essas montagens. A variação populacional permanece em aberto.
- A execução detectou um locus para a CDS publicada de dsRNase-2 na montagem principal. A busca na montagem alternativa ficou sem locus detectado sob os parâmetros aplicados, deixando inconclusiva a comparação entre haplótipos. Uma duplicação colapsada pela montagem permanece possível.
- O limiar de 98 % de identidade pressupõe divergência alélica abaixo de 2 % entre os indivíduos sequenciados. Esse pressuposto não é calibrado para *D. maidis*.
- Os transcritos publicados e as montagens vêm de indivíduos e estudos diferentes; nenhuma afirmação sobre um mesmo indivíduo está disponível.

## O que esta decisão NÃO estabelece

- Não estabelece que qualquer chamada de locus esteja correta, que qualquer montagem esteja correta, nem que a estrutura éxon/íntron inferida seja a estrutura gênica verdadeira.
- A origem genômica de `GITV01012450.1` e sua relação com o locus detectado para a CDS publicada permanecem em aberto.
- Não estabelece identidade gênica, ortologia, paralogia, tamanho de família gênica nem número de cópias na espécie.
- Não estabelece nem toca em atividade enzimática, especificidade de substrato, expressão ou qualquer fenótipo. Nenhuma afirmação desse tipo é feita em qualquer parte do mapeamento.
- Não estabelece validade científica. Uma execução bem sucedida e um resultado reprodutível não são validade científica.

## Condições de falseamento / revisão

- Uma montagem anotada de *D. maidis*, ou uma com modelos gênicos sustentados por RNA-seq, substituiria a inferência por empilhamento de HSPs e é motivo para revisar as regras 4 e 7. **Parcialmente acionada:** uma rodada posterior nesta branch obteve e conferiu uma anotação do Ensembl Genebuild do Ensembl AEGIS para `GCA_975739785.1`, comparando-a contra os três loci inferidos (ver o adendo do registro de execução). Se essa anotação existia antes ou depois da escrita desta ADR não está estabelecido e não é afirmado; o que está documentado é a ordem em que este repositório a procurou e a usou. Este registro trata essa comparação como evidência corroborante, não como substituição: não revisa as regras 4 ou 7, não reexecuta nem substitui o empilhamento de HSPs, e a própria comparação não exigiu nenhum alinhador splice-aware. Revisar as regras 4 e 7 para usar a anotação diretamente, ou acrescentar um alinhador splice-aware, permanece postergado para uma rodada futura.
- Acrescentar um alinhador splice-aware ao ambiente declarado é motivo para revisar o método e reexaminar toda estrutura `inferido/interpretado`.
- Uma montagem de um segundo indivíduo em nível cromossômico é motivo para revisar a regra 9: o número de cópias poderia então ser comparado entre indivíduos.
- Evidência de profundidade de leituras sobre um locus atribuído é motivo para revisar a limitação de duplicação colapsada.
- Uma estimativa medida de divergência alélica em *D. maidis* é motivo para revisar o limiar de 98 % de identidade.
- Observar que uma montagem declarada foi substituída ou suprimida no NCBI é motivo para revisar o painel, não para relaxar a verificação.

## Notebook relacionado

`src/zeaguard/nb01_locus.py`

## Dataset / artefato relacionado

`data/reference/nb01_dsrnase_locus_panel.json`; saídas em `results/bioinformatics/nb01/mappings/dsrnase_locus_mapping/` (fora do versionamento, reprodutíveis a partir dos insumos declarados).

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não commitado`

## Proveniência

Registrado de forma contemporânea à implementação, na branch `feat/nb01-dsrnase-locus-mapping` cortada de `origin/master`. Evidências inspecionadas antes de fixar os critérios: os registros de taxonomia e de assembly do NCBI para o taxid 74065 e os relatórios do NCBI Datasets dos três acessos; ADR 0003, ADR 0004 e os três registros de execução do NB01 citados acima; `data/reference/target_anchor_sequences.fasta` e `data/reference/target_anchors.tsv`; `environment.yml` e o inventário de ferramentas do ambiente conda canônico. Os limiares da decisão foram escritos antes de qualquer alinhamento contra as montagens; o registro de execução declara o commit em que ocorreu a primeira execução completa.
