# RELATORIO TECNICO Modelagem de degradacao de dsRNA e exposicao acumulada (AUC)

BioGuard - triagem de evidencias, hipoteses aceitas e plano de parametrizacao

**Escopo: perda de dsRNA intacto -> k_deg -> meia-vida -> AUC -> incerteza/Monte Carlo**

Versao de trabalho baseada exclusivamente nos materiais e bancos de evidencias fornecidos.

11 de setembro de 2026

## Resumo executivo

Conclusao principal. Os tres bancos de evidencias sustentam de forma razoavel a estrutura biologica do modulo de degradacao, mas ainda nao fornecem um valor numerico defensavel de k_deg para Dalbulus maidis. A versao v2 explicita essa lacuna: nao ha k em unidade de tempo^-1; ha apenas medidas de degradacao em tempos pontuais, Vmax/Km de outras especies e limites qualitativos. Portanto, o modelo deve ser construido agora como uma estrutura parametrizavel, sem inventar precisao numerica.

**Decisao metodologica central**

Adotar decaimento de primeira ordem como modelo inicial por condicao, separar pelo menos os cenarios saliva/glândula salivar e intestino medio, usar dados interespecificos apenas para sensibilidade e deixar k_deg como parametro a ser estimado a partir de uma curva temporal C(t) de D. maidis.

O produto desta etapa nao e um numero isolado de k_deg. E um conjunto defensavel de hipoteses, restricoes, equacoes, criterios de inclusao de evidencia e um procedimento claro para estimar k_deg, t_1/2 e AUC quando a curva temporal estiver disponivel.

## 1. Materiais analisados

- Banco de evidencias.xlsx: banco-base com 42 registros experimentais e campos de transferibilidade, limitacao e decisao afetada.
- BioGuard Banco de Evidencias v2.xlsx: versao com triagem, tabela longa de parametros, lacunas e correcoes de consistencia.
- Banco_de_evidencias_Revisado.xlsx: inclui uma aba de revisao cientifica e um resumo de verificacao das fontes.
- Divisao_Modelagem_BioGuard.pdf: define o modulo M1 como degradacao do dsRNA e AUC, com k_deg, t_1/2, AUC e propagacao de incerteza via Monte Carlo.
- Material de apoio - Nivelamento de Calculo aplicado ao Bioguard.pdf e slides: define as equacoes operacionais de degradacao, meia-vida e AUC.
- Shiflet & Shiflet, Introduction to Computational Science: base metodologica para formulacao de modelos, hipoteses simplificadoras, verificacao e simulacao Monte Carlo.

**Regra de leitura dos bancos**

As planilhas foram tratadas como bancos de evidencia e nao como fonte primaria definitiva. Quando a revisao interna marcou uma linha como "pendente de verificacao primaria", o dado foi usado apenas para sustentar estrutura ou direcao biologica, nao para fixar um valor numerico final.

## 2. Como a triagem foi realizada

A analise foi feita em seis passos, para separar evidencias que ajudam a construir a arquitetura do modelo daquelas que podem realmente parametriza-lo:

1. Localizacao dos registros relacionados a degradacao de dsRNA, dsRNase-2, estabilidade, Vmax/Km, tempo de degradacao, BicC e carreadores.
2. Comparacao do mesmo registro entre o banco-base, a versao v2 e a revisao cientifica.
3. Priorizacao por proximidade biologica: D. maidis > outros hemipteros > outros insetos; ensaio intestinal/salivar > estabilidade ambiental; dado quantitativo verificado > descricao qualitativa.
4. Checagem da compatibilidade matematica do dado com o parametro desejado. Vmax/Km, por exemplo, nao tem o mesmo significado nem as mesmas unidades de k_deg.
5. Identificacao de inconsistencias ou conflacoes de tempo, dose, DOI e endpoint.

6. Conversao das evidencias validas em hipoteses de modelagem explicitamente classificadas como aceitas, provisoriamente aceitas ou rejeitadas para uso quantitativo.

## 3. Evidencias uteis para o modulo de degradacao

