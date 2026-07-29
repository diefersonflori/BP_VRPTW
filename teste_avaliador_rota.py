"""Testes deterministicos e independentes de framework para AvaliadorRota.

Rodar com:  python teste_avaliador_rota.py

So depende de `instancia.py` e `avaliador_rota.py` (nenhum dos dois importa
gurobipy), por isso roda em qualquer ambiente. A secao final ("fim a fim")
tenta importar `metodos.py`/rodar uma instancia real; se gurobipy nao
estiver instalado nesse ambiente, ela e pulada com aviso, sem derrubar o
restante da suite.
"""

import math
import sys

from instancia import Instancia, Node, Veiculo
from solucao import Solucao
from avaliador_rota import AvaliadorRota, AVALIADOR_ROTA_PADRAO

AV = AVALIADOR_ROTA_PADRAO


# ======================================================================
# Helper: monta uma instancia Petro minima "a mao" (sem depender de JSON),
# com controle total sobre janelas/demandas/capacidades de cada teste.
# ======================================================================
def montar_instancia_petro(specs, cap_deck=1000.0, cap_diesel=1000.0, cap_agua=1000.0,
                            velocidade=1.0, readiness=0.0, nbv=1):
    """specs: lista de dicts (indice 0 = base, indice -1 = deposito final),
    cada um com nome, x, y, ready (lista), due (lista), servico, dl, db, di, ag."""
    inst = Instancia()
    n = len(specs)
    inst.nbn = n
    inst.nbcd = n - 2
    inst.nbv = nbv

    inst.noh = []
    for i, spec in enumerate(specs):
        noh = Node(node_id=i, x=spec["x"], y=spec["y"],
                    demanda=spec.get("dl", 0.0) + spec.get("db", 0.0))
        noh.READY_TIME = list(spec["ready"])
        noh.DUE_DATE = list(spec["due"])
        noh.SERVICE_TIME = [spec.get("servico", 0.0)]
        inst.noh.append(noh)

    inst.matriz_distancia = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = specs[i]["x"] - specs[j]["x"]
            dy = specs[i]["y"] - specs[j]["y"]
            inst.matriz_distancia[i][j] = math.hypot(dx, dy)

    inst.veiculos = []
    for _ in range(nbv):
        veic = Veiculo(capacidade=cap_deck, velocidade=velocidade)
        veic.cap_deck = cap_deck
        veic.cap_diesel = cap_diesel
        veic.cap_agua = cap_agua
        veic.readiness = readiness
        inst.veiculos.append(veic)

    inst.dados_petro = {
        "nomes": [spec["nome"] for spec in specs],
        "lat": [spec["y"] for spec in specs],
        "lon": [spec["x"] for spec in specs],
        "dem_deck_load": [spec.get("dl", 0.0) for spec in specs],
        "dem_deck_backload": [spec.get("db", 0.0) for spec in specs],
        "dem_diesel": [spec.get("di", 0.0) for spec in specs],
        "dem_agua": [spec.get("ag", 0.0) for spec in specs],
    }
    return inst


def no(nome, x, y, ready=(0.0,), due=(1000.0,), servico=0.0, dl=0.0, db=0.0, di=0.0, ag=0.0):
    return {"nome": nome, "x": x, "y": y, "ready": list(ready), "due": list(due),
            "servico": servico, "dl": dl, "db": db, "di": di, "ag": ag}


# ======================================================================
# Metodo LEGADO -- somente para comparacao nos testes. Replica o avaliar_seq
# antigo das 5 construtivas (janela unica READY_TIME[0]/DUE_DATE[0] + pre-
# filtro de capacidade Solomon aditivo, seguido da checagem real de cargas).
# NUNCA e chamado pelas construtivas nem pela bateria (main.py) -- existe so
# aqui para demonstrar quais rotas o pre-filtro antigo rejeitava.
# ======================================================================
def _avaliar_seq_legado_construtivas(inst, k, seq):
    av = AVALIADOR_ROTA_PADRAO
    nbcd = inst.nbcd
    Q = inst.veiculos[k].capacidade
    carga = 0.0
    tempo = 0.0
    for t in range(1, len(seq)):
        i, j = seq[t - 1], seq[t]
        tempo = max(av._ready0(inst, j), tempo + av.tempo_servico(inst, i) + av.tempo_viagem(inst, k, i, j))
        if tempo + av.tempo_servico(inst, j) > av._due0(inst, j):
            return False
        if 1 <= j <= nbcd:
            carga += av._demand0(inst, j)
        if carga > Q:
            return False
    viavel, _motivo, _pico = av.validar_cargas_petro(inst, k, seq)
    return viavel


