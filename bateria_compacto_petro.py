
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURACAO FIXA DA BATERIA
# ============================================================
TIME_LIMIT = 1200
THREADS = 1
TIMEOUT_PROCESSO_MARGEM_S = 180
SEED_GUROBI = 42  # valor atualmente definido dentro de metodo_exato_petro

BASE_DIR = Path(__file__).resolve().parent
PASTA_INSTANCIAS = BASE_DIR / "instancias" / "instancias_petro_geradas" / "instancias_mais_nos"
PASTA_RESULTADOS_RAIZ = BASE_DIR / "resultados_compacto_petro"
PASTA_RESULTADOS_BP = BASE_DIR / "resultados_calibracao_gamma"

INSTANCIAS = {
    "A03": "petro_A03_12ped_5plat_3nav_min2_coleta_pesada.json",
    "B03": "petro_B03_15ped_6plat_3nav_min3_forca3v_janelas.json",
    "C01": "petro_C01_18ped_7plat_3nav_min2_forca2v_balanceada.json",
    "E01": "petro_E01_25ped_10plat_4nav_min3_forca3v_balanceada.json",
}

CAMPOS_CSV = [
    "instancia",
    "arquivo_instancia",
    "status",
    "tem_solucao",
    "otimo",
    "consistente",
    "retorno_metodo",
    "lb",
    "ub",
    "gap_percentual",
    "tempo_solver",
    "tempo_total",
    "time_limit",
    "threads",
    "seed_gurobi",
    "terminou_por_timeout_externo",
    "motivo_final",
    "log",
    "rotas_json",
]

CAMPOS_COMPARACAO = [
    "instancia",
    "bp_configuracao",
    "bp_lb",
    "bp_ub",
    "bp_gap_percentual",
    "bp_tempo",
    "bp_otimo_certificado",
    "compacto_lb",
    "compacto_ub",
    "compacto_gap_percentual",
    "compacto_tempo_solver",
    "compacto_tempo_total",
    "compacto_otimo",
    "compacto_consistente",
    "indicador_preliminar",
]


def numero_finito_ou_none(valor):
    if valor is None or valor == "":
        return None
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(valor) or math.isinf(valor):
        return None
    return valor


def bool_csv(valor):
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {"true", "1", "yes", "sim"}


def csv_val(valor, casas=6):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            return ""
        return round(valor, casas)
    return valor


def resultado_vazio(codigo):
    return {
        "instancia": codigo,
        "arquivo_instancia": INSTANCIAS[codigo],
        "status": "",
        "tem_solucao": False,
        "otimo": False,
        "consistente": False,
        "retorno_metodo": False,
        "lb": None,
        "ub": None,
        "gap_percentual": None,
        "tempo_solver": None,
        "tempo_total": None,
        "time_limit": TIME_LIMIT,
        "threads": THREADS,
        "seed_gurobi": SEED_GUROBI,
        "terminou_por_timeout_externo": False,
        "motivo_final": "",
        "log": "",
        "rotas_json": "",
    }


