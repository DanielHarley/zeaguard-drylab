# Title

Classify NB01 target identity associations with exact matching and thresholded BLASTn

## Status

Proposed

## Date

2026-09-11

## Context / problem

Publication local Trinity identifiers are not preserved in the headers of the materialized `GITV00000000.1` TSA. NB01 Stage 3 therefore applied a layered reconciliation method to associate published anchors with TSA records while retaining uncertainty and competitive matches.

## Question being decided

Which computational evidence and thresholds are sufficient to classify a published target anchor as `RESOLVED_EXACT`, `RESOLVED_HIGH_CONFIDENCE`, `AMBIGUOUS`, or `UNRESOLVED` against the NB01 primary TSA?

## Evidence

The implemented constants and classification logic are in [nb01_identity.py](../../../zeaguard/nb01_identity.py). The executed parameters, input hashes, tool versions, candidates, and classifications are recorded in [target_identity_report.json](../../../../results/bioinformatics/nb01/target_identity_report.json) and [target_identity_candidates.tsv](../../../../results/bioinformatics/nb01/target_identity_candidates.tsv).

## Evidence classification

1. `directly demonstrated`: the implementation and report record the layer order, thresholds, competitive hit rule, BLAST parameters, and status definitions used by the completed execution.
2. `derived/computed`: alignments, metrics, competitive hit counts, and resulting status assignments were computed from the recorded anchor sequences and TSA.
3. `inferred/interpreted`: `RESOLVED_HIGH_CONFIDENCE` is a computational interpretation conditional on this policy. It is not independently validated biological identity.
4. `unresolved`: `AMBIGUOUS` and `UNRESOLVED` preserve evidence that cannot distinguish or support a unique association under the current policy.
5. `operational assumption`: the 98% minimum identity, 95% minimum query coverage, `1e-20` maximum e-value, and competitive hit tolerances have no bibliographic foundation or independent validation recorded in the repository. They are agent selected operational thresholds pending human review.

## Alternatives considered

`not recoverable`. The original deliberation comparing alternative aligners, validated cutoffs, exact matching only, or manual adjudication is not recorded. The current implementation demonstrates the applied policy only.

## Decision

Apply the following ordered layers without adapting criteria to observed targets.

1. Search TSA headers for exact preservation of the published transcript identifier or declared alias.
2. Search all TSA sequences for complete nucleotide containment in the forward orientation and, when applicable, the reverse complement.
3. When no exact association exists and an official published nucleotide sequence is available, run local BLASTn against the manifest selected TSA.

Classify results as follows.

1. `RESOLVED_EXACT`: exactly one TSA header preserves a published identifier or alias, or exactly one TSA record contains the complete published sequence in forward or reverse complement orientation.
2. `RESOLVED_HIGH_CONFIDENCE`: the top BLASTn hit has identity at least 98%, query coverage at least 95%, and e-value at most `1e-20`, with no distinct competitive TSA accession.
3. `AMBIGUOUS`: multiple header or complete sequence matches exist, or at least one distinct BLASTn hit is competitively similar to a high confidence top hit.
4. `UNRESOLVED`: no exact match exists and no unique BLASTn result satisfies every high confidence threshold. Lack of a search hit also remains `UNRESOLVED`.

A competitive BLASTn hit must independently satisfy all high confidence thresholds and must have a bit score at least 95% of the top score, identity no more than 1 percentage point below the top hit, and query coverage no more than 2 percentage points below the top hit.

The executed search used BLASTn task `blastn`, dust filtering disabled, search e-value `1e-5`, at most 100 target sequences, and at most one HSP per subject. These are operational implementation parameters without recorded independent validation.

## Rationale

The recoverable rationale is to prefer direct identifier and complete sequence evidence, then preserve uncertainty when local alignment evidence is insufficient or competitively supported. Scientific justification for the numeric thresholds is `not recoverable`. Their use constitutes an operational assumption pending review.

## Consequences

Status assignments are deterministic under the declared inputs, tool behavior, and thresholds. Multiple exact matches cannot produce a unique resolution. A top BLASTn hit cannot produce high confidence when any required threshold fails or a competitive accession remains.

## Limitations

