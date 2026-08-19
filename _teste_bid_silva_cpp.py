import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import os
import types
import time

import numpy as np

from instancia import Instancia
from metodos import Metodos

# ============================================================
# TESTE BID_SILVA_CPP -- compara o novo nucleo C++ heuristico (beam/label-
# setting com dominancia por nivel, reaproveitando SilvaPricingData/
# SilvaLabel de silva_pricing_core.h) contra SUB_PROG_BID_SILVA (Python, ja
# validado, NAO alterado por este arquivo/tarefa). Mesma instancia/duais/
# cenarios ja usados em _teste_pd_silva_cpp.py.
#
# BID e HEURISTICO dos dois lados: nao se exige mesma rota nem mesmo RC
# entre Python e C++ (busca_completa/completa=False sempre) -- so que ambos
# respeitem a fisica/branching/nao-revisita e que toda candidata C++ seja
# auditada por avaliar_rota_silva2024 (UNICA autoridade de viabilidade/
# custo). BID_SILVA_CPP nao e integrado ao B&P nesta tarefa.
# ============================================================

CPP_DIR = os.path.join(
    r"C:\Users\PolyanaSilva\Documents\BP_VRPTW", "PD_SILVA_CPP", "PD_SILVA_CPP", "x64", "Release"
)
sys.path.insert(0, CPP_DIR)
import vrptw_pd_silva  # noqa: E402

print("\n[C++ MODULE]")
print(f"arquivo={vrptw_pd_silva.__file__}")
assert os.path.abspath(vrptw_pd_silva.__file__).startswith(os.path.abspath(CPP_DIR)), \
    "vrptw_pd_silva importado de um caminho inesperado -- possivel .pyd antigo no sys.path"
assert hasattr(vrptw_pd_silva, "pricing_bid_silva"), \
    "modulo carregado nao expoe pricing_bid_silva -- .pyd desatualizado?"

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
assert len(PI_BASE) == inst.nbcd == 14

MAX_CANDIDATAS = 5
MAX_LABELS_POR_NO = 60  # mesmo default conceitual de SUB_PROG_BID_SILVA
TOL_RC = 1e-6


def no_bp_vazio():
    ns = types.SimpleNamespace()
    ns.arcos_proibidos = set()
    ns.arcos_fixados_em_1 = set()
    return ns


def _plataforma_chave(inst, no):
    dp = inst.dados_petro
    nomes = list(dp.get("nomes", []))
    nome = str(nomes[no]) if no < len(nomes) else ""
    if "_order_" in nome:
        return nome.split("_order_", 1)[0]
    elif "_order" in nome:
        return nome.split("_order", 1)[0]
    return nome


def _plataforma_de(inst, no):
    if no == 0 or no == inst.nbn - 1:
        return None
    return _plataforma_chave(inst, no)


def checa_nao_revisita_plataforma(tag_origem, candidatas, erros):
    for c in candidatas:
        seq_plataformas = [_plataforma_de(inst, no) for no in c["seq"]]
        seq_plataformas = [p for p in seq_plataformas if p is not None]
        comprimida = []
        for p in seq_plataformas:
            if not comprimida or comprimida[-1] != p:
                comprimida.append(p)
        if len(comprimida) != len(set(comprimida)):
            erros.append(f"[{tag_origem}] candidata {c['seq']} REVISITA uma plataforma "
                          f"(sequencia comprimida de plataformas={comprimida})")


