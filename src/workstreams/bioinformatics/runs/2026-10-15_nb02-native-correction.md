# NB02: correção computacional para CANDIDATE_NATIVE_ALIGNMENT

Data: 2026/10/15, America/Sao_Paulo. Estado atual: revisão computacional independente por agente concluída, conforme declaração do responsável registrada ao final deste relatório. Integração técnica Git autorizada pelo responsável. Pareceres humanos sobre as candidatas native permanecem pendentes. CP5 native não foi fechado. As seções de execução e os artefatos científicos preservam seus estados históricos de materialização.

## Resultado demonstrado

A nova execução consultou 4.174 candidatas e um benchmark diretamente. Produziu 122.783 HSPs e reproduziu 907 diferenças de vetor, Pareto L400 de 667 janelas e 12 células. As diferenças estão exclusivamente em DSRNASE1. Esses valores foram conhecidos no diagnóstico anterior e serviram como referências de investigação. Nenhum parâmetro foi ajustado para obtê-los.

## Autorização, base e isolamento

Autorização vigente: anexo do responsável com SHA256 `5be6ca45cbed2192dc609c4bd52a539a71f0d8922c1e75993ff39ab688fd8d7c`. Referência técnica 0.2: SHA256 `6714e0a6eee0598de2480d18c5758251083ca013e99c8f60d7908a00b70137a9`. A autorização substituiu a auditoria documental prévia e as autorizações fragmentadas, manteve dois a quatro recomendados e excluiu a expansão C18.

A correção é posterior a um diagnóstico com efeitos conhecidos sobre candidatos. O resultado histórico full CDS + clipping permanece preservado e identificado.

Base confirmada: `a34892d1874a7ea3298cb1873f02efd4cd99912a`. Branch local de implementação: `feat/nb02-native-correction`. Checkout gerenciado: `C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab`. Nenhum commit, push, PR, merge ou snapshot foi realizado.

A árvore principal permanece em `feat/nb04-cp0`, no mesmo HEAD, com o staging vazio e as mesmas alterações CP0 preexistentes. Seus 448 arquivos protegidos conservaram os hashes. O checkout de implementação contém apenas três arquivos novos no patch: módulo, testes e este registro. Resultados e logs ficam em namespaces ignorados pelo Git.

A suíte completa foi executada em clone descartável com metadados Git independentes, sem hardlinks ou alternates, contendo uma cópia fiel da árvore atual, incluindo o patch CP0 preexistente, acrescida dos dois arquivos de código/teste NB02. O patch CP0 não foi incorporado à branch de implementação.

## Organização e compatibilidade

Foi escolhido um único módulo aditivo para evitar multiplicação de loaders, schemas e políticas. O YAML e os módulos históricos permaneceram inalterados. A implementação reutiliza parsing e validação BTOP puros de NB03, sem invocar seu workflow, suas unidades ou seu desempate. Reutiliza os kernels NB02 de assinatura, dominância, células e ordenação.

| Arquivo | Função |
| --- | --- |
| [nb02_native.py](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/src/zeaguard/nb02_native.py) | Queries certificadas, busca native, métricas, CP3, CP4 e estado separado de revisão/quantidade |
| [test_nb02_native.py](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/tests/test_nb02_native.py) | 36 casos de reconstrução, agregação, precisão, falha, integridade e compatibilidade |
| 2026-10-15_nb02-native-correction.md | Registro consolidado da autorização, método, execução, resultados e limitações |

## Contrato efetivamente executado

Python 3.12.14 em `/home/daniel/miniforge3/envs/zeaguard`, WSL Ubuntu 24.04.4, BLAST 2.17.0+, build Aug 22 2026. O banco foi reconstruído de inputs locais certificados: 56.117 registros TSA e quatro cDNAs publicados, total 56.121 registros e 94.710.159 bases. SHA256 combinado: `ea236b31337549262969fdadd54fcce2ae1bb7bceef14e5ee51c95d952c63d4b`.

Native: `-task blastn -dust no -word_size 11 -evalue 10 -strand both -max_target_seqs 100000 -num_threads 1 -reward 2 -penalty -3 -gapopen 5 -gapextend 2`. Sem `searchsp` e sem `max_hsps`.

Outfmt exato: `6 qseqid sseqid pident length qlen slen qstart qend sstart send sstrand evalue bitscore mismatch gapopen gaps qcovs btop score nident`. Os 18 campos históricos permanecem na mesma ordem, seguidos de score e nident. Estes campos adicionais são instrumentação descritiva.

Identidade é a razão float entre identidades BTOP e todas as colunas do HSP, incluindo ambos os tipos de gap. Cobertura é união inclusiva de posições da query dentro da unidade. Maior trecho exato é o máximo de trechos consecutivos, interrompidos por diferença ou gap, sem concatenar HSPs. Os descritores são independentes. Unidades não são agrupadas.

O desempate preserva maior identidade interna, maior extensão da query e menor identificador textual histórico, com ordenação canônica residual por coordenadas e BTOP. A métrica não usa bitscore ou E-value para ordenar candidatas. Colunas alinhadas, extensão da query e numerador do HSP fornecedor são preservados separadamente.

CP3 grava identidade com seis casas decimais. CP4 lê o TSV persistido, valida essa fronteira e usa os valores relidos em igualdade, Pareto e assinaturas. Não há epsilon decisório adicional. A busca concluída sem HSP recebe NO_REPORTED_HSP_UNDER_CONFIGURED_SEARCH e vetor zero. Falhas e processamento incompleto não são convertidos em ausência.

## Queries, HSPs e verificações exatas

| Objeto | Contagem |
| --- | --- |
| Queries de desenho | 4174 |
| Benchmark separado | 1 |
| HSPs native | 122783 |
| Linhas query × unidade | 20875 |
| Verificações query × unidade × k | 41750 |
| Divergências de k mers | 0 |

| Unidade | HSPs |
| --- | --- |
| DSRNASE1 | 3632 |
| KNOWN_DSRNASE2_COMPATIBLE | 12525 |
| OTHER_TRANSCRIPT | 106626 |

