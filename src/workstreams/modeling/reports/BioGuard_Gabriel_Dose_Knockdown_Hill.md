# BioGuard | Módulo M2 — Relação dose → knockdown (curva de Hill)

Reconstrução do dataset, padronização, análise de identificabilidade e plano de calibração

Responsável do módulo: Gabriel — Modelagem (BioGuard)

11 de setembro de 2026

## Resumo executivo

Conclusão principal. O banco de evidências não sustenta, hoje, uma curva de Hill calibrada para a relação dose → knockdown (KD) em Dalbulus maidis por via oral. Isso não é uma opinião: a própria aba Lacunas do Banco de Evidências v2 já classifica EC50_KD, E_max e n_Hill como AUSENTES, com o impacto explícito “bloqueia o modelo de Hill (M2)”. A reconstrução do dataset feita aqui, e a conferência das fontes primárias de acesso aberto, confirmam a causa: para a população-alvo (D. maidis, dieta artificial, KD de transcrito) existe um único nível efetivo de dose observado (100–200 ng/µL, que produzem o mesmo KD), nenhum ponto na região de baixo efeito e nenhum ponto de platô. Com isso, $E_{max}$, $EC_{50}$ e $n$ não são individualmente identificáveis.

O que este módulo entrega. Em coerência com o processo de modelagem de Shiflet & Shiflet e com o padrão adotado pelo Módulo M1 (degradação/AUC), o produto desta etapa não é uma curva com números inventados. É: (i) um dataset dose–resposta reconstruído e auditável; (ii) a padronização de dose, de endpoint e de tempo; (iii) a demonstração quantitativa da não-identificabilidade; (iv) um conjunto de hipóteses aceitas/rejeitadas; (v) o protocolo de ajuste progressivo pronto para rodar quando os dados existirem; e (vi) um arquivo de parâmetros (parameters_hill.yaml) que declara honestamente o estado “AUSENTE/a estimar”.

Achado adicional relevante. Buscando fontes primárias abertas (como pede a ação da aba Lacunas: “reunir todos os pontos dose-resposta de RNAi oral em Hemiptera”), localizei fora do banco a única curva dose-resposta oral multi-dose em um hemíptero — Diaphorina citri (Qureshi et al., 2024). Ela revela um padrão que muda o modelo: o RNAi oral em Hemiptera tende a um platô baixo ($E_{max} \approx 0,3$–$0,5$, não $\approx 1,0$) e pode reverter em dose alta. Recomendo incorporá-la ao banco (via verificação humana) como prior fraco, com transferibilidade indireta.

## 1. Escopo do módulo e materiais analisados

Pela divisão de responsabilidades (Divisao_Modelagem_BioGuard.pdf), o Módulo M2 (Gabriel) é: “Organizar dados de dose–resposta da literatura e ajustar a relação entre dose/exposição de dsRNA e intensidade do knockdown”, entregando “EC50, Emax, coeficiente de Hill n, intervalos de confiança e curva dose–resposta”.

A curva de Hill é a forma empírica adotada:

$$
KD(D)=E_{\max}\frac{D^n}{EC_{50}^{n}+D^n}
$$

em que $D$ é a dose de dsRNA, $E_{max}$ é o efeito máximo (KD de platô), $EC_{50}$ é a dose que produz metade de $E_{max}$ e $n$ é o coeficiente de Hill (inclinação da transição).

**Materiais.**

- [BANCO] BioGuard Banco de Evidencias v2.xlsx — 41 linhas no “Banco v2”, 72 pares parâmetro-valor em “Parametros (long)”, abas “Lacunas”, “Resumo da triagem”, “Listas”, “Guia v2”. Tratado como input dado (não como fonte primária definitiva), exatamente como o Módulo M1 tratou.
- [PRIM] fontes primárias de acesso aberto conferidas nesta etapa (bioRxiv, PLoS ONE, MDPI) — ver §Referências.
- [EXT] fontes de Hemiptera externas ao banco, localizadas na busca, recomendadas para inclusão.
- Shiflet & Shiflet, Introduction to Computational Science — base metodológica (modelos empíricos; simplificações; verificação × validação).

Regra de leitura (do Guia v2 do banco). “Nenhum parâmetro entra em modelo quantitativo sem: valor_num, unidade, grau e verificação humana. Sem isso, usar apenas qualitativamente.” No “Resumo da triagem”, usar_em_modelo = sim está marcado em 0 linhas, e apenas 2 dos 72 pares têm n e incerteza registrados. Esse é o ponto de partida real.

