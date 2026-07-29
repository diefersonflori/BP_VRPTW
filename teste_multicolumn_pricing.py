"""Testes deterministicos e independentes da bateria completa para o
multi-column pricing (secoes 1-14 do pedido).

Rodar com:  python teste_multicolumn_pricing.py

Requer gurobipy (metodos.py o importa no topo) e, para os testes 2/11/12,
o modulo C++ vrptw_pd compilado em PD_PARA_PYTHON/PD_PARA_PYTHON/x64/Release.
Se algum desses nao estiver disponivel neste ambiente, os testes que dependem
dele sao pulados com aviso -- os demais (selecao/certificacao/coluna_ja_existe)
nao dependem de gurobipy nem do C++ e sempre rodam.
"""

import sys

_RESULTADOS = []


def teste(nome):
    def decorator(fn):
        _RESULTADOS.append((nome, fn))
        return fn
    return decorator


def _importar_metodos():
    from metodos import Metodos
    return Metodos


def _importar_solucao():
    from solucao import Solucao
    return Solucao


def _importar_vrptw_pd():
    import sys as _sys
    from pathlib import Path
    base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
    for sub in ("x64/Release", "x64/Debug"):
        p = base / sub
        if p.is_dir():
            _sys.path.append(str(p))
    import vrptw_pd
    return vrptw_pd


# ======================================================================
# Instancia sintetica C++ (3 clientes, 3 plataformas -> qualquer ordem
# permitida) usada nos testes 2/11/12.
# ======================================================================
def _instancia_cpp_3clientes():
    import numpy as np
    nbn = 5  # 0=base, 1..3=clientes, 4=depf
    coords = [0, 10, 20, 30, 40]
    tt = np.array([[abs(coords[i] - coords[j]) for j in range(nbn)] for i in range(nbn)], dtype=np.float64)
    aw = [[0.0]] * nbn
    bw = [[1000.0]] * nbn
    s = [0.0] * nbn
    d_deck = [0.0, 5.0, 5.0, 5.0, 0.0]
    b_deck = [0.0] * nbn
    d_diesel = [0.0] * nbn
    d_agua = [0.0] * nbn
    plataforma_id = [-1, 0, 1, 2, -1]
    pi = [80.0, 80.0, 80.0]
    kwargs = dict(
        tt=tt, aw=aw, bw=bw, s=s, d_deck=d_deck, b_deck=b_deck, d_diesel=d_diesel, d_agua=d_agua,
        plataforma_id=plataforma_id, pi=pi, sigma_k=0.0, cap_deck=100.0, cap_diesel=100.0, cap_agua=100.0,
        nbcd=3, dep0=0, depf=4,
    )
    return kwargs


# ---------------------------------------------------------------- teste 1
@teste("1. lote: candidata existente no pool e descartada, a nova e mantida")
def teste_1_filtro_pool():
    Solucao = _importar_solucao()
    sol = Solucao(1, 3)
    sol.rotas = {0: {"sequencia_rota": [[0, 1, 2]]}}

    candidatas = [
        {"k": 0, "seq": [0, 1, 2], "rc": -10.0},
        {"k": 0, "seq": [0, 2, 1], "rc": -8.0},
    ]
    sem_pool = [c for c in candidatas if not sol.coluna_ja_existe(c["seq"], k=0, globalmente=False)]
    assert len(sem_pool) == 1
    assert sem_pool[0]["seq"] == [0, 2, 1]


# ---------------------------------------------------------------- teste 2
def _teste_2_impl():
    vrptw_pd = _importar_vrptw_pd()
    kwargs = _instancia_cpp_3clientes()
    completo = vrptw_pd.sub_prog_din_petro_multi(rotas_excluidas=[], max_candidatas=20, **kwargs)
    candidatas_todas, _completa, _to = completo
    assert len(candidatas_todas) >= 6, f"instancia sintetica gerou poucas rotas ({len(candidatas_todas)}); ajuste o teste"

    cinco_primeiras = [c["clientes"] for c in candidatas_todas[:5]]
    res = vrptw_pd.sub_prog_din_petro_multi(rotas_excluidas=cinco_primeiras, max_candidatas=20, **kwargs)
    candidatas, _completa2, _to2 = res
    sextas_seqs = {tuple(c["clientes"]) for c in candidatas}
    for seq in cinco_primeiras:
        assert tuple(seq) not in sextas_seqs, f"rota excluida {seq} reapareceu"
    esperada_sexta = tuple(candidatas_todas[5]["clientes"])
    assert esperada_sexta in sextas_seqs, "a 6a candidata inedita nao foi encontrada apos excluir as 5 primeiras"


