# Title

Select candidate regions for a nominal 400 nt dsRNA against Dmai dsRNase-2 under a pre-registered criteria registry, with a published 330 nt benchmark and a mandatory intraspecies review

## Status

Proposed

## Date

2026-10-05

## Context / problem

NB01 closed with an operational reference for Dmai dsRNase-2 (`GITV01008430.1`, correspondence `UNIQUE`) while accession, CDS and protein remain `AMBIGUOUS` ([ADR 0004](0004-nb01-dsrnase2-identity-criteria.md)). NB02 must propose regions of the CDS for a future dsRNA. The risk is not computational: it is false precision. There are no validated weights, no validated cross-silencing threshold for *D. maidis*, no transferable siRNA efficacy predictor, and no controlled comparison of 5', central and 3' regions, so any rule that looks quantitative must either rest on evidence or be declared a convention, and must be fixed before candidate rankings are visible.

This record does not modify ADR 0004 and does not decide the molecular architecture of the construct.

## Question being decided

Which policy governs the selection of candidate regions (interval and length) of the operational dsRNase-2 CDS, and how are the published benchmark, known variants, specificity and the Wet Lab hand-off treated?

## Evidence

1. [Criteria registry](../../../../config/nb02_design_criteria.yaml) (pre-registered; every criterion has an evidence category, roles, what it may influence and `evidence_refs`).
2. [Operational reference pin](../../../../data/reference/nb01_dsrnase2_operational_reference.json), re-derived from the hash-pinned TSA by [nb02_reference.py](../../../zeaguard/nb02_reference.py) (CDS sha256 `bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7`; seven known variable CDS positions 9, 30, 219, 312, 350, 816, 1272).
3. Published benchmark: Dalaison-Fuentes et al. 2023 (DOI 10.1016/j.pestbp.2023.105618). The dsRNase-2 primers of Supplementary Table S1 map exactly to CDS 814-1143 (330 nt, sha256 `97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179`). Two provenance layers are kept apart: `benchmark_sequence_verification = VERIFIED_FROM_SUPPLEMENT_AND_REFERENCE` (primers, span, sha256, T7-tail amplicon lengths, variant 816 and identity with the published cDNA, recomputed by `verify_reference`) and `experimental_protocol_verification = PROJECT_PROVIDED_NOT_AGENT_VERIFIED` (the protocols `INJECTION_PRECONDITIONING` and `ORAL_COFEEDING` and the Results 3.4 endpoints were supplied by the project with the locators Methods 2.4, 2.5.1, 2.5.2 and Results 3.4; the main text was **not** retrievable at CP1). The protocols are stored unchanged; promotion of the second layer requires reading the main text and an explicit commit.
4. Literature checked at abstract level: Bolognesi 2012, Bachman 2013, Whyard 2009, Miller 2012, dsRIP 2025. Three project reviews (position, specificity, length and architecture) are incorporated as supplied conclusions whose citations were not provided.
5. [Policy kernel and registry validation](../../../zeaguard/nb02_criteria.py) and its [tests](../../../../tests/test_nb02_criteria.py).

## Evidence classification

Same four categories as ADR 0003/0004. In the registry, `EVIDENCE_BACKED`, `TOOL_DERIVED`, `PROJECT_CONVENTION` and `OPERATIONAL_ASSUMPTION` classify criteria; an operational assumption is never described as a validated biological rule.

1. `directly demonstrated`: hashes, the seven variants and the benchmark interval re-derived from the TSA; the primer sequences and amplicon lengths of Table S1.
2. `derived/computed`: the pin, the coordinates, the policy kernel results on synthetic data.
3. `inferred/interpreted`: the transferability of the 21 nt unit, the 60 bp floor and the position argument to *D. maidis*; the protocol facts supplied by the project.
4. `unresolved`: the optimal length, any cross-silencing threshold, the effect of position, the nature of the two accessions, the main-text statements of the benchmark.

## Alternatives considered

A composite score with weights (rejected: no defensible weights, false precision). A hard filter on E-value or on a shared 19/21-mer (rejected: E-values depend on database size, query size and scoring, and 19/21 nt are not a universal off-target cutoff). Normalising specificity by length (rejected: a fixed-size homology is diluted in longer windows). Using the TSA background as a decisional group (rejected: a permissive BLAST yields many incidental HSPs and would give them the structural weight of a paralog hit). A pre-registered maximum overlap between recommended regions (rejected: no evidence for a value).