| Evidencia | Dado principal | Utilidade | Decisao para M1 |
| --- | --- | --- | --- |
| D. maidis - dsRNase-2, ensaio ex vivo | Degradacao descrita como total (~100%) em ate 12 h na linha salivar. | Muito alta para estrutura | Central para afirmar degradacao forte e necessidade de k especifico. Nao fornece k sozinho. |
| D. maidis - silenciamento de dsRNase-2 | Reducao registrada de 23,6x e melhora do RNAi oral apos pretratamento + dieta. | Alta, direcional | Sustenta que menor atividade/expressao de dsRNase-2 deve reduzir a degradacao efetiva. Nao autoriza dividir k por 23,6. |
| Nylanderia fulva | Apenas 23% do dsRNA permaneceu apos 2 h (~77% degradado). Fonte marcada como confirmada na revisao. | Comparativa | Pode testar se o modelo reproduz cenarios externos agressivos. Nao e parametro de D. maidis. |
| Quatro insetos - Vmax/Km | Vmax/Km confirmados; revisao corrige substrato de 500 µM para 0,5 µM. | Comparativa de mecanismo | Demonstra variacao interespecifica e cinetica enzimática. Nao converter Vmax/Km diretamente em k_deg. |
| Aedes aegypti | Linha registrava "4 min", mas a revisao aponta DOI incompatível e a v2 manda nao usar/corrigir. | Excluida quantitativamente | O valor de 4 min fica fora do modelo ate a referencia correta ser localizada e conferida. |
| Psylliodes chrysocephala -carreadores | Protecao termica/UV e liberacao por nanoparticulas. | Qualitativa | Mostra que formulacao altera estabilidade, mas mede estresse ambiental/foliar, nao degradacao intestinal em D. maidis. |
| D. maidis - BicC por dieta | Exposicao oral por 3 dias em 100-200 ng/µL. | Indireta para M1 | Importante para lembrar que o ensaio real tem entrada repetida; nao deve ser tratado como um unico bolus sem reposicao. |

## 4. O que foi aceito, corrigido ou excluido - e por que

### 4.1 Evidencia direta em D. maidis

O registro mais importante e o estudo de 2023 sobre dsRNase-2 (DOI 10.1016/j.pestbp.2023.105618). No banco-base e na v2, ele aparece em duas formas complementares: uma linha ex vivo com degradacao salivar total em ate 12 h e uma linha de intervencao, com silenciamento de dsRNase-2 seguido de dieta oral. A revisao cientifica considera o artigo altamente relevante, mas mantem os numeros de 12 h, 12-24 h e 23,6x como pendentes de conferencia no texto primario.

Isso permite aceitar duas conclusoes estruturais: (i) a degradacao e um gargalo biologicamente real em D. maidis; e (ii) dsRNase-2 e um mecanismo plausivel e experimentalmente relevante desse gargalo. O que ainda nao e permitido e atribuir uma taxa numerica final de degradacao sem extrair uma curva C(t).

**Por que "degradacao total em 12 h" nao e k_deg**

Em um modelo exponencial C(t)=C0 exp(-k_deg t), C(t) se aproxima de zero, mas nao chega matematicamente a zero. A expressao "degradacao total" em gel normalmente significa "abaixo do limite de deteccao". Sem saber esse limite, 12 h define apenas uma restricao sobre k_deg, nao um valor unico.

### 4.2 Vmax/Km de outras especies

O artigo de 2018 compara nucleases degradadoras de dsRNA em quatro insetos. A revisao cientifica confirma os pares Vmax/Km e corrige um erro importante de unidade/concentracao: o substrato final reportado pela fonte e 0,5 µM, enquanto o banco-base registrava 500 µM. Esses dados sao biologicamente uteis, mas matematicamente pertencem a um modelo de Michaelis-Menten. Portanto, nao podem ser usados como se fossem k_deg de primeira ordem.

| Especie | Vmax | Km | Uso permitido |
| --- | --- | --- | --- |
| Spodoptera litura | 13,40 µM.s^-1 | 2,28 µM | Cenario comparativo |
| Locusta migratoria | 9,46 µM.s^-1 | 3,06 µM | Cenario comparativo |
| Periplaneta americana | 3,58 µM.s^-1 | 0,27 µM | Cenario comparativo |
| Zophobas atratus | 38,87 µM.s^-1 | 17,59 µM | Cenario comparativo |

### 4.3 Nylanderia fulva: exemplo de transformacao matematica, nao de transferencia