The policy has not been benchmarked against independently confirmed positive and negative identities. BLAST metrics depend on the query, database, software version, and search parameters. Query coverage below threshold may reflect partial deposition, transcript boundaries, isoforms, assembly fragmentation, or an incorrect association. The current method does not distinguish those explanations.

## What this decision does NOT establish

`RESOLVED_HIGH_CONFIDENCE` does not establish experimentally confirmed identity. `AMBIGUOUS` does not identify the correct candidate. `UNRESOLVED` does not demonstrate gene absence or incorrect identity. Failing one threshold does not demonstrate that an association is false.

## Falsification / revision conditions

Review is required before acceptance. Revise or reject this policy if independent validation contradicts a classification, benchmark data support different thresholds, alternative search parameters materially change candidate ordering or ambiguity, public cross references supply direct mappings, reference sequences are corrected, or the primary TSA changes.

## Related notebook

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Related dataset / artifact

[Dataset manifest](../../../../data/reference/manifest.json), [target anchors](../../../../data/reference/target_anchors.tsv), [published anchor sequences](../../../../data/reference/target_anchor_sequences.fasta), and [Stage 3 report](../../../../results/bioinformatics/nb01/target_identity_report.json)

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

Implementation and this ADR are `not yet committed`.

## Provenance

This retrospective ADR records the policy implemented and executed on 2026-09-11. It was reconstructed from the current code and immutable Stage 3 outputs. It remains `Proposed` because no human approval, bibliographic calibration, or independent validation of the operational thresholds is recorded.

# Versão em PTBR

# Título

Classificar associações de identidade dos alvos do NB01 com correspondência exata e BLASTn sujeito a limiares

## Estado

Proposed

## Data

2026-09-11

## Contexto / problema

Os identificadores Trinity locais das publicações não estão preservados nos headers do TSA `GITV00000000.1` materializado. A Etapa 3 do NB01 aplicou, portanto, um método de reconciliação em camadas para associar âncoras publicadas a registros TSA, preservando a incerteza e as correspondências competitivas.

## Questão sendo decidida

Quais evidências e limiares computacionais são suficientes para classificar uma âncora publicada como `RESOLVED_EXACT`, `RESOLVED_HIGH_CONFIDENCE`, `AMBIGUOUS` ou `UNRESOLVED` em relação ao TSA primário do NB01?

## Evidências

As constantes implementadas e a lógica de classificação estão em [nb01_identity.py](../../../zeaguard/nb01_identity.py). Os parâmetros executados, hashes dos inputs, versões das ferramentas, candidatos e classificações estão registrados em [target_identity_report.json](../../../../results/bioinformatics/nb01/target_identity_report.json) e [target_identity_candidates.tsv](../../../../results/bioinformatics/nb01/target_identity_candidates.tsv).

## Classificação das evidências

1. `diretamente demonstrado`: a implementação e o relatório registram a ordem das camadas, os limiares, a regra para hits competitivos, os parâmetros do BLAST e as definições de estado usadas na execução concluída.
2. `derivado/computado`: alinhamentos, métricas, contagens de hits competitivos e estados resultantes foram computados a partir das sequências das âncoras e do TSA registrados.
3. `inferido/interpretado`: `RESOLVED_HIGH_CONFIDENCE` é uma interpretação computacional condicionada a esta política. Ela não constitui identidade biológica validada de forma independente.
4. `não resolvido`: `AMBIGUOUS` e `UNRESOLVED` preservam evidências incapazes de distinguir ou sustentar uma associação única sob esta política.
5. `pressuposto operacional`: identidade mínima de 98%, cobertura mínima da query de 95%, e-value máximo de `1e-20` e tolerâncias para hits competitivos não possuem fundamentação bibliográfica ou validação independente registrada no repositório. São limiares operacionais selecionados pelo agente e pendentes de revisão humana.

## Alternativas consideradas

`não recuperável`. A deliberação original que comparou alinhadores alternativos, cutoffs validados, correspondência exclusivamente exata ou adjudicação manual não está registrada. A implementação atual demonstra somente a política aplicada.

## Decisão

Aplicar as seguintes camadas ordenadas sem adaptar os critérios aos alvos observados.

