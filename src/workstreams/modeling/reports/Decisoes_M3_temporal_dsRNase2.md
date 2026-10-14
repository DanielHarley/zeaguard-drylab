**BIOGUARD  FRENTE DE MODELAGEM**

# Decisões e metodologia do submodelo temporal de dsRNase 2

Responsável pelo submodelo: Marcos<br>Revisão científica e metodológica consolidada em 13 de outubro de 2026

**O levantamento sustenta a construção de uma versão exploratória do submodelo. A implementação depende da formalização da dinâmica, das entradas por via de administração e das faixas de sensibilidade. As evidências disponíveis não sustentam uma recomendação quantitativa calibrada do intervalo ótimo.**

## 1 Objetivo e fronteiras do submodelo

Pergunta de modelagem: como o silenciamento de dsRNase-2 altera a capacidade de degradação do dsRNA ao longo do tempo e modifica a exposição ao dsRNA-alvo em *Dalbulus maidis*?

Marcos representa a dinâmica do transcrito da nuclease e explora seu acoplamento à capacidade degradativa. Tales fornece a degradação basal e o modelo de exposição. Gabriel fornece a relação exposição–resposta de BicC. A divisão de responsabilidades não elimina a necessidade de definir conjuntamente os compartimentos, as unidades e as condições experimentais das interfaces.

| **Responsável** | **Interface e responsabilidade** |
| --- | --- |
| Marcos | Estado temporal da nuclease; atraso; recuperação; cenários de acoplamento funcional. |
| Tales | k\_deg,0; dinâmica do dsRNA-alvo; concentração C(t); AUC no compartimento definido. |
| Gabriel | Relação exposição–knockdown de BicC; EC50, Emax e coeficiente de Hill, quando identificáveis. |

## 2 Decisões consolidadas

As 48 h são uma condição do protocolo, não uma medida de início de silenciamento. Expressão de mRNA não equivale à atividade enzimática. Persistência de redução de transcrito não identifica recuperação. Meia-vida proteica e magnitude do acoplamento funcional permanecem sem estimativa empírica específica. \[1–5\]

Os resultados de espécies externas informam plausibilidade e cenários; não são parâmetros diretamente transferíveis. A versão inicial deve produzir mapas de sensibilidade e prioridades de medição, sem apresentar um ótimo artificial.

## 3 Evidências específicas de *Dalbulus maidis*

A fonte principal é Dalaisón-Fuentes et al. (2023). Os itens abaixo mantêm separados protocolo, observações e valores derivados. Métodos 2.3 e 2.5; resultados 3.2–3.4; figuras 3, 4 e 8 e figura suplementar S1. \[1\]

| **Item** | **Valor e contexto** | **Uso correto** |
| --- | --- | --- |
| Anti-dsRNase-2 injetado | 200 ng/µL; fêmeas adultas recém-emergidas. | Condição experimental; não é massa por inseto. |
| Intervalo pós-injeção | 48 h de recuperação da lesão. | Intervalo do protocolo; não equivale a τ\_on. |
| dsRNA-BicC oral | 200 ng/µL durante 72 h; renovação diária. | Entrada de dieta; não é dose absorvida. |
| Leituras sequenciais | 1 e 7 dias após o término da alimentação. | 144 e 288 h desde a injeção, por derivação. |
| Co-feeding | 72 h; 200 ng/µL de cada dsRNA. | Administração simultânea; Δt = 0. |
| Leituras do co-feeding | 1 e 7 dias após o término da alimentação. | 96 e 240 h desde o início da exposição oral. |
| RT-qPCR | 3 réplicas biológicas; barras com SEM; triplicatas técnicas nos métodos. | Réplicas técnicas não ampliam o n biológico. |
| Volume de injeção | Média de 0,5 µL informada em 2022. \[2\] | ≈100 ng somente se o volume foi mantido em 2023. |

### Observações e conversões

