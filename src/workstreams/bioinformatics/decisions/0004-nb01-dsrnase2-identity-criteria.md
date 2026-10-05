# Title

Classify Dmai dsRNase-2 identity separately at accession, CDS, and protein level with evidence-integrating criteria

## Status

Proposed

## Date

2026-10-03

## Context / problem

[ADR 0003](0003-nb01-target-identity-resolution-policy.md) (Proposed) classified one number per target from a single BLASTn query: `AMBIGUOUS` for `dsRNase-2` (`GITV01012450.1` versus `GITV01008430.1`). That policy used `-max_hsps 1`, a coverage metric computed over the whole published cDNA (CDS plus flanking regions), and no HSP coordinates, strand, translation, or domain evidence. It therefore could not say whether two competing records differ in accession only, in CDS, or in protein, and its thresholds are recorded as unvalidated operational assumptions. The question that matters for the next ZeaGuard step (region selection for dsRNA) is not "which accession" but "which CDS and protein, and how certain".

This record does **not** modify ADR 0003. It adds separate criteria for a new investigation whose results are recorded in the [run record](../runs/2026-10-03_nb01-dsrnase2-identity.md).

## Question being decided

Which computational evidence is sufficient to assign `RESOLVED`, `AMBIGUOUS`, or `UNRESOLVED` independently to (a) the TSA accession, (b) the coding sequence, and (c) the protein sequence of Dmai dsRNase-2, and how is correspondence to the published sequence kept separate from biological identity?

## Evidence

1. Audit of ADR 0003 against the repository (`directly demonstrated`, see the table below).
2. Primary source: Dalaison Fuentes et al. 2023, Pestic. Biochem. Physiol. 196:105618 (DOI 10.1016/j.pestbp.2023.105618, PMID 37945254), Supplementary File S1 (`mmc1.pdf`), which provides for each dsRNase a predicted protein and the full Trinity transcript (no separate ORF nucleotide record).
3. Implementation: [nb01_dsrnase_investigation.py](../../../zeaguard/nb01_dsrnase_investigation.py) and [tests](../../../../tests/test_nb01_dsrnase_investigation.py).
4. Outputs: `results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/` (`decision.json`, `run_manifest.json`).

### Audit of the ADR 0003 rules

| ADR 0003 rule | Implemented now | Used in the 2026-09-11 run | Only proposed | Empirical support | Needs validation |
| --- | --- | --- | --- | --- | --- |
| Layer 1: exact header/alias match | yes (`find_direct_header_matches`) | yes, matched no anchor | no | none (cannot fire: TSA headers carry no Trinity identifiers) | not applicable here |
| Layer 2: complete published sequence contained in one TSA record | yes (`find_exact_sequence_matches`) | yes, matched no anchor | no | none | not applicable here |
| Layer 3: BLASTn `-task blastn -dust no -evalue 1e-5 -max_target_seqs 100 -max_hsps 1` | yes (`run_blastn`) | yes | parameters are operational | none recorded | yes; `-max_hsps 1` and the missing coordinates prevent union coverage and strand reporting |
| `RESOLVED_HIGH_CONFIDENCE`: identity >= 98 %, query coverage >= 95 %, e-value <= 1e-20, no competitor | yes (constants) | yes (BicC only) | thresholds are "agent selected" | none | yes |
| Competitive hit: bit score >= 95 % of top, identity within 1 point, coverage within 2 points | yes | yes (flagged dsRNase-2) | thresholds are "agent selected" | none | yes |
| `UNRESOLVED` on any failed threshold | yes | yes (dsRNase-1, dsRNase-3) | n/a | none | yes |

This investigation adds one empirical observation (`derived/computed`, see the run record): the 95 % query-coverage threshold, computed over the whole published cDNA, was failed by dsRNase-1 (85 %) although the full published CDS is covered at 100 % by two TSA records, because coverage is dominated by the length of flanking regions present in the published transcript and absent from the TSA record. The ADR 0003 threshold was not changed.

## Evidence classification

Same four categories as ADR 0003. Every claim in `decision.json` carries one of `OBSERVATION` (maps to `directly demonstrated` or `derived/computed`), `INFERENCE` (`inferred/interpreted`), or `HYPOTHESIS` (`unresolved` until tested). A hypothesis is never promoted to an observation without new evidence. All thresholds below are `operational assumption` pending review; none has bibliographic or empirical calibration.

## Alternatives considered

`not recoverable` for any historical deliberation. Contemporaneous alternatives named in the task brief: a single combined label for all three levels (rejected: the levels can legitimately disagree), picking the highest-scoring BLAST hit (rejected: BLAST rank is not a biological classification), using a phylogeny by default (deferred: only if direct comparison cannot separate paralogs).

