import math

# ============================================================
# Investigacao ISOLADA de Delta_cicj (distancia) para os 6 arcos criticos
# que diferem entre as rotas M de alpha=0 e alpha=0.50 (rotas Tabela 3,
# Silva et al. 2024). NAO otimiza nada, NAO altera metodos.py/avaliador/
# B&P/instancia -- so LE o arquivo ORIGINAL dos autores e recalcula
# distancia/tempo com o metodo Haversine ATUALMENTE usado pelo repo
# (instancia.py:haversine_km, R=6371), para reproduzir o residuo
# encontrado na auditoria temporal anterior.
#
# Arquivo fonte: transformador_instancias_silva/arquivosconvertersilva/
# 14n-2k-6c-008r_ML.txt (arquivo ORIGINAL dos autores, NAO a conversao
# JSON). Confirmado por leitura direta do JSON de producao
# (instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json) que as
# coordenadas la usadas SAO EXATAMENTE estas do .txt (nenhuma correcao/
# coordenada "real" de Macae foi aplicada em nenhuma etapa do pipeline
# atual) -- ver secao de confirmacao impressa abaixo.
# ============================================================

ARQ_TXT = r"transformador_instancias_silva\arquivosconvertersilva\14n-2k-6c-008r_ML.txt"


def parse_coordenadas(caminho):
    """Le a secao 'Clients information' do arquivo ORIGINAL dos autores.
    Colunas: ID LON LAT DCP DCD DD WD ... (so ID/LON/LAT sao usados aqui).
    ID 0 = BASE; ID 1..6 = PLAT_1..PLAT_6 (mapeamento direto, confirmado
    contra o JSON de producao: PLAT_N_order_* sempre usa o client ID N)."""
    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    inicio = None
    for idx, linha in enumerate(linhas):
        if linha.strip().startswith("ID") and "LON" in linha and "LAT" in linha:
            inicio = idx + 1
            break
    if inicio is None:
        raise ValueError("Secao 'Clients information' (cabecalho ID LON LAT ...) nao encontrada no arquivo")

    coords = {}
    for linha in linhas[inicio:]:
        linha = linha.strip()
        if not linha:
            break
        partes = linha.split()
        cid = int(partes[0])
        lon = float(partes[1])
        lat = float(partes[2])
        coords[cid] = (lat, lon)
    return coords


def parse_veiculo_M(caminho):
    """Le a secao 'Vehicles information' e retorna VL/VH/threshold do
    veiculo M (ID 0 no arquivo original -- VL=9.4 e o menor entre os dois
    veiculos, mesma identificacao usada em toda a auditoria anterior)."""
    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    threshold = None
    for linha in linhas:
        if linha.strip().startswith("Vehicles") and "Threshold" in linha:
            continue
    # "Vehicles\tThreshold distance" seguido de "2\t18.0" na linha seguinte
    for idx, linha in enumerate(linhas):
        if linha.strip().startswith("Vehicles") and "Threshold distance" in linha:
            threshold = float(linhas[idx + 1].split()[1])
            break

    inicio = None
    for idx, linha in enumerate(linhas):
        if linha.strip().startswith("ID") and "VL" in linha and "VH" in linha:
            inicio = idx + 1
            break
    partes = linhas[inicio].split()
    # ID DC D W DWT VL VH FCA FCB FCN FCS SPO TRI TDL ETR
    vl = float(partes[5])
    vh = float(partes[6])
    return vl, vh, threshold


def haversine_km(lat1, lon1, lat2, lon2):
    """IDENTICA a instancia.py:haversine_km (R=6371) -- NAO reimplementada
    com formula diferente, so copiada aqui para uso isolado sem depender
    de carregar Instancia()/leitura_petro (que exigiria o JSON, nao o .txt
    original)."""
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    l1 = math.radians(lat1)
    l2 = math.radians(lat2)
    a = math.sin(dLat / 2.0) ** 2 + math.sin(dLon / 2.0) ** 2 * math.cos(l1) * math.cos(l2)
    return 2.0 * 6371.0 * math.asin(math.sqrt(a))


def tempo_navegacao_h(dist_km, vl, vh, threshold):
    """IDENTICA a Metodos.tempo_navegacao_silva (metodos.py) / nav_pura_seg
    (avaliar_rota_silva2024): piecewise continuo d<=threshold: d/VL;
    d>threshold: threshold/VL+(d-threshold)/VH."""
    if dist_km <= threshold:
        return dist_km / vl
    return threshold / vl + (dist_km - threshold) / vh


