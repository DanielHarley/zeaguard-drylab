# Title

`NB03 BicC benchmark: classification of the cause of the 1 nt published length discrepancy`

## Status

`Proposed`

## Decision scope

The 1 nt difference between the body length reported for the BicC dsRNA fragment in the 2022 primary publication and the length of the primer-defined reconstruction used by the project. This record does not touch candidate enumeration, cell formation, Pareto comparison, specificity evidence, exact k-mer counting, non-target organism work, or any delivered sequence.

## Date

`2026-11-13`

## Context / problem

NB03 CP0 reconstructed the published BicC fragment from the primers in the 2022 supplementary table and measured a body of 373 nt against a reported 372 nt, with 403 nt against a reported 402 nt for the amplicon carrying the partial T7 tails. The project froze the status as `UNRESOLVED_PUBLICATION_INCONSISTENCY`, recorded `length_discrepancy_cause_asserted: false`, and `src/zeaguard/nb03_benchmark.py` explicitly declines to promote the non-inclusive count reading, stating that it "is a separate hypothesis, not an explanation, and no value is adjusted".

That classification was correct for the evidence available when it was frozen. The reconstruction was then assessed against the operational transcriptome record, so a count artifact could not be distinguished from a sequence difference between the material the authors amplified and the record the project adopted.

Evidence already present in the repository, and not previously used for this question, now distinguishes those alternatives.

## Question being decided

For the BicC benchmark only, should the non-inclusive count reading be promoted from a non-promoted hypothesis to a recorded cause classified as `inferred/interpreted`, while the operational body remains 373 nt and no value is adjusted?

## Evidence

1. [`data/reference/target_anchor_sequences.fasta`](../../../../data/reference/target_anchor_sequences.fasta), `SHA256 da38253dfdf01e521d20d367129d1e08dcc7b68f5376e0c026b2b93fd83806f5`, holds the four published transcripts. Each header names its source file: `ps6937-sup-0001-Supinfo.txt` for BicC, `S0048357523002833-mmc1.pdf` for dsRNases 1, 2 and 3.
2. The BicC anchor `TRINITY_DN24799_c0_g1_i7` is 2655 nt and is stored antisense to the coding orientation. In the coding orientation, `BicC_Fw` occurs once and the reverse complement of `BicC_Rv` occurs once. The primer-to-primer span is 264 to 636, measuring `636 − 264 + 1 = 373` nt, `SHA256 e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb`.
3. That hash is identical to the delivered comparator `BC-BENCH-0215-0587`. The body the project carries and the body delimited by the same primers inside the authors' own published transcript are the same sequence, with no mismatched position.
4. The same operation on the dsRNase-2 anchor `TRINITY_DN22752_c0_g2_i1`, 1544 nt, gives a primer-to-primer span of 897 to 1226, measuring `1226 − 897 + 1 = 330` nt, `SHA256 97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179`, identical to the delivered comparator `D2-BENCH-0814-1143`.
5. The 2023 supplementary table reports 330 nt for that amplicon and 360 nt with tails. The reconstruction returns 330 and 360. The difference is zero on both measures.
6. The 2022 supplementary table reports 372 nt and 402 nt. The reconstruction returns 373 and 403. The difference is 1 nt on both measures.
7. Both supplementary tables carry the same footnote declaring the 15 nt sequence a partial T7 promoter and giving the canonical 20 nt promoter separately, so the 30 nt difference between body and amplicon is the two tails in both publications.
8. `src/zeaguard/nb03_benchmark.py` lines 41, 303, 305 and 308 hold the frozen position; [`data/reference/nb01_bicc_operational_reference.json`](../../../../data/reference/nb01_bicc_operational_reference.json) records `length_discrepancy_nt: 1`, `length_discrepancy_status: UNRESOLVED_PUBLICATION_INCONSISTENCY` and `length_discrepancy_cause_asserted: false`.

## Evidence classification

