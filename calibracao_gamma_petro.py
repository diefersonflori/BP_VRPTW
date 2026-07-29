
import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURACAO FIXA DA CALIBRACAO (PARTE 3)
# ============================================================
SEED = 123
SM_FIXO = 100
ALPHA_ESTAB = 0.30
TIME_TARGET = 600
TIME_MAX = 600
TIPO_GERACAO = "PD"
MAX_WORKERS = 1  # execucao sequencial (subprocesso por caso) -- tempos comparaveis

# margem de seguranca do timeout externo do subprocess em relacao ao TIME_MAX
# interno do B&P (protege so contra travamentos, nao contra o tempo normal)
TIMEOUT_PROCESSO_MARGEM_S = 180

BASE_DIR = Path(__file__).resolve().parent
PASTA_INSTANCIAS = BASE_DIR / "instancias" / "instancias_petro_geradas" / "instancias_mais_nos"
PASTA_RESULTADOS_RAIZ = BASE_DIR / "resultados_calibracao_gamma"

INSTANCIAS = {
    "A03": "petro_A03_12ped_5plat_3nav_min2_coleta_pesada.json",
    "B03": "petro_B03_15ped_6plat_3nav_min3_forca3v_janelas.json",
    "C01": "petro_C01_18ped_7plat_3nav_min2_forca2v_balanceada.json",
    "E01": "petro_E01_25ped_10plat_4nav_min3_forca3v_balanceada.json",
}

CONFIGURACOES = [
    {"nome": "sem_caixa", "usar_estabilizacao": False, "rho": None},
    {"nome": "rho_001", "usar_estabilizacao": True, "rho": 0.01},
    {"nome": "rho_002", "usar_estabilizacao": True, "rho": 0.02},
    {"nome": "rho_003", "usar_estabilizacao": True, "rho": 0.03},
    {"nome": "rho_005", "usar_estabilizacao": True, "rho": 0.05},
    {"nome": "rho_010", "usar_estabilizacao": True, "rho": 0.10},
    {"nome": "rho_015", "usar_estabilizacao": True, "rho": 0.15},
    {"nome": "rho_020", "usar_estabilizacao": True, "rho": 0.20},
    {"nome": "rho_025", "usar_estabilizacao": True, "rho": 0.25},
    {"nome": "rho_030", "usar_estabilizacao": True, "rho": 0.30},
]
CONFIG_POR_NOME = {c["nome"]: c for c in CONFIGURACOES}

# instancias usadas nos relatorios especificos de refinamento (PARTE nova)
INSTANCIAS_REFINAMENTO = ("A03", "B03")

CAMPOS_CSV = [
    "instancia", "configuracao", "usar_estabilizacao", "rho", "seed",
    "time_target", "time_max", "sm", "alpha_estab",
    "escala_dual", "gamma_ini_efetivo", "gamma_min_efetivo", "gamma_max_efetivo",
    "iter_centro_aceito", "iteracoes_caixa_ativa", "motivo_desligamento_caixa",
    "custo_construtiva", "lb", "ub", "gap_percentual",
    "lb_valido", "arvore_certificada_completa", "otimalidade_certificada",
    "nos", "colunas", "tempo_bp", "motivo_final",
    "pricing_timeout", "parou_por_max_iter", "terminou_por_tempo", "houve_no_interrompido",
    "log",
]

CAMPOS_RESUMO_CONFIG = [
    "configuracao", "rho", "n_execucoes", "n_otimos_certificados", "n_arvores_completas",
    "n_lb_validos", "n_sem_lb", "gap_medio_apenas_lb_valido", "gap_maximo_apenas_lb_valido",
    "ub_medio", "tempo_medio", "tempo_mediano", "nos_medios", "colunas_medias",
    "n_timeouts", "n_pricing_timeouts", "n_interrompidos", "media_iteracoes_caixa_ativa",
]


def csv_val(valor, casas=4):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, float):
        if math.isinf(valor) or math.isnan(valor):
            return ""
        return round(valor, casas)
    return valor


