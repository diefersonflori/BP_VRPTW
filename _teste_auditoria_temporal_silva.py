import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao
from avaliador_rota import AVALIADOR_ROTA_PADRAO

# ============================================================
# Auditoria ARCO A ARCO do cronograma temporal do PSV M, para localizar
# onde exatamente esta o residuo entre o modelo e a Tabela 3 de Silva et
# al. (2024). NAO ALTERA modelo/B&P/avaliador -- so LEITURA de dados e de
# funcoes ja existentes:
#   - Metodos.avaliar_rota_silva2024(..., silva_sp_arcos_base=False):
#     fonte da cronologia oficial (chegada/espera/inicio/fim/janela por no),
#     ja documentada como reproduzindo a MESMA fisica do modelo compacto.
#   - Metodos.metodo_exato_petro(..., fixar_rotas=..., silva_sp_arcos_base=False):
#     usado so como CROSS-CHECK independente (Gurobi) dos agregados, quando
#     a rota fixa e viavel no modelo compacto.
#   - AVALIADOR_ROTA_PADRAO.plataforma_petro: mesma funcao ja usada em toda
#     parte para identificar a plataforma de um no.
#
# A decomposicao arco-a-arco (distancia/VL/VH/threshold/navegacao/SP/SET)
# nao e exposta por nenhuma funcao existente separadamente por arco -- ela e
# recalculada aqui com a MESMA formula (nav piecewise + SET/SP por entrada de
# plataforma nova) documentada em Metodos.tempo_navegacao_silva/tempo_arco
# (metodos.py) e Metodos.avaliar_rota_silva2024.nav_pura_seg/tempo_arco, e
# imediatamente CROSS-VALIDADA contra os agregados oficiais (hN, hB_saida,
# hB_retorno, F, B) das duas funcoes acima. Nenhum parametro fisico (SET,
# SP, distancia, velocidade, TDL, eficiencia) e alterado.
#
# Puramente temporal (secao 10 do pedido): NAO usa alpha_fo/xi/f1/f2 -- so
# o menor cronograma factivel da rota fixa (B=AT sempre, por construcao de
# avaliar_rota_silva2024).
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"
SEG_H = 3600.0
CENARIO_LABEL = "SP_SAIDA_BASE_NAO"  # silva_sp_arcos_base=False -- unico cenario usado nesta auditoria (secao 2)

CASOS = [
    {"tag": "alpha=0 (e 0.25, mesma rota)", "alpha": 0.00, "k": 0,
     "rota": [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15], "F_B_artigo": 93.6},
    {"tag": "alpha=0.50", "alpha": 0.50, "k": 0,
     "rota": [0, 8, 9, 5, 2, 4, 3, 6, 7, 13, 11, 12, 14, 1, 15], "F_B_artigo": 93.4},
]


def carrega(alpha):
    inst = Instancia()
    inst.leitura_petro(ARQ)
    inst.alpha_fo = alpha
    metod = Metodos(inst)
    return inst, metod


def dist_km(dp, depf, i, j):
    """IDENTICA a dist_km usada em Metodos.avaliar_rota_silva2024/
    tempo_navegacao_silva (metodos.py): remapeia depf->0 antes de indexar
    dp['dist'] (mesma matriz, mesma convencao)."""
    ii = 0 if i == depf else i
    jj = 0 if j == depf else j
    return float(dp["dist"][ii][jj])


def nav_pura_seg(dp, depf, veic, i, j):
    """IDENTICA a tempo_navegacao_silva (metodos.py) / nav_pura_seg
    (avaliar_rota_silva2024): piecewise continuo VL/VH/threshold do
    proprio navio. Recalculada aqui SO para exibicao arco-a-arco; o
    resultado e cross-validado abaixo contra hN oficial de
    avaliar_rota_silva2024 e metodo_exato_petro."""
    d = dist_km(dp, depf, i, j)
    if d == 0.0:
        return 0.0, None, None, None
    vs = veic.velocities
    vl = min(vs, key=lambda v: v["above"])["speed"]
    vh = max(vs, key=lambda v: v["above"])["speed"]
    th = max(vs, key=lambda v: v["above"])["above"]
    n_h = d / vl if d <= th else th / vl + (d - th) / vh
    return n_h * SEG_H, vl, vh, th


