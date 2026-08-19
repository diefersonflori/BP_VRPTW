import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from instancia import Instancia
from metodos import Metodos

# ============================================================
# PARIDADE C++ x PYTHON (rota fixa, sem Gurobi): compara
# avaliar_rota_silva2024 (Python, oficial) x avaliar_rota_silva_cpp (novo
# wrapper diagnostico pybind, reutilizando EXATAMENTE
# SilvaPricingData::avaliar_fechamento do nucleo silva_pricing_core.h --
# mesmo core usado por PD_SILVA_CPP.cpp/BID_SILVA_CPP.cpp).
#
# NAO usa Gurobi como intermediario -- o Python ja foi validado contra o
# compacto em _teste_regressao_avaliador_vs_compacto_silva.py. Aqui
# validamos so C++ x Python oficial, com a MESMA regra deterministica de
# escolha de delta_B dos dois lados -- logo B/P/R/F devem bater tambem
# (nao e degenerescencia, e reproducao deterministica).
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

CAMPOS_NUMERICOS = ["B", "P", "R", "F", "F_menos_B", "hF", "hB", "hN", "hDP", "f1", "f2", "custo"]

KWARGS_SO_PRICING = {"k", "pi", "sigma_k", "mu_flat", "forbid_flat", "req_i", "req_j"}


def extrair_python(metod, inst, k, seq):
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


def extrair_cpp(mod, metod, inst, k, seq):
    kwargs_full = metod._montar_kwargs_silva_cpp(inst, k, pi=[0.0] * inst.nbcd, sigma_k=0.0, mu_arc={}, no_bp=None)
    kwargs_cpp = {kk: vv for kk, vv in kwargs_full.items() if kk not in KWARGS_SO_PRICING}
    kwargs_cpp["seq"] = list(seq)
    d = mod.avaliar_rota_silva_cpp(**kwargs_cpp)
    if not d["viavel"]:
        return {"viavel": False, "motivo": d["motivo"]}
    return {
        "viavel": True,
        "B": d["B"], "P": d["P"], "R": d["R"], "F": d["F"],
        "F_menos_B": d["F_menos_B"],
        "hF": d["hF"], "hB": d["hB"], "hN": d["hN"], "hDP": d["hDP"],
        "f1": d["f1"], "f2": d["f2"], "custo": d["custo"],
    }


def main():
    inst = Instancia()
    inst.leitura_petro(str(ARQ))
    metod = Metodos(inst)

    mod = metod._silva_cpp_module()
    print(f"\n[VRPTW_PD_SILVA __file__] {mod.__file__}")

    linhas = []
    divergencias = []
    todas_ok = True

    for nome_particao, rotas in PARTICOES.items():
        for alpha in ALPHAS:
            inst.alpha_fo = alpha

            for k, seq in rotas.items():
                py = extrair_python(metod, inst, k, seq)
                cp = extrair_cpp(mod, metod, inst, k, seq)

                if py["viavel"] != cp["viavel"]:
                    status = "FAIL"
                    todas_ok = False
                    divergencias.append(
                        f"[{nome_particao} k={k} alpha={alpha}] DIVERGENCIA DE VIABILIDADE: "
                        f"python={py['viavel']} (motivo={py.get('motivo')}) x cpp={cp['viavel']} (motivo={cp.get('motivo')})"
                    )
                    linhas.append((nome_particao, k, alpha, "viabilidade", status,
                                    f"python={py['viavel']}", f"cpp={cp['viavel']}", "-"))
                    continue

                if not py["viavel"]:
                    linhas.append((nome_particao, k, alpha, "viabilidade", "PASS",
                                    f"python=False({py.get('motivo')})", f"cpp=False({cp.get('motivo')})", "-"))
                    continue

                for campo in CAMPOS_NUMERICOS:
                    vp, vc = py[campo], cp[campo]
                    diff = abs(vp - vc)
                    status = "PASS" if diff <= TOL else "FAIL"
                    if status == "FAIL":
                        todas_ok = False
                        divergencias.append(
                            f"[{nome_particao} k={k} alpha={alpha}] campo={campo}: "
                            f"python={vp!r} cpp={vc!r} diff={diff:.3e} > TOL={TOL:.1e}"
                        )
                    linhas.append((nome_particao, k, alpha, campo, status, f"{vp:.6f}", f"{vc:.6f}", f"{diff:.3e}"))

    print("\n" + "=" * 130)
    print("TABELA DETALHADA (particao, k, alpha, campo, status, python, cpp, diff)")
    print("=" * 130)
    for l in linhas:
        print(f"{l[0]:38s} k={l[1]} alpha={l[2]:<4} campo={l[3]:<12} {l[4]:<4} "
              f"python={l[5]:<20} cpp={l[6]:<20} diff={l[7]}")

    n_pass = sum(1 for l in linhas if l[4] == "PASS")
    n_fail = sum(1 for l in linhas if l[4] == "FAIL")
    print(f"\nContagem: PASS={n_pass} FAIL={n_fail} (total linhas={len(linhas)})")

    print("\n" + "=" * 130)
    if divergencias:
        print(f"[DIVERGENCIAS] ({len(divergencias)})")
        for d in divergencias:
            print(f"  - {d}")
    else:
        print(f"[NENHUMA DIVERGENCIA] C++ e Python bateram em todos os campos, tolerancia {TOL:.1e}")
    print("=" * 130)

    print(f"\n[RESULTADO FINAL PARIDADE C++ x PYTHON] {'TODAS AS COMBINACOES OK' if todas_ok else 'HOUVE DIVERGENCIAS -- ver acima'}")


if __name__ == "__main__":
    main()
