import sys
import time
import random
import os
import math
import copy
from multiprocessing import freeze_support

from instancia import Instancia
from solucao import Solucao
from metodos import Metodos, NoBP


SEED_DEBUG = 123
TAM        = 25
CAP        = 200
TABU       = 0
GAMMA_INI  = 10   # família C
GAMMA_MIN  = 10
GAMMA_MAX  = 50
TIPO_GER   = "PD"
TIME_TARGET = 5000
TIME_MAX    = 600   # 10 min por rodada

INSTANCIAS = [
    ("instancias/c101N.txt", "c101n", 3, 191.3),
    ("instancias/c102.txt",  "c102",  3, 190.3),
    ("instancias/c103.txt",  "c103",  3, 190.3),
    ("instancias/c104.txt",  "c104",  3, 186.9),
    ("instancias/c105.txt",  "c105",  3, 191.3),
    ("instancias/c106.txt",  "c106",  3, 191.3),
]


def fmt(v):
    if v is None or (isinstance(v, float) and math.isinf(v)):
        return "---"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def rodar_instancia(arquivo, nome_base, nbv, fo_target, usar_estab, inst_base=None):
    label = "COM estab" if usar_estab else "SEM estab"

    inst = copy.deepcopy(inst_base) if inst_base else Instancia()
    if not inst_base:
        inst.nbcd = TAM
        inst.nbn  = TAM + 2
        inst.nomeInst = arquivo
        inst.nbv  = nbv
        inst.ninst = 0
        inst.leitura(arquivo)
        for v in inst.veiculos:
            v.capacidade = CAP
            v.velocidade = 10

    inst.usar_estabilizacao   = usar_estab
    inst.nbconstrutiva        = 10
    inst.iteraSemMelhora      = 20
    inst.TABU_TENURE          = TABU
    inst.parar_ao_atingir_int_target = True

    metod = Metodos(inst)
    metod.TABU_TENURE = TABU

    sol = Solucao(inst.nbv, inst.nbcd)
    sol.FO_TARGET     = fo_target
    sol.time_initial  = time.time()
    sol.TIME_TARGET   = TIME_TARGET
    sol.TIME_MAX      = TIME_MAX
    sol.gamma_pi          = GAMMA_INI
    sol.gamma_pi_inicial  = GAMMA_INI
    sol.gamma_pi_min      = GAMMA_MIN
    sol.gamma_pi_max      = GAMMA_MAX

    random.seed(SEED_DEBUG)

    metod.init_pool_vazio(inst, sol)
    metod.gera_rotas_iniciaisUNICA(inst, sol)
    metod.gera_rotas_iniciais_inteligente_inteira(inst, sol)

    inst.temmip = False
    t0 = time.time()
    metod.branch_and_price_global(inst, sol, tipo_geracao=TIPO_GER)
    tempo = time.time() - t0

    fo_bp    = metod.best_obj
    achou    = sol.achou_int_target
    iter_int = sol.iter_int_target if sol.iter_int_target else "---"
    t_int    = sol.tempo_int_target
    motivo   = getattr(sol, "motivoConv", "---")
    nb_iter  = getattr(sol, "nb_iteracoes", "---")
    colunas  = metod.total_colunas

    gap = ""
    if fo_bp not in (None, -1) and fo_target > 0:
        gap = f"{((fo_bp - fo_target) / fo_target) * 100:.2f}%"

    return {
        "label":   label,
        "fo_bp":   fo_bp,
        "gap":     gap,
        "tempo":   tempo,
        "achou":   achou,
        "iter_int":iter_int,
        "t_int":   t_int,
        "motivo":  motivo,
        "nb_iter": nb_iter,
        "colunas": colunas,
    }


def main():
    print("=" * 80)
    print(f"  EXPERIMENTO: c101n–c106, 25 clientes, cap={CAP}")
    print("=" * 80)

    cabecalho = (
        f"{'Instância':<10} {'Modo':<10} {'FO BP':>8} {'Gap':>8} "
        f"{'Tempo(s)':>9} {'Iter':>5} {'t_INT(s)':>9} {'Motivo':<25} {'n_iter':>6} {'Cols':>5}"
    )
    sep = "-" * len(cabecalho)

    resultados_por_inst = {}

    for arquivo, nome_base, nbv, fo_target in INSTANCIAS:
        print(f"\n{'=' * 70}")
        print(f"  INSTÂNCIA: {nome_base}  |  veículos={nbv}  |  target={fo_target}")
        print(f"{'=' * 70}")

        # constrói instância base uma vez
        inst_base = Instancia()
        inst_base.nbcd    = TAM
        inst_base.nbn     = TAM + 2
        inst_base.nomeInst = arquivo
        inst_base.nbv     = nbv
        inst_base.ninst   = 0
        inst_base.leitura(arquivo)
        for v in inst_base.veiculos:
            v.capacidade = CAP
            v.velocidade = 10

        # solução exata (referência)
        from solucao import Solucao as Sol2
        solex = Sol2(inst_base.nbv, inst_base.nbn)
        metod_ex = Metodos(inst_base)
        t_ex0 = time.time()
        metod_ex.metodo_exato(inst_base, solex)
        t_ex  = time.time() - t_ex0
        fo_ex = solex.custo
        print(f"  Exato: FO={fo_ex:.4f}  tempo={t_ex:.2f}s")

        print(f"\n{cabecalho}")
        print(sep)

        res = {}
        for usar_estab in [True, False]:
            r = rodar_instancia(arquivo, nome_base, nbv, fo_target, usar_estab, inst_base)
            res[usar_estab] = r
            print(
                f"  {nome_base:<8} {r['label']:<10} "
                f"{fmt(r['fo_bp']):>8} {r['gap']:>8} "
                f"{r['tempo']:>9.2f} {str(r['iter_int']):>5} "
                f"{fmt(r['t_int']):>9} {r['motivo']:<25} "
                f"{str(r['nb_iter']):>6} {str(r['colunas']):>5}"
            )

        resultados_por_inst[nome_base] = {"res": res, "fo_ex": fo_ex, "fo_target": fo_target}

    # ── Tabela resumo final ────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("  RESUMO GERAL")
    print("=" * 80)
    print(f"  {'Inst':<8} {'FO exato':>9} {'Target':>8} {'FO COM':>8} {'t COM':>8} {'achou COM':>10} {'FO SEM':>8} {'t SEM':>8} {'achou SEM':>10}")
    print("  " + "-" * 78)
    for nome_base, d in resultados_por_inst.items():
        r_com = d["res"][True]
        r_sem = d["res"][False]
        print(
            f"  {nome_base:<8} {d['fo_ex']:>9.4f} {d['fo_target']:>8.1f} "
            f"{fmt(r_com['fo_bp']):>8} {r_com['tempo']:>8.1f} {str(r_com['achou']):>10} "
            f"{fmt(r_sem['fo_bp']):>8} {r_sem['tempo']:>8.1f} {str(r_sem['achou']):>10}"
        )


if __name__ == "__main__":
    freeze_support()
    main()
