import random


random.seed(42)
import copy
import time
import gurobipy as gp
from aiohttp._websocket import mask
from asyncssh.asn1 import BOOLEAN
from gurobipy import GRB, quicksum
# from holoviews.examples.gallery.demos.bokeh.square_limit import nonet
from sipbuild.generator.parser.annotations import boolean
import json
import datetime
import os
import csv
from datetime import datetime
import math
from collections import defaultdict

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
        self.custo_mip = None
        self.custo_lp_HERDADO = None
        self.custo_mip_HERDADO = None


        self.lambdas = {}
        self.solucao_inteira = False

        self.matriz_rc = {}

        # controle de validade
        self.matriz_rc_valida = False

        # Novos campos para log
        self.status = "ativo"  # 'ativo', 'resolvido', 'podado'
        self.motivo_poda = None  # string explicando o motivo
        self.branching_from = None  # {'pai': id, 'arco': (i,j,k), 'tipo': 'proibido'/'obrigatorio'}

        # chave: (i,j,k) ou (i,j) dependendo do  padrão
        self.score_arcos_lambda = {}  # dict: arco -> float

        # tabu
        # --- TABU POR ARCO ---
        self.freq_arc = None  # quantas vezes o arco apareceu
        self.last_arc = None  # última iteração que apareceu
        self.tabu_until = None  # até qual iteração o arco está tabu

        self.tabu_tenure = 9991  # quantas iterações fica tabu- to pensando em colocar max(5, alfa*nbn)

    def criaMatriRC(self, inst):
        self.matriz_rc = {
            k: [[0.0] * inst.nbn for _ in range(inst.nbn)] for k in range(inst.nbv)
        }