| **Observação** | **Resultado** | **Interpretação** |
| --- | --- | --- |
| dsRNase2/β na glândula salivar | 23,6 vezes; residual 0,042373; knockdown 95,7627%. | Transcrito no primeiro ponto de leitura da figura 4. |
| dsRNase2/β no intestino médio | 33,1 vezes; residual 0,030211; knockdown 96,9789%. | Transcrito no primeiro ponto de leitura da figura 4. |
| Expressão entre tecidos | ≈600 vezes maior na glândula salivar. | Razão de expressão relativa; não é peso funcional. |
| Ensaio de degradação | Banda não detectável em 12 h no homogenato salivar. | Observação sob condições ex vivo; não identifica k. |
| Persistência no co-feeding | Redução significativa no intestino médio no dia 7. | Restringe a trajetória; não estima k\_rec. |

Cálculos: residual = 1/F; knockdown (%) = 100 × (1 − 1/F). Os percentuais resultam da inversão dos folds publicados. Não representam medições diretas de atividade nem trazem intervalos de confiança próprios. A inversão de uma média não equivale necessariamente à média das inversões.

## 4 Evidências transferidas e limites de extrapolação

### *Nezara viridula*

Sharma et al. (2021) apresentam expressão em 48, 72, 96 e 120 h pós-injeção na figura suplementar S1. O segundo dsRNA foi oferecido após 48 h, quando o silenciamento já havia sido constatado. Esse resultado não identifica o instante exato de início. \[3\]

No ensaio funcional, adultos foram injetados e saliva e conteúdo intestinal coletados após 72 h. A saliva controle degradou o dsRNA completamente em 30 min; após silenciamento, uma fração permaneceu intacta até 120 min. Os ensaios de dinâmica em ninfas e os ensaios funcionais em adultos não devem ser tratados como uma única série temporal. \[3, seção 2.6 e figura 5\]

Uso: sustentação do mecanismo e construção de cenários temporais. Não transferir a constante de silenciamento, o atraso ou a recuperação diretamente para *D. maidis*.

### *Bemisia tabaci*

Luo et al. (2017) administraram dsRNA contra dsRNase1/2 simultaneamente ao dsGFP ou três dias antes. A expressão caiu aproximadamente 25–30%. O pré-tratamento contra dsRNase2 ou ambas as nucleases aumentou significativamente a preservação de dsGFP. \[4, seção 3.4 e figura 4\]

A meia-vida curta das proteínas é uma hipótese da discussão, sem medição direta. O artigo sustenta a plausibilidade de pré-tratamento e coadministração; não determina que 72 h sejam o intervalo ótimo de *D. maidis*. \[4, discussão\]

### *Aedes aegypti*

Giesbrecht et al. (2020) alimentaram larvas por cinco dias com *E. coli* expressando shRNAs. Extratos intestinais controles degradaram virtualmente todo o dsRNA em 30 min. O tratamento contra 4103 apresentou ausência de degradação significativa até 60 min; contra 8858, até 30 min, com degradação substancial aos 60 min. \[5, seção 3.3 e figura 3\]

Uso: evidência funcional auxiliar distante. A espécie, o estágio larval e a entrega bacteriana diferem do protocolo específico de *D. maidis*. Os tempos do ensaio ex vivo não podem parametrizar diretamente a dinâmica in vivo.

### Critério de transferibilidade

Registrar espécie, estágio, tecido, via, dose, formulação, duração e variável medida. Pertencer à mesma ordem taxonômica aumenta a relevância comparativa, mas não demonstra equivalência cinética. A evidência sustenta uma direção mecanística plausível, sem estabelecer uma relação quantitativa universal entre transcrito e degradação.

## 5 Inventário revisado de parâmetros e estados

Classificações: não identificado significa ausência de estimativa defensável no conjunto consultado; potencialmente ajustável requer modelo e teste de identificabilidade; assumido significa cenário de sensibilidade; definição significa convenção matemática.

