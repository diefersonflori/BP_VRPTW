from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

COMMODITY_MAP = {
    "DCP": "deckCargoBackload",
    "DCD": "deckCargoLoad",
    "DD": "dieselLoad",
    "WD": "waterLoad",
}

EFF_FIELD = {
    "DCP": "DCP_Ef",
    "DCD": "DCD_Ef",
    "DD": "DD_Ef",
    "WD": "WD_Ef",
}

CAPACITY_MAP = {
    "DC": "deckSpace",
    "D": "dieselTanks",
    "W": "waterTanks",
}


def _split(line: str) -> list[str]:
    return re.split(r"\s+", line.strip()) if line.strip() else []


def _find_exact(lines: list[str], text: str) -> int:
    wanted = text.strip().lower()
    for i, line in enumerate(lines):
        if line.strip().lower() == wanted:
            return i
    raise ValueError(f"Secao nao encontrada: {text}")


def _find_tokens(lines: list[str], tokens: list[str]) -> int:
    wanted = [x.lower() for x in tokens]
    for i, line in enumerate(lines):
        got = [x.lower() for x in _split(line)]
        if got[:len(wanted)] == wanted:
            return i
    raise ValueError(f"Cabecalho nao encontrado: {' '.join(tokens)}")


def _next_nonempty(lines: list[str], start: int) -> tuple[int, str]:
    for i in range(start, len(lines)):
        if lines[i].strip():
            return i, lines[i]
    raise ValueError("Fim de arquivo inesperado")


def _number(token: str):
    value = float(token)
    return int(value) if value.is_integer() else value


def _inv_eff(hours_per_unit: float) -> float:
    if hours_per_unit <= 0:
        raise ValueError(f"Eficiencia invalida (h/unidade): {hours_per_unit}")
    return 1.0 / hours_per_unit


def _vessel_classes(source_name: str, n_vehicles: int) -> list[str]:
    # Ex.: 14n-2k-6c-008r_ML.txt -> ["M", "L"]
    suffix = Path(source_name).stem.rsplit("_", 1)[-1].upper()
    if len(suffix) == n_vehicles and suffix.isalpha():
        return list(suffix)
    return [suffix] * n_vehicles


def _client_windows(client: dict, header: list[str]) -> list[list[float]]:
    suffixes = []
    for field in header:
        match = re.fullmatch(r"ET(\d+)", field, flags=re.IGNORECASE)
        if match:
            suffixes.append(int(match.group(1)))

    windows = []
    for suffix in sorted(set(suffixes)):
        et = client.get(f"ET{suffix}")
        lt = client.get(f"LT{suffix}")
        if et is not None and lt is not None:
            windows.append([float(et), float(lt)])
    return windows