| Claim | Category |
| --- | --- |
| The anchor file holds transcripts taken from the named supplements | `directly demonstrated` |
| The BicC anchor is antisense to the coding orientation and contains both primer sites exactly once | `derived/computed` |
| The primer-to-primer span inside the published BicC transcript measures 373 nt | `derived/computed` |
| The anchor-derived body is byte identical to the delivered comparator, for both targets | `derived/computed` |
| The dsRNase-2 reconstruction reproduces the published 330 and 360 exactly | `derived/computed` |
| The reported 372 arises from a count equal to `end − start` over the primer-defined span | `inferred/interpreted` |
| The counting procedure the 2022 authors actually applied | `unresolved` |
| Whether the discrepancy has any biological meaning | `unresolved` |

## Alternatives considered

1. **Retain `cause_asserted: false` unchanged.** Defensible, and it remains the correct record of what the sources state. It is rejected as the final classification because it leaves at `unresolved` a reading that is now testable inside the authors' own published sequence, which under-classifies the available evidence rather than over-classifying it.
2. **Treat 372 as correct and the reconstruction as defective.** Rejected. The span is delimited by the published primers inside the published transcript; no inclusive count of that span yields 372.
3. **Attribute the difference to a sequence difference between the amplified material and the project reference.** Rejected. The anchor-derived body and the operational reconstruction are identical, so no sequence difference exists over the span.
4. **Attribute the difference to a counting convention used throughout by the same group.** Rejected. The 2023 fragment, same group and same supplementary table format, reproduces exactly on both measures.
5. **Promote the reading to a cause classified as `inferred/interpreted`, scoped to BicC, with no value adjusted.** Adopted.

## Decision

1. The 1 nt discrepancy in the BicC benchmark is recorded with a cause classified as `inferred/interpreted`: a reported length equal to `end − start` over the primer-defined span, propagated to the amplicon figure.
2. The operational body remains **373 nt** and the amplicon with tails remains **403 nt**. No published value is rewritten and no project value is adjusted.
3. The classification is `inferred/interpreted` and must never be rendered as `directly demonstrated`. The procedure the authors applied remains `unresolved`.
4. Scope is the BicC benchmark. The dsRNase-2 benchmark has no discrepancy and this record makes no claim about it beyond its use as a control.
5. Implementation in code and in the pinned reference record is **deferred** and does not accompany this decision. Until it is carried out, `nb03_benchmark.py` and `nb01_bicc_operational_reference.json` continue to carry the superseded classification. That divergence is deliberate and is recorded here so it is not read as an inconsistency.

## Rationale

When the position was frozen, the reconstruction could only be compared with the operational transcriptome record, so a counting artifact and a sequence difference were indistinguishable and `unresolved` was the weakest category the evidence supported. The anchors remove the sequence-difference alternative, because the published transcript and the project reference agree exactly over the span. The dsRNase-2 reconstruction removes the group-convention alternative, because the same group and the same table format reproduce exactly on both body and amplicon. What remains is an arithmetic reading that the sources neither state nor contradict, which is the definition of `inferred/interpreted` under this directory's evidence discipline.

## Consequences

- No analysis is invalidated and no execution is required. Candidate enumeration, cell formation, Pareto comparison, specificity evidence, exact 19 and 21 nt counting, and non-target organism preparation are untouched, because none of them consumes the reported published length.
- No delivered sequence changes. All seven handoff hashes remain valid.
- Documents that circulate outside the team may state the reading, provided they carry its classification as an interpretation of this project and not an assertion by the authors.
- A later implementation record must update `nb03_benchmark.py` and the pinned reference together, and must keep `length_discrepancy_status` meaningful rather than silently setting it to `NONE`, because the published and reconstructed values still differ.
- Until that implementation, any consistency check comparing the report against the pinned artifact will show this divergence. It is expected.

## Limitations

- No source declares the counting procedure. The cause is an inference and is classified as such.
- The anchor sequences were extracted by the project from the supplements. The extraction is recorded in the FASTA headers. **Amended 2026-11-13, same day as this record:** the `Dmai-BicC` record of the 2022 Appendix S1 was supplied by the Dry Lab lead, transcribed, and found to reproduce the stored BicC anchor exactly, 2655 nt, sequence `SHA256 da59dc63fbf8022eaec9f89fa3f644ac1860b2625a0f1bd0b666ff22ef37977b`. It is retained at `data/external/nb03_cp0_sources/dalaison2022_supinfo_s1/` with its own provenance record. This confirms that the project anchor reproduces the published record, and because the agreement is a hash match over the full 2655 nt, transcription error is excluded. Byte level fidelity to the publisher's own file is not established and is immaterial here, since this decision rests on sequence and not on file bytes. The other five records of Appendix S1, `Dmai-Act1`, `Dmai-Dcr2`, `Dmai-Ago2`, `Dmai-R2D2` and `Dmai-Sid1`, are **out of scope by decision of the Dry Lab lead on 2026-11-13**: no project artifact derives from them and none is used by this record.
- The comparison is of nucleotide sequence only. It establishes nothing about what the authors physically synthesised or administered.
- The anchors are single assembled contigs. They carry no information about population variation or isoforms.

