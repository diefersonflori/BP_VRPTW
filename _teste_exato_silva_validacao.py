import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao
from avaliador_rota import AVALIADOR_ROTA_PADRAO
import metodos
import solucao
import avaliador_rota

print("[TEST PATH] metodos =", metodos.__file__)
print("[TEST PATH] solucao =", solucao.__file__)
print("[TEST PATH] avaliador =", avaliador_rota.__file__)

# ============================================================
# TESTE ISOLADO: valida a correcao da validacao pos-hoc do modelo compacto
# Silva (AttributeError em 'validar_ordem_plataformas_silva2024'). NAO altera
# main.py, C++, B&P, estabilizacao. So testa:
#   1) AvaliadorRota.validar_ordem_plataformas_silva2024 (secao 1/2/4)
#   2) Solucao.ordem_plataformas_petro_valida, mode-gated (secao 3/4) -- o
#      MESMO caminho que metodo_exato_petro chama na validacao pos-hoc
#      (metodos.py, linha ~14414-14421)
#   3) avaliar_rota_silva2024 x custo do compacto (secao 5)
#   4) metodo_exato_petro(time_limit=20, considerar_conflito_plataforma=False)
#      (secao 6) -- NAO o B&P.
# ============================================================

ARQ = BASE_DIR / "instancias" / "Petro_instancias" / "14n-2k-6c-008r_ML_silva2024.json"

inst = Instancia()
inst.leitura_petro(str(ARQ))
metod = Metodos(inst)

DEPF = inst.nbn - 1

ROTA_K0 = [0, 8, 1, 15]
ROTA_K1 = [0, 9, 10, 5, 7, 6, 2, 3, 4, 11, 13, 14, 12, 15]

# Valores reportados pelo ultimo run do compacto (secao 5 do pedido) --
# usados como referencia "custo_compacto" original; cross-checados abaixo
# tambem via metodo_exato_petro com fixar_rotas (mesmo padrao ja usado em
# _teste_auditoria_temporal_silva.py) para obter um valor Gurobi PRECISO
# para as MESMAS sequencias, nao so a aproximacao reportada.
CUSTO_COMPACTO_REPORTADO = {0: 33.2258, 1: 96.3238}
TOTAL_REPORTADO = 129.5496


def plataforma_de(inst, no):
    if no == 0 or no == inst.nbn - 1:
        return None
    return AVALIADOR_ROTA_PADRAO.plataforma_petro(inst, no)


def checa_nao_revisita(inst, seq):
    seq_plat = [plataforma_de(inst, no) for no in seq]
    seq_plat = [p for p in seq_plat if p is not None]
    comprimida = []
    for p in seq_plat:
        if not comprimida or comprimida[-1] != p:
            comprimida.append(p)
    return len(comprimida) == len(set(comprimida)), comprimida


