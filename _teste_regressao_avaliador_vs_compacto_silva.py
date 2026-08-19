import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

# ============================================================
# REGRESSAO: avaliar_rota_silva2024 x modelo compacto (Gurobi) COM ROTA FIXADA
# (fixar_rotas), para varias rotas fixas (feasiveis e inviaveis) e varios
# alphaWeight (0.0, 0.1, 1.0). NAO altera pricing_silva2024 nem o B&P -- so
# testa avaliar_rota_silva2024 contra metodo_exato_petro(fixar_rotas=...).
#
# Cada "particao" abaixo e um par de rotas (k=0, k=1) que cobre TODOS os 14
# clientes da instancia (exigido pelo modelo: sum_k visita[i,k]==1).
#
# Classificacao por linha (particao, k, alpha):
#   FAIL           -- viabilidade diverge, OU custo diverge >TOL, OU f1
#                     diverge >TOL quando f1 participa da FO (alpha>0), OU f2
#                     diverge >TOL quando f2 participa da FO (alpha<1).
#   DEGENERADO_OK  -- viabilidade e custo (e f1/f2 quando participam) batem,
#                     mas B/P/R/F/hF/hB/hN/hDP diferem -- multiplas solucoes
#                     otimas com a MESMA FO (nao e erro).
#   SKIP           -- rota viavel isolada cujo par tem OUTRA rota
#                     intencionalmente inviavel -- joint model nao produz
#                     numeros comparaveis para ela.
#   PASS           -- tudo bate, inclusive B/P/R/F.
# ============================================================

ARQ = BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json"
TOL = 1e-6

PARTICOES = {
    "P1_baseline": {
        0: [0, 8, 1, 15],
        1: [0, 9, 10, 5, 7, 6, 2, 3, 4, 11, 13, 14, 12, 15],
    },
    "P2_medio_semEspera_e_esperaGrande": {
        0: [0, 8, 9, 10, 11, 12, 13, 14, 15],
        1: [0, 1, 2, 3, 4, 5, 6, 7, 15],
    },
    "P3_trivial_e_TDLinviavel": {
        0: [0, 1, 15],
        1: [0, 8, 9, 10, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15],
    },
    "P4_grande_com_espera_moderada": {
        1: [0, 7, 6, 15],
        0: [0, 1, 8, 9, 10, 2, 3, 4, 5, 11, 12, 13, 14, 15],
    },
    "P6_trivial_e_janelaInviavel": {
        0: [0, 1, 15],
        1: [0, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 8, 9, 10, 15],
    },
}

ALPHAS = [0.0, 0.1, 1.0]

CAMPOS_POSICIONAIS = ["B", "P", "R", "F", "F_menos_B", "hF", "hB", "hN", "hDP"]


def extrair_avaliador(metod, inst, k, seq):
    r = metod.avaliar_rota_silva2024(inst, k, seq, diagnostico=False)
    if not r["viavel"]:
        return {"viavel": False, "motivo": r["motivo"]}
    hF = r["B"] - r["AT"]
    return {
        "viavel": True,
        "B": r["B"], "P": r["P"], "R": r["R"], "F": r["F"],
        "F_menos_B": r["F"] - r["B"],
        "hF": hF, "hB": r["hB"], "hN": r["hN"], "hDP": r["hDP"],
        "f1": r["f1"], "f2": r["f2"], "custo": r["custo"],
    }


def extrair_gurobi(sol_fix, k, alpha_fo, eta_fo):
    diag = getattr(sol_fix, "exato_petro_silva_diag", {}) or {}
    d = diag[k]
    custo = alpha_fo * d["f1"] + (1.0 - alpha_fo) * eta_fo * d["f2"]
    return {
        "viavel": True,
        "B": d["B"], "P": d["P"], "R": d["R"], "F": d["F"],
        "F_menos_B": d["dur"],
        "hF": d["hF"], "hB": d["hB"], "hN": d["hN"], "hDP": d["hDP"],
        "f1": d["f1"], "f2": d["f2"], "custo": custo,
    }