## What this decision does NOT establish

- It does not establish the intent, procedure, or correctness of the 2022 authors.
- It does not validate the benchmark biologically, nor its activity, nor its suitability as a candidate.
- It does not alter the identity status of the records compatible with dsRNase-2, which remains governed by ADR 0004 and remains open.
- It does not bear on specificity, off-target assessment, ecological safety, or efficacy.
- It does not authorise adjusting, rounding, or restating any published figure.

## Falsification / revision conditions

- A primary source, corrigendum, or author statement declaring the counting procedure.
- A different published version of the BicC transcript in which the primer-to-primer span does not measure 373 nt.
- Evidence that the anchor extraction mis-transcribed the supplement, which would require re-deriving the anchor from the retained source before any conclusion.
- ~~Retention of `ps6937-sup-0001-Supinfo.txt`, which would upgrade the auditability of the BicC anchor.~~ **Met and closed on 2026-11-13** by the transcribed and hash-verified `Dmai-BicC` record described under Limitations. A byte-preserved copy obtained later from the publisher would add file level fidelity without altering the sequence evidence, and would not by itself require revision of this decision.

## Related notebook

`not applicable`

## Related dataset / artifact

`data/reference/target_anchor_sequences.fasta`, `data/reference/nb01_bicc_operational_reference.json`, `data/external/nb03_cp0_sources/dalaison2022_table_s1/ps6937-sup-0006-tables1.docx`, `data/external/Dalaison-Fuentes2023_S1_mmc1.pdf`, `src/workstreams/bioinformatics/handoffs/2026-11-04_wetlab_dsrna_v1.fasta`

## Related Issue

`not recoverable`

## Related PR

`not recoverable`

## Related commits

`not yet committed`

## Provenance

Recorded retrospectively on 2026-11-13 by an automated assistant at the request of the Dry Lab lead, who retains the bibliographic decision. Evidence inspected: the anchor FASTA and its headers; the delivered handoff FASTA; the BicC and dsRNase-2 operational reference records; `src/zeaguard/nb03_benchmark.py`; the 2022 supplementary primer table; the 2023 supplementary table; and the 2022 article Methods section 2.4. The primer-to-primer cuts, lengths, and hashes reported here were recomputed from the FASTA files for this record. No analysis was re-executed and no code was modified.

# Versão em PTBR

# Título

`NB03 comparador de BicC: classificação da causa da diferença de 1 nt no comprimento publicado`

## Estado

`Proposed`

## Escopo da decisão

A diferença de 1 nt entre o comprimento de corpo reportado para o fragmento de dsRNA de BicC na publicação primária de 2022 e o comprimento da reconstrução definida pelos primers adotada pelo projeto. Este registro não toca enumeração de candidatas, formação de células, comparação de Pareto, evidência de especificidade, contagem exata de k-mers, trabalho com organismos não alvo, nem qualquer sequência entregue.

## Data

`2026-11-13`

## Contexto / problema

O NB03 CP0 reconstruiu o fragmento publicado de BicC a partir dos primers da tabela suplementar de 2022 e mediu um corpo de 373 nt contra os 372 nt reportados, e 403 nt contra os 402 nt reportados para o amplicon com as caudas T7 parciais. O projeto congelou o estado como `UNRESOLVED_PUBLICATION_INCONSISTENCY`, registrou `length_discrepancy_cause_asserted: false`, e `src/zeaguard/nb03_benchmark.py` recusa explicitamente promover a leitura de contagem não inclusiva, declarando que ela "é uma hipótese separada, não uma explicação, e nenhum valor é ajustado".

