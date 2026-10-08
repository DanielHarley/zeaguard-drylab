# Title

Pre-register the policy for selecting candidate regions of a nominal 400 nt dsRNA against Dmai-BicC inside the operational CDS, with a primer-defined benchmark of 373 nt kept apart from the published 372 bp

## Status

Accepted

## Decision scope

This ADR accepts the NB03 preregistration policy through CP1.
It does not imply acceptance of downstream candidate-selection results, which remain pending CP2–CP5.

## Date

2026-10-08

## Context / problem

NB01 resolved the published BicC cDNA (`TRINITY_DN24799_c0_g1_i7`) to the TSA record `GITV01000968.1` with `RESOLVED_HIGH_CONFIDENCE`, at transcript level only. NB02 closed the equivalent exercise for dsRNase-2. NB03 must now select regions of the BicC CDS for a future dsRNA. BicC is the payload target, and a published fragment with direct experimental evidence exists, so the risk is not computational: it is false precision (an invented weight, an invented threshold, a sequence silently corrected to fit a reported number, or a hypothesis such as paralogy promoted to a fact). Every rule that looks quantitative must rest on evidence or be declared a convention, and must be fixed before any candidate window exists.

This record does not modify ADR 0003, 0004 or 0005 and does not decide the molecular architecture of the construct.

## Question being decided

Which policy governs the selection of candidate regions (interval and length) of the operational BicC CDS, and how are the published benchmark, the observed sequence differences, BicC-like and dsRNase-2 specificity, and the Wet Lab hand-off treated?

## Evidence

1. [Criteria registry](../../../../config/nb03_design_criteria.yaml), pre-registered before any window, validated by [nb03_criteria.py](../../../zeaguard/nb03_criteria.py) and its [tests](../../../../tests/test_nb03_criteria.py).
2. [Operational reference pin](../../../../data/reference/nb01_bicc_operational_reference.json), re-derived from the hash-pinned TSA, the versioned anchor FASTA and the pinned primers by `verify_pin`; it does not need the raw supplement or the gitignored CP0 results.
3. [Unit membership decisions](../../../../config/nb03_unit_membership_decisions.tsv), each with an `evidence_sha256` that is either the hash of a versioned file or a CP0 output hash registered in the pin.
4. Primary evidence for the benchmark: Supplementary Table S1 of Dalaison-Fuentes et al. 2022 (DOI 10.1002/ps.6937), provided by the user (sha256 `0d235a577ed7ac5782a90e07cdb6679db1ecf2da4d0e9bc79e37bf377b0bc4be`), kept outside Git. It lists `BicC_Fw`, `BicC_Rv`, their T7 versions for dsRNA synthesis, and the amplicon lengths 372 and 402 bp. The 2023 supplement carries the same values and is corroboration only.
5. CP0 code at commit `2d1ae8f` ([nb03_reference.py](../../../zeaguard/nb03_reference.py), [nb03_discovery.py](../../../zeaguard/nb03_discovery.py), [nb03_benchmark.py](../../../zeaguard/nb03_benchmark.py)).

## Evidence classification

Each statement carries one category; they are not mixed.

1. `OBSERVATION`: `GITV01000968.1` has a 2337 nt CDS (65-2401) encoding 778 aa on the + strand, 5' UTR 64 nt and 3' UTR 3665 nt. The published cDNA is stored antisense (2655 nt, CDS 2337 nt). The two CDS differ at 7 positions (597, 1092, 1120, 1287, 2094, 2259, 2280) without indels. The primers of Table S1 map uniquely and define a 373 nt body (CDS 215-587, sha256 `e866ebd1…53fb`) and a 403 nt amplicon with two 15 nt tails, whereas the publication reports 372 and 402. `GITV01002238.1` aligns to BicC at 85.6% protein identity over 792 aa and 79.7% nucleotide identity.
2. `INFERENCE`: the observed differences may matter for the robustness of a design to the two sequences available; `GITV01002238.1` justifies a unit for the interpretability of the BicC effect.
3. `HYPOTHESIS`: `GITV01002238.1` may be a paralog, duplicate, co-ortholog or another related transcript; the reported 372 might come from a non-inclusive count. Neither is established or promoted.
4. `PROJECT_CONVENTION`: CDS-only design domain; 300-500 nt design range; 400 nt as ranking length; the joint six-axis Pareto and its lower-is-better direction; the observed-differences count as a decisional robustness metric; the descriptive roles of every other metric; the unit taxonomy.
5. `OPERATIONAL_ASSUMPTION`: k = 21 for describing potential 21-nt derived windows; the BLASTn detection limit shared with NB02.

