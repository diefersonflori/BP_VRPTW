import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import types

from instancia import Instancia
from metodos import Metodos

# ============================================================
# TESTE 3 NIVEIS -- ALLBEST_SILVA x BID_SILVA x pricing_silva2024 (oraculo
# exato), com os MESMOS duais (pi/sigma/mu) e o MESMO k, na instancia 14n.
# NAO roda B&P/300s -- so as tres funcoes de pricing isoladas, com duais
# deterministicos escolhidos a mao (mesmos de _teste_allbest_silva.py, ja
# validado -- NAO alterado por este arquivo).
#
# ALLBEST_SILVA e BID_SILVA sao heuristicos (busca_completa=False sempre) --
# NAO se exige que encontrem a melhor coluna, so que toda candidata que
# produzem seja auditavelmente correta (viavel/custo/rc/branching).
# pricing_silva2024 e o oraculo exato/fallback (so ele pode certificar
# ausencia de coluna negativa, quando completa=True e sem timeout).
# ============================================================

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


def audita_candidatas(tag_origem, candidatas, k, sigma_k, mu_arc, no_bp, pi, erros):
    """Mesma auditoria aplicada as candidatas ALLBEST em _teste_allbest_silva.py,
    reaproveitada aqui para BID_SILVA (e tambem aplicada ao PD como checagem
    cruzada): viavel por avaliar_rota_silva2024, custo/rc batendo a 1e-8,
    branching respeitado."""
    for c in candidatas:
        if c["k"] != k:
            erros.append(f"[{tag_origem}] candidata com k={c['k']} != {k}")

        resultado = metod.avaliar_rota_silva2024(inst, k, c["seq"])
        if not resultado["viavel"]:
            erros.append(f"[{tag_origem}] candidata {c['seq']} NAO viavel por "
                          f"avaliar_rota_silva2024: {resultado.get('motivo')}")
            continue

        custo_oficial = float(resultado["custo"])
        if abs(custo_oficial - c["custo"]) > 1e-8:
            erros.append(f"[{tag_origem}] custo armazenado ({c['custo']}) difere de "
                          f"resultado['custo'] ({custo_oficial}) por "
                          f"{abs(custo_oficial - c['custo']):.2e} (candidata {c['seq']})")

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
            erros.append(f"[{tag_origem}] RC armazenado ({c['rc']}) difere da "
                          f"recomputacao independente ({rc_recomputado}) por "
                          f"{abs(rc_recomputado - c['rc']):.2e} (candidata {c['seq']})")

        if not metod.coluna_respeita_no(no_bp, c["seq"], k):
            erros.append(f"[{tag_origem}] candidata {c['seq']} viola branching do NO_BP")


def _plataforma_de(no):
    """MESMA regra de agrupamento por plataforma de avaliar_rota_silva2024/
    pricing_silva2024/SUB_PROG_BID_SILVA (nome ate '_order_'/'_order'). None
    para deposito (inicio/fim)."""
    if no == 0 or no == inst.nbn - 1:
        return None
    dp = inst.dados_petro
    nomes = list(dp.get("nomes", []))
    nome = str(nomes[no]) if no < len(nomes) else ""
    if "_order_" in nome:
        return nome.split("_order_", 1)[0]
    elif "_order" in nome:
        return nome.split("_order", 1)[0]
    return nome