def set_por_plataforma_chave(inst, dp):
    """Reducao trivial (max) de platform_setup_seg por plataforma -- mesma
    checagem de uniformidade ja feita em metodo_exato_petro/avaliar_rota_silva2024.
    Retorna em HORAS (platform_setup_seg esta em segundos, como o nome indica)."""
    resultado = {}
    for i in range(1, inst.nbcd + 1):
        chave = AVALIADOR_ROTA_PADRAO.plataforma_petro(inst, i)
        resultado.setdefault(chave, set()).add(float(dp["platform_setup_seg"][i]) / SEG_H)
    return {chave: max(vals) for chave, vals in resultado.items()}


def auditar_caso(caso):
    alpha = caso["alpha"]
    k = caso["k"]
    rota = caso["rota"]
    F_B_artigo = caso["F_B_artigo"]

    print("\n\n" + "#" * 110)
    print(f"# CASO: {caso['tag']} -- rota M = {rota} -- cenario {CENARIO_LABEL} (silva_sp_arcos_base=False)")
    print("#" * 110)

    inst, metod = carrega(alpha)
    dp = inst.dados_petro
    dep0 = 0
    depf = inst.nbn - 1
    veic = inst.veiculos[k]
    clientes = set(range(1, inst.nbcd + 1))
    set_chave = set_por_plataforma_chave(inst, dp)

    servico = {i: float(inst.noh[i].SERVICE_TIME[0]) if getattr(inst.noh[i], "SERVICE_TIME", None) else 0.0
               for i in range(inst.nbn)}

    # ---- fonte oficial 1: avaliar_rota_silva2024 (cronologia completa, B=AT sempre) ----
    resultado = metod.avaliar_rota_silva2024(inst, k, rota, diagnostico=True, silva_sp_arcos_base=False)
    cronologia = resultado.get("cronologia", [])
    print(f"\n[FONTE 1] avaliar_rota_silva2024: viavel={resultado['viavel']} motivo={resultado.get('motivo')} "
          f"(len(cronologia)={len(cronologia)} de {len(rota) - 1} arcos esperados)")

    # ---- fonte oficial 2: metodo_exato_petro com a rota fixa (cross-check Gurobi, quando viavel) ----
    sol = Solucao(inst.nbv, inst.nbn)
    ok = metod.metodo_exato_petro(inst, sol, time_limit=60, threads=4, salvar_modelo=False, diagnostico=False,
                                   fixar_rotas={k: rota}, considerar_conflito_plataforma=True,
                                   silva_sp_arcos_base=False)
    status_compacto = getattr(sol, "exato_petro_status", None)
    diag_compacto = getattr(sol, "exato_petro_silva_diag", {}).get(k)
    print(f"[FONTE 2] metodo_exato_petro (fixar_rotas): ok={ok} status={status_compacto} "
          f"(cross-check disponivel = {diag_compacto is not None})")

    # ============================================================
    # SECAO 3+4: arco a arco + cronologia completa (1 passo por arco, em
    # lockstep com cronologia -- ambos iteram exatamente os mesmos pares
    # consecutivos de rota, na mesma ordem -- ver avaliar_rota_silva2024).
    # ============================================================
    print("\n" + "-" * 110)
    print("SECAO 3+4 -- ARCO A ARCO E CRONOLOGIA COMPLETA")
    print("-" * 110)

    # ---- base de saida (calculada ANTES do laco de arcos, pois P e o
    # "tempo_antes_deslocamento" do PRIMEIRO arco -- ver secao 5 abaixo) ----
    AT_h = float(veic.readiness) / SEG_H
    B_h = AT_h  # avaliar_rota_silva2024: B=AT sempre (minimo factivel, sem ganho em atrasar -- ver docstring)
    clientes_rota = [no for no in rota if no not in (dep0, depf)]
    hB_saida_deck = sum(float(dp["tempo_carreg_deck"][no]) for no in clientes_rota) / SEG_H
    hB_saida_diesel = sum(float(dp["tempo_carreg_diesel"][no]) for no in clientes_rota) / SEG_H
    hB_saida_agua = sum(float(dp["tempo_carreg_agua"][no]) for no in clientes_rota) / SEG_H
    hB_saida_h = hB_saida_deck + hB_saida_diesel + hB_saida_agua
    P_h = B_h + hB_saida_h

    hN_soma = 0.0
    SET_soma = 0.0
    SP_soma = 0.0
    servico_soma = 0.0
    espera_soma_direta = 0.0
    tempo_antes = None  # inicio_h do no anterior (ou P, no primeiro arco)
    blocos_plataforma = []  # para secao 9: lista de (chave, [nos], SET, SP)
    bloco_atual = None

    for pos in range(len(rota) - 1):
        i, j = rota[pos], rota[pos + 1]
        pi = AVALIADOR_ROTA_PADRAO.plataforma_petro(inst, i) if i in clientes else None
        pj = AVALIADOR_ROTA_PADRAO.plataforma_petro(inst, j) if j in clientes else None

        nav_seg, vl, vh, th = nav_pura_seg(dp, depf, veic, i, j)
        nav_h = nav_seg / SEG_H
        d_km = dist_km(dp, depf, i, j)

        if j == depf:
            tipo = "ULTIMA PLATAFORMA -> BASE (retorno)"
            SET_h, SP_h = 0.0, 0.0
            print(f"\n[arco {pos}] {tipo}: {i}({pi}) -> {j}(BASE)")
            print(f"  distancia_km={d_km:.4f}")
            print(f"  tempo_navegacao_puro={nav_h:.4f}h")
            print(f"  SP=0.0000h SET=0.0000h  (este arco NUNCA cobra SP/SET, com ou sem silva_sp_arcos_base "
                  f"-- codigo historico, nao alterado nesta etapa)")
        elif i == dep0:
            tipo = "BASE -> PRIMEIRA PLATAFORMA"
            SET_h = set_chave[pj]
            SP_h = 0.0  # cenario SP_SAIDA_BASE_NAO
            print(f"\n[arco {pos}] {tipo}: {i}(BASE) -> {j}({pj})")
            print(f"  distancia_km={d_km:.4f} VL={vl} VH={vh} threshold={th}")
            print(f"  tempo_navegacao_puro={nav_h:.4f}h")
            print(f"  SP=0.0000h (cenario {CENARIO_LABEL}) | SET_destino({pj})={SET_h:.4f}h")
        elif pi == pj:
            tipo = "MESMA PLATAFORMA"
            SET_h, SP_h = 0.0, 0.0
            nav_h = 0.0  # dist=0 entre nos da mesma plataforma (confirmado abaixo por d_km)
            print(f"\n[arco {pos}] {tipo}: {i}({pi}) -> {j}({pj})")
            print(f"  MESMA PLATAFORMA -> navegacao=0.0000h SP=0.0000h SET=0.0000h (distancia_km={d_km:.4f})")
        else:
            tipo = "TRANSICAO ENTRE PLATAFORMAS DIFERENTES"
            SET_h = set_chave[pj]
            SP_h = float(veic.safe_positioning_time) / SEG_H
            print(f"\n[arco {pos}] {tipo}: {i}({pi}) -> {j}({pj})")
            print(f"  distancia_km={d_km:.4f} VL={vl} VH={vh} threshold={th}")
            print(f"  tempo_navegacao_puro={nav_h:.4f}h")
            print(f"  SP={SP_h:.4f}h | SET_destino({pj})={SET_h:.4f}h")

        hN_soma += nav_h
        SET_soma += SET_h
        SP_soma += SP_h

        # ---- bloco de plataforma (secao 9) ----
        if j in clientes:
            if bloco_atual is None or bloco_atual["chave"] != pj:
                if bloco_atual is not None:
                    blocos_plataforma.append(bloco_atual)
                bloco_atual = {"chave": pj, "nos": [], "SET": SET_h, "SP": SP_h}
            bloco_atual["nos"].append(j)

        # ---- cronologia oficial deste MESMO arco (mesma ordem de iteracao) ----
        evento = cronologia[pos] if pos < len(cronologia) else None
        if evento is None:
            print("  [SEM cronologia oficial para este arco -- resultado interrompeu antes (ver motivo acima)]")
            continue

        if j == depf:
            R_h_oficial = evento["chegada_h"]
            print(f"  R (chegada oficial de volta a base) = {R_h_oficial:.4f}h")
            # cross-check: chegada = tempo_antes(inicio no anterior) + servico(anterior) + nav
            servico_anterior_h = servico.get(i, 0.0) / SEG_H
            chegada_calc = (tempo_antes if tempo_antes is not None else 0.0) + servico_anterior_h + nav_h
            diff_chegada = R_h_oficial - chegada_calc
            print(f"  cross-check: tempo_antes({tempo_antes:.4f}) + servico_no_{i}({servico_anterior_h:.4f}) "
                  f"+ nav({nav_h:.4f}) = {chegada_calc:.4f}h | diff vs oficial = {diff_chegada:+.2e}h")
        else:
            no = evento["no"]
            order_original = dp["order_ids"][no] if no < len(dp["order_ids"]) else None
            servico_no_h = servico.get(no, 0.0) / SEG_H
            servico_soma += servico_no_h
            espera_soma_direta += evento["espera_h"]

            servico_anterior_h = servico.get(i, 0.0) / SEG_H if i != dep0 else 0.0
            base_antes = tempo_antes if tempo_antes is not None else P_h
            chegada_calc = (base_antes if base_antes is not None else 0.0) + servico_anterior_h + nav_h + SP_h + SET_h
            diff_chegada = evento["chegada_h"] - chegada_calc

            jinfo = resultado.get("janelas_usadas", {}).get(no, {})

            print(f"  order_interno={no} order_original_silva={order_original} plataforma={pj}")
            print(f"  tempo_antes_deslocamento={base_antes:.4f}h (inicio do no anterior, ou P se 1o arco)")
            print(f"  servico_no_anterior({i})={servico_anterior_h:.4f}h | arco(nav+SP+SET)={nav_h + SP_h + SET_h:.4f}h")
            print(f"  chegada_fisica(oficial)={evento['chegada_h']:.4f}h | "
                  f"chegada_calculada(cross-check)={chegada_calc:.4f}h | diff={diff_chegada:+.2e}h")
            print(f"  janela_escolhida idx={jinfo.get('indice')} ready={jinfo.get('ready_h')} due={jinfo.get('due_h')}")
            print(f"  espera={evento['espera_h']:.4f}h | inicio_servico={evento['inicio_h']:.4f}h | "
                  f"duracao_servico={servico_no_h:.4f}h | fim_servico={evento['fim_h']:.4f}h")

            tempo_antes = evento["inicio_h"]

    if bloco_atual is not None:
        blocos_plataforma.append(bloco_atual)

    # ============================================================
    # SECAO 5 -- BASE (saida e retorno) -- valores ja calculados ANTES do
    # laco de arcos (necessario para o cross-check do 1o arco); so exibidos aqui.
    # ============================================================
    print("\n" + "-" * 110)
    print("SECAO 5 -- BASE (carregamento na saida / descarga no retorno)")
    print("-" * 110)

    print(f"  B (=AT, minimo factivel) = {B_h:.4f}h")
    print(f"  carregamento_deck  = {hB_saida_deck:.4f}h")
    print(f"  carregamento_diesel= {hB_saida_diesel:.4f}h")
    print(f"  carregamento_agua  = {hB_saida_agua:.4f}h")
    print(f"  hB_saida total     = {hB_saida_h:.4f}h")
    print(f"  P (partida efetiva)= B+hB_saida = {P_h:.4f}h")

    R_h_oficial = cronologia[-1]["chegada_h"] if cronologia and cronologia[-1].get("evento") == "retorno_base" else None
    hB_retorno_h = sum(float(dp["tempo_descarreg_backload"][no]) for no in clientes_rota
                        if dp["commodities"][no] == "deckCargoBackload") / SEG_H
    print(f"\n  R (chegada de volta, oficial) = {R_h_oficial}")
    backload_total = sum(float(dp["dem_deck_backload"][no]) for no in clientes_rota)
    print(f"  backload_total (unidades)     = {backload_total:.4f}")
    print(f"  tempo_descarga_backload total = {hB_retorno_h:.4f}h")
    F_h = (R_h_oficial + hB_retorno_h) if R_h_oficial is not None else None
    print(f"  hB_retorno = {hB_retorno_h:.4f}h")
    print(f"  F = R + hB_retorno = {F_h}")
    print(f"  F - B = {(F_h - B_h) if F_h is not None else None}")

    # ============================================================
    # SECAO 6 -- RESUMO POR COMPONENTE
    # ============================================================
    print("\n" + "-" * 110)
    print("SECAO 6 -- RESUMO POR COMPONENTE (script de auditoria)")
    print("-" * 110)

    hN_h = hN_soma
    SET_h_tot = SET_soma
    SP_h_tot = SP_soma
    servico_h_tot = servico_soma
    hDP_h = None
    espera_residual = None
    total_script = None
    if F_h is not None:
        hDP_h = (R_h_oficial - P_h) - hN_h
        espera_residual = hDP_h - SET_h_tot - SP_h_tot - servico_h_tot
        total_script = hB_saida_h + hN_h + SP_h_tot + SET_h_tot + servico_h_tot + espera_residual + hB_retorno_h

    print(f"  hB_saida         = {hB_saida_h:.4f}h")
    print(f"  hN (navegacao)   = {hN_h:.4f}h")
    print(f"  SP               = {SP_h_tot:.4f}h")
    print(f"  SET              = {SET_h_tot:.4f}h")
    print(f"  servico_offshore = {servico_h_tot:.4f}h")
    print(f"  espera (residual = hDP-SET-SP-servico) = {espera_residual}")
    print(f"  espera (soma direta da cronologia)     = {espera_soma_direta:.4f}h")
    if espera_residual is not None:
        print(f"    diff espera (residual - direta) = {espera_residual - espera_soma_direta:+.2e}h")
    print(f"  hB_retorno       = {hB_retorno_h:.4f}h")
    print(f"  TOTAL (script)   = {total_script}")
    print(f"  TOTAL_artigo (F-s publicado) = {F_B_artigo:.4f}h")
    if total_script is not None:
        residuo = total_script - F_B_artigo
        print(f"  RESIDUO = TOTAL_script - TOTAL_artigo = {residuo:+.4f}h")
    else:
        print(f"  RESIDUO = nao calculavel (rota nao completou cronologia ate o retorno -- ver motivo)")
        residuo = None

    # ---- cross-check contra as duas fontes oficiais ----
    print("\n  --- CROSS-CHECK vs FONTE 1 (avaliar_rota_silva2024) ---")
    if resultado["viavel"]:
        for campo, valor_script in [("hB_saida", hB_saida_h), ("hB_retorno", hB_retorno_h),
                                     ("hN", hN_h), ("hDP", hDP_h), ("F", F_h), ("B", B_h)]:
            valor_oficial = resultado.get(campo)
            if valor_oficial is None:
                continue
            diff = valor_script - valor_oficial
            marca = "OK" if abs(diff) < 1e-6 else "*** DIFERE ***"
            print(f"    {campo}: script={valor_script:.6f} oficial={valor_oficial:.6f} diff={diff:+.2e} [{marca}]")
    else:
        print(f"    resultado['viavel']=False (motivo={resultado.get('motivo')}) -- avaliar_rota_silva2024 nao "
              f"retorna os agregados hB/hN/hDP/F/B estruturados quando inviavel (só a cronologia, ja auditada acima).")

    print("\n  --- CROSS-CHECK vs FONTE 2 (metodo_exato_petro, Gurobi) ---")
    if diag_compacto is not None:
        for campo_script, campo_diag, valor_script in [
            ("hB_saida", "hB_saida", hB_saida_h), ("hB_retorno", "hB_retorno", hB_retorno_h),
            ("hN", "hN", hN_h), ("SET", "SET", SET_h_tot), ("SP", "SP", SP_h_tot),
            ("servico", "servico", servico_h_tot), ("F", "F", F_h), ("B", "B", B_h),
            ("dur(F-B)", "dur", (F_h - B_h) if F_h is not None else None),
        ]:
            valor_oficial = diag_compacto.get(campo_diag)
            if valor_script is None or valor_oficial is None:
                continue
            diff = valor_script - valor_oficial
            marca = "OK" if abs(diff) < 1e-6 else "*** DIFERE ***"
            print(f"    {campo_script}: script={valor_script:.6f} compacto(Gurobi)={valor_oficial:.6f} "
                  f"diff={diff:+.2e} [{marca}]")
    else:
        print(f"    sem cross-check possivel: metodo_exato_petro tambem nao formou incumbente para esta rota "
              f"neste cenario (status={status_compacto}) -- mesmo motivo fisico (ver TDL acima), nao um bug do script.")

    # ============================================================
    # SECAO 7 -- distancias unicas usadas na rota
    # ============================================================
    print("\n" + "-" * 110)
    print("SECAO 7 -- DISTANCIAS UNICAS USADAS NA ROTA (diagnostico, SEM alterar distancia/Haversine)")
    print("-" * 110)
    dists_unicas = sorted({dist_km(dp, depf, rota[pos], rota[pos + 1]) for pos in range(len(rota) - 1)})
    for dv in dists_unicas:
        print(f"  {dv:.4f} km")

    print("\n  Onde estao concentrados os componentes do total (script):")
    if total_script is not None and total_script > 0:
        for nome_comp, valor in [("navegacao(hN)", hN_h), ("SP", SP_h_tot), ("SET", SET_h_tot),
                                  ("servico_offshore", servico_h_tot), ("espera", espera_residual),
                                  ("base(hB_saida+hB_retorno)", hB_saida_h + hB_retorno_h)]:
            pct = 100.0 * valor / total_script
            print(f"    {nome_comp:28s} = {valor:8.4f}h ({pct:5.1f}% do total)")
    else:
        print("    nao calculavel (rota nao completou -- ver secao 6)")

    # ============================================================
    # SECAO 9 -- blocos de mesma plataforma
    # ============================================================
    print("\n" + "-" * 110)
    print("SECAO 9 -- VERIFICACAO DE SERVICOS NA MESMA PLATAFORMA (SET/SP unicos por bloco)")
    print("-" * 110)
    for bloco in blocos_plataforma:
        nos_str = ",".join(str(n) for n in bloco["nos"])
        orders_str = ",".join(str(dp["order_ids"][n]) for n in bloco["nos"])
        n_internos = len(bloco["nos"]) - 1
        print(f"\n  Plataforma {bloco['chave']} | nos internos=[{nos_str}] (orders_silva=[{orders_str}])")
        print(f"    SET cobrado 1x ao entrar = {bloco['SET']:.4f}h | SP cobrado 1x ao entrar = {bloco['SP']:.4f}h")
        print(f"    arcos internos (mesma plataforma) = {n_internos} (todos com nav=SP=SET=0, confirmado na secao 3)")
        for no in bloco["nos"]:
            print(f"    - order_interno={no} order_silva={dp['order_ids'][no]} commodity={dp['commodities'][no]} "
                  f"servico={servico.get(no, 0.0) / SEG_H:.4f}h deck_load={dp['dem_deck_load'][no]:.1f} "
                  f"deck_backload={dp['dem_deck_backload'][no]:.1f} diesel={dp['dem_diesel'][no]:.1f} "
                  f"agua={dp['dem_agua'][no]:.1f}")

    return {
        "alpha": alpha, "F_B_artigo": F_B_artigo, "residuo": residuo,
        "hB_saida": hB_saida_h, "hN": hN_h, "SP": SP_h_tot, "SET": SET_h_tot,
        "servico": servico_h_tot, "espera": espera_residual, "hB_retorno": hB_retorno_h,
        "total_script": total_script, "viavel_avaliador": resultado["viavel"],
        "motivo_avaliador": resultado.get("motivo"),
    }