# ============================================================
# MODO WORKER: roda UMA combinacao instancia/configuracao, sozinho
# num processo novo. Escreve o resultado em JSON (--out-json) e imprime
# o log normal (stdout/stderr) -- o processo pai redireciona para o
# arquivo de log da rodada.
# ============================================================
def rodar_worker(instancia_codigo, config_nome, out_json_path):
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    import random as _random

    resultado = {
        "instancia": instancia_codigo,
        "configuracao": config_nome,
        "usar_estabilizacao": None,
        "rho": None,
        "seed": SEED,
        "time_target": TIME_TARGET,
        "time_max": TIME_MAX,
        "sm": SM_FIXO,
        "alpha_estab": ALPHA_ESTAB,
        "escala_dual": None,
        "gamma_ini_efetivo": None,
        "gamma_min_efetivo": None,
        "gamma_max_efetivo": None,
        "iter_centro_aceito": None,
        "iteracoes_caixa_ativa": 0,
        "motivo_desligamento_caixa": None,
        "custo_construtiva": None,
        "lb": None,
        "ub": None,
        "gap_percentual": None,
        "lb_valido": False,
        "arvore_certificada_completa": False,
        "otimalidade_certificada": False,
        "nos": None,
        "colunas": None,
        "tempo_bp": None,
        "motivo_final": "",
        "pricing_timeout": False,
        "parou_por_max_iter": False,
        "terminou_por_tempo": False,
        "houve_no_interrompido": False,
        "log": "",
    }

    try:
        arquivo_instancia = str((PASTA_INSTANCIAS / INSTANCIAS[instancia_codigo]).resolve())
        config = CONFIG_POR_NOME[config_nome]
        resultado["usar_estabilizacao"] = bool(config["usar_estabilizacao"])
        resultado["rho"] = config["rho"]

        from instancia import Instancia
        from metodos import Metodos
        from solucao import Solucao

        inst = Instancia()
        inst.nbcd = 50
        inst.nbn = 52
        inst.nbv = 0
        inst.ninst = 0
        inst.nomeInst = arquivo_instancia
        inst.leitura_petro(arquivo_instancia)

        inst.usar_estabilizacao = bool(config["usar_estabilizacao"])
        inst.nbconstrutiva = 10
        inst.iteraSemMelhora = SM_FIXO

        _random.seed(SEED)

        sol_pool = Solucao(inst.nbv, inst.nbcd)
        sol_pool.FO_TARGET = -1
        sol_pool.time_initial = time.time()
        sol_pool.TIME_TARGET = float(TIME_TARGET)
        sol_pool.TIME_MAX = float(TIME_MAX)
        sol_pool.alpha_estab = ALPHA_ESTAB

        # PARTE 1: modo de gamma. Nao usamos gamma_ini fixo (ex.: 15) para as
        # configuracoes relativas -- o gamma e calculado dentro do B&P a
        # partir da escala dos duais validos encontrados na raiz (ver
        # metodos.py, bloco de aceitacao do centro em resolver_no_com_pool).
        if config["usar_estabilizacao"] and config["rho"] is not None:
            sol_pool.usar_gamma_relativo = True
            sol_pool.gamma_rho = float(config["rho"])
            # gamma_min_factor / gamma_max_factor / gamma_abs_min ficam nos
            # defaults de metodos.py (0.25 / 4.0 / 10.0), conforme PARTE 1.
        else:
            sol_pool.usar_gamma_relativo = False
            sol_pool.gamma_rho = None

        metod = Metodos(inst)
        metod.TABU_TENURE = 0

        t0_construt = time.time()
        metod.init_pool_vazio(inst, sol_pool)
        metod.gera_solucao_inicial(inst, sol_pool)
        metod.adiciona_colunas_ociosas(inst, sol_pool)
        tempo_construtiva = time.time() - t0_construt

        custo_construtiva = sum(
            float(c) for k in range(inst.nbv) for c in sol_pool.rotas[k].get("custo", [])
        )
        resultado["custo_construtiva"] = custo_construtiva
        print(f"[CONSTRUT] {instancia_codigo} | {config_nome} | custo={custo_construtiva:.1f} | tempo={tempo_construtiva:.1f}s", flush=True)

        t0_bp = time.time()
        metod.branch_and_price_global(inst, sol_pool, tipo_geracao=TIPO_GERACAO)
        tempo_bp = time.time() - t0_bp
        resultado["tempo_bp"] = tempo_bp

        ub = metod.best_obj if metod.best_obj > 0 else None

        # PROBLEMA 3 (mesma logica de teste_petro_a03.py / main.py): nunca
        # usar UB como fallback de LB. Prioridade: lb_global_confiavel,
        # depois lb_raiz_confiavel, senao None.
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

        motivo_final = getattr(sol_pool, "motivoConv", "") or ""

        resultado.update({
            "escala_dual": getattr(sol_pool, "escala_dual_raiz", None),
            "gamma_ini_efetivo": getattr(sol_pool, "gamma_ini_efetivo", None),
            "gamma_min_efetivo": getattr(sol_pool, "gamma_min_efetivo", None),
            "gamma_max_efetivo": getattr(sol_pool, "gamma_max_efetivo", None),
            "iter_centro_aceito": getattr(sol_pool, "iter_centro_aceito", None),
            "iteracoes_caixa_ativa": int(getattr(sol_pool, "iteracoes_caixa_ativa", 0)),
            "motivo_desligamento_caixa": getattr(sol_pool, "motivo_desligamento_caixa", None),
            "lb": lb,
            "ub": ub,
            "gap_percentual": gap,
            "lb_valido": lb_valido,
            "arvore_certificada_completa": arvore_certificada_completa,
            "otimalidade_certificada": otimalidade_certificada,
            "nos": metod.total_nos,
            "colunas": metod.total_colunas,
            "motivo_final": motivo_final,
            "pricing_timeout": bool(getattr(sol_pool, "pricing_timeout_algum_no", False)),
            "parou_por_max_iter": bool(getattr(sol_pool, "parou_por_max_iter_algum_no", False)),
            "terminou_por_tempo": bool(getattr(sol_pool, "terminou_por_tempo", False)),
            "houve_no_interrompido": bool(getattr(sol_pool, "houve_no_interrompido", False)),
        })

        lb_str = f"{lb:.2f}" if lb_valido else "NA"
        ub_str = f"{ub:.2f}" if ub is not None else "NA"
        gap_str = f"{gap:.2f}%" if gap is not None else "NA"
        print(
            f"[CALIB_FIM] {instancia_codigo} | {config_nome} | LB={lb_str} | UB={ub_str} | gap={gap_str} | "
            f"lb_valido={lb_valido} | arvore_certificada_completa={arvore_certificada_completa} | "
            f"otimalidade_certificada={otimalidade_certificada} | nos={metod.total_nos} | "
            f"cols={metod.total_colunas} | t={tempo_bp:.1f}s | motivo={motivo_final}",
            flush=True,
        )

    except Exception as exc:
        import traceback
        print(f"[ERRO] {instancia_codigo} | {config_nome}: {exc}\n{traceback.format_exc()}", flush=True)
        resultado["motivo_final"] = f"ERRO: {exc}"

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, default=str)