## Decision

Apply the following, in this order, without adapting any criterion after seeing results.

1. **Discovery set** (breadth only, says nothing about identity): historical candidates plus every TSA record with non-redundant union query coverage >= 50 % and e-value <= 1e-5 in BLASTn (nucleotide references, `-task blastn -dust no -evalue 1e-5 -max_target_seqs 500`, no `-max_hsps`) or TBLASTN (published proteins, `-evalue 1e-5 -max_target_seqs 500 -db_gencode 1 -seg no`). Union coverage is computed per `(query, subject, strand)` on 1-based inclusive intervals; HSPs on opposite strands are never merged.
2. **ORF / CDS**: all stop-delimited reading segments >= 30 aa in six frames are listed. A segment is homology-supported when its best local BLOSUM62 alignment (gap 11/1) to a published protein scores >= 80. The primary segment is the best supported one (not the longest). The CDS starts at the in-frame Met aligned to residue 1 of the published protein; N-terminal completeness is judged from converging evidence (published N-terminus aligned, Met present, upstream sequence, transcript end) and the absence of an upstream stop is never read as truncation.
3. **Identity-competing candidate for dsRNase-2**: the published dsRNase-2 protein must be the candidate's best protein match (identity over the published length; ties count) and be covered >= 50 %. Paralog separation uses protein identity and coverage, not BLAST rank.
4. **Published-reference correspondence** (`UNIQUE`, `TIED`, `NO_CONFIDENT_MATCH`): `UNIQUE` or `TIED` among candidates whose CDS and protein equal the published ones exactly; otherwise the best by (CDS indels, amino-acid-changing substitutions, fixed substitutions, IUPAC codes) among complete candidates with protein identity >= 95 %; `NO_CONFIDENT_MATCH` if none qualifies. Ties are kept. This is a statement about similarity to a published sequence, not about biological identity.
5. **Accession**: `RESOLVED` only if exactly one competing candidate remains after exclusions. A record is excluded only for a structural reason (best match is another paralog, or incomplete CDS). A difference from the published sequence (substitution, IUPAC code, indel-free variant) is not an exclusion: it can be an allele, a consensus-coding artefact, or redundancy. `AMBIGUOUS` if more than one remains; `UNRESOLVED` if none.
6. **CDS**: `RESOLVED` if all remaining records share one identical CDS (sha256) or one CDS is uniquely supported with the alternatives justifiably excluded; `AMBIGUOUS` if two or more distinct plausible CDS remain; `UNRESOLVED` if no complete CDS exists.
7. **Protein** (strict policy): `RESOLVED` only when every biologically compatible record supports the same protein sequence, or when discriminating evidence (for example reads meeting rule 8) eliminates the alternatives. **A protein containing an undetermined residue with more than one plausible amino-acid translation remains `AMBIGUOUS`, even when one of the possibilities coincides with the published sequence. Compatibility with the reference is not resolution of the sequence.** Three statements are kept apart in every artefact: `published_reference_correspondence` (similarity to the published sequence), protein compatibility with the published protein (yes/no per record) and protein sequence resolved (yes/no). An IUPAC symbol is uncertainty, not a biological substitution, and a record that carries one is not thereby classified as biologically different or incorrect. Case in this investigation: `GITV01012450.1` has `ARA` at residue 117 (AAA = K, AGA = R); the published residue R remains compatible and K remains possible, so `published_protein_compatible = yes` and `protein_sequence_resolved = no`.
8. **Reads** (used only for a registered discriminating question, hypothesis written before download): for each variable CDS site, count the base between exact 16-nt anchors on both strands. A site is informative with >= 20 reads; an allele is supported with >= 5 reads and >= 5 % of informative reads; both alleles supported means allelic variation is supported at that site. Reads never select an accession.
9. **PF01223**: HMMER `hmmsearch` with the Pfam PF01223 profile, curated gathering threshold (GA) recorded; domain presence supports family membership only.
10. **Signal peptide**: N-terminal completeness is assessed first; a truncated N-terminus is `NOT_ASSESSABLE_DUE_TO_N_TERMINAL_INCOMPLETENESS`. Tool order: SignalP (if licensed and installed), then DeepSig, else `NOT_ASSESSED`. The result is complementary and never decides between accessions.
11. **Overall label** keeps the three levels visible (for example `AMBIGUOUS_AT_ACCESSION_LEVEL`) and is never reduced to one word.

## Rationale