A revisao confirma que, em um ensaio in vitro de fluido de intestino medio, 23% do dsRNA permaneceu apos 2 h. Se - apenas como exercicio matematico - se impuser cinetica de primeira ordem, uma taxa aparente pode ser calculada por:

$$
k_{\mathrm{aparente}}=-\frac{\ln(C/C_0)}{t}=-\frac{\ln(0{,}23)}{2\,\mathrm{h}}=0.735\,\mathrm{h}^{-1}
$$

$$
t_{1/2}=\frac{\ln 2}{k_{\mathrm{aparente}}}=0.94\,\mathrm{h}=56.6\,\mathrm{min}
$$

Esse calculo mostra como um ponto residual pode ser traduzido em taxa sob uma hipotese matematica especifica. Ele NAO cria um valor transferivel para D. maidis: a especie, a fisiologia digestiva, a matriz e o desenho experimental sao diferentes. Por isso, o resultado serve apenas como teste de sanidade/sensibilidade do codigo.

### 4.4 Registros que nao entram na parametrizacao

- Aedes aegypti: o banco revisado identifica incompatibilidade entre o titulo e o DOI registrado. O valor "4 min" nao deve ser usado enquanto a referencia correta nao for recuperada e verificada.
- Psylliodes chrysocephala: a v2 mostra que o campo "15 dias" pertence ao bioensaio de sobrevivencia, nao aos ensaios de estabilidade termica/UV. Os tempos especificos de 12-16 h (calor) e ~6 h (inicio de degradacao UV) sao contextuais e ambientais; nao estimam k intestinal de D. maidis.
- Plautia stali: registro incompleto, com DOI de dataset e sem dose/tempo/endpoint suficientes; fica fora da parametrizacao.

## 5. Hipoteses aceitas para a primeira versao do modelo

| ID | Hipotese | Status | Justificativa |
| --- | --- | --- | --- |
| H1 | A degradacao pode ser inicialmente aproximada por cinetica de primeira ordem em cada condicao: dC/dt = -k_deg*C. | Aceita como simplificacao inicial | O material BioGuard ja adota essa forma; e simples, identificavel e testavel quando houver C(t). |
| H2 | k_deg e positivo e aproximadamente constante dentro de uma janela curta e condicao fixa. | Aceita provisoriamente | Permite uma primeira parametrizacao. Deve ser revista se a curva mostrar fases distintas ou saturacao. |
| H3 | k_deg nao e universal; varia com especie, tecido/matriz, formulacao e condicao. | Aceita | Os bancos mostram forte variacao interespecifica e diferencas entre ensaios. |
| H4 | Saliva/glândula salivar e intestino medio devem ser tratados com parametros distintos. | Aceita estruturalmente | Os registros de D. maidis distinguem compartimentos e tempos de degradacao. |
| H5 | A degradacao salivar parece mais rapida que a do intestino medio. | Provisoria | Baseada nos registros de 12 h versus 12-24 h; precisa ser confirmada no artigo primario. |
| H6 | dsRNase-2 contribui de forma relevante para a perda de dsRNA em D. maidis. | Aceita | Estudo diretamente direcionado ao mecanismo e melhora de RNAi oral apos silenciamento. |
| H7 | Silenciar dsRNase-2 reduz k_deg efetivo e aumenta t_1/2/AUC, mantidas as demais condicoes. | Aceita apenas direcionalmente | A direcao e sustentada; a magnitude nao pode ser inferida do fold-change de expressao. |
| H8 | Somente dsRNA intacto/funcional entra em C(t) e na AUC da versao inicial. | Aceita como definicao operacional | Evita contar fragmentos como exposicao util. |
| H9 | No ensaio ex vivo de degradacao, apos t=0 nao ha nova entrada de dsRNA. | Aceita para estimar k_deg | E a condicao que permite isolar o desaparecimento. Nao vale para alimentacao continua. |
| H10 | Observacoes "sem banda"/"degradacao total" sao censuradas pelo limite de deteccao. | Aceita | Evita substituir uma observacao instrumental por C=0 matematico. |
| H11 | Dados de outras especies servem apenas para cenarios, sensibilidade ou verificacao de ordem de grandeza. | Aceita | A transferibilidade foi classificada como indireta/especulativa nos bancos. |
| H12 | A incerteza de k deve vir do ajuste/replicatas/intervalos ou de cenarios explicitamente rotulados, e nao de um numero arbitrario. | Aceita | Necessario para que bandas e Monte Carlo tenham interpretacao estatistica defensavel. |