class Metodos:

    def __init__(self, inst):
        n = inst.nbn
        K = inst.nbv
        self.tabb = 0

        def m3d():
            return [[[0 for _ in range(K)] for _ in range(n)] for _ in range(n)]

        # Arcos usados
        self.arcos_usados_ijk = m3d()

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
        self.printarsol=True

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
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # self.hist_bp.append(f"[{timestamp}] {msg}")

    def _salvar_hist_bp_txt(self, nome_arquivo=None):

        """

        if not hasattr(self, "hist_bp") or not self.hist_bp:
            return
        if nome_arquivo is None:
            nome_arquivo = f"hist_bp_{self.log_bp['run_id']}.txt"
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            for linha in self.hist_bp:
                f.write(linha + "\n")
        print(f"Histórico do B&P salvo em {nome_arquivo}")
        """

    def _get_nivel_entry(self, profundidade):
        """Garante que exista um entry para o nível e retorna."""

        """
        while len(self.log_bp["niveis"]) <= profundidade:
            self.log_bp["niveis"].append({
                "nivel": len(self.log_bp["niveis"]),
                "nos": []
            })
        return self.log_bp["niveis"][profundidade]
        """

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

        # nivel_entry = self._get_nivel_entry(profundidade)
        # nivel_entry["nos"].append(info_no)

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

    def exportar_colunas_pool_raiz_csv(self, sol_pool, no_bp, pool_ini_por_k, nome_arquivo=None):
        if nome_arquivo is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"POOL_RAIZ_no{no_bp.id_no}_{ts}.csv"

        with open(nome_arquivo, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["k", "p", "custo", "seq", "binaria", "gerada_na_raiz"])

            for k in sol_pool.rotas.keys():
                seqs = sol_pool.rotas[k]["sequencia_rota"]
                bins = sol_pool.rotas[k]["rotas_binaria"]
                custos = sol_pool.rotas[k]["custo"]

                p0 = pool_ini_por_k.get(k, 0)
                for p in range(len(seqs)):
                    gerada = 1 if p >= p0 else 0
                    w.writerow([
                        k,
                        p,
                        float(custos[p]),
                        json.dumps(seqs[p]),
                        json.dumps(bins[p]),
                        gerada
                    ])

        print(f"[RAIZ] Exportou pool para: {nome_arquivo}")
        return nome_arquivo

    def criar_filhos_por_arco075(self, inst, sol_pool, no_pai: NoBP, proximo_id: int, melhor_no_inteiro: NoBP = None):
        """
        Branching em arco + fixação em lote:
        - fixa todos os arcos que aparecem na incumbente (melhor_no_inteiro)
        - e que no LP do nó atual têm arc_score > 0.75
        """

        tolerancia = 1e-3
        limiar_fix = 0.65

        # ----------------------------
        # (A) extrai arcos da incumbente (sem salvar variável global)
        # ----------------------------
        inc_arcs = set()
        if melhor_no_inteiro is not None and hasattr(melhor_no_inteiro, "lambdas"):
            for (k, p), val in melhor_no_inteiro.lambdas.items():
                if val >= 1.0 - 1e-6:
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    for t in range(len(seq) - 1):
                        inc_arcs.add((seq[t], seq[t + 1], k))

        # ----------------------------
        # (B) monta fixações extras usando arc_score do nó atual
        # ----------------------------
        arc_score = getattr(no_pai, "arc_score", {})  # (i,j,k) -> soma lambdas no nó
        fix_extra = set()

        for arco in inc_arcs:
            if arco in no_pai.arcos_proibidos:
                continue
            if arco in no_pai.arcos_fixados_em_1:
                continue
            if arc_score.get(arco, 0.0) > limiar_fix:
                fix_extra.add(arco)

        # base para ambos os filhos
        base_fix = set(no_pai.arcos_fixados_em_1) | fix_extra
        base_proib = set(no_pai.arcos_proibidos)

        # ----------------------------
        # (C) escolhe 1 arco para branching (evita conflito com fix_extra)
        #     Sugestão: escolher arco mais fracionário via arc_score (mais próximo de 0.5)
        #     (se arc_score não existir, cai no lambda/rota como antes)
        # ----------------------------
        arco_escolhido = None

        if arc_score:
            # pega candidatos que NÃO estão fixados/proibidos e não conflitam com fix_extra
            best = None
            for (i, j, k), sc in arc_score.items():
                arco = (i, j, k)
                if arco in base_fix or arco in base_proib:
                    continue
                if i == 0 and j == inst.nbn - 1:
                    continue
                # queremos o mais fracionário (perto de 0.5)
                if sc <= tolerancia or sc >= 1 - tolerancia:
                    continue
                key = abs(sc - 0.5)
                if (best is None) or (key < best[0]):
                    best = (key, arco)
            if best is not None:
                arco_escolhido = best[1]

        # fallback: usa seu método antigo (lambda fracionário em rota) se não achou por arc_score
        if arco_escolhido is None:
            for (k, p), val in no_pai.lambdas.items():
                if not (tolerancia < val < 1 - tolerancia):
                    continue

                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                for idx in range(len(seq) - 1):
                    i_no = seq[idx]
                    j_no = seq[idx + 1]

                    if i_no == 0 and j_no == inst.nbn - 1:
                        continue

                    arco = (i_no, j_no, k)

                    if arco in base_fix or arco in base_proib:
                        continue

                    arco_escolhido = arco
                    break

                if arco_escolhido is not None:
                    break

        if arco_escolhido is None:
            return None, None, proximo_id

        i_sel, j_sel, k_sel = arco_escolhido
        print(f" Branching no arco ({i_sel},{j_sel},{k_sel}) no nó {no_pai.id_no}")
        if fix_extra:
            print(f"  Fixações extras (incumbente & arc_score>{limiar_fix}): {len(fix_extra)}")

        # ----------------------------
        # (D) cria filhos
        # ----------------------------
        filho_esq = NoBP(
            id_no=proximo_id,
            arcos_fixados_em_1=base_fix,
            arcos_proibidos=base_proib.union({arco_escolhido})
        )
        filho_esq.branching_from = {
            "pai": no_pai.id_no,
            "arco": [i_sel, j_sel, k_sel],
            "tipo": "proibido",
            "fix_extra_qtd": len(fix_extra),
        }

        filho_dir = NoBP(
            id_no=proximo_id + 1,
            arcos_fixados_em_1=base_fix.union({arco_escolhido}),
            arcos_proibidos=base_proib
        )
        filho_dir.branching_from = {
            "pai": no_pai.id_no,
            "arco": [i_sel, j_sel, k_sel],
            "tipo": "obrigatorio",
            "fix_extra_qtd": len(fix_extra),
        }

        self._append_hist_bp(
            f"Do nó {no_pai.id_no} filhos {filho_esq.id_no} (proíbe {i_sel}->{j_sel},k={k_sel}) "
            f"e {filho_dir.id_no} (obriga {i_sel}->{j_sel},k={k_sel}); "
            f"fix_extra={len(fix_extra)}."
        )

        return filho_esq, filho_dir, proximo_id + 2

    def criar_filhos_por_arco(self, inst, sol, no_pai: NoBP, proximo_id: int):
        tolerancia = 1e-3

        # 1) calcula soma dos lambdas por arco (i,j,k) no nó pai
        soma_arco = {}  # (i,j,k) -> float

        for (k, p), lam in no_pai.lambdas.items():
            lam = float(lam)
            if lam <= tolerancia:
                continue

            seq = sol.rotas[k]['sequencia_rota'][p]
            for idx in range(len(seq) - 1):
                i_no = seq[idx]
                j_no = seq[idx + 1]

                # ignora arco direto dep0 -> depf se for o seu caso especial
                if i_no == 0 and j_no == inst.nbn - 1:
                    continue

                arco = (i_no, j_no, k)
                soma_arco[arco] = soma_arco.get(arco, 0.0) + lam

        # (opcional) salva no nó para log/uso futuro
        no_pai.score_arcos_lambda = dict(soma_arco)

        # 2) escolhe arco para branching: fracionário e mais próximo de 0.5
        melhor_arco = None
        melhor_gap = float("inf")

        for arco, val in soma_arco.items():
            if not (tolerancia < val < 1.0 - tolerancia):
                continue
            if arco in no_pai.arcos_fixados_em_1:
                continue
            if arco in no_pai.arcos_proibidos:
                continue

            gap = abs(val - 0.5)  # quanto mais perto de 0.5, melhor para branching
            if gap < melhor_gap:
                melhor_gap = gap
                melhor_arco = arco

        if melhor_arco is None:
            return None, None, proximo_id

        i_sel, j_sel, k_sel = melhor_arco
        print(
            f" Branching no arco ({i_sel},{j_sel},{k_sel}) no nó {no_pai.id_no} (soma_lambda≈{soma_arco[melhor_arco]:.4f})")

        pai_fix = set(no_pai.arcos_fixados_em_1)
        pai_proib = set(no_pai.arcos_proibidos)

        # filho esquerdo: proíbe arco
        filho_esq = NoBP(
            id_no=proximo_id,
            arcos_fixados_em_1=pai_fix,
            arcos_proibidos=pai_proib.union({melhor_arco})
        )
        filho_esq.branching_from = {"pai": no_pai.id_no, "arco": [i_sel, j_sel, k_sel], "tipo": "proibido"}
        filho_esq.custo_lp_HERDADO=no_pai.custo_lp
        filho_esq.custo_mip_HERDADO=no_pai.custo_mip

        # filho direito: obriga arco
        filho_dir = NoBP(
            id_no=proximo_id + 1,
            arcos_fixados_em_1=pai_fix.union({melhor_arco}),
            arcos_proibidos=pai_proib
        )
        filho_dir.branching_from = {"pai": no_pai.id_no, "arco": [i_sel, j_sel, k_sel], "tipo": "obrigatorio"}
        filho_dir.custo_lp_HERDADO=no_pai.custo_lp
        filho_dir.custo_mip_HERDADO=no_pai.custo_mip


        #self._append_hist_bp(
        #    f"Do nó {no_pai.id_no} gerados filhos {filho_esq.id_no} (proíbe arco {i_sel}->{j_sel}, k={k_sel}) "
        ##    f"e {filho_dir.id_no} (obriga arco {i_sel}->{j_sel}, k={k_sel})."
        #)

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

    def branch_and_price_global(self, inst, sol_pool, tipo_geracao="PD"):

        #limpeza arquivo principal dos logs meus
        nome_arquivo_log = f"log_bounds_{inst.nbcd}_{inst.ninst}.csv"

        with open(nome_arquivo_log, "w", encoding="utf-8") as f:
            f.write("no_id;z_inc;z_lp;z_li;total_colunas\n")


        raiz = True
        import time, math, json

        # === parâmetros ===
        time_limit = 3600
        gap = 1e-4
        total_nos_processados = 0

        z_inc = float("inf")  # melhor inteiro (UB)
        x_inc = None
        z_li = -float("inf")  # lower bound global (de nós com LB confiável)

        self.best_obj = -1
        self.total_nos = 0
        self.total_colunas = 0
        sol_pool.custo = -1
        sol_pool.rotas_escolhidas = {}

        t0 = time.time()

        melhor_no = None
        melhor_no_frac = None
        z_frac = float("inf")

        # === raiz ===
        id_no = 0
        raiz = NoBP(id_no=id_no)
        id_no += 1

        ativos = [(raiz, 0, None)]  # (no, profundidade, pai)

        while ativos:
            elapsed = time.time() - t0
            total_nos_processados += 1
            # -------------------------------------------------
            # z_li = min custo_lp entre nós abertos COM LB confiável
            # -------------------------------------------------
            custos_validos = [
                no.custo_lp
                for (no, _, _) in ativos
                if (no.custo_lp is not None) and getattr(no, "lb_confiavel", False)
            ]
            z_li = min(custos_validos) if custos_validos else -float("inf")

            # -------------------------------------------------
            # critério de parada por gap (só se z_li for válido)
            # -------------------------------------------------
            if (not math.isinf(z_inc)) and (z_li > -float("inf")):
                if z_inc - z_li <= gap:
                    print(f"Parou por gap: z_inc={z_inc:.4f}, z_li={z_li:.4f}")
                    break

            # -------------------------------------------------
            # critério de parada por tempo
            # -------------------------------------------------
            if elapsed >= time_limit:
                print(f"Parou por time limit: {elapsed:.1f}s")
                break

            # -------------------------------------------------
            # seleciona nó (DFS)
            # -------------------------------------------------
            no_atual, prof, pai = ativos.pop()
            print(f"\n=========== PROCESSANDO NÓ {no_atual.id_no} (prof={prof}, pai={pai}) ===========")
            no_atual.tabu_tenure = self.TABU_TENURE
            # -------------------------------------------------
            # resolve nó
            # -------------------------------------------------
            raiz = False
            t00 = time.time()
            #teste poda do no ja com o herdado
            if no_atual.custo_lp_HERDADO is not None and not math.isinf(z_inc):
                if no_atual.custo_lp_HERDADO > z_inc - 1e-6:
                    print(
                        f"Poda nó {no_atual.id_no} por bound herdado: {no_atual.custo_lp_HERDADO:.4f} >= incumbente {z_inc:.4f}")
                    no_atual.status = "podado"
                    no_atual.motivo_poda = "bound_herdado"
                    continue

            if (raiz):
                raiz = False
                self.resolver_no_com_poolRAIZ(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)
            else:
                self.resolver_no_com_pool(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)
                #self.resolver_no_com_pool_semSlack(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)

            # caso 0: LP inviável/sem solução
            print(f'Tempo total: {time.time() - t00:.1f}s')
            if no_atual.custo_lp is None:
                print("Nó inviável ou sem solução LP, podado.")
                no_atual.status = "podado"
                no_atual.motivo_poda = "LP_inviavel"
                continue

            z_lp = float(no_atual.custo_lp)
            z_mip = float(no_atual.custo_mip) if no_atual.custo_mip is not None else float("inf")
            no_atual.status = "resolvido"

            lb_ok = bool(getattr(no_atual, "lb_confiavel", False))

            print(
                f"[Nó {no_atual.id_no}] LP={z_lp:.4f} inteira={no_atual.solucao_inteira} "
                f"lb_confiavel={lb_ok} slack_final={getattr(no_atual, 'slack_sum_final', 0.0):.6f} "
                f"cg_convergiu={getattr(no_atual, 'cg_convergiu', False)} max_iter={getattr(no_atual, 'parou_por_max_iter', False)}"
            )

            # -------------------------------------------------
            # poda por bound (SÓ com LB confiável)
            # -------------------------------------------------
            if lb_ok and (not math.isinf(z_inc)) and (z_lp > z_inc - 1e-6):
                print(f"Poda por bound (LB ok): LP {z_lp:.4f} >= z_inc {z_inc:.4f}")
                no_atual.status = "podado"
                no_atual.motivo_poda = "poda_bound"
                continue

            # -------------------------------------------------
            # caso 1: nó tem novo inteiro
            # -------------------------------------------------
            if no_atual.solucao_inteira:
                print(f"Nó {no_atual.id_no} tem inteiro com custo {z_mip:.4f}")

                if z_mip < z_inc:
                    z_inc = z_mip

                    print(f"ATUALIZOU MELHOR INTEIRO Nó {no_atual.id_no} Valor INTEIRO com custo {z_mip:.4f}")
                    x_inc = getattr(no_atual, "lambdas_inteiras", None)
                    melhor_no = no_atual
                    print(f"Novo incumbente: z_inc={z_inc:.4f}")

                    # limpa ativos: só remove nós cujo LB confiável já prova que não melhoram
                    novos_ativos = []
                    for (n, p, pai_n) in ativos:
                        n_lb_ok = bool(getattr(n, "lb_confiavel", False))

                        if n.custo_lp is None:
                            novos_ativos.append((n, p, pai_n))
                        elif (not n_lb_ok):
                            # LB não confiável => não remove
                            novos_ativos.append((n, p, pai_n))
                        elif n.custo_lp < z_inc - 1e-9:
                            novos_ativos.append((n, p, pai_n))
                        else:
                            print(f"Removendo nó {n.id_no} (LB ok): custo_lp={n.custo_lp:.4f} >= z_inc={z_inc:.4f}")

                    ativos = novos_ativos

                if(z_mip==z_lp): #incumbente é igual a fracionaria, logo o nó é inteiro
                    print("PODOU por ser inteiro- fim da linha")
                    no_atual.motivo_poda = no_atual.motivo_poda or "no_inteiro_folha"
                    continue
                nome_arquivo_log = f"log_bounds_{inst.nbcd}_{inst.ninst}.csv"
                with open(nome_arquivo_log, "a", encoding="utf-8") as f:
                    f.write(f"{no_atual.id_no};{z_inc};{z_lp};{z_li};{self.total_colunas}\n")

                print("")

            # -------------------------------------------------
            # caso 2: melhor fracionário -> branching
            # -------------------------------------------------
            print(f"Nó {no_atual.id_no} Valor fracionário com custo {z_lp:.4f}")

            if z_lp < z_frac:
                z_frac = z_lp
                melhor_no_frac = no_atual
                print(f"ATUALIZOU MELHOR FRAC Nó {no_atual.id_no} Valor fracionário com custo {z_lp:.4f}")

            filho_esq, filho_dir, id_no = self.criar_filhos_por_arco(inst, sol_pool, no_atual, id_no)
            # filho_esq, filho_dir, id_no = self.criar_filhos_por_arco075(inst, sol_pool, no_atual, id_no, melhor_no)

            if (filho_esq is not None) and (filho_dir is not None):
                # >>> IMPORTANTE: filhos NÃO herdam custo_lp do pai
                filho_esq.custo_lp = None
                filho_dir.custo_lp = None

                filho_esq.status = "ativo"
                filho_dir.status = "ativo"

                ativos.append((filho_esq, prof + 1, no_atual.id_no))
                ativos.append((filho_dir, prof + 1, no_atual.id_no))
            else:
                no_atual.status = "podado"
                no_atual.motivo_poda = "sem_lambda_fracionario"

            print(f"FIM do nó  {no_atual.id_no} ")

        # =========================
        # Fim
        # =========================
        print("\n==== FIM B&P ====")

        if melhor_no is not None:
            self.total_nos = total_nos_processados
            self.best_obj = float(z_inc)
            sol_pool.custo = float(z_inc)

            #################
            total_colunas = 0
            for k in sol_pool.rotas.keys():
                total_colunas += len(sol_pool.rotas[k]['sequencia_rota'])
            self.total_colunas = total_colunas

            #################
            sol_pool.rotas_escolhidas = {}
            for (k, p), val in melhor_no.lambdas_inteiras.items():
                if val > 0.5:
                    if k not in sol_pool.rotas_escolhidas:
                        sol_pool.rotas_escolhidas[k] = {
                            'sequencias': [],
                            'custos': [],
                            'indices': []
                        }

                    sol_pool.rotas_escolhidas[k]['sequencias'].append(sol_pool.rotas[k]['sequencia_rota'][p])
                    sol_pool.rotas_escolhidas[k]['custos'].append(sol_pool.rotas[k]['custo'][p])
                    sol_pool.rotas_escolhidas[k]['indices'].append(p)
            #######################

            print(f"Melhor solução inteira: nó {melhor_no.id_no} com custo {z_inc:.4f}")
            self.imprimir_lambdas_no(melhor_no, sol_pool)

            dados_inc = {
                "tipo": "inteira",
                "no_id": melhor_no.id_no,
                "custo": float(z_inc),
                "lambdas": {f"{k},{p}": float(v) for (k, p), v in melhor_no.lambdas.items()},
                "rotas_ativas": self.extrair_rotas_do_no(melhor_no, sol_pool),
                "arcos_fixados_em_1": [list(t) for t in sorted(melhor_no.arcos_fixados_em_1)],
                "arcos_proibidos": [list(t) for t in sorted(melhor_no.arcos_proibidos)],
            }
            with open("melhor_inteira.json", "w", encoding="utf-8") as f:
                json.dump(dados_inc, f, ensure_ascii=False, indent=2)
        else:
            print("Nenhuma solução inteira encontrada.")

        if melhor_no_frac is not None:
            print(f"Melhor solução fracionária: nó {melhor_no_frac.id_no} com custo {z_frac:.4f}")
            self.imprimir_lambdas_no(melhor_no_frac, sol_pool)

            dados_frac = {
                "tipo": "fracionaria",
                "no_id": melhor_no_frac.id_no,
                "custo": float(z_frac),
                "lambdas": {f"{k},{p}": float(v) for (k, p), v in melhor_no_frac.lambdas.items()},
                "rotas_ativas": self.extrair_rotas_do_no(melhor_no_frac, sol_pool),
                "arcos_fixados_em_1": [list(t) for t in sorted(melhor_no_frac.arcos_fixados_em_1)],
                "arcos_proibidos": [list(t) for t in sorted(melhor_no_frac.arcos_proibidos)],
            }
            with open("melhor_fracionaria.json", "w", encoding="utf-8") as f:
                json.dump(dados_frac, f, ensure_ascii=False, indent=2)
        else:
            print("Nenhuma solução fracionária registrada (ou todos nós foram inteiros/podados).")

        # se você usa JSON da árvore:
        #self._salvar_log_bp()


    def SUB_PROG_DIN_PW(self, inst, pi, sigma_k, k, NO_BP,
                        arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                        #widening_seq=(1, 2, 4, 8, "ALL"),
                        widening_seq=(4,8,"ALL"),
                        eps=1e-6):
        import math
        from collections import deque

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}  # (i,j) or (i,j,k) -> dual

        # flexible- a ideia é que o algoritmo fixe ou proiba em base das duais, para que
        # assim eu consiga proibir ou fixar o arco de acordo com a dual,
        # #senao nao estarei otimizando nada
        print(f'Subprob ', k)
        arcos_fixados = set()
        arcos_proibidos = set()
        # fim flexible
        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        # print matriz custo reduzido
        #"""
        print("\n=== MATRIZ DE CUSTO REDUZIDO (delta_rc) ===")

        for i in range(nbn):

            linha = []

            for j in range(nbn):

                if i == j:
                    linha.append("   -   ")
                    continue

                if (i, j) in arcos_proibidos:
                    linha.append("  X    ")
                    continue

                # custo base
                rc = travel_time(i, j)

                # dual arco
                rc -= float(mu_arc.get((i, j), 0.0))

                # dual cliente
                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                # dual veiculo (igual sua lógica: só ao fechar)
                if j == depf:
                    rc -= float(sigma_k)

                linha.append(f"{rc:7.2f}")

            print(f"i={i:2d} | " + " ".join(linha))

        print("==========================================\n")
        
        #"""
        # ------------------ FIXOS (FORÇAR) ------------------
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
        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def delta_rc(i, j):
            # incremento de custo reduzido no arco i->j
            val = travel_time(i, j) - mu(i, j)
            if 1 <= j <= nbcd:
                val -= float(pi[j - 1])
            if j == depf:
                val -= float(sigma_k)  # mantém seu esquema: sigma ao fechar
            return val

        # =========================
        # Progressive widening loop
        # =========================
        for B in widening_seq:

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

                # ------------------ candidatos - excluo quem ja foi (esta na mascara esse)

                if no_i in succ_fixo:
                    candidatos = [succ_fixo[no_i]]
                else:
                    candidatos = []
                    for c in range(1, nbcd + 1):
                        if (mask_i & cliente_mask(c)) == 0:
                            candidatos.append(c)
                    candidatos.append(depf)

                # ------------------ filtra viáveis e ranqueia ------------------
                viaveis = []
                for j in candidatos:

                    # print(f'Tamanho Candidatos ',len(candidatos),' j: ',j,' - CANDIDATOS: ',candidatos)
                    ######################################### expansão dos arcos

                    # essa parte retirei, pois o pred e succ fica a cargo da dualidade
                    # proibido
                    if (no_i, j) in arcos_proibidos or (no_i, j, k) in arcos_proibidos:
                        continue

                    # pred fixo
                    if j in pred_fixo and pred_fixo[j] != no_i:
                        continue

                    # bloqueia rota vazia 0->depf
                    if j == depf and mask_i == 0:
                        continue

                    # clientes visitados
                    nova_mask = mask_i
                    if 1 <= j <= nbcd:
                        bit = cliente_mask(j)
                        if (mask_i & bit) != 0:
                            continue
                        nova_mask = mask_i | bit

                    # capacidade
                    nova_carga = carga_i + (d[j] if 1 <= j <= nbcd else 0.0)
                    if nova_carga > cap_k + 1e-9:
                        continue

                    # janela de tempo
                    tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                    if tempo_chegada < a[j]:
                        tempo_chegada = a[j]
                    if tempo_chegada > b[j] + 1e-9:
                        continue

                    # TABU - se estiver em tabu nao passa
                    if NO_BP.tabu_until[k][no_i][j] > 0:
                        # rint(f'tabu bloqueou  expansao',k,'-',no_i,'-',j,'- id NO= ',NO_BP.id_no)
                        continue

                    # se a rota\ arco sobreviveu até aqui, é pq é viavel
                    viaveis.append((j, tempo_chegada, nova_carga, nova_mask))

                if not viaveis:
                    continue

                # ordena por melhor incremento de custo reduzido
                viaveis.sort(key=lambda tpl: delta_rc(no_i, tpl[0]))

                # Top-B
                if B == "ALL":
                    top = viaveis
                else:
                    top = viaveis[:min(int(B), len(viaveis))]

                for (j, tempo_chegada, nova_carga, nova_mask) in top:

                    custo_mod_novo = custo_mod_i + delta_rc(no_i, j)

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

                    # early exit ao fechar no depósito final
                    if j == depf and custo_mod_novo < -eps:

                        rota_reversa = []
                        idx_tmp = idx_novo
                        while idx_tmp is not None:
                            rota_reversa.append(rotulos[idx_tmp]["no"])
                            idx_tmp = rotulos[idx_tmp]["pai"]
                        rota = list(reversed(rota_reversa))

                        custo_real = 0.0
                        for t in range(len(rota) - 1):
                            custo_real += travel_time(rota[t], rota[t + 1])

                        bin_xij = [0 for _ in range(nbcd)]
                        for v in rota:
                            if 1 <= v <= nbcd:
                                bin_xij[v - 1] = 1

                        return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, custo_mod_novo

            # pós (se achou a melhor no final)
            if melhor_indice is not None and melhor_custo_reduzido < -eps:

                rota_reversa = []
                idx = melhor_indice
                while idx is not None:
                    rota_reversa.append(rotulos[idx]["no"])
                    idx = rotulos[idx]["pai"]
                rota = list(reversed(rota_reversa))

                custo_real = 0.0
                for t in range(len(rota) - 1):
                    custo_real += travel_time(rota[t], rota[t + 1])

                bin_xij = [0 for _ in range(nbcd)]
                for v in rota:
                    if 1 <= v <= nbcd:
                        bin_xij[v - 1] = 1

                return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, melhor_custo_reduzido

        return None, None

    def SUB_PROG_DIN_BIDIRECIONAL_MICHEL(self, inst, pi, sigma_k, k, NO_BP,
                                         arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                                         max_labels_por_no=100,
                                         usar_poda_por_no=True,
                                         usar_bound_tempo=True,
                                         frac_tempo_critico=0.5,
                                         modo="heur",  # "heur" ou "exato"
                                         eps=1e-6):
        import math
        from collections import deque, defaultdict

        print(f"Subprob BIDIRECIONAL MICHEL veículo {k} | modo={modo}")

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(float(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0))

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)
        tol = 1e-6

        horizonte = b[depf] - a[dep0]
        limite_meia_busca = frac_tempo_critico * horizonte

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def delta_rc(i, j):
            val = travel_time(i, j) - mu(i, j)
            if 1 <= j <= nbcd:
                val -= float(pi[j - 1])
            if j == depf:
                val -= float(sigma_k)
            return val

        def domina_heur(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        def domina_exata(maskA, cA, tA, qA, maskB, cB, tB, qB):
            if maskA != maskB:
                return False
            return domina_heur(cA, tA, qA, cB, tB, qB)

        def domina_label(maskA, cA, tA, qA, maskB, cB, tB, qB):
            if modo == "heur":
                return domina_heur(cA, tA, qA, cB, tB, qB)
            return domina_exata(maskA, cA, tA, qA, maskB, cB, tB, qB)

        def chave_fronteira(no, mask):
            if modo == "heur":
                return no
            return (no, mask)

        def rota_forward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            seq.reverse()
            return seq

        def rota_backward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            return seq

        def avaliar_rota(rota):
            if not rota:
                return None, None

            if rota[0] != dep0 or rota[-1] != depf:
                return None, None

            visitados = set()
            tempo = max(a[dep0], 0.0)
            carga = 0.0
            custo_real = 0.0
            custo_red = 0.0

            for t_idx in range(len(rota) - 1):
                i = rota[t_idx]
                j = rota[t_idx + 1]

                if i == j:
                    return None, None

                if (i, j) in arcos_proibidos or (i, j, k) in arcos_proibidos:
                    return None, None

                if NO_BP.tabu_until[k][i][j] > 0:
                    return None, None

                tempo = tempo + s[i] + travel_time(i, j)
                if tempo < a[j]:
                    tempo = a[j]
                if tempo > b[j] + 1e-9:
                    return None, None

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return None, None
                    visitados.add(j)
                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return None, None

                custo_real += travel_time(i, j)
                custo_red += delta_rc(i, j)

            if len(visitados) == 0:
                return None, None

            bin_xij = [0 for _ in range(nbcd)]
            for v in visitados:
                bin_xij[v - 1] = 1

            return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, custo_red

        # =========================
        # FORWARD
        # =========================
        rot_f = []
        abertos_f = deque()
        labels_f_por_no = defaultdict(list)
        fronteira_f = defaultdict(list)

        rot_f.append({
            "no": dep0,
            "tempo": max(a[dep0], 0.0),
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_f.append(0)
        labels_f_por_no[dep0].append(0)
        fronteira_f[chave_fronteira(dep0, 0)].append(0)

        while abertos_f:
            idx_atual = abertos_f.popleft()
            r = rot_f[idx_atual]

            if not r["ativo"]:
                continue

            no_i = r["no"]
            tempo_i = r["tempo"]
            carga_i = r["carga"]
            custo_i = r["custo_mod"]
            mask_i = r["mask"]
            nvisit_i = r["nvisit"]

            candidatos = [j for j in range(1, nbcd + 1) if (mask_i & cliente_mask(j)) == 0]

            viaveis = []
            for j in candidatos:
                if (no_i, j) in arcos_proibidos or (no_i, j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][j] > 0:
                    continue

                bit = cliente_mask(j)
                if (mask_i & bit) != 0:
                    continue

                nova_mask = mask_i | bit
                nova_carga = carga_i + d[j]
                if nova_carga > cap_k + 1e-9:
                    continue

                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j] + 1e-9:
                    continue

                if usar_bound_tempo and tempo_chegada > limite_meia_busca + 1e-9:
                    continue

                viaveis.append((j, tempo_chegada, nova_carga, nova_mask))

            viaveis.sort(key=lambda tpl: (delta_rc(no_i, tpl[0]), tpl[1], tpl[2]))

            for (j, tempo_chegada, nova_carga, nova_mask) in viaveis:
                custo_novo = custo_i + delta_rc(no_i, j)
                chave = chave_fronteira(j, nova_mask)
                lista = fronteira_f.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina_label(ro["mask"], ro["custo_mod"], ro["tempo"], ro["carga"],
                                    nova_mask, custo_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina_label(nova_mask, custo_novo, tempo_chegada, nova_carga,
                                    ro["mask"], ro["custo_mod"], ro["tempo"], ro["carga"]):
                        rot_f[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_f)
                rot_f.append({
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_i + 1
                })
                abertos_f.append(idx_novo)
                labels_f_por_no[j].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_f[chave] = nova_lista

            if usar_poda_por_no:
                lista_no = [idx for idx in labels_f_por_no[no_i] if rot_f[idx]["ativo"]]
                if len(lista_no) > max_labels_por_no:
                    lista_no.sort(key=lambda idx: (
                        rot_f[idx]["custo_mod"],
                        rot_f[idx]["tempo"],
                        rot_f[idx]["carga"]
                    ))
                    manter = set(lista_no[:max_labels_por_no])
                    for idx in lista_no[max_labels_por_no:]:
                        rot_f[idx]["ativo"] = False
                    labels_f_por_no[no_i] = [idx for idx in labels_f_por_no[no_i] if idx in manter]

        # =========================
        # BACKWARD
        # =========================
        rot_b = []
        abertos_b = deque()
        labels_b_por_no = defaultdict(list)
        fronteira_b = defaultdict(list)

        rot_b.append({
            "no": depf,
            "tempo_back": 0.0,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_b.append(0)
        labels_b_por_no[depf].append(0)
        fronteira_b[chave_fronteira(depf, 0)].append(0)

        while abertos_b:
            idx_atual = abertos_b.popleft()
            r = rot_b[idx_atual]

            if not r["ativo"]:
                continue

            no_j = r["no"]
            tempo_back_j = r["tempo_back"]
            carga_j = r["carga"]
            custo_j = r["custo_mod"]
            mask_j = r["mask"]
            nvisit_j = r["nvisit"]

            candidatos = [i for i in range(1, nbcd + 1) if (mask_j & cliente_mask(i)) == 0]

            viaveis = []
            for i in candidatos:
                if (i, no_j) in arcos_proibidos or (i, no_j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][i][no_j] > 0:
                    continue

                bit = cliente_mask(i)
                if (mask_j & bit) != 0:
                    continue

                nova_mask = mask_j | bit
                nova_carga = carga_j + d[i]
                if nova_carga > cap_k + 1e-9:
                    continue

                novo_tempo_back = tempo_back_j + s[i] + travel_time(i, no_j)

                # base backward da tese: 50% do recurso crítico em cada direção
                if usar_bound_tempo and novo_tempo_back > limite_meia_busca + 1e-9:
                    continue

                custo_novo = custo_j + delta_rc(i, no_j)
                viaveis.append((i, novo_tempo_back, nova_carga, nova_mask, custo_novo))

            viaveis.sort(key=lambda tpl: (tpl[4], tpl[1], tpl[2]))

            for (i, novo_tempo_back, nova_carga, nova_mask, custo_novo) in viaveis:
                chave = chave_fronteira(i, nova_mask)
                lista = fronteira_b.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina_label(ro["mask"], ro["custo_mod"], ro["tempo_back"], ro["carga"],
                                    nova_mask, custo_novo, novo_tempo_back, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina_label(nova_mask, custo_novo, novo_tempo_back, nova_carga,
                                    ro["mask"], ro["custo_mod"], ro["tempo_back"], ro["carga"]):
                        rot_b[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_b)
                rot_b.append({
                    "no": i,
                    "tempo_back": novo_tempo_back,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_j + 1
                })
                abertos_b.append(idx_novo)
                labels_b_por_no[i].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_b[chave] = nova_lista

            if usar_poda_por_no:
                lista_no = [idx for idx in labels_b_por_no[no_j] if rot_b[idx]["ativo"]]
                if len(lista_no) > max_labels_por_no:
                    lista_no.sort(key=lambda idx: (
                        rot_b[idx]["custo_mod"],
                        rot_b[idx]["tempo_back"],
                        rot_b[idx]["carga"]
                    ))
                    manter = set(lista_no[:max_labels_por_no])
                    for idx in lista_no[max_labels_por_no:]:
                        rot_b[idx]["ativo"] = False
                    labels_b_por_no[no_j] = [idx for idx in labels_b_por_no[no_j] if idx in manter]

        # =========================
        # COMBINAÇÃO FORWARD/BACKWARD
        # =========================
        melhor_coluna = None
        melhor_rc = math.inf

        nos_encontro = set(labels_f_por_no.keys()).intersection(set(labels_b_por_no.keys()))
        nos_encontro = [m for m in nos_encontro if 1 <= m <= nbcd]

        for m in nos_encontro:
            lista_f = [idx for idx in labels_f_por_no[m] if rot_f[idx]["ativo"]]
            lista_b = [idx for idx in labels_b_por_no[m] if rot_b[idx]["ativo"]]

            for idx_f in lista_f:
                rf = rot_f[idx_f]
                rota_f = rota_forward(rot_f, idx_f)  # 0 -> ... -> m

                for idx_b in lista_b:
                    rb = rot_b[idx_b]
                    rota_b = rota_backward(rot_b, idx_b)  # m -> ... -> depf

                    mask_f = rf["mask"]
                    mask_b = rb["mask"]

                    # só o nó de encontro pode repetir
                    if (mask_f & mask_b) != cliente_mask(m):
                        continue

                    rota_completa = rota_f[:-1] + rota_b

                    coluna, rc = avaliar_rota(rota_completa)
                    if coluna is None:
                        continue

                    if rc < melhor_rc:
                        melhor_rc = rc
                        melhor_coluna = coluna

        # =========================
        # FECHAMENTO DIRETO FORWARD
        # =========================
        for no_i, lista_idx in labels_f_por_no.items():
            if no_i == depf:
                continue

            for idx in lista_idx:
                r = rot_f[idx]
                if not r["ativo"]:
                    continue

                if (no_i, depf) in arcos_proibidos or (no_i, depf, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][depf] > 0:
                    continue

                rota_f = rota_forward(rot_f, idx)
                rota = rota_f + [depf]
                coluna, rc = avaliar_rota(rota)
                if coluna is None:
                    continue

                if rc < melhor_rc:
                    melhor_rc = rc
                    melhor_coluna = coluna

        if melhor_coluna is not None and melhor_rc < -eps:
            return melhor_coluna, melhor_rc

        return None, None

    def SUB_PROG_DIN_BIDIRECIONAL_DEPTH(self, inst, pi, sigma_k, k, NO_BP,
                                        arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                                        max_labels_por_no=100,
                                        max_depth=None,
                                        usar_poda_por_no=True,
                                        usar_poda_profundidade=True,
                                        eps=1e-6):
        import math
        from collections import deque, defaultdict

        print(f"Subprob BIDIRECIONAL veículo {k}")

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        if max_depth is None:
            max_depth = math.ceil(nbcd / 2)

        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)
        tol = 1e-6

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def delta_rc(i, j):
            val = travel_time(i, j) - mu(i, j)
            if 1 <= j <= nbcd:
                val -= float(pi[j - 1])
            if j == depf:
                val -= float(sigma_k)
            return val

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        def rota_forward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            seq.reverse()
            return seq

        def rota_backward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            return seq

        def avaliar_rota(rota):
            if not rota:
                return None, None

            if rota[0] != dep0 or rota[-1] != depf:
                return None, None

            visitados = set()
            tempo = max(a[dep0], 0.0)
            carga = 0.0
            custo_real = 0.0
            custo_red = 0.0

            for t_idx in range(len(rota) - 1):
                i = rota[t_idx]
                j = rota[t_idx + 1]

                if i == j:
                    return None, None

                if (i, j) in arcos_proibidos or (i, j, k) in arcos_proibidos:
                    return None, None

                if NO_BP.tabu_until[k][i][j] > 0:
                    return None, None

                tempo = tempo + s[i] + travel_time(i, j)
                if tempo < a[j]:
                    tempo = a[j]
                if tempo > b[j] + 1e-9:
                    return None, None

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return None, None
                    visitados.add(j)
                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return None, None

                custo_real += travel_time(i, j)
                custo_red += delta_rc(i, j)

            if len(visitados) == 0:
                return None, None

            bin_xij = [0 for _ in range(nbcd)]
            for v in visitados:
                bin_xij[v - 1] = 1

            return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, custo_red

        # =========================
        # GERAÇÃO FORWARD
        # =========================
        rot_f = []
        abertos_f = deque()
        labels_f_por_no = defaultdict(list)
        fronteira_f = defaultdict(list)

        idx0 = 0
        rot_f.append({
            "no": dep0,
            "tempo": max(a[dep0], 0.0),
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_f.append(idx0)
        labels_f_por_no[dep0].append(idx0)
        fronteira_f[(dep0, 0)].append(idx0)

        while abertos_f:
            idx_atual = abertos_f.popleft()
            r = rot_f[idx_atual]

            if not r["ativo"]:
                continue

            no_i = r["no"]
            tempo_i = r["tempo"]
            carga_i = r["carga"]
            custo_i = r["custo_mod"]
            mask_i = r["mask"]
            nvisit_i = r["nvisit"]

            if usar_poda_profundidade and nvisit_i >= max_depth:
                continue

            candidatos = []
            for j in range(1, nbcd + 1):
                if (mask_i & cliente_mask(j)) == 0:
                    candidatos.append(j)

            viaveis = []
            for j in candidatos:
                if (no_i, j) in arcos_proibidos or (no_i, j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][j] > 0:
                    continue

                bit = cliente_mask(j)
                if (mask_i & bit) != 0:
                    continue

                nova_mask = mask_i | bit
                nova_carga = carga_i + d[j]
                if nova_carga > cap_k + 1e-9:
                    continue

                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j] + 1e-9:
                    continue

                viaveis.append((j, tempo_chegada, nova_carga, nova_mask))

            viaveis.sort(key=lambda tpl: delta_rc(no_i, tpl[0]))

            for (j, tempo_chegada, nova_carga, nova_mask) in viaveis:
                custo_novo = custo_i + delta_rc(no_i, j)
                chave = (j, nova_mask)
                lista = fronteira_f.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo"], ro["carga"],
                              custo_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, tempo_chegada, nova_carga,
                              ro["custo_mod"], ro["tempo"], ro["carga"]):
                        rot_f[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_f)
                rot_f.append({
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_i + 1
                })
                abertos_f.append(idx_novo)
                labels_f_por_no[j].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_f[chave] = nova_lista

            if usar_poda_por_no:
                lista_no = [idx for idx in labels_f_por_no[no_i] if rot_f[idx]["ativo"]]
                if len(lista_no) > max_labels_por_no:
                    lista_no.sort(key=lambda idx: (
                        rot_f[idx]["custo_mod"],
                        rot_f[idx]["tempo"],
                        rot_f[idx]["carga"]
                    ))
                    manter = set(lista_no[:max_labels_por_no])
                    for idx in lista_no[max_labels_por_no:]:
                        rot_f[idx]["ativo"] = False
                    labels_f_por_no[no_i] = [idx for idx in labels_f_por_no[no_i] if idx in manter]

        # =========================
        # GERAÇÃO BACKWARD
        # =========================
        rot_b = []
        abertos_b = deque()
        labels_b_por_no = defaultdict(list)
        fronteira_b = defaultdict(list)

        idx0b = 0
        rot_b.append({
            "no": depf,
            "tempo_back": 0.0,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_b.append(idx0b)
        labels_b_por_no[depf].append(idx0b)
        fronteira_b[(depf, 0)].append(idx0b)

        while abertos_b:
            idx_atual = abertos_b.popleft()
            r = rot_b[idx_atual]

            if not r["ativo"]:
                continue

            no_j = r["no"]
            tempo_back_j = r["tempo_back"]
            carga_j = r["carga"]
            custo_j = r["custo_mod"]
            mask_j = r["mask"]
            nvisit_j = r["nvisit"]

            if usar_poda_profundidade and nvisit_j >= max_depth:
                continue

            candidatos = []
            for i in range(1, nbcd + 1):
                if (mask_j & cliente_mask(i)) == 0:
                    candidatos.append(i)

            viaveis = []
            for i in candidatos:
                if (i, no_j) in arcos_proibidos or (i, no_j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][i][no_j] > 0:
                    continue

                bit = cliente_mask(i)
                if (mask_j & bit) != 0:
                    continue

                nova_mask = mask_j | bit
                nova_carga = carga_j + d[i]
                if nova_carga > cap_k + 1e-9:
                    continue

                novo_tempo_back = tempo_back_j + s[i] + travel_time(i, no_j)
                custo_novo = custo_j + delta_rc(i, no_j)
                viaveis.append((i, novo_tempo_back, nova_carga, nova_mask, custo_novo))

            viaveis.sort(key=lambda tpl: tpl[4])

            for (i, novo_tempo_back, nova_carga, nova_mask, custo_novo) in viaveis:
                chave = (i, nova_mask)
                lista = fronteira_b.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo_back"], ro["carga"],
                              custo_novo, novo_tempo_back, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, novo_tempo_back, nova_carga,
                              ro["custo_mod"], ro["tempo_back"], ro["carga"]):
                        rot_b[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_b)
                rot_b.append({
                    "no": i,
                    "tempo_back": novo_tempo_back,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_j + 1
                })
                abertos_b.append(idx_novo)
                labels_b_por_no[i].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_b[chave] = nova_lista

            if usar_poda_por_no:
                lista_no = [idx for idx in labels_b_por_no[no_j] if rot_b[idx]["ativo"]]
                if len(lista_no) > max_labels_por_no:
                    lista_no.sort(key=lambda idx: (
                        rot_b[idx]["custo_mod"],
                        rot_b[idx]["tempo_back"],
                        rot_b[idx]["carga"]
                    ))
                    manter = set(lista_no[:max_labels_por_no])
                    for idx in lista_no[max_labels_por_no:]:
                        rot_b[idx]["ativo"] = False
                    labels_b_por_no[no_j] = [idx for idx in labels_b_por_no[no_j] if idx in manter]

        # =========================
        # COMBINAÇÃO
        # =========================
        melhor_coluna = None
        melhor_rc = math.inf

        nos_encontro = set(labels_f_por_no.keys()).intersection(set(labels_b_por_no.keys()))
        nos_encontro = [m for m in nos_encontro if 1 <= m <= nbcd]

        for m in nos_encontro:
            lista_f = [idx for idx in labels_f_por_no[m] if rot_f[idx]["ativo"]]
            lista_b = [idx for idx in labels_b_por_no[m] if rot_b[idx]["ativo"]]

            for idx_f in lista_f:
                rf = rot_f[idx_f]
                rota_f = rota_forward(rot_f, idx_f)

                for idx_b in lista_b:
                    rb = rot_b[idx_b]
                    rota_b = rota_backward(rot_b, idx_b)

                    mask_f = rf["mask"]
                    mask_b = rb["mask"]

                    inter = mask_f & mask_b
                    if inter != cliente_mask(m):
                        continue

                    rota_completa = rota_f[:-1] + rota_b

                    coluna, rc = avaliar_rota(rota_completa)
                    if coluna is None:
                        continue

                    if rc < melhor_rc:
                        melhor_rc = rc
                        melhor_coluna = coluna

        # =========================
        # FECHAMENTO DIRETO FORWARD
        # =========================
        for no_i, lista_idx in labels_f_por_no.items():
            if no_i == depf:
                continue

            for idx in lista_idx:
                r = rot_f[idx]
                if not r["ativo"]:
                    continue

                if (no_i, depf) in arcos_proibidos or (no_i, depf, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][depf] > 0:
                    continue

                rota_f = rota_forward(rot_f, idx)
                rota = rota_f + [depf]
                coluna, rc = avaliar_rota(rota)
                if coluna is None:
                    continue

                if rc < melhor_rc:
                    melhor_rc = rc
                    melhor_coluna = coluna

        if melhor_coluna is not None and melhor_rc < -eps:
            return melhor_coluna, melhor_rc

        return None, None

    def SUB_PROG_DIN_BIDIRECIONAL(self, inst, pi, sigma_k, k, NO_BP,
                                  arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                                  max_labels_por_no=100,
                                  max_depth=None,
                                  eps=1e-6):
        import math
        from collections import deque, defaultdict

        print(f"Subprob BIDIRECIONAL veículo {k}")

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        if max_depth is None:
            max_depth = math.ceil(nbcd / 2)

        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)
        tol = 1e-6

        proibidos_k = set()
        fixados_k = set()

        for arc in arcos_proibidos:
            if len(arc) == 2:
                proibidos_k.add(arc)
            elif len(arc) == 3 and arc[2] == k:
                proibidos_k.add((arc[0], arc[1]))

        for arc in arcos_fixados:
            if len(arc) == 2:
                fixados_k.add(arc)
            elif len(arc) == 3 and arc[2] == k:
                fixados_k.add((arc[0], arc[1]))

        if hasattr(NO_BP, "arcos_proibidos"):
            for (i, j, kk) in NO_BP.arcos_proibidos:
                if kk == k:
                    proibidos_k.add((i, j))

        if hasattr(NO_BP, "arcos_fixados_em_1"):
            for (i, j, kk) in NO_BP.arcos_fixados_em_1:
                if kk == k:
                    fixados_k.add((i, j))

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None
            succ_fixo[i] = j
            pred_fixo[j] = i

        def arco_proibido(i, j):
            return (i, j) in proibidos_k

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False
            return True

        def todos_fixados_na_rota(rota):
            aset = {(rota[t], rota[t + 1]) for t in range(len(rota) - 1)}
            for arc in fixados_k:
                if arc not in aset:
                    return False
            return True

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def delta_rc(i, j):
            val = travel_time(i, j) - mu(i, j)
            if 1 <= j <= nbcd:
                val -= float(pi[j - 1])
            if j == depf:
                val -= float(sigma_k)
            return val

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        def rota_forward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            seq.reverse()
            return seq

        def rota_backward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            return seq

        def avaliar_rota(rota):
            if not rota:
                return None, None

            if rota[0] != dep0 or rota[-1] != depf:
                return None, None

            visitados = set()
            tempo = max(a[dep0], 0.0)
            carga = 0.0
            custo_real = 0.0
            custo_red = 0.0

            for t_idx in range(len(rota) - 1):
                i = rota[t_idx]
                j = rota[t_idx + 1]

                if i == j:
                    return None, None

                if not arco_permitido(i, j):
                    return None, None

                if NO_BP.tabu_until[k][i][j] > 0:
                    return None, None

                tempo = tempo + s[i] + travel_time(i, j)
                if tempo < a[j]:
                    tempo = a[j]
                if tempo > b[j] + 1e-9:
                    return None, None

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return None, None
                    visitados.add(j)
                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return None, None

                custo_real += travel_time(i, j)
                custo_red += delta_rc(i, j)

            if len(visitados) == 0:
                return None, None

            if len(fixados_k) > 0 and not todos_fixados_na_rota(rota):
                return None, None

            bin_xij = [0 for _ in range(nbcd)]
            for v in visitados:
                bin_xij[v - 1] = 1

            return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, custo_red

        # =========================
        # GERAÇÃO FORWARD
        # =========================
        rot_f = []
        abertos_f = deque()
        labels_f_por_no = defaultdict(list)
        fronteira_f = defaultdict(list)

        idx0 = 0
        rot_f.append({
            "no": dep0,
            "tempo": max(a[dep0], 0.0),
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })

        abertos_f.append(idx0)
        labels_f_por_no[dep0].append(idx0)
        fronteira_f[(dep0, 0)].append(idx0)

        while abertos_f:
            idx_atual = abertos_f.popleft()
            r = rot_f[idx_atual]

            if not r["ativo"]:
                continue

            no_i = r["no"]
            tempo_i = r["tempo"]
            carga_i = r["carga"]
            custo_i = r["custo_mod"]
            mask_i = r["mask"]
            nvisit_i = r["nvisit"]

            if nvisit_i >= max_depth:
                continue

            candidatos = []
            for j in range(1, nbcd + 1):
                if (mask_i & cliente_mask(j)) == 0:
                    candidatos.append(j)

            viaveis = []
            for j in candidatos:
                if arco_proibido(no_i, j):
                    continue

                if not arco_permitido(no_i, j):
                    continue

                if NO_BP.tabu_until[k][no_i][j] > 0:
                    continue

                bit = cliente_mask(j)
                if (mask_i & bit) != 0:
                    continue

                nova_mask = mask_i | bit
                nova_carga = carga_i + d[j]
                if nova_carga > cap_k + 1e-9:
                    continue

                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j] + 1e-9:
                    continue

                viaveis.append((j, tempo_chegada, nova_carga, nova_mask))

            viaveis.sort(key=lambda tpl: delta_rc(no_i, tpl[0]))

            for (j, tempo_chegada, nova_carga, nova_mask) in viaveis:
                custo_novo = custo_i + delta_rc(no_i, j)
                chave = (j, nova_mask)
                lista = fronteira_f.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo"], ro["carga"],
                              custo_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, tempo_chegada, nova_carga,
                              ro["custo_mod"], ro["tempo"], ro["carga"]):
                        rot_f[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_f)
                rot_f.append({
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_i + 1
                })
                abertos_f.append(idx_novo)
                labels_f_por_no[j].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_f[chave] = nova_lista

            lista_no = [idx for idx in labels_f_por_no[no_i] if rot_f[idx]["ativo"]]
            if len(lista_no) > max_labels_por_no:
                lista_no.sort(key=lambda idx: (rot_f[idx]["custo_mod"], rot_f[idx]["tempo"], rot_f[idx]["carga"]))
                manter = set(lista_no[:max_labels_por_no])
                for idx in lista_no[max_labels_por_no:]:
                    rot_f[idx]["ativo"] = False
                labels_f_por_no[no_i] = [idx for idx in labels_f_por_no[no_i] if idx in manter]

        # =========================
        # GERAÇÃO BACKWARD
        # =========================
        rot_b = []
        abertos_b = deque()
        labels_b_por_no = defaultdict(list)
        fronteira_b = defaultdict(list)

        idx0b = 0
        rot_b.append({
            "no": depf,
            "tempo_back": 0.0,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_b.append(idx0b)
        labels_b_por_no[depf].append(idx0b)
        fronteira_b[(depf, 0)].append(idx0b)

        while abertos_b:
            idx_atual = abertos_b.popleft()
            r = rot_b[idx_atual]

            if not r["ativo"]:
                continue

            no_j = r["no"]
            tempo_back_j = r["tempo_back"]
            carga_j = r["carga"]
            custo_j = r["custo_mod"]
            mask_j = r["mask"]
            nvisit_j = r["nvisit"]

            if nvisit_j >= max_depth:
                continue

            candidatos = []
            for i in range(1, nbcd + 1):
                if (mask_j & cliente_mask(i)) == 0:
                    candidatos.append(i)

            viaveis = []
            for i in candidatos:
                if arco_proibido(i, no_j):
                    continue

                if not arco_permitido(i, no_j):
                    continue

                if NO_BP.tabu_until[k][i][no_j] > 0:
                    continue

                bit = cliente_mask(i)
                if (mask_j & bit) != 0:
                    continue

                nova_mask = mask_j | bit
                nova_carga = carga_j + d[i]
                if nova_carga > cap_k + 1e-9:
                    continue

                novo_tempo_back = tempo_back_j + s[i] + travel_time(i, no_j)
                custo_novo = custo_j + delta_rc(i, no_j)
                viaveis.append((i, novo_tempo_back, nova_carga, nova_mask, custo_novo))

            viaveis.sort(key=lambda tpl: tpl[4])

            for (i, novo_tempo_back, nova_carga, nova_mask, custo_novo) in viaveis:
                chave = (i, nova_mask)
                lista = fronteira_b.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo_back"], ro["carga"],
                              custo_novo, novo_tempo_back, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, novo_tempo_back, nova_carga,
                              ro["custo_mod"], ro["tempo_back"], ro["carga"]):
                        rot_b[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_b)
                rot_b.append({
                    "no": i,
                    "tempo_back": novo_tempo_back,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_j + 1
                })
                abertos_b.append(idx_novo)
                labels_b_por_no[i].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_b[chave] = nova_lista

            lista_no = [idx for idx in labels_b_por_no[no_j] if rot_b[idx]["ativo"]]
            if len(lista_no) > max_labels_por_no:
                lista_no.sort(key=lambda idx: (rot_b[idx]["custo_mod"], rot_b[idx]["tempo_back"], rot_b[idx]["carga"]))
                manter = set(lista_no[:max_labels_por_no])
                for idx in lista_no[max_labels_por_no:]:
                    rot_b[idx]["ativo"] = False
                labels_b_por_no[no_j] = [idx for idx in labels_b_por_no[no_j] if idx in manter]

        # =========================
        # COMBINAÇÃO
        # =========================
        melhor_coluna = None
        melhor_rc = math.inf

        nos_encontro = set(labels_f_por_no.keys()).intersection(set(labels_b_por_no.keys()))
        nos_encontro = [m for m in nos_encontro if 1 <= m <= nbcd]

        for m in nos_encontro:
            lista_f = [idx for idx in labels_f_por_no[m] if rot_f[idx]["ativo"]]
            lista_b = [idx for idx in labels_b_por_no[m] if rot_b[idx]["ativo"]]

            for idx_f in lista_f:
                rf = rot_f[idx_f]
                rota_f = rota_forward(rot_f, idx_f)

                for idx_b in lista_b:
                    rb = rot_b[idx_b]
                    rota_b = rota_backward(rot_b, idx_b)

                    mask_f = rf["mask"]
                    mask_b = rb["mask"]

                    inter = mask_f & mask_b
                    if inter != cliente_mask(m):
                        continue

                    rota_completa = rota_f[:-1] + rota_b

                    coluna, rc = avaliar_rota(rota_completa)
                    if coluna is None:
                        continue

                    if rc < melhor_rc:
                        melhor_rc = rc
                        melhor_coluna = coluna

        # =========================
        # FECHAMENTO DIRETO FORWARD
        # =========================
        for no_i, lista_idx in labels_f_por_no.items():
            if no_i == depf:
                continue

            for idx in lista_idx:
                r = rot_f[idx]
                if not r["ativo"]:
                    continue

                if arco_proibido(no_i, depf):
                    continue

                if not arco_permitido(no_i, depf):
                    continue

                if NO_BP.tabu_until[k][no_i][depf] > 0:
                    continue

                rota_f = rota_forward(rot_f, idx)
                rota = rota_f + [depf]
                coluna, rc = avaliar_rota(rota)
                if coluna is None:
                    continue

                if rc < melhor_rc:
                    melhor_rc = rc
                    melhor_coluna = coluna

        if melhor_coluna is not None and melhor_rc < -eps:
            return melhor_coluna, melhor_rc

        return None, None

    def SUB_PROG_DIN_BIDIRECIONALSemFixos(self, inst, pi, sigma_k, k, NO_BP,
                                  arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                                  max_labels_por_no=100,
                                  max_depth=None,
                                  eps=1e-6):
        import math
        from collections import deque, defaultdict

        print(f"Subprob BIDIRECIONAL veículo {k}")

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        if max_depth is None:
            max_depth = math.ceil(nbcd / 2)

        a, b, s, d = [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d.append(noh.DEMAND if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)
        tol = 1e-6

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def delta_rc(i, j):
            val = travel_time(i, j) - mu(i, j)
            if 1 <= j <= nbcd:
                val -= float(pi[j - 1])
            if j == depf:
                val -= float(sigma_k)
            return val

        def domina(cA, tA, qA, cB, tB, qB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    qA <= qB + tol and
                    (cA < cB - tol or tA < tB - tol or qA < qB - tol)
            )

        def rota_forward(rotulos, idx):
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            seq.reverse()
            return seq

        def rota_backward(rotulos, idx):
            # backward foi construído a partir do depósito final
            # ao reconstruir, sai algo como [m, ..., depf]
            seq = []
            while idx is not None:
                seq.append(rotulos[idx]["no"])
                idx = rotulos[idx]["pai"]
            return seq

        def avaliar_rota(rota):
            if not rota:
                return None, None

            if rota[0] != dep0 or rota[-1] != depf:
                return None, None

            visitados = set()
            tempo = max(a[dep0], 0.0)
            carga = 0.0
            custo_real = 0.0
            custo_red = 0.0

            for t_idx in range(len(rota) - 1):
                i = rota[t_idx]
                j = rota[t_idx + 1]

                if i == j:
                    return None, None

                if (i, j) in arcos_proibidos or (i, j, k) in arcos_proibidos:
                    return None, None

                if NO_BP.tabu_until[k][i][j] > 0:
                    return None, None

                tempo = tempo + s[i] + travel_time(i, j)
                if tempo < a[j]:
                    tempo = a[j]
                if tempo > b[j] + 1e-9:
                    return None, None

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return None, None
                    visitados.add(j)
                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return None, None

                custo_real += travel_time(i, j)
                custo_red += delta_rc(i, j)

            if len(visitados) == 0:
                return None, None

            bin_xij = [0 for _ in range(nbcd)]
            for v in visitados:
                bin_xij[v - 1] = 1

            return {"clientes": rota, "custo": custo_real, "bin_xij": bin_xij}, custo_red

        # =========================
        # GERAÇÃO FORWARD
        # =========================
        rot_f = []
        abertos_f = deque()
        labels_f_por_no = defaultdict(list)
        fronteira_f = defaultdict(list)

        idx0 = 0
        rot_f.append({
            "no": dep0,
            "tempo": max(a[dep0], 0.0),
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        """
        """
        abertos_f.append(idx0)
        labels_f_por_no[dep0].append(idx0)
        fronteira_f[(dep0, 0)].append(idx0)

        while abertos_f:
            idx_atual = abertos_f.popleft()
            r = rot_f[idx_atual]

            if not r["ativo"]:
                continue

            no_i = r["no"]
            tempo_i = r["tempo"]
            carga_i = r["carga"]
            custo_i = r["custo_mod"]
            mask_i = r["mask"]
            nvisit_i = r["nvisit"]

            if nvisit_i >= max_depth:
                continue

            candidatos = []
            for j in range(1, nbcd + 1):
                if (mask_i & cliente_mask(j)) == 0:
                    candidatos.append(j)

            viaveis = []
            for j in candidatos:
                if (no_i, j) in arcos_proibidos or (no_i, j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][j] > 0:
                    continue

                bit = cliente_mask(j)
                if (mask_i & bit) != 0:
                    continue

                nova_mask = mask_i | bit
                nova_carga = carga_i + d[j]
                if nova_carga > cap_k + 1e-9:
                    continue

                tempo_chegada = tempo_i + s[no_i] + travel_time(no_i, j)
                if tempo_chegada < a[j]:
                    tempo_chegada = a[j]
                if tempo_chegada > b[j] + 1e-9:
                    continue

                viaveis.append((j, tempo_chegada, nova_carga, nova_mask))

            viaveis.sort(key=lambda tpl: delta_rc(no_i, tpl[0]))

            for (j, tempo_chegada, nova_carga, nova_mask) in viaveis:
                custo_novo = custo_i + delta_rc(no_i, j)
                chave = (j, nova_mask)
                lista = fronteira_f.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo"], ro["carga"],
                              custo_novo, tempo_chegada, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_f[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, tempo_chegada, nova_carga,
                              ro["custo_mod"], ro["tempo"], ro["carga"]):
                        rot_f[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_f)
                rot_f.append({
                    "no": j,
                    "tempo": tempo_chegada,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_i + 1
                })
                abertos_f.append(idx_novo)
                labels_f_por_no[j].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_f[chave] = nova_lista

            # poda por nó
            lista_no = [idx for idx in labels_f_por_no[no_i] if rot_f[idx]["ativo"]]
            if len(lista_no) > max_labels_por_no:
                lista_no.sort(key=lambda idx: (rot_f[idx]["custo_mod"], rot_f[idx]["tempo"], rot_f[idx]["carga"]))
                manter = set(lista_no[:max_labels_por_no])
                for idx in lista_no[max_labels_por_no:]:
                    rot_f[idx]["ativo"] = False
                labels_f_por_no[no_i] = [idx for idx in labels_f_por_no[no_i] if idx in manter]

        # =========================
        # GERAÇÃO BACKWARD
        # =========================
        rot_b = []
        abertos_b = deque()
        labels_b_por_no = defaultdict(list)
        fronteira_b = defaultdict(list)

        idx0b = 0
        rot_b.append({
            "no": depf,
            "tempo_back": 0.0,
            "carga": 0.0,
            "custo_mod": 0.0,
            "mask": 0,
            "pai": None,
            "ativo": True,
            "nvisit": 0
        })
        abertos_b.append(idx0b)
        labels_b_por_no[depf].append(idx0b)
        fronteira_b[(depf, 0)].append(idx0b)

        while abertos_b:
            idx_atual = abertos_b.popleft()
            r = rot_b[idx_atual]

            if not r["ativo"]:
                continue

            no_j = r["no"]
            tempo_back_j = r["tempo_back"]
            carga_j = r["carga"]
            custo_j = r["custo_mod"]
            mask_j = r["mask"]
            nvisit_j = r["nvisit"]

            if nvisit_j >= max_depth:
                continue

            candidatos = []
            for i in range(1, nbcd + 1):
                if (mask_j & cliente_mask(i)) == 0:
                    candidatos.append(i)

            viaveis = []
            for i in candidatos:
                if (i, no_j) in arcos_proibidos or (i, no_j, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][i][no_j] > 0:
                    continue

                bit = cliente_mask(i)
                if (mask_j & bit) != 0:
                    continue

                nova_mask = mask_j | bit
                nova_carga = carga_j + d[i]
                if nova_carga > cap_k + 1e-9:
                    continue

                # backward simplificado: acumula tempo de trás para frente
                novo_tempo_back = tempo_back_j + s[i] + travel_time(i, no_j)

                custo_novo = custo_j + delta_rc(i, no_j)
                viaveis.append((i, novo_tempo_back, nova_carga, nova_mask, custo_novo))

            viaveis.sort(key=lambda tpl: tpl[4])

            for (i, novo_tempo_back, nova_carga, nova_mask, custo_novo) in viaveis:
                chave = (i, nova_mask)
                lista = fronteira_b.get(chave, [])

                dominado = False
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(ro["custo_mod"], ro["tempo_back"], ro["carga"],
                              custo_novo, novo_tempo_back, nova_carga):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    ro = rot_b[idx_old]
                    if not ro["ativo"]:
                        continue
                    if domina(custo_novo, novo_tempo_back, nova_carga,
                              ro["custo_mod"], ro["tempo_back"], ro["carga"]):
                        rot_b[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                idx_novo = len(rot_b)
                rot_b.append({
                    "no": i,
                    "tempo_back": novo_tempo_back,
                    "carga": nova_carga,
                    "custo_mod": custo_novo,
                    "mask": nova_mask,
                    "pai": idx_atual,
                    "ativo": True,
                    "nvisit": nvisit_j + 1
                })
                abertos_b.append(idx_novo)
                labels_b_por_no[i].append(idx_novo)
                nova_lista.append(idx_novo)
                fronteira_b[chave] = nova_lista

            lista_no = [idx for idx in labels_b_por_no[no_j] if rot_b[idx]["ativo"]]
            if len(lista_no) > max_labels_por_no:
                lista_no.sort(key=lambda idx: (rot_b[idx]["custo_mod"], rot_b[idx]["tempo_back"], rot_b[idx]["carga"]))
                manter = set(lista_no[:max_labels_por_no])
                for idx in lista_no[max_labels_por_no:]:
                    rot_b[idx]["ativo"] = False
                labels_b_por_no[no_j] = [idx for idx in labels_b_por_no[no_j] if idx in manter]

        # =========================
        # COMBINAÇÃO
        # =========================
        melhor_coluna = None
        melhor_rc = math.inf

        nos_encontro = set(labels_f_por_no.keys()).intersection(set(labels_b_por_no.keys()))
        nos_encontro = [m for m in nos_encontro if 1 <= m <= nbcd]

        for m in nos_encontro:
            lista_f = [idx for idx in labels_f_por_no[m] if rot_f[idx]["ativo"]]
            lista_b = [idx for idx in labels_b_por_no[m] if rot_b[idx]["ativo"]]

            for idx_f in lista_f:
                rf = rot_f[idx_f]
                rota_f = rota_forward(rot_f, idx_f)  # 0 -> ... -> m

                for idx_b in lista_b:
                    rb = rot_b[idx_b]
                    rota_b = rota_backward(rot_b, idx_b)  # m -> ... -> depf

                    mask_f = rf["mask"]
                    mask_b = rb["mask"]

                    inter = mask_f & mask_b
                    if inter != cliente_mask(m):
                        continue

                    rota_completa = rota_f[:-1] + rota_b

                    coluna, rc = avaliar_rota(rota_completa)
                    if coluna is None:
                        continue

                    if rc < melhor_rc:
                        melhor_rc = rc
                        melhor_coluna = coluna

        # =========================
        # FECHAMENTO DIRETO FORWARD
        # =========================
        # opcional: também tenta fechar labels forward direto no depósito final
        for no_i, lista_idx in labels_f_por_no.items():
            if no_i == depf:
                continue

            for idx in lista_idx:
                r = rot_f[idx]
                if not r["ativo"]:
                    continue

                if (no_i, depf) in arcos_proibidos or (no_i, depf, k) in arcos_proibidos:
                    continue

                if NO_BP.tabu_until[k][no_i][depf] > 0:
                    continue

                rota_f = rota_forward(rot_f, idx)
                rota = rota_f + [depf]
                coluna, rc = avaliar_rota(rota)
                if coluna is None:
                    continue

                if rc < melhor_rc:
                    melhor_rc = rc
                    melhor_coluna = coluna

        if melhor_coluna is not None and melhor_rc < -eps:
            return melhor_coluna, melhor_rc

        return None, None

    def escolhe_vizinho_enviesado(self, lista_ordenada, alpha=0.7):
        pesos=[]
        for pos in range(len(lista_ordenada)):
            pesos.append(alpha**pos)

        return(random.choices(lista_ordenada,weights=pesos,k=1)[0])

    def SUB_HEUR_VNS(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                     n_starts=40, alpha=0.3, eps=1e-6):

        import random
        import math

        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        cap_k = inst.veiculos[k].capacidade
        vel = inst.veiculos[k].velocidade

        proibidos_k = {(i, j) for (i, j, kk) in NO_BP.arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in NO_BP.arcos_fixados_em_1 if kk == k}

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None
            succ_fixo[i] = j
            pred_fixo[j] = i

        def travel(i, j):
            return inst.matriz_distancia[i][j] / vel

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return mu_arc[(i, j, k)]
            return mu_arc.get((i, j), 0.0)

        def delta_rc(i, j):
            rc = travel(i, j) - mu(i, j)

            if 1 <= j <= nbcd:
                rc -= pi[j - 1]

            if j == depf:
                rc -= sigma_k

            return rc

        def rota_para_binaria(rota):
            bin_x = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_x[v - 1] = 1
            return bin_x

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False
            return True

        def arcos_da_rota(rota):
            return [(rota[t], rota[t + 1]) for t in range(len(rota) - 1)]

        def custo_real_rota(rota):
            return sum(travel(rota[t], rota[t + 1]) for t in range(len(rota) - 1))

        def custo_reduzido_rota(rota):
            return sum(delta_rc(rota[t], rota[t + 1]) for t in range(len(rota) - 1))

        def checa_fixados_na_rota(rota):
            aset = set(arcos_da_rota(rota))
            for arc in fixados_k:
                if arc not in aset:
                    return False
            return True

        def prefixo_estado(rota):
            """
            Retorna:
              tempos_saida[pos]: instante de saída do nó rota[pos]
              cargas[pos]: carga acumulada ao sair de rota[pos]
              visitados_clientes
            """
            tempos_saida = [0.0] * len(rota)
            cargas = [0.0] * len(rota)
            visitados = set()

            # depósito inicial
            tempos_saida[0] = 0.0
            cargas[0] = 0.0

            for pos in range(1, len(rota)):
                i = rota[pos - 1]
                j = rota[pos]

                if not arco_permitido(i, j):
                    return None

                chegada = tempos_saida[pos - 1] + travel(i, j)

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return None
                    visitados.add(j)

                    carga = cargas[pos - 1] + inst.noh[j].DEMAND
                    if carga > cap_k:
                        return None
                    cargas[pos] = carga

                    a = inst.noh[j].READY_TIME[0]
                    b = inst.noh[j].DUE_DATE[0]
                    s = inst.noh[j].SERVICE_TIME[0]

                    if chegada < a:
                        chegada = a
                    if chegada > b:
                        return None

                    tempos_saida[pos] = chegada + s
                else:
                    cargas[pos] = cargas[pos - 1]
                    tempos_saida[pos] = chegada

            return tempos_saida, cargas, visitados

        def avalia_insercao(rota, tempos_saida, cargas, visitados, cliente, pos):
            """
            Testa inserir 'cliente' na posição pos.
            Recalcula só a partir de pos-1.
            Retorna:
                (ok, nova_rota, novos_tempos, novas_cargas, delta)
            """
            if cliente in visitados:
                return False, None, None, None, None

            i = rota[pos - 1]
            j = rota[pos]

            # não pode quebrar arco fixado existente
            if (i, j) in fixados_k:
                return False, None, None, None, None

            # novos arcos devem ser permitidos
            if not arco_permitido(i, cliente):
                return False, None, None, None, None
            if not arco_permitido(cliente, j):
                return False, None, None, None, None

            delta = delta_rc(i, cliente) + delta_rc(cliente, j) - delta_rc(i, j)

            nova_rota = rota[:pos] + [cliente] + rota[pos:]

            # recálculo incremental a partir de pos
            novos_tempos = tempos_saida[:pos]
            novas_cargas = cargas[:pos]
            novos_visit = set(v for v in visitados)

            prev_saida = tempos_saida[pos - 1]
            prev_carga = cargas[pos - 1]

            chegada = prev_saida + travel(i, cliente)

            if cliente in novos_visit:
                return False, None, None, None, None
            novos_visit.add(cliente)

            carga_cli = prev_carga + inst.noh[cliente].DEMAND
            if carga_cli > cap_k:
                return False, None, None, None, None

            a = inst.noh[cliente].READY_TIME[0]
            b = inst.noh[cliente].DUE_DATE[0]
            s = inst.noh[cliente].SERVICE_TIME[0]

            if chegada < a:
                chegada = a
            if chegada > b:
                return False, None, None, None, None

            saida = chegada + s
            novos_tempos.append(saida)
            novas_cargas.append(carga_cli)

            for idx in range(pos + 1, len(nova_rota)):
                u = nova_rota[idx - 1]
                v = nova_rota[idx]

                if not arco_permitido(u, v):
                    return False, None, None, None, None

                chegada_v = novos_tempos[idx - 1] + travel(u, v)

                if 1 <= v <= nbcd:
                    carga_v = novas_cargas[idx - 1] + inst.noh[v].DEMAND
                    a_v = inst.noh[v].READY_TIME[0]
                    b_v = inst.noh[v].DUE_DATE[0]
                    s_v = inst.noh[v].SERVICE_TIME[0]

                    if chegada_v < a_v:
                        chegada_v = a_v
                    if chegada_v > b_v:
                        return False, None, None, None, None
                    if carga_v > cap_k:
                        return False, None, None, None, None

                    novos_tempos.append(chegada_v + s_v)
                    novas_cargas.append(carga_v)
                else:
                    novos_tempos.append(chegada_v)
                    novas_cargas.append(novas_cargas[idx - 1])

            return True, nova_rota, novos_tempos, novas_cargas, delta

        def constrói_rota_base():
            """
            Tenta criar uma base coerente com os arcos fixos.
            """
            rota = [dep0]
            usados = {dep0}
            atual = dep0

            while atual in succ_fixo:
                prox = succ_fixo[atual]
                if prox in usados:
                    return None
                rota.append(prox)
                usados.add(prox)
                atual = prox
                if atual == depf:
                    break

            if rota[-1] != depf:
                if depf in pred_fixo and pred_fixo[depf] != rota[-1]:
                    return None
                rota.append(depf)

            # se há fixados desconectados da cadeia iniciada em 0, esta heurística não costura ainda
            if not checa_fixados_na_rota(rota) and len(fixados_k) > 0:
                return None

            estado = prefixo_estado(rota)
            if estado is None:
                return None

            return rota, estado[0], estado[1], estado[2]

        melhor_rota = None
        melhor_rc = math.inf
        melhor_custo = None

        base = constrói_rota_base()
        if base is None:
            # fallback: rota vazia só se não houver fixados
            if len(fixados_k) > 0:
                return None, None
            rota0 = [dep0, depf]
            estado0 = prefixo_estado(rota0)
            if estado0 is None:
                return None, None
            base = (rota0, estado0[0], estado0[1], estado0[2])

        for _ in range(n_starts):
            rota = base[0][:]
            tempos_saida = base[1][:]
            cargas = base[2][:]
            visitados = set(base[3])

            rc_total = custo_reduzido_rota(rota)

            while True:
                insercoes = []

                for cliente in range(1, nbcd + 1):
                    if cliente in visitados:
                        continue

                    # predecessor fixo ainda não está na rota
                    if cliente in pred_fixo and pred_fixo[cliente] not in rota:
                        continue

                    # sucessor fixo já está na rota, mas cliente ainda não
                    # a inserção só será aceita pelo teste local se estiver consistente

                    best_delta = math.inf
                    best_move = None

                    for pos in range(1, len(rota)):
                        ok, nova_rota, novos_tempos, novas_cargas, delta = avalia_insercao(
                            rota, tempos_saida, cargas, visitados, cliente, pos
                        )

                        if not ok:
                            continue

                        if delta < best_delta:
                            best_delta = delta
                            best_move = (pos, nova_rota, novos_tempos, novas_cargas, delta)

                    if best_move is not None:
                        insercoes.append((cliente, best_delta, best_move))

                if not insercoes:
                    break

                insercoes.sort(key=lambda x: x[1])

                rcl_size = max(1, int(len(insercoes) * alpha))
                cliente, _, move = random.choice(insercoes[:rcl_size])

                pos, rota, tempos_saida, cargas, delta = move
                visitados.add(cliente)
                rc_total += delta

            if len(rota) >= 3:
                if len(fixados_k) > 0 and not checa_fixados_na_rota(rota):
                    continue

                custo_real = custo_real_rota(rota)

                if rc_total < melhor_rc:
                    melhor_rc = rc_total
                    melhor_rota = rota[:]
                    melhor_custo = custo_real

                if melhor_rota is not None and melhor_rc < -eps:
                    return {
                        "clientes": melhor_rota,
                        "custo": melhor_custo,
                        "bin_xij": rota_para_binaria(melhor_rota)
                    }, melhor_rc

        return None, None

    def SUB_HEUR_VNSSemProibidos(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                     n_starts=40, alpha=0.3, eps=1e-6):

        import random
        import math

        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        cap_k = inst.veiculos[k].capacidade
        vel = inst.veiculos[k].velocidade

        def travel(i, j):
            return inst.matriz_distancia[i][j] / vel

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return mu_arc[(i, j, k)]
            return mu_arc.get((i, j), 0.0)

        def delta_rc(i, j):
            rc = travel(i, j) - mu(i, j)

            if 1 <= j <= nbcd:
                rc -= pi[j - 1]

            if j == depf:
                rc -= sigma_k

            return rc

        def rota_para_binaria(rota):
            bin_x = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_x[v - 1] = 1
            return bin_x

        # ---------------------
        # viabilidade simples
        # ---------------------

        def verifica_rota(rota):

            tempo = 0
            carga = 0
            visit = set()

            for t in range(len(rota) - 1):

                i = rota[t]
                j = rota[t + 1]

                tempo += travel(i, j)

                if 1 <= j <= nbcd:

                    if j in visit:
                        return False

                    visit.add(j)

                    carga += inst.noh[j].DEMAND

                    if carga > cap_k:
                        return False

                    a = inst.noh[j].READY_TIME[0]
                    b = inst.noh[j].DUE_DATE[0]
                    s = inst.noh[j].SERVICE_TIME[0]

                    if tempo < a:
                        tempo = a

                    if tempo > b:
                        return False

                    tempo += s

            return True

        # ---------------------

        melhor_rota = None
        melhor_rc = math.inf
        melhor_custo = None

        for start in range(n_starts):

            rota = [dep0, depf]
            visitados = set([dep0, depf])

            rc_total = delta_rc(dep0, depf)

            while True:

                insercoes = []

                for cliente in range(1, nbcd + 1):

                    if cliente in visitados:
                        continue

                    best_delta = math.inf
                    best_pos = None

                    for pos in range(1, len(rota)):

                        i = rota[pos - 1]
                        j = rota[pos]

                        delta = (
                                delta_rc(i, cliente)
                                + delta_rc(cliente, j)
                                - delta_rc(i, j)
                        )

                        nova = rota[:pos] + [cliente] + rota[pos:]

                        if not verifica_rota(nova):
                            continue

                        if delta < best_delta:
                            best_delta = delta
                            best_pos = pos

                    if best_pos is not None:
                        insercoes.append((cliente, best_pos, best_delta))

                if not insercoes:
                    break

                insercoes.sort(key=lambda x: x[2])

                rcl_size = max(1, int(len(insercoes) * alpha))
                cand = random.choice(insercoes[:rcl_size])

                cliente, pos, delta = cand

                rota.insert(pos, cliente)
                visitados.add(cliente)

                rc_total += delta

            if len(rota) >= 3:

                custo_real = 0
                for t in range(len(rota) - 1):
                    custo_real += travel(rota[t], rota[t + 1])

                if rc_total < melhor_rc:
                    melhor_rc = rc_total
                    melhor_rota = rota[:]
                    melhor_custo = custo_real

            if melhor_rota is not None and melhor_rc < -eps:
                return {
                    "clientes": melhor_rota,
                    "custo": melhor_custo,
                    "bin_xij": rota_para_binaria(melhor_rota)
                }, melhor_rc

        return None, None

    def SUB_HEUR_ALLBESTINSERTION(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                                  n_starts=30, eps=1e-6):
        import math
        import random

        if mu_arc is None:
            mu_arc = {}

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        # =========================================================
        # ARCOS FIXOS / PROIBIDOS DO NÓ BP
        # =========================================================
        proibidos_k = {(i, j) for (i, j, kk) in NO_BP.arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in NO_BP.arcos_fixados_em_1 if kk == k}

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None
            succ_fixo[i] = j
            pred_fixo[j] = i

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False
            return True

        def arcos_da_rota(rota):
            return [(rota[t], rota[t + 1]) for t in range(len(rota) - 1)]

        def contem_todos_fixados(rota):
            aset = set(arcos_da_rota(rota))
            for arc in fixados_k:
                if arc not in aset:
                    return False
            return True

        # =========================================================
        # DADOS DOS NÓS: múltiplas janelas por nó
        # =========================================================
        janelas = []
        d = []

        for i in range(nbn):
            noh = inst.noh[i]

            if (hasattr(noh, "READY_TIME") and hasattr(noh, "DUE_DATE")
                    and noh.READY_TIME and noh.DUE_DATE):

                servs = noh.SERVICE_TIME if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else [0.0] * len(
                    noh.READY_TIME)

                lista_janelas = []
                for r in range(len(noh.READY_TIME)):
                    ai = float(noh.READY_TIME[r])
                    bi = float(noh.DUE_DATE[r])
                    si = float(servs[r]) if r < len(servs) else float(servs[0])
                    lista_janelas.append((ai, bi, si))
            else:
                lista_janelas = [(0.0, float("inf"), 0.0)]

            lista_janelas.sort(key=lambda x: x[0])

            janelas.append(lista_janelas)
            d.append(float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def rota_para_binaria(rota):
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1
            return bin_xij

        def custo_reduzido_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                i = rota_av[t]
                j = rota_av[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def custo_real_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                val += travel_time(rota_av[t], rota_av[t + 1])
            return val

        def verifica_viabilidade(rota_av):
            """
            Retorna:
                (True, janelas_escolhidas, tempo_final, carga_final)
            ou
                (False, None, None, None)
            """
            if not rota_av or rota_av[0] != dep0 or rota_av[-1] != depf:
                return False, None, None, None

            # todos os arcos da rota precisam ser permitidos
            for (i, j) in arcos_da_rota(rota_av):
                if not arco_permitido(i, j):
                    return False, None, None, None

            visitados_local = set()
            carga = 0.0

            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota_av)):
                i = rota_av[pos - 1]
                j = rota_av[pos]

                if 1 <= j <= nbcd:
                    if j in visitados_local:
                        return False, None, None, None
                    visitados_local.add(j)

                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def constroi_rota_base():
            """
            Tenta iniciar a rota já com a cadeia fixa a partir do depósito.
            """
            rota = [dep0]
            usados = {dep0}
            atual = dep0

            while atual in succ_fixo:
                prox = succ_fixo[atual]

                if prox in usados:
                    return None

                rota.append(prox)
                usados.add(prox)
                atual = prox

                if atual == depf:
                    break

            if rota[-1] != depf:
                if depf in pred_fixo and pred_fixo[depf] != rota[-1]:
                    return None
                rota.append(depf)

            viavel, janelas_escolhidas, tempo_final, carga_final = verifica_viabilidade(rota)
            if not viavel:
                return None

            return rota, set(rota), janelas_escolhidas, tempo_final, carga_final

        def melhores_insercoes(rota_atual, visitados, rc_atual):
            """
            Gera todas as inserções viáveis em todas as posições.
            Retorna lista ordenada por delta de custo reduzido.
            """
            insercoes = []

            for cliente in range(1, nbcd + 1):
                if cliente in visitados:
                    continue

                # se cliente tem predecessor fixo, esse predecessor precisa já estar na rota
                if cliente in pred_fixo and pred_fixo[cliente] not in rota_atual:
                    continue

                for pos in range(1, len(rota_atual)):  # insere antes de pos
                    i = rota_atual[pos - 1]
                    j = rota_atual[pos]

                    # não pode quebrar um arco fixado existente
                    if (i, j) in fixados_k:
                        continue

                    # novos arcos devem ser permitidos
                    if not arco_permitido(i, cliente):
                        continue
                    if not arco_permitido(cliente, j):
                        continue

                    nova_rota = rota_atual[:pos] + [cliente] + rota_atual[pos:]

                    viavel, janelas_novas, tempo_final, carga_final = verifica_viabilidade(nova_rota)
                    if not viavel:
                        continue

                    rc_nova = custo_reduzido_rota(nova_rota)
                    custo_real_novo = custo_real_rota(nova_rota)
                    delta_rc = rc_nova - rc_atual

                    score = delta_rc + 0.01 * tempo_final

                    insercoes.append((
                        cliente,  # 0
                        pos,  # 1
                        nova_rota,  # 2
                        delta_rc,  # 3
                        rc_nova,  # 4
                        custo_real_novo,  # 5
                        janelas_novas,  # 6
                        tempo_final,  # 7
                        carga_final,  # 8
                        score  # 9
                    ))

            insercoes.sort(key=lambda x: (x[3], x[9], x[4]))
            return insercoes

        melhor_rota = None
        melhor_custo_red = math.inf
        melhor_custo_real = None

        base = constroi_rota_base()

        if base is None:
            if len(fixados_k) > 0:
                return None, None

            rota0 = [dep0, depf]
            viavel_ini, janelas_escolhidas0, tempo_final0, carga_final0 = verifica_viabilidade(rota0)
            if not viavel_ini:
                return None, None

            base = (rota0, {dep0, depf}, janelas_escolhidas0, tempo_final0, carga_final0)

        for ii in range(n_starts):

            rota = base[0][:]
            visitados = set(base[1])
            janelas_escolhidas = list(base[2])
            tempo_final = base[3]
            carga_final = base[4]

            custo_red_total = custo_reduzido_rota(rota)
            custo_real_total = custo_real_rota(rota)

            while True:
                insercoes = melhores_insercoes(rota, visitados, custo_red_total)

                if not insercoes:
                    break

                melhor_delta = insercoes[0][3]
                pior_delta = insercoes[-1][3]

                alpha_rcl = random.uniform(0.15, 0.40)
                limite = melhor_delta + alpha_rcl * (pior_delta - melhor_delta)

                rcl = [ins for ins in insercoes if ins[3] <= limite]
                if not rcl:
                    rcl = insercoes[:1]

                cliente, pos, rota_nova, delta_rc, rc_nova, custo_real_novo, janelas_novas, tempo_novo, carga_nova, score = random.choice(
                    rcl)

                if delta_rc > 1e-6 and custo_red_total > 1e-6:
                    break

                rota = rota_nova
                visitados.add(cliente)
                janelas_escolhidas = janelas_novas
                tempo_final = tempo_novo
                carga_final = carga_nova
                custo_red_total = rc_nova
                custo_real_total = custo_real_novo

                if len(visitados) >= nbcd + 2:
                    break

            if len(rota) >= 3:
                if len(fixados_k) > 0 and not contem_todos_fixados(rota):
                    continue

                rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                    rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                )

                if rota_melhorada is not None:
                    # garante que a BL não destruiu os fixos / proibidos
                    viavel_bl, _, _, _ = verifica_viabilidade(rota_melhorada)
                    if not viavel_bl:
                        rota_melhorada = None
                    elif len(fixados_k) > 0 and not contem_todos_fixados(rota_melhorada):
                        rota_melhorada = None

                if rota_melhorada is not None and custo_red_melhorado < melhor_custo_red:
                    melhor_rota = rota_melhorada[:]
                    melhor_custo_red = custo_red_melhorado
                    melhor_custo_real = custo_real_melhorado

                if melhor_rota is not None and melhor_custo_red < -eps:
                    return {
                        "clientes": melhor_rota,
                        "custo": melhor_custo_real,
                        "bin_xij": rota_para_binaria(melhor_rota)
                    }, melhor_custo_red

        return None, None

    def SUB_HEUR_ALLBESTINSERTIONsemfixos(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                                  n_starts=30, eps=1e-6):
        import math
        import random

        if mu_arc is None:
            mu_arc = {}

        #print(f"Subprob ALL BEST INSERTION veículo {k}")

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        # =========================================================
        # DADOS DOS NÓS: múltiplas janelas por nó
        # cada janela = (ready, due, service)
        # =========================================================
        janelas = []
        d = []

        for i in range(nbn):
            noh = inst.noh[i]

            if (hasattr(noh, "READY_TIME") and hasattr(noh, "DUE_DATE")
                    and noh.READY_TIME and noh.DUE_DATE):

                servs = noh.SERVICE_TIME if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else [0.0] * len(
                    noh.READY_TIME)

                lista_janelas = []
                for r in range(len(noh.READY_TIME)):
                    ai = float(noh.READY_TIME[r])
                    bi = float(noh.DUE_DATE[r])
                    si = float(servs[r]) if r < len(servs) else float(servs[0])
                    lista_janelas.append((ai, bi, si))
            else:
                lista_janelas = [(0.0, float("inf"), 0.0)]

            lista_janelas.sort(key=lambda x: x[0])

            janelas.append(lista_janelas)
            d.append(float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def rota_para_binaria(rota):
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1
            return bin_xij

        def custo_reduzido_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                i = rota_av[t]
                j = rota_av[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def custo_real_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                val += travel_time(rota_av[t], rota_av[t + 1])
            return val

        def verifica_viabilidade(rota_av):
            """
            Retorna:
                (True, janelas_escolhidas, tempo_final, carga_final)
            ou
                (False, None, None, None)
            """
            if not rota_av or rota_av[0] != dep0 or rota_av[-1] != depf:
                return False, None, None, None

            visitados_local = set()
            carga = 0.0

            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota_av)):
                i = rota_av[pos - 1]
                j = rota_av[pos]

                if 1 <= j <= nbcd:
                    if j in visitados_local:
                        return False, None, None, None
                    visitados_local.add(j)

                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    # se no seu modelo exigir término dentro da janela,
                    # troque por: if fim_servico_j <= bj + 1e-9:
                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def melhores_insercoes(rota_atual, visitados, rc_atual):
            """
            Gera todas as inserções viáveis em todas as posições.
            Retorna lista ordenada por delta de custo reduzido.
            """
            insercoes = []

            for cliente in range(1, nbcd + 1):
                if cliente in visitados:
                    continue

                for pos in range(1, len(rota_atual)):  # insere antes de pos
                    nova_rota = rota_atual[:pos] + [cliente] + rota_atual[pos:]

                    viavel, janelas_novas, tempo_final, carga_final = verifica_viabilidade(nova_rota)
                    if not viavel:
                        continue

                    rc_nova = custo_reduzido_rota(nova_rota)
                    custo_real_novo = custo_real_rota(nova_rota)
                    delta_rc = rc_nova - rc_atual

                    # folga simples: quanto menor tempo final, melhor
                    score = delta_rc + 0.01 * tempo_final

                    insercoes.append((
                        cliente,  # 0
                        pos,  # 1
                        nova_rota,  # 2
                        delta_rc,  # 3
                        rc_nova,  # 4
                        custo_real_novo,  # 5
                        janelas_novas,  # 6
                        tempo_final,  # 7
                        carga_final,  # 8
                        score  # 9
                    ))

            insercoes.sort(key=lambda x: (x[3], x[9], x[4]))
            return insercoes

        melhor_rota = None
        melhor_custo_red = math.inf
        melhor_custo_real = None

        for ii in range(n_starts):
            #print(f"\nSTART {ii}")

            rota = [dep0, depf]
            visitados = {dep0, depf}

            viavel_ini, janelas_escolhidas, tempo_final, carga_final = verifica_viabilidade(rota)
            if not viavel_ini:
                #print("Rota inicial [dep0,depf] inviável")
                return None, None

            custo_red_total = custo_reduzido_rota(rota)
            custo_real_total = custo_real_rota(rota)

            #print(f"rota inicial = {rota} | rc = {custo_red_total}")

            while True:
                insercoes = melhores_insercoes(rota, visitados, custo_red_total)

                if not insercoes:
                    #print("sem inserções viáveis")
                    break

                melhor_delta = insercoes[0][3]
                pior_delta = insercoes[-1][3]

                alpha_rcl = random.uniform(0.15, 0.40)
                limite = melhor_delta + alpha_rcl * (pior_delta - melhor_delta)

                rcl = [ins for ins in insercoes if ins[3] <= limite]
                if not rcl:
                    rcl = insercoes[:1]

                # diversificação
                cliente, pos, rota_nova, delta_rc, rc_nova, custo_real_novo, janelas_novas, tempo_novo, carga_nova, score = random.choice(
                    rcl)

                #print(
                #    f"inserindo cliente {cliente} na posição {pos} | delta_rc = {delta_rc:.6f} | rc_novo = {rc_nova:.6f}")

                # regra de parada: se piorou demais e já não está promissor, para
                if delta_rc > 1e-6 and custo_red_total > 1e-6:
                    #print("inserção piora a rota e rc atual já não é promissor")
                    break

                rota = rota_nova
                visitados.add(cliente)
                janelas_escolhidas = janelas_novas
                tempo_final = tempo_novo
                carga_final = carga_nova
                custo_red_total = rc_nova
                custo_real_total = custo_real_novo

                #print(f"rota atual = {rota} | rc = {custo_red_total:.6f}")

                # se não sobrou cliente, para
                if len(visitados) >= nbcd + 2:
                    break

            # precisa ter pelo menos 1 cliente
            if len(rota) >= 3:
                #print(f"rota construída final = {rota} | rc = {custo_red_total:.6f}")

                rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                    rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                )

                #print(f"rota BL = {rota_melhorada} | rc BL = {custo_red_melhorado}")

                if rota_melhorada is not None and custo_red_melhorado < melhor_custo_red:
                    melhor_rota = rota_melhorada[:]
                    melhor_custo_red = custo_red_melhorado
                    melhor_custo_real = custo_real_melhorado

                if melhor_rota is not None and melhor_custo_red < -eps:
                    return {
                        "clientes": melhor_rota,
                        "custo": melhor_custo_real,
                        "bin_xij": rota_para_binaria(melhor_rota)
                    }, melhor_custo_red

        return None, None

    def SUB_VNSRANDOMant(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                      n_starts=30, eps=1e-6):
        import math
        import random

        if mu_arc is None:
            mu_arc = {}

        print(f"Subprob VNS RANDOM veículo {k}")

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        proibidos_k = {(i, j) for (i, j, kk) in NO_BP.arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in NO_BP.arcos_fixados_em_1 if kk == k}

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None
            succ_fixo[i] = j
            pred_fixo[j] = i

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False
            return True

        def arcos_da_rota(rota):
            return [(rota[t], rota[t + 1]) for t in range(len(rota) - 1)]

        def contem_todos_fixados(rota):
            aset = set(arcos_da_rota(rota))
            for arc in fixados_k:
                if arc not in aset:
                    return False
            return True

        # =========================================================
        # DADOS DOS NÓS: múltiplas janelas por nó
        # =========================================================
        janelas = []
        d = []

        for i in range(nbn):
            noh = inst.noh[i]

            if (hasattr(noh, "READY_TIME") and hasattr(noh, "DUE_DATE")
                    and noh.READY_TIME and noh.DUE_DATE):

                servs = noh.SERVICE_TIME if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else [0.0] * len(
                    noh.READY_TIME)

                lista_janelas = []
                for r in range(len(noh.READY_TIME)):
                    ai = float(noh.READY_TIME[r])
                    bi = float(noh.DUE_DATE[r])
                    si = float(servs[r]) if r < len(servs) else float(servs[0])
                    lista_janelas.append((ai, bi, si))
            else:
                lista_janelas = [(0.0, float("inf"), 0.0)]

            lista_janelas.sort(key=lambda x: x[0])

            janelas.append(lista_janelas)
            d.append(float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def rota_para_binaria(rota):
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1
            return bin_xij

        def custo_real_rota(rota):
            val = 0.0
            for t in range(len(rota) - 1):
                val += travel_time(rota[t], rota[t + 1])
            return val

        def custo_reduzido_rota(rota):
            val = 0.0
            for t in range(len(rota) - 1):
                i = rota[t]
                j = rota[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def escolhe_janela_viavel(no_i, tempo_fim_i, j):
            chegada_j = tempo_fim_i + travel_time(no_i, j)

            melhor = None
            for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                inicio_servico_j = max(chegada_j, aj)
                fim_servico_j = inicio_servico_j + sj

                if inicio_servico_j <= bj + 1e-9:
                    melhor = (inicio_servico_j, fim_servico_j, idx_janela)
                    break

            return melhor

        def score_candidato(no_i, j, delta_rc, tempo_atual, nova_carga):
            melhor_janela = escolhe_janela_viavel(no_i, tempo_atual, j)
            if melhor_janela is None:
                return math.inf

            inicio_servico_j, fim_servico_j, idx_janela = melhor_janela

            rc_fecho = travel_time(j, depf) - mu(j, depf) - float(sigma_k)

            aj, bj, sj = janelas[j][idx_janela]
            folga = bj - inicio_servico_j
            ocup = nova_carga / max(cap_k, 1.0)

            score = (
                    1.0 * delta_rc +
                    0.25 * rc_fecho +
                    0.02 * fim_servico_j +
                    2.0 * ocup -
                    0.01 * folga
            )

            return score

        def verifica_rota(rota):
            if not rota or rota[0] != dep0 or rota[-1] != depf:
                return False, None, None, None

            for (i, j) in arcos_da_rota(rota):
                if not arco_permitido(i, j):
                    return False, None, None, None
                if NO_BP.tabu_until[k][i][j] > 0:
                    return False, None, None, None

            visitados_local = set()
            carga = 0.0

            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota)):
                i = rota[pos - 1]
                j = rota[pos]

                if 1 <= j <= nbcd:
                    if j in visitados_local:
                        return False, None, None, None
                    visitados_local.add(j)

                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            if len(fixados_k) > 0 and not contem_todos_fixados(rota):
                return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def constroi_rota_base():
            rota = [dep0]
            usados = {dep0}
            atual = dep0

            while atual in succ_fixo:
                prox = succ_fixo[atual]

                if prox in usados:
                    return None

                rota.append(prox)
                usados.add(prox)
                atual = prox

                if atual == depf:
                    break

            if rota[-1] != depf:
                if depf in pred_fixo and pred_fixo[depf] != rota[-1]:
                    return None
                rota.append(depf)

            viavel, janelas_escolhidas, tempo_final, carga_final = verifica_rota(rota)
            if not viavel:
                return None

            return rota, set(rota), janelas_escolhidas, tempo_final, carga_final

        melhor_rota = None
        melhor_custo_real = None
        melhor_custo_red = math.inf

        # =========================================================
        # PRE-CÁLCULO
        # =========================================================
        rc = [[math.inf] * nbn for _ in range(nbn)]
        vizinhos_ordenados = [[] for _ in range(nbn)]

        for i in range(nbn):
            linha = []

            for j in range(nbn):
                if i == j:
                    continue

                if not arco_permitido(i, j):
                    continue

                val = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    val -= float(pi[j - 1])

                if j == depf:
                    val -= float(sigma_k)

                rc[i][j] = val
                linha.append((j, val))

            linha.sort(key=lambda x: x[1])
            vizinhos_ordenados[i] = linha

        base = constroi_rota_base()

        if base is None:
            if len(fixados_k) > 0:
                return None, None

            rota0 = [dep0, depf]
            viavel0, janelas0, tempo0, carga0 = verifica_rota(rota0)
            if not viavel0:
                return None, None
            base = (rota0, {dep0, depf}, janelas0, tempo0, carga0)

        # =========================================================
        # MULTI-START RANDOMIZADO
        # =========================================================
        for ii in range(n_starts):

            rota = base[0][:]
            visitados = set(base[1])
            janelas_escolhidas = list(base[2])
            tempo_atual = base[3]
            carga_atual = base[4]
            no_atual = rota[-1]

            if no_atual == depf and len(rota) > 1:
                # se a base já terminou no depósito final, reabre para inserir no meio
                rota = rota[:-1]
                janelas_escolhidas = janelas_escolhidas[:-1]
                no_atual = rota[-1]

                # recalcula estado até o último nó atual
                a0, b0, s0 = janelas[dep0][0]
                inicio_servico_0 = max(0.0, a0)
                tempo_atual = inicio_servico_0 + s0
                carga_atual = 0.0

                for pos in range(1, len(rota)):
                    i = rota[pos - 1]
                    j = rota[pos]
                    janela_viavel = escolhe_janela_viavel(i, tempo_atual, j)
                    if janela_viavel is None:
                        return None, None
                    inicio_servico_j, fim_servico_j, idx_janela = janela_viavel
                    tempo_atual = fim_servico_j
                    if 1 <= j <= nbcd:
                        carga_atual += d[j]

            custo_red_total = custo_reduzido_rota(rota) if len(rota) >= 2 else 0.0

            while True:
                viaveis = []

                top_k = random.randint(2, min(7, max(2, nbcd)))

                for (j, delta_rc) in vizinhos_ordenados[no_atual]:

                    if j in visitados:
                        continue

                    if NO_BP.tabu_until[k][no_atual][j] > 0:
                        continue

                    nova_carga = carga_atual + (d[j] if 1 <= j <= nbcd else 0.0)
                    if nova_carga > cap_k + 1e-9:
                        continue

                    janela_viavel = escolhe_janela_viavel(no_atual, tempo_atual, j)
                    if janela_viavel is None:
                        continue

                    inicio_servico_j, fim_servico_j, idx_janela = janela_viavel

                    # se j tem sucessor fixo, não pode ficar "preso" sem possibilidade de continuar
                    if j in succ_fixo:
                        prox_fixo = succ_fixo[j]
                        if prox_fixo in visitados:
                            continue
                        if not arco_permitido(j, prox_fixo):
                            continue

                    score = score_candidato(no_atual, j, delta_rc, tempo_atual, nova_carga)

                    viaveis.append((
                        j,
                        inicio_servico_j,
                        fim_servico_j,
                        nova_carga,
                        delta_rc,
                        idx_janela,
                        score
                    ))

                # tenta fechar no depósito final quando a rota atual não termina lá
                if no_atual != depf and arco_permitido(no_atual, depf) and NO_BP.tabu_until[k][no_atual][depf] <= 0:
                    janela_fecho = escolhe_janela_viavel(no_atual, tempo_atual, depf)
                    if janela_fecho is not None:
                        inicio_servico_f, fim_servico_f, idx_janela_f = janela_fecho
                        delta_fecho = rc[no_atual][depf]
                        score_fecho = score_candidato(no_atual, depf, delta_fecho, tempo_atual, carga_atual)
                        viaveis.append((
                            depf,
                            inicio_servico_f,
                            fim_servico_f,
                            carga_atual,
                            delta_fecho,
                            idx_janela_f,
                            score_fecho
                        ))

                if not viaveis:
                    break

                viaveis.sort(key=lambda x: x[6])
                viaveis = viaveis[:top_k]

                j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela, score = (
                    self.escolhe_vizinho_enviesado(viaveis, alpha=0.55)
                )

                rota.append(j)
                janelas_escolhidas.append(idx_janela)

                custo_red_total += delta_rc
                tempo_atual = fim_servico_j
                carga_atual = nova_carga
                no_atual = j

                visitados.add(j)

                if j == depf:
                    break

            if len(rota) >= 3 and rota[-1] == depf:
                viavel_final, _, _, _ = verifica_rota(rota)
                if viavel_final:
                    custo_real = custo_real_rota(rota)

                    if custo_red_total < melhor_custo_red:
                        melhor_custo_red = custo_red_total
                        melhor_custo_real = custo_real
                        melhor_rota = rota[:]

            if melhor_rota is not None and melhor_custo_red < -eps:
                return {
                    "clientes": melhor_rota,
                    "custo": melhor_custo_real,
                    "bin_xij": rota_para_binaria(melhor_rota)
                }, melhor_custo_red
            else:
                if len(rota) >= 3 and rota[-1] == depf:
                    viavel_final, _, _, _ = verifica_rota(rota)
                    if viavel_final:
                        rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                            rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                        )

                        if rota_melhorada is not None:
                            viavel_bl, _, _, _ = verifica_rota(rota_melhorada)
                            if not viavel_bl:
                                rota_melhorada = None

                        if rota_melhorada is not None and custo_red_melhorado < -eps:
                            return {
                                "clientes": rota_melhorada,
                                "custo": custo_real_melhorado,
                                "bin_xij": rota_para_binaria(rota_melhorada)
                            }, custo_red_melhorado

        return None, None

    def SUB_VNSRANDOM(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                      n_starts=30, eps=1e-6):
        import math
        import random

        if mu_arc is None:
            mu_arc = {}

        print(f"Subprob VNS RANDOM veículo {k}")

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        proibidos_k = {(i, j) for (i, j, kk) in NO_BP.arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in NO_BP.arcos_fixados_em_1 if kk == k}

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None
            succ_fixo[i] = j
            pred_fixo[j] = i

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False
            return True

        def arcos_da_rota(rota):
            return [(rota[t], rota[t + 1]) for t in range(len(rota) - 1)]

        def contem_todos_fixados(rota):
            aset = set(arcos_da_rota(rota))
            for arc in fixados_k:
                if arc not in aset:
                    return False
            return True

        # =========================================================
        # DADOS DOS NÓS: múltiplas janelas por nó
        # =========================================================
        janelas = []
        d = []

        for i in range(nbn):
            noh = inst.noh[i]

            if (hasattr(noh, "READY_TIME") and hasattr(noh, "DUE_DATE")
                    and noh.READY_TIME and noh.DUE_DATE):

                servs = noh.SERVICE_TIME if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else [0.0] * len(
                    noh.READY_TIME)

                lista_janelas = []
                for r in range(len(noh.READY_TIME)):
                    ai = float(noh.READY_TIME[r])
                    bi = float(noh.DUE_DATE[r])
                    si = float(servs[r]) if r < len(servs) else float(servs[0])
                    lista_janelas.append((ai, bi, si))
            else:
                lista_janelas = [(0.0, float("inf"), 0.0)]

            lista_janelas.sort(key=lambda x: x[0])

            janelas.append(lista_janelas)
            d.append(float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def rota_para_binaria(rota):
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1
            return bin_xij

        def custo_real_rota(rota):
            val = 0.0
            for t in range(len(rota) - 1):
                val += travel_time(rota[t], rota[t + 1])
            return val

        def custo_reduzido_rota(rota):
            val = 0.0
            for t in range(len(rota) - 1):
                i = rota[t]
                j = rota[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def escolhe_janela_viavel(no_i, tempo_fim_i, j):
            chegada_j = tempo_fim_i + travel_time(no_i, j)

            melhor = None
            for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                inicio_servico_j = max(chegada_j, aj)
                fim_servico_j = inicio_servico_j + sj

                if inicio_servico_j <= bj + 1e-9:
                    melhor = (inicio_servico_j, fim_servico_j, idx_janela)
                    break

            return melhor

        def rank_proximidade(no_i, j):
            pos = pos_vizinho_dist[no_i].get(j, top_near_default + 5)
            return float(pos)

        def score_candidato(no_i, j, delta_rc, tempo_atual, nova_carga):
            melhor_janela = escolhe_janela_viavel(no_i, tempo_atual, j)
            if melhor_janela is None:
                return math.inf

            inicio_servico_j, fim_servico_j, idx_janela = melhor_janela

            rc_fecho = travel_time(j, depf) - mu(j, depf) - float(sigma_k)

            aj, bj, sj = janelas[j][idx_janela]
            folga = bj - inicio_servico_j
            ocup = nova_carga / max(cap_k, 1.0)
            dist_ij = travel_time(no_i, j)
            rank_dist = rank_proximidade(no_i, j)

            score = (
                    1.00 * delta_rc +
                    0.20 * rc_fecho +
                    0.12 * dist_ij +
                    0.03 * rank_dist +
                    0.01 * fim_servico_j +
                    1.20 * ocup -
                    0.02 * folga
            )

            return score

        def verifica_rota(rota):
            if not rota or rota[0] != dep0 or rota[-1] != depf:
                return False, None, None, None

            for (i, j) in arcos_da_rota(rota):
                if not arco_permitido(i, j):
                    return False, None, None, None
                if NO_BP.tabu_until[k][i][j] > 0:
                    return False, None, None, None

            visitados_local = set()
            carga = 0.0

            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota)):
                i = rota[pos - 1]
                j = rota[pos]

                if 1 <= j <= nbcd:
                    if j in visitados_local:
                        return False, None, None, None
                    visitados_local.add(j)

                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            if len(fixados_k) > 0 and not contem_todos_fixados(rota):
                return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def constroi_rota_base():
            rota = [dep0]
            usados = {dep0}
            atual = dep0

            while atual in succ_fixo:
                prox = succ_fixo[atual]

                if prox in usados:
                    return None

                rota.append(prox)
                usados.add(prox)
                atual = prox

                if atual == depf:
                    break

            if rota[-1] != depf:
                if depf in pred_fixo and pred_fixo[depf] != rota[-1]:
                    return None
                rota.append(depf)

            viavel, janelas_escolhidas, tempo_final, carga_final = verifica_rota(rota)
            if not viavel:
                return None

            return rota, set(rota), janelas_escolhidas, tempo_final, carga_final

        melhor_rota = None
        melhor_custo_real = None
        melhor_custo_red = math.inf

        # =========================================================
        # PRE-CÁLCULO
        # =========================================================
        rc = [[math.inf] * nbn for _ in range(nbn)]
        vizinhos_ordenados = [[] for _ in range(nbn)]
        vizinhos_dist = [[] for _ in range(nbn)]
        pos_vizinho_dist = [dict() for _ in range(nbn)]

        top_near_default = 12

        for i in range(nbn):
            linha_rc = []
            linha_dist = []

            for j in range(nbn):
                if i == j:
                    continue

                if not arco_permitido(i, j):
                    continue

                dist_ij = travel_time(i, j)
                linha_dist.append((j, dist_ij))

                val = dist_ij - mu(i, j)

                if 1 <= j <= nbcd:
                    val -= float(pi[j - 1])

                if j == depf:
                    val -= float(sigma_k)

                rc[i][j] = val
                linha_rc.append((j, val))

            linha_rc.sort(key=lambda x: x[1])
            linha_dist.sort(key=lambda x: x[1])

            vizinhos_ordenados[i] = linha_rc
            vizinhos_dist[i] = [j for (j, _) in linha_dist]

            for pos, (j, _) in enumerate(linha_dist):
                pos_vizinho_dist[i][j] = pos

        base = constroi_rota_base()

        if base is None:
            if len(fixados_k) > 0:
                return None, None

            rota0 = [dep0, depf]
            viavel0, janelas0, tempo0, carga0 = verifica_rota(rota0)
            if not viavel0:
                return None, None
            base = (rota0, {dep0, depf}, janelas0, tempo0, carga0)

        # =========================================================
        # MULTI-START RANDOMIZADO
        # =========================================================
        for ii in range(n_starts):

            rota = base[0][:]
            visitados = set(base[1])
            janelas_escolhidas = list(base[2])
            tempo_atual = base[3]
            carga_atual = base[4]
            no_atual = rota[-1]

            if no_atual == depf and len(rota) > 1:
                rota = rota[:-1]
                janelas_escolhidas = janelas_escolhidas[:-1]
                no_atual = rota[-1]

                a0, b0, s0 = janelas[dep0][0]
                inicio_servico_0 = max(0.0, a0)
                tempo_atual = inicio_servico_0 + s0
                carga_atual = 0.0

                for pos in range(1, len(rota)):
                    i = rota[pos - 1]
                    j = rota[pos]
                    janela_viavel = escolhe_janela_viavel(i, tempo_atual, j)
                    if janela_viavel is None:
                        return None, None
                    inicio_servico_j, fim_servico_j, idx_janela = janela_viavel
                    tempo_atual = fim_servico_j
                    if 1 <= j <= nbcd:
                        carga_atual += d[j]

            custo_red_total = custo_reduzido_rota(rota) if len(rota) >= 2 else 0.0

            while True:
                viaveis = []

                # mais exploração no começo, mais foco depois
                if ii < max(1, n_starts // 3):
                    top_near = 18
                    limite_top_k = 8
                else:
                    top_near = 12
                    limite_top_k = 5

                permitidos_proximos = set(vizinhos_dist[no_atual][:top_near])

                for (j, delta_rc) in vizinhos_ordenados[no_atual]:

                    if j in visitados:
                        continue

                    if NO_BP.tabu_until[k][no_atual][j] > 0:
                        continue

                    # prioriza vizinhos próximos, mas deixa passar arcos muito bons em rc
                    if j not in permitidos_proximos and delta_rc > -5.0:
                        continue

                    nova_carga = carga_atual + (d[j] if 1 <= j <= nbcd else 0.0)
                    if nova_carga > cap_k + 1e-9:
                        continue

                    janela_viavel = escolhe_janela_viavel(no_atual, tempo_atual, j)
                    if janela_viavel is None:
                        continue

                    inicio_servico_j, fim_servico_j, idx_janela = janela_viavel

                    if j in succ_fixo:
                        prox_fixo = succ_fixo[j]
                        if prox_fixo in visitados:
                            continue
                        if not arco_permitido(j, prox_fixo):
                            continue

                    score = score_candidato(no_atual, j, delta_rc, tempo_atual, nova_carga)

                    viaveis.append((
                        j,
                        inicio_servico_j,
                        fim_servico_j,
                        nova_carga,
                        delta_rc,
                        idx_janela,
                        score
                    ))

                if no_atual != depf and arco_permitido(no_atual, depf) and NO_BP.tabu_until[k][no_atual][depf] <= 0:
                    janela_fecho = escolhe_janela_viavel(no_atual, tempo_atual, depf)
                    if janela_fecho is not None:
                        inicio_servico_f, fim_servico_f, idx_janela_f = janela_fecho
                        delta_fecho = rc[no_atual][depf]
                        score_fecho = score_candidato(no_atual, depf, delta_fecho, tempo_atual, carga_atual)
                        viaveis.append((
                            depf,
                            inicio_servico_f,
                            fim_servico_f,
                            carga_atual,
                            delta_fecho,
                            idx_janela_f,
                            score_fecho
                        ))

                if not viaveis:
                    break

                viaveis.sort(key=lambda x: x[6])

                top_k = min(limite_top_k, len(viaveis))
                viaveis = viaveis[:top_k]

                alpha_escolha = 0.35 if ii < max(1, n_starts // 3) else 0.60

                j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela, score = (
                    self.escolhe_vizinho_enviesado(viaveis, alpha=alpha_escolha)
                )

                rota.append(j)
                janelas_escolhidas.append(idx_janela)

                custo_red_total += delta_rc
                tempo_atual = fim_servico_j
                carga_atual = nova_carga
                no_atual = j

                visitados.add(j)

                if j == depf:
                    break

            if len(rota) >= 3 and rota[-1] == depf:
                viavel_final, _, _, _ = verifica_rota(rota)
                if viavel_final:
                    custo_real = custo_real_rota(rota)

                    if custo_red_total < melhor_custo_red:
                        melhor_custo_red = custo_red_total
                        melhor_custo_real = custo_real
                        melhor_rota = rota[:]

            if melhor_rota is not None and melhor_custo_red < -eps:
                return {
                    "clientes": melhor_rota,
                    "custo": melhor_custo_real,
                    "bin_xij": rota_para_binaria(melhor_rota)
                }, melhor_custo_red
            else:
                if len(rota) >= 3 and rota[-1] == depf:
                    viavel_final, _, _, _ = verifica_rota(rota)
                    if viavel_final:
                        rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                            rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                        )

                        if rota_melhorada is not None:
                            viavel_bl, _, _, _ = verifica_rota(rota_melhorada)
                            if not viavel_bl:
                                rota_melhorada = None

                        if rota_melhorada is not None and custo_red_melhorado < -eps:
                            return {
                                "clientes": rota_melhorada,
                                "custo": custo_real_melhorado,
                                "bin_xij": rota_para_binaria(rota_melhorada)
                            }, custo_red_melhorado

        return None, None

    def SUB_VNSRANDOMSemFixos(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                       n_starts=30, eps=1e-6):
        import math
        import random
        top_k=5
        if mu_arc is None:
            mu_arc = {}

        print(f"Subprob VNS RANDOM veículo {k}")


        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1



        # =========================================================
        # DADOS DOS NÓS: múltiplas janelas por nó
        # cada janela = (ready, due, service)
        # =========================================================
        janelas = []
        d = []

        for i in range(nbn):
            noh = inst.noh[i]

            if (hasattr(noh, "READY_TIME") and hasattr(noh, "DUE_DATE")
                    and noh.READY_TIME and noh.DUE_DATE):

                servs = noh.SERVICE_TIME if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else [0.0] * len(
                    noh.READY_TIME)

                lista_janelas = []
                for r in range(len(noh.READY_TIME)):
                    ai = float(noh.READY_TIME[r])
                    bi = float(noh.DUE_DATE[r])
                    si = float(servs[r]) if r < len(servs) else float(servs[0])
                    lista_janelas.append((ai, bi, si))
            else:
                lista_janelas = [(0.0, float("inf"), 0.0)]

            # opcional: ordenar por início da janela
            lista_janelas.sort(key=lambda x: x[0])

            janelas.append(lista_janelas)
            d.append(float(noh.DEMAND) if hasattr(noh, "DEMAND") else 0.0)

        cap_k = float(inst.veiculos[k].capacidade)
        velocidade = float(inst.veiculos[k].velocidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def rota_para_binaria(rota):
            bin_xij = [0] * nbcd
            for v in rota:
                if 1 <= v <= nbcd:
                    bin_xij[v - 1] = 1
            return bin_xij
        """
        print("\n=== MATRIZ DE CUSTO REDUZIDO (delta_rc) ===")

        for i in range(nbn):

            linha = []

            for j in range(nbn):

                if i == j:
                    linha.append("   -   ")
                    continue

                # custo base
                rc = travel_time(i, j)

                # dual arco
                rc -= float(mu_arc.get((i, j), 0.0))

                # dual cliente
                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                # dual veiculo (igual sua lógica: só ao fechar)
                if j == depf:
                    rc -= float(sigma_k)

                linha.append(f"{rc:7.2f}")

            print(f"i={i:2d} | " + " ".join(linha))

        print("==========================================\n")
        """


        def escolhe_janela_viavel(no_i, tempo_fim_i, j):
            """
            tempo_fim_i = instante em que o serviço terminou no nó i
            retorna:
                (inicio_servico_j, fim_servico_j, idx_janela)
            ou None se j for inviável em todas as janelas
            """
            chegada_j = tempo_fim_i + travel_time(no_i, j)

            melhor = None
            for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                inicio_servico_j = max(chegada_j, aj)
                fim_servico_j = inicio_servico_j + sj

                # serviço deve começar dentro da janela
                # se no seu modelo o serviço precisa TERMINAR dentro da janela,
                # troque por: if fim_servico_j <= bj + 1e-9:
                if inicio_servico_j <= bj + 1e-9:
                    melhor = (inicio_servico_j, fim_servico_j, idx_janela)
                    break

            return melhor

        def score_candidato(no_i, j, delta_rc, tempo_atual, nova_carga):
            """
            Quanto menor, melhor.
            Mistura custo reduzido do arco com informação de futuro.
            """
            # chegada em j
            chegada_j = tempo_atual + travel_time(no_i, j)

            # melhor janela em j
            melhor_janela = escolhe_janela_viavel(no_i, tempo_atual, j)
            if melhor_janela is None:
                return math.inf

            inicio_servico_j, fim_servico_j, idx_janela = melhor_janela

            # custo para voltar ao depósito final
            rc_fecho = travel_time(j, depf) - mu(j, depf) - float(sigma_k)

            # folga temporal na janela escolhida
            aj, bj, sj = janelas[j][idx_janela]
            folga = bj - inicio_servico_j

            # ocupação da capacidade
            ocup = nova_carga / max(cap_k, 1.0)

            # score combinado
            score = (
                    1.0 * delta_rc +  # custo reduzido imediato
                    0.25 * rc_fecho +  # facilidade de fechar
                    0.02 * fim_servico_j +  # penaliza tempos tardios
                    2.0 * ocup -  # empurra a usar capacidade
                    0.01 * folga  # prefere mais folga
            )

            return score


        # melhor solução encontrada
        melhor_rota = None
        melhor_custo_real = None
        melhor_custo_red = math.inf

        # =========================================================
        # PRE-CÁLCULO: custo reduzido e vizinhos já ordenados
        # =========================================================
        rc = [[math.inf] * nbn for _ in range(nbn)]
        vizinhos_ordenados = [[] for _ in range(nbn)]

        for i in range(nbn):
            linha = []

            for j in range(nbn):
                if i == j:
                    continue

                val = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    val -= float(pi[j - 1])

                if j == depf:
                    val -= float(sigma_k)

                rc[i][j] = val
                linha.append((j, val))

            linha.sort(key=lambda x: x[1])
            vizinhos_ordenados[i] = linha

        # =========================================================
        # MULTI-START RANDOMIZADO
        # =========================================================
        for ii in range(n_starts):

            rota = [dep0]
            visitados = {dep0}
            no_atual = dep0

            # estado temporal = fim de serviço no nó atual
            # depósito inicial: pega a primeira janela viável, se houver
            a0, b0, s0 = janelas[dep0][0]
            inicio_servico_0 = max(0.0, a0)
            if inicio_servico_0 > b0 + 1e-9:
                return None, None
            tempo_atual = inicio_servico_0 + s0

            carga_atual = 0.0
            custo_red_total = 0.0

            # opcional: guardar janela usada em cada nó
            janelas_escolhidas = [0]

            while True:
                viaveis = []

                top_k = random.randint(2, min(7, nbcd))
                for (j, delta_rc) in vizinhos_ordenados[no_atual]:

                    if j in visitados:
                        continue

                    #aqui vou colocar o

                    if NO_BP.tabu_until[k][no_atual][j] > 0:
                        print(f"nó tabu {no_atual}-{j}")

                    # tabu
                    """
                    if NO_BP is not None and hasattr(NO_BP, "tabu_until"):
                        if NO_BP.tabu_until[k][no_atual][j] > 0:
                            continue
                    """

                    nova_carga = carga_atual + (d[j] if 1 <= j <= nbcd else 0.0)
                    if nova_carga > cap_k + 1e-9:
                        continue

                    janela_viavel = escolhe_janela_viavel(no_atual, tempo_atual, j)
                    if janela_viavel is None:
                        #print(f"janela inviavel para {j}")
                        continue

                    inicio_servico_j, fim_servico_j, idx_janela = janela_viavel

                    score = score_candidato(no_atual, j, delta_rc, tempo_atual, nova_carga)

                    viaveis.append((
                        j,
                        inicio_servico_j,
                        fim_servico_j,
                        nova_carga,
                        delta_rc,
                        idx_janela,
                        score
                    ))


                if not viaveis:
                    break

                viaveis.sort(key=lambda x: x[6])
                viaveis = viaveis[:top_k]

                #escolha enviesada

                j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela,score =(
                    self.escolhe_vizinho_enviesado(viaveis,alpha=0.55))
                #j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela = random.choice(viaveis)
                # j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela = viaveis[0]

                rota.append(j)
                janelas_escolhidas.append(idx_janela)

                custo_red_total += delta_rc
                tempo_atual = fim_servico_j
                carga_atual = nova_carga
                no_atual = j

                visitados.add(j)

                if j == depf:
                    break

            # rota fechada com pelo menos 1 cliente
            if len(rota) >= 3 and rota[-1] == depf:
                custo_real = 0.0
                for t in range(len(rota) - 1):
                    custo_real += travel_time(rota[t], rota[t + 1])

                if custo_red_total < melhor_custo_red:
                    melhor_custo_red = custo_red_total
                    melhor_custo_real = custo_real
                    melhor_rota = rota[:]

            if melhor_rota is not None and melhor_custo_red < -eps:
                return {
                    "clientes": melhor_rota,
                    "custo": melhor_custo_real,
                    "bin_xij": rota_para_binaria(melhor_rota)
                }, melhor_custo_red
            else:
                if len(rota) >= 3 and rota[-1] == depf:
                    #print(f"melhora uma vez custo antigo red {rota}= {custo_red_total}")
                    rota_melhorada, custo_red_melhorado, custo_real_melhorado,janelas_melhoradas  = self.busca_local_rota(
                        rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                    )
                    #print(f"melhora uma vez custo novo red {rota_melhorada}= {custo_red_melhorado}")
                    if rota_melhorada is not None and custo_red_melhorado < -eps:
                        #print(f"heuristica deu boa patrão rota {rota_melhorada}- custor= {custo_red_melhorado}")
                        return {
                            "clientes": rota_melhorada,
                            "custo": custo_real_melhorado,
                            "bin_xij": rota_para_binaria(rota_melhorada)
                        }, custo_red_melhorado
                        print("")

                    """
                    if ii >= n_starts -2 and self.tabb==0:
                        print("FORÇADO!!!")
                        self.tabb=1
                        print("")
                        rota_forcada=[0,6,5,8,7,11,10,14]
                        custo_real= 0.0

                        for t in range (len(rota_forcada)-1):
                            custo_real+=travel_time(rota_forcada[t],rota_forcada[t+1])

                        custo_red=0.0
                        for t in range (len(rota_forcada)-1):
                            i=rota_forcada[t]
                            j=rota_forcada[t+1]

                            rc = travel_time(i,j)
                            rc -=mu(i,j)

                            if 1<=j<=nbcd:
                                rc-= float(pi[j-1])

                            if  j==depf:
                                rc-=float(sigma_k)

                            custo_red+= rc
                            print(f"CR {custo_red}")
                        print("ROTA FORÇADA:", rota_forcada)
                        print("custo_real =", custo_real)
                        print("custo_red =", custo_red)
                        print("")
                        return {
                            "clientes": rota_forcada,
                            "custo": custo_real,
                            "bin_xij": rota_para_binaria(rota_forcada)
                        }, custo_red

                        print("")
                    else:
                        if ii >= n_starts - 2 and self.tabb==1:
                            print("")
                            rota_forcada = [0, 1, 9, 3, 12, 4, 2, 13,14]
                            custo_real = 0.0

                            for t in range(len(rota_forcada) - 1):
                                custo_real += travel_time(rota_forcada[t], rota_forcada[t + 1])

                            custo_red = 0.0
                            for t in range(len(rota_forcada) - 1):
                                i = rota_forcada[t]
                                j = rota_forcada[t + 1]

                                rc = travel_time(i, j)
                                rc -= mu(i, j)

                                if 1 <= j <= nbcd:
                                    rc -= float(pi[j - 1])

                                if j == depf:
                                    rc -= float(sigma_k)

                                custo_red += rc
                                print(f"CR {custo_red}")
                            print("ROTA FORÇADA:", rota_forcada)
                            print("custo_real =", custo_real)
                            print("custo_red =", custo_red)
                            print("")
                            return {
                                "clientes": rota_forcada,
                                "custo": custo_real,
                                "bin_xij": rota_para_binaria(rota_forcada)
                            }, custo_red

                            print("")
                    
                    """

                #print("NAO RETORNOU COLUNA-GERA NOVA")
                #print(ii)

        return None, None

    def busca_local_rota(self, rota, inst, pi, sigma_k, k, mu_arc, janelas, d,
                         eps=1e-6, max_perturb=5):
        import math
        import random

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        velocidade = float(inst.veiculos[k].velocidade)
        cap_k = float(inst.veiculos[k].capacidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def custo_reduzido_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                i = rota_av[t]
                j = rota_av[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def custo_real_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                val += travel_time(rota_av[t], rota_av[t + 1])
            return val

        def verifica_viabilidade(rota_av):
            if not rota_av or rota_av[0] != dep0 or rota_av[-1] != depf:
                return False, None, None, None

            visitados = set()
            carga = 0.0

            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota_av)):
                i = rota_av[pos - 1]
                j = rota_av[pos]

                if 1 <= j <= nbcd:
                    if j in visitados:
                        return False, None, None, None
                    visitados.add(j)

                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    # se quiser término dentro da janela, troque a linha abaixo
                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def gera_relocate(rota_base):
            vizinhas = []
            for i in range(1, len(rota_base) - 1):
                cliente = rota_base[i]
                if cliente == depf:
                    continue

                base_sem = rota_base[:i] + rota_base[i + 1:]

                for j in range(1, len(base_sem)):
                    nova = base_sem[:j] + [cliente] + base_sem[j:]
                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)
            return vizinhas

        def gera_swap(rota_base):
            vizinhas = []
            for i in range(1, len(rota_base) - 2):
                for j in range(i + 1, len(rota_base) - 1):
                    if rota_base[i] == depf or rota_base[j] == depf:
                        continue
                    nova = rota_base[:]
                    nova[i], nova[j] = nova[j], nova[i]
                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)
            return vizinhas

        def gera_2opt(rota_base):
            vizinhas = []
            # não mexe no dep0 nem no depf
            for i in range(1, len(rota_base) - 3):
                for j in range(i + 1, len(rota_base) - 1):
                    nova = rota_base[:i] + list(reversed(rota_base[i:j + 1])) + rota_base[j + 1:]
                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)
            return vizinhas

        def gera_oropt2(rota_base):
            vizinhas = []
            # move bloco de 2 clientes
            for i in range(1, len(rota_base) - 2):
                bloco = rota_base[i:i + 2]
                if depf in bloco:
                    continue

                base_sem = rota_base[:i] + rota_base[i + 2:]

                for j in range(1, len(base_sem)):
                    nova = base_sem[:j] + bloco + base_sem[j:]
                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)
            return vizinhas

        def melhor_vizinho(vizinhas, melhor_atual):
            melhor_cand = None
            melhor_custo = melhor_atual
            melhor_real = None
            melhor_janelas = None

            for cand in vizinhas:
                viavel, cand_janelas, _, _ = verifica_viabilidade(cand)
                if not viavel:
                    continue

                cand_custo = custo_reduzido_rota(cand)
                if cand_custo < melhor_custo - eps:
                    melhor_cand = cand
                    melhor_custo = cand_custo
                    melhor_real = custo_real_rota(cand)
                    melhor_janelas = cand_janelas

            return melhor_cand, melhor_custo, melhor_real, melhor_janelas

        def perturbacao(rota_base):
            if len(rota_base) <= 4:
                return rota_base[:]

            nova = rota_base[:]
            i = random.randint(1, len(nova) - 3)
            j = random.randint(1, len(nova) - 3)
            while j == i:
                j = random.randint(1, len(nova) - 3)

            nova[i], nova[j] = nova[j], nova[i]
            return nova

        if rota is None:
            return None, math.inf, math.inf, None

        melhor_rota_global = rota[:]
        viavel, melhor_janelas_global, _, _ = verifica_viabilidade(melhor_rota_global)
        if not viavel:
            return rota, math.inf, math.inf, None

        melhor_custo_red_global = custo_reduzido_rota(melhor_rota_global)
        melhor_custo_real_global = custo_real_rota(melhor_rota_global)

        rota_corrente = melhor_rota_global[:]
        custo_corrente = melhor_custo_red_global
        real_corrente = melhor_custo_real_global
        janelas_corrente = melhor_janelas_global

        n_pert = 0
        while n_pert <= max_perturb:
            melhorou = True

            while melhorou:
                melhorou = False

                # VND: relocate -> swap -> 2opt -> oropt2
                estruturas = [
                    gera_relocate,
                    gera_swap,
                    gera_2opt,
                    gera_oropt2
                ]

                for gerador in estruturas:
                    vizinhas = gerador(rota_corrente)
                    cand, cand_custo, cand_real, cand_janelas = melhor_vizinho(vizinhas, custo_corrente)

                    if cand is not None:
                        rota_corrente = cand
                        custo_corrente = cand_custo
                        real_corrente = cand_real
                        janelas_corrente = cand_janelas
                        melhorou = True

                        if custo_corrente < melhor_custo_red_global - eps:
                            melhor_rota_global = rota_corrente[:]
                            melhor_custo_red_global = custo_corrente
                            melhor_custo_real_global = real_corrente
                            melhor_janelas_global = janelas_corrente

                        break

            # travou: tenta perturbar
            n_pert += 1
            rota_pert = perturbacao(melhor_rota_global)
            viavel, janelas_pert, _, _ = verifica_viabilidade(rota_pert)

            if viavel:
                custo_pert = custo_reduzido_rota(rota_pert)
                real_pert = custo_real_rota(rota_pert)

                rota_corrente = rota_pert
                custo_corrente = custo_pert
                real_corrente = real_pert
                janelas_corrente = janelas_pert
            else:
                rota_corrente = melhor_rota_global[:]
                custo_corrente = melhor_custo_red_global
                real_corrente = melhor_custo_real_global
                janelas_corrente = melhor_janelas_global

        return melhor_rota_global, melhor_custo_red_global, melhor_custo_real_global, melhor_janelas_global

    def busca_local_rotaMIOPE(self, rota, inst, pi, sigma_k, k, mu_arc, janelas, d, eps=1e-6):
        import math

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        velocidade = float(inst.veiculos[k].velocidade)
        cap_k = float(inst.veiculos[k].capacidade)

        def travel_time(i, j):
            return float(inst.matriz_distancia[i][j]) / velocidade

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        def custo_reduzido_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                i = rota_av[t]
                j = rota_av[t + 1]

                rc = travel_time(i, j) - mu(i, j)

                if 1 <= j <= nbcd:
                    rc -= float(pi[j - 1])

                if j == depf:
                    rc -= float(sigma_k)

                val += rc
            return val

        def custo_real_rota(rota_av):
            val = 0.0
            for t in range(len(rota_av) - 1):
                val += travel_time(rota_av[t], rota_av[t + 1])
            return val

        def verifica_viabilidade(rota_av):
            """
            Retorna:
                (True, janelas_escolhidas, tempo_final, carga_final)
            ou
                (False, None, None, None)
            """
            if not rota_av or rota_av[0] != dep0 or rota_av[-1] != depf:
                return False, None, None, None

            visitados = set()
            carga = 0.0

            # depósito inicial
            a0, b0, s0 = janelas[dep0][0]
            inicio0 = max(0.0, a0)
            if inicio0 > b0 + 1e-9:
                return False, None, None, None

            tempo = inicio0 + s0
            janelas_escolhidas = [0]

            for pos in range(1, len(rota_av)):
                i = rota_av[pos - 1]
                j = rota_av[pos]

                # não pode repetir cliente
                if 1 <= j <= nbcd:
                    if j in visitados:
                        return False, None, None, None
                    visitados.add(j)

                # capacidade
                if 1 <= j <= nbcd:
                    carga += d[j]
                    if carga > cap_k + 1e-9:
                        return False, None, None, None

                chegada_j = tempo + travel_time(i, j)

                achou = False
                for idx_janela, (aj, bj, sj) in enumerate(janelas[j]):
                    inicio_servico_j = max(chegada_j, aj)
                    fim_servico_j = inicio_servico_j + sj

                    # se seu modelo exigir término dentro da janela, troque para:
                    # if fim_servico_j <= bj + 1e-9:
                    if inicio_servico_j <= bj + 1e-9:
                        tempo = fim_servico_j
                        janelas_escolhidas.append(idx_janela)
                        achou = True
                        break

                if not achou:
                    return False, None, None, None

            return True, janelas_escolhidas, tempo, carga

        def gera_relocate(rota_base):
            vizinhas = []
            # não mexe no depósito inicial nem final
            for i in range(1, len(rota_base) - 1):
                cliente = rota_base[i]

                # normalmente não faz sentido mover o depósito final
                if cliente == depf:
                    continue

                base_sem = rota_base[:i] + rota_base[i + 1:]

                for j in range(1, len(base_sem)):
                    nova = base_sem[:j] + [cliente] + base_sem[j:]

                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)

            return vizinhas

        def gera_swap(rota_base):
            vizinhas = []
            for i in range(1, len(rota_base) - 2):
                for j in range(i + 1, len(rota_base) - 1):
                    # não troca depósito
                    if rota_base[i] == depf or rota_base[j] == depf:
                        continue

                    nova = rota_base[:]
                    nova[i], nova[j] = nova[j], nova[i]

                    if nova[0] == dep0 and nova[-1] == depf:
                        vizinhas.append(nova)

            return vizinhas

        melhor_rota = rota[:]
        viavel, melhor_janelas, _, _ = verifica_viabilidade(melhor_rota)
        if not viavel:
            return rota, math.inf, math.inf, None

        melhor_custo_red = custo_reduzido_rota(melhor_rota)
        melhor_custo_real = custo_real_rota(melhor_rota)

        melhorou = True
        while melhorou:
            melhorou = False

            # 1) Relocate
            candidatos = gera_relocate(melhor_rota)
            for cand in candidatos:
                viavel, cand_janelas, _, _ = verifica_viabilidade(cand)
                if not viavel:
                    continue

                cand_custo_red = custo_reduzido_rota(cand)
                if cand_custo_red < melhor_custo_red - eps:
                    melhor_rota = cand
                    melhor_janelas = cand_janelas
                    melhor_custo_red = cand_custo_red
                    melhor_custo_real = custo_real_rota(cand)
                    melhorou = True
                    break

            if melhorou:
                continue

            # 2) Swap
            candidatos = gera_swap(melhor_rota)
            for cand in candidatos:
                viavel, cand_janelas, _, _ = verifica_viabilidade(cand)
                if not viavel:
                    continue

                cand_custo_red = custo_reduzido_rota(cand)
                if cand_custo_red < melhor_custo_red - eps:
                    melhor_rota = cand
                    melhor_janelas = cand_janelas
                    melhor_custo_red = cand_custo_red
                    melhor_custo_real = custo_real_rota(cand)
                    melhorou = True
                    break

        return melhor_rota, melhor_custo_red, melhor_custo_real, melhor_janelas


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
                    #print("PROIBIDO viola arco proibido")
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
                #print("PROIBIDa COlujna não respeita arco obrigatorio")
                return False  # não respeita arco obrigatório

        return True

    def resolver_no_com_poolRAIZz(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL NORMALZITO ---")

        # ===== flags p/ controller global =====
        no_bp.cg_convergiu = False
        no_bp.parou_por_max_iter = False
        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = False
        no_bp.lp_status = None

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)

        # Para duais estáveis
        model.setParam("Method", 1)  # dual simplex
        model.setParam("Crossover", 1)

        EPS_RC = 1e-6
        max_iter_cg = 500  # enquanto depura
        BIGM_ARC = 1e6
        BIGM_VIS = 1e6

        # -------------------------
        # helpers
        # -------------------------
        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])

        # =========================
        # 1) Variáveis λ (ub=0 se coluna incompatível com nó)
        # =========================
        lbd = {k: [] for k in sol_pool.rotas.keys()}

        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0, ub=ub, obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}"
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) VISITA ÚNICA com SLACK (Phase I por cobertura)
        #    expr + s_i == 1
        # =========================
        visita_constr = []
        slack_vis = []

        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                for p in range(n):
                    expr += lbd[k][p] * float(sol_pool.rotas[k]["rotas_binaria"][p][i])

            s = model.addVar(lb=0.0, obj=BIGM_VIS, vtype=GRB.CONTINUOUS, name=f"slack_vis_{i}")
            slack_vis.append(s)
            c = model.addConstr(expr + s == 1.0, name=f"visita_{i}")
            visita_constr.append(c)

        # =========================
        # 3) 1 rota por veículo (sem slack)
        # =========================
        uma_rota_constr = {}
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Arcos do nó (proibidos == 0; fixados == 1 com SLACK)
        # =========================
        constr_arco = {}  # (k,i,j) -> Constr
        slack_arc = {}  # (k,i,j) -> Var

        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}

            if fixados_k or proibidos_k:
                print(f"[Nó {no_bp.id_no}] k={k} fixados_k={fixados_k} proibidos_k={proibidos_k}")

            branch_arcs_k = set(proibidos_k) | set(fixados_k)
            if not branch_arcs_k:
                continue

            nrotas = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * lbd[k][p]

                if (i, j) in proibidos_k:
                    # aqui começa um primeiro teste onde quero testar colocar um -s para o lado esquerdo do nó,
                    # vou usar o mesmo para depois eu ver se ele zera (para ser viável)
                    s = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = s
                    constr_arco[(k, i, j)] = model.addConstr(expr - s == 0.0, name=f"arc_{k}_{i}_{j}")


                else:
                    smenos = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc2_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = smenos
                    constr_arco[(k, i, j)] = model.addConstr(expr + smenos == 1.0, name=f"arc_{k}_{i}_{j}")

        model.update()

        # >>> logo no começo da resolver_no_com_poolRAIZz, depois do print inicial:
        pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}
        # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)
        print("")

        # -------------------------
        # helper: adiciona λ no modelo com coluna (inclui visita/1rota/arcos)
        # -------------------------
        def add_lambda_var_model(k, idx_pool, seq_nova, rota_binaria, custo_original):
            constrs, coefs = [], []

            # visita (com slack, mas coef só das lambdas)
            for i in range(inst.nbcd):
                constrs.append(visita_constr[i])
                coefs.append(float(rota_binaria[i]))

            # 1 rota por veículo
            constrs.append(uma_rota_constr[k])
            coefs.append(1.0)

            # arcos do nó (somente do veículo k)
            for (kk, i, j), con in constr_arco.items():
                if kk != k:
                    continue
                constrs.append(con)
                coefs.append(float(rota_usa_arco(seq_nova, i, j)))

            col = gp.Column(coefs, constrs)
            v = model.addVar(
                lb=0.0, ub=1.0, obj=float(custo_original),
                vtype=GRB.CONTINUOUS,
                name=f"lambda_{k}_{idx_pool}",
                column=col
            )
            lbd[k].append(v)

        # =========================
        # LOOP CG (correto): solve -> pricing (todos k) -> adiciona lote -> solve
        # =========================
        iter_cg = 0
        while True:
            model.optimize()
            no_bp.lp_status = model.Status

            if model.Status != GRB.OPTIMAL:
                # com slack_vis + slack_arc, aqui só cai se houver problema numérico/estrutural
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            print(
                f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj = {model.ObjVal:.4f} |CONSTRUTIVA CANCELADA = {inst.nbconstrutiva} Colunas = {sum(len(lbd[k]) for k in lbd)}")

            slack_sum_vis = sum(float(v.X) for v in slack_vis)
            slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
            slack_sum_total = slack_sum_vis + slack_sum_arc

            if slack_sum_total > 1e-9:
                print(
                    f"[Nó {no_bp.id_no}] slack_total={slack_sum_total:.6f} (vis={slack_sum_vis:.6f}, arc={slack_sum_arc:.6f})")

            # duais
            pi = [float(c.Pi) for c in visita_constr]
            sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

            # mu_arc por k (duais das arc_{k,i,j})
            mu_arc_por_k = {k: {} for k in sol_pool.rotas.keys()}
            if constr_arco:
                cons_by_k = {k: [] for k in sol_pool.rotas.keys()}
                keys_by_k = {k: [] for k in sol_pool.rotas.keys()}
                for (k, i, j), con in constr_arco.items():
                    cons_by_k[k].append(con)
                    keys_by_k[k].append((i, j))

                for k in sol_pool.rotas.keys():
                    if not cons_by_k[k]:
                        continue
                    try:
                        pis = model.getAttr("Pi", cons_by_k[k])
                        for (i, j), pi_ in zip(keys_by_k[k], pis):
                            mu_arc_por_k[k][(i, j)] = float(pi_)
                    except gp.GurobiError:
                        mu_arc_por_k[k] = {}

            # pricing para todos k
            novas_colunas = []

            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)

                mu_arc = mu_arc_por_k.get(k, {})

                # emergência: se há slack e há fixados, tenta gerar rota que respeite fixados (aceita rc>=0)
                """
                if slack_sum_total > 1e-9 and fixados_k and tipo_geracao == "PD":
                    rota_emerg, _ = self.SUB_PROG_DIN(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc
                    )
                    if rota_emerg is not None:
                        seq = rota_emerg["clientes"]
                        if self.coluna_respeita_no(no_bp, seq, k):
                            novas_colunas.append((k, seq, rota_emerg["bin_xij"], rota_emerg["custo"]))
                            continue
                """

                # pricing normal
                t0 = time.time()
                if tipo_geracao == "PD":
                    # nova_rota, custo_red = self.SUB_PROG_DINCPP(
                    nova_rota, custo_red = self.SUB_PROG_DIN(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc
                    )
                else:
                    nova_rota, custo_red = self.subproblema(inst, pi, sigma[k], k, duais_arcos=None)

                """
                t1=time.time()
                if tipo_geracao == "PD":
                    nova_rotac, custo_redc = self.SUB_PROG_DINCPP(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc
                    )
                print("t python : "+str(t1-t0 ))
                if(nova_rotac!=nova_rota):
                    print("Diferentes ROTAC")
                    print(nova_rotac)
                    print("ROTA PY")
                    print(nova_rotac)
                    print("")
                """

                if nova_rota is None:
                    continue

                if float(custo_red) < -EPS_RC:
                    seq = nova_rota["clientes"]
                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue
                    novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"]))

            # convergência
            if not novas_colunas:
                no_bp.cg_convergiu = True
                break

            print("t C : " + str(time.time() - t0))
            print("NOVA ROTA ", nova_rota)
            print("CUSTO R" + str(custo_red))

            # adiciona lote e repete
            for (k, seq, binx, custo) in novas_colunas:
                idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                add_rota_no_pool(k, seq, binx, custo)
                add_lambda_var_model(k, idx_pool, seq, binx, custo)

            model.update()

            iter_cg += 1
            if iter_cg >= max_iter_cg:
                no_bp.parou_por_max_iter = True
                no_bp.cg_convergiu = False
                break

        # =========================
        # Final do nó
        # =========================
        model.optimize()
        no_bp.lp_status = model.Status
        if model.Status != GRB.OPTIMAL:
            no_bp.custo_lp = None
            no_bp.solucao_inteira = False
            no_bp.lambdas = {}
            return

        slack_sum_vis = sum(float(v.X) for v in slack_vis)
        slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
        no_bp.slack_sum_final = slack_sum_vis + slack_sum_arc

        # LB confiável só se convergiu e slack zerou
        no_bp.lb_confiavel = (no_bp.cg_convergiu and (no_bp.slack_sum_final <= 1e-9) and (not no_bp.parou_por_max_iter))

        no_bp.custo_lp = float(model.ObjVal)

        # lambdas + integrality
        lambdas = {}
        inteira = True
        tol = 1e-6

        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                lambdas[(k, p)] = val
                if val > tol and abs(val - 1.0) > tol:
                    inteira = False

        no_bp.lambdas = lambdas
        no_bp.solucao_inteira = inteira

        # arc_score = soma dos lambdas por arco (para branching)
        arc_score = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lam = float(lbd[k][p].X)
                if lam <= 1e-12:
                    continue
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    arc_score[(i, j, k)] = arc_score.get((i, j, k), 0.0) + lam
        no_bp.arc_score = arc_score

        print(
            f"Nó {no_bp.id_no} finalizado: LP={no_bp.custo_lp:.4f}, "
            f"inteira? {no_bp.solucao_inteira}, cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, slack_final={no_bp.slack_sum_final:.6f}, "
            f"lb_confiavel={no_bp.lb_confiavel}"
        )

    def resolver_no_com_pool_semSlack(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL SEM SLACK ---")

        # ===== flags p/ controller global =====
        no_bp.cg_convergiu = False
        no_bp.parou_por_max_iter = False
        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = False
        no_bp.lp_status = None
        no_bp.custo_lp = None
        no_bp.custo_mip = None
        no_bp.solucao_inteira = False
        no_bp.lambdas = {}
        no_bp.lambdas_inteiras = {}
        no_bp.arc_score = {}

        # contadores
        construtivas = [0, 0, 0, 0]

        N = inst.nbn
        K = inst.nbv

        # itens do tabu
        no_bp.freq_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.last_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.tabu_until = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)
        model.setParam("Method", 1)  # dual simplex
        model.setParam("Crossover", 1)

        EPS_RC = 1e-6
        max_iter_cg = 500

        # -------------------------
        # helpers
        # -------------------------
        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])

        # =========================
        # 1) Variáveis λ (ub=0 se coluna incompatível com nó)
        # =========================
        lbd = {k: [] for k in sol_pool.rotas.keys()}

        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0, ub=ub, obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}"
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) VISITA ÚNICA sem slack
        # =========================
        visita_constr = []

        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                for p in range(n):
                    expr += lbd[k][p] * float(sol_pool.rotas[k]["rotas_binaria"][p][i])

            c = model.addConstr(expr == 1.0, name=f"visita_{i}")
            visita_constr.append(c)

        # =========================
        # 3) 1 rota por veículo
        # =========================
        uma_rota_constr = {}
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Arcos do nó sem slack
        # =========================
        constr_arco = {}  # (k,i,j) -> Constr

        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}

            if fixados_k or proibidos_k:
                print(f"[Nó {no_bp.id_no}] k={k} fixados_k={fixados_k} proibidos_k={proibidos_k}")

            branch_arcs_k = set(proibidos_k) | set(fixados_k)
            if not branch_arcs_k:
                continue

            nrotas = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * lbd[k][p]

                if (i, j) in proibidos_k:
                    constr_arco[(k, i, j)] = model.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                else:
                    constr_arco[(k, i, j)] = model.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")

        model.update()

        # -------------------------
        # helper: adiciona λ no modelo com coluna
        # -------------------------
        def add_lambda_var_model(k, idx_pool, seq_nova, rota_binaria, custo_original):
            constrs, coefs = [], []

            # visita
            for i in range(inst.nbcd):
                constrs.append(visita_constr[i])
                coefs.append(float(rota_binaria[i]))

            # 1 rota por veículo
            constrs.append(uma_rota_constr[k])
            coefs.append(1.0)

            # arcos do nó
            for (kk, i, j), con in constr_arco.items():
                if kk != k:
                    continue
                constrs.append(con)
                coefs.append(float(rota_usa_arco(seq_nova, i, j)))

            col = gp.Column(coefs, constrs)
            v = model.addVar(
                lb=0.0, ub=1.0, obj=float(custo_original),
                vtype=GRB.CONTINUOUS,
                name=f"lambda_{k}_{idx_pool}",
                column=col
            )
            lbd[k].append(v)

        # -------------------------
        # helper: resolve MIP final com pool atual
        # -------------------------
        def resolver_mip_final_com_pool():
            mip = gp.Model(f"MIP_final_no_{no_bp.id_no}")
            mip.setParam("OutputFlag", 0)

            z = {k: [] for k in sol_pool.rotas.keys()}

            for k in sol_pool.rotas.keys():
                nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    custo = float(sol_pool.rotas[k]["custo"][p])

                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue

                    var = mip.addVar(
                        lb=0.0, ub=1.0,
                        obj=custo,
                        vtype=GRB.BINARY,
                        name=f"z_{k}_{p}"
                    )
                    z[k].append((p, var))

            mip.ModelSense = GRB.MINIMIZE
            mip.update()

            # visita única
            for i in range(inst.nbcd):
                expr = gp.LinExpr()
                for k in sol_pool.rotas.keys():
                    for p, var in z[k]:
                        expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
                mip.addConstr(expr == 1.0, name=f"visita_{i}")

            # uma rota por veículo
            for k in sol_pool.rotas.keys():
                expr = gp.LinExpr()
                for p, var in z[k]:
                    expr += var
                mip.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

            # arcos do nó
            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                branch_arcs_k = set(proibidos_k) | set(fixados_k)

                for (i, j) in branch_arcs_k:
                    expr = gp.LinExpr()
                    for p, var in z[k]:
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        expr += float(rota_usa_arco(seq, i, j)) * var

                    if (i, j) in proibidos_k:
                        mip.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                    else:
                        mip.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")

            mip.optimize()
            return mip, z

        # =========================
        # LOOP CG
        # =========================
        iter_cg = 0
        pi = None
        sigma = None
        mu_arc_por_k = None

        while True:
            model.optimize()
            no_bp.lp_status = model.Status

            if model.Status == GRB.INFEASIBLE:
                print(f"[Nó {no_bp.id_no}] RMP inviável com pool atual.")
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            print(
                f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj = {model.ObjVal:.4f} |CONSTRUTIVA CANCELADA = {inst.nbconstrutiva} Colunas = {sum(len(lbd[k]) for k in lbd)}")
            print(f"[Nó {no_bp.id_no}] Solução LP fracionada na iteração {iter_cg}:")

            tem_ativa = False
            valor_recomposto = 0.0
            tol_print = 1e-6

            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
                for p in range(n):
                    val = float(lbd[k][p].X)

                    if val > tol_print:
                        tem_ativa = True
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_recomposto += val * custo

                        print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

            if not tem_ativa:
                print("   nenhuma coluna ativa")

            print(f"   valor recomposto = {valor_recomposto:.6f}")
            print("")

            # duais
            pi = [float(c.Pi) for c in visita_constr]
            sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

            if no_bp.matriz_rc == {}:
                no_bp.criaMatriRC(inst)

            # mu_arc por k
            mu_arc_por_k = {k: {} for k in sol_pool.rotas.keys()}
            if constr_arco:
                cons_by_k = {k: [] for k in sol_pool.rotas.keys()}
                keys_by_k = {k: [] for k in sol_pool.rotas.keys()}
                for (k, i, j), con in constr_arco.items():
                    cons_by_k[k].append(con)
                    keys_by_k[k].append((i, j))

                for k in sol_pool.rotas.keys():
                    if not cons_by_k[k]:
                        continue
                    try:
                        pis = model.getAttr("Pi", cons_by_k[k])
                        for (i, j), pi_ in zip(keys_by_k[k], pis):
                            mu_arc_por_k[k][(i, j)] = float(pi_)
                    except gp.GurobiError:
                        mu_arc_por_k[k] = {}

            # pricing para todos k
            novas_colunas = []

            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)
                mu_arc = mu_arc_por_k.get(k, {})

                nova_rota, custo_red = self.SUB_VNSRANDOM(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if nova_rota is not None:
                    sol_pool.construtivas[0] += 1
                    print("gerou na 1")

                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_ALLBESTINSERTION(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[1] += 1
                        print("gerou na 2")

                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_VNS(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[2] += 1
                        print("gerou na 3")


                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_PROG_DIN_PW(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[3] += 1
                        print("gerou na 4")

                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_PROG_DIN(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[4] += 1
                        print("gerou na 5")

                if nova_rota is None:
                    print("PASSOU PELOS 5 sem gerar nada")
                    continue

                nova_rota["custo_reduzido"] = float(custo_red)
                print(f"NOVA COLUNA GERAL | rc={nova_rota['custo_reduzido']:.6f}")
                print(nova_rota)

                if float(custo_red) < -EPS_RC:
                    seq = nova_rota["clientes"]

                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue

                    novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"]))

                    print(f"NOVA COLUNA | rc={nova_rota['custo_reduzido']:.6f}")
                    print(nova_rota)
                    print("")

                    # atualiza tabu
                    mat = no_bp.tabu_until[k]
                    for i in range(inst.nbn):
                        row = mat[i]
                        for j in range(inst.nbn):
                            if row[j] > 0:
                                row[j] -= 1

                    for t in range(len(seq) - 1):
                        i, j = seq[t], seq[t + 1]
                        no_bp.freq_arc[k][i][j] += 1
                        no_bp.last_arc[k][i][j] = iter_cg
                        no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

                    print("")

            # convergência
            if not novas_colunas:
                no_bp.cg_convergiu = True
                break

            # adiciona lote e repete
            for (k, seq, binx, custo) in novas_colunas:
                idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                add_rota_no_pool(k, seq, binx, custo)
                add_lambda_var_model(k, idx_pool, seq, binx, custo)

            model.update()

            iter_cg += 1
            if iter_cg >= max_iter_cg:
                no_bp.parou_por_max_iter = True
                no_bp.cg_convergiu = False
                break

        # =========================
        # Final do nó - LP
        # =========================
        model.optimize()
        no_bp.lp_status = model.Status

        if model.Status != GRB.OPTIMAL:
            no_bp.custo_lp = None
            no_bp.solucao_inteira = False
            no_bp.lambdas = {}
            return

        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = (no_bp.cg_convergiu and (not no_bp.parou_por_max_iter))
        no_bp.custo_lp = float(model.ObjVal)

        # lambdas LP
        lambdas_lp = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lambdas_lp[(k, p)] = float(lbd[k][p].X)
        no_bp.lambdas = lambdas_lp

        print(f"[Nó {no_bp.id_no}] Melhor solução fracionada final (LP):")
        tem_lp = False
        valor_lp_recomposto = 0.0

        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                if val > 1e-6:
                    tem_lp = True
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    custo = float(sol_pool.rotas[k]["custo"][p])
                    valor_lp_recomposto += val * custo

                    print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

        if not tem_lp:
            print("   nenhuma coluna LP ativa")

        print(f"   valor LP recomposto = {valor_lp_recomposto:.6f}")
        print("")

        # arc_score = soma dos lambdas LP por arco
        arc_score = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lam = float(lbd[k][p].X)
                if lam <= 1e-12:
                    continue
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    arc_score[(i, j, k)] = arc_score.get((i, j, k), 0.0) + lam
        no_bp.arc_score = arc_score

        # =========================
        # MIP final com pool atual
        # =========================
        mip_final, z_final = resolver_mip_final_com_pool()

        no_bp.custo_mip = None
        no_bp.lambdas_inteiras = {}
        no_bp.solucao_inteira = False

        if mip_final.Status == GRB.OPTIMAL:
            no_bp.custo_mip = float(mip_final.ObjVal)
            no_bp.solucao_inteira = True

            lambdas_int = {}
            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    lambdas_int[(k, p)] = float(var.X)
            no_bp.lambdas_inteiras = lambdas_int

            print(f"[Nó {no_bp.id_no}] Lambdas da melhor solução inteira:")
            for (k, p), val in sorted(no_bp.lambdas_inteiras.items()):
                if val > 1e-6:
                    print(f"   lambda_int[{k},{p}] = {val:.0f}")
            print("")

            print(f"[Nó {no_bp.id_no}] Melhor solução inteira final (MIP no pool):")
            valor_int_recomposto = 0.0
            tem_int = False

            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    val = float(var.X)
                    if val > 1e-6:
                        tem_int = True
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_int_recomposto += val * custo

                        print(f"   veic={k} | col={p} | z={val:.0f} | custo={custo:.4f} | rota={seq}")

            if not tem_int:
                print("   nenhuma coluna inteira ativa")

            print(f"   valor inteiro recomposto = {valor_int_recomposto:.6f}")
            print("")
        else:
            print(f"[Nó {no_bp.id_no}] MIP final do pool inviável/sem solução ótima.")

        print(
            f"Nó {no_bp.id_no} finalizado: "
            f"LP={no_bp.custo_lp:.4f}, "
            f"MIP_pool={no_bp.custo_mip if no_bp.custo_mip is not None else 'None'}, "
            f"tem_inteira={no_bp.solucao_inteira}, "
            f"cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, "
            f"lb_confiavel={no_bp.lb_confiavel}"
        )

        # exporta solução inteira do MIP final
        if no_bp.solucao_inteira:
            selecao = []

            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    if float(var.X) > 1e-6:
                        selecao.append({
                            "k": k,
                            "p": p,
                            "nome": f"veic={k} col={p}"
                        })

            if selecao:
                mu_arc_total = {}
                if mu_arc_por_k is not None:
                    for kk in mu_arc_por_k:
                        for (i, j), val in mu_arc_por_k[kk].items():
                            mu_arc_total[(i, j, kk)] = float(val)

                if pi is None:
                    pi = [0.0 for _ in range(inst.nbcd)]
                if sigma is None:
                    sigma = {k: 0.0 for k in sol_pool.rotas.keys()}

                sol_pool.exportar_rotas_pares_js(
                    inst=inst,
                    selecao=selecao,
                    pi=pi,
                    mu_arc=mu_arc_total,
                    sigma=sigma,
                    nome_arquivo_js="rotas_plot_data.js",
                    title=f"Solução inteira do nó {no_bp.id_no}",
                    subtitle=f"Melhor inteira do pool | rotas ativas: {len(selecao)}"
                )

        print("SALDOS")
        print(construtivas)

        if no_bp.id_no == 0:
            pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}
            # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)
            print("PRIMEIRO NO")

    def resolver_no_com_pool2(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL NORMALZITO ---")

        # ===== flags p/ controller global =====
        no_bp.cg_convergiu = False
        no_bp.parou_por_max_iter = False
        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = False
        no_bp.lp_status = None
        no_bp.custo_lp = None
        no_bp.custo_mip = None
        no_bp.solucao_inteira = False
        no_bp.lambdas = {}
        no_bp.lambdas_inteiras = {}
        no_bp.arc_score = {}

        # contadores
        construtivas = [0, 0, 0, 0]

        N = inst.nbn
        K = inst.nbv

        # itens do tabu
        no_bp.freq_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.last_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.tabu_until = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)

        # Para duais estáveis
        model.setParam("Method", 1)
        model.setParam("Crossover", 1)

        EPS_RC = 1e-6
        max_iter_cg = 500
        BIGM_ARC = 1e6
        BIGM_VIS = 1e6

        # -------------------------
        # helpers
        # -------------------------
        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])

        def resolver_mip_final_com_pool():
            """
            MIP final SEM slack, usando somente colunas que respeitam o nó.
            """
            mip = gp.Model(f"MIP_final_no_{no_bp.id_no}")
            mip.setParam("OutputFlag", 0)

            z = {k: [] for k in sol_pool.rotas.keys()}

            for k in sol_pool.rotas.keys():
                nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    custo = float(sol_pool.rotas[k]["custo"][p])

                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue

                    var = mip.addVar(
                        lb=0.0, ub=1.0,
                        obj=custo,
                        vtype=GRB.BINARY,
                        name=f"z_{k}_{p}"
                    )
                    z[k].append((p, var))

            mip.ModelSense = GRB.MINIMIZE
            mip.update()

            # visita única sem slack
            for i in range(inst.nbcd):
                expr = gp.LinExpr()
                for k in sol_pool.rotas.keys():
                    for p, var in z[k]:
                        expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
                mip.addConstr(expr == 1.0, name=f"visita_{i}")

            # uma rota por veículo
            for k in sol_pool.rotas.keys():
                expr = gp.LinExpr()
                for p, var in z[k]:
                    expr += var
                mip.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

            # arcos do nó sem slack
            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                branch_arcs_k = set(proibidos_k) | set(fixados_k)

                for (i, j) in branch_arcs_k:
                    expr = gp.LinExpr()
                    for p, var in z[k]:
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        expr += float(rota_usa_arco(seq, i, j)) * var

                    if (i, j) in proibidos_k:
                        mip.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                    else:
                        mip.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")

            mip.optimize()
            return mip, z

        # =========================
        # 1) Variáveis λ (ub=0 se coluna incompatível com nó)
        # =========================
        lbd = {k: [] for k in sol_pool.rotas.keys()}

        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0, ub=ub, obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}"
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) VISITA ÚNICA com SLACK
        # =========================
        visita_constr = []
        slack_vis = []

        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                for p in range(n):
                    expr += lbd[k][p] * float(sol_pool.rotas[k]["rotas_binaria"][p][i])

            s = model.addVar(lb=0.0, obj=BIGM_VIS, vtype=GRB.CONTINUOUS, name=f"slack_vis_{i}")
            slack_vis.append(s)
            c = model.addConstr(expr + s == 1.0, name=f"visita_{i}")
            visita_constr.append(c)

        # =========================
        # 3) 1 rota por veículo
        # =========================
        uma_rota_constr = {}
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Arcos do nó com SLACK
        # =========================
        constr_arco = {}
        slack_arc = {}

        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}

            if fixados_k or proibidos_k:
                print(f"[Nó {no_bp.id_no}] k={k} fixados_k={fixados_k} proibidos_k={proibidos_k}")

            branch_arcs_k = set(proibidos_k) | set(fixados_k)
            if not branch_arcs_k:
                continue

            nrotas = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * lbd[k][p]

                if (i, j) in proibidos_k:
                    s = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = s
                    constr_arco[(k, i, j)] = model.addConstr(expr - s == 0.0, name=f"arc_{k}_{i}_{j}")
                else:
                    smenos = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc2_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = smenos
                    constr_arco[(k, i, j)] = model.addConstr(expr + smenos == 1.0, name=f"arc_{k}_{i}_{j}")

        model.update()

        # -------------------------
        # helper: adiciona λ no modelo com coluna
        # -------------------------
        def add_lambda_var_model(k, idx_pool, seq_nova, rota_binaria, custo_original):
            constrs, coefs = [], []

            for i in range(inst.nbcd):
                constrs.append(visita_constr[i])
                coefs.append(float(rota_binaria[i]))

            constrs.append(uma_rota_constr[k])
            coefs.append(1.0)

            for (kk, i, j), con in constr_arco.items():
                if kk != k:
                    continue
                constrs.append(con)
                coefs.append(float(rota_usa_arco(seq_nova, i, j)))

            col = gp.Column(coefs, constrs)
            v = model.addVar(
                lb=0.0, ub=1.0, obj=float(custo_original),
                vtype=GRB.CONTINUOUS,
                name=f"lambda_{k}_{idx_pool}",
                column=col
            )
            lbd[k].append(v)

        # =========================
        # LOOP CG
        # =========================
        iter_cg = 0
        pi = None
        sigma = None
        mu_arc_por_k = None

        while True:
            model.optimize()
            no_bp.lp_status = model.Status

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            print(
                f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj = {model.ObjVal:.4f} |CONSTRUTIVA CANCELADA = {inst.nbconstrutiva} Colunas = {sum(len(lbd[k]) for k in lbd)}")

            print(f"[Nó {no_bp.id_no}] Colunas ativas na iteração {iter_cg}:")
            tem_ativa = False
            valor_recomposto = 0.0
            tol_print = 1e-6

            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
                for p in range(n):
                    val = float(lbd[k][p].X)

                    if val > tol_print:
                        tem_ativa = True
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_recomposto += val * custo

                        print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

            if not tem_ativa:
                print("   nenhuma coluna ativa")

            print(f"   valor recomposto = {valor_recomposto:.6f}")
            print("")

            slack_sum_vis = sum(float(v.X) for v in slack_vis)
            slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
            slack_sum_total = slack_sum_vis + slack_sum_arc

            if slack_sum_total > 1e-9:
                print(
                    f"[Nó {no_bp.id_no}] slack_total={slack_sum_total:.6f} (vis={slack_sum_vis:.6f}, arc={slack_sum_arc:.6f})")

            # duais
            pi = [float(c.Pi) for c in visita_constr]
            sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

            if no_bp.matriz_rc == {}:
                no_bp.criaMatriRC(inst)

            # mu_arc por k
            mu_arc_por_k = {k: {} for k in sol_pool.rotas.keys()}
            if constr_arco:
                cons_by_k = {k: [] for k in sol_pool.rotas.keys()}
                keys_by_k = {k: [] for k in sol_pool.rotas.keys()}
                for (k, i, j), con in constr_arco.items():
                    cons_by_k[k].append(con)
                    keys_by_k[k].append((i, j))

                for k in sol_pool.rotas.keys():
                    if not cons_by_k[k]:
                        continue
                    try:
                        pis = model.getAttr("Pi", cons_by_k[k])
                        for (i, j), pi_ in zip(keys_by_k[k], pis):
                            mu_arc_por_k[k][(i, j)] = float(pi_)
                    except gp.GurobiError:
                        mu_arc_por_k[k] = {}

            novas_colunas = []

            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)
                mu_arc = mu_arc_por_k.get(k, {})

                t0 = time.time()

                nova_rota, custo_red = self.SUB_VNSRANDOM(inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc)
                if nova_rota is not None:
                    sol_pool.construtivas[0] += 1
                    print("gerou na 1")

                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_ALLBESTINSERTION(inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp,
                                                                          mu_arc=mu_arc)
                    if nova_rota is not None:
                        sol_pool.construtivas[1] += 1
                        print("gerou na 2")

                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_VNS(inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp,
                                                             mu_arc=mu_arc)
                    if nova_rota is not None:
                        sol_pool.construtivas[2] += 1
                        print("gerou na 3")


                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_PROG_DIN_PW(inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc)
                    if nova_rota is not None:
                        sol_pool.construtivas[3] += 1
                        print("gerou na 4")
                #"""

                if iter_cg == 13:
                    print("")

                if nova_rota is None:
                    print("PASSOU PELOS 3 sem gerar nada")
                    continue

                nova_rota["custo_reduzido"] = float(custo_red)
                print(f"NOVA COLUNA GERAL | rc={nova_rota['custo_reduzido']:.6f}")
                print(nova_rota)

                if float(custo_red) < -EPS_RC:
                    seq = nova_rota["clientes"]
                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue

                    novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"]))

                    print(f"NOVA COLUNA | rc={nova_rota['custo_reduzido']:.6f}")
                    print(nova_rota)
                    print("")

                    mat = no_bp.tabu_until[k]
                    for i in range(inst.nbn):
                        row = mat[i]
                        for j in range(inst.nbn):
                            if row[j] > 0:
                                row[j] -= 1

                    for t in range(len(seq) - 1):
                        i, j = seq[t], seq[t + 1]
                        no_bp.freq_arc[k][i][j] += 1
                        no_bp.last_arc[k][i][j] = iter_cg
                        no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

                    print("")

            if not novas_colunas:
                no_bp.cg_convergiu = True
                break

            for (k, seq, binx, custo) in novas_colunas:
                idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                add_rota_no_pool(k, seq, binx, custo)
                add_lambda_var_model(k, idx_pool, seq, binx, custo)

            model.update()

            iter_cg += 1
            if iter_cg >= max_iter_cg:
                no_bp.parou_por_max_iter = True
                no_bp.cg_convergiu = False
                break

        # =========================
        # Final do nó - LP com slack
        # =========================
        model.optimize()
        no_bp.lp_status = model.Status
        if model.Status != GRB.OPTIMAL:
            no_bp.custo_lp = None
            no_bp.solucao_inteira = False
            no_bp.lambdas = {}
            return

        slack_sum_vis = sum(float(v.X) for v in slack_vis)
        slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
        no_bp.slack_sum_final = slack_sum_vis + slack_sum_arc

        no_bp.lb_confiavel = (
                no_bp.cg_convergiu and
                (no_bp.slack_sum_final <= 1e-9) and
                (not no_bp.parou_por_max_iter)
        )

        no_bp.custo_lp = float(model.ObjVal)

        # lambdas LP
        lambdas_lp = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lambdas_lp[(k, p)] = float(lbd[k][p].X)
        no_bp.lambdas = lambdas_lp

        print(f"[Nó {no_bp.id_no}] Melhor solução fracionada final (LP com slack):")
        tem_lp = False
        valor_lp_recomposto = 0.0

        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                if val > 1e-6:
                    tem_lp = True
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    custo = float(sol_pool.rotas[k]["custo"][p])
                    valor_lp_recomposto += val * custo
                    print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

        if not tem_lp:
            print("   nenhuma coluna LP ativa")

        print(f"   valor LP recomposto = {valor_lp_recomposto:.6f}")
        print(f"   slack_final = {no_bp.slack_sum_final:.6f}")
        print("")

        # arc_score = soma dos lambdas LP por arco
        arc_score = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lam = float(lbd[k][p].X)
                if lam <= 1e-12:
                    continue
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    arc_score[(i, j, k)] = arc_score.get((i, j, k), 0.0) + lam
        no_bp.arc_score = arc_score

        # =========================
        # MIP final com pool atual (SEM slack)
        # =========================
        mip_final, z_final = resolver_mip_final_com_pool()

        no_bp.custo_mip = None
        no_bp.lambdas_inteiras = {}
        no_bp.solucao_inteira = False

        if mip_final.Status == GRB.OPTIMAL:
            no_bp.custo_mip = float(mip_final.ObjVal)
            no_bp.solucao_inteira = True

            lambdas_int = {}
            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    lambdas_int[(k, p)] = float(var.X)
            no_bp.lambdas_inteiras = lambdas_int

            print(f"[Nó {no_bp.id_no}] Lambdas da melhor solução inteira:")
            for (k, p), val in sorted(no_bp.lambdas_inteiras.items()):
                if val > 1e-6:
                    print(f"   lambda_int[{k},{p}] = {val:.0f}")
            print("")

            print(f"[Nó {no_bp.id_no}] Melhor solução inteira final (MIP no pool):")
            valor_int_recomposto = 0.0
            tem_int = False

            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    val = float(var.X)
                    if val > 1e-6:
                        tem_int = True
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_int_recomposto += val * custo
                        print(f"   veic={k} | col={p} | z={val:.0f} | custo={custo:.4f} | rota={seq}")

            if not tem_int:
                print("   nenhuma coluna inteira ativa")

            print(f"   valor inteiro recomposto = {valor_int_recomposto:.6f}")
            print("")
        else:
            print(f"[Nó {no_bp.id_no}] MIP final do pool inviável/sem solução ótima.")

        print(
            f"Nó {no_bp.id_no} finalizado: "
            f"LP={no_bp.custo_lp:.4f}, "
            f"MIP_pool={no_bp.custo_mip if no_bp.custo_mip is not None else 'None'}, "
            f"tem_inteira={no_bp.solucao_inteira}, "
            f"cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, "
            f"slack_final={no_bp.slack_sum_final:.6f}, "
            f"lb_confiavel={no_bp.lb_confiavel}"
        )

        # exporta a solução inteira do MIP final
        if no_bp.solucao_inteira:
            selecao = []

            for k in sol_pool.rotas.keys():
                for p, var in z_final[k]:
                    if float(var.X) > 1e-6:
                        selecao.append({
                            "k": k,
                            "p": p,
                            "nome": f"veic={k} col={p}"
                        })

            if selecao:
                mu_arc_total = {}
                if mu_arc_por_k is not None:
                    for kk in mu_arc_por_k:
                        for (i, j), val in mu_arc_por_k[kk].items():
                            mu_arc_total[(i, j, kk)] = float(val)

                if pi is None:
                    pi = [0.0 for _ in range(inst.nbcd)]
                if sigma is None:
                    sigma = {k: 0.0 for k in sol_pool.rotas.keys()}

                sol_pool.exportar_rotas_pares_js(
                    inst=inst,
                    selecao=selecao,
                    pi=pi,
                    mu_arc=mu_arc_total,
                    sigma=sigma,
                    nome_arquivo_js="rotas_plot_data.js",
                    title=f"Solução inteira do nó {no_bp.id_no}",
                    subtitle=f"Melhor inteira do pool | rotas ativas: {len(selecao)}"
                )

        print("SALDOS")
        print(construtivas)

        if no_bp.id_no == 0:
            pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}
            # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)
            print("PRIMEIRO NO")

    def resolver_no_com_pool(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB
        tentativasLP=0

        rodadas_sem_melhoria=0
        nmaxrodadas_sem_melhoria=inst.iteraSemMelhora
        colunas_reais_usadas=False
        ULTIMAFO=-1

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL NORMALZITO ---")

        # ===== flags p/ controller global =====
        no_bp.cg_convergiu = False
        no_bp.parou_por_max_iter = False
        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = False
        no_bp.lp_status = None
        no_bp.custo_lp = None
        no_bp.custo_mip = None
        no_bp.solucao_inteira = False
        no_bp.lambdas = {}
        no_bp.lambdas_inteiras = {}
        no_bp.arc_score = {}

        # contadores
        sol_pool.construtivas = [0, 0, 0, 0,0,0,0]

        N = inst.nbn
        K = inst.nbv

        # itens do tabu
        no_bp.freq_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.last_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.tabu_until = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)

        # Para duais estáveis
        model.setParam("Method", 1)
        model.setParam("Crossover", 1)

        EPS_RC = 1e-6
        max_iter_cg = 500
        BIGM_ARC = 1e6
        BIGM_VIS = 1e6

        # -------------------------
        # helpers
        # -------------------------
        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])

        # =========================
        # 1) Variáveis λ (ub=0 se coluna incompatível com nó)
        # =========================
        lbd = {k: [] for k in sol_pool.rotas.keys()}

        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0, ub=ub, obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}"
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) VISITA ÚNICA com SLACK
        # =========================
        visita_constr = []
        slack_vis = []

        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                for p in range(n):
                    expr += lbd[k][p] * float(sol_pool.rotas[k]["rotas_binaria"][p][i])

            s = model.addVar(lb=0.0, obj=BIGM_VIS, vtype=GRB.CONTINUOUS, name=f"slack_vis_{i}")
            slack_vis.append(s)
            c = model.addConstr(expr + s == 1.0, name=f"visita_{i}")
            visita_constr.append(c)

        # =========================
        # 3) 1 rota por veículo
        # =========================
        uma_rota_constr = {}
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Arcos do nó com SLACK
        # =========================
        constr_arco = {}
        slack_arc = {}

        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}

            if fixados_k or proibidos_k:
                print(f"[Nó {no_bp.id_no}] k={k} fixados_k={fixados_k} proibidos_k={proibidos_k}")

            branch_arcs_k = set(proibidos_k) | set(fixados_k)
            if not branch_arcs_k:
                continue

            nrotas = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * lbd[k][p]

                if (i, j) in proibidos_k:
                    s = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = s
                    constr_arco[(k, i, j)] = model.addConstr(expr - s == 0.0, name=f"arc_{k}_{i}_{j}")
                else:
                    smenos = model.addVar(lb=0.0, obj=BIGM_ARC, vtype=GRB.CONTINUOUS, name=f"slack_arc2_{k}_{i}_{j}")
                    slack_arc[(k, i, j)] = smenos
                    constr_arco[(k, i, j)] = model.addConstr(expr + smenos == 1.0, name=f"arc_{k}_{i}_{j}")

        model.update()

        # -------------------------
        # helper: adiciona λ no modelo com coluna
        # -------------------------
        def add_lambda_var_model(k, idx_pool, seq_nova, rota_binaria, custo_original):
            constrs, coefs = [], []

            for i in range(inst.nbcd):
                constrs.append(visita_constr[i])
                coefs.append(float(rota_binaria[i]))

            constrs.append(uma_rota_constr[k])
            coefs.append(1.0)

            for (kk, i, j), con in constr_arco.items():
                if kk != k:
                    continue
                constrs.append(con)
                coefs.append(float(rota_usa_arco(seq_nova, i, j)))

            col = gp.Column(coefs, constrs)
            v = model.addVar(
                lb=0.0, ub=1.0, obj=float(custo_original),
                vtype=GRB.CONTINUOUS,
                name=f"lambda_{k}_{idx_pool}",
                column=col
            )
            lbd[k].append(v)

        # =========================
        # LOOP CG
        # =========================
        iter_cg = 0
        pi = None
        sigma = None
        mu_arc_por_k = None

        colunas_desde_ultimo_mip = 0
        nome_arquivo_mip = f"mip_periodico_no_{no_bp.id_no}.txt"

        while True:
            model.optimize()
            no_bp.lp_status = model.Status

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            print(
                f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj = {model.ObjVal:.4f} |CONSTRUTIVA CANCELADA = {inst.nbconstrutiva} Colunas = {sum(len(lbd[k]) for k in lbd)}")

            print(f"[Nó {no_bp.id_no}] Colunas ativas na iteração {iter_cg}:")

            #escreve no arquivo a sol do nó
            ##mudanca para diminuir o tempo
            nome_arquivo_logLOCAL = f"log_bounds_{inst.nbcd}_{inst.ninst}_LOCAL.csv"
            ###with open(nome_arquivo_logLOCAL, "a", encoding="utf-8") as f:
            ###    f.write(f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj LP = {model.ObjVal:.4f} CONSTRUTIVA CANCELADA = {inst.nbconstrutiva}| Colunas = {sum(len(lbd[k]) for k in lbd)} \n")
            tem_ativa = False
            valor_recomposto = 0.0
            tol_print = 1e-6

            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
                for p in range(n):
                    val = float(lbd[k][p].X)

                    if val > tol_print:
                        tem_ativa = True
                        # IGNORA artificiais (p = 0 e 1)
                        if p > 1:
                            colunas_reais_usadas = True
                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_recomposto += val * custo

                        if(self.printarsol):
                            print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

            if abs(valor_recomposto - ULTIMAFO) <= 0.001:
                if colunas_reais_usadas:
                    rodadas_sem_melhoria += 1
            else:
                rodadas_sem_melhoria = 0
                ULTIMAFO = valor_recomposto


            if not tem_ativa:
                print("   nenhuma coluna ativa")
            if (self.printarsol):
                print(f"   valor recomposto = {valor_recomposto:.6f}")
                print("")

            slack_sum_vis = sum(float(v.X) for v in slack_vis)
            slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
            slack_sum_total = slack_sum_vis + slack_sum_arc

            if slack_sum_total > 1e-9:
                if (self.printarsol):
                    print(
                        f"[Nó {no_bp.id_no}] slack_total={slack_sum_total:.6f} (vis={slack_sum_vis:.6f}, arc={slack_sum_arc:.6f})")

            print("\n--- COBERTURA POR CLIENTE ---")
            for i in range(inst.nbcd):
                soma_lambda = 0.0

                for k in sol_pool.rotas.keys():
                    n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                    for p in range(n):
                        soma_lambda += (
                                float(sol_pool.rotas[k]["rotas_binaria"][p][i]) *
                                float(lbd[k][p].X)
                        )

                print(
                    f"cliente {i + 1:02d} | "
                    f"lambda={soma_lambda:.6f} | "
                    f"slack={float(slack_vis[i].X):.6f} | "
                    f"total={soma_lambda + float(slack_vis[i].X):.6f}"
                )
            # duais
            #subsitui por uma funcao
            """
            pi = [float(c.Pi) for c in visita_constr]
            sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

            if no_bp.matriz_rc == {}:
                no_bp.criaMatriRC(inst)

            # mu_arc por k
            mu_arc_por_k = {k: {} for k in sol_pool.rotas.keys()}
            if constr_arco:
                cons_by_k = {k: [] for k in sol_pool.rotas.keys()}
                keys_by_k = {k: [] for k in sol_pool.rotas.keys()}
                for (k, i, j), con in constr_arco.items():
                    cons_by_k[k].append(con)
                    keys_by_k[k].append((i, j))

                for k in sol_pool.rotas.keys():
                    if not cons_by_k[k]:
                        continue
                    try:
                        pis = model.getAttr("Pi", cons_by_k[k])
                        for (i, j), pi_ in zip(keys_by_k[k], pis):
                            mu_arc_por_k[k][(i, j)] = float(pi_)
                    except gp.GurobiError:
                        mu_arc_por_k[k] = {}

            novas_colunas = []
            """

            print("")

            pi, sigma, mu_arc_por_k = self.extrair_duais_do_mestre(
                model=model,sol_pool=sol_pool,visita_constr=visita_constr,
                uma_rota_constr=uma_rota_constr,constr_arco=constr_arco
            )

            if no_bp.matriz_rc == {}:
                no_bp.criaMatriRC(inst)

            novas_colunas = self.gerar_novas_colunas_com_duais(
                inst=inst,sol_pool=sol_pool,no_bp=no_bp,pi=pi,sigma=sigma,
                mu_arc_por_k=mu_arc_por_k,EPS_RC=EPS_RC
            )
            tentativasLP+=1
            #teste- alteracao para funcao
            """"""
            if not novas_colunas:# or tentativasLP==60:
                #teste de numero de iteracoes sem mudar a FO
                if rodadas_sem_melhoria>=nmaxrodadas_sem_melhoria and colunas_reais_usadas:
                    if inst.temmip:
                        rodadas_sem_melhoria=0
                        gerou_extra = self.tenta_intensificar_com_mip(
                            inst=inst,
                            sol_pool=sol_pool,no_bp=no_bp,model=model,lbd=lbd,
                            visita_constr=visita_constr,uma_rota_constr=uma_rota_constr,
                            constr_arco=constr_arco,slack_vis=slack_vis,slack_arc=slack_arc,
                            EPS_RC=EPS_RC,add_rota_no_pool=add_rota_no_pool,add_lambda_var_model=add_lambda_var_model,
                            rota_usa_arco=rota_usa_arco,max_tentativas=3,max_arcos_mip=5
                        )

                        if gerou_extra:
                            model.update()
                            iter_cg += 1
                            continue

                    no_bp.cg_convergiu = True
                    break
            """
            if not novas_colunas:
                no_bp.cg_convergiu = True
                break
            """

            # frota heterogenea
            """
            for k in range (len(sol_pool.rotas.keys())):
                for (k, seq, binx, custo) in novas_colunas:
                    idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                    add_rota_no_pool(k, seq, binx, custo)
                    add_lambda_var_model(k, idx_pool, seq, binx, custo)
            """

            # frota homogenea
            """
            for kk in range (len(sol_pool.rotas.keys())):
                for (_, seq, binx, custo) in novas_colunas:
                    idx_pool = len(sol_pool.rotas[kk]["sequencia_rota"])
                    add_rota_no_pool(kk, seq, binx, custo)
                    add_lambda_var_model(kk, idx_pool, seq, binx, custo)
            """
            # frota homogenea
            """
            for kk in range(len(sol_pool.rotas.keys())):
                for col in novas_colunas:
                    _, seq, binx, custo, _ = col
                    idx_pool = len(sol_pool.rotas[kk]["sequencia_rota"])
                    add_rota_no_pool(kk, seq, binx, custo)
                    add_lambda_var_model(kk, idx_pool, seq, binx, custo)

            model.update()

            """
            # primeiro adiciona todas as novas colunas ao pool/modelo
            for col in novas_colunas:
                _, seq, binx, custo, _ = col

                for kk in sol_pool.rotas.keys():
                    idx_pool = len(sol_pool.rotas[kk]["sequencia_rota"])
                    add_rota_no_pool(kk, seq, binx, custo)
                    add_lambda_var_model(kk, idx_pool, seq, binx, custo)

                # conta 1 por coluna gerada, não 1 por veículo
                colunas_desde_ultimo_mip += 1

            model.update()

            # a cada 20 colunas geradas, roda um MIP no pool atual
            if colunas_desde_ultimo_mip >= 20:
                print(f"[Nó {no_bp.id_no}] Rodando MIP periódico após {colunas_desde_ultimo_mip} colunas...")

                mip_periodico = gp.Model(f"MIP_periodico_no_{no_bp.id_no}")
                mip_periodico.setParam("OutputFlag", 0)

                z_per = {k: [] for k in sol_pool.rotas.keys()}

                # variáveis binárias
                for k in sol_pool.rotas.keys():
                    nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
                    for p in range(nrotas):
                        seqp = sol_pool.rotas[k]["sequencia_rota"][p]
                        custop = float(sol_pool.rotas[k]["custo"][p])

                        if not self.coluna_respeita_no(no_bp, seqp, k):
                            continue

                        var = mip_periodico.addVar(
                            lb=0.0,
                            ub=1.0,
                            obj=custop,
                            vtype=GRB.BINARY,
                            name=f"zper_{k}_{p}"
                        )
                        z_per[k].append((p, var))

                mip_periodico.ModelSense = GRB.MINIMIZE
                mip_periodico.update()

                # visita única
                for i in range(inst.nbcd):
                    expr = gp.LinExpr()
                    for k in sol_pool.rotas.keys():
                        for p, var in z_per[k]:
                            expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
                    mip_periodico.addConstr(expr == 1.0, name=f"visita_{i}")

                # uma rota por veículo
                for k in sol_pool.rotas.keys():
                    expr = gp.LinExpr()
                    for p, var in z_per[k]:
                        expr += var
                    mip_periodico.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

                # arcos do nó
                for k in sol_pool.rotas.keys():
                    proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                    fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                    branch_arcs_k = set(proibidos_k) | set(fixados_k)

                    for (i, j) in branch_arcs_k:
                        expr = gp.LinExpr()
                        for p, var in z_per[k]:
                            seqp = sol_pool.rotas[k]["sequencia_rota"][p]
                            expr += float(rota_usa_arco(seqp, i, j)) * var

                        if (i, j) in proibidos_k:
                            mip_periodico.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                        else:
                            mip_periodico.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")

                mip_periodico.optimize()

                if mip_periodico.Status == GRB.OPTIMAL:
                    usou_coluna_inicial = False
                    selecionadas = []

                    for k in sol_pool.rotas.keys():
                        for p, var in z_per[k]:
                            if float(var.X) > 0.5:
                                selecionadas.append((k, p))
                                if p in (0, 1):
                                    usou_coluna_inicial = True

                    if not usou_coluna_inicial:
                        with open(nome_arquivo_mip, "a", encoding="utf-8") as f:
                            f.write(f"Nó {no_bp.id_no} | iter_cg={iter_cg} | FO={mip_periodico.ObjVal:.6f}\n")
                            for k, p in selecionadas:
                                seqp = sol_pool.rotas[k]["sequencia_rota"][p]
                                custop = float(sol_pool.rotas[k]["custo"][p])
                                f.write(f"   veic={k} col={p} custo={custop:.6f} rota={seqp}\n")
                            f.write("\n")

                        print(
                            f"[Nó {no_bp.id_no}] MIP periódico encontrou solução inteira válida. FO={mip_periodico.ObjVal:.6f}")
                    else:
                        print(f"[Nó {no_bp.id_no}] MIP periódico usou coluna inicial, então foi ignorado.")
                else:
                    print(f"[Nó {no_bp.id_no}] MIP periódico não foi ótimo.")

                colunas_desde_ultimo_mip = 0


            iter_cg += 1
            """
            if iter_cg >= max_iter_cg:
                no_bp.parou_por_max_iter = True
                no_bp.cg_convergiu = False
                break
            """

        # =========================
        # Final do nó - LP com slack
        # =========================
        model.optimize()
        no_bp.lp_status = model.Status
        if model.Status != GRB.OPTIMAL:
            no_bp.custo_lp = None
            no_bp.solucao_inteira = False
            no_bp.lambdas = {}
            return

        slack_sum_vis = sum(float(v.X) for v in slack_vis)
        slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
        no_bp.slack_sum_final = slack_sum_vis + slack_sum_arc

        no_bp.lb_confiavel = (
                no_bp.cg_convergiu and
                (no_bp.slack_sum_final <= 1e-9) and
                (not no_bp.parou_por_max_iter)
        )

        no_bp.custo_lp = float(model.ObjVal)

        # lambdas LP
        lambdas_lp = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lambdas_lp[(k, p)] = float(lbd[k][p].X)
        no_bp.lambdas = lambdas_lp

        print(f"[Nó {no_bp.id_no}] Melhor solução fracionada final (LP com slack):")
        tem_lp = False
        valor_lp_recomposto = 0.0

        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                if val > 1e-6:
                    tem_lp = True
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    custo = float(sol_pool.rotas[k]["custo"][p])
                    valor_lp_recomposto += val * custo
                    print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

        if not tem_lp:
            print("   nenhuma coluna LP ativa")

        print(f"   valor LP recomposto = {valor_lp_recomposto:.6f}")
        print(f"   slack_final = {no_bp.slack_sum_final:.6f}")
        print("")

        # arc_score = soma dos lambdas LP por arco
        arc_score = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                lam = float(lbd[k][p].X)
                if lam <= 1e-12:
                    continue
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    arc_score[(i, j, k)] = arc_score.get((i, j, k), 0.0) + lam
        no_bp.arc_score = arc_score

        # =========================
        # MIP final com pool atual (SEM slack) - inline
        # =========================
        no_bp.custo_mip = None
        no_bp.lambdas_inteiras = {}
        no_bp.solucao_inteira = False

        mip = gp.Model(f"MIP_final_no_{no_bp.id_no}")
        mip.setParam("OutputFlag", 0)

        z = {k: [] for k in sol_pool.rotas.keys()}

        # variáveis binárias
        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                if not self.coluna_respeita_no(no_bp, seq, k):
                    continue

                var = mip.addVar(
                    lb=0.0,
                    ub=1.0,
                    obj=custo,
                    vtype=GRB.BINARY,
                    name=f"z_{k}_{p}"
                )
                z[k].append((p, var))

        mip.ModelSense = GRB.MINIMIZE
        mip.update()

        # visita única sem slack
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                for p, var in z[k]:
                    expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
            mip.addConstr(expr == 1.0, name=f"visita_{i}")

        # uma rota por veículo
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p, var in z[k]:
                expr += var
            mip.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        # arcos do nó sem slack
        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
            branch_arcs_k = set(proibidos_k) | set(fixados_k)

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p, var in z[k]:
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * var

                if (i, j) in proibidos_k:
                    mip.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                else:
                    mip.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")

        mip.optimize()

        if mip.Status == GRB.OPTIMAL:
            #preciso ver se esse mip não tem por acaso aquelas solucoes das colunas inicias
            no_bp.custo_mip = float(mip.ObjVal)
            #no_bp.solucao_inteira = True




            lambdas_int = {}
            selecao = []
            usou_coluna_inicial = False
            for k in sol_pool.rotas.keys():
                for p, var in z[k]:
                    val = float(var.X)
                    lambdas_int[(k, p)] = val
                    if val > 1e-6:
                        selecao.append({
                            "k": k,
                            "p": p,
                            "nome": f"veic={k} col={p}"
                        })
                        if p in (0, 1):
                            usou_coluna_inicial = True

            no_bp.lambdas_inteiras = lambdas_int

            print(f"[Nó {no_bp.id_no}] Lambdas da melhor solução inteira:")
            for (k, p), val in sorted(no_bp.lambdas_inteiras.items()):
                if val > 1e-6:
                    print(f"   lambda_int[{k},{p}] = {val:.0f}")

            print(f"[Nó {no_bp.id_no}] Melhor solução inteira final (MIP no pool):")
            valor_int_recomposto = 0.0

            for item in selecao:
                k = item["k"]
                p = item["p"]
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])
                valor_int_recomposto += custo
                print(f"   veic={k} | col={p} | z=1 | custo={custo:.4f} | rota={seq}")

            # escreve no arquivo a sol do nó
            nome_arquivo_logLOCAL = f"log_bounds_{inst.nbcd}_{inst.ninst}_LOCAL.csv"
            ###with open(nome_arquivo_logLOCAL, "a", encoding="utf-8") as f:
            ###    f.write(
            ###        f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj MIP = {mip.ObjVal:.4f} |  CONSTRUTIVA CANCELADA = {inst.nbconstrutiva}"
            ###        f"Colunas = {sum(1 for v in no_bp.lambdas_inteiras.values() if v > 1e-6)}\n"
            ###    )
            print(f"   valor inteiro recomposto = {valor_int_recomposto:.6f}")
            print("")

            no_bp.rotas_inteiras = []
            valor_int_recomposto = 0.0

            for item in selecao:
                k = item["k"]
                p = item["p"]
                seq = list(sol_pool.rotas[k]["sequencia_rota"][p])
                custo = float(sol_pool.rotas[k]["custo"][p])
                binaria = list(sol_pool.rotas[k]["rotas_binaria"][p])

                no_bp.rotas_inteiras.append({
                    "k": k,
                    "p": p,
                    "rota": seq,
                    "custo": custo,
                    "bin_xij": binaria
                })

                valor_int_recomposto += custo

            no_bp.valor_recomposto_inteiro = valor_int_recomposto

            # decide se a solução inteira é válida
            if usou_coluna_inicial:
                no_bp.solucao_inteira = False
                print(f"[Nó {no_bp.id_no}] MIP usou coluna inicial. Inteira inválida.")
            else:
                no_bp.solucao_inteira = True
            # exporta a solução inteira do MIP
                if selecao:
                    mu_arc_total = {}
                    if mu_arc_por_k is not None:
                        for kk in mu_arc_por_k:
                            for (i, j), val in mu_arc_por_k[kk].items():
                                mu_arc_total[(i, j, kk)] = float(val)

                    if pi is None:
                        pi = [0.0 for _ in range(inst.nbcd)]
                    if sigma is None:
                        sigma = {k: 0.0 for k in sol_pool.rotas.keys()}

                    print(f"[Nó {no_bp.id_no}] Exportando solução inteira do MIP para JS...")
                    print(f"   colunas ativas no MIP: {[(item['k'], item['p']) for item in selecao]}")

                    sol_pool.exportar_rotas_pares_js(
                        inst=inst,
                        selecao=selecao,
                        pi=pi,
                        mu_arc=mu_arc_total,
                        sigma=sigma,
                        nome_arquivo_js="rotas_plot_data.js",
                        title=f"Solução inteira do nó {no_bp.id_no}",
                        subtitle=f"Melhor inteira do pool | rotas ativas: {len(selecao)}"
                    )
        else:
            print(f"[Nó {no_bp.id_no}] MIP final do pool inviável/sem solução ótima.")

        print(
            f"Nó {no_bp.id_no} finalizado: "
            f"LP={no_bp.custo_lp:.4f}, "
            f"MIP_pool={no_bp.custo_mip if no_bp.custo_mip is not None else 'None'}, "
            f"tem_inteira={no_bp.solucao_inteira}, "
            f"cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, "
            f"slack_final={no_bp.slack_sum_final:.6f}, "
            f"lb_confiavel={no_bp.lb_confiavel}"
        )

        print("SALDOS")
        print(sol_pool.construtivas)

        if no_bp.id_no == 0:
            pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}
            # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)
            print("PRIMEIRO NO")

    def extrair_duais_do_mestre(self, model, sol_pool, visita_constr, uma_rota_constr, constr_arco):
        import gurobipy as gp

        pi = [float(c.Pi) for c in visita_constr]
        sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

        mu_arc_por_k = {k: {} for k in sol_pool.rotas.keys()}
        if constr_arco:
            cons_by_k = {k: [] for k in sol_pool.rotas.keys()}
            keys_by_k = {k: [] for k in sol_pool.rotas.keys()}

            for (k, i, j), con in constr_arco.items():
                cons_by_k[k].append(con)
                keys_by_k[k].append((i, j))

            for k in sol_pool.rotas.keys():
                if not cons_by_k[k]:
                    continue
                try:
                    pis = model.getAttr("Pi", cons_by_k[k])
                    for (i, j), pi_ in zip(keys_by_k[k], pis):
                        mu_arc_por_k[k][(i, j)] = float(pi_)
                except gp.GurobiError:
                    mu_arc_por_k[k] = {}

        return pi, sigma, mu_arc_por_k


    def gerar_novas_colunas_com_duais(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC):
        import time

        novas_colunas = []

        # frota homogênea: resolve só um k e replica depois
        for k in range(1):
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
            proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)
            mu_arc = mu_arc_por_k.get(k, {})

            t0 = time.time()
            nova_rota = None
            custo_red = None

            if (inst.nbconstrutiva != 0 and inst.nbconstrutiva != 22):
                #nova_rota, custo_red = self.SUB_VNSRANDOM(
                #    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                #)

                nova_rota2, custo_red2 = self.SUB_VNSRANDOMant(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )

                if nova_rota is not None:
                    sol_pool.construtivas[0] += 1
                    print("gerou na 1")

            if (inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22):
                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_ALLBESTINSERTION(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[1] += 1
                        if self.printarsol:
                            print("gerou na 2")

            if (inst.nbconstrutiva != 2 and inst.nbconstrutiva != 22):
                if nova_rota is None:
                    nova_rota, custo_red = self.SUB_HEUR_VNS(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[2] += 1
                        if self.printarsol:
                            print("gerou na 3")

            if (inst.nbconstrutiva != 3):
                if nova_rota is None:
                    if self.printarsol:
                        print("%%%%%%%%%TESTE BIDIRECIONAL")
                    nova_rota, custo_red = self.SUB_PROG_DIN_BIDIRECIONAL(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if self.printarsol:
                        print("%%%%%%% BIDIRECIONALACHOU")
                    if nova_rota is not None:
                        sol_pool.construtivas[3] += 1
                        if self.printarsol:
                            print("gerou na BID")
            """
            if nova_rota is None or float(custo_red) >= -EPS_RC:
                print("$$$$$$$$$$$$$$ nao achou sol, testa PD")
                nova_rota, custo_red = self.SUB_PROG_DIN_PW(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if nova_rota is not None:
                    sol_pool.construtivas[5] += 1
                    print("gerou na PD COMPLETA")
            """

            if nova_rota is None:
                print("PASSOU PELOS 3 sem gerar nada")
                continue

            nova_rota["custo_reduzido"] = float(custo_red)
            print(f"NOVA COLUNA GERAL | rc={nova_rota['custo_reduzido']:.6f}")
            print(nova_rota)

            if float(custo_red) < -EPS_RC:
                seq = nova_rota["clientes"]
                if not self.coluna_respeita_no(no_bp, seq, k):
                    continue

                novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"], float(custo_red)))

                print(f"NOVA COLUNA | rc={nova_rota['custo_reduzido']:.6f}")
                print(nova_rota)
                print("")

                # tabu
                mat = no_bp.tabu_until[k]
                for i in range(inst.nbn):
                    row = mat[i]
                    for j in range(inst.nbn):
                        if row[j] > 0:
                            row[j] -= 1

                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    no_bp.freq_arc[k][i][j] += 1
                    no_bp.last_arc[k][i][j] = 0
                    no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

        return novas_colunas


    def resolve_mip_pool_para_intensificacao(self, inst, sol_pool, no_bp, rota_usa_arco):
        import gurobipy as gp
        from gurobipy import GRB

        mip = gp.Model(f"MIP_intens_no_{no_bp.id_no}")
        mip.setParam("OutputFlag", 0)

        z = {k: [] for k in sol_pool.rotas.keys()}

        for k in sol_pool.rotas.keys():
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = float(sol_pool.rotas[k]["custo"][p])

                if not self.coluna_respeita_no(no_bp, seq, k):
                    continue

                var = mip.addVar(
                    lb=0.0,
                    ub=1.0,
                    obj=custo,
                    vtype=GRB.BINARY,
                    name=f"z_{k}_{p}"
                )
                z[k].append((p, var))

        mip.ModelSense = GRB.MINIMIZE
        mip.update()

        # visita única
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                for p, var in z[k]:
                    expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
            mip.addConstr(expr == 1.0, name=f"visita_{i}")

        # uma rota por veículo
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p, var in z[k]:
                expr += var
            mip.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        # arcos do nó
        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
            branch_arcs_k = set(proibidos_k) | set(fixados_k)

            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p, var in z[k]:
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    expr += float(rota_usa_arco(seq, i, j)) * var

                if (i, j) in proibidos_k:
                    mip.addConstr(expr == 0.0, name=f"arc_{k}_{i}_{j}")
                else:
                    mip.addConstr(expr == 1.0, name=f"arc_{k}_{i}_{j}")





        mip.optimize()

        import time
        import csv
        import os

        caminho = "log_mip_intensificacao.csv"
        novo = not os.path.exists(caminho)

        with open(caminho, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")

            if novo:
                w.writerow([
                    "id_no",
                    "obj_mip",
                ])

            w.writerow([
                no_bp.id_no,
                round(mip.ObjVal, 6)
            ])

        if mip.Status != GRB.OPTIMAL:
            return {
                "status": mip.Status,
                "obj": None,
                "selecao": [],
                "arcos_mip": []
            }

        selecao = []
        arcos_mip = set()

        for k in sol_pool.rotas.keys():
            for p, var in z[k]:
                if float(var.X) > 0.5:
                    seq = list(sol_pool.rotas[k]["sequencia_rota"][p])
                    selecao.append((k, p, seq))
                    for t in range(len(seq) - 1):
                        i, j = seq[t], seq[t + 1]
                        arcos_mip.add((i, j, k))
        print(f"[Nó {no_bp.id_no}] Arcos presentes na solução do MIP de intensificação:")
        for (i, j, k) in sorted(arcos_mip):
            print(f"   arco=({i},{j},{k})")

        print(f"[Nó {no_bp.id_no}] Solução do MIP de intensificação:")
        valor_recomposto = 0.0
        for (k, p, seq) in selecao:
            custo = float(sol_pool.rotas[k]["custo"][p])
            valor_recomposto += custo
            print(f"   veic={k} | col={p} | z=1 | custo={custo:.4f} | rota={seq}")
        print(f"   valor recomposto MIP = {valor_recomposto:.6f}")


        return {
            "status": mip.Status,
            "obj": float(mip.ObjVal),
            "selecao": selecao,
            "arcos_mip": list(arcos_mip)
        }


    def rankear_arcos_candidatos_mip(self, no_bp, arcos_mip):
        candidatos = []

        for (i, j, k) in arcos_mip:
            if (i, j, k) in no_bp.arcos_fixados_em_1:
                continue
            if (i, j, k) in no_bp.arcos_proibidos:
                continue

            arc_lp = no_bp.arc_score.get((i, j, k), 0.0)
            score = 10.0 + arc_lp
            candidatos.append((i, j, k, score))

        candidatos.sort(key=lambda x: x[3], reverse=True)
        return candidatos


    def tenta_intensificar_com_mip(
        self, inst, sol_pool, no_bp, model, lbd,
        visita_constr, uma_rota_constr, constr_arco, slack_vis, slack_arc,
        EPS_RC, add_rota_no_pool, add_lambda_var_model, rota_usa_arco, max_tentativas=3,
        max_arcos_mip=5
    ):


        print(f"[Nó {no_bp.id_no}] Iniciando intensificação por MIP...")

        info_mip = self.resolve_mip_pool_para_intensificacao(
            inst=inst, sol_pool=sol_pool, no_bp=no_bp, rota_usa_arco=rota_usa_arco
        )

        if info_mip["status"] != GRB.OPTIMAL:
            print(f"[Nó {no_bp.id_no}] MIP de intensificação não ótimo.")
            return False

        print(f"[Nó {no_bp.id_no}] MIP de intensificação obj = {info_mip['obj']:.6f}")

        candidatos = self.rankear_arcos_candidatos_mip(
            no_bp=no_bp,
            arcos_mip=info_mip["arcos_mip"]
        )

        if not candidatos:
            print(f"[Nó {no_bp.id_no}] Sem arcos candidatos para intensificação.")
            return False

        tentativas = 0

        for (i_sel, j_sel, k_sel, score) in candidatos[:max_arcos_mip]:
            if tentativas >= max_tentativas:
                break

            print(f"[Nó {no_bp.id_no}] Testando arco temporário ({i_sel},{j_sel},{k_sel}) | score={score:.4f}")

            expr = gp.LinExpr()
            nrotas = min(len(lbd[k_sel]), len(sol_pool.rotas[k_sel]["sequencia_rota"]))
            for p in range(nrotas):
                seq = sol_pool.rotas[k_sel]["sequencia_rota"][p]
                expr += float(rota_usa_arco(seq, i_sel, j_sel)) * lbd[k_sel][p]

            nome_tmp = f"tmp_fix_mip_{no_bp.id_no}_{k_sel}_{i_sel}_{j_sel}_{tentativas}"
            constr_tmp = model.addConstr(expr == 1.0, name=nome_tmp)
            model.update()

            try:
                model.optimize()

                if model.Status != GRB.OPTIMAL:
                    print(f"[Nó {no_bp.id_no}] LP temporário inviável/não ótimo para arco ({i_sel},{j_sel},{k_sel})")
                    model.remove(constr_tmp)
                    model.update()
                    tentativas += 1
                    continue


                pi, sigma, mu_arc_por_k = self.extrair_duais_do_mestre(
                    model=model,
                    sol_pool=sol_pool,
                    visita_constr=visita_constr,
                    uma_rota_constr=uma_rota_constr,
                    constr_arco=constr_arco
                )

                novas_colunas = self.gerar_novas_colunas_com_duais(
                    inst=inst,
                    sol_pool=sol_pool,
                    no_bp=no_bp,
                    pi=pi,
                    sigma=sigma,
                    mu_arc_por_k=mu_arc_por_k,
                    EPS_RC=EPS_RC
                )

                model.remove(constr_tmp)
                model.update()

                if novas_colunas:
                    print(f"[Nó {no_bp.id_no}] Intensificação encontrou {len(novas_colunas)} coluna(s).")

                    for kk in range(len(sol_pool.rotas.keys())):
                        for (_, seq, binx, custo, custo_red) in novas_colunas:
                            idx_pool = len(sol_pool.rotas[kk]["sequencia_rota"])
                            add_rota_no_pool(kk, seq, binx, custo)
                            add_lambda_var_model(kk, idx_pool, seq, binx, custo)
                            print(f"[Nó {no_bp.id_no}] Coluna adicionada pela intensificação | kk={kk} | rc={custo_red:.6f} | rota={seq}")

                    model.update()
                    return True

            except Exception as e:
                try:
                    model.remove(constr_tmp)
                    model.update()
                except:
                    pass
                print(f"[Nó {no_bp.id_no}] Erro na intensificação: {e}")

            tentativas += 1

        print(f"[Nó {no_bp.id_no}] Intensificação não encontrou colunas novas.")
        return False

    def resolver_no_com_poolRAIZ(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} (RAIZ) GC PURA ---")

        # flags
        no_bp.cg_convergiu = False
        no_bp.parou_por_max_iter = False
        no_bp.slack_sum_final = 0.0
        no_bp.lb_confiavel = False
        no_bp.lp_status = None

        EPS_RC = 1e-6
        max_iter_cg = 500

        # marca quantas colunas existiam antes da raiz (para export)
        pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])

        def construir_modelo_mestre():
            model = gp.Model(f"Mestre_no_{no_bp.id_no}_RAIZ")
            model.setParam("OutputFlag", 0)
            model.setParam("Method", 1)  # dual simplex
            model.setParam("Crossover", 1)

            # 1) lambdas
            lbd = {k: [] for k in sol_pool.rotas.keys()}
            for k in sol_pool.rotas.keys():
                nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
                for p in range(nrotas):
                    custo = float(sol_pool.rotas[k]["custo"][p])
                    # raiz: sem branching, então todas respeitam (mas mantém seu filtro)
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    ub = 1.0 if self.coluna_respeita_no(no_bp, seq, k) else 0.0

                    v = model.addVar(lb=0.0, ub=ub, obj=custo,
                                     vtype=GRB.CONTINUOUS,
                                     name=f"lambda_{k}_{p}")
                    lbd[k].append(v)

            model.ModelSense = GRB.MINIMIZE
            model.update()

            # 2) visita única (SEM slack)
            visita_constr = []
            for i in range(inst.nbcd):
                expr = gp.LinExpr()
                for k in sol_pool.rotas.keys():
                    n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                    for p in range(n):
                        expr += lbd[k][p] * float(sol_pool.rotas[k]["rotas_binaria"][p][i])
                visita_constr.append(model.addConstr(expr == 1.0, name=f"visita_{i}"))

            # 3) 1 rota por veículo (SEM slack)
            uma_rota_constr = {}
            for k in sol_pool.rotas.keys():
                expr = gp.LinExpr()
                for p in range(len(lbd[k])):
                    expr += lbd[k][p]
                uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

            model.update()
            return model, lbd, visita_constr, uma_rota_constr

        def add_lambda_var_model(model, lbd, visita_constr, uma_rota_constr, k, idx_pool, seq_nova, rota_binaria,
                                 custo_original):
            constrs, coefs = [], []

            for i in range(inst.nbcd):
                constrs.append(visita_constr[i])
                coefs.append(float(rota_binaria[i]))

            constrs.append(uma_rota_constr[k])
            coefs.append(1.0)

            col = gp.Column(coefs, constrs)
            v = model.addVar(lb=0.0, ub=1.0, obj=float(custo_original),
                             vtype=GRB.CONTINUOUS,
                             name=f"lambda_{k}_{idx_pool}",
                             column=col)
            lbd[k].append(v)

        # -------------------------
        # 0) constroi mestre e garante viabilidade (sem slack)
        # -------------------------
        model, lbd, visita_constr, uma_rota_constr = construir_modelo_mestre()
        model.optimize()
        no_bp.lp_status = model.Status

        if model.Status != GRB.OPTIMAL:
            # sem slack, o mais comum é INFEASIBLE por falta de cobertura no pool inicial.
            # solução: injeta colunas artificiais (base) e reconstrói
            print(
                f"[RAIZ] Mestre inviável (Status={model.Status}). Inserindo colunas artificiais para viabilizar base...")
            self.gera_rotas_artificiais(inst, sol_pool,
                                        custo_alto=100000)  # já existe no seu código :contentReference[oaicite:1]{index=1}

            # atualiza marcador de início (para export “gerada_na_raiz” funcionar)
            pool_ini_por_k = {k: 0 for k in sol_pool.rotas.keys()}

            model, lbd, visita_constr, uma_rota_constr = construir_modelo_mestre()
            model.optimize()
            no_bp.lp_status = model.Status
            if model.Status != GRB.OPTIMAL:
                print(f"[RAIZ] Ainda não ficou ótimo após artificiais. Status={model.Status}. Abortando nó.")
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

        # -------------------------
        # LOOP CG (GC pura)
        # -------------------------
        iter_cg = 0
        while True:
            # print(
            #    f"[RAIZ Nó {no_bp.id_no}] Iter {iter_cg} | Obj={model.ObjVal:.6f} | Colunas={sum(len(lbd[k]) for k in lbd)}")

            # duais
            pi = [float(c.Pi) for c in visita_constr]
            sigma = {k: float(uma_rota_constr[k].Pi) for k in sol_pool.rotas.keys()}

            novas_colunas = []
            for k in sol_pool.rotas.keys():
                t0 = time.time()
                if tipo_geracao == "PD":
                    nova_rota, custo_red = self.SUB_PROG_DIN(
                        inst, pi, sigma_k=sigma[k], k=k,
                        arcos_proibidos=set(), arcos_fixados=set(), mu_arc={}
                    )
                else:
                    nova_rota, custo_red = self.subproblema(inst, pi, sigma[k], k, duais_arcos=None)

                # opcional
                # print(f"[RAIZ] k={k} t={time.time()-t0:.3f}s rc={custo_red}")

                if nova_rota is None:
                    continue
                if float(custo_red) < -EPS_RC:
                    seq = nova_rota["clientes"]
                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue
                    novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"]))

            if not novas_colunas:
                no_bp.cg_convergiu = True
                break

            for (k, seq, binx, custo) in novas_colunas:
                idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                add_rota_no_pool(k, seq, binx, custo)
                add_lambda_var_model(model, lbd, visita_constr, uma_rota_constr, k, idx_pool, seq, binx, custo)

            model.update()
            model.optimize()
            no_bp.lp_status = model.Status
            if model.Status != GRB.OPTIMAL:
                print(f"[RAIZ] Mestre ficou não-ótimo durante CG. Status={model.Status}. Abortando nó.")
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            iter_cg += 1
            if iter_cg >= max_iter_cg:
                no_bp.parou_por_max_iter = True
                no_bp.cg_convergiu = False
                break

        # -------------------------
        # Final do nó
        # -------------------------
        no_bp.custo_lp = float(model.ObjVal)
        no_bp.lb_confiavel = (no_bp.cg_convergiu and (not no_bp.parou_por_max_iter))
        no_bp.slack_sum_final = 0.0

        # lambdas
        lambdas = {}
        inteira = True
        tol = 1e-6
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                lambdas[(k, p)] = val
                if val > tol and abs(val - 1.0) > tol:
                    inteira = False
        no_bp.lambdas = lambdas
        no_bp.solucao_inteira = inteira

        print(
            f"Nó {no_bp.id_no} (RAIZ) finalizado: LP={no_bp.custo_lp:.4f}, "
            f"inteira? {no_bp.solucao_inteira}, cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, lb_confiavel={no_bp.lb_confiavel}"
        )

        # exporta pool ao final da raiz
        # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)

    def resolver_no_com_poolRAIZ2(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB

        print(f"\n--- Resolve nó {no_bp.id_no} com POOL GLOBAL de colunas ---")

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)

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
            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
            for p in range(nrotas):
                seq = sol_pool.rotas[k]["sequencia_rota"][p]
                custo = sol_pool.rotas[k]["custo"][p]

                respeita = self.coluna_respeita_no(no_bp, seq, k)
                ub = 1.0 if respeita else 0.0

                v = model.addVar(
                    lb=0.0,
                    ub=ub,
                    obj=custo,
                    vtype=GRB.CONTINUOUS,
                    name=f"lambda_{k}_{p}",
                )
                lbd[k].append(v)

        model.ModelSense = GRB.MINIMIZE
        model.update()

        # =========================
        # 2) Restrições de visita única  (ROBUSTO: usa min(len(lbd), len(rotas_binaria)))
        # =========================
        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                for p in range(n):
                    rota_bin = sol_pool.rotas[k]["rotas_binaria"][p]
                    expr += lbd[k][p] * float(rota_bin[i])
            model.addConstr(expr == 1.0, name=f"visita_{i}")

        # =========================
        # 3) Restrição 1 rota por veículo (ROBUSTO: usa len(lbd[k]))
        # =========================
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Restrições de arcos do nó (fixo=1 / proibido=0)
        # =========================
        constr_arco = {}  # (k,i,j) -> Constr

        for k in sol_pool.rotas.keys():
            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
            branch_arcs_k = set(proibidos_k) | set(fixados_k)

            if not branch_arcs_k:
                continue

            nrotas = len(sol_pool.rotas[k]["sequencia_rota"])  # no build inicial bate com len(lbd[k])

            # coeficientes (i,j) -> list[0/1] por rota p
            coef_arco = {}
            for (i, j) in branch_arcs_k:
                coef_arco[(i, j)] = [0.0] * nrotas
                for p in range(nrotas):
                    seq = sol_pool.rotas[k]["sequencia_rota"][p]
                    coef_arco[(i, j)][p] = rota_usa_arco(seq, i, j)

            # constraints
            for (i, j) in branch_arcs_k:
                expr = gp.LinExpr()
                for p in range(nrotas):
                    expr += float(coef_arco[(i, j)][p]) * lbd[k][p]

                rhs = 1.0 if (i, j) in fixados_k else 0.0
                constr_arco[(k, i, j)] = model.addConstr(expr == rhs, name=f"arc_{k}_{i}_{j}")

        model.update()

        # =========================
        # LOOP DE GERAÇÃO DE COLUNAS
        # =========================
        iter_cg = 0
        max_iter_cg = 50

        while True:
            model.optimize()

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            # prints/score (assuma que suas funções internas usam min() ao iterar lbd vs pool)
            self.print_matriz_arcos_por_k(inst, sol_pool, lbd, incluir_deposito=True, casas=3)
            self.atualizar_score_arcos_lambda_com_lbd(inst, sol_pool, lbd, no_bp)

            # duais visitas
            pi = [model.getConstrByName(f"visita_{i}").Pi for i in range(inst.nbcd)]
            # duais 1 rota por veic
            sigma = {k: model.getConstrByName(f"uma_rota_veic_{k}").Pi for k in sol_pool.rotas.keys()}

            houve_nova_coluna = False

            for k in sol_pool.rotas.keys():
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}

                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)

                # ===== mu_arc (duais das restrições de arco do nó, para este veículo k) - ROBUSTO =====
                mu_arc = {}
                cons_k = []
                keys_k = []
                for (kk, i, j), c in constr_arco.items():
                    if kk == k:
                        cons_k.append(c)
                        keys_k.append((i, j))

                if cons_k and model.SolCount > 0 and (not model.IsMIP) and model.Status == GRB.OPTIMAL:
                    pis = model.getAttr("Pi", cons_k)
                    for (i, j), pi_ in zip(keys_k, pis):
                        mu_arc[(i, j)] = float(pi_)

                # ===== pricing =====
                if tipo_geracao == "PD":
                    nova_rota, custo_red = self.SUB_PROG_DINCPP(
                        inst,
                        pi,
                        sigma_k=sigma[k],
                        k=k,
                        arcos_proibidos=proibidos_equiv,
                        arcos_fixados=fixados_k,
                        mu_arc=mu_arc,
                    )
                elif tipo_geracao == "GUROBI":
                    nova_rota, custo_red = self.subproblema(inst, pi, sigma[k], k, duais_arcos=None)
                else:
                    raise ValueError("tipo_geracao deve ser 'PD' ou 'GUROBI'")

                if nova_rota is None:
                    continue

                seq_nova = nova_rota["clientes"]
                rota_binaria = nova_rota["bin_xij"]
                custo_original = nova_rota["custo"]

                # compatibilidade com nó
                if not self.coluna_respeita_no(no_bp, seq_nova, k):
                    idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                    sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
                    sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
                    sol_pool.rotas[k]["custo"].append(custo_original)
                    sol_pool.rotas[k]["vezes_usada_geral"].append(0)
                    sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
                    sol_pool.rotas[k]["lbd_iteracao"].append([])
                    continue

                if custo_red < -1e-6:
                    houve_nova_coluna = True

                    # 1) adiciona ao pool
                    idx_pool = len(sol_pool.rotas[k]["sequencia_rota"])
                    sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
                    sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
                    sol_pool.rotas[k]["custo"].append(custo_original)
                    sol_pool.rotas[k]["vezes_usada_geral"].append(0)
                    sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
                    sol_pool.rotas[k]["lbd_iteracao"].append([])

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

                    # restrições de arco do nó (somente k)
                    for (kk, i, j), con in constr_arco.items():
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
                        column=coluna,
                    )
                    lbd[k].append(v)
                    model.update()

            print(f"  [Nó {no_bp.id_no}] houve_nova_coluna = {houve_nova_coluna}")
            for k in sol_pool.rotas.keys():
                print(f"    veic {k}: {len(sol_pool.rotas[k]['sequencia_rota'])} rotas no pool")

            if (not houve_nova_coluna) or (iter_cg >= max_iter_cg):
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

        # salva lambdas somente do que está no mestre (robusto)
        lambdas = {}
        inteira = True
        tol = 1e-6
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                val = float(lbd[k][p].X)
                lambdas[(k, p)] = val
                if val > tol and abs(val - 1.0) > tol:
                    inteira = False

        no_bp.lambdas = lambdas
        no_bp.solucao_inteira = inteira

        print(f"Nó {no_bp.id_no} finalizado: LP = {no_bp.custo_lp:.4f}, inteira? {no_bp.solucao_inteira}")

    def soma_lambda_de_um_arco(self, sol_pool, lbd, k, i, j):

        # sanity: mesmo tamanho
        seqs = sol_pool.rotas[k]['sequencia_rota']
        if len(seqs) != len(lbd[k]):
            raise ValueError(
                f"[soma_lambda_de_um_arco] k={k}: "
                f"len(seqs)={len(seqs)} != len(lbd[k])={len(lbd[k])}"
            )

        s = 0.0
        for p, seq in enumerate(seqs):
            # checa se a rota usa o arco
            usa = 0.0
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    usa = 1.0
                    break
            if usa:
                s += float(lbd[k][p].X)
        return s

    def atualizar_score_arcos_lambda_com_lbd(self, inst, sol_pool, lbd, no_bp=None):
        score = {}
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]['sequencia_rota']))
            for p in range(n):
                lam = float(lbd[k][p].X)
                if lam <= 1e-12:
                    continue
                seq = sol_pool.rotas[k]['sequencia_rota'][p]
                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    key = (i, j, k)
                    score[key] = score.get(key, 0.0) + lam
        if no_bp is not None:
            no_bp.score_arcos_lambda = score
        return score

    def soma_lambda_por_arco_veiculo(self, sol_pool, lbd, k):
        seqs = sol_pool.rotas[k]['sequencia_rota']
        n_model = len(lbd[k])
        n_pool = len(seqs)

        n = min(n_model, n_pool)  # usa só o que existe no modelo

        sums = {}
        for p in range(n):
            lam = float(lbd[k][p].X)  # (desde que já tenha solução)
            if lam == 0.0:
                continue

            seq = seqs[p]
            for t in range(len(seq) - 1):
                i, j = seq[t], seq[t + 1]
                key = (i, j, k)
                sums[key] = sums.get(key, 0.0) + lam

        # opcional: avisar se divergiu (debug)
        if n_model != n_pool:
            print(f"[WARN] k={k}: pool={n_pool} rotas, modelo={n_model} vars. Usando n={n}.")

        return sums

    def print_matriz_arcos_por_k(self, inst, sol_pool, lbd, *, incluir_deposito=False, casas=3,
                                 mostrar_so_maiores_que=1e-9):
        """
        Imprime, para cada k, uma 'matriz' (tabela i x j) com soma dos lambdas no arco i->j.
        Por padrão, não imprime depósito (0 e nbn-1) para reduzir ruído.

        - incluir_deposito=False: ignora i/j iguais a 0 ou depf
        - mostrar_so_maiores_que: não imprime células abaixo desse valor (vira '.')
        """
        dep0 = 0
        depf = inst.nbn - 1

        for k in sol_pool.rotas.keys():
            sums = self.soma_lambda_por_arco_veiculo(sol_pool, lbd, k)

            # define nós na matriz
            if incluir_deposito:
                nos = list(range(inst.nbn))
            else:
                nos = list(range(1, inst.nbn - 1))

            print("\n" + "=" * 80)
            print(f"k={k}  (matriz soma-lambda por arco i->j)")
            print("=" * 80)

            # header
            header = "i\\j | " + " ".join(f"{j:>7d}" for j in nos)
            print(header)
            print("-" * len(header))

            for i in nos:
                row_vals = []
                for j in nos:
                    v = sums.get((i, j), 0.0)

                    # ignora depósito se configurado (redundante com 'nos', mas seguro)
                    if not incluir_deposito and (i in (dep0, depf) or j in (dep0, depf)):
                        v = 0.0

                    if abs(v) <= mostrar_so_maiores_que:
                        row_vals.append("   .   ")
                    else:
                        row_vals.append(f"{v:7.{casas}f}")
                print(f"{i:>3d} | " + " ".join(row_vals))

    def extrair_lambdas_do_modelo(sol_pool, lbd_vars):

        lbd_vals = {}
        for k, data in sol_pool.rotas.items():
            nrotas = len(data.get("sequencia_rota", []))
            lbd_vals[k] = [float(lbd_vars[k][p].X) for p in range(nrotas)]
        return lbd_vals

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

        # y[i,k,w] = 1 se o cliente i for atendido pelo veículo k na janela w
        y = {}

        for i in clientes:
            n_janelas = len(inst.noh[i].READY_TIME)
            for k in K:
                for w in range(n_janelas):
                    y[i, k, w] = model.addVar(vtype=GRB.BINARY, name=f'y_{i}_{k}_{w}')


        # Função objetivo: minimizar tempo total percorrido
        model.setObjective(
            # gp.quicksum(inst.matriz_distancia[i][j] * inst.veiculos[k].velocidade * x[i, j, k]  # FOO alterar FO
            gp.quicksum(inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade * x[i, j, k]  # FOO alterar FO
                        for k in K for i in V for j in V if i != j),
            GRB.MINIMIZE
        )
        model.Params.TimeLimit = 60
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

        # janelas de tempo múltiplas
        BIG_M = 1e5

        for k in K:
            # depósito inicial
            model.addConstr(s[0, k] == 0, f'inicio_zero_{k}')

            for i in V:
                # clientes: escolhe exatamente uma janela se o veículo visitar
                if i in clientes:
                    n_janelas = len(inst.noh[i].READY_TIME)

                    visita_ik = gp.quicksum(x[j, i, k] for j in V if j != i)

                    model.addConstr(
                        gp.quicksum(y[i, k, w] for w in range(n_janelas)) == visita_ik,
                        name=f'escolha_janela_{i}_{k}'
                    )

                    for w in range(n_janelas):
                        ready_w = inst.noh[i].READY_TIME[w]
                        due_w = inst.noh[i].DUE_DATE[w]

                        model.addConstr(
                            s[i, k] >= ready_w - BIG_M * (1 - y[i, k, w]),
                            name=f'tw_inicio_{i}_{k}_{w}'
                        )
                        model.addConstr(
                            s[i, k] <= due_w + BIG_M * (1 - y[i, k, w]),
                            name=f'tw_fim_{i}_{k}_{w}'
                        )

                # depósito final: pode usar a 1ª janela ou deixar frouxo
                elif i == inst.nbn - 1:
                    if len(inst.noh[i].READY_TIME) > 0:
                        model.addConstr(s[i, k] >= inst.noh[i].READY_TIME[0], f'tw_inicio_depfin_{k}')
                    if len(inst.noh[i].DUE_DATE) > 0:
                        model.addConstr(s[i, k] <= inst.noh[i].DUE_DATE[0], f'tw_fim_depfin_{k}')

                # propagação do tempo
                for j in V:
                    if i != j:
                        service = inst.noh[i].SERVICE_TIME[0] if hasattr(inst.noh[i], 'SERVICE_TIME') and inst.noh[
                            i].SERVICE_TIME else 0
                        travel = inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

                        model.addConstr(
                            s[i, k] + service + travel <= s[j, k] + BIG_M * (1 - x[i, j, k]),
                            name=f'tempo_chegada_{i}_{j}_{k}'
                        )


        model.write("modelo.lp")
        model.optimize()

        # Extração da solução, preenche bin_visitas para compatibilidade com sua estrutura
        #if model.status == GRB.OPTIMAL:
        if model.SolCount >0:
            # --- RESULTADOS DETALHADOS ---
            sol.custo = model.ObjVal

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

    # teste heuristica gulosa
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

    # fim da gulosa

    def gera_rotas_iniciaisUNICA(self, inst, sol, custo_alto=1e7):

        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))

        # sol.rotas = {}

        for k in range(inst.nbv):
            # inicializa listas para o veículo k
            # k=len(sol.rotas[ki])
            sol.rotas[k] = {
                'rotas_binaria': [],
                'sequencia_rota': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': [],
            }

            # === Rota cheia (coluna artificial forte) ===
            #random.shuffle(clientes)
            rota_cheia = [0] + list(range(1, inst.nbcd + 1)) + [depf]
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

            """
            print(
                "\n\n============================================================================= ITERACAO GLOBAL " + str(
                    globalIteration))
            """
            initerruptall = False

            model.optimize()
            # print("%%%%%%%%%%%%%%%%% iteracao " + str(self.total_iteracoes_CG))
            if model.Status != GRB.OPTIMAL:

                if nbIteracNoOpt < nbMAXIteracNoOpt:
                    nbIteracNoOpt += 1
                    # print("Problema mestre não resolvido/ótimo. Parando.")
                    # removo os cortes

                    # print("🧹 Removendo restrições de arco fixado DENTRO DA GC ...")

                    for (i, j, k) in arcos_fixados_em_1:
                        nome_restr = f"arco_fixado_{i}_{j}_{k}"
                        restr = model.getConstrByName(nome_restr)
                        if restr:
                            model.remove(restr)
                            # print(f"✔️ Removida: {nome_restr}")
                        # else:
                        # print(f"⚠️ Restrição {nome_restr} não encontrada no modelo.")

                    model.update()
                    model.optimize()

            else:

                # print("\n--- Solução Ótima Encontrada NO GC MESTRE ---")
                # print(f"Valor da Função Objetivo (Custo Total): {model.ObjVal:.4f}\n")

                # ==================================================================
                # INICIO Bloco para mostrar as colunas escolhidas na solução do mestre
                # ==================================================================
                # print(f"\n--- Colunas Escolhidas na Solução do Mestre (Iteração {self.total_iteracoes_CG}) ---")
                custo_total_iteracao = 0
                for k in sol.rotas.keys():  # range(inst.nbv):

                    for p in range(len(lbd[k])):

                        x_val = lbd[k][p].X

                        # Se o valor for maior que uma pequena tolerância, a coluna foi "usada"
                        if x_val > 1e-6:
                            # print(f"  Veículo {k}, Rota {p}:")
                            # print(f"    - Valor (lambda): {x_val:.4f}")

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

                            # print(f"    - Sequência: {sequencia}")
                            # print(f"    - Custo:     {custo_rota:.2f}")

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
                        # print("/n/n/n-------- PRIMEIRO MIP------------")

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

                            # print("--- Detalhes das Rotas Escolhidas (Solução Inteira-MIP 1) ---")
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

        """
        for (i, j) in arcos_fixados:
            if i in succ_fixo and succ_fixo[i] != j:
                return None, None  # conflito: 2 sucessores fixos
            if j in pred_fixo and pred_fixo[j] != i:
                return None, None  # conflito: 2 predecessores fixos
            succ_fixo[i] = j
            pred_fixo[j] = i
        """

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

                # =========================
                # EARLY TEST: fechar no depósito final
                # =========================
                if j != depf:

                    # 1) arco proibido?
                    if (j, depf) not in arcos_proibidos:

                        tempo_close = tempo_chegada + s[j] + travel_time(j, depf)

                        if tempo_close < a[depf]:
                            tempo_close = a[depf]

                        # 2) respeita janela do depósito?
                        if tempo_close <= b[depf]:

                            # custo reduzido ao fechar
                            custo_close = custo_mod_novo + travel_time(j, depf)
                            custo_close -= float(mu_arc.get((j, depf), 0.0))
                            custo_close -= float(sigma_k)

                            if custo_close < -1e-6:

                                # cria rótulo final temporário
                                rotulos.append({
                                    "no": depf,
                                    "tempo": tempo_close,
                                    "carga": nova_carga,
                                    "custo_mod": custo_close,
                                    "mask": nova_mask,
                                    "pai": idx_novo,
                                    "ativo": True
                                })

                                idx_final = len(rotulos) - 1

                                # reconstrói rota
                                rota_reversa = []
                                idx_tmp = idx_final
                                while idx_tmp is not None:
                                    rota_reversa.append(rotulos[idx_tmp]["no"])
                                    idx_tmp = rotulos[idx_tmp]["pai"]

                                rota = list(reversed(rota_reversa))

                                custo_real = 0.0
                                for t in range(len(rota) - 1):
                                    custo_real += travel_time(rota[t], rota[t + 1])

                                bin_xij = [0 for _ in range(nbcd)]
                                for v in rota:
                                    if 1 <= v <= nbcd:
                                        bin_xij[v - 1] = 1

                                return {
                                    "clientes": rota,
                                    "custo": custo_real,
                                    "bin_xij": bin_xij
                                }, custo_close

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

    def SUB_PROG_DINOK(self, inst, pi, sigma_k, k,
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

        # mu_arc = {}  # (i,j)->dual arco

        # arcos_proibidos = set()
        # arcos_fixados = set()

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

    def SUB_PROG_DIN_PW_CPP(self, inst, pi, sigma_k, k,
                            arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                            widening_seq=None, eps=1e-6):
        import sys
        import numpy as np
        from pathlib import Path

        # --- mesmo esquema de import do .pyd ---
        pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON" / "x64" / "Release"
        if not pyd_dir.exists():
            pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON" / "x64" / "Debug"
        if str(pyd_dir) not in sys.path:
            sys.path.insert(0, str(pyd_dir))

        import vrptw_pd

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}
        if widening_seq is None:
            widening_seq = [-1]  # -1 = ALL (sem widening)

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

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
            d[i] = float(getattr(noh, "DEMAND", 0.0))

        dist = np.asarray(inst.matriz_distancia, dtype=np.float64)
        tt = dist / vel

        pi_np = np.asarray(pi, dtype=np.float64)

        # Decide qual função chamar:
        # - se tiver proibidos/mu/fixados -> branch
        # - senão -> base
        tem_branch = (len(arcos_proibidos) > 0) or (len(arcos_fixados) > 0) or (len(mu_arc) > 0)

        if not tem_branch:
            return vrptw_pd.sub_prog_din_pw(
                tt, a.tolist(), b.tolist(), s.tolist(), d.tolist(),
                pi_np.tolist(),
                float(sigma_k), cap_k,
                int(nbcd), int(dep0), int(depf),
                list(map(int, widening_seq)),
                float(eps)
            )

        # --- branch: monta mu_flat e forbid_flat (nbn*nbn) ---
        mu_flat = np.zeros(nbn * nbn, dtype=np.float64)
        for (i, j), val in mu_arc.items():
            mu_flat[int(i) * nbn + int(j)] = float(val)

        forbid_flat = np.zeros(nbn * nbn, dtype=np.uint8)
        for (i, j) in arcos_proibidos:
            forbid_flat[int(i) * nbn + int(j)] = 1

        # required arcs (fixados) -> req_i/req_j
        # (limite atual no C++: m <= 16)
        req_i = [int(i) for (i, j) in arcos_fixados]
        req_j = [int(j) for (i, j) in arcos_fixados]

        return vrptw_pd.sub_prog_din_pw_branch_greedy(
            tt, a.tolist(), b.tolist(), s.tolist(), d.tolist(),
            pi_np.tolist(),
            float(sigma_k), cap_k,
            int(nbcd), int(dep0), int(depf),
            list(map(int, widening_seq)),
            float(eps),
            mu_flat.tolist(),
            forbid_flat.tolist(),
            req_i,
            req_j
        )

    def SUB_PROG_DINCPP(self, inst, pi, sigma_k, k,
                        arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        import sys
        import numpy as np
        from pathlib import Path

        pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON" / "x64" / "Release"
        if not pyd_dir.exists():
            pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON" / "x64" / "Debug"
        if str(pyd_dir) not in sys.path:
            sys.path.insert(0, str(pyd_dir))

        import vrptw_pd

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}  # dict {(i,j): mu}

        nbn = inst.nbn
        nbcd = inst.nbcd

        cap_k = float(inst.veiculos[k].capacidade)
        vel = float(inst.veiculos[k].velocidade)

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

        dist = np.asarray(inst.matriz_distancia, dtype=np.float64)
        tt = dist / vel

        # proibidos mp x 2 int32
        if len(arcos_proibidos) == 0:
            F = np.zeros((0, 2), dtype=np.int32)
        else:
            F = np.array(list(arcos_proibidos), dtype=np.int32).reshape(-1, 2)

        # fixados mf x 2 int32
        if len(arcos_fixados) == 0:
            FX = np.zeros((0, 2), dtype=np.int32)
        else:
            FX = np.array(list(arcos_fixados), dtype=np.int32).reshape(-1, 2)

        # mu_arc mm x 3 float64: (i, j, mu)
        if len(mu_arc) == 0:
            MU = np.zeros((0, 3), dtype=np.float64)
        else:
            MU = np.array([(int(i), int(j), float(v)) for (i, j), v in mu_arc.items()],
                          dtype=np.float64).reshape(-1, 3)

        pi_np = np.asarray(pi, dtype=np.float64)

        # se quiser ver o hello, precisa printar
        # print(vrptw_pd.hello())

        return vrptw_pd.SUB_PROG_DIN(tt, a, b, s, d, pi_np, float(sigma_k), cap_k, F, FX, MU)

    def SUB_PROG_DINCPP0202(self, inst, pi, sigma_k, k,
                            arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        import sys
        import numpy as np
        from pathlib import Path

        # 1) apontar para a pasta do .pyd
        pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "x64" / "Release"
        if not pyd_dir.exists():
            pyd_dir = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "x64" / "Debug"

        if str(pyd_dir) not in sys.path:
            sys.path.insert(0, str(pyd_dir))

        import vrptw_pd  # seu módulo .pyd

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}  # (i,j)->dual

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
            a[i] = noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0
            b[i] = noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else 1e18
            s[i] = noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0
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

        # MU: mm x 3  (i,j,mu)
        if len(mu_arc) == 0:
            MU = np.zeros((0, 3), dtype=np.float64)
        else:
            MU = np.empty((len(mu_arc), 3), dtype=np.float64)
            for r, ((i, j), val) in enumerate(mu_arc.items()):
                MU[r, 0] = float(i)
                MU[r, 1] = float(j)
                MU[r, 2] = float(val)

        # pi
        pi_np = np.asarray(pi, dtype=np.float64)

        # chamada C++
        return vrptw_pd.SUB_PROG_DIN(
            tt, a, b, s, d,
            pi_np, float(sigma_k), cap_k,
            F, FX, MU
        )

    def registrar_novo_corte(self, iteracao, indice_corte, i, j, k, nome_arquivo="log_gc.txt"):

        with open(nome_arquivo, "a", encoding="utf-8") as f:
            linha = (
                f"{iteracao}; corte{indice_corte} [{i},{j},{k}]; "
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            )
            f.write(linha)