def audita_candidatas(tag_origem, candidatas, k, sigma_k, mu_arc, no_bp, pi, erros, tol=1e-8):
    for c in candidatas:
        if c["k"] != k:
            erros.append(f"[{tag_origem}] candidata com k={c['k']} != {k}")

        resultado = metod.avaliar_rota_silva2024(inst, k, c["seq"])
        if not resultado["viavel"]:
            erros.append(f"[{tag_origem}] candidata {c['seq']} NAO viavel por "
                          f"avaliar_rota_silva2024: {resultado.get('motivo')}")
            continue

        custo_oficial = float(resultado["custo"])
        if abs(custo_oficial - c["custo"]) > tol:
            erros.append(f"[{tag_origem}] custo armazenado ({c['custo']}) difere de "
                          f"resultado['custo'] ({custo_oficial}) por "
                          f"{abs(custo_oficial - c['custo']):.2e} (candidata {c['seq']})")

        rc_recomputado = float(custo_oficial)
        for cliente in c["seq"]:
            if 1 <= cliente <= inst.nbcd:
                rc_recomputado -= float(pi[cliente - 1])
        rc_recomputado -= float(sigma_k)
        for t in range(len(c["seq"]) - 1):
            i, j = c["seq"][t], c["seq"][t + 1]
            mu_val = mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0))
            rc_recomputado -= float(mu_val)

        if abs(rc_recomputado - c["rc"]) > tol:
            erros.append(f"[{tag_origem}] RC armazenado ({c['rc']}) difere da "
                          f"recomputacao independente ({rc_recomputado}) por "
                          f"{abs(rc_recomputado - c['rc']):.2e} (candidata {c['seq']})")

        if c["rc"] >= -tol:
            erros.append(f"[{tag_origem}] candidata {c['seq']} tem RC>=0 ({c['rc']}) -- "
                          f"nao deveria ter sido retornada")

        if not metod.coluna_respeita_no(no_bp, c["seq"], k):
            erros.append(f"[{tag_origem}] candidata {c['seq']} viola branching do NO_BP")

    checa_nao_revisita_plataforma(tag_origem, candidatas, erros)


# ============================================================
# Marshaling: IDENTICO a montar_kwargs_cpp de _teste_pd_silva_cpp.py (mesmo
# mapeamento instancia/veiculo -> parametros de vrptw_pd_silva -- so os
# ultimos kwargs, especificos do BID, mudam: max_labels_por_no/max_depth em
# vez de max_labels/timeout_s do PD).
# ============================================================