| **Símbolo e unidade** | **Papel** | **Classificação e decisão** |
| --- | --- | --- |
| τ\_on  \|  h | Atraso operacional do silenciamento. | Não identificado em *D. maidis*. Definir se significa atraso efetivo, limiar biológico ou detecção estatística. |
| k\_sil,mRNA  \|  h⁻¹ | Taxa efetiva no modelo reduzido de transcrito. | Potencialmente ajustável sob hipóteses; identificabilidade ainda não demonstrada. |
| k\_rec  \|  h⁻¹ | Retorno do estado de transcrito ao basal na estrutura candidata. | Não identificado. Não confundir com recuperação funcional ou término de RNAi. |
| k\_sil,functional  \|  h⁻¹ | Taxa de queda funcional em eventual estrutura alternativa. | Não identificado. Não estimar diretamente com RT-qPCR; dispensável na estrutura com P(t). |
| k\_P  \|  h⁻¹ | Resposta do estado proteico/funcional à variação de M. | Não identificado; assumir para testar atraso funcional, sem alegar meia-vida medida. |
| t½,P  \|  h | Meia-vida proteica na hipótese de perda de primeira ordem. | t½,P = ln(2)/k\_P somente sob essa hipótese. Não estimar simultaneamente ambos. |
| η\_R  \|  adimensional | Participação basal da nuclease na decomposição proposta de k\_deg. | Assumido para sensibilidade; 0 ≤ η\_R ≤ 1. Sem fração específica medida. |
| γ  \|  adimensional | Curvatura do acoplamento ao estado residual. | Assumido; γ &gt; 0. Variar γ não substitui atraso proteico. |
| R\_c  \|  adimensional | Limiar em modelo alternativo. | Assumido apenas se houver pergunta que justifique testar limiar; omitir da V1 básica. |
| M(0) e P(0) | Estados relativos inicialmente basais. | Definição igual a 1 quando o basal e o instante inicial forem compatíveis. |
| u(t)  \|  adimensional | Estímulo efetivo de silenciamento. | Entrada/hipótese estrutural a definir por regime; não é automaticamente concentração da dieta. |
| k\_deg,0  \|  h⁻¹ | Degradação basal na interface com Tales. | Fora do escopo de estimativa de Marcos; compatibilizar compartimento e condições. |
| Parâmetros Hill/BicC | Relação exposição–resposta. | Interface com Gabriel; não recalibrar neste levantamento. |

M(t) representa transcrito relativo. P(t) é um estado funcional hipotético na extensão com atraso; não constitui proteína ou atividade experimentalmente observada. As faixas numéricas dos parâmetros assumidos precisam ser justificadas antes de executar a análise.

## 6 Dinâmica candidata e identificabilidade

### Estrutura fenomenológica para exploração

A equação abaixo é uma proposta matemática testável, não uma equação validada pelos artigos. Ela formaliza a queda de transcrito e seu retorno ao basal:

dM/dt = k\_rec (1 − M) − k\_sil u(t) M

M é adimensional; k\_rec e k\_sil têm unidade h⁻¹; u(t) é um estímulo efetivo adimensional. Com taxas e entrada não negativas, a estrutura preserva M ≥ 0 e, para M(0) ≤ 1, mantém M ≤ 1. Sem estímulo, retorna ao basal. Para estímulo constante u₀, M\* = k\_rec/(k\_rec + k\_sil u₀).

Esse limite de 0–1 pertence à estrutura proposta. Dados de expressão relativa podem ultrapassar 1 por regulação ou variabilidade. Se isso ocorrer de modo consistente, revisar a estrutura ou modelar um basal variável; não truncar silenciosamente as observações.

### Definição da entrada e da memória de RNAi

