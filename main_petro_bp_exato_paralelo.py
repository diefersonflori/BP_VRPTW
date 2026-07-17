import csv
import math
import multiprocessing as mp
import os
import random
import shutil
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


# =============================================================================
# CONFIGURACAO DA RODADA
# =============================================================================
SEED_DEBUG = 123

# Branch-and-Price: o metodo atual tambem possui limite interno de 3600 s.
TIME_LIMIT_BP = 3600
SM_SEM_ESTABILIZACAO = 30
TIPO_PRICING = "PD"
TABU_TENURE = 0
NB_CONSTRUTIVA = 10

# O metodo_exato atual possui model.Params.TimeLimit = 12000 dentro de metodos.py.
TIME_LIMIT_EXATO = 12000
RODAR_EXATO = True

# Maquina com 18 nucleos: configuracao conservadora.
# Tres instancias rodam simultaneamente, com ate quatro threads Gurobi por processo.
MAX_WORKERS = 1
GUROBI_THREADS_POR_PROCESSO = 4

BASE_DIR = Path(__file__).resolve().parent
PASTA_INSTANCIAS = BASE_DIR / "instancias" / "instancias_petro_geradas"
PASTA_RESULTADOS_RAIZ = BASE_DIR / "resultados_petro_bp_exato_paralelo"


CAMPOS_RESUMO = [
    "instancia",
    "regiao",
    "base",
    "pedidos",
    "plataformas",
    "navios",
    "worker_pid",
    "time_limit_bp_s",
    "time_limit_exato_s",
    "sm_sem_estab",
    "custo_construtiva",
    "rotas_artificiais",
    "ub_bp",
    "lb_bp",
    "lb_certificada",
    "gap_bp_percentual",
    "nos_bp",
    "colunas_bp",
    "iteracoes_gc",
    "tempo_bp_s",
    "motivo_parada_bp",
    "sequencias_bp",
    "fo_exato_incumbente",
    "tempo_exato_s",
    "status_exato",
    "sequencias_exato",
    "diferenca_bp_exato",
    "diferenca_bp_exato_percentual",
    "status_geral",
    "erro",
]


def valor_csv(valor, casas=4):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            return ""
        return round(valor, casas)
    return valor


def nome_regiao(nome_base: str) -> str:
    nome = nome_base.lower()
    if "_campos_" in nome:
        return "Campos"
    if "_santos_" in nome:
        return "Santos"
    return ""


def ordem_instancia(caminho: Path):
    nome = caminho.stem.lower()
    tamanho = 10 if "_10ped" in nome else 15 if "_15ped" in nome else 999
    return tamanho, nome


def criar_pastas_rodada():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_rodada = PASTA_RESULTADOS_RAIZ / f"rodada_{timestamp}"

    pastas = {
        "rodada": pasta_rodada,
        "logs": pasta_rodada / "logs",
        "vis": pasta_rodada / "visualizacoes",
        "diag": pasta_rodada / "diagnosticos",
        "conv": pasta_rodada / "convergencia",
        "work": pasta_rodada / "work",
    }

    for chave, pasta in pastas.items():
        if chave != "rodada":
            pasta.mkdir(parents=True, exist_ok=True)

    return pastas


def escrever_cabecalho_resumo(caminho_csv: Path):
    with caminho_csv.open("w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=CAMPOS_RESUMO, delimiter=";")
        writer.writeheader()


def anexar_resumo(caminho_csv: Path, resultado: dict):
    linha = {campo: resultado.get(campo, "") for campo in CAMPOS_RESUMO}
    with caminho_csv.open("a", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=CAMPOS_RESUMO, delimiter=";")
        writer.writerow(linha)
        arquivo.flush()


def exportar_convergencia_csv(sol_pool, caminho: Path):
    linhas = getattr(sol_pool, "log_convergencia", None)
    if not linhas:
        return

    campos = []
    for linha in linhas:
        for chave in linha.keys():
            if chave not in campos:
                campos.append(chave)

    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos, delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)


def extrair_sequencias_bp(inst, sol_pool) -> str:
    partes = []
    for k in sorted(sol_pool.rotas_escolhidas.keys()):
        entrada = sol_pool.rotas_escolhidas[k]
        for seq in entrada.get("sequencias", []):
            clientes = [no for no in seq if 1 <= no <= inst.nbcd]
            partes.append(f"V{k}:{clientes}")
    return " | ".join(partes) if partes else "sem_solucao_inteira"


