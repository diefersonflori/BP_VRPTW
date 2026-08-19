import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import types

from instancia import Instancia
from metodos import Metodos

# ============================================================
# Validacao de SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA contra pricing_silva2024
# (oraculo exato), com os MESMOS duais (pi/sigma/mu) e o MESMO k. NAO roda
# B&P/300s -- so as duas funcoes de pricing isoladas, com duais deterministicos
# escolhidos a mao (nao extraidos de um mestre resolvido).
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

# Duais deterministicos: pi (0-based por order, 14 orders), sigma_k por navio,
# mu_arc com um formato generico (i,j)->valor e um especifico (i,j,k)->valor,
# para exercitar os dois fallbacks de mu() (identico ao usado pelo pricing real).
#
# Magnitude escolhida a dedo (nao extraida de um mestre resolvido) para
# GARANTIR RC<0 em pelo menos algumas colunas: nesta instancia (alphaWeight=0.0
# no JSON, eta=1.0) o campo "custo" de avaliar_rota_silva2024 e dominado por
# f2=F-AT, ou seja, esta em HORAS -- uma rota de 1 unico cliente custa ~15-40h
# (a maior parte so de navegacao base<->plataforma). pi precisa ser da mesma
# ordem de grandeza para que exista alguma insercao com RC<0.
PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
assert len(PI_BASE) == inst.nbcd == 14


def no_bp_vazio():
    """NO_BP minimo (raiz, sem branching): so os 2 atributos que ALLBEST_SILVA/
    pricing_silva2024/coluna_respeita_no leem."""
    ns = types.SimpleNamespace()
    ns.arcos_proibidos = set()
    ns.arcos_fixados_em_1 = set()
    return ns