Definir separadamente u\_injeção(t) e u\_oral(t). Um pulso de administração não representa automaticamente um pulso de atividade de RNAi. A persistência intracelular pode continuar após a retirada do dsRNA. Uma janela atrasada de u(t), com início τ\_on e término T\_eff, é apenas um cenário; T\_eff também deve entrar no inventário se for utilizado.

Sem exposição/atividade efetiva medida, há ambiguidade entre k\_sil e a amplitude de u(t). Fixar uma normalização explícita de u para interpretar k\_sil. τ\_on deve ter uma definição operacional; o primeiro tempo significativamente reduzido não é necessariamente o início biológico.

### Por que um ponto tardio não identifica taxa e atraso

Como demonstração, suponha queda exponencial sem recuperação e com basal conhecido:

M(t) = exp\[−k\_sil (t − τ\_on)\]   para t &gt; τ\_on

k\_sil (t₁ − τ\_on) = −ln\[M(t₁)\]

Uma observação restringe uma combinação de parâmetros. Muitos pares de taxa e atraso reproduzem o mesmo ponto. Acrescentar recuperação, síntese ou memória do estímulo pode ampliar a ambiguidade. Não interpretar a convergência de um ajuste como demonstração de identificabilidade.

A análise deve distinguir identificabilidade estrutural, imposta pelas equações e variáveis observadas, de identificabilidade prática, dependente da quantidade, distribuição temporal e incerteza dos dados. Usar perfil de verossimilhança quando o ajuste e o modelo de erro forem definidos. \[6\]

## 7 Acoplamento entre transcrito e degradação

### Versão instantânea

k\_deg,eff(t) = k\_deg,0 \[(1 − η\_R) + η\_R M(t)<sup>γ</sup>\]

A expressão é dimensionalmente coerente para M normalizado, 0 ≤ η\_R ≤ 1 e γ &gt; 0. No basal M = 1, k\_deg,eff = k\_deg,0. Para M = 0, k\_deg,eff = k\_deg,0(1 − η\_R). Essa decomposição assume um componente residual constante e um componente modulável associado à nuclease.

Na V1 instantânea, η\_R e γ são parâmetros efetivos. Sua interpretação como fração enzimática e mecanismo molecular exige evidência funcional. O uso de M como proxy associa transcrito e capacidade degradativa no mesmo instante, assumindo ausência de memória funcional relevante.

### Extensão estrutural com atraso funcional

dP/dt = k\_P \[M(t) − P(t)\]   com P(0) = 1

k\_deg,eff(t) = k\_deg,0 \[(1 − η\_R) + η\_R P(t)<sup>γ</sup>\]

P é um estado normalizado sob as hipóteses de tradução proporcional ao transcrito, perda de primeira ordem e estado basal equilibrado. A extensão não descreve explicitamente secreção ou transporte. k\_P permanece assumido para sensibilidade. O objetivo é verificar se a persistência de proteína/atividade altera a decisão temporal.

Comparar resposta funcional rápida, intermediária e lenta. Variar γ altera a curvatura da relação entre estado e degradação; não substitui o atraso de P. A estrutura instantânea corresponde a uma aproximação de resposta funcional suficientemente rápida para a escala temporal analisada.

### Limite da hipótese de meia vida curta

A meia-vida curta foi apresentada como hipótese na literatura. \[1,4\] Na estrutura linear dP/dt = k\_P(M − P), com M constante, P tende a M: uma resposta rápida acelera a aproximação, mas não amplifica por si só a redução proporcional no equilíbrio. Uma redução funcional desproporcional exige mecanismos adicionais ou um acoplamento não linear; não atribuí-la automaticamente ao turnover.

### Limites dos ensaios de gel

Ausência de banda indica concentração abaixo do limite de detecção nas condições do ensaio, não concentração exatamente nula. Para C(t) = C₀ exp(−kt), uma observação C(t\*) &lt; C\_lim pode restringir k &gt; ln(C₀/C\_lim)/t\*, se C₀ e C\_lim forem conhecidos e a cinética for aplicável. Não calcular k = 1/12 h nem usar 12 h como meia-vida.