## Alternatives considered

A composite score with weights (rejected: no defensible weights). A hard filter on GC, homopolymer, complexity, identity, exact match or 19/21-mer (rejected: no evidence). Truncating the reconstructed body to 372 nt or shifting a primer to match the reported length (rejected: it would invent a sequence that no primer defines). A 372 nt window as a second ranking stratum (rejected: the sequence that exists has 373 nt). Promoting `GITV01002238.1` to PARALOG from transcriptomic similarity (rejected: not sufficient evidence). Treating the 3' UTR as design space because the benchmark may touch a UTR (rejected: the design domain is not widened by the benchmark). A hierarchy between BICC_LIKE and DSRNASE2 (rejected: no basis to prefer one). Widening k to 19-23 (rejected for now: a descriptor needs no sensitivity band).

## Decision

1. **Operational reference.** `GITV01000968.1`, CDS 65-2401, coordinates of design on the CDS in sense orientation (1-2337). This is not a claim of unique biological identity.
2. **Design domain and length.** CDS only; candidates of 300-500 nt, fully inside the CDS, with only A/C/G/T: these are the only three hard filters. 400 nt is the ranking length by `PROJECT_CONVENTION`, not a biological optimum; 300 and 500 nt are sensitivity strata. Specificity is compared only within a length stratum.
3. **Benchmark.** The primer-defined body of 373 nt is the operational benchmark sequence, a `REFERENCE_SET` member that never counts among the 2-4 new candidates and never takes part in forming the cells of candidates. The published 372 bp stays `PUBLISHED_REPORTED_METADATA`; the 1 nt difference is recorded as `UNRESOLVED_PUBLICATION_INCONSISTENCY` with no asserted cause. The sequence layer (`VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY`) and the protocol layer (`PROJECT_PROVIDED_NOT_AGENT_VERIFIED`) stay independent. Overlap with the benchmark, its fraction and the categories DISJOINT, PARTIAL_OVERLAP, FULLY_WITHIN and CONTAINS_BENCHMARK are descriptive only. A benchmark touching a UTR does not widen the design domain.
4. **Units.** `KNOWN_BICC_COMPATIBLE` (`GITV01000968.1`, the published cDNA) is excluded from risk. `BICC_LIKE` (`GITV01002238.1`) keeps `relationship_status = UNRESOLVED` and is decisional for interpretability; no PARALOG label is used. `DSRNASE2` is a CO_TARGET decisional for interpretability. `DSRNASE1` and `DSRNASE3` are descriptive only. `OTHER_TRANSCRIPT` is descriptive plus a mandatory manual review, outside the vector, the Pareto order, the cell signature and the automatic ordering. Units are never pooled. Membership decisions are human, versioned and carry an `evidence_sha256`.
5. **Pareto.** One joint comparison of BICC_LIKE and DSRNASE2 on six axes (longest exact match, covered nt and best local identity, each clipped to the candidate, for each unit), all lower is better. A dominates B if it is no worse on all six axes and strictly better on at least one; a trade-off between units is incomparable (a tie). No summation, normalisation, weights, score, hierarchy, E-value axis or HSP-count axis. The direction is a convention of interpretability, not a statement of safety.
6. **Observed sequence differences.** `count_intersected_observed_sequence_differences` (lower is better) acts after specificity, never excludes and has no threshold. The decisional cell signature contains this count and the two specificity vectors. Equal vectors and equal counts define the same signature even when the intersected positions differ. `intersected_observed_sequence_difference_positions` is calculated, preserved and reported as `DESCRIPTIVE_ONLY`, with no role in splitting cells, Pareto, ordering or tie-breaking. Permitted reading: fewer intersected means greater robustness to the two currently observed sequences. Their nature stays unresolved and `read_support_status = NOT_ASSESSED_FOR_NB03_CP0`. `fraction_unaffected` is descriptive.
7. **Small-RNA descriptors.** k = 21, an `OPERATIONAL_ASSUMPTION`, descriptive only, called "potential 21-nt derived windows"; it does not enter the Pareto, the signature, the ordering or any exclusion.
8. **Descriptive-only criteria.** GC, longest homopolymer, low complexity, position along the CDS, exact 19-mer and 21-mer counts, E-values, HSP counts, DSRNASE1/DSRNASE3 and OTHER_TRANSCRIPT evidence, shuffled controls, benchmark overlap and `relationship_status` cannot alter a cell or an order without a dated amendment made before the analysis.
9. **Modularity.** dsRNA-BicC is meant to act on BicC, dsRNA-dsRNase2 on dsRNase-2, and co-feeding or co-expression delivers both. The interpretability direction follows from this modular strategy.
10. **Out of scope.** Architecture (hairpin or linear), promoter, terminator, plasmid, chassis, formulation and ecological off-target stay downstream of NB03.

