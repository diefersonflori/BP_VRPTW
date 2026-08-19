# Diagnóstico complementar — Reprodução da Tabela 3 (Silva et al., 2024)

Complementa `DIAGNOSTICO_SILVA2024.md` (não o altera). Registra especificamente
a tentativa de reprodução da **Tabela 3** do artigo para a instância
`14n-2k-6c-008r_ML` (`14n-2k-6c-008r_ML_silva2024.json`,
`instancias/Petro_instancias/`).

**Este documento é só um registro do estado atual.** Os números abaixo vêm
de scripts de diagnóstico já executados (`_teste_reproduzir_tabela3_silva.py`,
`_teste_auditoria_temporal_silva.py`, `_teste_distancia_silva.py`). Nenhuma
calibração foi aplicada para forçar a tabela a bater.

## 1. Objetivo do diagnóstico

Reproduzir a Tabela 3 do artigo para a instância `14n-2k-6c-008r_ML`,
comparando, para cada PSV e cada `alpha`:

- `s_artigo = B_k` (instante em que o PSV começa o serviço de carregamento
  na base);
- `f_artigo = F_k` (instante em que a rota está completamente concluída);
- `f - s = F_k - B_k`.

A comparação usa as **rotas publicadas fixas** (via `fixar_rotas` em
`metodo_exato_petro`), deixando o Gurobi resolver só o cronograma — nunca a
escolha de rotas.

A intenção inicial **não era calibrar** o modelo para bater com a tabela,
e sim identificar precisamente as diferenças entre:

- a formulação implementada (`objectiveMode="silva2024"` em
  `metodo_exato_petro`/`avaliar_rota_silva2024`);
- a instância original dos autores;
- os resultados publicados na Tabela 3.

## 2. Dados originais

- O arquivo original dos autores usado como referência é
  `transformador_instancias_silva/arquivosconvertersilva/14n-2k-6c-008r_ML.txt`.
- As coordenadas LAT/LON do JSON de produção
  (`instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json`, campos
  `latitude`/`longitude` de `ordersData` e `supplyBasesData`) foram
  auditadas diretamente contra esse `.txt` (script
  `_teste_distancia_silva.py`, seção 1 do seu output).
- **Os valores coincidem exatamente** — nenhuma coordenada real/corrigida
  de Macaé foi usada em nenhuma etapa do pipeline atual (nem na conversão
  `transformador_instancias_silva.py`, que só copia LAT/LON do `.txt` para
  o JSON, nem na leitura em produção).

Coordenada original da base (mantida sem alteração, para preservar o
benchmark):

```
LAT = -21.830
LON = -41.770
```

## 3. Valores da Tabela 3

Valores publicados usados como alvo de comparação:

| alpha | PSV | AT | s | f | f-s |
|---|---|---|---|---|---|
| 0.00 / 0.25 | M | 7.0 | 7.0 | 100.6 | 93.6 |
| 0.00 / 0.25 | L | 0.8 | 0.8 | 32.5 | 31.7 |
| 0.50 | M | 7.0 | 7.3 | 100.7 | 93.4 |
| 0.50 | L | 0.8 | 0.8 | 32.5 | 31.7 |
| 0.75 | M | 7.0 | 12.2 | 100.7 | 88.5 |
| 0.75 | L | 0.8 | 0.8 | 35.2 | 34.4 |
| 1.00 | M | 7.0 | 20.1 | 108.6 | 88.5 |
| 1.00 | L | 0.8 | 0.8 | 35.2 | 34.4 |

Rotas publicadas usadas (nós internos, order Silva 0..13 → nó = order+1;
base inicial = 0, base final = 15):