def classifica(nome_particao, k, alpha, eta_fo, av, gu, divergencias):
    """Retorna (status, linha_resumo_dict)."""
    f1_participa = alpha > 0.0
    f2_participa = (1.0 - alpha) * eta_fo != 0.0

    diff_custo = abs(av["custo"] - gu["custo"])
    diff_f1 = abs(av["f1"] - gu["f1"])
    diff_f2 = abs(av["f2"] - gu["f2"])
    diff_B = abs(av["B"] - gu["B"])

    fail_motivos = []
    if diff_custo > TOL:
        fail_motivos.append(f"custo diff={diff_custo:.3e}")
    if f1_participa and diff_f1 > TOL:
        fail_motivos.append(f"f1 diff={diff_f1:.3e} (participa, alpha={alpha}>0)")
    if f2_participa and diff_f2 > TOL:
        fail_motivos.append(f"f2 diff={diff_f2:.3e} (participa, alpha={alpha}<1)")

    if fail_motivos:
        status = "FAIL"
        divergencias.append(f"[{nome_particao} k={k} alpha={alpha}] " + "; ".join(fail_motivos))
    else:
        posicional_diverge = any(abs(av[c] - gu[c]) > TOL for c in CAMPOS_POSICIONAIS)
        status = "DEGENERADO_OK" if posicional_diverge else "PASS"

    linha = {
        "particao": nome_particao, "k": k, "alpha": alpha, "status": status,
        "viavel_av": av["viavel"], "viavel_gu": gu["viavel"],
        "custo_av": av["custo"], "custo_gu": gu["custo"], "diff_custo": diff_custo,
        "f1_av": av["f1"], "f1_gu": gu["f1"],
        "f2_av": av["f2"], "f2_gu": gu["f2"],
        "B_av": av["B"], "B_gu": gu["B"],
    }
    return status, linha


