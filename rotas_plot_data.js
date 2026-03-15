window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Rotas ativas: 2",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=90",
      "vehicle": 0,
      "sequence": [
        0,
        6,
        5,
        8,
        7,
        11,
        10,
        14
      ],
      "total_real_cost": 98.990721,
      "total_reduced_cost": -0.0,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 6,
          "x": 25.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 5,
          "x": 15.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 8,
          "x": 10.0,
          "y": 43.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 7,
          "x": 20.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 11,
          "x": 20.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 67.0,
          "due_date": 77.0,
          "service_time": 0.0
        },
        {
          "id": 10,
          "x": 30.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 124.0,
          "due_date": 154.0,
          "service_time": 0.0
        },
        {
          "id": 14,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 6,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 25.0,
          "to_y": 30.0,
          "real_cost": 11.18034,
          "reduced_cost": 4.144381
        },
        {
          "from": 6,
          "to": 5,
          "from_x": 25.0,
          "from_y": 30.0,
          "to_x": 15.0,
          "to_y": 30.0,
          "real_cost": 10.0,
          "reduced_cost": 1.67426
        },
        {
          "from": 5,
          "to": 8,
          "from_x": 15.0,
          "from_y": 30.0,
          "to_x": 10.0,
          "to_y": 43.0,
          "real_cost": 13.928388,
          "reduced_cost": 0.81626
        },
        {
          "from": 8,
          "to": 7,
          "from_x": 10.0,
          "from_y": 43.0,
          "to_x": 20.0,
          "to_y": 50.0,
          "real_cost": 12.206556,
          "reduced_cost": -13.427433
        },
        {
          "from": 7,
          "to": 11,
          "from_x": 20.0,
          "from_y": 50.0,
          "to_x": 20.0,
          "to_y": 65.0,
          "real_cost": 15.0,
          "reduced_cost": -999985.0
        },
        {
          "from": 11,
          "to": 10,
          "from_x": 20.0,
          "from_y": 65.0,
          "to_x": 30.0,
          "to_y": 60.0,
          "real_cost": 11.18034,
          "reduced_cost": 4.964867
        },
        {
          "from": 10,
          "to": 14,
          "from_x": 30.0,
          "from_y": 60.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 25.495098,
          "reduced_cost": 25.495098
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=86",
      "vehicle": 1,
      "sequence": [
        0,
        1,
        9,
        3,
        12,
        4,
        2,
        13,
        14
      ],
      "total_real_cost": 115.865838,
      "total_reduced_cost": -0.035109,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 1,
          "x": 41.0,
          "y": 49.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 9,
          "x": 55.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 3,
          "x": 55.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 12,
          "x": 50.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 63.0,
          "due_date": 73.0,
          "service_time": 0.0
        },
        {
          "id": 4,
          "x": 55.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 2,
          "x": 35.0,
          "y": 17.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        },
        {
          "id": 13,
          "x": 30.0,
          "y": 25.0,
          "kind": "customer",
          "ready_time": 159.0,
          "due_date": 169.0,
          "service_time": 0.0
        },
        {
          "id": 14,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 9999.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 1,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 41.0,
          "to_y": 49.0,
          "real_cost": 15.231546,
          "reduced_cost": 14.140161
        },
        {
          "from": 1,
          "to": 9,
          "from_x": 41.0,
          "from_y": 49.0,
          "to_x": 55.0,
          "to_y": 60.0,
          "real_cost": 17.804494,
          "reduced_cost": -4.407735
        },
        {
          "from": 9,
          "to": 3,
          "from_x": 55.0,
          "from_y": 60.0,
          "to_x": 55.0,
          "to_y": 45.0,
          "real_cost": 15.0,
          "reduced_cost": -2.672079
        },
        {
          "from": 3,
          "to": 12,
          "from_x": 55.0,
          "from_y": 45.0,
          "to_x": 50.0,
          "to_y": 35.0,
          "real_cost": 11.18034,
          "reduced_cost": -999978.684531
        },
        {
          "from": 12,
          "to": 4,
          "from_x": 50.0,
          "from_y": 35.0,
          "to_x": 55.0,
          "to_y": 20.0,
          "real_cost": 15.811388,
          "reduced_cost": -0.068795
        },
        {
          "from": 4,
          "to": 2,
          "from_x": 55.0,
          "from_y": 20.0,
          "to_x": 35.0,
          "to_y": 17.0,
          "real_cost": 20.223748,
          "reduced_cost": 10.588638
        },
        {
          "from": 2,
          "to": 13,
          "from_x": 35.0,
          "from_y": 17.0,
          "to_x": 30.0,
          "to_y": 25.0,
          "real_cost": 9.433981,
          "reduced_cost": -9.071929
        },
        {
          "from": 13,
          "to": 14,
          "from_x": 30.0,
          "from_y": 25.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 11.18034,
          "reduced_cost": 11.18034
        }
      ],
      "color": "#ef4444"
    }
  ]
};
