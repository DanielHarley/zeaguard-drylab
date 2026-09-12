# Title

Adopt TSA GITV00000000.1 as the versioned primary transcriptome reference for NB01

## Status

Accepted

## Date

2026-09-11

## Context / problem

NB01 requires one locally materialized, integrity checked transcriptome dataset as the reference surface for later target identity reconciliation. The repository records the `Dalbulus maidis` TSA master accession `GITV00000000`, version `GITV00000000.1`, and BioProject `PRJNA579843` in the dataset manifest.

## Question being decided

Which versioned public transcriptome dataset is the primary reference input for NB01?

## Evidence

The [dataset manifest](../../../../data/reference/manifest.json) records the NCBI source URL, acquisition timestamp, local path, byte size, and SHA-256. The [acquisition script](../../../../scripts/fetch_nb01_reference.py) implements idempotent materialization and integrity rejection. The [NB01 notebook](../notebooks/01_reference_dataset_and_target_identity.ipynb) consumes the manifest through the existing input contract. The Stage 3 report records the same dataset version and SHA-256 as its executed primary input.

## Evidence classification

1. `directly demonstrated`: accession, version, BioProject, source URL, local path, acquisition time, file size, and SHA-256 are recorded in the manifest. The file passed the repository input contract and was used by the Stage 3 report.
2. `derived/computed`: SHA-256 and the Stage 3 FASTA record count are computational measurements of the materialized file.
3. `inferred/interpreted`: designating this materialized TSA as the primary NB01 reference is a workflow decision supported by the manifest, notebook contract, and current implementation.
4. `unresolved`: transcriptome completeness, assembly correctness, biological representativeness, and suitability for every downstream question remain unvalidated.

## Alternatives considered

`not recoverable`. No repository artifact documents a historical comparison with alternative transcriptome assemblies or genomic references.

## Decision

NB01 uses the NCBI TSA `GITV00000000.1` associated with BioProject `PRJNA579843` as its versioned primary transcriptome reference. The dataset must be obtained exclusively through the repository manifest and must satisfy its recorded SHA-256 before use.

## Rationale

The recoverable rationale is limited to the existence of a public, versioned `Dalbulus maidis` TSA that has been materialized, assigned a stable source, verified by SHA-256, and accepted by the NB01 input contract. Any broader historical rationale is `not recoverable`.

## Consequences

NB01 computations that require the primary reference operate on the manifest selected file. A changed file, source version, or accession requires a manifest update, integrity validation, and review of comparability with earlier outputs.

## Limitations

Artifact integrity verifies file identity. It does not validate assembly completeness, annotation correctness, tissue coverage, isoform resolution, or biological suitability.

## What this decision does NOT establish

This decision does not establish target identity, target absence, biological function, sequence completeness, or scientific validity of later associations.

## Falsification / revision conditions

Revise this decision if the accession is corrected or superseded, the recorded hash cannot be reproduced, the file fails structural validation, public metadata contradict the declared organism or project, or documented evidence shows that another reference is required for the bounded NB01 objective.

## Related notebook

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Related dataset / artifact

[Dataset manifest](../../../../data/reference/manifest.json) and local path `data/external/tsa.GITV.1.fsa_nt.gz`

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed`

## Provenance

This retrospective ADR was reconstructed on 2026-09-11 from the current manifest, acquisition script, NB01 input contract, and Stage 3 report. Historical deliberation absent from those artifacts is marked `not recoverable`.

# Versão em PTBR

# Título

Adotar o TSA GITV00000000.1 como referência transcriptômica primária versionada do NB01

## Estado

Accepted

## Data

2026-09-11

## Contexto / problema

O NB01 requer um dataset transcriptômico materializado localmente e verificado quanto à integridade como superfície de referência para a reconciliação posterior da identidade dos alvos. O repositório registra no manifest do dataset o accession mestre TSA `GITV00000000`, a versão `GITV00000000.1` e o BioProject `PRJNA579843` de `Dalbulus maidis`.

## Questão sendo decidida

Qual dataset transcriptômico público versionado constitui o input primário de referência do NB01?

## Evidências

O [manifest do dataset](../../../../data/reference/manifest.json) registra a URL de origem no NCBI, o timestamp de aquisição, o caminho local, o tamanho em bytes e o SHA-256. O [script de aquisição](../../../../scripts/fetch_nb01_reference.py) implementa materialização idempotente e rejeição por divergência de integridade. O [Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb) consome o manifest por meio do contrato de inputs existente. O relatório da Etapa 3 registra a mesma versão do dataset e o mesmo SHA-256 como input primário da execução.

## Classificação das evidências

1. `diretamente demonstrado`: accession, versão, BioProject, URL de origem, caminho local, data de aquisição, tamanho do arquivo e SHA-256 estão registrados no manifest. O arquivo foi aceito pelo contrato de inputs do repositório e utilizado pelo relatório da Etapa 3.
2. `derivado/computado`: o SHA-256 e a contagem de registros FASTA da Etapa 3 são medições computacionais do arquivo materializado.
3. `inferido/interpretado`: designar esse TSA materializado como referência primária do NB01 é uma decisão de fluxo de trabalho sustentada pelo manifest, pelo contrato do notebook e pela implementação atual.
4. `não resolvido`: completude do transcriptoma, correção da montagem, representatividade biológica e adequação a todas as questões posteriores permanecem sem validação.

## Alternativas consideradas

`não recuperável`. Nenhum artefato do repositório documenta uma comparação histórica com montagens transcriptômicas alternativas ou referências genômicas.

## Decisão

O NB01 utiliza o TSA `GITV00000000.1` do NCBI, associado ao BioProject `PRJNA579843`, como referência transcriptômica primária versionada. O dataset deve ser obtido exclusivamente por meio do manifest do repositório e deve satisfazer o SHA-256 registrado antes do uso.

## Justificativa

A justificativa recuperável limita-se à existência de um TSA público e versionado de `Dalbulus maidis`, materializado, associado a uma origem estável, verificado por SHA-256 e aceito pelo contrato de inputs do NB01. Qualquer justificativa histórica mais ampla é `não recuperável`.

## Consequências

Os cálculos do NB01 que exigem a referência primária operam sobre o arquivo selecionado pelo manifest. Uma alteração de arquivo, versão da fonte ou accession exige atualização do manifest, validação de integridade e revisão da comparabilidade com resultados anteriores.

## Limitações

A integridade do artefato verifica a identidade do arquivo. Ela não valida completude da montagem, correção da anotação, cobertura de tecidos, resolução de isoformas ou adequação biológica.

## O que esta decisão NÃO estabelece

Esta decisão não estabelece identidade dos alvos, ausência dos alvos, função biológica, completude das sequências ou validade científica das associações posteriores.

## Condições de falseamento / revisão

Revise esta decisão se o accession for corrigido ou substituído, se o hash registrado não puder ser reproduzido, se o arquivo falhar na validação estrutural, se metadados públicos contradisserem o organismo ou projeto declarado, ou se evidência documentada demonstrar que outra referência é necessária para o objetivo delimitado do NB01.

## Notebook relacionado

[Notebook 01](../notebooks/01_reference_dataset_and_target_identity.ipynb)

## Dataset / artefato relacionado

[Manifest do dataset](../../../../data/reference/manifest.json) e caminho local `data/external/tsa.GITV.1.fsa_nt.gz`

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não commitado`

## Proveniência

Este ADR retrospectivo foi reconstruído em 2026-09-11 a partir do manifest atual, do script de aquisição, do contrato de inputs do NB01 e do relatório da Etapa 3. A deliberação histórica ausente nesses artefatos está marcada como `não recuperável`.
