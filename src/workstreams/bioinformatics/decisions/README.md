# Bioinformatics methodological decisions

This directory stores Architecture Decision Records for significant methodological or computational decisions in the Bioinformatics workstream.

The governing distinction is:

`DECISION -> ADR`

`EXECUTION -> Run Record`

An ADR is appropriate when a choice changes how scientific evidence is selected, transformed, classified, interpreted, or made reproducible. Examples include selection of a primary reference dataset, target identity policy, classification criteria, tool choice, and changes that alter the scientific meaning of outputs.

An ADR is not created automatically for routine execution, commits, ordinary notebook runs, behavior preserving refactors, mechanical corrections, or documentation maintenance. Those events receive a Run Record only when retaining execution context is necessary.

## Evidence discipline

Each ADR classifies its claims as `directly demonstrated`, `derived/computed`, `inferred/interpreted`, or `unresolved`. A claim must retain the weakest classification supported by its evidence. Missing evidence remains `unresolved`.

A successful execution demonstrates completion of declared computational checks only. It does not demonstrate scientific validity. Computational reproducibility does not establish scientific validity. A computational association remains an association until the declared identity evidence is sufficient. Absence of evidence remains `UNRESOLVED`.

## Lifecycle and naming

Use zero padded sequential names such as `0001-short-title.md`. Start from [0000-adr-template.md](0000-adr-template.md). Valid initial statuses are `Proposed` and `Accepted`. Later records may use `Superseded`, `Rejected`, or `Deprecated`, with links to the replacing decision when applicable.

Current records:

1. [0001 NB01 primary reference dataset](0001-nb01-primary-reference-dataset.md)
2. [0002 NB01 target anchor policy](0002-nb01-target-anchor-policy.md)
3. [0003 NB01 target identity resolution policy](0003-nb01-target-identity-resolution-policy.md)
4. [0004 NB01 dsRNase-2 identity criteria](0004-nb01-dsrnase2-identity-criteria.md)
5. [0005 NB02 dsRNase-2 candidate region policy](0005-nb02-dsrnase2-candidate-region-policy.md)
6. [0006 NB03 BicC candidate region policy](0006-nb03-bicc-candidate-region-policy.md)
7. [0007 NB04 NTO sequence specificity policy](0007-nb04-nto-sequence-specificity-policy.md)

## Governance amendment A1

[B6_GOVERNANCE_AMENDMENT_A1.md](B6_GOVERNANCE_AMENDMENT_A1.md) — governance amendment A1. State: `ADOPTED_AFTER_INDEPENDENT_AUDIT`. Canonical `SHA256 9EA167A88359F78E916D753865D7D40A5C37D2FF04D3A09D73C647C3AEBAA62B`.

The materialised file preserves the audited bytes exactly, including its internal historical status line `PROPOSED_FOR_INDEPENDENT_AUDIT`. Adoption is recorded here rather than by editing the audited document, and the directory `.gitattributes` marks the file `-text` so its bytes are never rewritten by end-of-line normalisation.

A1 is a documentary governance amendment. It prevails only in the matters it explicitly supersedes: staffing, fixed roles, pre-assignment of people, automatic second review, separate adjudication, administrative COI assessment, and governance registries. All other provisions continue to govern unchanged, including the scientific and technical requirements carried in the superseded passages and the contracts of B3, B4 and B5. Adoption of A1 does not declare `METHODOLOGICAL_CONTRACT_APPROVAL`, does not certify any gate, and does not establish scientific validity.

The complete PLAN and the complete B6 baseline are maintained externally to this repository and are not imported here. The available identities are:

| Baseline | Version | Available hash |
| --- | --- | --- |
| PLAN | v2.2.5 | `SHA256 826291FBCB1B88244F5981300704A811670D93B2E9D95B98C78B6F2261E02DF8` — hash of the archived and verified textual representation, not the canonical hash originally supplied by the project |
| B6 review package `PRE_CONTRACT_B6_REVIEW_GOVERNANCE_READY_FOR_INDEPENDENT_AUDIT.zip` | historical baseline | `SHA256 1BEDA7CF4723EBA7193674272ECF0EF8BAE6972FD5F59E812B10941BC78EBC6C` — hash of the verified external package |

The original B6 remains `RESOLVED_AFTER_INDEPENDENT_AUDIT` per the project ledger. The historical ZIP name is preserved as given.

# Versão em PTBR

# Decisões metodológicas de Bioinformática

Este diretório armazena Registros de Decisão Arquitetural para decisões metodológicas ou computacionais significativas do workstream de Bioinformática.

A distinção fundamental é:

`DECISÃO -> ADR`

`EXECUÇÃO -> Run Record`

