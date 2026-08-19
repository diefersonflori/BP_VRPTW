import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

ROTA_M_TAB3 = [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15]
ROTA_L_TAB3 = [0, 10, 15]
ROTA_M_CONSTR = [0, 2, 4, 3, 11, 12, 14, 1, 15]
ROTA_L_CONSTR = [0, 8, 10, 9, 7, 6, 13, 5, 15]


def carrega():
    inst = Instancia()
    inst.leitura_petro(ARQ)
    metod = Metodos(inst)
    return inst, metod


def roda_compacto(metod, inst, rotas_fixas, tag):
    sol = Solucao(inst.nbv, inst.nbn)
    print(f"\n{'='*100}\nCOMPACTO (fixar_rotas) -- {tag}: {rotas_fixas}\n{'='*100}")
    ok = metod.metodo_exato_petro(inst, sol, time_limit=60, threads=4, salvar_modelo=False,
                                   diagnostico=True, fixar_rotas=rotas_fixas)
    status = getattr(sol, "exato_petro_status", None)
    print(f"\n>>> RESULTADO COMPACTO [{tag}]: ok={ok} status={status} obj={getattr(sol,'exato_petro_obj',None)}")
    return ok, status, sol


def roda_novo(metod, inst, k, seq, tag):
    print(f"\n{'-'*100}\nNOVA FUNCAO avaliar_rota_silva2024 -- {tag} (k={k}, seq={seq})\n{'-'*100}")
    r = metod.avaliar_rota_silva2024(inst, k, seq, diagnostico=True)
    print(f">>> RESULTADO NOVO [{tag}]: viavel={r['viavel']} motivo={r.get('motivo')} custo={r.get('custo')}")
    return r


inst, metod = carrega()

print("\n\n" + "#" * 100)
print("# TESTE 1: rotas da Tabela 3 (M + L simultaneamente, para manter atende_uma_vez viavel)")
print("#" * 100)
ok1, status1, sol1 = roda_compacto(metod, inst, {0: ROTA_M_TAB3, 1: ROTA_L_TAB3}, "TAB3 M+L")
r_L_tab3 = roda_novo(metod, inst, 1, ROTA_L_TAB3, "TAB3 L")
r_M_tab3 = roda_novo(metod, inst, 0, ROTA_M_TAB3, "TAB3 M")

print("\n\n" + "#" * 100)
print("# TESTE 2: rotas da construtiva (M + L simultaneamente)")
print("#" * 100)
ok2, status2, sol2 = roda_compacto(metod, inst, {0: ROTA_M_CONSTR, 1: ROTA_L_CONSTR}, "CONSTR M+L")
r_M_constr = roda_novo(metod, inst, 0, ROTA_M_CONSTR, "CONSTR M")
r_L_constr = roda_novo(metod, inst, 1, ROTA_L_CONSTR, "CONSTR L")

print("\n\n" + "#" * 100)
print("# RESUMO")
print("#" * 100)
print(f"TESTE 1 (TAB3): compacto ok={ok1} status={status1}")
print(f"  novo L: viavel={r_L_tab3['viavel']} motivo={r_L_tab3.get('motivo')} custo={r_L_tab3.get('custo')}")
print(f"  novo M: viavel={r_M_tab3['viavel']} motivo={r_M_tab3.get('motivo')} custo={r_M_tab3.get('custo')}")
print(f"TESTE 2 (CONSTR): compacto ok={ok2} status={status2}")
print(f"  novo M: viavel={r_M_constr['viavel']} motivo={r_M_constr.get('motivo')} custo={r_M_constr.get('custo')}")
print(f"  novo L: viavel={r_L_constr['viavel']} motivo={r_L_constr.get('motivo')} custo={r_L_constr.get('custo')}")
if ok2:
    print(f"  compacto obj total = {sol2.exato_petro_obj}")
    print(f"  soma novo (M+L) = {r_M_constr.get('custo', 0) + r_L_constr.get('custo', 0)}")
