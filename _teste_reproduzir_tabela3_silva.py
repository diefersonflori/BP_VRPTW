import sys
sys.path.insert(0, r"C:\Users\PolyanaSilva\Documents\BP_VRPTW")

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

# ============================================================
# Reproducao da Tabela 3 de Silva et al. (2024) para a instancia
# 14n-2k-6c-008r_ML_silva2024, com rotas FIXAS (publicadas), variando
# alpha_fo E o tratamento de SP na perna de saida da base
# (silva_sp_arcos_base). O Gurobi resolve so o cronograma (B_k/berco,
# janela, sequenciamento de plataforma); nao escolhe rotas.
#
# Nomenclatura do artigo -> nossa nomenclatura:
#   AT = disponibilidade do PSV        -> AT_k
#   s  = inicio do servico de carreg. na base -> B_k (berco[k])
#   f  = fim completo da rota          -> F_k
#   f-s                                -> F_k - B_k
# NAO comparar s com P_k, NAO comparar f com R_k (ver enunciado).
#
# Cenarios (parametro silva_sp_arcos_base de metodo_exato_petro, DEFAULT=True):
#   SP_SAIDA_BASE_SIM (True):  base->1a_plataforma leva N+SP+SET (igual ao
#                                comportamento historico/default do modelo).
#   SP_SAIDA_BASE_NAO  (False): base->1a_plataforma leva N+SET, SEM SP
#                                (convencao observada empiricamente na
#                                Tabela 3 -- SET nunca removido).
# Em AMBOS os cenarios, plataforma->plataforma diferente continua N+SP+SET,
# e plataforma->base continua SEM SP/SET (isso NUNCA teve SP/SET, com ou
# sem esta chave -- nao e alterado por nenhum cenario).
#
# XI: f2 = sum xi_k*(F_k-AT_k) usa hoje xi_k=1 implicito, NAO CONFIRMADO
# contra o artigo -- ver DIAGNOSTICO_SILVA2024.md secao 4.3.
# ============================================================

ARQ = r"instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json"

TOL_H = 0.15      # tolerancia de reproducao temporal (Tabela 3 arredondada em 1 casa decimal)
TOL_DECOMP = 1e-6  # tolerancia da checagem de fechamento F-B = soma das parcelas

NOME_PSV = {0: "M", 1: "L"}

CENARIOS = [
    ("SP_SAIDA_BASE_SIM", True),
    ("SP_SAIDA_BASE_NAO", False),
]

ROTAS_TABELA3 = {
    0.00: {
        0: [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15],
        1: [0, 10, 15],
    },
    0.25: {
        0: [0, 1, 8, 9, 5, 2, 4, 3, 6, 7, 13, 14, 11, 12, 15],
        1: [0, 10, 15],
    },
    0.50: {
        0: [0, 8, 9, 5, 2, 4, 3, 6, 7, 13, 11, 12, 14, 1, 15],
        1: [0, 10, 15],
    },
    0.75: {
        0: [0, 1, 4, 2, 3, 6, 7, 13, 11, 14, 12, 5, 15],
        1: [0, 10, 8, 9, 15],
    },
    1.00: {
        0: [0, 5, 7, 6, 11, 14, 13, 12, 4, 2, 3, 1, 15],
        1: [0, 10, 8, 9, 15],
    },
}

ALVOS_TABELA3 = {
    0.00: {
        0: {"AT": 7.0, "s": 7.0, "f": 100.6, "dur": 93.6},
        1: {"AT": 0.8, "s": 0.8, "f": 32.5, "dur": 31.7},
    },
    0.25: {
        0: {"AT": 7.0, "s": 7.0, "f": 100.6, "dur": 93.6},
        1: {"AT": 0.8, "s": 0.8, "f": 32.5, "dur": 31.7},
    },
    0.50: {
        0: {"AT": 7.0, "s": 7.3, "f": 100.7, "dur": 93.4},
        1: {"AT": 0.8, "s": 0.8, "f": 32.5, "dur": 31.7},
    },
    0.75: {
        0: {"AT": 7.0, "s": 12.2, "f": 100.7, "dur": 88.5},
        1: {"AT": 0.8, "s": 0.8, "f": 35.2, "dur": 34.4},
    },
    1.00: {
        0: {"AT": 7.0, "s": 20.1, "f": 108.6, "dur": 88.5},
        1: {"AT": 0.8, "s": 0.8, "f": 35.2, "dur": 34.4},
    },
}

