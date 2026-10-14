# Relatórios de modelagem

Esta pasta reúne os relatórios de fundamentação e as decisões metodológicas dos
submodelos de degradação e exposição ao dsRNA (M1), dose–knockdown–efeito (M2) e
dinâmica temporal de dsRNase-2 (M3). As revisões de 13 de outubro de 2026 documentam
como tratar parâmetros ausentes por meio de hipóteses explícitas, análise de
identificabilidade, cenários de sensibilidade e prioridades experimentais.
Elas não estabelecem uma calibração quantitativa concluída nem um intervalo ótimo
validado.

## Decisões e inventários de 13 de outubro de 2026

| Submodelo | Relatório | Conteúdo |
| --- | --- | --- |
| M1 | [Decisões de degradação e AUC](Decisoes_M1_degradacao_AUC.md) | Taxa aparente ex vivo, censura e limite de detecção, AUC relativa e absoluta, condições para ajuste e integração. |
| M2 | [Dose, knockdown e efeito](Relatorio_M2_dose_knockdown_efeito.md) | Registro de 29 parâmetros e campos, correções de evidências, identificabilidade da curva de Hill e ligação com efeito reprodutivo. |
| M3 | [Decisões do submodelo temporal de dsRNase-2](Decisoes_M3_temporal_dsRNase2.md) | Dinâmica candidata do transcrito, acoplamento à degradação, atraso funcional, regimes de administração e sensibilidade. |

As ações propostas dentro dos relatórios permanecem como decisões e trabalho
futuro. A inclusão destes documentos não executa ajustes, simulações ou mudanças
no banco de evidências e não libera parâmetros para uso quantitativo. Menções a
datasets, scripts e arquivos de parâmetros nos textos pertencem ao contexto dos
documentos de origem e não garantem a presença desses artefatos neste repositório.

## Relatórios anteriores de 11 de setembro de 2026

Os relatórios anteriores são preservados como histórico da fundamentação. As
revisões acima registram decisões posteriores e, no M2, correções explícitas de
valores, autoria e interpretação do ensaio de BicC.

- [Degradação de dsRNA e exposição acumulada](BioGuard_Tales_Degradacao_dsRNA_AUC.md)
- [Dose–knockdown e curva de Hill](BioGuard_Gabriel_Dose_Knockdown_Hill.md)
- [Base de dados e hipóteses do submodelo temporal dsRNase-2](BioGuard_Marcos_dsRNase2.md)

## Proveniência da conversão

Os três relatórios foram convertidos dos DOCX fornecidos, preservando o conteúdo
do corpo, a ordem de parágrafos e tabelas, as referências, os links e a notação
científica. As alterações de apresentação se limitam à hierarquia de títulos,
formatação Markdown, listas e representação das equações. Nas duas equações em
LaTeX do M2, as barras invertidas duplicadas no DOCX foram normalizadas para
renderização matemática. Cabeçalhos e rodapés de paginação não são reproduzidos.
Os DOCX originais não fazem parte desta inclusão.

| Markdown | DOCX de origem | SHA-256 do DOCX |
| --- | --- | --- |
| `Decisoes_M1_degradacao_AUC.md` | `Decisoes_metodologia_submodelo_M1_degradacao_AUC_modelo_Marcos.docx` | `ec2bd3085492ad1c4cd491f8462ed7876a25a63043935e66847dd198105e01eb` |
| `Relatorio_M2_dose_knockdown_efeito.md` | `Relatório técnico M2 — Dose, knockdown e efeito (BioGuard).docx` | `f2b60cc1cff0713db20a913330288e10ba3bc8cd5e766efeb76afc5426c689e5` |
| `Decisoes_M3_temporal_dsRNase2.md` | `Decisoes_submodelo_temporal_dsRNase2_Marcos (6).docx` | `018fc18401799b1f5a52f1e6c6918d93a1cffb6d2272e529f25ba02021b425d5` |

As afirmações científicas e as ressalvas de acesso às fontes são as dos autores
dos DOCX. A conversão não constitui uma nova revisão bibliográfica. Em particular,
os relatos de acesso ao artigo de 2023 diferem entre documentos; essa diferença
foi mantida para preservar a proveniência de cada relatório.
