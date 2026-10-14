**BIOGUARD  FRENTE DE MODELAGEM**

# Decisões e metodologia do submodelo de degradação do dsRNA e exposição acumulada (AUC)

Revisão científica e metodológica consolidada em 13 de outubro de 2026

**O levantamento sustenta uma versão exploratória e rastreável do submodelo M1. A estrutura matemática de degradação e AUC está definida, mas a calibração numérica permanece condicionada à quantificação das bandas do ensaio ex vivo, à caracterização da incerteza e à distinção entre condições ex vivo e exposição in vivo.**

## 1 Objetivo e fronteiras do submodelo

Pergunta de modelagem: com que velocidade o dsRNA intacto desaparece nos contextos experimentais relevantes de *Dalbulus maidis*, como essa persistência se traduz em meia-vida e exposição acumulada e quais incertezas precisam ser propagadas antes da integração com os demais submodelos?

O M1 representa a degradação basal/aparente do dsRNA e a exposição acumulada. O submodelo temporal de dsRNase-2 fornece cenários de modulação da capacidade degradativa, enquanto a frente de dose-resposta utiliza a AUC para relacionar exposição e knockdown. A integração exige compatibilidade explícita de compartimento, tempo, unidade e condição experimental.

| **Submodelo / interface** | **Responsabilidade na integração** |
| --- | --- |
| M1 — degradação/AUC | k\_deg,app; dinâmica do dsRNA intacto; meia-vida; AUC relativa/absoluta; incerteza da degradação. |
| M3 — dsRNase-2 temporal | Estado temporal da nuclease; cenários de acoplamento funcional; eventual fator de modulação de k\_deg. |
| M2 — dose–resposta | Relação AUC–knockdown de BicC; EC50, Emax e coeficiente de Hill quando identificáveis. |

## 2 Decisões consolidadas

O ensaio de estabilidade disponível é ex vivo e realizado com homogenatos; portanto, qualquer taxa obtida deve ser interpretada como constante aparente de degradação sob as condições do ensaio (k\_deg,app), não como constante fisiológica universal in vivo. A cinética de primeira ordem é uma hipótese inicial de trabalho, cuja adequação precisa ser avaliada após a densitometria.

Os pontos de 1, 12 e 24 h tornam k\_deg,app potencialmente estimável por ajuste, condicionado à quantidade de bandas efetivamente quantificáveis. Se a informação for insuficiente ou fortemente censurada, devem ser reportadas faixas ou limites em vez de valores pontuais. AUC relativa é a primeira saída quantitativa defensável; AUC absoluta exige concentração interna efetiva.

## 3 Evidências específicas de *Dalbulus maidis*

A fonte principal para a calibração basal é Dalaisón-Fuentes et al. (2023). Os registros abaixo separam protocolo, observação experimental e inferência de modelagem; não transformam automaticamente ausência de banda em concentração nula. \[1\]

| **Item** | **Valor e contexto** | **Uso correto** |
| --- | --- | --- |
| Ensaio ex vivo | 1 µg de dsRNABicC incubado com 1 µg de homogenato; preparação em PBS; leitura em gel. | Base direta para estimar k\_deg,app sob as condições do ensaio; não é cinética in vivo. |
| Tempos de observação | 1, 12 e 24 h. | Pontos disponíveis para densitometria e ajuste; série temporal curta. |
| Glândulas salivares | Maior pressão degradativa; banda não detectável em 12 h. | Suporta cenário salivar mais degradativo; não usar 12 h como meia-vida. |
| Intestino médio | Degradação relevante, inferior à observada no homogenato salivar. | Justifica ajuste separado de k\_deg,app^MG. |
| Exposição oral | 200 ng/µL na dieta por 72 h, com renovação diária. | Concentração ofertada; não equivale a C0 interno nem a taxa ingerida. |
| Silenciamento de dsRNase-2 | Redução do transcrito e melhora da resposta ao RNAi oral. | Evidência direcional para modulação de k; não converte fold de mRNA em fold de k. |

### Observações e inferências

| **Observação** | **Situação atual** | **Interpretação** |
| --- | --- | --- |
| k\_deg,app^SG | Candidato a ajuste semiquantitativo pela Fig. S1. | Pode resultar em estimativa, faixa ou limite; depende dos pontos quantificáveis. |
| k\_deg,app^MG | Candidato a ajuste separado pela mesma figura. | Não impor o mesmo valor do contexto salivar. |
| C0\_eff interno | Não medido. | Bloqueia AUC absoluta, mas não impede análise relativa. |
| LOD do gel | Não reportado formalmente. | Ponto sem banda deve ser tratado como censurado: C &lt; LOD. |
| Efeito de dsRNase-2 sobre k | Direção biologicamente plausível, magnitude não medida. | Usar apenas em sensibilidade até existir curva local pós-silenciamento. |