```python
ROTAS_TABELA3 = {
    0.00: {0: [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15], 1: [0, 10, 15]},
    0.25: {0: [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15], 1: [0, 10, 15]},
    0.50: {0: [0, 8, 9, 5, 2, 4, 3, 6, 7, 13, 11, 12, 14, 1, 15], 1: [0, 10, 15]},
    0.75: {0: [0, 1, 4, 2, 3, 6, 7, 13, 11, 14, 12, 5, 15], 1: [0, 10, 8, 9, 15]},
    1.00: {0: [0, 5, 7, 6, 11, 14, 13, 12, 4, 2, 3, 1, 15], 1: [0, 10, 8, 9, 15]},
}
```

## 4. Correção do validador pós-hoc

Bug encontrado: o validador Petrobras (`validar_ordem_plataformas_petro` em
`avaliador_rota.py`, usado por `metodo_exato_petro` para checagem
operacional pós-Gurobi) tratava `dieselLoad`/`waterLoad` como "entregas" que
bloqueavam um pickup (`deckCargoBackload`) subsequente na mesma plataforma.
Para o modo Silva isso está incorreto: a Eq. (21) do artigo só exige
precedência pickup→delivery entre produtos do **mesmo compartimento**
(`deckSpace`), e diesel/água usam tanques próprios (`dieselTanks`/
`waterTanks`).

Correção aplicada: criada `validar_ordem_plataformas_silva2024` em
`avaliador_rota.py`, com precedência restrita ao compartimento de deck —
`deckCargoBackload` deve preceder `deckCargoLoad` quando necessário na
mesma plataforma; `dieselLoad`/`waterLoad` **não** bloqueiam um pickup de
deck. `validar_cargas_petro` (mesmo arquivo) e
`Solucao.ordem_plataformas_petro_valida` (`solucao.py`) passaram a rotear
por `inst.objective_mode`:

```python
if inst.objective_mode == "silva2024":
    validar_ordem_plataformas_silva2024(...)
else:
    validar_ordem_plataformas_petro(...)   # inalterado
```

O validador Petrobras original **não foi alterado** (ramo `else`,
byte-a-byte igual). Efeito confirmado: rotas M publicadas de alpha=0.75 e
1.00, antes rejeitadas com `motivo=coleta_apos_entrega_no_4` /
`viavel_cargas_petro_rejeitou`, passaram a ser aceitas pela validação
pós-hoc (`sol.exato_petro_consistente=True`), sem nenhuma rejeição
remanescente.

## 5. Investigação do SP na saída da base

Foi adicionado o parâmetro de diagnóstico `silva_sp_arcos_base` (default
`True`) a `metodo_exato_petro`, `avaliar_rota_silva2024` e
`custo_rota_silva2024`, e comparados dois cenários:

- `SP_SAIDA_BASE_SIM` (`silva_sp_arcos_base=True`);
- `SP_SAIDA_BASE_NAO` (`silva_sp_arcos_base=False`).

**Importante**: nenhum dos dois cenários deve ser chamado de "formulação
literal". Foi descoberto, ao investigar `tempo_arco` (`metodos.py`) e o
`tempo_arco` equivalente em `avaliar_rota_silva2024`, que o código
histórico **já não cobrava SP (nem SET) na perna plataforma→base** (o
retorno à base), em nenhum dos dois cenários — isso nunca foi alterado
nesta etapa. A única diferença efetiva entre `SP_SAIDA_BASE_SIM` e
`SP_SAIDA_BASE_NAO` é a perna **base → primeira plataforma**, que carrega
SP (além do SET, sempre cobrado) apenas no cenário `SIM`.

O `DEFAULT` do código de produção continua `silva_sp_arcos_base=True`.
Nenhum chamador existente (B&P: `preparar_pool_silva2024` e os demais
pontos que chamam `avaliar_rota_silva2024`/`custo_rota_silva2024`) passa
esse argumento — todos continuam usando o default `True`, sem qualquer
mudança de comportamento. O B&P **não foi alterado**.

## 6. Resultados com `SP_SAIDA_BASE_NAO`

**alpha=0.00 / 0.25:**

| PSV | modelo F-B | artigo | resíduo |
|---|---|---|---|
| M | 95.9827 h | 93.6 h | **+2.3827 h** |
| L | 31.7034 h | 31.7 h | **+0.0034 h** |