## 2. Reconstrução do dataset (não partir da curva publicada)

Seguindo a instrução, para cada registro extraí — quando disponível — os campos: nível de dose, unidade, espécie, gene-alvo, comprimento do dsRNA, rota de entrega, duração da exposição, momento em que o KD foi medido, endpoint, tamanho amostral (biológico) e medida de dispersão. Réplicas biológicas e técnicas foram mantidas separadas.

Resultado: 29 observações dose × endpoint × tempo × espécie × rota (arquivo dataset_dose_knockdown_reconstruido.csv/.xlsx). Distribuição por espécie: Dalbulus maidis (8), Diaphorina citri (15, externa), Nilaparvata lugens (3), Plautia stali (3).

Dois cuidados dignos de registro, ambos exigidos pela instrução:

- Réplica biológica ≠ técnica. Em Jones-Bernal et al. (2021, D. maidis, V-ATPase), o “n=3” corresponde a 3 pools de 3 insetos cada, medidos por RT-qPCR. Três qPCRs técnicos do mesmo pool não são três observações biológicas independentes. Isso reduz o suporte estatístico real desses pontos.

- Comprimento do dsRNA é majoritariamente ausente no banco. Recuperei da fonte primária: BicC = 372 bp (Dalaisón-Fuentes 2022); D. citri = 147–194 bp (Qureshi 2024). Como o comprimento do dsRNA afeta a eficiência de RNAi, sua ausência é uma limitação estrutural a declarar.

## 3. Padronização da dose: grandezas físicas incomensuráveis

Antes de qualquer eixo $D$ comum, é obrigatório distinguir o que “dose” significa em cada registro. No dataset, o campo dose_tipo separa:

| Tipo de dose | Unidade | Significado físico / por que não somar ingenuamente |
| --- | --- | --- |
| conc_dieta | ng/µL | Concentração de dsRNA ofertada na solução de dieta. Não é a massa ingerida nem a concentração interna. |
| conc_injetada | ng/µL | Concentração injetada (bolus) — contorna intestino e degradação; rota fisiologicamente distinta da oral. |
| planta_transgenica | — | Dose ingerida não quantificada (expressão da planta). Impossível posicionar no eixo $D$. |

Além dessas, o banco contém ainda µM (atividade de nuclease in vitro, $V_{max}/K_{m}$ — pertence ao M1, não é KD) e µg/planta (mortalidade foliar em Diaphorina — endpoint diferente). Regra adotada: 500 ng/µL na dieta e 500 ng/µL injetados não entram no mesmo eixo $D$; a rota oral é a única mantida no ajuste. A dose ofertada na dieta não é a concentração interna (a mesma ressalva feita pelo M1 sobre “100–200 ng/µL ofertados ≠ $C_{0}$ interno”).

## 4. Padronização do endpoint (KD)

Os registros misturam endpoints não equivalentes: expressão relativa, fold-change, percentual de redução, e descrições qualitativas (“Não significativo”, “Alta redução”, “Queda drástica”). Defini um endpoint único:

$$
KD=1-E_{\mathrm{rel}},\qquad E_{\mathrm{rel}}=\text{expressão relativa (controle = 1).}
$$

Conversões aplicadas: de fold-change $FC=\text{controle}/\text{tratamento}$, $KD= 1 -1/FC$; de percentual de redução $P$, $KD= P/100$. Exemplos (D. maidis, BicC, oral): $FC= 2,6$ (dia 1) $\Rightarrow KD= 0,615$; $FC= 3,7$ (dia 7) $\Rightarrow KD= 0,730$. Os registros qualitativos não foram convertidos em número (ficam marcados como não elegíveis). Não se misturam $2^{-\Delta \Delta Ct}$, fold-change, % de redução e quantidade absoluta de transcrito como se fossem o mesmo eixo.

## 5. Separação do efeito de dose e do efeito de tempo

Este ponto é crítico e, nos dados de D. maidis, decisivo. O mesmo par (dose, gene) muda de KD com o tempo:

![Figura 1 — Gabriel](graficos/gabriel/figura_01_dados_dose_knockdown.png)