A ausência de um ponto experimental explícito em t = 0 impede assumir automaticamente R(0) = 1. A normalização deve utilizar o controle adequado de cada tempo e manter um fator de amplitude livre quando necessário.

## 4 Evidências transferidas e limites de extrapolação

### *Aedes aegypti*

Giesbrecht et al. (2020) mostraram, em ensaio ex vivo de intestino, que o silenciamento de dsRNases reduz a degradação do dsRNA. No controle houve degradação intensa em dezenas de minutos, enquanto condições de silenciamento preservaram o dsRNA por mais tempo. \[2\]

Uso: evidência funcional auxiliar para a direção do efeito dsRNase → estabilidade do dsRNA. Não transferir tempos, taxas ou magnitudes para *Dalbulus maidis*, pois espécie, estágio, tecido e protocolo diferem.

### Critério de transferibilidade

Registrar espécie, estágio, tecido, via, matriz, concentração/massa, temperatura, duração, método de leitura e variável medida. Evidência externa pode sustentar mecanismo, faixa exploratória ou prioridade experimental, mas não substitui calibração local. A mesma cautela vale para diferenças entre homogenato ex vivo e compartimento in vivo.

## 5 Inventário revisado de parâmetros e estados

Classificações: medido = obtido diretamente; derivado = calculado a partir de parâmetros; transferido = proveniente de outro sistema; potencialmente ajustável = inferível sob hipóteses e com identificabilidade suficiente; assumido = cenário de sensibilidade; ausente = sem estimativa defensável.

| **Símbolo e unidade** | **Papel** | **Classificação e decisão** |
| --- | --- | --- |
| k\_deg,app^SG \| h⁻¹ | Taxa aparente de perda do dsRNA no homogenato de glândula salivar. | Potencialmente ajustável pela Fig. S1; se houver forte censura, reportar faixa/limite. |
| k\_deg,app^MG \| h⁻¹ | Taxa aparente de perda do dsRNA no homogenato de intestino médio. | Potencialmente ajustável separadamente; não igualar ao contexto salivar. |
| A\_R \| adimensional | Amplitude do ajuste R(t)=A\_R·exp(-k·t) quando R(0) não é conhecido. | Potencialmente ajustável; fixar em 1 apenas se a normalização justificar. |
| M0\_ex vivo \| µg | Massa inicial de dsRNABicC no ensaio de estabilidade. | Medido: 1 µg; condição experimental, não dose interna in vivo. |
| C0\_eff \| ng/µL | Concentração interna efetiva para AUC absoluta. | Ausente; concentração ofertada na dieta não substitui esse parâmetro. |
| t\_obs \| h | Tempos observados do ensaio ex vivo. | Medido: 1, 12 e 24 h. |
| T\_AUC \| h | Horizonte de integração da AUC. | Assumido por cenário; deve corresponder à pergunta e ao regime experimental. |
| t1/2,SG / t1/2,MG \| h | Meias-vidas derivadas sob hipótese de 1ª ordem. | Derivadas: ln(2)/k somente após obtenção de k\_deg,app. |
| AUC\_rel \| h | Exposição relativa acumulada obtida de R(t). | Derivada; primeira saída quantitativa recomendada. |
| AUC\_abs \| ng·h/µL | Exposição absoluta acumulada. | Derivada, mas bloqueada por C0\_eff e por k local. |
| Incerteza de k \| h⁻¹ | Erro/IC/distribuição para propagação de incerteza. | Estimável após ajuste/replicação; não inventar distribuição sem suporte. |
| LOD\_gel \| fração/intensidade | Limite de detecção do modelo de observação. | Ausente; não detecção implica C &lt; LOD, não C = 0. |
| α\_RNase \| adimensional | Fator efetivo de modulação de k pela condição de dsRNase-2. | Assumido para sensibilidade; magnitude local não medida. |
| M\_gut \| ng | Estado de massa de dsRNA numa extensão intestinal in vivo. | Estado de extensão; requer definição operacional e dados de entrada/remoção. |
| I\_in \| ng/h | Taxa de entrada de dsRNA no compartimento intestinal. | Ausente; concentração da dieta não determina ingestão por tempo. |
| k\_abs \| h⁻¹ | Remoção por absorção/captação na extensão intestinal. | Ausente; não confundir com degradação. |

Elementos de protocolo e de observação foram mantidos no inventário porque condicionam a identificabilidade, mas não devem ser confundidos com parâmetros biológicos. A extensão intestinal só deve ser ativada quando a pergunta exigir dinâmica in vivo e houver dados mínimos de entrada e remoção.

## 6 Dinâmica candidata e identificabilidade

### Estrutura fenomenológica para o ensaio ex vivo