def checa_nao_revisita_plataforma(tag_origem, candidatas, erros):
    """Regra de modelagem DEFINITIVA (nao a do artigo Silva et al. 2024):
    cada navio visita cada plataforma NO MAXIMO UMA VEZ por trip (subconjuntos
    de orders continuam permitidos -- so a plataforma nao pode ser abandonada
    e retomada depois). Ja garantida fisicamente por avaliar_rota_silva2024
    (motivo 'retorno_plataforma') para toda candidata das 3 fontes (todas
    passam por ela antes de virar candidata) -- aqui so auditada de forma
    explicita e independente: comprime visitas consecutivas da mesma
    plataforma e confere que nenhuma reaparece depois de abandonada."""
    for c in candidatas:
        seq_plataformas = [_plataforma_de(no) for no in c["seq"]]
        seq_plataformas = [p for p in seq_plataformas if p is not None]
        comprimida = []
        for p in seq_plataformas:
            if not comprimida or comprimida[-1] != p:
                comprimida.append(p)
        if len(comprimida) != len(set(comprimida)):
            erros.append(f"[{tag_origem}] candidata {c['seq']} REVISITA uma plataforma "
                          f"(sequencia comprimida de plataformas={comprimida})")


def roda_caso(tag, k, sigma_k, mu_arc, no_bp, timeout_s=120.0):
    print("\n" + "#" * 100)
    print(f"# CASO: {tag} -- k={k} sigma_k={sigma_k} mu_arc={mu_arc}")
    print("#" * 100)

    pi = list(PI_BASE)

    cand_allbest, completa_ab, timeout_ab = metod.SUB_HEUR_ALLBESTINSERTION_MULTI_SILVA(
        inst, None, pi, sigma_k, k, no_bp, mu_arc=mu_arc, max_candidatas=5,
    )
    cand_bid, completa_bid, timeout_bid = metod.SUB_PROG_BID_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, max_candidatas=5,
    )
    cand_python, completa_py, timeout_py = metod.pricing_silva2024(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, diagnostico=False, timeout_s=timeout_s,
    )

    melhor_ab = cand_allbest[0] if cand_allbest else None
    melhor_bid = cand_bid[0] if cand_bid else None
    melhor_py = cand_python[0] if cand_python else None

    print("\n[SILVA TEST 3 NIVEIS]")
    print(f"k={k}")
    print(f"rc_allbest={melhor_ab['rc'] if melhor_ab else None}")
    print(f"rc_bid={melhor_bid['rc'] if melhor_bid else None}")
    print(f"rc_python={melhor_py['rc'] if melhor_py else None}")
    print(f"python_completa={completa_py}")
    print(f"rota_allbest={melhor_ab['seq'] if melhor_ab else None}")
    print(f"rota_bid={melhor_bid['seq'] if melhor_bid else None}")
    print(f"rota_python={melhor_py['seq'] if melhor_py else None}")

    erros = []

    # ---- contrato de retorno: os dois heuristicos NUNCA certificam ----
    if completa_ab is not False or timeout_ab is not False:
        erros.append("ALLBEST_SILVA nao retornou (busca_completa=False, timeout=False)")
    if completa_bid is not False or timeout_bid is not False:
        erros.append("BID_SILVA nao retornou (busca_completa=False, timeout=False)")

    if not completa_py:
        print("[AVISO] pricing_silva2024 NAO completou a enumeracao neste orcamento "
              "(timeout/max_avaliacoes) -- comparacoes contra o exato reportadas so "
              "como aviso, nao como falha automatica.")

    # ---- auditoria de CORRECAO das candidatas BID_SILVA (secao "TESTE" do pedido) ----
    audita_candidatas("BID_SILVA", cand_bid, k, sigma_k, mu_arc, no_bp, pi, erros)
    # mesma auditoria tambem aplicada a ALLBEST/PD como checagem cruzada (nao
    # e o foco desta tarefa, mas nao custa nada confirmar que segue OK).
    audita_candidatas("ALLBEST_SILVA", cand_allbest, k, sigma_k, mu_arc, no_bp, pi, erros)
    audita_candidatas("SILVA_PD", cand_python, k, sigma_k, mu_arc, no_bp, pi, erros)

    # ---- regra de modelagem definitiva: no maximo 1 visita por plataforma
    # por navio/trip (subconjuntos de orders continuam permitidos) ----
    checa_nao_revisita_plataforma("BID_SILVA", cand_bid, erros)
    checa_nao_revisita_plataforma("ALLBEST_SILVA", cand_allbest, erros)
    checa_nao_revisita_plataforma("SILVA_PD", cand_python, erros)

    # ---- BID_SILVA nao precisa achar a melhor coluna, mas se achou RC<0, o
    # exato (quando completo) tem que tambem achar RC<0 em algum lugar (o
    # espaco do BID e um SUBCONJUNTO do espaco do exato) ----
    if cand_bid and any(c["rc"] < -1e-6 for c in cand_bid) and completa_py:
        if not any(c["rc"] < -1e-6 for c in cand_python):
            erros.append("BID_SILVA encontrou RC<0 mas pricing_silva2024 (exato, completo) "
                          "NAO encontrou nenhum RC<0")

    if melhor_bid is not None and melhor_py is not None and completa_py:
        if melhor_py["rc"] > melhor_bid["rc"] + 1e-8:
            erros.append(f"RC_exato ({melhor_py['rc']}) > RC_bid ({melhor_bid['rc']}) + 1e-8 "
                          f"-- o exato completo deveria encontrar RC igual ou MELHOR")

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