As queries foram rederivadas da CDS operacional e verificadas contra os hashes CP2, com igualdade exata do conjunto de IDs. O manifest CP2 e os arquivos por ele vinculados foram verificados. Os outputs diagnósticos não foram lidos pelo pipeline. A comparação histórica ocorre após o cálculo native.

## Comparação histórica por estrato

| Estrato | N1 diferentes | Pareto histórica | Pareto native | Células históricas | Células native |
| --- | --- | --- | --- | --- | --- |
| 300 | 259 | 1126 | 867 | 11 | 14 |
| 330 | 289 | 1096 | 807 | 10 | 13 |
| 400 | 359 | 1026 | 667 | 9 | 12 |
| 500 | 0 | 926 | 926 | 9 | 9 |

Total N1: 907 diferentes e 3.267 idênticos. DSRNASE1: 907 diferenças. DSRNASE3 e BICC: zero. A comparação nominal por candidata, unidade e estrato foi persistida, incluindo pertencimento, células, representantes e grupos.

| Candidato | Vetor DSRNASE1 native | Pareto | Célula | Grupo | Representante |
| --- | --- | --- | --- | --- | --- |
| D2-L400-0351-0750 | ('0', '0', '0.000000') | True | D2C-L400-006 | 1 | D2-L400-0351-0750 |
| D2-L400-0817-1216 | ('12', '42', '0.761905') | False | D2C-L400-010 | 7 | D2-L400-0817-1216 |

D2-L400-0351-0750 continua não dominado e representa o grupo superior. D2-L400-0817-1216 sai da Pareto e permanece representante de sua célula no grupo 7. Nenhuma candidata de grupo inferior ou janela equivalente foi adicionada para atingir quantidade.

| Benchmark: unidade | Maior trecho exato | Cobertura | Melhor identidade | Colunas do HSP fornecedor |
| --- | --- | --- | --- | --- |
| DSRNASE1 | 12 | 42 | 0.761905 | 42 |
| DSRNASE3 | 0 | 0 | 0.000000 | 0 |
| BICC | 0 | 0 | 0.000000 | 0 |
| KNOWN_DSRNASE2_COMPATIBLE | 330 | 330 | 1.000000 | 330 |
| OTHER_TRANSCRIPT | 17 | 161 | 1.000000 | 17 |

## C18 e alcance dos controles

Foram reproduzidos os cinco shuffles históricos da CDS, seeds 1 a 5, com `random.Random(seed).shuffle`, composição mononucleotídica preservada e parametrização histórica. A consulta da CDS foi mantida nessa reprodução como referência. O multiconjunto dos 18 campos de todos os 150 HSPs reproduziu exatamente o histórico. Os shuffles forneceram respectivamente 31, 18, 17, 18 e 22 HSPs.

Esses controles são contexto descritivo do comportamento histórico, não controles específicos de cada candidata native. A expansão para 20.875 queries de controle não foi executada e permanece fora desta entrega. Os controles não constituem inferência estatística, threshold biológico ou critério de exclusão. Testes sintéticos e varredura exata independente sustentam verificações da reconstrução e agregação native.

## Validação executada e determinismo

| Validação | Resultado |
| --- | --- |
| Testes novos isolados | 36 passed in 3.27s |
| Suíte completa no clone QA | 663 passed in 177.18s, zero falhas e skips |
| Repetição CP3/CP4 em namespace novo | 25 artefatos determinísticos idênticos por SHA256 |
| Reprodução histórica CDS e C18 | Multiconjunto dos 18 campos idêntico |
| Preservação da árvore principal | 448 hashes idênticos, branch/HEAD/status/staging preservados |

A suíte de QA incluiu os consumidores NB03 e o trabalho NB04 atual. Foram testados ambos os tipos de gap, orientações, mismatches, coordenadas, redundância, agregação independente, desempate por extensão da query, serialização e leitura CP4, falha versus ausência, integridade e igualdade exata das queries.

A repetição exclui da igualdade de bytes os comandos/manifests com caminhos e horários próprios e metadados de build dos binários BLAST. Os arquivos científicos, HSPs brutos, FASTA combinado e estados comparados coincidiram. Não é alegada identidade de metadados variáveis.

Comandos executados a partir do driver do ambiente canônico:

```text
python artifacts/nb02_native_setup/environment.py pytest -q tests/test_nb02_native.py -p no:cacheprovider
python artifacts/nb02_native_setup/environment.py cp3
python artifacts/nb02_native_setup/environment.py cp4
python <clone_QA>/artifacts/nb02_native_setup/environment.py pytest -q -p no:cacheprovider
python artifacts/nb02_native_setup/verify_delivery.py
```

O driver fixa PATH, PYTHONPATH, ausência de bytecode e a interpretação do Git entre Windows e WSL. A CLI pública do produto é `python -m zeaguard.nb02_native cp3 --root <checkout>` e o subcomando `cp4`. As linhas BLAST completas, retornos e horários estão no commands.json CP3.

Ocorrências operacionais resolvidas: a preparação inicial teve erros de tamanho de argumento e quoting antes da execução científica. A revisão automática rejeitou a primeira proposta de QA com metadados Git compartilhados antes de sua execução. A alternativa aplicada foi um clone independente. Não houve falha nos testes executados nem divergência de proveniência.

## Revisão humana, CP5 e NB04

Existe um representante provisório no grupo 1, D2-L400-0351-0750. Existem zero novas aprovações humanas. Isso não equivale a uma recomendação final. O pacote de revisão e seu hash foram preparados. Pareceres históricos não foram transferidos.

A regra de dois a quatro recomendados foi preservada. CP5 não está fechado: revisão humana pendente e quantidade aprovada abaixo do mínimo. Não foi produzido ou promovido handoff final. A revisão independente dos resultados científicos pode prosseguir. Não foi fabricado nome, parecer ou adjudicação.

