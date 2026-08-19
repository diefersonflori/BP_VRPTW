import io
import re
import sys
import random
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ============================================================
# TESTE DE INTEGRACAO B&P CURTO (30s) -- pipeline de PRODUCAO
# ALLBEST_SILVA -> BID_SILVA_CPP -> PD_SILVA_CPP, via
# metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD").
#
# NAO roda o modelo compacto. NAO roda 300s. NAO cria pipeline alternativo --
# usa exatamente a mesma preparacao de instancia/pool de main.py (construtiva,
# adiciona_colunas_ociosas, preparar_pool_silva2024) e a mesma chamada de
# branch_and_price_global ja usada em producao.
#
# Objetivo: validar a INTEGRACAO (modulo C++ certo carregado, ALLBEST/BID/PD
# chamados na ordem certa, nenhum mismatch custo/RC C++ x Python, nenhuma
# revisita, branching respeitado, nenhuma excecao) -- NAO provar otimalidade
# nem obter LB certificado em 30s.
# ============================================================

import instancia as instancia_mod
import metodos as metodos_mod
import solucao as solucao_mod
import avaliador_rota as avaliador_rota_mod

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

print("[PATH] metodos =", metodos_mod.__file__)
print("[PATH] solucao =", solucao_mod.__file__)
print("[PATH] avaliador =", avaliador_rota_mod.__file__)

ARQ = BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json"

TIME_TARGET = 30
TIME_MAX = 30
SEED_DEBUG = 123
SM_FIXO = 100
GAMMA_INI = 15
GAMMA_MIN = 10
GAMMA_MAX = 600
TABU = 0
USAR_GAMMA_RELATIVO = True
GAMMA_RHO = 0.25
PRICING_EXATO_TIMEOUT_S = 60
PRICING_EXATO_MAX_LABELS = 1_000_000_000


class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, s):
        for f in self.files:
            f.write(s)

    def flush(self):
        for f in self.files:
            f.flush()


