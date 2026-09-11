# Base de dados e hipóteses do submodelo temporal dsRNase 2

Dados, variáveis, parâmetros, equações candidatas e hipóteses simplificadoras

Projeto BioGuard

Responsável pelo submodelo: Marcos

Data de referência: 11 de setembro de 2026

**Pergunta de modelagem**

**Como o silenciamento de dsRNase-2 modifica, ao longo do tempo, a exposição do dsRNA-alvo?**

*Fonte dos dados: BioGuard Banco de Evidências v2.xlsx. Base metodológica: Shiflet e Shiflet (2006), especialmente os módulos sobre processo de modelagem, erros, modelos compartimentais, cinética enzimática e trabalho por submodelos.*

## 1 Resposta central

O banco sustenta a construção imediata de um submodelo dinâmico mínimo, mas não sustenta ainda uma previsão calibrada do intervalo ótimo. A evidência específica em Dalbulus maidis fornece um regime experimental de referência - 200 ng/µL contra dsRNase-2, 48 h de pré-tratamento e 3 dias subsequentes de exposição oral - além de uma redução registrada de 23,6 vezes no transcrito de dsRNase-2. Entretanto, faltam a curva temporal do silenciamento, a atividade ou abundância proteica da nuclease, a recuperação pós-tratamento e a relação quantitativa entre a atividade residual da enzima e kdeg.

**Conclusão operacional.** Marcos pode definir símbolos, unidades, interfaces, equações concorrentes e cenários de sensibilidade. Ele ainda não pode afirmar que 48 h é o intervalo ótimo nem converter a degradação descrita como total em 12 h em uma constante única sem assumir um limite de detecção.

- O único intervalo empírico registrado é 48 h; ele é uma condição testada, não um ótimo.

- A queda de 23,6 vezes é de transcrito; não equivale automaticamente à mesma redução de atividade enzimática.

- A degradação completa em até 12 h é um dado censurado por intervalo e pelo limite de detecção do gel.

- Nenhum par parâmetro-valor está atualmente marcado como usar_em_modelo = sim.

- A conexão KD de dsRNase-2 -\> kdeg permanece uma hipótese estrutural a ser calibrada.

## 2 Fundamento metodológico no livro

Shiflet e Shiflet tratam a modelagem como um processo cíclico. Na formulação, o modelador reúne dados, documenta simplificações, define variáveis e unidades, estabelece relações entre submodelos e seleciona equações. A verificação avalia se o modelo foi implementado corretamente; a validação avalia se ele responde ao problema real e dentro do domínio de aplicação. O livro também afirma que etapas e submodelos podem ser desenvolvidos simultaneamente por diferentes membros da equipe (Shiflet e Shiflet, 2006, pp. 8-10).

**Tabela 1 - Aplicação do processo de modelagem ao trabalho de Marcos**

| **Etapa do livro**           | **Aplicação ao submodelo dsRNase-2**                                                                   |
|------------------------------|--------------------------------------------------------------------------------------------------------|
| Analisar o problema          | Fixar a saída: exposição temporal do dsRNA-BicC e efeito do intervalo de administração.                |
| Reunir dados                 | Extrair dose, rota, tempos, knockdown, degradação, controles, n, erro e sistema experimental.          |
| Simplificar e documentar     | Começar com atividade relativa, compartimento efetivo e perdas agregadas; registrar o que foi omitido. |
| Definir variáveis e unidades | Usar horas como unidade temporal e distinguir concentração, fração residual, taxa e AUC.               |
| Relacionar submodelos        | Conectar intervenção -\> silenciamento -\> atividade da nuclease -\> degradação -\> exposição do alvo. |
| Definir equações             | Comparar relações linear, potência e limiar entre atividade da nuclease e kdeg.                        |
| Verificar e validar          | Testar conservação, não negatividade, unidades, limites e concordância com dados não usados no ajuste. |

*Fonte: síntese de Shiflet e Shiflet (2006, pp. 8-10).*

O livro também distingue erros de dados de erros de modelagem. No BioGuard, um DOI incorreto, uma unidade de dose deslocada por fator 1.000 ou um valor qualitativo tratado como número seriam erros de dados; assumir proporcionalidade instantânea entre mRNA e atividade enzimática seria erro potencial de modelagem (Shiflet e Shiflet, 2006, pp. 17-18).

