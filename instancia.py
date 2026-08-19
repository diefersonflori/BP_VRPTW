import math
import json

class Veiculo:
    def __init__(self, capacidade=0, velocidade=0.0):
        self.capacidade = capacidade
        self.velocidade = velocidade
        # ---- dados Petro (por navio);
        self.nome = ""                 # vesselName
        self.classe = ""               # vesselClass
        self.vessel_id = None          # vesselId
        self.setup_arrival = 0.0  # s
        self.setup_departure = 0.0  # s
        self.trip_duration_limit = 0.0  # s
        self.max_departure = 0.0  # s
        self.readiness = 0.0  # s
        ##capacidades
        self.cap_deck = capacidade
        self.cap_diesel = 0
        self.cap_agua = 0
        #capacidades iniciais
        self.stock_diesel = 0.0
        self.stock_agua = 0.0
        self.velocities = []
        # ---- consumo de combustivel por regime (m3/h), Petro FO ambiental
        self.fuel_anchored = 0.0     # theta_k: fundeio
        self.fuel_base = 0.0         # varphi_k: berco/base
        self.fuel_navigation = 0.0   # gamma_k: navegacao
        self.fuel_dynamic = 0.0      # delta_k: posicionamento dinamico
        # ---- custo por regime (USD/h), modo silva2024 (FCA/FCB/FCN/FCS); nao
        # confundir com fuel_* acima (m3/h, exclusivo do modo petrobras)
        self.cost_anchored = 0.0     # FCA_k: fundeado
        self.cost_base = 0.0         # FCB_k: base
        self.cost_navigation = 0.0   # FCN_k: navegando
        self.cost_dynamic = 0.0      # FCS_k: servico (SET+SP+servico+espera)
        self.safe_positioning_time = 0.0  # SP_k, em segundos (modo silva2024)
        # xi_k: peso de utilizacao por navio (f2 = sum_k xi_k*(F_k-AT_k)), modo
        # silva2024. NAO ATRIBUIDO -- nenhuma fonte local (JSON/README/artigo)
        # informa o valor ou a formula de xi_k; deixado como None de proposito
        # para nao inventar. f2 hoje e calculado como sum_k(F_k-AT_k), ou seja
        # xi_k=1 implicito, o que NAO foi confirmado contra o artigo publicado.
        self.xi = None


class Node:
    def __init__(self, node_id=0, x=0, y=0, demanda=0):
        self.id = node_id
        self.XCOORD = x
        self.YCOORD = y

        # Demanda usada pelo código atual
        self.DEMAND = demanda

        # Demandas Petro separadas
        self.DEMAND_DECK_LOAD = 0
        self.DEMAND_DECK_BACKLOAD = 0
        self.DEMAND_DIESEL = 0
        self.DEMAND_AGUA = 0

        self.READY_TIME = []
        self.DUE_DATE = []
        self.SERVICE_TIME = []


