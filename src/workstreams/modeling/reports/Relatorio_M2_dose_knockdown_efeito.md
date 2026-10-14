# BioGuard \| Relatório técnico do submodelo M2

## Dose, knockdown e efeito: curva dose-resposta oral, parâmetros de Hill e ligação com endpoint reprodutivo

*Registro mestre de parâmetros, mapa de lacunas e busca dirigida — construído sobre o relatório M2 de 11/09/2026*

Oct 13, 2026 · @Madame

## 1. Resumo executivo

Este documento é o **registro mestre de parâmetros** do M2, exigido como entregável desta semana. Ele não refaz a análise do relatório de 11/09/2026, que permanece a referência técnica do módulo: assume suas conclusões, formaliza seus símbolos em inventário auditável com classe e representação pretendida, e acrescenta o que a etapa pede — busca dirigida por lacuna, com critério objetivo de encerramento, e encaminhamento das evidências ao Banco.

A conclusão central do módulo é mantida: EC50, Emax e n não são identificáveis para *D. maidis* por via oral. Nada encontrado nesta busca alterou esse diagnóstico.

**Três correções numéricas na base de evidências.** A conferência das fontes primárias de acesso aberto, feita nesta etapa, encontrou divergências em relação ao que o relatório de 11/09 registrou:

1. **O platô oral em Hemiptera é mais baixo do que o anotado.** O relatório registra Emax ≈ 0,3–0,5 a partir de *Diaphorina citri*. O artigo verificado reporta knockdown significativo de 12–34% em ninfas e 18–39% em adultos, em cinco concentrações e três genes. A faixa defensável é, portanto, **≈ 0,12–0,39**, não 0,3–0,5.

2. **A autoria da fonte de** ***D. citri*** **está trocada.** O trabalho é de Saberi et al. (2024); Qureshi é o último autor e correspondente. A citação como "Qureshi et al." precisa ser corrigida no banco e no texto.

3. **O motivo de haver um único nível efetivo de dose em** ***D. maidis*** **é outro.** O relatório diz que 100 e 200 ng/µL "produzem o mesmo KD". O pré-print de acesso aberto declara que a RT-qPCR foi conduzida **somente** na concentração mais alta: a 100 ng/µL não há medida molecular, e não medida igual. A conclusão (um nível efetivo) não muda; a justificativa de R4 muda, e com ela o que se deve pedir ao Wet Lab.

**Uma consequência estrutural das correções.** O knockdown oral observado em *D. maidis* (≈ 0,73 em ovário, dia 7) é **superior** a todo o platô de *D. citri*. Logo, G6 não pode operar como limite superior de Emax na espécie-alvo: o alerta de R2 — não fixar Emax ≈ 1,0 — continua válido, mas a faixa 0,12–0,39 não é um teto transferível. Parte da diferença pode ser de tecido: *D. citri* mede corpo inteiro agrupado; *D. maidis*, ovário dissecado.

| **Decisão operacional desta etapa** Manter o protocolo de ajuste progressivo e a fixação de n = 1 como estão. Reclassificar o prior de *D. citri* de "teto de Emax" para "evidência de que o platô oral pode ser muito inferior a 1", com faixa corrigida. Registrar Emax com piso empírico de 0,73 na espécie-alvo e sem teto estabelecido. Nenhum parâmetro muda de AUSENTE para calibrado. |
| --- |

## 2. Escopo matemático e símbolos a inventariar

Esta seção existe para fixar quais símbolos entram no registro e com que significado. A derivação e a demonstração de não-identificabilidade estão no relatório de 11/09 e não são repetidas.

### 2.1 Forma funcional e endpoint

A forma empírica de trabalho é a Hill, com endpoint único KD = 1 − E\_rel (hipótese G1):

$$
KD(D) = E_{\max}\,\frac{D^{\,n}}{EC_{50}^{\,n} + D^{\,n}}
$$

As conversões para o eixo KD são determinísticas: de fold-change, KD = 1 − 1/FC; de percentual de redução P, KD = P/100. Importa registrar que a conversão **não propaga incerteza**: a dispersão precisa ser transportada à parte, e nas fontes disponíveis ela existe apenas em figura.

### 2.2 Eixo de dose e grandezas incomensuráveis

O eixo D é a concentração de dsRNA na dieta, rota oral apenas (G2, G3). O campo dose\_tipo do dataset é o que torna essa restrição auditável, e por isso entra no inventário como parâmetro de pleno direito:

| dose\_tipo | Unidade | Entra no eixo D? | Razão |
| --- | --- | --- | --- |
| conc\_dieta | ng/µL | Sim | Grandeza-alvo do M2 |
| conc\_injetada | ng/µL | Não | Contorna intestino e degradação; rota fisiologicamente distinta |
| planta\_transgenica | — | Não | Dose ingerida não quantificada |
| µg/planta | µg/planta | Não | Endpoint e matriz diferentes |
| µM (atividade de nuclease) | µM | Não | Pertence ao M1, não é KD |

Uma observação de escopo, não uma proposta de mudança: a concentração na dieta é a variável controlada, não a variável causal. Sob 200 ng/µL nominais, o knockdown em *D. maidis* foi de ≈ 0,73 por via oral e &gt; 0,99 por injeção. A grandeza causal é a exposição interna, que é a saída do M1 (AUC). Enquanto o M1 não entregar AUC com C0 interno resolvido, G2 continua sendo a decisão correta — e o inventário registra a exposição interna como parâmetro ausente de interface, para que a substituição futura do eixo seja rastreável em vez de silenciosa.

### 2.3 Separação entre efeito de dose e efeito de tempo

Nos dados de *D. maidis* o tempo domina (G4). Em BicC oral, o KD vai de 0,615 (dia 1) a 0,730 (dia 7) na mesma dose. Em V-ATPase oral a 500 ng/µL, não há silenciamento significativo no dia 2 e há no dia 4. O registro precisa, portanto, carregar o tempo de leitura ligado a cada valor de KD, e não apenas o KD.

### 2.4 Elo knockdown → efeito fenotípico

O endpoint de controle é reprodutivo, não o transcrito. A ligação é função própria, com parâmetros declarados:

$$
\frac{Ovip(D)}{Ovip_{ctrl}} = 1 - g\bigl(KD(D)\bigr)
$$

O padrão disponível é de limiar, não de proporção. Por via oral, KD ≈ 0,73 acompanhou alteração ovariana em 13,3–27,3% das fêmeas; por injeção, KD &gt; 0,99 produziu o fenótipo em 87,5–100%. A evidência externa reforça e acrescenta uma variável: em *D. citri*, knockdown de 18–39% não produziu mortalidade após 48 h de acesso, mas a mesma faixa de concentração produziu mortalidade significativa sob dez dias de ingestão contínua. Ou seja, **g depende da duração da exposição, não apenas da magnitude do KD** — o que o registro precisa acomodar antes que alguém tente ajustar g com dados de protocolos diferentes.

### 2.5 Condição de identificabilidade

A restrição é aritmética: um modelo de *p* parâmetros livres exige ao menos *p* níveis de dose com respostas distintas, e estimar EC50 e n com incerteza útil exige delimitar a transição dos dois lados do ponto de inflexão.