Recoverable rationale: the three levels answer different downstream questions, and ADR 0003's single label hid which of them is uncertain. Excluding records only for structural reasons avoids converting polymorphism or assembly consensus coding into a false negative. Scientific justification for the numeric thresholds is `not recoverable`; they are operational assumptions.

## Consequences

Outputs are deterministic under the declared inputs and tool versions (verified by a second run into a scratch directory). The investigation can end `AMBIGUOUS` at one level while `RESOLVED` at another, which is a valid scientific result. A later validation can change thresholds without changing the structure.

## Limitations

Thresholds (50 % discovery coverage, local score 80, 50 % reference coverage, 20 / 5 / 5 % read rules, 95 % protein identity for correspondence) are not calibrated against independently confirmed positives or negatives. The published sequence and the TSA come from different assemblies and possibly different individuals. IUPAC codes in a TSA record cannot be resolved from the assembly alone. DeepSig was used, not SignalP, and its sensitivity may differ.

## What this decision does NOT establish

It does not establish biological identity, absence of other loci, that a candidate not matching the published sequence is invalid, or that any threshold is correct. `RESOLVED` at CDS or protein level does not resolve the accession.

## Falsification / revision conditions

Revise if an independent source (genome, amplicon sequencing, a validated annotation) contradicts a classification, if a benchmark supports different thresholds, if a candidate is excluded by a criterion that is later shown to retain true dsRNase-2 records, or if the primary TSA or the published sequences change.

## Related notebook