ALPHAS = [0.00, 0.25, 0.50, 0.75, 1.00]

linhas_tabela_final = []
linhas_decomposicao = []

print("#" * 100)
print("# REPRODUCAO TABELA 3 SILVA ET AL. (2024) -- instancia 14n-2k-6c-008r_ML_silva2024")
print("#" * 100)
print("[XI PROVISORIO = 1] f2 = sum(F_k - AT_k), xi_k do artigo NAO confirmado.")
print("[ESCOPO] (A) reproducao TEMPORAL de rotas publicadas FIXAS -- NAO eh (B) reproducao")
print("         da selecao otima de rotas via FO (rotas nao sao otimizadas aqui).")
print("[CENARIOS] SP_SAIDA_BASE_SIM=silva_sp_arcos_base=True (DEFAULT, formulacao literal, "
      "identico ao comportamento historico) | SP_SAIDA_BASE_NAO=silva_sp_arcos_base=False "
      "(experimental, SP removido so da perna base->1a_plataforma).")

for alpha in ALPHAS:
    for nome_cenario, silva_sp_arcos_base in CENARIOS:
        inst = Instancia()
        inst.leitura_petro(ARQ)
        inst.alpha_fo = alpha

        metod = Metodos(inst)
        sol = Solucao(inst.nbv, inst.nbn)

        rotas_fixas = ROTAS_TABELA3[alpha]

        print("\n" + "=" * 100)
        print(f"TABELA 3 SILVA -- alpha={alpha} -- cenario={nome_cenario} "
              f"(silva_sp_arcos_base={silva_sp_arcos_base})")
        print("=" * 100)

        ok = metod.metodo_exato_petro(
            inst, sol,
            time_limit=120, threads=4, salvar_modelo=False, diagnostico=True,
            fixar_rotas=rotas_fixas,
            considerar_conflito_plataforma=True,
            silva_sp_arcos_base=silva_sp_arcos_base,
        )
        status = getattr(sol, "exato_petro_status", None)
        diag = getattr(sol, "exato_petro_silva_diag", {})

        print(f"\n>>> ok={ok} status={status} obj={getattr(sol, 'exato_petro_obj', None)}")

        for k in sorted(rotas_fixas.keys()):
            nome = NOME_PSV.get(k, str(k))
            alvo = ALVOS_TABELA3[alpha][k]
            d = diag.get(k)

            print(f"\nPSV {nome} [{nome_cenario}]:")
            if d is None:
                print(f"  [SEM INCUMBENTE -- status={status} -- modelo nao encontrou nenhum cronograma "
                      f"para esta rota fixa; nao ha valores para comparar]")
                linhas_tabela_final.append({
                    "alpha": alpha, "psv": nome, "cenario": nome_cenario, "status": status,
                    "s_art": alvo["s"], "B_mod": None, "erro_s": None,
                    "f_art": alvo["f"], "F_mod": None, "erro_f": None,
                    "dur_art": alvo["dur"], "durF_B_mod": None, "erro_dur": None,
                })
                continue

            if not ok:
                print(f"  [AVISO] status={status}, Gurobi encontrou um cronograma "
                      f"(obj={getattr(sol, 'exato_petro_obj', None)}), mas a validacao operacional "
                      f"pos-hoc REJEITOU a rota reconstruida (sol.exato_petro_consistente=False). "
                      f"Os valores abaixo sao os do cronograma que o Gurobi calculou mesmo assim.")

            erro_s = d["B"] - alvo["s"]
            erro_f = d["F"] - alvo["f"]
            erro_dur = d["dur"] - alvo["dur"]

            print(f"  AT artigo = {alvo['AT']:.4f}")
            print(f"  AT modelo = {d['AT']:.4f}")
            print(f"  s artigo  = {alvo['s']:.4f}")
            print(f"  B modelo  = {d['B']:.4f}")
            print(f"  erro_s = B_modelo - s_artigo = {erro_s:+.4f}")
            print(f"  f artigo  = {alvo['f']:.4f}")
            print(f"  F modelo  = {d['F']:.4f}")
            print(f"  erro_f = F_modelo - f_artigo = {erro_f:+.4f}")
            print(f"  f-s artigo = {alvo['dur']:.4f}")
            print(f"  F-B modelo = {d['dur']:.4f}")
            print(f"  erro_dur = (F-B)_modelo - dur_artigo = {erro_dur:+.4f}")

            print("  --- diagnostico (nao publicado, so decomposicao interna) ---")
            print(f"  P (partida efetiva, inicio[dep0,k]) = {d['P']:.4f}")
            print(f"  R (chegada de volta, inicio[depf,k]) = {d['R']:.4f}")
            print(f"  hB (berco saida+retorno) = {d['hB']:.4f}h | hN (navegacao pura) = {d['hN']:.4f}h "
                  f"| hDP (servico offshore+espera+SET+SP) = {d['hDP']:.4f}h")
            print(f"  hDP decomposto: SET={d['SET']:.4f}h SP={d['SP']:.4f}h "
                  f"servico={d['servico']:.4f}h espera(residual)={d['espera']:.4f}h")
            print(f"  base_loading(hB_saida)={d['hB_saida']:.4f}h | base_unloading(hB_retorno)={d['hB_retorno']:.4f}h")
            print(f"  f1_k (D_v, USD) = {d['f1']:.4f} | f2_k (T_v=F_k-AT_k, [XI PROVISORIO=1]) = {d['f2']:.4f}")

            ok_tempo = abs(erro_s) <= TOL_H and abs(erro_f) <= TOL_H and abs(erro_dur) <= TOL_H
            print(f"  [{'OK' if ok_tempo else 'DIVERGE'}] tolerancia={TOL_H}h")

            linhas_tabela_final.append({
                "alpha": alpha, "psv": nome, "cenario": nome_cenario, "status": status,
                "s_art": alvo["s"], "B_mod": d["B"], "erro_s": erro_s,
                "f_art": alvo["f"], "F_mod": d["F"], "erro_f": erro_f,
                "dur_art": alvo["dur"], "durF_B_mod": d["dur"], "erro_dur": erro_dur,
            })

            # ---- checagem de fechamento: F-B = base_loading+pure_nav+SP+SET+offshore_service+espera+base_unloading
            soma_parcelas = (d["hB_saida"] + d["hN"] + d["SP"] + d["SET"] + d["servico"]
                              + d["espera"] + d["hB_retorno"])
            diff_fechamento = d["dur"] - soma_parcelas
            fecha_ok = abs(diff_fechamento) <= TOL_DECOMP
            linhas_decomposicao.append({
                "alpha": alpha, "psv": nome, "cenario": nome_cenario,
                "base_loading": d["hB_saida"], "pure_navigation": d["hN"],
                "SP": d["SP"], "SET": d["SET"], "offshore_service": d["servico"],
                "espera": d["espera"], "base_unloading": d["hB_retorno"],
                "F_B": d["dur"], "soma_parcelas": soma_parcelas,
                "diff": diff_fechamento, "fecha_ok": fecha_ok,
            })