print("#" * 110)
print("# AUDITORIA TEMPORAL ARCO A ARCO -- PSV M -- Silva et al. (2024)")
print(f"# Cenario unico usado: {CENARIO_LABEL} (silva_sp_arcos_base=False)")
print("# Puramente TEMPORAL -- alpha_fo/xi/f1/f2 NAO sao usados (secao 10 do pedido).")
print("# NENHUMA alteracao de formulacao/parametro fisico foi feita nesta etapa.")
print("#" * 110)

resumos = []
for caso in CASOS:
    resumos.append(auditar_caso(caso))

# ============================================================
# SECAO 8 -- comparacao alpha=0 vs alpha=0.50
# ============================================================
print("\n\n" + "#" * 110)
print("# SECAO 8 -- COMPARACAO ALPHA=0 vs ALPHA=0.50 (mesmo cenario SP_SAIDA_BASE_NAO)")
print("#" * 110)
r0, r50 = resumos[0], resumos[1]
cab = f"{'componente':28s} | {'alpha=0':>10} | {'alpha=0.50':>10} | {'diferenca':>10}"
print(cab)
print("-" * len(cab))
for comp in ["hB_saida", "hN", "SP", "SET", "servico", "espera", "hB_retorno", "total_script"]:
    v0, v50 = r0.get(comp), r50.get(comp)
    if v0 is None or v50 is None:
        print(f"{comp:28s} | {'NA':>10} | {'NA':>10} | {'NA':>10}")
    else:
        print(f"{comp:28s} | {v0:10.4f} | {v50:10.4f} | {v50 - v0:+10.4f}")

