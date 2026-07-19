import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import csv
import math
import multiprocessing
import random
import re
import shutil
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
RODAR_EXATO_PETRO = True
SEED_DEBUG = 123
SM_FIXO = 30
GAMMA_INI = 15
GAMMA_MIN = 10
GAMMA_MAX = 600
TABU = 0
TIME_TARGET = 3600
TIME_MAX = 3600

BASE_DIR = Path(__file__).resolve().parent
PASTA_INSTANCIAS = BASE_DIR / "instancias" / "instancias_petro_geradas"
PASTA_RESULTADOS_RAIZ = BASE_DIR / "resultados_petro_bp_exato_paralelo"
PASTA_PLOTJS = BASE_DIR / "PlotJS"
PASTA_BASE_PADRAO = PASTA_PLOTJS / "basePadrao"

CONFIG_PLOTJS = {
    "construtiva": {"html": "gantt_petro_construtiva.html", "js": "petroConstr.js"},
    "bp": {"html": "gantt_petroBp.html", "js": "petroBP.js"},
    "exato": {"html": "gantt_petro_exato.html", "js": "petroEx.js"},
}


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
    if not PASTA_INSTANCIAS.is_dir():
        raise FileNotFoundError(f"Pasta de instancias nao encontrada: {PASTA_INSTANCIAS}")
    if not PASTA_BASE_PADRAO.is_dir():
        raise FileNotFoundError(f"Pasta PlotJS/basePadrao nao encontrada: {PASTA_BASE_PADRAO}")

    faltantes = []
    for config in CONFIG_PLOTJS.values():
        caminho = PASTA_BASE_PADRAO / config["html"]
        if not caminho.is_file():
            faltantes.append(str(caminho))

    if faltantes:
        raise FileNotFoundError("HTMLs padrao nao encontrados:\n" + "\n".join(f"  - {caminho}" for caminho in faltantes))


def copiar_html_apontando_para_js(html_origem, html_destino, nome_js):
    texto = html_origem.read_text(encoding="utf-8")
    padrao_script = re.compile(r'script\.src\s*=\s*["\'][^"\']+["\']\s*\+\s*Date\.now\(\)\s*;')
    texto, quantidade = padrao_script.subn(f'script.src = "{nome_js}?v=" + Date.now();', texto, count=1)

    if quantidade != 1:
        raise RuntimeError(f"Nao foi encontrada exatamente uma linha script.src dinamica em: {html_origem}")

    nomes_antigos = ["visualizacao_dados.js", "visualizacao_dadosBP.js", "visualizacao_dados_construtiva.js", "visualizacao_dados_exato.js", "petroConstr.js", "petroBP.js", "PetroBp.js", "petroEx.js"]
    for nome_antigo in nomes_antigos:
        texto = texto.replace(nome_antigo, nome_js)

    html_destino.write_text(texto, encoding="utf-8")


def preparar_pacote_plotjs(arquivo_instancia, inst):
    pasta_saida = PASTA_PLOTJS / nome_pasta_instancia(arquivo_instancia, inst)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    for config in CONFIG_PLOTJS.values():
        html_origem = PASTA_BASE_PADRAO / config["html"]
        html_destino = pasta_saida / config["html"]
        js_destino = pasta_saida / config["js"]
        copiar_html_apontando_para_js(html_origem, html_destino, config["js"])
        js_destino.write_text("window.DADOS = null;\n", encoding="utf-8")

    return pasta_saida


def exportar_plotjs(solucao, inst, pasta_plotjs_instancia, tipo):
    config = CONFIG_PLOTJS[tipo]
    caminho_js = pasta_plotjs_instancia / config["js"]
    solucao.exportar_visualizacao(inst, tipo, str(caminho_js))

    if not caminho_js.is_file():
        raise RuntimeError(f"O JS de {tipo} nao foi criado: {caminho_js}")

    return pasta_plotjs_instancia / config["html"], caminho_js