A cinética de primeira ordem é uma hipótese testável e não uma conclusão imposta pelos artigos. Para a concentração ou quantidade intacta C(t):

dC/dt = -k\_deg,app · C

C(t) = C0 · exp(-k\_deg,app · t)

Como não há ponto experimental explícito em t = 0, a densitometria deve preferencialmente ser expressa por uma razão de intensidades no mesmo tempo:

R(t) = I\_tecido(t) / I\_controle(t)

R(t) = A\_R · exp(-k\_deg,app · t)

Se A\_R for desconhecido, taxa e amplitude precisam ser estimadas conjuntamente. Dois pontos quantificáveis apenas determinam uma solução exata sem permitir avaliação robusta do erro; três ou mais pontos úteis são preferíveis. Pontos não detectáveis exigem tratamento de censura.

### Limite imposto por uma observação não detectável

Se uma banda é não detectável em t\* e o limite relativo de detecção R\_lim for conhecido, a observação pode restringir o parâmetro em vez de ser convertida em zero:

R(t\*) &lt; R\_lim  ⇒  k\_deg,app &gt; ln(A\_R/R\_lim) / t\*

Sem A\_R e R\_lim definidos, a ausência de banda apenas informa que o sinal caiu abaixo da detecção. Não calcular k = 1/12 h e não usar 12 h como meia-vida.

### Avaliação da hipótese de primeira ordem

Após a densitometria, comparar ajuste, resíduos e coerência entre tempos. Um bom ajuste com poucos pontos indica compatibilidade, não prova mecanismo. Se houver padrão sistemático de resíduos ou dependência incompatível com uma taxa constante, considerar estrutura mais flexível antes de interpretar k biologicamente.

## 7 Exposição acumulada e interpretação da AUC

### AUC relativa no ensaio ex vivo

Quando a escala absoluta interna não é conhecida, a saída mais defensável é a área sob a curva relativa. Para R(t)=A\_R·exp(-k·t):

AUC\_rel(T) = ∫₀ᵀ R(t) dt = (A\_R/k) · \[1 - exp(-k·T)\]

Como R(t) é adimensional, AUC\_rel tem unidade de tempo. Ela representa tempo equivalente de exposição relativa ao dsRNA intacto, não massa total nem dose absorvida.

### AUC absoluta

AUC\_abs(T) = ∫₀ᵀ C(t) dt = (C0\_eff/k) · \[1 - exp(-k·T)\]

AUC\_abs só deve ser apresentada como resultado físico quando C0\_eff representar a concentração efetiva no compartimento definido. Usar 200 ng/µL da dieta como C0\_eff produziria uma falsa equivalência entre oferta externa e exposição interna.

### Extensão in vivo com entrada e remoção

dM\_gut/dt = I\_in(t) - k\_abs·M\_gut - k\_deg·M\_gut

Essa extensão usa massa M\_gut em ng para manter consistência dimensional com I\_in em ng/h. Ela só deve ser ativada quando houver necessidade de representar alimentação repetida e quando entrada/remoção tiverem hipóteses explícitas. I\_in e k\_abs permanecem ausentes no conjunto atual.

## 8 Compartimentos e contrato de integração

### Heterogeneidade entre contextos

Os resultados ex vivo justificam examinar glândula salivar e intestino médio separadamente. Isso não equivale a afirmar que os k\_deg,app estimados em homogenato são as taxas fisiológicas desses compartimentos in vivo. Na versão inicial, comparar cenários por contexto e manter a origem experimental explícita.

### Contrato de integração entre submodelos

| **Interface** | **Definição necessária antes de integrar** |
| --- | --- |
| Compartimento | Onde C(t) ou M(t) é definida e onde a degradação modulada atua. |
| Tempo | Origem comum; início/fim de exposição; tempos de coleta; horizonte T da AUC. |
| Unidades | h para tempo; h⁻¹ para taxas; concentração, massa e AUC dimensionalmente consistentes. |
| Entrada | Concentração da dieta, massa administrada, taxa ingerida e dose interna mantidas distintas. |
| Basal | k\_deg compatível com tecido/matriz, temperatura, formulação e condição experimental. |
| Resposta | A função dose–resposta deve usar a AUC do mesmo compartimento e horizonte definidos no M1. |

### Compatibilidade experimental

Um k\_deg,app obtido em homogenato ex vivo não deve ser reutilizado como constante in vivo sem hipótese explícita. A interface com o submodelo temporal de dsRNase-2 deve distinguir redução de transcrito, atividade funcional e mudança efetiva na degradação. A interface com dose–resposta deve preservar a definição da exposição utilizada.

## 9 Calibração, incerteza e sensibilidade

### Preparação dos dados