# ============================================================
# PROCESSO PAI: orquestra as combinacoes, cada uma em subprocesso novo
# ============================================================
def combinacoes_concluidas(resumo_path):
    concluidas = set()
    if not resumo_path.exists():
        return concluidas
    with open(resumo_path, "r", newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=";")
        for linha in leitor:
            concluidas.add((linha["instancia"], linha["configuracao"]))
    return concluidas


def carregar_linhas_existentes(resumo_path):
    if not resumo_path.exists():
        return []
    with open(resumo_path, "r", newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=";")
        return list(leitor)


def rodar_caso_subprocesso(instancia_codigo, config_nome, pasta_rodada):
    nome_caso = f"{instancia_codigo}__{config_nome}"
    pasta_logs = pasta_rodada / "logs"
    pasta_work = pasta_rodada / "work" / nome_caso
    pasta_logs.mkdir(parents=True, exist_ok=True)
    pasta_work.mkdir(parents=True, exist_ok=True)

    log_path = pasta_logs / f"{nome_caso}.txt"
    out_json_path = pasta_rodada / "work" / f"{nome_caso}.json"

    cmd = [
        sys.executable, str(Path(__file__).resolve()),
        "--worker",
        "--instancia-codigo", instancia_codigo,
        "--config-nome", config_nome,
        "--out-json", str(out_json_path),
    ]

    print(f"[INICIO] {nome_caso}", flush=True)
    t0 = time.time()
    timeout_s = TIME_MAX + TIMEOUT_PROCESSO_MARGEM_S
    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            subprocess.run(
                cmd, cwd=str(pasta_work), stdout=log_fh, stderr=subprocess.STDOUT,
                timeout=timeout_s, check=False,
            )
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT PROCESSO] {nome_caso} nao terminou em {timeout_s}s -- processo encerrado.", flush=True)

    tempo_total = time.time() - t0

    if out_json_path.exists():
        with open(out_json_path, "r", encoding="utf-8") as f:
            resultado = json.load(f)
    else:
        # subprocesso morreu antes de escrever o JSON (timeout, crash duro, etc.)
        config = CONFIG_POR_NOME[config_nome]
        resultado = {campo: None for campo in CAMPOS_CSV}
        resultado.update({
            "instancia": instancia_codigo, "configuracao": config_nome,
            "usar_estabilizacao": bool(config["usar_estabilizacao"]), "rho": config["rho"],
            "seed": SEED, "time_target": TIME_TARGET, "time_max": TIME_MAX,
            "sm": SM_FIXO, "alpha_estab": ALPHA_ESTAB,
            "iteracoes_caixa_ativa": 0, "lb_valido": False,
            "arvore_certificada_completa": False, "otimalidade_certificada": False,
            "tempo_bp": tempo_total, "motivo_final": "TIMEOUT_PROCESSO_EXTERNO",
            "pricing_timeout": False, "parou_por_max_iter": False,
            "terminou_por_tempo": True, "houve_no_interrompido": False,
        })

    resultado["log"] = str(log_path)
    return resultado


