# B6_GOVERNANCE_AMENDMENT_A1

Data: 2026/10/14

B6 original = RESOLVED_AFTER_INDEPENDENT_AUDIT, conforme o ledger fornecido pelo projeto.

B6_GOVERNANCE_AMENDMENT_A1 = PROPOSED_FOR_INDEPENDENT_AUDIT

Natureza: amendment documental de governança. Sua redação não declara METHODOLOGICAL_CONTRACT_APPROVAL, G0_PASS ou certificação de qualquer gate.

## 1. Substituição normativa e preservação histórica

Após auditoria independente documentada do amendment e adoção pela autoridade do projeto, A1 constitui a referência vigente de governança para o escopo NB04 e o complemento normativo do PLAN v2.2.5. A auditoria documental de A1 não cria obrigação de staffing humano externo anterior à aprovação metodológica.

A1 substitui normativamente GOV02, GOV04 a GOV15 e GOV17 exclusivamente nas matérias de staffing, cargos fixos, pré atribuição de pessoas, segunda revisão automática, adjudicação separada, avaliação administrativa de COI e registros de governança. A substituição alcança as disposições equivalentes do B6_METHOD_DECISION_MEMO.md, as respostas correspondentes de B6 e suas referências no PLAN.

Permanecem vigentes os requisitos científicos e técnicos incorporados nesses trechos, incluindo admissibilidade, escopo, revisão das unidades requeridas, fundamentação das disposições, proveniência e preservação de versões.

O pacote B6 original permanece inalterado como registro histórico. Os seguintes sete TSVs conservam seus bytes e recebem, por este registro externo de aplicabilidade, a classificação SUPERSEDED_FOR_CURRENT_SCOPE como instrumentos normativos de governança:

1. b6_role_registry.tsv
2. b6_competency_matrix.tsv
3. b6_review_governance_matrix.tsv
4. b6_disagreement_resolution.tsv
5. b6_signoff_contract.tsv
6. b6_review_workflow.tsv
7. b6_amendment_matrix.tsv

Essa classificação terá efeito com a adoção de A1. Os registros de fontes, evidências metodológicas e verificações históricas de B6 permanecem preservados. As matrizes antigas não constituem requisitos operacionais adicionais após a adoção.

## 2. Governança humana mínima do NB04

O responsável principal do Dry Lab pode executar, verificar, interpretar, emitir as disposições científicas permitidas por B5 e documentar o trabalho. A revisão humana de toda unidade requerida por B5 permanece obrigatória e pode ser realizada por esse responsável.

Não são exigidos cargos permanentes, pré atribuição de pessoas, quórum, votação, segunda revisão automática ou adjudicador separado. A autoria da query, a execução da análise e a emissão de uma disposição científica não ativam, por si mesmas, uma segunda revisão adicional.

Uma pessoa externa qualificada será necessária quando o contrato do gate explicitamente exigir revisão humana independente.

Nessa situação, uma pessoa distinta do produtor principal e com competência pertinente examina o pacote antes da certificação. A revisão independente não pode examinar como independente um objeto produzido pela própria pessoa. Participação prévia e interesses relevantes são declarados no parecer. Interesses incompatíveis com independência tornam esse parecer insuficiente para cumprir o requisito do gate. Não se exige um processo separado de avaliação de COI por terceiro.

A revisão externa registra identidade do revisor, artefato ou pacote e versão examinada, data, parecer fundamentado, limitações e participação ou interesses relevantes. Os hashes e vínculos de evidência já exigidos pelo PLAN e por B5 permanecem obrigatórios.

Uma única revisão externa do pacote pode cumprir a exigência de revisão independente daquele gate. O parecer emitido nesse ato não exige automaticamente outro auditor ou uma adjudicação separada. A mesma pessoa pode revisar gates diferentes quando preservar competência e independência para cada objeto.

Discordância científica material não resolvida pela evidência permanece documentada. Quando a ciência for insuficiente após revisão válida e efetivamente concluída, aplica-se UNRESOLVED conforme B5. A ausência de revisor externo mantém a certificação pendente e não produz UNRESOLVED científico. Defeitos técnicos continuam sujeitos aos respectivos contratos de admissibilidade e certificação.

A ausência de revisão externa requerida bloqueia somente a certificação correspondente e as etapas que dependem dela. A preparação técnica anterior àquele gate pode continuar dentro das autorizações já existentes. As dependências entre checkpoints permanecem vigentes.

Alterações materiais preservam versões anteriores e seguem análise de aplicabilidade conforme o PLAN. Não são criadas exigências automáticas de novo pessoal por alteração, autoria ou tipo de disposição. A revisão externa continua vinculada ao contrato do gate cuja certificação ou nova certificação a exigir.

B3, B4 e B5 permanecem inalterados. As ferramentas de IA podem apoiar o trabalho e a revisão documental. Sua utilização não constitui a participação da pessoa externa nos gates que exigem revisão humana independente.

## 3. Certificações com exigência explícita neste amendment

Este mapeamento preserva os pontos de auditoria independente do PLAN, com a seguinte definição explícita de participação humana externa:

1. G0: revisão independente dos artefatos CP0, sua conformidade com o contrato, proveniência por query, sobreposições e assessability preliminar. Base: PLAN §J.0, etapa 8, §J.3 e Verification.
2. G1: revisão independente dos recursos, assessability final, configuração, calibração, preservação dos hashes G0, separação de fixtures e demonstração de truncamento. Base: PLAN Verification.
3. G2: revisão independente das semânticas de contagem, ocorrências, completude formal e separação entre análises canônicas e de sensibilidade. Base: PLAN Verification.
4. G3: revisão independente dos contratos HSP, reconstrução, campos de orientação, configuração executada e limites de recuperação e relato. Base: PLAN Verification.
5. G5: revisão independente do pacote de interpretações e disposições humanas, incluindo fundamentos de concern e ausência, atribuição, contaminação, lacunas e citações de sensibilidade pertinentes. Base: PLAN Verification.
6. G6: revisão independente da integridade, completude, contraste 1253/1254, estado terminal e limites das conclusões. Base: PLAN Verification.

