import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

ROTA_M = [0, 2, 4, 3, 11, 12, 14, 1, 15]
ROTA_L = [0, 8, 10, 9, 7, 6, 13, 5, 15]

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

cM = metod.custo_rota_silva2024(inst, 0, ROTA_M)
cL = metod.custo_rota_silva2024(inst, 1, ROTA_L)
print(f"\ncM = custo_rota_silva2024(inst, 0, ROTA_M) = {cM}")
print(f"cL = custo_rota_silva2024(inst, 1, ROTA_L) = {cL}")
print(f"cM + cL = {cM + cL}")

sol = Solucao(inst.nbv, inst.nbn)
ok = metod.metodo_exato_petro(
    inst, sol, time_limit=60, threads=4, salvar_modelo=False, diagnostico=True,
    fixar_rotas={0: ROTA_M, 1: ROTA_L},
    considerar_conflito_plataforma=False,
)
obj = getattr(sol, "exato_petro_obj", None)
status = getattr(sol, "exato_petro_status", None)

print("\n" + "=" * 100)
print("ETAPA 2 -- VALIDACAO DE ADITIVIDADE (considerar_conflito_plataforma=False)")
print("=" * 100)
print(f"ok={ok} status={status} ObjVal_compacto={obj}")
print(f"cM+cL = {cM + cL}")
if obj is not None:
    diff = abs((cM + cL) - obj)
    print(f"diferenca abs((cM+cL) - ObjVal) = {diff}")
    print(f"CRITERIO (<=1e-4): {'PASSOU' if diff <= 1e-4 else 'FALHOU'}")
else:
    print("ObjVal indisponivel (ok=False) -- nao foi possivel comparar.")
