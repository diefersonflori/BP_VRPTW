import sys
import time
from instancia import Instancia
from solucao import Solucao
from metodos import Metodos

inst = Instancia()
inst.leitura("instancias/R102.txt")

# Métodos
metod = Metodos()

solex = Solucao(inst.nbv, inst.nbn)
solc = Solucao(inst.nbv, inst.nbcd)

tiex = time.time()
#metod.metodo_exato(inst, solex)
tfex = time.time()
solex.exportar_json(inst, "solucao_ex.json")
solex.printar_sol_exata(inst)

tiseq = time.time()
tipo_geracao="PD"
#tipo_geracao="GUROBI"
metod.geracao_colunas(inst, solc,tipo_geracao)
tfseq = time.time()

solex.printar_sol_exata(inst)
solex.registrar_fo_gc(inst,solex.custo)

solc.exportar_json_gc(inst, "solucao_gcm.json")

print("\n tempo total exato:", tfex - tiex)
print("\n tempo total gc:", tfseq - tiseq)
print("\n tempo total diff:", ((tfex - tiex) - (tfseq - tiseq)) / (tiex - tfex))


