import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

import types

from instancia import Instancia
from metodos import Metodos

# ============================================================
# TESTE 4 NIVEIS -- ALLBEST_SILVA x BID_SILVA x PD_SILVA (label-setting/DP,
# exato) x pricing_silva2024 (enumerativo, exato/diagnostico), com os MESMOS
# duais (pi/sigma/mu) e o MESMO k, na instancia 14n. NAO roda B&P/300s -- so
# as quatro funcoes de pricing isoladas, com duais deterministicos (mesmos
# de _teste_3niveis_silva.py, ja validado -- NAO alterado por este arquivo).
#
# ALLBEST_SILVA e BID_SILVA sao heuristicos (busca_completa=False sempre) --
# NAO se exige que encontrem a melhor coluna. PD_SILVA e pricing_silva2024
# sao os dois EXATOS (cada um so certifica quando sua propria busca
# completou sem timeout/limite) -- quando ambos completam, devem concordar
# no melhor RC encontrado (mesmo espaco de rotas validas).
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(ARQ)
metod = Metodos(inst)

PI_BASE = [28.0, 32.0, 22.0, 40.0, 26.0, 45.0, 24.0, 20.0, 33.0, 15.0, 29.0, 36.0, 21.0, 18.0]
assert len(PI_BASE) == inst.nbcd == 14

PD_TIMEOUT_S = 20.0
PD_MAX_LABELS = 300_000
ENUM_TIMEOUT_S = 20.0


def no_bp_vazio():
    ns = types.SimpleNamespace()
    ns.arcos_proibidos = set()
    ns.arcos_fixados_em_1 = set()
    return ns


def audita_candidatas(tag_origem, candidatas, k, sigma_k, mu_arc, no_bp, pi, erros):
    """viavel por avaliar_rota_silva2024, custo/rc batendo a 1e-8, branching
    respeitado -- mesma auditoria de _teste_3niveis_silva.py, reaproveitada."""
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
    """Regra de modelagem definitiva: no maximo 1 visita por plataforma por
    navio/trip (subconjuntos de orders continuam permitidos)."""
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