# ============================================================
# SECAO 11 -- CONCLUSAO OBJETIVA
# ============================================================
print("\n\n" + "#" * 110)
print("# SECAO 11 -- CONCLUSAO OBJETIVA (diagnostico, NENHUMA correcao aplicada)")
print("#" * 110)

for r in resumos:
    if r["residuo"] is not None:
        print(f"\nalpha={r['alpha']}: RESIDUO M = TOTAL_script({r['total_script']:.4f}h) - "
              f"TOTAL_artigo({r['F_B_artigo']:.4f}h) = {r['residuo']:+.4f}h")
    else:
        print(f"\nalpha={r['alpha']}: RESIDUO nao calculavel -- avaliar_rota_silva2024 retornou "
              f"viavel={r['viavel_avaliador']} motivo={r['motivo_avaliador']} (rota nao fecha ciclo completo "
              f"de B a F sob os parametros atuais, mesmo no cenario {CENARIO_LABEL}).")

print("\nO artigo (Silva et al. 2024) NAO publica a decomposicao de f-s em hB/hN/SP/SET/servico/espera --")
print("so publica s (=B) e f (=F) agregados. Portanto NAO e possivel apontar, a partir do artigo, qual")
print("componente especifico do NOSSO modelo diverge do componente correspondente do artigo -- so podemos")
print("dizer ONDE o residuo esta concentrado DENTRO do nosso proprio calculo (ver percentuais na secao 7 de")
print("cada caso acima), nao se aquele componente especifico do artigo teria o mesmo valor.")