def montar_kwargs_cpp_bid(inst, k, pi, sigma_k, mu_arc, no_bp,
                           max_labels_por_no=MAX_LABELS_POR_NO, max_depth=-1,
                           max_candidatas=MAX_CANDIDATAS):
    dp = inst.dados_petro
    nbn = inst.nbn
    nbcd = inst.nbcd
    dep0 = 0
    depf = nbn - 1
    veic = inst.veiculos[k]

    nomes = list(dp.get("nomes", []))
    mapa_plataformas = {}
    plataforma_id = [-1] * nbn
    for i in range(1, nbcd + 1):
        chave = _plataforma_chave(inst, i)
        if chave not in mapa_plataformas:
            mapa_plataformas[chave] = len(mapa_plataformas)
        plataforma_id[i] = mapa_plataformas[chave]

    platform_setup_seg = list(dp.get("platform_setup_seg", [0.0] * nbn))
    n_plataformas = len(mapa_plataformas)
    set_por_plataforma = [0.0] * max(n_plataformas, 1)
    for i in range(1, nbcd + 1):
        p = plataforma_id[i]
        set_por_plataforma[p] = max(set_por_plataforma[p], float(platform_setup_seg[i]))

    dist_raw = dp["dist"]
    n_raw = len(dist_raw)
    dist_km_arr = np.zeros((nbn, nbn), dtype=np.float64)
    for i in range(n_raw):
        for j in range(n_raw):
            dist_km_arr[i, j] = float(dist_raw[i][j])

    vs = veic.velocities
    v_low = float(min(vs, key=lambda v: v["above"])["speed"])
    v_high = float(max(vs, key=lambda v: v["above"])["speed"])
    th_km = float(max(vs, key=lambda v: v["above"])["above"])

    servico = [float(inst.noh[i].SERVICE_TIME[0]) if getattr(inst.noh[i], "SERVICE_TIME", None) else 0.0
               for i in range(nbn)]
    ready = [list(getattr(inst.noh[i], "READY_TIME", []) or []) for i in range(nbn)]
    due = [list(getattr(inst.noh[i], "DUE_DATE", []) or []) for i in range(nbn)]

    def dado_no(i, atributo, chave):
        valor_no = getattr(inst.noh[i], atributo, None)
        if valor_no is not None:
            return float(valor_no)
        vetor = dp.get(chave, [])
        return float(vetor[i]) if i < len(vetor) else 0.0

    deck_load = [dado_no(i, "DEMAND_DECK_LOAD", "dem_deck_load") for i in range(nbn)]
    deck_backload = [dado_no(i, "DEMAND_DECK_BACKLOAD", "dem_deck_backload") for i in range(nbn)]
    diesel_dem = [dado_no(i, "DEMAND_DIESEL", "dem_diesel") for i in range(nbn)]
    agua_dem = [dado_no(i, "DEMAND_AGUA", "dem_agua") for i in range(nbn)]

    tempo_carreg_deck = list(dp.get("tempo_carreg_deck", [0.0] * nbn))
    tempo_carreg_diesel = list(dp.get("tempo_carreg_diesel", [0.0] * nbn))
    tempo_carreg_agua = list(dp.get("tempo_carreg_agua", [0.0] * nbn))
    tempo_descarreg_backload = list(dp.get("tempo_descarreg_backload", [0.0] * nbn))
    commodities = list(dp.get("commodities", [None] * nbn))
    is_backload = [1 if (i < len(commodities) and commodities[i] == "deckCargoBackload") else 0
                   for i in range(nbn)]
    order_due_time_seg = list(dp.get("order_due_time_seg", [None] * nbn))
    has_due_time = [1 if (i < len(order_due_time_seg) and order_due_time_seg[i] is not None) else 0
                    for i in range(nbn)]
    order_due_time = [float(order_due_time_seg[i]) if (i < len(order_due_time_seg) and order_due_time_seg[i] is not None) else 0.0
                      for i in range(nbn)]

    cap_deck = float(getattr(veic, "cap_deck", veic.capacidade))
    cap_diesel = float(getattr(veic, "cap_diesel", float("inf")))
    cap_agua = float(getattr(veic, "cap_agua", float("inf")))

    AT = float(veic.readiness)
    max_partida = float(getattr(veic, "max_departure", 0.0))
    tdl = float(getattr(veic, "trip_duration_limit", 0.0))
    theta_k = float(veic.cost_anchored)
    varphi_k = float(veic.cost_base)
    gamma_k = float(veic.cost_navigation)
    delta_k = float(veic.cost_dynamic)
    xi_usado = float(veic.xi) if veic.xi is not None else 1.0
    alpha_fo = float(inst.alpha_fo)
    eta_fo = float(inst.eta_fo)

    mu_flat = [0.0] * (nbn * nbn)
    for i in range(nbn):
        for j in range(nbn):
            mu_flat[i * nbn + j] = float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))

    proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
    forbid_flat = [0] * (nbn * nbn)
    for (i, j) in proibidos_k:
        forbid_flat[i * nbn + j] = 1

    fixados_k = [(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k]
    req_i = [i for (i, j) in fixados_k]
    req_j = [j for (i, j) in fixados_k]

    return dict(
        nbn=nbn, nbcd=nbcd, dep0=dep0, depf=depf, k=k,
        dist_km_arr=dist_km_arr,
        v_low=v_low, v_high=v_high, th_km=th_km, safe_positioning_time=float(veic.safe_positioning_time),
        plataforma_id=plataforma_id,
        set_por_plataforma=set_por_plataforma,
        servico=servico, ready=ready, due=due,
        deck_load=deck_load, deck_backload=deck_backload, diesel_dem=diesel_dem, agua_dem=agua_dem,
        tempo_carreg_deck=tempo_carreg_deck, tempo_carreg_diesel=tempo_carreg_diesel,
        tempo_carreg_agua=tempo_carreg_agua, tempo_descarreg_backload=tempo_descarreg_backload,
        is_backload=is_backload, order_due_time=order_due_time, has_due_time=has_due_time,
        cap_deck=cap_deck, cap_diesel=cap_diesel, cap_agua=cap_agua,
        AT=AT, max_partida=max_partida, tdl=tdl,
        theta_k=theta_k, varphi_k=varphi_k, gamma_k=gamma_k, delta_k=delta_k,
        xi_usado=xi_usado, alpha_fo=alpha_fo, eta_fo=eta_fo,
        pi=list(pi), sigma_k=float(sigma_k), mu_flat=mu_flat,
        forbid_flat=forbid_flat, req_i=req_i, req_j=req_j,
        max_labels_por_no=max_labels_por_no, max_depth=max_depth, max_candidatas=max_candidatas,
        eps=1e-6,
    )


def roda_caso(tag, k, sigma_k, mu_arc, no_bp):
    print("\n" + "#" * 100)
    print(f"# CASO: {tag} -- k={k} sigma_k={sigma_k} mu_arc={mu_arc}")
    print("#" * 100)

    pi = list(PI_BASE)

    t0 = time.time()
    cand_py, completa_py, timeout_py = metod.SUB_PROG_BID_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, max_candidatas=MAX_CANDIDATAS, max_labels_por_no=MAX_LABELS_POR_NO,
    )
    tempo_py = time.time() - t0

    kwargs_cpp = montar_kwargs_cpp_bid(inst, k, pi, sigma_k, mu_arc, no_bp)
    saida_cpp, completa_cpp, timeout_cpp, labels_cpp, nivel_cpp, tempo_cpp = \
        vrptw_pd_silva.pricing_bid_silva(**kwargs_cpp)
    cand_cpp = list(saida_cpp)

    melhor_py = cand_py[0] if cand_py else None
    melhor_cpp = cand_cpp[0] if cand_cpp else None

    print("\n[SILVA BID PY x CPP]")
    print(f"caso={tag}")
    print(f"k={k}")
    print("\nPY:")
    print(f"melhor_rc={melhor_py['rc'] if melhor_py else None}")
    print(f"rota={melhor_py['seq'] if melhor_py else None}")
    print(f"labels=n/d (SUB_PROG_BID_SILVA nao expoe total_labels)")
    print(f"completa={completa_py} timeout={timeout_py}")
    print(f"tempo={tempo_py:.4f}s")

    print("\nCPP:")
    print(f"melhor_rc={melhor_cpp['rc'] if melhor_cpp else None}")
    print(f"rota={melhor_cpp['seq'] if melhor_cpp else None}")
    print(f"labels={labels_cpp}")
    print(f"completa={completa_cpp} timeout={timeout_cpp} nivel={nivel_cpp}")
    print(f"tempo={tempo_cpp:.4f}s")

    speedup = (tempo_py / tempo_cpp) if tempo_cpp > 1e-9 else None
    print(f"\nspeedup={speedup}")

    erros = []

    # ---- contrato: BID e sempre heuristico ----
    if completa_py is not False:
        erros.append(f"[BID_PY] completa deveria ser sempre False (heuristico), veio {completa_py}")
    if completa_cpp is not False:
        erros.append(f"[BID_SILVA_CPP] completa deveria ser sempre False (heuristico), veio {completa_cpp}")

    # ---- auditoria obrigatoria de toda candidata C++ (secao 14) ----
    audita_candidatas("BID_SILVA_CPP", cand_cpp, k, sigma_k, mu_arc, no_bp, pi, erros)
    # auditoria tambem do lado Python, para referencia (BID python ja validado
    # antes, mas nao custa nada confirmar aqui tambem)
    audita_candidatas("BID_SILVA_PY", cand_py, k, sigma_k, mu_arc, no_bp, pi, erros)

    # ---- RC cpp x RC python recomputado de forma independente (secao 8/14) ----
    for c in cand_cpp:
        resultado = metod.avaliar_rota_silva2024(inst, k, c["seq"])
        if not resultado["viavel"]:
            continue  # ja reportado por audita_candidatas
        rc_py = float(resultado["custo"])
        for cliente in c["seq"]:
            if 1 <= cliente <= inst.nbcd:
                rc_py -= float(pi[cliente - 1])
        rc_py -= float(sigma_k)
        for t in range(len(c["seq"]) - 1):
            i, j = c["seq"][t], c["seq"][t + 1]
            rc_py -= float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))
        if abs(c["rc"] - rc_py) > TOL_RC:
            erros.append(f"[BID_SILVA_CPP] rc_cpp ({c['rc']}) difere de rc_python ({rc_py}) "
                          f"por {abs(c['rc'] - rc_py):.2e} > tolerancia {TOL_RC:.1e} (candidata {c['seq']})")

    # ---- se o C++ retornou alguma coluna, exige RC<0 (secao 11) ----
    if cand_cpp and not all(c["rc"] < -1e-8 for c in cand_cpp):
        erros.append("[BID_SILVA_CPP] alguma candidata retornada nao tem RC<0")

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")

    return len(erros) == 0