Quantificar a Fig. S1 em resolução adequada, registrar intensidade de banda, controle contemporâneo, tecido, tempo e eventual replicação. Normalizar de forma rastreável e preservar pontos não detectáveis como censurados. Se houver replicatas, manter o nível biológico separado de repetições técnicas.

### Ajuste e avaliação

Definir função de observação e modelo de erro antes da estimação. Ajustar o menor conjunto sustentado pelos dados, começando por A\_R e k\_deg,app quando ambos forem necessários. Avaliar resíduos, intervalos e correlação entre parâmetros. Não chamar o mesmo conjunto de dados de calibração e validação independente.

### Plano mínimo de sensibilidade

| **Incerteza / hipótese** | **Comparação proposta** |
| --- | --- |
| k\_deg,app | Faixa compatível com o ajuste, censura e incerteza experimental. |
| A\_R | Livre versus fixado em 1 quando a normalização permitir. |
| T\_AUC | Horizontes coerentes com 1, 12 e 24 h e, posteriormente, janelas biológicas justificadas. |
| C0\_eff | Somente para cenários de AUC absoluta; rotular claramente como assumido se não medido. |
| α\_RNase | Ausência, modulação intermediária e forte; não atribuir probabilidade sem dados. |
| Extensão in vivo | Variar I\_in e k\_abs apenas se a estrutura intestinal for ativada. |

Monte Carlo quantitativo deve ser iniciado somente quando houver distribuição ou intervalo defensável para os parâmetros. Na ausência disso, utilizar análise de sensibilidade por faixas declaradas. Frequência de cenários favoráveis sob uma amostragem arbitrária não equivale a probabilidade de sucesso.

## 10 Banco de evidências e próximos passos

### Registro rastreável

Cada evidência relevante ao M1 deve registrar referência/DOI, seção ou figura, espécie, estágio, tecido/matriz, tratamento, concentração/massa, duração, temperatura quando disponível, tempo de observação, método analítico, controle, replicação, incerteza e classificação como medido, derivado, transferido, potencialmente ajustável, assumido ou ausente.

### Sequência recomendada para a etapa inicial

1. Obter a Figura S1 em resolução adequada e quantificar as bandas de glândula salivar e intestino médio.

2. Construir R(t) usando o controle contemporâneo apropriado e documentar a normalização.

3. Ajustar k\_deg,app por tecido somente se houver informação suficiente; caso contrário, reportar faixa ou limite.

4. Calcular t1/2 e AUC\_rel com propagação da incerteza permitida pelos dados.

5. Atualizar o Banco de Evidências com os valores derivados, método de extração e limitações.

6. Só depois ativar Monte Carlo e testar integração com dsRNase-2 temporal e dose–resposta.

### Medições que reduzem as principais lacunas

Priorizar uma série temporal mais densa de degradação em *D. maidis*, especialmente em tempos precoces; determinar intensidade/limite de detecção; medir degradação após silenciamento de dsRNase-2; quantificar dsRNA recuperado no compartimento relevante após exposição oral; e, para a extensão intestinal, estimar entrada e remoção não degradativa.

### Critério de conclusão

O levantamento está consolidado quando cada parâmetro possui símbolo, unidade, papel, proveniência, classificação e decisão de uso; as condições do protocolo estão separadas dos parâmetros; os derivados são rastreáveis; e as lacunas são convertidas em medições ou cenários explícitos. A calibração quantitativa só deve ser apresentada quando a informação temporal e a identificabilidade forem suficientes.

## 11 Referências e acesso aos artigos

Referências numéricas utilizadas no texto. Os DOIs e fontes principais são indicados para rastreabilidade.

\[1\] DALAISÓN-FUENTES, L. I. et al. Knockdown of double-stranded RNases (dsRNases) enhances oral RNA interference (RNAi) in the corn leafhopper, Dalbulus maidis. Pesticide Biochemistry and Physiology, v. 196, art. 105618, 2023.<br>DOI [10.1016/j.pestbp.2023.105618](<https://doi.org/10.1016/j.pestbp.2023.105618>)

\[2\] GIESBRECHT, D. et al. RNA interference is enhanced by knockdown of double-stranded RNases in the Yellow Fever Mosquito Aedes aegypti. Insects, v. 11, n. 6, art. 327, 2020.<br>DOI [10.3390/insects11060327](<https://doi.org/10.3390/insects11060327>)

\[3\] SHIFLET, A. B.; SHIFLET, G. W. Introduction to Computational Science: Modeling and Simulation for the Sciences. Princeton: Princeton University Press, 2006.

\[4\] BIOGUARD. Material de apoio de cálculo: nivelamento Dry Lab — cálculo aplicado. Material interno do projeto, 2026.

*Documento técnico de trabalho. Parâmetros assumidos, faixas de sensibilidade e resultados derivados devem permanecer explicitamente diferenciados de medições experimentais.*