Essa classificação estava correta para a evidência disponível quando foi congelada. A reconstrução era então avaliada contra o registro operacional do transcriptoma, de modo que um artefato de contagem não podia ser distinguido de uma diferença de sequência entre o material que os autores amplificaram e o registro que o projeto adotou.

Evidência já presente no repositório, e não utilizada antes para esta questão, agora distingue essas alternativas.

## Questão sendo decidida

Somente para o comparador de BicC, a leitura de contagem não inclusiva deve ser promovida de hipótese não promovida a causa registrada e classificada como `inferido/interpretado`, mantendo o corpo operacional em 373 nt e sem ajustar nenhum valor?

## Evidências

1. [`data/reference/target_anchor_sequences.fasta`](../../../../data/reference/target_anchor_sequences.fasta), `SHA256 da38253dfdf01e521d20d367129d1e08dcc7b68f5376e0c026b2b93fd83806f5`, guarda os quatro transcritos publicados. Cada cabeçalho nomeia seu arquivo de origem: `ps6937-sup-0001-Supinfo.txt` para BicC e `S0048357523002833-mmc1.pdf` para as dsRNases 1, 2 e 3.
2. A âncora de BicC `TRINITY_DN24799_c0_g1_i7` tem 2655 nt e está guardada em sentido antissenso ao codificante. No sentido codificante, `BicC_Fw` ocorre uma única vez e o complemento reverso de `BicC_Rv` ocorre uma única vez. O intervalo primer a primer é 264 a 636, medindo `636 − 264 + 1 = 373` nt, `SHA256 e866ebd114008e708e962704b4424dbbd633e8f1da0895a68afcd619660053fb`.
3. Esse hash é idêntico ao do comparador entregue `BC-BENCH-0215-0587`. O corpo que o projeto carrega e o corpo delimitado pelos mesmos primers dentro do transcrito publicado pelos próprios autores são a mesma sequência, sem uma única posição divergente.
4. A mesma operação na âncora de dsRNase-2 `TRINITY_DN22752_c0_g2_i1`, de 1544 nt, dá o intervalo primer a primer 897 a 1226, medindo `1226 − 897 + 1 = 330` nt, `SHA256 97d39c22ae297e91d62c40d7b9afa6530822e111914dbb1bb0013b8be92dc179`, idêntico ao comparador entregue `D2-BENCH-0814-1143`.
5. A tabela suplementar de 2023 reporta 330 nt para esse amplicon e 360 nt com caudas. A reconstrução devolve 330 e 360. A diferença é zero nas duas medidas.
6. A tabela suplementar de 2022 reporta 372 nt e 402 nt. A reconstrução devolve 373 e 403. A diferença é de 1 nt nas duas medidas.
7. As duas tabelas suplementares trazem a mesma nota de rodapé declarando a sequência de 15 nt como promotor T7 parcial e informando à parte o promotor canônico de 20 nt, de modo que os 30 nt entre corpo e amplicon são as duas caudas nas duas publicações.
8. `src/zeaguard/nb03_benchmark.py`, linhas 41, 303, 305 e 308, guarda a posição congelada; [`data/reference/nb01_bicc_operational_reference.json`](../../../../data/reference/nb01_bicc_operational_reference.json) registra `length_discrepancy_nt: 1`, `length_discrepancy_status: UNRESOLVED_PUBLICATION_INCONSISTENCY` e `length_discrepancy_cause_asserted: false`.

## Classificação das evidências

| Afirmação | Categoria |
| --- | --- |
| O arquivo de âncoras guarda transcritos extraídos dos suplementares nomeados | `diretamente demonstrado` |
| A âncora de BicC é antissenso ao codificante e contém os dois sítios de primer uma única vez | `derivado/computado` |
| O intervalo primer a primer dentro do transcrito publicado de BicC mede 373 nt | `derivado/computado` |
| O corpo derivado da âncora é idêntico byte a byte ao comparador entregue, nos dois alvos | `derivado/computado` |
| A reconstrução de dsRNase-2 reproduz exatamente os 330 e 360 publicados | `derivado/computado` |
| Os 372 reportados resultam de contagem igual a `fim − início` sobre o intervalo definido pelos primers | `inferido/interpretado` |
| O procedimento de contagem efetivamente aplicado pelos autores de 2022 | `não resolvido` |
| Se a diferença tem algum significado biológico | `não resolvido` |