G4 conserva todas as verificações técnicas e documentais de §J.2 e a conferência de §O, etapa 14. A existência de G4 e a expressão Audit G4 não estabelecem, neste amendment, obrigação de uma pessoa externa. Essa conferência pode ser realizada e documentada pelo responsável principal.

Antes de METHODOLOGICAL_CONTRACT_APPROVAL, a revisão de consistência do contrato pode ser realizada pelo responsável principal com ferramentas de apoio. Essa fase não exige a disponibilidade ou pré atribuição de uma pessoa externa. Nenhum outro gate adquire exigência de revisão humana independente apenas por ser um gate.

## 4. Substituições pontuais do PLAN e de N15

As substituições abaixo são aplicadas como complemento normativo ao PLAN v2.2.5. A cópia histórica do PLAN permanece preservada.

### N15 em §N

N15 — External review requirement

Para qualquer gate cujo contrato exija revisão humana independente, registrar um revisor externo qualificado antes da certificação daquele gate. A pessoa não precisa ser pré atribuída antes do METHODOLOGICAL_CONTRACT_APPROVAL ou de CP0. A ausência de revisor bloqueia somente a certificação correspondente e as etapas que dependem dela. O responsável principal do Dry Lab registra o parecer recebido.

### G0 FREEZE BLOCKERS

Retirar a linha que torna N15 um blocker de staffing anterior à aprovação. Aplicar a seguinte nota à lista:

A política de governança é definida pelo amendment A1 adotado. A disponibilidade de revisor externo é verificada somente na certificação que explicitamente exige revisão humana independente. N15 deixa de ser blocker anterior a CP0. Os demais requisitos metodológicos e técnicos permanecem vigentes.

### §J.2, condição de parada de CP0

Substituir review responsibility unassigned por:

Parecer externo independente requerido para G0 ainda ausente ou insuficiente: certificação G0 pendente. A preparação dos artefatos CP0 permanece permitida após aprovação metodológica e autorização aplicável.

### §J.3, responsabilidades de revisão e auditoria

Substituir a exigência de atribuição antecipada de responsabilidades por:

Responsabilidade principal do Dry Lab e política de revisão humana independente por gate conforme A1, sem matriz fixa de cargos ou pré atribuição de pessoas.

### §O, etapas 6 e 7

Na etapa 6, substituir a resolução nominal de N15 por:

Define a política de revisão por gate. A identificação do revisor externo ocorre antes da certificação pertinente. O trabalho continua como minuta, sem certificação de artefatos.

Substituir a etapa 7 por:

Revisão documentada da consistência entre literatura, landscape, painel e contrato pelo responsável principal, com ferramentas de apoio quando úteis. Conservam-se os objetos e critérios de verificação previstos. A disponibilidade de pessoa externa não é requisito desta etapa.

### Verification e READY / NOT READY MATRIX

Separar a revisão anterior à aprovação dos pontos de revisão independente de certificação. Na fase anterior à aprovação, aplicar a revisão de consistência descrita acima. Para as certificações, aplicar a lista explícita da seção 3 de A1, conservando os demais requisitos de Verification.

Na matriz de readiness e nas referências gerais aos blockers, retirar N15 como motivo de bloqueio anterior a CP0. A aprovação metodológica e os demais requisitos pertinentes permanecem necessários. A identificação de revisor externo é obrigação localizada no gate correspondente.

## 5. Consequências e limites

Após adoção de A1, a falta de pessoa externa deixa de impedir METHODOLOGICAL_CONTRACT_APPROVAL por staffing. Essa aprovação continua sendo um ato explícito do projeto, condicionado aos demais requisitos. CP0 formal continua condicionado à aprovação e à autorização pertinentes.

G0 continua exigindo seu parecer externo independente. Sem G0_PASS, continuam vedados CP1, aquisição de payloads e inspeção de resultados reais NTO, conforme §J.0 e §J.0a. Nos demais gates, a falta de parecer requerido impede a certificação e as etapas dependentes, preservando o trabalho técnico anterior e os registros válidos.

Permanecem os contratos científicos de B3, B4 e B5, incluindo R05, R16, admissibilidade, regras de ausência, unidade query × organismo, obrigações CORE, separação entre trigger e concern, tratamento de sensibilidade e proibição de thresholds, scores e decisões científicas automáticas.

A1 altera as garantias procedimentais de revisão e staffing. Sua adoção não comprova correção científica de um resultado, não reescreve certificações anteriores e não declara gates satisfeitos. O estado PROPOSED_FOR_INDEPENDENT_AUDIT permanece até a auditoria documental independente e a decisão de adoção.

## 6. Fontes de referência

[PLAN v2.2.5 recuperado do texto fornecido pelo usuário](C:/Users/Daniel/.codex/visualizations/2026/10/14/01a1386c-2baf-7bb2-819c-e771903471c2/PLAN_v2_2_5_source.md)

[B6 histórico, GOV17](C:/Users/Daniel/.codex/visualizations/2026/10/13/01a132b0-ea82-74d0-be04-3039b3927a07/B6_REVIEW/B6_GOVERNANCE_REVIEW.md:347)

[B5, delimitação da governança em §13](C:/Users/Daniel/.codex/visualizations/2026/10/13/01a132b0-ea82-74d0-be04-3039b3927a07/B5_REVIEW/B5_CONCERN_CRITERIA_REVIEW.md:251)
