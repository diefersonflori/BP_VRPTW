import sys
import time
import csv
import random
from datetime import datetime

from instancia import Instancia
from solucao import Solucao
from metodos import Metodos, NoBP

SEED_DEBUG = 123
# SEED_DEBUG = 9999

ARQ_CSV_FINAL = "resultados_finais.csv"
ARQ_TXT_FINAL = "resultados_finais_legivel.txt"

import os
import sys

# sys.stdout = open(os.devnull, 'w')
# =========================
# Arquivos de saída
# =========================
"""

with open(ARQ_CSV_FINAL, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow([
        "run_id",
        "arquivo_instancia",
        "ninst",
        "tem_janelas",
        "heuristica_retirada",
        "tamanho_clientes",
        "nos_rede",
        "veiculos",
        "capacidade",
        "tabu",
        "tipo_geracao",
        "tempo_exato",
        "tempo_bp",
        "fo_exato",
        "fo_bp",
        "gap_pct",
        "igual_exato",
        "nos_bp",
        "colunas_bp",
        "seq_exato",
        "seq_bp",
        "timestamp"
    ])

with open(ARQ_TXT_FINAL, "w", encoding="utf-8") as f:
    f.write("RESULTADOS FINAIS DOS EXPERIMENTOS\n")
    f.write("=" * 120 + "\n\n")
"""
# tamanhos=[4,7,13]#,20,25]
# capacidades=[36,70,110]#,200,200]
# tamanhos=[13]#,20,25]
# capacidades=[110]#,200,200]
# capacidades~ 60% do total das demandas

# tamanhos=[16]#,25]
# capacidades=[150]#,200]
tamanhos = [50]
capacidades = [200]

# tamanhos=[16,20]#,25]
# capacidades=[150,200]#,200]
# tamanhos=[20,25]
# capacidades=[200,200]
# tamanhos=[20]
# capacidades=[200]
nbvv = [3, 5]
# N_TABUS=[3,4,5]
N_TABUS = [0]  # ,1,2,3]
# combinacao_construtivas=[1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
# combinacao_construtivas=[10]#,0,1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
combinacao_construtivas = [10]  # 10 só pra testar ta ligado? quero tirar ninguem não fióti
# combinacao_construtivas=[0,1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
# combinacao_construtivas=[22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
# combinacao_construtivas=[10]#10 só pra testar ta ligado? quero tirar ninguem não fióti


# todas_instancias = ["instancias/r110.txt"]
"""
todas_instancias = ["instancias/c107.txt",
                    "instancias/c108.txt", "instancias/c109.txt"]#,
"""
"""
"instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",
todas_instancias = [ "instancias/c203.txt", "instancias/c204.txt",
                    "instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt"]

                    "instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",
                    "instancias/c105.txt", "instancias/c106.txt", 

"""
"instancias/c201.txt", "instancias/c202.txt",
# C25
"""

todas_instancias = ["instancias/c101N.txt","instancias/c102.txt","instancias/c103.txt",
                     "instancias/c104.txt","instancias/c105.txt","instancias/c106.txt", "instancias/c107.txt",
                     "instancias/c108.txt", "instancias/c109.txt","instancias/r101.txt","instancias/r102.txt",
                     "instancias/r103.txt","instancias/r104.txt",
                     "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                     "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                     "instancias/r111.txt","instancias/r112.txt"]

nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4]#C25
"""
# R25
"""
todas_instancias = (["instancias/r101.txt","instancias/r102.txt","instancias/r103.txt","instancias/r104.txt",
                      "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                      "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                      "instancias/r111.txt","instancias/r112.txt"])
nbv=[8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25
"""
# todas_instancias = (["instancias/c103.txt"])
"""    
"instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
"instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt",
"instancias/c208.txt"]
"""
# todas_instancias = (["instancias/c101N.txt","instancias/c102.txt","instancias/c103.txt",
#                     "instancias/c104.txt","instancias/c105.txt","instancias/c106.txt", "instancias/c107.txt",
#                    "instancias/c108.txt", "instancias/c109.txt"])

# C50
"""
todas_instancias = ["instancias/c101N.txt",
                    "instancias/c102.txt", "instancias/c103.txt","instancias/c105.txt", "instancias/c106.txt",
                    "instancias/c107.txt", "instancias/c108.txt"]#,
nbv=[5,5,4,5,5,5,5]#C50
"""