Um ADR é apropriado quando uma escolha altera a forma como a evidência científica é selecionada, transformada, classificada, interpretada ou tornada reprodutível. Exemplos incluem a seleção de um dataset primário de referência, a política de identidade dos alvos, os critérios de classificação, a escolha de ferramentas e mudanças que alterem o significado científico dos resultados.

Um ADR não é criado automaticamente para execuções rotineiras, commits, execuções normais de notebooks, refatorações que preservem o comportamento, correções mecânicas ou manutenção de documentação. Esses eventos recebem um Run Record somente quando for necessário preservar o contexto da execução.

## Disciplina de evidências

Cada ADR classifica suas afirmações como `diretamente demonstrado`, `derivado/computado`, `inferido/interpretado` ou `não resolvido`. Uma afirmação deve manter a categoria mais fraca sustentada pela evidência disponível. Evidência ausente permanece `não resolvida`.

Uma execução bem sucedida demonstra apenas a conclusão das verificações computacionais declaradas. Ela não demonstra validade científica. Reprodutibilidade computacional não estabelece validade científica. Uma associação computacional permanece uma associação até que a evidência de identidade declarada seja suficiente. Ausência de evidência permanece `UNRESOLVED`.

## Ciclo de vida e nomenclatura

Use nomes sequenciais com preenchimento por zeros, como `0001-titulo-curto.md`. Comece pelo [template de ADR](0000-adr-template.md). Os estados iniciais válidos são `Proposed` e `Accepted`. Registros posteriores podem usar `Superseded`, `Rejected` ou `Deprecated`, com links para a decisão substituta quando aplicável.

Registros atuais:

1. [0001 Dataset primário de referência do NB01](0001-nb01-primary-reference-dataset.md)
2. [0002 Política de âncoras de alvos do NB01](0002-nb01-target-anchor-policy.md)
3. [0003 Política de resolução de identidade dos alvos do NB01](0003-nb01-target-identity-resolution-policy.md)
4. [0004 Critérios de identidade de dsRNase-2 do NB01](0004-nb01-dsrnase2-identity-criteria.md)
5. [0005 Política de regiões candidatas de dsRNase-2 do NB02](0005-nb02-dsrnase2-candidate-region-policy.md)
6. [0006 Política de regiões candidatas de BicC do NB03](0006-nb03-bicc-candidate-region-policy.md)
7. [0007 Política de especificidade de sequência NTO do NB04](0007-nb04-nto-sequence-specificity-policy.md)

## Amendment de governança A1

[B6_GOVERNANCE_AMENDMENT_A1.md](B6_GOVERNANCE_AMENDMENT_A1.md) — amendment de governança A1. Estado: `ADOPTED_AFTER_INDEPENDENT_AUDIT`. `SHA256 9EA167A88359F78E916D753865D7D40A5C37D2FF04D3A09D73C647C3AEBAA62B` canônico.

O arquivo materializado preserva exatamente os bytes auditados, incluindo sua linha de status histórico interno `PROPOSED_FOR_INDEPENDENT_AUDIT`. A adoção é registrada aqui, e não por edição do documento auditado; o `.gitattributes` do diretório marca o arquivo como `-text` para que seus bytes nunca sejam reescritos por normalização de fim de linha.

A1 é um amendment documental de governança. Ele prevalece somente nas matérias que substitui explicitamente: staffing, cargos fixos, pré atribuição de pessoas, segunda revisão automática, adjudicação separada, avaliação administrativa de COI e registros de governança. As demais disposições permanecem vigentes sem alteração, incluindo os requisitos científicos e técnicos contidos nos trechos substituídos e os contratos de B3, B4 e B5. A adoção de A1 não declara `METHODOLOGICAL_CONTRACT_APPROVAL`, não certifica qualquer gate e não estabelece validade científica.

O PLAN completo e o baseline B6 completo são mantidos externamente a este repositório e não são importados aqui. As identidades disponíveis são:

| Baseline | Versão | Hash disponível |
| --- | --- | --- |
| PLAN | v2.2.5 | `SHA256 826291FBCB1B88244F5981300704A811670D93B2E9D95B98C78B6F2261E02DF8` — hash da representação textual arquivada e verificada, não o hash canônico originalmente fornecido pelo projeto |
| Pacote de revisão B6 `PRE_CONTRACT_B6_REVIEW_GOVERNANCE_READY_FOR_INDEPENDENT_AUDIT.zip` | baseline histórico | `SHA256 1BEDA7CF4723EBA7193674272ECF0EF8BAE6972FD5F59E812B10941BC78EBC6C` — hash do pacote externo verificado |

O B6 original permanece `RESOLVED_AFTER_INDEPENDENT_AUDIT` conforme o ledger do projeto. O nome histórico do ZIP é preservado como fornecido.