## 6. Hipoteses que NAO devem ser adotadas

| Premissa rejeitada | Motivo |
| --- | --- |
| "12 h" = meia-vida | Incorreto. O tempo para ficar indetectavel nao e o tempo para cair a 50%. |
| "degradacao total" = C(t)=0 | Incorreto em modelo exponencial e incompatível com o conceito de limite de deteccao. |
| k_deg = Vmax ou Vmax/Km | Incorreto: unidades, mecanismo e forma funcional sao diferentes. |
| k_tratado = k_basal / 23,6 | Nao sustentado. Fold-change de transcrito nao e proporcional, por definicao, a atividade enzimatica nem a taxa macroscópica. |
| Um unico k para todo o inseto | Excessivamente simplificador diante das diferencas entre compartimentos. |
| Usar o valor de Aedes de 4 min | Registro bibliograficamente inconsistente; deve ser excluido ate correcao. |
| Usar estabilidade termica/UV de carreador como k intestinal | Os fenomenos e matrizes nao sao equivalentes. |
| Tratar 100-200 ng/µL oferecidos na dieta como C0 interno | Dose ofertada nao e concentracao intacta interna. Entrega/ingestao e degradacao interpoem-se entre as duas grandezas. |
| Chamar qualquer faixa de Monte Carlo de "banda de credibilidade" | Credibilidade tem interpretacao bayesiana. Se a distribuicao vier de bootstrap ou cenarios, usar "banda de incerteza"/percentis. |

## 7. Modelo matematico inicial e como cada grandeza e obtida

### 7.1 Equacao de degradacao

Parte-se da hipotese de que a velocidade instantanea de perda do dsRNA intacto e proporcional a quantidade ainda existente. O sinal negativo representa perda:

$$
\frac{dC}{dt}=-k_{\deg}C
$$

Separando variaveis e integrando: dC/C = -k_deg dt. Assim, ln(C) = -k_deg*t + constante. Aplicando C(0)=C0, obtem-se:

$$
C(t)=C_0\exp(-k_{\deg}t)
$$

Aqui, C(t) e a concentracao (ou quantidade normalizada) de dsRNA intacto, C0 e o valor inicial, t e o tempo e k_deg tem unidade de tempo^-1. As unidades de t e k precisam ser coerentes.

![Figura 1 — Tales](graficos/tales/figura_01_decaimento_primeira_ordem.png)

Figura 1. Curvas ilustrativas de primeira ordem. Valores de k sao didaticos e nao representam calibracao de D. maidis.

### 7.2 Meia-vida

Por definicao, na meia-vida resta metade de C0. Substitui-se C(t_1/2)=C0/2 na solucao exponencial:

$$
t_{1/2}=\frac{\ln 2}{k_{\deg}}
$$

Portanto, k alto implica meia-vida curta; k baixo implica maior persistencia.

### 7.3 AUC

AUC resume a exposicao acumulada ao dsRNA intacto durante a janela de interesse:

$$
\mathrm{AUC}(T)=\int_0^T C(t)\,dt
$$

Substituindo a solucao exponencial e integrando:

$$
\mathrm{AUC}(T)=\frac{C_0}{k_{\deg}}\left[1-\exp(-k_{\deg}T)\right]
$$

Com C0 e T fixos, aumentar k_deg reduz a AUC. Esse e o elo matematico que transforma estabilidade em exposicao acumulada.

### 7.4 Como tratar um ponto "abaixo da deteccao"

Se em T horas o gel nao detecta mais dsRNA e o limite de deteccao corresponde a uma fracao f_LOD de C0, entao o dado deve ser escrito como C(T)/C0 < f_LOD. Da equacao exponencial:

$$
k_{\deg}>-\frac{\ln(f_{\mathrm{LOD}})}{T}
$$