A mudança na justificativa científica da região D2-L400-0817-1216 requer avaliação de aplicabilidade do upstream NB04 antes de G0. Os bytes e a proveniência do bundle atual permanecem preservados. Sua aplicabilidade não foi declarada resolvida e NB04 não foi declarado inválido. Nenhuma atualização de bundle, busca NTO, calibração informativa ou resource freeze foi executada. G0_PASS = NOT_DECLARED. CP1 NB04 = NOT_STARTED.

GITV01009778.1 continua em OTHER_TRANSCRIPT pela política congelada e biologicamente IDENTIDADE_BIOLOGICA_UNRESOLVED. A identidade local de 17 nt não estabelece identidade de locus ou off target funcional.

## Artefatos para revisão conjunta

| Artefato | Local |
| --- | --- |
| Manifest CP3 | [run_manifest.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp3/run_manifest.json) |
| Manifest CP4 | [run_manifest.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/run_manifest.json) |
| Comparação por candidata | [delta_by_candidate.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/delta_by_candidate.tsv) |
| Comparação por unidade | [delta_by_unit.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/delta_by_unit.tsv) |
| Células e representantes | [cells.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/cells.tsv) |
| Pacote de revisão | [review_evidence.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/review_evidence.tsv) |
| Estado de fechamento | [closure_status.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/closure_status.json) |
| Log da suíte completa | [full_suite.log](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/artifacts/nb02_native_setup/full_suite.log) |
| Determinismo | [reproduction_verification.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/reproduction_verification.json) |
| Preservação | [preservation_verification.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/preservation_verification.json) |
| Hashes consolidados | [delivery_manifest.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/delivery_manifest.json) |

## Conclusão e limites

A entrega demonstra a implementação computacional da geometria native conforme o contrato autorizado, sua compatibilidade com a fronteira numérica histórica, integridade dos inputs, reprodução dos resultados de referência e ausência de regressões na suíte executada. Essa conclusão não substitui revisão científica independente, revisão humana das evidências ou certificação de eficácia e segurança biológica. O pacote está preparado para revisão conjunta de código e resultados.

## Análise das consequências científicas para NB02 e da aplicabilidade dos inputs NB04

Data: 2026/10/15. Autoria: agente. Natureza: interpretação dos resultados existentes e avaliação documental de aplicabilidade. Esta seção atualiza a avaliação anteriormente assinalada como pendente neste registro. Pareceres humanos sobre o pacote native, auditoria científica independente e decisão de G0 continuam pendentes. A leitura, comparação de tabelas e conferência de hashes desta etapa utilizaram exclusivamente arquivos locais existentes. Nenhuma busca, execução científica, calibração ou geração de evidência experimental foi realizada.

### Fontes e alcance da comparação

1. Evidência native: [candidate_unit_specificity.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp3/candidate_unit_specificity.tsv), [hsp_provenance.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp3/hsp_provenance.tsv), [benchmark_specificity.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp3/benchmark_specificity.tsv) e [exact_kmer_checks.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp3/exact_kmer_checks.tsv).
2. Seleção native: [cells.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/cells.tsv), [delta_by_candidate.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/delta_by_candidate.tsv), [comparison_summary.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/comparison_summary.json), [review_packet_manifest.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/review_packet_manifest.json) e [closure_status.json](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/native_v1/cp4/closure_status.json).
3. Evidência histórica: [provisional_candidates.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/cp4/provisional_candidates.tsv), [other_transcript_review_evidence.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/cp4/other_transcript_review_evidence.tsv), [benchmark_specificity.tsv](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/results/bioinformatics/nb02/cp3/benchmark_specificity.tsv) e [handoff NB02 histórico](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/data/reference/nb02_dsrnase2_candidate_regions.tsv).
4. Interpretação e gates históricos: [critérios NB02](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/config/nb02_design_criteria.yaml), especialmente C07, C09, C10, C17, C18, C19 e a política de seleção iterativa, [pareceres humanos de 2026/10/07](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/config/nb02_manual_review_decisions.tsv), [limitações históricas](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/config/nb02_candidate_limitations.tsv), [ADR 0005](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/src/workstreams/bioinformatics/decisions/0005-nb02-dsrnase2-candidate-region-policy.md) e [pin NB01](C:/Users/Daniel/.codex/worktrees/nb02-native-correction/zeaguard-drylab/data/reference/nb01_dsrnase2_operational_reference.json).
5. Conteúdo NB04 efetivamente incorporado na árvore principal: [registro de queries](C:/Programming/Python/zeaguard-drylab/data/reference/nb04_nto_queries.tsv), [FASTA](C:/Programming/Python/zeaguard-drylab/data/reference/nb04_nto_queries.fasta), [proveniência](C:/Programming/Python/zeaguard-drylab/data/reference/nb04_upstream_provenance.json), [política atual](C:/Programming/Python/zeaguard-drylab/config/nb04_nto_policy.yaml), [ADR 0007](C:/Programming/Python/zeaguard-drylab/src/workstreams/bioinformatics/decisions/0007-nb04-nto-sequence-specificity-policy.md) e [contrato implementado de bundle](C:/Programming/Python/zeaguard-drylab/src/zeaguard/nb04_cp0.py). O PLAN v2.2.5, preservado no [arquivo normativo fornecido](C:/Users/Daniel/Downloads/NB04_B5_INPUTS/01_PLAN_v2.2.5.md), foi consultado em §B, §G.6, §I.7, §J.0 e §K.2. Sua identidade consta no ADR 0007 e no registro documental CP0.

Os valores abaixo foram conferidos nas linhas das respectivas queries. O vetor é apresentado na ordem maior trecho exato, união de posições cobertas da query e melhor identidade local. Identidades decimais reproduzem a precisão persistida de seis casas. Comprimento do HSP fornecedor, cobertura agregada e trecho exato são descritores diferentes. Quatro registros da mesma unidade representam evidência redundante para agregação, sem multiplicação da cobertura ou demonstração de quatro loci independentes.

### Interpretação dos três casos