# ============================================================
# WORKER INTERNO: executa UMA instancia em processo separado.
# O usuario nao precisa chamar este modo diretamente.
# ============================================================
def rodar_worker(instancia_codigo, out_json_path, rotas_json_path):
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    resultado = resultado_vazio(instancia_codigo)
    t0_total = time.time()

    try:
        arquivo_instancia = (PASTA_INSTANCIAS / INSTANCIAS[instancia_codigo]).resolve()
        if not arquivo_instancia.exists():
            raise FileNotFoundError(f"Instancia nao encontrada: {arquivo_instancia}")

        from instancia import Instancia
        from metodos import Metodos
        from solucao import Solucao

        inst = Instancia()
        inst.nbcd = 50
        inst.nbn = 52
        inst.nbv = 0
        inst.ninst = 0
        inst.nomeInst = str(arquivo_instancia)
        inst.leitura_petro(str(arquivo_instancia))

        sol_exato = Solucao(inst.nbv, inst.nbcd)
        metod = Metodos(inst)

        print("=" * 96, flush=True)
        print(f"MODELO COMPACTO PETRO | instancia={instancia_codigo}", flush=True)
        print(f"arquivo={arquivo_instancia}", flush=True)
        print(f"time_limit={TIME_LIMIT}s | threads={THREADS}", flush=True)
        print("=" * 96, flush=True)

        retorno = metod.metodo_exato_petro(
            inst,
            sol_exato,
            time_limit=TIME_LIMIT,
            threads=THREADS,
            salvar_modelo=False,
            diagnostico=True,
        )

        tempo_total = time.time() - t0_total
        status = str(getattr(sol_exato, "exato_petro_status", ""))
        tem_solucao = bool(getattr(sol_exato, "exato_petro_tem_solucao", False))
        otimo = bool(getattr(sol_exato, "exato_petro_otimo", False))
        consistente = bool(getattr(sol_exato, "exato_petro_consistente", False))
        ub = numero_finito_ou_none(getattr(sol_exato, "exato_petro_obj", None))
        lb = numero_finito_ou_none(getattr(sol_exato, "exato_petro_bound", None))
        tempo_solver = numero_finito_ou_none(getattr(sol_exato, "exato_petro_runtime", None))

        gap_modelo = numero_finito_ou_none(getattr(sol_exato, "exato_petro_gap", None))
        if ub is not None and lb is not None:
            gap_percentual = abs(ub - lb) / max(abs(ub), 1e-9) * 100.0
        elif gap_modelo is not None:
            gap_percentual = 100.0 * gap_modelo
        else:
            gap_percentual = None

        rotas = getattr(sol_exato, "exato_petro_rotas_brutas", None)
        if rotas is not None:
            Path(rotas_json_path).parent.mkdir(parents=True, exist_ok=True)
            with open(rotas_json_path, "w", encoding="utf-8") as f:
                json.dump(rotas, f, ensure_ascii=False, indent=2, default=str)
            resultado["rotas_json"] = str(rotas_json_path)

        if not tem_solucao:
            motivo = "SEM_SOLUCAO_INCUMBENTE"
        elif not consistente:
            motivo = "SOLUCAO_REJEITADA_NA_VALIDACAO_OPERACIONAL"
        elif otimo:
            motivo = "OTIMO_CERTIFICADO"
        else:
            motivo = "TIME_LIMIT_OU_PARADA_SEM_OTIMALIDADE"

        resultado.update({
            "status": status,
            "tem_solucao": tem_solucao,
            "otimo": otimo,
            "consistente": consistente,
            "retorno_metodo": bool(retorno),
            "lb": lb,
            "ub": ub,
            "gap_percentual": gap_percentual,
            "tempo_solver": tempo_solver,
            "tempo_total": tempo_total,
            "motivo_final": motivo,
        })

        lb_txt = "NA" if lb is None else f"{lb:.2f}"
        ub_txt = "NA" if ub is None else f"{ub:.2f}"
        gap_txt = "NA" if gap_percentual is None else f"{gap_percentual:.4f}%"
        print(
            f"[COMPACTO_FIM] {instancia_codigo} | status={status} | LB={lb_txt} | UB={ub_txt} | "
            f"gap={gap_txt} | otimo={otimo} | consistente={consistente} | "
            f"tempo_solver={tempo_solver} | tempo_total={tempo_total:.2f}s",
            flush=True,
        )

    except Exception as exc:
        import traceback

        resultado["tempo_total"] = time.time() - t0_total
        resultado["motivo_final"] = f"ERRO: {exc}"
        print(f"[ERRO] {instancia_codigo}: {exc}\n{traceback.format_exc()}", flush=True)

    Path(out_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)


# ============================================================
# PROCESSO PRINCIPAL
# ============================================================
def executar_instancia(instancia_codigo, pasta_rodada):
    pasta_logs = pasta_rodada / "logs"
    pasta_work = pasta_rodada / "work"
    pasta_rotas = pasta_rodada / "rotas"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    pasta_work.mkdir(parents=True, exist_ok=True)
    pasta_rotas.mkdir(parents=True, exist_ok=True)

    log_path = pasta_logs / f"{instancia_codigo}.txt"
    out_json_path = pasta_work / f"{instancia_codigo}.json"
    rotas_json_path = pasta_rotas / f"{instancia_codigo}_rotas.json"

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--instancia-codigo",
        instancia_codigo,
        "--out-json",
        str(out_json_path),
        "--rotas-json",
        str(rotas_json_path),
    ]

    print(f"[INICIO] {instancia_codigo}", flush=True)
    t0 = time.time()
    timeout_externo = TIME_LIMIT + TIMEOUT_PROCESSO_MARGEM_S

    timeout_ocorreu = False
    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                timeout=timeout_externo,
                check=False,
            )
    except subprocess.TimeoutExpired:
        timeout_ocorreu = True
        print(
            f"[TIMEOUT EXTERNO] {instancia_codigo} excedeu {timeout_externo}s e foi encerrada.",
            flush=True,
        )

    tempo_total_pai = time.time() - t0

    if out_json_path.exists():
        with open(out_json_path, "r", encoding="utf-8") as f:
            resultado = json.load(f)
    else:
        resultado = resultado_vazio(instancia_codigo)
        resultado["tempo_total"] = tempo_total_pai
        resultado["motivo_final"] = "TIMEOUT_PROCESSO_EXTERNO" if timeout_ocorreu else "PROCESSO_SEM_JSON"

    resultado["terminou_por_timeout_externo"] = timeout_ocorreu
    resultado["log"] = str(log_path)
    if rotas_json_path.exists():
        resultado["rotas_json"] = str(rotas_json_path)

    print(
        f"[CONCLUIDO] {instancia_codigo} | status={resultado.get('status') or 'NA'} | "
        f"LB={csv_val(resultado.get('lb'))} | UB={csv_val(resultado.get('ub'))} | "
        f"gap={csv_val(resultado.get('gap_percentual'))} | "
        f"t={csv_val(resultado.get('tempo_total'))}s",
        flush=True,
    )
    return resultado