## Pre-CP2 descriptive clarification (2026-10-08)

Before any NB03 candidate window was generated, the user approved explicit benchmark overlap denominators: `overlap_fraction_of_candidate = overlap_with_benchmark_nt / candidate_length` and `overlap_fraction_of_benchmark = overlap_with_benchmark_nt / 373`. The ambiguous `overlap_fraction` field is removed. `EXACT_MATCH` identifies the design window at CDS 215-587; strictly shorter contained windows are `FULLY_WITHIN`, strictly longer containing windows are `CONTAINS_BENCHMARK`, zero overlap is `DISJOINT`, and every other positive overlap is `PARTIAL_OVERLAP`. All four descriptors remain `DESCRIPTIVE_ONLY`, outside Pareto, the decisional signature, ordering and tie-breaking. Registry amendment C23 records this clarification without changing decisional policy. The geometric design window and the separately characterized `REFERENCE_SET` benchmark retain distinct memberships despite identical coordinates and sequence.

## Rationale

Each rule is either backed by recorded evidence or declared a convention, and each convention is bounded so that it cannot act silently as a biological threshold. Keeping 372 and 373 side by side makes the inconsistency auditable instead of hiding it in a corrected sequence. Keeping BICC_LIKE unresolved lets it inform interpretability without turning a hypothesis into a fact.

## Consequences

CP2 can enumerate windows against a frozen contract. Results will depend on a person's reviewed OTHER_TRANSCRIPT decisions and on a membership file whose evidence hashes are verifiable. If the BICC_LIKE or DSRNASE2 vectors are all zero, the ordering will be decided by the observed-differences count alone, as happened for NB02.

## Limitations

Only two BicC sequences are compared and the nature of their 7 differences is unresolved; nothing population-level follows. The article text of 2022 was not read by the agent: only its Table S1, supplied by the user. The experimental protocol of the benchmark is not verified. The 21 nt unit comes from other systems. "No homology detected" means no homology at the declared detection limit, never safety. The TSA is not the laboratory colony; any chosen region must be confirmed by sequencing the colony.

## What this decision does NOT establish

Biological efficacy of any region, an optimal length, that a position matters, that `GITV01002238.1` is or is not a paralog, the cause of the 372/373 difference, the nature of the 7 observed differences, safety from the absence of hits, or the experimental protocol of the benchmark.

## Falsification / revision conditions

Revise by dated amendment if the authors resolve the benchmark length, if the 2022 text contradicts the supplied protocol facts, if strong independent genomic or locus evidence bears on `GITV01002238.1`, if read-level or additional sequence evidence characterises the differences, if validated data support a cross-silencing criterion or a length optimum for *D. maidis*, or if the Wet Lab documents a real synthesis constraint.

## Related notebook

Not yet created (Notebook 03 belongs to the closing checkpoint).

## Related dataset / artifact

