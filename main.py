import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import csv
import math
import multiprocessing
import random
import re
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path

multiprocessing.set_start_method("spawn", force=True)

# ============================================================
# CONFIGURACAO DA BATERIA PETROBRAS
# ============================================================
MAX_WORKERS = 3
GUROBI_THREADS_POR_PROCESSO = 4
TIME_LIMIT_EXATO = 300
RODAR_BP = True
RODAR_EXATO_PETRO = True
SEED_DEBUG = 123
SM_FIXO = 100
GAMMA_INI = 15
GAMMA_MIN = 10
GAMMA_MAX = 600
TABU = 0
TIME_TARGET = 300
TIME_MAX = 300
USAR_GAMMA_RELATIVO = True
GAMMA_RHO = 0.25
PRICING_EXATO_TIMEOUT_S = 60
PRICING_EXATO_MAX_LABELS = 1_000_000_000

BASE_DIR = Path(__file__).resolve().parent
PASTA_INSTANCIAS = BASE_DIR / "instancias" / "instancias_petro_geradas"
#PASTA_INSTANCIAS_nova_petro = BASE_DIR / "instancias" / "instancias_petro_geradas"/ "instancias_mais_nos"/"instancias_petro_28_30_35"
#PASTA_INSTANCIAS_nova_petro = BASE_DIR / "instancias" / "instancias_petro_geradas"/ "instancias_petro_forca_multiveiculo_10"
PASTA_INSTANCIAS_nova_petro = BASE_DIR / "instancias" / "instancias_petro_geradas"/ "convertidas_victor"
PASTA_RESULTADOS_RAIZ = BASE_DIR / "resultados_petro_bp_exato_paralelo"
PASTA_PLOTJS = BASE_DIR / "PlotJS"


# ============================================================
# FUNCOES AUXILIARES
# ============================================================
def chave_natural(caminho):
    return [int(parte) if parte.isdigit() else parte.lower() for parte in re.split(r"(\d+)", Path(caminho).name)]


def nome_seguro(texto):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_")


def nome_pasta_instancia(arquivo_instancia, inst):
    return f"{nome_seguro(Path(arquivo_instancia).stem)}_{inst.nbcd}nos_{inst.nbv}veiculos"


def validar_estrutura():
    if not PASTA_INSTANCIAS_nova_petro.is_dir():
        raise FileNotFoundError(f"Pasta de instancias nao encontrada: {PASTA_INSTANCIAS_nova_petro}")


def csv_val(valor, casas=4):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, float) and math.isinf(valor):
        return ""
    if isinstance(valor, float):
        return round(valor, casas)
    return valor


def exportar_plotjs_seguro(sol_pool, inst, pasta_plotjs_instancia, tempo_construtiva=None,
                            tempo_bp=None, tempo_exato=None, etapa="", stdout_original=None):
    """Chama sol_pool.exportar_plotjs capturando qualquer excecao APENAS da
    visualizacao -- nunca derruba a otimizacao. Chamada progressivamente (apos
    construtiva/BP/exato), sobrescrevendo o mesmo pacote a cada etapa, para
    garantir que pelo menos as etapas ja concluidas fiquem exportadas mesmo se
    uma etapa posterior falhar."""
    print(f"[PLOTJS] exportando pacote... (apos {etapa})", flush=True)
    if stdout_original is not None:
        print(f"[PLOTJS] exportando pacote... (apos {etapa})", file=stdout_original, flush=True)
    try:
        pasta = sol_pool.exportar_plotjs(
            inst, pasta_plotjs_instancia,
            tempo_construtiva=tempo_construtiva, tempo_bp=tempo_bp, tempo_exato=tempo_exato,
        )
        caminho_abs = str(Path(pasta).resolve())
        print(f"[PLOTJS] pasta: {caminho_abs}", flush=True)
        print("[PLOTJS] OK", flush=True)
        if stdout_original is not None:
            print(f"[PLOTJS] pasta: {caminho_abs}", file=stdout_original, flush=True)
            print("[PLOTJS] OK", file=stdout_original, flush=True)
        return pasta
    except Exception:
        erro_txt = traceback.format_exc()
        print(f"[PLOTJS][ERRO] falha ao exportar PlotJS (apos {etapa}):\n{erro_txt}", flush=True)
        if stdout_original is not None:
            print(f"[PLOTJS][ERRO] falha ao exportar PlotJS (apos {etapa}) -- ver log", file=stdout_original, flush=True)
        return None