def valida_rota(k, seq):
    print("\n" + "#" * 100)
    print(f"# VALIDACAO EXATO -- k={k} seq={seq}")
    print("#" * 100)

    erros = []

    # ---- 1) validacao direta em AvaliadorRota (secao 2) -- NUNCA deve
    # lancar AttributeError; foi exatamente esse o bug relatado. ----
    try:
        ordem_ok, motivo = AVALIADOR_ROTA_PADRAO.validar_ordem_plataformas_silva2024(inst, seq)
    except AttributeError as e:
        erros.append(f"AttributeError em validar_ordem_plataformas_silva2024: {e!r}")
        ordem_ok, motivo = None, f"EXCECAO:{e!r}"

    # ---- 2) o MESMO caminho que metodo_exato_petro usa na validacao pos-hoc
    # (Solucao.ordem_plataformas_petro_valida, mode-gated -- secao 3) ----
    sol_dummy = Solucao(inst.nbv, inst.nbn)
    try:
        ordem_ok_sol = sol_dummy.ordem_plataformas_petro_valida(inst, seq)
        excecao_sol = None
    except AttributeError as e:
        ordem_ok_sol = None
        excecao_sol = e
        erros.append(f"AttributeError em Solucao.ordem_plataformas_petro_valida: {e!r}")

    # ---- 3) avaliar_rota_silva2024 (oraculo fisico/custo oficial) ----
    resultado = metod.avaliar_rota_silva2024(inst, k, seq, diagnostico=True)
    viavel = resultado["viavel"]
    custo_avaliador = resultado.get("custo")
    B = resultado.get("B")
    P = resultado.get("P")
    R = resultado.get("R")
    F = resultado.get("F")

    print("\n[SILVA VALIDACAO EXATO]")
    print(f"k={k}")
    print(f"seq={seq}")
    print(f"ordem_plataformas_valida={ordem_ok}")
    print(f"motivo={motivo}")
    print(f"avaliar_rota_silva_viavel={viavel} (motivo_avaliador={resultado.get('motivo')})")
    print(f"custo_avaliador={custo_avaliador}")
    print(f"B={B}")
    print(f"P={P}")
    print(f"R={R}")
    print(f"F={F}")

    print(f"\n[CHECAGEM ADICIONAL] Solucao.ordem_plataformas_petro_valida (caminho real de "
          f"metodo_exato_petro) -> {ordem_ok_sol} (excecao={excecao_sol!r})")

    sem_revisita, comprimida = checa_nao_revisita(inst, seq)
    print(f"[CHECAGEM ADICIONAL] sem_revisita_plataforma={sem_revisita} "
          f"(sequencia comprimida de plataformas={comprimida})")

    if not ordem_ok:
        erros.append(f"ordem_plataformas_valida=False (motivo={motivo}) -- rota deveria ser valida")
    if not viavel:
        erros.append(f"avaliar_rota_silva2024 nao-viavel: {resultado.get('motivo')}")
    if not sem_revisita:
        erros.append(f"rota REVISITA uma plataforma (comprimida={comprimida})")
    if ordem_ok_sol is not True:
        erros.append(f"Solucao.ordem_plataformas_petro_valida deveria retornar True, veio {ordem_ok_sol}")

    if erros:
        print("\n[VALIDACAO][FALHOU]")
        for e in erros:
            print(f"  - {e}")
    else:
        print("\n[VALIDACAO][OK] nenhum erro -- sem AttributeError, rota viavel e sem revisita")

    return dict(k=k, seq=seq, ordem_ok=ordem_ok, viavel=viavel, custo_avaliador=custo_avaliador,
                B=B, P=P, R=R, F=F, erros=erros)


ok_geral = True

res0 = valida_rota(0, ROTA_K0)
ok_geral &= (not res0["erros"])

res1 = valida_rota(1, ROTA_K1)
ok_geral &= (not res1["erros"])


# ============================================================
# SECAO 5: custo_compacto (reportado + cross-check Gurobi via fixar_rotas)
# x avaliar_rota_silva2024 (custo_avaliador), diferenca sem mascarar.
# ============================================================

print("\n\n" + "#" * 100)
print("# SECAO 5 -- CUSTO COMPACTO x avaliar_rota_silva2024")
print("#" * 100)

TOL = 1e-6
erros_custo = []

print("\n[INFORMATIVO -- valor REPORTADO pelo ultimo run do compacto, so 4 casas decimais]")
print("(NAO e usado como referencia de PASS/FAIL -- e apenas o texto impresso de uma rodada")
print(" anterior, arredondado; a referencia de verdade e o cross-check Gurobi abaixo, com")
print(" precisao total, via fixar_rotas na MESMA rota.)")
custo_avaliador_por_k = {0: res0["custo_avaliador"], 1: res1["custo_avaliador"]}
for k in (0, 1):
    cc = CUSTO_COMPACTO_REPORTADO[k]
    ca = custo_avaliador_por_k[k]
    if ca is None:
        print(f"k={k} | custo_compacto(reportado)={cc:.6f} | custo_avaliador=None (rota inviavel)")
        continue
    diff = abs(cc - ca)
    print(f"k={k} | custo_compacto(reportado)={cc:.6f} | custo_avaliador={ca:.6f} | diferenca={diff:.6e} "
          f"(esperado ~1e-5, e so arredondamento do texto reportado)")

print("\n[COMPARACAO -- cross-check Gurobi, fixar_rotas (mesma rota, so resolve horarios/berco) -- "
      "REFERENCIA de PASS/FAIL, precisao total]")
sol_fix = Solucao(inst.nbv, inst.nbn)
ok_fix = metod.metodo_exato_petro(
    inst, sol_fix, time_limit=60, threads=4, salvar_modelo=False, diagnostico=False,
    fixar_rotas={0: ROTA_K0, 1: ROTA_K1}, considerar_conflito_plataforma=True,
)
print(f"\n[FIXAR_ROTAS] ok={ok_fix} status={getattr(sol_fix, 'exato_petro_status', None)} "
      f"consistente={getattr(sol_fix, 'exato_petro_consistente', None)}")