| LOD hipotetico em 12 h | Limite inferior de k | Interpretacao |
| --- | --- | --- |
| 10% de C0 | 0.192 h^-1 | Exemplo hipotetico; depende do LOD real |
| 5% de C0 | 0.250 h^-1 | Exemplo hipotetico; depende do LOD real |
| 1% de C0 | 0.384 h^-1 | Exemplo hipotetico; depende do LOD real |

A tabela acima NAO e parametrizacao do BioGuard. Ela demonstra por que o limite de deteccao precisa ser conhecido: diferentes LODs produzem diferentes limites para k.

## 8. Estrutura recomendada: cenarios separados antes de um modelo acoplado

A primeira implementacao deve evitar um modelo multicompartmental grande. E preferivel estimar e comparar dois cenarios independentes, desde que os dados primarios permitam:

**Saliva/glândula salivar:**

$$
\frac{dC_s}{dt}=-k_sC_s
$$

**Intestino medio:**

$$
\frac{dC_m}{dt}=-k_mC_m
$$

Depois de estimar k_s e k_m, com suas incertezas, pode-se avaliar se a ordem k_s > k_m e realmente sustentada. Somente entao vale integrar os compartimentos ou acoplar o efeito do silenciamento de dsRNase-2.

**Vantagem desta estrategia**

Ela preserva a diferenca biologica entre compartimentos sem exigir parametros adicionais que ainda nao existem. Isso reduz a chance de um modelo sofisticado ser numericamente elegante, mas biologicamente nao identificavel.

## 9. Limite do modelo de bolus e extensao para alimentacao continua

O modelo C(t)=C0 exp(-k t) e adequado para um ensaio de degradacao no qual, apos t=0, nao entra novo dsRNA. Entretanto, os registros de BicC em D. maidis usam dieta artificial por 3 dias. Nesse contexto ha entrada repetida, e a equacao de desaparecimento puro deixa de representar o experimento completo.

Uma extensao minima e:

$$
\frac{dC}{dt}=I(t)-k_{\deg}C
$$

Em uma versao intestinal mais completa, o material de apoio do BioGuard inclui tambem um termo de remocao/captacao, por exemplo: dM_gut/dt = I_in - k_abs*M_gut - k_deg*M_gut. Essa extensao deve ser feita somente depois de k_deg estar minimamente identificado; caso contrario, diferentes mecanismos de perda ficariam confundidos.

## 10. Como k_deg deve ser estimado quando os dados forem obtidos

| Etapa | O que fazer |
| --- | --- |
| Extrair a serie temporal | Obter tempos e intensidade/concentracao de dsRNA intacto para cada compartimento/condicao. Se o artigo fornecer apenas figura, digitalizar os pontos mantendo o erro de leitura documentado. |
| Normalizar quando apropriado | Calcular C(t)/C0 para remover diferencas de escala entre replicas, sem apagar informacao de dose quando ela for relevante. |
| Ajustar o modelo | Ajustar C(t)=C0 exp(-k t) por regressao nao linear ou, se os erros permitirem, ln[C(t)/C0]=-k t. Nao forcar pontos abaixo do LOD a zero. |
| Verificar adequacao | Inspecionar residuos e curva observada versus prevista. Se houver duas fases claras, o modelo de k constante deve ser rejeitado/refinado. |
| Obter incerteza | Usar erro-padrao/IC do ajuste, replicas ou bootstrap. Com poucos dados, preferir intervalos/cenarios a uma falsa distribuicao precisa. |
| Calcular derivados | Para cada estimativa de k, calcular t_1/2=ln2/k e AUC(T)=C0/k*[1-exp(-kT)]. |
| Comparar condicoes | Estimar separadamente saliva, intestino, dsRNA nu/protegido e, se houver dados, condicao com dsRNase-2 silenciada. |
| Documentar unidade e janela | Registrar se k esta em min^-1 ou h^-1 e qual T foi usado na AUC; misturar escalas temporais distorce completamente a simulacao. |

## 11. Propagacao de incerteza e Monte Carlo

O entregavel do modulo pede que a incerteza dos parametros seja propagada. O procedimento recomendado e amostrar parametros plausiveis, recalcular C(t), t_1/2 e AUC em cada iteracao e resumir os percentis das saidas.

**Para i = 1...N:  k_i -> C_i(t) -> t_1/2,i -> AUC_i**