# R50
# """
"""
todas_instancias = (["instancias/r101.txt","instancias/r102.txt","instancias/r103.txt",
                      "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                     "instancias/r110.txt"])
"""
# RC25
# todas_instancias = (["instancias/rc101.txt","instancias/rc102.txt","instancias/rc103.txt",
#                      "instancias/rc104.txt","instancias/rc105.txt","instancias/rc106.txt","instancias/rc107.txt",
#                     "instancias/rc108.txt"])
# nbv=[4,3,3,3,4,3,3,3]


# """
# TODES 50
todas_instancias = (
["instancias/c101N.txt", "instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt", "instancias/c105.txt",
 "instancias/c106.txt",
 "instancias/c107.txt", "instancias/c108.txt", "instancias/c109.txt",
 "instancias/r101.txt", "instancias/r102.txt", "instancias/r103.txt", "instancias/r104.txt",
 "instancias/r105.txt", "instancias/r106.txt", "instancias/r107.txt",
 "instancias/r108.txt", "instancias/r109.txt", "instancias/r110.txt",
 "instancias/r111.txt", "instancias/r112.txt",
 "instancias/rc101.txt", "instancias/rc102.txt", "instancias/rc103.txt",
 "instancias/rc104.txt", "instancias/rc105.txt", "instancias/rc106.txt", "instancias/rc107.txt",
 "instancias/rc108.txt",
 "instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
 "instancias/c205.txt", "instancias/c206.txt",
 "instancias/c207.txt", "instancias/c208.txt", "instancias/c209.txt",
 "instancias/r201.txt", "instancias/r202.txt", "instancias/r203.txt", "instancias/r204.txt",
 "instancias/r205.txt", "instancias/r206.txt", "instancias/r207.txt",
 "instancias/r208.txt", "instancias/r209.txt", "instancias/r120.txt",
 "instancias/r211.txt", "instancias/r212.txt",
 "instancias/rc201.txt", "instancias/rc202.txt", "instancias/rc203.txt",
 "instancias/rc204.txt", "instancias/rc205.txt", "instancias/rc206.txt", "instancias/rc207.txt"])
# nbv=[5,5,5,5,5,5,5,5,5,11,9,6,9,6,7,6,8,7,7,6,8,7,6,5,8,6,6,
# 6,3,3,3,2,3,3,3,2,6,5,5,2,4,4,2,2,4,4,3,5,5,4,3,5,5,4]
nbv = [5, 5, 5, 5, 5, 5, 5, 5, 5, 12, 11, 9, 6, 9, 6, 7, 6, 8, 7, 7, 6, 8, 7, 6, 5, 8, 6, 6, 6, 3, 3, 3, 2, 3, 3, 3, 2,
       6, 5, 5, 2, 4, 4, 2, 2, 4, 4, 3, 5, 5, 4, 3, 5, 5, 4, ]

FO_TARGET_50 = {
    "c101n": 362.4, "c102": 362.4, "c103": 362.4, "c104": 362.4, "c105": 362.4, "c106": 1043.3, "c107": 909.0, "c108": 769.2, "c109": 619.1,
    "r101": 892.1,"r102": 791.3,"r103": 707.2,"r104": 594.7,"r105": 775.3,"r106": 695.1,"r107": 696.3,"r108": 614.8,"r109": 850.0,"r110": 721.8,"r111": 645.2,"r112": 545.8, "rc101": 761.5,
    "rc102": 664.4,"rc103": 603.5,"rc104": 541.1}

# """

# 25- 50
"""

todas_instancias = ["instancias/c101N.txt","instancias/c102.txt","instancias/c103.txt",
                     "instancias/c104.txt","instancias/c105.txt","instancias/c106.txt", "instancias/c107.txt",
                     "instancias/c108.txt", "instancias/c109.txt","instancias/r101.txt","instancias/r102.txt",
                     "instancias/r103.txt","instancias/r104.txt",
                     "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                     "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                     "instancias/r111.txt","instancias/r112.txt",#fim 25
                    "instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt","instancias/c104.txt",
                    "instancias/c105.txt", "instancias/c106.txt",
                    "instancias/c107.txt", "instancias/c108.txt", "instancias/c109.txt",
                    "instancias/r101.txt","instancias/r102.txt","instancias/r103.txt","instancias/r104.txt",
                    "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                    "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                    "instancias/r111.txt","instancias/r112.txt",
                    "instancias/rc101.txt","instancias/rc102.txt","instancias/rc103.txt",
                    "instancias/rc104.txt","instancias/rc105.txt","instancias/rc106.txt","instancias/rc107.txt",
                    "instancias/rc108.txt",
                    "instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
                     "instancias/c205.txt", "instancias/c206.txt",
                     "instancias/c207.txt", "instancias/c208.txt", "instancias/c209.txt",
                     "instancias/r201.txt", "instancias/r202.txt", "instancias/r203.txt", "instancias/r204.txt",
                     "instancias/r205.txt", "instancias/r206.txt", "instancias/r207.txt",
                     "instancias/r208.txt", "instancias/r209.txt", "instancias/r120.txt",
                     "instancias/r211.txt", "instancias/r212.txt",
                    "instancias/rc201.txt", "instancias/rc202.txt", "instancias/rc203.txt",
                     "instancias/rc204.txt", "instancias/rc205.txt", "instancias/rc206.txt", "instancias/rc207.txt"

                    ]

nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4,#fim 25
     5,5,5,5,5,5,5,5,5,12,11,9,6,9,6,7,6,8,7,7,6,8,7,6,5,8,6,6,6,3,3,3,2,3,3,3,2,6,5,5,2,4,4,2,2,4,4,3,5,5,4,3,5,5,4]
,"""