## 3 Auditoria do banco de evidências

**Tabela 2 - Estado quantitativo do banco**

| **Indicador**            | **Valor** | **Interpretação**                                         |
|--------------------------|-----------|-----------------------------------------------------------|
| Linhas no Banco v2       | 41        | Condições experimentais registradas.                      |
| Pares parâmetro-valor    | 72        | Registros em formato longo.                               |
| Com valor numérico       | 43        | Nem todos possuem unidade, incerteza ou verificação.      |
| Com unidade              | 40        | Persistem valores numéricos sem unidade definida.         |
| Com incerteza registrada | 2         | Insuficiente para ajuste ponderado.                       |
| Com n registrado         | 2         | Insuficiente para prior baseada em precisão experimental. |
| usar_em_modelo = sim     | 0         | Nenhum parâmetro está liberado para calibração final.     |
| Verificadas por humano   | 11        | A maioria ainda exige conferência na fonte primária.      |

*Fonte: aba Resumo da triagem do BioGuard Banco de Evidências v2.*

O banco já implementa uma regra adequada: cada linha do Banco v2 representa uma condição experimental e cada linha de Parâmetros (long) representa um parâmetro medido. Também exige valor numérico, unidade, grau de transferibilidade e verificação humana antes do uso quantitativo. As larguras sigma_log10 atribuídas por grau de transferibilidade são hipóteses de prior, não erros experimentais medidos.

**Tabela 3 - Inconsistências que afetam diretamente o submodelo**

| **Item**            | **Problema observado**                                                                                      | **Tratamento recomendado**                                                       |
|---------------------|-------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| P017                | DOI malformado em Parâmetros (long): 10.1016/j.pest2023.105618bp.                                           | Substituir pelo DOI do Banco v2: 10.1016/j.pestbp.2023.105618.                   |
| Linha 35 / P057     | Banco v2 contém DOI corrigido 10.3390/insects11060327; Parâmetros (long) mantém DOI antigo e o valor 4 min. | Sincronizar as abas e remover 4 min até digitalização da figura.                 |
| Linhas 7-9 e 33     | Dose aparece como 500 µM; a triagem registra que a fonte indica 0,5 µM.                                     | Não calcular cinética até confirmação humana e correção do campo.                |
| Linha 36 / P058     | Fração degradada 0,77 está sem unidade no formato longo e a linha permanece bloqueada.                      | Registrar como fração adimensional e manter apenas como cenário distante.        |
| P059-P060           | Redução 23,6x e melhora alta não foram convertidas em valor_num; n e incerteza ausentes.                    | Extrair figura/tabela, controle, n, erro e tempo de leitura da fonte primária.   |
| Linhas 22-23 vs. 42 | Registros qualitativos de BicC coexistem com uma linha posterior quantitativa do mesmo estudo.              | Usar a linha 42 como registro principal após conferência; consolidar duplicatas. |

*Fonte: comparação entre Banco v2, Parâmetros (long), Guia v2 e Etapa 2 - Triagem LLM (orig).*

## 4 Dados relevantes e correspondência com o modelo

A tabela distingue observação registrada, variável correspondente e uso autorizado. Direto significa que o banco atribui o resultado a uma condição experimental; derivado significa cálculo matemático a partir do texto do banco; assumido significa estrutura necessária para simulação.

**Tabela 4 - Matriz de evidências para dsRNase-2, degradação e dsRNA-BicC**

