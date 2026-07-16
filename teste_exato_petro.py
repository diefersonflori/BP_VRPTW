from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

inst = Instancia()
inst.leitura_petro(r"instancias/Petro_instancias/10n-1k-3c-1r_testeUSP_v33.json")
metod = Metodos(inst)
sol = Solucao(inst.nbv, inst.nbn)
metod.metodo_exato(inst, sol)
print("\n[EXATO] ObjVal:", sol.custo)
