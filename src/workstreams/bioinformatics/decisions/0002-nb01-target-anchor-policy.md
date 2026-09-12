# Title

Use published identifiers and primary sources as precomputational target identity anchors in NB01

## Status

Accepted

## Date

2026-09-11

## Context / problem

The four targets declared in `config/project.yaml` require traceable identity anchors before any comparison against the public TSA. Repository artifacts separate publication sourced identifiers and sequences from later computational associations.

## Question being decided

What evidence may define an NB01 target anchor before computational identity resolution?

## Evidence

The [target anchor table](../../../../data/reference/target_anchors.tsv) contains one row per configured target and records source references, source identifiers, publication local identifiers, evidence strength, limitations, and identity status. The [published sequence artifact](../../../../data/reference/target_anchor_sequences.fasta) preserves the four publication local transcript identifiers and their source labels. The [NB01 notebook](../notebooks/01_reference_dataset_and_target_identity.ipynb) validates anchors before invoking Stage 3.

## Evidence classification

1. `directly demonstrated`: the anchor table names four configured targets and records publication and supplement provenance for each published identifier. The sequence artifact is keyed by those identifiers.
2. `derived/computed`: structural validation determines coverage of configured targets, duplicate identifiers, and required fields.
3. `inferred/interpreted`: evidence strength and the use of a publication local record as an identity anchor are curated interpretations bounded by the cited source.
4. `unresolved`: an anchor without a documented TSA mapping remains computationally unresolved until a separate reconciliation policy is applied.

## Alternatives considered

`not recoverable`. The repository does not preserve the original deliberation or a documented comparison with similarity first anchoring, manual notebook constants, or secondary source only curation.

## Decision

NB01 reads its target list from `config/project.yaml`. Each target must have one structured anchor derived from a directly relevant publication, its official supplement, an associated public record, or existing curated repository evidence. Publication local identifiers and source sequences remain distinct from TSA accessions. Computational similarity results cannot retroactively populate or replace the bibliographic anchor.

## Rationale

The recoverable rationale is the implemented separation between configured targets, source attributed anchors, and subsequent computational resolution. The broader historical reasoning for selecting this policy is `not recoverable`.

## Consequences

Missing published identifiers may remain explicit review conditions. A target can be documented by a primary source while its mapping to the reference TSA remains `UNRESOLVED`. Later computational outputs must retain the published identifier, TSA candidate, and evidence source separately.

## Limitations

Publication local identifiers may be absent from public FASTA headers. Published sequences may differ from deposited assemblies. Source attribution and structural completeness do not independently validate target identity or biological function.

## What this decision does NOT establish

This policy does not confirm correspondence between a publication local transcript and a TSA record. It does not establish sequence correctness, uniqueness, biological function, or absence from the organism.

## Falsification / revision conditions

Revise the policy if primary sources are corrected, target declarations change, a public cross reference provides stronger direct evidence, or validation demonstrates that the artifact cannot preserve claim level provenance.

## Related notebook

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Related dataset / artifact

[Target anchor table](../../../../data/reference/target_anchors.tsv) and [published anchor sequences](../../../../data/reference/target_anchor_sequences.fasta)

## Stage 2 output artifact