O relatório de 11/09 quantificou o que acontece quando essa condição não é satisfeita, usando o melhor caso disponível (*D. citri*, 5 doses): na Hill completa, erro-padrão relativo de 759% para EC50 e ≈ 4700% para n, com correlação EC50 ~ n igual a +1,00 e AIC que ainda assim "prefere" o modelo de três parâmetros. Esse resultado é o argumento mais forte do módulo e deve acompanhar o registro: **qualidade de ajuste não protege contra não-identificabilidade**.

A verificação da fonte explica por que a transição não é delimitável nem ali. Em adultos de *D. citri*, 10 e 50 ng/µL não produziram silenciamento significativo e 100, 200 e 500 ng/µL não diferiram entre si — toda a transição está contida no salto de 50 para 100 ng/µL. O IC95% estreito obtido por bootstrap (EC50 ≈ 92 ng/µL, \[66, 98\]) é precisão da grade de doses, não dos dados.

### 2.6 Monotonicidade como hipótese testável

A adequação de uma Hill monotônica é hipótese, não dado (G5). A verificação confirmou e tornou numérica a reversão em dose alta: em ninfas de *D. citri*, o knockdown de CHC deixou de ser significativo a 500 ng/µL após ser de 34,19% a 100 e 32,00% a 200; vATPase-A caiu de 30,95% a 200 para 12,08% a 500. Em adultos a reversão não apareceu. A não-monotonicidade é, portanto, dependente de estágio — o que a torna uma hipótese a testar na espécie-alvo, e não uma propriedade a importar.

### 2.7 Definição do controle e zero da escala

Em todas as fontes utilizáveis o grupo de referência é dsRNA não homólogo em concentração comparável — *β-lactamase* em *D. maidis* (BicC), GFP em *D. maidis* (V-ATPase), luciferase em *D. citri* — e não ausência de dsRNA. O KD = 0 da escala corresponde à presença de dsRNA inespecífico. Isso isola o efeito sequência-específico, que é o desejado, mas deixa fora do escopo do M2 qualquer efeito inespecífico de carga de dsRNA. Em *D. citri* os autores observam toxicidade do próprio controle de luciferase acima de 200 ng/µL, o que mostra que essa ressalva não é formal.

## 3. Critério de classificação dos parâmetros

As classes seguem a definição obrigatória do plano semanal, aplicadas sem flexibilização:

**Medido diretamente.** Valor observado em sistema experimental compatível com a variável do modelo.

**Derivado.** Valor obtido por transformação matemática explícita de uma medida ou conjunto de medidas.

**Transferido.** Valor obtido em outra espécie, matriz, rota ou contexto, usado com limitação declarada de transferibilidade.

**Estimável pelo ajuste.** Parâmetro sem valor direto, inferível de uma série de dados adequada ao modelo. Em M2 a palavra operante é *adequada*: um parâmetro só recebe esta classe se o número de níveis de dose distintos satisfizer a condição de identificabilidade da seção 2.4.

**Assumido para análise de sensibilidade.** Valor ou faixa usada para explorar o comportamento do modelo quando a evidência é insuficiente.

**Ausente.** Lacuna sem evidência ou estratégia consolidada; permanece como bloqueador explícito.

### Dimensão adicional: papel do parâmetro

A classe de evidência não diz onde o parâmetro atua. No M2 convivem cinco papéis distintos, e confundi-los produz substituições indevidas entre grandezas incompatíveis:

| Papel | O que é | Exemplo em M2 |
| --- | --- | --- |
| Parâmetro de forma da curva | Define a geometria da resposta | EC50, Emax, n |
| Condição de exposição | Descreve o que foi administrado | Concentração na dieta, duração, renovação |
| Parâmetro de interface entre módulos | Liga M2 a M1 ou M3 | Exposição interna (AUC), fator de co-feeding |
| Processo de observação | Pertence ao método, não à biologia | Tempo de leitura, tecido amostrado, gene normalizador, identidade do controle |
| Saída derivada | Calculada a partir das anteriores | Knockdown fracionário, redução relativa de oviposição |

Uma consequência prática: o tempo de leitura do knockdown é parâmetro do processo de observação, não constante biológica. Um EC50 estimado a partir de leitura no dia 7 não é comparável a um estimado no dia 1, porque o knockdown ainda está em instalação.

## 4. Registro mestre de parâmetros

Todo símbolo das equações da seção 2 está abaixo, somado às condições de exposição, aos parâmetros do processo de observação, aos priors externos e aos campos de controle do dataset. Todos pertencem ao submodelo M2; a transferibilidade está declarada na última coluna junto ao uso permitido.

### 4.1 Parâmetros de forma da curva

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-01 | EC50 — dose que produz metade de Emax | ng/µL (dieta, oral) | **Ausente** | Sem valor para *D. maidis*. Prior externo: ≈ 92 ng/µL em *D. citri*, IC95% \[66, 98\] — precisão da grade de doses, não dos dados | Limite ou faixa condicional, nunca valor nominal | Não usar em modelo. Transferibilidade indireta. Fechar com curva oral de ≥ 5 doses na espécie-alvo |
| M2-02 | Emax — platô de silenciamento | adimensional, 0–1 | **Ausente** | Piso empírico 0,73 (*D. maidis*, BicC, ovário, dia 7). Teto não estabelecido | Cenários com piso em 0,73 | Não fixar em 1,0 (R2). Não usar a faixa de *D. citri* como teto — ela é inferior ao já observado na espécie-alvo |
| M2-03 | n — coeficiente de Hill | adimensional | **Ausente / não identificável** | Nenhuma estimativa local. Na Hill completa de *D. citri*, n = 20 ± 942 | Fixado em 1 (G7); varrido em sensibilidade | Fixar n = 1. Liberar apenas com pontos dentro da transição |
| M2-04 | KD(D) — knockdown fracionário | adimensional, 0–1 | Derivado (definição operacional, G1) | KD = 1 − E\_rel, com conversões de fold-change e de percentual | Função, não valor | Endpoint único do eixo y. Não misturar com 2^−ΔΔCt bruto, fold-change ou transcrito absoluto |

### 4.2 Eixo de dose e exposição

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-05 | D — concentração de dsRNA na dieta | ng/µL | Medido | *D. maidis*: 100 e 200 (BicC, fêmeas adultas); 500 (V-ATPase B e D, ninfas de 3º ínstar) | Níveis discretos observados | Eixo operacional do M2 (G2). Não é concentração interna. Os dois conjuntos são de genes e estágios distintos e não formam uma curva |
| M2-06 | dose\_tipo — classificador de comensurabilidade | categórico | Medido (metadado) | conc\_dieta, conc\_injetada, planta\_transgenica, µg/planta, µM | Campo obrigatório por observação | Filtro de elegibilidade: só conc\_dieta entra no ajuste (G3) |
| M2-07 | x\_int — exposição interna efetiva | h (AUC\_norm) ou ng·h/µL | **Ausente** — interface com M1 | Nenhuma quantificação de dsRNA interno por inseto ou tecido | Substituição futura do eixo D | Não implementar antes de o M1 entregar AUC. Mesma lacuna que C0\_eff no M1 — não duplicar a busca |
| M2-08 | t\_exposicao — duração da exposição | dias | Medido | BicC: 3 dias com renovação diária. V-ATPase: 4 dias, renovação a cada 24 h. *D. citri*: 48 h, ou 10 dias contínuos no ensaio de mortalidade | Metadado obrigatório por ponto | Pontos com durações diferentes não são comparáveis no mesmo eixo, mesmo com a mesma concentração |