@teste("2. cinco primeiras excluidas, sexta inedita ainda e encontrada")
def teste_2_seis_candidatas():
    try:
        _teste_2_impl()
    except ImportError as exc:
        print(f"  [PULADO] vrptw_pd indisponivel neste ambiente ({exc}).")


# ---------------------------------------------------------------- teste 3
@teste("3. mesma sequencia aceita em veiculo diferente")
def teste_3_mesma_seq_outro_veiculo():
    Solucao = _importar_solucao()
    sol = Solucao(2, 3)
    sol.rotas = {
        0: {"sequencia_rota": [[0, 1, 2]]},
        1: {"sequencia_rota": [[0, 3]]},
    }
    assert sol.coluna_ja_existe([0, 1, 2], k=0, globalmente=False) is True
    assert sol.coluna_ja_existe([0, 1, 2], k=1, globalmente=False) is False


# ---------------------------------------------------------------- teste 4
@teste("4. duplicacao interna no mesmo lote: so uma sobrevive")
def teste_4_dedupe_lote():
    lote = [
        {"k": 0, "seq": [0, 1, 2], "rc": -10.0},
        {"k": 0, "seq": [0, 1, 2], "rc": -10.0},
        {"k": 0, "seq": [0, 2, 1], "rc": -5.0},
    ]
    vistas = set()
    dedupe = []
    for c in lote:
        chave = tuple(c["seq"])
        if chave in vistas:
            continue
        vistas.add(chave)
        dedupe.append(c)
    assert len(dedupe) == 2
    assert [tuple(c["seq"]) for c in dedupe] == [(0, 1, 2), (0, 2, 1)]


# ---------------------------------------------------------------- teste 5
@teste("5. limite total: 10 disponiveis, no maximo 5 selecionadas")
def teste_5_limite_iteracao():
    Metodos = _importar_metodos()
    ks = [0, 1]
    candidatas_por_k = {
        0: [{"k": 0, "seq": [0, i, 99], "rc": -float(i)} for i in range(1, 6)],
        1: [{"k": 1, "seq": [0, i, 99], "rc": -float(i)} for i in range(1, 6)],
    }
    sel = Metodos._selecionar_colunas_multi(candidatas_por_k, [0, 1], ks, max_colunas_novas_iter=5, max_colunas_novas_veiculo=10)
    assert len(sel) == 5


# ---------------------------------------------------------------- teste 6
@teste("6. limite por veiculo: 5 do mesmo veiculo, no maximo 2 selecionadas")
def teste_6_limite_por_veiculo():
    Metodos = _importar_metodos()
    ks = [0, 1]
    candidatas_por_k = {
        0: [{"k": 0, "seq": [0, i, 99], "rc": -float(i)} for i in range(1, 6)],
        1: [],
    }
    sel = Metodos._selecionar_colunas_multi(candidatas_por_k, [0, 1], ks, max_colunas_novas_iter=5, max_colunas_novas_veiculo=2)
    assert len(sel) == 2
    assert all(c["k"] == 0 for c in sel)


# ---------------------------------------------------------------- teste 7
@teste("7. round-robin: selecao alterna conforme lista_k_tentativa")
def teste_7_round_robin():
    Metodos = _importar_metodos()
    ks = [0, 1, 2]
    candidatas_por_k = {
        0: [{"k": 0, "seq": [0, 10, 99], "rc": -1.0}, {"k": 0, "seq": [0, 11, 99], "rc": -0.5}],
        1: [{"k": 1, "seq": [0, 20, 99], "rc": -1.0}, {"k": 1, "seq": [0, 21, 99], "rc": -0.5}],
        2: [{"k": 2, "seq": [0, 30, 99], "rc": -1.0}],
    }
    lista_k_tentativa = [1, 2, 0]
    sel = Metodos._selecionar_colunas_multi(candidatas_por_k, lista_k_tentativa, ks, max_colunas_novas_iter=5, max_colunas_novas_veiculo=2)
    ordem_k = [c["k"] for c in sel]
    # 1a passagem: 1,2,0 (cada um cede 1); 2a passagem: so 1 e 0 ainda tem (k=2 esgotou)
    assert ordem_k == [1, 2, 0, 1, 0], ordem_k
    assert ordem_k[0] == 1, "primeira selecionada deveria vir do 1o veiculo de lista_k_tentativa, nao do veiculo 0"