# ======================================================================
# Runner minimo (sem dependencia de pytest)
# ======================================================================
_RESULTADOS = []


def teste(nome):
    def decorator(fn):
        _RESULTADOS.append((nome, fn))
        return fn
    return decorator


# ---------------------------------------------------------------- teste 1
@teste("1. rota Petrobras valida")
def teste_rota_petro_valida():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=5),
        no("P2_order1", 20, 0, dl=5),
        no("BASE_FIM", 30, 0),
    ])
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2, 3])
    assert r.viavel, f"esperado viavel, motivo={r.motivo}"
    assert r.custo is not None and r.custo > 0


# ---------------------------------------------------------------- teste 2
@teste("2. revisita de plataforma deve ser rejeitada")
def teste_revisita_plataforma_rejeitada():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P43_order1", 10, 0, dl=1),
        no("P40_order1", 20, 0, dl=1),
        no("P43_order2", 30, 0, dl=1),
        no("BASE_FIM", 40, 0),
    ])
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2, 3, 4])
    assert not r.viavel
    assert r.motivo.startswith("retorno_plataforma"), r.motivo


# ---------------------------------------------------------------- teste 3
@teste("3. mesma plataforma dividida entre navios diferentes: aceita")
def teste_plataforma_dividida_entre_navios():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=1),
        no("P1_order2", 10, 5, dl=1),
        no("BASE_FIM", 20, 0),
    ], nbv=2)
    r_a = AV.avaliar_rota_petro(inst, 0, [0, 1, 3])
    r_b = AV.avaliar_rota_petro(inst, 1, [0, 2, 3])
    assert r_a.viavel, r_a.motivo
    assert r_b.viavel, r_b.motivo


# ---------------------------------------------------------------- teste 4
@teste("4. usa a segunda janela do pedido e deve ser aceita")
def teste_segunda_janela_aceita():
    inst = montar_instancia_petro([
        no("BASE", 0, 0, ready=(0.0,), due=(1000.0,)),
        no("P1_order1", 55, 0, ready=(0.0, 50.0), due=(10.0, 60.0), dl=1),
        no("BASE_FIM", 110, 0, ready=(0.0,), due=(1000.0,)),
    ])
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2])
    assert r.viavel, f"esperado viavel usando a 2a janela, motivo={r.motivo}"
    janela_usada = next(passo["janela"] for passo in r.cronograma if passo["no"] == 1)
    assert janela_usada == 1, f"esperado janela indice 1, obtido {janela_usada}"

    # Demonstra a divergencia relatada: o pre-filtro ANTIGO (so janela[0])
    # rejeita essa mesma rota, mesmo ela sendo operacionalmente viavel.
    assert _avaliar_seq_legado_construtivas(inst, 0, [0, 1, 2]) is False


# ---------------------------------------------------------------- teste 5
@teste("5. deck excede capacidade apos coleta: rejeita")
def teste_deck_excede_apos_coleta():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, db=15),
        no("BASE_FIM", 20, 0),
    ], cap_deck=10.0)
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2])
    assert not r.viavel
    assert r.motivo.startswith("capacidade_deck"), r.motivo


# ---------------------------------------------------------------- teste 6
@teste("6. deck viavel por causa da ordem entrega-antes-de-coleta")
def teste_deck_viavel_pela_ordem_operacional():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=8),
        no("P2_order1", 20, 0, db=8),
        no("BASE_FIM", 30, 0),
    ], cap_deck=10.0)
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2, 3])
    assert r.viavel, f"esperado viavel (P1 entrega antes de P2 coletar), motivo={r.motivo}"