A distribuicao de k deve vir, preferencialmente, do proprio ajuste (ou de bootstrap/intervalo experimental). Como k e estritamente positivo, uma distribuicao em escala log pode ser conveniente quando a incerteza for multiplicativa, mas isso precisa ser justificado pelos dados.

A versao v2 possui um campo sigma_log10 associado ao grau de transferibilidade. Esse campo pode ser util para stress tests ou priors de cenario, mas nao deve ser apresentado como variancia experimental ou posterior estatistica se nao foi estimado a partir de dados. Se for usado, o relatorio deve dizer explicitamente que se trata de incerteza assumida.

**Nomenclatura recomendada**

Use "banda de incerteza" ou "intervalo percentil" quando a simulacao vier de ajuste frequentista, bootstrap ou cenarios. Reserve "intervalo/banda de credibilidade" para uma distribuicao com interpretacao bayesiana.

## 12. Lacunas que ainda impedem a calibracao final

| Lacuna | Estado | Impacto | Como fechar |
| --- | --- | --- | --- |
| k_deg local em D. maidis | AUSENTE no banco v2 em h^-1/min^-1 | Sem ele, M1 nao pode gerar AUC calibrada. | Extrair curva temporal C(t) do artigo/figura ou gerar ensaio local. |
| Curvas separadas por compartimento | Nao consolidadas | Sem isso, k_saliva e k_midgut ficam apenas hipoteticos. | Confirmar tempos, tecidos, controles e intensidade das bandas. |
| Limite de deteccao/quantificacao | Nao registrado | Impede converter "total"/"sem banda" em restricao numerica correta. | Buscar metodos do artigo ou usar dado densitometrico acima do LOD. |
| Incerteza experimental | Nao registrada para k | Monte Carlo nao deve inventar dispersao. | Obter replicas, IC, erro ou bootstrap da curva. |
| Relacao expressao dsRNase-2 -> atividade | Nao parametrizada | Impede converter reducao 23,6x em alteracao de k. | Tratar apenas direcionalmente ate haver atividade/proteina/cinetica. |
| Entrada oral I(t) | Ainda nao parametrizada para M1 | Necessaria para simular alimentacao de 3 dias. | Integrar depois com o modulo de entrega/ingestao. |

## 13. Entregavel computacional recomendado apos a calibracao

- Tabela de parametros por condicao: k_deg, unidade, t_1/2, C0, T, AUC e intervalo de incerteza.
- Curvas C(t) observadas e ajustadas para saliva e intestino medio, com bandas de incerteza.
- Distribuicao de AUC obtida por Monte Carlo e percentis (por exemplo, 2,5%, 50%, 97,5%).
- Analise de sensibilidade mostrando quanto a AUC varia quando k_deg varia dentro da faixa plausivel.
- Comparacao basal versus protecao/formulacao versus silenciamento de dsRNase-2 apenas quando houver dados comparaveis.
- Arquivo de parametros separado do notebook/codigo, sem valores numericos hardcoded, mantendo rastreabilidade de fonte e unidade.

## 14. Conclusao

O que os bancos permitem afirmar hoje: a degradacao de dsRNA e um gargalo real e relevante em D. maidis; dsRNase-2 participa desse processo; o grau de degradacao varia fortemente entre especies e condicoes; protecao pode alterar persistencia; e o valor de k_deg precisa ser tratado como condicional ao compartimento e ao desenho experimental.

O que os bancos ainda nao permitem afirmar: um k_deg numerico final para D. maidis, uma meia-vida calibrada, uma AUC biologicamente validada ou uma razao quantitativa entre o fold-change de dsRNase-2 e a taxa de degradacao.

Modelo aprovado para a versao 1: decaimento exponencial de primeira ordem por condicao, com k_saliva e k_midgut separados, observacoes abaixo do limite de deteccao tratadas como censuradas, dados de outras especies usados apenas em sensibilidade e incerteza propagada somente de fontes explicitamente documentadas.

**Proxima acao critica**

Obter a curva temporal de degradacao em D. maidis (idealmente com pontos intermediarios e replicas) e ajustar k_deg. Sem essa etapa, qualquer curva numerica apresentada como "predicao" seria apenas um cenario ilustrativo.

## Referencias e rastreabilidade