# R50
# nbv=[12,11,9,9,8,7,7]#R50
# """
# """
# todas_instancias = ["instancias/c104.txt"]
# nbv=[3]
ab = 1
semMelhora = [300,10, 15, 20, 25]  # ,2,4,6,8]
# instancais grandes
# nbv=[4]#25

# VALORES OTIMOS FO C25
"""
nbv=[3,3,3,3,3,3,3,3,3]#C25
todas_instancias = (["instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt","instancias/c104.txt","instancias/c105.txt", "instancias/c106.txt",
                    "instancias/c107.txt", "instancias/c108.txt", "instancias/c109.txt"])
"""

# FOTARGET=[191.3,190.3,190.3,186.9,191.3,191.3,191.3,191.3,191.3]
# TIMETARGET=[18.6,79.7,134.7,223.9,25.6,20.7,31.7,43.1,585.4]


# VALORES OTIMOS FO R25
# FOTARGET=[617.1, 547.1, 454.6, 416.9, 530.5, 467.4, 424.3, 397.2, 441.3, 429.5, 428.8, 393]
# TIMETARGET=[5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4, 14.4, 64.3, 330, 623.3]
# nbv=[8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25

# FOTARGET=[617.1, 547.1, 454.6, 416.9, 530.5, 467.4, 424.3, 397.2, 441.3, 429.5, 428.8, 393]
# TIMETARGET=[18.6,79.7,134.7,223.9,25.6,20.7,31.7,43.1,585.4,5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4, 14.4, 64.3, 330, 623.3]
# nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25

FOTARGET = []
TIMETARGET = [18.6, 79.7, 134.7, 223.9, 25.6, 20.7, 31.7, 43.1, 585.4, 5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4,
              14.4, 64.3, 330, 623.3]
# nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25

# estabilizacao
gammas_25_C = [20, 30, 40, 50, 60, 80]
gammas_25_R = [40, 80, 120, 160]

gammas_50_C = [40, 80, 120, 160]
gammas_50_R = [80, 160, 240, 320]

gamma_pi_max = [500, 1000, 2000]

gamma_pi_min = 10
# gamma_pi_max = 10000
ARQ_CALIB_GAMMA = "calibracao_gamma.csv"
# RC25
# nbv=[4,3,3,3]#R50

ii = 0
tabu = 0