1. Pesquisar nos headers do TSA a preservação exata do identificador publicado do transcrito ou de um alias declarado.
2. Pesquisar em todas as sequências do TSA a contenção nucleotídica completa na orientação direta e, quando aplicável, no reverso complementar.
3. Quando não existir uma associação exata e uma sequência nucleotídica oficial publicada estiver disponível, executar BLASTn local contra o TSA selecionado pelo manifest.

Classificar os resultados da seguinte forma.

1. `RESOLVED_EXACT`: exatamente um header TSA preserva um identificador publicado ou alias, ou exatamente um registro TSA contém a sequência publicada completa na orientação direta ou reverso complementar.
2. `RESOLVED_HIGH_CONFIDENCE`: o principal hit do BLASTn possui identidade de pelo menos 98%, cobertura da query de pelo menos 95% e e-value de no máximo `1e-20`, sem accession TSA competitivo distinto.
3. `AMBIGUOUS`: existem múltiplas correspondências de header ou sequência completa, ou pelo menos um hit BLASTn distinto é competitivamente semelhante a um principal hit de alta confiança.
4. `UNRESOLVED`: não existe correspondência exata e nenhum resultado BLASTn único satisfaz todos os limiares de alta confiança. A ausência de hit na busca também permanece `UNRESOLVED`.

Um hit BLASTn competitivo deve satisfazer de forma independente todos os limiares de alta confiança e deve possuir bit score de pelo menos 95% do score principal, identidade no máximo 1 ponto percentual abaixo do principal hit e cobertura da query no máximo 2 pontos percentuais abaixo do principal hit.

A busca executada usou a tarefa `blastn` do BLASTn, desativou a filtragem dust, adotou e-value de busca `1e-5`, limitou os resultados a 100 sequências alvo e a um HSP por subject. Esses parâmetros são escolhas operacionais de implementação sem validação independente registrada.

## Justificativa

A justificativa recuperável consiste em priorizar evidência direta de identificador e sequência completa e, depois, preservar a incerteza quando a evidência do alinhamento local for insuficiente ou possuir suporte competitivo. A justificativa científica para os limiares numéricos é `não recuperável`. Seu uso constitui um pressuposto operacional pendente de revisão.

## Consequências

As atribuições de estado são determinísticas sob os inputs, o comportamento das ferramentas e os limiares declarados. Múltiplas correspondências exatas não podem produzir uma resolução única. Um principal hit do BLASTn não pode produzir alta confiança quando algum limiar obrigatório falhar ou permanecer um accession competitivo.

## Limitações

A política não foi avaliada contra identidades positivas e negativas confirmadas de forma independente. As métricas do BLAST dependem da query, do banco de dados, da versão do software e dos parâmetros da busca. Cobertura abaixo do limiar pode refletir deposição parcial, limites do transcrito, isoformas, fragmentação da montagem ou uma associação incorreta. O método atual não distingue essas explicações.

## O que esta decisão NÃO estabelece

`RESOLVED_HIGH_CONFIDENCE` não estabelece identidade confirmada experimentalmente. `AMBIGUOUS` não identifica o candidato correto. `UNRESOLVED` não demonstra ausência do gene ou identidade incorreta. A falha em um limiar não demonstra que uma associação é falsa.

## Condições de falseamento / revisão

É necessária revisão antes da aceitação. Revise ou rejeite esta política se validação independente contradisser uma classificação, se dados de benchmark sustentarem limiares diferentes, se parâmetros alternativos da busca alterarem materialmente a ordenação dos candidatos ou a ambiguidade, se referências cruzadas públicas fornecerem mapeamentos diretos, se as sequências de referência forem corrigidas ou se o TSA primário mudar.

## Notebook relacionado

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Dataset / artefato relacionado

[Manifest do dataset](../../../../data/reference/manifest.json), [âncoras dos alvos](../../../../data/reference/target_anchors.tsv), [sequências publicadas das âncoras](../../../../data/reference/target_anchor_sequences.fasta) e [relatório da Etapa 3](../../../../results/bioinformatics/nb01/target_identity_report.json)

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

A implementação e este ADR `ainda não foram commitados`.

## Proveniência

Este ADR retrospectivo registra a política implementada e executada em 2026-09-11. Ele foi reconstruído a partir do código atual e dos outputs imutáveis da Etapa 3. Permanece `Proposed` porque não há registro de aprovação humana, calibração bibliográfica ou validação independente dos limiares operacionais.