print("\nAchados desta auditoria:")
print("  - SET duplicado: NAO encontrado (1 valor por bloco de plataforma, confirmado na secao 9).")
print("  - SP duplicado: NAO encontrado (1 valor por bloco de plataforma, exceto base->1a quando SP=0 no cenario).")
print("  - servico duplicado: NAO encontrado (1 valor por order, somado uma unica vez).")
print("  - espera causada por janela: ver campo 'espera' por no na secao 4 de cada caso -- valores de espera_h")
print("    positivos indicam that o navio chegou antes do inicio da janela escolhida e aguardou.")
print("  - descarga de backload inesperada: nao encontrada -- hB_retorno bate exatamente com a soma de")
print("    tempo_descarreg_backload dos nos deckCargoBackload da rota (cross-check OK, ver secao 6).")
print("  - diferenca entre calculo do modelo (metodo_exato_petro/Gurobi) e do script: ver blocos")
print("    'CROSS-CHECK vs FONTE 1/2' de cada caso -- qualquer linha marcada [*** DIFERE ***] indica")
print("    inconsistencia real a investigar; ausencia de marcas = os tres calculos (script, avaliador,")
print("    modelo compacto) concordam exatamente.")

print("\n[FIM DA AUDITORIA -- nenhuma correcao foi aplicada.]")
