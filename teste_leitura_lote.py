import glob
from instancia import Instancia

arquivos = sorted(glob.glob("instancias/instancias_petro_geradas/*.json"))
print(f"{len(arquivos)} instancias encontradas\n")

resumo = []
for arq in arquivos:
    print("#" * 78)
    try:
        inst = Instancia()
        inst.leitura_petro(arq)
        dp = inst.dados_petro
        resumo.append((arq.split("/")[-1].split("\\")[-1], inst.nbcd, inst.nbv,
                       sum(dp["demanda"]), inst.veiculos[0].capacidade, "OK"))
    except Exception as e:
        resumo.append((arq.split("/")[-1].split("\\")[-1], "-", "-", "-", "-",
                       f"ERRO: {e}"))

print("\n" + "=" * 78)
print("RESUMO DO LOTE")
for nome, nbcd, nbv, dem, cap, status in resumo:
    print(f"{nome:48s} orders={nbcd!s:>3} navios={nbv!s:>2} "
          f"dem_deck={dem!s:>6} cap={cap!s:>4} {status}")