class Instancia:
    def __init__(self):
        self.nbv = 0  # Number of vehicles
        self.nbn = 0  # Number of nodes (clients + depots)
        self.nbcd = 0  # Number of clients
        self.noh = []  # List of Node objects
        self.matriz_distancia = []  # Distance matreix
        self.veiculos = []  # List of Veiculo objects
        self.fileName = ""
        #para teste com muitas
        self.ninst=0
        self.nbconstrutiva=0
        self.temmip=True
        self.iteraSemMelhora=30

        self.usar_estabilizacao=True

        # ---- parametros da FO ambiental Petro (lidos do JSON; Solomon nao usa)
        self.alpha_fo = None
        self.eta_fo = None
        self.densidade_diesel = None
        self.conversao_diesel_co2 = None
        # "petrobras" (default) ou "silva2024" -- ver basicData.objectiveMode
        self.objective_mode = "petrobras"
    nomeInst=""

    ###leitura petro
    def leitura_petro_dados(self, arquivo_instancia, verboso=True):


        with open(arquivo_instancia, "r", encoding="utf-8") as f:
            js = json.load(f)

        entrada = js["input"]
        basicdata = entrada.get("basicData", {})

        decl_clientes = basicdata.get("numberOfClients")
        decl_veiculos = basicdata.get("numberOfVessels")
        decl_orders = basicdata.get("numberOfOrders")

        # ---- parametros da FO ambiental (etapa nova FO Petro) ----
        alpha_fo = basicdata.get("alphaWeight")
        eta_fo = basicdata.get("etaConversion")
        densidade_diesel = basicdata.get("dieselDensity")
        conversao_diesel_co2 = basicdata.get("conversionTonDieselTonCO2Eq")
        # "petrobras" (default, instancias atuais) ou "silva2024" (benchmark Silva et al.)
        objective_mode = basicdata.get("objectiveMode", "petrobras")

        base = entrada["supplyBasesData"][0]
        frota = entrada["fleetData"]
        orders = entrada["ordersData"]

        # ---------- frota ----------
        navio0 = frota[0]
        homogenea = all(
            v["capacity"] == navio0["capacity"]
            and v["tripDurationLimit"] == navio0["tripDurationLimit"]
            and v["setupArrival"] == navio0["setupArrival"]
            and v["setupDeparture"] == navio0["setupDeparture"]
            and v["velocities"] == navio0["velocities"]
            for v in frota
        )
        SEGUNDOS_POR_HORA = 3600.0
        if not homogenea:
            print("[AVISO PETRO] Frota heterogenea - usando navio de MENOR deckSpace.")
            navio0 = min(frota, key=lambda v: v["capacity"]["deckSpace"])
        frota_info = []
        for v in frota:
            fuel = v.get("fuelConsumption", {})
            custo = v.get("fuelCost", {})
            frota_info.append({
                "vessel_id": v.get("vesselId"),
                "nome": v.get("vesselName", ""),
                "classe": v.get("vesselClass", ""),
                "cap_deck": v["capacity"]["deckSpace"],
                "cap_diesel": v["capacity"]["dieselTanks"],
                "cap_agua": v["capacity"]["waterTanks"],
                "stock_diesel": v.get("initialStock", {}).get("dieselLoad", 0.0),
                "stock_agua": v.get("initialStock", {}).get("waterLoad", 0.0),
                "setup_arrival": v["setupArrival"] * SEGUNDOS_POR_HORA,
                "setup_departure": v["setupDeparture"] * SEGUNDOS_POR_HORA,
                "trip_duration_limit": v["tripDurationLimit"] * SEGUNDOS_POR_HORA,
                "max_departure": v["maximumDepartureTime"] * SEGUNDOS_POR_HORA,
                "readiness": v["estimatedTimeOfReadiness"] * SEGUNDOS_POR_HORA,
                "velocities": v["velocities"],
                # consumo por regime (m3/h), usado na FO ambiental do modo petrobras
                "fuel_anchored": fuel.get("anchored", 0.0),
                "fuel_base": fuel.get("base", 0.0),
                "fuel_navigation": fuel.get("navigation", 0.0),
                "fuel_dynamic": fuel.get("dynamic", 0.0),
                # custo por regime (USD/h), usado na FO do modo silva2024 (FCA/FCB/FCN/FCS)
                "cost_anchored": custo.get("anchored", 0.0),
                "cost_base": custo.get("base", 0.0),
                "cost_navigation": custo.get("navigation", 0.0),
                "cost_dynamic": custo.get("dynamic", 0.0),
                # SP_k, modo silva2024 (safe positioning time, uma vez por plataforma visitada)
                "safe_positioning_time": v.get("safePositioningTime", 0.0) * SEGUNDOS_POR_HORA,
            })

        cap_deck = navio0["capacity"]["deckSpace"]
        cap_diesel = navio0["capacity"]["dieselTanks"]
        cap_agua = navio0["capacity"]["waterTanks"]

        setup_total = navio0["setupArrival"] + navio0["setupDeparture"]
        velocities = navio0["velocities"]

        T_max = navio0["tripDurationLimit"] * SEGUNDOS_POR_HORA
        readiness = navio0["estimatedTimeOfReadiness"] * SEGUNDOS_POR_HORA
        max_partida = navio0["maximumDepartureTime"] * SEGUNDOS_POR_HORA

        stock_diesel = navio0.get("initialStock", {}).get("dieselLoad", 0.0)
        stock_agua = navio0.get("initialStock", {}).get("waterLoad", 0.0)

        num_veiculos = decl_veiculos if decl_veiculos is not None else len(frota)
        eff_base = base["efficiency"]

        # ---------- valida contagens ----------
        if decl_veiculos is not None and decl_veiculos != len(frota):
            print("[AVISO PETRO] numberOfVessels=%s declarado, mas %d navios em fleetData."
                  % (decl_veiculos, len(frota)))

        if decl_orders is not None and decl_orders != len(orders):
            print("[AVISO PETRO] numberOfOrders=%s declarado, mas %d orders em ordersData."
                  % (decl_orders, len(orders)))

        clientes_unicos = sorted(set(od["clientId"] for od in orders))
        if decl_clientes is not None and decl_clientes != len(clientes_unicos):
            print("[AVISO PETRO] numberOfClients=%s declarado, mas %d clientId unicos em ordersData."
                  % (decl_clientes, len(clientes_unicos)))

        # ---------- vetores por nó: 0 = base, 1..n = orders ----------
        nomes = ["BASE_" + base["baseName"]]
        lats = [base["latitude"]]
        lons = [base["longitude"]]

        dem_v1 = [0.0]
        dem_dl = [0.0]
        dem_db = [0.0]
        dem_di = [0.0]
        dem_ag = [0.0]

        servico = [0.0]
        janelas_mtw = [[[readiness, T_max]]]
        tempo_carreg_deck = [0.0]
        # duracoes de berco ainda nao computadas antes desta etapa (dado morto):
        # diesel/agua carregados na SAIDA da base; backload descarregado no RETORNO.
        tempo_carreg_diesel = [0.0]
        tempo_carreg_agua = [0.0]
        tempo_descarreg_backload = [0.0]
        # SET (platformSetup), modo silva2024: setup por PLATAFORMA/VISITA, nao por
        # order; o valor eh lido por order (repetido entre orders da mesma
        # plataforma) e a deduplicacao (uma cobranca por visita) ocorre em metodos.py.
        platform_setup_seg = [0.0]

        order_ids = [None]
        client_ids = [None]
        commodities = [None]
        # dueTime por order (modo silva2024; restricao de prazo AINDA NAO
        # implementada -- so leitura/armazenamento, ver metodo_exato_petro).
        order_due_time_seg = [None]

        descartes = []

        orders_ordenadas = sorted(orders, key=lambda od: od["orderId"])

        for od in orders_ordenadas:
            q = od["quantity"]
            comm = od["commodity"]

            nomes.append("%s_order_%s" % (od["clientName"], od["orderId"]))
            lats.append(od["latitude"])
            lons.append(od["longitude"])

            order_ids.append(od["orderId"])
            client_ids.append(od["clientId"])
            commodities.append(comm)
            due_time = od.get("dueTime")
            order_due_time_seg.append(due_time * SEGUNDOS_POR_HORA if due_time is not None else None)

            dl = db = di = ag = 0.0
            carreg_diesel = 0.0
            carreg_agua = 0.0
            descarreg_backload = 0.0

            if comm == "deckCargoLoad":
                dl = q
                demanda_vrp = q
                carreg_deck = (
                                      q / eff_base["deckCargoLoad"]
                              ) * SEGUNDOS_POR_HORA

            elif comm == "deckCargoBackload":
                db = q
                demanda_vrp = q
                carreg_deck = 0.0
                # descarga do backload ocorre no RETORNO a base (apos R_k)
                descarreg_backload = (
                                      q / eff_base["deckCargoBackload"]
                              ) * SEGUNDOS_POR_HORA

            elif comm == "dieselLoad":
                di = q
                demanda_vrp = 0.0
                carreg_deck = 0.0
                # diesel e carregado na SAIDA da base (antes de P_k)
                carreg_diesel = (
                                      q / eff_base["dieselLoad"]
                              ) * SEGUNDOS_POR_HORA

            elif comm == "waterLoad":
                ag = q
                demanda_vrp = 0.0
                carreg_deck = 0.0
                # agua e carregada na SAIDA da base (antes de P_k)
                carreg_agua = (
                                      q / eff_base["waterLoad"]
                              ) * SEGUNDOS_POR_HORA

            dem_dl.append(dl)
            dem_db.append(db)
            dem_di.append(di)
            dem_ag.append(ag)
            dem_v1.append(demanda_vrp)

            tempo_servico = (
                                    q / od["efficiency"]
                                    + od.get("serviceSetup", 0.0)
                            ) * SEGUNDOS_POR_HORA
            servico.append(tempo_servico)  # setup movido para os arcos

            janelas_mtw.append([
                [
                    ini * SEGUNDOS_POR_HORA,
                    fim * SEGUNDOS_POR_HORA
                ]
                for ini, fim in od["timeWindows"]
            ])
            tempo_carreg_deck.append(carreg_deck)
            tempo_carreg_diesel.append(carreg_diesel)
            tempo_carreg_agua.append(carreg_agua)
            tempo_descarreg_backload.append(descarreg_backload)
            platform_setup_seg.append(od.get("platformSetup", 0.0) * SEGUNDOS_POR_HORA)

            avisar_relacoes = False

            if avisar_relacoes and od.get("successor") is not None:
                descartes.append("order %d (%s): successor=%s ignorado"
                                 % (od["orderId"], od["clientName"], od["successor"]))

            if avisar_relacoes and od.get("transshipment") is not None:
                descartes.append("order %d (%s): transshipment=%s ignorado"
                                 % (od["orderId"], od["clientName"], od["transshipment"]))

        n = len(orders_ordenadas)

        janelas_env = [[j[0][0], j[-1][1]] for j in janelas_mtw]

        # ---------- matrizes ----------
        N = n + 1
        dist = [[0.0] * N for _ in range(N)]
        tempo = [[0.0] * N for _ in range(N)]
        # tempo de navegacao pura (sem setupArrival/setupDeparture), usado na FO
        # ambiental (t_k); NAO usar "tempo" acima para isso, pois inclui setups.
        tempo_navegacao = [[0.0] * N for _ in range(N)]

        setup_arr = navio0["setupArrival"] * SEGUNDOS_POR_HORA
        setup_dep = navio0["setupDeparture"] * SEGUNDOS_POR_HORA
        for i in range(N):
            for j in range(N):
                if i == j:
                    continue
                # mesma plataforma (mesmo clientId): navio ja atracado -> arco 0
                if client_ids[i] is not None and client_ids[i] == client_ids[j]:
                    dist[i][j] = 0.0
                    tempo[i][j] = 0.0
                    tempo_navegacao[i][j] = 0.0
                    continue
                d = self.haversine_km(lats[i], lons[i], lats[j], lons[j])
                dist[i][j] = d
                velocidade_arco = self.velocidade_kmh(d, velocities)

                t_puro = (
                            d / velocidade_arco
                    ) * SEGUNDOS_POR_HORA
                tempo_navegacao[i][j] = t_puro
                t = t_puro
                if i == 0:  # base -> order: atracacao na chegada
                    t += setup_arr
                elif j == 0:  # order -> base: desatracacao na saida
                    t += setup_dep
                else:  # plataforma -> plataforma: sai de i e atraca em j
                    t += setup_dep + setup_arr
                tempo[i][j] = t

        dados = {
            "arquivo": arquivo_instancia,
            "n_clientes": n,  # para compatibilidade com seu código
            "n_orders": n,
            "num_veiculos": num_veiculos,

            "nomes": nomes,
            "lat": lats,
            "lon": lons,

            "order_ids": order_ids,
            "client_ids": client_ids,
            "commodities": commodities,

            "capacidade": cap_deck,
            "cap_diesel": cap_diesel,
            "cap_agua": cap_agua,

            "stock_diesel": stock_diesel,
            "stock_agua": stock_agua,

            "demanda": dem_v1,
            "dem_deck_load": dem_dl,
            "dem_deck_backload": dem_db,
            "dem_diesel": dem_di,
            "dem_agua": dem_ag,

            "servico": servico,
            "janelas_mtw": janelas_mtw,
            "janelas_env": janelas_env,

            "dist": dist,
            "tempo": tempo,
            "tempo_navegacao": tempo_navegacao,

            "T_max": T_max,
            "readiness": readiness,
            "max_partida": max_partida,

            "tempo_carreg_deck": tempo_carreg_deck,
            "tempo_carreg_diesel": tempo_carreg_diesel,
            "tempo_carreg_agua": tempo_carreg_agua,
            "tempo_descarreg_backload": tempo_descarreg_backload,
            "platform_setup_seg": platform_setup_seg,
            "order_due_time_seg": order_due_time_seg,
            "eff_base": eff_base,
            "frota_info": frota_info,
            "descartes": descartes,

            # parametros da FO ambiental (etapa nova FO Petro)
            "alpha_fo": alpha_fo,
            "eta_fo": eta_fo,
            "densidade_diesel": densidade_diesel,
            "conversao_diesel_co2": conversao_diesel_co2,
            "objective_mode": objective_mode,
        }

        if verboso:
            self.relatorio_petro(dados)

        return dados
    def relatorio_petro(self, d):
        print("=" * 70)
        print("LEITURA PETRO: %s" % d["arquivo"])
        print("Clientes: %d | Navios: %d | deckSpace=%.0f dieselTanks=%.0f waterTanks=%.0f"
              % (d["n_clientes"], d["num_veiculos"],
                 d["capacidade"], d["cap_diesel"], d["cap_agua"]))
        print("initialStock: diesel=%.0f agua=%.0f | janela base=[%.0f, %.0f] s | max_partida=%.0f s"
              % (d["stock_diesel"], d["stock_agua"],
                 d["readiness"], d["T_max"], d["max_partida"]))
        print("-" * 70)
        print("%-12s %8s %8s %8s %8s %8s %8s %5s" %
              ("no", "dem_v1", "deck_L", "deck_B", "diesel", "agua", "serv(s)", "#jan"))
        for i in range(len(d["nomes"])):
            print("%-12s %8.1f %8.1f %8.1f %8.1f %8.1f %8.2f %5d" %
                  (d["nomes"][i], d["demanda"][i], d["dem_deck_load"][i],
                   d["dem_deck_backload"][i], d["dem_diesel"][i], d["dem_agua"][i],
                   d["servico"][i], len(d["janelas_mtw"][i])))
        print("-" * 70)
        print("Demanda v1 total (deck L+B): %.1f  (capacidade %.0f)"
              % (sum(d["demanda"]), d["capacidade"]))
        print("Diesel total: %.1f (stock %.0f) | Agua total: %.1f (stock %.0f)"
              % (sum(d["dem_diesel"]), d["stock_diesel"],
                 sum(d["dem_agua"]), d["stock_agua"]))
        for j in range(1, d["n_clientes"] + 1):
            print("base -> %-8s: %6.1f km  %8.0f s"
                  % (d["nomes"][j], d["dist"][0][j], d["tempo"][0][j]))
        if d["descartes"]:
            print("-" * 70)
            print("IGNORADO NA v1 (%d itens):" % len(d["descartes"]))
            for s in d["descartes"]:
                print("  - " + s)
        print("=" * 70)

    def leitura_petro(self, argv):

        self.fileName = argv
        dados = self.leitura_petro_dados(argv, verboso=True)

        self.nbcd = dados["n_clientes"]
        self.nbn = self.nbcd + 2
        self.nbv = dados["num_veiculos"]

        # ---------- nos ----------
        self.noh = [Node() for _ in range(self.nbn)]
        for i in range(self.nbcd + 1):  # 0=base, 1..n=clientes
            no_aux = Node(
                node_id=i,
                x=dados["lon"][i],
                y=dados["lat"][i],
                demanda=int(round(dados["demanda"][i])),
            )
            no_aux.DEMAND_DECK_LOAD = int(round(dados["dem_deck_load"][i]))
            no_aux.DEMAND_DECK_BACKLOAD = int(round(dados["dem_deck_backload"][i]))
            no_aux.DEMAND_DIESEL = int(round(dados["dem_diesel"][i]))
            no_aux.DEMAND_AGUA = int(round(dados["dem_agua"][i]))

            for (ini, fim) in dados["janelas_mtw"][i]:
                no_aux.READY_TIME.append(int(round(ini)))
                no_aux.DUE_DATE.append(int(round(fim)))
            no_aux.SERVICE_TIME.append(int(round(dados["servico"][i])))
            self.noh[i] = no_aux

        # copia da base no ultimo no
        self.noh[self.nbn - 1] = Node(
            node_id=self.nbn - 1,
            x=self.noh[0].XCOORD, y=self.noh[0].YCOORD,
            demanda=self.noh[0].DEMAND,
        )
        self.noh[self.nbn - 1].READY_TIME = list(self.noh[0].READY_TIME)
        self.noh[self.nbn - 1].DUE_DATE = list(self.noh[0].DUE_DATE)
        self.noh[self.nbn - 1].SERVICE_TIME = list(self.noh[0].SERVICE_TIME)

        self.noh[self.nbn - 1].DEMAND_DECK_LOAD = self.noh[0].DEMAND_DECK_LOAD
        self.noh[self.nbn - 1].DEMAND_DECK_BACKLOAD = self.noh[0].DEMAND_DECK_BACKLOAD
        self.noh[self.nbn - 1].DEMAND_DIESEL = self.noh[0].DEMAND_DIESEL
        self.noh[self.nbn - 1].DEMAND_AGUA = self.noh[0].DEMAND_AGUA

        # ---------- matriz: tempo de viagem (inclui setupArrival/setupDeparture) ----------
        self.matriz_distancia = [[-1] * self.nbn for _ in range(self.nbn)]
        # ---------- matriz: tempo de navegacao pura (sem setups), usada na FO ambiental ----------
        self.matriz_tempo_navegacao = [[-1] * self.nbn for _ in range(self.nbn)]
        for i in range(self.nbn):
            for j in range(self.nbn):
                if i == j:
                    continue
                ii = 0 if i == self.nbn - 1 else i
                jj = 0 if j == self.nbn - 1 else j
                if ii == jj:
                    self.matriz_distancia[i][j] = 0
                    self.matriz_tempo_navegacao[i][j] = 0
                else:
                    self.matriz_distancia[i][j] = int(
                        round(dados["tempo"][ii][jj]))
                    self.matriz_tempo_navegacao[i][j] = int(
                        round(dados["tempo_navegacao"][ii][jj]))

        # ---------- veiculos (dados individuais; pricing usa o mais restritivo) ----------
        cap_pricing = int(round(min(fi["cap_deck"] for fi in dados["frota_info"])))
        self.veiculos = []
        for fi in dados["frota_info"]:
            veic = Veiculo(capacidade=int(round(fi["cap_deck"])), velocidade=1.0)
            veic.nome = fi["nome"]
            veic.classe = fi["classe"]
            veic.vessel_id = fi["vessel_id"]
            veic.setup_arrival = fi["setup_arrival"]
            veic.setup_departure = fi["setup_departure"]
            veic.trip_duration_limit = fi["trip_duration_limit"]
            veic.max_departure = fi["max_departure"]
            veic.readiness = fi["readiness"]
            veic.cap_deck = fi["cap_deck"]
            veic.cap_diesel = fi["cap_diesel"]
            veic.cap_agua = fi["cap_agua"]
            veic.stock_diesel = fi["stock_diesel"]
            veic.stock_agua = fi["stock_agua"]
            veic.velocities = list(fi["velocities"])
            veic.fuel_anchored = fi["fuel_anchored"]
            veic.fuel_base = fi["fuel_base"]
            veic.fuel_navigation = fi["fuel_navigation"]
            veic.fuel_dynamic = fi["fuel_dynamic"]
            veic.cost_anchored = fi["cost_anchored"]
            veic.cost_base = fi["cost_base"]
            veic.cost_navigation = fi["cost_navigation"]
            veic.cost_dynamic = fi["cost_dynamic"]
            veic.safe_positioning_time = fi["safe_positioning_time"]
            self.veiculos.append(veic)


        # dados Petro extras (diesel/agua, carregamento na base, etc.)
        self.dados_petro = dados

        # parametros da FO ambiental Petro (lidos do JSON, nao hardcoded)
        self.alpha_fo = dados["alpha_fo"]
        self.eta_fo = dados["eta_fo"]
        self.densidade_diesel = dados["densidade_diesel"]
        self.conversao_diesel_co2 = dados["conversao_diesel_co2"]
        self.objective_mode = dados["objective_mode"]

    ###Fimleitura petro


    def leitura(self, argv):
        """

        with open("solucao_ex.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_gcm.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_gc.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_final.json", 'w') as f:
            json.dump("", f, indent=0)
        """

        if len(argv) < 2:
            print("Error! File Name missing")
            exit(1)

        #"""
        #self.nbcd = 13
        #Q = 110
        #self.nbcd = 7
        #Q = 70
        #self.nbv = 2
        #"""
        #self.nbcd = 20
        #self.nbv = 2
        #Q = 200
        """
        #self.nbcd = 20
        #self.nbv = 2
        """

        #Q = 200
        """

        self.nbcd = 25
        self.nbv = 3
        Q = 200
        """

        """

        self.nbcd = 50
        self.nbv = 25
        Q = 1000
        """

        #self.nbcd = 4
        #Q = 36

        #self.nbn = self.nbcd + 2
        Vel = 1
        #Vel = 1
        self.fileName = argv

        with open(self.fileName, 'r') as infile:
            lines = infile.readlines()

        self.noh = [Node() for _ in range(self.nbn)]
        found = False
        idx = 0
        for i, line in enumerate(lines):
            if "TIME" in line:
                found = True
                for j in range(self.nbn - 1):  # nbn-1 nodes before final depot
                    parts = lines[i + j + 2].split()
                    #parts = lines[i + j + 1].split() ## ajuste para instancias em geral
                    #if len(parts) < 10:
                    #    continue  # Skip invalid lines
                    no_aux = Node(
                        node_id=int(parts[0]),
                        x=int(parts[1]),
                        y=int(parts[2]),
                        demanda=int(parts[3]),
                    )
                    a1 = int(parts[4])
                    a2 = int(parts[5])
                    #a3 = int(parts[6])
                    #a4 = int(parts[7])
                    #a5 = int(parts[8])
                    a5 = int(parts[6])
                    #a5 = int(parts[8])
                    #a6 = int(parts[9])
                    no_aux.READY_TIME.append(a1)
                    no_aux.DUE_DATE.append(a2)
                    #no_aux.READY_TIME.append(a3)
                    #no_aux.DUE_DATE.append(a4)
                    no_aux.SERVICE_TIME.append(a5)
                    #no_aux.SERVICE_TIME.append(90)
                    #$talvez colocar depois o servico
                    self.noh[j] = no_aux
                self.noh[self.nbn - 1] = Node(
                    node_id=self.nbn - 1,
                    x=self.noh[0].XCOORD,
                    y=self.noh[0].YCOORD,
                    demanda=self.noh[0].DEMAND
                )
                self.noh[self.nbn - 1].READY_TIME = list(self.noh[0].READY_TIME)
                self.noh[self.nbn - 1].DUE_DATE = list(self.noh[0].DUE_DATE)
                self.noh[self.nbn - 1].SERVICE_TIME = list(self.noh[0].SERVICE_TIME)

                break

        # Distância
        self.gera_matriz_distancias()
        # Veículos
        for jk in range(self.nbv):
            veic_aux = Veiculo(
                #capacidade=int(Q / (jk + 1)),
                #velocidade=int(Vel * (jk + 1))
                #capacidade = Q,
                capacidade = 0,
                velocidade = Vel
            )
            self.veiculos.append(veic_aux)

    def gera_matriz_distancias(self):
        self.matriz_distancia = [[0] * self.nbn for _ in range(self.nbn)]
        for i in range(self.nbn):
            for j in range(self.nbn):
                if i != j:
                    self.matriz_distancia[i][j] = self.calculo_distancia(
                        1,
                        self.noh[i].XCOORD, self.noh[i].YCOORD,
                        self.noh[j].XCOORD, self.noh[j].YCOORD
                    )
                else:
                    self.matriz_distancia[i][j] = -1

    def calculo_distancia2(self, cond, cordx1, cordy1, cordx2, cordy2):
        if cond == 1:
            return math.hypot(cordx1 - cordx2, cordy1 - cordy2)
        return 0.0

    def calculo_distancia(self, cond, cordx1, cordy1, cordx2, cordy2):
        if cond == 1:
            dist = math.hypot(cordx1 - cordx2, cordy1 - cordy2)
            dist_trunc_1casa = math.floor(dist * 10.0) / 10.0
            return int(dist_trunc_1casa * 10)
        return 0

    def haversine_km(self,lat1, lon1, lat2, lon2):
        """Distância em km — réplica exata da get_haversine_distance do C++ (R=6371)."""
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        l1 = math.radians(lat1)
        l2 = math.radians(lat2)
        a = math.sin(dLat / 2.0) ** 2 + math.sin(dLon / 2.0) ** 2 * math.cos(l1) * math.cos(l2)
        return 2.0 * 6371.0 * math.asin(math.sqrt(a))

    def velocidade_kmh(self, dist_km, velocities):
        """Seleciona a velocidade (km/h) cujo limiar 'above' (km) é o maior abaixo da distância."""
        for v in sorted(velocities, key=lambda x: x["above"], reverse=True):
            if dist_km > v["above"]:
                return v["speed"]
        return sorted(velocities, key=lambda x: x["above"])[0]["speed"]