# Caso 2: com mu_arc generico (i,j) e especifico (i,j,k).
no_bp_mu = no_bp_vazio()
mu_arc_teste = {(0, 1): 0.5, (1, 8, 0): 1.2}
ok_geral &= roda_caso("com_mu_arc", 0, sigma_k=1.5, mu_arc=mu_arc_teste, no_bp=no_bp_mu)

# Caso 3: branching ativo -- forca o arco (0,1) e proibe o arco (1,8) para k=0.
no_bp_branch = no_bp_vazio()
no_bp_branch.arcos_fixados_em_1 = {(0, 1, 0)}
no_bp_branch.arcos_proibidos = {(1, 8, 0)}
ok_geral &= roda_caso("com_branching_fixa_0_1_proibe_1_8", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch)

# Caso 4: branching que forca uma sequencia de 2 arcos fixos (testa succ_fixo/
# pred_fixo do BID_SILVA de forma mais exigente).
no_bp_branch2 = no_bp_vazio()
no_bp_branch2.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= roda_caso("com_branching_cadeia_0_6_1", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch2)


# ============================================================
# BID BRANCH TEST -- prova explicita do bug relatado e corrigido:
# fechar (seq_aberta + [depf]) e uma tentativa de registrar/ranquear, NUNCA
# um criterio para descartar o label. Um label cujo fechamento imediato e
# proibido pelo branching (arco fixado forcando outra continuacao, ou o
# proprio arco no->depf proibido) tem que continuar vivo e expansivel.
# ============================================================

