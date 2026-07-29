"""
Gerador das seis instâncias Petrobras de 15 pedidos e 6 plataformas.

As coordenadas foram transcritas da planilha:
Localização das Plataformas(1).xlsx

Uso:
    python gerar_instancias_petro_15ped_6plat.py

Saída:
    ./instancias_petro_15ped_6plataformas/
"""
import json
import math
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone

PLATAFORMAS = {'P-43': {'lat': -22.55011, 'lon': -40.25944889},
 'P-40': {'lat': -22.54742194, 'lon': -40.06744306},
 'P-51': {'lat': -22.63440278, 'lon': -40.09363722},
 'P-53': {'lat': -22.42401667, 'lon': -39.95766667},
 'P-48': {'lat': -22.66388389, 'lon': -40.24018889},
 'FPANE': {'lat': -22.46391639, 'lon': -40.05731667},
 'P-58': {'lat': -21.21508417, 'lon': -39.99736472},
 'P-54': {'lat': -21.96911389, 'lon': -39.82530278},
 'P-65': {'lat': -22.70183667, 'lon': -40.67710639},
 'FPCGZ': {'lat': -22.95337917, 'lon': -40.72554611}}

BASE = {'instanceInformation': {'omarGatewayJobId': 999999999,
                         'referenceDateTime': '2021-01-01T04:00:00-0300',
                         'userComments': [],
                         'instanceDatetimeGeneration': '2026-07-20T08:14:57+0000',
                         'instanceId': {'basicData': '3LTPK5Y0Q7SKX',
                                        'capacityCommodityAssignmentData': '50X3NY4DEBUK1',
                                        'fleetData': '4BO6192QF3CR9',
                                        'supplyBasesData': '3TW73IB1RSVSZ',
                                        'ordersData': ''}},
 'input': {'basicData': {'alphaWeight': 0.1,
                         'etaConversion': 1.4,
                         'mipRelativeGapTolerance': 0.001,
                         'numberOfThreads': 1,
                         'runTimeLimit': 600,
                         'useCostMeasureInFuelVolume': True,
                         'useMipStarts': False,
                         'useRoundedCapacityInequalities': False,
                         'useSolverCuts': False,
                         'useSubtourEliminationConstraints': False,
                         'conversionTonDieselTonCO2Eq': 3.595,
                         'dieselDensity': 0.852,
                         'numberOfOrders': 15,
                         'numberOfVessels': 3,
                         'numberOfClients': 6,
                         'numberOfBackloadCommodities': 1,
                         'numberOfCompartments': 3,
                         'numberOfLoadCommodities': 3,
                         'tripClass': 'cronograma'},
           'capacityCommodityAssignmentData': [{'compartment': 'deckSpace',
                                                'deckCargoBackload': 1,
                                                'deckCargoLoad': 1,
                                                'dieselLoad': 0,
                                                'waterLoad': 0},
                                               {'compartment': 'dieselTanks',
                                                'deckCargoBackload': 0,
                                                'deckCargoLoad': 0,
                                                'dieselLoad': 1,
                                                'waterLoad': 0},
                                               {'compartment': 'waterTanks',
                                                'deckCargoBackload': 0,
                                                'deckCargoLoad': 0,
                                                'dieselLoad': 0,
                                                'waterLoad': 1}],
           'fleetData': [{'vesselId': 2,
                          'vesselName': 'STARNAV TAURUS2',
                          'vesselClass': 'PSV 4500',
                          'maximumNumberOfTrips': 1,
                          'tripDurationLimit': 168.0,
                          'setupArrival': 1.02,
                          'setupDeparture': 0.51,
                          'estimatedTimeOfReadiness': 3.0,
                          'maximumDepartureTime': 48.0,
                          'latitude': -22.333,
                          'longitude': -41.645,
                          'capacity': {'deckSpace': 900.0, 'dieselTanks': 1000.0, 'waterTanks': 2500.0},
                          'fuelConsumption': {'anchored': 0.3525,
                                              'base': 0.9832,
                                              'navigation': 3.9419,
                                              'dynamic': 1.9694},
                          'velocities': [{'above': 18.0, 'speed': 16.668}, {'above': 0.0, 'speed': 13.3344}],
                          'initialStock': {'dieselLoad': 500.0, 'waterLoad': 400.0}},
                         {'vesselId': 1,
                          'vesselName': 'STARNAV TAURUS3',
                          'vesselClass': 'PSV 4500',
                          'maximumNumberOfTrips': 1,
                          'tripDurationLimit': 168.0,
                          'setupArrival': 1.02,
                          'setupDeparture': 0.51,
                          'estimatedTimeOfReadiness': 3.0,
                          'maximumDepartureTime': 48.0,
                          'latitude': -22.333,
                          'longitude': -41.645,
                          'capacity': {'deckSpace': 900.0, 'dieselTanks': 1000.0, 'waterTanks': 2500.0},
                          'fuelConsumption': {'anchored': 0.3525,
                                              'base': 0.9832,
                                              'navigation': 3.9419,
                                              'dynamic': 1.9694},
                          'velocities': [{'above': 18.0, 'speed': 16.668}, {'above': 0.0, 'speed': 13.3344}],
                          'initialStock': {'dieselLoad': 500.0, 'waterLoad': 400.0}},
                         {'vesselId': 3,
                          'vesselName': 'STARNAV TAURUS',
                          'vesselClass': 'PSV 4500',
                          'maximumNumberOfTrips': 1,
                          'tripDurationLimit': 168.0,
                          'setupArrival': 1.02,
                          'setupDeparture': 0.51,
                          'estimatedTimeOfReadiness': 3.0,
                          'maximumDepartureTime': 48.0,
                          'latitude': -22.333,
                          'longitude': -41.645,
                          'capacity': {'deckSpace': 900.0, 'dieselTanks': 1000.0, 'waterTanks': 2500.0},
                          'fuelConsumption': {'anchored': 0.3525,
                                              'base': 0.9832,
                                              'navigation': 3.9419,
                                              'dynamic': 1.9694},
                          'velocities': [{'above': 18.0, 'speed': 16.668}, {'above': 0.0, 'speed': 13.3344}],
                          'initialStock': {'dieselLoad': 500.0, 'waterLoad': 400.0}}],
           'supplyBasesData': [{'baseName': 'PACU',
                                'baseId': 0,
                                'region': 'SE',
                                'efficiency': {'deckCargoBackload': 73.0,
                                               'deckCargoLoad': 73.0,
                                               'dieselLoad': 90.0,
                                               'waterLoad': 102.0},
                                'successor': None,
                                'navigationTimeToMoor': 3.0,
                                'latitude': -21.845602,
                                'longitude': -40.996652}],
           'ordersData': []},
 'output': {'instanceStatus': 'unsolved'}}