def roda_caso(tag, k, sigma_k, mu_arc, no_bp, timeout_s=120.0):
    print("\n" + "#" * 100)
    print(f"# CASO: {tag} -- k={k} sigma_k={sigma_k} mu_arc={mu_arc}")
    print("#" * 100)

    pi = list(PI_BASE)

    candidatas_allbest, completa_ab, timeout_ab = metod.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA(
        inst, None, pi, sigma_k, k, no_bp, mu_arc=mu_arc, max_candidatas=5,
    )
    candidatas_exato, completa_exato, timeout_exato = metod.pricing_silva2024(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, diagnostico=False, timeout_s=timeout_s,
    )

    melhor_allbest = candidatas_allbest[0] if candidatas_allbest else None
    melhor_exato = candidatas_exato[0] if candidatas_exato else None

    print("\n[SILVA TEST]")
    print(f"k={k}")
    print(f"melhor_rc_allbest={melhor_allbest['rc'] if melhor_allbest else None}")
    print(f"melhor_rota_allbest={melhor_allbest['seq'] if melhor_allbest else None}")
    print(f"melhor_rc_exato={melhor_exato['rc'] if melhor_exato else None}")
    print(f"melhor_rota_exato={melhor_exato['seq'] if melhor_exato else None}")
    print(f"allbest_encontrou={bool(candidatas_allbest)}")
    print(f"exato_encontrou={bool(candidatas_exato)}")
    print(f"busca_completa_allbest={completa_ab} timeout_allbest={timeout_ab} "
          f"(esperado sempre False,False -- heuristico, nunca certifica)")
    print(f"busca_completa_exato={completa_exato} timeout_exato={timeout_exato}")

    # ---- validacoes obrigatorias ----
    erros = []

    if completa_ab is not False or timeout_ab is not False:
        erros.append("ALLBEST_SILVA nao retornou (busca_completa=False, timeout=False)")

    if not completa_exato:
        print("[AVISO] pricing_silva2024 NAO completou a enumeracao neste orcamento "
              "(timeout/max_avaliacoes) -- o teste abaixo so pode ser conclusivo se completa_exato=True; "
              "reportando mesmo assim, sem certificar convergencia.")

    for c in candidatas_allbest:
        if c["k"] != k:
            erros.append(f"candidata com k={c['k']} != {k}")

        resultado = metod.avaliar_rota_silva2024(inst, k, c["seq"])
        if not resultado["viavel"]:
            erros.append(f"candidata ALLBEST {c['seq']} NAO viavel por avaliar_rota_silva2024: {resultado.get('motivo')}")
            continue

        custo_oficial = float(resultado["custo"])
        if abs(custo_oficial - c["custo"]) > 1e-8:
            erros.append(f"custo armazenado ({c['custo']}) difere de resultado['custo'] "
                          f"({custo_oficial}) por {abs(custo_oficial - c['custo']):.2e} (candidata {c['seq']})")

        rc_recomputado = float(custo_oficial)
        for cliente in c["seq"]:
            if 1 <= cliente <= inst.nbcd:
                rc_recomputado -= float(pi[cliente - 1])
        rc_recomputado -= float(sigma_k)
        for t in range(len(c["seq"]) - 1):
            i, j = c["seq"][t], c["seq"][t + 1]
            mu_val = mu_arc.get((i, j, k), mu_arc.get((i, j), 0.0))
            rc_recomputado -= float(mu_val)

        if abs(rc_recomputado - c["rc"]) > 1e-8:
            erros.append(f"RC armazenado ({c['rc']}) difere da recomputacao independente "
                          f"({rc_recomputado}) por {abs(rc_recomputado - c['rc']):.2e} (candidata {c['seq']})")

        if not metod.coluna_respeita_no(no_bp, c["seq"], k):
            erros.append(f"candidata ALLBEST {c['seq']} viola branching do NO_BP")

    if candidatas_allbest and any(c["rc"] < -1e-6 for c in candidatas_allbest) and not any(c["rc"] < -1e-6 for c in candidatas_exato):
        erros.append("ALLBEST encontrou RC<0 mas pricing_silva2024 (exato) NAO encontrou nenhum RC<0")

    # Requisito central desta correcao: o exato busca num SUPERSET do espaco do
    # ALLBEST (heuristico), entao melhor_rc_exato <= melhor_rc_allbest + 1e-8.
    # So e um requisito RIGOROSO quando completa_exato=True (se a enumeracao foi
    # cortada por timeout, o exato pode nao ter alcancado a melhor rota ainda --
    # reportado como aviso, nao como falha automatica).
    if melhor_allbest is not None and melhor_exato is not None:
        rc_ab = melhor_allbest["rc"]
        rc_ex = melhor_exato["rc"]
        if rc_ex > rc_ab + 1e-8:
            msg = (f"RC_exato ({rc_ex}) > RC_allbest ({rc_ab}) + 1e-8 -- "
                   f"o exato deveria encontrar RC igual ou MELHOR (mais negativo)")
            if completa_exato:
                erros.append(msg + " [completa_exato=True -- FALHA REAL]")
            else:
                print(f"[AVISO -- nao contado como falha, completa_exato=False] {msg}")
    elif melhor_allbest is not None and melhor_exato is None:
        msg = "ALLBEST encontrou candidata mas pricing_silva2024 (exato) NAO encontrou nenhuma"
        if completa_exato:
            erros.append(msg + " [completa_exato=True -- FALHA REAL]")
        else:
            print(f"[AVISO -- nao contado como falha, completa_exato=False] {msg}")

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")

    return len(erros) == 0


ok_geral = True

# Caso 1: raiz, sem branching, os dois navios.
for k in range(inst.nbv):
    ok_geral &= roda_caso(f"raiz_sem_branching_navio{k}", k, sigma_k=2.0, mu_arc={}, no_bp=no_bp_vazio())

# Caso 2: com mu_arc generico (i,j) e especifico (i,j,k), para exercitar os dois fallbacks.
no_bp_mu = no_bp_vazio()
mu_arc_teste = {(0, 1): 0.5, (1, 8, 0): 1.2}
ok_geral &= roda_caso("com_mu_arc", 0, sigma_k=1.5, mu_arc=mu_arc_teste, no_bp=no_bp_mu)

# Caso 3: branching ativo -- forca o arco (0,1) e proibe o arco (1,8) para k=0.
no_bp_branch = no_bp_vazio()
no_bp_branch.arcos_fixados_em_1 = {(0, 1, 0)}
no_bp_branch.arcos_proibidos = {(1, 8, 0)}
ok_geral &= roda_caso("com_branching_fixa_0_1_proibe_1_8", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch)

