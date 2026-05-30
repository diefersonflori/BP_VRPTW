window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Melhor inteira do pool | rotas ativas: 3",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=0",
      "vehicle": 0,
      "sequence": [
        0,
        20,
        24,
        25,
        10,
        11,
        9,
        6,
        23,
        22,
        21,
        3,
        5,
        26
      ],
      "total_real_cost": 100.4,
      "total_reduced_cost": -556.129872,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 20,
          "x": 30.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 10.0,
          "due_date": 73.0,
          "service_time": 90.0
        },
        {
          "id": 24,
          "x": 25.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 65.0,
          "due_date": 144.0,
          "service_time": 90.0
        },
        {
          "id": 25,
          "x": 25.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 169.0,
          "due_date": 224.0,
          "service_time": 90.0
        },
        {
          "id": 10,
          "x": 35.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 357.0,
          "due_date": 410.0,
          "service_time": 90.0
        },
        {
          "id": 11,
          "x": 35.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 448.0,
          "due_date": 505.0,
          "service_time": 90.0
        },
        {
          "id": 9,
          "x": 38.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 534.0,
          "due_date": 605.0,
          "service_time": 90.0
        },
        {
          "id": 6,
          "x": 40.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 621.0,
          "due_date": 702.0,
          "service_time": 90.0
        },
        {
          "id": 23,
          "x": 28.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 732.0,
          "due_date": 777.0,
          "service_time": 90.0
        },
        {
          "id": 22,
          "x": 28.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 812.0,
          "due_date": 883.0,
          "service_time": 90.0
        },
        {
          "id": 21,
          "x": 30.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1135.0,
          "service_time": 90.0
        },
        {
          "id": 3,
          "x": 42.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1129.0,
          "service_time": 90.0
        },
        {
          "id": 5,
          "x": 42.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1130.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 20,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 30.0,
          "to_y": 50.0,
          "real_cost": 10.0,
          "reduced_cost": 2532.785051
        },
        {
          "from": 20,
          "to": 24,
          "from_x": 30.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 50.0,
          "real_cost": 5.0,
          "reduced_cost": 383.635286
        },
        {
          "from": 24,
          "to": 25,
          "from_x": 25.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": 939.416687
        },
        {
          "from": 25,
          "to": 10,
          "from_x": 25.0,
          "from_y": 52.0,
          "to_x": 35.0,
          "to_y": 66.0,
          "real_cost": 17.2,
          "reduced_cost": 3299.463367
        },
        {
          "from": 10,
          "to": 11,
          "from_x": 35.0,
          "from_y": 66.0,
          "to_x": 35.0,
          "to_y": 69.0,
          "real_cost": 3.0,
          "reduced_cost": 4183.298976
        },
        {
          "from": 11,
          "to": 9,
          "from_x": 35.0,
          "from_y": 69.0,
          "to_x": 38.0,
          "to_y": 70.0,
          "real_cost": 3.1,
          "reduced_cost": 497.22501
        },
        {
          "from": 9,
          "to": 6,
          "from_x": 38.0,
          "from_y": 70.0,
          "to_x": 40.0,
          "to_y": 69.0,
          "real_cost": 2.2,
          "reduced_cost": -14.910451
        },
        {
          "from": 6,
          "to": 23,
          "from_x": 40.0,
          "from_y": 69.0,
          "to_x": 28.0,
          "to_y": 55.0,
          "real_cost": 18.4,
          "reduced_cost": 2406.017481
        },
        {
          "from": 23,
          "to": 22,
          "from_x": 28.0,
          "from_y": 55.0,
          "to_x": 28.0,
          "to_y": 52.0,
          "real_cost": 3.0,
          "reduced_cost": 4667.798397
        },
        {
          "from": 22,
          "to": 21,
          "from_x": 28.0,
          "from_y": 52.0,
          "to_x": 30.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": 4660.213535
        },
        {
          "from": 21,
          "to": 3,
          "from_x": 30.0,
          "from_y": 52.0,
          "to_x": 42.0,
          "to_y": 66.0,
          "real_cost": 18.4,
          "reduced_cost": 5102.819273
        },
        {
          "from": 3,
          "to": 5,
          "from_x": 42.0,
          "from_y": 66.0,
          "to_x": 42.0,
          "to_y": 65.0,
          "real_cost": 1.0,
          "reduced_cost": 3971.958451
        },
        {
          "from": 5,
          "to": 26,
          "from_x": 42.0,
          "from_y": 65.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 15.1,
          "reduced_cost": 15.1
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=0",
      "vehicle": 1,
      "sequence": [
        0,
        13,
        17,
        8,
        14,
        12,
        4,
        2,
        1,
        7,
        26
      ],
      "total_real_cost": 133.1,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 13,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 30.0,
          "due_date": 92.0,
          "service_time": 90.0
        },
        {
          "id": 17,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 99.0,
          "due_date": 148.0,
          "service_time": 90.0
        },
        {
          "id": 8,
          "x": 38.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 255.0,
          "due_date": 324.0,
          "service_time": 90.0
        },
        {
          "id": 14,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 567.0,
          "due_date": 620.0,
          "service_time": 90.0
        },
        {
          "id": 12,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1107.0,
          "service_time": 90.0
        },
        {
          "id": 4,
          "x": 42.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 727.0,
          "due_date": 782.0,
          "service_time": 90.0
        },
        {
          "id": 2,
          "x": 45.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1125.0,
          "service_time": 90.0
        },
        {
          "id": 1,
          "x": 45.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1127.0,
          "service_time": 90.0
        },
        {
          "id": 7,
          "x": 40.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 1130.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 13,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 30.8,
          "reduced_cost": 706.494007
        },
        {
          "from": 13,
          "to": 17,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 4.0,
          "reduced_cost": 2941.112943
        },
        {
          "from": 17,
          "to": 8,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 38.0,
          "to_y": 68.0,
          "real_cost": 21.1,
          "reduced_cost": 4792.899475
        },
        {
          "from": 8,
          "to": 14,
          "from_x": 38.0,
          "from_y": 68.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 23.3,
          "reduced_cost": -4166.58637
        },
        {
          "from": 14,
          "to": 12,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": 7726.23169
        },
        {
          "from": 12,
          "to": 4,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 42.0,
          "to_y": 68.0,
          "real_cost": 24.0,
          "reduced_cost": 4479.030128
        },
        {
          "from": 4,
          "to": 2,
          "from_x": 42.0,
          "from_y": 68.0,
          "to_x": 45.0,
          "to_y": 70.0,
          "real_cost": 3.6,
          "reduced_cost": 6769.507259
        },
        {
          "from": 2,
          "to": 1,
          "from_x": 45.0,
          "from_y": 70.0,
          "to_x": 45.0,
          "to_y": 68.0,
          "real_cost": 2.0,
          "reduced_cost": 4716.618397
        },
        {
          "from": 1,
          "to": 7,
          "from_x": 45.0,
          "from_y": 68.0,
          "to_x": 40.0,
          "to_y": 66.0,
          "real_cost": 5.3,
          "reduced_cost": 5219.643407
        },
        {
          "from": 7,
          "to": 26,
          "from_x": 40.0,
          "from_y": 66.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 16.0,
          "reduced_cost": 16.0
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=0",
      "vehicle": 2,
      "sequence": [
        0,
        18,
        19,
        15,
        16,
        26
      ],
      "total_real_cost": 90.6,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 18,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 179.0,
          "due_date": 254.0,
          "service_time": 90.0
        },
        {
          "id": 19,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 278.0,
          "due_date": 345.0,
          "service_time": 90.0
        },
        {
          "id": 15,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 384.0,
          "due_date": 429.0,
          "service_time": 90.0
        },
        {
          "id": 16,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 475.0,
          "due_date": 528.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 18,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 35.3,
          "reduced_cost": 5205.681603
        },
        {
          "from": 18,
          "to": 19,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": 7912.969333
        },
        {
          "from": 19,
          "to": 15,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": 10023.0
        },
        {
          "from": 15,
          "to": 16,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 5.0,
          "reduced_cost": 10019.0
        },
        {
          "from": 16,
          "to": 26,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 40.3,
          "reduced_cost": 40.3
        }
      ],
      "color": "#0f766e"
    }
  ]
};