JANELAS_AMPLAS = {'P-43': [[18.0, 96.0], [108.0, 168.0]],
 'P-40': [[24.0, 102.0], [114.0, 168.0]],
 'P-51': [[30.0, 108.0], [120.0, 168.0]],
 'P-53': [[18.0, 108.0], [120.0, 168.0]],
 'P-48': [[36.0, 120.0], [132.0, 168.0]],
 'FPANE': [[24.0, 114.0], [126.0, 168.0]],
 'P-58': [[18.0, 108.0], [120.0, 168.0]],
 'P-54': [[24.0, 114.0], [126.0, 168.0]],
 'P-65': [[36.0, 126.0], [138.0, 168.0]],
 'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}
JANELAS_ESCALONADAS = {'P-43': [[18.0, 84.0], [108.0, 156.0]],
 'P-40': [[42.0, 108.0], [126.0, 168.0]],
 'P-51': [[30.0, 96.0], [114.0, 162.0]],
 'P-53': [[60.0, 126.0], [138.0, 168.0]],
 'P-48': [[48.0, 114.0], [126.0, 168.0]],
 'FPANE': [[78.0, 144.0], [150.0, 168.0]]}

ORDER_PATTERN = [('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0),
 ('waterLoad', 56.3),
 ('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0),
 ('dieselLoad', 66.7),
 ('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0),
 ('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0),
 ('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0),
 ('waterLoad', 56.3),
 ('deckCargoLoad', 30.0),
 ('deckCargoBackload', 30.0)]
PLATFORM_INDEX_PATTERN = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5]

SCENARIOS = [{'arquivo': 'petro_campos_15ped_6plat_01_forca2v_balanceada.json',
  'descricao': '15 pedidos, 6 plataformas, mínimo teórico de 2 navios; entregas e coletas balanceadas.',
  'platforms': ['P-43', 'P-40', 'P-51', 'P-53', 'P-48', 'FPANE'],
  'loads': [200, 180, 220, 190, 210, 200],
  'backs': [160, 180, 170, 190, 180, 170],
  'water': [280, 260],
  'diesel': [260],
  'windows': {'P-43': [[18.0, 96.0], [108.0, 168.0]],
              'P-40': [[24.0, 102.0], [114.0, 168.0]],
              'P-51': [[30.0, 108.0], [120.0, 168.0]],
              'P-53': [[18.0, 108.0], [120.0, 168.0]],
              'P-48': [[36.0, 120.0], [132.0, 168.0]],
              'FPANE': [[24.0, 114.0], [126.0, 168.0]],
              'P-58': [[18.0, 108.0], [120.0, 168.0]],
              'P-54': [[24.0, 114.0], [126.0, 168.0]],
              'P-65': [[36.0, 126.0], [138.0, 168.0]],
              'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}},
 {'arquivo': 'petro_campos_15ped_6plat_02_forca2v_entrega_pesada.json',
  'descricao': '15 pedidos, 6 plataformas, mínimo de 2 navios forçado principalmente por entregas.',
  'platforms': ['P-43', 'P-40', 'P-51', 'P-53', 'P-48', 'FPANE'],
  'loads': [260, 240, 260, 250, 280, 260],
  'backs': [120, 130, 110, 130, 140, 120],
  'water': [300, 250],
  'diesel': [280],
  'windows': {'P-43': [[18.0, 96.0], [108.0, 168.0]],
              'P-40': [[24.0, 102.0], [114.0, 168.0]],
              'P-51': [[30.0, 108.0], [120.0, 168.0]],
              'P-53': [[18.0, 108.0], [120.0, 168.0]],
              'P-48': [[36.0, 120.0], [132.0, 168.0]],
              'FPANE': [[24.0, 114.0], [126.0, 168.0]],
              'P-58': [[18.0, 108.0], [120.0, 168.0]],
              'P-54': [[24.0, 114.0], [126.0, 168.0]],
              'P-65': [[36.0, 126.0], [138.0, 168.0]],
              'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}},
 {'arquivo': 'petro_campos_15ped_6plat_03_forca2v_coleta_pesada.json',
  'descricao': '15 pedidos, 6 plataformas, mínimo de 2 navios forçado principalmente por coletas.',
  'platforms': ['P-43', 'P-40', 'P-51', 'P-53', 'P-48', 'FPANE'],
  'loads': [130, 140, 120, 140, 130, 140],
  'backs': [210, 220, 200, 230, 210, 230],
  'water': [280, 260],
  'diesel': [260],
  'windows': {'P-43': [[18.0, 96.0], [108.0, 168.0]],
              'P-40': [[24.0, 102.0], [114.0, 168.0]],
              'P-51': [[30.0, 108.0], [120.0, 168.0]],
              'P-53': [[18.0, 108.0], [120.0, 168.0]],
              'P-48': [[36.0, 120.0], [132.0, 168.0]],
              'FPANE': [[24.0, 114.0], [126.0, 168.0]],
              'P-58': [[18.0, 108.0], [120.0, 168.0]],
              'P-54': [[24.0, 114.0], [126.0, 168.0]],
              'P-65': [[36.0, 126.0], [138.0, 168.0]],
              'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}},
 {'arquivo': 'petro_campos_15ped_6plat_04_forca3v_balanceada.json',
  'descricao': '15 pedidos, 6 plataformas, mínimo teórico de 3 navios por entregas e coletas.',
  'platforms': ['P-43', 'P-40', 'P-51', 'P-53', 'P-48', 'FPANE'],
  'loads': [320, 310, 330, 310, 330, 320],
  'backs': [300, 310, 300, 320, 300, 310],
  'water': [260, 240],
  'diesel': [240],
  'windows': {'P-43': [[18.0, 96.0], [108.0, 168.0]],
              'P-40': [[24.0, 102.0], [114.0, 168.0]],
              'P-51': [[30.0, 108.0], [120.0, 168.0]],
              'P-53': [[18.0, 108.0], [120.0, 168.0]],
              'P-48': [[36.0, 120.0], [132.0, 168.0]],
              'FPANE': [[24.0, 114.0], [126.0, 168.0]],
              'P-58': [[18.0, 108.0], [120.0, 168.0]],
              'P-54': [[24.0, 114.0], [126.0, 168.0]],
              'P-65': [[36.0, 126.0], [138.0, 168.0]],
              'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}},
 {'arquivo': 'petro_campos_15ped_6plat_05_forca3v_janelas_escalonadas.json',
  'descricao': '15 pedidos, 6 plataformas, mínimo de 3 navios por entregas, com janelas escalonadas.',
  'platforms': ['P-43', 'P-40', 'P-51', 'P-53', 'P-48', 'FPANE'],
  'loads': [300, 310, 320, 310, 330, 320],
  'backs': [260, 270, 250, 270, 280, 270],
  'water': [240, 220],
  'diesel': [220],
  'windows': {'P-43': [[18.0, 84.0], [108.0, 156.0]],
              'P-40': [[42.0, 108.0], [126.0, 168.0]],
              'P-51': [[30.0, 96.0], [114.0, 162.0]],
              'P-53': [[60.0, 126.0], [138.0, 168.0]],
              'P-48': [[48.0, 114.0], [126.0, 168.0]],
              'FPANE': [[78.0, 144.0], [150.0, 168.0]]}},
 {'arquivo': 'petro_campos_15ped_6plat_06_forca3v_geografia_espalhada.json',
  'descricao': '15 pedidos, 6 plataformas mais espalhadas na Bacia de Campos; mínimo de 3 navios por '
               'entregas.',
  'platforms': ['P-58', 'P-54', 'P-43', 'P-48', 'P-65', 'FPCGZ'],
  'loads': [320, 310, 330, 320, 330, 310],
  'backs': [240, 250, 260, 250, 260, 240],
  'water': [240, 220],
  'diesel': [220],
  'windows': {'P-43': [[18.0, 96.0], [108.0, 168.0]],
              'P-40': [[24.0, 102.0], [114.0, 168.0]],
              'P-51': [[30.0, 108.0], [120.0, 168.0]],
              'P-53': [[18.0, 108.0], [120.0, 168.0]],
              'P-48': [[36.0, 120.0], [132.0, 168.0]],
              'FPANE': [[24.0, 114.0], [126.0, 168.0]],
              'P-58': [[18.0, 108.0], [120.0, 168.0]],
              'P-54': [[24.0, 114.0], [126.0, 168.0]],
              'P-65': [[36.0, 126.0], [138.0, 168.0]],
              'FPCGZ': [[42.0, 132.0], [144.0, 168.0]]}}]

def make_order(order_id, client_id, platform, commodity, efficiency, quantity, windows):
    loc = PLATAFORMAS[platform]
    return {
        "orderId": order_id,
        "clientId": client_id,
        "clientName": platform,
        "clusterName": "BC04",
        "commodity": commodity,
        "efficiency": float(efficiency),
        "serviceSetup": 0.0,
        "latitude": float(loc["lat"]),
        "longitude": float(loc["lon"]),
        "orderPriorityClient": 0,
        "penaltyDueDate": 1000.0,
        "penaltyReadyTime": 1000.0,
        "quantity": float(quantity),
        "successor": None,
        "fix_successor_seq": False,
        "transshipment": None,
        "timeWindows": deepcopy(windows[platform]),
    }

def gerar():
    destino = Path(__file__).resolve().parent / "instancias_petro_15ped_6plataformas"
    destino.mkdir(parents=True, exist_ok=True)

    for i, scenario in enumerate(SCENARIOS, start=1):
        data = deepcopy(BASE)
        data["instanceInformation"]["instanceDatetimeGeneration"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        )
        data["instanceInformation"]["instanceId"]["ordersData"] = f"PETRO15P6PLAT_{i:02d}"
        data["instanceInformation"]["userComments"] = [
            scenario["descricao"],
            "Coordenadas extraídas da planilha Localização das Plataformas(1).xlsx.",
            "Sem successor/transshipment para isolar capacidade, janelas e roteamento."
        ]

        load_iter = iter(scenario["loads"])
        back_iter = iter(scenario["backs"])
        water_iter = iter(scenario["water"])
        diesel_iter = iter(scenario["diesel"])

        orders = []
        for order_id, ((commodity, efficiency), plat_idx) in enumerate(
            zip(ORDER_PATTERN, PLATFORM_INDEX_PATTERN), start=1
        ):
            platform = scenario["platforms"][plat_idx]

            if commodity == "deckCargoLoad":
                quantity = next(load_iter)
            elif commodity == "deckCargoBackload":
                quantity = next(back_iter)
            elif commodity == "waterLoad":
                quantity = next(water_iter)
            elif commodity == "dieselLoad":
                quantity = next(diesel_iter)
            else:
                raise ValueError(f"Commodity desconhecida: {commodity}")

            orders.append(
                make_order(
                    order_id,
                    plat_idx + 1,
                    platform,
                    commodity,
                    efficiency,
                    quantity,
                    scenario["windows"],
                )
            )

        data["input"]["ordersData"] = orders

        total_load = sum(
            o["quantity"] for o in orders if o["commodity"] == "deckCargoLoad"
        )
        total_back = sum(
            o["quantity"] for o in orders if o["commodity"] == "deckCargoBackload"
        )
        minimo = max(
            math.ceil(total_load / 900.0),
            math.ceil(total_back / 900.0),
        )

        if len(orders) != 15:
            raise RuntimeError("A instância não ficou com 15 pedidos.")
        if len({o["clientId"] for o in orders}) != 6:
            raise RuntimeError("A instância não ficou com 6 plataformas.")
        if minimo < 2:
            raise RuntimeError("A instância não força múltiplos navios.")

        caminho = destino / scenario["arquivo"]
        caminho.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(
            f"{caminho.name} | load={total_load:.0f} | "
            f"backload={total_back:.0f} | mínimo={minimo} navios"
        )

    print(f"\nArquivos criados em: {destino}")

if __name__ == "__main__":
    gerar()