def bid_cpp_branch_test_arco_fixado(tag, k, sigma_k, no_bp, arco_fixo):
    print("\n" + "#" * 100)
    print(f"# BID CPP BRANCH TEST (arco fixado): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, j, kk = arco_fixo
    kwargs_cpp = montar_kwargs_cpp_bid(inst, k, pi, sigma_k, {}, no_bp)
    saida_cpp, completa_cpp, timeout_cpp, labels_cpp, nivel_cpp, tempo_cpp = \
        vrptw_pd_silva.pricing_bid_silva(**kwargs_cpp)
    candidatas = list(saida_cpp)

    label_chegou = any(i in c["seq"] for c in candidatas)
    label_expandiu = any(
        any(c["seq"][t] == i and c["seq"][t + 1] == j for t in range(len(c["seq"]) - 1))
        for c in candidatas
    )
    respeita_no = all(metod.coluna_respeita_no(no_bp, c["seq"], k) for c in candidatas) if candidatas else False

    print("\n[BID CPP BRANCH TEST]")
    print(f"arco_fixo=({i},{j},{kk})")
    print(f"label_chegou_{i}={label_chegou}")
    print(f"label_expandiu_{i}_{j}={label_expandiu}")
    print(f"candidata_contem_arco={label_expandiu}")
    print(f"coluna_respeita_no={respeita_no}")
    print(f"rota_encontrada={candidatas[0]['seq'] if candidatas else None}")
    print(f"completa={completa_cpp} labels={labels_cpp} nivel={nivel_cpp} tempo={tempo_cpp:.4f}s")

    erros = []
    if not candidatas:
        erros.append("BID_SILVA_CPP nao encontrou candidata com o arco fixado")
    if not label_expandiu:
        erros.append(f"nenhuma candidata BID_SILVA_CPP contem o arco fixado ({i},{j}) consecutivo")
    if not respeita_no:
        erros.append("alguma candidata BID_SILVA_CPP viola coluna_respeita_no")
    audita_candidatas("BID_SILVA_CPP_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")
    return len(erros) == 0


def bid_cpp_branch_test_arco_proibido_deposito(tag, k, sigma_k, no_bp, arco_proibido):
    print("\n" + "#" * 100)
    print(f"# BID CPP BRANCH TEST (arco proibido p/ deposito): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, depf_no, kk = arco_proibido
    kwargs_cpp = montar_kwargs_cpp_bid(inst, k, pi, sigma_k, {}, no_bp)
    saida_cpp, completa_cpp, timeout_cpp, labels_cpp, nivel_cpp, tempo_cpp = \
        vrptw_pd_silva.pricing_bid_silva(**kwargs_cpp)
    candidatas = list(saida_cpp)

    label_chegou = any(i in c["seq"] for c in candidatas)
    label_contornou = any(
        i in c["seq"] and c["seq"][c["seq"].index(i) + 1] != depf_no
        for c in candidatas
    )
    nenhuma_usa_arco_proibido = all(
        not any(c["seq"][t] == i and c["seq"][t + 1] == depf_no for t in range(len(c["seq"]) - 1))
        for c in candidatas
    )
    respeita_no = all(metod.coluna_respeita_no(no_bp, c["seq"], k) for c in candidatas) if candidatas else False

    print("\n[BID CPP BRANCH TEST]")
    print(f"arco_proibido=({i},{depf_no},{kk})")
    print(f"label_chegou_{i}={label_chegou}")
    print(f"label_expandiu_{i}_j={label_contornou}")
    print(f"candidata_contem_arco={nenhuma_usa_arco_proibido}")
    print(f"coluna_respeita_no={respeita_no}")
    print(f"rota_encontrada={candidatas[0]['seq'] if candidatas else None}")
    print(f"completa={completa_cpp} labels={labels_cpp} nivel={nivel_cpp} tempo={tempo_cpp:.4f}s")

    erros = []
    if not label_chegou:
        erros.append(f"nenhuma candidata BID_SILVA_CPP visita o no {i}")
    if candidatas and not label_contornou:
        erros.append(f"nenhuma candidata BID_SILVA_CPP visita {i} e contorna o fechamento direto p/ o deposito")
    if not nenhuma_usa_arco_proibido:
        erros.append(f"alguma candidata BID_SILVA_CPP usa o arco proibido ({i},{depf_no})")
    if not respeita_no:
        erros.append("alguma candidata BID_SILVA_CPP viola coluna_respeita_no")
    audita_candidatas("BID_SILVA_CPP_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")
    return len(erros) == 0


ok_geral = True

for k in range(inst.nbv):
    ok_geral &= roda_caso(f"raiz_sem_branching_navio{k}", k, sigma_k=2.0, mu_arc={}, no_bp=no_bp_vazio())

no_bp_mu = no_bp_vazio()
mu_arc_teste = {(0, 1): 0.5, (1, 8, 0): 1.2}
ok_geral &= roda_caso("com_mu_arc", 0, sigma_k=1.5, mu_arc=mu_arc_teste, no_bp=no_bp_mu)

no_bp_branch = no_bp_vazio()
no_bp_branch.arcos_fixados_em_1 = {(0, 1, 0)}
no_bp_branch.arcos_proibidos = {(1, 8, 0)}
ok_geral &= roda_caso("com_branching_fixa_0_1_proibe_1_8", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch)

no_bp_branch2 = no_bp_vazio()
no_bp_branch2.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= roda_caso("com_branching_cadeia_0_6_1", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch2)

DEPF = inst.nbn - 1
no_bp_proibido = no_bp_vazio()
no_bp_proibido.arcos_proibidos = {(6, DEPF, 0)}
ok_geral &= roda_caso("com_arco_retorno_proibido_6", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_proibido)


# ============================================================
# BID CPP BRANCH TEST
# ============================================================

no_bp_bt_fixo = no_bp_vazio()
no_bp_bt_fixo.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= bid_cpp_branch_test_arco_fixado(
    "cadeia_0_6_1_forca_6_1", 0, sigma_k=2.0, no_bp=no_bp_bt_fixo, arco_fixo=(6, 1, 0),
)

no_bp_bt_proibido = no_bp_vazio()
no_bp_bt_proibido.arcos_proibidos = {(6, DEPF, 0)}
ok_geral &= bid_cpp_branch_test_arco_proibido_deposito(
    "proibe_6_para_deposito", 0, sigma_k=2.0, no_bp=no_bp_bt_proibido, arco_proibido=(6, DEPF, 0),
)

print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
