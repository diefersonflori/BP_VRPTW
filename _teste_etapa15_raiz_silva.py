import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import gurobipy as gp
from gurobipy import GRB

from instancia import Instancia
from metodos import Metodos, NoBP
from solucao import Solucao

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
inst.nbconstrutiva = 10

metod = Metodos(inst)

sol_pool = Solucao(inst.nbv, inst.nbcd)

print("\n" + "#" * 100)
print("# 1) CONSTRUTIVA (inalterada)")
print("#" * 100)
metod.init_pool_vazio(inst, sol_pool)
metod.gera_solucao_inicial(inst, sol_pool)
metod.adiciona_colunas_ociosas(inst, sol_pool)

print("\n" + "#" * 100)
print("# 2) preparar_pool_silva2024")
print("#" * 100)
diag_pool = metod.preparar_pool_silva2024(inst, sol_pool, diagnostico=True)
print("diagnostico:", diag_pool)

K = list(range(inst.nbv))
nbcd = inst.nbcd
no_raiz = NoBP(id_no=0)  # sem branching (Etapa 13)


def rotas_binarias_pool():
    """Espelha exatamente o pool atual (sol_pool.rotas) como lista de colunas
    (k, seq, binx, custo) -- inclui as reais (construtiva ja re-precificada
    pela Etapa 3/4) e as ociosas."""
    cols = []
    for k in K:
        for p in range(len(sol_pool.rotas[k]["sequencia_rota"])):
            seq = sol_pool.rotas[k]["sequencia_rota"][p]
            binx = sol_pool.rotas[k]["rotas_binaria"][p]
            custo = sol_pool.rotas[k]["custo"][p]
            cols.append((k, seq, list(binx), float(custo)))
    return cols


def resolve_rmp_e_extrai_duais(cols):
    """RMP EXATAMENTE como descrito pela investigacao do mestre atual:
    min sum(custo*lambda) s.a. cobertura de cliente (==1, uma por cliente)
    e uso de navio (==1, uma por navio). Sem slack (o pool sempre tem as
    colunas ociosas + as reais da construtiva, que juntas ja cobrem tudo)."""
    m = gp.Model("RMP_silva_raiz")
    m.Params.OutputFlag = 0
    lam = {}
    for idx, (k, seq, binx, custo) in enumerate(cols):
        lam[idx] = m.addVar(lb=0.0, obj=custo, vtype=GRB.CONTINUOUS, name=f"lambda_{idx}")

    cobertura = {}
    for i in range(1, nbcd + 1):
        cobertura[i] = m.addConstr(
            gp.quicksum(lam[idx] for idx, (k, seq, binx, custo) in enumerate(cols) if binx[i - 1] == 1) == 1.0,
            name=f"visita_{i}",
        )
    uso_navio = {}
    for k in K:
        uso_navio[k] = m.addConstr(
            gp.quicksum(lam[idx] for idx, (kk, seq, binx, custo) in enumerate(cols) if kk == k) == 1.0,
            name=f"uma_rota_veic_{k}",
        )

    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"RMP nao OPTIMAL: status={m.Status}")

    pi = [float(cobertura[i].Pi) for i in range(1, nbcd + 1)]
    sigma = {k: float(uso_navio[k].Pi) for k in K}
    lambdas = {idx: lam[idx].X for idx in lam}
    return m.ObjVal, pi, sigma, lambdas


print("\n" + "#" * 100)
print("# 3-7) CG DA RAIZ (loop manual, sem branching, sem estabilizacao)")
print("#" * 100)

cols = rotas_binarias_pool()
EPS_RC = 1e-6
iteracao = 0
historico = []