ARQUIVOS_PLOTJS_ESPERADOS = [
    "gantt_petro_construtiva.html", "petroConstr.js",
    "gantt_petroBp.html", "petroBP.js",
    "gantt_petro_exato.html", "petroEx.js",
]


def verificar_arquivos_plotjs(pasta_plotjs_instancia, stdout_original=None):
    """Confere (existe/tamanho) os 6 arquivos esperados do pacote PlotJS. Nao trata
    DADOS=null como erro (abordagem sem solucao) -- so confere que o arquivo FISICO
    foi criado."""
    pasta_plotjs_instancia = Path(pasta_plotjs_instancia)
    for nome in ARQUIVOS_PLOTJS_ESPERADOS:
        caminho = pasta_plotjs_instancia / nome
        existe = caminho.is_file()
        tamanho = caminho.stat().st_size if existe else 0
        linha = f"[PLOTJS CHECK] {nome} | existe={existe} | tamanho={tamanho} bytes"
        print(linha, flush=True)
        if stdout_original is not None:
            print(linha, file=stdout_original, flush=True)


def registrar_cronogramas_silva(inst, metod, sol_pool, nome_solucao, rotas_dict):
    """SOMENTE modo silva2024: avalia cada rota de `rotas_dict` (formato canonico
    {k: {"sequencias": [...]}}) com Metodos.avaliar_rota_silva2024 (fonte ja validada
    da fisica silva2024, sem duplicar formula aqui) e registra o resultado via
    sol_pool.registrar_cronograma_plotjs, para o PlotJS desenhar o cronograma correto.
    Rotas ociosas ([0,depf] ou vazias) sao ignoradas (navio fica 'ocioso' no Gantt)."""
    cronogramas = {}
    for k, entrada in rotas_dict.items():
        seqs = entrada.get("sequencias", [])
        seq = list(seqs[0]) if seqs else []
        clientes_seq = [no for no in seq if 1 <= no <= inst.nbcd]
        if not clientes_seq:
            continue
        cronogramas[k] = metod.avaliar_rota_silva2024(inst, k, seq, diagnostico=False)
    sol_pool.registrar_cronograma_plotjs(nome_solucao, cronogramas)


