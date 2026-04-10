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

#import os
#import sys

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


# todas_instancias = ["instancias/c101N.txt"]
"""
todas_instancias = [ "instancias/c105.txt", "instancias/c106.txt", "instancias/c107.txt",
                    "instancias/c108.txt", "instancias/c109.txt"]#,
"""
"""
"instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",
todas_instancias = [ "instancias/c203.txt", "instancias/c204.txt",
                    "instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt"]
"""
"instancias/c201.txt","instancias/c202.txt",
#"""
"""

                  ,
                  "instancias/r103.txt","instancias/r104.txt",
                  "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                  "instancias/r108.txt"]
#"""

todas_instancias = (["instancias/c101N.txt"])
"""
todas_instancias = (["instancias/r101.txt","instancias/r102.txt","instancias/r103.txt","instancias/r104.txt",
#"""
"""
                      "instancias/r105.txt","instancias/r106.txt","instancias/r107.txt",
                      "instancias/r108.txt","instancias/r109.txt","instancias/r110.txt",
                      "instancias/r111.txt","instancias/r112.txt",
                     "instancias/c101N.txt","instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",])
    ,)
"instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
"instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt",
"instancias/c208.txt"]
"""

#"""
#todas_instancias = ["instancias/c104.txt"]
#nbv=[3]
ab=1
semMelhora=[0]#,2,4,6,8]
#instancais grandes
#nbv=[8,7,5,4,6,5,4,4,5,4,4,4,3,3,3,3,3,3,3,3,3,3]
nbv=[3,3,3,3,3,3,3,3,3]
for i in range(len(tamanhos)):
    tam=tamanhos[i]
    cap=capacidades[0]
    #nbv_atual = nbvv[i]


    for tabu in N_TABUS:
        ii=0
        for arquivo_instancia in (todas_instancias):
            ninst=0

            print("\n==============================")
            print(f"Teste tam={tam} cap={cap} tabu={tabu} ninst={ninst}")
            print("==============================")

            tem_janelas=0
            inst = Instancia()
            inst.nbcd = tam
            inst.nbn = tam + 2
            #inst.nbv = nbv_atual
            inst.nbv = nbv[ii]
            #inst.nbv = nbv[ninst]
            ii+=1
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
            #metod.metodo_exato(inst, solex)
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
                inst.iteraSemMelhora=SM

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
                metod.init_pool_vazio(inst, sol_pool)
                metod.gera_rotas_iniciaisUNICA(inst, sol_pool)

                for k in range(inst.nbv):
                    print("veic", k, "rotas iniciais =", len(sol_pool.rotas[k]["sequencia_rota"]))

                # =========================
                # Branch-and-Price
                # =========================
                #teste para com e sem mip
                for j in range(1):
                    #print(f"JJJJ {j}")
                    if j==0:
                        inst.temmip=False
                    else:
                        inst.temmip=True

                    t1 = time.time()
                    metod.branch_and_price_global(inst, sol_pool, tipo_geracao=tipo_geracao)
                    tempo_bp = time.time() - t1

                    print(f"Tempo total BP: {tempo_bp:.4f}")

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


