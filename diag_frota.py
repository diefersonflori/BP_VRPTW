import json

js = json.load(open(r"instancias/Petro_instancias/10n-1k-3c-1r_testeUSP_v33.json"))
frota = js["input"]["fleetData"]
n0 = frota[0]
print("Navio de referencia:", n0.get("vesselName"))
achou = False
for v in frota:
    for campo in ["capacity", "tripDurationLimit", "setupArrival",
                  "setupDeparture", "velocities"]:
        if v[campo] != n0[campo]:
            achou = True
            print("DIFERENTE: %s | campo=%s | %s vs %s"
                  % (v.get("vesselName"), campo, v[campo], n0[campo]))
if not achou:
    print("Frota homogenea neste arquivo - o aviso nao deveria disparar.")