Figure 1: Painel A: todas as observações com dose e KD numéricos, por tipo de dose/espécie (tipos de dose não comensuráveis entre rotas). Painel B: a população-alvo isolada (D. maidis, oral) — um único nível efetivo de dose, sem região de baixo efeito e sem platô observados.

- BicC oral, 100–200 ng/µL: $KD= 0,615$ no dia 1 → $0,730$ no dia 7 (mesma dose; o que muda é o tempo).
- V-ATPase oral, 500 ng/µL: sem KD significativo no dia 2, KD significativo no dia 4 (latência t_delay).

Combinar tudo numa única Hill atribuiria à dose o que é efeito de tempo. Regra adotada: fixar um endpoint temporal biologicamente justificado (aqui, dia 7 para BicC) e só comparar doses medidas no mesmo tempo. O problema é que, feito isso, sobra praticamente um ponto por dose.

## 6. Inspeção visual antes do ajuste

A Figura 1 mostra os pontos brutos de $KD$ contra dose, eixo de dose em escala logarítmica, como manda a seção de modelos empíricos de Shiflet & Shiflet. A pergunta é se aparecem as três regiões: baixo efeito, transição e platô.

Leitura. Para D. maidis oral, as três regiões não aparecem: há apenas o degrau 100–200 ng/µL, ambos com o mesmo KD. Não há dose baixa oral (que fixaria o piso $\approx 0$) nem dose alta oral (que fixaria o platô $E_{max}$). Os pontos de injeção (triângulos) e de planta transgênica pertencem a outras grandezas/rotas e não podem preencher essas lacunas.

## 7. Evidência externa de Hemiptera (fora do banco)

Como a lacuna EC50 recomenda reunir pontos dose-resposta de RNAi oral em Hemiptera, busquei fontes primárias abertas. A única curva oral multi-dose em um hemíptero é Diaphorina citri (Qureshi et al., 2024; não está no banco): 5 doses (10, 50, 100, 200, 500 ng/µL), 3 genes, $n= 3$ réplicas biológicas. Plautia stali (2021) fornece 3 doses orais (100, 1000, 5000 ng/µL).

**Implicação para o modelo (importante).**

Diferente da suposição usual da Hill (platô próximo de 1), o RNAi oral em Hemiptera satura num platô baixo ($E_{max} \approx 0,3$– $0,5$) e pode ser não-monotônico em dose alta (queda a 500 ng/µL em ninfas de D. citri). Consequência: $E_{max}$ não deve ser fixado $\approx 1,0$, e a própria adequação de uma Hill monotônica é uma hipótese a testar, não um dado.

![Figura 2 — Gabriel](graficos/gabriel/figura_02_evidencia_hemiptera.png)

Figure 2: Única evidência de dose-resposta oral em Hemiptera (externa ao banco; transferibilidade indireta). D. citri mostra limiar em ~100 ng/µL, platô baixo (~0,2–0,4) e, em ninfas, reversão a 500 ng/µL; P. stali só responde (~0,5) a 5000 ng/µL.

![Figura 3 — Gabriel](graficos/gabriel/figura_03_curvas_hill.png)

Figure 3: Não-identificabilidade: curvas de Hill muito diferentes ajustam-se igualmente aos pontos orais de D. maidis. Dentro de 100–200 ng/µL os dados não as distinguem; a extrapolação para 1 ou 5000 ng/µL vai de $KD\approx 0$ a $\approx 0,5$ e de $\approx 0,73$ a $\approx 1,0$, respectivamente.

## 8. Suporte paramétrico e não-identificabilidade

8.1 População-alvo (D. maidis oral). Com um único nível efetivo de dose, infinitas curvas de Hill passam pelos pontos. A Figura 3 mostra cinco curvas com $(E_{max}, EC_{50}, n)$ radicalmente diferentes, todas compatíveis com os pontos orais — e divergindo por completo fora do intervalo observado.

8.2 Melhor caso disponível (D. citri, 5 doses). Mesmo na única curva multi-dose, ajustar a Hill completa produz um ótimo ajuste visual com parâmetros sem sentido — exatamente o alerta da instrução (“uma curva visualmente excelente pode coexistir com $EC_{50}$ quase indeterminado”):

| Modelo (gene CHC, adultos) | AIC | $EC_{50}$ (ng/µL) | $n$ |
| --- | --- | --- | --- |
| $n=1$ fixo, $E_{\max}$ fixo (1 par.) | −20,4 | 61 ± 46 | 1 (fixo) |
| $n=1$, $E_{\max}$ livre (2 par.) | −19,6 | 124 ± 150 | 1 (fixo) |
| Hill completa (3 par.) | −50,3 | 85 ± 645 | 20 ± 942 |