# ============================================================
# EXECUCAO DE UMA INSTANCIA
# ============================================================
def rodar_caso(args):
    from instancia import Instancia
    from metodos import Metodos
    from solucao import Solucao

    arquivo_instancia, ninst, pasta_rodada_str = args
    arquivo_instancia = str(Path(arquivo_instancia).resolve())
    pasta_rodada = Path(pasta_rodada_str)
    nome_arquivo = nome_seguro(Path(arquivo_instancia).stem)
    pasta_logs = pasta_rodada / "logs"
    pasta_work = pasta_rodada / "work" / nome_arquivo
    pasta_logs.mkdir(parents=True, exist_ok=True)
    pasta_work.mkdir(parents=True, exist_ok=True)

    log_path = pasta_logs / f"{nome_arquivo}.txt"
    stdout_original = sys.__stdout__
    stderr_original = sys.__stderr__
    cwd_original = Path.cwd()
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)

    print(f"[INICIO] {nome_arquivo}", file=stdout_original, flush=True)

    resultado = None
    try:
        os.chdir(pasta_work)
        sys.stdout = log_file
        sys.stderr = log_file

        inst = Instancia()
        inst.nbcd = 50
        inst.nbn = 52
        inst.nbv = 0
        inst.ninst = ninst
        inst.nomeInst = arquivo_instancia
        inst.leitura_petro(arquivo_instancia)
        inst.pricing_exato_timeout_s = PRICING_EXATO_TIMEOUT_S
        inst.pricing_exato_max_labels = PRICING_EXATO_MAX_LABELS

        nome_saida = nome_pasta_instancia(arquivo_instancia, inst)
        pasta_plotjs_instancia = PASTA_PLOTJS / nome_saida
        modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"

        metod = Metodos(inst)
        metod.TABU_TENURE = TABU
        metod._log_file = log_file
        inst.usar_estabilizacao = True
        inst.nbconstrutiva = 10
        inst.iteraSemMelhora = SM_FIXO
        random.seed(SEED_DEBUG)

        sol_pool = Solucao(inst.nbv, inst.nbcd)
        sol_pool.FO_TARGET = -1
        sol_pool.time_initial = time.time()
        sol_pool.TIME_TARGET = TIME_TARGET
        sol_pool.TIME_MAX = TIME_MAX
        sol_pool.gamma_pi = GAMMA_INI
        sol_pool.gamma_pi_inicial = GAMMA_INI
        sol_pool.gamma_pi_min = GAMMA_MIN
        sol_pool.gamma_pi_max = GAMMA_MAX
        sol_pool.usar_gamma_relativo = USAR_GAMMA_RELATIVO
        sol_pool.gamma_rho = GAMMA_RHO
        sol_pool.gamma_abs_min = 10.0
        sol_pool.gamma_min_factor = 0.25
        sol_pool.gamma_max_factor = 4.0

        t0_construt = time.time()
        metod.init_pool_vazio(inst, sol_pool)
        metod.gera_solucao_inicial(inst, sol_pool)
        metod.adiciona_colunas_ociosas(inst, sol_pool)

        # Etapa 4 (modo silva2024): re-precifica o pool com o custo Silva
        # (avaliar_rota_silva2024), logo apos as construtivas e antes do
        # primeiro mestre. Nao toca nada quando objective_mode="petrobras".
        if getattr(inst, "objective_mode", "petrobras") == "silva2024":
            metod.preparar_pool_silva2024(inst, sol_pool, diagnostico=True)

        tempo_construtiva = time.time() - t0_construt

        custo_construt = sum(float(custo) for k in range(inst.nbv) for custo in sol_pool.rotas[k].get("custo", []))
        n_art = sum(1 for k in range(inst.nbv) for p in range(len(sol_pool.rotas[k].get("artificial", []))) if sol_pool.rotas[k]["artificial"][p])
        construtiva_valida = n_art == 0

        veiculos_ativos_construtiva = sum(
            1
            for k in range(inst.nbv)
            if sol_pool.rotas[k]["sequencia_rota"]
            and any(
                1 <= cliente <= inst.nbcd
                for cliente in sol_pool.rotas[k]["sequencia_rota"][0]
            )
        )
        seqs_construt = []
        for k in range(inst.nbv):
            seq = sol_pool.rotas[k]["sequencia_rota"][0] if sol_pool.rotas[k]["sequencia_rota"] else []
            art = sol_pool.rotas[k]["artificial"][0] if sol_pool.rotas[k]["artificial"] else False
            clientes = [cliente for cliente in seq if 1 <= cliente <= inst.nbcd]
            seqs_construt.append(f"V{k}{'*' if art else ''}:{clientes}")

        msg_construt = f"[CONSTRUT] {nome_saida} | custo={custo_construt:.1f} | art={n_art} | {' | '.join(seqs_construt)}"
        print(msg_construt, flush=True)
        print(msg_construt, file=stdout_original, flush=True)

        rotas_construt = {k: {"sequencias": [list(sol_pool.rotas[k]["sequencia_rota"][0])], "custos": [float(sol_pool.rotas[k]["custo"][0])]} for k in sol_pool.rotas if sol_pool.rotas[k]["sequencia_rota"] and not sol_pool.rotas[k]["artificial"][0]}
        sol_pool.registrar_solucao("construtiva", rotas_construt)
        if modo_silva:
            registrar_cronogramas_silva(inst, metod, sol_pool, "construtiva", rotas_construt)

        # A) exportacao progressiva apos a construtiva -- garante o pacote PlotJS mesmo
        # se B&P/exato falharem depois (ver pedido: exportacao robusta em 3 momentos).
        exportar_plotjs_seguro(sol_pool, inst, pasta_plotjs_instancia,
                                tempo_construtiva=tempo_construtiva,
                                etapa="construtiva", stdout_original=stdout_original)

        ub = None
        lb = None
        gap = None
        lb_valido = False
        arvore_certificada_completa = False
        otimalidade_certificada = False
        n_nos = 0
        n_cols = 0
        tempo_bp = 0.0
        seq_str_bp = "nao_executado"


        sol_exato = None
        fo_exato = None
        tempo_exato = None
        delta_bp_exato = None
        alpha_exato = None
        eta_exato = None
        consumo_diesel_exato_m3 = None
        emissoes_exato_tco2eq = None
        tempo_total_exato_h = None
        parcela_ambiental_exato = None
        parcela_temporal_exato = None
        f1_exato_silva = None
        f2_exato_silva = None
        parcela_f1_exato_silva = None
        parcela_f2_exato_silva = None

        if RODAR_BP:
            t0_bp = time.time()
            metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")
            tempo_bp = time.time() - t0_bp

            ub = metod.best_obj if metod.best_obj > 0 else None

            # mesma logica de LB/gap/certificacao de teste_petro_a03.py: nunca usar UB
            # como fallback de LB; lb_global_confiavel primeiro, senao lb_raiz_confiavel
            # (valido mas sem certificar otimalidade); otimalidade so certificada quando
            # a arvore necessaria foi concluida (nenhum no interrompido/nao certificado),
            # existe LB global e abs(UB-LB) <= tolerancia.
            lb_global = getattr(sol_pool, "lb_global_confiavel", None)
            lb_raiz = getattr(sol_pool, "lb_raiz_confiavel", None)
            arvore_certificada_completa = bool(getattr(sol_pool, "arvore_certificada_completa", False))

            if lb_global is not None:
                lb = float(lb_global)
                lb_valido = True
            elif lb_raiz is not None:
                lb = float(lb_raiz)
                lb_valido = True
            else:
                lb = None
                lb_valido = False

            tol_gap = 1e-6
            otimalidade_certificada = (
                arvore_certificada_completa
                and lb_global is not None
                and ub is not None
                and abs(float(ub) - float(lb_global)) <= tol_gap
            )

            gap = abs(ub - lb) / max(abs(ub), 1e-9) * 100 if (lb_valido and ub is not None) else None
            n_nos = metod.total_nos
            n_cols = metod.total_colunas

            seqs_bp = []
            if sol_pool.rotas_escolhidas:
                for k in sorted(sol_pool.rotas_escolhidas):
                    for seq in sol_pool.rotas_escolhidas[k]["sequencias"]:
                        clientes = [cliente for cliente in seq if 1 <= cliente <= inst.nbcd]
                        seqs_bp.append(f"V{k}:{clientes}")

            seq_str_bp = " | ".join(seqs_bp) if seqs_bp else "sem_solucao_inteira"
            gap_str = f"{gap:.2f}%" if gap is not None else "NA"
            lb_str = f"{lb:.2f}" if lb_valido else "NA"
            ub_str = f"{ub:.2f}" if ub is not None else "NA"
            msg_bp = (
                f"[BP_FIM] {nome_saida} | LB={lb_str} | UB={ub_str} | gap={gap_str} | "
                f"lb_valido={lb_valido} | arvore_certificada_completa={arvore_certificada_completa} | "
                f"otimalidade_certificada={otimalidade_certificada} | "
                f"nos={n_nos} | cols={n_cols} | t={tempo_bp:.1f}s"
            )
            msg_seq = f"[SEQ_BP] {nome_saida} | {seq_str_bp}"
            print(msg_bp, flush=True)
            print(msg_seq, flush=True)
            print(msg_bp, file=stdout_original, flush=True)
            print(msg_seq, file=stdout_original, flush=True)

            if sol_pool.rotas_escolhidas:
                metod.relatorio_cronograma_petro(inst, sol_pool.rotas_escolhidas)
                sol_pool.registrar_solucao("bp", sol_pool.rotas_escolhidas)
                if modo_silva:
                    registrar_cronogramas_silva(inst, metod, sol_pool, "bp", sol_pool.rotas_escolhidas)

            # B) exportacao progressiva apos o B&P (com ou sem incumbente) -- garante o
            # pacote mesmo se o exato falhar depois.
            exportar_plotjs_seguro(sol_pool, inst, pasta_plotjs_instancia,
                                    tempo_construtiva=tempo_construtiva, tempo_bp=tempo_bp,
                                    etapa="bp", stdout_original=stdout_original)


        if RODAR_EXATO_PETRO:
            print("[EXATO] resolvendo modelo compacto...", flush=True)
            sol_exato = Solucao(inst.nbv, inst.nbn)
            t0_exato = time.time()
            #metod.metodo_exato(inst, sol_exato)

            # SOMENTE modo silva2024: o B&P Silva atual trabalha com rotas separaveis
            # por navio (ainda sem o conflito inter-navio de plataforma). Para comparar
            # o compacto na MESMA condicao, desliga aqui o bloqueio entre navios
            # diferentes na mesma plataforma -- so nesta bateria de comparacao, sem
            # tocar no DEFAULT de metodo_exato_petro nem em Petrobras.
            considerar_conflito_plataforma = False if modo_silva else True
            if modo_silva:
                print(f"[SILVA EXATO] considerar_conflito_plataforma={considerar_conflito_plataforma}", flush=True)

            ok_exato = metod.metodo_exato_petro(
                inst,
                sol_exato,
                time_limit=TIME_LIMIT_EXATO,
                threads=GUROBI_THREADS_POR_PROCESSO,
                salvar_modelo=False,
                diagnostico=False,
                considerar_conflito_plataforma=considerar_conflito_plataforma,
            )

            tempo_exato = time.time() - t0_exato

            if ok_exato:
                rotas_exato = {
                    k: {
                        "sequencias": list(sol_exato.rotas[k]["sequencia_rota"]),
                        "custos": list(sol_exato.rotas[k]["custo"])
                    }
                    for k in sol_exato.rotas
                }

                fo_exato = float(sol_exato.custo)
                status_exato = getattr(sol_exato, "exato_petro_status", "DESCONHECIDO")
                bound_exato = getattr(sol_exato, "exato_petro_bound", None)
                gap_exato = getattr(sol_exato, "exato_petro_gap", None)

                bound_txt = f"{bound_exato:.1f}" if bound_exato is not None and math.isfinite(bound_exato) else "NA"
                gap_txt = f"{100.0 * gap_exato:.2f}%" if gap_exato is not None and math.isfinite(gap_exato) else "NA"

                msg_exato = (
                    f"[EXATO_PETRO] {nome_saida} | status={status_exato} | "
                    f"FO={fo_exato:.1f} | bound={bound_txt} | gap={gap_txt} | "
                    f"t={tempo_exato:.1f}s"
                )

                # Parcelas da FO, reaproveitando exatamente os totais ja calculados/
                # checados dentro de metodo_exato_petro (sol.exato_petro_*) -- NUNCA
                # recalculadas aqui. Nomes gravados em sol.exato_petro_* sao GENERICOS
                # (consumo_total/emissoes_total/etc.) porque a mesma formula de
                # objetivo serve os dois modos, mas o SIGNIFICADO fisico e diferente:
                #   Petrobras: consumo_total=D (m3 diesel), emissoes_total=E (tCO2eq).
                #   Silva (ver metodo_exato_petro, modo_silva): E_k=D_k=f1_k (USD, sem
                #     conversao para CO2 -- "Silva: D_k (=f1_k) ja esta em USD, sem
                #     conversao para CO2, E_k so existe para reaproveitar a mesma
                #     formula de objetivo"), tempo_total=T=f2 (=xi*(F-AT), horas),
                #     componente_ambiental=alpha*f1, componente_temporal=(1-alpha)*eta*f2.
                # O relatorio abaixo e MODE-GATED: Petrobras mantem o texto/campos
                # originais; Silva usa nomes proprios (f1/f2), nunca "diesel"/"CO2".
                consumo_diesel_exato_m3 = getattr(sol_exato, "exato_petro_consumo_total", None)
                emissoes_exato_tco2eq = getattr(sol_exato, "exato_petro_emissoes_total", None)
                tempo_total_exato_h = getattr(sol_exato, "exato_petro_tempo_total", None)
                alpha_exato = getattr(sol_exato, "exato_petro_alpha", None)
                eta_exato = getattr(sol_exato, "exato_petro_eta", None)
                parcela_ambiental_exato = getattr(sol_exato, "exato_petro_componente_ambiental", None)
                parcela_temporal_exato = getattr(sol_exato, "exato_petro_componente_temporal", None)

                fo_check = parcela_ambiental_exato + parcela_temporal_exato
                objval_exato = getattr(sol_exato, "exato_petro_obj", fo_exato)

                if modo_silva:
                    # Silva: consumo_total/emissoes_total (sol.exato_petro_*) SAO f1
                    # (USD) -- nao m3/tCO2eq. Nao gravamos isso nos campos CSV
                    # legados (consumo_diesel_exato_m3/emissoes_exato_tco2eq ficam
                    # None para Silva); usamos campos novos e mode-gated abaixo.
                    consumo_diesel_exato_m3 = None
                    emissoes_exato_tco2eq = None
                    f1_exato_silva = getattr(sol_exato, "exato_petro_consumo_total", None)
                    f2_exato_silva = tempo_total_exato_h
                    parcela_f1_exato_silva = parcela_ambiental_exato
                    parcela_f2_exato_silva = parcela_temporal_exato

                    msg_fo = (
                        f"[FO_SILVA_EXATO] f1_total={f1_exato_silva:.4f} USD | "
                        f"f2_total={f2_exato_silva:.4f} h | alpha={alpha_exato:.2f} | eta={eta_exato:.2f} | "
                        f"alpha_f1={parcela_f1_exato_silva:.4f} | termo_temporal={parcela_f2_exato_silva:.4f} | "
                        f"FO_total={fo_check:.4f}"
                    )
                    if abs(fo_check - objval_exato) > 1e-4:
                        msg_fo += "\n[FO_SILVA_EXATO][ALERTA] componentes da FO nao fecham com ObjVal"
                else:
                    msg_fo = (
                        f"[FO_EXATO] diesel={consumo_diesel_exato_m3:.2f} m3 | "
                        f"E={emissoes_exato_tco2eq:.2f} tCO2eq | T={tempo_total_exato_h:.2f} h | "
                        f"alpha={alpha_exato:.2f} | eta={eta_exato:.2f} | "
                        f"CO2={parcela_ambiental_exato:.2f} | tempo={parcela_temporal_exato:.2f} | "
                        f"soma={fo_check:.4f}"
                    )
                    if abs(fo_check - objval_exato) > 1e-4:
                        msg_fo += "\n[FO_EXATO][ALERTA] componentes da FO nao fecham com ObjVal"

                print(msg_exato, flush=True)
                print(msg_exato, file=stdout_original, flush=True)
                print(msg_fo, flush=True)
                print(msg_fo, file=stdout_original, flush=True)

                metod.relatorio_cronograma_petro(inst, rotas_exato)
                sol_pool.registrar_solucao("exato", rotas_exato)
                if modo_silva:
                    # Fonte: sol.exato_petro_silva_diag[k] -- horarios JA resolvidos pelo
                    # Gurobi. Usa o cronograma resolvido diretamente (em vez de
                    # rechamar avaliar_rota_silva2024) para evitar qualquer duvida em
                    # casos degenerados (alpha_fo=0 ou cost_dynamic==cost_anchored),
                    # onde B/P/R/F podem nao ser unicos entre solucoes de mesma FO --
                    # avaliar_rota_silva2024 ja escolhe B pelo mesmo criterio de FO do
                    # compacto (nao mais B=AT fixo), mas nesses casos degenerados o
                    # Gurobi pode ter escolhido outro B igualmente otimo.
                    cronogramas_exato = getattr(sol_exato, "exato_petro_silva_diag", {})
                    sol_pool.registrar_cronograma_plotjs("exato", cronogramas_exato)

            else:
                fo_exato = None
                delta_bp_exato = None

                status_exato = getattr(sol_exato, "exato_petro_status", "SEM_SOLUCAO")
                msg_exato = f"[EXATO_PETRO] {nome_saida} | status={status_exato} | FO=NA | t={tempo_exato:.1f}s"

                print(msg_exato, flush=True)
                print(msg_exato, file=stdout_original, flush=True)

            # C) exportacao progressiva apos o exato (com ou sem incumbente).
            exportar_plotjs_seguro(sol_pool, inst, pasta_plotjs_instancia,
                                    tempo_construtiva=tempo_construtiva,
                                    tempo_bp=(tempo_bp if RODAR_BP else None), tempo_exato=tempo_exato,
                                    etapa="exato", stdout_original=stdout_original)

        # Chamada final de seguranca (sobrescreve com o estado mais completo
        # disponivel; idempotente, nao duplica logica -- reusa exportar_plotjs_seguro).
        exportar_plotjs_seguro(sol_pool, inst, pasta_plotjs_instancia,
                                tempo_construtiva=tempo_construtiva,
                                tempo_bp=(tempo_bp if RODAR_BP else None), tempo_exato=tempo_exato,
                                etapa="final", stdout_original=stdout_original)
        verificar_arquivos_plotjs(pasta_plotjs_instancia, stdout_original=stdout_original)

        resultado = {
            "ordem": ninst,
            "instancia": Path(arquivo_instancia).name,
            "nome_saida": nome_saida,
            "nbcd": inst.nbcd,
            "nbv": inst.nbv,
            "custo_construt": custo_construt,
            "n_art": n_art,
            "lb": lb,
            "ub": ub,
            "gap": gap,
            "lb_valido": lb_valido,
            "arvore_certificada_completa": arvore_certificada_completa,
            "otimalidade_certificada": otimalidade_certificada,
            "n_nos": n_nos,
            "n_cols": n_cols,
            "tempo_bp": tempo_bp,
            "fo_exato": fo_exato,
            "tempo_exato": tempo_exato,
            "delta_bp_exato": delta_bp_exato,
            "alpha_exato": alpha_exato,
            "eta_exato": eta_exato,
            "consumo_diesel_exato_m3": consumo_diesel_exato_m3,
            "emissoes_exato_tco2eq": emissoes_exato_tco2eq,
            "tempo_total_exato_h": tempo_total_exato_h,
            "parcela_ambiental_exato": parcela_ambiental_exato,
            "parcela_temporal_exato": parcela_temporal_exato,
            "f1_exato_silva": f1_exato_silva,
            "f2_exato_silva": f2_exato_silva,
            "parcela_f1_exato_silva": parcela_f1_exato_silva,
            "parcela_f2_exato_silva": parcela_f2_exato_silva,
            "motivo": getattr(sol_pool, "motivoConv", ""),
            "iteracoes": getattr(sol_pool, "nb_iteracoes", ""),
            "log": str(log_path),
            "plotjs": str(pasta_plotjs_instancia),
        }

    except Exception as erro:
        print(f"[ERRO] {nome_arquivo}: {erro}\n{traceback.format_exc()}", file=log_file, flush=True)
        print(f"[ERRO] {nome_arquivo}: {erro}", file=stdout_original, flush=True)

    finally:
        sys.stdout = stdout_original
        sys.stderr = stderr_original
        os.chdir(cwd_original)
        log_file.flush()
        log_file.close()

    return resultado


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================
def main():
    validar_estrutura()

    #instancias = sorted(PASTA_INSTANCIAS.glob("*.json"), key=chave_natural)
    #instancias = sorted(PASTA_INSTANCIAS_nova_petro.glob("*.json"), key=chave_natural)
    PASTA_INSTANCIAS_nova_petro = BASE_DIR / "instancias" / "instancias_petro_geradas" / "convertidas_victor"
    instancias = [
        #BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json"

        #BASE_DIR / "instancias" / "instancias_petro_geradas"/ "convertidas_victor" / "20n-4k-7c-244r_SSML_silva2024.json"
        #BASE_DIR / "instancias" / "Petro_instancias" / "10n-1k-3c-1r_testeUSP_v33.json"
    ]
    INSTANCIAS_SELECIONADAS = [
        # 10 nós
        "10n-2k-6c-019r_SS_silva2024.json",
        "10n-2k-6c-027r_MM_silva2024.json",
        "10n-2k-6c-095r_LL_silva2024.json",

        # 14 nós
        "14n-3k-7c-030r_SSM_silva2024.json",
        "14n-3k-7c-070r_MML_silva2024.json",
        "14n-4k-6c-025r_SSML_silva2024.json",

        # 20 nós
        "20n-4k-7c-244r_SSML_silva2024.json",
    ]

    instancias = [PASTA_INSTANCIAS_nova_petro / nome for nome in INSTANCIAS_SELECIONADAS]

    #instancias = [
    #    PASTA_INSTANCIAS / "petro_campos_C1_nucleo_atual_10ped.json"
    #]
    if not instancias:
        raise FileNotFoundError(f"Nenhuma instancia JSON encontrada em: {PASTA_INSTANCIAS_nova_petro}")

    id_rodada = datetime.now().strftime("rodada_%Y%m%d_%H%M%S")
    pasta_rodada = PASTA_RESULTADOS_RAIZ / id_rodada
    (pasta_rodada / "logs").mkdir(parents=True, exist_ok=True)
    (pasta_rodada / "work").mkdir(parents=True, exist_ok=True)

    resumo_path = pasta_rodada / "resumo_bp_exato.csv"
    resumo_ordenado_path = pasta_rodada / "resumo_bp_exato_ordenado.csv"
    campos = ["ordem", "instancia", "nome_saida", "nbcd", "nbv", "custo_construt", "n_art", "lb", "ub", "gap", "lb_valido", "arvore_certificada_completa", "otimalidade_certificada", "n_nos", "n_cols", "iteracoes", "tempo_bp", "fo_exato", "tempo_exato", "delta_bp_exato", "alpha_exato", "eta_exato", "consumo_diesel_exato_m3", "emissoes_exato_tco2eq", "tempo_total_exato_h", "parcela_ambiental_exato", "parcela_temporal_exato", "f1_exato_silva", "f2_exato_silva", "parcela_f1_exato_silva", "parcela_f2_exato_silva", "motivo", "log", "plotjs"]

    with open(resumo_path, "w", newline="", encoding="utf-8") as arquivo_csv:
        csv.DictWriter(arquivo_csv, fieldnames=campos, delimiter=";").writeheader()

    tarefas = [(str(caminho.resolve()), indice, str(pasta_rodada.resolve())) for indice, caminho in enumerate(instancias)]

    print("=" * 96)
    print("BATERIA PETROBRAS - B&P + MODELO EXATO + PLOTJS POR INSTANCIA")
    print(f"Instancias: {len(instancias)}")
    print(f"Workers paralelos: {MAX_WORKERS}")
    print(f"Pasta de entrada: {PASTA_INSTANCIAS_nova_petro}")
    print(f"Pasta de resultados: {pasta_rodada}")
    print(f"Pasta PlotJS: {PASTA_PLOTJS}")
    print("=" * 96)

    resultados = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(rodar_caso, tarefa): tarefa for tarefa in tarefas}
        for futuro in as_completed(futuros):
            resultado = futuro.result()
            if resultado is None:
                continue

            resultados.append(resultado)
            linha = {campo: csv_val(resultado.get(campo)) for campo in campos}
            with open(resumo_path, "a", newline="", encoding="utf-8") as arquivo_csv:
                escritor = csv.DictWriter(arquivo_csv, fieldnames=campos, delimiter=";")
                escritor.writerow(linha)
                arquivo_csv.flush()

            print(f"[CONCLUIDO] {resultado['nome_saida']} | UB={csv_val(resultado['ub'])} | exato={csv_val(resultado['fo_exato'])} | BP={resultado['tempo_bp']:.1f}s")

    resultados.sort(key=lambda item: item["ordem"])
    with open(resumo_ordenado_path, "w", newline="", encoding="utf-8") as arquivo_csv:
        escritor = csv.DictWriter(arquivo_csv, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        for resultado in resultados:
            escritor.writerow({campo: csv_val(resultado.get(campo)) for campo in campos})

    print("=" * 96)
    print(f"Finalizado: {len(resultados)}/{len(instancias)} instancias")
    print(f"Resumo: {resumo_ordenado_path}")
    print("=" * 96)


if __name__ == "__main__":
    freeze_support()
    main()