import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import random
import shutil
from pathlib import Path

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

import main as main_mod

# ============================================================
# Smoke test do PlotJS Silva -- NAO roda B&P completo (nada de 300s).
# So: carrega a instancia, gera a construtiva (mesmo caminho de rodar_caso),
# registra cronograma Silva e chama exportar_plotjs_seguro. Confere os 6
# arquivos e que petroConstr.js tem "window.DADOS = {" (nao null).
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"
PASTA_SAIDA = Path(r"C:\Users\PolyanaSilva\Documents\BP_VRPTW\PlotJS\_smoke_test_silva")

if PASTA_SAIDA.exists():
    shutil.rmtree(PASTA_SAIDA)

inst = Instancia()
inst.leitura_petro(ARQ)
inst.nbconstrutiva = 10
modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"
print(f"modo_silva = {modo_silva}")
assert modo_silva, "instancia deveria estar em objective_mode=silva2024"

metod = Metodos(inst)
random.seed(123)

sol_pool = Solucao(inst.nbv, inst.nbcd)
sol_pool.FO_TARGET = -1

metod.init_pool_vazio(inst, sol_pool)
metod.gera_solucao_inicial(inst, sol_pool)
metod.adiciona_colunas_ociosas(inst, sol_pool)
metod.preparar_pool_silva2024(inst, sol_pool, diagnostico=False)

rotas_construt = {
    k: {"sequencias": [list(sol_pool.rotas[k]["sequencia_rota"][0])],
        "custos": [float(sol_pool.rotas[k]["custo"][0])]}
    for k in sol_pool.rotas
    if sol_pool.rotas[k]["sequencia_rota"] and not sol_pool.rotas[k]["artificial"][0]
}
print("rotas_construt:", {k: v["sequencias"] for k, v in rotas_construt.items()})

sol_pool.registrar_solucao("construtiva", rotas_construt)
main_mod.registrar_cronogramas_silva(inst, metod, sol_pool, "construtiva", rotas_construt)

print("cronogramas_plotjs['construtiva']:",
      {k: {kk: vv for kk, vv in v.items() if kk != "cronologia"} for k, v in sol_pool.cronogramas_plotjs["construtiva"].items()})

pasta = main_mod.exportar_plotjs_seguro(sol_pool, inst, PASTA_SAIDA, tempo_construtiva=1.23, etapa="smoke_construtiva")
assert pasta is not None, "exportar_plotjs_seguro retornou None -- export falhou"

main_mod.verificar_arquivos_plotjs(PASTA_SAIDA)

js_construtiva = PASTA_SAIDA / "petroConstr.js"
conteudo = js_construtiva.read_text(encoding="utf-8")
tem_dados = "window.DADOS = {" in conteudo
tem_null = "window.DADOS = null" in conteudo
print(f"\npetroConstr.js: window.DADOS = {{ presente = {tem_dados} | window.DADOS = null presente = {tem_null}")
assert tem_dados, "petroConstr.js deveria ter window.DADOS = { (construtiva registrada)"
assert not tem_null, "petroConstr.js NAO deveria estar null (construtiva registrada)"

# petroBP.js / petroEx.js devem existir mas com DADOS=null (nao registramos bp/exato aqui)
for nome in ("petroBP.js", "petroEx.js"):
    txt = (PASTA_SAIDA / nome).read_text(encoding="utf-8")
    print(f"{nome}: window.DADOS = null presente = {'window.DADOS = null' in txt}")

print("\n[SMOKE TEST] OK -- pacote PlotJS Silva gerado corretamente sem rodar B&P/exato.")