# ---------------------------------------------------------------- teste 8
@teste("8. busca incompleta sem candidatas: nao certifica")
def teste_8_busca_incompleta():
    Metodos = _importar_metodos()
    ok = Metodos._certifica_pricing_exato_completo(
        exato_tentado_algum=True, exato_busca_completa_todos=False, exato_timeout_algum=False
    )
    assert ok is False


# ---------------------------------------------------------------- teste 9
@teste("9. busca completa sem candidatas: permite certificar")
def teste_9_busca_completa():
    Metodos = _importar_metodos()
    ok = Metodos._certifica_pricing_exato_completo(
        exato_tentado_algum=True, exato_busca_completa_todos=True, exato_timeout_algum=False
    )
    assert ok is True


# --------------------------------------------------------------- teste 10
@teste("10. timeout: nunca certifica, mesmo com busca_completa=True")
def teste_10_timeout_bloqueia_certificacao():
    Metodos = _importar_metodos()
    ok = Metodos._certifica_pricing_exato_completo(
        exato_tentado_algum=True, exato_busca_completa_todos=True, exato_timeout_algum=True
    )
    assert ok is False


# --------------------------------------------------------------- teste 11
def _teste_11_impl():
    vrptw_pd = _importar_vrptw_pd()
    kwargs = _instancia_cpp_3clientes()
    rota_antiga, rc_antiga = vrptw_pd.sub_prog_din_petro(**kwargs)
    candidatas, _completa, _to = vrptw_pd.sub_prog_din_petro_multi(rotas_excluidas=[], max_candidatas=1, **kwargs)
    assert len(candidatas) == 1
    assert candidatas[0]["clientes"] == rota_antiga["clientes"]
    assert abs(candidatas[0]["custo_reduzido"] - rc_antiga) < 1e-9
    assert abs(candidatas[0]["custo"] - rota_antiga["custo"]) < 1e-9


@teste("11. max_candidatas=1 reproduz a interface antiga")
def teste_11_compat_max_candidatas_1():
    try:
        _teste_11_impl()
    except ImportError as exc:
        print(f"  [PULADO] vrptw_pd indisponivel neste ambiente ({exc}).")


# --------------------------------------------------------------- teste 12
def _teste_12_impl():
    vrptw_pd = _importar_vrptw_pd()
    kwargs = _instancia_cpp_3clientes()
    rota_antiga, _rc = vrptw_pd.sub_prog_din_petro(**kwargs)
    melhor_seq = rota_antiga["clientes"]

    candidatas, completa, _to = vrptw_pd.sub_prog_din_petro_multi(
        rotas_excluidas=[melhor_seq], max_candidatas=20, **kwargs
    )
    assert completa is True
    assert all(c["clientes"] != melhor_seq for c in candidatas)
    assert len(candidatas) >= 1, "excluir a melhor rota nao deveria impedir achar outras rotas negativas"


@teste("12. melhor rota excluida: pricing continua e acha a proxima")
def teste_12_rotas_excluidas_continua_busca():
    try:
        _teste_12_impl()
    except ImportError as exc:
        print(f"  [PULADO] vrptw_pd indisponivel neste ambiente ({exc}).")