| **ID** | **Sistema**                       | **Dado registrado**                                                                     | **Variável ou parâmetro**              | **Classe**              | **Uso e limitação**                                                | **Local no banco**    |
|--------|-----------------------------------|-----------------------------------------------------------------------------------------|----------------------------------------|-------------------------|--------------------------------------------------------------------|-----------------------|
| E1     | D. maidis; saliva; in vitro       | Degradação total (~100%) em 12 h                                                        | frem,saliva(12 h); limite para ksaliva | Direto, mas qualitativo | Grau 1; não identifica k sem limite de detecção                    | Linha 11; P017        |
| E2     | D. maidis; dsRNase-2              | 200 ng/µL; injeção; 48 h antes de 3 dias de dieta                                       | DR; Delta t; TB                        | Direto                  | Grau 2; condição testada, não ótima                                | Linha 37; P059-P060   |
| E3     | D. maidis; dsRNase-2              | Redução de 23,6 vezes no transcrito                                                     | FR; Rm; KDR                            | Direto + derivado       | Conversão depende do significado de 23,6x; fonte primária pendente | Linha 37; P059        |
| E4     | D. maidis; observação do trato    | Saliva: completa até 12 h; intestino: 12-24 h                                           | ksaliva; kgut; tempos de trânsito      | Direto, intervalar      | Não separar taxas sem série temporal                               | Linha 37, observações |
| E5     | A. aegypti; extrato intestinal    | Normal: quase todo dsRNA em \<=30 min; após KD: sem degradação significativa até 60 min | Razão kKD/k0; forma de kdeg(R)         | Direto comparativo      | Grau 3; sustenta monotonicidade, não valor para D. maidis          | Linha 35              |
| E6     | N. fulva; fluido intestinal       | 23% remanescente após 2 h                                                               | frem(2 h); k derivável                 | Direto + derivado       | Grau 4 e linha bloqueada; apenas cenário matemático                | Linha 36; P058        |
| E7     | Quatro insetos; ensaio enzimático | Vmax/Km: 9,46/3,06; 3,58/0,27; 38,87/17,59; 13,4/2,28                                   | Vmax; Km; modelo saturável             | Direto no banco         | Grau 4; dose/unidade pendente; não equivale a k de 1ª ordem        | Linhas 7-9 e 33       |
| E8     | D. maidis; BicC; dieta            | 100-200 ng/µL; 3 dias; dsRNA renovado diariamente                                       | DB; TB; uB(t)                          | Direto                  | Grau 1; concentração externa, não dose interna                     | Linha 42              |
| E9     | D. maidis; BicC; dieta            | Redução 2,6x no dia 1 e 3,7x no dia 7; p\<=0,005                                        | KDBicC(t); elo exposição-efeito        | Direto + derivado       | Não pareado no banco com AUC interna                               | Linha 42              |
| E10    | D. maidis; BicC; fenótipo         | Sobrevivência sem diferença; ovário alterado 13,3% e 27,3%                              | Saída fenotípica                       | Direto                  | Informa validação fenotípica, não kdeg                             | Linha 42              |

*Fonte: BioGuard Banco de Evidências v2. Abreviações definidas na Seção 6.*

## 5 Derivações matemáticas permitidas e seus limites

### 5.1 Conversão de redução em vezes para fração residual

Se a expressão redução de 23,6 vezes significar que o controle possui 23,6 vezes mais transcrito que o tratamento, a abundância relativa de mRNA e a fração de knockdown são calculadas por:

$$
R_m=\frac{1}{F_R},\qquad KD_R=1-\frac{1}{F_R}
$$

$$
F_R=23.6\quad\Rightarrow\quad R_m\approx0.0424,\qquad KD_R\approx0.9576
$$

*Derivação condicional. Não converte mRNA em atividade enzimática.*

Sob essa interpretação, o mRNA residual seria 4,24% e o knockdown do transcrito 95,76%. Esses números são derivados, não medidos como percentuais, e permanecem bloqueados até a confirmação do sentido do fold-change, do controle, do tempo de leitura, do n e do erro.

### 5.2 Derivação de k em um modelo de primeira ordem

O modelo de um compartimento do livro assume mistura homogênea e eliminação proporcional à quantidade presente, produzindo decaimento exponencial e a relação entre k e meia-vida (Shiflet e Shiflet, 2006, pp. 99-100). Aplicado apenas como hipótese matemática:

$$
C(t)=C_0e^{-kt},\qquad k=-\frac{\ln[C(t)/C_0]}{t},\qquad t_{1/2}=\frac{\ln 2}{k}
$$

**Tabela 5 - Exemplos derivados sem autorização para calibração final**