| Query | Unidade | Vetor histórico | Vetor native | Consequência computacional |
| --- | --- | --- | --- | --- |
| D2-L400-0351-0750 | DSRNASE1 | (0, 0, 0.000000) | (0, 0, 0.000000) | Continua na Pareto L400 e no grupo 1 |
| D2-L400-0351-0750 | DSRNASE3 e BICC, separadamente | (0, 0, 0.000000) em cada unidade | (0, 0, 0.000000) em cada unidade | Preserva os demais eixos decisórios |
| D2-L400-0817-1216 | DSRNASE1 | (0, 0, 0.000000) | (12, 42, 0.761905) | Sai da Pareto L400, passa do grupo 1 ao grupo 7 |
| D2-L400-0817-1216 | DSRNASE3 e BICC, separadamente | (0, 0, 0.000000) em cada unidade | (0, 0, 0.000000) em cada unidade | Mudança decisória restrita a DSRNASE1 |
| D2-BENCH-0814-1143 | DSRNASE1 | (0, 0, 0.000000) | (12, 42, 0.761905) | A descrição histórica de vetor zero requer qualificação pela geometria |
| D2-BENCH-0814-1143 | DSRNASE3 e BICC, separadamente | (0, 0, 0.000000) em cada unidade | (0, 0, 0.000000) em cada unidade | Mantém a descrição de ausência de HSP reportado nessas unidades |

#### D2-L400-0351-0750

A candidata continua representante de D2C-L400-006, célula com 66 janelas, inícios de 351 a 416 e términos de 750 a 815. É a única célula do grupo superior L400 na execução native. A assinatura preserva ausência de variantes conhecidas interceptadas e vetores zero em DSRNASE1, DSRNASE3 e BICC. O desempate entre as duas células historicamente superiores deixou de existir porque a célula representada por 0817 passou a apresentar evidência em DSRNASE1. Essa preferência é condicional ao banco, às unidades congeladas, à geometria e à hierarquia computacional do contrato.

A evidência descritiva OTHER_TRANSCRIPT mudou substancialmente, apesar da assinatura decisória preservada.

| Query | Geometria | Maior trecho exato OTHER_TRANSCRIPT | covered_nt | Melhor identidade | Colunas do HSP fornecedor | HSPs | Registros | Contagens exatas de 19 e 21 nt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D2-L400-0351-0750 | Histórica | 18 | 115 | 1.000000 | 18 | 10 | 10 | 0 e 0 |
| D2-L400-0351-0750 | Native | 18 | 186 | 1.000000 | 18 | 28 | 28 | 0 e 0 |
| D2-L400-0817-1216 | Histórica | 17 | 126 | 1.000000 | 15 | 17 | 17 | 0 e 0 |
| D2-L400-0817-1216 | Native | 17 | 186 | 1.000000 | 17 | 44 | 44 | 0 e 0 |
| D2-BENCH-0814-1143 | Histórica | 17 | 111 | 0.952381 | 21 | 16 | 16 | 0 e 0 |
| D2-BENCH-0814-1143 | Native | 17 | 161 | 1.000000 | 17 | 43 | 43 | 0 e 0 |

Para 0351, os dez accessions anteriores continuam presentes e existem 18 adicionais. Os HSPs native têm de 17 a 38 colunas. O trecho perfeito de 18 nt continua em GITV01026637.1, query 117 a 134, CDS 467 a 484. Além da concentração histórica próxima da CDS 500 a 540, a tabela native contém correspondências perfeitas de 17 nt em CDS 411 a 427, contra GITV01009367.1 e GITV01052134.1, e em CDS 636 a 652, contra GITV01021810.1, GITV01026552.1 e GITV01026577.1. Há também HSPs adicionais com diferenças e gaps. Esses exemplos demonstram que a revisão futura precisa considerar a distribuição completa, incluindo regiões fora da concentração destacada anteriormente.

Permanecem sustentadas a ausência de HSP reportado nas três unidades decisórias, a ausência dos k mers exatos de 19 e 21 nt verificada no pacote, o maior trecho exato OTHER_TRANSCRIPT de 18 nt e a ausência de variantes conhecidas nesse intervalo. O alcance desses resultados é o recurso e a configuração examinados. A ausência de variantes conhecidas tampouco demonstra invariância populacional.

O parecer histórico APPROVED foi emitido por Daniel Harley em 2026/10/07 e vinculado ao hash de evidência `5b377739627c1eb4b10ce484c21ce714c903d77720a5a5a78dbc138cce46e2d4`. O novo pacote de revisão tem hash `a448b02b76a607a175ff4821ccdcdf57f669d82d4ed4aa3b73bf03f563de805b` e declara `historical_review_transferred=false`, com `human_decisions=[]`. A permanência dos três máximos decisórios e dos dois descritores extremos de OTHER_TRANSCRIPT não demonstra equivalência entre os pacotes revisados. A avaliação humana de concern sobre os 28 HSPs permanece pendente.

A conclusão sustentada para 0351 é sua preferência computacional provisória no estrato nominal de 400 nt e sua prioridade para revisão humana sobre a evidência native existente. O resultado preserva empates entre as 66 janelas da célula e não demonstra superioridade biológica exclusiva dessa janela, eficácia, ausência de efeito funcional em outros transcritos ou segurança ecológica. A posição central, o GC e os controles históricos continuam descritivos.

#### D2-L400-0817-1216

O intervalo e seu hash permanecem iguais aos históricos, assim como a ausência de variantes conhecidas interceptadas. A célula representada continua compreendendo 56 janelas, com inícios de 817 a 872, agora identificada como D2C-L400-010, grupo 7 e fora da Pareto. O vetor DSRNASE1 native torna 0817 dominado por 0351 nos eixos dessa unidade, com igualdade nos eixos DSRNASE3 e BICC. A justificativa histórica de empate no grupo superior e de vetor zero em todas as unidades decisórias deixou de descrever o resultado native.