Na Hill completa, o erro-padrão relativo é 759% para $EC_{50}$ e ~4700% para $n$, com correlação $EC_{50} \sim n= +1,00$ — parâmetros completamente confundidos. O AIC “prefere” a Hill completa (ajuste quase perfeito de um degrau), o que ilustra que qualidade de ajuste/AIC não protege contra não-identificabilidade. Um bootstrap usando os 3 genes como réplicas de forma dá $EC_{50}$ mediana $\approx 92$ ng/µL, IC95% $[66, 98]$ — estreito apenas porque a grade de doses força qualquer transição para a janela 50–100 ng/µL; é precisão da grade, não dos dados. O $n$ permanece indeterminado.

![Figura 4 — Gabriel](graficos/gabriel/figura_04_ajuste_progressivo.png)

Figure 4: Ajuste progressivo (do simples ao complexo) na curva de D. citri. A Hill completa (tracejada) reproduz o degrau, mas $EC_{50}$ e $n$ ficam mal determinados porque a transição inteira é capturada por um único salto de dose (50 → 100 ng/µL).

## 9. Ajuste progressivo (recomendação de Shiflet & Shiflet)

O protocolo adotado — e implementado no código — vai do modelo mais simples ao mais complexo, buscando o mais simples capaz de representar os dados, não o de mais parâmetros:

1. $n= 1$ e $E_{max}$ fixo (só $EC_{50}$);
2. $n= 1$, liberar $E_{max}$;
3. liberar $n$ (Hill completa);

comparando por AIC e examinando IC, correlações e estabilidade à retirada de pontos. Conclusão operacional atual: para D. maidis oral, mesmo o passo 1 é subdeterminado; para D. citri, o passo 3 sobre-ajusta sem identificar $n$. Enquanto não houver pontos na transição, $n$ deve ser fixado (sugestão: $n= 1$) como simplificação inicial.

## 10. Hipóteses aceitas e rejeitadas

| ID | Hipótese | Status |
| --- | --- | --- |
| G1 | O endpoint do eixo KD é $KD= 1 -E_{rel}$, com conversões explícitas de fold-change e % de redução. | Aceita (definição operacional) |
| G2 | O eixo de dose $D$ é concentração de dsRNA na dieta (ng/µL), rota ORAL somente. | Aceita |
| G3 | Doses de rotas diferentes (injeção, planta transgênica) não entram no mesmo eixo $D$. | Aceita |
| G4 | Comparar apenas doses medidas no mesmo tempo; endpoint temporal = dia 7 (BicC). | Aceita provisoriamente |
| G5 | A forma empírica de trabalho é a Hill; sua adequação (monotonicidade/saturação) é testável, não pressuposta. | Aceita como ponto de partida |
| G6 | $E_{max}$ do RNAi oral em Hemiptera é baixo ($\approx 0,3$– $0,5$), não $\approx 1,0$. | Provisória (evidência externa indireta) |
| G7 | Sem pontos na transição, fixar $n= 1$; liberar $n$ só quando houver dados que o sustentem. | Aceita (simplificação de Shiflet) |
| G8 | Réplicas biológicas e técnicas mantidas separadas; pools contam como 1 réplica biológica. | Aceita |
| G9 | Dados de outras espécies servem como prior fraco/sensibilidade, nunca como valor calibrado de *D. maidis*. | Aceita |

**Premissas rejeitadas**

| ID | Premissa rejeitada | Status |
| --- | --- | --- |
| R1 | Ajustar $EC_{50}$, $E_{max}$, $n$ juntos com os dados atuais de *D. maidis*. | Rejeitada (não identificável) |
| R2 | Fixar $E_{max} \approx 1,0$ por padrão. | Rejeitada (platô oral é baixo) |
| R3 | Combinar oral + injeção (ou + planta transgênica) no mesmo eixo $D$. | Rejeitada (grandezas distintas) |
| R4 | Tratar 100 e 200 ng/µL como dois níveis informativos de dose. | Rejeitada (mesmo KD; oral dose-independente) |
| R5 | Ler uma boa curva/baixo AIC como evidência de parâmetros bem estimados. | Rejeitada (curva ótima com $EC_{50}$/$n$ indeterminados) |
| R6 | Extrapolar a curva para fora do intervalo de doses observado. | Rejeitada |

