import random
import copy
import time
import gurobipy as gp
from aiohttp._websocket import mask
from asyncssh.asn1 import BOOLEAN
from gurobipy import GRB, quicksum
#from holoviews.examples.gallery.demos.bokeh.square_limit import nonet
from sipbuild.generator.parser.annotations import boolean
import json
import datetime
import os
import csv
from datetime import datetime
import math

# ápara o c++
import subprocess
from pathlib import Path

from sqlalchemy import false

from instancia import Instancia
from solucao import Solucao

PRINT_ROTAS_INICIAIS = True
PRINT_ROTAS_GC = True


class NoBP:
    def __init__(self, id_no, arcos_fixados_em_1=None, arcos_proibidos=None):
        self.id_no = id_no

        self.arcos_fixados_em_1 = set(arcos_fixados_em_1) if arcos_fixados_em_1 else set()
        self.arcos_proibidos = set(arcos_proibidos) if arcos_proibidos else set()

        # Resultados da GC neste nó
        self.custo_lp = None
        self.lambdas = {}
        self.solucao_inteira = False

        # Novos campos para log
        self.status = "ativo"  # 'ativo', 'resolvido', 'podado'
        self.motivo_poda = None  # string explicando o motivo
        self.branching_from = None  # {'pai': id, 'arco': (i,j,k), 'tipo': 'proibido'/'obrigatorio'}