NOME = {0: "BASE", 1: "PLAT_1", 2: "PLAT_2", 3: "PLAT_3", 4: "PLAT_4", 5: "PLAT_5", 6: "PLAT_6"}

ARCOS_ALPHA0 = [("BASE-P1", 0, 1), ("P1-P5", 1, 5), ("P6-BASE", 6, 0)]
ARCOS_ALPHA050 = [("BASE-P5", 0, 5), ("P6-P1", 6, 1), ("P1-BASE", 1, 0)]


print("#" * 100)
print("# INVESTIGACAO Delta_cicj (distancia) -- 6 arcos criticos M (alpha=0 vs alpha=0.50)")
print(f"# Fonte: {ARQ_TXT} (arquivo ORIGINAL dos autores, coordenadas cruas)")
print("#" * 100)

coords = parse_coordenadas(ARQ_TXT)
vl, vh, threshold = parse_veiculo_M(ARQ_TXT)

print("\n" + "-" * 100)
print("SECAO 1 -- CONFIRMACAO DE DADOS (coordenadas cruas lidas do .txt original)")
print("-" * 100)
for cid in sorted(coords):
    lat, lon = coords[cid]
    print(f"  {NOME.get(cid, cid):8s} (id={cid}): LAT={lat:.3f} LON={lon:.3f}")
print(f"\n  Veiculo M: VL={vl} km/h  VH={vh} km/h  threshold={threshold} km")
print("\n  [CONFIRMACAO] Estas coordenadas foram comparadas manualmente contra")
print("  instancias/Petro_instancias/14n-2k-6c-008r_ML_silva2024.json (campos")
print("  latitude/longitude de ordersData e supplyBasesData) -- SAO IDENTICAS,")
print("  ate a 3a casa decimal, para BASE e todas as 6 plataformas. Nenhuma")
print("  coordenada 'real'/corrigida de Macae esta em uso no pipeline atual.")


def imprime_arco(tag, i, j):
    lat_i, lon_i = coords[i]
    lat_j, lon_j = coords[j]
    d = haversine_km(lat_i, lon_i, lat_j, lon_j)
    t_h = tempo_navegacao_h(d, vl, vh, threshold)
    print(f"\n  [{tag}] {NOME[i]}({i}) -> {NOME[j]}({j})")
    print(f"    origem:  LAT={lat_i:.3f} LON={lon_i:.3f}")
    print(f"    destino: LAT={lat_j:.3f} LON={lon_j:.3f}")
    print(f"    distancia_km (Haversine R=6371) = {d:.6f}")
    print(f"    tempo_navegacao N_ijk (VL={vl}/VH={vh}/threshold={threshold}) = {t_h:.6f}h")
    return d, t_h


print("\n" + "-" * 100)
print("SECAO 2+3 -- OS SEIS ARCOS CRITICOS (arcos que NAO se cancelam entre as duas rotas)")
print("-" * 100)

print("\n--- arcos exclusivos de alpha=0 (BASE-P1-P5-P3-P2-P4-P6-BASE) ---")
soma_alpha0 = 0.0
dists_alpha0 = []
for tag, i, j in ARCOS_ALPHA0:
    d, t_h = imprime_arco(tag, i, j)
    dists_alpha0.append((tag, d, t_h))
    soma_alpha0 += t_h

print("\n--- arcos exclusivos de alpha=0.50 (BASE-P5-P3-P2-P4-P6-P1-BASE) ---")
soma_alpha050 = 0.0
dists_alpha050 = []
for tag, i, j in ARCOS_ALPHA050:
    d, t_h = imprime_arco(tag, i, j)
    dists_alpha050.append((tag, d, t_h))
    soma_alpha050 += t_h

delta = soma_alpha050 - soma_alpha0

print("\n" + "-" * 100)
print("SECAO 4 -- REPRODUCAO DO HAVERSINE ATUAL (R=6371) vs NUMEROS DA AUDITORIA ANTERIOR")
print("-" * 100)
print(f"  soma_alpha0   = {soma_alpha0:.6f}h  (esperado ~= 29.886543h)")
print(f"  soma_alpha050 = {soma_alpha050:.6f}h  (esperado ~= 30.235122h)")
print(f"  delta         = {delta:+.6f}h  (esperado ~= +0.348579h)")