## 8 Compartimentos e comparação de regimes

### Via de administração e intervalo

O protocolo sequencial combina injeção anti-dsRNase-2 e alimentação com dsRNA-alvo; o co-feeding administra ambos oralmente. \[1\] A comparação não isola o intervalo: via, disponibilidade e dinâmica de entrada também mudam. Tratar os regimes como cenários distintos.

Não reutilizar uma dinâmica calibrada por injeção como dinâmica oral sem evidência ou hipótese explícita. Para investigar o efeito exclusivo de Δt, comparar administrações com via, dose, formulação e duração de exposição equivalentes, variando o início relativo do segundo dsRNA.

### Heterogeneidade entre tecidos

A expressão relativa elevada na glândula salivar e os resultados ex vivo justificam examinar heterogeneidade. \[1\] A razão de transcritos não informa diretamente quantidade total de proteína, atividade secretada, volume de contato ou tempo de residência do dsRNA. Não utilizar a razão de expressão como peso automático da contribuição funcional.

Na V1, escolher um compartimento operacional ou comparar cenários salivar e intestinal. Um estado agregado é aceitável para exploração se sua definição e ponderação forem explicitadas. Se forem usados M\_SG e M\_MG, não ajustar cada tecido com o mesmo estado sem testar essa restrição. Uma V2 com dois compartimentos exige dados que sustentem estados, transportes e observações adicionais.

### Contrato de integração com Tales e Gabriel

| **Interface** | **Definição necessária antes de integrar** |
| --- | --- |
| Compartimento | Onde C(t) é definida e onde a degradação modulada atua. |
| Tempo | Origem comum; início e fim de cada administração; tempos de coleta. |
| Unidades | h para tempo; h⁻¹ para taxas; concentração e AUC consistentes. |
| Entrada | Concentração da dieta, massa administrada e dose absorvida mantidas distintas. |
| Basal | k\_deg,0 compatível com tecido, temperatura, formulação e condição. |
| Resposta | Função de BicC utiliza a exposição no compartimento e horizonte definidos. |

### Compatibilidade experimental

Um k\_deg obtido em homogenato ex vivo não é automaticamente uma constante in vivo. Na transferência para exposição oral, registrar a hipótese e analisar sua influência. A separação entre autores não deve ocultar essa incerteza na fronteira entre submodelos.

## 9 Calibração incerteza e sensibilidade

### Preparação dos dados

Registrar o calibrador e o controle de cada tempo antes de interpretar expressão relativa como estado basal-normalizado. Na figura 8, o calibrador declarado é o controle no primeiro dia pós-tratamento. \[1\] Para estimar efeito específico no tempo, avaliar a razão tratamento/controle contemporâneo; para modelar expressão absoluta relativa, representar a possível variação basal.

Preferir dados individuais de Cq e eficiência quando disponíveis. Manter n biológico separado de triplicatas técnicas e registrar agrupamento de tecidos. A transformação de fold exige propagação de incerteza; não usar o percentual derivado como observação independente do fold que o gerou. Normalização, eficiência e limites de detecção devem seguir práticas transparentes de RT-qPCR. \[7\]

### Ajuste e avaliação

Especificar função de observação e modelo de erro. Escolher escala de ajuste compatível com a análise de qPCR; quando houver dados adequados, avaliar ΔCq ou log da quantidade relativa. Ajustar o menor conjunto de parâmetros sustentado pelos dados. Identificar correlações, perfis abertos e dependência das condições fixadas. \[6,7\]

Os mesmos pontos não constituem calibração e validação independente. Nesta etapa, usar “compatibilidade com observações”. Reservar validação preditiva para tempos, regimes ou experimentos não utilizados no ajuste. Não há simulações ou ajustes concluídos neste documento.

### Plano mínimo de sensibilidade