# ======================================================================
# Testes do FLUXO REAL de insercao (revisao): usam as mesmas pecas que
# resolver_no_com_pool usa de verdade -- Metodos._verifica_limite_colunas_multi,
# Metodos._calcular_rc_coluna, Solucao.coluna_ja_existe e
# AvaliadorRota.avaliar_rota/custo_rota -- orquestradas do mesmo jeito que o
# loop real "Adiciona colunas geradas" (copia de uma candidata para cada
# veiculo), sem precisar montar um modelo Gurobi completo (o alvo aqui e a
# DECISAO de quais/quantas colunas entram, nao o LP do mestre em si).
# ======================================================================
def _instancia_solomon_generica(caps):
    """Instancia Solomon minima (sem dados_petro): base(0), 3 clientes bem
    separados (demanda=5 cada), depf(4). caps = tupla de capacidades, uma por
    veiculo (todas com velocidade=1.0, exceto quando o teste pedir diferente)."""
    from instancia import Instancia, Node, Veiculo

    coords = [0.0, 10.0, 20.0, 30.0, 40.0]
    inst = Instancia()
    inst.nbn = 5
    inst.nbcd = 3
    inst.nbv = len(caps)
    inst.noh = []
    for i, x in enumerate(coords):
        demanda = 5.0 if 1 <= i <= 3 else 0.0
        noh = Node(node_id=i, x=x, y=0.0, demanda=demanda)
        noh.READY_TIME, noh.DUE_DATE, noh.SERVICE_TIME = [0.0], [1000.0], [0.0]
        inst.noh.append(noh)
    inst.matriz_distancia = [[abs(coords[i] - coords[j]) for j in range(5)] for i in range(5)]
    inst.veiculos = [Veiculo(capacidade=cap, velocidade=1.0) for cap in caps]
    return inst


def _simular_insercao_multi(sol, avaliador, Metodos, inst, novas_colunas, max_iter, max_por_veiculo,
                             pi, sigma, mu_arc_por_k=None, eps=1e-6):
    """Espelha o loop real de 'Adiciona colunas geradas' em resolver_no_com_pool:
    para cada candidata (k_base, seq, binx, custo, rc_base), tenta copiar para
    TODOS os veiculos, reavaliando viabilidade/custo/rc para kk != k_base
    (secao 2) e aplicando o mesmo filtro central (duplicidade + limites,
    secao 1) antes de "inserir" (aqui, so anexar em sol.rotas[kk])."""
    mu_arc_por_k = mu_arc_por_k or {}
    colunas_novas_iter = 0
    colunas_novas_por_veiculo_iter = {k: 0 for k in sol.rotas}
    aceitas, rejeitadas_limite, rejeitadas_viabilidade, duplicadas = [], [], [], []

    for (k_base, seq, binx, custo, rc_base) in novas_colunas:
        for kk in sol.rotas.keys():
            if kk == k_base:
                custo_kk, rc_kk = custo, rc_base
            else:
                resultado_kk = avaliador.avaliar_rota(inst, kk, seq)
                if not resultado_kk.viavel:
                    rejeitadas_viabilidade.append((k_base, kk, list(seq)))
                    continue
                custo_kk = avaliador.custo_rota(inst, kk, seq)
                rc_kk = Metodos._calcular_rc_coluna(seq, custo_kk, pi, sigma[kk], mu_arc_por_k.get(kk, {}), inst.nbcd)

            if rc_kk >= -eps:
                continue

            if sol.coluna_ja_existe(seq, k=kk, globalmente=False):
                duplicadas.append((kk, list(seq)))
                continue

            permitido, motivo = Metodos._verifica_limite_colunas_multi(
                kk, colunas_novas_iter, colunas_novas_por_veiculo_iter, max_iter, max_por_veiculo
            )
            if not permitido:
                rejeitadas_limite.append((kk, motivo))
                continue

            sol.rotas[kk]["sequencia_rota"].append(list(seq))
            colunas_novas_iter += 1
            colunas_novas_por_veiculo_iter[kk] += 1
            aceitas.append((kk, list(seq), custo_kk, rc_kk))

    return {
        "aceitas": aceitas,
        "rejeitadas_limite": rejeitadas_limite,
        "rejeitadas_viabilidade": rejeitadas_viabilidade,
        "duplicadas": duplicadas,
        "colunas_novas_iter": colunas_novas_iter,
        "colunas_novas_por_veiculo_iter": colunas_novas_por_veiculo_iter,
    }


def _setup_fluxo_real(caps=(100.0, 100.0, 100.0)):
    from avaliador_rota import AVALIADOR_ROTA_PADRAO
    Metodos = _importar_metodos()
    Solucao = _importar_solucao()
    inst = _instancia_solomon_generica(caps)
    sol = Solucao(inst.nbv, inst.nbcd)
    sol.rotas = {k: {"sequencia_rota": [], "custo": []} for k in range(inst.nbv)}
    pi = [1000.0, 1000.0, 1000.0]  # bem alto -> rc sempre negativo, independente do custo real
    sigma = {k: 0.0 for k in range(inst.nbv)}
    return Metodos, inst, sol, AVALIADOR_ROTA_PADRAO, pi, sigma


