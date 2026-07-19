import sys
import time
from pathlib import Path

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao
from teste_ab_pricing_petro import montar_casos_pi, custo_reduzido_real, validar_coluna


INSTANCIA = "instancias/instancias_petro_geradas/petro_campos_C1_nucleo_atual_15ped.json"

TIMEOUT_BID = 5
TIMEOUT_PD = 15

MAX_LABELS_BID = 200
MAX_COMBINACOES_BID = 200_000

TOL_RC = 1e-3
EPS_NEGATIVO = 1e-6


def carregar_vrptw_pd():
    base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON" / "x64" / "Release"
    sys.path.insert(0, str(base))

    import vrptw_pd

    return vrptw_pd


def verificar_coluna(inst, sol, metod, k, rota, rc, pi, nome_metodo):
    problemas = []

    if rota is None:
        return problemas

    if rc is None:
        problemas.append(f"{nome_metodo} retornou rota sem custo reduzido")
        return problemas

    ok, motivo = validar_coluna(inst, sol, metod, k, rota)

    if not ok:
        problemas.append(f"rota {nome_metodo} inviavel: {motivo}")

    rc_calculado = custo_reduzido_real(inst, k, rota, pi, 0.0)

    if abs(rc_calculado - float(rc)) > TOL_RC:
        problemas.append(f"rc {nome_metodo} inconsistente: retornado={float(rc):.6f}, calculado={rc_calculado:.6f}")

    if float(rc) >= -EPS_NEGATIVO:
        problemas.append(f"{nome_metodo} retornou coluna sem rc negativo: {float(rc):.6f}")

    return problemas


def main():
    vrptw_pd = carregar_vrptw_pd()

    funcoes_necessarias = ["sub_prog_din_bidirecional_petro", "sub_prog_din_petro"]

    for nome_funcao in funcoes_necessarias:
        if not hasattr(vrptw_pd, nome_funcao):
            print(f"[ERRO] {nome_funcao} ausente; recompile o projeto C++ em Release.")
            return

    print("[OK] modulo:", vrptw_pd.__file__)

    inst = Instancia()
    inst.leitura_petro(INSTANCIA)

    metod = Metodos(inst)
    sol = Solucao(inst.nbv, inst.nbn)

    total = 0
    pass_count = 0
    inconclusivos = 0
    falhas = 0
    bid_encontrou = 0
    pd_encontrou = 0
    timeout_bid_total = 0
    timeout_pd_total = 0

    print()
    print(f"{'k':>2} | {'pi':<18} | {'bid(s)':>8} | {'pd(s)':>8} | {'status':<8} | detalhe")
    print("-" * 120)

    for k in range(inst.nbv):
        for nome_pi, pi in montar_casos_pi(inst.nbcd):
            total += 1

            t0 = time.time()
            rota_bid, rc_bid = metod.SUB_PROG_DIN_BIDIRECIONAL_PETRO_CPP(inst, pi, 0.0, k, timeout_s=TIMEOUT_BID, max_labels_por_no=MAX_LABELS_BID, max_combinacoes=MAX_COMBINACOES_BID)
            tempo_bid = time.time() - t0
            timeout_bid = bool(getattr(metod, "_ultimo_timeout_cpp", False))

            if timeout_bid:
                timeout_bid_total += 1

            t0 = time.time()
            rota_pd, rc_pd = metod.SUB_PROG_DIN_PETRO_CPP(inst, pi, 0.0, k, timeout_s=TIMEOUT_PD)
            tempo_pd = time.time() - t0
            timeout_pd = bool(getattr(metod, "_ultimo_timeout_cpp", False))

            if timeout_pd:
                timeout_pd_total += 1

            problemas = []

            problemas.extend(verificar_coluna(inst, sol, metod, k, rota_bid, rc_bid, pi, "BID"))
            problemas.extend(verificar_coluna(inst, sol, metod, k, rota_pd, rc_pd, pi, "PD"))

            if rota_bid is not None:
                bid_encontrou += 1

            if rota_pd is not None:
                pd_encontrou += 1

            # A comparação só é válida quando a PD terminou normalmente.
            if rota_bid is not None and rota_pd is not None and not timeout_pd:
                if float(rc_bid) < float(rc_pd) - TOL_RC:
                    problemas.append(f"BID encontrou rc melhor que a PD completa: BID={float(rc_bid):.6f}, PD={float(rc_pd):.6f}")

            if problemas:
                status = "FAIL"
                falhas += 1
                detalhe = "; ".join(problemas)

            elif rota_bid is not None:
                status = "PASS"
                pass_count += 1

                detalhe = f"BID rc={float(rc_bid):.3f}"

                if timeout_bid:
                    detalhe += " | BID TIMEOUT"

                if rota_pd is not None:
                    detalhe += f" | PD rc={float(rc_pd):.3f}"
                elif timeout_pd:
                    detalhe += " | PD TIMEOUT"
                else:
                    detalhe += " | PD concluiu sem coluna"

            elif rota_pd is not None:
                status = "PASS"
                pass_count += 1

                detalhe = f"BID sem coluna | PD rc={float(rc_pd):.3f}"

                if timeout_bid:
                    detalhe = f"BID TIMEOUT | PD rc={float(rc_pd):.3f}"

            elif timeout_pd:
                status = "INC"
                inconclusivos += 1

                if timeout_bid:
                    detalhe = "BID TIMEOUT | PD TIMEOUT"
                else:
                    detalhe = "BID sem coluna | PD TIMEOUT"

            else:
                status = "PASS"
                pass_count += 1

                if timeout_bid:
                    detalhe = "BID TIMEOUT | PD concluiu sem coluna"
                else:
                    detalhe = "ambos concluiram sem coluna"

            print(f"{k:>2} | {nome_pi:<18} | {tempo_bid:8.3f} | {tempo_pd:8.3f} | {status:<8} | {detalhe}")

    print("-" * 120)
    print(f"Total={total} | PASS={pass_count} | INC={inconclusivos} | FAIL={falhas}")
    print(f"BID encontrou={bid_encontrou} | PD encontrou={pd_encontrou}")
    print(f"Timeout BID={timeout_bid_total} | Timeout PD={timeout_pd_total}")

    if falhas > 0:
        print("[RESULTADO] Existem falhas de viabilidade ou consistencia.")
    elif inconclusivos > 0:
        print("[RESULTADO] Bidirecional aprovado, mas alguns casos ficaram inconclusivos porque a PD completa atingiu timeout.")
    else:
        print("[RESULTADO] Todos os casos foram concluídos sem falhas.")


if __name__ == "__main__":
    main()