def extrair_sequencias_exato(inst, sol_exato) -> str:
    partes = []
    for k in sorted(sol_exato.rotas.keys()):
        for seq in sol_exato.rotas[k].get("sequencia_rota", []):
            clientes = [no for no in seq if 1 <= no <= inst.nbcd]
            partes.append(f"V{k}:{clientes}")
    return " | ".join(partes) if partes else "sem_solucao_inteira"


def obter_lb(sol_pool, ub: float):
    lb_certificada = getattr(sol_pool, "lb_global_confiavel", None)
    if lb_certificada is not None:
        return float(lb_certificada), True

    lb_heuristica = getattr(sol_pool, "melhor_lp_valido", float("inf"))
    if lb_heuristica not in (None, float("inf")) and float(lb_heuristica) > 0:
        return float(lb_heuristica), False

    return ub, False


def custo_total_exato(sol_exato) -> float:
    if getattr(sol_exato, "custo", -1) not in (None, -1):
        try:
            valor = float(sol_exato.custo)
            if math.isfinite(valor) and valor >= 0:
                return valor
        except (TypeError, ValueError):
            pass

    if not getattr(sol_exato, "rotas", None):
        return float("inf")

    return sum(
        float(custo)
        for dados in sol_exato.rotas.values()
        for custo in dados.get("custo", [])
    )


def preparar_rotas_exato(sol_exato):
    rotas = {}
    for k, dados in sol_exato.rotas.items():
        seqs = [list(seq) for seq in dados.get("sequencia_rota", [])]
        custos = [float(c) for c in dados.get("custo", [])]
        rotas[k] = {
            "sequencias": seqs,
            "custos": custos,
        }
    return rotas


def mover_diagnostico(work_dir: Path, nome_base: str, pasta_diag: Path):
    origem = work_dir / f"diag_{nome_base}.csv"
    if origem.exists():
        destino = pasta_diag / origem.name
        if destino.exists():
            destino.unlink()
        shutil.move(str(origem), str(destino))