[Pin](../../../../data/reference/nb01_bicc_operational_reference.json), [criteria registry](../../../../config/nb03_design_criteria.yaml), [membership decisions](../../../../config/nb03_unit_membership_decisions.tsv). CP0 outputs are gitignored under `results/bioinformatics/nb03/cp0/`; their hashes are registered in the pin.

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

CP0: `2d1ae8f` on `feat/nb03-bicc-candidate-regions` (base `584e585`). CP1: `099f751780283fecbc63da177c113aec9f6d60d5`. CP2 changes remain uncommitted pending user review.

## Provenance

Written at checkpoint 1, before any candidate window, candidate search, cell or ranking existed. The C23 descriptive clarification was recorded on 2026-10-08 before CP2 window generation. The 372/373 policy, the CDS-only domain, the unit taxonomy, the joint Pareto and the descriptive roles were decided by the project on 2026-10-08; the primary Table S1 was supplied by the user and its bibliographic content was validated outside this repository.

# Versão em PTBR

# Título

Pré-registrar a política de seleção de regiões candidatas de um dsRNA nominal de 400 nt contra Dmai-BicC dentro da CDS operacional, com um benchmark definido por primers de 373 nt mantido separado dos 372 pb publicados

## Estado

Accepted

## Escopo da decisão

Este ADR aceita a política de pré-registro do NB03 até o CP1.
A aceitação dos resultados posteriores de seleção de candidatos permanece pendente dos checkpoints CP2–CP5.

## Data

2026-10-08

## Contexto / problema

O NB01 resolveu o cDNA publicado de BicC (`TRINITY_DN24799_c0_g1_i7`) para o registro `GITV01000968.1` com `RESOLVED_HIGH_CONFIDENCE`, apenas em nível de transcrito. O NB02 fechou o exercício equivalente para dsRNase-2. O NB03 deve agora selecionar regiões da CDS de BicC para um dsRNA futuro. BicC é o alvo do payload e existe um fragmento publicado com evidência experimental direta; o risco, portanto, não é computacional: é a falsa precisão (peso inventado, limiar inventado, sequência corrigida em silêncio para caber em um número reportado, ou hipótese como paralogia promovida a fato). Toda regra de aparência quantitativa deve ter evidência ou ser declarada convenção, e fixada antes de existir qualquer janela candidata.

Este registro não modifica os ADR 0003, 0004 e 0005 e não decide a arquitetura molecular do construto.

## Questão sendo decidida

Qual política governa a seleção de regiões candidatas (intervalo e comprimento) da CDS operacional de BicC, e como são tratados o benchmark publicado, as diferenças de sequência observadas, a especificidade contra BicC-like e dsRNase-2 e a entrega ao Wet Lab?

## Evidências

1. [Registro de critérios](../../../../config/nb03_design_criteria.yaml), pré-registrado antes de qualquer janela, validado por [nb03_criteria.py](../../../zeaguard/nb03_criteria.py) e seus [testes](../../../../tests/test_nb03_criteria.py).
2. [Pin da referência operacional](../../../../data/reference/nb01_bicc_operational_reference.json), rederivado do TSA com hash fixado, do FASTA de âncoras versionado e dos primers fixados por `verify_pin`; não precisa do suplemento bruto nem dos resultados gitignored do CP0.
3. [Decisões de pertencimento às unidades](../../../../config/nb03_unit_membership_decisions.tsv), cada uma com `evidence_sha256` que é o hash de um arquivo versionado ou o hash de uma saída do CP0 registrada no pin.
4. Evidência primária do benchmark: Tabela Suplementar S1 de Dalaison-Fuentes et al. 2022 (DOI 10.1002/ps.6937), fornecida pelo usuário (sha256 `0d235a577ed7ac5782a90e07cdb6679db1ecf2da4d0e9bc79e37bf377b0bc4be`), mantida fora do Git. Ela lista `BicC_Fw`, `BicC_Rv`, suas versões T7 para síntese de dsRNA e os comprimentos de amplicon 372 e 402 pb. O suplemento de 2023 traz os mesmos valores e é só corroboração.
5. Código do CP0 no commit `2d1ae8f` ([nb03_reference.py](../../../zeaguard/nb03_reference.py), [nb03_discovery.py](../../../zeaguard/nb03_discovery.py), [nb03_benchmark.py](../../../zeaguard/nb03_benchmark.py)).