### 4.3 Tempo

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-09 | t\_medicao\_KD — tempo de leitura do knockdown | dias | Medido (processo de observação) | BicC: 1 e 7 d após o fim da administração. V-ATPase: 2 e 4 d. *D. citri*: 5 d após o período de acesso | Endpoint temporal fixado: dia 7 para BicC (G4) | Todo KD e todo EC50 reportado vem indexado ao tempo de leitura |
| M2-10 | t\_delay — latência do silenciamento | dias | Estimável por ajuste, condicionado | V-ATPase oral a 500 ng/µL: sem redução significativa no dia 2, significativa no dia 4 (p = 0,012 e 0,010) | Faixa, entre 2 e 4 dias | Não ajustar nesta etapa. É o único parâmetro temporal com suporte direcional na espécie-alvo |
| M2-11 | Duração e recuperação do knockdown | dias | **Ausente** | Nenhuma leitura molecular além de 7 dias em *D. maidis* | — | Lacuna compartilhada com o M3; coordenar o pedido ao Wet Lab |

### 4.4 Processo de observação

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-12 | endpoint\_original — forma em que o KD foi reportado | categórico | Medido (processo) | expressão relativa, fold-change, % de redução, e descrições qualitativas | Campo do dataset, com conversão explícita | Registros qualitativos permanecem não elegíveis e não são convertidos em número |
| M2-13 | Controle de referência | categórico | Medido (processo) | *β-lactamase* (BicC), GFP (V-ATPase), luciferase (*D. citri*) | Metadado por ponto | O zero da escala é dsRNA inespecífico, não ausência de dsRNA |
| M2-14 | Gene normalizador e tecido amostrado | categórico | Medido (processo) | Dmai-Act1 em ovário dissecado (BicC); ETF em corpo inteiro agrupado (V-ATPase); RPL5 em pool (*D. citri*) | Metadado por ponto | KD de ovário e de corpo inteiro não são o mesmo observável e não vão ao mesmo eixo |
| M2-15 | dsRNA\_bp — comprimento do construto | pb | Parcial | BicC 372 pb; *D. citri* 147, 153 e 194 pb; V-ATPase B/D em *D. maidis* não localizado | Metadado por ponto | Afeta a eficiência de RNAi. Negligenciado na v1 por falta de dados — simplificação declarada, não ignorada |
| M2-16 | n\_biologico — réplicas biológicas | contagem | Medido parcialmente | BicC: 3 réplicas. V-ATPase: 3 réplicas de pools de 3 insetos. *D. citri*: 3 réplicas de pools de 5, com 3 réplicas técnicas cada | Contagem explícita por ponto | Pool conta como uma réplica biológica (G8). Réplica técnica nunca entra como observação independente |
| M2-17 | Dispersão do KD (SD, SE ou IC) | mesma unidade do KD | **Insuficiente** | 2 de 72 pares do Banco v2 têm n e incerteza registrados; o restante existe apenas em figura | Faixa declarada, não distribuição | Bloqueia Monte Carlo. Fechar por digitalização ou pela fonte |

### 4.5 Efeito fenotípico

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-18 | Ovip\_ctrl e Ovip(D) — oviposição | ovos/fêmea | Estimável por digitalização | Somente em figura; são valores preditos por GLMM binomial negativo com fêmea como efeito aleatório | Médias e SE por tratamento | Digitalizar. Registrar que são preditos pelo modelo, não médias brutas |
| M2-19 | ΔOvip — redução relativa de oviposição | adimensional | Derivado | 1 − Ovip(D)/Ovip\_ctrl | Valor por dose e rota | Primeira saída fenotípica quantitativa do M2 |
| M2-20 | p\_ov — proporção com fenótipo ovariano | proporção | Medido | Oral: 13,3% a 100 ng/µL e 27,3% a 200. Injeção: 87,5% e 100% | Proporção por dose | Único endpoint oral com dois níveis e resposta monotônica. Falta o n por grupo antes de qualquer ajuste |
| M2-21 | β\_KD→ovos, com KD50 e m — função g | adimensional | **Ausente** | Evidência de limiar sem nenhum par (KD, efeito) medido no mesmo experimento | Estrutura declarada, parâmetros vazios | Não ajustar. Fechar extraindo KD e oviposição do mesmo experimento e da mesma coorte |
| M2-22 | Mortalidade | proporção | Medido | BicC: sem diferença (oral p = 0,1406; injeção p = 0,9475). V-ATPase oral: sobrevivência de 16–18% contra 37% no controle GFP e 52% sem dsRNA | Por alvo, nunca global | Excluir do M2 para BicC. A alta mortalidade dos próprios controles no ensaio de V-ATPase limita seu uso quantitativo |
| M2-23 | Viabilidade dos ovos | proporção | Medido qualitativamente | Injeção: nenhum ovo eclodiu. Oral: a maioria atingiu o primeiro ínstar | Qualitativo | Esterilidade é fenômeno da rota injetada. O endpoint oral é quantidade de postura |

### 4.6 Priors externos e campos de controle

| ID | Símbolo e definição | Unidade | Classe | Valor ou faixa atual, e origem | Representação pretendida | Uso permitido e ação restante |
| --- | --- | --- | --- | --- | --- | --- |
| M2-24 | Emax\_prior — platô oral em Hemiptera | adimensional | **Transferido** | *D. citri*, 3 genes, 5 doses: 12–34% em ninfas e 18–39% em adultos | Prior fraco, como faixa | Transferibilidade indireta. Serve como evidência de que o platô pode ser muito inferior a 1. **Não** é teto para *D. maidis*, cujo valor oral observado já o excede |
| M2-25 | Limiar de resposta oral | ng/µL | **Transferido** | Adultos de *D. citri*: nada significativo a 10 e 50 ng/µL; significativo a partir de 100 | Prior fraco | Usar para desenhar a grade de doses do Wet Lab, nunca para calibrar |
| M2-26 | Reversão em dose alta | — | **Transferido** / hipótese estrutural | Ninfas de *D. citri*: CHC perde significância a 500 ng/µL; vATPase-A cai de 30,95% (200) para 12,08% (500). Em adultos a reversão não aparece | Hipótese a testar | Impede assumir monotonicidade por padrão (G5). O efeito é dependente de estágio |
| M2-27 | Faixa efetiva em outros hemípteros | ng/µL | **Transferido** | *P. stali*: ≈ 50% de knockdown apenas a 5000 ng/µL, sem resposta a 100 e 1000 | Prior fraco | Mostra que a faixa efetiva varia por ordens de grandeza dentro da ordem. Reforça que EC50 não se transfere |
| M2-28 | α\_cof — ganho por co-feeding com anti-dsRNase | adimensional | **Ausente** — pertence a M1/M3 | Direção do efeito estabelecida; magnitude inacessível (fonte paga) | Fator sobre a exposição, não sobre KD | Não é parâmetro de calibração do M2. Registrado para que a interface seja explícita |
| M2-29 | usar\_em\_modelo — liberação para uso quantitativo | booleano | Medido (estado do Banco v2) | sim em 0 das 41 linhas | Campo de controle | Nenhum parâmetro do M2 está liberado. O campo só muda após verificação humana, conforme o Guia v2 |

