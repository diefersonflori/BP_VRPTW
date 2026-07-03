import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
import time
import csv
import random
import math
from datetime import datetime

from multiprocessing import freeze_support
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)
from concurrent.futures import ProcessPoolExecutor, as_completed


def rodar_caso(args):
    import os, sys, time, random, math
    from instancia import Instancia
    from solucao import Solucao
    from metodos import Metodos, NoBP

    (arquivo_instancia, tam, cap, nbv_inst, ninst,
     nome_base, nome_inst, gamma_PMAX, SM, gamma_ini_val,
     gamma_pi_min, fo_target_inst, tabu, SEED_DEBUG) = args

    os.makedirs("GammaParalelo50", exist_ok=True)
    log_path = f"GammaParalelo50/{nome_base}_SM{SM}_gmax{gamma_PMAX}.txt"
    _stdout = sys.__stdout__
    log_file = open(log_path, "w", encoding="utf-8")

    msg_inicio = f"[INICIO]   {nome_base} | SM={SM} | gmax={gamma_PMAX}"
    print(msg_inicio, flush=True, file=_stdout)
    print(msg_inicio, flush=True, file=log_file)

    try:
        inst = Instancia()
        inst.nbcd = tam
        inst.nbn = tam + 2
        inst.nomeInst = arquivo_instancia
        inst.nbv = nbv_inst
        inst.ninst = ninst
        inst.leitura(arquivo_instancia)
        for v in inst.veiculos:
            v.capacidade = cap
            v.velocidade = 10

        metod = Metodos(inst)
        metod.TABU_TENURE = tabu
        inst.usar_estabilizacao = True    # COM estabilizacao -- calibracao de gamma_max
        inst.nbconstrutiva = 10
        inst.iteraSemMelhora = SM
        random.seed(SEED_DEBUG)

        sol_pool = Solucao(inst.nbv, inst.nbcd)
        sol_pool.FO_TARGET = fo_target_inst
        sol_pool.time_initial = time.time()
        sol_pool.TIME_TARGET = 3600
        sol_pool.TIME_MAX = 3600
        sol_pool.gamma_pi = gamma_ini_val
        sol_pool.gamma_pi_inicial = gamma_ini_val
        sol_pool.gamma_pi_min = gamma_pi_min
        sol_pool.gamma_pi_max = gamma_PMAX

        metod.init_pool_vazio(inst, sol_pool)
        metod._log_file = log_file  # redireciona _print da construtiva para o log antes de B&P setar
        metod.gera_solucao_inicial(inst, sol_pool)

        # --- custo e sequências da construtiva ---
        custo_construt = sum(
            float(c) for k in range(inst.nbv)
            for c in sol_pool.rotas[k].get("custo", [])
        )
        n_art = sum(
            1 for k in range(inst.nbv)
            for p in range(len(sol_pool.rotas[k].get('artificial', [])))
            if sol_pool.rotas[k]['artificial'][p]
        )
        seqs_construt = []
        for k in range(inst.nbv):
            seq = sol_pool.rotas[k]['sequencia_rota'][0] if sol_pool.rotas[k]['sequencia_rota'] else []
            art = sol_pool.rotas[k]['artificial'][0] if sol_pool.rotas[k]['artificial'] else False
            clientes = [c for c in seq if 1 <= c <= inst.nbcd]
            tag = "*" if art else ""
            seqs_construt.append(f"V{k}{tag}:{clientes}")
        seq_str_construt = " | ".join(seqs_construt)

        if n_art > 0:
            msg_aviso = f"[AVISO]    {nome_base} | SM={SM} | gmax={gamma_PMAX} | heuristica vencedora precisou de rota artificial ({n_art} cliente(s))"
            print(msg_aviso, flush=True, file=_stdout)
            print(msg_aviso, flush=True, file=log_file)

        msg_construt = f"[CONSTRUT] {nome_base} | SM={SM} | gmax={gamma_PMAX} | custo={custo_construt:.1f} | art={n_art} | {seq_str_construt}"
        print(msg_construt, flush=True, file=_stdout)
        print(msg_construt, flush=True, file=log_file)

        # --- B&P ---
        t0 = time.time()
        inst.usar_estabilizacao=False
        metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD", log_file=log_file)
        tempo_bp = time.time() - t0

        ub = metod.best_obj if metod.best_obj > 0 else float("inf")

        # LB CONFIÁVEL: só considera nós que provaram convergência do CG
        # (cg_convergiu=True, sem timeout, slack~0). Ver branch_and_price_global.
        lb_confiavel_val = getattr(sol_pool, "lb_global_confiavel", None)
        # LB HEURÍSTICA (legado): mínimo histórico entre TODOS os nós já
        # resolvidos, confiáveis ou não -- mantida só para referência/diagnóstico,
        # NÃO deve ser usada para afirmar otimalidade.
        lb_heuristica = getattr(sol_pool, "melhor_lp_valido", float("inf"))

        if lb_confiavel_val is not None:
            lb = lb_confiavel_val
            lb_certificado = True
        else:
            lb = lb_heuristica if (lb_heuristica != float("inf") and lb_heuristica > 0) else ub
            lb_certificado = False

        gap = abs(ub - lb) / max(abs(ub), 1e-9) * 100 if not math.isinf(ub) else float("inf")
        n_nos = metod.total_nos
        n_cols = metod.total_colunas

        # sequências da solução B&P
        seqs_bp = []
        if sol_pool.rotas_escolhidas:
            for k in sorted(sol_pool.rotas_escolhidas.keys()):
                for seq in sol_pool.rotas_escolhidas[k]['sequencias']:
                    clientes = [c for c in seq if 1 <= c <= inst.nbcd]
                    seqs_bp.append(f"V{k}:{clientes}")
        seq_str_bp = " | ".join(seqs_bp) if seqs_bp else "sem_solucao_inteira"
        seq_str_bp = seq_str_bp.replace('\n', ' | ')

        gap_str = f"{gap:.2f}%" if not math.isinf(gap) else "inf"
        flag = " ***" if (not math.isinf(gap) and gap > 0.01) else ""
        tag_cert = "" if lb_certificado else " [LB NAO CERTIFICADA]"

        msg_bp_fim = f"[BP_FIM]  {nome_base} | SM={SM} | gmax={gamma_PMAX} | LB={lb:.2f} | UB={ub:.2f} | gap={gap_str} | nos={n_nos} | cols={n_cols} | t={tempo_bp:.1f}s{flag}{tag_cert}"
        msg_seq_bp = f"[SEQ_BP]  {nome_base} | SM={SM} | gmax={gamma_PMAX} | {seq_str_bp}"
        print(msg_bp_fim, flush=True, file=_stdout)
        print(msg_bp_fim, flush=True, file=log_file)
        print(msg_seq_bp, flush=True, file=_stdout)
        print(msg_seq_bp, flush=True, file=log_file)

        log_file.flush(); log_file.close()

        return {
            "nome_base": nome_base, "SM": SM, "gamma_max": gamma_PMAX,
            "custo_construt": custo_construt, "n_art": n_art,
            "lb": lb, "ub": ub, "gap": gap, "lb_certificado": lb_certificado,
            "n_nos": n_nos, "n_cols": n_cols, "tempo_bp": tempo_bp,
            "seq_bp": seq_str_bp,
        }

    except Exception as e:
        import traceback
        msg = traceback.format_exc()
        print(f"[ERRO] {nome_base} SM={SM} gmax={gamma_PMAX}: {e}\n{msg}", flush=True, file=log_file)
        try: log_file.flush(); log_file.close()
        except: pass
        return None