gamma_ini = 40
for i in range(len(tamanhos)):
    tam = tamanhos[i]
    cap = capacidades[0]

    for ninst in range(2, len(todas_instancias)):

        arquivo_instancia = todas_instancias[ninst]

        nome_inst = os.path.basename(arquivo_instancia).lower()
        nome_base = nome_inst.replace(".txt", "").replace("n", "n")
        fo_target_inst = FO_TARGET_50.get(nome_base, -1)

        # =========================
        # Escolha dos gammas por família
        # =========================
        if tam <= 25:
            if nome_inst.startswith("c"):
                lista_gammas = gammas_25_C
            elif nome_inst.startswith("r"):
                lista_gammas = gammas_25_R
            else:
                lista_gammas = [40, 80, 120]
        else:
            if nome_inst.startswith("c"):
                lista_gammas = gammas_50_C
            elif nome_inst.startswith("r"):
                lista_gammas = gammas_50_R
            else:
                lista_gammas = [80, 160, 240]

        # teste gamma max
        # gamma_pi_max

        # for gamma_ini in lista_gammas:
        for gamma_PMAX in gamma_pi_max:

            print("\n############################################")
            # print(f"TESTANDO GAMMA = {gamma_ini}")
            print(f"TESTANDO GAMMA = {gamma_PMAX}")
            print("############################################")

            #FOTAarg = -1
            FOTAarg = fo_target_inst ## FORCANDO FO OTIMA
            TIMETarg = 5000

            print("\n==============================")
            print(
                f"NOVA - tam={tam} cap={cap} VEIC={nbv[ninst]} "
                # f"gamma={gamma_ini} ninst={ninst} INSTANCIA={arquivo_instancia}"
                f"gamma={gamma_PMAX} ninst={ninst} INSTANCIA={arquivo_instancia}"
            )
            print("==============================")

            tem_janelas = 0

            inst = Instancia()
            inst.nbcd = tam
            inst.nbn = tam + 2
            inst.nomeInst = arquivo_instancia
            inst.nbv = nbv[ninst]
            inst.ninst = ninst
            inst.leitura(arquivo_instancia)

            for v in inst.veiculos:
                v.capacidade = cap
                v.velocidade = 10

            metod = Metodos(inst)
            metod.TABU_TENURE = tabu

            solex = Solucao(inst.nbv, inst.nbn)
            solc = Solucao(inst.nbv, inst.nbcd)

            tiex = time.time()
            #metod.metodo_exato(inst, solex)
            tfex = time.time()

            tempo_exato = tfex - tiex
            fo_exato = solex.custo
            seq_exato = solex.sequencias_exato_para_texto()

            print("tempo total exato:", tempo_exato)

            tipo_geracao = "PD"

            for SM in semMelhora:

                inst.nbconstrutiva = 10
                inst.iteraSemMelhora = SM
                random.seed(SEED_DEBUG)

                print("\n--------------------------------------------------")
                print(f"Heurística retirada = {inst.nbconstrutiva}")
                print("--------------------------------------------------")

                sol_pool = Solucao(inst.nbv, inst.nbcd)

                sol_pool.FO_TARGET = FOTAarg
                sol_pool.time_initial = time.time()
                sol_pool.TIME_TARGET = TIMETarg

                sol_pool.gamma_pi = gammas_50_C[0]
                # sol_pool.gamma_pi_inicial = gamma_ini
                sol_pool.gamma_pi_inicial = gammas_50_C[0]
                sol_pool.gamma_pi_min = gamma_pi_min
                sol_pool.gamma_pi_max = gamma_PMAX

                metod.init_pool_vazio(inst, sol_pool)
                metod.gera_rotas_iniciaisUNICA(inst, sol_pool)
                #metod.gera_rotas_iniciais_boas(inst, sol_pool)

                #construtiva com inical inteira
                metod.gera_rotas_iniciais_inteligente_inteira(inst, sol_pool)


                for k in range(inst.nbv):
                    print("veic", k, "rotas iniciais =", len(sol_pool.rotas[k]["sequencia_rota"]))

                t1 = time.time()
                inst.temmip = False

                metod.branch_and_price_global(inst, sol_pool, tipo_geracao=tipo_geracao)

                #################################################################
                melhor_lp_com_slack = sol_pool.melhor_lp_com_slack
                melhor_lp_com_slack_iter = sol_pool.iter_melhor_lp_com_slack

                melhor_lp_valido = sol_pool.melhor_lp_valido
                melhor_lp_valido_iter = sol_pool.iter_melhor_lp_valido

                melhor_int = sol_pool.melhor_inteiro
                melhor_int_iter = sol_pool.iter_melhor_inteiro

                achou_lp_target = sol_pool.achou_lp_target
                achou_int_target = sol_pool.achou_int_target

                iter_lp_target = sol_pool.iter_lp_target
                iter_int_target = sol_pool.iter_int_target

                tempo_lp_target = sol_pool.tempo_lp_target
                tempo_int_target = sol_pool.tempo_int_target

                import math


                def fmt(v):
                    if v is None:
                        return ""
                    if isinstance(v, (int, float)) and math.isinf(v):
                        return ""
                    return v


                print(f"FO_TARGET = {sol_pool.FO_TARGET}")

                print(
                    f"Melhor LP com slack = {fmt(sol_pool.melhor_lp_com_slack)} "
                    f"| iter = {sol_pool.iter_melhor_lp_com_slack} "
                    f"| no = {sol_pool.no_melhor_lp_com_slack}"
                )

                print(
                    f"Melhor LP válido = {fmt(sol_pool.melhor_lp_valido)} "
                    f"| iter = {sol_pool.iter_melhor_lp_valido} "
                    f"| no = {sol_pool.no_melhor_lp_valido}"
                )

                print(
                    f"Melhor inteiro = {fmt(sol_pool.melhor_inteiro)} "
                    f"| iter = {sol_pool.iter_melhor_inteiro} "
                    f"| no = {sol_pool.no_melhor_inteiro}"
                )

                print(
                    f"Achou LP target = {sol_pool.achou_lp_target} "
                    f"| iter = {sol_pool.iter_lp_target} "
                    f"| tempo = {sol_pool.tempo_lp_target} "
                    f"| no = {sol_pool.no_lp_target}"
                )

                print(
                    f"Achou INT target = {sol_pool.achou_int_target} "
                    f"| iter = {sol_pool.iter_int_target} "
                    f"| tempo = {sol_pool.tempo_int_target} "
                    f"| no = {sol_pool.no_int_target}"
                )

                #################################################################

                try:
                    nome_excel = f"convergencia_BP_{nome_inst.replace('.txt', '')}_g{gamma_PMAX}.xlsx"
                    # nome_excel = f"convergencia_BP_{nome_inst.replace('.txt','')}_g{gamma_ini}.xlsx"
                    sol_pool.exportar_convergencia_excel(inst, nome_excel)
                except Exception as e:
                    print(f"Erro ao exportar Excel de convergência: {e}")

                tempo_bp = time.time() - t1

                print(f"Tempo total BP: {tempo_bp:.4f}")

                fo_bp = metod.best_obj
                seq_bp = sol_pool.sequencias_bp_para_texto()
                nos_bp = metod.total_nos
                colunas_bp = metod.total_colunas

                run_id = (
                    f"{nome_inst.replace('.txt', '')}_"
                    f"gmax{gamma_PMAX}_"
                    f"SM{inst.iteraSemMelhora}"
                )

                gap = ""
                if fo_exato not in (None, 0, -1) and fo_bp not in (None, -1):
                    gap = ((fo_bp - fo_exato) / fo_exato) * 100.0

                igual_exato = ""
                if fo_exato not in (None, -1) and fo_bp not in (None, -1):
                    igual_exato = 1 if abs(fo_bp - fo_exato) <= 1e-6 else 0

                if not seq_bp:
                    seq_bp = "SEM_SOLUCAO_BP"

                with open(ARQ_TXT_FINAL, "a", encoding="utf-8") as f:
                    f.write("=" * 120 + "\n")
                    f.write(f"RUN_ID: {run_id}\n")
                    f.write(f"Instância: {arquivo_instancia}\n")
                    f.write(
                        f"Clientes={inst.nbcd} | Nós_rede={inst.nbn} | Veículos={inst.nbv} | "
                        f"Capacidade={cap} | Tabu={tabu} | Heurística_retirada={inst.nbconstrutiva}\n"
                    )
                    f.write(
                        f"Tempo exato={tempo_exato:.4f} | Tempo BP={tempo_bp:.4f} | "
                        f"FO exato={fo_exato:.4f} | FO BP={fo_bp:.4f}\n"
                    )

                    if gap != "":
                        f.write(f"GAP (%) = {gap:.4f}\n")

                    if igual_exato != "":
                        f.write(f"Igual ao exato = {igual_exato}\n")

                    f.write(f"Nós processados BP = {nos_bp}\n")
                    f.write(f"Colunas geradas BP = {colunas_bp}\n")
                    f.write(f"MIP = {inst.temmip}\n")
                    f.write(f"SEM MELHORA = {getattr(inst, 'iteraSemMelhora', '')}\n")
                    f.write(f"SCORE DAS CONSTRUTIBAS BP = {getattr(sol_pool, 'construtivas', '')}\n")
                    f.write(f"SEQ_EXATO: {seq_exato}\n")
                    f.write(f"SEQ_BP: {seq_bp}\n\n")
                    f.write(f"GAMMA PI: {gamma_ini}\n")
                    f.write(f"GAMMA MIN: {gamma_pi_min}\n")
                    f.write(f"GAMMA MAX: {gamma_PMAX}\n")
                    f.write(f"MOTIVO: {getattr(sol_pool, 'motivoConv', '')}\n")
                    f.write(f"ITERAC: {getattr(sol_pool, 'nb_iteracoes', '')}\n\n")
                    f.write(f"ITER SEM MELHORA: {inst.iteraSemMelhora}\n\n")

                    f.write(f"FO_TARGET = {sol_pool.FO_TARGET}\n")
                    f.write(f"Melhor LP com slack = {melhor_lp_com_slack} | iter = {melhor_lp_com_slack_iter}\n")
                    f.write(f"Melhor LP válido = {melhor_lp_valido} | iter = {melhor_lp_valido_iter}\n")
                    f.write(f"Melhor inteiro = {melhor_int} | iter = {melhor_int_iter}\n")
                    f.write(
                        f"Achou LP target = {achou_lp_target} | iter = {iter_lp_target} | tempo = {tempo_lp_target}\n")
                    f.write(
                        f"Achou INT target = {achou_int_target} | iter = {iter_int_target} | tempo = {tempo_int_target}\n")

                with open(ARQ_CSV_FINAL, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f, delimiter=";")

                    w.writerow([
                        run_id,
                        arquivo_instancia,
                        ninst,
                        tem_janelas,
                        inst.nbconstrutiva,
                        inst.nbcd,
                        inst.nbn,
                        inst.nbv,
                        cap,
                        tabu,
                        tipo_geracao,

                        round(tempo_exato, 4),
                        round(tempo_bp, 4),

                        sol_pool.FO_TARGET,
                        round(fo_exato, 4) if fo_exato is not None else "",
                        round(fo_bp, 4) if fo_bp is not None else "",

                        round(melhor_lp_com_slack, 4) if melhor_lp_com_slack != "" else "",
                        melhor_lp_com_slack_iter,

                        round(melhor_lp_valido, 4) if melhor_lp_valido != "" else "",
                        melhor_lp_valido_iter,

                        round(melhor_int, 4) if melhor_int != "" else "",
                        melhor_int_iter,

                        achou_lp_target,
                        iter_lp_target,
                        round(tempo_lp_target, 4) if tempo_lp_target != "" else "",

                        achou_int_target,
                        iter_int_target,
                        round(tempo_int_target, 4) if tempo_int_target != "" else "",

                        round(gap, 4) if gap != "" else "",
                        igual_exato,

                        nos_bp,
                        colunas_bp,

                        inst.temmip,
                        getattr(inst, "iteraSemMelhora", ""),

                        gamma_ini,
                        gamma_pi_min,
                        gamma_PMAX,

                        getattr(sol_pool, "motivoConv", ""),
                        getattr(sol_pool, "nb_iteracoes", ""),

                        getattr(no_raiz, "cg_convergiu", ""),
                        getattr(no_raiz, "solucao_inteira", ""),
                        getattr(no_raiz, "lb_confiavel", ""),
                        getattr(no_raiz, "slack_sum_final", ""),

                        seq_exato,
                        seq_bp,

                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])
                existe_calib = os.path.exists(ARQ_CALIB_GAMMA)

                with open(ARQ_CALIB_GAMMA, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f, delimiter=";")

                    if not existe_calib:
                        w.writerow([
                            "run_id",
                            "instancia",
                            "familia",
                            "clientes",
                            "veiculos",
                            "capacidade",
                            "gamma_ini",
                            "gamma_min",
                            "gamma_max",
                            "tempo_bp",
                            "fo_bp",
                            "nos_bp",
                            "colunas_bp",
                            "iteracoes",
                            "motivo",
                            "sem_melhora",
                            "score_construtivas",
                            "timestamp"
                        ])

                    w.writerow([
                        run_id,
                        arquivo_instancia,
                        nome_inst[0].upper(),
                        inst.nbcd,
                        inst.nbv,
                        cap,
                        gamma_ini,
                        gamma_pi_min,
                        gamma_pi_max,
                        round(tempo_bp, 4),
                        round(fo_bp, 4) if fo_bp is not None else "",
                        nos_bp,
                        colunas_bp,
                        getattr(sol_pool, "nb_iteracoes", ""),
                        getattr(sol_pool, "motivoConv", ""),
                        getattr(inst, "iteraSemMelhora", ""),
                        getattr(sol_pool, "construtivas", ""),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])

                print("")

# metod.geracao_colunas(inst, solc,tipo_geracao)


tfseq = time.time()

solex.printar_sol_exata(inst)
solex.registrar_fo_gc(inst, solex.custo)

solc.exportar_json_gc(inst, "solucao_gcm.json")

print("\n tempo total exato:", tfex - tiex)
# print("\n tempo total gc:", tfseq - tiseq)
# print("\n tempo total diff:", ((tfex - tiex) - (tfseq - tiseq)) / (tiex - tfex))


