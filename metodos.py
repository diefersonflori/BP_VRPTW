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
import statistics
import itertools
from collections import defaultdict

# ápara o c++
import subprocess
from pathlib import Path

from sqlalchemy import false

from instancia import Instancia
from solucao import Solucao
from avaliador_rota import AVALIADOR_ROTA_PADRAO

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
        self.lb_confiavel_HERDADO = False

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

        ######
        # melhores valores encontrados durante a GC do nó
        self.melhor_lp_com_slack = float("inf")
        self.melhor_lp_com_slack_iter = None

        self.melhor_lp_valido = float("inf")
        self.melhor_lp_valido_iter = None
        self.melhor_lp_valido_rotas = []

        self.melhor_int = float("inf")
        self.melhor_int_iter = None
        self.melhor_int_rotas = []

        # marcos
        self.achou_lp_target = False
        self.achou_int_target = False
        self.iter_lp_target = None
        self.iter_int_target = None
        self.tempo_lp_target = None
        self.tempo_int_target = None
        self.pricing_timeout = False
        ######

        # centro local da caixa de estabilizacao (secao TAREFA 2): pertence ao
        # no, nao ao sol_pool global; None ate ser inicializado (raiz) ou
        # herdado por copia independente (filhos)
        self.pi_bar = None

    def criaMatriRC(self, inst):
        self.matriz_rc = {
            k: [[0.0] * inst.nbn for _ in range(inst.nbn)] for k in range(inst.nbv)
        }


class Metodos:

    def criar_pool_artificial_sequencial(self, inst, sol_pool, custo_artificial=1_000_000.0, k_artificial=0):
        """Cria um RMP inicial de Fase I:

        - uma única coluna artificial cobre todos os pedidos, na ordem 1,2,...,nbcd;
        - a coluna artificial pertence somente ao veículo k_artificial;
        - todos os veículos recebem uma coluna ociosa [0, depf];
        - nenhuma solução artificial pode ser aceita como UB pelos MIPs.
        """

        if inst.nbv <= 0:
            raise ValueError("A instância não possui veículos.")

        if not 0 <= k_artificial < inst.nbv:
            raise ValueError(
                f"k_artificial inválido: {k_artificial}. "
                f"Use um valor entre 0 e {inst.nbv - 1}."
            )

        if custo_artificial <= 0:
            raise ValueError("O custo artificial deve ser positivo.")

        nbcd = inst.nbcd
        depf = inst.nbn - 1

        # Inicializa toda a estrutura do pool.
        # Não depende de init_pool_vazio, pois precisamos garantir a chave artificial.
        sol_pool.rotas = {}

        for k in range(inst.nbv):
            sol_pool.rotas[k] = {
                "sequencia_rota": [],
                "rotas_binaria": [],
                "custo": [],
                "vezes_usada_geral": [],
                "vezes_usada_otimo": [],
                "lbd_iteracao": [],
                "artificial": [],
            }

        # Coluna artificial cobrindo todos os pedidos.
        seq_artificial = [0] + list(range(1, nbcd + 1)) + [depf]
        binaria_artificial = [1] * nbcd

        dados = sol_pool.rotas[k_artificial]
        dados["sequencia_rota"].append(seq_artificial)
        dados["rotas_binaria"].append(binaria_artificial)
        dados["custo"].append(float(custo_artificial))
        dados["vezes_usada_geral"].append(0)
        dados["vezes_usada_otimo"].append(0)
        dados["lbd_iteracao"].append([])
        dados["artificial"].append(True)

        # Inclui [0, depf] para todos os veículos, inclusive o veículo artificial.
        self.adiciona_colunas_ociosas(inst, sol_pool)

        sol_pool.numero_de_rotas = [
            len(sol_pool.rotas[k]["sequencia_rota"])
            for k in range(inst.nbv)
        ]

        print("=" * 78)
        print("[POOL INICIAL ARTIFICIAL SEQUENCIAL]")
        print(f"Veículo artificial: {k_artificial}")
        print(f"Custo artificial: {custo_artificial:.1f}")
        print(f"Pedidos cobertos: {nbcd}")
        print(f"Sequência: {seq_artificial}")

        for k in range(inst.nbv):
            print(
                f"  k={k} | colunas={len(sol_pool.rotas[k]['sequencia_rota'])} | "
                f"rotas={sol_pool.rotas[k]['sequencia_rota']} | "
                f"artificial={sol_pool.rotas[k]['artificial']}"
            )

        print("=" * 78)

        return {
            "k_artificial": k_artificial,
            "custo_artificial": float(custo_artificial),
            "sequencia_artificial": seq_artificial,
            "n_colunas": sum(
                len(sol_pool.rotas[k]["sequencia_rota"])
                for k in range(inst.nbv)
            ),
        }

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
        self.printarsol = True
        self.printarsoldual = True

        # estabilizacao
        self.pi_antigo = []
        self._ultimo_timeout_cpp = False

        # avaliacao de rota centralizada (sem estado -> reutiliza instancia compartilhada)
        self.avaliador_rota = AVALIADOR_ROTA_PADRAO

        # multi-column pricing: limites centralizados (facil de alterar aqui, sem tocar main.py)
        self.MAX_CANDIDATAS_PRICING = 20   # candidatas negativas ineditas que um pricing tenta reunir
        self.MAX_COLUNAS_NOVAS_ITER = 50    # colunas novas aceitas no pool por iteracao de CG
        self.MAX_COLUNAS_NOVAS_VEICULO = 2  # colunas novas aceitas no pool por veiculo na mesma iteracao

        # PD_SILVA_CPP/BID_SILVA_CPP (pipeline silva2024 -- secao 10/11 da
        # integracao no B&P): defaults SEPARADOS de PRICING_EXATO_MAX_LABELS
        # (Petro/Solomon, definido em main.py, tipicamente ~1e9) -- o teste
        # de escala do PD_SILVA_CPP mostrou ~1.35 GB em 10 milhoes de labels,
        # entao NAO reaproveitar aquele valor aqui. Podem ser sobrescritos
        # por instancia via inst.silva_pd_cpp_max_labels/silva_pd_cpp_timeout_s.
        self.SILVA_PD_CPP_MAX_LABELS = 3_000_000
        self.SILVA_PD_CPP_TIMEOUT_S = 5.0
        self.SILVA_BID_CPP_MAX_LABELS_POR_NO = 60  # mesmo default conceitual de SUB_PROG_BID_SILVA

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

    def gera_rotas_iniciais_inteligente_inteira(self, inst, sol, custo_artificial=1e6):
        nbcd = inst.nbcd
        depf = inst.nbn - 1

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def demand(i):
            return getattr(inst.noh[i], 'DEMAND', 0.0)

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0

        def travel(k, i, j):
            return self.avaliador_rota.tempo_viagem(inst, k, i, j)

        def custo_seq(k, seq):
            return self.avaliador_rota.custo_rota(inst, k, seq)

        def avaliar_seq(k, seq):
            return self.avaliador_rota.avaliar_rota(inst, k, seq).viavel

        def binaria_seq(seq):
            binaria = [0] * nbcd
            for no in seq:
                if 1 <= no <= nbcd:
                    binaria[no - 1] = 1
            return binaria

        def melhor_insercao(k, seq, cliente):
            melhor = None

            for pos in range(1, len(seq)):
                nova = seq[:pos] + [cliente] + seq[pos:]

                if not avaliar_seq(k, nova):
                    continue

                delta = custo_seq(k, nova) - custo_seq(k, seq)
                score = delta + 0.001 * due(cliente)

                if melhor is None or score < melhor[0]:
                    melhor = (score, nova)

            return melhor

        sol.rotas = {}

        for k in range(inst.nbv):
            sol.rotas[k] = {
                'sequencia_rota': [],
                'rotas_binaria': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': [],
                'artificial': [],
            }

        import itertools as _it3

        # Geographic clustering: divide clients into nbv angle-based sectors from depot
        _dep_x = inst.noh[0].XCOORD
        _dep_y = inst.noh[0].YCOORD
        _cli_angles = {
            c: math.atan2(inst.noh[c].YCOORD - _dep_y, inst.noh[c].XCOORD - _dep_x)
            for c in range(1, nbcd + 1)
        }
        _sorted_by_angle = sorted(range(1, nbcd + 1), key=lambda c: _cli_angles[c])
        def _run_pipeline(strategy_name, seed_key, zone_seed_key, forced_seeds=None):
            rotas = {}
            for k in range(inst.nbv):
                rotas[k] = {
                    'sequencia_rota': [], 'rotas_binaria': [], 'custo': [],
                    'vezes_usada_geral': [], 'vezes_usada_otimo': [],
                    'lbd_iteracao': [], 'artificial': [],
                }

            nao = set(range(1, nbcd + 1))

            # Fresh home-zone per strategy call — no shared mutable state across strategies
            home_zone = {}
            for _k in range(inst.nbv):
                _s = round(_k * nbcd / inst.nbv)
                _e = round((_k + 1) * nbcd / inst.nbv)
                home_zone[_k] = set(_sorted_by_angle[_s:_e])

            # Seeding: prefer earliest-due client from each vehicle's home zone;
            #          fall back to global seed_key order if zone yields no feasible seed
            seq_ini = {k: [0, depf] for k in range(inst.nbv)}
            for k in range(inst.nbv):
                seeded = False
                if forced_seeds is not None and k in forced_seeds:
                    cli = forced_seeds[k]
                    if cli in nao and avaliar_seq(k, [0, cli, depf]):
                        seq_ini[k] = [0, cli, depf]
                        nao.discard(cli)
                        seeded = True
                if not seeded:
                    for cli in sorted(home_zone[k] & nao, key=zone_seed_key):
                        if avaliar_seq(k, [0, cli, depf]):
                            seq_ini[k] = [0, cli, depf]
                            nao.discard(cli)
                            seeded = True
                            break
                    if not seeded:
                        for cli in sorted(nao, key=seed_key):
                            if avaliar_seq(k, [0, cli, depf]):
                                seq_ini[k] = [0, cli, depf]
                                nao.discard(cli)
                                break

            # Per-vehicle insertion: phase 1 fills from home zone, phase 2 opens to all
            for k in range(inst.nbv):
                seq = seq_ini[k]
                # Phase 1: home-zone clients only
                mudou = True
                while mudou and nao:
                    zone_nao = home_zone[k] & nao
                    if not zone_nao:
                        break
                    mudou = False
                    mg = None
                    for cli in sorted(zone_nao, key=due):
                        ins = melhor_insercao(k, seq, cli)
                        if ins is None:
                            continue
                        score, nova = ins
                        if mg is None or score < mg[0]:
                            mg = (score, cli, nova)
                    if mg is not None:
                        _, cli_add, seq = mg
                        nao.remove(cli_add)
                        mudou = True
                # Phase 2: any remaining client (original logic)
                mudou = True
                while mudou and nao:
                    mudou = False
                    mg = None
                    for cli in sorted(nao, key=due):
                        ins = melhor_insercao(k, seq, cli)
                        if ins is None:
                            continue
                        score, nova = ins
                        if mg is None or score < mg[0]:
                            mg = (score, cli, nova)
                    if mg is not None:
                        _, cli_add, seq = mg
                        nao.remove(cli_add)
                        mudou = True
                rotas[k]['sequencia_rota'].append(seq)
                rotas[k]['rotas_binaria'].append(binaria_seq(seq))
                rotas[k]['custo'].append(custo_seq(k, seq))
                rotas[k]['vezes_usada_geral'].append(0)
                rotas[k]['vezes_usada_otimo'].append(0)
                rotas[k]['lbd_iteracao'].append([])
                rotas[k]['artificial'].append(False)

            # Sobras
            mudou = True
            while mudou and nao:
                mudou = False
                for cli in sorted(nao, key=due):
                    mg = None
                    for k in range(inst.nbv):
                        seq = rotas[k]['sequencia_rota'][0]
                        ins = melhor_insercao(k, seq, cli)
                        if ins is None:
                            continue
                        score, nova = ins
                        if mg is None or score < mg[0]:
                            mg = (score, k, nova)
                    if mg is not None:
                        _, kb, nova = mg
                        rotas[kb]['sequencia_rota'][0] = nova
                        rotas[kb]['rotas_binaria'][0] = binaria_seq(nova)
                        rotas[kb]['custo'][0] = custo_seq(kb, nova)
                        nao.remove(cli)
                        mudou = True

            # 2-swap
            changed = True
            while changed and nao:
                changed = False
                best_sw = None
                for cli in sorted(nao, key=due):
                    for k in range(inst.nbv):
                        seq_k = rotas[k]['sequencia_rota'][0]
                        cost_k_orig = custo_seq(k, seq_k)
                        int_k = [n for n in seq_k if 1 <= n <= nbcd]
                        for vic in int_k:
                            vi = seq_k.index(vic)
                            swout = seq_k[:vi] + seq_k[vi + 1:]
                            bpc = None; bcc = float("inf")
                            for p in range(1, len(swout)):
                                nv = swout[:p] + [cli] + swout[p:]
                                if avaliar_seq(k, nv):
                                    c = custo_seq(k, nv)
                                    if c < bcc:
                                        bcc = c; bpc = p
                            if bpc is None:
                                continue
                            skwc = swout[:bpc] + [cli] + swout[bpc:]
                            for m in range(inst.nbv):
                                st = skwc if m == k else rotas[m]['sequencia_rota'][0]
                                cmo = bcc if m == k else custo_seq(m, st)
                                for p2 in range(1, len(st)):
                                    nv2 = st[:p2] + [vic] + st[p2:]
                                    if not avaliar_seq(m, nv2):
                                        continue
                                    cn2 = custo_seq(m, nv2)
                                    if m == k:
                                        d = cn2 - cost_k_orig; skf, smf = nv2, nv2
                                    else:
                                        d = (bcc - cost_k_orig) + (cn2 - cmo); skf, smf = skwc, nv2
                                    if best_sw is None or d < best_sw[0]:
                                        best_sw = (d, cli, k, skf, m, smf)
                if best_sw is not None:
                    _, csw, ksw, sksw, msw, smsw = best_sw
                    rotas[ksw]['sequencia_rota'][0] = sksw
                    rotas[ksw]['rotas_binaria'][0] = binaria_seq(sksw)
                    rotas[ksw]['custo'][0] = custo_seq(ksw, sksw)
                    if msw != ksw:
                        rotas[msw]['sequencia_rota'][0] = smsw
                        rotas[msw]['rotas_binaria'][0] = binaria_seq(smsw)
                        rotas[msw]['custo'][0] = custo_seq(msw, smsw)
                    nao.remove(csw)
                    changed = True

            # 3-swap
            changed3 = True
            while changed3 and nao:
                changed3 = False
                best_sw3 = None
                for cli in sorted(nao, key=due):
                    dcli = demand(cli)
                    for k in range(inst.nbv):
                        seq_k = rotas[k]['sequencia_rota'][0]
                        cost_k_orig = custo_seq(k, seq_k)
                        int_k = [n for n in seq_k if 1 <= n <= nbcd]
                        for v1, v2 in _it3.combinations(int_k, 2):
                            if demand(v1) + demand(v2) < dcli:
                                continue
                            swout = [n for n in seq_k if n != v1 and n != v2]
                            bpc = None; bcc = float("inf")
                            for p in range(1, len(swout)):
                                nv = swout[:p] + [cli] + swout[p:]
                                if avaliar_seq(k, nv):
                                    c = custo_seq(k, nv)
                                    if c < bcc:
                                        bcc = c; bpc = p
                            if bpc is None:
                                continue
                            skwc = swout[:bpc] + [cli] + swout[bpc:]
                            bv1 = None
                            for m1 in range(inst.nbv):
                                st1 = skwc if m1 == k else rotas[m1]['sequencia_rota'][0]
                                ct1 = bcc if m1 == k else custo_seq(m1, st1)
                                for p1 in range(1, len(st1)):
                                    nv1 = st1[:p1] + [v1] + st1[p1:]
                                    if avaliar_seq(m1, nv1):
                                        d1 = custo_seq(m1, nv1) - ct1
                                        if bv1 is None or d1 < bv1[0]:
                                            bv1 = (d1, m1, nv1)
                            if bv1 is None:
                                continue
                            dv1, m1b, sm1 = bv1
                            bv2 = None
                            for m2 in range(inst.nbv):
                                if m1b == k and m2 == k:
                                    st2 = sm1; ct2 = custo_seq(m2, st2)
                                elif m2 == k:
                                    st2 = skwc; ct2 = bcc
                                elif m2 == m1b:
                                    st2 = sm1; ct2 = custo_seq(m2, st2)
                                else:
                                    st2 = rotas[m2]['sequencia_rota'][0]; ct2 = custo_seq(m2, st2)
                                for p2 in range(1, len(st2)):
                                    nv2 = st2[:p2] + [v2] + st2[p2:]
                                    if avaliar_seq(m2, nv2):
                                        d2 = custo_seq(m2, nv2) - ct2
                                        if bv2 is None or d2 < bv2[0]:
                                            bv2 = (d2, m2, nv2)
                            if bv2 is None:
                                continue
                            dv2, m2b, sm2 = bv2
                            td = (bcc - cost_k_orig) + dv1 + dv2
                            if m2b == k and m1b == k:
                                rch = {k: sm2}
                            elif m2b == k:
                                rch = {k: sm2, m1b: sm1}
                            elif m1b == k:
                                rch = {k: sm1, m2b: sm2}
                            elif m2b == m1b:
                                rch = {k: skwc, m1b: sm2}
                            else:
                                rch = {k: skwc, m1b: sm1, m2b: sm2}
                            if best_sw3 is None or td < best_sw3[0]:
                                best_sw3 = (td, cli, rch)
                if best_sw3 is not None:
                    _, csw3, rch = best_sw3
                    for rk, rs in rch.items():
                        rotas[rk]['sequencia_rota'][0] = rs
                        rotas[rk]['rotas_binaria'][0] = binaria_seq(rs)
                        rotas[rk]['custo'][0] = custo_seq(rk, rs)
                    nao.remove(csw3)
                    changed3 = True

            # Or-opt improvement phase: relocate segments (1, 2, 3 clients) to other routes;
            #   also retry inserting any remaining unassigned clients each pass
            or_improved = True
            while or_improved:
                or_improved = False

                # Retry inserting remaining unassigned clients (any feasible position accepted)
                for cli in sorted(list(nao), key=due):
                    for k2 in range(inst.nbv):
                        seq2 = rotas[k2]['sequencia_rota'][0]
                        for pos in range(1, len(seq2)):
                            nova2 = seq2[:pos] + [cli] + seq2[pos:]
                            if avaliar_seq(k2, nova2):
                                rotas[k2]['sequencia_rota'][0] = nova2
                                rotas[k2]['rotas_binaria'][0] = binaria_seq(nova2)
                                rotas[k2]['custo'][0] = custo_seq(k2, nova2)
                                nao.discard(cli)
                                or_improved = True
                                break
                        if cli not in nao:
                            break

                # Or-opt-1/2/3: first-improving inter-route segment relocation
                found = False
                for seg_len in (1, 2, 3):
                    if found:
                        break
                    for k in range(inst.nbv):
                        if found:
                            break
                        seq_k = rotas[k]['sequencia_rota'][0]
                        int_k = [n for n in seq_k if 1 <= n <= nbcd]
                        if len(int_k) <= seg_len:
                            continue
                        for i in range(1, len(seq_k) - seg_len):
                            if found:
                                break
                            seg = seq_k[i:i + seg_len]
                            if not all(1 <= n <= nbcd for n in seg):
                                continue
                            origin_wo = seq_k[:i] + seq_k[i + seg_len:]
                            if not avaliar_seq(k, origin_wo):
                                continue
                            cost_orig_k = custo_seq(k, seq_k)
                            cost_new_k = custo_seq(k, origin_wo)
                            for k2 in range(inst.nbv):
                                if found:
                                    break
                                if k2 == k:
                                    continue
                                seq_k2 = rotas[k2]['sequencia_rota'][0]
                                cost_orig_k2 = custo_seq(k2, seq_k2)
                                for pos in range(1, len(seq_k2)):
                                    nova_k2 = seq_k2[:pos] + seg + seq_k2[pos:]
                                    if avaliar_seq(k2, nova_k2):
                                        cost_new_k2 = custo_seq(k2, nova_k2)
                                        delta = (cost_new_k - cost_orig_k) + (cost_new_k2 - cost_orig_k2)
                                        if delta < -1e-9:
                                            rotas[k]['sequencia_rota'][0] = origin_wo
                                            rotas[k]['rotas_binaria'][0] = binaria_seq(origin_wo)
                                            rotas[k]['custo'][0] = cost_new_k
                                            rotas[k2]['sequencia_rota'][0] = nova_k2
                                            rotas[k2]['rotas_binaria'][0] = binaria_seq(nova_k2)
                                            rotas[k2]['custo'][0] = cost_new_k2
                                            or_improved = True
                                            found = True
                                            break

            # Fallback artificial
            if nao:
                print("ATENÇÃO: clientes não couberam em rotas reais.")
                print("Criando rota artificial para garantir solução inteira inicial.")
                print("Clientes artificiais:", sorted(nao))
                kb = min(range(inst.nbv), key=lambda k: len(rotas[k]['sequencia_rota'][0]))
                sa = rotas[kb]['sequencia_rota'][0]
                ca = [i for i in sa if 1 <= i <= nbcd]
                seq_art = [0] + ca + sorted(nao) + [depf]
                rotas[kb]['sequencia_rota'][0] = seq_art
                rotas[kb]['rotas_binaria'][0] = binaria_seq(seq_art)
                rotas[kb]['custo'][0] = custo_seq(kb, seq_art) + custo_artificial
                rotas[kb]['artificial'][0] = True

            # Reorder+relocate: for each artificial route, try removing one client at a time
            #   and find a valid permutation of the remaining (n-1) clients; if found,
            #   insert the removed client into any other route and unmark as artificial
            for k in range(inst.nbv):
                if not rotas[k]['artificial'][0]:
                    continue
                seq_k = rotas[k]['sequencia_rota'][0]
                clients_k = [n for n in seq_k if 1 <= n <= nbcd]
                if len(clients_k) > 8 or len(clients_k) < 2:
                    continue
                fixed = False
                for drop_idx in range(len(clients_k)):
                    if fixed:
                        break
                    dropped = clients_k[drop_idx]
                    subset = [c for i, c in enumerate(clients_k) if i != drop_idx]
                    for perm in _it3.permutations(subset):
                        if fixed:
                            break
                        new_seq_k = [0] + list(perm) + [depf]
                        if not avaliar_seq(k, new_seq_k):
                            continue
                        for k2 in range(inst.nbv):
                            if fixed or k2 == k:
                                continue
                            seq_k2 = rotas[k2]['sequencia_rota'][0]
                            for pos in range(1, len(seq_k2)):
                                nova_k2 = seq_k2[:pos] + [dropped] + seq_k2[pos:]
                                if avaliar_seq(k2, nova_k2):
                                    rotas[k]['sequencia_rota'][0] = new_seq_k
                                    rotas[k]['rotas_binaria'][0] = binaria_seq(new_seq_k)
                                    rotas[k]['custo'][0] = custo_seq(k, new_seq_k)
                                    rotas[k]['artificial'][0] = False
                                    rotas[k2]['sequencia_rota'][0] = nova_k2
                                    rotas[k2]['rotas_binaria'][0] = binaria_seq(nova_k2)
                                    rotas[k2]['custo'][0] = custo_seq(k2, nova_k2)
                                    fixed = True
                                    break
                            if fixed:
                                break

            n_art = sum(1 for k in range(inst.nbv) if rotas[k]['artificial'][0])
            c_art = sum(rotas[k]['custo'][0] for k in range(inst.nbv) if rotas[k]['artificial'][0])
            return rotas, n_art, c_art

        # EDF seeding: earliest deadline first, window width as tiebreak
        rotas_edf, n_art_edf, cost_art_edf = _run_pipeline(
            "EDF",
            lambda c: (due(c), due(c) - ready(c)),
            zone_seed_key=lambda c: (due(c), due(c) - ready(c)))
        print(f"[INTEIRA] EDF: {n_art_edf} art, custo_art={cost_art_edf:.2f}")

        # Balanced seeding: highest demand first, earliest due as tiebreak
        rotas_bal, n_art_bal, cost_art_bal = _run_pipeline(
            "Balanced",
            lambda c: (-demand(c), due(c)),
            zone_seed_key=lambda c: due(c) - demand(c))
        print(f"[INTEIRA] Balanced: {n_art_bal} art, custo_art={cost_art_bal:.2f}")

        # Sector seeding: one evenly-spaced seed per vehicle from the angle-sorted list
        _sector_seeds = {
            k: _sorted_by_angle[int(k * nbcd / inst.nbv)]
            for k in range(inst.nbv)
        }
        rotas_sec, n_art_sec, cost_art_sec = _run_pipeline(
            "Sector",
            lambda c: (due(c), due(c) - ready(c)),
            zone_seed_key=lambda c: (due(c), due(c) - ready(c)),
            forced_seeds=_sector_seeds)
        print(f"[INTEIRA] Sector: {n_art_sec} art, custo_art={cost_art_sec:.2f}")

        # LateIsolated seeding: EDF order for the first K-1 seeds; K-th seed is the client
        #   in positions [K, 2K) of the EDF ranking with the highest due * dist(depot) score
        _K = inst.nbv
        _edf_order = sorted(range(1, nbcd + 1), key=lambda c: (due(c), due(c) - ready(c)))
        _late_seeds = {}
        for k in range(_K - 1):
            _late_seeds[k] = _edf_order[k]
        _pool_start = _K
        _pool_end = min(2 * _K, nbcd)
        if _pool_start < _pool_end:
            _last_seed = max(
                _edf_order[_pool_start:_pool_end],
                key=lambda c: due(c) * inst.matriz_distancia[0][c]
            )
        else:
            _last_seed = _edf_order[_K - 1] if _K - 1 < nbcd else _edf_order[-1]
        _late_seeds[_K - 1] = _last_seed
        rotas_lat, n_art_lat, cost_art_lat = _run_pipeline(
            "LateIsolated",
            lambda c: (due(c), due(c) - ready(c)),
            zone_seed_key=lambda c: (due(c), due(c) - ready(c)),
            forced_seeds=_late_seeds)
        print(f"[INTEIRA] LateIsolated: {n_art_lat} art, custo_art={cost_art_lat:.2f}")

        # BalancedGlobal seeding: top K clients by (due - demand, due) globally, ignoring home zones
        _bg_order = sorted(range(1, nbcd + 1), key=lambda c: (due(c) - demand(c), due(c)))
        _bg_seeds = {k: _bg_order[k] for k in range(inst.nbv)}
        rotas_bg, n_art_bg, cost_art_bg = _run_pipeline(
            "BalancedGlobal",
            lambda c: (due(c) - demand(c), due(c)),
            zone_seed_key=lambda c: (due(c) - demand(c), due(c)),
            forced_seeds=_bg_seeds)
        print(f"[INTEIRA] BalancedGlobal: {n_art_bg} art, custo_art={cost_art_bg:.2f}")

        # Regret-2 seeding: greedy construction ordered by regret score
        _sol_rg = Solucao(inst.nbv, inst.nbcd)
        n_art_rg, cost_art_rg = self.gera_rotas_iniciais_regret(inst, _sol_rg)
        rotas_rg = _sol_rg.rotas

        # Keep the best result among all six strategies
        _candidates = [
            (n_art_edf, cost_art_edf, rotas_edf, "EDF (due asc)"),
            (n_art_bal, cost_art_bal, rotas_bal, "Balanced (demand desc)"),
            (n_art_sec, cost_art_sec, rotas_sec, "Sector (angle)"),
            (n_art_lat, cost_art_lat, rotas_lat, "LateIsolated"),
            (n_art_bg,  cost_art_bg,  rotas_bg,  "BalancedGlobal"),
            (n_art_rg,  cost_art_rg,  rotas_rg,  "Regret2"),
        ]
        _best = min(_candidates, key=lambda x: (x[0], x[1]))
        sol.rotas = _best[2]
        print(f"[INTEIRA] VENCEDOR: {_best[3]} — {_best[0]} art")

        sol.numero_de_rotas = [len(sol.rotas[k]['sequencia_rota']) for k in range(inst.nbv)]

        print("\n=== ROTAS INICIAIS INTEIRAS ===")
        custo_total = 0.0
        for k in range(inst.nbv):
            seq = sol.rotas[k]['sequencia_rota'][0]
            custo = sol.rotas[k]['custo'][0]
            art = sol.rotas[k]['artificial'][0]
            custo_total += custo
            print(f"Veículo {k}: {seq}")
            print(f"  custo = {custo:.4f} | artificial = {art}")

        print(f"Custo inicial inteiro = {custo_total:.4f}")

        return sol.rotas

    def gera_rotas_iniciais_regret(self, inst, sol, custo_artificial=1e6):
        import itertools as _itr
        nbcd = inst.nbcd
        depf = inst.nbn - 1    # final depot node index

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def demand(i):
            return getattr(inst.noh[i], 'DEMAND', 0.0)

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0

        def travel(k, i, j):
            return self.avaliador_rota.tempo_viagem(inst, k, i, j)

        def custo_seq(k, seq):
            return self.avaliador_rota.custo_rota(inst, k, seq)

        def avaliar_seq(k, seq):
            return self.avaliador_rota.avaliar_rota(inst, k, seq).viavel

        def binaria_seq(seq):
            b = [0] * nbcd
            for n in seq:
                if 1 <= n <= nbcd:
                    b[n - 1] = 1
            return b

        # STEP 1: Initialize — one empty route per vehicle, no zone clustering
        rotas = {}
        for k in range(inst.nbv):
            rotas[k] = {
                'sequencia_rota': [[0, depf]],
                'rotas_binaria': [[0] * nbcd],
                'custo': [0.0],
                'vezes_usada_geral': [0],
                'vezes_usada_otimo': [0],
                'lbd_iteracao': [[]],
                'artificial': [False],
            }

        assigned = set()

        # STEP 2: EDF Seeds — strictly assign the k-th EDF client as seed of vehicle k
        # No greedy first-feasible search; each vehicle gets exactly one candidate.
        edf_order = sorted(range(1, nbcd + 1), key=lambda c: (due(c), due(c) - ready(c)))
        for k in range(inst.nbv):
            if k >= len(edf_order):
                break
            c = edf_order[k]
            if avaliar_seq(k, [0, c, depf]):
                rotas[k]['sequencia_rota'][0] = [0, c, depf]
                rotas[k]['rotas_binaria'][0] = binaria_seq([0, c, depf])
                rotas[k]['custo'][0] = custo_seq(k, [0, c, depf])
                assigned.add(c)
            # else: vehicle k stays with empty route [0, depf]

        # STEP 3: Regret-2 insertion loop
        remaining = [c for c in range(1, nbcd + 1) if c not in assigned]

        while remaining:
            best_c = None
            best_regret = -float('inf')
            best_k = None
            best_pos = None

            for c in remaining:
                feasible = []
                for k in range(inst.nbv):
                    seq = rotas[k]['sequencia_rota'][0]
                    cost_k = custo_seq(k, seq)
                    for pos in range(1, len(seq)):
                        nova = seq[:pos] + [c] + seq[pos:]
                        if avaliar_seq(k, nova):
                            delta = custo_seq(k, nova) - cost_k
                            feasible.append((delta, k, pos))

                feasible.sort(key=lambda x: x[0])

                if len(feasible) == 0:
                    regret = float('inf')
                    c_k = None
                    c_pos = None
                elif len(feasible) == 1:
                    regret = feasible[0][0] + 1000
                    c_k = feasible[0][1]
                    c_pos = feasible[0][2]
                else:
                    regret = feasible[1][0] - feasible[0][0]
                    c_k = feasible[0][1]
                    c_pos = feasible[0][2]

                if regret > best_regret:
                    best_regret = regret
                    best_c = c
                    best_k = c_k
                    best_pos = c_pos

            remaining.remove(best_c)

            if best_k is None:
                # No feasible position anywhere: create artificial route [0, c*, depf].
                # Prefer a vehicle with an empty route to avoid displacing assigned clients.
                kb = next(
                    (k for k in range(inst.nbv)
                     if len([n for n in rotas[k]['sequencia_rota'][0] if 1 <= n <= nbcd]) == 0),
                    min(range(inst.nbv),
                        key=lambda k: len([n for n in rotas[k]['sequencia_rota'][0] if 1 <= n <= nbcd]))
                )
                seq_antiga = rotas[kb]['sequencia_rota'][0]
                clientes_antigos = [n for n in seq_antiga if 1 <= n <= nbcd]
                seq_art = [0] + clientes_antigos + [best_c] + [depf]
                rotas[kb]['sequencia_rota'][0] = seq_art
                rotas[kb]['rotas_binaria'][0] = binaria_seq(seq_art)
                rotas[kb]['custo'][0] = custo_seq(kb, seq_art) + custo_artificial
                rotas[kb]['artificial'][0] = True
            else:
                seq = rotas[best_k]['sequencia_rota'][0]
                nova = seq[:best_pos] + [best_c] + seq[best_pos:]
                rotas[best_k]['sequencia_rota'][0] = nova
                rotas[best_k]['rotas_binaria'][0] = binaria_seq(nova)
                rotas[best_k]['custo'][0] = custo_seq(best_k, nova)

        # STEP 4a: Or-opt improvement — first-improving inter-route segment relocation
        or_improved = True
        while or_improved:
            or_improved = False
            found = False
            for seg_len in (1, 2, 3):
                if found:
                    break
                for k in range(inst.nbv):
                    if found:
                        break
                    seq_k = rotas[k]['sequencia_rota'][0]
                    int_k = [n for n in seq_k if 1 <= n <= nbcd]
                    if len(int_k) <= seg_len:
                        continue
                    for i in range(1, len(seq_k) - seg_len):
                        if found:
                            break
                        seg = seq_k[i:i + seg_len]
                        if not all(1 <= n <= nbcd for n in seg):
                            continue
                        origin_wo = seq_k[:i] + seq_k[i + seg_len:]
                        if not avaliar_seq(k, origin_wo):
                            continue
                        cost_orig_k = custo_seq(k, seq_k)
                        cost_new_k = custo_seq(k, origin_wo)
                        for k2 in range(inst.nbv):
                            if found or k2 == k:
                                continue
                            seq_k2 = rotas[k2]['sequencia_rota'][0]
                            cost_orig_k2 = custo_seq(k2, seq_k2)
                            for pos in range(1, len(seq_k2)):
                                nova_k2 = seq_k2[:pos] + seg + seq_k2[pos:]
                                if avaliar_seq(k2, nova_k2):
                                    cost_new_k2 = custo_seq(k2, nova_k2)
                                    delta = (cost_new_k - cost_orig_k) + (cost_new_k2 - cost_orig_k2)
                                    if delta < -1e-9:
                                        rotas[k]['sequencia_rota'][0] = origin_wo
                                        rotas[k]['rotas_binaria'][0] = binaria_seq(origin_wo)
                                        rotas[k]['custo'][0] = cost_new_k
                                        rotas[k2]['sequencia_rota'][0] = nova_k2
                                        rotas[k2]['rotas_binaria'][0] = binaria_seq(nova_k2)
                                        rotas[k2]['custo'][0] = cost_new_k2
                                        or_improved = True
                                        found = True
                                        break

        # STEP 4b: Reorder+relocate for any remaining artificial routes
        for k in range(inst.nbv):
            if not rotas[k]['artificial'][0]:
                continue
            seq_k = rotas[k]['sequencia_rota'][0]
            clients_k = [n for n in seq_k if 1 <= n <= nbcd]
            if len(clients_k) > 8 or len(clients_k) < 2:
                continue
            fixed = False
            for drop_idx in range(len(clients_k)):
                if fixed:
                    break
                dropped = clients_k[drop_idx]
                subset = [c for i, c in enumerate(clients_k) if i != drop_idx]
                for perm in _itr.permutations(subset):
                    if fixed:
                        break
                    new_seq_k = [0] + list(perm) + [depf]
                    if not avaliar_seq(k, new_seq_k):
                        continue
                    for k2 in range(inst.nbv):
                        if fixed or k2 == k:
                            continue
                        seq_k2 = rotas[k2]['sequencia_rota'][0]
                        for pos in range(1, len(seq_k2)):
                            nova_k2 = seq_k2[:pos] + [dropped] + seq_k2[pos:]
                            if avaliar_seq(k2, nova_k2):
                                rotas[k]['sequencia_rota'][0] = new_seq_k
                                rotas[k]['rotas_binaria'][0] = binaria_seq(new_seq_k)
                                rotas[k]['custo'][0] = custo_seq(k, new_seq_k)
                                rotas[k]['artificial'][0] = False
                                rotas[k2]['sequencia_rota'][0] = nova_k2
                                rotas[k2]['rotas_binaria'][0] = binaria_seq(nova_k2)
                                rotas[k2]['custo'][0] = custo_seq(k2, nova_k2)
                                fixed = True
                                break
                        if fixed:
                            break

        sol.rotas = rotas
        sol.numero_de_rotas = [1] * inst.nbv

        # STEP 5: Count artificials by flag and print
        n_art = sum(1 for k in range(inst.nbv) if rotas[k]['artificial'][0])
        cost_art = sum(rotas[k]['custo'][0] for k in range(inst.nbv) if rotas[k]['artificial'][0])
        print(f"[INTEIRA] Regret2: {n_art} art, custo_art={cost_art:.2f}")

        return n_art, cost_art

    def gera_rotas_iniciais_clarke_wright(self, inst, sol, custo_artificial=1e6):
        nbcd = inst.nbcd
        depf = inst.nbn - 1

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def demand(i):
            return getattr(inst.noh[i], 'DEMAND', 0.0)

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0

        def dist(i, j):
            return inst.matriz_distancia[i][j]

        def travel(k, i, j):
            return self.avaliador_rota.tempo_viagem(inst, k, i, j)

        def custo_seq(k, seq):
            return self.avaliador_rota.custo_rota(inst, k, seq)

        def avaliar_seq(k, seq):
            return self.avaliador_rota.avaliar_rota(inst, k, seq).viavel

        def binaria_seq(seq):
            binaria = [0] * nbcd
            for no in seq:
                if 1 <= no <= nbcd:
                    binaria[no - 1] = 1
            return binaria

        # -------------------------------------------------------
        # 1. Start: one route per client [0, i, depf]
        # -------------------------------------------------------
        clients = list(range(1, nbcd + 1))

        # route_of[i] = current route list that contains client i
        # Each route is stored as a plain list [0, ..., depf]
        route_of = {}
        routes = []
        for cli in clients:
            r = [0, cli, depf]
            routes.append(r)
            route_of[cli] = r

        # -------------------------------------------------------
        # 2. Compute savings s(i,j) = d(0,i) + d(0,j) - d(i,j)
        #    Use vehicle 0 distances (homogeneous fleet assumed)
        # -------------------------------------------------------
        savings = []
        for i in clients:
            for j in clients:
                if i == j:
                    continue
                s = dist(0, i) + dist(0, j) - dist(i, j)
                savings.append((s, i, j))
        savings.sort(reverse=True)

        # -------------------------------------------------------
        # 3. Greedy merge: merge tail-i route with head-j route
        #    Use vehicle 0 for feasibility (homogeneous fleet)
        # -------------------------------------------------------
        k_check = 0  # representative vehicle for feasibility checks

        for s_val, i, j in savings:
            if s_val <= 0:
                break

            ri = route_of.get(i)
            rj = route_of.get(j)

            if ri is None or rj is None:
                continue
            if ri is rj:
                continue

            # i must be the last client in ri (just before depf)
            interior_ri = [n for n in ri if 1 <= n <= nbcd]
            if not interior_ri or interior_ri[-1] != i:
                continue

            # j must be the first client in rj (just after depot 0)
            interior_rj = [n for n in rj if 1 <= n <= nbcd]
            if not interior_rj or interior_rj[0] != j:
                continue

            merged = [0] + interior_ri + interior_rj + [depf]

            if not avaliar_seq(k_check, merged):
                continue

            # commit merge: update route_of for all clients in rj
            for n in interior_rj:
                route_of[n] = merged
            for n in interior_ri:
                route_of[n] = merged

            routes.remove(ri)
            routes.remove(rj)
            routes.append(merged)

        # -------------------------------------------------------
        # 4. Consolidation: reduce to at most inst.nbv routes
        # -------------------------------------------------------
        print(f"[CW] Após savings: {len(routes)} rotas, {inst.nbv} veículos")

        def tentar_absorver(seq_target, clientes_abs):
            """Try inserting each client in clientes_abs into seq_target at the
            cheapest feasible position.  Returns new sequence or None."""
            seq = list(seq_target)
            for cli in clientes_abs:
                best_pos = None
                best_delta = float("inf")
                for pos in range(1, len(seq)):
                    nova = seq[:pos] + [cli] + seq[pos:]
                    if avaliar_seq(k_check, nova):
                        delta = custo_seq(k_check, nova) - custo_seq(k_check, seq)
                        if delta < best_delta:
                            best_delta = delta
                            best_pos = pos
                if best_pos is None:
                    return None
                seq = seq[:best_pos] + [cli] + seq[best_pos:]
            return seq

        # Phase A: greedy absorption — routes shorter than average absorbed into longer routes
        changed = True
        while len(routes) > inst.nbv and changed:
            changed = False
            avg_len = sum(len(r) for r in routes) / len(routes)
            routes.sort(key=len)
            for short_r in [r for r in routes if len(r) < avg_len]:
                interior_short = [n for n in short_r if 1 <= n <= nbcd]
                for target in sorted([r for r in routes if r is not short_r], key=len, reverse=True):
                    absorbed = tentar_absorver(target, interior_short)
                    if absorbed is not None:
                        for n in [x for x in target if 1 <= x <= nbcd] + interior_short:
                            route_of[n] = absorbed
                        routes.remove(short_r)
                        routes.remove(target)
                        routes.append(absorbed)
                        changed = True
                        break
                if changed:
                    break

        # Phase A.5: try to form a single combined feasible route for all excess clients
        if len(routes) > inst.nbv:
            import itertools as _it
            routes.sort(key=len, reverse=True)
            excess_a5 = routes[inst.nbv:]
            excess_clients_a5 = [n for r_ex in excess_a5 for n in r_ex if 1 <= n <= nbcd]
            if excess_clients_a5:
                combined_route = None
                best_cost_a5 = float("inf")
                if len(excess_clients_a5) <= 7:
                    perm_iter = _it.permutations(excess_clients_a5)
                else:
                    perm_iter = iter([
                        sorted(excess_clients_a5, key=lambda c: due(c)),
                        sorted(excess_clients_a5, key=lambda c: ready(c)),
                        sorted(excess_clients_a5, key=lambda c: (due(c), ready(c))),
                        sorted(excess_clients_a5, key=lambda c: due(c) - ready(c)),
                    ])
                for perm in perm_iter:
                    seq = [0] + list(perm) + [depf]
                    if avaliar_seq(k_check, seq):
                        cost = custo_seq(k_check, seq)
                        if cost < best_cost_a5:
                            best_cost_a5 = cost
                            combined_route = seq
                        if len(excess_clients_a5) > 7:
                            break
                if combined_route is not None:
                    for r_ex in excess_a5:
                        routes.remove(r_ex)
                    routes.append(combined_route)
                    print(f"[CW] Phase A.5: {len(excess_clients_a5)} clientes excedentes → "
                          f"rota combinada viável (custo={best_cost_a5:.2f}), rotas={len(routes)}")
                else:
                    print(f"[CW] Phase A.5: sem rota combinada viável para "
                          f"{len(excess_clients_a5)} clientes excedentes")

        # Phase B: try to insert each excess client into the best compatible keep route;
        #           only truly uninsertable clients go to an artificial route.
        artificial_route_ids = set()
        if len(routes) > inst.nbv:
            routes.sort(key=len, reverse=True)
            keep = routes[:inst.nbv]
            excess = routes[inst.nbv:]
            excess_clients = [n for r_ex in excess for n in r_ex if 1 <= n <= nbcd]

            truly_uninsertable = []
            for cli in excess_clients:
                best = None  # (delta, t_idx, pos)
                for t_idx, target in enumerate(keep):
                    for pos in range(1, len(target)):
                        nova = target[:pos] + [cli] + target[pos:]
                        if avaliar_seq(k_check, nova):
                            delta = custo_seq(k_check, nova) - custo_seq(k_check, target)
                            if best is None or delta < best[0]:
                                best = (delta, t_idx, pos)
                if best is not None:
                    _, t_idx, pos = best
                    keep[t_idx] = keep[t_idx][:pos] + [cli] + keep[t_idx][pos:]
                else:
                    truly_uninsertable.append(cli)

            routes = keep

            if truly_uninsertable:
                # Try to form a single dedicated feasible route for all truly_uninsertable
                import itertools as _it_b
                combined_tu = None
                best_cost_tu = float("inf")
                for perm in _it_b.permutations(truly_uninsertable):
                    seq = [0] + list(perm) + [depf]
                    if avaliar_seq(k_check, seq):
                        cost = custo_seq(k_check, seq)
                        if cost < best_cost_tu:
                            best_cost_tu = cost
                            combined_tu = seq

                if combined_tu is not None:
                    # Free a keep slot by redistributing the shortest keep route's clients
                    target_idx = min(range(len(keep)),
                                     key=lambda i: sum(1 for n in keep[i] if 1 <= n <= nbcd))
                    displaced = [n for n in keep[target_idx] if 1 <= n <= nbcd]
                    tentative_keep = [r for i, r in enumerate(keep) if i != target_idx]
                    slot_freed = True
                    for d_cli in displaced:
                        best_d = None
                        for t_idx2, tgt in enumerate(tentative_keep):
                            for pos in range(1, len(tgt)):
                                nova = tgt[:pos] + [d_cli] + tgt[pos:]
                                if avaliar_seq(k_check, nova):
                                    delta = custo_seq(k_check, nova) - custo_seq(k_check, tgt)
                                    if best_d is None or delta < best_d[0]:
                                        best_d = (delta, t_idx2, pos)
                        if best_d is not None:
                            _, t_idx2, pos = best_d
                            tentative_keep[t_idx2] = (tentative_keep[t_idx2][:pos]
                                                      + [d_cli] + tentative_keep[t_idx2][pos:])
                        else:
                            slot_freed = False
                            break
                    if slot_freed:
                        keep = tentative_keep + [combined_tu]
                        routes = keep
                        truly_uninsertable = []
                        print(f"[CW] Phase B: {len(combined_tu) - 2} clientes não inseríveis → "
                              f"rota combinada viável (custo={best_cost_tu:.2f})")
                    else:
                        print(f"[CW] Phase B: rota combinada viável mas slot indisponível — "
                              f"tentando reinserção individual")

                if truly_uninsertable:
                    print("[CW] Clientes não inseríveis após Phase B — tentando reinserção:")
                    for cli_u in sorted(truly_uninsertable):
                        print(f"  cliente {cli_u}: ready={ready(cli_u)} due={due(cli_u)} "
                              f"demand={demand(cli_u)} service={service(cli_u)}")

                    still_uninsertable = []
                    for cli in truly_uninsertable:
                        best = None  # (score, t_idx, pos)
                        for t_idx, target in enumerate(keep):
                            for pos in range(1, len(target)):
                                nova = target[:pos] + [cli] + target[pos:]
                                if avaliar_seq(k_check, nova):
                                    delta = custo_seq(k_check, nova) - custo_seq(k_check, target)
                                    score = delta + 0.001 * due(cli)
                                    if best is None or score < best[0]:
                                        best = (score, t_idx, pos)
                        if best is not None:
                            _, t_idx, pos = best
                            keep[t_idx] = keep[t_idx][:pos] + [cli] + keep[t_idx][pos:]
                            print(f"  [OK] cliente {cli} inserido na rota do veículo {t_idx} pos {pos}")
                        else:
                            still_uninsertable.append(cli)
                            print(f"  [FAIL] cliente {cli} sem posição viável em nenhuma rota")

                    routes = keep

                    if still_uninsertable:
                        target_idx = min(
                            range(len(keep)),
                            key=lambda idx_k: sum(1 for n in keep[idx_k] if 1 <= n <= nbcd)
                        )
                        base_interior = [n for n in keep[target_idx] if 1 <= n <= nbcd]
                        forced = [0] + base_interior + sorted(still_uninsertable) + [depf]
                        keep[target_idx] = forced
                        routes = keep
                        artificial_route_ids.add(id(forced))
                        print(f"[CW] {len(still_uninsertable)} clientes sem inserção viável → rota artificial")
                    else:
                        print(f"[CW] Todos os clientes reinseridos com sucesso")
                else:
                    print(f"[CW] Todos os clientes não-inseríveis → rota combinada viável")
            else:
                print(f"[CW] Todos os {len(excess_clients)} clientes excedentes absorvidos")

        # -------------------------------------------------------
        # 5. Assign exactly one route per vehicle
        # -------------------------------------------------------
        sol.rotas = {}
        for k in range(inst.nbv):
            sol.rotas[k] = {
                'sequencia_rota': [],
                'rotas_binaria': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': [],
                'artificial': [],
            }

        for k, r in enumerate(sorted(routes, key=len, reverse=True)):
            is_art = id(r) in artificial_route_ids
            c = custo_seq(k, r) + (custo_artificial if is_art else 0.0)
            sol.rotas[k]['sequencia_rota'].append(r)
            sol.rotas[k]['rotas_binaria'].append(binaria_seq(r))
            sol.rotas[k]['custo'].append(c)
            sol.rotas[k]['vezes_usada_geral'].append(0)
            sol.rotas[k]['vezes_usada_otimo'].append(0)
            sol.rotas[k]['lbd_iteracao'].append([])
            sol.rotas[k]['artificial'].append(is_art)

        # Vehicles with no route assigned get an empty [0, depf] route
        for k in range(inst.nbv):
            if not sol.rotas[k]['sequencia_rota']:
                sol.rotas[k]['sequencia_rota'].append([0, depf])
                sol.rotas[k]['rotas_binaria'].append([0] * nbcd)
                sol.rotas[k]['custo'].append(0.0)
                sol.rotas[k]['vezes_usada_geral'].append(0)
                sol.rotas[k]['vezes_usada_otimo'].append(0)
                sol.rotas[k]['lbd_iteracao'].append([])
                sol.rotas[k]['artificial'].append(False)

        # -------------------------------------------------------
        # 6. Fallback artificial for any still-unserved clients
        # -------------------------------------------------------
        served = set()
        for k in range(inst.nbv):
            served.update(n for n in sol.rotas[k]['sequencia_rota'][0] if 1 <= n <= nbcd)

        nao_atendidos = set(range(1, nbcd + 1)) - served

        if nao_atendidos:
            print("ATENÇÃO: clientes não couberam em rotas reais (CW).")
            print("Criando rota artificial para garantir solução inteira inicial.")
            print("Clientes artificiais:", sorted(nao_atendidos))

            kbest = min(
                range(inst.nbv),
                key=lambda kk: len(sol.rotas[kk]['sequencia_rota'][0])
            )

            seq_antiga = sol.rotas[kbest]['sequencia_rota'][0]
            clientes_antigos = [n for n in seq_antiga if 1 <= n <= nbcd]

            seq_art = [0] + clientes_antigos + sorted(nao_atendidos) + [depf]

            sol.rotas[kbest]['sequencia_rota'][0] = seq_art
            sol.rotas[kbest]['rotas_binaria'][0] = binaria_seq(seq_art)
            sol.rotas[kbest]['custo'][0] = custo_seq(kbest, seq_art) + custo_artificial
            sol.rotas[kbest]['artificial'][0] = True

        # Reorder+relocate: for each artificial route, drop one client at a time,
        #   find valid permutation of remaining (n-1) clients, insert dropped into another route
        import itertools as _it_rr
        for k in range(inst.nbv):
            if not sol.rotas[k]['artificial'][0]:
                continue
            seq_k = sol.rotas[k]['sequencia_rota'][0]
            clients_k = [n for n in seq_k if 1 <= n <= nbcd]
            if len(clients_k) > 8 or len(clients_k) < 2:
                continue
            fixed = False
            for drop_idx in range(len(clients_k)):
                if fixed:
                    break
                dropped = clients_k[drop_idx]
                subset = [c for i, c in enumerate(clients_k) if i != drop_idx]
                for perm in _it_rr.permutations(subset):
                    if fixed:
                        break
                    new_seq_k = [0] + list(perm) + [depf]
                    if not avaliar_seq(k, new_seq_k):
                        continue
                    for k2 in range(inst.nbv):
                        if fixed or k2 == k:
                            continue
                        seq_k2 = sol.rotas[k2]['sequencia_rota'][0]
                        for pos in range(1, len(seq_k2)):
                            nova_k2 = seq_k2[:pos] + [dropped] + seq_k2[pos:]
                            if avaliar_seq(k2, nova_k2):
                                sol.rotas[k]['sequencia_rota'][0] = new_seq_k
                                sol.rotas[k]['rotas_binaria'][0] = binaria_seq(new_seq_k)
                                sol.rotas[k]['custo'][0] = custo_seq(k, new_seq_k)
                                sol.rotas[k]['artificial'][0] = False
                                sol.rotas[k2]['sequencia_rota'][0] = nova_k2
                                sol.rotas[k2]['rotas_binaria'][0] = binaria_seq(nova_k2)
                                sol.rotas[k2]['custo'][0] = custo_seq(k2, nova_k2)
                                fixed = True
                                break
                        if fixed:
                            break

        sol.numero_de_rotas = [1] * inst.nbv

        print("\n=== ROTAS INICIAIS CW ===")
        custo_total = 0.0
        for k in range(inst.nbv):
            r = sol.rotas[k]['sequencia_rota'][0]
            custo = sol.rotas[k]['custo'][0]
            art = sol.rotas[k]['artificial'][0]
            custo_total += custo
            print(f"Veículo {k}: {r}")
            print(f"  custo = {custo:.4f} | artificial = {art}")
        print(f"Custo inicial CW = {custo_total:.4f}")

        return sol.rotas

    def _contar_artificiais(self, sol):
        count = 0
        for k in sol.rotas:
            for custo in sol.rotas[k]['custo']:
                if custo > 500000:
                    count += 1
        return count

    def _custo_artificiais(self, sol):
        total = 0.0
        for k in sol.rotas:
            for custo in sol.rotas[k]['custo']:
                if custo > 500000:
                    total += custo
        return total

    def gera_solucao_inicial(self, inst, sol_pool):
        sol_int = Solucao(inst.nbv, inst.nbcd)
        self.init_pool_vazio(inst, sol_int)
        self.gera_rotas_iniciais_inteligente_inteira(inst, sol_int)

        n_art_int = self._contar_artificiais(sol_int)

        if n_art_int == 0:
            sol_pool.rotas = sol_int.rotas
            print("[CONSTRUTIVA] VENCEDOR: Inteligente — nenhuma rota artificial")
            self._garantir_cobertura_total(inst, sol_pool.rotas)
            return

        cost_art_int = self._custo_artificiais(sol_int)

        sol_cw = Solucao(inst.nbv, inst.nbcd)
        self.init_pool_vazio(inst, sol_cw)
        self.gera_rotas_iniciais_clarke_wright(inst, sol_cw)

        n_art_cw = self._contar_artificiais(sol_cw)
        cost_art_cw = self._custo_artificiais(sol_cw)

        if (n_art_cw < n_art_int) or (n_art_cw == n_art_int and cost_art_cw < cost_art_int):
            sol_pool.rotas = sol_cw.rotas
            print(f"[CONSTRUTIVA] VENCEDOR: Clarke-Wright ({n_art_cw} art, custo_art={cost_art_cw:.2f}) "
                  f"vs Inteligente ({n_art_int} art, custo_art={cost_art_int:.2f})")
            self._garantir_cobertura_total(inst, sol_pool.rotas)
        else:
            sol_pool.rotas = sol_int.rotas
            print(f"[CONSTRUTIVA] VENCEDOR: Inteligente ({n_art_int} art, custo_art={cost_art_int:.2f}) "
                  f"vs Clarke-Wright ({n_art_cw} art, custo_art={cost_art_cw:.2f})")
            self._garantir_cobertura_total(inst, sol_pool.rotas)

    def _garantir_cobertura_total(self, inst, rotas, custo_artificial=1e6):
        """Rede de seguranca: todo pedido 1..nbcd DEVE aparecer em alguma rota.
        Qualquer pedido ausente e' anexado a uma rota artificial e contado como tal.
        Nunca deixa um pedido sumir silenciosamente."""
        nbcd = inst.nbcd
        depf = inst.nbn - 1

        def _bin(seq):
            b = [0] * nbcd
            for n in seq:
                if 1 <= n <= nbcd:
                    b[n - 1] = 1
            return b

        def _custo(k, seq):
            v = inst.veiculos[k].velocidade
            return sum(inst.matriz_distancia[seq[t]][seq[t + 1]] / v for t in range(len(seq) - 1))

        servidos = set()
        for k in rotas:
            for seq in rotas[k]['sequencia_rota']:
                servidos.update(n for n in seq if 1 <= n <= nbcd)

        faltando = sorted(set(range(1, nbcd + 1)) - servidos)
        if not faltando:
            return 0

        print(f"[COBERTURA] ALERTA: {len(faltando)} pedido(s) ausente(s) da construtiva: {faltando}")
        print("[COBERTURA] Anexando a rota artificial para preservar viabilidade inteira.")

        kb = min(rotas.keys(), key=lambda kk: len([n for n in rotas[kk]['sequencia_rota'][0] if 1 <= n <= nbcd]))
        clientes_antigos = [n for n in rotas[kb]['sequencia_rota'][0] if 1 <= n <= nbcd]
        seq_art = [0] + clientes_antigos + faltando + [depf]
        rotas[kb]['sequencia_rota'][0] = seq_art
        rotas[kb]['rotas_binaria'][0] = _bin(seq_art)
        rotas[kb]['custo'][0] = _custo(kb, seq_art) + custo_artificial
        rotas[kb]['artificial'][0] = True

        servidos2 = set()
        for k in rotas:
            for seq in rotas[k]['sequencia_rota']:
                servidos2.update(n for n in seq if 1 <= n <= nbcd)
        faltando2 = set(range(1, nbcd + 1)) - servidos2
        assert not faltando2, f"[COBERTURA] FALHA CRITICA: pedidos ainda ausentes: {sorted(faltando2)}"
        return len(faltando)

    def adiciona_colunas_ociosas(self, inst, sol_pool):

        depf = inst.nbn - 1
        nbcd = inst.nbcd
        n_adicionadas = 0

        for k in sol_pool.rotas.keys():
            ja_existe = any(
                seq == [0, depf]
                for seq in sol_pool.rotas[k]['sequencia_rota']
            )
            if ja_existe:
                continue

            sol_pool.rotas[k]['sequencia_rota'].append([0, depf])
            sol_pool.rotas[k]['rotas_binaria'].append([0] * nbcd)
            sol_pool.rotas[k]['custo'].append(0.0)
            sol_pool.rotas[k]['vezes_usada_geral'].append(0)
            sol_pool.rotas[k]['vezes_usada_otimo'].append(0)
            sol_pool.rotas[k]['lbd_iteracao'].append([])
            sol_pool.rotas[k]['artificial'].append(False)
            n_adicionadas += 1

        print(f"[POOL] Coluna ociosa adicionada para {n_adicionadas} navios (navio pode ficar na base)")
        return n_adicionadas

    def gera_rotas_iniciais_boas(self, inst, sol, max_rotas_por_criterio=3):
        nbcd = inst.nbcd
        depf = inst.nbn - 1

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def demand(i):
            return getattr(inst.noh[i], 'DEMAND', 0.0)

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0

        def travel(k, i, j):
            return self.avaliador_rota.tempo_viagem(inst, k, i, j)

        def custo_seq(k, seq):
            return self.avaliador_rota.custo_rota(inst, k, seq)

        def avaliar_seq(k, seq):
            resultado = self.avaliador_rota.avaliar_rota(inst, k, seq)
            if not resultado.viavel:
                return False, None, None
            return True, resultado.tempo_final, resultado.carga_deck_maxima

        def melhor_insercao(k, seq, cliente):
            melhor = None

            for pos in range(1, len(seq)):
                nova = seq[:pos] + [cliente] + seq[pos:]
                fact, tempo_final, carga_final = avaliar_seq(k, nova)
                if not fact:
                    continue

                delta = custo_seq(k, nova) - custo_seq(k, seq)

                # penaliza terminar muito perto da janela
                folga_final = due(cliente) - max(ready(cliente), 0)
                score = delta + 0.001 * tempo_final - 0.0001 * folga_final

                if (melhor is None) or (score < melhor[0]):
                    melhor = (score, nova)

            return melhor

        def add_rota(sol, k, seq):
            binaria = [0] * nbcd
            for no in seq:
                if 1 <= no <= nbcd:
                    binaria[no - 1] = 1

            if k not in sol.rotas:
                sol.rotas[k] = {
                    'sequencia_rota': [],
                    'rotas_binaria': [],
                    'custo': [],
                    'vezes_usada_geral': [],
                    'vezes_usada_otimo': [],
                    'lbd_iteracao': [],
                    'artificial': [],
                }

            # evita duplicata
            for s in sol.rotas[k]['sequencia_rota']:
                if s == seq:
                    return

            sol.rotas[k]['sequencia_rota'].append(seq[:])
            sol.rotas[k]['rotas_binaria'].append(binaria)
            sol.rotas[k]['custo'].append(custo_seq(k, seq))
            sol.rotas[k]['vezes_usada_geral'].append(0)
            sol.rotas[k]['vezes_usada_otimo'].append(0)
            sol.rotas[k]['lbd_iteracao'].append([])
            sol.rotas[k]['artificial'].append(False)

        clientes = list(range(1, nbcd + 1))

        criterios = [
            ("due", lambda i: due(i)),
            ("dist", lambda i: -inst.matriz_distancia[0][i]),
            ("demanda", lambda i: -demand(i)),
            ("folga", lambda i: (due(i) - ready(i))),
        ]

        sol.rotas = {k: {
            'sequencia_rota': [],
            'rotas_binaria': [],
            'custo': [],
            'vezes_usada_geral': [],
            'vezes_usada_otimo': [],
            'lbd_iteracao': [],
            'artificial': [],
        } for k in range(inst.nbv)}

        for nome_criterio, chave in criterios:
            ordenados = sorted(clientes, key=chave)

            usados_global = set()
            rotas_criadas = 0

            for seed in ordenados:
                if seed in usados_global:
                    continue
                if rotas_criadas >= max_rotas_por_criterio:
                    break

                melhor_seed = None

                for k in range(inst.nbv):
                    seq0 = [0, seed, depf]
                    fact, _, _ = avaliar_seq(k, seq0)
                    if fact:
                        c = custo_seq(k, seq0)
                        if (melhor_seed is None) or (c < melhor_seed[0]):
                            melhor_seed = (c, k, seq0)

                if melhor_seed is None:
                    continue

                _, kbest, seq = melhor_seed
                usados_rota = {seed}
                melhorou = True

                while melhorou:
                    melhorou = False
                    melhor_cand = None

                    for cli in ordenados:
                        if cli in usados_rota or cli in usados_global:
                            continue

                        ins = melhor_insercao(kbest, seq, cli)
                        if ins is None:
                            continue

                        score, nova_seq = ins
                        if (melhor_cand is None) or (score < melhor_cand[0]):
                            melhor_cand = (score, cli, nova_seq)

                    if melhor_cand is not None:
                        _, cli_add, seq = melhor_cand
                        usados_rota.add(cli_add)
                        melhorou = True

                add_rota(sol, kbest, seq)
                usados_global.update(usados_rota)
                rotas_criadas += 1

        # fallback: se algum veículo ficou sem coluna, adiciona rota nula
        for k in range(inst.nbv):
            if len(sol.rotas[k]['sequencia_rota']) == 0:
                seq = [0, depf]
                add_rota(sol, k, seq)

        sol.numero_de_rotas = [len(sol.rotas[k]['sequencia_rota']) for k in range(inst.nbv)]
        return sol.rotas

    def gera_rotas_iniciais_geometricas(self, inst, sol, n_starts=8, max_rotas_por_k=30):
        import math
        import random

        nbcd = inst.nbcd
        depf = inst.nbn - 1
        depot = 0

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0.0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0.0

        def demand(i):
            return getattr(inst.noh[i], "DEMAND", 0.0)

        def travel(k, i, j):
            return self.avaliador_rota.tempo_viagem(inst, k, i, j)

        def custo_seq(k, seq):
            return self.avaliador_rota.custo_rota(inst, k, seq)

        def angle_from_depot(i):
            dx = inst.noh[i].XCOORD - inst.noh[depot].XCOORD
            dy = inst.noh[i].YCOORD - inst.noh[depot].YCOORD
            ang = math.atan2(dy, dx)
            if ang < 0:
                ang += 2 * math.pi
            return ang

        def dist_from_depot(i):
            return inst.matriz_distancia[depot][i]

        def avalia_seq(k, seq):
            resultado = self.avaliador_rota.avaliar_rota(inst, k, seq)
            if not resultado.viavel:
                return False, None, None
            return True, resultado.tempo_final, resultado.carga_deck_maxima

        def melhor_insercao_cliente(k, seq, cliente, peso_tempo=0.001, peso_folga=0.0001):
            custo_base = custo_seq(k, seq)
            melhores = []

            for pos in range(1, len(seq)):
                nova = seq[:pos] + [cliente] + seq[pos:]
                fact, tempo_final, _ = avalia_seq(k, nova)
                if not fact:
                    continue

                delta = custo_seq(k, nova) - custo_base
                folga = max(1.0, due(cliente) - ready(cliente))
                score = delta + peso_tempo * tempo_final + peso_folga * (1.0 / folga)
                melhores.append((score, pos, nova))

            melhores.sort(key=lambda x: x[0])
            return melhores

        def add_rota(k, seq):
            binaria = [0] * nbcd
            for no in seq:
                if 1 <= no <= nbcd:
                    binaria[no - 1] = 1

            for antiga in sol.rotas[k]['sequencia_rota']:
                if antiga == seq:
                    return

            sol.rotas[k]['sequencia_rota'].append(seq[:])
            sol.rotas[k]['rotas_binaria'].append(binaria)
            sol.rotas[k]['custo'].append(custo_seq(k, seq))
            sol.rotas[k]['vezes_usada_geral'].append(0)
            sol.rotas[k]['vezes_usada_otimo'].append(0)
            sol.rotas[k]['lbd_iteracao'].append([])
            sol.rotas[k]['artificial'].append(False)

        def two_opt(k, seq):
            melhor = seq[:]
            melhor_custo = custo_seq(k, melhor)
            mudou = True

            while mudou:
                mudou = False
                for i in range(1, len(melhor) - 3):
                    for j in range(i + 1, len(melhor) - 1):
                        cand = melhor[:i] + melhor[i:j + 1][::-1] + melhor[j + 1:]
                        fact, _, _ = avalia_seq(k, cand)
                        if not fact:
                            continue
                        c = custo_seq(k, cand)
                        if c + 1e-9 < melhor_custo:
                            melhor = cand
                            melhor_custo = c
                            mudou = True
                            break
                    if mudou:
                        break

            return melhor

        # inicializa estrutura
        sol.rotas = {}
        for k in range(inst.nbv):
            sol.rotas[k] = {
                'sequencia_rota': [],
                'rotas_binaria': [],
                'custo': [],
                'vezes_usada_geral': [],
                'vezes_usada_otimo': [],
                'lbd_iteracao': [],
                'artificial': []
            }

        clientes = list(range(1, nbcd + 1))

        base_ordenada = sorted(
            clientes,
            key=lambda i: (angle_from_depot(i), dist_from_depot(i))
        )

        for st in range(n_starts):
            ordem = base_ordenada[:]

            # diversificação geométrica
            shift = 0 if len(ordem) == 0 else (st * max(1, len(ordem) // max(1, n_starts))) % len(ordem)
            ordem = ordem[shift:] + ordem[:shift]

            # alterna sentido
            if st % 2 == 1:
                ordem = list(reversed(ordem))

            nao_atendidos = set(ordem)

            while nao_atendidos:
                seed = None
                for c in ordem:
                    if c in nao_atendidos:
                        seed = c
                        break

                if seed is None:
                    break

                melhor_seed = None
                for k in range(inst.nbv):
                    seq0 = [0, seed, depf]
                    fact, tempo_final, _ = avalia_seq(k, seq0)
                    if not fact:
                        continue

                    # favorece cliente longe e urgente na semente
                    folga = max(1.0, due(seed) - ready(seed))
                    prioridade = custo_seq(k, seq0) - 0.01 * dist_from_depot(seed) + 1.0 / folga

                    if (melhor_seed is None) or (prioridade < melhor_seed[0]):
                        melhor_seed = (prioridade, k, seq0)

                if melhor_seed is None:
                    nao_atendidos.remove(seed)
                    continue

                _, kbest, seq = melhor_seed
                usados = {seed}

                melhorou = True
                while melhorou:
                    melhorou = False
                    melhor_cliente = None

                    for cli in ordem:
                        if cli not in nao_atendidos or cli in usados:
                            continue

                        insercoes = melhor_insercao_cliente(kbest, seq, cli)
                        if not insercoes:
                            continue

                        melhor1 = insercoes[0][0]
                        melhor2 = insercoes[1][0] if len(insercoes) > 1 else melhor1 + 1e6
                        regret = melhor2 - melhor1

                        # score final: maior regret, com leve viés para longe/urgente
                        folga = max(1.0, due(cli) - ready(cli))
                        prioridade = regret + 0.01 * dist_from_depot(cli) + 1.0 / folga

                        if (melhor_cliente is None) or (prioridade > melhor_cliente[0]):
                            melhor_cliente = (prioridade, cli, insercoes[0][2])

                    if melhor_cliente is not None:
                        _, cli_add, nova_seq = melhor_cliente
                        seq = nova_seq
                        usados.add(cli_add)
                        melhorou = True

                seq = two_opt(kbest, seq)
                add_rota(kbest, seq)

                for u in usados:
                    nao_atendidos.discard(u)

        # sobe também unitárias viáveis
        for i in clientes:
            for k in range(inst.nbv):
                seq = [0, i, depf]
                fact, _, _ = avalia_seq(k, seq)
                if fact:
                    add_rota(k, seq)

        # garante pelo menos uma rota por veículo
        for k in range(inst.nbv):
            if len(sol.rotas[k]['sequencia_rota']) == 0:
                seq = [0, depf]
                sol.rotas[k]['sequencia_rota'].append(seq)
                sol.rotas[k]['rotas_binaria'].append([0] * nbcd)
                sol.rotas[k]['custo'].append(custo_seq(k, seq))
                sol.rotas[k]['vezes_usada_geral'].append(0)
                sol.rotas[k]['vezes_usada_otimo'].append(0)
                sol.rotas[k]['lbd_iteracao'].append([])
                sol.rotas[k]['artificial'].append(False)

        # limita número de rotas por veículo
        for k in range(inst.nbv):
            idxs = list(range(len(sol.rotas[k]['sequencia_rota'])))
            idxs.sort(key=lambda p: sol.rotas[k]['custo'][p])
            idxs = idxs[:max_rotas_por_k]

            for chave in ['sequencia_rota', 'rotas_binaria', 'custo',
                          'vezes_usada_geral', 'vezes_usada_otimo',
                          'lbd_iteracao', 'artificial']:
                sol.rotas[k][chave] = [sol.rotas[k][chave][p] for p in idxs]

        sol.numero_de_rotas = [len(sol.rotas[k]['sequencia_rota']) for k in range(inst.nbv)]
        return sol.rotas

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
        filho_esq.lb_confiavel_HERDADO = bool(getattr(no_pai, "lb_confiavel", False))

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
        filho_dir.lb_confiavel_HERDADO = bool(getattr(no_pai, "lb_confiavel", False))

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
        # print(
        #    f" Branching no arco ({i_sel},{j_sel},{k_sel}) no nó {no_pai.id_no} (soma_lambda≈{soma_arco[melhor_arco]:.4f})")

        pai_fix = set(no_pai.arcos_fixados_em_1)
        pai_proib = set(no_pai.arcos_proibidos)

        # filho esquerdo: proíbe arco
        filho_esq = NoBP(
            id_no=proximo_id,
            arcos_fixados_em_1=pai_fix,
            arcos_proibidos=pai_proib.union({melhor_arco})
        )
        filho_esq.branching_from = {"pai": no_pai.id_no, "arco": [i_sel, j_sel, k_sel], "tipo": "proibido"}
        filho_esq.custo_lp_HERDADO = no_pai.custo_lp
        filho_esq.custo_mip_HERDADO = no_pai.custo_mip
        filho_esq.lb_confiavel_HERDADO = bool(getattr(no_pai, "lb_confiavel", False))
        # TAREFA 2: copia independente do centro da caixa -- alterar o centro
        # de um filho nao pode afetar o pai nem o outro filho
        filho_esq.pi_bar = copy.deepcopy(no_pai.pi_bar) if no_pai.pi_bar is not None else None

        # filho direito: obriga arco
        filho_dir = NoBP(
            id_no=proximo_id + 1,
            arcos_fixados_em_1=pai_fix.union({melhor_arco}),
            arcos_proibidos=pai_proib
        )
        filho_dir.branching_from = {"pai": no_pai.id_no, "arco": [i_sel, j_sel, k_sel], "tipo": "obrigatorio"}
        filho_dir.custo_lp_HERDADO = no_pai.custo_lp
        filho_dir.custo_mip_HERDADO = no_pai.custo_mip
        filho_dir.lb_confiavel_HERDADO = bool(getattr(no_pai, "lb_confiavel", False))
        filho_dir.pi_bar = copy.deepcopy(no_pai.pi_bar) if no_pai.pi_bar is not None else None

        # self._append_hist_bp(
        #    f"Do nó {no_pai.id_no} gerados filhos {filho_esq.id_no} (proíbe arco {i_sel}->{j_sel}, k={k_sel}) "
        ##    f"e {filho_dir.id_no} (obriga arco {i_sel}->{j_sel}, k={k_sel})."
        # )

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

    # exporta_visualizacao_petro foi movido para Solucao.exportar_visualizacao (solucao.py).
    # Use: sol.registrar_solucao(nome, rotas); sol.exportar_visualizacao(inst, nome, caminho_js)

    def relatorio_cronograma_petro(self, inst, rotas_escolhidas):
        """
        Imprime o cronograma detalhado da solucao final (instancias Petro).
        rotas_escolhidas: {k: sequencia} ou {k: {"sequencias": [seq, ...], ...}}
        Mostra por visita: chegada, janela usada, inicio/fim de servico;
        e por navio: navegacao (=FO), servico, espera, retorno.
        """
        if not hasattr(inst, "dados_petro"):
            return
        H = 3600.0
        nomes = inst.dados_petro["nomes"]
        depf = inst.nbn - 1
        fo_total = 0.0
        print("=" * 78)
        print("CRONOGRAMA DA SOLUCAO (tempos em horas)")
        for k in sorted(rotas_escolhidas.keys()):
            ent = rotas_escolhidas[k]
            if isinstance(ent, dict):
                seqs = list(ent.get("sequencias", []))
            elif ent and isinstance(ent[0], (list, tuple)):
                seqs = list(ent)
            else:
                seqs = [ent]
            veic = inst.veiculos[k]

            if not seqs:
                print("-" * 78)
                print("Navio %d (%s): sem rota escolhida" % (k, getattr(veic, "nome", "")))
                continue

            for seq in seqs:
                seq = list(seq)
                if len(seq) <= 2:  # [0, depf] = ocioso
                    print("-" * 78)
                    print("Navio %d (%s): OCIOSO (fica na base)" % (k, getattr(veic, "nome", "")))
                    continue
                print("-" * 78)
                print("Navio %d (%s) | rota: %s" % (k, getattr(veic, "nome", ""), seq))
                print("%-16s %9s %9s %9s %9s  %s" %
                      ("no", "chegada", "ini_serv", "fim_serv", "espera", "janela usada"))
                tempo = float(inst.noh[0].READY_TIME[0])
                navegacao = 0.0
                servico_tot = 0.0
                espera_tot = 0.0
                for a in range(len(seq) - 1):
                    i, j = seq[a], seq[a + 1]
                    arco = inst.matriz_distancia[i][j] / veic.velocidade
                    navegacao += arco
                    chegada = tempo + (inst.noh[i].SERVICE_TIME[0] if a > 0 else 0.0) + arco
                    if a > 0:
                        servico_tot += inst.noh[i].SERVICE_TIME[0]
                    if j == depf:
                        print("%-16s %9.2f %9s %9s %9s  retorno a base" %
                              ("BASE(retorno)", chegada / H, "-", "-", "-"))
                        tempo = chegada
                        continue
                    no_j = inst.noh[j]
                    ini = None
                    jan_txt = "SEM JANELA VIAVEL!"
                    for r in range(len(no_j.DUE_DATE)):
                        ini_cand = max(chegada, float(no_j.READY_TIME[r]))
                        if ini_cand + no_j.SERVICE_TIME[0] <= no_j.DUE_DATE[r] + 1e-6:
                            ini = ini_cand
                            jan_txt = "[%.1f, %.1f] (janela %d)" % (
                                no_j.READY_TIME[r] / H, no_j.DUE_DATE[r] / H, r + 1)
                            break
                    if ini is None:
                        print("%-16s %9.2f  *** VIOLACAO DE JANELA ***" % (nomes[j], chegada / H))
                        ini = chegada
                    fim = ini + no_j.SERVICE_TIME[0]
                    espera = ini - chegada
                    espera_tot += espera
                    print("%-16s %9.2f %9.2f %9.2f %9.2f  %s" %
                          (nomes[j], chegada / H, ini / H, fim / H, espera / H, jan_txt))
                    tempo = ini
                fo_navio = navegacao
                fo_total += fo_navio
                print("Navio %d: navegacao+manobras=%.2f h (FO) | servico=%.2f h | "
                      "espera=%.2f h | retorno em t=%.2f h (limite %.1f h)" %
                      (k, navegacao / H, servico_tot / H, espera_tot / H,
                       tempo / H, veic.trip_duration_limit / H))
        print("-" * 78)
        print("FO TOTAL (soma da navegacao+manobras) = %.0f s = %.2f h" % (fo_total, fo_total / H))
        print("=" * 78)

    def branch_and_price_global(self, inst, sol_pool, tipo_geracao="PD"):

        # limpeza arquivo principal dos logs meus
        # nome_arquivo_log = f"log_bounds_{inst.nbcd}_{inst.ninst}.csv"

        # with open(nome_arquivo_log, "w", encoding="utf-8") as f:
        #    f.write("no_id;z_inc;z_lp;z_li;total_colunas\n")

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
        sol_pool.lb_global_confiavel = None  # so certificado no fim, se todos os nos necessarios tiverem LB confiavel
        sol_pool.lb_raiz_confiavel = None  # LB valido (nao necessariamente otimo) assim que a raiz certificar

        # PARTE 2 (calibracao gamma): instrumentacao, so diagnostico -- nao influencia decisao
        sol_pool.terminou_por_tempo = False
        sol_pool.houve_no_interrompido = False
        sol_pool.pricing_timeout_algum_no = False
        sol_pool.parou_por_max_iter_algum_no = False

        t0 = time.time()

        melhor_no = None
        melhor_no_frac = None
        z_frac = float("inf")

        # === raiz ===
        id_no = 0
        raiz = NoBP(id_no=id_no)
        id_no += 1

        ativos = [(raiz, 0, None)]  # (no, profundidade, pai)
        diag_list = []

        todos_nos_confiaveis = True  # AND do lb_confiavel de todos os nos processados
        while ativos:
            if (time.time() - sol_pool.time_initial > sol_pool.TIME_MAX):
                sol_pool.terminou_por_tempo = True  # PARTE 2: instrumentacao
                break
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
            # teste poda do no ja com o herdado (só com bound herdado CONFIÁVEL; ver secao 2)
            if (
                no_atual.custo_lp_HERDADO is not None
                and getattr(no_atual, "lb_confiavel_HERDADO", False)
                and not math.isinf(z_inc)
                and no_atual.custo_lp_HERDADO >= z_inc - 1e-6
            ):
                print(
                    f"Poda nó {no_atual.id_no} por bound herdado: {no_atual.custo_lp_HERDADO:.4f} >= incumbente {z_inc:.4f}")
                no_atual.status = "podado"
                no_atual.motivo_poda = "bound_herdado"
                diag_list.append({
                    "no_id": no_atual.id_no, "profundidade": prof,
                    "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                    "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                    "motivo_conv": getattr(sol_pool, "motivoConv", None),
                    "custo_lp": getattr(no_atual, "custo_lp", None),
                    "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                    "custo_mip": getattr(no_atual, "custo_mip", None),
                    "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                    "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                    "abriu_filhos": False,
                    "z_inc": None if math.isinf(z_inc) else z_inc,
                    "z_li": None if math.isinf(z_li) else z_li,
                    "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
                })
                continue

            self.resolver_no_com_pool(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)
            # self.resolver_no_com_pool_semSlack(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)

            lb_no_confiavel = bool(getattr(no_atual, "lb_confiavel", False))
            todos_nos_confiaveis = todos_nos_confiaveis and lb_no_confiavel
            # PARTE 2 (calibracao gamma): instrumentacao agregada -- OR sobre todo no processado
            sol_pool.pricing_timeout_algum_no = sol_pool.pricing_timeout_algum_no or bool(getattr(no_atual, "pricing_timeout", False))
            sol_pool.parou_por_max_iter_algum_no = sol_pool.parou_por_max_iter_algum_no or bool(getattr(no_atual, "parou_por_max_iter", False))
            print(
                f"[CONFIABILIDADE] no={no_atual.id_no} | "
                f"lb_confiavel={lb_no_confiavel} | "
                f"cg_convergiu={getattr(no_atual, 'cg_convergiu', False)} | "
                f"motivo={getattr(no_atual, 'motivo_conv', getattr(sol_pool, 'motivoConv', ''))}"
            )

            #####################
            if no_atual.melhor_lp_com_slack < getattr(sol_pool, "melhor_lp_com_slack", float("inf")):
                sol_pool.melhor_lp_com_slack = no_atual.melhor_lp_com_slack
                sol_pool.iter_melhor_lp_com_slack = no_atual.melhor_lp_com_slack_iter
                sol_pool.no_melhor_lp_com_slack = no_atual.id_no

            if no_atual.melhor_lp_valido < getattr(sol_pool, "melhor_lp_valido", float("inf")):
                sol_pool.melhor_lp_valido = no_atual.melhor_lp_valido
                sol_pool.iter_melhor_lp_valido = no_atual.melhor_lp_valido_iter
                sol_pool.no_melhor_lp_valido = no_atual.id_no

            if no_atual.melhor_int < getattr(sol_pool, "melhor_inteiro", float("inf")):
                sol_pool.melhor_inteiro = no_atual.melhor_int
                sol_pool.iter_melhor_inteiro = no_atual.melhor_int_iter
                sol_pool.no_melhor_inteiro = no_atual.id_no

            if no_atual.achou_lp_target and not getattr(sol_pool, "achou_lp_target", False):
                sol_pool.achou_lp_target = True
                sol_pool.iter_lp_target = no_atual.iter_lp_target
                sol_pool.tempo_lp_target = no_atual.tempo_lp_target
                sol_pool.no_lp_target = no_atual.id_no

            if no_atual.achou_int_target and not getattr(sol_pool, "achou_int_target", False):
                sol_pool.achou_int_target = True
                sol_pool.iter_int_target = no_atual.iter_int_target
                sol_pool.tempo_int_target = no_atual.tempo_int_target
                sol_pool.no_int_target = no_atual.id_no
            #####################

            print(f'Tempo total: {time.time() - t00:.1f}s')
            if no_atual.custo_lp is None:
                print("Nó inviável ou sem solução LP, podado.")
                no_atual.status = "podado"
                no_atual.motivo_poda = "LP_inviavel"
                diag_list.append({
                    "no_id": no_atual.id_no, "profundidade": prof,
                    "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                    "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                    "motivo_conv": getattr(sol_pool, "motivoConv", None),
                    "custo_lp": None,
                    "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                    "custo_mip": getattr(no_atual, "custo_mip", None),
                    "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                    "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                    "abriu_filhos": False,
                    "z_inc": None if math.isinf(z_inc) else z_inc,
                    "z_li": None if math.isinf(z_li) else z_li,
                    "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
                })
                continue

            z_lp = float(no_atual.custo_lp)
            z_mip = float(no_atual.custo_mip) if no_atual.custo_mip is not None else float("inf")

            # Saída antecipada (lp_inteiro_target / fo_target_int_atingido): melhor_int pode
            # ser melhor que custo_mip se o post-loop LP distorceu o resultado.
            melhor_int_direto = getattr(no_atual, "melhor_int", float("inf"))
            if melhor_int_direto < z_mip - 1e-6:
                z_mip = melhor_int_direto
                no_atual.custo_mip = z_mip
                no_atual.solucao_inteira = True

            no_atual.status = "resolvido"

            lb_ok = bool(getattr(no_atual, "lb_confiavel", False))

            # TAREFA 4: LB da raiz certificado -- valido para o problema original
            # mesmo que a arvore nao termine (fallback de bound quando nao ha
            # lb_global_confiavel ainda).
            if (
                prof == 0
                and lb_ok
                and bool(getattr(no_atual, "cg_convergiu", False))
                and sol_pool.lb_raiz_confiavel is None
            ):
                sol_pool.lb_raiz_confiavel = float(z_lp)
                print(f"[LB RAIZ] lb_raiz_confiavel = {sol_pool.lb_raiz_confiavel:.4f}")

            # secao 15 (silva2024): a raiz integrada tem que reproduzir o LB
            # ja validado isoladamente (CG manual em _teste_etapa15_raiz_silva.py)
            # antes de abrir qualquer filho. O valor esperado e opcional
            # (sol_pool.SILVA_LB_RAIZ_ESPERADO), setado pelo script de teste.
            if (
                prof == 0
                and getattr(inst, "objective_mode", "petrobras") == "silva2024"
                and sol_pool.lb_raiz_confiavel is not None
                and getattr(sol_pool, "SILVA_LB_RAIZ_ESPERADO", None) is not None
            ):
                lb_esperado = float(sol_pool.SILVA_LB_RAIZ_ESPERADO)
                dif_raiz = sol_pool.lb_raiz_confiavel - lb_esperado
                if abs(dif_raiz) > 1e-4:
                    print(
                        f"[SILVA RAIZ] PARADA: LB da raiz integrada ({sol_pool.lb_raiz_confiavel:.6f}) "
                        f"nao reproduz o teste isolado ({lb_esperado:.6f}); dif={dif_raiz:.6f}. "
                        f"Nao abrindo filhos."
                    )
                    sol_pool.motivoConv = "silva_raiz_divergente"
                    break
                print(
                    f"[SILVA RAIZ] OK: LB da raiz reproduzida "
                    f"({sol_pool.lb_raiz_confiavel:.6f} vs esperado {lb_esperado:.6f})."
                )

            # teste integralidade-podar os filhos
            tol = 1e-6
            if abs(z_lp - z_mip) <= tol:
                no_atual.solucao_inteira = True
                print("SOL INTEIRA")
                no_atual.podar = True
            print(
                f"[Nó {no_atual.id_no}] LP={z_lp:.4f} inteira={no_atual.solucao_inteira} "
                f"lb_confiavel={lb_ok} slack_final={getattr(no_atual, 'slack_sum_final', 0.0):.6f} "
                f"cg_convergiu={getattr(no_atual, 'cg_convergiu', False)} max_iter={getattr(no_atual, 'parou_por_max_iter', False)}"
            )

            if getattr(inst, "objective_mode", "petrobras") == "silva2024":
                ncol_atual = sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values())
                print(
                    f"[SILVA BP] no={no_atual.id_no} prof={prof} RMP={z_lp:.6f} "
                    f"MIP_RMP={(z_mip if not math.isinf(z_mip) else None)} lb_confiavel={lb_ok} "
                    f"ncol={ncol_atual} iterCG={getattr(no_atual, 'iter_cg_final', None)} "
                    f"melhorRC_por_k={getattr(no_atual, 'melhor_rc_por_k', {})} "
                    f"motivoCG={getattr(sol_pool, 'motivoConv', None)}"
                )

            # -------------------------------------------------
            # poda por bound (SÓ com LB confiável)
            # -------------------------------------------------
            if lb_ok and (not math.isinf(z_inc)) and (z_lp > z_inc - 1e-6):
                print(f"Poda por bound (LB ok): LP {z_lp:.4f} >= z_inc {z_inc:.4f}")
                no_atual.status = "podado"
                no_atual.motivo_poda = "poda_bound"
                diag_list.append({
                    "no_id": no_atual.id_no, "profundidade": prof,
                    "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                    "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                    "motivo_conv": getattr(sol_pool, "motivoConv", None),
                    "custo_lp": no_atual.custo_lp,
                    "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                    "custo_mip": getattr(no_atual, "custo_mip", None),
                    "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                    "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                    "abriu_filhos": False,
                    "z_inc": None if math.isinf(z_inc) else z_inc,
                    "z_li": None if math.isinf(z_li) else z_li,
                    "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
                })
                continue

            # -------------------------------------------------
            # caso 1: nó tem novo inteiro
            # -------------------------------------------------
            no_inteiro_sem_certificacao = False  # item 5: forca busca de arco fracionario no caso 2
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

                if abs(float(z_mip) - float(z_lp)) <= 1e-6:  # incumbente é igual a fracionaria (com tolerancia): so prova integralidade se o no estiver certificado
                    no_certificado = (
                        bool(getattr(no_atual, "cg_convergiu", False))
                        and bool(getattr(no_atual, "lb_confiavel", False))
                        and not bool(getattr(no_atual, "parou_por_max_iter", False))
                        and float(getattr(no_atual, "slack_sum_final", float("inf"))) <= 1e-6
                    )

                    if no_certificado:
                        print("PODOU por integralidade certificada")
                        no_atual.status = "podado"
                        no_atual.motivo_poda = no_atual.motivo_poda or "no_inteiro_certificado"
                        diag_list.append({
                            "no_id": no_atual.id_no, "profundidade": prof,
                            "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                            "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                            "motivo_conv": getattr(sol_pool, "motivoConv", None),
                            "custo_lp": no_atual.custo_lp,
                            "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                            "custo_mip": getattr(no_atual, "custo_mip", None),
                            "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                            "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                            "abriu_filhos": False,
                            "z_inc": None if math.isinf(z_inc) else z_inc,
                            "z_li": None if math.isinf(z_li) else z_li,
                            "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
                        })
                        continue

                    # Mestre restrito inteiro, mas pricing/LB nao certificado: o incumbente
                    # (ja atualizado acima, se melhor) fica valido, mas NAO prova que o no
                    # e uma folha otima -- nao pode ser podado por integralidade.
                    print("[NAO PODOU] Mestre restrito inteiro, mas pricing/LB nao certificado.")

                    if (time.time() - sol_pool.time_initial) >= sol_pool.TIME_MAX:
                        print(f"Nó {no_atual.id_no}: TIME_MAX global atingido com nó inteiro não certificado -- encerrando B&P, incumbente preservado, certificação global permanece falsa.")
                        # item 4: nao usar "resolvido" -- esse status seria lido
                        # como se o no tivesse sido concluido de forma confiavel;
                        # "interrompido" deixa explicito que ficou pendente.
                        no_atual.status = "interrompido"
                        no_atual.motivo_poda = None
                        sol_pool.terminou_por_tempo = True  # PARTE 2: instrumentacao
                        sol_pool.houve_no_interrompido = True  # PARTE 2: instrumentacao
                        diag_list.append({
                            "no_id": no_atual.id_no, "profundidade": prof,
                            "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                            "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                            "motivo_conv": getattr(sol_pool, "motivoConv", None),
                            "custo_lp": no_atual.custo_lp,
                            "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                            "custo_mip": getattr(no_atual, "custo_mip", None),
                            "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                            "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                            "abriu_filhos": False,
                            "z_inc": None if math.isinf(z_inc) else z_inc,
                            "z_li": None if math.isinf(z_li) else z_li,
                            "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
                        })
                        break

                    # Tempo global nao esgotado: nao poda por bound nem por integralidade,
                    # nao trata como resolvido de forma exata -- segue para o tratamento
                    # ja existente de nó fracionário/não confiável (caso 2 abaixo), que so
                    # tenta abrir filhos se houver lambda fracionário para o branching.
                    # item 5: marca para o caso 2 sempre TENTAR achar um arco
                    # fracionario (nao pular a busca so por z_mip==z_lp).
                    no_inteiro_sem_certificacao = True
                # nome_arquivo_log = f"log_bounds_{inst.nbcd}_{inst.ninst}.csv"
                # with open(nome_arquivo_log, "a", encoding="utf-8") as f:
                #    f.write(f"{no_atual.id_no};{z_inc};{z_lp};{z_li};{self.total_colunas}\n")

                print("")

            # -------------------------------------------------
            # caso 2: melhor fracionário -> branching
            # -------------------------------------------------
            print(f"Nó {no_atual.id_no} Valor fracionário com custo {z_lp:.4f}")

            if z_lp < z_frac:
                z_frac = z_lp
                melhor_no_frac = no_atual
                print(f"ATUALIZOU MELHOR FRAC Nó {no_atual.id_no} Valor fracionário com custo {z_lp:.4f}")

            filho_esq = None
            filho_dir = None
            if ((time.time() - sol_pool.time_initial) < sol_pool.TIME_TARGET):
                # item 5: um no inteiro-mas-nao-certificado nao pode pular a
                # busca por arco fracionario so porque z_mip==z_lp -- o custo
                # bater nao garante que o lambda do LP seja integral.
                if (abs(float(z_mip) - float(z_lp)) > 1e-6) or no_inteiro_sem_certificacao:
                    print("DIVIDE")
                    filho_esq, filho_dir, id_no = self.criar_filhos_por_arco(inst, sol_pool, no_atual, id_no)
                else:
                    print("INTEIROSS")
            # filho_esq, filho_dir, id_no = self.criar_filhos_por_arco075(inst, sol_pool, no_atual, id_no, melhor_no)

            abriu_filhos = (filho_esq is not None) and (filho_dir is not None)
            if abriu_filhos:
                if getattr(inst, "objective_mode", "petrobras") == "silva2024":
                    bfrom = filho_dir.branching_from or {}
                    arco_sel = tuple(bfrom.get("arco", ()))
                    score_sel = getattr(no_atual, "arc_score", {}).get(arco_sel)
                    print(
                        f"[SILVA BRANCH] no_pai={no_atual.id_no} arco={arco_sel} score={score_sel} "
                        f"filho_proibe={filho_esq.id_no} filho_fixa={filho_dir.id_no}"
                    )

                # >>> IMPORTANTE: filhos NÃO herdam custo_lp do pai
                filho_esq.custo_lp = None
                filho_dir.custo_lp = None

                filho_esq.status = "ativo"
                filho_dir.status = "ativo"

                ativos.append((filho_esq, prof + 1, no_atual.id_no))
                ativos.append((filho_dir, prof + 1, no_atual.id_no))
            elif no_inteiro_sem_certificacao:
                # item 5: inteiro nao certificado e sem elemento fracionario
                # para branch -- preserva o incumbente (ja atualizado acima),
                # mas o no fica pendente/nao certificado, nunca "podado" por
                # integralidade nem contado como resolvido.
                print(f"[NAO CERTIFICADO] Nó {no_atual.id_no}: inteiro mas nao certificado, sem arco fracionario para branch -- fica interrompido.")
                no_atual.status = "interrompido"
                no_atual.motivo_poda = None
                sol_pool.houve_no_interrompido = True  # PARTE 2: instrumentacao
            else:
                no_atual.status = "podado"
                no_atual.motivo_poda = "sem_lambda_fracionario"

            diag_list.append({
                "no_id": no_atual.id_no, "profundidade": prof,
                "lb_confiavel": getattr(no_atual, "lb_confiavel", None),
                "cg_convergiu": getattr(no_atual, "cg_convergiu", None),
                "motivo_conv": getattr(sol_pool, "motivoConv", None),
                "custo_lp": no_atual.custo_lp,
                "melhor_lp_valido": getattr(no_atual, "melhor_lp_valido", None),
                "custo_mip": getattr(no_atual, "custo_mip", None),
                "slack_sum_final": getattr(no_atual, "slack_sum_final", None),
                "solucao_inteira": getattr(no_atual, "solucao_inteira", None),
                "abriu_filhos": abriu_filhos,
                "z_inc": None if math.isinf(z_inc) else z_inc,
                "z_li": None if math.isinf(z_li) else z_li,
                "n_colunas_pool": sum(len(v["sequencia_rota"]) for v in sol_pool.rotas.values()),
            })
            print(f"FIM do nó  {no_atual.id_no} ")

        # =========================
        # Fim
        # =========================
        # ----- LB GLOBAL CERTIFICADA (lida pela main no [BP_FIM]) -----
        # Caso 1: arvore explorada por completo e todos os nos com CG convergido
        #         -> otimalidade provada: LB = melhor inteira (z_inc).
        # Caso 2: parada por gap/tempo com nos abertos, todos com LB confiavel
        #         -> LB = min entre os custos_lp confiaveis dos abertos e z_inc.
        custos_conf_abertos = [
            no.custo_lp for (no, _, _) in ativos
            if (no.custo_lp is not None) and getattr(no, "lb_confiavel", False)
        ]
        abertos_nao_conf = [
            no for (no, _, _) in ativos
            if (no.custo_lp is None) or not getattr(no, "lb_confiavel", False)
        ]
        if (not ativos) and todos_nos_confiaveis and (not math.isinf(z_inc)):
            sol_pool.lb_global_confiavel = z_inc
        elif ativos and (not abertos_nao_conf) and custos_conf_abertos:
            sol_pool.lb_global_confiavel = min(min(custos_conf_abertos), z_inc)

        # item 6: sinal separado para otimalidade -- todos_nos_confiaveis e um
        # AND acumulado sobre TODO no ja processado (mesmo os depois descartados
        # como "interrompido"), entao so fica True se a arvore foi esgotada
        # (ativos vazio) e nenhum no processado ficou nao certificado/interrompido
        # pelo caminho. lb_global_confiavel sozinho NAO garante isso (o ramo por
        # gap/tempo com nos abertos todos confiaveis pode ainda ter descartado um
        # no interrompido que ja saiu de ativos).
        sol_pool.arvore_certificada_completa = (not ativos) and todos_nos_confiaveis

        print("\n==== FIM B&P ====")

        if diag_list:
            import csv
            # Cada instancia ja roda dentro da sua propria pasta work/; usar so "diag.csv"
            # evita nomes de caminho gigantes (erro no Windows) sem sobrescrever entre instancias.
            diag_path = "diag.csv"
            with open(diag_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(diag_list[0].keys()))
                writer.writeheader()
                writer.writerows(diag_list)
            print(f"Diagnóstico salvo em {diag_path}")

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
        # self._salvar_log_bp()

    def SearchCOl_global(self, inst, sol_pool, tipo_geracao="PD"):

        # limpeza arquivo principal dos logs meus
        nome_arquivo_log = f"SC_log_bounds_{inst.nbcd}_{inst.ninst}.csv"

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
            # teste poda do no ja com o herdado
            if no_atual.custo_lp_HERDADO is not None and not math.isinf(z_inc):
                if no_atual.custo_lp_HERDADO > z_inc - 1e-6:
                    print(
                        f"Poda nó {no_atual.id_no} por bound herdado: {no_atual.custo_lp_HERDADO:.4f} >= incumbente {z_inc:.4f}")
                    no_atual.status = "podado"
                    no_atual.motivo_poda = "bound_herdado"
                    continue

            self.resolver_no_com_pool(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)
            # self.resolver_no_com_pool_semSlack(inst, sol_pool, no_atual, tipo_geracao=tipo_geracao)

            # caso 0: LP inviável/sem solução
            if (no_atual.id_no == 50):
                print("")
            print(f'Tempo total: {time.time() - t00:.1f}s')
            if no_atual.custo_lp is None:
                print("Nó inviável ou sem solução LP, podado.")
                no_atual.status = "podado"
                no_atual.motivo_poda = "LP_inviavel"
                continue

            z_lp = float(no_atual.custo_lp)
            z_mip = float(no_atual.custo_mip) if no_atual.custo_mip is not None else float("inf")

            # Saída antecipada: melhor_int pode ser melhor que custo_mip se o post-loop LP distorceu.
            melhor_int_direto = getattr(no_atual, "melhor_int", float("inf"))
            if melhor_int_direto < z_mip - 1e-6:
                z_mip = melhor_int_direto
                no_atual.custo_mip = z_mip
                no_atual.solucao_inteira = True

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

                if (z_mip == z_lp):  # incumbente é igual a fracionaria, logo o nó é inteiro
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

            filho_esq = None
            filho_dir = None
            if ((time.time() - sol_pool.time_initial) < sol_pool.TIME_TARGET):
                if (z_mip != z_lp):
                    # teste do tempo max

                    print("DIVIDE")
                    filho_esq, filho_dir, id_no = self.criar_filhos_por_arco(inst, sol_pool, no_atual, id_no)
                else:
                    print("INTEIROSS")
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
        # self._salvar_log_bp()

    def SUB_PROG_DIN_PW(self, inst, pi, sigma_k, k, NO_BP,
                        arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                        # widening_seq=(1, 2, 4, 8, "ALL"),
                        widening_seq=(4, 8, "ALL"),
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
        # """
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

        # """
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

    def SUB_PROG_DIN_BIDIRECIONAL_CPP(
            self, inst, pi, sigma_k, k,
            arcos_proibidos=None,
            arcos_fixados=None,
            mu_arc=None,
            eps=1e-6
    ):
        import os
        import sys
        import numpy as np

        from pathlib import Path
        import sys
        # base = Path(r"C:\Users\PolyanaSilva\Documents\BP_VRPTW\PD_PARA_PYTHON\PD_PARA_PYTHON")
        # >>> AJUSTE v5c: caminho relativo ao proprio metodos.py — funciona em
        # qualquer maquina, desde que a pasta PD_PARA_PYTHON esteja dentro da
        # pasta do projeto (ao lado deste arquivo).
        base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
        p_release = base / "x64" / "Release"
        p_debug = base / "x64" / "Debug"

        if p_release.exists():
            sys.path.append(str(p_release))
        if p_debug.exists():
            sys.path.append(str(p_debug))

        import vrptw_pd

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = inst.nbn - 1

        tt = np.array([
            [inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade for j in range(nbn)]
            for i in range(nbn)
        ], dtype=np.float64)

        a = np.array(
            [inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0.0 for i in range(nbn)],
            dtype=np.float64
        )
        b = np.array(
            [inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9 for i in range(nbn)],
            dtype=np.float64
        )
        s = np.array(
            [inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0.0 for i in range(nbn)],
            dtype=np.float64
        )
        d = np.array(
            [inst.noh[i].DEMAND if hasattr(inst.noh[i], "DEMAND") else 0.0 for i in range(nbn)],
            dtype=np.float64
        )

        cap_k = float(inst.veiculos[k].capacidade)

        if mu_arc is None:
            mu_flat = np.zeros(nbn * nbn, dtype=np.float64)
        else:
            mu_flat = np.zeros(nbn * nbn, dtype=np.float64)
            for key, val in mu_arc.items():
                if len(key) == 3:
                    i, j, kk = key
                    if kk != k:
                        continue
                else:
                    i, j = key
                mu_flat[i * nbn + j] = float(val)

        forbid_flat = np.zeros(nbn * nbn, dtype=np.uint8)
        if arcos_proibidos:
            for arco in arcos_proibidos:
                if len(arco) == 3:
                    i, j, kk = arco
                    if kk != k:
                        continue
                else:
                    i, j = arco
                forbid_flat[i * nbn + j] = 1

        req_i, req_j = [], []
        if arcos_fixados:
            for arco in arcos_fixados:
                if len(arco) == 3:
                    i, j, kk = arco
                    if kk != k:
                        continue
                else:
                    i, j = arco
                req_i.append(i)
                req_j.append(j)
        """
        rota, rc = vrptw_pd.sub_prog_din_bidirecional(
            tt=tt,
            a=a.tolist(),
            b=b.tolist(),
            s=s.tolist(),
            d=d.tolist(),
            pi=list(map(float, pi)),
            sigma_k=float(sigma_k),
            cap_k=cap_k,
            nbcd=nbcd,
            dep0=dep0,
            depf=depf,
            mu_flat=mu_flat.tolist(),
            forbid_flat=forbid_flat.tolist(),
            req_i=req_i,
            req_j=req_j,
            eps=float(eps),
        )
        """
        rota, rc = self.chamar_cpp_timeout(
            vrptw_pd.sub_prog_din_bidirecional,
            (),
            kwargs={
                "tt": tt,
                "a": a.tolist(),
                "b": b.tolist(),
                "s": s.tolist(),
                "d": d.tolist(),
                "pi": list(map(float, pi)),
                "sigma_k": float(sigma_k),
                "cap_k": cap_k,
                "nbcd": nbcd,
                "dep0": dep0,
                "depf": depf,
                "mu_flat": mu_flat.tolist(),
                "forbid_flat": forbid_flat.tolist(),
                "req_i": req_i,
                "req_j": req_j,
                "eps": float(eps),
            },
            timeout=600
        )

        if rota is None:
            return None, None

        return rota, rc

    def _get_vrptw_pd_module(self):
        """Importa (e cacheia em self) o modulo pybind11 vrptw_pd, reaproveitando
        o mesmo caminho relativo usado em SUB_PROG_DIN_BIDIRECIONAL_CPP. Retorna
        None se o .pyd nao existir/nao carregar (fallback Python continua valido)."""
        if not hasattr(self, "_vrptw_pd_mod_cache"):
            import sys
            from pathlib import Path

            base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
            p_release = base / "x64" / "Release"
            p_debug = base / "x64" / "Debug"

            if p_release.exists():
                sys.path.append(str(p_release))
            if p_debug.exists():
                sys.path.append(str(p_debug))

            try:
                import vrptw_pd
                self._vrptw_pd_mod_cache = vrptw_pd
            except ImportError:
                self._vrptw_pd_mod_cache = None

        return self._vrptw_pd_mod_cache

    def _montar_dados_petro_cpp(self, inst, k, NO_BP=None, mu_arc=None):
        import numpy as np
        nbn, nbcd, dep0, depf = inst.nbn, inst.nbcd, 0, inst.nbn - 1
        tt = np.array([[inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade for j in range(nbn)] for i in range(nbn)], dtype=np.float64)
        aw, bw, s, d_deck, b_deck, d_diesel, d_agua = [], [], [], [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            aw.append(list(noh.READY_TIME) if hasattr(noh, "READY_TIME") and noh.READY_TIME else [0.0])
            bw.append(list(noh.DUE_DATE) if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else [1e9])
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d_deck.append(getattr(noh, "DEMAND_DECK_LOAD", 0.0))
            b_deck.append(getattr(noh, "DEMAND_DECK_BACKLOAD", 0.0))
            d_diesel.append(getattr(noh, "DEMAND_DIESEL", 0.0))
            d_agua.append(getattr(noh, "DEMAND_AGUA", 0.0))
        plataforma_id = [-1] * nbn
        mapa_plataformas = {}
        nomes = inst.dados_petro["nomes"]

        for i in range(1, nbcd + 1):
            nome = str(nomes[i])

            if "_order_" in nome:
                plataforma = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                plataforma = nome.split("_order", 1)[0]
            else:
                plataforma = nome

            if plataforma not in mapa_plataformas:
                mapa_plataformas[plataforma] = len(mapa_plataformas)

            plataforma_id[i] = mapa_plataformas[plataforma]

        mu_flat = np.zeros(nbn * nbn, dtype=np.float64)
        if mu_arc:
            for key, val in mu_arc.items():
                if len(key) == 3:
                    i, j, kk = key
                    if kk != k: continue
                else:
                    i, j = key
                mu_flat[i * nbn + j] = float(val)
        forbid_flat = np.zeros(nbn * nbn, dtype=np.uint8)
        if NO_BP and NO_BP.arcos_proibidos:
            for arco in NO_BP.arcos_proibidos:
                if len(arco) == 3:
                    i, j, kk = arco
                    if kk != k: continue
                else:
                    i, j = arco
                forbid_flat[i * nbn + j] = 1
        req_i, req_j = [], []
        if NO_BP and NO_BP.arcos_fixados_em_1:
            for arco in NO_BP.arcos_fixados_em_1:
                if len(arco) == 3:
                    i, j, kk = arco
                    if kk != k: continue
                else:
                    i, j = arco
                req_i.append(i); req_j.append(j)

        return tt, aw, bw, s, d_deck, b_deck, d_diesel, d_agua, plataforma_id, float(
            inst.veiculos[k].capacidade), float(inst.veiculos[k].cap_diesel), float(
            inst.veiculos[k].cap_agua), nbcd, dep0, depf, mu_flat, forbid_flat, req_i, req_j
    def SUB_PROG_DIN_PETRO_CPP(self, inst, pi, sigma_k, k, NO_BP=None, mu_arc=None, eps=1e-6, timeout_s=15, max_labels_por_no=1_000_000_000):
        vrptw_pd = self._get_vrptw_pd_module()
        if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_petro"): raise RuntimeError("vrptw_pd.sub_prog_din_petro indisponivel (modulo C++ nao recompilado)")
        tt, aw, bw, s, d_deck, b_deck, d_diesel, d_agua, plataforma_id, cap_deck, cap_diesel, cap_agua, nbcd, dep0, depf, mu_flat, forbid_flat, req_i, req_j = self._montar_dados_petro_cpp(inst, k, NO_BP, mu_arc)
        kwargs = {"tt": tt, "plataforma_id": plataforma_id,"aw": aw, "bw": bw, "s": s, "d_deck": d_deck, "b_deck": b_deck, "d_diesel": d_diesel, "d_agua": d_agua, "pi": list(map(float, pi)), "sigma_k": float(sigma_k), "cap_deck": cap_deck, "cap_diesel": cap_diesel, "cap_agua": cap_agua, "nbcd": nbcd, "dep0": dep0, "depf": depf, "mu_flat": mu_flat.tolist(), "forbid_flat": forbid_flat.tolist(), "req_i": req_i, "req_j": req_j, "max_labels_por_no": int(max_labels_por_no), "eps": float(eps)}
        t0 = time.time(); rota, rc = self.chamar_cpp_timeout(vrptw_pd.sub_prog_din_petro, kwargs=kwargs, timeout=timeout_s)
        print(f"[PETRO PD] k={k} | limite={timeout_s}s | tempo={time.time() - t0:.2f}s | timeout={self._ultimo_timeout_cpp}")
        return (None, None) if rota is None else (rota, rc)

    def SUB_PROG_DIN_BIDIRECIONAL_PETRO_CPP(self, inst, pi, sigma_k, k, NO_BP=None, mu_arc=None, eps=1e-6, timeout_s=5, max_labels_por_no=200, max_depth=None, max_combinacoes=200_000):
        vrptw_pd = self._get_vrptw_pd_module()
        if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_bidirecional_petro"): raise RuntimeError("vrptw_pd.sub_prog_din_bidirecional_petro indisponivel; recompile o C++ em Release")
        tt, aw, bw, s, d_deck, b_deck, d_diesel, d_agua, plataforma_id, cap_deck, cap_diesel, cap_agua, nbcd, dep0, depf, mu_flat, forbid_flat, req_i, req_j = self._montar_dados_petro_cpp(
            inst, k, NO_BP, mu_arc)
        if max_depth is None: max_depth = (nbcd + 2) // 2
        kwargs = {"tt": tt,"plataforma_id": plataforma_id, "aw": aw, "bw": bw, "s": s, "d_deck": d_deck, "b_deck": b_deck, "d_diesel": d_diesel, "d_agua": d_agua, "pi": list(map(float, pi)), "sigma_k": float(sigma_k), "cap_deck": cap_deck, "cap_diesel": cap_diesel, "cap_agua": cap_agua, "nbcd": nbcd, "dep0": dep0, "depf": depf, "mu_flat": mu_flat.tolist(), "forbid_flat": forbid_flat.tolist(), "req_i": req_i, "req_j": req_j, "max_labels_por_no": int(max_labels_por_no), "max_depth": int(max_depth), "max_combinacoes": int(max_combinacoes), "eps": float(eps)}
        t0 = time.time(); rota, rc = self.chamar_cpp_timeout(vrptw_pd.sub_prog_din_bidirecional_petro, kwargs=kwargs, timeout=timeout_s)
        print(f"[PETRO BID] k={k} | limite={timeout_s}s | labels={max_labels_por_no} | depth={max_depth} | tempo={time.time() - t0:.2f}s | timeout={self._ultimo_timeout_cpp}")
        return (None, None) if rota is None else (rota, rc)

    def _petro_pricing_exato(self, inst, pi, sigma_k, k, no_bp=None, mu_arc=None, timeout_s=15, max_labels_por_no=1_000_000_000):
        vrptw_pd = self._get_vrptw_pd_module()
        usa_cpp = vrptw_pd is not None and hasattr(vrptw_pd, "sub_prog_din_petro")
        print(f"[PETRO] pricing exato via {'C++ (sub_prog_din_petro)' if usa_cpp else 'Python (SUB_PROG_DIN_PETRO)'}")
        if usa_cpp: return self.SUB_PROG_DIN_PETRO_CPP(inst, pi, sigma_k, k, NO_BP=no_bp, mu_arc=mu_arc, timeout_s=timeout_s, max_labels_por_no=max_labels_por_no)
        return self.SUB_PROG_DIN_PETRO(inst, pi, sigma_k, k, arcos_proibidos=no_bp.arcos_proibidos if no_bp else None, arcos_fixados=no_bp.arcos_fixados_em_1 if no_bp else None, mu_arc=mu_arc)

    def _candidatas_cpp_para_padrao(self, k, candidatas_raw, origem):
        """Converte a lista de dicts do C++ ({clientes,custo,bin_xij,custo_reduzido})
        para o formato padrao Python da secao 2: {k, seq, binx, custo, rc, origem}."""
        return [
            {
                "k": k,
                "seq": list(c["clientes"]),
                "binx": list(c["bin_xij"]),
                "custo": float(c["custo"]),
                "rc": float(c["custo_reduzido"]),
                "origem": origem,
            }
            for c in candidatas_raw
        ]

    def SUB_PROG_DIN_PETRO_CPP_MULTI(self, inst, pi, sigma_k, k, rotas_existentes_k, NO_BP=None, mu_arc=None,
                                      eps=1e-6, timeout_s=15, max_labels_por_no=1_000_000_000, max_candidatas=None):
        """Multi-candidatas do pricing exato Petro (sub_prog_din_petro_multi).
        rotas_existentes_k: iteravel de tuplas/sequencias ja no pool deste veiculo k
        (secao 3) -- usado somente para descartar rotas COMPLETAS repetidas, nunca
        para podar arcos/labels/dominancia. Retorna (candidatas, busca_completa, timeout)."""
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        vrptw_pd = self._get_vrptw_pd_module()
        if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_petro_multi"):
            raise RuntimeError("vrptw_pd.sub_prog_din_petro_multi indisponivel; recompile o C++ em Release")
        tt, aw, bw, s, d_deck, b_deck, d_diesel, d_agua, plataforma_id, cap_deck, cap_diesel, cap_agua, nbcd, dep0, depf, mu_flat, forbid_flat, req_i, req_j = self._montar_dados_petro_cpp(
            inst, k, NO_BP, mu_arc)
        kwargs = {
            "tt": tt, "plataforma_id": plataforma_id, "aw": aw, "bw": bw, "s": s,
            "d_deck": d_deck, "b_deck": b_deck, "d_diesel": d_diesel, "d_agua": d_agua,
            "pi": list(map(float, pi)), "sigma_k": float(sigma_k),
            "cap_deck": cap_deck, "cap_diesel": cap_diesel, "cap_agua": cap_agua,
            "nbcd": nbcd, "dep0": dep0, "depf": depf,
            "mu_flat": mu_flat.tolist(), "forbid_flat": forbid_flat.tolist(),
            "req_i": req_i, "req_j": req_j,
            "rotas_excluidas": [list(seq) for seq in rotas_existentes_k],
            "max_candidatas": int(max_candidatas),
            "max_labels_por_no": int(max_labels_por_no), "eps": float(eps),
        }
        t0 = time.time()
        candidatas_raw, busca_completa, timeout_flag = self.chamar_cpp_timeout_multi(
            vrptw_pd.sub_prog_din_petro_multi, kwargs=kwargs, timeout=timeout_s
        )
        if self._ultimo_timeout_cpp:
            busca_completa, timeout_flag = False, True
        print(f"[PETRO PD MULTI] k={k} | limite={timeout_s}s | tempo={time.time() - t0:.2f}s | "
              f"candidatas={len(candidatas_raw)} | completa={busca_completa} | timeout={timeout_flag}")
        return self._candidatas_cpp_para_padrao(k, candidatas_raw, "PD_CPP"), busca_completa, timeout_flag

    def SUB_PROG_DIN_BIDIRECIONAL_PETRO_CPP_MULTI(self, inst, pi, sigma_k, k, rotas_existentes_k, NO_BP=None, mu_arc=None,
                                                    eps=1e-6, timeout_s=5, max_labels_por_no=200, max_depth=None,
                                                    max_combinacoes=200_000, max_candidatas=None):
        """Multi-candidatas do pricing bidirecional heuristico Petro
        (sub_prog_din_bidirecional_petro_multi). Heuristico -> busca_completa
        sempre False (nunca certifica ausencia de outras colunas negativas)."""
        _default_labels = max(200, inst.nbcd * 60)
        _ov = getattr(inst, "pricing_max_labels", None)
        max_labels_por_no = int(_ov) if _ov is not None else _default_labels
        _ov_t = getattr(inst, "pricing_timeout_s", None)
        if _ov_t is not None: timeout_s = float(_ov_t)
        _ov_c = getattr(inst, "pricing_max_combinacoes", None)
        if _ov_c is not None: max_combinacoes = int(_ov_c)
        print(f"[PRICING CAPS] nbcd={inst.nbcd} max_labels={max_labels_por_no} "
              f"timeout_s={timeout_s if 'timeout_s' in dir() else 'NA'} "
              f"max_comb={max_combinacoes if 'max_combinacoes' in dir() else 'NA'}", flush=True)
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        vrptw_pd = self._get_vrptw_pd_module()
        if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_bidirecional_petro_multi"):
            raise RuntimeError("vrptw_pd.sub_prog_din_bidirecional_petro_multi indisponivel; recompile o C++ em Release")
        tt, aw, bw, s, d_deck, b_deck, d_diesel, d_agua, plataforma_id, cap_deck, cap_diesel, cap_agua, nbcd, dep0, depf, mu_flat, forbid_flat, req_i, req_j = self._montar_dados_petro_cpp(
            inst, k, NO_BP, mu_arc)
        if max_depth is None: max_depth = (nbcd + 2) // 2
        kwargs = {
            "tt": tt, "plataforma_id": plataforma_id, "aw": aw, "bw": bw, "s": s,
            "d_deck": d_deck, "b_deck": b_deck, "d_diesel": d_diesel, "d_agua": d_agua,
            "pi": list(map(float, pi)), "sigma_k": float(sigma_k),
            "cap_deck": cap_deck, "cap_diesel": cap_diesel, "cap_agua": cap_agua,
            "nbcd": nbcd, "dep0": dep0, "depf": depf,
            "mu_flat": mu_flat.tolist(), "forbid_flat": forbid_flat.tolist(),
            "req_i": req_i, "req_j": req_j,
            "rotas_excluidas": [list(seq) for seq in rotas_existentes_k],
            "max_candidatas": int(max_candidatas),
            "max_labels_por_no": int(max_labels_por_no), "max_depth": int(max_depth),
            "max_combinacoes": int(max_combinacoes), "eps": float(eps),
        }
        t0 = time.time()
        candidatas_raw, busca_completa, timeout_flag = self.chamar_cpp_timeout_multi(
            vrptw_pd.sub_prog_din_bidirecional_petro_multi, kwargs=kwargs, timeout=timeout_s
        )
        if self._ultimo_timeout_cpp:
            busca_completa, timeout_flag = False, True
        print(f"[PETRO BID MULTI] k={k} | limite={timeout_s}s | labels={max_labels_por_no} | depth={max_depth} | "
              f"tempo={time.time() - t0:.2f}s | candidatas={len(candidatas_raw)} | timeout={timeout_flag}")
        return self._candidatas_cpp_para_padrao(k, candidatas_raw, "BID_CPP"), False, timeout_flag

    def _petro_pricing_exato_multi(self, inst, pi, sigma_k, k, rotas_existentes_k, no_bp=None, mu_arc=None,
                                    timeout_s=15, max_labels_por_no=1_000_000_000, max_candidatas=None):
        """Multi-candidatas do pricing exato Petro, com o mesmo fallback de
        _petro_pricing_exato quando o C++ multi nao estiver disponivel (nesse
        caso, busca_completa=False sempre -- a via legada nao certifica)."""
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        vrptw_pd = self._get_vrptw_pd_module()
        usa_cpp_multi = vrptw_pd is not None and hasattr(vrptw_pd, "sub_prog_din_petro_multi")
        print(f"[PETRO] pricing exato multi via {'C++ (sub_prog_din_petro_multi)' if usa_cpp_multi else 'fallback single-candidate (sem certificacao)'}")

        if usa_cpp_multi:
            return self.SUB_PROG_DIN_PETRO_CPP_MULTI(
                inst, pi, sigma_k, k, rotas_existentes_k, NO_BP=no_bp, mu_arc=mu_arc,
                timeout_s=timeout_s, max_labels_por_no=max_labels_por_no, max_candidatas=max_candidatas
            )

        rota, rc = self._petro_pricing_exato(inst, pi, sigma_k, k, no_bp=no_bp, mu_arc=mu_arc,
                                              timeout_s=timeout_s, max_labels_por_no=max_labels_por_no)
        timeout_flag = bool(self._ultimo_timeout_cpp)
        if rota is None:
            return [], False, timeout_flag
        seq = list(rota["clientes"])
        if tuple(seq) in rotas_existentes_k:
            return [], False, timeout_flag
        candidata = {"k": k, "seq": seq, "binx": list(rota["bin_xij"]), "custo": float(rota["custo"]),
                     "rc": float(rc), "origem": "PD_FALLBACK"}
        return [candidata], False, timeout_flag

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
        pesos = []
        for pos in range(len(lista_ordenada)):
            pesos.append(alpha ** pos)

        return (random.choices(lista_ordenada, weights=pesos, k=1)[0])

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

    def SUB_HEUR_ALLBESTINSERTION_MULTI(self, inst, sol_pool, pi, sigma_k, k, NO_BP, mu_arc=None,
                                         n_starts=30, eps=1e-6, max_candidatas=None):
        """Mesma heuristica ALLBEST (GRASP + insercao + busca local), mas em vez de
        retornar na primeira candidata negativa inedita, continua tentando os demais
        starts para acumular ate max_candidatas negativas ineditas (rc < -eps, nao
        duplicadas no pool nem dentro deste lote). Nao altera n_starts/seeds/alpha da
        RCL/scores/regras de insercao ou viabilidade/branching/tabu/criterios internos
        de parada de cada start -- so o que acontece com uma candidata aceita ao final
        de um start (guardar e continuar, em vez de retornar).

        Retorna (candidatas, busca_completa, timeout):
            candidatas: lista de dicts {k, seq, binx, custo, rc, origem}, ordenada
                        pelo rc mais negativo primeiro.
            busca_completa: sempre False (heuristica GRASP, nao certifica ausencia
                        de outras colunas negativas).
            timeout: sempre False (ALLBEST nao usa timeout).
        """
        import math
        import random

        if mu_arc is None:
            mu_arc = {}
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING

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

            # Tabu opcional (somente ALLBEST; diversificacao heuristica, nunca prova de
            # ausencia de coluna negativa). Desativado por padrao (TABU=0 -> tabu_tenure=0).
            obrigatorio = (i, j) in fixados_k
            if not obrigatorio:
                tabu_tenure = getattr(NO_BP, "tabu_tenure", 0)
                tabu_until = getattr(NO_BP, "tabu_until", None)
                if tabu_tenure and tabu_tenure > 0 and tabu_until is not None:
                    if tabu_until[k][i][j] > 0:
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

                    if fim_servico_j <= bj + 1e-9:
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

        candidatas = []
        vistas_no_lote = set()

        base = constroi_rota_base()

        if base is None:
            if len(fixados_k) > 0:
                return [], False, False

            rota0 = [dep0, depf]
            viavel_ini, janelas_escolhidas0, tempo_final0, carga_final0 = verifica_viabilidade(rota0)
            if not viavel_ini:
                return [], False, False

            base = (rota0, {dep0, depf}, janelas_escolhidas0, tempo_final0, carga_final0)

        for ii in range(n_starts):
            if len(candidatas) >= max_candidatas:
                break

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

                # Escolhe a melhor rota deste start (com busca local se disponível)
                rota_start = rota_melhorada if rota_melhorada is not None else rota
                rc_start   = custo_red_melhorado if rota_melhorada is not None else custo_reduzido_rota(rota)
                custo_start = custo_real_melhorado if rota_melhorada is not None else custo_real_rota(rota)

                if rc_start < -eps:
                    chave = tuple(rota_start)
                    if chave in vistas_no_lote:
                        continue  # já coletada neste mesmo lote
                    if sol_pool is None or not sol_pool.coluna_ja_existe(rota_start, k=k, globalmente=False):
                        vistas_no_lote.add(chave)
                        candidatas.append({
                            "k": k,
                            "seq": list(rota_start),
                            "binx": rota_para_binaria(rota_start),
                            "custo": float(custo_start),
                            "rc": float(rc_start),
                            "origem": "ALLBEST",
                        })
                        if len(candidatas) >= max_candidatas:
                            break
                    # Já existe no pool → tenta próximo start (GRASP gera rota diferente)

        candidatas.sort(key=lambda c: c["rc"])
        return candidatas, False, False

    def SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA(self, inst, sol_pool, pi, sigma_k, k, NO_BP, mu_arc=None,
                                               n_starts=30, eps=1e-6, max_candidatas=None):
        """Heuristica ALLBEST (GRASP + insercao), EXCLUSIVA de objective_mode=="silva2024",
        primeira etapa da nova arquitetura de pricing Silva (reaproveita a arquitetura do
        B&P atual; ainda NAO implementa BID_SILVA/PD_SILVA). Reaproveita de
        SUB_HEUR_ALLBESTINSERTION_MULTI: multi-start GRASP, insercao incremental de
        pedidos, eliminacao de duplicatas (vistas_no_lote/coluna_ja_existe), respeito ao
        branching (NO_BP.arcos_proibidos/arcos_fixados_em_1 via arco_permitido/
        contem_todos_fixados), pi/sigma/mu com o MESMO papel/formato (mu_arc[(i,j,k)] com
        fallback (i,j)), e o mesmo formato de retorno (candidatas, busca_completa=False,
        timeout=False).

        SUBSTITUIDO por avaliacao Silva: toda viabilidade e todo custo de rota (base,
        insercoes, rota final) vem de self.avaliar_rota_silva2024(inst, k, seq) -- a
        MESMA fisica/oraculo ja usado por pricing_silva2024/metodo_exato_petro (VL/VH,
        SP, SET, janelas, dueTime, carregamento na base, servico offshore, espera,
        backload, capacidades, TDL, precedencia por compartimento). Nada da formula
        fisica Silva e reimplementado aqui -- so a formula de custo reduzido (rc_silva,
        identica a _calcular_rc_coluna/pricing_silva2024) e local.

        NAO reaproveitado (desabilitado SOMENTE aqui, sem alterar
        SUB_HEUR_ALLBESTINSERTION_MULTI nem busca_local_rota): a busca local de
        SUB_HEUR_ALLBESTINSERTION_MULTI pressupoe a viabilidade generica Solomon/Petro
        (travel_time simples, uma unica demanda/capacidade por no) e nao e valida para a
        fisica Silva (navegacao piecewise, precedencia por compartimento, TDL relativo a
        B, etc.) -- nesta primeira versao a rota de cada start e aceita como esta ao fim
        da construcao por insercao, sem refinamento local adicional.

        Retorna (candidatas, busca_completa, timeout):
            candidatas: lista de dicts {k, seq, binx, custo, rc, origem="ALLBEST_SILVA"},
                        ordenada pelo rc mais negativo primeiro.
            busca_completa: sempre False (heuristica GRASP, nao certifica ausencia de
                        outras colunas negativas -- pricing_silva2024 continua sendo o
                        oraculo exato/fallback para certificacao).
            timeout: sempre False (ALLBEST_SILVA nao usa timeout).
        """
        import random

        if mu_arc is None:
            mu_arc = {}
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING

        nbcd = inst.nbcd
        dep0 = 0
        depf = inst.nbn - 1

        # =========================================================
        # ARCOS FIXOS / PROIBIDOS DO NO BP (identico a SUB_HEUR_ALLBESTINSERTION_MULTI)
        # =========================================================
        proibidos_k = {(i, j) for (i, j, kk) in NO_BP.arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in NO_BP.arcos_fixados_em_1 if kk == k}

        succ_fixo = {}
        pred_fixo = {}

        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                # conflito de arcos fixados (2 sucessores/predecessores fixos para o
                # mesmo no) -- CORRIGIDO nesta etapa: contrato de retorno e sempre
                # (candidatas, busca_completa, timeout), NUNCA (None, None) -- o
                # chamador em gerar_novas_colunas_com_duais11 desempacota 3 valores.
                return [], False, False
            if j in pred_fixo and pred_fixo[j] != i:
                return [], False, False
            succ_fixo[i] = j
            pred_fixo[j] = i

        def arco_permitido(i, j):
            if (i, j) in proibidos_k:
                return False
            if i in succ_fixo and succ_fixo[i] != j:
                return False
            if j in pred_fixo and pred_fixo[j] != i:
                return False

            obrigatorio = (i, j) in fixados_k
            if not obrigatorio:
                tabu_tenure = getattr(NO_BP, "tabu_tenure", 0)
                tabu_until = getattr(NO_BP, "tabu_until", None)
                if tabu_tenure and tabu_tenure > 0 and tabu_until is not None:
                    if tabu_until[k][i][j] > 0:
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

        # =========================================================
        # DUAIS: MESMO PAPEL do B&P atual, MESMA formula de _calcular_rc_coluna /
        # pricing_silva2024 (pi 0-based por order, sigma_k uma unica vez, mu por arco
        # com fallback (i,j,k)->(i,j)). Nao cria dual nova, nao altera o mestre.
        # =========================================================
        def rc_silva(seq, custo_real):
            rc = float(custo_real)
            for cliente in seq:
                if 1 <= cliente <= nbcd:
                    rc -= float(pi[cliente - 1])
            rc -= float(sigma_k)
            for t in range(len(seq) - 1):
                rc -= mu(seq[t], seq[t + 1])
            return rc

        # =========================================================
        # FONTE UNICA da fisica/FO Silva: avaliar_rota_silva2024. Retorna None se
        # inviavel (rejeita a candidata); senao (resultado, custo_real, rc).
        # =========================================================
        def avaliar_candidata_silva(seq):
            resultado = self.avaliar_rota_silva2024(inst, k, seq)
            if not resultado["viavel"]:
                return None
            custo_real = float(resultado["custo"])
            return resultado, custo_real, rc_silva(seq, custo_real)

        def constroi_rota_base_silva():
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

            av = avaliar_candidata_silva(rota)
            if av is None:
                return None
            _resultado, custo_real, rc = av
            return rota, set(rota), custo_real, rc

        def melhores_insercoes_silva(rota_atual, visitados, rc_atual):
            """Gera todas as insercoes viaveis (avaliadas com avaliar_rota_silva2024,
            nao com a formula generica antiga) em todas as posicoes, ordenadas pelo
            delta de custo reduzido Silva -- exige RC_SILVA(candidata) para CADA
            candidata testada, nunca custo generico recalculado so no final."""
            insercoes = []

            for cliente in range(1, nbcd + 1):
                if cliente in visitados:
                    continue
                if cliente in pred_fixo and pred_fixo[cliente] not in rota_atual:
                    continue

                for pos in range(1, len(rota_atual)):
                    i = rota_atual[pos - 1]
                    j = rota_atual[pos]

                    if (i, j) in fixados_k:
                        continue
                    if not arco_permitido(i, cliente):
                        continue
                    if not arco_permitido(cliente, j):
                        continue

                    nova_rota = rota_atual[:pos] + [cliente] + rota_atual[pos:]

                    av = avaliar_candidata_silva(nova_rota)
                    if av is None:
                        continue
                    resultado_novo, custo_real_novo, rc_nova = av

                    delta_rc = rc_nova - rc_atual
                    score = delta_rc + 0.01 * float(resultado_novo.get("F", 0.0))

                    insercoes.append((
                        cliente,  # 0
                        pos,  # 1
                        nova_rota,  # 2
                        delta_rc,  # 3
                        rc_nova,  # 4
                        custo_real_novo,  # 5
                        score,  # 6
                    ))

            insercoes.sort(key=lambda x: (x[3], x[6], x[4]))
            return insercoes

        candidatas = []
        vistas_no_lote = set()

        base = constroi_rota_base_silva()

        if base is None:
            if len(fixados_k) > 0:
                return [], False, False

            rota0 = [dep0, depf]
            av0 = avaliar_candidata_silva(rota0)
            if av0 is None:
                return [], False, False
            _resultado0, custo0, rc0 = av0
            base = (rota0, {dep0, depf}, custo0, rc0)

        for _ii in range(n_starts):
            if len(candidatas) >= max_candidatas:
                break

            rota = base[0][:]
            visitados = set(base[1])
            custo_red_total = base[3]
            custo_real_total = base[2]

            while True:
                insercoes = melhores_insercoes_silva(rota, visitados, custo_red_total)

                if not insercoes:
                    break

                melhor_delta = insercoes[0][3]
                pior_delta = insercoes[-1][3]

                alpha_rcl = random.uniform(0.15, 0.40)
                limite = melhor_delta + alpha_rcl * (pior_delta - melhor_delta)

                rcl = [ins for ins in insercoes if ins[3] <= limite]
                if not rcl:
                    rcl = insercoes[:1]

                cliente, pos, rota_nova, delta_rc, rc_nova, custo_real_novo, score = random.choice(rcl)

                if delta_rc > 1e-6 and custo_red_total > 1e-6:
                    break

                rota = rota_nova
                visitados.add(cliente)
                custo_red_total = rc_nova
                custo_real_total = custo_real_novo

                if len(visitados) >= nbcd + 2:
                    break

            if len(rota) >= 3:
                if len(fixados_k) > 0 and not contem_todos_fixados(rota):
                    continue

                rc_start = custo_red_total
                custo_start = custo_real_total

                if rc_start < -eps:
                    chave = tuple(rota)
                    if chave in vistas_no_lote:
                        continue
                    if sol_pool is None or not sol_pool.coluna_ja_existe(rota, k=k, globalmente=False):
                        vistas_no_lote.add(chave)
                        candidatas.append({
                            "k": k,
                            "seq": list(rota),
                            "binx": rota_para_binaria(rota),
                            "custo": float(custo_start),
                            "rc": float(rc_start),
                            "origem": "ALLBEST_SILVA",
                        })
                        if len(candidatas) >= max_candidatas:
                            break

        candidatas.sort(key=lambda c: c["rc"])
        return candidatas, False, False

    def SUB_PROG_BID_SILVA(self, inst, pi, sigma_k, k, NO_BP, arcos_proibidos=None,
                            arcos_fixados=None, mu_arc=None, max_labels_por_no=60,
                            max_depth=None, max_candidatas=None, eps=1e-6):
        """
        Busca intermediaria (secao "PARTE B" do pedido), EXCLUSIVA de
        objective_mode=="silva2024": mais forte que SUB_HEUR_ALLBESTINSERTION_
        MULTI_SILVA (nao e so um GRASP multi-start, expande por ORDER com
        dominancia/beam por nivel) e mais barata que pricing_silva2024 (nao
        enumera TODOS os subconjuntos x permutacoes de cada plataforma).
        Primeira versao Python -- reaproveita a arquitetura conceitual de
        SUB_PROG_DIN_BIDIRECIONAL (expansao progressiva de labels/rotas,
        dominancia por nivel/beam, recursos acumulados, poda), adaptada aos
        recursos Silva (orders, plataforma aberta/fechada, precedencia
        coleta-antes-de-entrega de DECK, deck/diesel/agua, branching) -- NAO
        bidirecional ainda (a fisica Silva nao da para compor duas metades
        sem reavaliar a rota inteira -- ver abaixo) e SEM usar
        matriz_distancia/velocidade como FO propria.

        FONTE UNICA de viabilidade/custo: exatamente como ALLBEST_SILVA/
        pricing_silva2024, cada rota FECHADA (terminando no deposito final)
        e avaliada por self.avaliar_rota_silva2024(inst, k, seq) -- a MESMA
        fisica/oraculo (VL/VH, SP/SET, janelas, dueTime, deck pre-carregado
        na base, backload, capacidades, TDL, precedencia por compartimento).
        Nenhuma formula fisica e reimplementada aqui; so o custo reduzido
        (mesma convencao de sinais de pricing_silva2024/_calcular_rc_coluna)
        e local. resultado["custo"] e sempre o custo real armazenado na
        candidata.

        Por que so forward (nao bidirecional de fato): avaliar_rota_silva2024
        exige seq[0]==dep0 e seq[-1]==depf (nao avalia trechos abertos) --
        nao ha como obter viabilidade/custo de uma METADE backward isolada
        sem fechar no deposito. Em vez disso, este BID expande labels
        FORWARD por ORDER (nao por bloco de plataforma inteiro, como pede a
        secao "VISITAS PARCIAIS" -- uma plataforma pode ficar so
        parcialmente atendida) e, a CADA expansao, fecha a rota parcial no
        deposito final e chama avaliar_rota_silva2024 -- exatamente o mesmo
        padrao de avaliar_e_registrar em pricing_silva2024 e de
        avaliar_candidata_silva em ALLBEST_SILVA, so que aqui guiando uma
        busca por label em vez de DFS exaustivo ou insercao GRASP.

        FECHAR agora != CONTINUAR existindo (correcao critica desta versao):
        a cada expansao, o prefixo (seq_aberta) e SEMPRE mantido vivo e
        anexado ao proximo nivel, independente de conseguir virar uma
        candidata fechando exatamente ali. "Fechar agora" (seq_aberta +
        [depf]) e so uma TENTATIVA -- feita a cada expansao -- de (a)
        registrar uma candidata valida e (b) obter um RC real para ranking
        do label; ela NUNCA decide se o prefixo pode continuar sendo
        expandido. Isso e feito em duas fases explicitas, deliberadamente
        separadas:
          1. avalia_fechamento_fisico(seq_aberta): SO a fisica
             (avaliar_rota_silva2024), sem conhecer branching. Retorna None
             so quando a rota fechada agora e FISICAMENTE inviavel (janela/
             capacidade/TDL/etc.).
          2. registra(...): so aqui, alem de contem_todos_fixados, e checado
             arco_permitido(ultimo_no, depf) -- se o fechamento aqui viola
             branching (por exemplo o ultimo no tem um succ_fixo apontando
             para OUTRO no, ou o proprio arco no->depf esta proibido), a
             candidata simplesmente nao e registrada, mas o label (que ja
             foi anexado ao proximo nivel de qualquer forma) continua
             disponivel para ser expandido -- e e exatamente essa expansao
             que permite cumprir o arco fixado (no->succ_fixo[no]) ou
             alcancar depf por outro caminho quando no->depf e proibido.
        Quando avalia_fechamento_fisico falha (fisica OU indisponivel
        naquele ponto), o label herda como `rc_fechamento` o valor do PAI --
        um proxy de ranking seguro (nao inventa FO nova, nunca usa
        matriz_distancia/velocidade), usado so para ordenar o beam, nunca
        para decidir viabilidade/existencia do label.

        BUG CORRIGIDO (nao presente na primeira versao aceita por engano
        durante auto-revisao): uma versao anterior condicionava a propria
        EXPANSAO a `arco_permitido(ultimo_no, depf)`, descartando (via
        `continue`) qualquer label cujo fechamento imediato fosse proibido
        pelo branching -- isso podia eliminar POR COMPLETO o unico caminho
        que cumpre um arco fixado (succ_fixo forcando i->j: o label que
        chega em i tem arco_permitido(i, depf)==False por definicao, e
        acabava descartado ANTES de poder expandir i->j) ou impedir
        contornar um arco proibido para o deposito (i->depf proibido, mas
        i->j->...->depf continuaria valido). A separacao acima resolve isso.

        Dominancia/beam: ao final de cada nivel, os labels sao ordenados
        pelo RC de fechamento (real quando disponivel, ou o proxy herdado
        do pai) e so os `max_labels_por_no` melhores sobrevivem -- um proxy
        razoavel de dominancia (nao um criterio formal de Pareto sobre
        tempo/carga, que exigiria reimplementar a fisica Silva fora de
        avaliar_rota_silva2024) -- EXCETO labels cujo ultimo no tem uma
        continuacao obrigatoria pendente (esta em succ_fixo, ou seja, ainda
        precisa cumprir um arco fixado): esses NUNCA sao removidos so por
        ranking desfavoravel, para o beam nunca descartar justamente o
        prefixo que o branching exige manter vivo.

        Regras herdadas SEM reimplementacao nova (mesma logica de
        pricing_silva2024/ALLBEST_SILVA):
          - precedencia por plataforma: dentro do bloco aberto, nenhuma
            coleta de DECK apos qualquer entrega de DECK ja ter comecado;
          - uma plataforma, uma vez fechada (trocou-se para outra), nunca
            reabre;
          - capacidades deck/diesel/agua conferidas de forma exata (mesma
            regra/tolerancia de pricing_silva2024) como poda estrutural
            (nunca descarta nada que avaliar_rota_silva2024 aceitaria);
          - branching: arcos_proibidos corta durante a expansao
            (arco_permitido); arcos_fixados_em_1 e exigido no FECHAMENTO de
            cada candidata (contem_todos_fixados + arco_permitido no arco
            de fechamento, ambos dentro de registra), reaplicado de novo
            pelo chamador via coluna_respeita_no antes de aceitar a coluna
            (mesmo padrao de pricing_silva2024).

        Retorna (candidatas, busca_completa, timeout):
            candidatas: lista de dicts {k, seq, binx, custo, rc,
                        origem="BID_SILVA"}, ordenada pelo rc mais negativo.
            busca_completa: SEMPRE False -- BID_SILVA e heuristico nesta
                        primeira versao (beam width finito, max_depth,
                        ranking por proxy quando o fechamento imediato nao
                        e possivel), NUNCA certifica ausencia de coluna
                        negativa.
            timeout: SEMPRE False (sem orcamento de tempo nesta versao; o
                        controle de custo computacional e so max_labels_por_no/
                        max_depth/max_candidatas).
        """
        dep0 = 0
        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))
        veic = inst.veiculos[k]
        mu_arc = mu_arc or {}
        arcos_proibidos = arcos_proibidos or set()
        arcos_fixados = arcos_fixados or set()

        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        if max_depth is None:
            max_depth = inst.nbcd

        proibidos_k = {(i, j) for (i, j, kk) in arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in arcos_fixados if kk == k}

        succ_fixo = {}
        pred_fixo = {}
        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return [], False, False
            if j in pred_fixo and pred_fixo[j] != i:
                return [], False, False
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

        def contem_todos_fixados(seq_nos):
            if not fixados_k:
                return True
            aset = {(seq_nos[t], seq_nos[t + 1]) for t in range(len(seq_nos) - 1)}
            return all(arc in aset for arc in fixados_k)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        # ---- agrupamento por plataforma (MESMA regra de avaliar_rota_silva2024/
        # pricing_silva2024) ----
        dp = inst.dados_petro
        nomes = list(dp.get("nomes", []))
        mapa_plataformas = {}
        plataforma_id = {}
        for i in clientes:
            nome = str(nomes[i]) if i < len(nomes) else ""
            if "_order_" in nome:
                chave = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                chave = nome.split("_order", 1)[0]
            else:
                chave = nome
            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)
            plataforma_id[i] = mapa_plataformas[chave]

        deck_load = {i: float(getattr(inst.noh[i], "DEMAND_DECK_LOAD", 0.0)) for i in clientes}
        deck_backload = {i: float(getattr(inst.noh[i], "DEMAND_DECK_BACKLOAD", 0.0)) for i in clientes}
        diesel = {i: float(getattr(inst.noh[i], "DEMAND_DIESEL", 0.0)) for i in clientes}
        agua = {i: float(getattr(inst.noh[i], "DEMAND_AGUA", 0.0)) for i in clientes}

        Q = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel_k = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua_k = float(getattr(veic, "cap_agua", float("inf")))

        def rc_de(custo_real, seq_fechada):
            rc = float(custo_real)
            for c in seq_fechada:
                if 1 <= c <= inst.nbcd:
                    rc -= float(pi[c - 1])
            rc -= float(sigma_k)
            for t in range(len(seq_fechada) - 1):
                rc -= mu(seq_fechada[t], seq_fechada[t + 1])
            return rc

        def avalia_fechamento_fisico(seq_aberta):
            # SO a fisica (avaliar_rota_silva2024) -- de proposito NAO checa
            # arco_permitido(last, depf) aqui. Um prefixo pode ser
            # fisicamente fechavel agora mas ter esse fechamento especifico
            # proibido pelo branching (arco fixado obrigando outra
            # continuacao, ou arco last->depf proibido); isso NAO significa
            # que o prefixo em si e invalido/inexpansivel -- so que ele nao
            # pode virar candidata FECHANDO AQUI. Retorna None so quando a
            # rota fechada agora e fisicamente inviavel (janela/capacidade/
            # TDL/etc., decidido inteiramente por avaliar_rota_silva2024).
            seq_fechada = seq_aberta + [depf]
            resultado = self.avaliar_rota_silva2024(inst, k, seq_fechada)
            if not resultado["viavel"]:
                return None
            custo_real = float(resultado["custo"])
            return seq_fechada, custo_real, rc_de(custo_real, seq_fechada)

        candidatas = []
        vistas = set()

        def registra(seq_fechada, custo_real, rc):
            if rc >= -eps:
                return
            # arco de FECHAMENTO (ultimo no -> depf): nunca checado dentro de
            # avalia_fechamento_fisico (proposital -- ver docstring/comentario
            # la); e o UNICO lugar onde essa checagem de branching acontece.
            if not arco_permitido(seq_fechada[-2], depf):
                return
            if not contem_todos_fixados(seq_fechada):
                return
            chave = tuple(seq_fechada)
            if chave in vistas:
                return
            vistas.add(chave)
            binx = [0] * inst.nbcd
            for c in seq_fechada:
                if 1 <= c <= inst.nbcd:
                    binx[c - 1] = 1
            candidatas.append({"k": k, "seq": list(seq_fechada), "binx": binx,
                                "custo": custo_real, "rc": rc, "origem": "BID_SILVA"})

        label0 = {
            "seq": [dep0], "visitados": frozenset(), "plataforma_aberta": None,
            "fechadas": frozenset(), "entrega_iniciada": False,
            "deck": 0.0, "diesel": 0.0, "agua": 0.0, "rc_fechamento": float("inf"),
        }

        fecha0 = avalia_fechamento_fisico(label0["seq"])
        if fecha0 is not None:
            registra(*fecha0)
            label0["rc_fechamento"] = fecha0[2]

        nivel_atual = [label0]
        nivel = 0

        while nivel < max_depth and nivel_atual and len(candidatas) < max_candidatas:
            proximo_nivel = []

            for lab in nivel_atual:
                if len(candidatas) >= max_candidatas:
                    break
                last = lab["seq"][-1]

                for j in clientes:
                    if j in lab["visitados"]:
                        continue
                    pj = plataforma_id[j]
                    if pj in lab["fechadas"]:
                        continue
                    if not arco_permitido(last, j):
                        continue

                    nova_entrega_iniciada = lab["entrega_iniciada"]
                    nova_plataforma_aberta = lab["plataforma_aberta"]
                    nova_fechadas = lab["fechadas"]
                    if pj != lab["plataforma_aberta"]:
                        if lab["plataforma_aberta"] is not None:
                            nova_fechadas = lab["fechadas"] | {lab["plataforma_aberta"]}
                        nova_plataforma_aberta = pj
                        nova_entrega_iniciada = False

                    tem_coleta = deck_backload[j] > 1e-9
                    tem_entrega = deck_load[j] > 1e-9
                    if tem_coleta and nova_entrega_iniciada:
                        continue
                    if tem_entrega:
                        nova_entrega_iniciada = True

                    novo_deck = lab["deck"] + deck_load[j]
                    if novo_deck > Q + 1e-6:
                        continue
                    novo_diesel = lab["diesel"] + diesel[j]
                    if math.isfinite(cap_diesel_k) and novo_diesel > cap_diesel_k + 1e-6:
                        continue
                    novo_agua = lab["agua"] + agua[j]
                    if math.isfinite(cap_agua_k) and novo_agua > cap_agua_k + 1e-6:
                        continue

                    novo_seq = lab["seq"] + [j]
                    # Fechar AGORA (novo_seq + [depf]) e so uma TENTATIVA de
                    # registrar candidata / refinar o ranking -- NUNCA um
                    # criterio para descartar o label. Um prefixo pode ser
                    # fisicamente infechavel agora (ainda precisa de mais
                    # nos) ou ter esse fechamento especifico proibido pelo
                    # branching (succ_fixo forcando outra continuacao, ou
                    # arco last->depf proibido) e AINDA ASSIM continuar
                    # sendo um prefixo perfeitamente valido/expansivel (ver
                    # docstring). Por isso o label e SEMPRE anexado a
                    # proximo_nivel, independente do resultado de
                    # avalia_fechamento_fisico.
                    fech = avalia_fechamento_fisico(novo_seq)
                    if fech is not None:
                        seq_fechada, custo_real, rc = fech
                        registra(seq_fechada, custo_real, rc)
                        rc_fechamento_label = rc
                    else:
                        # Nao fechavel agora (fisica OU branching) -- nao
                        # inventa FO nova (nunca matriz_distancia/
                        # velocidade): so herda o proxy de ranking do PAI,
                        # um score seguro que so serve para ordenar o beam,
                        # nunca para decidir viabilidade.
                        rc_fechamento_label = lab["rc_fechamento"]

                    proximo_nivel.append({
                        "seq": novo_seq, "visitados": lab["visitados"] | {j},
                        "plataforma_aberta": nova_plataforma_aberta, "fechadas": nova_fechadas,
                        "entrega_iniciada": nova_entrega_iniciada,
                        "deck": novo_deck, "diesel": novo_diesel, "agua": novo_agua,
                        "rc_fechamento": rc_fechamento_label,
                    })

                    if len(candidatas) >= max_candidatas:
                        break

            # dominancia/beam (ver docstring): so os melhores max_labels_por_no
            # labels (menor RC de fechamento/proxy) sobrevivem para o proximo
            # nivel -- EXCETO labels com uma continuacao obrigatoria pendente
            # (ultimo no em succ_fixo, ou seja, com um arco fixado ainda por
            # cumprir): esses NUNCA sao removidos so por ranking desfavoravel,
            # senao o beam poderia descartar justamente o prefixo que o
            # branching exige manter vivo. Os slots restantes de
            # max_labels_por_no sao preenchidos pelos melhores-ranqueados
            # entre os demais.
            protegidos = [lb for lb in proximo_nivel if lb["seq"][-1] in succ_fixo]
            demais = [lb for lb in proximo_nivel if lb["seq"][-1] not in succ_fixo]
            demais.sort(key=lambda lb: lb["rc_fechamento"])
            slots_restantes = max(0, max_labels_por_no - len(protegidos))
            proximo_nivel = protegidos + demais[:slots_restantes]

            nivel_atual = proximo_nivel
            nivel += 1

        candidatas.sort(key=lambda c: c["rc"])
        return candidatas[:max_candidatas], False, False

    def SUB_PROG_PD_SILVA(self, inst, pi, sigma_k, k, NO_BP, arcos_proibidos=None,
                           arcos_fixados=None, mu_arc=None, max_labels=500_000,
                           timeout_s=90.0, max_candidatas=None, eps=1e-6, diagnostico=False):
        """
        Pricing EXATO Silva por label-setting/DP, EXCLUSIVO de
        objective_mode=="silva2024". Primeira versao Python, com o objetivo
        explicito de servir de base para portar a MESMA logica para C++
        depois (nao ainda). NAO substitui pricing_silva2024 (enumeracao por
        combinacoes/permutacoes) em lugar nenhum -- ele continua disponivel,
        intacto, como diagnostico/fallback de comparacao (ver
        _teste_3niveis_silva.py). NAO integrado ao pipeline de producao
        (gerar_novas_colunas_com_duais11) nesta tarefa -- validacao isolada.

        ESTADO DO LABEL (minimo suficiente, ver prova abaixo):
            seq: sequencia de nos visitados ate agora (dep0 + orders), ABERTA
                 (sem depf ainda).
            mask: bitmask (1<<(order-1)) das orders ja visitadas.
            plataforma_aberta: id da plataforma do ULTIMO no (None em dep0).
            fechadas: frozenset de plataformas que ja foram abandonadas
                 (nunca mais alcancaveis -- regra de nao-revisita, secao 5).
            entrega_iniciada: True se alguma entrega de DECK ja ocorreu
                 dentro do bloco da plataforma_aberta (trava futura coleta
                 nesse MESMO bloco).
            deck/diesel/agua: soma acumulada das demandas das orders no mask
                 (poda de capacidade estrutural, EXATA -- ver secao abaixo).

        NAO faz parte do estado (PROVADO redundante dado (ultimo_no, mask)):
            plataforma_aberta = plataforma_id[ultimo_no] (funcao direta de
                ultimo_no, exceto ultimo_no==dep0);
            fechadas = {plataforma_id[i] for i in mask} \\ {plataforma_aberta}
                (toda plataforma que aparece no mask e nao e a aberta JA foi
                necessariamente fechada, porque arco_permitido nunca deixa
                uma plataforma ser revisitada -- ver secao 5/8 abaixo -- logo
                so pode estar no mask por ter sido visitada e abandonada
                antes);
            entrega_iniciada = existe alguma order de deck_load>0 da
                plataforma_aberta dentro do mask (independe de QUANDO foi
                visitada dentro do bloco, so de TER sido);
            deck/diesel/agua = somas diretas sobre o mask.
        Mantidos explicitamente no label mesmo assim (nao como bitmask
        derivado a cada passo) so por performance/legibilidade -- SAO,
        matematicamente, funcoes puras de (ultimo_no, mask), o que e
        exatamente o argumento usado abaixo para justificar a ausencia de
        dominancia por recursos (ver "DOMINANCIA").

        POR QUE NAO HA (ainda) DOMINANCIA POR TEMPO/CUSTO -- decisao
        deliberada, nao uma lacuna esquecida (secao 10 do pedido: "criar
        dominancia SOMENTE quando for matematicamente segura"):
        Na fisica Silva (avaliar_rota_silva2024), o instante de partida da
        base P = AT + hB_saida, onde hB_saida = soma dos tempos de
        carregamento de TODAS as orders da rota FINAL (todo o deck/diesel/
        agua e pre-carregado na base antes de zarpar) -- NAO so das orders
        visitadas ate agora no prefixo. Duas extensoes (prefixo + sufixos
        diferentes) do MESMO prefixo podem terminar em masks finais
        diferentes, logo com P finais diferentes, logo com toda a
        cronologia (chegadas, esperas, janela escolhida) diferente. Isso
        quebra a premissa classica de dominancia VRPTW (tempo de chegada
        comparavel entre dois labels no MESMO (no,mask) prefixo): nao existe
        um "tempo relativo" consistente e barato de calcular durante a
        expansao que preserve a comparacao correta sem assumir um P (ainda
        desconhecido). O mesmo vale para o pico de carga de deck (deck_atual
        comeca em deck_total da rota FINAL, nao do prefixo) e para o
        proprio sinal dos coeficientes de custo (gamma_k-delta_k,
        delta_k-theta_k podem ser positivos OU negativos dependendo da
        instancia -- ver f1 em avaliar_rota_silva2024), entao nem
        "hN acumulado menor e sempre melhor" e universalmente verdade sem
        checar o sinal desses coeficientes por veiculo. Uma dominancia
        condicional (2D Pareto em tempo relativo + hN acumulado, valida SE
        E SOMENTE SE gamma_k>=delta_k>=theta_k e xi_usado>=0 puderem ser
        confirmados em tempo de execucao) tem uma prova algebrica que
        aponta para ser segura, mas exigiria tambem replicar com exatidao a
        selecao de janela (ready/due) com um relogio auxiliar cuja
        equivalencia ao relogio real (deslocado por P, desconhecido durante
        a expansao) nao foi possivel provar sem risco dentro do escopo desta
        tarefa -- decisao: NAO implementar, documentar como trabalho futuro,
        em vez de arriscar uma dominancia incorreta. A UNICA "dominancia"
        aqui e a poda ESTRUTURAL (sempre segura, ver abaixo), que nunca
        elimina uma rota que avaliar_rota_silva2024 aceitaria.

        PODA ESTRUTURAL (segura, mesma logica de pricing_silva2024/
        SUB_PROG_BID_SILVA -- nao reimplementada, so reaplicada):
          - capacidade: soma de deck_load/diesel/agua sobre o mask (LIMITE
            INFERIOR do total final, ja que so cresce) <= capacidade do
            navio -- nunca descarta uma rota que a fisica aceitaria;
          - precedencia: dentro do bloco da plataforma_aberta, nenhuma
            coleta apos qualquer entrega ja ter comecado (diesel/agua
            ficam de fora desta regra, como sempre);
          - nao-revisita (secao 5): uma plataforma em `fechadas` nunca pode
            ser reaberta -- QUALQUER subconjunto das orders de uma
            plataforma continua permitido, so nao em dois blocos separados;
          - branching (secao 8): arcos_proibidos corta durante a expansao
            (arco_permitido); succ_fixo/pred_fixo (arcos_fixados_em_1)
            restringem arco_permitido tambem durante a expansao -- se
            succ_fixo[i]=j, arco_permitido(i,m) e False para todo m!=j (a
            unica continuacao permitida ao sair de i e j); arcos ainda nao
            cumpridos sao GARANTIDOS pelo proprio mecanismo de
            arco_permitido (nunca ha como o label "esquecer" de ir para j) e
            reconferidos no FECHAMENTO via contem_todos_fixados + o arco de
            fechamento (ultimo_no->depf) via arco_permitido, dentro de
            registra().

        FECHAR != CONTINUAR (secao 7 do pedido, MESMA correcao critica ja
        validada em SUB_PROG_BID_SILVA, preservada aqui sem alteracao de
        principio): a cada expansao, o prefixo e SEMPRE mantido vivo e
        anexado ao proximo nivel, independente de conseguir fechar
        (seq_aberta + [depf]) exatamente ali. Fechar agora e so uma
        TENTATIVA -- feita a cada expansao -- de registrar uma candidata;
        NUNCA decide se o label pode continuar. avalia_fechamento_fisico
        (so a fisica) e registra (fisica + branching do arco de fechamento +
        arcos fixados) sao funcoes separadas, exatamente como no BID_SILVA.
        Um label cujo fechamento imediato falha (por fisica -- janela/
        capacidade/TDL -- OU por branching -- succ_fixo apontando para
        outro no, ou arco no->depf proibido) continua vivo e expansivel.

        FONTE UNICA de viabilidade/custo: exatamente como ALLBEST_SILVA/
        BID_SILVA/pricing_silva2024, toda candidata fechada e avaliada por
        self.avaliar_rota_silva2024(inst, k, seq) antes de virar candidata;
        nenhuma formula fisica e reimplementada aqui (so o custo reduzido,
        mesma convencao de sinais de pricing_silva2024). resultado["custo"]
        e sempre o custo real armazenado.

        EXAUSTAO/CERTIFICACAO (secao 12/16 do pedido): SEM beam search, SEM
        limite silencioso de labels por nivel -- TODOS os labels
        estruturalmente validos de cada nivel sao expandidos. So dois
        orcamentos finitos podem interromper a busca ANTES de esgotar as
        <=14 orders: max_labels (total de labels criados) e timeout_s.
        Atingir MAX_CANDIDATAS_PRICING (limite do que e RETORNADO) nao
        interrompe a busca nem afeta completa -- so limita o tamanho da
        lista devolvida (a busca continua ate esgotar a arvore ou o
        orcamento, exatamente como pedido na secao 12). completa=True SE E
        SOMENTE SE a arvore foi esgotada (nenhum limite de labels/timeout
        atingido); caso contrario completa=False e o chamador NUNCA deve
        certificar convergencia/LB com este resultado.

        Retorna (candidatas, completa, timeout):
            candidatas: lista de dicts {k, seq, binx, custo, rc,
                        origem="PD_SILVA"}, ordenada pelo rc mais negativo,
                        limitada a max_candidatas.
            completa: True somente se a arvore de estados foi TOTALMENTE
                        esgotada (nenhum orcamento atingido).
            timeout: True se o motivo especifico da interrupcao foi
                        timeout_s (max_labels tambem pode ter sido atingido
                        primeiro -- completa=False em ambos os casos).
        """
        import time as _time

        t0 = _time.time()
        dep0 = 0
        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))
        veic = inst.veiculos[k]
        mu_arc = mu_arc or {}
        arcos_proibidos = arcos_proibidos or set()
        arcos_fixados = arcos_fixados or set()
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING

        proibidos_k = {(i, j) for (i, j, kk) in arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in arcos_fixados if kk == k}

        succ_fixo = {}
        pred_fixo = {}
        for (i, j) in fixados_k:
            if i in succ_fixo and succ_fixo[i] != j:
                return [], False, False
            if j in pred_fixo and pred_fixo[j] != i:
                return [], False, False
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

        def contem_todos_fixados(seq_nos):
            if not fixados_k:
                return True
            aset = {(seq_nos[t], seq_nos[t + 1]) for t in range(len(seq_nos) - 1)}
            return all(arc in aset for arc in fixados_k)

        def mu(i, j):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        # ---- agrupamento por plataforma (MESMA regra de avaliar_rota_silva2024/
        # pricing_silva2024/SUB_PROG_BID_SILVA) ----
        dp = inst.dados_petro
        nomes = list(dp.get("nomes", []))
        mapa_plataformas = {}
        plataforma_id = {}
        for i in clientes:
            nome = str(nomes[i]) if i < len(nomes) else ""
            if "_order_" in nome:
                chave = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                chave = nome.split("_order", 1)[0]
            else:
                chave = nome
            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)
            plataforma_id[i] = mapa_plataformas[chave]

        deck_load = {i: float(getattr(inst.noh[i], "DEMAND_DECK_LOAD", 0.0)) for i in clientes}
        deck_backload = {i: float(getattr(inst.noh[i], "DEMAND_DECK_BACKLOAD", 0.0)) for i in clientes}
        diesel = {i: float(getattr(inst.noh[i], "DEMAND_DIESEL", 0.0)) for i in clientes}
        agua = {i: float(getattr(inst.noh[i], "DEMAND_AGUA", 0.0)) for i in clientes}

        Q = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel_k = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua_k = float(getattr(veic, "cap_agua", float("inf")))

        def rc_de(custo_real, seq_fechada):
            rc = float(custo_real)
            for c in seq_fechada:
                if 1 <= c <= inst.nbcd:
                    rc -= float(pi[c - 1])
            rc -= float(sigma_k)
            for t in range(len(seq_fechada) - 1):
                rc -= mu(seq_fechada[t], seq_fechada[t + 1])
            return rc

        def avalia_fechamento_fisico(seq_aberta):
            # SO a fisica (avaliar_rota_silva2024) -- ver docstring "FECHAR
            # != CONTINUAR": nao checa arco_permitido(last, depf) aqui de
            # proposito, para nunca confundir "nao pode fechar aqui" com
            # "prefixo invalido".
            seq_fechada = seq_aberta + [depf]
            resultado = self.avaliar_rota_silva2024(inst, k, seq_fechada)
            if not resultado["viavel"]:
                return None
            custo_real = float(resultado["custo"])
            return seq_fechada, custo_real, rc_de(custo_real, seq_fechada)

        candidatas = []
        vistas = set()

        def registra(seq_fechada, custo_real, rc):
            if rc >= -eps:
                return
            if not arco_permitido(seq_fechada[-2], depf):
                return
            if not contem_todos_fixados(seq_fechada):
                return
            chave = tuple(seq_fechada)
            if chave in vistas:
                return
            vistas.add(chave)
            # secao 12 (CORRIGIDO): NAO limitar aqui -- um cap aqui manteria
            # so as PRIMEIRAS max_candidatas descobertas na ordem de busca
            # (nao necessariamente as MELHORES), quebrando silenciosamente a
            # garantia de que o corte final e por RC. A busca continua livre
            # (nao interrompida por isto -- completa e decidido so pelo
            # orcamento de labels/timeout); o corte para as `max_candidatas`
            # MELHORES acontece uma unica vez, no final, apos ordenar por rc.
            binx = [0] * inst.nbcd
            for c in seq_fechada:
                if 1 <= c <= inst.nbcd:
                    binx[c - 1] = 1
            candidatas.append({"k": k, "seq": list(seq_fechada), "binx": binx,
                                "custo": custo_real, "rc": rc, "origem": "PD_SILVA"})

        def bit(c):
            return 1 << (c - 1)

        label0 = {
            "seq": [dep0], "mask": 0, "plataforma_aberta": None,
            "fechadas": frozenset(), "entrega_iniciada": False,
            "deck": 0.0, "diesel": 0.0, "agua": 0.0,
        }

        total_labels = [1]
        limite_atingido = [False]
        timeout_atingido = [False]

        def orcamento_esgotado():
            if total_labels[0] >= max_labels:
                return True
            if (_time.time() - t0) > timeout_s:
                timeout_atingido[0] = True
                return True
            return False

        fecha0 = avalia_fechamento_fisico(label0["seq"])
        if fecha0 is not None:
            registra(*fecha0)

        nivel_atual = [label0]
        nivel = 0

        while nivel < inst.nbcd and nivel_atual and not limite_atingido[0]:
            proximo_nivel = []

            for lab in nivel_atual:
                if orcamento_esgotado():
                    limite_atingido[0] = True
                    break
                last = lab["seq"][-1]

                for j in clientes:
                    if lab["mask"] & bit(j):
                        continue
                    pj = plataforma_id[j]
                    if pj in lab["fechadas"]:
                        continue
                    if not arco_permitido(last, j):
                        continue

                    nova_entrega_iniciada = lab["entrega_iniciada"]
                    nova_plataforma_aberta = lab["plataforma_aberta"]
                    nova_fechadas = lab["fechadas"]
                    if pj != lab["plataforma_aberta"]:
                        if lab["plataforma_aberta"] is not None:
                            nova_fechadas = lab["fechadas"] | {lab["plataforma_aberta"]}
                        nova_plataforma_aberta = pj
                        nova_entrega_iniciada = False

                    tem_coleta = deck_backload[j] > 1e-9
                    tem_entrega = deck_load[j] > 1e-9
                    if tem_coleta and nova_entrega_iniciada:
                        continue
                    if tem_entrega:
                        nova_entrega_iniciada = True

                    novo_deck = lab["deck"] + deck_load[j]
                    if novo_deck > Q + 1e-6:
                        continue
                    novo_diesel = lab["diesel"] + diesel[j]
                    if math.isfinite(cap_diesel_k) and novo_diesel > cap_diesel_k + 1e-6:
                        continue
                    novo_agua = lab["agua"] + agua[j]
                    if math.isfinite(cap_agua_k) and novo_agua > cap_agua_k + 1e-6:
                        continue

                    if orcamento_esgotado():
                        limite_atingido[0] = True
                        break

                    novo_seq = lab["seq"] + [j]
                    total_labels[0] += 1

                    # FECHAR != CONTINUAR (ver docstring): tentativa de
                    # registrar candidata, NUNCA um criterio para descartar
                    # o label -- o label e SEMPRE anexado ao proximo nivel
                    # logo abaixo, independente do resultado.
                    fech = avalia_fechamento_fisico(novo_seq)
                    if fech is not None:
                        seq_fechada, custo_real, rc = fech
                        registra(seq_fechada, custo_real, rc)

                    proximo_nivel.append({
                        "seq": novo_seq, "mask": lab["mask"] | bit(j),
                        "plataforma_aberta": nova_plataforma_aberta, "fechadas": nova_fechadas,
                        "entrega_iniciada": nova_entrega_iniciada,
                        "deck": novo_deck, "diesel": novo_diesel, "agua": novo_agua,
                    })

                if limite_atingido[0]:
                    break

            nivel_atual = proximo_nivel
            nivel += 1

        candidatas.sort(key=lambda c: c["rc"])
        completa = not limite_atingido[0]
        timeout_final = bool(timeout_atingido[0] and limite_atingido[0])
        if diagnostico:
            motivo = ("timeout" if timeout_final else "max_labels") if limite_atingido[0] else "arvore_esgotada"
            print(f"[PD_SILVA] k={k} niveis_alcancados={nivel} total_labels={total_labels[0]} "
                  f"candidatas_negativas={len(candidatas)} completa={completa} motivo_parada={motivo} "
                  f"tempo={_time.time() - t0:.2f}s")
        return candidatas[:max_candidatas], completa, timeout_final

    def SUB_HEUR_ALLBESTINSERTION(self, inst, sol_pool, pi, sigma_k, k, NO_BP, mu_arc=None,
                                   n_starts=30, eps=1e-6):
        """Wrapper de compatibilidade: mesma interface/retorno de antes
        (rota_dict, rc) ou (None, None), reproduzindo a primeira candidata
        que SUB_HEUR_ALLBESTINSERTION_MULTI encontraria com max_candidatas=1."""
        candidatas, _busca_completa, _timeout = self.SUB_HEUR_ALLBESTINSERTION_MULTI(
            inst, sol_pool, pi, sigma_k, k, NO_BP, mu_arc=mu_arc, n_starts=n_starts, eps=eps,
            max_candidatas=1
        )
        if not candidatas:
            return None, None

        c = candidatas[0]
        return {
            "clientes": c["seq"],
            "custo": c["custo"],
            "bin_xij": c["binx"],
        }, c["rc"]

    def SUB_HEUR_ALLBESTINSERTIONsemfixos(self, inst, pi, sigma_k, k, NO_BP, mu_arc=None,
                                          n_starts=30, eps=1e-6):
        import math
        import random

        if mu_arc is None:
            mu_arc = {}

        # print(f"Subprob ALL BEST INSERTION veículo {k}")

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
            # print(f"\nSTART {ii}")

            rota = [dep0, depf]
            visitados = {dep0, depf}

            viavel_ini, janelas_escolhidas, tempo_final, carga_final = verifica_viabilidade(rota)
            if not viavel_ini:
                # print("Rota inicial [dep0,depf] inviável")
                return None, None

            custo_red_total = custo_reduzido_rota(rota)
            custo_real_total = custo_real_rota(rota)

            # print(f"rota inicial = {rota} | rc = {custo_red_total}")

            while True:
                insercoes = melhores_insercoes(rota, visitados, custo_red_total)

                if not insercoes:
                    # print("sem inserções viáveis")
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

                # print(
                #    f"inserindo cliente {cliente} na posição {pos} | delta_rc = {delta_rc:.6f} | rc_novo = {rc_nova:.6f}")

                # regra de parada: se piorou demais e já não está promissor, para
                if delta_rc > 1e-6 and custo_red_total > 1e-6:
                    # print("inserção piora a rota e rc atual já não é promissor")
                    break

                rota = rota_nova
                visitados.add(cliente)
                janelas_escolhidas = janelas_novas
                tempo_final = tempo_novo
                carga_final = carga_nova
                custo_red_total = rc_nova
                custo_real_total = custo_real_novo

                # print(f"rota atual = {rota} | rc = {custo_red_total:.6f}")

                # se não sobrou cliente, para
                if len(visitados) >= nbcd + 2:
                    break

            # precisa ter pelo menos 1 cliente
            if len(rota) >= 3:
                # print(f"rota construída final = {rota} | rc = {custo_red_total:.6f}")

                rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                    rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                )

                # print(f"rota BL = {rota_melhorada} | rc BL = {custo_red_melhorado}")

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
        top_k = 5
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

                    # aqui vou colocar o

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
                        # print(f"janela inviavel para {j}")
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

                # escolha enviesada

                j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela, score = (
                    self.escolhe_vizinho_enviesado(viaveis, alpha=0.55))
                # j, inicio_servico_j, fim_servico_j, nova_carga, delta_rc, idx_janela = random.choice(viaveis)
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
                    # print(f"melhora uma vez custo antigo red {rota}= {custo_red_total}")
                    rota_melhorada, custo_red_melhorado, custo_real_melhorado, janelas_melhoradas = self.busca_local_rota(
                        rota, inst, pi, sigma_k, k, mu_arc, janelas, d
                    )
                    # print(f"melhora uma vez custo novo red {rota_melhorada}= {custo_red_melhorado}")
                    if rota_melhorada is not None and custo_red_melhorado < -eps:
                        # print(f"heuristica deu boa patrão rota {rota_melhorada}- custor= {custo_red_melhorado}")
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

                # print("NAO RETORNOU COLUNA-GERA NOVA")
                # print(ii)

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
                    # print("PROIBIDO viola arco proibido")
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
                # print("PROIBIDa COlujna não respeita arco obrigatorio")
                return False  # não respeita arco obrigatório

        return True

    def resolver_no_com_pool(self, inst, sol_pool, no_bp, tipo_geracao="PD"):
        import time
        import gurobipy as gp
        from gurobipy import GRB

        t0N = time.time()
        tentativasLP = 0
        rodadas_sem_melhoria = 0
        # nmaxrodadas_sem_melhoria = inst.iteraSemMelhora
        # >>> AJUSTE v5: SM bifasico - limite de estagnacao depende da fase (caixa ativa vs fora da caixa)
        SM_FORA  = inst.iteraSemMelhora
        SM_CAIXA = getattr(inst, "iteraSemMelhora_estab", inst.iteraSemMelhora)
        nmaxrodadas_sem_melhoria = SM_CAIXA if inst.usar_estabilizacao else SM_FORA
        colunas_reais_usadas = True
        ULTIMAFO = -1

        # Tempo extra depois de achar FO alvo inteira.
        # Pode definir na main: sol_pool.TEMPO_POS_TARGET = 600
        tempo_pos_target = getattr(sol_pool, "TEMPO_POS_TARGET", 600.0)
        tempo_int_target_relogio = None

        if not hasattr(sol_pool, "SemMelhora"):
            sol_pool.SemMelhora = []
        sol_pool.SemMelhora.append(0)

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

        # Garante campos novos caso algum nó antigo não tenha sido recriado
        if not hasattr(no_bp, "melhor_lp_com_slack"):
            no_bp.melhor_lp_com_slack = float("inf")
            no_bp.melhor_lp_com_slack_iter = None
        if not hasattr(no_bp, "melhor_lp_valido"):
            no_bp.melhor_lp_valido = float("inf")
            no_bp.melhor_lp_valido_iter = None
            no_bp.melhor_lp_valido_rotas = []
        if not hasattr(no_bp, "melhor_int"):
            no_bp.melhor_int = float("inf")
            no_bp.melhor_int_iter = None
            no_bp.melhor_int_rotas = []
        if not hasattr(no_bp, "achou_lp_target"):
            no_bp.achou_lp_target = False
            no_bp.achou_int_target = False
            no_bp.iter_lp_target = None
            no_bp.iter_int_target = None
            no_bp.tempo_lp_target = None
            no_bp.tempo_int_target = None

        # contadores
        sol_pool.construtivas = [0, 0, 0, 0, 0, 0, 0]

        N = inst.nbn
        K = inst.nbv

        # tabu
        no_bp.freq_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.last_arc = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]
        no_bp.tabu_until = [[[0 for _ in range(N)] for _ in range(N)] for _ in range(K)]

        model = gp.Model(f"Mestre_no_{no_bp.id_no}")
        model.setParam("OutputFlag", 0)
        model.setParam("Method", 1)
        model.setParam("Crossover", 1)

        EPS_RC = 1e-6
        BIGM_ARC = 1e6
        BIGM_VIS = 1e6

        usar_estabilizacao =inst.usar_estabilizacao
        fase_final_sem_estab = False

        stab_y_low = []
        stab_y_up = []

        # TAREFA 2/3: o centro da caixa e do no (no_bp.pi_bar), nao do sol_pool.
        # Raiz (ou 1o no processado sem centro herdado do pai) comeca com
        # no_bp.pi_bar is None -> precisa do warm start sem caixa (TAREFA 3)
        # antes da 1a iteracao estabilizada. Filhos ja recebem pi_bar copiado
        # do pai em criar_filhos_por_arco e so reativam a caixa em torno dele.
        precisa_warm_start_raiz = False

        if usar_estabilizacao:
            if not hasattr(sol_pool, "gamma_pi"):
                sol_pool.gamma_pi = 50.0
            if not hasattr(sol_pool, "alpha_estab"):
                sol_pool.alpha_estab = 0.30

            # >>> AJUSTE v5b: warm start (Ben Amor et al. 2006) - a caixa e sempre
            # reativada na largura inicial a cada no; sem isso, todo no filho
            # herdaria o gamma deixado pela fase final do pai e rodaria sem
            # estabilizacao de fato
            sol_pool.gamma_pi = float(getattr(sol_pool, "gamma_pi_inicial", sol_pool.gamma_pi))

            if no_bp.pi_bar is None:
                precisa_warm_start_raiz = True
                print(f"[ESTAB] No {no_bp.id_no}: sem centro herdado -- caixa comeca fixada em zero ate obter um centro utilizavel (nao dominado pelo BIGM).")
            else:
                print(f"[ESTAB] No {no_bp.id_no}: caixa reativada com gamma_pi = {sol_pool.gamma_pi} (centro pi_bar herdado do pai)")

        # Ajuste: fica True enquanto o no roda sem caixa buscando um centro
        # utilizavel (duais nao dominados pelo BIGM_VIS e slack artificial
        # zero). Testado a cada iteracao do loop CG, nao so uma vez.
        aguardando_centro_estab = precisa_warm_start_raiz

        def rota_usa_arco(seq, i, j):
            for t in range(len(seq) - 1):
                if seq[t] == i and seq[t + 1] == j:
                    return 1.0
            return 0.0

        def coluna_artificial(k, p):
            flags = sol_pool.rotas[k].get("artificial", [])
            return p < len(flags) and bool(flags[p])

        def add_rota_no_pool(k, seq_nova, rota_binaria, custo_original):
            sol_pool.rotas[k]["sequencia_rota"].append(seq_nova)
            sol_pool.rotas[k]["rotas_binaria"].append(rota_binaria)
            sol_pool.rotas[k]["custo"].append(float(custo_original))
            sol_pool.rotas[k]["vezes_usada_geral"].append(0)
            sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
            sol_pool.rotas[k]["lbd_iteracao"].append([])
            sol_pool.rotas[k].setdefault("artificial", []).append(False)

        # =========================
        # 1) Variáveis lambda
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
        # 2) Visita única com slack e estabilização
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

            if usar_estabilizacao:
                if precisa_warm_start_raiz:
                    # TAREFA 3 (passo 2): sem centro ainda -- caixa comeca fixada
                    # em zero; so ganha Obj/limites reais apos o warm start sem
                    # caixa, logo apos o modelo completo estar montado.
                    y_low = model.addVar(lb=0.0, ub=0.0, obj=0.0, vtype=GRB.CONTINUOUS, name=f"stab_pi_low_{i}")
                    y_up = model.addVar(lb=0.0, ub=0.0, obj=0.0, vtype=GRB.CONTINUOUS, name=f"stab_pi_up_{i}")
                else:
                    gamma_pi = float(sol_pool.gamma_pi)
                    pi_centro = float(no_bp.pi_bar[i])
                    pi_min = pi_centro - gamma_pi
                    pi_max = pi_centro + gamma_pi

                    y_low = model.addVar(lb=0.0, obj=-pi_min, vtype=GRB.CONTINUOUS, name=f"stab_pi_low_{i}")
                    y_up = model.addVar(lb=0.0, obj=pi_max, vtype=GRB.CONTINUOUS, name=f"stab_pi_up_{i}")
                stab_y_low.append(y_low)
                stab_y_up.append(y_up)

                c = model.addConstr(expr + s - y_low + y_up == 1.0, name=f"visita_{i}")
            else:
                c = model.addConstr(expr + s == 1.0, name=f"visita_{i}")

            visita_constr.append(c)

        # =========================
        # 3) Uma rota por veículo
        # =========================
        uma_rota_constr = {}
        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p in range(len(lbd[k])):
                expr += lbd[k][p]
            uma_rota_constr[k] = model.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

        model.update()

        # =========================
        # 4) Arcos do nó com slack
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

        # Ajuste: nao ha mais warm start em bloco unico aqui -- quando
        # aguardando_centro_estab=True, o mestre completo (com y_low=y_up
        # fixados em zero desde a criacao das variaveis) roda normalmente
        # dentro do loop CG abaixo, e o centro so e aceito quando os duais
        # passarem na validacao contra o BIGM (ver dentro do loop, logo apos
        # extrair_duais_do_mestre).

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
                lb=0.0,
                ub=1.0,
                obj=float(custo_original),
                vtype=GRB.CONTINUOUS,
                name=f"lambda_{k}_{idx_pool}",
                column=col
            )
            lbd[k].append(v)

        # =========================
        # Protecao central contra colunas duplicadas (secao 3): TODA insercao de
        # coluna no pool (ALLBEST, BID, PD completa, intensificacao, copia entre
        # veiculos) deve passar por aqui, imediatamente antes de add_rota_no_pool
        # e add_lambda_var_model.
        # =========================
        contador_colunas_novas_total = 0
        contador_colunas_duplicadas_total = 0
        colunas_novas_iter = 0
        colunas_duplicadas_iter = 0
        # secao 1: limites contam colunas REALMENTE adicionadas, nao candidatas
        # selecionadas -- uma mesma candidata pode ser copiada para varios
        # veiculos, entao o teto tem que ser aplicado aqui, no ponto central.
        colunas_novas_por_veiculo_iter = {k: 0 for k in sol_pool.rotas}

        def tentar_adicionar_coluna(kk, seq, binx, custo, rc, origem):
            nonlocal contador_colunas_novas_total, contador_colunas_duplicadas_total
            nonlocal colunas_novas_iter, colunas_duplicadas_iter

            if rc >= -EPS_RC:
                return False

            if sol_pool.coluna_ja_existe(seq, k=kk, globalmente=False):
                contador_colunas_duplicadas_total += 1
                colunas_duplicadas_iter += 1
                print(f"[COLUNA DUPLICADA] origem={origem} | k={kk} | rc={rc:.6f} | seq={seq}")

                # secao 13: rc negativo para uma rota que ja existe no pool e so um
                # alerta de possivel inconsistencia (mestre x pricing x sigma/duais/
                # estabilizacao/copia entre veiculos) -- nao muda a coluna do pool
                # nem a certificacao, so ajuda a investigar depois.
                custo_pool = None
                for seq_existente, custo_existente in zip(
                    sol_pool.rotas[kk]["sequencia_rota"], sol_pool.rotas[kk]["custo"]
                ):
                    if tuple(seq_existente) == tuple(seq):
                        custo_pool = custo_existente
                        break
                print(
                    f"[DUPLICADA RC] origem={origem} | k={kk} | rc_pricing={rc:.6f} | "
                    f"custo_pricing={custo:.6f} | custo_pool={custo_pool} | seq={seq}"
                )
                return False

            permitido, motivo_limite = Metodos._verifica_limite_colunas_multi(
                kk, colunas_novas_iter, colunas_novas_por_veiculo_iter,
                self.MAX_COLUNAS_NOVAS_ITER, self.MAX_COLUNAS_NOVAS_VEICULO
            )
            if not permitido:
                print(f"[LIMITE MULTI] k={kk} | motivo={motivo_limite}")
                return False

            # secao 7 (silva2024): auditoria obrigatoria de TODA coluna antes de
            # entrar no pool -- reavalia com o mesmo oraculo do pricing, confere
            # RC contra os duais atuais do mestre e reconfirma compatibilidade
            # com o branching do no. Qualquer inconsistencia para o teste.
            if getattr(inst, "objective_mode", "petrobras") == "silva2024":
                if not hasattr(sol_pool, "silva_audit"):
                    sol_pool.silva_audit = {
                        "criadas": 0, "rejeitadas_viabilidade": 0,
                        "rejeitadas_rc": 0, "rejeitadas_branching": 0,
                    }

                res_audit = self.avaliar_rota_silva2024(inst, kk, seq)
                if not res_audit["viavel"]:
                    sol_pool.silva_audit["rejeitadas_viabilidade"] += 1
                    print(f"[SILVA ERRO COLUNA] k={kk} seq={seq} origem={origem} "
                          f"motivo=inviavel_no_oraculo detalhe={res_audit.get('motivo')}")
                    raise RuntimeError(f"[SILVA ERRO COLUNA] coluna inviavel no oraculo: k={kk} seq={seq}")

                mu_arc_kk = mu_arc_por_k.get(kk, {}) if mu_arc_por_k else {}
                rc_check = Metodos._calcular_rc_coluna(seq, res_audit["custo"], pi, sigma[kk], mu_arc_kk, inst.nbcd)
                if abs(rc_check - rc) > 1e-6:
                    sol_pool.silva_audit["rejeitadas_rc"] += 1
                    print(f"[SILVA ERRO COLUNA] k={kk} seq={seq} origem={origem} motivo=rc_inconsistente "
                          f"rc_pricing={rc:.6f} rc_check={rc_check:.6f} custo_oraculo={res_audit['custo']:.6f}")
                    raise RuntimeError(f"[SILVA ERRO COLUNA] RC inconsistente: k={kk} seq={seq}")

                if not self.coluna_respeita_no(no_bp, seq, kk):
                    sol_pool.silva_audit["rejeitadas_branching"] += 1
                    print(f"[SILVA ERRO COLUNA] k={kk} seq={seq} origem={origem} motivo=viola_branching "
                          f"proibidos={no_bp.arcos_proibidos} fixados={no_bp.arcos_fixados_em_1}")
                    raise RuntimeError(f"[SILVA ERRO COLUNA] viola branching do no: k={kk} seq={seq}")

                sol_pool.silva_audit["criadas"] += 1

            idx_pool = len(sol_pool.rotas[kk]["sequencia_rota"])
            add_rota_no_pool(kk, seq, binx, custo)
            add_lambda_var_model(kk, idx_pool, seq, binx, custo)
            contador_colunas_novas_total += 1
            colunas_novas_iter += 1
            colunas_novas_por_veiculo_iter[kk] += 1
            return True

        def calcular_rc_coluna(kk, seq, custo_original):
            """Recalcula o rc de uma coluna copiada para um veiculo kk diferente
            do de origem, usando a mesma formula do pricing (secao 2)."""
            mu_arc_kk = mu_arc_por_k.get(kk, {}) if mu_arc_por_k else {}
            return Metodos._calcular_rc_coluna(seq, custo_original, pi, sigma[kk], mu_arc_kk, inst.nbcd)

        # =========================
        # LOOP CG
        # =========================
        iter_cg = 0
        pi = None
        sigma = None
        mu_arc_por_k = None
        colunas_desde_ultimo_mip = 0
        MIP_LOG_A_CADA_ITERACOES = 10
        MIP_PERIODICO_A_CADA_COLUNAS = 10
        TIME_LIMIT_MIP_LOG = 2.0
        lb_iteracao = 0
        tempo_limite_no = getattr(inst, "tempo_limite_no", float("inf"))
        _tempo_lim_consumido = False  # abre a caixa só uma vez por nó

        while True:
            sol_pool.nb_iteracoes += 1
            colunas_novas_iter = 0
            colunas_duplicadas_iter = 0
            for _k in colunas_novas_por_veiculo_iter:
                colunas_novas_por_veiculo_iter[_k] = 0

            if (time.time() - sol_pool.time_initial > sol_pool.TIME_MAX):
                sol_pool.motivoConv = "TIME_MAX"
                sol_pool.terminou_por_tempo = True  # PARTE 2: instrumentacao
                break

            if (
                    tempo_int_target_relogio is not None
                    and (time.time() - tempo_int_target_relogio) >= tempo_pos_target
                    and not no_bp.cg_convergiu
            ):
                print(f"[PARADA] Rodou {tempo_pos_target:.0f}s após atingir FO alvo inteira.")
                sol_pool.motivoConv = "fo_target_int_mais_tempo"
                break

            if not _tempo_lim_consumido and (time.time() - t0N) > tempo_limite_no:
                elapsed_no = time.time() - t0N
                print(f"[Nó {no_bp.id_no}] Tempo limite do nó atingido ({elapsed_no:.1f}s > {tempo_limite_no:.0f}s)")
                if usar_estabilizacao and not fase_final_sem_estab:
                    print("[TEMPO] Abrindo caixa para checagem final sem estabilização")
                    sol_pool.motivo_desligamento_caixa = "time_limit"  # PARTE 2: instrumentacao
                    fase_final_sem_estab = True
                    _tempo_lim_consumido = True
                    for i in range(inst.nbcd):
                        stab_y_low[i].LB = 0.0
                        stab_y_low[i].UB = 0.0
                        stab_y_up[i].LB = 0.0
                        stab_y_up[i].UB = 0.0

                        # Os coeficientes deixam de ter função, pois a2s variáveis estão fixadas.
                        stab_y_low[i].Obj = 0.0
                        stab_y_up[i].Obj = 0.0

                    model.update()
                    rodadas_sem_melhoria = 0
                    sol_pool.SemMelhora[-1] = 0
                    iter_cg += 1
                    continue
                else:
                    print("[TEMPO] Encerrando CG do nó por tempo limite")
                    sol_pool.motivoConv = "tempo_limite_no"
                    no_bp.parou_por_max_iter = True
                    no_bp.cg_convergiu = False
                    break

            model.optimize()
            no_bp.lp_status = model.Status

            if model.Status != GRB.OPTIMAL:
                no_bp.custo_lp = None
                no_bp.solucao_inteira = False
                no_bp.lambdas = {}
                return

            lb_iteracao = float(model.ObjVal)
            print(
                f"[Nó {no_bp.id_no}] Iter {iter_cg} - Obj = {model.ObjVal:.4f}  Colunas = {sum(len(lbd[k]) for k in lbd)} inst= {inst.nomeInst}")
            print(f"[Nó {no_bp.id_no}] inst= {inst.nomeInst} Colunas ativas na iteração {iter_cg}: ")

            tem_ativa = False
            valor_recomposto = 0.0
            tol_print = 1e-6
            inteirasol = True

            for k in sol_pool.rotas.keys():
                n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
                for p in range(n):
                    val = float(lbd[k][p].X)

                    if val > tol_print:
                        tem_ativa = True
                        if p > 1:
                            colunas_reais_usadas = True

                        seq = sol_pool.rotas[k]["sequencia_rota"][p]
                        custo = float(sol_pool.rotas[k]["custo"][p])
                        valor_recomposto += val * custo

                        if val < 1 - 1e-6:
                            inteirasol = False

                        if self.printarsol:
                            print(f"   veic={k} | col={p} | lambda={val:.6f} | custo={custo:.4f} | rota={seq}")

            if iter_cg==16:
                print("")

            if abs(valor_recomposto - ULTIMAFO) <= 0.001:
                if colunas_reais_usadas:
                    rodadas_sem_melhoria += 1
                    sol_pool.SemMelhora[-1] += 1
                    print(f"MESMA FO-  Sem melhora {rodadas_sem_melhoria} Recom {valor_recomposto} Ultmf {ULTIMAFO}  VALOR SUB {valor_recomposto - ULTIMAFO}")
            else:
                rodadas_sem_melhoria = 0
                sol_pool.SemMelhora[-1] = 0
                print(f"Diff FO-  Sem melhora {rodadas_sem_melhoria} ")
                ULTIMAFO = valor_recomposto

            if not tem_ativa:
                print("   nenhuma coluna ativa")

            if self.printarsol:
                print(f"   valor recomposto = {valor_recomposto:.6f}")
                print("")
            print(f"   valor recomposto = {valor_recomposto:.6f}")

            slack_sum_vis = sum(float(v.X) for v in slack_vis)
            slack_sum_arc = sum(float(v.X) for v in slack_arc.values()) if slack_arc else 0.0
            slack_sum_total = slack_sum_vis + slack_sum_arc

            # =========================
            # Salva melhores LPs do nó
            # =========================
            if valor_recomposto < no_bp.melhor_lp_com_slack - 1e-6:
                no_bp.melhor_lp_com_slack = valor_recomposto
                no_bp.melhor_lp_com_slack_iter = iter_cg

            # LP válido somente sem slack artificial real.
            # y_low/y_up são variáveis de estabilização; elas podem aparecer mesmo com cobertura real ok.
            lp_valido = slack_sum_total <= 1e-6

            if lp_valido and valor_recomposto < no_bp.melhor_lp_valido - 1e-6:
                no_bp.melhor_lp_valido = valor_recomposto
                no_bp.melhor_lp_valido_iter = iter_cg
                no_bp.melhor_lp_valido_rotas = []

                for kk in sol_pool.rotas.keys():
                    n = min(len(lbd[kk]), len(sol_pool.rotas[kk]["sequencia_rota"]))
                    for pp in range(n):
                        val_lp = float(lbd[kk][pp].X)
                        if val_lp > 1e-6:
                            no_bp.melhor_lp_valido_rotas.append({
                                "k": kk,
                                "p": pp,
                                "lambda": val_lp,
                                "custo": float(sol_pool.rotas[kk]["custo"][pp]),
                                "rota": list(sol_pool.rotas[kk]["sequencia_rota"][pp])
                            })

            if (
                    lp_valido
                    and getattr(sol_pool, "FO_TARGET", -1) > 0
                    and not no_bp.achou_lp_target
                    and abs(valor_recomposto - sol_pool.FO_TARGET) <= 1e-4
            ):
                no_bp.achou_lp_target = True
                no_bp.iter_lp_target = iter_cg
                no_bp.tempo_lp_target = time.time() - sol_pool.time_initial
                print(f"[MARCO LP] Relaxado válido atingiu FO alvo = {valor_recomposto:.6f}")

                # LP válido, inteiro e igual ao target → solução ótima provada, para imediatamente
                if inteirasol and getattr(inst, "parar_ao_atingir_int_target", True):
                    no_bp.achou_int_target = True
                    no_bp.iter_int_target = iter_cg
                    no_bp.tempo_int_target = time.time() - sol_pool.time_initial
                    no_bp.melhor_int = valor_recomposto
                    no_bp.melhor_int_iter = iter_cg
                    sol_pool.motivoConv = "lp_inteiro_target"
                    print(f"[PARADA LP INTEIRO] LP valido e inteiro = {valor_recomposto:.4f}. Encerrando.")
                    # registra estado final antes de sair
                    n_cols_final = sum(len(sol_pool.rotas[kk]["sequencia_rota"]) for kk in sol_pool.rotas)
                    sol_pool.registrar_convergencia(
                        inst=inst, iteracao=iter_cg, no_id=no_bp.id_no if no_bp else 0,
                        lb=valor_recomposto, ub=None, n_colunas=n_cols_final,
                        tempo=time.time() - sol_pool.time_initial,
                        ub_mip_iter=valor_recomposto,  # LP inteiro = UB provado
                    )
                    sol_pool.iter_gc += 1
                    break

            if slack_sum_total > 1e-9 and self.printarsol:
                print(
                    f"[Nó {no_bp.id_no}] slack_total={slack_sum_total:.6f} (vis={slack_sum_vis:.6f}, arc={slack_sum_arc:.6f}) inst= {inst.nomeInst}")

            # Diagnóstico de cobertura. Pode comentar para acelerar.
            print("\n--- COBERTURA POR CLIENTE ---")
            for i in range(inst.nbcd):
                soma_lambda = 0.0
                for k in sol_pool.rotas.keys():
                    n = min(len(lbd[k]), len(sol_pool.rotas[k]["rotas_binaria"]))
                    for p in range(n):
                        soma_lambda += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * float(lbd[k][p].X)

                s_val = float(slack_vis[i].X)
                if usar_estabilizacao:
                    ylow_val = float(stab_y_low[i].X)
                    yup_val = float(stab_y_up[i].X)
                else:
                    ylow_val = 0.0
                    yup_val = 0.0

                total_real = soma_lambda + s_val - ylow_val + yup_val
                print(
                    f"cliente {i + 1:02d} | "
                    f"lambda={soma_lambda:.6f} | "
                    f"slack={s_val:.6f} | "
                    f"y_low={ylow_val:.6f} | "
                    f"y_up={yup_val:.6f} | "
                    f"total_real={total_real:.6f}"
                )
            print("")

            pi, sigma, mu_arc_por_k = self.extrair_duais_do_mestre(
                inst=inst,
                model=model,
                sol_pool=sol_pool,
                visita_constr=visita_constr,
                uma_rota_constr=uma_rota_constr,
                constr_arco=constr_arco
            )

            if usar_estabilizacao and aguardando_centro_estab and not fase_final_sem_estab and pi is not None:
                # Ajuste: ainda sem centro utilizavel -- valida os duais desta
                # iteracao antes de aceitar como pi_bar. Com poucas colunas o
                # RMP e dual-degenerado e os duais ficam dominados pelo
                # BIGM_VIS (ex.: pi[i]=1e6 para todo i); isso NAO e um centro
                # utilizavel e nao pode ativar a caixa.
                limite_dual_artificial = 0.95 * BIGM_VIS

                # Projeta componentes ancoradas no BIGM (duais degenerados) para a
                # escala dos duais limpos, em vez de rejeitar o centro. Sem isto, em
                # instancias degeneradas (frota simetrica) algum pi[i] fica preso perto
                # do BIGM em toda iteracao, o centro nunca e aceito e a caixa nunca liga
                # -- deadlock: a caixa precisa de dual limpo e o dual limpo precisa da
                # caixa. A projecao quebra o deadlock; a caixa passa a limitar os duais
                # a [pi_bar +- gamma] e o gamma adaptativo corrige um centro imperfeito.
                _idx_limpos = [
                    i for i in range(inst.nbcd)
                    if math.isfinite(float(pi[i])) and abs(float(pi[i])) < limite_dual_artificial
                ]
                _escala_centro = (
                    statistics.median([abs(float(pi[i])) for i in _idx_limpos])
                    if _idx_limpos else 0.0
                )
                pi_projetado = [
                    float(pi[i])
                    if (math.isfinite(float(pi[i])) and abs(float(pi[i])) < limite_dual_artificial)
                    else _escala_centro
                    for i in range(inst.nbcd)
                ]

                # Aceita assim que a cobertura real esta limpa (sem slack artificial).
                # Nao exige mais que TODOS os duais estejam abaixo do BIGM.
                if len(pi) == inst.nbcd and slack_sum_total <= 1e-6:
                    no_bp.pi_bar = list(pi_projetado)
                    sol_pool.pi_bar = list(pi)  # copia so p/ diagnostico/print
                    aguardando_centro_estab = False

                    # PARTE 1 (calibracao gamma): modo relativo opcional, calculado
                    # uma unica vez (aqui, no momento em que a RAIZ aceita um centro
                    # valido). Filhos nunca passam por este bloco -- ja herdam
                    # no_bp.pi_bar do pai em criar_filhos_por_arco, entao
                    # aguardando_centro_estab comeca False para eles.
                    if bool(getattr(sol_pool, "usar_gamma_relativo", False)):
                        valores_duais = [
                            abs(float(v))
                            for v in pi
                            if math.isfinite(float(v))
                            and abs(float(v)) > 1e-6
                            and abs(float(v)) < 0.95 * BIGM_VIS
                        ]
                        escala_dual = statistics.median(valores_duais) if valores_duais else 1.0

                        rho = float(sol_pool.gamma_rho)
                        gamma_abs_min = float(getattr(sol_pool, "gamma_abs_min", 10.0))
                        gamma_min_factor = float(getattr(sol_pool, "gamma_min_factor", 0.25))
                        gamma_max_factor = float(getattr(sol_pool, "gamma_max_factor", 4.0))

                        gamma_ini_efetivo = max(gamma_abs_min, rho * escala_dual)
                        gamma_min_efetivo = max(gamma_abs_min, gamma_min_factor * gamma_ini_efetivo)
                        gamma_max_efetivo = max(gamma_ini_efetivo, gamma_max_factor * gamma_ini_efetivo)

                        sol_pool.escala_dual_raiz = escala_dual
                        sol_pool.gamma_pi = gamma_ini_efetivo
                        sol_pool.gamma_pi_inicial = gamma_ini_efetivo
                        sol_pool.gamma_pi_min = gamma_min_efetivo
                        sol_pool.gamma_pi_max = gamma_max_efetivo

                        # PARTE 2: instrumentacao (somente diagnostico, nao influencia decisao)
                        sol_pool.gamma_ini_efetivo = gamma_ini_efetivo
                        sol_pool.gamma_min_efetivo = gamma_min_efetivo
                        sol_pool.gamma_max_efetivo = gamma_max_efetivo

                        print(
                            f"[GAMMA REL] rho={rho} | escala_dual={escala_dual:.4f} | "
                            f"gamma_ini={gamma_ini_efetivo:.4f} | gamma_min={gamma_min_efetivo:.4f} | "
                            f"gamma_max={gamma_max_efetivo:.4f}"
                        )

                    gamma = float(sol_pool.gamma_pi)
                    for i in range(inst.nbcd):
                        pi_min = float(no_bp.pi_bar[i]) - gamma
                        pi_max = float(no_bp.pi_bar[i]) + gamma
                        stab_y_low[i].LB = 0.0
                        stab_y_low[i].UB = GRB.INFINITY
                        stab_y_up[i].LB = 0.0
                        stab_y_up[i].UB = GRB.INFINITY
                        stab_y_low[i].Obj = -pi_min
                        stab_y_up[i].Obj = pi_max
                    model.update()

                    _min_pi, _max_pi = min(pi), max(pi)
                    _media_pi = sum(pi) / len(pi) if pi else 0.0
                    print("[ESTAB INIT] Centro válido obtido após enriquecimento do RMP. Ativando caixa.")
                    print(f"[ESTAB INIT] iter={iter_cg} | pi: min={_min_pi:.6f} | max={_max_pi:.6f} | media={_media_pi:.6f}")
                    sol_pool.iter_centro_aceito = iter_cg  # PARTE 2: instrumentacao
                    iter_cg += 1
                    continue
                else:
                    print("[ESTAB INIT] Centro rejeitado: duais dominados pelo BIGM. Iniciando CG sem caixa até obter centro utilizável.")

            elif usar_estabilizacao and not aguardando_centro_estab and not fase_final_sem_estab and pi is not None:
                # TAREFA 3 (passo 9): o centro autoritativo e do no (no_bp.pi_bar),
                # nao do sol_pool. Nao atualiza com os duais da fase final.
                alpha = float(sol_pool.alpha_estab)
                for i in range(inst.nbcd):
                    no_bp.pi_bar[i] = alpha * float(pi[i]) + (1 - alpha) * float(no_bp.pi_bar[i])
                sol_pool.pi_bar = list(no_bp.pi_bar)  # copia so p/ diagnostico/print
                print(f" [ETSAB] gamma_pi = {sol_pool.gamma_pi:4f}")

            if no_bp.matriz_rc == {}:
                no_bp.criaMatriRC(inst)

            t00 = time.time()
            novas_colunas = self.gerar_novas_colunas_com_duais11(
                inst=inst,
                sol_pool=sol_pool,
                no_bp=no_bp,
                pi=pi,
                sigma=sigma,
                mu_arc_por_k=mu_arc_por_k,
                EPS_RC=EPS_RC
            )

            if usar_estabilizacao and not fase_final_sem_estab and not aguardando_centro_estab:
                # PARTE 2 (calibracao gamma): caixa realmente ativa nesta iteracao
                # (nao aguardando centro, nao na fase final sem estabilizacao) --
                # conta para instrumentacao, sem influenciar nenhuma decisao.
                sol_pool.iteracoes_caixa_ativa = getattr(sol_pool, "iteracoes_caixa_ativa", 0) + 1

                print(f"GAMMA PI {sol_pool.gamma_pi}")
                if novas_colunas:
                    sol_pool.gamma_pi = max(float(getattr(sol_pool, "gamma_pi_min", 10.0)), 0.95 * float(sol_pool.gamma_pi))
                else:
                    sol_pool.gamma_pi = min(float(getattr(sol_pool, "gamma_pi_max", 500)), 1.5 * float(sol_pool.gamma_pi))
                print(f"GAMMA PI atualizado {sol_pool.gamma_pi}")

                for i in range(inst.nbcd):
                    pi_centro = float(no_bp.pi_bar[i])
                    gamma_pi = float(sol_pool.gamma_pi)
                    pi_min = pi_centro - gamma_pi
                    pi_max = pi_centro + gamma_pi
                    stab_y_low[i].Obj = -pi_min
                    stab_y_up[i].Obj = pi_max
                model.update()

            print(f"Tempo total nessa geracao : {time.time() - t00:.1f}s")
            print(f"Tempo total no NO: {time.time() - t0N:.1f}s")

            if self.printarsol:
                for col in novas_colunas:
                    k, seq, bin_xij, custo, rc = col
                    print(f"TAMANHO NOVAS COL {len(novas_colunas)}")
                    print("\n--- Nova Coluna ---")
                    print(f"Veículo: {k}")
                    print(f"Sequência: {seq}")
                    print(f"Custo: {custo:.2f}")
                    print(f"Custo Reduzido: {rc:.6f}")
                    print(f"Clientes atendidos: {[i + 1 for i, v in enumerate(bin_xij) if v == 1]}")

            tentativasLP += 1

            # >>> AJUSTE v5: SM bifasico - platos de FO sao esperados na fase de caixa ativa,
            # entao o limite de estagnacao usado neste ponto do loop deve refletir a fase atual
            if usar_estabilizacao and not fase_final_sem_estab:
                nmaxrodadas_sem_melhoria = SM_CAIXA
            else:
                nmaxrodadas_sem_melhoria = SM_FORA

            # =========================
            # Parada por estagnação da FO
            # =========================
            if rodadas_sem_melhoria >= nmaxrodadas_sem_melhoria and colunas_reais_usadas:
                print(f"MELHORA SEM MELHORA {rodadas_sem_melhoria}")
                print(f"[Nó {no_bp.id_no}] PAROU POR ESTAGNAÇÃO DA FO")

                if usar_estabilizacao and not fase_final_sem_estab:
                    if aguardando_centro_estab:
                        print("[ESTAB INIT] Estagnação da FO antes de obter um centro válido. Nó termina sem estabilização.")
                        sol_pool.motivo_desligamento_caixa = "convergiu_sem_precisar_caixa"  # PARTE 2
                        aguardando_centro_estab = False
                    else:
                        print("[ESTAB] Estagnação da FO. Fixando y_low=y_up=0 para checagem final sem estabilização.")
                        sol_pool.motivo_desligamento_caixa = "estagnacao"  # PARTE 2: instrumentacao
                    fase_final_sem_estab = True

                    for i in range(inst.nbcd):
                        stab_y_low[i].LB = 0.0
                        stab_y_low[i].UB = 0.0
                        stab_y_up[i].LB = 0.0
                        stab_y_up[i].UB = 0.0
                        stab_y_low[i].Obj = 0.0
                        stab_y_up[i].Obj = 0.0

                    model.update()
                    rodadas_sem_melhoria = 0
                    sol_pool.SemMelhora[-1] = 0
                    iter_cg += 1
                    continue

                sol_pool.motivoConv = "estagnacao_fo"
                no_bp.cg_convergiu = False
                break

            # =========================
            # Critério correto de convergência
            # =========================
            if not novas_colunas:
                print("SEM NOVAS COLUNAS")
                print(f"RODADA SEM MELHORA {rodadas_sem_melhoria}")
                if getattr(no_bp, "pricing_timeout", False):
                    no_bp.cg_convergiu = False
                    sol_pool.motivoConv = "pricing_timeout_cpp"
                    print("[FALHA CG] O pricing completo terminou por timeout; o LB nao sera certificado.")
                    break

                if inst.temmip and rodadas_sem_melhoria >= nmaxrodadas_sem_melhoria and colunas_reais_usadas:
                    rodadas_sem_melhoria = 0
                    gerou_extra = self.tenta_intensificar_com_mip(
                        inst=inst,
                        sol_pool=sol_pool,
                        no_bp=no_bp,
                        model=model,
                        lbd=lbd,
                        visita_constr=visita_constr,
                        uma_rota_constr=uma_rota_constr,
                        constr_arco=constr_arco,
                        slack_vis=slack_vis,
                        slack_arc=slack_arc,
                        EPS_RC=EPS_RC,
                        tentar_adicionar_coluna=tentar_adicionar_coluna,
                        rota_usa_arco=rota_usa_arco,
                        max_tentativas=3,
                        max_arcos_mip=5
                    )
                    if gerou_extra:
                        print(f"[COLUNAS ITER] novas={colunas_novas_iter} | duplicadas={colunas_duplicadas_iter} | por_veiculo={colunas_novas_por_veiculo_iter}")
                        model.update()
                        iter_cg += 1
                        continue

                if usar_estabilizacao and not fase_final_sem_estab:
                    if aguardando_centro_estab:
                        # item 2: pricing exato completo convergiu sem nunca ter
                        # surgido um centro utilizavel -- o no termina sem
                        # estabilizacao, sem forcar a caixa.
                        print("[ESTAB INIT] Pricing convergiu sem coluna negativa antes de obter um centro válido. Nó termina sem estabilização.")
                        sol_pool.motivo_desligamento_caixa = "convergiu_sem_precisar_caixa"  # PARTE 2
                        aguardando_centro_estab = False
                    else:
                        print("[ESTAB] Sem coluna negativa com box. Fixando y_low=y_up=0 para checagem final sem estabilização.")
                        sol_pool.motivo_desligamento_caixa = "sem_coluna_negativa"  # PARTE 2: instrumentacao
                    fase_final_sem_estab = True

                    for i in range(inst.nbcd):
                        stab_y_low[i].LB = 0.0
                        stab_y_low[i].UB = 0.0
                        stab_y_up[i].LB = 0.0
                        stab_y_up[i].UB = 0.0
                        stab_y_low[i].Obj = 0.0
                        stab_y_up[i].Obj = 0.0

                    model.update()
                    iter_cg += 1
                    continue

                if slack_sum_total <= 1e-6:
                    # secao 7/14: para Petro, "zero candidatas" so certifica quando o
                    # pricing exato (unico que pode certificar) rodou ate o fim para
                    # todo veiculo tentado (busca_completa=True) e sem timeout. Solomon
                    # nao usa esse flag (hasattr(inst,'dados_petro') False) -> inalterado.
                    exato_completo_ok = (not hasattr(inst, "dados_petro")) or getattr(no_bp, "cg_convergiu_exato_completo", False)
                    if exato_completo_ok:
                        no_bp.cg_convergiu = True
                        sol_pool.motivoConv = "convergiu_sem_coluna_negativa"
                    else:
                        no_bp.cg_convergiu = False
                        sol_pool.motivoConv = "pricing_exato_busca_incompleta"
                        print(
                            "[FALHA CG] Nenhuma coluna negativa retornada, mas o pricing exato "
                            "nao completou a busca (busca_completa=False); LB nao sera certificado."
                        )
                else:
                    no_bp.cg_convergiu = False
                    sol_pool.motivoConv = "sem_coluna_negativa_com_slack"

                    print(
                        f"[FALHA CG] Nenhuma coluna negativa, mas ainda existem "
                        f"slacks = {slack_sum_total:.6f}"
                    )

                break

            # =========================
            # MIP de logging — roda no pool ANTES de adicionar novas colunas
            # (mesmo estado do LP → LB e UB consistentes)
            # =========================
            ub_mip_iter = None
            n_cols_antes = sum(len(sol_pool.rotas[kk]["sequencia_rota"]) for kk in sol_pool.rotas)
            n_novas = len(novas_colunas) if novas_colunas else 0
            rodar_mip_log = (
                n_cols_antes > 2 * inst.nbv
                and iter_cg % MIP_LOG_A_CADA_ITERACOES == 0
            )

            if rodar_mip_log:
                print(
                    f"[MIP_LOG] iter={iter_cg} | colunas_pool={n_cols_antes} | "
                    f"frequencia={MIP_LOG_A_CADA_ITERACOES}"
                )
                try:
                    _mlog = gp.Model("MIP_log")
                    _mlog.setParam("OutputFlag", 0)
                    _mlog.setParam("TimeLimit", TIME_LIMIT_MIP_LOG)
                    _zvars = {kk: [] for kk in sol_pool.rotas}
                    for kk in sol_pool.rotas:
                        for pp, seq_pp in enumerate(sol_pool.rotas[kk]["sequencia_rota"]):
                            if not self.coluna_respeita_no(no_bp, seq_pp, kk):
                                continue
                            if coluna_artificial(kk, pp):
                                continue

                            custo_pp = float(sol_pool.rotas[kk]["custo"][pp])
                            v = _mlog.addVar(
                                lb=0.0,
                                ub=1.0,
                                obj=custo_pp,
                                vtype=gp.GRB.BINARY,
                                name=f"zlog_{kk}_{pp}"
                            )
                            _zvars[kk].append((pp, v))
                    _mlog.ModelSense = gp.GRB.MINIMIZE
                    _mlog.update()
                    for ci in range(inst.nbcd):
                        expr = gp.LinExpr()
                        for kk in sol_pool.rotas:
                            for pp, v in _zvars[kk]:
                                expr += float(sol_pool.rotas[kk]["rotas_binaria"][pp][ci]) * v
                        _mlog.addConstr(expr == 1.0)
                    for kk in sol_pool.rotas:
                        if not _zvars[kk]:
                            continue
                        _mlog.addConstr(
                            gp.quicksum(v for _, v in _zvars[kk]) == 1.0,
                            name=f"uma_rota_log_{kk}"
                        )
                    for kk in sol_pool.rotas:
                        proibidos_k = {(i, j) for (i, j, kkk) in no_bp.arcos_proibidos if kkk == kk}
                        fixados_k = {(i, j) for (i, j, kkk) in no_bp.arcos_fixados_em_1 if kkk == kk}
                        branch_arcs_k = proibidos_k | fixados_k

                        for i, j in branch_arcs_k:
                            expr = gp.LinExpr()
                            for pp, v in _zvars[kk]:
                                seq_pp = sol_pool.rotas[kk]["sequencia_rota"][pp]
                                expr += float(rota_usa_arco(seq_pp, i, j)) * v

                            if (i, j) in proibidos_k:
                                _mlog.addConstr(expr == 0.0, name=f"arc_log_0_{kk}_{i}_{j}")
                            else:
                                _mlog.addConstr(expr == 1.0, name=f"arc_log_1_{kk}_{i}_{j}")
                    _mlog.optimize()
                    if _mlog.SolCount > 0:
                        ub_mip_iter = float(_mlog.ObjVal)
                except Exception as _e:
                    print(f"[MIP_LOG erro] iter={iter_cg}: {_e}")

            sol_pool.registrar_convergencia(
                inst=inst,
                iteracao=iter_cg,
                no_id=no_bp.id_no if no_bp else 0,
                lb=lb_iteracao,
                ub=None,
                n_colunas=n_cols_antes,
                tempo=time.time() - sol_pool.time_initial,
                ub_mip_iter=ub_mip_iter,
            )
            sol_pool.iter_gc += 1

            # =========================
            # Adiciona colunas geradas (ALLBEST/BID/PD completa para k_base +
            # copia para outros veiculos), sempre via tentar_adicionar_coluna.
            # secao 2: para kk != k_base, a copia reavalia viabilidade/custo/rc
            # para o veiculo de destino em vez de reaproveitar valores do
            # veiculo de origem (frota pode ser heterogenea).
            # =========================
            print("")
            for col in novas_colunas:
                k_base, seq, binx, custo, rc_base = col

                if len(binx) != inst.nbcd:
                    print(f"[COPIA REJEITADA] origem_k={k_base} | destino_k={k_base} | motivo=binx_tamanho_invalido | seq={seq}")
                    continue

                for kk in sol_pool.rotas.keys():
                    if not self.coluna_respeita_no(no_bp, seq, kk):
                        continue

                    if kk == k_base:
                        custo_kk = custo
                        rc_kk = rc_base
                    elif getattr(inst, "objective_mode", "petrobras") == "silva2024":
                        # secao 8/9 (silva2024): copia entre navios usa o MESMO
                        # oraculo do pricing (avaliar_rota_silva2024), nunca o
                        # avaliador antigo do Petrobras.
                        resultado_kk = self.avaliar_rota_silva2024(inst, kk, seq)
                        if not resultado_kk["viavel"]:
                            print(f"[COPIA REJEITADA] origem_k={k_base} | destino_k={kk} | motivo=viabilidade | seq={seq}")
                            continue

                        custo_kk = resultado_kk["custo"]
                        rc_kk = calcular_rc_coluna(kk, seq, custo_kk)
                    else:
                        resultado_kk = self.avaliador_rota.avaliar_rota(inst, kk, seq)
                        if not resultado_kk.viavel:
                            print(f"[COPIA REJEITADA] origem_k={k_base} | destino_k={kk} | motivo=viabilidade | seq={seq}")
                            continue

                        custo_kk = self.avaliador_rota.custo_rota(inst, kk, seq)
                        rc_kk = calcular_rc_coluna(kk, seq, custo_kk)

                    origem_tag = "pricing_iter" if kk == k_base else "pricing_copia_veiculo"
                    if not tentar_adicionar_coluna(kk, seq, binx, custo_kk, rc_kk, origem=origem_tag):
                        print(f"Nao adicionou no k {kk}")
                        continue

                    if kk != k_base:
                        print(f"[COPIA ACEITA] origem_k={k_base} | destino_k={kk} | custo={custo_kk:.6f} | rc={rc_kk:.6f}")

            print(f"[COLUNAS ITER] novas={colunas_novas_iter} | duplicadas={colunas_duplicadas_iter} | por_veiculo={colunas_novas_por_veiculo_iter}")
            model.update()
            colunas_desde_ultimo_mip += colunas_novas_iter

            # =========================
            # MIP periódico (parada)
            # =========================
            if colunas_desde_ultimo_mip >= MIP_PERIODICO_A_CADA_COLUNAS:
                print(
                    f"[Nó {no_bp.id_no}] Rodando MIP periódico após "
                    f"{colunas_desde_ultimo_mip} novas colunas realmente adicionadas..."
                )

                mip_periodico = gp.Model(f"MIP_periodico_no_{no_bp.id_no}")
                mip_periodico.setParam("OutputFlag", 0)

                z_per = {k: [] for k in sol_pool.rotas.keys()}

                for k in sol_pool.rotas.keys():
                    nrotas = len(sol_pool.rotas[k]["sequencia_rota"])
                    for p in range(nrotas):
                        seqp = sol_pool.rotas[k]["sequencia_rota"][p]
                        custop = float(sol_pool.rotas[k]["custo"][p])

                        if not self.coluna_respeita_no(no_bp, seqp, k):
                            continue

                        if coluna_artificial(k, p):
                            continue

                        var = mip_periodico.addVar(lb=0.0, ub=1.0, obj=custop, vtype=GRB.BINARY, name=f"zper_{k}_{p}")
                        z_per[k].append((p, var))

                mip_periodico.ModelSense = GRB.MINIMIZE
                mip_periodico.update()

                for i in range(inst.nbcd):
                    expr = gp.LinExpr()
                    for k in sol_pool.rotas.keys():
                        for p, var in z_per[k]:
                            expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
                    mip_periodico.addConstr(expr == 1.0, name=f"visita_{i}")

                for k in sol_pool.rotas.keys():
                    expr = gp.LinExpr()
                    for p, var in z_per[k]:
                        expr += var
                    mip_periodico.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

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

                    if not usou_coluna_inicial:
                        if float(mip_periodico.ObjVal) < no_bp.melhor_int - 1e-6:
                            no_bp.melhor_int = float(mip_periodico.ObjVal)
                            no_bp.melhor_int_iter = iter_cg
                            no_bp.melhor_int_rotas = []

                            for kk in sol_pool.rotas.keys():
                                for pp, var in z_per[kk]:
                                    if float(var.X) > 0.5:
                                        no_bp.melhor_int_rotas.append({
                                            "k": kk,
                                            "p": pp,
                                            "z": 1,
                                            "custo": float(sol_pool.rotas[kk]["custo"][pp]),
                                            "rota": list(sol_pool.rotas[kk]["sequencia_rota"][pp])
                                        })

                        if (
                                getattr(sol_pool, "FO_TARGET", -1) > 0
                                and not no_bp.achou_int_target
                                and abs(float(mip_periodico.ObjVal) - sol_pool.FO_TARGET) <= 1e-4
                        ):
                            no_bp.achou_int_target = True
                            no_bp.iter_int_target = iter_cg
                            no_bp.tempo_int_target = time.time() - sol_pool.time_initial
                            tempo_int_target_relogio = time.time()
                            print(f"[MARCO INT] MIP periódico atingiu FO alvo = {mip_periodico.ObjVal:.6f}")
                            if getattr(inst, "parar_ao_atingir_int_target", True):
                                sol_pool.motivoConv = "fo_target_int_atingido"
                                print(f"[PARADA ANTECIPADA] FO={mip_periodico.ObjVal:.4f} <= target. Encerrando GC.")
                                # registra estado final: LB=UB=ótimo (gap=0)
                                _fo_final = float(mip_periodico.ObjVal)
                                _n_final = sum(len(sol_pool.rotas[_kk]["sequencia_rota"]) for _kk in sol_pool.rotas)
                                sol_pool.registrar_convergencia(
                                    inst=inst, iteracao=iter_cg + 1,
                                    no_id=no_bp.id_no if no_bp else 0,
                                    lb=_fo_final, ub=None,
                                    n_colunas=_n_final,
                                    tempo=time.time() - sol_pool.time_initial,
                                    ub_mip_iter=_fo_final,
                                )
                                sol_pool.iter_gc += 1
                                break

                        print(
                            f"[Nó {no_bp.id_no}] MIP periódico encontrou solução inteira válida. FO={mip_periodico.ObjVal:.6f}")
                    else:
                        print(f"[Nó {no_bp.id_no}] MIP periódico usou coluna inicial, então foi ignorado.")
                else:
                    print(f"[Nó {no_bp.id_no}] MIP periódico não foi ótimo.")

                colunas_desde_ultimo_mip = 0

            iter_cg += 1

        no_bp.iter_cg_final = iter_cg

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

        artificial_sum_final = 0.0
        for k in sol_pool.rotas.keys():
            n = min(len(lbd[k]), len(sol_pool.rotas[k]["sequencia_rota"]))
            for p in range(n):
                if coluna_artificial(k, p):
                    artificial_sum_final += max(0.0, float(lbd[k][p].X))
        no_bp.artificial_sum_final = artificial_sum_final

        if artificial_sum_final > 1e-9:
            print(
                f"[LB NAO CERTIFICADA] Colunas artificiais ativas no LP: "
                f"lambda_art_total={artificial_sum_final:.8f}"
            )

        if usar_estabilizacao:
            no_bp.lb_confiavel = (
                    no_bp.cg_convergiu
                    and fase_final_sem_estab
                    and (no_bp.slack_sum_final <= 1e-9)
                    and (no_bp.artificial_sum_final <= 1e-9)
                    and (not no_bp.parou_por_max_iter)
                    and (not getattr(no_bp, "pricing_timeout", False))
            )

            y_estab_total = sum(
                abs(float(stab_y_low[i].X)) + abs(float(stab_y_up[i].X))
                for i in range(inst.nbcd)
            )
            if y_estab_total > 1e-6:
                print(f"[LB NAO CERTIFICADA] Variaveis de estabilizacao ativas: y_total={y_estab_total:.8f}")
                no_bp.lb_confiavel = False
        else:
            no_bp.lb_confiavel = (
                    no_bp.cg_convergiu
                    and (no_bp.slack_sum_final <= 1e-9)
                    and (no_bp.artificial_sum_final <= 1e-9)
                    and (not no_bp.parou_por_max_iter)
                    and (not getattr(no_bp, "pricing_timeout", False))
            )

        if no_bp.slack_sum_final > 1e-9:
            no_bp.custo_lp = no_bp.melhor_lp_valido
        else:
            no_bp.custo_lp = float(model.ObjVal)

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
        # MIP final com pool atual
        # =========================
        no_bp.custo_mip = None
        no_bp.lambdas_inteiras = {}
        no_bp.solucao_inteira = False

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

                if coluna_artificial(k, p):
                    continue

                var = mip.addVar(lb=0.0, ub=1.0, obj=custo, vtype=GRB.BINARY, name=f"z_{k}_{p}")
                z[k].append((p, var))

        mip.ModelSense = GRB.MINIMIZE
        mip.update()

        for i in range(inst.nbcd):
            expr = gp.LinExpr()
            for k in sol_pool.rotas.keys():
                for p, var in z[k]:
                    expr += float(sol_pool.rotas[k]["rotas_binaria"][p][i]) * var
            mip.addConstr(expr == 1.0, name=f"visita_{i}")

        for k in sol_pool.rotas.keys():
            expr = gp.LinExpr()
            for p, var in z[k]:
                expr += var
            mip.addConstr(expr == 1.0, name=f"uma_rota_veic_{k}")

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
            no_bp.custo_mip = float(mip.ObjVal)

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

            no_bp.lambdas_inteiras = lambdas_int

            if not usou_coluna_inicial and float(mip.ObjVal) < no_bp.melhor_int - 1e-6:
                no_bp.melhor_int = float(mip.ObjVal)
                no_bp.melhor_int_iter = iter_cg
                no_bp.melhor_int_rotas = []

                for item in selecao:
                    kk = item["k"]
                    pp = item["p"]
                    no_bp.melhor_int_rotas.append({
                        "k": kk,
                        "p": pp,
                        "z": 1,
                        "custo": float(sol_pool.rotas[kk]["custo"][pp]),
                        "rota": list(sol_pool.rotas[kk]["sequencia_rota"][pp])
                    })

            if (
                    not usou_coluna_inicial
                    and getattr(sol_pool, "FO_TARGET", -1) > 0
                    and not no_bp.achou_int_target
                    and abs(float(mip.ObjVal) - sol_pool.FO_TARGET) <= 1e-4
            ):
                no_bp.achou_int_target = True
                no_bp.iter_int_target = iter_cg
                no_bp.tempo_int_target = time.time() - sol_pool.time_initial
                print(f"[MARCO INT] MIP final atingiu FO alvo = {mip.ObjVal:.6f}")

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

            print(f"   valor inteiro recomposto = {valor_int_recomposto:.6f}")
            print("")

            no_bp.rotas_inteiras = []
            no_bp.valor_recomposto_inteiro = 0.0

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
                no_bp.valor_recomposto_inteiro += custo

            if usou_coluna_inicial:
                no_bp.solucao_inteira = False
                print(f"[Nó {no_bp.id_no}] MIP usou coluna inicial. Inteira inválida.")
            else:
                no_bp.solucao_inteira = True

                # secao 14 (silva2024): revalida TODAS as rotas escolhidas pelo
                # oraculo avaliar_rota_silva2024 antes de aceitar o incumbente.
                if getattr(inst, "objective_mode", "petrobras") == "silva2024" and selecao:
                    ub_check = 0.0
                    for item in selecao:
                        kk_ub = item["k"]
                        seq_ub = sol_pool.rotas[kk_ub]["sequencia_rota"][item["p"]]
                        res_ub = self.avaliar_rota_silva2024(inst, kk_ub, seq_ub)
                        if not res_ub["viavel"]:
                            print(f"[SILVA UB CHECK] rota inviavel no oraculo: k={kk_ub} seq={seq_ub} "
                                  f"motivo={res_ub.get('motivo')}")
                            ub_check = float("inf")
                            break
                        ub_check += res_ub["custo"]

                    dif_ub = (ub_check - no_bp.custo_mip) if math.isfinite(ub_check) else float("inf")
                    print(f"[SILVA UB CHECK] MIP={no_bp.custo_mip:.6f} recalculado={ub_check:.6f} dif={dif_ub:.6f}")
                    if not math.isfinite(ub_check) or abs(dif_ub) > 1e-6:
                        print(f"[Nó {no_bp.id_no}] [SILVA UB CHECK] incumbente REJEITADO (divergencia do oraculo).")
                        no_bp.solucao_inteira = False

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

        print(f"[COLUNAS NO] novas_total={contador_colunas_novas_total} | duplicadas_total={contador_colunas_duplicadas_total}")

        print(
            f"Nó {no_bp.id_no} finalizado: "
            f"LP={no_bp.custo_lp:.4f}, "
            f"MIP_pool={no_bp.custo_mip if no_bp.custo_mip is not None else 'None'}, "
            f"tem_inteira={no_bp.solucao_inteira}, "
            f"cg_convergiu={no_bp.cg_convergiu}, "
            f"max_iter={no_bp.parou_por_max_iter}, "
            f"slack_final={no_bp.slack_sum_final:.6f}, "
            f"artificial_final={no_bp.artificial_sum_final:.6f}, "
            f"lb_confiavel={no_bp.lb_confiavel}"
        )

        print(f"Melhor LP com slack = {no_bp.melhor_lp_com_slack} iter={no_bp.melhor_lp_com_slack_iter}")
        print(f"Melhor LP válido    = {no_bp.melhor_lp_valido} iter={no_bp.melhor_lp_valido_iter}")
        print(f"Melhor inteiro      = {no_bp.melhor_int} iter={no_bp.melhor_int_iter}")
        print(
            f"Achou LP target     = {no_bp.achou_lp_target} iter={no_bp.iter_lp_target} tempo={no_bp.tempo_lp_target}")
        print(
            f"Achou INT target    = {no_bp.achou_int_target} iter={no_bp.iter_int_target} tempo={no_bp.tempo_int_target}")

        print("SALDOS")
        print(sol_pool.construtivas)

        if no_bp.id_no == 0:
            pool_ini_por_k = {k: len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()}
            # self.exportar_colunas_pool_raiz_csv(sol_pool, no_bp, pool_ini_por_k)
            print("PRIMEIRO NO")


    def extrair_duais_do_mestre(self, inst, model, sol_pool, visita_constr, uma_rota_constr, constr_arco):
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

        if self.printarsoldual:
            print("\n================ DUAIS DO MESTRE ================")

            print("\nPI (clientes):")
            for j, val in enumerate(pi, start=1):
                print(f"  pi[{j}] = {val: .6f}")

            print("\nSIGMA (veículos):")
            for k in sol_pool.rotas.keys():
                print(f"  sigma[{k}] = {sigma[k]: .6f}")

            print("\nMU (arcos):")
            tem_mu = False
            for k in sol_pool.rotas.keys():
                if mu_arc_por_k[k]:
                    tem_mu = True
                    print(f"  Veículo {k}:")
                    for (i, j), val in sorted(mu_arc_por_k[k].items()):
                        print(f"    mu[{k}][({i},{j})] = {val: .6f}")

            if not tem_mu:
                print("  sem duais de arco")

            print("=================================================\n")

        # ================= ESTABILIZAÇÃO DOS DUAIS =================
        usar_estabilizacao = True
        alpha = 0.7  # peso do dual atual

        pi_estavel = []

        if usar_estabilizacao:

            # reseta se não existe ou se o tamanho mudou (novo nó do B&P)
            if not hasattr(self, "pi_antigo") or self.pi_antigo is None or len(self.pi_antigo) != len(pi):
                self.pi_antigo = pi[:]
                pi_estavel = pi[:]

            else:
                # verifica se os duais são artificiais (big-M), se sim não estabiliza
                tem_artificial = any(abs(p) >= 9000 for p in pi)

                for i in range(len(pi)):
                    p_atual = pi[i]
                    p_antigo = self.pi_antigo[i]

                    p_estavel = alpha * p_atual + (1 - alpha) * p_antigo

                    pi_estavel.append(p_estavel)

                # salva o estabilizado, não o cru
                self.pi_antigo = pi_estavel[:]

        else:
            pi_estavel = pi[:]

        # ================= FIM ESTABILIZAÇÃO DOS DUAIS =================

        # return pi_estavel, sigma, mu_arc_por_k
        return pi, sigma, mu_arc_por_k

    def gerar_novas_colunas_com_duaisant(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC):
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
                nova_rota, custo_red = self.SUB_VNSRANDOM(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )

                # nova_rota2, custo_red2 = self.SUB_VNSRANDOMant(
                #    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                # )

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

    def gerar_novas_colunas_com_duaismanha(
            self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC,
            limiar_rc=None, usar_insertion=True
    ):
        if limiar_rc is None:
            limiar_rc = -EPS_RC

        novas_colunas = []
        ks = list(sol_pool.rotas.keys())

        # round-robin
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        # função de similaridade leve
        def rota_parecida(seq, rotas_existentes, limiar=0.9):
            arcos_novos = {(seq[t], seq[t + 1]) for t in range(len(seq) - 1)}

            for seq2 in rotas_existentes:
                arcos_old = {(seq2[t], seq2[t + 1]) for t in range(len(seq2) - 1)}

                inter = len(arcos_novos & arcos_old)
                base = max(1, min(len(arcos_novos), len(arcos_old)))

                if inter / base >= limiar:
                    return True
            return False

        # ordem de tentativa dos veículos
        lista_k_tentativa = []
        nks = len(ks)
        for off in range(nks):
            idx = (no_bp.prox_k_idx + off) % nks
            lista_k_tentativa.append(ks[idx])

        max_colunas_aceitas = 1

        for k in lista_k_tentativa:
            mu_arc = mu_arc_por_k.get(k, {})

            candidatas = []

            # -----------------------
            # HEURÍSTICAS
            # -----------------------

            # insertion (controlada)
            if usar_insertion and inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22:
                rota, rc = self.SUB_HEUR_ALLBESTINSERTION(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if rota is not None and rc is not None:
                    candidatas.append({"rota": rota, "rc": float(rc), "metodo": 1})

            # bidirecional
            if inst.nbconstrutiva != 3:
                rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if rota is not None and rc is not None:
                    candidatas.append({"rota": rota, "rc": float(rc), "metodo": 3})

            if not candidatas:
                continue

            # ordena por melhor rc
            candidatas.sort(key=lambda x: x["rc"])

            escolhida = None

            for cand in candidatas:
                seq = cand["rota"]["clientes"]
                rc = cand["rc"]

                print(f"[Nó {no_bp.id_no}] k={k} | tenta metodo={cand['metodo']} | rc={rc:.6f}")

                # filtro rc
                if rc >= limiar_rc:
                    continue

                # respeita branching
                if not self.coluna_respeita_no(no_bp, seq, k):
                    continue

                # filtro 1: rota idêntica
                if seq in sol_pool.rotas[k]["sequencia_rota"]:
                    print("REJEITA: rota idêntica")
                    continue

                # filtro 2: rota parecida
                if rota_parecida(seq, sol_pool.rotas[k]["sequencia_rota"], 0.9):
                    print("REJEITA: muito parecida")
                    continue

                escolhida = cand
                break

            if escolhida is None:
                continue

            seq = escolhida["rota"]["clientes"]
            rc = escolhida["rc"]

            escolhida["rota"]["custo_reduzido"] = rc

            novas_colunas.append((
                k,
                seq,
                escolhida["rota"]["bin_xij"],
                escolhida["rota"]["custo"],
                rc
            ))

            print(f"[Nó {no_bp.id_no}] k={k} | ACEITA | rc={rc:.6f} | seq={seq}")

            # contabiliza heurística
            sol_pool.construtivas[escolhida["metodo"]] += 1

            # tabu update
            mat = no_bp.tabu_until[k]
            for i in range(inst.nbn):
                for j in range(inst.nbn):
                    if mat[i][j] > 0:
                        mat[i][j] -= 1

            for t in range(len(seq) - 1):
                i, j = seq[t], seq[t + 1]
                no_bp.freq_arc[k][i][j] += 1
                no_bp.last_arc[k][i][j] = 0
                no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

            # atualiza round-robin
            pos_k = ks.index(k)
            no_bp.prox_k_idx = (pos_k + 1) % len(ks)

            if len(novas_colunas) >= max_colunas_aceitas:
                break

        return novas_colunas

    def gerar_novas_colunas_com_duais5(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC, limiar_rc=None):
        if limiar_rc is None:
            limiar_rc = -EPS_RC

        novas_colunas = []
        ks = list(sol_pool.rotas.keys())

        # round-robin
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        # fase inicial: enquanto todos tiverem só artificiais
        num_artificiais_iniciais = 2
        so_artificiais = True
        for kk in ks:
            if len(sol_pool.rotas[kk]["sequencia_rota"]) > num_artificiais_iniciais:
                so_artificiais = False
                break

        if so_artificiais:
            lista_k_tentativa = ks[:]
            max_colunas_aceitas = len(ks)
        else:
            lista_k_tentativa = []
            nks = len(ks)
            for off in range(nks):
                idx = (no_bp.prox_k_idx + off) % nks
                lista_k_tentativa.append(ks[idx])
            max_colunas_aceitas = 1

        for k in lista_k_tentativa:
            mu_arc = mu_arc_por_k.get(k, {})

            melhor_rota = None
            melhor_custo_red = float("inf")
            metodo_escolhido = -1

            # 1) ALL BEST INSERTION
            if inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22:
                rota, rc = self.SUB_HEUR_ALLBESTINSERTION(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 1

            # se insertion já achou coluna suficientemente boa, não chama o bidirecional
            if not (melhor_rota is not None and melhor_custo_red < limiar_rc):
                if inst.nbconstrutiva != 3:
                    rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                        melhor_rota = rota
                        melhor_custo_red = float(rc)
                        metodo_escolhido = 3

            if melhor_rota is None:
                print(f"[Nó {no_bp.id_no}] k={k} | nenhuma coluna encontrada")
                continue

            print(
                f"[Nó {no_bp.id_no}] k={k} | melhor metodo={metodo_escolhido} | "
                f"rc={float(melhor_custo_red):.6f} | limiar={float(limiar_rc):.6f}"
            )

            if metodo_escolhido >= 0:
                sol_pool.construtivas[metodo_escolhido] += 1

            if float(melhor_custo_red) < limiar_rc:
                seq = melhor_rota["clientes"]

                if not self.coluna_respeita_no(no_bp, seq, k):
                    print(f"[Nó {no_bp.id_no}] k={k} | REJEITA por não respeitar nó | seq={seq}")
                    continue

                melhor_rota["custo_reduzido"] = float(melhor_custo_red)

                novas_colunas.append((
                    k,
                    seq,
                    melhor_rota["bin_xij"],
                    melhor_rota["custo"],
                    float(melhor_custo_red)
                ))

                print(
                    f"[Nó {no_bp.id_no}] k={k} | ACEITA | "
                    f"rc={float(melhor_custo_red):.6f} | seq={seq}"
                )

                # tabu
                mat = no_bp.tabu_until[k]
                for i in range(inst.nbn):
                    for j in range(inst.nbn):
                        if mat[i][j] > 0:
                            mat[i][j] -= 1

                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    no_bp.freq_arc[k][i][j] += 1
                    no_bp.last_arc[k][i][j] = 0
                    no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

                if len(novas_colunas) >= max_colunas_aceitas:
                    pos_k = ks.index(k)
                    no_bp.prox_k_idx = (pos_k + 1) % len(ks)
                    break
            else:
                print(
                    f"[Nó {no_bp.id_no}] k={k} | REJEITA por limiar | "
                    f"rc={float(melhor_custo_red):.6f} | limiar={float(limiar_rc):.6f}"
                )

        return novas_colunas

    def gerar_novas_colunas_com_duais4(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC, limiar_rc=None):
        if limiar_rc is None:
            limiar_rc = -EPS_RC

        novas_colunas = []
        ks = list(sol_pool.rotas.keys())

        # round-robin
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        # fase inicial: enquanto todos tiverem só artificiais
        num_artificiais_iniciais = 2
        so_artificiais = True
        for kk in ks:
            if len(sol_pool.rotas[kk]["sequencia_rota"]) > num_artificiais_iniciais:
                so_artificiais = False
                break

        if so_artificiais:
            lista_k_tentativa = ks[:]
            max_colunas_aceitas = len(ks)
        else:
            lista_k_tentativa = []
            nks = len(ks)
            for off in range(nks):
                idx = (no_bp.prox_k_idx + off) % nks
                lista_k_tentativa.append(ks[idx])
            max_colunas_aceitas = 1

        for k in lista_k_tentativa:
            mu_arc = mu_arc_por_k.get(k, {})

            melhor_rota = None
            melhor_custo_red = float("inf")
            metodo_escolhido = -1

            # 1) ALL BEST INSERTION
            if inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22:
                rota, rc = self.SUB_HEUR_ALLBESTINSERTION(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 1

            # early stop: se a insertion já achou coluna suficientemente boa,
            # não chama o bidirecional
            if not (melhor_rota is not None and melhor_custo_red < limiar_rc):
                # 3) BIDIRECIONAL
                if inst.nbconstrutiva != 3:
                    rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                        melhor_rota = rota
                        melhor_custo_red = float(rc)
                        metodo_escolhido = 3

            if melhor_rota is None:
                continue

            if metodo_escolhido >= 0:
                sol_pool.construtivas[metodo_escolhido] += 1

            if float(melhor_custo_red) < limiar_rc:
                seq = melhor_rota["clientes"]

                if not self.coluna_respeita_no(no_bp, seq, k):
                    continue

                melhor_rota["custo_reduzido"] = float(melhor_custo_red)

                novas_colunas.append((
                    k,
                    seq,
                    melhor_rota["bin_xij"],
                    melhor_rota["custo"],
                    float(melhor_custo_red)
                ))

                # tabu
                mat = no_bp.tabu_until[k]
                for i in range(inst.nbn):
                    for j in range(inst.nbn):
                        if mat[i][j] > 0:
                            mat[i][j] -= 1

                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    no_bp.freq_arc[k][i][j] += 1
                    no_bp.last_arc[k][i][j] = 0
                    no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

                if len(novas_colunas) >= max_colunas_aceitas:
                    pos_k = ks.index(k)
                    no_bp.prox_k_idx = (pos_k + 1) % len(ks)
                    break

        return novas_colunas

    def gerar_novas_colunas_com_duais(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC):
        import random
        import time

        novas_colunas = []
        ks = list(sol_pool.rotas.keys())

        # ============================================================
        # CONTROLE DA FROTA HOMOGÊNEA
        # ============================================================
        frota_homogenea = True

        # Opções:
        # "um_randomico"  -> roda pricing 1 vez e adiciona em 1 veículo aleatório
        # "um_balanceado" -> roda pricing 1 vez e adiciona no veículo com menos colunas
        modo_frota_homogenea = "todos"  # -> roda pricing 1 vez e replica para todos os veículos
        # modo_frota_homogenea = "por_veiculo"#   -> comportamento antigo: roda pricing para cada veículo
        # modo_frota_homogenea = "um_balanceado"

        # ============================================================
        # ROUND-ROBIN
        # ============================================================
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        # ============================================================
        # FASE INICIAL
        # ============================================================
        num_artificiais_iniciais = 2
        so_artificiais = True

        for kk in ks:
            if len(sol_pool.rotas[kk]["sequencia_rota"]) > num_artificiais_iniciais:
                so_artificiais = False
                break

        if so_artificiais:
            lista_k_tentativa = ks[:]
        else:
            lista_k_tentativa = []
            nks = len(ks)

            for off in range(nks):
                idx = (no_bp.prox_k_idx + off) % nks
                lista_k_tentativa.append(ks[idx])

        # ============================================================
        # LIMITE DE COLUNAS ACEITAS
        # ============================================================
        if so_artificiais:
            max_colunas_aceitas = len(ks)
        else:
            if frota_homogenea and modo_frota_homogenea == "todos":
                max_colunas_aceitas = len(ks)
            else:
                max_colunas_aceitas = 1

        # ============================================================
        # DEFINE QUANTAS VEZES RODAR O PRICING
        # ============================================================
        if frota_homogenea and modo_frota_homogenea != "por_veiculo":
            # Roda o pricing uma única vez
            if modo_frota_homogenea == "um_balanceado":
                k_ref = min(
                    lista_k_tentativa,
                    key=lambda kk: len(sol_pool.rotas[kk]["sequencia_rota"])
                )
            else:
                k_ref = random.choice(lista_k_tentativa)

            lista_k_pricing = [k_ref]

        else:
            # Comportamento antigo: roda pricing para cada veículo
            lista_k_pricing = lista_k_tentativa

        # ============================================================
        # LOOP DE PRICING
        # ============================================================
        for k in lista_k_pricing:
            mu_arc = mu_arc_por_k.get(k, {})

            melhor_rota = None
            melhor_custo_red = float("inf")
            metodo_escolhido = -1

            # ========================================================
            # 1) ALL BEST INSERTION
            # ========================================================
            if inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22:
                rota, rc = self.SUB_HEUR_ALLBESTINSERTION(
                    inst,
                    pi,
                    sigma_k=sigma[k],
                    k=k,
                    NO_BP=no_bp,
                    mu_arc=mu_arc
                )

                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 1

            # ========================================================
            # 3) BIDIRECIONAL CPP
            # Só chama se ainda não encontrou coluna boa
            # ========================================================
            if not (melhor_rota is not None and melhor_custo_red < -EPS_RC):

                if inst.nbconstrutiva != 3:
                    t0 = time.time()

                    rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL_CPP(
                        inst,
                        pi,
                        sigma[k],
                        k,
                        arcos_proibidos=no_bp.arcos_proibidos if no_bp else None,
                        arcos_fixados=no_bp.arcos_fixados_em_1 if no_bp else None,
                        mu_arc=mu_arc
                    )

                    t2 = time.time()
                    print(f"Tempo CPP {t2 - t0}")

                    if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                        melhor_rota = rota
                        melhor_custo_red = float(rc)
                        metodo_escolhido = 3

            # ========================================================
            # 4) VNS RANDOM
            # Só chama se ainda não encontrou rota
            # ========================================================
            if melhor_rota is None:
                rota, rc = self.SUB_VNSRANDOM(
                    inst,
                    pi,
                    sigma_k=sigma[k],
                    k=k,
                    NO_BP=no_bp,
                    mu_arc=mu_arc
                )

                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 4

            if melhor_rota is None:
                continue

            if metodo_escolhido >= 0:
                sol_pool.construtivas[metodo_escolhido] += 1

            if float(melhor_custo_red) >= -EPS_RC:
                continue

            seq = melhor_rota["clientes"]

            # ========================================================
            # DEFINE EM QUAIS VEÍCULOS A COLUNA SERÁ ADICIONADA
            # ========================================================
            if frota_homogenea and modo_frota_homogenea == "todos":
                ks_destino = lista_k_tentativa[:]

            elif frota_homogenea and modo_frota_homogenea == "um_randomico":
                ks_destino = [random.choice(lista_k_tentativa)]

            elif frota_homogenea and modo_frota_homogenea == "um_balanceado":
                k_destino = min(
                    lista_k_tentativa,
                    key=lambda kk: len(sol_pool.rotas[kk]["sequencia_rota"])
                )
                ks_destino = [k_destino]

            else:
                ks_destino = [k]

            # ========================================================
            # ADICIONA A COLUNA
            # ========================================================
            for kk in ks_destino:

                if not self.coluna_respeita_no(no_bp, seq, kk):
                    continue

                melhor_rota["custo_reduzido"] = float(melhor_custo_red)

                novas_colunas.append((
                    kk,
                    seq,
                    melhor_rota["bin_xij"],
                    melhor_rota["custo"],
                    float(melhor_custo_red)
                ))

                # ====================================================
                # TABU DO VEÍCULO kk
                # ====================================================
                if no_bp is not None and hasattr(no_bp, "tabu_until"):
                    mat = no_bp.tabu_until[kk]

                    for i in range(inst.nbn):
                        for j in range(inst.nbn):
                            if mat[i][j] > 0:
                                mat[i][j] -= 1

                    for t in range(len(seq) - 1):
                        i, j = seq[t], seq[t + 1]
                        no_bp.freq_arc[kk][i][j] += 1
                        no_bp.last_arc[kk][i][j] = 0
                        no_bp.tabu_until[kk][i][j] = no_bp.tabu_tenure

                if len(novas_colunas) >= max_colunas_aceitas:
                    break

            if len(novas_colunas) >= max_colunas_aceitas:
                pos_k = ks.index(k)
                no_bp.prox_k_idx = (pos_k + 1) % len(ks)
                break

        return novas_colunas

    def _filtrar_candidatas_validas(self, inst, sol_pool, no_bp, k, candidatas):
        """Filtro de seguranca aplicado a QUALQUER origem (ALLBEST/BID/PD/fallback),
        antes de a candidata poder ser selecionada (secao 8): respeita o branching
        do no e, para Petro, revalida cargas dinamicas (deck/diesel/agua)."""
        aceitas = []
        for c in candidatas:
            seq = c["seq"]
            if not self.coluna_respeita_no(no_bp, seq, k):
                continue
            if hasattr(inst, "dados_petro") and not sol_pool.viavel_cargas_petro(inst, k, seq):
                print(f"[DESCARTA PETRO] k={k} | rota viola coleta antes da entrega por plataforma | seq={seq}")
                continue
            aceitas.append(c)
        return aceitas

    @staticmethod
    def _certifica_pricing_exato_completo(exato_tentado_algum, exato_busca_completa_todos, exato_timeout_algum):
        """Secao 7: so certifica ausencia de colunas negativas quando o pricing
        exato foi tentado, terminou a enumeracao (busca_completa) para TODOS os
        veiculos em que rodou nesta iteracao, e nenhuma chamada teve timeout."""
        return bool(exato_tentado_algum and exato_busca_completa_todos and not exato_timeout_algum)

    @staticmethod
    def _verifica_limite_colunas_multi(kk, colunas_novas_iter, colunas_novas_por_veiculo_iter, max_iter, max_por_veiculo):
        """Secao 1 (revisao): os limites valem para colunas REALMENTE adicionadas
        ao pool nesta iteracao, nao para candidatas selecionadas -- uma mesma
        candidata pode virar varias copias (uma por veiculo), entao o teto
        precisa ser conferido aqui, no ponto central de insercao. Retorna
        (permitido, motivo); motivo em {None, 'limite_total', 'limite_veiculo'}."""
        if colunas_novas_iter >= max_iter:
            return False, "limite_total"
        if colunas_novas_por_veiculo_iter.get(kk, 0) >= max_por_veiculo:
            return False, "limite_veiculo"
        return True, None

    @staticmethod
    def _calcular_rc_coluna(seq, custo_original, pi, sigma_kk, mu_arc_kk, nbcd):
        """Secao 2: formula do custo reduzido de uma rota para um veiculo kk,
        identica a usada pelo pricing (custo_reduzido_rota em
        SUB_HEUR_ALLBESTINSERTION_MULTI / delta_rc no C++): custo_original menos
        os duais pi dos clientes atendidos, menos sigma_kk, menos os duais de
        arco mu_arc_kk dos arcos usados. Usada para recalcular o rc de uma
        coluna copiada para um veiculo diferente do de origem (nao reaproveita
        rc_base + sigma[k_base] - sigma[kk], que so seria valido sob
        homogeneidade completa)."""
        mu_arc_kk = mu_arc_kk or {}
        rc = float(custo_original)
        for t in range(len(seq) - 1):
            i, j = seq[t], seq[t + 1]
            rc -= float(mu_arc_kk.get((i, j), 0.0))
        for cliente in seq:
            if 1 <= cliente <= nbcd:
                rc -= float(pi[cliente - 1])
        rc -= float(sigma_kk)
        return rc

    @staticmethod
    def _selecionar_colunas_multi(candidatas_por_k, lista_k_tentativa, ks, max_colunas_novas_iter, max_colunas_novas_veiculo):
        """Secao 9: selecao circular das candidatas por veiculo, seguindo o
        round-robin (lista_k_tentativa) e respeitando max_colunas_novas_iter/
        max_colunas_novas_veiculo. Nao faz ordenacao global por rc (isso
        voltaria a privilegiar sempre o mesmo veiculo) -- espera que
        candidatas_por_k[k] ja venha ordenada do rc mais negativo para o
        menos negativo. Estatico e sem efeitos colaterais (nao muta o dict
        de entrada) para poder ser testado isoladamente."""
        filas = {k: list(candidatas_por_k.get(k, [])) for k in ks}
        selecionadas = []
        usadas_por_k = {k: 0 for k in ks}
        while len(selecionadas) < max_colunas_novas_iter:
            adicionou_na_passagem = False
            for k in lista_k_tentativa:
                if usadas_por_k[k] >= max_colunas_novas_veiculo:
                    continue
                if not filas.get(k):
                    continue
                selecionadas.append(filas[k].pop(0))
                usadas_por_k[k] += 1
                adicionou_na_passagem = True
                if len(selecionadas) >= max_colunas_novas_iter:
                    break
            if not adicionou_na_passagem:
                break
        return selecionadas

    def gerar_novas_colunas_com_duais11(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC):
        """Multi-column pricing (secao 8): para cada veiculo tentado nesta iteracao,
        reune ate MAX_CANDIDATAS_PRICING candidatas negativas ineditas (ALLBEST multi;
        se nada, BID multi; se nada, PD completa/exato multi -- so este ultimo pode
        certificar convergencia). Depois seleciona, respeitando o round-robin e os
        limites MAX_COLUNAS_NOVAS_ITER/MAX_COLUNAS_NOVAS_VEICULO (secao 9), sempre
        passando pela dupla filtragem (coluna_respeita_no + viavel_cargas_petro) e,
        mais tarde, por tentar_adicionar_coluna em resolver_no_com_pool."""

        no_bp.pricing_timeout = False
        ks = list(sol_pool.rotas.keys())

        # round-robin (inalterado)
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        # fase inicial: enquanto todos tiverem só artificiais (inalterado)
        num_artificiais_iniciais = 2
        so_artificiais = True
        for kk in ks:
            if len(sol_pool.rotas[kk]["sequencia_rota"]) > num_artificiais_iniciais:
                so_artificiais = False
                break

        if so_artificiais:
            lista_k_tentativa = ks[:]
        else:
            lista_k_tentativa = []
            nks = len(ks)
            for off in range(nks):
                idx = (no_bp.prox_k_idx + off) % nks
                lista_k_tentativa.append(ks[idx])

        print(f"[ORDEM PRICING] iter={sol_pool.nb_iteracoes} | veiculos={lista_k_tentativa}")

        candidatas_por_k = {}
        # AND de "exato tentado e busca_completa" -- so vale (secao 7) se pelo menos
        # um veiculo chegou ao exato; se algum timeout ocorreu, nunca certifica.
        exato_tentado_algum = False
        exato_busca_completa_todos = True
        exato_timeout_algum = False

        for k in lista_k_tentativa:
            mu_arc = mu_arc_por_k.get(k, {})
            # secao 3: rotas ja existentes deste veiculo, para excluir do pricing
            # (nunca para proibir arcos/alterar dominancia/labels/branching/recursos/RC).
            rotas_existentes_k = {tuple(seq) for seq in sol_pool.rotas[k]["sequencia_rota"]}

            candidatas_k = []
            origem_usada = None

            # Pipeline Silva2024 (integracao no B&P): ALLBEST_SILVA (Python,
            # heuristico) -> BID_SILVA_CPP (C++, heuristico, producao) ->
            # PD_SILVA_CPP (C++, exato, UNICO que certifica). Toda a logica
            # de decisao/certificacao mora em _pricing_silva2024_um_veiculo
            # (nao duplicada aqui) -- fluxo Petrobras/Solomon permanece
            # EXATAMENTE como esta abaixo (fora deste if), inalterado.
            # pricing_silva2024 (enumerativo Python) e SUB_PROG_BID_SILVA
            # Python NAO sao mais chamados neste caminho de producao; ambos
            # continuam intactos e disponiveis para diagnostico/regressao.
            if getattr(inst, "objective_mode", "petrobras") == "silva2024":
                candidatas_k_silva, status_k = self._pricing_silva2024_um_veiculo(
                    inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, k
                )
                candidatas_por_k[k] = candidatas_k_silva[:self.MAX_COLUNAS_NOVAS_VEICULO]
                if status_k["pd_chamado"]:
                    exato_tentado_algum = True
                    if not status_k["pd_completa"]:
                        exato_busca_completa_todos = False
                    if status_k["pd_timeout"]:
                        exato_timeout_algum = True
                continue

            # 1) ALL BEST INSERTION (multi)
            if inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22:
                print("TESTA ALLBEST MULTI")
                geradas, _completa, _to = self.SUB_HEUR_ALLBESTINSERTION_MULTI(
                    inst, sol_pool, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc,
                    max_candidatas=self.MAX_CANDIDATAS_PRICING
                )
                validas = self._filtrar_candidatas_validas(inst, sol_pool, no_bp, k, geradas)
                sem_pool = [c for c in validas if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
                print(f"[PRICING MULTI] origem=ALLBEST | k={k} | geradas={len(geradas)} | "
                      f"novas_pool={len(sem_pool)} | duplicadas_pool={len(validas) - len(sem_pool)} | "
                      f"duplicadas_lote=0 | completa=False")
                if sem_pool:
                    candidatas_k = sem_pool
                    origem_usada = "ALLBEST"
                    sol_pool.construtivas[1] += 1

            # 2) BIDIRECIONAL (multi para Petro; Solomon mantido single-candidate, sem alteracao)
            if not candidatas_k and inst.nbconstrutiva != 3:
                t0 = time.time()
                if hasattr(inst, "dados_petro"):
                    print("TESTA BID PETRO MULTI")
                    geradas, _completa, to_bid = self.SUB_PROG_DIN_BIDIRECIONAL_PETRO_CPP_MULTI(
                        inst, pi, sigma[k], k, rotas_existentes_k, NO_BP=no_bp, mu_arc=mu_arc, eps=EPS_RC,
                        timeout_s=5, max_labels_por_no=200, max_depth=None, max_combinacoes=200_000,
                        max_candidatas=self.MAX_CANDIDATAS_PRICING
                    )
                    validas = self._filtrar_candidatas_validas(inst, sol_pool, no_bp, k, geradas)
                    sem_pool = [c for c in validas if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
                    print(f"[PRICING MULTI] origem=BID_CPP | k={k} | geradas={len(geradas)} | "
                          f"novas_pool={len(sem_pool)} | duplicadas_pool={len(validas) - len(sem_pool)} | "
                          f"duplicadas_lote=0 | completa=False | timeout={to_bid}")
                    if sem_pool:
                        candidatas_k = sem_pool
                        origem_usada = "BID_CPP"
                        sol_pool.construtivas[3] += 1
                else:
                    print("TESTA BID")
                    rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL_CPP(
                        inst, pi, sigma[k], k,
                        arcos_proibidos=no_bp.arcos_proibidos if no_bp else None,
                        arcos_fixados=no_bp.arcos_fixados_em_1 if no_bp else None,
                        mu_arc=mu_arc
                    )
                    if rota is not None and rc is not None and float(rc) < -EPS_RC:
                        seq = list(rota["clientes"])
                        cand = [{"k": k, "seq": seq, "binx": list(rota["bin_xij"]), "custo": float(rota["custo"]),
                                 "rc": float(rc), "origem": "BID_CPP"}]
                        validas = self._filtrar_candidatas_validas(inst, sol_pool, no_bp, k, cand)
                        sem_pool = [c for c in validas if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
                        if sem_pool:
                            candidatas_k = sem_pool
                            origem_usada = "BID_CPP"
                            sol_pool.construtivas[3] += 1
                print(f'Tempo CPP {time.time() - t0}')

            # 3) PD completa / exato (multi para Petro) -- unico que pode certificar
            if not candidatas_k:
                if hasattr(inst, "dados_petro"):
                    print("TESTA PETRO PD COMPLETA MULTI")
                    exato_tentado_algum = True
                    pricing_exato_timeout_s = float(
                        getattr(inst, "pricing_exato_timeout_s", 15.0)
                    )
                    pricing_exato_max_labels = int(
                        getattr(inst, "pricing_exato_max_labels", 1_000_000_000)
                    )
                    print(
                        f"[PRICING EXATO CONFIG] k={k} | "
                        f"timeout={pricing_exato_timeout_s:.1f}s | "
                        f"max_labels={pricing_exato_max_labels}"
                    )
                    geradas, completa, to_pd = self._petro_pricing_exato_multi(
                        inst, pi, sigma[k], k, rotas_existentes_k, no_bp=no_bp, mu_arc=mu_arc,
                        timeout_s=pricing_exato_timeout_s, max_labels_por_no=pricing_exato_max_labels, max_candidatas=self.MAX_CANDIDATAS_PRICING
                    )
                    if to_pd:
                        no_bp.pricing_timeout = True
                        exato_timeout_algum = True
                        print(
                            f"[PETRO] PD completa excedeu "
                            f"{pricing_exato_timeout_s:.1f}s no veiculo {k}; "
                            f"convergencia nao certificada."
                        )
                    if not completa:
                        exato_busca_completa_todos = False
                    validas = self._filtrar_candidatas_validas(inst, sol_pool, no_bp, k, geradas)
                    sem_pool = [c for c in validas if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
                    print(f"[PRICING MULTI] origem=PD_CPP | k={k} | geradas={len(geradas)} | "
                          f"novas_pool={len(sem_pool)} | duplicadas_pool={len(validas) - len(sem_pool)} | "
                          f"duplicadas_lote=0 | completa={completa} | timeout={to_pd}")
                    if sem_pool:
                        candidatas_k = sem_pool
                        origem_usada = "PD_CPP"
                        sol_pool.construtivas[3] += 1
                else:
                    print("TESTa completo")
                    rota, rc = self.SUB_PROG_DIN_PW_CPP_NOVA(
                        inst, pi, sigma[k], k,
                        arcos_proibidos=no_bp.arcos_proibidos if no_bp else None,
                        arcos_fixados=no_bp.arcos_fixados_em_1 if no_bp else None,
                        mu_arc=mu_arc, widening_seq=[4, 8, -1], eps=EPS_RC
                    )
                    if rota is not None and rc is not None and float(rc) < -EPS_RC:
                        seq = list(rota["clientes"])
                        cand = [{"k": k, "seq": seq, "binx": list(rota["bin_xij"]), "custo": float(rota["custo"]),
                                 "rc": float(rc), "origem": "PD_CPP"}]
                        validas = self._filtrar_candidatas_validas(inst, sol_pool, no_bp, k, cand)
                        sem_pool = [c for c in validas if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
                        if sem_pool:
                            candidatas_k = sem_pool
                            origem_usada = "PD_CPP"
                            sol_pool.construtivas[3] += 1

            if not candidatas_k:
                print("NAO GEROU NADA")

            # ordena por rc mais negativo e ja limita por veiculo (secao 9)
            candidatas_k.sort(key=lambda c: c["rc"])
            candidatas_por_k[k] = candidatas_k[:self.MAX_COLUNAS_NOVAS_VEICULO]

        # Certificacao (secao 7/14): so integra busca_completa/timeout ao cg_convergiu
        # ja existente (em resolver_no_com_pool); nao mexe no resto da logica de LB.
        no_bp.cg_convergiu_exato_completo = Metodos._certifica_pricing_exato_completo(
            exato_tentado_algum, exato_busca_completa_todos, exato_timeout_algum
        )

        # PARTE A (certificacao explicita, so para o modo silva2024): a regra
        # formal exigida e "sem_coluna_negativa E pricing_completo_para_TODOS_k
        # => pode certificar" -- nunca "pricing foi chamado" como sinonimo de
        # "pricing exato concluido". lista_k_tentativa cobre sempre TODOS os
        # veiculos desta iteracao (fase inicial: ks[:]; senao: round-robin de
        # todos os ks a partir de prox_k_idx -- nunca um subconjunto), entao o
        # AND abaixo e de fato "para todos os veiculos". Reescreve (mais estrito/
        # auditavel) o resultado generico acima quando os dois divergirem --
        # nunca o contrario, para nunca certificar mais do que o explicito
        # permite.
        if getattr(inst, "objective_mode", "petrobras") == "silva2024":
            todos_k_certificados = all(
                bool(no_bp.silva_certifica_k.get(kk, False)) for kk in lista_k_tentativa
            )
            if todos_k_certificados != no_bp.cg_convergiu_exato_completo:
                print(f"[SILVA CERT][AVISO] divergencia entre certificacao explicita "
                      f"por veiculo (todos_k_certificados={todos_k_certificados}) e o "
                      f"AND generico legado (cg_convergiu_exato_completo="
                      f"{no_bp.cg_convergiu_exato_completo}) -- usando a explicita.")
            no_bp.cg_convergiu_exato_completo = todos_k_certificados
            print(f"[SILVA CERT] todos_k_certificados={todos_k_certificados}")

        # secao 9: selecao circular respeitando lista_k_tentativa e os limites globais
        selecionadas = Metodos._selecionar_colunas_multi(
            candidatas_por_k, lista_k_tentativa, ks,
            self.MAX_COLUNAS_NOVAS_ITER, self.MAX_COLUNAS_NOVAS_VEICULO
        )

        por_veiculo_log = {}
        for c in selecionadas:
            por_veiculo_log[c["k"]] = por_veiculo_log.get(c["k"], 0) + 1
        print(f"[SELECAO MULTI] iter={sol_pool.nb_iteracoes} | selecionadas={len(selecionadas)} | por_veiculo={por_veiculo_log}")

        # tabu (secao 10): decai e marca as rotas efetivamente selecionadas, mesmo
        # mecanismo de antes (inerte quando tabu_tenure=0).
        for c in selecionadas:
            k, seq = c["k"], c["seq"]
            mat = no_bp.tabu_until[k]
            for i in range(inst.nbn):
                for j in range(inst.nbn):
                    if mat[i][j] > 0:
                        mat[i][j] -= 1
            for t in range(len(seq) - 1):
                i, j = seq[t], seq[t + 1]
                no_bp.freq_arc[k][i][j] += 1
                no_bp.last_arc[k][i][j] = 0
                no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

        if selecionadas:
            ultimo_k = selecionadas[-1]["k"]
            pos_k = ks.index(ultimo_k)
            no_bp.prox_k_idx = (pos_k + 1) % len(ks)

        return [(c["k"], c["seq"], c["binx"], c["custo"], c["rc"]) for c in selecionadas]

    def gerar_novas_colunas_com_duais3(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, EPS_RC):
        import time

        novas_colunas = []
        ks = list(sol_pool.rotas.keys())

        print("\n================ GERAR NOVAS COLUNAS ================")
        print(f"[Nó {no_bp.id_no}] ks disponíveis = {ks}")

        # controle round-robin
        if not hasattr(no_bp, "prox_k_idx") or no_bp.prox_k_idx is None:
            no_bp.prox_k_idx = 0

        print(f"[Nó {no_bp.id_no}] prox_k_idx antes = {no_bp.prox_k_idx}")

        # detectar fase inicial (só artificiais)
        num_artificiais_iniciais = 2

        so_artificiais = True
        for kk in ks:
            if len(sol_pool.rotas[kk]["sequencia_rota"]) > num_artificiais_iniciais:
                so_artificiais = False
                break

        # definir lista de veículos a tentar
        if so_artificiais:
            lista_k_tentativa = ks[:]
            max_colunas_aceitas = len(ks)
        else:
            lista_k_tentativa = []
            nks = len(ks)
            for off in range(nks):
                idx = (no_bp.prox_k_idx + off) % nks
                lista_k_tentativa.append(ks[idx])
            max_colunas_aceitas = 1

        print(f"[Nó {no_bp.id_no}] so_artificiais = {so_artificiais}")
        print(f"[Nó {no_bp.id_no}] lista_k_tentativa = {lista_k_tentativa}")
        print(f"[Nó {no_bp.id_no}] max_colunas_aceitas = {max_colunas_aceitas}")

        # loop de tentativa
        for k in lista_k_tentativa:

            print(f"\n[Nó {no_bp.id_no}] >>> Tentando gerar coluna para veículo k={k}")
            print(f"[Nó {no_bp.id_no}] colunas atuais de k={k}: {len(sol_pool.rotas[k]['sequencia_rota'])}")

            proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
            fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
            mu_arc = mu_arc_por_k.get(k, {})

            melhor_rota = None
            melhor_custo_red = float("inf")
            metodo_escolhido = -1

            # ===== VNS RANDOM ANT =====
            if (inst.nbconstrutiva != 0 and inst.nbconstrutiva != 22):
                rota, rc = self.SUB_VNSRANDOMant(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                print(f"[Nó {no_bp.id_no}] k={k} | método 0 VNS -> {'OK' if rota else 'X'} | rc={rc}")
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 0

            # ===== ALL INSERTION =====
            if (inst.nbconstrutiva != 1 and inst.nbconstrutiva != 22):
                rota, rc = self.SUB_HEUR_ALLBESTINSERTION(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                print(f"[Nó {no_bp.id_no}] k={k} | método 1 INSERTION -> {'OK' if rota else 'X'} | rc={rc}")
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 1

            # ===== HEUR VNS =====
            if (inst.nbconstrutiva != 2 and inst.nbconstrutiva != 22):
                rota, rc = self.SUB_HEUR_VNS(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                print(f"[Nó {no_bp.id_no}] k={k} | método 2 HEUR_VNS -> {'OK' if rota else 'X'} | rc={rc}")
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 2

            # ===== BIDIRECIONAL =====
            if (inst.nbconstrutiva != 3):
                rota, rc = self.SUB_PROG_DIN_BIDIRECIONAL(
                    inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                )
                print(f"[Nó {no_bp.id_no}] k={k} | método 3 BID -> {'OK' if rota else 'X'} | rc={rc}")
                if rota is not None and rc is not None and float(rc) < melhor_custo_red:
                    melhor_rota = rota
                    melhor_custo_red = float(rc)
                    metodo_escolhido = 3

            # nenhum método achou
            if melhor_rota is None:
                print(f"[Nó {no_bp.id_no}] k={k} | nenhum método gerou coluna")
                continue

            print(f"[Nó {no_bp.id_no}] k={k} | melhor método = {metodo_escolhido} | melhor_rc = {melhor_custo_red:.6f}")

            nova_rota = melhor_rota
            custo_red = melhor_custo_red

            if metodo_escolhido >= 0:
                sol_pool.construtivas[metodo_escolhido] += 1

            nova_rota["custo_reduzido"] = float(custo_red)

            if float(custo_red) < -EPS_RC:
                seq = nova_rota["clientes"]

                if not self.coluna_respeita_no(no_bp, seq, k):
                    print(f"[Nó {no_bp.id_no}] k={k} | coluna rejeitada por restrição")
                    continue

                novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"], float(custo_red)))

                print(f"[Nó {no_bp.id_no}] k={k} | COLUNA ACEITA | rc={float(custo_red):.6f} | seq={seq}")

                # tabu
                mat = no_bp.tabu_until[k]
                for i in range(inst.nbn):
                    for j in range(inst.nbn):
                        if mat[i][j] > 0:
                            mat[i][j] -= 1

                for t in range(len(seq) - 1):
                    i, j = seq[t], seq[t + 1]
                    no_bp.freq_arc[k][i][j] += 1
                    no_bp.last_arc[k][i][j] = 0
                    no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure

                # parar se atingiu limite da iteração
                if len(novas_colunas) >= max_colunas_aceitas:
                    pos_k = ks.index(k)
                    no_bp.prox_k_idx = (pos_k + 1) % len(ks)

                    print(f"[Nó {no_bp.id_no}] parada após aceitar {len(novas_colunas)} coluna(s)")
                    print(f"[Nó {no_bp.id_no}] prox_k_idx depois = {no_bp.prox_k_idx}")

                    break

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
            EPS_RC, tentar_adicionar_coluna, rota_usa_arco, max_tentativas=3,
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

                    # secao 11: processa todas as candidatas ja disponiveis (a formulacao
                    # do MIP de intensificacao nao foi alterada), mas respeita os mesmos
                    # limites por iteracao/veiculo da secao 9.
                    adicionou_alguma = False
                    adicionadas_total = 0
                    usadas_por_kk = {}
                    for kk in range(len(sol_pool.rotas.keys())):
                        if adicionadas_total >= self.MAX_COLUNAS_NOVAS_ITER:
                            break
                        for (k_base, seq, binx, custo, custo_red) in novas_colunas:
                            if adicionadas_total >= self.MAX_COLUNAS_NOVAS_ITER:
                                break
                            if usadas_por_kk.get(kk, 0) >= self.MAX_COLUNAS_NOVAS_VEICULO:
                                break
                            # mesmo custo reduzido usado na copia entre veiculos do loop principal
                            rc_kk = custo_red + sigma[k_base] - sigma[kk]
                            if self.coluna_respeita_no(no_bp, seq, kk) and tentar_adicionar_coluna(
                                    kk, seq, binx, custo, rc_kk, origem="intensificacao_mip"
                            ):
                                adicionou_alguma = True
                                adicionadas_total += 1
                                usadas_por_kk[kk] = usadas_por_kk.get(kk, 0) + 1
                                print(
                                    f"[Nó {no_bp.id_no}] Coluna adicionada pela intensificação | kk={kk} | rc={rc_kk:.6f} | rota={seq}")

                    if adicionou_alguma:
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

    def metodo_exato_petro(self, inst, sol, time_limit=1200, threads=1, salvar_modelo=False, diagnostico=True,
                           fixar_rotas=None, considerar_conflito_plataforma=True, silva_sp_arcos_base=True):
        """
        silva_sp_arcos_base (default True -- comportamento IDENTICO ao de
        sempre; SO tem efeito quando inst.objective_mode=="silva2024", SEM
        efeito em modo petrobras): controla se o SP (safe positioning) e
        cobrado tambem na perna de SAIDA da base (base->1a plataforma).
        True (default, formulacao literal): T_ij^k=N_ij^k+SP_k+SET_j quando
        c_i!=c_j -- inclusive saindo da base. SET continua sendo cobrado
        nesse arco em AMBOS os casos (nunca removido). False (experimental,
        convencao observada na Tabela 3 do benchmark Silva): a perna
        base->1a plataforma usa so N+SET, sem SP; as demais pernas entre
        plataformas diferentes continuam N+SP+SET, e a perna de retorno
        plataforma->base continua sem SP/SET em ambos os casos (esse arco
        nunca teve SP/SET, com ou sem esta chave -- ver tempo_arco abaixo).
        Chave so para diagnostico/comparacao com o artigo; nao usada pelo
        B&P (pricing_silva2024/branch_and_price_global) nesta etapa.

        fixar_rotas (opcional, diagnostico -- NAO faz parte da formulacao):
        dict {k: [sequencia de nos incluindo dep0 e depf]}. Quando informado,
        fixa x[i,j,k] em 1 para os arcos da rota dada (e em 0 para os demais
        arcos do navio k), deixando o Gurobi resolver so os horarios (inicio,
        berco, escolha de janela, sequenciamento de plataforma) -- usado para
        comparar o cronograma calculado com uma rota publicada (Tabela 3 do
        benchmark Silva), sem depender do solver escolher a rota.

        considerar_conflito_plataforma (default True -- comportamento IDENTICO
        ao de sempre): quando True, mantem o bloco de nao-sobreposicao ENTRE
        NAVIOS na mesma plataforma (seq_plat), exatamente como ja existia.
        Quando False -- so tem efeito em modo_silva2024, ignorado em modo
        petrobras -- REMOVE apenas esse acoplamento entre navios diferentes,
        usado como referencia de compacto "por navio independente" para
        validar a aditividade das colunas do B&P (nenhuma outra regra --
        janelas, SET, SP, dueTime, TDL, capacidade, precedencia deck,
        carregamento, descarga, velocidades, FO -- e desligada).
        """
        """
        Modelo compacto exclusivo das instancias Petrobras.

        Regras principais:
          - cada order e atendida exatamente uma vez;
          - orders da mesma plataforma atendidas pelo mesmo navio formam um unico bloco;
          - dentro do bloco, toda coleta de deck ocorre antes de qualquer entrega;
          - o navio sai da base com todas as entregas de deck da rota;
          - em cada order, coleta primeiro e entrega depois;
          - diesel e agua usam compartimentos proprios;
          - multiplas janelas de tempo sao preservadas.

        O metodo_exato generico permanece inalterado.
        """
        if not hasattr(inst, "dados_petro"):
            raise ValueError("metodo_exato_petro exige uma instancia carregada por leitura_petro")

        print("==================== Iniciando o MODELO EXATO PETRO")

        dp = inst.dados_petro
        K = list(range(inst.nbv))
        V = list(range(inst.nbn))
        clientes = list(range(1, inst.nbcd + 1))
        dep0 = 0
        depf = inst.nbn - 1
        eps = 1e-9

        # "petrobras" (default, inalterado) ou "silva2024" (benchmark Silva et al. 2024:
        # custo em USD/h por regime, sem conversao para CO2, disponibilidade e limite de
        # viagem por navio, SET+SP cobrados uma vez por plataforma visitada).
        modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"

        # ------------------------------------------------------------------
        # Plataformas: mesma regra usada em _montar_dados_petro_cpp.
        # ------------------------------------------------------------------
        nomes = list(dp.get("nomes", []))
        plataforma_chave = {}
        plataforma_id = [-1] * inst.nbn
        mapa_plataformas = {}
        nos_por_plataforma = defaultdict(list)

        for i in clientes:
            nome = str(nomes[i]) if i < len(nomes) else ""
            if "_order_" in nome:
                chave = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                chave = nome.split("_order", 1)[0]
            elif nome:
                chave = nome
            else:
                lat = round(float(dp.get("lat", [0.0] * inst.nbn)[i]), 6)
                lon = round(float(dp.get("lon", [0.0] * inst.nbn)[i]), 6)
                chave = f"{lat:.6f},{lon:.6f}"

            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)

            p = mapa_plataformas[chave]
            plataforma_id[i] = p
            plataforma_chave[p] = chave
            nos_por_plataforma[p].append(i)

        P = sorted(nos_por_plataforma.keys())

        if modo_silva:
            order_due_time_seg = dp.get("order_due_time_seg", [None] * inst.nbn)
            print("=" * 78)
            print("[SILVA] orders | dueTime: DELIVERY (deckCargoLoad/dieselLoad/waterLoad) "
                  "-> inicio+servico<=dueTime | PICKUP (deckCargoBackload) -> F_k<=dueTime "
                  "(descarga agregada da viagem, sem FIFO/LIFO individual).")
            print(f"{'no':>3} {'sourceOrderId':>13} {'commodity':<18} {'dueTime(h)':>10}  timeWindows(h)")
            for i in clientes:
                due_h = order_due_time_seg[i] / 3600.0 if order_due_time_seg[i] is not None else None
                janelas_h = [(r / 3600.0, d / 3600.0)
                             for r, d in zip(inst.noh[i].READY_TIME, inst.noh[i].DUE_DATE)]
                due_txt = f"{due_h:.2f}" if due_h is not None else "NA"
                print(f"{i:>3} {dp['order_ids'][i]:>13} {dp['commodities'][i]:<18} {due_txt:>10}  {janelas_h}")
            print("=" * 78)

        # SET_p (modo silva2024): platformSetup e por PLATAFORMA/VISITA, nao por order
        # (varias orders podem pertencer a mesma plataforma). Usa o valor lido por no
        # (dp["platform_setup_seg"], em segundos) e confere uniformidade entre as
        # orders de uma mesma plataforma antes de reduzir a um unico valor.
        set_por_plataforma = {}
        if modo_silva:
            platform_setup_seg_tmp = dp.get("platform_setup_seg", [0.0] * inst.nbn)
            for p, nos_p in nos_por_plataforma.items():
                valores = {float(platform_setup_seg_tmp[i]) for i in nos_p}
                if len(valores) > 1:
                    print(f"[AVISO SILVA] platformSetup nao uniforme na plataforma {plataforma_chave[p]}: {valores} -- usando o maior")
                set_por_plataforma[p] = max(valores) if valores else 0.0

        # Dados por order. Usa primeiro os atributos dos nos, com fallback no dicionario Petro.
        def dado_no(i, atributo, chave):
            valor_no = getattr(inst.noh[i], atributo, None)
            if valor_no is not None:
                return float(valor_no)
            vetor = dp.get(chave, [])
            return float(vetor[i]) if i < len(vetor) else 0.0

        deck_load = {i: dado_no(i, "DEMAND_DECK_LOAD", "dem_deck_load") for i in V}
        deck_backload = {i: dado_no(i, "DEMAND_DECK_BACKLOAD", "dem_deck_backload") for i in V}
        diesel = {i: dado_no(i, "DEMAND_DIESEL", "dem_diesel") for i in V}
        agua = {i: dado_no(i, "DEMAND_AGUA", "dem_agua") for i in V}
        servico = {i: float(inst.noh[i].SERVICE_TIME[0]) if getattr(inst.noh[i], "SERVICE_TIME", None) else 0.0 for i in V}

        def tempo_viagem(i, j, k):
            return float(inst.matriz_distancia[i][j]) / float(inst.veiculos[k].velocidade)

        def tempo_navegacao_pura(i, j, k):
            """Tempo de navegacao pura (sem setupArrival/setupDeparture), em segundos.
            Usado apenas na FO ambiental do modo PETROBRAS (t_k); matriz_distancia/
            tempo_viagem continuam sendo a base da viabilidade temporal (inalterada).
            NAO usar para modo silva2024 -- ver tempo_navegacao_silva abaixo."""
            return float(inst.matriz_tempo_navegacao[i][j]) / float(inst.veiculos[k].velocidade)

        def tempo_navegacao_silva(i, j, k):
            """Tempo de navegacao do modo silva2024, POR NAVIO (VL_k/VH_k proprios,
            nao a matriz unica construida com o navio de referencia da frota).
            Formula (piecewise CONTINUA, conforme artigo): d<=threshold: d/VL;
            d>threshold: threshold/VL + (d-threshold)/VH. Distancia fisica (km) vem
            de dp["dist"], remapeada 0<->depf como as demais matrizes; nos da mesma
            plataforma tem dist=0 (ja zerado na leitura)."""
            ii = 0 if i == depf else i
            jj = 0 if j == depf else j
            if ii == jj:
                return 0.0
            dist_km = float(dp["dist"][ii][jj])
            velocities_k = inst.veiculos[k].velocities
            vl = min(velocities_k, key=lambda v: v["above"])["speed"]
            vh = max(velocities_k, key=lambda v: v["above"])["speed"]
            threshold = max(velocities_k, key=lambda v: v["above"])["above"]
            if dist_km <= threshold:
                n_horas = dist_km / vl
            else:
                n_horas = threshold / vl + (dist_km - threshold) / vh
            return n_horas * 3600.0

        def tempo_arco(i, j, k):
            """Tempo de arco usado na propagacao temporal (viabilidade). Em modo
            petrobras e identico a tempo_viagem (no-op). Em modo silva2024, usa
            tempo_navegacao_silva (piecewise continuo, por navio) como base e soma
            SET (setup da plataforma de destino) na primeira vez que o arco entra
            numa plataforma nova -- inclusive saindo da base, ja que
            plataforma_id[dep0]==-1 nunca bate com nenhuma plataforma real. SP
            (safe positioning) e somado no mesmo evento, EXCETO na perna de saida
            da base quando silva_sp_arcos_base=False (chave de diagnostico, default
            True = formulacao literal, identica ao comportamento historico). A
            perna de retorno plataforma->base (j==depf, fora de `clientes`) nunca
            entra neste bloco, com ou sem a chave -- nunca teve SP/SET, em nenhum
            dos dois casos. setupArrival/setupDeparture nao existem no arco em
            Silva (sao 0.0 no JSON): SET+SP e quem faz esse papel."""
            t = tempo_navegacao_silva(i, j, k) if modo_silva else tempo_viagem(i, j, k)
            if modo_silva and j in clientes and plataforma_id[i] != plataforma_id[j]:
                p = plataforma_id[j]
                t += set_por_plataforma.get(p, 0.0)
                if silva_sp_arcos_base or i != dep0:
                    t += float(getattr(inst.veiculos[k], "safe_positioning_time", 0.0))
            return t

        def cap_deck(k):
            return float(getattr(inst.veiculos[k], "cap_deck", inst.veiculos[k].capacidade))

        def cap_diesel(k):
            return float(getattr(inst.veiculos[k], "cap_diesel", float("inf")))

        def cap_agua(k):
            return float(getattr(inst.veiculos[k], "cap_agua", float("inf")))

        # Janelas validas por order.
        janelas = {}
        for i in V:
            ready = list(getattr(inst.noh[i], "READY_TIME", []) or [])
            due = list(getattr(inst.noh[i], "DUE_DATE", []) or [])
            n_janelas = min(len(ready), len(due))
            janelas[i] = [(float(ready[w]), float(due[w])) for w in range(n_janelas)]

        dues_existentes = [fim for js in janelas.values() for _, fim in js]
        max_due = max(dues_existentes) if dues_existentes else 1e9
        for i in V:
            if not janelas[i]:
                janelas[i] = [(0.0, max_due)]

        max_servico = max(servico.values()) if servico else 0.0
        max_viagem = max(tempo_arco(i, j, k) for k in K for i in V for j in V if i != j)
        max_duracao = max((float(getattr(inst.veiculos[k], "trip_duration_limit", 0.0)) for k in K), default=0.0)
        # Ajuste defensivo: inicio[dep0,k] deixa de ser uma constante (agora cresce com
        # o tempo de berco de saida), entao o Big-M precisa cobrir tambem essa duracao.
        _tcd = dp.get("tempo_carreg_deck", [0.0] * inst.nbn)
        _tcdi = dp.get("tempo_carreg_diesel", [0.0] * inst.nbn)
        _tca = dp.get("tempo_carreg_agua", [0.0] * inst.nbn)
        _tdb = dp.get("tempo_descarreg_backload", [0.0] * inst.nbn)
        max_carga_seg = max((float(_tcd[i]) + float(_tcdi[i]) + float(_tca[i]) + float(_tdb[i]) for i in range(len(_tcd))), default=0.0)
        M_tempo = float(max_due + max_servico + max_viagem + max_duracao + max_carga_seg + 1.0)
        M_ordem = float(inst.nbcd + 1)

        model = gp.Model("VRPTW_Exato_Petro")
        model.Params.TimeLimit = float(time_limit)
        model.Params.Threads = max(1, int(threads))
        model.Params.Seed = 42

        # ------------------------------------------------------------------
        # Variaveis.
        # ------------------------------------------------------------------
        x = model.addVars(V, V, K, vtype=GRB.BINARY, name="x")
        visita = model.addVars(clientes, K, vtype=GRB.BINARY, name="visita")
        inicio = model.addVars(V, K, lb=0.0, vtype=GRB.CONTINUOUS, name="inicio")
        ordem = model.addVars(clientes, K, lb=0.0, ub=float(inst.nbcd), vtype=GRB.CONTINUOUS, name="ordem")
        carga = model.addVars(V, K, lb=0.0, vtype=GRB.CONTINUOUS, name="carga_apos")
        usa_plataforma = model.addVars(P, K, vtype=GRB.BINARY, name="usa_plataforma")
        # B_k: instante em que comeca a operacao de berco de SAIDA (>= AT_k). Antes,
        # inicio[dep0,k] era fixado por igualdade a AT_k; agora e derivado de berco[k].
        berco = model.addVars(K, lb=0.0, vtype=GRB.CONTINUOUS, name="berco_inicio")

        y = {}
        for i in clientes:
            for k in K:
                for w in range(len(janelas[i])):
                    y[i, k, w] = model.addVar(vtype=GRB.BINARY, name=f"janela_{i}_{k}_{w}")

        if fixar_rotas is not None:
            # Diagnostico (ver docstring): fixa a rota de cada navio informado,
            # deixando so os horarios livres para o Gurobi resolver.
            for k, rota_fixa in fixar_rotas.items():
                arcos_fixos = set(zip(rota_fixa[:-1], rota_fixa[1:]))
                for i in V:
                    for j in V:
                        if i == j:
                            continue
                        model.addConstr(x[i, j, k] == (1 if (i, j) in arcos_fixos else 0), name=f"fixar_rota_{k}_{i}_{j}")

        # ------------------------------------------------------------------
        # Funcao objetivo Petrobras: consumo ambiental (fundeio/berco/navegacao/DP)
        # + tempo total de utilizacao, ponderados por alpha_fo/eta_fo (JSON).
        # O metodo_exato generico (Solomon) mantem a FO de tempo/distancia
        # inalterada; esta funcao e exclusiva de instancias Petro.
        #
        # Instantes: AT_k=readiness | B_k=berco[k] (inicio do berco de SAIDA,
        # novo, pode ser > AT_k) | P_k=inicio[dep0,k]=B_k+hB_saida_seg_k (partida
        # efetiva) | R_k=inicio[depf,k] (chegada de volta) | F_k=R_k+hB_retorno_seg_k
        # (fim da descarga do backload, novo).
        #
        # hF_k = (B_k-AT_k)/3600           (fundeio antes do berco)
        # hB_k = (hB_saida+hB_retorno)/3600  (berco de saida + de retorno)
        # hN_k = soma da navegacao PURA dos arcos usados, sem setups
        # hDP_k = (R_k-P_k)/3600 - hN_k    (servico + espera + setups offshore)
        # T_k  = F_k - AT_k = (R_k-AT_k)/3600 + hB_retorno/3600
        # ------------------------------------------------------------------
        SEGUNDOS_POR_HORA = 3600.0

        alpha_fo = float(inst.alpha_fo)
        eta_fo = float(inst.eta_fo)
        if modo_silva:
            # Silva et al. (2024): custo em USD/h (FCA/FCB/FCN/FCS), sem conversao
            # para CO2 -- densidade_diesel/conversao_diesel_co2 nao existem/nao sao
            # usados neste modo (None no JSON, e deve continuar assim).
            chi_fo = None
        else:
            chi_fo = float(inst.densidade_diesel) * float(inst.conversao_diesel_co2)

        tempo_carreg_deck = list(dp.get("tempo_carreg_deck", [0.0] * inst.nbn))
        tempo_carreg_diesel = list(dp.get("tempo_carreg_diesel", [0.0] * inst.nbn))
        tempo_carreg_agua = list(dp.get("tempo_carreg_agua", [0.0] * inst.nbn))
        tempo_descarreg_backload = list(dp.get("tempo_descarreg_backload", [0.0] * inst.nbn))

        expr_hF, expr_hB, expr_hN, expr_hDP = {}, {}, {}, {}
        expr_T, expr_D, expr_E = {}, {}, {}
        expr_hB_saida_seg, expr_hB_retorno_seg = {}, {}
        # Termos marginais do f1 de Silva (custo relativo ao navio fundeado/theta=FCA).
        expr_termo_base, expr_termo_nav, expr_termo_serv = {}, {}, {}

        for k in K:
            veic = inst.veiculos[k]
            AT_k = float(veic.readiness)

            # Sequencial: soma dos tempos de carregamento (saida) e de descarga (retorno).
            hB_saida_seg_k = gp.quicksum(
                (tempo_carreg_deck[i] + tempo_carreg_diesel[i] + tempo_carreg_agua[i]) * visita[i, k]
                for i in clientes
            )
            hB_retorno_seg_k = gp.quicksum(tempo_descarreg_backload[i] * visita[i, k] for i in clientes)

            hB_k = (hB_saida_seg_k + hB_retorno_seg_k) / SEGUNDOS_POR_HORA
            _nav_pura = tempo_navegacao_silva if modo_silva else tempo_navegacao_pura
            hN_k = gp.quicksum((_nav_pura(i, j, k) / SEGUNDOS_POR_HORA) * x[i, j, k]
                                for i in V for j in V if i != j)
            hDP_k = (inicio[depf, k] - inicio[dep0, k]) / SEGUNDOS_POR_HORA - hN_k
            hF_k = (berco[k] - AT_k) / SEGUNDOS_POR_HORA
            T_k = (inicio[depf, k] - AT_k) / SEGUNDOS_POR_HORA + hB_retorno_seg_k / SEGUNDOS_POR_HORA

            if modo_silva:
                theta_k, varphi_k, gamma_k, delta_k = veic.cost_anchored, veic.cost_base, veic.cost_navigation, veic.cost_dynamic
            else:
                theta_k, varphi_k, gamma_k, delta_k = veic.fuel_anchored, veic.fuel_base, veic.fuel_navigation, veic.fuel_dynamic

            if modo_silva:
                # Custo MARGINAL relativo ao navio fundeado (theta=FCA): Silva et
                # al. (2024) nao cobra theta*hF -- fundeio e a referencia (custo 0
                # de oportunidade), so os desvios de regime custam algo a mais/menos.
                termo_base_k = (varphi_k - theta_k) * hB_k
                termo_nav_k = (gamma_k - theta_k) * hN_k
                termo_serv_k = (delta_k - theta_k) * hDP_k
                D_k = termo_base_k + termo_nav_k + termo_serv_k
                # Silva: D_k (=f1_k) ja esta em USD, sem conversao para CO2 (E_k so
                # existe aqui para reaproveitar a mesma formula de objetivo abaixo).
                E_k = D_k
            else:
                termo_base_k = termo_nav_k = termo_serv_k = None
                D_k = theta_k * hF_k + varphi_k * hB_k + gamma_k * hN_k + delta_k * hDP_k
                E_k = chi_fo * D_k

            expr_hF[k], expr_hB[k], expr_hN[k], expr_hDP[k] = hF_k, hB_k, hN_k, hDP_k
            expr_T[k], expr_D[k], expr_E[k] = T_k, D_k, E_k
            expr_hB_saida_seg[k], expr_hB_retorno_seg[k] = hB_saida_seg_k, hB_retorno_seg_k
            expr_termo_base[k], expr_termo_nav[k], expr_termo_serv[k] = termo_base_k, termo_nav_k, termo_serv_k

        model.setObjective(
            gp.quicksum(alpha_fo * expr_E[k] + (1.0 - alpha_fo) * eta_fo * expr_T[k] for k in K),
            GRB.MINIMIZE
        )

        # Arcos estruturalmente proibidos.
        for k in K:
            for i in V:
                model.addConstr(x[i, i, k] == 0, name=f"sem_laco_{i}_{k}")
            for i in clientes + [depf]:
                model.addConstr(x[i, dep0, k] == 0, name=f"sem_retorno_dep0_{i}_{k}")
            for j in [dep0] + clientes:
                model.addConstr(x[depf, j, k] == 0, name=f"sem_saida_depf_{j}_{k}")

        # Cada order e atendida exatamente uma vez.
        for i in clientes:
            model.addConstr(gp.quicksum(visita[i, k] for k in K) == 1, name=f"atende_uma_vez_{i}")

        # Fluxo por navio e vinculo com visita.
        for k in K:
            model.addConstr(gp.quicksum(x[dep0, j, k] for j in clientes + [depf]) == 1, name=f"sai_base_{k}")
            model.addConstr(gp.quicksum(x[i, depf, k] for i in [dep0] + clientes) == 1, name=f"volta_base_{k}")

            for i in clientes:
                model.addConstr(gp.quicksum(x[j, i, k] for j in V if j != i) == visita[i, k], name=f"entrada_{i}_{k}")
                model.addConstr(gp.quicksum(x[i, j, k] for j in V if j != i) == visita[i, k], name=f"saida_{i}_{k}")

        # MTZ: elimina subtours e fornece a posicao de cada order na rota.
        for k in K:
            for i in clientes:
                model.addConstr(ordem[i, k] >= visita[i, k], name=f"ordem_min_{i}_{k}")
                model.addConstr(ordem[i, k] <= inst.nbcd * visita[i, k], name=f"ordem_max_{i}_{k}")

            for i in clientes:
                for j in clientes:
                    if i != j:
                        model.addConstr(ordem[j, k] >= ordem[i, k] + 1 - M_ordem * (1 - x[i, j, k]), name=f"mtz_{i}_{j}_{k}")

        # ------------------------------------------------------------------
        # Cada plataforma forma um unico bloco por navio.
        # ------------------------------------------------------------------
        for p in P:
            nos_p = nos_por_plataforma[p]
            fora_p = [i for i in clientes if plataforma_id[i] != p]

            for k in K:
                entrada_bloco = gp.quicksum(x[i, j, k] for i in [dep0] + fora_p for j in nos_p)
                saida_bloco = gp.quicksum(x[i, j, k] for i in nos_p for j in fora_p + [depf])

                model.addConstr(entrada_bloco == usa_plataforma[p, k], name=f"uma_entrada_plat_{p}_{k}")
                model.addConstr(saida_bloco == usa_plataforma[p, k], name=f"uma_saida_plat_{p}_{k}")
                model.addConstr(usa_plataforma[p, k] <= gp.quicksum(visita[i, k] for i in nos_p), name=f"ativa_plat_{p}_{k}")

                for i in nos_p:
                    model.addConstr(visita[i, k] <= usa_plataforma[p, k], name=f"visita_implica_plat_{i}_{k}")

        # ------------------------------------------------------------------
        # Etapa 3 (modo silva2024): dois navios DIFERENTES nao podem operar na
        # mesma plataforma ao mesmo tempo. Disjuncao Big-M por par de navios e
        # por plataforma: um binario seq_plat[p,k,l] decide se o bloco de k
        # termina antes do bloco de l comecar (ou o inverso), aplicado a TODO
        # par de nos (i em p visitado por k, j em p visitado por l) -- ativa
        # apenas quando AMBOS usa_plataforma[p,k] e usa_plataforma[p,l] sao 1.
        # Nao compara nos do MESMO navio (a ordem dentro do proprio bloco ja e
        # garantida pelo MTZ acima).
        # Guardado tambem por considerar_conflito_plataforma (default True =
        # comportamento identico ao de sempre); False desliga so este bloco.
        # ------------------------------------------------------------------
        if modo_silva and considerar_conflito_plataforma:
            seq_plat = {}
            for p in P:
                nos_p = nos_por_plataforma[p]
                for idx_k in range(len(K)):
                    for idx_l in range(idx_k + 1, len(K)):
                        k, l = K[idx_k], K[idx_l]
                        seq_plat[p, k, l] = model.addVar(vtype=GRB.BINARY, name=f"seq_plat_{p}_{k}_{l}")
                        for i in nos_p:
                            for j in nos_p:
                                model.addConstr(
                                    inicio[i, k] + servico[i] <= inicio[j, l]
                                    + M_tempo * (1 - seq_plat[p, k, l])
                                    + M_tempo * (1 - usa_plataforma[p, k])
                                    + M_tempo * (1 - usa_plataforma[p, l]),
                                    name=f"nao_sobrepos_kl_{p}_{k}_{l}_{i}_{j}"
                                )
                                model.addConstr(
                                    inicio[j, l] + servico[j] <= inicio[i, k]
                                    + M_tempo * seq_plat[p, k, l]
                                    + M_tempo * (1 - usa_plataforma[p, k])
                                    + M_tempo * (1 - usa_plataforma[p, l]),
                                    name=f"nao_sobrepos_lk_{p}_{k}_{l}_{i}_{j}"
                                )

        # Dentro da plataforma, qualquer order com coleta deve vir antes de
        # qualquer order com entrega. Se uma order possui ambos, a coleta e
        # executada antes da entrega dentro da propria order, como no C++.
        for p in P:
            nos_p = nos_por_plataforma[p]
            coletas = [i for i in nos_p if deck_backload[i] > eps]
            if modo_silva:
                # JSON: basicData.pickupDeckBeforeDeliveryDeck=true -- a regra e
                # especificamente "backload de DECK antes de ENTREGA de DECK", nao
                # antes de diesel/agua (confirmado pela rota publicada da Tabela 3,
                # PLAT_6: diesel,agua,backload,deck -- diesel/agua sao entregues
                # ANTES do backload). Regra ampla (Petro) causava INFEASIBLE aqui.
                entregas = [i for i in nos_p if deck_load[i] > eps]
            else:
                entregas = [i for i in nos_p if deck_load[i] > eps or diesel[i] > eps or agua[i] > eps]

            for k in K:
                for c in coletas:
                    for d in entregas:
                        if c == d:
                            continue
                        model.addConstr(ordem[c, k] + 1 <= ordem[d, k] + M_ordem * (2 - visita[c, k] - visita[d, k]), name=f"coleta_antes_entrega_{c}_{d}_{k}")

        # ------------------------------------------------------------------
        # Deck: carga inicial = todas as entregas da rota. Em cada order,
        # coleta primeiro, verifica o pico e entrega depois.
        # ------------------------------------------------------------------
        for k in K:
            Q = cap_deck(k)
            max_b = max((deck_backload[i] for i in clientes), default=0.0)
            max_d = max((deck_load[i] for i in clientes), default=0.0)
            M_carga = float(2.0 * Q + max_b + max_d + 1.0)

            for i in V:
                model.addConstr(carga[i, k] <= Q, name=f"cap_deck_{i}_{k}")

            model.addConstr(carga[dep0, k] == gp.quicksum(deck_load[i] * visita[i, k] for i in clientes), name=f"carga_inicial_{k}")

            for i in [dep0] + clientes:
                for j in clientes + [depf]:
                    if i == j:
                        continue

                    coleta_j = deck_backload[j] if j in clientes else 0.0
                    entrega_j = deck_load[j] if j in clientes else 0.0
                    saldo_j = coleta_j - entrega_j

                    model.addConstr(carga[j, k] >= carga[i, k] + saldo_j - M_carga * (1 - x[i, j, k]), name=f"carga_lb_{i}_{j}_{k}")
                    model.addConstr(carga[j, k] <= carga[i, k] + saldo_j + M_carga * (1 - x[i, j, k]), name=f"carga_ub_{i}_{j}_{k}")

                    if j in clientes:
                        model.addConstr(carga[i, k] + coleta_j <= Q + M_carga * (1 - x[i, j, k]), name=f"pico_antes_entrega_{i}_{j}_{k}")

        # Diesel e agua sao entregas em compartimentos independentes.
        for k in K:
            cap_di = cap_diesel(k)
            cap_ag = cap_agua(k)

            if math.isfinite(cap_di):
                model.addConstr(gp.quicksum(diesel[i] * visita[i, k] for i in clientes) <= cap_di, name=f"cap_diesel_{k}")
            if math.isfinite(cap_ag):
                model.addConstr(gp.quicksum(agua[i] * visita[i, k] for i in clientes) <= cap_ag, name=f"cap_agua_{k}")

        # ------------------------------------------------------------------
        # Multiplas janelas e propagacao temporal.
        # ------------------------------------------------------------------
        for k in K:
            veic = inst.veiculos[k]
            if modo_silva:
                # Disponibilidade estritamente individual (ETR_k): NAO usar a janela
                # compartilhada do no base, que vem de um unico navio de referencia da
                # frota e sobrepoe (max) o ETR de navios com ETR menor -- esse era o
                # bug relatado (janela base=[25200,...] igual para M e L).
                inicio_base = float(veic.readiness)
            else:
                inicio_base = float(janelas[dep0][0][0])
                if hasattr(veic, "readiness"):
                    inicio_base = max(inicio_base, float(veic.readiness))
            # B_k (berco[k]) pode ser >= disponibilidade (fundeio permitido); a partida
            # efetiva P_k=inicio[dep0,k] só ocorre apos o berco de saida (sequencial).
            model.addConstr(berco[k] >= inicio_base, name=f"berco_min_{k}")
            model.addConstr(inicio[dep0, k] == berco[k] + expr_hB_saida_seg[k], name=f"partida_apos_berco_{k}")

            max_partida_k = float(getattr(veic, "max_departure", 0.0))
            if max_partida_k > 0.0 and math.isfinite(max_partida_k):
                model.addConstr(inicio[dep0, k] <= max_partida_k, name=f"max_partida_{k}")

            for i in clientes:
                model.addConstr(gp.quicksum(y[i, k, w] for w in range(len(janelas[i]))) == visita[i, k], name=f"escolhe_janela_{i}_{k}")

                for w, (ready_w, due_w) in enumerate(janelas[i]):
                    model.addConstr(inicio[i, k] >= ready_w - M_tempo * (1 - y[i, k, w]), name=f"janela_ini_{i}_{k}_{w}")
                    model.addConstr(inicio[i, k] + servico[i] <= due_w + M_tempo * (1 - y[i, k, w]), name=f"janela_fim_{i}_{k}_{w}")

                if modo_silva:
                    due_i = order_due_time_seg[i]
                    if due_i is not None:
                        if dp.get("commodities", [None] * inst.nbn)[i] != "deckCargoBackload":
                            # dueTime DELIVERY: servico offshore deve terminar ate
                            # dueTime_i. Restricao ADICIONAL as timeWindows, nao uma
                            # substituicao.
                            model.addConstr(inicio[i, k] + servico[i] <= due_i + M_tempo * (1 - visita[i, k]), name=f"due_time_delivery_{i}_{k}")
                        else:
                            # dueTime PICKUP (restricoes (26)-(32) do artigo, adaptadas
                            # ao modelo de 1 viagem/navio desta instancia): a DESCARGA
                            # na base do backload i deve terminar ate dueTime_i, i.e.
                            # F_k <= dueTime_i (nao FIFO/LIFO individual -- com 1 viagem
                            # por navio, TODOS os pickups do navio k terminam de ser
                            # descarregados no mesmo instante F_k, o fim do bloco
                            # agregado de descarga).
                            model.addConstr(
                                inicio[depf, k] + servico[depf] + expr_hB_retorno_seg[k] <= due_i + M_tempo * (1 - visita[i, k]),
                                name=f"due_time_pickup_{i}_{k}"
                            )

            ready_depf, due_depf = janelas[depf][0]
            model.addConstr(inicio[depf, k] >= ready_depf, name=f"ready_depf_{k}")
            if not modo_silva:
                # due_depf vale sobre F_k = R_k + hB_retorno_seg_k (fim da descarga do
                # backload), nao apenas sobre a chegada R_k=inicio[depf,k]. Em modo
                # silva2024 este limite ABSOLUTO nao se aplica (ver bloco de
                # tripDurationLimit abaixo, que usa F_k-s_k, nao um due absoluto).
                model.addConstr(inicio[depf, k] + servico[depf] + expr_hB_retorno_seg[k] <= due_depf, name=f"due_depf_{k}")

            for i in [dep0] + clientes:
                for j in clientes + [depf]:
                    if i != j:
                        model.addConstr(inicio[j, k] >= inicio[i, k] + servico[i] + tempo_arco(i, j, k) - M_tempo * (1 - x[i, j, k]), name=f"tempo_{i}_{j}_{k}")

            limite_viagem = float(getattr(veic, "trip_duration_limit", 0.0))
            if limite_viagem > 0.0 and math.isfinite(limite_viagem):
                if modo_silva:
                    # Silva et al. (2024): TDL significa F_k - s_k <= TDL_k, com
                    # s_k = berco[k] (instante em que comeca a operacao de berco, NAO
                    # AT_k -- comprovado pela Tabela 3, ex. PSV M com alpha=1:
                    # f-s=88.5<=96 mas f-AT=101.6>96). Substitui devido_depf (absoluto)
                    # e duracao_viagem (R_k-P_k) para este modo -- ambos nao
                    # implementam esta condicao relativa a s_k.
                    model.addConstr(
                        inicio[depf, k] + servico[depf] + expr_hB_retorno_seg[k] - berco[k] <= limite_viagem,
                        name=f"tdl_silva_Fk_menos_sk_{k}"
                    )
                else:
                    model.addConstr(inicio[depf, k] - inicio[dep0, k] <= limite_viagem, name=f"duracao_viagem_{k}")
                    # F_k - AT_k <= tripDurationLimit_k, explicito por navio. due_depf
                    # (acima) usa uma janela ABSOLUTA compartilhada (T_max do navio de
                    # referencia da frota, copiada para o no base/depf), que NAO e
                    # necessariamente igual a AT_k + tripDurationLimit_k de cada navio
                    # individual -- confirmado que due_depf nao implementa esta condicao
                    # relativa em geral, por isso ela e garantida aqui de forma
                    # explicita, sem tocar due_depf nem a FO.
                    AT_k_seg = float(veic.readiness)
                    model.addConstr(
                        inicio[depf, k] + servico[depf] + expr_hB_retorno_seg[k] - AT_k_seg <= limite_viagem,
                        name=f"trip_duration_Fk_{k}"
                    )

        if salvar_modelo:
            model.write(f"modelo_exato_petro_{os.getpid()}.lp")

        model.optimize()

        # ------------------------------------------------------------------
        # Status e bounds do Gurobi.
        # ------------------------------------------------------------------
        status_map = {
            GRB.LOADED: "LOADED",
            GRB.OPTIMAL: "OPTIMAL",
            GRB.INFEASIBLE: "INFEASIBLE",
            GRB.INF_OR_UNBD: "INF_OR_UNBD",
            GRB.UNBOUNDED: "UNBOUNDED",
            GRB.CUTOFF: "CUTOFF",
            GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
            GRB.NODE_LIMIT: "NODE_LIMIT",
            GRB.TIME_LIMIT: "TIME_LIMIT",
            GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
            GRB.INTERRUPTED: "INTERRUPTED",
            GRB.NUMERIC: "NUMERIC",
            GRB.SUBOPTIMAL: "SUBOPTIMAL",
            GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT",
        }

        status_nome = status_map.get(model.Status, f"STATUS_{model.Status}")
        tem_solucao = model.SolCount > 0
        obj = float(model.ObjVal) if tem_solucao else None

        try:
            bound = float(model.ObjBound)
        except Exception:
            bound = None

        try:
            mip_gap = float(model.MIPGap) if tem_solucao else None
        except Exception:
            mip_gap = None

        sol.exato_petro_status = status_nome
        sol.exato_petro_tem_solucao = bool(tem_solucao)
        sol.exato_petro_otimo = bool(model.Status == GRB.OPTIMAL)
        sol.exato_petro_obj = obj
        sol.exato_petro_bound = bound
        sol.exato_petro_gap = mip_gap
        sol.exato_petro_runtime = float(model.Runtime)
        sol.exato_petro_consistente = False
        sol.exato_petro_plataforma_id = list(plataforma_id)
        sol.exato_petro_silva_sp_arcos_base = silva_sp_arcos_base

        gap_txt = "NA" if mip_gap is None or not math.isfinite(mip_gap) else f"{100.0 * mip_gap:.2f}%"
        obj_txt = "NA" if obj is None else f"{obj:.2f}"
        bound_txt = "NA" if bound is None or not math.isfinite(bound) else f"{bound:.2f}"
        print(f"[EXATO_PETRO] status={status_nome} | FO={obj_txt} | bound={bound_txt} | gap={gap_txt} | t={model.Runtime:.1f}s")

        if not tem_solucao:
            sol.custo = -1
            sol.rotas = {}
            print("[EXATO_PETRO] Nenhuma solucao incumbente disponivel.")
            return False

        # ------------------------------------------------------------------
        # Validacao independente, usando exatamente a regra do pricing C++.
        # ------------------------------------------------------------------
        def validar_rota(k, rota):
            if not rota or rota[0] != dep0 or rota[-1] != depf:
                return False, "rota_sem_depositos", []

            vistos = set()
            plataformas_encerradas = set()
            plataforma_atual = None
            entrega_iniciada = False
            clientes_rota = []

            for no in rota:
                if no not in clientes:
                    continue
                if no in vistos:
                    return False, f"order_repetida_{no}", []
                vistos.add(no)
                clientes_rota.append(no)

                p = plataforma_id[no]
                if p != plataforma_atual:
                    if plataforma_atual is not None:
                        plataformas_encerradas.add(plataforma_atual)
                    if p in plataformas_encerradas:
                        return False, f"retorno_plataforma_{plataforma_chave[p]}", []
                    plataforma_atual = p
                    entrega_iniciada = False

                tem_coleta = deck_backload[no] > eps
                # Mesma regra da Etapa 3/JSON (pickupDeckBeforeDeliveryDeck): em modo
                # silva2024, "entrega" para fins de ordenacao coleta-antes-entrega e
                # so deck_load (nao diesel/agua) -- ver bloco de restricoes acima.
                if modo_silva:
                    tem_entrega = deck_load[no] > eps
                else:
                    tem_entrega = deck_load[no] > eps or diesel[no] > eps or agua[no] > eps
                if tem_coleta and entrega_iniciada:
                    return False, f"coleta_depois_entrega_no_{no}", []
                if tem_entrega:
                    entrega_iniciada = True

            Q = cap_deck(k)
            deck = sum(deck_load[i] for i in clientes_rota)
            diesel_total = sum(diesel[i] for i in clientes_rota)
            agua_total = sum(agua[i] for i in clientes_rota)

            if deck > Q + 1e-6:
                return False, f"carga_inicial_deck_{deck:.6f}_maior_{Q:.6f}", []
            if math.isfinite(cap_diesel(k)) and diesel_total > cap_diesel(k) + 1e-6:
                return False, "capacidade_diesel", []
            if math.isfinite(cap_agua(k)) and agua_total > cap_agua(k) + 1e-6:
                return False, "capacidade_agua", []

            if modo_silva:
                # Mesma correcao do item 5: ETR individual, sem max() com a janela
                # compartilhada do no base.
                tempo = float(inst.veiculos[k].readiness)
            else:
                tempo = float(janelas[dep0][0][0])
                if hasattr(inst.veiculos[k], "readiness"):
                    tempo = max(tempo, float(inst.veiculos[k].readiness))
            partida = tempo
            diagnostico_carga = []

            for pos in range(len(rota) - 1):
                i = rota[pos]
                j = rota[pos + 1]
                chegada = tempo + servico[i] + tempo_arco(i, j, k)

                inicio_j = None
                if modo_silva and j == depf:
                    # Espelha a Gurobi: due_depf (janela ABSOLUTA de 96h, copiada do
                    # navio de referencia) foi propositalmente desativado no modelo
                    # para este modo (ver bloco tdl_silva_Fk_menos_sk_{k}), entao a
                    # checagem generica de janela nao deve reimpor esse limite aqui --
                    # so o piso ready_depf continua valendo.
                    inicio_j = max(chegada, janelas[j][0][0])
                else:
                    for ready_w, due_w in janelas[j]:
                        candidato = max(chegada, ready_w)
                        if candidato + servico[j] <= due_w + 1e-6:
                            inicio_j = candidato
                            break

                if inicio_j is None:
                    return False, f"janela_no_{j}", diagnostico_carga
                tempo = inicio_j

                if j in clientes:
                    antes = deck
                    coleta = deck_backload[j]
                    pico = antes + coleta
                    entrega = deck_load[j]
                    depois = pico - entrega

                    diagnostico_carga.append({
                        "no": j,
                        "plataforma": plataforma_chave[plataforma_id[j]],
                        "carga_antes": antes,
                        "coleta": coleta,
                        "pico": pico,
                        "entrega": entrega,
                        "carga_depois": depois,
                        "inicio_servico": inicio_j,
                    })

                    if pico > Q + 1e-6:
                        return False, f"pico_deck_no_{j}_{pico:.6f}_maior_{Q:.6f}", diagnostico_carga
                    if depois < -1e-6:
                        return False, f"carga_negativa_no_{j}", diagnostico_carga
                    deck = depois

            limite = float(getattr(inst.veiculos[k], "trip_duration_limit", 0.0))
            if modo_silva:
                # Espelha a restricao tdl_silva_Fk_menos_sk_{k}: F_k - s_k <= TDL,
                # com s_k = berco[k] ja resolvido pelo Gurobi (nao AT_k/partida).
                s_k = berco[k].X
                if limite > 0.0 and tempo - s_k > limite + 1e-6:
                    return False, "duracao_viagem", diagnostico_carga
            elif limite > 0.0 and tempo - partida > limite + 1e-6:
                return False, "duracao_viagem", diagnostico_carga

            return True, "ok", diagnostico_carga

        rotas_tmp = {}
        todos_atendidos = []
        consistente = True
        custo_reconstruido = 0.0

        # Acumuladores da frota para o relatorio da FO ambiental Petro.
        D_total = E_total = T_total = amb_total = temp_total = 0.0
        TOL_FECHAMENTO_H = 1e-3  # tolerancia (horas) da checagem T_k ~= hF+hB+hN+hDP

        # Diagnostico programatico (modo silva2024): espelha os valores ja
        # impressos em [FO_PETRO], por navio, para consumo por testes de
        # reproducao (ex.: Tabela 3), sem alterar formulacao/comportamento.
        sol.exato_petro_silva_diag = {}

        for k in K:
            rota = [dep0]
            atual = dep0
            usados_na_reconstrucao = {dep0}

            for _ in range(inst.nbn + 2):
                proximos = [j for j in V if j != atual and x[atual, j, k].X > 0.5]
                if len(proximos) != 1:
                    consistente = False
                    print(f"[EXATO_PETRO][ERRO] k={k}: no {atual} possui {len(proximos)} sucessores ativos: {proximos}")
                    break

                proximo = proximos[0]
                rota.append(proximo)
                if proximo == depf:
                    break
                if proximo in usados_na_reconstrucao:
                    consistente = False
                    print(f"[EXATO_PETRO][ERRO] k={k}: ciclo durante reconstrucao em {proximo}")
                    break
                usados_na_reconstrucao.add(proximo)
                atual = proximo

            if rota[-1] != depf:
                consistente = False

            valida, motivo, diag = validar_rota(k, rota)

            # Usa tambem a validacao atualizada de Solucao quando ela estiver
            # disponivel. A checagem de plataforma_petro distingue a versao nova
            # da antiga validacao conservadora que somava load + backload.
            if valida and hasattr(sol, "plataforma_petro") and hasattr(sol, "viavel_cargas_petro"):
                try:
                    if not sol.viavel_cargas_petro(inst, k, rota):
                        valida = False
                        motivo = "viavel_cargas_petro_rejeitou"
                except Exception as exc:
                    valida = False
                    motivo = f"erro_viavel_cargas_petro:{exc}"

            if valida and hasattr(sol, "ordem_plataformas_petro_valida"):
                try:
                    if not sol.ordem_plataformas_petro_valida(inst, rota):
                        valida = False
                        motivo = "ordem_plataformas_petro_valida_rejeitou"
                except Exception as exc:
                    valida = False
                    motivo = f"erro_ordem_plataformas:{exc}"

            # custo_rota = FO ambiental+temporal do navio k (mesmas expressoes da
            # funcao objetivo), avaliada nos valores da solucao do Gurobi.
            custo_rota = alpha_fo * expr_E[k].getValue() + (1.0 - alpha_fo) * eta_fo * expr_T[k].getValue()
            custo_reconstruido += custo_rota
            clientes_k = [i for i in rota if i in clientes]
            todos_atendidos.extend(clientes_k)

            binaria = [0] * inst.nbcd
            for i in clientes_k:
                binaria[i - 1] = 1

            rotas_tmp[k] = {
                "rotas_binaria": [binaria],
                "sequencia_rota": [rota],
                "custo": [custo_rota],
                "vezes_usada_geral": [0],
                "vezes_usada_otimo": [0],
                "lbd_iteracao": [[]],
                "artificial": [False],
            }

            print(f"[EXATO_PETRO] Navio {k} | rota={rota} | custo={custo_rota:.2f} | valida={valida} | motivo={motivo}")
            if diagnostico:
                print("  no | plataforma | antes | coleta | pico | entrega | depois")
                for item in diag:
                    print(f"  {item['no']:>2} | {item['plataforma']:<12} | {item['carga_antes']:>7.2f} | {item['coleta']:>7.2f} | {item['pico']:>7.2f} | {item['entrega']:>7.2f} | {item['carga_depois']:>7.2f}")

            # ---- Relatorio da FO ambiental Petro, apenas para navios utilizados ----
            if clientes_k:
                veic = inst.veiculos[k]
                hF_v = expr_hF[k].getValue()
                hB_v = expr_hB[k].getValue()
                hN_v = expr_hN[k].getValue()
                hDP_v = expr_hDP[k].getValue()
                T_v = expr_T[k].getValue()
                D_v = expr_D[k].getValue()
                E_v = expr_E[k].getValue()
                amb_v = alpha_fo * E_v
                temp_v = (1.0 - alpha_fo) * eta_fo * T_v
                custo_v = amb_v + temp_v

                fecha = hF_v + hB_v + hN_v + hDP_v
                alerta = "" if abs(T_v - fecha) <= TOL_FECHAMENTO_H else \
                    f"  *** ALERTA: T_k={T_v:.4f} difere de hF+hB+hN+hDP={fecha:.4f} ***"

                print(f"[FO_PETRO] Navio {k} | hF={hF_v:.4f}h hB={hB_v:.4f}h hN={hN_v:.4f}h hDP={hDP_v:.4f}h | T={T_v:.4f}h{alerta}")

                # AT_k local (nao reusar a variavel de mesmo nome do laco da FO acima:
                # aquela "vaza" com o valor do ULTIMO navio do laco, por escopo de
                # funcao do Python -- bug pre-existente, corrigido aqui).
                AT_k_h = float(veic.readiness) / SEGUNDOS_POR_HORA
                B_v = berco[k].X / SEGUNDOS_POR_HORA
                P_v = inicio[dep0, k].X / SEGUNDOS_POR_HORA
                R_v = inicio[depf, k].X / SEGUNDOS_POR_HORA
                F_v = R_v + expr_hB_retorno_seg[k].getValue() / SEGUNDOS_POR_HORA
                print(f"[FO_PETRO] Navio {k} | AT_k={AT_k_h:.4f}h B_k={B_v:.4f}h "
                      f"P_k={P_v:.4f}h R_k={R_v:.4f}h F_k={F_v:.4f}h")

                servico_seg = sum(servico[rota[pos]] for pos in range(len(rota) - 1) if rota[pos] in clientes)
                servico_h = servico_seg / SEGUNDOS_POR_HORA

                if modo_silva:
                    # Decomposicao de hDP_k (modo silva2024): SET (setup por
                    # plataforma) + SP (safe positioning do navio), cobrados uma vez
                    # por visita a plataforma nova (mesmo criterio de tempo_arco) +
                    # servico + espera (residual). setupArrival/setupDeparture nao
                    # existem nos arcos deste modo (0.0 no JSON): SET+SP fazem esse
                    # papel, por isso nao hah "setup_offshore" via tempo_viagem aqui.
                    set_total_seg = 0.0
                    sp_total_seg = 0.0
                    for pos in range(len(rota) - 1):
                        a, b = rota[pos], rota[pos + 1]
                        if b in clientes and plataforma_id[a] != plataforma_id[b]:
                            set_total_seg += set_por_plataforma.get(plataforma_id[b], 0.0)
                            if silva_sp_arcos_base or a != dep0:
                                sp_total_seg += float(veic.safe_positioning_time)
                    set_total_h = set_total_seg / SEGUNDOS_POR_HORA
                    sp_total_h = sp_total_seg / SEGUNDOS_POR_HORA
                    espera_h = hDP_v - set_total_h - sp_total_h - servico_h
                    print(f"[FO_PETRO] Navio {k} | hDP decomposto: SET={set_total_h:.4f}h "
                          f"SP={sp_total_h:.4f}h servico={servico_h:.4f}h espera(residual)={espera_h:.4f}h")

                    # Confirmacao explicita de F_k - s_k <= tripDurationLimit_k (s_k=B_k).
                    limite_viagem_h = float(getattr(veic, "trip_duration_limit", 0.0)) / SEGUNDOS_POR_HORA
                    folga_trip = limite_viagem_h - (F_v - B_v)
                    print(f"[FO_PETRO] Navio {k} | tripDurationLimit={limite_viagem_h:.4f}h | "
                          f"F_k-s_k={F_v - B_v:.4f}h | folga={folga_trip:.4f}h")

                    print(f"[FO_PETRO] Navio {k} | FCA(theta)={veic.cost_anchored:.4f} FCB(varphi)={veic.cost_base:.4f} "
                          f"FCN(gamma)={veic.cost_navigation:.4f} FCS(delta)={veic.cost_dynamic:.4f} (USD/h)")
                    termo_base_v = expr_termo_base[k].getValue()
                    termo_nav_v = expr_termo_nav[k].getValue()
                    termo_serv_v = expr_termo_serv[k].getValue()
                    print(f"[FO_PETRO] Navio {k} | f1 marginal (custo relativo ao fundeio, theta=FCA): "
                          f"termo_base=(FCB-FCA)*hB={termo_base_v:.4f} | "
                          f"termo_navegacao=(FCN-FCA)*hN={termo_nav_v:.4f} | "
                          f"termo_servico=(FCS-FCA)*hDP={termo_serv_v:.4f} | f1_k={D_v:.4f} USD")
                    print(f"[FO_PETRO] Navio {k} | alpha*f1_k={amb_v:.4f} USD | "
                          f"(1-alpha)*eta*xi_k*T_k={temp_v:.4f} (xi_k=1, NAO CONFIRMADO -- ver ETAPA 5) | "
                          f"custo_total={custo_v:.4f}")

                    # Cronologia por order (read-only, so leitura dos valores JA
                    # resolvidos pelo Gurobi -- inicio[j,k].X -- NUNCA recalcula B=AT;
                    # usada pelo PlotJS Silva para desenhar o Gantt sem duplicar a
                    # formula fisica em solucao.py. Mesmo shape (chaves) do retorno de
                    # avaliar_rota_silva2024()["cronologia"], para o consumidor tratar
                    # as duas fontes de forma uniforme. Nenhuma restricao/variavel nova.
                    cronologia_gurobi = []
                    for pos in range(len(rota) - 1):
                        a, b = rota[pos], rota[pos + 1]
                        if b == depf:
                            cronologia_gurobi.append({
                                "evento": "retorno_base", "de": a, "para": b,
                                "chegada_h": R_v,
                            })
                            continue
                        inicio_b_h = inicio[b, k].X / SEGUNDOS_POR_HORA
                        chegada_b_h = (inicio[a, k].X + servico[a]) / SEGUNDOS_POR_HORA + tempo_arco(a, b, k) / SEGUNDOS_POR_HORA
                        fim_b_h = inicio_b_h + servico[b] / SEGUNDOS_POR_HORA
                        espera_b_h = inicio_b_h - chegada_b_h

                        janela_idx = None
                        for widx, (rd_seg, du_seg) in enumerate(janelas.get(b, [])):
                            if inicio_b_h >= rd_seg / SEGUNDOS_POR_HORA - 1e-6 and fim_b_h <= du_seg / SEGUNDOS_POR_HORA + 1e-6:
                                janela_idx = widx
                                break

                        cronologia_gurobi.append({
                            "no": b, "chegada_h": chegada_b_h, "espera_h": espera_b_h,
                            "inicio_h": inicio_b_h, "fim_h": fim_b_h, "janela_idx": janela_idx,
                        })

                    # Diagnostico programatico (so modo silva2024): espelha os
                    # valores acima ja impressos, para consumo por testes de
                    # reproducao (ex.: Tabela 3), sem alterar formulacao/comportamento.
                    sol.exato_petro_silva_diag[k] = {
                        "AT": AT_k_h, "B": B_v, "P": P_v, "R": R_v, "F": F_v,
                        "dur": F_v - B_v,
                        "hF": hF_v, "hB": hB_v, "hN": hN_v, "hDP": hDP_v,
                        "hB_saida": expr_hB_saida_seg[k].getValue() / SEGUNDOS_POR_HORA,
                        "hB_retorno": expr_hB_retorno_seg[k].getValue() / SEGUNDOS_POR_HORA,
                        "SET": set_total_h, "SP": sp_total_h,
                        "servico": servico_h, "espera": espera_h,
                        "f1": D_v, "f2": T_v,
                        "termo_base": termo_base_v, "termo_nav": termo_nav_v, "termo_serv": termo_serv_v,
                        "silva_sp_arcos_base": silva_sp_arcos_base,
                        "cronologia": cronologia_gurobi,
                    }
                else:
                    # Decomposicao de hDP_k (modo petrobras) em setup offshore + servico
                    # + espera (residual). setupArrival do arco base->1a plataforma e
                    # setupDeparture do arco ultima plataforma->base ocorrem
                    # FISICAMENTE na plataforma (manobra de atracacao/desatracacao la,
                    # nao na base -- confirmado em leitura_petro_dados: "if i==0:
                    # t+=setup_arr" e "elif j==0: t+=setup_dep" sao sempre eventos do
                    # lado da plataforma). Por isso TODOS os arcos da rota entram no
                    # setup_offshore, inclusive os que tocam dep0/depf.
                    setup_offshore_seg = sum(
                        tempo_viagem(rota[pos], rota[pos + 1], k) - tempo_navegacao_pura(rota[pos], rota[pos + 1], k)
                        for pos in range(len(rota) - 1)
                    )
                    setup_offshore_h = setup_offshore_seg / SEGUNDOS_POR_HORA
                    espera_h = hDP_v - setup_offshore_h - servico_h
                    print(f"[FO_PETRO] Navio {k} | hDP decomposto: setup_offshore={setup_offshore_h:.4f}h "
                          f"servico={servico_h:.4f}h espera(residual)={espera_h:.4f}h")

                    # Confirmacao explicita de F_k - AT_k <= tripDurationLimit_k.
                    limite_viagem_h = float(getattr(veic, "trip_duration_limit", 0.0)) / SEGUNDOS_POR_HORA
                    folga_trip = limite_viagem_h - (F_v - AT_k_h)
                    print(f"[FO_PETRO] Navio {k} | tripDurationLimit={limite_viagem_h:.4f}h | "
                          f"F_k-AT_k={F_v - AT_k_h:.4f}h | folga={folga_trip:.4f}h")

                    print(f"[FO_PETRO] Navio {k} | theta={veic.fuel_anchored:.4f} varphi={veic.fuel_base:.4f} "
                          f"gamma={veic.fuel_navigation:.4f} delta={veic.fuel_dynamic:.4f} (m3/h)")
                    print(f"[FO_PETRO] Navio {k} | consumo_fundeio={veic.fuel_anchored * hF_v:.4f} "
                          f"consumo_berco={veic.fuel_base * hB_v:.4f} consumo_navegacao={veic.fuel_navigation * hN_v:.4f} "
                          f"consumo_DP={veic.fuel_dynamic * hDP_v:.4f} | D_k={D_v:.4f} m3 | E_k={E_v:.4f} tCO2eq")
                    print(f"[FO_PETRO] Navio {k} | ambiental=alpha*E_k={amb_v:.4f} | "
                          f"temporal=(1-alpha)*eta*T_k={temp_v:.4f} | custo_total={custo_v:.4f}")

                D_total += D_v
                E_total += E_v
                T_total += T_v
                amb_total += amb_v
                temp_total += temp_v

            if not valida:
                consistente = False

        print("-" * 78)
        if modo_silva:
            print(f"[FO_PETRO] FROTA | custo_direto_total(f1)={D_total:.4f} USD | "
                  f"tempo_total(xi)={T_total:.4f} h | alpha*f1={amb_total:.4f} USD | "
                  f"(1-alpha)*eta*soma(xi)={temp_total:.4f} | FO_total={amb_total + temp_total:.4f}")
        else:
            print(f"[FO_PETRO] FROTA | consumo_total={D_total:.4f} m3 | emissoes_totais={E_total:.4f} tCO2eq | "
                  f"tempo_total={T_total:.4f} h | componente_ambiental={amb_total:.4f} | "
                  f"componente_temporal={temp_total:.4f} | FO_total={amb_total + temp_total:.4f}")

        if sorted(todos_atendidos) != clientes:
            consistente = False
            print(f"[EXATO_PETRO][ERRO] orders atendidas={sorted(todos_atendidos)} | esperado={clientes}")

        if obj is not None and abs(custo_reconstruido - obj) > 1e-4:
            consistente = False
            print(f"[EXATO_PETRO][ERRO] FO reconstruida={custo_reconstruido:.6f} difere de ObjVal={obj:.6f}")

        sol.exato_petro_rotas_brutas = rotas_tmp
        sol.exato_petro_consistente = bool(consistente)

        if not consistente:
            sol.custo = -1
            sol.rotas = {}
            print("[EXATO_PETRO] Solucao do Gurobi rejeitada pela validacao operacional.")
            return False

        sol.rotas = rotas_tmp
        sol.numero_de_rotas = [1] * inst.nbv
        sol.custo = float(obj)

        # Componentes da FO ambiental+temporal (mesmos totais ja usados acima na
        # checagem/impressao [FO_PETRO] FROTA), para consumo pela main sem recalculo.
        sol.exato_petro_consumo_total = D_total
        sol.exato_petro_emissoes_total = E_total
        sol.exato_petro_tempo_total = T_total
        sol.exato_petro_componente_ambiental = amb_total
        sol.exato_petro_componente_temporal = temp_total
        sol.exato_petro_alpha = alpha_fo
        sol.exato_petro_eta = eta_fo
        sol.exato_petro_chi = chi_fo

        print("[EXATO_PETRO] Solucao operacionalmente valida.")
        return True

    # ======================================================================
    # SILVA 2024 -- avaliacao de rota fixa (funcoes NOVAS e ISOLADAS).
    #
    # Nao chamam nem alteram metodo_exato_petro, metodo_exato (Solomon), B&P
    # (branch_and_price_global, resolver_no_com_pool, mestre), pricing Python
    # ou C++, construtivas, estabilizacao, branching ou avaliador_rota.py.
    #
    # Reproduzem, para UMA rota fixa de UM navio, exatamente a mesma
    # interpretacao fisica que metodo_exato_petro usa hoje no modo
    # objectiveMode="silva2024" (mesma formula de navegacao piecewise por
    # navio, mesmo SP/SET por entrada de plataforma nova, mesmo carregamento/
    # descarga na base, mesmas regras de dueTime, TDL=F-s e capacidade).
    # Nao usar para pricing/B&P ainda -- so avaliacao isolada de rota fixa.
    # ======================================================================
    def avaliar_rota_silva2024(self, inst, k, seq, diagnostico=False, silva_sp_arcos_base=True):
        """
        Avalia viabilidade e custo de uma rota FIXA de um navio k, no modo
        silva2024. seq = rota completa, incluindo dep0 (0) e depf (nbn-1),
        ex.: [0, 10, 15].

        silva_sp_arcos_base (default True -- IDENTICO ao comportamento
        historico desta funcao): mesma chave/semantica de
        Metodos.metodo_exato_petro -- controla so a perna de SAIDA da base
        (base->1a plataforma), que carrega SP+SET quando True (literal) ou
        so SET quando False (convencao observada na Tabela 3 do benchmark
        Silva). A perna de retorno plataforma->base nunca teve SP/SET, com
        ou sem esta chave. O B&P (pricing_silva2024) continua chamando esta
        funcao com o default True nesta etapa.

        Retorna um dict:
        {
            "viavel": bool, "motivo": str,
            "custo": float, "f1": float, "f2": float, "xi_usado": float,
            "AT": h, "B": h, "P": h, "R": h, "F": h,
            "hB_saida": h, "hB_retorno": h, "hB": h, "hN": h, "hDP": h,
            "espera": h, "janelas_usadas": {no: {...}}, "cronologia": [...],
        }
        Tempos agregados no retorno em HORAS; internamente tudo em segundos.
        """
        if not hasattr(inst, "dados_petro"):
            raise ValueError("avaliar_rota_silva2024 exige uma instancia carregada por leitura_petro")
        if getattr(inst, "objective_mode", "petrobras") != "silva2024":
            raise ValueError("avaliar_rota_silva2024 e exclusiva do modo objectiveMode=silva2024")

        dp = inst.dados_petro
        dep0 = 0
        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))
        eps = 1e-6
        SEG_H = 3600.0
        veic = inst.veiculos[k]

        if seq[0] != dep0 or seq[-1] != depf:
            return {"viavel": False, "motivo": "rota_sem_depositos", "cronologia": []}

        clientes_rota = [i for i in seq if i not in (dep0, depf)]
        if len(set(clientes_rota)) != len(clientes_rota):
            return {"viavel": False, "motivo": "order_repetida", "cronologia": []}
        if any(i not in clientes for i in clientes_rota):
            return {"viavel": False, "motivo": "no_invalido_na_rota", "cronologia": []}

        # ---- plataformas: MESMA regra usada em metodo_exato_petro ----
        nomes = list(dp.get("nomes", []))
        plataforma_id = [-1] * inst.nbn
        mapa_plataformas = {}
        plataforma_chave = {}
        nos_por_plataforma = {}
        for i in clientes:
            nome = str(nomes[i]) if i < len(nomes) else ""
            if "_order_" in nome:
                chave = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                chave = nome.split("_order", 1)[0]
            elif nome:
                chave = nome
            else:
                lat = round(float(dp.get("lat", [0.0] * inst.nbn)[i]), 6)
                lon = round(float(dp.get("lon", [0.0] * inst.nbn)[i]), 6)
                chave = f"{lat:.6f},{lon:.6f}"
            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)
            p = mapa_plataformas[chave]
            plataforma_id[i] = p
            plataforma_chave[p] = chave
            nos_por_plataforma.setdefault(p, []).append(i)

        # ---- dados por order (mesmo fallback dado_no de metodo_exato_petro) ----
        def dado_no(i, atributo, chave):
            valor_no = getattr(inst.noh[i], atributo, None)
            if valor_no is not None:
                return float(valor_no)
            vetor = dp.get(chave, [])
            return float(vetor[i]) if i < len(vetor) else 0.0

        deck_load = {i: dado_no(i, "DEMAND_DECK_LOAD", "dem_deck_load") for i in clientes_rota}
        deck_backload = {i: dado_no(i, "DEMAND_DECK_BACKLOAD", "dem_deck_backload") for i in clientes_rota}
        diesel = {i: dado_no(i, "DEMAND_DIESEL", "dem_diesel") for i in clientes_rota}
        agua = {i: dado_no(i, "DEMAND_AGUA", "dem_agua") for i in clientes_rota}
        servico = {i: float(inst.noh[i].SERVICE_TIME[0]) if getattr(inst.noh[i], "SERVICE_TIME", None) else 0.0 for i in range(inst.nbn)}

        tempo_carreg_deck = dp.get("tempo_carreg_deck", [0.0] * inst.nbn)
        tempo_carreg_diesel = dp.get("tempo_carreg_diesel", [0.0] * inst.nbn)
        tempo_carreg_agua = dp.get("tempo_carreg_agua", [0.0] * inst.nbn)
        tempo_descarreg_backload = dp.get("tempo_descarreg_backload", [0.0] * inst.nbn)
        platform_setup_seg = dp.get("platform_setup_seg", [0.0] * inst.nbn)
        order_due_time_seg = dp.get("order_due_time_seg", [None] * inst.nbn)
        commodities = dp.get("commodities", [None] * inst.nbn)

        # ---- SET por plataforma (mesma checagem de uniformidade de metodo_exato_petro) ----
        set_por_plataforma = {}
        for p, nos_p in nos_por_plataforma.items():
            valores = {float(platform_setup_seg[i]) for i in nos_p}
            set_por_plataforma[p] = max(valores) if valores else 0.0

        # ---- navegacao pura por navio (MESMA formula de tempo_navegacao_silva) ----
        def dist_km(i, j):
            ii = 0 if i == depf else i
            jj = 0 if j == depf else j
            return float(dp["dist"][ii][jj])

        def nav_pura_seg(i, j):
            d = dist_km(i, j)
            if d == 0.0:
                return 0.0
            vs = veic.velocities
            vl = min(vs, key=lambda v: v["above"])["speed"]
            vh = max(vs, key=lambda v: v["above"])["speed"]
            th = max(vs, key=lambda v: v["above"])["above"]
            n = d / vl if d <= th else th / vl + (d - th) / vh
            return n * SEG_H

        def tempo_arco(i, j):
            # MESMA regra de tempo_arco: SET so na entrada de uma plataforma NOVA
            # (inclusive vindo da base); nunca voltando para a base. SP idem,
            # EXCETO na perna de saida da base quando silva_sp_arcos_base=False.
            t = nav_pura_seg(i, j)
            if j not in (dep0, depf):
                pi = plataforma_id[i] if i not in (dep0, depf) else -1
                pj = plataforma_id[j]
                if pi != pj:
                    t += set_por_plataforma.get(pj, 0.0)
                    if silva_sp_arcos_base or i != dep0:
                        t += float(veic.safe_positioning_time)
            return t

        # ---- capacidades individuais do navio ----
        Q = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel_k = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua_k = float(getattr(veic, "cap_agua", float("inf")))

        deck_total = sum(deck_load.values())
        diesel_total = sum(diesel.values())
        agua_total = sum(agua.values())

        if deck_total > Q + eps:
            return {"viavel": False, "motivo": f"capacidade_deck_{deck_total:.4f}_maior_{Q:.4f}", "cronologia": []}
        if math.isfinite(cap_diesel_k) and diesel_total > cap_diesel_k + eps:
            return {"viavel": False, "motivo": "capacidade_diesel", "cronologia": []}
        if math.isfinite(cap_agua_k) and agua_total > cap_agua_k + eps:
            return {"viavel": False, "motivo": "capacidade_agua", "cronologia": []}

        # ---- bloco unico por plataforma + coleta de DECK antes de entrega de DECK ----
        # (regra estreita Silva: diesel/agua NAO entram nesta precedencia --
        # ver pickupDeckBeforeDeliveryDeck no JSON e correcao ja feita em
        # metodo_exato_petro; diesel/agua sao tratados so por dueTime/janela.)
        plataforma_atual = None
        plataformas_encerradas = set()
        entrega_deck_iniciada = False
        for no in clientes_rota:
            p = plataforma_id[no]
            if p != plataforma_atual:
                if plataforma_atual is not None:
                    plataformas_encerradas.add(plataforma_atual)
                if p in plataformas_encerradas:
                    return {"viavel": False, "motivo": f"retorno_plataforma_{plataforma_chave[p]}", "cronologia": []}
                plataforma_atual = p
                entrega_deck_iniciada = False
            tem_coleta = deck_backload[no] > eps
            tem_entrega_deck = deck_load[no] > eps
            if tem_coleta and entrega_deck_iniciada:
                return {"viavel": False, "motivo": f"coleta_depois_entrega_deck_no_{no}", "cronologia": []}
            if tem_entrega_deck:
                entrega_deck_iniciada = True

        # ---- cronologia ----
        AT = float(veic.readiness)
        hB_saida_seg = sum(tempo_carreg_deck[i] + tempo_carreg_diesel[i] + tempo_carreg_agua[i] for i in clientes_rota)
        hB_retorno_seg = sum(tempo_descarreg_backload[i] for i in clientes_rota if commodities[i] == "deckCargoBackload")

        # B_k (berco/inicio da operacao de saida) comeca em AT_k para simular
        # a cronologia -- e o minimo possivel, nunca atrasa nada a jusante.
        # So DEPOIS de calcular F_k (abaixo) e que decidimos se e preciso
        # atrasar B_k (dentro da folga de espera/janela ja existente na rota)
        # para caber no tripDurationLimit, exatamente como o compacto faz com
        # berco[k] livre (>= AT_k) -- ver Silva et al. (2024) Tabela 3 e a
        # restricao tdl_silva_Fk_menos_sk em metodo_exato_petro (TDL usa
        # F_k-B_k, nao F_k-AT_k; o bloco de TDL mais abaixo reproduz isso).
        B = AT
        P = B + hB_saida_seg

        max_partida_k = float(getattr(veic, "max_departure", 0.0))
        if max_partida_k > 0.0 and math.isfinite(max_partida_k) and P > max_partida_k + eps:
            return {"viavel": False, "motivo": "max_partida_excedida", "cronologia": []}

        cronologia = []
        janelas_usadas = {}
        espera_total = 0.0
        # forward time slack (Savelsbergh): min_j (espera acumulada ate j +
        # margem ate o due da janela ativa em j) -- quanto B_k pode atrasar
        # sem violar NENHUMA janela/dueTime offshore da rota (nao tem nada a
        # ver com TDL por si so; e usado abaixo so como um dos limites de
        # delta_max, junto com espera_total e max_departure).
        margem_janela_min = float("inf")
        deck_atual = deck_total  # carga inicial = toda a entrega da rota (pre-carregada)
        if deck_atual > Q + eps:
            return {"viavel": False, "motivo": f"pico_deck_inicial_{deck_atual:.4f}_maior_{Q:.4f}", "cronologia": []}

        tempo = P
        for pos in range(len(seq) - 1):
            i, j = seq[pos], seq[pos + 1]

            if j == depf:
                t_arco = nav_pura_seg(i, j)  # sem SP/SET voltando para a base
                chegada = tempo + servico.get(i, 0.0) + t_arco
                if chegada < tempo - 1e-9:
                    return {"viavel": False, "motivo": "tempo_retrocedeu_retorno", "cronologia": cronologia}
                cronologia.append({"evento": "retorno_base", "de": i, "para": j, "chegada_h": chegada / SEG_H})
                tempo = chegada
                continue

            t_arco = tempo_arco(i, j)
            chegada = tempo + servico.get(i, 0.0) + t_arco
            if chegada < tempo - 1e-9:
                return {"viavel": False, "motivo": f"tempo_retrocedeu_{i}_{j}", "cronologia": cronologia}

            ready_list = list(getattr(inst.noh[j], "READY_TIME", []) or [])
            due_list = list(getattr(inst.noh[j], "DUE_DATE", []) or [])
            inicio_j = None
            widx_sel = None
            for widx, (ready_w, due_w) in enumerate(zip(ready_list, due_list)):
                candidato = max(chegada, ready_w)
                if candidato + servico.get(j, 0.0) <= due_w + eps:
                    inicio_j = candidato
                    widx_sel = widx
                    break
            if inicio_j is None:
                return {"viavel": False, "motivo": f"janela_no_{j}", "cronologia": cronologia}

            espera = inicio_j - chegada
            espera_total += espera
            fim_j = inicio_j + servico.get(j, 0.0)

            # margem ate o due da janela ativa neste no, contando com o que
            # ja foi absorvido de espera ate aqui (inclusive) -- ver
            # margem_janela_min acima.
            margem_j = due_list[widx_sel] - servico.get(j, 0.0) - inicio_j
            margem_janela_min = min(margem_janela_min, espera_total + margem_j)

            due_j = order_due_time_seg[j] if j < len(order_due_time_seg) else None
            if due_j is not None and commodities[j] != "deckCargoBackload":
                if fim_j > due_j + eps:
                    return {"viavel": False, "motivo": f"dueTime_delivery_no_{j}", "cronologia": cronologia}

            if deck_backload[j] > eps or deck_load[j] > eps:
                antes = deck_atual
                coleta = deck_backload[j]
                pico = antes + coleta
                entrega = deck_load[j]
                depois = pico - entrega
                if pico > Q + eps:
                    return {"viavel": False, "motivo": f"pico_deck_no_{j}_{pico:.4f}_maior_{Q:.4f}", "cronologia": cronologia}
                if depois < -eps:
                    return {"viavel": False, "motivo": f"carga_negativa_no_{j}", "cronologia": cronologia}
                deck_atual = depois

            janelas_usadas[j] = {
                "indice": widx_sel,
                "ready_h": ready_list[widx_sel] / SEG_H if widx_sel is not None else None,
                "due_h": due_list[widx_sel] / SEG_H if widx_sel is not None else None,
                "espera_h": espera / SEG_H,
            }
            cronologia.append({
                "no": j, "chegada_h": chegada / SEG_H, "espera_h": espera / SEG_H,
                "inicio_h": inicio_j / SEG_H, "fim_h": fim_j / SEG_H, "janela_idx": widx_sel,
            })

            # tempo carrega o INICIO do servico (nao o fim); servico[i] e somado
            # uma unica vez no "chegada=" da proxima iteracao (i vira o no atual).
            tempo = inicio_j

        R = tempo
        F = R + hB_retorno_seg

        # dueTime PICKUP: F_k <= dueTime_i para cada pickup da rota (Etapa 2/item4)
        for i in clientes_rota:
            if commodities[i] == "deckCargoBackload":
                due_i = order_due_time_seg[i] if i < len(order_due_time_seg) else None
                if due_i is not None and F > due_i + eps:
                    return {"viavel": False, "motivo": f"dueTime_pickup_no_{i}", "cronologia": cronologia}

        # TDL: F_k - B_k <= tripDurationLimit_k, com B_k=berco[k] LIVRE (>=
        # AT_k), igual ao compacto (Silva et al. 2024, Tabela 3: F-s<=TDL mas
        # F-AT>TDL e viavel).
        #
        # ---- 1) intervalo factivel de atraso de B_k: [delta_min, delta_max] ----
        # delta_min: atraso MINIMO de B_k para satisfazer o TDL (F_k-B_k<=TDL).
        # F_k, R_k, hB_k, hN_k, T_k=F_k-AT_k NAO mudam com o atraso de B_k
        # enquanto ele for absorvido pela espera de janela ja existente a
        # jusante -- so P_k=B_k+hB_saida_seg cresce.
        tdl = float(getattr(veic, "trip_duration_limit", 0.0))
        T_baseline_seg = F - AT  # = T_k do compacto; nao muda com B_k
        delta_min = 0.0
        if tdl > 0.0 and math.isfinite(tdl):
            delta_min = max(0.0, T_baseline_seg - tdl)

        # delta_max: atraso MAXIMO de B_k que pode ser absorvido sem alterar
        # F_k/R_k e sem violar nenhuma janela/dueTime offshore ou
        # max_departure -- min de tres limites independentes:
        #   (a) espera_total: alem disso F_k comecaria a crescer tambem (a
        #       espera de janela ja existente na rota acaba);
        #   (b) margem_janela_min: forward time slack (Savelsbergh) ate o due
        #       mais apertado de qualquer no da rota (nada a ver com TDL,
        #       so viabilidade de janela);
        #   (c) folga_partida: max_departure_k - P_k, se houver limite.
        folga_partida = float("inf")
        if max_partida_k > 0.0 and math.isfinite(max_partida_k):
            folga_partida = max_partida_k - P
        delta_max = min(espera_total, margem_janela_min, folga_partida)

        if delta_min > delta_max + eps:
            return {
                "viavel": False,
                "motivo": f"tdl_violado_{T_baseline_seg / SEG_H:.4f}h_maior_{tdl / SEG_H:.4f}h",
                "cronologia": cronologia,
            }

        # ---- 2) escolher delta_B em [delta_min, delta_max] pelo coeficiente
        # da FO (MESMA FO do compacto), nao por uma convencao arbitraria.
        # Enquanto o atraso e absorvido pela espera (F_k, hB_k, hN_k, T_k
        # fixos), hDP_k = (R_k-P_k)/SEG_H-hN_k DIMINUI exatamente delta/SEG_H
        # por unidade de atraso (P_k cresce, R_k fixo) -- logo f1 varia com
        # -(delta_cost-theta_cost)*delta/SEG_H (delta_cost=FCS=cost_dynamic,
        # theta_cost=FCA=cost_anchored) e f2=T_k_h fica constante. Como
        # custo=alpha_fo*f1+(1-alpha_fo)*eta_fo*f2, o sinal de d(custo)/d(delta)
        # e -alpha_fo*(delta_cost-theta_cost)/SEG_H:
        #   alpha_fo>0 e delta_cost>theta_cost -> custo decresce com delta -> delta_max
        #   alpha_fo>0 e delta_cost<theta_cost -> custo cresce com delta -> delta_min
        #   alpha_fo==0 ou delta_cost==theta_cost -> degenerado (mesma FO no
        #     intervalo todo) -> convencao deterministica: delta_min.
        alpha_fo_local = float(inst.alpha_fo)
        theta_cost = float(veic.cost_anchored)
        delta_cost = float(veic.cost_dynamic)
        eps_custo = 1e-9
        if alpha_fo_local > 0.0 and (delta_cost - theta_cost) > eps_custo:
            delta_B = delta_max
        elif alpha_fo_local > 0.0 and (theta_cost - delta_cost) > eps_custo:
            delta_B = delta_min
        else:
            delta_B = delta_min

        B = AT + delta_B
        P = B + hB_saida_seg

        # ---- componentes da FO (mesmas formulas do compacto) ----
        hB_saida_h = hB_saida_seg / SEG_H
        hB_retorno_h = hB_retorno_seg / SEG_H
        hB = hB_saida_h + hB_retorno_h
        hN_seg = sum(nav_pura_seg(seq[pos], seq[pos + 1]) for pos in range(len(seq) - 1))
        hN = hN_seg / SEG_H
        hDP = (R - P) / SEG_H - hN

        theta_k = veic.cost_anchored
        varphi_k = veic.cost_base
        gamma_k = veic.cost_navigation
        delta_k = veic.cost_dynamic

        f1 = (varphi_k - theta_k) * hB + (gamma_k - theta_k) * hN + (delta_k - theta_k) * hDP

        xi_definido = veic.xi is not None
        xi_usado = veic.xi if xi_definido else 1.0
        T_k_h = (F - AT) / SEG_H
        f2 = xi_usado * T_k_h

        alpha_fo = float(inst.alpha_fo)
        eta_fo = float(inst.eta_fo)
        custo = alpha_fo * f1 + (1.0 - alpha_fo) * eta_fo * f2

        resultado = {
            "viavel": True, "motivo": "ok",
            "custo": custo, "f1": f1, "f2": f2, "xi_usado": xi_usado,
            "xi_provisorio": not xi_definido,
            "AT": AT / SEG_H, "B": B / SEG_H, "P": P / SEG_H, "R": R / SEG_H, "F": F / SEG_H,
            "hB_saida": hB_saida_h, "hB_retorno": hB_retorno_h, "hB": hB,
            "hN": hN, "hDP": hDP, "espera": espera_total / SEG_H,
            "janelas_usadas": janelas_usadas, "cronologia": cronologia,
            "silva_sp_arcos_base": silva_sp_arcos_base,
        }
        if diagnostico:
            aviso_xi = "  (xi=1 PROVISORIO -- veic.xi nao definido)" if not xi_definido else ""
            print(f"[SILVA_ROTA] navio={k} rota={seq} viavel=True custo={custo:.4f} f1={f1:.4f} f2={f2:.4f}{aviso_xi}")
            print(f"[SILVA_ROTA] navio={k} AT={resultado['AT']:.4f}h B={resultado['B']:.4f}h P={resultado['P']:.4f}h "
                  f"R={resultado['R']:.4f}h F={resultado['F']:.4f}h hB={hB:.4f}h hN={hN:.4f}h hDP={hDP:.4f}h "
                  f"espera={resultado['espera']:.4f}h")
        return resultado

    def custo_rota_silva2024(self, inst, k, seq, silva_sp_arcos_base=True):
        """
        Wrapper simples de avaliar_rota_silva2024: retorna o custo da rota se
        viavel, ou float('inf') se inviavel. Funcao NOVA e ISOLADA -- nao
        substitui nenhuma chamada existente do B&P/pricing.

        silva_sp_arcos_base (default True -- IDENTICO ao comportamento
        historico): repassado sem alteracao a avaliar_rota_silva2024. O B&P
        (preparar_pool_silva2024 e demais chamadores atuais) nao passa este
        argumento, logo continua usando o default True nesta etapa.
        """
        resultado = self.avaliar_rota_silva2024(inst, k, seq, silva_sp_arcos_base=silva_sp_arcos_base)
        if not resultado["viavel"]:
            return float("inf")
        return resultado["custo"]

    def preparar_pool_silva2024(self, inst, sol_pool, diagnostico=False):
        """
        Funcao NOVA e ISOLADA (Etapa 3): re-precifica o pool de colunas ja
        gerado pelas construtivas ATUAIS (nao as altera) usando exatamente a
        interpretacao fisica de avaliar_rota_silva2024/metodo_exato_petro
        (modo silva2024). So deve ser chamada quando
        inst.objective_mode == "silva2024".

        Para cada navio k e cada rota p em sol_pool.rotas[k]["sequencia_rota"]:
          - coluna artificial (["artificial"][p] is True): NAO tocada (fica
            com o custo artificial de Fase I, necessario para viabilidade).
          - coluna ociosa ([0, depf]): custo Silva = 0.0.
          - demais colunas REAIS: avaliadas por avaliar_rota_silva2024; se
            viavel, sol_pool.rotas[k]["custo"][p] e substituido pelo custo
            Silva; se inviavel, a coluna e removida de forma consistente de
            TODAS as listas paralelas (sequencia_rota, rotas_binaria, custo,
            vezes_usada_geral, vezes_usada_otimo, lbd_iteracao, artificial).

        Retorna um dict de diagnostico:
        {"avaliadas": int, "viaveis": int, "inviaveis": int, "custos_atualizados": int}
        """
        depf = inst.nbn - 1
        avaliadas = viaveis = inviaveis = custos_atualizados = 0

        for k in sol_pool.rotas.keys():
            rotas_k = sol_pool.rotas[k]
            manter = []  # indices das colunas que permanecem no pool

            for p, seq in enumerate(rotas_k["sequencia_rota"]):
                if rotas_k["artificial"][p]:
                    # Fase I -- nao mexe, mantem custo artificial existente.
                    manter.append(p)
                    continue

                if seq == [0, depf]:
                    # coluna ociosa: custo Silva = 0.0 (navio nao utilizado).
                    rotas_k["custo"][p] = 0.0
                    manter.append(p)
                    continue

                avaliadas += 1
                resultado = self.avaliar_rota_silva2024(inst, k, seq)
                if resultado["viavel"]:
                    viaveis += 1
                    custo_antigo = rotas_k["custo"][p]
                    rotas_k["custo"][p] = resultado["custo"]
                    custos_atualizados += 1
                    manter.append(p)
                    if diagnostico:
                        print(f"[SILVA_POOL] navio={k} p={p} seq={seq} viavel=True "
                              f"custo_antigo={custo_antigo:.4f} custo_silva={resultado['custo']:.4f}")
                else:
                    inviaveis += 1
                    if diagnostico:
                        print(f"[SILVA_POOL] navio={k} p={p} seq={seq} viavel=False "
                              f"motivo={resultado.get('motivo')} -- REMOVIDA do pool")

            if len(manter) != len(rotas_k["sequencia_rota"]):
                for chave in ("sequencia_rota", "rotas_binaria", "custo", "vezes_usada_geral",
                              "vezes_usada_otimo", "lbd_iteracao", "artificial"):
                    rotas_k[chave] = [rotas_k[chave][p] for p in manter]

        sol_pool.numero_de_rotas = [len(sol_pool.rotas[k]["sequencia_rota"]) for k in sol_pool.rotas.keys()]

        diag = {
            "avaliadas": avaliadas, "viaveis": viaveis,
            "inviaveis": inviaveis, "custos_atualizados": custos_atualizados,
        }
        if diagnostico:
            print(f"[SILVA_POOL] resumo: avaliadas={avaliadas} viaveis={viaveis} "
                  f"inviaveis={inviaveis} custos_atualizados={custos_atualizados}")
        return diag

    # ========================================================================
    # WRAPPERS C++ SILVA (secao 4 do pedido de integracao BID_SILVA_CPP/
    # PD_SILVA_CPP no B&P): centralizam import do modulo, marshaling
    # instancia/veiculo -> args pybind, chamada do C++ e auditoria
    # Python obrigatoria (secao 5) -- NENHUMA coluna C++ entra no pool sem
    # passar por avaliar_rota_silva2024 + recomputo de RC + coluna_respeita_no
    # + checagem de nao-revisita aqui dentro. Fisica/branching/nucleo C++
    # (silva_pricing_core.h, PD_SILVA_CPP.cpp, BID_SILVA_CPP.cpp) NAO sao
    # alterados por esta tarefa -- so consumidos via pybind.
    # ========================================================================

    def _silva_cpp_module(self):
        """Importa (uma unica vez, cacheado na classe) o modulo pybind
        vrptw_pd_silva a partir do caminho ABSOLUTO relativo a este arquivo
        (secao 13): PD_SILVA_CPP/PD_SILVA_CPP/x64/Release/vrptw_pd_silva.pyd.
        Nunca depende de um .pyd antigo que por acaso esteja em sys.path --
        insere o diretorio correto na FRENTE de sys.path e confere que o
        modulo efetivamente carregado veio de la. Imprime [SILVA C++ MODULE]
        uma unica vez, no primeiro uso."""
        cache = getattr(Metodos, "_silva_cpp_mod_cache", None)
        if cache is not None:
            return cache

        import sys
        cpp_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "PD_SILVA_CPP", "PD_SILVA_CPP", "x64", "Release",
        )
        if cpp_dir not in sys.path:
            sys.path.insert(0, cpp_dir)
        import vrptw_pd_silva

        mod_path = os.path.abspath(vrptw_pd_silva.__file__)
        if not mod_path.startswith(os.path.abspath(cpp_dir)):
            raise RuntimeError(
                f"vrptw_pd_silva carregado de caminho inesperado ({mod_path}); "
                f"esperado sob {cpp_dir} -- possivel .pyd antigo no sys.path"
            )
        print("\n[SILVA C++ MODULE]")
        print(f"arquivo={mod_path}")
        Metodos._silva_cpp_mod_cache = vrptw_pd_silva
        return vrptw_pd_silva

    def _plataforma_de_no_silva(self, inst, no):
        """Mesma regra de agrupamento de plataforma usada em
        avaliar_rota_silva2024/pricing_silva2024/SUB_PROG_PD_SILVA/
        SUB_PROG_BID_SILVA (nome ate '_order_'/'_order'); None para
        dep0/depf."""
        if no == 0 or no == inst.nbn - 1:
            return None
        dp = inst.dados_petro
        nomes = list(dp.get("nomes", []))
        nome = str(nomes[no]) if no < len(nomes) else ""
        if "_order_" in nome:
            return nome.split("_order_", 1)[0]
        elif "_order" in nome:
            return nome.split("_order", 1)[0]
        return nome

    def _silva_seq_respeita_nao_revisita(self, inst, seq):
        """Checagem de seguranca (a mesma ja usada nos testes isolados
        _teste_pd_silva_cpp.py/_teste_bid_silva_cpp.py): a sequencia
        comprimida de plataformas (removendo repeticoes CONSECUTIVAS) nao
        pode ter uma plataforma repetida -- isso significaria que a coluna
        saiu de uma plataforma e voltou depois, o que os labels C++ (bitset
        `fechadas`) ja deveriam impedir por construcao; esta checagem so
        confirma isso na auditoria, nunca reimplementa a regra."""
        seq_plat = [self._plataforma_de_no_silva(inst, no) for no in seq]
        seq_plat = [p for p in seq_plat if p is not None]
        comprimida = []
        for p in seq_plat:
            if not comprimida or comprimida[-1] != p:
                comprimida.append(p)
        return len(comprimida) == len(set(comprimida))

    def _montar_kwargs_silva_cpp(self, inst, k, pi, sigma_k, mu_arc, no_bp):
        """Marshaling instancia/veiculo k -> kwargs COMUNS de
        pricing_pd_silva/pricing_bid_silva (tudo exceto os parametros de
        orcamento/estrategia especificos de cada um, adicionados pelo
        chamador). Mesma logica ja validada em montar_kwargs_cpp/
        montar_kwargs_cpp_bid dos testes isolados _teste_pd_silva_cpp.py/
        _teste_bid_silva_cpp.py -- traduzida aqui para nao duplicar esse
        marshaling dentro de gerar_novas_colunas_com_duais11."""
        import numpy as np

        dp = inst.dados_petro
        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1
        veic = inst.veiculos[k]

        mapa_plataformas = {}
        plataforma_id = [-1] * nbn
        for i in range(1, nbcd + 1):
            chave = self._plataforma_de_no_silva(inst, i)
            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)
            plataforma_id[i] = mapa_plataformas[chave]

        platform_setup_seg = list(dp.get("platform_setup_seg", [0.0] * nbn))
        n_plataformas = len(mapa_plataformas)
        set_por_plataforma = [0.0] * max(n_plataformas, 1)
        for i in range(1, nbcd + 1):
            p = plataforma_id[i]
            set_por_plataforma[p] = max(set_por_plataforma[p], float(platform_setup_seg[i]))

        dist_raw = dp["dist"]
        n_raw = len(dist_raw)
        dist_km_arr = np.zeros((nbn, nbn), dtype=np.float64)
        for i in range(n_raw):
            for j in range(n_raw):
                dist_km_arr[i, j] = float(dist_raw[i][j])

        vs = veic.velocities
        v_low = float(min(vs, key=lambda v: v["above"])["speed"])
        v_high = float(max(vs, key=lambda v: v["above"])["speed"])
        th_km = float(max(vs, key=lambda v: v["above"])["above"])

        servico = [float(inst.noh[i].SERVICE_TIME[0]) if getattr(inst.noh[i], "SERVICE_TIME", None) else 0.0
                   for i in range(nbn)]
        ready = [list(getattr(inst.noh[i], "READY_TIME", []) or []) for i in range(nbn)]
        due = [list(getattr(inst.noh[i], "DUE_DATE", []) or []) for i in range(nbn)]

        def dado_no(i, atributo, chave):
            valor_no = getattr(inst.noh[i], atributo, None)
            if valor_no is not None:
                return float(valor_no)
            vetor = dp.get(chave, [])
            return float(vetor[i]) if i < len(vetor) else 0.0

        deck_load = [dado_no(i, "DEMAND_DECK_LOAD", "dem_deck_load") for i in range(nbn)]
        deck_backload = [dado_no(i, "DEMAND_DECK_BACKLOAD", "dem_deck_backload") for i in range(nbn)]
        diesel_dem = [dado_no(i, "DEMAND_DIESEL", "dem_diesel") for i in range(nbn)]
        agua_dem = [dado_no(i, "DEMAND_AGUA", "dem_agua") for i in range(nbn)]

        tempo_carreg_deck = list(dp.get("tempo_carreg_deck", [0.0] * nbn))
        tempo_carreg_diesel = list(dp.get("tempo_carreg_diesel", [0.0] * nbn))
        tempo_carreg_agua = list(dp.get("tempo_carreg_agua", [0.0] * nbn))
        tempo_descarreg_backload = list(dp.get("tempo_descarreg_backload", [0.0] * nbn))
        commodities = list(dp.get("commodities", [None] * nbn))
        is_backload = [1 if (i < len(commodities) and commodities[i] == "deckCargoBackload") else 0
                       for i in range(nbn)]
        order_due_time_seg = list(dp.get("order_due_time_seg", [None] * nbn))
        has_due_time = [1 if (i < len(order_due_time_seg) and order_due_time_seg[i] is not None) else 0
                        for i in range(nbn)]
        order_due_time = [float(order_due_time_seg[i]) if (i < len(order_due_time_seg) and order_due_time_seg[i] is not None) else 0.0
                          for i in range(nbn)]

        cap_deck = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua = float(getattr(veic, "cap_agua", float("inf")))

        AT = float(veic.readiness)
        max_partida = float(getattr(veic, "max_departure", 0.0))
        tdl = float(getattr(veic, "trip_duration_limit", 0.0))
        theta_k = float(veic.cost_anchored)
        varphi_k = float(veic.cost_base)
        gamma_k = float(veic.cost_navigation)
        delta_k = float(veic.cost_dynamic)
        xi_usado = float(veic.xi) if veic.xi is not None else 1.0
        alpha_fo = float(inst.alpha_fo)
        eta_fo = float(inst.eta_fo)

        mu_flat = [0.0] * (nbn * nbn)
        for i in range(nbn):
            for j in range(nbn):
                mu_flat[i * nbn + j] = float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))

        proibidos_k = {(i, j) for (i, j, kk) in (no_bp.arcos_proibidos if no_bp else set()) if kk == k}
        forbid_flat = [0] * (nbn * nbn)
        for (i, j) in proibidos_k:
            forbid_flat[i * nbn + j] = 1

        fixados_k = [(i, j) for (i, j, kk) in (no_bp.arcos_fixados_em_1 if no_bp else set()) if kk == k]
        req_i = [i for (i, j) in fixados_k]
        req_j = [j for (i, j) in fixados_k]

        return dict(
            nbn=nbn, nbcd=nbcd, dep0=dep0, depf=depf, k=k,
            dist_km_arr=dist_km_arr,
            v_low=v_low, v_high=v_high, th_km=th_km, safe_positioning_time=float(veic.safe_positioning_time),
            plataforma_id=plataforma_id,
            set_por_plataforma=set_por_plataforma,
            servico=servico, ready=ready, due=due,
            deck_load=deck_load, deck_backload=deck_backload, diesel_dem=diesel_dem, agua_dem=agua_dem,
            tempo_carreg_deck=tempo_carreg_deck, tempo_carreg_diesel=tempo_carreg_diesel,
            tempo_carreg_agua=tempo_carreg_agua, tempo_descarreg_backload=tempo_descarreg_backload,
            is_backload=is_backload, order_due_time=order_due_time, has_due_time=has_due_time,
            cap_deck=cap_deck, cap_diesel=cap_diesel, cap_agua=cap_agua,
            AT=AT, max_partida=max_partida, tdl=tdl,
            theta_k=theta_k, varphi_k=varphi_k, gamma_k=gamma_k, delta_k=delta_k,
            xi_usado=xi_usado, alpha_fo=alpha_fo, eta_fo=eta_fo,
            pi=list(pi), sigma_k=float(sigma_k), mu_flat=mu_flat,
            forbid_flat=forbid_flat, req_i=req_i, req_j=req_j,
        )

    def _auditar_candidatas_silva_cpp(self, origem, candidatas_cpp, inst, k, pi, sigma_k, mu_arc, no_bp,
                                       tol_rc=1e-6):
        """Auditoria OBRIGATORIA (secao 5) de TODA candidata retornada por
        PD_SILVA_CPP/BID_SILVA_CPP -- avaliar_rota_silva2024 e a UNICA
        autoridade de viabilidade/custo; o valor armazenado na candidata
        final e SEMPRE o custo/RC recalculados aqui em Python (nunca o valor
        cru do C++, so usado para comparacao/diagnostico). Candidata que
        falhar qualquer checagem (inviavel, RC divergente, branching violado,
        revisita de plataforma) e descartada com um log de erro explicito --
        nunca sobe silenciosamente ao pool (secao 6/7)."""
        mu_arc = mu_arc or {}
        aceitas = []
        for c in candidatas_cpp:
            seq = list(c["seq"])

            resultado = self.avaliar_rota_silva2024(inst, k, seq)
            if not resultado.get("viavel"):
                print(f"[SILVA {origem}][ERRO] candidata k={k} seq={seq} REJEITADA: "
                      f"avaliar_rota_silva2024 nao-viavel (motivo={resultado.get('motivo')})")
                continue

            custo_python = float(resultado["custo"])
            rc_python = custo_python
            for cliente in seq:
                if 1 <= cliente <= inst.nbcd:
                    rc_python -= float(pi[cliente - 1])
            rc_python -= float(sigma_k)
            for t in range(len(seq) - 1):
                i, j = seq[t], seq[t + 1]
                rc_python -= float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))

            rc_cpp = float(c.get("rc", rc_python))
            if abs(rc_cpp - rc_python) > tol_rc:
                print(f"[SILVA {origem}][ERRO] candidata k={k} seq={seq} REJEITADA: "
                      f"rc_cpp ({rc_cpp}) difere de rc_python ({rc_python}) por "
                      f"{abs(rc_cpp - rc_python):.2e} > tolerancia {tol_rc:.1e}")
                continue

            if no_bp is not None and not self.coluna_respeita_no(no_bp, seq, k):
                print(f"[SILVA {origem}][ERRO] candidata k={k} seq={seq} REJEITADA: "
                      f"viola branching do NO_BP")
                continue

            if not self._silva_seq_respeita_nao_revisita(inst, seq):
                print(f"[SILVA {origem}][ERRO] candidata k={k} seq={seq} REJEITADA: "
                      f"revisita uma plataforma")
                continue

            binx = [0] * inst.nbcd
            for c_no in seq:
                if 1 <= c_no <= inst.nbcd:
                    binx[c_no - 1] = 1
            aceitas.append({"k": k, "seq": seq, "binx": binx, "custo": custo_python,
                             "rc": rc_python, "origem": origem})
        return aceitas

    def chamar_pd_silva_cpp(self, inst, pi, sigma_k, k, no_bp, mu_arc=None,
                             max_labels=None, timeout_s=None, max_candidatas=None, eps=1e-6):
        """Wrapper isolado (secao 4) para pricing_pd_silva (PD_SILVA_CPP.cpp,
        NAO alterado por esta tarefa): monta os kwargs, chama o C++, audita
        TODA candidata (secao 5) e devolve no contrato ja usado pelo pool
        (secao 6). Nunca certifica sozinho -- devolve completa/timeout do
        C++ para o chamador decidir (secao 8).

        Retorna (candidatas, completa, timeout, labels_gerados, niveis_alcancados, tempo).
        Em caso de falha de import/chamada (secao 14): NAO propaga a
        excecao -- registra o erro e devolve completa=False (nunca
        certifica), lista vazia."""
        mu_arc = mu_arc or {}
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        if max_labels is None:
            max_labels = getattr(inst, "silva_pd_cpp_max_labels", self.SILVA_PD_CPP_MAX_LABELS)
        if timeout_s is None:
            timeout_s = getattr(inst, "silva_pd_cpp_timeout_s", self.SILVA_PD_CPP_TIMEOUT_S)

        try:
            mod = self._silva_cpp_module()
            kwargs = self._montar_kwargs_silva_cpp(inst, k, pi, sigma_k, mu_arc, no_bp)
            kwargs.update(max_labels=int(max_labels), timeout_s=float(timeout_s),
                          max_candidatas=int(max_candidatas), eps=float(eps))
            saida_cpp, completa, timeout_flag, labels_gerados, nivel, tempo = mod.pricing_pd_silva(**kwargs)
        except Exception as e:
            print(f"[SILVA PD_SILVA_CPP][ERRO] falha ao chamar pricing_pd_silva k={k}: {e!r} "
                  f"-- completa=False (nao certifica), nenhuma candidata devolvida")
            return [], False, False, 0, 0, 0.0

        candidatas = self._auditar_candidatas_silva_cpp(
            "PD_SILVA_CPP", list(saida_cpp), inst, k, pi, sigma_k, mu_arc, no_bp
        )
        return candidatas, bool(completa), bool(timeout_flag), int(labels_gerados), int(nivel), float(tempo)

    def chamar_bid_silva_cpp(self, inst, pi, sigma_k, k, no_bp, mu_arc=None,
                              max_labels_por_no=None, max_depth=None, max_candidatas=None, eps=1e-6):
        """Wrapper isolado (secao 4) para pricing_bid_silva (BID_SILVA_CPP.cpp,
        NAO alterado por esta tarefa): mesmo papel de chamar_pd_silva_cpp,
        para o pricing HEURISTICO. completa e SEMPRE False no retorno do
        proprio C++ (BID nunca certifica -- secao 2/11).

        Retorna (candidatas, completa, timeout, labels_gerados, niveis_alcancados, tempo).
        Em caso de falha (secao 14): NAO propaga a excecao -- registra o
        erro e devolve lista vazia, para o chamador seguir com seguranca
        para PD_SILVA_CPP."""
        mu_arc = mu_arc or {}
        if max_candidatas is None:
            max_candidatas = self.MAX_CANDIDATAS_PRICING
        if max_labels_por_no is None:
            max_labels_por_no = self.SILVA_BID_CPP_MAX_LABELS_POR_NO
        if max_depth is None:
            max_depth = -1  # C++ interpreta <=0 como nbcd (mesmo default de max_depth do BID Python)

        try:
            mod = self._silva_cpp_module()
            kwargs = self._montar_kwargs_silva_cpp(inst, k, pi, sigma_k, mu_arc, no_bp)
            kwargs.update(max_labels_por_no=int(max_labels_por_no), max_depth=int(max_depth),
                          max_candidatas=int(max_candidatas), eps=float(eps))
            saida_cpp, completa, timeout_flag, labels_gerados, nivel, tempo = mod.pricing_bid_silva(**kwargs)
        except Exception as e:
            print(f"[SILVA BID_SILVA_CPP][ERRO] falha ao chamar pricing_bid_silva k={k}: {e!r} "
                  f"-- seguindo para PD_SILVA_CPP, nenhuma candidata devolvida")
            return [], False, False, 0, 0, 0.0

        candidatas = self._auditar_candidatas_silva_cpp(
            "BID_SILVA_CPP", list(saida_cpp), inst, k, pi, sigma_k, mu_arc, no_bp
        )
        return candidatas, bool(completa), bool(timeout_flag), int(labels_gerados), int(nivel), float(tempo)

    def _pricing_silva2024_um_veiculo(self, inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, k):
        """Pipeline Silva2024 (secao 1 do pedido de integracao) para UM
        veiculo k: ALLBEST_SILVA (heuristico Python, sempre tentado
        primeiro) -> BID_SILVA_CPP (heuristico C++, producao -- substitui
        SUB_PROG_BID_SILVA Python no pipeline normal, secao 2) -> PD_SILVA_CPP
        (exato C++, UNICO que certifica, substitui pricing_silva2024 no
        pipeline normal, secao 3). Cada estagio so roda se o anterior nao
        encontrou nenhuma candidata negativa INEDITA no pool deste k.

        Usado tanto por gerar_novas_colunas_com_duais11 (producao) quanto
        pelo teste de integracao isolado (secao 15) -- mesma funcao, sem
        duplicar a logica de decisao ALLBEST->BID_CPP->PD_CPP.

        Retorna (candidatas_para_pool, status_k). status_k documenta cada
        estagio para o log [SILVA PRICING] (secao 9) e para a certificacao
        (secao 8): so True quando PD_SILVA_CPP foi chamado, completa=True,
        timeout=False e nao sobrou candidata inedita."""
        mu_arc = mu_arc_por_k.get(k, {})
        sigma_k = sigma[k]

        if not hasattr(no_bp, "melhor_rc_por_k"):
            no_bp.melhor_rc_por_k = {}
        if not hasattr(no_bp, "silva_certifica_k"):
            no_bp.silva_certifica_k = {}

        status_k = {
            "allbest_chamado": True, "allbest_encontrou": False, "n_allbest": 0,
            "bid_chamado": False, "bid_encontrou": False, "n_bid": 0,
            "pd_chamado": False, "pd_encontrou": False, "n_pd": 0,
            "pd_completa": None, "pd_timeout": None,
            "labels_pd": None, "nivel_pd": None,
            "melhor_rc": None, "origem": None, "certifica_k": False,
            "tem_negativa_pd": False,
        }

        def _log_bloco():
            # secao 9 do pedido -- formato obrigatorio, impresso uma vez por
            # veiculo ao final desta funcao (ALLBEST/BID_CPP/PD_CPP = numero
            # de candidatas ineditas encontradas em cada estagio, 0 se o
            # estagio nao foi alcancado).
            print("[SILVA PRICING]")
            print(f"k={k}")
            print(f"ALLBEST={status_k['n_allbest']}")
            print(f"BID_CPP={status_k['n_bid']}")
            print(f"PD_CPP={status_k['n_pd']}")
            print(f"pd_completa={status_k['pd_completa']}")
            print(f"pd_timeout={status_k['pd_timeout']}")
            print(f"labels_pd={status_k['labels_pd']}")
            print(f"nivel_pd={status_k['nivel_pd']}")
            print(f"melhor_rc={status_k['melhor_rc']}")
            print(f"origem={status_k['origem']}")
            print(f"certifica_k={status_k['certifica_k']}")

        # ---- 1) ALLBEST_SILVA (heuristico Python, inalterado) ----
        print("TESTA ALLBEST_SILVA")
        geradas_allbest, _completa_ab, _to_ab = self.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA(
            inst, sol_pool, pi, sigma_k=sigma_k, k=k, NO_BP=no_bp, mu_arc=mu_arc,
            max_candidatas=self.MAX_CANDIDATAS_PRICING,
        )
        geradas_allbest = geradas_allbest or []
        status_k["n_allbest"] = len(geradas_allbest)
        validas_ab = [c for c in geradas_allbest if self.coluna_respeita_no(no_bp, c["seq"], k)]
        sem_pool_ab = [c for c in validas_ab if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
        print(f"[PRICING MULTI] origem=ALLBEST_SILVA | k={k} | geradas={len(geradas_allbest)} | "
              f"novas_pool={len(sem_pool_ab)} | duplicadas_pool={len(validas_ab) - len(sem_pool_ab)} | "
              f"completa=False")

        if sem_pool_ab:
            sem_pool_ab.sort(key=lambda c: c["rc"])
            no_bp.melhor_rc_por_k[k] = sem_pool_ab[0]["rc"]
            status_k["allbest_encontrou"] = True
            status_k["melhor_rc"] = sem_pool_ab[0]["rc"]
            status_k["origem"] = "ALLBEST_SILVA"
            status_k["certifica_k"] = False
            no_bp.silva_certifica_k[k] = False
            _log_bloco()
            return sem_pool_ab[:self.MAX_COLUNAS_NOVAS_VEICULO], status_k

        # ---- 2) BID_SILVA_CPP (heuristico C++, PRODUCAO -- secao 2: nao usa
        # mais SUB_PROG_BID_SILVA Python aqui, que fica so para teste/regressao) ----
        print("TESTA BID_SILVA_CPP")
        status_k["bid_chamado"] = True
        geradas_bid, _completa_bid, _to_bid, labels_bid, nivel_bid, _tempo_bid = self.chamar_bid_silva_cpp(
            inst, pi, sigma_k, k, no_bp, mu_arc=mu_arc,
            max_labels_por_no=self.SILVA_BID_CPP_MAX_LABELS_POR_NO, max_depth=-1,
            max_candidatas=self.MAX_CANDIDATAS_PRICING,
        )
        geradas_bid = geradas_bid or []
        status_k["n_bid"] = len(geradas_bid)
        # chamar_bid_silva_cpp ja auditou (viavel/RC/branching/nao-revisita,
        # secao 5) -- so falta excluir o que ja esta no pool deste k.
        sem_pool_bid = [c for c in geradas_bid if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
        print(f"[PRICING MULTI] origem=BID_SILVA_CPP | k={k} | geradas={len(geradas_bid)} | "
              f"novas_pool={len(sem_pool_bid)} | duplicadas_pool={len(geradas_bid) - len(sem_pool_bid)} | "
              f"completa=False")

        if sem_pool_bid:
            sem_pool_bid.sort(key=lambda c: c["rc"])
            no_bp.melhor_rc_por_k[k] = sem_pool_bid[0]["rc"]
            status_k["bid_encontrou"] = True
            status_k["melhor_rc"] = sem_pool_bid[0]["rc"]
            status_k["origem"] = "BID_SILVA_CPP"
            status_k["certifica_k"] = False
            no_bp.silva_certifica_k[k] = False
            _log_bloco()
            return sem_pool_bid[:self.MAX_COLUNAS_NOVAS_VEICULO], status_k

        # ---- 3) PD_SILVA_CPP (exato C++, PRODUCAO -- secao 3: unico que
        # certifica; pricing_silva2024 nao e mais chamado aqui, continua
        # disponivel so para diagnostico/teste) ----
        print("TESTA PD_SILVA_CPP")
        status_k["pd_chamado"] = True
        geradas_pd, completa_pd, timeout_pd_flag, labels_pd, nivel_pd, _tempo_pd = self.chamar_pd_silva_cpp(
            inst, pi, sigma_k, k, no_bp, mu_arc=mu_arc,
            max_labels=getattr(inst, "silva_pd_cpp_max_labels", self.SILVA_PD_CPP_MAX_LABELS),
            timeout_s=getattr(inst, "silva_pd_cpp_timeout_s", self.SILVA_PD_CPP_TIMEOUT_S),
            max_candidatas=self.MAX_CANDIDATAS_PRICING,
        )
        geradas_pd = geradas_pd or []
        status_k["n_pd"] = len(geradas_pd)
        status_k["pd_completa"] = completa_pd
        status_k["pd_timeout"] = timeout_pd_flag
        status_k["labels_pd"] = labels_pd
        status_k["nivel_pd"] = nivel_pd
        sem_pool_pd = [c for c in geradas_pd if not sol_pool.coluna_ja_existe(c["seq"], k=k, globalmente=False)]
        print(f"[PRICING MULTI] origem=PD_SILVA_CPP | k={k} | geradas={len(geradas_pd)} | "
              f"novas_pool={len(sem_pool_pd)} | duplicadas_pool={len(geradas_pd) - len(sem_pool_pd)} | "
              f"completa={completa_pd} | timeout={timeout_pd_flag}")

        if timeout_pd_flag:
            no_bp.pricing_timeout = True
            print(f"[SILVA] PD_SILVA_CPP excedeu o orcamento (timeout/max_labels) "
                  f"no veiculo {k}; convergencia nao certificada.")

        if sem_pool_pd:
            sem_pool_pd.sort(key=lambda c: c["rc"])
            status_k["pd_encontrou"] = True
            status_k["melhor_rc"] = sem_pool_pd[0]["rc"]
            status_k["tem_negativa_pd"] = True
            status_k["origem"] = "PD_SILVA_CPP"
            # secao 8: PD encontrou coluna negativa => certifica_k=False (a CG continua)
            status_k["certifica_k"] = False
            no_bp.silva_certifica_k[k] = False
            no_bp.melhor_rc_por_k[k] = sem_pool_pd[0]["rc"]
            _log_bloco()
            return sem_pool_pd[:self.MAX_COLUNAS_NOVAS_VEICULO], status_k

        # PD_SILVA_CPP nao encontrou nenhuma candidata INEDITA -- mas isso NAO
        # basta para certificar: sem_pool_pd so diz "nao ha nada NOVO para o
        # pool" (neste ponto sem_pool_pd e SEMPRE vazio, ja que o caminho
        # acima retornou se houvesse algo -- "not sem_pool_pd" sozinho seria
        # sempre True aqui, um bug silencioso). O que importa para
        # certificacao e se o PD encontrou QUALQUER rota com RC<0, mesmo que
        # ja existente no pool (duplicata negativa == "ainda ha coluna de
        # custo reduzido negativo para este k", a CG NAO convergiu para k).
        # So certifica (secao 8) se a arvore foi REALMENTE esgotada, sem
        # timeout, E nenhuma candidata negativa (inedita ou nao) foi vista.
        eps_certifica = 1e-6
        tem_negativa_pd = any(c["rc"] < -eps_certifica for c in geradas_pd)
        certifica_k = bool(completa_pd) and (not timeout_pd_flag) and (not tem_negativa_pd)
        status_k["certifica_k"] = certifica_k
        status_k["tem_negativa_pd"] = tem_negativa_pd
        # melhor_rc do log/diagnostico deve refletir a melhor RC vista pelo PD
        # mesmo quando ela e' uma duplicata (nao ha nada NOVO para o pool, mas
        # ha RC<0 -- diagnostico nao pode "esconder" isso so porque nao sera
        # adicionada de novo).
        melhor_rc_pd = min((c["rc"] for c in geradas_pd), default=None)
        status_k["melhor_rc"] = melhor_rc_pd
        no_bp.silva_certifica_k[k] = certifica_k
        no_bp.melhor_rc_por_k[k] = melhor_rc_pd
        _log_bloco()
        return [], status_k

    def pricing_silva2024(self, inst, pi, sigma_k, k, NO_BP, arcos_proibidos=None,
                          arcos_fixados=None, mu_arc=None, diagnostico=False,
                          timeout_s=90.0, max_avaliacoes=300_000):
        """
        Pricing ISOLADO, exclusivo do modo silva2024. Nao chama C++, nao usa
        VNS/GRASP nem as heuristicas antigas (ALLBEST/BID). Python puro,
        exato/auditavel para as 14 orders desta instancia -- correcao antes
        de velocidade, conforme pedido.

        CORRECAO desta etapa: a unidade de decisao da enumeracao passa a ser a
        ORDER, nao a plataforma inteira. O artigo (Silva et al., 2024) e
        explicito: "There is no obligation ... to fulfill all orders placed
        by a platform from a single visit and/or vessel" -- portanto uma
        coluna pode conter QUALQUER subconjunto nao vazio das orders de uma
        plataforma (a versao anterior so gerava o bloco COMPLETO de cada
        plataforma, restringindo incorretamente o espaco de colunas -- ver
        DIAGNOSTICO/teste ALLBEST_SILVA x pricing_silva2024, onde ALLBEST
        encontrou RC mais negativo que este "oraculo" exatamente por causa
        dessa lacuna).

        Continua respeitando a mesma regra de precedencia JA VALIDADA (nao
        duplicada aqui como logica nova, so aplicada na geracao de
        candidatas -- avaliar_rota_silva2024 continua sendo a AUTORIDADE
        FINAL, nunca esta enumeracao sozinha): dentro de uma mesma
        plataforma/visita, toda coleta de DECK deve preceder toda entrega de
        DECK; diesel/agua sao livres (nao contam nessa precedencia). Uma
        plataforma, uma vez encerrada (nenhuma order sua na visita atual),
        nao pode ser reaberta depois -- mesma regra de bloco-por-plataforma
        de sempre (SO o CONTEUDO do bloco deixou de ser obrigatoriamente
        completo).

        Enumera, com poda de capacidade EXATA (nao aproximada -- ver abaixo),
        todas as sequencias validas de blocos de plataforma (cada bloco =
        QUALQUER subconjunto nao vazio das orders daquela plataforma, em
        QUALQUER ordenacao valida) para o navio k, incluindo toda rota
        PARCIAL (fechando direto no deposito apos qualquer prefixo). Para
        cada candidata fechada, usa avaliar_rota_silva2024 como ORACULO de
        viabilidade/custo real.

        Poda de capacidade (deck/diesel/agua, acumulada por SUBCONJUNTO
        escolhido, nao mais pelo total da plataforma): EXATA, nao
        aproximada -- a soma de deck_load (entregas) das orders efetivamente
        selecionadas ate agora e EXATAMENTE o que avaliar_rota_silva2024
        tambem exige <=capacidade no fechamento (todas as entregas sao
        pre-carregadas na base, "o navio sai da base com todas as entregas
        da rota"); o mesmo vale para diesel/agua (compartimentos proprios,
        totais simples). Portanto esta poda NUNCA elimina uma rota que
        avaliar_rota_silva2024 aceitaria -- so corta ramos que ja seriam
        estruturalmente inviaveis (nao e uma poda "grosseira"/otimista).

        Branching (arcos_proibidos/arcos_fixados): arcos_proibidos corta
        durante a construcao (arco_permitido); arcos_fixados_em_1 e exigido
        no FECHAMENTO de cada candidata (contem_todos_fixados, mesmo
        criterio de SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA/coluna_respeita_no)
        -- agora IMPOSTO, nao so aceito por compatibilidade de assinatura.

        Custo reduzido, EXATAMENTE a mesma convencao de sinais do mestre
        atual (pi indexado 0-based por cliente, sigma_k uma unica vez, mu_arc
        por arco com fallback (i,j,k) -> (i,j)):

            RC = custo_real
                 - sum(pi[i-1] para cada order i visitada)
                 - sigma_k
                 - sum(mu_arc(i,j) para os arcos efetivamente usados)

        Certificacao (Etapa desta correcao): para 14 orders o espaco de
        subconjuntos por plataforma pode crescer bastante (ate 2^|plataforma|
        variantes), entao a enumeracao e protegida por timeout_s/
        max_avaliacoes -- MESMO padrao ja usado pelos demais pricers "exatos"
        deste codebase (_petro_pricing_exato_multi/SUB_PROG_DIN_BIDIRECIONAL_
        PETRO_CPP_MULTI: timeout_s/max_labels + flag completa/timeout).
        Retorna (candidatas, completa, timeout): completa=False sempre que o
        limite foi atingido ANTES de esgotar a arvore -- o chamador NUNCA deve
        marcar convergencia/certificacao de otimalidade quando completa=False.
        Ordem de exploracao (gulosa, por soma de pi) so afeta QUAL candidata e
        encontrada primeiro se houver corte por timeout -- nunca o conjunto
        de rotas consideradas quando a busca termina completa.

        candidatas: lista de dicts {"k","seq","binx","custo","rc","origem"}
        com RC < -eps, ordenada da mais negativa.
        """
        import time as _time

        dep0 = 0
        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))
        veic = inst.veiculos[k]
        mu_arc = mu_arc or {}
        arcos_proibidos = arcos_proibidos or set()
        arcos_fixados = arcos_fixados or set()
        eps = 1e-6

        if veic.xi is None:
            print("[SILVA] xi=1 PROVISORIO")

        proibidos_k = {(i, j) for (i, j, kk) in arcos_proibidos if kk == k}
        fixados_k = {(i, j) for (i, j, kk) in arcos_fixados if kk == k}

        def arco_permitido(i, j):
            return (i, j) not in proibidos_k

        def contem_todos_fixados(seq_nos):
            if not fixados_k:
                return True
            aset = {(seq_nos[t], seq_nos[t + 1]) for t in range(len(seq_nos) - 1)}
            return all(arc in aset for arc in fixados_k)

        def mu(i, j):
            # mesmo fallback usado em SUB_PROG_DIN_PW/etc: (i,j,k) especifico,
            # senao (i,j) generico.
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            return float(mu_arc.get((i, j), 0.0))

        # ---- agrupamento por plataforma (MESMA regra de avaliar_rota_silva2024) ----
        dp = inst.dados_petro
        nomes = list(dp.get("nomes", []))
        mapa_plataformas = {}
        nos_por_plataforma = {}
        for i in clientes:
            nome = str(nomes[i]) if i < len(nomes) else ""
            if "_order_" in nome:
                chave = nome.split("_order_", 1)[0]
            elif "_order" in nome:
                chave = nome.split("_order", 1)[0]
            else:
                chave = nome
            if chave not in mapa_plataformas:
                mapa_plataformas[chave] = len(mapa_plataformas)
            nos_por_plataforma.setdefault(mapa_plataformas[chave], []).append(i)

        deck_load = {i: float(getattr(inst.noh[i], "DEMAND_DECK_LOAD", 0.0)) for i in clientes}
        deck_backload = {i: float(getattr(inst.noh[i], "DEMAND_DECK_BACKLOAD", 0.0)) for i in clientes}
        diesel = {i: float(getattr(inst.noh[i], "DEMAND_DIESEL", 0.0)) for i in clientes}
        agua = {i: float(getattr(inst.noh[i], "DEMAND_AGUA", 0.0)) for i in clientes}

        # ordenacoes validas de CADA SUBCONJUNTO nao vazio das orders de uma
        # plataforma (nao so do conjunto completo -- esta e a correcao desta
        # etapa): mesma regra de precedencia de sempre, toda coleta de DECK
        # antes de toda entrega de DECK (diesel/agua livres).
        def variantes_validas(nos_p):
            variantes = []
            vistas = set()
            n = len(nos_p)
            for tam in range(1, n + 1):
                for subset in itertools.combinations(nos_p, tam):
                    for perm in itertools.permutations(subset):
                        coletas_pos = [perm.index(c) for c in subset if deck_backload[c] > 1e-9]
                        entregas_pos = [perm.index(e) for e in subset if deck_load[e] > 1e-9]
                        if coletas_pos and entregas_pos and max(coletas_pos) > min(entregas_pos):
                            continue
                        if perm in vistas:
                            continue
                        vistas.add(perm)
                        variantes.append(list(perm))
            # ordenacao gulosa (subconjunto MAIOR primeiro, desempate por soma de
            # pi): SO decide a ORDEM de exploracao, nunca o conjunto de variantes
            # geradas. Tentar o bloco quase-completo/completo primeiro reproduz o
            # comportamento (ja validado) da versao anterior (bloco unico) logo
            # nos primeiros fechamentos, e so entao passa a explorar os
            # subconjuntos estritos -- aumenta MUITO a chance de achar uma
            # candidata boa cedo caso timeout_s/max_avaliacoes interrompa a busca
            # antes de esgotar a arvore (medido empiricamente: ordenar por soma de
            # pi bruta prioriza subconjuntos PEQUENOS primeiro -- ver
            # itertools.combinations acima, tam=1..n -- e a arvore nunca chega aos
            # blocos completos dentro do orcamento).
            variantes.sort(key=lambda v: (-len(v), -sum(float(pi[i - 1]) for i in v)))
            return variantes

        # ordem natural das plataformas (mesma de sempre, sem heuristica extra --
        # a heuristica que importa e a de TAMANHO do subconjunto, acima).
        plataformas = sorted(nos_por_plataforma.keys())
        variantes_por_plataforma = {p: variantes_validas(nos_por_plataforma[p]) for p in plataformas}

        Q = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel_k = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua_k = float(getattr(veic, "cap_agua", float("inf")))

        candidatas = []
        avaliadas_fechamentos = 0
        melhor_rc_visto = [float("inf")]
        t0 = _time.time()
        limite_atingido = [False]

        def orcamento_esgotado():
            if avaliadas_fechamentos >= max_avaliacoes:
                return True
            if (_time.time() - t0) > timeout_s:
                return True
            return False

        def avaliar_e_registrar(seq_nos):
            nonlocal avaliadas_fechamentos
            for t in range(len(seq_nos) - 1):
                if not arco_permitido(seq_nos[t], seq_nos[t + 1]):
                    return
            resultado = self.avaliar_rota_silva2024(inst, k, seq_nos)
            avaliadas_fechamentos += 1
            if not resultado["viavel"]:
                return
            custo_real = resultado["custo"]
            dual_clientes = sum(float(pi[i - 1]) for i in seq_nos if 1 <= i <= inst.nbcd)
            dual_arcos = sum(mu(seq_nos[t], seq_nos[t + 1]) for t in range(len(seq_nos) - 1))
            dual_veiculo = float(sigma_k)
            rc = custo_real - dual_clientes - dual_veiculo - dual_arcos

            if diagnostico:
                print(f"[SILVA_RC] k={k} seq={seq_nos} custo_real={custo_real:.4f} "
                      f"dual_clientes={dual_clientes:.4f} dual_veiculo={dual_veiculo:.4f} "
                      f"dual_arcos={dual_arcos:.4f} RC={rc:.6f}")

            if rc < melhor_rc_visto[0]:
                melhor_rc_visto[0] = rc

            if rc < -eps:
                # branching (secao 8): so vira candidata valida se contiver TODOS
                # os arcos fixados em 1 para este navio -- mesmo criterio de
                # SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA/coluna_respeita_no.
                if not contem_todos_fixados(seq_nos):
                    return
                binx = [0] * inst.nbcd
                for i in seq_nos:
                    if 1 <= i <= inst.nbcd:
                        binx[i - 1] = 1
                candidatas.append({"k": k, "seq": list(seq_nos), "binx": binx,
                                    "custo": float(custo_real), "rc": float(rc), "origem": "SILVA_PD"})

        def dfs(plataformas_restantes, blocos_visitados, deck_acum, diesel_acum, agua_acum):
            if limite_atingido[0]:
                return
            if orcamento_esgotado():
                limite_atingido[0] = True
                return

            if blocos_visitados:
                seq_nos = [dep0]
                for _, ordem in blocos_visitados:
                    seq_nos.extend(ordem)
                seq_nos.append(depf)
                avaliar_e_registrar(seq_nos)

            for p in plataformas_restantes:
                if limite_atingido[0]:
                    return
                for ordem in variantes_por_plataforma[p]:
                    if limite_atingido[0]:
                        return
                    novo_diesel = diesel_acum + sum(diesel[i] for i in ordem)
                    novo_agua = agua_acum + sum(agua[i] for i in ordem)
                    if math.isfinite(cap_diesel_k) and novo_diesel > cap_diesel_k + 1e-6:
                        continue
                    if math.isfinite(cap_agua_k) and novo_agua > cap_agua_k + 1e-6:
                        continue
                    novo_deck = deck_acum + sum(deck_load[i] for i in ordem)
                    if novo_deck > Q + 1e-6:
                        # poda EXATA (ver docstring) -- nunca elimina rota viavel.
                        continue
                    dfs(
                        [pp for pp in plataformas_restantes if pp != p],
                        blocos_visitados + [(p, ordem)],
                        novo_deck, novo_diesel, novo_agua,
                    )

        dfs(plataformas, [], 0.0, 0.0, 0.0)

        candidatas.sort(key=lambda c: c["rc"])
        completa = not limite_atingido[0]
        timeout_atingido = bool(limite_atingido[0] and (_time.time() - t0) > timeout_s)

        if diagnostico:
            print(f"[SILVA_PRICING] k={k} fechamentos_avaliados={avaliadas_fechamentos} "
                  f"candidatas_negativas={len(candidatas)} melhor_rc_visto={melhor_rc_visto[0]:.6f} "
                  f"completa={completa} timeout={timeout_atingido} tempo={_time.time() - t0:.2f}s")
            if not completa:
                print(f"[SILVA_PRICING][AVISO] enumeracao INTERROMPIDA "
                      f"(max_avaliacoes={max_avaliacoes} ou timeout_s={timeout_s}) -- "
                      f"NAO certifica ausencia de coluna negativa nem otimalidade para k={k}.")

        return candidatas, completa, timeout_atingido

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
        model.Params.TimeLimit = 1200
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
        if hasattr(inst, "dados_petro"):
            # Petro: u[i,k] = ocupação do convés APÓS servir i (coleta backload
            # e entrega deck do nó i). O pico de ocupação de uma visita ocorre
            # antes da entrega (ao coletar o backload), por isso a restrição
            # de pico usa a ocupação do nó anterior + backload do nó atual.
            dp = inst.dados_petro
            for k in K:
                Q = getattr(inst.veiculos[k], "cap_deck", inst.veiculos[k].capacidade)
                model.addConstr(
                    u[0, k] == gp.quicksum(
                        dp["dem_deck_load"][i] * gp.quicksum(x[j, i, k] for j in V if j != i)
                        for i in clientes
                    ),
                    name=f"carga_deposito_{k}"
                )
                for i in V:
                    model.addConstr(u[i, k] <= Q, name=f'capacidade_max_{i}_{k}')
                    for j in clientes:
                        if i != j:
                            d_j = dp["dem_deck_load"][j]
                            b_j = dp["dem_deck_backload"][j]
                            model.addConstr(
                                u[j, k] >= u[i, k] + b_j - d_j - Q * (1 - x[i, j, k]),
                                name=f'fluxo_carga_{i}_{j}_{k}'
                            )
                            model.addConstr(
                                u[i, k] + b_j <= Q + Q * (1 - x[i, j, k]),
                                name=f'pico_carga_{i}_{j}_{k}'
                            )
        else:
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

        # recursos por compartimento (Petro): diesel e agua por navio
        if hasattr(inst, "dados_petro"):
            dp = inst.dados_petro
            for k in K:
                veic = inst.veiculos[k]
                model.addConstr(
                    gp.quicksum(dp["dem_diesel"][i] * gp.quicksum(x[j, i, k] for j in V if j != i)
                                for i in clientes) <= veic.cap_diesel,
                    name=f'cap_diesel_{k}')
                model.addConstr(
                    gp.quicksum(dp["dem_agua"][i] * gp.quicksum(x[j, i, k] for j in V if j != i)
                                for i in clientes) <= veic.cap_agua,
                    name=f'cap_agua_{k}')

        # janelas de tempo múltiplas
        # BIG_M dinamico: maior due + maior servico + maior viagem (escala-agnostico)
        vel_min = min(v.velocidade for v in inst.veiculos)
        max_due = max(max(no.DUE_DATE) for no in inst.noh if no.DUE_DATE)
        max_serv = max((no.SERVICE_TIME[0] if no.SERVICE_TIME else 0.0) for no in inst.noh)
        max_trav = max(max(l) for l in inst.matriz_distancia) / vel_min
        BIG_M = float(max_due + max_serv + max_trav + 1.0)

        for k in K:
            # depósito inicial
            partida0 = inst.noh[0].READY_TIME[0] if inst.noh[0].READY_TIME else 0.0
            model.addConstr(s[0, k] == partida0, f'inicio_zero_{k}')

            for i in V:
                # clientes: escolhe exatamente uma janela se o veículo visitar
                if i in clientes:
                    n_janelas = len(inst.noh[i].READY_TIME)

                    visita_ik = gp.quicksum(x[j, i, k] for j in V if j != i)

                    model.addConstr(
                        gp.quicksum(y[i, k, w] for w in range(n_janelas)) == visita_ik,
                        name=f'escolha_janela_{i}_{k}'
                    )

                    service_i = inst.noh[i].SERVICE_TIME[0] if hasattr(inst.noh[i], 'SERVICE_TIME') and inst.noh[
                        i].SERVICE_TIME else 0

                    for w in range(n_janelas):
                        ready_w = inst.noh[i].READY_TIME[w]
                        due_w = inst.noh[i].DUE_DATE[w]

                        model.addConstr(
                            s[i, k] >= ready_w - BIG_M * (1 - y[i, k, w]),
                            name=f'tw_inicio_{i}_{k}_{w}'
                        )
                        model.addConstr(
                            s[i, k] + service_i <= due_w + BIG_M * (1 - y[i, k, w]),
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
        # if model.status == GRB.OPTIMAL:
        if model.SolCount > 0:
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
            # random.shuffle(clientes)
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

                            # sol.exportar_json_gc(inst, "solucao_gc.json")

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

    def SUB_PROG_DIN_PETRO(self, inst, pi, sigma_k, k,
                     arcos_proibidos=None, arcos_fixados=None, mu_arc=None):
        """Variante Petro de SUB_PROG_DIN: multi-janela (READY_TIME/DUE_DATE completos)
        e recursos extras diesel/agua, por navio k."""
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
        # d_deck/b_deck: entrega e backload de convés por nó (convés
        # embarca no depósito e desembarca ao longo da rota; o backload
        # é coletado ANTES da entrega em cada visita - ver formalização
        # em metodos.py:SUB_PROG_DIN_PETRO / solucao.viavel_cargas_petro)
        a, b, s, d_deck, b_deck, dd, da = [], [], [], [], [], [], []
        for i in range(nbn):
            noh = inst.noh[i]
            a.append(noh.READY_TIME[0] if hasattr(noh, "READY_TIME") and noh.READY_TIME else 0.0)
            b.append(noh.DUE_DATE[0] if hasattr(noh, "DUE_DATE") and noh.DUE_DATE else float("inf"))
            s.append(noh.SERVICE_TIME[0] if hasattr(noh, "SERVICE_TIME") and noh.SERVICE_TIME else 0.0)
            d_deck.append(getattr(noh, "DEMAND_DECK_LOAD", 0.0))
            b_deck.append(getattr(noh, "DEMAND_DECK_BACKLOAD", 0.0))
            dd.append(getattr(noh, "DEMAND_DIESEL", 0.0))
            da.append(getattr(noh, "DEMAND_AGUA", 0.0))

        cap_k = inst.veiculos[k].capacidade
        cap_diesel_k = inst.veiculos[k].cap_diesel
        cap_agua_k = inst.veiculos[k].cap_agua
        velocidade = inst.veiculos[k].velocidade

        def travel_time(i, j):
            return inst.matriz_distancia[i][j] / velocidade

        def cliente_mask(c):
            return 1 << (c - 1)

        def extensao_janela(tempo_bruto, no_dest):
            # multi-janela: acha a primeira janela r com max(tempo_bruto, aj_list[r]) + s[no_dest] <= bj_list[r] + 1e-6;
            # servico comeca em max(tempo_bruto, aj_list[r]). Sem janela viavel -> poda (None).
            aj_list = inst.noh[no_dest].READY_TIME
            bj_list = inst.noh[no_dest].DUE_DATE
            servico = s[no_dest]
            for r in range(len(bj_list)):
                inicio = max(tempo_bruto, aj_list[r])
                if inicio + servico <= bj_list[r] + 1e-6:
                    return inicio
            return None

        # ------------------ FIXOS (FORÇAR) ------------------
        # succ_fixo[i] = j  e pred_fixo[j] = i

        succ_fixo = {}
        pred_fixo = {}

        tol = 1e-6

        # dominância Pareto 3D: (custo, tempo, m). soma_d e net NÃO entram
        # na dominância porque são determinados pela mask (mesma mask ->
        # mesma soma_d/net); m depende da ORDEM de visita e por isso precisa
        # ser comparado label a label.
        def domina(cA, tA, mA, cB, tB, mB):
            return (
                    cA <= cB + tol and
                    tA <= tB + tol and
                    mA <= mB + tol and
                    (cA < cB - tol or tA < tB - tol or mA < mB - tol)
            )

        # fronteira por estado (no, mask_clientes) com lista de labels não dominados
        fronteira = {}

        rotulos = []
        abertos = deque()

        tempo_inicial = max(a[dep0], 0.0)
        rotulos.append({
            "no": dep0,
            "tempo": tempo_inicial,
            "soma_d": 0.0,
            "net": 0.0,
            "m": 0.0,
            "diesel": 0.0,
            "agua": 0.0,
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
            soma_d_i = r_atual["soma_d"]
            net_i = r_atual["net"]
            m_i = r_atual["m"]
            diesel_i = r_atual.get("diesel", 0.0)
            agua_i = r_atual.get("agua", 0.0)
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

                # capacidade (deck): recorrência soma_d/net/m (formalização
                # do pico de ocupação de convés, coleta de backload antes
                # da entrega em cada visita)
                novo_soma_d = soma_d_i
                novo_net = net_i
                novo_m = m_i
                if 1 <= j <= nbcd:
                    pico_cand = net_i + b_deck[j]
                    novo_m = max(m_i, pico_cand)
                    novo_net = net_i + b_deck[j] - d_deck[j]
                    novo_soma_d = soma_d_i + d_deck[j]
                if novo_soma_d + novo_m > cap_k + 1e-9:
                    continue

                # capacidade (diesel/agua)
                novo_diesel = diesel_i
                nova_agua = agua_i
                if 1 <= j <= nbcd:
                    novo_diesel += dd[j]
                    nova_agua += da[j]
                if novo_diesel > cap_diesel_k + 1e-9:
                    continue
                if nova_agua > cap_agua_k + 1e-9:
                    continue

                # janela de tempo (multi-janela)
                tempo_bruto = tempo_i + s[no_i] + travel_time(no_i, j)
                tempo_chegada = extensao_janela(tempo_bruto, j)
                if tempo_chegada is None:
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
                    if domina(r_old["custo_mod"], r_old["tempo"], r_old["m"],
                              custo_mod_novo, tempo_chegada, novo_m):
                        dominado = True
                        break
                if dominado:
                    continue

                nova_lista = []
                for idx_old in lista:
                    r_old = rotulos[idx_old]
                    if not r_old.get("ativo", True):
                        continue
                    if domina(custo_mod_novo, tempo_chegada, novo_m,
                              r_old["custo_mod"], r_old["tempo"], r_old["m"]):
                        rotulos[idx_old]["ativo"] = False
                    else:
                        nova_lista.append(idx_old)

                novo_rotulo = {
                    "no": j,
                    "tempo": tempo_chegada,
                    "soma_d": novo_soma_d,
                    "net": novo_net,
                    "m": novo_m,
                    "diesel": novo_diesel,
                    "agua": nova_agua,
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
                # TESTE DE FECHAMENTO no depósito final: apenas ATUALIZA a
                # melhor coluna encontrada até agora (não retorna) -- a busca
                # continua completa e a melhor coluna é retornada só ao final,
                # igual ao C++ (sub_prog_din_petro).
                # =========================
                if j != depf:

                    # 1) arco proibido?
                    if (j, depf) not in arcos_proibidos:

                        tempo_close_bruto = tempo_chegada + s[j] + travel_time(j, depf)
                        tempo_close = extensao_janela(tempo_close_bruto, depf)

                        # 2) respeita (multi-)janela do depósito?
                        if tempo_close is not None:

                            # custo reduzido ao fechar
                            custo_close = custo_mod_novo + travel_time(j, depf)
                            custo_close -= float(mu_arc.get((j, depf), 0.0))
                            custo_close -= float(sigma_k)

                            if custo_close < melhor_custo_reduzido:
                                melhor_custo_reduzido = custo_close

                                # cria rótulo final temporário só para
                                # reconstrução da rota ao final da busca
                                # (fechamento em depf: nenhuma checagem extra
                                # de convés é necessária além das podas já
                                # aplicadas na extensão para j)
                                rotulos.append({
                                    "no": depf,
                                    "tempo": tempo_close,
                                    "soma_d": novo_soma_d,
                                    "net": novo_net,
                                    "m": novo_m,
                                    "diesel": novo_diesel,
                                    "agua": nova_agua,
                                    "custo_mod": custo_close,
                                    "mask": nova_mask,
                                    "pai": idx_novo,
                                    "ativo": True
                                })
                                melhor_indice = len(rotulos) - 1

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

        from pathlib import Path
        import sys
        # base = Path(r"C:\Users\PolyanaSilva\Documents\BP_VRPTW\PD_PARA_PYTHON\PD_PARA_PYTHON")
        # >>> AJUSTE v5c: caminho relativo ao proprio metodos.py — funciona em
        # qualquer maquina, desde que a pasta PD_PARA_PYTHON esteja dentro da
        # pasta do projeto (ao lado deste arquivo).
        base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
        p_release = base / "x64" / "Release"
        p_debug = base / "x64" / "Debug"

        if p_release.exists():
            sys.path.append(str(p_release))
        if p_debug.exists():
            sys.path.append(str(p_debug))

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

    from multiprocessing import Process, Queue
    @staticmethod
    def worker_cpp(q, func_cpp, args, kwargs):
        try:
            rota, custo = func_cpp(*args, **kwargs)
            q.put((rota, custo, None))
        except Exception as e:
            q.put((None, None, str(e)))

    def chamar_cpp_timeout(self, func_cpp, args=(), kwargs=None, timeout=600):
        from multiprocessing import Process, Queue
        from queue import Empty
        self._ultimo_timeout_cpp = False
        if kwargs is None: kwargs = {}
        q = Queue(); p = Process(target=Metodos.worker_cpp, args=(q, func_cpp, args, kwargs)); p.start(); p.join(timeout)
        if p.is_alive():
            self._ultimo_timeout_cpp = True
            print(f"[TIMEOUT CPP] excedeu {timeout}s")
            p.terminate(); p.join(); q.close(); q.join_thread()
            return None, None
        try:
            rota, custo, erro = q.get(timeout=1)
        except Empty:
            print("[ERRO CPP] processo terminou sem retornar resultado")
            return None, None
        finally:
            q.close(); q.join_thread()
        if erro is not None:
            print("Erro CPP:", erro)
            return None, None
        return rota, custo

    @staticmethod
    def worker_cpp_multi(q, func_cpp, args, kwargs):
        """Igual a worker_cpp, mas para as interfaces *_multi, que retornam
        (candidatas, busca_completa, timeout) em vez de (rota, custo)."""
        try:
            candidatas, busca_completa, timeout_flag = func_cpp(*args, **kwargs)
            q.put((candidatas, busca_completa, timeout_flag, None))
        except Exception as e:
            q.put(([], False, False, str(e)))

    def chamar_cpp_timeout_multi(self, func_cpp, args=(), kwargs=None, timeout=600):
        """Igual a chamar_cpp_timeout, mas para as interfaces *_multi (secao 5).
        Nao reaproveita chamar_cpp_timeout/worker_cpp para nao alterar o
        contrato (rota, custo) usado pelas chamadas antigas (inclusive Solomon)."""
        from multiprocessing import Process, Queue
        from queue import Empty
        self._ultimo_timeout_cpp = False
        if kwargs is None: kwargs = {}
        q = Queue(); p = Process(target=Metodos.worker_cpp_multi, args=(q, func_cpp, args, kwargs)); p.start(); p.join(timeout)
        if p.is_alive():
            self._ultimo_timeout_cpp = True
            print(f"[TIMEOUT CPP] excedeu {timeout}s")
            p.terminate(); p.join(); q.close(); q.join_thread()
            return [], False, True
        try:
            candidatas, busca_completa, timeout_flag, erro = q.get(timeout=1)
        except Empty:
            print("[ERRO CPP] processo terminou sem retornar resultado")
            return [], False, False
        finally:
            q.close(); q.join_thread()
        if erro is not None:
            print("Erro CPP:", erro)
            return [], False, False
        return candidatas, busca_completa, timeout_flag

    def SUB_PROG_DIN_PW_CPP_NOVA(self, inst, pi, sigma_k, k,
                                 arcos_proibidos=None, arcos_fixados=None, mu_arc=None,
                                 widening_seq=None, eps=1e-6):
        import sys
        import numpy as np
        from pathlib import Path

        # caminho do .pyd
        from pathlib import Path
        import sys
        # base = Path(r"C:\Users\PolyanaSilva\Documents\BP_VRPTW\PD_PARA_PYTHON\PD_PARA_PYTHON")
        # >>> AJUSTE v5c: caminho relativo ao proprio metodos.py — funciona em
        # qualquer maquina, desde que a pasta PD_PARA_PYTHON esteja dentro da
        # pasta do projeto (ao lado deste arquivo).
        base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
        p_release = base / "x64" / "Release"
        p_debug = base / "x64" / "Debug"

        if p_release.exists():
            sys.path.insert(0, str(p_release))
        elif p_debug.exists():
            sys.path.insert(0, str(p_debug))

        import vrptw_pd

        if arcos_proibidos is None:
            arcos_proibidos = set()
        if arcos_fixados is None:
            arcos_fixados = set()
        if mu_arc is None:
            mu_arc = {}
        if widening_seq is None:
            widening_seq = [4, 8, -1]  # -1 = ALL

        nbn = inst.nbn
        nbcd = inst.nbcd
        dep0 = 0
        depf = nbn - 1

        cap_k = float(inst.veiculos[k].capacidade)
        vel = float(inst.veiculos[k].velocidade)

        # vetores da instância
        a = np.zeros(nbn, dtype=np.float64)
        b = np.zeros(nbn, dtype=np.float64)
        s = np.zeros(nbn, dtype=np.float64)
        d = np.zeros(nbn, dtype=np.float64)

        for i in range(nbn):
            noh = inst.noh[i]
            a[i] = noh.READY_TIME[0] if noh.READY_TIME else 0.0
            b[i] = noh.DUE_DATE[0] if noh.DUE_DATE else 1e18
            s[i] = noh.SERVICE_TIME[0] if noh.SERVICE_TIME else 0.0
            d[i] = float(getattr(noh, "DEMAND", 0.0))

        dist = np.asarray(inst.matriz_distancia, dtype=np.float64)
        tt = dist / vel

        pi_list = np.asarray(pi, dtype=np.float64).tolist()

        # usa versão simples se não há branch/mu
        tem_branch = (
                len(arcos_proibidos) > 0 or
                len(arcos_fixados) > 0 or
                len(mu_arc) > 0
        )
        ###################fim das alteracoes que estavam dando bug

        import numpy as np

        pi_np = np.asarray(pi, dtype=np.float64)

        if len(pi_np) != nbcd:
            raise ValueError(f"pi com tamanho errado: len(pi)={len(pi_np)} | nbcd={nbcd}")

            # ===== MU =====
        if mu_arc is None:
            mu_flat = np.zeros((0, 3), dtype=np.float64)
        else:
            mu_list = []
            for (i, j), val in mu_arc.items():
                mu_list.append([i, j, float(val)])
            mu_flat = np.asarray(mu_list, dtype=np.float64)

        # ===== ARCOS PROIBIDOS =====
        forbid_list = []

        if arcos_proibidos:
            for (i, j, kk) in arcos_proibidos:
                if kk == k:
                    forbid_list.append([i, j])

        forbid_flat = np.asarray(forbid_list, dtype=np.int32)

        # ===== ARCOS FIXADOS =====
        req_i = -1
        req_j = -1

        if arcos_fixados:
            for (i, j, kk) in arcos_fixados:
                if kk == k:
                    req_i = int(i)
                    req_j = int(j)
                    break

        ###################fim das alteracoes que estavam dando bug

        if not tem_branch:
            return self.chamar_cpp_timeout(
                vrptw_pd.sub_prog_din_pw_branch_greedy,
                (
                    tt, a.tolist(), b.tolist(), s.tolist(), d.tolist(),
                    pi_np.tolist(),
                    float(sigma_k), cap_k,
                    int(nbcd), int(dep0), int(depf),
                    list(map(int, widening_seq)),
                    float(eps),
                    mu_flat.tolist(),
                    forbid_flat.tolist(),
                    req_i, req_j
                ),
                timeout=600
            )

        # versão com mu, arcos proibidos e arcos fixados
        mu_flat = np.zeros(nbn * nbn, dtype=np.float64)
        for chave, val in mu_arc.items():
            i, j = chave[0], chave[1]
            mu_flat[int(i) * nbn + int(j)] = float(val)

        forbid_flat = np.zeros(nbn * nbn, dtype=np.uint8)
        for arco in arcos_proibidos:
            i, j = arco[0], arco[1]
            forbid_flat[int(i) * nbn + int(j)] = 1

        req_i = [int(arco[0]) for arco in arcos_fixados]
        req_j = [int(arco[1]) for arco in arcos_fixados]

        """
        return vrptw_pd.sub_prog_din_pw_branch_greedy(
            tt,
            a.tolist(),
            b.tolist(),
            s.tolist(),
            d.tolist(),
            pi_list,
            float(sigma_k),
            cap_k,
            int(nbcd),
            int(dep0),
            int(depf),
            list(map(int, widening_seq)),
            float(eps),
            mu_flat.tolist(),
            forbid_flat.tolist(),
            req_i,
            req_j
        )
        """
        return self.chamar_cpp_timeout(
            vrptw_pd.sub_prog_din_pw_branch_greedy,
            (
                tt,
                a.tolist(),
                b.tolist(),
                s.tolist(),
                d.tolist(),
                pi_list,
                float(sigma_k),
                cap_k,
                int(nbcd),
                int(dep0),
                int(depf),
                list(map(int, widening_seq)),
                float(eps),
                mu_flat.tolist(),
                forbid_flat.tolist(),
                req_i,
                req_j
            ),
            timeout=600
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

        # return vrptw_pd.SUB_PROG_DIN(tt, a, b, s, d, pi_np, float(sigma_k), cap_k, F, FX, MU)
        return vrptw_pd.sub_prog_din_pw_greedy(tt, a, b, s, d, pi_np, float(sigma_k), cap_k, F, FX, MU)

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



    #petrobras

    def menor_inicio_viavel_mtw(self, no, chegada, exige_termino_janela=False):
        """
        Retorna o menor instante viável dentro de alguma janela do nó.
        Unidade: segundos.
        """
        serv = no.SERVICE_TIME[0] if no.SERVICE_TIME else 0

        for ini, fim in zip(no.READY_TIME, no.DUE_DATE):
            inicio_servico = max(chegada, ini)

            if exige_termino_janela:
                if inicio_servico + serv <= fim:
                    return inicio_servico
            else:
                if inicio_servico <= fim:
                    return inicio_servico

        return None

    def avaliar_rota_petro(self, inst, k, seq, exige_termino_janela=False):
        """
        Avalia uma rota Petro.
        seq exemplo: [0, 1, 5, 8, depf]

        Unidade:
          matriz_distancia = segundos
          SERVICE_TIME = segundos
          READY/DUE = segundos
        """
        depf = inst.nbn - 1

        if not seq or seq[0] != 0 or seq[-1] != depf:
            return {"factivel": False, "motivo": "rota_sem_deposito"}

        veic = inst.veiculos[k]

        cap_deck = getattr(veic, "cap_deck", veic.capacidade)
        cap_diesel = getattr(veic, "cap_diesel", 10 ** 18)
        cap_agua = getattr(veic, "cap_agua", 10 ** 18)

        deck = 0
        diesel = 0
        agua = 0

        tempo = inst.noh[0].READY_TIME[0] if inst.noh[0].READY_TIME else 0
        chegadas = [tempo]
        custo = 0

        for pos in range(1, len(seq)):
            i = seq[pos - 1]
            j = seq[pos]

            serv_i = inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0
            viagem = inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

            if viagem < 0:
                return {"factivel": False, "motivo": "arco_invalido", "arco": (i, j)}

            custo += viagem

            chegada_bruta = tempo + serv_i + viagem
            inicio_j = self.menor_inicio_viavel_mtw(
                inst.noh[j],
                chegada_bruta,
                exige_termino_janela=exige_termino_janela
            )

            if inicio_j is None:
                return {
                    "factivel": False,
                    "motivo": "janela",
                    "no": j,
                    "chegada_bruta": chegada_bruta,
                }

            tempo = inicio_j
            chegadas.append(tempo)

            if 1 <= j <= inst.nbcd:
                no_j = inst.noh[j]

                deck += getattr(no_j, "DEMAND_DECK_LOAD", 0)
                deck += getattr(no_j, "DEMAND_DECK_BACKLOAD", 0)
                diesel += getattr(no_j, "DEMAND_DIESEL", 0)
                agua += getattr(no_j, "DEMAND_AGUA", 0)

                if deck > cap_deck:
                    return {"factivel": False, "motivo": "cap_deck", "deck": deck}

                if diesel > cap_diesel:
                    return {"factivel": False, "motivo": "cap_diesel", "diesel": diesel}

                if agua > cap_agua:
                    return {"factivel": False, "motivo": "cap_agua", "agua": agua}

        return {
            "factivel": True,
            "custo": custo,
            "chegadas": chegadas,
            "deck": deck,
            "diesel": diesel,
            "agua": agua,
        }

    def custo_reduzido_rota_petro(self, inst, seq, custo, pi, sigma_k):
        """
        Custo reduzido da coluna.
        """
        soma_pi = 0.0

        for no in seq:
            if 1 <= no <= inst.nbcd:
                soma_pi += pi[no - 1]

        return custo - soma_pi - sigma_k

    def SUB_HEUR_INSERCAO_PETRO(self, inst, pi, sigma_k, k, exige_termino_janela=False):
        """
        Pricing heurístico inicial para Petro.
        Monta rota por melhor inserção.
        Retorna coluna se achar custo reduzido negativo.
        """
        depf = inst.nbn - 1
        clientes = list(range(1, inst.nbcd + 1))

        rota = [0, depf]
        nao_visitados = set(clientes)

        melhor_global = None
        melhor_rc_global = float("inf")

        while True:
            melhor_candidato = None
            melhor_rc_candidato = float("inf")

            for cli in list(nao_visitados):
                for pos in range(1, len(rota)):
                    nova_seq = rota[:pos] + [cli] + rota[pos:]

                    aval = self.avaliar_rota_petro(
                        inst,
                        k,
                        nova_seq,
                        exige_termino_janela=exige_termino_janela
                    )

                    if not aval["factivel"]:
                        continue

                    rc = self.custo_reduzido_rota_petro(
                        inst,
                        nova_seq,
                        aval["custo"],
                        pi,
                        sigma_k
                    )

                    if rc < melhor_rc_candidato:
                        melhor_rc_candidato = rc
                        melhor_candidato = {
                            "seq": nova_seq,
                            "cli": cli,
                            "aval": aval,
                            "rc": rc,
                        }

            if melhor_candidato is None:
                break

            rota = melhor_candidato["seq"]
            nao_visitados.remove(melhor_candidato["cli"])

            if melhor_candidato["rc"] < melhor_rc_global:
                melhor_rc_global = melhor_candidato["rc"]
                melhor_global = melhor_candidato

        if melhor_global is None:
            return None, None

        if melhor_rc_global >= -1e-6:
            return None, melhor_rc_global

        seq = melhor_global["seq"]
        custo = melhor_global["aval"]["custo"]

        bin_xij = [0] * inst.nbcd
        for no in seq:
            if 1 <= no <= inst.nbcd:
                bin_xij[no - 1] = 1

        nova_rota = {
            "clientes": seq,
            "custo": custo,
            "bin_xij": bin_xij,
        }

        return nova_rota, melhor_rc_global