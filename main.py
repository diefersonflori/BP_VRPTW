import sys
import time
import csv
import random
import os
import math
from datetime import datetime

from instancia import Instancia
from solucao import Solucao
from metodos import Metodos, NoBP
from multiprocessing import freeze_support


def main():
    SEED_DEBUG = 123

    ARQ_CSV_FINAL = "resultados_finais.csv"
    ARQ_TXT_FINAL = "resultados_finais_legivel.txt"
    ARQ_CALIB_GAMMA = "calibracao_gamma.csv"


    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, (int, float)) and math.isinf(v):
            return ""
        return v


    def round_safe(v, ndigits=4):
        if v is None:
            return ""
        if isinstance(v, (int, float)) and math.isinf(v):
            return ""
        if v == "":
            return ""
        return round(v, ndigits)


    # ============================================================
    # CONFIGURAÇÃO FLEXÍVEL
    # ============================================================
    # Escolha aqui o que quer rodar:
    #   [25]     -> só 25 clientes
    #   [50]     -> só 50 clientes
    #   [25, 50] -> roda os dois
    tamanhos = [25]

    # Capacidade por tamanho
    capacidade_por_tamanho = {
        25: 200,
        50: 200,
    }

    semMelhora_por_tamanho = {
        25: [10, 20, 50, 100, 300],
        50: [300, 10, 15, 20, 25],
    }

    gamma_ini_por_tamanho = {
        25: 40,
        50: 40,
    }

    gamma_pi_min_por_tamanho = {
        25: 10,
        50: 10,
    }

    gamma_pi_max_por_tamanho = {
        25: [100, 200, 300, 500],
        50: [500, 1000, 2000],
    }

    # Gamma inicial da caixa. Pode separar por família.
    gamma_inicial_caixa = {
        25: {
            "c": 40,
            "r": 80,
            "rc": 80,
        },
        50: {
            "c": 40,
            "r": 80,
            "rc": 80,
        },
    }

    tabu = 0

    todas_instancias = [
        "instancias/c101N.txt", "instancias/c102.txt", "instancias/c103.txt", "instancias/c104.txt",
        "instancias/c105.txt", "instancias/c106.txt", "instancias/c107.txt", "instancias/c108.txt",
        "instancias/c109.txt",
        "instancias/r101.txt", "instancias/r102.txt", "instancias/r103.txt", "instancias/r104.txt",
        "instancias/r105.txt", "instancias/r106.txt", "instancias/r107.txt", "instancias/r108.txt",
        "instancias/r109.txt", "instancias/r110.txt", "instancias/r111.txt", "instancias/r112.txt",
        "instancias/rc101.txt", "instancias/rc102.txt", "instancias/rc103.txt", "instancias/rc104.txt",
        "instancias/rc105.txt", "instancias/rc106.txt", "instancias/rc107.txt", "instancias/rc108.txt",
        "instancias/c201.txt", "instancias/c202.txt", "instancias/c203.txt", "instancias/c204.txt",
        "instancias/c205.txt", "instancias/c206.txt", "instancias/c207.txt", "instancias/c208.txt",
        "instancias/c209.txt",
        "instancias/r201.txt", "instancias/r202.txt", "instancias/r203.txt", "instancias/r204.txt",
        "instancias/r205.txt", "instancias/r206.txt", "instancias/r207.txt", "instancias/r208.txt",
        "instancias/r209.txt", "instancias/r120.txt", "instancias/r211.txt", "instancias/r212.txt",
        "instancias/rc201.txt", "instancias/rc202.txt", "instancias/rc203.txt", "instancias/rc204.txt",
        "instancias/rc205.txt", "instancias/rc206.txt", "instancias/rc207.txt"
    ]

    # Veículos por tamanho e por instância.
    # Para 25 usei os valores da tabela que você mandou.
    # Para 50 mantive os valores que já estavam no seu código.
    NBV_POR_TAM = {
        25: {
            "c101n": 1, "c102": 1, "c103": 1, "c104": 1, "c105": 1,
            "c106": 1, "c107": 1, "c108": 1, "c109": 1,
            "r101": 1, "r102": 3, "r103": 1, "r104": 1, "r105": 1,
            "r106": 7, "r107": 1, "r108": 5, "r109": 1, "r110": 25,
            "r111": 5, "r112": 15,
            "rc101": 321, "rc102": 1, "rc103": 1, "rc104": 1, "rc105": 3,
            "rc106": 1, "rc107": 1, "rc108": 1,
        },
        50: {
            "c101n": 5, "c102": 5, "c103": 5, "c104": 5, "c105": 5,
            "c106": 5, "c107": 5, "c108": 5, "c109": 5,
            "r101": 12, "r102": 11, "r103": 9, "r104": 6, "r105": 9,
            "r106": 6, "r107": 7, "r108": 6, "r109": 8, "r110": 7,
            "r111": 7, "r112": 6,
            "rc101": 8, "rc102": 7, "rc103": 6, "rc104": 5,
        },
    }

    FO_TARGET = {
        25: {
            "c101n": 191.3, "c102": 190.3, "c103": 190.3, "c104": 186.9,
            "c105": 191.3, "c106": 191.3, "c107": 191.3, "c108": 191.3,
            "c109": 191.3,
            "r101": 617.1, "r102": 546.3, "r103": 454.6, "r104": 416.9,
            "r105": 530.5, "r106": 457.3, "r107": 424.3, "r108": 396.8,
            "r109": 441.3, "r110": 438.3, "r111": 427.2, "r112": 387.1,
            "rc101": 406.6, "rc102": 351.8, "rc103": 332.8, "rc104": 306.6,
            "rc105": 410.95, "rc106": 345.5, "rc107": 298.3, "rc108": 294.5,
        },
        50: {
            "c101n": 362.4, "c102": 362.4, "c103": 362.4, "c104": 362.4,
            "c105": 362.4, "c106": 1043.3, "c107": 909.0, "c108": 769.2,
            "c109": 619.1,
            "r101": 892.1, "r102": 791.3, "r103": 707.2, "r104": 594.7,
            "r105": 775.3, "r106": 695.1, "r107": 696.3, "r108": 614.8,
            "r109": 850.0, "r110": 721.8, "r111": 645.2, "r112": 545.8,
            "rc101": 761.5, "rc102": 664.4, "rc103": 603.5, "rc104": 541.1,
        },
    }

    def normaliza_nome_instancia(arquivo):
        nome = os.path.basename(arquivo).lower().replace(".txt", "")
        return nome

    def familia_instancia(nome_base):
        if nome_base.startswith("rc"):
            return "rc"
        if nome_base.startswith("r"):
            return "r"
        return "c"

    def obter_nbv(tam, nome_base):
        return NBV_POR_TAM.get(tam, {}).get(nome_base, None)

    def obter_fo_target(tam, nome_base):
        return FO_TARGET.get(tam, {}).get(nome_base, -1)

    def obter_gamma_inicial(tam, nome_base):
        fam = familia_instancia(nome_base)
        return gamma_inicial_caixa.get(tam, {}).get(fam, gamma_ini_por_tamanho[tam])

    def instancias_do_tamanho(tam):
        # Para 25, roda C/R/RC 100 até RC108.
        # Para 50, roda apenas instâncias com FO e veículos cadastrados.
        nomes_validos = set(FO_TARGET.get(tam, {}).keys())
        return [arq for arq in todas_instancias if normaliza_nome_instancia(arq) in nomes_validos]

    for tam in tamanhos:
        cap = capacidade_por_tamanho[tam]
        semMelhora = semMelhora_por_tamanho[tam]
        gamma_ini = gamma_ini_por_tamanho[tam]
        gamma_pi_min = gamma_pi_min_por_tamanho[tam]
        gamma_pi_max = gamma_pi_max_por_tamanho[tam]

        lista_instancias = instancias_do_tamanho(tam)

        for ninst, arquivo_instancia in enumerate(lista_instancias):

            nome_inst = os.path.basename(arquivo_instancia).lower()
            nome_base = normaliza_nome_instancia(arquivo_instancia)
            fo_target_inst = obter_fo_target(tam, nome_base)
            nbv_inst = obter_nbv(tam, nome_base)

            if nbv_inst is None:
                print(f"Pulando {arquivo_instancia}: nbv não cadastrado para tam={tam}")
                continue

            for gamma_PMAX in gamma_pi_max:

                print("\n############################################")
                print(f"TESTANDO GAMMA = {gamma_PMAX}")
                print("############################################")

                FOTAarg = fo_target_inst
                TIMETarg = 5000

                print("\n==============================")
                print(
                    f"NOVA - tam={tam} cap={cap} VEIC={nbv_inst} "
                    f"gamma={gamma_PMAX} ninst={ninst} INSTANCIA={arquivo_instancia}"
                )
                print("==============================")

                tem_janelas = 0

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

                solex = Solucao(inst.nbv, inst.nbn)
                solc = Solucao(inst.nbv, inst.nbcd)

                tiex = time.time()
                # metod.metodo_exato(inst, solex)
                tfex = time.time()

                tempo_exato = tfex - tiex
                fo_exato = solex.custo
                seq_exato = solex.sequencias_exato_para_texto()

                print("tempo total exato:", tempo_exato)

                tipo_geracao = "PD"

                for SM in semMelhora:

                    inst.nbconstrutiva = 10
                    inst.iteraSemMelhora = SM
                    random.seed(SEED_DEBUG)

                    print("\n--------------------------------------------------")
                    print(f"Heurística retirada = {inst.nbconstrutiva}")
                    print("--------------------------------------------------")

                    sol_pool = Solucao(inst.nbv, inst.nbcd)

                    sol_pool.FO_TARGET = FOTAarg
                    sol_pool.time_initial = time.time()
                    sol_pool.TIME_TARGET = TIMETarg

                    gamma_ini_inst = obter_gamma_inicial(tam, nome_base)
                    sol_pool.gamma_pi = gamma_ini_inst
                    sol_pool.gamma_pi_inicial = gamma_ini_inst
                    sol_pool.gamma_pi_min = gamma_pi_min
                    sol_pool.gamma_pi_max = gamma_PMAX

                    metod.init_pool_vazio(inst, sol_pool)
                    metod.gera_rotas_iniciaisUNICA(inst, sol_pool)
                    metod.gera_rotas_iniciais_inteligente_inteira(inst, sol_pool)

                    for k in range(inst.nbv):
                        print("veic", k, "rotas iniciais =", len(sol_pool.rotas[k]["sequencia_rota"]))

                    t1 = time.time()
                    inst.temmip = False

                    metod.branch_and_price_global(inst, sol_pool, tipo_geracao=tipo_geracao)

                    melhor_lp_com_slack = sol_pool.melhor_lp_com_slack
                    melhor_lp_com_slack_iter = sol_pool.iter_melhor_lp_com_slack
                    no_melhor_lp_com_slack = sol_pool.no_melhor_lp_com_slack

                    melhor_lp_valido = sol_pool.melhor_lp_valido
                    melhor_lp_valido_iter = sol_pool.iter_melhor_lp_valido
                    no_melhor_lp_valido = sol_pool.no_melhor_lp_valido

                    melhor_int = sol_pool.melhor_inteiro
                    melhor_int_iter = sol_pool.iter_melhor_inteiro
                    no_melhor_inteiro = sol_pool.no_melhor_inteiro

                    achou_lp_target = sol_pool.achou_lp_target
                    achou_int_target = sol_pool.achou_int_target

                    iter_lp_target = sol_pool.iter_lp_target
                    iter_int_target = sol_pool.iter_int_target

                    tempo_lp_target = sol_pool.tempo_lp_target
                    tempo_int_target = sol_pool.tempo_int_target

                    no_lp_target = sol_pool.no_lp_target
                    no_int_target = sol_pool.no_int_target

                    print(f"FO_TARGET = {sol_pool.FO_TARGET}")

                    print(
                        f"Melhor LP com slack = {fmt(melhor_lp_com_slack)} "
                        f"| iter = {melhor_lp_com_slack_iter} "
                        f"| no = {no_melhor_lp_com_slack}"
                    )

                    print(
                        f"Melhor LP válido = {fmt(melhor_lp_valido)} "
                        f"| iter = {melhor_lp_valido_iter} "
                        f"| no = {no_melhor_lp_valido}"
                    )

                    print(
                        f"Melhor inteiro = {fmt(melhor_int)} "
                        f"| iter = {melhor_int_iter} "
                        f"| no = {no_melhor_inteiro}"
                    )

                    print(
                        f"Achou LP target = {achou_lp_target} "
                        f"| iter = {iter_lp_target} "
                        f"| tempo = {tempo_lp_target} "
                        f"| no = {no_lp_target}"
                    )

                    print(
                        f"Achou INT target = {achou_int_target} "
                        f"| iter = {iter_int_target} "
                        f"| tempo = {tempo_int_target} "
                        f"| no = {no_int_target}"
                    )

                    try:
                        nome_excel = f"convergencia_BP_{nome_inst.replace('.txt', '')}_g{gamma_PMAX}.xlsx"
                        sol_pool.exportar_convergencia_excel(inst, nome_excel)
                    except Exception as e:
                        print(f"Erro ao exportar Excel de convergência: {e}")

                    tempo_bp = time.time() - t1

                    print(f"Tempo total BP: {tempo_bp:.4f}")

                    fo_bp = metod.best_obj
                    seq_bp = sol_pool.sequencias_bp_para_texto()
                    nos_bp = metod.total_nos
                    colunas_bp = metod.total_colunas

                    run_id = (
                        f"{nome_inst.replace('.txt', '')}_"
                        f"tam{tam}_"
                        f"gini{gamma_ini_inst}_"
                        f"gmax{gamma_PMAX}_"
                        f"SM{inst.iteraSemMelhora}"
                    )

                    gap = ""
                    if fo_exato not in (None, 0, -1) and fo_bp not in (None, -1):
                        gap = ((fo_bp - fo_exato) / fo_exato) * 100.0

                    igual_exato = ""
                    if fo_exato not in (None, -1) and fo_bp not in (None, -1):
                        igual_exato = 1 if abs(fo_bp - fo_exato) <= 1e-6 else 0

                    if not seq_bp:
                        seq_bp = "SEM_SOLUCAO_BP"

                    with open(ARQ_TXT_FINAL, "a", encoding="utf-8") as f:
                        f.write("=" * 120 + "\n")
                        f.write(f"RUN_ID: {run_id}\n")
                        f.write(f"Instância: {arquivo_instancia}\n")
                        f.write(
                            f"Clientes={inst.nbcd} | Nós_rede={inst.nbn} | Veículos={inst.nbv} | "
                            f"Capacidade={cap} | Tabu={tabu} | Heurística_retirada={inst.nbconstrutiva}\n"
                        )
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
                        f.write(f"SEM MELHORA = {getattr(inst, 'iteraSemMelhora', '')}\n")
                        f.write(f"SCORE DAS CONSTRUTIVAS BP = {getattr(sol_pool, 'construtivas', '')}\n")
                        f.write(f"SEQ_EXATO: {seq_exato}\n")
                        f.write(f"SEQ_BP: {seq_bp}\n\n")
                        f.write(f"GAMMA PI: {gamma_ini_inst}\n")
                        f.write(f"GAMMA MIN: {gamma_pi_min}\n")
                        f.write(f"GAMMA MAX: {gamma_PMAX}\n")
                        f.write(f"MOTIVO: {getattr(sol_pool, 'motivoConv', '')}\n")
                        f.write(f"ITERAC: {getattr(sol_pool, 'nb_iteracoes', '')}\n\n")
                        f.write(f"ITER SEM MELHORA: {inst.iteraSemMelhora}\n\n")

                        f.write(f"FO_TARGET = {sol_pool.FO_TARGET}\n")
                        f.write(
                            f"Melhor LP com slack = {fmt(melhor_lp_com_slack)} "
                            f"| iter = {melhor_lp_com_slack_iter} "
                            f"| no = {no_melhor_lp_com_slack}\n"
                        )
                        f.write(
                            f"Melhor LP válido = {fmt(melhor_lp_valido)} "
                            f"| iter = {melhor_lp_valido_iter} "
                            f"| no = {no_melhor_lp_valido}\n"
                        )
                        f.write(
                            f"Melhor inteiro = {fmt(melhor_int)} "
                            f"| iter = {melhor_int_iter} "
                            f"| no = {no_melhor_inteiro}\n"
                        )
                        f.write(
                            f"Achou LP target = {achou_lp_target} "
                            f"| iter = {iter_lp_target} "
                            f"| tempo = {tempo_lp_target} "
                            f"| no = {no_lp_target}\n"
                        )
                        f.write(
                            f"Achou INT target = {achou_int_target} "
                            f"| iter = {iter_int_target} "
                            f"| tempo = {tempo_int_target} "
                            f"| no = {no_int_target}\n"
                        )

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

                            sol_pool.FO_TARGET,
                            round_safe(fo_exato),
                            round_safe(fo_bp),

                            round_safe(melhor_lp_com_slack),
                            melhor_lp_com_slack_iter,
                            no_melhor_lp_com_slack,

                            round_safe(melhor_lp_valido),
                            melhor_lp_valido_iter,
                            no_melhor_lp_valido,

                            round_safe(melhor_int),
                            melhor_int_iter,
                            no_melhor_inteiro,

                            achou_lp_target,
                            iter_lp_target,
                            round_safe(tempo_lp_target),
                            no_lp_target,

                            achou_int_target,
                            iter_int_target,
                            round_safe(tempo_int_target),
                            no_int_target,

                            round_safe(gap),
                            igual_exato,

                            nos_bp,
                            colunas_bp,

                            inst.temmip,
                            getattr(inst, "iteraSemMelhora", ""),

                            gamma_ini_inst,
                            gamma_pi_min,
                            gamma_PMAX,

                            getattr(sol_pool, "motivoConv", ""),
                            getattr(sol_pool, "nb_iteracoes", ""),

                            seq_exato,
                            seq_bp,

                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])

                    existe_calib = os.path.exists(ARQ_CALIB_GAMMA)

                    with open(ARQ_CALIB_GAMMA, "a", newline="", encoding="utf-8") as f:
                        w = csv.writer(f, delimiter=";")

                        if not existe_calib:
                            w.writerow([
                                "run_id",
                                "instancia",
                                "familia",
                                "clientes",
                                "veiculos",
                                "capacidade",
                                "gamma_ini",
                                "gamma_min",
                                "gamma_max",
                                "tempo_bp",
                                "fo_bp",
                                "nos_bp",
                                "colunas_bp",
                                "iteracoes",
                                "motivo",
                                "sem_melhora",
                                "score_construtivas",
                                "timestamp"
                            ])

                        w.writerow([
                            run_id,
                            arquivo_instancia,
                            familia_instancia(nome_base).upper(),
                            inst.nbcd,
                            inst.nbv,
                            cap,
                            gamma_ini_inst,
                            gamma_pi_min,
                            gamma_PMAX,
                            round_safe(tempo_bp),
                            round_safe(fo_bp),
                            nos_bp,
                            colunas_bp,
                            getattr(sol_pool, "nb_iteracoes", ""),
                            getattr(sol_pool, "motivoConv", ""),
                            getattr(inst, "iteraSemMelhora", ""),
                            getattr(sol_pool, "construtivas", ""),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])

                    print("")


    tfseq = time.time()

    try:
        solex.printar_sol_exata(inst)
        solex.registrar_fo_gc(inst, solex.custo)
        solc.exportar_json_gc(inst, "solucao_gcm.json")
        print("\n tempo total exato:", tfex - tiex)
    except NameError:
        pass

if __name__ == "__main__":
    freeze_support()
    main()