# ---------------------------------------------------------------- teste 7
@teste("7. diesel acima da capacidade: rejeita")
def teste_diesel_acima_capacidade():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, di=15),
        no("BASE_FIM", 20, 0),
    ], cap_diesel=10.0)
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2])
    assert not r.viavel
    assert r.motivo == "capacidade_diesel", r.motivo


# ---------------------------------------------------------------- teste 8
@teste("8. agua acima da capacidade: rejeita")
def teste_agua_acima_capacidade():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, ag=15),
        no("BASE_FIM", 20, 0),
    ], cap_agua=10.0)
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 2])
    assert not r.viavel
    assert r.motivo == "capacidade_agua", r.motivo


# ---------------------------------------------------------------- teste 9
@teste("9. pedido repetido na rota: rejeita")
def teste_pedido_repetido():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=1),
        no("BASE_FIM", 20, 0),
    ])
    r = AV.avaliar_rota_petro(inst, 0, [0, 1, 1, 2])
    assert not r.viavel
    assert r.motivo.startswith("pedido_repetido"), r.motivo


# --------------------------------------------------------------- teste 10
@teste("10. rota sem deposito inicial/final: rejeita")
def teste_sem_depositos():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=1),
        no("BASE_FIM", 20, 0),
    ])
    r = AV.avaliar_rota_petro(inst, 0, [1, 2])
    assert not r.viavel
    assert r.motivo == "rota_sem_depositos", r.motivo


# --------------------------------------------------------------- teste 11
@teste("11. avaliacao Solomon antes/depois com o mesmo resultado")
def teste_solomon_paridade():
    inst = Instancia()
    inst.nbn, inst.nbcd, inst.nbv = 3, 1, 1
    inst.noh = [
        Node(node_id=0, x=0, y=0, demanda=0),
        Node(node_id=1, x=10, y=0, demanda=5),
        Node(node_id=2, x=20, y=0, demanda=0),
    ]
    for noh_, ready, due, serv in ((inst.noh[0], [0.0], [1000.0], 0.0),
                                    (inst.noh[1], [0.0], [100.0], 2.0),
                                    (inst.noh[2], [0.0], [1000.0], 0.0)):
        noh_.READY_TIME, noh_.DUE_DATE, noh_.SERVICE_TIME = ready, due, [serv]
    inst.matriz_distancia = [[0.0, 10.0, 20.0], [10.0, 0.0, 10.0], [20.0, 10.0, 0.0]]
    inst.veiculos = [Veiculo(capacidade=10.0, velocidade=1.0)]
    seq = [0, 1, 2]
    k = 0

    # Implementacao "anterior" (formula original, replicada aqui so para o teste).
    def ready(i):
        return inst.noh[i].READY_TIME[0]

    def due(i):
        return inst.noh[i].DUE_DATE[0]

    def service(i):
        return inst.noh[i].SERVICE_TIME[0]

    def demand(i):
        return getattr(inst.noh[i], "DEMAND", 0.0)

    def travel(i, j):
        return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

    Q = inst.veiculos[k].capacidade
    carga_old, tempo_old, viavel_old = 0.0, 0.0, True
    for t in range(1, len(seq)):
        i, j = seq[t - 1], seq[t]
        tempo_old = max(ready(j), tempo_old + service(i) + travel(i, j))
        if tempo_old + service(j) > due(j):
            viavel_old = False
            break
        if 1 <= j <= inst.nbcd:
            carga_old += demand(j)
        if carga_old > Q:
            viavel_old = False
            break
    custo_old = sum(travel(seq[t], seq[t + 1]) for t in range(len(seq) - 1))

    r = AV.avaliar_rota(inst, k, seq)
    assert not hasattr(inst, "dados_petro")
    assert r.viavel == viavel_old
    assert r.viavel and abs(r.custo - custo_old) < 1e-9


