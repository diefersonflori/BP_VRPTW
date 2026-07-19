"""Teste A/B: SUB_PROG_DIN_PETRO (Python) vs SUB_PROG_DIN_PETRO_CPP (vrptw_pd.sub_prog_din_petro).

Compara, para k em {0,1,2} e 5 vetores de pi, se as duas implementacoes do
pricing exato Petro concordam. Ambas agora varrem a busca completa e
retornam a MELHOR coluna (menor custo reduzido), entao devem empatar em rc
sempre que as duas colunas forem viaveis e consistentes.

Para pegar bugs de matematica independentemente da politica de retorno, a
comparacao (a) recalcula o custo reduzido de cada coluna de forma
independente (soma de arcos da matriz/velocidade, menos pi das orders, menos
sigma_k) e confere com o rc reportado; (b) valida a viabilidade da coluna via
sol.viavel_cargas_petro (deck/diesel/agua) e via simulacao de janelas
(inicio + servico dentro de alguma janela, mesma regra do pricing).

Se o modulo C++ compilado ainda nao tiver sub_prog_din_petro (ou tiver a
assinatura antiga, sem d_deck/b_deck), avisa e sai sem erro (exit code 0) --
nao ha nada para comparar ainda.
"""
import sys
import time
import random
from pathlib import Path

from instancia import Instancia
from metodos import Metodos
from solucao import Solucao

INSTANCIA = "instancias/Petro_instancias/10n-1k-3c-1r_testeUSP_v33.json"

TOL_RC = 1e-3


def carregar_vrptw_pd():
    base = Path(__file__).resolve().parent / "PD_PARA_PYTHON" / "PD_PARA_PYTHON"
    for sub in ("x64/Release", "x64/Debug"):
        p = base / sub
        if p.exists():
            sys.path.append(str(p))
    try:
        import vrptw_pd
        return vrptw_pd
    except ImportError:
        return None


def montar_casos_pi(nbcd):
    casos = [
        ("zeros", [0.0] * nbcd),
        ("uniforme_100000", [100000.0] * nbcd),
    ]
    for seed in (1, 2, 3):
        rnd = random.Random(seed)
        casos.append((f"aleatorio_seed{seed}", [rnd.uniform(0.0, 50000.0) for _ in range(nbcd)]))
    return casos


def custo_reduzido_real(inst, k, rota, pi, sigma_k):
    """Recalcula o rc de forma independente: soma de arcos (matriz_distancia /
    velocidade) menos pi das orders visitadas menos sigma_k (uma unica vez,
    pelo fechamento no deposito)."""
    seq = rota["clientes"]
    velocidade = inst.veiculos[k].velocidade
    custo_arcos = sum(
        inst.matriz_distancia[seq[t]][seq[t + 1]] / velocidade
        for t in range(len(seq) - 1)
    )
    soma_pi = sum(float(pi[no - 1]) for no in seq if 1 <= no <= inst.nbcd)
    return custo_arcos - soma_pi - float(sigma_k)


def validar_janelas(inst, metod, k, rota):
    """Simula a chegada nó a nó e confere: inicio_servico + servico <= due,
    para alguma janela (mesma regra usada no pricing exato)."""
    seq = rota["clientes"]
    velocidade = inst.veiculos[k].velocidade
    no0 = inst.noh[seq[0]]
    tempo = no0.READY_TIME[0] if no0.READY_TIME else 0.0
    for pos in range(1, len(seq)):
        i, j = seq[pos - 1], seq[pos]
        serv_i = inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0.0
        viagem = inst.matriz_distancia[i][j] / velocidade
        chegada_bruta = tempo + serv_i + viagem
        inicio_j = metod.menor_inicio_viavel_mtw(
            inst.noh[j], chegada_bruta, exige_termino_janela=True
        )
        if inicio_j is None:
            return False, f"janela violada no arco ({i},{j})"
        tempo = inicio_j
    return True, "ok"


def validar_coluna(inst, sol, metod, k, rota):
    if not sol.viavel_cargas_petro(inst, k, rota["clientes"]):
        return False, "cap_deck/diesel/agua"
    return validar_janelas(inst, metod, k, rota)