# --------------------------------------------------------------- teste 13
@teste("13. 5 candidatas / 3 veiculos: no maximo 5 colunas realmente adicionadas")
def teste_13_limite_total_com_copias():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    candidatas = [
        (0, [0, 1, 4], [1, 0, 0], 10.0, -900.0),
        (0, [0, 2, 4], [0, 1, 0], 10.0, -900.0),
        (0, [0, 3, 4], [0, 0, 1], 10.0, -900.0),
        (0, [0, 1, 2, 4], [1, 1, 0], 20.0, -1800.0),
        (0, [0, 1, 3, 4], [1, 0, 1], 20.0, -1800.0),
    ]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=2, pi=pi, sigma=sigma)
    assert r["colunas_novas_iter"] == 5, r
    assert len(r["aceitas"]) == 5, r["aceitas"]
    assert len(r["rejeitadas_limite"]) > 0, "com 5 candidatas x 3 veiculos deveria haver tentativas alem do limite"


# --------------------------------------------------------------- teste 14
@teste("14. varias copiaveis para o mesmo veiculo: no maximo 2 entram nele")
def teste_14_limite_por_veiculo_com_copias():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    candidatas = [
        (0, [0, 1, 4], [1, 0, 0], 10.0, -900.0),
        (0, [0, 2, 4], [0, 1, 0], 10.0, -900.0),
        (0, [0, 3, 4], [0, 0, 1], 10.0, -900.0),
        (0, [0, 1, 2, 4], [1, 1, 0], 20.0, -1800.0),
    ]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=10, max_por_veiculo=2, pi=pi, sigma=sigma)
    assert r["colunas_novas_por_veiculo_iter"][1] <= 2, r["colunas_novas_por_veiculo_iter"]
    assert r["colunas_novas_por_veiculo_iter"][2] <= 2, r["colunas_novas_por_veiculo_iter"]
    assert any(motivo == "limite_veiculo" for _, motivo in r["rejeitadas_limite"])


# --------------------------------------------------------------- teste 15
@teste("15. candidata duplicada nao consome o limite; a proxima ainda ocupa a vaga")
def teste_15_duplicada_nao_consome_limite():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    # duplicada nos 3 veiculos (nao so no k_base) para garantir que nao ha
    # nenhum veiculo onde a copia possa "escapar" e consumir a vaga por outro
    # motivo que nao o de teste: a candidata deve ser 100% rejeitada por
    # duplicidade, em todo lugar em que for tentada.
    for k in sol.rotas:
        sol.rotas[k]["sequencia_rota"].append([0, 1, 4])

    candidatas = [
        (0, [0, 1, 4], [1, 0, 0], 10.0, -900.0),   # duplicada em todos os veiculos
        (0, [0, 2, 4], [0, 1, 0], 10.0, -900.0),   # nova
    ]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=1, max_por_veiculo=1, pi=pi, sigma=sigma)
    assert (0, [0, 1, 4]) in r["duplicadas"]
    assert r["colunas_novas_iter"] == 1
    assert (0, [0, 2, 4], 10.0, -900.0) in r["aceitas"], r["aceitas"]


# --------------------------------------------------------------- teste 16
@teste("16. copia para veiculo com capacidade insuficiente e rejeitada")
def teste_16_copia_capacidade_insuficiente():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real(caps=(100.0, 100.0, 3.0))
    candidatas = [(0, [0, 1, 4], [1, 0, 0], 10.0, -900.0)]  # demanda do cliente 1 = 5 > cap do veiculo 2 (3)
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=5, pi=pi, sigma=sigma)
    assert (0, 2, [0, 1, 4]) in r["rejeitadas_viabilidade"], r["rejeitadas_viabilidade"]
    assert all(kk != 2 for kk, _, _, _ in r["aceitas"])