| **Incerteza** | **Comparação proposta** |
| --- | --- |
| Magnitude funcional | η\_R entre ausência e forte contribuição; justificar os valores internos. |
| Forma do acoplamento | γ &lt; 1, γ = 1 e γ &gt; 1, com domínio e grade declarados. |
| Dinâmica de mRNA | τ\_on, k\_sil, k\_rec e duração efetiva do estímulo, quando usados. |
| Memória funcional | Acoplamento instantâneo versus P(t) com diferentes k\_P. |
| Regime e tecido | Entradas específicas por via; cenários salivar e intestinal. |

Faixas ainda não justificadas devem ser rotuladas como exploratórias. Informar limites, amostragem linear ou logarítmica, restrições entre parâmetros e incerteza estrutural. Frequência de cenários favoráveis não equivale a probabilidade de sucesso.

### Definição do objetivo e da robustez

Definir antes da comparação o objetivo J(Δt): por exemplo, AUC do dsRNA-alvo no compartimento relevante e em janela relativa ao início do alvo. Só converter exposição em resposta se a interface de Gabriel for sustentada. Um horizonte global fixo pode favorecer artificialmente administrações mais precoces.

Relatar regiões em que a preferência muda. Distinguir resultado invariável em todo o domínio, resultado frequente sob uma amostragem definida e resultado dependente de hipóteses. A análise deve identificar decisões robustas ou medições prioritárias, sem converter uma maioria arbitrária em recomendação validada.

## 10 Banco de evidências e próximos passos

### Registro rastreável

Cada registro deve conter identificador, referência e DOI, seção/figura, espécie, estágio, tecido, tratamento, via, concentração/massa/volume, duração, origem do tempo, método analítico, calibrador, n biológico, réplicas técnicas, agrupamento, incerteza e classificação como medido, derivado, hipótese ou transferência.

Registrar folds como estimativas de expressão relativa obtidas por análise, não como dados brutos. Manter fórmulas dos valores derivados. Preservar valores não significativos com sua incerteza; ausência de significância não demonstra ausência de efeito. Documentar limites de detecção e condições ex vivo.

### Sequência recomendada para a etapa inicial

1. Consolidar os registros específicos de *D. maidis* e distinguir as observações de injeção e co-feeding.

2. Escolher compartimento, variável observada e estrutura mínima; formalizar a entrada e o basal.

3. Avaliar identificabilidade antes de estimar simultaneamente atraso, taxa e recuperação.

4. Justificar faixas de sensibilidade e comparar as estruturas instantânea e com atraso funcional.

5. Integrar com Tales e Gabriel apenas após compatibilizar unidades, tempos e condições.

6. Definir o objetivo e produzir mapas de decisão; planejar medições nas regiões de maior incerteza.

### Medições que reduzem as principais lacunas

Priorizar série temporal precoce de transcrito para restringir início e velocidade; pontos após a retirada da exposição para separar persistência do estímulo e recuperação; medidas funcionais por tecido para testar o acoplamento; quantificação de exposição/ingestão para interpretar a via oral. O número de tempos e réplicas deve ser definido por planejamento e variabilidade, não por uma regra fixa.

Não é necessário concluir o problema biológico nesta fase. O entregável deve mostrar quais hipóteses são testáveis, quais parâmetros permanecem não identificados e quais dados têm maior valor para a próxima etapa.

### Critério de conclusão

O levantamento está consolidado quando cada parâmetro tem símbolo, unidade, papel, proveniência e classificação; as condições do protocolo estão separadas dos parâmetros; os derivados são rastreáveis; as evidências externas estão qualificadas; e as lacunas são convertidas em hipóteses e medições prioritárias.

**A etapa de modelagem exploratória estará executável quando as equações, as entradas, as faixas e o objetivo forem definidos. A calibração quantitativa e a recomendação de Δt permanecem condicionadas à identificabilidade e à evidência funcional. Não apresentar parâmetros assumidos ou modelos candidatos como resultados medidos.**