## Classificação das evidências

Cada afirmação tem uma categoria; elas não se misturam.

1. `OBSERVATION`: `GITV01000968.1` tem CDS de 2337 nt (65-2401) que codifica 778 aa na fita +, 5' UTR de 64 nt e 3' UTR de 3665 nt. O cDNA publicado está armazenado antisense (2655 nt, CDS de 2337 nt). As duas CDS diferem em 7 posições (597, 1092, 1120, 1287, 2094, 2259, 2280), sem indels. Os primers da Tabela S1 mapeiam de forma única e definem um corpo de 373 nt (CDS 215-587, sha256 `e866ebd1…53fb`) e um amplicon de 403 nt com duas caudas de 15 nt, enquanto a publicação reporta 372 e 402. `GITV01002238.1` alinha a BicC com 85,6% de identidade proteica em 792 aa e 79,7% de identidade nucleotídica.
2. `INFERENCE`: as diferenças observadas podem importar para a robustez de um desenho às duas sequências disponíveis; `GITV01002238.1` justifica uma unidade para a interpretabilidade do efeito de BicC.
3. `HYPOTHESIS`: `GITV01002238.1` pode ser parálogo, duplicata, co-ortólogo ou outro transcrito relacionado; o 372 reportado pode vir de uma contagem não inclusiva. Nenhuma está estabelecida nem promovida.
4. `PROJECT_CONVENTION`: domínio de design só na CDS; faixa de 300-500 nt; 400 nt como comprimento de ranking; o Pareto conjunto de seis eixos e sua direção menor-é-melhor; a contagem de diferenças observadas como métrica decisional de robustez; os papéis descritivos de todas as demais métricas; a taxonomia de unidades.
5. `OPERATIONAL_ASSUMPTION`: k = 21 para descrever janelas potenciais derivadas de 21 nt; o limite de detecção do BLASTn compartilhado com o NB02.

## Alternativas consideradas

Score composto com pesos (rejeitada: sem pesos defensáveis). Filtro duro por GC, homopolímero, complexidade, identidade, trecho exato ou 19/21-mer (rejeitada: sem evidência). Truncar o corpo reconstruído a 372 nt ou deslocar um primer para caber no comprimento reportado (rejeitada: inventaria uma sequência que nenhum primer define). Janela de 372 nt como segundo estrato de ranking (rejeitada: a sequência que existe tem 373 nt). Promover `GITV01002238.1` a PARALOG por similaridade transcriptômica (rejeitada: evidência insuficiente). Tratar a 3' UTR como espaço de design porque o benchmark pode tocar uma UTR (rejeitada: o benchmark não amplia o domínio). Hierarquia entre BICC_LIKE e DSRNASE2 (rejeitada: sem base para preferir uma). Ampliar k para 19-23 (rejeitada por ora: um descritor não precisa de faixa de sensibilidade).

## Decisão