def main():
    inst = Instancia()
    inst.leitura_petro(str(ARQ))
    metod = Metodos(inst)

    linhas_resumo = []
    divergencias = []
    resumo_particao_alpha = {}

    for nome_particao, rotas in PARTICOES.items():
        for alpha in ALPHAS:
            inst.alpha_fo = alpha
            eta_fo = float(inst.eta_fo)

            print("\n" + "#" * 100)
            print(f"# PARTICAO={nome_particao} alpha_fo={alpha}")
            print("#" * 100)

            avaliador_por_k = {k: extrair_avaliador(metod, inst, k, seq) for k, seq in rotas.items()}
            for k, seq in rotas.items():
                av = avaliador_por_k[k]
                if av["viavel"]:
                    print(f"[AVALIADOR] k={k} seq={seq}\n  viavel=True custo={av['custo']:.6f} "
                          f"B={av['B']:.4f} P={av['P']:.4f} R={av['R']:.4f} F={av['F']:.4f} "
                          f"F-B={av['F_menos_B']:.4f} hF={av['hF']:.4f} f1={av['f1']:.4f} f2={av['f2']:.4f}")
                else:
                    print(f"[AVALIADOR] k={k} seq={seq}\n  viavel=False motivo={av['motivo']}")

            sol_fix = Solucao(inst.nbv, inst.nbn)
            ok_fix = metod.metodo_exato_petro(
                inst, sol_fix, time_limit=60, threads=4, salvar_modelo=False, diagnostico=False,
                fixar_rotas=rotas, considerar_conflito_plataforma=True,
            )
            status_gurobi = getattr(sol_fix, "exato_petro_status", None)
            consistente = bool(getattr(sol_fix, "exato_petro_consistente", None))
            joint_ok = bool(ok_fix) and consistente
            print(f"[GUROBI fixar_rotas] ok={ok_fix} status={status_gurobi} consistente={consistente}")

            ks_avaliador_inviavel = {k for k, av in avaliador_por_k.items() if not av["viavel"]}

            particao_ok = True
            for k, seq in rotas.items():
                av = avaliador_por_k[k]

                if av["viavel"] and not ks_avaliador_inviavel:
                    if joint_ok:
                        gu = extrair_gurobi(sol_fix, k, alpha, eta_fo)
                        status, linha = classifica(nome_particao, k, alpha, eta_fo, av, gu, divergencias)
                        linhas_resumo.append(linha)
                        particao_ok = particao_ok and status != "FAIL"
                    else:
                        particao_ok = False
                        divergencias.append(
                            f"[{nome_particao} k={k} alpha={alpha}] DIVERGENCIA: avaliador diz TODAS as "
                            f"rotas da particao viaveis, mas Gurobi (fixar_rotas) nao achou solucao "
                            f"consistente (status={status_gurobi}, consistente={consistente})."
                        )
                        linhas_resumo.append({
                            "particao": nome_particao, "k": k, "alpha": alpha, "status": "FAIL",
                            "viavel_av": True, "viavel_gu": False,
                            "custo_av": av["custo"], "custo_gu": None, "diff_custo": None,
                            "f1_av": av["f1"], "f1_gu": None, "f2_av": av["f2"], "f2_gu": None,
                            "B_av": av["B"], "B_gu": None,
                        })

                elif av["viavel"] and ks_avaliador_inviavel:
                    if joint_ok:
                        gu = extrair_gurobi(sol_fix, k, alpha, eta_fo)
                        status, linha = classifica(nome_particao, k, alpha, eta_fo, av, gu, divergencias)
                        linhas_resumo.append(linha)
                        particao_ok = particao_ok and status != "FAIL"
                    else:
                        linhas_resumo.append({
                            "particao": nome_particao, "k": k, "alpha": alpha, "status": "SKIP",
                            "viavel_av": True, "viavel_gu": None,
                            "custo_av": av["custo"], "custo_gu": None, "diff_custo": None,
                            "f1_av": av["f1"], "f1_gu": None, "f2_av": av["f2"], "f2_gu": None,
                            "B_av": av["B"], "B_gu": None,
                        })

                else:
                    if not joint_ok:
                        linhas_resumo.append({
                            "particao": nome_particao, "k": k, "alpha": alpha, "status": "PASS",
                            "viavel_av": False, "viavel_gu": False,
                            "custo_av": None, "custo_gu": None, "diff_custo": None,
                            "f1_av": None, "f1_gu": None, "f2_av": None, "f2_gu": None,
                            "B_av": None, "B_gu": None,
                        })
                    else:
                        particao_ok = False
                        divergencias.append(
                            f"[{nome_particao} k={k} alpha={alpha}] DIVERGENCIA: avaliador rejeitou a rota "
                            f"(motivo={av['motivo']}) mas Gurobi (fixar_rotas) encontrou solucao "
                            f"consistente para a particao inteira."
                        )
                        linhas_resumo.append({
                            "particao": nome_particao, "k": k, "alpha": alpha, "status": "FAIL",
                            "viavel_av": False, "viavel_gu": True,
                            "custo_av": None, "custo_gu": None, "diff_custo": None,
                            "f1_av": None, "f1_gu": None, "f2_av": None, "f2_gu": None,
                            "B_av": None, "B_gu": None,
                        })

            resumo_particao_alpha[(nome_particao, alpha)] = particao_ok

    def fmt(v, nd=4):
        return "-" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))

    print("\n\n" + "=" * 160)
    print("TABELA RESUMO (particao, k, alpha, viabilidade, custo av/gu, diff, f1 av/gu, f2 av/gu, B av/gu, status)")
    print("=" * 160)
    header = (f"{'particao':38s} {'k':>2} {'alpha':>5} {'viav(av/gu)':>13} "
              f"{'custo_av':>12} {'custo_gu':>12} {'diff_custo':>11} "
              f"{'f1_av':>12} {'f1_gu':>12} {'f2_av':>10} {'f2_gu':>10} "
              f"{'B_av':>8} {'B_gu':>8}  status")
    print(header)
    for l in linhas_resumo:
        viav = f"{l['viavel_av']}/{l['viavel_gu']}"
        print(f"{l['particao']:38s} {l['k']:>2} {l['alpha']:>5} {viav:>13} "
              f"{fmt(l['custo_av']):>12} {fmt(l['custo_gu']):>12} {fmt(l['diff_custo'], 3):>11} "
              f"{fmt(l['f1_av']):>12} {fmt(l['f1_gu']):>12} {fmt(l['f2_av'], 3):>10} {fmt(l['f2_gu'], 3):>10} "
              f"{fmt(l['B_av'], 3):>8} {fmt(l['B_gu'], 3):>8}  {l['status']}")

    print("\n\n" + "=" * 120)
    print("RESUMO PASS/FAIL POR PARTICAO x ALPHA (FAIL = viabilidade/custo/f1/f2 divergentes; DEGENERADO_OK nao conta como FAIL)")
    print("=" * 120)
    print(f"{'particao':38s} {'alpha=0.0':>12} {'alpha=0.1':>12} {'alpha=1.0':>12}")
    todas_ok = True
    for nome_particao in PARTICOES:
        linha = f"{nome_particao:38s}"
        for alpha in ALPHAS:
            ok = resumo_particao_alpha[(nome_particao, alpha)]
            todas_ok = todas_ok and ok
            linha += f" {'PASS' if ok else 'FAIL':>12}"
        print(linha)

    print("\n" + "=" * 120)
    if divergencias:
        print(f"[DIVERGENCIAS REAIS ENCONTRADAS] ({len(divergencias)})")
        for d in divergencias:
            print(f"  - {d}")
    else:
        print("[NENHUMA DIVERGENCIA REAL] viabilidade, custo, f1 (quando participa) e f2 (quando participa) "
              f"bateram em todas as particoes/alphas, tolerancia {TOL:.1e}. Diferencas remanescentes em "
              "B/P/R/F/hF/hB/hN/hDP (se houver) sao degenerescencia de solucoes otimas equivalentes.")
    print("=" * 120)

    n_degenerado = sum(1 for l in linhas_resumo if l["status"] == "DEGENERADO_OK")
    n_skip = sum(1 for l in linhas_resumo if l["status"] == "SKIP")
    n_pass = sum(1 for l in linhas_resumo if l["status"] == "PASS")
    n_fail = sum(1 for l in linhas_resumo if l["status"] == "FAIL")
    print(f"\nContagem: PASS={n_pass} DEGENERADO_OK={n_degenerado} SKIP={n_skip} FAIL={n_fail} "
          f"(total linhas={len(linhas_resumo)})")

    print(f"\n[RESULTADO FINAL REGRESSAO] {'TODAS AS PARTICOES/ALPHAS OK (sem FAIL real)' if todas_ok else 'HOUVE DIVERGENCIAS REAIS -- ver acima'}")


if __name__ == "__main__":
    main()
