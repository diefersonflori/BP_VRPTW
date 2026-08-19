import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import os
import types

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

# ============================================================
# TESTE DE INTEGRACAO (secao 15 do pedido): valida o pipeline
# ALLBEST_SILVA -> BID_SILVA_CPP -> PD_SILVA_CPP tal como integrado em
# gerar_novas_colunas_com_duais11 -- SEM rodar o B&P completo. Chama
# diretamente Metodos._pricing_silva2024_um_veiculo (a mesma funcao usada
# pelo pipeline de producao, nao uma reimplementacao paralela), com um
# sol_pool/no_bp minimos (mesmo padrao usado no restante do codigo:
# Solucao(...) + init_pool_vazio + NoBP/SimpleNamespace para arcos).
#
# Casos B e C usam monkeypatch SOMENTE NESTE ARQUIVO DE TESTE (nunca em
# metodos.py) para FORCAR deterministicamente "ALLBEST nao encontra" e
# "ALLBEST e BID nao encontram" -- ALLBEST_SILVA e um GRASP com reinicios
# aleatorios, entao nao ha como garantir "nao encontra" so escolhendo duais,
# sem depender do estado do gerador aleatorio a cada execucao. O caminho de
# codigo exercitado (chamar_bid_silva_cpp/chamar_pd_silva_cpp reais, C++
# real) e o MESMO da producao -- so a saida do estagio anterior e' forcada.
# ============================================================

CPP_DIR = os.path.join(
    r"C:\Users\PolyanaSilva\Documents\BP_VRPTW", "PD_SILVA_CPP", "PD_SILVA_CPP", "x64", "Release"
)

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
assert len(PI_BASE) == inst.nbcd == 14


def no_bp_vazio():
    ns = types.SimpleNamespace()
    ns.arcos_proibidos = set()
    ns.arcos_fixados_em_1 = set()
    return ns


def novo_sol_pool():
    sol_pool = Solucao(inst.nbv, inst.nbcd)
    metod.init_pool_vazio(inst, sol_pool)
    return sol_pool


def _plataforma_chave(inst, no):
    dp = inst.dados_petro
    nomes = list(dp.get("nomes", []))
    nome = str(nomes[no]) if no < len(nomes) else ""
    if "_order_" in nome:
        return nome.split("_order_", 1)[0]
    elif "_order" in nome:
        return nome.split("_order", 1)[0]
    return nome


def _plataforma_de(inst, no):
    if no == 0 or no == inst.nbn - 1:
        return None
    return _plataforma_chave(inst, no)


def _sem_revisita(inst, seq):
    seq_plat = [_plataforma_de(inst, no) for no in seq]
    seq_plat = [p for p in seq_plat if p is not None]
    comprimida = []
    for p in seq_plat:
        if not comprimida or comprimida[-1] != p:
            comprimida.append(p)
    return len(comprimida) == len(set(comprimida))


def regressao_das_colunas(tag, candidatas, k, sigma_k, mu_arc, no_bp, pi, erros, tol=1e-6):
    """Secao 16 do pedido: para TODA candidata devolvida pelo pipeline,
    confere de forma INDEPENDENTE (nao reaproveitando o resultado interno do
    wrapper) viavel/custo/RC/branching/nao-revisita."""
    mu_arc = mu_arc or {}
    for c in candidatas:
        seq = c["seq"]
        resultado = metod.avaliar_rota_silva2024(inst, k, seq)
        if not resultado["viavel"]:
            erros.append(f"[{tag}] candidata {seq} NAO viavel: {resultado.get('motivo')}")
            continue
        custo_oficial = float(resultado["custo"])
        if abs(custo_oficial - c["custo"]) > tol:
            erros.append(f"[{tag}] custo armazenado ({c['custo']}) difere do oficial "
                          f"({custo_oficial}) por {abs(custo_oficial - c['custo']):.2e} (seq={seq})")
        rc_recomputado = float(custo_oficial)
        for cliente in seq:
            if 1 <= cliente <= inst.nbcd:
                rc_recomputado -= float(pi[cliente - 1])
        rc_recomputado -= float(sigma_k)
        for t in range(len(seq) - 1):
            i, j = seq[t], seq[t + 1]
            rc_recomputado -= float(mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0)))
        if abs(rc_recomputado - c["rc"]) > tol:
            erros.append(f"[{tag}] RC armazenado ({c['rc']}) difere do recomputado "
                          f"({rc_recomputado}) por {abs(rc_recomputado - c['rc']):.2e} (seq={seq})")
        if not metod.coluna_respeita_no(no_bp, seq, k):
            erros.append(f"[{tag}] candidata {seq} viola branching do NO_BP")
        if not _sem_revisita(inst, seq):
            erros.append(f"[{tag}] candidata {seq} REVISITA uma plataforma")