| **Origem**           | **Entrada**      | **Derivação**   | **Resultado**                  | **Status**                                |
|----------------------|------------------|-----------------|--------------------------------|-------------------------------------------|
| Linha 36; N. fulva   | C(2 h)/C0 = 0,23 | k = -ln(0,23)/2 | k = 0,735 h^-1; t1/2 = 0,943 h | Cenário distante; grau 4; linha bloqueada |
| Linha 42; BicC dia 1 | Redução 2,6x     | KD = 1 - 1/2,6  | KD = 61,5%                     | Derivado condicional                      |
| Linha 42; BicC dia 7 | Redução 3,7x     | KD = 1 - 1/3,7  | KD = 73,0%                     | Derivado condicional                      |

*Resultados arredondados. Eles dependem das hipóteses indicadas e não substituem a fonte primária.*

### 5.3 Por que degradação total em 12 h não identifica k

Se o gel apenas informa que a banda ficou abaixo de uma fração residual desconhecida epsilon, o resultado fornece um limite inferior para k, não uma estimativa pontual:

$$
C(12\ \mathrm{h})<\varepsilon C_0\quad\Rightarrow\quad k>-\frac{\ln\varepsilon}{12\ \mathrm{h}}
$$

**Tabela 6 - Sensibilidade ao limite de detecção hipotético**

| **Fração residual epsilon** | **Limite inferior de k** | **Limite superior de t1/2** |
|-----------------------------|--------------------------|-----------------------------|
| 0,10                        | 0,192 h^-1               | 3,61 h                      |
| 0,05                        | 0,250 h^-1               | 2,78 h                      |
| 0,01                        | 0,384 h^-1               | 1,81 h                      |

*Cenários ilustrativos; epsilon não foi informado no banco. Estes valores não são estimativas empíricas de D. maidis.*

### 5.4 Por que Vmax e Km não são kdeg

O livro define a velocidade Michaelis-Menten como função saturável da concentração de substrato. Vmax tem unidade de concentração por tempo e Km tem unidade de concentração; kdeg de primeira ordem tem unidade de tempo^-1. A conversão só seria possível para uma concentração específica e sob condições experimentais compatíveis, por exemplo por uma taxa efetiva dependente de substrato. Como o banco ainda possui conflito de 500 versus 0,5 µM e espécies distantes, Vmax e Km devem testar uma estrutura alternativa, não calibrar diretamente o modelo exponencial (Shiflet e Shiflet, 2006, pp. 214-216).

## 6 Variáveis do submodelo

**Tabela 7 - Variáveis independentes, controles e entradas**

| **Símbolo** | **Definição**                                                     | **Unidade**              | **Valor ou domínio atual**                     | **Origem**          |
|-------------|-------------------------------------------------------------------|--------------------------|------------------------------------------------|---------------------|
| t           | Tempo desde a intervenção contra dsRNase-2                        | h                        | t \>= 0                                        | Definição do modelo |
| Delta t     | Intervalo entre início da intervenção anti-dsRNase-2 e dsRNA-BicC | h                        | Variável de decisão; 48 h é condição observada | Linha 37            |
| DR          | Concentração administrada de dsRNA contra dsRNase-2               | ng/µL                    | 200; massa total por inseto desconhecida       | Linha 37            |
| DB          | Concentração externa de dsRNA-BicC                                | ng/µL                    | 100-200; dose interna desconhecida             | Linha 42            |
| uR(t)       | Função de intervenção ou exposição anti-dsRNase-2                 | adimensional ou dose/h   | A definir conforme protocolo                   | Assumida            |
| uB(t)       | Entrada efetiva de dsRNA-BicC no compartimento                    | ng µL^-1 h^-1 ou massa/h | Desconhecida; depende de ingestão              | Lacuna Eing         |

*Delta t = 48 h é um regime experimental registrado, não uma constante biológica.*

**Tabela 8 - Variáveis de estado e saídas**

