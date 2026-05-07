import sys
import time
import csv
import random
from datetime import datetime

from instancia import Instancia
from solucao import Solucao
from metodos import Metodos, NoBP

SEED_DEBUG = 123
#SEED_DEBUG = 9999

ARQ_CSV_FINAL = "resultados_finais.csv"
ARQ_TXT_FINAL = "resultados_finais_legivel.txt"

import os
import sys

#sys.stdout = open(os.devnull, 'w')
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
#tamanhos=[4,7,13]#,20,25]
#capacidades=[36,70,110]#,200,200]
#tamanhos=[13]#,20,25]
#capacidades=[110]#,200,200]
#capacidades~ 60% do total das demandas

#tamanhos=[16]#,25]
#capacidades=[150]#,200]
tamanhos=[25]
capacidades=[200]

#tamanhos=[16,20]#,25]
#capacidades=[150,200]#,200]
#tamanhos=[20,25]
#capacidades=[200,200]
#tamanhos=[20]
#capacidades=[200]
nbvv=[3,5]
#N_TABUS=[3,4,5]
N_TABUS=[0]#,1,2,3]
#combinacao_construtivas=[1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
#combinacao_construtivas=[10]#,0,1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
combinacao_construtivas=[10]#10 só pra testar ta ligado? quero tirar ninguem não fióti
#combinacao_construtivas=[0,1,2,3,22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
#combinacao_construtivas=[22]#10 só pra testar ta ligado? quero tirar ninguem não fióti
#combinacao_construtivas=[10]#10 só pra testar ta ligado? quero tirar ninguem não fióti


#todas_instancias = ["instancias/r110.txt"]
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
"instancias/c201.txt","instancias/c202.txt",
#C25
#"""

todas_instancias = ["instancias/c101N.txt","instancias/c102.txt","instancias/c103.txt",
                     "instancias/c104.txt","instancias/c105.txt","instancias/c106.txt", "instancias/c107.txt",
                     "instancias/c108.txt", "instancias/c109.txt","instancias/r101.txt","instancias/r102.txt",
                     "instancias/r103.txt","instancias/r104.txt",
                     "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                     "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                     "instancias/r111.txt","instancias/r112.txt"]

nbv=[3,3,3,3,3,3,3,3,3]#C25
#"""
#R25
"""
todas_instancias = (["instancias/r101.txt","instancias/r102.txt","instancias/r103.txt","instancias/r104.txt",
                      "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                      "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                      "instancias/r111.txt","instancias/r112.txt"])
nbv=[8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25
"""
#todas_instancias = (["instancias/c103.txt"])
"""    
"instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
"instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt",
"instancias/c208.txt"]
"""
#todas_instancias = (["instancias/c101N.txt","instancias/c102.txt","instancias/c103.txt",
#                     "instancias/c104.txt","instancias/c105.txt","instancias/c106.txt", "instancias/c107.txt",
#                    "instancias/c108.txt", "instancias/c109.txt"])

#C50
"""
todas_instancias = ["instancias/c101N.txt",
                    "instancias/c102.txt", "instancias/c103.txt","instancias/c105.txt", "instancias/c106.txt",
                    "instancias/c107.txt", "instancias/c108.txt"]#,
nbv=[5,5,4,5,5,5,5]#C50
"""

#R50
#"""
"""
todas_instancias = (["instancias/r101.txt","instancias/r102.txt","instancias/r103.txt",
                      "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                     "instancias/r110.txt"])
"""
#RC25
#todas_instancias = (["instancias/rc101.txt","instancias/rc102.txt","instancias/rc103.txt",
#                      "instancias/rc104.txt","instancias/rc105.txt","instancias/rc106.txt","instancias/rc107.txt",
#                     "instancias/rc108.txt"])
#nbv=[4,3,3,3,4,3,3,3]


"""
#TODES 50
todas_instancias = (["instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt","instancias/c104.txt","instancias/c105.txt", "instancias/c106.txt",
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
                     "instancias/rc204.txt", "instancias/rc205.txt", "instancias/rc206.txt", "instancias/rc207.txt"])
#nbv=[5,5,5,5,5,5,5,5,5,11,9,6,9,6,7,6,8,7,7,6,8,7,6,5,8,6,6,
#6,3,3,3,2,3,3,3,2,6,5,5,2,4,4,2,2,4,4,3,5,5,4,3,5,5,4]
nbv=[5,5,5,5,5,5,5,5,5,12,11,9,6,9,6,7,6,8,7,7,6,8,7,6,5,8,6,6,6,3,3,3,2,3,3,3,2,6,5,5,2,4,4,2,2,4,4,3,5,5,4,3,5,5,4,]

"""

#R50
#nbv=[12,11,9,9,8,7,7]#R50
#"""
#"""
#todas_instancias = ["instancias/c104.txt"]
#nbv=[3]
ab=1
semMelhora=[0]#,2,4,6,8]
#instancais grandes
#nbv=[4]#25