O PSV **L reproduz a Tabela 3 praticamente exatamente** (diferença ao
nível de arredondamento da tabela publicada, que só tem 1 casa decimal).

**alpha=0.50:**

| PSV | modelo F-B | artigo | resíduo |
|---|---|---|---|
| M | 96.3313 h | 93.4 h | **+2.9313 h** |

A rota de M em alpha=0.50 **permanece inviável para `tripDurationLimit=96h`**
no nosso modelo (status Gurobi `INF_OR_UNBD`, confirmado por IIS: a
restrição `tdl_silva_Fk_menos_sk_0` está no núcleo de infeasibilidade,
junto com a fixação de arcos da rota). Isso **não foi corrigido
artificialmente** — nem relaxando o TDL, nem alterando SP/SET/distância.

## 7. Auditoria temporal arco a arco

Script criado: `_teste_auditoria_temporal_silva.py`. Todos os cross-checks
numéricos entre três fontes independentes — o próprio script (recálculo
arco a arco), `avaliar_rota_silva2024` (cronologia oficial) e
`metodo_exato_petro`/Gurobi (quando viável) — **fecharam a ~1e-14**
(erro de ponto flutuante), tanto para alpha=0 quanto para alpha=0.50.

Não foram encontrados:

- SET duplicado;
- SP duplicado;
- serviço duplicado;
- espera de janela inesperada;
- descarga de backload inesperada;
- nenhuma diferença entre o cálculo de `avaliar_rota_silva2024` e o de
  `metodo_exato_petro`/Gurobi para as rotas viáveis.

Espera offshore de M:

```
alpha=0.00:  espera = 0.0000 h
alpha=0.50:  espera = 0.0000 h
```

O navio nunca esperou por janela em nenhum nó da rota M, em nenhum dos
dois casos.

Confirmado que a decomposição fecha exatamente (diferença < 1e-6 em todas
as linhas viáveis):

```
F - B = base_loading (hB_saida)
      + hN (navegação pura)
      + SP
      + SET
      + serviço_offshore
      + espera
      + base_unloading (hB_retorno)
```

## 8. Mesma plataforma

Para os blocos de plataforma da rota M (nomeados por `(orders_silva)_plataforma`):

```
(7,8)_5
(1,3,2)_2
(5,6)_4
(12,13,10,11)_6
```

confirmado explicitamente (seção 9 do output de
`_teste_auditoria_temporal_silva.py`, para alpha=0 e alpha=0.50):

- SET cobrado **uma única vez** ao entrar na plataforma;
- SP cobrado **uma única vez** ao entrar na plataforma;
- navegação = 0 entre orders da mesma plataforma;
- SP = 0 entre orders da mesma plataforma;
- SET = 0 entre orders da mesma plataforma;
- cada order mantém seu próprio tempo de serviço (por `commodity`/eficiência).

Logo, a diferença com a Tabela 3 **não vem de duplicação interna** nesses
blocos.

## 9. Isolamento da diferença entre alpha=0 e alpha=0.50

Observação central desta investigação:

**Nosso modelo:**

```
alpha=0.00:  F-B = 95.9827 h
alpha=0.50:  F-B = 96.3313 h
diferença:   +0.348579 h
```

**Tabela 3:**

```
alpha=0.00:  93.6 h
alpha=0.50:  93.4 h
diferença:   -0.2 h
```

As duas rotas de M (alpha=0 e alpha=0.50) atendem:

- os mesmos 13 pedidos (orders);
- as mesmas 6 plataformas;
- o mesmo loading (carregamento na base);
- o mesmo unloading (descarga na base);
- o mesmo serviço total offshore;
- o mesmo SET total;
- o mesmo SP total;
- espera = 0 em ambas.

Portanto, **dentro do nosso modelo**, a diferença entre as duas rotas vem
exclusivamente da navegação (hN) — confirmado na seção 8 do output de
`_teste_auditoria_temporal_silva.py` (comparação lado a lado dos
componentes).