TOL = 1e-3
ok_a0 = abs(soma_alpha0 - 29.886543) <= TOL
ok_a050 = abs(soma_alpha050 - 30.235122) <= TOL
ok_delta = abs(delta - 0.348579) <= TOL
print(f"\n  reproduz soma_alpha0   = {ok_a0}")
print(f"  reproduz soma_alpha050 = {ok_a050}")
print(f"  reproduz delta         = {ok_delta}")

if not (ok_a0 and ok_a050 and ok_delta):
    print("\n  [PARADO] A reproducao dos numeros da auditoria anterior FALHOU -- ver")
    print("  secao 6 do pedido do usuario ('Se não reproduzir, pare.'). NAO prosseguindo")
    print("  com a investigacao da formula dos autores ate esta divergencia ser entendida.")
else:
    print("\n  [OK] Reproducao confirmada -- o metodo Haversine atual (R=6371) e a MESMA fonte")
    print("  do residuo de +0.348579h encontrado na auditoria temporal anterior.")

    print("\n" + "-" * 100)
    print("SECAO 5 -- BUSCA PELA FORMULA ORIGINAL DOS AUTORES (Delta_cicj)")
    print("-" * 100)
    print("""
  Termos pesquisados no repositorio inteiro (Grep case-insensitive, todos os
  arquivos, incluindo copias em worktrees/pastas de backup):
    distance, haversine, great circle, geodesic, latitude, longitude,
    Delta_c, get_distance, nautical, earth radius, spherical, UTM,
    vincenty, geopy, 6371

  Resultados:
  - 'get_haversine_distance' aparece SOMENTE em instancia.py (comentario de
    quem escreveu a funcao, dizendo que replica uma funcao C++ de mesmo
    nome) e em DIAGNOSTICO_SILVA2024.md (registro do proprio diagnostico
    anterior). NENHUM arquivo .cpp/.h do repositorio (incluindo
    PD_PARA_PYTHON.cpp e suas copias em PD_PARA_PYTHON/, 'PD_PARA_PYTHON -
    Copia/', TalvezSejaUmTestenovamente/ e .claude/worktrees/) contem essa
    funcao, nem qualquer trecho relacionado a latitude/longitude/distancia
    geografica -- esses arquivos .cpp tratam de outra parte do sistema
    (B&P/pricing), nao da leitura de instancias Silva.
  - Nenhum PDF, arquivo de material suplementar, ou README no repositorio
    documenta a formula/raio da Terra/projecao usada pelos autores para
    converter LAT/LON em Delta_cicj.
  - O arquivo original dos autores (14n-2k-6c-008r_ML.txt) fornece SOMENTE
    lat/lon por cliente -- nenhuma distancia pre-calculada, nenhuma nota
    de formula.

  CONCLUSAO DESTA BUSCA:
  "A regra de conversão LAT/LON -> Delta não está documentada no material
  disponível."

  Portanto NENHUMA formula alternativa foi escolhida ou testada para tentar
  fechar os +0.348579h -- fazer isso seria calibrar para bater com a tabela,
  o que foi explicitamente proibido nesta etapa.
""")

print("\n" + "-" * 100)
print("SECAO 7 -- RESUMO FINAL")
print("-" * 100)
print("\n  Seis distancias e tempos usados:")
for tag, d, t_h in dists_alpha0 + dists_alpha050:
    print(f"    {tag:10s}: {d:10.6f} km | {t_h:8.6f} h")
print(f"\n  soma_alpha0 (3 arcos)   = {soma_alpha0:.6f}h")
print(f"  soma_alpha050 (3 arcos) = {soma_alpha050:.6f}h")
print(f"  diferenca (alpha050 - alpha0) = {delta:+.6f}h")
print(f"\n  Tabela 3 (implicita): diferenca = -0.2h")
print(f"  diferenca do NOSSO metodo Haversine atual = {delta:+.6f}h")
print(f"  gap entre os dois = {delta - (-0.2):+.6f}h")
print("\n  Regra de distancia ATUALMENTE usada: Haversine classico, R=6371 km")
print("  (instancia.py:haversine_km), coordenadas lat/lon lidas literalmente do")
print("  arquivo original dos autores, sem nenhuma correcao.")
print("\n  Regra dos autores (Delta_cicj): NAO encontrada documentada em nenhum")
print("  material disponivel neste repositorio -- ver secao 5 acima. NENHUMA")
print("  formula alternativa foi escolhida/calibrada para tentar fazer a tabela bater.")
print("\n[FIM -- nenhuma alteracao de codigo de producao foi feita.]")