def bid_branch_test_arco_fixado(tag, k, sigma_k, no_bp, arco_fixo):
    """arco_fixo=(i,j,kk): confirma que o label que chega em i (que NAO
    consegue fechar direto em i, pois succ_fixo[i]=j bloqueia arco_permitido
    (i, depf)) continua vivo e e expandido para i->j -- exatamente o cenario
    do bug relatado."""
    print("\n" + "#" * 100)
    print(f"# BID BRANCH TEST (arco fixado): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, j, kk = arco_fixo
    candidatas, completa, timeout = metod.SUB_PROG_BID_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc={}, max_candidatas=5,
    )

    label_chegou_i = any(i in c["seq"] for c in candidatas)
    label_expandiu_i_j = any(
        any(c["seq"][t] == i and c["seq"][t + 1] == j for t in range(len(c["seq"]) - 1))
        for c in candidatas
    )
    candidata_contem_arco = label_expandiu_i_j
    respeita_no = all(metod.coluna_respeita_no(no_bp, c["seq"], k) for c in candidatas) if candidatas else False

    print("\n[BID BRANCH TEST]")
    print(f"arco_fixo=({i},{j},{kk})")
    print(f"label_chegou_i={label_chegou_i}")
    print(f"label_expandiu_i_j={label_expandiu_i_j}")
    print(f"candidata_contem_arco={candidata_contem_arco}")
    print(f"coluna_respeita_no={respeita_no}")

    erros = []
    if not candidatas:
        erros.append("BID_SILVA nao encontrou NENHUMA candidata com o arco fixado -- branching nao cumprido")
    if not label_expandiu_i_j:
        erros.append(f"nenhuma candidata BID_SILVA contem o arco fixado ({i},{j}) consecutivo")
    if not respeita_no:
        erros.append("alguma candidata BID_SILVA viola coluna_respeita_no")
    audita_candidatas("BID_SILVA_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)
    checa_nao_revisita_plataforma("BID_SILVA_BRANCH", candidatas, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")
    return len(erros) == 0


def bid_branch_test_arco_proibido_deposito(tag, k, sigma_k, no_bp, arco_proibido):
    """arco_proibido=(i,depf,kk): confirma que o label que chega em i (que
    NAO pode fechar direto em i, pois o arco i->depf esta proibido) continua
    vivo e consegue contornar visitando outro no antes de fechar
    (i->j->...->depf), em vez de ser descartado."""
    print("\n" + "#" * 100)
    print(f"# BID BRANCH TEST (arco proibido p/ deposito): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, depf_no, kk = arco_proibido
    candidatas, completa, timeout = metod.SUB_PROG_BID_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc={}, max_candidatas=5,
    )

    label_chegou_i = any(i in c["seq"] for c in candidatas)
    label_contornou = any(
        i in c["seq"] and c["seq"][c["seq"].index(i) + 1] != depf_no
        for c in candidatas
    )
    nenhuma_usa_arco_proibido = all(
        not any(c["seq"][t] == i and c["seq"][t + 1] == depf_no for t in range(len(c["seq"]) - 1))
        for c in candidatas
    )
    respeita_no = all(metod.coluna_respeita_no(no_bp, c["seq"], k) for c in candidatas) if candidatas else False

    print("\n[BID BRANCH TEST]")
    print(f"arco_proibido=({i},{depf_no},{kk})")
    print(f"label_chegou_i={label_chegou_i}")
    print(f"label_expandiu_i_j={label_contornou}")
    print(f"candidata_contem_arco={nenhuma_usa_arco_proibido}")
    print(f"coluna_respeita_no={respeita_no}")

    erros = []
    if not label_chegou_i:
        erros.append(f"nenhuma candidata BID_SILVA visita o no {i} -- nao da p/ confirmar o contorno")
    if not label_contornou:
        erros.append(f"nenhuma candidata BID_SILVA visita {i} e contorna o fechamento direto p/ o deposito")
    if not nenhuma_usa_arco_proibido:
        erros.append(f"alguma candidata BID_SILVA usa o arco proibido ({i},{depf_no})")
    if not respeita_no:
        erros.append("alguma candidata BID_SILVA viola coluna_respeita_no")
    audita_candidatas("BID_SILVA_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)
    checa_nao_revisita_plataforma("BID_SILVA_BRANCH", candidatas, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")
    return len(erros) == 0


no_bp_bt_fixo = no_bp_vazio()
no_bp_bt_fixo.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= bid_branch_test_arco_fixado(
    "cadeia_0_6_1_forca_6_1", 0, sigma_k=2.0, no_bp=no_bp_bt_fixo, arco_fixo=(6, 1, 0),
)

DEPF = inst.nbn - 1
no_bp_bt_proibido = no_bp_vazio()
no_bp_bt_proibido.arcos_proibidos = {(6, DEPF, 0)}
ok_geral &= bid_branch_test_arco_proibido_deposito(
    "proibe_6_para_deposito", 0, sigma_k=2.0, no_bp=no_bp_bt_proibido, arco_proibido=(6, DEPF, 0),
)

print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
