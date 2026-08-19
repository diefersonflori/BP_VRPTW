import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

# ============================================================
# SMOKE TEST: metodo_exato_petro LIVRE (sem fixar_rotas), time_limit=20s,
# considerar_conflito_plataforma=False. Objetivo: confirmar o fluxo completo
# -- Gurobi encontra incumbente -> extrai rotas -> validacao operacional ->
# solucao aceita -> FO reconstruida fecha com ObjVal -> relatorio Silva usa
# os nomes corretos (f1/f2, nao diesel/CO2). NAO fixa rotas, NAO roda B&P.
# ============================================================

ARQ = BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(str(ARQ))
metod = Metodos(inst)

sol = Solucao(inst.nbv, inst.nbn)
ok = metod.metodo_exato_petro(
    inst, sol, time_limit=20, threads=4, salvar_modelo=False, diagnostico=True,
    considerar_conflito_plataforma=False,
)

status = getattr(sol, "exato_petro_status", None)
tem_solucao = getattr(sol, "exato_petro_tem_solucao", None)
otimo = getattr(sol, "exato_petro_otimo", None)
objval = getattr(sol, "exato_petro_obj", None)
bound = getattr(sol, "exato_petro_bound", None)
gap = getattr(sol, "exato_petro_gap", None)
consistente = getattr(sol, "exato_petro_consistente", None)

f1_total = getattr(sol, "exato_petro_consumo_total", None)
f2_total = getattr(sol, "exato_petro_tempo_total", None)
alpha_f1 = getattr(sol, "exato_petro_componente_ambiental", None)
temp_f2 = getattr(sol, "exato_petro_componente_temporal", None)
alpha_exato = getattr(sol, "exato_petro_alpha", None)
eta_exato = getattr(sol, "exato_petro_eta", None)

fo_reconstruida = None
diff_fo = None
if alpha_f1 is not None and temp_f2 is not None:
    fo_reconstruida = alpha_f1 + temp_f2
    if objval is not None:
        diff_fo = abs(fo_reconstruida - objval)

rotas = {}
if hasattr(sol, "exato_petro_rotas_brutas"):
    for k, dados in sol.exato_petro_rotas_brutas.items():
        seq_rota = dados.get("sequencia_rota", [])
        rotas[k] = seq_rota[0] if seq_rota else None

print("\n\n" + "=" * 100)
print("RESULTADO COMPACTO LIVRE (20s, sem fixar_rotas, considerar_conflito_plataforma=False)")
print("=" * 100)
print(f"ok = {ok}")
print(f"status = {status}")
print(f"tem_solucao = {tem_solucao}")
print(f"otimo = {otimo}")
print(f"ObjVal = {objval}")
print(f"BestBound = {bound}")
print(f"gap = {gap}")
print(f"rotas = {rotas}")
print(f"alpha = {alpha_exato}")
print(f"eta = {eta_exato}")
print(f"f1_total = {f1_total}")
print(f"f2_total = {f2_total}")
print(f"alpha*f1 = {alpha_f1}")
print(f"(1-alpha)*eta*f2 = {temp_f2}")
print(f"FO reconstruida (alpha*f1 + (1-alpha)*eta*f2) = {fo_reconstruida}")
print(f"diferenca FO reconstruida - ObjVal = {diff_fo}")
print(f"exato_petro_consistente = {consistente}")

TOL = 1e-6
print("\n" + "=" * 100)
falhas = []
if not ok:
    falhas.append("metodo_exato_petro retornou ok=False (nenhuma solucao)")
if consistente is not True:
    falhas.append(f"exato_petro_consistente != True (veio {consistente}) -- validacao operacional rejeitou algo")
if diff_fo is not None and diff_fo > TOL:
    falhas.append(f"diferenca FO reconstruida x ObjVal ({diff_fo:.3e}) > tolerancia {TOL:.1e}")

if falhas:
    print("[SMOKE TEST] FAIL")
    for f in falhas:
        print(f"  - {f}")
else:
    print("[SMOKE TEST] PASS -- solucao operacionalmente aceita, FO reconstruida fecha com ObjVal")
print("=" * 100)
