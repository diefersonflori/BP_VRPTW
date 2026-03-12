import gurobipy as gp
from numba.core.cgutils import sizeof
import random

from instancia import Instancia
from solucao import Solucao


class Metodos:
    """
    Contém os algoritmos e métodos para resolver o VRPTW.
    """

    def modelo_exato(self, instancia: Instancia, solucao: Solucao):
        """
        Constrói e resolve um modelo de programação matemática para o VRPTW.
        A solução gerada será salva no objeto 'solucao'.
        """
        print("Iniciando a resolução do modelo exato...")

        num_veiculos = len(instancia.capacidades_veiculos)
        K = range(num_veiculos)  # veículos

        clientes = list(instancia.clientes.keys())
        V = [0] + clientes  # 0 = depósito
        DepFinal= len(V)
        V= V+ [DepFinal] #V todos os nós
        todos_nos = {0: instancia.deposito, **instancia.clientes,DepFinal:instancia.deposito }

        # 1. Cria o modelo
        modelo = gp.Model('VRPTW_Exato')

        # 2. Variáveis de decisão
        x = modelo.addVars(V, V, K, vtype=gp.GRB.BINARY, name='x')
        w = modelo.addVars(V, K, vtype=gp.GRB.CONTINUOUS, name='w')
        u = modelo.addVars(V, K, vtype=gp.GRB.CONTINUOUS, name='u')

        # 3. Função objetivo: minimizar tempo total (não distância)
        modelo.setObjective(
            gp.quicksum(instancia.matriz_tempos[k][i][j] * x[i, j, k]
                        for i in V for j in V for k in K if i != j),
            gp.GRB.MINIMIZE
        )

        # 4. Cada cliente visitado exatamente uma vez
        for i in clientes:
            modelo.addConstr(
                gp.quicksum(x[j, i, k] for j in V if j != i for k in K) == 1,
                name=f'entrada_{i}'
            )
            modelo.addConstr(
                gp.quicksum(x[i, j, k] for j in V if j != i for k in K) == 1,
                name=f'saida_{i}'
            )

        # 5. Fluxo no depósito para cada veículo
        for k in K:
            # cada veículo sai do depósito no máximo uma vez
            modelo.addConstr(gp.quicksum(x[0, j, k] for j in (clientes+[DepFinal])) == 1, name=f'saida_deposito_{k}')
            # cada veículo retorna ao depósito no máximo uma vez
            modelo.addConstr(gp.quicksum(x[j, DepFinal, k] for j in ([0]+clientes)) == 1, name=f'retorno_deposito_{k}')

        # 6. Janelas de tempo múltiplas
        y_vars = {}
        for i in V:
            if 'janelas' in todos_nos[i]:
                num_janelas = len(todos_nos[i]['janelas'])
                for k in K:
                    y_vars[i, k] = modelo.addVars(num_janelas, vtype=gp.GRB.BINARY, name=f'y_{i}_{k}')
                    modelo.addConstr(
                        gp.quicksum(y_vars[i, k][j] for j in range(num_janelas)) == 1,
                        name=f'escolhe_uma_janela_{i}_{k}'
                    )
                    for j, (rt, dd) in enumerate(todos_nos[i]['janelas']):
                        modelo.addConstr(
                            w[i, k] >= rt - (1 - y_vars[i, k][j]) * 1e5,
                            name=f'janela_inicio_{i}_{j}_{k}'
                        )
                        modelo.addConstr(
                            w[i, k] <= dd + (1 - y_vars[i, k][j]) * 1e5,
                            name=f'janela_fim_{i}_{j}_{k}'
                        )

        # 7. Tempo de viagem entre nós
        M_tempo = max(fim for inicio, fim in todos_nos[0]['janelas'])
        for k in K:
            for i in V:
                for j in V:
                    if i != j:
                        tempo_viagem = instancia.matriz_distancias[i][j] + todos_nos[i].get('tempo_servico', 0)
                        modelo.addConstr(
                            w[i, k] + tempo_viagem <= w[j, k] + M_tempo * (1 - x[i, j, k]),
                            name=f'tempo_chegada_{i}_{j}_{k}'
                        )

        # 8. MTZ para eliminar subtours e respeitar capacidade
        for k in K:
            modelo.addConstr(u[0, k] == 0, name=f"mtz_deposito_{k}")
            Q = instancia.capacidades_veiculos[k]
            for i in clientes:
                modelo.addConstr(u[i, k] >= todos_nos[i]['demanda'], name=f'carga_min_{i}_{k}')
                modelo.addConstr(u[i, k] <= Q, name=f'carga_max_{i}_{k}')
                for j in clientes:
                    if i != j:
                        modelo.addConstr(
                            u[i, k] - u[j, k] + Q * x[i, j, k] <= Q - todos_nos[j]['demanda'],
                            name=f'mtz_{i}_{j}_{k}'
                        )

        # 9. Continuidade
        for k in K:
            for i in clientes:
                modelo.addConstr(
                    gp.quicksum(x[j, i, k] for j in V if j != i) ==
                    gp.quicksum(x[i, j, k] for j in V if j != i),
                    name=f'continuidade_{i}_{k}'
                )

        # 10. Fluxo de carga: veículo inicia vazio e vai carregando os pedidos
        for k in K:
            Q = instancia.capacidades_veiculos[k]
            modelo.addConstr(u[0, k] == 0, name=f"carga_deposito_{k}")
            for i in V:
                for j in clientes:
                    if i != j:
                        modelo.addConstr(
                            u[j, k] >= u[i, k] + todos_nos[j]['demanda'] - Q * (1 - x[i, j, k]),
                            name=f'fluxo_carga_{i}_{j}_{k}'
                        )
            for i in clientes:
                modelo.addConstr(u[i, k] <= Q, name=f'capacidade_max_{i}_{k}')

        # 10. Otimiza o modelo
        modelo.write("modelo.lp")
        modelo.optimize()

        # 11. Extrai a solução
        if modelo.Status == gp.GRB.OPTIMAL:
            rotas_encontradas = self._extrair_rotas(modelo, instancia, x, w)
            solucao.rotas = rotas_encontradas

            for k in K:
                for i in V:
                    solucao.tempos_chegada[(i, k)] = w[i, k].X

            solucao.calcular_custo(instancia)
            print("Solução encontrada com sucesso!")
            print(f"Custo total: {solucao.custo_total}")
            print(f"Número de rotas: {len(rotas_encontradas)}")
            print("Rotas:")
            for i, rota in enumerate(rotas_encontradas):
                print(f"  Rota {i + 1}: {rota}")
        else:
            print("Nenhuma solução ótima encontrada. O modelo pode ser inviável.")

        # DEBUG: variáveis x ativas
        print("\n--- DEBUG: Variáveis x ativas ---")
        for k in K:
            for i in V:
                for j in V:
                    if i != j and x[i, j, k].X > 0.5:
                        chegada = w[i, k].X
                        servico = todos_nos[i].get('tempo_servico', 0)
                        saida = chegada + servico
                        chegada_dest = w[j, k].X
                        carga = u[i, k].X
                        janela = todos_nos[i]['janelas']
                        print(
                            f"x[{i},{j},{k}] = 1 | Veículo {k+1} chega em {i} às {chegada:.2f}, sai às {saida:.2f}, "
                            f"capacidade a bordo: {carga:.2f}, janelas: {janela}, chega em {j} às {chegada_dest:.2f}"
                        )
        print("wait")

    def _extrair_rotas(self, modelo, instancia, x, w):
        """
        Extrai as rotas completas do modelo, considerando depósito inicial (0) e final (DepFinal).
        """
        clientes = list(instancia.clientes.keys())
        num_veiculos = len(instancia.capacidades_veiculos)
        K = range(num_veiculos)
        V = [0] + clientes
        DepFinal = len(V)
        Vfull = V + [DepFinal]

        rotas = []

        for k in K:
            for j in clientes:
                if x[0, j, k].X > 0.5:
                    rota = [0, j]
                    atual = j
                    while True:
                        proximo = None
                        for l in Vfull:
                            if x[atual, l, k].X > 0.5:
                                proximo = l
                                break
                        if proximo is None:
                            break
                        if proximo == DepFinal:
                            rota.append(DepFinal)
                            break
                        if proximo in rota:
                            # Previne ciclos
                            break
                        rota.append(proximo)
                        atual = proximo
                    rotas.append(rota)
        return rotas

    def geracao_de_colunas(self, instancia, solucao):
        """
        Geração de colunas para o VRP: resolve o problema mestre relaxado,
        calcula custos reduzidos e adiciona novas colunas se necessário.
        """
        print("Iniciando geração de colunas...")

        clientes = list(instancia.clientes.keys())
        num_clientes = len(clientes)
        rotas = solucao.rotas
        custos = solucao.rotas_custo
        matriz_binaria = solucao.rotas_binarias

        # 1. Cria o modelo mestre relaxado
        modelo = gp.Model("Problema_Mestre")
        modelo.setParam('OutputFlag', 0)  # Silencia o output do Gurobi

        # Variáveis lambda_r (relaxadas)
        lambdas = modelo.addVars(len(rotas), lb=0, ub=1, vtype=gp.GRB.CONTINUOUS, name="lambda")

        # Restrição: cada cliente deve ser atendido ao menos uma vez
        for idx_c, c in enumerate(clientes):
            modelo.addConstr(
                gp.quicksum(matriz_binaria[r][idx_c] * lambdas[r] for r in range(len(rotas))) >= 1,
                name=f"atende_{c}"
            )

        # Função objetivo: minimizar custo total das rotas escolhidas
        modelo.setObjective(
            gp.quicksum(custos[r] * lambdas[r] for r in range(len(rotas))),
            gp.GRB.MINIMIZE
        )

        # 2. Resolve o problema mestre relaxado
        modelo.optimize()

        print(f"Custo do mestre relaxado: {modelo.ObjVal:.2f}")

        # 3. Recupera os multiplicadores (pi) das restrições dos clientes
        pi = [modelo.getConstrByName(f"atende_{c}").Pi for c in clientes]

        # 4. Subproblema: gerar nova rota com custo reduzido negativo
        # (Aqui você pode chamar sua heurística construtiva ou um subproblema exato usando pi)
        # Exemplo: custo reduzido de uma rota = custo_rota - sum(pi[c] para c na rota)
        nova_rota = None
        novo_binario = None
        novo_custo = None
        custo_reduzido = None

        for _ in range(10):  # Tenta gerar até 10 rotas novas
            rota = self.heuristica_construtiva(instancia, indice_veiculo=0)
            binario = [1 if c in rota else 0 for c in clientes]
            custo = 0
            for i in range(len(rota) - 1):
                custo += instancia.matriz_distancias[rota[i]][rota[i+1]]
            custo_reduzido = custo - sum(pi[idx] for idx, c in enumerate(clientes) if c in rota)
            if custo_reduzido < -1e-6:
                nova_rota = rota
                novo_binario = binario
                novo_custo = custo
                print(f"Nova coluna com custo reduzido negativo encontrada: {rota} | Custo reduzido: {custo_reduzido:.2f}")
                break

        # 5. Se encontrou nova coluna, adiciona e repete; senão, encerra
        if nova_rota:
            solucao.rotas.append(nova_rota)
            solucao.rotas_binarias.append(novo_binario)
            solucao.rotas_custo.append(novo_custo)
            print("Adicionando nova coluna e resolvendo novamente...")
            return self.geracao_de_colunas(instancia, solucao)  # Chama recursivamente
        else:
            print("Nenhuma nova coluna com custo reduzido negativo encontrada. Encerrando.")

        # 6. Ao final, pode extrair a solução ótima relaxada
        print("Lambdas finais (solução relaxada):")
        for r, var in lambdas.items():
            print(f"Rota {r}: lambda = {var.X:.3f} | {rotas[r]} | Custo: {custos[r]:.2f}")

        # 7. Resolve o problema mestre inteiro ao final do processo de geração de colunas
        print("\nResolvendo o problema mestre inteiro com as colunas geradas...")

        modelo_inteiro = gp.Model("Problema_Mestre_Inteiro")
        modelo_inteiro.setParam('OutputFlag', 0)

        lambdas_int = modelo_inteiro.addVars(len(solucao.rotas), vtype=gp.GRB.BINARY, name="lambda")

        # Restrição: cada cliente deve ser atendido ao menos uma vez
        for idx_c, c in enumerate(clientes):
            modelo_inteiro.addConstr(
                gp.quicksum(solucao.rotas_binarias[r][idx_c] * lambdas_int[r] for r in range(len(solucao.rotas))) >= 1,
                name=f"atende_{c}"
            )

        # Função objetivo: minimizar custo total das rotas escolhidas
        modelo_inteiro.setObjective(
            gp.quicksum(solucao.rotas_custo[r] * lambdas_int[r] for r in range(len(solucao.rotas))),
            gp.GRB.MINIMIZE
        )

        modelo_inteiro.optimize()

        if modelo_inteiro.Status == gp.GRB.OPTIMAL:
            print(f"\nCusto ótimo inteiro: {modelo_inteiro.ObjVal:.2f}")
            print("Rotas selecionadas na solução:")
            for r, var in lambdas_int.items():
                if var.X > 0.5:
                    print(f"Rota {r}: {solucao.rotas[r]} | Custo: {solucao.rotas_custo[r]:.2f}")
        else:
            print("Nenhuma solução ótima encontrada para o mestre inteiro.")

        print("Geração de colunas finalizada.")

    def heuristica(self, instancia: Instancia, solucao: Solucao):
        print("Executando heurística...")
        pass

    def heuristica_construtiva(self, instancia, indice_veiculo):
        """
        Gera uma rota viável para o veículo 'indice_veiculo' de forma construtiva e aleatória.
        Não necessariamente visita todos os pedidos.
        """
        capacidade = instancia.capacidades_veiculos[indice_veiculo]
        velocidade = instancia.velocidades_veiculos[indice_veiculo]
        clientes = list(instancia.clientes.keys())
        random.shuffle(clientes)  # Aleatoriza a ordem dos clientes

        rota = [0]  # Começa no depósito
        carga = 0
        tempo = 0
        atual = 0

        for cliente in clientes:
            demanda = instancia.clientes[cliente]['demanda']
            # Calcula tempo de viagem
            tempo_viagem = instancia.matriz_distancias[atual][cliente] / velocidade
            tempo_chegada = tempo + tempo_viagem
            # Verifica se cabe a demanda e se respeita alguma janela de tempo
            janelas = instancia.clientes[cliente]['janelas']
            pode_atender = False
            for (rt, dd) in janelas:
                if tempo_chegada <= dd and tempo_chegada >= rt:
                    pode_atender = True
                    tempo_chegada = max(tempo_chegada, rt)
                    break
            if carga + demanda <= capacidade and pode_atender:
                rota.append(cliente)
                carga += demanda
                tempo = tempo_chegada + instancia.clientes[cliente]['tempo_servico']
                atual = cliente

        rota.append(0)  # Retorna ao depósito
        return rota