def gravar_linha_csv(resumo_path, linha):
    novo = not resumo_path.exists()
    with open(resumo_path, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=";")
        if novo:
            escritor.writeheader()
        escritor.writerow({campo: csv_val(linha.get(campo)) for campo in CAMPOS_CSV})


# ============================================================
# PARTE 6 -- resumo agregado por configuracao
# ============================================================
def _to_float_ou_none(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if math.isinf(f) or math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def gerar_resumo_por_configuracao(linhas, caminho_saida):
    linhas_por_config = {c["nome"]: [] for c in CONFIGURACOES}
    for linha in linhas:
        cfg = linha.get("configuracao")
        if cfg in linhas_por_config:
            linhas_por_config[cfg].append(linha)

    resumo = []
    for config in CONFIGURACOES:
        nome = config["nome"]
        rows = linhas_por_config[nome]
        n_exec = len(rows)

        n_otimos = sum(1 for r in rows if _to_bool(r.get("otimalidade_certificada")))
        n_arvores = sum(1 for r in rows if _to_bool(r.get("arvore_certificada_completa")))
        n_lb_validos = sum(1 for r in rows if _to_bool(r.get("lb_valido")))
        n_sem_lb = n_exec - n_lb_validos

        gaps_validos = [
            _to_float_ou_none(r.get("gap_percentual"))
            for r in rows
            if _to_bool(r.get("lb_valido")) and _to_float_ou_none(r.get("gap_percentual")) is not None
        ]
        gaps_validos = [g for g in gaps_validos if g is not None]

        ubs = [v for v in (_to_float_ou_none(r.get("ub")) for r in rows) if v is not None]
        tempos = [v for v in (_to_float_ou_none(r.get("tempo_bp")) for r in rows) if v is not None]
        nos_vals = [v for v in (_to_float_ou_none(r.get("nos")) for r in rows) if v is not None]
        col_vals = [v for v in (_to_float_ou_none(r.get("colunas")) for r in rows) if v is not None]
        iters_caixa = [v for v in (_to_float_ou_none(r.get("iteracoes_caixa_ativa")) for r in rows) if v is not None]

        n_timeouts = sum(1 for r in rows if _to_bool(r.get("terminou_por_tempo")))
        n_pricing_to = sum(1 for r in rows if _to_bool(r.get("pricing_timeout")))
        n_interrompidos = sum(1 for r in rows if _to_bool(r.get("houve_no_interrompido")))

        resumo.append({
            "configuracao": nome,
            "rho": config["rho"],
            "n_execucoes": n_exec,
            "n_otimos_certificados": n_otimos,
            "n_arvores_completas": n_arvores,
            "n_lb_validos": n_lb_validos,
            "n_sem_lb": n_sem_lb,
            "gap_medio_apenas_lb_valido": statistics.mean(gaps_validos) if gaps_validos else None,
            "gap_maximo_apenas_lb_valido": max(gaps_validos) if gaps_validos else None,
            "ub_medio": statistics.mean(ubs) if ubs else None,
            "tempo_medio": statistics.mean(tempos) if tempos else None,
            "tempo_mediano": statistics.median(tempos) if tempos else None,
            "nos_medios": statistics.mean(nos_vals) if nos_vals else None,
            "colunas_medias": statistics.mean(col_vals) if col_vals else None,
            "n_timeouts": n_timeouts,
            "n_pricing_timeouts": n_pricing_to,
            "n_interrompidos": n_interrompidos,
            "media_iteracoes_caixa_ativa": statistics.mean(iters_caixa) if iters_caixa else None,
        })

    with open(caminho_saida, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_RESUMO_CONFIG, delimiter=";")
        escritor.writeheader()
        for r in resumo:
            escritor.writerow({campo: csv_val(r.get(campo)) for campo in CAMPOS_RESUMO_CONFIG})

    return resumo


# ============================================================
# PARTE 7 -- criterio de comparacao (nao escolhe so pelo tempo)
# ============================================================
def _chave_comparacao(resumo_cfg):
    """Ordena por: mais otimos certificados, mais LBs validos, menor gap
    medio (LB valido), menor tempo, menos nos, menos colunas -- nessa ordem.
    None em qualquer criterio conta como pior (vai para o fim)."""
    gap = resumo_cfg["gap_medio_apenas_lb_valido"]
    tempo = resumo_cfg["tempo_medio"]
    nos = resumo_cfg["nos_medios"]
    cols = resumo_cfg["colunas_medias"]
    return (
        -resumo_cfg["n_otimos_certificados"],
        -resumo_cfg["n_lb_validos"],
        gap if gap is not None else float("inf"),
        tempo if tempo is not None else float("inf"),
        nos if nos is not None else float("inf"),
        cols if cols is not None else float("inf"),
    )


def _domina(a, b):
    """True se 'a' e melhor ou igual a 'b' em TODOS os criterios e
    estritamente melhor em pelo menos um (dominancia de Pareto)."""
    ka, kb = _chave_comparacao(a), _chave_comparacao(b)
    melhor_ou_igual = all(xa <= xb for xa, xb in zip(ka, kb))
    estritamente_melhor = any(xa < xb for xa, xb in zip(ka, kb))
    return melhor_ou_igual and estritamente_melhor


def configuracoes_nao_dominadas(resumo):
    nao_dominadas = []
    for cfg in resumo:
        if cfg["n_execucoes"] == 0:
            continue
        if not any(_domina(outro, cfg) for outro in resumo if outro is not cfg and outro["n_execucoes"] > 0):
            nao_dominadas.append(cfg["configuracao"])
    return nao_dominadas


def melhor_ub_por_instancia(linhas):
    """Para cada instancia, qual(is) configuracao(oes) tiveram o melhor UB
    (empate = todas com o mesmo melhor valor)."""
    por_instancia = {}
    for linha in linhas:
        inst = linha.get("instancia")
        ub = _to_float_ou_none(linha.get("ub"))
        if ub is None:
            continue
        por_instancia.setdefault(inst, []).append((linha.get("configuracao"), ub))

    vencedores = {}
    for inst, pares in por_instancia.items():
        melhor = min(v for _, v in pares)
        vencedores[inst] = sorted({c for c, v in pares if abs(v - melhor) <= 1e-6})
    return vencedores


def montar_tabela_por_instancia(linhas, instancias=None):
    """Uma tabela por instancia, uma linha por configuracao, com
    LB/UB/gap/certificacao/tempo/nos/colunas/gamma efetivo/iteracoes caixa ativa.

    'instancias' permite restringir a um subconjunto (ex.: relatorio de
    refinamento A03/B03); por padrao usa todas as INSTANCIAS."""
    tabelas = {}
    for codigo in (instancias if instancias is not None else INSTANCIAS.keys()):
        linhas_inst = [l for l in linhas if l.get("instancia") == codigo]
        if not linhas_inst:
            continue
        por_config = {l.get("configuracao"): l for l in linhas_inst}
        linhas_tabela = []
        for config in CONFIGURACOES:
            l = por_config.get(config["nome"])
            if l is None:
                linhas_tabela.append({"configuracao": config["nome"], "sem_dados": True})
                continue
            linhas_tabela.append({
                "configuracao": config["nome"],
                "lb": _to_float_ou_none(l.get("lb")),
                "ub": _to_float_ou_none(l.get("ub")),
                "gap": _to_float_ou_none(l.get("gap_percentual")),
                "otimalidade_certificada": _to_bool(l.get("otimalidade_certificada")),
                "arvore_certificada_completa": _to_bool(l.get("arvore_certificada_completa")),
                "tempo_bp": _to_float_ou_none(l.get("tempo_bp")),
                "nos": _to_float_ou_none(l.get("nos")),
                "colunas": _to_float_ou_none(l.get("colunas")),
                "gamma_ini_efetivo": _to_float_ou_none(l.get("gamma_ini_efetivo")),
                "iteracoes_caixa_ativa": _to_float_ou_none(l.get("iteracoes_caixa_ativa")),
            })
        tabelas[codigo] = linhas_tabela
    return tabelas


def _fmt(v, casas=2, pct=False):
    if v is None:
        return "NA"
    if isinstance(v, bool):
        return "sim" if v else "nao"
    if pct:
        return f"{v:.{casas}f}%"
    return f"{v:.{casas}f}"


def montar_relatorio_comparacao(linhas, resumo_config, instancias=None, titulo_extra=None):
    out = []
    if titulo_extra:
        out.append("=" * 96)
        out.append(titulo_extra)
        out.append("=" * 96)
        out.append("")
    out.append("=" * 96)
    out.append("RESUMO AGREGADO POR CONFIGURACAO")
    out.append("=" * 96)
    for r in resumo_config:
        out.append(
            f"{r['configuracao']:10s} | rho={str(r['rho']):6s} | n={r['n_execucoes']} | "
            f"otimos_certificados={r['n_otimos_certificados']} | arvores_completas={r['n_arvores_completas']} | "
            f"lb_validos={r['n_lb_validos']} | sem_lb={r['n_sem_lb']} | "
            f"gap_medio={_fmt(r['gap_medio_apenas_lb_valido'], pct=True)} | "
            f"gap_max={_fmt(r['gap_maximo_apenas_lb_valido'], pct=True)} | "
            f"ub_medio={_fmt(r['ub_medio'])} | tempo_medio={_fmt(r['tempo_medio'])}s | "
            f"tempo_mediano={_fmt(r['tempo_mediano'])}s | nos_medios={_fmt(r['nos_medios'], 1)} | "
            f"colunas_medias={_fmt(r['colunas_medias'], 1)} | timeouts={r['n_timeouts']} | "
            f"pricing_timeouts={r['n_pricing_timeouts']} | interrompidos={r['n_interrompidos']} | "
            f"iter_caixa_ativa_media={_fmt(r['media_iteracoes_caixa_ativa'], 1)}"
        )

    out.append("")
    out.append("=" * 96)
    out.append("TABELA POR INSTANCIA")
    out.append("=" * 96)
    tabelas = montar_tabela_por_instancia(linhas, instancias=instancias)
    for codigo, linhas_tab in tabelas.items():
        out.append(f"\n--- {codigo} ({INSTANCIAS[codigo]}) ---")
        for lt in linhas_tab:
            if lt.get("sem_dados"):
                out.append(f"  {lt['configuracao']:10s} | sem dados (nao executado)")
                continue
            out.append(
                f"  {lt['configuracao']:10s} | LB={_fmt(lt['lb'])} | UB={_fmt(lt['ub'])} | "
                f"gap={_fmt(lt['gap'], pct=True)} | otim_cert={_fmt(lt['otimalidade_certificada'])} | "
                f"arvore_completa={_fmt(lt['arvore_certificada_completa'])} | "
                f"tempo={_fmt(lt['tempo_bp'])}s | nos={_fmt(lt['nos'], 0)} | colunas={_fmt(lt['colunas'], 0)} | "
                f"gamma_efetivo={_fmt(lt['gamma_ini_efetivo'])} | iter_caixa_ativa={_fmt(lt['iteracoes_caixa_ativa'], 0)}"
            )

    out.append("")
    out.append("=" * 96)
    out.append("MELHOR UB POR INSTANCIA (empate = todas listadas)")
    out.append("=" * 96)
    for inst, vencedores in melhor_ub_por_instancia(linhas).items():
        out.append(f"  {inst}: {', '.join(vencedores)}")

    out.append("")
    out.append("=" * 96)
    out.append("CRITERIO DE COMPARACAO (ordem: otimalidades certificadas > LBs validos > "
                "gap medio (so LB valido) > melhor UB por instancia > tempo > nos > colunas)")
    out.append("=" * 96)
    ordenado = sorted([r for r in resumo_config if r["n_execucoes"] > 0], key=_chave_comparacao)
    for i, r in enumerate(ordenado, start=1):
        out.append(f"  {i}. {r['configuracao']}")

    nao_dominadas = configuracoes_nao_dominadas(resumo_config)
    out.append("")
    if len(nao_dominadas) > 1:
        out.append(
            f"[SEM VENCEDOR UNICO] Configuracoes NAO dominadas (empate conceitual): {', '.join(nao_dominadas)}. "
            f"Nenhuma delas e estritamente melhor que as outras em todos os criterios -- "
            f"a escolha final depende de prioridade (robustez de certificacao x tempo)."
        )
    elif len(nao_dominadas) == 1:
        out.append(f"[RECOMENDACAO PRELIMINAR] Configuracao nao dominada: {nao_dominadas[0]} "
                    f"(melhor ou igual a todas as outras em todos os criterios, e melhor em pelo menos um).")
    else:
        out.append("[SEM DADOS SUFICIENTES] Nenhuma configuracao com execucoes para comparar.")

    return "\n".join(out)


# ============================================================
# ORQUESTRACAO PRINCIPAL
# ============================================================
def montar_lista_casos(instancias_selecionadas, configs_selecionadas):
    casos = []
    for codigo in instancias_selecionadas:
        for config in configs_selecionadas:
            casos.append((codigo, config["nome"]))
    return casos


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--retomar", type=str, default=None, help="nome (ou caminho) da pasta de rodada a retomar")
    parser.add_argument("--somente", action="append", default=None, choices=list(INSTANCIAS.keys()),
                         help="codigo da instancia (A03, B03, C01, E01); pode repetir")
    parser.add_argument("--config", action="append", default=None, choices=list(CONFIG_POR_NOME.keys()),
                         help="nome da configuracao (" + ", ".join(CONFIG_POR_NOME.keys()) + "); pode repetir")
    parser.add_argument("--listar-pendentes", action="store_true",
                         help="lista casos concluidos e pendentes da rodada (--retomar, ou a mais recente se "
                              "omitido) e sai -- nao cria .lock, nao altera CSV, nao executa B&P")
    # modo interno (self-invocacao em subprocesso); nao documentado para uso direto
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--instancia-codigo", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--config-nome", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--out-json", type=str, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        rodar_worker(args.instancia_codigo, args.config_nome, args.out_json)
        return

    instancias_selecionadas = args.somente if args.somente else list(INSTANCIAS.keys())
    configs_selecionadas = (
        [CONFIG_POR_NOME[c] for c in args.config] if args.config else CONFIGURACOES
    )

    if args.listar_pendentes:
        if args.retomar:
            candidato = Path(args.retomar)
            pasta_rodada = candidato if candidato.is_absolute() or candidato.exists() else PASTA_RESULTADOS_RAIZ / args.retomar
        else:
            pastas = sorted(PASTA_RESULTADOS_RAIZ.glob("rodada_*")) if PASTA_RESULTADOS_RAIZ.exists() else []
            pasta_rodada = pastas[-1] if pastas else None

        resumo_path_consulta = pasta_rodada / "resumo_calibracao_gamma.csv" if pasta_rodada else None
        ja_concluidos = combinacoes_concluidas(resumo_path_consulta) if resumo_path_consulta else set()

        casos = montar_lista_casos(instancias_selecionadas, configs_selecionadas)
        casos_concluidos = [(i, c) for (i, c) in casos if (i, c) in ja_concluidos]
        casos_pendentes = [(i, c) for (i, c) in casos if (i, c) not in ja_concluidos]

        print("=" * 96)
        print("LISTAGEM DE PENDENCIAS (--listar-pendentes) -- nao cria .lock, nao altera CSV, nao executa B&P")
        print(f"Pasta de rodada consultada: {pasta_rodada if pasta_rodada else '(nenhuma -- nada concluido ainda)'}")
        print("=" * 96)
        print(f"\nCONCLUIDOS ({len(casos_concluidos)}):")
        for i, c in casos_concluidos:
            print(f"  [OK] {i} | {c}")
        print(f"\nPENDENTES ({len(casos_pendentes)}):")
        for i, c in casos_pendentes:
            print(f"  [--] {i} | {c}")
        print(f"\nTotal: {len(casos)} | concluidos: {len(casos_concluidos)} | pendentes: {len(casos_pendentes)}")
        return

    if args.retomar:
        candidato = Path(args.retomar)
        pasta_rodada = candidato if candidato.is_absolute() or candidato.exists() else PASTA_RESULTADOS_RAIZ / args.retomar
        if not pasta_rodada.exists():
            raise FileNotFoundError(f"Pasta de rodada para retomar nao encontrada: {pasta_rodada}")
    else:
        id_rodada = datetime.now().strftime("rodada_%Y%m%d_%H%M%S")
        pasta_rodada = PASTA_RESULTADOS_RAIZ / id_rodada
        pasta_rodada.mkdir(parents=True, exist_ok=True)

    lock_path = pasta_rodada / ".lock"
    if lock_path.exists():
        raise RuntimeError(
            f"Ja existe uma calibracao em andamento (ou interrompida sem limpeza) nesta pasta: {lock_path}. "
            f"Nao rode duas calibracoes simultaneamente na mesma pasta de rodada. "
            f"Se tiver certeza de que nao ha outra execucao ativa, apague o arquivo .lock e tente de novo."
        )
    lock_path.write_text(str(os.getpid()), encoding="utf-8")

    resumo_path = pasta_rodada / "resumo_calibracao_gamma.csv"
    resumo_ordenado_path = pasta_rodada / "resumo_calibracao_gamma_ordenado.csv"
    resumo_config_path = pasta_rodada / "resumo_por_configuracao.csv"
    comparacao_path = pasta_rodada / "comparacao_final.txt"

    ja_concluidos = combinacoes_concluidas(resumo_path)
    casos = montar_lista_casos(instancias_selecionadas, configs_selecionadas)
    casos_pendentes = [(i, c) for (i, c) in casos if (i, c) not in ja_concluidos]

    print("=" * 96)
    print("CALIBRACAO DE GAMMA -- BRANCH-AND-PRICE PETROBRAS")
    print(f"Pasta da rodada: {pasta_rodada}")
    print(f"Instancias selecionadas: {instancias_selecionadas}")
    print(f"Configuracoes selecionadas: {[c['nome'] for c in configs_selecionadas]}")
    print(f"Total de combinacoes pedidas: {len(casos)} | ja concluidas: {len(ja_concluidos & set(casos))} | pendentes: {len(casos_pendentes)}")
    print("=" * 96)

    try:
        for instancia_codigo, config_nome in casos_pendentes:
            resultado = rodar_caso_subprocesso(instancia_codigo, config_nome, pasta_rodada)
            gravar_linha_csv(resumo_path, resultado)
            print(
                f"[CONCLUIDO] {instancia_codigo} | {config_nome} | "
                f"LB={csv_val(resultado.get('lb'))} | UB={csv_val(resultado.get('ub'))} | "
                f"gap={csv_val(resultado.get('gap_percentual'))} | t={csv_val(resultado.get('tempo_bp'))}s",
                flush=True,
            )
    finally:
        lock_path.unlink(missing_ok=True)

    linhas = carregar_linhas_existentes(resumo_path)

    # resumo ordenado (por instancia, depois configuracao, ordem fixa)
    ordem_config = {c["nome"]: i for i, c in enumerate(CONFIGURACOES)}
    linhas_ordenadas = sorted(
        linhas, key=lambda l: (l.get("instancia", ""), ordem_config.get(l.get("configuracao"), 99))
    )
    with open(resumo_ordenado_path, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=";")
        escritor.writeheader()
        for l in linhas_ordenadas:
            escritor.writerow({campo: l.get(campo, "") for campo in CAMPOS_CSV})

    if (not args.retomar) or (not resumo_config_path.exists()) or (not comparacao_path.exists()):
        resumo_config = gerar_resumo_por_configuracao(linhas, resumo_config_path)
        relatorio = montar_relatorio_comparacao(linhas, resumo_config)
        comparacao_path.write_text(relatorio, encoding="utf-8")
        print("\n" + relatorio)
    else:
        print("[PRESERVADO] resumo_por_configuracao.csv da calibracao original")
        print("[PRESERVADO] comparacao_final.txt da calibracao original")

    print("\n" + "=" * 96)
    print(f"Finalizado. {len(linhas)} linha(s) no resumo: {resumo_path}")
    print(f"Resumo por configuracao: {resumo_config_path}")
    print(f"Comparacao final: {comparacao_path}")
    print("=" * 96)

    # ============================================================
    # Relatorios especificos de refinamento -- somente A03/B03, dez configs
    # ============================================================
    linhas_refinamento = [l for l in linhas if l.get("instancia") in INSTANCIAS_REFINAMENTO]
    if linhas_refinamento:
        resumo_refinamento_path = pasta_rodada / "resumo_refinamento_A03_B03.csv"
        resumo_config_refinamento_path = pasta_rodada / "resumo_por_configuracao_refinamento_A03_B03.csv"
        comparacao_refinamento_path = pasta_rodada / "comparacao_refinamento_A03_B03.txt"

        linhas_refinamento_ordenadas = sorted(
            linhas_refinamento,
            key=lambda l: (l.get("instancia", ""), ordem_config.get(l.get("configuracao"), 99)),
        )
        with open(resumo_refinamento_path, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=";")
            escritor.writeheader()
            for l in linhas_refinamento_ordenadas:
                escritor.writerow({campo: l.get(campo, "") for campo in CAMPOS_CSV})

        resumo_config_refinamento = gerar_resumo_por_configuracao(
            linhas_refinamento, resumo_config_refinamento_path
        )
        relatorio_refinamento = montar_relatorio_comparacao(
            linhas_refinamento, resumo_config_refinamento,
            instancias=INSTANCIAS_REFINAMENTO,
            titulo_extra="REFINAMENTO A03/B03 -- DEZ CONFIGURACOES DE RHO",
        )
        comparacao_refinamento_path.write_text(relatorio_refinamento, encoding="utf-8")

        print(f"Resumo refinamento A03/B03: {resumo_refinamento_path}")
        print(f"Resumo por configuracao (refinamento A03/B03): {resumo_config_refinamento_path}")
        print(f"Comparacao (refinamento A03/B03): {comparacao_refinamento_path}")
        print("=" * 96)


if __name__ == "__main__":
    main()