# --------------------------------------------------------------- teste 12
@teste("12. custo da rota == custo pela formula antiga (travel-time)")
def teste_custo_rota_paridade():
    inst = montar_instancia_petro([
        no("BASE", 0, 0),
        no("P1_order1", 10, 0, dl=1),
        no("P2_order1", 10, 10, dl=1),
        no("BASE_FIM", 0, 10),
    ])
    seq = [0, 1, 2, 3]
    k = 0

    def travel_antigo(i, j):
        return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

    custo_antigo = sum(travel_antigo(seq[t], seq[t + 1]) for t in range(len(seq) - 1))
    custo_novo = AV.custo_rota(inst, k, seq)
    assert abs(custo_novo - custo_antigo) < 1e-9, (custo_novo, custo_antigo)


# ======================================================================
# Secao fim-a-fim (opcional): roda uma instancia real pequena pelas
# construtivas ja refatoradas e confere pontos 5/6 pedidos -- toda rota real
# passa de novo pelo AvaliadorRota, cobertura completa e sem duplicados.
# Pulada com aviso se o ambiente nao tiver gurobipy (metodos.py depende dele).
# ======================================================================
def teste_fim_a_fim_instancia_real():
    from pathlib import Path
    try:
        from metodos import Metodos
    except ImportError as exc:
        print(f"  [PULADO] metodos.py nao pode ser importado neste ambiente ({exc}).")
        print("  Rode esta secao manualmente (ex.: no PyCharm) para validacao fim-a-fim.")
        return

    arquivo = Path(__file__).resolve().parent / "instancias" / "instancias_petro_geradas" / "petro_campos_C1_nucleo_atual_10ped.json"
    if not arquivo.is_file():
        print(f"  [PULADO] instancia de exemplo nao encontrada: {arquivo}")
        return

    import random
    inst = Instancia()
    inst.nbcd = 50
    inst.nbn = 52
    inst.nbv = 0
    inst.leitura_petro(str(arquivo))

    metod = Metodos(inst)
    inst.nbconstrutiva = 10
    inst.iteraSemMelhora = 30
    random.seed(123)

    sol = Solucao(inst.nbv, inst.nbcd)
    metod.init_pool_vazio(inst, sol)
    metod.gera_rotas_iniciais_clarke_wright(inst, sol)

    clientes_cobertos = []
    for k in range(inst.nbv):
        seq = sol.rotas[k]["sequencia_rota"][0]
        artificial = sol.rotas[k]["artificial"][0]
        if len(seq) <= 2:
            continue

        r = AV.avaliar_rota_petro(inst, k, seq)
        legado = _avaliar_seq_legado_construtivas(inst, k, seq)
        print(f"  veiculo {k}: artificial={artificial} novo.viavel={r.viavel} "
              f"(motivo={r.motivo!r}) legado.viavel={legado}")

        if not artificial:
            assert r.viavel, f"rota real do veiculo {k} nao passou no AvaliadorRota: {r.motivo}"
            clientes_cobertos.extend(AV.clientes_da_rota(inst, seq))

    assert len(clientes_cobertos) == len(set(clientes_cobertos)), "pedido duplicado entre veiculos"
    faltantes = set(range(1, inst.nbcd + 1)) - set(clientes_cobertos)
    if faltantes:
        print(f"  [AVISO] pedidos nao cobertos por rotas reais (podem estar em rota artificial): {sorted(faltantes)}")
    else:
        print("  cobertura completa 1..nbcd confirmada, sem duplicados.")


# ======================================================================
# Execucao
# ======================================================================
def main():
    falhas = 0
    for nome, fn in _RESULTADOS:
        try:
            fn()
            print(f"[OK]   {nome}")
        except AssertionError as exc:
            falhas += 1
            print(f"[FALHOU] {nome}: {exc}")
        except Exception as exc:  # defeito inesperado tambem conta como falha
            falhas += 1
            print(f"[ERRO] {nome}: {type(exc).__name__}: {exc}")

    print("\n-- secao fim-a-fim (instancia real, opcional) --")
    try:
        teste_fim_a_fim_instancia_real()
    except AssertionError as exc:
        falhas += 1
        print(f"[FALHOU] fim-a-fim: {exc}")

    print(f"\n{len(_RESULTADOS)} testes, {len(_RESULTADOS) - falhas} OK, {falhas} falha(s).")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