def roda_caso(tag, k, sigma_k, mu_arc, no_bp):
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
    cand_pd, completa_pd, timeout_pd = metod.SUB_PROG_PD_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, max_candidatas=5, timeout_s=PD_TIMEOUT_S, max_labels=PD_MAX_LABELS,
    )
    cand_enum, completa_enum, timeout_enum = metod.pricing_silva2024(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc=mu_arc, diagnostico=False, timeout_s=ENUM_TIMEOUT_S,
    )

    melhor_ab = cand_allbest[0] if cand_allbest else None
    melhor_bid = cand_bid[0] if cand_bid else None
    melhor_pd = cand_pd[0] if cand_pd else None
    melhor_enum = cand_enum[0] if cand_enum else None

    print("\n[SILVA TEST 4 NIVEIS]")
    print(f"caso={tag}")
    print(f"k={k}")
    print(f"rc_allbest={melhor_ab['rc'] if melhor_ab else None}")
    print(f"rc_bid={melhor_bid['rc'] if melhor_bid else None}")
    print(f"rc_pd={melhor_pd['rc'] if melhor_pd else None}")
    print(f"rc_enum={melhor_enum['rc'] if melhor_enum else None}")
    print(f"pd_completa={completa_pd}")
    print(f"enum_completa={completa_enum}")
    print(f"rota_pd={melhor_pd['seq'] if melhor_pd else None}")

    erros = []

    # ---- contrato de retorno: os dois heuristicos NUNCA certificam ----
    if completa_ab is not False or timeout_ab is not False:
        erros.append("ALLBEST_SILVA nao retornou (busca_completa=False, timeout=False)")
    if completa_bid is not False or timeout_bid is not False:
        erros.append("BID_SILVA nao retornou (busca_completa=False, timeout=False)")

    if not completa_pd:
        print(f"[AVISO] PD_SILVA NAO completou a busca neste orcamento "
              f"(timeout_s={PD_TIMEOUT_S}/max_labels={PD_MAX_LABELS}) -- comparacoes "
              f"contra ele reportadas so como aviso, nao como falha automatica.")
    if not completa_enum:
        print("[AVISO] pricing_silva2024 NAO completou a enumeracao neste orcamento -- "
              "comparacoes contra ele reportadas so como aviso, nao como falha automatica.")

    # ---- auditoria de CORRECAO das candidatas PD_SILVA (secao 14 do pedido) ----
    audita_candidatas("PD_SILVA", cand_pd, k, sigma_k, mu_arc, no_bp, pi, erros)
    audita_candidatas("BID_SILVA", cand_bid, k, sigma_k, mu_arc, no_bp, pi, erros)
    audita_candidatas("ALLBEST_SILVA", cand_allbest, k, sigma_k, mu_arc, no_bp, pi, erros)
    audita_candidatas("SILVA_ENUM", cand_enum, k, sigma_k, mu_arc, no_bp, pi, erros)

    checa_nao_revisita_plataforma("PD_SILVA", cand_pd, erros)
    checa_nao_revisita_plataforma("BID_SILVA", cand_bid, erros)
    checa_nao_revisita_plataforma("ALLBEST_SILVA", cand_allbest, erros)
    checa_nao_revisita_plataforma("SILVA_ENUM", cand_enum, erros)

    # ---- PD_SILVA explora um espaco que contem o de BID_SILVA/ALLBEST_SILVA
    # (sem beam/GRASP): quando pd_completa=True, o melhor RC do PD tem que
    # ser igual ou melhor (mais negativo) que o de ambos heuristicos ----
    if completa_pd:
        if melhor_bid is not None and (melhor_pd is None or melhor_pd["rc"] > melhor_bid["rc"] + 1e-8):
            erros.append(f"PD_SILVA completo (rc={melhor_pd['rc'] if melhor_pd else None}) "
                          f"pior que BID_SILVA (rc={melhor_bid['rc']}) -- nao deveria, "
                          f"o espaco do PD contem o do BID")
        if melhor_ab is not None and (melhor_pd is None or melhor_pd["rc"] > melhor_ab["rc"] + 1e-8):
            erros.append(f"PD_SILVA completo (rc={melhor_pd['rc'] if melhor_pd else None}) "
                          f"pior que ALLBEST_SILVA (rc={melhor_ab['rc']}) -- nao deveria, "
                          f"o espaco do PD contem o do ALLBEST")

    # ---- PD_SILVA e pricing_silva2024 cobrem o MESMO espaco exato de rotas
    # validas; quando os DOIS completam, o melhor RC tem que bater ----
    if completa_pd and completa_enum:
        rc_pd_val = melhor_pd["rc"] if melhor_pd else None
        rc_enum_val = melhor_enum["rc"] if melhor_enum else None
        if (rc_pd_val is None) != (rc_enum_val is None):
            erros.append(f"PD_SILVA e pricing_silva2024 completos mas discordam se existe "
                          f"RC<0 (pd={rc_pd_val}, enum={rc_enum_val})")
        elif rc_pd_val is not None and abs(rc_pd_val - rc_enum_val) > 1e-6:
            erros.append(f"PD_SILVA completo (rc={rc_pd_val}) difere de pricing_silva2024 "
                          f"completo (rc={rc_enum_val}) por {abs(rc_pd_val - rc_enum_val):.2e} "
                          f"-- os dois exatos deveriam concordar no melhor RC")

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")

    return len(erros) == 0


def pd_branch_test_arco_fixado(tag, k, sigma_k, no_bp, arco_fixo):
    """arco_fixo=(i,j,kk): mesmo cenario do [BID BRANCH TEST], agora para
    PD_SILVA -- confirma que o label que chega em i (que NAO consegue
    fechar direto em i, pois succ_fixo[i]=j bloqueia arco_permitido(i,depf))
    continua vivo e e expandido para i->j."""
    print("\n" + "#" * 100)
    print(f"# PD BRANCH TEST (arco fixado): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, j, kk = arco_fixo
    candidatas, completa, timeout = metod.SUB_PROG_PD_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc={}, max_candidatas=5, timeout_s=PD_TIMEOUT_S, max_labels=PD_MAX_LABELS,
    )

    label_chegou_i = any(i in c["seq"] for c in candidatas)
    label_expandiu_i_j = any(
        any(c["seq"][t] == i and c["seq"][t + 1] == j for t in range(len(c["seq"]) - 1))
        for c in candidatas
    )
    candidata_contem_arco = label_expandiu_i_j
    respeita_no = all(metod.coluna_respeita_no(no_bp, c["seq"], k) for c in candidatas) if candidatas else False

    print("\n[PD BRANCH TEST]")
    print(f"arco_fixo=({i},{j},{kk})")
    print(f"label_chegou_i={label_chegou_i}")
    print(f"label_expandiu_i_j={label_expandiu_i_j}")
    print(f"candidata_contem_arco={candidata_contem_arco}")
    print(f"coluna_respeita_no={respeita_no}")
    print(f"pd_completa={completa}")

    erros = []
    if not candidatas:
        erros.append("PD_SILVA nao encontrou NENHUMA candidata com o arco fixado -- branching nao cumprido")
    if not label_expandiu_i_j:
        erros.append(f"nenhuma candidata PD_SILVA contem o arco fixado ({i},{j}) consecutivo")
    if not respeita_no:
        erros.append("alguma candidata PD_SILVA viola coluna_respeita_no")
    audita_candidatas("PD_SILVA_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)
    checa_nao_revisita_plataforma("PD_SILVA_BRANCH", candidatas, erros)

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] todas as checagens passaram")
    return len(erros) == 0