**Conversões aplicadas.** Os valores de KD de *D. maidis* vêm de fold-change por KD = 1 − 1/FC: 2,6× → 0,615 e 3,7× → 0,730 na via oral; 3,2× → 0,688 e &gt; 170× → &gt; 0,994 por injeção. A legenda da figura original indica normalização em relação ao controle do dia 1, o que altera o denominador do ponto de dia 7 — conferir antes de fixar esses valores no dataset.

## 5. Contextos experimentais e o que cada um autoriza

As fontes do dataset reconstruído estão agrupadas aqui pelo papel que exercem no registro. A verificação desta etapa cobriu as quatro fontes de acesso aberto; o que foi conferido e o que não foi está marcado.

### 5.1 *D. maidis*, BicC, via oral — população-alvo

[Dalaisón-Fuentes et al. (2022)](<https://www.biorxiv.org/content/10.1101/2022.01.17.476645v1.full>) · **verificado no pré-print aberto**

Fêmeas adultas recém-emergidas em câmaras de alimentação com dieta de sacarose a 10%; dsRNA adicionado 24 h depois e renovado diariamente por três dias; depois cada fêmea isolada com um macho sobre milho, com mortalidade e oviposição registradas a cada 48 h e ovários dissecados no dia 18.

| Elo | Medida | 100 ng/µL | 200 ng/µL |
| --- | --- | --- | --- |
| Transcrito (ovário) | Redução de Dmai-BicC, dia 1 | não medido | 2,6× → KD ≈ 0,615 |
| Transcrito (ovário) | Redução de Dmai-BicC, dia 7 | não medido | 3,7× → KD ≈ 0,730 |
| Fenótipo celular | Fêmeas com alteração ovariana | 13,3% | 27,3% |
| Fenótipo reprodutivo | Oviposição | redução significativa | redução significativa, sem diferir de 100 ng/µL |
| Viabilidade da prole | Eclosão | maioria atingiu o 1º ínstar | maioria atingiu o 1º ínstar |
| Sobrevivência | Mortalidade das fêmeas | sem diferença (p = 0,1406) | sem diferença |

**O ponto que corrige o dataset.** A linha "não medido" a 100 ng/µL não é uma lacuna de extração: os autores declaram que optaram por avaliar a expressão somente na concentração mais alta. O registro de 11/09 trata 100 e 200 ng/µL como duas doses que produziram o mesmo KD; na prática não há ponto molecular em 100. Isso não muda a conclusão de não-identificabilidade — continua havendo um único nível efetivo —, mas muda duas coisas práticas: R4 deve ser rejustificada, e o pedido ao Wet Lab passa a incluir medir o que já foi administrado, e não só administrar doses novas.

A eclosão também delimita o endpoint. Por via oral o efeito aparece como menos ovos, mas os ovos postos são viáveis; esterilidade é fenômeno da rota injetada e não deve ser transportada para a rota oral.

### 5.2 *D. maidis*, V-ATPase B e D, via oral — segunda fonte na espécie-alvo

[Jones-Bernal et al. (2021)](<https://www.biorxiv.org/content/10.1101/2021.09.29.462424v1.full>) · **verificado no pré-print aberto**

Ninfas de 3º ínstar, dieta D-10, dsRNA a 500 ng/µL renovado a cada 24 h, leituras nos dias 2 e 4. Três réplicas independentes por tratamento e tempo, cada uma um pool de três insetos; normalização por ETF, controle de dsRNA-GFP.

O resultado relevante é temporal, não de dose. A ANOVA não detectou efeito de gene, de dia nem de interação; o que foi significativo foram os testes de uma amostra contra a razão 1,0, apenas no dia 4 (p = 0,012 para a subunidade B e 0,010 para a D). Daí a latência registrada em M2-10. **O artigo não reporta um percentual numérico de knockdown** — as razões aparecem só em figura, o que mantém este ponto como estimável por digitalização e não como medido.

Dois cuidados antes de usar esta fonte. Primeiro, é outro gene, outro estágio de vida, outro tecido e outro normalizador: 500 ng/µL aqui **não** é um terceiro ponto da curva de BicC. Segundo, a sobrevivência em 4 dias foi de ≈ 16% (V-ATPase B) e ≈ 18% (D) contra ≈ 37% no controle de GFP e ≈ 52% sem dsRNA — ou seja, os próprios controles perdem metade dos insetos, o que limita o uso quantitativo do endpoint de mortalidade neste delineamento.

### 5.3 Rotas fora do eixo D

A microinjeção de dsRNA^BicC produziu KD ≈ 0,688 no dia 1 e &gt; 0,994 no dia 7, oviposição próxima de zero com separação entre as duas doses, nenhum ovo eclodido e fenótipo ovariano em 87,5% e 100% das fêmeas. Por R3 esses pontos não entram no eixo D. O que eles estabelecem é que a maquinaria de RNAi da espécie alcança silenciamento quase completo — portanto a limitação da rota oral está entre a oferta e o compartimento, que é escopo do M1 e do M3, e não um teto da maquinaria.

O mesmo vale para os registros de planta transgênica em *N. lugens* (knockdown de 42–73% sem dose absoluta): sem dose quantificada, não há posição no eixo.

### 5.4 *D. citri* — a única curva oral multi-dose em Hemiptera

[Saberi, Mondal, Paredes-Montero, Nawaz, Brown e Qureshi (2024)](<https://doi.org/10.3390/insects15010058>) · **verificado no texto completo (MDPI, acesso aberto)**

A verificação confirmou o desenho e corrigiu os números. Cinco concentrações (10, 50, 100, 200, 500 ng/µL) em sacarose a 20%, 48 h de acesso, depois 5 dias em brotos de *Murraya paniculata* antes da qPCR; três réplicas biológicas, cada uma um pool de cinco insetos com três réplicas técnicas; normalizador RPL5; controle de dsRNA-luciferase na mesma concentração; construtos de 147, 153 e 194 pb.

| Gene | Estágio | 10 | 50 | 100 | 200 | 500 |
| --- | --- | --- | --- | --- | --- | --- |
| CHC | adultos | n.s. | n.s. | 36,41% | 37,24% | 38,37% |
| vATPase-A | adultos | n.s. | n.s. | 24,19% | 25,14% | 22,02% |
| Snf7 | adultos | n.s. | n.s. | 18,46% | 29,79% | 26,73% |
| CHC | ninfas | 17,58% | 19,99% | 34,19% | 32,00% | n.s. |
| vATPase-A | ninfas | n.s. | n.s. | 21,74% | 30,95% | 12,08% |
| Snf7 | ninfas | n.s. | n.s. | 16,40% | 20,52% | 16,42% |

Três leituras saem daí. **Primeira:** o platô é de 0,18–0,39 em adultos e 0,12–0,34 em ninfas — mais baixo que os 0,3–0,5 registrados, e muito abaixo dos 0,73 observados em *D. maidis*. **Segunda:** em adultos, 100, 200 e 500 ng/µL não diferem entre si e 10 e 50 não são significativos, de modo que toda a transição cabe no salto de 50 para 100 — é isso que torna o IC95% do bootstrap estreito por construção da grade. **Terceira:** a reversão em dose alta é real mas restrita às ninfas, o que a torna dependente de estágio.

Há ainda um achado que o registro de 11/09 não continha e que importa para o elo knockdown → efeito: com 48 h de acesso não houve mortalidade em nenhuma concentração, enquanto com dez dias de ingestão contínua houve mortalidade significativa a 200 e 500 ng/µL, mas não a 100. O mesmo nível de knockdown produz ou não produz fenótipo conforme a duração da exposição — o que entra no registro como restrição sobre g, em M2-21.

### 5.5 Demais hemípteros

*P. stali* fornece três doses orais (100, 1000 e 5000 ng/µL) com resposta de ≈ 50% apenas na maior. Esse contraste com *D. citri*, que satura a partir de 100 ng/µL, é o argumento mais direto de que EC50 não se transfere entre espécies dentro da ordem: a faixa efetiva varia por ordens de grandeza. Não verifiquei o texto completo desta fonte nesta etapa; o registro vem do relatório de 11/09.

### 5.6 Estado do Banco de Evidências v2

O Banco permanece como input, não como fonte primária definitiva. O estado registrado continua sendo o fator limitante: usar\_em\_modelo = sim em zero linhas, e apenas 2 dos 72 pares parâmetro-valor com n e incerteza. Pelo Guia v2, nenhum parâmetro do M2 está habilitado para entrar em modelo quantitativo — o que é coerente com o inventário da seção 4, onde nenhum item sai de AUSENTE nesta etapa.

## 6. Busca dirigida: resultado por lacuna

As lacunas são as da seção 13 do relatório de 11/09, convertidas em perguntas fechadas com critério objetivo de encerramento. A busca foi restrita a elas — não houve reabertura de revisão ampla sobre RNAi.

| Lacuna | Pergunta e critério de sucesso | Status | O que a busca retornou | Próxima ação |
| --- | --- | --- | --- | --- |
| EC50 oral em *D. maidis* | Existe ensaio oral na espécie com ≥ 3 concentrações e medida de transcrito em cada uma? Sucesso = ≥ 3 pares (dose, KD) na mesma rota, gene e tempo | **Aberta** | Nenhum. Confirmado que as duas fontes orais da espécie são de genes, estágios e tecidos diferentes e não compõem curva. Nenhum estudo novo localizado desde 11/09 | Encerrar a busca bibliográfica por este item. É lacuna de delineamento |
| Emax oral | Qual o maior knockdown oral documentado em *D. maidis*, e qual o platô em hemípteros? Sucesso = valores com tecido e tempo definidos | **Fechada parcialmente, com correção** | Piso na espécie-alvo: 0,73. Platô em *D. citri* verificado no texto completo: 0,12–0,34 (ninfas) e 0,18–0,39 (adultos), não 0,3–0,5 | Corrigir a faixa no banco. Reclassificar o prior: evidência de platô baixo, não teto para a espécie-alvo |
| Coeficiente de Hill n | Há estimativa publicada de inclinação de curva dose-resposta de RNAi em hemípteros? Sucesso = n ajustado com IC | **Aberta** | Nenhuma. Confirmado que mesmo na curva de 5 doses de *D. citri* a transição cabe num único salto (50 → 100), o que impede estimar n ali também | Manter n = 1 fixo (G7). Não transferir n de contexto farmacológico |
| Comprimento do dsRNA | Qual o tamanho do construto por fonte? Sucesso = bp registrado por observação | **Fechada parcialmente** | BicC 372 pb (já registrado); *D. citri* confirmado em 147, 153 e 194 pb por gene — o relatório registrava a faixa agregada 147–194. V-ATPase B/D em *D. maidis*: não localizado no pré-print | Desagregar os bp por gene no dataset. Buscar o tamanho dos construtos de V-ATPase |
| β\_KD→ovos | Existe conjunto com knockdown e oviposição medidos no mesmo experimento? Sucesso = pares (KD, ovos/fêmea) por réplica | **Aberta** | Nenhum. No estudo de 2022 os experimentos de expressão foram independentes dos de oviposição. Em *D. citri* encontrei evidência adicional de que a relação depende também da duração da exposição, não só do KD | Pedido ao Wet Lab deve exigir pareamento na mesma coorte **e** duração de exposição fixa |
| Réplica e dispersão | Quais os SE/IC e o n por tratamento? Sucesso = valores numéricos ou n explícito por grupo | **Aberta** | *D. citri*: n = 3 pools de 5, com 3 técnicas — registrado. *D. maidis* BicC: 3 réplicas biológicas, dispersão só em figura, e o n de fêmeas por tratamento não aparece no pré-print | Digitalizar as figuras. O n de fêmeas exige a versão publicada (paga) |
| Duração e recuperação | Por quanto tempo o silenciamento persiste após o fim da exposição? Sucesso = ≥ 3 tempos cobrindo além de 7 dias | **Aberta** | Nenhuma leitura além de 7 dias em *D. maidis*. A latência de 2 a 4 dias em V-ATPase é o único dado temporal adicional | Lacuna de delineamento, compartilhada com o M3 |
| Magnitude de α\_cof | Qual o ganho de knockdown sob co-feeding com anti-dsRNase-2? Sucesso = par de valores com dispersão | **Aberta por restrição de acesso** | Artigo de 2023 atrás de paywall; o registro no CONICET não disponibilizou PDF na consulta | Pertence a M1/M3. Pedir ao responsável pelo M3, que já trabalhou com o suplementar do artigo |
| Exposição interna | Há quantificação de dsRNA íntegro por inseto ou tecido após alimentação? Sucesso = massa ou concentração interna com tempo | **Aberta** | Nenhuma. Coincide com a lacuna C0\_eff do M1 | Não duplicar. Acompanhar a resolução no M1 |

### Leitura transversal

O resultado mais útil da busca não foi preencher lacuna, e sim **corrigir a base**: duas das nove lacunas fecharam parcialmente, e as duas fecharam *para menos* — o platô externo é mais baixo do que o anotado, e o comprimento do dsRNA precisava ser desagregado por gene. Nenhuma lacuna de forma de curva foi fechada.

Isso confirma a tipologia que já estava implícita no relatório de 11/09. Das nove lacunas, **quatro são de delineamento** (EC50, n, β\_KD→ovos, duração) e nenhuma busca bibliográfica as resolve, porque o experimento necessário não existe; **duas são de acesso** (dispersão e n amostral em figura ou atrás de paywall; magnitude de α\_cof); **uma é de interface** e pertence ao M1; e **duas fecharam parcialmente** por verificação de fonte. Insistir em busca bibliográfica para o primeiro grupo seria busca aberta sem critério de encerramento — exatamente o que o plano semanal pede para evitar.

## 7. Hipóteses e decisões

### 7.1 Hipóteses aceitas: status após a verificação

| ID | Hipótese | Status |
| --- | --- | --- |
| G1 | Endpoint do eixo KD é 1 − E\_rel, com conversões explícitas | Mantida |
| G2 | Eixo D é concentração na dieta (ng/µL), rota oral apenas | Mantida. A exposição interna entra no registro como parâmetro ausente de interface, não como substituição do eixo agora |
| G3 | Rotas diferentes não entram no mesmo eixo D | Mantida e estendida: registros sem dose absoluta (planta transgênica em *N. lugens*) também ficam fora |
| G4 | Comparar apenas doses medidas no mesmo tempo; dia 7 para BicC | Mantida e reforçada pela latência de 2 a 4 dias em V-ATPase |
| G5 | Hill é ponto de partida; sua adequação é testável | Mantida, agora com evidência numérica de violação em ninfas |
| G6 | Emax oral em Hemiptera é baixo | **Corrigida.** A faixa é 0,12–0,39, não 0,3–0,5. E reclassificada: não é teto para *D. maidis*, cujo valor oral observado (0,73) já a excede |
| G7 | Sem pontos na transição, fixar n = 1 | Mantida e reforçada: nem a curva de 5 doses de *D. citri* identifica n |
| G8 | Réplicas biológicas e técnicas separadas; pool conta como 1 | Mantida e aplicada também a *D. citri* (pool de 5 insetos, 3 réplicas técnicas) |
| G9 | Outras espécies servem como prior fraco, nunca como valor calibrado | Mantida e reforçada: *P. stali* responde só a 5000 ng/µL e *D. citri* satura a partir de 100 — a faixa efetiva varia por ordens de grandeza dentro da ordem |

### 7.2 Premissas rejeitadas: status

| ID | Premissa rejeitada | Status |
| --- | --- | --- |
| R1 | Ajustar EC50, Emax e n juntos com os dados atuais | Rejeição mantida |
| R2 | Fixar Emax ≈ 1,0 por padrão | Rejeição mantida, agora com piso explícito: Emax ≥ 0,73 na espécie-alvo |
| R3 | Combinar oral e injeção no mesmo eixo D | Rejeição mantida |
| R4 | Tratar 100 e 200 ng/µL como dois níveis informativos | **Rejeição mantida, base corrigida.** Não é que produzam o mesmo KD: a 100 ng/µL não houve medida molecular |
| R5 | Ler bom ajuste ou baixo AIC como parâmetros bem estimados | Rejeição mantida |
| R6 | Extrapolar fora do intervalo de doses observado | Rejeição mantida |

### 7.3 Decisões novas desta etapa

**D1 — O registro da seção 4 passa a ser a fonte única dos símbolos do M2.** *Base:* o entregável da semana é um inventário auditável, e símbolos dispersos entre código, dataset e relatório produzem divergência silenciosa. *Impacto:* parameters\_hill.yaml espelha as classes e os campos de uso permitido deste registro; qualquer símbolo novo entra aqui antes de entrar no código.

**D2 — Reclassificar o prior de** ***D. citri*****.** *Base:* a faixa estava superestimada e estava sendo usada com função de teto. *Impacto:* passa a constar como 0,12–0,39, com transferibilidade indireta e uso restrito a duas coisas: sustentar que o platô oral pode ser muito inferior a 1, e desenhar a grade de doses do Wet Lab.

**D3 — Registrar Emax com piso e sem teto.** *Base:* 0,73 é observação direta na espécie, na rota e no endpoint de interesse; nenhum dado estabelece o teto. *Impacto:* os cenários de Emax partem de 0,73 e não são limitados por valores de outra espécie. A diferença de tecido — ovário dissecado contra corpo inteiro — fica anotada como explicação possível e não testada.

**D4 — Incorporar a duração da exposição como condicionante de g.** *Base:* em *D. citri*, a mesma faixa de knockdown produziu ou não produziu mortalidade conforme a exposição fosse de 48 h ou de 10 dias contínuos. *Impacto:* g não é função só de KD. Pares (KD, efeito) vindos de protocolos de duração diferente não podem ser ajustados juntos, e o pedido ao Wet Lab precisa fixar a duração.

**D5 — Corrigir dois registros de proveniência.** *Base:* a autoria da fonte de *D. citri* está trocada (Saberi et al., não Qureshi et al.) e os comprimentos de dsRNA estavam agregados como faixa. *Impacto:* corrigir a citação no banco e no dataset, e desagregar bp por gene (147, 153 e 194). São correções pequenas, mas é por elas que a rastreabilidade se perde.

**D6 — Nenhum parâmetro muda de estado nesta etapa.** *Base:* o Guia v2 exige valor\_num, unidade, grau e verificação humana, e nenhum item do M2 reúne os quatro. *Impacto:* usar\_em\_modelo permanece nao em todas as linhas do M2. O registro fica pronto para que a mudança seja de uma célula, quando houver evidência.

## 8. Encaminhamento ao Banco de Evidências

Três tipos de submissão vão ao Banco nesta etapa: **correções** de registros existentes, **inclusões** das fontes externas que o relatório de 11/09 recomendou incorporar, e **registros novos** vindos da verificação. Todos entram sob verificação humana, no padrão vigente, e nenhum altera usar\_em\_modelo.

### 8.1 Correções de registros existentes

| Registro | O que está no banco | O que deve passar a constar |
| --- | --- | --- |
| Platô oral em Hemiptera | Emax ≈ 0,3–0,5 | 0,12–0,34 (ninfas) e 0,18–0,39 (adultos), com tecido (corpo inteiro agrupado) e tempo (5 d pós-acesso) declarados |
| Autoria da fonte de *D. citri* | Qureshi et al. (2024) | Saberi, E.; Mondal, M.; Paredes-Montero, J. R.; Nawaz, K.; Brown, J. K.; Qureshi, J. A. (2024) |
| Comprimento do dsRNA em *D. citri* | 147–194 pb, agregado | 147 pb (CHC), 153 pb (vATPase-A), 194 pb (Snf7) |
| Níveis de dose de BicC | 100 e 200 ng/µL com o mesmo KD | 100 e 200 ng/µL administrados; RT-qPCR conduzida somente em 200 — a 100 não há medida molecular |

### 8.2 Inclusões recomendadas, com transferibilidade declarada

| Registro | Contexto a registrar | Utilidade | Limite de uso |
| --- | --- | --- | --- |
| Curva oral multi-dose em *D. citri* | 5 doses (10–500 ng/µL) em sacarose 20%; 48 h de acesso; qPCR 5 d depois; 3 genes; n = 3 pools de 5 com 3 técnicas; normalizador RPL5; controle de luciferase na mesma concentração | Única curva oral multi-dose em Hemiptera. Define forma qualitativa: limiar, platô baixo, saturação | Transferibilidade indireta, apenas ordem de grandeza. Não fornece EC50 nem Emax para *D. maidis* |
| Reversão em dose alta | Ninfas: CHC perde significância a 500 ng/µL; vATPase-A cai de 30,95% para 12,08%. Adultos: sem reversão | Hipótese estrutural contra monotonicidade automática | Dependente de estágio. É hipótese a testar, não propriedade a importar |
| Dependência da duração da exposição | Mesma faixa de concentração: sem mortalidade após 48 h de acesso, com mortalidade significativa a 200 e 500 ng/µL após 10 dias contínuos | Restringe a função g: o fenótipo depende da duração, não só do KD | Endpoint de mortalidade, espécie diferente. Vale como forma, não como valor |
| Faixa efetiva em *P. stali* | 100, 1000 e 5000 ng/µL por via oral; ≈ 50% de knockdown apenas na maior | Demonstra variação de ordens de grandeza na faixa efetiva dentro de Hemiptera | Texto completo não verificado nesta etapa; marcar como pendente de conferência |

### 8.3 Registros novos da espécie-alvo

| Registro | Contexto a registrar | Utilidade | Limite de uso |
| --- | --- | --- | --- |
| Latência do silenciamento em *D. maidis* | V-ATPase B e D, oral, 500 ng/µL, ninfas de 3º ínstar, dieta D-10 renovada a cada 24 h; sem redução significativa no dia 2, significativa no dia 4 (p = 0,012 e 0,010); n = 3 pools de 3; normalizador ETF; controle GFP | Único parâmetro temporal com suporte direcional na espécie | O artigo não reporta percentual de knockdown — as razões estão só em figura. Registrar como estimável por digitalização |
| Mortalidade dos controles no mesmo ensaio | Sobrevivência em 4 dias: ≈ 52% sem dsRNA, ≈ 37% no controle GFP, ≈ 18% e ≈ 16% nos tratamentos | Alerta metodológico: o delineamento tem perda alta nos próprios controles | Limita o uso quantitativo do endpoint de mortalidade nesta fonte |
| Toxicidade do controle em dose alta | Em *D. citri*, os autores observam efeito do próprio controle de luciferase acima de 200 ng/µL | Justifica tratar o zero da escala como "presença de dsRNA inespecífico" e não como ausência de efeito | Espécie diferente; registrar como alerta de método |

**Observação de curadoria.** Os registros de protocolo de exposição oral e de efeito do co-feeding se sobrepõem ao que o M1 já encaminhou. Convém uni-los em um registro único com múltiplos usos declarados, em vez de manter duplicatas por submodelo — do contrário a mesma evidência pode ser curada com critérios diferentes em cada módulo.

## 9. Ações restantes

### 9.1 Sobre o dataset e o banco

1. Aplicar as quatro correções da seção 8.1 no dataset\_dose\_knockdown\_reconstruido e no Banco v2, incluindo a desagregação de dsRNA\_bp por gene e a correção de autoria.

2. Alterar o registro de BicC a 100 ng/µL de "mesmo KD que 200" para "dose administrada, sem medida molecular", ajustando uso\_no\_Hill e a observação.

3. Incluir as fontes de *D. citri* e *P. stali* no Banco com transferibilidade declarada, conforme a recomendação já feita em 11/09.

4. Verificar o texto completo de *P. stali*, único registro externo ainda não conferido, antes de consolidá-lo.

5. Digitalizar as figuras que retêm números: oviposição e expressão de BicC, e as razões de expressão de V-ATPase. Registrar que as médias de oviposição são preditas pelo GLMM, não brutas.

6. Recuperar da versão publicada (paga) o número de fêmeas por tratamento no estudo de 2022, hoje ausente do pré-print, e conferir se os valores do pré-print se mantiveram.

### 9.2 Sobre o código e o arquivo de parâmetros

7. Espelhar o registro da seção 4 em parameters\_hill.yaml, acrescentando os campos que hoje não estão declarados: t\_delay, t\_exposicao, dose\_tipo, dsRNA\_bp por gene, e os priors externos com faixa corrigida.

8. Implementar a restrição de D4 no protocolo de ajuste: pontos com durações de exposição diferentes não são elegíveis para o mesmo ajuste de g, e a verificação disso deve falhar explicitamente em vez de passar silenciosamente.

9. Manter o ajuste progressivo como está. Nenhuma alteração é necessária: as correções desta etapa mudam priors e metadados, não a estrutura do protocolo.

### 9.3 Requisitos ao Wet Lab

Quatro lacunas são de delineamento e nenhuma busca as resolve. O pedido precisa ser específico o bastante para ser executável:

| Requisito | Delineamento mínimo | O que destrava |
| --- | --- | --- |
| Curva dose-resposta oral com medida molecular | 5 a 6 concentrações em escala logarítmica, concentradas **abaixo** de 200 ng/µL — a 200 o KD já é 0,73, e em *D. citri* a transição ficou abaixo de 100. Sugestão de grade: 1, 5, 20, 50, 100, 200 ng/µL. Mesmo gene, tecido, tempo de leitura e normalizador em todos os níveis | EC50 e, com níveis suficientes dentro da transição, n |
| Medida molecular no nível já administrado | Repetir a RT-qPCR a 100 ng/µL, dose que já foi usada no ensaio de 2022 sem leitura de transcrito | Transforma um nível efetivo em dois, pelo menor custo experimental de toda a lista |
| Pareamento knockdown-efeito | Transcrito e oviposição na mesma coorte e na mesma dose, com **duração de exposição fixa** entre tratamentos | KD50 e m da função g, hoje inteiramente ausentes |
| Cinética estendida | Leituras em 0, 1, 3, 7, 10 e 14 dias após o fim da exposição | t\_delay, duração e recuperação; compartilhado com o M3 |

O segundo item merece destaque por ser desproporcionalmente barato: não exige novo tratamento, apenas quantificar uma condição que já faz parte do protocolo estabelecido. Os dois últimos valem coordenar com o responsável pelo M3 antes de encaminhar, para não duplicar delineamento.

### 9.4 O que continua vedado

10. Não ajustar a Hill completa aos dados atuais de *D. maidis*. O ajuste converge e produz números sem conteúdo informativo — demonstrado para *D. citri*, que tem cinco doses.

11. Não construir o módulo Monte Carlo. Sem dispersão numérica para nenhum parâmetro, a banda refletiria a distribuição escolhida.

12. Não extrapolar fora do intervalo observado, nem importar EC50 ou n de outra espécie ou de contexto farmacológico geral.

## 10. Conclusão

O diagnóstico do M2 não mudou: EC50, Emax e n continuam não identificáveis para *D. maidis* por via oral, e o entregável defensável continua sendo estrutura parametrizável mais protocolo de ajuste, não uma curva. O que esta etapa acrescenta é o registro mestre que torna isso auditável — e três correções na base de evidências que o sustentava.

Dos 29 parâmetros inventariados: treze estão medidos, quatro são transferidos com transferibilidade indireta declarada, dois são derivados por transformação explícita, dois são recuperáveis por digitalização ou ajuste condicionado, um tem dispersão insuficiente, e sete permanecem ausentes — entre eles EC50, Emax, n e os dois parâmetros da função que liga knockdown a efeito. Nenhum muda de estado nesta etapa, e usar\_em\_modelo segue nao em todas as linhas do módulo.

As correções importam mais do que seu tamanho sugere. O platô de *D. citri* estava registrado como 0,3–0,5 quando a fonte reporta 0,12–0,39, e estava sendo usado como teto de Emax quando o próprio valor oral de *D. maidis* (0,73) o excede — isto é, um prior externo estava operando como restrição sobre a espécie-alvo em direção oposta à evidência local. A segunda correção é de justificativa: o único nível efetivo de dose não decorre de 100 e 200 ng/µL produzirem o mesmo knockdown, mas de a RT-qPCR ter sido feita apenas em 200. A diferença muda o pedido ao laboratório, e para melhor: medir o transcrito a 100 ng/µL reaproveita um protocolo já estabelecido e converte um nível efetivo em dois pelo menor custo experimental da lista.

A verificação também acrescentou uma restrição estrutural sobre o elo knockdown → efeito. Em *D. citri*, a mesma faixa de knockdown produziu ou não produziu mortalidade conforme a exposição durasse 48 h ou dez dias. A função g, portanto, não é função apenas da magnitude do silenciamento, e qualquer tentativa futura de ajustá-la precisa manter a duração fixa entre tratamentos — sob pena de atribuir à intensidade do knockdown o que é efeito de exposição acumulada.

O resultado prático é uma separação limpa do caminho adiante. Quatro lacunas são de delineamento e estão encerradas para busca bibliográfica; duas são de acesso; uma pertence ao M1; duas fecharam parcialmente por conferência de fonte. Isso permite dar a busca por encerrada com critério, em vez de mantê-la aberta sobre um tema onde não há mais o que encontrar.

## 11. Referências e rastreabilidade

Marcação de acesso, no padrão do relatório de 11/09: **\[aberto\]** = texto completo conferido; **\[paywall\]** = apenas resumo ou registro; **\[não conferido\]** = usado a partir do registro interno, sem verificação nesta etapa.

### Espécie-alvo

DALAISÓN-FUENTES, L. I.; PASCUAL, A.; GAZZA, E.; WELCHEN, E.; RIVERA-POMAR, R.; CATALANO, M. I. Development of efficient RNAi methods in the corn leafhopper *Dalbulus maidis*, a promising application for pest control. *Pest Management Science*, v. 78, n. 7, p. 3108–3116, 2022. DOI: [10.1002/ps.6937](<https://doi.org/10.1002/ps.6937>) **\[paywall\]**; pré-print: [bioRxiv 2022.01.17.476645](<https://www.biorxiv.org/content/10.1101/2022.01.17.476645v1.full>) **\[aberto\]** — BicC, oral e injeção, 100 e 200 ng/µL, 372 pb, n = 3 biológicas.

JONES-BERNAL et al. Assessing the functionality of RNA interference (RNAi) in the phloem-feeding maize pest *Dalbulus maidis*. *bioRxiv*, 2021. DOI: [10.1101/2021.09.29.462424](<https://doi.org/10.1101/2021.09.29.462424>) **\[aberto\]** — V-ATPase B e D, dieta, 500 ng/µL, dose única; n = 3 pools de 3 insetos; leituras nos dias 2 e 4.

DALAISÓN-FUENTES, L. I.; PASCUAL, A.; CRESPO, M.; ANDRADA, N. L.; WELCHEN, E.; CATALANO, M. I. Knockdown of double-stranded RNases (dsRNases) enhances oral RNA interference (RNAi) in the corn leafhopper, *Dalbulus maidis*. *Pesticide Biochemistry and Physiology*, v. 196, 105618, 2023. DOI: [10.1016/j.pestbp.2023.105618](<https://doi.org/10.1016/j.pestbp.2023.105618>) **\[paywall — só resumo\]**; registro: [CONICET Digital 11336/221063](<https://ri.conicet.gov.ar/handle/11336/221063>) — pré-tratamento com anti-dsRNase-2; pertence a M1/M3, não à curva de Hill.

ANDRADA, N. L.; CRESPO, M.; BARICALLA, A. A.; DALAISÓN-FUENTES, L. I.; STERKEL, M.; CATALANO, M. I. ETH and Burs-α are necessary for the normal molting in *Dalbulus maidis* and *Delphacodes kuscheli*. *Frontiers in Insect Science*, v. 6, 1811933, 2026. DOI: [10.3389/finsc.2026.1811933](<https://doi.org/10.3389/finsc.2026.1811933>) **\[aberto\]** — injeção, dose única de 500 ng/µL; knockdown de 90–95%; leitura no dia 4. Fora do eixo D; registrado como evidência de que silenciamento profundo é alcançável na espécie.

### Evidência transferida (Hemiptera)

SABERI, E.; MONDAL, M.; PAREDES-MONTERO, J. R.; NAWAZ, K.; BROWN, J. K.; QURESHI, J. A. Optimal dsRNA concentration for RNA interference in Asian citrus psyllid. *Insects*, v. 15, n. 1, 58, 2024. DOI: [10.3390/insects15010058](<https://doi.org/10.3390/insects15010058>) **\[aberto; externo ao banco\]** — 5 doses orais (10–500 ng/µL), 3 genes, adultos e ninfas, n = 3. Única curva oral multi-dose em Hemiptera. *A citação anterior como "Qureshi et al." precisa ser corrigida: Qureshi é o último autor.*

Effectiveness of orally-delivered dsRNA on gene silencing in the stinkbug *Plautia stali*. *PLoS ONE*, 2021. DOI: [10.1371/journal.pone.0245081](<https://doi.org/10.1371/journal.pone.0245081>) **\[não conferido nesta etapa\]** — oral a 100, 1000 e 5000 ng/µL; ≈ 50% de knockdown só na maior.

*Nilaparvata lugens*. *PLoS ONE*, 2011. DOI: [10.1371/journal.pone.0020504](<https://doi.org/10.1371/journal.pone.0020504>) **\[não conferido nesta etapa\]** — planta transgênica, knockdown de 42–73% sem dose absoluta; não posicionável no eixo D.

### Material interno e metodológico

BIOGUARD. *Módulo M2 — Relação dose → knockdown (curva de Hill): reconstrução do dataset, padronização, análise de identificabilidade e plano de calibração.* Gabriel, 11 set. 2026. **Referência técnica deste registro.** Entregáveis associados: dataset\_dose\_knockdown\_reconstruido.csv/.xlsx, parameters\_hill.yaml, 01\_reconstruir\_dataset.py, 02\_analise\_figuras.py, 03\_saidas.py.

BIOGUARD. *Banco de Evidências v2* (BioGuard Banco de Evidencias v2.xlsx). Abas Banco v2, Parametros (long), Lacunas, Resumo da triagem, Listas, Guia v2.

SHIFLET, A. B.; SHIFLET, G. W. *Introduction to Computational Science: Modeling and Simulation for the Sciences*. Princeton: Princeton University Press, 2006. — base metodológica: modelos empíricos, simplificações, verificação × validação.

### Ressalva de acesso

- **Artigo de 2022.** Lido no pré-print aberto; a versão publicada é paga e não foi verificada. Todos os valores de BicC citados aqui vêm do pré-print e carecem de conferência contra a versão final, que também contém o n de fêmeas por tratamento, ausente no pré-print.

- **Artigo de 2023.** Integralmente atrás de paywall; o registro do CONICET não disponibilizou PDF na consulta. Nenhum valor numérico dele aparece neste documento.

- **Fontes não conferidas.** *P. stali* e *N. lugens* entram a partir do registro interno de 11/09, sem verificação de texto completo nesta etapa. Marcadas como pendentes antes de consolidação no Banco.

- **Valores em figura.** Oviposição, dispersão do knockdown de BicC e as razões de expressão de V-ATPase existem apenas graficamente. Classificados como estimáveis por digitalização, não como medidos.

As conversões de fold-change para knockdown fracionário e a leitura de identificabilidade da seção 2.5 são raciocínio aplicado aos dados publicados, não resultados extraídos das fontes citadas. As três correções da seção 1 vêm de conferência direta do texto completo das fontes de acesso aberto.
