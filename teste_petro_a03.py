"""Teste pontual e isolado da instancia petro_A03_12ped_5plat_3nav_min2_coleta_pesada
com estabilizacao ativada, para validar a correcao da fase final sem estabilizacao
em metodos.py (fixar y_low=y_up=0 em vez de abrir a caixa com gamma_pi=1e4).

Rodar com: python teste_petro_a03.py
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import random
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_INSTANCIA = BASE_DIR / "instancias" / "instancias_petro_geradas" / "instancias_mais_nos" / "petro_A03_12ped_5plat_3nav_min2_coleta_pesada.json"

SEED_DEBUG = 123
SM_FIXO = 100
GAMMA_INI = 15
GAMMA_MIN = 10
GAMMA_MAX = 600
TABU = 0
TIME_TARGET = 600
TIME_MAX = 600


def main():
    from instancia import Instancia
    from metodos import Metodos
    from solucao import Solucao

    inst = Instancia()
    inst.nbcd = 50
    inst.nbn = 52
    inst.nbv = 0
    inst.ninst = 0
    inst.nomeInst = str(ARQUIVO_INSTANCIA)
    inst.leitura_petro(str(ARQUIVO_INSTANCIA))

    metod = Metodos(inst)
    metod.TABU_TENURE = TABU
    inst.usar_estabilizacao = True
    inst.nbconstrutiva = 10
    inst.iteraSemMelhora = SM_FIXO
    random.seed(SEED_DEBUG)

    sol_pool = Solucao(inst.nbv, inst.nbcd)
    sol_pool.FO_TARGET = -1
    sol_pool.time_initial = time.time()
    sol_pool.TIME_TARGET = TIME_TARGET
    sol_pool.TIME_MAX = TIME_MAX
    sol_pool.gamma_pi = GAMMA_INI
    sol_pool.gamma_pi_inicial = GAMMA_INI
    sol_pool.gamma_pi_min = GAMMA_MIN
    sol_pool.gamma_pi_max = GAMMA_MAX

    metod.init_pool_vazio(inst, sol_pool)
    metod.gera_solucao_inicial(inst, sol_pool)
    metod.adiciona_colunas_ociosas(inst, sol_pool)

    custo_construt = sum(float(c) for k in range(inst.nbv) for c in sol_pool.rotas[k].get("custo", []))
    print(f"[CONSTRUT] custo={custo_construt:.1f}")

    metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")

    ub = metod.best_obj if metod.best_obj > 0 else None

    # PROBLEMA 3 / item 6: prioridade de LB -- nunca usar UB como fallback de LB.
    lb_global = getattr(sol_pool, "lb_global_confiavel", None)
    lb_raiz = getattr(sol_pool, "lb_raiz_confiavel", None)
    arvore_completa = bool(getattr(sol_pool, "arvore_certificada_completa", False))

    if lb_global is not None:
        lb = float(lb_global)
        lb_valido = True
    elif lb_raiz is not None:
        lb = float(lb_raiz)
        lb_valido = True
    else:
        lb = None
        lb_valido = False

    # item 6: otimalidade so certificada quando a arvore necessaria foi
    # concluida (nenhum no interrompido/nao certificado pelo caminho), o LB
    # eh o LB GLOBAL (nao so o da raiz), o UB existe e abs(UB-LB) <= tol.
    # lb_global_confiavel != None sozinho NAO basta (pode vir do ramo por
    # gap/tempo com a arvore ainda aberta).
    tol_gap = 1e-6
    otimalidade_certificada = (
        arvore_completa
        and lb_global is not None
        and ub is not None
        and abs(float(ub) - float(lb_global)) <= tol_gap
    )

    if lb_valido and ub is not None:
        gap = abs(ub - lb) / max(abs(ub), 1e-9) * 100
        gap_str = f"{gap:.2f}%"
    else:
        gap_str = "NA"

    lb_str = f"{lb:.2f}" if lb_valido else "NA"
    ub_str = f"{ub:.2f}" if ub is not None else "NA"

    print(
        f"[BP_FIM] LB={lb_str} | UB={ub_str} | gap={gap_str} | "
        f"lb_valido={lb_valido} | arvore_certificada_completa={arvore_completa} | "
        f"otimalidade_certificada={otimalidade_certificada} | "
        f"nos={metod.total_nos} | cols={metod.total_colunas}"
    )


if __name__ == "__main__":
    main()