## 11 Referências e acesso aos artigos

Referências numéricas utilizadas no texto. Os links de DOI e de texto integral são clicáveis. A cópia de 2023 no CONICET é um manuscrito aceito identificado como Journal Pre-proof.

\[1\] DALAISÓN-FUENTES, L. I. et al. Knockdown of double-stranded RNases (dsRNases) enhances oral RNA interference (RNAi) in the corn leafhopper, *Dalbulus maidis*. Pesticide Biochemistry and Physiology, v. 196, art. 105618, 2023.

[DOI 10.1016/j.pestbp.2023.105618](<https://doi.org/10.1016/j.pestbp.2023.105618>)  \|  [Acesso ao artigo](<https://ri.conicet.gov.ar/bitstream/handle/11336/221063/CONICET_Digital_Nro.4a1048d9-1b4c-430a-a243-e47c5004b38c_K.pdf?sequence=11>)

\[2\] DALAISÓN-FUENTES, L. I. et al. Development of efficient RNAi methods in the corn leafhopper *Dalbulus maidis*, a promising application for pest control. Pest Management Science, v. 78, n. 7, p. 3108–3116, 2022.

[DOI 10.1002/ps.6937](<https://doi.org/10.1002/ps.6937>)  \|  [Acesso ao artigo](<https://www.researchgate.net/publication/360084605_Development_of_efficient_RNAi_methods_in_the_corn_leafhopper_Dalbulus_maidis_a_promising_application_for_pest_control>)

\[3\] SHARMA, R.; TANING, C. N. T.; SMAGGHE, G.; CHRISTIAENS, O. Silencing of double-stranded ribonuclease improves oral RNAi efficacy in Southern Green Stinkbug *Nezara viridula*. Insects, v. 12, n. 2, art. 115, 2021.

[DOI 10.3390/insects12020115](<https://doi.org/10.3390/insects12020115>)  \|  [Acesso ao artigo](<https://backoffice.biblio.ugent.be/download/8705730/8705737>)

\[4\] LUO, Y. et al. Towards an understanding of the molecular basis of effective RNAi against a global insect pest, the whitefly *Bemisia tabaci*. Insect Biochemistry and Molecular Biology, v. 88, p. 21–29, 2017.

[DOI 10.1016/j.ibmb.2017.07.005](<https://doi.org/10.1016/j.ibmb.2017.07.005>)  \|  [Acesso ao artigo](<https://pmc.ncbi.nlm.nih.gov/articles/PMC5595799/>)

\[5\] GIESBRECHT, D. et al. RNA interference is enhanced by knockdown of double-stranded RNases in the Yellow Fever Mosquito *Aedes aegypti*. Insects, v. 11, n. 6, art. 327, 2020.

[DOI 10.3390/insects11060327](<https://doi.org/10.3390/insects11060327>)  \|  [Acesso ao artigo](<https://pmc.ncbi.nlm.nih.gov/articles/PMC7349537/>)

\[6\] RAUE, A. et al. Structural and practical identifiability analysis of partially observed dynamical models by exploiting the profile likelihood. Bioinformatics, v. 25, n. 15, p. 1923–1929, 2009.

[DOI 10.1093/bioinformatics/btp358](<https://doi.org/10.1093/bioinformatics/btp358>)  \|  [Acesso ao artigo](<https://academic.oup.com/bioinformatics/article/25/15/1923/213246>)

\[7\] BUSTIN, S. A. et al. MIQE 2.0: Revision of the Minimum Information for Publication of Quantitative Real-Time PCR Experiments Guidelines. Clinical Chemistry, v. 71, n. 6, p. 634–651, 2025.

[DOI 10.1093/clinchem/hvaf043](<https://doi.org/10.1093/clinchem/hvaf043>)  \|  [Acesso ao artigo](<https://pubmed.ncbi.nlm.nih.gov/40272429/>)