| **Símbolo** | **Definição**                                       | **Unidade**     | **Faixa**      | **Função no modelo**                |
|-------------|-----------------------------------------------------|-----------------|----------------|-------------------------------------|
| R(t)        | Atividade funcional relativa de dsRNase-2           | adimensional    | 0 a 1          | Estado agregado; 1 = basal          |
| MR(t)       | mRNA relativo de dsRNase-2                          | adimensional    | 0 a 1 ou razão | Refinamento transcrito-proteína     |
| PR(t)       | Proteína/atividade relativa da nuclease             | adimensional    | 0 a 1          | Refinamento mecanístico             |
| CB(t)       | Concentração ou quantidade disponível de dsRNA-BicC | ng/µL ou ng     | \>= 0          | Estado do payload alvo              |
| kdeg(t)     | Taxa efetiva de degradação do dsRNA-BicC            | h^-1            | \>= 0          | Saída intermediária dependente de R |
| AB(t)       | Exposição acumulada ao dsRNA-BicC                   | ng h/µL ou ng h | \>= 0          | AUC do payload                      |
| KDR(t)      | Fração de knockdown de dsRNase-2                    | adimensional    | 0 a 1          | Saída molecular                     |
| KDB(t)      | Fração de knockdown de BicC                         | adimensional    | 0 a 1          | Interface com submodelo de Gabriel  |

*As unidades de CB e AB devem permanecer coerentes com a escolha entre concentração e massa interna.*

## 7 Parâmetros e estado de identificabilidade

**Tabela 9 - Parâmetros com alguma informação no banco**

| **Parâmetro** | **Significado**                        | **Informação atual**                     | **Uso permitido**                       |
|---------------|----------------------------------------|------------------------------------------|-----------------------------------------|
| FR            | Fator de redução do mRNA de dsRNase-2  | 23,6x; fonte primária pendente           | Conversão condicional para MR e KDR     |
| Delta temp    | Intervalo do regime testado            | 48 h                                     | Âncora de cenário; não ótimo            |
| TB            | Duração de exposição ao dsRNA alvo     | 72 h                                     | Condição de simulação                   |
| frem,saliva   | Fração remanescente de dsRNA na saliva | Aproximadamente zero aos 12 h            | Restrição intervalar para k             |
| Vmax, Km      | Parâmetros de cinética saturável       | Quatro espécies; unidades/dose pendentes | Comparar estrutura Michaelis-Menten     |
| KDB(t)        | Resposta molecular de BicC             | 61,5% dia 1; 73,0% dia 7, derivados      | Validação/interface após conferir fonte |

*Nenhum desses registros está liberado no campo usar_em_modelo.*

**Tabela 10 - Parâmetros essenciais ainda ausentes**

| **Símbolo** | **Parâmetro**                             | **Unidade**  | **Por que é necessário**                         | **Estratégia provisória**               |
|-------------|-------------------------------------------|--------------|--------------------------------------------------|-----------------------------------------|
| tauon       | Atraso até início do knockdown            | h            | Define quando R começa a cair                    | Faixa ampla; inferir de série temporal  |
| ksil        | Intensidade efetiva do silenciamento      | h^-1         | Controla velocidade e profundidade da queda de R | Calibrar com MR(t)                      |
| krec        | Recuperação funcional da dsRNase-2        | h^-1         | Define duração da proteção                       | Não informado; análise de sensibilidade |
| kp          | Degradação/turnover da proteína dsRNase-2 | h^-1         | Separa mRNA de atividade enzimática              | Lacuna crítica; experimento             |
| kres        | Perdas não atribuídas à dsRNase-2         | h^-1         | Evita atribuir toda degradação a uma enzima      | Inferir de KD máximo ou controles       |
| kR          | Contribuição de dsRNase-2 à degradação    | h^-1         | Liga R a kdeg                                    | Calibrar com ensaio pareado +/- KD      |
| gamma       | Não linearidade da relação R-kdeg         | adimensional | Testa proporcionalidade                          | Varrer cenários; comparar modelos       |
| Rc          | Limiar de atividade no modelo threshold   | adimensional | Estrutura concorrente                            | Ajustar apenas se dados sustentarem     |
| Eing        | Eficiência de ingestão/internalização     | adimensional | Converte dose externa em uB                      | Wet lab; incerteza estrutural           |
| kloss       | Perdas adicionais do dsRNA-alvo           | h^-1         | Agrega excreção, transporte e outras nucleases   | Faixa residual; não confundir com kR    |

*O banco identifica explicitamente kdeg, Eing e a meia-vida da proteína dsRNase como lacunas.*

## 8 Estrutura matemática mínima

