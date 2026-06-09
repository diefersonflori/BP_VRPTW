import random
import copy
import time
import gurobipy as gp
from asyncssh.asn1 import BOOLEAN
from gurobipy import GRB, quicksum
from sipbuild.generator.parser.annotations import boolean
import datetime
import os
import csv
from datetime import datetime

from sqlalchemy import false

from instancia import Instancia
from solucao import Solucao

PRINT_ROTAS_INICIAIS = True
PRINT_ROTAS_GC = True


class Metodos:

    def metodo_exato(self, inst, sol):
        print("==================== Iniciando a resolução do modelo exato")
        K = range(inst.nbv)  # Veículos
        V = list(range(inst.nbn))  # Nós (depósito + clientes + depósito final)
        clientes = list(range(1, inst.nbn - 1)) # clientes devem ser 1..n-2

        model = gp.Model('VRPTW_Exato')

        # Variáveis de decisão
        x = model.addVars(V, V, K, vtype=GRB.BINARY, name='x')
        s = model.addVars(V, K, vtype=GRB.CONTINUOUS, name='s')  # Tempo de chegada do veículo k em nó i
        u = model.addVars(V, K, vtype=GRB.CONTINUOUS, name='u')  # Carga do veículo k ao chegar em i

        READY_TIME = {i: inst.noh[i].READY_TIME[0] if len(inst.noh[i].READY_TIME) > 0 else 0 for i in V}
        DUE_DATE = {i: inst.noh[i].DUE_DATE[0] if len(inst.noh[i].DUE_DATE) > 0 else (
                print(f"i={i} não tem DUE_DATE definida, usando 9999") or 9999)
                    for i in V}



        # Função objetivo: minimizar tempo total percorrido
        model.setObjective(
            gp.quicksum(inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade * x[i, j, k]
                        for k in K for i in V for j in V if i != j),
            GRB.MINIMIZE
        )
        #model.Params.TimeLimit = 150
        """
        T_retorno = model.addVar(vtype=GRB.CONTINUOUS, name='T_retorno')
        model.addConstr(
            T_retorno == gp.quicksum(s[inst.nbn - 1, k] for k in K),
            name="soma_retornos"
        )
        model.setObjective(T_retorno, GRB.MINIMIZE)
        """

        # Cada cliente visitado exatamente uma vez
        for i in clientes:
            model.addConstr(gp.quicksum(x[j, i, k] for j in V if j != i for k in K) == 1, f'entrada_{i}')
            model.addConstr(gp.quicksum(x[i, j, k] for j in V if j != i for k in K) == 1, f'saida_{i}')

        # Cada veículo sai do depósito de origem (0) e chega no depósito final (inst.nbn-1)
        for k in K:
            model.addConstr(gp.quicksum(x[0, j, k] for j in clientes + [inst.nbn - 1]) == 1, f'saida_deposito_{k}')
            model.addConstr(gp.quicksum(x[j, inst.nbn - 1, k] for j in [0] + clientes) == 1, f'retorno_deposito_{k}')

        # Restrições de fluxo de continuidade para clientes
        for k in K:
            for i in clientes:
                model.addConstr(
                    gp.quicksum(x[j, i, k] for j in V if j != i) ==
                    gp.quicksum(x[i, j, k] for j in V if j != i),
                    f'continuidade_{i}_{k}'
                )

        # Restrições de capacidade e fluxo de carga
        for k in K:
            Q = inst.veiculos[k].capacidade
            model.addConstr(u[0, k] == 0, name=f"carga_deposito_{k}")
            for i in V:
                model.addConstr(u[i, k] <= Q, name=f'capacidade_max_{i}_{k}')
                for j in clientes:
                    if i != j:
                        demand_j = inst.noh[j].DEMAND
                        model.addConstr(
                            u[j, k] >= u[i, k] + demand_j - Q * (1 - x[i, j, k]),
                            name=f'fluxo_carga_{i}_{j}_{k}'
                        )

        #  janelas de tempo
        BIG_M = 1e5
        for k in K:
            # Início no depósito
            model.addConstr(s[0, k] == 0, f'inicio_zero_{k}')
            for i in V:
                # Respeitar as janelas de tempo para cada nó/cliente (primeira janela sempre)
                model.addConstr(s[i, k] >= READY_TIME[i], f'tw_inicio_{i}_{k}')
                model.addConstr(s[i, k] <= DUE_DATE[i], f'tw_fim_{i}_{k}')
                for j in V:
                    if i != j:
                        service = inst.noh[i].SERVICE_TIME[0] if hasattr(inst.noh[i], 'SERVICE_TIME') and inst.noh[i].SERVICE_TIME else 0
                        travel = inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade
                        model.addConstr(
                            s[i, k] + service + travel <= s[j, k] + BIG_M * (1 - x[i, j, k]),
                            f'tempo_chegada_{i}_{j}_{k}'
                        )

        model.write("modelo.lp")
        model.optimize()

        # Extração da solução, preenche bin_visitas para compatibilidade com sua estrutura
        if model.status == GRB.OPTIMAL:
            # --- RESULTADOS DETALHADOS ---

            resultados_veiculos = []

            for k in K:
                # Reconstrói a rota do veículo
                rota_seq = [0]
                current = 0
                while True:
                    prox_nos = [j for j in V if j != current and x[current, j, k].X > 0.5]
                    if not prox_nos:
                        break
                    next_node = prox_nos[0]
                    rota_seq.append(next_node)
                    current = next_node
                    if current == inst.nbn - 1:
                        break

                print(f"\n== Veículo {k} ==")
                print("Rota: " + " -> ".join(str(n) for n in rota_seq))
                print(f"{'Nó':>4} | {'Chegada':>8} | {'Saída':>8} | {'Carga_in':>9} | {'Carga_out':>9}")

                for idx, node in enumerate(rota_seq):
                    chegada = s[node, k].X
                    carga_in = u[node, k].X
                    servico = inst.noh[node].SERVICE_TIME[0] if hasattr(inst.noh[node], 'SERVICE_TIME') and inst.noh[
                        node].SERVICE_TIME else 0
                    saida = chegada + servico
                    if idx < len(rota_seq) - 1:
                        next_node = rota_seq[idx + 1]
                        if next_node == inst.nbn - 1:
                            carga_out = 0.0
                        else:
                            carga_out = u[next_node, k].X
                    else:
                        carga_out = "-"
                    print(f"{node:>4} | {chegada:8.2f} | {saida:8.2f} | {carga_in:9.2f} | {str(carga_out):>9}")
                    resultados_veiculos.append({
                        'veiculo': k,
                        'no': node,
                        'chegada': chegada,
                        'saida': saida,
                        'carga_in': carga_in,
                        'carga_out': carga_out
                    })


            print("Solução encontrada com sucesso!")
            for k in K:
                for i in V:
                    for j in V:
                        if i != j and x[i, j, k].X > 0.5:
                            sol.bin_visitas[k][i][j] = 1
                            print(f"x[{k}][{i}][{j}] = 1")

            # Reconstrução das rotas para exportação
            for k in K:
                rota_seq = [0]
                current = 0
                while True:
                    prox_nos = [j for j in V if j != current and x[current, j, k].X > 0.5]
                    if not prox_nos:
                        break
                    next_node = prox_nos[0]
                    rota_seq.append(next_node)
                    current = next_node
                    if current == inst.nbn - 1:
                        break

                if k not in sol.rotas:
                    sol.rotas[k] = {
                        'rotas_binaria': [],
                        'sequencia_rota': [],
                        'custo': [],
                        'vezes_usada_geral': []
                    }

                # Cria vetor binário
                binaria = [0] * inst.nbcd
                for cliente in rota_seq:
                    if 1 <= cliente <= inst.nbcd:
                        binaria[cliente - 1] = 1

                # Custo da rota
                custo = sum(
                    inst.matriz_distancia[rota_seq[i]][rota_seq[i + 1]] / inst.veiculos[k].velocidade
                    for i in range(len(rota_seq) - 1)
                )

                sol.rotas[k]['rotas_binaria'].append(binaria)
                sol.rotas[k]['sequencia_rota'].append(rota_seq)
                sol.rotas[k]['custo'].append(custo)


        else:
            print("Nenhuma solução ótima encontrada")

    def gera_rotas_iniciais(self, inst,sol):
        rotas = {}
        nb_rotas = 40
        for ii in range(inst.nbv):  # Para cada veículo
            rotas_binaria = []  # Cada lista vai ter nb_rotas listas
            sequencia_rota = []
            custos = []
            vezes_usada_geral = []
            vezes_usada_otimo = []
            lbd_iteracao = []

            valor_lbd=[]
            for r in range(nb_rotas):
                # Gera os clientes visitados
                clientes = list(range(1, inst.nbcd + 1))
                random.shuffle(clientes)
                n_clientes_rota = random.randint(1, inst.nbcd-2)
                visitados = clientes[:n_clientes_rota]

                # Rotas binárias
                binaria = [0] * inst.nbcd
                for cli in visitados:
                    binaria[cli - 1] = 1
                rotas_binaria.append(binaria)

                # Sequência completa, incluindo depósito inicial/final
                rota_seq = [0] + visitados + [inst.nbn - 1]
                sequencia_rota.append(rota_seq)

                # Cálculo do custo
                cost = 0
                for i in range(len(rota_seq) - 1):
                    no_atual = rota_seq[i]
                    prox_no = rota_seq[i + 1]
                    cost += inst.matriz_distancia[no_atual][prox_no] / inst.veiculos[ii].velocidade

                cost=cost
                custos.append(cost)
                vezes_usada_geral.append(0)
                vezes_usada_otimo.append(0)
                valor_lbd.append(0)

            lbd_iteracao.append(valor_lbd)
            # Adiciona no dicionário
            rotas[ii] = {
                'rotas_binaria': rotas_binaria,
                'sequencia_rota': sequencia_rota,
                'custo': custos,
                'vezes_usada_geral': vezes_usada_geral,
                'vezes_usada_otimo': vezes_usada_otimo,
                'lbd_iteracao': lbd_iteracao
            }

        sol.rotas=rotas

        return rotas

    def gera_rotas_iniciaisUNICA(self, inst, sol, custo_alto=1e7):

        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))

        sol.rotas = {}

        for k in range(inst.nbv):
            # inicializa listas para o veículo k
            sol.rotas[k] = {
                'rotas_binaria': [],
                'sequencia_rota': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': [],
            }

            # === Rota cheia (coluna artificial forte) ===
            random.shuffle(clientes)
            rota_cheia = [0] + clientes[:] + [depf]

            bin_cheia = [1] * inst.nbcd  # marca que cobre todos os clientes
            sol.rotas[k]['rotas_binaria'].append(bin_cheia)
            sol.rotas[k]['sequencia_rota'].append(rota_cheia)
            sol.rotas[k]['custo'].append(custo_alto)
            sol.rotas[k]['vezes_usada_geral'].append(0)
            sol.rotas[k]['vezes_usada_otimo'].append(0)
            sol.rotas[k]['lbd_iteracao'].append([])

            # === Rota nula (não atende ninguém) ===
            rota_nula = [0, depf]
            bin_nula = [0] * inst.nbcd

            sol.rotas[k]['rotas_binaria'].append(bin_nula)
            sol.rotas[k]['sequencia_rota'].append(rota_nula)
            sol.rotas[k]['custo'].append(0.0)
            sol.rotas[k]['vezes_usada_geral'].append(0)
            sol.rotas[k]['vezes_usada_otimo'].append(0)
            sol.rotas[k]['lbd_iteracao'].append([])

        return sol.rotas

    def gera_rotas_artificiais(self, inst, sol, custo_alto=100000):

        rotas = {k: {
            'rotas_binaria': [],
            'sequencia_rota': [],
            'custo': [],
            'vezes_usada_geral': [],
            'vezes_usada_otimo': [],
            'lbd_iteracao': [[]]
        } for k in range(inst.nbv)}

        depot_fim = inst.nbn - 1
        for idx_i, i in enumerate(range(1, inst.nbcd + 1)):
            k = idx_i % inst.nbv  # distribui clientes entre veículos
            seq = [0, i, depot_fim]
            binaria = [0] * inst.nbcd
            binaria[i - 1] = 1

            rotas[k]['rotas_binaria'].append(binaria)
            rotas[k]['sequencia_rota'].append(seq)
            rotas[k]['custo'].append(float(custo_alto))
            rotas[k]['vezes_usada_geral'].append(0)
            rotas[k]['vezes_usada_otimo'].append(0)
            rotas[k]['lbd_iteracao'][0].append(0)

        sol.rotas = rotas
        # Se você usa sol.numero_de_rotas depois:
        sol.numero_de_rotas = [len(sol.rotas[k]['rotas_binaria']) for k in sol.rotas.keys()]
        return rotas

    def gerar_rotas_unitarias_insercao(self, inst, sol, custo_art=0, remover_base=True):
        """
        Uma coluna por cliente. Distribui rotas entre veículos de forma balanceada:
        prioriza o veículo com menos colunas; em empate, menor custo real.
        """
        nbcd = inst.nbcd
        nbn = inst.nbn
        depf = nbn - 1

        def travel(k, i, j):
            return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

        def custo_seq(k, seq):
            return sum(travel(k, seq[t], seq[t + 1]) for t in range(len(seq) - 1))

        # base [0, dep] por veículo
        sol.rotas = {}
        for k in range(inst.nbv):
            base = [0, depf]
            sol.rotas[k] = {
                'sequencia_rota': [base[:]],
                'rotas_binaria': [[0] * nbcd],
                'custo': [custo_seq(k, base)],
                'vezes_usada_geral': [0],
                'vezes_usada_otimo': [0],
                'lbd_iteracao': [[]],
                'artificial': [False],
            }

        # contador de colunas por veículo (exclui a base)
        colunas_por_k = [0] * inst.nbv

        for i in range(1, nbcd + 1):
            candidatos = []  # (colunas_por_k[k], custo_real, k, rota, s, u)

            for k in range(inst.nbv):
                # garante base intacta
                sol.rotas[k]['sequencia_rota'][0] = [0, depf]
                res = sol.inserir_cliente_rota(inst, k=k, cliente=i, pos=1)
                if res.get('factivel'):
                    rota_i = res['rota']  # [0, i, depf]
                    custo_i = custo_seq(k, rota_i)  # custo real
                    candidatos.append((colunas_por_k[k], custo_i, k, rota_i, res['s'], res['u']))

            if candidatos:
                # ordena por (menos colunas, menor custo)
                candidatos.sort(key=lambda x: (x[0], x[1]))
                _, _, kbest, rota_i, _, _ = candidatos[0]

                binaria = [0] * nbcd
                binaria[i - 1] = 1

                sol.rotas[kbest]['sequencia_rota'].append(rota_i)
                sol.rotas[kbest]['rotas_binaria'].append(binaria)
                sol.rotas[kbest]['custo'].append(custo_seq(kbest, rota_i))
                sol.rotas[kbest]['vezes_usada_geral'].append(0)
                sol.rotas[kbest]['vezes_usada_otimo'].append(0)
                sol.rotas[kbest]['lbd_iteracao'].append([])
                sol.rotas[kbest]['artificial'].append(False)

                colunas_por_k[kbest] += 1
            else:
                # nenhuma viável → criar artificial balanceando também
                k_art = min(range(inst.nbv), key=lambda kk: colunas_por_k[kk])
                seq_art = [0, i, depf]
                custo_col = custo_seq(k_art, seq_art) + custo_art

                binaria = [0] * nbcd
                binaria[i - 1] = 1

                sol.rotas[k_art]['sequencia_rota'].append(seq_art)
                sol.rotas[k_art]['rotas_binaria'].append(binaria)
                sol.rotas[k_art]['custo'].append(custo_col)
                sol.rotas[k_art]['vezes_usada_geral'].append(0)
                sol.rotas[k_art]['vezes_usada_otimo'].append(0)
                sol.rotas[k_art]['lbd_iteracao'].append([])
                sol.rotas[k_art]['artificial'].append(True)

                colunas_por_k[k_art] += 1

        # remove a base
        if remover_base:
            for k in range(inst.nbv):
                if len(sol.rotas[k]['sequencia_rota']) > 1 and sol.rotas[k]['sequencia_rota'][0] == [0, depf]:
                    for chave in ['sequencia_rota', 'rotas_binaria', 'custo',
                                  'vezes_usada_geral', 'vezes_usada_otimo', 'lbd_iteracao', 'artificial']:
                        del sol.rotas[k][chave][0]

    def geracao_colunas(self, inst, sol,tipo_geracao):
        print()
        print()
        print("\n\n========Geracao de Colunas==========")

        with open("log_gc.txt", "w", encoding="utf-8") as f:
            f.write("iteracao;veiculo;custo_original;custo_reduzido;sequencia;data_hora\n")

        primeiromip=True
        #auxiliares -
        arcos_usados_ijk = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]

        ######################################################
        # Inicialização dos contadores para cada arco (i,j,k)
        #essa aqui é só linear
        LRRecency = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]
        #Soma dos valores da variável em todas as iterações CG
        LRAcc = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]
        #Nº de vezes que a variável teve valor 1 na solução ótima do mestre
        LRLast = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]
        #Valor da variável na última solução CG

        #valores nas buscas
        SearchRecency = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]
        #Soma dos valores da variável em todas as soluções de busca
        SearchLast = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]
        #Valor da variável na última busca
        Inc = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]

        # Contadores auxiliares
        total_iteracoes_CG = -1
        total_iteracoes_search = 0
        total_iteracoes_incumbente = 0

        ##########################################################################3

        #self.gera_rotas_iniciais(inst, sol)
        self.gera_rotas_iniciaisUNICA(inst, sol)
        #self.gera_rotas_artificiais(inst, sol)
        #self.gerar_rotas_unitarias_insercao(inst, sol)

        interrupt = False
        printToScreen = True
        pi = []
        nova_coluna = []

        # Subindo as primeiras colunas
        rotas = []
        # Itera apenas sobre as chaves (índices dos veículos) que existem em sol.rotas
        for k in sol.rotas.keys():
            # Agora é seguro acessar sol.rotas[k], pois sabemos que a chave 'k' existe
            nrotas = len(sol.rotas[k]['rotas_binaria'])
            for p in range(nrotas):
                rota_visitas = sol.rotas[k]['rotas_binaria'][p]
                rotas.append({
                    'veic': k,
                    'ind': p,
                    'visitas': rota_visitas,
                    'custo': sol.rotas[k]['custo'][p]
                })

        # Cria o modelo mestre
        model = gp.Model("Mestre_GC")
        #model.setParam('OutputFlag', 0)
        lbd = []  # lista de variáveis lbd (rotas)

        for k in range(inst.nbv):
            lbd.append([])

        # Adiciona variáveis iniciais
        for r in rotas:
            v = model.addVar(
                lb=0, ub=1,
                obj=r['custo'],
                vtype=GRB.CONTINUOUS,
                #vtype=GRB.BINARY,
                name=f"lb_{r['veic']}_{r['ind']}"
            )
            lbd[r['veic']].append(v)

        model.update()

        # Restrições de visita única
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol.rotas.keys(): #range(inst.nbv):
                nrotas = len(sol.rotas[k]['rotas_binaria'])
                for p in range(nrotas):
                    expr += lbd[k][p] * sol.rotas[k]['rotas_binaria'][p][i]
            model.addConstr(expr == 1, name=f"bin_xij_{i}")#$$$$$$$$$$$$$$$
            #model.addConstr(expr >= 1, name=f"bin_xij_{i}")
            #teste com >=  com uma coluna unica artificial




        # Restrições de uso máximo de rota por veículo
        constr_veic = {}
        for k in sol.rotas.keys():#range(inst.nbv):
            expr = gp.LinExpr()
            nrotas = len(sol.rotas[k]['rotas_binaria'])
            for p in range(nrotas):
                expr += lbd[k][p]
            #constr_veic[k] =model.addConstr(expr >= 1, name=f"rlbd_{k}")
            constr_veic[k] = model.addConstr(expr == 1, name=f"rlbd_{k}")#$$$$$$$$$$$$$$$

        # Objetivo
        model.ModelSense = GRB.MINIMIZE
        model.update()
        sol.numero_de_rotas = [len(sol.rotas[k]['rotas_binaria']) for k in sol.rotas.keys()]#range(inst.nbv)]

        contador = 0
        globalIteration = 0
        arcos_fixados_em_1 = set()
        initerruptall = True
        var_testes_arcos_igual_1=0
        max_var_testes_arcos_igual_1=5 #editavel
        operacao='fixa arcos recorrentes'
        #operacao='fixa arcos fracionados'

        ############################################ MECANISMO ITERATIVO #######################################################
        custo_global=0
        iteracao_sem_melhora=0
        indice_corte=0

        COLUNASINICIAISGERADAS=False
        COLUNASINICIAISGERADAS_RESTOK=False
        nbMAXIteracNoOpt=10
        nbIteracNoOpt=0
        nbIteracNoChange=0
        nbIMAXteracNoChange=20
        bool_alteracao_lbd=True
        while (initerruptall): #initerruptall
            print("\n\n============================================================================= ITERACAO GLOBAL "+str(globalIteration))
            initerruptall=False


            """
            if(COLUNASINICIAISGERADAS and not COLUNASINICIAISGERADAS_RESTOK):
                COLUNASINICIAISGERADAS_RESTOK=True
                # Restrições de uso máximo de rota por veículo
                for k in sol.rotas.keys():  # range(inst.nbv):
                    expr = gp.LinExpr()
                    nrotas = len(sol.rotas[k]['rotas_binaria'])
                    for p in range(nrotas):
                        expr += lbd[k][p]
                    model.addConstr(expr <= 1, name=f"rlbd_{k}")
                    # model.addConstr(expr == 1, name=f"rlbd_{k}")#$$$$$$$$$$$$$$$
            """


            model.optimize()
            print("%%%%%%%%%%%%%%%%% iteracao "+str(total_iteracoes_CG))
            if model.Status != GRB.OPTIMAL:




                if nbIteracNoOpt<nbMAXIteracNoOpt:
                    nbIteracNoOpt+=1
                    print("Problema mestre não resolvido/ótimo. Parando.")
                    #removo os cortes

                    print("🧹 Removendo restrições de arco fixado DENTRO DA GC ...")

                    for (i, j, k) in arcos_fixados_em_1:
                        nome_restr = f"arco_fixado_{i}_{j}_{k}"
                        restr = model.getConstrByName(nome_restr)
                        if restr:
                            model.remove(restr)
                            print(f"✔️ Removida: {nome_restr}")
                        else:
                            print(f"⚠️ Restrição {nome_restr} não encontrada no modelo.")

                    model.update()
                    model.optimize()

            else:

                print("\n--- Solução Ótima Encontrada NO GC MESTRE ---")
                print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")

                # ==================================================================
                # INICIO Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================
                print(f"\n--- Colunas Escolhidas na Solução do Mestre (Iteração {total_iteracoes_CG}) ---")
                custo_total_iteracao = 0
                for k in sol.rotas.keys():#range(inst.nbv):
                    print()
                    print()
                    print("SOL itera k "+str(k))

                    for p in range(len(lbd[k])):
                        print("k "+str(k)+" p "+str(p)+ " itera "+str(globalIteration))
                        # Pega o valor da variável lambda (lbd) correspondente
                        # O .X acessa o valor da variável na solução
                        x_val = lbd[k][p].X

                        # Se o valor for maior que uma pequena tolerância, a coluna foi "usada"
                        if x_val > 1e-6:
                            print(f"  Veículo {k}, Rota {p}:")
                            print(f"    - Valor (lambda): {x_val:.4f}")

                            # Acessa os dados da rota correspondente na sua estrutura sol.rotas
                            sequencia = sol.rotas[k]['sequencia_rota'][p]
                            ##contabilizar os arcos
                            for i in range(len(sequencia) - 1):
                                no_origem = sequencia[i]
                                no_destino = sequencia[i + 1]

                                # Adiciona contador no arco
                                arcos_usados_ijk[no_origem][no_destino][k] +=1

                            #print(f"Debug: k={k}, p={p}, tamanho da lista={len(sol.rotas[k]['vezes_usada_geral'])}")
                            sol.rotas[k]['vezes_usada_geral'][p]+=1
                            custo_rota = sol.rotas[k]['custo'][p]

                            print(f"    - Sequência: {sequencia}")
                            print(f"    - Custo:     {custo_rota:.2f}")

                            # Acumula o custo total da solução atual do mestre (Lower Bound)
                            custo_total_iteracao += x_val * custo_rota

                # ==================================================================
                # FIM Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================



                # Atualiza LRRecency, LRLast, LRAcc
                for k in sol.rotas.keys():
                    for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                        lambda_val = lbd[k][p].X  # valor da variável lambda no modelo mestre

                        if lambda_val > 1e-6:
                            rota_bin = sol.rotas[k]['rotas_binaria'][p]
                            sequencia = sol.rotas[k]['sequencia_rota'][p]

                            # Atualiza LRAcc
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                LRAcc[i_no][j_no][k] += 1
                                LRLast[i_no][j_no][k] = 1
                                LRRecency[i_no][j_no][k] += lambda_val
                        else:
                            # Zera LRLast se a rota não foi usada
                            sequencia = sol.rotas[k]['sequencia_rota'][p]
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                LRLast[i_no][j_no][k] = 0

                if custo_total_iteracao == custo_global:
                    nbIteracNoOpt+=1
                    nbIteracNoChange+=1



                    print("SEM MELHORA ITERACAO "+str(nbIteracNoChange))
                    #if nbIteracNoChange==nbIMAXteracNoChange:
                    #    break

                else:
                    nbIteracNoChange=0

                naoGeraCorteArco=False #seto false para que o proximo if nao aconteca' ele gera cortes
                if custo_total_iteracao== custo_global and naoGeraCorteArco:

                    #obter o primeiro MIP gerado da GC pura inicial' faz só o primeiro
                    ##=====================terminou a GC

                    if(primeiromip):
                        print("/n/n/n-------- PRIMEIRO MIP------------")

                        # Altera o tipo de todas as variáveis lambda para Binário
                        for k in sol.rotas.keys():  # range(inst.nbv):
                            for var_lambda in lbd[k]:
                                var_lambda.vtype = GRB.BINARY

                        model.update()

                        model.optimize()


                        #exportar as variaveis
                        if model.Status == GRB.OPTIMAL:
                            primeiromip=False
                            ##salva a rota em rotas escolhidas
                            custo_total_inteiro = model.ObjVal

                            print("--- Detalhes das Rotas Escolhidas (Solução Inteira-MIP 1) ---")
                            for k in range(inst.nbv):
                                # Itera sobre todas as rotas geradas para o veículo k
                                for p in range(len(lbd[k])):
                                    # Para variáveis binárias, verificamos se o valor é próximo de 1
                                    if lbd[k][p].X > 0.5:
                                        print(f"  Veículo {k}, Rota {p}:")
                                        sequencia = sol.rotas[k]['sequencia_rota'][p]
                                        custo_rota = sol.rotas[k]['custo'][p]
                                        print(f"    - Sequência: {sequencia}")
                                        print(f"    - Custo:     {custo_rota:.2f}")

                                        # salvar na sol como rota escolhida
                                        #sol.rotas_escolhidas= {}
                                        if k not in sol.rotas_escolhidas:
                                            sol.rotas_escolhidas[k] = {
                                                'sequencias': [],
                                                'custos': [],
                                                'indices': []
                                            }
                                        sol.rotas_escolhidas[k]['sequencias'].append(sol.rotas[k]['sequencia_rota'][p])
                                        sol.rotas_escolhidas[k]['custos'].append(sol.rotas[k]['custo'][p])
                                        sol.rotas_escolhidas[k]['indices'].append(p)


                            sol.exportar_json_gc(inst, "solucao_gc.json")



                        # Altera o tipo de todas as variáveis lambda para Binário
                        for k in sol.rotas.keys():  # range(inst.nbv):
                            for var_lambda in lbd[k]:
                                var_lambda.vtype = GRB.CONTINUOUS
                        model.update()
                        model.optimize()

                    #"""

                    iteracao_sem_melhora+=1

                    total_iteracoes_incumbente += 1

                    for k in sol.rotas.keys():
                        for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                            lambda_val = lbd[k][p].X
                            if lambda_val > 1e-6:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    Inc[i_no][j_no][k] += 1

                    print("ITERACAO SEM MELHORA")

                    total_iteracoes_search += 1

                    for k in sol.rotas.keys():
                        for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                            lambda_val = lbd[k][p].X
                            if lambda_val > 1e-6:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    SearchRecency[i_no][j_no][k] += lambda_val
                                    SearchLast[i_no][j_no][k] = 1
                            else:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    SearchLast[i_no][j_no][k] = 0


                    # Expressão para fixar um arco em 1
                    #quantidade de arcos fixados?
                    if operacao== 'fixa arcos recorrentes': #case 'fixa arcos recorrentes':

                        lista_arcos_usados = []
                        for i in range(inst.nbn):
                            for j in range(inst.nbn):
                                if i == j:
                                    continue
                                for k in range(inst.nbv):
                                    cont = arcos_usados_ijk[i][j][k]
                                    if cont > 0 and (i, j, k) not in arcos_fixados_em_1:
                                        lista_arcos_usados.append((i, j, k, cont))

                        # Ordena por contagem decrescente

                        lista_arcos_usados.sort(key=lambda x: x[3], reverse=True)
                        top5_arcos = lista_arcos_usados[:5]
                        print("\n===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====")
                        for (i, j, k, cont) in top5_arcos:
                            print(f"({i},{j},{k}) -> usado {cont} vezes")
                        print("===========================================\n")

                        # Se houver ao menos um arco, escolhe um aleatoriamente entre os top 5
                        if top5_arcos: #mostrado com i-j-k-numero de vezes
                            i_sel, j_sel, k_sel, cont_sel = random.choice(top5_arcos)
                            print(
                                f"Selecionando aleatoriamente o arco ({i_sel},{j_sel},{k_sel}) para fixar em 1 (usado {cont_sel} vezes).")

                            # Monta a expressão: soma das lambdas das rotas do veículo k_sel que contêm o arco (i_sel,j_sel) >= 1
                            expr_fix = gp.LinExpr()
                            nrotas = len(sol.rotas[k_sel]['rotas_binaria'])
                            for p in range(nrotas):
                                rota_seq = sol.rotas[k_sel]['sequencia_rota'][p]
                                contains = any(
                                    (rota_seq[idx], rota_seq[idx + 1]) == (i_sel, j_sel)
                                    for idx in range(len(rota_seq) - 1)
                                )
                                if contains:
                                    expr_fix += lbd[k_sel][p]

                            # Só adiciona a restrição se existir ao menos uma coluna com esse arco
                            if expr_fix.size() > 0:
                                model.addConstr(expr_fix >= 1, name=f"arco_fixado_{i_sel}_{j_sel}_{k_sel}")#nome da restricao fixa
                                arcos_fixados_em_1.add((i_sel, j_sel, k_sel))
                                iteracao_sem_melhora = 0
                                initerruptall = True
                                print(
                                    f"Restrição adicionada: veículo {k_sel} deve ter pelo menos uma rota contendo o arco {i_sel}->{j_sel}.")
                                model.update()

                                #mostro no arquivo log que fixei esse arco

                                indice_corte += 1
                                self.registrar_novo_corte(globalIteration, indice_corte, i_sel, j_sel, k_sel)


                            else:
                                print(
                                    f"Nenhuma rota atual do veículo {k_sel} contém o arco {i_sel}->{j_sel}, pulando fixação.")
                                arcos_fixados_em_1.add((i_sel, j_sel, k_sel))

                        model.update()
                        model.optimize()

                        if model.Status == GRB.OPTIMAL:

                            print("\n--- Solução Ótima Encontrada NO GC HEURISTICO ---")
                            print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")
                            #fim do case 'fixa arcos'
                            if operacao=='fixa arcos fracionados':
                                print("frac")
                                lambda_para_branch = None
                                min_diferenca = float('inf')

                                print("\n--- Verificando Lambdas Fracionários ---")
                                for var in model.getVars():
                                    # Checar se é uma variável lambda e se seu valor é fracionário
                                    if var.VarName.startswith("lb") and 0.3 < var.X < 0.7:
                                        print(f"  Variável {var.VarName}: Valor = {var.X:.4f}")
                                        lambda_para_branch = var.VarName
                                        lambda_var = model.getVarByName(lambda_para_branch)
                                        model.addConstr(lambda_var >= 1, name=f"branch_fix_on_{lambda_var}")
                                        model.optimize()

                                        #mostrar solucao nova
                                        custo_total_iteracao = 0
                                        for k in sol.rotas.keys():  # range(inst.nbv):
                                            print("SOL itera FRACIIONADA " + str(k))
                                            # Itera sobre todas as rotas (colunas) existentes para o veículo k
                                            for p in range(len(lbd[k])):
                                                # print("k "+str(k)+" p "+str(p)+ " itera "+str(globalIteration))
                                                # Pega o valor da variável lambda (lbd) correspondente
                                                # O .X acessa o valor da variável na solução
                                                x_val = lbd[k][p].X

                                                # Se o valor for maior que uma pequena tolerância, a coluna foi "usada"
                                                if x_val > 1e-6:
                                                    print(f"  Veículo {k}, Rota {p}:")
                                                    print(f"    - Valor (lambda): {x_val:.4f}")

                                                    # Acessa os dados da rota correspondente na sua estrutura sol.rotas
                                                    sequencia = sol.rotas[k]['sequencia_rota'][p]
                                                    ##contabilizar os arcos
                                                    for i in range(len(sequencia) - 1):
                                                        no_origem = sequencia[i]
                                                        no_destino = sequencia[i + 1]

                                                        # Adiciona contador no arco
                                                        arcos_usados_ijk[no_origem][no_destino][k] += 1

                                                    # print(f"Debug: k={k}, p={p}, tamanho da lista={len(sol.rotas[k]['vezes_usada_geral'])}")
                                                    sol.rotas[k]['vezes_usada_geral'][p] += 1
                                                    custo_rota = sol.rotas[k]['custo'][p]

                                                    print(f"    - Sequência: {sequencia}")
                                                    print(f"    - Custo:     {custo_rota:.2f}")

                                                    # Acumula o custo total da solução atual do mestre (Lower Bound)
                                                    custo_total_iteracao += x_val * custo_rota

                                        break

                        else:
                            print("\n--- Modelo mestre não encontrou solução ótima após fixação ---")


                            """
                            if arcos_fixados_em_1:
                                # Remove o último arco fixado
                                i_rem, j_rem, k_rem = arcos_fixados_em_1.pop()
                                nome_restr = f"arco_fixado_{i_rem}_{j_rem}_{k_rem}"
                                restr = model.getConstrByName(nome_restr)

                                if restr is not None:
                                    model.remove(restr)
                                    model.update()
                                    print(
                                        f"❌ Restrição {nome_restr} removida — arco ({i_rem}, {j_rem}, {k_rem}) agora é flexível.")
                                else:
                                    print(f"⚠️ Restrição {nome_restr} não encontrada no modelo.")
                            else:
                                print("⚠️ Nenhum arco fixado para remover.")

                            # Reotimiza após remoção
                            model.optimize()
                            if model.Status == GRB.OPTIMAL:
                                print("\n--- Solução Ótima Encontrada após remoção de arco fixado ---")
                                print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")
                            else:
                                print("❌ Ainda não foi possível encontrar solução ótima mesmo após remoção.")
                            """

           

                else:
                    iteracao_sem_melhora=0
                    custo_global=custo_total_iteracao


                #continua o wile do código



                print(f"Custo Total do Mestre  nesta iteração: {custo_total_iteracao:.4f}")
                print("--- Fim da Listagem de Colunas ---\n")

                ###escrever sol
                self.registrar_fo_gc(inst,total_iteracoes_CG,custo_total_iteracao)


                # ==================================================================
                # FIM DO Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================

                #  valores duais das restrições de visita única
                pi = [model.getConstrByName(f"bin_xij_{i}").Pi for i in range(inst.nbcd)]

                sigma = [model.getConstrByName(f"rlbd_{k}").Pi for k in sol.rotas.keys()]#k in range(inst.nbv)]

                #initerruptall = False

                # duais dos arcos fixados em 1
                """
                duais_arcos_fixados = dict()

                for (i, j, k) in arcos_fixados_em_1:
                    nome_restr = f"arco_fixado_{i}_{j}_{k}"
                    restr = model.getConstrByName(nome_restr)
                    if restr is not None:
                        dual = restr.Pi
                        duais_arcos_fixados[(i, j, k)] = dual
                """

                ###################################### ==================Resolver subproblema para cada veículo%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                for k in sol.rotas.keys():#range(inst.nbv):

                    # Subproblema retorna a nova rota e custo
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!inicia   roda sub probl do veic "+str(k))

                    duais_para_k={}
                    """
                    duais_para_k = {
                        (i, j): dual
                        for (i, j, kfix), dual in duais_arcos_fixados.items()
                        if kfix == k
                    }
                    """
                    nova_rota = None
                    custo_red = None
                    if (tipo_geracao == "GUROBI"):
                        nova_rota, custo_red = self.subproblema(inst, pi,sigma[k], k,duais_arcos=duais_para_k)

                    if(tipo_geracao=="PD"):
                        nova_rota, custo_red = self.SUB_PROG_DIN(inst, pi,sigma[k], k)



                    if nova_rota is not None:
                        # Extrai as informações do dicionário retornado
                        custo_original = nova_rota['custo']
                        sequencia_clientes = nova_rota['clientes']
                        rota_binaria = nova_rota['bin_xij']

                        print(f"22222222222222222 Terminou roda sub probl do veic {k}, com CUSTO RED "+str(custo_red))

                        if custo_red <-1e-6:

                            initerruptall = True
                            print("___________ INITERRUPT TRUE")
                            self.registrar_nova_coluna(k, sequencia_clientes, custo_original, custo_red,
                                                          total_iteracoes_CG,inst,tipo_geracao)

                            # Adiciona nova coluna ao modelo mestre
                            constrs_clientes = [model.getConstrByName(f"bin_xij_{i}") for i in range(inst.nbcd)]

                            coluna = gp.Column(rota_binaria, constrs_clientes)

                            #coluna.addTerms(1.0, constr_veic[k])  # <<--- ESSENCIAL

                            coluna.addTerms(1.0, model.getConstrByName(f"rlbd_{k}"))#$$$$$$$

                            # Adicionar a nova variável (lambda) ao modelo
                            # ==================================================================

                            # Pega o novo índice para a rota
                            novo_indice_rota = sol.numero_de_rotas[k]



                            nova_variavel = model.addVar(
                                obj=custo_original,
                                vtype=GRB.CONTINUOUS,
                                name=f"rlbd_{k}_{novo_indice_rota}",
                                column=coluna
                            )
                            lbd[k].append(nova_variavel)

                            sol.rotas[k]['rotas_binaria'].append(rota_binaria)
                            sol.rotas[k]['sequencia_rota'].append(
                                 sequencia_clientes )  # Adiciona depósito
                            sol.rotas[k]['custo'].append(custo_original)
                            sol.rotas[k]['vezes_usada_geral'].append(0)
                            sol.numero_de_rotas[k] += 1
                            print("NOVA ROTA ADICIONADA veiculo "+str(k))
                            print(sequencia_clientes)
                            model.update()


                globalIteration += 1


            """
            if initerruptall==False:
                break
            """
            total_iteracoes_CG += 1


        ##=====================terminou a GC
        print("/n/n/n-------- INICIOU MIP------------")
        #model.write()
        # MIP
        # Altera o tipo de todas as variáveis lambda para Binário
        for k in sol.rotas.keys():#range(inst.nbv):
            for var_lambda in lbd[k]:
                var_lambda.vtype = GRB.BINARY



        print("🧹 Removendo restrições de arco fixado antes do MIP final...")

        for (i, j, k) in arcos_fixados_em_1:
            nome_restr = f"arco_fixado_{i}_{j}_{k}"
            restr = model.getConstrByName(nome_restr)
            if restr:
                model.remove(restr)
                print(f"✔️ Removida: {nome_restr}")
            else:
                print(f"⚠️ Restrição {nome_restr} não encontrada no modelo.")

        model.update()
        model.optimize()

        if model.Status == GRB.OPTIMAL:
            sol.rotas_escolhidas = {}
            print("\n==== SOLUÇÃO ÓTIMA INTEIRA ENCONTRADA ====")
            custo_total_inteiro = model.ObjVal
            print(f"Custo Total Inteiro (Upper Bound): {custo_total_inteiro:.4f}\n")

            print("--- Detalhes das Rotas Escolhidas (Solução Inteira) ---")
            for k in range(inst.nbv):
                # Itera sobre todas as rotas geradas para o veículo k
                for p in range(len(lbd[k])):
                    # Para variáveis binárias, verificamos se o valor é próximo de 1
                    if lbd[k][p].X > 0.5:
                        print(f"  Veículo {k}, Rota {p}:")
                        sequencia = sol.rotas[k]['sequencia_rota'][p]
                        custo_rota = sol.rotas[k]['custo'][p]
                        print(f"    - Sequência: {sequencia}")
                        print(f"    - Custo:     {custo_rota:.2f}")


                        #salvar na sol como rota escolhida

                        if k not in sol.rotas_escolhidas:
                            sol.rotas_escolhidas[k] = {
                                'sequencias': [],
                                'custos': [],
                                'indices': []
                            }
                        sol.rotas_escolhidas[k]['sequencias'].append(sol.rotas[k]['sequencia_rota'][p])
                        sol.rotas_escolhidas[k]['custos'].append(sol.rotas[k]['custo'][p])
                        sol.rotas_escolhidas[k]['indices'].append(p)

            print("==============================================")

            colunas_geradas_por_veiculo = {k: [] for k in range(inst.nbv)}

            nova_rota = {'sequencia': [...], 'custo': ..., 'a_ij': [...]}  # a_ij indica se a rota visita o cliente i
            colunas_geradas_por_veiculo[k].append(nova_rota)

            self.registrar_fo_gc(inst,-1,custo_total_inteiro)



        else:
            print("Não foi possível encontrar uma solução ótima inteira para o problema mestre final.")

        ##########iteracoes colunas
        print(arcos_usados_ijk)



    def subproblema(self,inst, pi,sigma, k, duais_arcos=None):
        #adicionar mais argumentos para na resolucao de fixar arcos como 0 ou 1- lista de arcos
        print("sub _ k"+str(k))
        #print("=========")
        #print("pi "+str(pi) )
        print("VALORES PASSADOS")
        # π de cada cliente
        print("π (visit unique constraints):")
        for i, val in enumerate(pi, start=1):
            print(f"  Cliente {i:02d}: {val:.6f}")

        # σ do veículo
        print(f"\nσ_k (dual veículo {k}): {sigma:.6f}")

        # duais de arcos fixados (se houver)
        if duais_arcos and len(duais_arcos) > 0:
            print("\nDuais de arcos fixados:")
            for (i, j), val in duais_arcos.items():
                print(f"  arco ({i}->{j}): {val:.6f}")
        else:
            print("\nDuais de arcos fixados: nenhum")

        try:
            nbn = inst.nbn  # número de nós (depósito + clientes + depósito final)
            V = list(range(nbn))
            clientes = list(range(1, nbn - 1))
            BIG_M = 1e5
            # Modelagem Gurobi
            model = gp.Model(f'Subproblema_v{k}')

            model.setParam('OutputFlag', 0)
            model.Params.TimeLimit = 30

            x = model.addVars(nbn, nbn, vtype=GRB.BINARY, name='x')

            s = model.addVars(nbn, vtype=GRB.CONTINUOUS, name='s')

            u = model.addVars(nbn, vtype=GRB.CONTINUOUS, name='u')

            # Cada veículo sai do depósito de origem (0) e chega no depósito final (inst.nbn-1)
            model.addConstr(gp.quicksum(x[0, j] for j in clientes) == 1, "saida_deposito")
            model.addConstr(gp.quicksum(x[i, nbn - 1] for i in clientes) == 1, "chega_deposito_fim")

            # fluxo de continuidade para clientes
            for h in clientes:
                model.addConstr(
                    gp.quicksum(x[i, h] for i in V if i != h) ==
                    gp.quicksum(x[h, j] for j in V if j != h),
                    f"fluxo_{h}"
                )
            # capacidade e fluxo de carga
            Q = inst.veiculos[k].capacidade
            for i in V:
                model.addConstr(u[i] <= Q)
                for j in clientes:
                    if i != j:
                        model.addConstr(u[j] >= u[i] + inst.noh[j].DEMAND - Q * (1 - x[i, j]))
            # Depósito inicia com zero carga
            #model.addConstr(u[0] == 0) #?


            for i in V:
                ready = inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0
                due = inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9
                model.addConstr(s[i] >= ready, f"ready_{i}")
                model.addConstr(s[i] <= due, f"due_{i}")


            #  janelas de tempo
            model.addConstr(s[0] == 0, "tempo_inicio_zero")
            for i in V:
                for j in V:
                    if i != j:
                        service = inst.noh[i].SERVICE_TIME[0] if hasattr(inst.noh[i], 'SERVICE_TIME') and inst.noh[
                            i].SERVICE_TIME else 0

                        travel = inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

                        model.addConstr(s[i] + service + travel - BIG_M * (1 - x[i, j]) <= s[j],
                                        f"sequenciamento_{i}_{j}")

            # 7) Função objetivo com custos ajustados pelos duais 'pi'
            # Inicializa a função objetivo
            obj = gp.LinExpr()

            # Para cada par de nós (i, j), com i ≠ j
            for i in V:
                for j in V:
                    if i == j:
                        continue

                    # 1. Custo base do arco (i, j) para o veículo k
                    custo_base = inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

                    # 2. Valor dual da restrição de visita única do cliente j (π_j)
                    dual_pi = pi[j - 1] if j in clientes else 0

                    # 3. Valor dual da restrição de arco fixado (σ_ijk), se houver
                    dual_arco = duais_arcos.get((i, j), 0)

                    # 4. Custo reduzido do arco (i, j)
                    custo_reduzido = custo_base - dual_pi - dual_arco

                    # 5. Adiciona o termo à função objetivo
                    obj += custo_reduzido * x[i, j]

            # 6. Subtrai o dual da restrição de uso do veículo (σ_k)
            obj -= sigma

            # 7. Define a função objetivo no modelo
            model.setObjective(obj, GRB.MINIMIZE)

            model.update()
            model.optimize()

            #if model.Status == GRB.OPTIMAL and model.ObjVal < -1e-6:
            if model.ObjVal < -1e-6:
                rota = [0]
                atual = 0
                visitados = set([0, nbn - 1])
                while atual != nbn - 1:
                    next_node = None
                    for j in V:
                        if atual != j and x[atual, j].X > 0.5 and j not in visitados:
                            next_node = j
                            break
                    if next_node is None:
                        rota.append(nbn - 1)
                        break
                    rota.append(next_node)
                    visitados.add(next_node)
                    atual = next_node
                bin_xij = [0 for _ in range(nbn-2)]
                for v in rota:
                    if v != 0 and v != nbn - 1:
                        bin_xij[v-1] = 1
                custo_total = sum(
                    inst.matriz_distancia[rota[i]][rota[i + 1]] / inst.veiculos[k].velocidade
                    for i in range(len(rota) - 1)
                )
                print("««««««« custo subido para o mestre "+ str(custo_total))
                return {
                    "clientes": rota,
                    "custo": custo_total,
                    "bin_xij": bin_xij
                }, model.ObjVal
            else:
                return None, None

        except gp.GurobiError as e:
            print(f"Erro Gurobi: {e.errno} {e}")
            return None, None

        except Exception as ex:
            print(f"Exception geral: {ex}")
            return None, None




    def registrar_fo_gc(self, inst, iteracao, valor_fo):

        filename = f"{inst.nbcd}.csv"

        # Se for iteracao 0, sempre recomeça o arquivo
        if iteracao == 0:
            mode = 'w'
        else:
            mode = 'a'

        with open(filename, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if mode == 'w':
                writer.writerow(['iteracao', 'valor_fo'])

            if(iteracao == -1):
                writer.writerow(["MIP", f"{valor_fo:.6f}"])
            else:
                if (iteracao == -2):
                    writer.writerow(["COMPACTO", f"{valor_fo:.6f}"])
                else:
                    writer.writerow([iteracao, f"{valor_fo:.6f}"])



    def registrar_nova_coluna(self, k, rota, custo_original, custo_reduzido, iteracao, inst,tipo_geracao):
        """
        Registra a geração de uma nova coluna (nova rota do subproblema)
        como uma linha no arquivo de log já existente.
        """
        filename = f"COLUNASADD_{inst.nbcd}_{tipo_geracao}.csv"
        with open(filename, "a", encoding="utf-8") as f:
            linha = (
                f"{iteracao};{k};"
                f"{custo_original:.6f};{custo_reduzido:.6f};"
                f"[{' '.join(map(str, rota))}];"
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            )
            f.write(linha)


    def SUB_PROG_DIN(self, inst, pi, sigma_k, k, duais_arcos=None):

        import math
        from collections import deque

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        a = []   # ready time
        b = []   # due date
        s = []   # service time
        d = []   # demanda


        #IMPORTACAO DOS DADOS
        for i in range(nbn):
            noh = inst.noh[i]

            if hasattr(noh, "READY_TIME") and noh.READY_TIME:
                a.append(noh.READY_TIME[0])
            else:
                a.append(0.0)

            if hasattr(noh, "DUE_DATE") and noh.DUE_DATE:
                b.append(noh.DUE_DATE[0])
            else:
                b.append(float("inf"))

            if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME:
                s.append(noh.SERVICE_TIME[0])
            else:
                s.append(0.0)

            if hasattr(noh, "DEMAND"):
                d.append(noh.DEMAND)
            else:
                d.append(0.0)

        cap_k = inst.veiculos[k].capacidade
        velocidade = inst.veiculos[k].velocidade

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        # --------------- MAPA CLIENTE  ---------------
        # Clientes são nós 1..nbcd, bit (cliente-1)
        def cliente_mask(c):
            return 1 << (c - 1)






        # ---------------- ESTRUTURA DOS RÓTULOS ----------------
        # Cada rótulo:
        # {
        #   "no": nó atual,
        #   "tempo": tempo de chegada,
        #   "carga": carga acumulada,
        #   "custo_mod": custo reduzido acumulado (parcial),
        #   "mask": mascara dos clientes visitados,
        #   "pai": índice do rótulo anterior em rotulos
        # }

        rotulos = []
        abertos = deque()

        # rótulo inicial no depósito
        tempo_inicial = max(a[dep0], 0.0)
        rotulo_inicial = {
            "no": dep0,
            "tempo": tempo_inicial,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,     # nenhum cliente visitado
            "pai": None
        }
        rotulos.append(rotulo_inicial)
        abertos.append(0)

        # melhor rota até agora que termina no depósito final
        melhor_indice = None
        melhor_custo_reduzido = math.inf

        # dicionário para poda (dominância simples)
        # guarda o melhor (custo_mod, tempo) observado para (no, mask)
        melhor_estado = {}
        melhor_estado[(dep0, 0)] = (0.0, tempo_inicial)

        # ---------------- LOOP PRINCIPAL ----------------
        while abertos:
            idx_atual = abertos.popleft()
            r_atual = rotulos[idx_atual]

            no_i = r_atual["no"]
            tempo_i = r_atual["tempo"]
            carga_i = r_atual["carga"]
            custo_mod_i = r_atual["custo_mod"]
            mask_i = r_atual["mask"]

            # Se já estamos no depósito final, atualiza melhor e não expande
            if no_i == depf:
                if custo_mod_i < melhor_custo_reduzido:
                    melhor_custo_reduzido = custo_mod_i
                    melhor_indice = idx_atual
                continue

            # Expande para todo j
            j = 0
            while j < nbn:
                # não voltar pro depósito inicial
                if j == dep0:
                    j += 1
                    continue

                nova_mask = mask_i

                # se j for cliente
                if 1 <= j <= nbcd:
                    bit_j = cliente_mask(j)
                    # se já visitei o cliente, não posso repetir
                    if (mask_i & bit_j) != 0:
                        j += 1
                        continue
                    nova_mask = mask_i | bit_j

                # capacidade
                nova_carga = carga_i
                if 1 <= j <= nbcd:
                    nova_carga += d[j]
                if nova_carga > cap_k:
                    j += 1
                    continue

                # tempo de chegada e janela
                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j]:
                    j += 1
                    continue

                # custo reduzido acumulado
                custo_mod_novo = custo_mod_i + travel_time(no_i, j)

                # se j for cliente, subtrai dual pi_j
                if 1 <= j <= nbcd:
                    custo_mod_novo -= pi[j - 1]

                # se for depósito final, subtrai sigma_k
                if j == depf:
                    custo_mod_novo -= sigma_k

                # PODA POR DOMINÂNCIA SIMPLES:
                chave = (j, nova_mask)
                # Se já existe um rótulo melhor ou igual para (j, nova_mask), descarta
                if chave in melhor_estado:
                    melhor_custo, melhor_tempo = melhor_estado[chave]
                    if (custo_mod_novo >= melhor_custo - 1e-9 and
                        tempo_chegada >= melhor_tempo - 1e-9):
                        j += 1
                        continue

                # Atualiza melhor_estado
                melhor_estado[chave] = (custo_mod_novo, tempo_chegada)

                # Cria novo rótulo
                novo_rotulo = {
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_mod_novo,
                    "mask": nova_mask,
                    "pai": idx_atual
                }
                idx_novo = len(rotulos)
                rotulos.append(novo_rotulo)
                abertos.append(idx_novo)

                j += 1

        # ---------------- PÓS-PROCESSAMENTO ----------------

        # Nenhuma rota até o depósito final
        if melhor_indice is None:
            return None, None

        # Custo reduzido não é negativo → não gera coluna
        if melhor_custo_reduzido >= -1e-6:
            return None, None

        # Reconstrói rota
        rota_reversa = []
        idx = melhor_indice
        while idx is not None:
            r = rotulos[idx]
            rota_reversa.append(r["no"])
            idx = r["pai"]

        rota = list(reversed(rota_reversa))  # [0, ..., depf]

        # Custo REAL (sem duais)
        custo_real = 0.0
        for i in range(len(rota) - 1):
            custo_real += travel_time(rota[i], rota[i + 1])

        # Vetor binário dos clientes
        bin_xij = [0 for _ in range(nbcd)]
        for v in rota:
            if 1 <= v <= nbcd:
                bin_xij[v - 1] = 1

        print("««« custo REAL subido para o mestre:", custo_real)
        print("««« custo REDUZIDO desta rota:", melhor_custo_reduzido)

        rota_dict = {
            "clientes": rota,
            "custo": custo_real,
            "bin_xij": bin_xij
        }

        return rota_dict, melhor_custo_reduzido




    def registrar_novo_corte(self,iteracao, indice_corte, i, j, k, nome_arquivo="log_gc.txt"):

        with open(nome_arquivo, "a", encoding="utf-8") as f:
            linha = (
                f"{iteracao}; corte{indice_corte} [{i},{j},{k}]; "
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            )
            f.write(linha)
