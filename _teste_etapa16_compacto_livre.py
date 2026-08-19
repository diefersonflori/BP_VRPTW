import sys, time
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)
sol = Solucao(inst.nbv, inst.nbn)

t0 = time.time()
ok = metod.metodo_exato_petro(
    inst, sol, time_limit=300, threads=4, salvar_modelo=False, diagnostico=True,
    fixar_rotas=None,  # ROTEAMENTO LIVRE (Etapa 16)
    considerar_conflito_plataforma=False,
)
tempo = time.time() - t0

print("\n" + "=" * 100)
print("ETAPA 16 -- COMPACTO LIVRE, considerar_conflito_plataforma=False")
print("=" * 100)
print(f"ok={ok} status={getattr(sol,'exato_petro_status',None)} "
      f"obj={getattr(sol,'exato_petro_obj',None)} tempo={tempo:.2f}s")
if ok:
    for k in sol.rotas:
        print(f"  k={k} seq={sol.rotas[k]['sequencia_rota'][0]} custo={sol.rotas[k]['custo'][0]:.4f}")