def main():
    SEED_DEBUG = 123

    tamanhos = [50]
    capacidade_por_tamanho = {25: 200, 50: 200}
    gamma_ini_por_tamanho = {25: 30, 50: 40}
    gamma_pi_min_por_tamanho = {25: 10, 50: 10}

    gamma_inicial_caixa = {
        25: {"c": 10},
        50: {"c": [15], "r": [80], "rc": [80]},
    }

    SM_FIXO = 20  # fixado com base na calibracao anterior (indice balanceado gap x tempo)
    GAMMA_MAX_LIST = [20, 50, 100, 200, 400]  # 20 = perto da escala natural de arco (~7-17);
                                                # 50 = ancora da calibracao de 25 clientes;
                                                # 100/200 = grid original; 400 = quase irrestrito

    tabu = 0
    MAX_WORKERS = 1

    #    "instancias/c101N.txt", "instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",
    todas_instancias = [
        "instancias/c105.txt", "instancias/c106.txt", "instancias/c107.txt", "instancias/c108.txt",
        "instancias/c109.txt",
        "instancias/r101.txt", "instancias/r102.txt", "instancias/r103.txt", "instancias/r104.txt",
        "instancias/r105.txt", "instancias/r106.txt", "instancias/r107.txt", "instancias/r108.txt",
        "instancias/r109.txt", "instancias/r110.txt", "instancias/r111.txt", "instancias/r112.txt",
        "instancias/rc101.txt", "instancias/rc102.txt", "instancias/rc103.txt", "instancias/rc104.txt",
        "instancias/rc105.txt", "instancias/rc106.txt", "instanc+ias/rc107.txt", "instancias/rc108.txt",
    ]

    NBV_POR_TAM = {
        25: {
            "c101n": 3, "c101": 3, "c102": 3, "c103": 3, "c104": 3,
            "c105": 3, "c106": 3, "c107": 3, "c108": 3, "c109": 3,
            "r101": 8, "r102": 7, "r103": 5, "r104": 4,
            "r105": 6, "r106": 5, "r107": 4, "r108": 4,
            "r109": 5, "r110": 4, "r111": 4, "r112": 4,
            "rc101": 4, "rc102": 3, "rc103": 3, "rc104": 3,
            "rc105": 4, "rc106": 3, "rc107": 3, "rc108": 3,
        },
        50: {
            "c101n": 5, "c101": 5, "c102": 5, "c103": 5, "c104": 5,
            "c105": 5, "c106": 5, "c107": 5, "c108": 5, "c109": 5,
            "r101": 12, "r102": 11, "r103": 9, "r104": 6,
            "r105": 9, "r106": 8, "r107": 7, "r108": 6,
            "r109": 8, "r110": 7, "r111": 7, "r112": 6,
            "rc101": 8, "rc102": 7, "rc103": 6, "rc104": 5,
            "rc105": 8, "rc106": 6, "rc107": 6, "rc108": 6,
        },
    }

    FO_TARGET = {
        25: {
            "c101n": 191.3, "c102": 190.3, "c103": 190.3, "c104": 186.9,
            "c105": 191.3, "c106": 191.3, "c107": 191.3, "c108": 191.3, "c109": 191.3,
            "r101": 617.1, "r102": 547.1, "r103": 454.6, "r104": 416.9,
            "r105": 530.5, "r106": 465.4, "r107": 424.3, "r108": 397.3,
            "r109": 441.3, "r110": 444.1, "r111": 428.8, "r112": 393.0,
            "rc101": 461.1, "rc102": 351.8, "rc103": 332.8, "rc104": 306.6,
            "rc105": 411.3, "rc106": 345.5, "rc107": 298.3, "rc108": 294.5,
        },
        50: {
            "c101n": 362.4, "c101": 362.4, "c102": 361.4, "c103": 361.4,
            "c104": 358.0, "c105": 362.4, "c106": 362.4, "c107": 362.4,
            "c108": 362.4, "c109": 362.4,
            "r101": 1044.0, "r102": 909.0, "r103": 772.9, "r104": 625.4,
            "r105": 899.3, "r106": 793.0, "r107": 711.1, "r108": 617.7,
            "r109": 786.8, "r110": 697.0, "r111": 707.2, "r112": 630.2,
            "rc101": 944.0, "rc102": 822.5, "rc103": 710.9, "rc104": 545.8,
            "rc105": 855.3, "rc106": 723.2, "rc107": 642.7, "rc108": 598.1,
        },
    }

    def normaliza(arquivo):
        return os.path.basename(arquivo).lower().replace(".txt", "")

    def familia(nome_base):
        if nome_base.startswith("rc"): return "rc"
        if nome_base.startswith("r"): return "r"
        return "c"

    tarefas = []
    for tam in tamanhos:
        cap = capacidade_por_tamanho[tam]
        nomes_validos = set(FO_TARGET.get(tam, {}).keys())
        lista_inst = [a for a in todas_instancias if normaliza(a) in nomes_validos]

        for ninst, arquivo in enumerate(lista_inst):
            nome_base = normaliza(arquivo)
            nome_inst = os.path.basename(arquivo).lower()
            nbv_inst = NBV_POR_TAM.get(tam, {}).get(nome_base)
            if nbv_inst is None:
                continue
            fo_target = FO_TARGET.get(tam, {}).get(nome_base, -1)
            fam = familia(nome_base)
            gamma_pi_min = gamma_pi_min_por_tamanho[tam]

            _gini_raw = gamma_inicial_caixa[tam].get(fam, [gamma_ini_por_tamanho[tam]])
            gamma_ini_val = (_gini_raw[0] if isinstance(_gini_raw, list) else _gini_raw)
            SM = SM_FIXO

            for gamma_PMAX in GAMMA_MAX_LIST:
                tarefas.append((
                    arquivo, tam, cap, nbv_inst, ninst,
                    nome_base, nome_inst, gamma_PMAX, SM, gamma_ini_val,
                    gamma_pi_min, fo_target, tabu, SEED_DEBUG
                ))

    sys.stdout = sys.__stdout__
    print(f"Total de tarefas: {len(tarefas)} | SM_FIXO={SM_FIXO} | GAMMA_MAX_LIST={GAMMA_MAX_LIST} | estabilizacao=True")

    resumo = {}

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(rodar_caso, t): t for t in tarefas}
        for futuro in as_completed(futuros):
            try:
                resultado = futuro.result()
                if resultado is None:
                    print("[ERRO] resultado None")
                    continue
                nome = resultado['nome_base']
                gmax = resultado['gamma_max']
                if nome not in resumo:
                    resumo[nome] = {}
                resumo[nome][gmax] = resultado
            except Exception as e:
                print(f"[ERRO futuro] {e}")

    print("\n" + "="*100)
    for gmax in GAMMA_MAX_LIST:
        print(f"\n=== SM={SM_FIXO} | gamma_max={gmax} ===")
        n_ok = 0
        n_ok_certificado = 0
        for nome in sorted(resumo.keys()):
            r = resumo[nome].get(gmax)
            if r is None:
                continue
            flag = " ***" if r['gap'] > 0.01 else ""
            cert = r.get('lb_certificado', False)
            tag_cert = "" if cert else " [nao certificado]"
            print(f"  {nome:12s} | LB={r['lb']:.2f} | UB={r['ub']:.2f} | gap={r['gap']:.2f}% | nos={r['n_nos']} | cols={r['n_cols']} | t={r['tempo_bp']:.1f}s{flag}{tag_cert}")
            if r['gap'] <= 0.01:
                n_ok += 1
                if cert:
                    n_ok_certificado += 1
        print(f"  Ótimos (gap<=0.01%, inclui não-certificados): {n_ok}/29")
        print(f"  Ótimos CERTIFICADOS (LB confiável de fato): {n_ok_certificado}/29")


if __name__ == "__main__":
    freeze_support()
    main()