| Fonte | Uso no relatorio |
| --- | --- |
| [B1] Banco de evidencias.xlsx | Banco-base fornecido para o projeto. |
| [B2] BioGuard Banco de Evidencias v2.xlsx | Triagem, Parametros (long), Lacunas e Resumo da triagem. |
| [B3] Banco_de_evidencias_Revisado.xlsx | Aba Revisao cientifica e Resumo da revisao. |
| [M1] Divisao_Modelagem_BioGuard.pdf | Definicao de responsabilidades e entregaveis do modulo de degradacao/AUC. |
| [M2] Material de apoio - Nivelamento de Calculo aplicado ao Bioguard.pdf | Equacoes de degradacao, meia-vida, AUC e extensao intestinal. |
| [S] Shiflet, A. B.; Shiflet, G. W. Introduction to Computational Science: Modeling and Simulation for the Sciences. | Base metodologica de modelagem, simplificacao e simulacao. |
| Knockdown of double-stranded RNases enhances oral RNA interference in the corn leafhopper. | DOI: 10.1016/j.pestbp.2023.105618. |
| Biochemical Comparison of dsRNA Degrading Nucleases in Four Different Insects. | DOI: 10.3389/fphys.2018.00624. |
| Cloning and functional characterization of a double-stranded RNA-degrading nuclease in the tawny crazy ant. | DOI: 10.3389/fphys.2022.833652. |
| DsRNA-based carriers with pH-tuneable release kinetics for effective control of Psylliodes chrysocephala. | DOI: 10.1016/j.ijbiomac.2025.149697. |
| Development of efficient RNAi methods in the corn leafhopper Dalbulus maidis. | DOI: 10.1002/ps.6937. |

## Apendice A - Trilha de decisao por evidencia

| Origem | O que consta | Decisao |
| --- | --- | --- |
| B2, Banco v2, linha 11 | D. maidis / dsRNase-2 / in vitro / 12 h / degradacao_saliva = total (~100%) | Manter como evidencia central de estrutura; nao converter diretamente em k. A propria triagem diz que so define limite e pede extracao de curva temporal. |
| B2, Lacunas, k_deg | "AUSENTE"; nenhuma linha traz k em tempo^-1 | Confirma que a calibracao numerica ainda nao existe e que M1 depende de extrair C(t). |
| B3, Revisao, linhas 11 e 37 | Fonte primaria nao acessada na revisao; 12 h, 12-24 h e 23,6x precisam de conferencia | Usar como hipotese forte/direcional, nao como numero final. |
| B3, Revisao, linhas 7-9 e 33 | Vmax/Km confirmados; dose corrigida de 500 para 0,5 µM | Manter como comparacao de mecanismo; nao usar como k_deg. |
| B3, Revisao, linha 36 | Nylanderia: 23% remanescente apos 2 h | Cenario externo confirmado; calculo de k aparente apenas ilustrativo. |
| B3, Revisao, linha 35 | DOI de Aedes nao corresponde ao titulo registrado | Excluir valor de 4 min ate correcao. |
| B2, Parametros long, linhas de Psylliodes | Tempos termicos/UV sao 12-16 h e ~6 h; nao "15 dias" | Corrige conflacao entre janela do bioensaio e ensaio de estabilidade. Mantem uso apenas qualitativo. |
| B1/B3, BicC por dieta | 100-200 ng/µL por 3 dias | Sinaliza entrada continuada; nao usar dose ofertada como C0 interno nem em modelo de bolus. |

## Apendice B - Logica minima para implementacao

A implementacao computacional pode ser organizada com a seguinte sequencia conceitual, independentemente da linguagem de programacao:

1. Carregar parametros e unidades de um arquivo separado.
2. Definir C(t; C0, k) = C0 * exp(-k*t).
3. Ajustar k para cada condicao usando dados observados de C(t).
4. Calcular t_half = ln(2)/k.
5. Calcular AUC(T) = C0/k * (1 - exp(-k*T)).
6. Gerar amostras de k (e C0, se incerto) a partir da incerteza documentada.
7. Repetir curvas e AUC em Monte Carlo.
8. Resumir mediana/percentis e produzir grafico de sensibilidade.
9. Validar unidades e comparar previsao com dados nao usados no ajuste, quando houver.
10. Registrar fonte, condicao biologica e limitacoes junto de cada parametro.
