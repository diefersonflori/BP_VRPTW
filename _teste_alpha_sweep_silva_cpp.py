import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import os
import types

from instancia import Instancia
from metodos import Metodos

# ============================================================
# TESTE ALPHA SWEEP (secao 10 do pedido de auditoria C++): confirma que o
# novo B (otimo pelo coeficiente da FO) afeta corretamente hDP/f1/f2/custo/RC
# em TODOS os regimes de alpha_fo -- nao so no default da instancia. Usa um
# candidato REAL do pricing PD_SILVA_CPP (nao uma rota fabricada a mao) e
# recomputa tudo com avaliar_rota_silva2024 (autoridade).
# ============================================================

CPP_DIR = os.path.join(str(BASE_DIR), "PD_SILVA_CPP", "PD_SILVA_CPP", "x64", "Release")
sys.path.insert(0, CPP_DIR)
import vrptw_pd_silva  # noqa: E402

print("\n[C++ MODULE]")
print(f"arquivo={vrptw_pd_silva.__file__}")

ARQ = str(BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json")
inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
TOL = 1e-6


def no_bp_vazio():
    ns = types.SimpleNamespace()
    ns.arcos_proibidos = set()
    ns.arcos_fixados_em_1 = set()
    return ns


def montar_kwargs_cpp(inst, k, pi, sigma_k, no_bp, max_labels=300_000, timeout_s=20.0, max_candidatas=5):
    import numpy as np
    dp = inst.dados_petro
    nbn = inst.nbn
    nbcd = inst.nbcd
    dep0 = 0
    depf = nbn - 1
    veic = inst.veiculos[k]

    nomes = list(dp.get("nomes", []))

    def _plataforma_chave(no):
        nome = str(nomes[no]) if no < len(nomes) else ""
        if "_order_" in nome:
            return nome.split("_order_", 1)[0]
        elif "_order" in nome:
            return nome.split("_order", 1)[0]
        return nome

    mapa_plataformas = {}
    plataforma_id = [-1] * nbn
    for i in range(1, nbcd + 1):
        chave = _plataforma_chave(i)
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
        pi=list(pi), sigma_k=float(sigma_k), mu_flat=[],
        forbid_flat=forbid_flat, req_i=req_i, req_j=req_j,
        max_labels=max_labels, timeout_s=timeout_s, max_candidatas=max_candidatas,
        eps=1e-6,
    )


ok_geral = True
linhas = []

for alpha in (0.0, 0.1, 1.0):
    inst.alpha_fo = alpha
    pi = list(PI_BASE)
    k = 1
    sigma_k = 0.2
    no_bp = no_bp_vazio()

    kwargs_cpp = montar_kwargs_cpp(inst, k, pi, sigma_k, no_bp)
    saida_cpp, completa_cpp, timeout_cpp, labels_cpp, nivel_cpp, tempo_cpp = \
        vrptw_pd_silva.pricing_pd_silva(**kwargs_cpp)
    candidatas = list(saida_cpp)
    if not candidatas:
        print(f"[alpha={alpha}] nenhuma candidata retornada -- pulando")
        continue
    melhor = candidatas[0]
    seq = melhor["seq"]

    resultado = metod.avaliar_rota_silva2024(inst, k, seq)
    erros = []
    if not resultado["viavel"]:
        erros.append(f"[alpha={alpha}] melhor candidata C++ nao-viavel no Python: {resultado.get('motivo')}")
        ok_geral = False
        continue

    custo_python = float(resultado["custo"])
    f1_python = float(resultado["f1"])
    f2_python = float(resultado["f2"])
    hDP_python = float(resultado["hDP"])
    B_python = float(resultado["B"])

    rc_python = custo_python
    for cliente in seq:
        if 1 <= cliente <= inst.nbcd:
            rc_python -= float(pi[cliente - 1])
    rc_python -= float(sigma_k)

    diff_custo = abs(custo_python - melhor["custo"])
    diff_rc = abs(rc_python - melhor["rc"])

    if diff_custo > TOL:
        erros.append(f"[alpha={alpha}] custo_cpp ({melhor['custo']}) difere de custo_python "
                      f"({custo_python}) por {diff_custo:.3e} > {TOL:.1e}")
    if diff_rc > TOL:
        erros.append(f"[alpha={alpha}] rc_cpp ({melhor['rc']}) difere de rc_python ({rc_python}) "
                      f"por {diff_rc:.3e} > {TOL:.1e}")

    print(f"\n[alpha={alpha}] seq={seq}")
    print(f"  custo_cpp={melhor['custo']:.6f} custo_python={custo_python:.6f} diff={diff_custo:.3e}")
    print(f"  rc_cpp={melhor['rc']:.6f} rc_python={rc_python:.6f} diff={diff_rc:.3e}")
    print(f"  B={B_python:.4f} hDP={hDP_python:.4f} f1={f1_python:.4f} f2={f2_python:.4f}")

    linhas.append((alpha, seq, B_python, hDP_python, f1_python, f2_python, custo_python, diff_custo, diff_rc))

    if erros:
        ok_geral = False
        for e in erros:
            print(f"  [FALHOU] {e}")
    else:
        print("  [OK]")

print("\n\n" + "=" * 100)
print("RESUMO ALPHA SWEEP (mesmo candidato/pricing, alpha variando)")
print("=" * 100)
print(f"{'alpha':>6} {'B':>8} {'hDP':>8} {'f1':>12} {'f2':>8} {'custo':>12} {'diff_custo':>11} {'diff_rc':>11}")
for (alpha, seq, B, hDP, f1, f2, custo, dc, dr) in linhas:
    print(f"{alpha:>6} {B:>8.4f} {hDP:>8.4f} {f1:>12.4f} {f2:>8.4f} {custo:>12.4f} {dc:>11.3e} {dr:>11.3e}")

print("\n" + "=" * 100)
print(f"[RESULTADO FINAL ALPHA SWEEP] {'TODOS OS ALPHAS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