Os quatro HSPs DSRNASE1 de 0817 cobrem as mesmas posições da query, 106 a 147, correspondentes à CDS 922 a 963. Cada um tem 42 colunas, 32 identidades, dez mismatches e zero gaps. A identidade interna é 32/42, persistida como 0.761905. Os subjects são GITV01001583.1, GITV01002042.1, GITV01003945.1 e TRINITY_DN13786_c0_g1_i8. A cobertura da unidade é 42 nt. Essa evidência permite rever a comparação de homologia local com o parálogo. Seu E value reportado de 8.4 permanece contexto da busca, sem papel de threshold biológico.

No fundo OTHER_TRANSCRIPT, a mudança também ultrapassa uma simples contagem de novos registros. Dos 17 accessions históricos, 16 continuam presentes, GITV01043171.1 deixa de ser reportado para esta query e 28 outros passam a constar. A melhor identidade continua 1.000000, mas seu HSP fornecedor passa de 15 a 17 colunas. O novo fornecedor é GITV01009778.1. Esses fatos impedem transferir automaticamente o parecer anterior mesmo para os descritores que parecem numericamente estáveis.

O pertencimento de 0817 à shortlist histórica permanece um fato documental verificável. Sua prioridade atual como recomendação native perdeu o fundamento anterior. A saída da Pareto expressa dominância computacional sob o contrato e não constitui uma decisão humana STRONG_SPECIFICITY_CONCERN ou demonstração de cross silencing. A sobreposição de 327 nt com o benchmark continua correta e útil para particionar evidência compartilhada e exclusiva. Sua interpretação como convergência de uma escolha atualmente preferida com o benchmark precisa ser abandonada para o pacote native.

#### D2-BENCH-0814-1143

O benchmark continua sendo o fragmento de 330 nt da CDS 814 a 1143 e permanece REFERENCE_SET. Seu novo sinal DSRNASE1 ocupa query 109 a 150, a mesma CDS 922 a 963 encontrada em 0817. Os quatro subjects, as 32 identidades em 42 colunas, o trecho exato máximo de 12 nt, o raw score 34, o bitscore 31.9 e o BTOP `2AT2GC12CT1TA3TC1GCAT3GA1TG2GA5` coincidem com os de 0817. O E value é 6.8 para a query de 330 nt. Esses HSPs estão inteiramente na região compartilhada de 327 nt e constituem evidência sobre o mesmo substrato de sequência. Sua concordância não fornece uma réplica biológica independente.

No fundo OTHER_TRANSCRIPT, os 16 subjects anteriores são mantidos e existem 27 adicionais. O vetor descritivo passa de (17, 111, 0.952381) a (17, 161, 1.000000). O único HSP perfeitamente idêntico native nessa unidade é contra GITV01009778.1, com query 102 a 118, subject 149 a 165, BTOP 17, raw score 34 e bitscore 31.9. Em 0817, o mesmo trecho aparece na query 99 a 115. Ambos mapeiam à CDS 915 a 931 e têm zero mismatches e gaps.

A classificação computacional desse accession continua OTHER_TRANSCRIPT pela política congelada, que exclui apenas os membros declarados das unidades decisórias e os três registros KNOWN_DSRNASE2_COMPATIBLE. `GITV01009778.1 = IDENTIDADE_BIOLOGICA_UNRESOLVED` é preservado. O alinhamento perfeito de 17 nt não resolve identidade de locus, relacionamento com o próprio alvo ou efeito funcional de RNAi. O resultado tampouco autoriza declarar background biologicamente confirmado ou concern funcional. Uma futura identificação requer evidência independente e procedimento separado.

A unidade KNOWN_DSRNASE2_COMPATIBLE conserva os três subjects congelados e o vetor agregado (330, 330, 1.000000). A inspeção dos HSPs individuais mostra 330/330 identidades em GITV01008430.1 e no cDNA TRINITY_DN22752_c0_g2_i1, e 329/330 em GITV01012450.1. O máximo agregado não representa identidade perfeita de todos os registros. A diferença é compatível com a variante sinônima conhecida na CDS 816, já documentada no pin.

Permanecem sustentados o intervalo, a sequência, a verificação por suplemento e referência e seu papel comparativo. Os protocolos e endpoints permanecem PROJECT_PROVIDED_NOT_AGENT_VERIFIED. A coadministração de BicC no protocolo oral impede atribuir seus endpoints exclusivamente ao fragmento dsRNase 2. O benchmark continua excluído da quantidade de recomendados e de qualquer score de eficácia. Comparações de seleção preservam os estratos de comprimento, especialmente a distinção entre 330 e 400 nt.

### Justificativas históricas que requerem qualificação

1. A afirmação de que a especificidade não separa nenhuma janela L400 descreve a execução histórica. A execução native registra 359 mudanças nesse estrato, Pareto de 667 janelas contra 1.026 anteriormente e 12 células contra nove. No espaço completo, há 907 vetores alterados entre 4.174 candidatas, todos na unidade DSRNASE1. A ordenação deixou de depender exclusivamente das variantes.
2. O empate histórico entre os representantes 0351 e 0817 permanece documentado como resultado do método anterior. A comparação native favorece 0351 e coloca 0817 no grupo 7. A equivalência de ambas como escolhas atualmente preferidas perdeu sustentação computacional.
3. Para 0351, a justificação de ausência de HSP nas unidades decisórias continua sustentada no limite configurado. A extensão do parecer humano OTHER_TRANSCRIPT ao pacote novo permanece pendente diante de novos HSPs e de cobertura adicional. Para 0817, também mudou a premissa de vetor decisório zero.
4. Os cinco shuffles históricos da CDS foram reproduzidos e conservam sua função descritiva. A semelhança da ordem de grandeza dos trechos exatos históricos não aprova os novos pacotes nem calibra uma probabilidade de efeito. Controles por candidata native não foram executados. A ausência de k mers exatos de 19 ou 21 nt e o tamanho de um trecho perfeito continuam insuficientes para estabelecer ausência de concern.
5. Os artefatos e pareceres históricos são preservados integralmente. Esta seção registra a interpretação posterior, sem retroeditar os fundamentos ou a autoria das decisões anteriores. Os dados demonstram diferenças de evidência entre geometrias. Atribuir todas essas diferenças a um mecanismo interno específico de BLAST exigiria evidência adicional.