print("\n\n" + "#" * 100)
print("# TABELA FINAL -- reproducao temporal da Tabela 3 (rotas fixas, xi=1 provisorio, 2 cenarios)")
print("#" * 100)

cab = (f"{'alpha':>6} | {'PSV':>3} | {'cenario':>19} | {'status':>12} | {'s_art':>7} | {'B_mod':>7} | "
       f"{'erro_s':>7} | {'f_art':>7} | {'F_mod':>7} | {'erro_f':>7} | {'dur_art':>7} | {'F-B_mod':>7} | {'erro_dur':>8}")
print(cab)
print("-" * len(cab))


def fmt(v):
    return f"{v:7.2f}" if v is not None else f"{'NA':>7}"


def fmt_err(v):
    return f"{v:+7.2f}" if v is not None else f"{'NA':>7}"


n_ok_tempo = 0
for linha in linhas_tabela_final:
    print(f"{linha['alpha']:>6.2f} | {linha['psv']:>3} | {linha['cenario']:>19} | {str(linha['status']):>12} | "
          f"{fmt(linha['s_art'])} | {fmt(linha['B_mod'])} | {fmt_err(linha['erro_s'])} | "
          f"{fmt(linha['f_art'])} | {fmt(linha['F_mod'])} | {fmt_err(linha['erro_f'])} | "
          f"{fmt(linha['dur_art'])} | {fmt(linha['durF_B_mod'])} | {fmt_err(linha['erro_dur'])}")
    if linha["erro_s"] is not None and linha["erro_f"] is not None and linha["erro_dur"] is not None:
        if abs(linha["erro_s"]) <= TOL_H and abs(linha["erro_f"]) <= TOL_H and abs(linha["erro_dur"]) <= TOL_H:
            n_ok_tempo += 1