if ok_fix and getattr(sol_fix, "exato_petro_rotas_brutas", None):
    for k in (0, 1):
        custo_gurobi_fix = sol_fix.exato_petro_rotas_brutas[k]["custo"][0]
        ca = custo_avaliador_por_k[k]
        if ca is None:
            continue
        diff = abs(custo_gurobi_fix - ca)
        print(f"k={k} | custo_compacto(fixar_rotas, Gurobi)={custo_gurobi_fix:.6f} | "
              f"custo_avaliador={ca:.6f} | diferenca={diff:.6e}")
        if diff > TOL:
            erros_custo.append(f"k={k}: diferenca {diff:.6e} > tolerancia {TOL:.1e} entre custo_compacto "
                                f"(fixar_rotas Gurobi) e custo_avaliador")
    total_gurobi_fix = sum(sol_fix.exato_petro_rotas_brutas[k]["custo"][0] for k in (0, 1))
    print(f"TOTAL | custo_compacto(fixar_rotas, Gurobi)={total_gurobi_fix:.6f}")
else:
    erros_custo.append("fixar_rotas nao retornou solucao consistente -- sem referencia de "
                        "precisao total para comparar custo_avaliador")
    print("[AVISO] fixar_rotas nao retornou solucao consistente -- sem referencia Gurobi de "
          "precisao total para este run")

if erros_custo:
    print("\n[VALIDACAO SECAO 5][FALHOU]")
    for e in erros_custo:
        print(f"  - {e}")
else:
    print("\n[VALIDACAO SECAO 5][OK] custo_compacto e custo_avaliador batem dentro da tolerancia")
ok_geral &= (not erros_custo)


# ============================================================
# SECAO 6: SO ENTAO rodar o compacto de verdade (nao B&P), time_limit=20s,
# considerar_conflito_plataforma=False.
# ============================================================

print("\n\n" + "#" * 100)
print("# SECAO 6 -- METODO EXATO PETRO (compacto), time_limit=20s, "
      "considerar_conflito_plataforma=False")
print("#" * 100)

sol_compacto = Solucao(inst.nbv, inst.nbn)
try:
    ok_compacto = metod.metodo_exato_petro(
        inst, sol_compacto, time_limit=20, threads=4, salvar_modelo=False, diagnostico=True,
        considerar_conflito_plataforma=False,
    )
    excecao_compacto = None
except AttributeError as e:
    ok_compacto = False
    excecao_compacto = e

print(f"\n[COMPACTO 20s] ok={ok_compacto} excecao={excecao_compacto!r}")
print(f"[COMPACTO 20s] status={getattr(sol_compacto, 'exato_petro_status', None)} "
      f"tem_solucao={getattr(sol_compacto, 'exato_petro_tem_solucao', None)} "
      f"otimo={getattr(sol_compacto, 'exato_petro_otimo', None)} "
      f"consistente={getattr(sol_compacto, 'exato_petro_consistente', None)} "
      f"gap={getattr(sol_compacto, 'exato_petro_gap', None)}")
print(f"[COMPACTO 20s] custo(FO)={getattr(sol_compacto, 'custo', None)}")

erros_compacto = []
if excecao_compacto is not None:
    erros_compacto.append(f"AttributeError durante metodo_exato_petro: {excecao_compacto!r}")
if getattr(sol_compacto, "exato_petro_tem_solucao", False) and not getattr(sol_compacto, "exato_petro_consistente", False):
    erros_compacto.append("incumbente encontrado mas exato_petro_consistente=False "
                           "(validacao pos-hoc rejeitou alguma rota -- ver [EXATO_PETRO] acima)")

if erros_compacto:
    print("\n[VALIDACAO SECAO 6][FALHOU]")
    for e in erros_compacto:
        print(f"  - {e}")
else:
    print("\n[VALIDACAO SECAO 6][OK] sem AttributeError; validacao pos-hoc "
          "funcionou para o(s) incumbente(s) encontrado(s)")
ok_geral &= (not erros_compacto)


print("\n\n" + "=" * 100)
print(f"[RESULTADO FINAL] {'TODOS OS CASOS OK' if ok_geral else 'HOUVE FALHAS -- ver acima'}")
print("=" * 100)