### Integridade, proveniência e aplicabilidade NB04

A conferência atual encontrou correspondência dos sete hashes de sequência e comprimentos do registro NB04 com seu FASTA. Para os três inputs dsRNase 2, houve igualdade exata de sequência entre bundle NB04, FASTA histórico NB02 e queries native. Os oito artefatos do registro de proveniência conferem com seus hashes no modo de normalização declarado. O FASTA e o TSV históricos NB02 também conferem com os blobs do commit certificador `74b9d6584690b95d4c8175b7d487940f2372bda6` após normalização LF.

| Objeto conferido | Modo | SHA256 |
| --- | --- | --- |
| nb04_nto_queries.tsv | Bytes atuais | b952466940c776032ad2ad2361668fc118cec7baa7328b01a5d1998e6bdf6007 |
| nb04_nto_queries.fasta | Bytes atuais | 486adee671664db73a2e8ef3dea84650638ce749b835cbd33c97c36a5874a234 |
| nb04_upstream_provenance.json | Bytes atuais | 2ea6f2b771ca58e6b660a214162c93f05706b5ba981114c56e4ae139b3f9bedd |
| FASTA histórico NB02 | LF normalizado, também conferido no commit certificador | a673be55faf1c2c31c9b02d99263d2ab1670e2d711a2be7350faca93dde8ef2e |
| TSV histórico NB02 | LF normalizado, também conferido no commit certificador | 341bc9f32cf120a18295d2f4129de81856a5b765a0759d77f62cace541a42939 |
| Manifest CP5 histórico NB02 | Bytes atuais | 733fb625c1a96aa52febd199625d248b6904de4e172312c7f28678c2ee869b1a |

Essas verificações resolvem a integridade dos objetos examinados e a continuidade da proveniência histórica. A seleção e a sequência são camadas distintas. Os dois CANDIDATE dsRNase 2 apontam para a seleção histórica NB02_CP5 no TSV. O benchmark utiliza o FASTA desse estágio como origem de sequência, com seleção NOT_APPLICABLE. Nenhum desses campos certifica uma seleção native concluída.

O PLAN §B exige exatamente as sete queries integrais. §K.2 limita query_role a CANDIDATE e REFERENCE_SET e preserva a seleção histórica como origem dos candidatos dsRNase 2. A semântica é NB04_SEQUENCE_SCREENING_INPUT e SELECTED_SEQUENCE_FOR_NTO_SCREENING, sem equivalência a WET_LAB_READY. O objetivo NB04 é examinar correspondências de cada sequência em recursos de organismos registrados. O contrato não exige que uma query histórica continue sendo a melhor candidata NB02 para que sua correspondência de sequência seja cientificamente informativa.

Por isso, a perda de posição de 0817 não elimina sua utilidade para a pergunta de correspondência de sequência nem invalida o bundle automaticamente. A manutenção das sete queries, com interpretação explicitamente histórica para essa seleção, é compatível com o contrato observado. A palavra comparador descreve aqui uma função analítica. Uma conversão formal de 0817 para REFERENCE_SET conflitaria com o conjunto de papéis atualmente fixado e exigiria procedimento próprio de atualização. Nenhuma conversão ou atualização foi realizada.

| Input efetivamente incorporado | Dependência da seleção histórica NB02 | Aplicabilidade científica e papel compatível | Disposição recomendada | Ajuste mínimo e pendência humana |
| --- | --- | --- | --- | --- |
| D2-L400-0351-0750, 400 nt, SHA256 5c2b656e80265d1f248fb16cca21aff092b12169c1348758d78959b3d4e5cdc3 | Direta. CANDIDATE, sequência e seleção NB02_CP5 | Continua input histórico íntegro e candidato com preferência computacional native sustentada. Sua sequência é apropriada para examinar correspondências NTO no escopo registrado | Manter com qualificação explícita | Referenciar nesta análise o novo estado provisório e os 28 HSPs OTHER_TRANSCRIPT. A revisão humana native permanece pendente para eventual recomendação NB02. A revisão humana de G0 deverá considerar esse estado sem presumir uma shortlist native fechada |
| D2-L400-0817-1216, 400 nt, SHA256 eb32cfa98180028dab7cfc045171f152d6be34658d02b3259e70857586bc9977 | Direta. CANDIDATE, sequência e seleção NB02_CP5 | Continua informativo como candidato historicamente selecionado e comparador de sequência, inclusive pela partição com o benchmark. Sua apresentação como candidato empatado no topo native perdeu fundamento | Manter com qualificação explícita no escopo histórico NB04. Aplicabilidade como escolha preferida native não sustentada | Registrar a saída da Pareto, grupo 7 e ampliação OTHER_TRANSCRIPT. Preservar o papel CANDIDATE histórico do bundle. A revisão de G0 deverá reconhecer a finalidade histórica e comparativa. Se a finalidade pretendida mudar para avaliar somente recomendações native finais, a composição deverá ser reavaliada em procedimento próprio após revisão e fechamento pertinentes |
| D2-BENCH-0814-1143, 330 nt, SHA256 97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179 | Sem dependência da seleção. Origem de sequência NB02_CP5, seleção NOT_APPLICABLE | Referência publicada com sequência verificada. O novo perfil DSRNASE1 e OTHER_TRANSCRIPT modifica a descrição computacional e preserva a utilidade comparativa. §I.7 mantém REFERENCE_SET | Manter como REFERENCE_SET, com limitações explícitas | Referenciar os vetores native e a identidade biológica unresolved de GITV01009778.1. Preservar a limitação dos protocolos fornecidos pelo projeto. A referência não exige uma aprovação como candidata recomendada nem conta para min 2 |
| BC-L400-1337-1736 | Ausente. Sequência e seleção NB03_CP4B | CANDIDATE do contrato NB04, sem alteração de evidência de seleção demonstrada por esta correção NB02 | Manter | Nenhum ajuste decorrente desta correção. Preservar origem NB03 e revisão NB04 aplicável |
| BC-L400-1253-1652 | Ausente. Sequência e seleção NB03_CP4B | CANDIDATE separado, preservando a região conceitual compartilhada com 1254 | Manter | Nenhum ajuste decorrente desta correção. Preservar a query separada e sua proveniência |
| BC-L400-1254-1653 | Ausente. Sequência e seleção NB03_CP4B | CANDIDATE separado, preservando a região conceitual compartilhada com 1253 | Manter | Nenhum ajuste decorrente desta correção. Preservar a query separada e sua proveniência |
| BC-BENCH-0215-0587 | Ausente. Reconstrução NB03_CP0 certificada pela cadeia CP1 | REFERENCE_SET de 373 nt operacionais com a inconsistência publicada de 372 nt preservada | Manter | Nenhum ajuste decorrente desta correção. Preservar UNRESOLVED_PUBLICATION_INCONSISTENCY |