def rodar_instancia_worker(
    arquivo_instancia_str: str,
    indice: int,
    total: int,
    pasta_logs_str: str,
    pasta_vis_str: str,
    pasta_diag_str: str,
    pasta_conv_str: str,
    pasta_work_str: str,
):
    """Executa B&P e, em seguida, o modelo exato para uma instancia.

    Cada worker usa um diretorio de trabalho exclusivo. Isso evita colisao em
    arquivos fixos produzidos pelos metodos, como modelo.lp e diag_*.csv.
    """
    arquivo_instancia = Path(arquivo_instancia_str).resolve()
    pasta_logs = Path(pasta_logs_str).resolve()
    pasta_vis = Path(pasta_vis_str).resolve()
    pasta_diag = Path(pasta_diag_str).resolve()
    pasta_conv = Path(pasta_conv_str).resolve()
    pasta_work = Path(pasta_work_str).resolve()

    nome_base = arquivo_instancia.stem
    work_dir = pasta_work / nome_base
    work_dir.mkdir(parents=True, exist_ok=True)

    log_path = pasta_logs / f"{nome_base}.txt"
    cwd_original = Path.cwd()

    resultado = {
        "instancia": nome_base,
        "regiao": nome_regiao(nome_base),
        "worker_pid": os.getpid(),
        "time_limit_bp_s": TIME_LIMIT_BP,
        "time_limit_exato_s": TIME_LIMIT_EXATO,
        "sm_sem_estab": SM_SEM_ESTABILIZACAO,
        "status_geral": "ERRO",
        "erro": "",
    }

    inicio_total = time.time()

    # Imports dentro do processo filho: mais seguro com spawn no Windows.
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    import gurobipy as gp
    from instancia import Instancia
    from metodos import Metodos
    from solucao import Solucao

    # Limita a quantidade de threads de cada modelo Gurobi criado neste processo.
    gp.setParam("Threads", GUROBI_THREADS_POR_PROCESSO)

    with log_path.open("w", encoding="utf-8") as log_file:
        stdout_anterior = sys.stdout
        stderr_anterior = sys.stderr
        sys.stdout = log_file
        sys.stderr = log_file

        try:
            os.chdir(work_dir)

            print("=" * 96)
            print(f"INSTANCIA: {nome_base}")
            print(f"ARQUIVO: {arquivo_instancia}")
            print(f"WORKER: {indice}/{total} | PID={os.getpid()}")
            print("MODO: B&P sem estabilizacao + modelo exato")
            print(f"TIME_LIMIT_BP: {TIME_LIMIT_BP} s")
            print(f"TIME_LIMIT_EXATO: {TIME_LIMIT_EXATO} s (definido em metodo_exato)")
            print(f"GUROBI_THREADS: {GUROBI_THREADS_POR_PROCESSO}")
            print(f"SM: {SM_SEM_ESTABILIZACAO}")
            print(f"PRICING: {TIPO_PRICING}")
            print("=" * 96)

            # -----------------------------------------------------------------
            # LEITURA
            # -----------------------------------------------------------------
            inst = Instancia()
            inst.nomeInst = str(arquivo_instancia)
            inst.ninst = indice - 1
            inst.leitura_petro(str(arquivo_instancia))

            # Desliga explicitamente a estabilizacao dual.
            inst.usar_estabilizacao = False
            inst.nbconstrutiva = NB_CONSTRUTIVA
            inst.iteraSemMelhora = SM_SEM_ESTABILIZACAO

            random.seed(SEED_DEBUG)

            plataformas = len(set(inst.dados_petro.get("client_ids", [])[1:]))
            base = inst.dados_petro.get("nomes", [""])[0]
            resultado.update({
                "base": base,
                "pedidos": inst.nbcd,
                "plataformas": plataformas,
                "navios": inst.nbv,
            })

            # -----------------------------------------------------------------
            # BRANCH-AND-PRICE
            # -----------------------------------------------------------------
            print("\n" + "=" * 96)
            print("INICIO DO BRANCH-AND-PRICE SEM ESTABILIZACAO")
            print("=" * 96)

            metod_bp = Metodos(inst)
            metod_bp.TABU_TENURE = TABU_TENURE
            metod_bp._log_file = log_file

            sol_pool = Solucao(inst.nbv, inst.nbcd)
            sol_pool.FO_TARGET = -1
            sol_pool.time_initial = time.time()
            sol_pool.TIME_TARGET = TIME_LIMIT_BP
            sol_pool.TIME_MAX = TIME_LIMIT_BP

            metod_bp.init_pool_vazio(inst, sol_pool)
            metod_bp.gera_solucao_inicial(inst, sol_pool)
            metod_bp.adiciona_colunas_ociosas(inst, sol_pool)

            custo_construtiva = sum(
                float(custo)
                for k in range(inst.nbv)
                for custo in sol_pool.rotas[k].get("custo", [])
            )
            n_artificiais = sum(
                1
                for k in range(inst.nbv)
                for artificial in sol_pool.rotas[k].get("artificial", [])
                if artificial
            )

            rotas_construtiva = {}
            for k in range(inst.nbv):
                seqs = sol_pool.rotas[k].get("sequencia_rota", [])
                custos = sol_pool.rotas[k].get("custo", [])
                artificiais = sol_pool.rotas[k].get("artificial", [])
                if not seqs:
                    continue
                if artificiais and artificiais[0]:
                    continue
                rotas_construtiva[k] = {
                    "sequencias": [list(seqs[0])],
                    "custos": [float(custos[0])],
                }

            if rotas_construtiva:
                sol_pool.registrar_solucao("construtiva", rotas_construtiva)
                sol_pool.exportar_visualizacao(
                    inst,
                    "construtiva",
                    str(pasta_vis / f"{nome_base}_construtiva.js"),
                )

            inicio_bp = time.time()
            metod_bp.branch_and_price_global(inst, sol_pool, tipo_geracao=TIPO_PRICING)
            tempo_bp = time.time() - inicio_bp

            ub_bp = (
                float(metod_bp.best_obj)
                if getattr(metod_bp, "best_obj", -1) > 0
                else float("inf")
            )
            lb_bp, lb_certificada = obter_lb(sol_pool, ub_bp)

            if math.isfinite(ub_bp) and math.isfinite(lb_bp):
                gap_bp = abs(ub_bp - lb_bp) / max(abs(ub_bp), 1e-9) * 100.0
            else:
                gap_bp = float("inf")

            sequencias_bp = extrair_sequencias_bp(inst, sol_pool)

            if sol_pool.rotas_escolhidas:
                metod_bp.relatorio_cronograma_petro(inst, sol_pool.rotas_escolhidas)
                sol_pool.registrar_solucao("bp", sol_pool.rotas_escolhidas)
                sol_pool.exportar_visualizacao(
                    inst,
                    "bp",
                    str(pasta_vis / f"{nome_base}_bp.js"),
                )

            exportar_convergencia_csv(
                sol_pool,
                pasta_conv / f"{nome_base}_convergencia.csv",
            )

            resultado.update({
                "custo_construtiva": valor_csv(custo_construtiva),
                "rotas_artificiais": n_artificiais,
                "ub_bp": valor_csv(ub_bp),
                "lb_bp": valor_csv(lb_bp),
                "lb_certificada": lb_certificada,
                "gap_bp_percentual": valor_csv(gap_bp),
                "nos_bp": getattr(metod_bp, "total_nos", 0),
                "colunas_bp": getattr(metod_bp, "total_colunas", 0),
                "iteracoes_gc": getattr(sol_pool, "nb_iteracoes", ""),
                "tempo_bp_s": valor_csv(tempo_bp),
                "motivo_parada_bp": getattr(sol_pool, "motivoConv", ""),
                "sequencias_bp": sequencias_bp,
            })

            print("\n" + "=" * 96)
            print("FIM DO BRANCH-AND-PRICE")
            print(f"UB B&P: {ub_bp}")
            print(f"LB B&P: {lb_bp} | certificada={lb_certificada}")
            print(f"Gap B&P: {gap_bp}")
            print(f"Tempo B&P: {tempo_bp:.1f} s")
            print("=" * 96)

            # -----------------------------------------------------------------
            # MODELO EXATO
            # -----------------------------------------------------------------
            fo_exato = float("inf")
            tempo_exato = 0.0
            status_exato = "NAO_EXECUTADO"
            sequencias_exato = ""

            if RODAR_EXATO:
                print("\n" + "=" * 96)
                print("INICIO DO MODELO EXATO")
                print("=" * 96)

                metod_exato = Metodos(inst)
                sol_exato = Solucao(inst.nbv, inst.nbn)

                inicio_exato = time.time()
                metod_exato.metodo_exato(inst, sol_exato)
                tempo_exato = time.time() - inicio_exato

                fo_exato = custo_total_exato(sol_exato)
                sequencias_exato = extrair_sequencias_exato(inst, sol_exato)

                if math.isfinite(fo_exato) and sol_exato.rotas:
                    status_exato = "COM_SOLUCAO"
                    rotas_exato = preparar_rotas_exato(sol_exato)
                    metod_exato.relatorio_cronograma_petro(inst, rotas_exato)
                    sol_exato.registrar_solucao("exato", rotas_exato)
                    sol_exato.exportar_visualizacao(
                        inst,
                        "exato",
                        str(pasta_vis / f"{nome_base}_exato.js"),
                    )
                else:
                    status_exato = "SEM_SOLUCAO"

                print("\n" + "=" * 96)
                print("FIM DO MODELO EXATO")
                print(f"FO exato/incumbente: {fo_exato}")
                print(f"Tempo exato: {tempo_exato:.1f} s")
                print(f"Status: {status_exato}")
                print("=" * 96)

            diferenca_abs = ""
            diferenca_pct = ""
            if math.isfinite(ub_bp) and math.isfinite(fo_exato):
                diferenca_abs_val = ub_bp - fo_exato
                diferenca_pct_val = (
                    diferenca_abs_val / max(abs(fo_exato), 1e-9) * 100.0
                )
                diferenca_abs = valor_csv(diferenca_abs_val)
                diferenca_pct = valor_csv(diferenca_pct_val)

            resultado.update({
                "fo_exato_incumbente": valor_csv(fo_exato),
                "tempo_exato_s": valor_csv(tempo_exato),
                "status_exato": status_exato,
                "sequencias_exato": sequencias_exato,
                "diferenca_bp_exato": diferenca_abs,
                "diferenca_bp_exato_percentual": diferenca_pct,
                "status_geral": (
                    "OK"
                    if math.isfinite(ub_bp) and (
                        not RODAR_EXATO or status_exato == "COM_SOLUCAO"
                    )
                    else "PARCIAL"
                ),
                "erro": "",
            })

            print("\n" + "=" * 96)
            print("RESUMO FINAL DA INSTANCIA")
            print(f"UB B&P: {ub_bp}")
            print(f"FO exato/incumbente: {fo_exato}")
            print(f"Diferenca B&P - exato: {diferenca_abs}")
            print(f"Tempo total: {time.time() - inicio_total:.1f} s")
            print("=" * 96)

        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {exc}"
            resultado["status_geral"] = "ERRO"
            print("\n[ERRO NA INSTANCIA]")
            traceback.print_exc(file=log_file)

        finally:
            os.chdir(cwd_original)
            sys.stdout = stdout_anterior
            sys.stderr = stderr_anterior

    mover_diagnostico(work_dir, nome_base, pasta_diag)
    resultado["tempo_total_s"] = valor_csv(time.time() - inicio_total)
    resultado["log_path"] = str(log_path)
    return resultado


