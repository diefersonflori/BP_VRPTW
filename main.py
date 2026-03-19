import sys
import time
from instancia import Instancia
from solucao import Solucao
from metodos import Metodos

from metodos import Metodos, NoBP



ARQ_SAIDA = "resultados_experimentos.txt"

with open(ARQ_SAIDA, "w", encoding="utf-8") as f:
    f.write("tamanho;capacidade;tabu;tempo_exato;\ntempo_bp;fo_exato;\nfo_bp;nos_bp;colunas_bp\n")


#tamanhos=[4,7,13]#,20,25]
#capacidades=[36,70,110]#,200,200]
tamanhos=[13]#,20,25]
capacidades=[110]#,200,200]
#capacidades~ 60% do total das demandas

#tamanhos=[16]#,20,25]
#capacidades=[150]#,200,200]
#tamanhos=[20]#,25]
#capacidades=[200]#,200]
#N_TABUS=[3,4,5]
N_TABUS=[0,1,2,3]

for i in range(len(tamanhos)):
    tam=tamanhos[i]
    cap=capacidades[i]
    for tabu in N_TABUS:
        print("\n==============================")
        print(f"Teste tam={tam} cap={cap} tabu={tabu}")
        print("==============================")

        inst = Instancia()
        inst.nbcd = tam
        inst.nbn = tam + 2

        inst.leitura("instancias/R102.txt")
        #inst.leitura("instancias/r207.txt")
        #inst.leitura("instancias/c101.txt")

        for v in inst.veiculos:
            v.capacidade = cap
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


        # pool global de colunas
        sol_pool = Solucao(inst.nbv, inst.nbcd)
        metod.init_pool_vazio(inst, sol_pool)
        #metod.gera_rotas_iniciaisUNICA(inst, sol_pool)

        #sol_ini = metod.solucao_inicial_gulosa(inst, alpha=5, tentativas=30)


        #cobertos, nrot = metod.gerar_pool_inicial_por_seeds(inst, sol_pool)

        metod.gera_rotas_iniciaisUNICA(inst, sol_pool)

        for k in range(inst.nbv):
            print("veic", k, "rotas iniciais =", len(sol_pool.rotas[k]['sequencia_rota']))


        t1=time.time()
        metod.branch_and_price_global(inst,sol_pool, tipo_geracao="PD")
        tempo_bp=time.time()-t1
        print(f"Tempo total BP: {tempo_bp}")

        fo_bp = metod.best_obj
        seq_bp = sol_pool.sequencias_bp_para_texto()

        nos_bp = metod.total_nos

        colunas_bp = metod.total_colunas

        with open(ARQ_SAIDA, "a", encoding="utf-8") as f:
            linha = (
                f"{tam};{cap};{tabu};"
                f"{nos_bp};{colunas_bp}\n"
                f"{tempo_exato:.4f};{tempo_bp:.4f};\n"
                f"{fo_exato:.4f};{fo_bp:.4f};\n"
            )
            f.write(linha)
            f.write(f"SEQ_EXATO: {seq_exato}\n")
            f.write(f"SEQ_BP: {seq_bp}\n")
            f.write("=" * 120 + "\n")

metod.geracao_colunas(inst, solc,tipo_geracao)



tfseq = time.time()

solex.printar_sol_exata(inst)
solex.registrar_fo_gc(inst,solex.custo)

solc.exportar_json_gc(inst, "solucao_gcm.json")

print("\n tempo total exato:", tfex - tiex)
print("\n tempo total gc:", tfseq - tiseq)
print("\n tempo total diff:", ((tfex - tiex) - (tfseq - tiseq)) / (tiex - tfex))