O alcance dessa conclusão de aplicabilidade é a pergunta de correspondência de sequências do bundle histórico registrado. Os dois candidatos dsRNase 2 dependem da justificativa histórica de seleção, cuja leitura atual requer as qualificações acima. O benchmark depende da cadeia de certificação da sequência e de suas limitações de interpretação. Os quatro inputs BicC não herdam uma seleção NB02. Nenhuma conclusão NTO foi produzida ou revalidada por esta análise.

A análise do agente resolve a distinção entre preservação histórica, sequência examinável e preferência computacional atual. A avaliação humana exigida para G0 permanece aberta, assim como qualquer decisão de redefinir o propósito ou atualizar o upstream NB04. Preservação de bytes não encerra essa avaliação humana. A alteração NB02 também não impõe atualização automática do bundle. Esta seção fornece a análise de aplicabilidade a ser examinada no processo vigente, sem nova proposta de emenda ou rodada de ratificação.

### Limitações e pendências concretas

| Tema | Estado observado | Consequência e evidência necessária |
| --- | --- | --- |
| Evidência computacional NB02 | CP3 e CP4 concluídos no pacote, com verificações e repetição documentadas. Auditoria científica independente PENDING_INDEPENDENT_REVIEW | Os resultados podem ser examinados cientificamente com CP5 aberto. Conclusão da auditoria depende de examinador independente real |
| Parecer humano native sobre 0351 | Nenhuma decisão nova registrada. Pacote com 28 HSPs OTHER_TRANSCRIPT disponível | Um revisor humano deverá examinar a evidência atual e emitir decisão justificada vinculada ao hash desse pacote. O agente não emite APPROVED ou concern em nome do revisor |
| Demais recomendações native | Um representante provisório, zero aprovados. Equivalência entre janelas da célula não equivale a candidatas independentes recomendadas | O contrato e a evidência subsequente governam qualquer progressão. A aprovação hipotética de 0351 produziria apenas uma aprovação e continuaria abaixo do mínimo |
| Quantidade e CP5 native | min 2, max 4. quantity_gate_satisfied=false, human_review_complete=false, closed=false, handoff_promoted=false | CP5 permanece incompleto por revisão e quantidade. Nenhum segundo candidato, janela equivalente, benchmark ou grupo inferior será acrescentado por conveniência. A regra existente de avançar após concern justificado não autoriza preenchimento automático de quota |
| Significado de homologia | HSPs são evidência local dependente do recurso e da configuração | Função, cross silencing e concern exigem interpretação e evidência próprias. Vetor zero significa NO_REPORTED_HSP_UNDER_CONFIGURED_SEARCH |
| GITV01009778.1 | OTHER_TRANSCRIPT computacional, IDENTIDADE_BIOLOGICA_UNRESOLVED | Sua identidade e eventual reclassificação continuam dependentes de evidência independente. O HSP perfeito de 17 nt não encerra essa questão |
| Benchmark e variação | Sequência verificada, protocolos PROJECT_PROVIDED_NOT_AGENT_VERIFIED. As variantes do pin são o conjunto conhecido | Mantêm se as limitações de causalidade do co feeding e de abrangência populacional. Não foi realizada consulta bibliográfica adicional |
| Controles e limites de busca | Cinco shuffles históricos, sem controles específicos por candidata native. Busca BLAST heurística sob os parâmetros registrados | Os controles permanecem descritivos. Ausência de HSP ou de 19/21 mers não demonstra ausência de risco, e E values não são thresholds biológicos |
| NB04 antes de G0 | Integridade e proveniência conferidas. Manutenção qualificada das sete queries sustentada para a finalidade histórica registrada. Avaliação humana de G0 pendente | O revisor de G0 deverá considerar explicitamente a mudança da justificativa de seleção e a distinção entre input histórico e recomendação native. Qualquer alteração de sequência, papel ou composição exige avaliação de impacto e autorização própria |

### Próxima ação técnica recomendada e preservação

A próxima ação é submeter o pacote native já materializado de 0351 a um revisor humano para exame de OTHER_TRANSCRIPT e da interpretação de especificidade, usando o hash de evidência existente. Em paralelo, o pacote CP3/CP4 pode seguir para a auditoria científica independente prevista, mesmo com CP5 incompleto. A preparação computacional do pacote já está concluída. Não é necessária uma nova busca para disponibilizar essa evidência.

Depois de um parecer real, o estado de seleção e os gates deverão ser avaliados pelas regras vigentes. A eventual aprovação de 0351 não fecha CP5 enquanto a quantidade mínima e os demais requisitos permanecerem insatisfeitos. Qualquer progressão precisa de fundamento no contrato, sem inferir um segundo recomendado. Resultados científicos, revisão humana, fechamento do handoff e promoção são estados distintos.

Para NB04, a ação documental mínima é incorporar a leitura desta seção na avaliação humana de aplicabilidade antes de G0, reconhecendo 0351 como provisório native e 0817 como input da seleção histórica, ainda útil à comparação de sequência. O bundle atual conserva a finalidade registrada e seus sete papéis. Uma futura mudança do propósito para consumir exclusivamente a shortlist native final deverá aguardar suas condições efetivamente satisfeitas e seguir procedimento próprio de atualização. Esta análise não introduz um requisito de aprovação de benchmark como candidata nem declara um gate.