![Figura 1 — Diagrama causal mínimo](graficos/marcos/figura_01_diagrama_causal.png)

*Figura 1 - Diagrama causal mínimo. As relações funcionais permanecem hipóteses testáveis.*

Uma primeira versão pode colapsar transcrito, tradução, secreção e atividade em R(t). A entrada anti-dsRNase-2 reduz R após um atraso; R modula a taxa de degradação do dsRNA-BicC; CB acumula exposição em AB.

$$
\frac{dR}{dt}=k_{\mathrm{rec}}(1-R)-k_{\mathrm{sil}}\,u_R(t-\tau_{\mathrm{on}})R
$$

$$
\frac{dC_B}{dt}=u_B(t-\Delta t)-[k_{\mathrm{res}}+k_RR(t)^{\gamma}]C_B
$$

$$
\frac{dA_B}{dt}=C_B(t),\qquad A_B(0)=0
$$

*Modelo mínimo candidato. Todos os parâmetros devem ser positivos e as condições iniciais devem assegurar R entre 0 e 1 e CB \>= 0.*

**Interpretação.** O primeiro termo recupera R em direção ao basal; o segundo representa silenciamento dependente da intervenção. A perda de CB é de primeira ordem para um kdeg variável no tempo. AB é a área sob a curva de dsRNA disponível e constitui a saída a ser entregue ao submodelo exposição -\> knockdown de BicC.

O objetivo computacional pode ser formulado como maximização da exposição acumulada dentro de um horizonte T, sem confundir o máximo numérico do modelo provisório com um intervalo biologicamente validado:

$$
\Delta t^{*}=\underset{\Delta t}{\mathrm{arg\,max}}\ A_B(T;\Delta t)
$$

$$
A_B(T)=\int_0^T C_B(t)\,dt
$$

## 9 Modelos concorrentes para a ponte R para kdeg

O banco sustenta monotonicidade qualitativa - menor atividade de dsRNase deve reduzir a degradação -, mas não identifica a forma funcional. Três estruturas devem ser preservadas até que dados discriminem entre elas:

$$
\mathrm{A:}\quad k_{\deg}(R)=k_{\mathrm{res}}+k_RR
$$

$$
\mathrm{B:}\quad k_{\deg}(R)=k_{\mathrm{res}}+k_RR^{\gamma}
$$

$$
\mathrm{C:}\quad k_{\deg}(R)=k_{\mathrm{low}}\ (R<R_c),\quad k_{\mathrm{high}}\ (R\geq R_c)
$$

Modelo A é a aproximação linear mínima. Modelo B admite resposta côncava ou convexa por meio de gamma. Modelo C representa um efeito de limiar. A conclusão sobre Delta t deve ser comparada entre as três estruturas; mudança qualitativa do ótimo caracteriza incerteza estrutural, não apenas incerteza paramétrica.

## 10 Hipóteses simplificadoras

Conforme o livro, cada simplificação deve ser documentada com sua finalidade e seu possível erro. Risco baixo significa aceitável para a versão mínima; risco moderado exige sensibilidade; risco alto exige validação antes de uma recomendação operacional.

**Tabela 11 - Registro de hipóteses do submodelo**