## Decision

1. **Operational reference and contract.** `GITV01008430.1` is the operational reference; this is not a claim of unique biological identity and `GITV01012450.1` is not treated as incorrect. NB02 consumes a versioned pin and re-derives it from the TSA; the gitignored NB01 table is only a cross-check.
2. **Region, length and architecture are separate variables.** NB02 selects region and length. Linear, hairpin, protected-end or other architectures, primers, promoters, loops, terminators, restriction sites and codon optimisation belong to the Wet Lab after the shortlist.
3. **Pre-registration.** The criteria registry is committed before any candidate window exists; later changes are dated amendments, never silent edits.
4. **Length.** The plausible space is 300-500 nt. 400 nt is a `PROJECT_CONVENTION` (Wet Lab nominal, centre of the range), not a biological optimum. Specificity is compared only within a length stratum: 400 nt (ranking), 330 nt (benchmark comparator), 300 and 500 nt (sensitivity).
5. **Published benchmark.** The 330 nt fragment is the `PUBLISHED_EXPERIMENTAL_BENCHMARK` of a reference set. It appears in every table, is evaluated with the same criteria, never counts as a recommended candidate, carries no efficacy score (the co-feeding design also delivers BicC), and the two protocols are never merged.
6. **Specificity.** Evidence (clipped BLAST alignment metrics) is separated from interpretation and decision. Decisional groups are PARALOG and CO_TARGET, built from biological units fixed before the first BLAST: DSRNASE1 (`GITV01001583.1`, `GITV01002042.1`, `GITV01003945.1` and the published cDNA), DSRNASE3 (the published cDNA) and BICC (the published cDNA and `GITV01000968.1`, the NB01 high-confidence TSA record of BicC, which therefore never appears in OTHER_TRANSCRIPT). Evidence is clipped to the candidate and aggregated within a unit (longest exact match = maximum, covered nt = union of query positions so redundant records never add, best local identity = maximum reported with the aligned nt of the HSP that provided it, which is not a Pareto axis); units are never pooled. PARALOG compares the DSRNASE1 and DSRNASE3 vectors jointly, so a trade-off between them is a tie. Candidates are compared by Pareto dominance, with ties preserved. There is no hard filter on E-value, 19-mer or 21-mer. **OTHER_TRANSCRIPT** (the rest of the *D. maidis* TSA) is a descriptor with a mandatory pre-recommendation manual review: it does not enter the vector, the Pareto order, the cell signature or the primary ordering, but no candidate can be recommended without a versioned `APPROVED` decision on its hits against the complete TSA; a strong concern (`STRONG_INTRASPECIES_SPECIFICITY_CONCERN`, with justification) excludes the candidate after review and selection moves to the next eligible candidate.
7. **No composite score, position as descriptor.** Prioritisation is lexicographic (structure, specificity, variants), ties are explicit, and the 5'/central/3' position is a descriptor that affects neither cells nor ranking.

## Rationale

Recoverable rationale: each rule is either backed by the evidence recorded in the registry or declared a convention, and each convention is bounded so that it cannot silently act as a biological threshold. The mandatory review preserves intraspecies specificity without letting an unspecific background define the structure of the analysis.

## Consequences

The recommended shortlist is produced iteratively: a provisional candidate is ordered by decisive evidence, its complete-TSA hits are reviewed by a person and recorded in `config/nb02_manual_review_decisions.tsv`, and only then can it be recommended. Results depend on a person's reviewed decisions, which are versioned with the hash of the reviewed evidence.

## Limitations

The 21 nt unit, the 60 bp floor and the benchmark generalisation come from other systems or from a design that delivers two dsRNAs. Thresholds are conventions where they exist. The main text of the benchmark article was not read by the agent (`experimental_protocol_verification = PROJECT_PROVIDED_NOT_AGENT_VERIFIED`). The 60 nt floor (C03) is redundant given the 300-500 nt range (C02) and affects no NB02 candidate. The two TSA accessions may be one locus or two.

