# Diagnóstico — modo `objectiveMode="silva2024"`

Estado da validação contra o benchmark de Silva et al. (2024), instância
`14n-2k-6c-008r_ML_silva2024.json` (`instancias/Petro_instancias/`).

**Este documento é só um registro do estado atual. Nenhum código foi alterado
para produzi-lo. Nenhuma otimização foi rodada.**

## 1. O que já foi implementado (modo `silva2024`, isolado do modo `petrobras`)

Tudo em `metodo_exato_petro` (`metodos.py`), guardado por
`modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"`;
o ramo `petrobras` (`else`) permanece byte-a-byte igual ao que era antes desta
etapa. Leitura de dados nova/adicional em `instancia.py`, mode-agnóstica
(campos zerados/`None` quando ausentes, sem efeito sobre instâncias Petro).

- **Navegação piecewise por navio** (`tempo_navegacao_silva`): `d<=18: d/VL_k`;
  `d>18: 18/VL_k + (d-18)/VH_k`, usando `VL_k`/`VH_k` do próprio navio (não
  mais uma matriz única de um navio de referência).
- **`f1` marginal**: `(FCB-FCA)*hB + (FCN-FCA)*hN + (FCS-FCA)*hDP` (sem
  `FCA*hF`), com `theta=FCA, varphi=FCB, gamma=FCN, delta=FCS` lidos de
  `fuelCost` (USD/h) — não confundido com `fuelConsumption` (m³/h, Petro).
- **Disponibilidade individual por navio (ETR)**: `berco[k] >= AT_k`, sem o
  `max()` com a janela compartilhada do nó-base (que usava o ETR de um único
  navio de referência da frota).
- **TDL como relação F_k−s_k**: `F_k − berco[k] <= tripDurationLimit_k`
  (`s_k = berco[k]`, não `AT_k`), substituindo as três restrições do modo
  Petro (`due_depf` absoluto, `duracao_viagem`, `trip_duration_Fk`) que não
  reproduziam essa semântica.
- **dueTime**: DELIVERY → `inicio_i+servico_i<=dueTime_i`; PICKUP →
  `F_k<=dueTime_i` condicionado à visita (adaptação válida para o caso de uma
  viagem por navio desta instância, sem FIFO/LIFO individual de descarga).
- **Regra "coleta antes de entrega" restrita a DECK** (`pickupDeckBeforeDeliveryDeck`):
  em modo Silva, só `deckCargoLoad` conta como "entrega" para essa ordenação
  (diesel/água não), diferente do modo Petro (que conta os três). Sem essa
  correção a rota publicada de M era estruturalmente inviável no nosso modelo.
- **Disjunção de plataforma entre navios diferentes** (`seq_plat[p,k,l]`):
  impede que dois navios distintos operem a mesma plataforma ao mesmo tempo.
- **Carregamento na base aditivo** (Eq. 11 do artigo): deck+diesel+água
  somados sequencialmente (`hB_saida_seg_k`), sem paralelismo — nunca alterado.
- **Parâmetro de diagnóstico `fixar_rotas`** em `metodo_exato_petro` (fixa
  `x[i,j,k]` para uma rota dada, sem mudar a formulação) — só para testes,
  não faz parte do modelo em produção.
- **`veic.xi = None`**: placeholder criado, **nunca atribuído**. `f2` é
  calculado hoje como `sum_k(F_k-AT_k)` (equivalente a `xi_k=1` implícito,
  **não confirmado** contra o artigo).

## 2. Auditoria de dados — CONCLUÍDA, sem discrepância

O usuário confirmou externamente (arquivo oficial dos autores,
`14n-2k-6c-008r_ML.txt`, via `https://gounaris.cheme.cmu.edu/datasets/psvrp/`)
que o JSON convertido bate com o original em: VL/VH/SP/TDL/ETR de M e L,
eficiências de base (DCP/DCD/DD/WD), eficiências offshore, SET por
plataforma, quantidades, coordenadas, janelas de tempo e deadlines.

**Conclusão: a conversão JSON não é a fonte do problema.** Não há mais
parâmetro de entrada a auditar.

## 3. Evidência numérica reunida (cenários A/B/C, sem alterar formulação)

Definições dos cenários (só variam o tratamento de SP; SET sempre cobrado
quando `ci≠cj`, nunca alterado):
- **A** (literal do artigo): SP em toda mudança de localização, inclusive
  pernas base↔plataforma.