def main():
    mp.freeze_support()

    if not PASTA_INSTANCIAS.exists():
        raise FileNotFoundError(
            f"Pasta de instancias nao encontrada: {PASTA_INSTANCIAS}"
        )

    instancias = sorted(PASTA_INSTANCIAS.glob("*.json"), key=ordem_instancia)

    if not instancias:
        raise FileNotFoundError(
            f"Nenhum JSON encontrado em: {PASTA_INSTANCIAS}"
        )

    if len(instancias) != 12:
        print(
            f"[AVISO] Foram encontradas {len(instancias)} instancias, "
            "mas eram esperadas 12. A rodada continuara."
        )

    pastas = criar_pastas_rodada()
    resumo_csv = pastas["rodada"] / "resumo_bp_exato.csv"
    escrever_cabecalho_resumo(resumo_csv)

    print("=" * 96)
    print("BATERIA PETROBRAS - B&P SEM ESTABILIZACAO + MODELO EXATO")
    print(f"Instancias: {len(instancias)}")
    print(f"Pasta de entrada: {PASTA_INSTANCIAS}")
    print(f"Pasta de resultados: {pastas['rodada']}")
    print(f"Processos paralelos: {MAX_WORKERS}")
    print(f"Threads Gurobi por processo: {GUROBI_THREADS_POR_PROCESSO}")
    print(f"Limite B&P: {TIME_LIMIT_BP} s por instancia")
    print(f"Limite exato atual: {TIME_LIMIT_EXATO} s por instancia")
    print(f"SM sem estabilizacao: {SM_SEM_ESTABILIZACAO}")
    print(f"Pricing: {TIPO_PRICING}")
    print("Estabilizacao dual: DESLIGADA")
    print("=" * 96)

    inicio_rodada = time.time()
    total = len(instancias)
    resultados = []

    contexto = mp.get_context("spawn")

    with ProcessPoolExecutor(
        max_workers=MAX_WORKERS,
        mp_context=contexto,
    ) as executor:
        futuros = {}

        for indice, arquivo in enumerate(instancias, start=1):
            print(f"[FILA {indice:02d}/{total:02d}] {arquivo.stem}", flush=True)
            futuro = executor.submit(
                rodar_instancia_worker,
                str(arquivo.resolve()),
                indice,
                total,
                str(pastas["logs"]),
                str(pastas["vis"]),
                str(pastas["diag"]),
                str(pastas["conv"]),
                str(pastas["work"]),
            )
            futuros[futuro] = arquivo

        concluidas = 0
        for futuro in as_completed(futuros):
            arquivo = futuros[futuro]
            concluidas += 1

            try:
                resultado = futuro.result()
            except Exception as exc:
                resultado = {
                    "instancia": arquivo.stem,
                    "regiao": nome_regiao(arquivo.stem),
                    "status_geral": "ERRO_PROCESSO",
                    "erro": f"{type(exc).__name__}: {exc}",
                }

            resultados.append(resultado)
            anexar_resumo(resumo_csv, resultado)

            print(
                f"[CONCLUIDO {concluidas:02d}/{total:02d}] "
                f"{resultado.get('instancia', arquivo.stem)} | "
                f"status={resultado.get('status_geral', '')} | "
                f"BP={resultado.get('ub_bp', '')} | "
                f"EXATO={resultado.get('fo_exato_incumbente', '')} | "
                f"PID={resultado.get('worker_pid', '')}",
                flush=True,
            )

            if resultado.get("erro"):
                print(
                    f"[ERRO] {resultado['instancia']}: {resultado['erro']} | "
                    f"log={resultado.get('log_path', '')}",
                    flush=True,
                )

    # Resumo final ordenado por tamanho e nome.
    resumo_ordenado = pastas["rodada"] / "resumo_bp_exato_ordenado.csv"
    escrever_cabecalho_resumo(resumo_ordenado)
    for resultado in sorted(
        resultados,
        key=lambda r: (
            int(r.get("pedidos", 999) or 999),
            str(r.get("instancia", "")),
        ),
    ):
        anexar_resumo(resumo_ordenado, resultado)

    tempo_rodada = time.time() - inicio_rodada

    print("\n" + "=" * 96)
    print("RODADA CONCLUIDA")
    print(f"Tempo total: {tempo_rodada:.1f} s")
    print(f"Resumo por conclusao: {resumo_csv}")
    print(f"Resumo ordenado: {resumo_ordenado}")
    print(f"Logs: {pastas['logs']}")
    print(f"Visualizacoes: {pastas['vis']}")
    print(f"Diagnosticos: {pastas['diag']}")
    print(f"Convergencia: {pastas['conv']}")
    print(f"Diretorios temporarios: {pastas['work']}")
    print("=" * 96)


if __name__ == "__main__":
    main()