1. **Referência operacional.** `GITV01000968.1`, CDS 65-2401, coordenadas de design na CDS em orientação sense (1-2337). Isso não é afirmação de identidade biológica única.
2. **Domínio de design e comprimento.** Só a CDS; candidatos de 300-500 nt, inteiramente dentro da CDS, só com A/C/G/T: esses são os únicos três filtros duros. 400 nt é o comprimento de ranking por `PROJECT_CONVENTION`, não ótimo biológico; 300 e 500 nt são estratos de sensibilidade. A especificidade só é comparada dentro de um estrato de comprimento.
3. **Benchmark.** O corpo de 373 nt definido pelos primers é a sequência operacional do benchmark, membro do `REFERENCE_SET`, que nunca conta entre os 2-4 candidatos novos e nunca participa da formação das células dos candidatos. Os 372 pb publicados permanecem `PUBLISHED_REPORTED_METADATA`; a diferença de 1 nt é registrada como `UNRESOLVED_PUBLICATION_INCONSISTENCY`, sem causa afirmada. A camada de sequência (`VERIFIED_FROM_PRIMARY_2022_PRIMERS_WITH_REPORTED_LENGTH_DISCREPANCY`) e a de protocolo (`PROJECT_PROVIDED_NOT_AGENT_VERIFIED`) permanecem independentes. A sobreposição com o benchmark, sua fração e as categorias DISJOINT, PARTIAL_OVERLAP, FULLY_WITHIN e CONTAINS_BENCHMARK são só descritivas. Um benchmark que toque uma UTR não amplia o domínio de design.
4. **Unidades.** `KNOWN_BICC_COMPATIBLE` (`GITV01000968.1`, o cDNA publicado) fica fora do risco. `BICC_LIKE` (`GITV01002238.1`) mantém `relationship_status = UNRESOLVED` e é decisional para interpretabilidade; nenhum rótulo PARALOG é usado. `DSRNASE2` é CO_TARGET decisional para interpretabilidade. `DSRNASE1` e `DSRNASE3` são só descritivos. `OTHER_TRANSCRIPT` é descritivo mais revisão manual obrigatória, fora do vetor, da ordem de Pareto, da assinatura de célula e da ordenação automática. As unidades nunca são agregadas entre si. As decisões de pertencimento são humanas, versionadas e têm `evidence_sha256`.
5. **Pareto.** Uma comparação conjunta de BICC_LIKE e DSRNASE2 em seis eixos (maior trecho exato, nt cobertos e melhor identidade local, cada um recortado ao candidato, para cada unidade), todos menor-é-melhor. A domina B se não for pior em nenhum dos seis eixos e estritamente melhor em ao menos um; um trade-off entre unidades é incomparável (empate). Sem soma, normalização, pesos, score, hierarquia, eixo de E-value ou de número de HSPs. A direção é convenção de interpretabilidade, não afirmação de segurança.
6. **Diferenças de sequência observadas.** `count_intersected_observed_sequence_differences` (menor é melhor) age depois da especificidade, nunca exclui e não tem limiar. A assinatura decisional de célula contém essa contagem e os dois vetores de especificidade. Vetores e contagens iguais definem a mesma assinatura mesmo quando as posições interceptadas diferem. `intersected_observed_sequence_difference_positions` é calculada, preservada e reportada como `DESCRIPTIVE_ONLY`, sem papel na divisão de células, no Pareto, na ordenação ou no desempate. Leitura permitida: menos interceptadas significa maior robustez às duas sequências atualmente observadas. A natureza delas permanece não resolvida e `read_support_status = NOT_ASSESSED_FOR_NB03_CP0`. `fraction_unaffected` é descritiva.
7. **Descritores de small RNA.** k = 21, `OPERATIONAL_ASSUMPTION`, só descritivo, chamado "potential 21-nt derived windows"; não entra no Pareto, na assinatura, na ordenação nem em exclusão.
8. **Critérios só descritivos.** GC, homopolímero mais longo, baixa complexidade, posição na CDS, contagens exatas de 19-mer e 21-mer, E-values, número de HSPs, evidência de DSRNASE1/DSRNASE3 e OTHER_TRANSCRIPT, controles embaralhados, sobreposição com o benchmark e `relationship_status` não alteram célula nem ordem sem uma emenda datada feita antes da análise.
9. **Modularidade.** O dsRNA-BicC deve agir sobre BicC, o dsRNA-dsRNase2 sobre dsRNase-2, e co-feeding ou coexpressão entrega ambos. A direção de interpretabilidade decorre dessa estratégia modular.
10. **Fora de escopo.** Arquitetura (hairpin ou linear), promotor, terminador, plasmídeo, chassi, formulação e off-target ecológico ficam a jusante do NB03.

## Clarificação descritiva antes do CP2 (2026-10-08)