## 11. Suposições simplificadoras: como FAZER e como DOCUMENTAR

Atendendo explicitamente às duas seções da instrução (método Shiflet & Shiflet).

### 11.1 Como fazer as simplificações (aplicadas aqui).

- Negligenciar variáveis menos relevantes: na v1, ignora-se a dependência do KD com o comprimento do dsRNA e com o gene específico (agregados), por falta de dados para estimá-las.
- Tratar variáveis como constantes: $n$ fixado em 1 até haver dados de transição; tempo fixado no endpoint (dia 7) para isolar o efeito de dose.
- Agregar variáveis: as doses orais 100 e 200 ng/µL, indistinguíveis nos dados, são tratadas como um único nível.
- Relações mais simples primeiro: começar por Hill com $n= 1$ (equivalente a Michaelis-Menten/saturação simples) antes de qualquer sigmoide íngreme.
- Restringir o escopo: o eixo $D$ restringe-se à rota oral e à concentração na dieta; injeção e planta transgênica saem do ajuste principal.

### 11.2 Como documentar (registrado neste relatório e no parameters_hill.yaml).

- Registrar suposição + justificativa (rationale): cada hipótese G1–G9/R1–R6 traz o porquê, não só o quê.
- Documentar desde o início: este relatório e o arquivo de parâmetros são versionados junto com o código; nada de valores hardcoded no notebook.
- Especificar limites e faixas de aplicabilidade: ver §12.

## 12. Domínio de validade

Qualquer ajuste eventual será válido apenas dentro do intervalo de doses observado e para a rota/tempo/espécie correspondentes. Concretamente: uma Hill ajustada entre 100 e 500 ng/µL não autoriza previsões confiáveis em 1 ng/µL ou 5000 ng/µL (Figura 3 quantifica essa ambiguidade). O livro separa resolver corretamente o modelo de validar que ele responde ao problema certo, e adverte contra aplicá-lo muito além do intervalo em que foi construído — princípio adotado como restrição explícita.

## 13. Lacunas que impedem a calibração e como fechá-las

| Parâmetro | Estado | Como fechar |
| --- | --- | --- |
| $EC_{50}$ (oral, *D. maidis*) | AUSENTE | Curva própria com $\ge 5$ doses cobrindo baixo-efeito, transição e platô; ou reunir pontos orais de Hemiptera com dose absoluta. |
| $E_{max}$ | AUSENTE | Idem; medir doses altas até o platô. Evidência externa sugere teto baixo (0,3–0,5). |
| $n$ (Hill) | AUSENTE / não identificável | Requer vários pontos na transição. Até lá, fixar $n= 1$. |
| Comprimento do dsRNA | Parcial | Registrar bp por construto (afeta eficiência). |
| $\beta_{KD\to\mathrm{ovos}}$ | AUSENTE | Extrair KD e oviposição do MESMO experimento (Dalaisón-Fuentes 2022) para ligar efeito molecular ao fenótipo. |
| Réplica/dispersão | Insuficiente | Registrar $n$ biológico e IC/SD por ponto (2 de 72 pares têm hoje). |

## 14. Entregável computacional (protocolo pronto)

O código (01_reconstruir_dataset.py, 02_analise_figuras.py, 03_saidas.py) já implementa, de forma reprodutível e sem valores hardcoded de parâmetros de saída:

1. carregar o dataset reconstruído e as unidades de um arquivo separado;
2. definir $KD(D; E_{max}, EC_{50}, n)$;
3. ajuste progressivo ($n= 1$ → $n$ livre → $E_{max}$ livre) por condição/tempo;
4. relatar $EC_{50}$, $E_{max}$, $n$ com IC, correlações e AIC — não só a curva;
5. bootstrap/perfil para incerteza; teste de estabilidade à retirada de pontos;
6. validar dentro do domínio; sinalizar extrapolação.

Basta trocar usar_em_modelo para sim e preencher valor_num/n/incerteza quando os pontos verificados existirem — a mesma disciplina de “editar uma célula, nunca reescrever o notebook” adotada no banco.

## 15. Conclusão