#VALORES OTIMOS FO C25
"""
nbv=[3,3,3,3,3,3,3,3,3]#C25
todas_instancias = (["instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt","instancias/c104.txt","instancias/c105.txt", "instancias/c106.txt",
                    "instancias/c107.txt", "instancias/c108.txt", "instancias/c109.txt"])
"""

#FOTARGET=[191.3,190.3,190.3,186.9,191.3,191.3,191.3,191.3,191.3]
#TIMETARGET=[18.6,79.7,134.7,223.9,25.6,20.7,31.7,43.1,585.4]


#VALORES OTIMOS FO R25
#FOTARGET=[617.1, 547.1, 454.6, 416.9, 530.5, 467.4, 424.3, 397.2, 441.3, 429.5, 428.8, 393]
#TIMETARGET=[5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4, 14.4, 64.3, 330, 623.3]
#nbv=[8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25

#FOTARGET=[617.1, 547.1, 454.6, 416.9, 530.5, 467.4, 424.3, 397.2, 441.3, 429.5, 428.8, 393]
#TIMETARGET=[18.6,79.7,134.7,223.9,25.6,20.7,31.7,43.1,585.4,5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4, 14.4, 64.3, 330, 623.3]
#nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25

FOTARGET=[]
TIMETARGET=[18.6,79.7,134.7,223.9,25.6,20.7,31.7,43.1,585.4,5.8, 20.3, 22.2, 46, 22.6, 205.2, 304.1, 307.4, 14.4, 64.3, 330, 623.3]
#nbv=[3,3,3,3,3,3,3,3,3,8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]#R25


#RC25
#nbv=[4,3,3,3]#R50