| **ID** | **Hipótese**                                             | **O que permite**                           | **Consequência potencial**                                 | **Risco**     | **Teste ou refinamento**                  |
|--------|----------------------------------------------------------|---------------------------------------------|------------------------------------------------------------|---------------|-------------------------------------------|
| M1     | Modelo contínuo e determinístico                         | Representar trajetórias médias              | Não descreve variação individual                           | Baixo         | Adicionar amostragem de parâmetros depois |
| M2     | Um compartimento efetivo homogêneo                       | Evitar modelagem espacial                   | Colapsa saliva e intestino, que têm tempos distintos       | Moderado-alto | Comparar com dois compartimentos          |
| M3     | R(t) resume mRNA, proteína, secreção e atividade         | Compatibilizar o modelo com os dados atuais | Pode antecipar o efeito do KD de mRNA                      | Alto          | Refinar para MR(t) e PR(t)                |
| M4     | Início do knockdown por atraso único tauon               | Representar latência sem maquinaria RNAi    | Ignora distribuição de atrasos                             | Moderado      | Testar atraso fixo versus distribuído     |
| M5     | Recuperação de R é de primeira ordem                     | Dar duração ao efeito                       | Forma e meia-vida são desconhecidas                        | Alto          | Sensibilidade em krec; medir recuperação  |
| M6     | kdeg aumenta monotonicamente com R                       | Formalizar a direção causal                 | Monotonicidade é plausível, mas magnitude é desconhecida   | Moderado      | Comparar linear, potência e limiar        |
| M7     | Outras perdas são um termo residual constante            | Agregar outras nucleases e perdas           | Perdas podem mudar com tempo e tratamento                  | Moderado      | Controles com KD máximo e tecidos         |
| M8     | Perda do dsRNA-BicC é de primeira ordem                  | Usar modelo identificável com poucos dados  | Falha se houver saturação enzimática                       | Moderado      | Comparar com Michaelis-Menten             |
| M9     | Sem competição entre os dois dsRNAs pela maquinaria RNAi | Simplificar coadministração                 | Pode superestimar duplo silenciamento                      | Alto          | Variar razão de doses e medir siRNA/RISC  |
| M10    | dsRNase-2 afeta BicC principalmente via degradação       | Criar a ponte entre submodelos              | Pode haver efeitos sobre ingestão, transporte ou imunidade | Alto          | Medir dsRNA interno e KD simultaneamente  |
| M11    | uB independe do tratamento anti-dsRNase-2                | Separar ingestão de degradação              | A intervenção pode alterar alimentação                     | Moderado      | Controle de ingestão/EPG                  |
| M12    | Dados de outras espécies definem apenas cenários         | Usar informação sem falsa especificidade    | Ainda pode haver viés de mecanismo                         | Baixo         | Priors largas e análise de exclusão       |

*Classificação de risco proposta para planejamento do modelo; não é uma escala validada externamente.*

## 11 Versões recomendadas do modelo

**Tabela 12 - Escalonamento de complexidade**

| **Versão** | **Estrutura**                    | **O que responde**                                      | **Condição para avançar**             |
|------------|----------------------------------|---------------------------------------------------------|---------------------------------------|
| V0         | Diagrama causal e limites        | Quais dados conectam os módulos e onde estão as lacunas | Pode ser concluída agora              |
| V1         | R agregado + CB + AUC            | Se a ordem de administração é robusta a faixas amplas   | Definir priors provisórias e cenários |
| V2         | MR -\> PR/atividade -\> kdeg     | Como persistência proteica altera o intervalo           | Obter ou testar meia-vida da proteína |
| V3         | Saliva e intestino separados     | Como compartimentos e trânsito alteram exposição        | Séries temporais por tecido           |
| V4         | Acoplado a dose-resposta de BicC | Intervalo que maximiza KD ou efeito reprodutivo         | Função AUC -\> KDBicC de Gabriel      |

*A progressão segue o princípio de começar tão simples quanto razoavelmente possível e refinar quando necessário.*

## 12 Lacunas prioritárias e plano de extração

**Tabela 13 - Dados que desbloqueiam o modelo**

| **Prioridade** | **Dado necessário**                   | **Campo a extrair**                                                             | **Parâmetro desbloqueado**     |
|----------------|---------------------------------------|---------------------------------------------------------------------------------|--------------------------------|
| 1              | Artigo de D. maidis sobre dsRNase-2   | Dose total/inseto, tempo da qPCR, fold exato, n, SD/SE/IC, gene-alvo secundário | DR, tauon, KDR(t)              |
| 2              | Gel temporal em saliva e intestino    | Intensidade normalizada em cada tempo e limite de detecção                      | ksaliva, kgut ou Vmax/Km       |
| 3              | Ensaio pareado antes/depois do KD     | C(t) nas duas condições usando o mesmo dsRNA                                    | kR, kres, gamma                |
| 4              | Persistência proteica/atividade       | Proteína ou atividade após a queda do mRNA e durante recuperação                | kp, krec                       |
| 5              | Coadministração versus pré-tratamento | Mesmas doses, vários Delta t, AUC interna e KD secundário                       | Delta t e validação estrutural |
| 6              | Ingestão e dose interna               | Volume ingerido ou marcador interno ao longo do tempo                           | Eing, uB(t)                    |
| 7              | Especificidade do substrato           | Comparar dsRNA do ensaio com dsRNA-BicC em comprimento e sequência              | Transferência para CB          |