def csv_val(valor, casas=4):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, float) and math.isinf(valor):
        return ""
    if isinstance(valor, float):
        return round(valor, casas)
    return valor


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

        nome_saida = nome_pasta_instancia(arquivo_instancia, inst)
        pasta_plotjs_instancia = preparar_pacote_plotjs(arquivo_instancia, inst)
        print(f"[PLOTJS] pasta da instancia: {pasta_plotjs_instancia}", flush=True)

        metod = Metodos(inst)
        metod.TABU_TENURE = TABU
        metod._log_file = log_file
        inst.usar_estabilizacao = False
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

        metod.init_pool_vazio(inst, sol_pool)
        metod.gera_solucao_inicial(inst, sol_pool)
        metod.adiciona_colunas_ociosas(inst, sol_pool)

        custo_construt = sum(float(custo) for k in range(inst.nbv) for custo in sol_pool.rotas[k].get("custo", []))
        n_art = sum(1 for k in range(inst.nbv) for p in range(len(sol_pool.rotas[k].get("artificial", []))) if sol_pool.rotas[k]["artificial"][p])
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
        exportar_plotjs(sol_pool, inst, pasta_plotjs_instancia, "construtiva")

        t0_bp = time.time()
        metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")
        tempo_bp = time.time() - t0_bp

        ub = metod.best_obj if metod.best_obj > 0 else float("inf")
        lb_confiavel_val = getattr(sol_pool, "lb_global_confiavel", None)
        lb_heuristica = getattr(sol_pool, "melhor_lp_valido", float("inf"))

        if lb_confiavel_val is not None:
            lb = lb_confiavel_val
            lb_certificado = True
        else:
            lb = lb_heuristica if lb_heuristica != float("inf") and lb_heuristica > 0 else ub
            lb_certificado = False

        gap = abs(ub - lb) / max(abs(ub), 1e-9) * 100 if not math.isinf(ub) else float("inf")
        n_nos = metod.total_nos
        n_cols = metod.total_colunas

        seqs_bp = []
        if sol_pool.rotas_escolhidas:
            for k in sorted(sol_pool.rotas_escolhidas):
                for seq in sol_pool.rotas_escolhidas[k]["sequencias"]:
                    clientes = [cliente for cliente in seq if 1 <= cliente <= inst.nbcd]
                    seqs_bp.append(f"V{k}:{clientes}")

        seq_str_bp = " | ".join(seqs_bp) if seqs_bp else "sem_solucao_inteira"
        gap_str = f"{gap:.2f}%" if not math.isinf(gap) else "inf"
        tag_cert = "" if lb_certificado else " [LB NAO CERTIFICADA]"
        msg_bp = f"[BP_FIM] {nome_saida} | LB={lb:.2f} | UB={ub:.2f} | gap={gap_str} | nos={n_nos} | cols={n_cols} | t={tempo_bp:.1f}s{tag_cert}"
        msg_seq = f"[SEQ_BP] {nome_saida} | {seq_str_bp}"
        print(msg_bp, flush=True)
        print(msg_seq, flush=True)
        print(msg_bp, file=stdout_original, flush=True)
        print(msg_seq, file=stdout_original, flush=True)

        if sol_pool.rotas_escolhidas:
            metod.relatorio_cronograma_petro(inst, sol_pool.rotas_escolhidas)
            sol_pool.registrar_solucao("bp", sol_pool.rotas_escolhidas)
            exportar_plotjs(sol_pool, inst, pasta_plotjs_instancia, "bp")

        fo_exato = None
        tempo_exato = None
        delta_bp_exato = None

        if RODAR_EXATO_PETRO:
            print("[EXATO] resolvendo modelo compacto...", flush=True)
            sol_exato = Solucao(inst.nbv, inst.nbn)
            t0_exato = time.time()
            metod.metodo_exato(inst, sol_exato)
            tempo_exato = time.time() - t0_exato
            rotas_exato = {k: {"sequencias": list(sol_exato.rotas[k]["sequencia_rota"])} for k in sol_exato.rotas}
            fo_exato = sum(float(custo) for k in sol_exato.rotas for custo in sol_exato.rotas[k]["custo"])
            delta_bp_exato = None if math.isinf(ub) else ub - fo_exato
            msg_exato = f"[EXATO] {nome_saida} | FO={fo_exato:.1f} | t={tempo_exato:.1f}s | B&P={ub}"
            print(msg_exato, flush=True)
            print(msg_exato, file=stdout_original, flush=True)
            metod.relatorio_cronograma_petro(inst, rotas_exato)
            sol_pool.registrar_solucao("exato", rotas_exato)
            exportar_plotjs(sol_pool, inst, pasta_plotjs_instancia, "exato")

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
            "lb_certificado": lb_certificado,
            "n_nos": n_nos,
            "n_cols": n_cols,
            "tempo_bp": tempo_bp,
            "fo_exato": fo_exato,
            "tempo_exato": tempo_exato,
            "delta_bp_exato": delta_bp_exato,
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

    instancias = sorted(PASTA_INSTANCIAS.glob("*.json"), key=chave_natural)
    if not instancias:
        raise FileNotFoundError(f"Nenhuma instancia JSON encontrada em: {PASTA_INSTANCIAS}")

    id_rodada = datetime.now().strftime("rodada_%Y%m%d_%H%M%S")
    pasta_rodada = PASTA_RESULTADOS_RAIZ / id_rodada
    (pasta_rodada / "logs").mkdir(parents=True, exist_ok=True)
    (pasta_rodada / "work").mkdir(parents=True, exist_ok=True)

    resumo_path = pasta_rodada / "resumo_bp_exato.csv"
    resumo_ordenado_path = pasta_rodada / "resumo_bp_exato_ordenado.csv"
    campos = ["ordem", "instancia", "nome_saida", "nbcd", "nbv", "custo_construt", "n_art", "lb", "ub", "gap", "lb_certificado", "n_nos", "n_cols", "iteracoes", "tempo_bp", "fo_exato", "tempo_exato", "delta_bp_exato", "motivo", "log", "plotjs"]

    with open(resumo_path, "w", newline="", encoding="utf-8") as arquivo_csv:
        csv.DictWriter(arquivo_csv, fieldnames=campos, delimiter=";").writeheader()

    tarefas = [(str(caminho.resolve()), indice, str(pasta_rodada.resolve())) for indice, caminho in enumerate(instancias)]

    print("=" * 96)
    print("BATERIA PETROBRAS - B&P + MODELO EXATO + PLOTJS POR INSTANCIA")
    print(f"Instancias: {len(instancias)}")
    print(f"Workers paralelos: {MAX_WORKERS}")
    print(f"Pasta de entrada: {PASTA_INSTANCIAS}")
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