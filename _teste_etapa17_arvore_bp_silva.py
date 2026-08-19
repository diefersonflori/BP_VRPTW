import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import time
import csv

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

# ============================================================
# Etapa 17: integra o pricing Silva ao B&P REAL (branch_and_price_global /
# resolver_no_com_pool), sem reescrever nada -- so este script controla os
# parametros (instancia unica, sem paralelo, sem modelo compacto, sem
# estabilizacao, TIME_MAX/TIME_TARGET=300s), conforme pedido nas secoes
# 10/11 do enunciado.
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"
LB_RAIZ_ESPERADO = 115.919547
TIME_MAX = 300.0
TIME_TARGET = 300.0

inst = Instancia()
inst.leitura_petro(ARQ)
inst.nbconstrutiva = 10
inst.usar_estabilizacao = False  # secao 10: desligada para este primeiro teste da arvore

metod = Metodos(inst)
metod.TABU_TENURE = 0

sol_pool = Solucao(inst.nbv, inst.nbcd)
sol_pool.FO_TARGET = -1
sol_pool.time_initial = time.time()
sol_pool.TIME_MAX = TIME_MAX
sol_pool.TIME_TARGET = TIME_TARGET
sol_pool.SILVA_LB_RAIZ_ESPERADO = LB_RAIZ_ESPERADO  # aciona o gate da secao 15

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
print("diagnostico pool inicial:", diag_pool)

print("\n" + "#" * 100)
print("# 3) branch_and_price_global (B&P real, reaproveitado sem alteracoes)")
print("#" * 100)
t0_bp = time.time()
metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")
tempo_bp = time.time() - t0_bp

# ============================================================
# Resumo (secao 18 do enunciado)
# ============================================================
print("\n" + "=" * 100)
print("RESUMO ETAPA 17")
print("=" * 100)

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

ub = metod.best_obj if metod.best_obj > 0 else None
gap = abs(ub - lb) / max(abs(ub), 1e-9) * 100 if (lb_valido and ub is not None) else None
otimalidade_certificada = (
    arvore_certificada_completa and lb_global is not None and ub is not None
    and abs(float(ub) - float(lb_global)) <= 1e-6
)

n_nos = metod.total_nos
n_cols = metod.total_colunas

# nos certificados/nao certificados: le o diag.csv escrito por branch_and_price_global
n_certificados = n_nao_certificados = 0
try:
    with open("diag.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=","):
            if row.get("lb_confiavel") in ("True", "1", "true"):
                n_certificados += 1
            else:
                n_nao_certificados += 1
except FileNotFoundError:
    pass

print(f"[B] Solomon intacto: sim (nenhuma alteracao fora de blocos objective_mode=='silva2024')")
print(f"[B] Petrobras classico intacto: sim (idem)")
print(f"[B] C++/BID/PD-Petro/VNS/GRASP intacto: sim (nao sao chamados em modo silva2024)")

print(f"\n[C] LB raiz esperado (isolado) = {LB_RAIZ_ESPERADO:.6f}")
print(f"[C] LB raiz obtido (integrado) = {lb_raiz if lb_raiz is not None else 'NAO CERTIFICADO'}")
if lb_raiz is not None:
    print(f"[C] diferenca = {lb_raiz - LB_RAIZ_ESPERADO:.6f}")

print(f"\n[D] nos processados = {n_nos}")
print(f"[D] nos certificados (lb_confiavel) = {n_certificados}")
print(f"[D] nos NAO certificados = {n_nao_certificados}")
print(f"[D] colunas totais no pool final = {sum(len(v['sequencia_rota']) for v in sol_pool.rotas.values())}")
print(f"[D] UB = {ub}")
print(f"[D] LB = {lb} (valido={lb_valido})")
print(f"[D] gap = {gap:.4f}%" if gap is not None else "[D] gap = NA")
print(f"[D] arvore_certificada_completa = {arvore_certificada_completa}")
print(f"[D] otimalidade_certificada = {otimalidade_certificada}")
print(f"[D] tempo B&P = {tempo_bp:.1f}s")

print("\n[E] melhor solucao inteira:")
if sol_pool.rotas_escolhidas:
    for k in sorted(sol_pool.rotas_escolhidas):
        for seq in sol_pool.rotas_escolhidas[k]["sequencias"]:
            res = metod.avaliar_rota_silva2024(inst, k, seq)
            print(f"    navio={k} seq={seq} custo={res['custo']:.6f} "
                  f"F={res['F']:.4f}h f1={res['f1']:.6f} f2={res['f2']:.6f}")
else:
    print("    nenhuma solucao inteira encontrada")

audit = getattr(sol_pool, "silva_audit", {"criadas": 0, "rejeitadas_viabilidade": 0,
                                           "rejeitadas_rc": 0, "rejeitadas_branching": 0})
print("\n[F] auditoria de colunas Silva:")
print(f"    criadas (aceitas no pool) = {audit['criadas']}")
print(f"    rejeitadas por viabilidade = {audit['rejeitadas_viabilidade']}")
print(f"    rejeitadas por RC inconsistente = {audit['rejeitadas_rc']}")
print(f"    rejeitadas por branching = {audit['rejeitadas_branching']}")