class Metodos:

    def __init__(self, inst):
        n = inst.nbn
        K = inst.nbv

        # 3D list – fácil de ler e manter
        def m3d():
            return [[[0 for _ in range(K)] for _ in range(n)] for _ in range(n)]

        # Arcos usados
        self.arcos_usados_ijk = m3d()

        # Valores da relaxação linear
        self.LRRecency = m3d()
        self.LRAcc = m3d()
        self.LRLast = m3d()

        # Valores da busca
        self.SearchRecency = m3d()
        self.SearchLast = m3d()
        self.Inc = m3d()

        # Contadores auxiliares
        self.total_iteracoes_CG = -1
        self.total_iteracoes_search = 0
        self.total_iteracoes_incumbente = 0

        self.log_bp = None
        self.hist_bp = []  # NOVO: histórico textual da árvore

    def run_exe(self, exe_name: str, args=None, stdin_text: str | None = None) -> subprocess.CompletedProcess:
        args = args or []
        exe = Path(__file__).resolve().parent / exe_name

        mingw_bin = r"C:\msys64\mingw64\bin"
        env = os.environ.copy()
        env["PATH"] = mingw_bin + os.pathsep + env.get("PATH", "")

        p = subprocess.run(
            [str(exe), *map(str, args)],
            input=stdin_text,
            capture_output=True,
            text=True,
            cwd=str(exe.parent),
            env=env
        )
        return p

    ##############################################PARA REGISTROS NA ARVORE JSON

    # ===================== LOG DO BRANCH-AND-PRICE =====================

    def _init_log_bp(self, inst):
        self.log_bp = {
            "run_id": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
            "instancia": {
                "nbcd": inst.nbcd,
                "nbn": inst.nbn,
                "nbv": inst.nbv,
            },
            "niveis": []
        }
        # inicializa log textual da história
        self.hist_bp = []

    def _append_hist_bp(self, msg: str):
        if not hasattr(self, "hist_bp") or self.hist_bp is None:
            self.hist_bp = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.hist_bp.append(f"[{timestamp}] {msg}")

    def _salvar_hist_bp_txt(self, nome_arquivo=None):
        if not hasattr(self, "hist_bp") or not self.hist_bp:
            return
        if nome_arquivo is None:
            nome_arquivo = f"hist_bp_{self.log_bp['run_id']}.txt"
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            for linha in self.hist_bp:
                f.write(linha + "\n")
        print(f"Histórico do B&P salvo em {nome_arquivo}")

    def _get_nivel_entry(self, profundidade):
        """Garante que exista um entry para o nível e retorna."""
        while len(self.log_bp["niveis"]) <= profundidade:
            self.log_bp["niveis"].append({
                "nivel": len(self.log_bp["niveis"]),
                "nos": []
            })
        return self.log_bp["niveis"][profundidade]

    def _registrar_no_bp(self, no_bp: NoBP, sol_no: Solucao, profundidade: int, id_pai):
        """
        Cria o dicionário do nó (para o JSON) e coloca no nível correto.
        """
        rotas_no = self.extrair_rotas_do_no(no_bp, sol_no)

        info_no = {
            "no_id": no_bp.id_no,
            "id_pai": id_pai,
            "profundidade": profundidade,
            "custo_lp": no_bp.custo_lp,
            "solucao_inteira": bool(no_bp.solucao_inteira),
            "status": getattr(no_bp, "status", None),
            "motivo_poda": getattr(no_bp, "motivo_poda", None),
            "arcos_fixados_em_1": [list(t) for t in sorted(no_bp.arcos_fixados_em_1)],
            "arcos_proibidos": [list(t) for t in sorted(no_bp.arcos_proibidos)],
            "rotas_ativas_lp": rotas_no
        }

        nivel_entry = self._get_nivel_entry(profundidade)
        nivel_entry["nos"].append(info_no)

    def _salvar_log_bp(self, nome_arquivo=None):
        """Salva o JSON em disco."""
        if self.log_bp is None:
            return

        if nome_arquivo is None:
            nome_arquivo = f"arvore_bp_{self.log_bp['run_id']}.json"

        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(self.log_bp, f, ensure_ascii=False, indent=2)
        print(f"JSON da árvore salvo em {nome_arquivo}")

    # ===================== HISTÓRICO EM TXT =====================

    def _init_hist_bp(self):
        """Inicializa o buffer de histórico textual do B&P."""
        self.hist_bp = []

    def _append_hist_bp(self, msg: str):
        """Adiciona uma linha ao histórico com carimbo de data/hora."""
        if self.hist_bp is None:
            self.hist_bp = []
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.hist_bp.append(f"[{ts}] {msg}")

    def _salvar_hist_bp(self, nome_arquivo="hist_bp.txt"):
        """Salva o histórico textual em um .txt."""
        if not self.hist_bp:
            return
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("\n".join(self.hist_bp))
        print(f"Histórico do B&P salvo em {nome_arquivo}")

    # ===================== HISTÓRICO EM TXT =====================

    ##############################################PARA REGISTROS NA ARVORE JSON

    def extrair_rotas_do_no(self, no_bp: NoBP, sol):
        """
        A partir de no_bp.lambdas e sol.rotas,
        devolve as rotas (sequências) ativas neste nó.
        """
        rotas_no = {}  # {k: {'sequencias': [], 'custos': []}}

        for (k, p), val in no_bp.lambdas.items():
            if val > 0.5:  # λ "ativo"
                seq = sol.rotas[k]['sequencia_rota'][p]
                custo = sol.rotas[k]['custo'][p]

                if k not in rotas_no:
                    rotas_no[k] = {
                        'sequencias': [],
                        'custos': []
                    }

                rotas_no[k]['sequencias'].append(seq)
                rotas_no[k]['custos'].append(custo)

        return rotas_no

    def imprimir_lambdas_no(self, no_bp: NoBP, sol, tol=1e-6):
        """
        Imprime os lambdas do nó (LP do nó do B&P),
        parecido com o que você fazia na GC.
        """
        print("\n=== LAMBDAS DO NÓ", no_bp.id_no, "===")
        for (k, p), val in no_bp.lambdas.items():
            if abs(val) > tol:  # só imprime os relevantes
                seq = sol.rotas[k]['sequencia_rota'][p]
                custo = sol.rotas[k]['custo'][p]
                print(f"Veículo {k}, rota {p}: lambda = {val:.4f}")
                print(f"   Sequência: {seq}")
                print(f"   Custo:     {custo:.2f}")
        print("=== FIM LAMBDAS NÓ", no_bp.id_no, "===\n")

    def criar_filhos_por_arco(self, inst, sol, no_pai: NoBP, proximo_id: int):

        arco_escolhido = None
        tolerancia = 1e-3

        for (k, p), val in no_pai.lambdas.items():
            if not (tolerancia < val < 1 - tolerancia):
                continue

            seq = sol.rotas[k]['sequencia_rota'][p]

            for idx in range(len(seq) - 1):
                i_no = seq[idx]
                j_no = seq[idx + 1]

                if i_no == 0 and j_no == inst.nbn - 1:
                    continue

                arco = (i_no, j_no, k)

                if arco in no_pai.arcos_fixados_em_1:
                    continue
                if arco in no_pai.arcos_proibidos:
                    continue

                arco_escolhido = arco
                break

            if arco_escolhido is not None:
                break

        if arco_escolhido is None:
            return None, None, proximo_id

        i_sel, j_sel, k_sel = arco_escolhido
        print(f" Branching no arco ({i_sel},{j_sel},{k_sel}) no nó {no_pai.id_no}")

        pai_fix = set(no_pai.arcos_fixados_em_1)
        pai_proib = set(no_pai.arcos_proibidos)

        filho_esq = NoBP(
            id_no=proximo_id,
            arcos_fixados_em_1=pai_fix,
            arcos_proibidos=pai_proib.union({arco_escolhido})
        )
        filho_esq.branching_from = {
            "pai": no_pai.id_no,
            "arco": [i_sel, j_sel, k_sel],
            "tipo": "proibido"
        }

        filho_dir = NoBP(
            id_no=proximo_id + 1,
            arcos_fixados_em_1=pai_fix.union({arco_escolhido}),
            arcos_proibidos=pai_proib
        )
        filho_dir.branching_from = {
            "pai": no_pai.id_no,
            "arco": [i_sel, j_sel, k_sel],
            "tipo": "obrigatorio"
        }

        # log textual
        self._append_hist_bp(
            f"Do nó {no_pai.id_no} gerados filhos {filho_esq.id_no} (proíbe arco {i_sel}->{j_sel}, k={k_sel}) "
            f"e {filho_dir.id_no} (obriga arco {i_sel}->{j_sel}, k={k_sel})."
        )

        return filho_esq, filho_dir, proximo_id + 2

    def rota_contem_arco(self, sequencia, i, j):
        """Retorna True se a rota (sequencia) usar o arco (i,j)."""
        for t in range(len(sequencia) - 1):
            if sequencia[t] == i and sequencia[t + 1] == j:
                return True
        return False

    def escolhe_arco_branching(x_val, arcos_on, arcos_off, tol=1e-6):
        """
        x_val: dicionário {(i,j,k): valor LP} da solução atual
        arcos_on/off: conjuntos de arcos já fixados neste nó
        """
        for (i, j, k), v in x_val.items():
            if (i, j, k) in arcos_on or (i, j, k) in arcos_off:
                continue
            if tol < v < 1 - tol:
                return (i, j, k)
        return None

    def rota_compatível_com_no(rota, arcos_on, arcos_off):
        arcos_rota = extrai_arcos_da_rota(rota)  # -> conjunto de (i,j,k)
        if not arcos_on.issubset(arcos_rota):
            return False
        if any(a in arcos_rota for a in arcos_off):
            return False
        return True

    def BP_GC(self, inst, sol, tipo_geracao, no_bp: NoBP):

        print()
        print()
        print(f"\n\n======== Branch-and-Price: Nó {no_bp.id_no} ==========")

        # LOG PROVISóRIO
        with open("log_gc.txt", "w", encoding="utf-8") as f:
            f.write("iteracao;veiculo;custo_original;custo_reduzido;sequencia;data_hora\n")

        primeiromip = True

        # Usa o conjunto de cortes DO NÓ, não um set novo
        arcos_fixados_em_1 = no_bp.arcos_fixados_em_1
        arcos_proibidos = no_bp.arcos_proibidos  # ainda vamos usar no subproblema no futuro

        # auxiliares
        arcos_usados_ijk = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]

        self.total_iteracoes_incumbente = 0

        # rotas iniciais
        self.gera_rotas_iniciaisUNICA(inst, sol)

        interrupt = False
        printToScreen = True
        pi = []
        nova_coluna = []

        # Subindo as primeiras colunas>> talvez fazer alguma herança do pai??
        rotas = []
        for k in sol.rotas.keys():
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
        model = gp.Model("Mestre_BP_No")
        # model.setParam('OutputFlag', 0)
        lbd = []
        for k in range(inst.nbv):
            lbd.append([])

        # Adiciona variáveis iniciais
        for r in rotas:
            v = model.addVar(
                lb=0, ub=1,
                obj=r['custo'],
                vtype=GRB.CONTINUOUS,
                name=f"lb_{r['veic']}_{r['ind']}"
            )
            lbd[r['veic']].append(v)

        model.update()

        # Restrições de visita única
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol.rotas.keys():
                nrotas = len(sol.rotas[k]['rotas_binaria'])
                for p in range(nrotas):
                    expr += lbd[k][p] * sol.rotas[k]['rotas_binaria'][p][i]
            model.addConstr(expr == 1, name=f"bin_xij_{i}")

        # Restrições de uso máximo de rota por veículo
        constr_veic = {}
        for k in sol.rotas.keys():
            expr = gp.LinExpr()
            nrotas = len(sol.rotas[k]['rotas_binaria'])
            for p in range(nrotas):
                expr += lbd[k][p]
            constr_veic[k] = model.addConstr(expr == 1, name=f"rlbd_{k}")

        # Objetivo
        model.ModelSense = GRB.MINIMIZE
        model.update()
        sol.numero_de_rotas = [len(sol.rotas[k]['rotas_binaria']) for k in sol.rotas.keys()]

        # =====================================================
        # APLICAR DECISÕES DE BRANCHING NESTE NÓ
        #   - arcos_proibidos: lambdas dessas = 0
        #   - arcos_fixados_em_1: só rotas que contêm o arco podem ter valor >= 0
        # =====================================================

        # Arcos proibidos (i,j,k): nenhuma rota do veículo k pode conter esse arco
        for (i_proib, j_proib, k_proib) in arcos_proibidos:
            if k_proib not in sol.rotas:
                continue
            for p, seq in enumerate(sol.rotas[k_proib]['sequencia_rota']):
                if self.rota_contem_arco(seq, i_proib, j_proib):
                    # zera o limite superior dessa coluna
                    lbd[k_proib][p].UB = 0.0

        # 2) Arcos fixados em 1 (i,j,k): o veículo k DEVE usar esse arco
        #    => só rotas que contêm o arco podem ter lambda > 0
        for (i_fix, j_fix, k_fix) in arcos_fixados_em_1:
            if k_fix not in sol.rotas:
                continue
            existe_rota_com_arco = False
            for p, seq in enumerate(sol.rotas[k_fix]['sequencia_rota']):
                if self.rota_contem_arco(seq, i_fix, j_fix):
                    existe_rota_com_arco = True
                    # deixa UB = 1 (ou o que já estiver)
                    continue
                # rota de k_fix que NÃO contém (i_fix,j_fix) não pode ser usada
                lbd[k_fix][p].UB = 0.0

            if not existe_rota_com_arco:
                print(f"AVISO: no nó {no_bp.id_no} ainda não há rota de k={k_fix} com arco ({i_fix},{j_fix}).")
                print("       O pricing terá que gerar ao menos uma rota com esse arco para viabilizar o nó.")

        contador = 0
        globalIteration = 0
        initerruptall = True

        operacao = 'fixa arcos recorrentes'  # vai ser ignorado aqui
        custo_global = 0
        iteracao_sem_melhora = 0
        indice_corte = 0

        nbMAXIteracNoOpt = 10
        nbIteracNoOpt = 0
        nbIteracNoChange = 0

        # =====================================================
        #    A PARTIR DAQUI É O SEU while(initerruptall)
        #    COPIA EXATAMENTE COMO EM geracao_colunas
        #    MAS VAMOS COMENTAR O BLOCO DA HEURÍSTICA DE CORTES
        # =====================================================

        # ADICIONE:
        custo_total_iteracao = None

        while initerruptall:
            print(
                "\n\n============================================================================= ITERACAO GLOBAL " + str(
                    globalIteration))
            initerruptall = False

            model.optimize()
            print("%%%%%%%%%%%%%%%%% iteracao " + str(self.total_iteracoes_CG))

            if model.Status != GRB.OPTIMAL:
                print("Problema mestre deste nó é inviável ou não ótimo. Podando nó.")
                no_bp.custo_lp = None
                no_bp.lambdas = {}
                no_bp.solucao_inteira = False
                return no_bp

            else:
                # daqui para baixo fica igual ao seu bloco atual:
                print("\n--- Solução Ótima Encontrada NO GC MESTRE (NÓ BP) ---")
                print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")

                custo_total_iteracao = 0

                print("\n--- Solução Ótima Encontrada NO GC MESTRE (NÓ BP) ---")
                print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")

                # === COPIA 1: bloco de listagem de colunas + cálculo custo_total_iteracao ===
                # (igual ao seu geracao_colunas)
                custo_total_iteracao = 0
                for k in sol.rotas.keys():
                    for p in range(len(lbd[k])):
                        x_val = lbd[k][p].X
                        if x_val > 1e-6:
                            sequencia = sol.rotas[k]['sequencia_rota'][p]
                            for i in range(len(sequencia) - 1):
                                no_origem = sequencia[i]
                                no_destino = sequencia[i + 1]
                                arcos_usados_ijk[no_origem][no_destino][k] += 1
                            sol.rotas[k]['vezes_usada_geral'][p] += 1
                            custo_rota = sol.rotas[k]['custo'][p]
                            custo_total_iteracao += x_val * custo_rota

                # === COPIA 2: atualização de LRAcc, LRLast, LRRecency ===
                for k in sol.rotas.keys():
                    for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                        lambda_val = lbd[k][p].X
                        sequencia = sol.rotas[k]['sequencia_rota'][p]
                        if lambda_val > 1e-6:
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                self.LRAcc[i_no][j_no][k] += 1
                                self.LRLast[i_no][j_no][k] = 1
                                self.LRRecency[i_no][j_no][k] += lambda_val
                        else:
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                self.LRLast[i_no][j_no][k] = 0

                # === COPIA 3: lógica de "sem melhora" (mas sem corte heurístico) ===
                if custo_total_iteracao == custo_global:
                    nbIteracNoOpt += 1
                    nbIteracNoChange += 1
                    print("SEM MELHORA ITERACAO " + str(nbIteracNoChange))
                else:
                    nbIteracNoChange = 0
                    custo_global = custo_total_iteracao

                print(f"Custo Total do Mestre nesta iteração: {custo_total_iteracao:.4f}")
                print("--- Fim da Listagem de Colunas ---\n")

                self.registrar_fo_gc(inst, self.total_iteracoes_CG, custo_total_iteracao)

                # === COPIA 4: pegar duais pi e sigma ===
                pi = [model.getConstrByName(f"bin_xij_{i}").Pi for i in range(inst.nbcd)]
                sigma = [model.getConstrByName(f"rlbd_{k}").Pi for k in sol.rotas.keys()]

                # ================= ATENÇÃO AQUI =================
                # Nesta versão PARA B&P, NÃO vamos fazer:
                #   - if operacao == 'fixa arcos recorrentes': ...
                # OU seja, comente ou remova TODO aquele bloco.
                # =================================================

                # === COPIA 5: subproblemas e geração de novas colunas ===
                for k in sol.rotas.keys():
                    print(
                        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!inicia   roda sub probl do veic " + str(k))

                    nova_rota = None
                    custo_red = None

                    # filtra proibidos deste veículo
                    proibidos_k = {(i, j) for (i, j, kk) in arcos_proibidos if kk == k}

                    print(f"Inicio da PD {time.time()}")

                    if tipo_geracao == "GUROBI":
                        duais_para_k = {}
                        nova_rota, custo_red = self.subproblema(inst, pi, sigma[k], k, duais_arcos=duais_para_k,
                                                                arcos_proibidos=proibidos_k)

                    if tipo_geracao == "PD":
                        nova_rota, custo_red = self.SUB_PROG_DIN(inst, pi, sigma[k], k,
                                                                 arcos_proibidos=proibidos_k)

                    # Se não gerou rota, segue
                    if nova_rota is None:
                        continue

                    seq_nova = nova_rota['clientes']

                    # Verifica violação de arcos PROIBIDOS do nó
                    violado = False
                    for (i_proib, j_proib, k_proib) in arcos_proibidos:
                        if k_proib == k and self.rota_contem_arco(seq_nova, i_proib, j_proib):
                            violado = True
                            break

                    # Verifica arcos FIXADOS EM 1 (se o veiculo k tem algum arco obrigatório,
                    # a nova rota PRECISA conter esse arco)
                    for (i_fix, j_fix, k_fix) in arcos_fixados_em_1:
                        if violado:
                            break
                        if k_fix == k and not self.rota_contem_arco(seq_nova, i_fix, j_fix):
                            violado = True
                            break

                    if violado:
                        # ignora esta coluna, não adiciona ao mestre
                        continue

                    if nova_rota is not None:
                        custo_original = nova_rota['custo']
                        sequencia_clientes = nova_rota['clientes']
                        rota_binaria = nova_rota['bin_xij']

                        print(f"Terminou subproblema do veic {k}, custo_red = {custo_red}")

                        if custo_red < -1e-6:
                            initerruptall = True

                            self.registrar_nova_coluna(
                                k, sequencia_clientes, custo_original, custo_red,
                                self.total_iteracoes_CG, inst, tipo_geracao
                            )

                            constrs_clientes = [model.getConstrByName(f"bin_xij_{i}") for i in range(inst.nbcd)]
                            coluna = gp.Column(rota_binaria, constrs_clientes)
                            coluna.addTerms(1.0, model.getConstrByName(f"rlbd_{k}"))

                            novo_indice_rota = sol.numero_de_rotas[k]
                            nova_variavel = model.addVar(
                                obj=custo_original,
                                vtype=GRB.CONTINUOUS,
                                name=f"rlbd_{k}_{novo_indice_rota}",
                                column=coluna
                            )
                            lbd[k].append(nova_variavel)

                            sol.rotas[k]['rotas_binaria'].append(rota_binaria)
                            sol.rotas[k]['sequencia_rota'].append(sequencia_clientes)
                            sol.rotas[k]['custo'].append(custo_original)
                            sol.rotas[k]['vezes_usada_geral'].append(0)
                            sol.numero_de_rotas[k] += 1
                            model.update()

                globalIteration += 1
                self.total_iteracoes_CG += 1

        # =====================================================
        #            FIM DO while(initerruptall)
        #         AQUI TERMINA A GC PARA ESTE NÓ
        # =====================================================

        # Preenche o nó com o resultado do LP
        no_bp.custo_lp = custo_total_iteracao

        # adiciono valores dos lambdas deste nó
        no_bp.lambdas = {}
        for k in sol.rotas.keys():
            for p, var in enumerate(lbd[k]):
                no_bp.lambdas[(k, p)] = var.X

        no_bp.solucao_inteira = all(abs(v - round(v)) <= 1e-6 for v in no_bp.lambdas.values())

        print(f"Nó {no_bp.id_no} finalizado: LP = {no_bp.custo_lp:.4f}, inteira? {no_bp.solucao_inteira}")

        return no_bp

    def branch_and_price_global(self, inst, sol_pool, tipo_geracao="PD"):
        """
        Controlador da árvore de Branch-and-Price.
        Usa BP_GC em cada nó e gera um JSON da árvore.
        """

        # === Parâmetros do esquema do Filipe ===
        time_limit = 3600  # em segundos
        gap = 1e-4  # tolerância z_inc - z_li
        z_inc = float('inf')  # melhor solução inteira (UB)
        x_inc = None  # se quiser guardar info da solução inteira

        z_li = -float('inf')  # lower bound global (mínimo custo_lp entre nós abertos)
        t0 = time.time()

        # Log / JSON da árvore
        self._init_log_bp(inst)
        self._init_hist_bp()
        self._append_hist_bp("Início do Branch-and-Price global.")

        melhor_no = None  # referência ao melhor nó inteiro
        melhor_no_frac = None  # melhor fracionário
        z_frac = float('inf')  # custo do melhor fracionário

        # === Cria nó raiz ===
        id_no = 0
        raiz = NoBP(id_no=id_no)
        id_no += 1

        self._append_hist_bp(f"Criado nó raiz {raiz.id_no}.")

        # ativos: pilha/fila de nós abertos: (no_bp, profundidade, id_pai)
        ativos = [(raiz, 0, None)]

        while ativos:

            elapsed = time.time() - t0

            # -------------------------------------------------
            # Atualiza z_li = min custo_lp entre nós abertos
            # (só considera nós que já têm custo_lp calculado)
            # -------------------------------------------------
            custos_validos = [no.custo_lp for (no, _, _) in ativos
                              if no.custo_lp is not None]

            if custos_validos:
                z_li = min(custos_validos)
            else:
                z_li = -float('inf')

            # -------------------------------------------------
            # Critério de parada por gap
            # -------------------------------------------------
            if not math.isinf(z_inc) and z_li > -float('inf'):
                if z_inc - z_li <= gap:
                    print(f"Parou por gap: z_inc={z_inc:.4f}, z_li={z_li:.4f}")
                    self._append_hist_bp(
                        f"Parada por gap: z_inc={z_inc:.4f}, z_li={z_li:.4f}."
                    )
                    break

            # -------------------------------------------------
            # Critério de parada por tempo
            # -------------------------------------------------
            if elapsed >= time_limit:
                print(f"Parou por time limit: {elapsed:.1f}s")
                self._append_hist_bp(f"Parada por time limit: {elapsed:.1f}s.")
                break

            # -------------------------------------------------
            # Seleciona um nó da lista (DFS com pop())
            # -------------------------------------------------
            no_atual, prof, pai = ativos.pop()
            print(f"\n=========== PROCESSANDO NÓ {no_atual.id_no} (prof={prof}, pai={pai}) ===========")

            self._append_hist_bp(
                f"Processando nó {no_atual.id_no} (prof={prof}, pai={pai}) "
                f"com {len(no_atual.arcos_fixados_em_1)} arcos fixados e "
                f"{len(no_atual.arcos_proibidos)} arcos proibidos."
            )

            # -------------------------------------------------
            # Resolve GC + pricing neste nó
            # -------------------------------------------------
            self.resolver_no_com_pool(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)

            # ===== Caso 0: LP inviável ou sem solução
            if no_atual.custo_lp is None:
                print("Nó inviável ou sem solução LP, podado.")
                no_atual.status = "podado"
                no_atual.motivo_poda = "LP_inviavel"
                self._append_hist_bp(f"Nó {no_atual.id_no} podado: LP inviável ou sem solução.")
                # registra no JSON já com status/motivo
                self._registrar_no_bp(no_atual, sol_pool, profundidade=prof, id_pai=pai)
                continue

            z = no_atual.custo_lp
            no_atual.status = "resolvido"
            self._append_hist_bp(
                f"Nó {no_atual.id_no} resolvido: custo LP = {z:.4f}, "
                f"inteira={no_atual.solucao_inteira}."
            )

            # ===== Poda por bound
            if not math.isinf(z_inc) and z >= z_inc - 1e-6:
                print(f"Poda por bound: custo LP {z:.4f} >= z_inc {z_inc:.4f}")
                no_atual.status = "podado"
                no_atual.motivo_poda = "poda_bound"
                self._append_hist_bp(
                    f"Nó {no_atual.id_no} podado por bound: LP {z:.4f} >= z_inc {z_inc:.4f}."
                )
                self._registrar_no_bp(no_atual, sol_pool, profundidade=prof, id_pai=pai)
                continue

            # ===== Caso 1: solução DO NÓ é inteira
            if no_atual.solucao_inteira:
                print(f"Nó {no_atual.id_no} inteiro com custo {z:.4f}")
                self._append_hist_bp(
                    f"Nó {no_atual.id_no} é inteiro com custo {z:.4f}."
                )

                if z < z_inc:
                    z_inc = z
                    x_inc = getattr(no_atual, "lambdas", None)
                    melhor_no = no_atual
                    print(f"Novo incumbente: z_inc={z_inc:.4f}")
                    self._append_hist_bp(
                        f"Novo incumbente: nó {no_atual.id_no} com custo {z_inc:.4f}."
                    )

                    # Limpa lista de nós, apagando todos com bound >= z_inc
                    novos_ativos = []
                    for (n, p, pai_n) in ativos:
                        if n.custo_lp is None:
                            novos_ativos.append((n, p, pai_n))
                        elif n.custo_lp < z_inc - 1e-9:
                            novos_ativos.append((n, p, pai_n))
                        else:
                            print(f"Removendo nó {n.id_no} da lista (custo_lp={n.custo_lp:.4f} >= z_inc={z_inc:.4f})")
                            self._append_hist_bp(
                                f"Nó {n.id_no} removido da lista de ativos "
                                f"(custo_lp={n.custo_lp:.4f} >= z_inc={z_inc:.4f})."
                            )
                    ativos = novos_ativos

                # nó inteiro vira folha
                no_atual.motivo_poda = no_atual.motivo_poda or "no_inteiro_folha"
                self._registrar_no_bp(no_atual, sol_pool, profundidade=prof, id_pai=pai)
                continue

            # ===== Caso 2: solução fracionária -> branching
            print(f"Nó {no_atual.id_no} fracionário com custo {z:.4f}")
            self._append_hist_bp(
                f"Nó {no_atual.id_no} fracionário (custo {z:.4f}), gerando filhos por branching em arco."
            )

            #vou salvar a solucao se for a melhor fracionaria= por que eu quero

            if (not no_atual.solucao_inteira) and (z < z_frac):
                z_frac = z
                melhor_no_frac = no_atual

            filho_esq, filho_dir, id_no = self.criar_filhos_por_arco(inst, sol_pool, no_atual, id_no)

            if filho_esq is not None and filho_dir is not None:
                filho_esq.custo_lp = z
                filho_dir.custo_lp = z
                filho_esq.status = "ativo"
                filho_dir.status = "ativo"

                ativos.append((filho_esq, prof + 1, no_atual.id_no))
                ativos.append((filho_dir, prof + 1, no_atual.id_no))
            else:
                no_atual.status = "podado"
                no_atual.motivo_poda = "sem_lambda_fracionario"
                self._append_hist_bp(
                    f"Nó {no_atual.id_no} podado: nenhum lambda fracionário útil para branching."
                )

            # registra o nó (fracionário explorado) com status/motivo já definidos
            self._registrar_no_bp(no_atual, sol_pool, profundidade=prof, id_pai=pai)

        # registra o nó com status + motivo
        self._registrar_no_bp(no_atual, sol_pool, profundidade=prof, id_pai=pai)

        # =========================
        # Fim do laço principal
        # =========================

        print("\n==== FIM B&P ====")

        # Salva JSON da árvore
        self._salvar_log_bp()

        # Salva histórico em TXT
        self._append_hist_bp("Fim do Branch-and-Price.")
        self._salvar_hist_bp()

        # ===== imprime + salva MELHOR INTEIRO =====
        if melhor_no is not None:
            print(f"Melhor solução inteira: nó {melhor_no.id_no} com custo {z_inc:.4f}")
            self.imprimir_lambdas_no(melhor_no, sol_pool)

            dados_inc = {
                "tipo": "inteira",
                "no_id": melhor_no.id_no,
                "custo": z_inc,
                "lambdas": {f"{k},{p}": float(v) for (k, p), v in melhor_no.lambdas.items()},
                "rotas_ativas": self.extrair_rotas_do_no(melhor_no, sol_pool),
                "arcos_fixados_em_1": [list(t) for t in sorted(melhor_no.arcos_fixados_em_1)],
                "arcos_proibidos": [list(t) for t in sorted(melhor_no.arcos_proibidos)],
            }
            with open("melhor_inteira.json", "w", encoding="utf-8") as f:
                json.dump(dados_inc, f, ensure_ascii=False, indent=2)
        else:
            print("Nenhuma solução inteira encontrada.")

        # ===== imprime + salva MELHOR FRACIONÁRIA =====
        if melhor_no_frac is not None:
            print(f"Melhor solução fracionária: nó {melhor_no_frac.id_no} com custo {z_frac:.4f}")
            self.imprimir_lambdas_no(melhor_no_frac, sol_pool)

            dados_frac = {
                "tipo": "fracionaria",
                "no_id": melhor_no_frac.id_no,
                "custo": z_frac,
                "lambdas": {f"{k},{p}": float(v) for (k, p), v in melhor_no_frac.lambdas.items()},
                "rotas_ativas": self.extrair_rotas_do_no(melhor_no_frac, sol_pool),
                "arcos_fixados_em_1": [list(t) for t in sorted(melhor_no_frac.arcos_fixados_em_1)],
                "arcos_proibidos": [list(t) for t in sorted(melhor_no_frac.arcos_proibidos)],
            }
            with open("melhor_fracionaria.json", "w", encoding="utf-8") as f:
                json.dump(dados_frac, f, ensure_ascii=False, indent=2)
        else:
            print("Nenhuma solução fracionária registrada (ou todos nós foram inteiros/podados).")

        # Salva JSON da árvore
        self._salvar_log_bp()

    def coluna_respeita_no(self, no_bp, seq, k):
        """
        Verifica se a rota 'seq' do veículo k é compatível com
        os arcos fixados/proibidos do nó.
        seq = [0, i1, i2, ..., 0]
        """
        # Arcos proibidos: se qualquer (i,j,k) aparecer, coluna é inválida
        for (i_proib, j_proib, k_proib) in no_bp.arcos_proibidos:
            if k_proib != k:
                continue
            for t in range(len(seq) - 1):
                if seq[t] == i_proib and seq[t + 1] == j_proib:
                    return False  # viola proibição

        # Arcos fixados em 1: todos esses arcos devem estar na rota
        for (i_fix, j_fix, k_fix) in no_bp.arcos_fixados_em_1:
            if k_fix != k:
                continue
            presente = any(
                (seq[t] == i_fix and seq[t + 1] == j_fix)
                for t in range(len(seq) - 1)
            )
            if not presente:
                return False  # não respeita arco obrigatório

        return True

    def resolver_no_com_pool(self, inst, sol_pool, no_bp, tipo_geracao="PD"):

        import time
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL de colunas ---")

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam('OutputFlag', 0)

        # helper: retorna 1.0 se seq usa o arco (i->j)
        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        # λ[k][p] para cada rota do pool
        lbd = {k: [] for k in sol_pool.rotas.keys()}

        # =========================
        # 1) Variáveis lambda (todas as colunas do pool; incompatíveis com ub=0)
        # =========================
        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]['sequencia_rota'][p]
                custo = sol_pool.rotas[k]['custo'][p]

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0,
                    ub=ub,
                    obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}"
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) Restrições de visita única
        # =========================
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                nrotas = len(sol_pool.rotas[k]['rotas_binaria'])
                for p in range(nrotas):
                    rota_bin = sol_pool.rotas[k]['rotas_binaria'][p]
                    expr += lbd[k][p] * rota_bin[i]
            model.addConstr(expr == 1.0, name=f"visita_{i}")

        # =========================
        # 3) Restrição 1 rota por veículo
        # =========================
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
            for p in range(nrotas):
                expr += lbd[k][p]
            model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) NOVO: Restrições de arcos do nó (fixo=1 / proibido=0)
        # =========================
        # constr_arco[(k,i,j)] = Constr
        """
        constr_arco = {}

        for k in sol_pool.rotas.keys():

            # -------------------------------
            # Arcos FIXADOS em 1
            # -------------------------------
            fixados_k = [(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k]

            if fixados_k:
                nrotas = len(sol_pool.rotas[k]['sequencia_rota'])

                # coeficientes dos arcos fixados
                coef_fixados = {}  # (i,j) -> [0/1 por rota]
                for (i, j) in fixados_k:
                    coef_fixados[(i, j)] = [0.0] * nrotas
                    for p in range(nrotas):
                        seq = sol_pool.rotas[k]['sequencia_rota'][p]
                        coef_fixados[(i, j)][p] = rota_usa_arco(seq, i, j)

                # constraints: arco deve aparecer (== 1)
                for (i, j) in fixados_k:
                    expr = gp.LinExpr()
                    for p in range(nrotas):
                        expr += coef_fixados[(i, j)][p] * lbd[k][p]

                    constr_arco[(k, i, j)] = model.addConstr(
                        expr == 1.0,
                        name=f"arc_fixado_{k}_{i}_{j}"
                    )

            # -------------------------------
            # Arcos PROIBIDOS (fixados em 0)
            # -------------------------------
            proibidos_k = [(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k]

            if proibidos_k:
                nrotas = len(sol_pool.rotas[k]['sequencia_rota'])

                # coeficientes dos arcos proibidos
                coef_proibidos = {}  # (i,j) -> [0/1 por rota]
                for (i, j) in proibidos_k:
                    coef_proibidos[(i, j)] = [0.0] * nrotas
                    for p in range(nrotas):
                        seq = sol_pool.rotas[k]['sequencia_rota'][p]
                        coef_proibidos[(i, j)][p] = rota_usa_arco(seq, i, j)

                # constraints: arco não pode aparecer (== 0)
                for (i, j) in proibidos_k:
                    expr = gp.LinExpr()
                    for p in range(nrotas):
                        expr += coef_proibidos[(i, j)][p] * lbd[k][p]

                    constr_arco[(k, i, j)] = model.addConstr(
                        expr == 0.0,
                        name=f"arc_proibido_{k}_{i}_{j}"
                    )


        """

        # =========================
        # 4) Restrições de arcos do nó
        #    - FIXADO: global (soma dos veículos) == 1
        #    - PROIBIDO: por veículo == 0
        # =========================

        constr_arco_fix_global = {}  # key: (i,j) -> Constr
        constr_arco_proib_k = {}  # key: (k,i,j) -> Constr

        # FIXADOS (GLOBAL)
        fixados_global = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1}
        for (i, j) in sorted(fixados_global):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]['sequencia_rota'][p]
                    if rota_usa_arco(seq, i, j):
                        expr += lbd[k][p]
            constr_arco_fix_global[(i, j)] = model.addConstr(expr == 1.0, name=f"arc_fixado_{i}_{j}")

        # PROIBIDOS (POR VEÍCULO)
        for k in sol_pool.rotas.keys():
            proibidos_k = [(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k]
            if not proibidos_k:
                continue

            nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
            for (i, j) in proibidos_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]['sequencia_rota'][p]
                    if rota_usa_arco(seq, i, j):
                        expr += lbd[k][p]
                constr_arco_proib_k[(k, i, j)] = model.addConstr(expr == 0.0, name=f"arc_proibido_{k}_{i}_{j}")


        model.update()

        # =========================
        # LOOP DE GERAÇÃO DE COLUNAS
        # =========================
        custo_total_iteracao = None
        iter_cg = 0
        max_iter_cg = 50


        while True:

            if no_bp.id_no == 18:
                print("\n" + "=" * 60)
                print(f"NÓ {no_bp.id_no} — antes do optimize")
                print("FIXOS:", no_bp.arcos_fixados_em_1)
                print("PROIB:", no_bp.arcos_proibidos)
                print("=" * 60 + "\n")

            if no_bp.id_no == 18:
                print("\n" + "#" * 80)
                print("DEBUG COLUNAS NO MESTRE — NÓ 18")
                print("#" * 80)

                for k in sol_pool.rotas.keys():
                    nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
                    print(f"\nVeículo {k} — rotas no pool: {nrotas}")

                    # arcos do nó filtrados por veículo k
                    fixados_k = [(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k]
                    proibidos_k = [(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k]

                    if fixados_k:
                        print(f"  Fixados(k={k}): {fixados_k}")
                    if proibidos_k:
                        print(f"  Proibidos(k={k}): {proibidos_k}")

                    # imprimir cada coluna p e o lambda correspondente
                    for p in range(nrotas):
                        seq = sol_pool.rotas[k]['sequencia_rota'][p]
                        custo = sol_pool.rotas[k]['custo'][p] if 'custo' in sol_pool.rotas[k] else None

                        # "está no modelo": variável existe e tem valor (se já otimizou antes)
                        var = lbd[k][p]  # Gurobi Var
                        try:
                            val = var.X  # só existe depois de uma otimização
                        except Exception:
                            val = None

                        # checar compatibilidade com branching (apenas info)
                        usa_fix = []
                        for (i, j) in fixados_k:
                            if rota_usa_arco(seq, i, j):
                                usa_fix.append((i, j))

                        viola_proib = []
                        for (i, j) in proibidos_k:
                            if rota_usa_arco(seq, i, j):
                                viola_proib.append((i, j))

                        # linha de debug
                        st_val = "N/A" if val is None else f"{val:.6f}"
                        st_custo = "N/A" if custo is None else f"{custo:.4f}"
                        print(f"    p={p:04d}  lambda={st_val}  custo={st_custo}  seq={seq}")

                        if usa_fix:
                            print(f"           -> USA FIXADOS: {usa_fix}")
                        if viola_proib:
                            print(f"           -> VIOLA PROIBIDOS: {viola_proib}")

                print("#" * 80 + "\n")

            if no_bp.id_no == 18:
                fixados0 = [(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == 0]
                proibidos0 = [(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == 0]

                def compativel(seq, k):
                    if k != 0:
                        return True
                    for (i, j) in fixados0:
                        if not rota_usa_arco(seq, i, j):
                            return False
                    for (i, j) in proibidos0:
                        if rota_usa_arco(seq, i, j):
                            return False
                    return True

                for i in [1, 4, 9]:
                    cnt = 0
                    ex = []
                    for k in sol_pool.rotas.keys():
                        for p, seq in enumerate(sol_pool.rotas[k]['sequencia_rota']):
                            if compativel(seq, k) and (i in seq):
                                cnt += 1
                                if len(ex) < 5:
                                    ex.append((k, p, seq))
                    print(f"cliente {i}: {cnt} rotas compatíveis no pool")
                    for (k, p, seq) in ex:
                        print(f"  ex: k={k} p={p} seq={seq}")

            if no_bp.id_no == 18:
                def dump_row(constr_name, max_terms=60):
                    c = model.getConstrByName(constr_name)  # <-- aqui entra STRING
                    if c is None:
                        print(f"[ERRO] não achei restrição {constr_name}")
                        return

                    row = model.getRow(c)
                    print(f"\n--- {constr_name} --- RHS={c.RHS}  n_terms={row.size()}")
                    for t in range(min(max_terms, row.size())):
                        v = row.getVar(t)
                        a = row.getCoeff(t)
                        print(f"  {v.VarName}: {a}")

                dump_row("visita_1")
                dump_row("visita_4")
                dump_row("visita_9")
                dump_row("arc_fixado_0_10")
                dump_row("arc_proibido_0_0_5")

            model.optimize()

            if no_bp.id_no == 18:
                print("\n" + "=" * 70)
                print(f"NÓ 18 — status após optimize: {model.Status}")
                print("=" * 70)

                if model.Status in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
                    print(f"Obj={model.ObjVal:.6f}")

                    # 1) lambdas positivos
                    print("\nLambdas positivos:")
                    for k in sol_pool.rotas.keys():
                        nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
                        print(f"\nVeículo {k}:")
                        for p in range(nrotas):
                            val = lbd[k][p].X
                            if val > 1e-6:
                                seq = sol_pool.rotas[k]['sequencia_rota'][p]
                                print(f"  p={p:04d}  lambda={val:.6f}  seq={seq}")

                    # 2) checar LHS das restrições de arco
                    print("\nChecando FIXADOS globais (LHS):")
                    for (i, j), c in constr_arco_fix_global.items():
                        lhs = 0.0
                        for kk in sol_pool.rotas.keys():
                            nrotas = len(sol_pool.rotas[kk]['sequencia_rota'])
                            for p in range(nrotas):
                                seq = sol_pool.rotas[kk]['sequencia_rota'][p]
                                if rota_usa_arco(seq, i, j):
                                    lhs += lbd[kk][p].X
                        print(f"  arco {i}->{j}: LHS={lhs:.6f}  RHS={c.RHS:.6f}")

                    print("\nChecando PROIBIDOS por veículo (LHS):")
                    for (kk, i, j), c in constr_arco_proib_k.items():
                        lhs = 0.0
                        nrotas = len(sol_pool.rotas[kk]['sequencia_rota'])
                        for p in range(nrotas):
                            seq = sol_pool.rotas[kk]['sequencia_rota'][p]
                            if rota_usa_arco(seq, i, j):
                                lhs += lbd[kk][p].X
                        print(f"  veic {kk} arco {i}->{j}: LHS={lhs:.6f}  RHS={c.RHS:.6f}")



                elif model.Status == GRB.INFEASIBLE:
                    print("NÓ 18 INVIÁVEL — calculando IIS (restrições conflitantes)")
                    model.computeIIS()
                    for c in model.getConstrs():
                        if c.IISConstr:
                            print("IIS:", c.ConstrName)

                elif model.Status == GRB.INF_OR_UNBD:
                    print("NÓ 18 INF_OR_UNBD — rode com Presolve=0 para diagnosticar")
                    model.setParam('Presolve', 0)
                    model.optimize()
                    print("Status após Presolve=0:", model.Status)
                    if model.Status == GRB.INFEASIBLE:
                        model.computeIIS()
                        for c in model.getConstrs():
                            if c.IISConstr:
                                print("IIS:", c.ConstrName)

                else:
                    print("Status sem solução (não há ObjVal nem X).")

            if no_bp.id_no == 18:
                print("\n" + "#" * 80)

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            custo_total_iteracao = model.ObjVal

            pi = [model.getConstrByName(f"visita_{i}").Pi for i in range(inst.nbcd)]
            sigma = {k: model.getConstrByName(f"uma_rota_veic_{k}").Pi for k in sol_pool.rotas.keys()}

            mu_fix_global_vals = {(i, j): c.Pi for (i, j), c in constr_arco_fix_global.items()}

            houve_nova_coluna = False

            for k in sol_pool.rotas.keys():

                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                # duais do FIXADO global (vale para qualquer veículo)

                # + duais do PROIBIDO do veículo k (se você quiser manter custo reduzido correto)
                mu_arc = dict(mu_fix_global_vals)
                for (kk, i, j), c in constr_arco_proib_k.items():
                    if kk == k:
                        mu_arc[(i, j)] = mu_arc.get((i, j), 0.0) + c.Pi

                # reforço (você já usa)
                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)


                nova_rota = None
                custo_red = None
                nova_rota2 = None
                custo_red2 = None

                print("===")

                tempo1 = time.time()
                if tipo_geracao == "PD":
                    #nova_rota, custo_red = self.SUB_PROG_DIN(
                    nova_rota, custo_red = self.SUB_PROG_DINLivre(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc
                    )
                elif tipo_geracao == "GUROBI":
                    nova_rota, custo_red = self.subproblema(
                        inst, pi, sigma[k], k,
                        duais_arcos=None
                    )

                print(nova_rota)
                print(f"Tempo da da PD PYTHON {time.time() - tempo1:.2f}s")
                """

                if tipo_geracao == "PD":
                    tempo2 = time.time()
                    nova_rota2, custo_red2 = self.SUB_PROG_DINLivre(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc
                    )
                    print(nova_rota2)
                    print(f"Tempo da da PD2 PYTHON {time.time() - tempo2:.2f}s")

                    if (nova_rota2 is not None) and (nova_rota is not None):
                        if nova_rota2["clientes"] != nova_rota["clientes"]:
                            print("ROTAS DIFERENTES")
                            print("proib")
                            print(proibidos_equiv)
                            print("fixos")
                            print(fixados_k)
                            print("mu_arc")
                            print(mu_arc)


                """
                print("proib")
                print(proibidos_equiv)
                print("fixos")
                print(fixados_k)
                print("mu_arc")
                print(mu_arc)

                if nova_rota is None:
                    continue

                seq_nova = nova_rota['clientes']
                rota_binaria = nova_rota['bin_xij']
                custo_original = nova_rota['custo']

                # compatibilidade com nó
                if not self.coluna_respeita_no(no_bp, seq_nova, k):
                    idx_pool = len(sol_pool.rotas[k]['sequencia_rota'])
                    sol_pool.rotas[k]['sequencia_rota'].append(seq_nova)
                    sol_pool.rotas[k]['rotas_binaria'].append(rota_binaria)
                    sol_pool.rotas[k]['custo'].append(custo_original)
                    sol_pool.rotas[k]['vezes_usada_geral'].append(0)
                    sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
                    sol_pool.rotas[k]['lbd_iteracao'].append([])
                    continue

                if custo_red < -1e-6:
                    houve_nova_coluna = True

                    # 1) adiciona ao pool
                    idx_pool = len(sol_pool.rotas[k]['sequencia_rota'])
                    sol_pool.rotas[k]['sequencia_rota'].append(seq_nova)
                    sol_pool.rotas[k]['rotas_binaria'].append(rota_binaria)
                    sol_pool.rotas[k]['custo'].append(custo_original)
                    sol_pool.rotas[k]['vezes_usada_geral'].append(0)
                    sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
                    sol_pool.rotas[k]['lbd_iteracao'].append([])

                    # 2) adiciona a variável λ no modelo incluindo também as restrições de arco
                    constrs = []
                    coefs = []

                    # visita
                    for i in range(inst.nbcd):
                        constrs.append(model.getConstrByName(f"visita_{i}"))
                        coefs.append(float(rota_binaria[i]))

                    # 1 rota por veic
                    constrs.append(model.getConstrByName(f"uma_rota_veic_{k}"))
                    coefs.append(1.0)

                    # FIXADOS globais: entram para qualquer veículo
                    for (i, j), con in constr_arco_fix_global.items():
                        constrs.append(con)
                        coefs.append(rota_usa_arco(seq_nova, i, j))

                    # PROIBIDOS do veículo k: só os do veículo k
                    for (kk, i, j), con in constr_arco_proib_k.items():
                        if kk != k:
                            continue
                        constrs.append(con)
                        coefs.append(rota_usa_arco(seq_nova, i, j))

                    coluna = gp.Column(coefs, constrs)

                    v = model.addVar(
                        lb=0.0,
                        ub=1.0,
                        obj=custo_original,
                        vtype=GRB.CONTINUOUS,
                        name=f"lambda_{k}_{idx_pool}",
                        column=coluna
                    )
                    lbd[k].append(v)

                    print(f"      Nova coluna adicionada ao nó e ao pool: veic {k}, idx {idx_pool}")

                    model.update()

            print(f"  [Nó {no_bp.id_no}] houve_nova_coluna = {houve_nova_coluna}")
            for k in sol_pool.rotas.keys():
                print(f"    veic {k}: {len(sol_pool.rotas[k]['sequencia_rota'])} rotas no pool")

            if not houve_nova_coluna or iter_cg >= max_iter_cg:
                break

            iter_cg += 1

        # =========================
        # FIM DA GC DO NÓ
        # =========================
        model.optimize()
        if model.Status != GRB.OPTIMAL:
            print(f"Nó {no_bp.id_no}: modelo não ótimo após otimização final.")
            no_bp.custo_lp = None
            no_bp.solucao_inteira = False
            no_bp.lambdas = {}
            return

        no_bp.custo_lp = model.ObjVal

        lambdas = {}
        inteira = True
        tol = 1e-6
        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]['sequencia_rota'])
            for p in range(nrotas):
                if p < len(lbd[k]):
                    val = lbd[k][p].X
                else:
                    val = 0.0
                lambdas[(k, p)] = val
                if val > tol and abs(val - 1.0) > tol:
                    inteira = False

        no_bp.lambdas = lambdas
        no_bp.solucao_inteira = inteira

        print(f"Nó {no_bp.id_no} finalizado: LP = {no_bp.custo_lp:.4f}, inteira? {no_bp.solucao_inteira}")

    def proibidos_com_fixados(self, inst, proibidos_k, fixados_k):
        """
        Converte arcos obrigatórios (fixados_k = {(i,j),...}) em proibições equivalentes:
          - se (i,j) fixo: proíbe (i,t) para todo t!=j
          - se (i,j) fixo: proíbe (t,j) para todo t!=i
        Retorna um set((u,v)) pronto para usar no pricing/PD.
        """
        nbn = inst.nbn
        proib = set(proibidos_k)  # copia

        # se houver conflitos (ex.: dois sucessores diferentes do mesmo i), vai ficar inviável mesmo (correto).
        for (i_fix, j_fix) in fixados_k:
            # proíbe outras saídas de i_fix
            for t in range(nbn):
                if t == j_fix:
                    continue
                proib.add((i_fix, t))

            # proíbe outras entradas em j_fix
            for t in range(nbn):
                if t == i_fix:
                    continue
                proib.add((t, j_fix))

        # opcional: nunca permitir voltar ao dep0
        proib.add((inst.nbn - 1, 0))  # só um exemplo; ajuste se quiser
        return proib

    def metodo_exato(self, inst, sol):
        print("==================== Iniciando a resolução do modelo exato")
        K = range(inst.nbv)  # Veículos
        V = list(range(inst.nbn))  # Nós (depósito + clientes + depósito final)
        clientes = list(range(1, inst.nbn - 1))  # clientes devem ser 1..n-2

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
            #gp.quicksum(inst.matriz_distancia[i][j] * inst.veiculos[k].velocidade * x[i, j, k]  # FOO alterar FO
            gp.quicksum(inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade * x[i, j, k]  # FOO alterar FO
                        for k in K for i in V for j in V if i != j),
            GRB.MINIMIZE
        )
        # model.Params.TimeLimit = 150
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
                        service = inst.noh[i].SERVICE_TIME[0] if hasattr(inst.noh[i], 'SERVICE_TIME') and inst.noh[
                            i].SERVICE_TIME else 0
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
                            # sol.bin_visitas[k][i][j] = 1
                            # print(f"x[{k}][{i}][{j}] = 1")
                            xx = 0

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
                    ##inst.matriz_distancia[rota_seq[i]][rota_seq[i + 1]] * inst.veiculos[k].velocidade  # FOO alterar FO
                    inst.matriz_distancia[rota_seq[i]][rota_seq[i + 1]] / inst.veiculos[k].velocidade  # FOO alterar FO
                    for i in range(len(rota_seq) - 1)
                )

                sol.rotas[k]['rotas_binaria'].append(binaria)
                sol.rotas[k]['sequencia_rota'].append(rota_seq)
                sol.rotas[k]['custo'].append(custo)


        else:
            print("Nenhuma solução ótima encontrada")

    def gera_rotas_iniciais(self, inst, sol):
        rotas = {}
        nb_rotas = 40
        for ii in range(inst.nbv):  # Para cada veículo
            rotas_binaria = []  # Cada lista vai ter nb_rotas listas
            sequencia_rota = []
            custos = []
            vezes_usada_geral = []
            vezes_usada_otimo = []
            lbd_iteracao = []

            valor_lbd = []
            for r in range(nb_rotas):
                # Gera os clientes visitados
                clientes = list(range(1, inst.nbcd + 1))
                random.shuffle(clientes)
                n_clientes_rota = random.randint(1, inst.nbcd - 2)
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

                cost = cost
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

        sol.rotas = rotas

        return rotas

    ############rotas iniciais

    def init_pool_vazio(self, inst, sol_pool):
        """
        Inicializa sol_pool.rotas com as chaves/estruturas esperadas pelo seu B&P/GC.
        Sem colunas artificiais.
        """
        nbcd = inst.nbcd
        sol_pool.rotas = {}

        for k in range(inst.nbv):
            sol_pool.rotas[k] = {
                'rotas_binaria': [],
                'sequencia_rota': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': []
            }

    #teste heuristica gulosa
    def rota_gulosa_veiculo(self, inst, k, clientes_disponiveis, alpha=5):
        """
        Constrói 1 rota para o veículo k:
        - sempre mantém viabilidade (janela/tempo/capacidade)
        - escolhe próximo cliente entre os 'alpha' melhores candidatos (barato e diversifica)
        Retorna: (rota, custo) ou (None, None) se não consegue inserir ninguém.
        """
        import random
        import math

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        cap = float(inst.veiculos[k].capacidade)
        vel = float(inst.veiculos[k].velocidade)

        # pré-carregar arrays (mais rápido que getattr toda hora)
        a = [0.0] * nbn
        b = [float("inf")] * nbn
        s = [0.0] * nbn
        d = [0.0] * nbn
        for i in range(nbn):
            noh = inst.noh[i]
            if noh.READY_TIME: a[i] = noh.READY_TIME[0]
            if noh.DUE_DATE:   b[i] = noh.DUE_DATE[0]
            if noh.SERVICE_TIME: s[i] = noh.SERVICE_TIME[0]
            d[i] = float(getattr(noh, "DEMAND", 0.0))

        dist = inst.matriz_distancia  # usa distância e divide por vel

        def tt(i, j):
            return dist[i][j] / vel

        rota = [dep0]
        no = dep0
        tempo = max(a[dep0], 0.0)
        carga = 0.0

        while True:
            # monta candidatos viáveis
            cand = []
            for c in list(clientes_disponiveis):
                # capacidade
                if carga + d[c] > cap:
                    continue

                # tempo se inserir c agora
                t = tempo + s[no] + tt(no, c)
                if t < a[c]: t = a[c]
                if t > b[c]:
                    continue

                # e ainda conseguir voltar ao depósito final?
                t_back = t + s[c] + tt(c, depf)
                if t_back < a[depf]: t_back = a[depf]
                if t_back > b[depf]:
                    continue

                # score simples: tempo de viagem + (pequena penalidade de espera)
                espera = max(0.0, a[c] - (tempo + s[no] + tt(no, c)))
                score = tt(no, c) + 0.001 * espera
                cand.append((score, c, t))

            if not cand:
                break

            cand.sort(key=lambda x: x[0])
            top = cand[:max(1, alpha)]
            _, escolhido, t_escolhido = random.choice(top)

            rota.append(escolhido)
            clientes_disponiveis.remove(escolhido)

            # atualiza estado
            carga += d[escolhido]
            tempo = t_escolhido
            no = escolhido

        # fecha no depf se possível
        t_final = tempo + s[no] + tt(no, depf)
        if t_final < a[depf]: t_final = a[depf]
        if t_final > b[depf]:
            # não conseguiu fechar: devolve None (ou tenta "repair", mas vamos manter simples)
            return None, None

        rota.append(depf)

        # custo real
        custo = 0.0
        for i in range(len(rota) - 1):
            custo += tt(rota[i], rota[i + 1])

        return rota, custo

    def solucao_inicial_gulosa(self, inst, alpha=5, tentativas=30):
        """
        Gera uma solução inicial (uma rota por veículo) cobrindo todos os clientes.
        Faz várias tentativas e devolve a melhor (menor custo).
        """
        import math
        melhor = None
        melhor_custo = math.inf

        veics = list(inst.veiculos.keys()) if isinstance(inst.veiculos, dict) else list(range(len(inst.veiculos)))
        nbcd = inst.nbcd
        clientes = list(range(1, nbcd + 1))

        for _ in range(tentativas):
            clientes_disp = set(clientes)
            rotas_k = {}
            custo_total = 0.0

            # constroi 1 rota por veículo
            for k in veics:
                rota, custo = self.rota_gulosa_veiculo(inst, k, clientes_disp, alpha=alpha)
                if rota is None:
                    rotas_k = None
                    break
                rotas_k[k] = (rota, custo)
                custo_total += custo

            if rotas_k is None:
                continue

            # se ainda sobrou cliente, falhou (porque não coube)
            if clientes_disp:
                continue

            if custo_total < melhor_custo:
                melhor_custo = custo_total
                melhor = rotas_k

        return melhor  # {k: (rota, custo)} ou None

    def adicionar_solucao_inicial_ao_pool(self, inst, sol_pool, sol_ini):
        """
        sol_ini: {k: (rota, custo)}
        """
        nbcd = inst.nbcd

        for k, (rota, custo) in sol_ini.items():
            # binária por cliente
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1

            sol_pool.rotas[k]['sequencia_rota'].append(rota)
            sol_pool.rotas[k]['rotas_binaria'].append(bin_xij)
            sol_pool.rotas[k]['custo'].append(float(custo))
            sol_pool.rotas[k]['vezes_usada_geral'].append(0)
            sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
            sol_pool.rotas[k]['lbd_iteracao'].append([])

    def rota_deterministica_seed(self, inst, k, seed, clientes_alvo):
        """
        Constrói 1 rota começando em dep0 -> seed, depois insere o próximo cliente viável
        pelo critério de MENOR distância (vizinho mais próximo), considerando apenas clientes_alvo.

        clientes_alvo: set de clientes que você quer priorizar (ex.: ainda não cobertos).
        Retorna: (rota, custo) ou (None, None) se nem consegue colocar o seed.
        """
        import math

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        cap = float(inst.veiculos[k].capacidade)
        vel = float(inst.veiculos[k].velocidade)

        # arrays
        a = [0.0] * nbn
        b = [float("inf")] * nbn
        s = [0.0] * nbn
        d = [0.0] * nbn
        for i in range(nbn):
            noh = inst.noh[i]
            if noh.READY_TIME: a[i] = noh.READY_TIME[0]
            if noh.DUE_DATE: b[i] = noh.DUE_DATE[0]
            if noh.SERVICE_TIME: s[i] = noh.SERVICE_TIME[0]
            d[i] = float(getattr(noh, "DEMAND", 0.0))

        dist = inst.matriz_distancia

        def tt(i, j):
            return dist[i][j] / vel

        # checa seed válido
        if seed < 1 or seed > nbcd:
            return None, None

        # tenta inserir seed
        tempo = max(a[dep0], 0.0)
        carga = 0.0
        no = dep0

        # viabilidade de ir ao seed e depois conseguir fechar no depf
        if carga + d[seed] > cap:
            return None, None

        t_seed = tempo + s[no] + tt(no, seed)
        if t_seed < a[seed]: t_seed = a[seed]
        if t_seed > b[seed]:
            return None, None

        t_back = t_seed + s[seed] + tt(seed, depf)
        if t_back < a[depf]: t_back = a[depf]
        if t_back > b[depf]:
            return None, None

        rota = [dep0, seed]
        tempo = t_seed
        carga += d[seed]
        no = seed

        usados = {seed}

        # agora insere clientes (apenas do conjunto alvo, excluindo os já usados)
        while True:
            melhor = None  # (dist, cliente, novo_tempo)
            for c in clientes_alvo:
                if c in usados:
                    continue
                if carga + d[c] > cap:
                    continue

                t = tempo + s[no] + tt(no, c)
                if t < a[c]: t = a[c]
                if t > b[c]:
                    continue

                # ainda consegue fechar no depf?
                t2 = t + s[c] + tt(c, depf)
                if t2 < a[depf]: t2 = a[depf]
                if t2 > b[depf]:
                    continue

                score = tt(no, c)  # vizinho mais próximo (determinístico)
                if (melhor is None) or (score < melhor[0]):
                    melhor = (score, c, t)

            if melhor is None:
                break

            _, c, t = melhor
            rota.append(c)
            usados.add(c)
            tempo = t
            carga += d[c]
            no = c

        # fecha
        t_final = tempo + s[no] + tt(no, depf)
        if t_final < a[depf]: t_final = a[depf]
        if t_final > b[depf]:
            return None, None

        rota.append(depf)

        # custo real
        custo = 0.0
        for i in range(len(rota) - 1):
            custo += tt(rota[i], rota[i + 1])

        return rota, custo

    def gerar_rotas_iniciais_por_seeds(self, inst, k, max_rotas=None):
        """
        Gera rotas determinísticas seed=1..nbcd (nessa ordem),
        sempre priorizando clientes ainda não cobertos.

        Retorna: lista de (rota, custo)
        """
        nbcd = inst.nbcd
        cobertos = set()
        rotas = []

        for seed in range(1, nbcd + 1):
            if max_rotas is not None and len(rotas) >= max_rotas:
                break

            # clientes_alvo = ainda não cobertos (priorizar)
            clientes_alvo = set(range(1, nbcd + 1)) - cobertos
            if not clientes_alvo:
                break

            # mantém o seed “na ordem”:
            # se seed já está coberto, a rota ainda pode começar nele,
            # mas tentará inserir os não cobertos depois.
            rota, custo = self.rota_deterministica_seed(inst, k, seed, clientes_alvo)
            if rota is None:
                continue

            rotas.append((rota, custo))

            # marca cobertos
            for v in rota:
                if 1 <= v <= nbcd:
                    cobertos.add(v)

            if len(cobertos) == nbcd:
                break

        return rotas

    def adicionar_rotas_ao_pool(self, inst, sol_pool, k, rotas):
        nbcd = inst.nbcd

        for rota, custo in rotas:
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1

            sol_pool.rotas[k]['sequencia_rota'].append(rota)
            sol_pool.rotas[k]['rotas_binaria'].append(bin_xij)
            sol_pool.rotas[k]['custo'].append(float(custo))
            sol_pool.rotas[k]['vezes_usada_geral'].append(0)
            sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
            sol_pool.rotas[k]['lbd_iteracao'].append([])

    def gerar_pool_inicial_por_seeds(self, inst, sol_pool, max_rotas_total=None, alpha=None):
        """
        Gera rotas determinísticas seed=1..nbcd e DISTRIBUI entre veículos (round-robin),
        até que todos os clientes estejam cobertos no pool (ao menos uma vez).

        - Não copia rotas para todos os veículos.
        - Cada nova rota vai para um veículo diferente (k = (idx_rota % nbv)).
        """
        nbcd = inst.nbcd
        nbv = inst.nbv

        cobertos = set()
        total_adicionadas = 0

        for seed in range(1, nbcd + 1):
            if max_rotas_total is not None and total_adicionadas >= max_rotas_total:
                break

            clientes_alvo = set(range(1, nbcd + 1)) - cobertos
            if not clientes_alvo:
                break

            k = total_adicionadas % nbv  # round-robin

            rota, custo = self.rota_deterministica_seed(inst, k, seed, clientes_alvo)
            if rota is None:
                continue

            # adiciona ao pool do veículo k
            self.adicionar_rotas_ao_pool(inst, sol_pool, k, [(rota, custo)])
            total_adicionadas += 1

            # marca cobertura global
            for v in rota:
                if 1 <= v <= nbcd:
                    cobertos.add(v)

            if len(cobertos) == nbcd:
                break

        return cobertos, total_adicionadas

    def adicionar_rotas_single_customer(self, inst, sol_pool, bigM=1e6):
        """
        Adiciona, para CADA veículo k e CADA cliente i:
          rota = [dep0, i, depf]
        com custo = custo_real + bigM (para o mestre evitar usar).
        """
        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        for k in range(inst.nbv):
            vel = float(inst.veiculos[k].velocidade)
            cap = float(inst.veiculos[k].capacidade)

            # dados (para checar viabilidade mínima)
            a = [0.0] * nbn
            b = [float("inf")] * nbn
            s = [0.0] * nbn
            dem = [0.0] * nbn
            for n in range(nbn):
                noh = inst.noh[n]
                if noh.READY_TIME: a[n] = noh.READY_TIME[0]
                if noh.DUE_DATE:   b[n] = noh.DUE_DATE[0]
                if noh.SERVICE_TIME: s[n] = noh.SERVICE_TIME[0]
                dem[n] = float(getattr(noh, "DEMAND", 0.0))

            dist = inst.matriz_distancia

            def tt(i, j):
                return dist[i][j] / vel

            for i in range(1, nbcd + 1):
                # capacidade
                if dem[i] > cap:
                    continue

                # checa janela: dep0 -> i -> depf (bem simples)
                t = max(a[dep0], 0.0) + s[dep0] + tt(dep0, i)
                if t < a[i]: t = a[i]
                if t > b[i]:
                    continue

                t2 = t + s[i] + tt(i, depf)
                if t2 < a[depf]: t2 = a[depf]
                if t2 > b[depf]:
                    continue

                rota = [dep0, i, depf]
                custo_real = tt(dep0, i) + tt(i, depf)
                custo_pool = float(custo_real + bigM)

                bin_xij = [0] * nbcd
                bin_xij[i - 1] = 1

                sol_pool.rotas[k]['sequencia_rota'].append(rota)
                sol_pool.rotas[k]['rotas_binaria'].append(bin_xij)
                sol_pool.rotas[k]['custo'].append(custo_pool)
                sol_pool.rotas[k]['vezes_usada_geral'].append(0)
                sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
                sol_pool.rotas[k]['lbd_iteracao'].append([])

    #fim da gulosa

    def gera_rotas_iniciaisUNICA(self, inst, sol, custo_alto=1e7):

        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))

        #sol.rotas = {}

        for k in range(inst.nbv):
            # inicializa listas para o veículo k
            #k=len(sol.rotas[ki])
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

    ###########fim de rotas iniciais

    def geracao_colunas(self, inst, sol, tipo_geracao):
        print()
        print()
        print("\n\n========Geracao de Colunas==========")

        with open("log_gc.txt", "w", encoding="utf-8") as f:
            f.write("iteracao;veiculo;custo_original;custo_reduzido;sequencia;data_hora\n")

        primeiromip = True
        # auxiliares -
        arcos_usados_ijk = [[[0 for _ in range(inst.nbv)] for _ in range(inst.nbn)] for _ in range(inst.nbn)]

        self.total_iteracoes_incumbente = 0

        ##########################################################################3

        # self.gera_rotas_iniciais(inst, sol)
        self.gera_rotas_iniciaisUNICA(inst, sol)
        # self.gera_rotas_artificiais(inst, sol)
        # self.gerar_rotas_unitarias_insercao(inst, sol)

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
        # model.setParam('OutputFlag', 0)
        lbd = []  # lista de variáveis lbd (rotas)

        for k in range(inst.nbv):
            lbd.append([])

        # Adiciona variáveis iniciais
        for r in rotas:
            v = model.addVar(
                lb=0, ub=1,
                obj=r['custo'],
                vtype=GRB.CONTINUOUS,
                # vtype=GRB.BINARY,
                name=f"lb_{r['veic']}_{r['ind']}"
            )
            lbd[r['veic']].append(v)

        model.update()

        # Restrições de visita única
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol.rotas.keys():  # range(inst.nbv):
                nrotas = len(sol.rotas[k]['rotas_binaria'])
                for p in range(nrotas):
                    expr += lbd[k][p] * sol.rotas[k]['rotas_binaria'][p][i]
            model.addConstr(expr == 1, name=f"bin_xij_{i}")  # $$$$$$$$$$$$$$$
            # model.addConstr(expr >= 1, name=f"bin_xij_{i}")
            # teste com >=  com uma coluna unica artificial

        # Restrições de uso máximo de rota por veículo
        constr_veic = {}
        for k in sol.rotas.keys():  # range(inst.nbv):
            expr = gp.LinExpr()
            nrotas = len(sol.rotas[k]['rotas_binaria'])
            for p in range(nrotas):
                expr += lbd[k][p]
            # constr_veic[k] =model.addConstr(expr >= 1, name=f"rlbd_{k}")
            constr_veic[k] = model.addConstr(expr == 1, name=f"rlbd_{k}")  # $$$$$$$$$$$$$$$

        # Objetivo
        model.ModelSense = GRB.MINIMIZE
        model.update()
        sol.numero_de_rotas = [len(sol.rotas[k]['rotas_binaria']) for k in sol.rotas.keys()]  # range(inst.nbv)]

        contador = 0
        globalIteration = 0
        arcos_fixados_em_1 = set()
        initerruptall = True
        var_testes_arcos_igual_1 = 0
        max_var_testes_arcos_igual_1 = 5  # editavel
        operacao = 'fixa arcos recorrentes'
        # operacao='fixa arcos fracionados'

        ############################################ MECANISMO ITERATIVO #######################################################
        custo_global = 0
        iteracao_sem_melhora = 0
        indice_corte = 0

        nbMAXIteracNoOpt = 10
        nbIteracNoOpt = 0
        nbIteracNoChange = 0

        while (initerruptall):  # initerruptall
            print(
                "\n\n============================================================================= ITERACAO GLOBAL " + str(
                    globalIteration))
            initerruptall = False

            model.optimize()
            print("%%%%%%%%%%%%%%%%% iteracao " + str(self.total_iteracoes_CG))
            if model.Status != GRB.OPTIMAL:

                if nbIteracNoOpt < nbMAXIteracNoOpt:
                    nbIteracNoOpt += 1
                    print("Problema mestre não resolvido/ótimo. Parando.")
                    # removo os cortes

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
                print(f"\n--- Colunas Escolhidas na Solução do Mestre (Iteração {self.total_iteracoes_CG}) ---")
                custo_total_iteracao = 0
                for k in sol.rotas.keys():  # range(inst.nbv):

                    for p in range(len(lbd[k])):

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

                # ==================================================================
                # FIM Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================

                # Atualiza self.LRRecency, self.LRLast, self.LRAcc
                for k in sol.rotas.keys():
                    for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                        lambda_val = lbd[k][p].X  # valor da variável lambda no modelo mestre

                        if lambda_val > 1e-6:
                            rota_bin = sol.rotas[k]['rotas_binaria'][p]
                            sequencia = sol.rotas[k]['sequencia_rota'][p]

                            # Atualiza self.LRAcc
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                self.LRAcc[i_no][j_no][k] += 1
                                self.LRLast[i_no][j_no][k] = 1
                                self.LRRecency[i_no][j_no][k] += lambda_val
                        else:
                            # Zera self.LRLast se a rota não foi usada
                            sequencia = sol.rotas[k]['sequencia_rota'][p]
                            for i in range(len(sequencia) - 1):
                                i_no = sequencia[i]
                                j_no = sequencia[i + 1]
                                self.LRLast[i_no][j_no][k] = 0

                if custo_total_iteracao == custo_global:
                    nbIteracNoOpt += 1
                    nbIteracNoChange += 1

                    print("SEM MELHORA ITERACAO " + str(nbIteracNoChange))
                    # if nbIteracNoChange==nbIMAXteracNoChange:
                    #    break

                else:
                    nbIteracNoChange = 0

                naoGeraCorteArco = False  # seto false para que o proximo if nao aconteca' ele gera cortes
                if custo_total_iteracao == custo_global and naoGeraCorteArco:

                    # obter o primeiro MIP gerado da GC pura inicial' faz só o primeiro
                    ##=====================terminou a GC

                    if (primeiromip):
                        print("/n/n/n-------- PRIMEIRO MIP------------")

                        # Altera o tipo de todas as variáveis lambda para Binário
                        for k in sol.rotas.keys():  # range(inst.nbv):
                            for var_lambda in lbd[k]:
                                var_lambda.vtype = GRB.BINARY

                        model.update()

                        model.optimize()

                        # exportar as variaveis
                        if model.Status == GRB.OPTIMAL:
                            primeiromip = False
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
                                        # sol.rotas_escolhidas= {}
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

                    # """

                    iteracao_sem_melhora += 1

                    for k in sol.rotas.keys():
                        for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                            lambda_val = lbd[k][p].X
                            if lambda_val > 1e-6:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    self.Inc[i_no][j_no][k] += 1

                    print("ITERACAO SEM MELHORA")

                    self.total_iteracoes_search += 1

                    for k in sol.rotas.keys():
                        for p, rota in enumerate(sol.rotas[k]['sequencia_rota']):
                            lambda_val = lbd[k][p].X
                            if lambda_val > 1e-6:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    self.SearchRecency[i_no][j_no][k] += lambda_val
                                    self.SearchLast[i_no][j_no][k] = 1
                            else:
                                sequencia = sol.rotas[k]['sequencia_rota'][p]
                                for i in range(len(sequencia) - 1):
                                    i_no = sequencia[i]
                                    j_no = sequencia[i + 1]
                                    self.SearchLast[i_no][j_no][k] = 0

                    # Expressão para fixar um arco em 1
                    # quantidade de arcos fixados?
                    if operacao == 'fixa arcos recorrentes':  # case 'fixa arcos recorrentes':

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
                        if top5_arcos:  # mostrado com i-j-k-numero de vezes
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
                                model.addConstr(expr_fix >= 1,
                                                name=f"arco_fixado_{i_sel}_{j_sel}_{k_sel}")  # nome da restricao fixa
                                arcos_fixados_em_1.add((i_sel, j_sel, k_sel))
                                iteracao_sem_melhora = 0
                                initerruptall = True
                                print(
                                    f"Restrição adicionada: veículo {k_sel} deve ter pelo menos uma rota contendo o arco {i_sel}->{j_sel}.")
                                model.update()

                                # mostro no arquivo log que fixei esse arco

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
                            # fim do case 'fixa arcos'
                            if operacao == 'fixa arcos fracionados':
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

                                        # mostrar solucao nova
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
                    iteracao_sem_melhora = 0
                    custo_global = custo_total_iteracao

                # continua o wile do código

                print(f"Custo Total do Mestre  nesta iteração: {custo_total_iteracao:.4f}")
                print("--- Fim da Listagem de Colunas ---\n")

                ###escrever sol
                self.registrar_fo_gc(inst, self.total_iteracoes_CG, custo_total_iteracao)

                # ==================================================================
                # FIM DO Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================

                #  valores duais das restrições de visita única
                pi = [model.getConstrByName(f"bin_xij_{i}").Pi for i in range(inst.nbcd)]

                sigma = [model.getConstrByName(f"rlbd_{k}").Pi for k in sol.rotas.keys()]  # k in range(inst.nbv)]

                # initerruptall = False

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
                for k in sol.rotas.keys():  # range(inst.nbv):

                    # Subproblema retorna a nova rota e custo
                    print(
                        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!inicia   roda sub probl do veic " + str(k))

                    duais_para_k = {}
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
                        nova_rota, custo_red = self.subproblema(inst, pi, sigma[k], k, duais_arcos=duais_para_k)

                    if (tipo_geracao == "PD"):
                        nova_rota, custo_red = self.SUB_PROG_DIN(inst, pi, sigma[k], k)

                    if nova_rota is not None:
                        # Extrai as informações do dicionário retornado
                        custo_original = nova_rota['custo']
                        sequencia_clientes = nova_rota['clientes']
                        rota_binaria = nova_rota['bin_xij']

                        print(f"22222222222222222 Terminou roda sub probl do veic {k}, com CUSTO RED " + str(custo_red))

                        if custo_red < -1e-6:
                            initerruptall = True
                            print("___________ INITERRUPT TRUE")
                            self.registrar_nova_coluna(k, sequencia_clientes, custo_original, custo_red,
                                                       self.total_iteracoes_CG, inst, tipo_geracao)

                            # Adiciona nova coluna ao modelo mestre
                            constrs_clientes = [model.getConstrByName(f"bin_xij_{i}") for i in range(inst.nbcd)]

                            coluna = gp.Column(rota_binaria, constrs_clientes)

                            coluna.addTerms(1.0, model.getConstrByName(f"rlbd_{k}"))  # $$$$$$$

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
                                sequencia_clientes)  # Adiciona depósito
                            sol.rotas[k]['custo'].append(custo_original)
                            sol.rotas[k]['vezes_usada_geral'].append(0)
                            sol.numero_de_rotas[k] += 1
                            print("NOVA ROTA ADICIONADA veiculo " + str(k))
                            print(sequencia_clientes)
                            model.update()

                globalIteration += 1

            """
            if initerruptall==False:
                break
            """
            self.total_iteracoes_CG += 1

        ##=====================terminou a GC
        print("/n/n/n-------- INICIOU MIP------------")
        # model.write()
        # MIP
        # Altera o tipo de todas as variáveis lambda para Binário
        for k in sol.rotas.keys():  # range(inst.nbv):
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

                        # salvar na sol como rota escolhida

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

            self.registrar_fo_gc(inst, -1, custo_total_inteiro)



        else:
            print("Não foi possível encontrar uma solução ótima inteira para o problema mestre final.")

        ##########iteracoes colunas
        print(arcos_usados_ijk)

    def subproblema(self, inst, pi, sigma, k, duais_arcos=None):
        # adicionar mais argumentos para na resolucao de fixar arcos como 0 ou 1- lista de arcos
        print("sub _ k" + str(k))
        # print("=========")
        # print("pi "+str(pi) )
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
            # model.addConstr(u[0] == 0) #?

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

            # if model.Status == GRB.OPTIMAL and model.ObjVal < -1e-6:
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
                bin_xij = [0 for _ in range(nbn - 2)]
                for v in rota:
                    if v != 0 and v != nbn - 1:
                        bin_xij[v - 1] = 1
                custo_total = sum(
                    inst.matriz_distancia[rota[i]][rota[i + 1]] / inst.veiculos[k].velocidade
                    for i in range(len(rota) - 1)
                )
                print("««««««« custo subido para o mestre " + str(custo_total))
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

            if (iteracao == -1):
                writer.writerow(["MIP", f"{valor_fo:.6f}"])
            else:
                if (iteracao == -2):
                    writer.writerow(["COMPACTO", f"{valor_fo:.6f}"])
                else:
                    writer.writerow([iteracao, f"{valor_fo:.6f}"])

    def registrar_nova_coluna(self, k, rota, custo_original, custo_reduzido, iteracao, inst, tipo_geracao):
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

    def SUB_PROG_DIN(self, inst, pi, sigma_k, k,
                     arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        import math
        from collections import deque

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}  # (i,j)->dual arco

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        # ------------------ dados ------------------
        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = inst.veiculos[k].capacidade
        velocidade = inst.veiculos[k].velocidade

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        # ------------------ FIXOS (FORÇAR) ------------------
        # succ_fixo[i] = j  e pred_fixo[j] = i

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in arcos_fixados:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None  # conflito: 2 sucessores fixos
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None  # conflito: 2 predecessores fixos
            succ_fixo[i] = j
            pred_fixo[j] = i


        tol = 1e-6

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        # fronteira por estado (no, mask_clientes) com lista de labels não dominados
        fronteira = {}

        rotulos = []
        abertos = deque()

        tempo_inicial = max(a[dep0], 0.0)
        rotulos.append({
            "no": dep0,
            "tempo": tempo_inicial,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True
        })
        abertos.append(0)
        fronteira[(dep0, 0)] = [0]

        melhor_indice = None
        melhor_custo_reduzido = math.inf

        while abertos:
            idx_atual = abertos.popleft()
            r_atual = rotulos[idx_atual]
            if not r_atual.get("ativo", True):
                continue

            no_i = r_atual["no"]
            tempo_i = r_atual["tempo"]
            carga_i = r_atual["carga"]
            custo_mod_i = r_atual["custo_mod"]
            mask_i = r_atual["mask"]

            if no_i == depf:
                if custo_mod_i < melhor_custo_reduzido:
                    melhor_custo_reduzido = custo_mod_i
                    melhor_indice = idx_atual
                continue

            # ------------------ candidatos (FORÇA succ fixo) ------------------
            if no_i in succ_fixo:
                candidatos = [succ_fixo[no_i]]
            else:
                candidatos = []
                for c in range(1, nbcd + 1):
                    if (mask_i & cliente_mask(c)) == 0:
                        candidatos.append(c)
                candidatos.append(depf)

            for j in candidatos:
                # proibido
                if (no_i, j) in arcos_proibidos:
                    continue

                # FORÇA pred fixo: só pode entrar em j vindo do predecessor fixo
                if j in pred_fixo and pred_fixo[j] != no_i:
                    continue

                # clientes visitados
                nova_mask = mask_i
                if 1 <= j <= nbcd:
                    bit = cliente_mask(j)
                    if (mask_i & bit) != 0:
                        continue
                    nova_mask = mask_i | bit

                # capacidade
                nova_carga = carga_i
                if 1 <= j <= nbcd:
                    nova_carga += d[j]
                if nova_carga > cap_k:
                    continue

                # janela de tempo
                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j]:
                    continue

                # custo reduzido: c_ij - mu_ij - pi(cliente) - sigma
                custo_mod_novo = custo_mod_i + travel_time(no_i, j)

                # dual do arco (se existir)
                custo_mod_novo -= float(mu_arc.get((no_i, j), 0.0))

                if 1 <= j <= nbcd:
                    custo_mod_novo -= float(pi[j - 1])
                if j == depf:
                    custo_mod_novo -= float(sigma_k)

                chave = (j, nova_mask)
                lista = fronteira.get(chave, [])

                dominado = False
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(r_old["custo_mod"], r_old["tempo"], r_old["carga"],
                              custo_mod_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(custo_mod_novo, tempo_chegada, nova_carga,
                              r_old["custo_mod"], r_old["tempo"], r_old["carga"]):
                        rotulos[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                novo_rotulo = {
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_mod_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True
                }
                idx_novo = len(rotulos)
                rotulos.append(novo_rotulo)
                abertos.append(idx_novo)

                nova_lista.append(idx_novo)
                fronteira[chave] = nova_lista

        # ------------------ pós ------------------
        if melhor_indice is None:
            return None, None

        if melhor_custo_reduzido >= -1e-6:
            return None, None

        # reconstrói rota
        rota_reversa = []
        idx = melhor_indice
        while idx is not None:
            rota_reversa.append(rotulos[idx]["no"])
            idx = rotulos[idx]["pai"]
        rota = list(reversed(rota_reversa))

        # custo real (sem duais)
        custo_real = 0.0
        for t in range(len(rota) - 1):
            custo_real += travel_time(rota[t], rota[t + 1])

        bin_xij = [0 for _ in range(nbcd)]
        for v in rota:
            if 1 <= v <= nbcd:
                bin_xij[v - 1] = 1

        rota_dict = {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}
        return rota_dict, melhor_custo_reduzido

    def SUB_PROG_DINLivre(self, inst, pi, sigma_k, k,
                     arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        import math
        from collections import deque

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}  # (i,j)->dual arco

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        # ------------------ dados ------------------
        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = inst.veiculos[k].capacidade
        velocidade = inst.veiculos[k].velocidade

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        # ------------------ FIXOS (FORÇAR) ------------------
        # succ_fixo[i] = j  e pred_fixo[j] = i

        succ_fixo = {}
        pred_fixo = {}
        for (i, j) in arcos_fixados:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None  # conflito: 2 sucessores fixos
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None  # conflito: 2 predecessores fixos
            succ_fixo[i] = j
            pred_fixo[j] = i

        succ_fixo = {}
        pred_fixo = {}

        tol = 1e-6

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        # fronteira por estado (no, mask_clientes) com lista de labels não dominados
        fronteira = {}

        rotulos = []
        abertos = deque()

        tempo_inicial = max(a[dep0], 0.0)
        rotulos.append({
            "no": dep0,
            "tempo": tempo_inicial,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True
        })
        abertos.append(0)
        fronteira[(dep0, 0)] = [0]

        melhor_indice = None
        melhor_custo_reduzido = math.inf

        while abertos:
            idx_atual = abertos.popleft()
            r_atual = rotulos[idx_atual]
            if not r_atual.get("ativo", True):
                continue

            no_i = r_atual["no"]
            tempo_i = r_atual["tempo"]
            carga_i = r_atual["carga"]
            custo_mod_i = r_atual["custo_mod"]
            mask_i = r_atual["mask"]

            if no_i == depf:
                if custo_mod_i < melhor_custo_reduzido:
                    melhor_custo_reduzido = custo_mod_i
                    melhor_indice = idx_atual
                continue

            # ------------------ candidatos (FORÇA succ fixo) ------------------
            if no_i in succ_fixo:
                candidatos = [succ_fixo[no_i]]
            else:
                candidatos = []
                for c in range(1, nbcd + 1):
                    if (mask_i & cliente_mask(c)) == 0:
                        candidatos.append(c)
                candidatos.append(depf)

            for j in candidatos:
                # proibido
                if (no_i, j) in arcos_proibidos:
                    continue

                # FORÇA pred fixo: só pode entrar em j vindo do predecessor fixo
                if j in pred_fixo and pred_fixo[j] != no_i:
                    continue

                # clientes visitados
                nova_mask = mask_i
                if 1 <= j <= nbcd:
                    bit = cliente_mask(j)
                    if (mask_i & bit) != 0:
                        continue
                    nova_mask = mask_i | bit

                # capacidade
                nova_carga = carga_i
                if 1 <= j <= nbcd:
                    nova_carga += d[j]
                if nova_carga > cap_k:
                    continue

                # janela de tempo
                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j]:
                    continue

                # custo reduzido: c_ij - mu_ij - pi(cliente) - sigma
                custo_mod_novo = custo_mod_i + travel_time(no_i, j)

                # dual do arco (se existir)
                custo_mod_novo -= float(mu_arc.get((no_i, j), 0.0))

                if 1 <= j <= nbcd:
                    custo_mod_novo -= float(pi[j - 1])
                if j == depf:
                    custo_mod_novo -= float(sigma_k)

                chave = (j, nova_mask)
                lista = fronteira.get(chave, [])

                dominado = False
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(r_old["custo_mod"], r_old["tempo"], r_old["carga"],
                              custo_mod_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(custo_mod_novo, tempo_chegada, nova_carga,
                              r_old["custo_mod"], r_old["tempo"], r_old["carga"]):
                        rotulos[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                novo_rotulo = {
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_mod_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True
                }
                idx_novo = len(rotulos)
                rotulos.append(novo_rotulo)
                abertos.append(idx_novo)

                nova_lista.append(idx_novo)
                fronteira[chave] = nova_lista

        # ------------------ pós ------------------
        if melhor_indice is None:
            return None, None

        if melhor_custo_reduzido >= -1e-6:
            return None, None

        # reconstrói rota
        rota_reversa = []
        idx = melhor_indice
        while idx is not None:
            rota_reversa.append(rotulos[idx]["no"])
            idx = rotulos[idx]["pai"]
        rota = list(reversed(rota_reversa))

        # custo real (sem duais)
        custo_real = 0.0
        for t in range(len(rota) - 1):
            custo_real += travel_time(rota[t], rota[t + 1])

        bin_xij = [0 for _ in range(nbcd)]
        for v in rota:
            if 1 <= v <= nbcd:
                bin_xij[v - 1] = 1

        rota_dict = {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}
        return rota_dict, melhor_custo_reduzido

    def SUB_PROG_DINLivre2(self, inst, pi, sigma_k, k, arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        import math
        from collections import deque


        arcos_proibidos = set()
        arcos_fixados = set()  # não será forçado aqui (teste)
        if mu_arc is None:
            mu_arc = {}  # (i,j)->dual arco

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        # dados
        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = inst.veiculos[k].capacidade
        velocidade = inst.veiculos[k].velocidade

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        tol = 1e-6

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        # fronteira por estado (no, mask_clientes) com lista de labels não dominados
        fronteira = {}

        rotulos = []
        abertos = deque()

        tempo_inicial = max(a[dep0], 0.0)
        rotulos.append({
            "no": dep0,
            "tempo": tempo_inicial,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True
        })
        abertos.append(0)
        fronteira[(dep0, 0)] = [0]

        melhor_indice = None
        melhor_custo_reduzido = math.inf

        while abertos:
            idx_atual = abertos.popleft()
            r_atual = rotulos[idx_atual]
            if not r_atual.get("ativo", True):
                continue

            no_i = r_atual["no"]
            tempo_i = r_atual["tempo"]
            carga_i = r_atual["carga"]
            custo_mod_i = r_atual["custo_mod"]
            mask_i = r_atual["mask"]

            if no_i == depf:
                if custo_mod_i < melhor_custo_reduzido:
                    melhor_custo_reduzido = custo_mod_i
                    melhor_indice = idx_atual
                continue

            # candidatos = clientes não visitados + depf
            candidatos = []
            for c in range(1, nbcd + 1):
                if (mask_i & cliente_mask(c)) == 0:
                    candidatos.append(c)
            candidatos.append(depf)

            for j in candidatos:
                if (no_i, j) in arcos_proibidos:
                    continue

                # clientes visitados
                nova_mask = mask_i
                if 1 <= j <= nbcd:
                    bit = cliente_mask(j)
                    if (mask_i & bit) != 0:
                        continue
                    nova_mask = mask_i | bit

                # capacidade
                nova_carga = carga_i
                if 1 <= j <= nbcd:
                    nova_carga += d[j]
                if nova_carga > cap_k:
                    continue

                # janela de tempo
                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j]:
                    continue

                # custo reduzido: c_ij - mu_ij - pi(cliente) - sigma
                custo_mod_novo = custo_mod_i + travel_time(no_i, j)

                # dual do arco (se existir)
                custo_mod_novo -= float(mu_arc.get((no_i, j), 0.0))

                if 1 <= j <= nbcd:
                    custo_mod_novo -= float(pi[j - 1])
                if j == depf:
                    custo_mod_novo -= float(sigma_k)

                chave = (j, nova_mask)
                lista = fronteira.get(chave, [])

                dominado = False
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(r_old["custo_mod"], r_old["tempo"], r_old["carga"],
                              custo_mod_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(custo_mod_novo, tempo_chegada, nova_carga,
                              r_old["custo_mod"], r_old["tempo"], r_old["carga"]):
                        rotulos[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                novo_rotulo = {
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_mod_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True
                }
                idx_novo = len(rotulos)
                rotulos.append(novo_rotulo)
                abertos.append(idx_novo)

                nova_lista.append(idx_novo)
                fronteira[chave] = nova_lista

        # pós
        if melhor_indice is None:
            return None, None

        if melhor_custo_reduzido >= -1e-6:
            return None, None

        # reconstrói rota
        rota_reversa = []
        idx = melhor_indice
        while idx is not None:
            rota_reversa.append(rotulos[idx]["no"])
            idx = rotulos[idx]["pai"]
        rota = list(reversed(rota_reversa))

        # custo real (sem duais)
        custo_real = 0.0
        for t in range(len(rota) - 1):
            custo_real += travel_time(rota[t], rota[t + 1])

        bin_xij = [0 for _ in range(nbcd)]
        for v in rota:
            if 1 <= v <= nbcd:
                bin_xij[v - 1] = 1

        rota_dict = {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}
        return rota_dict, melhor_custo_reduzido



    def SUB_PROG_DINCPP(self, inst, pi, sigma_k, k, arcos_proibidos=None, arcos_fixados=None):
        import sys
        import numpy as np
        from pathlib import Path

        # 1) apontar para a pasta do .pyd
        # RECOMENDADO: Release para performance
        pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "x64" / "Release"
        if not pyd_dir.exists():
            # fallback Debug
            pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "x64" / "Debug"

        if str(pyd_dir) not in sys.path:
            sys.path.insert(0, str(pyd_dir))

        import vrptw_pd  # seu módulo .pyd

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()

        nbn = inst.nbn
        nbcd = inst.nbcd

        cap_k = float(inst.veiculos[k].capacidade)
        vel = float(inst.veiculos[k].velocidade)

        # a,b,s,d
        a = np.empty(nbn, dtype=np.float64)
        b = np.empty(nbn, dtype=np.float64)
        s = np.empty(nbn, dtype=np.float64)
        d = np.empty(nbn, dtype=np.float64)

        for i in range(nbn):
            noh = inst.noh[i]
            a[i] = noh.READY_TIME[0] if noh.READY_TIME else 0.0
            b[i] = noh.DUE_DATE[0] if noh.DUE_DATE else 1e18
            s[i] = noh.SERVICE_TIME[0] if noh.SERVICE_TIME else 0.0
            d[i] = float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0

        # tt = dist/vel
        dist = np.asarray(inst.matriz_distancia, dtype=np.float64)
        tt = dist / vel

        # F: proibidos -> mp x 2
        if len(arcos_proibidos) == 0:
            F = np.zeros((0, 2), dtype=np.int32)
        else:
            F = np.array(list(arcos_proibidos), dtype=np.int32).reshape(-1, 2)

        # FX: fixados -> mf x 2
        if len(arcos_fixados) == 0:
            FX = np.zeros((0, 2), dtype=np.int32)
        else:
            FX = np.array(list(arcos_fixados), dtype=np.int32).reshape(-1, 2)

        # pi
        pi_np = np.asarray(pi, dtype=np.float64)

        # chamada C++
        return vrptw_pd.SUB_PROG_DIN(tt, a, b, s, d, pi_np, float(sigma_k), cap_k, F, FX)

    def registrar_novo_corte(self, iteracao, indice_corte, i, j, k, nome_arquivo="log_gc.txt"):

        with open(nome_arquivo, "a", encoding="utf-8") as f:
            linha = (
                f"{iteracao}; corte{indice_corte} [{i},{j},{k}]; "
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            )
            f.write(linha)