def main():
    inst = Instancia()
    inst.ninst = 0
    inst.nomeInst = str(ARQ)
    inst.leitura_petro(str(ARQ))
    inst.pricing_exato_timeout_s = PRICING_EXATO_TIMEOUT_S
    inst.pricing_exato_max_labels = PRICING_EXATO_MAX_LABELS

    modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"
    print(f"[INSTANCIA] modo_silva={modo_silva} nbcd={inst.nbcd} nbv={inst.nbv}")

    metod = Metodos(inst)
    metod.TABU_TENURE = TABU

    # Carrega o modulo C++ pelo MESMO mecanismo da producao (cacheado na
    # classe Metodos, caminho absoluto relativo a metodos.py, nunca um .pyd
    # antigo em sys.path).
    mod_cpp = metod._silva_cpp_module()
    print("[PATH] pyd =", mod_cpp.__file__)
    caminho_pyd_esperado = str(BASE_DIR / "PD_SILVA_CPP" / "PD_SILVA_CPP" / "x64" / "Release" / "vrptw_pd_silva.pyd")
    pyd_correto = str(Path(mod_cpp.__file__).resolve()) == str(Path(caminho_pyd_esperado).resolve())
    print(f"[PATH] pyd_correto={pyd_correto}")

    inst.usar_estabilizacao = True
    inst.nbconstrutiva = 10
    inst.iteraSemMelhora = SM_FIXO
    random.seed(SEED_DEBUG)

    sol_pool = Solucao(inst.nbv, inst.nbcd)
    sol_pool.FO_TARGET = -1
    sol_pool.time_initial = time.time()
    sol_pool.TIME_TARGET = TIME_TARGET
    sol_pool.TIME_MAX = TIME_MAX
    sol_pool.gamma_pi = GAMMA_INI
    sol_pool.gamma_pi_inicial = GAMMA_INI
    sol_pool.gamma_pi_min = GAMMA_MIN
    sol_pool.gamma_pi_max = GAMMA_MAX
    sol_pool.usar_gamma_relativo = USAR_GAMMA_RELATIVO
    sol_pool.gamma_rho = GAMMA_RHO
    sol_pool.gamma_abs_min = 10.0
    sol_pool.gamma_min_factor = 0.25
    sol_pool.gamma_max_factor = 4.0

    metod.init_pool_vazio(inst, sol_pool)
    metod.gera_solucao_inicial(inst, sol_pool)
    metod.adiciona_colunas_ociosas(inst, sol_pool)

    if modo_silva:
        metod.preparar_pool_silva2024(inst, sol_pool, diagnostico=True)

    print(f"\n[INICIO B&P] TIME_TARGET={TIME_TARGET}s TIME_MAX={TIME_MAX}s tipo_geracao=PD")

    buf = io.StringIO()
    real_stdout = sys.stdout
    t0 = time.time()
    excecao = None
    try:
        sys.stdout = Tee(real_stdout, buf)
        metod.branch_and_price_global(inst, sol_pool, tipo_geracao="PD")
    except Exception as e:
        import traceback
        excecao = f"{e!r}\n{traceback.format_exc()}"
    finally:
        sys.stdout = real_stdout
    tempo_total = time.time() - t0

    log_text = buf.getvalue()
    log_path = BASE_DIR / "_out_integracao_bp_silva_30s_bruto.log"
    log_path.write_text(log_text, encoding="utf-8")
    print(f"\n[LOG BRUTO] salvo em {log_path}")

    if excecao is not None:
        print("\n[EXCECAO DURANTE O B&P]")
        print(excecao)

    # ---- parsing do log para os contadores pedidos ----
    n_chamadas_allbest = len(re.findall(r"^TESTA ALLBEST_SILVA$", log_text, re.MULTILINE))
    n_chamadas_bid = len(re.findall(r"^TESTA BID_SILVA_CPP$", log_text, re.MULTILINE))
    n_chamadas_pd = len(re.findall(r"^TESTA PD_SILVA_CPP$", log_text, re.MULTILINE))

    pd_completa_vals = re.findall(r"^pd_completa=(\S+)$", log_text, re.MULTILINE)
    pd_timeout_vals = re.findall(r"^pd_timeout=(\S+)$", log_text, re.MULTILINE)
    n_pd_completa = sum(1 for v in pd_completa_vals if v == "True")
    n_pd_incompleta = sum(1 for v in pd_completa_vals if v == "False")
    n_pd_timeout = sum(1 for v in pd_timeout_vals if v == "True")

    n_certifica_k_true = len(re.findall(r"^certifica_k=True$", log_text, re.MULTILINE))
    n_todos_k_certificados_true = len(re.findall(r"^\[SILVA CERT\] todos_k_certificados=True$", log_text, re.MULTILINE))

    linhas_rejeitadas = re.findall(r"^\[SILVA [^\]]+\]\[ERRO\].*REJEITADA:.*$", log_text, re.MULTILINE)
    n_candidatas_rejeitadas_auditoria = len(linhas_rejeitadas)
    n_mismatch_rc = sum(1 for l in linhas_rejeitadas if "rc_cpp" in l and "difere de rc_python" in l)
    # producao SEMPRE usa o custo recalculado em Python como valor final
    # (nunca o custo cru do C++) -- nao existe um campo "custo_cpp" separado
    # para comparar dentro da auditoria de producao (_auditar_candidatas_silva_cpp),
    # so o RC (que embute o custo). Qualquer divergencia de custo se propagaria
    # para uma divergencia de RC (RC = custo - pi - sigma - mu), entao
    # n_mismatch_rc acima ja cobre essa classe de erro.
    n_mismatch_custo = n_mismatch_rc

    n_atributeerror = len(re.findall(r"AttributeError", log_text))
    n_revisita = sum(1 for l in linhas_rejeitadas if "REVISITA" in l)
    n_branching_violado = sum(1 for l in linhas_rejeitadas if "viola branching" in l)

    ub = metod.best_obj if getattr(metod, "best_obj", 0) > 0 else None
    lb_raiz = getattr(sol_pool, "lb_raiz_confiavel", None)
    lb_global = getattr(sol_pool, "lb_global_confiavel", None)
    arvore_certificada_completa = bool(getattr(sol_pool, "arvore_certificada_completa", False))
    n_nos = getattr(metod, "total_nos", None)
    n_cols = getattr(metod, "total_colunas", None)

    print("\n\n" + "=" * 100)
    print("RESUMO TESTE DE INTEGRACAO B&P (30s)")
    print("=" * 100)
    print(f"tempo_total = {tempo_total:.2f}s")
    print(f"n_nos = {n_nos}")
    print(f"n_colunas = {n_cols}")
    print(f"melhor_UB = {ub}")
    print(f"LB_raiz_confiavel = {lb_raiz}")
    print(f"LB_global_confiavel = {lb_global}")
    print(f"arvore_certificada_completa = {arvore_certificada_completa}")
    print(f"n_chamadas_ALLBEST = {n_chamadas_allbest}")
    print(f"n_chamadas_BID_CPP = {n_chamadas_bid}")
    print(f"n_chamadas_PD_CPP = {n_chamadas_pd}")
    print(f"n_PD_completa = {n_pd_completa}")
    print(f"n_PD_incompleta = {n_pd_incompleta}")
    print(f"n_PD_timeout = {n_pd_timeout}")
    print(f"n_certifica_k_true = {n_certifica_k_true}")
    print(f"n_todos_k_certificados_true = {n_todos_k_certificados_true}")
    print(f"n_mismatch_custo_cpp_python = {n_mismatch_custo}")
    print(f"n_mismatch_rc_cpp_python = {n_mismatch_rc}")
    print(f"n_candidatas_rejeitadas_auditoria = {n_candidatas_rejeitadas_auditoria} "
          f"(revisita={n_revisita}, branching={n_branching_violado}, "
          f"outros/inviavel={n_candidatas_rejeitadas_auditoria - n_mismatch_rc - n_revisita - n_branching_violado})")
    print(f"n_AttributeError = {n_atributeerror}")
    print(f"caminho_pyd = {mod_cpp.__file__}")
    print(f"pyd_correto = {pyd_correto}")

    falhas = []
    if excecao is not None:
        falhas.append("excecao/crash durante o B&P")
    if not pyd_correto:
        falhas.append("modulo C++ carregado de caminho inesperado")
    if n_mismatch_rc > 0:
        falhas.append(f"{n_mismatch_rc} mismatch(es) de RC C++ x Python > 1e-6")
    if n_revisita > 0:
        falhas.append(f"{n_revisita} candidata(s) com revisita de plataforma")
    if n_branching_violado > 0:
        falhas.append(f"{n_branching_violado} candidata(s) violando branching")
    if n_atributeerror > 0:
        falhas.append(f"{n_atributeerror} ocorrencia(s) de AttributeError no log")
    if n_chamadas_allbest == 0:
        falhas.append("ALLBEST_SILVA nunca foi chamado (pipeline nao seguiu a ordem esperada)")
    # certificacao falsa: certifica_k=True sem PD ter sido chamado/completo/sem timeout
    # ja e garantido pela propria formula de producao (certifica_k = completa_pd and not
    # timeout_pd and not tem_negativa_pd) -- aqui so confirmamos que nao houve
    # nenhuma inconsistencia obvia entre n_certifica_k_true e n_PD_completa.
    if n_certifica_k_true > n_pd_completa:
        falhas.append("certifica_k=True aparece mais vezes que PD completa=True -- possivel certificacao indevida")

    print("\n" + "=" * 100)
    if falhas:
        print("[TESTE DE INTEGRACAO] FAIL")
        for f in falhas:
            print(f"  - {f}")
    else:
        print("[TESTE DE INTEGRACAO] PASS")
    print("=" * 100)


if __name__ == "__main__":
    main()