## Alternativas consideradas

1. **Manter `cause_asserted: false` inalterado.** Defensável, e continua sendo o registro correto do que as fontes declaram. É rejeitada como classificação final porque deixa em `não resolvido` uma leitura agora testável dentro da sequência publicada pelos próprios autores, o que subclassifica a evidência disponível em vez de superclassificá-la.
2. **Tratar 372 como correto e a reconstrução como defeituosa.** Rejeitada. O intervalo é delimitado pelos primers publicados dentro do transcrito publicado; nenhuma contagem inclusiva desse intervalo produz 372.
3. **Atribuir a diferença a uma diferença de sequência entre o material amplificado e a referência do projeto.** Rejeitada. O corpo derivado da âncora e a reconstrução operacional são idênticos, logo não há diferença de sequência no intervalo.
4. **Atribuir a diferença a uma convenção de contagem usada sistematicamente pelo mesmo grupo.** Rejeitada. O fragmento de 2023, do mesmo grupo e no mesmo formato de tabela suplementar, reproduz exatamente nas duas medidas.
5. **Promover a leitura a causa classificada como `inferido/interpretado`, restrita a BicC, sem ajustar nenhum valor.** Adotada.

## Decisão

1. A diferença de 1 nt no comparador de BicC passa a ser registrada com causa classificada como `inferido/interpretado`: comprimento reportado igual a `fim − início` sobre o intervalo definido pelos primers, propagado à cifra do amplicon.
2. O corpo operacional permanece em **373 nt** e o amplicon com caudas permanece em **403 nt**. Nenhum valor publicado é reescrito e nenhum valor do projeto é ajustado.
3. A classificação é `inferido/interpretado` e nunca deve ser apresentada como `diretamente demonstrado`. O procedimento aplicado pelos autores permanece `não resolvido`.
4. O escopo é o comparador de BicC. O comparador de dsRNase-2 não apresenta diferença e este registro não faz afirmação sobre ele além de seu uso como controle.
5. A implementação no código e no registro de referência fixado fica **adiada** e não acompanha esta decisão. Até que seja feita, `nb03_benchmark.py` e `nb01_bicc_operational_reference.json` continuam carregando a classificação superada. Essa divergência é deliberada e fica registrada aqui para não ser lida como inconsistência.

## Justificativa

Quando a posição foi congelada, a reconstrução só podia ser comparada ao registro operacional do transcriptoma, de modo que um artefato de contagem e uma diferença de sequência eram indistinguíveis, e `não resolvido` era a categoria mais fraca que a evidência sustentava. As âncoras eliminam a alternativa de diferença de sequência, porque o transcrito publicado e a referência do projeto coincidem exatamente no intervalo. A reconstrução de dsRNase-2 elimina a alternativa de convenção do grupo, porque o mesmo grupo e o mesmo formato de tabela reproduzem exatamente no corpo e no amplicon. O que resta é uma leitura aritmética que as fontes não declaram nem contradizem, que é a definição de `inferido/interpretado` sob a disciplina de evidências deste diretório.

## Consequências

- Nenhuma análise é invalidada e nenhuma execução é exigida. Enumeração de candidatas, formação de células, comparação de Pareto, evidência de especificidade, contagem exata de 19 e 21 nt e preparação de organismos não alvo ficam intocadas, porque nenhuma delas consome o comprimento publicado.
- Nenhuma sequência entregue muda. Os sete hashes do handoff permanecem válidos.
- Documentos que circulam fora da equipe podem declarar a leitura, desde que carreguem sua classificação como interpretação deste projeto e não como afirmação dos autores.
- Um registro de implementação posterior deve atualizar `nb03_benchmark.py` e a referência fixada em conjunto, e deve manter `length_discrepancy_status` significativo em vez de simplesmente defini-lo como `NONE`, porque o valor publicado e o reconstruído continuam diferentes.
- Até essa implementação, qualquer conferência de consistência entre o relatório e o artefato fixado vai mostrar essa divergência. Ela é esperada.

## Limitações