def gravar_resumo(caminho, resultados):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=";")
        escritor.writeheader()
        for resultado in resultados:
            escritor.writerow({campo: csv_val(resultado.get(campo)) for campo in CAMPOS_CSV})


def localizar_resumo_bp():
    if not PASTA_RESULTADOS_BP.exists():
        return None
    candidatos = list(PASTA_RESULTADOS_BP.glob("rodada_*/resumo_calibracao_gamma.csv"))
    if not candidatos:
        return None
    candidatos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidatos[0]


def ler_bp_rho025(caminho_bp):
    linhas = {}
    with open(caminho_bp, "r", newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=";")
        for linha in leitor:
            if linha.get("configuracao") == "rho_025":
                linhas[linha.get("instancia")] = linha
    return linhas


def indicador_preliminar(bp, compacto):
    if bp is None:
        return "SEM_RESULTADO_BP_RHO025"

    bp_otimo = bool_csv(bp.get("otimalidade_certificada"))
    comp_otimo = bool(compacto.get("otimo")) and bool(compacto.get("consistente"))
    bp_gap = numero_finito_ou_none(bp.get("gap_percentual"))
    comp_gap = numero_finito_ou_none(compacto.get("gap_percentual"))
    bp_ub = numero_finito_ou_none(bp.get("ub"))
    comp_ub = numero_finito_ou_none(compacto.get("ub"))

    if bp_otimo and not comp_otimo:
        return "FAVORECE_BP: somente_B&P_certificou_otimo"
    if comp_otimo and not bp_otimo:
        return "FAVORECE_COMPACTO: somente_compacto_certificou_otimo"
    if bp_otimo and comp_otimo:
        bp_t = numero_finito_ou_none(bp.get("tempo_bp"))
        comp_t = numero_finito_ou_none(compacto.get("tempo_solver"))
        if bp_t is not None and comp_t is not None:
            if bp_t < comp_t - 1e-6:
                return "FAVORECE_BP: ambos_otimos_B&P_mais_rapido"
            if comp_t < bp_t - 1e-6:
                return "FAVORECE_COMPACTO: ambos_otimos_compacto_mais_rapido"
        return "EMPATE_TECNICO: ambos_otimos"

    if bp_gap is not None and comp_gap is not None:
        if bp_gap < comp_gap - 1e-6:
            return "FAVORECE_BP: menor_gap"
        if comp_gap < bp_gap - 1e-6:
            return "FAVORECE_COMPACTO: menor_gap"

    if bp_ub is not None and comp_ub is not None:
        if bp_ub < comp_ub - 1e-6:
            return "FAVORECE_BP: menor_UB"
        if comp_ub < bp_ub - 1e-6:
            return "FAVORECE_COMPACTO: menor_UB"

    return "INCONCLUSIVO_OU_EMPATE"