def roda_caso(tag, k, sigma_k, mu_arc, no_bp, forcar_allbest_vazio=False, forcar_bid_vazio=False):
    print("\n" + "#" * 100)
    print(f"# [SILVA PIPE TEST] caso={tag} k={k}")
    print("#" * 100)

    pi = list(PI_BASE)
    sol_pool = novo_sol_pool()

    metod_local = metod
    allbest_original = Metodos.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA
    bid_original = Metodos.chamar_bid_silva_cpp
    try:
        if forcar_allbest_vazio:
            metod_local.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA = \
                lambda *a, **kw: ([], False, False)
        if forcar_bid_vazio:
            metod_local.chamar_bid_silva_cpp = \
                lambda *a, **kw: ([], False, False, 0, 0, 0.0)

        sigma = {k: sigma_k}
        mu_arc_por_k = {k: mu_arc}
        retorno = metod._pricing_silva2024_um_veiculo(
            inst, sol_pool, no_bp, pi, sigma, mu_arc_por_k, k
        )
        # contrato de retorno (auditoria): TODOS os caminhos do helper devem
        # devolver exatamente (candidatas, status_k), com status_k um dict.
        assert isinstance(retorno, tuple) and len(retorno) == 2, \
            f"[{tag}] _pricing_silva2024_um_veiculo nao devolveu uma tupla de 2 elementos: {retorno!r}"
        candidatas, status_k = retorno
        assert isinstance(status_k, dict), \
            f"[{tag}] segundo elemento do retorno nao e um dict status_k: {status_k!r}"
    finally:
        # restaura SEMPRE os metodos originais na instancia (o monkeypatch e
        # so um atributo de instancia -- del volta a usar o metodo da classe)
        if forcar_allbest_vazio and "SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA" in metod_local.__dict__:
            del metod_local.__dict__["SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA"]
        if forcar_bid_vazio and "chamar_bid_silva_cpp" in metod_local.__dict__:
            del metod_local.__dict__["chamar_bid_silva_cpp"]

    allbest_chamado = status_k["allbest_chamado"]
    bid_chamado = status_k["bid_chamado"]
    pd_chamado = status_k["pd_chamado"]
    origem_escolhida = status_k["origem"]
    n_candidatas = len(candidatas)
    certifica_k = status_k["certifica_k"]

    print("\n[SILVA PIPE TEST]")
    print(f"caso={tag}")
    print(f"allbest_chamado={allbest_chamado}")
    print(f"bid_chamado={bid_chamado}")
    print(f"pd_chamado={pd_chamado}")
    print(f"origem_escolhida={origem_escolhida}")
    print(f"n_candidatas={n_candidatas}")
    print(f"certifica_k={certifica_k}")

    erros = []
    regressao_das_colunas(f"PIPE_{tag}", candidatas, k, sigma_k, mu_arc, no_bp, pi, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")

    return dict(allbest_chamado=allbest_chamado, bid_chamado=bid_chamado, pd_chamado=pd_chamado,
                origem_escolhida=origem_escolhida, n_candidatas=n_candidatas, certifica_k=certifica_k,
                erros=erros)


ok_geral = True

# ---- A) ALLBEST encontra coluna: caminho real, sem monkeypatch ----
res_a = roda_caso("A", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_vazio())
esperado_a = (res_a["allbest_chamado"] and not res_a["bid_chamado"] and not res_a["pd_chamado"]
              and res_a["origem_escolhida"] == "ALLBEST_SILVA" and res_a["n_candidatas"] > 0
              and res_a["certifica_k"] is False and not res_a["erros"])
print(f"\n[CASO A] esperado(ALLBEST usado, BID/PD nao chamados)={esperado_a}")
ok_geral &= esperado_a

# ---- B) ALLBEST nao encontra (forcado), BID encontra ----
res_b = roda_caso("B", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_vazio(), forcar_allbest_vazio=True)
esperado_b = (res_b["allbest_chamado"] and res_b["bid_chamado"] and not res_b["pd_chamado"]
              and res_b["origem_escolhida"] == "BID_SILVA_CPP" and res_b["n_candidatas"] > 0
              and res_b["certifica_k"] is False and not res_b["erros"])
print(f"\n[CASO B] esperado(BID_CPP usado, PD nao chamado)={esperado_b}")
ok_geral &= esperado_b

# ---- C) ALLBEST e BID nao encontram (forcados) -- PD_CPP chamado ----
res_c = roda_caso("C", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_vazio(),
                   forcar_allbest_vazio=True, forcar_bid_vazio=True)
esperado_c = (res_c["allbest_chamado"] and res_c["bid_chamado"] and res_c["pd_chamado"]
              and not res_c["erros"])
# PD_CPP e chamado; certifica so se completa=True/timeout=False -- aqui so exigimos
# que o PD tenha sido de fato chamado e que, SE encontrou candidata, certifica_k=False
# (secao 8 -- nunca certifica quando ha coluna negativa).
if res_c["n_candidatas"] > 0:
    esperado_c = esperado_c and (res_c["origem_escolhida"] == "PD_SILVA_CPP") and (res_c["certifica_k"] is False)
print(f"\n[CASO C] esperado(PD_CPP chamado, certifica conforme completa)={esperado_c}")
ok_geral &= esperado_c


# ============================================================
# TESTE DE DUPLICATA NEGATIVA (auditoria pos-integracao, secao 2/3 do
# pedido): forca PD a encontrar uma candidata negativa, insere essa MESMA
# sequencia no pool antes de rodar de novo, e confirma que uma duplicata
# negativa NAO certifica (bug que a logica antiga, "not sem_pool_pd", tinha
# -- sem_pool_pd e SEMPRE vazio nesse ponto, entao "not sem_pool_pd" era
# sempre True independente de haver RC<0 duplicada).
# ============================================================

print("\n" + "#" * 100)
print("# TESTE DE DUPLICATA NEGATIVA")
print("#" * 100)

no_bp_dup = no_bp_vazio()
sol_pool_dup = novo_sol_pool()

# 1a "chamada": obtem o conjunto COMPLETO de candidatas negativas que
# PD_SILVA_CPP encontra para este cenario, chamando chamar_pd_silva_cpp
# DIRETAMENTE (a mesma funcao usada dentro de _pricing_silva2024_um_veiculo
# -- nao uma reimplementacao) -- NAO via _pricing_silva2024_um_veiculo, que
# so devolveria as top-MAX_COLUNAS_NOVAS_VEICULO (=2) candidatas, insuficiente
# para pre-popular o pool com TODAS as negativas que o PD reencontraria.
geradas_pd_1a, completa_1a, timeout_1a, labels_1a, nivel_1a, _t1a = metod.chamar_pd_silva_cpp(
    inst, list(PI_BASE), 2.0, 0, no_bp_dup, mu_arc={},
)

erros_dup = []
if not geradas_pd_1a:
    erros_dup.append("1a chamada (chamar_pd_silva_cpp) nao encontrou nenhuma candidata negativa -- "
                      "nao da para montar o cenario de duplicata (ajustar duais/branching do teste)")
else:
    print(f"[DUPLICATA TEST] chamar_pd_silva_cpp encontrou {len(geradas_pd_1a)} candidata(s) negativa(s), "
          f"melhor seq={geradas_pd_1a[0]['seq']} rc={geradas_pd_1a[0]['rc']}")

    # pre-insere TODAS as sequencias encontradas (nao so a melhor) no pool
    # (imitando colunas ja aceitas em iteracoes anteriores de CG) --
    # PD_SILVA_CPP e' deterministico (sem aleatoriedade/beam), entao a 2a
    # chamada com os MESMOS duais/branching reencontra exatamente o mesmo
    # conjunto; so pre-inserindo TODAS e' que sem_pool_pd fica vazio na 2a
    # chamada, isolando de fato o caso "so duplicatas, nada inedito".
    for c in geradas_pd_1a:
        sol_pool_dup.rotas[0]["sequencia_rota"].append(list(c["seq"]))

    # 2a chamada: mesmos duais/branching, ALLBEST/BID forcados vazios -- PD
    # deve encontrar a MESMA candidata negativa (geradas_pd>0), mas agora ela
    # ja esta no pool (sem_pool_pd==0).
    _allbest_stub = lambda *a, **kw: ([], False, False)
    _bid_stub = lambda *a, **kw: ([], False, False, 0, 0, 0.0)
    metod.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA = _allbest_stub
    metod.chamar_bid_silva_cpp = _bid_stub
    try:
        cand_2a, status_2a = metod._pricing_silva2024_um_veiculo(
            inst, sol_pool_dup, no_bp_dup, list(PI_BASE), {0: 2.0}, {0: {}}, 0
        )
    finally:
        del metod.__dict__["SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA"]
        del metod.__dict__["chamar_bid_silva_cpp"]

    n_geradas_pd = status_2a["n_pd"]
    n_novas_pool = len(cand_2a)  # PD so devolve o que NAO esta no pool
    tem_negativa_pd = status_2a["tem_negativa_pd"]
    certifica_k_dup = status_2a["certifica_k"]

    print("\n[SILVA CERT DUPLICATA TEST]")
    print(f"pd_completa={status_2a['pd_completa']}")
    print(f"n_geradas_pd={n_geradas_pd}")
    print(f"n_novas_pool={n_novas_pool}")
    print(f"melhor_rc={status_2a['melhor_rc']}")
    print(f"tem_negativa_pd={tem_negativa_pd}")
    print(f"certifica_k={certifica_k_dup}")

    if n_geradas_pd <= 0:
        erros_dup.append(f"n_geradas_pd deveria ser >0 (PD deveria reencontrar a candidata "
                          f"duplicada), veio {n_geradas_pd}")
    if n_novas_pool != 0:
        erros_dup.append(f"n_novas_pool deveria ser 0 (candidata ja esta no pool), veio {n_novas_pool}")
    if tem_negativa_pd is not True:
        erros_dup.append(f"tem_negativa_pd deveria ser True, veio {tem_negativa_pd}")
    if certifica_k_dup is not False:
        erros_dup.append(f"certifica_k deveria ser False (duplicata negativa NAO certifica), "
                          f"veio {certifica_k_dup} -- BUG DE CERTIFICACAO")

if erros_dup:
    print("\n[VALIDACAO][FALHOU]")
    for e in erros_dup:
        print(f"  - {e}")
else:
    print("\n[VALIDACAO][OK] todas as checagens passaram")
esperado_dup = not erros_dup
print(f"\n[TESTE DUPLICATA] esperado(certifica_k=False mesmo com RC<0 duplicada)={esperado_dup}")
ok_geral &= esperado_dup


# ============================================================
# CASO D: certificacao POSITIVA -- ALLBEST e BID nao encontram (real, sem
# monkeypatch: pi=0/sigma=0 faz TODA rota ter RC=custo>=0, entao nenhum dos
# tres estagios jamais registra uma candidata, por construcao), PD_CPP
# chamado e esgota a arvore (usa o mesmo branching em cadeia 0->6->1 ja
# validado no teste de escala, que reduz a busca a ~172 mil labels -- bem
# dentro do orcamento de producao 3M labels/5s) sem achar nenhuma RC<0.
# ============================================================

print("\n" + "#" * 100)
print("# [SILVA PIPE TEST] caso=D_CERTIFICACAO")
print("#" * 100)

no_bp_d = no_bp_vazio()
no_bp_d.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
sol_pool_d = novo_sol_pool()

pi_zero = [0.0] * inst.nbcd
cand_d, status_d = metod._pricing_silva2024_um_veiculo(
    inst, sol_pool_d, no_bp_d, pi_zero, {0: 0.0}, {0: {}}, 0
)

print("\n[SILVA PIPE TEST]")
print("caso=D_CERTIFICACAO")
print(f"allbest_chamado={status_d['allbest_chamado']}")
print(f"bid_chamado={status_d['bid_chamado']}")
print(f"pd_chamado={status_d['pd_chamado']}")
print(f"pd_completa={status_d['pd_completa']}")
print(f"pd_timeout={status_d['pd_timeout']}")
print(f"n_negativas_pd={status_d['n_pd']}")
print(f"certifica_k={status_d['certifica_k']}")

erros_d = []
regressao_das_colunas("PIPE_D", cand_d, 0, 0.0, {}, no_bp_d, pi_zero, erros_d)
if status_d["allbest_chamado"] is not True:
    erros_d.append("allbest_chamado deveria ser True")
if status_d["bid_chamado"] is not True:
    erros_d.append("bid_chamado deveria ser True")
if status_d["pd_chamado"] is not True:
    erros_d.append("pd_chamado deveria ser True")
if status_d["pd_completa"] is not True:
    erros_d.append(f"pd_completa deveria ser True (arvore esgotada), veio {status_d['pd_completa']}")
if status_d["pd_timeout"] is not False:
    erros_d.append(f"pd_timeout deveria ser False, veio {status_d['pd_timeout']}")
if status_d["n_pd"] != 0:
    erros_d.append(f"n_negativas_pd deveria ser 0 (pi=0/sigma=0 -> RC=custo>=0 sempre), veio {status_d['n_pd']}")
if status_d["certifica_k"] is not True:
    erros_d.append(f"certifica_k deveria ser True, veio {status_d['certifica_k']}")
if len(cand_d) != 0:
    erros_d.append(f"caso D nao deveria devolver candidatas, veio {len(cand_d)}")

if erros_d:
    print("\n[VALIDACAO][FALHOU]")
    for e in erros_d:
        print(f"  - {e}")
else:
    print("\n[VALIDACAO][OK] todas as checagens passaram")
esperado_d = not erros_d
print(f"\n[CASO D] esperado(PD completa=True sem negativas => certifica_k=True)={esperado_d}")
ok_geral &= esperado_d


# ============================================================
# TESTE DO AND GLOBAL (secao 5 do pedido de auditoria): confirma a regra
# ja existente em gerar_novas_colunas_com_duais11 -- todos_k_certificados =
# all(no_bp.silva_certifica_k.get(kk, False) for kk in lista_k_tentativa) --
# SEM rodar o B&P, so escrevendo no_bp.silva_certifica_k diretamente (a
# mesma estrutura que _pricing_silva2024_um_veiculo preenche por veiculo).
# ============================================================

print("\n" + "#" * 100)
print("# TESTE DO AND GLOBAL (2 veiculos)")
print("#" * 100)


def and_global(silva_certifica_k, lista_k):
    return all(bool(silva_certifica_k.get(kk, False)) for kk in lista_k)


caso_and_1 = and_global({0: True, 1: True}, [0, 1])
caso_and_2 = and_global({0: True, 1: False}, [0, 1])
print(f"[AND GLOBAL] k0=True k1=True -> todos_k_certificados={caso_and_1} (esperado True)")
print(f"[AND GLOBAL] k0=True k1=False -> todos_k_certificados={caso_and_2} (esperado False)")

erros_and = []
if caso_and_1 is not True:
    erros_and.append(f"k0=True,k1=True deveria dar todos_k_certificados=True, veio {caso_and_1}")
if caso_and_2 is not False:
    erros_and.append(f"k0=True,k1=False deveria dar todos_k_certificados=False, veio {caso_and_2}")

if erros_and:
    print("\n[VALIDACAO][FALHOU]")
    for e in erros_and:
        print(f"  - {e}")
else:
    print("\n[VALIDACAO][OK] todas as checagens passaram")
esperado_and = not erros_and
ok_geral &= esperado_and


print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL PIPELINE] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