Nesta etapa foram autorizadas somente a adição desta seção e a atualização correspondente do hash deste relatório no delivery_manifest.json. Os manifests originais CP3 e CP4 permanecem com SHA256 `bebb4499a204c7d346000592ddd837254acf1d1b51c4b209da51bb7bb1462a8a` e `8857913d643d7f5dc9b944bd0643e4736816f00af500a3b16817e07e979fc0b7`, respectivamente. Código, configurações, resultados científicos, pareceres históricos e bundle NB04 são preservados. CP5 native permanece aberto. G0_PASS = NOT_DECLARED. CP1 NB04 = NOT_STARTED. Não houve operações de integração Git.

## Conclusão da revisão computacional independente e autorização de integração técnica

Data: 2026/10/15, America/Sao_Paulo. O responsável pelo projeto informou que revisou o material apresentado e que a revisão computacional independente foi realizada por agente. A autoria desta consolidação documental também é do agente. A declaração do responsável é a fonte do registro de conclusão da revisão independente nesta seção. O nome ou identificador do agente revisor e um relatório autônomo dessa revisão não foram fornecidos no pedido de integração.

O pedido explícito de integração foi fornecido em [Texto colado.txt](<C:/Users/Daniel/.codex/attachments/b09f3042-387d-4036-9466-60893f85e2bb/Texto colado.txt>), SHA256 dos bytes originais `fab349a3d61010ec94ea38778093333e5b56af167c17d4299e72de1f8fe4fbf5`. Sua identidade é registrada permanentemente aqui, independentemente da disponibilidade futura do caminho local.

### Escopo da revisão independente informado pelo responsável

| Verificação | Resultado informado |
| --- | --- |
| Reconstrução dos HSPs contra as sequências | 122.783 HSPs conferidos |
| Métricas por query e unidade | 20.875 linhas conferidas |
| Células e respectivas Pareto | 48 células reconstruídas |
| Comparação entre evidências históricas e native | 907 diferenças reproduzidas, exclusivamente em DSRNASE1 |
| Pareto L400 | 667 janelas conferidas |
| Testes novos reexecutados na revisão independente | 36 aprovados |
| Vínculos de integridade da entrega | 49 conferidos |
| Artefatos reproduzidos | 25 iguais |
| Arquivos protegidos da árvore principal | 448 preservados |

Os 663 testes da suíte completa pertencem à execução anterior documentada neste relatório e em seu log. O responsável informou a reexecução independente dos 36 testes novos. Esta etapa de integração reaproveita essas evidências enquanto código, inputs e condições pertinentes permanecem iguais. A conferência preparatória atual encontrou os mesmos hashes do módulo, dos testes e dos 49 arquivos vinculados no manifest da entrega. Mudanças desta etapa são documentais, seguidas das verificações de conteúdo, hashes, diff e integração Git. Uma divergência de código, inputs ou conflito exige a validação proporcional afetada.

### Declaração do responsável e alcance operacional

Declaração literal fornecida pelo responsável:

> Eu revisei tudo e autorizo tudo!

O alcance desta declaração é o escopo do pedido identificado acima: atualizar este relatório e seu vínculo de integridade, versionar exclusivamente a correção NB02 e a documentação pertinente, publicar a branch, abrir o PR para master, examinar o diff e os checks disponíveis, corrigir problemas reais de integração, realizar o merge quando atendidas as regras do repositório, sincronizar a referência principal local e incorporar a correção em feat/nb04-cp0 preservando suas mudanças existentes. O checkout isolado da correção e os resultados locais deverão ser preservados.

O escopo de versionamento é fechado nos três arquivos existentes: `src/zeaguard/nb02_native.py`, `tests/test_nb02_native.py` e este relatório. Resultados científicos, manifests de execução e logs seguem as convenções existentes de arquivos ignorados pelo Git. A alteração local de delivery_manifest.json limita se à entrada do hash deste relatório. Os manifests científicos CP3 e CP4 e seus resultados permanecem inalterados.

A autorização registra uma decisão operacional real do responsável. Pareceres humanos adicionais sobre OTHER_TRANSCRIPT, justificativas de concern, aprovações de candidatas e adjudicações continuam dependentes de conteúdo efetivamente emitido por pessoas. A declaração não foi materializada como uma nova decisão APPROVED no registro científico de candidatas.

### Estados científicos preservados e leitura dos registros históricos

1. A revisão computacional independente por agente está registrada como concluída segundo o relato explícito do responsável. Campos como scientific_audit=PENDING_INDEPENDENT_REVIEW em closure_status.json e referências a revisão pendente nas seções anteriores refletem o momento de geração daqueles registros. Seus bytes são preservados. Esta seção registra o evento posterior de revisão e autorização.
2. A revisão humana específica da evidência native permanece pendente, com zero novas candidatas aprovadas. CP5 native permanece incompleto nas condições registradas. A regra de dois a quatro recomendados continua vigente.
3. A manutenção das sete queries NB04 para a finalidade histórica registrada conserva as qualificações da seção anterior. 0351 permanece representante computacional provisório preferido. 0817 permanece identificável como escolha histórica e comparador, com sua posição native fora da Pareto explicitada.
4. GITV01009778.1 permanece IDENTIDADE_BIOLOGICA_UNRESOLVED. Homologia local, identidade biológica, efeito funcional e concern conservam seus significados separados.
5. A integração técnica preserva os históricos, as configurações científicas e o bundle NB04 atual. G0_PASS permanece NOT_DECLARED e CP1 NB04 permanece NOT_STARTED. Não são autorizadas novas buscas, calibração informativa, aquisição de recursos ou resource freeze por este pedido.
6. A incorporação do código e deste registro não declara recomendação final, concern, eficácia ou segurança biológica. Resultados da integração Git, commits, URL do PR, sincronização e hashes documentais finais serão apresentados na entrega operacional correspondente, sem modificar os manifests científicos originais.