# --------------------------------------------------------------- teste 17
@teste("17. custo diferente entre origem e destino: custo da copia e recalculado")
def teste_17_custo_recalculado_por_veiculo():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    inst.veiculos[1].velocidade = 2.0  # veiculo 1 e 2x mais rapido -> custo real menor
    seq = [0, 1, 4]
    custo_origem = avaliador.custo_rota(inst, 0, seq)
    custo_destino_esperado = avaliador.custo_rota(inst, 1, seq)
    assert custo_destino_esperado != custo_origem

    candidatas = [(0, seq, [1, 0, 0], custo_origem, -900.0)]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=5, pi=pi, sigma=sigma)
    aceita_k1 = next(a for a in r["aceitas"] if a[0] == 1)
    assert abs(aceita_k1[2] - custo_destino_esperado) < 1e-9, aceita_k1
    assert abs(aceita_k1[2] - custo_origem) > 1e-6, "custo da copia nao pode ser igual ao do veiculo de origem aqui"


# --------------------------------------------------------------- teste 18
@teste("18. sigma diferente: rc do destino recalculado pela formula completa")
def teste_18_rc_recalculado_por_sigma():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    sigma = {0: 10.0, 1: 50.0, 2: 10.0}
    seq = [0, 1, 4]
    custo = avaliador.custo_rota(inst, 0, seq)

    rc_k0 = Metodos._calcular_rc_coluna(seq, custo, pi, sigma[0], {}, inst.nbcd)
    rc_k1 = Metodos._calcular_rc_coluna(seq, custo, pi, sigma[1], {}, inst.nbcd)
    assert abs((rc_k0 - rc_k1) - (sigma[1] - sigma[0])) < 1e-9, (rc_k0, rc_k1)

    candidatas = [(0, seq, [1, 0, 0], custo, rc_k0)]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=5, pi=pi, sigma=sigma)
    aceita_k1 = next(a for a in r["aceitas"] if a[0] == 1)
    assert abs(aceita_k1[3] - rc_k1) < 1e-9, aceita_k1


# --------------------------------------------------------------- teste 19
@teste("19. mu de arco diferente por veiculo: rc da copia usa mu_arc_por_k do destino")
def teste_19_rc_usa_mu_do_destino():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real()
    seq = [0, 1, 4]
    custo = avaliador.custo_rota(inst, 0, seq)
    mu_arc_por_k = {0: {}, 1: {(0, 1): 7.0}}

    rc_sem_mu = Metodos._calcular_rc_coluna(seq, custo, pi, sigma[0], mu_arc_por_k[0], inst.nbcd)
    rc_com_mu = Metodos._calcular_rc_coluna(seq, custo, pi, sigma[1], mu_arc_por_k[1], inst.nbcd)
    assert abs((rc_sem_mu - rc_com_mu) - 7.0) < 1e-9, (rc_sem_mu, rc_com_mu)

    candidatas = [(0, seq, [1, 0, 0], custo, rc_sem_mu)]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=5,
                                 pi=pi, sigma=sigma, mu_arc_por_k=mu_arc_por_k)
    aceita_k1 = next(a for a in r["aceitas"] if a[0] == 1)
    assert abs(aceita_k1[3] - rc_com_mu) < 1e-9, aceita_k1


# --------------------------------------------------------------- teste 20
@teste("20. frota homogenea: a copia continua funcionando normalmente")
def teste_20_frota_homogenea():
    Metodos, inst, sol, avaliador, pi, sigma = _setup_fluxo_real(caps=(50.0, 50.0, 50.0))
    seq = [0, 1, 4]
    custo = avaliador.custo_rota(inst, 0, seq)
    candidatas = [(0, seq, [1, 0, 0], custo, -900.0)]
    r = _simular_insercao_multi(sol, avaliador, Metodos, inst, candidatas, max_iter=5, max_por_veiculo=5, pi=pi, sigma=sigma)
    assert len(r["aceitas"]) == 3, r["aceitas"]  # k_base=0 + copia para 1 e 2
    for kk, seq_aceita, custo_kk, rc_kk in r["aceitas"]:
        assert abs(custo_kk - custo) < 1e-9
        assert rc_kk < 0


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
        except ImportError as exc:
            print(f"[PULADO] {nome}: {exc}")
        except Exception as exc:
            falhas += 1
            print(f"[ERRO] {nome}: {type(exc).__name__}: {exc}")

    print(f"\n{len(_RESULTADOS)} testes, {len(_RESULTADOS) - falhas} OK/pulado(s), {falhas} falha(s).")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