## 10. Arcos críticos

Sequências de plataformas:

```
alpha=0.00:   BASE-P1-P5-P3-P2-P4-P6-BASE
alpha=0.50:   BASE-P5-P3-P2-P4-P6-P1-BASE
```

Os arcos comuns às duas sequências se cancelam. Sobram, exclusivos de cada
rota:

```
alpha=0.00:              alpha=0.50:
  BASE-P1                  BASE-P5
  P1-P5                    P6-P1
  P6-BASE                  P1-BASE
```

## 11. Distâncias e tempos Haversine

Calculados com Haversine clássico (`R=6371 km`), coordenadas lidas
diretamente do `.txt` original, PSV M com VL/VH/threshold originais
(VL=9.4 km/h, VH=12.7 km/h, threshold=18.0 km) — script
`_teste_distancia_silva.py`.

| arco | distância (km) | tempo (h) |
|---|---|---|
| BASE-P1 | 167.752615 | 13.706438 |
| P1-P5 | 4.794411 | 0.510044 |
| P6-BASE | 192.690625 | 15.670061 |
| BASE-P5 | 171.951728 | 14.037077 |
| P6-P1 | 25.324256 | 2.491607 |
| P1-BASE | 167.752615 | 13.706438 |

Somatórios:

```
alpha=0.00:                29.886543 h
alpha=0.50:                30.235122 h
diferença do nosso modelo: +0.348579 h
diferença implícita na Tabela 3: -0.2 h
diferença entre essas diferenças: +0.548579 h
```

## 12. Evidência sobre a métrica de distância

Com as coordenadas **originais** da instância (auditadas, sem correção),
nosso Haversine gera uma relação entre as duas sequências de navegação com
**sinal oposto** ao implícito pela Tabela 3: nosso modelo diz que a rota de
alpha=0.50 navega **mais** que a de alpha=0 (+0.348579h), enquanto a
Tabela 3 implica que ela deveria ser **mais curta** em 0.2h.

Isso é evidência de que a métrica/regra usada para `Delta_cicj` pelos
autores **pode** diferir da nossa (Haversine R=6371 clássico).

**Porém**: não está provado que todo o resíduo absoluto de M (+2.3827h em
alpha=0) venha da distância — só está isolado que a *diferença entre as
duas rotas* (+0.348579h vs -0.2h esperado) vem exclusivamente da
navegação, já que todos os outros componentes (loading, unloading, serviço,
SET, SP, espera) são idênticos entre as duas rotas. Não afirmar mais do
que os dados permitem.

## 13. Busca pela regra dos autores

Busca realizada (script `_teste_distancia_silva.py`, seção 5, mais
exploração manual do repositório):

- arquivo original dos autores (`14n-2k-6c-008r_ML.txt`) — só fornece
  LAT/LON por cliente, nenhuma distância pré-calculada, nenhuma nota de
  fórmula;
- `README_TRANSFORMADOR_SILVA.txt` e demais READMEs do repositório;
- todos os arquivos `.cpp`/`.h` do repositório, incluindo cópias em
  `PD_PARA_PYTHON/`, `PD_PARA_PYTHON - Copia/`,
  `TalvezSejaUmTestenovamente/` e `.claude/worktrees/` — nenhum contém
  código relacionado a latitude/longitude/distância geográfica (tratam de
  outra parte do sistema: B&P/pricing);
- busca textual (case-insensitive, repositório inteiro) pelos termos:
  `distance`, `haversine`, `great circle`, `latitude`, `longitude`,
  `Delta`, `get_distance`, `geodesic`, `nautical`, `earth radius`,
  `spherical`, `UTM`, `vincenty`, `geopy`, `6371`.

Resultado: nenhuma implementação da conversão LAT/LON → `Delta_cicj` foi
encontrada em nenhum material disponível localmente. `get_haversine_distance`
(nome citado em comentário de `instancia.py`) não existe em nenhum `.cpp`/`.h`
do repositório — só no próprio comentário e no `DIAGNOSTICO_SILVA2024.md`.