def pd_branch_test_arco_proibido_deposito(tag, k, sigma_k, no_bp, arco_proibido):
    """arco_proibido=(i,depf,kk): confirma que o label que chega em i (que
    NAO pode fechar direto em i) continua vivo e consegue contornar
    (i->j->...->depf) em vez de ser descartado."""
    print("\n" + "#" * 100)
    print(f"# PD BRANCH TEST (arco proibido p/ deposito): {tag}")
    print("#" * 100)

    pi = list(PI_BASE)
    i, depf_no, kk = arco_proibido
    candidatas, completa, timeout = metod.SUB_PROG_PD_SILVA(
        inst, pi, sigma_k, k, no_bp,
        arcos_proibidos=no_bp.arcos_proibidos, arcos_fixados=no_bp.arcos_fixados_em_1,
        mu_arc={}, max_candidatas=5, timeout_s=PD_TIMEOUT_S, max_labels=PD_MAX_LABELS,
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

    print("\n[PD BRANCH TEST]")
    print(f"arco_proibido=({i},{depf_no},{kk})")
    print(f"label_chegou_i={label_chegou_i}")
    print(f"label_expandiu_i_j={label_contornou}")
    print(f"candidata_contem_arco={nenhuma_usa_arco_proibido}")
    print(f"coluna_respeita_no={respeita_no}")
    print(f"pd_completa={completa}")

    erros = []
    if not label_chegou_i:
        erros.append(f"nenhuma candidata PD_SILVA visita o no {i} -- nao da p/ confirmar o contorno")
    if not label_contornou:
        erros.append(f"nenhuma candidata PD_SILVA visita {i} e contorna o fechamento direto p/ o deposito")
    if not nenhuma_usa_arco_proibido:
        erros.append(f"alguma candidata PD_SILVA usa o arco proibido ({i},{depf_no})")
    if not respeita_no:
        erros.append("alguma candidata PD_SILVA viola coluna_respeita_no")
    audita_candidatas("PD_SILVA_BRANCH", candidatas, k, sigma_k, {}, no_bp, pi, erros)
    checa_nao_revisita_plataforma("PD_SILVA_BRANCH", candidatas, erros)

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

# Caso 4: branching que forca uma cadeia de 2 arcos fixos.
no_bp_branch2 = no_bp_vazio()
no_bp_branch2.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= roda_caso("com_branching_cadeia_0_6_1", 0, sigma_k=2.0, mu_arc={}, no_bp=no_bp_branch2)


# ============================================================
# PD BRANCH TEST -- mesma prova do [BID BRANCH TEST], agora para PD_SILVA.
# ============================================================

no_bp_bt_fixo = no_bp_vazio()
no_bp_bt_fixo.arcos_fixados_em_1 = {(0, 6, 0), (6, 1, 0)}
ok_geral &= pd_branch_test_arco_fixado(
    "cadeia_0_6_1_forca_6_1", 0, sigma_k=2.0, no_bp=no_bp_bt_fixo, arco_fixo=(6, 1, 0),
)

DEPF = inst.nbn - 1
no_bp_bt_proibido = no_bp_vazio()
no_bp_bt_proibido.arcos_proibidos = {(6, DEPF, 0)}
ok_geral &= pd_branch_test_arco_proibido_deposito(
    "proibe_6_para_deposito", 0, sigma_k=2.0, no_bp=no_bp_bt_proibido, arco_proibido=(6, DEPF, 0),
)

print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