[Notebook 01, Stage 4](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Related dataset / artifact

[Investigation results](../../../../results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/decision.json) (not tracked by Git, see the run record for hashes), [dataset manifest](../../../../data/reference/manifest.json)

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed` (work on branch `feat/nb01-dsrnase2-identity-resolution`, base `0effa52`).

## Provenance

Written on 2026-10-03 **after** the comparison tables of this investigation had been inspected; it is therefore not a pre-registration of the whole policy. What was fixed in code before the corresponding outputs were inspected: the discovery thresholds (rule 1), the ORF-support score and the competing-candidate coverage (rules 2-3), and the read-support hypothesis and rules (rule 8, `raw/read_hypothesis_preregistration.md`, written before any read was downloaded). The structure of the accession / CDS / protein criteria (rules 5-7) was stated in the investigation plan before the searches, but their exact implementation (the treatment of IUPAC-ambiguous codons as keeping an alternative protein plausible, the correspondence ranking, and the rule that variant-level differences do not exclude a record) was written after the comparison tables had been seen. Two method corrections were also made after inspection and are recorded as deviations in the run record: IUPAC-aware translation and end anchoring of semi-global alignments. No numeric threshold was changed after results were seen. The strict protein policy (rule 7) was adopted by instruction of the investigator on 2026-10-05, after a molecular checkpoint in which an alternative, more permissive reading (published residue among the possibilities counts as resolved) had been evaluated and rejected. Remains `Proposed` because no human approval or empirical calibration of the thresholds is recorded.

# Versão em PTBR

# Título

Classificar a identidade de Dmai dsRNase-2 separadamente em accession, CDS e proteína com critérios que integram evidências

## Estado

Proposed

## Data

2026-10-03

## Contexto / problema

O [ADR 0003](0003-nb01-target-identity-resolution-policy.md) (Proposed) atribuía um único rótulo por alvo a partir de uma consulta BLASTn: `AMBIGUOUS` para `dsRNase-2` (`GITV01012450.1` versus `GITV01008430.1`). Essa política usou `-max_hsps 1`, uma cobertura calculada sobre todo o cDNA publicado (CDS mais regiões flanqueadoras) e nenhuma coordenada de HSP, strand, tradução ou evidência de domínio. Ela não conseguia dizer se dois registros concorrentes diferem apenas no accession, na CDS ou na proteína, e seus limiares estão registrados como pressupostos operacionais não validados. A pergunta relevante para a próxima etapa do ZeaGuard (seleção de regiões para dsRNA) não é "qual accession", e sim "qual CDS e proteína, e com que certeza".

Este registro **não** modifica o ADR 0003. Ele acrescenta critérios separados, fixados antes de os resultados de busca da investigação de 2026-10-03 serem inspecionados, cujos resultados estão no [run record](../runs/2026-10-03_nb01-dsrnase2-identity.md).

## Questão sendo decidida

Quais evidências computacionais bastam para atribuir `RESOLVED`, `AMBIGUOUS` ou `UNRESOLVED` independentemente ao (a) accession TSA, (b) sequência codificante e (c) sequência proteica de Dmai dsRNase-2, e como manter a correspondência com a sequência publicada separada da identidade biológica?

## Evidências

1. Auditoria do ADR 0003 contra o repositório (`diretamente demonstrado`, ver a tabela da versão em inglês).
2. Fonte primária: Dalaison Fuentes et al. 2023, Pestic. Biochem. Physiol. 196:105618 (DOI 10.1016/j.pestbp.2023.105618, PMID 37945254), Supplementary File S1 (`mmc1.pdf`), que fornece para cada dsRNase uma proteína predita e o transcrito Trinity completo (sem registro nucleotídico separado da ORF).
3. Implementação: [nb01_dsrnase_investigation.py](../../../zeaguard/nb01_dsrnase_investigation.py) e [testes](../../../../tests/test_nb01_dsrnase_investigation.py).
4. Saídas: `results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/` (`decision.json`, `run_manifest.json`).

A observação empírica nova (`derivado/computado`): o limiar de 95 % de cobertura da query, calculado sobre o cDNA publicado inteiro, foi reprovado pela dsRNase-1 (85 %) embora a CDS publicada completa esteja coberta a 100 % por dois registros TSA, porque a cobertura é dominada pelas regiões flanqueadoras presentes no transcrito publicado e ausentes do registro TSA. O limiar do ADR 0003 não foi alterado.

## Classificação das evidências

As mesmas quatro categorias do ADR 0003. Cada afirmação em `decision.json` leva `OBSERVATION` (`diretamente demonstrado` ou `derivado/computado`), `INFERENCE` (`inferido/interpretado`) ou `HYPOTHESIS` (`não resolvido` até ser testada). Uma hipótese nunca é promovida a observação sem nova evidência. Todos os limiares são `pressuposto operacional` pendente de revisão.

## Alternativas consideradas

`não recuperável` para qualquer deliberação histórica. Alternativas explicitadas no pedido: um único rótulo combinado (rejeitada: os níveis podem divergir legitimamente), escolher o hit de maior score do BLAST (rejeitada: a ordenação do BLAST não é classificação biológica), usar filogenia por padrão (adiada: somente se a comparação direta não separar parálogos).

## Decisão

Aplicar, nesta ordem, sem adaptar nenhum critério após ver os resultados.

1. **Conjunto de descoberta** (apenas amplitude, sem decidir identidade): candidatos históricos mais todo registro TSA com cobertura não redundante (união de intervalos) >= 50 % da query e e-value <= 1e-5 em BLASTn ou TBLASTN, com a cobertura calculada por `(query, subject, strand)` em intervalos 1-based inclusivos e sem unir HSPs de strands opostos.
2. **ORF / CDS**: listar todos os segmentos entre stops >= 30 aa nas seis fases; um segmento tem suporte de homologia quando o melhor alinhamento local BLOSUM62 com uma proteína publicada tem score >= 80; a ORF primária é a de melhor suporte (não a maior); a CDS começa na Met em fase alinhada ao resíduo 1 da proteína publicada; a completude N-terminal usa evidências convergentes e a ausência de stop a montante nunca é lida como truncamento.
3. **Candidato competidor à identidade de dsRNase-2**: a proteína publicada de dsRNase-2 deve ser a melhor correspondência proteica do candidato (empates contam) com cobertura >= 50 %.
4. **Correspondência com a referência publicada** (`UNIQUE`, `TIED`, `NO_CONFIDENT_MATCH`): empates são mantidos; trata-se de similaridade com uma sequência publicada, não de identidade biológica.
5. **Accession**: `RESOLVED` somente se restar exatamente um competidor após exclusões; exclusão apenas por razão estrutural (melhor correspondência é outro parálogo, ou CDS incompleta). Diferença em relação à sequência publicada não é critério de exclusão.
6. **CDS**: `RESOLVED` se todos os registros restantes compartilham a mesma CDS (sha256) ou uma CDS tem suporte único com alternativas justificadamente excluídas; `AMBIGUOUS` se restam duas ou mais; `UNRESOLVED` se nenhuma é completa.
7. **Proteína** (política estrita): `RESOLVED` somente quando todos os registros biologicamente compatíveis sustentam a mesma sequência proteica, ou quando evidência discriminante (por exemplo reads que cumpram a regra 8) elimina as alternativas. **Uma proteína com um resíduo indeterminado e mais de uma tradução aminoacídica plausível permanece `AMBIGUOUS`, mesmo quando uma das possibilidades coincide com a sequência publicada. Compatibilidade com a referência não equivale a resolução da sequência.** Três afirmações permanecem separadas em todos os artefatos: `published_reference_correspondence` (similaridade com a sequência publicada), compatibilidade da proteína com a publicada (sim/não por registro) e sequência proteica resolvida (sim/não). Um símbolo IUPAC é incerteza, não substituição biológica, e um registro que o contém não é classificado por isso como biologicamente diferente ou incorreto. Caso desta investigação: `GITV01012450.1` tem `ARA` no resíduo 117 (AAA = K, AGA = R); o R publicado permanece compatível e K permanece possível, logo `published_protein_compatible = sim` e `protein_sequence_resolved = não`.
8. **Reads** (somente para pergunta discriminante registrada antes do download): contagem da base entre âncoras exatas de 16 nt nas duas fitas; sítio informativo com >= 20 reads; alelo suportado com >= 5 reads e >= 5 %; reads nunca selecionam um accession.
9. **PF01223**: HMMER com o perfil Pfam e limiar de corte curado (GA) registrado; o domínio apoia pertencimento à família, não resolve o membro.
10. **Peptídeo sinal**: avaliar a completude N-terminal antes; N-terminal truncado resulta em `NOT_ASSESSABLE_DUE_TO_N_TERMINAL_INCOMPLETENESS`; ordem das ferramentas: SignalP, depois DeepSig, senão `NOT_ASSESSED`; evidência complementar apenas.
11. **Rótulo geral** preserva os três níveis (por exemplo `AMBIGUOUS_AT_ACCESSION_LEVEL`).

## Justificativa

A justificativa recuperável: os três níveis respondem perguntas diferentes e o rótulo único do ADR 0003 ocultava qual nível é incerto. Excluir registros apenas por razão estrutural evita transformar polimorfismo ou codificação consenso em falso negativo. A justificativa científica dos limiares é `não recuperável`.

## Consequências

Saídas determinísticas sob os inputs e versões de ferramentas declarados (verificado por segunda execução em diretório temporário). A investigação pode terminar `AMBIGUOUS` em um nível e `RESOLVED` em outro, o que é um resultado válido.

## Limitações

Os limiares não foram calibrados com positivos e negativos confirmados. A sequência publicada e o TSA vêm de montagens diferentes e possivelmente de indivíduos diferentes. Códigos IUPAC de um registro TSA não podem ser resolvidos só pela montagem. Foi usado DeepSig, não SignalP.

## O que esta decisão NÃO estabelece

Não estabelece identidade biológica, ausência de outros loci, que um candidato que não reproduz a sequência publicada seja inválido, nem que algum limiar esteja correto. `RESOLVED` em CDS ou proteína não resolve o accession.

## Condições de falseamento / revisão

Revisar se uma fonte independente (genoma, sequenciamento de amplicon, anotação validada) contradisser uma classificação, se um benchmark sustentar outros limiares, se um critério de exclusão se mostrar capaz de excluir registros verdadeiros de dsRNase-2, ou se o TSA primário ou as sequências publicadas mudarem.

## Notebook relacionado

[Notebook 01, Stage 4](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Dataset / artefato relacionado

[Resultados da investigação](../../../../results/bioinformatics/nb01/investigations/2026-10-03_dsrnase2_identity/decision.json) (não rastreados pelo Git, ver o run record para os hashes)

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não commitado` (trabalho na branch `feat/nb01-dsrnase2-identity-resolution`, base `0effa52`).

## Proveniência

Escrito em 2026-10-03 **depois** de as tabelas de comparação desta investigação terem sido inspecionadas; portanto não é um pré-registro de toda a política. Foi fixado no código antes de as saídas correspondentes serem inspecionadas: os limiares de descoberta (regra 1), o score de suporte de ORF e a cobertura do candidato competidor (regras 2-3) e a hipótese e as regras de suporte por reads (regra 8, `raw/read_hypothesis_preregistration.md`, escrita antes de qualquer download de reads). A estrutura dos critérios de accession / CDS / proteína (regras 5-7) foi enunciada no plano antes das buscas, mas sua implementação exata (tratamento de códons IUPAC ambíguos como mantendo uma proteína alternativa plausível, ordenação da correspondência e a regra de que diferenças em nível de variante não excluem um registro) foi escrita depois de as tabelas terem sido vistas. Duas correções de método também foram feitas após a inspeção e estão como desvios no run record: tradução com resolução IUPAC e ancoragem das extremidades dos alinhamentos semiglobais. Nenhum limiar numérico foi alterado após ver resultados. A política estrita para proteína (regra 7) foi adotada por instrução do investigador em 2026-10-05, depois de um checkpoint molecular em que uma leitura alternativa, mais permissiva (aminoácido publicado entre as possibilidades conta como resolvido), foi avaliada e rejeitada. Permanece `Proposed` porque não há aprovação humana nem calibração empírica dos limiares.