`inspect_target_anchors`/`prepare_nb01_stage2` in [nb01_inputs.py](../../../zeaguard/nb01_inputs.py) generate `results/bioinformatics/nb01/target_anchor_report.json`, SHA-256 `63e76eaed241caf7bcc8b9874888021393ded695d06bda628f38669950f8a9ec`. This file remains under the gitignored `results/` directory and is not itself Git-tracked. It is reproducible from the committed Stage 2 code together with the declared reference inputs (`config/project.yaml` and the target anchor table above).

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed`

## Provenance

This retrospective ADR was reconstructed on 2026-09-11 from the current project configuration, target anchor table, published sequence artifact, notebook ordering, and validation code. Undocumented historical reasoning is marked `not recoverable`.

# Versão em PTBR

# Título

Usar identificadores publicados e fontes primárias como âncoras pré-computacionais de identidade dos alvos no NB01

## Estado

Accepted

## Data

2026-09-11

## Contexto / problema

Os quatro alvos declarados em `config/project.yaml` exigem âncoras de identidade rastreáveis antes de qualquer comparação com o TSA público. Os artefatos do repositório separam identificadores e sequências provenientes de publicações das associações computacionais posteriores.

## Questão sendo decidida

Quais evidências podem definir uma âncora de alvo do NB01 antes da resolução computacional de identidade?

## Evidências

A [tabela de âncoras dos alvos](../../../../data/reference/target_anchors.tsv) contém uma linha por alvo configurado e registra referências das fontes, identificadores das fontes, identificadores locais das publicações, força da evidência, limitações e estado da identidade. O [artefato de sequências publicadas](../../../../data/reference/target_anchor_sequences.fasta) preserva os quatro identificadores locais dos transcritos e os rótulos de suas fontes. O [Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb) valida as âncoras antes de invocar a Etapa 3.

## Classificação das evidências

1. `diretamente demonstrado`: a tabela de âncoras nomeia os quatro alvos configurados e registra a proveniência da publicação e do material suplementar para cada identificador publicado. O artefato de sequências é indexado por esses identificadores.
2. `derivado/computado`: a validação estrutural determina a cobertura dos alvos configurados, identificadores duplicados e campos obrigatórios.
3. `inferido/interpretado`: a força da evidência e o uso de um registro local da publicação como âncora de identidade são interpretações curadas e delimitadas pela fonte citada.
4. `não resolvido`: uma âncora sem mapeamento documentado para o TSA permanece computacionalmente não resolvida até a aplicação de uma política separada de reconciliação.

## Alternativas consideradas

`não recuperável`. O repositório não preserva a deliberação original nem uma comparação documentada com ancoragem baseada primeiro em similaridade, constantes manuais no notebook ou curadoria exclusivamente por fontes secundárias.

## Decisão

O NB01 lê sua lista de alvos de `config/project.yaml`. Cada alvo deve possuir uma âncora estruturada derivada de uma publicação diretamente relevante, de seu material suplementar oficial, de um registro público associado ou de evidência curada existente no repositório. Identificadores locais de publicações e sequências de origem permanecem distintos dos accessions TSA. Resultados de similaridade computacional não podem preencher retroativamente nem substituir a âncora bibliográfica.

## Justificativa

A justificativa recuperável é a separação implementada entre alvos configurados, âncoras atribuídas às fontes e resolução computacional subsequente. A justificativa histórica mais ampla para a escolha desta política é `não recuperável`.

## Consequências

Identificadores publicados ausentes podem permanecer como condições explícitas de revisão. Um alvo pode estar documentado por uma fonte primária enquanto seu mapeamento para o TSA de referência permanece `UNRESOLVED`. Resultados computacionais posteriores devem preservar separadamente o identificador publicado, o candidato TSA e a fonte da evidência.

## Limitações

Identificadores locais de publicações podem estar ausentes dos headers FASTA públicos. Sequências publicadas podem diferir das montagens depositadas. A atribuição da fonte e a completude estrutural não validam de forma independente a identidade do alvo ou sua função biológica.

## O que esta decisão NÃO estabelece

Esta política não confirma a correspondência entre um transcrito local de uma publicação e um registro TSA. Ela não estabelece correção da sequência, unicidade, função biológica ou ausência no organismo.

## Condições de falseamento / revisão

Revise a política se fontes primárias forem corrigidas, se as declarações de alvos mudarem, se uma referência cruzada pública fornecer evidência direta mais forte ou se a validação demonstrar que o artefato não consegue preservar a proveniência no nível das afirmações.

## Notebook relacionado

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Dataset / artefato relacionado

[Tabela de âncoras dos alvos](../../../../data/reference/target_anchors.tsv) e [sequências publicadas das âncoras](../../../../data/reference/target_anchor_sequences.fasta)

## Artefato de saída da Etapa 2

`inspect_target_anchors`/`prepare_nb01_stage2` em [nb01_inputs.py](../../../zeaguard/nb01_inputs.py) geram `results/bioinformatics/nb01/target_anchor_report.json`, SHA-256 `63e76eaed241caf7bcc8b9874888021393ded695d06bda628f38669950f8a9ec`. Este arquivo permanece sob o diretório `results/` ignorado pelo Git e não é rastreado pelo Git. Ele é reproduzível a partir do código da Etapa 2 já commitado, em conjunto com os inputs de referência declarados (`config/project.yaml` e a tabela de âncoras dos alvos acima).

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não commitado`

## Proveniência

Este ADR retrospectivo foi reconstruído em 2026-09-11 a partir da configuração atual do projeto, da tabela de âncoras dos alvos, do artefato de sequências publicadas, da ordem do notebook e do código de validação. A justificativa histórica não documentada está marcada como `não recuperável`.