print(f"\nLinhas dentro da tolerancia ({TOL_H}h) nos 3 erros simultaneamente: {n_ok_tempo}/{len(linhas_tabela_final)}")

print("\n\n" + "#" * 100)
print("# TABELA DE DECOMPOSICAO -- F-B = base_loading+pure_navigation+SP+SET+offshore_service+espera+base_unloading")
print("#" * 100)

cab2 = (f"{'alpha':>6} | {'PSV':>3} | {'cenario':>19} | {'base_load':>9} | {'pure_nav':>8} | {'SP':>6} | "
        f"{'SET':>6} | {'offshore':>8} | {'espera':>7} | {'base_unl':>8} | {'F-B':>7} | {'fecha?':>6}")
print(cab2)
print("-" * len(cab2))
for linha in linhas_decomposicao:
    status_fecha = "OK" if linha["fecha_ok"] else f"DIFF={linha['diff']:.2e}"
    print(f"{linha['alpha']:>6.2f} | {linha['psv']:>3} | {linha['cenario']:>19} | "
          f"{linha['base_loading']:9.4f} | {linha['pure_navigation']:8.4f} | {linha['SP']:6.4f} | "
          f"{linha['SET']:6.4f} | {linha['offshore_service']:8.4f} | {linha['espera']:7.4f} | "
          f"{linha['base_unloading']:8.4f} | {linha['F_B']:7.4f} | {status_fecha:>6}")

n_fecha_ok = sum(1 for l in linhas_decomposicao if l["fecha_ok"])
print(f"\nLinhas com fechamento F-B=soma das parcelas dentro de {TOL_DECOMP}: "
      f"{n_fecha_ok}/{len(linhas_decomposicao)}")

print("\n[XI PROVISORIO = 1] Esta tabela reproduz APENAS o cronograma temporal de rotas publicadas")
print("FIXAS -- NAO confirma reproducao da solucao/FO otima do artigo (xi_k real desconhecido).")
print("[DEFAULT] silva_sp_arcos_base=True continua sendo o default de metodo_exato_petro/")
print("avaliar_rota_silva2024/custo_rota_silva2024 -- nenhum chamador existente (B&P/Petrobras/Solomon)")
print("foi alterado; SP_SAIDA_BASE_NAO (False) e usada SOMENTE neste script de comparacao.")