Conclusão, registrada literalmente:

> "A regra de conversão LAT/LON -> Delta não está documentada no material
> disponível."

Não foi inventada nenhuma fórmula alternativa.

## 14. Xi ainda desconhecido

A função objetivo do artigo usa:

```
f2 = sum_k xi_k * (F_k - AT_k)
```

Os valores originais de `xi_k` (fator adimensional para favorecer PSVs
menores, segundo o texto do artigo) ainda não foram identificados em
nenhum material disponível. Atualmente o código usa `xi=1` **PROVISÓRIO**
(`veic.xi` existe como atributo placeholder, nunca atribuído).

Portanto, **ainda não podemos afirmar reprodução da função objetivo
completa nem das soluções ótimas do artigo para alpha>0** — só a
reprodução temporal de rotas fixas foi investigada até aqui.

## 15. Consequência para o B&P

- O B&P Silva (branch-and-price com `objective_mode="silva2024"`) já
  reproduziu corretamente a geração de colunas da versão implementada.
- O LB da raiz (~115.919547, valor de referência usado em
  `_teste_etapa17_arvore_bp_silva.py` como `LB_RAIZ_ESPERADO`) foi
  reproduzido pela árvore B&P integrada, confirmando consistência interna
  entre pricing/pool/modelo compacto implementados.
- Isso valida a **consistência interna** do B&P com a formulação
  implementada — **não significa reprodução da Tabela 3** do artigo (que
  depende de xi_k desconhecido e possivelmente de uma métrica de distância
  diferente, ver seções 12-14).

O B&P **não foi alterado** com base neste diagnóstico.

## 16. Conclusão

1. A implementação atual (`objectiveMode="silva2024"`) é internamente
   consistente — script de auditoria, avaliador de rota fixa e modelo
   compacto/Gurobi concordam entre si a ~1e-14.
2. O PSV L reproduz praticamente exatamente a Tabela 3 (diferença
   ~0.003h) quando SP não é cobrado na saída da base
   (`silva_sp_arcos_base=False`).
3. O PSV M mantém resíduo de **+2.3827h** para alpha=0/0.25 no mesmo
   cenário.
4. Para alpha=0.50 o resíduo é **+2.9313h** e há violação do TDL
   (`tripDurationLimit=96h`) no nosso modelo, mesmo sem SP na saída da
   base.
5. Não há evidência de duplicação de SET/SP/serviço, nem de espera por
   janela inesperada, em nenhuma das rotas auditadas.
6. A comparação entre as rotas de alpha=0 e alpha=0.50 revelou uma
   discrepância **estrutural** (sinal oposto) na navegação: nosso modelo
   calcula +0.348579h de diferença entre as rotas, enquanto a Tabela 3
   implica -0.2h.
7. A regra LAT/LON → `Delta_cicj` utilizada pelos autores **não foi
   encontrada** documentada em nenhum material disponível neste
   repositório.
8. Nenhuma calibração ad hoc foi realizada para forçar a reprodução da
   tabela (SP, SET, distância, raio da Terra, eficiências e velocidades
   permanecem como estavam).
9. O próximo passo depende de: (a) localizar material suplementar/código
   dos autores que documente `Delta_cicj` e `xi_k`; ou (b), na ausência
   disso, assumir e documentar explicitamente uma convenção própria de
   distância/xi para esta implementação, sabendo que ela não será
   idêntica à dos autores.

## 17. Escopo desta tarefa

Nesta tarefa apenas este arquivo (`DIAGNOSTICO_SILVA2024_TABELA3.md`) foi
criado. Não alterado: `metodos.py`, `instancia.py`, `avaliador_rota.py`,
`solucao.py`, B&P, nem `DIAGNOSTICO_SILVA2024.md`. Nenhuma nova calibração
ou execução de otimização foi realizada para produzir este documento — só
consolidação de números já obtidos em etapas anteriores desta investigação.
