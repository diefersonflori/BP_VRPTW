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

# Bateria COM estabilizacao dual: sweep de gamma_ini nas 29 instancias Solomon de 50 clientes.
MAX_WORKERS = 1


def rodar_caso(args):
    import os, sys, time, random, math
    from instancia import Instancia
    from solucao import Solucao
    from metodos import Metodos, NoBP

    (arquivo_instancia, tam, cap, nbv_inst, ninst,
     nome_base, nome_inst, gamma_PMAX, SM, gamma_ini_val,
     gamma_pi_min, fo_target_inst, tabu, SEED_DEBUG) = args

    os.makedirs("resultados_COM_estab_gamma_sweep_50", exist_ok=True)
    log_path = f"resultados_COM_estab_gamma_sweep_50/{nome_base}_SM{SM}_gini{gamma_ini_val}_G{gamma_PMAX}.txt"
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
        #inst.leitura(arquivo_instancia)

        inst.leitura_petro(r"instancias\Petro_instancias\10n-1k-3c-1r_testeUSP_v33.json", escala=3600)

        print("nbcd=%d nbn=%d nbv=%d cap=%d cap_deck=%d cap_diesel=%d cap_agua=%d" %
              (
                  inst.nbcd,
                  inst.nbn,
                  inst.nbv,
                  inst.veiculos[0].capacidade,
                  inst.veiculos[0].cap_deck,
                  inst.veiculos[0].cap_diesel,
                  inst.veiculos[0].cap_agua,
              ))

        for no in inst.noh:
            print(
                "no %2d | lat=%10.6f | lon=%10.6f | dem=%4d | deckL=%4d | deckB=%4d | diesel=%4d | agua=%4d | serv=%s | READY=%s | DUE=%s" %
                (
                    no.id,
                    no.YCOORD, no.XCOORD,
                    no.DEMAND, no.DEMAND_DECK_LOAD,
                    no.DEMAND_DECK_BACKLOAD, no.DEMAND_DIESEL,
                    no.DEMAND_AGUA, no.SERVICE_TIME,
                    no.READY_TIME, no.DUE_DATE,
                )
            )

        print("\n--- CONFERENCIA DA ESTRUTURA (unidade: segundos) ---")

        # cabeçalho
        print("%8s" % "", end="")
        for j in range(inst.nbn):
            print("%8d" % j, end="")
        print()

        # linhas
        for i in range(inst.nbn):
            print("%8d" % i, end="")
            for j in range(inst.nbn):
                print("%8d" % inst.matriz_distancia[i][j], end="")
            print()



        for v in inst.veiculos:
            v.capacidade = cap
            v.velocidade = 10

        metod = Metodos(inst)
        metod.TABU_TENURE = tabu
        inst.usar_estabilizacao = True    # COM estabilizacao dual
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

        #metod.gera_solucao_inicial(inst, sol_pool)

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
        sys.stdout = log_file  # silencia console durante B&P
        sys.stderr = log_file
        metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")
        sys.stdout = _stdout  # restaura console
        sys.stderr = _stdout
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

        # gap contra a BKS (FO_TARGET), para o CSV de calibracao de gamma_max
        gap_bks = ""
        if fo_target_inst not in (None, 0, -1) and not math.isinf(ub):
            gap_bks = ((ub - fo_target_inst) / fo_target_inst) * 100.0

        return {
            "arquivo_instancia": arquivo_instancia,
            "nome_base": nome_base, "SM": SM, "gamma_max": gamma_PMAX,
            "gamma_ini": gamma_ini_val, "fo_target": fo_target_inst,
            "custo_construt": custo_construt, "n_art": n_art,
            "lb": lb, "ub": ub, "gap": gap, "lb_certificado": lb_certificado,
            "n_nos": n_nos, "n_cols": n_cols, "tempo_bp": tempo_bp,
            "seq_bp": seq_str_bp,
            "fo_bp": ub,
            "gap_bks": gap_bks,
            "motivo": getattr(sol_pool, "motivoConv", ""),
            "iteracoes": getattr(sol_pool, "nb_iteracoes", ""),
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
    capacidade_por_tamanho = {50: 200}
    gamma_pi_min_por_tamanho = {50: 10}

    SM_FIXO = 30
    GAMMA_MAX_FIXO = 600
    GAMMA_INI_POR_FAMILIA = {
        "c": [15, 30, 60],
        "r": [40, 80, 150],
        "rc": [40, 80, 150],
    }

    tabu = 0

    todas_instancias = [
        "instancias/c101N.txt", "instancias/c102.txt", "instancias/c103.txt",
        "instancias/c104.txt", "instancias/c105.txt", "instancias/c106.txt",
        "instancias/c107.txt", "instancias/c108.txt", "instancias/c109.txt",
        "instancias/r101.txt", "instancias/r102.txt", "instancias/r103.txt",
        "instancias/r104.txt", "instancias/r105.txt", "instancias/r106.txt",
        "instancias/r107.txt", "instancias/r108.txt", "instancias/r109.txt",
        "instancias/r110.txt", "instancias/r111.txt", "instancias/r112.txt",
        "instancias/rc101.txt", "instancias/rc102.txt", "instancias/rc103.txt",
        "instancias/rc104.txt", "instancias/rc105.txt", "instancias/rc106.txt",
        "instancias/rc107.txt", "instancias/rc108.txt",
    ]

    NBV_POR_TAM = {
        50: {
            "c101n": 5, "c102": 5, "c103": 5, "c104": 5, "c105": 5,
            "c106": 5, "c107": 5, "c108": 5, "c109": 5,
            "r101": 12, "r102": 11, "r103": 9, "r104": 6,
            "r105": 9, "r106": 8, "r107": 7, "r108": 6,
            "r109": 8, "r110": 7, "r111": 7, "r112": 6,
            "rc101": 8, "rc102": 7, "rc103": 6, "rc104": 5,
            "rc105": 8, "rc106": 6, "rc107": 6, "rc108": 6,
        },
    }

    FO_TARGET = {
        50: {
            "c101n": 362.4, "c102": 361.4, "c103": 361.4, "c104": 358.0, "c105": 362.4,
            "c106": 362.4, "c107": 362.4, "c108": 362.4, "c109": 362.4,
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
        if nome_base.startswith("rc"):
            return "rc"
        if nome_base.startswith("r"):
            return "r"
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
            gamma_pi_min = gamma_pi_min_por_tamanho[tam]
            fam = familia(nome_base)
            SM = SM_FIXO
            gamma_PMAX = GAMMA_MAX_FIXO

            for gamma_ini_val in GAMMA_INI_POR_FAMILIA[fam]:
                tarefas.append((
                    arquivo, tam, cap, nbv_inst, ninst,
                    nome_base, nome_inst, gamma_PMAX, SM, gamma_ini_val,
                    gamma_pi_min, fo_target, tabu, SEED_DEBUG
                ))

    sys.stdout = sys.__stdout__

    ARQ_CALIB_GMAX = "resultados_COM_estab_gamma.csv"
    if os.path.exists(ARQ_CALIB_GMAX):
        os.remove(ARQ_CALIB_GMAX)

    campos_csv = [
        "instancia", "gamma_ini", "gamma_max", "SM", "fo_bp", "fo_target",
        "gap_bks", "nos_bp", "colunas_bp", "iteracoes", "tempo_bp", "motivo",
        "lb_bp", "lb_certificado",
    ]

    with open(ARQ_CALIB_GMAX, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(campos_csv)

    def _csv_val(v, ndigits=4):
        if v is None or v == "":
            return ""
        if isinstance(v, float) and math.isinf(v):
            return ""
        if isinstance(v, float):
            return round(v, ndigits)
        return v

    print(f"[GRADE] Total de tarefas: {len(tarefas)} | "
          f"COM estabilizacao | SM=30 | gamma_max=600 | "
          f"gamma_ini por familia: C={[15, 30, 60]} R/RC={[40, 80, 150]}")
    for (_arquivo, _tam, _cap, _nbv_inst, _ninst, _nome_base, _nome_inst, _gamma_PMAX, _SM,
         _gamma_ini_val, _gamma_pi_min, _fo_target, _tabu, _SEED_DEBUG) in tarefas:
        print(f"[GRADE]   {_nome_base} | gamma_ini={_gamma_ini_val} | "
              f"gamma_max=600 | SM=30 | estab=True")

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(rodar_caso, t): t for t in tarefas}
        for futuro in as_completed(futuros):
            try:
                resultado = futuro.result()
                if resultado is None:
                    print("[ERRO] resultado None")
                    continue

                # Escrita incremental: como o loop as_completed roda so no
                # processo principal (nunca em paralelo), cada linha e
                # anexada e flushada aqui sem risco de corrida entre
                # processos -- os workers (ProcessPoolExecutor) nao tocam
                # neste arquivo, so retornam o resultado.
                with open(ARQ_CALIB_GMAX, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow([
                        resultado["arquivo_instancia"],
                        resultado["gamma_ini"],
                        resultado["gamma_max"],
                        resultado["SM"],
                        _csv_val(resultado["fo_bp"]),
                        resultado["fo_target"],
                        _csv_val(resultado["gap_bks"]),
                        resultado["n_nos"],
                        resultado["n_cols"],
                        resultado["iteracoes"],
                        _csv_val(resultado["tempo_bp"]),
                        resultado["motivo"],
                        _csv_val(resultado["lb"]),
                        resultado["lb_certificado"],
                    ])
                    f.flush()

                print(
                    f"[CONCLUIDO] {resultado['nome_base']} | gmax={resultado['gamma_max']} | "
                    f"fo_bp={_csv_val(resultado['fo_bp'])} | gap_bks={_csv_val(resultado['gap_bks'])} | "
                    f"tempo={resultado['tempo_bp']:.1f}s | motivo={resultado['motivo']}"
                )
            except Exception as e:
                print(f"[ERRO futuro] {e}")


if __name__ == "__main__":
    freeze_support()
    main()