- Nenhuma fonte declara o procedimento de contagem. A causa é uma inferência e está classificada como tal.
- As sequências âncora foram extraídas pelo projeto a partir dos suplementares. A extração está registrada nos cabeçalhos do FASTA. **Emendado em 2026-11-13, no mesmo dia deste registro:** o registro `Dmai-BicC` do Apêndice S1 de 2022 foi fornecido pelo responsável pelo Dry Lab, transcrito, e reproduz exatamente a âncora de BicC armazenada, 2655 nt, `SHA256` da sequência `da59dc63fbf8022eaec9f89fa3f644ac1860b2625a0f1bd0b666ff22ef37977b`. Está retido em `data/external/nb03_cp0_sources/dalaison2022_supinfo_s1/` com registro de proveniência próprio. Isso confirma que a âncora do projeto reproduz o registro publicado e, como a coincidência é um hash sobre os 2655 nt inteiros, erro de transcrição fica excluído. A fidelidade byte a byte ao arquivo da própria editora não está estabelecida e é irrelevante aqui, já que esta decisão se apoia em sequência e não em bytes de arquivo. Os outros cinco registros do Apêndice S1, `Dmai-Act1`, `Dmai-Dcr2`, `Dmai-Ago2`, `Dmai-R2D2` e `Dmai-Sid1`, estão **fora de escopo por decisão do responsável pelo Dry Lab em 2026-11-13**: nenhum artefato do projeto deriva deles e nenhum é usado por este registro.
- A comparação é apenas de sequência nucleotídica. Não estabelece nada sobre o que os autores sintetizaram ou administraram fisicamente.
- As âncoras são contigs montados únicos. Não carregam informação sobre variação populacional ou isoformas.

## O que esta decisão NÃO estabelece

- Não estabelece a intenção, o procedimento ou a correção dos autores de 2022.
- Não valida o comparador biologicamente, nem sua atividade, nem sua adequação como candidata.
- Não altera o estado de identidade dos registros compatíveis com dsRNase-2, que permanece governado pelo ADR 0004 e continua em aberto.
- Não tem relação com especificidade, avaliação de off-target, segurança ecológica ou eficácia.
- Não autoriza ajustar, arredondar ou reescrever qualquer cifra publicada.

## Condições de falseamento / revisão

- Uma fonte primária, errata ou declaração de autor informando o procedimento de contagem.
- Uma versão publicada diferente do transcrito de BicC em que o intervalo primer a primer não meça 373 nt.
- Evidência de que a extração da âncora transcreveu o suplementar incorretamente, o que exigiria rederivar a âncora a partir da fonte retida antes de qualquer conclusão.
- ~~Retenção do `ps6937-sup-0001-Supinfo.txt`, o que elevaria a auditabilidade da âncora de BicC.~~ **Atendida e encerrada em 2026-11-13** pelo registro `Dmai-BicC` transcrito e verificado por hash descrito em Limitações. Uma cópia com bytes preservados obtida depois junto à editora acrescentaria fidelidade de arquivo sem alterar a evidência de sequência, e não exigiria por si só revisão desta decisão.

## Notebook relacionado

`não aplicável`

## Dataset / artefato relacionado

`data/reference/target_anchor_sequences.fasta`, `data/reference/nb01_bicc_operational_reference.json`, `data/external/nb03_cp0_sources/dalaison2022_table_s1/ps6937-sup-0006-tables1.docx`, `data/external/Dalaison-Fuentes2023_S1_mmc1.pdf`, `src/workstreams/bioinformatics/handoffs/2026-11-04_wetlab_dsrna_v1.fasta`

## Issue relacionada

`não recuperável`

## PR relacionado

`não recuperável`

## Commits relacionados

`ainda não commitado`

## Proveniência

Registrado retrospectivamente em 2026-11-13 por assistente automatizado a pedido do responsável pelo Dry Lab, que retém a decisão bibliográfica. Evidências inspecionadas: o FASTA de âncoras e seus cabeçalhos; o FASTA de entrega do handoff; os registros de referência operacional de BicC e dsRNase-2; `src/zeaguard/nb03_benchmark.py`; a tabela suplementar de primers de 2022; a tabela suplementar de 2023; e a seção 2.4 de Métodos do artigo de 2022. Os cortes primer a primer, comprimentos e hashes aqui reportados foram recomputados a partir dos arquivos FASTA para este registro. Nenhuma análise foi reexecutada e nenhum código foi modificado.
