import sys
import time
import random
import os
import math

from instancia import Instancia
from solucao import Solucao
from metodos import Metodos, NoBP
from multiprocessing import freeze_support


def main():
    SEED_DEBUG = 123

    tam = 25
    cap = 200
    arquivo_instancia = "instancias/c101N.txt"
    nome_base = "c101n"
    nbv_inst = 3
    fo_target_inst = 191.3
    ninst = 0
    gamma_PMAX = 50
    gamma_ini_inst = 10  # família "c"
    gamma_pi_min = 10
    tabu = 0
    tipo_geracao = "PD"
    TIMETarg = 5000

    print("=" * 60)
    print(f"Instância: {arquivo_instancia}  |  tam={tam}  |  veículos={nbv_inst}")
    print(f"Capacidade={cap}  |  gamma_ini={gamma_ini_inst}  |  gamma_max={gamma_PMAX}")
    print("=" * 60)

    inst_base = Instancia()
    inst_base.nbcd = tam
    inst_base.nbn = tam + 2
    inst_base.nomeInst = arquivo_instancia
    inst_base.nbv = nbv_inst
    inst_base.ninst = ninst
    inst_base.leitura(arquivo_instancia)
    for v in inst_base.veiculos:
        v.capacidade = cap
        v.velocidade = 10

    # ── Solução exata ──────────────────────────────────────────────
    metod_ex = Metodos(inst_base)
    solex = Solucao(inst_base.nbv, inst_base.nbn)
    tiex = time.time()
    metod_ex.metodo_exato(inst_base, solex)
    tfex = time.time()
    tempo_exato = tfex - tiex
    fo_exato = solex.custo
    seq_exato = solex.sequencias_exato_para_texto()
    print(f"\nSolução exata: FO={fo_exato:.4f}  tempo={tempo_exato:.4f}s")
    print(f"Sequência: {seq_exato}\n")

    # ── Armazena resultados de cada rodada ─────────────────────────
    resultados = {}

    for usar_estab in [True, False]:
        label = "COM estabilização" if usar_estab else "SEM estabilização"
        print("\n" + "#" * 60)
        print(f"  RODADA: {label}")
        print("#" * 60)

        import copy
        inst = copy.deepcopy(inst_base)
        inst.usar_estabilizacao = usar_estab
        inst.nbconstrutiva = 10
        inst.iteraSemMelhora = 20
        inst.TABU_TENURE = tabu
        inst.parar_ao_atingir_int_target = True

        metod = Metodos(inst)
        metod.TABU_TENURE = tabu

        sol_pool = Solucao(inst.nbv, inst.nbcd)
        sol_pool.FO_TARGET = fo_target_inst
        sol_pool.time_initial = time.time()
        sol_pool.TIME_TARGET = TIMETarg

        sol_pool.gamma_pi = gamma_ini_inst
        sol_pool.gamma_pi_inicial = gamma_ini_inst
        sol_pool.gamma_pi_min = gamma_pi_min
        sol_pool.gamma_pi_max = gamma_PMAX
        sol_pool.TIME_MAX = 300  # limite de segurança: 5 minutos

        random.seed(SEED_DEBUG)

        metod.init_pool_vazio(inst, sol_pool)
        metod.gera_rotas_iniciaisUNICA(inst, sol_pool)
        metod.gera_rotas_iniciais_inteligente_inteira(inst, sol_pool)

        for k in range(inst.nbv):
            print(f"  veic {k}: {len(sol_pool.rotas[k]['sequencia_rota'])} rotas iniciais")

        t1 = time.time()
        inst.temmip = False

        metod.branch_and_price_global(inst, sol_pool, tipo_geracao=tipo_geracao)

        tempo_bp = time.time() - t1

        try:
            sol_pool.exportar_convergencia_excel(inst, usar_estabilizacao=usar_estab)
        except Exception as e:
            print(f"Erro export Excel: {e}")

        r = {
            "label": label,
            "usar_estab": usar_estab,
            "fo_bp": metod.best_obj,
            "tempo_bp": tempo_bp,
            "nos_bp": metod.total_nos,
            "colunas_bp": metod.total_colunas,
            "melhor_lp_com_slack": sol_pool.melhor_lp_com_slack,
            "iter_lp_com_slack": sol_pool.iter_melhor_lp_com_slack,
            "melhor_lp_valido": sol_pool.melhor_lp_valido,
            "iter_lp_valido": sol_pool.iter_melhor_lp_valido,
            "melhor_int": sol_pool.melhor_inteiro,
            "iter_int": sol_pool.iter_melhor_inteiro,
            "achou_lp_target": sol_pool.achou_lp_target,
            "iter_lp_target": sol_pool.iter_lp_target,
            "tempo_lp_target": sol_pool.tempo_lp_target,
            "achou_int_target": sol_pool.achou_int_target,
            "iter_int_target": sol_pool.iter_int_target,
            "tempo_int_target": sol_pool.tempo_int_target,
            "nb_iteracoes": getattr(sol_pool, "nb_iteracoes", ""),
            "motivoConv": getattr(sol_pool, "motivoConv", ""),
            "seq_bp": sol_pool.sequencias_bp_para_texto() or "SEM_SOLUCAO",
        }
        resultados[usar_estab] = r

        print(f"\n  -- Resumo {label} --")
        print(f"  Tempo BP:         {tempo_bp:.4f}s")
        print(f"  FO BP:            {r['fo_bp']}")
        print(f"  Nós:              {r['nos_bp']}")
        print(f"  Colunas:          {r['colunas_bp']}")
        print(f"  Iterações:        {r['nb_iteracoes']}")
        print(f"  Motivo conv.:     {r['motivoConv']}")
        print(f"  Melhor LP slack:  {r['melhor_lp_com_slack']}  (iter {r['iter_lp_com_slack']})")
        print(f"  Melhor LP válido: {r['melhor_lp_valido']}  (iter {r['iter_lp_valido']})")
        print(f"  Melhor inteiro:   {r['melhor_int']}  (iter {r['iter_int']})")
        print(f"  Achou LP target:  {r['achou_lp_target']}  iter={r['iter_lp_target']}  tempo={r['tempo_lp_target']}")
        print(f"  Achou INT target: {r['achou_int_target']}  iter={r['iter_int_target']}  tempo={r['tempo_int_target']}")

    # ── Comparação final ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  COMPARAÇÃO FINAL")
    print("=" * 60)
    print(f"  FO exato (referência): {fo_exato:.4f}")
    print(f"  FO target (literatura): {fo_target_inst}")
    print()

    r_com = resultados[True]
    r_sem = resultados[False]

    def gap(fo):
        if fo is None or fo in (-1, float("inf")):
            return "N/A"
        return f"{((fo - fo_exato) / fo_exato) * 100:.4f}%"

    rows = [
        ("FO BP",              r_com["fo_bp"],          r_sem["fo_bp"]),
        ("Gap vs exato",       gap(r_com["fo_bp"]),      gap(r_sem["fo_bp"])),
        ("Tempo (s)",          f"{r_com['tempo_bp']:.4f}", f"{r_sem['tempo_bp']:.4f}"),
        ("Nós B&P",            r_com["nos_bp"],          r_sem["nos_bp"]),
        ("Colunas geradas",    r_com["colunas_bp"],      r_sem["colunas_bp"]),
        ("Iterações GC",       r_com["nb_iteracoes"],    r_sem["nb_iteracoes"]),
        ("Motivo convergência",r_com["motivoConv"],      r_sem["motivoConv"]),
        ("Melhor LP com slack",r_com["melhor_lp_com_slack"], r_sem["melhor_lp_com_slack"]),
        ("  iter LP slack",    r_com["iter_lp_com_slack"],   r_sem["iter_lp_com_slack"]),
        ("Melhor LP válido",   r_com["melhor_lp_valido"],    r_sem["melhor_lp_valido"]),
        ("  iter LP válido",   r_com["iter_lp_valido"],      r_sem["iter_lp_valido"]),
        ("Melhor inteiro",     r_com["melhor_int"],           r_sem["melhor_int"]),
        ("  iter inteiro",     r_com["iter_int"],             r_sem["iter_int"]),
        ("Achou LP target",    r_com["achou_lp_target"],      r_sem["achou_lp_target"]),
        ("  iter LP target",   r_com["iter_lp_target"],       r_sem["iter_lp_target"]),
        ("  tempo LP target",  r_com["tempo_lp_target"],      r_sem["tempo_lp_target"]),
        ("Achou INT target",   r_com["achou_int_target"],     r_sem["achou_int_target"]),
        ("  iter INT target",  r_com["iter_int_target"],      r_sem["iter_int_target"]),
        ("  tempo INT target", r_com["tempo_int_target"],     r_sem["tempo_int_target"]),
    ]

    col_w = 26
    val_w = 22
    header = f"  {'Métrica':<{col_w}} {'COM estabilização':<{val_w}} {'SEM estabilização':<{val_w}}"
    print(header)
    print("  " + "-" * (col_w + 2 * val_w))
    for nome, v_com, v_sem in rows:
        print(f"  {nome:<{col_w}} {str(v_com):<{val_w}} {str(v_sem):<{val_w}}")

    print()
    print(f"  Sequência COM: {r_com['seq_bp']}")
    print(f"  Sequência SEM: {r_sem['seq_bp']}")
    print(f"  Sequência exata: {seq_exato}")


if __name__ == "__main__":
    freeze_support()
    main()
