import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import os
import types
import time
import ctypes

import numpy as np

from instancia import Instancia
from metodos import Metodos

# ============================================================
# TESTE DE ESCALA/COMPLETUDE do PD_SILVA_CPP (isolado, NAO altera
# PD_SILVA_CPP.cpp, silva_pricing_core.h, metodos.py nem o .pyd). So mede
# quantos labels o C++ precisa para esgotar o cenario raiz_sem_branching_navio0
# (mesmos pi/sigma/mu/instancia de _teste_pd_silva_cpp.py), crescendo
# max_labels ate completa=True ou ate 10M/20s. Roda o C++ uma vez por
# max_labels (NAO reexecuta o PD Python para cada configuracao -- so a
# auditoria de avaliar_rota_silva2024 na melhor candidata de cada execucao).
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

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
assert len(PI_BASE) == inst.nbcd == 14

TIMEOUT_S = 20.0
MAX_CANDIDATAS = 5
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


# ============================================================
# Marshaling: IDENTICO a montar_kwargs_cpp de _teste_pd_silva_cpp.py (copiado
# aqui, nao importado, para nao executar a bateria inteira daquele arquivo ao
# importa-lo -- nenhuma logica nova, so reuso do mesmo mapeamento ja validado).
# ============================================================

def montar_kwargs_cpp(inst, k, pi, sigma_k, mu_arc, no_bp,
                       max_labels, timeout_s, max_candidatas=MAX_CANDIDATAS):
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
        max_labels=max_labels, timeout_s=timeout_s, max_candidatas=max_candidatas,
        eps=1e-6,
    )


# ============================================================
# Memoria RSS do processo (Windows) via ctypes + psapi -- SEM biblioteca nova
# (ctypes e stdlib; psapi.dll e parte do Windows). So leitura, nao afeta o
# processo medido.
# ============================================================

def rss_mb():
    try:
        psapi = ctypes.WinDLL("psapi.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_uint32),
                ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_uint32]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        # PeakWorkingSetSize (nao WorkingSetSize): o pool de labels e um
        # std::vector LOCAL a pricing_pd_silva, liberado quando a chamada
        # retorna -- o RSS atual pos-retorno nao reflete o pico durante a
        # busca. Peak e uma marca d'agua do processo, sobrevive a liberacao.
        return counters.PeakWorkingSetSize / (1024.0 * 1024.0)
    except Exception:
        return None


pi = list(PI_BASE)
sigma_k = 2.0
mu_arc = {}
no_bp = no_bp_vazio()
k = 0

print("\n" + "#" * 100)
print("# TESTE DE ESCALA: raiz_sem_branching_navio0 (PD_SILVA_CPP)")
print("#" * 100)

niveis_max_labels = [300_000, 1_000_000, 3_000_000, 10_000_000]
linhas = []
certificado = None

for max_labels in niveis_max_labels:
    kwargs_cpp = montar_kwargs_cpp(inst, k, pi, sigma_k, mu_arc, no_bp,
                                    max_labels=max_labels, timeout_s=TIMEOUT_S)

    mem_antes = rss_mb()
    t0 = time.time()
    saida_cpp, completa_cpp, timeout_cpp, labels_cpp, nivel_cpp, tempo_cpp = \
        vrptw_pd_silva.pricing_pd_silva(**kwargs_cpp)
    tempo_wall = time.time() - t0
    mem_depois = rss_mb()

    cand_cpp = list(saida_cpp)
    melhor_cpp = cand_cpp[0] if cand_cpp else None
    labels_por_s = (labels_cpp / tempo_cpp) if tempo_cpp > 1e-9 else None

    print("\n[SILVA PD CPP ESCALA]")
    print(f"max_labels={max_labels}")
    print(f"labels_gerados={labels_cpp}")
    print(f"nivel={nivel_cpp}")
    print(f"melhor_rc={melhor_cpp['rc'] if melhor_cpp else None}")
    print(f"completa={completa_cpp}")
    print(f"timeout={timeout_cpp}")
    print(f"tempo={tempo_cpp:.3f}s")
    print(f"labels_por_segundo={labels_por_s}")
    if mem_depois is not None:
        print(f"memoria_mb={mem_depois:.1f}")
    else:
        print("memoria_mb=indisponivel")

    # ---- auditoria obrigatoria da melhor candidata (secao "AUDITORIA") ----
    rc_python = None
    viavel = None
    if melhor_cpp is not None:
        resultado = metod.avaliar_rota_silva2024(inst, k, melhor_cpp["seq"])
        viavel = resultado["viavel"]
        if viavel:
            rc_python = float(resultado["custo"])
            for cliente in melhor_cpp["seq"]:
                if 1 <= cliente <= inst.nbcd:
                    rc_python -= float(pi[cliente - 1])
            rc_python -= float(sigma_k)
            for t in range(len(melhor_cpp["seq"]) - 1):
                i, j = melhor_cpp["seq"][t], melhor_cpp["seq"][t + 1]
                rc_python -= float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))
        rc_ok = viavel and (rc_python is not None) and abs(rc_python - melhor_cpp["rc"]) <= TOL_RC
        print(f"auditoria: viavel={viavel} rc_cpp={melhor_cpp['rc']} rc_python={rc_python} "
              f"| RC_CPP==RC_PYTHON: {rc_ok}")
        if not rc_ok:
            print("[ERRO] auditoria falhou -- RC C++ diverge da avaliacao Python")

    linhas.append(dict(max_labels=max_labels, labels=labels_cpp, nivel=nivel_cpp,
                        rc=melhor_cpp['rc'] if melhor_cpp else None,
                        rota=melhor_cpp['seq'] if melhor_cpp else None,
                        completa=completa_cpp, timeout=timeout_cpp, tempo=tempo_cpp))

    if completa_cpp:
        certificado = dict(labels_totais=labels_cpp, melhor_rc=melhor_cpp['rc'],
                            rota=melhor_cpp['seq'], tempo=tempo_cpp)
        print("\n[SILVA PD CPP CERTIFICADO]")
        print(f"labels_totais={labels_cpp}")
        print(f"melhor_rc={melhor_cpp['rc']}")
        print(f"rota={melhor_cpp['seq']}")
        print(f"tempo={tempo_cpp:.3f}s")
        break

    if tempo_wall >= TIMEOUT_S and max_labels >= niveis_max_labels[-1]:
        break

print("\n" + "=" * 100)
print("[TABELA RESUMO] max_labels x labels x nivel x RC x tempo")
print("=" * 100)
print(f"{'max_labels':>12} {'labels':>10} {'nivel':>6} {'rc':>14} {'completa':>9} {'timeout':>8} {'tempo_s':>9}")
for ln in linhas:
    print(f"{ln['max_labels']:>12} {ln['labels']:>10} {ln['nivel']:>6} "
          f"{(ln['rc'] if ln['rc'] is not None else float('nan')):>14.4f} "
          f"{str(ln['completa']):>9} {str(ln['timeout']):>8} {ln['tempo']:>9.3f}")

print("\n" + "=" * 100)
if certificado:
    print(f"[RESULTADO] completa=True em max_labels={linhas[-1]['max_labels']} "
          f"| labels_necessarios={certificado['labels_totais']} | melhor_rc={certificado['melhor_rc']}")
else:
    print(f"[RESULTADO] completa=False ate max_labels={niveis_max_labels[-1]} / timeout={TIMEOUT_S}s -- parando aqui")
print("=" * 100)