- **B**: SP só entre plataformas offshore, nunca nas pernas com a base.
- **C**: SP nunca entra no cronograma.

| | ARTIGO (Tabela 3) | A | B | C |
|---|---|---|---|---|
| **L f-s** | 31,7 h | 33,7434 h | **31,7034 h** | 31,7034 h |
| **M f-s** | 93,6 h | 97,8027 h | 95,9827 h | 92,0337 h |

- **L**: cenário B (=C, pois a rota de L só tem pernas base-adjacentes)
  reproduz o artigo com diferença de **0,0034h (~12s)** — nível de
  arredondamento.
- **M**: nenhum cenário fecha. B deixa **+2,3827h**; nenhuma remoção
  isolada de um único SET ou SP (testado individualmente, por plataforma/arco)
  fecha esse gap — o mais próximo é remover o SET de PLAT_4 (o único valor
  atípico, 1,42h em vez de 0,67h), que ainda deixa +0,9627h residual.
- Não há espera de janela no cenário B de M (confirmado com `assert` na
  cronologia completa) — a diferença não vem de espera de janela.
- A mesma navegação (Haversine R=6371 + VL/VH por faixa) que reproduz L quase
  exatamente é usada em M — não há evidência de que a métrica de distância
  seja a causa do gap de M.
- Não há, em nenhum arquivo local do repositório, documentação da métrica de
  distância usada pelos autores (busquei por `haversine`, `great circle`,
  `geodesic`, `nautical`, `earth radius`, `coordinate` — nada encontrado além
  do nosso próprio código). O único indício é um comentário em
  `instancia.py:705` afirmando replicar uma função `get_haversine_distance`
  de um C++ que **não existe em nenhum `.cpp`/`.h` deste repositório** —
  afirmação não verificável localmente.

**Decisão (conforme instruído): não calibrar SP, SET, distância, eficiência
ou velocidade para forçar a Tabela 3.** O código permanece exatamente como
estava antes deste diagnóstico.

## 4. Informações que faltam obter do electronic supplement / código dos autores

1. **Regra efetiva de SP nas pernas base↔plataforma**: a equação escrita
   (`T_ijk=N+SP+SE` quando `ci≠cj`) sugere que SP se aplica também saindo/
   voltando da base, mas a Tabela 3 é consistente com SP **não** sendo
   cobrado nessas pernas (evidência forte em L). Precisamos confirmar se há
   uma exceção não documentada na equação principal (ex.: nas restrições
   (26)-(32) ou em uma nota de implementação do Appendix).
2. **Cálculo exato de `Delta_cicj`/distâncias**: confirmar se os autores usam
   Haversine com R=6371km (o que já reproduz L quase exatamente) ou outra
   métrica (grande círculo com outro raio, milha náutica, etc.) — e, mais
   importante, entender por que M não fecha mesmo com essa métrica validada
   contra L.
3. **Definição e valores numéricos de `xi_k`**: o artigo principal (segundo
   você) diz apenas que é "um fator adimensional positivo para favorecer
   PSVs menores" — precisamos da fórmula/tabela real (Appendix ou material
   suplementar), pois hoje `f2` está sem essa ponderação (`xi=1` implícito,
   não confirmado).
4. **Qualquer regra adicional específica de rotas com múltiplas plataformas**:
   como L (1 plataforma) já reproduz o artigo e M (6 plataformas) não, pode
   haver uma regra de continuidade/transição entre plataformas consecutivas
   que não está capturada pelos parâmetros básicos já auditados (ex.: alguma
   penalidade ou isenção específica de SET/SP para plataformas geograficamente
   muito próximas, como PLAT_1↔PLAT_5 a só 4,79km de distância).
5. Confirmar se existe, no material suplementar, uma tabela de cronograma
   detalhada (como a nossa, evento a evento) para pelo menos uma instância
   com múltiplas plataformas — isso permitiria comparar diretamente onde a
   divergência nasce, em vez de testar cenários por hipótese.

## 5. Escopo confirmado — nada alterado

Não alterado nesta etapa nem nas anteriores de diagnóstico: SP definitivo,
SET, distância/navegação, eficiências, serviços, a instância (JSON), modo
Petrobras, Solomon, B&P, pricing, construtivas. Nenhuma otimização foi
executada desde a última rodada válida (fixação de rotas, já reportada).
