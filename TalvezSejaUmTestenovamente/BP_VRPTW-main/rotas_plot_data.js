window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Melhor inteira do pool | rotas ativas: 3",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=56",
      "vehicle": 0,
      "sequence": [
        0,
        2,
        6,
        7,
        8,
        4,
        5,
        3,
        1,
        26
      ],
      "total_real_cost": 95.8,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 2,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 30.0,
          "due_date": 168.0,
          "service_time": 10.0
        },
        {
          "id": 6,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 60.0,
          "due_date": 159.0,
          "service_time": 10.0
        },
        {
          "id": 7,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 54.0,
          "due_date": 133.0,
          "service_time": 10.0
        },
        {
          "id": 8,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 67.0,
          "due_date": 144.0,
          "service_time": 10.0
        },
        {
          "id": 4,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 69.0,
          "due_date": 193.0,
          "service_time": 10.0
        },
        {
          "id": 5,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 40.0,
          "due_date": 189.0,
          "service_time": 10.0
        },
        {
          "id": 3,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 95.0,
          "due_date": 152.0,
          "service_time": 10.0
        },
        {
          "id": 1,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 49.0,
          "due_date": 191.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 2,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 30.8,
          "reduced_cost": 27.068716
        },
        {
          "from": 2,
          "to": 6,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 4.0,
          "reduced_cost": 4.0
        },
        {
          "from": 6,
          "to": 7,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 3.0,
          "reduced_cost": -31.944121
        },
        {
          "from": 7,
          "to": 8,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": -14.034844
        },
        {
          "from": 8,
          "to": 4,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": -3.821036
        },
        {
          "from": 4,
          "to": 5,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 5.0,
          "reduced_cost": -15.779072
        },
        {
          "from": 5,
          "to": 3,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 2.0,
          "reduced_cost": 29.57918
        },
        {
          "from": 3,
          "to": 1,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": -13.096548
        },
        {
          "from": 1,
          "to": 26,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 38.0,
          "reduced_cost": 38.0
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=112",
      "vehicle": 1,
      "sequence": [
        0,
        12,
        14,
        17,
        16,
        15,
        13,
        9,
        11,
        10,
        26
      ],
      "total_real_cost": 97.0,
      "total_reduced_cost": -44.3,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 12,
          "x": 8.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 32.0,
          "due_date": 148.0,
          "service_time": 10.0
        },
        {
          "id": 14,
          "x": 5.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 35.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 17,
          "x": 0.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 51.0,
          "due_date": 189.0,
          "service_time": 10.0
        },
        {
          "id": 16,
          "x": 0.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 41.0,
          "due_date": 141.0,
          "service_time": 10.0
        },
        {
          "id": 15,
          "x": 2.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 39.0,
          "due_date": 163.0,
          "service_time": 10.0
        },
        {
          "id": 13,
          "x": 5.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 53.0,
          "due_date": 191.0,
          "service_time": 10.0
        },
        {
          "id": 9,
          "x": 10.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 57.0,
          "due_date": 154.0,
          "service_time": 10.0
        },
        {
          "id": 11,
          "x": 8.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 33.0,
          "due_date": 152.0,
          "service_time": 10.0
        },
        {
          "id": 10,
          "x": 10.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 106.0,
          "due_date": 161.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 12,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 8.0,
          "to_y": 45.0,
          "real_cost": 32.3,
          "reduced_cost": 26.530205
        },
        {
          "from": 12,
          "to": 14,
          "from_x": 8.0,
          "from_y": 45.0,
          "to_x": 5.0,
          "to_y": 45.0,
          "real_cost": 3.0,
          "reduced_cost": 21.954369
        },
        {
          "from": 14,
          "to": 17,
          "from_x": 5.0,
          "from_y": 45.0,
          "to_x": 0.0,
          "to_y": 45.0,
          "real_cost": 5.0,
          "reduced_cost": -6.029558
        },
        {
          "from": 17,
          "to": 16,
          "from_x": 0.0,
          "from_y": 45.0,
          "to_x": 0.0,
          "to_y": 40.0,
          "real_cost": 5.0,
          "reduced_cost": -10.59849
        },
        {
          "from": 16,
          "to": 15,
          "from_x": 0.0,
          "from_y": 40.0,
          "to_x": 2.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": -43.1
        },
        {
          "from": 15,
          "to": 13,
          "from_x": 2.0,
          "from_y": 40.0,
          "to_x": 5.0,
          "to_y": 35.0,
          "real_cost": 5.8,
          "reduced_cost": -13.945739
        },
        {
          "from": 13,
          "to": 9,
          "from_x": 5.0,
          "from_y": 35.0,
          "to_x": 10.0,
          "to_y": 35.0,
          "real_cost": 5.0,
          "reduced_cost": -1.826321
        },
        {
          "from": 9,
          "to": 11,
          "from_x": 10.0,
          "from_y": 35.0,
          "to_x": 8.0,
          "to_y": 40.0,
          "real_cost": 5.3,
          "reduced_cost": -15.20712
        },
        {
          "from": 11,
          "to": 10,
          "from_x": 8.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": -13.70507
        },
        {
          "from": 10,
          "to": 26,
          "from_x": 10.0,
          "from_y": 40.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 31.6,
          "reduced_cost": 31.6
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=78",
      "vehicle": 2,
      "sequence": [
        0,
        22,
        20,
        19,
        18,
        21,
        23,
        25,
        24,
        26
      ],
      "total_real_cost": 101.7,
      "total_reduced_cost": -0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 22,
          "x": 40.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 64.0,
          "due_date": 149.0,
          "service_time": 10.0
        },
        {
          "id": 20,
          "x": 42.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 94.0,
          "due_date": 179.0,
          "service_time": 10.0
        },
        {
          "id": 19,
          "x": 42.0,
          "y": 10.0,
          "kind": "customer",
          "ready_time": 40.0,
          "due_date": 148.0,
          "service_time": 10.0
        },
        {
          "id": 18,
          "x": 44.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 73.0,
          "due_date": 130.0,
          "service_time": 10.0
        },
        {
          "id": 21,
          "x": 40.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 45.0,
          "due_date": 161.0,
          "service_time": 10.0
        },
        {
          "id": 23,
          "x": 38.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 45.0,
          "due_date": 164.0,
          "service_time": 10.0
        },
        {
          "id": 25,
          "x": 35.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 45.0,
          "due_date": 183.0,
          "service_time": 10.0
        },
        {
          "id": 24,
          "x": 38.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 51.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 22,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 40.0,
          "to_y": 15.0,
          "real_cost": 35.0,
          "reduced_cost": 57.383064
        },
        {
          "from": 22,
          "to": 20,
          "from_x": 40.0,
          "from_y": 15.0,
          "to_x": 42.0,
          "to_y": 15.0,
          "real_cost": 2.0,
          "reduced_cost": 9.851241
        },
        {
          "from": 20,
          "to": 19,
          "from_x": 42.0,
          "from_y": 15.0,
          "to_x": 42.0,
          "to_y": 10.0,
          "real_cost": 5.0,
          "reduced_cost": -11.212082
        },
        {
          "from": 19,
          "to": 18,
          "from_x": 42.0,
          "from_y": 10.0,
          "to_x": 44.0,
          "to_y": 5.0,
          "real_cost": 5.3,
          "reduced_cost": -18.569471
        },
        {
          "from": 18,
          "to": 21,
          "from_x": 44.0,
          "from_y": 5.0,
          "to_x": 40.0,
          "to_y": 5.0,
          "real_cost": 4.0,
          "reduced_cost": -58.048975
        },
        {
          "from": 21,
          "to": 23,
          "from_x": 40.0,
          "from_y": 5.0,
          "to_x": 38.0,
          "to_y": 5.0,
          "real_cost": 2.0,
          "reduced_cost": 1.840022
        },
        {
          "from": 23,
          "to": 25,
          "from_x": 38.0,
          "from_y": 5.0,
          "to_x": 35.0,
          "to_y": 5.0,
          "real_cost": 3.0,
          "reduced_cost": -0.702589
        },
        {
          "from": 25,
          "to": 24,
          "from_x": 35.0,
          "from_y": 5.0,
          "to_x": 38.0,
          "to_y": 15.0,
          "real_cost": 10.4,
          "reduced_cost": 4.431068
        },
        {
          "from": 24,
          "to": 26,
          "from_x": 38.0,
          "from_y": 15.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 35.0,
          "reduced_cost": 35.0
        }
      ],
      "color": "#0f766e"
    }
  ]
};