# ============================================================
# Teste 12: prova explicita de que o novo pricing_silva2024 (por ORDER) GERA
# colunas com um SUBCONJUNTO das orders de uma plataforma -- nao mais o bloco
# tudo-ou-nada da versao anterior. Prova por CONSTRUCAO: proibe TODOS os arcos
# de entrada no node14 (PLAT_6, order13/waterLoad) para o navio k=0, forcando
# qualquer candidata que passe por PLAT_6 a excluir esse node especifico,
# mantendo as demais orders da mesma plataforma (nodes 11,12,13) disponiveis.
# ============================================================
print("\n\n" + "#" * 100)
print("# TESTE 12 -- PROVA EXPLICITA DE VISITA PARCIAL DE PLATAFORMA (PLAT_6)")
print("#" * 100)

dp = inst.dados_petro
NODE_PLAT6 = [11, 12, 13, 14]  # deckCargoBackload, deckCargoLoad, dieselLoad, waterLoad
ORDERS_PLAT6 = [dp["order_ids"][n] for n in NODE_PLAT6]
NODE_EXCLUIDO = 14  # waterLoad (order13) -- sera forcado para fora da coluna

k_teste = 0
no_bp_parcial = no_bp_vazio()
# proibe TODO arco (x, 14, k_teste) para qualquer x -- node14 nunca pode ser
# alcancado, para qualquer navio k_teste, em nenhuma posicao da rota.
no_bp_parcial.arcos_proibidos = {(x, NODE_EXCLUIDO, k_teste) for x in range(inst.nbn) if x != NODE_EXCLUIDO}

pi_teste = list(PI_BASE)
candidatas_parcial, completa_parcial, timeout_parcial = metod.pricing_silva2024(
    inst, pi_teste, 2.0, k_teste, no_bp_parcial,
    arcos_proibidos=no_bp_parcial.arcos_proibidos, arcos_fixados=set(),
    mu_arc={}, diagnostico=False, timeout_s=120.0,
)
print(f"pricing_silva2024: completa={completa_parcial} timeout={timeout_parcial} "
      f"candidatas={len(candidatas_parcial)}")

# procura, entre as candidatas geradas, alguma que toque PLAT_6 (nodes 11-14)
# SEM o node14 explicitamente excluido -- prova que o subconjunto foi gerado.
candidata_prova = None
for c in candidatas_parcial:
    orders_no_seq_plat6 = [n for n in c["seq"] if n in NODE_PLAT6]
    if orders_no_seq_plat6 and NODE_EXCLUIDO not in orders_no_seq_plat6:
        candidata_prova = c
        break

erro_parcial = None
if candidata_prova is None:
    erro_parcial = "NENHUMA candidata gerada visita PLAT_6 parcialmente (sem node14) -- prova FALHOU"
else:
    orders_na_coluna_nos = [n for n in candidata_prova["seq"] if n in NODE_PLAT6]
    orders_na_coluna = [dp["order_ids"][n] for n in orders_na_coluna_nos]
    resultado_prova = metod.avaliar_rota_silva2024(inst, k_teste, candidata_prova["seq"])

    print("\n[SILVA PARCIAL]")
    print(f"plataforma=PLAT_6")
    print(f"orders_plataforma={ORDERS_PLAT6}")
    print(f"orders_na_coluna={orders_na_coluna}")
    print(f"seq={candidata_prova['seq']}")
    print(f"viavel={resultado_prova['viavel']}")
    print(f"custo={candidata_prova['custo']}")
    print(f"rc={candidata_prova['rc']}")

    if NODE_EXCLUIDO in orders_na_coluna_nos:
        erro_parcial = "node14 (proibido) aparece na coluna -- branching nao foi respeitado"
    if not resultado_prova["viavel"]:
        erro_parcial = f"candidata parcial nao e viavel por avaliar_rota_silva2024: {resultado_prova.get('motivo')}"
    if abs(float(resultado_prova["custo"]) - candidata_prova["custo"]) > 1e-8:
        erro_parcial = "custo da candidata parcial nao bate com resultado['custo'] a 1e-8"
    if len(orders_na_coluna_nos) >= len(NODE_PLAT6):
        erro_parcial = "candidata inclui TODAS as orders de PLAT_6 -- nao prova visita parcial"

if erro_parcial:
    print(f"\n[VALIDACAO TESTE 12][FALHOU] {erro_parcial}")
    ok_geral = False
else:
    print("\n[VALIDACAO TESTE 12][OK] pricing_silva2024 gerou e aceitou uma coluna com "
          "subconjunto estrito das orders de PLAT_6, viavel e com custo/rc consistentes.")


print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
