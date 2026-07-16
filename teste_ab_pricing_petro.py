"""Teste A/B: SUB_PROG_DIN_PETRO (Python) vs SUB_PROG_DIN_PETRO_CPP (vrptw_pd.sub_prog_din_petro).

Compara, para k em {0,1,2} e 5 vetores de pi, se as duas implementacoes do
pricing exato Petro concordam (mesma rota, ou custo reduzido empatado quando
a rota empata com desempate diferente) e mede o speedup do C++ sobre o Python.

Se o modulo C++ compilado ainda nao tiver sub_prog_din_petro, avisa e sai sem
erro (exit code 0) -- nao ha nada para comparar ainda.
"""
import sys
import time
import random
from pathlib import Path

from instancia import Instancia
from metodos import Metodos

INSTANCIA = "instancias/Petro_instancias/10n-1k-3c-1r_testeUSP_v33.json"


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


def comparar(rota_py, rc_py, rota_cpp, rc_cpp):
    if rota_py is None and rota_cpp is None:
        return "PASS", "ambos sem coluna melhorante"
    if rota_py is None or rota_cpp is None:
        return "FAIL", f"um retornou None (py={rota_py is not None}, cpp={rota_cpp is not None})"
    if rota_py["clientes"] == rota_cpp["clientes"]:
        return "PASS", "mesma rota"
    if abs(float(rc_py) - float(rc_cpp)) < 1e-4:
        return "PASS", f"rotas diferentes, rc empatado ({float(rc_py):.4f} vs {float(rc_cpp):.4f})"
    return "FAIL", f"rc divergente ({float(rc_py):.4f} vs {float(rc_cpp):.4f})"


def main():
    vrptw_pd = carregar_vrptw_pd()
    if vrptw_pd is None or not hasattr(vrptw_pd, "sub_prog_din_petro"):
        print("[TESTE A/B] vrptw_pd.sub_prog_din_petro indisponivel "
              "(modulo C++ ainda nao recompilado com essa funcao) -- nada a comparar.")
        sys.exit(0)

    inst = Instancia()
    inst.leitura_petro(INSTANCIA)
    metod = Metodos(inst)

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
            rota_cpp, rc_cpp = metod.SUB_PROG_DIN_PETRO_CPP(inst, pi, sigma_k, k)
            t_cpp = time.time() - t0

            status, detalhe = comparar(rota_py, rc_py, rota_cpp, rc_cpp)
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