def parse_silva(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    # Clients / Orders
    idx = _find_tokens(lines, ["Clients", "Orders"])
    _, row = _next_nonempty(lines, idx + 1)
    values = _split(row)
    if len(values) < 2:
        raise ValueError("Linha Clients/Orders invalida")
    n_clients, n_orders = int(values[0]), int(values[1])

    # Vehicles / Threshold distance
    idx = _find_tokens(lines, ["Vehicles", "Threshold"])
    _, row = _next_nonempty(lines, idx + 1)
    values = _split(row)
    if len(values) < 2:
        raise ValueError("Linha Vehicles/Threshold invalida")
    n_vehicles, threshold = int(values[0]), float(values[1])

    # Vehicles information
    idx = _find_exact(lines, "Vehicles information")
    hidx, header_line = _next_nonempty(lines, idx + 1)
    vheader = _split(header_line)
    vehicles = []
    cursor = hidx + 1
    for _ in range(n_vehicles):
        cursor, row = _next_nonempty(lines, cursor)
        values = _split(row)
        if len(values) != len(vheader):
            raise ValueError(f"Linha de veiculo invalida: {row}")
        vehicles.append({k: _number(v) for k, v in zip(vheader, values)})
        cursor += 1

    # Clients information: inclui a base ID=0
    idx = _find_exact(lines, "Clients information")
    hidx, header_line = _next_nonempty(lines, idx + 1)
    cheader = _split(header_line)
    clients = {}
    cursor = hidx + 1
    for _ in range(n_clients + 1):
        cursor, row = _next_nonempty(lines, cursor)
        values = _split(row)
        if len(values) > len(cheader):
            raise ValueError(f"Linha de cliente com colunas extras: {row}")
        client = {k: _number(v) for k, v in zip(cheader, values)}
        client["windows"] = _client_windows(client, cheader)
        clients[int(client["ID"])] = client
        cursor += 1

    if 0 not in clients:
        raise ValueError("Base ID=0 nao encontrada")

    # Orders information: ID seguido de tokens COMMODITY/QUANTITY/DEADLINE
    idx = _find_exact(lines, "Orders information")
    hidx, _ = _next_nonempty(lines, idx + 1)  # pula o cabecalho das orders
    cursor = hidx + 1
    source_orders = []
    while cursor < len(lines):
        text = lines[cursor].strip()
        if not text:
            cursor += 1
            continue
        if text.lower() == "capacity commodity assignment":
            break

        values = _split(text)
        cid = int(values[0])
        if cid not in clients:
            raise ValueError(f"Order referencia clientId inexistente: {cid}")

        for spec in values[1:]:
            parts = spec.split("/")
            if len(parts) != 3:
                raise ValueError(f"Order invalida: {spec}")
            commodity, quantity, deadline = parts
            commodity = commodity.upper()
            if commodity not in COMMODITY_MAP:
                raise ValueError(f"Commodity desconhecida: {commodity}")
            source_orders.append({
                "clientId": cid,
                "commodityCode": commodity,
                "quantity": abs(float(quantity)),
                "rawQuantity": float(quantity),
                "dueTime": float(deadline),
            })
        cursor += 1

    if len(source_orders) != n_orders:
        raise ValueError(f"Cabecalho declara {n_orders} orders, mas foram lidas {len(source_orders)}")

    # Capacity commodity assignment
    idx = _find_exact(lines, "Capacity commodity assignment")
    hidx, header_line = _next_nonempty(lines, idx + 1)
    aheader = _split(header_line)
    assignments = []
    cursor = hidx + 1
    while cursor < len(lines):
        text = lines[cursor].strip()
        if not text:
            cursor += 1
            continue
        values = _split(text)
        if len(values) != len(aheader):
            break
        row = {}
        for key, value in zip(aheader, values):
            row[key] = value if key.upper() == "CAP" else _number(value)
        assignments.append(row)
        cursor += 1

    return {
        "n_clients": n_clients,
        "n_orders": n_orders,
        "n_vehicles": n_vehicles,
        "threshold": threshold,
        "vehicles": vehicles,
        "clients": clients,
        "orders": source_orders,
        "assignments": assignments,
    }


def to_project_json(data: dict, source_name: str, alpha: float = 0.1) -> dict:
    base = data["clients"][0]
    classes = _vessel_classes(source_name, data["n_vehicles"])

    capacity_assignment = []
    for row in data["assignments"]:
        cap = str(row["CAP"]).upper()
        if cap not in CAPACITY_MAP:
            continue
        capacity_assignment.append({
            "compartment": CAPACITY_MAP[cap],
            "deckCargoBackload": int(row.get("DCP", 0)),
            "deckCargoLoad": int(row.get("DCD", 0)),
            "dieselLoad": int(row.get("DD", 0)),
            "waterLoad": int(row.get("WD", 0)),
        })

    fleet = []
    for pos, v in enumerate(data["vehicles"]):
        vessel_class = classes[pos]
        fleet.append({
            "vesselId": int(v["ID"]),
            "vesselName": f"SILVA_{vessel_class}_{int(v['ID'])}",
            "vesselClass": vessel_class,
            "maximumNumberOfTrips": int(v["TRI"]),
            "tripDurationLimit": float(v["TDL"]),
            "setupArrival": 0.0,
            "setupDeparture": 0.0,
            "estimatedTimeOfReadiness": float(v["ETR"]),
            # O arquivo Silva nao fornece esse parametro Petrobras.
            "maximumDepartureTime": 0.0,
            "latitude": float(base["LAT"]),
            "longitude": float(base["LON"]),
            "capacity": {
                "deckSpace": float(v["DC"]),
                "dieselTanks": float(v["D"]),
                "waterTanks": float(v["W"]),
            },
            # Silva fornece custos horarios FCA/FCB/FCN/FCS, nao consumo volumetrico.
            "fuelConsumption": {
                "anchored": 0.0,
                "base": 0.0,
                "navigation": 0.0,
                "dynamic": 0.0,
            },
            "fuelCost": {
                "anchored": float(v["FCA"]),
                "base": float(v["FCB"]),
                "navigation": float(v["FCN"]),
                "dynamic": float(v["FCS"]),
            },
            "safePositioningTime": float(v["SPO"]),
            "velocities": [
                {"above": float(data["threshold"]), "speed": float(v["VH"])},
                {"above": 0.0, "speed": float(v["VL"])},
            ],
            "initialStock": {"dieselLoad": 0.0, "waterLoad": 0.0},
        })

    orders = []
    for oid, src in enumerate(data["orders"]):
        cid = src["clientId"]
        client = data["clients"][cid]
        code = src["commodityCode"]
        hours_per_unit = float(client[EFF_FIELD[code]])
        windows = client["windows"]
        if not windows:
            raise ValueError(f"Cliente {cid} sem janela de tempo")

        orders.append({
            # 0-based para ficar igual a numeracao apresentada no artigo Silva.
            "orderId": oid,
            "clientId": int(cid),
            "clientName": f"PLAT_{cid}",
            "clusterName": "SILVA2024",
            "commodity": COMMODITY_MAP[code],
            # O leitor do projeto usa tempo = quantidade / efficiency.
            # Silva fornece *_Ef em horas/unidade, portanto fazemos 1 / *_Ef.
            "efficiency": _inv_eff(hours_per_unit),
            "serviceSetup": 0.0,
            "platformSetup": float(client.get("SET", 0.0)),
            "latitude": float(client["LAT"]),
            "longitude": float(client["LON"]),
            "orderPriorityClient": 0,
            "penaltyDueDate": 0.0,
            "penaltyReadyTime": 0.0,
            "quantity": float(src["quantity"]),
            "dueTime": float(src["dueTime"]),
            "successor": None,
            "fix_successor_seq": False,
            "transshipment": None,
            "timeWindows": [[float(a), float(b)] for a, b in windows],
        })

    return {
        "instanceInformation": {
            "userComments": [
                "Conversao automatica do benchmark PSVRP de Silva et al. (2024).",
                f"Fonte: {source_name}",
            ],
        },
        "input": {
            "basicData": {
                "objectiveMode": "silva2024",
                "alphaWeight": float(alpha),
                # Campos abaixo existem no schema Petrobras. Nao sao parametros do benchmark Silva.
                "etaConversion": 1.4,
                "dieselDensity": 0.852,
                "conversionTonDieselTonCO2Eq": 3.595,
                "numberOfOrders": int(data["n_orders"]),
                "numberOfVessels": int(data["n_vehicles"]),
                "numberOfClients": int(data["n_clients"]),
                "numberOfBackloadCommodities": 1,
                "numberOfCompartments": 3,
                "numberOfLoadCommodities": 3,
                "tripClass": "silva2024",
                "pickupDeckBeforeDeliveryDeck": True,
                "distanceThreshold": float(data["threshold"]),
                "conversionNote": (
                    "etaConversion/dieselDensity/conversionTonDieselTonCO2Eq foram mantidos apenas "
                    "por compatibilidade com o schema Petrobras; nao vieram do benchmark Silva. "
                    "No modo silva2024 os dados relevantes sao fuelCost (FCA/FCB/FCN/FCS), "
                    "safePositioningTime (SPO), platformSetup (SET), dueTime, janelas, capacidades e velocidades."
                ),
            },
            "capacityCommodityAssignmentData": capacity_assignment,
            "fleetData": fleet,
            "supplyBasesData": [{
                "baseName": "BASE_SILVA",
                "baseId": 0,
                "region": "SILVA2024",
                "efficiency": {
                    "deckCargoBackload": _inv_eff(float(base["DCP_Ef"])),
                    "deckCargoLoad": _inv_eff(float(base["DCD_Ef"])),
                    "dieselLoad": _inv_eff(float(base["DD_Ef"])),
                    "waterLoad": _inv_eff(float(base["WD_Ef"])),
                },
                "successor": None,
                "navigationTimeToMoor": 0.0,
                "latitude": float(base["LAT"]),
                "longitude": float(base["LON"]),
            }],
            "ordersData": orders,
        },
    }


def validate_conversion(src: dict, out: dict) -> None:
    inp = out["input"]
    basic = inp["basicData"]
    assert basic["numberOfOrders"] == len(inp["ordersData"]) == src["n_orders"]
    assert basic["numberOfVessels"] == len(inp["fleetData"]) == src["n_vehicles"]
    assert basic["numberOfClients"] == src["n_clients"]
    assert basic["objectiveMode"] == "silva2024"

    # Garante que quantidade, deadline e duracao de servico nao mudaram na conversao.
    for raw, order in zip(src["orders"], inp["ordersData"]):
        assert abs(abs(raw["rawQuantity"]) - order["quantity"]) < 1e-9
        assert abs(raw["dueTime"] - order["dueTime"]) < 1e-9
        client = src["clients"][raw["clientId"]]
        hpu = float(client[EFF_FIELD[raw["commodityCode"]]])
        expected_service_h = order["quantity"] * hpu
        converted_service_h = order["quantity"] / order["efficiency"]
        assert abs(expected_service_h - converted_service_h) < 1e-9


def convert_file(input_path: Path, output_path: Path, alpha: float = 0.1) -> None:
    src = parse_silva(input_path)
    out = to_project_json(src, input_path.name, alpha=alpha)
    validate_conversion(src, out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK  {input_path.name} -> {output_path.name} | "
        f"{src['n_orders']} orders | {src['n_vehicles']} navios | {src['n_clients']} plataformas"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte instancias PSVRP de Silva et al. (2024) para o JSON usado no projeto BP_VRPTW."
    )
    parser.add_argument("entrada", type=Path, help="Arquivo .txt ou pasta contendo as instancias Silva")
    parser.add_argument(
        "-o", "--saida", type=Path, default=None,
        help="Arquivo/pasta de saida. Para pasta, o padrao e <entrada>/convertidas_silva2024.",
    )
    parser.add_argument(
        "--alpha", type=float, default=0.1,
        help="alphaWeight gravado no JSON (padrao 0.1). Para reproduzir testes da Tabela 3 com alpha=0, use --alpha 0.",
    )
    args = parser.parse_args()

    entrada = args.entrada.expanduser()

    if entrada.is_file():
        saida = args.saida or entrada.with_name(entrada.stem + "_silva2024.json")
        convert_file(entrada, saida, alpha=args.alpha)
        return

    if not entrada.is_dir():
        raise SystemExit(f"Entrada nao encontrada: {entrada}")

    saida_dir = args.saida or (entrada / "convertidas_silva2024")
    files = sorted(
        p for p in entrada.iterdir()
        if p.is_file() and p.suffix.lower() == ".txt" and not p.name.startswith("000_")
    )
    if not files:
        raise SystemExit(f"Nenhum .txt de instancia encontrado em {entrada}")

    ok = 0
    errors = []
    for path in files:
        try:
            convert_file(path, saida_dir / f"{path.stem}_silva2024.json", alpha=args.alpha)
            ok += 1
        except Exception as exc:
            errors.append((path.name, str(exc)))
            print(f"ERRO {path.name}: {exc}")

    print(f"\nFinalizado: {ok}/{len(files)} convertidas em {saida_dir}")
    if errors:
        print("Falhas:")
        for name, msg in errors:
            print(f"  - {name}: {msg}")
        raise SystemExit(1)


if __name__ == "__main__":

    pasta_script = Path(__file__).resolve().parent

    entrada = pasta_script / "arquivosconvertersilva"
    saida = pasta_script / "arquivosconvertidos"

    alpha = 0.1

    saida.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p for p in entrada.iterdir()
        if p.is_file()
        and not p.name.startswith("000_")
    )

    print("=" * 100)
    print("CONVERSOR INSTANCIAS SILVA")
    print(f"Entrada: {entrada}")
    print(f"Saida:   {saida}")
    print(f"Alpha:   {alpha}")
    print(f"Arquivos encontrados: {len(files)}")
    print("=" * 100)

    ok = 0
    errors = []

    for path in files:
        try:
            destino = saida / f"{path.stem}_silva2024.json"

            convert_file(path, destino, alpha=alpha)

            ok += 1

        except Exception as exc:
            errors.append((path.name, str(exc)))
            print(f"ERRO {path.name}: {exc}")

    print()
    print("=" * 100)
    print(f"FINALIZADO: {ok}/{len(files)} instancias convertidas")
    print(f"Arquivos salvos em: {saida}")

    if errors:
        print("\nFALHAS:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    print("=" * 100)