while True:
    iteracao += 1
    obj_rmp, pi, sigma, lambdas = resolve_rmp_e_extrai_duais(cols)

    melhor_rc = {0: None, 1: None}
    melhor_col = {0: None, 1: None}
    novas_nesta_iter = []

    for k in K:
        candidatas = metod.pricing_silva2024(
            inst, pi, sigma[k], k, no_raiz,
            arcos_proibidos=set(), arcos_fixados=set(), mu_arc={},
            diagnostico=False,
        )
        if candidatas:
            melhor = candidatas[0]
            melhor_rc[k] = melhor["rc"]
            melhor_col[k] = melhor["seq"]
            # Etapa 14: auditoria independente ANTES de entrar no pool.
            res_check = metod.avaliar_rota_silva2024(inst, k, melhor["seq"])
            if not res_check["viavel"]:
                print(f"[ETAPA14][ERRO] k={k} seq={melhor['seq']} pricing disse viavel mas "
                      f"avaliar_rota_silva2024 diz inviavel ({res_check.get('motivo')}) -- NAO adicionada.")
                continue
            dual_clientes = sum(float(pi[i - 1]) for i in melhor["seq"] if 1 <= i <= nbcd)
            rc_check = res_check["custo"] - dual_clientes - float(sigma[k])
            if abs(rc_check - melhor["rc"]) > 1e-6:
                print(f"[ETAPA14][ERRO] k={k} seq={melhor['seq']} RC_pricing={melhor['rc']:.6f} "
                      f"RC_check={rc_check:.6f} diferem -- PARANDO a CG (nao adiciona, nao continua).")
                historico.append((iteracao, obj_rmp, melhor_rc[0], melhor_rc[1], melhor_col[0], melhor_col[1], "ERRO_ETAPA14"))
                raise SystemExit(1)
            if melhor["rc"] < -EPS_RC:
                novas_nesta_iter.append((k, melhor["seq"], melhor["binx"], melhor["custo"]))

    print(f"[ITER {iteracao}] RMP={obj_rmp:.6f} | melhor_RC_M={melhor_rc[0]} | melhor_RC_L={melhor_rc[1]} | "
          f"coluna_M={melhor_col[0]} | coluna_L={melhor_col[1]} | novas={len(novas_nesta_iter)}")
    historico.append((iteracao, obj_rmp, melhor_rc[0], melhor_rc[1], melhor_col[0], melhor_col[1], len(novas_nesta_iter)))

    if not novas_nesta_iter:
        print(f"\n>>> CG DA RAIZ CONVERGIU na iteracao {iteracao}: nenhuma coluna com RC < -{EPS_RC} para nenhum navio.")
        break

    for k, seq, binx, custo in novas_nesta_iter:
        if any(c[0] == k and c[1] == seq for c in cols):
            continue  # ja no pool
        cols.append((k, seq, binx, custo))
        sol_pool.rotas[k]["sequencia_rota"].append(seq)
        sol_pool.rotas[k]["rotas_binaria"].append(binx)
        sol_pool.rotas[k]["custo"].append(custo)
        sol_pool.rotas[k]["vezes_usada_geral"].append(0)
        sol_pool.rotas[k]["vezes_usada_otimo"].append(0)
        sol_pool.rotas[k]["lbd_iteracao"].append([])
        sol_pool.rotas[k]["artificial"].append(False)

print("\n" + "=" * 100)
print("TABELA DE ITERACOES")
print("=" * 100)
print(f"{'iter':>4} {'RMP':>12} {'melhor_RC_M':>14} {'melhor_RC_L':>14}  coluna_M / coluna_L")
for it, obj_rmp, rcM, rcL, colM, colL, novas in historico:
    print(f"{it:>4} {obj_rmp:>12.4f} {str(rcM):>14} {str(rcL):>14}  {colM} / {colL}")

obj_final, pi_final, sigma_final, lambdas_final = resolve_rmp_e_extrai_duais(cols)
print("\n" + "=" * 100)
print("SOLUCAO FINAL DA RAIZ")
print("=" * 100)
print(f"LB_CG (RMP final) = {obj_final:.6f}")
for idx, (k, seq, binx, custo) in enumerate(cols):
    if lambdas_final[idx] > 1e-6:
        print(f"  k={k} lambda={lambdas_final[idx]:.6f} custo={custo:.4f} seq={seq}")