## What this decision does NOT establish

It does not establish biological efficacy of any region, an optimal length, that 5' or 3' regions differ, that absence of homology is safety, or the identity of the dsRNase-2 locus.

## Falsification / revision conditions

Revise if the main text of the benchmark article contradicts the supplied protocol facts, if validated data support a cross-silencing criterion or length optimum for *D. maidis*, if the Wet Lab documents a real synthesis or cloning constraint, or if NB01 identity decisions change.

## Related notebook

Not applicable at this checkpoint (the NB02 notebook is created in a later checkpoint).

## Related dataset / artifact

[Pin](../../../../data/reference/nb01_dsrnase2_operational_reference.json), [criteria registry](../../../../config/nb02_design_criteria.yaml), [decision file](../../../../config/nb02_manual_review_decisions.tsv).

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed to master` (work on branch `feat/nb02-dsrnase2-dsrna-candidate-regions`, base `9e0a7a2`).

## Provenance

Written at checkpoint 1, before any candidate window, specificity search or ranking was produced. The policy was refined over several review rounds of the plan; the benchmark protocol facts and the three literature-review conclusions were supplied by the project and are not independently verified here.

# Versão em PTBR

# Título

Selecionar regiões candidatas para um dsRNA nominal de 400 nt contra Dmai dsRNase-2 com registro de critérios pré-registrado, benchmark publicado de 330 nt e revisão intraespécie obrigatória

## Estado

Proposed

## Data

2026-10-05

## Contexto / problema

O NB01 terminou com uma referência operacional para Dmai dsRNase-2 (`GITV01008430.1`, correspondência `UNIQUE`) enquanto accession, CDS e proteína permanecem `AMBIGUOUS` ([ADR 0004](0004-nb01-dsrnase2-identity-criteria.md)). O NB02 deve propor regiões da CDS para um futuro dsRNA. O risco é a falsa precisão: não há pesos validados, limiar de cross-silenciamento validado para *D. maidis*, preditor de eficácia de siRNA transferível, nem comparação controlada entre regiões 5', centrais e 3'; toda regra com aparência quantitativa precisa ou ter evidência ou ser declarada convenção, e fixada antes de os rankings serem visíveis.

Este registro não modifica o ADR 0004 e não decide a arquitetura molecular do construto.

## Questão sendo decidida

Qual política governa a seleção de regiões candidatas (intervalo e comprimento) da CDS operacional de dsRNase-2, e como são tratados o benchmark publicado, as variantes conhecidas, a especificidade e a entrega ao Wet Lab?

## Evidências

1. [Registro de critérios](../../../../config/nb02_design_criteria.yaml) (pré-registrado; cada critério tem categoria de evidência, papéis, o que pode influenciar e `evidence_refs`).
2. [Pin da referência operacional](../../../../data/reference/nb01_dsrnase2_operational_reference.json), rederivado do TSA com hash fixado por [nb02_reference.py](../../../zeaguard/nb02_reference.py) (sha256 da CDS `bf853267151d1c1a43ca687feb7cea7857ff5c651c5546cba721d8b7647d36d7`; sete posições variáveis conhecidas da CDS: 9, 30, 219, 312, 350, 816, 1272).
3. Benchmark publicado: Dalaison-Fuentes et al. 2023 (DOI 10.1016/j.pestbp.2023.105618). Os primers de dsRNase-2 da Tabela Suplementar S1 mapeiam exatamente na CDS 814-1143 (330 nt, sha256 `97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179`). Duas camadas de proveniência ficam separadas: `benchmark_sequence_verification = VERIFIED_FROM_SUPPLEMENT_AND_REFERENCE` (primers, intervalo, sha256, comprimentos de amplicon com caudas T7, variante 816 e identidade com o cDNA publicado, recalculados por `verify_reference`) e `experimental_protocol_verification = PROJECT_PROVIDED_NOT_AGENT_VERIFIED` (os protocolos `INJECTION_PRECONDITIONING` e `ORAL_COFEEDING` e os endpoints de Results 3.4 foram fornecidos pelo projeto com os localizadores Methods 2.4, 2.5.1, 2.5.2 e Results 3.4; o texto principal **não** pôde ser recuperado no CP1). Os protocolos são armazenados sem alteração; promover a segunda camada exige ler o texto principal e um commit explícito.
4. Literatura conferida no nível do resumo: Bolognesi 2012, Bachman 2013, Whyard 2009, Miller 2012, dsRIP 2025. Três revisões do projeto (posição, especificidade, comprimento e arquitetura) entram como conclusões fornecidas, sem citações.
5. [Kernel de política e validação do registro](../../../zeaguard/nb02_criteria.py) e seus [testes](../../../../tests/test_nb02_criteria.py).

## Classificação das evidências

As mesmas quatro categorias dos ADR 0003/0004. No registro, `EVIDENCE_BACKED`, `TOOL_DERIVED`, `PROJECT_CONVENTION` e `OPERATIONAL_ASSUMPTION` classificam critérios; um pressuposto operacional nunca é descrito como regra biológica validada.

1. `diretamente demonstrado`: hashes, as sete variantes e o intervalo do benchmark rederivados do TSA; sequências dos primers e comprimentos de amplicon da Tabela S1.
2. `derivado/computado`: o pin, as coordenadas, os resultados do kernel de política em dados sintéticos.
3. `inferido/interpretado`: a transferibilidade da unidade de 21 nt, do piso de 60 pb e do argumento de posição para *D. maidis*; os fatos de protocolo fornecidos pelo projeto.
4. `não resolvido`: o comprimento ótimo, qualquer limiar de cross-silenciamento, o efeito da posição, a natureza dos dois accessions, as afirmações do texto principal do benchmark.

## Alternativas consideradas

Score composto com pesos (rejeitada: sem pesos defensáveis, falsa precisão). Filtro duro por E-value ou por 19/21-mer compartilhado (rejeitada: o E-value depende do tamanho do banco, da query e do scoring, e 19/21 nt não são limiar universal de off-target). Normalizar especificidade por comprimento (rejeitada: homologia de tamanho fixo é diluída em janelas maiores). Usar o fundo do TSA como grupo decisório (rejeitada: BLAST permissivo gera muitos HSPs incidentais e lhes daria o peso estrutural de um hit em parálogo). Sobreposição máxima pré-registrada entre regiões recomendadas (rejeitada: sem evidência para um valor).

## Decisão

1. **Referência operacional e contrato.** `GITV01008430.1` é a referência operacional; isso não é afirmação de identidade biológica única, e `GITV01012450.1` não é tratado como incorreto. O NB02 consome um pin versionado e o rederiva do TSA; a tabela gitignored do NB01 é só conferência.
2. **Região, comprimento e arquitetura são variáveis separadas.** O NB02 seleciona região e comprimento. Arquiteturas linear, hairpin, de extremidades protegidas ou outras, primers, promotores, loops, terminadores, sítios de restrição e otimização de códons pertencem ao Wet Lab depois da shortlist.
3. **Pré-registro.** O registro de critérios é commitado antes de existir qualquer janela candidata; mudanças posteriores são emendas datadas, nunca edições silenciosas.
4. **Comprimento.** O espaço plausível é 300-500 nt. 400 nt é `PROJECT_CONVENTION` (nominal do Wet Lab, centro do intervalo), não ótimo biológico. Especificidade só é comparada dentro de um estrato de comprimento: 400 nt (ranking), 330 nt (comparador do benchmark), 300 e 500 nt (sensibilidade).
5. **Benchmark publicado.** O fragmento de 330 nt é o `PUBLISHED_EXPERIMENTAL_BENCHMARK` de um conjunto de referência. Aparece em todas as tabelas, é avaliado pelos mesmos critérios, nunca conta como candidato recomendado, não recebe score de eficácia (o co-feeding também entrega BicC) e os dois protocolos nunca são fundidos.
6. **Especificidade.** A evidência (métricas recortadas de alinhamentos BLAST) é separada da interpretação e da decisão. Os grupos decisórios são PARALOG e CO_TARGET, construídos a partir de unidades biológicas fixadas antes do primeiro BLAST: DSRNASE1 (`GITV01001583.1`, `GITV01002042.1`, `GITV01003945.1` e o cDNA publicado), DSRNASE3 (o cDNA publicado) e BICC (o cDNA publicado e `GITV01000968.1`, o registro TSA de alta confiança do BicC no NB01, que portanto nunca aparece em OTHER_TRANSCRIPT). A evidência é recortada ao candidato e agregada dentro da unidade (maior trecho exato = máximo, nt cobertos = união das posições da query, de modo que registros redundantes nunca somam, melhor identidade local = máximo reportado com os nt alinhados do HSP que a forneceu, que não é eixo do Pareto); unidades nunca são combinadas. PARALOG compara os vetores de DSRNASE1 e DSRNASE3 conjuntamente, então um trade-off entre eles é empate. Os candidatos são comparados por dominância de Pareto, com empates preservados. Não há filtro duro por E-value, 19-mer ou 21-mer. **OTHER_TRANSCRIPT** (o restante do TSA de *D. maidis*) é descritor com revisão manual obrigatória pré-recomendação: não entra no vetor, na ordem de Pareto, na assinatura das células nem na ordenação primária, mas nenhum candidato pode ser recomendado sem uma decisão `APPROVED` versionada sobre seus hits contra o TSA completo; uma preocupação forte (`STRONG_INTRASPECIES_SPECIFICITY_CONCERN`, com justificativa) exclui o candidato após a revisão e a seleção passa ao próximo elegível.
7. **Sem score composto, posição como descritor.** A priorização é lexicográfica (estrutura, especificidade, variantes), empates são explícitos, e a posição 5'/central/3' é descritor que não afeta células nem ranking.

## Justificativa

Justificativa recuperável: cada regra ou tem a evidência registrada no registro ou é declarada convenção, e cada convenção é limitada para que não atue silenciosamente como limiar biológico. A revisão obrigatória preserva a especificidade intraespécie sem deixar um fundo inespecífico definir a estrutura da análise.

## Consequências

A shortlist recomendada é produzida iterativamente: um candidato provisório é ordenado pela evidência decisória, seus hits contra o TSA completo são revisados por uma pessoa e registrados em `config/nb02_manual_review_decisions.tsv`, e só então pode ser recomendado. Os resultados dependem de decisões revisadas por pessoas, versionadas com o hash da evidência revisada.

## Limitações

A unidade de 21 nt, o piso de 60 pb e a generalização do benchmark vêm de outros sistemas ou de um desenho que entrega dois dsRNAs. Limiares são convenções onde existem. O texto principal do artigo do benchmark não foi lido pelo agente (`experimental_protocol_verification = PROJECT_PROVIDED_NOT_AGENT_VERIFIED`). O piso de 60 nt (C03) é redundante diante da faixa de 300-500 nt (C02) e não afeta nenhum candidato do NB02. Os dois accessions do TSA podem ser um locus ou dois.

## O que esta decisão NÃO estabelece

Não estabelece eficácia biológica de nenhuma região, um comprimento ótimo, que regiões 5' ou 3' difiram, que ausência de homologia seja segurança, nem a identidade do locus de dsRNase-2.

## Condições de falseamento / revisão

Revisar se o texto principal do artigo do benchmark contradisser os fatos de protocolo fornecidos, se dados validados sustentarem um critério de cross-silenciamento ou um comprimento ótimo para *D. maidis*, se o Wet Lab documentar uma restrição real de síntese ou clonagem, ou se as decisões de identidade do NB01 mudarem.

## Notebook relacionado

Não aplicável neste checkpoint (o notebook do NB02 é criado em checkpoint posterior).

## Dataset / artefato relacionado

[Pin](../../../../data/reference/nb01_dsrnase2_operational_reference.json), [registro de critérios](../../../../config/nb02_design_criteria.yaml), [arquivo de decisões](../../../../config/nb02_manual_review_decisions.tsv).

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não integrado ao master` (trabalho na branch `feat/nb02-dsrnase2-dsrna-candidate-regions`, base `9e0a7a2`).

## Proveniência

Escrito no checkpoint 1, antes de qualquer janela candidata, busca de especificidade ou ranking. A política foi refinada em várias rodadas de revisão do plano; os fatos de protocolo do benchmark e as conclusões das três revisões de literatura foram fornecidos pelo projeto e não foram verificados independentemente aqui.