Antes da geração de qualquer janela NB03, o usuário aprovou denominadores explícitos: `overlap_fraction_of_candidate = overlap_with_benchmark_nt / candidate_length` e `overlap_fraction_of_benchmark = overlap_with_benchmark_nt / 373`. O campo ambíguo `overlap_fraction` foi removido. `EXACT_MATCH` identifica a janela de design CDS 215-587. Janelas contidas estritamente menores são `FULLY_WITHIN`, janelas que contêm o benchmark e são estritamente maiores são `CONTAINS_BENCHMARK`, ausência de sobreposição é `DISJOINT` e os demais casos positivos são `PARTIAL_OVERLAP`. Todos permanecem `DESCRIPTIVE_ONLY`, fora do Pareto, da assinatura decisional, da ordenação e do desempate. A emenda C23 registra a clarificação. A janela geométrica e o benchmark `REFERENCE_SET` mantêm pertencimentos distintos apesar das mesmas coordenadas e sequência.

## Justificativa

Cada regra ou tem evidência registrada ou é declarada convenção, e cada convenção é limitada para não agir em silêncio como limiar biológico. Manter 372 e 373 lado a lado torna a inconsistência auditável em vez de escondê-la em uma sequência corrigida. Manter BICC_LIKE não resolvido deixa que ele informe a interpretabilidade sem transformar uma hipótese em fato.

## Consequências

O CP2 pode enumerar janelas contra um contrato congelado. Os resultados dependerão de decisões de revisão de OTHER_TRANSCRIPT feitas por pessoas e de um arquivo de pertencimento cujos hashes de evidência são verificáveis. Se os vetores de BICC_LIKE e DSRNASE2 forem todos zero, a ordenação será decidida só pela contagem de diferenças observadas, como ocorreu no NB02.

## Limitações

Só duas sequências de BicC são comparadas e a natureza de suas 7 diferenças é não resolvida; nada em nível populacional decorre disso. O texto do artigo de 2022 não foi lido pelo agente: apenas sua Tabela S1, fornecida pelo usuário. O protocolo experimental do benchmark não está verificado. A unidade de 21 nt vem de outros sistemas. "Nenhuma homologia detectada" significa nenhuma homologia no limite de detecção declarado, nunca segurança. O TSA não é a colônia do laboratório; qualquer região escolhida deve ser confirmada por sequenciamento da colônia.

## O que esta decisão NÃO estabelece

Eficácia biológica de qualquer região, um comprimento ótimo, que uma posição importe, que `GITV01002238.1` seja ou não parálogo, a causa da diferença 372/373, a natureza das 7 diferenças observadas, segurança a partir da ausência de hits, nem o protocolo experimental do benchmark.

## Condições de falseamento / revisão

Revisar por emenda datada se os autores resolverem o comprimento do benchmark, se o texto de 2022 contradisser os fatos de protocolo fornecidos, se evidência genômica ou de locus forte e independente disser respeito a `GITV01002238.1`, se evidência de leituras ou de sequências adicionais caracterizar as diferenças, se dados validados sustentarem um critério de cross-silenciamento ou um comprimento ótimo para *D. maidis*, ou se o Wet Lab documentar uma restrição real de síntese.

## Notebook relacionado

Ainda não criado (o Notebook 03 pertence ao checkpoint de fechamento).

## Dataset / artefato relacionado

[Pin](../../../../data/reference/nb01_bicc_operational_reference.json), [registro de critérios](../../../../config/nb03_design_criteria.yaml), [decisões de pertencimento](../../../../config/nb03_unit_membership_decisions.tsv). As saídas do CP0 são gitignored em `results/bioinformatics/nb03/cp0/`; seus hashes estão registrados no pin.

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

CP0: `2d1ae8f` em `feat/nb03-bicc-candidate-regions` (base `584e585`). CP1: `099f751780283fecbc63da177c113aec9f6d60d5`. Alterações do CP2 permanecem sem commit, aguardando revisão do usuário.

## Proveniência

Escrito no checkpoint 1, antes de existir qualquer janela candidata, busca de candidatos, célula ou ranking. A clarificação descritiva C23 foi registrada em 2026-10-08 antes da geração de janelas do CP2. A política 372/373, o domínio só-CDS, a taxonomia de unidades, o Pareto conjunto e os papéis descritivos foram decididos pelo projeto em 2026-10-08; a Tabela S1 primária foi fornecida pelo usuário e seu conteúdo bibliográfico foi validado fora deste repositório.