O que os dados permitem afirmar hoje: (i) existe efeito de RNAi por via oral em D. maidis (BicC, ~0,73 de KD no dia 7), mas medido em um nível efetivo de dose; (ii) a rota (oral vs injeção) e o tempo dominam a variação observada, não a dose; (iii) o RNAi oral em Hemiptera tende a um platô baixo. O que os dados não permitem: estimar $EC_{50}$, $E_{max}$ e $n$ de forma identificável para D. maidis oral. O entregável defensável do M2 é, portanto, a estrutura parametrizável + o protocolo de ajuste + a declaração honesta das lacunas — e não uma curva suave que esconderia a incerteza atrás de um ajuste bonito.

Próxima ação crítica. Gerar (ou reunir) uma curva dose-resposta oral com pontos na região de baixo efeito, na transição e no platô, a tempo fixo, com réplicas biológicas e dispersão — começando por incorporar ao banco, sob verificação humana, as fontes de D. citri (2024) e P. stali (2021).

## Referências e rastreabilidade

Marcação de acesso: [aberto] = texto completo conferido nesta etapa; [paywall] = só resumo/registro do banco.

- Jones-Bernal et al. (2021). Assessing the Functionality of RNA Interference (RNAi) in the Phloem-feeding Maize pest Dalbulus maidis. bioRxiv. DOI: 10.1101/2021.09.29.462424. [aberto] — V-ATPase B/D, dieta, 500 ng/µL, dose única; $n= 3$ pools de 3 insetos.

- Dalaisón-Fuentes et al. (2022). Development of efficient RNAi methods in the corn leafhopper Dalbulus maidis. Pest Manag. Sci. DOI: 10.1002/ps.6937 (Wiley [paywall]); preprint bioRxiv 10.1101/2022.01.17.476645 [aberto] — BicC, oral e injeção, 100/200 ng/µL; 372 bp; $n= 3$ biológicas, SD.
- Qureshi et al. (2024). Optimal dsRNA Concentration for RNA Interference in Asian Citrus Psyllid. Insects 15(1):58. DOI: 10.3390/insects15010058. [aberto; EXTERNO ao banco] — 5 doses orais; único dose-resposta oral multi-dose em Hemiptera.
- Plautia stali — Effectiveness of orally-delivered dsRNA on gene silencing in the stinkbug Plautia stali. PLoS ONE (2021). DOI: 10.1371/journal.pone.0245081. [aberto] — oral 100/1000/5000 ng/µL; ~50% KD só a 5000.
- Nilaparvata lugens (2011). PLoS ONE. DOI: 10.1371/journal.pone.0020504. [aberto] — planta transgênica, KD 42–73% sem dose absoluta (não posicionável no eixo $D$).
- Knockdown of dsRNases enhances oral RNAi in Dalbulus maidis (2023). Pestic. Biochem. Physiol. DOI: 10.1016/j.pestbp.2023.105618. [paywall — só resumo] — pré-tratamento/dsRNase-2; pertence ao M1, não à curva de Hill.
- Shiflet, A. B.; Shiflet, G. W. Introduction to Computational Science. — base metodológica (modelos empíricos, simplificações, verificação × validação).

Ressalva de acesso (preferência do projeto). Onde só tive o resumo (dsRNase-2 2023, ScienceDirect; versão Wiley de ps.6937), usei a versão aberta correspondente ou apenas o registro do banco, sem inventar números do texto completo. Os pontos numéricos usados vêm de fontes [aberto].

## Apêndice A — Dataset reconstruído (resumo)

Arquivos: dataset_dose_knockdown_reconstruido.csv e .xlsx (com aba “dicionario”). Colunas: id, espécie, hemiptera, alvo, rota, dose_valor, dose_unidade, dose_tipo, t_exposicao, t_medicao_KD, endpoint_original, KD_frac, n_biologico, dispersao, dsRNA_bp, transferibilidade, fonte, DOI, uso_no_Hill, obs. Observações elegíveis para o ajuste de Hill em D. maidis oral: 0 (nenhuma com dose resolvida + KD numérico + verificação + transição).

## Apêndice B — parameters_hill.yaml

Arquivo entregue à Modelagem, no espírito do “parameters.yaml” do M1: declara EC50_KD, E_max, n_Hill como AUSENTE / usar_em_modelo: nao, registra o prior externo fraco de D. citri (transferibilidade 3, apenas ordem de grandeza), o critério de liberação e as ações para fechar a lacuna. Nenhum valor calibrado é afirmado.