*Prioridade 1-5: submodelo de Marcos. Prioridade 6 requer interface com entrega; prioridade 7 evita assumir substratos equivalentes.*

## 13 Quadro de prontidão

**Tabela 14 - Conhecido, estimável, transferível e desconhecido**

| **Classe**         | **Conteúdo**                                                                                                | **Decisão atual**                                           |
|--------------------|-------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| Conhecido no banco | Regime 200 ng/µL + 48 h + 3 dias; redução 23,6x; degradação até 12 h; BicC 100-200 ng/µL por 3 dias         | Usar como condições e benchmarks, após conferência primária |
| Estimável          | Frações residuais e KD a partir de fold; k a partir de uma fração remanescente e tempo                      | Marcar como derivado e propagar a hipótese                  |
| Transferível       | Contraste +/- KD em A. aegypti; cinética em outras ordens                                                   | Usar apenas para forma estrutural e cenários                |
| Desconhecido       | kdeg em D. maidis, proteína/atividade, recuperação, ingestão, competição, gene secundário do ensaio de 2023 | Não substituir por ponto arbitrário                         |

*Síntese do estado de evidência em 11 de setembro de 2026.*

**Critério de saída.** O submodelo está pronto para integração exploratória quando todas as entradas provisórias estiverem rotuladas por origem e classe, e quando a ordem de administração for testada nas três estruturas de kdeg(R). Ele estará pronto para recomendação operacional somente após ao menos uma série temporal pareada em D. maidis e validação fora do conjunto de calibração.

## 14 Referências e fontes

BioGuard. BioGuard Banco de Evidências v2. Planilha de trabalho, versão fornecida em 11 set. 2026.

SHIFLET, Angela B.; SHIFLET, George W. Introduction to Computational Science: Modeling and Simulation for the Sciences. Princeton: Princeton University Press, 2006.

Knockdown of double-stranded RNases enhances oral RNA interference in the corn leafhopper. Pesticide Biochemistry and Physiology, 2023. DOI: [10.1016/j.pestbp.2023.105618](https://doi.org/10.1016/j.pestbp.2023.105618)

Development of efficient RNAi methods in the corn leafhopper Dalbulus maidis. Pest Management Science, 2022. DOI: [10.1002/ps.6937](https://doi.org/10.1002/ps.6937)

Biochemical Comparison of dsRNA Degrading Nucleases in Four Different Insects. Frontiers in Physiology, 2018. DOI: [10.3389/fphys.2018.00624](https://doi.org/10.3389/fphys.2018.00624)

RNA Interference Is Enhanced by Knockdown of Double-Stranded RNases in the Yellow Fever Mosquito Aedes aegypti. Insects, 2020. DOI: [10.3390/insects11060327](https://doi.org/10.3390/insects11060327)

Cloning and functional characterization of a double-stranded RNA-degrading nuclease in the tawny crazy ant. Frontiers in Physiology, 2022. DOI: [10.3389/fphys.2022.833652](https://doi.org/10.3389/fphys.2022.833652)

## Apêndice A Regras de interpretação para o arquivo de parâmetros

1.  Nenhum valor qualitativo, como total, alta ou drástica, deve ocupar valor_num.

2.  Concentração administrada não deve ser chamada de dose por inseto sem o volume administrado ou ingerido.

3.  Fold reduction deve armazenar o fator, o sentido da razão e o controle; a fração de KD fica em campo derivado separado.

4.  Valores censurados por limite de detecção devem armazenar o limite ou intervalo, não um zero exato.

5.  Vmax e Km permanecem ligados ao modelo Michaelis-Menten e às condições do ensaio.

6.  sigma_log10 derivado da transferibilidade deve ser identificado como prior de modelagem, não como SD experimental.

7.  Cada parâmetro deve conservar DOI, espécie, tecido, rota, tempo, método, controle, n e medida de incerteza.

8.  Parâmetros fictícios podem testar o código, mas não devem aparecer em resultados biológicos sem o rótulo cenário sintético.
