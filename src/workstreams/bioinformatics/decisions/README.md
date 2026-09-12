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