def gerar_comparacao_bp(pasta_rodada, resultados):
    caminho_bp = localizar_resumo_bp()
    if caminho_bp is None:
        print("[COMPARACAO] Nenhum resumo do B&P encontrado; comparacao automatica nao foi gerada.")
        return

    bp_por_instancia = ler_bp_rho025(caminho_bp)
    comparacoes = []

    for comp in resultados:
        codigo = comp["instancia"]
        bp = bp_por_instancia.get(codigo)
        comparacoes.append({
            "instancia": codigo,
            "bp_configuracao": "rho_025" if bp is not None else "",
            "bp_lb": numero_finito_ou_none(bp.get("lb")) if bp else None,
            "bp_ub": numero_finito_ou_none(bp.get("ub")) if bp else None,
            "bp_gap_percentual": numero_finito_ou_none(bp.get("gap_percentual")) if bp else None,
            "bp_tempo": numero_finito_ou_none(bp.get("tempo_bp")) if bp else None,
            "bp_otimo_certificado": bool_csv(bp.get("otimalidade_certificada")) if bp else False,
            "compacto_lb": numero_finito_ou_none(comp.get("lb")),
            "compacto_ub": numero_finito_ou_none(comp.get("ub")),
            "compacto_gap_percentual": numero_finito_ou_none(comp.get("gap_percentual")),
            "compacto_tempo_solver": numero_finito_ou_none(comp.get("tempo_solver")),
            "compacto_tempo_total": numero_finito_ou_none(comp.get("tempo_total")),
            "compacto_otimo": bool(comp.get("otimo")),
            "compacto_consistente": bool(comp.get("consistente")),
            "indicador_preliminar": indicador_preliminar(bp, comp),
        })

    csv_path = pasta_rodada / "comparacao_bp_rho025_vs_compacto.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_COMPARACAO, delimiter=";")
        escritor.writeheader()
        for linha in comparacoes:
            escritor.writerow({campo: csv_val(linha.get(campo)) for campo in CAMPOS_COMPARACAO})

    txt = []
    txt.append("=" * 110)
    txt.append("COMPARACAO PRELIMINAR: B&P rho=0.25 versus MODELO COMPACTO")
    txt.append(f"Resumo B&P utilizado: {caminho_bp}")
    txt.append(f"Limite do compacto: {TIME_LIMIT}s | threads={THREADS}")
    txt.append("ATENCAO: o tempo_bp do B&P nao inclui a construtiva inicial; por isso, a conclusao principal deve priorizar certificacao, gap, UB e LB.")
    txt.append("=" * 110)

    for linha in comparacoes:
        txt.append("")
        txt.append(f"Instancia {linha['instancia']}")
        txt.append(
            f"  B&P rho025: LB={linha['bp_lb']} | UB={linha['bp_ub']} | gap={linha['bp_gap_percentual']}% | "
            f"tempo={linha['bp_tempo']}s | otimo={linha['bp_otimo_certificado']}"
        )
        txt.append(
            f"  Compacto:   LB={linha['compacto_lb']} | UB={linha['compacto_ub']} | gap={linha['compacto_gap_percentual']}% | "
            f"tempo_solver={linha['compacto_tempo_solver']}s | tempo_total={linha['compacto_tempo_total']}s | "
            f"otimo={linha['compacto_otimo']} | consistente={linha['compacto_consistente']}"
        )
        txt.append(f"  Indicador: {linha['indicador_preliminar']}")

    txt_path = pasta_rodada / "comparacao_bp_rho025_vs_compacto.txt"
    txt_path.write_text("\n".join(txt), encoding="utf-8")

    print(f"[COMPARACAO] CSV: {csv_path}")
    print(f"[COMPARACAO] TXT: {txt_path}")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--instancia-codigo", type=str)
    parser.add_argument("--out-json", type=str)
    parser.add_argument("--rotas-json", type=str)
    args, extras = parser.parse_known_args()

    if args.worker:
        rodar_worker(args.instancia_codigo, args.out_json, args.rotas_json)
        return

    if extras:
        raise ValueError(
            "Este script nao exige parametros de entrada. Execute apenas: python bateria_compacto_petro.py"
        )

    id_rodada = datetime.now().strftime("rodada_%Y%m%d_%H%M%S")
    pasta_rodada = PASTA_RESULTADOS_RAIZ / id_rodada
    pasta_rodada.mkdir(parents=True, exist_ok=False)

    print("=" * 96)
    print("BATERIA DO MODELO COMPACTO/EXATO PETROBRAS")
    print(f"Pasta de resultados: {pasta_rodada}")
    print(f"Instancias: {list(INSTANCIAS.keys())}")
    print(f"Time limit por instancia: {TIME_LIMIT}s")
    print(f"Threads por instancia: {THREADS}")
    print(f"Total de execucoes: {len(INSTANCIAS)}")
    print("=" * 96)

    resultados = []
    for codigo in INSTANCIAS:
        resultados.append(executar_instancia(codigo, pasta_rodada))

    resumo_path = pasta_rodada / "resumo_compacto_petro.csv"
    resumo_ordenado_path = pasta_rodada / "resumo_compacto_petro_ordenado.csv"
    gravar_resumo(resumo_path, resultados)
    gravar_resumo(resumo_ordenado_path, sorted(resultados, key=lambda r: r["instancia"]))

    gerar_comparacao_bp(pasta_rodada, resultados)

    n_otimos = sum(1 for r in resultados if bool(r.get("otimo")) and bool(r.get("consistente")))
    n_com_solucao = sum(1 for r in resultados if bool(r.get("tem_solucao")))

    print("\n" + "=" * 96)
    print("BATERIA FINALIZADA")
    print(f"Instancias com incumbente: {n_com_solucao}/{len(resultados)}")
    print(f"Otimos certificados e consistentes: {n_otimos}/{len(resultados)}")
    print(f"Resumo: {resumo_path}")
    print(f"Logs: {pasta_rodada / 'logs'}")
    print("=" * 96)


if __name__ == "__main__":
    main()