ii=0
tabu=0
for i in range(len(tamanhos)):
    tam=tamanhos[i]
    cap=capacidades[0]
    #nbv_atual = nbvv[i]


    for tt in range(1):

        for ninst in range (len(todas_instancias)):

            arquivo_instancia=todas_instancias[ninst]

            FOTAarg = -1
            TIMETarg = 99999999
            if(tt==2):#agora nao sera- quero testar só normal e time
                FOTAarg=FOTARGET[ninst]

            if(tt==1):
                TIMETarg=TIMETARGET[ninst]

            print("\n==============================")
            print(f" NOVA- tam={tam} cap={cap}  VEIC = {nbv[ninst]} FOTAarg={FOTAarg} TIMETarg={TIMETarg} ninst={ninst} INSTANCIA={arquivo_instancia} FO TARGET= {FOTAarg}")
            print("==============================")


            tem_janelas=0
            inst = Instancia()
            inst.nbcd = tam
            inst.nbn = tam + 2
            inst.nomeInst=arquivo_instancia
            #inst.nbv = nbv_atual
            #inst.nbv = nbv[0]
            inst.nbv = nbv[ninst]

            inst.ninst = ninst

            """
            if ninst == 0:
                arquivo_instancia = "instancias/c101N.txt"
                tem_janelas = 1
                print("$$$$$$$$$$$$$$$$$$$$$$$$$$ COM janelas")
            else:
                arquivo_instancia = "instancias/c101_multpJan_open.txt"
                tem_janelas = 0
                print("$$$$$$$$$$$$$$$$$$$$$$$$$$ sem janelas")
            """
            #inst.leitura("instancias/R102 - Copia.txt")
            #inst.leitura("instancias/r207.txt")
            #inst.leitura("instancias/c101.txt")
            inst.leitura(arquivo_instancia)


            for v in inst.veiculos:
                v.capacidade = cap
                v.velocidade=10
            # Métodos
            metod = Metodos(inst)
            metod.TABU_TENURE = tabu

            solex = Solucao(inst.nbv, inst.nbn)
            solc = Solucao(inst.nbv, inst.nbcd)
            solBP= Solucao(inst.nbv, inst.nbcd)



            tiex = time.time()
            metod.metodo_exato(inst, solex)
            tfex = time.time()
            #solex.exportar_json(inst, "solucao_ex.json")
            #solex.printar_sol_exata(inst)
            tempo_exato = time.time() - tiex
            fo_exato = solex.custo
            seq_exato = solex.sequencias_exato_para_texto()
            print("tempo total exato:", tfex - tiex)

            tipo_geracao="PD"
            #tipo_geracao="GUROBI"
            #metod.geracao_colunas(inst, solc,tipo_geracao)

            #for construtiva in combinacao_construtivas:
                #inst.nbconstrutiva = construtiva
            for SM in semMelhora:
                inst.nbconstrutiva = 10
                #inst.iteraSemMelhora=

                random.seed(SEED_DEBUG)

                print("\n--------------------------------------------------")
                print(f"Heurística retirada = {inst.nbconstrutiva}")
                print("--------------------------------------------------")

                # log local do BP desta rodada
                nome_arquivo_log = f"log_bounds_{inst.nbcd}_{ninst}_C_Can_{inst.nbconstrutiva}.csv"
                with open(nome_arquivo_log, "w", encoding="utf-8") as f:
                    f.write("no_id;z_inc;z_lp;z_li;total_colunas\n")

                # pool global de colunas
                sol_pool = Solucao(inst.nbv, inst.nbcd)
                #recebe FO TARGET
                sol_pool.FO_TARGET=FOTAarg
                sol_pool.time_initial=time.time()
                sol_pool.TIME_TARGET=TIMETarg

                metod.init_pool_vazio(inst, sol_pool)
                metod.gera_rotas_iniciaisUNICA(inst, sol_pool)
                #metod.gera_rotas_iniciais_geometricas(inst, sol_pool, n_starts=10, max_rotas_por_k=25)

                metod.gera_rotas_iniciais_boas(inst, sol_pool)
                #metod.gerar_rotas_unitarias_insercao(inst, sol_pool, custo_art=100000, remover_base=False)

                for k in range(inst.nbv):
                    print("veic", k, "rotas iniciais =", len(sol_pool.rotas[k]["sequencia_rota"]))

                # =========================
                # Branch-and-Price
                # =========================
                #teste para com e sem mip
                for j in range(1):
                    #print(f"JJJJ {j}")

                    #if j==0:
                    #    inst.temmip=True
                    #else:
                    #    inst.temmip=False

                    t1 = time.time()
                    inst.temmip = False


                    metod.branch_and_price_global(inst, sol_pool, tipo_geracao=tipo_geracao)
                    sol_pool.exportar_convergencia_excel(inst, "convergencia_BP.xlsx")

                    #metod.SearchCOl_global(inst, sol_pool, tipo_geracao=tipo_geracao)

                    tempo_bp = time.time() - t1

                    print(f"Tempo total SC: {tempo_bp:.4f}")

                    fo_bp = metod.best_obj
                    seq_bp = sol_pool.sequencias_bp_para_texto()
                    nos_bp = metod.total_nos
                    colunas_bp = metod.total_colunas

                    # =========================
                    # Pós-processamento
                    # =========================
                    run_id = f"tam{tam}_cap{cap}_tabu{tabu}_inst{ninst}_cons{inst.nbconstrutiva}"

                    gap = ""
                    if fo_exato not in (None, 0, -1) and fo_bp not in (None, -1):
                        gap = ((fo_bp - fo_exato) / fo_exato) * 100.0

                    igual_exato = ""
                    if fo_exato not in (None, -1) and fo_bp not in (None, -1):
                        igual_exato = 1 if abs(fo_bp - fo_exato) <= 1e-6 else 0

                    if not seq_bp:
                        seq_bp = "SEM_SOLUCAO_BP"

                    # =========================
                    # TXT legível
                    # =========================
                    with open(ARQ_TXT_FINAL, "a", encoding="utf-8") as f:
                        f.write("=" * 120 + "\n")
                        f.write(f"RUN_ID: {run_id}\n")
                        f.write(f"Instância: {arquivo_instancia}\n")
                        f.write(
                            f"Clientes={inst.nbcd} | Nós_rede={inst.nbn} | Veículos={inst.nbv} | "
                            f"Capacidade={cap} | Tabu={tabu} | Heurística_retirada={inst.nbconstrutiva}\n"
                        )
                        #fo_exato=-1
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
                        f.write(f"SEM MELHORA = {inst.iteraSemMelhora}\n")
                        f.write(f"SCORE DAS CONSTRUTIBAS BP = {sol_pool.construtivas}\n")
                        f.write(f"SEQ_EXATO: {seq_exato}\n")
                        f.write(f"SEQ_BP: {seq_bp}\n\n")
                        f.write(f"MOTIVO: {sol_pool.motivoConv}\n\n")


                    # =========================
                    # CSV final
                    # =========================
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
                            round(fo_exato, 4) if fo_exato is not None else "",
                            round(fo_bp, 4) if fo_bp is not None else "",
                            round(gap, 4) if gap != "" else "",
                            igual_exato,
                            nos_bp,
                            colunas_bp,
                            inst.temmip,
                            inst.iteraSemMelhora,
                            seq_exato,
                            seq_bp,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])

                    print("")

                ab=0


#metod.geracao_colunas(inst, solc,tipo_geracao)



tfseq = time.time()

solex.printar_sol_exata(inst)
solex.registrar_fo_gc(inst,solex.custo)

solc.exportar_json_gc(inst, "solucao_gcm.json")

print("\n tempo total exato:", tfex - tiex)
#print("\n tempo total gc:", tfseq - tiseq)
#print("\n tempo total diff:", ((tfex - tiex) - (tfseq - tiseq)) / (tiex - tfex))