def comparar(inst, sol, metod, k, rota_py, rc_py, rota_cpp, rc_cpp, pi, sigma_k):
    if rota_py is None and rota_cpp is None:
        return "PASS", "ambos sem coluna melhorante"
    if rota_py is None or rota_cpp is None:
        return "FAIL", f"um retornou None (py={rota_py is not None}, cpp={rota_cpp is not None})"

    problemas = []

    rc_py_calc = custo_reduzido_real(inst, k, rota_py, pi, sigma_k)
    if abs(rc_py_calc - float(rc_py)) > TOL_RC:
        problemas.append(
            f"[RC INCONSISTENTE] py: reportado={float(rc_py):.6f} recalculado={rc_py_calc:.6f}"
        )

    rc_cpp_calc = custo_reduzido_real(inst, k, rota_cpp, pi, sigma_k)
    if abs(rc_cpp_calc - float(rc_cpp)) > TOL_RC:
        problemas.append(
            f"[RC INCONSISTENTE] cpp: reportado={float(rc_cpp):.6f} recalculado={rc_cpp_calc:.6f}"
        )

    ok_py, motivo_py = validar_coluna(inst, sol, metod, k, rota_py)
    if not ok_py:
        problemas.append(f"[COLUNA INVIAVEL] py: {motivo_py}")

    ok_cpp, motivo_cpp = validar_coluna(inst, sol, metod, k, rota_cpp)
    if not ok_cpp:
        problemas.append(f"[COLUNA INVIAVEL] cpp: {motivo_cpp}")

    if problemas:
        return "FAIL", "; ".join(problemas)

    if abs(float(rc_py) - float(rc_cpp)) < TOL_RC:
        return "PASS", f"ambas viaveis e consistentes, rc empatado ({float(rc_py):.6f} vs {float(rc_cpp):.6f})"

    return "FAIL", f"rc divergente ({float(rc_py):.6f} vs {float(rc_cpp):.6f})"


def main():
    vrptw_pd = carregar_vrptw_pd()
    if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_petro"):
        print("[TESTE A/B] vrptw_pd.sub_prog_din_petro indisponivel "
              "(modulo C++ ainda nao recompilado com essa funcao) -- nada a comparar.")
        sys.exit(0)

    print(f"[TESTE A/B] vrptw_pd carregado de: {getattr(vrptw_pd, '__file__', '?')}")

    inst = Instancia()
    inst.leitura_petro(INSTANCIA)
    metod = Metodos(inst)
    sol = Solucao(inst.nbv, inst.nbn)

    sigma_k = 0.0
    casos_pi = montar_casos_pi(inst.nbcd)

    linhas = []
    speedups = []

    for k in range(3):
        for nome_pi, pi in casos_pi:
            t0 = time.time()
            rota_py, rc_py = metod.SUB_PROG_DIN_PETRO(inst, pi, sigma_k, k)
            t_py = time.time() - t0

            t0 = time.time()
            try:
                rota_cpp, rc_cpp = metod.SUB_PROG_DIN_PETRO_CPP(inst, pi, sigma_k, k)
            except TypeError as e:
                # .pyd ainda com a assinatura antiga (d unico de conves, sem
                # d_deck/b_deck) -- modulo C++ nao recompilado com a regra
                # nova de pico de ocupacao. Nada a comparar ainda.
                print("[TESTE A/B] vrptw_pd.sub_prog_din_petro com assinatura antiga "
                      "(sem d_deck/b_deck) -- modulo C++ ainda nao recompilado com a "
                      f"regra nova de conves. Detalhe: {e}")
                sys.exit(0)
            t_cpp = time.time() - t0

            status, detalhe = comparar(inst, sol, metod, k, rota_py, rc_py, rota_cpp, rc_cpp, pi, sigma_k)
            speedup = (t_py / t_cpp) if t_cpp > 0 else float("inf")
            if status == "PASS":
                speedups.append(speedup)

            linhas.append((k, nome_pi, status, t_py, t_cpp, speedup, detalhe))

    print(f"{'k':>2} | {'pi':<18} | {'status':<6} | {'t_py(s)':>9} | {'t_cpp(s)':>9} | {'speedup':>9} | detalhe")
    print("-" * 110)
    for k, nome_pi, status, t_py, t_cpp, speedup, detalhe in linhas:
        print(f"{k:>2} | {nome_pi:<18} | {status:<6} | {t_py:9.4f} | {t_cpp:9.4f} | {speedup:8.2f}x | {detalhe}")

    n_fail = sum(1 for l in linhas if l[2] == "FAIL")
    print("-" * 110)
    if speedups:
        print(f"Speedup medio (casos PASS): {sum(speedups) / len(speedups):.2f}x")
    print(f"Total: {len(linhas)} casos | PASS={len(linhas) - n_fail} | FAIL={n_fail}")

    if n_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
